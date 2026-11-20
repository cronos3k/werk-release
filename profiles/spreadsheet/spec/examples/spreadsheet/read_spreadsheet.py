#!/usr/bin/env python3
"""read_spreadsheet.py - read a `spreadsheet/1` werk capsule with the Python standard library.

It uses NO spreadsheet software and NO werk software: it is the executable form of
spec/PROFILE-SPREADSHEET.md section 6 ("Reading"), of spec/layouts/core.sheet.cells.layout.txt
and core.sheet.computed.layout.txt, and of spec/layouts/ENVELOPE.layout.txt. Everything it
knows, it knows from those files.

The cells of a sheet are stored in BANDS of rows, each band one zlib stream (RFC 1950). This
script inflates them with Python's standard `zlib` module. On a platform without one, the
format is defined in spec/formats/zlib-deflate.md, and tools/format-zlib-deflate-reference/
inflate.py (in every capsule that has bands) is a complete inflater in plain Python.

    python read_spreadsheet.py <capsule: .werk file or directory>            a summary
    python read_spreadsheet.py <capsule> --json out.json                     everything, as JSON
    python read_spreadsheet.py <capsule> --csv SHEET out.csv                 one sheet as CSV
    python read_spreadsheet.py <capsule> --revision K ...                    as it was at revision K

Exit status: 0 = read, nothing wrong; 1 = read, something was damaged or refused (it says
what); 2 = not a readable capsule.

The --json document (what a test compares against the application's own state):

    {"profile", "uuid", "revision", "date_system", "active_sheet", "lost": [node ids],
     "sheets": [{"node", "uid", "name", "visibility", "cells": [...], "spill_ranges": [...],
                 "merges", "charts": [...], "pivots": [...], "pictures": [...]}],
     "names": [...], "cell_formats": N, "external_values": {...} | null}

    cell = {"row", "col", "a1", "style", "value", "formula": text | null,
            "array_range": [r0, c0, r1, c1] | null, "spilled": bool}
    value = null | number | string | bool | {"error": "#N/A"} | {"nonfinite": "nan"|"inf"|"-inf"}
            | {"array": {"rows", "cols", "values": [value, ...]}}
"""

import hashlib
import json
import os
import struct
import sys
import zipfile
import zlib

PROFILE = "spreadsheet/1"
NONE = 0xFFFFFFFF
ERRORS = {1: "#NULL!", 2: "#DIV/0!", 3: "#VALUE!", 4: "#REF!", 5: "#NAME?", 6: "#NUM!", 7: "#N/A",
          8: "#GETTING_DATA", 9: "#SPILL!", 14: "#CALC!", 15: "#CIRC!"}


class Refused(Exception):
    """This node (or value) cannot be used; the rest of the document can."""


# ---------------------------------------------------------------- the container

class Container:
    """A capsule in either form: a directory tree, or the same tree as a store-mode zip."""

    def __init__(self, path):
        self.path = path
        self.zip = None
        if os.path.isdir(path):
            if not os.path.isfile(os.path.join(path, "MANIFEST.json")):
                raise ValueError("bad-manifest: MANIFEST.json is not in the directory")
        else:
            try:
                self.zip = zipfile.ZipFile(path)
            except (zipfile.BadZipFile, OSError) as e:
                raise ValueError("bad-container: %s" % e)
            if "MANIFEST.json" not in self.zip.namelist():
                raise ValueError("bad-manifest: MANIFEST.json is not in the zip")

    def read(self, name):
        if self.zip is not None:
            info = self.zip.getinfo(name)
            if info.compress_type != zipfile.ZIP_STORED:
                raise Refused("zip-entry-unsupported: %s is not stored" % name)
            try:
                return self.zip.read(name)
            except zipfile.BadZipFile as e:
                # The zip's own CRC-32 caught damaged bytes before the sha256 could: same verdict.
                raise Refused("hash-mismatch: %s (%s)" % (name, e))
        with open(os.path.join(self.path, *name.split("/")), "rb") as fh:
            return fh.read()


def logical(path):
    """A declared path with the `@N` version marker removed from its file name
    (spec/CRAFT-BASE.md section 4): sheets/sheet-1/cells@1.json -> sheets/sheet-1/cells.json,
    sheets/sheet-1/cells/rows-0000000.wkx@1.zlib -> sheets/sheet-1/cells/rows-0000000.wkx.zlib."""
    head, _, name = path.rpartition("/")
    at = name.rfind("@")
    if at >= 0:
        tail = name[at + 1:]
        digits = tail.split(".", 1)[0]
        if digits.isdigit():
            rest = tail[len(digits):]
            name = name[:at] + rest
    return (head + "/" if head else "") + name


# ---------------------------------------------------------------- the envelope

def msgpack(buf, i=0):
    """Decode one value of the MessagePack subset of ENVELOPE.layout.txt section 4.
    Integers and floats inside MessagePack are BIG-endian. Returns (value, next index)."""
    b = buf[i]
    i += 1
    if b <= 0x7F:
        return b, i
    if b >= 0xE0:
        return b - 256, i
    if 0xA0 <= b <= 0xBF:
        n = b & 0x1F
        return buf[i:i + n].decode("utf-8"), i + n
    if 0x90 <= b <= 0x9F:
        return msgpack_array(buf, i, b & 0x0F)
    if 0x80 <= b <= 0x8F:
        return msgpack_map(buf, i, b & 0x0F)
    if b == 0xC0:
        return None, i
    if b == 0xC2:
        return False, i
    if b == 0xC3:
        return True, i
    fixed = {0xCC: ">B", 0xCD: ">H", 0xCE: ">I", 0xCF: ">Q", 0xD0: ">b", 0xD1: ">h", 0xD2: ">i",
             0xD3: ">q", 0xCA: ">f", 0xCB: ">d"}
    if b in fixed:
        size = struct.calcsize(fixed[b])
        return struct.unpack_from(fixed[b], buf, i)[0], i + size
    lengths = {0xD9: 1, 0xDA: 2, 0xDB: 4, 0xC4: 1, 0xC5: 2, 0xC6: 4, 0xDC: 2, 0xDD: 4, 0xDE: 2, 0xDF: 4}
    if b in lengths:
        width = lengths[b]
        n = int.from_bytes(buf[i:i + width], "big")
        i += width
        if b in (0xD9, 0xDA, 0xDB):
            return buf[i:i + n].decode("utf-8"), i + n
        if b in (0xC4, 0xC5, 0xC6):
            return bytes(buf[i:i + n]), i + n
        if b in (0xDC, 0xDD):
            return msgpack_array(buf, i, n)
        return msgpack_map(buf, i, n)
    raise Refused("envelope-invalid: MessagePack byte 0x%02x is not in the subset" % b)


def msgpack_array(buf, i, n):
    out = []
    for _ in range(n):
        v, i = msgpack(buf, i)
        out.append(v)
    return out, i


def msgpack_map(buf, i, n):
    out = {}
    for _ in range(n):
        k, i = msgpack(buf, i)
        v, i = msgpack(buf, i)
        out[k] = v
    return out, i


DTYPES = {"u8": ("B", 1), "i8": ("b", 1), "u16": ("H", 2), "i16": ("h", 2), "u32": ("I", 4),
          "i32": ("i", 4), "u64": ("Q", 8), "i64": ("q", 8), "f32": ("f", 4), "f64": ("d", 8)}


class Envelope:
    """ENVELOPE.layout.txt section 7, the reference reader, as code."""

    def __init__(self, buf, magic, kind):
        if len(buf) < 12 or buf[0:4] != magic:
            raise Refused("envelope-invalid: magic is %r, expected %r" % (bytes(buf[0:4]), magic))
        self.buf = buf
        self.version, header_len = struct.unpack_from("<II", buf, 4)
        if 12 + header_len > len(buf):
            raise Refused("envelope-invalid: the header runs past the end of the file")
        self.header, _ = msgpack(buf[12:12 + header_len])
        h = self.header
        origin = 16 * ((12 + header_len + 15) // 16)
        if h.get("endianness") != "le" or h.get("kind") != kind:
            raise Refused("envelope-invalid: kind %r / endianness %r" % (h.get("kind"), h.get("endianness")))
        if h.get("payload_origin") != origin or origin + h.get("payload_size", -1) != len(buf):
            raise Refused("envelope-invalid: payload_origin / payload_size disagree with the file")
        self.sections = {}
        for s in h["sections"]:
            if s["offset"] % 16 != 0 or s["offset"] + s["size"] > len(buf):
                raise Refused("envelope-invalid: section %s does not fit" % s["name"])
            self.sections[s["name"]] = s

    def column(self, name, dtype, width=1):
        """A section as a flat tuple of numbers; `width` scalars per entry."""
        s = self.sections.get(name)
        if s is None:
            raise Refused("envelope-invalid: section `%s` is missing" % name)
        if s["dtype"] != dtype:
            raise Refused("envelope-invalid: section `%s` is %s, the layout says %s" % (name, s["dtype"], dtype))
        code, size = DTYPES[dtype]
        if s["size"] % (size * width) != 0:
            raise Refused("envelope-invalid: section `%s` has a partial entry" % name)
        count = s["size"] // size
        return struct.unpack_from("<%d%s" % (count, code), self.buf, s["offset"])

    def raw(self, name):
        s = self.sections.get(name)
        if s is None:
            raise Refused("envelope-invalid: section `%s` is missing" % name)
        return self.buf[s["offset"]:s["offset"] + s["size"]]

    def strings(self, prefix):
        """A string table: `<prefix>-offsets` (u64, one more than there are strings) and
        `<prefix>-bytes` (UTF-8). String i is bytes[offsets[i] : offsets[i+1]]."""
        offsets = self.column(prefix + "-offsets", "u64")
        data = self.raw(prefix + "-bytes")
        if not offsets or offsets[0] != 0 or offsets[-1] != len(data):
            raise Refused("envelope-invalid: `%s-offsets` does not span `%s-bytes`" % (prefix, prefix))
        out = []
        for a, b in zip(offsets, offsets[1:]):
            if b < a:
                raise Refused("envelope-invalid: `%s-offsets` runs backwards" % prefix)
            out.append(bytes(data[a:b]).decode("utf-8"))
        return out


class Values:
    """The value sections both binaries share: kind / number / ref per entry, a string table,
    and an array table whose arrays may only refer to EARLIER arrays."""

    def __init__(self, env):
        self.kind = env.column("kind", "u8")
        self.number = env.column("number", "f64")
        self.ref = env.column("ref", "u32")
        if not (len(self.kind) == len(self.number) == len(self.ref)):
            raise Refused("envelope-invalid: kind / number / ref differ in length")
        self.texts = env.strings("text")
        dims = env.column("array-dims", "u32", 4)
        ek, en, ex = env.column("elem-kind", "u8"), env.column("elem-number", "f64"), env.column("elem-ref", "u32")
        if not (len(ek) == len(en) == len(ex)):
            raise Refused("envelope-invalid: the element sections differ in length")
        self.arrays = []
        for a in range(len(dims) // 4):
            rows, cols, first, count = dims[4 * a:4 * a + 4]
            if first + count > len(ek):
                raise Refused("envelope-invalid: array %d runs past the element sections" % a)
            values = [self.decode(ek[i], en[i], ex[i]) for i in range(first, first + count)]
            self.arrays.append({"array": {"rows": rows, "cols": cols, "values": values}})

    def decode(self, kind, number, ref):
        if kind == 0:
            return None
        if kind == 1:
            return number
        if kind == 2:
            if ref >= len(self.texts):
                raise Refused("envelope-invalid: string index %d is out of range" % ref)
            return self.texts[ref]
        if kind == 3:
            if ref > 1:
                raise Refused("envelope-invalid: boolean ref %d" % ref)
            return ref == 1
        if kind == 4:
            if ref not in ERRORS:
                raise Refused("envelope-invalid: unknown error code %d" % ref)
            return {"error": ERRORS[ref]}
        if kind == 5:
            if ref > 2:
                raise Refused("envelope-invalid: non-finite code %d" % ref)
            return {"nonfinite": ["nan", "inf", "-inf"][ref]}
        if kind == 6:
            if ref >= len(self.arrays):
                raise Refused("envelope-invalid: array index %d is not an earlier array" % ref)
            return self.arrays[ref]
        raise Refused("envelope-invalid: unknown value kind %d" % kind)

    def get(self, i):
        return self.decode(self.kind[i], self.number[i], self.ref[i])


def a1(row, col):
    letters = ""
    n = col + 1
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return "%s%d" % (letters, row + 1)


def read_cells(buf, uid):
    """One INFLATED band of a core.sheet.cells store -> {(row, col): cell}. A formula cell has
    value None here; its cached result is in the computed node."""
    env = Envelope(buf, b"WKX0", "core.sheet.cells")
    if env.header.get("sheet_uid") != uid:
        raise Refused("envelope-invalid: sheet_uid %r, expected %d" % (env.header.get("sheet_uid"), uid))
    rows, cols = env.column("row", "u32"), env.column("col", "u32")
    styles, formula_of = env.column("style", "u32"), env.column("formula", "u32")
    values = Values(env)
    n = len(values.kind)
    if not (len(rows) == len(cols) == len(styles) == len(formula_of) == n):
        raise Refused("envelope-invalid: the per-cell sections differ in length")
    formulas = env.strings("formula")
    arrays = env.column("formula-array", "u32", 5)
    if len(arrays) != 5 * len(formulas):
        raise Refused("envelope-invalid: `formula-array` does not hold one entry per formula")
    cells = {}
    last = None
    for i in range(n):
        key = (rows[i], cols[i])
        if last is not None and key <= last:
            raise Refused("envelope-invalid: cells are not sorted by row, then column")
        last = key
        formula, array_range = None, None
        f = formula_of[i]
        if f != NONE:
            if f >= len(formulas):
                raise Refused("envelope-invalid: formula index %d is out of range" % f)
            formula = formulas[f]
            if arrays[5 * f] == 1:
                array_range = list(arrays[5 * f + 1:5 * f + 5])
        value = values.get(i)
        if formula is not None and value is not None:
            raise Refused("envelope-invalid: a formula cell carries a value")
        if key[0] >= 1048576 or key[1] >= 16384:
            continue  # outside the grid: refuse the value, keep the rest
        cells[key] = {"row": key[0], "col": key[1], "a1": a1(*key), "style": styles[i], "value": value,
                      "formula": formula, "array_range": array_range, "spilled": False}
    return cells


def read_computed(buf, uid):
    """One INFLATED band of a core.sheet.computed store -> (cached, spilled, spill ranges):
    the cached result of each formula cell (source 0), the values dynamic arrays spilled
    (source 1), and the rectangle each dynamic array fills."""
    env = Envelope(buf, b"WKX1", "core.sheet.computed")
    if env.header.get("sheet_uid") != uid:
        raise Refused("envelope-invalid: sheet_uid %r, expected %d" % (env.header.get("sheet_uid"), uid))
    rows, cols, sources = env.column("row", "u32"), env.column("col", "u32"), env.column("source", "u8")
    values = Values(env)
    if not (len(rows) == len(cols) == len(sources) == len(values.kind)):
        raise Refused("envelope-invalid: the per-entry sections differ in length")
    cached, spilled = [], []
    for i in range(len(rows)):
        key = (rows[i], cols[i])
        if key[0] >= 1048576 or key[1] >= 16384:
            continue
        if sources[i] == 0:
            cached.append((key, values.get(i)))
        elif sources[i] == 1:
            spilled.append((key, values.get(i)))
        else:
            raise Refused("envelope-invalid: source %d" % sources[i])
    ranges = env.column("spill-ranges", "u32", 6)
    return cached, spilled, [list(ranges[6 * k:6 * k + 6]) for k in range(len(ranges) // 6)]


def apply_computed(cached, spilled, cells):
    """Fill in the cached result of each formula cell and add the spilled values."""
    for key, value in cached:
        if key in cells and cells[key]["formula"] is not None:
            cells[key]["value"] = value
    for key, value in spilled:
        if key not in cells:
            cells[key] = {"row": key[0], "col": key[1], "a1": a1(*key), "style": None, "value": value,
                          "formula": None, "array_range": None, "spilled": True}
        elif cells[key]["value"] is None and cells[key]["formula"] is None:
            cells[key]["value"] = value
            cells[key]["spilled"] = True


# ---------------------------------------------------------------- the document

class Document:
    def __init__(self, path, revision=None):
        self.container = Container(path)
        try:
            self.manifest = json.loads(self.container.read("MANIFEST.json").decode("utf-8"))
        except ValueError as e:
            raise ValueError("bad-manifest: %s" % e)
        if self.manifest.get("profile") != PROFILE:
            raise ValueError("unsupported-profile: %r is not %s" % (self.manifest.get("profile"), PROFILE))
        conv = self.manifest.get("conventions", {})
        want = {"cell_index_base": 0, "grid_rows": 1048576, "grid_cols": 16384, "hash_algorithm": "sha256",
                "text_encoding": "utf-8", "number_type": "ieee754-binary64", "endianness": "le"}
        for key, value in want.items():
            if conv.get(key) != value:
                raise ValueError("unsupported-convention: %s is %r, this reader implements %r" % (key, conv.get(key), value))
        self.nodes = {n["node_id"]: n for n in self.manifest["nodes"]}
        self.lost = []
        self.messages = []
        self.uses, self.revision = self.resolve_revision(revision)

    def resolve_revision(self, wanted):
        """spec/CRAFT-BASE.md section 3: the `revisions` node holds one record per Save; record
        K maps node_id -> the version of that node the document used at revision K."""
        node = self.nodes.get("revisions")
        fallback = {i: n["active"] for i, n in self.nodes.items()}
        if node is None:
            self.messages.append("no revision log: the active version of every node is the document")
            return fallback, 0
        v = node["active"] if wanted is None else wanted
        try:
            version = [x for x in node["versions"] if x["v"] == v][0]
            ref = version["files"][0]
            data = self.container.read(ref["path"])
            if hashlib.sha256(data).hexdigest() != ref["sha256"]:
                raise Refused("hash-mismatch")
            record = json.loads(data.decode("utf-8"))
            return dict(record["nodes"]), record["revision"]
        except (Refused, KeyError, IndexError, ValueError) as e:
            if wanted is not None:
                raise ValueError("no readable revision %s: %s" % (wanted, e))
            self.messages.append("the revision log is unreadable: the active version of every node is the document")
            return fallback, 0

    def version(self, node_id, node_type):
        node = self.nodes.get(node_id)
        if node is None or node_id not in self.uses:
            raise Refused("node `%s` is not part of this revision" % node_id)
        if node["type"] != node_type:
            raise Refused("node `%s` is a %s, expected %s" % (node_id, node["type"], node_type))
        for v in node["versions"]:
            if v["v"] == self.uses[node_id]:
                if "compacted" in v:
                    raise Refused("version-compacted: `%s` v%d" % (node_id, v["v"]))
                return v
        raise Refused("node `%s` has no version %s" % (node_id, self.uses[node_id]))

    def file(self, version, ref):
        try:
            data = self.container.read(ref["path"])
        except (KeyError, OSError):
            raise Refused("file-missing: %s" % ref["path"])
        if len(data) != ref["size"] or hashlib.sha256(data).hexdigest() != ref["sha256"]:
            raise Refused("hash-mismatch: %s" % ref["path"])
        return data

    def payload(self, node_id, node_type):
        """The payload file of a node (spec/SPEC.md section 2.1): `payload_file` if declared,
        else the only file. NEVER files[0] of several."""
        version = self.version(node_id, node_type)
        files = version["files"]
        if "payload_file" in version:
            ref = [f for f in files if f["path"] == version["payload_file"]][0]
        elif len(files) == 1:
            ref = files[0]
        else:
            raise Refused("payload-file-ambiguous: `%s`" % node_id)
        return self.file(version, ref)

    def bands(self, node_id, node_type, store, uid):
        """A banded store (spec/PROFILE-SPREADSHEET.md section 3.3): the node's payload is an
        INDEX; each band is a file of the same node version, found by the sha256 the index
        gives, and is one zlib stream whose inflated bytes are one envelope. Returns the
        inflated bands in row order: [(first_row, row_count, bytes)]."""
        index = self.json_payload(node_id, node_type)
        if index.get("store") != store or index.get("sheet_uid") != uid or index.get("band_format") != "zlib-deflate":
            raise Refused("payload-schema-invalid: `%s` is not the %s index of sheet %d" % (node_id, store, uid))
        version = self.version(node_id, node_type)
        by_hash = {f["sha256"]: f for f in version["files"]}
        out, next_free = [], 0
        for band in index["bands"]:
            first, count = band["first_row"], band["row_count"]
            if count < 1 or first < next_free or first + count > 1048576:
                raise Refused("band-invalid: rows %d..%d overlap the band before or leave the grid" % (first, first + count))
            next_free = first + count
            ref = by_hash.get(band["stored_sha256"])
            if ref is None:
                raise Refused("file-missing: no file of `%s` has the sha256 of band %s" % (node_id, band["path"]))
            stored = self.file(version, ref)
            try:
                inflated = zlib.decompress(stored)
            except zlib.error as e:
                raise Refused("band-invalid: %s is not a zlib stream (%s)" % (band["path"], e))
            if len(inflated) != band["inflated_size"] or hashlib.sha256(inflated).hexdigest() != band["inflated_sha256"]:
                raise Refused("hash-mismatch: %s does not inflate to the bytes the index names" % band["path"])
            out.append((first, count, inflated))
        return out

    def json_payload(self, node_id, node_type):
        data = self.payload(node_id, node_type)
        value = json.loads(data.decode("utf-8"))
        if value.get("schema_version") != 1:
            raise Refused("payload-schema-invalid: `%s`: schema_version" % node_id)
        return value

    def attempt(self, node_id, fn, default=None):
        """Law 3: a node that cannot be read costs that node, never the document."""
        try:
            return fn()
        except (Refused, KeyError, IndexError, ValueError, struct.error, UnicodeDecodeError) as e:
            if node_id not in self.lost:
                self.lost.append(node_id)
                self.messages.append("lost node `%s`: %s" % (node_id, e))
            return default

    def read(self):
        primary = self.manifest.get("primary", {}).get("document", "workbook")
        wb = self.attempt(primary, lambda: self.json_payload(primary, "core.sheet.workbook"))
        if wb is None:
            wb = {"sheets": [i for i, n in self.nodes.items() if n["type"] == "core.sheet.sheet" and i in self.uses],
                  "active_sheet_index": 0, "date_system": "D1900", "names": "names", "styles": "styles"}
        out = {"profile": PROFILE, "uuid": self.manifest["entity"]["uuid"], "revision": self.revision,
               "date_system": wb["date_system"], "sheets": [], "names": [], "cell_formats": 0, "external_values": None}
        for sheet_id in wb["sheets"]:
            sheet = self.read_sheet(sheet_id)
            if sheet is not None:
                out["sheets"].append(sheet)
        ids = [s["node"] for s in out["sheets"]]
        active = wb.get("active_sheet")
        out["active_sheet"] = ids.index(active) if active in ids else wb.get("active_sheet_index", 0)
        if "names" in wb:
            names = self.attempt(wb["names"], lambda: self.json_payload(wb["names"], "core.sheet.names"))
            for n in (names or {}).get("names", []):
                scope = n.get("scope_sheet")
                if scope is not None and scope not in ids:
                    continue
                out["names"].append({"name": n["name"], "formula": n["formula"], "comment": n["comment"], "hidden": n["hidden"],
                                     "scope": ids.index(scope) if scope is not None else n.get("scope_index")})
        if "styles" in wb:
            styles = self.attempt(wb["styles"], lambda: self.json_payload(wb["styles"], "core.sheet.styles"))
            out["cell_formats"] = len((styles or {}).get("cell_formats", []))
        if "external_values" in wb:
            node_id = wb["external_values"]
            out["external_values"] = self.attempt(node_id, lambda: self.json_payload(node_id, "core.sheet.external-values"))
        out["lost"] = sorted(self.lost)
        return out

    def read_sheet(self, sheet_id):
        info = self.attempt(sheet_id, lambda: self.json_payload(sheet_id, "core.sheet.sheet"))
        if info is None:
            # The sheet node is gone; its cells are a node of their own.
            uid = sheet_id[len("sheet-"):]
            if not uid.isdigit() or ("sheet-%s-cells" % uid) not in self.uses:
                return None
            info = {"uid": int(uid), "name": "Recovered sheet %s" % uid, "visibility": "Visible", "merges": [],
                    "cells": "sheet-%s-cells" % uid, "charts": [], "pivots": [], "images": [], "cell_pictures": []}
            if ("sheet-%s-computed" % uid) in self.uses:
                info["computed"] = "sheet-%s-computed" % uid
        uid = info["uid"]
        cells, spill_ranges = {}, []
        if "cells" in info:
            def stored_cells():
                # Every band is decoded before anything is kept: a broken band costs the node.
                found = {}
                for first, count, buf in self.bands(info["cells"], "core.sheet.cells", "cells", uid):
                    band = read_cells(buf, uid)
                    if any(not (first <= row < first + count) for row, _ in band):
                        raise Refused("band-invalid: a cell lies outside the rows of its band")
                    found.update(band)
                return found
            cells = self.attempt(info["cells"], stored_cells, {})
        if "computed" in info:
            def computed():
                # Decode into a copy first: a broken file must not leave half of it applied.
                copy = {k: dict(v) for k, v in cells.items()}
                ranges = []
                for first, count, buf in self.bands(info["computed"], "core.sheet.computed", "computed", uid):
                    cached, spilled, band_ranges = read_computed(buf, uid)
                    if any(not (first <= key[0] < first + count) for key, _ in cached + spilled):
                        raise Refused("band-invalid: an entry lies outside the rows of its band")
                    apply_computed(cached, spilled, copy)
                    ranges.extend(band_ranges)
                return copy, ranges
            result = self.attempt(info["computed"], computed)
            if result is not None:
                cells, spill_ranges = result
        charts = []
        for chart_id in info.get("charts", []):
            c = self.attempt(chart_id, lambda: self.json_payload(chart_id, "core.sheet.chart"))
            if c is not None:
                charts.append({"node": chart_id, "id": c["id"], "kind": c["kind"], "title": c["title"],
                               "series": [s["values"] for s in c["series"]]})
        pivots = []
        for pivot_id in info.get("pivots", []):
            p = self.attempt(pivot_id, lambda: self.json_payload(pivot_id, "core.sheet.pivot"))
            if p is not None:
                pivots.append({"node": pivot_id, "name": p.get("name"), "source": p.get("source")})
        pictures = []
        for pic in info.get("images", []) + info.get("cell_pictures", []):
            pictures.append(self.read_picture(pic))
        return {"node": sheet_id, "uid": uid, "name": info["name"], "visibility": info["visibility"],
                "cells": [cells[k] for k in sorted(cells)], "spill_ranges": spill_ranges,
                "merges": len(info.get("merges", [])), "charts": charts, "pivots": pivots, "pictures": pictures}

    def read_picture(self, pic):
        """The picture's bytes: the node `media` holds the original; `png`, when present, holds
        a PNG rendition for readers that do not decode the original's encoding."""
        out = {"mime": pic["mime"], "alt": pic["alt"], "media": pic["media"], "png": pic.get("png"),
               "sha256": None, "png_sha256": None}
        for key, field in (("media", "sha256"), ("png", "png_sha256")):
            node_id = pic.get(key)
            if node_id is None or node_id not in self.nodes:
                continue
            node_type = self.nodes[node_id]["type"]
            data = self.attempt(node_id, lambda: self.payload(node_id, node_type))
            if data is not None:
                out[field] = hashlib.sha256(data).hexdigest()
        return out


def csv_text(value):
    if value is None:
        return ""
    if value is True:
        return "TRUE"
    if value is False:
        return "FALSE"
    if isinstance(value, dict):
        if "error" in value:
            return value["error"]
        if "array" in value:
            first = value["array"]["values"][:1]
            return csv_text(first[0]) if first else ""
        return "#NUM!"
    if isinstance(value, float):
        return repr(int(value)) if value == int(value) and abs(value) < 1e15 else repr(value)
    return str(value)


def sheet_csv(sheet):
    rows = {}
    for c in sheet["cells"]:
        rows.setdefault(c["row"], {})[c["col"]] = csv_text(c["value"])
    lines = []
    for r in range(max(rows) + 1 if rows else 0):
        cols = rows.get(r, {})
        fields = [cols.get(c, "") for c in range(max(cols) + 1 if cols else 0)]
        quoted = ['"%s"' % f.replace('"', '""') if any(ch in f for ch in ',"\n\r') else f for f in fields]
        lines.append(",".join(quoted))
    return "\n".join(lines) + "\n"


def main(argv):
    args = argv[1:]
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")  # a console that is not UTF-8 must not stop the read
    if not args or args[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 2
    revision = None
    if "--revision" in args:
        i = args.index("--revision")
        revision = int(args[i + 1])
        del args[i:i + 2]
    try:
        doc = Document(args[0], revision)
        content = doc.read()
    except ValueError as e:
        print("REFUSED (container scope): %s" % e)
        return 2
    if "--json" in args:
        with open(args[args.index("--json") + 1], "w", encoding="utf-8", newline="\n") as fh:
            json.dump(content, fh, ensure_ascii=False, indent=1)
    if "--csv" in args:
        name, target = args[args.index("--csv") + 1], args[args.index("--csv") + 2]
        sheets = [s for s in content["sheets"] if s["name"] == name]
        if not sheets:
            print("no sheet named %r" % name)
            return 1
        with open(target, "w", encoding="utf-8", newline="") as fh:
            fh.write(sheet_csv(sheets[0]))
    print("%s  uuid %s  revision %d  signature unverified (this reader carries no Ed25519)"
          % (PROFILE, content["uuid"], content["revision"]))
    for s in content["sheets"]:
        formulas = sum(1 for c in s["cells"] if c["formula"] is not None)
        print("  sheet %-4d %-32r %6d cell(s), %d formula(s), %d chart(s), %d picture(s)"
              % (s["uid"], s["name"], len(s["cells"]), formulas, len(s["charts"]), len(s["pictures"])))
    print("  %d defined name(s), %d cell format(s)" % (len(content["names"]), content["cell_formats"]))
    for m in doc.messages:
        print("  ! " + m)
    return 1 if doc.lost else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
