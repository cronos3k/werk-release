#!/usr/bin/env python3
"""build_presentation.py -- the presentation/1 release fixture, written deterministically with
the release library (profiles/tools/profilekit.py).

The deck "Harbour Lights review", 960 x 540 pt, one master, two layouts, three slides:

  slide 1  title slide: the logo (a picture shape), the title, a subtitle
  slide 2  "The result": the photograph of the harbour (a picture shape) with a caption
  slide 3  "Costs": a table (header row plus four rows), speaker notes

Two embedded files, both REUSED BY CONTENT HASH from the other release fixtures:

  media-10  the vector-art/1 fixture itself (profiles/fixtures/vector-art-v1.werk), byte for
            byte: encoding `zip`, definition `formats` (spec/formats/zip.md and the zlib-deflate
            definition it requires, each with its reference tool). Its PNG rendition
            (media-10-png, core.media.image, `measured`) is that package's own preview
            (primary.image) taken out of it unchanged -- the same sha256 as its preview node.
  media-11  the raster-layers/1 fixture's composite preview PNG, byte for byte: encoding `png`,
            definition `base` -- the same bytes as the rich-document/1 fixture's picture.

plus the deck outline (core.slide.outline, `measured`, the exact form of section 3.6) and the
reference reader as a core.tool node. No slide preview is written (this builder has no renderer).

usage: build_presentation.py [--out profiles/fixtures/presentation-v1.werk]
                             [--vector profiles/fixtures/vector-art-v1.werk]
                             [--raster profiles/fixtures/raster-layers-v1.werk]
"""
import argparse
import json
import os
import struct
import sys
import zipfile
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILES = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROFILES, "tools"))
import profilekit as K  # noqa: E402

W, H = 960, 540


def rgb(r, g, b, a=255):
    return OrderedDict([("r", r), ("g", g), ("b", b), ("a", a)])


def colour(r, g, b):
    return OrderedDict([("base", OrderedDict([("kind", "rgb"), ("rgb", rgb(r, g, b))]))])


def xfrm(x, y, w, h):
    return OrderedDict([("x", x), ("y", y), ("w", w), ("h", h)])


def para(text, size=None, bold=None, italic=None, level=None):
    props = OrderedDict()
    if size is not None:
        props["size"] = size
    if bold:
        props["bold"] = True
    if italic:
        props["italic"] = True
    run = OrderedDict([("text", text)])
    if props:
        run["props"] = props
    p = OrderedDict()
    if level is not None:
        p["level"] = level
    p["runs"] = [run]
    return p


def text_shape(sid, name, box, paragraphs, ph=None, fill=None):
    s = OrderedDict([("id", sid), ("name", name), ("xfrm", xfrm(*box)), ("kind", OrderedDict([("type", "shape")])),
                     ("geom", OrderedDict([("kind", "preset"), ("name", "rect")]))])
    if ph:
        s["ph"] = OrderedDict([("kind", ph), ("idx", 0)])
    if fill:
        s["fill"] = fill
    s["line"] = OrderedDict([("fill", OrderedDict([("kind", "none")]))])
    s["text"] = OrderedDict([("paragraphs", paragraphs)])
    return s


def picture(sid, name, box, media, descr):
    return OrderedDict([("id", sid), ("name", name), ("descr", descr), ("xfrm", xfrm(*box)),
                        ("kind", OrderedDict([("type", "picture"), ("fill", OrderedDict([("media", media)]))]))])


def table(sid, box, cols, rows):
    def cell(t, bold=False):
        return OrderedDict([("borders", [None, None, None, None]), ("grid_span", 1), ("h_merge", False), ("row_span", 1),
                            ("text", OrderedDict([("body", OrderedDict()),
                                                  ("paragraphs", [para(t, bold=bold, level=0)])])),
                            ("v_merge", False)])
    return OrderedDict([
        ("id", sid), ("name", "Cost table"), ("xfrm", xfrm(*box)), ("geom", OrderedDict([("kind", "preset"), ("name", "rect")])),
        ("kind", OrderedDict([("type", "table"), ("band_col", False), ("band_row", True), ("cols", cols),
                              ("first_col", False), ("first_row", True), ("last_col", False), ("last_row", True),
                              ("rows", [OrderedDict([("cells", [cell(c, bold=(i == 0 or i == len(rows) - 1)) for c in r]),
                                                     ("height", 40.0)]) for i, r in enumerate(rows)]),
                              ("style", "medium2-accent1")]))])


COST_ROWS = [("Work", "Hours", "Cost (EUR)"), ("Scraping and priming", "36", "1,980.00"),
             ("Red and white coats", "48", "2,640.00"), ("Lamp-room glazing", "12", "1,140.00"),
             ("Gallery railing", "18", "990.00"), ("Total", "114", "6,750.00")]


def slides():
    s1 = OrderedDict([("id", 3), ("layout", 2), ("shapes", [
        picture(20, "Logo", (280.0, 60.0, 400.0, 200.0), 10, "The Harbour Lights logo."),
        text_shape(21, "Title 1", (60.0, 290.0, 840.0, 90.0), [para(u"Harbour Lights", size=54, bold=True)], ph="ctrTitle"),
        text_shape(22, "Subtitle 2", (60.0, 390.0, 840.0, 60.0), [para(u"Autumn maintenance review", size=24)],
                   ph="subTitle")])])
    s2 = OrderedDict([("id", 4), ("layout", 5), ("shapes", [
        text_shape(30, "Title 1", (60.0, 30.0, 840.0, 80.0), [para(u"The result", size=40, bold=True)], ph="title"),
        picture(31, "Photograph", (224.0, 120.0, 512.0, 384.0), 11, "The lighthouse at dusk."),
        text_shape(32, "Caption", (224.0, 506.0, 512.0, 26.0), [para(u"The harbour at dusk, after the repaint.", size=14,
                                                                      italic=True)])])])
    s3 = OrderedDict([("id", 6), ("layout", 5), ("shapes", [
        text_shape(40, "Title 1", (60.0, 30.0, 840.0, 80.0), [para(u"Costs", size=40, bold=True)], ph="title"),
        table(41, (120.0, 130.0, 720.0, 240.0), [360.0, 140.0, 220.0], COST_ROWS)]),
        ("notes", OrderedDict([("paragraphs", [para(u"The figures come from the Lighthouse costs workbook."),
                                               para(u"VAT is not included.")])]))])
    return [s1, s2, s3]


def outline(sl):
    """core.slide.outline, PROFILE-PRESENTATION.md 3.6."""
    def ptext(p):
        return u"".join(u"\u000b" if r.get("kind") == "break" else r.get("text", u"") for r in p.get("runs") or [])

    def clean(t):
        out = []
        for ch in t:
            o = ord(ch)
            if ch in u"\n\r\t\u000b":
                out.append(u" ")
            elif o < 0x20 or 0x7F <= o <= 0x9F:
                out.append(u"�")
            else:
                out.append(ch)
        return u"".join(out)
    lines = []
    for n, s in enumerate(sl, 1):
        title_shape = next((x for x in s["shapes"] if (x.get("ph") or {}).get("kind") in ("title", "ctrTitle")), None)
        title = u"\n".join(ptext(p) for p in title_shape["text"]["paragraphs"]) if title_shape else u""
        lines.append(u"Slide %d: %s" % (n, clean(title)))
        for x in s["shapes"]:
            if x is title_shape:
                continue
            for p in (x.get("text") or {}).get("paragraphs") or []:
                t = ptext(p)
                if t:
                    lines.append(u"\t" * ((p.get("level") or 0) + 1) + clean(t))
            k = x.get("kind") or {}
            if k.get("type") == "table":
                for row in k["rows"]:
                    cells = [u"\n".join(ptext(p) for p in c["text"]["paragraphs"]) for c in row["cells"]
                             if not c.get("h_merge") and not c.get("v_merge")]
                    if any(c.strip() for c in cells):
                        lines.append(u"\t" + u" | ".join(clean(c) for c in cells))
        for p in (s.get("notes") or {}).get("paragraphs") or []:
            t = ptext(p)
            if t:
                lines.append(u"Notes: " + clean(t))
        lines.append(u"")
    if lines and lines[-1] == u"":
        lines.pop()
    return (u"\n".join(lines) + u"\n").encode("utf-8") if sl else u"(no slides)\n".encode("utf-8")


MASTER = OrderedDict([
    ("schema_version", 1), ("role", "slide"), ("master", OrderedDict([
        ("id", 1), ("name", "Harbour master"),
        ("theme", OrderedDict([
            ("name", "Harbour"),
            ("colors", OrderedDict([("name", "Harbour"), ("colors", [
                rgb(0, 0, 0), rgb(255, 255, 255), rgb(11, 37, 69), rgb(244, 244, 240), rgb(19, 168, 168),
                rgb(214, 40, 57), rgb(255, 209, 102), rgb(46, 111, 216), rgb(138, 92, 216), rgb(46, 163, 111),
                rgb(46, 111, 216), rgb(122, 91, 166)])])),
            ("fonts", OrderedDict([("name", "Harbour"), ("major", OrderedDict([("latin", "Source Sans 3")])),
                                   ("minor", OrderedDict([("latin", "Source Sans 3")]))])),
            ("format", OrderedDict([("name", "Harbour")]))])),
        ("background", OrderedDict([("kind", "fill"), ("fill", OrderedDict([
            ("kind", "solid"), ("color", OrderedDict([("base", OrderedDict([("kind", "scheme"), ("slot", "lt2")]))]))]))]))]))])

README = (u"Harbour Lights review\n\n"
          u"This is a werk package, profile `presentation/1`: a three-slide deck that embeds the "
          u"Harbour Lights logo (a vector-art/1 package, carried whole) and a photograph, both "
          u"byte-identical to files of other packages. It carries its own format specification, "
          u"three readers, a reference reader of this profile, and its licence.\n\n"
          u"    python loaders/werk_read.py <this file> --verify --strict\n"
          u"    python tools/reader-presentation/read_presentation.py <this file>\n\n"
          u"Where to read next: HOW-TO-READ.md, spec/PROFILE-PRESENTATION.md, spec/CRAFT-BASE.md, spec/SPEC.md.\n")
LICENSE = (u"CC0 1.0 Universal (public domain dedication).\n\n"
           u"This deck and the files it embeds were made by scripts for the werk release fixtures; to "
           u"the extent possible under law, the author has waived all copyright and related rights to "
           u"them. https://creativecommons.org/publicdomain/zero/1.0/\n")


def build(out, vector, raster):
    vbytes = open(vector, "rb").read()
    vz = zipfile.ZipFile(vector)
    vman = json.loads(vz.read("MANIFEST.json"))
    pid = vman["primary"]["image"]
    pnode = next(n for n in vman["nodes"] if n["node_id"] == pid)
    prec = pnode["versions"][pnode["active"] - 1]["files"][0]
    logo_png = vz.read(prec["path"])
    assert K.sha(logo_png) == prec["sha256"]
    photo = zipfile.ZipFile(raster).read("preview/composite.png")

    pp = K.ProfilePackage("presentation", "Harbour Lights review",
                          summary="presentation/1 release fixture: three slides, a vector logo and a photograph "
                                  "reused by content hash, a table, speaker notes.",
                          readme_text=README, license_text=LICENSE, spdx_id="CC0-1.0")
    w = pp.w
    pp.use_format("zlib-deflate")
    pp.use_format("zip")
    sl = slides()
    doc = OrderedDict([
        ("schema_version", 1), ("slide_size", OrderedDict([("width", W), ("height", H)])),
        ("notes_size", OrderedDict([("width", 540), ("height", 720)])), ("first_slide_number", 1), ("next_id", 50),
        ("slides", [OrderedDict([("id", s["id"]), ("node", "slide-%d" % s["id"])]) for s in sl]),
        ("masters", [OrderedDict([("id", 1), ("node", "master-1"),
                                  ("layouts", [OrderedDict([("id", 2), ("node", "layout-2")]),
                                               OrderedDict([("id", 5), ("node", "layout-5")])])])]),
        ("media", [OrderedDict([("id", 10), ("node", "media-10"), ("rendition", "media-10-png")]),
                   OrderedDict([("id", 11), ("node", "media-11")])]),
        ("props", OrderedDict([("title", "Harbour Lights review")]))])

    def add(nid, ntype, path, obj, note, edges=()):
        w.add_node(nid, ntype, [w.file(path, K.cjson(obj), "application/json")], note=note, edges=list(edges))

    add("master-1", "core.slide.master", "deck/masters/master-1.json", MASTER, "The slide master: theme and background.")
    add("layout-2", "core.slide.layout", "deck/layouts/layout-2.json",
        OrderedDict([("schema_version", 1), ("master", "master-1"),
                     ("layout", OrderedDict([("id", 2), ("name", "Title Slide"), ("kind", "title")]))]),
        "The title-slide layout.", [("master-1", "requires", "master")])
    add("layout-5", "core.slide.layout", "deck/layouts/layout-5.json",
        OrderedDict([("schema_version", 1), ("master", "master-1"),
                     ("layout", OrderedDict([("id", 5), ("name", "Title Only"), ("kind", "titleOnly")]))]),
        "The title-only layout.", [("master-1", "requires", "master")])
    for s in sl:
        uses = [("media-%d" % m, "enhances", "uses") for m in sorted(set(
            x["kind"]["fill"]["media"] for x in s["shapes"] if x.get("kind", {}).get("type") == "picture"))]
        add("slide-%d" % s["id"], "core.slide.slide", "deck/slides/slide-%d.json" % s["id"],
            OrderedDict([("schema_version", 1), ("slide", s)]), "Slide %d of the deck." % s["id"],
            [("layout-%d" % s["layout"], "enhances", "layout")] + uses)
    # media: the vector-art package (zip) and the photograph (png)
    asset10 = OrderedDict([("schema_version", 1), ("id", 10), ("name", "harbour-lights-logo.werk"),
                           ("content_type", "application/zip"), ("embedded", True), ("link", None),
                           ("encoding", "zip"), ("definition", "formats")])
    w.add_node("media-10", "core.media.asset",
               [w.file("deck/media/media-10/asset.json", K.cjson(asset10), "application/json", role="payload"),
                w.file("deck/media/media-10/harbour-lights-logo.werk", vbytes, "application/zip", role="media")],
               note="The Harbour Lights logo: the vector-art/1 package itself, embedded byte for byte.",
               meta=OrderedDict([("file_formats", OrderedDict([("media", "zip")]))]),
               payload_file="deck/media/media-10/asset.json")
    w.add_node("media-10-png", "core.media.image", [w.file("deck/media/media-10/rendition.png", logo_png, "image/png")],
               note="The logo as PNG: the embedded package's own preview (its primary.image), unchanged.",
               epistemic="measured", input_files=["deck/media/media-10/harbour-lights-logo.werk"],
               input_params=OrderedDict([("decoder", "vector-art/1 primary.image, taken out unchanged"),
                                         ("path_in_package", prec["path"])]),
               meta=OrderedDict([("role", "rendition"), ("of", "media-10")]),
               edges=[("media-10", "enhances", "derived-from")])
    asset11 = OrderedDict([("schema_version", 1), ("id", 11), ("name", "harbour-at-dusk.png"),
                           ("content_type", "image/png"), ("embedded", True), ("link", None),
                           ("encoding", "png"), ("definition", "base")])
    w.add_node("media-11", "core.media.asset",
               [w.file("deck/media/media-11/asset.json", K.cjson(asset11), "application/json", role="payload"),
                w.file("deck/media/media-11/harbour-at-dusk.png", photo, "image/png", role="media")],
               note="The photograph of the harbour at dusk, a PNG.", payload_file="deck/media/media-11/asset.json")
    ol = outline(sl)
    w.add_node("outline", "core.slide.outline", [w.file("deck/outline.txt", ol, "text/plain")],
               note="The text of the deck, slide by slide (section 3.6).", epistemic="measured",
               input_files=["deck/slides/slide-%d.json" % s["id"] for s in sl],
               input_params=OrderedDict([("form", "presentation-outline-1")]),
               edges=[("slide-%d" % s["id"], "requires", "derived-from") for s in sl])
    add("document", "core.slide.document", "deck/document.json", doc,
        "The deck structure: slides in show order, the master and its layouts, embedded files.",
        [("slide-%d" % s["id"], "enhances", "contains") for s in sl]
        + [(n, "enhances", "contains") for n in ("master-1", "layout-2", "layout-5", "media-10", "media-10-png", "media-11")])
    w.set_primary("document", "document")
    for p in ("HOW-TO-READ.md", "revisions/", "deck/document.json", "deck/outline.txt"):
        w.preview(p)
    pp.add_reference_reader()
    data = pp.write(out, "First save of the presentation/1 release fixture: Harbour Lights review.")
    sys.path.insert(0, HERE)
    import read_presentation as R
    got = R.read(out)
    assert not got["dead"] and not got["file_failures"], got["dead"]
    assert [s["title"] for s in got["slides"]] == ["Harbour Lights", "The result", "Costs"]
    med = {m["id"]: m for m in got["media"]}
    assert med[10]["media_sha256"] == K.sha(vbytes) and med[10]["rendition_sha256"] == K.sha(logo_png)
    assert med[11]["media_sha256"] == K.sha(photo)
    assert got["outline_matches"] is True
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(PROFILES, "fixtures", "presentation-v1.werk"))
    ap.add_argument("--vector", default=os.path.join(PROFILES, "fixtures", "vector-art-v1.werk"))
    ap.add_argument("--raster", default=os.path.join(PROFILES, "fixtures", "raster-layers-v1.werk"))
    a = ap.parse_args()
    data = build(a.out, a.vector, a.raster)
    print("%s %d bytes sha256 %s" % (a.out, len(data), K.sha(data)))


if __name__ == "__main__":
    main()
