import sys, os, zipfile
src, dst = sys.argv[1], sys.argv[2]
names = sys.argv[3:]
z = zipfile.ZipFile(src)
for n in names:
    p = os.path.join(dst, n.replace('/', '__'))
    os.makedirs(dst, exist_ok=True)
    open(p + '.txt' if not n.endswith('.txt') else p, 'wb').write(z.read(n))
    print("wrote", p)
