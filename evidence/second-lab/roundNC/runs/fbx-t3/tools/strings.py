import sys, re
p = sys.argv[1]; mn = int(sys.argv[2]) if len(sys.argv) > 2 else 6
data = open(p, 'rb').read()
for m in re.finditer(rb'[\x20-\x7e\t\r\n]{%d,}' % mn, data):
    s = m.group().decode('ascii')
    print(f"{m.start():08x} [{len(s)}] {s[:200]!r}")
