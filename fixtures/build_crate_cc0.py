#!/usr/bin/env python3
"""build_crate_cc0.py — the PUBLIC-DOMAIN crate fixtures.

    python fixtures/build_crate_cc0.py --variant lean
    python fixtures/build_crate_cc0.py --variant full
    python fixtures/build_crate_cc0.py --variant lean --check-determinism

Why these fixtures exist
------------------------
`fixtures/crate-v1.werk` (the golden crate) and `fixtures/crate-tex-v1.werk`
(the textured crate) are both built from PRIVATE assets: a real splat-foley run
and the golden crate's own game mesh. That makes the gate suite depend on files
that cannot be published. These two fixtures are CC0/public-domain stand-ins so
the whole conformance path is reproducible by anyone with only this repository:

  * `crate-cc0-lean-v1.werk`  — the smallest fixture that still exercises every
    mechanism a crate gate checks: multi-node load, round-trip byte identity,
    a damaged variant that degrades to an EXACT dead/skipped report while the
    signature stays valid, standalone parsing by the bootstrap reader, blob
    extraction, and `primary.mesh` resolution.
  * `crate-cc0-full-v1.werk`  — lean PLUS synthetic content that structurally
    echoes the golden crate: a deterministic synthetic AUDIO effect, two
    procedural "evidence" preview PNGs (x.* nodes a core reader skips),
    hand-authored facet tags (core.semantics) and simulation properties
    (core.props).

Each has a `-damaged` sibling built the way build_golden.py builds its own:
the unknown-type node goes in BEFORE signing (so the chain is valid), and one
payload byte is flipped AFTER signing (so the damage is caught by the per-file
hash and NOT by the signature — corrupting a payload must not invalidate the
chain).

Provenance of the geometry
--------------------------
The mesh is Poly Haven's "Wooden Crate 01", CC0 1.0
(https://polyhaven.com/a/wooden_crate_01). Its glTF+bin live verbatim in
`fixtures/sources/crate-cc0/`. `geometry/source.glb` is that mesh packed into a
GLB with nothing stripped but the (external) texture references; `geometry/
game.glb` merges its three primitives into one conformant single-primitive mesh
(POSITION + NORMAL + TEXCOORD_0) via `pipeline/glb.py`'s `build_glb`.

The three `core.tex` maps are NOT the Poly Haven photographic JPEGs — they are
the deterministic stdlib-Python maps from `build_crate_tex.py` (albedo/normal/
metallic-roughness), so the whole build stays byte-reproducible and small, and
everything in the package is CC0/public-domain. The embedded LICENSE is CC0 1.0
with a courtesy NOTICE crediting Poly Haven.

Determinism is mandatory: a fixed CREATED timestamp (reused from build_golden),
no wall clock in any payload, byte-identical across two runs. `--check-
determinism` builds twice and compares.

This file reuses build_golden.py and build_crate_tex.py rather than re-deriving
their helpers, so five fixture builders cannot disagree about zip framing,
hashing, signing, the minimal enclosing sphere, or a plank grain.
"""

import argparse
import json
import math
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)                         # build_golden, build_crate_tex
sys.path.insert(0, ROOT)                         # pipeline
sys.path.insert(0, os.path.join(ROOT, "tools"))  # spec_sha256, payload_file

# THE template. Reused verbatim so the two builders cannot drift apart.
import build_golden as G                                              # noqa: E402
from loader_caps import loader_capabilities        # noqa: E402
from build_golden import (sha256, jbytes, input_hash, png_info,       # noqa: E402
                          wav_info, glb_write, accessor, vertex_normals,
                          mesh_stats, welzl, write_zip, sign, CREATED, DEV_SK)
from build_crate_tex import (height_field, albedo_rows, normal_rows,  # noqa: E402
                             mr_rows, write_png, TEX_SIZE)
from spec_sha256 import spec_sha256_of_files                          # noqa: E402
from payload_file import annotate_payload_files                       # noqa: E402
from edge_targets import refuse_dangling_requires                     # noqa: E402
from pipeline.glb import build_glb                                    # noqa: E402

SRC_DEFAULT = os.path.join(HERE, "sources", "crate-cc0")

# Fixed, published, not secret — same doctrine as build_golden's DEV_KEY.
UUID = {
    "lean": "c1a0b2d3-4e5f-4a6b-8c7d-0e1f2a3b4c5d",
    "full": "d2b1c3e4-5f60-4b7c-9d8e-1f2a3b4c5d6e",
}

PREVIEW_ONE_SHOT = "audio/sfx/crate-cc0-click.wav"   # full variant only

ENTRY_ORDER = {
    "lean": [
        "MANIFEST.json", "SIGNATURE.json", "LICENSE", "README.txt",
        "loaders/", "spec/",
        "materials/", "textures/", "physics/", "disclosure/",
        "provenance/", "geometry/", "x/",
    ],
    "full": [
        "MANIFEST.json", "SIGNATURE.json", "LICENSE", "README.txt",
        "loaders/", "spec/", "semantics/", PREVIEW_ONE_SHOT,
        "materials/", "textures/", "physics/", "properties/", "disclosure/",
        "provenance/", "geometry/", "audio/", "x/",
    ],
}

# Everything at or before this index is the browsable tier (law 9). Lean ends
# at spec/ (it has no preview one-shot); full ends at the audio one-shot.
def preview_set(variant):
    eo = ENTRY_ORDER[variant]
    end = (eo.index(PREVIEW_ONE_SHOT) if variant == "full" else eo.index("spec/"))
    return eo[:end + 1]


# ---------------------------------------------------------------------------
# entry ordering (same shape as build_golden, but per-variant)
# ---------------------------------------------------------------------------

def order_entries(paths, entry_order):
    remaining = sorted(paths)
    out = []
    for pat in entry_order:
        picked = [p for p in remaining
                  if (p.startswith(pat) if pat.endswith("/") else p == pat)]
        for p in picked:
            remaining.remove(p)
            out.append(p)
    return out + remaining


def is_preview(name, pset):
    return any(name.startswith(p) if p.endswith("/") else name == p for p in pset)


# ---------------------------------------------------------------------------
# deterministic synthetic audio — a decaying wooden-crate "click"
# ---------------------------------------------------------------------------

def make_click_wav(sample_rate=48000, seconds=0.35):
    """A short 16-bit PCM mono impact: a fast transient plus three decaying
    resonant modes. A pure function of its parameters — no randomness, no wall
    clock — so the WAV bytes are the same on every run."""
    n = int(sample_rate * seconds)
    modes = [(196.0, 7.0, 1.00), (431.0, 11.0, 0.55), (912.0, 18.0, 0.30)]
    vals, peak = [], 0.0
    for i in range(n):
        t = i / float(sample_rate)
        s = math.exp(-400.0 * t) * 0.6            # broadband attack transient
        for f, decay, amp in modes:
            s += amp * math.exp(-decay * t) * math.sin(2.0 * math.pi * f * t)
        vals.append(s)
        peak = max(peak, abs(s))
    peak = peak or 1.0
    body = bytearray()
    for s in vals:
        body += struct.pack("<h", int(max(-1.0, min(1.0, 0.9 * s / peak)) * 32767))
    data = bytes(body)
    fmt = struct.pack("<HHIIHH", 1, 1, sample_rate, sample_rate * 2, 2, 16)
    out = b"RIFF" + struct.pack("<I", 4 + 8 + len(fmt) + 8 + len(data)) + b"WAVE"
    out += b"fmt " + struct.pack("<I", len(fmt)) + fmt
    out += b"data" + struct.pack("<I", len(data)) + data
    return out


# ---------------------------------------------------------------------------
# geometry: parse the CC0 glTF+bin, write a verbatim source GLB and a merged
# conformant game GLB
# ---------------------------------------------------------------------------

def load_source(src_dir):
    with open(os.path.join(src_dir, "wooden_crate_01_2k.gltf"), encoding="utf-8") as fh:
        js = json.load(fh)
    with open(os.path.join(src_dir, "wooden_crate_01.bin"), "rb") as fh:
        bin_ = fh.read()
    return js, bin_


def build_source_glb(js, bin_):
    """The Poly Haven mesh, verbatim geometry, in one self-contained GLB.

    The .bin becomes the BIN chunk (its buffer URI dropped) and the material /
    texture / image / sampler tables are stripped — they reference external
    JPEGs this fixture does not carry and does not use. Accessors, bufferViews
    and the three primitives are kept exactly as the artist exported them, so
    this is the anchor every derivation is checked against."""
    meshes = []
    for m in js["meshes"]:
        prims = [{"attributes": dict(p["attributes"]),
                  "indices": p["indices"], "mode": p.get("mode", 4)}
                 for p in m["primitives"]]
        meshes.append({"name": m.get("name", "mesh"), "primitives": prims})
    src_js = {
        "asset": {"version": "2.0",
                  "generator": "werk fixtures/build_crate_cc0.py "
                               "(Poly Haven Wooden Crate 01, CC0)"},
        "scene": 0,
        "scenes": [{"nodes": list(range(len(js["nodes"])))}],
        "nodes": [{"name": nd.get("name", "node"), "mesh": nd["mesh"]}
                  for nd in js["nodes"]],
        "meshes": meshes,
        "accessors": js["accessors"],
        "bufferViews": js["bufferViews"],
        "buffers": [{"byteLength": len(bin_)}],
    }
    return glb_write(src_js, bin_)


def merge_primitives(js, bin_):
    """The three primitives flattened into one indexed mesh, model space."""
    P, N, UV, I, base = [], [], [], [], 0
    for m in js["meshes"]:
        prim = m["primitives"][0]
        at = prim["attributes"]
        pos = accessor(js, bin_, at["POSITION"])
        nrm = accessor(js, bin_, at["NORMAL"])
        uv = accessor(js, bin_, at["TEXCOORD_0"])
        flat = accessor(js, bin_, prim["indices"])
        idx = [flat[i][0] for i in range(len(flat))]
        P.extend(pos)
        N.extend(nrm)
        UV.extend(uv)
        I.extend(v + base for v in idx)
        base += len(pos)
    tris = [(I[i], I[i + 1], I[i + 2]) for i in range(0, len(I), 3)]
    return P, N, UV, tris


# ---------------------------------------------------------------------------
# LICENSE / README text
# ---------------------------------------------------------------------------

LICENSE_TEXT = (
    "CC0 1.0 Universal (CC0 1.0) Public Domain Dedication\n"
    "\n"
    "This is the FULL DEDICATION TEXT, embedded, because law 7 says a licence\n"
    "travels as text and never as a link. A werk file that pointed at a URL for\n"
    "its terms would be a promise about another file, which law 1 bans.\n"
    "\n"
    "The person who associated a work with this deed has dedicated the work to\n"
    "the public domain by waiving all of his or her rights to the work worldwide\n"
    "under copyright law, including all related and neighboring rights, to the\n"
    "extent allowed by law.\n"
    "\n"
    "You can copy, modify, distribute and perform the work, even for commercial\n"
    "purposes, all without asking permission.\n"
    "\n"
    "Statement of Purpose\n"
    "The laws of most jurisdictions throughout the world automatically confer\n"
    "exclusive Copyright and Related Rights upon the creator of a work. Certain\n"
    "owners wish to permanently relinquish those rights in order to contribute\n"
    "to a commons of creative, cultural and scientific works that the public can\n"
    "reliably and without fear of later claims build upon, modify, incorporate\n"
    "in other works, reuse and redistribute as freely as possible in any form\n"
    "whatsoever and for any purposes, including without limitation commercial\n"
    "purposes. To the greatest extent permissible, the Affirmer waives and\n"
    "relinquishes all Copyright and Related Rights, and makes the Waiver for the\n"
    "benefit of the public at large and to the detriment of the Affirmer's heirs\n"
    "and successors, fully intending that such Waiver shall not be subject to\n"
    "revocation, rescission, cancellation, termination, or any other legal or\n"
    "equitable action to disrupt the quiet enjoyment of the Work by the public.\n"
    "\n"
    "Limitations and Disclaimer\n"
    "No trademark or patent rights held by Affirmer are waived, abandoned,\n"
    "surrendered, licensed or otherwise affected by this document. Affirmer\n"
    "offers the Work as-is and makes no representations or warranties of any kind\n"
    "concerning the Work, express, implied, statutory or otherwise, including\n"
    "without limitation warranties of title, merchantability, fitness for a\n"
    "particular purpose, non-infringement, or the absence of latent or other\n"
    "defects, accuracy, or the present or absence of errors, whether or not\n"
    "discoverable, all to the greatest extent permissible under applicable law.\n"
    "\n"
    "NOTICE (courtesy attribution, not a licence obligation)\n"
    "The 3D mesh is \"Wooden Crate 01\" by Poly Haven (https://polyhaven.com/a/\n"
    "wooden_crate_01), published under CC0 1.0. The texture maps carried in this\n"
    "package are NOT Poly Haven's photographic maps: they are procedurally\n"
    "generated by a deterministic stdlib-Python function and are likewise placed\n"
    "in the public domain. CC0 requires no attribution; this notice is a\n"
    "courtesy so a reader can trace where the geometry came from.\n"
)


def readme_text(variant, node_count):
    kind = ("the LEAN fixture: the smallest package that still exercises every "
            "mechanism a crate gate checks"
            if variant == "lean" else
            "the FULL fixture: the lean structure plus a synthetic sound effect, "
            "two procedural evidence previews, facet tags and material properties")
    return (
        "werk public-domain crate fixture (%s)\n"
        "%s\n"
        "\n"
        "A wooden crate packaged as one hermetic werk file, built entirely from\n"
        "public-domain inputs so the whole gate suite is reproducible by anyone\n"
        "with only this repository. This is %s.\n"
        "\n"
        "Everything needed to read this file is inside it: spec/ carries the\n"
        "format specification and its schemas, and loaders/ carries a single-\n"
        "file, dependency-free Python reader. Start with spec/README.md, or run\n"
        "loaders/werk_read.py against this file.\n"
        "\n"
        "The geometry is Poly Haven's CC0 \"Wooden Crate 01\"; the texture maps\n"
        "are deterministic procedural PNGs; the bounds are computed from the\n"
        "mesh; the facet tags and properties (full variant) are hand-authored\n"
        "and say so. It is signed with a DEV KEY derived from a published\n"
        "sentence and therefore not secret: the signature proves the chain\n"
        "works, nothing about authorship.\n"
        "\n"
        "This package declares %d nodes.\n"
        % ("full" if variant == "full" else "lean",
           "=" * 40, kind, node_count))


# ---------------------------------------------------------------------------
# the build
# ---------------------------------------------------------------------------

def collect(variant, src_dir, tmp_dir):
    """Return (files, nodes, stats) for the CLEAN variant. No manifest yet."""
    files, nodes = {}, []

    def put(path, data):
        assert path not in files, "two nodes claim %s" % path
        files[path] = data
        return {"path": path, "sha256": sha256(data), "size": len(data)}

    def node(node_id, ntype, ver, edges=(), meta=None, part=None, material=None):
        n = {"node_id": node_id, "type": ntype, "versions": [ver], "active": 1,
             "edges": list(edges)}
        if part:
            n["part_id"] = part
        if material:
            n["material_id"] = material
        if meta:
            n["meta"] = meta
        nodes.append(n)
        return n

    def version(fs, note, tool, tver, epistemic, inputs=None, confidence=None):
        v = {"v": 1, "files": fs, "note": note,
             "producer": {"tool": tool, "version": tver},
             "epistemic": epistemic, "created": CREATED}
        if inputs:
            v["input_files"] = list(inputs)
            v["input_hash"] = input_hash(inputs, files)
            v["input_params"] = {}
        if confidence is not None:
            v["confidence"] = confidence
        return v

    # -- LICENSE / README (README count patched after nodes are known) ----
    lic_f = put("LICENSE", LICENSE_TEXT.encode("utf-8"))

    # -- geometry --------------------------------------------------------
    js, bin_ = load_source(src_dir)
    src_glb = build_source_glb(js, bin_)
    P, N, UV, tris = merge_primitives(js, bin_)
    game_glb = build_glb(P, tris, nrm=N, uv=UV, name="crate")

    area, volume, watertight = mesh_stats(P, tris)
    centre, radius = welzl(P)
    assert all(math.dist(centre, p) <= radius + 1e-6 for p in P), \
        "minimal sphere misses a vertex"
    amin = [min(p[i] for p in P) for i in range(3)]
    amax = [max(p[i] for p in P) for i in range(3)]
    longest = max(amax[i] - amin[i] for i in range(3))

    src_f = put("geometry/source.glb", src_glb)
    game_f = put("geometry/game.glb", game_glb)
    node("geom-source", "core.geom.source",
         version([src_f], "Poly Haven's \"Wooden Crate 01\" (CC0), imported "
                          "verbatim: three primitives (lid, body, latch), "
                          "POSITION/NORMAL/TEXCOORD_0, external texture refs "
                          "dropped. The anchor every derivation is checked "
                          "against.", "fixtures/build_crate_cc0.py", "1", "authored"),
         part="crate")
    node("geom-game", "core.geom.game",
         version([game_f], "Runtime mesh: the three source primitives merged "
                           "into one conformant single-primitive mesh with "
                           "POSITION, NORMAL and TEXCOORD_0, built by "
                           "pipeline/glb.py build_glb.",
                 "fixtures/build_crate_cc0.py", "1", "authored",
                 inputs=["geometry/source.glb"]),
         edges=[{"to": "geom-source", "kind": "enhances", "role": "derived-from"}],
         part="crate")

    # -- textures: the deterministic procedural maps ---------------------
    field = height_field()
    tmp_png = os.path.join(tmp_dir, "_map.png")
    tex_specs = [
        ("tex-cc0-albedo", "textures/crate-cc0-albedo.png", albedo_rows(field),
         "srgb", "base-color",
         "Albedo (sRGB): plank pattern with a per-plank tint and a stated "
         "integer-hash grain. sRGB, declared not inferred."),
        ("tex-cc0-normal", "textures/crate-cc0-normal.png", normal_rows(field),
         "linear", "normal",
         "Tangent-space normal (LINEAR): central differences over the same "
         "height field the grain reads from, so the two maps agree by "
         "construction. Read as sRGB, every normal bends."),
        ("tex-cc0-mr", "textures/crate-cc0-mr.png", mr_rows(field),
         "linear", "metallic-roughness",
         "Metallic-roughness (LINEAR), glTF packing: occlusion=R, roughness=G, "
         "metallic=B. Metallic is 0 everywhere: wood is a dielectric."),
    ]
    tex_by_slot = {}
    for node_id, path, rows, cspace, usage, note in tex_specs:
        data = write_png(tmp_png, TEX_SIZE, TEX_SIZE, rows)
        f = put(path, data)
        f["media_type"] = "image/png"
        info = png_info(data)
        node(node_id, "core.tex",
             version([f], note, "fixtures/build_crate_cc0.py", "1", "authored"),
             meta={"color_space": cspace, "usage": usage,
                   "width": info["width"], "height": info["height"],
                   "channels": info["channels"], "bit_depth": info["bit_depth"]},
             part="crate")
        tex_by_slot[usage] = (node_id, path)

    # -- material: references the three core.tex nodes -------------------
    mat = {
        "material_id": "wood", "name": "Crate softwood", "model": "metallic-roughness",
        "base_color_factor": [1.0, 1.0, 1.0, 1.0],
        "metallic_factor": 0.0, "roughness_factor": 0.85,
        "alpha_mode": "opaque", "double_sided": True,
        "epistemic": "authored", "ior": 1.5,
        "textures": {
            "base_color": {"node": tex_by_slot["base-color"][0],
                           "path": tex_by_slot["base-color"][1], "uv_set": 0},
            "metallic_roughness": {"node": tex_by_slot["metallic-roughness"][0],
                                   "path": tex_by_slot["metallic-roughness"][1],
                                   "uv_set": 0, "channel": "rgb"},
            "normal": {"node": tex_by_slot["normal"][0],
                       "path": tex_by_slot["normal"][1], "uv_set": 0},
        },
        "note": "PBR parameters for the crate's only material, sampling the "
                "three procedural core.tex maps. Roughness is an authored "
                "judgement about dry sawn softwood, not a measurement.",
    }
    mat_f = put("materials/wood.json", jbytes(mat))
    mat_f["media_type"] = "application/json"
    node("material-wood", "core.material",
         version([mat_f], "Authored PBR parameters, three texture slots.",
                 "fixtures/build_crate_cc0.py", "1", "authored"),
         edges=[{"to": "geom-game", "kind": "enhances", "role": "shades"},
                {"to": "tex-cc0-albedo", "kind": "requires", "role": "samples"},
                {"to": "tex-cc0-mr", "kind": "requires", "role": "samples"},
                {"to": "tex-cc0-normal", "kind": "requires", "role": "samples"}],
         part="crate", material="wood")

    # -- bounds ----------------------------------------------------------
    bounds = {
        "schema_version": 1, "space": "model",
        "entity": {
            "aabb_min": [round(v, 7) for v in amin],
            "aabb_max": [round(v, 7) for v in amax],
            "sphere_center": [round(v, 7) for v in centre],
            "sphere_radius": round(radius, 7),
            "sphere_method": "welzl-exact",
            "surface_area_m2": round(area, 7),
            "volume_m3": round(volume, 7),
            "watertight": watertight,
            "longest_axis_m": round(longest, 7),
        },
        "epistemic": "measured",
        "note": "Computed from geometry/game.glb: the AABB over every vertex "
                "and the true minimal enclosing sphere by Welzl.",
    }
    bounds_f = put("physics/bounds.json", jbytes(bounds))
    bounds_f["media_type"] = "application/json"
    node("bounds", "core.phys.bounds",
         version([bounds_f], "Measured bounds for culling, placement and LOD.",
                 "fixtures/build_crate_cc0.py", "1", "measured",
                 inputs=["geometry/game.glb"]),
         edges=[{"to": "geom-game", "kind": "requires", "role": "bounds-of"}],
         part="crate")

    produced = ["geom-source", "geom-game", "tex-cc0-albedo", "tex-cc0-normal",
                "tex-cc0-mr", "material-wood", "bounds"]

    # -- FULL-only content ----------------------------------------------
    if variant == "full":
        # synthetic audio effect (WAV payload + JSON descriptor sidecar)
        wav = make_click_wav()
        wav_f = put(PREVIEW_ONE_SHOT, wav)
        wav_f["media_type"] = "audio/wav"
        wav_f["role"] = "best"
        info = wav_info(wav)
        eff = {
            "slug": "crate-cc0-click", "prompt_used": "a short hollow wooden "
            "crate being tapped once, dry indoor acoustic",
            "seconds": round(info["seconds"], 3), "loopable": False,
            "clap_score": 0.5, "accepted": True, "category": "interaction",
            "object": "wooden crate", "material": "wood",
            "interaction": "tapped once",
            "audio_format": {"sample_rate_hz": info["sample_rate_hz"],
                             "channels": info["channels"],
                             "bit_depth": info["bit_depth"],
                             "sample_format": info["sample_format"]},
            "epistemic": "authored", "part_id": "crate", "material_id": "wood",
            "note": "SYNTHETIC and AUTHORED: a deterministic decaying click "
                    "synthesised in stdlib Python (three resonant modes plus a "
                    "transient), not a generated take. clap_score is an authored "
                    "placeholder, not a real CLAP measurement, and is stamped so.",
        }
        eff_f = put("audio/sfx/crate-cc0-click.json", jbytes(eff))
        eff_f["media_type"] = "application/json"
        eff_f["role"] = "descriptor"
        node("audio-cc0-click", "core.audio.effect",
             version([wav_f, eff_f], "A synthetic one-shot impact for the crate: "
                     "the WAV take plus its generation/descriptor sidecar.",
                     "fixtures/build_crate_cc0.py", "1", "authored"),
             edges=[{"to": "geom-game", "kind": "enhances", "role": "sounds-for"}],
             part="crate", material="wood")
        produced.append("audio-cc0-click")

        # two procedural "evidence" preview PNGs — x.* nodes a core reader skips
        ev_field = height_field(size=128)
        for i, (rows, what) in enumerate((
                (albedo_rows(ev_field, size=128), "an albedo-lit front view"),
                (mr_rows(ev_field, size=128), "a roughness/occlusion pass")), 1):
            data = write_png(tmp_png, 128, 128, rows)
            f = put("x/evidence/view-%02d.png" % i, data)
            f["media_type"] = "image/png"
            f["role"] = "view"
            pi = png_info(data)
            node("evidence-view-%d" % i, "x.cc0.evidence",
                 version([f], "A procedural preview standing in for a rendered "
                             "evidence view (%s). An x.* node because a preview "
                             "is never sampled by a material; every core reader "
                             "skips it and loses nothing (law 12)." % what,
                         "fixtures/build_crate_cc0.py", "1", "authored"),
                 meta={"width": pi["width"], "height": pi["height"],
                       "kind": "procedural-preview"})

        # semantics — hand-authored facet tags, validated against the registry
        with open(os.path.join(ROOT, "spec", "facets.json"), encoding="utf-8") as fh:
            reg = json.load(fh)
        facets = {
            "style": ["rustic", "utilitarian", "industrial"],
            "function": ["container", "storage", "packaging"],
            "environment": ["warehouse", "interior", "exterior"],
            "era": ["timeless"],
            "mood": ["utilitarian", "neutral"],
            "condition": ["used", "worn"],
            "scale-class": [_scale_class_for(reg, longest)],
        }
        for facet, tags in facets.items():
            legal = set(reg["facets"][facet]["tags"])
            bad = [t for t in tags if t not in legal and not t.startswith("x.")]
            assert not bad, "tag(s) %s not in facets.json's %s" % (bad, facet)
        band = reg["facets"]["scale-class"]["tag_meta"][facets["scale-class"][0]]
        assert band["longest_axis_min_m"] <= longest < band["longest_axis_max_m"], \
            "scale-class does not contain the measured longest axis %.4f" % longest
        sem = {
            "schema_version": 1, "facets_version": reg["version"], "facets": facets,
            "tag_stamps": {"%s/%s" % (fc, t): {"epistemic": "authored"}
                           for fc, ts in facets.items() for t in ts},
            "palette": {
                "method": "authored",
                "colors": [
                    {"hex_srgb": "#a9793f", "linear_rgb": [0.3662, 0.1878, 0.0508],
                     "weight": 0.80, "name": "softwood"},
                    {"hex_srgb": "#5f3d1e", "linear_rgb": [0.1195, 0.0452, 0.0120],
                     "weight": 0.20, "name": "shadowed grain"},
                ],
                "dominant_index": 0, "average_luminance": 0.29,
            },
            "description": "A slatted wooden shipping crate with a hinged lid and "
                           "a small latch, roughly a metre across. Used and lightly "
                           "worn.",
            "keywords": ["crate", "wooden", "container", "cc0", "poly-haven", "prop"],
            "note": "Facet tags are hand-authored against spec/facets.json, which "
                    "travels in this package; every tag is stamped 'authored'. "
                    "scale-class was checked arithmetically against the registry "
                    "band (longest axis %.4f m)." % longest,
        }
        sem_f = put("semantics/semantics.json", jbytes(sem))
        sem_f["media_type"] = "application/json"
        node("semantics", "core.semantics",
             version([sem_f], "Hand-authored facet tags, palette and search text.",
                     "fixtures/build_crate_cc0.py", "1", "authored"),
             edges=[{"to": "geom-game", "kind": "enhances", "role": "describes"}])
        produced.append("semantics")

        # properties — authored wood values
        def num(value, unit, src_txt, rng=None):
            d = {"value": value, "unit": unit, "epistemic": "authored",
                 "source": src_txt}
            if rng:
                d["range"] = rng
            return d
        props = {
            "schema_version": 1, "registry_version": 1,
            "regions": [{
                "region_id": "crate-body", "material_id": "wood", "part_id": "crate",
                "label": "Sawn softwood slats, frame and lid",
                "properties": {
                    "mechanical": {
                        "density": num(500.0, "kg/m^3", "handbook, kiln-dried "
                                       "softwood at 12 percent moisture",
                                       [350.0, 650.0]),
                        "youngs_modulus": num(1.1e10, "Pa", "along the grain",
                                              [8.0e9, 1.4e10]),
                        "poisson_ratio": num(0.37, "1", "softwood longitudinal-radial"),
                    },
                    "thermal": {
                        "conductivity": num(0.13, "W/(m*K)", "dry softwood across grain"),
                        "specific_heat": num(1700.0, "J/(kg*K)", "dry wood"),
                    },
                    "flammability": {
                        "class": {"value": "flammable", "epistemic": "authored",
                                  "source": "untreated softwood"},
                        "autoignition_point": num(300.0, "degC", "typical for cellulose",
                                                  [250.0, 350.0]),
                    },
                },
            }],
            "note": "AUTHORED handbook values for kiln-dried softwood, each with a "
                    "named source and stamp. No model guessed any of these.",
        }
        props_f = put("properties/properties.json", jbytes(props))
        props_f["media_type"] = "application/json"
        node("props", "core.props",
             version([props_f], "Authored simulation properties for the crate's wood.",
                     "fixtures/build_crate_cc0.py", "1", "authored"),
             edges=[{"to": "material-wood", "kind": "enhances", "role": "properties-of"}])
        produced.append("props")

    # -- disclosure: the generic/blob node (corruption target in lean) --
    disc = {
        "disclosure_version": 1, "ai_generated": False, "ai_modified": False,
        "generation_scope": "none",
        "declared_by": {"name": "werk fixtures (build_crate_cc0.py)",
                        "kind": "service",
                        "uri": "urn:werk:dev-key:build-crate-cc0"},
        "declared_at": CREATED,
        "human_authorship": {
            "claimed": True,
            "description": "The mesh is a CC0 model by Poly Haven; the three "
                           "texture maps are procedurally generated by a stated "
                           "deterministic stdlib-Python function; the packaging, "
                           "material parameters and facet tags were authored by a "
                           "person. No generative model produced any content here.",
        },
        "models": [],
        "synthetic_markers": {
            "declared_watermarks": [{"kind": "none", "present": False,
                                     "note": "No watermarking of any kind; the "
                                             "maps are deterministic function output."}],
            "c2pa_manifest_present": False, "embedded_metadata_stripped": True,
        },
        "statements": [{"id": "cc0-dedication",
                        "text": "The mesh and all generated maps are released "
                                "into the public domain under CC0 1.0.",
                        "epistemic": "authored"}],
        "jurisdiction_note": "Informational only; confers nothing (law: the "
                             "format ships facts, the viewer applies jurisdiction).",
    }
    disc_f = put("disclosure/disclosure.json", jbytes(disc))
    disc_f["media_type"] = "application/json"
    node("disclosure-cc0", "core.disclosure",
         version([disc_f], "Machine-readable facts about how this package came to "
                          "exist: not AI-generated, procedural textures, CC0. In "
                          "the LEAN damaged variant this node's payload is the one "
                          "whose byte is flipped, so it goes dead by hash-mismatch.",
                 "fixtures/build_crate_cc0.py", "1", "authored"))
    produced.append("disclosure-cc0")

    # -- provenance ------------------------------------------------------
    prov = {
        "schema_version": 1,
        "runs": [{
            "run_id": "werk-cc0-build", "started": CREATED, "finished": CREATED,
            "tool": {"name": "fixtures/build_crate_cc0.py", "version": "1"},
            "consumed": [
                {"path": "Poly Haven Wooden Crate 01 (wooden_crate_01_2k.gltf)",
                 "sha256": sha256(_read(os.path.join(src_dir,
                                        "wooden_crate_01_2k.gltf"))),
                 "external": True, "license": "CC0-1.0"},
                {"path": "Poly Haven Wooden Crate 01 (wooden_crate_01.bin)",
                 "sha256": sha256(_read(os.path.join(src_dir,
                                        "wooden_crate_01.bin"))),
                 "external": True, "license": "CC0-1.0"},
            ],
            "produced": [{"node_id": nid, "v": 1} for nid in produced],
            "gates": _gates(variant),
            "note": "The werk packaging pass over the CC0 mesh: merged runtime "
                    "geometry, procedural maps, exact bounds, and (full) audio, "
                    "facets and properties. Each gate is asserted in the builder.",
        }],
    }
    prov_f = put("provenance/provenance.json", jbytes(prov))
    prov_f["media_type"] = "application/json"
    node("provenance", "core.provenance",
         version([prov_f], "Who made what, from what, and which gates it passed.",
                 "fixtures/build_crate_cc0.py", "1", "authored"))

    # -- spec / loader / license / readme --------------------------------
    spec_files = []
    for dirpath, _dirs, names in os.walk(os.path.join(ROOT, "spec")):
        for nm in sorted(names):
            if nm.endswith(".pyc"):
                continue
            full = os.path.join(dirpath, nm)
            rel = "spec/" + os.path.relpath(full, os.path.join(ROOT, "spec")).replace("\\", "/")
            spec_files.append(put(rel, _read(full)))
    spec_files.sort(key=lambda f: f["path"])
    node("spec", "core.spec",
         version(spec_files, "The format specification, its schemas and binary "
                            "layout grammars, travelling inside the file it "
                            "describes (law 2).", "werk", "0.1", "authored"))

    loader_data = _read(os.path.join(ROOT, "loaders", "werk_read.py"))
    loader_f = put("loaders/werk_read.py", loader_data)
    node("loader-python", "core.loader",
         version([loader_f], "A single-file, dependency-free Python reader for "
                            "this package, carried as payload so the file brings "
                            "its own reader (law 1).", "werk", "0.1", "authored"),
         meta={"language": "python", "form": "source",
               "entrypoint": "loaders/werk_read.py", "toolchain": "python>=3.8",
               "dependencies": [],
               "capabilities": loader_capabilities(loader_data)})

    node("license", "core.license",
         version([lic_f], "The full CC0 1.0 dedication text, embedded, never a "
                          "link (law 7).", "werk", "0.1", "authored"))

    # README last, once the node count is known.
    readme_f = put("README.txt", readme_text(variant, len(nodes) + 1).encode("utf-8"))
    node("readme", "core.readme",
         version([readme_f], "One page for a human who opened this file.",
                 "werk", "0.1", "authored"))

    stats = {"verts": len(P), "tris": len(tris), "longest": longest,
             "radius": radius}
    return files, nodes, stats


def _read(path):
    with open(path, "rb") as fh:
        return fh.read()


def _scale_class_for(reg, longest):
    for tag in reg["facets"]["scale-class"]["tags"]:
        band = reg["facets"]["scale-class"]["tag_meta"][tag]
        if band["longest_axis_min_m"] <= longest < band["longest_axis_max_m"]:
            return tag
    return "medium"


def _gates(variant):
    gates = [{"name": "minimal-sphere-encloses-every-vertex", "passed": True}]
    if variant == "full":
        gates += [{"name": "facet-tags-in-registry", "passed": True},
                  {"name": "scale-class-band-contains-longest-axis", "passed": True}]
    return gates


# ---------------------------------------------------------------------------
# manifest / assemble / sign
# ---------------------------------------------------------------------------

SCHEMA_FILES = {
    "core.material": "spec/schemas/core.material.schema.json",
    "core.phys.bounds": "spec/schemas/core.phys.bounds.schema.json",
    "core.semantics": "spec/schemas/core.semantics.schema.json",
    "core.props": "spec/schemas/core.props.schema.json",
    "core.provenance": "spec/schemas/core.provenance.schema.json",
    "core.disclosure": "spec/schemas/core.disclosure.schema.json",
    "core.audio.effect": "spec/schemas/core.audio.effect.schema.json",
}


def build_manifest(variant, files, nodes, preview_prefix, extra_summary=""):
    present = {n["type"] for n in nodes}
    schemas = {t: p for t, p in SCHEMA_FILES.items() if t in present}
    primary = {"mesh": "geom-game"}
    if variant == "full":
        primary["sound"] = "audio-cc0-click"
    name = "Wooden crate, CC0 %s" % ("(lean)" if variant == "lean" else "(full)")
    summary = (
        "A public-domain wooden crate (Poly Haven \"Wooden Crate 01\", CC0), "
        "packaged as a werk conformance fixture reproducible from this "
        "repository alone. %s Signed with a publicly derived DEV key that proves "
        "the chain works and nothing about authorship."
        % ("The lean variant: the smallest package that still exercises multi-"
           "node load, round-trip identity, graceful damage and blob extraction."
           if variant == "lean" else
           "The full variant adds a synthetic sound effect, procedural evidence "
           "previews, facet tags and material properties.")) + extra_summary
    return {
        "werk": {"major": 1, "minor": 0},
        "profile": "3d-entity/1",
        "entity": {"uuid": UUID[variant], "name": name, "summary": summary,
                   "created": CREATED},
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
            "entry_order": list(ENTRY_ORDER[variant]),
            "preview_prefix_bytes": preview_prefix,
        },
        "primary": primary,
        "license": {"spdx_id": "CC0-1.0", "file": "LICENSE",
                    "sha256": sha256(files["LICENSE"])},
        "spec_sha256": spec_sha256_of_files(files),
        "conventions_map": "spec/conventions-map.json",
        "schemas": schemas,
        "layouts": {},
        "parts": [{"part_id": "crate", "name": "Wooden crate", "parent": None,
                   "transform": {"translation": [0.0, 0.0, 0.0],
                                 "rotation": [1.0, 0.0, 0.0, 0.0],
                                 "scale": [1.0, 1.0, 1.0]}}],
        "materials": [{"material_id": "wood", "part_id": "crate",
                       "name": "Crate softwood", "class": "wood"}],
        "nodes": nodes,
    }


def assemble(variant, files, nodes, extra_summary=""):
    annotate_payload_files(nodes)
    # SPEC 5: never write a `requires` edge to a node not in nodes[].
    refuse_dangling_requires(nodes)
    pset = preview_set(variant)
    preview = 0
    for _round in range(8):
        manifest_bytes = jbytes(build_manifest(variant, files, nodes, preview,
                                               extra_summary))
        sig_bytes = jbytes(sign(manifest_bytes,
                                "Signed with a DEV key derived from a published "
                                "sentence. Not secret, not a trust anchor; it "
                                "proves only that the chain verifies."))
        allf = dict(files)
        allf["MANIFEST.json"] = manifest_bytes
        allf["SIGNATURE.json"] = sig_bytes
        entries = [(p, allf[p]) for p in order_entries(allf.keys(),
                                                       ENTRY_ORDER[variant])]
        cursor, prefix = 0, 0
        for name, data in entries:
            this = 30 + len(name.encode("utf-8")) + len(data)
            if is_preview(name, pset):
                prefix = cursor + this
            cursor += this
        if prefix == preview:
            return manifest_bytes, sig_bytes, entries
        preview = prefix
    raise SystemExit("preview_prefix_bytes did not converge")


# ---------------------------------------------------------------------------
# damaged variant
# ---------------------------------------------------------------------------

MYSTERY = (b"x.werk-future.mystery v1\n"
           b"A payload shape that does not exist yet. If you are reading this in "
           b"a reader that understands it, this fixture is older than you.\n")

# Which payload each variant flips a byte in. Lean has no audio, so it corrupts
# its generic blob node (the disclosure); full corrupts the audio, mirroring the
# golden crate's damaged shape exactly.
CORRUPT_TARGET = {"lean": "disclosure/disclosure.json",
                  "full": PREVIEW_ONE_SHOT}


def build_damaged(variant, files, nodes):
    dfiles = dict(files)
    dnodes = [json.loads(json.dumps(n)) for n in nodes]
    dfiles["x/mystery/blob.bin"] = MYSTERY
    dnodes.append({
        "node_id": "mystery", "type": "x.werk-future.mystery",
        "versions": [{"v": 1, "files": [{"path": "x/mystery/blob.bin",
                                         "sha256": sha256(MYSTERY),
                                         "size": len(MYSTERY)}],
                      "note": "A node type from a version of the format this "
                              "reader has never heard of. It must be listed, "
                              "hash-verified and skipped WITH A REPORT, never a "
                              "failure (law 12).",
                      "producer": {"tool": "fixtures/build_crate_cc0.py",
                                   "version": "1"},
                      "epistemic": "authored", "created": CREATED}],
        "active": 1, "edges": []})
    dmanifest, dsig, dentries = assemble(
        variant, dfiles, dnodes,
        " DAMAGED VARIANT: one node's payload byte is flipped (caught by the "
        "per-file hash, NOT the signature) and one node carries a type no "
        "current reader knows.")
    target = CORRUPT_TARGET[variant]
    off = 1000 if len(files[target]) > 1001 else 5
    dentries = [(p, (d[:off] + bytes([d[off] ^ 0xFF]) + d[off + 1:])
                 if p == target else d) for p, d in dentries]
    return write_zip(dentries), target, off


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------

def build(variant, src_dir, out_dir):
    import shutil
    tmp_dir = os.path.join(out_dir, ".werk-cc0-tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    try:
        files, nodes, stats = collect(variant, src_dir, tmp_dir)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    _manifest, _sig, entries = assemble(variant, files, nodes)
    clean_blob = write_zip(entries)
    dmg_blob, target, off = build_damaged(variant, files, nodes)
    return clean_blob, dmg_blob, nodes, stats, target, off


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--variant", choices=["lean", "full"], required=True)
    ap.add_argument("--src", default=SRC_DEFAULT)
    ap.add_argument("--out", default=None,
                    help="output dir for the fixtures. Defaults to the fixtures "
                         "tree on a normal build. Under --check-determinism the "
                         "fixtures are NOT written unless --out is given "
                         "explicitly, so verification never mutates its subject.")
    ap.add_argument("--check-determinism", action="store_true")
    args = ap.parse_args(argv)

    # build() only uses this for a self-cleaning temp subdir; the fixtures
    # themselves are written (or not) below, guarded by --check-determinism.
    scratch_base = args.out if args.out is not None else HERE
    clean_blob, dmg_blob, nodes, stats, target, off = build(
        args.variant, args.src, scratch_base)

    print("variant: %s" % args.variant)
    print("mesh %d verts / %d tris, longest axis %.4f m, sphere r=%.4f m"
          % (stats["verts"], stats["tris"], stats["longest"], stats["radius"]))

    if args.check_determinism:
        # A verification step must never overwrite the fixtures it verifies:
        # a bare --check-determinism writes nothing into the source tree.
        c2, d2, _n, _s, _t, _o = build(args.variant, args.src, scratch_base)
        ok = (sha256(c2) == sha256(clean_blob) and sha256(d2) == sha256(dmg_blob))
        print("determinism: %s (two builds, whole-file sha256 %s)"
              % ("PASS" if ok else "FAIL",
                 "identical" if ok else "DIFFER"))
        if args.out is None:
            return 0 if ok else 1
        if not ok:
            return 1

    out_dir = args.out if args.out is not None else HERE
    clean_path = os.path.join(out_dir, "crate-cc0-%s-v1.werk" % args.variant)
    dmg_path = os.path.join(out_dir, "crate-cc0-%s-v1-damaged.werk" % args.variant)
    with open(clean_path, "wb") as fh:
        fh.write(clean_blob)
    with open(dmg_path, "wb") as fh:
        fh.write(dmg_blob)

    print("wrote %s" % clean_path)
    print("  %d bytes, sha256 %s" % (len(clean_blob), sha256(clean_blob)))
    print("  %d nodes" % len(nodes))
    print("wrote %s" % dmg_path)
    print("  %d bytes, sha256 %s" % (len(dmg_blob), sha256(dmg_blob)))
    print("  damage: 1 flipped byte in %s (offset %d), plus x.werk-future.mystery"
          % (target, off))
    return 0


if __name__ == "__main__":
    sys.exit(main())
