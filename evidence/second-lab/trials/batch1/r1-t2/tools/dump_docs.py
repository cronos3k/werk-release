import sys, zipfile, os
z = zipfile.ZipFile(sys.argv[1])
dst = sys.argv[2]
for n in z.namelist():
    if n.startswith('spec/'):
        p = os.path.join(dst, *n.split('/')[1:])
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, 'wb').write(z.read(n))
        print(p)
