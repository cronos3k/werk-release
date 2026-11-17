#!/usr/bin/env python3
"""write_minimal.py - write a minimal valid `rich-document/1` werk capsule.

Python standard library only. It uses NO WordCraft or ArtCraft software: it is the executable
form of spec/PROFILE-RICH-DOCUMENT.md section 7 ("Writing a minimal valid rich-document/1
capsule") and of spec/CRAFT-BASE.md section 8. It copies loaders/ and spec/ out of an existing
capsule of the same profile (their content is the format) and writes everything else itself.

    python write_minimal.py <existing capsule: .werk file or directory> <new.werk>

The document it writes has two paragraphs, the second with a bold word:

    Hello, werk.
    **Bold** and plain.

The files it writes are fixed, so their sizes and hashes are a checkpoint for another
implementation (the same values are printed in section 7 of the profile document). The two
compressed files are written as zlib streams that hold one STORED block - valid zlib that any
inflater reads, and the same bytes whatever zlib library is at hand:

    text/body-000001.blocks.zlib, inflated        156 bytes  e3accf6c015d73be5c749c01cbcd8718498c4cf99f9439d19171a83da86e5dc8
    text/body-000001.blocks.zlib                  167 bytes  db2370ffd562dee692eda074dee27b3113cd7aa7dbc698598109569e8da142d4
    text/body-000001.json                         312 bytes  f1c694e138926da281a8f601143f8f24358d1b35119b79e8a5a87f018752915e
    preview/text/body-000001.txt.zlib, inflated    29 bytes  f2a1a185d8beee94a3c2f3cf785e462caa5c5f5555be736149d93f8bebc3c60b
    preview/text/body-000001.txt.zlib              40 bytes  108a7b06b121cc87cc1885fd2eced08c09d9f75df4e190776c856a90d1ffdee1
    document/document.json                        149 bytes  475be196cfbbf4e7546d3644e0eba3551139f0718005a31991113e7aa626a5f6
    input_hash of the plain text                             09a55075cc8505563cb334a222529d8398a02be38dfebc1c4289a928cfab00b7
"""

import hashlib
import json
import os
import struct
import sys
import zipfile
import zlib

LF = bytes([10])
PROFILE = "rich-document/1"
CREATED = "2026-10-12T00:00:00Z"
PRODUCER = {"tool": "write_minimal.py", "version": "1"}
NOTE = "A minimal document written from the embedded specification alone."

ZLIB = "zlib-deflate"   # the format id of both compressed files: MANIFEST.json -> formats


def zlib_stored(data):
    """A zlib stream (RFC 1950) whose DEFLATE data is ONE stored block (RFC 1951 section 3.2.4):
    the two header bytes 78 01, the block header 01, the length and its one's complement as
    little-endian u16, the bytes themselves, and the Adler-32 of the bytes, big-endian. No
    compression - and so no dependence on which zlib wrote it. Good for at most 65535 bytes;
    a real writer calls its zlib (zlib.compress(data) is just as valid)."""
    assert len(data) <= 0xFFFF
    return (bytes([0x78, 0x01, 0x01]) + struct.pack("<HH", len(data), len(data) ^ 0xFFFF)
            + data + struct.pack(">I", zlib.adler32(data)))


# 7.1 The blocks: a JSON array, one block per line (any valid JSON spelling would do as well).
BLOCKS_TEXT = LF.join([
    b'[',
    b'{"kind":"para","text":"Hello, werk.","runs":[{"len":12}]},',
    b'{"kind":"para","text":"Bold and plain.","runs":[{"len":4,"props":{"bold":true}},{"len":11}]}',
    b']',
]) + LF
BLOCKS_FILE = zlib_stored(BLOCKS_TEXT)
# The node's payload: a small header that says what the blocks are and describes that file.
BODY_PAYLOAD = (json.dumps({
    "schema_version": 1,
    "story": {"kind": "body"},
    "blocks": {"count": 2, "role": "blocks", "format": ZLIB,
               "stored_size": len(BLOCKS_FILE), "stored_sha256": hashlib.sha256(BLOCKS_FILE).hexdigest(),
               "inflated_size": len(BLOCKS_TEXT), "inflated_sha256": hashlib.sha256(BLOCKS_TEXT).hexdigest()},
}, separators=(",", ":")) + chr(10)).encode("utf-8")
# The plain text derived from the blocks (section 3.11): one line per paragraph; stored compressed.
TEXT_PLAIN = b"Hello, werk." + LF + b"Bold and plain." + LF
TEXT_PAYLOAD = zlib_stored(TEXT_PLAIN)
TEXT_PARAMS = {"method": "rich-document-plain-text-1"}
DOC_PAYLOAD = (
    b'{"schema_version":1,"body":["body-000001"],"bodyNextId":2,"finalSection":{},'
    b'"stories":[],"noteSeparators":[],"media":[],"plainText":["text-000001"]}' + LF
)
LICENSE_TEXT = (
    "Licence notice" + chr(10) + chr(10)
    + "THE TERMS OF THIS DOCUMENT'S CONTENT ARE NOT ESTABLISHED." + chr(10) + chr(10)
    + "This file was written by write_minimal.py as a worked example. No licence is granted "
    + "by this notice; anyone redistributing the file must establish its terms." + chr(10)
).encode("utf-8")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    """Canonical JSON: keys sorted, no insignificant white space, UTF-8 (spec/MINI-SPECS.md)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def input_hash(input_sha256s, params):
    """spec/CRAFT-BASE.md section 5: each input's sha256 as 32 RAW bytes, in input_files order,
    then the canonical JSON of input_params; sha256 of the concatenation."""
    acc = hashlib.sha256()
    for digest in input_sha256s:
        acc.update(bytes.fromhex(digest))
    acc.update(canonical(params))
    return acc.hexdigest()


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
    digits = tail.split(".", 1)[0]
    return digits.isdigit()


def file_entry(path, data, **extra):
    entry = {"path": path, "sha256": sha256(data), "size": len(data)}
    entry.update(extra)
    return entry


def version(files, note, **extra):
    v = {"v": 1, "files": files, "note": note, "producer": dict(PRODUCER),
         "epistemic": "authored", "created": CREATED}
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


def checkpoints():
    """The sizes and SHA-256 values of what this script writes, as printed in its docstring."""
    rows = [("text/body-000001.blocks.zlib, inflated", BLOCKS_TEXT),
            ("text/body-000001.blocks.zlib", BLOCKS_FILE),
            ("text/body-000001.json", BODY_PAYLOAD),
            ("preview/text/body-000001.txt.zlib, inflated", TEXT_PLAIN),
            ("preview/text/body-000001.txt.zlib", TEXT_PAYLOAD),
            ("document/document.json", DOC_PAYLOAD)]
    out = ["    %-44s %4d bytes  %s" % (name, len(data), sha256(data)) for name, data in rows]
    out.append("    %-44s             %s" % ("input_hash of the plain text", input_hash([sha256(BODY_PAYLOAD)], TEXT_PARAMS)))
    return out


def main(argv):
    if len(argv) != 3:
        print(__doc__.strip())
        return 2
    source, out_path = argv[1], argv[2]
    src = read_source(source)
    old = json.loads(src["MANIFEST.json"].decode("utf-8"))
    if old.get("profile") != PROFILE:
        print("the existing capsule is profile %r, not %s" % (old.get("profile"), PROFILE))
        return 2

    blobs = {}      # path -> bytes, everything except MANIFEST.json
    nodes = []

    # 7.2 the base files: loaders/ and spec/ copied unchanged, superseded versions skipped.
    # Format definitions travel only for the formats the package uses: here zlib-deflate alone.
    def wanted(p):
        if not p.startswith("spec/formats/"):
            return True
        name = p.rsplit("/", 1)[-1]
        return name == ZLIB + ".md" or name.startswith(ZLIB + ".")

    spec_entries = []
    for path in sorted(p for p in src if p.startswith("spec/") and not is_superseded(p) and wanted(p)):
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

    # The reference implementation the zlib-deflate definition names travels as a core.tool
    # node: copied, with its files, from the existing capsule (which uses the format too).
    tool = old_nodes["format-" + ZLIB + "-reference"]
    tool_version = [v for v in tool["versions"] if v["v"] == tool["active"]][0]
    tool_files = []
    for f in tool_version["files"]:
        blobs[f["path"]] = src[f["path"]]
        tool_files.append(dict(f))
    nodes.append(node(tool["node_id"], tool["type"], version(
        tool_files, tool_version["note"], payload_file=tool_version["payload_file"]),
        meta=tool.get("meta")))

    # 7.1 / 7.3 the three document nodes.
    blobs["text/body-000001.json"] = BODY_PAYLOAD
    blobs["text/body-000001.blocks.zlib"] = BLOCKS_FILE
    blobs["preview/text/body-000001.txt.zlib"] = TEXT_PAYLOAD
    blobs["document/document.json"] = DOC_PAYLOAD
    # Two files: the payload (the header) and the blocks file, whose format `meta` declares.
    body_node = node("body-000001", "core.text.blocks", version(
        [file_entry("text/body-000001.json", BODY_PAYLOAD, media_type="application/json", role="payload"),
         file_entry("text/body-000001.blocks.zlib", BLOCKS_FILE, media_type="application/zlib", role="blocks")],
        "The two paragraphs of the minimal document.",
        payload_file="text/body-000001.json"),
        meta={"file_formats": {"blocks": ZLIB}})
    # A derived node (law 5): `measured`, its inputs listed in order, `requires` its input.
    text_node = node("text-000001", "core.preview.text", version(
        [file_entry("preview/text/body-000001.txt.zlib", TEXT_PAYLOAD, media_type="application/zlib")],
        "The plain text of the body, derived from its blocks.",
        epistemic="measured",
        input_files=["text/body-000001.json"],
        input_params=dict(TEXT_PARAMS),
        input_hash=input_hash([sha256(BODY_PAYLOAD)], TEXT_PARAMS)),
        edges=[{"to": "body-000001", "kind": "requires", "role": "extracted-from"}],
        meta={"payload_format": ZLIB})
    # The structure node `enhances` its units: a document with a damaged body run is still a document.
    doc_node = node("document", "core.text.document", version(
        [file_entry("document/document.json", DOC_PAYLOAD, media_type="application/json")], NOTE),
        edges=[{"to": "body-000001", "kind": "enhances", "role": "body"},
               {"to": "text-000001", "kind": "enhances", "role": "plain-text"}])

    # 7.4 the revision record: every node except `revisions`, at version 1.
    uses = {n["node_id"]: 1 for n in nodes}
    for n in (body_node, text_node, doc_node):
        uses[n["node_id"]] = 1
    record = {"schema_version": 1, "revision": 1, "kind": "save", "note": NOTE,
              "created": CREATED, "producer": dict(PRODUCER), "nodes": uses}
    record_bytes = (json.dumps(record, indent=2, sort_keys=True) + chr(10)).encode("utf-8")
    blobs["revisions/revision.json"] = record_bytes
    nodes.append(node("revisions", "core.revisions", version(
        [file_entry("revisions/revision.json", record_bytes, media_type="application/json")], NOTE)))
    nodes.extend([body_node, text_node, doc_node])

    # 7.5 the manifest.
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
        "formats": {ZLIB: old["formats"][ZLIB]},
        "schemas": {t: p for t, p in old["schemas"].items() if t in types},
        "layouts": {t: p for t, p in old.get("layouts", {}).items() if t in types},
        "spec_sha256": spec_sha256(spec_entries),
        "entity": {"uuid": new_uuid(), "name": "Minimal", "created": CREATED,
                   "summary": "Written by write_minimal.py from the embedded specification."},
        "nodes": nodes,
        "generator": dict(PRODUCER),
    }
    manifest_bytes = (json.dumps(manifest, indent=2, ensure_ascii=False) + chr(10)).encode("utf-8")

    # 7.6 the container: store mode, MANIFEST.json first, the preview tier before the rest.
    tier = container["preview_tier"]

    def in_tier(path):
        return any(path.startswith(t) if t.endswith("/") else path == t for t in tier)

    def tier_rank(path):
        for i, t in enumerate(tier):
            if (path.startswith(t) if t.endswith("/") else path == t):
                return i
        return len(tier)

    ordered = sorted(blobs, key=lambda p: (0 if in_tier(p) else 1, tier_rank(p), p.encode("utf-8")))
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_STORED) as z:
        for name, data in [("MANIFEST.json", manifest_bytes)] + [(p, blobs[p]) for p in ordered]:
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 12, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            z.writestr(info, data)
    for line in checkpoints():
        print(line)
    print("wrote %s: %d nodes, %d files, manifest sha256 %s"
          % (out_path, len(nodes), len(blobs), sha256(manifest_bytes)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
