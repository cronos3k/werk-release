#!/usr/bin/env python3
"""Reference (trusted) extractor for the USDZ control, for the grade_nc.py
dry-run only. NOT an agent artifact. Run in a dir that holds crate-nc-v1.usdz.

Container part (stdlib zipfile): list the entries, check every zip CRC-32,
extract the PNG entry to out/.
Mesh part: stdlib Python has no usdc reader, so this trusted reference calls
Blender's bundled USD library (pxr) as an external program to read the
authored points (stage traversal order) and writes out/crate.obj, or
out/crate-positions.f32 when MESH_AS = "f32".
An agent has no such tool in its workspace; it must parse usdc itself.
"""
import glob
import os
import subprocess
import sys
import tempfile
import zipfile

MESH_AS = "obj"
BLENDER = "C:/Program Files/Blender Foundation/Blender 4.2/blender.exe"

src = os.path.abspath(glob.glob("*.usdz")[0])
os.makedirs("out", exist_ok=True)
with zipfile.ZipFile(src) as z:
    for i in z.infolist():
        print("entry %-32s %8d B  stored=%s  crc32 %08x" % (
            i.filename, i.file_size, i.compress_type == zipfile.ZIP_STORED, i.CRC))
    bad = z.testzip()
    print("integrity: zip CRC-32 of every entry %s; nothing cryptographic is declared"
          % ("holds" if bad is None else "FAILS at " + bad))
    for i in z.infolist():
        if i.filename.lower().endswith(".png"):
            with open(os.path.join("out", os.path.basename(i.filename)), "wb") as f:
                f.write(z.read(i.filename))
            print("extracted texture -> out/%s" % os.path.basename(i.filename))

PXR = r'''
import struct, sys
from pxr import Usd, UsdGeom
src, out, mode = sys.argv[sys.argv.index("--") + 1:][:3]
st = Usd.Stage.Open(src)
pts_all = []
for p in st.Traverse():
    if p.IsA(UsdGeom.Mesh):
        m = UsdGeom.Mesh(p)
        pts = m.GetPointsAttr().Get()
        fvc = m.GetFaceVertexCountsAttr().Get()
        print("REF mesh %s: %d points, %d faces" % (p.GetPath(), len(pts), len(fvc)))
        pts_all.extend((float(v[0]), float(v[1]), float(v[2])) for v in pts)
with open(out, "wb") as f:
    if mode == "f32":
        f.write(b"".join(struct.pack("<3f", *v) for v in pts_all))
    else:
        f.write("".join("v %.9g %.9g %.9g\n" % v for v in pts_all).encode())
'''
td = tempfile.mkdtemp()
script = os.path.join(td, "pxr_dump.py")
with open(script, "w", encoding="utf-8") as f:
    f.write(PXR)
out = os.path.abspath(os.path.join("out", "crate-positions.f32" if MESH_AS == "f32" else "crate.obj"))
p = subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1",
                    "--python", script, "--", src, out, MESH_AS], capture_output=True, text=True)
for ln in p.stdout.splitlines():
    if ln.startswith("REF "):
        print(ln[4:])
if p.returncode != 0:
    sys.stderr.write(p.stdout + p.stderr)
    sys.exit(1)
print("extracted mesh -> out/%s" % os.path.basename(out))
