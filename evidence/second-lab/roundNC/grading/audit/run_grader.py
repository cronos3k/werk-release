# Drive the frozen grade_nc.py (exported from 504a9ac, sha256 checked) over all 12 trials.
# mode committed : grade the committed run dir, no re-run
# mode literal   : --rerun with the agent program and NO argv (frozen grader as-is)
# mode rerun     : --rerun through the argv wrapper (deviation D1); optional --human rulings
import hashlib, json, os, subprocess, sys
G = r"D:\werk\nc-grading\frozen-504a9ac\gauntlet\roundNC\grade_nc.py"
assert hashlib.sha256(open(G, "rb").read()).hexdigest() == "23b6742e1070d0e5eedb4cab4ebfcdf19714e5e1f7c5f6abbdf7a206be20c163"
T = r"D:\gauntlet-sealed\nc-20261011-1543"
N = r"D:\werk\nc-grading"
PROG = {"werk-t1": "werk_reader.py", "werk-t2": "werkread.py", "werk-t3": "werk_reader.py",
        "fbx-t1": "fbx_extract.py", "fbx-t2": r"tools\crate_reader.py", "fbx-t3": r"tools\fbxpkg.py",
        "gltf-t1": r"tools\crate_reader.py", "gltf-t2": r"tools\crate_reader.py", "gltf-t3": "crate_reader.py",
        "usdz-t1": "crate_probe.py", "usdz-t2": "usdz_tool.py", "usdz-t3": r"tools\inspect_usdz.py"}
mode = sys.argv[1]
human = json.load(open(sys.argv[2])) if len(sys.argv) > 2 else {}
env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
for t in PROG:
    fmt = t.split("-")[0]
    cmd = [sys.executable, G, "--format", fmt, "--payload", "sound" if fmt == "werk" else "texture",
           "--rundir", os.path.join(T, t)]
    if mode == "literal":
        cmd += ["--rerun", "--prog", PROG[t], "--out", os.path.join(N, "scratch-literal", t)]
    elif mode == "rerun":
        cmd += ["--rerun", "--prog", os.path.join(N, "wrappers", "rerun_%s.py" % t), "--out", os.path.join(N, "scratch", t)]
    for h in human.get(t, []):
        cmd += ["--human", h]
    tag = mode + ("-ruled" if human else "")
    cmd += ["--json", os.path.join(N, "logs", "%s-%s.json" % (tag, t))]
    p = subprocess.run(cmd, cwd=os.path.dirname(G), capture_output=True, env=env)
    log = os.path.join(N, "logs", "%s-%s.log" % (tag, t))
    with open(log, "wb") as f:
        f.write(("$ " + " ".join(cmd) + "\n").encode())
        f.write(p.stdout); f.write(b"\n--- stderr ---\n"); f.write(p.stderr)
    try:
        r = json.load(open(os.path.join(N, "logs", "%s-%s.json" % (tag, t))))
        c = r["clauses"]
        print("%-8s exit=%s C1=%s C4=%s C5=%s [%s] verdict=%s vif=%s/%s" % (
            t, r["exit_code"], c["C1"]["result"], c["C4"]["result"], c["C5"]["result"],
            "; ".join("%s:%s" % (k, v[:60]) for k, v in c["C5"]["per_class"].items()),
            r["verdict"], r["verifiable_integrity_fraction"]["any_declared"],
            r["verifiable_integrity_fraction"]["cryptographic"]))
    except Exception as ex:
        print(t, "grader rc", p.returncode, ex)
