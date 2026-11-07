#!/usr/bin/env python3
"""glb.py — read an arbitrary glTF 2.0 binary, write a clean one.

The pipeline's input is "a bare GLB", which in practice means a file with a
node hierarchy, several primitives, several materials and images buried in
buffer views. This module flattens that into ONE indexed triangle mesh in
model space with per-vertex POSITION / NORMAL / TEXCOORD_0 / COLOR_0, plus a
material table and the image blobs, which is the shape every producer
downstream wants.

It reads only the parts of glTF that werk's profile can carry honestly. An
input using an extension that changes geometry (draco, meshopt) is REFUSED
with a named error rather than silently mis-read — MINI-SPECS section 10 is
the grammar this implements and it has no compression in it.
"""

import base64
import json
import struct

import numpy as np

CT = {5120: ("i1", 1), 5121: ("u1", 1), 5122: ("<i2", 2), 5123: ("<u2", 2),
      5125: ("<u4", 4), 5126: ("<f4", 4)}
NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}

GEOMETRY_CHANGING = ("KHR_draco_mesh_compression", "EXT_meshopt_compression",
                     "KHR_mesh_quantization")


def glb_read(b):
    assert b[:4] == b"glTF", "not a GLB"
    ver, _total = struct.unpack("<II", b[4:12])
    assert ver == 2, "glTF version %d, this reader is glTF 2.0" % ver
    off, js, bin_ = 12, None, b""
    while off + 8 <= len(b):
        ln, tag = struct.unpack("<I4s", b[off:off + 8])
        chunk = b[off + 8:off + 8 + ln]
        if tag == b"JSON":
            js = json.loads(chunk.decode("utf-8"))
        elif tag == b"BIN\x00":
            bin_ = chunk
        off += 8 + ln + ((4 - ln % 4) % 4 if ln % 4 else 0)
    assert js is not None, "GLB has no JSON chunk"
    return js, bin_


def glb_write(js, bin_):
    jb = json.dumps(js, separators=(",", ":"), sort_keys=True).encode("utf-8")
    jb += b" " * ((4 - len(jb) % 4) % 4)
    bb = bin_ + b"\x00" * ((4 - len(bin_) % 4) % 4)
    total = 12 + 8 + len(jb) + (8 + len(bb) if bb else 0)
    out = b"glTF" + struct.pack("<II", 2, total)
    out += struct.pack("<I4s", len(jb), b"JSON") + jb
    if bb:
        out += struct.pack("<I4s", len(bb), b"BIN\x00") + bb
    return out


def _buffer(js, bin_, idx):
    buf = js["buffers"][idx]
    uri = buf.get("uri")
    if uri is None:
        return bin_
    if uri.startswith("data:"):
        return base64.b64decode(uri.split(",", 1)[1])
    raise ValueError("external buffer URI %r: a werk input must be self-contained" % uri)


def accessor(js, bin_, idx):
    a = js["accessors"][idx]
    n = a["count"]
    nc = NCOMP[a["type"]]
    dt, esz = CT[a["componentType"]]
    if "bufferView" not in a:
        out = np.zeros((n, nc), dtype=np.float64)
    else:
        bv = js["bufferViews"][a["bufferView"]]
        data = _buffer(js, bin_, bv.get("buffer", 0))
        base = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
        stride = bv.get("byteStride") or nc * esz
        raw = np.frombuffer(data, dtype=np.uint8,
                            count=stride * (n - 1) + nc * esz, offset=base)
        rows = np.lib.stride_tricks.as_strided(
            raw, shape=(n, nc * esz), strides=(stride, 1)).copy()
        out = np.frombuffer(rows.tobytes(), dtype=dt).reshape(n, nc).astype(np.float64)
        if a.get("normalized"):
            out = out / {"u1": 255.0, "i1": 127.0, "<u2": 65535.0,
                         "<i2": 32767.0}.get(dt, 1.0)
            if dt in ("i1", "<i2"):
                out = np.maximum(out, -1.0)
    # sparse accessors: rare but legal, and silently ignoring them would
    # corrupt the mesh, so they are applied rather than skipped.
    sp = a.get("sparse")
    if sp:
        ib = js["bufferViews"][sp["indices"]["bufferView"]]
        idt, iesz = CT[sp["indices"]["componentType"]]
        idat = _buffer(js, bin_, ib.get("buffer", 0))
        ii = np.frombuffer(idat, dtype=idt,
                           count=sp["count"],
                           offset=ib.get("byteOffset", 0) + sp["indices"].get("byteOffset", 0))
        vb = js["bufferViews"][sp["values"]["bufferView"]]
        vdat = _buffer(js, bin_, vb.get("buffer", 0))
        vv = np.frombuffer(vdat, dtype=dt, count=sp["count"] * nc,
                           offset=vb.get("byteOffset", 0) + sp["values"].get("byteOffset", 0))
        out[ii.astype(np.int64)] = vv.reshape(sp["count"], nc).astype(np.float64)
    return out


def _trs(node):
    if "matrix" in node:
        return np.array(node["matrix"], dtype=np.float64).reshape(4, 4).T
    m = np.eye(4)
    if "scale" in node:
        m = np.diag(list(node["scale"]) + [1.0]) @ m
    if "rotation" in node:
        x, y, z, w = node["rotation"]           # glTF quaternion order is xyzw
        r = np.array([
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w), 0],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w), 0],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y), 0],
            [0, 0, 0, 1]], dtype=np.float64)
        m = r @ m
    if "translation" in node:
        t = np.eye(4)
        t[:3, 3] = node["translation"]
        m = t @ m
    return m


class Scene(object):
    """One flattened mesh plus the material and image tables that go with it."""

    def __init__(self, pos, nrm, uv, col, idx, mat_of_tri, materials, images,
                 prim_count, had_normals, had_uv):
        self.pos = pos              # (nv,3) f64, model space
        self.nrm = nrm              # (nv,3) f64, unit
        self.uv = uv                # (nv,2) f64 or None
        self.col = col              # (nv,4) f64 linear or None
        self.idx = idx              # (nt,3) int32
        self.mat_of_tri = mat_of_tri
        self.materials = materials  # list of dicts (glTF material + resolved images)
        self.images = images        # list of (bytes, mime)
        self.prim_count = prim_count
        self.had_normals = had_normals
        self.had_uv = had_uv


def load_scene(glb_bytes):
    js, bin_ = glb_read(glb_bytes)
    for e in js.get("extensionsUsed", []):
        if e in GEOMETRY_CHANGING:
            raise ValueError("input uses %s; this pipeline reads uncompressed "
                             "glTF 2.0 only (MINI-SPECS section 10)" % e)

    # world transform per node, walking the default scene
    world = {}
    scene = js.get("scenes", [{}])[js.get("scene", 0)]
    stack = [(r, np.eye(4)) for r in scene.get("nodes", range(len(js.get("nodes", []))))]
    while stack:
        ni, parent = stack.pop()
        node = js["nodes"][ni]
        m = parent @ _trs(node)
        world[ni] = m
        for c in node.get("children", []):
            stack.append((c, m))

    P, N, UV, C, I, MT = [], [], [], [], [], []
    base = 0
    prim_count = 0
    had_normals = True
    had_uv = True
    for ni, m in sorted(world.items()):
        node = js["nodes"][ni]
        if "mesh" not in node:
            continue
        nm = np.linalg.inv(m[:3, :3]).T
        for prim in js["meshes"][node["mesh"]]["primitives"]:
            if prim.get("mode", 4) != 4:
                continue          # not triangles; werk's profile carries triangles
            at = prim["attributes"]
            p = accessor(js, bin_, at["POSITION"])
            p = (m[:3, :3] @ p.T).T + m[:3, 3]
            nv = len(p)
            if "NORMAL" in at:
                n = (nm @ accessor(js, bin_, at["NORMAL"]).T).T
            else:
                had_normals = False
                n = np.zeros((nv, 3))
            if "TEXCOORD_0" in at:
                uv = accessor(js, bin_, at["TEXCOORD_0"])[:, :2]
            else:
                had_uv = False
                uv = np.zeros((nv, 2))
            if "COLOR_0" in at:
                c = accessor(js, bin_, at["COLOR_0"])
                if c.shape[1] == 3:
                    c = np.hstack([c, np.ones((nv, 1))])
            else:
                c = np.ones((nv, 4))
            if "indices" in prim:
                ii = accessor(js, bin_, prim["indices"]).astype(np.int64).reshape(-1)
            else:
                ii = np.arange(nv, dtype=np.int64)
            tri = ii.reshape(-1, 3) + base
            P.append(p); N.append(n); UV.append(uv); C.append(c); I.append(tri)
            MT.append(np.full(len(tri), prim.get("material", -1), dtype=np.int32))
            base += nv
            prim_count += 1

    if not I:
        raise ValueError("the GLB carries no triangle primitives")

    pos = np.vstack(P)
    nrm = np.vstack(N)
    uv = np.vstack(UV)
    col = np.vstack(C)
    idx = np.vstack(I).astype(np.int64)
    mat_of_tri = np.concatenate(MT)

    # images, resolved to bytes
    images = []
    for im in js.get("images", []):
        if "bufferView" in im:
            bv = js["bufferViews"][im["bufferView"]]
            data = _buffer(js, bin_, bv.get("buffer", 0))
            blob = data[bv.get("byteOffset", 0):bv.get("byteOffset", 0) + bv["byteLength"]]
            images.append((bytes(blob), im.get("mimeType", "image/png")))
        elif "uri" in im and im["uri"].startswith("data:"):
            head, b64 = im["uri"].split(",", 1)
            images.append((base64.b64decode(b64),
                           head.split(":", 1)[1].split(";", 1)[0]))
        else:
            images.append((None, None))     # external: recorded as missing

    def tex_image(mat, key, sub=None):
        d = mat.get(key) if sub is None else mat.get(sub, {}).get(key)
        if not d or "index" not in d:
            return None
        t = js["textures"][d["index"]]
        if "source" not in t:
            return None
        return {"image": t["source"], "uv_set": d.get("texCoord", 0)}

    materials = []
    for mi, mat in enumerate(js.get("materials", [])):
        pbr = mat.get("pbrMetallicRoughness", {})
        materials.append({
            "index": mi,
            "name": mat.get("name") or "material-%d" % mi,
            "base_color_factor": pbr.get("baseColorFactor", [1, 1, 1, 1]),
            "metallic_factor": pbr.get("metallicFactor", 1.0),
            "roughness_factor": pbr.get("roughnessFactor", 1.0),
            "emissive_factor": mat.get("emissiveFactor", [0, 0, 0]),
            "alpha_mode": mat.get("alphaMode", "OPAQUE"),
            "double_sided": bool(mat.get("doubleSided", False)),
            "base_color_texture": tex_image(mat, "baseColorTexture", "pbrMetallicRoughness"),
            "metallic_roughness_texture": tex_image(mat, "metallicRoughnessTexture",
                                                    "pbrMetallicRoughness"),
            "normal_texture": tex_image(mat, "normalTexture"),
            "occlusion_texture": tex_image(mat, "occlusionTexture"),
            "emissive_texture": tex_image(mat, "emissiveTexture"),
        })

    return Scene(pos, nrm, uv, col, idx, mat_of_tri, materials, images,
                 prim_count, had_normals, had_uv)


# ---------------------------------------------------------------------------
# writing a clean single-primitive GLB
# ---------------------------------------------------------------------------

def _pad4(b):
    return b + b"\x00" * ((4 - len(b) % 4) % 4)


def build_glb(pos, idx, nrm=None, uv=None, col=None, tan=None, name="mesh",
              material=None):
    """One buffer, one bufferView per attribute, no strides, no extensions.

    Every accessor declares min/max for POSITION because the glTF spec
    requires it there and because a consumer that wants a bounding box should
    not have to walk a million floats to find one.
    """
    pos = np.asarray(pos, dtype="<f4")
    idx = np.asarray(idx, dtype=np.int64).reshape(-1)
    itype, idt = (5125, "<u4") if pos.shape[0] > 65535 else (5123, "<u2")
    blobs, views, accs, attrs = [], [], [], {}
    off = 0

    def add(arr, dtype, comp_type, kind, target, minmax=False):
        nonlocal off
        raw = _pad4(np.ascontiguousarray(arr, dtype=dtype).tobytes())
        blobs.append(raw)
        views.append({"buffer": 0, "byteOffset": off, "byteLength": len(raw),
                      "target": target})
        off += len(raw)
        a = {"bufferView": len(views) - 1, "componentType": comp_type,
             "count": int(arr.shape[0]), "type": kind}
        if minmax:
            a["min"] = [float(v) for v in np.asarray(arr, dtype=np.float64).min(axis=0)]
            a["max"] = [float(v) for v in np.asarray(arr, dtype=np.float64).max(axis=0)]
        accs.append(a)
        return len(accs) - 1

    attrs["POSITION"] = add(pos, "<f4", 5126, "VEC3", 34962, minmax=True)
    if nrm is not None:
        attrs["NORMAL"] = add(np.asarray(nrm, "<f4"), "<f4", 5126, "VEC3", 34962)
    if tan is not None:
        attrs["TANGENT"] = add(np.asarray(tan, "<f4"), "<f4", 5126, "VEC4", 34962)
    if uv is not None:
        attrs["TEXCOORD_0"] = add(np.asarray(uv, "<f4"), "<f4", 5126, "VEC2", 34962)
    if col is not None:
        attrs["COLOR_0"] = add(np.asarray(col, "<f4"), "<f4", 5126, "VEC4", 34962)
    iacc = add(idx.astype(idt).reshape(-1, 1), idt, itype, "SCALAR", 34963)
    accs[iacc]["count"] = int(idx.size)

    bin_ = b"".join(blobs)
    prim = {"attributes": attrs, "indices": iacc, "mode": 4}
    js = {
        "asset": {"version": "2.0", "generator": "werk pipeline/enrich.py 0.1"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": name}],
        "meshes": [{"name": name, "primitives": [prim]}],
        "accessors": accs,
        "bufferViews": views,
        "buffers": [{"byteLength": len(bin_)}],
    }
    if material is not None:
        js["materials"] = [material]
        prim["material"] = 0
    return glb_write(js, bin_)
