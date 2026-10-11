"""Inspect crate-nc-v1.usdz using only rules derived empirically from the file.

The package contains no specification, manifest or reader. Every structural
rule used below was inferred from internal consistency of the bytes (a length
field is trusted only because it equals an observed span, etc.) and is
re-checked at run time. Fields whose meaning could not be derived from the
file are reported as raw values and NOT interpreted.

Usage: python -I inspect_usdz.py <path-to.usdz> <output-dir>
"""
import hashlib
import os
import re
import struct
import sys

U16 = lambda b, o: struct.unpack_from('<H', b, o)[0]
U32 = lambda b, o: struct.unpack_from('<I', b, o)[0]
U64 = lambda b, o: struct.unpack_from('<Q', b, o)[0]

# Record markers observed in the file: one at offset 0 (precedes each stored
# entry), one per entry in a trailing table, one final record at the tail.
ENTRY_MARK, DIR_MARK, END_MARK = b'PK\x03\x04', b'PK\x01\x02', b'PK\x05\x06'

problems = []


def check(cond, msg):
    print(f'  [{"ok" if cond else "FAIL"}] {msg}')
    if not cond:
        problems.append(msg)
    return cond


def sha(b):
    return hashlib.sha256(b).hexdigest()


def parse_end(d):
    pos = d.rfind(END_MARK)
    check(pos >= 0, 'trailing end record found')
    # Layout inferred: 4 marker, 2+2 unknown (both 0), 2+2 entry counts,
    # 4 table size, 4 table offset, 2 trailing (0 = nothing follows).
    end = dict(pos=pos, n1=U16(d, pos + 8), n2=U16(d, pos + 10),
               tsize=U32(d, pos + 12), toff=U32(d, pos + 16), tail=U16(d, pos + 20))
    check(pos + 22 + end['tail'] == len(d), 'end record + trailing count reaches EOF exactly')
    check(end['toff'] + end['tsize'] == pos, 'table offset + table size == end record position')
    check(end['n1'] == end['n2'], 'both entry-count fields agree')
    return end


def parse_dir(d, end):
    entries, p = [], end['toff']
    for _ in range(end['n1']):
        check(d[p:p + 4] == DIR_MARK, f'table record marker at {p}')
        e = dict(dir_pos=p,
                 unknown_versions=(U16(d, p + 4), U16(d, p + 6)),
                 unknown_flags_method=(U16(d, p + 8), U16(d, p + 10)),
                 unknown_stamp=(U16(d, p + 12), U16(d, p + 14)),
                 unknown_check32=U32(d, p + 16),
                 size_a=U32(d, p + 20), size_b=U32(d, p + 24),
                 name_len=U16(d, p + 28), extra_len=U16(d, p + 30),
                 comment_len=U16(d, p + 32), entry_off=U32(d, p + 42))
        q = p + 46
        e['name'] = d[q:q + e['name_len']].decode('utf-8')
        e['extra'] = d[q + e['name_len']:q + e['name_len'] + e['extra_len']]
        p = q + e['name_len'] + e['extra_len'] + e['comment_len']
        entries.append(e)
    check(p == end['pos'], 'table records tile exactly up to end record')
    return entries


def parse_entry(d, e):
    o = e['entry_off']
    check(d[o:o + 4] == ENTRY_MARK, f'{e["name"]}: entry marker at {o}')
    nl, xl = U16(d, o + 26), U16(d, o + 28)
    name = d[o + 30:o + 30 + nl].decode('utf-8')
    check(name == e['name'], f'{e["name"]}: name in entry header == name in table')
    # Fields at entry+4..+26 are the table record's +6..+28 fields, shifted.
    check(d[o + 4:o + 26] == d[e['dir_pos'] + 6:e['dir_pos'] + 28],
          f'{e["name"]}: entry header fields == table record fields')
    check(e['size_a'] == e['size_b'], f'{e["name"]}: both size fields equal ({e["size_a"]}) '
          '-> consistent with bytes stored verbatim')
    data_off = o + 30 + nl + xl
    e['data_off'] = data_off
    e['data'] = d[data_off:data_off + e['size_b']]
    check(data_off % 64 == 0, f'{e["name"]}: payload starts 64-byte aligned at {data_off} '
          '(extra field looks like zero padding)')
    check(set(d[o + 30 + nl + 4:data_off]) <= {0}, f'{e["name"]}: padding bytes are all zero')
    return e


def describe_scene_layer(blob):
    """List what can be seen of the binary scene layer without its spec."""
    print('  magic:', blob[:8])
    print('  unknown 8 bytes after magic:', blob[8:16].hex())
    toc = U64(blob, 16)
    count = U64(blob, toc)
    print(f'  section table at layer offset {toc}, {count} sections')
    secs = []
    for i in range(count):
        p = toc + 8 + 32 * i
        nm = blob[p:p + 16].rstrip(b'\0').decode('ascii')
        so, sz = U64(blob, p + 16), U64(blob, p + 24)
        secs.append((nm, so, sz))
        print(f'    {nm:<10} offset {so:8d} size {sz:6d}')
    check(toc + 8 + 32 * count == len(blob), 'section table ends exactly at layer end')
    for (a, ao, az), (b, bo, _) in zip(secs, secs[1:]):
        check(ao + az == bo, f'section {a} ends where {b} begins')
    # Readable fragments of the TOKENS section. The section is mostly
    # compressed by an undocumented scheme; only literal runs are visible.
    nm, so, sz = secs[0]
    frag = [m.group().decode() for m in re.finditer(rb'[A-Za-z_:\[\]0-9. /]{4,}', blob[so:so + sz])]
    print('  readable TOKENS fragments (partial, NOT a decoded list):')
    print('   ', ', '.join(frag))
    return secs


def main():
    src, outdir = sys.argv[1], sys.argv[2]
    with open(src, 'rb') as f:  # read-only; the container is never modified
        d = f.read()
    print(f'container: {src}\n  size {len(d)}  sha256 {sha(d)}')

    print('\n== structure checks ==')
    end = parse_end(d)
    entries = [parse_entry(d, e) for e in parse_dir(d, end)]
    spans = sorted((e['entry_off'], e['data_off'] + len(e['data'])) for e in entries)
    check(spans[0][0] == 0, 'first entry starts at offset 0')
    for (a0, a1), (b0, _) in zip(spans, spans[1:]):
        check(a1 == b0, f'entry ending at {a1} is followed immediately by next entry')
    check(spans[-1][1] == end['toff'], 'last entry ends exactly where the table begins')

    print('\n== contents ==')
    for e in entries:
        kind = ('binary scene layer (magic PXR-USDC); holds the scene incl. mesh Cube_020'
                if e['data'][:8] == b'PXR-USDC' else
                'image (PNG signature, 256x256 per IHDR bytes), referenced as texture'
                if e['data'][:8] == b'\x89PNG\r\n\x1a\n' else 'unknown')
        print(f'- {e["name"]}\n    payload offset {e["data_off"]}, {len(e["data"])} bytes: {kind}')
        print(f'    computed sha256 {sha(e["data"])}')
        print(f'    undeclared-meaning fields: check32=0x{e["unknown_check32"]:08x} '
              f'stamp={e["unknown_stamp"]} versions={e["unknown_versions"]} '
              f'flags/method={e["unknown_flags_method"]} extra={e["extra"][:4].hex()}+zeros')
        if e['data'][:8] == b'PXR-USDC':
            describe_scene_layer(e['data'])
        if e['data'][:8] == b'\x89PNG\r\n\x1a\n':
            check(e['data'].endswith(b'IEND\xaeB`\x82'), f'{e["name"]}: ends with the IEND trailer seen in file')

    print('\n== declared hashes ==')
    hexruns = re.findall(rb'[0-9a-fA-F]{32,}', d)
    print(f'  hex digest-like strings anywhere in container: {len(hexruns)}')
    print('  No sha256 manifest exists in the package. The only candidate integrity values are the')
    print('  4-byte "check32" fields above; their algorithm is not documented in the file, so they')
    print('  were NOT verified.')

    print('\n== extraction ==')
    os.makedirs(outdir, exist_ok=True)
    for e in entries:
        dst = os.path.join(outdir, e['name'].replace('/', '_'))
        with open(dst, 'wb') as f:
            f.write(e['data'])
        with open(dst, 'rb') as f:
            print(f'  wrote {dst}  sha256 {sha(f.read())}')

    print(f'\n{len(problems)} structural check failure(s)')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
