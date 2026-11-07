#!/usr/bin/env python3
"""run_gate_6.py -- ROADMAP Stage 6 gate: the one-calibration-pose retarget.

    python tests/run_gate_6.py [--rebuild-fixture] [--json OUT.json]

THE GATE, IN THE ROADMAP'S OWN WORDS: "three successful retargets with
residuals below declared tolerance". The three are real, foreign, freely
obtainable rigs and real motion on each:

  A  a rigged, animated glTF        Khronos CesiumMan, 19 joints, no naming
                                    convention, no clavicles, Z-up armature
  B  the Unreal Engine mannequin    UE 5.7's own SK_Mannequin, 68 bones,
                                    Z-up and LEFT handed, centimetres
  C  a raw mocap take               CMU 02_01, 31 joints, unit-less BVH

TOLERANCES ARE DECLARED IN THE NEXT BLOCK, BEFORE ANY MEASUREMENT CODE, which
is the whole point of putting them in a file rather than in a report. Each one
carries the reasoning that fixed it. Where a threshold came from a number the
format already states, it says so and quotes it; none is a round number chosen
because the results were nearby.

HONEST NOTE ON ORDER OF OPERATIONS. During development the calibration scan's
score landscape was surveyed on all three rigs before these thresholds were
written down -- that is how the frame-invariance clause below came to be split
into an adjacent and an interposed set, because the first version of the claim
was too strong and the measurement said so. The thresholds themselves are set
from the arguments given, not from the observed values, and where the two are
close the clause says how much margin there is.
"""

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import numpy as np                                        # noqa: E402

from retarget import load_canonical, load_map             # noqa: E402
from retarget import calibrate, writers                   # noqa: E402
from retarget import retarget as RT                       # noqa: E402
from retarget.quat import qangle, qinv, qmul              # noqa: E402
from retarget.sources import bvh, gltf, ue                # noqa: E402


# =====================================================================
# DECLARED TOLERANCES  -- fixed before measurement, with the argument
# =====================================================================

TOL = {
    # --- T1 -----------------------------------------------------------
    # The scan must find a DISTINGUISHED pose. If every candidate binds as
    # well as every other, the calibration pose is doing no work and "one
    # calibration pose is enough" is an empty sentence. Requiring the best
    # candidate to beat the MEDIAN candidate by 30 % is the weakest statement
    # that still says a minimum exists. It is a structural threshold: it does
    # not care what the absolute residual is, only that the landscape has a
    # shape.
    "scan_best_over_median": 0.70,

    # --- T2 -----------------------------------------------------------
    # A calibration pose chosen WRONGLY must visibly break the retarget, or
    # the pose is decoration. Binding on the scan's worst candidate instead of
    # its best must move the retargeted canonical pose by at least 0.30 rad
    # (17 degrees) somewhere. 17 degrees is roughly the angle at which a
    # limb's placement stops being a matter of taste and starts being a
    # different gesture; below that two riggers might disagree, above it they
    # would call it a bug.
    "wrong_pose_min_damage_rad": 0.30,

    # --- T3 -----------------------------------------------------------
    # The per-bone pose error of a retarget is FRAME-INVARIANT for every bone
    # pair that is parent-and-child in both rigs -- see the proof in
    # retarget/calibrate.py. In exact arithmetic the spread across frames is
    # zero. 1e-5 rad admits float64 accumulation over a chain of six
    # composed rotations and the sub-micrometre per-frame bone translation a
    # COLLADA export carries, while a genuine violation (an animated joint
    # interposed between two mapped bones) is four to five orders larger --
    # so the threshold cannot accidentally pass a broken bind.
    "frame_invariance_adjacent_rad": 1.0e-5,

    # --- T4 -----------------------------------------------------------
    # Round trip A -> canonical -> core.anim.clip on disk -> A. The clip
    # crosses the payload as f32 (animclip.layout.txt, section 1). An f32
    # quaternion component carries ~6e-8 of absolute error, so a chain of six
    # composed model-space rotations accumulates ~1e-6 rad. The threshold is
    # NOT invented here: animclip.layout.txt already declares that "two
    # conformant players MUST agree within 1e-4 radians on any interpolated
    # rotation", so 1e-4 is the format's own stated interoperability unit and
    # this gate adopts it rather than making up a smaller one.
    "roundtrip_rad": 1.0e-4,

    # --- T5 -----------------------------------------------------------
    # Cross-rig transit: A -> canonical -> file -> rig B -> canonical -> file.
    # Same argument, same number, one more file crossing.
    "transit_rad": 1.0e-4,

    # --- T6 -----------------------------------------------------------
    # A retarget moves rotations and NOTHING else. Any change in a canonical
    # bone length would mean the FK, the writer or the reader is wrong. In
    # exact arithmetic this is 0; 1e-9 m is one nanometre and is float noise
    # on a 1.75 m figure.
    "bone_length_drift_m": 1.0e-9,

    # --- T7 -----------------------------------------------------------
    # The retargeted canonical figure must be a plausible human, not merely
    # self-consistent algebra. Its hips must stay between 0.60 m and 1.30 m
    # above the floor plane the skeleton declares (canonical rest is 0.98 m;
    # the window admits a deep crouch and a full stride extension and
    # excludes a figure that is floating, sunk, or scaled wrong). This is the
    # one clause that no amount of internally consistent maths can fake,
    # because the scale it tests was SOLVED from the calibration pose and was
    # never told what a metre is.
    "hips_min_m": 0.60,
    "hips_max_m": 1.30,
}

SOURCES = [
    {
        "key": "cesium",
        "label": "glTF: Khronos CesiumMan",
        "path": "retarget/testdata/CesiumMan.glb",
        "sha256": "b7001eaeea8254bd44773bcd247e78696d94169388fbb2a1800fc69434e777d9",
        "origin": ("https://raw.githubusercontent.com/KhronosGroup/"
                   "glTF-Sample-Assets/main/Models/CesiumMan/glTF-Binary/"
                   "CesiumMan.glb"),
        "licence": "see retarget/testdata/CesiumMan-README.md (Khronos sample asset)",
        "map": "cesium-man",
    },
    {
        "key": "ue",
        "label": "UE 5.7 mannequin: SK_Mannequin + ThirdPersonWalk",
        # NOT in the repository, and that is a licence decision rather than an
        # oversight: this file is skeleton and animation data derived from Epic
        # engine content, which must not be redistributed. It is REGENERATED,
        # and the command is in `regenerate` below. A clone that has never run
        # it gets a SKIP naming the reason -- never a silent pass, and never a
        # failure blamed on the retargeter.
        "path": os.environ.get("WERK_S6_UE_EXPORT",
                               os.path.join(os.environ.get("WERK_LAB", "<WERK_LAB unset>"),
                                            "Stage6UE", "export", "ue-mannequin.json")),
        "sha256": None,          # produced on this box; see `origin`
        "origin": ("exported from a live UE 5.7.4 by "
                   "retarget/tools/ue_export_skeleton.py, from "
                   "C:/Program Files/Epic Games/UE_5.7/Templates/"
                   "TemplateResources/High/Mannequin copied verbatim into a "
                   "throwaway project at <WERK_LAB>/Stage6UE"),
        "licence": "Epic engine content; NOT redistributed, in the fixture or "
                   "in this repository",
        "regenerate": (
            'copy "C:/Program Files/Epic Games/UE_5.7/Templates/'
            'TemplateResources/High/Mannequin/Content" to '
            '<WERK_LAB>/Stage6UE/S6/Content/Mannequin, write a minimal S6.uproject '
            'enabling PythonScriptPlugin, then: UnrealEditor-Cmd.exe '
            '<WERK_LAB>/Stage6UE/S6/S6.uproject -run=pythonscript '
            '-script="<repo>/retarget/tools/ue_export_skeleton.py" '
            '-unattended -nosplash -nullrhi'),
        "map": "ue-mannequin",
    },
    {
        "key": "cmu",
        "label": "CMU mocap: take 02_01 (BVH)",
        "path": "retarget/testdata/02_01.bvh",
        "sha256": "cf56db43157acc3d200b3d4215523f54d354a8926bea67e1f6c8031bd335ba7e",
        "origin": ("https://raw.githubusercontent.com/una-dinosauria/cmu-mocap/"
                   "master/data/002/02_01.bvh -- Bruce Hahne's BVH conversion "
                   "of the CMU Graphics Lab Motion Capture Database"),
        "licence": "free for all uses; CMU's own terms in cmu-READMEFIRST.txt",
        "map": "cmu-bvh",
    },
]

FIXTURE = os.path.join(ROOT, "fixtures", "humanoid-retarget-v1.werk")
# S8-1..S8-3: a gate's numbers are measurements of ONE fixture build, so the
# build is pinned against fixtures/fixtures.json before anything is measured.
# A rebuild then fails here with both hashes in the message, instead of the
# gate going on printing PASS about a different file.
sys.path.insert(0, os.path.join(ROOT, "tests"))
from fixture_pin import pin as _pin_fixture           # noqa: E402



# =====================================================================
# harness
# =====================================================================

class Gate:
    def __init__(self):
        self.rows = []
        self.t0 = time.time()

    def add(self, status, name, detail):
        self.rows.append((status, name, detail))
        print("[%s] %-42s %s" % (status, name, detail))
        return status == "PASS"

    def check(self, ok, name, detail):
        return self.add("PASS" if ok else "FAIL", name, detail)

    def skip(self, name, reason):
        return self.add("SKIP", name, reason)

    def report(self):
        p = sum(1 for s, _, _ in self.rows if s == "PASS")
        f = sum(1 for s, _, _ in self.rows if s == "FAIL")
        s = sum(1 for s, _, _ in self.rows if s == "SKIP")
        print()
        print("%d PASS, %d FAIL, %d SKIP    (%.1f s total)"
              % (p, f, s, time.time() - self.t0))
        print("GATE: %s" % ("PASSED" if f == 0 and s == 0 else
                            "INCOMPLETE (%d SKIPPED; a skip is not a pass)" % s
                            if f == 0 else "FAILED"))
        # A SKIP is not a PASS: a run that skipped a clause did not verify it.
        return f == 0 and s == 0


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_source(spec, canon):
    p = spec["path"] if os.path.isabs(spec["path"]) else os.path.join(ROOT, spec["path"])
    if spec["key"] == "cesium":
        rig, clip = gltf.load(p, clip_id="cesium-walk")
    elif spec["key"] == "cmu":
        rig, clip = bvh.load(p, clip_id="cmu-02-01")
    else:
        rig, clip = ue.load(p, clip_name="ThirdPersonWalk", clip_id="ue-walk")
    name_map, prov = load_map(spec["map"])
    return rig, clip, name_map, prov, p


def through_file(cclip, canon, clip_id):
    """canonical clip -> WKAC bytes -> canonical clip, via the real writer and
    a reader that decodes the DECLARED header rather than reversing it."""
    data, header = writers.build_wkac(cclip, "canonical-humanoid-v1", clip_id=clip_id)
    back = writers.clip_from_wkac(data, canon)
    return back, data, header


def bone_lengths(clip):
    """Model-space parent->child distances for every frame."""
    rig = clip.rig
    _Q, P = clip.fk_all()
    out = []
    for i in range(rig.n):
        p = int(rig.parent[i])
        if p >= 0:
            out.append(np.linalg.norm(P[:, i, :] - P[:, p, :], axis=-1))
    return np.array(out)          # (bones, frames)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild-fixture", action="store_true")
    ap.add_argument("--json", default=None)
    a = ap.parse_args(argv)

    g = Gate()
    out = {"tolerances": TOL, "sources": [], "retargets": {}, "transits": [],
           "fixture": {}}

    print("werk Stage 6 gate -- one calibration pose, three foreign rigs")
    print("declared tolerances: %s" % json.dumps(TOL, sort_keys=True))
    print()

    canon = load_canonical()
    g.check(canon.source["recompose_residual_position_m"] < 1e-5,
            "canonical skeleton recomposes",
            "%.3e m worst local->model disagreement (schema asks for 1e-5); "
            "23 bones, status %s"
            % (canon.source["recompose_residual_position_m"], canon.source["status"]))

    # -- 0. the test data is the test data it claims to be -----------------
    present = []
    for spec in SOURCES:
        p = spec["path"] if os.path.isabs(spec["path"]) else os.path.join(ROOT, spec["path"])
        if not os.path.isfile(p):
            if spec.get("regenerate"):
                g.skip("source present: " + spec["key"],
                       "%s is absent. It is not redistributable (%s), so it is "
                       "regenerated, not cloned. To produce it: %s"
                       % (p, spec["licence"], spec["regenerate"]))
            else:
                g.check(False, "source present: " + spec["key"], "MISSING %s" % p)
            continue
        present.append(spec["key"])
        h = sha256_file(p)
        rec = {"key": spec["key"], "path": p, "sha256": h,
               "size": os.path.getsize(p), "origin": spec["origin"],
               "licence": spec["licence"]}
        out["sources"].append(rec)
        if spec["sha256"] is None:
            g.add("PASS", "source present: " + spec["key"],
                  "%d B, sha256 %s (produced on this box, not pinned)"
                  % (rec["size"], h[:16]))
        else:
            g.check(h == spec["sha256"], "source hash: " + spec["key"],
                    "%d B, sha256 %s" % (rec["size"], h[:16]))

    # -- 1..3. per-rig -----------------------------------------------------
    state = {}
    for spec in SOURCES:
        k = spec["key"]
        if k not in present:
            continue
        rig, clip, name_map, prov, path = load_source(spec, canon)
        bind, scores = calibrate.scan_clip(clip, canon, name_map)
        cclip = RT.to_canonical(bind, clip, clip_id=k + "-canonical")
        cback, wkac, header = through_file(cclip, canon, k + "-canonical")
        back = RT.to_rig(bind, cback)
        inv = calibrate.frame_invariance_residual(bind, clip)
        arr = np.array([s["direction_rms_rad"] for s in scores])
        state[k] = {"rig": rig, "clip": clip, "map": name_map, "bind": bind,
                    "cclip": cclip, "cback": cback, "wkac": wkac,
                    "header": header, "back": back}

        r = {"label": spec["label"], "rig_bones": rig.n, "clip_frames": clip.frames,
             "rate_hz": clip.rate_hz, "map_id": prov["map_id"],
             "map_from": prov["from"], "bound_bones": len(bind.pairs),
             "solved_scale": bind.scale,
             "solved_rotation_wxyz": [float(x) for x in bind.qA],
             "calibration": bind.calibration,
             "calibration_direction_rms_rad": bind.residuals["direction_rms_rad"],
             "calibration_direction_max_rad": bind.residuals["direction_max_rad"],
             "calibration_position_rms_m": bind.residuals["position_rms_m"],
             "scan": {"candidates": len(scores), "best": float(arr.min()),
                      "median": float(np.median(arr)), "worst": float(arr.max())},
             "frame_invariance": inv,
             "wkac_bytes": len(wkac)}

        # T1 -- the scan landscape has a minimum
        ratio = float(arr.min() / np.median(arr))
        r["scan_best_over_median"] = ratio
        g.check(ratio <= TOL["scan_best_over_median"],
                "%s: scan finds a distinguished pose" % k,
                "best/median %.3f <= %.2f over %d candidates; winner %s"
                % (ratio, TOL["scan_best_over_median"], len(scores),
                   json.dumps(bind.calibration.get("source")) +
                   ("" if bind.calibration.get("frame") is None
                    else " frame %d" % bind.calibration["frame"])))

        # T2 -- a wrong calibration pose must visibly break the retarget
        worst = max(scores, key=lambda s: s["direction_rms_rad"])
        if worst["kind"] == "rest":
            bad = calibrate.solve(rig, canon, name_map)
        else:
            f = worst["frame"]
            lt = None if clip.bone_t is None else clip.bone_t[f]
            ro = None if clip.bone_t is not None else clip.root_t[f]
            bad = calibrate.solve(rig, canon, name_map, local_q=clip.local_q[f],
                                  local_t=lt, root_offset=ro)
        bad_clip = RT.to_canonical(bad, clip, clip_id=k + "-badbind")
        shared = sorted(set(canon.names[ci] for _, ci in bind.pairs))
        dmg = RT.compare_model(cclip, bad_clip, bones=shared)
        r["wrong_pose_damage_rad"] = dmg["max_rad"]
        g.check(dmg["max_rad"] >= TOL["wrong_pose_min_damage_rad"],
                "%s: a wrong calibration pose breaks it" % k,
                "binding on the worst candidate moves the pose by %.4f rad "
                "(%.1f deg) at %s, threshold >= %.2f"
                % (dmg["max_rad"], np.rad2deg(dmg["max_rad"]), dmg["worst_bone"],
                   TOL["wrong_pose_min_damage_rad"]))

        # T3 -- frame invariance where the proof applies
        adj = inv["adjacent"]
        g.check(adj is not None and adj["spread_rad"] <= TOL["frame_invariance_adjacent_rad"],
                "%s: per-bone error is frame-invariant" % k,
                "%d adjacent pairs, spread across %d frames %.2e rad <= %.0e%s"
                % (adj["pairs"], inv["frames"], adj["spread_rad"],
                   TOL["frame_invariance_adjacent_rad"],
                   "" if inv["interposed"] is None else
                   "; %d interposed pair(s) %s spread %.4f rad, NOT averaged in"
                   % (inv["interposed"]["pairs"], inv["interposed_bones"],
                      inv["interposed"]["spread_rad"])))

        # T4 -- round trip through the real file
        mapped = [rig.names[fi] for fi, ci in bind.pairs]
        rt = RT.compare_model(clip, back, bones=mapped)
        r["roundtrip"] = rt
        g.check(rt["max_rad"] <= TOL["roundtrip_rad"],
                "%s: round trip through core.anim.clip" % k,
                "%.3e rad max over %d bones x %d frames (worst %s), rms %.3e; "
                "%d B of f32 payload crossed"
                % (rt["max_rad"], rt["bones"], rt["frames"], rt["worst_bone"],
                   rt["rms_rad"], len(wkac)))

        # T6 -- lengths
        L = bone_lengths(cclip)
        drift = float((L.max(axis=1) - L.min(axis=1)).max())
        r["bone_length_drift_m"] = drift
        g.check(drift <= TOL["bone_length_drift_m"],
                "%s: retarget moves rotations only" % k,
                "worst canonical bone-length drift over the clip %.2e m <= %.0e"
                % (drift, TOL["bone_length_drift_m"]))

        # T7 -- the result is a plausible human
        _Q, P = cclip.fk_all()
        hips = P[:, canon.index["hips"], 1]
        toes = np.minimum(P[:, canon.index["l-toe"], 1], P[:, canon.index["r-toe"], 1])
        r["hips_y_m"] = [float(hips.min()), float(hips.max())]
        r["min_toe_y_m"] = float(toes.min())
        g.check(TOL["hips_min_m"] <= hips.min() and hips.max() <= TOL["hips_max_m"],
                "%s: retargeted figure is plausible" % k,
                "hips %.3f..%.3f m above the declared floor (window %.2f..%.2f), "
                "lowest toe %.3f m; stature scale %.5f was SOLVED, not declared"
                % (hips.min(), hips.max(), TOL["hips_min_m"], TOL["hips_max_m"],
                   toes.min(), bind.scale))

        out["retargets"][k] = r

    # -- 4. cross-rig transit ---------------------------------------------
    keys = [s["key"] for s in SOURCES if s["key"] in state]
    for a_k in keys:
        for b_k in keys:
            if a_k == b_k:
                continue
            A = state[a_k]
            B = state[b_k]
            onB = RT.to_rig(B["bind"], A["cback"], clip_id="%s-on-%s" % (a_k, b_k))
            back_c = RT.to_canonical(B["bind"], onB, clip_id="%s-via-%s" % (a_k, b_k))
            back_c2, data2, _h = through_file(back_c, canon, "%s-via-%s" % (a_k, b_k))
            sa = set(canon.names[ci] for _, ci in A["bind"].pairs)
            sb = set(canon.names[ci] for _, ci in B["bind"].pairs)
            shared = sorted(sa & sb)
            lost = sorted(sa - sb)
            cmp_ = RT.compare_model(A["cclip"], back_c2, bones=shared)
            out["transits"].append({"from": a_k, "to": b_k, "shared": shared,
                                    "lost": lost, "result": cmp_,
                                    "bytes": len(data2)})
            g.check(cmp_["max_rad"] <= TOL["transit_rad"],
                    "transit %s -> %s -> canonical" % (a_k, b_k),
                    "%.3e rad max over %d shared bones (worst %s); %d bone(s) "
                    "%s cannot cross and are named, not averaged away"
                    % (cmp_["max_rad"], len(shared), cmp_["worst_bone"],
                       len(lost), lost or "-"))

    # -- 5. the fixture ----------------------------------------------------
    if a.rebuild_fixture or not os.path.isfile(FIXTURE):
        rc = subprocess.run([sys.executable,
                             os.path.join(ROOT, "fixtures", "build_retarget_fixture.py")],
                            cwd=ROOT, capture_output=True, text=True)
        g.check(rc.returncode == 0, "fixture builds",
                (rc.stdout.strip().splitlines() or ["-"])[-1])
    if os.path.isfile(FIXTURE):
        size = os.path.getsize(FIXTURE)
        fh = sha256_file(FIXTURE)
        out["fixture"] = {"path": FIXTURE, "size": size, "sha256": fh}
        r = _pin_fixture("humanoid-retarget-v1")
        g.add("PASS" if r.ok else "FAIL", "fixture pinned", r.detail)
        g.add("PASS", "fixture present", "%d B, sha256 %s" % (size, fh[:16]))

        # werk-core, over werk.dll
        rc = subprocess.run([sys.executable,
                             os.path.join(ROOT, "bindings", "python", "werk.py"),
                             FIXTURE], cwd=ROOT, capture_output=True, text=True)
        tail = (rc.stdout.strip().splitlines() or ["-"])[-1]
        errs = 0
        for line in rc.stdout.splitlines():
            if line.startswith("[error]"):
                errs += 1
        g.check(errs == 0, "fixture: werk-core verify", tail)
        out["fixture"]["werk_core"] = tail

        # the standalone bootstrap reader, which shares no code with the above
        rc = subprocess.run([sys.executable,
                             os.path.join(ROOT, "loaders", "werk_read.py"),
                             FIXTURE, "--verify"], cwd=ROOT,
                            capture_output=True, text=True)
        line = [l for l in rc.stdout.splitlines() if "files verified" in l]
        g.check(rc.returncode == 0 and line,
                "fixture: werk_read.py standalone",
                (line or ["no verification line"])[0] + " (exit %d)" % rc.returncode)
        out["fixture"]["werk_read"] = (line or [""])[0]

        # and the payload the fixture exists for: decode the WKAC out of the
        # package with a reader that never saw the writer, and check the clip
        # against the canonical rig it names.
        import zipfile
        with zipfile.ZipFile(FIXTURE) as z:
            wk = z.read("anim/cmu-02-01-walk.wkac")
            cj = json.loads(z.read("anim/cmu-02-01-walk.json"))
        h, root, rot = writers.read_wkac(wk)
        agree = (h["bone_count"] == cj["bone_count"] and
                 h["frame_count"] == cj["frame_count"] and
                 abs(float(h["rate_hz"]) - cj["rate_hz"]) < 1e-9 and
                 abs(float(h["duration_s"]) - cj["duration_s"]) < 1e-9 and
                 list(h["bones"]) == cj["bones"] and
                 h["root_bone"] == cj["root_bone"])
        g.check(agree, "fixture: WKAC binary and JSON agree",
                "%d bones x %d frames at %.4f Hz, duration %.6f s, root %r; "
                "the layout says the binary is authoritative and the two "
                "statements match"
                % (h["bone_count"], h["frame_count"], h["rate_hz"],
                   h["duration_s"], h["root_bone"]))
        unit = float(np.abs(np.linalg.norm(rot, axis=-1) - 1.0).max())
        g.check(unit < 1e-6, "fixture: clip rotations are unit quaternions",
                "worst |q|-1 = %.2e over %d x %d stored rotations"
                % (unit, h["bone_count"], h["frame_count"]))

    ok = g.report()
    if a.json:
        out["result"] = "PASSED" if ok else "FAILED"
        out["rows"] = [{"status": s, "name": n, "detail": d} for s, n, d in g.rows]
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1, default=str)
        print("wrote %s" % a.json)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
