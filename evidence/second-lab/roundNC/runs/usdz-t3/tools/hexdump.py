import sys
d = open(sys.argv[1], 'rb').read()
start, end = int(sys.argv[2]), int(sys.argv[3])
for off in range(start, min(end, len(d)), 16):
    row = d[off:off + 16]
    hx = ' '.join(f'{b:02x}' for b in row)
    asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in row)
    print(f'{off:8d}  {hx:<47}  {asc}')
