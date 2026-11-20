#!/usr/bin/env python3
"""write_minimal.py - write a minimal valid `spreadsheet/1` werk capsule.

Python standard library only. It uses NO spreadsheet software and NO werk software: it is the
executable form of spec/PROFILE-SPREADSHEET.md section 7 ("Writing a minimal valid
spreadsheet/1 capsule"), of spec/layouts/core.sheet.cells.layout.txt section 6 and of
spec/CRAFT-BASE.md section 8. It copies loaders/, spec/ and the reference inflater (the tool
node `format-zlib-deflate-reference`) out of an existing capsule of the same profile (their
content is the format) and writes everything else itself. The existing capsule must hold at
least one cell: only then does it carry the definition of the format its cells are stored in.

    python write_minimal.py <existing capsule: .werk file or directory> <new.werk>

The document it writes: one sheet, "Prices", with

        A        B
    1   Item     Price
    2   Tea      4.5
    3   Coffee   3
    4   Total    =SUM(B2:B3)

Its content is fixed, so sizes and hashes are checkpoints for another implementation
(spec/PROFILE-SPREADSHEET.md section 7.1 lists them):

    the cells envelope          the ONE band of the cells store, before it is compressed
    sheets/sheet-1/sheet.json   the sheet
    workbook/workbook.json      the structure node
    workbook/styles.json        one cell format, the default
    workbook/names.json         no defined names

The cells store is written as the profile says: an index (sheets/sheet-1/cells.json) and one
band file (sheets/sheet-1/cells/rows-0000000.wkx.zlib), the envelope compressed as one zlib
stream with Python's standard `zlib`. A zlib stream is not unique - another compressor gives
other bytes for the same content - so the band file and the index (which records the band's
hash) are NOT checkpoints; the envelope inside is.

It writes no core.sheet.computed node: this script has no formula engine, so the result of B4
is simply not cached. A reader with an engine computes 7.5; a reader without one shows the
formula. Both are correct readings of this file.
"""

import hashlib
import json
import os
import struct
import sys
import zipfile
import zlib

LF = bytes([10])
CREATED = "2026-10-12T00:00:00Z"
PRODUCER = {"tool": "write_minimal.py", "version": "1"}
NOTE = "A minimal workbook written from the embedded specification alone."
NONE = 0xFFFFFFFF
LICENSE_TEXT = (
    "Licence notice" + chr(10) + chr(10)
    + "THE TERMS OF THIS DOCUMENT'S CONTENT ARE NOT ESTABLISHED." + chr(10) + chr(10)
    + "This file was written by write_minimal.py as a worked example. No licence is granted "
    + "by this notice; anyone redistributing the file must establish its terms." + chr(10)
).encode("utf-8")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def compact(value):
    """One line of JSON and one line feed: the spelling whose hashes section 7.1 lists."""
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + LF


# ---------------------------------------------------------------- the envelope (ENVELOPE.layout.txt)

def mp(value):
    """Canonical MessagePack (ENVELOPE.layout.txt section 4.3): shortest integers, shortest
    strings, map keys sorted by their UTF-8 bytes. Big-endian inside MessagePack."""
    if isinstance(value, bool):
        return bytes([0xC3 if value else 0xC2])
    if isinstance(value, int):
        if 0 <= value <= 0x7F:
            return bytes([value])
        if value <= 0xFF:
            return bytes([0xCC, value])
        if value <= 0xFFFF:
            return bytes([0xCD]) + struct.pack(">H", value)
        if value <= 0xFFFFFFFF:
            return bytes([0xCE]) + struct.pack(">I", value)
        return bytes([0xCF]) + struct.pack(">Q", value)
    if isinstance(value, str):
        raw = value.encode("utf-8")
        if len(raw) <= 31:
            return bytes([0xA0 | len(raw)]) + raw
        if len(raw) <= 0xFF:
            return bytes([0xD9, len(raw)]) + raw
        return bytes([0xDA]) + struct.pack(">H", len(raw)) + raw
    if isinstance(value, list):
        head = bytes([0x90 | len(value)]) if len(value) <= 15 else bytes([0xDC]) + struct.pack(">H", len(value))
        return head + b"".join(mp(v) for v in value)
    if isinstance(value, dict):
        keys = sorted(value, key=lambda k: k.encode("utf-8"))
        head = bytes([0x80 | len(keys)]) if len(keys) <= 15 else bytes([0xDE]) + struct.pack(">H", len(keys))
        return head + b"".join(mp(k) + mp(value[k]) for k in keys)
    raise TypeError(type(value))


def align16(n):
    return (n + 15) // 16 * 16


def envelope(magic, kind, header, sections):
    """sections: [(name, dtype, shape, stride, data bytes)], written in this order. Every
    section starts on a 16-byte boundary; offsets in the header are ABSOLUTE. The header's
    length decides where the payload starts and the offsets are part of the header, so the
    layout is repeated until it stops moving."""
    origin = 16
    while True:
        table, cursor = [], origin
        for name, dtype, shape, stride, data in sections:
            table.append({"name": name, "offset": cursor, "size": len(data), "dtype": dtype, "shape": shape, "stride": stride})
            cursor = align16(cursor + len(data))
        full = dict(header)
        full.update({"kind": kind, "endianness": "le", "payload_origin": origin, "payload_size": cursor - origin, "sections": table})
        packed = mp(full)
        needed = align16(12 + len(packed))
        if needed == origin:
            break
        origin = needed
    out = bytearray(magic + struct.pack("<II", 1, len(packed)) + packed)
    out += bytes(origin - len(out))
    for entry, (_n, _d, _s, _st, data) in zip(table, sections):
        out += bytes(entry["offset"] - len(out))
        out += data
    out += bytes(origin + full["payload_size"] - len(out))
    return bytes(out)


def string_table(strings):
    offsets, data = [0], b""
    for s in strings:
        data += s.encode("utf-8")
        offsets.append(len(data))
    return struct.pack("<%dQ" % len(offsets), *offsets), data


def cells_file(uid, cells):
    """core.sheet.cells (spec/layouts/core.sheet.cells.layout.txt). `cells` maps (row, col),
    zero-based, to a number, a string, a bool, None, or ("=", formula text without `=`)."""
    rows, cols, kinds, numbers, refs, styles, formula_of = [], [], [], [], [], [], []
    texts, formulas = [], []
    for (row, col) in sorted(cells):
        value = cells[(row, col)]
        kind, number, ref, formula = 0, 0.0, 0, NONE
        if isinstance(value, tuple):          # a formula: kind 0 here, its text in the formula table
            if value[1] not in formulas:
                formulas.append(value[1])
            formula = formulas.index(value[1])
        elif isinstance(value, bool):
            kind, ref = 3, int(value)
        elif isinstance(value, (int, float)):
            kind, number = 1, float(value)
        elif isinstance(value, str):
            if value not in texts:
                texts.append(value)
            kind, ref = 2, texts.index(value)
        rows.append(row)
        cols.append(col)
        kinds.append(kind)
        numbers.append(number)
        refs.append(ref)
        styles.append(0)
        formula_of.append(formula)
    n = len(rows)
    u32 = lambda values: struct.pack("<%dI" % len(values), *values)
    text_offsets, text_bytes = string_table(texts)
    formula_offsets, formula_bytes = string_table(formulas)
    sections = [
        ("row", "u32", [n], 4, u32(rows)),
        ("col", "u32", [n], 4, u32(cols)),
        ("kind", "u8", [n], 1, bytes(kinds)),
        ("number", "f64", [n], 8, struct.pack("<%dd" % n, *numbers)),
        ("ref", "u32", [n], 4, u32(refs)),
        ("style", "u32", [n], 4, u32(styles)),
        ("formula", "u32", [n], 4, u32(formula_of)),
        ("text-offsets", "u64", [len(texts) + 1], 8, text_offsets),
        ("text-bytes", "u8", [len(text_bytes)], 1, text_bytes),
        ("array-dims", "u32", [0, 4], 16, b""),
        ("elem-kind", "u8", [0], 1, b""),
        ("elem-number", "f64", [0], 8, b""),
        ("elem-ref", "u32", [0], 4, b""),
        ("formula-offsets", "u64", [len(formulas) + 1], 8, formula_offsets),
        ("formula-bytes", "u8", [len(formula_bytes)], 1, formula_bytes),
        ("formula-array", "u32", [len(formulas), 5], 20, bytes(20 * len(formulas))),
    ]
    header = {"sheet_uid": uid, "cell_count": n, "text_count": len(texts), "formula_count": len(formulas),
              "array_count": 0, "element_count": 0}
    return envelope(b"WKX0", "core.sheet.cells", header, sections)


# ---------------------------------------------------------------- the JSON payloads

def default_format():
    """The default cell format, spelled out in full (spec/schemas/core.sheet.styles.schema.json)."""
    line = {"style": "None", "color": "Auto"}
    return {
        "font": {"name": "Calibri", "size": 11.0, "bold": False, "italic": False, "underline": "None",
                 "strike": False, "color": "Auto", "vert": "Baseline"},
        "fill": {"pattern": "None", "fg": "Auto", "bg": "Auto"},
        "borders": {"left": line, "right": line, "top": line, "bottom": line, "diag_down": line, "diag_up": line},
        "align": {"h": "General", "v": "Bottom", "wrap": False, "shrink": False, "indent": 0, "rotation": 0},
        "num_fmt": "General",
        "protection": {"locked": True, "hidden": False},
    }


def styles_payload():
    return {
        "schema_version": 1,
        "cell_formats": [default_format()],
        "named_styles": [],
        "theme": {"name": "Minimal",
                  "colors": [0xFFFFFF, 0x000000, 0xE8E8E8, 0x0E2841, 0x156082, 0xE97132, 0x196B24, 0x0F9ED5,
                             0xA02B93, 0x4EA72E, 0x467886, 0x96607D],
                  "major_font": "Calibri", "minor_font": "Calibri"},
    }


def sheet_payload(uid, name):
    origin = {"row": 0, "col": 0}
    return {
        "schema_version": 1, "uid": uid, "name": name, "cells": "sheet-%d-cells" % uid,
        "cols": {}, "rows": {}, "default_col_width": 64.0, "default_row_height": 20.0,
        "merges": [], "freeze": None, "tab_color": None, "visibility": "Visible",
        "show_gridlines": True, "show_headings": True, "show_formulas": False, "show_zeros": True,
        "right_to_left": False, "zoom": 100, "view": "normal", "view_active": origin, "view_top_left": origin,
        "cond_formats": [], "validations": [], "tables": [], "autofilter": None, "comments": {}, "hyperlinks": {},
        "charts": [], "pivots": [], "images": [], "cell_pictures": [], "shapes": [], "sparklines": [], "slicers": [],
        "protection": None, "edit_ranges": [],
        "print": {"orientation": "Portrait", "paper": "A4", "margins": [0.7, 0.7, 0.75, 0.75, 0.3, 0.3],
                  "print_area": None, "title_rows": None, "title_cols": None, "scale": 100, "fit_to": None,
                  "gridlines": False, "headings": False, "center_h": False, "center_v": False,
                  "header": "", "footer": "", "row_breaks": [], "col_breaks": []},
    }


def workbook_payload(sheet_ids):
    return {
        "schema_version": 1, "sheets": sheet_ids, "active_sheet": sheet_ids[0], "active_sheet_index": 0,
        "date_system": "D1900",
        "calc": {"mode": "Automatic", "iterative": False, "max_iterations": 100, "max_change": 0.001,
                 "precision_as_displayed": False},
        "props": {"title": "Minimal prices", "subject": "", "author": "", "company": "", "keywords": "", "description": ""},
        "protected_structure": False, "custom_lists": [], "styles": "styles", "names": "names",
    }


CELLS = {
    (0, 0): "Item", (0, 1): "Price",
    (1, 0): "Tea", (1, 1): 4.5,
    (2, 0): "Coffee", (2, 1): 3,
    (3, 0): "Total", (3, 1): ("=", "SUM(B2:B3)"),
}


BAND_ROWS = 4096
CELLS_INDEX = "sheets/sheet-1/cells.json"
CELLS_BAND = "sheets/sheet-1/cells/rows-0000000.wkx.zlib"


def cells_store(uid, cells):
    """The banded store of a sheet's cells (spec/PROFILE-SPREADSHEET.md section 3.3): the
    envelope of each band of rows, compressed as one zlib stream, and the index that names the
    bands. All the cells here are in rows 0..4095: one band."""
    envelope_bytes = cells_file(uid, cells)
    stored = zlib.compress(envelope_bytes, 6)
    index = {
        "schema_version": 1, "store": "cells", "sheet_uid": uid, "band_rows": BAND_ROWS,
        "band_format": "zlib-deflate", "inflated_layout": "spec/layouts/core.sheet.cells.layout.txt",
        "entry_count": len(cells),
        "bands": [{
            "path": CELLS_BAND, "first_row": 0, "row_count": BAND_ROWS, "entry_count": len(cells),
            "stored_size": len(stored), "stored_sha256": sha256(stored),
            "inflated_size": len(envelope_bytes), "inflated_sha256": sha256(envelope_bytes),
        }],
    }
    return envelope_bytes, stored, compact(index)


def payloads():
    """logical path -> bytes, for the files of the minimal document."""
    _envelope, band, index = cells_store(1, CELLS)
    return {
        CELLS_INDEX: index,
        CELLS_BAND: band,
        "sheets/sheet-1/sheet.json": compact(sheet_payload(1, "Prices")),
        "workbook/workbook.json": compact(workbook_payload(["sheet-1"])),
        "workbook/styles.json": compact(styles_payload()),
        "workbook/names.json": compact({"schema_version": 1, "names": []}),
    }


# ---------------------------------------------------------------- the package (CRAFT-BASE.md section 8)

def read_source(path):
    files = {}
    if os.path.isdir(path):
        for root, _dirs, names in os.walk(path):
            for name in names:
                full = os.path.join(root, name)
                rel = "/".join(os.path.relpath(full, path).split(os.sep))
                with open(full, "rb") as fh:
                    files[rel] = fh.read()
    else:
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                if not name.endswith("/"):
                    files[name] = z.read(name)
    return files


def is_superseded(path):
    name = path.rsplit("/", 1)[-1]
    if "@" not in name:
        return False
    return name.rsplit("@", 1)[1].split(".", 1)[0].isdigit()


def file_entry(path, data, **extra):
    entry = {"path": path, "sha256": sha256(data), "size": len(data)}
    entry.update(extra)
    return entry


def version(files, note, **extra):
    v = {"v": 1, "files": files, "note": note, "producer": dict(PRODUCER), "epistemic": "authored", "created": CREATED}
    v.update(extra)
    return v


def node(node_id, node_type, ver, edges=(), meta=None):
    n = {"node_id": node_id, "type": node_type, "versions": [ver], "active": 1, "edges": list(edges)}
    if meta is not None:
        n["meta"] = meta
    return n


def spec_sha256(entries):
    """spec/SPEC.md section 2: sort by path (UTF-8 bytes); for each: path, 0x0A, the file's
    sha256 as 32 RAW bytes, 0x0A; sha256 of the concatenation."""
    acc = hashlib.sha256()
    for entry in sorted(entries, key=lambda e: e["path"].encode("utf-8")):
        acc.update(entry["path"].encode("utf-8"))
        acc.update(LF)
        acc.update(bytes.fromhex(entry["sha256"]))
        acc.update(LF)
    return acc.hexdigest()


def new_uuid():
    raw = bytearray(os.urandom(16))
    raw[6] = (raw[6] & 0x0F) | 0x40
    raw[8] = (raw[8] & 0x3F) | 0x80
    h = raw.hex()
    return "-".join([h[0:8], h[8:12], h[12:16], h[16:20], h[20:32]])


def main(argv):
    if len(argv) != 3:
        print(__doc__.strip())
        return 2
    source, out_path = argv[1], argv[2]
    src = read_source(source)
    old = json.loads(src["MANIFEST.json"].decode("utf-8"))
    if old.get("profile") != "spreadsheet/1":
        print("the existing capsule is profile %r, not spreadsheet/1" % old.get("profile"))
        return 2
    blobs, nodes = {}, []

    # The base files: loaders/ and spec/ copied unchanged, superseded versions skipped.
    spec_entries = []
    for path in sorted(p for p in src if p.startswith("spec/") and not is_superseded(p)):
        blobs[path] = src[path]
        spec_entries.append(file_entry(path, src[path]))
    nodes.append(node("spec", "core.spec", version(spec_entries, "The format specification, travelling inside the file it describes (law 2).")))
    blobs["LICENSE"] = LICENSE_TEXT
    nodes.append(node("license", "core.license", version([file_entry("LICENSE", LICENSE_TEXT)], "The full licence text, embedded, never a link (law 7).")))
    for path in ("README.txt", "HOW-TO-READ.md"):
        blobs[path] = src[path]
    nodes.append(node("readme", "core.readme", version(
        [file_entry("README.txt", blobs["README.txt"], role="payload"),
         file_entry("HOW-TO-READ.md", blobs["HOW-TO-READ.md"], role="how-to-read")],
        "One page for a human, and the reading guide for this profile.", payload_file="README.txt")))
    old_nodes = {n["node_id"]: n for n in old["nodes"]}
    for node_id, fname in (("loader-python", "werk_read.py"), ("loader-rust", "werk_read.rs"), ("loader-c", "werk_read.c")):
        path = "loaders/" + fname
        blobs[path] = src[path]
        nodes.append(node(node_id, "core.loader", version(
            [file_entry(path, src[path])], "A single-file, dependency-free reader carried as payload (law 1)."),
            meta=old_nodes[node_id]["meta"]))

    # The definition of the one foreign format this document uses (zlib, for the cell bands) is
    # already in spec/ (copied above). Its reference implementation travels as a tool node:
    # copy that node, files and all.
    zlib_tool = "format-zlib-deflate-reference"
    if "zlib-deflate" not in old.get("formats", {}) or zlib_tool not in old_nodes:
        print("the existing capsule holds no cells, so it does not carry the zlib-deflate definition; use one that does")
        return 2
    tool = old_nodes[zlib_tool]
    tool_version = [v for v in tool["versions"] if v["v"] == tool["active"]][0]
    tool_files = []
    for f in tool_version["files"]:
        blobs[f["path"]] = src[f["path"]]
        tool_files.append(file_entry(f["path"], src[f["path"]], media_type=f["media_type"], role=f["role"]))
    nodes.append(node(zlib_tool, "core.tool", version(
        tool_files, "Reference implementation (source) of the format the cell bands are stored in.",
        payload_file=tool_version["payload_file"]), meta=tool.get("meta")))

    # The document: five nodes. Four have one file; the cells store has its index and one band.
    files = payloads()
    blobs.update(files)
    entry = lambda path, media: [file_entry(path, files[path], media_type=media)]
    document = [
        node("workbook", "core.sheet.workbook", version(entry("workbook/workbook.json", "application/json"), NOTE),
             edges=[{"to": "sheet-1", "kind": "enhances", "role": "sheet"},
                    {"to": "styles", "kind": "enhances", "role": "styles"},
                    {"to": "names", "kind": "enhances", "role": "names"}]),
        node("styles", "core.sheet.styles", version(entry("workbook/styles.json", "application/json"), NOTE)),
        node("names", "core.sheet.names", version(entry("workbook/names.json", "application/json"), NOTE)),
        node("sheet-1", "core.sheet.sheet", version(entry("sheets/sheet-1/sheet.json", "application/json"), NOTE),
             edges=[{"to": "sheet-1-cells", "kind": "enhances", "role": "cells"}]),
        node("sheet-1-cells", "core.sheet.cells", version(
            [file_entry(CELLS_INDEX, files[CELLS_INDEX], media_type="application/json", role="payload"),
             file_entry(CELLS_BAND, files[CELLS_BAND], media_type="application/zlib", role="band")],
            NOTE, payload_file=CELLS_INDEX),
            meta={"file_formats": {"band": "zlib-deflate"}}),
    ]

    # The revision record: every node except `revisions`, at version 1.
    uses = {n["node_id"]: 1 for n in nodes + document}
    record = {"schema_version": 1, "revision": 1, "kind": "save", "note": NOTE, "created": CREATED,
              "producer": dict(PRODUCER), "nodes": uses}
    record_bytes = (json.dumps(record, indent=2, sort_keys=True) + chr(10)).encode("utf-8")
    blobs["revisions/revision.json"] = record_bytes
    nodes.append(node("revisions", "core.revisions", version(
        [file_entry("revisions/revision.json", record_bytes, media_type="application/json")], NOTE)))
    nodes.extend(document)

    # The manifest.
    container = dict(old["container"])
    container.pop("preview_prefix_bytes", None)
    container["form"] = "zip"
    container["total_size_bytes"] = sum(len(b) for b in blobs.values())
    types = {n["type"] for n in nodes}
    manifest = {
        "werk": old["werk"],
        "profile": old["profile"],
        "manifest_schema": old["manifest_schema"],
        "conventions_map": old["conventions_map"],
        "conventions": old["conventions"],
        "container": container,
        "primary": {"document": "workbook"},
        "license": {"file": "LICENSE", "sha256": sha256(LICENSE_TEXT)},
        "schemas": {t: p for t, p in old["schemas"].items() if t in types},
        "layouts": {t: p for t, p in old.get("layouts", {}).items() if t in types},
        "formats": {"zlib-deflate": old["formats"]["zlib-deflate"]},
        "spec_sha256": spec_sha256(spec_entries),
        "entity": {"uuid": new_uuid(), "name": "Minimal prices", "created": CREATED,
                   "summary": "Written by write_minimal.py from the embedded specification."},
        "nodes": nodes,
        "generator": dict(PRODUCER),
    }
    manifest_bytes = (json.dumps(manifest, indent=2, ensure_ascii=False) + chr(10)).encode("utf-8")

    # The container: store mode, MANIFEST.json first, the preview tier before the rest.
    tier = container["preview_tier"]

    def tier_rank(path):
        for i, t in enumerate(tier):
            if (path.startswith(t) if t.endswith("/") else path == t):
                return i
        return len(tier)

    ordered = sorted(blobs, key=lambda p: (tier_rank(p), p.encode("utf-8")))
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_STORED) as z:
        for name, data in [("MANIFEST.json", manifest_bytes)] + [(p, blobs[p]) for p in ordered]:
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 12, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            z.writestr(info, data)
    envelope_bytes = cells_store(1, CELLS)[0]
    print("%-28s %6d bytes  sha256 %s" % ("the cells envelope (inflated)", len(envelope_bytes), sha256(envelope_bytes)))
    for path in sorted(files):
        print("%-28s %6d bytes  sha256 %s" % (path, len(files[path]), sha256(files[path])))
    print("wrote %s: %d nodes, %d files, manifest sha256 %s" % (out_path, len(nodes), len(blobs), sha256(manifest_bytes)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
