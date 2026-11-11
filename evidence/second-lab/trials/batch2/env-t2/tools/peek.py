import zipfile, sys, os
src, dst = sys.argv[1], sys.argv[2]
z = zipfile.ZipFile(src)
for i in z.infolist():
    print(i.header_offset, i.compress_type, i.file_size, "%08x" % i.CRC, i.filename)
print("comment", z.comment)
print("testzip", z.testzip())
os.makedirs(dst, exist_ok=True)
z.extractall(dst)
