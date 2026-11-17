#!/usr/bin/env python3
"""read_presentation.py - read a `presentation/1` werk capsule.

Python standard library only; no presentation software and no werk software. It is written
from spec/PROFILE-PRESENTATION.md section 6 ("Reading"), spec/CRAFT-BASE.md and the JSON
Schemas under spec/schemas/, and from nothing else.

    python read_presentation.py <capsule: .werk file or directory>
        lists the slides: number, title, how many shapes, the layout
    python read_presentation.py <capsule> --text
        prints the text of every slide (titles, body text by outline level, tables, notes)
    python read_presentation.py <capsule> --json out.json
        writes everything this reader understands as one JSON document (see `summary`)
    python read_presentation.py <capsule> --media DIR
        writes every embedded file to DIR, byte for byte, as <media id>.<extension>
    python read_presentation.py <capsule> --revision K ...
        the same for the document as it was at revision K (every Save is kept in the file)

Exit status: 0 = read with nothing lost; 1 = read, and at least one node was damaged or
missing (it is named on standard error and under "lost"); 2 = not a readable capsule.
"""

import hashlib
import json
import os
import re
import sys
import zipfile

PROFILE = "presentation/1"


class Refusal(Exception):
    """A container-scoped refusal: nothing can be read."""


class Capsule:
    """The container (spec/SPEC.md section 1): a directory, or the same tree as a store-mode zip."""

    def __init__(self, path):
        self.path = path
        self.zip = None
        if os.path.isdir(path):
            if not os.path.isfile(os.path.join(path, "MANIFEST.json")):
                raise Refusal("bad-container: no MANIFEST.json in the directory")
        else:
            try:
                self.zip = zipfile.ZipFile(path)
            except (zipfile.BadZipFile, OSError) as e:
                raise Refusal("bad-container: %s" % e)
            if any(i.compress_type != zipfile.ZIP_STORED for i in self.zip.infolist()):
                # Standard-library zipfile would inflate them; the format is store mode, and a
                # reader that supports less says so rather than guessing.
                raise Refusal("zip-entry-unsupported: a member is not stored (method 0)")
        try:
            self.manifest = json.loads(self.read("MANIFEST.json").decode("utf-8"))
        except (KeyError, OSError, ValueError) as e:
            raise Refusal("bad-manifest: %s" % e)
        self.nodes = {n["node_id"]: n for n in self.manifest.get("nodes", [])}

    def read(self, path):
        if self.zip is not None:
            return self.zip.read(path)
        with open(os.path.join(self.path, *path.split("/")), "rb") as fh:
            return fh.read()


def logical(path):
    """The stable name of a file within its node: the path with any `@<digits>` version
    marker removed from the file name (spec/CRAFT-BASE.md section 4)."""
    head, _, name = path.rpartition("/")
    name = re.sub(r"@\d+(?=\.[^.@]*$|$)", "", name)
    return (head + "/" if head else "") + name


class Document:
    """One revision of the document: which version of which node belongs to it."""

    def __init__(self, capsule, revision=None):
        self.capsule = capsule
        self.lost = []       # node ids that could not be read
        self.notes = []      # one sentence per loss
        self.versions = None
        self.revision = 0
        self.latest = 0
        log = capsule.nodes.get("revisions")
        if log is not None:
            self.latest = log.get("active", 0)
            wanted = self.latest if revision is None else revision
            record = self._record(log, wanted)
            nodes = None
            if record is not None and "nodes" in record:
                nodes = dict(record["nodes"])
            elif record is not None and "base" in record:
                # A delta record: the nodes of an earlier FULL record, with `changed` laid
                # over them and `removed` taken out.
                base = self._record(log, record["base"])
                if base is not None and "nodes" in base and record["base"] < record["revision"]:
                    nodes = dict(base["nodes"])
                    nodes.update(record.get("changed", {}))
                    for gone in record.get("removed", []):
                        nodes.pop(gone, None)
                else:
                    self.notes.append("the revision record %d is a delta whose base record %r is not a readable full record"
                                      % (wanted, record["base"]))
            if nodes is not None:
                self.versions = nodes
                self.revision = record["revision"]
            elif revision is not None:
                raise Refusal("this capsule has no readable revision %d" % revision)
        if self.versions is None:
            # No revision log: every node's active version is the document.
            self.versions = {n["node_id"]: n["active"] for n in capsule.manifest["nodes"]}
            self.notes.append("no revision log was read; the active version of every node was used")

    def _record(self, log, wanted):
        """Record `wanted` of the revision log, or None (with a note) when it cannot be read."""
        for v in log["versions"]:
            if v["v"] == wanted:
                try:
                    return json.loads(self._verified(v["files"][0]).decode("utf-8"))
                except Exception as e:  # the record is damaged: the caller falls back
                    self.notes.append("the revision record %d could not be read (%s)" % (wanted, e))
        return None

    def _verified(self, entry):
        data = self.capsule.read(entry["path"])
        if len(data) != entry["size"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError("hash-mismatch: %s" % entry["path"])
        return data

    def version(self, node_id):
        node = self.capsule.nodes.get(node_id)
        if node is None or node_id not in self.versions:
            raise KeyError("node `%s` is not part of this revision" % node_id)
        for v in node["versions"]:
            if v["v"] == self.versions[node_id]:
                if v.get("compacted"):
                    raise ValueError("version-compacted: `%s` v%d" % (node_id, v["v"]))
                return node, v
        raise KeyError("node `%s` has no version %d" % (node_id, self.versions[node_id]))

    def payload_entry(self, node_id):
        """spec/SPEC.md section 2.1: `payload_file` first; else the single file; never files[0]."""
        _node, v = self.version(node_id)
        if "payload_file" in v:
            return next(f for f in v["files"] if f["path"] == v["payload_file"])
        if len(v["files"]) == 1:
            return v["files"][0]
        marked = [f for f in v["files"] if f.get("role") == "payload"]
        if len(marked) == 1:
            return marked[0]
        raise ValueError("payload-file-ambiguous: node `%s`" % node_id)

    def payload(self, node_id, node_type):
        node, _v = self.version(node_id)
        if node["type"] != node_type:
            raise ValueError("node `%s` is a %s, expected %s" % (node_id, node["type"], node_type))
        return self._verified(self.payload_entry(node_id))

    def json(self, node_id, node_type):
        return json.loads(self.payload(node_id, node_type).decode("utf-8"))

    def file_with_role(self, node_id, role):
        _node, v = self.version(node_id)
        with_role = [f for f in v["files"] if f.get("role") == role]
        if len(with_role) != 1:
            raise ValueError("node `%s` does not have exactly one file with role `%s`" % (node_id, role))
        return with_role[0], self._verified(with_role[0])

    def lose(self, node_id, why, consequence):
        if node_id not in self.lost:
            self.lost.append(node_id)
            self.notes.append("%s (node `%s`: %s)" % (consequence, node_id, why))


# ---------------------------------------------------------------- the content

def run_text(run):
    kind = run.get("kind", {"kind": "text"})["kind"]
    return "\u000b" if kind == "break" else run.get("text", "")


def paragraphs(body):
    """A text body as [{level, runs: [{text, kind}]}]."""
    out = []
    for p in (body or {}).get("paragraphs", []):
        runs = [{"text": r.get("text", ""), "kind": r.get("kind", {"kind": "text"})["kind"]} for r in p.get("runs", [])]
        out.append({"level": p.get("level", 0), "runs": runs})
    return out


def plain(body):
    """The characters of a text body: paragraphs joined by a line feed, a break run as U+000B."""
    return "\n".join("".join(run_text(r) for r in p.get("runs", [])) for p in (body or {}).get("paragraphs", []))


def shape_summary(shape):
    kind = shape.get("kind", {"type": "shape"})
    geom = shape.get("geom", {"kind": "preset", "name": "rect"})
    box = shape.get("xfrm")
    out = {
        "id": shape.get("id", 0),
        "name": shape.get("name", ""),
        "type": kind["type"],
        "box": None if box is None else [box.get("x", 0.0), box.get("y", 0.0), box.get("w", 0.0), box.get("h", 0.0)],
        "placeholder": (shape.get("ph") or {}).get("kind", "body") if shape.get("ph") is not None else None,
        "geometry": geom.get("name") if geom["kind"] == "preset" else "custom",
        "text": None if shape.get("text") is None else paragraphs(shape["text"]),
    }
    t = kind["type"]
    if t == "picture":
        out["media"] = kind["fill"].get("media", 0)
    elif t == "group":
        out["children"] = [shape_summary(c) for c in kind["children"]]
    elif t == "table":
        out["table"] = [[plain(c.get("text")) for c in row.get("cells", [])] for row in kind.get("rows", [])]
        # A cell covered by a merged neighbour is present in the row and draws nothing.
        out["table_covered"] = [[bool(c.get("h_merge") or c.get("v_merge")) for c in row.get("cells", [])] for row in kind.get("rows", [])]
    elif t == "chart":
        out["chart"] = {
            "kind": kind.get("kind", "column"),
            "title": kind["title"],
            "categories": kind.get("categories", []),
            "series": [{"name": s.get("name", ""), "values": s.get("values", [])} for s in kind.get("series", [])],
        }
    elif t == "media":
        out["media"] = kind.get("media", 0)
        out["video"] = kind.get("video", False)
    elif t == "ink":
        out["strokes"] = len(kind["strokes"])
    elif t == "opaque":
        out["label"] = kind["label"]
    return out


def slide_title(slide):
    """The text of the first top-level title placeholder, line breaks as spaces."""
    for shape in slide.get("shapes", []):
        ph = shape.get("ph")
        if ph is not None and ph.get("kind", "body") in ("title", "ctrTitle"):
            return plain(shape.get("text")).replace("\u000b", " ")
    return ""


def master_summary(doc, entry, role_expected):
    payload = doc.json(entry["node"], "core.slide.master")
    master = payload["master"]
    theme = master.get("theme", {})
    colors = ["%02X%02X%02X%02X" % (c["r"], c["g"], c["b"], c["a"]) for c in theme.get("colors", {}).get("colors", [])]
    layouts = []
    for l in entry["layouts"]:
        try:
            layout = doc.json(l["node"], "core.slide.layout")["layout"]
            layouts.append({"id": layout.get("id", 0), "node": l["node"], "name": layout.get("name", ""), "kind": layout.get("kind", "titleAndContent"),
                            "shapes": len(layout.get("shapes", []))})
        except Exception as e:
            doc.lose(l["node"], e, "A layout was not read")
    return {"id": master.get("id", 0), "node": entry["node"], "role": payload.get("role", role_expected), "name": master.get("name", ""),
            "theme": theme.get("name"), "colors": colors, "shapes": len(master.get("shapes", [])), "layouts": layouts}


def summary(doc):
    """Everything this reader understands, as one JSON-able object."""
    capsule = doc.capsule
    manifest = capsule.manifest
    if manifest.get("profile") != PROFILE:
        raise Refusal("unsupported-profile: this capsule is `%s`, not `%s`" % (manifest.get("profile"), PROFILE))
    structure_id = manifest.get("primary", {}).get("document", "document")
    try:
        structure = doc.json(structure_id, "core.slide.document")
    except Exception as e:
        raise Refusal("the structure node `%s` could not be read: %s" % (structure_id, e))

    masters = []
    layout_names = {}
    for entry, role in [(m, "slide") for m in structure["masters"]] + [(structure.get(k), r) for k, r in (("notes_master", "notes"), ("handout_master", "handout")) if structure.get(k)]:
        try:
            m = master_summary(doc, entry, role)
        except Exception as e:
            doc.lose(entry["node"], e, "A master was not read, and with it its layouts")
            continue
        masters.append(m)
        if m["role"] == "slide":
            for l in m["layouts"]:
                layout_names.setdefault(l["id"], l["name"])   # the first layout with an id is the one meant

    slides = []
    first = structure.get("first_slide_number", 1)
    for position, entry in enumerate(structure["slides"]):
        try:
            slide = doc.json(entry["node"], "core.slide.slide")["slide"]
        except Exception as e:
            doc.lose(entry["node"], e, "Slide %d was not read" % (position + 1))
            continue
        transition = slide.get("transition")
        slides.append({
            "id": slide.get("id", 0),
            "node": entry["node"],
            "position": position,
            "number": position + first,
            "name": slide.get("name", ""),
            "hidden": slide.get("hidden", False),
            "layout": slide.get("layout", 0),
            "layout_name": layout_names.get(slide.get("layout", 0)),
            "title": slide_title(slide),
            "shapes": [shape_summary(s) for s in slide.get("shapes", [])],
            "notes": paragraphs(slide.get("notes")),
            "transition": None if transition is None else transition.get("kind", "none"),
            "animations": [{"shape": a.get("shape", 0), "class": a.get("class", "entrance"), "effect": a.get("effect", "fade"), "start": a.get("start", "onClick")}
                           for a in slide.get("animations", [])],
            "comments": [{"author": c.get("author", ""), "text": c.get("text", ""), "replies": len(c.get("replies", []))} for c in slide.get("comments", [])],
        })

    media = []
    for entry in structure.get("media", []):
        try:
            asset = doc.json(entry["node"], "core.media.asset")
            size, digest = 0, None
            if asset["embedded"]:
                f, data = doc.file_with_role(entry["node"], "media")
                size, digest = len(data), hashlib.sha256(data).hexdigest()
        except Exception as e:
            doc.lose(entry["node"], e, "Embedded file %s was not read" % entry["id"])
            continue
        media.append({"id": asset["id"], "node": entry["node"], "name": asset["name"], "content_type": asset["content_type"], "encoding": asset["encoding"],
                      "definition": asset["definition"], "embedded": asset["embedded"], "size": size, "sha256": digest,
                      "rendition": entry.get("rendition") is not None, "poster": entry.get("poster") is not None, "excerpt": entry.get("excerpt") is not None})

    size = structure["slide_size"]
    return {
        "profile": manifest["profile"],
        "entity": manifest["entity"]["uuid"],
        "revision": doc.revision,
        "latest_revision": doc.latest,
        "title": structure.get("props", {}).get("title", ""),
        "slide_size": [size["width"], size["height"]],
        "first_slide_number": first,
        "slides": slides,
        "masters": masters,
        "media": media,
        "sections": [{"name": s.get("name", ""), "slides": s.get("slides", [])} for s in structure.get("sections", [])],
        "lost": sorted(doc.lost),
    }


def clean(text):
    """Text inside one line of the outline (PROFILE-PRESENTATION.md section 3.6)."""
    return "".join(" " if c in "\n\r\t\u000b" else ("\ufffd" if ord(c) < 0x20 or 0x7f <= ord(c) <= 0x9f else c) for c in text)


def write_text(out, s):
    for slide in s["slides"]:
        out.write("Slide %d: %s\n" % (slide["position"] + 1, clean(slide["title"])))

        def walk(shapes, depth):
            for shape in shapes:
                if not (depth == 0 and shape["placeholder"] in ("title", "ctrTitle")):
                    for p in shape["text"] or []:
                        text = "".join("\u000b" if r["kind"] == "break" else r["text"] for r in p["runs"])
                        if text:
                            out.write("\t" * (min(p["level"], 8) + 1) + clean(text) + "\n")
                if shape["type"] == "group":
                    walk(shape["children"], depth + 1)
                if shape["type"] == "table":
                    for row, covered in zip(shape["table"], shape["table_covered"]):
                        cells = [clean(c) for c, hidden in zip(row, covered) if not hidden]
                        if any(c.strip() for c in cells):
                            out.write("\t" + " | ".join(cells) + "\n")

        walk(slide["shapes"], 0)
        for p in slide["notes"]:
            text = "".join("\u000b" if r["kind"] == "break" else r["text"] for r in p["runs"])
            if text:
                out.write("Notes: " + clean(text) + "\n")
        out.write("\n")


def extract_media(doc, s, directory):
    os.makedirs(directory, exist_ok=True)
    written = []
    for m in s["media"]:
        if not m["embedded"]:
            continue
        entry, data = doc.file_with_role(m["node"], "media")
        ext = logical(entry["path"]).rsplit(".", 1)[-1]
        target = os.path.join(directory, "%d.%s" % (m["id"], ext))
        with open(target, "wb") as fh:
            fh.write(data)
        written.append(target)
    return written


def main(argv):
    args = argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 2
    path, rest = args[0], args[1:]
    revision, json_out, media_dir, text = None, None, None, False
    while rest:
        flag = rest.pop(0)
        if flag == "--revision" and rest:
            revision = int(rest.pop(0))
        elif flag == "--json" and rest:
            json_out = rest.pop(0)
        elif flag == "--media" and rest:
            media_dir = rest.pop(0)
        elif flag == "--text":
            text = True
        else:
            print("unknown or incomplete option %s" % flag, file=sys.stderr)
            return 2
    try:
        doc = Document(Capsule(path), revision)
        s = summary(doc)
    except Refusal as e:
        print(str(e), file=sys.stderr)
        return 2
    if json_out is not None:
        with open(json_out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(s, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
    if media_dir is not None:
        for target in extract_media(doc, s, media_dir):
            print("wrote %s" % target)
    out = sys.stdout
    if hasattr(out, "reconfigure"):
        out.reconfigure(encoding="utf-8", newline="\n")
    if text:
        write_text(out, s)
    elif json_out is None and media_dir is None:
        out.write("%s  (revision %d of %d, %d x %d points)\n" % (s["title"] or "(untitled)", s["revision"], s["latest_revision"], s["slide_size"][0], s["slide_size"][1]))
        for slide in s["slides"]:
            out.write("  %3d  %-40s  %2d shape(s)  layout %s\n" % (slide["number"], slide["title"][:40] or "(no title)", len(slide["shapes"]), slide["layout_name"]))
        out.write("  %d master(s), %d embedded file(s)\n" % (len(s["masters"]), len(s["media"])))
    for note in doc.notes:
        print("NOTE: " + note, file=sys.stderr)
    return 1 if doc.lost else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
