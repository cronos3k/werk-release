import sys, struct, zlib
d = open(sys.argv[1], 'rb').read()
o = int(sys.argv[2], 0); n = int(sys.argv[3], 0)
png = d[o:o+n]
print(png[:8])
p = 8
while p < len(png):
    ln, typ = struct.unpack_from('>I4s', png, p)
    body = png[p+8:p+8+ln]
    crc = struct.unpack_from('>I', png, p+8+ln)[0]
    ok = zlib.crc32(typ + body) & 0xffffffff == crc
    print(typ, ln, 'crc ok' if ok else 'CRC MISMATCH', body[:80] if typ not in (b'IDAT',) else '')
    p += 12 + ln
print('end', p, len(png))
