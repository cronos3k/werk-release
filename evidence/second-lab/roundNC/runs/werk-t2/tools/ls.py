import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
for i in z.infolist():
    print("%-60s %9d %9d method=%d off=%d crc=%08x" % (i.filename, i.file_size, i.compress_size, i.compress_type, i.header_offset, i.CRC))
print("comment:", z.comment)
