import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
print('comment:', z.comment)
for i in z.infolist():
    print('%-60s %9d %9d method=%d off=%d crc=%08x extra=%s' % (i.filename, i.file_size, i.compress_size, i.compress_type, i.header_offset, i.CRC, i.extra.hex()))
