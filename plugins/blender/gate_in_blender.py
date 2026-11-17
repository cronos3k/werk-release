#!/usr/bin/env python3
"""The half of the Stage 11 gate that runs INSIDE Blender.

Launched by `plugins/blender/test_gate.py` as

    blender --background --factory-startup --python gate_in_blender.py -- <json>

`--factory-startup` matters: it guarantees no user add-on, preference or
startup file is contributing to the result, so a PASS here is a property of
this code and not of one machine's Blender.

Writes a JSON result document to the path given after `--`. It asserts
nothing itself; it MEASURES, and `test_gate.py` decides. Keeping the judgement
out of the subprocess means a crash cannot be mistaken for a pass.
"""

import json
import os
import sys
import time
import traceback

ARGS = json.loads(sys.argv[sys.argv.index("--") + 1])
sys.path.insert(0, ARGS["addon_parent"])

import bpy  # noqa: E402

import werk_blender  # noqa: E402
from werk_blender.importer import (PROP_SEMANTICS, PROP_UUID)  # noqa: E402

OUT = {"clauses": [], "errors": []}


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def record(name, **fields):
    fields["clause"] = name
    OUT["clauses"].append(fields)
    return fields


def counts():
    return {
        "objects": len(bpy.data.objects),
        "meshes": len(bpy.data.meshes),
        "materials": len(bpy.data.materials),
        "images": len(bpy.data.images),
        "armatures": len(bpy.data.armatures),
        "actions": len(bpy.data.actions),
        "sounds": len(bpy.data.sounds),
    }


def mesh_totals():
    v = t = 0
    for m in bpy.data.meshes:
        m.calc_loop_triangles()
        v += len(m.vertices)
        t += len(m.loop_triangles)
    return v, t


# --- 0. registration, both install shapes ----------------------------------

def clause_registration():
    t0 = time.time()
    reset()
    werk_blender.register()
    have_import = hasattr(bpy.ops.werk, "import_entity")
    have_export = hasattr(bpy.ops.werk, "export_entity")
    werk_blender.unregister()
    # And again, because an add-on that cannot be disabled and re-enabled is an
    # add-on that leaks menu entries.
    werk_blender.register()
    werk_blender.unregister()
    record("registration",
           registered=bool(have_import and have_export),
           import_operator=have_import, export_operator=have_export,
           reregistered=True,
           blender=".".join(str(x) for x in bpy.app.version),
           seconds=round(time.time() - t0, 4))


# --- 1. import the clean fixture -------------------------------------------

def clause_import_clean(path):
    reset()
    t0 = time.time()
    res = werk_blender.import_file(path, import_audio_preview=True)
    elapsed = time.time() - t0
    v, t = mesh_totals()
    record("import_clean",
           path=path,
           seconds=round(elapsed, 4),
           nodes_total=res.nodes_total, nodes_alive=res.nodes_alive,
           nodes_dead=res.nodes_dead, nodes_skipped=res.nodes_skipped_unknown,
           signature=res.signature,
           entity_uuid=res.entity_uuid,
           vertices=v, triangles=t,
           report_entries=len(res.report),
           package_report_entries=len(res.package_report),
           unexpected_skips=[list(x) for x in res.unexpected_skips()],
           errors=res.errors(),
           report_text_present=("werk_import_report.txt" in bpy.data.texts),
           notes_text_present=("werk_work_notes.txt" in bpy.data.texts),
           tags=json.loads(res.root[PROP_SEMANTICS]).get("facets", {})
           if res.root.get(PROP_SEMANTICS) else {},
           **counts())
    return res


# --- 2. import the damaged fixture -----------------------------------------

def clause_import_damaged(path):
    reset()
    t0 = time.time()
    res = werk_blender.import_file(path)
    elapsed = time.time() - t0
    v, t = mesh_totals()
    by_code = {}
    for sev, code, msg in res.report:
        by_code.setdefault(code, []).append(msg)
    pkg_by_code = {}
    for sev, code, msg in res.package_report:
        pkg_by_code.setdefault(code, []).append(msg)
    record("import_damaged",
           path=path,
           seconds=round(elapsed, 4),
           nodes_total=res.nodes_total, nodes_alive=res.nodes_alive,
           nodes_dead=res.nodes_dead, nodes_skipped=res.nodes_skipped_unknown,
           signature=res.signature,
           vertices=v, triangles=t,
           report_codes={k: len(v_) for k, v_ in sorted(by_code.items())},
           package_report_codes={k: len(v_) for k, v_ in sorted(pkg_by_code.items())},
           hash_mismatch_paths=[m for m in pkg_by_code.get("hash-mismatch", [])],
           **counts())
    return res


# --- 3. round trip ---------------------------------------------------------

def clause_round_trip(src, out_path):
    reset()
    t0 = time.time()
    res_in = werk_blender.import_file(src)
    t_import = time.time() - t0
    v1, t1 = mesh_totals()
    uuid_in = res_in.root[PROP_UUID]
    tags_in = json.loads(res_in.root[PROP_SEMANTICS]).get("facets", {}) \
        if res_in.root.get(PROP_SEMANTICS) else {}
    mats_in = len(bpy.data.materials)

    objs = [o for o in bpy.data.objects]
    t1s = time.time()
    exp = werk_blender.export_file(out_path, objects=objs)
    t_export = time.time() - t1s

    reset()
    t2s = time.time()
    res_out = werk_blender.import_file(out_path)
    t_reimport = time.time() - t2s
    v2, t2 = mesh_totals()
    uuid_out = res_out.root[PROP_UUID]
    tags_out = json.loads(res_out.root[PROP_SEMANTICS]).get("facets", {}) \
        if res_out.root.get(PROP_SEMANTICS) else {}

    record("round_trip",
           source=src, exported=out_path,
           import_seconds=round(t_import, 4),
           export_seconds=round(t_export, 4),
           reimport_seconds=round(t_reimport, 4),
           exported_bytes=exp.bytes, exported_sha256=exp.sha256,
           exported_entries=exp.entries, exported_nodes=exp.nodes,
           exported_files=exp.files, exported_manifest_bytes=exp.manifest_bytes,
           preview_prefix_bytes=exp.preview_prefix_bytes,
           reused_identity=exp.reused_identity,
           export_report=[list(x) for x in exp.report],
           vertices_before=v1, vertices_after=v2,
           triangles_before=t1, triangles_after=t2,
           materials_before=mats_in, materials_after=len(bpy.data.materials),
           uuid_before=uuid_in, uuid_after=uuid_out,
           uuid_survived=(uuid_in == uuid_out and bool(uuid_in)),
           tags_before=tags_in, tags_after=tags_out,
           tags_survived=(tags_in == tags_out and bool(tags_in)),
           vertices_survived=(v1 == v2),
           reimport_errors=res_out.errors(),
           reimport_nodes=res_out.nodes_total,
           reimport_alive=res_out.nodes_alive,
           reimport_dead=res_out.nodes_dead,
           reimport_signature=res_out.signature)


# --- 4. determinism of the writer ------------------------------------------

def clause_determinism(src, path_a, path_b):
    reset()
    werk_blender.import_file(src)
    objs = list(bpy.data.objects)
    a = werk_blender.export_file(path_a, objects=objs)
    b = werk_blender.export_file(path_b, objects=objs)
    # `created` is a wall-clock stamp inside the manifest, so two exports a
    # second apart legitimately differ. Compare the payload bytes, which are
    # what a store deduplicates and what byte-identity is actually about.
    import zipfile
    same, differing = 0, []
    with zipfile.ZipFile(path_a) as za, zipfile.ZipFile(path_b) as zb:
        na, nb = za.namelist(), zb.namelist()
        for n in na:
            if n in ("MANIFEST.json",):
                continue
            if n in nb and za.read(n) == zb.read(n):
                same += 1
            else:
                differing.append(n)
    record("determinism",
           entries_a=a.entries, entries_b=b.entries,
           bytes_a=a.bytes, bytes_b=b.bytes,
           payload_entries_identical=same,
           payload_entries_differing=differing,
           order_identical=(na == nb))


# --- 5. a synthetic rig: skeleton + animation, which no fixture exercises ---

def clause_rig_round_trip(out_path):
    """The golden fixture has no skeleton and no animation, so those two paths
    would otherwise ship unmeasured. A rig is built here from scratch, given a
    pose, exported and re-imported, and the bone rest positions and the posed
    rotations are compared. Building the input rather than finding one is
    stated plainly because it is a weaker test than a real asset would be.
    """
    import math
    import mathutils

    reset()
    bpy.ops.mesh.primitive_cube_add(size=0.5, location=(0, 0, 1))
    cube = bpy.context.object
    cube.name = "rig-body"

    bpy.ops.object.armature_add(location=(0, 0, 0))
    arm_obj = bpy.context.object
    arm_obj.name = "test-rig"
    arm = arm_obj.data
    bpy.ops.object.mode_set(mode="EDIT")
    root_eb = arm.edit_bones[0]
    root_eb.name = "root"
    root_eb.head = mathutils.Vector((0.0, 0.0, 0.0))
    root_eb.tail = mathutils.Vector((0.0, 0.0, 0.5))
    child = arm.edit_bones.new("upper")
    child.head = root_eb.tail
    child.tail = mathutils.Vector((0.0, 0.2, 1.0))
    child.parent = root_eb
    tip = arm.edit_bones.new("lower")
    tip.head = child.tail
    tip.tail = mathutils.Vector((0.0, 0.5, 1.4))
    tip.parent = child
    bpy.ops.object.mode_set(mode="OBJECT")

    # A pose with a real rotation on a child bone, keyed over 5 frames, so the
    # clip carries something a wrong conjugation would visibly destroy.
    arm_obj.animation_data_create()
    action = bpy.data.actions.new("test-clip")
    arm_obj.animation_data.action = action
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 0, 4
    for f in range(5):
        scene.frame_set(f)
        pb = arm_obj.pose.bones["upper"]
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = mathutils.Quaternion(
            mathutils.Vector((1.0, 0.0, 0.0)), math.radians(15.0 * f))
        pb.keyframe_insert("rotation_quaternion", frame=f)
    scene.frame_set(0)

    # NOT rounded. `2*acos(|dot|)` is catastrophically sensitive near dot = 1:
    # rounding the components to 5 decimals first manufactured 8e-3 rad of
    # "error" out of a round trip that was in fact exact to 1e-7. The gate was
    # measuring its own rounding, which is the sort of thing that gets called a
    # tolerance and then lived with.
    rest_before = {b.name: tuple(arm_obj.matrix_world @ b.head_local)
                   for b in arm.bones}
    scene.frame_set(3)
    posed_before = {b.name: tuple(arm_obj.pose.bones[b.name].matrix.to_quaternion())
                    for b in arm.bones}

    exp = werk_blender.export_file(out_path, objects=list(bpy.data.objects))

    reset()
    res = werk_blender.import_file(out_path)
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    rest_after, posed_after = {}, {}
    worst_rest = None
    worst_pose = None
    if arms:
        a2 = arms[0]
        rest_after = {b.name: tuple(a2.matrix_world @ b.head_local)
                      for b in a2.data.bones}
        bpy.context.scene.frame_set(3)
        posed_after = {b.name: tuple(a2.pose.bones[b.name].matrix.to_quaternion())
                       for b in a2.data.bones}
        common = sorted(set(rest_before) & set(rest_after))
        if common:
            worst_rest = max(max(abs(x - y) for x, y in
                                 zip(rest_before[k], rest_after[k]))
                             for k in common)
        commonp = sorted(set(posed_before) & set(posed_after))
        if commonp:
            def qdist(p, q):
                # 2*atan2(|p-q|, |p+q|) after sign alignment: numerically
                # stable everywhere, unlike acos(dot), which loses half its
                # significant digits exactly where a good result lands.
                if sum(a * b for a, b in zip(p, q)) < 0.0:
                    q = tuple(-c for c in q)
                diff = math.sqrt(sum((a - b) ** 2 for a, b in zip(p, q)))
                summ = math.sqrt(sum((a + b) ** 2 for a, b in zip(p, q)))
                return 2.0 * math.atan2(diff, summ)
            worst_pose = max(qdist(posed_before[k], posed_after[k]) for k in commonp)

    record("rig_round_trip",
           exported=out_path, exported_bytes=exp.bytes, exported_nodes=exp.nodes,
           bones_before=len(rest_before), bones_after=len(rest_after),
           bone_names_before=sorted(rest_before), bone_names_after=sorted(rest_after),
           actions_after=len(bpy.data.actions),
           worst_rest_head_error_m=worst_rest,
           worst_posed_rotation_error_rad=worst_pose,
           reimport_errors=res.errors(),
           reimport_report=[list(x) for x in res.report if x[0] == "error"],
           export_report=[list(x) for x in exp.report])


def clause_zip_install(zip_path):
    """The other install shape: the add-on unpacked from its distributable zip.

    Blender's own `addon_install` operator copies into the user's Blender
    configuration directory, which this must not scribble in just to run a
    test. Unpacking the zip into scratch and importing `werk_blender` from
    there proves the same thing that matters — that the zip is COMPLETE, that
    the package works with no path back to this repository, and that it
    registers — without leaving anything behind on the machine.
    """
    import shutil
    import tempfile
    import zipfile

    where = tempfile.mkdtemp(prefix="werk-zip-", dir=os.path.dirname(zip_path))
    try:
        with zipfile.ZipFile(zip_path) as z:
            names = z.namelist()
            z.extractall(where)
        # Import it as a DIFFERENT module object from the on-disk one, so a
        # missing file in the zip cannot be masked by the copy already loaded.
        for mod in [m for m in sys.modules if m.split(".")[0] == "werk_blender"]:
            del sys.modules[mod]
        sys.path.insert(0, where)
        try:
            import werk_blender as zipped
            loaded_from = os.path.dirname(os.path.abspath(zipped.__file__))
            from_zip = os.path.normcase(loaded_from).startswith(
                os.path.normcase(where))
            bad = zipped.selftest()
            reset()
            zipped.register()
            registered = hasattr(bpy.ops.werk, "import_entity")
            zipped.unregister()
            spec_files = sum(1 for n in names if n.startswith("werk_blender/spec/"))
            record("zip_install",
                   zip_path=zip_path,
                   zip_bytes=os.path.getsize(zip_path),
                   entries=len(names),
                   spec_files_in_zip=spec_files,
                   loader_in_zip=("werk_blender/vendor/werk_read.py" in names),
                   imported_from_zip=from_zip,
                   selftest_failures=bad,
                   registered=bool(registered))
        finally:
            sys.path.remove(where)
            for mod in [m for m in sys.modules if m.split(".")[0] == "werk_blender"]:
                del sys.modules[mod]
            sys.path.insert(0, ARGS["addon_parent"])
            import werk_blender  # noqa: F401  - restore the on-disk one
    finally:
        shutil.rmtree(where, ignore_errors=True)


def clause_textured_round_trip(out_path):
    """`core.tex` + `core.material` texture slots, which no fixture exercises.

    `fixtures/crate-v1.werk` is vertex-coloured and deliberately carries no
    texture at all (its build script says inventing one would be the single
    thing a conformance fixture must never do), so the whole texture path —
    PNG packing, the mandatory per-texture `color_space`, and the node wiring
    on the way back — would otherwise ship unmeasured. The scene is built here
    instead, and this is stated because a built input is weaker evidence than
    a real asset.

    The colour-space assertion is the one that matters: a base colour is sRGB
    and a roughness map is Non-Color, and getting that backwards is invisible
    in review and obvious on screen.
    """
    reset()
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    cube = bpy.context.object
    cube.name = "textured-cube"

    base = bpy.data.images.new("basecolor", 8, 8, alpha=True)
    base.generated_color = (0.8, 0.35, 0.1, 1.0)
    base.colorspace_settings.name = "sRGB"
    rough = bpy.data.images.new("roughmap", 8, 8, alpha=True, is_data=True)
    rough.generated_color = (0.4, 0.4, 0.4, 1.0)
    rough.colorspace_settings.name = "Non-Color"

    mat = bpy.data.materials.new("painted-wood")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Metallic"].default_value = 0.25
    bsdf.inputs["Roughness"].default_value = 0.6
    tb = nt.nodes.new("ShaderNodeTexImage")
    tb.image = base
    nt.links.new(tb.outputs["Color"], bsdf.inputs["Base Color"])
    tr = nt.nodes.new("ShaderNodeTexImage")
    tr.image = rough
    nt.links.new(tr.outputs["Color"], bsdf.inputs["Roughness"])
    cube.data.materials.append(mat)

    metallic_before = bsdf.inputs["Metallic"].default_value
    exp = werk_blender.export_file(out_path, objects=[cube])

    # What did the package actually declare? Read it back with the vendored
    # reader rather than trusting the exporter's own account of itself.
    import json as _json
    import zipfile
    tex_meta = {}
    material_payload = None
    with zipfile.ZipFile(out_path) as z:
        man = _json.loads(z.read("MANIFEST.json").decode("utf-8"))
        for n in man["nodes"]:
            if n["type"] == "core.tex":
                tex_meta[n["node_id"]] = n.get("meta", {})
            if n["type"] == "core.material":
                material_payload = _json.loads(
                    z.read(n["versions"][0]["files"][0]["path"]).decode("utf-8"))

    reset()
    res = werk_blender.import_file(out_path)
    imgs = {i.name: i.colorspace_settings.name for i in bpy.data.images}
    mats = [m for m in bpy.data.materials]
    metallic_after = None
    slots_wired = 0
    if mats:
        m2 = mats[0]
        if m2.use_nodes:
            b2 = next((n for n in m2.node_tree.nodes
                       if n.type == "BSDF_PRINCIPLED"), None)
            if b2:
                metallic_after = b2.inputs["Metallic"].default_value
            slots_wired = sum(1 for n in m2.node_tree.nodes if n.type == "TEX_IMAGE")

    record("textured_round_trip",
           exported=out_path, exported_bytes=exp.bytes, exported_nodes=exp.nodes,
           tex_nodes=len(tex_meta),
           tex_meta=tex_meta,
           material_texture_slots=sorted((material_payload or {})
                                         .get("textures", {}).keys()),
           material_metallic=(material_payload or {}).get("metallic_factor"),
           images_after=imgs,
           image_count_after=len(imgs),
           tex_image_nodes_after=slots_wired,
           metallic_before=metallic_before, metallic_after=metallic_after,
           reimport_errors=res.errors(),
           export_report=[list(x) for x in exp.report])


def clause_point_cloud(path):
    """Stage 12: a real Gaussian splat, imported as a point cloud.

    What is measured, and why each one is here rather than "it imported":

      * the point COUNT survives, so nothing was decimated on the way in;
      * a colour attribute exists on the POINT domain, because a point cloud
        whose colours landed on faces would have no faces to land on;
      * the first vertex's coordinates equal the splat's first `means` record
        put through the Y-up -> Z-up swing, checked against a value read out
        of the payload by the importer's own envelope reader -- so a silent
        axis change cannot pass;
      * the splat node is NOT imported a second time, because a core.geom.points
        node was derived from it (importer._import_points' second rule).
    """
    reset()
    from werk_blender import importer as IMP
    from werk_blender.vendor import werk_read

    t0 = time.time()
    res = IMP.import_file(path, import_colliders=False, import_skeleton=False,
                          import_animation=False, write_report_text=False)
    dt = time.time() - t0

    pkg = werk_read.Package(path)
    declared = {}
    for n in pkg.nodes:
        if n["type"] in ("core.geom.points", "core.geom.gsplat"):
            ver = IMP.resolved_version(n) or {}
            for f in ver.get("files", []):
                if f["path"].endswith((".wkpc", ".wkgs")):
                    _m, _v, hdr = werk_read.read_envelope(pkg.blob(f["path"]))
                    declared[n["type"]] = {"count": hdr["count"],
                                           "path": f["path"]}
                    if n["type"] == "core.geom.gsplat":
                        sec = next(x for x in hdr["sections"]
                                   if x["name"] == "means")
                        declared["first_mean"] = werk_read.read_section(
                            pkg.blob(f["path"]), sec, first=1)[0]

    clouds = [o for o in bpy.data.objects
              if o.type == "MESH" and o.name.startswith("werk:points:")]
    splat_clouds = [o for o in bpy.data.objects
                    if o.type == "MESH" and o.name.startswith("werk:gsplat:")]
    verts = len(clouds[0].data.vertices) if clouds else 0
    colour_domain = None
    colour_count = 0
    first_co = None
    if clouds:
        me = clouds[0].data
        for a in me.color_attributes:
            if a.name == "werk_color":
                colour_domain = a.domain
                colour_count = len(a.data)
        first_co = list(me.vertices[0].co) if len(me.vertices) else None

    expect_co = None
    if "first_mean" in declared:
        from werk_blender import axes
        expect_co = list(axes.vec_werk_to_blender(declared["first_mean"]))

    record("point_cloud",
           seconds=round(dt, 3),
           declared=declared,
           point_cloud_objects=len(clouds),
           gsplat_objects=len(splat_clouds),
           vertices=verts,
           colour_domain=colour_domain,
           colour_count=colour_count,
           first_vertex=first_co,
           expected_first_vertex=expect_co,
           report=[(sev, code) for sev, code, _m in res.report
                   if code in ("points-imported", "gsplat-degraded-to-points",
                               "gsplat-degradation-skipped")],
           nodes_alive=res.nodes_alive,
           nodes_dead=res.nodes_dead)


def main():
    try:
        clause_registration()
    except Exception:  # noqa: BLE001
        OUT["errors"].append("registration: " + traceback.format_exc())

    if ARGS.get("addon_zip"):
        try:
            clause_zip_install(ARGS["addon_zip"])
        except Exception:  # noqa: BLE001
            OUT["errors"].append("zip_install: " + traceback.format_exc())

    for fn, args in (
            (clause_import_clean, (ARGS["clean"],)),
            (clause_import_damaged, (ARGS["damaged"],)),
            (clause_round_trip, (ARGS["clean"], ARGS["round_trip_out"])),
            (clause_determinism, (ARGS["clean"], ARGS["determinism_a"],
                                  ARGS["determinism_b"])),
            (clause_rig_round_trip, (ARGS["rig_out"],)),
            (clause_textured_round_trip, (ARGS["textured_out"],)),
    ) + ((((clause_point_cloud, (ARGS["gsplat"],)),) if ARGS.get("gsplat") else ())):
        try:
            fn(*args)
        except Exception:  # noqa: BLE001
            OUT["errors"].append("%s: %s" % (fn.__name__, traceback.format_exc()))

    with open(ARGS["result"], "w", encoding="utf-8") as fh:
        json.dump(OUT, fh, indent=2, sort_keys=True)
    print("werk gate: wrote %s" % ARGS["result"])


main()
