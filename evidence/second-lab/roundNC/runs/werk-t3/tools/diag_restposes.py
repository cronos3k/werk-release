"""Diagnose the rest-poses input_hash disagreement. Reads only the container."""
import sys, os, json, hashlib, itertools, zipfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import werk_reader as W

z = zipfile.ZipFile(sys.argv[1])
man = json.loads(z.read('MANIFEST.json'))
decl = {f['path']: f['sha256'] for n in man['nodes'] for v in n['versions'] for f in v['files']}
node = next(n for n in man['nodes'] if n['node_id'] == 'rest-poses')
v = node['versions'][0]
print('declared input_hash', v['input_hash'])
ins = v['input_files']
for order in itertools.permutations(ins):
    for mode in ('raw', 'hex'):
        for tail in (b'{}', b''):
            h = hashlib.sha256()
            for p in order:
                h.update(bytes.fromhex(decl[p]) if mode == 'raw' else decl[p].encode())
            h.update(tail)
            print(f'  {list(order)} {mode} tail={tail!r}: {h.hexdigest()}')
b = z.read('poses/rest.wkrp')
magic, ver, hdr, secs = W.read_envelope(b)
print('envelope header:')
for k, val in hdr.items():
    print('  ', k, '=', val)
print('identical to spec example:', b == z.read('spec/examples/restposes.example.wkrp'))
print('bounds.json:', z.read('physics/bounds.json').decode())
import struct
c = secs['contacts']
print('contacts:', [struct.unpack_from('<fff', c, 12 * i) for i in range(len(c) // 12)])
