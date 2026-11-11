import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
sys.stdout.reconfigure(encoding='utf-8')
for name in sys.argv[2:]:
    print('=====', name)
    print(z.read(name).decode('utf-8', 'replace'))
