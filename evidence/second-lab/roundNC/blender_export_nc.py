"""
blender_export_nc.py -- Blender-side half of build_gltf_usdz.py (roundNC).

Run only through build_gltf_usdz.py:
  blender --background --factory-startup --python-use-system-env \
          --python-exit-code 1 --python blender_export_nc.py -- <args.json>

args.json keys:
  format          "gltf" or "usdz"
  gltf            path of the CC0 crate .gltf (read-only source)
  texture         path of the CC0 albedo PNG (crate_diffuse.png)
  image_name      datablock name for the image
  out             output path (.gltf or .usdz)
  report          output JSON path
  dump_dir        directory for float32 position dumps (Blender's view)
  reimport_dir    empty dir for the re-import check (outputs copied there alone)
  import_settings / export_settings   keyword arguments, passed verbatim

Scene setup is the same as blender_export_fbx.py (the FBX control):
  1. Empty scene. 2. Import the glTF, keep vertices 1:1. 3. Remove all
  imported materials and images. 4. One material "crate_wood", Base Color <-
  Image Texture (the albedo PNG), on all 3 meshes.
Then export, and report Blender's view before export and after re-import.
For usdz, the report also holds the stage as read by Blender's bundled USD
library (pxr): mesh prims in stage traversal order, their authored points.
"""

import hashlib
import json
import os
import shutil
import struct
import sys

import bpy


def sha(b):
    return hashlib.sha256(b).hexdigest()


def write_dump(dump_dir, tag, co):
    data = struct.pack("<%df" % len(co), *co)
    p = os.path.join(dump_dir, tag + ".f32")
    with open(p, "wb") as f:
        f.write(data)
    return p, sha(data)


def mesh_view(objs, dump_dir, prefix):
    out = []
    for ob in objs:
        me = ob.data
        co = [0.0] * (len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        p, h = write_dump(dump_dir, "%s-%s" % (prefix, me.name.replace("/", "_")), co)
        tri = sum(len(pl.vertices) - 2 for pl in me.polygons)
        out.append({
            "object": ob.name, "mesh": me.name,
            "vertex_count": len(me.vertices), "polygon_count": len(me.polygons),
            "triangle_count": tri, "loop_count": len(me.loops),
            "positions_f32_sha256": h, "positions_dump": p,
            "matrix_world": [list(r) for r in ob.matrix_world],
            "materials": [s.material.name if s.material else None for s in ob.material_slots],
            "uv_layers": [u.name for u in me.uv_layers],
        })
    return out


def images_view():
    out = []
    for i in bpy.data.images:
        d = bytes(i.packed_file.data) if i.packed_file else None
        rec = {"name": i.name, "filepath": i.filepath, "packed": d is not None,
               "packed_size": len(d) if d else None, "packed_sha256": sha(d) if d else None,
               "has_data": bool(i.has_data)}
        fp = bpy.path.abspath(i.filepath) if i.filepath else ""
        if not d and fp and os.path.isfile(fp):
            with open(fp, "rb") as f:
                fb = f.read()
            rec["file_sha256"] = sha(fb)
            rec["file_size"] = len(fb)
        out.append(rec)
    return out


def pxr_view(path, dump_dir):
    """The exported stage as Blender's bundled USD library reads it."""
    from pxr import Usd, UsdGeom, UsdShade, Sdf  # noqa: F401
    stage = Usd.Stage.Open(path)
    root = stage.GetRootLayer()
    meshes = []
    for prim in stage.Traverse():
        if not prim.IsA(UsdGeom.Mesh):
            continue
        m = UsdGeom.Mesh(prim)
        pts = m.GetPointsAttr().Get()
        fvc = list(m.GetFaceVertexCountsAttr().Get() or [])
        co = [float(c) for p in pts for c in p]
        p, h = write_dump(dump_dir, "pxr-" + str(prim.GetPath()).strip("/").replace("/", "_"), co)
        meshes.append({
            "prim_path": str(prim.GetPath()),
            "points_count": len(pts), "points_type": str(m.GetPointsAttr().GetTypeName()),
            "face_count": len(fvc), "triangle_count": sum(n - 2 for n in fvc),
            "all_triangles": all(n == 3 for n in fvc),
            "positions_f32_sha256": h, "positions_dump": p,
        })
    shaders = []
    for prim in stage.Traverse():
        if prim.IsA(UsdShade.Shader):
            sh = UsdShade.Shader(prim)
            ins = {}
            for i in sh.GetInputs():
                v = i.Get()
                ins[i.GetBaseName()] = str(v) if v is not None else None
            shaders.append({"prim_path": str(prim.GetPath()), "id": str(sh.GetIdAttr().Get()),
                            "inputs": ins})
    text = root.ExportToString()
    return {
        "usd_version": ".".join(str(x) for x in __import__("pxr").Usd.GetVersion()),
        "root_layer_identifier_basename": os.path.basename(root.identifier),
        "root_layer_file_format": root.GetFileFormat().formatId,
        "up_axis": str(UsdGeom.GetStageUpAxis(stage)),
        "meters_per_unit": UsdGeom.GetStageMetersPerUnit(stage),
        "default_prim": str(stage.GetDefaultPrim().GetPath()) if stage.GetDefaultPrim() else None,
        "traversal_order": [str(p.GetPath()) for p in stage.Traverse()],
        "meshes": meshes,
        "shaders": shaders,
        "root_layer_as_usda": text,
    }


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    with open(argv[0], encoding="utf-8") as f:
        a = json.load(f)
    os.makedirs(a["dump_dir"], exist_ok=True)
    rep = {"blender_version": bpy.app.version_string,
           "blender_build_hash": bpy.app.build_hash.decode() if isinstance(bpy.app.build_hash, bytes) else bpy.app.build_hash,
           "blender_build_date": bpy.app.build_date.decode() if isinstance(bpy.app.build_date, bytes) else bpy.app.build_date,
           "addons": {}}
    import addon_utils
    for mod in addon_utils.modules():
        if mod.__name__ in ("io_scene_gltf2",):
            rep["addons"][mod.__name__] = ".".join(str(x) for x in mod.bl_info.get("version", ()))
    try:
        from pxr import Usd
        rep["pxr_usd_version"] = ".".join(str(x) for x in Usd.GetVersion())
    except Exception as e:  # pragma: no cover
        rep["pxr_usd_version"] = "unavailable: %s" % e

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

    rep["blender_view_before_export"] = mesh_view(meshes, a["dump_dir"], "before")
    rep["image"] = {"name": img.name, "filepath": img.filepath, "size": list(img.size),
                    "file_format": img.file_format, "packed": img.packed_file is not None}

    es = dict(a["export_settings"])
    fmt = a["format"]
    if fmt == "gltf":
        bpy.ops.export_scene.gltf(filepath=a["out"], **es)
    elif fmt == "usdz":
        bpy.ops.wm.usd_export(filepath=a["out"], **es)
        rep["pxr_stage"] = pxr_view(a["out"], a["dump_dir"])
    else:
        raise SystemExit("unknown format %r" % fmt)

    # Re-import the exported output from a dir that holds only that output
    # (and, for glTF, its sidecars), so nothing can come from the source PNG.
    rdir = a["reimport_dir"]
    shutil.rmtree(rdir, ignore_errors=True)
    os.makedirs(rdir)
    for n in a["reimport_files"]:
        shutil.copyfile(os.path.join(os.path.dirname(a["out"]), n), os.path.join(rdir, n))
    rpath = os.path.join(rdir, os.path.basename(a["out"]))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if fmt == "gltf":
        bpy.ops.import_scene.gltf(filepath=rpath, **a["import_settings"])
    else:
        bpy.ops.wm.usd_import(filepath=rpath)
    re_meshes = sorted([o for o in bpy.data.objects if o.type == "MESH"], key=lambda o: o.name)
    rep["blender_view_after_reimport"] = mesh_view(re_meshes, a["dump_dir"], "reimport")
    rep["reimported_images"] = images_view()

    with open(a["report"], "w", encoding="utf-8", newline="\n") as f:
        json.dump(rep, f, indent=2)
        f.write("\n")
    print("blender_export_nc: OK")


try:
    main()
except Exception:
    import traceback
    traceback.print_exc()
    sys.exit(1)
