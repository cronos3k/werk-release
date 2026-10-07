#!/usr/bin/env python3
"""
build_expectations.py -- ground truth for roundNC (plan section 1.3).

Writes expectations.json plus the canonical mesh dumps it pins
(expectations-data/<fmt>-mesh-dump.f32). Both stay OUTSIDE every agent
workspace, always. The grader (grade_nc.py) reads only these.

Per fixture, two tiers:
  Tier 1  sha256 of every payload the format stores verbatim.
  Tier 2  canonical mesh dump: positions float32 LE in storage order, no dedup,
          no reindex; plus vertex count, triangle count, bbox (6 floats).

Status per format:
  werk  COMPLETE    from gauntlet/roundOW/mini-v1.werk (sha256 pinned below).
  gltf  CONTROLS_STATUS  from crate-nc-v1.gltf + .bin + crate_diffuse.png as
                    stored (build_gltf_usdz.py --format gltf). If the planned
                    fixture is missing, falls back to the in-repo SOURCE and
                    marks the format INCOMPLETE.
  fbx   CONTROLS_STATUS  from crate-nc-v1.fbx as stored (nc_fbx.py),
                    cross-checked with build_controls.py's record.
  usdz  CONTROLS_STATUS  from crate-nc-v1.usdz: zip entries read with zipfile
                    (stdlib); Tier 2 from the build record (Blender's bundled
                    USD library read the authored points; usdc is not
                    stdlib-parseable).
CONTROLS_STATUS is PROVISIONAL until the dry-runs pass, then COMPLETE.

Usage:
  py -3.13 build_expectations.py [--repo D:/werk/werk] [--out expectations.json]

Standard library only.
"""

import argparse
import binascii
import json
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nc_mesh  # noqa: E402

# PROVISIONAL until every dry-run passes; then COMPLETE (the freeze).
CONTROLS_STATUS = "COMPLETE"

WERK_FIXTURE = "gauntlet/roundOW/mini-v1.werk"
WERK_SHA256 = "f7bdcc853009504b1d31b2934a7a8294cbf0e6f227c95f7de1e81af0947e9837"

# The glTF fixture as the plan names it (section 1.2). Not built yet.
GLTF_PLANNED = ["crate-nc-v1.gltf", "crate-nc-v1.bin", "crate_diffuse.png"]
# The in-repo input the plan points at (Poly Haven glTF-separate download).
GLTF_SOURCE_DIR = "fixtures/sources/crate-cc0"
GLTF_SOURCE = "wooden_crate_01_2k.gltf"

# Plan 1.3 table, fixed now. 'payload_checks' is what the grader uses for the
# verifiable-integrity fraction: which integrity kinds cover a payload's bytes.
INTEGRITY_TABLE = {
    "werk": {
        "declares": "per-file sha256 for every declared file, zip CRC-32s, "
                    "spec_sha256, input_hash, Ed25519 chain",
        "payload_checks": ["sha256", "crc32"],
    },
    "fbx": {
        "declares": "none (no checksums of any kind)",
        "payload_checks": [],
    },
    "gltf": {
        "declares": "none (byteLength/count consistency checks only, not cryptographic)",
        "payload_checks": [],
        "structural_only": ["buffers[].byteLength", "bufferViews[].byteLength",
                            "accessors[].count", "accessors[].min/max"],
    },
    "usdz": {
        "declares": "zip CRC-32 per entry (a real, checkable declaration, and the only one)",
        "payload_checks": ["crc32"],
    },
}

DUMP_DEF = ("positions only, float32 little-endian, in the file's own storage "
            "order (meshes[] then primitives[] in index order, POSITION "
            "accessor element order), no dedup, no reindex, no node transforms")


def rel(p, root):
    return os.path.relpath(p, root).replace("\\", "/")


def write_dump(datadir, name, positions):
    os.makedirs(datadir, exist_ok=True)
    d = nc_mesh.canonical_dump(positions)
    p = os.path.join(datadir, name)
    with open(p, "wb") as f:
        f.write(d)
    return name


def mesh_tier2(prims, datadir, dumpname, provisional=False):
    pos = [p for pr in prims for p in pr["positions"]]
    tri = sum(pr["triangle_count"] for pr in prims)
    rec = nc_mesh.mesh_record(pos, tri)
    rec["dump_definition"] = DUMP_DEF
    rec["dump_file"] = "expectations-data/" + write_dump(datadir, dumpname, pos)
    offs = [pr["position_byte_offset"] for pr in prims]
    rec["storage_order_equals_byte_order"] = offs == sorted(offs)
    rec["submeshes"] = []
    for pr in prims:
        s = nc_mesh.mesh_record(pr["positions"], pr["triangle_count"])
        s.update({"mesh_index": pr["mesh_index"], "mesh_name": pr["mesh_name"],
                  "primitive_index": pr["primitive_index"]})
        rec["submeshes"].append(s)
    if provisional:
        rec["provisional"] = True
    return rec


def theoretical_fraction(fmt_entry, cls):
    """Verifiable-integrity fraction if the agent extracted the primary mesh
    plus the primary payload of class cls. Weighted by stored payload bytes."""
    pays = fmt_entry.get("payloads", [])
    pick = []
    for c in ("mesh", cls):
        prim = [p for p in pays if p["class"] == c and p.get("primary")]
        if prim:
            pick.append(prim[0])
    if not any(p["class"] == "mesh" for p in pick) and fmt_entry.get("tier2_mesh"):
        t2 = fmt_entry["tier2_mesh"]
        pick.insert(0, {"id": "mesh:tier2", "class": "mesh", "size": t2["dump_size"],
                        "integrity": t2.get("integrity", [])})
    if not pick:
        return None
    tot = sum(p["size"] for p in pick)
    anyv = sum(p["size"] for p in pick if p["integrity"])
    cry = sum(p["size"] for p in pick if "sha256" in p["integrity"])
    return {"payloads": [p["id"] for p in pick],
            "any_declared": round(anyv / tot, 6) if tot else None,
            "cryptographic": round(cry / tot, 6) if tot else None}


# ------------------------------------------------------------------- werk

def build_werk(repo, datadir):
    fx = os.path.join(repo, WERK_FIXTURE)
    got = nc_mesh.sha256_file(fx)
    if got != WERK_SHA256:
        raise SystemExit("ABORT: %s sha256 %s != pinned %s" % (fx, got, WERK_SHA256))
    with zipfile.ZipFile(fx) as z:
        man = json.loads(z.read("MANIFEST.json"))
        declared = {}
        roles = {}
        for n in man.get("nodes", []):
            for v in n.get("versions", []):
                for f in v.get("files", []):
                    declared[f["path"]] = f["sha256"]
                    roles[f["path"]] = (n["node_id"], n["type"], f.get("role"))
        # Sanity: the declared hashes and the zip CRCs must hold for the
        # pinned fixture, or ground truth is wrong before any trial.
        bad = z.testzip()
        if bad:
            raise SystemExit("ABORT: zip CRC failure on %s" % bad)
        for p, h in declared.items():
            if nc_mesh.sha256_bytes(z.read(p)) != h:
                raise SystemExit("ABORT: declared sha256 mismatch on %s" % p)
        crc = {i.filename: "%08x" % i.CRC for i in z.infolist()}
        glb = z.read("geometry/game.glb")
    primary = man.get("primary", {})
    mesh_node = primary.get("mesh")
    sound_node = primary.get("sound")

    payloads = []

    def add(cls, path, is_primary):
        payloads.append({
            "id": "%s:%s" % (cls, path), "class": cls, "path": path,
            "sha256": declared[path], "size": None,  # filled from the zip below
            "crc32": crc[path], "node": roles[path][0], "node_type": roles[path][1],
            "file_role": roles[path][2], "primary": is_primary,
            "integrity": ["sha256", "crc32"],
        })

    with zipfile.ZipFile(fx) as z:
        sizes = {i.filename: i.file_size for i in z.infolist()}
    for p, (nid, ntype, role) in roles.items():
        if nid == mesh_node and p.endswith(".glb"):
            add("mesh", p, True)
        elif nid == sound_node and p.endswith(".wav"):
            add("sound", p, role == "best")
        elif p.endswith(".png"):
            add("texture", p, True)
    for pl in payloads:
        pl["size"] = sizes[pl["path"]]

    gl, binc = nc_mesh.parse_glb(glb)
    prims = nc_mesh.gltf_primitives(gl, [binc])
    tier2 = mesh_tier2(prims, datadir, "werk-mesh-dump.f32")
    tier2["source_payload"] = "mesh:geometry/game.glb"

    e = {
        "status": "COMPLETE",
        "fixture_files": [{"path": WERK_FIXTURE, "name": "mini-v1.werk",
                           "sha256": got, "size": os.path.getsize(fx),
                           "role": "container"}],
        "payloads": payloads,
        "tier1_declared_all": declared,
        "tier2_mesh": tier2,
        "manifest_primary": primary,
        "absent_classes": [],
        "notes": [
            "Tier 1 = the manifest's own declared sha256 for every declared file.",
            "sound class: any of the four declared WAVs of the primary sound node "
            "counts as 'one sound'; the role=best WAV is marked primary.",
            "texture class: the only image in the package is "
            "x/splat-foley/segments/seg_00.png (a segment crop, used as the "
            "'texture-class PNG' the plan 1.1 mentions). Used only if the werk "
            "baseline is ever graded with --payload texture; plan 2.1 keeps the "
            "baseline on 'one sound'.",
        ],
    }
    return e


# ------------------------------------------------------------------- glTF

def build_gltf(repo, here, datadir):
    planned_dir = here  # after the move: gauntlet/roundNC/
    planned = [os.path.join(planned_dir, n) for n in GLTF_PLANNED]
    planned_present = {n: os.path.exists(p) for n, p in zip(GLTF_PLANNED, planned)}

    srcdir = os.path.join(repo, GLTF_SOURCE_DIR)
    src = os.path.join(srcdir, GLTF_SOURCE)
    if all(planned_present.values()):
        gpath = planned[0]
        origin = "planned fixture (gauntlet/roundNC/crate-nc-v1.*)"
    elif os.path.exists(src):
        gpath = src
        origin = "in-repo SOURCE (%s), NOT the planned fixture" % GLTF_SOURCE_DIR
    else:
        return {"status": "BLOCKED", "missing": [GLTF_SOURCE_DIR + "/" + GLTF_SOURCE]}

    with open(gpath, "rb") as f:
        gjson = json.loads(f.read().decode("utf-8"))
    gdir = os.path.dirname(gpath)
    refs = []
    for i, b in enumerate(gjson.get("buffers", [])):
        refs.append(("buffer", i, b.get("uri"), None))
    for i, im in enumerate(gjson.get("images", [])):
        refs.append(("image", i, im.get("uri"), im.get("name")))

    files = [{"path": rel(gpath, repo), "name": os.path.basename(gpath),
              "sha256": nc_mesh.sha256_file(gpath), "size": os.path.getsize(gpath),
              "role": "container"}]
    payloads = []
    missing = []
    for kind, idx, uri, name in refs:
        p = os.path.join(gdir, uri)
        if not os.path.exists(p):
            missing.append({"kind": kind, "index": idx, "uri": uri, "name": name,
                            "expected_at": rel(p, repo)})
            continue
        h = nc_mesh.sha256_file(p)
        files.append({"path": rel(p, repo), "name": uri, "sha256": h,
                      "size": os.path.getsize(p), "role": "sidecar-" + kind})
        cls = "mesh" if kind == "buffer" else "texture"
        payloads.append({
            "id": "%s:%s" % (cls, uri), "class": cls, "path": uri, "sha256": h,
            "size": os.path.getsize(p), "primary": idx == 0 if kind == "buffer"
            else (len([r for r in refs if r[0] == "image"]) == 1
                  or (name or "").endswith("_diff")), "integrity": [],
            "note": "external buffer; Tier 1 for the mesh class" if kind == "buffer"
            else "external image",
        })

    tier2 = None
    if not any(m["kind"] == "buffer" for m in missing):
        _, prims = nc_mesh.load_gltf_any(gpath)
        tier2 = mesh_tier2(prims, datadir, "gltf-mesh-dump.f32",
                           provisional=gpath == src or CONTROLS_STATUS != "COMPLETE")
        tier2["source_payload"] = "all POSITION accessors of the scene"
        tier2["accept_submesh_as_c5"] = False

    complete = not missing and gpath != src
    e = {
        "status": CONTROLS_STATUS if complete else "INCOMPLETE",
        "origin": origin,
        "planned_fixture_files": GLTF_PLANNED,
        "planned_fixture_present": planned_present,
        "fixture_files": files,
        "payloads": payloads,
        "tier2_mesh": tier2,
        "missing_inputs": missing,
        "absent_classes": ["sound"],  # glTF 2.0 core cannot reference audio
        "blocking_issues": [],
    }
    recp = os.path.join(here, "build", "gltf-build-record.json")
    if complete and os.path.exists(recp):
        with open(recp, encoding="utf-8") as f:
            rec = json.load(f)
        want = {x["name"]: x["sha256"] for x in rec["fixture_files"]}
        have = {x["name"]: x["sha256"] for x in files}
        if want != have or not rec["all_checks_ok"]:
            raise SystemExit("ABORT: glTF fixture files differ from build record, or build checks failed")
        e["gltf"] = rec["gltf"]
        e["mesh_totals_note"] = rec["mesh_totals"].get("vs_fbx")
        e["build"] = {"script": "build_gltf_usdz.py --format gltf + blender_export_nc.py",
                      "record": "build/gltf-build-record.json",
                      "blender": rec["blender"]["pin"], "blender_build_hash": rec["blender"]["build_hash"],
                      "addons": rec["blender"]["addons"], "env_pins": rec["blender"]["env_pins"],
                      "export_settings": rec["export_settings"],
                      "import_settings": rec["import_settings"], "scene_edits": rec["scene_edits"],
                      "inputs": rec["inputs"], "determinism": {
                          "byte_identical": rec["determinism"]["byte_identical"]},
                      "leak_scan_hits": len(rec["leak_scan"]["hits"])}
        e["notes"] = [
            "Blender glTF Separate export of the same CC0 crate mesh and the same CC0 albedo "
            "PNG as the FBX and USDZ controls. Not Poly Haven verbatim (see README).",
            "Tier 1 = the .bin (mesh class) and the .png (texture class), as shipped.",
            "Tier 2 = canonical dump from the glTF's own POSITION accessors.",
            "The exporter split 51 vertices (distinct normal/UV per loop): 4737 vertices "
            "as stored vs 4686 in Blender and in the FBX. Triangles equal (6576).",
        ]
    if gpath == src:
        e["blocking_issues"] += [
            "The planned fixture crate-nc-v1.gltf/.bin + crate_diffuse.png does not exist.",
            "The in-repo source glTF references %d image(s) that are NOT vendored "
            "(SOURCE.txt says they were deliberately left out): %s."
            % (len([m for m in missing if m["kind"] == "image"]),
               ", ".join(m["uri"] for m in missing if m["kind"] == "image")),
            "The source images are JPEG (image/jpeg); the plan names a PNG "
            "(crate_diffuse.png). Using Poly Haven's files verbatim (plan's "
            "preferred route) gives 1 .bin + 3 .jpg sidecars under the source "
            "names, which conflicts with the planned crate-nc-v1.* names and "
            "with the prompt's 'two files it references' clause (E3). Renaming "
            "the .bin requires editing the .gltf JSON, i.e. no longer verbatim.",
            "Mesh tiers below are computed from the vendored source .gltf/.bin and "
            "are PROVISIONAL until the fixture is frozen.",
        ]
    return e


# ---------------------------------------------------------- FBX / USDZ stubs

FBX_NAME = "crate-nc-v1.fbx"
FBX_RECORD = "build/fbx-build-record.json"
FBX_DUMP_DEF = ("positions only, float32 little-endian: Objects/Geometry nodes of class "
                "'Mesh' in FILE order, each Vertices array (float64 in the file) in element "
                "order, each value converted to float32 (lossless here: checked at build), "
                "no dedup, no reindex, no node transforms (Model Lcl transforms and "
                "GlobalSettings axes NOT applied)")
FBX_PENDING = [
    "Freeze: the fixture bytes are a single build; the freeze commit pins them. "
    "A rebuild changes the sha256 (CreationTimeStamp; see determinism).",
]


def stub_fbx():
    return {
        "status": "STUB",
        "plug_in": "run build_controls.py first (needs Blender 4.2.1 LTS); then rerun "
                   "build_expectations.py.",
        "fixture_files": [], "payloads": [], "tier2_mesh": None,
        "absent_classes": ["sound"],  # FBX audio embedding is nonstandard
    }


def build_fbx(repo, here, datadir):
    """PROVISIONAL ground truth for crate-nc-v1.fbx, read from the FBX AS STORED
    (stdlib parser nc_fbx.py), cross-checked against build_controls.py's record
    (Blender's own view before export and after re-import)."""
    fx = os.path.join(here, FBX_NAME)
    recp = os.path.join(here, FBX_RECORD)
    if not (os.path.exists(fx) and os.path.exists(recp)):
        return stub_fbx()
    import nc_fbx
    with open(fx, "rb") as f:
        b = f.read()
    with open(recp, encoding="utf-8") as f:
        rec = json.load(f)
    h = nc_mesh.sha256_bytes(b)
    if h != rec["sha256"] or not rec["all_checks_ok"]:
        raise SystemExit("ABORT: %s sha256 %s != build record %s, or build checks failed"
                         % (fx, h, rec["sha256"]))
    d = nc_fbx.describe(b)
    vids = [v for v in d["videos"] if v["content"]]
    if len(vids) != 1:
        raise SystemExit("ABORT: expected one embedded Video/Content, found %d" % len(vids))
    v = vids[0]
    content = v["content"]
    src_tex = rec["inputs"]["texture"]
    if nc_mesh.sha256_bytes(content) != src_tex["sha256"]:
        raise SystemExit("ABORT: embedded Content is not the source PNG bytes")
    tex_name = v["relative_filename"].replace("\\", "/").split("/")[-1]
    payloads = [{
        "id": "texture:" + tex_name, "class": "texture", "path": tex_name,
        "sha256": nc_mesh.sha256_bytes(content), "size": len(content),
        "primary": True, "integrity": [],
        "media_type": "image/png", "png_size": src_tex["png_size"],
        "stored_as": "Objects/Video '%s' property Content (type R raw bytes), "
                     "payload at file offset %d" % (v["name"], v["content_offset"]),
        "verbatim": "Content bytes == source PNG bytes (no re-encode); occurs once "
                    "in the file; Blender re-import packs the same bytes",
        "fbx_filename": v["filename"], "fbx_relative_filename": v["relative_filename"],
        "source": "%s!%s (MANIFEST sha256 verified at build)" % (src_tex["package"], src_tex["entry"]),
    }]
    prims = []
    for i, g in enumerate(d["geometries"]):
        if not g["f64_to_f32_lossless"]:
            raise SystemExit("ABORT: float64 -> float32 not lossless in %s" % g["name"])
        prims.append({"mesh_index": i, "mesh_name": g["name"], "primitive_index": 0,
                      "positions": g["positions"], "triangle_count": g["triangle_count"],
                      "position_byte_offset": g["offset"]})
    tier2 = mesh_tier2(prims, datadir, "fbx-mesh-dump.f32",
                       provisional=CONTROLS_STATUS != "COMPLETE")
    tier2["dump_definition"] = FBX_DUMP_DEF
    tier2["storage_order"] = "Geometry nodes in file order (ascending node offset)"
    tier2["source_payload"] = "all Objects/Geometry (Mesh) Vertices arrays of the file"
    tier2["accept_submesh_as_c5"] = False  # same rule as glTF (R5)
    tier2["polygon_count"] = sum(g["polygon_count"] for g in d["geometries"])
    tier2["all_polygons_triangles"] = tier2["polygon_count"] == tier2["triangle_count"]
    by_geom = {g["name"]: g for g in d["geometries"]}
    pre = {x["mesh"]: x for x in rec["blender_view_before_export"]}
    for s_ in tier2["submeshes"]:
        g = by_geom[s_["mesh_name"]]
        s_["polygon_count"] = g["polygon_count"]
        s_["fbx_geometry_id"] = g["id"]
        s_["blender_object"] = pre[s_["mesh_name"]]["object"]
        if pre[s_["mesh_name"]]["positions_f32_sha256"] != s_["dump_sha256"]:
            raise SystemExit("ABORT: Blender view disagrees on %s" % s_["mesh_name"])
    tier2["cross_check"] = ("per Geometry: vertex, polygon and triangle counts and the "
                            "float32 position sha256 equal Blender's mesh before export "
                            "AND Blender's re-import of the FBX (build record checks)")
    det = {k: val for k, val in rec["determinism"].items()
           if k not in ("header_run1", "header_run2")}
    return {
        "status": CONTROLS_STATUS,
        "provisional_pending": FBX_PENDING if CONTROLS_STATUS != "COMPLETE" else [],
        "fixture_files": [{"path": rel(fx, repo), "name": FBX_NAME, "sha256": h,
                           "size": len(b), "role": "container"}],
        "payloads": payloads,
        "tier2_mesh": tier2,
        "absent_classes": ["sound"],  # FBX audio embedding is nonstandard
        "fbx": {"version": d["version"], "creator": d["header"].get("Creator"),
                "creation_timestamp": d["header"].get("CreationTimeStamp"),
                "geometry_count": len(d["geometries"]), "video_count": len(d["videos"])},
        "build": {"script": "build_controls.py + blender_export_fbx.py",
                  "record": FBX_RECORD,
                  "blender": rec["blender"]["pin"], "blender_build_hash": rec["blender"]["build_hash"],
                  "addons": rec["blender"]["addons"], "env_pins": rec["blender"]["env_pins"],
                  "argv": rec["blender"]["argv"],
                  "export_settings": rec["export_settings"],
                  "import_settings": rec["import_settings"],
                  "scene_edits": rec["scene_edits"],
                  "inputs": rec["inputs"],
                  "determinism": det},
        "notes": [
            "Tier 1 = the embedded texture only. FBX stores the mesh as arrays, "
            "not as a sub-file, so the mesh class is Tier 2 only.",
            "The same PNG bytes are textures/crate-cc0-albedo.png in "
            "fixtures/crate-cc0-*-v1.werk (MANIFEST-declared there). Not reachable "
            "from an isolated FBX workspace.",
            "Vertex/triangle totals equal the glTF source (4686 / 6576): the glTF "
            "import kept vertices 1:1 (merge_vertices=False) and FBX stores Blender "
            "vertices without splitting. Geometry ORDER differs from the glTF "
            "(FBX file order: lid, body, latch).",
        ],
    }


USDZ_NAME = "crate-nc-v1.usdz"
USDZ_RECORD = "build/usdz-build-record.json"
USDZ_DUMP_DEF = ("positions only, float32 little-endian: every UsdGeom.Mesh prim in stage "
                 "traversal order (Usd.Stage.Traverse, i.e. namespace order: primChildren), each "
                 "'points' attribute (point3f[], default time) in element order; no dedup, no "
                 "reindex, no xform ops applied, no up-axis conversion (stage upAxis Z, as stored)")


def stub_usdz():
    return {
        "status": "STUB",
        "plug_in": "run build_gltf_usdz.py --format usdz first; then rerun build_expectations.py.",
        "fixture_files": [], "payloads": [], "tier2_mesh": None,
        "absent_classes": ["sound"],
    }


def build_usdz(repo, here, datadir):
    """Ground truth for crate-nc-v1.usdz. Zip entries are read here with
    zipfile (stdlib). Tier 2 comes from the build record: Blender's bundled
    USD library (pxr) read the authored points of the exported stage, and the
    build cross-checked them with Blender's mesh before export and after a
    re-import of the usdz. Stdlib Python cannot parse binary usdc, so an agent
    reaches the mesh only by parsing usdc itself."""
    import io
    fx = os.path.join(here, USDZ_NAME)
    recp = os.path.join(here, USDZ_RECORD)
    if not (os.path.exists(fx) and os.path.exists(recp)):
        return stub_usdz()
    with open(fx, "rb") as f:
        b = f.read()
    with open(recp, encoding="utf-8") as f:
        rec = json.load(f)
    h = nc_mesh.sha256_bytes(b)
    if h != rec["fixture_files"][0]["sha256"] or not rec["all_checks_ok"]:
        raise SystemExit("ABORT: %s sha256 %s != build record, or build checks failed" % (fx, h))
    entries = []
    with zipfile.ZipFile(io.BytesIO(b)) as z:
        if z.testzip() is not None:
            raise SystemExit("ABORT: zip CRC failure in %s" % fx)
        for i in z.infolist():
            d = z.read(i.filename)
            entries.append({"name": i.filename, "size": i.file_size, "crc32": "%08x" % i.CRC,
                            "sha256": nc_mesh.sha256_bytes(d), "compress_type": i.compress_type,
                            "magic": d[:8].decode("latin-1")})
    src_tex = rec["inputs"]["texture"]
    pngs = [e for e in entries if e["name"].lower().endswith(".png")]
    if len(pngs) != 1 or pngs[0]["sha256"] != src_tex["sha256"]:
        raise SystemExit("ABORT: USDZ PNG entry is not the source PNG")
    png = pngs[0]
    payloads = [{
        "id": "texture:" + png["name"], "class": "texture", "path": png["name"],
        "sha256": png["sha256"], "size": png["size"], "primary": True,
        "integrity": ["crc32"], "crc32": png["crc32"],
        "media_type": "image/png", "png_size": src_tex["png_size"],
        "stored_as": "zip entry %s (stored, uncompressed)" % png["name"],
        "verbatim": "entry bytes == source PNG bytes (no re-encode)",
        "source": "%s!%s (MANIFEST sha256 verified at build)" % (src_tex["package"], src_tex["entry"]),
    }]
    st = rec["usdz"]["pxr_stage"]
    dmp = rec["usdz"]["pxr_mesh_dump"]
    with open(os.path.join(here, dmp["file"]), "rb") as f:
        raw = f.read()
    if nc_mesh.sha256_bytes(raw) != dmp["sha256"]:
        raise SystemExit("ABORT: %s does not match the build record" % dmp["file"])
    pos = nc_mesh.dump_floats(raw)
    prims = []
    k = 0
    for i, m in enumerate(st["meshes"]):
        pp = pos[k:k + m["points_count"]]
        if nc_mesh.sha256_bytes(nc_mesh.canonical_dump(pp)) != m["positions_f32_sha256"]:
            raise SystemExit("ABORT: dump slice for %s does not match the record" % m["prim_path"])
        prims.append({"mesh_index": i, "mesh_name": m["prim_path"], "primitive_index": 0,
                      "positions": pp, "triangle_count": m["triangle_count"],
                      "position_byte_offset": k * 12})
        k += m["points_count"]
    if k != len(pos):
        raise SystemExit("ABORT: dump length does not match the mesh records")
    tier2 = mesh_tier2(prims, datadir, "usdz-mesh-dump.f32",
                       provisional=CONTROLS_STATUS != "COMPLETE")
    tier2["dump_definition"] = USDZ_DUMP_DEF
    tier2["storage_order"] = "stage traversal order: " + ", ".join(dmp["order"])
    tier2["source_payload"] = ("all UsdGeom.Mesh points of the root layer %s (zip entry, CRC-32 "
                               "declared)" % rec["usdz"]["root_layer_entry"])
    tier2["accept_submesh_as_c5"] = False  # same rule as glTF and FBX (R5)
    # The mesh bytes sit inside a zip entry whose CRC-32 the file declares.
    tier2["integrity"] = ["crc32"]
    tier2["polygon_count"] = sum(m["face_count"] for m in st["meshes"])
    tier2["all_polygons_triangles"] = all(m["all_triangles"] for m in st["meshes"])
    tier2["cross_check"] = ("per mesh prim: points float32 sha256 and triangle count equal Blender's "
                            "mesh before export AND Blender's USD re-import of the usdz (build record "
                            "checks). Read with Blender's bundled USD %s." % rec["blender"]["pxr_usd_version"])
    layer = [e for e in entries if e["name"] == rec["usdz"]["root_layer_entry"]][0]
    return {
        "status": CONTROLS_STATUS,
        "fixture_files": [{"path": rel(fx, repo), "name": USDZ_NAME, "sha256": h,
                           "size": len(b), "role": "container"}],
        "payloads": payloads,
        "zip_entries": entries,
        "tier2_mesh": tier2,
        "absent_classes": ["sound"],  # D2: no sound in the controls
        "usd": {"root_layer_entry": rec["usdz"]["root_layer_entry"],
                "root_layer_encoding": rec["usdz"]["root_layer_encoding"],
                "root_layer_sha256": layer["sha256"], "root_layer_size": layer["size"],
                "root_layer_crc32": layer["crc32"],
                "up_axis": st["up_axis"], "meters_per_unit": st["meters_per_unit"],
                "default_prim": st["default_prim"], "mesh_prims": dmp["order"],
                "texture_asset_path": "@./textures/crate_diffuse.png@ (relative)"},
        "build": {"script": "build_gltf_usdz.py --format usdz + blender_export_nc.py",
                  "record": USDZ_RECORD,
                  "blender": rec["blender"]["pin"], "blender_build_hash": rec["blender"]["build_hash"],
                  "pxr_usd_version": rec["blender"]["pxr_usd_version"],
                  "env_pins": rec["blender"]["env_pins"],
                  "export_settings": rec["export_settings"],
                  "import_settings": rec["import_settings"], "scene_edits": rec["scene_edits"],
                  "inputs": rec["inputs"],
                  "determinism": {k2: v for k2, v in rec["determinism"].items() if k2 != "per_file"},
                  "leak_scan_hits": len(rec["leak_scan"]["hits"])},
        "notes": [
            "Tier 1 = the PNG zip entry only (sha256 as shipped). The usdc root layer is NOT "
            "a Tier 1 mesh payload: copying it out is not a mesh extraction. An agent "
            "reaches the mesh only by parsing usdc (binary crate); stdlib Python has no "
            "usdc reader. That is part of what this control measures.",
            "Tier 2 = canonical dump of the authored points, read by Blender's bundled "
            "USD library and cross-checked with Blender's re-import.",
            "The Tier 2 dump bytes equal the FBX control's dump (same Blender mesh, same "
            "object order lid, body, latch, Blender Z-up coordinates in both files).",
            "Integrity the file declares: zip CRC-32 per entry. It covers the PNG and the "
            "usdc layer that holds the mesh. Nothing cryptographic.",
            "USDZ builds are not byte-deterministic: the zip timestamps differ, and the mesh "
            "prim order in the stage varies between Blender runs. The fixture is "
            "single-build, hash-pinned.",
        ],
    }


def prompt_hashes(here):
    out = {}
    for payload in ("sound", "texture"):
        d = os.path.join(here, "prompts", payload)
        if not os.path.isdir(d):
            continue
        for n in sorted(os.listdir(d)):
            out["prompts/%s/%s" % (payload, n)] = nc_mesh.sha256_file(os.path.join(d, n))
    return out


def default_repo():
    for c in (os.path.join(HERE, "..", ".."), os.path.join(HERE, "..", "werk")):
        if os.path.exists(os.path.join(c, WERK_FIXTURE)):
            return os.path.normpath(c)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=default_repo())
    ap.add_argument("--out", default=os.path.join(HERE, "expectations.json"))
    args = ap.parse_args()
    if not args.repo:
        raise SystemExit("--repo is required (repo root containing %s)" % WERK_FIXTURE)
    datadir = os.path.join(os.path.dirname(os.path.abspath(args.out)), "expectations-data")

    formats = {
        "werk": build_werk(args.repo, datadir),
        "gltf": build_gltf(args.repo, HERE, datadir),
        "fbx": build_fbx(args.repo, HERE, datadir),
        "usdz": build_usdz(args.repo, HERE, datadir),
    }
    for k, v in formats.items():
        v["integrity_declared_by_file"] = INTEGRITY_TABLE[k]
        v["theoretical_verifiable_integrity_fraction"] = {
            c: theoretical_fraction(v, c) for c in ("sound", "texture")}
        if v.get("tier2_mesh") and v["tier2_mesh"].get("dump_file"):
            p = os.path.join(os.path.dirname(datadir), v["tier2_mesh"]["dump_file"])
            v["tier2_mesh"]["dump_file_sha256"] = nc_mesh.sha256_file(p)

    doc = {
        "round": "roundNC",
        "what": "ground truth for grade_nc.py; NEVER copy into an agent workspace",
        "repo_commit_basis": "6d547d0",
        "tolerance": nc_mesh.TOL,
        "integrity_table": {k: v["declares"] for k, v in INTEGRITY_TABLE.items()},
        "prompt_sha256": prompt_hashes(HERE),
        "formats": formats,
    }
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=2, sort_keys=False)
        f.write("\n")
    print("wrote %s" % args.out)
    for k, v in formats.items():
        t2 = v.get("tier2_mesh") or {}
        print("  %-5s %-10s payloads=%d tier2=%s missing=%d" % (
            k, v["status"], len(v.get("payloads", [])),
            "%dv/%dt" % (t2["vertex_count"], t2["triangle_count"]) if t2 else "-",
            len(v.get("missing_inputs", []))))
        for m in v.get("missing_inputs", []):
            print("        MISSING %s %s -> %s" % (m["kind"], m["uri"], m["expected_at"]))


if __name__ == "__main__":
    main()
