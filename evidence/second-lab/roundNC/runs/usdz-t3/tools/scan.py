import re, sys
d = open(sys.argv[1], 'rb').read()
for sig in (b'PK\x03\x04', b'PK\x01\x02', b'PK\x05\x06', b'PK\x06\x06', b'PK\x07\x08'):
    print(sig, [m.start() for m in re.finditer(re.escape(sig), d)])
minlen = int(sys.argv[2]) if len(sys.argv) > 2 else 6
for m in re.finditer(rb'[\x20-\x7e\t\r\n]{%d,}' % minlen, d):
    s = m.group().decode('ascii')
    print(f'{m.start():8d} {len(s):6d} {s[:200]!r}')
