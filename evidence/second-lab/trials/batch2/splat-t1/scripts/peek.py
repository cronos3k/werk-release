import sys
p = sys.argv[1]
off = int(sys.argv[2]) if len(sys.argv) > 2 else 0
n = int(sys.argv[3]) if len(sys.argv) > 3 else 512
with open(p, 'rb') as f:
    f.seek(off)
    d = f.read(n)
for i in range(0, len(d), 16):
    c = d[i:i+16]
    print('%08x  %-48s %s' % (off + i, ' '.join('%02x' % b for b in c),
                              ''.join(chr(b) if 32 <= b < 127 else '.' for b in c)))
