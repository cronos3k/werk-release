import sys, json
m = json.load(open(sys.argv[1], encoding='utf-8'))
for k, v in m.items():
    if k == 'nodes':
        continue
    s = json.dumps(v)
    print(k, '=', s[:600])
print('--- nodes', len(m['nodes']))
for n in m['nodes']:
    act = [v for v in n['versions'] if v['v'] == n['active']]
    print(n['node_id'], n['type'], 'active', n['active'], 'nver', len(n['versions']),
          'files', [len(v['files']) for v in n['versions']],
          'payload_file', [v.get('payload_file') for v in n['versions']],
          'edges', n.get('edges'))
