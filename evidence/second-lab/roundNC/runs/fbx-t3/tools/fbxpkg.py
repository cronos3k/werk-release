"""Open crate-nc-v1.fbx, list its node graph with meanings, verify integrity,
and extract the primary mesh (OBJ) and the embedded texture (PNG).

Usage:  python -I fbxpkg.py <file.fbx> [outdir]

Only the Python standard library is used. Nothing from inside the file is executed.
"""
import hashlib, json, os, struct, sys, zlib

MAGIC = b'Kaydara FBX Binary  \x00\x1a\x00'
SCALAR = {'Y': ('<h', 2), 'C': ('<B', 1), 'I': ('<i', 4), 'F': ('<f', 4), 'D': ('<d', 8), 'L': ('<q', 8)}
ARRAY = {'f': ('f', 4), 'd': ('d', 8), 'l': ('q', 8), 'i': ('i', 4), 'b': ('B', 1)}

# Meanings: derived from names/values/connections inside the file (see REPORT.md).
MEANING = {
    'FBXHeaderExtension': 'file header block (format version, creation stamp, creator, scene info)',
    'FBXHeaderVersion': 'header block version', 'FBXVersion': 'file format version (matches u32 at offset 23)',
    'EncryptionType': 'encryption flag (0 = none)', 'CreationTimeStamp': 'creation date/time fields',
    'Creator': 'exporting application', 'SceneInfo': 'document metadata (title/author/... all empty here)',
    'FileId': '16-byte opaque file identifier', 'CreationTime': 'creation time string',
    'GlobalSettings': 'axis system, unit scale, time settings', 'Documents': 'document list; RootNode id 0',
    'References': 'external references (empty)', 'Definitions': 'object-type counts + default property templates',
    'Objects': 'all scene objects', 'Connections': 'object graph edges (C: kind, child id, parent id[, property])',
    'Takes': 'animation takes (none)', 'Properties70': 'property list (P: name, type, label, flags, value...)',
    'Vertices': 'control points, xyz float64 triples', 'PolygonVertexIndex': 'polygon corners; negative value v = last corner, real index = -v-1',
    'Edges': 'edge list as indices into PolygonVertexIndex', 'LayerElementNormal': 'normal layer',
    'Normals': 'normal vectors, xyz float64', 'NormalsIndex': 'per-corner index into Normals',
    'LayerElementUV': 'texture coordinate layer', 'UV': 'uv pairs float64', 'UVIndex': 'per-corner index into UV',
    'LayerElementMaterial': 'material assignment layer', 'Materials': 'material index list',
    'Layer': 'binds layer elements together', 'Content': 'embedded file bytes', 'Model': 'scene node (transform)',
    'Geometry': 'mesh data', 'Material': 'surface material', 'Texture': 'texture reference', 'Video': 'image clip (holds embedded image)',
}


class Node:
    __slots__ = ('name', 'props', 'children', 'start', 'end')

    def __init__(s, name, props, start, end):
        s.name, s.props, s.children, s.start, s.end = name, props, [], start, end

    def child(s, name):
        return next((c for c in s.children if c.name == name), None)


class FBX:
    def __init__(self, path):
        self.data = open(path, 'rb').read()
        self.issues, self.checks = [], []
        d = self.data
        if d[:23] != MAGIC:
            raise ValueError('bad magic')
        self.version = struct.unpack_from('<I', d, 23)[0]
        self.roots, o = [], 27
        while True:
            if d[o:o + 13] == b'\0' * 13:
                o += 13; break
            n, o = self._node(o)
            self.roots.append(n)
        self.body_end = o
        self.check('tree parses to a top-level terminator, every node end offset and property length exact', True)

    def check(self, what, ok, detail=''):
        self.checks.append((what, bool(ok), detail))

    # ---- parsing -----------------------------------------------------------
    def _prop(self, o):
        d = self.data; t = chr(d[o]); o += 1
        if t in SCALAR:
            f, n = SCALAR[t]; return (t, struct.unpack_from(f, d, o)[0]), o + n
        if t in 'SR':
            n, = struct.unpack_from('<I', d, o); return (t, d[o + 4:o + 4 + n]), o + 4 + n
        if t in ARRAY:
            cnt, enc, clen = struct.unpack_from('<III', d, o)
            return (t, ('array', cnt, enc, d[o + 12:o + 12 + clen], o)), o + 12 + clen
        raise ValueError(f'unknown property type {t!r} at {o - 1:#x}')

    def _node(self, o):
        d = self.data
        end, nprops, plen = struct.unpack_from('<III', d, o)
        nl = d[o + 12]
        name = d[o + 13:o + 13 + nl].decode('ascii')
        p = o + 13 + nl; props = []
        for _ in range(nprops):
            v, p = self._prop(p); props.append(v)
        if p != o + 13 + nl + plen:
            raise ValueError(f'{name}@{o:#x}: property bytes {p - o - 13 - nl} != declared {plen}')
        n = Node(name, props, o, end)
        while p < end:
            if end - p == 13 and d[p:p + 13] == b'\0' * 13:
                p += 13; break
            c, p = self._node(p); n.children.append(c)
        if p != end:
            raise ValueError(f'{name}@{o:#x}: children end {p:#x} != declared {end:#x}')
        return n, end

    def array(self, prop, label=''):
        t, (_, cnt, enc, raw, off) = prop
        fmt, size = ARRAY[t]
        if enc == 0:
            buf = raw
        elif enc == 1:
            try:
                buf = zlib.decompress(raw)  # zlib verifies its Adler-32 trailer
            except zlib.error as e:
                self.check(f'zlib/adler32 {label}@{off:#x}', False, str(e)); raise
        else:
            raise ValueError(f'unknown array encoding {enc} at {off:#x}')
        ok = len(buf) == cnt * size
        self.check(f'array {label}@{off:#x} enc={enc} decodes to {cnt}x{size} bytes', ok, f'got {len(buf)}')
        return list(struct.unpack(f'<{cnt}{fmt}', buf))

    # ---- helpers -----------------------------------------------------------
    def top(self, name):
        return next(n for n in self.roots if n.name == name)

    @staticmethod
    def sval(p):
        return p[1].replace(b'\x00\x01', b'::').decode('utf-8', 'replace') if p[0] == 'S' else p[1]

    def objects(self):
        return {o.props[0][1]: o for o in self.top('Objects').children}

    def connections(self):
        return [tuple(self.sval(p) for p in c.props) for c in self.top('Connections').children]


def fmt_prop(p):
    t, v = p
    if t == 'S':
        return repr(FBX.sval(p))
    if t == 'R':
        return f'<raw {len(v)} bytes>'
    if t in ARRAY:
        return f'{t}-array[{v[1]}] ({"zlib" if v[2] == 1 else "raw"} {len(v[3])} B)'
    return repr(v)


def list_graph(f, out):
    w = out.append
    w(f'FBX binary, version {f.version}, {len(f.data)} bytes, body ends at {f.body_end:#x}')

    def walk(n, depth):
        if n.name == 'P':
            w('  ' * depth + 'P ' + ', '.join(fmt_prop(p) for p in n.props)); return
        m = MEANING.get(n.name, '')
        w('  ' * depth + f'{n.name} [{n.start:#x}-{n.end:#x}] ' + ', '.join(fmt_prop(p) for p in n.props)
          + (f'   -- {m}' if m else ''))
        for c in n.children:
            walk(c, depth + 1)
    for r in f.roots:
        walk(r, 0)
    objs = f.objects()
    w('\nObject graph (child -> parent, from Connections; id 0 = Document RootNode):')
    for c in f.connections():
        kind, ch, par = c[:3]
        def nm(i):
            return 'RootNode' if i == 0 else f'{f.sval(objs[i].props[1])}' if i in objs else f'<MISSING {i}>'
        w(f'  {kind}  {nm(ch)}  ->  {nm(par)}' + (f'  via property {c[3]!r}' if len(c) > 3 else ''))


def mesh_of(f, geom):
    v = f.array(geom.child('Vertices').props[0], 'Vertices')
    pvi = f.array(geom.child('PolygonVertexIndex').props[0], 'PolygonVertexIndex')
    edges = f.array(geom.child('Edges').props[0], 'Edges')
    nl, ul = geom.child('LayerElementNormal'), geom.child('LayerElementUV')
    nrm = f.array(nl.child('Normals').props[0], 'Normals'); nidx = f.array(nl.child('NormalsIndex').props[0], 'NormalsIndex')
    uv = f.array(ul.child('UV').props[0], 'UV'); uidx = f.array(ul.child('UVIndex').props[0], 'UVIndex')
    for lay in (nl, ul):
        f.check(f'{lay.name} mapping is ByPolygonVertex/IndexToDirect',
                f.sval(lay.child('MappingInformationType').props[0]) == 'ByPolygonVertex'
                and f.sval(lay.child('ReferenceInformationType').props[0]) == 'IndexToDirect')
    nv = len(v) // 3
    polys, cur = [], []
    for k, i in enumerate(pvi):
        last = i < 0
        vi = -i - 1 if last else i
        cur.append((vi, k))
        if last:
            polys.append(cur); cur = []
    name = f.sval(geom.props[1])
    f.check(f'{name}: vertex array length multiple of 3', len(v) % 3 == 0)
    f.check(f'{name}: normals multiple of 3, uv multiple of 2', len(nrm) % 3 == 0 and len(uv) % 2 == 0)
    f.check(f'{name}: last PolygonVertexIndex entry closes a polygon', not cur)
    f.check(f'{name}: all corner vertex indices in [0,{nv})', all(0 <= c[0] < nv for p in polys for c in p))
    f.check(f'{name}: NormalsIndex/UVIndex length == corner count', len(nidx) == len(pvi) == len(uidx))
    f.check(f'{name}: NormalsIndex in range', all(0 <= i < len(nrm) // 3 for i in nidx))
    f.check(f'{name}: UVIndex in range', all(0 <= i < len(uv) // 2 for i in uidx))
    f.check(f'{name}: Edges index into corner array', all(0 <= e < len(pvi) for e in edges))
    return dict(name=name, v=v, pvi=pvi, polys=polys, nrm=nrm, nidx=nidx, uv=uv, uidx=uidx, edges=edges)


def write_obj(m, path, mtl_name=None, mtl_file=None, model_name=''):
    L = [f'# mesh {m["name"]} (model {model_name}) extracted from crate-nc-v1.fbx',
         '# coordinates are raw geometry-local values (model Lcl Rotation/Scaling NOT applied)']
    if mtl_file:
        L.append(f'mtllib {mtl_file}')
    v, n, uv = m['v'], m['nrm'], m['uv']
    L += [f'v {v[i]!r} {v[i+1]!r} {v[i+2]!r}' for i in range(0, len(v), 3)]
    L += [f'vt {uv[i]!r} {uv[i+1]!r}' for i in range(0, len(uv), 2)]
    L += [f'vn {n[i]!r} {n[i+1]!r} {n[i+2]!r}' for i in range(0, len(n), 3)]
    L.append(f'o {model_name or m["name"]}')
    if mtl_name:
        L.append(f'usemtl {mtl_name}')
    for p in m['polys']:
        L.append('f ' + ' '.join(f'{vi+1}/{m["uidx"][k]+1}/{m["nidx"][k]+1}' for vi, k in p))
    open(path, 'w', newline='\n').write('\n'.join(L) + '\n')


def verify_png(f, b):
    ok = b[:8] == b'\x89PNG\r\n\x1a\n'
    f.check('PNG signature', ok)
    o, idat, chunks, ihdr = 8, b'', [], None
    while o < len(b):
        ln, typ = struct.unpack_from('>I4s', b, o)
        body = b[o + 8:o + 8 + ln]; crc, = struct.unpack_from('>I', b, o + 8 + ln)
        good = zlib.crc32(typ + body) == crc
        f.check(f'PNG chunk {typ.decode()} @{o} len {ln} CRC-32', good)
        chunks.append(typ.decode())
        if typ == b'IHDR':
            ihdr = struct.unpack('>IIBBBBB', body)
        if typ == b'IDAT':
            idat += body
        o += 12 + ln
        if typ == b'IEND':
            break
    f.check('PNG ends exactly at IEND (no trailing bytes)', o == len(b), f'{len(b) - o} trailing')
    w, h, depth, ctype = ihdr[:4]
    ch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    raw = zlib.decompress(idat)
    exp = h * (1 + (w * ch * depth + 7) // 8)
    f.check(f'PNG IDAT inflates to {exp} bytes for {w}x{h} ctype {ctype} depth {depth}', len(raw) == exp, f'got {len(raw)}')
    return dict(width=w, height=h, bit_depth=depth, color_type=ctype, chunks=chunks)


def main(path, outdir):
    f = FBX(path)
    out = []
    list_graph(f, out)
    objs, conns = f.objects(), f.connections()
    ids = set(objs) | {0}
    f.check('every connection endpoint is a known object or RootNode', all(c[1] in ids and c[2] in ids for c in conns))
    defs = f.top('Definitions')
    for ot in defs.children:
        if ot.name == 'ObjectType' and f.sval(ot.props[0]) != 'GlobalSettings':
            typ = f.sval(ot.props[0]); want = ot.child('Count').props[0][1]
            have = sum(1 for o in objs.values() if o.name == typ)
            f.check(f'Definitions count for {typ} ({want}) matches Objects ({have})', want == have)
    f.check('FBXVersion in header block equals file version',
            f.top('FBXHeaderExtension').child('FBXVersion').props[0][1] == f.version)
    tail = f.data[f.body_end:]
    f.check('file version repeated in trailer', struct.pack('<I', f.version) in tail,
            'trailer semantics otherwise undocumented in file; not verifiable')

    # meshes: decode & validate all three
    parent = {c[1]: c[2] for c in conns if c[0] == 'OO'}
    meshes = {}
    for oid, o in objs.items():
        if o.name == 'Geometry':
            meshes[oid] = mesh_of(f, o)
    # primary mesh: no manifest names one -> geometry of the model whose name has no suffix
    # ('wooden_crate_01' vs '_lid'/'_latch'); it is also the largest by vertex count.
    def model_name(gid):
        return f.sval(objs[parent[gid]].props[1]).split('::')[0]
    by_size = max(meshes, key=lambda g: len(meshes[g]['v']))
    by_name = next(g for g in meshes if model_name(g) == 'wooden_crate_01')
    f.check('primary-mesh heuristics agree (unsuffixed model name == largest mesh)', by_size == by_name)
    prim = meshes[by_name]

    # texture: Video Content connected Video -> Texture -> Material(DiffuseColor)
    video = next(o for o in objs.values() if o.name == 'Video')
    png = video.child('Content').props[0][1]
    info = verify_png(f, png)
    tex_name = f.sval(video.child('RelativeFilename').props[0]).replace('\\', '/').split('/')[-1]

    os.makedirs(outdir, exist_ok=True)
    tex_path = os.path.join(outdir, tex_name)
    open(tex_path, 'wb').write(png)
    mtl = os.path.join(outdir, 'crate_wood.mtl')
    open(mtl, 'w', newline='\n').write(f'newmtl crate_wood\nKd 0.8 0.8 0.8\nmap_Kd {tex_name}\n')
    obj_path = os.path.join(outdir, 'wooden_crate_01.obj')
    write_obj(prim, obj_path, 'crate_wood', 'crate_wood.mtl', model_name(by_name))
    raw_path = os.path.join(outdir, 'wooden_crate_01.vertices.f64le')
    open(raw_path, 'wb').write(struct.pack(f'<{len(prim["v"])}d', *prim['v']))

    out.append('\nIntegrity checks:')
    for what, ok, det in f.checks:
        out.append(f'  [{"PASS" if ok else "FAIL"}] {what}' + (f'  ({det})' if det and not ok else ''))
    out.append('\nDeclared hashes: NONE. The file contains no manifest and no sha256/md5/crc declarations; '
               'only format-intrinsic checksums (zlib Adler-32, PNG CRC-32) exist and were checked above.')
    out.append('\nExtracted:')
    res = {}
    for p in (obj_path, raw_path, tex_path, mtl):
        h = hashlib.sha256(open(p, 'rb').read()).hexdigest(); res[os.path.basename(p)] = h
        out.append(f'  {os.path.basename(p)}  {os.path.getsize(p)} B  sha256 {h}  (declared: none)')
    out.append(f'  primary mesh {prim["name"]}: {len(prim["v"])//3} vertices, {len(prim["polys"])} polygons, '
               f'{len(prim["pvi"])} corners, {len(prim["edges"])} edges')
    out.append(f'  texture: {info}')
    out.append(f'  sha256 of embedded PNG bytes in file: {hashlib.sha256(png).hexdigest()}')
    nfail = sum(1 for c in f.checks if not c[1])
    out.append(f'\n{len(f.checks)} checks, {nfail} failed')
    print('\n'.join(out))
    json.dump({'sha256': res, 'checks_failed': nfail}, open(os.path.join(outdir, 'summary.json'), 'w'), indent=1)
    return 1 if nfail else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else 'extracted'))
