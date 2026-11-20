#!/usr/bin/env python3
"""build_rich_document.py -- the rich-document/1 release fixture, written deterministically with
the release library (profiles/tools/profilekit.py).

The document "Harbour report": one run of the body (core.text.blocks: a JSON header plus the
blocks as a zlib stream) holding a heading, styled paragraphs (bold, italic, a coloured run, a
non-ASCII character so that run lengths count UTF-8 bytes), an inline picture, a second
heading, a 4-column table with a header row and five rows, and a closing paragraph; the style
sheet (Normal, Heading1, Caption), the document properties, the picture as a core.media.image
node (role `original`: the PNG IS the raster-layers/1 fixture's composite preview, byte for
byte, read from that package -- reuse by content hash), and the derived plain text
(core.preview.text, `measured`, procedure rich-document-plain-text-1). The zlib-deflate
definition and its reference inflater travel with it; the reference reader is a core.tool node.

usage: build_rich_document.py [--out profiles/fixtures/rich-document-v1.werk]
                              [--raster profiles/fixtures/raster-layers-v1.werk]
"""
import argparse
import os
import struct
import sys
import zipfile
import zlib
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILES = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROFILES, "tools"))
import profilekit as K  # noqa: E402

FFFC = u"￼"


def para(text, runs, style=None, objects=None):
    """runs: list of (substring, props-or-None); lengths are counted in UTF-8 bytes."""
    joined = u"".join(s for s, _p in runs)
    assert joined == text, (joined, text)
    p = OrderedDict([("kind", "para"), ("text", text),
                     ("runs", [OrderedDict([("len", len(s.encode("utf-8")))] + ([("props", pr)] if pr else []))
                               for s, pr in runs])])
    if style:
        p["props"] = OrderedDict([("style", style)])
    if objects:
        p["objects"] = objects
    return p


def plain(text):
    return para(text, [(text, None)])


def cell(text, bold=False, align=None):
    p = para(text, [(text, OrderedDict([("bold", True)]) if bold else None)])
    if align:
        p.setdefault("props", OrderedDict())["align"] = align
    return OrderedDict([("blocks", [p])])


ROWS = [("Work", "Crew", "Hours", "Cost (EUR)"),
        ("Scraping and priming", "4", "36", "1980"),
        ("Red and white coats", "4", "48", "2640"),
        ("Lamp-room glazing", "2", "12", "1150"),
        ("Gallery railing", "3", "18", "990"),
        ("Total", "", "114", "6760")]

IMAGE_KEY = "harbour-at-dusk.png"


def blocks(png_w, png_h):
    b = []
    b.append(para(u"Harbour report — autumn", [(u"Harbour report — autumn", None)], style="Heading1"))
    b.append(para(u"The lighthouse at Fisherman’s Wharf was repainted in September. This report lists the work, "
                  u"its cost, and one picture of the result.",
                  [(u"The lighthouse at Fisherman’s Wharf", OrderedDict([("bold", True)])),
                   (u" was repainted in ", None),
                   (u"September", OrderedDict([("italic", True), ("color", OrderedDict([("Rgb", [214, 40, 57])]))])),
                   (u". This report lists the work, its cost, and one picture of the result.", None)]))
    img = OrderedDict([("type", "image"), ("media", IMAGE_KEY), ("w", float(png_w)), ("h", float(png_h)),
                       ("alt", u"The lighthouse at dusk, its foot fading into the sea.")])
    b.append(para(FFFC, [(FFFC, None)], objects=[img]))
    b.append(para(u"Figure 1. The harbour at dusk.", [(u"Figure 1. The harbour at dusk.", None)], style="Caption"))
    b.append(para(u"Costs", [(u"Costs", None)], style="Heading1"))
    rows = []
    for i, r in enumerate(ROWS):
        rows.append(OrderedDict([("cells", [cell(c, bold=(i == 0 or i == len(ROWS) - 1),
                                                 align=("right" if j >= 1 else None)) for j, c in enumerate(r)])]))
    b.append(OrderedDict([("kind", "table"), ("grid", [180.0, 60.0, 60.0, 100.0]), ("rows", rows)]))
    b.append(para(u"Prepared by the harbour office.", [(u"Prepared by the harbour office.", OrderedDict([("italic", True)]))]))
    return b


def plain_text(blks, depth=0):
    """rich-document-plain-text-1 (PROFILE-RICH-DOCUMENT.md 3.11)."""
    def clean(s):
        out = []
        for ch in s:
            o = ord(ch)
            if ch in u"\x0c\x0e":
                out.append(u"\n")
            elif ch in u"\n\t":
                out.append(ch)
            elif o < 0x20 or 0x7F <= o <= 0x9F:
                continue
            else:
                out.append(ch)
        return u"".join(out)
    out = []
    for blk in blks:
        if blk["kind"] == "para":
            objs, k, t = blk.get("objects") or [], 0, []
            for ch in blk["text"]:
                if ch == FFFC:
                    o = objs[k] if k < len(objs) else {}
                    k += 1
                    rep = {"field": o.get("result"), "equation": o.get("linear"), "ruby": o.get("base"),
                           "opaque": o.get("text")}.get(o.get("type")) or u""
                    t.append(clean(rep))
                else:
                    t.append(ch)
            out.append(clean(u"".join(t)) + u"\n")
        elif blk["kind"] == "table" and depth < 16:
            for row in blk["rows"]:
                cells = [plain_text(c["blocks"], depth + 1).rstrip(u"\n").replace(u"\n", u" ") for c in row["cells"]]
                out.append(u"\t".join(cells) + u"\n")
    return u"".join(out)


README = (u"Harbour report\n\n"
          u"This is a werk package, profile `rich-document/1`: a styled text document with headings, "
          u"formatted runs, a picture and a table. It carries its own format specification, three "
          u"readers, a reference reader of this profile, and its licence.\n\n"
          u"    python loaders/werk_read.py <this file> --verify --strict\n"
          u"    python tools/reader-rich-document/read_rich_document.py <this file>\n\n"
          u"Where to read next: HOW-TO-READ.md, spec/PROFILE-RICH-DOCUMENT.md, spec/CRAFT-BASE.md, spec/SPEC.md.\n")
LICENSE = (u"CC0 1.0 Universal (public domain dedication).\n\n"
           u"This document was written by a script for the werk release fixtures; to the extent possible "
           u"under law, the author has waived all copyright and related rights to it. "
           u"https://creativecommons.org/publicdomain/zero/1.0/\n")

STYLES = OrderedDict([
    ("defaultChr", OrderedDict([("font", "Source Serif 4"), ("lang", "en-GB"), ("size", 11.0)])),
    ("defaultPara", OrderedDict([("spaceAfter", 8.0)])), ("defaultParaPresent", True), ("schema_version", 1),
    ("styles", [
        OrderedDict([("basedOn", None), ("builtin", False), ("chr", OrderedDict()), ("hidden", False), ("id", "Normal"),
                     ("kind", "paragraph"), ("linked", None), ("name", "Normal"), ("next", None), ("para", OrderedDict()),
                     ("priority", None), ("quick", True), ("table", None)]),
        OrderedDict([("basedOn", "Normal"), ("builtin", False),
                     ("chr", OrderedDict([("bold", True), ("color", OrderedDict([("Rgb", [11, 37, 69])])), ("size", 16.0)])),
                     ("hidden", False), ("id", "Heading1"), ("kind", "paragraph"), ("linked", None), ("name", "Heading 1"),
                     ("next", "Normal"),
                     ("para", OrderedDict([("keepNext", True), ("outlineLevel", 0), ("spaceAfter", 4.0), ("spaceBefore", 12.0)])),
                     ("priority", None), ("quick", True), ("table", None)]),
        OrderedDict([("basedOn", "Normal"), ("builtin", False),
                     ("chr", OrderedDict([("italic", True), ("size", 9.0)])), ("hidden", False), ("id", "Caption"),
                     ("kind", "paragraph"), ("linked", None), ("name", "Caption"), ("next", "Normal"),
                     ("para", OrderedDict([("align", "center")])), ("priority", None), ("quick", True), ("table", None)])])])
PROPERTIES = OrderedDict([
    ("core", OrderedDict([("category", ""), ("created", "2026-11-20T00:00:00Z"), ("creator", "Harbour office"),
                          ("description", "Repainting of the lighthouse, autumn."), ("keywords", "harbour; lighthouse"),
                          ("lastModifiedBy", ""), ("modified", ""), ("revision", 1), ("subject", "Maintenance"),
                          ("title", "Harbour report")])),
    ("custom", [OrderedDict([("kind", "lpwstr"), ("name", "Department"), ("value", "Harbour office")])]),
    ("schema_version", 1)])


def composite_png(raster_pkg):
    z = zipfile.ZipFile(raster_pkg)
    return z.read("preview/composite.png")


def build(out, raster):
    png = composite_png(raster)
    pw, ph = struct.unpack(">II", png[16:24])
    pp = K.ProfilePackage("rich-document", "Harbour report",
                          summary="rich-document/1 release fixture: headings, styled runs, a picture and a table.",
                          readme_text=README, license_text=LICENSE, spdx_id="CC0-1.0")
    w = pp.w
    pp.use_format("zlib-deflate")
    blks = blocks(pw, ph)
    arr = (u"[\n" + u",\n".join(K.cjson(b).decode("utf-8").rstrip(u"\n") for b in blks) + u"\n]\n").encode("utf-8")
    stored = zlib.compress(arr, 6)
    header = OrderedDict([("schema_version", 1), ("story", OrderedDict([("kind", "body")])),
                          ("blocks", OrderedDict([("count", len(blks)), ("role", "blocks"), ("format", "zlib-deflate"),
                                                  ("stored_size", len(stored)), ("stored_sha256", K.sha(stored)),
                                                  ("inflated_size", len(arr)), ("inflated_sha256", K.sha(arr))]))])
    w.add_node("body-000001", "core.text.blocks",
               [w.file("text/body-000001.json", K.cjson(header), "application/json", role="payload"),
                w.file("text/body-000001.blocks.zlib", stored, "application/zlib", role="blocks")],
               note="The body: headings, paragraphs, a picture and a table.",
               meta=OrderedDict([("file_formats", OrderedDict([("blocks", "zlib-deflate")]))]),
               payload_file="text/body-000001.json")
    text = plain_text(blks).encode("utf-8")
    w.add_node("text-000001", "core.preview.text",
               [w.file("preview/text/body-000001.txt.zlib", zlib.compress(text, 6), "application/zlib")],
               note="The plain text of body-000001, by procedure rich-document-plain-text-1.",
               epistemic="measured", input_files=["text/body-000001.json"],
               input_params=OrderedDict([("method", "rich-document-plain-text-1")]),
               meta=OrderedDict([("payload_format", "zlib-deflate")]),
               edges=[("body-000001", "requires", "extracted-from")])
    w.add_node("styles", "core.style.sheet", [w.file("document/styles.json", K.cjson(STYLES), "application/json")],
               note="The style sheet: Normal, Heading 1 and Caption.")
    w.add_node("properties", "core.text.properties",
               [w.file("document/properties.json", K.cjson(PROPERTIES), "application/json")],
               note="The document properties: title, author, subject.")
    media_node = "media-harbour-at-dusk-png"
    w.add_node(media_node, "core.media.image", [w.file("media/harbour-at-dusk.png", png, "image/png")],
               note="The picture of the harbour at dusk, as the author supplied it (a PNG).",
               meta=OrderedDict([("width", pw), ("height", ph), ("role", "original"),
                                 ("original_media_type", "image/png"), ("media_key", IMAGE_KEY)]))
    doc = OrderedDict([("schema_version", 1), ("body", ["body-000001"]), ("bodyNextId", 2),
                       ("finalSection", OrderedDict()), ("stories", []), ("noteSeparators", []),
                       ("media", [OrderedDict([("key", IMAGE_KEY), ("mediaType", "image/png"), ("original", None),
                                               ("image", media_node), ("imageIs", "original")])]),
                       ("styles", "styles"), ("properties", "properties"), ("plainText", ["text-000001"])])
    w.add_node("document", "core.text.document", [w.file("document/document.json", K.cjson(doc), "application/json")],
               note="The document structure: the body's runs, the picture table, the single tables.",
               edges=[("body-000001", "enhances", "body"), ("text-000001", "enhances", "plain-text"),
                      ("styles", "enhances", "styles"), ("properties", "enhances", "properties"),
                      (media_node, "enhances", "picture")])
    w.set_primary("document", "document")
    for p in ("HOW-TO-READ.md", "revisions/", "document/document.json", "preview/"):
        w.preview(p)
    pp.add_reference_reader()
    data = pp.write(out, "First save of the rich-document/1 release fixture: the Harbour report.")
    sys.path.insert(0, HERE)
    import read_rich_document as R
    got = R.read(out)
    assert not got["dead"] and not got["file_failures"], got["dead"]
    assert got["plain_text"] == text.decode("utf-8") and got["plain_text_stored_matches"] is True
    assert got["tables"][0] == [list(r) for r in ROWS], got["tables"]
    assert got["media"][0]["png_sha256"] == K.sha(png)
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(PROFILES, "fixtures", "rich-document-v1.werk"))
    ap.add_argument("--raster", default=os.path.join(PROFILES, "fixtures", "raster-layers-v1.werk"))
    a = ap.parse_args()
    data = build(a.out, a.raster)
    print("%s %d bytes sha256 %s" % (a.out, len(data), K.sha(data)))


if __name__ == "__main__":
    main()
