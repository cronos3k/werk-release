import sys, re
path = sys.argv[1]
minlen = int(sys.argv[2]) if len(sys.argv) > 2 else 6
d = open(path, 'rb').read()
for m in re.finditer(rb'[\x20-\x7e\t\r\n]{%d,}' % minlen, d):
    s = m.group().decode('ascii')
    print('%08x %6d %s' % (m.start(), len(s), s[:200].replace('\n', '\\n')))
