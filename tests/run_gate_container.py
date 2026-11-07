#!/usr/bin/env python3
"""run_gate_container.py -- GATE CONTAINER: what the four reference readers do
with zip containers this repository's writers never produce.

    python tests/run_gate_container.py [--big]

Ruling 9 of 2026-10-13 (docs/RULINGS-2026-10-13.md; SPEC.md section 1):

  * DEFLATE (zip method 8) is READ by every reference reader. SPEC section 1
    always said a reader SHOULD; until this ruling none did, the core reported
    a deflated entry as `file-missing`, and a fully deflated package as "no
    MANIFEST.json".
  * ZIP64 is REFUSED, by name, by every reference reader: `zip64-unsupported`,
    container scope, exit status 2. A package that outgrows 4 GiB or 65,535
    entries uses the directory form. At baseline all four exited 1 with four
    different messages, one of them a Python traceback.
  * Any other method (and an encrypted entry) kills the node that owns the
    entry and nothing else: `zip-entry-unsupported`.

EVERY CONTAINER HERE IS REAL. The deflated fixture's streams were written by
zlib, which shares no code with any of the four inflaters. The zip64 files are
written by the Python standard library's zip writer at the moment the gate
runs, because that is what a zip64 file in the wild is: 70,001 entries (over
the 65,535 limit, so the end record is the zip64 one). The same writer also
makes the file that LOOKS like zip64 and is not -- a zip64 extra field in the
local headers only, ordinary values in the central directory (MINI-SPECS
section 5.5) -- which every reader must READ; the first draft of this gate
expected a refusal there and the four readers were right and the gate wrong.
`--big` adds a container of more than 4 GiB;
it needs 4.4 GB of scratch disk and about a minute, so it is opt-in, and its
last run is recorded in results/STAGE-ARTCRAFT-RESULTS.md.

Nothing is written outside core/target/gate-container/.
"""

import argparse
import os
import re
import shutil
import struct
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate_common as G                                        # noqa: E402
from fixture_pin import pin                                    # noqa: E402

WORK = os.path.join(G.ROOT, "core", "target", "gate-container")
TWIN = os.path.join(G.FIX, "crate-cc0-lean-v1.werk")
DEFLATED = os.path.join(G.FIX, "crate-cc0-lean-v1-deflated.werk")
VICTIM = "README.txt"          # the one file of node `readme`
VICTIM_NODE = "readme"


def counts(out):
    """Every integer in a reader's closing summary: the same list for two
    packages with the same content, whatever the reader's wording is."""
    lines = [l for l in out.strip().splitlines()
             if re.search(r"\d", l) and not l.startswith(("PASS", "[", "--"))]
    tail = [l for l in lines if re.match(r"(census|summary|verify|\d+/\d+)", l.strip())]
    return [re.findall(r"\d+", l) for l in tail]


def rewrite(src, dst, method_for):
    """Copy a zip, entry by entry, choosing each entry's method."""
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w") as zout:
        for info in zin.infolist():
            zi = zipfile.ZipInfo(info.filename, date_time=(2026, 8, 8, 9, 0, 0))
            zi.compress_type = method_for(info.filename)
            zout.writestr(zi, zin.read(info.filename))


def break_stream(src, dst, name):
    """Make one entry's deflate stream undecodable: its first block header
    becomes BTYPE 11, which RFC 1951 reserves. Sizes and CRC stay as declared,
    so only a reader that actually inflates can notice."""
    blob = bytearray(open(src, "rb").read())
    with zipfile.ZipFile(src) as z:
        off = z.getinfo(name).header_offset
    nlen, xlen = struct.unpack_from("<HH", blob, off + 26)
    blob[off + 30 + nlen + xlen] = 0x07
    with open(dst, "wb") as fh:
        fh.write(blob)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--big", action="store_true",
                    help="also write and refuse a zip64 container over 4 GiB")
    args = ap.parse_args(argv)

    gate = G.Gate("CONTAINER")
    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK)
    for key in ("crate-cc0-lean-v1", "crate-cc0-lean-v1-deflated"):
        r = pin(key)
        gate.record("fixture pinned: %s" % key, "PASS" if r.ok else "FAIL", r.detail)
    readers = G.readers(gate)

    # ---- 1. deflate, read -------------------------------------------------
    with zipfile.ZipFile(DEFLATED) as z:
        methods = {i.compress_type for i in z.infolist()}
        n = len(z.infolist())
        with zipfile.ZipFile(TWIN) as t:
            differ = sorted(i.filename for i in z.infolist()
                            if z.read(i.filename) != t.read(i.filename))
    gate.check("deflated fixture is all method 8", methods == {8},
               "%d entries, every one zip method 8" % n, "methods %s" % sorted(methods))
    gate.check("deflated fixture has its twin's content",
               differ == ["MANIFEST.json", "SIGNATURE.json"],
               "%d of %d entries inflate to the store-mode twin's bytes; the two that "
               "differ are the manifest, which declares the compression, and the "
               "signature over it" % (n - len(differ), n), "differ: %s" % differ)
    for reader in readers:
        rc_t, out_t = G.verify(reader, TWIN)
        rc_d, out_d = G.verify(reader, DEFLATED)
        ok = rc_t == 0 and rc_d == 0 and counts(out_t) == counts(out_d) \
            and not [c for s, c in G.codes(out_d) if s == "error"]
        gate.check("%s: reads the deflated fixture" % reader[0], ok,
                   "exit 0, and the same counts as the store-mode twin: %s"
                   % (" / ".join(" ".join(c) for c in counts(out_d)) or "-"),
                   "twin exit %d %s, deflated exit %d %s; %s"
                   % (rc_t, counts(out_t), rc_d, counts(out_d),
                      out_d.strip().splitlines()[-1][:120] if out_d.strip() else ""))

    # ---- 2. a deflate stream that does not decode --------------------------
    bad = os.path.join(WORK, "deflated-one-bad-stream.werk")
    break_stream(DEFLATED, bad, VICTIM)
    for reader in readers:
        rc, out = G.verify(reader, bad)
        named = "zip-entry-invalid" in out
        scoped = (G.dead_nodes(out) == [VICTIM_NODE] if reader[0] == "core"
                  else bool(re.search(r"^(FAIL|\[error\]).*\b%s\b" % VICTIM, out, re.M)))
        gate.check("%s: an undecodable stream kills one node" % reader[0],
                   rc == 1 and named and scoped,
                   "exit 1, zip-entry-invalid, node `%s` dead and the rest alive" % VICTIM_NODE,
                   "exit %d, named %s, scoped %s: %s"
                   % (rc, named, scoped, out.strip().splitlines()[-1][:140]))

    # ---- 3. a method nobody reads (12, bzip2), on one entry ----------------
    bz = os.path.join(WORK, "one-entry-bzip2.werk")
    rewrite(TWIN, bz, lambda n: zipfile.ZIP_BZIP2 if n == VICTIM else zipfile.ZIP_STORED)
    for reader in readers:
        rc, out = G.verify(reader, bz)
        named = "zip-entry-unsupported" in out
        scoped = (G.dead_nodes(out) == [VICTIM_NODE] if reader[0] == "core"
                  else bool(re.search(r"^(FAIL|\[error\]).*\b%s\b" % VICTIM, out, re.M)))
        gate.check("%s: zip method 12 kills one node" % reader[0],
                   rc == 1 and named and scoped,
                   "exit 1, zip-entry-unsupported, node `%s` dead and the rest alive"
                   % VICTIM_NODE,
                   "exit %d, named %s, scoped %s: %s"
                   % (rc, named, scoped, out.strip().splitlines()[-1][:140]))

    # ---- 4. NOT zip64: a zip64 extra field in LOCAL headers only ----------
    # (MINI-SPECS section 5.5, last paragraph.) The Python zip writer, asked
    # to allow for a large entry it then finds small, writes sentinel sizes
    # and a 0x0001 record into the local header and ordinary values into the
    # central directory. Every number a reader follows is real; it is read.
    local = os.path.join(WORK, "local-header-zip64-extra-only.werk")
    with zipfile.ZipFile(TWIN) as zin:
        with zipfile.ZipFile(local, "w", zipfile.ZIP_STORED, allowZip64=True) as zout:
            for info in zin.infolist():
                zi = zipfile.ZipInfo(info.filename, (2026, 8, 8, 9, 0, 0))
                with zout.open(zi, "w", force_zip64=True) as fh:
                    fh.write(zin.read(info.filename))
    blob = open(local, "rb").read()
    gate.check("local-header zip64 extra: the file is what it claims",
               blob.count(b"PK\x03\x04\x2d\x00") >= 78 and b"PK\x06\x06" not in blob[-200:],
               "every local header says version 45 with sentinel sizes; the end record "
               "is the ordinary 32-bit one")
    for reader in readers:
        rc_t, out_t = G.verify(reader, TWIN)
        rc, out = G.verify(reader, local)
        gate.check("%s: reads it (it is not zip64)" % reader[0],
                   rc == 0 and counts(out) == counts(out_t),
                   "exit 0, and the same counts as the original",
                   "exit %d: %s" % (rc, out.strip().splitlines()[-1][:160]))

    # ---- 4. zip64, refused by name ----------------------------------------
    cases = []
    many = os.path.join(WORK, "real-zip64-70001-entries.zip")
    with zipfile.ZipFile(many, "w", zipfile.ZIP_STORED, allowZip64=True) as z:
        z.writestr("MANIFEST.json", "{}")
        for i in range(70000):
            z.writestr("f/%05d" % i, "")
    cases.append(("70,001 entries", many))
    if args.big:
        big = os.path.join(WORK, "real-zip64-over-4gib.zip")
        with zipfile.ZipFile(big, "w", zipfile.ZIP_STORED, allowZip64=True) as z:
            z.writestr("MANIFEST.json", "{}")
            with z.open("payload.bin", "w", force_zip64=True) as fh:
                block = b"\0" * (1 << 24)
                for _ in range(260):
                    fh.write(block)
        cases.append(("%d bytes" % os.path.getsize(big), big))
    for label, path in cases:
        with open(path, "rb") as fh:
            blob_has = b"PK\x06\x06" in fh.read()[-200:] if os.path.getsize(path) < (1 << 30) \
                else True
        for reader in readers:
            rc, out = G.verify(reader, path)
            ok = rc == 2 and "zip64-unsupported" in out and "Traceback" not in out
            gate.check("%s: refuses zip64 (%s)" % (reader[0], label), ok,
                       "exit 2, zip64-unsupported%s"
                       % ("" if blob_has else " (no zip64 end record: per-entry field)"),
                       "exit %d: %s" % (rc, out.strip().splitlines()[-1][:160]
                                        if out.strip() else "no output"))
    if args.big:
        os.remove(cases[-1][1])

    return gate.finish()


if __name__ == "__main__":
    sys.exit(main())
