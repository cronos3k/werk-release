#!/usr/bin/env python3
"""write_minimal.py - write a minimal valid `motion-comp/1` werk capsule.

Python standard library only. It uses NO motion-graphics software and NO werk software: it is
the executable form of spec/PROFILE-MOTION-COMP.md section 7 ("Writing a minimal valid
motion-comp/1 capsule") and of spec/CRAFT-BASE.md section 8. It copies loaders/ and spec/ out of
an existing capsule of the same profile (their content is the format) and writes everything
else itself.

    python write_minimal.py <existing capsule: .werk file or directory> <new.werk> [--tracks]

The project it writes: one 8 x 8 solid of colour (1.0, 0.5, 0.25), and one composition
`Minimal` - 32 x 18 pixels, 25 frames per second, 1 second - with one layer that shows the
solid and moves it one pixel per frame from x = 4 to x = 29 at y = 9 (two Linear keyframes on
`transform/position`). At frame f the square covers columns f .. f+7 and rows 5 .. 12.

Its payloads are fixed, so their sizes and hashes are checkpoints for another implementation
(the profile document's section 7.1 lists them):

    project/project.json          the structure node
    items/item-1.json             the solid
    comps/comp-2/comp.json        the composition
    comps/comp-2/layer-3.json     its layer

With --tracks the two keyframes are written as a `core.keyframe.tracks` node instead
(comps/comp-2/layer-3.keys.wkx, layout spec/layouts/core.keyframe.tracks.layout.txt) and the
layer's `position` names track 0: the same project in the other spelling.

It writes no preview, no effect catalog and no editor view: all optional.
"""

import hashlib
import json
import os
import struct
import sys
import zipfile

LF = bytes([10])
CREATED = "2026-10-13T00:00:00Z"
PRODUCER = {"tool": "write_minimal.py", "version": "1"}
NOTE = "A minimal project written from the embedded specification alone."
LICENSE_TEXT = (
    "Licence notice" + chr(10) + chr(10)
    + "THE TERMS OF THIS DOCUMENT'S CONTENT ARE NOT ESTABLISHED." + chr(10) + chr(10)
    + "This file was written by write_minimal.py as a worked example. No licence is granted "
    + "by this notice; anyone redistributing the file must establish its terms." + chr(10)
).encode("utf-8")

TPS = 254016000000                 # ticks per second
SECOND = TPS

# Every object of the project has an id; all ids share one counter (`next_id`).
SOLID, COMP, LAYER = 1, 2, 3
ROOT, TRANSFORM, ANCHOR, POSITION, SCALE, ROTATION, OPACITY = 4, 5, 6, 7, 8, 9, 10
KEYS = [(0, [4.0, 9.0, 0.0]), (SECOND, [29.0, 9.0, 0.0])]


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def compact(value):
    """One line of JSON with sorted keys and one line feed: the spelling whose hashes section
    7.1 lists."""
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False, sort_keys=True).encode("utf-8") + LF


# ---------------------------------------------------------------- the payloads (section 7.1)

def project_payload():
    return {
        "schema_version": 1,
        "app_schema": 2,
        "settings": {"bit_depth": "Bpc8", "linearize": False, "time_display": "Timecode", "frame_start": 0, "audio_sample_rate": 48000},
        "next_id": OPACITY + 1,
        "folders": [],
        # which node holds which item
        "items": [
            {"id": SOLID, "kind": "solid", "node": "item-%d" % SOLID},
            {"id": COMP, "kind": "comp", "node": "comp-%d" % COMP},
        ],
        "fonts": [],
    }


def item_payload():
    return {
        "schema_version": 1,
        "id": SOLID,
        "name": "Square",
        "label": "None",
        "kind": {"Solid": {"color": [1.0, 0.5, 0.25], "width": 8, "height": 8, "pixel_aspect": 1.0}},
    }


def comp_payload():
    return {
        "schema_version": 1,
        "id": COMP,
        "name": "Minimal",
        "label": "None",
        "comp": {
            "width": 32, "height": 18, "pixel_aspect": 1.0,
            "frame_rate": {"num": 25, "den": 1},
            "duration": SECOND,
            "display_start": 0,
            "background": [0.0, 0.0, 0.0],
            "work_area": [0, SECOND],
            "shutter_angle": 180.0, "shutter_phase": -90.0, "motion_blur_samples": 16,
        },
        # the layers, front first
        "layers": [{"id": LAYER, "node": "layer-%d" % LAYER}],
    }


def prop(uid, match, name, kind, v):
    return {"node": "Prop", "uid": uid, "match": match, "name": name, "value": {"t": kind, "v": v}}


def layer_payload(tracks):
    position = prop(POSITION, "position", "Position", "Vec3", KEYS[0][1])
    if tracks:
        position["track"] = 0                       # track 0 of the node named by `tracks`
    else:
        position["keys"] = [{"time": t, "value": {"t": "Vec3", "v": v}} for t, v in KEYS]
    payload = {
        "schema_version": 1,
        "comp": COMP,
        "layer": {
            "id": LAYER,
            "name": "Square",
            "label": "None",
            "source": {"type": "Solid", "item": SOLID},
            "start_time": 0, "in_point": 0, "out_point": SECOND, "stretch": 100.0,
            "switches": {
                "video": True, "audio": True, "solo": False, "locked": False, "shy": False, "collapse": False,
                "quality": "Best", "sampling": "Bilinear", "effects": True, "frame_blend": "Off",
                "motion_blur": False, "adjustment": False, "three_d": False, "guide": False,
            },
            "blend_mode": "Normal",
            "props": {
                "uid": ROOT, "match": "layer", "name": "Square",
                "children": [{
                    "node": "Group", "uid": TRANSFORM, "match": "transform", "name": "Transform",
                    "children": [
                        prop(ANCHOR, "anchor", "Anchor Point", "Vec3", [4.0, 4.0, 0.0]),
                        position,
                        prop(SCALE, "scale", "Scale", "Vec3", [100.0, 100.0, 100.0]),
                        prop(ROTATION, "rotation", "Rotation", "Scalar", 0.0),
                        prop(OPACITY, "opacity", "Opacity", "Scalar", 100.0),
                    ],
                }],
            },
        },
    }
    if tracks:
        payload["tracks"] = "layer-%d-keys" % LAYER
    return payload


# ---------------------------------------------------------------- the keyframe tracks binary

def mp(value):
    """Canonical MessagePack (spec/layouts/ENVELOPE.layout.txt section 4.3): shortest integer
    and string forms, map keys sorted by their bytes."""
    if isinstance(value, bool):
        return bytes([0xC3 if value else 0xC2])
    if isinstance(value, int):
        if 0 <= value <= 0x7F:
            return bytes([value])
        if value >= 0:
            for code, fmt, top in ((0xCC, ">B", 0xFF), (0xCD, ">H", 0xFFFF), (0xCE, ">I", 0xFFFFFFFF), (0xCF, ">Q", 0xFFFFFFFFFFFFFFFF)):
                if value <= top:
                    return bytes([code]) + struct.pack(fmt, value)
        if value >= -32:
            return struct.pack(">b", value)
        for code, fmt, low in ((0xD0, ">b", -0x80), (0xD1, ">h", -0x8000), (0xD2, ">i", -0x80000000), (0xD3, ">q", -0x8000000000000000)):
            if value >= low:
                return bytes([code]) + struct.pack(fmt, value)
    if isinstance(value, float):
        return bytes([0xCB]) + struct.pack(">d", value)
    if isinstance(value, str):
        raw = value.encode("utf-8")
        if len(raw) <= 31:
            return bytes([0xA0 | len(raw)]) + raw
        if len(raw) <= 0xFF:
            return bytes([0xD9, len(raw)]) + raw
        return bytes([0xDA]) + struct.pack(">H", len(raw)) + raw
    if isinstance(value, (list, tuple)):
        head = bytes([0x90 | len(value)]) if len(value) <= 15 else bytes([0xDC]) + struct.pack(">H", len(value))
        return head + b"".join(mp(v) for v in value)
    if isinstance(value, dict):
        head = bytes([0x80 | len(value)]) if len(value) <= 15 else bytes([0xDE]) + struct.pack(">H", len(value))
        return head + b"".join(mp(k) + mp(value[k]) for k in sorted(value, key=lambda k: k.encode("utf-8")))
    raise TypeError(value)


def align16(n):
    return (n + 15) // 16 * 16


def envelope(magic, kind, header, sections):
    """A werk envelope. `sections`: [(name, dtype, shape, stride, bytes)] in file order."""
    origin = 0
    while True:                                  # the header's length depends on the offsets in it
        table, cursor = [], origin
        for name, dtype, shape, stride, data in sections:
            table.append({"name": name, "dtype": dtype, "shape": shape, "stride": stride, "offset": cursor, "size": len(data)})
            cursor = align16(cursor + len(data))
        full = dict(header)
        full.update({"kind": kind, "endianness": "le", "payload_origin": origin, "payload_size": cursor - origin, "sections": table})
        packed = mp(full)
        need = align16(12 + len(packed))
        if need == origin:
            break
        origin = need
    out = bytearray(magic + struct.pack("<II", 1, len(packed)) + packed)
    out += bytes(origin - len(out))
    for entry, (_n, _d, _s, _st, data) in zip(table, sections):
        out += bytes(entry["offset"] - len(out))
        out += data
    out += bytes(cursor - len(out))
    return bytes(out)


def tracks_payload():
    """spec/layouts/core.keyframe.tracks.layout.txt: one vec3 track of two Linear keys."""
    k = len(KEYS)
    header = {
        "owner": "layer-%d" % LAYER,
        "ticks_per_second": TPS,
        "interpolations": ["Linear", "Bezier", "Hold"],
        "tracks": [{"uid": POSITION, "kind": "vec3", "components": 3, "keys": k, "first_key": 0, "first_value": 0, "first_ease": 0}],
    }
    at = b"".join(struct.pack("<q", t) for t, _v in KEYS)
    interp = bytes([0, 0] * k)                    # in, out: Linear
    flags = bytes([4] * k)                        # bit 2: spatial_auto, the default of a key
    label = bytes(k)
    value = b"".join(struct.pack("<3d", *v) for _t, v in KEYS)
    spatial = b"".join(struct.pack("<6d", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0) for _ in KEYS)
    ease_count = bytes([0, 0] * k)
    sections = [
        ("at", "i64", [k], 8, at),
        ("interp", "u8", [k, 2], 2, interp),
        ("flags", "u8", [k], 1, flags),
        ("label", "u8", [k], 1, label),
        ("value", "f64", [3 * k], 8, value),
        ("spatial", "f64", [k, 6], 48, spatial),
        ("ease-count", "u8", [k, 2], 2, ease_count),
        ("ease", "f64", [0, 2], 16, b""),
    ]
    return envelope(b"WKX3", "core.keyframe.tracks", header, sections)


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
    args = [a for a in argv[1:] if not a.startswith("--")]
    tracks = "--tracks" in argv
    if len(args) != 2:
        print(__doc__.strip())
        return 2
    source, out_path = args
    src = read_source(source)
    old = json.loads(src["MANIFEST.json"].decode("utf-8"))
    if old.get("profile") != "motion-comp/1":
        print("the existing capsule is profile %r, not motion-comp/1" % old.get("profile"))
        return 2
    old_nodes = {n["node_id"]: n for n in old["nodes"]}
    blobs, nodes = {}, []

    # The base files: loaders/ and spec/ copied unchanged - except spec/formats/, the definitions
    # of foreign encodings the existing capsule's payloads were in: this capsule has no such
    # payload. Superseded versions of files are skipped.
    spec_entries = []
    for path in sorted(p for p in src if p.startswith("spec/") and not p.startswith("spec/formats/") and not is_superseded(p)):
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
    for node_id, fname in (("loader-python", "werk_read.py"), ("loader-rust", "werk_read.rs"), ("loader-c", "werk_read.c")):
        path = "loaders/" + fname
        blobs[path] = src[path]
        nodes.append(node(node_id, "core.loader", version(
            [file_entry(path, src[path])], "A single-file, dependency-free reader carried as payload (law 1)."),
            meta=old_nodes[node_id].get("meta")))

    # The document (section 7.2).
    comp_dir = "comps/comp-%d/" % COMP
    files = {
        "project/project.json": compact(project_payload()),
        "items/item-%d.json" % SOLID: compact(item_payload()),
        comp_dir + "comp.json": compact(comp_payload()),
        comp_dir + "layer-%d.json" % LAYER: compact(layer_payload(tracks)),
    }
    item_node, comp_node, layer_node, keys_node = "item-%d" % SOLID, "comp-%d" % COMP, "layer-%d" % LAYER, "layer-%d-keys" % LAYER
    entry = lambda path: [file_entry(path, files[path], media_type="application/json")]
    edge = lambda to, kind, role: {"to": to, "kind": kind, "role": role}
    layer_edges = [edge(item_node, "enhances", "source")]
    document = [node(item_node, "core.motion.item", version(entry("items/item-%d.json" % SOLID), NOTE))]
    if tracks:
        keys_path = comp_dir + "layer-%d.keys.wkx" % LAYER
        files[keys_path] = tracks_payload()
        document.append(node(keys_node, "core.keyframe.tracks",
                             version([file_entry(keys_path, files[keys_path], media_type="application/octet-stream")], NOTE),
                             edges=[edge(layer_node, "requires", "animates")]))
        layer_edges.append(edge(keys_node, "enhances", "keyframes"))
    document += [
        node(layer_node, "core.motion.layer", version(entry(comp_dir + "layer-%d.json" % LAYER), NOTE), edges=layer_edges),
        node(comp_node, "core.motion.comp", version(entry(comp_dir + "comp.json"), NOTE), edges=[edge(layer_node, "enhances", "layer")]),
        node("project", "core.motion.project", version(entry("project/project.json"), NOTE),
             edges=[edge(item_node, "enhances", "contains"), edge(comp_node, "enhances", "contains")]),
    ]
    blobs.update(files)

    # The revision record: every node except `revisions`, at version 1.
    uses = {n["node_id"]: 1 for n in nodes + document}
    record = {"schema_version": 1, "revision": 1, "kind": "save", "note": NOTE, "created": CREATED,
              "producer": dict(PRODUCER), "nodes": uses}
    record_bytes = (json.dumps(record, indent=2, sort_keys=True) + chr(10)).encode("utf-8")
    blobs["revisions/revision.json"] = record_bytes
    nodes.append(node("revisions", "core.revisions", version(
        [file_entry("revisions/revision.json", record_bytes, media_type="application/json")], NOTE)))
    nodes.extend(document)

    # The manifest (section 7.3).
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
        "primary": {"document": "project"},
        "license": {"file": "LICENSE", "sha256": sha256(LICENSE_TEXT)},
        # Only the node types actually written.
        "schemas": {t: p for t, p in old["schemas"].items() if t in types},
        "layouts": {t: p for t, p in old.get("layouts", {}).items() if t in types},
        "formats": {},
        "spec_sha256": spec_sha256(spec_entries),
        "entity": {"uuid": new_uuid(), "name": "Minimal", "created": CREATED,
                   "summary": "Written by write_minimal.py from the embedded specification."},
        "nodes": nodes,
        "generator": dict(PRODUCER),
    }
    if "profile_spec" in old:
        manifest["profile_spec"] = old["profile_spec"]
    if tracks and "core.keyframe.tracks" not in manifest["layouts"]:
        # the existing capsule had no tracks node: the layout file is in spec/ all the same
        manifest["layouts"]["core.keyframe.tracks"] = "spec/layouts/core.keyframe.tracks.layout.txt"
    for t in ("core.motion.project", "core.motion.item", "core.motion.comp", "core.motion.layer"):
        manifest["schemas"].setdefault(t, "spec/schemas/%s.schema.json" % t)
    manifest_bytes = (json.dumps(manifest, indent=2, ensure_ascii=False) + chr(10)).encode("utf-8")

    # The container (section 7.4): store mode, MANIFEST.json first, the preview tier before the rest.
    tier = container["preview_tier"]

    def tier_rank(path):
        for i, t in enumerate(tier):
            if (path.startswith(t) if t.endswith("/") else path == t):
                return i
        return len(tier)

    ordered = sorted(blobs, key=lambda p: (tier_rank(p), p.encode("utf-8")))
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_STORED) as z:
        for name, data in [("MANIFEST.json", manifest_bytes)] + [(p, blobs[p]) for p in ordered]:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0
            z.writestr(info, data)

    print("wrote %s: %d files, %d bytes of payload" % (out_path, len(blobs) + 1, container["total_size_bytes"]))
    for path in sorted(files):
        print("  %-34s %6d bytes  sha256 %s" % (path, len(files[path]), sha256(files[path])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
