"""werk -> Blender.

Graceful degradation is the whole design (manifesto law 3, SPEC section 10.1):
a node that cannot be read is SKIPPED, named in the report, and costs exactly
itself. The importer never raises for damage. It raises only for a
container-scoped refusal — not a zip, no EOCD, no readable MANIFEST.json —
because that is the one scope the spec allows to come back empty-handed.

Every skip lands in two places, deliberately: the Blender operator report
(which a human sees once) and a `werk_import_report.txt` text datablock (which
survives being saved into the .blend and can be read months later). A report
only a live operator can see is not a record.
"""

import json
import os
import time

import bpy  # noqa: F401  - the add-on only ever runs inside Blender
import mathutils

from . import axes
from .common import Scratch
from .vendor import werk_read

#: Custom properties stamped on the imported root empty. Named here so the
#: exporter reads exactly what the importer wrote and a drift is one edit.
PROP_UUID = "werk_entity_uuid"
PROP_NAME = "werk_entity_name"
PROP_SOURCE = "werk_source"
PROP_MANIFEST_SHA = "werk_manifest_sha256"
PROP_PROFILE = "werk_profile"
PROP_NODE_IDS = "werk_node_ids"
PROP_SEMANTICS = "werk_semantics"
PROP_LICENSE = "werk_license"
PROP_PARTS = "werk_parts"
PROP_MATERIALS = "werk_materials"
PROP_PRIMARY = "werk_primary"
PROP_TAGS = "werk_tags"
PROP_MATERIAL_ID = "werk_material_id"
PROP_TEX_NODE = "werk_tex_node"
PROP_SKELETON_ID = "werk_skeleton_id"
PROP_CLIP_ID = "werk_clip_id"
PROP_PART_ID = "werk_part_id"

REPORT_TEXT = "werk_import_report.txt"
NOTES_TEXT = "werk_work_notes.txt"

_LOD_TYPES = ("core.geom.lod",)


class Result(object):
    """What an import produced, in numbers a gate can assert on."""

    def __init__(self):
        self.root = None
        self.objects = []
        self.meshes = []
        self.materials = []
        self.images = []
        self.armatures = []
        self.actions = []
        self.sounds = []
        self.collider_empties = []
        self.lod_collections = {}
        self.report = []            # (severity, code, message)
        self.package_report = []    # the vendored reader's own entries
        self.nodes_total = 0
        self.nodes_alive = 0
        self.nodes_dead = 0
        self.nodes_skipped_unknown = 0
        self.nodes_not_implemented = []
        self.signature = "absent"
        #: Ed25519 checked by the vendored werk release library; `signature`
        #: above is the bootstrap reader's word, which never verifies.
        self.signature_verified = "unknown"
        self.library_verdict = None
        self.entity_uuid = None
        self.vertex_count = 0
        self.triangle_count = 0
        self.seconds = 0.0
        self.scratch_fell_back = False

    def add(self, severity, code, message):
        self.report.append((severity, code, message))

    def errors(self):
        return sum(1 for s, _, _ in self.report if s == "error")

    def unexpected_skips(self):
        """Skips that are NOT the two legitimate kinds: an `x.*` node this
        reader was never meant to know (law 12), and a `core.*` family this
        add-on has honestly not implemented. Anything else is a real skip and
        the gate counts it."""
        out = []
        for sev, code, msg in self.report:
            if code in ("node-skipped-unknown-type", "node-type-not-implemented"):
                continue
            if sev == "error":
                out.append((code, msg))
        return out

    def as_text(self):
        lines = [
            "werk import report",
            "==================",
            "",
            "source        : %s" % self.source_path,
            "entity        : %s" % (self.entity_name or "?"),
            "entity uuid   : %s" % (self.entity_uuid or "?"),
            "signature     : %s (bootstrap reader); %s (werk library, Ed25519 checked)"
            % (self.signature, self.signature_verified),
            "elapsed       : %.3f s" % self.seconds,
            "",
            "nodes         : %d total, %d alive, %d dead, %d skipped (unknown type)"
            % (self.nodes_total, self.nodes_alive, self.nodes_dead,
               self.nodes_skipped_unknown),
            "created       : %d object(s), %d mesh(es), %d material(s), %d image(s), "
            "%d armature(s), %d action(s), %d sound(s)"
            % (len(self.objects), len(self.meshes), len(self.materials),
               len(self.images), len(self.armatures), len(self.actions),
               len(self.sounds)),
            "geometry      : %d vertices, %d triangles (primary mesh)"
            % (self.vertex_count, self.triangle_count),
            "",
            "PACKAGE REPORT (from the bundled zero-dependency reader)",
            "--------------------------------------------------------",
        ]
        if not self.package_report:
            lines.append("(none)")
        for sev, code, msg in self.package_report:
            lines.append("[%s] %s: %s" % (sev, code, msg))
        lines += ["", "IMPORT REPORT", "-------------"]
        if not self.report:
            lines.append("(none)")
        for sev, code, msg in self.report:
            lines.append("[%s] %s: %s" % (sev, code, msg))
        lines += ["",
                  "Exit-status equivalent (SPEC section 10.1): %d"
                  % (1 if self.errors() else 0)]
        return "\n".join(lines) + "\n"

    source_path = ""
    entity_name = ""


# ---------------------------------------------------------------------------
# helpers over the vendored reader's node dicts
# ---------------------------------------------------------------------------

def resolved_version(node):
    if node.get("resolved") is None:
        return None
    for v in node["versions"]:
        if v.get("v") == node["resolved"]:
            return v
    return None


def node_files(node):
    ver = resolved_version(node)
    return list(ver.get("files", [])) if ver else []


def first_file(node, role=None, suffix=None):
    for f in node_files(node):
        if role and f.get("role") != role:
            continue
        if suffix and not f["path"].endswith(suffix):
            continue
        return f
    return None


def nodes_of_type(pkg, *types):
    return [n for n in pkg.nodes if n["type"] in types and n["status"] != "dead"]


def node_meta(pkg, node):
    """A node's `meta` block, from the MANIFEST rather than from the reader.

    `werk_read.Package` builds its own node dicts and does not copy `meta`
    across — it has no use for it. Reaching for `node["meta"]` therefore
    silently returns nothing, which is how every `core.tex` in an imported
    package ended up as Non-Color regardless of what its manifest declared:
    the mandatory `color_space` was read off a dict that never had it, and the
    fallback branch is deliberately the safe direction, so nothing looked
    wrong. Measured by the texture gate clause; this function is the fix.

    `meta` is where the manifest keeps what a reader needs BEFORE opening the
    payload — colour space, LOD selection metrics, loader capabilities — so
    losing it loses exactly the things that cannot be recovered from the bytes.
    """
    for raw in pkg.manifest.get("nodes", []):
        if raw.get("node_id") == node["node_id"]:
            return raw.get("meta") or {}
    return {}


def find_node(pkg, node_id):
    for n in pkg.nodes:
        if n["node_id"] == node_id:
            return n
    return None


def _json_payload(pkg, node, res, suffix=".json"):
    f = first_file(node, suffix=suffix)
    if f is None:
        res.add("warn", "payload-missing",
                "%s: no %s payload in its resolved version" % (node["node_id"], suffix))
        return None
    try:
        return json.loads(pkg.blob(f["path"]).decode("utf-8"))
    except Exception as e:  # noqa: BLE001 - a bad payload is node-scoped, not fatal
        res.add("error", "payload-invalid",
                "%s: %s is not readable JSON (%s)" % (node["node_id"], f["path"], e))
        return None


# ---------------------------------------------------------------------------
# the import
# ---------------------------------------------------------------------------

def import_file(filepath,
                import_lods=False,
                import_source=False,
                import_colliders=True,
                import_points=True,
                rigid_body_colliders=False,
                import_skeleton=True,
                import_animation=True,
                import_audio_preview=False,
                write_report_text=True,
                collection=None):
    """Import a .werk (or its directory form) into the current scene.

    Returns a `Result`. Raises RuntimeError only on a container-scoped
    refusal; every other problem is a report entry and a skipped node.
    """
    t0 = time.time()
    res = Result()
    res.source_path = os.path.abspath(filepath)

    # The werk release library reads the package first: it verifies the
    # signature chain, and it tells an image/1 package from a 3D one.
    from .libwerk import verdict_of
    res.library_verdict, _why = verdict_of(res.source_path)
    if res.library_verdict is not None:
        res.signature_verified = res.library_verdict.get("signature", "unknown")
        if res.library_verdict.get("profile") == "image/1":
            from .image_io import import_image_file
            return import_image_file(filepath, write_report_text=write_report_text)

    try:
        pkg = werk_read.Package(res.source_path)
    except SystemExit as e:
        # The vendored reader is a CLI at heart and exits on a container-scoped
        # refusal. Inside Blender that would take the whole process with it.
        raise RuntimeError("werk: %s" % e)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError("werk: cannot open %s: %s" % (res.source_path, e))

    res.package_report = list(pkg.report.lines)
    res.signature = pkg.signature
    manifest = pkg.manifest
    entity = manifest.get("entity", {})
    res.entity_uuid = entity.get("uuid")
    res.entity_name = entity.get("name") or os.path.basename(res.source_path)

    res.nodes_total = len(pkg.nodes)
    res.nodes_alive = sum(1 for n in pkg.nodes if n["status"] == "ok")
    res.nodes_dead = sum(1 for n in pkg.nodes if n["status"] == "dead")
    res.nodes_skipped_unknown = sum(1 for n in pkg.nodes if n["status"] == "skipped")
    for n in pkg.nodes:
        if n["status"] == "skipped":
            res.add("info", "node-skipped-unknown-type",
                    "%s: type `%s` is outside this reader's vocabulary; its bytes "
                    "were verified and it is extractable (law 12)"
                    % (n["node_id"], n["type"]))
        elif n["status"] == "dead":
            res.add("error", "node-dead",
                    "%s: %s" % (n["node_id"], n.get("reason") or "unusable"))

    target = collection or bpy.context.scene.collection

    root = bpy.data.objects.new("werk:" + res.entity_name, None)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 0.25
    target.objects.link(root)
    res.root = root
    res.objects.append(root)

    node_ids = {}

    with Scratch(near=res.source_path) as scratch:
        res.scratch_fell_back = scratch.fell_back
        if scratch.fell_back:
            res.add("info", "scratch-fallback",
                    "could not write beside the package; used the system temp "
                    "directory for the intermediate GLB/PNG files instead")

        _import_geometry(pkg, res, scratch, target, root, node_ids,
                         import_lods, import_source)
        if import_points:
            _import_points(pkg, res, target, root, node_ids)
        _import_textures_and_materials(pkg, res, scratch, node_ids)
        if import_colliders:
            _import_colliders(pkg, res, target, root, node_ids,
                              rigid_body_colliders)
        if import_skeleton:
            _import_skeletons(pkg, res, target, root, node_ids)
        if import_animation:
            _import_animation(pkg, res, node_ids)
        _import_audio(pkg, res, scratch, node_ids, import_audio_preview)

    _stamp_identity(pkg, res, root, node_ids)
    _note_unimplemented(pkg, res)

    res.seconds = time.time() - t0
    if write_report_text:
        _write_text(REPORT_TEXT, res.as_text())
        _write_text(NOTES_TEXT, _work_notes_text(pkg))
    return res


# --- point clouds and Gaussian splats (Stage 12) ---------------------------

def _points_from_wkpc(blob):
    """(positions, colours_or_None) out of a WKPC payload, decoded from the
    offsets its own header declares. `werk_read` is the vendored bootstrap
    loader, so this add-on and the reference loader read the payload through
    exactly one implementation."""
    magic, _version, header = werk_read.read_envelope(blob)
    if magic != b"WKPC":
        raise ValueError("not a WKPC payload")
    secs = {s["name"]: s for s in header.get("sections", [])}
    fields = {f["name"]: f for f in header.get("fields", [])}
    pos_name = None
    for f in header.get("fields", []):
        if f.get("semantic") == "position":
            pos_name = f["section"]
            break
    if pos_name is None or pos_name not in secs:
        raise ValueError("WKPC has no position section")
    pos = werk_read.read_section(blob, secs[pos_name])
    col = None
    for f in header.get("fields", []):
        if f.get("semantic") == "color" and f["section"] in secs:
            sec = secs[f["section"]]
            raw = werk_read.read_section(blob, sec)
            scale = 255.0 if sec["dtype"] in ("u8", "i8") else 1.0
            col = [[min(1.0, max(0.0, c / scale)) for c in (r if isinstance(r, list) else [r])]
                   for r in raw]
            # points.layout.txt section 5: u8 colour maps 0..255 onto 0..1, and
            # `color_space` says whether those are linear or sRGB-encoded.
            # Blender's colour attributes are LINEAR, so an sRGB field is
            # linearised here rather than being handed over gamma-wrong.
            if f.get("color_space") == "srgb":
                col = [[_srgb_to_linear(c) for c in row] for row in col]
            break
    return pos, col, header


def _points_from_wkgs(blob):
    """The normative degradation of spec/layouts/gsplat.layout.txt section 7,
    performed by an adapter that does not implement Gaussian splatting: read
    `means` and `sh-dc`, skip the other four sections without parsing them."""
    magic, _version, header = werk_read.read_envelope(blob)
    if magic != b"WKGS":
        raise ValueError("not a WKGS payload")
    secs = {s["name"]: s for s in header.get("sections", [])}
    if "means" not in secs or "sh-dc" not in secs:
        raise ValueError("WKGS is missing `means` or `sh-dc`")
    pos = werk_read.read_section(blob, secs["means"])
    dc = werk_read.read_section(blob, secs["sh-dc"])
    c0 = werk_read.SH_C0
    col = [[min(1.0, max(0.0, 0.5 + c0 * c)) for c in row] for row in dc]
    return pos, col, header


def _srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _make_point_cloud(name, positions, colours, target, root):
    """A Blender MESH with vertices and no edges or faces. Blender has a real
    point-cloud datablock, and it is still largely inaccessible from Python in
    4.2 LTS; a vertices-only mesh is what every point-cloud importer in
    practice produces, it renders, it can be instanced on, and it survives a
    save. Recorded as decision D-BL-1."""
    me = bpy.data.meshes.new(name)
    n = len(positions)
    me.vertices.add(n)
    flat = []
    for p in positions:
        b = axes.vec_werk_to_blender(p)
        flat.extend((b[0], b[1], b[2]))
    me.vertices.foreach_set("co", flat)
    if colours and hasattr(me, "color_attributes"):
        try:
            attr = me.color_attributes.new(name="werk_color", type="FLOAT_COLOR",
                                           domain="POINT")
            cflat = []
            for c in colours:
                r = c[0] if len(c) > 0 else 0.0
                g = c[1] if len(c) > 1 else r
                b = c[2] if len(c) > 2 else r
                a = c[3] if len(c) > 3 else 1.0
                cflat.extend((r, g, b, a))
            attr.data.foreach_set("color", cflat)
        except Exception:  # noqa: BLE001
            pass
    me.update()
    ob = bpy.data.objects.new(name, me)
    target.objects.link(ob)
    ob.parent = root
    return ob


def _import_points(pkg, res, target, root, node_ids):
    """Import every `core.geom.points`, and every `core.geom.gsplat` that no
    points node was derived from.

    The second half of that rule is the interesting one. A conformant splat
    package SHOULD carry both the splat and its DC-band point cloud
    (gsplat.layout.txt section 7), and importing both would put two identical
    million-vertex clouds in the scene. So the derived node wins where it
    exists — it is the producer's own materialisation and carries its
    `input_hash` — and the splat is degraded in-place only when nothing else
    did it. Either way the scene gets exactly one cloud per splat, and the
    report says which path produced it.
    """
    derived_from = set()
    point_nodes = nodes_of_type(pkg, "core.geom.points")
    for n in point_nodes:
        ver = resolved_version(n) or {}
        for src in ver.get("input_files", []) or []:
            derived_from.add(src)

    for n in point_nodes:
        f = first_file(n, suffix=".wkpc")
        if f is None:
            res.add("warn", "points-no-payload",
                    "%s: no .wkpc file in the resolved version" % n["node_id"])
            continue
        try:
            pos, col, header = _points_from_wkpc(pkg.blob(f["path"]))
        except Exception as e:  # noqa: BLE001
            res.add("error", "points-unreadable",
                    "%s: %s" % (n["node_id"], e))
            continue
        ob = _make_point_cloud("werk:points:" + n["node_id"], pos, col, target, root)
        node_ids[n["node_id"]] = ob.name
        res.objects.append(ob)
        res.add("info", "points-imported",
                "%s: %d points as mesh vertices%s"
                % (n["node_id"], len(pos), ", with a werk_color attribute"
                   if col else ""))

    for n in nodes_of_type(pkg, "core.geom.gsplat"):
        f = first_file(n, suffix=".wkgs")
        if f is None:
            continue
        if f["path"] in derived_from:
            res.add("info", "gsplat-degradation-skipped",
                    "%s: a core.geom.points node is already derived from this "
                    "splat, so the DC band was not degraded a second time"
                    % n["node_id"])
            continue
        try:
            pos, col, header = _points_from_wkgs(pkg.blob(f["path"]))
        except Exception as e:  # noqa: BLE001
            res.add("error", "gsplat-unreadable", "%s: %s" % (n["node_id"], e))
            continue
        ob = _make_point_cloud("werk:gsplat:" + n["node_id"], pos, col, target, root)
        node_ids[n["node_id"]] = ob.name
        res.objects.append(ob)
        res.add("info", "gsplat-degraded-to-points",
                "%s: %d Gaussians read as a point cloud from `means` and "
                "`sh-dc` alone; the other four sections were skipped without "
                "being parsed, which gsplat.layout.txt section 7 makes a "
                "conformant way to consume the node rather than a degraded one"
                % (n["node_id"], len(pos)))


# --- geometry --------------------------------------------------------------

def _new_objects(before):
    return [o for o in bpy.data.objects if o.name not in before]


def _import_glb(pkg, res, scratch, path, label):
    """Extract one GLB and hand it to Blender's bundled glTF importer.

    That importer is what performs the Y-up -> Z-up swing for positions,
    normals, tangents and node transforms. Everything the GLB does NOT carry —
    bounds, colliders, skeleton rest values, clip tracks — is swung by
    `axes.py` instead, and the two must agree; `axes.selftest()` is the check
    that they do.
    """
    try:
        data = pkg.blob(path)
    except Exception as e:  # noqa: BLE001
        res.add("error", "payload-unreadable", "%s: %s (%s)" % (label, path, e))
        return []
    tmp = scratch.file(os.path.basename(path) or "mesh.glb")
    with open(tmp, "wb") as fh:
        fh.write(data)
    before = {o.name for o in bpy.data.objects}
    try:
        bpy.ops.import_scene.gltf(filepath=tmp)
    except Exception as e:  # noqa: BLE001 - one bad GLB kills one node, not the load
        res.add("error", "gltf-import-failed", "%s: %s" % (label, e))
        return []
    return _new_objects(before)


def _reparent(objects, root, target, collection=None):
    """Parent the roots of an imported subtree to the werk root empty, keeping
    the world transform Blender's glTF importer produced."""
    out = []
    for obj in objects:
        if obj.parent is None:
            obj.parent = root
            obj.matrix_parent_inverse = root.matrix_world.inverted()
        if collection is not None:
            for c in list(obj.users_collection):
                c.objects.unlink(obj)
            collection.objects.link(obj)
        out.append(obj)
    return out


def _import_geometry(pkg, res, scratch, target, root, node_ids,
                     import_lods, import_source):
    primary = (pkg.manifest.get("primary") or {}).get("mesh")
    mesh_node = find_node(pkg, primary) if primary else None
    if primary and mesh_node is None:
        res.add("warn", "primary-dangling",
                "manifest primary.mesh names `%s`, which is not a node here" % primary)
    if mesh_node is None:
        candidates = nodes_of_type(pkg, "core.geom.game")
        if candidates:
            mesh_node = candidates[0]
            res.add("info", "primary-fallback",
                    "no usable primary.mesh; FELL BACK to the core.geom.game node "
                    "`%s` per SPEC section 2, and this line is the report that "
                    "fallback requires" % mesh_node["node_id"])
    if mesh_node is None:
        res.add("warn", "no-geometry",
                "this package declares no usable game mesh; everything else was "
                "still imported (law 3)")
    else:
        f = first_file(mesh_node, suffix=".glb")
        if f is None:
            res.add("error", "payload-missing",
                    "%s: no .glb in its resolved version" % mesh_node["node_id"])
        else:
            objs = _import_glb(pkg, res, scratch, f["path"], mesh_node["node_id"])
            objs = _reparent(objs, root, target)
            res.objects += objs
            node_ids["mesh"] = mesh_node["node_id"]
            for o in objs:
                o[PROP_PART_ID] = mesh_node.get("part_id") or ""
                if o.type == "MESH" and o.data not in res.meshes:
                    res.meshes.append(o.data)
                    res.vertex_count += len(o.data.vertices)
                    res.triangle_count += len(o.data.loop_triangles) or sum(
                        max(0, len(p.vertices) - 2) for p in o.data.polygons)

    if import_source:
        for n in nodes_of_type(pkg, "core.geom.source"):
            f = first_file(n, suffix=".glb")
            if f is None:
                continue
            coll = bpy.data.collections.new("werk-source-hi")
            target.children.link(coll)
            objs = _reparent(_import_glb(pkg, res, scratch, f["path"], n["node_id"]),
                             root, target, coll)
            res.objects += objs
            node_ids["source"] = n["node_id"]

    if import_lods:
        for n in sorted(nodes_of_type(pkg, *_LOD_TYPES),
                        key=lambda x: node_meta(pkg, x).get("lod_level", 99)):
            level = node_meta(pkg, n).get("lod_level")
            f = first_file(n, suffix=".glb")
            if f is None or level is None:
                res.add("warn", "lod-incomplete",
                        "%s: a core.geom.lod needs meta.lod_level and a .glb"
                        % n["node_id"])
                continue
            name = "lod%d" % level
            coll = bpy.data.collections.get(name) or bpy.data.collections.new(name)
            if coll.name not in {c.name for c in target.children}:
                target.children.link(coll)
            objs = _reparent(_import_glb(pkg, res, scratch, f["path"], n["node_id"]),
                             root, target, coll)
            res.objects += objs
            res.lod_collections[level] = coll
            node_ids.setdefault("lods", {})[str(level)] = n["node_id"]


# --- textures and materials ------------------------------------------------

_SLOT_TO_INPUT = {
    "base_color": "Base Color",
    "metallic_roughness": None,     # packed; wired to Metallic + Roughness below
    "normal": "Normal",
    "occlusion": None,              # Principled has no AO input; kept as a node
    "emissive": "Emission Color",
    "height": None,
}


def _import_textures_and_materials(pkg, res, scratch, node_ids):
    images = {}
    for n in nodes_of_type(pkg, "core.tex"):
        meta = node_meta(pkg, n)
        f = first_file(n, suffix=".png") or first_file(n)
        if f is None:
            res.add("warn", "payload-missing", "%s: no image payload" % n["node_id"])
            continue
        try:
            data = pkg.blob(f["path"])
        except Exception as e:  # noqa: BLE001
            res.add("error", "payload-unreadable", "%s: %s" % (n["node_id"], e))
            continue
        tmp = scratch.file(os.path.basename(f["path"]))
        with open(tmp, "wb") as fh:
            fh.write(data)
        try:
            img = bpy.data.images.load(tmp, check_existing=False)
            img.name = n["node_id"]
            img.pack()                 # the .blend must not depend on scratch
            img.filepath = ""
            img.filepath_raw = ""
        except Exception as e:  # noqa: BLE001
            res.add("error", "texture-load-failed", "%s: %s" % (n["node_id"], e))
            continue
        # `color_space` is mandatory per texture in the manifest (law 8), and
        # this is the line where getting it wrong is invisible in review and
        # obvious on screen. Blender's word for werk's `linear` is `Non-Color`
        # for data maps; the two vocabularies are mapped here, once.
        cs = meta.get("color_space")
        if cs == "srgb":
            img.colorspace_settings.name = "sRGB"
        elif cs == "linear":
            img.colorspace_settings.name = "Non-Color"
        else:
            img.colorspace_settings.name = "Non-Color"
            res.add("warn", "texture-colorspace-missing",
                    "%s: no meta.color_space; treated as Non-Color, which is the "
                    "safe direction (a linear map read as sRGB is wrong maths, an "
                    "sRGB map read as linear is only wrong colour)" % n["node_id"])
        img[PROP_TEX_NODE] = n["node_id"]
        img["werk_usage"] = meta.get("usage", "other")
        img["werk_color_space"] = cs or ""
        images[n["node_id"]] = img
        res.images.append(img)

    for n in nodes_of_type(pkg, "core.material"):
        payload = _json_payload(pkg, n, res)
        if payload is None:
            continue
        mat = _apply_material(payload, images, res)
        if mat is None:
            continue
        res.materials.append(mat)
        node_ids.setdefault("materials", {})[payload.get("material_id", "")] = \
            n["node_id"]
        _assign_material(mat, n, res)


def _assign_material(mat, node, res):
    """Put the material on the meshes it belongs to.

    Without this the material exists in the file and on nothing, so a
    re-export finds no material slots and the node vanishes — which is exactly
    what the first gate run measured (materials 1 -> 0 across a round trip).
    A material that describes a surface nobody is wearing has not survived.

    The join key is `material_id` through the manifest's `materials[]` table
    and the node's `part_id` (law 4: ids join, indices rot). Where the package
    declares exactly one material and the geometry has no slots at all — which
    is the common case for a GLB exported without materials — it goes on
    everything imported from this package.
    """
    targets = []
    part = node.get("part_id")
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        if part and obj.get(PROP_PART_ID) not in (None, "", part):
            continue
        targets.append(obj)
    attached = 0
    for obj in targets:
        names = [s.material.name if s.material else None for s in obj.material_slots]
        if mat.name in names:
            continue
        if not obj.material_slots:
            obj.data.materials.append(mat)
            attached += 1
        elif all(s.material is None for s in obj.material_slots):
            obj.material_slots[0].material = mat
            attached += 1
    if attached:
        res.add("info", "material-assigned",
                "%s: assigned to %d mesh object(s) that carried no material of "
                "their own" % (mat.name, attached))


def _find_material(payload):
    """Match a werk material onto a Blender material the glTF import already
    made, rather than creating a duplicate: by our own stamp first, then by
    the glTF material's name, then by material_id."""
    mid = payload.get("material_id")
    for m in bpy.data.materials:
        if m.get(PROP_MATERIAL_ID) == mid:
            return m
    for key in (payload.get("name"), mid):
        if key and key in bpy.data.materials:
            return bpy.data.materials[key]
    return None


def _apply_material(payload, images, res):
    mat = _find_material(payload)
    created = mat is None
    if created:
        mat = bpy.data.materials.new(payload.get("name") or
                                     payload.get("material_id") or "werk-material")
    mat.use_nodes = True
    mat[PROP_MATERIAL_ID] = payload.get("material_id", "")
    nt = mat.node_tree
    bsdf = next((nd for nd in nt.nodes if nd.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        out = next((nd for nd in nt.nodes if nd.type == "OUTPUT_MATERIAL"), None) \
            or nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
        bsdf.location = (-300, 0)

    def put(name, value):
        if name in bsdf.inputs:
            bsdf.inputs[name].default_value = value
            return True
        return False

    bcf = payload.get("base_color_factor")
    if bcf:
        put("Base Color", tuple(bcf[:4]))
        put("Alpha", float(bcf[3]))
    if "metallic_factor" in payload:
        put("Metallic", float(payload["metallic_factor"]))
    if "roughness_factor" in payload:
        put("Roughness", float(payload["roughness_factor"]))
    if "ior" in payload:
        put("IOR", float(payload["ior"]))
    ef = payload.get("emissive_factor")
    if ef:
        put("Emission Color", tuple(list(ef[:3]) + [1.0]))
        put("Emission Strength", float(payload.get("emissive_strength", 1.0)))

    mode = payload.get("alpha_mode", "opaque")
    # Blender 4.2 renamed the surface blend enum; try the modern spelling
    # first and fall back rather than assume one Blender version.
    try:
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = "BLENDED" if mode in ("blend", "mask") \
                else "DITHERED"
        else:
            mat.blend_method = {"opaque": "OPAQUE", "mask": "CLIP",
                                "blend": "BLEND"}.get(mode, "OPAQUE")
    except (AttributeError, TypeError) as e:
        res.add("info", "alpha-mode-unmapped",
                "%s: this Blender build has no writable alpha blend enum (%s); "
                "alpha_mode `%s` is preserved in the material JSON on export "
                "regardless" % (mat.name, e, mode))
    mat.use_backface_culling = not payload.get("double_sided", False)

    x = -900
    for slot, tex in (payload.get("textures") or {}).items():
        img = images.get(tex.get("node"))
        if img is None:
            res.add("warn", "texture-slot-dangling",
                    "%s: slot `%s` names texture node `%s`, which did not load"
                    % (mat.name, slot, tex.get("node")))
            continue
        tex_node = nt.nodes.new("ShaderNodeTexImage")
        tex_node.image = img
        tex_node.label = slot
        tex_node.location = (x, 300 - 320 * len(nt.nodes) % 900)
        x -= 40
        target_input = _SLOT_TO_INPUT.get(slot)
        try:
            if slot == "normal":
                nm = nt.nodes.new("ShaderNodeNormalMap")
                nm.location = (tex_node.location[0] + 250, tex_node.location[1])
                nm.inputs["Strength"].default_value = float(
                    payload.get("normal_scale", 1.0))
                nt.links.new(tex_node.outputs["Color"], nm.inputs["Color"])
                nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
            elif slot == "metallic_roughness":
                # glTF packs occlusion=R, roughness=G, metallic=B into one
                # image. Splitting is the only correct wiring and the schema's
                # `channel` field says so.
                sep = nt.nodes.new("ShaderNodeSeparateColor")
                sep.location = (tex_node.location[0] + 250, tex_node.location[1])
                nt.links.new(tex_node.outputs["Color"], sep.inputs["Color"])
                nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
                nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
            elif target_input and target_input in bsdf.inputs:
                nt.links.new(tex_node.outputs["Color"], bsdf.inputs[target_input])
                if slot == "base_color" and "Alpha" in bsdf.inputs:
                    nt.links.new(tex_node.outputs["Alpha"], bsdf.inputs["Alpha"])
            else:
                res.add("info", "texture-slot-unwired",
                        "%s: slot `%s` has no Principled BSDF input; the image is "
                        "loaded and present in the node tree, unconnected"
                        % (mat.name, slot))
        except Exception as e:  # noqa: BLE001
            res.add("warn", "texture-wiring-failed",
                    "%s: slot `%s`: %s" % (mat.name, slot, e))
    return mat


# --- colliders -------------------------------------------------------------

def _import_colliders(pkg, res, target, root, node_ids, rigid_body):
    nodes = nodes_of_type(pkg, "core.phys.colliders")
    if not nodes:
        return
    coll = bpy.data.collections.get("colliders") or bpy.data.collections.new("colliders")
    if coll.name not in {c.name for c in target.children}:
        target.children.link(coll)
    for n in nodes:
        payload = _json_payload(pkg, n, res)
        if payload is None:
            continue
        node_ids.setdefault("colliders", []).append(n["node_id"])
        for group in payload.get("groups", []):
            part = group.get("part_id", "part")
            for i, s in enumerate(group.get("spheres", [])):
                # `space` is part-local; this add-on's parts are the identity
                # transform unless a manifest says otherwise, and the swing is
                # the same either way because it is a pure axis relabel.
                e = bpy.data.objects.new("collider:%s:sphere:%d" % (part, i), None)
                e.empty_display_type = "SPHERE"
                e.empty_display_size = float(s["radius"])
                e.location = axes.vec_werk_to_blender(s["center"])
                e[PROP_PART_ID] = part
                e["werk_collider"] = "sphere"
                e["werk_radius"] = float(s["radius"])
                if s.get("material_id"):
                    e["werk_material_id"] = s["material_id"]
                coll.objects.link(e)
                e.parent = root
                res.collider_empties.append(e)
                res.objects.append(e)
            for i, b in enumerate(group.get("boxes", [])):
                e = bpy.data.objects.new("collider:%s:box:%d" % (part, i), None)
                e.empty_display_type = "CUBE"
                e.empty_display_size = 1.0
                e.location = axes.vec_werk_to_blender(b["center"])
                e.rotation_mode = "QUATERNION"
                e.rotation_quaternion = axes.quat_werk_to_blender(b["rotation"])
                # A CUBE empty spans +/- display_size on each axis, so scaling
                # it by the HALF-extents is the identity the schema declares
                # ("Half-extents, not full extents") rather than a factor of 2
                # someone has to remember.
                e.scale = axes.vec_werk_to_blender(b["half_extents"])
                e.scale = tuple(abs(v) for v in e.scale)
                e[PROP_PART_ID] = part
                e["werk_collider"] = "box"
                e["werk_half_extents"] = list(b["half_extents"])
                if b.get("material_id"):
                    e["werk_material_id"] = b["material_id"]
                coll.objects.link(e)
                e.parent = root
                res.collider_empties.append(e)
                res.objects.append(e)

    if rigid_body and res.collider_empties:
        res.add("info", "rigid-body-not-attached",
                "rigid-body shapes were requested, but Blender's rigid body system "
                "binds to mesh objects and these colliders are empties; the "
                "analytic sphere/box parameters are on each empty as custom "
                "properties and are what a solver should read")


# --- skeleton --------------------------------------------------------------

def _import_skeletons(pkg, res, target, root, node_ids):
    for n in nodes_of_type(pkg, "core.skeleton"):
        payload = _json_payload(pkg, n, res)
        if payload is None:
            continue
        arm = _reconcile_existing(payload, res, n["node_id"]) \
            or _build_armature(payload, res, target, root, n["node_id"])
        if arm is not None:
            res.armatures.append(arm)
            node_ids.setdefault("skeletons", {})[payload.get("skeleton_id", "")] = \
                n["node_id"]


def _reconcile_existing(payload, res, node_id):
    """If the GLB already produced this armature, adopt it — do not build a second.

    A skinned mesh forces the joint hierarchy into the GLB (glTF has no other
    way to express JOINTS_0), so for a skinned entity the armature legitimately
    arrives through Blender's glTF importer. Building a `core.skeleton` copy
    beside it would leave the scene with two armatures of the same name and two
    answers to "where is this bone", which is precisely the drift the format
    exists to prevent — and it is what the first rig gate run measured.

    So the glTF armature is adopted, and `core.skeleton` is used for what glTF
    cannot carry (bone roles, retarget maps, `axis_back`) plus one measurement:
    how far glTF's bone reconstruction has drifted from the declared rest pose.
    Reported, never silently accepted.
    """
    want = {b["bone_id"] for b in payload.get("bones", [])}
    if not want:
        return None
    for obj in bpy.data.objects:
        if obj.type != "ARMATURE" or obj.get(PROP_SKELETON_ID):
            continue
        if {b.name for b in obj.data.bones} != want:
            continue
        worst = 0.0
        for b in payload["bones"]:
            bone = obj.data.bones[b["bone_id"]]
            head = mathutils.Vector(axes.vec_werk_to_blender(b["model_rest_head_m"]))
            worst = max(worst, (obj.matrix_world @ bone.head_local - head).length)
        obj[PROP_SKELETON_ID] = payload.get("skeleton_id", "")
        obj["werk_skeleton_source"] = "gltf-skin, cross-checked against core.skeleton"
        res.add("info" if worst < 1e-4 else "warn", "skeleton-adopted-from-gltf",
                "%s: the GLB already carries this armature (a skinned mesh needs "
                "its joints), so it was adopted rather than duplicated; worst "
                "rest-head difference against the declared core.skeleton values "
                "is %.3g m" % (node_id, worst))
        return obj
    return None


def _build_armature(payload, res, target, root, node_id):
    conv = payload.get("conventions") or {}
    # The skeleton restates the conventions inside its own payload precisely so
    # a reader can refuse a mismatch instead of reconciling it (law 3, and the
    # schema says MUST). Blender happens to match every one of them except
    # up_axis, which is what `axes.py` exists for.
    for key, want in (("quat_order", "wxyz"), ("bone_axis_along", "+y"),
                      ("bone_axis_back", "+z"), ("units_per_meter", 1.0)):
        if key in conv and conv[key] != want:
            res.add("error", "unsupported-convention",
                    "%s: skeleton declares %s=%r; this add-on implements only %r — "
                    "refusing the node rather than guessing" % (node_id, key,
                                                                conv[key], want))
            return None
    if payload.get("status") == "draft":
        res.add("info", "skeleton-draft",
                "%s: skeleton `%s` is status `draft`; imported, and saying so"
                % (node_id, payload.get("skeleton_id")))

    name = payload.get("skeleton_id") or node_id
    arm_data = bpy.data.armatures.new(name)
    obj = bpy.data.objects.new(name, arm_data)
    target.objects.link(obj)
    obj.parent = root
    obj[PROP_SKELETON_ID] = payload.get("skeleton_id", "")

    prev = bpy.context.view_layer.objects.active
    bpy.context.view_layer.objects.active = obj
    try:
        bpy.ops.object.mode_set(mode="EDIT")
        made = {}
        for b in payload.get("bones", []):
            head = axes.vec_werk_to_blender(b["model_rest_head_m"])
            if b.get("model_rest_tail_m"):
                tail = axes.vec_werk_to_blender(b["model_rest_tail_m"])
            else:
                along = b["axis_along"]
                ln = float(b["length_m"])
                tail = axes.vec_werk_to_blender(
                    [b["model_rest_head_m"][i] + ln * along[i] for i in range(3)])
            eb = arm_data.edit_bones.new(b["bone_id"])
            eb.head = mathutils.Vector(head)
            eb.tail = mathutils.Vector(tail)
            if (eb.tail - eb.head).length < 1e-6:
                eb.tail = eb.head + mathutils.Vector((0.0, 0.0, 1e-4))
                res.add("warn", "bone-zero-length",
                        "%s: bone `%s` has zero length; Blender deletes those, so it "
                        "was given a 0.1 mm tail" % (node_id, b["bone_id"]))
            # `axis_back` fixes the roll, which is the degree of freedom that
            # silently ruins retargeting when left undeclared (the schema's own
            # words). Blender's align_roll takes exactly this vector.
            if b.get("axis_back"):
                eb.align_roll(mathutils.Vector(axes.vec_werk_to_blender(b["axis_back"])))
            made[b["bone_id"]] = eb
        for b in payload.get("bones", []):
            parent = b.get("parent")
            if parent and parent in made:
                made[b["bone_id"]].parent = made[parent]
            elif parent:
                res.add("warn", "bone-parent-missing",
                        "%s: bone `%s` names parent `%s`, which is not in this "
                        "skeleton" % (node_id, b["bone_id"], parent))
        bpy.ops.object.mode_set(mode="OBJECT")
    except Exception as e:  # noqa: BLE001
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:  # noqa: BLE001
            pass
        res.add("error", "armature-build-failed", "%s: %s" % (node_id, e))
        return None
    finally:
        bpy.context.view_layer.objects.active = prev
    return obj


# --- animation -------------------------------------------------------------

def _import_animation(pkg, res, node_ids):
    import struct

    for n in nodes_of_type(pkg, "core.anim.clip"):
        binf = first_file(n, suffix=".wkac") or first_file(n, suffix=".bin")
        if binf is None:
            for f in node_files(n):
                if not f["path"].endswith(".json"):
                    binf = f
                    break
        if binf is None:
            res.add("warn", "payload-missing", "%s: no clip binary" % n["node_id"])
            continue
        try:
            data = pkg.blob(binf["path"])
            magic, _ver, hdr = werk_read.read_envelope(data)
        except Exception as e:  # noqa: BLE001
            res.add("error", "envelope-invalid", "%s: %s" % (n["node_id"], e))
            continue
        if magic != b"WKAC":
            res.add("error", "envelope-invalid",
                    "%s: magic %r is not WKAC" % (n["node_id"], magic))
            continue

        arm = _armature_for(hdr.get("skeleton_id"))
        if arm is None:
            res.add("warn", "clip-unbound",
                    "%s: no armature for skeleton_id `%s` in this scene; the clip "
                    "was verified and skipped, not failed (law 3)"
                    % (n["node_id"], hdr.get("skeleton_id")))
            continue

        sections = {s["name"]: s for s in hdr.get("sections", [])}
        frames = int(hdr.get("frame_count", 0))
        bones = list(hdr.get("bones") or [])
        rate = float(hdr.get("rate_hz") or 30.0)
        root_bone = hdr.get("root_bone")

        action = bpy.data.actions.new(hdr.get("clip_id") or n["node_id"])
        action[PROP_CLIP_ID] = hdr.get("clip_id") or ""
        action["werk_rate_hz"] = rate
        action["werk_skeleton_id"] = hdr.get("skeleton_id") or ""
        if arm.animation_data is None:
            arm.animation_data_create()
        arm.animation_data.action = action

        scene = bpy.context.scene
        old_frame = scene.frame_current

        # NOTE ON ORDER, because getting it backwards is silent: the property is
        # set and THEN keyframed at `frame=f`, and `scene.frame_set` is never
        # called inside these loops. Calling it after the assignment re-evaluates
        # the half-built action and overwrites the value before it is keyed —
        # which produced a clip that was structurally perfect and animated
        # nothing, measured by the gate as every posed bone sitting at exactly
        # its rest rotation. It is also O(bones x frames) depsgraph evaluations
        # for no purpose.
        rt = sections.get("root-track")
        if rt and root_bone and root_bone in arm.pose.bones:
            pb = arm.pose.bones[root_bone]
            pb.rotation_mode = "QUATERNION"
            # The exporter samples the root track in WORLD space
            # (`arm_obj.matrix_world @ pb.matrix`), so the inverse comes back
            # through the same transform. Using armature space on one side and
            # world on the other agrees only while the armature object sits at
            # the origin, which is exactly the kind of latent asymmetry that
            # passes every test until someone moves the rig.
            to_armature = arm.matrix_world.inverted()
            rest = arm.data.bones[root_bone].matrix_local
            for f in range(frames):
                px, py, pz, qw, qx, qy, qz = struct.unpack_from(
                    "<7f", data, rt["offset"] + rt["stride"] * f)
                loc = mathutils.Vector(axes.vec_werk_to_blender((px, py, pz)))
                # bone-local -> model: LEFT-MULTIPLY, not conjugate (axes.py).
                quat = mathutils.Quaternion(
                    axes.frame_werk_to_blender((qw, qx, qy, qz)))
                desired = to_armature @ (mathutils.Matrix.Translation(loc)
                                         @ quat.to_matrix().to_4x4())
                pb.matrix_basis = rest.inverted() @ desired
                pb.keyframe_insert("location", frame=f)
                pb.keyframe_insert("rotation_quaternion", frame=f)
        elif rt and root_bone:
            res.add("warn", "clip-root-bone-missing",
                    "%s: root_bone `%s` is not in armature `%s`; the per-bone tracks "
                    "were still applied" % (n["node_id"], root_bone, arm.name))

        # Per-bone tracks: LOCAL rotations relative to the parent BONE's frame.
        # These are INVARIANT under the werk->Blender swing — see axes.py. The
        # only conversion needed is rest^-1 * desired, which turns a local
        # orientation into Blender's basis-relative-to-rest convention.
        br = sections.get("bone-rotations")
        applied = 0
        if br:
            for b_i, bone_id in enumerate(bones):
                pb = arm.pose.bones.get(bone_id)
                if pb is None:
                    res.add("info", "clip-bone-unbound",
                            "%s: track for bone `%s` has no match in armature `%s`; "
                            "dropped with a report, never a failure"
                            % (n["node_id"], bone_id, arm.name))
                    continue
                pb.rotation_mode = "QUATERNION"
                bone = arm.data.bones[bone_id]
                if bone.parent is not None:
                    rest_local = bone.parent.matrix_local.inverted() @ bone.matrix_local
                else:
                    rest_local = bone.matrix_local
                rest_rot = rest_local.to_quaternion()
                for f in range(frames):
                    qw, qx, qy, qz = struct.unpack_from(
                        "<4f", data, br["offset"] + br["stride"] * (b_i * frames + f))
                    local = mathutils.Quaternion((qw, qx, qy, qz))
                    pb.rotation_quaternion = rest_rot.inverted() @ local
                    pb.keyframe_insert("rotation_quaternion", frame=f)
                applied += 1

        # A uniform-rate clip is a grid of samples, so the curve between two
        # samples is linear, not Bezier: animclip.layout.txt's interpolation
        # section says positions are linear and rotations shortest-arc SLERP,
        # and Blender's default Bezier handles would overshoot between the very
        # samples the format went to the trouble of fixing.
        for fc in action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
            fc.update()

        scene.frame_set(old_frame)
        scene.frame_start = 0
        scene.frame_end = max(scene.frame_end, max(0, frames - 1))
        scene.render.fps = int(round(rate))

        res.actions.append(action)
        node_ids.setdefault("clips", {})[hdr.get("clip_id") or n["node_id"]] = \
            n["node_id"]
        res.add("info", "clip-imported",
                "%s: %d frame(s) at %.4f Hz over %d/%d bone track(s) onto `%s`"
                % (n["node_id"], frames, rate, applied, len(bones), arm.name))

        for ev in hdr.get("events") or []:
            m = action.pose_markers.new("%s:%s" % (ev.get("kind", "marker"),
                                                   ev.get("effect_id", "")))
            m.frame = int(round(float(ev.get("t_s", 0.0)) * rate))


def _armature_for(skeleton_id):
    for o in bpy.data.objects:
        if o.type == "ARMATURE" and (
                o.get(PROP_SKELETON_ID) == skeleton_id or o.name == skeleton_id):
            return o
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    return arms[0] if len(arms) == 1 else None


# --- audio -----------------------------------------------------------------

def _import_audio(pkg, res, scratch, node_ids, load_preview):
    effects = nodes_of_type(pkg, "core.audio.effect", "core.audio.ambience")
    if not effects:
        return
    listed = []
    for n in effects:
        wavs = [f["path"] for f in node_files(n) if f["path"].endswith(".wav")]
        listed.append("%s (%d take%s)" % (n["node_id"], len(wavs),
                                          "" if len(wavs) == 1 else "s"))
    node_ids["audio"] = [n["node_id"] for n in effects]
    res.add("info", "audio-listed",
            "%d audio node(s) verified and listed in the report: %s"
            % (len(effects), ", ".join(listed)))

    if not load_preview:
        return
    preview_id = (pkg.manifest.get("primary") or {}).get("sound")
    node = find_node(pkg, preview_id) if preview_id else None
    if node is None:
        pkgs = nodes_of_type(pkg, "core.audio.package")
        slug = None
        for p in pkgs:
            payload = _json_payload(pkg, p, res)
            if payload:
                slug = payload.get("preview_effect")
                break
        if slug:
            node = next((n for n in effects if n["node_id"].endswith(slug)), None)
        if node is None:
            node = effects[0]
        res.add("info", "primary-fallback",
                "no usable primary.sound; FELL BACK to `%s`, and reporting it as "
                "SPEC section 2 requires" % node["node_id"])
    f = first_file(node, role="best", suffix=".wav") or first_file(node, suffix=".wav")
    if f is None:
        res.add("warn", "payload-missing", "%s: no WAV take" % node["node_id"])
        return
    tmp = scratch.file(os.path.basename(f["path"]))
    with open(tmp, "wb") as fh:
        fh.write(pkg.blob(f["path"]))
    try:
        snd = bpy.data.sounds.load(tmp, check_existing=False)
        snd.name = node["node_id"]
        snd.use_memory_cache = True
        snd.pack()
        res.sounds.append(snd)
        node_ids["preview_sound"] = node["node_id"]
    except Exception as e:  # noqa: BLE001
        res.add("warn", "audio-load-failed", "%s: %s" % (node["node_id"], e))


# --- identity, notes, report ----------------------------------------------

def _stamp_identity(pkg, res, root, node_ids):
    """Everything the exporter needs to give the package its identity back.

    Law 4: ids survive re-export, indices rot. A werk that goes into Blender
    and comes out with a fresh uuid is a DIFFERENT entity, and would silently
    fork every downstream reference — so the uuid, the node ids, the parts,
    the materials table, the semantics payload and the licence text all ride
    on the root empty as custom properties.
    """
    m = pkg.manifest
    root[PROP_UUID] = res.entity_uuid or ""
    root[PROP_NAME] = res.entity_name
    root[PROP_SOURCE] = res.source_path
    root[PROP_MANIFEST_SHA] = pkg.manifest_sha256
    root[PROP_PROFILE] = m.get("profile", "")
    root[PROP_NODE_IDS] = json.dumps(node_ids, sort_keys=True)
    root[PROP_PARTS] = json.dumps(m.get("parts", []), sort_keys=True)
    root[PROP_MATERIALS] = json.dumps(m.get("materials", []), sort_keys=True)
    root[PROP_PRIMARY] = json.dumps(m.get("primary", {}), sort_keys=True)
    if m.get("entity", {}).get("summary"):
        root["werk_entity_summary"] = m["entity"]["summary"]

    sem_nodes = nodes_of_type(pkg, "core.semantics")
    if sem_nodes:
        payload = _json_payload(pkg, sem_nodes[0], res)
        if payload is not None:
            root[PROP_SEMANTICS] = json.dumps(payload, sort_keys=True)
            root[PROP_TAGS] = json.dumps(payload.get("facets", {}), sort_keys=True)
            node_ids["semantics"] = sem_nodes[0]["node_id"]
            root[PROP_NODE_IDS] = json.dumps(node_ids, sort_keys=True)
            flat = sorted("%s/%s" % (facet, t)
                          for facet, tags in (payload.get("facets") or {}).items()
                          for t in tags)
            root["werk_tag_list"] = ", ".join(flat)
    lic = m.get("license", {})
    if lic.get("file"):
        try:
            root[PROP_LICENSE] = pkg.blob(lic["file"]).decode("utf-8")
            root["werk_license_spdx"] = lic.get("spdx_id", "")
        except Exception:  # noqa: BLE001
            res.add("warn", "license-unreadable",
                    "the manifest names LICENSE but its bytes could not be read")


def _note_unimplemented(pkg, res):
    """Declared narrowness is the design; undeclared silence is the failure
    (SPEC section 10.0). Every core family present in the package that this
    add-on does not turn into Blender data gets named here."""
    handled = {
        "core.spec", "core.loader", "core.license", "core.readme",
        "core.geom.source", "core.geom.game", "core.geom.lod", "core.tex",
        "core.material", "core.phys.colliders", "core.skeleton",
        "core.anim.clip", "core.audio.package", "core.audio.effect",
        "core.audio.ambience", "core.semantics", "core.phys.bounds",
        "core.provenance", "core.props",
        "core.geom.points", "core.geom.gsplat",
        "core.recipe", "core.tool", "core.tool.config",
    }
    no_blender_form = {
        "core.phys.bounds": "recomputed on export from the mesh itself, so a "
                            "stale value can never survive a round trip",
        "core.props": "carried as data; Blender has no simulation-property "
                      "datablock to put it in",
        "core.provenance": "carried as data; re-authored on export",
        "core.spec": "the specification, extractable but not scene data",
        "core.loader": "source code, never executed (SPEC section 7.1)",
        "core.recipe": "carried as data; Blender has nothing to put a "
                       "reproduction record in",
        "core.tool": "the source of a tool that made this package. Carried, "
                     "readable, and NEVER executed (SPEC section 7.1) -- an "
                     "importer that ran an embedded tool would be the exact "
                     "thing that doctrine forbids",
        "core.tool.config": "carried as data beside its tool",
    }
    seen = set()
    for n in pkg.nodes:
        t = n["type"]
        if not t.startswith("core.") or t in seen:
            continue
        seen.add(t)
        if t not in handled:
            res.nodes_not_implemented.append(t)
            res.add("info", "node-type-not-implemented",
                    "`%s` is a core family this add-on does not import; its bytes "
                    "were verified and it is extractable" % t)
        elif t in no_blender_form:
            res.add("info", "node-type-data-only",
                    "`%s`: %s" % (t, no_blender_form[t]))


def _work_notes_text(pkg):
    lines = ["werk work notes (law 6: every version says why it exists)",
             "=========================================================", ""]
    for n in pkg.nodes:
        ver = resolved_version(n)
        if ver is None:
            lines.append("%-32s %-24s (no usable version)"
                         % (n["node_id"], n["type"]))
            continue
        prod = ver.get("producer", {})
        lines.append("%s  [%s]  v%d  %s" % (n["node_id"], n["type"], ver["v"],
                                            ver.get("epistemic", "?")))
        lines.append("    producer: %s %s%s" % (
            prod.get("tool", "?"), prod.get("version", "?"),
            (" (model %s)" % prod["model"]) if prod.get("model") else ""))
        if ver.get("input_files"):
            lines.append("    inputs  : %s" % ", ".join(ver["input_files"]))
        if ver.get("input_hash"):
            lines.append("    input_hash: %s" % ver["input_hash"])
        lines.append("    note    : %s" % ver.get("note", ""))
        lines.append("")
    return "\n".join(lines) + "\n"


def _write_text(name, body):
    txt = bpy.data.texts.get(name)
    if txt is None:
        txt = bpy.data.texts.new(name)
    txt.clear()
    txt.write(body)
    return txt
