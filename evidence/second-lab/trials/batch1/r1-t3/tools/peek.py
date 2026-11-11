import sys
p = sys.argv[1]
off = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0
n = int(sys.argv[3], 0) if len(sys.argv) > 3 else 512
d = open(p, 'rb').read()
if off < 0:
    off = len(d) + off
print('size', len(d))
chunk = d[off:off + n]
for i in range(0, len(chunk), 16):
    b = chunk[i:i + 16]
    print('%08x  %-48s  %s' % (off + i, b.hex(' '), ''.join(chr(c) if 32 <= c < 127 else '.' for c in b)))
