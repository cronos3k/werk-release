"""Probe the embedded PNG chunks and try inflating every enc=1 array."""
import struct, sys, zlib, binascii
d = open(sys.argv[1], 'rb').read()
i = d.find(b'\x89PNG\r\n\x1a\n')
print('png at %x' % i)
p = i + 8
while True:
    n, t = struct.unpack_from('>I4s', d, p)
    body = d[p + 8:p + 8 + n]
    crc = struct.unpack_from('>I', d, p + 8 + n)[0]
    ok = binascii.crc32(t + body) & 0xffffffff == crc
    print('  chunk %s len %d crc_ok %s %r' % (t, n, ok, body[:60] if t not in (b'IDAT',) else ''))
    p += 12 + n
    if t == b'IEND':
        break
print('png end %x; content node said 9460 bytes -> %x' % (p, i + 9460))
# any extra zlib streams anywhere?
import re
cnt = 0
for m in re.finditer(b'\x78[\x01\x5e\x9c\xda]', d):
    try:
        z = zlib.decompressobj()
        out = z.decompress(d[m.start():m.start() + 200000])
        if len(out) > 0 and z.eof:
            cnt += 1
            print('zlib @%x -> %d bytes, consumed %d, head %r' % (m.start(), len(out), len(d[m.start():m.start()+200000]) - len(z.unused_data), out[:40]))
    except Exception:
        pass
print(cnt)
