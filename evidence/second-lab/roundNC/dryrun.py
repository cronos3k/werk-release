#!/usr/bin/env python3
"""
dryrun.py -- plan section 5.7 instrument check for grade_nc.py.

Runs, in order, and saves every log + JSON under dryrun/:
  1. reference extractions (trusted code: zipfile / file copies) graded with
     --rerun in a clean dir: must come out PENDING (only C2/C3 human clauses
     open), then PASS once those clauses are ruled.
  2. corrupted copies (one byte flipped in an extracted payload): must FAIL C5.
  3. echo rule: no expected hash value in any file of a generated agent
     workspace (plus a planted-leak self-test that must be caught).
Covers werk and glTF. FBX: dryrun_fbx.py. USDZ: dryrun_usdz.py.
Writes dryrun/SUMMARY.txt with expected vs observed per check.

Standard library only.
"""

import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DR = os.path.join(HERE, "dryrun")
REF = os.path.join(DR, "ref")
PY = sys.executable
GR = os.path.join(HERE, "grade_nc.py")

with open(os.path.join(HERE, "expectations.json"), encoding="utf-8") as f:
    EXP = json.load(f)
sys.path.insert(0, HERE)
from grade_nc import default_repo  # noqa: E402
REPO = default_repo()  # staging: ../werk ; after the move: ../..

results = []


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


def main():
    # fresh output tree (keep ref/ sources)
    for d in ("logs", "clean", "corrupt", "workspaces"):
        shutil.rmtree(os.path.join(DR, d), ignore_errors=True)
    src = open(os.path.join(REF, "ref_extract_werk.py"), encoding="utf-8").read()
    with open(os.path.join(REF, "ref_extract_werk_obj.py"), "w", encoding="utf-8", newline="\n") as f:
        f.write(src.replace('os.environ.get("REF_MESH_AS", "glb")', '"obj"'))

    pend = lambda r: ("PENDING, C1/C4/C5 PASS",
                      "%s %s" % (r["verdict"], clauses(r)),
                      r["verdict"] == "PENDING" and all(
                          r["clauses"][k]["result"] == "PASS" for k in ("C1", "C4", "C5")))
    passed = lambda r: ("PASS", "%s %s" % (r["verdict"], clauses(r)), r["verdict"] == "PASS")
    human = ["--human", "C2=PASS", "--human", "C3=PASS"]

    # 1. werk reference extractions, clean-dir re-run
    for payload in ("sound", "texture"):
        base = ["--format", "werk", "--payload", payload, "--rundir", REF,
                "--rerun", "--prog", "ref_extract_werk.py"]
        run("1-werk-ref-%s" % payload,
            base + ["--out", os.path.join(DR, "clean", "werk-ref-" + payload)], pend)
        run("1-werk-ref-%s-ruled" % payload,
            base + ["--out", os.path.join(DR, "clean", "werk-ref-" + payload + "-ruled")] + human,
            passed)
    run("1-werk-ref-objdump",
        ["--format", "werk", "--payload", "sound", "--rundir", REF, "--rerun",
         "--prog", "ref_extract_werk_obj.py", "--out", os.path.join(DR, "clean", "werk-ref-obj")]
        + human,
        lambda r: ("PASS with mesh via T2-VALUES (OBJ text dump)",
                   "%s mesh=%s" % (r["verdict"], r["clauses"]["C5"]["per_class"]["mesh"]),
                   r["verdict"] == "PASS" and "T2-VALUES" in r["clauses"]["C5"]["per_class"]["mesh"]))

    # 1b. glTF reference extraction (the built fixture: .gltf + .bin + .png)
    GL = ["--format", "gltf", "--allow-provisional"]
    HUMAN_H = ["--human", "C2=PASS", "--human", "C3=PASS-honest"]
    c5 = lambda r, c: r["clauses"]["C5"]["per_class"].get(c, "")
    gbase = GL + ["--payload", "texture", "--rundir", REF, "--rerun", "--prog", "ref_extract_gltf.py"]
    run("1-gltf-ref-texture", gbase + ["--out", os.path.join(DR, "clean", "gltf-ref-texture")], pend)
    run("1-gltf-ref-texture-ruled",
        gbase + ["--out", os.path.join(DR, "clean", "gltf-ref-texture-ruled")] + HUMAN_H,
        lambda r: ("PASS; mesh T1 (.bin) + T2-VALUES (OBJ), texture T1",
                   "%s mesh=%s | texture=%s" % (r["verdict"], c5(r, "mesh"), c5(r, "texture")),
                   r["verdict"] == "PASS" and "[T1]" in c5(r, "mesh")
                   and "T2-VALUES" in c5(r, "mesh") and "[T1]" in c5(r, "texture")))
    run("1-gltf-ref-sound-NA-ruled",
        GL + ["--payload", "sound", "--rundir", REF, "--rerun", "--prog", "ref_extract_gltf.py",
              "--out", os.path.join(DR, "clean", "gltf-ref-sound")] + HUMAN_H,
        lambda r: ("PASS on mesh only, sound N/A",
                   "%s na=%s %s" % (r["verdict"], r["second_payload_na"], clauses(r)),
                   r["verdict"] == "PASS" and r["second_payload_na"]))

    # 2. corrupted copies, graded without re-run (as a run dir)
    good = os.path.join(DR, "clean", "werk-ref-sound")
    c1 = os.path.join(DR, "corrupt", "werk-wav-byteflip")
    shutil.copytree(good, c1)
    wav = os.path.join(c1, "out", "crate-impact-hard-surface.wav")
    flip(wav, os.path.getsize(wav) // 2)
    c5fail = lambda cls: (lambda r: (
        "C5 FAIL (%s mismatch), verdict PARTIAL" % cls,
        "%s C5=%s %s=%s" % (r["verdict"], r["clauses"]["C5"]["result"], cls,
                            r["clauses"]["C5"]["per_class"][cls]),
        r["clauses"]["C5"]["result"] == "FAIL"
        and r["clauses"]["C5"]["per_class"][cls].startswith("FAIL")))
    run("2-werk-corrupt-wav", ["--format", "werk", "--payload", "sound", "--rundir", c1] + human,
        c5fail("sound"))

    c2 = os.path.join(DR, "corrupt", "werk-glb-byteflip-in-positions")
    shutil.copytree(good, c2)
    glbp = os.path.join(c2, "out", "game.glb")
    with open(glbp, "rb") as f:
        b = f.read()
    jl = int.from_bytes(b[12:16], "little")
    bin0 = 20 + jl + 8
    flip(glbp, bin0 + 4896 + 1)  # inside POSITION bufferView (byteOffset 4896)
    run("2-werk-corrupt-glb", ["--format", "werk", "--payload", "sound", "--rundir", c2] + human,
        c5fail("mesh"))

    ggood = os.path.join(DR, "clean", "gltf-ref-texture-ruled")
    c3 = os.path.join(DR, "corrupt", "gltf-png-byteflip")
    shutil.copytree(ggood, c3)
    png = os.path.join(c3, "out", "crate_diffuse.png")
    flip(png, os.path.getsize(png) // 2)
    run("2-gltf-corrupt-png", GL + ["--payload", "texture", "--rundir", c3] + HUMAN_H,
        lambda r: ("C5 FAIL (texture mismatch), verdict PARTIAL (mesh still exact)",
                   "%s C5=%s texture=%s" % (r["verdict"], r["clauses"]["C5"]["result"], c5(r, "texture")),
                   r["clauses"]["C5"]["result"] == "FAIL" and c5(r, "texture").startswith("FAIL")
                   and r["verdict"] == "PARTIAL"))

    c4 = os.path.join(DR, "corrupt", "gltf-bin-byteflip-no-obj")
    shutil.copytree(ggood, c4)
    os.remove(os.path.join(c4, "out", "crate.obj"))
    flip(os.path.join(c4, "out", "crate-nc-v1.bin"), 100)
    run("2-gltf-corrupt-bin", GL + ["--payload", "texture", "--rundir", c4] + HUMAN_H,
        lambda r: ("C5 FAIL (mesh mismatch), verdict PARTIAL (texture still exact)",
                   "%s C5=%s mesh=%s" % (r["verdict"], r["clauses"]["C5"]["result"], c5(r, "mesh")),
                   r["clauses"]["C5"]["result"] == "FAIL" and c5(r, "mesh").startswith("FAIL")
                   and r["verdict"] == "PARTIAL"))

    c5d = os.path.join(DR, "corrupt", "gltf-input-only")
    os.makedirs(c5d)
    for ff in EXP["formats"]["gltf"]["fixture_files"]:
        shutil.copy2(os.path.join(REPO, ff["path"]), os.path.join(c5d, ff["name"]))
    run("2-gltf-input-only", GL + ["--payload", "texture", "--rundir", c5d] + HUMAN_H,
        lambda r: ("FAIL (inputs at their own paths are not extractions, R4)",
                   "%s (%s)" % (r["verdict"], r["verdict_reason"]), r["verdict"] == "FAIL"))

    # 3. echo rule on generated agent workspaces
    wsroot = os.path.join(DR, "workspaces")
    werk = EXP["formats"]["werk"]["fixture_files"][0]
    for payload in ("sound", "texture"):
        ws = os.path.join(wsroot, "werk-" + payload)
        os.makedirs(ws)
        shutil.copy2(os.path.join(REPO, werk["path"]), ws)
        shutil.copy2(os.path.join(HERE, "prompts", payload, "PROMPT-werk.txt"),
                     os.path.join(ws, "PROMPT.txt"))
        run("3-echo-werk-" + payload, ["--format", "werk", "--echo-check", ws],
            lambda r: ("PASS (MANIFEST self-declared hashes allowed, no leaks)",
                       "%s leaks=%d self-declared=%d" % (r["result"], len(r["leaks"]),
                                                         r["allowed_self_declared"]),
                       r["result"] == "PASS"))
    for payload in ("sound", "texture"):
        ws = os.path.join(wsroot, "gltf-" + payload)
        os.makedirs(ws)
        for ff in EXP["formats"]["gltf"]["fixture_files"]:
            shutil.copy2(os.path.join(REPO, ff["path"]), os.path.join(ws, ff["name"]))
        shutil.copy2(os.path.join(HERE, "prompts", payload, "PROMPT-gltf.txt"),
                     os.path.join(ws, "PROMPT.txt"))
        assert sorted(os.listdir(ws)) == ["PROMPT.txt", "crate-nc-v1.bin", "crate-nc-v1.gltf",
                                          "crate_diffuse.png"]
        run("3-echo-gltf-%s" % payload,
            ["--format", "gltf", "--allow-provisional", "--echo-check", ws],
            lambda r: ("PASS (no leaks)", "%s leaks=%d" % (r["result"], len(r["leaks"])),
                       r["result"] == "PASS"))
    ws = os.path.join(wsroot, "SELFTEST-gltf-planted-leak")
    shutil.copytree(os.path.join(wsroot, "gltf-texture"), ws)
    with open(os.path.join(ws, "PROMPT.txt"), "a", encoding="utf-8") as f:
        f.write("\n" + EXP["formats"]["gltf"]["tier2_mesh"]["dump_sha256"] + "\n")
    run("3-echo-gltf-SELFTEST-planted-leak",
        ["--format", "gltf", "--allow-provisional", "--echo-check", ws],
        lambda r: ("FAIL (planted leak detected)", "%s leaks=%d" % (r["result"], len(r["leaks"])),
                   r["result"] == "FAIL"))
    # self-test: plant the tier2 dump sha in a prompt copy; must be caught
    ws = os.path.join(wsroot, "SELFTEST-planted-leak")
    shutil.copytree(os.path.join(wsroot, "werk-sound"), ws)
    with open(os.path.join(ws, "PROMPT.txt"), "a", encoding="utf-8") as f:
        f.write("\n" + EXP["formats"]["werk"]["tier2_mesh"]["dump_sha256"] + "\n")
    run("3-echo-SELFTEST-planted-leak", ["--format", "werk", "--echo-check", ws],
        lambda r: ("FAIL (planted leak detected)", "%s leaks=%d" % (r["result"], len(r["leaks"])),
                   r["result"] == "FAIL"))
    # also: the generated prompt files themselves
    for payload in ("sound", "texture"):
        run("3-echo-prompts-" + payload,
            ["--format", "werk", "--echo-check", os.path.join(HERE, "prompts", payload)],
            lambda r: ("PASS", "%s leaks=%d" % (r["result"], len(r["leaks"])), r["result"] == "PASS"))

    w = max(len(t) for t, *_ in results)
    lines = ["roundNC dry-run summary (grade_nc.py instrument check, plan 5.7)", ""]
    for t, e, g, ok in results:
        lines.append("%-4s %-*s  expected: %s" % ("OK" if ok else "BAD", w, t, e))
        lines.append("     %-*s  observed: %s" % (w, "", g))
    nbad = sum(1 for r in results if not r[3])
    lines += ["", "checks: %d   as expected: %d   unexpected: %d" % (len(results), len(results) - nbad, nbad)]
    txt = "\n".join(lines) + "\n"
    with open(os.path.join(DR, "SUMMARY.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(txt)
    print(txt)
    sys.exit(1 if nbad else 0)


if __name__ == "__main__":
    main()
