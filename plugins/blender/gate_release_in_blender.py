"""The half of gate_release.py that runs INSIDE Blender. Measures, never judges.

    blender -b --factory-startup --python gate_release_in_blender.py -- <payload.json>

For every fixture in the payload:
  3d-entity/1 : import -> measure -> export the imported objects -> fresh
                scene -> re-import the export -> measure again.
  image/1     : import as an image datablock -> measure (packed bytes,
                pixels) -> load the separately extracted primary file
                directly -> compare pixels -> export image/1 -> re-import ->
                compare pixels.
Results go to payload["result"] as JSON; gate_release.py judges them.
"""

import hashlib
import json
import os
import sys
import time
import traceback

import bpy

ARGS = json.loads(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8").read())
sys.path.insert(0, ARGS["addon_parent"])
import werk_blender  # noqa: E402

werk_blender.register()


def fresh():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    # read_factory_settings unregisters add-ons that were registered by hand.
    try:
        werk_blender.register()
    except Exception:  # noqa: BLE001 - already registered
        pass


def _r(x):
    v = round(x, 4)
    return 0.0 if v == 0.0 else v     # no -0.0 in a hash


def geometry():
    """Counts + order-independent hashes of every mesh in the scene, in world
    space, evaluated (modifiers applied), positions rounded to 1e-4 m."""
    dg = bpy.context.evaluated_depsgraph_get()
    verts = tris = edges_loose = 0
    pos_set = set()
    tri_list = []
    corner_set = set()
    meshes = 0
    for ob in bpy.context.scene.objects:
        if ob.type != "MESH":
            continue
        meshes += 1
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ob.matrix_world
        co = [tuple(_r(c) for c in (mw @ v.co)) for v in me.vertices]
        verts += len(co)
        pos_set.update(co)
        me.calc_loop_triangles()
        uv = me.uv_layers.active.data if me.uv_layers.active else None
        for lt in me.loop_triangles:
            tri_list.append(tuple(sorted(co[i] for i in lt.vertices)))
        for lp in me.loops:
            corner_set.add((co[lp.vertex_index],
                            tuple(_r(c) for c in uv[lp.index].uv) if uv else ()))
        tris += len(me.loop_triangles)
        ev.to_mesh_clear()
    tri_list.sort()
    h_pos = hashlib.sha256(json.dumps(sorted(pos_set)).encode()).hexdigest()
    h_tri = hashlib.sha256(json.dumps(tri_list).encode()).hexdigest()
    h_cor = hashlib.sha256(json.dumps(sorted(corner_set)).encode()).hexdigest()
    return {"mesh_objects": meshes, "vertices": verts, "triangles": tris,
            "unique_positions": len(pos_set), "positions_sha256": h_pos,
            "triangles_sha256": h_tri,
            "distinct_corners": len(corner_set), "corners_sha256": h_cor,
            "materials": len([m for m in bpy.data.materials if m.users]),
            "images": len(bpy.data.images),
            "armatures": len([o for o in bpy.context.scene.objects
                              if o.type == "ARMATURE"]),
            "bones": sum(len(o.data.bones) for o in bpy.context.scene.objects
                         if o.type == "ARMATURE"),
            "actions": len(bpy.data.actions),
            "objects": len(bpy.context.scene.objects)}


def import_summary(res):
    return {"kind": getattr(res, "kind", "entity"),
            "nodes_total": res.nodes_total, "nodes_alive": res.nodes_alive,
            "nodes_dead": res.nodes_dead,
            "nodes_skipped": res.nodes_skipped_unknown,
            "signature_bootstrap": res.signature,
            "signature_library": res.signature_verified,
            "library_verdict": res.library_verdict,
            "errors": res.errors(),
            "report_codes": sorted({c for _s, c, _m in res.report}),
            "error_codes": sorted({c for s, c, _m in res.report if s == "error"}),
            "seconds": round(res.seconds, 3)}


def pixels_sha(img):
    import numpy as np
    w, h, c = int(img.size[0]), int(img.size[1]), int(img.channels)
    px = np.empty(w * h * c, dtype=np.float32)
    img.pixels.foreach_get(px)
    u8 = np.rint(np.clip(px, 0, 1) * 255).astype(np.uint8).reshape(h, w, c)
    if c == 4:
        u8 = u8[:, :, :4]
    return hashlib.sha256(u8.tobytes()).hexdigest(), [w, h, c]


def run_entity(fx):
    out = {"fixture": fx["key"], "profile": "3d-entity/1", "path": fx["path"]}
    fresh()
    res = werk_blender.import_file(fx["path"])
    out["import"] = import_summary(res)
    out["before"] = geometry()
    # The whole imported scene is exported (the operator's "Selection only"
    # off): an armature-only package has no mesh among res.objects' meshes.
    objs = list(bpy.context.scene.objects)
    exp_path = os.path.join(ARGS["out_dir"], fx["key"] + ".blender-export.werk")
    try:
        exp = werk_blender.export_file(exp_path, objects=objs)
        out["export"] = {"path": exp_path, "bytes": exp.bytes, "sha256": exp.sha256,
                         "entries": exp.entries, "nodes": exp.nodes, "files": exp.files,
                         "vertex_count": exp.vertex_count,
                         "triangle_count": exp.triangle_count,
                         "reused_identity": exp.reused_identity,
                         "entity_uuid": exp.entity_uuid,
                         "library_verdict": exp.library_verdict,
                         "report": [list(r) for r in exp.report]}
    except ValueError as e:
        out["export"] = {"refused": str(e)}
        return out
    fresh()
    back = werk_blender.import_file(exp_path)
    out["reimport"] = import_summary(back)
    out["reimport"]["entity_uuid"] = back.entity_uuid
    out["after"] = geometry()
    out["source_uuid"] = res.entity_uuid
    return out


def run_image(fx):
    out = {"fixture": fx["key"], "profile": "image/1", "path": fx["path"]}
    fresh()
    res = werk_blender.import_file(fx["path"])         # dispatches to image_io
    out["import"] = import_summary(res)
    img = res.image
    packed = bytes(img.packed_file.data) if img.packed_file else b""
    out["image"] = {"name": img.name, "size": [res.width, res.height],
                    "payload_path": res.payload_path,
                    "payload_sha256": res.payload_sha256,
                    "packed_sha256": hashlib.sha256(packed).hexdigest(),
                    "packed_bytes": len(packed),
                    "uuid_prop": img.get("werk_entity_uuid"),
                    "colorspace": img.colorspace_settings.name}
    sha_in, shape_in = pixels_sha(img)
    out["image"]["pixels_sha256"], out["image"]["pixels_shape"] = sha_in, shape_in
    ref = bpy.data.images.load(fx["extracted_primary"], check_existing=False)
    out["reference"] = {"file": fx["extracted_primary"]}
    out["reference"]["pixels_sha256"], out["reference"]["pixels_shape"] = pixels_sha(ref)
    bpy.data.images.remove(ref)
    exp_path = os.path.join(ARGS["out_dir"], fx["key"] + ".blender-export.werk")
    exp = werk_blender.export_image_file(exp_path, img)
    out["export"] = {"path": exp_path, "bytes": exp.bytes, "sha256": exp.sha256,
                     "png_sha256": exp.png_sha256,
                     "size": [exp.width, exp.height, exp.channels],
                     "entity_uuid": exp.entity_uuid,
                     "reused_identity": exp.reused_identity,
                     "library_verdict": exp.library_verdict,
                     "report": [list(r) for r in exp.report]}
    fresh()
    back = werk_blender.import_file(exp_path)
    out["reimport"] = import_summary(back)
    out["reimport"]["entity_uuid"] = back.entity_uuid
    out["reimport"]["pixels_sha256"], out["reimport"]["pixels_shape"] = \
        pixels_sha(back.image)
    out["source_uuid"] = res.entity_uuid
    return out


def main():
    results = {"blender": bpy.app.version_string, "fixtures": [], "errors": []}
    for fx in ARGS["fixtures"]:
        t0 = time.time()
        try:
            r = run_image(fx) if fx["profile"] == "image/1" else run_entity(fx)
        except Exception:  # noqa: BLE001
            r = {"fixture": fx["key"], "profile": fx["profile"],
                 "exception": traceback.format_exc()}
        r["seconds"] = round(time.time() - t0, 2)
        results["fixtures"].append(r)
        print("[gate-release] %s %.1fs" % (fx["key"], r["seconds"]))
        with open(ARGS["result"], "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=1, sort_keys=True)


main()
