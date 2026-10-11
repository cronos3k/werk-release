# Flag every tool call whose input names a path outside the trial directory; list web/skill/agent calls.
import json, re, collections
T = r"D:/gauntlet-sealed/nc-20261011-1543"
TR = ["%s-t%d" % (a, i) for i in (1, 2, 3) for a in ("werk", "fbx", "gltf", "usdz")]
for t in TR:
    sid = json.load(open(T + "/" + t + "/_agent-stdout.txt", encoding="utf-8"))["session_id"]
    p = r"D:/gauntlet-sealed/config/projects/D--gauntlet-sealed-nc-20261011-1543-%s/%s.jsonl" % (t, sid)
    root = ("d:/gauntlet-sealed/nc-20261011-1543/" + t).lower()
    lines = [json.loads(l) for l in open(p, encoding="utf-8")]
    res = {}
    for d in lines:
        m = d.get("message")
        if isinstance(m, dict) and isinstance(m.get("content"), list):
            for b in m["content"]:
                if b.get("type") == "tool_result":
                    c = b.get("content"); c = c if isinstance(c, str) else json.dumps(c)
                    res[b["tool_use_id"]] = (b.get("is_error"), c[:160])
    n = 0; names = collections.Counter(); flagged = []; web = []; special = []; errs = 0
    for d in lines:
        m = d.get("message")
        if not (isinstance(m, dict) and isinstance(m.get("content"), list)): continue
        for b in m["content"]:
            if b.get("type") != "tool_use": continue
            n += 1; name, inp = b["name"], b["input"]; names[name] += 1
            s = json.dumps(inp)
            if name in ("WebFetch", "WebSearch") or re.search(r"https?://", s if name not in ("Write","Edit") else ""): web.append((name, s[:200]))
            if name not in ("Bash","PowerShell","Read","Write","Edit","Glob","Grep"): special.append(name)
            cands = []
            for k in ("file_path", "path"):
                if k in inp: cands.append(inp[k])
            if "command" in inp:
                cands += re.findall(r"(?:[A-Za-z]:[\/][^\s\"';|&>]*|/[a-z]/[^\s\"';|&>]+|/(?:dev|tmp|etc|home|usr|proc)[^\s\"';|&>]*|\.\.[\/][^\s\"';|&>]*|~[^\s\"';|&>]*)", inp["command"])
            for c in cands:
                cl = c.replace("\\", "/").lower()
                cl = re.sub(r"^/([a-z])/", r"\1:/", cl)
                if re.match(r"^[a-z]:/", cl) or cl.startswith(("/", "..", "~")):
                    if not cl.startswith(root):
                        e = res.get(b["id"], (None, ""))
                        flagged.append((name, c, "ERR" if e[0] else "ran", e[1][:120]))
    print("==", t, "tool calls:", n, dict(names), "| web:", web, "| other tools:", special)
    for f in flagged: print("   OUTSIDE:", f)
