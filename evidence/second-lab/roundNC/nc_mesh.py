#!/usr/bin/env python3
"""
nc_mesh.py -- shared helpers for roundNC (negative-control round).

Used by build_expectations.py (to WRITE ground truth) and by grade_nc.py (to
READ agent artifacts). One code path for both, so the grader cannot disagree
with the builder about what "the canonical mesh dump" means.

Canonical mesh dump (plan section 1.3, Tier 2):
  positions only, float32 little-endian, in the file's own storage order,
  no dedup, no reindex. For a glTF/GLB with several primitives, "storage
  order" is defined here as: meshes[] in index order, then primitives[] in
  index order, each primitive's POSITION accessor read element by element.
  build_expectations.py checks that this order equals ascending byte offset
  in the buffer, and records the result, so the definition is auditable.

Standard library only.
"""

import hashlib
import json
import os
import struct

TOL = 1e-5  # plan 1.3: values matching to 1e-5 after parse

_COMP = {5126: ("f", 4)}  # only float32 POSITION is accepted (glTF core rule)
_NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
_ICOMP = {5121: ("B", 1), 5123: ("H", 2), 5125: ("I", 4)}


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- glTF / GLB

def parse_glb(b):
    """Return (json_dict, bin_chunk_bytes or None). Raises ValueError."""
    if len(b) < 20 or b[:4] != b"glTF":
        raise ValueError("not a GLB (magic)")
    ver, total = struct.unpack_from("<II", b, 4)
    if ver != 2:
        raise ValueError("GLB version %d" % ver)
    off = 12
    js = None
    binc = None
    while off + 8 <= min(total, len(b)):
        clen, ctype = struct.unpack_from("<II", b, off)
        data = b[off + 8: off + 8 + clen]
        if ctype == 0x4E4F534A and js is None:
            js = json.loads(data.decode("utf-8"))
        elif ctype == 0x004E4942 and binc is None:
            binc = data
        off += 8 + clen
    if js is None:
        raise ValueError("GLB without JSON chunk")
    return js, binc


def _accessor_bytes(gl, acc_idx, buffers):
    acc = gl["accessors"][acc_idx]
    bv = gl["bufferViews"][acc["bufferView"]]
    buf = buffers[bv.get("buffer", 0)]
    ncomp = _NCOMP[acc["type"]]
    return acc, bv, buf, ncomp


def read_positions(gl, acc_idx, buffers):
    acc, bv, buf, ncomp = _accessor_bytes(gl, acc_idx, buffers)
    if acc["componentType"] not in _COMP or ncomp != 3:
        raise ValueError("POSITION accessor is not float32 VEC3")
    base = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = bv.get("byteStride") or 12
    out = []
    for i in range(acc["count"]):
        out.append(struct.unpack_from("<3f", buf, base + i * stride))
    return out, base


def read_index_count(gl, prim, n_pos):
    if "indices" in prim:
        return gl["accessors"][prim["indices"]]["count"]
    return n_pos


def gltf_primitives(gl, buffers):
    """List of dicts, one per primitive, in canonical order."""
    prims = []
    for mi, mesh in enumerate(gl.get("meshes", [])):
        for pi, prim in enumerate(mesh.get("primitives", [])):
            mode = prim.get("mode", 4)
            if mode != 4:
                raise ValueError("primitive mode %d is not TRIANGLES" % mode)
            pos, byte_off = read_positions(gl, prim["attributes"]["POSITION"], buffers)
            nidx = read_index_count(gl, prim, len(pos))
            prims.append({
                "mesh_index": mi, "mesh_name": mesh.get("name"),
                "primitive_index": pi, "positions": pos,
                "triangle_count": nidx // 3, "position_byte_offset": byte_off,
            })
    return prims


def load_gltf_any(path):
    """Parse a .glb, or a .gltf with its external .bin buffers resolved
    relative to the .gltf. Returns (gl_json, prims)."""
    with open(path, "rb") as f:
        b = f.read()
    if b[:4] == b"glTF":
        gl, binc = parse_glb(b)
        buffers = [binc or b""]
        # GLB may also reference external buffers beyond index 0
        for i, bd in enumerate(gl.get("buffers", [])):
            if i > 0:
                buffers.append(_load_uri(path, bd.get("uri")))
    else:
        gl = json.loads(b.decode("utf-8"))
        buffers = [_load_uri(path, bd.get("uri")) for bd in gl.get("buffers", [])]
    return gl, gltf_primitives(gl, buffers)


def _load_uri(gltf_path, uri):
    if uri is None:
        raise ValueError("buffer without uri")
    if uri.startswith("data:"):
        import base64
        return base64.b64decode(uri.split(",", 1)[1])
    p = os.path.join(os.path.dirname(gltf_path), uri)
    with open(p, "rb") as f:
        return f.read()


# ------------------------------------------------------------- canonical dump

def canonical_dump(positions):
    return b"".join(struct.pack("<3f", *p) for p in positions)


def bbox(positions):
    xs = [p[0] for p in positions]
    ys = [p[1] for p in positions]
    zs = [p[2] for p in positions]
    return [min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)]


def mesh_record(positions, triangle_count):
    d = canonical_dump(positions)
    return {
        "vertex_count": len(positions),
        "triangle_count": triangle_count,
        "bbox": bbox(positions),
        "dump_sha256": sha256_bytes(d),
        "dump_size": len(d),
    }


# ------------------------------------------------------------ text/ply dumps

def parse_obj(text):
    pos = []
    for line in text.splitlines():
        s = line.split()
        if len(s) >= 4 and s[0] == "v":
            pos.append((float(s[1]), float(s[2]), float(s[3])))
    return pos


def parse_xyz_text(text):
    """Lines of three numbers (comma, semicolon or whitespace separated).
    Lines that do not parse as exactly 3+ leading floats are skipped."""
    pos = []
    for line in text.splitlines():
        s = line.replace(",", " ").replace(";", " ").split()
        if len(s) < 3:
            continue
        try:
            pos.append((float(s[0]), float(s[1]), float(s[2])))
        except ValueError:
            continue
    return pos


def parse_ply(b):
    end = b.find(b"end_header")
    if not b.startswith(b"ply") or end < 0:
        raise ValueError("not ply")
    nl = b.find(b"\n", end)
    header = b[:nl].decode("ascii", "replace").splitlines()
    body = b[nl + 1:]
    fmt = None
    nvert = 0
    props = []
    cur = None
    for h in header:
        t = h.split()
        if not t:
            continue
        if t[0] == "format":
            fmt = t[1]
        elif t[0] == "element":
            cur = t[1]
            if cur == "vertex":
                nvert = int(t[2])
        elif t[0] == "property" and cur == "vertex":
            if t[1] == "list":
                raise ValueError("list property on vertex")
            props.append((t[1], t[2]))
    names = [p[1] for p in props]
    ix, iy, iz = names.index("x"), names.index("y"), names.index("z")
    if fmt == "ascii":
        lines = body.decode("ascii", "replace").splitlines()
        out = []
        for ln in lines[:nvert]:
            v = ln.split()
            out.append((float(v[ix]), float(v[iy]), float(v[iz])))
        return out
    if fmt != "binary_little_endian":
        raise ValueError("ply format %s" % fmt)
    tmap = {"float": "f", "float32": "f", "double": "d", "float64": "d",
            "uchar": "B", "uint8": "B", "char": "b", "int8": "b",
            "short": "h", "int16": "h", "ushort": "H", "uint16": "H",
            "int": "i", "int32": "i", "uint": "I", "uint32": "I"}
    sf = "<" + "".join(tmap[p[0]] for p in props)
    sz = struct.calcsize(sf)
    out = []
    for i in range(nvert):
        v = struct.unpack_from(sf, body, i * sz)
        out.append((float(v[ix]), float(v[iy]), float(v[iz])))
    return out


MESH_TEXT_EXT = (".obj", ".txt", ".csv", ".xyz", ".tsv")


def positions_from_file(path):
    """Try to read vertex positions out of an agent artifact.
    Returns (kind, positions, triangle_count_or_None) or None.
    kind is 'binary' for glb/gltf/ply-binary, 'text' for text dumps."""
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in (".glb", ".gltf"):
            gl, prims = load_gltf_any(path)
            pos = [p for pr in prims for p in pr["positions"]]
            tri = sum(pr["triangle_count"] for pr in prims)
            return ("binary", pos, tri) if pos else None
        if ext == ".ply":
            with open(path, "rb") as f:
                b = f.read()
            kind = "text" if b"format ascii" in b[:200] else "binary"
            pos = parse_ply(b)
            return (kind, pos, None) if pos else None
        if ext in MESH_TEXT_EXT:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                t = f.read()
            pos = parse_obj(t) if ext == ".obj" else parse_xyz_text(t)
            return ("text", pos, None) if pos else None
    except Exception:
        return None
    return None


def compare_positions(got, exp_rec, exp_positions=None):
    """Return one of: 'VALUES' (all positions in order within TOL),
    'COUNT+BBOX' (count equal, bbox within TOL), or None."""
    if len(got) != exp_rec["vertex_count"]:
        return None
    if exp_positions is not None:
        ok = True
        for a, b in zip(got, exp_positions):
            if abs(a[0] - b[0]) > TOL or abs(a[1] - b[1]) > TOL or abs(a[2] - b[2]) > TOL:
                ok = False
                break
        if ok:
            return "VALUES"
    gb = bbox(got)
    if all(abs(x - y) <= TOL for x, y in zip(gb, exp_rec["bbox"])):
        return "COUNT+BBOX"
    return None


def dump_floats(dump_bytes):
    n = len(dump_bytes) // 12
    return [struct.unpack_from("<3f", dump_bytes, i * 12) for i in range(n)]
