"""Make a damaged COPY: flip one byte inside the stored data of an entry."""
import sys, zipfile, struct
src, dst, name = sys.argv[1], sys.argv[2], sys.argv[3]
b = bytearray(open(src, 'rb').read())
i = zipfile.ZipFile(src).getinfo(name)
lh = i.header_offset
n, mlen = struct.unpack('<HH', b[lh + 26:lh + 30])
data = lh + 30 + n + mlen
b[data + 100] ^= 0xFF
open(dst, 'wb').write(b)
print('flipped byte at', data + 100, 'in', name)
