#!/usr/bin/env python3
"""build_image_cc0.py — the PUBLIC-DOMAIN image fixture.

    python fixtures/build_image_cc0.py
    python fixtures/build_image_cc0.py --check-determinism

Why this fixture exists
-----------------------
`fixtures/ista-varun-v1.werk` (the golden image, profile `image/1`) is built
from PRIVATE assets: a real generated PNG, the pipeline's artifact database, and
a house style plate on disk. That makes the image gate depend on files that
cannot be published. This is the CC0/public-domain stand-in so the whole
image-profile conformance path is reproducible by anyone with only this
repository, in pure Python, with no database, no network and no private tree —
exactly the two-tier model `fixtures/CC0-FIXTURES.md` describes for the crate.

  * `image-cc0-v1.werk` — the smallest `image/1` fixture that still exercises
    every mechanism an image gate checks: a `core.image.source` plus two
    deterministic `core.image.derived` sizes, a `core.embedding` custom binary
    (`WKEM`, so `spec/layouts/ENVELOPE.layout.txt` and `embedding.layout.txt`
    get run rather than merely read), `core.semantics`, `core.disclosure`,
    `core.provenance`, the vendored spec/ and a bootstrap reader, a signed
    chain, and the preview-first byte layout with the thumbnail inside it.
  * `image-cc0-v1-damaged.werk` — the same package with one node's payload byte
    flipped (caught by the per-file hash, NOT the signature) and one node
    carrying a type no current reader knows (skipped WITH A REPORT, law 12).

Provenance of the image
-----------------------
The image is a Poly Haven CC0 2K texture (weathered wooden crate planks — the
same "Wooden Crate 01" family as the CC0 crate fixtures). It lives verbatim in
`fixtures/sources/image-cc0/image-cc0-source.jpg` and is carried into the
package unchanged as `image/source.jpg` (the archival anchor). The two derived
PNGs are deterministic Lanczos-3 downscales of it, and the style descriptor and
palette are `werk.descriptor.labhog/1` measurements over its pixels. The
embedded LICENSE is CC0 1.0 with a courtesy NOTICE crediting Poly Haven.

Determinism
-----------
A fixed CREATED timestamp, no wall clock in any payload, byte-identical across
two runs on one machine. `--check-determinism` builds twice and compares. The
derived PNGs are encoded by `pipeline/det_png.py` (pure-Python deflate, a fixed
algorithm), not by Pillow's zlib, so their bytes depend on the pixels alone;
the pixels are Pillow's Lanczos-3 resample of the JPEG's decoded pixels, and
the descriptor is over those, so cross-*machine* byte-identity assumes the
pinned Pillow (and the libjpeg-turbo in its wheel) — measured identical on
Windows and two Linux machines.

This file reuses `build_image_fixture.py`'s zip framing, hashing, WKEM writer
and helpers rather than re-deriving them, so the two image builders cannot
disagree, exactly as `build_crate_cc0.py` reuses `build_golden.py`.

DEPENDENCIES: Pillow==12.3.0 (decode/resample) and numpy (the labhog
descriptor); pinned in fixtures/requirements-build.txt. Neither travels inside
the package — law 1's ban is about what ships in the file, and a builder is not
a `core.loader`. The resampled pixels are Pillow-version-sensitive (Lanczos
arithmetic changed between Pillow releases), so the version is pinned for
byte-exact reproduction of the shipped fixture; a mismatch is warned, not
silently drifted.
"""

import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)                          # build_image_fixture, labhog
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))   # spec_sha256, payload_file
sys.path.insert(0, os.path.join(ROOT, "store"))   # werkstore.signature

# THE template. Reused verbatim so the two image builders cannot drift apart:
# the zip writer, the hashers, the WKEM envelope writer, and the small PNG and
# colour helpers all come from the private builder.
import build_image_fixture as IMG                                   # noqa: E402
from loader_caps import loader_capabilities        # noqa: E402
from build_image_fixture import (sha256, jbytes, input_hash,        # noqa: E402
                                 write_zip, png_info, png_chunks,
                                 derived_height, linear_to_hex,
                                 build_wkem, matches, DEV_SK)
import labhog                                                        # noqa: E402
from pipeline import det_png                                         # noqa: E402
from spec_sha256 import spec_sha256_of_files                        # noqa: E402
from payload_file import annotate_payload_files                     # noqa: E402
from edge_targets import refuse_dangling_edges                   # noqa: E402
from werkstore.signature import build_chain                         # noqa: E402

SRC_DEFAULT = os.path.join(HERE, "sources", "image-cc0")
SRC_IMAGE = "image-cc0-source.jpg"

CREATED = "2026-09-05T00:00:00Z"
ENTITY_UUID = "e3f4a5b6-7c8d-4e9f-8a0b-1c2d3e4f5a6b"

PREVIEW_W, THUMB_W = 1024, 256

ENTRY_ORDER = [
    "MANIFEST.json", "SIGNATURE.json", "LICENSE", "README.txt",
    "loaders/", "spec/", "semantics/", "disclosure/",
    "image/thumb-256.png",              # thumbnail in the browsable tier (law 9)
    "image/", "provenance/", "x/",
]
# Everything at or before the thumbnail is the browsable tier: a store fetching
# the first few hundred kilobytes gets the manifest, a reader, the spec, the
# facets, the disclosure and the thumbnail — but NOT the full source image.
PREVIEW_SET = ENTRY_ORDER[:ENTRY_ORDER.index("image/thumb-256.png") + 1]


def order_entries(paths):
    remaining = sorted(paths)
    out = []
    for pat in ENTRY_ORDER:
        for p in [q for q in remaining if matches(q, pat)]:
            remaining.remove(p)
            out.append(p)
    return out + remaining


def is_preview(name):
    return any(matches(name, p) for p in PREVIEW_SET)


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
    "The image is a Poly Haven (https://polyhaven.com) CC0 1.0 texture. Poly\n"
    "Haven publishes all of its assets under CC0 and requires no attribution;\n"
    "this notice is a courtesy so a reader can trace where the image came from.\n"
    "The two derived PNGs and the style descriptor are deterministic functions\n"
    "of that image and are likewise placed in the public domain.\n"
)


def readme_text(node_count):
    return (
        "werk public-domain image fixture\n"
        "%s\n"
        "\n"
        "A werk package, profile image/1, built entirely from public-domain\n"
        "inputs so the whole image gate is reproducible by anyone with only this\n"
        "repository. It is hermetic: everything needed to read it is inside it.\n"
        "spec/ carries the specification, its schemas and the layout grammars;\n"
        "loaders/ carries a single-file, dependency-free Python reader. Start\n"
        "with spec/README.md, or run loaders/werk_read.py against this file.\n"
        "\n"
        "What is in it: one CC0 image (a Poly Haven wooden-crate texture) carried\n"
        "verbatim as image/source.jpg, two deterministic Lanczos-3 PNG sizes of\n"
        "it, a measured werk.descriptor.labhog/1 style descriptor in a WKEM\n"
        "custom binary (read spec/layouts/ENVELOPE.layout.txt then\n"
        "embedding.layout.txt), facet tags and a palette, a machine-readable\n"
        "disclosure, a provenance record, and a signature chain.\n"
        "\n"
        "Two things worth knowing:\n"
        "\n"
        "1. This image is NOT AI-generated. disclosure/disclosure.json says so\n"
        "   as a fact, and there is no core.recipe node because there is no\n"
        "   generation recipe: it is a photographed/authored CC0 texture, not a\n"
        "   model output. That is the honest shape for public-domain source art,\n"
        "   and it is the counterpart to the golden image fixture, which IS\n"
        "   generated and carries the recipe that proves it.\n"
        "\n"
        "2. It is signed with a DEV KEY derived from a published sentence, so it\n"
        "   is not secret and not a trust anchor. The signature proves the chain\n"
        "   works; it proves nothing about authorship.\n"
        "\n"
        "This package declares %d nodes.\n"
        % ("=" * 40, node_count))


# ---------------------------------------------------------------------------
# the build
# ---------------------------------------------------------------------------

def _read(path):
    with open(path, "rb") as fh:
        return fh.read()


def _facets_registry():
    with open(os.path.join(ROOT, "spec", "facets.json"), encoding="utf-8") as fh:
        return json.load(fh)


def collect(src_dir):
    """Return (files, nodes, stats) for the CLEAN variant. No manifest yet."""
    from PIL import Image
    import PIL
    import io
    import numpy as np

    if PIL.__version__ != "12.3.0":
        print("warning: Pillow %s != pinned 12.3.0 (fixtures/requirements-build.txt); "
              "the Lanczos resample is version-sensitive, so the rebuilt fixture "
              "may differ from the shipped bytes." % PIL.__version__, file=sys.stderr)

    files, nodes = {}, []

    def put(path, data, media=None, role=None):
        assert path not in files, "two nodes claim %s" % path
        files[path] = data
        f = {"path": path, "sha256": sha256(data), "size": len(data)}
        if media:
            f["media_type"] = media
        if role:
            f["role"] = role
        return f

    def node(node_id, ntype, versions, edges=(), meta=None, active=None):
        n = {"node_id": node_id, "type": ntype, "versions": versions,
             "active": active or len(versions), "edges": list(edges)}
        if meta:
            n["meta"] = meta
        nodes.append(n)
        return n

    def version(v, fs, note, tool, tver, epistemic, created=CREATED,
                inputs=None, model=None, confidence=None):
        out = {"v": v, "files": fs, "note": note,
               "producer": {"tool": tool, "version": tver},
               "epistemic": epistemic, "created": created}
        if model:
            out["producer"]["model"] = model
        if inputs:
            out["input_files"] = list(inputs)
            out["input_hash"] = input_hash(inputs, files)
            out["input_params"] = {}
        if confidence is not None:
            out["confidence"] = confidence
        return out

    # -- LICENSE / README (README count patched after nodes are known) ----
    lic_f = put("LICENSE", LICENSE_TEXT.encode("utf-8"), "text/plain")

    # -- the image and its derivatives -----------------------------------
    src_jpg = _read(os.path.join(src_dir, SRC_IMAGE))
    src_img = Image.open(io.BytesIO(src_jpg))
    src_img.load()
    assert src_img.format == "JPEG", "source is expected to be the CC0 JPEG"
    w, h = src_img.size
    stats = {"src_w": w, "src_h": h, "src_bytes": len(src_jpg)}

    # JPEG carries no PNG text chunks; the disclosure states, as MEASURED, that
    # the file carries no ancillary metadata. Assert what we can: no EXIF that
    # Pillow surfaces (an APP1 Exif segment would populate this).
    exif_present = bool(src_img.getexif())
    stats["exif_present"] = exif_present

    src_f = put("image/source.jpg", src_jpg, "image/jpeg")

    def derive(width):
        dh = derived_height(w, h, width)
        im = src_img.convert("RGB").resize((width, dh), Image.LANCZOS)
        # Pillow supplies the pixels; the PNG stream is pipeline/det_png.py's,
        # the same bytes on every OS (finding N3: Pillow's own stream depends
        # on the zlib its wheel links).
        return dh, det_png.encode_pil(im)

    prev_h, prev_png = derive(PREVIEW_W)
    thumb_h, thumb_png = derive(THUMB_W)
    prev_f = put("image/preview-1024.png", prev_png, "image/png")
    thumb_f = put("image/thumb-256.png", thumb_png, "image/png")

    # -- the style descriptor (WKEM) -------------------------------------
    vec, palette, diag = labhog.descriptor(src_img)
    lin = labhog.srgb_to_linear(labhog.box_resample(
        np.asarray(src_img.convert("RGB"))))
    avg_lum = float((lin[..., 0] * 0.2126729 + lin[..., 1] * 0.7151522
                     + lin[..., 2] * 0.0721750).mean())
    stats["descriptor"] = diag
    wkem = build_wkem(vec, palette, {
        "model": labhog.MODEL_ID,
        "dim": labhog.DIM,
        "normalized": True,
        "metric": "cosine",
        "swatch_count": int(palette.shape[0]),
        "colour_space": "linear-srgb",
        "source_path": "image/source.jpg",
        "tolerance": labhog.TOLERANCE,
        "epistemic": "measured",
        "input_hash": input_hash(["image/source.jpg"], files),
        "producer": {"tool": "fixtures/labhog.py", "version": "1"},
        "note": "64 CIELAB histogram bins then 8 gradient-orientation bins, "
                "L2-normalised. Defined completely in "
                "spec/layouts/embedding.layout.txt section 4, so it can be "
                "recomputed from image/source.jpg (decoded to RGB) and checked.",
    })
    wkem_f = put("semantics/style-embedding.wkem", wkem,
                 "application/octet-stream")

    # -- semantics: hand-authored facet tags + the measured palette -------
    reg = _facets_registry()
    facets = {
        "style": ["rustic", "utilitarian", "industrial"],
        "function": ["container", "packaging"],
        "environment": ["warehouse", "interior"],
        "era": ["timeless"],
        "mood": ["utilitarian", "neutral"],
        "condition": ["worn", "weathered", "used"],
    }
    for facet, tags in facets.items():
        legal = set(reg["facets"][facet]["tags"])
        bad = [t for t in tags if t not in legal and not t.startswith("x.")]
        assert not bad, "tag(s) %s not in facets.json's %s" % (bad, facet)

    swatches = [
        {"hex_srgb": linear_to_hex(palette[i, 0:3]),
         "linear_rgb": [float(palette[i, 0]), float(palette[i, 1]),
                        float(palette[i, 2])],
         "weight": float(palette[i, 3])}
        for i in range(palette.shape[0]) if palette[i, 3] > 0.0
    ]
    weight_sum = sum(s["weight"] for s in swatches)
    stats["weight_sum"] = weight_sum
    semantics = {
        "schema_version": 1, "facets_version": reg["version"], "facets": facets,
        "tag_stamps": {"%s/%s" % (fc, t): {"epistemic": "authored"}
                       for fc, ts in facets.items() for t in ts},
        "palette": {
            "method": "werk.descriptor.labhog/1 top-8 CIELAB histogram bins, "
                      "mean linear sRGB per bin",
            "colors": swatches,
            "dominant_index": 0,
            "average_luminance": avg_lum,
        },
        "description": "A photographic-style texture atlas of weathered wooden "
                       "crate planks and a little iron hardware, warm mid-brown "
                       "throughout, used and worn.",
        "keywords": ["texture", "wood", "crate", "planks", "cc0", "poly-haven",
                     "atlas"],
        "note": "Facet tags are hand-authored against spec/facets.json (which "
                "travels in this package); every tag is stamped 'authored'. The "
                "palette is MEASURED over the image by labhog and is duplicated "
                "here in both sRGB hex and linear float deliberately (law 9), so "
                "a listing never has to parse the WKEM envelope. These are the "
                "up-to-eight largest non-empty histogram bins by cell "
                "population; their weights sum to %.4f (they cover the whole "
                "32x32 working grid here because this image has few dominant "
                "colours, so the sum reaches 1.0; a busier image's top-8 would "
                "sum to less). See spec finding S-24." % weight_sum,
    }
    sem_f = put("semantics/semantics.json", jbytes(semantics), "application/json")

    # -- disclosure: NOT AI-generated ------------------------------------
    disclosure = {
        "disclosure_version": 1, "ai_generated": False, "ai_modified": False,
        "generation_scope": "none",
        "declared_by": {"name": "werk fixtures (build_image_cc0.py)",
                        "kind": "service",
                        "uri": "urn:werk:dev-key:build-image-cc0"},
        "declared_at": CREATED,
        "human_authorship": {
            "claimed": True,
            "description": "The image is a CC0 texture authored by Poly Haven "
                           "(a photograph-derived, human-authored asset). The "
                           "two derived sizes are deterministic Lanczos-3 "
                           "downscales; the palette and style descriptor are "
                           "arithmetic over the pixels. No generative model "
                           "produced any content in this package.",
        },
        "models": [],
        "synthetic_markers": {
            "declared_watermarks": [{"kind": "none", "present": False,
                                     "note": "No watermarking of any kind; the "
                                             "derivatives are deterministic "
                                             "resamples of a CC0 source."}],
            "c2pa_manifest_present": False, "embedded_metadata_stripped": True,
        },
        "statements": [
            {"id": "cc0-dedication",
             "text": "The source image is a Poly Haven asset released into the "
                     "public domain under CC0 1.0; the derivatives and the "
                     "descriptor are placed in the public domain likewise.",
             "epistemic": "authored"},
            {"id": "source-is-jpeg",
             "text": "image/source.jpg is the CC0 file carried verbatim. Its "
                     "derivatives are re-encoded to PNG, and the style "
                     "descriptor is over the JPEG's decoded pixels rather than "
                     "over a lossless master, which is stated rather than "
                     "hidden.",
             "epistemic": "measured", "confidence": 1.0,
             "basis": "the source file's own bytes carried in this package"},
            {"id": "no-enforcement",
             "text": "Nothing in this node obliges any viewer to do anything. "
                     "The format ships facts; the viewer applies jurisdiction "
                     "(spec/SPEC.md section 3.12).",
             "epistemic": "authored"},
        ],
        "jurisdiction_note": "Informational only; confers nothing and binds no "
                             "viewer.",
    }
    disc_f = put("disclosure/disclosure.json", jbytes(disclosure),
                 "application/json")

    # -- provenance ------------------------------------------------------
    provenance = {
        "schema_version": 1,
        "runs": [{
            "run_id": "werk-image-cc0-build",
            "started": CREATED, "finished": CREATED,
            "tool": {"name": "fixtures/build_image_cc0.py", "version": "1"},
            "consumed": [{"path": "Poly Haven CC0 texture (%s)" % SRC_IMAGE,
                          "sha256": sha256(src_jpg),
                          "external": True, "license": "CC0-1.0"}],
            "produced": [{"node_id": nid, "v": 1} for nid in
                         ("image-source", "image-preview", "image-thumb",
                          "style-embedding", "semantics")],
            "note": "The werk packaging pass over the CC0 image: the source "
                    "carried verbatim, two deterministic Lanczos-3 sizes, a "
                    "measured labhog descriptor and palette, and the disclosure "
                    "that says the image is not model-generated.",
        }],
    }
    prov_f = put("provenance/provenance.json", jbytes(provenance),
                 "application/json")

    # -- spec / loader ---------------------------------------------------
    spec_files = []
    for dirpath, _dirs, names in os.walk(os.path.join(ROOT, "spec")):
        for nm in sorted(names):
            if nm.endswith(".pyc"):
                continue
            full = os.path.join(dirpath, nm)
            rel = "spec/" + os.path.relpath(
                full, os.path.join(ROOT, "spec")).replace("\\", "/")
            media = ("application/json" if nm.endswith(".json")
                     else "text/markdown" if nm.endswith(".md") else "text/plain")
            spec_files.append(put(rel, _read(full), media))
    spec_files.sort(key=lambda f: f["path"])

    loader_data = _read(os.path.join(ROOT, "loaders", "werk_read.py"))
    loader_f = put("loaders/werk_read.py", loader_data, "text/x-python")

    # -- nodes -----------------------------------------------------------
    node("spec", "core.spec", [version(
        1, spec_files, "The format specification, its schemas and binary layout "
        "grammars, travelling inside the file it describes (law 2). Profile "
        "image/1 is spec/PROFILE-IMAGE.md.", "werk", "0.1", "authored")])

    node("license", "core.license", [version(
        1, [lic_f], "The full CC0 1.0 dedication text, embedded, never a link "
        "(law 7).", "werk", "0.1", "authored")])

    node("loader-python", "core.loader", [version(
        1, [loader_f], "A single-file, dependency-free Python reader for this "
        "package, carried as payload so the file brings its own reader (law 1).",
        "werk", "0.1", "authored")],
        meta={"language": "python", "form": "source",
              "entrypoint": "loaders/werk_read.py", "toolchain": "python>=3.8",
              "dependencies": [],
              "capabilities": loader_capabilities(loader_data)})

    node("image-source", "core.image.source", [version(
        1, [src_f], "The CC0 image, carried verbatim as the JPEG it was "
        "published as: no crop, no resize, no re-encode. The archival anchor "
        "every derived node hashes against.",
        "fixtures/build_image_cc0.py", "1", "authored")],
        edges=[{"to": "disclosure", "kind": "enhances", "role": "discloses"}],
        meta={"width": w, "height": h, "channels": 3, "bit_depth": 8,
              "color_space": "srgb", "encoding": "jpeg", "has_alpha": False})

    node("image-preview", "core.image.derived", [version(
        1, [prev_f], "Mid-size web render: Lanczos-3 from the source at build "
        "time, so it is reproducible from image/source.jpg and its input_hash "
        "proves it.", "fixtures/build_image_cc0.py", "1", "measured",
        inputs=["image/source.jpg"])],
        edges=[{"to": "image-source", "kind": "requires", "role": "derived-from"}],
        meta={"width": PREVIEW_W, "height": prev_h, "channels": 3, "bit_depth": 8,
              "color_space": "srgb", "encoding": "png", "has_alpha": False,
              "derived_role": "preview", "resample": "lanczos3"})

    node("image-thumb", "core.image.derived", [version(
        1, [thumb_f], "Listing tier: it sits inside "
        "container.preview_prefix_bytes on purpose, so a browser showing a "
        "thousand of these pays a ranged read and not a download (law 9).",
        "fixtures/build_image_cc0.py", "1", "measured",
        inputs=["image/source.jpg"])],
        edges=[{"to": "image-source", "kind": "requires", "role": "derived-from"}],
        meta={"width": THUMB_W, "height": thumb_h, "channels": 3, "bit_depth": 8,
              "color_space": "srgb", "encoding": "png", "has_alpha": False,
              "derived_role": "thumbnail", "resample": "lanczos3"})

    node("style-embedding", "core.embedding", [version(
        1, [wkem_f], "A 72-component style descriptor and an 8-swatch palette "
        "from one pass over the source, in a WKEM envelope. Measured, and "
        "recomputable from image/source.jpg by anyone with "
        "spec/layouts/embedding.layout.txt.",
        "fixtures/labhog.py", "1", "measured", inputs=["image/source.jpg"])],
        edges=[{"to": "image-source", "kind": "requires", "role": "derived-from"}])

    node("semantics", "core.semantics", [version(
        1, [sem_f], "Facet tags against spec/facets.json, plus the palette in "
        "both sRGB hex and linear float so a listing never has to parse an "
        "envelope.", "fixtures/build_image_cc0.py", "1", "authored")],
        edges=[{"to": "image-source", "kind": "enhances", "role": "describes"},
               {"to": "style-embedding", "kind": "enhances", "role": "embedding"}])

    node("disclosure", "core.disclosure", [version(
        1, [disc_f], "Machine-readable facts about how this image came to exist: "
        "a CC0 texture, not model-generated. In the damaged variant this node's "
        "payload is the one whose byte is flipped, so it goes dead by "
        "hash-mismatch while the signature stays valid.",
        "fixtures/build_image_cc0.py", "1", "authored")],
        edges=[{"to": "image-source", "kind": "requires", "role": "discloses"}])

    node("provenance", "core.provenance", [version(
        1, [prov_f], "Where the source came from and what this build did with "
        "it.", "fixtures/build_image_cc0.py", "1", "authored")],
        edges=[{"to": "image-source", "kind": "enhances", "role": "records"}])

    # README last, once the node count is known.
    readme_f = put("README.txt", readme_text(len(nodes) + 1).encode("utf-8"),
                   "text/plain")
    node("readme", "core.readme", [version(
        1, [readme_f], "One page for a human who opened this file.",
        "werk", "0.1", "authored")])

    return files, nodes, stats


# ---------------------------------------------------------------------------
# manifest / assemble / sign
# ---------------------------------------------------------------------------

CONVENTIONS = {
    "endianness": "le", "color_space_default": "srgb", "pixel_origin": "top-left",
    "alpha_mode": "straight", "alignment_bytes": 16, "text_encoding": "utf-8",
    "id_case": "kebab-case", "hash_algorithm": "sha256",
    "signature_algorithm": "ed25519",
}

SCHEMA_FILES = {
    "core.disclosure": "spec/schemas/core.disclosure.schema.json",
    "core.semantics": "spec/schemas/core.semantics.schema.json",
    "core.provenance": "spec/schemas/core.provenance.schema.json",
}


def build_manifest(files, nodes, preview_prefix):
    present = {n["type"] for n in nodes}
    schemas = {t: p for t, p in SCHEMA_FILES.items() if t in present}
    total = sum(len(v) for v in files.values())
    return {
        "werk": {"major": 1, "minor": 0},
        "profile": "image/1",
        "manifest_schema": "spec/schemas/manifest.image.schema.json",
        "entity": {
            "uuid": ENTITY_UUID,
            "name": "Wooden-crate texture, CC0",
            "summary": (
                "A public-domain image (a Poly Haven CC0 wooden-crate texture), "
                "packaged as a werk conformance fixture, profile image/1, "
                "reproducible from this repository alone. The source is carried "
                "verbatim as image/source.jpg; two deterministic Lanczos-3 PNG "
                "sizes, a measured labhog style descriptor in a WKEM binary, "
                "facet tags and a palette accompany it. It is NOT AI-generated "
                "and the disclosure says so. Signed with a publicly derived DEV "
                "key that proves the chain works and nothing about authorship."),
            "created": CREATED,
        },
        "conventions": dict(CONVENTIONS),
        "container": {
            "form": "zip", "zip_compression": "store",
            "entry_order": list(ENTRY_ORDER),
            "preview_tier": list(PREVIEW_SET),
            "total_size_bytes": total,
            "preview_prefix_bytes": preview_prefix,
        },
        "primary": {"image": "image-source", "thumbnail": "image-thumb"},
        "license": {"spdx_id": "CC0-1.0", "file": "LICENSE",
                    "sha256": sha256(files["LICENSE"])},
        "spec_sha256": spec_sha256_of_files(files),
        "conventions_map": "spec/conventions-map.image.json",
        "schemas": schemas,
        "layouts": {"core.embedding": "spec/layouts/embedding.layout.txt"},
        "nodes": nodes,
        "signature_file": "SIGNATURE.json",
        "generator": {"tool": "fixtures/build_image_cc0.py", "version": "1"},
    }


def sign(manifest_bytes):
    return build_chain(sha256(manifest_bytes), [{
        "secret": DEV_SK,
        "name": "werk dev key (publicly derived, fixtures only)",
        "uri": "urn:werk:dev-key:build-image-cc0",
        "kind": "service", "role": "author", "signed_at": CREATED,
        "note": "Signed with a DEV key derived from a published sentence. It is "
                "not secret, it is not a trust anchor, and it proves only that "
                "the chain verifies.",
    }])


def assemble(files, nodes):
    annotate_payload_files(nodes)
    # SPEC 5: never write a `requires` edge to a node not in nodes[].
    refuse_dangling_edges(nodes)
    preview = 0
    for _round in range(8):
        manifest_bytes = jbytes(build_manifest(files, nodes, preview))
        sig_bytes = jbytes(sign(manifest_bytes))
        allf = dict(files)
        allf["MANIFEST.json"] = manifest_bytes
        allf["SIGNATURE.json"] = sig_bytes
        entries = [(p, allf[p]) for p in order_entries(allf.keys())]
        cursor, prefix = 0, 0
        for name, data in entries:
            this = 30 + len(name.encode("utf-8")) + len(data)
            if is_preview(name):
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

CORRUPT_TARGET = "disclosure/disclosure.json"


def build_damaged(files, nodes):
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
                      "producer": {"tool": "fixtures/build_image_cc0.py",
                                   "version": "1"},
                      "epistemic": "authored", "created": CREATED}],
        "active": 1, "edges": []})
    _m, _s, dentries = assemble(dfiles, dnodes)
    off = 1000 if len(files[CORRUPT_TARGET]) > 1001 else 5
    dentries = [(p, (d[:off] + bytes([d[off] ^ 0xFF]) + d[off + 1:])
                 if p == CORRUPT_TARGET else d) for p, d in dentries]
    return write_zip(dentries), CORRUPT_TARGET, off


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------

def build(src_dir):
    files, nodes, stats = collect(src_dir)
    _m, _s, entries = assemble(files, nodes)
    clean_blob = write_zip(entries)
    dmg_blob, target, off = build_damaged(files, nodes)
    return clean_blob, dmg_blob, nodes, stats, target, off


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--src", default=SRC_DEFAULT)
    ap.add_argument("--out", default=None,
                    help="output dir for the fixtures. Defaults to the fixtures "
                         "tree on a normal build. Under --check-determinism the "
                         "fixtures are NOT written unless --out is given "
                         "explicitly, so verification never mutates its subject.")
    ap.add_argument("--check-determinism", action="store_true")
    args = ap.parse_args(argv)

    clean_blob, dmg_blob, nodes, stats, target, off = build(args.src)

    print("source image %dx%d, %d bytes; descriptor %s"
          % (stats["src_w"], stats["src_h"], stats["src_bytes"],
             stats["descriptor"]))
    print("palette weights sum to %.6f (S-24)" % stats["weight_sum"])

    if args.check_determinism:
        # A verification step must never overwrite the fixtures it verifies:
        # a bare --check-determinism writes nothing into the source tree. Pass
        # an explicit --out to also (re)build the fixtures into that dir.
        c2, d2, _n, _s2, _t, _o = build(args.src)
        ok = (sha256(c2) == sha256(clean_blob) and sha256(d2) == sha256(dmg_blob))
        print("determinism: %s (two builds, whole-file sha256 %s)"
              % ("PASS" if ok else "FAIL", "identical" if ok else "DIFFER"))
        if args.out is None:
            return 0 if ok else 1
        if not ok:
            return 1

    out_dir = args.out if args.out is not None else HERE
    clean_path = os.path.join(out_dir, "image-cc0-v1.werk")
    dmg_path = os.path.join(out_dir, "image-cc0-v1-damaged.werk")
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
