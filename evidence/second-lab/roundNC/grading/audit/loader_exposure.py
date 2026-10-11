# Count unique 40+ char lines of the bundled loaders (from the frozen fixture) that appear in
# tool results of each werk transcript, and verbatim in each final program.
import json, zipfile
W = r"D:\werk\nc-grading\frozen-504a9ac\gauntlet\roundOW\mini-v1.werk"
z = zipfile.ZipFile(W)
spec = "".join(z.read(n).decode("utf-8", "replace") for n in z.namelist() if n.startswith("spec/") or n.endswith((".txt", ".md", ".json")))
lines = {}
for n in z.namelist():
    if n.startswith("loaders/"):
        s = set(l.strip() for l in z.read(n).decode("utf-8", "replace").splitlines())
        lines[n] = {l for l in s if len(l) >= 40 and l not in spec}
T = r"D:/gauntlet-sealed/nc-20261011-1543"
PROG = {"werk-t1": "werk_reader.py", "werk-t2": "werkread.py", "werk-t3": "werk_reader.py"}
for t, prog in PROG.items():
    sid = json.load(open(T + "/" + t + "/_agent-stdout.txt", encoding="utf-8"))["session_id"]
    p = r"D:/gauntlet-sealed/config/projects/D--gauntlet-sealed-nc-20261011-1543-%s/%s.jsonl" % (t, sid)
    res = ""
    for l in open(p, encoding="utf-8"):
        d = json.loads(l); m = d.get("message")
        if isinstance(m, dict) and isinstance(m.get("content"), list):
            for b in m["content"]:
                if b.get("type") == "tool_result":
                    c = b.get("content"); res += (c if isinstance(c, str) else json.dumps(c)) + "\n"
    src = open(T + "/" + t + "/" + prog, encoding="utf-8", errors="replace").read()
    print(t, {n.split("/")[-1]: (len(ls), sum(1 for x in ls if x in res), sum(1 for x in ls if x in src)) for n, ls in lines.items()}, "(unique lines, in tool results, in program)")
