import sys, json
m = json.load(open(sys.argv[1], encoding='utf-8'))
for n in m['nodes']:
    if n['node_id'] in sys.argv[2:]:
        print(json.dumps(n, indent=1, ensure_ascii=False))
