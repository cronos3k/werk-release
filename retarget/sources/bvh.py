"""bvh.py -- read a Biovision Hierarchy file into a Rig and a Clip.

BVH is the raw mocap interchange format: an ASCII hierarchy of OFFSETs and
CHANNELs, then a flat matrix of numbers, one row per frame.

CONVERSIONS DONE HERE, AND NOWHERE ELSE
---------------------------------------
* **Euler channels -> quaternion.** The per-joint local rotation is the product
  of the single-axis rotations IN THE ORDER THE CHANNELS ARE DECLARED, which is
  usually but not always Z, Y, X. The order is read from the file per joint,
  never assumed -- getting it wrong produces a clip that is structurally perfect
  and wrong in every frame, which is precisely the failure mode this project
  exists to catch.
* **Units.** BVH carries no unit. The OFFSETs are in whatever the capture stage
  used (CMU's conversion is roughly 1 unit = 1 inch / 2.54 ...); this reader
  does NOT guess. It leaves the numbers alone and lets the calibration solve
  recover the scale, which it must do anyway for any rig whose stature differs
  from 1.75 m. The solved scale is reported as a measurement.
* **Axes.** BVH has no declared axis convention either. Same answer: the
  calibration solve recovers the whole-body rotation and reports it.

A BVH root normally carries 6 channels (3 position + 3 rotation) and every
other joint 3. Both are handled generically: any joint may declare position
channels, and a non-root joint that does is reported, because per-bone
translation is not a thing core clips carry (animclip.layout.txt D-AC-4).
"""

import numpy as np

from ..quat import euler_to_quat
from ..skeleton import Clip, Rig

_ROT = {"Xrotation": "X", "Yrotation": "Y", "Zrotation": "Z"}
_POS = {"Xposition": 0, "Yposition": 1, "Zposition": 2}


def _tokens(text):
    for line in text.splitlines():
        for tok in line.split():
            yield tok


def load(path, clip_id=None, end_site_bones=False):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    head, _, motion = text.partition("MOTION")
    if not motion:
        raise ValueError("%s: no MOTION section" % path)

    toks = list(_tokens(head))
    i = 0
    if toks[i].upper() != "HIERARCHY":
        raise ValueError("%s: does not start with HIERARCHY" % path)
    i += 1

    rig = Rig("bvh:" + path.replace("\\", "/").rsplit("/", 1)[-1],
              source={"path": path}, unit_scale_m=1.0)
    # channel plan, in file order: (bone_index, kind, spec)
    plan = []
    rot_order = {}
    stack = []
    end_sites = {}

    while i < len(toks):
        t = toks[i]
        if t in ("ROOT", "JOINT"):
            name = toks[i + 1]
            i += 2
            if toks[i] != "{":
                raise ValueError("%s: expected { after %s %s" % (path, t, name))
            i += 1
            parent = stack[-1] if stack else None
            offset = None
            channels = None
            # OFFSET and CHANNELS must both be seen before any child
            while toks[i] in ("OFFSET", "CHANNELS"):
                if toks[i] == "OFFSET":
                    offset = [float(toks[i + 1]), float(toks[i + 2]), float(toks[i + 3])]
                    i += 4
                else:
                    nc = int(toks[i + 1])
                    channels = toks[i + 2:i + 2 + nc]
                    i += 2 + nc
            if offset is None:
                raise ValueError("%s: joint %s has no OFFSET" % (path, name))
            rig.add(name, parent, offset, [1.0, 0.0, 0.0, 0.0])
            bi = rig.index[name]
            order = ""
            for c in (channels or []):
                if c in _POS:
                    plan.append((bi, "pos", _POS[c]))
                elif c in _ROT:
                    plan.append((bi, "rot", len(order)))
                    order += _ROT[c]
                else:
                    raise ValueError("%s: unknown channel %r on joint %s" % (path, c, name))
            rot_order[bi] = order
            stack.append(name)
        elif t == "End":
            # "End Site { OFFSET x y z }" -- geometry for the leaf's tail, no
            # channels. Kept as data, optionally as a bone, never as a joint.
            i += 2
            if toks[i] != "{":
                raise ValueError("%s: malformed End Site" % path)
            i += 1
            if toks[i] != "OFFSET":
                raise ValueError("%s: End Site without OFFSET" % path)
            off = [float(toks[i + 1]), float(toks[i + 2]), float(toks[i + 3])]
            i += 4
            if toks[i] != "}":
                raise ValueError("%s: End Site not closed" % path)
            i += 1
            end_sites[stack[-1]] = off
            if end_site_bones:
                rig.add(stack[-1] + "_End", stack[-1], off, [1.0, 0.0, 0.0, 0.0])
                rot_order[rig.index[stack[-1] + "_End"]] = ""
        elif t == "}":
            stack.pop()
            i += 1
        else:
            raise ValueError("%s: unexpected token %r in HIERARCHY" % (path, t))
    rig.finish()
    rig.source["end_sites"] = end_sites
    rig.source["channel_count"] = len(plan)

    mtoks = motion.split()
    j = 0

    def expect(word):
        nonlocal j
        if mtoks[j].lower() != word:
            raise ValueError("%s: expected %r in MOTION, got %r" % (path, word, mtoks[j]))
        j += 1

    expect("frames:")
    frames = int(mtoks[j]); j += 1
    expect("frame")
    expect("time:")
    ft = float(mtoks[j]); j += 1
    if ft <= 0:
        raise ValueError("%s: Frame Time is %r" % (path, ft))
    rate = 1.0 / ft

    need = frames * len(plan)
    vals = np.array(mtoks[j:j + need], dtype=np.float64)
    if vals.size != need:
        raise ValueError("%s: MOTION has %d numbers, the header promises %d x %d = %d"
                         % (path, vals.size, frames, len(plan), need))
    vals = vals.reshape(frames, len(plan))

    n = rig.n
    local_q = np.tile(rig.local_q[None, :, :], (frames, 1, 1))
    pos = np.zeros((frames, n, 3))
    euler = {}
    for col, (bi, kind, spec) in enumerate(plan):
        if kind == "pos":
            pos[:, bi, spec] = vals[:, col]
        else:
            euler.setdefault(bi, {})[spec] = np.deg2rad(vals[:, col])

    for bi, chans in euler.items():
        order = rot_order[bi]
        ang = np.stack([chans[k] for k in range(len(order))], axis=1)
        for f in range(frames):
            local_q[f, bi] = euler_to_quat(order, ang[f])

    root_bi = rig.roots()[0]
    moved = np.abs(pos).max(axis=(0, 2))
    moved[root_bi] = 0.0
    wi = int(np.argmax(moved))
    rig.source["max_nonroot_translation"] = float(moved[wi])
    rig.source["max_nonroot_translation_bone"] = rig.names[wi]

    root_t = pos[:, root_bi, :] - rig.local_t[root_bi][None, :]
    bone_t = np.tile(rig.local_t[None, :, :], (frames, 1, 1))
    # BVH position channels are absolute in the parent's frame, replacing the
    # OFFSET, not added to it -- that is what the format says, and treating
    # them as additive is a silent doubling of every root translation.
    for col, (bi, kind, spec) in enumerate(plan):
        if kind == "pos":
            bone_t[:, bi, spec] = vals[:, col]
    clip = Clip(clip_id or rig.rig_id.split(":")[-1].rsplit(".", 1)[0], rig, rate,
                local_q, root_t, root_bone=rig.names[root_bi],
                source={"path": path, "frame_time_s": ft, "frames": frames,
                        "channels": len(plan)},
                bone_t=bone_t)
    return rig, clip
