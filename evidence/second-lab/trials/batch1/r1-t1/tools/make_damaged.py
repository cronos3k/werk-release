"""Write a damaged COPY of a store-mode werk: flip one byte inside the data of
each named entry. The original file is only read."""
import struct, sys, zipfile
src, dst, names = sys.argv[1], sys.argv[2], sys.argv[3:]
raw = bytearray(open(src, "rb").read())
with zipfile.ZipFile(src) as z:
    for name in names:
        info = z.getinfo(name)
        off = info.header_offset
        n, m = struct.unpack_from("<HH", raw, off + 26)
        pos = off + 30 + n + m + info.compress_size // 2
        raw[pos] ^= 0xFF
        print("flipped byte at %d (middle of %s)" % (pos, name))
open(dst, "wb").write(raw)
