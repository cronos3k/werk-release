#!/usr/bin/env python3
"""Open crate-nc-v1.fbx, list its node graph with meanings, verify integrity,
and extract the primary mesh (OBJ) and the embedded texture (PNG).

Usage:  python -I fbx_extract.py crate-nc-v1.fbx [outdir]

The input is opened read-only and never modified.
Layout rules used here were inferred from the bytes of this file (see REPORT.md);
the zlib/PNG checks rely on Python's stdlib, not on anything in the file.
"""
import hashlib
import json
import os
import struct
import sys
import zlib

MAGIC = b'Kaydara FBX Binary  \x00\x1a\x00'
SCALAR = {'Y': ('<h', 2), 'C': ('<B', 1), 'I': ('<i', 4), 'F': ('<f', 4),
          'D': ('<d', 8), 'L': ('<q', 8)}
ARRAY = {'f': ('f', 4), 'd': ('d', 8), 'l': ('q', 8), 'i': ('i', 4), 'b': ('B', 1)}
NAME_SEP = b'\x00\x01'   # object names look like b'<name>\x00\x01<Class>'

# Meanings are my reading of the self-describing node names plus their observed
# structure; the file itself carries no glossary.
MEANINGS = {
    'FBXHeaderExtension': 'file header block (format/version metadata)',
    'FBXHeaderVersion': 'version of the header block',
    'FBXVersion': 'format version (matches the 7400 after the magic and in the footer)',
    'EncryptionType': 'encryption flag (0 = none)',
    'CreationTimeStamp': 'creation date/time broken into fields',
    'Creator': 'name of the exporting application',
    'SceneInfo': 'scene metadata object (title/author/etc., all empty here)',
    'MetaData': 'document metadata strings',
    'Properties70': 'typed property list; each P = (name, type, label, flags, value...)',
    'P': 'one property: name, type, sub-type, flags, value(s)',
    'FileId': '16 opaque bytes identifying the file (not verifiable from inside)',
    'CreationTime': 'creation time as a string',
    'GlobalSettings': 'scene-wide settings: axes, unit scale, frame rate, time span',
    'Documents': 'list of documents in the file',
    'Document': 'scene document; RootNode gives the id of the scene root (0)',
    'RootNode': 'id of the scene root object',
    'References': 'external references (empty)',
    'Definitions': 'object type census + default property templates per type',
    'ObjectType': 'one object class, with Count and its PropertyTemplate',
    'PropertyTemplate': 'default property values for the class',
    'Count': 'number of items',
    'Version': 'version number of the enclosing block',
    'Objects': 'all scene objects (geometry, models, material, texture, video)',
    'Geometry': 'mesh data: id, name, kind',
    'GeometryVersion': 'version of the geometry block',
    'Vertices': 'control-point positions, flat xyz doubles',
    'PolygonVertexIndex': 'face corner -> vertex index; a negative value v means ~v and ends the polygon',
    'Edges': 'edge list as indices into PolygonVertexIndex',
    'LayerElementNormal': 'per-corner normals layer',
    'LayerElementUV': 'per-corner texture-coordinate layer',
    'LayerElementMaterial': 'material assignment layer',
    'MappingInformationType': 'what the layer maps onto (ByPolygonVertex = each face corner, AllSame = whole mesh)',
    'ReferenceInformationType': 'how values are looked up (IndexToDirect = via a separate index array)',
    'Normals': 'normal vectors, flat xyz doubles',
    'NormalsIndex': 'corner -> index into Normals',
    'UV': 'texture coordinates, flat uv doubles',
    'UVIndex': 'corner -> index into UV',
    'Materials': 'material slot index(es)',
    'Name': 'layer name',
    'Layer': 'layer bundle tying the element layers together',
    'LayerElement': 'reference to one layer element by Type and TypedIndex',
    'Type': 'type string',
    'TypedIndex': 'which element of that type',
    'Model': 'scene node (transform) that instances a geometry',
    'MultiLayer': 'flag', 'MultiTake': 'flag', 'Shading': 'shading flag',
    'Culling': 'back-face culling mode',
    'Material': 'surface material',
    'ShadingModel': 'shading model name',
    'Texture': 'texture object referencing a Video (image) by name',
    'TextureName': 'texture name', 'Media': 'name of the Video holding the pixels',
    'FileName': 'original absolute path of the image at export time',
    'Filename': 'original absolute path of the image at export time',
    'RelativeFilename': 'image path relative to the file',
    'Video': 'image clip; Content holds the embedded image bytes',
    'UseMipMap': 'mip-map flag',
    'Content': 'embedded image file bytes',
    'Connections': 'graph edges between objects',
    'C': "edge: kind ('OO' object->object, 'OP' object->property), child id, parent id[, property]",
    'Takes': 'animation takes (none)', 'Current': 'current take name',
    'Year': 'date field', 'Month': 'date field', 'Day': 'date field', 'Hour': 'time field',
    'Minute': 'time field', 'Second': 'time field', 'Millisecond': 'time field',
    'Title': 'metadata string', 'Subject': 'metadata string', 'Author': 'metadata string',
    'Keywords': 'metadata string', 'Revision': 'metadata string', 'Comment': 'metadata string',
}


class Node:
    def __init__(self, name, props, offset, end):
        self.name, self.props, self.offset, self.end = name, props, offset, end
        self.children = []

    def child(self, name):
        for c in self.children:
            if c.name == name:
                return c
        return None

    def all(self, name):
        return [c for c in self.children if c.name == name]


class Reader:
    def __init__(self, data):
        self.d = data
        self.checks = []   # (description, ok)
        self.arrays = 0
        self.zarrays = 0

    def check(self, desc, ok):
        self.checks.append((desc, bool(ok)))
        return ok

    def read_props(self, o, n):
        d, out = self.d, []
        for _ in range(n):
            t = chr(d[o]); o += 1
            if t in SCALAR:
                fmt, sz = SCALAR[t]
                out.append((t, struct.unpack_from(fmt, d, o)[0])); o += sz
            elif t in 'SR':
                ln = struct.unpack_from('<I', d, o)[0]; o += 4
                out.append((t, d[o:o + ln])); o += ln
            elif t in ARRAY:
                cnt, enc, clen = struct.unpack_from('<III', d, o); o += 12
                raw = d[o:o + clen]; o += clen
                self.arrays += 1
                if enc == 1:
                    self.zarrays += 1
                    raw = zlib.decompress(raw)   # verifies the adler32 trailer
                elif enc != 0:
                    raise ValueError('unknown array encoding %d at %#x' % (enc, o))
                ch, sz = ARRAY[t]
                if len(raw) != cnt * sz:
                    raise ValueError('array length mismatch at %#x' % o)
                out.append((t, list(struct.unpack('<%d%s' % (cnt, ch), raw))))
            else:
                raise ValueError('unknown property type %r at %#x' % (t, o - 1))
        return out, o

    def read_node(self, o):
        end, n, plen, nl = struct.unpack_from('<IIIB', self.d, o)
        if end == 0 and n == 0 and plen == 0 and nl == 0:
            return None, o + 13
        name = self.d[o + 13:o + 13 + nl].decode('ascii')
        p0 = o + 13 + nl
        props, pe = self.read_props(p0, n)
        if pe != p0 + plen:
            raise ValueError('%s @%#x: property list length mismatch' % (name, o))
        node = Node(name, props, o, end)
        c = pe
        if c < end:
            while True:
                ch, c = self.read_node(c)
                if ch is None:
                    break
                node.children.append(ch)
        if c != end:
            raise ValueError('%s @%#x: end offset %#x but children end at %#x' % (name, o, end, c))
        return node, end

    def parse(self):
        d = self.d
        self.check('magic is %r' % MAGIC, d[:23] == MAGIC)
        self.version = struct.unpack_from('<I', d, 23)[0]
        roots, o = [], 27
        while True:
            n, o = self.read_node(o)
            if n is None:
                break
            roots.append(n)
        self.check('all %d top-level nodes, nested end offsets and property lengths consistent' % len(roots), True)
        self.check('%d arrays decoded to declared element counts (%d zlib-compressed, adler32 verified)'
                   % (self.arrays, self.zarrays), True)
        self.tree_end = o
        self.parse_footer(o)
        return roots

    def parse_footer(self, o):
        d = self.d
        self.footer_id = d[o:o + 16]
        p = o + 16
        pad = (-p) % 16
        self.check('footer padding (%d bytes) is zero' % pad, d[p:p + pad] == b'\0' * pad)
        p += pad
        fv = struct.unpack_from('<I', d, p)[0]
        self.check('footer version %d equals header version %d' % (fv, self.version), fv == self.version)
        p += 4
        tail = d[p:]
        self.check('footer: 120 zero bytes then 16-byte trailer, ending exactly at EOF',
                   len(tail) == 136 and tail[:120] == b'\0' * 120)
        self.footer_trailer = tail[120:]


def sname(b):
    """Split b'name\\x00\\x01Class' into ('name', 'Class')."""
    if NAME_SEP in b:
        a, c = b.split(NAME_SEP, 1)
        return a.decode('utf-8', 'replace'), c.decode('utf-8', 'replace')
    return b.decode('utf-8', 'replace'), ''


def fmt_props(props):
    out = []
    for t, v in props:
        if t in ARRAY:
            out.append('%s[%d]' % (t, len(v)))
        elif t == 'S':
            n, c = sname(v)
            out.append(repr(n + ('::' + c if c else '')))
        elif t == 'R':
            out.append('<%d raw bytes>' % len(v))
        elif t == 'D':
            out.append('%g' % v)
        else:
            out.append(str(v))
    return ' '.join(out)


def print_tree(nodes, depth=0, collapse_p=True):
    for n in nodes:
        m = MEANINGS.get(n.name, '?')
        if collapse_p and n.name == 'Properties70' and depth <= 1:
            print('%s%s  (%d property templates/defaults)  -- %s' % ('  ' * depth, n.name, len(n.children), m))
            continue
        print('%s%s %s  -- %s' % ('  ' * depth, n.name, fmt_props(n.props), m))
        print_tree(n.children, depth + 1, collapse_p)


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def png_check(r, png, label):
    if not r.check('%s: PNG signature' % label, png[:8] == b'\x89PNG\r\n\x1a\n'):
        return
    p, chunks = 8, []
    while p + 12 <= len(png):
        ln, typ = struct.unpack_from('>I4s', png, p)
        body = png[p + 8:p + 8 + ln]
        crc = struct.unpack_from('>I', png, p + 8 + ln)[0]
        r.check('%s: chunk %s crc32' % (label, typ.decode()), zlib.crc32(typ + body) & 0xffffffff == crc)
        chunks.append(typ)
        p += 12 + ln
    r.check('%s: chunks end exactly at IEND/EOF' % label, p == len(png) and chunks[-1] == b'IEND')
    w, h = struct.unpack_from('>II', png, 16)
    return w, h


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    show_tree = '--no-tree' not in sys.argv
    src = args[0] if args else 'crate-nc-v1.fbx'
    out = args[1] if len(args) > 1 else 'extracted'
    with open(src, 'rb') as f:
        data = f.read()
    print('file: %s  size=%d  sha256=%s' % (src, len(data), sha256(data)))
    r = Reader(data)
    roots = r.parse()
    print('format version (after magic): %d' % r.version)

    if show_tree:
        print('\n=== NODE TREE ===')
        print_tree(roots)

    top = {n.name: n for n in roots}
    r.check('FBXHeaderExtension/FBXVersion equals header version',
            top['FBXHeaderExtension'].child('FBXVersion').props[0][1] == r.version)

    # ---- object graph
    objs = {}
    for o in top['Objects'].children:
        oid = o.props[0][1]
        name, cls = sname(o.props[1][1])
        objs[oid] = (o.name, name, o)
    conns = [(c.props[0][1].decode(), c.props[1][1], c.props[2][1],
              c.props[3][1].decode() if len(c.props) > 3 else None)
             for c in top['Connections'].all('C')]
    print('\n=== OBJECT GRAPH (child -> parent) ===')

    def label(i):
        return 'scene-root(0)' if i == 0 else '%s "%s" (%d)' % (objs[i][0], objs[i][1], i)

    for kind, ch, pa, prop in conns:
        r.check('connection endpoints exist: %d -> %d' % (ch, pa), ch in objs and (pa == 0 or pa in objs))
        print('  %s %s -> %s%s' % (kind, label(ch), label(pa), ('  [property %s]' % prop) if prop else ''))

    # Definitions census vs actual objects
    actual = {}
    for t, _, _ in objs.values():
        actual[t] = actual.get(t, 0) + 1
    for ot in top['Definitions'].all('ObjectType'):
        t = ot.props[0][1].decode()
        if t == 'GlobalSettings':
            continue
        declared = ot.child('Count').props[0][1]
        r.check('Definitions declares %d %s, found %d' % (declared, t, actual.get(t, 0)),
                declared == actual.get(t, 0))

    # ---- geometries
    geoms = {}
    print('\n=== GEOMETRIES ===')
    for oid, (t, name, n) in objs.items():
        if t != 'Geometry':
            continue
        V = n.child('Vertices').props[0][1]
        I = n.child('PolygonVertexIndex').props[0][1]
        nv = len(V) // 3
        ln = n.child('LayerElementNormal'); luv = n.child('LayerElementUV')
        N = ln.child('Normals').props[0][1]; NI = ln.child('NormalsIndex').props[0][1]
        UV = luv.child('UV').props[0][1]; UVI = luv.child('UVIndex').props[0][1]
        npoly = sum(1 for x in I if x < 0)
        r.check('%s: vertex array is xyz triples' % name, len(V) % 3 == 0)
        r.check('%s: every face index in range [0,%d) after ~ on negatives' % (name, nv),
                all(0 <= (x if x >= 0 else ~x) < nv for x in I))
        r.check('%s: last corner closes a polygon' % name, I[-1] < 0)
        r.check('%s: NormalsIndex/UVIndex have one entry per corner' % name,
                len(NI) == len(I) == len(UVI))
        r.check('%s: normal/uv indices in range' % name,
                all(0 <= x < len(N) // 3 for x in NI) and all(0 <= x < len(UV) // 2 for x in UVI))
        geoms[oid] = dict(name=name, V=V, I=I, N=N, NI=NI, UV=UV, UVI=UVI)
        print('  %s (%d): %d vertices, %d polygons, %d corners, %d normals, %d uvs'
              % (name, oid, nv, npoly, len(I), len(N) // 3, len(UV) // 2))

    # ---- primary mesh: model named without a part suffix; also the largest geometry
    models = {oid: v for oid, v in objs.items() if v[0] == 'Model'}
    model_geom = {pa: ch for k, ch, pa, _ in conns if k == 'OO' and ch in geoms and pa in models}
    largest = max(geoms, key=lambda g: len(geoms[g]['I']))
    by_name = [m for m in models if models[m][1] == 'wooden_crate_01']
    prim_model = by_name[0] if by_name else [m for m, g in model_geom.items() if g == largest][0]
    prim_geom = model_geom[prim_model]
    print('\nprimary mesh: model "%s" -> geometry "%s" (largest geometry: %s)'
          % (models[prim_model][1], geoms[prim_geom]['name'], geoms[largest]['name']))

    # ---- textures
    videos = {oid: v for oid, v in objs.items() if v[0] == 'Video'}
    os.makedirs(out, exist_ok=True)
    results = []

    g = geoms[prim_geom]
    mnode = models[prim_model][2]
    xf = {p.props[0][1].decode(): [x[1] for x in p.props[4:]] for p in mnode.child('Properties70').all('P')}
    lines = ['# primary mesh from %s' % os.path.basename(src),
             '# model "%s", geometry "%s"; coordinates are geometry-local (model transform NOT applied)'
             % (models[prim_model][1], g['name']),
             '# model Lcl Rotation=%s Lcl Scaling=%s' % (xf.get('Lcl Rotation'), xf.get('Lcl Scaling')),
             'mtllib none', 'o %s' % models[prim_model][1]]
    V, N, UV = g['V'], g['N'], g['UV']
    lines += ['v %r %r %r' % tuple(V[i:i + 3]) for i in range(0, len(V), 3)]
    lines += ['vt %r %r' % tuple(UV[i:i + 2]) for i in range(0, len(UV), 2)]
    lines += ['vn %r %r %r' % tuple(N[i:i + 3]) for i in range(0, len(N), 3)]
    face = []
    for c, x in enumerate(g['I']):
        vi = x if x >= 0 else ~x
        face.append('%d/%d/%d' % (vi + 1, g['UVI'][c] + 1, g['NI'][c] + 1))
        if x < 0:
            lines.append('f ' + ' '.join(face)); face = []
    lines.remove('mtllib none')
    obj = ('\n'.join(lines) + '\n').encode()
    mesh_path = os.path.join(out, models[prim_model][1] + '.obj')
    with open(mesh_path, 'wb') as f:
        f.write(obj)
    results.append(dict(file=mesh_path, kind='mesh (Wavefront OBJ, converted)', sha256=sha256(obj),
                        source_sha256=sha256(struct.pack('<%dd' % len(V), *V)), declared_sha256=None))

    for vid, (_, vname, vn) in videos.items():
        content = vn.child('Content').props[0][1]
        wh = png_check(r, content, 'video "%s"' % vname)
        tex_path = os.path.join(out, vname)
        with open(tex_path, 'wb') as f:
            f.write(content)
        results.append(dict(file=tex_path, kind='texture %dx%d PNG (verbatim bytes)' % wh,
                            sha256=sha256(content), declared_sha256=None))
        break   # one texture is enough

    # ---- declared hashes
    print('\n=== DECLARED HASHES ===')
    print('  none: the file contains no manifest and no sha256/md5/crc values for its contents.')
    print('  opaque ids that cannot be verified from inside the file:')
    print('    FileId      %s' % top['FileId'].props[0][1].hex())
    print('    footer id   %s' % r.footer_id.hex())
    print('    trailer     %s' % r.footer_trailer.hex())

    print('\n=== INTEGRITY CHECKS ===')
    bad = 0
    for desc, ok in r.checks:
        bad += not ok
        print('  [%s] %s' % ('ok' if ok else 'FAIL', desc))
    print('  %d checks, %d failed' % (len(r.checks), bad))

    print('\n=== EXTRACTED ===')
    for x in results:
        print('  %s  %s\n    sha256 %s  (declared: none in file)' % (x['file'], x['kind'], x['sha256']))
    with open(os.path.join(out, 'extracted.json'), 'w') as f:
        json.dump(dict(source=src, source_sha256=sha256(data), files=results,
                       checks=[dict(check=d, ok=o) for d, o in r.checks]), f, indent=1)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
