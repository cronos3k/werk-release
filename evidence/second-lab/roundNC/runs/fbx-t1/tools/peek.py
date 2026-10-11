import sys
p, off, n = sys.argv[1], int(sys.argv[2], 0), int(sys.argv[3], 0)
with open(p, 'rb') as f:
    f.seek(off)
    d = f.read(n)
for i in range(0, len(d), 16):
    c = d[i:i+16]
    print('%08x  %-48s %s' % (off + i, ' '.join('%02x' % b for b in c),
          ''.join(chr(b) if 32 <= b < 127 else '.' for b in c)))
