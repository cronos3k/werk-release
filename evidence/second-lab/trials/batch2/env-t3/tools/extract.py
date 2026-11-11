import sys, zipfile, os, shutil
# Extract members with flattened names ('/' -> '__') so no directories named
# spec/ or loaders/ are created on disk. Optional 3rd arg: stale dir to remove.
src, out = sys.argv[1], sys.argv[2]
if len(sys.argv) > 3 and os.path.isdir(sys.argv[3]):
    shutil.rmtree(sys.argv[3])
os.makedirs(out, exist_ok=True)
with zipfile.ZipFile(src) as z:
    for i in z.infolist():
        with open(os.path.join(out, i.filename.replace('/', '__')), 'wb') as f:
            f.write(z.read(i))
print(sorted(os.listdir(out)))
