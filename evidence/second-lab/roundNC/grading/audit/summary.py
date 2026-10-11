import json, os
T = r"D:/gauntlet-sealed/nc-20261011-1543"
P = r"D:/gauntlet-sealed/config/projects"
for t in ["seal-check"] + ["%s-t%d" % (a, i) for i in (1, 2, 3) for a in ("werk", "fbx", "gltf", "usdz")]:
    d = json.load(open(T + "/" + t + "/_agent-stdout.txt", encoding="utf-8"))
    sid = d["session_id"]
    jp = P + "/D--gauntlet-sealed-nc-20261011-1543-%s/%s.jsonl" % (t, sid)
    proj = os.listdir(P + "/D--gauntlet-sealed-nc-20261011-1543-%s" % t)
    models = {k: (v["inputTokens"], v["outputTokens"], round(v["costUSD"], 4)) for k, v in d["modelUsage"].items()}
    print(t, sid, "cost=%.3f" % d["total_cost_usd"], "turns=%d" % d["num_turns"], "dur=%.1f" % (d["duration_ms"]/1000),
          "err=%s" % d["is_error"], "sub=%s" % d["subtype"], "denials=%d" % len(d["permission_denials"]),
          "web=%s" % d["usage"]["server_tool_use"], "jsonl=%s" % os.path.exists(jp), "projfiles=%s" % proj)
    print("    models", models)
