#!/usr/bin/env python3
"""The half of build_crate_tex.py that runs INSIDE Blender.

    blender --background --factory-startup --python build_crate_tex_in_blender.py -- \
        --src crate-v1.werk --out crate-tex-v1.werk \
        --albedo a.png --normal n.png --mr mr.png \
        --addon <repo>/adapters/blender --report report.json

`--factory-startup` for the same reason the Stage 11 gate uses it: no user
add-on or preference may contribute to a fixture's bytes.

It writes a JSON report of MEASURED facts and asserts nothing; the outer script
decides. Same split as the Blender gate, same reason: a crash in here must not
be mistakable for a success.
"""

import argparse
import json
import os
import sys

import bpy

ARGV = sys.argv[sys.argv.index("--") + 1:]
AP = argparse.ArgumentParser()
AP.add_argument("--src", required=True)
AP.add_argument("--out", required=True)
AP.add_argument("--albedo", required=True)
AP.add_argument("--normal", required=True)
AP.add_argument("--mr", required=True)
AP.add_argument("--addon", required=True)
AP.add_argument("--report", required=True)
AP.add_argument("--created", required=True)
AP.add_argument("--source-label", required=True)
A = AP.parse_args(ARGV)

sys.path.insert(0, A.addon)
import werk_blender  # noqa: E402
import werk_blender.exporter  # noqa: E402

# The exporter stamps `created` with the wall clock. A fixture must not, so
# the builder supplies the fixed value (build_crate_tex.py CREATED).
werk_blender.exporter._now = lambda: A.created


def box_uvs(mesh):
    """Analytic box projection: the face's dominant normal axis picks the plane.

    Deliberately NOT Smart UV Project. An unwrapper's output is not promised
    stable across Blender releases, and a fixture whose bytes depend on that is
    not a fixture. This is six planar projections and a stated scale, so the
    same mesh gives the same UVs on any version that can run the script.
    """
    if not mesh.uv_layers:
        mesh.uv_layers.new(name="UVMap")
    uv = mesh.uv_layers.active.data

    lo = [min(v.co[i] for v in mesh.vertices) for i in range(3)]
    hi = [max(v.co[i] for v in mesh.vertices) for i in range(3)]
    span = [max(1e-9, hi[i] - lo[i]) for i in range(3)]
    scale = max(span)

    for poly in mesh.polygons:
        n = poly.normal
        axis = max(range(3), key=lambda i: abs(n[i]))
        u_ax, v_ax = {0: (1, 2), 1: (0, 2), 2: (0, 1)}[axis]
        for li in poly.loop_indices:
            co = mesh.vertices[mesh.loops[li].vertex_index].co
            uv[li].uv = ((co[u_ax] - lo[u_ax]) / scale,
                         (co[v_ax] - lo[v_ax]) / scale)
    return len(mesh.uv_layers)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # The mesh comes from the golden fixture, imported by the add-on that is
    # already gate-measured, so this fixture's geometry is the real crate and
    # not a primitive standing in for one.
    res = werk_blender.import_file(A.src)
    # The importer records the absolute source path as `werk_source`, and the
    # exporter writes it into game.glb. Record a host-independent name instead.
    for o in bpy.data.objects:
        if "werk_source" in o.keys():
            o["werk_source"] = A.source_label
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not meshes:
        raise SystemExit("no mesh imported from %s" % A.src)
    # core.geom.game, not core.geom.source: the source has no normals (S-9) and
    # is the archival anchor, not the renderable thing.
    obj = sorted(meshes, key=lambda o: o.name)[0]
    for other in meshes:
        if other is not obj:
            bpy.data.objects.remove(other, do_unlink=True)

    uv_layers = box_uvs(obj.data)

    def load(path, name, colorspace, usage):
        img = bpy.data.images.load(os.path.abspath(path))
        img.name = name
        img.colorspace_settings.name = colorspace
        # The add-on reads these custom properties before it guesses from the
        # name, so the declared value is the one that travels.
        img["werk_color_space"] = "srgb" if colorspace == "sRGB" else "linear"
        img["werk_usage"] = usage
        return img

    albedo = load(A.albedo, "crate-tex-albedo", "sRGB", "base-color")
    normal = load(A.normal, "crate-tex-normal", "Non-Color", "normal")
    mr = load(A.mr, "crate-tex-mr", "Non-Color", "metallic-roughness")

    mat = bpy.data.materials.new("crate-planks")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = 0.85
    bsdf.inputs["Base Color"].default_value = (1.0, 1.0, 1.0, 1.0)

    n_albedo = nt.nodes.new("ShaderNodeTexImage")
    n_albedo.image = albedo
    nt.links.new(n_albedo.outputs["Color"], bsdf.inputs["Base Color"])

    n_mr = nt.nodes.new("ShaderNodeTexImage")
    n_mr.image = mr
    nt.links.new(n_mr.outputs["Color"], bsdf.inputs["Roughness"])

    n_normal = nt.nodes.new("ShaderNodeTexImage")
    n_normal.image = normal
    n_nmap = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(n_normal.outputs["Color"], n_nmap.inputs["Color"])
    nt.links.new(n_nmap.outputs["Normal"], bsdf.inputs["Normal"])

    obj.data.materials.clear()
    obj.data.materials.append(mat)

    exp = werk_blender.export_file(
        A.out, objects=[obj],
        entity_name="Wooden crate, textured",
        summary=(
            "A TEST fixture, not a scan. The geometry is the golden crate's own "
            "core.geom.game mesh; the UVs are an analytic box projection and the "
            "three maps are generated from a stated procedure in "
            "fixtures/build_crate_tex.py. It exists so that the core.tex and "
            "core.material texture-slot paths have a measured input, which "
            "fixtures/crate-v1.werk deliberately cannot provide."))

    # Read the result back with the vendored reader rather than trusting the
    # exporter's account of itself.
    import zipfile
    tex_meta, slots, material_payload = {}, [], None
    with zipfile.ZipFile(A.out) as z:
        man = json.loads(z.read("MANIFEST.json").decode("utf-8"))
        for n in man["nodes"]:
            if n["type"] == "core.tex":
                tex_meta[n["node_id"]] = n.get("meta", {})
            if n["type"] == "core.material":
                material_payload = json.loads(
                    z.read(n["versions"][0]["files"][0]["path"]).decode("utf-8"))
        slots = sorted((material_payload or {}).get("textures", {}).keys())

    mesh = obj.data
    report = {
        "nodes": exp.nodes,
        "bytes": exp.bytes,
        "tex_nodes": len(tex_meta),
        "material_slots": slots,
        "uv_layers": uv_layers,
        "verts": len(mesh.vertices),
        "tris": sum(len(p.vertices) - 2 for p in mesh.polygons),
        "color_space": {k: v.get("color_space") for k, v in tex_meta.items()},
        "usage": {k: v.get("usage") for k, v in tex_meta.items()},
        "import_report": list(res.package_report),
        "material_payload": material_payload,
    }
    with open(A.report, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)


main()
