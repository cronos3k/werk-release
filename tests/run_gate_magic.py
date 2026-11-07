#!/usr/bin/env python3
"""run_gate_magic.py -- GATE MAGIC: an envelope is recognised by its FRAME, by
all four reference readers, and the table of reserved magics exists once.

    python tests/run_gate_magic.py

Ruling 4 of 2026-10-13 (docs/RULINGS-2026-10-13.md; SPEC.md section 3.1;
spec/layouts/ENVELOPE.layout.txt section 2).

THE FINDING. A reader used to recognise an envelope only if its magic was in
that reader's own copy of a table. There were four copies. The ArtCraft corpus
carries 365 envelopes outside `core.spec` in 40 packages, nearly all of them
under profile and extension kinds, and a magic absent from a reader's table was not
parsed by that reader and not reported by it either: silence, which SPEC
section 10 calls a bug.

WHAT THIS GATE HOLDS.

  1  THE TABLE. The seven reserved magics, and the kind each binds, are read
     out of the normative text and out of the source of each of the four
     readers, and must be the same seven pairs five times. (A table that is a
     consistency check may be copied; a copy that drifts must be caught.)

  2  THE BEHAVIOUR, on one real package (the CC0 lean crate) to which one
     extension node carrying one binary file is added four ways:
       a  a well-formed envelope under a magic NO table has ("WKQ7")
            -> every reader loads the package, exit 0, and reports no invalid
               envelope; the core counts one more validated envelope and says
               the kind has no grammar in `layouts` (`envelope-undeclared`);
       b  the same envelope with its frame broken
            -> every reader reports `envelope-invalid` against that node:
               the proof that the unknown magic was parsed and not passed over;
       c  a RESERVED magic ("WKRP") over a header that says another kind
            -> every reader reports `envelope-invalid`;
       d  four bytes that are not a magic ("WKq7")
            -> no reader says anything about envelopes: it is not one.

The package is unsigned on purpose (the manifest is rewritten here), which is
the state `signature-absent`, not an error.
"""

import hashlib
import json
import os
import re
import shutil
import struct
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate_common as G                                        # noqa: E402
from fixture_pin import pin                                    # noqa: E402
sys.path.insert(0, os.path.join(G.ROOT, "pipeline"))
from common import write_envelope                              # noqa: E402

WORK = os.path.join(G.ROOT, "core", "target", "gate-magic")
BASE = os.path.join(G.FIX, "crate-cc0-lean-v1.werk")
NODE, KIND, PATH = "x-gate-envelope", "x.gate.blob", "x/gate/blob.bin"

PAIR = re.compile(r'"?(WK[A-Z0-9]{2})"?[^A-Za-z0-9]+(?:=> Some\()?"?(core\.[a-z.]+[a-z])')

SOURCES = [
    ("spec/layouts/ENVELOPE.layout.txt", "The seven magics in the table are RESERVED",
     "that says another kind is malformed"),
    ("core/src/envelope.rs", "pub const RESERVED_MAGICS", "];"),
    ("loaders/werk_read.py", "MAGIC_KIND = {", "}"),
    ("loaders/werk_read.rs", "fn magic_kind(", "_ => None"),
    ("loaders/werk_read.c", "magickind ENV_MAGIC[] = {", "};"),
]


def table(rel, start, end):
    text = open(os.path.join(G.ROOT, rel), encoding="utf-8").read()
    at = text.index(start)
    return dict(PAIR.findall(" ".join(text[at:text.index(end, at)].split())))


def package(dest, blob):
    """The lean crate plus one extension node carrying `blob`; unsigned."""
    with zipfile.ZipFile(BASE) as zin:
        manifest = json.loads(zin.read("MANIFEST.json"))
        manifest["container"].pop("preview_prefix_bytes", None)
        manifest["nodes"].append({
            "node_id": NODE, "type": KIND, "active": 1, "edges": [],
            "versions": [{
                "v": 1, "epistemic": "authored", "created": "2026-10-13T00:00:00Z",
                "note": "One binary file under an extension type, added by "
                        "tests/run_gate_magic.py to ask a reader what it does with it.",
                "producer": {"tool": "tests/run_gate_magic.py", "version": "1"},
                "files": [{"path": PATH, "size": len(blob),
                           "sha256": hashlib.sha256(blob).hexdigest()}]}]})
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_STORED) as zout:
            def put(name, data):
                zout.writestr(zipfile.ZipInfo(name, (2026, 8, 8, 9, 0, 0)), data)
            put("MANIFEST.json", json.dumps(manifest, indent=1, ensure_ascii=False)
                .encode("utf-8"))
            for info in zin.infolist():
                if info.filename not in ("MANIFEST.json", "SIGNATURE.json"):
                    put(info.filename, zin.read(info.filename))
            put(PATH, blob)
    return dest


def envelope_lines(out):
    return [l.strip() for l in out.splitlines() if re.search(r"envelope-[a-z]+", l)]


def main():
    gate = G.Gate("MAGIC")
    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK)
    r = pin("crate-cc0-lean-v1")
    gate.record("fixture pinned: crate-cc0-lean-v1", "PASS" if r.ok else "FAIL", r.detail)

    # ---- 1. one table, five places ---------------------------------------
    tables = [(rel, table(rel, a, b)) for rel, a, b in SOURCES]
    norm = tables[0][1]
    gate.check("reserved magics in the normative text", len(norm) == 7,
               " ".join("%s=%s" % kv for kv in sorted(norm.items())),
               "found %d: %s" % (len(norm), sorted(norm.items())))
    for rel, t in tables[1:]:
        gate.check("same table: %s" % rel, t == norm, "7 of 7 magic/kind pairs identical",
                   "differs: %s" % sorted(set(t.items()) ^ set(norm.items())))

    # ---- 2. behaviour ------------------------------------------------------
    payload = struct.pack("<8f", *[float(i) for i in range(8)])
    good = write_envelope("WKQ7", KIND, {"note": "gate"}, [("values", "f32", [8], 4, payload)])
    broken = bytearray(good)
    broken[8:12] = struct.pack("<I", len(good) * 4)       # header runs past the file
    reserved = write_envelope("WKRP", KIND, {"note": "gate"},
                              [("values", "f32", [8], 4, payload)])
    not_one = b"WKq7" + bytes(good[4:])
    readers = G.readers(gate)
    core = next((x for x in readers if x[0] == "core"), None)
    base_n = None
    if core:
        _rc, out = G.verify(core, BASE)
        m = re.search(r"^envelopes\s*:\s*(\d+)", out, re.M)
        base_n = int(m.group(1)) if m else None

    cases = [
        ("a", "unknown magic WKQ7, well formed", bytes(good)),
        ("b", "unknown magic WKQ7, frame broken", bytes(broken)),
        ("c", "reserved magic WKRP, another kind", reserved),
        ("d", "bytes WKq7 (not a magic)", not_one),
    ]
    for key, label, blob in cases:
        path = package(os.path.join(WORK, "case-%s.werk" % key), blob)
        for reader in readers:
            rc, out = G.verify(reader, path)
            lines = envelope_lines(out)
            invalid = [l for l in lines if "envelope-invalid" in l and NODE in l]
            name = "%s %s: %s" % (reader[0], key, label)
            if key == "a":
                ok = rc == 0 and not [l for l in lines if "envelope-invalid" in l]
                detail = "exit 0, no invalid envelope"
                if reader[0] == "core":
                    m = re.search(r"^envelopes\s*:\s*(\d+)", out, re.M)
                    n = int(m.group(1)) if m else None
                    undeclared = any("envelope-undeclared" in l and NODE in l for l in lines)
                    ok = ok and base_n is not None and n == base_n + 1 and undeclared
                    detail = ("exit 0, %s envelopes validated where the unmodified crate "
                              "has %s, and envelope-undeclared for `%s`" % (n, base_n, KIND))
            elif key in ("b", "c"):
                ok = bool(invalid)
                detail = "envelope-invalid against node `%s`" % NODE
            else:
                ok = rc == 0 and not lines
                detail = "exit 0 and not a word about envelopes"
            gate.check(name, ok, detail,
                       "exit %d; envelope lines: %s" % (rc, lines[:2] or "none"))
    return gate.finish()


if __name__ == "__main__":
    sys.exit(main())
