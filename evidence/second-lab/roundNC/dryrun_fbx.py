#!/usr/bin/env python3
"""
dryrun_fbx.py -- plan 5.7 instrument check of grade_nc.py on the FBX control.

Same shape as dryrun.py, FBX only. Everything goes under dryrun/fbx/:
  logs/        one .log + .json per check
  clean/       clean-dir re-runs of the reference extractor (holds fixture copies)
  blender-ref/ second reference extraction, by Blender's own FBX importer
  corrupt/     copies with one byte flipped or one value changed
  workspaces/  generated agent workspaces for the echo check (fixture + PROMPT.txt)
  SUMMARY.txt  expected vs observed per check

Every grade passes --allow-provisional, so the same script runs before and
after the freeze (the flag is a no-op for COMPLETE ground truth).
Standard library only (Blender is called as an external program).
"""

import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DR = os.path.join(HERE, "dryrun", "fbx")
REF = os.path.join(HERE, "dryrun", "ref")
PY = sys.executable
GR = os.path.join(HERE, "grade_nc.py")
BLENDER = "C:/Program Files/Blender Foundation/Blender 4.2/blender.exe"

with open(os.path.join(HERE, "expectations.json"), encoding="utf-8") as f:
    EXP = json.load(f)
FBX = EXP["formats"]["fbx"]
FIX = os.path.join(HERE, "crate-nc-v1.fbx")
TEXNAME = FBX["payloads"][0]["path"]

results = []
PROV = ["--format", "fbx", "--allow-provisional"]
HUMAN = ["--human", "C2=PASS", "--human", "C3=PASS-honest"]


def run(tag, argv, check):
    log = os.path.join(DR, "logs", tag + ".log")
    js = os.path.join(DR, "logs", tag + ".json")
    os.makedirs(os.path.dirname(log), exist_ok=True)
    p = subprocess.run([PY, GR] + argv + ["--json", js], capture_output=True)
    with open(log, "wb") as f:
        f.write(p.stdout + (b"\n--- stderr ---\n" + p.stderr if p.stderr else b""))
    if p.returncode != 0:
        results.append((tag, "grader exit 0", "exit %d" % p.returncode, False))
        return None
    with open(js, encoding="utf-8") as f:
        r = json.load(f)
    exp, got, ok = check(r)
    results.append((tag, exp, got, ok))
    return r


def flip(path, offset):
    with open(path, "r+b") as f:
        f.seek(offset)
        b = f.read(1)
        f.seek(offset)
        f.write(bytes([b[0] ^ 0x01]))


def clauses(r):
    return " ".join("%s=%s" % (k, r["clauses"][k]["result"]) for k in ("C1", "C2", "C3", "C4", "C5"))


def c5(r, cls):
    return r["clauses"]["C5"]["per_class"].get(cls, "")


def main():
    for d in ("logs", "clean", "blender-ref", "corrupt", "workspaces"):
        shutil.rmtree(os.path.join(DR, d), ignore_errors=True)
    os.makedirs(DR, exist_ok=True)
    src = open(os.path.join(REF, "ref_extract_fbx.py"), encoding="utf-8").read()
    with open(os.path.join(REF, "ref_extract_fbx_f32.py"), "w", encoding="utf-8", newline="\n") as f:
        f.write(src.replace('MESH_AS = "obj"', 'MESH_AS = "f32"'))

    pend = lambda r: ("PENDING, C1/C4/C5 PASS",
                      "%s %s" % (r["verdict"], clauses(r)),
                      r["verdict"] == "PENDING" and all(
                          r["clauses"][k]["result"] == "PASS" for k in ("C1", "C4", "C5")))

    # 1. stdlib reference extraction, clean-dir re-run
    base = PROV + ["--payload", "texture", "--rundir", REF, "--rerun", "--prog", "ref_extract_fbx.py"]
    run("1-fbx-ref-texture", base + ["--out", os.path.join(DR, "clean", "ref-texture")], pend)
    run("1-fbx-ref-texture-ruled",
        base + ["--out", os.path.join(DR, "clean", "ref-texture-ruled")] + HUMAN,
        lambda r: ("PASS; mesh T2-VALUES (OBJ), texture T1",
                   "%s mesh=%s | texture=%s" % (r["verdict"], c5(r, "mesh"), c5(r, "texture")),
                   r["verdict"] == "PASS" and "T2-VALUES" in c5(r, "mesh")
                   and "[T1]" in c5(r, "texture")))
    run("1-fbx-ref-f32-ruled",
        PROV + ["--payload", "texture", "--rundir", REF, "--rerun", "--prog", "ref_extract_fbx_f32.py",
                "--out", os.path.join(DR, "clean", "ref-f32")] + HUMAN,
        lambda r: ("PASS; mesh T2-EXACT (canonical .f32 dump bytes)",
                   "%s mesh=%s" % (r["verdict"], c5(r, "mesh")),
                   r["verdict"] == "PASS" and "T2-EXACT" in c5(r, "mesh")))
    run("1-fbx-ref-sound-NA-ruled",
        PROV + ["--payload", "sound", "--rundir", REF, "--rerun", "--prog", "ref_extract_fbx.py",
                "--out", os.path.join(DR, "clean", "ref-sound")] + HUMAN,
        lambda r: ("PASS on mesh only, sound N/A",
                   "%s na=%s %s" % (r["verdict"], r["second_payload_na"], clauses(r)),
                   r["verdict"] == "PASS" and r["second_payload_na"]))

    # 1b. Blender's own importer as a second, independent reference
    bref = os.path.join(DR, "blender-ref")
    os.makedirs(bref)
    tmpfbx = os.path.join(DR, "blender-ref-input")
    shutil.rmtree(tmpfbx, ignore_errors=True)
    os.makedirs(tmpfbx)
    shutil.copy2(FIX, tmpfbx)
    p = subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1",
                        "--python", os.path.join(REF, "ref_extract_fbx_blender.py"), "--",
                        os.path.join(tmpfbx, "crate-nc-v1.fbx"), bref], capture_output=True)
    os.makedirs(os.path.join(DR, "logs"), exist_ok=True)
    with open(os.path.join(DR, "logs", "1-fbx-blender-ref-extract.log"), "wb") as f:
        f.write(p.stdout + b"\n--- stderr ---\n" + p.stderr)
    shutil.rmtree(tmpfbx)
    run("1-fbx-blender-ref-ruled", PROV + ["--payload", "texture", "--rundir", bref] + HUMAN,
        lambda r: ("C4/C5 PASS (texture T1; mesh by T2, objects in Blender name order); "
                   "C1 NOT-RUN (no clean re-run), so PENDING",
                   "%s %s | mesh=%s | texture=%s" % (r["verdict"], clauses(r), c5(r, "mesh"), c5(r, "texture")),
                   r["clauses"]["C5"]["result"] == "PASS" and r["clauses"]["C4"]["result"] == "PASS"
                   and r["verdict"] == "PENDING"))

    # 2. corruptions (graded as run dirs, no re-run)
    good = os.path.join(DR, "clean", "ref-texture-ruled")
    c1 = os.path.join(DR, "corrupt", "texture-byteflip")
    shutil.copytree(good, c1)
    png = os.path.join(c1, "out", TEXNAME)
    flip(png, os.path.getsize(png) // 2)
    run("2-fbx-corrupt-texture", PROV + ["--payload", "texture", "--rundir", c1] + HUMAN,
        lambda r: ("C5 FAIL (texture mismatch), verdict PARTIAL (mesh still exact)",
                   "%s C5=%s texture=%s" % (r["verdict"], r["clauses"]["C5"]["result"], c5(r, "texture")),
                   r["clauses"]["C5"]["result"] == "FAIL" and c5(r, "texture").startswith("FAIL")
                   and r["verdict"] == "PARTIAL"))

    def obj_bump(tag, pick):
        d = os.path.join(DR, "corrupt", tag)
        shutil.copytree(good, d)
        objp = os.path.join(d, "out", "crate.obj")
        lines = open(objp, encoding="utf-8").read().split("\n")
        vi = [i for i, l in enumerate(lines) if l.startswith("v ")]
        k = pick(vi, lines)
        t = lines[k].split()
        t[1] = repr(float(t[1]) + 1e-3)
        lines[k] = " ".join(t)
        open(objp, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
        return d

    # 2b. interior vertex x + 1e-3: the plan 1.3 text-dump rule (count + bbox)
    # cannot see this. Recorded as a KNOWN LIMIT, expected to still PASS.
    def interior(vi, lines):
        xs = [float(lines[i].split()[1]) for i in vi]
        lo, hi = min(xs), max(xs)
        return next(i for i, x in zip(vi, xs) if lo + 1e-2 < x < hi - 1e-2)
    c2 = obj_bump("obj-interior-x-plus-1e-3", interior)
    run("2-fbx-obj-interior-value-KNOWN-LIMIT", PROV + ["--payload", "texture", "--rundir", c2] + HUMAN,
        lambda r: ("PASS via T2-COUNT+BBOX (known limit: count+bbox rule for text dumps "
                   "does not see an interior value error)",
                   "%s mesh=%s" % (r["verdict"], c5(r, "mesh")),
                   "T2-COUNT+BBOX" in c5(r, "mesh")))

    # 2c. the vertex holding max x, + 1e-3: moves the bbox, must FAIL C5 mesh
    def extreme(vi, lines):
        return max(vi, key=lambda i: float(lines[i].split()[1]))
    c2b = obj_bump("obj-bbox-max-x-plus-1e-3", extreme)
    run("2-fbx-corrupt-obj-bbox-value", PROV + ["--payload", "texture", "--rundir", c2b] + HUMAN,
        lambda r: ("C5 FAIL (mesh: no matching artifact), verdict PARTIAL",
                   "%s C5=%s mesh=%s" % (r["verdict"], r["clauses"]["C5"]["result"], c5(r, "mesh")),
                   r["clauses"]["C5"]["result"] == "FAIL" and c5(r, "mesh").startswith("FAIL")))

    c3 = os.path.join(DR, "corrupt", "f32-byteflip")
    shutil.copytree(os.path.join(DR, "clean", "ref-f32"), c3)
    flip(os.path.join(c3, "out", "crate-positions.f32"), 4 * 3 * 100 + 1)
    run("2-fbx-corrupt-f32", PROV + ["--payload", "texture", "--rundir", c3] + HUMAN,
        lambda r: ("C5 FAIL (mesh), texture still PASS",
                   "%s C5=%s mesh=%s" % (r["verdict"], r["clauses"]["C5"]["result"], c5(r, "mesh")),
                   r["clauses"]["C5"]["result"] == "FAIL" and c5(r, "mesh").startswith("FAIL")
                   and c5(r, "texture").startswith("PASS")))

    c4 = os.path.join(DR, "corrupt", "no-extraction-input-only")
    os.makedirs(c4)
    shutil.copy2(FIX, c4)
    run("2-fbx-input-only", PROV + ["--payload", "texture", "--rundir", c4] + HUMAN,
        lambda r: ("FAIL (input at its own path is not an extraction, R4)",
                   "%s (%s)" % (r["verdict"], r["verdict_reason"]),
                   r["verdict"] == "FAIL"))

    # 3. echo rule: generated FBX agent workspaces = fixture + PROMPT.txt only
    wsroot = os.path.join(DR, "workspaces")
    for payload in ("sound", "texture"):
        ws = os.path.join(wsroot, "fbx-" + payload)
        os.makedirs(ws)
        shutil.copy2(FIX, ws)
        shutil.copy2(os.path.join(HERE, "prompts", payload, "PROMPT-fbx.txt"),
                     os.path.join(ws, "PROMPT.txt"))
        assert sorted(os.listdir(ws)) == ["PROMPT.txt", "crate-nc-v1.fbx"]
        run("3-echo-fbx-" + payload, PROV + ["--echo-check", ws],
            lambda r: ("PASS (no leaks, 0 self-declared)",
                       "%s leaks=%d self-declared=%d files=%d values=%d" % (
                           r["result"], len(r["leaks"]), r["allowed_self_declared"],
                           r["files_scanned"], r["values_checked"]),
                       r["result"] == "PASS" and r["allowed_self_declared"] == 0))
    ws = os.path.join(wsroot, "SELFTEST-planted-leak")
    shutil.copytree(os.path.join(wsroot, "fbx-texture"), ws)
    with open(os.path.join(ws, "PROMPT.txt"), "a", encoding="utf-8") as f:
        f.write("\n" + FBX["payloads"][0]["sha256"] + "\n")
    run("3-echo-fbx-SELFTEST-planted-leak", PROV + ["--echo-check", ws],
        lambda r: ("FAIL (planted texture sha256 detected)",
                   "%s leaks=%d" % (r["result"], len(r["leaks"])), r["result"] == "FAIL"))
    for payload in ("sound", "texture"):
        run("3-echo-fbx-prompts-" + payload,
            PROV + ["--echo-check", os.path.join(HERE, "prompts", payload)],
            lambda r: ("PASS", "%s leaks=%d" % (r["result"], len(r["leaks"])), r["result"] == "PASS"))

    w = max(len(t) for t, *_ in results)
    out = ["roundNC FBX dry-run summary (grade_nc.py instrument check, plan 5.7)",
           "fixture crate-nc-v1.fbx sha256 %s (%d B), ground truth %s" % (
               FBX["fixture_files"][0]["sha256"], FBX["fixture_files"][0]["size"], FBX["status"]), ""]
    for t, e, g, ok in results:
        out.append("%-4s %-*s  expected: %s" % ("OK" if ok else "BAD", w, t, e))
        out.append("     %-*s  observed: %s" % (w, "", g))
    nbad = sum(1 for r in results if not r[3])
    out += ["", "checks: %d   as expected: %d   unexpected: %d" % (len(results), len(results) - nbad, nbad)]
    txt = "\n".join(out) + "\n"
    with open(os.path.join(DR, "SUMMARY.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(txt)
    print(txt)
    sys.exit(1 if nbad else 0)


if __name__ == "__main__":
    main()
