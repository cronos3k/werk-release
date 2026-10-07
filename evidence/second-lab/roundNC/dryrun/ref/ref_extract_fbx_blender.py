"""Second reference extraction for the FBX control, using Blender's own FBX
importer (an independent implementation). Dry-run only. NOT an agent artifact.

  blender --background --factory-startup --python ref_extract_fbx_blender.py -- <fbx> <outdir>

Writes <outdir>/out/<image name> (the packed bytes Blender read from
Video/Content) and <outdir>/out/crate-blender.obj (vertex positions, objects in
Blender's name-sorted order, Blender vertex order within each object).
"""
import os
import sys

import bpy

fbx, outdir = sys.argv[sys.argv.index("--") + 1:][:2]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=fbx)
out = os.path.join(outdir, "out")
os.makedirs(out, exist_ok=True)
imgs = [i for i in bpy.data.images if i.packed_file]
img = imgs[0]
name = os.path.basename(img.filepath.replace("\\", "/")) or img.name
with open(os.path.join(out, name), "wb") as f:
    f.write(bytes(img.packed_file.data))
print("images: %s" % [(i.name, i.packed_file.size if i.packed_file else None) for i in bpy.data.images])
obs = sorted((o for o in bpy.data.objects if o.type == "MESH"), key=lambda o: o.name)
with open(os.path.join(out, "crate-blender.obj"), "w") as f:
    for ob in obs:
        f.write("o %s\n" % ob.name)
        for v in ob.data.vertices:
            f.write("v %.9g %.9g %.9g\n" % tuple(v.co))
        print("mesh %s: %d vertices, %d polygons" % (ob.name, len(ob.data.vertices), len(ob.data.polygons)))
print("ref_extract_fbx_blender: OK")
