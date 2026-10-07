"""
blender_export_fbx.py -- Blender-side half of build_controls.py (roundNC).

Run only through build_controls.py:
  blender --background --factory-startup --python blender_export_fbx.py -- <args.json>

args.json keys:
  gltf      path of the CC0 crate .gltf (read-only source)
  texture   path of the CC0 albedo PNG to embed
  image_name  datablock name for the image (becomes the FBX Video name)
  out_fbx   output .fbx path
  report    output JSON path (Blender's own view, settings, versions)
  reimport_dir  empty dir for the re-import check (FBX copied there alone)
  import_settings / export_settings   keyword arguments, passed verbatim

Steps:
  1. Empty scene (read_factory_settings(use_empty=True)).
  2. Import the glTF. Its three JPEGs are not in the repo, so the importer
     leaves those image slots empty. All imported materials and images are
     then removed.
  3. One new material "crate_wood": Principled BSDF, Base Color <- Image
     Texture (the albedo PNG). Assigned to every mesh object, slot 0 only.
  4. Export one binary FBX with the export settings given.
  5. Report Blender's view: per mesh, before export and after re-importing
     the exported FBX (vertex/polygon/triangle counts, float32 positions sha256
     in Blender vertex order), plus the packed image bytes after re-import.
"""

import hashlib
import json
import struct
import sys

import bpy


def sha(b):
    return hashlib.sha256(b).hexdigest()


def mesh_view(objs):
    out = []
    for ob in objs:
        me = ob.data
        co = [0.0] * (len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        dump = struct.pack("<%df" % len(co), *co)
        tri = sum(len(p.vertices) - 2 for p in me.polygons)
        out.append({
            "object": ob.name, "mesh": me.name,
            "vertex_count": len(me.vertices), "polygon_count": len(me.polygons),
            "triangle_count": tri, "loop_count": len(me.loops),
            "positions_f32_sha256": sha(dump),
            "matrix_world": [list(r) for r in ob.matrix_world],
            "materials": [s.material.name if s.material else None for s in ob.material_slots],
            "uv_layers": [u.name for u in me.uv_layers],
        })
    return out


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    with open(argv[0], encoding="utf-8") as f:
        a = json.load(f)
    rep = {"blender_version": bpy.app.version_string,
           "blender_build_hash": bpy.app.build_hash.decode() if isinstance(bpy.app.build_hash, bytes) else bpy.app.build_hash,
           "blender_build_date": bpy.app.build_date.decode() if isinstance(bpy.app.build_date, bytes) else bpy.app.build_date,
           "addons": {}}
    import addon_utils
    for mod in addon_utils.modules():
        if mod.__name__ in ("io_scene_fbx", "io_scene_gltf2"):
            rep["addons"][mod.__name__] = ".".join(str(x) for x in mod.bl_info.get("version", ()))

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=a["gltf"], **a["import_settings"])
    meshes = sorted([o for o in bpy.data.objects if o.type == "MESH"], key=lambda o: o.name)
    rep["imported_objects"] = [(o.name, o.type) for o in bpy.data.objects]
    rep["imported_images_before_cleanup"] = [
        {"name": i.name, "filepath": i.filepath, "has_data": bool(i.has_data)} for i in bpy.data.images]

    for m in list(bpy.data.materials):
        bpy.data.materials.remove(m)
    for i in list(bpy.data.images):
        bpy.data.images.remove(i)

    img = bpy.data.images.load(a["texture"], check_existing=False)
    img.name = a["image_name"]
    mat = bpy.data.materials.new("crate_wood")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    for ob in meshes:
        ob.data.materials.clear()
        ob.data.materials.append(mat)

    rep["blender_view_before_export"] = mesh_view(meshes)
    rep["image"] = {"name": img.name, "filepath": img.filepath, "size": list(img.size),
                    "file_format": img.file_format, "packed": img.packed_file is not None}

    es = dict(a["export_settings"])
    es["object_types"] = set(es["object_types"])  # enum-flag property wants a set
    bpy.ops.export_scene.fbx(filepath=a["out_fbx"], **es)

    # Blender's own view of the EXPORTED file: re-import it into an empty scene.
    # The copy sits alone in its own directory, so the importer cannot find
    # the source PNG on disk: any image data must come from Video/Content.
    import os
    import shutil
    rdir = a["reimport_dir"]
    shutil.rmtree(rdir, ignore_errors=True)
    os.makedirs(rdir)
    rfbx = os.path.join(rdir, os.path.basename(a["out_fbx"]))
    shutil.copyfile(a["out_fbx"], rfbx)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=rfbx)
    re_meshes = sorted([o for o in bpy.data.objects if o.type == "MESH"], key=lambda o: o.name)
    rep["blender_view_after_reimport"] = mesh_view(re_meshes)
    rep["reimported_images"] = []
    for i in bpy.data.images:
        d = bytes(i.packed_file.data) if i.packed_file else None
        rep["reimported_images"].append({
            "name": i.name, "filepath": i.filepath, "packed": d is not None,
            "packed_size": len(d) if d else None, "packed_sha256": sha(d) if d else None})

    with open(a["report"], "w", encoding="utf-8", newline="\n") as f:
        json.dump(rep, f, indent=2)
        f.write("\n")
    print("blender_export_fbx: OK")


try:
    main()
except Exception:
    import traceback
    traceback.print_exc()
    sys.exit(1)
