import sys, zipfile, hashlib, itertools
z = zipfile.ZipFile(sys.argv[1])
want = '60e08ed15118810abfeeee57aa45a4bbbbc3e21d90c887debaff8bd585d496c8'
files = ['geometry/game.glb', 'physics/bounds.json', 'poses/rest.wkrp', 'spec/examples/restposes.example.wkrp']
raw = {f: hashlib.sha256(z.read(f)).digest() for f in files}
hexd = {f: hashlib.sha256(z.read(f)).hexdigest() for f in files}
for n in range(0, 3):
    for combo in itertools.permutations(files, n):
        for tail in (b'{}', b'', b'null'):
            for mode in ('raw', 'hex'):
                h = hashlib.sha256()
                for f in combo:
                    h.update(raw[f] if mode == 'raw' else hexd[f].encode())
                h.update(tail)
                if h.hexdigest() == want:
                    print('MATCH', combo, tail, mode)
print('done')
