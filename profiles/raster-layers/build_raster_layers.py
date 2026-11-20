#!/usr/bin/env python3
"""build_raster_layers.py -- the raster-layers/1 release fixture, written deterministically
with the release library (profiles/tools/profilekit.py).

The document "Harbour at dusk", 512 x 384 px, RGB, 8 bits per channel, layer tree bottom to top:

  layer-1  "Sky and sea"   raster, the whole canvas; its surface is stored as PhotoCraft
                           stores pixels: tile envelopes with sample_encoding "planes-delta",
                           each tile file a zlib stream (format zlib-deflate, carried)
  layer-4  "Foreground"    group, blend PassThrough, holding
    layer-2  "Lighthouse"  raster with a layer MASK (a gray surface that fades the tower's
                           foot into the sea); stored in the minimal-writer form (plain
                           envelopes, raw samples)
  layer-3  "Warm grade"    adjustment layer, Levels (per-channel + master), opacity 0.75

plus `composite` and `thumbnail` previews (core.raster.preview, measured: flattened by the
rules of PROFILE-RASTER-LAYERS.md 5.2-5.3 implemented below), the zlib-deflate definition with
its reference inflater, and the reference reader (core.tool, source only).

usage: build_raster_layers.py [--out profiles/fixtures/raster-layers-v1.werk]
"""
import argparse
import os
import struct
import sys
import zlib
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import profilekit as K  # noqa: E402

W, H = 512, 384
TILE = 256
RGBA = ["red", "green", "blue", "alpha"]


# ---------------------------------------------------------------- the pictures (u8)

def sky_and_sea(x, y):
    if y < 240:
        t = y / 239.0
        r, g, b = 40 + (250 - 40) * t, 90 + (180 - 90) * t, 170 + (120 - 170) * t
    else:
        wave = ((x + 3 * (y - 240)) // 12 + (y - 240) // 9) % 4
        r, g, b = 20 + 6 * wave, 60 + 8 * wave, 110 + 10 * wave
    return int(round(r)), int(round(g)), int(round(b)), 255


def lighthouse(x, y):
    dx, dy = x - 320, y - 110
    if dx * dx + dy * dy <= 18 * 18:
        return 255, 230, 120, 255
    if 300 <= x < 340 and 128 <= y < 300:
        band = ((y - 128) // 30) % 2
        return (200, 40, 40, 255) if band == 0 else (245, 245, 240, 255)
    return 0, 0, 0, 0


def foot_mask(x, y):
    if y < 240:
        return 255
    if y >= 300:
        return 0
    return int(round(255 * (300 - y) / 60.0))


def canvas(fn, channels):
    buf = bytearray(W * H * channels)
    for y in range(H):
        for x in range(W):
            v = fn(x, y)
            i = (y * W + x) * channels
            if channels == 1:
                buf[i] = v
            else:
                buf[i:i + channels] = bytes(v)
    return buf


# ---------------------------------------------------------------- surfaces (layout txt)

def tiles_of(buf, C, default):
    """{(tx, ty): tile bytes} for every tile holding a pixel that differs from the default
    pixel; pixels outside the canvas hold the default pixel."""
    out = OrderedDict()
    default = bytes(default)
    for ty in range((H + TILE - 1) // TILE):
        for tx in range((W + TILE - 1) // TILE):
            t = bytearray(default * (TILE * TILE))
            differs = False
            for r in range(TILE):
                y = ty * TILE + r
                if y >= H:
                    break
                x0 = tx * TILE
                n = min(TILE, W - x0)
                row = buf[(y * W + x0) * C:(y * W + x0 + n) * C]
                t[r * TILE * C:r * TILE * C + n * C] = row
                if row != default * n:
                    differs = True
            if differs:
                out[(tx, ty)] = bytes(t)
    return out


def planes_delta(tile, C, esz=1):
    N = 65536 * C
    e = bytearray(len(tile))
    for k in range(esz):
        p = tile[k::esz]
        for i in range(N):
            e[k * N + i] = p[i] if i < C else (p[i] - p[i - C]) & 0xFF
    return bytes(e)


def surface(node_id, buf, mode, channels, default, compressed):
    """(index bytes, [(role, file bytes, envelope sha256)], tile count)."""
    C = len(channels)
    fmt = {"pixel_mode": mode, "has_alpha": channels[-1] == "alpha", "channels": channels,
           "sample_type": "u8", "tile_size": TILE, "nonfinite": False}
    tiles = tiles_of(buf, C, default)
    files, rows = [], []
    if tiles:
        role = "ztiles-p0-p0" if compressed else "tiles-p0-p0"
        keys = dict(fmt, part="tiles", tile_count=len(tiles))
        if compressed:
            keys["sample_encoding"] = "planes-delta"
            data = b"".join(planes_delta(t, C) for t in tiles.values())
            env = K.envelope(b"WKX0", "core.raster.surface", keys, [("samples", "u8", [len(data)], 1, data)])
            stored = zlib.compress(env, 3)
        else:
            data = b"".join(tiles.values())
            env = K.envelope(b"WKX0", "core.raster.surface", keys,
                             [("samples", "u8", [len(tiles), 256, 256, C], C, data)])
            stored = env
        files.append((role, stored, K.sha(env)))
        order = list(tiles)  # slot = position in the samples section
        for (tx, ty) in sorted(tiles, key=lambda t: (t[1], t[0])):
            rows.append(struct.pack("<iiii", tx, ty, 0, order.index((tx, ty))))
    ikeys = dict(fmt, part="index", tile_count=len(tiles), tile_files=[f[0] for f in files])
    if compressed and files:
        ikeys["tile_file_sha256"] = [f[2] for f in files]
    index = K.envelope(b"WKX0", "core.raster.surface", ikeys, [
        ("default-pixel", "u8", [C], 1, bytes(default)),
        ("tile-index", "i32", [len(rows), 4], 16, b"".join(rows))])
    return index, files, len(tiles)


# ---------------------------------------------------------------- compositing (5.2, 5.3)

def levels(rec, v):
    lo, hi = rec["in_black"], rec["in_white"]
    t = min(1.0, max(0.0, (v - lo) / (hi - lo)))
    t = t ** (1.0 / rec["gamma"])
    return rec["out_black"] + (rec["out_white"] - rec["out_black"]) * t


def composite(bg, lh, mask, adj, adj_opacity):
    """Flatten: Normal blends, the group is PassThrough, the raster mask's effective value is
    1 - density * (1 - v), the adjustment replaces the picture beneath it within its coverage
    (= its opacity, no mask). Result straight-alpha RGBA u8."""
    out = bytearray(W * H * 4)
    pc, ms = adj["Levels"]["per_channel"], adj["Levels"]["master"]
    for i in range(W * H):
        b = [bg[4 * i + c] / 255.0 for c in range(3)]
        a = lh[4 * i + 3] / 255.0 * (mask[i] / 255.0)
        if a > 0:
            b = [(1 - a) * b[c] + a * (lh[4 * i + c] / 255.0) for c in range(3)]
        g = [levels(ms, levels(pc[c], b[c])) for c in range(3)]
        b = [(1 - adj_opacity) * b[c] + adj_opacity * g[c] for c in range(3)]
        out[4 * i:4 * i + 4] = bytes([int(round(min(1.0, max(0.0, v)) * 255)) for v in b] + [255])
    return out


# ---------------------------------------------------------------- payloads

def doc_json(tree, layer_ids):
    return OrderedDict([
        ("schema_version", 1), ("name", "Harbour at dusk"), ("width", W), ("height", H),
        ("resolution_dpi", 72.0), ("color_mode", "Rgb"), ("sample_type", "U8"),
        ("color_space", None), ("icc_profile", None), ("layers", tree), ("channels", []),
        ("quick_mask", None), ("quick_mask_unselected", False), ("selection", None),
        ("patterns", []), ("paths", []), ("work_path", None), ("clipping_path", None),
        ("layer_comps", []), ("last_applied_comp", None), ("last_document_state", None),
        ("text_styles", None), ("variables", None), ("metadata", None),
        ("guides", OrderedDict([("horizontal", [240.0]), ("vertical", [320.0])])),
        ("global_light", OrderedDict([("angle", 120.0), ("altitude", 30.0)])),
        ("color_table", None), ("duotone", None),
        ("measurement", OrderedDict([("scale", OrderedDict([("pixel_length", 1.0), ("logical_length", 1.0),
                                                             ("units", "pixels")])),
                                     ("count_groups", []), ("active_count_group", 0), ("ruler", None)])),
        ("notes", []), ("slices", OrderedDict([("groupName", ""), ("list", [])])), ("timeline", None),
        ("file_encoding", OrderedDict()), ("psd", None), ("fonts", []),
        ("app", OrderedDict([("document_id", 0)]))])


def layer_json(name, content, blend="Normal", opacity=1.0, mask=None):
    return OrderedDict([
        ("schema_version", 1), ("name", name), ("visible", True),
        ("locks", OrderedDict([("transparency", False), ("pixels", False), ("position", False),
                               ("artboard", False), ("all", False)])),
        ("blend", blend), ("opacity", opacity), ("fill_opacity", 1.0), ("clipped", False),
        ("mask", mask), ("vector_mask", None),
        ("effects", OrderedDict([("enabled", True), ("items", []), ("reference", None)])),
        ("label", "None"), ("content", content), ("psd_id", None), ("psd", None), ("fill_cache", None),
        ("link_group", None), ("excluded_channels", 0), ("blend_if", OrderedDict([("ranges", [])])),
        ("advanced", OrderedDict([("knockout", "none"), ("blendInterior", False), ("blendClipped", True),
                                  ("transparencyShapes", True), ("layerMaskHidesEffects", False),
                                  ("vectorMaskHidesEffects", False)])),
        ("video", None)])


def lv(in_black=0.0, in_white=1.0, gamma=1.0, out_black=0.0, out_white=1.0):
    return OrderedDict([("in_black", in_black), ("in_white", in_white), ("gamma", gamma),
                        ("out_black", out_black), ("out_white", out_white)])


ADJUSTMENT = OrderedDict([("Levels", OrderedDict([
    ("master", lv(gamma=1.25, out_black=0.0625, out_white=0.9375)),
    ("per_channel", [lv(gamma=1.125), lv(), lv(gamma=0.875)]),
    ("space", "Rgb"),
    ("black", lv())]))])
ADJ_OPACITY = 0.75

README = (u"Harbour at dusk\n\n"
          u"This is a werk package, profile `raster-layers/1`: a layered raster image document "
          u"(three layers and a group: a background, a masked lighthouse in a group, a Levels "
          u"adjustment). It carries its own format specification, three readers, a reference "
          u"reader of this profile, and its licence. You need no application to read it.\n\n"
          u"    python loaders/werk_read.py <this file> --verify --strict\n"
          u"    python tools/reader-raster-layers/read_raster_layers.py <this file>\n\n"
          u"Where to read next: HOW-TO-READ.md, spec/PROFILE-RASTER-LAYERS.md, spec/CRAFT-BASE.md, "
          u"spec/SPEC.md.\n")
LICENSE = (u"CC0 1.0 Universal (public domain dedication).\n\n"
           u"The pictures in this package were generated by a script for the werk release fixtures; "
           u"to the extent possible under law, the author has waived all copyright and related "
           u"rights to them. https://creativecommons.org/publicdomain/zero/1.0/\n")


def build(out):
    pp = K.ProfilePackage("raster-layers", "Harbour at dusk",
                          summary="raster-layers/1 release fixture: 512 x 384 px, Rgb, 8 bits per channel, "
                                  "3 layers and a group, a mask and an adjustment.",
                          readme_text=README, license_text=LICENSE, spdx_id="CC0-1.0")
    w = pp.w
    pp.use_format("zlib-deflate")
    bg = canvas(sky_and_sea, 4)
    lh = canvas(lighthouse, 4)
    mk = canvas(foot_mask, 1)

    tree = [OrderedDict([("layer", "layer-1")]),
            OrderedDict([("layer", "layer-4"), ("children", [OrderedDict([("layer", "layer-2")])])]),
            OrderedDict([("layer", "layer-3")])]
    layer_ids = ["layer-1", "layer-4", "layer-2", "layer-3"]
    doc = K.pjson(doc_json(tree, layer_ids))
    w.add_node("document", "core.raster.document",
               [w.file("document/document.json", doc, "application/json")],
               note="The document structure: canvas, colour model and the layer tree, bottom to top.",
               meta=OrderedDict([("width", W), ("height", H), ("color_mode", "Rgb"), ("sample_type", "U8")]),
               edges=[(l, "enhances", "contains") for l in layer_ids])

    def add_surface(nid, buf, mode, channels, default, compressed, usage, owner, edges=()):
        index, files, n = surface(nid, buf, mode, channels, default, compressed)
        fl = [w.file("surfaces/%s/surface.wkx" % nid, index, "application/octet-stream",
                     role="payload" if files else None)]
        ext = ".wkxz" if compressed else ".wkx"
        for role, data, _s in files:
            fl.append(w.file("surfaces/%s/%s%s" % (nid, role.replace("ztiles", "tiles"), ext),
                             data, "application/octet-stream", role=role))
        meta = OrderedDict([("usage", usage), ("owner", owner), ("channels", channels), ("bits_per_sample", 8)])
        if compressed and files:
            meta["file_formats"] = OrderedDict((role, "zlib-deflate") for role, _d, _s in files)
        w.add_node(nid, "core.raster.surface", fl,
                   note="Pixels of %s (%s), %d stored tile(s)." % (owner, usage, n), meta=meta,
                   payload_file="surfaces/%s/surface.wkx" % nid if files else None, edges=list(edges))

    # layer-1: background
    add_surface("layer-1-pixels", bg, "rgb", RGBA, [0, 0, 0, 0], True, "layer-pixels", "layer-1")
    w.add_node("layer-1", "core.raster.layer",
               [w.file("layers/layer-1/layer.json",
                       K.pjson(layer_json("Sky and sea", OrderedDict([("kind", "raster"), ("pixels", "layer-1-pixels")]))),
                       "application/json")],
               note="The background: a dusk sky over a banded sea.", meta=OrderedDict([("kind", "raster")]),
               edges=[("layer-1-pixels", "enhances", "pixels")])
    # layer-4: group
    w.add_node("layer-4", "core.raster.layer",
               [w.file("layers/layer-4/layer.json",
                       K.pjson(layer_json("Foreground", OrderedDict([("kind", "group"), ("expanded", True), ("artboard", None)]),
                                          blend="PassThrough")),
                       "application/json")],
               note="A pass-through group holding the lighthouse.", meta=OrderedDict([("kind", "group")]))
    # layer-2: lighthouse with mask
    add_surface("layer-2-pixels", lh, "rgb", RGBA, [0, 0, 0, 0], False, "layer-pixels", "layer-2")
    mask = OrderedDict([("surface", "layer-2-mask"), ("enabled", True), ("linked", True), ("density", 1.0),
                        ("feather", 0.0)])
    w.add_node("layer-2", "core.raster.layer",
               [w.file("layers/layer-2/layer.json",
                       K.pjson(layer_json("Lighthouse", OrderedDict([("kind", "raster"), ("pixels", "layer-2-pixels")]),
                                          mask=mask)),
                       "application/json")],
               note="The lighthouse, its foot faded into the sea by a layer mask.", meta=OrderedDict([("kind", "raster")]),
               edges=[("layer-2-pixels", "enhances", "pixels"), ("layer-2-mask", "enhances", "mask")])
    add_surface("layer-2-mask", mk, "grayscale", ["gray"], [255], False, "layer-mask", "layer-2",
                edges=[("layer-2", "requires", "belongs-to")])
    # layer-3: adjustment
    w.add_node("layer-3", "core.raster.layer",
               [w.file("layers/layer-3/layer.json",
                       K.pjson(layer_json("Warm grade", OrderedDict([("kind", "adjustment"), ("adjustment", ADJUSTMENT)]),
                                          opacity=ADJ_OPACITY)),
                       "application/json")],
               note="A Levels adjustment that warms the whole picture.", meta=OrderedDict([("kind", "adjustment")]))

    # previews (derived): inputs = files of every core.raster.* node, document first, then manifest order
    order = ["document"] + [n for n in w.nodes if n != "document" and w.nodes[n]["type"].startswith("core.raster.")]
    inputs = []
    for nid in order:
        inputs += [f["path"] for f in w.nodes[nid]["versions"][0]["files"]]
    comp = composite(bg, lh, mk, ADJUSTMENT, ADJ_OPACITY)
    for nid, side in (("thumbnail", 64), ("composite", 256)):
        pw, ph, px = K.downscale_area(W, H, comp, side)
        w.add_node(nid, "core.raster.preview",
                   [w.file("preview/%s.png" % nid, K.png_rgba(pw, ph, px), "image/png")],
                   note="The document flattened (every visible layer blended) and scaled to at most %d px." % side,
                   epistemic="measured", input_files=inputs,
                   input_params=OrderedDict([("derivation", "flattened-composite"), ("max_side", side),
                                             ("resample", "area-average")]),
                   meta=OrderedDict([("usage", nid), ("width", pw), ("height", ph), ("color_space", "srgb"),
                                     ("bits_per_sample", 8), ("channels", RGBA), ("alpha_mode", "straight")]),
                   edges=[(n, "requires", "rendered-from") for n in order])
    w.set_primary("document", "document")
    w.set_primary("image", "composite")
    w.set_primary("thumbnail", "thumbnail")
    for p in ("HOW-TO-READ.md", "revisions/", "document/document.json", "preview/", "layers/"):
        w.preview(p)
    pp.add_reference_reader()
    data = pp.write(out, "First save of the raster-layers/1 release fixture: 3 layers and a group, 512 x 384 px.")
    # ground truth: the reference reader must give back exactly the canvases written
    sys.path.insert(0, HERE)
    import read_raster_layers as R
    got = R.read(out)
    want = {"layer-1-pixels": K.sha(bytes(bg)), "layer-2-pixels": K.sha(bytes(lh)), "layer-2-mask": K.sha(bytes(mk))}
    flat = {}

    def walk(ls):
        for L in ls:
            for k in ("pixels",):
                if L.get(k):
                    flat[L[k]["node"]] = L[k]["samples_sha256"]
            if L.get("mask"):
                flat[L["mask"]["surface"]["node"]] = L["mask"]["surface"]["samples_sha256"]
            walk(L.get("children") or [])
    walk(got["layers"])
    assert flat == want, (flat, want)
    assert not got["dead"] and not got["file_failures"]
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(HERE), "fixtures", "raster-layers-v1.werk"))
    a = ap.parse_args()
    data = build(a.out)
    print("%s %d bytes sha256 %s" % (a.out, len(data), K.sha(data)))


if __name__ == "__main__":
    main()
