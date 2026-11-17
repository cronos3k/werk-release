#!/usr/bin/env python3
"""write_minimal_image.py -- write a minimal valid werk package of profile
`image/1` from scratch, with the Python standard library and nothing else.

    python write_minimal_image.py <a werk package> <out.werk>
    python write_minimal_image.py <a werk package> <out-directory> --dir

This is the executable half of spec/WRITING-IMAGE.md, which is NORMATIVE and
which you should read beside it: every step below is a numbered step there,
and every number that document quotes is printed by this script.

"From the file alone" is meant literally. The first argument is any werk
package you are holding -- very likely the one this script came out of, zipped
or unzipped. The script takes from it the two things a writer does not author:
the specification (`spec/`) and the bootstrap readers (`loaders/`). Everything
else it makes itself:

    image/source.png      an 8 x 8 RGBA test pattern: the source image
    image/thumb.png       a 4 x 4 box-filter downscale of it, MEASURED from the
                          source, so the package has one derived node and one
                          `input_hash` to check
    LICENSE, README.txt
    MANIFEST.json

It shares no code with any werk tool. It imports nothing but hashlib, json,
os, struct, sys, zipfile and zlib (and of zlib only crc32 and adler32: the PNG
is written with STORED deflate blocks, so no compressor is involved and the
bytes are the same on every machine).
"""

import hashlib
import json
import os
import struct
import sys
import zipfile
import zlib

TOOL = "spec/examples/write_minimal_image.py"
TOOL_VERSION = "1"

# A fixed instant and a fixed identity, so two runs against the same donor
# package give the same bytes. YOUR package gets the time you wrote it and a
# NEW random uuid (uuid.uuid4()).
CREATED = "2026-10-13T00:00:00Z"
ENTITY_UUID = "1a6e0000-0000-4000-8000-000000000001"

# Law 8: the nine conventions of `image/1` (spec/PROFILE-IMAGE.md section 6).
CONVENTIONS = {
    "endianness": "le", "color_space_default": "srgb",
    "pixel_origin": "top-left", "alpha_mode": "straight",
    "alignment_bytes": 16, "text_encoding": "utf-8", "id_case": "kebab-case",
    "hash_algorithm": "sha256", "signature_algorithm": "ed25519",
}

ENTRY_ORDER = ["MANIFEST.json", "SIGNATURE.json", "LICENSE", "README.txt",
               "loaders/", "spec/", "image/thumb.png", "image/"]
PREVIEW_TIER = ["MANIFEST.json", "SIGNATURE.json", "LICENSE", "README.txt",
                "loaders/", "spec/", "image/thumb.png"]

LICENSE_TEXT = """\
LICENCE TERMS NOT ESTABLISHED

This package is a worked example written by spec/examples/write_minimal_image.py.
Its content is an 8 x 8 test pattern. Whoever ran the script decides the terms
under which that content is offered; none are stated here, and this file says
so instead of inventing some. The werk format records licence facts and
enforces none (spec/SPEC.md section 2, `license`).

The specification under spec/ and the readers under loaders/ are not the
content of this package. They are the format, copied unchanged from the
package this one was written from, and they keep whatever terms they had
there.
"""

README_TEXT = """\
This is a werk package. Everything needed to read it is inside it.

Start with spec/README.md. loaders/ holds single-file, dependency-free readers
in Python, Rust and C; any one of them lists the nodes and verifies every hash:

    python loaders/werk_read.py <this file> --verify

This particular package is the worked example of spec/WRITING-IMAGE.md: an
8 x 8 test pattern (image/source.png) and a 4 x 4 thumbnail measured from it
(image/thumb.png), written from scratch by spec/examples/write_minimal_image.py.
"""


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def pretty(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def canonical(value):
    """Canonical JSON for hashing a VALUE (spec/MINI-SPECS.md section 3)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


# ---------------------------------------------------------------------------
# step 1 -- the specification and the readers, copied from a package you hold
# ---------------------------------------------------------------------------

def read_donor(path):
    if os.path.isdir(path):
        def read(rel):
            with open(os.path.join(path, *rel.split("/")), "rb") as fh:
                return fh.read()
    else:
        z = zipfile.ZipFile(path)   # MINI-SPECS section 5: any zip library works

        def read(rel):
            return z.read(rel)
    return read, json.loads(read("MANIFEST.json").decode("utf-8"))


def carried_nodes(read, donor):
    """The donor's `core.spec` and `core.loader` nodes at their ACTIVE version."""
    files, nodes = {}, []
    for n in donor["nodes"]:
        if n["type"] not in ("core.spec", "core.loader"):
            continue
        active = next(v for v in n["versions"] if v["v"] == n["active"])
        listed = []
        for f in active["files"]:
            data = read(f["path"])
            if sha256(data) != f["sha256"]:
                raise SystemExit("the donor's %s does not match its declared hash; "
                                 "refusing to copy a damaged specification" % f["path"])
            files[f["path"]] = data
            entry = {"path": f["path"], "sha256": f["sha256"], "size": len(data)}
            if "media_type" in f:
                entry["media_type"] = f["media_type"]
            listed.append(entry)
        note = ("The specification this package conforms to, travelling inside it "
                "(law 2); copied unchanged from the package it was written from."
                if n["type"] == "core.spec" else
                "A single-file, dependency-free reader, so the package carries a way "
                "to read itself (law 1); copied unchanged.")
        node = {"node_id": n["node_id"], "type": n["type"],
                "versions": [version(listed, note, "authored")],
                "active": 1, "edges": []}
        if "meta" in n:
            node["meta"] = n["meta"]
        nodes.append(node)
    if not any(n["type"] == "core.spec" for n in nodes):
        raise SystemExit("the donor package carries no core.spec node; a package "
                         "cannot be written from it")
    return files, nodes


# ---------------------------------------------------------------------------
# step 3 -- the payloads
# ---------------------------------------------------------------------------

def source_pixels():
    """8 x 8, RGBA, 8 bits per channel, sRGB, straight alpha, top row first.
    Red rises left to right, green rises top to bottom, blue is a 2 x 2
    checkerboard of 64 and 192, and the bottom-right quadrant is half
    transparent -- so every channel, the origin and the alpha mode are each
    visible in the picture."""
    rows = []
    for y in range(8):
        row = []
        for x in range(8):
            r = x * 36                          # 0, 36, ... 252
            g = y * 36
            b = 192 if ((x // 2) + (y // 2)) % 2 == 0 else 64
            a = 128 if (x >= 4 and y >= 4) else 255
            row.append((r, g, b, a))
        rows.append(row)
    return rows


def box_half(rows):
    """Each output pixel is the mean of a 2 x 2 block of the input, per channel,
    on the STORED values (no linearisation), rounded half up: (sum + 2) // 4.
    That sentence is the whole filter, which is what `resample: "box"` plus
    these parameters has to mean for a derivative to be reproducible."""
    out = []
    for y in range(0, len(rows), 2):
        row = []
        for x in range(0, len(rows[0]), 2):
            block = [rows[y][x], rows[y][x + 1], rows[y + 1][x], rows[y + 1][x + 1]]
            row.append(tuple((sum(p[c] for p in block) + 2) // 4 for c in range(4)))
        out.append(row)
    return out


def png(rows):
    """A PNG per spec/MINI-SPECS.md section 8: colour type 6 (RGBA), bit depth
    8, filter 0 on every scanline, and an IDAT whose zlib stream uses STORED
    deflate blocks (section 7.1) -- legal, needs no compressor, and is the same
    bytes everywhere."""
    height, width = len(rows), len(rows[0])
    raw = b"".join(b"\x00" + bytes(c for px in row for c in px) for row in rows)

    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))

    stored = b""
    for i in range(0, len(raw), 0xFFFF):
        part = raw[i:i + 0xFFFF]
        last = 1 if i + 0xFFFF >= len(raw) else 0
        stored += struct.pack("<BHH", last, len(part), len(part) ^ 0xFFFF) + part
    idat = b"\x78\x01" + stored + struct.pack(">I", zlib.adler32(raw) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", idat)
            + chunk(b"IEND", b""))


# ---------------------------------------------------------------------------
# step 4 -- node and version records
# ---------------------------------------------------------------------------

def file_record(path, data, media_type=None):
    rec = {"path": path, "sha256": sha256(data), "size": len(data)}
    if media_type:
        rec["media_type"] = media_type
    return rec


def version(files, note, epistemic, input_files=None, input_params=None,
            input_hash=None):
    v = {"v": 1, "files": files, "note": note,
         "producer": {"tool": TOOL, "version": TOOL_VERSION},
         "epistemic": epistemic, "created": CREATED}
    if input_files is not None:
        v["input_files"] = input_files
        v["input_params"] = input_params
        v["input_hash"] = input_hash
    return v


def input_hash_of(files, paths, params):
    """spec/MINI-SPECS.md section 11: each input's sha256 as 32 RAW bytes, in
    the order input_files lists them, then the canonical JSON of input_params."""
    h = hashlib.sha256()
    for p in paths:
        h.update(hashlib.sha256(files[p]).digest())
    h.update(canonical(params))
    return h.hexdigest()


def spec_sha256_of(nodes):
    """spec/SPEC.md section 2."""
    declared = {}
    for n in nodes:
        for v in n["versions"]:
            for f in v["files"]:
                if f["path"].startswith("spec/"):
                    declared[f["path"]] = f["sha256"]
    acc = b""
    for path in sorted(declared, key=lambda p: p.encode("utf-8")):
        acc += path.encode("utf-8") + b"\n" + bytes.fromhex(declared[path]) + b"\n"
    return hashlib.sha256(acc).hexdigest()


# ---------------------------------------------------------------------------
# step 6 -- the container
# ---------------------------------------------------------------------------

def physical_order(paths):
    """`container.entry_order`, applied (spec/SPEC.md section 1): every exact
    path first, in list order, then the directory prefixes in list order -- so
    image/thumb.png, listed BEFORE the prefix image/, travels early and the
    source image does not."""
    left = sorted(paths)
    placed = {}
    for i, pat in enumerate(ENTRY_ORDER):
        if not pat.endswith("/") and pat in left:
            placed[pat] = i
    for i, pat in enumerate(ENTRY_ORDER):
        if pat.endswith("/"):
            for p in left:
                if p not in placed and p.startswith(pat):
                    placed[p] = i
    listed = sorted((p for p in left if p in placed), key=lambda p: (placed[p], p))
    return listed + [p for p in left if p not in placed]


def write_zip(dest, entries):
    """A store-mode zip written by hand from spec/MINI-SPECS.md section 5."""
    dos_time, dos_date = (9 << 11), ((2026 - 1980) << 9) | (8 << 5) | 8
    body, central = bytearray(), bytearray()
    for name, data in entries:
        nb = name.encode("utf-8")
        crc = zlib.crc32(data) & 0xFFFFFFFF
        offset = len(body)
        body += struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, 0x0800, 0, dos_time,
                            dos_date, crc, len(data), len(data), len(nb), 0)
        body += nb + data
        central += struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, 20, 20, 0x0800, 0,
                               dos_time, dos_date, crc, len(data), len(data),
                               len(nb), 0, 0, 0, 0, 0, offset)
        central += nb
    end = struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, len(entries), len(entries),
                      len(central), len(body), 0)
    with open(dest, "wb") as fh:
        fh.write(bytes(body) + bytes(central) + end)


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 2:
        print(__doc__)
        return 2
    donor_path, dest = args
    as_dir = "--dir" in argv

    # 1. the specification and the readers
    read, donor = read_donor(donor_path)
    files, nodes = carried_nodes(read, donor)
    schema = "spec/schemas/manifest.image.schema.json"
    if schema not in files:
        raise SystemExit("the donor package does not carry %s, the schema an image/1 "
                         "manifest names; use a package that carries the whole "
                         "reference spec tree" % schema)

    # 2. licence and readme
    files["LICENSE"] = LICENSE_TEXT.encode("utf-8")
    files["README.txt"] = README_TEXT.encode("utf-8")
    nodes.append({"node_id": "license", "type": "core.license",
                  "versions": [version([file_record("LICENSE", files["LICENSE"], "text/plain")],
                                       "The licence statement, embedded in full, never a link "
                                       "(law 7).", "authored")],
                  "active": 1, "edges": []})
    nodes.append({"node_id": "readme", "type": "core.readme",
                  "versions": [version([file_record("README.txt", files["README.txt"],
                                                    "text/plain")],
                                       "One page for a human who opened the archive by hand.",
                                       "authored")],
                  "active": 1, "edges": []})

    # 3. the payloads
    src = source_pixels()
    files["image/source.png"] = png(src)
    files["image/thumb.png"] = png(box_half(src))

    # 4. their nodes
    nodes.append({"node_id": "image-source", "type": "core.image.source",
                  "versions": [version([file_record("image/source.png",
                                                    files["image/source.png"], "image/png")],
                                       # `authored`: a person (through this script) decided
                                       # every pixel. A MODEL's output would be `inferred`,
                                       # with input_files -- see PROFILE-IMAGE.md section 3.
                                       "The source image: an 8 x 8 test pattern written by "
                                       "hand to show the smallest valid image payload.",
                                       "authored")],
                  "active": 1, "edges": [],
                  "meta": {"width": 8, "height": 8, "channels": 4, "bit_depth": 8,
                           "color_space": "srgb", "encoding": "png", "has_alpha": True}})
    thumb_inputs = ["image/source.png"]
    thumb_params = {"resample": "box", "width": 4, "height": 4,
                    "on": "stored-values", "rounding": "half-up"}
    thumb_hash = input_hash_of(files, thumb_inputs, thumb_params)
    nodes.append({"node_id": "image-thumb", "type": "core.image.derived",
                  "versions": [version([file_record("image/thumb.png",
                                                    files["image/thumb.png"], "image/png")],
                                       "The listing thumbnail: a 2 x 2 box-filter downscale "
                                       "of the source, reproducible from it.", "measured",
                                       input_files=thumb_inputs, input_params=thumb_params,
                                       input_hash=thumb_hash)],
                  "active": 1,
                  # `requires`: a thumbnail of a source that is gone is a picture of nothing.
                  "edges": [{"to": "image-source", "kind": "requires", "role": "derived-from"}],
                  "meta": {"width": 4, "height": 4, "channels": 4, "bit_depth": 8,
                           "color_space": "srgb", "encoding": "png", "has_alpha": True,
                           "derived_role": "thumbnail", "resample": "box"}})

    # 5. the manifest
    manifest = {
        "werk": {"major": 1, "minor": 0},
        "profile": "image/1",
        "manifest_schema": schema,
        "spec_sha256": spec_sha256_of(nodes),
        "entity": {"uuid": ENTITY_UUID, "name": "Minimal test pattern",
                   "summary": "The worked example of spec/WRITING-IMAGE.md: an 8 x 8 "
                              "test pattern and a thumbnail measured from it.",
                   "created": CREATED},
        "conventions": CONVENTIONS,
        "container": {"form": "directory" if as_dir else "zip",
                      "zip_compression": "store", "entry_order": ENTRY_ORDER,
                      "preview_tier": PREVIEW_TIER},
        "primary": {"image": "image-source", "thumbnail": "image-thumb"},
        "license": {"file": "LICENSE", "sha256": sha256(files["LICENSE"])},
        "schemas": {},
        "layouts": {},
        "nodes": nodes,
        "generator": {"tool": TOOL, "version": TOOL_VERSION},
    }
    if "spec/conventions-map.image.json" in files:
        manifest["conventions_map"] = "spec/conventions-map.image.json"
    files["MANIFEST.json"] = pretty(manifest)

    # 6. the container
    order = physical_order(files)
    order.remove("MANIFEST.json")
    order.insert(0, "MANIFEST.json")
    if as_dir:
        for p in order:
            full = os.path.join(dest, *p.split("/"))
            os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
            with open(full, "wb") as fh:
                fh.write(files[p])
    else:
        write_zip(dest, [(p, files[p]) for p in order])

    # the checkpoints spec/WRITING-IMAGE.md quotes
    a, b = files["image/source.png"], files["image/thumb.png"]
    print("image/source.png        %d bytes  sha256 %s" % (len(a), sha256(a)))
    print("image/thumb.png         %d bytes  sha256 %s" % (len(b), sha256(b)))
    print("thumbnail input_hash    %s" % thumb_hash)
    print("canonical input_params  %s" % canonical(thumb_params).decode("utf-8"))
    print("spec_sha256             %s   (depends on the package you copied spec/ from)"
          % manifest["spec_sha256"])
    print("nodes                   %d   files %d (+ MANIFEST.json)"
          % (len(nodes), len(files) - 1))
    print("wrote %s" % dest)
    print("check it:  python loaders/werk_read.py %s --verify --strict" % dest)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
