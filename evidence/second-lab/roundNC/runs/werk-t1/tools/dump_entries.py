import sys, struct, os
d = open(sys.argv[1], 'rb').read()
out = sys.argv[2]
off = 0
while d[off:off+4] == b'PK\x03\x04':
    ver, flg, meth, mt, md, crc, csz, usz, nl, xl = struct.unpack_from('<HHHHHIIIHH', d, off+4)
    name = d[off+30:off+30+nl].decode('utf-8')
    data = off + 30 + nl + xl
    if not name.startswith('loaders/') and '..' not in name:
        p = os.path.join(out, *name.split('/'))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, 'wb').write(d[data:data+csz])
    off = data + csz
