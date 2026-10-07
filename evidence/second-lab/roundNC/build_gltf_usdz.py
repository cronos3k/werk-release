#!/usr/bin/env python3
"""
build_gltf_usdz.py -- builds the roundNC glTF and USDZ control fixtures.

The FBX control is built by build_controls.py (unchanged). This script uses
the SAME inputs and the SAME Blender scene setup, so all three controls carry
the same mesh and the same texture bytes:

  mesh     fixtures/sources/crate-cc0/wooden_crate_01_2k.gltf (+ .bin), CC0
  texture  textures/crate-cc0-albedo.png from fixtures/crate-cc0-full-v1.werk,
           sha256 af85a84d..., extracted with zipfile and checked against that
           package's MANIFEST.json before use. Named crate_diffuse.png.

Outputs (copied into this directory):
  --format gltf   crate-nc-v1.gltf + crate-nc-v1.bin + crate_diffuse.png
                  (glTF Separate; the .gltf references both sidecars by
                  relative URI only)
  --format usdz   crate-nc-v1.usdz (one file; texture packaged inside; no sound)

Nothing is downloaded. Blender 4.2.1 LTS runs headless twice with identical
arguments. Run 1 is the fixture; run 2 only measures determinism.
The build runs in a NEUTRAL directory (default D:/build/<format>), with TEMP
and TMP pointed there too, so no user or repo path can enter the output.
Every output is then scanned for leaked strings.

Writes build/<format>-build-record.json (read by build_expectations.py).

Usage:
  py -3.13 build_gltf_usdz.py --format gltf [--build-dir D:/build/gltf]
  py -3.13 build_gltf_usdz.py --format usdz [--build-dir D:/build/usdz]
Exit code 0 only if every check passed.
"""

import argparse
import binascii
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nc_mesh  # noqa: E402
from build_controls import (BLENDER_DEFAULT, BLENDER_PIN, BLENDER_FLAGS, BLENDER_ENV,  # noqa: E402
                            GLTF_SRC, TEX_PKG, TEX_ENTRY, TEX_SHA256, TEX_NAME,
                            IMPORT_SETTINGS, default_repo, diff_ranges)

FIXTURE = {
    "gltf": ["crate-nc-v1.gltf", "crate-nc-v1.bin", TEX_NAME],
    "usdz": ["crate-nc-v1.usdz"],
}

# Every keyword that matters is set explicitly. Defaults of Blender 4.2.1 /
# io_scene_gltf2 4.2.60 are used for the rest (listed in the build record).
GLTF_EXPORT = {
    "check_existing": False,
    "export_format": "GLTF_SEPARATE",
    "export_texture_dir": "",          # PNG beside the .gltf
    "export_image_format": "AUTO",     # keep PNG
    "export_keep_originals": False,    # True would point the URI at the source path
    "export_copyright": "",
    "export_texcoords": True,
    "export_normals": True,
    "export_tangents": False,
    "export_materials": "EXPORT",
    "export_vertex_color": "MATERIAL",
    "export_attributes": False,
    "use_mesh_edges": False,
    "use_mesh_vertices": False,
    "export_cameras": False,
    "export_lights": False,
    "use_selection": False,
    "use_visible": False,
    "use_renderable": False,
    "use_active_collection": False,
    "use_active_scene": False,
    "export_extras": False,
    "export_yup": True,
    "export_apply": False,
    "export_shared_accessors": False,
    "export_animations": False,
    "export_skins": False,
    "export_morph": False,
    "export_draco_mesh_compression_enable": False,
    "export_use_gltfpack": False,
    "export_gpu_instances": False,
    "export_unused_images": False,
    "export_unused_textures": False,
}

USDZ_EXPORT = {
    "check_existing": False,
    "selected_objects_only": False,
    "visible_objects_only": False,
    "export_animation": False,
    "export_hair": False,
    "export_uvmaps": True,
    "rename_uvmaps": True,
    "export_mesh_colors": False,
    "export_normals": True,
    "export_materials": True,
    "export_subdivision": "IGNORE",
    "export_armatures": False,
    "only_deform_bones": False,
    "export_shapekeys": False,
    "use_instancing": False,
    "evaluation_mode": "RENDER",
    "generate_preview_surface": True,
    "generate_materialx_network": False,
    "convert_orientation": False,
    "export_textures": True,
    "overwrite_textures": True,
    "relative_paths": True,
    "xform_op_mode": "TRS",
    "root_prim_path": "/root",
    "export_custom_properties": False,
    "author_blender_name": False,
    "convert_world_material": False,
    "allow_unicode": False,
    "export_meshes": True,
    "export_lights": False,
    "export_cameras": False,
    "export_curves": False,
    "export_volumes": False,
    "triangulate_meshes": False,
    "usdz_downscale_size": "KEEP",
}

LEAK_WORDS = [b"werk", b"roundnc", b"staging", b"yuvra", b"gauntlet", b"users",
              b"appdata", b"\\build", b"/build", b"d:\\", b"d:/", b"c:\\", b"c:/"]
ABS_PATH = re.compile(rb"(?i)(?<![a-z0-9])[a-z]:[\\/]|\\\\[a-z0-9]|file://")


def sha(b):
    return hashlib.sha256(b).hexdigest()


def extract_texture(repo, dst):
    pkg = os.path.join(repo, TEX_PKG)
    with zipfile.ZipFile(pkg) as z:
        man = json.loads(z.read("MANIFEST.json"))
        data = z.read(TEX_ENTRY)
    declared = [f["sha256"] for n in man.get("nodes", []) for v in n.get("versions", [])
                for f in v.get("files", []) if f["path"] == TEX_ENTRY]
    if declared != [TEX_SHA256] or sha(data) != TEX_SHA256:
        raise SystemExit("ABORT: texture sha256 mismatch")
    w, h = struct.unpack(">II", data[16:24])
    with open(dst, "wb") as f:
        f.write(data)
    return data, {"package": TEX_PKG, "package_sha256": nc_mesh.sha256_file(pkg),
                  "entry": TEX_ENTRY, "manifest_sha256": declared[0], "sha256": sha(data),
                  "size": len(data), "png_size": [w, h], "written_as": TEX_NAME}


def blender_env(build):
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("PYTHON")}
    env.update(BLENDER_ENV)
    tmp = os.path.join(build, "tmp")
    os.makedirs(tmp, exist_ok=True)
    env["TEMP"] = env["TMP"] = env["TMPDIR"] = tmp
    return env


def run_blender(blender, repo, fmt, build, tex_path, run_tag):
    outdir = os.path.join(build, "out")
    shutil.rmtree(outdir, ignore_errors=True)
    os.makedirs(outdir)
    out = os.path.join(outdir, FIXTURE[fmt][0])
    rep = os.path.join(build, "blender-report-%s.json" % run_tag)
    a = {"format": fmt, "gltf": os.path.join(repo, GLTF_SRC), "texture": tex_path,
         "image_name": TEX_NAME, "out": out, "report": rep,
         "dump_dir": os.path.join(build, "dumps-" + run_tag),
         "reimport_dir": os.path.join(build, "reimport-" + run_tag),
         "reimport_files": FIXTURE[fmt],
         "import_settings": IMPORT_SETTINGS,
         "export_settings": GLTF_EXPORT if fmt == "gltf" else USDZ_EXPORT}
    ap = os.path.join(build, "blender-args.json")
    with open(ap, "w", encoding="utf-8", newline="\n") as f:
        json.dump(a, f, indent=2)
    argv = [blender] + BLENDER_FLAGS + ["--python", os.path.join(HERE, "blender_export_nc.py"), "--", ap]
    p = subprocess.run(argv, capture_output=True, timeout=900, env=blender_env(build))
    with open(os.path.join(build, "blender-%s.log" % run_tag), "wb") as f:
        f.write(p.stdout + b"\n--- stderr ---\n" + p.stderr)
    if p.returncode != 0 or not os.path.exists(out):
        raise SystemExit("ABORT: Blender run %s failed (exit %d), see %s"
                         % (run_tag, p.returncode, os.path.join(build, "blender-%s.log" % run_tag)))
    produced = sorted(os.listdir(outdir))
    files = {n: open(os.path.join(outdir, n), "rb").read() for n in produced
             if os.path.isfile(os.path.join(outdir, n))}
    with open(rep, encoding="utf-8") as f:
        return produced, files, json.load(f)


def text_like(label, b):
    return label.endswith((".gltf", ".usda")) or "usda text" in label


def leak_scan(blobs):
    """blobs: list of (label, bytes). Returns list of hits."""
    hits = []
    for label, b in blobs:
        low = b.lower()
        for w in LEAK_WORDS:
            i = low.find(w)
            if i >= 0:
                hits.append({"in": label, "string": w.decode(), "offset": i,
                             "context": b[max(0, i - 24): i + 40].decode("latin-1")})
        if not text_like(label, b):
            continue  # random binary (floats, deflate) would match by chance
        for m in ABS_PATH.finditer(b):
            hits.append({"in": label, "string": "absolute-path pattern", "offset": m.start(),
                         "context": b[max(0, m.start() - 24): m.start() + 40].decode("latin-1")})
    return hits


def read_dump(p):
    with open(p, "rb") as f:
        return nc_mesh.dump_floats(f.read())


def zip_entries(b):
    """USDZ rules: stored (no compression), data 64-byte aligned, CRC-32."""
    import io
    out = []
    with zipfile.ZipFile(io.BytesIO(b)) as z:
        bad = z.testzip()
        for i in z.infolist():
            # local header: 30 bytes + name + extra
            lh = i.header_offset
            nlen, xlen = struct.unpack_from("<HH", b, lh + 26)
            data_off = lh + 30 + nlen + xlen
            data = z.read(i.filename)
            out.append({"name": i.filename, "compress_type": i.compress_type,
                        "stored": i.compress_type == zipfile.ZIP_STORED,
                        "size": i.file_size, "crc32": "%08x" % i.CRC,
                        "crc32_recomputed": "%08x" % (binascii.crc32(data) & 0xFFFFFFFF),
                        "data_offset": data_off, "aligned_64": data_off % 64 == 0,
                        "sha256": sha(data), "magic": data[:8].decode("latin-1")})
    return out, bad


USD_DUMP = os.path.join(HERE, "build", "usdz-pxr-mesh-dump.f32")


def write_usd_dump(st):
    """Tier 2 source for the USDZ: the authored points of every UsdGeom.Mesh,
    in stage traversal order, as float32 LE (point3f is float32: lossless).
    Read by build_expectations.py, which re-checks it against the record."""
    parts = []
    for m in st["meshes"]:
        with open(m["positions_dump"], "rb") as f:
            b = f.read()
        if sha(b) != m["positions_f32_sha256"] or len(b) != 12 * m["points_count"]:
            raise SystemExit("ABORT: pxr dump of %s does not match its record" % m["prim_path"])
        parts.append(b)
    data = b"".join(parts)
    with open(USD_DUMP, "wb") as f:
        f.write(data)
    return {"file": "build/usdz-pxr-mesh-dump.f32", "sha256": sha(data), "size": len(data),
            "order": [m["prim_path"] for m in st["meshes"]]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--format", required=True, choices=["gltf", "usdz"])
    ap.add_argument("--repo", default=default_repo())
    ap.add_argument("--blender", default=BLENDER_DEFAULT)
    ap.add_argument("--build-dir", default=None)
    args = ap.parse_args()
    fmt = args.format
    build = os.path.abspath(args.build_dir or ("D:/build/" + fmt))
    for w in ("werk", "roundnc", "staging", "yuvra", "gauntlet"):
        if w in build.lower():
            raise SystemExit("ABORT: build dir %s is not neutral (contains %r)" % (build, w))
    shutil.rmtree(build, ignore_errors=True)
    os.makedirs(os.path.join(build, "src"))

    ver = subprocess.run([args.blender, "--version"], capture_output=True).stdout.decode("utf-8", "replace")
    ver_line = [l for l in ver.splitlines() if l.startswith("Blender ")][0].strip()
    if ver_line != "Blender " + BLENDER_PIN:
        raise SystemExit("ABORT: Blender is %r, pinned %r" % (ver_line, BLENDER_PIN))

    tex_path = os.path.join(build, "src", TEX_NAME)
    src_png, tex_rec = extract_texture(args.repo, tex_path)

    prod1, files1, rep1 = run_blender(args.blender, args.repo, fmt, build, tex_path, "run1")
    prod2, files2, rep2 = run_blender(args.blender, args.repo, fmt, build, tex_path, "run2")
    det = {"run1_files": prod1, "run2_files": prod2, "per_file": {}}
    for n in prod1:
        a, b = files1.get(n), files2.get(n)
        d = {"run1_sha256": sha(a), "run2_sha256": sha(b) if b is not None else None,
             "byte_identical": a == b}
        if b is not None and a != b:
            d["differing_ranges_offset_len"] = diff_ranges(a, b)
            d["sizes"] = [len(a), len(b)]
        det["per_file"][n] = d
    det["byte_identical"] = prod1 == prod2 and all(v["byte_identical"] for v in det["per_file"].values())

    checks = []

    def chk(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})
        return ok

    chk("output files are exactly %s" % FIXTURE[fmt], prod1 == sorted(FIXTURE[fmt]), str(prod1))

    # copy run-1 outputs into the round directory
    for n in FIXTURE[fmt]:
        with open(os.path.join(HERE, n), "wb") as f:
            f.write(files1[n])

    rec = {"fixture_files": [{"name": n, "sha256": sha(files1[n]), "size": len(files1[n])}
                             for n in FIXTURE[fmt]],
           "format": fmt, "build_dir": build}
    pre = rep1["blender_view_before_export"]
    post = rep1["blender_view_after_reimport"]
    blobs = [(n, files1[n]) for n in FIXTURE[fmt]]

    if fmt == "gltf":
        gpath = os.path.join(HERE, "crate-nc-v1.gltf")
        gl = json.loads(files1["crate-nc-v1.gltf"].decode("utf-8"))
        uris = [b.get("uri") for b in gl.get("buffers", [])] + [i.get("uri") for i in gl.get("images", [])]
        chk("buffers[].uri == ['crate-nc-v1.bin'] and images[].uri == ['%s']" % TEX_NAME,
            [b.get("uri") for b in gl.get("buffers", [])] == ["crate-nc-v1.bin"]
            and [i.get("uri") for i in gl.get("images", [])] == [TEX_NAME], str(uris))
        chk("every URI is relative (no scheme, no drive, no leading slash, no '..')",
            all(u and ":" not in u and not u.startswith(("/", "\\")) and ".." not in u for u in uris),
            str(uris))
        chk("sidecar PNG bytes == source PNG bytes (verbatim, not re-encoded)",
            files1[TEX_NAME] == src_png, "sha256 %s" % sha(files1[TEX_NAME]))
        chk("buffers[0].byteLength == size of crate-nc-v1.bin",
            gl["buffers"][0]["byteLength"] == len(files1["crate-nc-v1.bin"]),
            "%d vs %d" % (gl["buffers"][0]["byteLength"], len(files1["crate-nc-v1.bin"])))
        _, prims = nc_mesh.load_gltf_any(gpath)
        offs = [p["position_byte_offset"] for p in prims]
        rec["gltf"] = {"asset": gl.get("asset"), "extensionsUsed": gl.get("extensionsUsed", []),
                       "meshes": [{"name": m.get("name"), "primitives": len(m["primitives"])}
                                  for m in gl["meshes"]],
                       "nodes": [n.get("name") for n in gl.get("nodes", [])],
                       "materials": [m.get("name") for m in gl.get("materials", [])],
                       "images": gl.get("images"), "buffers": gl.get("buffers"),
                       "primitives": [{k: p[k] for k in ("mesh_index", "mesh_name", "primitive_index",
                                                         "triangle_count", "position_byte_offset")}
                                      | {"vertex_count": len(p["positions"])} for p in prims],
                       "storage_order_equals_byte_order": offs == sorted(offs)}
        nv = sum(len(p["positions"]) for p in prims)
        nt = sum(p["triangle_count"] for p in prims)
        rec["mesh_totals"] = {"vertex_count": nv, "triangle_count": nt}
        # Cross-check with Blender. glTF is Y-up: Blender (x, y, z) -> glTF (x, z, -y).
        # The exporter may split a Blender vertex into several glTF vertices
        # (one per distinct normal/UV); the ground truth then describes the
        # file as stored. So: triangles equal, distinct position SETS equal,
        # and every split is recorded.
        by_mesh = {x["mesh"]: x for x in pre}
        rec["gltf"]["vertex_split_vs_blender"] = []
        for p in prims:
            bp = by_mesh.get(p["mesh_name"])
            if not chk("glTF mesh %s has a Blender mesh of the same name" % p["mesh_name"], bp is not None):
                continue
            bpos = read_dump(bp["positions_dump"])
            conv = {(round(x, 6), round(z, 6), round(-y, 6)) for x, y, z in bpos}
            got = {(round(x, 6), round(y, 6), round(z, 6)) for x, y, z in p["positions"]}
            chk("glTF mesh %s triangles == Blender before export" % p["mesh_name"],
                bp["triangle_count"] == p["triangle_count"],
                "%d vs %d" % (p["triangle_count"], bp["triangle_count"]))
            chk("glTF mesh %s distinct positions == Blender's (axis converted, 1e-6)" % p["mesh_name"],
                conv == got, "%d vs %d distinct" % (len(got), len(conv)))
            rec["gltf"]["vertex_split_vs_blender"].append({
                "mesh": p["mesh_name"], "gltf_vertices": len(p["positions"]),
                "blender_vertices": bp["vertex_count"],
                "extra_vertices_from_split": len(p["positions"]) - bp["vertex_count"],
                "vertex_order_identical_to_blender":
                    [(x, z, -y) for x, y, z in bpos] == [tuple(v) for v in p["positions"]]})
        tot_re = sum(x["vertex_count"] for x in post)
        chk("Blender re-import of the glTF (3 files alone in a dir): same totals",
            tot_re == nv and sum(x["triangle_count"] for x in post) == nt,
            "%dv/%dt" % (tot_re, sum(x["triangle_count"] for x in post)))
        re_imgs = rep1["reimported_images"]
        chk("Blender re-import loads the PNG sidecar with the source bytes",
            any(i.get("file_sha256") == TEX_SHA256 or i.get("packed_sha256") == TEX_SHA256
                for i in re_imgs), json.dumps(re_imgs))
        chk("triangle total equals the FBX control (6576)", nt == 6576, "%dv/%dt" % (nv, nt))
        rec["mesh_totals"]["vs_fbx"] = ("FBX stores 4686 vertices / 6576 triangles. glTF stores %d / %d: "
                                        "the glTF exporter split %d vertices (distinct normal/UV per "
                                        "loop). Ground truth describes the glTF as stored." % (nv, nt, nv - 4686))
    else:
        ub = files1["crate-nc-v1.usdz"]
        ents, bad = zip_entries(ub)
        rec["usdz"] = {"zip_entries": ents, "testzip": bad}
        chk("zip CRC-32 of every entry holds (testzip)", bad is None, str(bad))
        chk("every entry stored (no compression) and 64-byte aligned (USDZ rule)",
            all(e["stored"] and e["aligned_64"] for e in ents),
            json.dumps([(e["name"], e["stored"], e["data_offset"]) for e in ents]))
        layer = ents[0]
        is_usdc = layer["magic"].startswith("PXR-USDC")
        rec["usdz"]["root_layer_entry"] = layer["name"]
        rec["usdz"]["root_layer_encoding"] = "usdc (binary crate)" if is_usdc else (
            "usda (text)" if layer["name"].lower().endswith(".usda") or layer["magic"].startswith("#usda")
            else "unknown: magic %r" % layer["magic"])
        chk("first entry is the root layer (.usd/.usdc/.usda)",
            os.path.splitext(layer["name"])[1].lower() in (".usd", ".usdc", ".usda"), layer["name"])
        pngs = [e for e in ents if e["name"].lower().endswith(".png")]
        chk("exactly one PNG entry, bytes == source PNG (verbatim)",
            len(pngs) == 1 and pngs[0]["sha256"] == TEX_SHA256,
            json.dumps([(e["name"], e["sha256"][:16], e["size"]) for e in pngs]))
        chk("no audio entry (D2: no sound)", not any(
            e["name"].lower().endswith((".wav", ".mp3", ".m4a", ".aac")) for e in ents))
        st = rep1["pxr_stage"]
        st2 = rep2["pxr_stage"]
        det["usd_mesh_prim_order_run1"] = [m["prim_path"] for m in st["meshes"]]
        det["usd_mesh_prim_order_run2"] = [m["prim_path"] for m in st2["meshes"]]
        det["usd_same_meshes_ignoring_order"] = (
            sorted((m["prim_path"], m["positions_f32_sha256"]) for m in st["meshes"])
            == sorted((m["prim_path"], m["positions_f32_sha256"]) for m in st2["meshes"]))
        det["usd_same_prim_order"] = det["usd_mesh_prim_order_run1"] == det["usd_mesh_prim_order_run2"]
        det["usd_png_entry_identical"] = (
            [e["sha256"] for e in zip_entries(files2["crate-nc-v1.usdz"])[0] if e["name"].endswith(".png")]
            == [e["sha256"] for e in zip_entries(ub)[0] if e["name"].endswith(".png")])
        chk("run 2 holds the same meshes and the same PNG (prim order may differ)",
            det["usd_same_meshes_ignoring_order"] and det["usd_png_entry_identical"],
            "prim order same: %s" % det["usd_same_prim_order"])
        rec["usdz"]["pxr_stage"] = {k: v for k, v in st.items() if k != "root_layer_as_usda"}
        rec["usdz"]["pxr_stage"]["meshes"] = [{k: v for k, v in m.items() if k != "positions_dump"}
                                              for m in st["meshes"]]
        # The usdc string tables can be compressed, so scan the text form too.
        usda_text = st["root_layer_as_usda"].encode("utf-8")
        blobs.append(("root layer exported to usda text by pxr", usda_text))
        for e in ents:
            import io
            with zipfile.ZipFile(io.BytesIO(ub)) as z:
                blobs.append(("usdz!" + e["name"], z.read(e["name"])))
        nv = sum(m["points_count"] for m in st["meshes"])
        nt = sum(m["triangle_count"] for m in st["meshes"])
        rec["mesh_totals"] = {"vertex_count": nv, "triangle_count": nt}
        chk("all USD mesh faces are triangles", all(m["all_triangles"] for m in st["meshes"]))
        chk("points are float3 (point3f[])", all(m["points_type"] in ("point3f[]", "float3[]")
                                                for m in st["meshes"]),
            str([m["points_type"] for m in st["meshes"]]))
        pre_by_sha = {x["positions_f32_sha256"]: x for x in pre}
        for m in st["meshes"]:
            bp = pre_by_sha.get(m["positions_f32_sha256"])
            chk("USD mesh %s points == Blender mesh before export (same order, float32 bytes)"
                % m["prim_path"], bp is not None and bp["triangle_count"] == m["triangle_count"],
                bp and bp["mesh"] or "no match")
        post_by_sha = {x["positions_f32_sha256"]: x for x in post}
        for m in st["meshes"]:
            rp = post_by_sha.get(m["positions_f32_sha256"])
            chk("USD mesh %s points == Blender re-import of the usdz (alone in a dir)"
                % m["prim_path"], rp is not None and rp["triangle_count"] == m["triangle_count"],
                rp and rp["object"] or "no match")
        re_imgs = rep1["reimported_images"]
        chk("Blender re-import of the usdz finds the same PNG bytes",
            any(i.get("file_sha256") == TEX_SHA256 or i.get("packed_sha256") == TEX_SHA256
                for i in re_imgs), json.dumps(re_imgs))
        chk("totals equal the FBX control (4686 v / 6576 t)", (nv, nt) == (4686, 6576),
            "%dv/%dt" % (nv, nt))
        rec["usdz"]["pxr_mesh_dump"] = write_usd_dump(st)
        rec["usdz"]["root_layer_usda_excerpt"] = st["root_layer_as_usda"][:6000]

    hits = leak_scan(blobs)
    rec["leak_scan"] = {"strings": [w.decode() for w in LEAK_WORDS],
                        "absolute_path_regex": ABS_PATH.pattern.decode(),
                        "scanned": [l for l, _ in blobs], "hits": hits}
    chk("leak scan: 0 hits in every output (and in the usda text form)", not hits,
        json.dumps(hits)[:400])

    rec.update({
        "blender": {"pin": BLENDER_PIN, "exe": args.blender, "version_output": ver.strip().splitlines(),
                    "bpy_version_string": rep1["blender_version"],
                    "build_hash": rep1["blender_build_hash"], "build_date": rep1["blender_build_date"],
                    "addons": rep1["addons"], "pxr_usd_version": rep1.get("pxr_usd_version"),
                    "argv": BLENDER_FLAGS + ["--python", "blender_export_nc.py", "--", "<args.json>"],
                    "env_pins": dict(BLENDER_ENV, TEMP="<build>/tmp", TMP="<build>/tmp")},
        "inputs": {"gltf": GLTF_SRC,
                   "gltf_sha256": nc_mesh.sha256_file(os.path.join(args.repo, GLTF_SRC)),
                   "bin_sha256": nc_mesh.sha256_file(os.path.join(args.repo, os.path.dirname(GLTF_SRC),
                                                                  "wooden_crate_01.bin")),
                   "texture": tex_rec},
        "import_settings": IMPORT_SETTINGS,
        "export_settings": GLTF_EXPORT if fmt == "gltf" else USDZ_EXPORT,
        "scene_edits": ["read_factory_settings(use_empty=True)",
                        "all glTF-imported materials and images removed (the 3 JPEGs are not in the repo)",
                        "one material 'crate_wood': Principled BSDF Base Color <- Image Texture(%s)" % TEX_NAME,
                        "material assigned to all 3 mesh objects",
                        "identical to blender_export_fbx.py (the FBX control)"],
        "blender_view_before_export": [{k: v for k, v in x.items() if k != "positions_dump"} for x in pre],
        "blender_view_after_reimport": [{k: v for k, v in x.items() if k != "positions_dump"} for x in post],
        "reimported_images": rep1["reimported_images"],
        "determinism": det,
        "checks": checks,
        "all_checks_ok": all(c["ok"] for c in checks),
    })
    os.makedirs(os.path.join(HERE, "build"), exist_ok=True)
    recp = os.path.join(HERE, "build", "%s-build-record.json" % fmt)
    with open(recp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rec, f, indent=2)
        f.write("\n")
    for ff in rec["fixture_files"]:
        print("%-20s sha256 %s  %d B" % (ff["name"], ff["sha256"], ff["size"]))
    print("mesh totals: %s" % rec["mesh_totals"])
    if fmt == "usdz":
        print("root layer: %s (%s)" % (rec["usdz"]["root_layer_entry"], rec["usdz"]["root_layer_encoding"]))
    print("determinism: byte_identical=%s" % det["byte_identical"])
    for c in checks:
        print("  %-4s %s  %s" % ("OK" if c["ok"] else "BAD", c["check"], c["detail"][:160]))
    sys.exit(0 if rec["all_checks_ok"] else 1)


if __name__ == "__main__":
    main()
