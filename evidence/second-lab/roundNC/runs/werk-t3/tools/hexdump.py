import sys
path = sys.argv[1]
start = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0
length = int(sys.argv[3], 0) if len(sys.argv) > 3 else 512
d = open(path, 'rb').read()
if start < 0:
    start = len(d) + start
print('filesize', len(d))
for i in range(start, min(start + length, len(d)), 16):
    c = d[i:i + 16]
    print('%08x' % i, c.hex(' ').ljust(48), ''.join(chr(b) if 32 <= b < 127 else '.' for b in c))
