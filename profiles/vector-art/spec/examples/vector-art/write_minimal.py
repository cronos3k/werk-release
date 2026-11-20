#!/usr/bin/env python3
"""write_minimal.py - write a minimal valid `vector-art/1` werk capsule.

Python standard library only. It uses NO ArtCraft software: it is the executable form of
spec/PROFILE-VECTOR-ART.md section 7 ("Writing a minimal valid vector-art/1 capsule") and of
spec/CRAFT-BASE.md section 8. It copies loaders/ and spec/ out of an existing capsule of the
same profile (their content is the format) and writes everything else itself.

    python write_minimal.py <existing capsule: .werk file or directory> <new.werk>

The document it writes: one artboard of 200 x 100 points, one layer, one red rectangle.
The three payloads are fixed, so their hashes are a checkpoint for another implementation:

    vector/artboards/artboard-1.json   89 bytes  c317ee569895e512aab830a9caee0784cacc3370021b67eab3402f220c7bd67b
    vector/layers/layer-1.json        384 bytes  69c19576e9a06c92cbb3357c7d95851ccb6e2cd3b99769c3e5e3c5a79326d850
    vector/document.json               87 bytes  92c86b4bf15d587f5a610d9b7de016deed71c21c2e516741cf3bfdf88850da2d
"""

import hashlib
import json
import os
import sys
import zipfile

LF = bytes([10])
CREATED = "2026-10-12T00:00:00Z"
PRODUCER = {"tool": "write_minimal.py", "version": "1"}

ARTBOARD = b'{"schema_version":1,"id":1,"name":"Artboard 1","rect":{"x0":0,"y0":0,"x1":200,"y1":100}}' + LF
LAYER = (
    b'{"schema_version":1,"layer":{"id":1,"name":"Layer 1","kind":{"type":"layer","color":{"Preset":0},'
    b'"children":[{"id":2,"name":"Red rectangle","appearance":{"items":[{"kind":"fill","paint":{"type":"solid",'
    b'"color":{"model":"rgb","r":1,"g":0,"b":0}}}]},"kind":{"type":"path","path":{"subpaths":[{"anchors":['
    b'{"p":[20,20]},{"p":[180,20]},{"p":[180,80]},{"p":[20,80]}],"closed":true}]}}}]}}}' + LF
)
DOCUMENT = b'{"schema_version":1,"title":"Minimal","artboards":["artboard-1"],"layers":["layer-1"]}' + LF

LICENSE_TEXT = (
    "Licence notice" + chr(10) + chr(10)
    + "THE TERMS OF THIS DOCUMENT'S CONTENT ARE NOT ESTABLISHED." + chr(10) + chr(10)
    + "This file was written by write_minimal.py as a worked example. No licence is granted "
    + "by this notice; anyone redistributing the file must establish its terms." + chr(10)
).encode("utf-8")


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
    tail = name.rsplit("@", 1)[1]
    return tail.split(".", 1)[0].isdigit()


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
    if old.get("profile") != "vector-art/1":
        print("the existing capsule is profile %r, not vector-art/1" % old.get("profile"))
        return 2

    blobs = {}  # path -> bytes, everything except MANIFEST.json
    nodes = []

    # 7.2 the base files: loaders/ and spec/ copied unchanged, superseded versions skipped.
    spec_entries = []
    for path in sorted(p for p in src if p.startswith("spec/") and not is_superseded(p)):
        blobs[path] = src[path]
        spec_entries.append(file_entry(path, src[path]))
    nodes.append(node("spec", "core.spec", version(spec_entries, "The format specification, travelling inside the file it describes (law 2).")))

    blobs["LICENSE"] = LICENSE_TEXT
    nodes.append(node("license", "core.license", version([file_entry("LICENSE", LICENSE_TEXT)], "The full licence text, embedded, never a link (law 7).")))

    for path in ("README.txt", "HOW-TO-READ.md"):
        blobs[path] = src[path]
    nodes.append(
        node(
            "readme",
            "core.readme",
            version(
                [file_entry("README.txt", blobs["README.txt"], role="payload"), file_entry("HOW-TO-READ.md", blobs["HOW-TO-READ.md"], role="how-to-read")],
                "One page for a human, and the reading guide for this profile.",
                payload_file="README.txt",
            ),
        )
    )

    old_nodes = {n["node_id"]: n for n in old["nodes"]}
    for node_id, fname in (("loader-python", "werk_read.py"), ("loader-rust", "werk_read.rs"), ("loader-c", "werk_read.c")):
        path = "loaders/" + fname
        blobs[path] = src[path]
        nodes.append(
            node(node_id, "core.loader", version([file_entry(path, src[path])], "A single-file, dependency-free reader carried as payload (law 1)."), meta=old_nodes[node_id]["meta"])
        )

    # 7.1 the three payloads.
    payloads = [
        ("artboard-1", "core.vector.artboard", "vector/artboards/artboard-1.json", ARTBOARD, "The one artboard of the minimal document."),
        ("layer-1", "core.vector.layer", "vector/layers/layer-1.json", LAYER, "The one layer of the minimal document: a red rectangle."),
        ("document", "core.vector.document", "vector/document.json", DOCUMENT, "A minimal document written from the embedded specification alone."),
    ]
    content = []
    for node_id, node_type, path, data, note in payloads:
        blobs[path] = data
        edges = []
        if node_id == "document":
            edges = [{"to": "artboard-1", "kind": "enhances", "role": "contains"}, {"to": "layer-1", "kind": "enhances", "role": "contains"}]
        content.append(node(node_id, node_type, version([file_entry(path, data, media_type="application/json")], note), edges=edges))

    # 7.3 the revision record: every node except `revisions`, at version 1.
    uses = {n["node_id"]: 1 for n in nodes + content}
    record = {
        "schema_version": 1,
        "revision": 1,
        "kind": "save",
        "note": "A minimal document written from the embedded specification alone.",
        "created": CREATED,
        "producer": dict(PRODUCER),
        "nodes": uses,
    }
    record_bytes = (json.dumps(record, indent=2, sort_keys=True) + chr(10)).encode("utf-8")
    blobs["revisions/revision.json"] = record_bytes
    nodes.append(node("revisions", "core.revisions", version([file_entry("revisions/revision.json", record_bytes, media_type="application/json")], record["note"])))
    nodes.extend(content)

    # 7.4 the manifest.
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
        "entity": {"uuid": new_uuid(), "name": "Minimal", "created": CREATED, "summary": "Written by write_minimal.py from the embedded specification."},
        "nodes": nodes,
        "generator": dict(PRODUCER),
    }
    manifest_bytes = (json.dumps(manifest, indent=2, ensure_ascii=False) + chr(10)).encode("utf-8")

    # 7.5 the container: store mode, MANIFEST.json first, the preview tier before the rest.
    tier = container["preview_tier"]

    def tier_rank(path):
        for i, t in enumerate(tier):
            if path.startswith(t) if t.endswith("/") else path == t:
                return i
        return len(tier)

    ordered = sorted(blobs, key=lambda p: (tier_rank(p), p.encode("utf-8")))
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_STORED) as z:
        for name, data in [("MANIFEST.json", manifest_bytes)] + [(p, blobs[p]) for p in ordered]:
            info = zipfile.ZipInfo(name, date_time=(2026, 8, 8, 9, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            z.writestr(info, data)
    print("wrote %s: %d nodes, %d files, manifest sha256 %s" % (out_path, len(nodes), len(blobs), sha256(manifest_bytes)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
