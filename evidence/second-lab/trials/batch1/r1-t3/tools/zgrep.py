import sys, zipfile, re
# usage: zgrep.py werk member regex   |   zgrep.py werk member --lines A B
z = zipfile.ZipFile(sys.argv[1])
sys.stdout.reconfigure(encoding='utf-8')
lines = z.read(sys.argv[2]).decode('utf-8', 'replace').split('\n')
if sys.argv[3] == '--lines':
    a, b = int(sys.argv[4]), int(sys.argv[5])
    for i in range(a, min(b, len(lines)) + 1):
        print('%5d  %s' % (i, lines[i - 1]))
else:
    rx = re.compile(sys.argv[3])
    for i, l in enumerate(lines, 1):
        if rx.search(l):
            print('%5d  %s' % (i, l))
