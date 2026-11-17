# Show per-version notes, input_files/params, meta, for each node.
import sys, zipfile, json
z = zipfile.ZipFile(sys.argv[1])
sys.stdout.reconfigure(encoding='utf-8')
m = json.loads(z.read('MANIFEST.json'))
for n in m['nodes']:
    print('==', n['node_id'], n['type'], 'meta=' + json.dumps(n.get('meta'))[:400])
    for v in n['versions']:
        extra = {k: v[k] for k in v if k not in ('files', 'note')}
        print('   note:', v.get('note', '')[:300])
        print('   ', json.dumps(extra)[:600])
