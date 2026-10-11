"""Exploratory dumper: walk the node tree, print every node and a summary of its props."""
import sys, struct, zlib

d = open(sys.argv[1], 'rb').read()
ver = struct.unpack_from('<I', d, 23)[0]
print('magic', d[:23], 'version', ver, 'size', len(d))

SCALAR = {'Y': ('<h', 2), 'C': ('<B', 1), 'I': ('<i', 4), 'F': ('<f', 4), 'D': ('<d', 8), 'L': ('<q', 8)}
ARR = {'f': ('f', 4), 'd': ('d', 8), 'l': ('q', 8), 'i': ('i', 4), 'b': ('B', 1)}
covered = []

def props(o, n):
    out = []
    for _ in range(n):
        t = chr(d[o]); o += 1
        if t in SCALAR:
            fmt, sz = SCALAR[t]; out.append((t, struct.unpack_from(fmt, d, o)[0])); o += sz
        elif t in 'SR':
            ln = struct.unpack_from('<I', d, o)[0]; o += 4
            out.append((t, d[o:o+ln])); o += ln
        elif t in ARR:
            cnt, enc, clen = struct.unpack_from('<III', d, o); o += 12
            raw = d[o:o+clen]; o += clen
            if enc == 1:
                raw = zlib.decompress(raw)
            ch, sz = ARR[t]
            assert len(raw) == cnt * sz, (t, cnt, enc, clen, len(raw))
            out.append((t, (cnt, enc, clen, raw)))
        else:
            raise ValueError('unknown prop type %r at %x' % (t, o - 1))
    return out, o

def node(o, depth):
    end, n, plen, nl = struct.unpack_from('<IIIB', d, o)
    if end == 0:
        return None, o + 13
    name = d[o+13:o+13+nl].decode()
    p0 = o + 13 + nl
    pr, pe = props(p0, n)
    assert pe == p0 + plen, (name, hex(o))
    s = []
    for t, v in pr:
        if t in ARR:
            cnt, enc, clen, raw = v
            s.append('%s[%d]%s' % (t, cnt, ' z' if enc else ''))
        elif t in 'SR':
            s.append('%s%r' % (t, v[:60] if t == 'S' else ('<%d bytes>' % len(v))))
        else:
            s.append('%s%r' % (t, v))
    print('%08x %s%s  %s' % (o, '  ' * depth, name, ' '.join(s)))
    c = pe
    while c < end:
        r, c = node(c, depth + 1)
        if r is None:
            break
    assert c == end, (name, hex(c), hex(end))
    return name, end

o = 27
while True:
    r, o = node(o, 0)
    if r is None:
        break
print('top-level end at %x; remaining %d bytes' % (o, len(d) - o))
