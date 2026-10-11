import re, sys
d = open(sys.argv[1], 'rb').read()
minlen = int(sys.argv[2]) if len(sys.argv) > 2 else 12
for m in re.finditer(rb'[\x20-\x7e\t\r\n]{%d,}' % minlen, d):
    s = m.group().decode('ascii')
    print('%06x %5d %r' % (m.start(), len(s), s[:160]))
