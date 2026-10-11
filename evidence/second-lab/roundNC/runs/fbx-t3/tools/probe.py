import sys, hashlib, struct, zlib, collections
sys.path.insert(0, sys.argv[2])
from fbxpkg import FBX, mesh_of
f = FBX(sys.argv[1]); d = f.data
tail = d[f.body_end:]
print('trailer len', len(tail), 'body_end', hex(f.body_end), 'file len % 16', len(d) % 16)
foot1, foot2 = tail[:16], tail[-16:]
fid = f.top('FileId').props[0][1]
print('footer1', foot1.hex(), '\nfooter2', foot2.hex(), '\nFileId ', fid.hex())
cands = {'body': d[:f.body_end], 'all-but-footer': d[:-16], 'from27': d[27:f.body_end], 'all': d,
         'pre-foot1': d[:f.body_end]}
for k, b in cands.items():
    for alg in ('md5', 'sha1', 'sha256'):
        h = hashlib.new(alg, b).digest()
        for nm, t in (('foot1', foot1), ('foot2', foot2), ('fileid', fid)):
            if h[:16] == t:
                print('MATCH', k, alg, nm)
print('xor foot1^fileid', bytes(a ^ b for a, b in zip(foot1, fid)).hex())
objs = f.objects()
for oid, o in objs.items():
    if o.name == 'Geometry':
        m = mesh_of(f, o)
        sizes = collections.Counter(len(p) for p in m['polys'])
        v = m['v']; xs, ys, zs = v[0::3], v[1::3], v[2::3]
        print(m['name'], dict(sizes), 'bbox', (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs)))
