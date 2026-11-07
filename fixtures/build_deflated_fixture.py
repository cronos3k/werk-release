#!/usr/bin/env python3
"""build_deflated_fixture.py -- the one conformance fixture whose zip entries are
DEFLATED (zip method 8), so that reading method 8 is exercised by a real file.

    python fixtures/build_deflated_fixture.py [--out DIR] [--check]

    fixtures/crate-cc0-lean-v1-deflated.werk

WHY IT EXISTS. SPEC.md section 1 has always said that method 8 "remains legal
and a reader SHOULD support it". Until ruling 9 of 2026-10-13 no reader in
this repository did, no fixture was deflated, and the paper said so in as many
words ("no deflate and no zip64 support exists anywhere in this project").
The four reference readers now inflate (spec/MINI-SPECS.md section 7.1), and a
capability nothing exercises is a capability nobody has tested.

WHAT IT IS. The CC0 lean crate -- the same public-domain content, the same
nodes, the same payload bytes, byte for byte, as `crate-cc0-lean-v1.werk` --
with every zip entry compressed, `container.zip_compression` saying "deflate",
and a signature over the manifest that says so. A reader that inflates it
correctly reports exactly what it reports for the store-mode twin, down to the
per-file hashes; that comparison is the test (`tests/run_gate_container.py`).

THE ENCODER IS NOT OURS, AND THAT IS THE POINT. Every entry is compressed by
zlib, through the standard library, at level 9 -- real dynamic-Huffman blocks
with real matches, from an implementation that shares no code with any of the
four inflaters under test. The zip framing around it is written by hand
(method 8, UTF-8 names, no data descriptor, a fixed timestamp), because the
standard library's zip writer does not let a caller fix the timestamp and the
entry order together.

DETERMINISM, STATED HONESTLY. The CONTENT is a pure function of the repository.
The BYTES of a deflate stream are a function of the zlib version that made
them, so this file is byte-reproducible only on a host with the same zlib; the
shipped build was made with the version recorded in fixtures/fixtures.json,
and `--check` therefore compares what matters -- that every entry of a fresh
build inflates to the same bytes as the shipped one's -- and reports whether
the containers are also byte-identical rather than requiring it. `preview_
prefix_bytes` is omitted for the same reason: it is a hint about the container
(S-15), and this container's layout is its encoder's.
"""

import argparse
import hashlib
import json
import os
import shutil
import struct
import sys
import zipfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import build_crate_cc0 as C                                   # noqa: E402
from payload_file import annotate_payload_files               # noqa: E402

NAME = "crate-cc0-lean-v1-deflated.werk"

EXTRA = (" DEFLATED VARIANT: the same content as crate-cc0-lean-v1.werk, byte "
         "for byte, in a container whose every entry is zip method 8. It exists "
         "so that a reader's inflate is tested against streams it did not write.")


def write_deflated_zip(entries):
    """A zip whose every entry is method 8. MINI-SPECS section 5 for the
    framing, zlib (raw, window 15, level 9) for the streams."""
    dos_time, dos_date = (9 << 11), ((2026 - 1980) << 9) | (8 << 5) | 8
    body, central = bytearray(), bytearray()
    for name, data in entries:
        co = zlib.compressobj(9, zlib.DEFLATED, -15)
        comp = co.compress(data) + co.flush()
        nb = name.encode("utf-8")
        crc = zlib.crc32(data) & 0xFFFFFFFF
        offset = len(body)
        body += struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, 0x0800, 8, dos_time,
                            dos_date, crc, len(comp), len(data), len(nb), 0)
        body += nb + comp
        central += struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, 20, 20, 0x0800, 8,
                               dos_time, dos_date, crc, len(comp), len(data),
                               len(nb), 0, 0, 0, 0, 0, offset)
        central += nb
    end = struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, len(entries), len(entries),
                      len(central), len(body), 0)
    return bytes(body) + bytes(central) + end


def build(src_dir, out_dir):
    tmp_dir = os.path.join(out_dir, ".werk-deflated-tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    try:
        files, nodes, _stats = C.collect("lean", src_dir, tmp_dir)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    annotate_payload_files(nodes)
    manifest = C.build_manifest("lean", files, nodes, 0, EXTRA)
    manifest["container"]["zip_compression"] = "deflate"
    del manifest["container"]["preview_prefix_bytes"]
    manifest_bytes = C.jbytes(manifest)
    sig_bytes = C.jbytes(C.sign(
        manifest_bytes,
        "Signed with a DEV key derived from a published sentence. Not secret, "
        "not a trust anchor; it proves only that the chain verifies."))
    allf = dict(files)
    allf["MANIFEST.json"] = manifest_bytes
    allf["SIGNATURE.json"] = sig_bytes
    entries = [(p, allf[p]) for p in C.order_entries(allf.keys(), C.ENTRY_ORDER["lean"])]
    return write_deflated_zip(entries), entries, nodes


def contents(blob_or_path):
    """name -> inflated bytes, read with the standard library's own zip reader."""
    import io
    z = zipfile.ZipFile(io.BytesIO(blob_or_path) if isinstance(blob_or_path, bytes)
                        else blob_or_path)
    assert all(i.compress_type == zipfile.ZIP_DEFLATED for i in z.infolist()), \
        "every entry of this fixture is method 8"
    return {i.filename: z.read(i.filename) for i in z.infolist()}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--src", default=C.SRC_DEFAULT)
    ap.add_argument("--out", default=HERE)
    ap.add_argument("--check", action="store_true",
                    help="build in memory and compare with the shipped file instead "
                         "of writing")
    args = ap.parse_args(argv)

    blob, entries, nodes = build(args.src, args.out)
    path = os.path.join(args.out, NAME)
    stored = sum(len(d) for _n, d in entries)
    if args.check:
        if not os.path.isfile(path):
            print("no shipped %s to compare with" % NAME)
            return 1
        with open(path, "rb") as fh:
            shipped = fh.read()
        same_content = contents(shipped) == contents(blob)
        same_bytes = shipped == blob
        print("content identical to the shipped build: %s (%d entries)"
              % (same_content, len(entries)))
        print("container bytes identical: %s  (zlib here %s; they need not be, on "
              "another zlib)" % (same_bytes, zlib.ZLIB_RUNTIME_VERSION))
        return 0 if same_content else 1

    with open(path, "wb") as fh:
        fh.write(blob)
    print("wrote %s" % path)
    print("  %d bytes, sha256 %s" % (len(blob), hashlib.sha256(blob).hexdigest()))
    print("  %d entries, all method 8; %d payload bytes stored in %d (%.1f%%)"
          % (len(entries), stored, len(blob), 100.0 * len(blob) / stored))
    print("  %d nodes; zlib %s" % (len(nodes), zlib.ZLIB_RUNTIME_VERSION))
    twin = os.path.join(args.out, "crate-cc0-lean-v1.werk")
    if os.path.isfile(twin):
        a, b = contents(blob), {i.filename: zipfile.ZipFile(twin).read(i.filename)
                                for i in zipfile.ZipFile(twin).infolist()}
        differ = sorted(n for n in a if a[n] != b.get(n))
        print("  against the store-mode twin: %d of %d entries differ (%s) -- the "
              "manifest, which declares the compression, and the signature over it"
              % (len(differ), len(a), ", ".join(differ)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
