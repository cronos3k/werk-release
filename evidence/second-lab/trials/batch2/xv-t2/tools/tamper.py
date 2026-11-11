"""Make damaged COPIES of a werk (the original is only read). Each copy flips one
byte inside one entry's data and rewrites that entry's CRC in both the local and
the central header, so the zip itself stays valid and only werk-level checks can
notice. Usage: tamper.py SRC OUT ENTRY [byte_offset_within_entry]"""
import sys, struct, zlib, zipfile
src, out, entry = sys.argv[1:4]
k = int(sys.argv[4]) if len(sys.argv) > 4 else 100
d = bytearray(open(src, "rb").read())
z = zipfile.ZipFile(src)
info = z.getinfo(entry)
lho = info.header_offset
nl, ml = struct.unpack_from("<HH", d, lho + 26)
start = lho + 30 + nl + ml
d[start + k] ^= 0x01
crc = zlib.crc32(bytes(d[start:start + info.file_size])) & 0xFFFFFFFF
struct.pack_into("<I", d, lho + 14, crc)
# central directory record for this entry
eocd = d.rfind(b"PK\x05\x06")
cd_off = struct.unpack_from("<I", d, eocd + 16)[0]
p = cd_off
while d[p:p + 4] == b"PK\x01\x02":
    n, m, c = struct.unpack_from("<HHH", d, p + 28)
    if d[p + 46:p + 46 + n].decode() == entry:
        struct.pack_into("<I", d, p + 16, crc)
    p += 46 + n + m + c
open(out, "wb").write(bytes(d))
print("wrote", out, "flipped byte", k, "of", entry)
