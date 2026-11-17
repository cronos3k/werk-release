# -*- coding: utf-8 -*-
"""raster-layers/1 for host plug-ins: read the layer tree with its pixels, and
write a minimal valid capsule from layers. Python standard library + the werk
release library (`werk_single.py`, vendored beside this file).

The normative text is the capsule's own spec/PROFILE-RASTER-LAYERS.md and
spec/layouts/core.raster.surface.layout.txt (they travel inside every
raster-layers/1 package). This module implements:

READ  - primary.document -> the tree (bottom to top, groups with children);
        per layer: name, visible, opacity, blend, kind; pixels for `raster`
        (content.pixels) and for `text` / `shape` / `smart` (content.cache),
        decoded from the surface (index + tile files, zlib streams, sample
        encodings "raw" and "planes-delta", u8 / u16 / f32) and cropped to
        the canvas. Colour models rgb, indexed, multichannel, grayscale,
        bitmap, duotone are decoded; cmyk and lab surfaces are reported and
        not decoded. Masks, adjustment and fill layers, effects and clipping
        are reported, not applied.
WRITE - PROFILE-RASTER-LAYERS.md section 7, grown to N pixel layers: u8 RGBA
        surfaces, raw tiles (no compression), only tiles that differ from
        the default pixel; one composite preview (primary.image). Written by
        the release library's PackageWriter: spec/ and loaders/ come from the
        library's bundle; the profile's own spec files (PROFILE-RASTER-LAYERS.md,
        its schemas, layouts, examples), which the bundle lacks, are added with
        add_spec_file from a TEMPLATE capsule of the same profile.
"""

import hashlib
import json
import os
import struct
import uuid as _uuidlib
import zlib
from itertools import accumulate

import werk_single as werk

TILE = 256
COLOUR = {"rgb": "rgb", "indexed": "rgb", "multichannel": "rgb",
          "grayscale": "gray", "bitmap": "gray", "duotone": "gray"}
ESZ = {"u8": 1, "u16": 2, "f32": 4}
BABL_TYPE = {"u8": "u8", "u16": "u16", "f32": "float"}


class Report(object):
    def __init__(self):
        self.entries = []

    def add(self, sev, code, msg):
        self.entries.append((sev, code, msg))


# ---------------------------------------------------------------------------
# reading
# ---------------------------------------------------------------------------

def _version_files(pkg, node_id):
    node = pkg.node(node_id)
    if node is None:
        raise KeyError("no node %s" % node_id)
    if node.status == "dead":
        raise ValueError("node %s is dead" % node_id)
    ver = None
    for v in node.versions:
        if v.get("v") == node.resolved:
            ver = v
    if ver is None:
        raise ValueError("node %s has no resolved version" % node_id)
    return ver


def _sections(data, header):
    return {s["name"]: data[s["offset"]:s["offset"] + s["size"]]
            for s in header.get("sections") or []}


def _undelta(e, C, esz):
    """planes-delta DECODE (layout section 5.2) of one tile."""
    N = TILE * TILE * C
    out = bytearray(N * esz)
    add = lambda a, b: (a + b) & 0xFF                                # noqa: E731
    for k in range(esz):
        plane = e[k * N:(k + 1) * N]
        dec = bytearray(N)
        for c in range(C):
            dec[c::C] = bytes(accumulate(plane[c::C], add))
        out[k::esz] = dec
    return bytes(out)


def decode_surface(pkg, node_id, canvas_w, canvas_h):
    """-> dict(mode, has_alpha, channels, sample_type, C, esz, rect, data):
    the surface cropped to the canvas, rows top to bottom, interleaved."""
    ver = _version_files(pkg, node_id)
    files = ver["files"]
    by_role = {f.get("role"): f["path"] for f in files if f.get("role")}
    index_path = ver.get("payload_file") or files[0]["path"]
    idx = pkg.read_file(index_path)
    magic, _v, h = werk.read_envelope(idx)
    if h.get("part") != "index":
        raise ValueError("%s: not an index envelope" % index_path)
    if h.get("tile_size") != TILE:
        raise ValueError("tile_size %r" % h.get("tile_size"))
    st, mode = h["sample_type"], h["pixel_mode"]
    chans = list(h["channels"])
    C, esz = len(chans), ESZ[st]
    secs = _sections(idx, h)
    default = bytes(secs["default-pixel"])
    rows = secs.get("tile-index", b"")
    T = TILE * TILE * C * esz
    canvas = bytearray(default * (canvas_w * canvas_h))
    tile_cache = {}
    stride = canvas_w * C * esz
    for i in range(h.get("tile_count", 0)):
        tx, ty, fi, slot = struct.unpack_from("<iiii", rows, i * 16)
        x0, y0 = tx * TILE, ty * TILE
        if x0 >= canvas_w or y0 >= canvas_h or x0 + TILE <= 0 or y0 + TILE <= 0:
            continue
        role = h["tile_files"][fi]
        if role not in tile_cache:
            raw = pkg.read_file(by_role[role])
            if raw[:4] != b"WKX0":
                raw = zlib.decompress(raw)
            _m, _vv, th = werk.read_envelope(raw)
            for k in ("pixel_mode", "has_alpha", "channels", "sample_type"):
                if th.get(k) != h.get(k):
                    raise ValueError("tile file %s: %s differs from the index" % (role, k))
            enc = th.get("sample_encoding", "raw")
            if enc not in ("raw", "planes-delta"):
                raise ValueError("sample_encoding %r" % enc)
            tile_cache[role] = (_sections(raw, th)["samples"], enc)
        samples, enc = tile_cache[role]
        tile = bytes(samples[slot * T:(slot + 1) * T])
        if len(tile) != T:
            raise ValueError("slot %d not in tile file %s" % (slot, role))
        if enc == "planes-delta":
            tile = _undelta(tile, C, esz)
        qa, qb = max(0, -x0), min(TILE, canvas_w - x0)
        for r in range(max(0, -y0), min(TILE, canvas_h - y0)):
            src = (r * TILE + qa) * C * esz
            dst = (y0 + r) * stride + (x0 + qa) * C * esz
            canvas[dst:dst + (qb - qa) * C * esz] = tile[src:src + (qb - qa) * C * esz]
    return {"mode": mode, "has_alpha": bool(h["has_alpha"]), "channels": chans,
            "sample_type": st, "C": C, "esz": esz,
            "rect": (0, 0, canvas_w, canvas_h), "data": bytes(canvas),
            "colour": COLOUR.get(mode)}


def babl_format(surf):
    """The babl format name a GEGL buffer takes these bytes in, or None."""
    col = surf["colour"]
    if col is None:
        return None
    base = "R'G'B'" if col == "rgb" else "Y'"
    return "%s%s %s" % (base, "A" if surf["has_alpha"] else "", BABL_TYPE[surf["sample_type"]])


def read_document(path):
    """-> (doc dict, tree, report). tree entries: dict(node_id, name, kind,
    visible, opacity, blend, surface|None, children|None, notes[])."""
    rep = Report()
    pkg = werk.open(path)
    v = pkg.verdict()
    for e in pkg.report:
        rep.add(e.severity, e.code, ("%s: %s" % (e.node, e.message)) if e.node else e.message)
    if pkg.manifest.get("profile") != "raster-layers/1":
        raise ValueError("profile is %r, not raster-layers/1" % pkg.manifest.get("profile"))
    doc_id = (pkg.manifest.get("primary") or {}).get("document")
    doc = json.loads(pkg.read_payload(doc_id).decode("utf-8"))
    W, H = int(doc["width"]), int(doc["height"])

    def build(entries, depth=0):
        out = []
        for ent in entries:
            nid = ent["layer"]
            try:
                lj = json.loads(pkg.read_payload(nid).decode("utf-8"))
            except Exception as e:  # noqa: BLE001 - law 3: lose the layer, keep going
                rep.add("error", "layer-dead", "%s: %s; dropped (children kept)" % (nid, e))
                if ent.get("children"):
                    out.extend(build(ent["children"], depth))
                continue
            c = lj.get("content") or {}
            item = {"node_id": nid, "name": lj.get("name") or nid, "kind": c.get("kind"),
                    "visible": bool(lj.get("visible", True)),
                    "opacity": float(lj.get("opacity", 1.0)) * float(lj.get("fill_opacity", 1.0)),
                    "blend": lj.get("blend", "Normal"), "surface": None,
                    "children": None, "notes": []}
            if lj.get("mask"):
                item["notes"].append("mask-not-applied")
            if lj.get("clipped"):
                item["notes"].append("clipping-not-applied")
            if (lj.get("effects") or {}).get("items"):
                item["notes"].append("effects-not-applied")
            if "children" in ent:
                item["children"] = build(ent["children"] or [], depth + 1)
            else:
                sid = c.get("pixels") if c.get("kind") == "raster" else c.get("cache")
                if c.get("kind") in ("adjustment", "fill"):
                    item["notes"].append("%s-layer-not-rendered" % c.get("kind"))
                elif sid:
                    try:
                        item["surface"] = decode_surface(pkg, sid, W, H)
                        if item["surface"]["colour"] is None:
                            item["notes"].append("pixel-mode-%s-not-decoded"
                                                 % item["surface"]["mode"])
                            item["surface"] = None
                    except Exception as e:  # noqa: BLE001
                        rep.add("error", "surface-dead", "%s: %s; layer shown empty" % (sid, e))
                else:
                    item["notes"].append("no-pixels")
            for n in item["notes"]:
                rep.add("info", n, "%s (%s)" % (nid, item["name"]))
            out.append(item)
        return out

    tree = build(doc.get("layers") or [])
    return {"width": W, "height": H, "sample_type": doc.get("sample_type", "U8"),
            "color_mode": doc.get("color_mode"), "name": doc.get("name"),
            "resolution_dpi": doc.get("resolution_dpi"),
            "entity": dict(pkg.manifest.get("entity") or {}), "verdict": dict(v),
            "primary_image": (pkg.manifest.get("primary") or {}).get("image")}, tree, rep


# ---------------------------------------------------------------------------
# writing
# ---------------------------------------------------------------------------

def _mp(value):
    """Canonical MessagePack (ENVELOPE.layout.txt 4.3)."""
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
            for lim, lead, fmt in ((0xFF, 0xCC, ">B"), (0xFFFF, 0xCD, ">H"),
                                   (0xFFFFFFFF, 0xCE, ">I")):
                if value <= lim:
                    return bytes([lead]) + struct.pack(fmt, value)
            return b"\xcf" + struct.pack(">Q", value)
        for lim, lead, fmt in ((-0x80, 0xD0, ">b"), (-0x8000, 0xD1, ">h"),
                               (-0x80000000, 0xD2, ">i")):
            if value >= lim:
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
        head = bytes([0x90 | n]) if n <= 15 else (
            b"\xdc" + struct.pack(">H", n) if n <= 0xFFFF else b"\xdd" + struct.pack(">I", n))
        return head + b"".join(_mp(v) for v in value)
    if isinstance(value, dict):
        n = len(value)
        head = bytes([0x80 | n]) if n <= 15 else (
            b"\xde" + struct.pack(">H", n) if n <= 0xFFFF else b"\xdf" + struct.pack(">I", n))
        return head + b"".join(_mp(k) + _mp(value[k])
                               for k in sorted(value, key=lambda k: k.encode("utf-8")))
    raise TypeError("not encodable: %r" % (value,))


def _a16(n):
    return (n + 15) // 16 * 16


def _envelope(kind, keys, sections):
    hl = 0
    while True:
        origin = _a16(12 + hl)
        table, cur = [], origin
        for (name, dtype, shape, stride, data) in sections:
            table.append({"name": name, "offset": cur, "size": len(data), "dtype": dtype,
                          "shape": list(shape), "stride": stride})
            cur = _a16(cur + len(data))
        hd = dict(keys)
        hd.update({"kind": kind, "endianness": "le", "payload_origin": origin,
                   "payload_size": cur - origin, "sections": table})
        enc = _mp(hd)
        if len(enc) == hl:
            break
        hl = len(enc)
    out = bytearray(b"WKX0" + struct.pack("<II", 1, hl) + enc)
    out += bytes(origin - len(out))
    for (_n, _d, _s, _st, data) in sections:
        out += data
        out += bytes(_a16(len(out)) - len(out))
    return bytes(out)


def surface_files_rgba8(rgba, w, h):
    """(index bytes, tiles bytes or None, tile count) for a w x h RGBA u8
    picture at the canvas origin. Default pixel transparent black; only tiles
    with a non-zero byte are stored (layout section 7)."""
    fmt = {"pixel_mode": "rgb", "has_alpha": True,
           "channels": ["red", "green", "blue", "alpha"], "sample_type": "u8",
           "tile_size": TILE, "nonfinite": False}
    C = 4
    tiles, rows = [], []
    zero_row = bytes(TILE * C)
    for ty in range((h + TILE - 1) // TILE):
        for tx in range((w + TILE - 1) // TILE):
            t = bytearray(TILE * TILE * C)
            x0, y0 = tx * TILE, ty * TILE
            qw = min(TILE, w - x0)
            any_set = False
            for r in range(min(TILE, h - y0)):
                src = ((y0 + r) * w + x0) * C
                seg = rgba[src:src + qw * C]
                if seg != zero_row[:qw * C]:
                    any_set = True
                t[r * TILE * C:r * TILE * C + qw * C] = seg
            if any_set:
                rows.append(struct.pack("<iiii", tx, ty, 0, len(tiles)))
                tiles.append(bytes(t))
    tk = dict(fmt, part="tiles", tile_count=len(tiles))
    tiles_b = _envelope("core.raster.surface", tk,
                        [("samples", "u8", [len(tiles), TILE, TILE, C], C, b"".join(tiles))]
                        ) if tiles else None
    ik = dict(fmt, part="index", tile_count=len(tiles),
              tile_files=["tiles-p0-p0"] if tiles else [])
    index_b = _envelope("core.raster.surface", ik, [
        ("default-pixel", "u8", [C], 1, bytes(C)),
        ("tile-index", "i32", [len(tiles), 4], 16, b"".join(rows))])
    return index_b, tiles_b, len(tiles)


def _compact(v):
    return json.dumps(v, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n"


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def _is_superseded(path):
    name = path.rsplit("/", 1)[-1]
    return "@" in name and name.rsplit("@", 1)[1].split(".", 1)[0].isdigit()


DOC_TEMPLATE = {
    "schema_version": 1, "name": None, "width": None, "height": None,
    "resolution_dpi": 72.0, "color_mode": "Rgb", "sample_type": "U8",
    "color_space": None, "icc_profile": None, "layers": None, "channels": [],
    "quick_mask": None, "quick_mask_unselected": False, "selection": None,
    "patterns": [], "paths": [], "work_path": None, "clipping_path": None,
    "layer_comps": [], "last_applied_comp": None, "last_document_state": None,
    "text_styles": None, "variables": None, "metadata": None,
    "guides": {"horizontal": [], "vertical": []},
    "global_light": {"angle": 120.0, "altitude": 30.0}, "color_table": None,
    "duotone": None,
    "measurement": {"scale": {"pixel_length": 1.0, "logical_length": 1.0,
                              "units": "pixels"},
                    "count_groups": [], "active_count_group": 0, "ruler": None},
    "notes": [], "slices": {"groupName": "", "list": []}, "timeline": None,
    "file_encoding": {}, "psd": None, "fonts": [], "app": {"document_id": 0},
}

LAYER_TEMPLATE = {
    "schema_version": 1, "name": None, "visible": True,
    "locks": {"transparency": False, "pixels": False, "position": False,
              "artboard": False, "all": False},
    "blend": "Normal", "opacity": 1.0, "fill_opacity": 1.0, "clipped": False,
    "mask": None, "vector_mask": None,
    "effects": {"enabled": True, "items": [], "reference": None}, "label": "None",
    "content": None, "psd_id": None, "psd": None, "fill_cache": None,
    "link_group": None, "excluded_channels": 0, "blend_if": {"ranges": []},
    "advanced": {"knockout": "none", "blendInterior": False, "blendClipped": True,
                 "transparencyShapes": True, "layerMaskHidesEffects": False,
                 "vectorMaskHidesEffects": False},
    "video": None,
}

README = (u"{name}\n\nThis is a werk capsule, profile `raster-layers/1`, written by {tool} "
          u"{version}. It is one self-carrying file: it contains its own format "
          u"specification, three readers and its licence.\n\n"
          u"    python loaders/werk_read.py <this file> --verify    re-hash every byte\n\n"
          u"Where to read next: HOW-TO-READ.md, spec/PROFILE-RASTER-LAYERS.md, "
          u"spec/SPEC.md.\nMANIFEST.json is the only index: every file, its sha256 and "
          u"its size.\n")

LICENSE_UNESTABLISHED = (
    u"Licence notice\n\nTHE TERMS OF THIS DOCUMENT'S CONTENT ARE NOT ESTABLISHED.\n\n"
    u"The program that wrote this file was not told under which terms its content may be "
    u"used. No licence is granted by this notice; anyone redistributing the file must "
    u"establish its terms.\n")


def write_capsule(out, template, name, width, height, layers, composite_png=None,
                  created=None, uuid=None, tool="werk-gimp", version="1.0.0",
                  license_text=None, resolution_dpi=72.0):
    """Write a raster-layers/1 capsule through the release library's
    PackageWriter (spec/ + loaders/ from the library's bundle; the profile's
    own spec files that the bundle lacks added with add_spec_file).

    layers: bottom to top, each dict(name, visible, opacity (0..1), blend, rgba
    (bytes, width*height*4, u8, straight alpha, canvas-aligned)).
    composite_png: the flattened picture (PNG bytes, full size) -> the
    `composite` preview node and primary.image. Returns the PackageWriter.
    """
    tpl = werk.open(template)
    tm = tpl.manifest
    if tm.get("profile") != "raster-layers/1":
        raise ValueError("template %s is profile %r, not raster-layers/1"
                         % (template, tm.get("profile")))
    producer = {"tool": tool, "version": version}
    # The profile's spec files the release bundle does not carry. Paths both
    # have keep the RELEASE bundle's bytes (the newer revision of SPEC.md,
    # MINI-SPECS.md, ENVELOPE.layout.txt, core.revisions.schema.json, ...).
    bundled = {p for p in werk.default_bundle().files if p.startswith("spec/")}
    extra = {}
    for f in _version_files(tpl, "spec")["files"]:
        p = f["path"]
        if p not in bundled and not _is_superseded(p):
            extra[p] = tpl.read_file(p)
    w = werk.PackageWriter(
        "raster-layers/1", name,
        summary="%d-layer raster document, %d x %d px, exported by %s."
                % (len(layers), width, height, tool),
        uuid=uuid, created=created, conventions=tm["conventions"],
        manifest_schema=tm["manifest_schema"], profile_spec=tm.get("profile_spec"),
        generator=producer, producer=producer, license_text=license_text,
        readme_text=README.format(name=name, tool=tool, version=version),
        spec_files=extra, conventions_map=tm.get("conventions_map"))
    # One gap between the release library and this (older) profile revision,
    # bridged here and reported upstream, not hidden: the profile's manifest
    # schema (from the template) permits fewer loader capabilities than the
    # release loaders declare (summarize-points / summarize-gsplat are newer).
    # The loader records are narrowed to the capabilities THIS package's
    # schema can express: a true subset, never an added claim.
    try:
        ms = json.loads(w.blobs[tm["manifest_schema"]].decode("utf-8"))
        allowed = ms["$defs"]["loaderMeta"]["properties"]["capabilities"]["items"]["enum"]
    except (KeyError, TypeError, ValueError, AttributeError):
        allowed = None
    if allowed is not None:
        for n in w.nodes.values():
            meta = n.get("meta") if n["type"] == "core.loader" else None
            if meta and "capabilities" in meta:
                meta = dict(meta)
                meta["capabilities"] = [c for c in meta["capabilities"] if c in allowed]
                n["meta"] = meta
    w.add_readme_file("HOW-TO-READ.md", tpl.read_file("HOW-TO-READ.md"), "text/markdown")
    for t in ("core.raster.document", "core.raster.layer", "core.raster.surface",
              "core.revisions"):
        if t in (tm.get("schemas") or {}):
            w.set_schema(t, tm["schemas"][t])
        if t in (tm.get("layouts") or {}):
            w.set_layout(t, tm["layouts"][t])

    entries, doc_edges, inputs, layer_ids = [], [], [], []
    for i, L in enumerate(layers, 1):
        lid, sid = "layer-%d" % i, "layer-%d-pixels" % i
        lj = dict(LAYER_TEMPLATE)
        lj["name"] = L["name"] or ("Layer %d" % i)
        lj["visible"] = bool(L.get("visible", True))
        lj["opacity"] = float(round(L.get("opacity", 1.0), 6))
        lj["blend"] = L.get("blend") or "Normal"
        lj["content"] = {"kind": "raster", "pixels": sid}
        index_b, tiles_b, ntiles = surface_files_rgba8(L["rgba"], width, height)
        ip = "surfaces/%s/surface.wkx" % sid
        sfiles = [w.file(ip, index_b, "application/octet-stream",
                         "payload" if tiles_b else None)]
        if tiles_b:
            sfiles.append(w.file("surfaces/%s/tiles-p0-p0.wkx" % sid, tiles_b,
                                 "application/octet-stream", "tiles-p0-p0"))
        w.add_node(sid, "core.raster.surface", sfiles,
                   note="The pixels of layer %d: %d stored tile(s) of 256 x 256, u8 RGBA, "
                        "raw." % (i, ntiles),
                   meta={"usage": "layer-pixels", "owner": lid,
                         "channels": ["red", "green", "blue", "alpha"], "bits_per_sample": 8},
                   payload_file=ip if tiles_b else None)
        lp = "layers/%s/layer.json" % lid
        w.add_node(lid, "core.raster.layer", [w.file(lp, _compact(lj), "application/json")],
                   note="Layer %d of %d as %s exported it." % (i, len(layers), tool),
                   meta={"kind": "raster"},
                   edges=[{"to": sid, "kind": "enhances", "role": "pixels"}])
        inputs += [ip] + (["surfaces/%s/tiles-p0-p0.wkx" % sid] if tiles_b else []) + [lp]
        layer_ids += [sid, lid]
        entries.append({"layer": lid})
        doc_edges.append({"to": lid, "kind": "enhances", "role": "contains"})
    dj = dict(DOC_TEMPLATE)
    dj.update({"name": name, "width": width, "height": height, "layers": entries,
               "resolution_dpi": float(resolution_dpi)})
    w.add_node("document", "core.raster.document",
               [w.file("document/document.json", _compact(dj), "application/json")],
               note="The canvas and the layer tree, %d layer(s), %d x %d px, exported by %s."
                    % (len(layers), width, height, tool),
               meta={"width": width, "height": height, "color_mode": "Rgb",
                     "sample_type": "U8"}, edges=doc_edges)
    w.set_primary("document", "document")
    if composite_png is not None:
        info = werk.png_info(composite_png)
        w.add_node("composite", "core.raster.preview",
                   [w.file("preview/composite.png", composite_png, "image/png")],
                   note="The document flattened by %s at full size." % tool,
                   epistemic="measured", input_files=["document/document.json"] + inputs,
                   input_params={"derivation": "flattened-composite",
                                 "max_side": max(width, height), "resample": "area-average"},
                   meta={"alpha_mode": "straight", "bits_per_sample": 8,
                         "channels": ["red", "green", "blue", "alpha"][:info[2]],
                         "color_space": "srgb", "height": info[1], "usage": "composite",
                         "width": info[0]},
                   edges=[{"to": n, "kind": "requires", "role": "rendered-from"}
                          for n in ["document"] + layer_ids])
        w.set_primary("image", "composite")
        w.preview("preview/composite.png")
    # 7.4 the revision record: every node, at version 1
    uses = dict((nid, 1) for nid in list(w.nodes) + ["revisions"])
    rec = {"schema_version": 1, "revision": 1, "kind": "save",
           "note": "Exported by %s." % tool, "created": w.created,
           "producer": dict(producer), "nodes": uses}
    w.add_node("revisions", "core.revisions",
               [w.file("revisions/revision.json",
                       (json.dumps(rec, indent=2, sort_keys=True) + "\n").encode("utf-8"),
                       "application/json")],
               note="The revision record of this save.")
    w.write(out)
    return w
