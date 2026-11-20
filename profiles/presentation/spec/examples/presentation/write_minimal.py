#!/usr/bin/env python3
"""write_minimal.py - write a minimal valid `presentation/1` werk capsule.

Python standard library only. It uses NO presentation software and NO werk software: it is the
executable form of spec/PROFILE-PRESENTATION.md section 7 ("Writing a minimal valid
presentation/1 capsule") and of spec/CRAFT-BASE.md section 8. It copies loaders/ and spec/ out
of an existing capsule of the same profile (their content is the format) and writes everything
else itself.

    python write_minimal.py <existing capsule: .werk file or directory> <new.werk>

The document it writes: a 960 x 540 point deck with one master, one blank layout and ONE slide.
On the slide: a yellow rectangle at (80, 60), 400 x 120 points, holding the text "Hello, werk",
and the speaker note "Written by a stranger."

Its payloads are fixed, so their sizes and hashes are checkpoints for another implementation
(spec/PROFILE-PRESENTATION.md section 7.1 lists them):

    deck/document.json            the structure node
    deck/masters/master-1.json    the master: theme colours and fonts, a white background
    deck/layouts/layout-2.json    the layout "Blank"
    deck/slides/slide-3.json      the slide

It writes no preview picture, no outline text and no core.slide.geometry node: those are
derived conveniences, and this script has no renderer. A reader draws the slide from the four
payloads alone (the one shape is the preset `rect`, which section 4.4 defines).
"""

import hashlib
import json
import os
import sys
import zipfile

LF = bytes([10])
CREATED = "2026-10-12T00:00:00Z"
PRODUCER = {"tool": "write_minimal.py", "version": "1"}
NOTE = "A minimal presentation written from the embedded specification alone."
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


# ---------------------------------------------------------------- the four payloads

def rgb(r, g, b):
    return {"r": r, "g": g, "b": b, "a": 255}


def scheme(slot):
    """A colour that names a slot of the master's theme."""
    return {"base": {"kind": "scheme", "slot": slot}}


def document_payload():
    return {
        "schema_version": 1,
        "slide_size": {"width": 960, "height": 540},
        "notes_size": {"width": 540, "height": 720},
        "first_slide_number": 1,
        "next_id": 4,
        "slides": [{"id": 3, "node": "slide-3"}],
        "masters": [{"id": 1, "node": "master-1", "layouts": [{"id": 2, "node": "layout-2"}]}],
        "media": [],
        "props": {"title": "Minimal deck"},
    }


def master_payload():
    # The twelve theme colours, in the fixed order dk1, lt1, dk2, lt2, accent1..accent6, hlink, folHlink.
    colors = [rgb(0, 0, 0), rgb(255, 255, 255), rgb(30, 43, 60), rgb(237, 235, 231),
              rgb(46, 111, 216), rgb(242, 107, 29), rgb(46, 163, 111), rgb(138, 92, 216),
              rgb(216, 63, 107), rgb(227, 178, 28), rgb(46, 111, 216), rgb(122, 91, 166)]
    return {
        "schema_version": 1,
        "role": "slide",
        "master": {
            "id": 1,
            "name": "Minimal master",
            "theme": {
                "name": "Minimal",
                "colors": {"name": "Minimal", "colors": colors},
                "fonts": {"name": "Minimal", "major": {"latin": "Inter"}, "minor": {"latin": "Inter"}},
                "format": {"name": "Minimal"},
            },
            "background": {"kind": "fill", "fill": {"kind": "solid", "color": scheme("bg1")}},
        },
    }


def layout_payload():
    return {"schema_version": 1, "master": "master-1", "layout": {"id": 2, "name": "Blank", "kind": "blank"}}


def slide_payload():
    hello = {
        "id": 4,
        "name": "Hello box",
        "xfrm": {"x": 80, "y": 60, "w": 400, "h": 120},
        "kind": {"type": "shape"},
        "geom": {"kind": "preset", "name": "rect"},
        "fill": {"kind": "solid", "color": {"base": {"kind": "rgb", "rgb": rgb(255, 204, 0)}}},
        "line": {"fill": {"kind": "none"}},
        "text": {"paragraphs": [{"runs": [{"text": "Hello, werk", "props": {"size": 32, "bold": True}}]}]},
    }
    return {
        "schema_version": 1,
        "slide": {
            "id": 3,
            "layout": 2,
            "shapes": [hello],
            "notes": {"paragraphs": [{"runs": [{"text": "Written by a stranger."}]}]},
        },
    }


def payloads():
    """logical path -> bytes, for the four payloads of the minimal document."""
    return {
        "deck/document.json": compact(document_payload()),
        "deck/masters/master-1.json": compact(master_payload()),
        "deck/layouts/layout-2.json": compact(layout_payload()),
        "deck/slides/slide-3.json": compact(slide_payload()),
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
    if old.get("profile") != "presentation/1":
        print("the existing capsule is profile %r, not presentation/1" % old.get("profile"))
        return 2
    blobs, nodes = {}, []
    old_nodes = {n["node_id"]: n for n in old["nodes"]}

    # The base files: loaders/ and spec/ copied unchanged, superseded versions skipped. Format
    # definitions (spec/formats/) and the reference decoders (tools/) belong to media this
    # document does not have, so they are left out.
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
            meta=old_nodes[node_id]["meta"]))

    # The document: four nodes, one file each.
    files = payloads()
    blobs.update(files)
    entry = lambda path: [file_entry(path, files[path], media_type="application/json")]
    contains = lambda to: {"to": to, "kind": "enhances", "role": "contains"}
    document = [
        node("document", "core.slide.document", version(entry("deck/document.json"), NOTE),
             edges=[contains("slide-3"), contains("master-1"), contains("layout-2")]),
        node("master-1", "core.slide.master", version(entry("deck/masters/master-1.json"), NOTE)),
        # A layout is meaningless without its master: `requires`.
        node("layout-2", "core.slide.layout", version(entry("deck/layouts/layout-2.json"), NOTE),
             edges=[{"to": "master-1", "kind": "requires", "role": "master"}]),
        # A slide whose layout is damaged is still a slide: `enhances`.
        node("slide-3", "core.slide.slide", version(entry("deck/slides/slide-3.json"), NOTE),
             edges=[{"to": "layout-2", "kind": "enhances", "role": "layout"}]),
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
        "primary": {"document": "document"},
        "license": {"file": "LICENSE", "sha256": sha256(LICENSE_TEXT)},
        "schemas": {t: p for t, p in old["schemas"].items() if t in types},
        "layouts": {t: p for t, p in old.get("layouts", {}).items() if t in types},
        "spec_sha256": spec_sha256(spec_entries),
        "entity": {"uuid": new_uuid(), "name": "Minimal deck", "created": CREATED,
                   "summary": "Written by write_minimal.py from the embedded specification."},
        "nodes": nodes,
        "generator": dict(PRODUCER),
    }
    if "profile_spec" in old:
        manifest["profile_spec"] = old["profile_spec"]
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
    for path in sorted(files):
        print("%-28s %6d bytes  sha256 %s" % (path, len(files[path]), sha256(files[path])))
    print("wrote %s: %d nodes, %d files, manifest sha256 %s" % (out_path, len(nodes), len(blobs), sha256(manifest_bytes)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
