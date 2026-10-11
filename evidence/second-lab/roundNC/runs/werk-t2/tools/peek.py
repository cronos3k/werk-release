import sys
d = open(sys.argv[1], 'rb').read()
off = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0
n = int(sys.argv[3], 0) if len(sys.argv) > 3 else 512
print("size", len(d))
chunk = d[off:off + n]
for i in range(0, len(chunk), 16):
    row = chunk[i:i + 16]
    print("%08x  %-48s %s" % (off + i, row.hex(' '), ''.join(chr(b) if 32 <= b < 127 else '.' for b in row)))
