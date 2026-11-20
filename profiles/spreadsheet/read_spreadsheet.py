#!/usr/bin/env python3
"""read_spreadsheet.py -- reference reader of werk profile spreadsheet/1 (werk release).

    python read_spreadsheet.py PACKAGE [--json OUT]

Reads a spreadsheet/1 package (directory or .werk zip) the way spec/PROFILE-SPREADSHEET.md
section 6 says: the workbook, each sheet in tab order, its banded cells store (index, then each
band found by its stored_sha256, inflated, checked, decoded as spec/layouts/core.sheet.cells
.layout.txt says) and its cached results (core.sheet.computed, the same way), and prints the
extraction profiles/spreadsheet/PROFILE.md ("What a reader outputs") defines, as canonical JSON
(UTF-8, keys sorted, indent 1): per sheet, every stored cell by its A1 address with its
displayed value (constant, or the cached result of its formula), its formula text, its format
index and number format, and whether the cached results' input_hash still matches their
inputs (MINI-SPECS section 11). It evaluates no formula. Every file it uses is checked against
MANIFEST.json first. Pure Python 3.8+ standard library; it runs nothing it finds in the package.

Exit status: 0 read, nothing dead; 1 read, with dead or missing nodes (listed under "dead");
2 not readable as a spreadsheet/1 package.
"""
# ---- container block: shared verbatim by the six profiles/*/read_*.py readers -------------
# (profiles/tools/check_readers.py checks that every reader carries this block unchanged.)
# A werk package is a directory, or that tree as a zip (store or deflate entries, no zip64).
# MANIFEST.json is the only index; every file is reached node -> version -> files[] and checked
# against its sha256 and size before it is used (spec/SPEC.md sections 1, 2, 2.1).
import hashlib, json, os, struct, sys, zlib


class Refusal(Exception):
    """The container cannot be read at all (spec/SPEC.md 10.1, container scope): exit 2."""


class Dead(Exception):
    """One node cannot be used (missing file, hash or size mismatch, unparseable payload)."""


def _sha(b):
    return hashlib.sha256(b).hexdigest()


class Package(object):
    def __init__(self, path):
        self.path = path
        self._zip = None
        if os.path.isdir(path):
            self._dir = path
        else:
            self._dir = None
            with open(path, "rb") as fh:
                self._blob = fh.read()
            self._zip = self._central_directory(self._blob)
        try:
            self.manifest = json.loads(self._raw("MANIFEST.json").decode("utf-8"))
        except Refusal:
            raise
        except Exception as e:  # noqa: BLE001
            raise Refusal("MANIFEST.json unreadable: %s" % e)
        if not isinstance(self.manifest, dict) or not isinstance(self.manifest.get("nodes"), list):
            raise Refusal("MANIFEST.json has no nodes[]")
        self.nodes = {}
        for n in self.manifest["nodes"]:
            if isinstance(n, dict) and isinstance(n.get("node_id"), str):
                self.nodes[n["node_id"]] = n
        self.verified = set()

    @staticmethod
    def _central_directory(b):
        eocd = b.rfind(b"PK\x05\x06")
        if eocd < 0 or len(b) < eocd + 22:
            raise Refusal("not a zip and not a directory")
        count, size, off = struct.unpack_from("<HII", b, eocd + 10)
        if count == 0xFFFF or size == 0xFFFFFFFF or off == 0xFFFFFFFF:
            raise Refusal("zip64 is not part of the format")
        out, p = {}, off
        for _ in range(count):
            if b[p:p + 4] != b"PK\x01\x02":
                raise Refusal("damaged central directory")
            flags, method = struct.unpack_from("<HH", b, p + 8)
            csize, usize = struct.unpack_from("<II", b, p + 20)
            nlen, xlen, clen = struct.unpack_from("<HHH", b, p + 28)
            lho = struct.unpack_from("<I", b, p + 42)[0]
            name = b[p + 46:p + 46 + nlen].decode("utf-8", "replace")
            if name in out:
                raise Refusal("duplicate entry name %s" % name)
            out[name] = (lho, method, csize, usize, flags)
            p += 46 + nlen + xlen + clen
        return out

    def _raw(self, path):
        if self._dir is not None:
            full = os.path.join(self._dir, *path.split("/"))
            if not os.path.isfile(full):
                raise Dead("file missing: %s" % path)
            with open(full, "rb") as fh:
                return fh.read()
        ent = self._zip.get(path)
        if ent is None:
            if path == "MANIFEST.json":
                raise Refusal("no MANIFEST.json")
            raise Dead("file missing: %s" % path)
        lho, method, csize, usize, flags = ent
        b = self._blob
        if b[lho:lho + 4] != b"PK\x03\x04":
            raise Dead("bad local header: %s" % path)
        nlen, xlen = struct.unpack_from("<HH", b, lho + 26)
        data = b[lho + 30 + nlen + xlen:lho + 30 + nlen + xlen + csize]
        if method == 0:
            return data
        if method == 8:
            try:
                return zlib.decompress(data, -15)
            except zlib.error as e:
                raise Dead("deflate error in %s: %s" % (path, e))
        raise Dead("unsupported zip method %d: %s" % (method, path))

    def node(self, nid):
        n = self.nodes.get(nid)
        if n is None:
            raise Dead("no node %s" % nid)
        return n

    def version(self, nid, v=None):
        n = self.node(nid)
        want = n.get("active") if v is None else v
        for ver in n.get("versions") or []:
            if isinstance(ver, dict) and ver.get("v") == want:
                return ver
        raise Dead("node %s has no version %s" % (nid, want))

    def read(self, rec):
        """The bytes of one files[] record, checked against its size and sha256."""
        data = self._raw(rec["path"])
        if len(data) != rec.get("size") or _sha(data) != rec.get("sha256"):
            raise Dead("hash or size mismatch: %s" % rec["path"])
        self.verified.add(rec["path"])
        return data

    def payload(self, nid, v=None):
        """(record, bytes) of the node's payload file (spec/SPEC.md 2.1: payload_file, else
        the only file)."""
        ver = self.version(nid, v)
        files = ver.get("files") or []
        pf = ver.get("payload_file")
        if pf is None:
            if len(files) != 1:
                raise Dead("node %s: payload not determinable" % nid)
            rec = files[0]
        else:
            rec = next((f for f in files if f.get("path") == pf), None)
            if rec is None:
                raise Dead("node %s: payload_file not listed" % nid)
        return rec, self.read(rec)

    def by_role(self, nid, role, v=None):
        ver = self.version(nid, v)
        rec = next((f for f in ver.get("files") or [] if f.get("role") == role), None)
        if rec is None:
            raise Dead("node %s: no file with role %s" % (nid, role))
        return rec, self.read(rec)

    def json_payload(self, nid, v=None):
        rec, data = self.payload(nid, v)
        try:
            return json.loads(data.decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            raise Dead("node %s: payload is not JSON: %s" % (nid, e))

    def verify_all(self):
        """Every file of every version of every node: (number verified, [failures])."""
        bad, n = [], 0
        for nid, node in self.nodes.items():
            for ver in node.get("versions") or []:
                for rec in ver.get("files") or []:
                    try:
                        self.read(rec)
                        n += 1
                    except Dead as e:
                        bad.append("%s: %s" % (nid, e))
        return n, bad


def mp_decode(b, i=0):
    """MessagePack, the subset the envelope header uses (ENVELOPE.layout.txt section 4)."""
    c = b[i]
    if c <= 0x7F:
        return c, i + 1
    if c >= 0xE0:
        return c - 256, i + 1
    if 0xA0 <= c <= 0xBF:
        n = c & 0x1F
        return b[i + 1:i + 1 + n].decode("utf-8"), i + 1 + n
    if 0x90 <= c <= 0x9F:
        return _mp_seq(b, i + 1, c & 0x0F)
    if 0x80 <= c <= 0x8F:
        return _mp_map(b, i + 1, c & 0x0F)
    simple = {0xC0: None, 0xC2: False, 0xC3: True}
    if c in simple:
        return simple[c], i + 1
    ints = {0xCC: ">B", 0xCD: ">H", 0xCE: ">I", 0xCF: ">Q", 0xD0: ">b", 0xD1: ">h", 0xD2: ">i", 0xD3: ">q",
            0xCA: ">f", 0xCB: ">d"}
    if c in ints:
        sz = struct.calcsize(ints[c])
        return struct.unpack_from(ints[c], b, i + 1)[0], i + 1 + sz
    if c in (0xD9, 0xDA, 0xDB):
        fmt = {0xD9: ">B", 0xDA: ">H", 0xDB: ">I"}[c]
        sz = struct.calcsize(fmt)
        n = struct.unpack_from(fmt, b, i + 1)[0]
        j = i + 1 + sz
        return b[j:j + n].decode("utf-8"), j + n
    if c in (0xDC, 0xDD):
        fmt = ">H" if c == 0xDC else ">I"
        sz = struct.calcsize(fmt)
        return _mp_seq(b, i + 1 + sz, struct.unpack_from(fmt, b, i + 1)[0])
    if c in (0xDE, 0xDF):
        fmt = ">H" if c == 0xDE else ">I"
        sz = struct.calcsize(fmt)
        return _mp_map(b, i + 1 + sz, struct.unpack_from(fmt, b, i + 1)[0])
    raise ValueError("MessagePack byte 0x%02x is not used by envelopes" % c)


def _mp_seq(b, i, n):
    out = []
    for _ in range(n):
        v, i = mp_decode(b, i)
        out.append(v)
    return out, i


def _mp_map(b, i, n):
    out = {}
    for _ in range(n):
        k, i = mp_decode(b, i)
        v, i = mp_decode(b, i)
        out[k] = v
    return out, i


def envelope(data, magic=None):
    """(header dict, {section name: bytes}) of a binary envelope (ENVELOPE.layout.txt 1)."""
    if len(data) < 12 or data[:2] != b"WK":
        raise Dead("not an envelope")
    if magic is not None and data[:4] != magic:
        raise Dead("envelope magic %r, expected %r" % (data[:4], magic))
    ver, hlen = struct.unpack_from("<II", data, 4)
    if ver != 1:
        raise Dead("envelope version %d" % ver)
    header, _ = mp_decode(data[12:12 + hlen])
    secs = {}
    for s in header.get("sections") or []:
        o, n = s["offset"], s["size"]
        if o + n > len(data):
            raise Dead("section %s outside the file" % s.get("name"))
        secs[s["name"]] = data[o:o + n]
    return header, secs


def emit(result, out_path=None):
    text = json.dumps(result, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    if out_path:
        with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    else:
        sys.stdout.buffer.write(text.encode("utf-8"))
# ---- end of container block -------------------------------------------------------------

PROFILE = "spreadsheet/1"
NONE = 4294967295
ERRORS = {1: "#NULL!", 2: "#DIV/0!", 3: "#VALUE!", 4: "#REF!", 5: "#NAME?", 6: "#NUM!", 7: "#N/A",
          8: "#GETTING_DATA", 9: "#SPILL!", 14: "#CALC!", 15: "#CIRC!"}


def a1(row, col):
    s, c = "", col + 1
    while c:
        c, r = divmod(c - 1, 26)
        s = chr(65 + r) + s
    return "%s%d" % (s, row + 1)


def _arr(fmt, data):
    n = len(data) // struct.calcsize("<" + fmt)
    return struct.unpack("<%d%s" % (n, fmt), data)


def _strings(offsets, data):
    off = _arr("Q", offsets)
    return [data[off[k]:off[k + 1]].decode("utf-8") for k in range(len(off) - 1)]


def _value(kind, number, ref, texts, arrays):
    if kind == 0:
        return None
    if kind == 1:
        return number
    if kind == 2:
        return texts[ref]
    if kind == 3:
        return bool(ref)
    if kind == 4:
        if ref not in ERRORS:
            raise Dead("unknown error code %d" % ref)
        return {"error": ERRORS[ref]}
    if kind == 5:
        return {"nonfinite": ["NaN", "+Infinity", "-Infinity"][ref]}
    if kind == 6:
        return {"array": arrays[ref]}
    raise Dead("unknown value kind %d" % kind)


def _arrays(s, texts):
    dims = _arr("I", s["array-dims"])
    ek, en, er = s["elem-kind"], _arr("d", s["elem-number"]), _arr("I", s["elem-ref"])
    out = []
    for j in range(len(dims) // 4):
        rows, cols, first, count = dims[4 * j:4 * j + 4]
        vals = [_value(ek[first + q], en[first + q], er[first + q], texts, out) for q in range(count)]
        out.append([vals[r * cols:(r + 1) * cols] for r in range(rows)])
    return out


def read_store(pkg, nid, magic, uid):
    """The decoded entries of a banded store (sections 3.3 / 3.4)."""
    idx = pkg.json_payload(nid)
    if idx.get("sheet_uid") != uid:
        raise Dead("%s: sheet_uid differs" % nid)
    files = pkg.version(nid).get("files") or []
    entries = []
    for band in idx["bands"]:
        rec = next((f for f in files if f.get("sha256") == band["stored_sha256"]), None)
        if rec is None:
            raise Dead("%s: band %s not among the version's files" % (nid, band["first_row"]))
        raw = zlib.decompress(pkg.read(rec))
        if len(raw) != band["inflated_size"] or _sha(raw) != band["inflated_sha256"]:
            raise Dead("%s: inflated band differs from the index" % nid)
        h, s = envelope(raw, magic)
        if h.get("sheet_uid") != uid:
            raise Dead("%s: band sheet_uid differs" % nid)
        texts = _strings(s["text-offsets"], s["text-bytes"])
        arrays = _arrays(s, texts)
        rows, cols = _arr("I", s["row"]), _arr("I", s["col"])
        kinds, nums, refs = s["kind"], _arr("d", s["number"]), _arr("I", s["ref"])
        prev = None
        for i in range(len(rows)):
            key = (rows[i], cols[i]) if magic == b"WKX0" else (rows[i], cols[i], s["source"][i])
            if prev is not None and key <= prev:
                raise Dead("%s: entries out of order" % nid)
            prev = key
            if not (band["first_row"] <= rows[i] < band["first_row"] + band["row_count"]):
                raise Dead("%s: a cell lies outside its band" % nid)
            e = {"row": rows[i], "col": cols[i], "value": _value(kinds[i], nums[i], refs[i], texts, arrays)}
            if magic == b"WKX0":
                forms = _strings(s["formula-offsets"], s["formula-bytes"])
                fi = _arr("I", s["formula"])[i]
                e["style"] = _arr("I", s["style"])[i]
                e["formula"] = None if fi == NONE else forms[fi]
                if fi != NONE and kinds[i] != 0:
                    raise Dead("%s: a formula cell with a stored value" % nid)
            else:
                e["source"] = s["source"][i]
                if e["source"] not in (0, 1):
                    raise Dead("%s: unknown source" % nid)
            entries.append(e)
    return entries


def _canon(v):
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def input_hash_ok(pkg, nid):
    """MINI-SPECS section 11 against the files the package now holds at those paths."""
    ver = pkg.version(nid)
    if ver.get("epistemic") == "authored":
        return None
    by_path = {}
    for n in pkg.nodes.values():
        try:
            for f in pkg.version(n["node_id"]).get("files") or []:
                by_path[f["path"]] = f["sha256"]
        except Dead:
            pass
    acc = b"".join(bytes.fromhex(by_path.get(p, "00" * 32)) for p in ver.get("input_files") or [])
    acc += _canon(ver.get("input_params") or {}) if ver.get("input_params") else b"{}"
    return _sha(acc) == ver.get("input_hash")


def read(path):
    pkg = Package(path)
    m = pkg.manifest
    if m.get("profile") != PROFILE:
        raise Refusal("profile is %r, not %s" % (m.get("profile"), PROFILE))
    dead, notes = [], []
    wid = (m.get("primary") or {}).get("document")
    try:
        wb = pkg.json_payload(wid)
    except Dead as e:
        raise Refusal("the workbook node is unreadable: %s" % e)
    fmts = []
    try:
        fmts = [f.get("num_fmt") for f in pkg.json_payload(wb.get("styles", "styles")).get("cell_formats") or []]
    except Dead as e:
        dead.append({"node": wb.get("styles"), "why": str(e)})
    sheets = []
    for sid in wb.get("sheets") or []:
        try:
            sp = pkg.json_payload(sid)
        except Dead as e:
            dead.append({"node": sid, "why": str(e)})
            continue
        uid = sp["uid"]
        cells, ok = {}, None
        try:
            for e in read_store(pkg, sp["cells"], b"WKX0", uid):
                st = e["style"]
                cells[a1(e["row"], e["col"])] = {"value": e["value"], "formula": e["formula"], "style": st,
                                                 "num_fmt": fmts[st] if st < len(fmts) else (fmts[0] if fmts else None)}
        except (Dead, KeyError, ValueError, zlib.error, struct.error) as e:
            dead.append({"node": sp["cells"], "why": str(e)})
            notes.append("%s: the cells store is dead; the sheet is shown empty" % sid)
        if sp.get("computed"):
            try:
                comp = read_store(pkg, sp["computed"], b"WKX1", uid)
                ok = input_hash_ok(pkg, sp["computed"])
                for e in comp:
                    k = a1(e["row"], e["col"])
                    c = cells.get(k)
                    if e["source"] == 0:
                        if c is None or c["formula"] is None:
                            notes.append("%s %s: cached result for a cell without a formula, ignored" % (sid, k))
                            continue
                        c["value"] = e["value"]
                        c["cached"] = True
                    elif c is None or (c["value"] is None and c["formula"] is None):
                        cells[k] = {"value": e["value"], "formula": None, "style": 0, "spilled": True,
                                    "num_fmt": fmts[0] if fmts else None}
            except (Dead, KeyError, ValueError, zlib.error, struct.error) as e:
                dead.append({"node": sp["computed"], "why": str(e)})
                notes.append("%s: no cached results; formula cells show their formula" % sid)
        sheets.append({"node": sid, "uid": uid, "name": sp.get("name"), "cells": cells,
                       "cell_count": len(cells), "formula_count": sum(1 for c in cells.values() if c["formula"]),
                       "computed_input_hash_ok": ok})
    nver, bad = pkg.verify_all()
    return {"profile": PROFILE, "title": (wb.get("props") or {}).get("title"), "date_system": wb.get("date_system"),
            "active_sheet": wb.get("active_sheet"), "sheets": sheets, "notes": notes,
            "dead": sorted(dead, key=lambda d: str(d["node"])), "files_verified": nver, "file_failures": bad}


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("package"); ap.add_argument("--json")
    a = ap.parse_args(argv)
    try:
        res = read(a.package)
    except Refusal as e:
        sys.stderr.write("refused: %s\n" % e)
        return 2
    emit(res, a.json)
    return 1 if (res["dead"] or res["file_failures"]) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
