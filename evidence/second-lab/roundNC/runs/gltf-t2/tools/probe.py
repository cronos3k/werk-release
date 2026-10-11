import hashlib, re, sys, os
d = sys.argv[1]
for f in ['crate-nc-v1.gltf', 'crate-nc-v1.bin', 'crate_diffuse.png']:
    b = open(os.path.join(d, f), 'rb').read()
    print(f, len(b), hashlib.sha256(b).hexdigest())
b = open(os.path.join(d, 'crate-nc-v1.bin'), 'rb').read()
print('bin tail', b[-64:].hex())
p = open(os.path.join(d, 'crate_diffuse.png'), 'rb').read()
print('png head', p[:64])
print('png tail', p[-48:])
for m in re.finditer(rb'[ -~]{6,}', p):
    print('png str', m.start(), m.group()[:80])
for m in re.finditer(rb'[ -~]{8,}', b):
    print('bin str', m.start(), m.group()[:80])
