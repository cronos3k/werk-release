"""Exploratory node walker: prints the full node tree of the container."""
import struct, sys, zlib

d = open(sys.argv[1], 'rb').read()
ver = struct.unpack_from('<I', d, 23)[0]
W = 8 if ver >= 7500 else 4
NULL = 3 * W + 1
print('version', ver, 'offset width', W)


def prop(o):
    t = chr(d[o]); o += 1
    sc = {'Y': ('<h', 2), 'C': ('<?', 1), 'I': ('<i', 4), 'F': ('<f', 4), 'D': ('<d', 8), 'L': ('<q', 8)}
    if t in sc:
        f, n = sc[t]
        return t, struct.unpack_from(f, d, o)[0], o + n
    if t in 'SR':
        n = struct.unpack_from('<I', d, o)[0]
        return t, d[o + 4:o + 4 + n], o + 4 + n
    if t in 'fdlib':
        cnt, enc, clen = struct.unpack_from('<III', d, o)
        raw = d[o + 12:o + 12 + clen]
        return t, (cnt, enc, clen, raw), o + 12 + clen
    raise ValueError('unknown prop type %r at %x' % (t, o - 1))


def fmt(t, v):
    if t == 'S':
        return 'S' + repr(v[:100])
    if t == 'R':
        return 'R<%d bytes: %r>' % (len(v), v[:24])
    if t in 'fdlib':
        cnt, enc, clen, raw = v
        return '%s[%d enc=%d clen=%d]' % (t, cnt, enc, clen)
    return '%s%r' % (t, v)


def walk(o, depth, end_limit):
    while o < end_limit:
        end, nprops, plen = struct.unpack_from('<' + ('Q' if W == 8 else 'I') * 3, d, o)
        nl = d[o + 3 * W]
        if end == 0:
            return o + NULL
        name = d[o + 3 * W + 1:o + 3 * W + 1 + nl].decode('latin1')
        p = o + 3 * W + 1 + nl
        props = []
        for _ in range(nprops):
            t, v, p = prop(p)
            props.append(fmt(t, v))
        print('%06x %s%s %s' % (o, '  ' * depth, name, ', '.join(props)[:300]))
        if p < end:
            walk(p, depth + 1, end)
        o = end
    return o


o = walk(27, 0, len(d))
print('top-level end at %x of %x' % (o, len(d)))
print('footer:', d[o:o + 200].hex())
print('tail:', d[-64:].hex())
