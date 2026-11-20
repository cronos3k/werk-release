#!/usr/bin/env python3
"""read_document.py - read a `vector-art/1` werk capsule with the Python standard library.

It uses NO ArtCraft software and nothing but what spec/PROFILE-VECTOR-ART.md says: it is the
executable form of that document's section 6 ("Reading"). It opens the container (a store-mode
zip or a directory), verifies every file it reads against MANIFEST.json, follows
primary.document to the structure node, reads the artboards, the layers (bottom first), the
symbols, the patterns and the images, and prints the document as one JSON object:

    python read_document.py <capsule: .werk file or directory> [--revision K] [--images DIR]
                            [--originals DIR] [--decode DIR]

    title, units, color_mode
    artboards   [{node, id, name, rect: [x0, y0, x1, y1]}]
    layers      [{node, objects: [<object>...]}]            bottom first
    symbols     [{node, name, objects: [...]}]
    patterns    [{node, name, tile, objects: [...]}]
    images      [{key, node, width, height, bit_depth, color_type, rgba_sha256,
                  original: {node, type, format, definition, bytes, sha256}}]
    fonts       [{family, style, status, source, bytes, sha256}]
    encoded     [{node, type, format, definition, bytes, sha256,
                  decoded: {tool, bytes, sha256} | refused: "<why>"}]     with --decode
    stored_apart [{node, type, role, path, format, definition, bytes, sha256,
                  decoded | refused}]     the compressed file of each payload stored apart
    lost       [{node, reason}]     nodes that are dead, missing or of an unexpected type

An <object> is flattened in tree order (a parent before its children, bottom first):
    {id, depth, type, name, visible, opacity,
     path:  [[["M", x, y], ["C", x1, y1, x2, y2, x, y], ..., ["Z"]], ...]   one list per subpath
     fills / strokes: [<paint summary>]      bottom first
     text:  "..."                            the characters of a type object
     image: "<key>"   symbol: "<name>" }

`rgba_sha256` is the sha256 of the image's pixels as 8-bit RGBA, row by row from the top
(width * height * 4 bytes), decoded here from the PNG with zlib alone. With --images DIR the
PNG of every image is also written to DIR/<node>.png.

`original` is there when the image's own file is carried verbatim in a format the capsule
defines (section 3.2): `format` is the node's meta.payload_format and `definition` the path of
the document, inside the capsule, from which a decoder for it can be written. With
--originals DIR each such file is written to DIR/<node>.

`encoded` lists EVERY payload of the document that is in a foreign format the capsule defines
(an image's own file, a placed document, a font, a colour profile): its node's
meta.payload_format, and the definition MANIFEST.json's `formats` names for it. With
--decode DIR, and only then, the reference decoder the capsule carries for that format (source,
under tools/, named by the definition's own header) is copied to DIR/tools/ and run with this
Python on the payload; what it writes is saved as DIR/<node>.decoded. A payload the definition
does not cover (its coverage note says what it leaves out) is REFUSED by the decoder: `refused`
then holds its message. Nothing here runs unless --decode is given.

Exit status: 0 when everything named was read, 1 when something was lost, 2 when the file is
no readable vector-art/1 capsule.
"""

import hashlib
import json
import os
import struct
import subprocess
import sys
import zipfile
import zlib


class Container:
    """A capsule's files by package-relative path: a directory, or a store-mode zip."""

    def __init__(self, path):
        self.dir = path if os.path.isdir(path) else None
        self.zip = None if self.dir else zipfile.ZipFile(path)

    def read(self, rel):
        if self.dir:
            with open(os.path.join(self.dir, *rel.split("/")), "rb") as fh:
                return fh.read()
        info = self.zip.getinfo(rel)
        if info.compress_type != zipfile.ZIP_STORED:
            raise IOError("%s is not stored (method %d)" % (rel, info.compress_type))
        return self.zip.read(rel)


class Capsule:
    def __init__(self, path, revision=None):
        self.files = Container(path)
        self.manifest = json.loads(self.files.read("MANIFEST.json").decode("utf-8"))
        self.nodes = {n["node_id"]: n for n in self.manifest["nodes"]}
        self.lost = []
        # Which version of which node the document uses: the newest revision record, or record K
        # (spec/CRAFT-BASE.md section 3). Without a readable record: every node's active version.
        self.uses = {i: n["active"] for i, n in self.nodes.items()}
        record = self.revision_record(revision)
        if record is not None:
            self.uses = record["nodes"]

    def revision_record(self, revision):
        node = self.nodes.get("revisions")
        if node is None:
            return None
        want = node["active"] if revision is None else revision
        for version in node["versions"]:
            if version["v"] == want:
                return json.loads(self.verified(version, version["files"][0]).decode("utf-8"))
        raise SystemExit("the file has no revision %s" % want)

    def verified(self, version, entry):
        data = self.files.read(entry["path"])
        if len(data) != entry["size"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise IOError("hash-mismatch: %s" % entry["path"])
        return data

    def payload(self, node_id, node_type):
        """The payload bytes of node `node_id`, which must be of `node_type` and part of the
        revision read; None (and the node listed as lost) otherwise."""
        try:
            node = self.nodes[node_id]
            if not node["type"].startswith(node_type):
                raise IOError("is a %s node, not a %s" % (node["type"], node_type))
            if node_id not in self.uses:
                raise IOError("is not part of this revision")
            version = [v for v in node["versions"] if v["v"] == self.uses[node_id]][0]
            if version.get("compacted"):
                raise IOError("version-compacted")
            files = version["files"]
            # SPEC.md section 2.1: payload_file first, else the single file.
            if "payload_file" in version:
                entry = [f for f in files if f["path"] == version["payload_file"]][0]
            elif len(files) == 1:
                entry = files[0]
            else:
                raise IOError("payload-file-ambiguous")
            return self.verified(version, entry)
        except (KeyError, IndexError, IOError, OSError) as e:
            self.lost.append({"node": node_id, "reason": "%s: %s" % (type(e).__name__, e)})
            return None

    def json(self, node_id, node_type):
        data = self.payload(node_id, node_type)
        if data is None:
            return None
        try:
            value = json.loads(data.decode("utf-8"))
            if isinstance(value, dict) and "external" in value:
                value = json.loads(self.external(node_id, value["external"]).decode("utf-8"))
            return value
        except (ValueError, KeyError, IndexError, IOError, OSError, zlib.error) as e:
            self.lost.append({"node": node_id, "reason": "%s: %s" % (type(e).__name__, e)})
            return None

    def external(self, node_id, external):
        """A payload stored apart (section 3.1): the payload file is a stub; the complete payload
        is what the file of role `external.role`, of the same version of the node, inflates to."""
        if external["format"] != "zlib-deflate":
            raise IOError("the payload is stored as %r, not zlib-deflate" % external["format"])
        node = self.nodes[node_id]
        version = [v for v in node["versions"] if v["v"] == self.uses[node_id]][0]
        entry = [f for f in version["files"] if f.get("role") == external["role"]][0]
        data = zlib.decompress(self.verified(version, entry))
        if len(data) != external["bytes"] or hashlib.sha256(data).hexdigest() != external["sha256"]:
            raise IOError("what %s inflates to is not the payload its stub names" % entry["path"])
        return data


# ---------------------------------------------------------------- PNG pixels (MINI-SPECS section 8)

def png_rgba(data):
    """Decode a non-interlaced PNG -> (width, height, bit_depth, color_type, 8-bit RGBA bytes)."""
    if data[:8] != bytes([137, 80, 78, 71, 13, 10, 26, 10]):
        raise ValueError("not a PNG")
    pos, idat, palette, trns, head = 8, [], None, None, None
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            head = struct.unpack(">IIBBBBB", body)
        elif kind == b"PLTE":
            palette = body
        elif kind == b"tRNS":
            trns = body
        elif kind == b"IDAT":
            idat.append(body)
        elif kind == b"IEND":
            break
    width, height, depth, color, _comp, _filt, interlace = head
    if interlace:
        raise ValueError("interlaced PNGs are not decoded by this script")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
    bpp = max(1, channels * depth // 8)  # bytes per complete pixel, for the filters
    stride = (width * channels * depth + 7) // 8
    raw = zlib.decompress(b"".join(idat))
    rows, prev, at = [], bytearray(stride), 0
    for _ in range(height):
        ftype = raw[at]
        line = bytearray(raw[at + 1:at + 1 + stride])
        at += 1 + stride
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if ftype == 1:
                line[i] = (line[i] + a) & 255
            elif ftype == 2:
                line[i] = (line[i] + b) & 255
            elif ftype == 3:
                line[i] = (line[i] + ((a + b) >> 1)) & 255
            elif ftype == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else (b if pb <= pc else c))) & 255
        rows.append(line)
        prev = line

    def samples(line):
        """The samples of one row as integers 0..2^depth-1."""
        if depth == 8:
            return list(line)
        if depth == 16:
            return [(line[i] << 8) | line[i + 1] for i in range(0, len(line), 2)]
        out = []
        for byte in line:
            for shift in range(8 - depth, -1, -depth):
                out.append((byte >> shift) & ((1 << depth) - 1))
        return out[:width * channels]

    def to8(v):
        # 16-bit samples keep their high byte; smaller depths are scaled to the full range.
        return v >> 8 if depth == 16 else (v * 255) // ((1 << depth) - 1)

    out = bytearray()
    for line in rows:
        s = samples(line)
        for x in range(width):
            px = s[x * channels:(x + 1) * channels]
            if color == 0:
                g = to8(px[0])
                alpha = 0 if trns and len(trns) >= 2 and px[0] == ((trns[0] << 8) | trns[1]) else 255
                out += bytes([g, g, g, alpha])
            elif color == 2:
                alpha = 255
                if trns and len(trns) >= 6 and px == [(trns[i] << 8) | trns[i + 1] for i in (0, 2, 4)]:
                    alpha = 0
                out += bytes([to8(px[0]), to8(px[1]), to8(px[2]), alpha])
            elif color == 3:
                i = px[0]
                out += palette[3 * i:3 * i + 3] + bytes([trns[i] if trns and i < len(trns) else 255])
            elif color == 4:
                g = to8(px[0])
                out += bytes([g, g, g, to8(px[1])])
            else:
                out += bytes([to8(v) for v in px])
    return width, height, depth, color, bytes(out)


# ---------------------------------------------------------------- objects (PROFILE-VECTOR-ART section 4)

def subpath_commands(sub):
    """One subpath as move / curve / close commands: the pseudocode of section 4."""
    anchors = sub["anchors"]
    if not anchors:
        return []
    out = [["M"] + anchors[0]["p"]]
    n = len(anchors)
    for i in range(1, n + (1 if sub.get("closed") else 0)):
        a, b = anchors[i - 1], anchors[i % n]
        out.append(["C"] + a.get("out", a["p"]) + b.get("in", b["p"]) + b["p"])
    if sub.get("closed"):
        out.append(["Z"])
    return out


def paint_summary(paint):
    kind = paint["type"]
    if kind == "solid":
        c = paint["color"]
        return {"type": "solid", "color": [c["model"]] + [c[k] for k in {"rgb": "rgb", "cmyk": "cmyk", "gray": "k", "lab": "lab"}[c["model"]]]}
    if kind == "gradient":
        return {"type": "gradient", "kind": paint["gradient"]["kind"], "stops": len(paint["gradient"]["stops"])}
    if kind == "pattern":
        return {"type": "pattern", "pattern": paint["pattern"]}
    return {"type": "none"}


def flatten(obj, depth, out):
    kind = obj["kind"]
    row = {"id": obj["id"], "depth": depth, "type": kind["type"], "name": obj.get("name"), "visible": obj.get("visible", True), "opacity": obj.get("opacity", 1)}
    items = obj.get("appearance", {}).get("items", [])
    fills = [paint_summary(i["paint"]) for i in items if i["kind"] == "fill"]
    strokes = [dict(paint_summary(i["paint"]), width=i["width"]) for i in items if i["kind"] == "stroke"]
    if fills:
        row["fills"] = fills
    if strokes:
        row["strokes"] = strokes
    if kind["type"] == "path":
        row["path"] = [subpath_commands(s) for s in kind["path"]["subpaths"]]
        row["rule"] = kind.get("rule", "NonZero")
    elif kind["type"] == "text":
        row["text"] = "".join(run["text"] for run in kind["runs"])
        row["fonts"] = sorted({(run["style"]["font_family"], run["style"].get("font_style", "Regular")) for run in kind["runs"]})
    elif kind["type"] in ("image", "placeddocument"):
        row["image"] = kind["key"]
    elif kind["type"] == "symbolinstance":
        row["symbol"] = kind["symbol"]
    out.append(row)
    if obj.get("mask"):
        flatten(obj["mask"]["art"], depth + 1, out)
    for child in kind.get("children", kind.get("content", kind.get("source", []))):
        flatten(child, depth + 1, out)
    return out


# ---------------------------------------------------------------- foreign formats (CRAFT-BASE section 6.1)

def definition_header(markdown):
    """The machine-readable header of a format definition: the JSON of its `werk-format` block."""
    start = markdown.index("```werk-format") + len("```werk-format")
    return json.loads(markdown[start:markdown.index(chr(10) + "```", start)])


def encoded_payloads(cap, decode_dir):
    """Every payload of this revision in a foreign format the capsule defines; decoded, with the
    reference decoder the capsule carries, when `decode_dir` is given."""
    rows = []
    formats = cap.manifest.get("formats", {})
    for node_id in sorted(cap.uses):
        node = cap.nodes.get(node_id)
        fmt = (node or {}).get("meta", {}).get("payload_format")
        if not fmt or node["type"] == "core.tool":
            continue
        data = cap.payload(node_id, node["type"])
        if data is None:
            continue
        row = {"node": node_id, "type": node["type"], "format": fmt, "definition": formats.get(fmt),
               "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        rows.append(row)
        if decode_dir:
            reference_decode(cap, row, data, decode_dir, node_id)
    return rows


def reference_decode(cap, row, data, decode_dir, name):
    """Run the reference decoder the capsule carries for `row["format"]` on `data`; what it prints
    goes to `<decode_dir>/<name>.decoded`. The decoder is the first of the definition's
    `reference_tools`, a file of the capsule; it is run with `python -I` and nothing installed."""
    fmt = row["format"]
    try:
        header = definition_header(cap.files.read(cap.manifest["formats"][fmt]).decode("utf-8"))
        entry = header["reference_tools"][0]["entrypoint"]
        tool_dir = os.path.join(decode_dir, "tools")
        os.makedirs(tool_dir, exist_ok=True)
        tool = os.path.join(tool_dir, entry.split("/")[-1])
        with open(tool, "wb") as fh:
            fh.write(cap.files.read(entry))
        source = os.path.join(decode_dir, name + ".payload")
        with open(source, "wb") as fh:
            fh.write(data)
    except (KeyError, IndexError, ValueError, IOError, OSError) as e:
        row["refused"] = "no reference decoder for `%s` in the capsule: %s" % (fmt, e)
        return
    run = subprocess.run([sys.executable, "-I", tool, source], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if run.returncode != 0:
        row["refused"] = run.stderr.decode("utf-8", "replace").strip() or "exit status %d" % run.returncode
        return
    with open(os.path.join(decode_dir, name + ".decoded"), "wb") as fh:
        fh.write(run.stdout)
    row["decoded"] = {"tool": entry, "bytes": len(run.stdout), "sha256": hashlib.sha256(run.stdout).hexdigest()}


def stored_apart(cap, decode_dir):
    """Every file of this revision that holds a payload stored apart (section 3.1): a file whose
    role the node's `meta.file_formats` gives a format for. With `decode_dir`, inflated by the
    reference decoder the capsule carries (not by this script's own `zlib`)."""
    rows = []
    formats = cap.manifest.get("formats", {})
    for node_id in sorted(cap.uses):
        node = cap.nodes.get(node_id)
        by_role = (node or {}).get("meta", {}).get("file_formats") or {}
        if not by_role:
            continue
        version = [v for v in node["versions"] if v["v"] == cap.uses[node_id]][0]
        for entry in version["files"]:
            fmt = by_role.get(entry.get("role"))
            if not fmt:
                continue
            try:
                data = cap.verified(version, entry)
            except (IOError, OSError, KeyError) as e:
                cap.lost.append({"node": node_id, "reason": "%s: %s" % (type(e).__name__, e)})
                continue
            row = {"node": node_id, "type": node["type"], "role": entry["role"], "path": entry["path"], "format": fmt,
                   "definition": formats.get(fmt), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            rows.append(row)
            if decode_dir:
                reference_decode(cap, row, data, decode_dir, "%s.%s" % (node_id, entry["role"]))
    return rows


def main(argv):
    args, options = [], {"--revision": None, "--images": None, "--originals": None, "--decode": None}
    rest = iter(argv[1:])
    for a in rest:
        if a in options:
            options[a] = next(rest, None)
        else:
            args.append(a)
    if len(args) != 1 or any(a.startswith("--") for a in args):
        print(__doc__.strip())
        return 2
    revision = int(options["--revision"]) if options["--revision"] else None
    images_dir, originals_dir, decode_dir = options["--images"], options["--originals"], options["--decode"]
    try:
        cap = Capsule(args[0], revision)
    except (IOError, OSError, KeyError, ValueError, zipfile.BadZipFile) as e:
        print("not a readable werk capsule: %s" % e, file=sys.stderr)
        return 2
    if cap.manifest.get("profile") != "vector-art/1":
        print("profile is %r, not vector-art/1" % cap.manifest.get("profile"), file=sys.stderr)
        return 2
    conv = cap.manifest["conventions"]
    assert conv["y_axis"] == "down" and conv["length_unit"] == "point" and conv["curve_representation"] == "cubic-bezier-anchors", conv

    doc = cap.json(cap.manifest["primary"]["document"], "core.vector.document")
    if doc is None:
        print(json.dumps({"lost": cap.lost}, indent=1))
        return 1
    out = {"title": doc.get("title", ""), "units": doc.get("units", "Points"), "color_mode": doc.get("color_mode", "Rgb")}
    out["artboards"] = []
    for node_id in doc["artboards"]:
        a = cap.json(node_id, "core.vector.artboard")
        if a is not None:
            r = a["rect"]
            out["artboards"].append({"node": node_id, "id": a["id"], "name": a.get("name", ""), "rect": [r["x0"], r["y0"], r["x1"], r["y1"]]})
    out["layers"] = []
    for node_id in doc["layers"]:
        layer = cap.json(node_id, "core.vector.layer")
        if layer is not None:
            out["layers"].append({"node": node_id, "objects": flatten(layer["layer"], 0, [])})
    out["symbols"] = []
    for entry in doc.get("symbols", []):
        s = cap.json(entry["node"], "core.vector.symbol")
        if s is not None:
            out["symbols"].append({"node": entry["node"], "name": s["name"], "objects": flatten(s["art"], 0, [])})
    out["patterns"] = []
    for entry in doc.get("patterns", []):
        p = cap.json(entry["node"], "core.paint.pattern")
        if p is not None:
            p = p["pattern"]
            t = p["tile"]
            objects = []
            for art in p["art"]:
                flatten(art, 0, objects)
            out["patterns"].append({"node": entry["node"], "name": p["name"], "tile": [t["x0"], t["y0"], t["x1"], t["y1"]], "objects": objects})
    out["images"] = []
    for entry in doc.get("images", []):
        row = {"key": entry["key"]}
        if "original" in entry:
            # The image's own file, verbatim, in a format the capsule defines (section 3.2).
            data = cap.payload(entry["original"], "core.vector.")
            if data is not None:
                node = cap.nodes[entry["original"]]
                fmt = node.get("meta", {}).get("payload_format")
                row["original"] = {"node": entry["original"], "type": node["type"], "format": fmt, "definition": cap.manifest.get("formats", {}).get(fmt),
                                   "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                if originals_dir:
                    os.makedirs(originals_dir, exist_ok=True)
                    with open(os.path.join(originals_dir, entry["original"]), "wb") as fh:
                        fh.write(data)
        png = cap.payload(entry["node"], "core.vector.image") if "node" in entry else None
        if png is not None:
            try:
                w, h, depth, color, rgba = png_rgba(png)
                row.update(node=entry["node"], width=w, height=h, bit_depth=depth, color_type=color, rgba_sha256=hashlib.sha256(rgba).hexdigest())
                if images_dir:
                    os.makedirs(images_dir, exist_ok=True)
                    with open(os.path.join(images_dir, entry["node"] + ".png"), "wb") as fh:
                        fh.write(png)
            except (ValueError, KeyError, IndexError, struct.error, zlib.error) as e:
                cap.lost.append({"node": entry["node"], "reason": "PNG: %s" % e})
        if len(row) > 1:
            out["images"].append(row)
    out["fonts"] = []
    for f in doc.get("fonts", []):
        row = {"family": f["family"], "style": f["style"], "source": f.get("source"),
               "status": f.get("status", "embedded" if f.get("source") else "unknown")}
        if f.get("source"):
            data = cap.payload(f["source"], "")
            if data is not None:
                row.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        out["fonts"].append(row)
    out["encoded"] = encoded_payloads(cap, decode_dir)
    out["stored_apart"] = stored_apart(cap, decode_dir)
    out["lost"] = cap.lost
    sys.stdout.write(json.dumps(out, indent=1, ensure_ascii=False, sort_keys=True))
    sys.stdout.write(chr(10))
    return 1 if cap.lost else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8") if hasattr(sys.stdout, "reconfigure") else None
    sys.exit(main(sys.argv))
