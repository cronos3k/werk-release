#!/usr/bin/env python3
"""build_spreadsheet.py -- the spreadsheet/1 release fixture, written deterministically with the
release library (profiles/tools/profilekit.py).

The workbook "Lighthouse costs", two sheets:

  sheet-1 "Costs"    a table of work items: text, numbers, a formula per row (B*C) and two
                     SUM formulas in the total row
  sheet-2 "Summary"  formulas that read the other sheet (`Costs!D6`, `MAX(Costs!D2:D5)`) and
                     its own cells (VAT, gross, a share)

Each sheet has its cells store (core.sheet.cells: a JSON index plus one band, a zlib stream of
a WKX0 envelope) and its cached results (core.sheet.computed, `measured`: index plus one band,
a zlib stream of a WKX1 envelope; the input files follow PROFILE-SPREADSHEET.md 3.4, so the
Summary cache depends on both sheets). Number formats in the styles node (two-decimal money,
a percentage). zlib-deflate definition and reference inflater travel with it; the reference
reader is a core.tool node.

usage: build_spreadsheet.py [--out profiles/fixtures/spreadsheet-v1.werk]
"""
import argparse
import copy
import os
import struct
import sys
import zlib
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILES = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROFILES, "tools"))
import profilekit as K  # noqa: E402
# The profile's own example writer (vendored spec file): its full default payloads are reused.
sys.path.insert(0, os.path.join(HERE, "spec", "examples", "spreadsheet"))
import write_minimal as WM  # noqa: E402

NONE = 4294967295
BAND_ROWS = 4096
MONEY, PERCENT = 1, 2


def F(text, style=0):
    return ("=", text, style)


def V(v, style=0):
    return ("v", v, style)


COSTS = {
    (0, 0): V("Work"), (0, 1): V("Hours"), (0, 2): V("Rate"), (0, 3): V("Cost"),
    (1, 0): V("Scraping and priming"), (1, 1): V(36), (1, 2): V(55, MONEY), (1, 3): F("B2*C2", MONEY),
    (2, 0): V("Red and white coats"), (2, 1): V(48), (2, 2): V(55, MONEY), (2, 3): F("B3*C3", MONEY),
    (3, 0): V("Lamp-room glazing"), (3, 1): V(12), (3, 2): V(95, MONEY), (3, 3): F("B4*C4", MONEY),
    (4, 0): V("Gallery railing"), (4, 1): V(18), (4, 2): V(55, MONEY), (4, 3): F("B5*C5", MONEY),
    (5, 0): V("Total"), (5, 1): F("SUM(B2:B5)"), (5, 3): F("SUM(D2:D5)", MONEY),
}
SUMMARY = {
    (0, 0): V("Total cost"), (0, 1): F("Costs!D6", MONEY),
    (1, 0): V("VAT 19%"), (1, 1): F("B1*0.19", MONEY),
    (2, 0): V("Gross"), (2, 1): F("B1+B2", MONEY),
    (3, 0): V("Largest item"), (3, 1): F("MAX(Costs!D2:D5)", MONEY),
    (4, 0): V("Share of largest"), (4, 1): F("B4/B1", PERCENT),
}
# the cached results, computed here by hand from the formulas above (binary64 arithmetic)
_d = [36 * 55, 48 * 55, 12 * 95, 18 * 55]
_total = float(sum(_d))
COSTS_RESULTS = {(1, 3): float(_d[0]), (2, 3): float(_d[1]), (3, 3): float(_d[2]), (4, 3): float(_d[3]),
                 (5, 1): float(36 + 48 + 12 + 18), (5, 3): _total}
_vat = _total * 0.19
SUMMARY_RESULTS = {(0, 1): _total, (1, 1): _vat, (2, 1): _total + _vat, (3, 1): float(max(_d)),
                   (4, 1): float(max(_d)) / _total}


def string_table(strings):
    offsets, data = [0], b""
    for s in strings:
        data += s.encode("utf-8")
        offsets.append(len(data))
    return struct.pack("<%dQ" % len(offsets), *offsets), data


def u32(v):
    return struct.pack("<%dI" % len(v), *v)


def cells_file(uid, cells):
    """core.sheet.cells.layout.txt: one band holding every cell (all rows < 4096)."""
    rows, cols, kinds, nums, refs, styles, fidx, texts, forms = [], [], [], [], [], [], [], [], []
    for (r, c) in sorted(cells):
        tag, v, st = cells[(r, c)]
        kind, num, ref, f = 0, 0.0, 0, NONE
        if tag == "=":
            if v not in forms:
                forms.append(v)
            f = forms.index(v)
        elif isinstance(v, str):
            if v not in texts:
                texts.append(v)
            kind, ref = 2, texts.index(v)
        else:
            kind, num = 1, float(v)
        rows.append(r); cols.append(c); kinds.append(kind); nums.append(num); refs.append(ref)
        styles.append(st); fidx.append(f)
    n = len(rows)
    to, tb = string_table(texts)
    fo, fb = string_table(forms)
    secs = [("row", "u32", [n], 4, u32(rows)), ("col", "u32", [n], 4, u32(cols)),
            ("kind", "u8", [n], 1, bytes(kinds)), ("number", "f64", [n], 8, struct.pack("<%dd" % n, *nums)),
            ("ref", "u32", [n], 4, u32(refs)), ("style", "u32", [n], 4, u32(styles)),
            ("formula", "u32", [n], 4, u32(fidx)),
            ("text-offsets", "u64", [len(texts) + 1], 8, to), ("text-bytes", "u8", [len(tb)], 1, tb),
            ("array-dims", "u32", [0, 4], 16, b""), ("elem-kind", "u8", [0], 1, b""),
            ("elem-number", "f64", [0], 8, b""), ("elem-ref", "u32", [0], 4, b""),
            ("formula-offsets", "u64", [len(forms) + 1], 8, fo), ("formula-bytes", "u8", [len(fb)], 1, fb),
            ("formula-array", "u32", [len(forms), 5], 20, bytes(20 * len(forms)))]
    hdr = {"sheet_uid": uid, "cell_count": n, "text_count": len(texts), "formula_count": len(forms),
           "array_count": 0, "element_count": 0}
    return K.envelope(b"WKX0", "core.sheet.cells", hdr, secs), n


def computed_file(uid, results):
    """core.sheet.computed.layout.txt: source 0 (cached formula results), all numbers."""
    keys = sorted(results)
    n = len(keys)
    to, tb = string_table([])
    secs = [("row", "u32", [n], 4, u32([k[0] for k in keys])), ("col", "u32", [n], 4, u32([k[1] for k in keys])),
            ("source", "u8", [n], 1, bytes(n)), ("kind", "u8", [n], 1, bytes([1] * n)),
            ("number", "f64", [n], 8, struct.pack("<%dd" % n, *[results[k] for k in keys])),
            ("ref", "u32", [n], 4, u32([0] * n)),
            ("text-offsets", "u64", [1], 8, to), ("text-bytes", "u8", [0], 1, tb),
            ("array-dims", "u32", [0, 4], 16, b""), ("elem-kind", "u8", [0], 1, b""),
            ("elem-number", "f64", [0], 8, b""), ("elem-ref", "u32", [0], 4, b""),
            ("spill-ranges", "u32", [0, 6], 24, b"")]
    hdr = {"sheet_uid": uid, "entry_count": n, "text_count": 0, "array_count": 0, "element_count": 0,
           "spill_range_count": 0}
    return K.envelope(b"WKX1", "core.sheet.computed", hdr, secs), n


def store(w, nid, uid, kind, env, count, note, epistemic="authored", inputs=None, params=None, edges=()):
    sub = "cells" if kind == "cells" else "computed"
    band_path = "sheets/sheet-%d/%s/rows-0000000.wkx.zlib" % (uid, sub)
    stored = zlib.compress(env, 6)
    index = OrderedDict([
        ("schema_version", 1), ("store", kind), ("sheet_uid", uid), ("band_rows", BAND_ROWS),
        ("band_format", "zlib-deflate"), ("inflated_layout", "spec/layouts/core.sheet.%s.layout.txt" % sub),
        ("entry_count", count),
        ("bands", [OrderedDict([("path", band_path), ("first_row", 0), ("row_count", BAND_ROWS), ("entry_count", count),
                                ("stored_size", len(stored)), ("stored_sha256", K.sha(stored)),
                                ("inflated_size", len(env)), ("inflated_sha256", K.sha(env))])])])
    w.add_node(nid, "core.sheet.%s" % kind,
               [w.file("sheets/sheet-%d/%s.json" % (uid, sub), K.cjson(index), "application/json", role="payload"),
                w.file(band_path, stored, "application/zlib", role="band")],
               note=note, epistemic=epistemic, input_files=inputs, input_params=params,
               meta=OrderedDict([("file_formats", OrderedDict([("band", "zlib-deflate")]))]),
               payload_file="sheets/sheet-%d/%s.json" % (uid, sub), edges=list(edges))


README = (u"Lighthouse costs\n\n"
          u"This is a werk package, profile `spreadsheet/1`: a workbook of two sheets with formulas "
          u"across them and their cached results. It carries its own format specification, three "
          u"readers, a reference reader of this profile, and its licence.\n\n"
          u"    python loaders/werk_read.py <this file> --verify --strict\n"
          u"    python tools/reader-spreadsheet/read_spreadsheet.py <this file>\n\n"
          u"Where to read next: HOW-TO-READ.md, spec/PROFILE-SPREADSHEET.md, spec/CRAFT-BASE.md, spec/SPEC.md.\n")
LICENSE = (u"CC0 1.0 Universal (public domain dedication).\n\n"
           u"This workbook was written by a script for the werk release fixtures; to the extent possible "
           u"under law, the author has waived all copyright and related rights to it. "
           u"https://creativecommons.org/publicdomain/zero/1.0/\n")


def build(out):
    pp = K.ProfilePackage("spreadsheet", "Lighthouse costs",
                          summary="spreadsheet/1 release fixture: two sheets, formulas across sheets, cached results.",
                          readme_text=README, license_text=LICENSE, spdx_id="CC0-1.0")
    w = pp.w
    pp.use_format("zlib-deflate")
    styles = WM.styles_payload()
    for fmt in ("#,##0.00", "0.0%"):
        f = copy.deepcopy(WM.default_format())
        f["num_fmt"] = fmt
        f["align"]["h"] = "Right"
        styles["cell_formats"].append(f)
    wb = WM.workbook_payload(["sheet-1", "sheet-2"])
    wb["props"]["title"] = "Lighthouse costs"
    wb["props"]["author"] = "Harbour office"
    w.add_node("workbook", "core.sheet.workbook", [w.file("workbook/workbook.json", K.cjson(wb), "application/json")],
               note="The workbook: sheet order, date system, calculation settings.",
               edges=[("sheet-1", "enhances", "sheet"), ("sheet-2", "enhances", "sheet"),
                      ("styles", "enhances", "styles"), ("names", "enhances", "names")])
    w.add_node("styles", "core.sheet.styles", [w.file("workbook/styles.json", K.cjson(styles), "application/json")],
               note="Cell formats: the default, money with two decimals, a percentage.")
    w.add_node("names", "core.sheet.names",
               [w.file("workbook/names.json", K.cjson(OrderedDict([("schema_version", 1), ("names", [])])),
                       "application/json")], note="Defined names: none in this workbook.")
    for uid, name, cells, results in ((1, "Costs", COSTS, COSTS_RESULTS), (2, "Summary", SUMMARY, SUMMARY_RESULTS)):
        sp = WM.sheet_payload(uid, name)
        sp["computed"] = "sheet-%d-computed" % uid
        sp["cols"] = {"0": OrderedDict([("size", 140.0 if uid == 1 else 120.0), ("hidden", False), ("outline", 0),
                                        ("collapsed", False), ("custom", True), ("style", None)])}
        w.add_node("sheet-%d" % uid, "core.sheet.sheet",
                   [w.file("sheets/sheet-%d/sheet.json" % uid, K.cjson(sp), "application/json")],
                   note="Sheet %s: its layout and the nodes of its cells and cached results." % name,
                   edges=[("sheet-%d-cells" % uid, "enhances", "cells"), ("sheet-%d-computed" % uid, "enhances", "computed")])
        env, n = cells_file(uid, cells)
        store(w, "sheet-%d-cells" % uid, uid, "cells", env, n, "The cells of sheet %s: values, formulas, formats." % name)
    for uid, name, results, deps in ((1, "Costs", COSTS_RESULTS, [1]), (2, "Summary", SUMMARY_RESULTS, [1, 2])):
        inputs = ["workbook/workbook.json", "workbook/names.json"]
        for d in deps:
            inputs += ["sheets/sheet-%d/sheet.json" % d, "sheets/sheet-%d/cells.json" % d]
        env, n = computed_file(uid, results)
        req = ["workbook", "names"] + sum((["sheet-%d" % d, "sheet-%d-cells" % d] for d in deps), [])
        store(w, "sheet-%d-computed" % uid, uid, "computed", env, n,
              "Cached results of the formulas of sheet %s." % name, epistemic="measured", inputs=inputs,
              params=OrderedDict([("formula_grammar", "excel-a1-en-us"), ("calc_mode", "Automatic"),
                                  ("volatile_functions", False)]),
              edges=[(r, "requires", "computed-from") for r in req])
    w.set_primary("document", "workbook")
    for p in ("HOW-TO-READ.md", "revisions/", "workbook/"):
        w.preview(p)
    pp.add_reference_reader()
    data = pp.write(out, "First save of the spreadsheet/1 release fixture: Lighthouse costs.")
    sys.path.insert(0, HERE)
    import read_spreadsheet as R
    got = R.read(out)
    assert not got["dead"] and not got["file_failures"], got["dead"]
    sh = {s["name"]: s for s in got["sheets"]}
    assert sh["Costs"]["cells"]["D6"]["formula"] == "SUM(D2:D5)" and sh["Costs"]["cells"]["D6"]["value"] == _total
    assert sh["Summary"]["cells"]["B1"]["formula"] == "Costs!D6" and sh["Summary"]["cells"]["B3"]["value"] == _total + _vat
    assert all(s["computed_input_hash_ok"] for s in got["sheets"])
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(PROFILES, "fixtures", "spreadsheet-v1.werk"))
    a = ap.parse_args()
    data = build(a.out)
    print("%s %d bytes sha256 %s" % (a.out, len(data), K.sha(data)))


if __name__ == "__main__":
    main()
