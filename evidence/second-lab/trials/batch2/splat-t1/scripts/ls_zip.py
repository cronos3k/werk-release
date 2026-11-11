import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
for i in z.infolist():
    print('%10d %10d %d %08x %s' % (i.header_offset, i.file_size, i.compress_type, i.CRC, i.filename))
print(len(z.infolist()), 'entries')
