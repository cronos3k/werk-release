import sys, zipfile, os
z = zipfile.ZipFile(sys.argv[1])
out = sys.argv[2]
for i in z.infolist():
    n = i.filename
    assert not n.startswith('/') and '..' not in n.split('/'), n
    p = os.path.join(out, *n.split('/'))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'wb') as f:
        f.write(z.read(i))  # zipfile checks CRC32 on read
print('ok', len(z.infolist()))
