#!/usr/bin/env python3
"""Reference (trusted) extractor for the werk baseline, for the grade_nc.py
dry-run only. Uses Python zipfile directly. NOT an agent artifact.

Set REF_MESH_AS=obj to write the mesh as an OBJ text dump instead of the
verbatim game.glb (exercises the Tier 2 text-dump path)."""
import glob
import hashlib
import json
import os
import struct
import sys
import zipfile

MESH_AS = os.environ.get("REF_MESH_AS", "glb")
if len(sys.argv) > 1:
    MESH_AS = sys.argv[1]
src = glob.glob("*.werk")[0]
z = zipfile.ZipFile(src)
man = json.loads(z.read("MANIFEST.json"))
print("container: %s (%d zip entries)" % (src, len(z.infolist())))
declared = {}
for n in man["nodes"]:
    print("node %-34s type=%s" % (n["node_id"], n["type"]))
    for v in n["versions"]:
        for f in v["files"]:
            declared[f["path"]] = f["sha256"]
            print("    %s" % f["path"])
bad_crc = z.testzip()
print("zip CRC-32: %s" % ("all entries OK" if bad_crc is None else "FAILED on " + bad_crc))
ok = sum(1 for p, h in declared.items() if hashlib.sha256(z.read(p)).hexdigest() == h)
print("declared sha256 verified: %d/%d" % (ok, len(declared)))
print("not verified here: Ed25519 signature chain, spec_sha256, input_hash")
if ok != len(declared) or bad_crc is not None:
    sys.exit(2)

prim = man["primary"]
os.makedirs("out", exist_ok=True)


def node_files(nid):
    for n in man["nodes"]:
        if n["node_id"] == nid:
            return n["versions"][0]["files"]


mesh = [f for f in node_files(prim["mesh"]) if f["path"].endswith(".glb")][0]
glb = z.read(mesh["path"])
if MESH_AS == "obj":
    jl = struct.unpack_from("<I", glb, 12)[0]
    gl = json.loads(glb[20:20 + jl])
    binc = glb[20 + jl + 8:]
    acc = gl["accessors"][gl["meshes"][0]["primitives"][0]["attributes"]["POSITION"]]
    bv = gl["bufferViews"][acc["bufferView"]]
    base = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    with open("out/crate.obj", "w") as f:
        for i in range(acc["count"]):
            f.write("v %.9g %.9g %.9g\n" % struct.unpack_from("<3f", binc, base + 12 * i))
    print("extracted mesh -> out/crate.obj (OBJ text dump of POSITION)")
else:
    with open("out/" + os.path.basename(mesh["path"]), "wb") as f:
        f.write(glb)
    print("extracted mesh -> out/%s" % os.path.basename(mesh["path"]))
snd = [f for f in node_files(prim["sound"]) if f.get("role") == "best"][0]
with open("out/" + os.path.basename(snd["path"]), "wb") as f:
    f.write(z.read(snd["path"]))
print("extracted sound -> out/%s" % os.path.basename(snd["path"]))
png = [p for p in declared if p.endswith(".png")][0]
with open("out/" + os.path.basename(png), "wb") as f:
    f.write(z.read(png))
print("extracted texture-class image -> out/%s" % os.path.basename(png))
