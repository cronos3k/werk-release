#!/usr/bin/env python3
"""
nc_fbx.py -- stdlib reader for binary FBX, for roundNC ground truth.

Used by build_controls.py and build_expectations.py to describe the FBX
control AS STORED (plan 1.3): the embedded texture blob (Objects/Video/Content)
and the geometry arrays (Objects/Geometry/Vertices, PolygonVertexIndex).

Binary FBX node record (no official spec; this is the widely documented layout):
  header  "Kaydara FBX Binary  \\x00\\x1a\\x00" (23 B) + uint32 version
  node    EndOffset, NumProperties, PropertyListLen  (uint32, or uint64 if
          version >= 7500), uint8 NameLen, Name, properties, nested nodes,
          then a null record (13 or 25 zero bytes) if the node has children.
  props   Y int16, C bool, I int32, F float32, D float64, L int64,
          f/d/l/i/b arrays (uint32 count, uint32 encoding 0|1=zlib,
          uint32 byte length, data), S string / R raw (uint32 length, data).

Canonical FBX mesh dump (Tier 2): Objects/Geometry nodes of class "Mesh" in
file order; each Vertices array element order (float64 in the file),
converted to float32 little-endian; no dedup, no reindex, no node transforms.
Triangle count = sum(n - 2) over polygons in PolygonVertexIndex (a polygon
ends at a negative index, stored as ~index).

Standard library only.
"""

import struct
import zlib

MAGIC = b"Kaydara FBX Binary  \x00\x1a\x00"
_ARR = {"f": ("f", 4), "d": ("d", 8), "l": ("q", 8), "i": ("i", 4), "b": ("b", 1)}


class Node:
    __slots__ = ("name", "props", "children", "offset", "end", "prop_offsets")

    def __init__(self, name, props, children, offset, prop_offsets, end=None):
        self.end = end
        self.name = name
        self.props = props
        self.children = children
        self.offset = offset
        self.prop_offsets = prop_offsets  # absolute offset of each prop's payload

    def find(self, name):
        return [c for c in self.children if c.name == name]

    def first(self, name):
        for c in self.children:
            if c.name == name:
                return c
        return None


def _read_prop(b, off):
    t = chr(b[off])
    off += 1
    if t == "Y":
        return struct.unpack_from("<h", b, off)[0], off, off + 2
    if t == "C":
        return bool(b[off]), off, off + 1
    if t == "I":
        return struct.unpack_from("<i", b, off)[0], off, off + 4
    if t == "F":
        return struct.unpack_from("<f", b, off)[0], off, off + 4
    if t == "D":
        return struct.unpack_from("<d", b, off)[0], off, off + 8
    if t == "L":
        return struct.unpack_from("<q", b, off)[0], off, off + 8
    if t in ("S", "R"):
        n = struct.unpack_from("<I", b, off)[0]
        data = b[off + 4: off + 4 + n]
        return (data if t == "R" else data), off + 4, off + 4 + n
    if t in _ARR:
        cnt, enc, clen = struct.unpack_from("<III", b, off)
        raw = b[off + 12: off + 12 + clen]
        if enc == 1:
            raw = zlib.decompress(raw)
        elif enc != 0:
            raise ValueError("array encoding %d" % enc)
        code, sz = _ARR[t]
        if len(raw) != cnt * sz:
            raise ValueError("array length mismatch")
        return list(struct.unpack("<%d%s" % (cnt, code), raw)), off + 12, off + 12 + clen
    raise ValueError("unknown property type %r at %d" % (t, off - 1))


def _read_node(b, off, wide):
    if wide:
        end, nprop, plen = struct.unpack_from("<QQQ", b, off)
        off += 24
    else:
        end, nprop, plen = struct.unpack_from("<III", b, off)
        off += 12
    nlen = b[off]
    off += 1
    if end == 0:
        return None, off + nlen
    start = off - (25 if wide else 13)
    name = b[off: off + nlen].decode("ascii")
    off += nlen
    props, poffs = [], []
    pend = off + plen
    for _ in range(nprop):
        v, poff, off = _read_prop(b, off)
        props.append(v)
        poffs.append(poff)
    if off != pend:
        raise ValueError("property list length mismatch in %s" % name)
    children = []
    null_len = 25 if wide else 13
    while off < end:
        if end - off == null_len and b[off:end] == b"\x00" * null_len:
            off = end
            break
        c, off = _read_node(b, off, wide)
        if c is None:
            break
        children.append(c)
    return Node(name, props, children, start, poffs, end), end


def parse(b):
    """Return (version, [top-level Node])."""
    if b[:23] != MAGIC:
        raise ValueError("not a binary FBX")
    ver = struct.unpack_from("<I", b, 23)[0]
    wide = ver >= 7500
    off = 27
    top = []
    while off < len(b):
        n, off = _read_node(b, off, wide)
        if n is None:
            break
        top.append(n)
    return ver, top


def node_span(b, path):
    """(start, end) byte span of the first node at path, e.g.
    ['FBXHeaderExtension', 'CreationTimeStamp']."""
    _, top = parse(b)
    cur = top
    n = None
    for name in path:
        n = next(x for x in cur if x.name == name)
        cur = n.children
    return n.offset, n.end


def _obj_name(prop):
    """FBX object name 'name\\x00\\x01Class' -> 'name'."""
    s = prop.decode("utf-8", "replace") if isinstance(prop, bytes) else str(prop)
    return s.split("\x00\x01")[0]


def describe(b):
    """Everything roundNC records about an FBX, as stored."""
    ver, top = parse(b)
    objs = [n for n in top if n.name == "Objects"]
    if len(objs) != 1:
        raise ValueError("expected one Objects node")
    objs = objs[0]
    geoms, videos = [], []
    for n in objs.children:
        if n.name == "Geometry" and len(n.props) >= 3 and n.props[2] == b"Mesh":
            v = n.first("Vertices").props[0]
            pvi = n.first("PolygonVertexIndex").props[0]
            polys, tri, cur = 0, 0, 0
            for x in pvi:
                cur += 1
                if x < 0:
                    polys += 1
                    tri += cur - 2
                    cur = 0
            if cur:
                raise ValueError("unterminated polygon in %s" % _obj_name(n.props[1]))
            pos = [(v[i], v[i + 1], v[i + 2]) for i in range(0, len(v), 3)]
            pos32 = [struct.unpack("<3f", struct.pack("<3f", *p)) for p in pos]
            lossless = all(a == b_ for p, q in zip(pos, pos32) for a, b_ in zip(p, q))
            geoms.append({"id": n.props[0], "name": _obj_name(n.props[1]),
                          "offset": n.offset, "positions": pos32,
                          "f64_to_f32_lossless": lossless,
                          "polygon_count": polys, "triangle_count": tri,
                          "polygon_vertex_index_count": len(pvi)})
        elif n.name == "Video":
            c = n.first("Content")
            fn = n.first("Filename") or n.first("FileName")
            rf = n.first("RelativeFilename")
            content = c.props[0] if c and c.props else None
            videos.append({"id": n.props[0], "name": _obj_name(n.props[1]),
                           "filename": fn.props[0].decode("utf-8", "replace") if fn else None,
                           "relative_filename": rf.props[0].decode("utf-8", "replace") if rf else None,
                           "content": content,
                           "content_offset": c.prop_offsets[0] if c and content else None})
    header = {}
    for n in top:
        if n.name == "FBXHeaderExtension":
            for k in ("FBXHeaderVersion", "FBXVersion", "EncryptionType", "Creator"):
                c = n.first(k)
                if c and c.props:
                    p = c.props[0]
                    header[k] = p.decode("utf-8", "replace") if isinstance(p, bytes) else p
            ts = n.first("CreationTimeStamp")
            if ts:
                header["CreationTimeStamp"] = {c.name: c.props[0] for c in ts.children if c.props}
        elif n.name in ("CreationTime", "Creator", "FileId") and n.props:
            p = n.props[0]
            header[n.name] = p.decode("utf-8", "replace") if n.name != "FileId" else p.hex()
    return {"version": ver, "header": header, "geometries": geoms, "videos": videos,
            "top_level": [n.name for n in top]}
