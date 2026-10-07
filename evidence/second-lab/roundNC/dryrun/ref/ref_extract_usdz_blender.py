"""Second reference extraction for the USDZ control, using Blender's own USD
importer (a different code path from the pxr points read). Dry-run only.
NOT an agent artifact.

  blender --background --factory-startup --python ref_extract_usdz_blender.py -- <usdz> <outdir>

Writes <outdir>/out/<image file name> (the PNG bytes Blender loaded from the
package) and <outdir>/out/crate-blender.obj (vertex positions, objects in
Blender's name-sorted order, Blender vertex order within each object).
"""
import os
import sys

import bpy

usdz, outdir = sys.argv[sys.argv.index("--") + 1:][:2]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.usd_import(filepath=usdz)
out = os.path.join(outdir, "out")
os.makedirs(out, exist_ok=True)
for img in bpy.data.images:
    if img.packed_file:
        data = bytes(img.packed_file.data)
    else:
        with open(bpy.path.abspath(img.filepath), "rb") as f:
            data = f.read()
    name = os.path.basename(img.filepath.replace("\\", "/")) or img.name
    with open(os.path.join(out, name), "wb") as f:
        f.write(data)
    print("image %s: %d B" % (name, len(data)))
obs = sorted((o for o in bpy.data.objects if o.type == "MESH"), key=lambda o: o.name)
with open(os.path.join(out, "crate-blender.obj"), "w") as f:
    for ob in obs:
        f.write("o %s\n" % ob.name)
        for v in ob.data.vertices:
            f.write("v %.9g %.9g %.9g\n" % tuple(v.co))
        print("mesh %s: %d vertices, %d polygons" % (ob.name, len(ob.data.vertices), len(ob.data.polygons)))
print("ref_extract_usdz_blender: OK")
