# Print a member of the container straight from the ZIP (never extracted to disk).
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
name = sys.argv[2]
start = int(sys.argv[3]) if len(sys.argv) > 3 else 0
count = int(sys.argv[4]) if len(sys.argv) > 4 else 10**9
data = z.read(name)
lines = data.decode('utf-8', 'replace').splitlines()
sys.stdout.reconfigure(encoding='utf-8')
for i, l in enumerate(lines[start:start + count], start + 1):
    print('%5d| %s' % (i, l))
print('--- %d lines total' % len(lines))
