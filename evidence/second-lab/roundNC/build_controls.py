#!/usr/bin/env python3
"""
build_controls.py -- builds the roundNC control fixtures (plan section 1.2).

Builds the FBX control only. glTF and USDZ: build_gltf_usdz.py (same inputs,
same scene setup).
  crate-nc-v1.fbx   one binary FBX, CC0 crate mesh + one embedded PNG texture.

Inputs (all CC0, all in the repo, read-only):
  mesh     fixtures/sources/crate-cc0/wooden_crate_01_2k.gltf (+ .bin)
           Poly Haven "Wooden Crate 01". Its three JPEG textures are not
           vendored; the importer leaves those slots empty and they are dropped.
  texture  textures/crate-cc0-albedo.png from fixtures/crate-cc0-full-v1.werk
           (the deterministic procedural albedo of build_crate_cc0.py). It is
           extracted with zipfile and checked against that package's
           MANIFEST.json sha256 before use. Pinned below.

Steps:
  1. Extract and verify the albedo PNG -> build/fbx/crate_diffuse.png.
  2. Run Blender (pinned 4.2.1 LTS) headless twice with identical arguments
     and the same output path. Run 1 becomes crate-nc-v1.fbx, run 2 is kept as
     build/fbx/run2.fbx. Record whether the bytes are identical, and if not,
     where they differ.
  3. Parse the FBX in stdlib (nc_fbx.py): the embedded Video/Content blob must
     equal the source PNG bytes; geometry counts and position dumps must equal
     Blender's own view (before export and after re-import).
  4. Write build/fbx-build-record.json (pins, settings, results).

Usage:
  py -3.13 build_controls.py [--repo D:/werk/werk] [--blender <exe>]
Exit code 0 only if every check passed.
"""

import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nc_fbx  # noqa: E402

BLENDER_DEFAULT = "C:/Program Files/Blender Foundation/Blender 4.2/blender.exe"
BLENDER_PIN = "4.2.1 LTS"

GLTF_SRC = "fixtures/sources/crate-cc0/wooden_crate_01_2k.gltf"
TEX_PKG = "fixtures/crate-cc0-full-v1.werk"
TEX_ENTRY = "textures/crate-cc0-albedo.png"
TEX_SHA256 = "af85a84d80b8fee7bf413a5edc2e722f4442df09a5d2d064d8b16dfb0a51ec1f"
TEX_NAME = "crate_diffuse.png"  # same name the plan uses for the glTF control

FBX_NAME = "crate-nc-v1.fbx"
BUILD = os.path.join(HERE, "build", "fbx")
RECORD = os.path.join(HERE, "build", "fbx-build-record.json")  # read by build_expectations.py

IMPORT_SETTINGS = {
    "merge_vertices": False,          # keep glTF vertices 1:1 (no welding)
    "import_shading": "NORMALS",
    "bone_heuristic": "BLENDER",
    "guess_original_bind_pose": True,
    "import_pack_images": True,
}

# Every bpy.ops.export_scene.fbx keyword in Blender 4.2, set explicitly.
EXPORT_SETTINGS = {
    "check_existing": False,
    "use_selection": False,
    "use_visible": False,
    "use_active_collection": False,
    "collection": "",
    "global_scale": 1.0,
    "apply_unit_scale": True,
    "apply_scale_options": "FBX_SCALE_NONE",
    "use_space_transform": True,
    "bake_space_transform": False,
    "object_types": ["MESH"],
    "use_mesh_modifiers": True,
    "use_mesh_modifiers_render": True,
    "mesh_smooth_type": "OFF",
    "colors_type": "SRGB",
    "prioritize_active_color": False,
    "use_subsurf": False,
    "use_mesh_edges": False,
    "use_tspace": False,
    "use_triangles": False,
    "use_custom_props": False,
    "add_leaf_bones": False,
    "primary_bone_axis": "Y",
    "secondary_bone_axis": "X",
    "use_armature_deform_only": False,
    "armature_nodetype": "NULL",
    "bake_anim": False,
    "path_mode": "COPY",
    "embed_textures": True,
    "batch_mode": "OFF",
    "use_batch_own_dir": False,
    "use_metadata": True,
    "axis_forward": "-Z",
    "axis_up": "Y",
}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def sha_file(p):
    with open(p, "rb") as f:
        return sha(f.read())


def default_repo():
    for c in (os.path.join(HERE, "..", ".."), os.path.join(HERE, "..", "werk")):
        if os.path.exists(os.path.join(c, GLTF_SRC)):
            return os.path.normpath(c)
    return None


def extract_texture(repo):
    pkg = os.path.join(repo, TEX_PKG)
    with zipfile.ZipFile(pkg) as z:
        man = json.loads(z.read("MANIFEST.json"))
        data = z.read(TEX_ENTRY)
    declared = [f["sha256"] for n in man.get("nodes", []) for v in n.get("versions", [])
                for f in v.get("files", []) if f["path"] == TEX_ENTRY]
    if declared != [TEX_SHA256] or sha(data) != TEX_SHA256:
        raise SystemExit("ABORT: %s!%s sha256 %s, MANIFEST declares %s, pinned %s"
                         % (TEX_PKG, TEX_ENTRY, sha(data), declared, TEX_SHA256))
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit("ABORT: texture is not a PNG")
    w, h = struct.unpack(">II", data[16:24])
    out = os.path.join(BUILD, TEX_NAME)
    with open(out, "wb") as f:
        f.write(data)
    return out, {"package": TEX_PKG, "package_sha256": sha_file(pkg), "entry": TEX_ENTRY,
                 "manifest_sha256": declared[0], "sha256": sha(data), "size": len(data),
                 "png_size": [w, h], "written_as": TEX_NAME}


# The FBX exporter derives object UIDs from Python hash() of string keys
# (io_scene_fbx/fbx_utils.py _key_to_uuid). String hashing is randomized per
# process unless PYTHONHASHSEED is fixed, and Blender ignores the environment
# unless --python-use-system-env is given. So: pass that flag with a minimal
# environment (no PYTHON* variables except the two below).
BLENDER_FLAGS = ["--background", "--factory-startup", "--python-use-system-env",
                 "--python-exit-code", "1"]
BLENDER_ENV = {"PYTHONHASHSEED": "0", "PYTHONNOUSERSITE": "1"}


def blender_env():
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("PYTHON")}
    env.update(BLENDER_ENV)
    return env


def run_blender(blender, repo, tex_path, run_tag):
    out_fbx = os.path.join(BUILD, FBX_NAME)  # same path every run
    if os.path.exists(out_fbx):
        os.remove(out_fbx)
    rep = os.path.join(BUILD, "blender-report-%s.json" % run_tag)
    a = {"gltf": os.path.join(repo, GLTF_SRC), "texture": tex_path, "image_name": TEX_NAME,
         "out_fbx": out_fbx, "report": rep, "import_settings": IMPORT_SETTINGS,
         "reimport_dir": os.path.join(BUILD, "reimport-" + run_tag),
         "export_settings": EXPORT_SETTINGS}
    ap = os.path.join(BUILD, "blender-args.json")
    with open(ap, "w", encoding="utf-8", newline="\n") as f:
        json.dump(a, f, indent=2)
    argv = [blender] + BLENDER_FLAGS + ["--python", os.path.join(HERE, "blender_export_fbx.py"), "--", ap]
    p = subprocess.run(argv, capture_output=True, timeout=600, env=blender_env())
    with open(os.path.join(BUILD, "blender-%s.log" % run_tag), "wb") as f:
        f.write(p.stdout + b"\n--- stderr ---\n" + p.stderr)
    if p.returncode != 0 or not os.path.exists(out_fbx):
        raise SystemExit("ABORT: Blender run %s failed (exit %d), see build/fbx/blender-%s.log"
                         % (run_tag, p.returncode, run_tag))
    with open(rep, encoding="utf-8") as f:
        return out_fbx, json.load(f)


def diff_ranges(a, b, limit=50):
    rng = []
    n = min(len(a), len(b))
    i = 0
    while i < n and len(rng) < limit:
        if a[i] != b[i]:
            j = i
            while j < n and a[j] != b[j]:
                j += 1
            rng.append([i, j - i])
            i = j
        else:
            i += 1
    return rng


def main():
    global BUILD
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=default_repo())
    ap.add_argument("--blender", default=BLENDER_DEFAULT)
    ap.add_argument("--build-dir", default=BUILD,
                    help="Blender work dir. Its ABSOLUTE path is written into the FBX "
                         "(Texture/Video FileName), so the bytes depend on it.")
    args = ap.parse_args()
    BUILD = os.path.abspath(args.build_dir)
    if not args.repo:
        raise SystemExit("--repo is required")
    os.makedirs(BUILD, exist_ok=True)

    ver = subprocess.run([args.blender, "--version"], capture_output=True).stdout.decode("utf-8", "replace")
    ver_line = [l for l in ver.splitlines() if l.startswith("Blender ")][0].strip()
    if ver_line != "Blender " + BLENDER_PIN:
        raise SystemExit("ABORT: Blender is %r, pinned %r" % (ver_line, BLENDER_PIN))

    tex_path, tex_rec = extract_texture(args.repo)
    src_png = open(tex_path, "rb").read()

    # two identical runs, same output path
    fbx1, rep1 = run_blender(args.blender, args.repo, tex_path, "run1")
    b1 = open(fbx1, "rb").read()
    final = os.path.join(HERE, FBX_NAME)
    shutil.copyfile(fbx1, final)
    fbx2, rep2 = run_blender(args.blender, args.repo, tex_path, "run2")
    b2 = open(fbx2, "rb").read()
    shutil.copyfile(fbx2, os.path.join(BUILD, "run2.fbx"))
    os.remove(fbx2)

    d1 = nc_fbx.describe(b1)
    d2 = nc_fbx.describe(b2)
    same = b1 == b2
    det = {"run1_sha256": sha(b1), "run2_sha256": sha(b2), "run1_size": len(b1),
           "run2_size": len(b2), "byte_identical": same}
    if not same:
        rng = diff_ranges(b1, b2)
        det["differing_ranges_offset_len"] = rng
        det["differing_bytes_total"] = sum(l for _, l in rng)
        s0, s1 = nc_fbx.node_span(b1, ["FBXHeaderExtension", "CreationTimeStamp"])
        det["creation_timestamp_span"] = [s0, s1]
        det["all_differences_inside_CreationTimeStamp"] = (
            len(b1) == len(b2) and all(s0 <= o and o + l <= s1 for o, l in rng))
        det["header_run1"] = d1["header"]
        det["header_run2"] = d2["header"]
        # Is everything except the differing ranges equal, and is the
        # geometry/texture content equal?
        det["content_equal"] = (
            [g["positions"] for g in d1["geometries"]] == [g["positions"] for g in d2["geometries"]]
            and [v["content"] for v in d1["videos"]] == [v["content"] for v in d2["videos"]])

    checks = []

    def chk(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    vids = [v for v in d1["videos"] if v["content"]]
    chk("exactly one Video node with Content", len(vids) == 1, "%d videos" % len(d1["videos"]))
    v = vids[0]
    chk("embedded Content == source PNG bytes (verbatim, not re-encoded)",
        v["content"] == src_png, "sha256 %s, %d B" % (sha(v["content"]), len(v["content"])))
    chk("Content blob occurs exactly once in the file", b1.count(src_png) == 1,
        "offset %d" % v["content_offset"])
    chk("Content offset points at the PNG bytes",
        b1[v["content_offset"]: v["content_offset"] + len(src_png)] == src_png)
    re_imgs = [i for i in rep1["reimported_images"] if i["packed"]]
    chk("Blender re-import (FBX alone in its dir) packs the same bytes from Content",
        len(re_imgs) >= 1 and all(i["packed_sha256"] == sha(src_png) for i in re_imgs)
        and len(re_imgs) == len(rep1["reimported_images"]),
        json.dumps(rep1["reimported_images"]))

    geoms = d1["geometries"]
    chk("float64 -> float32 positions lossless", all(g["f64_to_f32_lossless"] for g in geoms))

    def by_mesh_name(view):
        return {x["mesh"]: x for x in view}

    pre = by_mesh_name(rep1["blender_view_before_export"])
    post = {x["object"]: x for x in rep1["blender_view_after_reimport"]}
    for g in geoms:
        dump = b"".join(struct.pack("<3f", *p) for p in g["positions"])
        gs = sha(dump)
        bp = pre.get(g["name"])
        chk("geometry %s vs Blender before export" % g["name"],
            bp is not None and bp["vertex_count"] == len(g["positions"])
            and bp["triangle_count"] == g["triangle_count"]
            and bp["polygon_count"] == g["polygon_count"]
            and bp["positions_f32_sha256"] == gs,
            "fbx %dv/%dp/%dt; blender %s" % (len(g["positions"]), g["polygon_count"],
                                             g["triangle_count"],
                                             bp and "%dv/%dp/%dt" % (bp["vertex_count"], bp["polygon_count"], bp["triangle_count"])))
        # re-imported objects keep the Model name; match by vertex dump
        match = [x for x in post.values() if x["positions_f32_sha256"] == gs]
        chk("geometry %s vs Blender re-import of the FBX" % g["name"],
            len(match) == 1 and match[0]["vertex_count"] == len(g["positions"])
            and match[0]["triangle_count"] == g["triangle_count"],
            match and match[0]["object"] or "no match")

    rec = {
        "fixture": FBX_NAME,
        "build_dir": BUILD,
        "sha256": sha(b1), "size": len(b1),
        "blender": {"pin": BLENDER_PIN, "exe": args.blender, "version_output": ver.strip().splitlines(),
                    "bpy_version_string": rep1["blender_version"],
                    "build_hash": rep1["blender_build_hash"], "build_date": rep1["blender_build_date"],
                    "addons": rep1["addons"],
                    "argv": BLENDER_FLAGS + ["--python", "blender_export_fbx.py", "--", "<args.json>"],
                    "env_pins": BLENDER_ENV},
        "inputs": {"gltf": GLTF_SRC, "gltf_sha256": sha_file(os.path.join(args.repo, GLTF_SRC)),
                   "bin_sha256": sha_file(os.path.join(args.repo, os.path.dirname(GLTF_SRC), "wooden_crate_01.bin")),
                   "texture": tex_rec},
        "import_settings": IMPORT_SETTINGS,
        "export_settings": EXPORT_SETTINGS,
        "scene_edits": ["read_factory_settings(use_empty=True)",
                        "all glTF-imported materials and images removed (the 3 JPEGs are not in the repo)",
                        "one material 'crate_wood': Principled BSDF Base Color <- Image Texture(%s)" % TEX_NAME,
                        "material assigned to all 3 mesh objects"],
        "blender_imported_images_before_cleanup": rep1["imported_images_before_cleanup"],
        "fbx_version": d1["version"], "fbx_header": d1["header"], "fbx_top_level": d1["top_level"],
        "video": {"name": v["name"], "filename": v["filename"], "relative_filename": v["relative_filename"],
                  "content_sha256": sha(v["content"]), "content_size": len(v["content"]),
                  "content_offset": v["content_offset"]},
        "geometries": [{k: g[k] for k in ("name", "offset", "polygon_count", "triangle_count",
                                         "polygon_vertex_index_count", "f64_to_f32_lossless")}
                       | {"vertex_count": len(g["positions"])} for g in geoms],
        "blender_view_before_export": rep1["blender_view_before_export"],
        "blender_view_after_reimport": rep1["blender_view_after_reimport"],
        "determinism": det,
        "checks": checks,
        "all_checks_ok": all(c["ok"] for c in checks),
    }
    with open(RECORD, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rec, f, indent=2)
        f.write("\n")
    print("crate-nc-v1.fbx  sha256 %s  %d B" % (rec["sha256"], rec["size"]))
    print("determinism: byte_identical=%s" % same)
    if not same:
        print("  differing ranges (offset, len): %s" % det["differing_ranges_offset_len"])
        print("  content_equal: %s" % det["content_equal"])
        print("  all differences inside CreationTimeStamp %s: %s" % (
            det["creation_timestamp_span"], det["all_differences_inside_CreationTimeStamp"]))
    for c in checks:
        print("  %-4s %s  %s" % ("OK" if c["ok"] else "BAD", c["check"], c["detail"][:120]))
    sys.exit(0 if rec["all_checks_ok"] else 1)


if __name__ == "__main__":
    main()
