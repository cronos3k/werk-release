"""Make damaged COPIES of the package and run werk_open.py on each.
The original file is opened read-only and never written."""
import os, subprocess, sys, zipfile

src = sys.argv[1]
os.makedirs('damage', exist_ok=True)
orig = open(src, 'rb').read()
z = zipfile.ZipFile(src)


def data_off(name):
    i = z.getinfo(name)
    n, m = int.from_bytes(orig[i.header_offset + 26:i.header_offset + 28], 'little'), \
        int.from_bytes(orig[i.header_offset + 28:i.header_offset + 30], 'little')
    return i.header_offset + 30 + n + m


cases = {}
b = bytearray(orig); o = data_off('geometry/game.glb') + 2000; b[o] ^= 0xFF
cases['glb-byte-flip'] = b
b = bytearray(orig); o = data_off('MANIFEST.json'); s = orig[o:o + 23311]
k = s.find(b'"Wooden crate (small-context fixture)"'); b[o + k + 1] = ord('w')
cases['manifest-edit'] = b
b = bytearray(orig); o = data_off('poses/rest.wkrp') + 0x190 + 24; b[o] ^= 0x01
cases['wkrp-flip'] = b
cases['truncated'] = bytearray(orig[:500000])

for name, blob in cases.items():
    p = os.path.join('damage', name + '.werk')
    open(p, 'wb').write(blob)
    r = subprocess.run([sys.executable, '-I', 'werk_open.py', p, os.path.join('damage', name + '-out')],
                       capture_output=True, text=True, encoding='utf-8')
    lines = [l for l in r.stdout.splitlines() if l.startswith('  error') or l.startswith('[4]')
             or 'exit status' in l or 'DEAD' in l or 'MISMATCH' in l]
    print('=== %s -> exit %d' % (name, r.returncode))
    for l in lines:
        print('   ', l[:170])
