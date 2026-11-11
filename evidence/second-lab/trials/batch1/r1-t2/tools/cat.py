import sys, zipfile
sys.stdout.reconfigure(encoding='utf-8')
z = zipfile.ZipFile(sys.argv[1])
for n in sys.argv[2:]:
    print(f'===== {n} =====')
    sys.stdout.write(z.read(n).decode('utf-8', 'replace'))
    print()
