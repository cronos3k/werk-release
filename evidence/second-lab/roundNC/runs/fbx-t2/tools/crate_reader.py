"""crate_reader.py - open crate-nc-v1.fbx, list its node graph with meanings,
verify integrity, and extract the primary mesh (OBJ) and the embedded texture.

Usage:  python -I crate_reader.py <file.fbx> <outdir>

Every structural rule used here was confirmed against the bytes of the file
(see REPORT.md): node records are (u32 end, u32 nprops, u32 proplen, u8 namelen,
name, props, children..., 13-byte zero sentinel); array props are
(u32 count, u32 encoding, u32 bytelen, payload) with encoding 1 = zlib.
The file is read-only; nothing in it is executed.
"""
import binascii, hashlib, os, re, struct, sys, zlib

SCALAR = {'Y': ('<h', 2), 'C': ('<?', 1), 'I': ('<i', 4), 'F': ('<f', 4),
          'D': ('<d', 8), 'L': ('<q', 8)}
ARRAY = {'f': ('f', 4), 'd': ('d', 8), 'l': ('q', 8), 'i': ('i', 4), 'b': ('?', 1)}

MEANING = {
    'FBXHeaderExtension': 'file header block (format version, creator, timestamps)',
    'FBXHeaderVersion': 'version of the header block layout',
    'FBXVersion': 'container format version (7400 -> 32-bit record offsets)',
    'EncryptionType': '0 = not encrypted',
    'CreationTimeStamp': 'creation date/time broken into fields',
    'Creator': 'application that wrote the file',
    'SceneInfo': 'document metadata (title, author, ... all empty here)',
    'MetaData': 'free-form document metadata',
    'Properties70': 'list of typed properties (P records: name, type, label, flags, value...)',
    'P': 'one property: name, type, sub-type, flags, value(s)',
    'FileId': '16-byte opaque file identifier',
    'CreationTime': 'creation time string',
    'GlobalSettings': 'scene-wide settings: axes, unit scale, frame rate',
    'Documents': 'list of documents (scenes) in the file',
    'Document': 'one scene document; RootNode gives id of the scene root (0)',
    'RootNode': 'object id of scene root',
    'References': 'external references (empty)',
    'Definitions': 'object-type table: counts per type + default property templates',
    'ObjectType': 'one object type and its instance count',
    'Count': 'number of items',
    'PropertyTemplate': 'default property values for this object type',
    'Objects': 'all scene objects (geometry, models, material, texture, video)',
    'Geometry': 'mesh geometry object (id, name, class)',
    'GeometryVersion': 'geometry record version',
    'Vertices': 'vertex positions, flat xyz doubles',
    'PolygonVertexIndex': 'polygon corner -> vertex index; last corner of each polygon stored as -(i+1)',
    'Edges': 'edge list, indexes into polygon-vertex array',
    'LayerElementNormal': 'normal layer',
    'LayerElementUV': 'texture-coordinate layer',
    'LayerElementMaterial': 'per-polygon material assignment layer',
    'Normals': 'normal vectors, flat xyz doubles',
    'NormalsIndex': 'per polygon-corner index into Normals',
    'UV': 'texture coordinates, flat uv doubles',
    'UVIndex': 'per polygon-corner index into UV',
    'Materials': 'material slot index (AllSame -> one value for whole mesh)',
    'MappingInformationType': 'how layer values map onto the mesh',
    'ReferenceInformationType': 'Direct or IndexToDirect (via *Index array)',
    'Layer': 'binds layer elements together',
    'LayerElement': 'reference to one layer element',
    'Type': 'type tag',
    'TypedIndex': 'index of the referenced layer element',
    'Version': 'record version',
    'Name': 'layer name',
    'Model': 'scene node (transform) carrying a mesh',
    'MultiLayer': 'flag', 'MultiTake': 'flag', 'Shading': 'shading enabled',
    'Culling': 'backface culling mode',
    'Material': 'surface material',
    'ShadingModel': 'lighting model name',
    'Texture': 'texture object referencing a Video (image)',
    'TextureName': 'texture name', 'Media': 'name of the Video holding the pixels',
    'FileName': 'absolute path of the original image on the authoring machine',
    'Filename': 'absolute path of the original image on the authoring machine',
    'RelativeFilename': 'image path relative to the .fbx',
    'Video': 'image/clip object; Content holds the embedded file bytes',
    'UseMipMap': 'mipmap flag',
    'Content': 'embedded file bytes (here a PNG)',
    'Connections': 'object graph edges',
    'C': "edge: 'OO' child->parent object, 'OP' child->parent property; id 0 = scene root",
    'Takes': 'animation takes (none)', 'Current': 'current take name',
    'Year': 'year', 'Month': 'month', 'Day': 'day', 'Hour': 'hour', 'Minute': 'minute',
    'Second': 'second', 'Millisecond': 'millisecond',
    'Title': 'metadata', 'Subject': 'metadata', 'Author': 'metadata',
    'Keywords': 'metadata', 'Revision': 'metadata', 'Comment': 'metadata',
}


class Node:
    def __init__(self, off, end, name, props):
        self.off, self.end, self.name, self.props, self.children = off, end, name, props, []

    def child(self, name):
        for c in self.children:
            if c.name == name:
                return c

    def find_all(self, name):
        return [c for c in self.children if c.name == name]


class Reader:
    def __init__(self, data):
        self.d = data
        self.problems = []
        self.checks = []
        self.arrays = []           # (node, type, count, enc, clen, ok)

    def problem(self, msg):
        self.problems.append(msg)

    def ok(self, msg):
        self.checks.append(msg)

    def parse(self):
        d = self.d
        magic = b'Kaydara FBX Binary  \x00\x1a\x00'
        if d[:23] != magic:
            self.problem('header magic mismatch')
        self.version = struct.unpack_from('<I', d, 23)[0]
        self.W = 8 if self.version >= 7500 else 4
        self.root = Node(0, len(d), '<root>', [])
        self.top_end = self._walk(27, len(d), self.root, top=True)
        self._footer()
        return self.root

    def _prop(self, o):
        d = self.d
        t = chr(d[o]); o += 1
        if t in SCALAR:
            f, n = SCALAR[t]
            return (t, struct.unpack_from(f, d, o)[0]), o + n
        if t in 'SR':
            n = struct.unpack_from('<I', d, o)[0]
            return (t, d[o + 4:o + 4 + n]), o + 4 + n
        if t in ARRAY:
            cnt, enc, clen = struct.unpack_from('<III', d, o)
            raw = d[o + 12:o + 12 + clen]
            return (t, (cnt, enc, clen, raw, o + 12)), o + 12 + clen
        raise ValueError('unknown property type %r at 0x%x' % (t, o - 1))

    def _walk(self, o, limit, parent, top=False):
        d, W = self.d, self.W
        fmt = '<' + ('Q' if W == 8 else 'I') * 3
        while o < limit:
            end, nprops, plen = struct.unpack_from(fmt, d, o)
            nl = d[o + 3 * W]
            if end == 0 and nprops == 0 and plen == 0 and nl == 0:
                return o + 3 * W + 1           # zero sentinel closes the list
            if not (o < end <= limit):
                self.problem('node at 0x%x has end 0x%x outside parent (limit 0x%x)' % (o, end, limit))
                return o
            name = d[o + 3 * W + 1:o + 3 * W + 1 + nl].decode('latin1')
            p0 = p = o + 3 * W + 1 + nl
            props = []
            for _ in range(nprops):
                pr, p = self._prop(p)
                props.append(pr)
            if p - p0 != plen:
                self.problem('%s@0x%x: property bytes %d != declared %d' % (name, o, p - p0, plen))
            n = Node(o, end, name, props)
            parent.children.append(n)
            if p < end:
                q = self._walk(p, end, n)
                if q != end:
                    self.problem('%s@0x%x: children end at 0x%x, record says 0x%x' % (name, o, q, end))
            o = end
        return o

    def _footer(self):
        d, e = self.d, self.top_end
        tail = d[e:]
        self.footer = tail
        # Observed layout: 16 id bytes, zero padding, u32 version, 120 zero bytes, 16 magic bytes
        if len(tail) < 16 + 4 + 120 + 16:
            self.problem('footer too short (%d bytes)' % len(tail))
            return
        v_off = tail.find(struct.pack('<I', self.version), 16)
        if v_off < 0 or any(tail[16:v_off]) or any(tail[v_off + 4:v_off + 124]):
            self.problem('footer layout differs from expected (zeros/version/zeros)')
        else:
            self.ok('footer: id + %d pad bytes + version %d + 120 zero bytes + 16-byte trailer'
                    % (v_off - 16, self.version))
        if v_off + 124 + 16 != len(tail):
            self.problem('footer has %d unexpected trailing bytes' % (len(tail) - v_off - 140))
        if self.version != struct.unpack_from('<I', self.d, 23)[0]:
            self.problem('footer version differs from header version')

    def array(self, prop):
        t, (cnt, enc, clen, raw, off) = prop
        code, size = ARRAY[t]
        if enc == 0:
            buf = raw
        elif enc == 1:
            z = zlib.decompressobj()
            buf = z.decompress(raw) + z.flush()   # zlib adler32 is checked by zlib on eof
            if not z.eof or z.unused_data:
                raise ValueError('zlib stream at 0x%x incomplete or has trailing data' % off)
        else:
            raise ValueError('unknown array encoding %d at 0x%x' % (enc, off))
        if len(buf) != cnt * size:
            raise ValueError('array at 0x%x: %d bytes, expected %d' % (off, len(buf), cnt * size))
        return list(struct.unpack('<%d%s' % (cnt, code), buf))


def s(v):
    return v.decode('utf-8', 'replace').replace('\x00\x01', '::')


def fmt_prop(p):
    t, v = p
    if t == 'S':
        return repr(s(v))
    if t == 'R':
        return '<%d raw bytes>' % len(v)
    if t in ARRAY:
        cnt, enc, clen, raw, off = v
        return '%s[%d]%s' % (t, cnt, ' zlib(%dB)' % clen if enc == 1 else '')
    return repr(v)


def list_tree(node, depth=0, out=print, show_P=False):
    for c in node.children:
        if c.name == 'P' and not show_P:
            continue
        hidden = sum(1 for g in c.children if g.name == 'P')
        line = '%s%s %s' % ('  ' * depth, c.name, ', '.join(fmt_prop(p) for p in c.props))
        if hidden and not show_P:
            line += '  [%d P records]' % hidden
        out('%-90s # %s' % (line[:90], MEANING.get(c.name, '?')))
        list_tree(c, depth + 1, out, show_P)


def walk_all(node):
    for c in node.children:
        yield c
        yield from walk_all(c)


def verify(r, root):
    d = r.d
    # 1. every zlib array inflates, adler32 passes, size matches count
    n = 0
    for nd in walk_all(root):
        for p in nd.props:
            if p[0] in ARRAY:
                try:
                    r.array(p)
                    n += 1
                except Exception as e:
                    r.problem('%s@0x%x: %s' % (nd.name, nd.off, e))
    r.ok('%d arrays decoded; zlib adler32 + element counts consistent' % n)
    # 2. Definitions counts match Objects
    objs = root.child('Objects')
    actual = {}
    for o in objs.children:
        actual[o.name] = actual.get(o.name, 0) + 1
    actual['GlobalSettings'] = len(root.find_all('GlobalSettings'))
    defs = root.child('Definitions')
    total = defs.child('Count').props[0][1]
    declared = {}
    for ot in defs.find_all('ObjectType'):
        declared[s(ot.props[0][1])] = ot.child('Count').props[0][1]
    if declared != actual or total != sum(declared.values()):
        r.problem('Definitions counts %r (total %d) != objects %r' % (declared, total, actual))
    else:
        r.ok('Definitions object counts match Objects: %r (total %d)' % (declared, total))
    # 3. connections reference existing ids
    ids = {o.props[0][1] for o in objs.children} | {0}
    bad = [c for c in root.child('Connections').children
           if c.props[1][1] not in ids or c.props[2][1] not in ids]
    if bad:
        r.problem('%d connections reference unknown ids' % len(bad))
    else:
        r.ok('all %d connections reference existing objects' % len(root.child('Connections').children))
    # 4. mesh index ranges
    for g in objs.find_all('Geometry'):
        name = s(g.props[1][1])
        try:
            m = mesh_data(r, g)
            nv, nn, nu = len(m['V']) // 3, len(m['N']) // 3, len(m['UV']) // 2
            pvi = m['PVI']
            assert pvi[-1] < 0, 'last polygon not terminated'
            assert all(0 <= (i if i >= 0 else ~i) < nv for i in pvi), 'vertex index out of range'
            assert len(m['NI']) == len(pvi) and len(m['UI']) == len(pvi), 'index arrays length mismatch'
            assert all(0 <= i < nn for i in m['NI']), 'normal index out of range'
            assert all(0 <= i < nu for i in m['UI']), 'uv index out of range'
            assert all(0 <= e < len(pvi) for e in m['E']), 'edge index out of range'
            r.ok('mesh %s: %d verts, %d polys, all indices in range' % (name, nv, sum(1 for i in pvi if i < 0)))
        except Exception as e:
            r.problem('mesh %s: %s' % (name, e))
    # 5. embedded PNG chunk CRCs
    for v in objs.find_all('Video'):
        c = v.child('Content')
        if c is None:
            continue
        png = c.props[0][1]
        try:
            check_png(png)
            r.ok('embedded %s: PNG signature, all chunk CRC32s, IDAT inflate size OK'
                 % s(v.props[1][1]))
        except Exception as e:
            r.problem('embedded image: %s' % e)
    # 6. header CreationTimeStamp vs CreationTime string
    ts = root.child('FBXHeaderExtension').child('CreationTimeStamp')
    f = {c.name: c.props[0][1] for c in ts.children}
    ct = s(root.child('CreationTime').props[0][1])
    stamp = '%04d-%02d-%02d %02d:%02d:%02d:%03d' % (f['Year'], f['Month'], f['Day'], f['Hour'],
                                                     f['Minute'], f['Second'], f['Millisecond'])
    if stamp != ct:
        r.problem('inconsistent metadata (not corruption): CreationTimeStamp %s vs CreationTime %s'
                  % (stamp, ct))
    # 7. declared hashes: search the whole file for any hash/manifest declaration
    hexre = re.compile(rb'(?i)\b[0-9a-f]{40,128}\b')
    declared_hashes = [nd for nd in walk_all(root)
                       if re.search(r'(?i)hash|sha\d|manifest|digest|checksum', nd.name)
                       or any(p[0] == 'S' and hexre.search(p[1]) for p in nd.props)]
    if declared_hashes:
        r.problem('possible hash declarations found but not understood: %r'
                  % [(n.name, n.off) for n in declared_hashes])
    else:
        r.ok('NOTE: file declares no manifest / no sha256 hashes; nothing to compare against')


def check_png(png):
    if png[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('bad PNG signature')
    p, idat, ihdr = 8, b'', None
    while p < len(png):
        n, t = struct.unpack_from('>I4s', png, p)
        body = png[p + 8:p + 8 + n]
        crc = struct.unpack_from('>I', png, p + 8 + n)[0]
        if binascii.crc32(t + body) & 0xffffffff != crc:
            raise ValueError('CRC mismatch in chunk %s' % t)
        if t == b'IHDR':
            ihdr = struct.unpack('>IIBBBBB', body)
        if t == b'IDAT':
            idat += body
        p += 12 + n
        if t == b'IEND':
            break
    if p != len(png):
        raise ValueError('%d bytes after IEND' % (len(png) - p))
    w, h, depth, ctype = ihdr[:4]
    chan = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    raw = zlib.decompress(idat)
    if len(raw) != h * (1 + w * chan * depth // 8):
        raise ValueError('IDAT inflates to %d bytes' % len(raw))
    stride = 1 + w * chan * depth // 8
    if any(raw[i * stride] > 4 for i in range(h)):
        raise ValueError('invalid scanline filter byte')


def mesh_data(r, g):
    def arr(node, name):
        return r.array(node.child(name).props[0])
    ln, lu = g.child('LayerElementNormal'), g.child('LayerElementUV')
    return {'V': arr(g, 'Vertices'), 'PVI': arr(g, 'PolygonVertexIndex'), 'E': arr(g, 'Edges'),
            'N': arr(ln, 'Normals'), 'NI': arr(ln, 'NormalsIndex'),
            'UV': arr(lu, 'UV'), 'UI': arr(lu, 'UVIndex')}


def primary_mesh(root):
    """Primary = geometry of the Model whose name is the un-suffixed base name and
    which carries the most vertices (here wooden_crate_01 -> Cube.020)."""
    objs = root.child('Objects')
    geoms = {g.props[0][1]: g for g in objs.find_all('Geometry')}
    models = {m.props[0][1]: s(m.props[1][1]).split('::')[0] for m in objs.find_all('Model')}
    links = [(c.props[1][1], c.props[2][1]) for c in root.child('Connections').children]
    pairs = [(models[m], geoms[gid]) for gid, m in links if gid in geoms and m in models]
    pairs.sort(key=lambda mg: -mg[1].child('Vertices').props[0][1][0])
    return pairs[0], pairs


def write_obj(r, model_name, g, path, mtl_name, tex_name):
    m = mesh_data(r, g)
    V, N, UV = m['V'], m['N'], m['UV']
    out = ['# extracted by crate_reader.py from %s (geometry %s)' % (os.path.basename(sys.argv[1]),
                                                                    s(g.props[1][1])),
           'mtllib %s' % mtl_name, 'o %s' % model_name]
    out += ['v %.9g %.9g %.9g' % tuple(V[i:i + 3]) for i in range(0, len(V), 3)]
    out += ['vt %.9g %.9g' % tuple(UV[i:i + 2]) for i in range(0, len(UV), 2)]
    out += ['vn %.9g %.9g %.9g' % tuple(N[i:i + 3]) for i in range(0, len(N), 3)]
    out.append('usemtl crate_wood')
    poly = []
    for k, i in enumerate(m['PVI']):
        vi = i if i >= 0 else ~i
        poly.append('%d/%d/%d' % (vi + 1, m['UI'][k] + 1, m['NI'][k] + 1))
        if i < 0:
            out.append('f ' + ' '.join(poly))
            poly = []
    data = ('\n'.join(out) + '\n').encode()
    open(path, 'wb').write(data)
    open(os.path.join(os.path.dirname(path), mtl_name), 'wb').write(
        ('newmtl crate_wood\nKd 0.8 0.8 0.8\nmap_Kd %s\n' % tex_name).encode())
    return data


def main():
    src, outdir = sys.argv[1], sys.argv[2]
    data = open(src, 'rb').read()
    print('file %s  %d bytes  sha256 %s' % (src, len(data), hashlib.sha256(data).hexdigest()))
    r = Reader(data)
    root = r.parse()
    print('format version %d, top-level records end at 0x%x, footer %d bytes\n'
          % (r.version, r.top_end, len(r.footer)))
    print('=== NODE GRAPH ===')
    list_tree(root)
    print('\n=== OBJECT GRAPH (Connections) ===')
    objs = root.child('Objects')
    names = {o.props[0][1]: '%s %r' % (o.name, s(o.props[1][1]).split('::')[0]) for o in objs.children}
    names[0] = 'SceneRoot'
    for c in root.child('Connections').children:
        kind = s(c.props[0][1])
        extra = (' .%s' % s(c.props[3][1])) if len(c.props) > 3 else ''
        print('  %s  %s  ->  %s%s' % (kind, names.get(c.props[1][1]), names.get(c.props[2][1]), extra))

    print('\n=== VERIFY ===')
    verify(r, root)
    for c in r.checks:
        print('  OK   ', c)
    for p in r.problems:
        print('  WARN ', p)

    os.makedirs(outdir, exist_ok=True)
    (mname, g), allpairs = primary_mesh(root)
    print('\n=== EXTRACT ===')
    print('  meshes:', ', '.join('%s(%s, %d verts)' % (n, s(gg.props[1][1]).split('::')[0],
                                                     gg.child('Vertices').props[0][1][0] // 3)
                                  for n, gg in allpairs))
    video = objs.find_all('Video')[0]
    png = video.child('Content').props[0][1]
    tex_name = os.path.basename(s(video.child('RelativeFilename').props[0][1]).replace('\\', '/'))
    open(os.path.join(outdir, tex_name), 'wb').write(png)
    obj = write_obj(r, mname, g, os.path.join(outdir, mname + '.obj'), mname + '.mtl', tex_name)
    print('  primary mesh  %-22s sha256 %s  declared: (none in file)'
          % (mname + '.obj', hashlib.sha256(obj).hexdigest()))
    print('  texture       %-22s sha256 %s  declared: (none in file)'
          % (tex_name, hashlib.sha256(png).hexdigest()))
    # raw geometry bytes (inflated Vertices array) so the hash is of file-native data too
    vraw = zlib.decompress(g.child('Vertices').props[0][1][3])
    print('  (raw inflated Vertices array of %s: sha256 %s)' % (mname, hashlib.sha256(vraw).hexdigest()))
    return 1 if r.problems and any(not p.startswith('inconsistent metadata') for p in r.problems) else 0


if __name__ == '__main__':
    sys.exit(main())
