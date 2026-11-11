import sys, zipfile, os
z = zipfile.ZipFile(sys.argv[1])
out = sys.argv[2]
os.makedirs(out, exist_ok=True)
for i in z.infolist():
    if i.file_size > 2_000_000:
        continue  # skip large binaries; read those directly from the zip
    flat = i.filename.replace('/', '__') + '.txt'  # .txt suffix: never executable by association
    with open(os.path.join(out, flat), 'wb') as f:
        f.write(z.read(i))
print('done')
