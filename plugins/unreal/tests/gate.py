#!/usr/bin/env python3
"""gate.py -- the W5c WerkLink gate on Unreal Engine 5.8, against the werk release.

    py -3.12 tests/gate.py --repo <werk release repo> --libs <werk libs dir>
        [--engine "C:/Program Files/Epic Games/UE_5.8"]
        [--project project/WerkGate/WerkGate.uproject] [--skip-commandlet]

Three parts, every clause printed as PASS / FAIL (a reader that could not run
is NOT-RUN, never PASS):

 A. standalone core (tests/build_gate.bat, MSVC): werk_gate.exe selftests --
    including the dangling-edge guard -- plus a real read of crate-v1 and its
    damaged twin.
 B. the commandlet round trip (tests/roundtrip_gate.py, rebaselined from the
    fixture manifests), as its own subprocess.
 C. the Python path: `UnrealEditor-Cmd -run=pythonscript` runs
    tests/ue_python_gate.py, which imports EVERY 3d-entity/1 fixture in
    <repo>/fixtures through `unreal.WerkLinkScripting`, exports what each
    import created, and re-imports the export. Here each import is checked
    against the release reader (exit status, node count, files verified derived
    from the manifest), and every export is verified by every release reader
    (tests/readers.py) and checked for edges to absent nodes.

Writes _gate_out/gate.json and prints the summary. Exit 0 only if no FAIL.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(PLUGIN, "vendor"))
import readers                                  # noqa: E402
import werk_single as werklib                   # noqa: E402

RESULTS = []


def clause(part, name, ok, detail):
    word = "NOT-RUN" if ok is None else ("PASS" if ok else "FAIL")
    RESULTS.append({"part": part, "clause": name, "result": word, "detail": detail})
    print("[%s] %-46s %s" % (word, name, detail))
    sys.stdout.flush()


def derived(path):
    pkg = werklib.open(path)
    files = 0
    for n in pkg.nodes:
        if n.status == "dead" or n.resolved is None:
            continue
        ver = [v for v in n.versions if v.get("v") == n.resolved]
        files += len(ver[0]["files"]) if ver else 0
    return pkg.verdict()["exit"], len(pkg.nodes), files


def part_a(repo):
    print("\n== A. standalone core (MSVC) ==")
    p = subprocess.run(["cmd", "/c", os.path.join(HERE, "build_gate.bat")],
                       capture_output=True, text=True)
    exe = os.path.join(HERE, ".build", "werk_gate.exe")
    if p.returncode != 0 or not os.path.isfile(exe):
        clause("A", "build werk_gate.exe", False, (p.stdout + p.stderr)[-300:])
        return
    clause("A", "build werk_gate.exe", True, "cl /std:c++17 /W4 /WX, exit 0")
    fx = os.path.join(repo, "fixtures")
    p = subprocess.run([exe, os.path.join(fx, "crate-v1.werk"), os.path.join(fx, "crate-v1-damaged.werk")],
                       capture_output=True, text=True)
    lines = p.stdout.splitlines()
    for l in lines:
        if l.startswith("[PASS]") or l.startswith("[FAIL]"):
            clause("A", "werk_gate: " + l[7:41].strip(), l.startswith("[PASS]"), l[41:].strip())
    clause("A", "werk_gate exit status", p.returncode == 0,
           "exit %d; %s" % (p.returncode, next((l for l in lines if " PASS, " in l), "")))
    # the deflate reader (added in this release copy): every file of the
    # method-8 fixture must inflate AND hash to its manifest sha256
    p = subprocess.run([exe, os.path.join(fx, "crate-cc0-lean-v1-deflated.werk")],
                       capture_output=True, text=True)
    line = next((l for l in p.stdout.splitlines() if "package open + verify" in l), "")
    clause("A", "werk_gate: deflated fixture (method 8)", p.returncode == 0 and line.startswith("[PASS]"),
           "exit %d; %s" % (p.returncode, line[41:].strip() or p.stdout.strip()[-160:]))


def part_a2(args):
    print("\n== A2. release-fixes reader rules: WerkLink core vs python -m werk vs werkc ==")
    p = subprocess.run([sys.executable, os.path.join(HERE, "agree_release_fixes.py"), "--repo", args.repo,
                        "--libs", args.libs, "--out", os.path.join(args.out, "agree")],
                       capture_output=True, text=True)
    for l in p.stdout.splitlines():
        if l.startswith("[PASS]") or l.startswith("[FAIL]"):
            clause("A2", "agree: " + l[7:39].strip(), l.startswith("[PASS]"), l[39:].strip())
    clause("A2", "agree_release_fixes.py exit status", p.returncode == 0,
           "exit %d; %s" % (p.returncode, (p.stdout.strip().splitlines() or [p.stderr[-200:]])[-1]))


def part_b(args):
    print("\n== B. commandlet round trip (roundtrip_gate.py) ==")
    log = os.path.join(args.out, "commandlet_gate.txt")
    cmd = [sys.executable, "-u", os.path.join(HERE, "roundtrip_gate.py"), "--repo", args.repo,
           "--engine", args.engine, "--project", args.project,
           "--logs", os.path.join(args.out, "commandlet", "logs"),
           "--out", os.path.join(args.out, "commandlet", "roundtrip")]
    with open(log, "w", encoding="utf-8") as fh:
        p = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, text=True)
    text = open(log, encoding="utf-8").read()
    print(text)
    for l in text.splitlines():
        if l.startswith("[PASS]") or l.startswith("[FAIL]"):
            clause("B", l[7:45].strip(), l.startswith("[PASS]"), l[45:].strip()[:200])
        elif l.startswith("[SKIP]"):
            clause("B", l[7:45].strip(), None, l[45:].strip()[:200])
    clause("B", "roundtrip_gate.py exit status", p.returncode == 0, "exit %d" % p.returncode)


def part_c(args):
    print("\n== C. Python path (-run=pythonscript, unreal.WerkLinkScripting) ==")
    fxdir = os.path.join(args.repo, "fixtures")
    fixtures = []
    for f in sorted(os.listdir(fxdir)):
        if not f.endswith(".werk"):
            continue
        with zipfile.ZipFile(os.path.join(fxdir, f)) as z:
            prof = json.loads(z.read("MANIFEST.json")).get("profile")
        if prof == "3d-entity/1":
            fixtures.append({"name": f[:-5], "path": os.path.join(fxdir, f).replace("\\", "/")})
    print("3d-entity/1 fixtures: %d (%s)" % (len(fixtures), ", ".join(x["name"] for x in fixtures)))

    pdir = os.path.join(args.out, "python")
    expdir = os.path.join(pdir, "exports")
    os.makedirs(expdir, exist_ok=True)
    content = os.path.join(os.path.dirname(args.project), "Content")
    for sub in ("WerkPy", "WerkPyRT"):
        d = os.path.join(content, sub)
        if os.path.isdir(d):
            shutil.rmtree(d)
    job = {"fixtures": fixtures, "spec": args.repo.replace("\\", "/"),
           "out_dir": expdir.replace("\\", "/"),
           "result": os.path.join(pdir, "ue_result.json").replace("\\", "/")}
    if os.path.isfile(job["result"]):
        os.remove(job["result"])
    jobfile = os.path.join(pdir, "job.json")
    json.dump(job, open(jobfile, "w", encoding="utf-8"), indent=1)

    exe = os.path.join(args.engine, "Engine", "Binaries", "Win64", "UnrealEditor-Cmd.exe")
    env = dict(os.environ)
    env["WERK_UE_JOB"] = jobfile
    cmd = [exe, args.project, "-run=pythonscript",
           "-script=%s" % os.path.join(HERE, "ue_python_gate.py").replace("\\", "/"),
           "-unattended", "-nopause", "-nosplash", "-nullrhi", "-stdout", "-nop4"]
    t0 = time.time()
    with open(os.path.join(pdir, "ue.log"), "wb") as fh:
        p = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, env=env, timeout=7200)
    secs = time.time() - t0
    ok = os.path.isfile(job["result"])
    clause("C", "UnrealEditor-Cmd -run=pythonscript", ok and p.returncode == 0,
           "exit %d, %.0f s, result file %s" % (p.returncode, secs, "written" if ok else "MISSING"))
    if not ok:
        return
    res = json.load(open(job["result"], encoding="utf-8"))
    if res.get("error"):
        clause("C", "in-editor script", False, res["error"][-300:])
        return
    print("engine reported by the editor: %s" % res.get("engine"))
    R = readers.Readers(args.libs, os.path.join(args.repo, "loaders"), os.path.join(args.out, "bin"),
                        os.path.join(PLUGIN, "vendor", "werk_single.py"))
    for n in R.build_notes:
        print("  " + n)
    for row in res["fixtures"]:
        name = row["name"]
        if row.get("exception"):
            clause("C", "%s: script" % name, False, row["exception"].strip().splitlines()[-1])
            continue
        want_exit, want_nodes, want_files = derived(row["path"])
        imp = row["import"]
        clause("C", "%s: import" % name,
               imp["exit"] == want_exit and imp["nodes"] == want_nodes
               and imp["files_verified"] == want_files,
               "exit %d (reader %d), %d nodes (manifest %d), %d files verified (derived %d); "
               "%d imported, %d skipped, %d refused, %d assets; %.1f s" % (
                   imp["exit"], want_exit, imp["nodes"], want_nodes, imp["files_verified"],
                   want_files, imp["imported"], imp["skipped"], imp["refused"], imp["assets"],
                   row.get("import_seconds", 0)))
        if not imp.get("created_assets"):
            clause("C", "%s: export" % name, None,
                   "the import created no assets (nothing to export): outcomes %s" % sorted(
                       {o["outcome"] for o in imp["outcomes"]}))
            continue
        exp = row.get("export") or {}
        out = exp.get("file", "")
        clause("C", "%s: export" % name, exp.get("exit") == 0 and os.path.isfile(out),
               "exit %s, %s" % (exp.get("exit"), exp.get("summary") or exp.get("error")))
        if not os.path.isfile(out):
            continue
        for rname, rok, detail in R.check(out, 0):
            clause("C", "%s: verify %s" % (name, rname), rok, detail)
        with zipfile.ZipFile(out) as z:
            man = json.loads(z.read("MANIFEST.json"))
        ids = {n["node_id"] for n in man["nodes"]}
        edges = [(n["node_id"], e.get("kind"), e.get("to")) for n in man["nodes"]
                 for e in n.get("edges") or []]
        dangling = [e for e in edges if e[2] not in ids]
        clause("C", "%s: no edge to an absent node" % name, not dangling,
               "%d edge(s) written, %d dangling%s" % (len(edges), len(dangling),
                                                     (": %s" % dangling) if dangling else ""))
        rt = row.get("reimport") or {}
        clause("C", "%s: re-import of the export" % name, rt.get("exit") == 0,
               "exit %s, %s" % (rt.get("exit"), rt.get("summary") or rt.get("error")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--libs", required=True)
    ap.add_argument("--engine", default="C:/Program Files/Epic Games/UE_5.8")
    ap.add_argument("--project", default=os.path.join(PLUGIN, "project", "WerkGate", "WerkGate.uproject"))
    ap.add_argument("--out", default=os.path.join(PLUGIN, "_gate_out"))
    ap.add_argument("--skip-commandlet", action="store_true")
    ap.add_argument("--parts", default="ABC")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    bundle = json.load(open(os.path.join(args.libs, "bundle", "bundle.json"), encoding="utf-8"))
    vend = os.path.join(PLUGIN, "vendor", "werk_single.py")
    import hashlib
    print("werk W5c WerkLink gate")
    print("engine  : %s" % args.engine)
    print("project : %s" % args.project)
    print("repo    : %s" % args.repo)
    print("libs    : lib_version %s, bundle source_rev %s" % (bundle.get("lib_version"), bundle.get("source_rev")))
    print("vendored werk_single.py sha256 %s" % hashlib.sha256(open(vend, "rb").read()).hexdigest())
    t0 = time.time()
    if "A" in args.parts:
        part_a(args.repo)
        part_a2(args)
    if "B" in args.parts and not args.skip_commandlet:
        part_b(args)
    if "C" in args.parts:
        part_c(args)
    counts = {w: sum(1 for r in RESULTS if r["result"] == w) for w in ("PASS", "FAIL", "NOT-RUN")}
    print("\n%d PASS, %d FAIL, %d NOT-RUN  (%.0f s)" % (counts["PASS"], counts["FAIL"], counts["NOT-RUN"],
                                                       time.time() - t0))
    json.dump({"bundle_source_rev": bundle.get("source_rev"), "lib_version": bundle.get("lib_version"),
               "engine": args.engine, "counts": counts, "clauses": RESULTS},
              open(os.path.join(args.out, "gate.json"), "w", encoding="utf-8"), indent=1)
    print("GATE: %s" % ("PASSED" if counts["FAIL"] == 0 else "FAILED"))
    return 0 if counts["FAIL"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
