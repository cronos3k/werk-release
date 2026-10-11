import sys
p = sys.argv[1]
off = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0
n = int(sys.argv[3], 0) if len(sys.argv) > 3 else 1024
d = open(p, 'rb').read()
print('size', len(d))
for i in range(off, min(off + n, len(d)), 16):
    c = d[i:i + 16]
    print('%06x  %-48s %s' % (i, c.hex(' '), ''.join(chr(b) if 32 <= b < 127 else '.' for b in c)))
