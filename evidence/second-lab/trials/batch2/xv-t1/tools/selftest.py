# 1) Ed25519 + message construction against spec/examples (MINI-SPECS 12.1 checkpoint)
# 2) build damaged COPIES of the package and show the reader's verdicts.
import sys, os, zipfile, hashlib, json, shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import werk_open as W

pkg = sys.argv[1]
work = sys.argv[2]
z = zipfile.ZipFile(pkg)
mex = z.read('spec/examples/MANIFEST.example.json')
sex = json.loads(z.read('spec/examples/SIGNATURE.example.json'))
e = sex['chain'][0]
msg = W.sig_message(e)
print('example manifest sha256', hashlib.sha256(mex).hexdigest(), '== entry', e['manifest_sha256'])
print('message len', len(msg), 'sha256', hashlib.sha256(msg).hexdigest(), '(spec checkpoint 203 / 11e260cc...)')
print('example chain verdict:', W.verify_chain(sex, mex))
print('selftest RFC vector:', W.ed25519_selftest())

os.makedirs(work, exist_ok=True)
data = open(pkg, 'rb').read()

def damaged(name, member, delta_off=100):
    info = z.getinfo(member)
    d = bytearray(data)
    lh = info.header_offset
    n = int.from_bytes(d[lh + 26:lh + 28], 'little'); m = int.from_bytes(d[lh + 28:lh + 30], 'little')
    off = lh + 30 + n + m + delta_off
    d[off] ^= 0x01   # keeps ASCII text ASCII, so a tampered MANIFEST still parses
    p = os.path.join(work, name)
    open(p, 'wb').write(bytes(d))
    return p

for name, member, off in (('glb-flip.werk', 'geometry/game.glb', 5000),
                          ('manifest-flip.werk', 'MANIFEST.json', 300),
                          ('wav-flip.werk', 'audio/sfx/crate-impact-hard-surface.wav', 2000)):
    p = damaged(name, member, off)
    W.REPORT.clear()
    print('\n######', name)
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = W.main(['x', p, os.path.join(work, 'out-' + name)])
    out = buf.getvalue()
    print('exit', rc)
    i = out.find('== primary')
    print(out[i:] if i >= 0 else out)
