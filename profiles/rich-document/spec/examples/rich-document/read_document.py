#!/usr/bin/env python3
"""read_document.py - read a `rich-document/1` werk capsule with the standard library only.

It uses NO WordCraft or ArtCraft software. It is the executable form of
spec/PROFILE-RICH-DOCUMENT.md section 6 ("Reading"): from MANIFEST.json to the text, the
stories, the pictures - verifying every byte it reads against the manifest's sha256.

    python read_document.py FILE                     a summary: what the document holds
    python read_document.py FILE --text              the body's plain text (section 3.11), recomputed
                                                     from the blocks and compared with the stored one
    python read_document.py FILE --json              everything below as one JSON object
    python read_document.py FILE --extract DIR       text.txt, every picture and every embedded font, into DIR
    python read_document.py FILE --revision K ...    the document as it was at saved revision K

FILE is a .werk file (a store-mode zip) or a capsule directory.

Exit status: 0 everything read; 1 something was damaged or missing (reported, the rest is read);
2 not a rich-document/1 capsule.
"""

import hashlib
import json
import os
import sys
import zipfile
import zlib

PROFILE = "rich-document/1"
OBJ = chr(0xFFFC)  # convention `object_char`: marks an inline object in a paragraph's text
# What reading one node may raise: a missing file, a missing manifest field, bytes that do not
# hash to the manifest's sha256, or - in the zip form - a member whose CRC-32 no longer matches.
UNREADABLE = (OSError, KeyError, IndexError, ValueError, zipfile.BadZipFile, zlib.error)


class Capsule:
    """The container: a directory, or a zip whose members are stored (method 0)."""

    def __init__(self, path):
        self.path = path
        self.zip = None if os.path.isdir(path) else zipfile.ZipFile(path)
        self.manifest = json.loads(self.read("MANIFEST.json").decode("utf-8"))
        self.nodes = {n["node_id"]: n for n in self.manifest["nodes"]}
        self.problems = []

    def read(self, path):
        if self.zip is not None:
            return self.zip.read(path)
        with open(os.path.join(self.path, *path.split("/")), "rb") as fh:
            return fh.read()

    def revisions(self):
        """The revision records, oldest first (spec/CRAFT-BASE.md section 3)."""
        node = self.nodes.get("revisions")
        out = []
        for ver in (node or {}).get("versions", []):
            try:
                out.append(json.loads(self.checked(ver["files"][0]).decode("utf-8")))
            except UNREADABLE as e:
                self.problems.append("revision record %s: %s" % (ver.get("v"), e))
        return out

    def checked(self, entry):
        """The bytes of one files[] entry, verified against its sha256 and size."""
        data = self.read(entry["path"])
        if len(data) != entry["size"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError("hash-mismatch: %s" % entry["path"])
        return data

    def version(self, node_id, uses):
        """The version of `node_id` the document uses: uses[node_id], else its `active`."""
        node = self.nodes[node_id]
        wanted = uses.get(node_id, node["active"])
        for ver in node["versions"]:
            if ver["v"] == wanted:
                if "compacted" in ver:
                    raise ValueError("version-compacted: %s v%d" % (node_id, wanted))
                return ver
        raise ValueError("node %s has no version %s" % (node_id, wanted))

    def payload_entry(self, ver):
        """Which file IS the payload (spec/SPEC.md section 2.1): `payload_file`, else the one
        file, else the file with role `payload`. Never "the first"."""
        files = ver["files"]
        if "payload_file" in ver:
            # (A superseded version's files, and its `payload_file`, carry an `@N` marker.)
            return [f for f in files if strip_marker(f["path"]) == strip_marker(ver["payload_file"])][0]
        if len(files) == 1:
            return files[0]
        return [f for f in files if f.get("role") == "payload"][0]

    def payload(self, node_id, uses):
        return self.checked(self.payload_entry(self.version(node_id, uses)))

    def file_with_role(self, node_id, uses, role):
        ver = self.version(node_id, uses)
        return self.checked([f for f in ver["files"] if f.get("role") == role][0])

    def blocks(self, node_id, uses):
        """A core.text.blocks node: (its story, its blocks). The payload is a small JSON header;
        the blocks are in the node's file with role `blocks`, one zlib stream (RFC 1950) whose
        inflated bytes are a JSON array. The header says what the inflated bytes must be."""
        header = json.loads(self.payload(node_id, uses).decode("utf-8"))
        about = header["blocks"]
        stored = self.file_with_role(node_id, uses, about["role"])
        inflated = zlib.decompress(stored)
        if len(inflated) != about["inflated_size"] or hashlib.sha256(inflated).hexdigest() != about["inflated_sha256"]:
            raise ValueError("hash-mismatch: the blocks file of %s does not inflate to what its header says" % node_id)
        return header["story"], json.loads(inflated.decode("utf-8"))


def strip_marker(path):
    """A path without its `@N` version marker (spec/CRAFT-BASE.md section 4)."""
    head, _, name = path.rpartition("/")
    if "@" in name:
        stem, _, tail = name.rpartition("@")
        digits, dot, ext = tail.partition(".")
        if digits.isdigit():
            name = stem + dot + ext
    return (head + "/" if head else "") + name


# ---- section 3.11: the plain text of a list of blocks ---------------------------------------

def object_text(obj):
    """What an inline object contributes to the plain text."""
    kind = obj.get("type")
    if kind == "field":
        return obj.get("result", "")
    if kind == "equation":
        return obj.get("linear", "")
    if kind == "ruby":
        return obj.get("base", "")
    if kind == "opaque":
        return obj.get("text", "")
    return ""


def is_control(ch):
    code = ord(ch)
    return code < 0x20 or 0x7F <= code <= 0x9F


def clean(text):
    out = []
    for ch in text:
        if ch in (chr(0x0C), chr(0x0E)):        # page break, column break
            out.append(chr(10))
        elif ch in (chr(10), chr(9)) or not is_control(ch):
            out.append(ch)
    return "".join(out)


def paragraph_text(block):
    objects = block.get("objects", [])
    out, k = [], 0
    for ch in block.get("text", ""):
        if ch == OBJ:
            if k < len(objects):
                out.append(clean(object_text(objects[k])))
            k += 1
        else:
            out.append(clean(ch))
    return "".join(out)


def plain_text(blocks, depth=0):
    if depth > 16:
        return ""
    out = []
    for block in blocks:
        if block.get("kind") == "table":
            for row in block.get("rows", []):
                cells = []
                for cell in row.get("cells", []):
                    inner = plain_text(cell.get("blocks", []), depth + 1)
                    cells.append(inner.rstrip(chr(10)).replace(chr(10), " "))
                out.append(chr(9).join(cells) + chr(10))
        else:
            out.append(paragraph_text(block) + chr(10))
    return "".join(out)


def outline(blocks):
    """The blocks as a stranger sees them: paragraphs with their text and style, tables as rows."""
    out = []
    for block in blocks:
        if block.get("kind") == "table":
            out.append({"kind": "table", "rows": [
                [plain_text(c.get("blocks", []), 1).rstrip(chr(10)) for c in row.get("cells", [])]
                for row in block.get("rows", [])]})
        else:
            entry = {"kind": "para", "text": block.get("text", "")}
            style = block.get("props", {}).get("style")
            if style is not None:
                entry["style"] = style
            if block.get("objects"):
                entry["objects"] = [o.get("type") for o in block["objects"]]
            out.append(entry)
    return out


def graphics(blocks, out, depth=0):
    """Every chart and diagram object of the blocks, tables included, in reading order."""
    if depth > 16:
        return
    for block in blocks:
        if block.get("kind") == "table":
            for row in block.get("rows", []):
                for cell in row.get("cells", []):
                    graphics(cell.get("blocks", []), out, depth + 1)
        else:
            out.extend(o.get("graphic", {}) for o in block.get("objects", []) if o.get("type") == "graphic")


def chart_of(graphic, chart_data):
    """What a chart plots (sections 3.10 and 3.15): from the object's own `chart`, else from the
    entry of the chart-data node whose `source` is the object's `ooxmlSource`."""
    own = graphic.get("chart")
    if own is not None:
        categories = own.get("categories", [])
        return {"data_from": "object", "type": own.get("type"), "title": own.get("title"),
                "series": [{"name": x.get("name", ""), "categories": categories, "values": x.get("values", [])}
                           for x in own.get("series", [])]}
    entry = chart_data.get(graphic.get("ooxmlSource"))
    if entry is not None:
        return {"data_from": "chart-data", "type": entry["type"], "title": entry.get("title"),
                "series": [{"name": x["name"], "categories": x["categories"], "values": x["values"]} for x in entry["series"]]}
    return {"data_from": None, "type": None, "title": None, "series": []}


# ---- section 6: reading ---------------------------------------------------------------------

def read(path, revision=None):
    cap = Capsule(path)
    m = cap.manifest
    if m.get("profile") != PROFILE:
        raise SystemExit(2)
    records = cap.revisions()
    if revision is None:
        record = records[-1] if records else None
    else:
        found = [r for r in records if r.get("revision") == revision]
        if not found:
            print("no revision %s (the file holds %d)" % (revision, len(records)))
            raise SystemExit(2)
        record = found[0]
    uses = dict(record["nodes"]) if record else {}
    out = {"profile": m["profile"], "uuid": m["entity"]["uuid"], "name": m["entity"]["name"],
           "revision": record["revision"] if record else None, "revisions": len(records),
           "note": record["note"] if record else None, "dead": [], "skipped": []}

    def get(node_id, what):
        try:
            return cap.payload(node_id, uses)
        except UNREADABLE as e:
            out["dead"].append(node_id)
            cap.problems.append("%s (%s): %s" % (what, node_id, e))
            return None

    def get_json(node_id, what):
        data = get(node_id, what)
        return None if data is None else json.loads(data.decode("utf-8"))

    def get_blocks(node_id, what):
        try:
            return cap.blocks(node_id, uses)
        except UNREADABLE as e:
            out["dead"].append(node_id)
            cap.problems.append("%s (%s): %s" % (what, node_id, e))
            return None

    structure = get_json(m["primary"]["document"], "the document structure")
    if structure is None:
        out["problem"] = "the structure node is unreadable; see section 3 for rebuilding from the other nodes"
        out["problems"] = cap.problems
        return out, cap

    # The body: the blocks of the listed nodes, concatenated in the listed order.
    body = []
    for node_id in structure["body"]:
        v = get_blocks(node_id, "a part of the body text")
        if v is None:
            body.append({"kind": "para", "text": "[node %s could not be read]" % node_id})
        else:
            body.extend(v[1])
    out["body"] = outline(body)
    drawn = []
    graphics(body, drawn)
    out["plain_text"] = plain_text(body)
    stored = []
    for node_id in structure.get("plainText", []):
        # Each plain-text node is one zlib stream of UTF-8 text.
        data = None if node_id is None else get(node_id, "derived plain text")
        stored.append("" if data is None else zlib.decompress(data).decode("utf-8"))
    out["stored_plain_text"] = "".join(stored) if "plainText" in structure else None

    # The secondary stories: each node says what it is in `story`.
    out["stories"] = []
    for node_id in structure["stories"] + structure["noteSeparators"]:
        v = get_blocks(node_id, "a story")
        if v is not None:
            story = dict(v[0])
            story.pop("textBody", None)
            story["text"] = plain_text(v[1])
            out["stories"].append(story)
            graphics(v[1], drawn)

    # Charts and diagrams: a chart's data is in its own object or in the chart-data node; a
    # diagram's text is in the `text` items of what it draws.
    chart_data = {}
    if structure.get("chartData"):
        v = get_json(structure["chartData"], "the data of the charts")
        chart_data = {} if v is None else {entry["source"]: entry for entry in v["charts"]}
    out["charts"] = [chart_of(g, chart_data) for g in drawn if g.get("kind") == "chart"]
    out["diagrams"] = [{"text": [i["text"] for i in g.get("items", []) if i.get("type") == "text"]}
                       for g in drawn if g.get("kind") == "diagram"]

    # The pictures: the original where a core node holds it, else the PNG.
    out["media"] = []
    for entry in structure["media"]:
        item = {"key": entry["key"], "mediaType": entry["mediaType"], "bytes": None, "sha256": None, "from": None}
        source = entry.get("original") or (entry["image"] if entry["imageIs"] == "original" else None)
        tries = [(source, "original")] if source else []
        if entry["imageIs"] == "rendition":
            tries.append((entry["image"], "png-rendition"))
        for node_id, how in tries:
            data = get(node_id, "the picture %s" % entry["key"])
            if data is not None:
                item.update({"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "from": how, "node": node_id})
                item["_data"] = data
                break
        out["media"].append(item)

    # The fonts: the files of the embedded faces are in the package; the others are names.
    out["fonts"] = []
    font_data = {}
    for row in structure.get("fonts", []):
        item = {k: row[k] for k in ("family", "style", "status", "use")}
        if row["status"] == "embedded":
            data = font_data.get(row["node"])
            if data is None:
                data = get(row["node"], "the font %s %s" % (row["family"], row["style"]))
                font_data[row["node"]] = data
            if data is not None:
                item.update({"node": row["node"], "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                             "faceIndex": row.get("faceIndex", 0)})
        out["fonts"].append(item)
    out["_fonts"] = font_data

    # The parts of the package the document came from (a .docx), kept verbatim: only a reader
    # that writes that format needs them.
    out["package_parts"] = []
    for row in structure.get("packageParts", []):
        node = cap.nodes.get(row["node"])
        item = {"name": row["name"], "role": row["role"], "type": node["type"] if node else None, "bytes": None, "sha256": None}
        data = get(row["node"], "the package part %s" % row["name"]) if node else None
        if data is not None:
            item.update({"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        out["package_parts"].append(item)

    # Extension nodes hold the originals of pictures in an encoding without a definition here.
    # A reader may skip them; this one reads their descriptors to name what they hold.
    out["extension_originals"] = {}
    for node_id in sorted(uses):
        node = cap.nodes.get(node_id)
        if node is None or not node["type"].startswith("x.wordcraft.source."):
            continue
        try:
            descriptor = json.loads(cap.file_with_role(node_id, uses, "descriptor").decode("utf-8"))
            data = cap.payload(node_id, uses)
            out["extension_originals"][descriptor["mediaKey"]] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "node": node_id}
        except UNREADABLE as e:
            out["dead"].append(node_id)
            cap.problems.append("%s: %s" % (node_id, e))

    for key, what in (("styles", "styles"), ("numbering", "numbering"), ("settings", "settings"),
                      ("properties", "properties"), ("comments", "comments"),
                      ("trackedChanges", "tracked changes"), ("bibliography", "bibliography")):
        if structure.get(key):
            v = get_json(structure[key], what)
            if v is None:
                continue
            if key == "styles":
                out["styles"] = [s.get("id", "") for s in v["styles"]]
            elif key == "properties":
                out["title"] = v["core"].get("title", "")
                out["author"] = v["core"].get("creator", "")
            elif key == "comments":
                out["comments"] = len(v["comments"])
            elif key == "trackedChanges":
                out["tracked_changes"] = len(v["changes"])
            elif key == "bibliography":
                out["sources"] = len(v["sources"])
            elif key == "numbering":
                out["lists"] = len(v["nums"])
    known = ("core.text.", "core.style.", "core.media.", "core.preview.", "core.package.", "core.chart.", "x.wordcraft.")
    base = ("core.spec", "core.loader", "core.license", "core.readme", "core.revisions", "core.tool")
    for node_id in sorted(uses):
        node = cap.nodes.get(node_id)
        if node is not None and not node["type"].startswith(known) and node["type"] not in base:
            out["skipped"].append(node_id)
    out["dead"] = sorted(set(out["dead"]))
    out["signature"] = "unverified" if has_signature(cap) else "absent"
    out["problems"] = cap.problems
    return out, cap


def has_signature(cap):
    try:
        cap.read("SIGNATURE.json")
        return True
    except (OSError, KeyError):
        return False


def main(argv):
    args = argv[1:]
    revision = None
    if "--revision" in args:
        i = args.index("--revision")
        revision = int(args[i + 1])
        del args[i:i + 2]
    extract = None
    if "--extract" in args:
        i = args.index("--extract")
        extract = args[i + 1]
        del args[i:i + 2]
    flags = [a for a in args if a.startswith("--")]
    files = [a for a in args if not a.startswith("--")]
    if len(files) != 1:
        print(__doc__.strip())
        return 2
    out, _cap = read(files[0], revision)
    media_data = {m["key"]: m.pop("_data", None) for m in out.get("media", [])}
    font_data = out.pop("_fonts", {})
    if extract is not None:
        os.makedirs(extract, exist_ok=True)
        with open(os.path.join(extract, "text.txt"), "wb") as fh:
            fh.write(out.get("plain_text", "").encode("utf-8"))
        for i, m in enumerate(out.get("media", [])):
            if media_data.get(m["key"]) is not None:
                ext = "png" if m["from"] == "png-rendition" else m["mediaType"].rsplit("/", 1)[-1]
                with open(os.path.join(extract, "picture-%d.%s" % (i + 1, ext)), "wb") as fh:
                    fh.write(media_data[m["key"]])
        for node_id, data in sorted(font_data.items()):
            if data is not None:
                ext = "ttc" if data[:4] == b"ttcf" else "otf" if data[:4] == b"OTTO" else "ttf"
                with open(os.path.join(extract, "%s.%s" % (node_id, ext)), "wb") as fh:
                    fh.write(data)
    if "--json" in flags:
        sys.stdout.buffer.write((json.dumps(out, indent=1, sort_keys=True, ensure_ascii=False) + chr(10)).encode("utf-8"))
    elif "--text" in flags:
        sys.stdout.buffer.write(out.get("plain_text", "").encode("utf-8"))
        stored = out.get("stored_plain_text")
        if stored is not None:
            same = stored == out["plain_text"]
            sys.stderr.write("stored plain text: %s the text recomputed from the blocks\n" % ("equals" if same else "DIFFERS FROM"))
    else:
        print("%s  \"%s\"  uuid %s" % (out["profile"], out["name"], out["uuid"]))
        print("revision %s of %s: %s" % (out["revision"], out["revisions"], out["note"]))
        if "body" in out:
            paragraphs = sum(1 for b in out["body"] if b["kind"] == "para")
            print("body: %d paragraph(s), %d table(s), %d character(s) of plain text"
                  % (paragraphs, len(out["body"]) - paragraphs, len(out["plain_text"])))
            for s in out["stories"]:
                print("story: %s %s: %s" % (s["kind"], s.get("id", s.get("role", "")), s["text"].strip()[:60]))
            for m in out["media"]:
                print("picture: %s (%s), %s bytes, read from %s" % (m["key"], m["mediaType"], m["bytes"], m["from"]))
            for c in out["charts"]:
                print("chart: %s%s, %d series, data read from %s"
                      % (c["type"], " \"%s\"" % c["title"] if c["title"] else "", len(c["series"]), c["data_from"] or "nowhere (drawing only)"))
            for d in out["diagrams"]:
                print("diagram: %d piece(s) of text: %s" % (len(d["text"]), "; ".join(d["text"])[:60]))
            for f in out["fonts"]:
                print("font: %s %s - %s%s" % (f["family"], f["style"], f["status"],
                                              ", %s bytes in the file" % f["bytes"] if f.get("bytes") else ""))
        print("signature: %s" % out["signature"])
    for p in out.get("problems", []):
        sys.stderr.write("PROBLEM: %s\n" % p)
    return 1 if out.get("problems") else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
