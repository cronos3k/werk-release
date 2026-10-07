#!/usr/bin/env python3
"""Reference (trusted) extractor for the glTF control, for the grade_nc.py
dry-run only. NOT an agent artifact. Stdlib only. Run in a dir that holds
crate-nc-v1.gltf and the files it references.

Writes out/<buffer uri> (copy of the .bin), out/<image uri> (copy of the PNG)
and out/crate.obj (POSITION values, meshes[] then primitives[] order).
"""
import glob
import json
import os
import shutil
import struct

src = glob.glob("*.gltf")[0]
gl = json.load(open(src, encoding="utf-8"))
print("glTF %s, generator %s" % (gl["asset"]["version"], gl["asset"].get("generator")))
for i, m in enumerate(gl["meshes"]):
    for p in m["primitives"]:
        a = gl["accessors"][p["attributes"]["POSITION"]]
        print("mesh %d %s: %d vertices, %d indices" % (
            i, m["name"], a["count"], gl["accessors"][p["indices"]]["count"]))
bufs = []
for b in gl["buffers"]:
    data = open(b["uri"], "rb").read()
    print("buffer %s: declared byteLength %d, actual %d -> %s" % (
        b["uri"], b["byteLength"], len(data), "consistent" if len(data) == b["byteLength"] else "MISMATCH"))
    bufs.append(data)
for im in gl.get("images", []):
    print("image %s (%s): %s" % (im["uri"], im.get("mimeType"),
                                 "present" if os.path.exists(im["uri"]) else "MISSING from workspace"))
print("integrity: this file declares no checksums; only structural consistency was checkable")
os.makedirs("out", exist_ok=True)
shutil.copyfile(gl["buffers"][0]["uri"], os.path.join("out", os.path.basename(gl["buffers"][0]["uri"])))
for im in gl.get("images", []):
    if os.path.exists(im["uri"]):
        shutil.copyfile(im["uri"], os.path.join("out", os.path.basename(im["uri"])))
with open("out/crate.obj", "w") as f:
    for m in gl["meshes"]:
        for p in m["primitives"]:
            a = gl["accessors"][p["attributes"]["POSITION"]]
            bv = gl["bufferViews"][a["bufferView"]]
            base = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
            stride = bv.get("byteStride") or 12
            for i in range(a["count"]):
                f.write("v %.9g %.9g %.9g\n" % struct.unpack_from("<3f", bufs[bv["buffer"]], base + stride * i))
print("extracted mesh -> out/%s and out/crate.obj; texture -> out/%s" % (
    gl["buffers"][0]["uri"], ", ".join(os.path.basename(im["uri"]) for im in gl.get("images", []))))
