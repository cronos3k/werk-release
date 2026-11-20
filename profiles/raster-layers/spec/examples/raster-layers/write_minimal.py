#!/usr/bin/env python3
"""write_minimal.py - write a minimal valid `raster-layers/1` werk capsule.

Python standard library only. It uses NO PhotoCraft and NO ArtCraft software: it is the
executable form of spec/PROFILE-RASTER-LAYERS.md section 7 ("Writing a minimal valid
raster-layers/1 capsule"), of spec/layouts/core.raster.surface.layout.txt section 7 and of
spec/CRAFT-BASE.md section 8. It copies loaders/ and spec/ out of an existing capsule of the
same profile (their content is the format) and writes everything else itself.

    python write_minimal.py <existing capsule: .werk file or directory> <new.werk>

The document it writes: a 256 x 256 px RGB canvas, 8 bits per channel, with one pixel layer
named "Layer 1" whose pixel (x, y) is red = x, green = y, blue = (x + y) mod 256, alpha = 255.

The four payload files it writes are fixed, so their sizes and hashes are a checkpoint for
another implementation (they are quoted in section 7 of the profile document):

    document/document.json
    layers/layer-1/layer.json
    surfaces/layer-1-pixels/surface.wkx
    surfaces/layer-1-pixels/tiles-p0-p0.wkx
"""

import hashlib
import json
import os
import struct
import sys
import zipfile

LF = bytes([10])
CREATED = "2026-10-12T00:00:00Z"
PRODUCER = {"tool": "write_minimal.py", "version": "1"}
LICENSE_TEXT = (
    "Licence notice" + chr(10) + chr(10)
    + "THE TERMS OF THIS DOCUMENT'S CONTENT ARE NOT ESTABLISHED." + chr(10) + chr(10)
    + "This file was written by write_minimal.py as a worked example. No licence is granted "
    + "by this notice; anyone redistributing the file must establish its terms." + chr(10)
).encode("utf-8")

# ----------------------------------------------------------------------------- the payloads

DOCUMENT = {
    "schema_version": 1,
    "name": "Minimal",
    "width": 256,
    "height": 256,
    "resolution_dpi": 72.0,
    "color_mode": "Rgb",
    "sample_type": "U8",
    "color_space": None,
    "icc_profile": None,
    "layers": [{"layer": "layer-1"}],
    "channels": [],
    "quick_mask": None,
    "quick_mask_unselected": False,
    "selection": None,
    "patterns": [],
    "paths": [],
    "work_path": None,
    "clipping_path": None,
    "layer_comps": [],
    "last_applied_comp": None,
    "last_document_state": None,
    "text_styles": None,
    "variables": None,
    "metadata": None,
    "guides": {"horizontal": [], "vertical": []},
    "global_light": {"angle": 120.0, "altitude": 30.0},
    "color_table": None,
    "duotone": None,
    "measurement": {
        "scale": {"pixel_length": 1.0, "logical_length": 1.0, "units": "pixels"},
        "count_groups": [],
        "active_count_group": 0,
        "ruler": None,
    },
    "notes": [],
    "slices": {"groupName": "", "list": []},
    "timeline": None,
    "file_encoding": {},
    "psd": None,
    "fonts": [],
    "app": {"document_id": 0},
}

LAYER = {
    "schema_version": 1,
    "name": "Layer 1",
    "visible": True,
    "locks": {"transparency": False, "pixels": False, "position": False, "artboard": False, "all": False},
    "blend": "Normal",
    "opacity": 1.0,
    "fill_opacity": 1.0,
    "clipped": False,
    "mask": None,
    "vector_mask": None,
    "effects": {"enabled": True, "items": [], "reference": None},
    "label": "None",
    "content": {"kind": "raster", "pixels": "layer-1-pixels"},
    "psd_id": None,
    "psd": None,
    "fill_cache": None,
    "link_group": None,
    "excluded_channels": 0,
    "blend_if": {"ranges": []},
    "advanced": {
        "knockout": "none",
        "blendInterior": False,
        "blendClipped": True,
        "transparencyShapes": True,
        "layerMaskHidesEffects": False,
        "vectorMaskHidesEffects": False,
    },
    "video": None,
}


def compact_json(value):
    """One line of JSON, keys in the order written above, then one line feed."""
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + LF


# ----------------------------------------------------------------------------- MessagePack
# The canonical encoding of spec/layouts/ENVELOPE.layout.txt section 4.3: shortest integer
# form, float64 for non-integers, shortest string form, map keys sorted by their UTF-8 bytes.
# Integers and lengths inside MessagePack are BIG-endian.

def mp_encode(value):
    if value is None:
        return b"\xc0"
    if value is True:
        return b"\xc3"
    if value is False:
        return b"\xc2"
    if isinstance(value, int):
        if 0 <= value <= 0x7F:
            return struct.pack(">B", value)
        if -32 <= value < 0:
            return struct.pack(">b", value)
        if value > 0:
            for limit, lead, fmt in ((0xFF, 0xCC, ">B"), (0xFFFF, 0xCD, ">H"), (0xFFFFFFFF, 0xCE, ">I")):
                if value <= limit:
                    return bytes([lead]) + struct.pack(fmt, value)
            return b"\xcf" + struct.pack(">Q", value)
        for limit, lead, fmt in ((-0x80, 0xD0, ">b"), (-0x8000, 0xD1, ">h"), (-0x80000000, 0xD2, ">i")):
            if value >= limit:
                return bytes([lead]) + struct.pack(fmt, value)
        return b"\xd3" + struct.pack(">q", value)
    if isinstance(value, float):
        return b"\xcb" + struct.pack(">d", value)
    if isinstance(value, str):
        raw = value.encode("utf-8")
        n = len(raw)
        if n <= 31:
            return bytes([0xA0 | n]) + raw
        if n <= 0xFF:
            return b"\xd9" + struct.pack(">B", n) + raw
        if n <= 0xFFFF:
            return b"\xda" + struct.pack(">H", n) + raw
        return b"\xdb" + struct.pack(">I", n) + raw
    if isinstance(value, (list, tuple)):
        n = len(value)
        head = bytes([0x90 | n]) if n <= 15 else (b"\xdc" + struct.pack(">H", n) if n <= 0xFFFF else b"\xdd" + struct.pack(">I", n))
        return head + b"".join(mp_encode(v) for v in value)
    if isinstance(value, dict):
        n = len(value)
        head = bytes([0x80 | n]) if n <= 15 else (b"\xde" + struct.pack(">H", n) if n <= 0xFFFF else b"\xdf" + struct.pack(">I", n))
        body = b""
        for key in sorted(value, key=lambda k: k.encode("utf-8")):
            body += mp_encode(key) + mp_encode(value[key])
        return head + body
    raise TypeError("not encodable: %r" % (value,))


# ----------------------------------------------------------------------------- the envelope

DTYPE_SIZE = {"u8": 1, "u16": 2, "i32": 4, "u32": 4, "f32": 4}


def align16(n):
    return (n + 15) // 16 * 16


def envelope(magic, kind, keys, sections):
    """spec/layouts/ENVELOPE.layout.txt section 1. `sections` is a list of
    (name, dtype, shape, stride, data). Section offsets are absolute and depend on the
    header's own length, so the header is laid out until its length stops changing."""
    header_len = 0
    while True:
        origin = align16(12 + header_len)
        table = []
        cursor = origin
        for (name, dtype, shape, stride, data) in sections:
            table.append({"name": name, "offset": cursor, "size": len(data), "dtype": dtype, "shape": list(shape), "stride": stride})
            cursor = align16(cursor + len(data))
        header = dict(keys)
        header.update({"kind": kind, "endianness": "le", "payload_origin": origin, "payload_size": cursor - origin, "sections": table})
        encoded = mp_encode(header)
        if len(encoded) == header_len:
            break
        header_len = len(encoded)
    out = bytearray(magic + struct.pack("<II", 1, header_len) + encoded)
    out += bytes(origin - len(out))
    for (_name, _dtype, _shape, _stride, data) in sections:
        out += data
        out += bytes(align16(len(out)) - len(out))
    return bytes(out)


def surface_files():
    """One RGBA 8-bit tile at tile (0, 0): spec/layouts/core.raster.surface.layout.txt."""
    fmt = {
        "pixel_mode": "rgb",
        "has_alpha": True,
        "channels": ["red", "green", "blue", "alpha"],
        "sample_type": "u8",
        "tile_size": 256,
        "tile_count": 1,
        "nonfinite": False,
    }
    samples = bytearray()
    for y in range(256):          # rows top to bottom
        for x in range(256):      # pixels left to right
            samples += bytes([x, y, (x + y) % 256, 255])
    tiles_keys = dict(fmt)
    tiles_keys["part"] = "tiles"
    tiles = envelope(b"WKX0", "core.raster.surface", tiles_keys, [("samples", "u8", [1, 256, 256, 4], 4, bytes(samples))])
    index_keys = dict(fmt)
    index_keys["part"] = "index"
    index_keys["tile_files"] = ["tiles-p0-p0"]
    index = envelope(b"WKX0", "core.raster.surface", index_keys, [
        ("default-pixel", "u8", [4], 1, bytes(4)),                           # transparent black
        ("tile-index", "i32", [1, 4], 16, struct.pack("<iiii", 0, 0, 0, 0)),  # tile (0,0): file 0, slot 0
    ])
    return index, tiles


# ----------------------------------------------------------------------------- the capsule

def sha256(data):
    return hashlib.sha256(data).hexdigest()


def read_source(path):
    """Every file of the existing capsule, as {package-relative path: bytes}."""
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
    """True for a file whose NAME carries an `@N` version marker (spec/CRAFT-BASE.md section 4)."""
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


def spec_sha256(spec_entries):
    """spec/SPEC.md section 2: sort by path (UTF-8 bytes); for each: path, 0x0A, the file's
    sha256 as 32 RAW bytes, 0x0A; sha256 of the concatenation."""
    acc = hashlib.sha256()
    for entry in sorted(spec_entries, key=lambda e: e["path"].encode("utf-8")):
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
    if old.get("profile") != "raster-layers/1":
        print("the existing capsule is profile %r, not raster-layers/1" % old.get("profile"))
        return 2

    blobs = {}      # path -> bytes, everything except MANIFEST.json
    nodes = []

    # The base files: loaders/ and spec/ copied unchanged, superseded versions skipped.
    spec_entries = []
    for path in sorted(p for p in src if p.startswith("spec/") and not is_superseded(p)):
        blobs[path] = src[path]
        spec_entries.append(file_entry(path, src[path]))
    nodes.append(node("spec", "core.spec", version(
        spec_entries, "The format specification, travelling inside the file it describes (law 2).")))

    blobs["LICENSE"] = LICENSE_TEXT
    nodes.append(node("license", "core.license", version(
        [file_entry("LICENSE", LICENSE_TEXT)], "The full licence text, embedded, never a link (law 7).")))

    for path in ("README.txt", "HOW-TO-READ.md"):
        blobs[path] = src[path]
    nodes.append(node("readme", "core.readme", version(
        [file_entry("README.txt", blobs["README.txt"], role="payload"),
         file_entry("HOW-TO-READ.md", blobs["HOW-TO-READ.md"], role="how-to-read")],
        "One page for a human, and the reading guide for this profile.",
        payload_file="README.txt")))

    old_nodes = {n["node_id"]: n for n in old["nodes"]}
    for node_id, fname in (("loader-python", "werk_read.py"), ("loader-rust", "werk_read.rs"),
                           ("loader-c", "werk_read.c")):
        path = "loaders/" + fname
        blobs[path] = src[path]
        nodes.append(node(node_id, "core.loader", version(
            [file_entry(path, src[path])],
            "A single-file, dependency-free reader carried as payload (law 1)."),
            meta=old_nodes[node_id]["meta"]))

    # The document's own four files.
    document_bytes = compact_json(DOCUMENT)
    layer_bytes = compact_json(LAYER)
    index_bytes, tiles_bytes = surface_files()
    blobs["document/document.json"] = document_bytes
    blobs["layers/layer-1/layer.json"] = layer_bytes
    blobs["surfaces/layer-1-pixels/surface.wkx"] = index_bytes
    blobs["surfaces/layer-1-pixels/tiles-p0-p0.wkx"] = tiles_bytes
    note = "A minimal document written from the embedded specification alone."
    document_node = node("document", "core.raster.document", version(
        [file_entry("document/document.json", document_bytes, media_type="application/json")], note),
        edges=[{"to": "layer-1", "kind": "enhances", "role": "contains"}],
        meta={"width": 256, "height": 256, "color_mode": "Rgb", "sample_type": "U8"})
    layer_node = node("layer-1", "core.raster.layer", version(
        [file_entry("layers/layer-1/layer.json", layer_bytes, media_type="application/json")],
        "The one layer of the minimal document."),
        edges=[{"to": "layer-1-pixels", "kind": "enhances", "role": "pixels"}],
        meta={"kind": "raster"})
    surface_node = node("layer-1-pixels", "core.raster.surface", version(
        [file_entry("surfaces/layer-1-pixels/surface.wkx", index_bytes, media_type="application/octet-stream", role="payload"),
         file_entry("surfaces/layer-1-pixels/tiles-p0-p0.wkx", tiles_bytes, media_type="application/octet-stream", role="tiles-p0-p0")],
        "The pixels of the one layer: one 256 x 256 tile.",
        payload_file="surfaces/layer-1-pixels/surface.wkx"),
        meta={"usage": "layer-pixels", "owner": "layer-1", "channels": ["red", "green", "blue", "alpha"], "bits_per_sample": 8})

    # The revision record: every node except `revisions`, at version 1.
    uses = {n["node_id"]: 1 for n in nodes}
    for n in (document_node, layer_node, surface_node):
        uses[n["node_id"]] = 1
    record = {"schema_version": 1, "revision": 1, "kind": "save", "note": note,
              "created": CREATED, "producer": dict(PRODUCER), "nodes": uses}
    record_bytes = (json.dumps(record, indent=2, sort_keys=True) + chr(10)).encode("utf-8")
    blobs["revisions/revision.json"] = record_bytes
    nodes.append(node("revisions", "core.revisions", version(
        [file_entry("revisions/revision.json", record_bytes, media_type="application/json")], note)))
    nodes.extend([document_node, layer_node, surface_node])

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
        "primary": {"document": "document"},
        "license": {"file": "LICENSE", "sha256": sha256(LICENSE_TEXT)},
        "schemas": {t: p for t, p in old["schemas"].items() if t in types},
        "layouts": {t: p for t, p in old.get("layouts", {}).items() if t in types},
        "spec_sha256": spec_sha256(spec_entries),
        "entity": {"uuid": new_uuid(), "name": "Minimal", "created": CREATED,
                   "summary": "Written by write_minimal.py from the embedded specification."},
        "nodes": nodes,
        "generator": dict(PRODUCER),
    }
    if "formats" in old:
        # Format definitions are keyed by the formats actually present; this document has none.
        manifest["formats"] = {}
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
    for path in ("document/document.json", "layers/layer-1/layer.json",
                 "surfaces/layer-1-pixels/surface.wkx", "surfaces/layer-1-pixels/tiles-p0-p0.wkx"):
        print("%-42s %7d bytes  sha256 %s" % (path, len(blobs[path]), sha256(blobs[path])))
    print("wrote %s: %d nodes, %d files, manifest sha256 %s"
          % (out_path, len(nodes), len(blobs), sha256(manifest_bytes)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
