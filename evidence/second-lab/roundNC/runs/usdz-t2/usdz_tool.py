#!/usr/bin/env python3
"""Open crate-nc-v1.usdz, list its contents, verify integrity, extract mesh + texture.

Usage:  python -I usdz_tool.py <file.usdz> [outdir]

Nothing inside the package documents its own format.  Every structural rule
used here is a hypothesis that is checked against redundancy in the file
itself (duplicated headers, sizes that must tile the file, CRC-32 fields,
decoded counts that must agree, indices that must be in range).  Any check
that fails is reported; nothing is silently trusted.
"""
import hashlib
import json
import os
import struct
import sys
import zlib

CHECKS = []          # (description, ok)


def check(desc, ok):
    CHECKS.append((desc, bool(ok)))
    return ok


# --------------------------------------------------------------------------
# Container (zip-shaped, stored, 64-byte aligned)
# --------------------------------------------------------------------------
def read_container(d):
    e = d.rfind(b'PK\x05\x06')
    check('end-of-directory record found', e >= 0)
    (_, _, _, n_here, n_tot, cd_size, cd_off, clen) = struct.unpack_from('<IHHHHIIH', d, e)
    check('end record is last thing in file', e + 22 + clen == len(d))
    check('directory entry counts agree', n_here == n_tot)
    check('directory ends where end record starts', cd_off + cd_size == e)
    ents, p = [], cd_off
    for _ in range(n_tot):
        f = struct.unpack_from('<IHHHHHHIIIHHHHHII', d, p)
        sig, crc, csz, usz, nl, xl, cl, loff = f[0], f[7], f[8], f[9], f[10], f[11], f[12], f[16]
        check('directory entry signature', sig == 0x02014b50)
        name = d[p + 46:p + 46 + nl].decode('utf-8')
        ents.append(dict(name=name, method=f[4], crc=crc, csize=csz, usize=usz, loff=loff))
        p += 46 + nl + xl + cl
    check('directory size matches walked entries', p == e)
    cursor = 0
    for ent in ents:
        lf = struct.unpack_from('<IHHHHHIIIHH', d, ent['loff'])
        lname = d[ent['loff'] + 30:ent['loff'] + 30 + lf[9]].decode('utf-8')
        ds = ent['loff'] + 30 + lf[9] + lf[10]
        ent['data_off'] = ds
        n = ent['name']
        check('%s: local header signature' % n, lf[0] == 0x04034b50)
        check('%s: local name == directory name' % n, lname == n)
        check('%s: local crc/sizes == directory' % n, (lf[6], lf[7], lf[8]) == (ent['crc'], ent['csize'], ent['usize']))
        check('%s: stored (method 0, csize == usize)' % n, ent['method'] == 0 and ent['csize'] == ent['usize'])
        check('%s: data 64-byte aligned' % n, ds % 64 == 0)
        check('%s: entry starts where previous ended (no hidden bytes)' % n, ent['loff'] == cursor)
        cursor = ds + ent['csize']
        data = d[ds:ds + ent['csize']]
        ent['data'] = data
        ent['crc_computed'] = zlib.crc32(data) & 0xffffffff
        check('%s: CRC-32 declared %08x == computed %08x' % (n, ent['crc'], ent['crc_computed']),
              ent['crc'] == ent['crc_computed'])
        ent['sha256'] = hashlib.sha256(data).hexdigest()
    check('last entry ends where directory starts', cursor == cd_off)
    return ents


# --------------------------------------------------------------------------
# LZ4-style block decompression and the chunk wrapper around it
# --------------------------------------------------------------------------
def lz4_block(src):
    out = bytearray()
    i, n = 0, len(src)
    while i < n:
        tok = src[i]; i += 1
        lit = tok >> 4
        if lit == 15:
            while True:
                b = src[i]; i += 1; lit += b
                if b != 255:
                    break
        out += src[i:i + lit]; i += lit
        if i >= n:
            break
        off = src[i] | (src[i + 1] << 8); i += 2
        if off == 0 or off > len(out):
            raise ValueError('bad match offset %d at %d' % (off, i))
        ml = tok & 15
        if ml == 15:
            while True:
                b = src[i]; i += 1; ml += b
                if b != 255:
                    break
        ml += 4
        start = len(out) - off
        for k in range(ml):
            out.append(out[start + k])
    return bytes(out)


def fast_decompress(buf):
    nchunks = buf[0]
    if nchunks == 0:
        return lz4_block(buf[1:])
    out, p = bytearray(), 1
    for _ in range(nchunks):
        sz, = struct.unpack_from('<i', buf, p); p += 4
        out += lz4_block(buf[p:p + sz]); p += sz
    return bytes(out)


def decode_ints(raw, n, wide=False):
    """Delta + 2-bit width-code integer coding."""
    if n == 0:
        return []
    cfmt, csz = ('<q', 8) if wide else ('<i', 4)
    common, = struct.unpack_from(cfmt, raw, 0)
    codes_len = (n * 2 + 7) // 8
    codes = raw[csz:csz + codes_len]
    p = csz + codes_len
    widths = ((None, 'b', 'h', 'i') if not wide else (None, 'h', 'i', 'q'))
    out, prev = [], 0
    for k in range(n):
        c = (codes[k // 4] >> (2 * (k % 4))) & 3
        if c == 0:
            v = common
        else:
            f = '<' + widths[c]
            v, = struct.unpack_from(f, raw, p); p += struct.calcsize(f)
        prev += v
        out.append(prev)
    return out


# --------------------------------------------------------------------------
# Binary scene file
# --------------------------------------------------------------------------
TYPES = {1: 'bool', 2: 'uchar', 3: 'int', 4: 'uint', 5: 'int64', 6: 'uint64', 7: 'half', 8: 'float',
         9: 'double', 10: 'string', 11: 'token', 12: 'asset', 13: 'matrix2d', 14: 'matrix3d',
         15: 'matrix4d', 16: 'quatd', 17: 'quatf', 18: 'quath', 19: 'double2', 20: 'float2',
         21: 'half2', 22: 'int2', 23: 'double3', 24: 'float3', 25: 'half3', 26: 'int3',
         27: 'double4', 28: 'float4', 29: 'half4', 30: 'int4', 31: 'dictionary',
         32: 'tokenListOp', 33: 'stringListOp', 34: 'pathListOp', 35: 'referenceListOp',
         36: 'intListOp', 37: 'int64ListOp', 38: 'uintListOp', 39: 'uint64ListOp',
         40: 'pathVector', 41: 'tokenVector', 42: 'specifier', 43: 'permission',
         44: 'variability', 45: 'variantSelectionMap', 46: 'timeSamples', 47: 'payload',
         48: 'doubleVector', 49: 'layerOffsetVector', 50: 'stringVector', 51: 'valueBlock',
         52: 'value', 53: 'unregisteredValue', 54: 'unregisteredValueListOp', 55: 'payloadListOp',
         56: 'timecode', 57: 'pathExpression'}
SCALAR = {1: ('<?', 1), 2: ('<B', 1), 3: ('<i', 4), 4: ('<I', 4), 5: ('<q', 8), 6: ('<Q', 8),
          7: ('<e', 2), 8: ('<f', 4), 9: ('<d', 8)}
VEC = {19: ('d', 2), 20: ('f', 2), 21: ('e', 2), 22: ('i', 2), 23: ('d', 3), 24: ('f', 3), 25: ('e', 3),
       26: ('i', 3), 27: ('d', 4), 28: ('f', 4), 29: ('e', 4), 30: ('i', 4), 16: ('d', 4), 17: ('f', 4),
       18: ('e', 4), 13: ('d', 4), 14: ('d', 9), 15: ('d', 16)}
SPEC_TYPES = {0: 'Unknown', 1: 'Attribute', 2: 'Connection', 3: 'Expression', 4: 'Mapper',
              5: 'MapperArg', 6: 'Prim', 7: 'PseudoRoot', 8: 'Relationship',
              9: 'RelationshipTarget', 10: 'Variant', 11: 'VariantSet'}
SPECIFIERS = {0: 'def', 1: 'over', 2: 'class'}
VARIABILITY = {0: 'varying', 1: 'uniform'}


class Crate:
    def __init__(self, b):
        self.b = b
        check('scene magic is PXR-USDC', b[:8] == b'PXR-USDC')
        self.version = tuple(b[8:11])
        toc, = struct.unpack_from('<Q', b, 16)
        check('table of contents offset inside file', 0 < toc < len(b))
        n, = struct.unpack_from('<Q', b, toc)
        self.sections = {}
        for i in range(n):
            nm, off, sz = struct.unpack_from('<16sQQ', b, toc + 8 + 32 * i)
            self.sections[nm.rstrip(b'\0').decode()] = (off, sz)
        check('table of contents ends at end of scene file', toc + 8 + 32 * n == len(b))
        prev_end = 88
        for nm, (off, sz) in sorted(self.sections.items(), key=lambda kv: kv[1][0]):
            check('section %s within file and non-overlapping' % nm, off >= prev_end and off + sz <= toc)
            prev_end = off + sz
        self._tokens(); self._strings(); self._fields(); self._fieldsets(); self._paths(); self._specs()

    def u64(self, p):
        return struct.unpack_from('<Q', self.b, p)[0]

    def cints(self, p, n, wide=False):
        sz = self.u64(p)
        raw = fast_decompress(self.b[p + 8:p + 8 + sz])
        return decode_ints(raw, n, wide), p + 8 + sz

    def _tokens(self):
        off, sz = self.sections['TOKENS']
        n, usz, csz = struct.unpack_from('<QQQ', self.b, off)
        raw = fast_decompress(self.b[off + 24:off + 24 + csz])
        check('TOKENS: decompressed size %d == declared %d' % (len(raw), usz), len(raw) == usz)
        toks = raw.split(b'\0')
        check('TOKENS: %d strings == declared count %d' % (len(toks) - 1, n), toks[-1] == b'' and len(toks) - 1 == n)
        check('TOKENS: section fully consumed', off + 24 + csz == off + sz)
        self.tokens = [t.decode('utf-8') for t in toks[:-1]]

    def _strings(self):
        off, sz = self.sections['STRINGS']
        n = self.u64(off)
        self.strings = list(struct.unpack_from('<%dI' % n, self.b, off + 8))
        check('STRINGS: size matches count', 8 + 4 * n == sz)
        check('STRINGS: all token indices valid', all(i < len(self.tokens) for i in self.strings))

    def _fields(self):
        off, sz = self.sections['FIELDS']
        n = self.u64(off)
        toks, p = self.cints(off + 8, n)
        rsz = self.u64(p)
        reps = fast_decompress(self.b[p + 8:p + 8 + rsz])
        check('FIELDS: value-rep block is 8*count bytes', len(reps) == 8 * n)
        check('FIELDS: section fully consumed', p + 8 + rsz == off + sz)
        check('FIELDS: name indices valid', all(0 <= t < len(self.tokens) for t in toks))
        self.fields = [(self.tokens[t], struct.unpack_from('<Q', reps, 8 * i)[0]) for i, t in enumerate(toks)]

    def _fieldsets(self):
        off, sz = self.sections['FIELDSETS']
        n = self.u64(off)
        vals, p = self.cints(off + 8, n)
        check('FIELDSETS: section fully consumed', p == off + sz)
        self.fieldsets, cur, start = {}, [], 0
        for i, v in enumerate(vals):
            v &= 0xffffffff
            if v == 0xffffffff:
                self.fieldsets[start] = cur; cur = []; start = i + 1
            else:
                check_ok = v < len(self.fields)
                if not check_ok:
                    check('FIELDSETS: field index %d in range' % v, False)
                cur.append(v)
        check('FIELDSETS: ends with terminator', cur == [])

    def _paths(self):
        off, sz = self.sections['PATHS']
        total = self.u64(off)
        n = self.u64(off + 8)
        pidx, p = self.cints(off + 16, n)
        etok, p = self.cints(p, n)
        jumps, p = self.cints(p, n)
        check('PATHS: section fully consumed', p == off + sz)
        self.paths = [None] * total
        # iterative walk; a stack replaces recursion on siblings
        stack = [(0, None)]
        while stack:
            cur, parent = stack.pop()
            while True:
                i = cur; cur += 1
                if parent is None:
                    path = '/'
                    parent = path
                else:
                    t = etok[i]
                    name = self.tokens[abs(t)]
                    if t < 0:
                        path = parent + '.' + name
                    else:
                        path = (parent.rstrip('/') + '/' + name)
                self.paths[pidx[i]] = path
                has_child = jumps[i] > 0 or jumps[i] == -1
                has_sib = jumps[i] >= 0
                if has_child:
                    if has_sib:
                        stack.append((i + jumps[i], parent))
                    parent = path
                if not (has_child or has_sib):
                    break
        check('PATHS: every path index filled exactly once', all(x is not None for x in self.paths)
              and len(set(self.paths)) == total)

    def _specs(self):
        off, sz = self.sections['SPECS']
        n = self.u64(off)
        pi, p = self.cints(off + 8, n)
        fs, p = self.cints(p, n)
        st, p = self.cints(p, n)
        check('SPECS: section fully consumed', p == off + sz)
        check('SPECS: fieldset indices are fieldset starts', all(f in self.fieldsets for f in fs))
        check('SPECS: spec types known', all(t in SPEC_TYPES for t in st))
        self.specs = []
        for a, f, t in zip(pi, fs, st):
            fields = {}
            for fi in self.fieldsets[f]:
                name, rep = self.fields[fi]
                fields[name] = self.value(rep)
            self.specs.append(dict(path=self.paths[a], type=SPEC_TYPES[t], fields=fields))

    # ---- values --------------------------------------------------------
    def tok(self, i):
        return self.tokens[i]

    def value(self, rep):
        is_array = bool(rep >> 63 & 1)
        inlined = bool(rep >> 62 & 1)
        compressed = bool(rep >> 61 & 1)
        t = (rep >> 48) & 0xff
        payload = rep & ((1 << 48) - 1)
        if t not in TYPES:
            check('value type %d known' % t, False)
            return ('?', rep)
        if inlined:
            return self._inline(t, payload)
        if is_array:
            return self._array(t, payload, compressed)
        return self._outofline(t, payload)

    def _inline(self, t, pl):
        u32 = pl & 0xffffffff
        if t in (11, 12):
            return self.tok(u32)
        if t == 10:
            return self.tok(self.strings[u32])
        if t == 42:
            return SPECIFIERS.get(u32, u32)
        if t == 44:
            return VARIABILITY.get(u32, u32)
        if t == 8:
            return struct.unpack('<f', struct.pack('<I', u32))[0]
        if t == 9:   # double stored as float
            return struct.unpack('<f', struct.pack('<I', u32))[0]
        if t in (1, 2, 3, 4, 5, 6):
            v = struct.unpack('<i', struct.pack('<I', u32))[0] if t in (3, 5) else u32
            return bool(v) if t == 1 else v
        if t in VEC:   # small vectors stored as int8 components
            _, k = VEC[t]
            bs = struct.pack('<Q', pl)
            if t in (13, 14, 15):  # diagonal matrices
                diag = list(struct.unpack('<%db' % int(k ** 0.5), bs[:int(k ** 0.5)]))
                return ('diag', diag)
            return list(struct.unpack('<%db' % k, bs[:k]))
        if t == 31:
            return {}
        if t == 51:
            return None
        return ('inline', TYPES[t], pl)

    def _scalar_at(self, t, p):
        if t in SCALAR:
            f, s = SCALAR[t]
            return struct.unpack_from(f, self.b, p)[0], p + s
        if t in VEC:
            c, k = VEC[t]
            v = list(struct.unpack_from('<%d%s' % (k, c), self.b, p))
            return v, p + k * struct.calcsize(c)
        if t in (11, 12):
            return self.tok(struct.unpack_from('<I', self.b, p)[0]), p + 4
        if t == 10:
            return self.tok(self.strings[struct.unpack_from('<I', self.b, p)[0]]), p + 4
        raise ValueError('scalar type %s' % TYPES[t])

    def _array(self, t, p, compressed):
        n = self.u64(p); p += 8
        if n == 0:
            return []
        if compressed and t in (3, 4, 5, 6):
            if n < 16:
                return [self._scalar_at(t, p + i * SCALAR[t][1])[0] for i in range(n)]
            return self.cints(p, n, wide=t in (5, 6))[0]
        if compressed and t in (7, 8, 9):
            if n < 16:
                return [self._scalar_at(t, p + i * SCALAR[t][1])[0] for i in range(n)]
            code = chr(self.b[p]); p += 1
            if code == 'i':
                return [float(x) for x in self.cints(p, n)[0]]
            if code == 't':
                lsz = struct.unpack_from('<I', self.b, p)[0]; p += 4
                f, s = SCALAR[t]
                lut = list(struct.unpack_from('<%d%s' % (lsz, f[1]), self.b, p)); p += lsz * s
                return [lut[i] for i in self.cints(p, n)[0]]
            raise ValueError('float array code %r' % code)
        out = []
        for _ in range(n):
            v, p = self._scalar_at(t, p)
            out.append(v)
        return out

    def _listop(self, p, read_item):
        hdr = self.b[p]; p += 1
        res = {}
        if hdr & 1:
            res['explicit'] = True
        for bit, key in ((2, 'explicitItems'), (4, 'addedItems'), (8, 'deletedItems'), (16, 'orderedItems'),
                         (32, 'prependedItems'), (64, 'appendedItems')):
            if hdr & bit:
                n = self.u64(p); p += 8
                items = []
                for _ in range(n):
                    v, p = read_item(p)
                    items.append(v)
                res[key] = items
        return res

    def _outofline(self, t, p):
        if t in SCALAR or t in VEC or t in (10, 11, 12):
            return self._scalar_at(t, p)[0]
        if t == 41:
            n = self.u64(p)
            return [self.tok(i) for i in struct.unpack_from('<%dI' % n, self.b, p + 8)]
        if t == 40:
            n = self.u64(p)
            return [self.paths[i] for i in struct.unpack_from('<%dI' % n, self.b, p + 8)]
        if t == 32:
            return self._listop(p, lambda q: (self.tok(struct.unpack_from('<I', self.b, q)[0]), q + 4))
        if t == 34:
            return self._listop(p, lambda q: (self.paths[struct.unpack_from('<I', self.b, q)[0]], q + 4))
        if t == 31:
            n = self.u64(p); p += 8
            out = {}
            for _ in range(n):
                k = self.tok(self.strings[struct.unpack_from('<I', self.b, p)[0]]); p += 4
                rel, = struct.unpack_from('<q', self.b, p)
                rep = self.u64(p + rel)
                out[k] = self.value(rep)
                p += 8
            return out
        return ('unparsed', TYPES[t], p)


# --------------------------------------------------------------------------
# Meanings
# --------------------------------------------------------------------------
def describe(spec):
    f, typ, path = spec['fields'], spec['type'], spec['path']
    if typ == 'PseudoRoot':
        return 'layer root (holds stage-wide settings)'
    if typ == 'Prim':
        tn = f.get('typeName', '')
        m = {'Xform': 'transform group node', 'Mesh': 'polygon mesh geometry', 'Scope': 'organisational folder',
             'Material': 'surface material', 'Shader': 'shading node'}.get(tn, 'prim')
        if tn == 'Shader' and 'info:id' in str(f):
            pass
        return '%s %s (%s)' % (f.get('specifier', ''), tn or '(untyped)', m)
    if typ == 'Attribute':
        name = path.rsplit('.', 1)[-1]
        known = {
            'points': 'vertex positions', 'faceVertexCounts': 'vertices per face',
            'faceVertexIndices': 'vertex index list for each face corner', 'normals': 'surface normals',
            'extent': 'axis-aligned bounding box (min, max)', 'subdivisionScheme': 'subdivision rule (none = plain polygons)',
            'doubleSided': 'render both faces', 'primvars:st': 'texture (UV) coordinates',
            'primvars:UVMap': 'texture (UV) coordinates', 'xformOp:transform': 'local 4x4 transform',
            'xformOpOrder': 'order of transform operations', 'info:id': 'shader implementation identifier',
            'inputs:file': 'texture image file path', 'outputs:surface': 'material surface output',
            'inputs:diffuseColor': 'base colour', 'inputs:roughness': 'roughness', 'inputs:metallic': 'metalness',
            'inputs:st': 'UV coordinate input', 'inputs:varname': 'which primvar to read as UVs',
            'outputs:rgb': 'texture colour output', 'outputs:result': 'shader result output',
            'inputs:wrapS': 'horizontal wrap mode', 'inputs:wrapT': 'vertical wrap mode',
            'inputs:sourceColorSpace': 'colour space of image', 'inputs:opacity': 'opacity',
            'inputs:specularColor': 'specular colour', 'inputs:clearcoat': 'clearcoat amount',
            'inputs:clearcoatRoughness': 'clearcoat roughness', 'inputs:ior': 'index of refraction',
            'inputs:emissiveColor': 'emission colour', 'inputs:useSpecularWorkflow': 'specular vs metallic workflow',
            'inputs:normal': 'normal map input', 'inputs:occlusion': 'ambient occlusion',
        }
        base = known.get(name)
        if base is None and name.startswith('primvars:'):
            base = 'per-geometry variable %s' % name[9:]
        return 'attribute %s%s' % (f.get('typeName', ''), ' - ' + base if base else '')
    if typ == 'Relationship':
        return 'relationship (pointer to other prims)'
    return typ


def short(v, n=6):
    if isinstance(v, list):
        if len(v) > n:
            return '[%d items] %s ...' % (len(v), json.dumps(v[:n], default=str)[:160])
        return json.dumps(v, default=str)[:200]
    if isinstance(v, float):
        return '%g' % v
    if isinstance(v, dict):
        return json.dumps(v, default=str)[:300]
    return repr(v)[:200]


# --------------------------------------------------------------------------
def main():
    src = sys.argv[1]
    outdir = sys.argv[2] if len(sys.argv) > 2 else 'extracted'
    d = open(src, 'rb').read()
    print('== FILE %s  %d bytes  sha256=%s' % (src, len(d), hashlib.sha256(d).hexdigest()))
    ents = read_container(d)
    print('\n== CONTAINER ENTRIES')
    for e in ents:
        print('  %-28s %7d bytes @0x%06x  crc32 declared=%08x computed=%08x  sha256=%s'
              % (e['name'], e['usize'], e['data_off'], e['crc'], e['crc_computed'], e['sha256']))
        kind = {'.usdc': 'binary scene description (magic PXR-USDC)', '.png': 'PNG image'}.get(os.path.splitext(e['name'])[1], '?')
        print('      meaning: %s' % kind)

    scene = [e for e in ents if e['data'][:8] == b'PXR-USDC']
    check('exactly one scene file in package', len(scene) == 1)
    cr = Crate(scene[0]['data'])
    print('\n== SCENE FILE  version %s' % '.'.join(map(str, cr.version)))
    for nm, (off, sz) in cr.sections.items():
        print('  section %-10s @0x%06x %7d bytes' % (nm, off, sz))
    print('  %d tokens, %d strings, %d fields, %d fieldsets, %d paths, %d specs'
          % (len(cr.tokens), len(cr.strings), len(cr.fields), len(cr.fieldsets), len(cr.paths), len(cr.specs)))

    print('\n== NODE GRAPH (spec path : kind : meaning)')
    for s in cr.specs:
        print('  %-60s %s' % (s['path'], describe(s)))
        for k, v in s['fields'].items():
            print('      %-22s = %s' % (k, short(v)))

    # cross-check: declared children lists vs actual paths
    bypath = {s['path']: s for s in cr.specs}
    for s in cr.specs:
        kids = s['fields'].get('primChildren')
        if isinstance(kids, list):
            base = s['path'].rstrip('/')
            check('%s: every declared child exists' % s['path'], all((base + '/' + k) in bypath for k in kids))
        props = s['fields'].get('properties')
        if isinstance(props, list):
            check('%s: every declared property exists' % s['path'], all((s['path'] + '.' + k) in bypath for k in props))

    def walk(v):
        if isinstance(v, tuple) and v and v[0] in ('unparsed', 'inline', '?'):
            return False
        if isinstance(v, (list, tuple)):
            return all(walk(x) for x in v)
        if isinstance(v, dict):
            return all(walk(x) for x in v.values())
        return True
    check('every field value of every spec decoded (no unparsed types)',
          all(walk(s['fields']) for s in cr.specs))

    # ---- meshes ----
    meshes = []
    for s in cr.specs:
        if s['type'] == 'Prim' and s['fields'].get('typeName') == 'Mesh':
            g = lambda a: bypath.get(s['path'] + '.' + a, {}).get('fields', {}).get('default')
            pts, fvc, fvi = g('points'), g('faceVertexCounts'), g('faceVertexIndices')
            uvname = next((a for a in ('primvars:st', 'primvars:UVMap') if g(a) is not None), None)
            meshes.append(dict(path=s['path'], points=pts, fvc=fvc, fvi=fvi, normals=g('normals'),
                               uv=g(uvname) if uvname else None, uvname=uvname,
                               uvidx=g(uvname + ':indices') if uvname else None,
                               uvinterp=bypath.get(s['path'] + '.' + uvname, {}).get('fields', {}).get('interpolation') if uvname else None,
                               extent=g('extent')))
    print('\n== MESHES')
    for m in meshes:
        n = len(m['points'] or [])
        ok = (m['fvc'] is not None and m['fvi'] is not None and sum(m['fvc']) == len(m['fvi'])
              and all(0 <= i < n for i in m['fvi']))
        check('%s: face counts sum to index count and indices in range' % m['path'], ok)
        sharp = bypath.get(m['path'] + '.primvars:sharp_face', {}).get('fields', {}).get('default')
        for nm, arr, want in (('primvars:st', m['uv'], len(m['fvi'])), ('normals', m['normals'], len(m['fvi'])),
                              ('primvars:sharp_face', sharp, len(m['fvc']))):
            if arr is not None:
                check('%s: %s has %d entries == expected %d' % (m['path'], nm, len(arr), want), len(arr) == want)
        if m['extent'] and m['points']:
            lo = [min(p[k] for p in m['points']) for k in range(3)]
            hi = [max(p[k] for p in m['points']) for k in range(3)]
            check('%s: declared extent matches computed bounds' % m['path'],
                  all(abs(a - b) < 1e-4 for a, b in zip(lo + hi, m['extent'][0] + m['extent'][1])))
        print('  %-50s %6d points %6d faces  uv=%s(%s)' % (m['path'], n, len(m['fvc'] or []), m['uvname'], m['uvinterp']))

    os.makedirs(outdir, exist_ok=True)
    primary = max(meshes, key=lambda m: len(m['points'] or []))
    objname = os.path.join(outdir, primary['path'].strip('/').replace('/', '_') + '.obj')
    write_obj(primary, objname)
    print('\n== EXTRACTED primary mesh %s -> %s' % (primary['path'], objname))

    # texture: the entry referenced by inputs:file
    refs = [s['fields'].get('default') for s in cr.specs if s['path'].endswith('.inputs:file')]
    print('  texture references in scene: %s' % refs)
    tex = next(e for e in ents if e['name'].endswith('.png'))
    check('texture entry is referenced by the scene', any(r and r.lstrip('./') == tex['name'] for r in refs))
    tpath = os.path.join(outdir, os.path.basename(tex['name']))
    with open(tpath, 'wb') as f:
        f.write(tex['data'])
    spath = os.path.join(outdir, scene[0]['name'])
    with open(spath, 'wb') as f:
        f.write(scene[0]['data'])
    results = []
    for path, ent in ((tpath, tex), (spath, scene[0])):
        b = open(path, 'rb').read()
        crc = zlib.crc32(b) & 0xffffffff
        check('%s: re-read crc32 %08x == declared %08x' % (path, crc, ent['crc']), crc == ent['crc'])
        results.append((path, ent['crc'], crc, hashlib.sha256(b).hexdigest()))
    b = open(objname, 'rb').read()
    results.append((objname, None, zlib.crc32(b) & 0xffffffff, hashlib.sha256(b).hexdigest()))
    print('\n== OUTPUT FILES')
    for path, dc, cc, sh in results:
        print('  %-50s declared crc32=%s computed crc32=%08x sha256=%s'
              % (path, '%08x' % dc if dc is not None else '(none declared)', cc, sh))

    print('\n== INTEGRITY CHECKS')
    for desc, ok in CHECKS:
        print('  [%s] %s' % ('OK ' if ok else 'FAIL', desc))
    nfail = sum(1 for _, ok in CHECKS if not ok)
    print('\n%d checks, %d failed' % (len(CHECKS), nfail))
    return 1 if nfail else 0


def write_obj(m, path):
    with open(path, 'w', newline='\n') as f:
        f.write('# %s\n' % m['path'])
        for p in m['points']:
            f.write('v %.9g %.9g %.9g\n' % tuple(p))
        uv = m['uv']
        # faceVarying UVs map 1:1 onto face corners (optionally via an index array)
        if uv:
            for t in uv:
                f.write('vt %.9g %.9g\n' % tuple(t))
        nrm = m['normals']
        if nrm:
            for n in nrm:
                f.write('vn %.9g %.9g %.9g\n' % tuple(n))
        c = 0
        for cnt in m['fvc']:
            parts = []
            for k in range(cnt):
                vi = m['fvi'][c + k] + 1
                if uv:
                    if m['uvidx'] is not None:
                        ti = m['uvidx'][c + k] + 1
                    elif m['uvinterp'] == 'vertex':
                        ti = vi
                    else:
                        ti = c + k + 1
                else:
                    ti = None
                ni = None
                if nrm:
                    ni = (c + k + 1) if len(nrm) == len(m['fvi']) else vi
                parts.append('%d/%s/%s' % (vi, ti or '', ni or '') if (ti or ni) else '%d' % vi)
            f.write('f %s\n' % ' '.join(parts))
            c += cnt


if __name__ == '__main__':
    sys.exit(main())
