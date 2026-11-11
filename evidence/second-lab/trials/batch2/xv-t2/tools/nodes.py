import json, sys
m = json.load(open(sys.argv[1], encoding="utf-8"))
if len(sys.argv) > 2:
    sys.stdout = open(sys.argv[2], "w", encoding="utf-8")
print("top keys:", list(m))
for k in m:
    if k not in ("nodes", "conventions", "entity", "schemas", "parts", "materials"):
        print(k, "=", json.dumps(m[k])[:300])
for n in m["nodes"]:
    print(f"\n== {n['node_id']}  [{n['type']}] active={n['active']} part={n.get('part_id')} edges={[(e['to'], e['kind'], e.get('role')) for e in n['edges']]}")
    if "meta" in n: print("   meta keys:", list(n["meta"]))
    for v in n["versions"]:
        extra = {k: v[k] for k in v if k not in ("files", "note", "producer", "created", "v", "epistemic")}
        print(f"   v{v['v']} {v['epistemic']} producer={v['producer']} {json.dumps(extra)[:250]}")
        print(f"   note: {v['note'][:200]}")
        for f in v["files"]:
            print(f"     - {f['path']} {f['size']} role={f.get('role')} {[k for k in f if k not in ('path','sha256','size','role')]}")
