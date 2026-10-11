# Sensitivity only (amendment proposal A1): the frozen grader with a copy of expectations.json
# where accept_submesh_as_c5 = True for the controls. Same re-run wrappers, same human rulings.
import json, os, subprocess, sys
G = r"D:\werk\nc-grading\frozen-504a9ac\gauntlet\roundNC\grade_nc.py"
E = r"D:\werk\nc-grading\sensitivity\expectations.json"
T = r"D:\gauntlet-sealed\nc-20261011-1543"; N = r"D:\werk\nc-grading"
human = json.load(open(N + r"\audit\human_rulings.json"))
env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
for t in human:
    fmt = t.split("-")[0]
    if fmt == "werk": continue
    js = os.path.join(N, "logs", "sens-%s.json" % t)
    cmd = [sys.executable, G, "--format", fmt, "--payload", "texture", "--rundir", os.path.join(T, t),
           "--expectations", E, "--rerun", "--prog", os.path.join(N, "wrappers", "rerun_%s.py" % t),
           "--out", os.path.join(N, "sensitivity", "scratch", t), "--json", js]
    for h in human[t]: cmd += ["--human", h]
    p = subprocess.run(cmd, cwd=os.path.dirname(G), capture_output=True, env=env)
    open(os.path.join(N, "logs", "sens-%s.log" % t), "wb").write(p.stdout + b"\n--- stderr ---\n" + p.stderr)
    r = json.load(open(js)); c = r["clauses"]
    print(t, r["verdict"], c["C5"]["per_class"], r["verifiable_integrity_fraction"]["any_declared"], r["verifiable_integrity_fraction"]["cryptographic"])
