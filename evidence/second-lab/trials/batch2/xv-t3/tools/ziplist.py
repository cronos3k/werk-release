import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
print('comment:', z.comment[:500])
for i in z.infolist():
    print('%-70s %10d %10d m=%d off=%d extra=%s' % (i.filename, i.file_size, i.compress_size, i.compress_type, i.header_offset, i.extra.hex()[:40]))
