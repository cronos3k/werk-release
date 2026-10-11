import sys, hashlib
p = sys.argv[1]
d = open(p, 'rb').read()
print('size', len(d), 'sha256', hashlib.sha256(d).hexdigest())
def hx(off, n):
    for i in range(off, min(off + n, len(d)), 16):
        b = d[i:i+16]
        print('%08x  %-48s %s' % (i, b.hex(' '), ''.join(chr(c) if 32 <= c < 127 else '.' for c in b)))
hx(0, 256)
print('...')
hx(max(0, len(d) - 512), 512)
