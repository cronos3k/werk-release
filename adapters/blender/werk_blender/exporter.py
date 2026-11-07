"""Blender -> werk.

Writes an unsigned, conformant, store-mode `.werk`. Unsigned is deliberate:
signing needs a private key, and SPEC section 6's three states make `absent`
a legitimate, visible state rather than a defect. An exporter that minted a
key so the output "looked signed" would defeat the doctrine it is implementing.

Every node this writes carries the full apparatus, because the apparatus is
the format:

  * a `versions[]` entry with `v`, `files[]`, `created`,
  * a work note of real substance (law 6; the schema enforces >= 8 characters
    and a note that says `update` satisfies the schema while betraying the law,
    so these say what and why),
  * `producer {tool: "werk_blender", version, model?}` plus the Blender build
    that made it,
  * an `epistemic` stamp, and where that stamp is `measured`, an ordered
    `input_files` and the `input_hash` computed over them — including the two
    bytes `{}` for the absent `input_params` (S-10),
  * real sha256s over the bytes actually written, never a placeholder.

Identity survives (law 4): if the scene came from `import_file`, the entity
uuid, the node ids, the parts table, the materials table and the semantics
payload are read back off the root empty. Only a scene with no werk ancestry
gets a fresh uuid.
"""

import datetime
import json
import os
import time
import uuid as uuidlib

import bpy
import mathutils

from . import axes, bounds, envelope, wzip
from .common import Scratch, input_hash, is_valid_id, jbytes, kebab, sha256_hex, \
    unique_id
from .importer import (PROP_CLIP_ID, PROP_LICENSE, PROP_MATERIALS, PROP_MATERIAL_ID,
                       PROP_NAME, PROP_NODE_IDS, PROP_PARTS, PROP_PRIMARY,
                       PROP_SEMANTICS, PROP_SKELETON_ID, PROP_UUID)

TOOL = "werk_blender"
TOOL_VERSION = "1.0.0"

#: The spec tree vendored into this add-on, shipped inside every package it
#: writes so the manifest's `schemas` map points at files that are really
#: there (SPEC section 2) and law 2 holds for the output as well as the input.
SPEC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spec")
LOADER_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "vendor", "werk_read.py")

#: Which convention -> node-type map this profile's packages declare (S-17,
#: ruled 2026-08-08). Declared rather than derived, like every other path in a
#: manifest; the file itself travels in the vendored spec/ tree above.
CONVENTIONS_MAP = "spec/conventions-map.json"


def spec_sha256_of(blobs):
    """The manifest's mandatory `spec_sha256` (S-29, ruled 2026-08-08).

    One sha256 over the spec/ tree this package carries, so a reader can tell
    in one comparison whether the schemas travelling inside the file are the
    ones it already knows. Vendoring spec/ is structural for this add-on -
    installed from a zip, it has no path back to the repository and must ship
    the bytes - and this field is what stops that copy being an unversioned
    one. The algorithm is spec/SPEC.md section 2's, and the reference
    implementation is tools/spec_sha256.py in the werk repository; it is
    re-implemented here rather than imported because an add-on with an import
    is an add-on with a dependency.

    Sort spec/ paths ascending by UTF-8 bytes; for each append
    path || 0x0A || sha256(bytes) as 32 RAW bytes || 0x0A; hash the lot. Note
    that for a single file this is NOT that file's own sha256.
    """
    import hashlib
    acc = hashlib.sha256()
    for path in sorted((k for k in blobs if k.startswith("spec/")),
                       key=lambda k: k.encode("utf-8")):
        acc.update(path.encode("utf-8"))
        acc.update(b"\n")
        acc.update(hashlib.sha256(blobs[path]).digest())
        acc.update(b"\n")
    return acc.hexdigest()


NO_LICENSE_TEXT = (
    "NO LICENCE WAS DECLARED FOR THIS PACKAGE.\n"
    "\n"
    "Law 7 says a licence travels inside the file as full text, never as a\n"
    "link. This file is not a licence and grants nothing. It is here because\n"
    "the exporter was not told what the terms are, and because a package that\n"
    "silently omitted its LICENSE would look licensed-by-omission to every\n"
    "downstream reader.\n"
    "\n"
    "Set the terms before distributing this package: pass `license_text` to\n"
    "werk_blender.export_file(), or put the full text in the `werk_license`\n"
    "custom property on the exported root object. A package imported from an\n"
    "existing .werk carries its original licence forward automatically.\n"
)


class ExportResult(object):
    def __init__(self):
        self.path = ""
        self.bytes = 0
        self.sha256 = ""
        self.entries = 0
        self.nodes = 0
        self.files = 0
        self.manifest_bytes = 0
        self.preview_prefix_bytes = 0
        self.entity_uuid = ""
        self.reused_identity = False
        self.vertex_count = 0
        self.triangle_count = 0
        self.report = []
        self.seconds = 0.0

    def add(self, severity, code, message):
        self.report.append((severity, code, message))

    def errors(self):
        return sum(1 for s, _, _ in self.report if s == "error")


def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _blender_version():
    return ".".join(str(v) for v in bpy.app.version)


# ---------------------------------------------------------------------------
# selection
# ---------------------------------------------------------------------------

def _gather(objects=None, collection=None):
    if objects:
        objs = list(objects)
    elif collection is not None:
        objs = list(collection.all_objects)
    else:
        objs = [o for o in bpy.context.selected_objects] or \
            list(bpy.context.scene.collection.all_objects)
    seen = {}
    for o in objs:
        seen[o.name] = o
        p = o.parent
        while p is not None:
            seen.setdefault(p.name, p)
            p = p.parent
    return list(seen.values())


def _find_root(objs):
    """The `werk:` empty an import left behind, if any of these objects is
    under one. It is what carries the entity's identity."""
    for o in objs:
        node = o
        while node is not None:
            if PROP_UUID in node.keys():
                return node
            node = node.parent
    return None


# ---------------------------------------------------------------------------
# geometry
# ---------------------------------------------------------------------------

def _evaluated_werk_vertices(obj, depsgraph):
    """World-space vertices and triangles of one evaluated mesh, converted into
    werk model space by `axes.py`.

    Evaluated, not raw: modifiers are part of what the artist sees, and the GLB
    the exporter writes is also evaluated (`export_apply=True`). Bounds
    computed off the un-evaluated mesh would describe a different object from
    the one in the file, which is the exact class of silent disagreement law 5
    exists to catch.
    """
    ev = obj.evaluated_get(depsgraph)
    try:
        mesh = ev.to_mesh()
    except RuntimeError:
        return [], []
    if mesh is None:
        return [], []
    try:
        mw = ev.matrix_world
        pts = [axes.vec_blender_to_werk(mw @ v.co) for v in mesh.vertices]
        tris = []
        mesh.calc_loop_triangles()
        for t in mesh.loop_triangles:
            tris.append(tuple(t.vertices))
        return pts, tris
    finally:
        ev.to_mesh_clear()


def _export_glb(objs, path, res, with_materials=True):
    """Blender's bundled glTF exporter writes the game mesh.

    It performs the Z-up -> Y-up swing, which is the same swing `axes.py`
    performs for everything that does NOT go through a GLB. Images are
    deliberately NOT embedded (`export_image_format='NONE'`): the textures are
    `core.tex` nodes with their colour space declared per texture, and
    embedding them in the GLB as well would put the same bytes in the package
    twice under two different authorities.
    """
    prev_selected = list(bpy.context.selected_objects)
    prev_active = bpy.context.view_layer.objects.active
    try:
        bpy.ops.object.select_all(action="DESELECT")
    except RuntimeError:
        pass
    # An armature only belongs in the GLB when a mesh is actually skinned to
    # it: glTF needs the joint nodes for JOINTS_0/WEIGHTS_0 (SPEC 3.10), and
    # nothing else. An UNSKINNED armature in the GLB would be a second
    # authority on the rest pose beside `core.skeleton` — measured: a
    # re-import produced two armatures from one rig, and the glTF one had lost
    # the roll that `core.skeleton`'s `axis_back` exists to pin.
    meshes = [o for o in objs if o.type == "MESH"]
    skinned_to = set()
    for m in meshes:
        if m.parent is not None and m.parent_type == "ARMATURE":
            skinned_to.add(m.parent.name)
        for mod in m.modifiers:
            if mod.type == "ARMATURE" and mod.object is not None:
                skinned_to.add(mod.object.name)
    exportable = []
    dropped = []
    for o in objs:
        if o.type == "ARMATURE" and o.name not in skinned_to:
            dropped.append(o.name)
            continue
        if o.type in ("MESH", "ARMATURE", "EMPTY", "CURVE"):
            exportable.append(o)
    if dropped:
        res.add("info", "armature-not-in-glb",
                "%s: no exported mesh is skinned to it, so it is carried by the "
                "core.skeleton node alone rather than twice"
                % ", ".join(sorted(dropped)))
    for o in exportable:
        try:
            o.select_set(True)
        except RuntimeError:
            pass
    if exportable:
        bpy.context.view_layer.objects.active = exportable[0]

    kwargs = dict(
        filepath=path,
        export_format="GLB",
        use_selection=True,
        export_yup=True,
        export_apply=True,
        export_normals=True,
        export_materials="EXPORT" if with_materials else "NONE",
        export_image_format="NONE",
        export_extras=True,
        export_cameras=False,
        export_lights=False,
        # Animation lives in `core.anim.clip`, which is the authority. Letting
        # the GLB carry it too would put the same clip in the package twice
        # under two encodings, and a re-import would produce two actions from
        # one — measured, and this is the line that fixed it.
        export_animations=False,
        export_skins=True,
    )
    try:
        bpy.ops.export_scene.gltf(**kwargs)
    except TypeError as e:
        # Blender's glTF operator gains and loses keywords between releases;
        # drop to the guaranteed core set rather than fail the export.
        res.add("info", "gltf-args-reduced",
                "this Blender build rejected an export keyword (%s); retried with "
                "the minimal argument set" % e)
        bpy.ops.export_scene.gltf(filepath=path, export_format="GLB",
                                  use_selection=True, export_apply=True)
    finally:
        try:
            bpy.ops.object.select_all(action="DESELECT")
            for o in prev_selected:
                o.select_set(True)
            bpy.context.view_layer.objects.active = prev_active
        except (RuntimeError, ReferenceError):
            pass
    with open(path, "rb") as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# textures and materials
# ---------------------------------------------------------------------------

_INPUT_TO_SLOT = {
    "Base Color": "base_color",
    "Normal": "normal",
    "Emission Color": "emission",
}


def _material_payload(mat, material_id, tex_nodes, res):
    """Flatten a Blender material onto the metallic-roughness JSON schema.

    Only what the schema can hold travels. A node group, a mix shader or a
    procedural texture has no representation in `core.material` and is
    reported rather than approximated: an exporter that guessed a roughness
    for an arbitrary shader graph would be writing an `authored` number that
    nobody authored.
    """
    payload = {
        "material_id": material_id,
        "name": mat.name,
        "model": "metallic-roughness",
        "base_color_factor": [1.0, 1.0, 1.0, 1.0],
        "metallic_factor": 0.0,
        "roughness_factor": 0.5,
        "alpha_mode": "opaque",
        "double_sided": not mat.use_backface_culling,
        "epistemic": "authored",
    }
    bsdf = None
    if mat.use_nodes and mat.node_tree:
        bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"),
                    None)
    if bsdf is None:
        payload["note"] = (
            "Exported from a Blender material with no Principled BSDF; the "
            "factors here are the schema's neutral defaults and are NOT a "
            "description of that shader graph. Stated rather than guessed.")
        res.add("warn", "material-not-principled",
                "%s: no Principled BSDF; neutral defaults written and said so"
                % mat.name)
        return payload

    def get(name, default=None):
        sock = bsdf.inputs.get(name)
        if sock is None:
            return default
        try:
            v = sock.default_value
        except AttributeError:
            return default
        return list(v) if hasattr(v, "__len__") else v

    base = get("Base Color", [1.0, 1.0, 1.0, 1.0]) or [1.0, 1.0, 1.0, 1.0]
    alpha = get("Alpha", 1.0)
    payload["base_color_factor"] = [
        min(1.0, max(0.0, float(base[0]))), min(1.0, max(0.0, float(base[1]))),
        min(1.0, max(0.0, float(base[2]))), min(1.0, max(0.0, float(alpha)))]
    payload["metallic_factor"] = min(1.0, max(0.0, float(get("Metallic", 0.0))))
    payload["roughness_factor"] = min(1.0, max(0.0, float(get("Roughness", 0.5))))
    ior = get("IOR")
    if ior is not None:
        payload["ior"] = min(3.0, max(1.0, float(ior)))
    emis = get("Emission Color")
    strength = get("Emission Strength", 0.0)
    if emis and strength and float(strength) > 0.0:
        payload["emissive_factor"] = [min(1.0, max(0.0, float(c))) for c in emis[:3]]
        payload["emissive_strength"] = float(strength)

    slots = {}
    for link in mat.node_tree.links:
        to_sock = link.to_socket
        # `==`, NOT `is`: Blender hands out a FRESH Python wrapper for the
        # same RNA struct on every access, so `link.to_node is bsdf` is False
        # even when they are the same node. `==` compares the underlying
        # pointer and is the only correct test. Measured: every texture slot
        # silently vanished from every exported material.
        if link.to_node != bsdf and link.to_node.type != "NORMAL_MAP":
            continue
        src = link.from_node
        chain = []
        while src is not None and src.type in ("NORMAL_MAP", "SEPARATE_COLOR",
                                               "SEPRGB"):
            up = next((l for l in mat.node_tree.links if l.to_node == src), None)
            chain.append(src.type)
            src = up.from_node if up else None
        if src is None or src.type != "TEX_IMAGE" or src.image is None:
            continue
        node_id = tex_nodes.get(src.image.name)
        if node_id is None:
            continue
        if "NORMAL_MAP" in chain or to_sock.name == "Normal":
            slot = "normal"
        elif "SEPARATE_COLOR" in chain or "SEPRGB" in chain or \
                to_sock.name in ("Roughness", "Metallic"):
            slot = "metallic_roughness"
        elif to_sock.name == "Base Color":
            slot = "base_color"
        elif to_sock.name == "Emission Color":
            slot = "emissive"
        else:
            continue
        entry = {"node": node_id, "path": tex_nodes["__path__"][src.image.name],
                 "uv_set": 0}
        if slot == "metallic_roughness":
            entry["channel"] = "rgb"
        slots[slot] = entry
    if slots:
        payload["textures"] = slots
    payload["note"] = (
        "Flattened from Blender material `%s` by %s %s. Factors are read from "
        "the Principled BSDF; anything the metallic-roughness schema cannot "
        "hold was left out rather than approximated." % (mat.name, TOOL, TOOL_VERSION))
    return payload


def _save_image_png(img, path, res):
    """Write one Blender image out as PNG, and say which colour space it is in.

    `core.tex` node `meta.color_space` is mandatory in the manifest and this is
    where it is decided. Blender's `Non-Color` and everything that is not
    `sRGB` map to werk's `linear`, which is the correct direction: a data map
    (normal, roughness, AO) read as sRGB is wrong maths, and that is the
    failure worth preventing.
    """
    scene = bpy.context.scene
    settings = scene.render.image_settings
    old = (settings.file_format, settings.color_mode, settings.color_depth,
           settings.compression)
    settings.file_format = "PNG"
    settings.color_mode = "RGBA"
    settings.color_depth = "16" if img.is_float and img.depth > 32 else "8"
    settings.compression = 15
    try:
        img.save_render(bpy.path.abspath(path), scene=scene) \
            if img.type == "RENDER_RESULT" else img.save(filepath=path)
    except Exception as e:  # noqa: BLE001
        res.add("warn", "texture-save-failed", "%s: %s" % (img.name, e))
        return None
    finally:
        (settings.file_format, settings.color_mode, settings.color_depth,
         settings.compression) = old
    with open(path, "rb") as fh:
        return fh.read()


def _png_info(data):
    import struct
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    ln, tag = struct.unpack(">I4s", data[8:16])
    if tag != b"IHDR":
        return None
    w, h, depth, color = struct.unpack(">IIBB", data[16:26])
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color)
    if channels is None:
        return None
    return {"width": w, "height": h, "bit_depth": depth, "channels": channels}


_USAGE_BY_SLOT = {"base_color": "base-color", "normal": "normal",
                  "metallic_roughness": "metallic-roughness",
                  "emissive": "emissive", "occlusion": "occlusion"}


def _image_usage(img):
    declared = img.get("werk_usage")
    if declared in ("base-color", "normal", "metallic-roughness", "occlusion",
                    "emissive", "height", "opacity", "mrao", "depth", "other"):
        return declared
    name = (img.name or "").lower()
    for key, usage in (("normal", "normal"), ("rough", "metallic-roughness"),
                       ("metal", "metallic-roughness"), ("occl", "occlusion"),
                       ("emis", "emissive"), ("height", "height"),
                       ("basecolor", "base-color"), ("albedo", "base-color"),
                       ("diffuse", "base-color")):
        if key in name:
            return usage
    return "other"


# ---------------------------------------------------------------------------
# skeleton and animation
# ---------------------------------------------------------------------------

def _skeleton_payload(arm_obj, skeleton_id, res):
    """A Blender armature as `core.skeleton` JSON, in werk model space.

    Blender's bone convention IS werk's declared one — local +Y from head to
    tail, local +Z as the roll reference — which is why the skeleton schema
    pins `bone_axis_along: "+y"` and `bone_axis_back: "+z"` and says so. The
    only conversion is the up-axis swing.

    Both the LOCAL and the MODEL-space rest values are written, as the schema
    requires. They are redundant by construction and that is the point: it is
    what makes the local numbers checkable by hand, and the exporter verifies
    the recomposition itself before writing (schema: a reader MUST verify
    within 1e-5), so a bad export fails here instead of in someone's runtime.
    """
    arm = arm_obj.data
    obj_mat = arm_obj.matrix_world
    ordered = []
    seen = set()

    def visit(bone):
        if bone.name in seen:
            return
        seen.add(bone.name)
        ordered.append(bone)
        for c in bone.children:
            visit(c)

    for b in arm.bones:
        if b.parent is None:
            visit(b)

    ids = {}
    taken = set()
    for b in ordered:
        ids[b.name] = unique_id(b.name, taken, fallback="bone")

    bones = []
    worst_residual = 0.0
    for b in ordered:
        world = obj_mat @ b.matrix_local
        loc, rot, _scale = world.decompose()
        head_w = axes.vec_blender_to_werk(loc)
        along_b = (world.to_3x3() @ mathutils.Vector((0.0, 1.0, 0.0))).normalized()
        back_b = (world.to_3x3() @ mathutils.Vector((0.0, 0.0, 1.0))).normalized()
        length = max(float(b.length), 1e-6)
        tail_w = axes.vec_blender_to_werk(loc + along_b * b.length)
        # bone-local -> model: only the model end changes convention, because
        # the schema pins bone_axis_along/+y and bone_axis_back/+z, which are
        # Blender's own. LEFT-MULTIPLY, never conjugate. See axes.py.
        model_rot = axes.frame_blender_to_werk((rot.w, rot.x, rot.y, rot.z))

        if b.parent is None:
            # A root bone's parent IS model space, so its rest values are the
            # model-space ones.
            local_mat = world
            rest_rot = model_rot
            rest_trans = list(head_w)
        else:
            parent_world = obj_mat @ b.parent.matrix_local
            local_mat = parent_world.inverted() @ world
            l_loc, l_rot, _ = local_mat.decompose()
            # A non-root bone's local rest values are expressed in the PARENT
            # BONE's frame, and that frame swings with the bone, so they are
            # INVARIANT under the werk<->Blender conversion. Converting them
            # would be the bug; see axes.py.
            rest_rot = axes.quat_canonical((l_rot.w, l_rot.x, l_rot.y, l_rot.z))
            rest_trans = [float(l_loc.x), float(l_loc.y), float(l_loc.z)]

        entry = {
            "bone_id": ids[b.name],
            "parent": ids[b.parent.name] if b.parent else None,
            "rest_rotation": [round(float(c), 9) for c in rest_rot],
            "rest_translation": [round(float(c), 9) for c in rest_trans],
            "length_m": round(length, 9),
            "model_rest_rotation": [round(float(c), 9) for c in model_rot],
            "model_rest_head_m": [round(float(c), 9) for c in head_w],
            "model_rest_tail_m": [round(float(c), 9) for c in tail_w],
            "axis_along": [round(float(c), 9)
                           for c in axes.vec_blender_to_werk(along_b)],
            "axis_back": [round(float(c), 9)
                          for c in axes.vec_blender_to_werk(back_b)],
            "leaf": len(b.children) == 0,
        }
        bones.append(entry)

    # Recompose the local chain and compare against the declared model-space
    # values, exactly as the schema tells a READER to. A writer that does not
    # check its own redundancy has written two numbers and verified neither.
    by_id = {e["bone_id"]: e for e in bones}
    accum = {}
    for e in bones:
        q_local = mathutils.Quaternion(e["rest_rotation"])
        t_local = mathutils.Vector(e["rest_translation"])
        if e["parent"] is None:
            model_q, model_t = q_local.copy(), t_local.copy()
        else:
            pq, pt = accum[e["parent"]]
            model_q = pq @ q_local
            model_t = pt + pq @ t_local
        accum[e["bone_id"]] = (model_q, model_t)
        declared_q = mathutils.Quaternion(e["model_rest_rotation"])
        if declared_q.dot(model_q) < 0.0:
            model_q = mathutils.Quaternion([-c for c in model_q])
        rq = max(abs(a - b_) for a, b_ in zip(model_q, declared_q))
        rt = max(abs(a - b_) for a, b_ in
                 zip(model_t, mathutils.Vector(e["model_rest_head_m"])))
        worst_residual = max(worst_residual, rq, rt)

    if worst_residual > 1e-5:
        res.add("warn", "skeleton-recomposition-residual",
                "%s: local->model recomposition differs from the declared model "
                "values by %.3g, above the schema's 1e-5 tolerance; written anyway "
                "with this report rather than silently" % (skeleton_id, worst_residual))
    else:
        res.add("info", "skeleton-recomposition-ok",
                "%s: local->model recomposition residual %.3g (tolerance 1e-5)"
                % (skeleton_id, worst_residual))

    height = 0.0
    for e in bones:
        height = max(height, e["model_rest_head_m"][1], e["model_rest_tail_m"][1])

    payload = {
        "schema_version": 1,
        "skeleton_id": skeleton_id,
        "name": arm_obj.name,
        "status": "draft",
        "conventions": {
            "up_axis": "y", "forward_axis": "-z", "right_axis": "+x",
            "handedness": "right", "quat_order": "wxyz", "units_per_meter": 1.0,
            "bone_axis_along": "+y", "bone_axis_back": "+z",
            "composition": "M_bone = M_parent * T(rest_translation) * R(rest_rotation)",
        },
        "bones": bones,
        "epistemic": "authored",
        "note": "Read out of Blender armature `%s`. Blender's bone convention is "
                "the one this schema declares (+Y head-to-tail, +Z roll "
                "reference), so only the up-axis swing was applied. Local and "
                "model-space values were recomposed and compared before writing; "
                "the residual is %.3g." % (arm_obj.name, worst_residual),
    }
    if height > 0.0:
        payload["reference_height_m"] = round(height, 6)
    return payload, ids, worst_residual


def _clip_payloads(arm_obj, action, clip_id, skeleton_id, bone_ids, res):
    """One Blender action as a WKAC binary plus its `core.anim.clip` JSON.

    Uniform-rate sampling, because that is what core takes (D-AC-3): the action
    is evaluated frame by frame over its own range at the scene's fps and the
    resulting local rotations are written to a fixed grid. Curve handles are
    deliberately not preserved; a curve-fitted variant belongs in `x.*`.
    """
    import struct

    scene = bpy.context.scene
    rate = float(scene.render.fps) / float(scene.render.fps_base or 1.0)
    fr = action.frame_range
    start, end = int(round(fr[0])), int(round(fr[1]))
    frames = max(1, end - start + 1)

    arm = arm_obj.data
    ordered = [b for b in arm.bones]
    roots = [b for b in ordered if b.parent is None]
    root_bone_name = roots[0].name if len(roots) == 1 else None
    track_bones = [b for b in ordered if b.name != root_bone_name]

    prev_action = arm_obj.animation_data.action if arm_obj.animation_data else None
    if arm_obj.animation_data is None:
        arm_obj.animation_data_create()
    arm_obj.animation_data.action = action
    old_frame = scene.frame_current

    root_rows = bytearray()
    bone_rows = {b.name: bytearray() for b in track_bones}
    try:
        for f in range(frames):
            scene.frame_set(start + f)
            if root_bone_name:
                pb = arm_obj.pose.bones[root_bone_name]
                m = arm_obj.matrix_world @ pb.matrix
                loc, rot, _s = m.decompose()
                pw = axes.vec_blender_to_werk(loc)
                # The root track carries the root bone's model-space frame, so
                # it converts by LEFT-MULTIPLICATION (bone-local -> model),
                # unlike the per-bone tracks below, which are invariant.
                qw = axes.frame_blender_to_werk((rot.w, rot.x, rot.y, rot.z))
                root_rows += struct.pack("<7f", pw[0], pw[1], pw[2],
                                         qw[0], qw[1], qw[2], qw[3])
            for b in track_bones:
                pb = arm_obj.pose.bones[b.name]
                if b.parent is not None:
                    local = arm_obj.pose.bones[b.parent.name].matrix.inverted() \
                        @ pb.matrix
                else:
                    local = pb.matrix
                q = local.to_quaternion()
                # Local, parent-frame rotations are invariant under the axis
                # swing (axes.py); only the root track above converts.
                q = axes.quat_canonical((q.w, q.x, q.y, q.z))
                bone_rows[b.name] += struct.pack("<4f", q[0], q[1], q[2], q[3])
    finally:
        scene.frame_set(old_frame)
        if arm_obj.animation_data:
            arm_obj.animation_data.action = prev_action

    if not root_bone_name:
        res.add("warn", "clip-no-single-root",
                "%s: the armature has %d root bones, so there is no single "
                "root_bone for the root track; the clip carries a zero root track "
                "and the IN_PLACE flag, which is the honest encoding"
                % (clip_id, len(roots)))
        root_rows = bytearray(struct.pack("<7f", 0, 0, 0, 1, 0, 0, 0) * frames)

    names = [bone_ids.get(b.name, kebab(b.name, "bone")) for b in track_bones]
    rots = bytearray()
    for b in track_bones:
        rots += bone_rows[b.name]

    header = {
        "kind": "core.anim.clip",
        "clip_id": clip_id,
        "skeleton_id": skeleton_id,
        "bone_count": len(track_bones),
        "frame_count": frames,
        "rate_hz": rate,
        "duration_s": frames / rate,
        "flags": 0x1 if not root_bone_name else 0,
        "bones": names,
        "root_bone": bone_ids.get(root_bone_name, "root") if root_bone_name else "root",
        "loop": False,
        "producer": {"tool": TOOL, "version": TOOL_VERSION},
        "epistemic": "authored",
    }
    events = []
    for marker in action.pose_markers:
        kind, _, effect = (marker.name or "marker").partition(":")
        if kind not in ("audio", "footstep", "contact", "effect", "attach",
                        "detach", "marker"):
            kind = "marker"
        ev = {"t_s": max(0.0, (marker.frame - start) / rate), "kind": kind}
        if effect and is_valid_id(effect):
            ev["effect_id"] = effect
        events.append(ev)
    if events:
        header["events"] = sorted(events, key=lambda e: e["t_s"])

    blob = envelope.build(
        b"WKAC", 1, header,
        [("root-track", "f32", [frames, 7], 28, bytes(root_rows)),
         ("bone-rotations", "f32", [len(track_bones), frames, 4], 16, bytes(rots))])

    meta = {
        "schema_version": 1,
        "clip_id": clip_id,
        "name": action.name,
        "skeleton_id": skeleton_id,
        "bone_count": len(track_bones),
        "frame_count": frames,
        "rate_hz": rate,
        "duration_s": frames / rate,
        "flags": {"in_place": not bool(root_bone_name), "additive": False,
                  "root_yaw_only": False},
        "loop": {"loops": False},
        "binary": {"path": "animation/%s.wkac" % clip_id, "magic": "WKAC",
                   "envelope_version": 1},
        "root_bone": header["root_bone"],
        "bones": names,
        "epistemic": "authored",
        "note": "Sampled from Blender action `%s` at %.4f Hz over %d frame(s). "
                "Uniform grid, no curve handles: core takes samples, and a "
                "curve-fitted encoding belongs in x.* (D-AC-3)."
                % (action.name, rate, frames),
    }
    if events:
        meta["events"] = header["events"]
    return blob, meta


# ---------------------------------------------------------------------------
# the export
# ---------------------------------------------------------------------------

def export_file(filepath,
                objects=None,
                collection=None,
                entity_name=None,
                license_text=None,
                include_spec=True,
                include_loader=True,
                export_skeleton=True,
                export_animation=True,
                summary=None):
    """Write the selection (or `objects`, or `collection`) to `filepath`.

    Returns an `ExportResult`. Raises ValueError only when there is nothing
    exportable at all.
    """
    t0 = time.time()
    res = ExportResult()
    res.path = os.path.abspath(filepath)

    objs = _gather(objects, collection)
    meshes = [o for o in objs if o.type == "MESH"]
    armatures = [o for o in objs if o.type == "ARMATURE"]
    if not meshes and not armatures:
        raise ValueError("nothing to export: no mesh or armature in the selection")

    root = _find_root(objs)
    res.reused_identity = root is not None and bool(root.get(PROP_UUID))
    entity_uuid = (root.get(PROP_UUID) if root else None) or str(uuidlib.uuid4())
    res.entity_uuid = entity_uuid
    name = entity_name or (root.get(PROP_NAME) if root else None) \
        or (meshes[0].name if meshes else armatures[0].name)
    created = _now()

    prior_nodes = {}
    if root and root.get(PROP_NODE_IDS):
        try:
            prior_nodes = json.loads(root[PROP_NODE_IDS])
        except (ValueError, TypeError):
            prior_nodes = {}

    blobs = {}
    nodes = []
    node_ids_taken = set()

    def put(path, data):
        if path in blobs and blobs[path] != data:
            raise ValueError("two nodes claim %s with different bytes" % path)
        blobs[path] = data
        return {"path": path, "sha256": sha256_hex(data), "size": len(data)}

    def version(files, note, epistemic, inputs=None, model=None, confidence=None):
        v = {
            "v": 1,
            "files": files,
            "note": note,
            "producer": {"tool": TOOL, "version": TOOL_VERSION,
                         "host": "blender-" + _blender_version()},
            "epistemic": epistemic,
            "created": created,
        }
        if model:
            v["producer"]["model"] = model
        if inputs:
            v["input_files"] = list(inputs)
            v["input_hash"] = input_hash(inputs, blobs)
            # Written out explicitly, as manifest.schema.json says a writer
            # SHOULD, so nobody has to rediscover that absent means `{}` (S-10).
            v["input_params"] = {}
        if confidence is not None:
            v["confidence"] = confidence
        return v

    def add_node(node_id, ntype, ver, edges=(), meta=None, part=None, material=None):
        nid = unique_id(node_id, node_ids_taken, fallback="node")
        n = {"node_id": nid, "type": ntype, "versions": [ver], "active": 1,
             "edges": list(edges)}
        if part:
            n["part_id"] = part
        if material:
            n["material_id"] = material
        if meta:
            n["meta"] = meta
        nodes.append(n)
        return nid

    with Scratch(near=res.path) as scratch:
        # -- LICENSE / README -------------------------------------------
        lic = license_text or (root.get(PROP_LICENSE) if root else None)
        if not lic:
            lic = NO_LICENSE_TEXT
            res.add("warn", "license-unspecified",
                    "no licence text was supplied and the scene carries none; a "
                    "LICENSE file saying exactly that was written, because an "
                    "absent LICENSE reads as licensed-by-omission")
        lic_f = put("LICENSE", lic.encode("utf-8"))
        readme = _readme_text(name, entity_uuid, res.reused_identity)
        readme_f = put("README.txt", readme.encode("utf-8"))

        # -- spec/ and loaders/ ------------------------------------------
        spec_files = []
        if include_spec and os.path.isdir(SPEC_DIR):
            for dirpath, dirnames, filenames in os.walk(SPEC_DIR):
                dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
                for nm in sorted(filenames):
                    if nm.endswith(".pyc"):
                        continue
                    full = os.path.join(dirpath, nm)
                    rel = "spec/" + os.path.relpath(full, SPEC_DIR).replace(os.sep, "/")
                    with open(full, "rb") as fh:
                        spec_files.append(put(rel, fh.read()))
            spec_files.sort(key=lambda f: f["path"])
        elif include_spec:
            res.add("warn", "spec-missing",
                    "the vendored spec/ tree is not beside this add-on, so the "
                    "package carries no core.spec node and its `schemas` map "
                    "points at files that are not in it")

        # -- geometry ----------------------------------------------------
        depsgraph = bpy.context.evaluated_depsgraph_get()
        glb_path = scratch.file("game.glb")
        glb = _export_glb(objs, glb_path, res)
        game_f = put("geometry/game.glb", glb)

        pts, tris = [], []
        for m in meshes:
            base = len(pts)
            p, t = _evaluated_werk_vertices(m, depsgraph)
            pts += p
            tris += [(a + base, b + base, c + base) for a, b, c in t]
        res.vertex_count = len(pts)
        res.triangle_count = len(tris)

        part_id = "entity"
        # `authored`, not `measured`: the schema defines measured as "came out
        # of a simulation, a bake or an instrument and is REPRODUCIBLE FROM ITS
        # INPUTS", and requires an ordered `input_files` naming package paths
        # to prove it. A Blender scene is not a file in this package, so there
        # is nothing to name and nothing to recompute against. A deliberate
        # authoring act is exactly what the `authored` stamp is for. (werk-core
        # caught the first version of this as a schema error, which is law 5
        # being machine-enforced rather than hoped for.)
        mesh_node = add_node(prior_nodes.get("mesh") or "geom-game", "core.geom.game",
                             version([game_f],
                                     "The runtime mesh, written by Blender's bundled "
                                     "glTF exporter with modifiers applied. That "
                                     "exporter performs the Z-up to Y-up swing; "
                                     "everything in this package that does not travel "
                                     "through a GLB is swung by the add-on instead, "
                                     "and the two agree by construction.",
                                     "authored"),
                             part=part_id)

        # -- textures ----------------------------------------------------
        tex_nodes = {"__path__": {}}
        wanted_images = {}
        for m in meshes:
            for slot in m.material_slots:
                mat = slot.material
                if mat is None or not mat.use_nodes or not mat.node_tree:
                    continue
                for nd in mat.node_tree.nodes:
                    if nd.type == "TEX_IMAGE" and nd.image is not None:
                        wanted_images[nd.image.name] = nd.image
        for img_name, img in sorted(wanted_images.items()):
            usage = _image_usage(img)
            tex_id = unique_id("tex-" + kebab(img_name, "image"), set(),
                               fallback="tex")
            fname = "textures/%s.png" % tex_id
            tmp = scratch.file(os.path.basename(fname))
            data = _save_image_png(img, tmp, res)
            if data is None:
                continue
            info = _png_info(data)
            if info is None:
                res.add("warn", "texture-not-png",
                        "%s: Blender did not produce a readable PNG; skipped"
                        % img_name)
                continue
            declared = img.get("werk_color_space")
            cs = declared if declared in ("srgb", "linear") else (
                "srgb" if img.colorspace_settings.name == "sRGB" else "linear")
            f = put(fname, data)
            f["media_type"] = "image/png"
            nid = add_node(tex_id, "core.tex",
                           version([f],
                                   "Texture `%s` packed out of Blender as PNG. Its "
                                   "colour space is declared here rather than "
                                   "inferred: a data map read as sRGB is wrong "
                                   "maths, and that is the failure worth naming."
                                   % img_name,
                                   "authored"),
                           meta={"color_space": cs, "usage": usage,
                                 "width": info["width"], "height": info["height"],
                                 "channels": info["channels"],
                                 "bit_depth": info["bit_depth"]},
                           part=part_id)
            tex_nodes[img_name] = nid
            tex_nodes["__path__"][img_name] = fname

        # -- materials ---------------------------------------------------
        materials_table = []
        mat_ids = set()
        seen_mats = []
        for m in meshes:
            for slot in m.material_slots:
                if slot.material is not None and slot.material not in seen_mats:
                    seen_mats.append(slot.material)
        prior_mat_nodes = prior_nodes.get("materials") or {}
        for mat in seen_mats:
            mid = mat.get(PROP_MATERIAL_ID)
            if not is_valid_id(mid):
                mid = unique_id(mat.name, mat_ids, fallback="material")
            else:
                mat_ids.add(mid)
            payload = _material_payload(mat, mid, tex_nodes, res)
            f = put("materials/%s.json" % mid, jbytes(payload))
            f["media_type"] = "application/json"
            edges = [{"to": mesh_node, "kind": "enhances", "role": "shades"}]
            for slot_name, slot in (payload.get("textures") or {}).items():
                edges.append({"to": slot["node"], "kind": "requires",
                              "role": "samples"})
            add_node(prior_mat_nodes.get(mid) or ("material-" + mid),
                     "core.material",
                     version([f],
                             "PBR parameters for material `%s`, flattened onto the "
                             "metallic-roughness model. What the schema cannot hold "
                             "was left out rather than approximated." % mat.name,
                             "authored"),
                     edges=edges, part=part_id, material=mid)
            materials_table.append({"material_id": mid, "name": mat.name,
                                    "part_id": part_id})

        # -- bounds ------------------------------------------------------
        if pts:
            rec = bounds.bounds_record(pts, tris)
            payload = {
                "schema_version": 1, "space": "model", "entity": rec,
                "epistemic": "measured",
                "note": "Computed from the same evaluated meshes the GLB was "
                        "written from: the AABB over every vertex and the true "
                        "minimal enclosing sphere by Welzl, checked against every "
                        "vertex before the word `welzl-exact` was written.",
            }
            f = put("physics/bounds.json", jbytes(payload))
            f["media_type"] = "application/json"
            add_node(prior_nodes.get("bounds") or "bounds", "core.phys.bounds",
                     version([f],
                             "Measured bounds for culling, placement and LOD "
                             "selection maths, recomputed on every export so a "
                             "stale value cannot survive a round trip.",
                             "measured", inputs=["geometry/game.glb"]),
                     edges=[{"to": mesh_node, "kind": "requires",
                             "role": "bounds-of"}],
                     part=part_id)

        # -- skeleton and animation --------------------------------------
        skeleton_node_id = None
        bone_ids = {}
        skeleton_id = None
        if export_skeleton and armatures:
            arm_obj = armatures[0]
            if len(armatures) > 1:
                res.add("info", "multiple-armatures",
                        "%d armatures in the selection; `%s` was exported and the "
                        "others were not (core profile 1 has one skeleton per "
                        "entity)" % (len(armatures), arm_obj.name))
            skeleton_id = arm_obj.get(PROP_SKELETON_ID) or kebab(arm_obj.name, "rig")
            if not is_valid_id(skeleton_id):
                skeleton_id = kebab(arm_obj.name, "rig")
            payload, bone_ids, _resid = _skeleton_payload(arm_obj, skeleton_id, res)
            f = put("skeleton/%s.json" % skeleton_id, jbytes(payload))
            f["media_type"] = "application/json"
            skeleton_node_id = add_node(
                (prior_nodes.get("skeletons") or {}).get(skeleton_id) or "skeleton",
                "core.skeleton",
                version([f],
                        "Bone hierarchy and rest pose read out of Blender armature "
                        "`%s`, with both the local and the model-space values "
                        "written and the recomposition between them verified before "
                        "writing." % arm_obj.name,
                        "authored"),
                part=part_id)

            if export_animation:
                actions = _actions_for(arm_obj)
                prior_clip_nodes = prior_nodes.get("clips") or {}
                clip_ids = set()
                for action in actions:
                    cid = action.get(PROP_CLIP_ID)
                    if not is_valid_id(cid):
                        cid = unique_id(action.name, clip_ids, fallback="clip")
                    else:
                        clip_ids.add(cid)
                    try:
                        blob, meta = _clip_payloads(arm_obj, action, cid,
                                                    skeleton_id, bone_ids, res)
                    except Exception as e:  # noqa: BLE001
                        res.add("warn", "clip-export-failed",
                                "action `%s`: %s" % (action.name, e))
                        continue
                    bf = put("animation/%s.wkac" % cid, blob)
                    bf["role"] = "binary"
                    jf = put("animation/%s.json" % cid, jbytes(meta))
                    jf["media_type"] = "application/json"
                    jf["role"] = "descriptor"
                    add_node(prior_clip_nodes.get(cid) or ("clip-" + cid),
                             "core.anim.clip",
                             version([bf, jf],
                                     "Blender action `%s` sampled onto a uniform "
                                     "frame grid. The binary is authoritative for "
                                     "anything a player needs; the JSON carries the "
                                     "same facts for tooling." % action.name,
                                     "authored"),
                             edges=[{"to": skeleton_node_id, "kind": "requires",
                                     "role": "animates"}] if skeleton_node_id else [])

        # -- colliders ---------------------------------------------------
        collider_objs = [o for o in objs
                         if o.type == "EMPTY" and o.get("werk_collider")]
        if collider_objs:
            groups = {}
            for e in collider_objs:
                pid = e.get("werk_part_id") or part_id
                g = groups.setdefault(pid, {"part_id": pid, "spheres": [], "boxes": []})
                centre = axes.vec_blender_to_werk(e.matrix_world.translation)
                if e["werk_collider"] == "sphere":
                    g["spheres"].append({
                        "center": [round(float(c), 7) for c in centre],
                        "radius": round(float(e.get("werk_radius",
                                                    e.empty_display_size)), 7)})
                else:
                    q = e.matrix_world.to_quaternion()
                    half = e.get("werk_half_extents") or [abs(v) for v in e.scale]
                    g["boxes"].append({
                        "center": [round(float(c), 7) for c in centre],
                        "half_extents": [round(max(1e-6, float(c)), 7) for c in half],
                        "rotation": [round(float(c), 9) for c in
                                     axes.quat_blender_to_werk((q.w, q.x, q.y, q.z))]})
            payload = {"schema_version": 1, "space": "part-local",
                       "groups": list(groups.values()), "epistemic": "authored",
                       "note": "Analytic collision volumes carried as Blender empties; "
                               "half-extents, not full extents, and a quaternion, "
                               "not a matrix."}
            f = put("physics/colliders.json", jbytes(payload))
            f["media_type"] = "application/json"
            add_node((prior_nodes.get("colliders") or ["colliders"])[0],
                     "core.phys.colliders",
                     version([f], "Analytic sphere and box colliders for this entity.",
                             "authored"),
                     edges=[{"to": mesh_node, "kind": "enhances",
                             "role": "collides-for"}],
                     part=part_id)

        # -- semantics ---------------------------------------------------
        sem_payload = None
        if root and root.get(PROP_SEMANTICS):
            try:
                sem_payload = json.loads(root[PROP_SEMANTICS])
            except (ValueError, TypeError):
                sem_payload = None
        if sem_payload is None:
            tags = _tags_from_custom_props(root, objs)
            if tags:
                sem_payload = {
                    "schema_version": 1, "facets_version": 1, "facets": tags,
                    "note": "Facet tags read from Blender custom properties on the "
                            "exported objects. Stamped `authored` because a person "
                            "typed them; nothing here was inferred.",
                }
        if sem_payload is not None:
            f = put("semantics/semantics.json", jbytes(sem_payload))
            f["media_type"] = "application/json"
            add_node(prior_nodes.get("semantics") or "semantics", "core.semantics",
                     version([f],
                             "Facet tags, palette and search text. This node alone "
                             "renders a browser listing (law 9), which is why it "
                             "sits inside the preview prefix.",
                             "authored"))

        # -- spec, loader, licence, readme -------------------------------
        if spec_files:
            add_node("spec", "core.spec",
                     version(spec_files,
                             "The format specification, its schemas and its binary "
                             "layout grammars, travelling inside the file they "
                             "describe (law 2). This is the copy the manifest's "
                             "`schemas` map points at.",
                             "authored"))
        if include_loader and os.path.isfile(LOADER_SRC):
            with open(LOADER_SRC, "rb") as fh:
                loader_bytes = fh.read()
            f = put("loaders/werk_read.py", loader_bytes)
            f["media_type"] = "text/x-python"
            # What the loader does is stated by the loader, in one line, and
            # read from the bytes being embedded -- not typed here a ninth
            # time (finding F-AC-4; tools/loader_caps.py is the same rule).
            mark = b"WERK-LOADER-CAPABILITIES:"
            at = loader_bytes.find(mark)
            loader_caps = ([c.decode("ascii") for c in
                            loader_bytes[at + len(mark):].split(b"\n", 1)[0].split()]
                           if at >= 0 else
                           ["read-manifest", "verify-hashes", "read-envelope",
                            "materialize"])
            add_node("loader-python", "core.loader",
                     version([f],
                             "A single-file, dependency-free reader for this "
                             "package, carried as payload so the file brings its own "
                             "reader (law 1).",
                             "authored"),
                     meta={"language": "python", "form": "source",
                           "entrypoint": "loaders/werk_read.py",
                           "toolchain": "python>=3.8", "dependencies": [],
                           "capabilities": loader_caps})
        add_node("license", "core.license",
                 version([lic_f],
                         "The full licence text, embedded, never a link (law 7).",
                         "authored"))
        add_node("readme", "core.readme",
                 version([readme_f],
                         "One page for a human who opened this file and wants to "
                         "know what it is.",
                         "authored"))

        # -- parts, primary, manifest, container -------------------------
        parts = _parts_table(root, part_id, name)
        primary = {"mesh": mesh_node}
        prior_primary = {}
        if root and root.get(PROP_PRIMARY):
            try:
                prior_primary = json.loads(root[PROP_PRIMARY])
            except (ValueError, TypeError):
                prior_primary = {}
        prior_materials = []
        if root and root.get(PROP_MATERIALS):
            try:
                prior_materials = json.loads(root[PROP_MATERIALS])
            except (ValueError, TypeError):
                prior_materials = []
        if not materials_table and prior_materials:
            materials_table = [
                {k: v for k, v in m.items() if k in
                 ("material_id", "part_id", "name", "class")}
                for m in prior_materials]

        manifest_bytes, entries = _assemble(
            blobs, nodes, parts, materials_table, primary, lic_f,
            entity_uuid, name, created,
            summary or (root.get("werk_entity_summary") if root else None), res)

    blob = wzip.write_zip(entries)
    os.makedirs(os.path.dirname(res.path) or ".", exist_ok=True)
    with open(res.path, "wb") as fh:
        fh.write(blob)

    res.bytes = len(blob)
    res.sha256 = sha256_hex(blob)
    res.entries = len(entries)
    res.nodes = len(nodes)
    res.files = sum(len(v["files"]) for n in nodes for v in n["versions"])
    res.manifest_bytes = len(manifest_bytes)
    res.preview_prefix_bytes = json.loads(
        manifest_bytes.decode("utf-8"))["container"]["preview_prefix_bytes"]
    res.seconds = time.time() - t0
    return res


def _actions_for(arm_obj):
    """Actions that plausibly belong to this armature: the one assigned, plus
    every NLA strip's. An action from another rig would export as a clip full
    of unbound bone names, so guessing widely is worse than guessing narrowly."""
    out = []
    ad = arm_obj.animation_data
    if ad is None:
        return out
    if ad.action is not None:
        out.append(ad.action)
    for track in ad.nla_tracks:
        for strip in track.strips:
            if strip.action is not None and strip.action not in out:
                out.append(strip.action)
    return out


def _tags_from_custom_props(root, objs):
    """`werk_tag_list` or `werk_facet_<facet>` custom properties -> facets."""
    facets = {}
    sources = ([root] if root else []) + list(objs)
    for o in sources:
        for key in o.keys():
            if not key.startswith("werk_facet_"):
                continue
            facet = key[len("werk_facet_"):].replace("_", "-")
            vals = o[key]
            if isinstance(vals, str):
                vals = [v.strip() for v in vals.split(",") if v.strip()]
            facets.setdefault(facet, [])
            for v in vals:
                if v not in facets[facet]:
                    facets[facet].append(v)
    if root and root.get("werk_tag_list") and not facets:
        for item in str(root["werk_tag_list"]).split(","):
            item = item.strip()
            if "/" in item:
                facet, _, tag = item.partition("/")
                facets.setdefault(facet.strip(), []).append(tag.strip())
    return facets


def _parts_table(root, part_id, name):
    if root and root.get(PROP_PARTS):
        try:
            parts = json.loads(root[PROP_PARTS])
            if isinstance(parts, list) and parts:
                return parts
        except (ValueError, TypeError):
            pass
    return [{"part_id": part_id, "name": name, "parent": None,
             "transform": {"translation": [0.0, 0.0, 0.0],
                           "rotation": [1.0, 0.0, 0.0, 0.0],
                           "scale": [1.0, 1.0, 1.0]}}]


_SCHEMA_FOR = {
    "core.material": "spec/schemas/core.material.schema.json",
    "core.phys.bounds": "spec/schemas/core.phys.bounds.schema.json",
    "core.phys.colliders": "spec/schemas/core.phys.colliders.schema.json",
    "core.semantics": "spec/schemas/core.semantics.schema.json",
    "core.skeleton": "spec/schemas/core.skeleton.schema.json",
    "core.anim.clip": "spec/schemas/core.anim.clip.schema.json",
}
_LAYOUT_FOR = {"core.anim.clip": "spec/layouts/animclip.layout.txt"}


def _refuse_dangling_edges(nodes):
    """SPEC section 5: a writer MUST NOT emit an edge, `requires` or
    `enhances`, to a node that is not in nodes[]. Same rule as
    tools/edge_targets.py and werk::manifest::refuse_dangling_edges."""
    ids = {n.get("node_id") for n in nodes}
    bad = ["`%s` %s `%s`" % (n.get("node_id"), e.get("kind"), e.get("to"))
           for n in nodes for e in (n.get("edges") or []) if e.get("to") not in ids]
    if bad:
        raise ValueError("refusing to write a package with an edge to a node that "
                         "is not in nodes[] (SPEC section 5): " + ", ".join(bad))


def _build_manifest(blobs, nodes, parts, materials, primary, lic_f,
                    entity_uuid, name, created, summary, preview_prefix):
    _refuse_dangling_edges(nodes)
    present = {n["type"] for n in nodes}
    # S10-1, ruled 2026-08-08: `schemas` maps only the node types actually
    # present that HAVE a schema, and an EMPTY MAP IS CONFORMANT. This used to
    # name the material schema for a package that had no JSON payload node at
    # all, purely to satisfy minProperties:1 - i.e. it declared a schema the
    # package did not use, to get past a validator. That workaround is gone
    # with the rule that caused it: a mesh-only export now says {} and means it.
    schemas = {t: p for t, p in _SCHEMA_FOR.items() if t in present}
    layouts = {t: p for t, p in _LAYOUT_FOR.items() if t in present}
    return {
        "werk": {"major": 1, "minor": 0},
        "profile": "3d-entity/1",
        "entity": {
            "uuid": entity_uuid,
            "name": name,
            "summary": summary or (
                "Exported from Blender %s by %s %s. Geometry, materials and "
                "textures come from the scene; the bounds are measured from the "
                "same evaluated meshes the GLB was written from. Unsigned: SPEC "
                "section 6 makes `absent` a legitimate, visible state, and an "
                "exporter that minted a key so the file looked signed would "
                "defeat the doctrine it implements."
                % (_blender_version(), TOOL, TOOL_VERSION)),
            "created": created,
        },
        "conventions": {
            "endianness": "le", "units_per_meter": 1.0, "length_unit": "metre",
            "angle_unit": "radian", "time_unit": "second", "mass_unit": "kilogram",
            "up_axis": "y", "forward_axis": "-z", "right_axis": "+x",
            "handedness": "right", "winding": "ccw", "quat_order": "wxyz",
            "oct_encoding_pole": "y", "sh_l1_order": ["dc", "y", "z", "x"],
            "color_space_default": "srgb", "uv_origin": "top-left",
            "alignment_bytes": 16, "text_encoding": "utf-8", "id_case": "kebab-case",
            "hash_algorithm": "sha256", "signature_algorithm": "ed25519",
        },
        "container": {
            "form": "zip", "zip_compression": "store",
            "entry_order": list(wzip.ENTRY_ORDER),
            "preview_prefix_bytes": preview_prefix,
        },
        "primary": primary,
        "license": {"file": "LICENSE", "sha256": lic_f["sha256"]},
        "spec_sha256": spec_sha256_of(blobs),
        "conventions_map": CONVENTIONS_MAP,
        "schemas": schemas,
        "layouts": layouts,
        "parts": parts,
        "materials": materials,
        "nodes": nodes,
        "generator": {"tool": TOOL, "version": TOOL_VERSION},
    }


def _assemble(blobs, nodes, parts, materials, primary, lic_f, entity_uuid, name,
              created, summary, res):
    """Iterate `preview_prefix_bytes` to a fixed point.

    The prefix length depends on the manifest's own size and the manifest
    declares the prefix length, so the value is iterated rather than guessed —
    the same fixed point `fixtures/build_golden.py` solves, and for the same
    reason. Bounded, so a pathological input fails loudly.
    """
    preview = 0
    for _round in range(8):
        manifest_bytes = jbytes(_build_manifest(
            blobs, nodes, parts, materials, primary, lic_f, entity_uuid, name,
            created, summary, preview))
        allf = dict(blobs)
        allf["MANIFEST.json"] = manifest_bytes
        order = wzip.order_entries(allf.keys())
        entries = [(p, allf[p]) for p in order]
        prefix = wzip.preview_prefix_bytes(entries)
        if prefix == preview:
            return manifest_bytes, entries
        preview = prefix
    raise ValueError("preview_prefix_bytes did not converge")


def _readme_text(name, entity_uuid, reused):
    return (
        "%s\n%s\n"
        "\n"
        "A werk 3D entity written out of Blender by %s %s.\n"
        "\n"
        "Everything needed to read this file is inside it: spec/ carries the\n"
        "format specification, its JSON Schemas and its binary layout grammars,\n"
        "and loaders/werk_read.py is a single-file, dependency-free reader that\n"
        "needs nothing but a Python interpreter. Start with spec/README.md, or\n"
        "just run loaders/werk_read.py against this file.\n"
        "\n"
        "entity uuid: %s\n"
        "%s\n"
        "\n"
        "This package is UNSIGNED, and that is a state rather than a defect:\n"
        "SPEC section 6 requires a tool to distinguish `absent` from\n"
        "`present-and-invalid`, and an exporter that minted a key so the file\n"
        "looked signed would have defeated the doctrine it implements.\n"
        % (name, "=" * len(name), TOOL, TOOL_VERSION, entity_uuid,
           "Identity was carried forward from the .werk this scene was imported\n"
           "from, so this file is a new version of the SAME entity (law 4)."
           if reused else
           "This uuid was minted at export: the scene had no werk ancestry, so\n"
           "this is a new entity rather than a new version of an existing one.")
    )
