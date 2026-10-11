import sys, hashlib, zipfile, itertools, json
pkg = sys.argv[1]
z = zipfile.ZipFile(pkg)
names = [i.filename for i in z.infolist()]
print('zipfile entries', len(names), 'methods', {i.compress_type for i in z.infolist()})
print('zipfile testzip (CRC):', z.testzip())
raw = lambda p: hashlib.sha256(z.read(p)).digest()
target = '60e08ed15118810abfeeee57aa45a4bbbbc3e21d90c887debaff8bd585d496c8'
ins = ['geometry/game.glb', 'physics/bounds.json']
cands = {}
for perm in itertools.permutations(ins):
    for tail in (b'{}', b''):
        h = hashlib.sha256(b''.join(raw(p) for p in perm) + tail).hexdigest()
        cands['%s + %r' % (list(perm), tail)] = h
# single-input variants and hex variants
for p in ins:
    cands['%s only + {}' % p] = hashlib.sha256(raw(p) + b'{}').hexdigest()
cands['hex concat + {}'] = hashlib.sha256(''.join(hashlib.sha256(z.read(p)).hexdigest() for p in ins).encode() + b'{}').hexdigest()
for k, v in cands.items():
    print('MATCH' if v == target else '     ', k, v)
