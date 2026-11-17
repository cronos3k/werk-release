import sys
path, off, n = sys.argv[1], int(sys.argv[2], 0), int(sys.argv[3], 0)
with open(path, 'rb') as f:
    f.seek(off)
    data = f.read(n)
for i in range(0, len(data), 16):
    chunk = data[i:i+16]
    hx = ' '.join(f'{b:02x}' for b in chunk)
    asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
    print(f'{off+i:08x}  {hx:<48}  {asc}')
