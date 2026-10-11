# Dump every tool call and its result for one roundNC trial.
import json, sys
B = r"D:/gauntlet-sealed/config/projects"
T = r"D:/gauntlet-sealed/nc-20261011-1543"
trial = sys.argv[1]
full = len(sys.argv) > 2
sid = json.load(open(T + "/" + trial + "/_agent-stdout.txt", encoding="utf-8"))["session_id"]
p = B + "/D--gauntlet-sealed-nc-20261011-1543-%s/%s.jsonl" % (trial, sid)
results = {}
calls = []
types = {}
for line in open(p, encoding="utf-8"):
    d = json.loads(line)
    types[d.get("type")] = types.get(d.get("type"), 0) + 1
    m = d.get("message")
    if not isinstance(m, dict): continue
    c = m.get("content")
    if not isinstance(c, list): continue
    for b in c:
        if b.get("type") == "tool_use":
            calls.append((d.get("timestamp"), b["id"], b["name"], b["input"]))
        elif b.get("type") == "tool_result":
            cont = b.get("content")
            if isinstance(cont, list):
                cont = " ".join(x.get("text", "") for x in cont if isinstance(x, dict))
            results[b["tool_use_id"]] = (b.get("is_error"), str(cont))
print("session", sid, "types", types)
for i, (ts, tid, name, inp) in enumerate(calls):
    err, res = results.get(tid, (None, "<no result>"))
    s = {k: (v if (full or k not in ("content", "new_string", "old_string")) else "<%d chars>" % len(v)) for k, v in inp.items()}
    lim = 100000 if full else 700
    print("#%02d %s %s %s" % (i, ts[11:19] if ts else "", name, json.dumps(s, ensure_ascii=True)[:lim]))
    print("     -> err=%s %s" % (err, res[:(3000 if full else 400)].replace("\n", " | ").encode("ascii", "replace").decode()))
