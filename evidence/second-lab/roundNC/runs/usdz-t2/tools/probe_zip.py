import sys, struct, zlib, hashlib
d = open(sys.argv[1], 'rb').read()
# EOCD hypothesis: last 22 bytes
e = d.rfind(b'PK\x05\x06')
sig, disk, cdisk, n_here, n_tot, cd_size, cd_off, clen = struct.unpack('<IHHHHIIH', d[e:e+22])
print('EOCD@%x entries=%d/%d cd_size=%d cd_off=%x comment_len=%d trailing=%d' % (e, n_here, n_tot, cd_size, cd_off, clen, len(d) - (e + 22)))
p = cd_off
ents = []
for i in range(n_tot):
    f = struct.unpack('<IHHHHHHIIIHHHHHII', d[p:p+46])
    (sig, vmade, vneed, flags, meth, mt, md, crc, csz, usz, nl, xl, cl, dstart, iattr, eattr, loff) = f
    name = d[p+46:p+46+nl].decode()
    extra = d[p+46+nl:p+46+nl+xl]
    print('CD  %-28s ver=%d/%d flags=%x meth=%d time=%04x date=%04x crc=%08x csz=%d usz=%d extra=%s loff=%x' % (name, vmade, vneed, flags, meth, mt, md, crc, csz, usz, extra.hex(), loff))
    ents.append((name, crc, csz, usz, loff, meth))
    p += 46 + nl + xl + cl
print('CD end %x vs EOCD %x' % (p, e))
for name, crc, csz, usz, loff, meth in ents:
    f = struct.unpack('<IHHHHHIIIHH', d[loff:loff+30])
    lname = d[loff+30:loff+30+f[9]].decode()
    lx = d[loff+30+f[9]:loff+30+f[9]+f[10]]
    ds = loff + 30 + f[9] + f[10]
    data = d[ds:ds+csz]
    print('LFH %-28s crc=%08x csz=%d usz=%d extra=%s data@%x (mod64=%d) end=%x' % (lname, f[6], f[7], f[8], lx.hex(), ds, ds % 64, ds + csz))
    print('    crc32(data)=%08x match=%s  sha256=%s' % (zlib.crc32(data), zlib.crc32(data) == crc, hashlib.sha256(data).hexdigest()))
    if name.endswith('.png'):
        q = 8
        print('    png sig', data[:8].hex())
        while q < len(data):
            ln, = struct.unpack('>I', data[q:q+4]); typ = data[q+4:q+8]
            body = data[q+8:q+8+ln]; c, = struct.unpack('>I', data[q+8+ln:q+12+ln])
            ok = zlib.crc32(typ + body) == c
            extra_info = body.hex() if typ == b'IHDR' else (body[:200] if typ in (b'tEXt', b'iTXt', b'zTXt') else '')
            print('    chunk %s len=%d crc_ok=%s %s' % (typ.decode('latin1'), ln, ok, extra_info))
            q += 12 + ln
