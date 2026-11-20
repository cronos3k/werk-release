#!/usr/bin/env python3
"""build_vector_art.py -- the vector-art/1 release fixture, written deterministically with the
release library (profiles/tools/profilekit.py).

The document "Harbour Lights logo": one artboard 400 x 200 pt and two layers, bottom first:

  layer-1 "Mark"  a disc filled with a LINEAR gradient, a light beam filled with a RADIAL
                  gradient that fades to transparent, and a group "Lighthouse" of four solid
                  paths (roof, lamp, tower, band); the tower's band is a compound path
  layer-2 "Type"  point type "HARBOUR LIGHTS" (Source Sans 3 Bold, 28 pt) and a tagline run in a
                  second style; the font is named, not embedded (fonts[] says so: status
                  `not-requested`), as the profile allows

plus the swatch library (core.paint.swatches), the text-style library (core.text.styles), the
preview (core.vector.preview, PNG of the artboard rendered by the rasterizer below; `measured`;
type is NOT drawn in it, because this builder has no font to set it in, and `input_params`
says so), and the reference reader as a core.tool node. The preview PNG is reused, byte for
byte, by the presentation/1 fixture.

usage: build_vector_art.py [--out profiles/fixtures/vector-art-v1.werk]
"""
import argparse
import math
import os
import struct
import sys
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import profilekit as K  # noqa: E402

AW, AH = 400, 200
KAPPA = 0.5522847498307936


def c32(v):
    """A colour component as the profile writes it: binary32, shortest round-trip decimal."""
    x = struct.unpack("<f", struct.pack("<f", v))[0]
    for d in range(1, 10):
        s = "%.*g" % (d, x)
        if struct.unpack("<f", struct.pack("<f", float(s)))[0] == x:
            return float(s)
    return x


def rgb(hexs):
    h = hexs.lstrip("#")
    return OrderedDict([("model", "rgb"), ("r", c32(int(h[0:2], 16) / 255.0)),
                        ("g", c32(int(h[2:4], 16) / 255.0)), ("b", c32(int(h[4:6], 16) / 255.0))])


def solid(hexs):
    return OrderedDict([("type", "solid"), ("color", rgb(hexs))])


def stop(offset, hexs, opacity=1.0):
    return OrderedDict([("offset", offset), ("color", rgb(hexs)), ("opacity", opacity), ("midpoint", 0.5)])


def gradient(kind, start, end, stops):
    return OrderedDict([("type", "gradient"),
                        ("gradient", OrderedDict([("kind", kind), ("stops", stops)])),
                        ("geom", OrderedDict([("start", OrderedDict([("x", start[0]), ("y", start[1])])),
                                              ("end", OrderedDict([("x", end[0]), ("y", end[1])]))]))])


def fill(paint):
    return OrderedDict([("items", [OrderedDict([("kind", "fill"), ("paint", paint)])])])


def poly(points, closed=True):
    return OrderedDict([("subpaths", [OrderedDict([("anchors", [OrderedDict([("p", [float(x), float(y)])])
                                                                for x, y in points]), ("closed", closed)])])])


def circle(cx, cy, r):
    k = KAPPA * r
    pts = [((cx, cy - r), (cx - k, cy - r), (cx + k, cy - r)),
           ((cx + r, cy), (cx + r, cy - k), (cx + r, cy + k)),
           ((cx, cy + r), (cx + k, cy + r), (cx - k, cy + r)),
           ((cx - r, cy), (cx - r, cy + k), (cx - r, cy - k))]
    anchors = [OrderedDict([("p", [float(p[0]), float(p[1])]), ("in", [float(i[0]), float(i[1])]),
                            ("out", [float(o[0]), float(o[1])]), ("kind", "Smooth")]) for p, i, o in pts]
    return OrderedDict([("subpaths", [OrderedDict([("anchors", anchors), ("closed", True)])])])


def path_obj(oid, name, path, appearance, rule=None):
    kind = OrderedDict([("type", "path"), ("path", path)])
    if rule:
        kind["rule"] = rule
    return OrderedDict([("id", oid), ("name", name), ("appearance", appearance), ("kind", kind)])


NAVY, TEAL, YELLOW, RED, WHITE = "#0B2545", "#13A8A8", "#FFD166", "#D62839", "#F4F4F0"

DISC = path_obj(3, "Disc", circle(100, 100, 80),
                fill(gradient("Linear", (100.0, 20.0), (100.0, 180.0), [stop(0.0, NAVY), stop(1.0, TEAL)])))
BEAM = path_obj(4, "Beam", poly([(118, 70), (390, 40), (390, 110), (118, 82)]),
                fill(gradient("Radial", (118.0, 76.0), (390.0, 76.0), [stop(0.0, YELLOW, c32(0.9)),
                                                                     stop(1.0, YELLOW, 0.0)])))
ROOF = path_obj(6, "Roof", poly([(90, 68), (110, 68), (100, 54)]), fill(solid(NAVY)))
LAMP = path_obj(7, "Lamp", poly([(92, 68), (108, 68), (108, 84), (92, 84)]), fill(solid(YELLOW)))
TOWER = path_obj(8, "Tower", poly([(94, 84), (106, 84), (112, 160), (88, 160)]), fill(solid(RED)))
BAND = OrderedDict([
    ("id", 9), ("name", "Band"), ("appearance", fill(solid(WHITE))),
    ("kind", OrderedDict([("type", "compound"), ("rule", "EvenOdd"), ("children", [
        path_obj(10, "Band upper", poly([(95.2, 100), (104.8, 100), (105.6, 110), (94.4, 110)]), OrderedDict([("items", [])])),
        path_obj(11, "Band lower", poly([(93.6, 120), (106.4, 120), (107.2, 130), (92.8, 130)]), OrderedDict([("items", [])])),
    ])]))])
LIGHTHOUSE = OrderedDict([("id", 5), ("name", "Lighthouse"),
                          ("kind", OrderedDict([("type", "group"), ("children", [TOWER, BAND, LAMP, ROOF]),
                                                ("clip", False)]))])


def run_style(size, style, colour, tracking):
    return OrderedDict([
        ("font_family", "Source Sans 3"), ("font_style", style), ("size", size), ("tracking", tracking),
        ("baseline_shift", 0.0), ("h_scale", 100.0), ("v_scale", 100.0), ("rotation", 0.0),
        ("fill", solid(colour)), ("stroke", OrderedDict([("type", "none")])), ("stroke_width", 0.0),
        ("underline", False), ("strikethrough", False), ("all_caps", False)])


PARA = OrderedDict([("justify", "Left"), ("left_indent", 0.0), ("right_indent", 0.0), ("first_line_indent", 0.0),
                    ("space_before", 0.0), ("space_after", 0.0), ("hyphenate", False)])
WORDMARK = OrderedDict([
    ("id", 13), ("name", "Wordmark"), ("appearance", OrderedDict([("items", [])])),
    ("kind", OrderedDict([("type", "text"), ("kind", OrderedDict([("kind", "point")])),
                          ("xf", [1.0, 0.0, 0.0, 1.0, 196.0, 150.0]),
                          ("runs", [OrderedDict([("text", u"HARBOUR LIGHTS\n"), ("style", run_style(28.0, "Bold", NAVY, 40.0))]),
                                    OrderedDict([("text", u"Fisherman’s Wharf · est. 1897"),
                                                 ("style", run_style(12.0, "Regular", TEAL, 0.0))])]),
                          ("para", PARA)]))])


def layer(oid, name, children, colour_preset):
    return OrderedDict([("schema_version", 1), ("layer", OrderedDict([
        ("id", oid), ("name", name),
        ("kind", OrderedDict([("type", "layer"), ("color", OrderedDict([("Preset", colour_preset)])),
                              ("children", children)]))]))])


# ---------------------------------------------------------------- the rasterizer (preview)

def flatten(path, steps=24):
    polys = []
    for sub in path["subpaths"]:
        a = sub["anchors"]
        pts = [tuple(a[0]["p"])]
        n = len(a)
        for i in range(1, n + (1 if sub["closed"] else 0)):
            A, B = a[i - 1], a[i % n]
            p0, p1, p2, p3 = A["p"], A.get("out", A["p"]), B.get("in", B["p"]), B["p"]
            if p1 == p0 and p2 == p3:
                pts.append(tuple(p3))
                continue
            for s in range(1, steps + 1):
                t = s / float(steps); u = 1 - t
                pts.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                            u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]))
        polys.append(pts)
    return polys


SS = 4  # 4 x 4 samples per pixel


def coverage(polys, W, H, rule="NonZero"):
    """Fraction of each pixel's 16 sample points inside the polygons (scanline crossings)."""
    cov = [0] * (W * H)
    edges = []
    for pts in polys:
        for i in range(len(pts)):
            (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % len(pts)]
            if y0 != y1:
                edges.append((x0, y0, x1, y1, 1 if y1 > y0 else -1))
    for sy in range(H * SS):
        y = (sy + 0.5) / SS
        xs = []
        for (x0, y0, x1, y1, w) in edges:
            if (y0 <= y < y1) or (y1 <= y < y0):
                xs.append((x0 + (y - y0) * (x1 - x0) / (y1 - y0), w))
        if not xs:
            continue
        xs.sort()
        wind = 0
        for j in range(len(xs) - 1):
            wind += xs[j][1]
            inside = (wind != 0) if rule != "EvenOdd" else (j % 2 == 0)
            if not inside:
                continue
            a, b = xs[j][0], xs[j + 1][0]
            s0 = max(0, int(math.ceil(a * SS - 0.5)))
            s1 = min(W * SS - 1, int(math.floor(b * SS - 0.5)))
            row = (sy // SS) * W
            for sx in range(s0, s1 + 1):
                cov[row + sx // SS] += 1
    return [c / float(SS * SS) for c in cov]


def colour_of(c):
    return (c["r"], c["g"], c["b"])


def paint_at(paint, x, y):
    if paint["type"] == "solid":
        return colour_of(paint["color"]) + (1.0,)
    g, geo = paint["gradient"], paint["geom"]
    sx, sy, ex, ey = geo["start"]["x"], geo["start"]["y"], geo["end"]["x"], geo["end"]["y"]
    if g["kind"] == "Linear":
        dx, dy = ex - sx, ey - sy
        t = ((x - sx) * dx + (y - sy) * dy) / (dx * dx + dy * dy)
    else:
        t = math.hypot(x - sx, y - sy) / math.hypot(ex - sx, ey - sy)
    t = min(1.0, max(0.0, t))
    st = g["stops"]
    for i in range(len(st) - 1):
        if st[i]["offset"] <= t <= st[i + 1]["offset"]:
            a, b = st[i], st[i + 1]
            u = (t - a["offset"]) / ((b["offset"] - a["offset"]) or 1.0)
            ca, cb = colour_of(a["color"]), colour_of(b["color"])
            return tuple(ca[k] + (cb[k] - ca[k]) * u for k in range(3)) + (a["opacity"] + (b["opacity"] - a["opacity"]) * u,)
    last = st[-1] if t >= st[-1]["offset"] else st[0]
    return colour_of(last["color"]) + (last["opacity"],)


def render(objects, W, H):
    """Paths and compound paths with fill items, bottom first, Normal 'over' compositing; type
    is skipped (no font). Returns straight-alpha RGBA u8."""
    acc = [(0.0, 0.0, 0.0, 0.0)] * (W * H)  # premultiplied

    def draw(obj, inherited=None):
        k = obj["kind"]
        if k["type"] in ("group", "layer"):
            for ch in k["children"]:
                draw(ch)
            return
        if k["type"] not in ("path", "compound"):
            return
        polys = flatten(k["path"]) if k["type"] == "path" else sum((flatten(c["kind"]["path"]) for c in k["children"]), [])
        items = (obj.get("appearance") or {}).get("items") or []
        for it in items:
            if it["kind"] != "fill" or it["paint"]["type"] == "none":
                continue
            cov = coverage(polys, W, H, k.get("rule", "NonZero"))
            for i, c in enumerate(cov):
                if c <= 0:
                    continue
                x, y = i % W + 0.5, i // W + 0.5
                r, g, b, a = paint_at(it["paint"], x, y)
                a *= c
                R, G, B, A = acc[i]
                acc[i] = (r * a + R * (1 - a), g * a + G * (1 - a), b * a + B * (1 - a), a + A * (1 - a))
    for o in objects:
        draw(o)
    out = bytearray(W * H * 4)
    for i, (R, G, B, A) in enumerate(acc):
        if A > 0:
            out[4 * i:4 * i + 3] = bytes(int(round(min(1.0, v / A) * 255)) for v in (R, G, B))
        out[4 * i + 3] = int(round(A * 255))
    return bytes(out)


README = (u"Harbour Lights logo\n\n"
          u"This is a werk package, profile `vector-art/1`: a vector logo (paths with linear and "
          u"radial gradients, a group, a compound path, and type). It carries its own format "
          u"specification, three readers, a reference reader of this profile, and its licence.\n\n"
          u"    python loaders/werk_read.py <this file> --verify --strict\n"
          u"    python tools/reader-vector-art/read_vector_art.py <this file>\n\n"
          u"Where to read next: HOW-TO-READ.md, spec/PROFILE-VECTOR-ART.md, spec/CRAFT-BASE.md, spec/SPEC.md.\n")
LICENSE = (u"CC0 1.0 Universal (public domain dedication).\n\n"
           u"The artwork in this package was made by a script for the werk release fixtures; to the "
           u"extent possible under law, the author has waived all copyright and related rights to it. "
           u"https://creativecommons.org/publicdomain/zero/1.0/\n")


def payloads():
    artboard = OrderedDict([("schema_version", 1), ("id", 1), ("name", "Logo"),
                            ("rect", OrderedDict([("x0", 0.0), ("y0", 0.0), ("x1", float(AW)), ("y1", float(AH))]))])
    l1 = layer(1, "Mark", [DISC, BEAM, LIGHTHOUSE], 0)
    l2 = layer(12, "Type", [WORDMARK], 1)
    swatches = OrderedDict([("schema_version", 1), ("swatches", [
        OrderedDict([("name", n), ("paint", solid(c)), ("global", True), ("spot", False)])
        for n, c in (("Harbour Navy", NAVY), ("Sea Teal", TEAL), ("Beacon Yellow", YELLOW), ("Signal Red", RED))]),
        ("groups", [])])
    doc = OrderedDict([("schema_version", 1), ("title", "Harbour Lights logo"), ("model_version", 1),
                       ("units", "Points"), ("color_mode", "Rgb"), ("artboards", ["artboard-1"]),
                       ("layers", ["layer-1", "layer-2"]), ("swatches", "swatches"),
                       ("symbols", []), ("patterns", []), ("images", []),
                       ("fonts", [OrderedDict([("family", "Source Sans 3"), ("style", s), ("status", "not-requested"),
                                               ("reason", "The release fixture builder embeds no font files.")])
                                  for s in ("Bold", "Regular")]),
                       ("next_object_id", 14)])
    return doc, artboard, l1, l2, swatches


def build(out):
    pp = K.ProfilePackage("vector-art", "Harbour Lights logo",
                          summary="vector-art/1 release fixture: a logo with linear and radial gradients, a "
                                  "group, a compound path and point type.",
                          readme_text=README, license_text=LICENSE, spdx_id="CC0-1.0")
    w = pp.w
    doc, artboard, l1, l2, swatches = payloads()
    files = OrderedDict()

    def add(nid, ntype, path, obj, note, edges=()):
        data = K.cjson(obj)
        files[nid] = path
        w.add_node(nid, ntype, [w.file(path, data, "application/json")], note=note, edges=list(edges))

    add("document", "core.vector.document", "vector/document.json", doc,
        "The document structure: artboards, layers, libraries and fonts by reference.",
        [(n, "enhances", "contains") for n in ("artboard-1", "layer-1", "layer-2", "swatches")])
    add("artboard-1", "core.vector.artboard", "vector/artboards/artboard-1.json", artboard, "The logo artboard, 400 x 200 pt.")
    add("layer-1", "core.vector.layer", "vector/layers/layer-1.json", l1, "The mark: disc, beam and lighthouse.")
    add("layer-2", "core.vector.layer", "vector/layers/layer-2.json", l2, "The wordmark and tagline, as live type.")
    add("swatches", "core.paint.swatches", "vector/swatches.json", swatches, "The document's four named colours.")
    # preview: rendered here; type not drawn (no font), and input_params says so
    px = render([l1["layer"], l2["layer"]], AW, AH)
    png = K.png_rgba(AW, AH, px)
    inputs = [files[n] for n in ("document", "artboard-1", "layer-1", "layer-2")]
    w.add_node("preview", "core.vector.preview", [w.file("preview/artboard.png", png, "image/png")],
               note="The first artboard rendered to PNG at 1 px per point; type is not drawn in it.",
               epistemic="measured", input_files=inputs,
               input_params=OrderedDict([("background", "transparent"), ("height", AH), ("pixels_per_point", "1"),
                                         ("region", ["0", "0", str(AW), str(AH)]), ("rendered", True),
                                         ("renderer", "werk-release build_vector_art.py"), ("renderer_version", "1"),
                                         ("type_drawn", False), ("width", AW)]),
               edges=[(n, "requires", "derived-from") for n in ("document", "artboard-1", "layer-1", "layer-2")])
    w.set_primary("document", "document")
    w.set_primary("image", "preview")
    for p in ("HOW-TO-READ.md", "revisions/", "vector/document.json", "preview/"):
        w.preview(p)
    pp.add_reference_reader()
    data = pp.write(out, "First save of the vector-art/1 release fixture: the Harbour Lights logo.")
    sys.path.insert(0, HERE)
    import read_vector_art as R
    got = R.read(out)
    assert not got["dead"] and not got["file_failures"], got["dead"]
    assert got["text"] == [u"HARBOUR LIGHTS\nFisherman’s Wharf · est. 1897"], got["text"]
    assert got["preview"]["png_sha256"] == K.sha(png)
    return data, png


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(HERE), "fixtures", "vector-art-v1.werk"))
    a = ap.parse_args()
    data, _png = build(a.out)
    print("%s %d bytes sha256 %s" % (a.out, len(data), K.sha(data)))


if __name__ == "__main__":
    main()
