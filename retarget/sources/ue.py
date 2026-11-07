"""ue.py -- read the JSON that retarget/tools/ue_export_skeleton.py exports
from a live Unreal Engine, into a Rig and a Clip.

CONVERSIONS DONE HERE, AND NOWHERE ELSE
---------------------------------------
* **Handedness.** Unreal's world is LEFT handed (X forward, Y right, Z up);
  werk is right handed. The conversion is the reflection M = diag(1, -1, 1):

      t' = ( tx, -ty,  tz)
      q' = (  w,  -x,   y,  -z)

  The rotation half is worth stating explicitly because it is not the obvious
  one. For a reflection M (det = -1) and a rotation R = rot(n, theta),

      M R M = rot(M n, -theta)

  -- the axis mirrors AND the angle negates. With n = (x, y, z) and
  M n = (x, -y, z), the mirrored quaternion is
  (w, -sin(th/2)*x, +sin(th/2)*y, -sin(th/2)*z) = (w, -x, y, -z).
  Applying only the axis mirror, which is the mistake that looks right, gives
  (w, x, -y, z) and produces a rig that is correct in the rest pose and
  backwards in every animated frame.

  Doing it here rather than in the solver is deliberate: `umeyama_similarity`
  refuses reflections, because a reflection cannot be carried by a quaternion
  and a solver that accepted one would mirror every rotation while fitting the
  positions beautifully.
* **Units.** Unreal is centimetres. Scaled to metres by the exporter's declared
  `unit_scale_m`, which is read from the file, never assumed.
* **Up axis.** Unreal is Z-up, werk is Y-up. NOT converted here: the whole-body
  rotation is exactly what the calibration solve exists to find, and hard-coding
  it would remove the only part of this test that is actually being proven.
* **Quaternion order** was already re-ordered from Unreal's xyzw to wxyz at the
  export boundary, and the exported file says so in `source.quat_order_here`.
"""

import json

import numpy as np

from ..quat import qmul, qnorm
from ..skeleton import Clip, Rig

MIRROR_T = np.array([1.0, -1.0, 1.0])
MIRROR_Q = np.array([1.0, -1.0, 1.0, -1.0])


def _conv_t(t, scale):
    return np.asarray(t, dtype=np.float64) * MIRROR_T * scale


def _conv_q(q):
    return qnorm(np.asarray(q, dtype=np.float64) * MIRROR_Q)


def load(path, clip_name=None, clip_id=None, keep_bones=None):
    with open(path, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    src = doc["source"]
    scale = float(src.get("unit_scale_m", 0.01))
    if src.get("quat_order_here", "").split()[0] != "wxyz":
        raise ValueError("%s does not declare wxyz quaternions" % path)

    bones = doc["bones"]
    by_name = {b["name"]: b for b in bones}
    if keep_bones is not None:
        keep = set(keep_bones)
        # a kept bone's ancestors must be kept too, or the hierarchy breaks
        grow = True
        while grow:
            grow = False
            for nm in list(keep):
                p = by_name[nm].get("parent")
                if p and p not in keep:
                    keep.add(p)
                    grow = True
        bones = [b for b in bones if b["name"] in keep]

    rig = Rig("ue-mannequin",
              source={"path": path, "engine_version": src.get("engine_version"),
                      "mesh_asset": src.get("mesh_asset"), "origin": src.get("origin"),
                      "unit_scale_m": scale, "bone_count_exported": len(doc["bones"])},
              unit_scale_m=scale)

    # The exporter gives MODEL-space rest transforms (component space). Local
    # rest is derived: local_q = inv(parent_model_q) * model_q, and
    # local_t = inv(parent_model_q) * (model_t - parent_model_t).
    model_q = {}
    model_t = {}
    for b in bones:
        nm = b["name"]
        mq = _conv_q(b["rest_model"]["q"])
        mt = _conv_t(b["rest_model"]["t"], scale)
        model_q[nm] = mq
        model_t[nm] = mt
        p = b.get("parent")
        if p is None or p not in model_q:
            rig.add(nm, None, mt, mq)
        else:
            pqi = np.array([model_q[p][0], -model_q[p][1], -model_q[p][2], -model_q[p][3]])
            lq = qmul(pqi, mq)
            dt = mt - model_t[p]
            w, x, y, z = pqi
            # rotate dt by pqi
            u = np.array([x, y, z])
            uv = np.cross(u, dt)
            lt = dt + 2.0 * (w * uv + np.cross(u, uv))
            rig.add(nm, p, lt, lq)
    rig.finish()

    Q, P = rig.rest_fk()
    worst = 0.0
    for i, nm in enumerate(rig.names):
        worst = max(worst, float(np.abs(P[i] - model_t[nm]).max()))
    rig.source["rest_recompose_residual_m"] = worst
    if worst > 1e-6:
        raise ValueError("UE rest pose does not recompose: worst %.3e m" % worst)

    clips = doc["clips"]
    if clip_name is None:
        clip = clips[0]
    else:
        m = [c for c in clips if c["name"] == clip_name]
        if not m:
            raise ValueError("%s has no clip named %r (has %s)"
                             % (path, clip_name, [c["name"] for c in clips]))
        clip = m[0]

    F = int(clip["frame_count"])
    local_q = np.tile(rig.local_q[None, :, :], (F, 1, 1))
    local_t = np.tile(rig.local_t[None, :, :], (F, 1, 1))
    for nm, seq in clip["tracks"].items():
        if nm not in rig.index:
            continue
        bi = rig.index[nm]
        for f in range(F):
            local_q[f, bi] = _conv_q(seq[f]["q"])
            local_t[f, bi] = _conv_t(seq[f]["t"], scale)

    root_bi = rig.roots()[0]
    # UE's `root` bone is a locomotion root that is usually keyed at identity
    # while `pelvis` carries the actual motion; per D-AC-4 only the clip root
    # may translate, so any other animated translation is MEASURED here.
    moved = np.abs(local_t - rig.local_t[None, :, :]).max(axis=(0, 2))
    moved[root_bi] = 0.0
    wi = int(np.argmax(moved))
    rig.source["max_nonroot_translation_m"] = float(moved[wi])
    rig.source["max_nonroot_translation_bone"] = rig.names[wi]
    # ... and carried, not dropped: a rig whose pelvis translates is the normal
    # case in Unreal, so the pelvis translation is kept in `bone_t` and the
    # retargeter uses it for FK. Core clips cannot store it; the Stage 6 finding
    # S6-4 records what that costs.
    root_t = local_t[:, root_bi, :] - rig.local_t[root_bi][None, :]

    c = Clip(clip_id or clip["name"], rig, float(clip["rate_hz"]), local_q, root_t,
             root_bone=rig.names[root_bi],
             source={"path": path, "ue_clip": clip["name"],
                     "frame_count": F, "duration_s": clip["duration_s"]},
             bone_t=local_t)
    return rig, c
