"""writers.py -- emit `core.skeleton` and `core.anim.clip` nodes.

The MessagePack encoder is IMPORTED from `spec/examples/make-examples.py`
rather than written again. That file is the executable statement of the
envelope rules, and Stage 2 proved werk-core's Rust writer byte-identical to
its output; a second Python encoder here would be a second thing that can drift
from the spec, which is the exact failure S-29 is about.

`read_wkac` is written from `spec/layouts/animclip.layout.txt`, from the
DECLARED offsets and sizes -- it never reverses the writer's arithmetic. That
is the only way a round-trip measurement means anything: a reader that computed
its offsets the way the writer did would agree with a broken writer.
"""

import importlib.util
import json
import os
import struct

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)


def _load_spec_examples():
    p = os.path.join(_ROOT, "spec", "examples", "make-examples.py")
    spec = importlib.util.spec_from_file_location("werk_spec_examples", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_EX = _load_spec_examples()
mp_encode = _EX.mp_encode
mp_decode = _EX.mp_decode
align16 = _EX.align16


# --- core.anim.clip ---------------------------------------------------------

def build_wkac(clip, skeleton_id, clip_id=None, name=None, loop=False,
               events=None, flags=0, extra_header=None):
    """Serialise a Clip to a WKAC envelope. Returns (bytes, header_dict).

    Bone track order is the rig's own bone order minus the root bone, and the
    header carries the names, so the clip is an island (D-AC-2).
    """
    rig = clip.rig
    root_bone = clip.root_bone
    if root_bone not in rig.index:
        raise ValueError("root_bone %r is not a bone of rig %r" % (root_bone, rig.rig_id))
    bones = [b for b in rig.names if b != root_bone]
    bi = [rig.index[b] for b in bones]
    F = clip.frames

    root_q = clip.local_q[:, rig.index[root_bone], :]
    root = np.empty((F, 7), dtype=np.float32)
    root[:, 0:3] = clip.root_t.astype(np.float32)
    root[:, 3:7] = root_q.astype(np.float32)
    root_blob = root.tobytes(order="C")

    rots = np.ascontiguousarray(
        np.transpose(clip.local_q[:, bi, :], (1, 0, 2))).astype(np.float32)
    rot_blob = rots.tobytes(order="C")

    if flags & 0x1 and np.abs(clip.root_t).max() > 0.0:
        raise ValueError("IN_PLACE is set but the root track translates by %g"
                         % float(np.abs(clip.root_t).max()))

    def make_header(origin, off0, off1):
        h = dict(extra_header or {})
        h.update({
            "kind": "core.anim.clip",
            "endianness": "le",
            "payload_origin": origin,
            "payload_size": align16(off1 + len(rot_blob)) - origin,
            "clip_id": clip_id or clip.clip_id,
            "skeleton_id": skeleton_id,
            "bone_count": len(bones),
            "frame_count": F,
            "rate_hz": float(clip.rate_hz),
            "duration_s": float(F / clip.rate_hz),
            "flags": int(flags),
            "bones": bones,
            "root_bone": root_bone,
            "loop": bool(loop),
            "sections": [
                {"name": "root-track", "offset": off0, "size": len(root_blob),
                 "dtype": "f32", "shape": [F, 7], "stride": 28},
                {"name": "bone-rotations", "offset": off1, "size": len(rot_blob),
                 "dtype": "f32", "shape": [len(bones), F, 4], "stride": 16},
            ],
        })
        if events:
            h["events"] = list(events)
        return mp_encode(h), h

    header_len = len(make_header(0, 0, 0)[0])
    for _ in range(8):
        origin = align16(12 + header_len)
        off0 = origin
        off1 = align16(off0 + len(root_blob))
        blob, hdict = make_header(origin, off0, off1)
        if len(blob) == header_len:
            break
        header_len = len(blob)
    else:
        raise RuntimeError("WKAC header length did not converge")
    if align16(12 + len(blob)) != origin:
        raise RuntimeError("payload_origin disagrees with its own definition")

    out = bytearray()
    out += b"WKAC"
    out += struct.pack("<I", 1)
    out += struct.pack("<I", len(blob))
    out += blob
    out += b"\x00" * (origin - len(out))
    out += root_blob
    out += b"\x00" * (off1 - len(out))
    out += rot_blob
    out += b"\x00" * (align16(len(out)) - len(out))
    data = bytes(out)
    if len(data) != hdict["payload_origin"] + hdict["payload_size"]:
        raise RuntimeError("file_size != payload_origin + payload_size")
    return data, hdict


#: The animclip grammar revisions this reader implements. Revision 2 added an
#: optional "bone-translations" section (S6-4, ruled 2026-08-08); this reader
#: does not consume it, and says so by SKIPPING AND REPORTING rather than by
#: refusing the clip -- see ENVELOPE.layout.txt section 5a.
WKAC_SECTIONS_IMPLEMENTED = ("root-track", "bone-rotations")


def read_wkac(data, reports=None):
    """Decode a WKAC envelope straight from its DECLARED header.

    Written against spec/layouts/animclip.layout.txt and
    spec/layouts/ENVELOPE.layout.txt. Every offset and size comes out of the
    header; nothing is recomputed from a shape times a guessed stride, and the
    two independent statements of payload_origin are compared, which is what
    ENVELOPE.layout.txt section 1 asks a reader to do.

    `reports` is an optional list that receives (code, detail) tuples. The two
    codes this reader can emit are ENVELOPE.layout.txt section 5a's:
    "layout-version-newer" and "section-skipped-unknown". Both are INFO. A
    version integer higher than this reader implements is never grounds to
    refuse a payload it can substantially read -- refusing on the version alone
    is exactly law 3's failure mode -- and an unrecognised section is skipped
    and reported, never guessed at and never treated as damage.
    """
    if reports is None:
        reports = []
    if len(data) < 12:
        raise ValueError("shorter than the 12-byte fixed prefix")
    if data[:4] != b"WKAC":
        raise ValueError("magic is %r, not WKAC" % data[:4])
    version, header_len = struct.unpack_from("<II", data, 4)
    if version < 1:
        raise ValueError("envelope version %d is not a legal version" % version)
    if version > 2:
        reports.append(("layout-version-newer",
                        "clip declares animclip grammar revision %d; this "
                        "reader implements 2 and reads what it recognises"
                        % version))
    h = mp_decode(data[12:12 + header_len])
    if h.get("endianness") != "le":
        raise ValueError("endianness %r" % h.get("endianness"))
    if h.get("kind") != "core.anim.clip":
        raise ValueError("kind %r does not match magic WKAC" % h.get("kind"))
    computed = align16(12 + header_len)
    if int(h["payload_origin"]) != computed:
        raise ValueError("declared payload_origin %d, computed %d"
                         % (h["payload_origin"], computed))
    if len(data) != int(h["payload_origin"]) + int(h["payload_size"]):
        raise ValueError("file is %d bytes, header promises %d"
                         % (len(data), h["payload_origin"] + h["payload_size"]))

    sec = {s["name"]: s for s in h["sections"]}
    for name in sec:
        if name not in WKAC_SECTIONS_IMPLEMENTED:
            reports.append(("section-skipped-unknown",
                            "section %r is not one this reader implements; "
                            "skipped, and the clip is read without it" % name))
    for s in h["sections"]:
        end = int(s["offset"]) + int(s["size"])
        if end > len(data):
            raise ValueError("section %r runs past the end of the file" % s["name"])
        esz = {"f32": 4, "f64": 8, "u32": 4, "i32": 4, "u16": 2, "u8": 1}.get(s["dtype"])
        if esz is None:
            esz = int(s["stride"])
        shape = [int(x) for x in s["shape"]]
        if int(s["stride"]) == esz:
            want = int(s["stride"]) * int(np.prod(shape))
        else:
            if int(s["stride"]) < esz * shape[-1]:
                raise ValueError("section %r: stride %d < esz*shape[-1] %d"
                                 % (s["name"], s["stride"], esz * shape[-1]))
            want = int(s["stride"]) * int(np.prod(shape[:-1]))
        if want != int(s["size"]):
            raise ValueError("section %r: declared size %d, consistency rule says %d"
                             % (s["name"], s["size"], want))

    F = int(h["frame_count"])
    B = int(h["bone_count"])
    s0 = sec["root-track"]
    root = np.frombuffer(data, dtype="<f4", count=F * 7,
                         offset=int(s0["offset"])).reshape(F, 7).astype(np.float64)
    s1 = sec["bone-rotations"]
    rot = np.frombuffer(data, dtype="<f4", count=B * F * 4,
                        offset=int(s1["offset"])).reshape(B, F, 4).astype(np.float64)
    if abs(float(h["duration_s"]) - F / float(h["rate_hz"])) > 1e-6:
        raise ValueError("duration_s %r != frame_count/rate_hz %r"
                         % (h["duration_s"], F / float(h["rate_hz"])))
    return h, root, rot


def clip_from_wkac(data, rig):
    """Rebuild a Clip on `rig` from WKAC bytes, binding tracks BY NAME."""
    from .skeleton import Clip
    h, root, rot = read_wkac(data)
    bones = list(h["bones"])
    F = int(h["frame_count"])
    local_q = np.tile(rig.local_q[None, :, :], (F, 1, 1))
    for k, nm in enumerate(bones):
        if nm not in rig.index:
            continue                       # law 3: an unbindable track is dropped
        local_q[:, rig.index[nm], :] = rot[k]
    rb = h["root_bone"]
    if rb in rig.index:
        local_q[:, rig.index[rb], :] = root[:, 3:7]
    return Clip(h["clip_id"], rig, float(h["rate_hz"]), local_q, root[:, 0:3],
                root_bone=rb, source={"from": "core.anim.clip", "bones": len(bones)})


def clip_json(clip, skeleton_id, clip_id, name, binary_path, category=None,
              tags=None, loop=False, flags=0, events=None):
    """The `core.anim.clip` JSON payload beside the binary."""
    rig = clip.rig
    bones = [b for b in rig.names if b != clip.root_bone]
    F = clip.frames
    Q, P = clip.fk_all()
    root_i = rig.index[clip.root_bone]
    disp = P[:, root_i, :]
    dist = float(np.linalg.norm(disp[-1] - disp[0]))
    doc = {
        "schema_version": 1,
        "clip_id": clip_id,
        "name": name,
        "skeleton_id": skeleton_id,
        "bone_count": len(bones),
        "frame_count": F,
        "rate_hz": float(clip.rate_hz),
        "duration_s": float(F / clip.rate_hz),
        "flags": {"in_place": bool(flags & 0x1), "additive": bool(flags & 0x2),
                  "root_yaw_only": bool(flags & 0x4)},
        "binary": {"path": binary_path, "magic": "WKAC", "envelope_version": 1},
        "root_bone": clip.root_bone,
        "bones": bones,
    }
    if category:
        doc["category"] = category
    if tags:
        doc["tags"] = list(tags)
    if dist > 1e-6:
        d = disp[-1] - disp[0]
        doc["locomotion"] = {
            "distance_m": dist,
            "average_speed_m_s": dist / (F / clip.rate_hz),
            "direction": [float(x) for x in (d / np.linalg.norm(d))],
        }
    if loop:
        from .quat import qangle
        seam = float(qangle(clip.local_q[0], clip.local_q[-1]).max())
        doc["loop"] = {"loops": True, "seam_error_rad": seam}
    if events:
        doc["events"] = list(events)
    return doc


# --- core.skeleton ----------------------------------------------------------

def skeleton_json(rig, skeleton_id=None, name=None, status="draft", note=None,
                  reference_height_m=None, pose_name=None, retarget=None,
                  calibration_pose=None, epistemic="authored"):
    """Emit a `core.skeleton` payload for any Rig.

    Both the local and the model-space rest values are written, as Stage 1
    decision 8 requires, and the model ones are COMPUTED here from the local
    ones rather than copied from wherever the rig came from -- so the
    redundancy is a real check for a reader instead of two copies of one
    import bug.
    """
    Q, P = rig.rest_fk()
    child_of = {}
    for i in range(rig.n):
        p = int(rig.parent[i])
        if p >= 0:
            child_of.setdefault(p, []).append(i)

    bones = []
    for i, nm in enumerate(rig.names):
        kids = child_of.get(i, [])
        if kids:
            length = float(np.mean([np.linalg.norm(P[k] - P[i]) for k in kids]))
        else:
            length = 0.0
        along = np.array([0.0, 1.0, 0.0])
        back = np.array([0.0, 0.0, 1.0])
        from .quat import qrot
        a = qrot(Q[i], along)
        b = qrot(Q[i], back)
        e = {
            "bone_id": nm,
            "parent": None if int(rig.parent[i]) < 0 else rig.names[int(rig.parent[i])],
            "rest_rotation": [float(x) for x in rig.local_q[i]],
            "rest_translation": [float(x) for x in rig.local_t[i]],
            "length_m": length,
            "model_rest_rotation": [float(x) for x in Q[i]],
            "model_rest_head_m": [float(x) for x in P[i]],
            "model_rest_tail_m": [float(x) for x in (P[i] + length * a)],
            "axis_along": [float(x) for x in a],
            "axis_back": [float(x) for x in b],
            "leaf": not kids,
        }
        bones.append(e)

    doc = {
        "schema_version": 1,
        "skeleton_id": skeleton_id or rig.rig_id,
        "name": name or rig.rig_id,
        "status": status,
        "epistemic": epistemic,
        "conventions": {
            "up_axis": "y", "forward_axis": "-z", "right_axis": "+x",
            "handedness": "right", "quat_order": "wxyz", "units_per_meter": 1.0,
            "bone_axis_along": "+y", "bone_axis_back": "+z",
            "composition": "M_bone = M_parent * T(rest_translation) * R(rest_rotation)",
        },
        "bones": bones,
    }
    if note:
        doc["note"] = note
    if reference_height_m:
        doc["reference_height_m"] = float(reference_height_m)
    if pose_name:
        doc["pose_name"] = pose_name
    if retarget:
        doc["retarget"] = retarget
    if calibration_pose:
        doc["calibration_pose"] = calibration_pose
    return doc


def write_json(path, doc):
    b = (json.dumps(doc, indent=1, sort_keys=False, ensure_ascii=False) + "\n").encode("utf-8")
    with open(path, "wb") as fh:
        fh.write(b)
    return b
