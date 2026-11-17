import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
print('comment:', z.comment)
for i in z.infolist():
    print(f'{i.filename:60s} size={i.file_size:8d} csize={i.compress_size:8d} method={i.compress_type} off={i.header_offset} crc={i.CRC:08x}')
