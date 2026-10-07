#!/usr/bin/env python3
"""
dryrun_usdz.py -- plan 5.7 instrument check of grade_nc.py on the USDZ control.

Same shape as dryrun_fbx.py, USDZ only. Everything goes under dryrun/usdz/:
  logs/        one .log + .json per check
  clean/       clean-dir re-runs of the reference extractor (holds fixture copies)
  blender-ref/ second reference extraction, by Blender's own USD importer
  corrupt/     copies with one byte flipped, or with the mesh step left out
  workspaces/  generated agent workspaces for the echo check (fixture + PROMPT.txt)
  SUMMARY.txt  expected vs observed per check
Only logs/ and SUMMARY.txt are committed (the rest holds fixture copies).

Every grade passes --allow-provisional, so the same script runs before and
after the freeze. Standard library only (Blender is called as an external
program by the reference extractors).
"""

import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DR = os.path.join(HERE, "dryrun", "usdz")
REF = os.path.join(HERE, "dryrun", "ref")
PY = sys.executable
GR = os.path.join(HERE, "grade_nc.py")
BLENDER = "C:/Program Files/Blender Foundation/Blender 4.2/blender.exe"

with open(os.path.join(HERE, "expectations.json"), encoding="utf-8") as f:
    EXP = json.load(f)
USDZ = EXP["formats"]["usdz"]
FIX = os.path.join(HERE, "crate-nc-v1.usdz")
TEXNAME = os.path.basename(USDZ["payloads"][0]["path"])

results = []
PROV = ["--format", "usdz", "--allow-provisional"]
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


def vif(r):
    v = r["verifiable_integrity_fraction"]
    return "vif any=%s crypto=%s kinds=%s" % (v["any_declared"], v["cryptographic"], v["kinds"])


def main():
    for d in ("logs", "clean", "blender-ref", "corrupt", "workspaces"):
        shutil.rmtree(os.path.join(DR, d), ignore_errors=True)
    os.makedirs(DR, exist_ok=True)
    src = open(os.path.join(REF, "ref_extract_usdz.py"), encoding="utf-8").read()
    with open(os.path.join(REF, "ref_extract_usdz_f32.py"), "w", encoding="utf-8", newline="\n") as f:
        f.write(src.replace('MESH_AS = "obj"', 'MESH_AS = "f32"'))

    pend = lambda r: ("PENDING, C1/C4/C5 PASS",
                      "%s %s" % (r["verdict"], clauses(r)),
                      r["verdict"] == "PENDING" and all(
                          r["clauses"][k]["result"] == "PASS" for k in ("C1", "C4", "C5")))

    # 1. reference extraction (zipfile + pxr via Blender), clean-dir re-run
    base = PROV + ["--payload", "texture", "--rundir", REF, "--rerun", "--prog", "ref_extract_usdz.py"]
    run("1-usdz-ref-texture", base + ["--out", os.path.join(DR, "clean", "ref-texture")], pend)
    run("1-usdz-ref-texture-ruled",
        base + ["--out", os.path.join(DR, "clean", "ref-texture-ruled")] + HUMAN,
        lambda r: ("PASS; mesh T2-VALUES (OBJ), texture T1; vif any=1.0 (CRC-32), crypto=0.0",
                   "%s mesh=%s | texture=%s | %s" % (r["verdict"], c5(r, "mesh"), c5(r, "texture"), vif(r)),
                   r["verdict"] == "PASS" and "T2-VALUES" in c5(r, "mesh")
                   and "[T1]" in c5(r, "texture")
                   and r["verifiable_integrity_fraction"]["any_declared"] == 1.0
                   and r["verifiable_integrity_fraction"]["cryptographic"] == 0.0))
    run("1-usdz-ref-f32-ruled",
        PROV + ["--payload", "texture", "--rundir", REF, "--rerun", "--prog", "ref_extract_usdz_f32.py",
                "--out", os.path.join(DR, "clean", "ref-f32")] + HUMAN,
        lambda r: ("PASS; mesh T2-EXACT (canonical .f32 dump bytes)",
                   "%s mesh=%s" % (r["verdict"], c5(r, "mesh")),
                   r["verdict"] == "PASS" and "T2-EXACT" in c5(r, "mesh")))
    run("1-usdz-ref-sound-NA-ruled",
        PROV + ["--payload", "sound", "--rundir", REF, "--rerun", "--prog", "ref_extract_usdz.py",
                "--out", os.path.join(DR, "clean", "ref-sound")] + HUMAN,
        lambda r: ("PASS on mesh only, sound N/A",
                   "%s na=%s %s" % (r["verdict"], r["second_payload_na"], clauses(r)),
                   r["verdict"] == "PASS" and r["second_payload_na"]))

    # 1b. Blender's own USD importer as a second reference
    bref = os.path.join(DR, "blender-ref")
    os.makedirs(bref)
    tmp = os.path.join(DR, "blender-ref-input")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    shutil.copy2(FIX, tmp)
    p = subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1",
                        "--python", os.path.join(REF, "ref_extract_usdz_blender.py"), "--",
                        os.path.join(tmp, "crate-nc-v1.usdz"), bref], capture_output=True)
    os.makedirs(os.path.join(DR, "logs"), exist_ok=True)
    with open(os.path.join(DR, "logs", "1-usdz-blender-ref-extract.log"), "wb") as f:
        f.write(p.stdout + b"\n--- stderr ---\n" + p.stderr)
    shutil.rmtree(tmp)
    run("1-usdz-blender-ref-ruled", PROV + ["--payload", "texture", "--rundir", bref] + HUMAN,
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
    run("2-usdz-corrupt-texture", PROV + ["--payload", "texture", "--rundir", c1] + HUMAN,
        lambda r: ("C5 FAIL (texture mismatch), verdict PARTIAL (mesh still exact)",
                   "%s C5=%s texture=%s" % (r["verdict"], r["clauses"]["C5"]["result"], c5(r, "texture")),
                   r["clauses"]["C5"]["result"] == "FAIL" and c5(r, "texture").startswith("FAIL")
                   and r["verdict"] == "PARTIAL"))

    c3 = os.path.join(DR, "corrupt", "f32-byteflip")
    shutil.copytree(os.path.join(DR, "clean", "ref-f32"), c3)
    flip(os.path.join(c3, "out", "crate-positions.f32"), 4 * 3 * 100 + 1)
    run("2-usdz-corrupt-f32", PROV + ["--payload", "texture", "--rundir", c3] + HUMAN,
        lambda r: ("C5 FAIL (mesh), texture still PASS",
                   "%s C5=%s mesh=%s" % (r["verdict"], r["clauses"]["C5"]["result"], c5(r, "mesh")),
                   r["clauses"]["C5"]["result"] == "FAIL" and c5(r, "mesh").startswith("FAIL")
                   and c5(r, "texture").startswith("PASS")))

    # 2b. usdc layer copied out verbatim, no mesh dump: not a mesh extraction
    c4 = os.path.join(DR, "corrupt", "usdc-copied-no-dump")
    shutil.copytree(good, c4)
    os.remove(os.path.join(c4, "out", "crate.obj"))
    import zipfile
    with zipfile.ZipFile(FIX) as z:
        layer = USDZ["usd"]["root_layer_entry"]
        with open(os.path.join(c4, "out", os.path.basename(layer)), "wb") as f:
            f.write(z.read(layer))
    run("2-usdz-usdc-copy-only", PROV + ["--payload", "texture", "--rundir", c4] + HUMAN,
        lambda r: ("C4 PASS (usdc is a mesh-class file), C5 FAIL mesh (usdc copy is not Tier 1), "
                   "verdict PARTIAL",
                   "%s C4=%s C5=%s mesh=%s" % (r["verdict"], r["clauses"]["C4"]["result"],
                                               r["clauses"]["C5"]["result"], c5(r, "mesh")),
                   r["clauses"]["C4"]["result"] == "PASS" and c5(r, "mesh").startswith("FAIL")
                   and r["verdict"] == "PARTIAL"))

    c5d = os.path.join(DR, "corrupt", "no-extraction-input-only")
    os.makedirs(c5d)
    shutil.copy2(FIX, c5d)
    run("2-usdz-input-only", PROV + ["--payload", "texture", "--rundir", c5d] + HUMAN,
        lambda r: ("FAIL (input at its own path is not an extraction, R4)",
                   "%s (%s)" % (r["verdict"], r["verdict_reason"]), r["verdict"] == "FAIL"))

    # 3. echo rule: generated USDZ agent workspaces = fixture + PROMPT.txt only
    wsroot = os.path.join(DR, "workspaces")
    for payload in ("sound", "texture"):
        ws = os.path.join(wsroot, "usdz-" + payload)
        os.makedirs(ws)
        shutil.copy2(FIX, ws)
        shutil.copy2(os.path.join(HERE, "prompts", payload, "PROMPT-usdz.txt"),
                     os.path.join(ws, "PROMPT.txt"))
        assert sorted(os.listdir(ws)) == ["PROMPT.txt", "crate-nc-v1.usdz"]
        run("3-echo-usdz-" + payload, PROV + ["--echo-check", ws],
            lambda r: ("PASS (no leaks, zip members scanned too)",
                       "%s leaks=%d self-declared=%d files=%d values=%d" % (
                           r["result"], len(r["leaks"]), r["allowed_self_declared"],
                           r["files_scanned"], r["values_checked"]),
                       r["result"] == "PASS"))
    ws = os.path.join(wsroot, "SELFTEST-planted-leak")
    shutil.copytree(os.path.join(wsroot, "usdz-texture"), ws)
    with open(os.path.join(ws, "PROMPT.txt"), "a", encoding="utf-8") as f:
        f.write("\n" + USDZ["tier2_mesh"]["dump_sha256"] + "\n")
    run("3-echo-usdz-SELFTEST-planted-leak", PROV + ["--echo-check", ws],
        lambda r: ("FAIL (planted tier2 sha256 detected)",
                   "%s leaks=%d" % (r["result"], len(r["leaks"])), r["result"] == "FAIL"))
    for payload in ("sound", "texture"):
        run("3-echo-usdz-prompts-" + payload,
            PROV + ["--echo-check", os.path.join(HERE, "prompts", payload)],
            lambda r: ("PASS", "%s leaks=%d" % (r["result"], len(r["leaks"])), r["result"] == "PASS"))

    w = max(len(t) for t, *_ in results)
    out = ["roundNC USDZ dry-run summary (grade_nc.py instrument check, plan 5.7)",
           "fixture crate-nc-v1.usdz sha256 %s (%d B), ground truth %s" % (
               USDZ["fixture_files"][0]["sha256"], USDZ["fixture_files"][0]["size"], USDZ["status"]), ""]
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
