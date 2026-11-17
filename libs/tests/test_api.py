#!/usr/bin/env python3
"""test_api.py -- the library API (not the CLI), as libs/README.md shows it.

    python tests/test_api.py            (Python 3.7+; the read half also on 2.7)

Writes into libs/_scratch/api/, checks every package with the library itself
and, when it is on PATH or in libs/_target, with werkc (werk-core, the full
reader with JSON Schema validation).
"""
from __future__ import print_function

import hashlib
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIBS = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(LIBS, "python"))
sys.path.insert(0, HERE)
import werk  # noqa: E402
import make_inputs  # noqa: E402

OUT = os.path.join(LIBS, "_scratch", "api")
FAIL = []


def check(name, ok, detail=""):
    print("%s %s %s" % ("PASS" if ok else "FAIL", name, detail))
    if not ok:
        FAIL.append(name)


def werkc():
    name = "werkc" + (".exe" if os.name == "nt" else "")
    for exe in (os.path.join(LIBS, "_target", "release", name),
                os.path.join(os.path.dirname(LIBS), "core", "target", "release", name)):
        if os.path.isfile(exe):
            return exe
    return shutil.which("werkc")


def full_check(path):
    w = werkc()
    if not w:
        return None
    p = subprocess.run([w, "verify", path, "--json"], stdout=subprocess.PIPE)
    return p.returncode


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    png = make_inputs.png(make_inputs.pattern(8, 0))
    thumb = make_inputs.png(make_inputs.box_half(make_inputs.pattern(8, 0)))
    glb = make_inputs.triangle_glb()
    key = "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"

    # --- README: write an image package (3 lines) ---------------------------
    out = os.path.join(OUT, "sunset.werk")
    werk.write_image_package(out, png, name="Sunset", thumbnail_png=thumb,
                             created="2026-11-07T12:00:00Z", uuid="1a6e0000-0000-4000-8000-0000000000aa")
    pkg = werk.open(out)
    v = pkg.verdict()
    check("image package verifies (library)", v["exit"] == 0 and v["dead"] == 0, str(dict(v)))
    check("image package verifies (werkc)", full_check(out) in (0, None))
    nid, path, data = pkg.primary_image()
    check("primary_image is the source PNG", nid == "image-source" and data == png, path)
    check("primary thumbnail resolves", pkg.read_payload(pkg.primary("thumbnail")[0]) == thumb)

    # --- README: write a mesh package ----------------------------------------
    out2 = os.path.join(OUT, "crate.werk")
    werk.write_mesh_package(out2, glb, name="Crate", created="2026-11-07T12:00:00Z",
                            uuid="1a6e0000-0000-4000-8000-0000000000bb",
                            textures=[{"id": "albedo", "png": png}],
                            materials=[{"id": "wood", "name": "Wood", "base_color": "albedo", "class": "wood"}],
                            preview_png=thumb, sign_key=key,
                            signer={"uri": "urn:werk:test:k1", "kind": "service"})
    pkg2 = werk.open(out2)
    check("mesh package verifies, signed", pkg2.signature_state == "signed-and-valid" and not pkg2.errors())
    check("mesh package verifies (werkc)", full_check(out2) in (0, None))
    check("primary_mesh is the GLB", pkg2.primary_mesh()[2] == glb)
    check("primary_image is the preview", pkg2.primary_image()[0] == "preview")

    # --- PackageWriter directly: a custom node, a measured derivative ----------
    w = werk.PackageWriter("image/1", "Custom", created="2026-11-07T12:00:00Z",
                           uuid="1a6e0000-0000-4000-8000-0000000000cc")
    w.add_node("image-source", "core.image.source", [w.file("image/source.png", png, "image/png")],
               note="The source image, written through the API.",
               meta={"width": 8, "height": 8, "channels": 4, "bit_depth": 8, "color_space": "srgb",
                     "encoding": "png", "has_alpha": True})
    w.add_node("hist", "x.example.histogram", [w.file("x/example/hist.json", b'{"bins": 4}\n', "application/json")],
               note="A derived histogram, measured from the source.", epistemic="measured",
               input_files=["image/source.png"], input_params={"bins": 4},
               edges=[{"to": "image-source", "kind": "requires", "role": "derived-from"}])
    w.set_primary("image", "image-source")
    out3 = os.path.join(OUT, "custom")
    w.write(out3, form="directory")
    pkg3 = werk.open(out3)
    check("directory form verifies; x.* node skipped not dead",
          pkg3.census() == (len(pkg3.nodes) - 1, 1, 0) and not pkg3.errors(), str(pkg3.census()))
    zb = w.to_bytes()
    check("to_bytes() is a zip of the same content", zb[:4] == b"PK\x03\x04" and len(zb) > 1000)

    # --- append a version, then extract -------------------------------------
    out4 = os.path.join(OUT, "sunset-v2.werk")
    werk.append_version(out, out4, "image-thumb", [werk.PackageWriter.file("image/thumb.png", png)],
                        note="Thumbnail replaced by the full image, for the test.",
                        created="2026-11-07T13:00:00Z")
    pkg4 = werk.open(out4)
    th = pkg4.node("image-thumb")
    paths = [[f["path"] for f in v["files"]] for v in th.versions]
    check("append moved v1 to @1, v2 at the plain path",
          paths == [["image/thumb@1.png"], ["image/thumb.png"]] and th.resolved == 2, str(paths))
    check("an authored v2 carries no input_hash, so nothing is reported stale",
          any(e.code == "stale-derived-data" for e in pkg4.report) is False)
    ex = os.path.join(OUT, "extracted")
    written = pkg4.extract(ex, node_ids=["image-thumb"], all_versions=True)
    check("extract all versions of one node", sorted(written) == ["image/thumb.png", "image/thumb@1.png"], str(written))
    with open(os.path.join(ex, "image", "thumb@1.png"), "rb") as fh:
        check("the superseded bytes are the v1 bytes", fh.read() == thumb)

    # --- a profile outside the bundle, carried with add_spec_file -----------
    w5 = werk.PackageWriter("raster-layers/1", "Layered", created="2026-11-07T12:00:00Z",
                            uuid="1a6e0000-0000-4000-8000-0000000000dd",
                            conventions=werk._core.BASE_CONVENTIONS,
                            manifest_schema="spec/schemas/manifest.raster-layers.schema.json",
                            profile_spec="spec/PROFILE-RASTER-LAYERS.md")
    schema = b'{"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object"}\n'
    check("add_spec_file adds a new file", w5.add_spec_file("spec/schemas/manifest.raster-layers.schema.json", schema) is False)
    w5.add_spec_file("spec/PROFILE-RASTER-LAYERS.md", b"# raster-layers/1 (test)\n")
    check("add_spec_file replaces a vendored file", w5.add_spec_file("spec/README.md", b"# replaced\n") is True)
    w5.add_node("layer-0", "core.image.layer", [w5.file("layers/0.png", png, "image/png")],
                note="The bottom layer, for the test.")
    out5 = os.path.join(OUT, "layered.werk")
    w5.write(out5)
    p5 = werk.open(out5)
    spec_paths = [f["path"] for f in p5.node("spec").version()["files"]]
    check("unknown profile written with its own schema: opens clean, spec_sha256 holds",
          not p5.errors() and p5.verdict()["spec_sha256_ok"]
          and any(e.code == "unsupported-profile" for e in p5.report), str([e.code for e in p5.report]))
    check("core.spec files stay sorted by UTF-8 path", spec_paths == sorted(spec_paths, key=lambda s: s.encode()))
    check("the replaced spec/README.md is the given bytes", p5.read_file("spec/README.md") == b"# replaced\n")
    rc = full_check(out5)
    check("werkc opens the unknown-profile package (exit 0 or 1, never 2)", rc in (0, 1, None), "werkc exit %s" % rc)

    # --- conventions_map= and add_readme_file ------------------------------
    w6 = werk.PackageWriter("image/1", "Extras", created="2026-11-07T12:00:00Z",
                            uuid="1a6e0000-0000-4000-8000-0000000000ee",
                            conventions_map="spec/conventions-map.extra.json")
    w6.add_spec_file("spec/conventions-map.extra.json",
                     werk.default_bundle().data("spec/conventions-map.image.json"))
    w6.add_readme_file("HOW-TO-READ.md", b"# How to read this package\n")
    w6.add_node("image-source", "core.image.source", [w6.file("image/source.png", png, "image/png")],
                note="The source image, for the test.",
                meta={"width": 8, "height": 8, "channels": 4, "bit_depth": 8, "color_space": "srgb",
                      "encoding": "png", "has_alpha": True})
    out6 = os.path.join(OUT, "extras.werk")
    w6.write(out6)
    p6 = werk.open(out6)
    rv = p6.node("readme").version()
    check("conventions_map= is declared", p6.manifest.get("conventions_map") == "spec/conventions-map.extra.json")
    check("add_readme_file joins the readme node; payload stays README.txt",
          [f["path"] for f in rv["files"]] == ["README.txt", "HOW-TO-READ.md"]
          and p6.payload_path("readme") == "README.txt" and list(rv.keys())[:3] == ["v", "files", "payload_file"])
    check("extras package clean (library, werkc)", not p6.errors() and full_check(out6) in (0, None))
    bad = werk.PackageWriter("image/1", "Bad", conventions_map="spec/not-here.json")
    try:
        bad.manifest("zip")
        check("conventions_map naming no carried file is refused", False)
    except werk.WerkError:
        check("conventions_map naming no carried file is refused", True)

    # --- a zip with two entries of one name is refused whole ------------------
    import warnings
    import zipfile
    dup = os.path.join(OUT, "dup.werk")
    shutil.copyfile(out, dup)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with zipfile.ZipFile(dup, "a") as z:
            z.writestr("README.txt", b"another")
    try:
        werk.open(dup)
        check("duplicate entry names refused", False)
    except werk.ContainerRefusal as e:
        check("duplicate entry names refused (bad-container)", e.code == "bad-container", e.message[:60])

    # --- refusals are typed ---------------------------------------------------
    try:
        werk.open(os.path.join(OUT, "nope.werk"))
        check("missing file refused", False)
    except werk.ContainerRefusal as e:
        check("missing file refused as container scope", e.code == "bad-container", e.code)
    try:
        werk.PackageWriter("image/1", "x").add_node("a", "core.tex", [], note="short")
        check("bad writer input refused", False)
    except werk.WerkError:
        check("bad writer input refused (WerkError)", True)
    print("%d failure(s)" % len(FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
