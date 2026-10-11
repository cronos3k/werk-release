import sys, re
d = open(sys.argv[1], 'rb').read()
minlen = int(sys.argv[2]) if len(sys.argv) > 2 else 8
for m in re.finditer(rb'[\x20-\x7e\t\r\n]{%d,}' % minlen, d):
    s = m.group().decode('ascii')
    print('%08x %5d %s' % (m.start(), len(s), s[:160].replace('\n', '\\n')))
