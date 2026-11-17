# grep a regex inside one container member, with context lines.
import sys, zipfile, re
z = zipfile.ZipFile(sys.argv[1])
sys.stdout.reconfigure(encoding='utf-8')
lines = z.read(sys.argv[2]).decode('utf-8', 'replace').splitlines()
ctx = int(sys.argv[4]) if len(sys.argv) > 4 else 0
pat = re.compile(sys.argv[3])
for i, l in enumerate(lines):
    if pat.search(l):
        for j in range(max(0, i - ctx), min(len(lines), i + ctx + 1)):
            print('%5d| %s' % (j + 1, lines[j][:300]))
        if ctx:
            print('--')
