#!/usr/bin/env python3
"""profilekit.py -- what the six profile builders share.

A builder writes a package of one ArtCraft profile with the RELEASE Python library
(libs/python, `PackageWriter` + `add_spec_file`), the documented route for a profile outside
the bundle (libs/README.md, "Writing"). Nothing here edits the release spec: the profile's own
definition files (profiles/<name>/spec/...) are added to the package's `core.spec` node, as
SPEC section 2.2 says a profile travels (profile narrative, manifest schema, payload schemas,
layouts, conventions map), and format definitions go under spec/formats/ with their reference
tool as a `core.tool` node (SPEC sections 3.17, 3.18).

Also here: the binary envelope writer (spec/layouts/ENVELOPE.layout.txt: magic, version,
header length, canonical MessagePack header, 16-byte aligned sections at absolute offsets), a
deterministic RGBA PNG writer (MINI-SPECS section 8), and compact JSON.
Python 3.8+, standard library only (plus the release library).
"""
import hashlib
import json
import os
import struct
import sys
import uuid as _uuid
import zlib
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILES = os.path.dirname(HERE)
REPO = os.path.dirname(PROFILES)
sys.path.insert(0, os.path.join(REPO, "libs", "python"))
import werk  # noqa: E402  the release library

CREATED = "2026-11-20T00:00:00Z"
PRODUCER = OrderedDict([("tool", "werk-release profiles builder"), ("version", "1")])
LF = b"\n"


def sha(b):
    return hashlib.sha256(b).hexdigest()


def cjson(value):
    """One line of JSON (key order as given), UTF-8, then one line feed: the form the
    ArtCraft writers use for payloads (PROFILE-RASTER-LAYERS.md section 7.1)."""
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + LF


def pjson(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")


def f32(x):
    """A value held as binary32, written as the decimal expansion of that float widened to 64
    bits (PROFILE-RASTER-LAYERS.md section 5.1, the same rule in every ArtCraft profile)."""
    return struct.unpack("<f", struct.pack("<f", x))[0]


def uuid_for(name):
    return str(_uuid.uuid5(_uuid.NAMESPACE_URL, "werk-release/profiles/" + name))


# ---------------------------------------------------------------- MessagePack + envelope

def mp_encode(value):
    """Canonical MessagePack (ENVELOPE.layout.txt section 4.3): shortest integer form, float64
    for non-integers, shortest string form, map keys sorted by their UTF-8 bytes."""
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
        head = bytes([0x90 | n]) if n <= 15 else (b"\xdc" + struct.pack(">H", n) if n <= 0xFFFF
                                                 else b"\xdd" + struct.pack(">I", n))
        return head + b"".join(mp_encode(v) for v in value)
    if isinstance(value, dict):
        n = len(value)
        head = bytes([0x80 | n]) if n <= 15 else (b"\xde" + struct.pack(">H", n) if n <= 0xFFFF
                                                 else b"\xdf" + struct.pack(">I", n))
        body = b""
        for key in sorted(value, key=lambda k: k.encode("utf-8")):
            body += mp_encode(key) + mp_encode(value[key])
        return head + body
    raise TypeError("not encodable: %r" % (value,))


def align16(n):
    return (n + 15) // 16 * 16


def envelope(magic, kind, keys, sections):
    """ENVELOPE.layout.txt section 1. `sections`: list of (name, dtype, shape, stride, data).
    Offsets are absolute and depend on the header's own length, so the header is laid out
    until its length stops changing."""
    header_len = 0
    while True:
        origin = align16(12 + header_len)
        table, cursor = [], origin
        for (name, dtype, shape, stride, data) in sections:
            table.append({"name": name, "offset": cursor, "size": len(data), "dtype": dtype,
                          "shape": list(shape), "stride": stride})
            cursor = align16(cursor + len(data))
        header = dict(keys)
        header.update({"kind": kind, "endianness": "le", "payload_origin": origin,
                       "payload_size": cursor - origin, "sections": table})
        enc = mp_encode(header)
        if len(enc) == header_len:
            break
        header_len = len(enc)
    out = bytearray(magic + struct.pack("<II", 1, header_len) + enc)
    out += bytes(origin - len(out))
    for (_n, _d, _s, _st, data) in sections:
        out += data
        out += bytes(align16(len(out)) - len(out))
    return bytes(out)


# ---------------------------------------------------------------- PNG

def png_rgba(width, height, rgba):
    """8-bit RGBA PNG, filter 0 on every row, zlib level 9: the same bytes on every run."""
    assert len(rgba) == width * height * 4

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    raw = bytearray()
    stride = width * 4
    for y in range(height):
        raw += b"\x00" + rgba[y * stride:(y + 1) * stride]
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


def downscale_area(width, height, rgba, max_side):
    """Area-average resample of straight-alpha RGBA to fit max_side (integer box factors only:
    the fixtures use canvases that divide evenly). Colour is averaged weighted by alpha."""
    f = 1
    while max(width, height) // f > max_side:
        f *= 2
    if f == 1:
        return width, height, bytes(rgba)
    w2, h2 = width // f, height // f
    out = bytearray(w2 * h2 * 4)
    for y in range(h2):
        for x in range(w2):
            sr = sg = sb = sa = 0
            for dy in range(f):
                row = ((y * f + dy) * width + x * f) * 4
                for dx in range(f):
                    i = row + dx * 4
                    a = rgba[i + 3]
                    sr += rgba[i] * a; sg += rgba[i + 1] * a; sb += rgba[i + 2] * a; sa += a
            o = (y * w2 + x) * 4
            n = f * f
            if sa:
                out[o] = (sr + sa // 2) // sa; out[o + 1] = (sg + sa // 2) // sa; out[o + 2] = (sb + sa // 2) // sa
            out[o + 3] = (sa + n // 2) // n
    return w2, h2, bytes(out)


# ---------------------------------------------------------------- the package

def profile_dir(name):
    return os.path.join(PROFILES, name)


def read_tree(root, prefix):
    out = OrderedDict()
    for dp, _dn, fn in os.walk(root):
        for f in fn:
            full = os.path.join(dp, f)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            out[prefix + rel] = open(full, "rb").read()
    return OrderedDict(sorted(out.items(), key=lambda kv: kv[0].encode("utf-8")))


MEDIA = {".md": "text/markdown", ".json": "application/json", ".txt": "text/plain", ".py": "text/x-python"}


def media_of(path):
    if path.endswith(".schema.json"):
        return "application/schema+json"
    return MEDIA.get(os.path.splitext(path)[1])


class ProfilePackage(object):
    """A PackageWriter set up for one ArtCraft profile.

        pp = ProfilePackage("raster-layers", "Harbour poster", summary=..., readme=...)
        pp.w.add_node(...)            # the profile's own nodes, through the release library
        pp.use_format("zlib-deflate")
        pp.add_reference_reader()     # profiles/<name>/read_<name>.py as a core.tool node
        pp.write(out)                 # adds the revisions record, schemas/layouts maps, writes
    """

    def __init__(self, name, entity_name, summary, readme_text, license_text=None, spdx_id=None,
                 uuid=None, created=CREATED):
        self.name = name
        self.dir = profile_dir(name)
        self.spec = read_tree(os.path.join(self.dir, "spec"), "spec/")
        ms = "spec/schemas/manifest.%s.schema.json" % name
        schema = json.loads(self.spec[ms])
        self.manifest_schema_obj = schema
        cprops = schema["properties"]["conventions"]["properties"]
        conv = OrderedDict((k, cprops[k]["const"]) for k in sorted(cprops))
        narrative = [p for p in self.spec if p.startswith("spec/PROFILE-")]
        assert len(narrative) == 1, narrative
        self.w = werk.PackageWriter(
            "%s/1" % name, entity_name, summary=summary, uuid=uuid or uuid_for(name), created=created,
            conventions=conv, producer=PRODUCER, generator=PRODUCER, license_text=license_text,
            spdx_id=spdx_id, readme_text=readme_text, manifest_schema=ms, profile_spec=narrative[0],
            conventions_map="spec/conventions-map.%s.json" % name)
        for path, data in self.spec.items():
            replaced = self.w.add_spec_file(path, data, media_of(path))
            assert not replaced, "%s would replace a release spec file" % path
        htr = os.path.join(self.dir, "HOW-TO-READ.md")
        self.w.add_readme_file("HOW-TO-READ.md", open(htr, "rb").read(), "text/markdown")
        self.formats = []

    # -- formats (SPEC 3.18) -------------------------------------------------
    def use_format(self, fid):
        """Carry spec/formats/<fid>.md and its reference tool (core.tool node
        format-<fid>-reference, source only) as the ArtCraft writers do (CRAFT-BASE.md 6.1)."""
        if fid in self.formats:
            return
        root = os.path.join(PROFILES, "_formats")
        path = "spec/formats/%s.md" % fid
        self.w.add_spec_file(path, open(os.path.join(root, path), "rb").read(), "text/markdown")
        self.w.set_format(fid, path)
        tdir = os.path.join(root, "tools", "format-%s-reference" % fid)
        tj = json.loads(open(os.path.join(tdir, "tool.json"), "rb").read())
        files = [self.w.file("tools/format-%s-reference/tool.json" % fid,
                             open(os.path.join(tdir, "tool.json"), "rb").read(), "application/json", role="payload")]
        for f in tj["files"]:
            files.append(self.w.file(f["path"], open(os.path.join(tdir, os.path.basename(f["path"])), "rb").read(),
                                     "text/x-python", role=f.get("role")))
        self.w.add_node("format-%s-reference" % fid, "core.tool", files,
                        note="Reference implementation (source) of a format this document's payloads are "
                             "encoded in, named by that format's definition.",
                        payload_file="tools/format-%s-reference/tool.json" % fid)
        self.formats.append(fid)

    # -- the profile's reference reader as an embedded tool (SPEC 3.17) ------
    def add_reference_reader(self):
        fn = "read_%s.py" % self.name.replace("-", "_")
        src = open(os.path.join(self.dir, fn), "rb").read()
        tid = "reader-%s" % self.name
        rel = "tools/%s/%s" % (tid, fn)
        desc = OrderedDict([
            ("schema_version", 1), ("tool_id", tid),
            ("name", "%s (reference reader for %s/1)" % (fn, self.name)), ("version", "1"),
            ("role", "viewer"), ("form", "source"), ("language", "python"), ("entrypoint", rel),
            ("files", [OrderedDict([("path", rel), ("sha256", sha(src)), ("size", len(src))])]),
            ("license", OrderedDict([("spdx_id", "CC0-1.0"),
                                     ("note", "Reference code written for the werk release; no rights reserved.")])),
            ("invocation", OrderedDict([
                ("example", "python %s <this package> [--json OUT] [--verify-only]" % fn),
                ("toolchain", "python>=3.8, standard library only"),
                ("note", "Reads the package as profiles/%s/PROFILE.md section 'What a reader outputs' says "
                         "and prints that extraction as canonical JSON. Never run automatically." % self.name)])),
            ("produced", []),
            ("note", "The release's reference reader of profile %s/1, carried in source as the convenience "
                     "spec/SPEC.md 3.17 allows. It produced nothing in this package." % self.name)])
        self.w.add_node(tid, "core.tool",
                        [self.w.file("tools/%s/tool.json" % tid, pjson(desc), "application/json", role="payload"),
                         self.w.file(rel, src, "text/x-python", role="source")],
                        note="The reference reader of this profile, source only (spec/SPEC.md 3.17); reading it "
                             "is allowed, nothing in this package is ever executed automatically.",
                        meta=OrderedDict([("tool_id", tid), ("role", "viewer"), ("language", "python"),
                                          ("form", "source"), ("file_count", 1)]),
                        payload_file="tools/%s/tool.json" % tid)

    # -- finishing ------------------------------------------------------------
    def _maps(self):
        types = sorted(set(n["type"] for n in self.w.nodes.values()))
        for t in types:
            sp = "spec/schemas/%s.schema.json" % t
            if sp in self.w.blobs and t not in self.w.schemas:
                self.w.set_schema(t, sp)
            lp = "spec/layouts/%s.layout.txt" % t
            if lp in self.w.blobs and t not in self.w.layouts:
                self.w.set_layout(t, lp)

    def add_revisions(self, note):
        nodes = OrderedDict((nid, 1) for nid in sorted(self.w.nodes))
        rec = OrderedDict([("schema_version", 1), ("revision", 1), ("kind", "save"), ("note", note),
                           ("created", self.w.created), ("producer", PRODUCER), ("nodes", nodes)])
        self.w.add_node("revisions", "core.revisions",
                        [self.w.file("revisions/revision.json", pjson(rec), "application/json")],
                        note=note)

    def write(self, out, revision_note):
        self.add_revisions(revision_note)
        self._maps()
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        self.w.write(out)
        return open(out, "rb").read()
