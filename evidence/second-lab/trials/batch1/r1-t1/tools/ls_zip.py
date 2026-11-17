import sys, zipfile, hashlib
p = sys.argv[1]
print("sha256(file) =", hashlib.sha256(open(p, "rb").read()).hexdigest())
with zipfile.ZipFile(p) as z:
    for i in z.infolist():
        print(f"{i.header_offset:>8} {i.compress_type} {i.file_size:>9} {i.compress_size:>9} {i.CRC:08x} {i.filename}")
    print("comment:", z.comment)
