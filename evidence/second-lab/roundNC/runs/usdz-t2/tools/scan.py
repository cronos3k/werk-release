import sys, re
d = open(sys.argv[1], 'rb').read()
minlen = int(sys.argv[2]) if len(sys.argv) > 2 else 6
lo = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0
hi = int(sys.argv[4], 0) if len(sys.argv) > 4 else len(d)
for m in re.finditer(rb'PK[\x01-\x08][\x02-\x08]', d):
    print('SIG %08x %s' % (m.start(), m.group().hex()))
for m in re.finditer(rb'[\x20-\x7e\t\r\n]{%d,}' % minlen, d[lo:hi]):
    s = m.group().decode('ascii')
    print('STR %08x len=%d %r' % (lo + m.start(), len(s), s[:300]))
