import sys, zipfile, os
z = zipfile.ZipFile(sys.argv[1])
out = sys.argv[2]
for i in z.infolist():
    dst = os.path.normpath(os.path.join(out, i.filename))
    assert dst.startswith(os.path.normpath(out) + os.sep), i.filename
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, 'wb') as f:
        f.write(z.read(i))  # z.read verifies CRC32
print('ok')
