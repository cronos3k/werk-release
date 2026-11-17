import sys, os, datetime
p = sys.argv[1]
off = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0
n = int(sys.argv[3], 0) if len(sys.argv) > 3 else 512
print("now", datetime.datetime.now(), "size", os.path.getsize(p))
with open(p, "rb") as f:
    f.seek(off)
    b = f.read(n)
for i in range(0, len(b), 16):
    c = b[i:i+16]
    print(f"{off+i:08x}  {c.hex(' '):<48}  {''.join(chr(x) if 32 <= x < 127 else '.' for x in c)}")
