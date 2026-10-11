import sys, struct, zipfile
path = sys.argv[1]
d = open(path, 'rb').read()
print('== local headers walk ==')
off = 0
while off + 30 <= len(d) and d[off:off + 4] == b'PK\x03\x04':
    ver, flag, meth, mt, md, crc, csz, usz, nl, el = struct.unpack('<HHHHHIIIHH', d[off + 4:off + 30])
    name = d[off + 30:off + 30 + nl].decode('utf-8', 'replace')
    data_off = off + 30 + nl + el
    print(f'{off:8d} data@{data_off:8d} meth={meth} flag={flag:#x} crc={crc:08x} csz={csz} usz={usz} extra={el} {name}')
    off = data_off + csz
print('stopped at', off, d[off:off + 4])
print('== zipfile central directory ==')
z = zipfile.ZipFile(path)
for i in z.infolist():
    print(f'{i.header_offset:8d} meth={i.compress_type} crc={i.CRC:08x} csz={i.compress_size} usz={i.file_size} {i.filename}  comment={i.comment!r}')
print('archive comment', z.comment)
