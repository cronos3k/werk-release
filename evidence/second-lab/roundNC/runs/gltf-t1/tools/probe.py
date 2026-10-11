import hashlib, re, struct, sys, os

base = sys.argv[1]
d = open(os.path.join(base, 'crate_diffuse.png'), 'rb').read()
print(d[:8], len(d))
p = 8
while p < len(d):
    n, = struct.unpack('>I', d[p:p+4]); t = d[p+4:p+8]
    body = d[p+8:p+8+n]
    print(t, n, body[:80] if t != b'IDAT' else '')
    p += 12 + n
print('trailing', len(d) - p)
for f in ['crate-nc-v1.gltf', 'crate-nc-v1.bin', 'crate_diffuse.png']:
    print(f, hashlib.sha256(open(os.path.join(base, f), 'rb').read()).hexdigest())
b = open(os.path.join(base, 'crate-nc-v1.bin'), 'rb').read()
print(len(b), re.findall(rb'[ -~]{8,}', b)[:20])
