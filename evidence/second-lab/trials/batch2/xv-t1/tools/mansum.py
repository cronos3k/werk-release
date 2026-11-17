# Summarise MANIFEST.json from the container without dumping all of it.
import sys, zipfile, json
z = zipfile.ZipFile(sys.argv[1])
sys.stdout.reconfigure(encoding='utf-8')
m = json.loads(z.read('MANIFEST.json'))
for k, v in m.items():
    if k == 'nodes':
        print('nodes: %d' % len(v))
    else:
        print(k, '=', json.dumps(v, ensure_ascii=False)[:1500])
print()
for n in m['nodes']:
    vs = n['versions']
    print('%-40s %-24s active=%s vers=%s part=%s mat=%s edges=%s' % (n['node_id'], n['type'], n.get('active'), [x['v'] for x in vs], n.get('part_id'), n.get('material_id'), [(e['to'], e['kind'], e.get('role')) for e in n.get('edges', [])]))
    for ver in vs:
        print('    v%s payload_file=%s epi=%s files=%s' % (ver['v'], ver.get('payload_file'), ver.get('epistemic'), [(f['path'], f.get('role')) for f in ver['files']] if len(ver['files']) < 8 else '%d files' % len(ver['files'])))
