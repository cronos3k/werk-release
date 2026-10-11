"""Exploratory tree dumper; asserts each structural assumption against the bytes."""
import sys, struct, zlib

data = open(sys.argv[1], 'rb').read()
maxdepth = int(sys.argv[2]) if len(sys.argv) > 2 else 99
FIXED = {'Y': ('<h', 2), 'C': ('<B', 1), 'I': ('<i', 4), 'F': ('<f', 4), 'D': ('<d', 8), 'L': ('<q', 8)}
ARR = {'f': ('f', 4), 'd': ('d', 8), 'l': ('q', 8), 'i': ('i', 4), 'b': ('B', 1)}


def prop(o):
    t = chr(data[o]); o += 1
    if t in FIXED:
        f, n = FIXED[t]; return t, struct.unpack_from(f, data, o)[0], o + n
    if t in 'SR':
        n, = struct.unpack_from('<I', data, o); raw = data[o + 4:o + 4 + n]
        return t, raw, o + 4 + n
    if t in ARR:
        cnt, enc, clen = struct.unpack_from('<III', data, o); raw = data[o + 12:o + 12 + clen]
        return t, (cnt, enc, raw), o + 12 + clen
    raise ValueError(f'unknown prop type {t!r} at {o-1:#x}')


def short(t, v):
    if t == 'S':
        return 'S' + repr(v.replace(b'\x00\x01', b'::').decode('utf-8', 'replace')[:120])
    if t == 'R':
        return f'R<{len(v)} bytes {v[:16].hex()}>'
    if t in ARR:
        cnt, enc, raw = v; return f'{t}[{cnt}] enc={enc} clen={len(raw)} head={raw[:4].hex()}'
    return f'{t}{v!r}'


def node(o, depth):
    end, np_, pl = struct.unpack_from('<III', data, o)
    nl = data[o + 12]
    if end == 0:
        return None, o + 13
    name = data[o + 13:o + 13 + nl].decode('ascii')
    p = o + 13 + nl; props = []
    for _ in range(np_):
        t, v, p = prop(p); props.append(short(t, v))
    assert p == o + 13 + nl + pl, (name, hex(o))
    if depth <= maxdepth:
        print(f'{"  "*depth}{o:#07x}..{end:#07x} {name}: {" | ".join(props)[:300]}')
    while p < end:
        if end - p == 13 and data[p:p + 13] == b'\0' * 13:
            p += 13; break
        _, p = node(p, depth + 1)
    assert p == end, (name, hex(p), hex(end))
    return name, end


assert data[:23] == b'Kaydara FBX Binary  \x00\x1a\x00'
print('version', struct.unpack_from('<I', data, 23)[0])
o = 27
while o < len(data):
    if data[o:o + 13] == b'\0' * 13:
        print(f'top-level terminator at {o:#x}'); o += 13; break
    _, o = node(o, 0)
print(f'trailer from {o:#x}, {len(data)-o} bytes: {data[o:o+64].hex()}')
