"""Copy selected members out of the container into a FLAT directory (no subdirs),
names with '/' replaced by '__', so no directory named spec/ or loaders/ is ever created."""
import sys, zipfile, zlib, os
p, outdir = sys.argv[1], sys.argv[2]
want = sys.argv[3:]
os.makedirs(outdir, exist_ok=True)
z = zipfile.ZipFile(p)
for i in z.infolist():
    if want and not any(i.filename.startswith(w) or i.filename == w for w in want):
        continue
    b = z.read(i)  # zipfile checks CRC itself
    out = os.path.join(outdir, i.filename.replace("/", "__") + ".txt")
    open(out, "wb").write(b)
    print("wrote", out, len(b))
