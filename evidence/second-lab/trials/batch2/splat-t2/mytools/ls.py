import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
print('comment:', z.comment)
for i in z.infolist():
    print(f'{i.header_offset:>10} {i.compress_type:>2} {i.compress_size:>10} {i.file_size:>10} {i.CRC:08x} {i.filename}')
print(len(z.infolist()), 'entries')
