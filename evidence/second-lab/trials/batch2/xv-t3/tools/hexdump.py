import sys
p = sys.argv[1]
off = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0
n = int(sys.argv[3], 0) if len(sys.argv) > 3 else 512
with open(p, 'rb') as f:
    f.seek(off)
    d = f.read(n)
for i in range(0, len(d), 16):
    c = d[i:i+16]
    print('%08x' % (off + i), c.hex(' '), ''.join(chr(x) if 32 <= x < 127 else '.' for x in c))
