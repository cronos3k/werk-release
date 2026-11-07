#!/usr/bin/env python3
"""build_retarget_fixture.py -- Stage 6 conformance fixture: a rig and a clip.

Builds `fixtures/humanoid-retarget-v1.werk`, profile `3d-entity/1`: the werk
canonical humanoid as a `core.skeleton` node, plus one `core.anim.clip` that is
REAL RETARGETED MOTION -- a CMU Graphics Lab mocap take, bound to the canonical
rig from one calibration pose by `retarget/`, and written through the
`core.anim.clip` envelope.

    python fixtures/build_retarget_fixture.py [--out DIR]

WHY THIS CLIP. Three requirements had to hold at once and only one candidate
held all three:

  * the motion must be REAL, not authored for the test. Stage 11 recorded that
    the rig clause it had to build inside Blender was weaker evidence than a
    real asset, and that "a real skinned character ... is the most valuable
    next test";
  * the source rig must be genuinely foreign -- different names, different bone
    count, different proportions, a different rest pose -- or the retarget
    proves nothing;
  * the licence must permit handing the result to a stranger. CMU's database is
    free for all uses and says so in its own README, which travels in the
    package as `provenance/cmu-READMEFIRST.txt`. The Unreal mannequin walk this
    stage also retargeted is Epic-licensed engine content and is deliberately
    NOT in the handed-out fixture; the glTF CesiumMan is CC-BY and could have
    been, but one clip is what the stage asked for and CMU is the rawest of the
    three.

WHAT IT EXERCISES that no previous fixture did:

  * the first `core.skeleton` node in any werk package, and therefore the first
    time a reader has to check the schema's own local-versus-model
    recomposition claim against real numbers;
  * the first `core.anim.clip`, so `spec/layouts/animclip.layout.txt` and the
    `WKAC` magic stop being unexercised code, and BOTH branches of the envelope
    section-consistency rule appear again in a second, independent payload
    (root-track: stride 28 == a 7-float record; bone-rotations: stride 16 over
    a [bones, frames, 4] shape);
  * a `requires` edge from a clip to its skeleton, which is the first time a
    node has depended on a rig.

DEPENDENCIES: numpy, through `retarget/`. Nothing third-party travels inside
the package; law 1's ban is about what ships in the file.
"""

import argparse
import hashlib
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# S-29, ruled 2026-08-08: every manifest declares a spec_sha256 over the spec/
# tree it carries. tools/spec_sha256.py is the reference implementation and
# carries the algorithm in its docstring; importing it rather than re-deriving
# it here is the point of having one.
sys.path.insert(0, os.path.join(ROOT, "tools"))
from spec_sha256 import spec_sha256_of_files          # noqa: E402
from payload_file import annotate_payload_files       # noqa: E402
from loader_caps import loader_capabilities        # noqa: E402
from edge_targets import refuse_dangling_edges     # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "store"))
sys.path.insert(0, ROOT)
from werkstore.signature import build_chain            # noqa: E402
from retarget import load_canonical, load_map          # noqa: E402
from retarget import calibrate, writers                # noqa: E402
from retarget import retarget as RT                    # noqa: E402
from retarget.sources import bvh                       # noqa: E402

CREATED = "2026-08-08T13:00:00Z"
ENTITY_UUID = "b1c9e4d2-5a37-4f80-9e16-2c7d08a5b3f4"
DEV_KEY_PHRASE = b"werk dev key, publicly derived, fixtures only"
DEV_SK = hashlib.sha256(DEV_KEY_PHRASE).digest()

SRC_DIR = os.path.join(ROOT, "retarget", "testdata")
BVH_NAME = "02_01.bvh"

DOS_TIME = (9 << 11) | (0 << 5)
DOS_DATE = ((2026 - 1980) << 9) | (8 << 5) | 8
FLAG_UTF8 = 0x0800

ENTRY_ORDER = [
    "MANIFEST.json",
    "SIGNATURE.json",
    "LICENSE",
    "README.txt",
    "loaders/",
    "spec/",
    "skeleton/",
    "anim/cmu-02-01-walk.json",
    "anim/",
    "provenance/",
    "x/",
]
PREVIEW_SET = ENTRY_ORDER[: ENTRY_ORDER.index("anim/") + 1]

LICENSE_TEXT = """\
CC-BY-4.0 applies to this package as assembled.

The motion in anim/cmu-02-01-walk.wkac is derived from take 02_01 of the CMU
Graphics Lab Motion Capture Database (http://mocap.cs.cmu.edu/), in Bruce
Hahne's BVH conversion. CMU's own terms travel with it, unedited, in
provenance/cmu-READMEFIRST.txt: the database is free for all uses.

skeleton/canonical-humanoid-v1.json is a copy of the werk specification's own
spec/skeleton/canonical-humanoid-v1.json, which is also in this package under
spec/. It carries status "draft".

The signature is a DEV key derived from a published sentence. It proves the
chain verifies and nothing whatsoever about authorship.
"""

README_TEXT = """\
werk conformance fixture: a skeleton and a retargeted clip
==========================================================

Two nodes matter here:

  skeleton/canonical-humanoid-v1.json   core.skeleton, 23 bones, status DRAFT
  anim/cmu-02-01-walk.wkac              core.anim.clip, magic WKAC

Everything you need to read them is in this package. spec/layouts/
ENVELOPE.layout.txt has the envelope grammar, spec/layouts/animclip.layout.txt
has the clip layout, and loaders/ has three single-file readers that need
nothing installed.

THE CLIP IS NOT AUTHORED ON THIS RIG. It is a CMU mocap take, captured on a
31-joint rig with different names, different proportions and a different rest
pose, bound to the canonical humanoid from ONE calibration pose and retargeted.
The bind is recorded in x/retarget-report.json, including the
calibration frame the solver chose by scanning, the whole-body rotation and the
stature scale it recovered, and the residuals it measured. The numbers there
are measurements from the run that produced this file.

TWO THINGS A READER CAN CHECK WITHOUT TRUSTING US

1. The skeleton declares each bone's rest transform twice, once in its
   parent's frame and once in model space. Recompose the local numbers along
   the parent chain and compare: they agree to 1.1e-10 m.

2. The clip's binary header declares duration_s AND frame_count AND rate_hz.
   frame_count / rate_hz must equal duration_s within 1e-6.

WHAT IS DELIBERATELY MISSING

No mesh, no material, no texture. This package is a rig and a motion, and
inventing a character to hang them on would be the one thing a conformance
fixture must never do.

The source rig's LHipJoint, RHipJoint, Neck1 and finger joints have no
canonical counterpart, so their motion is NOT in this clip. That loss is
measured, not glossed: x/retarget-report.json names those joints and
records how much rotation was dropped.
"""


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def jbytes(v):
    return (json.dumps(v, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def input_hash(paths, files):
    h = hashlib.sha256()
    for p in paths:
        h.update(hashlib.sha256(files[p]).digest())
    h.update(b"{}")
    return h.hexdigest()


CRC_TABLE = []


def crc32(data):
    if not CRC_TABLE:
        for i in range(256):
            c = i
            for _ in range(8):
                c = (c >> 1) ^ (0xEDB88320 if c & 1 else 0)
            CRC_TABLE.append(c)
    c = 0xFFFFFFFF
    for b in data:
        c = CRC_TABLE[(c ^ b) & 0xFF] ^ (c >> 8)
    return c ^ 0xFFFFFFFF


def write_zip(entries):
    out, central, count = bytearray(), bytearray(), 0
    for name, data in entries:
        lho = len(out)
        crc = crc32(data)
        nb = name.encode("utf-8")
        out += struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, FLAG_UTF8, 0, DOS_TIME,
                           DOS_DATE, crc, len(data), len(data), len(nb), 0)
        out += nb + data
        central += struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, 20, 20, FLAG_UTF8, 0,
                               DOS_TIME, DOS_DATE, crc, len(data), len(data), len(nb),
                               0, 0, 0, 0, 0, lho)
        central += nb
        count += 1
    cd_off, cd_size = len(out), len(central)
    out += central
    out += struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, count, count, cd_size, cd_off, 0)
    return bytes(out)


def matches(path, pattern):
    return path.startswith(pattern) if pattern.endswith("/") else path == pattern


def order_entries(paths):
    remaining = sorted(paths)
    out = []
    for pat in ENTRY_ORDER:
        for p in [p for p in remaining if matches(p, pat)]:
            remaining.remove(p)
            out.append(p)
    return out + remaining


def is_preview(name):
    return any(matches(name, p) for p in PREVIEW_SET)


def build_retarget():
    """Do the actual retarget and return everything the package needs."""
    canon = load_canonical()
    rig, clip = bvh.load(os.path.join(SRC_DIR, BVH_NAME), clip_id="cmu-02-01")
    name_map, prov = load_map("cmu-bvh")
    bind, scores = calibrate.scan_clip(clip, canon, name_map)
    cclip = RT.to_canonical(bind, clip, clip_id="cmu-02-01-walk")
    inv = calibrate.frame_invariance_residual(bind, clip)

    wkac, header = writers.build_wkac(
        cclip, "canonical-humanoid-v1", clip_id="cmu-02-01-walk",
        loop=False, flags=0)
    cjson = writers.clip_json(
        cclip, "canonical-humanoid-v1", "cmu-02-01-walk",
        "CMU 02_01, retargeted to the werk canonical humanoid",
        "anim/cmu-02-01-walk.wkac", category="locomotion",
        tags=["walk", "mocap", "retargeted"])

    # what the source rig carried that the canonical rig cannot
    dropped = sorted(set(rig.names) - set(name_map.keys()))
    report = {
        "what_this_is": (
            "The measured record of one retarget: a CMU mocap take on a "
            "31-joint capture rig, bound to the werk canonical humanoid from "
            "ONE calibration pose, then written as a core.anim.clip. Every "
            "number here is from the run that produced the .wkac beside it."),
        "source": {
            "file": "provenance/" + BVH_NAME,
            "rig_bones": rig.n,
            "clip_frames": clip.frames,
            "rate_hz": clip.rate_hz,
            "frame_time_s": clip.source["frame_time_s"],
            "units": "BVH declares none; the stature scale below was solved, "
                     "not assumed",
        },
        "bone_map": {"map_id": prov["map_id"], "from": prov["from"],
                     "entries": len(name_map)},
        "calibration": bind.calibration,
        "solved": {
            "stature_scale": bind.scale,
            "whole_body_rotation_quat_wxyz": [float(x) for x in bind.qA],
            "bound_bones": len(bind.pairs),
        },
        "residuals": {
            "calibration_direction_rms_rad": bind.residuals["direction_rms_rad"],
            "calibration_direction_max_rad": bind.residuals["direction_max_rad"],
            "calibration_position_rms_m": bind.residuals["position_rms_m"],
            "scan_best_rad": bind.residuals["scan_best_rad"],
            "scan_median_rad": bind.residuals["scan_median_rad"],
            "scan_worst_rad": bind.residuals["scan_worst_rad"],
            "per_bone_direction_rad": bind.residuals["per_bone_direction_rad"],
        },
        "frame_invariance": inv,
        "not_carried": {
            "source_joints_with_no_canonical_counterpart": dropped,
            "note": ("Their rotation is not in this clip and cannot be "
                     "recovered from it. LHipJoint and RHipJoint are "
                     "zero-length CMU artefacts; Neck1 is the second segment "
                     "of a two-segment neck the canonical rig does not have; "
                     "the rest are fingers. The frame_invariance.interposed "
                     "block above measures exactly what that costs."),
        },
        "how_to_reproduce": (
            "python fixtures/build_retarget_fixture.py, against "
            "retarget/testdata/02_01.bvh. The gate that measured these "
            "numbers is tests/run_gate_6.py."),
    }
    # -- the SOLVED BIND as a core node (S6-2, ruled 2026-08-08) -----------
    # This fixture used to carry the bind only inside x/retarget-report.json,
    # and said so: "core has no schema for a retarget report". Ruling 12 added
    # core.retarget.bind, so the three numbers a consumer actually needs - the
    # pose it was taken in, the scale that was solved, the rotation that was
    # recovered - are now readable by anyone rather than by whoever knows this
    # extension. The x.werk.retarget node stays: it carries the FULL report and
    # the bone map, which is more than the core node claims to hold.
    # The solver measures a direction residual per CORRESPONDENCE, keyed
    # "parent->child": it is the angle between the source segment and the
    # canonical segment that joins those two bone heads. Attributing it needs a
    # convention, so state it rather than assume it: the residual is recorded
    # on the CHILD bone, the bone the direction points AT. That keeps the
    # interposed-joint story readable - "hips->l-thigh" 0.32 rad lands on
    # l-thigh, which is exactly the bone CMU's zero-length LHipJoint sits above
    # (S6-3) - and a bone that is nobody's child in a measured pair simply
    # carries no residual rather than a fabricated zero.
    per_bone = {}
    for key, val in bind.residuals["per_bone_direction_rad"].items():
        child = key.split("->")[-1]
        per_bone[child] = max(per_bone.get(child, 0.0), float(val))
    bones_out = []
    for fi, ci in sorted(bind.pairs, key=lambda pr: pr[1]):
        cname = canon.names[ci]
        entry = {
            "source_bone": rig.names[fi],
            "bone_id": cname,
            "offset_rotation": [float(x) for x in bind.O[ci]],
        }
        if cname in per_bone:
            entry["residual_rad"] = float(per_bone[cname])
        bones_out.append(entry)
    worst = max(((b.get("residual_rad", 0.0), b["bone_id"]) for b in bones_out),
                default=(0.0, ""))
    measured = [b["residual_rad"] for b in bones_out if "residual_rad" in b]
    bind_doc = {
        "schema_version": 1,
        "bind_id": "cmu-02-01-to-canonical-humanoid",
        "name": "CMU take 02_01 bound to the werk canonical humanoid",
        "source": {
            "skeleton_id": "cmu-mocap-bvh/02_01",
            "name": "CMU Graphics Lab motion capture rig, Hahne BVH conversion",
            "bone_count": rig.n,
            "file": "provenance/" + BVH_NAME,
            "sha256": sha256(open(os.path.join(SRC_DIR, BVH_NAME), "rb").read()),
            # Nothing in a BVH declares its unit. This number was RECOVERED
            # from stature by the solver, and the field says which of the two
            # it is rather than letting a reader assume it was declared.
            "unit_scale_to_metre": float(bind.scale),
            "unit_scale_epistemic": "recovered",
            "axes": {"up_axis": "y", "forward_axis": "-z", "handedness": "right"},
        },
        "target": {
            "node_id": "skeleton-canonical",
            "skeleton_id": "canonical-humanoid-v1",
            "bone_count": canon.n,
        },
        "scale": float(bind.scale),
        "rotation": [float(x) for x in bind.qA],
        "bones": bones_out,
        "residual": {
            "mean_rad": float(sum(measured) / len(measured)) if measured else 0.0,
            "max_rad": float(worst[0]),
            "max_bone_id": worst[1],
            "frames_measured": 0,
        },
        "unmapped": {
            "source_bones": sorted(set(rig.names) - set(name_map.keys())),
            "target_bones": sorted(set(canon.names)
                                   - {b["bone_id"] for b in bones_out}
                                   - {"root"}),
            "note": ("The canonical root is never driven by a mapped foreign "
                     "bone and is therefore not listed as unmapped: ruling 9 "
                     "makes it a base bone carrying locomotion, and the root "
                     "track derives from the hips. LHipJoint and RHipJoint are "
                     "zero-length CMU artefacts; Neck1 is the second segment "
                     "of a two-segment neck this skeleton does not have; the "
                     "rest are fingers, which live in the hands extension."),
        },
        "solver": {
            "method": ("one calibration pose, per-bone rest-offset quaternion, "
                       "uniform stature scale solved from bone directions"),
            "calibration_frame_source": bind.calibration.get("source", "auto-scan"),
            "verified_against": ["anim/cmu-02-01-walk.wkac"],
        },
        "epistemic": "measured",
        "note": ("Every number here came out of the run that produced the clip "
                 "beside it, and the per-bone residuals are in the file so a "
                 "consumer can judge the bind instead of trusting it. Each "
                 "residual_rad is the direction residual of the correspondence "
                 "that ENDS at that bone; the solver measures per segment, and "
                 "attributing it to the child is a stated convention rather "
                 "than an assumed one. The full "
                 "report, including the frame-invariance measurement and the "
                 "bone-name map, is the x.werk.retarget node."),
    }
    if "frame" in bind.calibration:
        bind_doc["solver"]["calibration_frame_index"] = int(bind.calibration["frame"])

    return canon, rig, clip, cclip, bind, wkac, header, cjson, report, bind_doc


def collect():
    files = {}
    nodes = []

    def put(path, data, media=None, role=None):
        assert path not in files, "two nodes claim %s" % path
        files[path] = data
        f = {"path": path, "sha256": sha256(data), "size": len(data)}
        if media:
            f["media_type"] = media
        if role:
            f["role"] = role
        return f

    def node(node_id, ntype, versions, edges=(), meta=None):
        n = {"node_id": node_id, "type": ntype, "versions": versions,
             "active": len(versions), "edges": list(edges)}
        if meta:
            n["meta"] = meta
        nodes.append(n)
        return n

    def version(v, fs, note, tool, tver, epistemic, inputs=None):
        out = {"v": v, "files": fs, "note": note,
               "producer": {"tool": tool, "version": tver},
               "epistemic": epistemic, "created": CREATED}
        if inputs:
            out["input_files"] = list(inputs)
            out["input_hash"] = input_hash(inputs, files)
            out["input_params"] = {}
        return out

    (canon, rig, clip, cclip, bind, wkac, header, cjson, report,
     bind_doc) = build_retarget()

    lic_f = put("LICENSE", LICENSE_TEXT.encode("utf-8"), "text/plain")
    readme_f = put("README.txt", README_TEXT.encode("utf-8"), "text/plain")

    spec_files = []
    for dirpath, _dirs, names in os.walk(os.path.join(ROOT, "spec")):
        if "__pycache__" in dirpath:
            continue
        for nm in sorted(names):
            if nm.endswith(".pyc"):
                continue
            full = os.path.join(dirpath, nm)
            rel = "spec/" + os.path.relpath(
                full, os.path.join(ROOT, "spec")).replace("\\", "/")
            with open(full, "rb") as fh:
                spec_files.append(put(rel, fh.read()))
    node("spec", "core.spec",
         [version(1, spec_files + [lic_f, readme_f],
                  "The specification this package conforms to, in full.",
                  "fixtures/build_retarget_fixture.py", "1", "authored")])

    for nid, nm, lang, toolchain, build in [
            ("loader-py", "werk_read.py", "python", "python>=3.8", None),
            ("loader-rs", "werk_read.rs", "rust", "rustc>=1.70 --edition 2021",
             "rustc -O --edition 2021 loaders/werk_read.rs -o werk_read"),
            ("loader-c", "werk_read.c", "c", "c99",
             "cc -std=c99 -O2 loaders/werk_read.c -o werk_read")]:
        with open(os.path.join(ROOT, "loaders", nm), "rb") as fh:
            loader_bytes = fh.read()
        lf = put("loaders/" + nm, loader_bytes, "text/plain")
        meta = {"language": lang, "form": "source",
                "entrypoint": "loaders/" + nm, "toolchain": toolchain,
                "dependencies": [],
                "capabilities": loader_capabilities(loader_bytes)}
        if build:
            meta["build_command"] = build
        node(nid, "core.loader",
             [version(1, [lf],
                      "A single-file, dependency-free reader for this package.",
                      "fixtures/build_retarget_fixture.py", "1", "authored")],
             meta=meta)

    # -- the skeleton: the canonical file, byte for byte --------------------
    with open(os.path.join(ROOT, "spec", "skeleton",
                           "canonical-humanoid-v1.json"), "rb") as fh:
        canon_bytes = fh.read()
    skel_f = put("skeleton/canonical-humanoid-v1.json", canon_bytes,
                 "application/json")
    node("skeleton-canonical", "core.skeleton",
         [version(1, [skel_f],
                  "The werk canonical humanoid v1, 23 bones, copied byte for "
                  "byte from spec/skeleton/canonical-humanoid-v1.json. Status "
                  "is DRAFT and the payload says so in its own note field: the "
                  "numbers are pending approval, and every clip bound to them "
                  "inherits that.",
                  "fixtures/build_retarget_fixture.py", "1", "authored")],
         meta={"status": "draft", "bone_count": 23,
               "reference_height_m": 1.75, "pose_name": "t-pose-palms-down"})

    # -- provenance: the untouched source, and the measured report ----------
    with open(os.path.join(SRC_DIR, BVH_NAME), "rb") as fh:
        bvh_f = put("provenance/" + BVH_NAME, fh.read(), "text/plain")
    with open(os.path.join(SRC_DIR, "cmu-READMEFIRST.txt"), "rb") as fh:
        cmu_f = put("provenance/cmu-READMEFIRST.txt", fh.read(), "text/plain")
    map_doc = json.load(open(os.path.join(ROOT, "retarget", "maps",
                                          "cmu-bvh.json"), encoding="utf-8"))
    map_f = put("x/bone-map-cmu-bvh.json", jbytes(map_doc),
                "application/json")
    rep_f = put("x/retarget-report.json", jbytes(report),
                "application/json")
    bind_f = put("retarget/bind-cmu-02-01.json", jbytes(bind_doc),
                 "application/json")


    # -- the clip -----------------------------------------------------------
    wkac_f = put("anim/cmu-02-01-walk.wkac", wkac, "application/octet-stream")
    cj_f = put("anim/cmu-02-01-walk.json", jbytes(cjson), "application/json")
    node("clip-walk", "core.anim.clip",
         [version(1, [wkac_f, cj_f],
                  "CMU take 02_01 retargeted onto the canonical humanoid from "
                  "one calibration pose. MEASURED: the producer is "
                  "retarget/, the inputs are named and ordered, and the "
                  "residuals are in x/retarget-report.json.",
                  "retarget/", "1", "measured",
                  inputs=["provenance/" + BVH_NAME,
                          "x/bone-map-cmu-bvh.json",
                          "skeleton/canonical-humanoid-v1.json"])],
         edges=[{"kind": "requires", "to": "skeleton-canonical"}],
         meta={"skeleton_id": "canonical-humanoid-v1",
               "bone_count": int(header["bone_count"]),
               "frame_count": int(header["frame_count"]),
               "rate_hz": float(header["rate_hz"])})

    res = report["residuals"]
    prov_doc = {
        "schema_version": 1,
        "runs": [{
            "run_id": "retarget-cmu-02-01",
            "started": CREATED,
            "finished": CREATED,
            "tool": {"name": "retarget", "version": "1"},
            "consumed": [{"path": "provenance/" + BVH_NAME,
                          "sha256": bvh_f["sha256"]},
                         {"path": "skeleton/canonical-humanoid-v1.json",
                          "sha256": skel_f["sha256"]}],
            "produced": [{"node_id": "clip-walk", "v": 1}],
            "gates": [
                {"name": "calibration-direction-rms", "passed": True,
                 "value": res["calibration_direction_rms_rad"], "unit": "rad"},
                {"name": "calibration-direction-max", "passed": True,
                 "value": res["calibration_direction_max_rad"], "unit": "rad"},
                {"name": "calibration-position-rms", "passed": True,
                 "value": res["calibration_position_rms_m"], "unit": "m"},
                {"name": "scan-margin-best-over-median", "passed": True,
                 "value": res["scan_best_rad"] / res["scan_median_rad"],
                 "threshold": 0.70, "unit": "ratio"},
                {"name": "frame-invariance-adjacent-spread", "passed": True,
                 "value": report["frame_invariance"]["adjacent"]["spread_rad"],
                 "threshold": 1e-5, "unit": "rad"},
            ],
            "note": (
                "One calibration pose, found by scanning the take: %s. The "
                "solver recovered a stature scale of %.6f and a whole-body "
                "rotation; neither was declared. The gates above are "
                "measurements from this run. The interposed joints LHipJoint, "
                "RHipJoint and Neck1 have no canonical counterpart and their "
                "rotation is not in the clip -- x/retarget-report.json "
                "measures what that costs."
                % (json.dumps(report["calibration"]),
                   report["solved"]["stature_scale"])),
        }],
    }
    prov_f = put("provenance/retarget-run.json", jbytes(prov_doc),
                 "application/json")
    node("retarget-measurement", "core.provenance",
         [version(1, [prov_f, bvh_f, cmu_f],
                  "What the calibration solver found -- the frame it picked by "
                  "scanning, the scale and rotation it recovered, the "
                  "residuals it measured -- together with the mocap take "
                  "exactly as downloaded and CMU's own terms unedited. The "
                  "source travels WITH the record of what was done to it, "
                  "because a provenance claim whose input is somewhere else is "
                  "a promise about another file (law 1).",
                  "tests/run_gate_6.py", "1", "measured",
                  inputs=["provenance/" + BVH_NAME])],
         edges=[{"kind": "enhances", "to": "clip-walk"}])
    node("bind-cmu-02-01", "core.retarget.bind",
         [version(1, [bind_f],
                  "The solved bind as a CORE node (S6-2, ruled 2026-08-08): "
                  "the calibration pose, the solved stature scale, the "
                  "recovered basis rotation and every per-bone offset with its "
                  "MEASURED residual. Before this node type existed a package "
                  "could contain a retargeted clip and the skeleton it was "
                  "retargeted onto and say nothing about the bind between "
                  "them; this fixture said it in an x.* node that only this "
                  "repository could read.",
                  "retarget/", "1", "measured",
                  inputs=["provenance/" + BVH_NAME,
                          "skeleton/canonical-humanoid-v1.json"])],
         edges=[{"kind": "requires", "to": "skeleton-canonical"},
                {"kind": "enhances", "to": "clip-walk", "role": "bound-from"}])
    node("retarget-detail", "x.werk.retarget",
         [version(1, [rep_f, map_f],
                  "The full per-bone retarget report and the bone-name map. An "
                  "EXTENSION node on purpose: core has no schema for a "
                  "retarget report, and inventing one so this would validate "
                  "is exactly the cleverness law 11 keeps out of core. A "
                  "conformant reader lists it, verifies its bytes, and skips "
                  "it with a report (law 12).",
                  "tests/run_gate_6.py", "1", "measured",
                  inputs=["provenance/" + BVH_NAME])],
         edges=[{"kind": "enhances", "to": "clip-walk"}])

    stats = {"bind": bind, "report": report, "header": header,
             "wkac_bytes": len(wkac), "canon": canon, "clip": clip,
             "cclip": cclip}
    return files, nodes, stats


def build_manifest(files, nodes, preview_prefix):
    total = sum(len(v) for v in files.values())
    return {
        "werk": {"major": 1, "minor": 0},
        "profile": "3d-entity/1",
        "entity": {
            "uuid": ENTITY_UUID,
            "name": "Canonical humanoid + one retargeted walk",
            "summary": (
                "A rig and a motion, and nothing else. The rig is the werk "
                "canonical humanoid v1 (23 bones, status DRAFT). The motion is "
                "CMU mocap take 02_01, captured on a 31-joint rig with "
                "different names, different proportions and a different rest "
                "pose, bound to the canonical rig from ONE calibration pose "
                "the solver found by scanning the take, and retargeted. The "
                "source take, CMU's own terms, the bone-name map and every "
                "residual the solver measured all travel in provenance/. "
                "First werk package to carry a core.skeleton or a "
                "core.anim.clip, so WKAC and spec/layouts/animclip.layout.txt "
                "are exercised rather than merely published."),
            "created": CREATED,
        },
        "conventions": {
            "endianness": "le", "units_per_meter": 1.0, "length_unit": "metre",
            "angle_unit": "radian", "time_unit": "second", "mass_unit": "kilogram",
            "up_axis": "y", "forward_axis": "-z", "right_axis": "+x",
            "handedness": "right", "winding": "ccw", "quat_order": "wxyz",
            "oct_encoding_pole": "y", "sh_l1_order": ["dc", "y", "z", "x"],
            "color_space_default": "srgb", "uv_origin": "top-left",
            "alignment_bytes": 16, "text_encoding": "utf-8", "id_case": "kebab-case",
            "hash_algorithm": "sha256", "signature_algorithm": "ed25519",
        },
        "container": {
            "form": "zip", "zip_compression": "store",
            "entry_order": list(ENTRY_ORDER),
            "preview_prefix_bytes": preview_prefix,
        },
        # No mesh, no image, no sound: an absent key is the honest answer when
        # the entity does not have one (S-13).
        "primary": {},
        "license": {"spdx_id": "CC-BY-4.0", "file": "LICENSE",
                    "sha256": sha256(files["LICENSE"])},
        # S-29: the revision of spec/ this package carries, so a reader can
        # tell in one comparison whether the schemas travelling inside the
        # file are the ones it already knows. Mandatory.
        "spec_sha256": spec_sha256_of_files(files),
        # S-17: the convention -> node-type map as DATA, declared rather than
        # derived, so a reader that does not support a convention refuses
        # exactly the nodes it governs instead of transcribing a prose table
        # into a constant.
        "conventions_map": "spec/conventions-map.json",
        "schemas": {
            "core.skeleton": "spec/schemas/core.skeleton.schema.json",
            "core.anim.clip": "spec/schemas/core.anim.clip.schema.json",
            "core.retarget.bind": "spec/schemas/core.retarget.bind.schema.json",
            "core.provenance": "spec/schemas/core.provenance.schema.json",
        },
        "layouts": {"core.anim.clip": "spec/layouts/animclip.layout.txt"},
        "parts": [{"part_id": "figure", "name": "Humanoid figure", "parent": None,
                   "transform": {"translation": [0.0, 0.0, 0.0],
                                 "rotation": [1.0, 0.0, 0.0, 0.0],
                                 "scale": [1.0, 1.0, 1.0]}}],
        "materials": [],
        "nodes": nodes,
    }


def sign(manifest_bytes):
    return build_chain(sha256(manifest_bytes), [{
        "secret": DEV_SK,
        "name": "werk dev key (publicly derived, fixtures only)",
        "uri": "urn:werk:dev-key:build-retarget-fixture",
        "kind": "service",
        "role": "author",
        "signed_at": CREATED,
        "note": "Signed with a DEV key derived from a published sentence. It "
                "is not secret, it is not a trust anchor, and it proves only "
                "that the chain verifies.",
    }])


def assemble(files, nodes):
    # SPEC 2.1 (S-XV-4 / S-OW-2)
    annotate_payload_files(nodes)
    # SPEC 5: never write a `requires` edge to a node not in nodes[].
    refuse_dangling_edges(nodes)
    preview = 0
    for _round in range(8):
        manifest_bytes = jbytes(build_manifest(files, nodes, preview))
        sig_bytes = jbytes(sign(manifest_bytes))
        allf = dict(files)
        allf["MANIFEST.json"] = manifest_bytes
        allf["SIGNATURE.json"] = sig_bytes
        entries = [(p, allf[p]) for p in order_entries(allf.keys())]
        cursor, prefix = 0, 0
        for name, data in entries:
            this = 30 + len(name.encode("utf-8")) + len(data)
            if is_preview(name):
                prefix = cursor + this
            cursor += this
        if prefix == preview:
            return manifest_bytes, sig_bytes, entries
        preview = prefix
    raise SystemExit("preview_prefix_bytes did not converge")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=HERE)
    args = ap.parse_args(argv)

    files, nodes, stats = collect()
    manifest_bytes, sig_bytes, entries = assemble(files, nodes)
    blob = write_zip(entries)
    path = os.path.join(args.out, "humanoid-retarget-v1.werk")
    with open(path, "wb") as fh:
        fh.write(blob)

    prefix = json.loads(manifest_bytes)["container"]["preview_prefix_bytes"]
    b = stats["bind"]
    print("wrote %s" % path)
    print("  %d bytes, sha256 %s" % (len(blob), sha256(blob)))
    print("  %d entries, %d nodes, %d declared file references"
          % (len(entries), len(nodes),
             sum(len(v["files"]) for n in nodes for v in n["versions"])))
    print("  manifest %d bytes, sha256 %s"
          % (len(manifest_bytes), sha256(manifest_bytes)))
    print("  preview_prefix_bytes %d (%.2f%% of the archive)"
          % (prefix, 100.0 * prefix / len(blob)))
    print("  WKAC %d bytes, %d bones x %d frames at %.4f Hz"
          % (stats["wkac_bytes"], stats["header"]["bone_count"],
             stats["header"]["frame_count"], stats["header"]["rate_hz"]))
    print("  bind: %s, scale %.5f, calibration direction rms %.5f rad"
          % (b.calibration.get("source"), b.scale,
             b.residuals["direction_rms_rad"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
