#!/usr/bin/env python3
"""Reference (trusted) extractor for the FBX control, for the grade_nc.py
dry-run only. NOT an agent artifact. Written separately from nc_fbx.py (the
code that builds the ground truth), so the dry-run does not grade the builder
against itself. Stdlib only. Run in a dir that holds crate-nc-v1.fbx.

Writes out/<Video RelativeFilename basename> (the embedded Content bytes) and
a mesh dump: out/crate.obj (default) or out/crate-positions.f32 (MESH_AS='f32').
"""
import glob
import os
import struct
import zlib

MESH_AS = "f32"

src = glob.glob("*.fbx")[0]
b = open(src, "rb").read()
assert b[:21] == b"Kaydara FBX Binary  \x00", "not binary FBX"
ver = struct.unpack_from("<I", b, 23)[0]
W = ver >= 7500
HDR = 25 if W else 13
ARR = {"f": "f", "d": "d", "l": "q", "i": "i", "b": "b"}


def prop(o):
    t = b[o:o + 1].decode()
    o += 1
    fixed = {"Y": "<h", "C": "<?", "I": "<i", "F": "<f", "D": "<d", "L": "<q"}
    if t in fixed:
        n = struct.calcsize(fixed[t])
        return struct.unpack_from(fixed[t], b, o)[0], o + n
    if t in "SR":
        n = struct.unpack_from("<I", b, o)[0]
        return b[o + 4:o + 4 + n], o + 4 + n
    cnt, enc, ln = struct.unpack_from("<III", b, o)
    raw = b[o + 12:o + 12 + ln]
    if enc:
        raw = zlib.decompress(raw)
    return struct.unpack("<%d%s" % (cnt, ARR[t]), raw), o + 12 + ln


def node(o):
    end, np_, _pl = struct.unpack_from("<QQQ" if W else "<III", b, o)
    nl = b[o + HDR - 1]
    if end == 0:
        return None, o + HDR
    name = b[o + HDR:o + HDR + nl].decode()
    o += HDR + nl
    props = []
    for _ in range(np_):
        v, o = prop(o)
        props.append(v)
    kids = []
    while o < end:
        if b[o:end] == b"\0" * (end - o):  # trailing null record
            break
        k, o = node(o)
        if k is None:
            break
        kids.append(k)
    return (name, props, kids), end


top = []
o = 27
while o < len(b):
    n, o = node(o)
    if n is None:
        break
    top.append(n)

print("binary FBX version %d, %d top-level nodes: %s" % (ver, len(top), ", ".join(n[0] for n in top)))
objects = [n for n in top if n[0] == "Objects"][0]


def nm(p):
    return p.split(b"\x00\x01")[0].decode()


def child(n, name):
    return [k for k in n[2] if k[0] == name]


geoms, videos = [], []
for k in objects[2]:
    label = nm(k[1][1]) if len(k[1]) > 1 and isinstance(k[1][1], bytes) else ""
    cls = k[1][2].decode() if len(k[1]) > 2 and isinstance(k[1][2], bytes) else ""
    print("  Objects/%s %r class=%s" % (k[0], label, cls))
    if k[0] == "Geometry" and cls == "Mesh":
        geoms.append((label, child(k, "Vertices")[0][1][0], child(k, "PolygonVertexIndex")[0][1][0]))
    if k[0] == "Video":
        c = child(k, "Content")
        rf = child(k, "RelativeFilename")
        if c and c[0][1] and c[0][1][0]:
            videos.append((label, rf[0][1][0].decode() if rf else label, c[0][1][0]))

for label, v, pvi in geoms:
    print("mesh %s: %d vertices, %d polygons" % (label, len(v) // 3, sum(1 for x in pvi if x < 0)))
for label, rf, data in videos:
    print("embedded media %s (%s): %d bytes, magic %r" % (label, rf, len(data), data[:4]))
print("integrity: this FBX declares no checksums of any kind; only structural "
      "consistency (array lengths, zlib streams, node end offsets) was checkable")

os.makedirs("out", exist_ok=True)
for label, rf, data in videos:
    name = rf.replace("\\", "/").split("/")[-1]
    open(os.path.join("out", name), "wb").write(data)
    print("extracted texture -> out/%s" % name)
if MESH_AS == "f32":
    with open("out/crate-positions.f32", "wb") as f:
        for _, v, _ in geoms:
            f.write(struct.pack("<%df" % len(v), *v))
    print("extracted mesh positions -> out/crate-positions.f32")
else:
    with open("out/crate.obj", "w") as f:
        base = 1
        for label, v, pvi in geoms:
            f.write("o %s\n" % label)
            for i in range(0, len(v), 3):
                f.write("v %.17g %.17g %.17g\n" % (v[i], v[i + 1], v[i + 2]))
            poly = []
            for x in pvi:
                poly.append(x if x >= 0 else ~x)
                if x < 0:
                    f.write("f %s\n" % " ".join(str(j + base) for j in poly))
                    poly = []
            base += len(v) // 3
    print("extracted mesh -> out/crate.obj")
