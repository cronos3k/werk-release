"""gltf.py -- read a rigged, animated glTF 2.0 / GLB into a Rig and a Clip.

stdlib + numpy. No glTF library, for the same reason werk-core implements zip
and MessagePack itself: a format whose argument is "reading this needs no
ecosystem" should not need one to run its own tests.

CONVERSIONS DONE HERE, AND NOWHERE ELSE
---------------------------------------
* **Quaternion order.** glTF stores `[x, y, z, w]`; werk stores `[w, x, y, z]`.
  Reordered on read. (spec/SPEC.md Stage 1 decision 13 flags this exact trap.)
* **Axes.** glTF is right handed, +Y up, and its spec says +Z forward; werk says
  -Z forward. Stage 1 decision 13 already rules that a GLB inside a werk package
  is authored in werk model space, so the *frame* is unchanged here and any
  residual whole-body orientation (a Z-up asset carrying a `Z_UP` node, like
  CesiumMan) is absorbed by the calibration solve, which reports it as a
  measured rotation instead of a hard-coded one.
* **Node hierarchy above the joints.** The scene chain down to each joint is
  imported as ordinary bones, so an armature node's own matrix is part of FK
  rather than a correction applied later.

NOT DONE: scale. glTF nodes may carry non-uniform scale; skeletons that use it
are out of scope for core v1 (animclip.layout.txt D-AC-4 says the same thing
about translation). The reader MEASURES the worst scale deviation it saw and
puts it in `rig.source["max_scale_deviation"]`, so "there was no scale" is a
number a later reader can check rather than a claim this docstring makes.
"""

import json
import struct

import numpy as np

from ..quat import mat_to_quat, qnorm
from ..skeleton import Clip, Rig

_COMP = {
    5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2),
    5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4),
}
_NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def _read_glb(path):
    with open(path, "rb") as fh:
        blob = fh.read()
    if blob[:4] == b"glTF":
        magic, version, total = struct.unpack_from("<III", blob, 0)
        if version != 2:
            raise ValueError("%s: GLB container version %d, only 2 is defined" % (path, version))
        off = 12
        js = None
        bin_chunk = b""
        while off + 8 <= len(blob):
            clen, ctype = struct.unpack_from("<II", blob, off)
            data = blob[off + 8: off + 8 + clen]
            if ctype == 0x4E4F534A:
                js = json.loads(data.decode("utf-8"))
            elif ctype == 0x004E4942:
                bin_chunk = data
            off += 8 + clen
        if js is None:
            raise ValueError("%s: GLB has no JSON chunk" % path)
        return js, bin_chunk
    doc = json.loads(blob.decode("utf-8"))
    return doc, b""


def _accessor(doc, blob, i):
    acc = doc["accessors"][i]
    if "sparse" in acc:
        raise ValueError("accessor %d is sparse; not supported by this reader" % i)
    ncomp = _NCOMP[acc["type"]]
    fmt, size = _COMP[acc["componentType"]]
    count = acc["count"]
    if "bufferView" not in acc:
        return np.zeros((count, ncomp), dtype=np.float64)
    bv = doc["bufferViews"][acc["bufferView"]]
    base = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = bv.get("byteStride") or (ncomp * size)
    out = np.empty((count, ncomp), dtype=np.float64)
    for k in range(count):
        o = base + k * stride
        out[k] = struct.unpack_from("<" + fmt * ncomp, blob, o)
    if acc.get("normalized"):
        lim = {"b": 127.0, "B": 255.0, "h": 32767.0, "H": 65535.0}.get(fmt)
        if lim:
            out = np.maximum(out / lim, -1.0)
    return out


def _node_trs(node):
    """(t, q_wxyz, s) for one node, from either TRS or a 4x4 matrix."""
    if "matrix" in node:
        m = np.array(node["matrix"], dtype=np.float64).reshape(4, 4).T  # column-major
        t = m[:3, 3].copy()
        b = m[:3, :3]
        s = np.linalg.norm(b, axis=0)
        s = np.where(s == 0.0, 1.0, s)
        q = mat_to_quat(b / s)
        return t, q, s
    t = np.array(node.get("translation", [0.0, 0.0, 0.0]), dtype=np.float64)
    r = node.get("rotation", [0.0, 0.0, 0.0, 1.0])       # glTF xyzw
    q = qnorm(np.array([r[3], r[0], r[1], r[2]], dtype=np.float64))
    s = np.array(node.get("scale", [1.0, 1.0, 1.0]), dtype=np.float64)
    return t, q, s


def _sample_linear(times, values, t):
    """LINEAR sampler evaluation, clamped at both ends (glTF 2.0 §3.6.2.2)."""
    n = len(times)
    if t <= times[0]:
        return values[0]
    if t >= times[-1]:
        return values[-1]
    k = int(np.searchsorted(times, t) - 1)
    k = max(0, min(k, n - 2))
    span = times[k + 1] - times[k]
    u = 0.0 if span <= 0 else (t - times[k]) / span
    return values[k], values[k + 1], u


def load(path, animation=0, clip_id=None):
    """Return (rig, clip). `animation` is an index or a name."""
    doc, blob = _read_glb(path)
    nodes = doc["nodes"]
    if not doc.get("skins"):
        raise ValueError("%s has no skins; this reader wants a rigged asset" % path)
    skin = doc["skins"][0]
    joints = list(skin["joints"])

    # Parent map over the whole node graph, then the ancestor chain of every
    # joint, so an armature node's transform is FK and not a fudge factor.
    parent = {}
    for i, n in enumerate(nodes):
        for c in n.get("children", []) or []:
            parent[c] = i
    scene_roots = doc["scenes"][doc.get("scene", 0)]["nodes"]

    wanted = set()
    for j in joints:
        k = j
        while True:
            wanted.add(k)
            if k in parent:
                k = parent[k]
            else:
                break
    order = []
    seen = set()

    def walk(i):
        if i in seen or i not in wanted:
            return
        seen.add(i)
        order.append(i)
        for c in nodes[i].get("children", []) or []:
            walk(c)

    for r in scene_roots:
        walk(r)

    rig = Rig("gltf:" + (doc.get("asset", {}).get("generator") or "unknown"),
              source={"path": path, "generator": doc.get("asset", {}).get("generator"),
                      "gltf_version": doc.get("asset", {}).get("version"),
                      "joint_count": len(joints)},
              unit_scale_m=1.0)
    max_scale_dev = 0.0
    name_of = {}
    for i in order:
        n = nodes[i]
        nm = n.get("name") or ("node_%d" % i)
        name_of[i] = nm
        t, q, s = _node_trs(n)
        max_scale_dev = max(max_scale_dev, float(np.abs(s - 1.0).max()))
        p = parent.get(i)
        rig.add(nm, name_of[p] if p is not None and p in name_of else None, t, q)
    rig.finish()
    rig.source["max_scale_deviation"] = max_scale_dev
    rig.source["joint_names"] = [name_of[j] for j in joints]

    # ---- animation -> uniform grid ----------------------------------------
    anims = doc.get("animations") or []
    if not anims:
        raise ValueError("%s has no animations" % path)
    if isinstance(animation, str):
        idx = [k for k, a in enumerate(anims) if a.get("name") == animation]
        if not idx:
            raise ValueError("%s has no animation named %r" % (path, animation))
        ai = idx[0]
    else:
        ai = int(animation)
    anim = anims[ai]

    samplers = []
    for s in anim["samplers"]:
        interp = s.get("interpolation", "LINEAR")
        if interp not in ("LINEAR", "STEP"):
            raise ValueError("sampler interpolation %r is not supported; core clips are "
                             "uniformly sampled and CUBICSPLINE would need a curve "
                             "evaluator this reader deliberately does not have" % interp)
        samplers.append({
            "t": _accessor(doc, blob, s["input"])[:, 0],
            "v": _accessor(doc, blob, s["output"]),
            "interp": interp,
        })

    t0 = min(float(s["t"][0]) for s in samplers)
    t1 = max(float(s["t"][-1]) for s in samplers)
    nkeys = max(len(s["t"]) for s in samplers)
    # The asset's own densest track sets the rate; nothing is invented and
    # nothing is thrown away.
    frames = nkeys
    rate = (frames - 1) / (t1 - t0) if frames > 1 and t1 > t0 else 30.0
    grid = t0 + np.arange(frames) / rate

    local_q = np.tile(rig.local_q[None, :, :], (frames, 1, 1))
    local_t = np.tile(rig.local_t[None, :, :], (frames, 1, 1))
    channels_used = {"rotation": 0, "translation": 0, "scale": 0}
    for ch in anim["channels"]:
        tgt = ch["target"]
        ni = tgt.get("node")
        if ni is None or ni not in name_of:
            continue
        bi = rig.index[name_of[ni]]
        s = samplers[ch["sampler"]]
        path_ = tgt["path"]
        channels_used[path_] = channels_used.get(path_, 0) + 1
        if path_ == "rotation":
            for f, tt in enumerate(grid):
                r = _sample_linear(s["t"], s["v"], float(tt))
                if isinstance(r, tuple):
                    a, b, u = r
                    if s["interp"] == "STEP":
                        v = a
                    else:
                        qa = np.array([a[3], a[0], a[1], a[2]])
                        qb = np.array([b[3], b[0], b[1], b[2]])
                        if float(np.dot(qa, qb)) < 0:
                            qb = -qb
                        local_q[f, bi] = qnorm(qa * (1 - u) + qb * u)
                        continue
                else:
                    v = r
                local_q[f, bi] = qnorm(np.array([v[3], v[0], v[1], v[2]]))
        elif path_ == "translation":
            for f, tt in enumerate(grid):
                r = _sample_linear(s["t"], s["v"], float(tt))
                if isinstance(r, tuple):
                    a, b, u = r
                    v = a if s["interp"] == "STEP" else a * (1 - u) + b * u
                else:
                    v = r
                local_t[f, bi] = v[:3]

    # Per-bone translation is a rig property in core (D-AC-4). The only bone
    # allowed to move is the clip root, so any OTHER animated translation is
    # measured and reported rather than silently discarded.
    root_bi = rig.roots()[0]
    moved = np.abs(local_t - rig.local_t[None, :, :]).max(axis=(0, 2))
    moved[root_bi] = 0.0
    worst_i = int(np.argmax(moved))
    rig.source["max_nonroot_translation_m"] = float(moved[worst_i])
    rig.source["max_nonroot_translation_bone"] = rig.names[worst_i]

    root_t = local_t[:, root_bi, :] - rig.local_t[root_bi][None, :]

    clip = Clip(clip_id or ("gltf-anim-%d" % ai), rig, rate, local_q, root_t,
                root_bone=rig.names[root_bi],
                source={"path": path, "animation_index": ai,
                        "animation_name": anim.get("name"),
                        "key_count": nkeys, "t0_s": t0, "t1_s": t1,
                        "channels": channels_used},
                bone_t=local_t)
    return rig, clip
