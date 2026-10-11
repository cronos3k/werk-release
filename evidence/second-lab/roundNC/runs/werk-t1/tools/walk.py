import sys, struct
d = open(sys.argv[1], 'rb').read()
# local headers
off = 0
while d[off:off+4] == b'PK\x03\x04':
    ver, flg, meth, mt, md, crc, csz, usz, nl, xl = struct.unpack_from('<HHHHHIIIHH', d, off+4)
    name = d[off+30:off+30+nl].decode('utf-8')
    data = off + 30 + nl + xl
    print('LFH @%08x data@%08x ver=%d flg=%04x meth=%d crc=%08x csz=%d usz=%d xl=%d align64=%d %s' % (off, data, ver, flg, meth, crc, csz, usz, xl, data % 64, name))
    off = data + csz
print('after locals @%08x sig=%r' % (off, d[off:off+4]))
# EOCD
e = d.rfind(b'PK\x05\x06')
print('EOCD @%08x' % e, struct.unpack_from('<HHHHIIH', d, e+4), 'trailing', len(d) - (e+22))
print('comment', d[e+22:e+22+struct.unpack_from('<H', d, e+20)[0]])
