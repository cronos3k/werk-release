# Print markdown headings of a container member with line numbers.
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
sys.stdout.reconfigure(encoding='utf-8')
for i, l in enumerate(z.read(sys.argv[2]).decode('utf-8', 'replace').splitlines(), 1):
    if l.startswith('#'):
        print('%5d| %s' % (i, l))
