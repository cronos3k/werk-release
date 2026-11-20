#!/usr/bin/env python3
"""read_raster_layers.py -- reference reader of werk profile raster-layers/1 (werk release).

    python read_raster_layers.py PACKAGE [--json OUT] [--dump DIR]

Reads a raster-layers/1 package (directory or .werk zip) the way
spec/PROFILE-RASTER-LAYERS.md section 6 says, and prints the extraction that
profiles/raster-layers/PROFILE.md ("What a reader outputs") defines, as canonical JSON
(UTF-8, keys sorted, indent 1): the canvas, the layer tree bottom to top with every layer's
properties, and for every surface it names the decoded samples cropped to the canvas, given as
their sha256 (--dump DIR also writes them, one raw file per surface). Every file it uses is
checked against MANIFEST.json first. Pure Python 3.8+ standard library; it runs nothing it
finds in the package.

Exit status: 0 read, nothing dead; 1 read, with dead or missing nodes (listed under "dead");
2 not readable as a raster-layers/1 package.
"""
# ---- container block: shared verbatim by the six profiles/*/read_*.py readers -------------
# (profiles/tools/check_readers.py checks that every reader carries this block unchanged.)
# A werk package is a directory, or that tree as a zip (store or deflate entries, no zip64).
# MANIFEST.json is the only index; every file is reached node -> version -> files[] and checked
# against its sha256 and size before it is used (spec/SPEC.md sections 1, 2, 2.1).
import hashlib, json, os, struct, sys, zlib


class Refusal(Exception):
    """The container cannot be read at all (spec/SPEC.md 10.1, container scope): exit 2."""


class Dead(Exception):
    """One node cannot be used (missing file, hash or size mismatch, unparseable payload)."""


def _sha(b):
    return hashlib.sha256(b).hexdigest()


class Package(object):
    def __init__(self, path):
        self.path = path
        self._zip = None
        if os.path.isdir(path):
            self._dir = path
        else:
            self._dir = None
            with open(path, "rb") as fh:
                self._blob = fh.read()
            self._zip = self._central_directory(self._blob)
        try:
            self.manifest = json.loads(self._raw("MANIFEST.json").decode("utf-8"))
        except Refusal:
            raise
        except Exception as e:  # noqa: BLE001
            raise Refusal("MANIFEST.json unreadable: %s" % e)
        if not isinstance(self.manifest, dict) or not isinstance(self.manifest.get("nodes"), list):
            raise Refusal("MANIFEST.json has no nodes[]")
        self.nodes = {}
        for n in self.manifest["nodes"]:
            if isinstance(n, dict) and isinstance(n.get("node_id"), str):
                self.nodes[n["node_id"]] = n
        self.verified = set()

    @staticmethod
    def _central_directory(b):
        eocd = b.rfind(b"PK\x05\x06")
        if eocd < 0 or len(b) < eocd + 22:
            raise Refusal("not a zip and not a directory")
        count, size, off = struct.unpack_from("<HII", b, eocd + 10)
        if count == 0xFFFF or size == 0xFFFFFFFF or off == 0xFFFFFFFF:
            raise Refusal("zip64 is not part of the format")
        out, p = {}, off
        for _ in range(count):
            if b[p:p + 4] != b"PK\x01\x02":
                raise Refusal("damaged central directory")
            flags, method = struct.unpack_from("<HH", b, p + 8)
            csize, usize = struct.unpack_from("<II", b, p + 20)
            nlen, xlen, clen = struct.unpack_from("<HHH", b, p + 28)
            lho = struct.unpack_from("<I", b, p + 42)[0]
            name = b[p + 46:p + 46 + nlen].decode("utf-8", "replace")
            if name in out:
                raise Refusal("duplicate entry name %s" % name)
            out[name] = (lho, method, csize, usize, flags)
            p += 46 + nlen + xlen + clen
        return out

    def _raw(self, path):
        if self._dir is not None:
            full = os.path.join(self._dir, *path.split("/"))
            if not os.path.isfile(full):
                raise Dead("file missing: %s" % path)
            with open(full, "rb") as fh:
                return fh.read()
        ent = self._zip.get(path)
        if ent is None:
            if path == "MANIFEST.json":
                raise Refusal("no MANIFEST.json")
            raise Dead("file missing: %s" % path)
        lho, method, csize, usize, flags = ent
        b = self._blob
        if b[lho:lho + 4] != b"PK\x03\x04":
            raise Dead("bad local header: %s" % path)
        nlen, xlen = struct.unpack_from("<HH", b, lho + 26)
        data = b[lho + 30 + nlen + xlen:lho + 30 + nlen + xlen + csize]
        if method == 0:
            return data
        if method == 8:
            try:
                return zlib.decompress(data, -15)
            except zlib.error as e:
                raise Dead("deflate error in %s: %s" % (path, e))
        raise Dead("unsupported zip method %d: %s" % (method, path))

    def node(self, nid):
        n = self.nodes.get(nid)
        if n is None:
            raise Dead("no node %s" % nid)
        return n

    def version(self, nid, v=None):
        n = self.node(nid)
        want = n.get("active") if v is None else v
        for ver in n.get("versions") or []:
            if isinstance(ver, dict) and ver.get("v") == want:
                return ver
        raise Dead("node %s has no version %s" % (nid, want))

    def read(self, rec):
        """The bytes of one files[] record, checked against its size and sha256."""
        data = self._raw(rec["path"])
        if len(data) != rec.get("size") or _sha(data) != rec.get("sha256"):
            raise Dead("hash or size mismatch: %s" % rec["path"])
        self.verified.add(rec["path"])
        return data

    def payload(self, nid, v=None):
        """(record, bytes) of the node's payload file (spec/SPEC.md 2.1: payload_file, else
        the only file)."""
        ver = self.version(nid, v)
        files = ver.get("files") or []
        pf = ver.get("payload_file")
        if pf is None:
            if len(files) != 1:
                raise Dead("node %s: payload not determinable" % nid)
            rec = files[0]
        else:
            rec = next((f for f in files if f.get("path") == pf), None)
            if rec is None:
                raise Dead("node %s: payload_file not listed" % nid)
        return rec, self.read(rec)

    def by_role(self, nid, role, v=None):
        ver = self.version(nid, v)
        rec = next((f for f in ver.get("files") or [] if f.get("role") == role), None)
        if rec is None:
            raise Dead("node %s: no file with role %s" % (nid, role))
        return rec, self.read(rec)

    def json_payload(self, nid, v=None):
        rec, data = self.payload(nid, v)
        try:
            return json.loads(data.decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            raise Dead("node %s: payload is not JSON: %s" % (nid, e))

    def verify_all(self):
        """Every file of every version of every node: (number verified, [failures])."""
        bad, n = [], 0
        for nid, node in self.nodes.items():
            for ver in node.get("versions") or []:
                for rec in ver.get("files") or []:
                    try:
                        self.read(rec)
                        n += 1
                    except Dead as e:
                        bad.append("%s: %s" % (nid, e))
        return n, bad


def mp_decode(b, i=0):
    """MessagePack, the subset the envelope header uses (ENVELOPE.layout.txt section 4)."""
    c = b[i]
    if c <= 0x7F:
        return c, i + 1
    if c >= 0xE0:
        return c - 256, i + 1
    if 0xA0 <= c <= 0xBF:
        n = c & 0x1F
        return b[i + 1:i + 1 + n].decode("utf-8"), i + 1 + n
    if 0x90 <= c <= 0x9F:
        return _mp_seq(b, i + 1, c & 0x0F)
    if 0x80 <= c <= 0x8F:
        return _mp_map(b, i + 1, c & 0x0F)
    simple = {0xC0: None, 0xC2: False, 0xC3: True}
    if c in simple:
        return simple[c], i + 1
    ints = {0xCC: ">B", 0xCD: ">H", 0xCE: ">I", 0xCF: ">Q", 0xD0: ">b", 0xD1: ">h", 0xD2: ">i", 0xD3: ">q",
            0xCA: ">f", 0xCB: ">d"}
    if c in ints:
        sz = struct.calcsize(ints[c])
        return struct.unpack_from(ints[c], b, i + 1)[0], i + 1 + sz
    if c in (0xD9, 0xDA, 0xDB):
        fmt = {0xD9: ">B", 0xDA: ">H", 0xDB: ">I"}[c]
        sz = struct.calcsize(fmt)
        n = struct.unpack_from(fmt, b, i + 1)[0]
        j = i + 1 + sz
        return b[j:j + n].decode("utf-8"), j + n
    if c in (0xDC, 0xDD):
        fmt = ">H" if c == 0xDC else ">I"
        sz = struct.calcsize(fmt)
        return _mp_seq(b, i + 1 + sz, struct.unpack_from(fmt, b, i + 1)[0])
    if c in (0xDE, 0xDF):
        fmt = ">H" if c == 0xDE else ">I"
        sz = struct.calcsize(fmt)
        return _mp_map(b, i + 1 + sz, struct.unpack_from(fmt, b, i + 1)[0])
    raise ValueError("MessagePack byte 0x%02x is not used by envelopes" % c)


def _mp_seq(b, i, n):
    out = []
    for _ in range(n):
        v, i = mp_decode(b, i)
        out.append(v)
    return out, i


def _mp_map(b, i, n):
    out = {}
    for _ in range(n):
        k, i = mp_decode(b, i)
        v, i = mp_decode(b, i)
        out[k] = v
    return out, i


def envelope(data, magic=None):
    """(header dict, {section name: bytes}) of a binary envelope (ENVELOPE.layout.txt 1)."""
    if len(data) < 12 or data[:2] != b"WK":
        raise Dead("not an envelope")
    if magic is not None and data[:4] != magic:
        raise Dead("envelope magic %r, expected %r" % (data[:4], magic))
    ver, hlen = struct.unpack_from("<II", data, 4)
    if ver != 1:
        raise Dead("envelope version %d" % ver)
    header, _ = mp_decode(data[12:12 + hlen])
    secs = {}
    for s in header.get("sections") or []:
        o, n = s["offset"], s["size"]
        if o + n > len(data):
            raise Dead("section %s outside the file" % s.get("name"))
        secs[s["name"]] = data[o:o + n]
    return header, secs


def emit(result, out_path=None):
    text = json.dumps(result, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    if out_path:
        with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    else:
        sys.stdout.buffer.write(text.encode("utf-8"))
# ---- end of container block -------------------------------------------------------------

PROFILE = "raster-layers/1"
ESZ = {"u8": 1, "u16": 2, "f32": 4}
CHANNELS = {"rgb": ["red", "green", "blue"], "indexed": ["red", "green", "blue"],
            "multichannel": ["red", "green", "blue"], "grayscale": ["gray"], "bitmap": ["gray"],
            "duotone": ["gray"], "cmyk": ["cyan", "magenta", "yellow", "black"],
            "lab": ["lightness", "a", "b"]}
TILE = 256


def undelta(e, C, esz):
    """core.raster.surface.layout.txt 5.2 DECODE."""
    N = 65536 * C
    d = bytearray(len(e))
    for k in range(esz):
        plane = bytearray(e[k * N:(k + 1) * N])
        for i in range(C, N):
            plane[i] = (plane[i] + plane[i - C]) & 0xFF
        d[k::esz] = plane
    return bytes(d)


def decode_surface(pkg, nid, W, H):
    """The surface's samples over the canvas (W x H x C x esz bytes, little-endian, rows top to
    bottom), plus its format. Layout sections 4-6."""
    _rec, idx = pkg.payload(nid)
    h, secs = envelope(idx, b"WKX0")
    if h.get("part") != "index" or h.get("tile_size") != TILE:
        raise Dead("%s: not a surface index" % nid)
    mode, st = h["pixel_mode"], h["sample_type"]
    chans = CHANNELS[mode] + (["alpha"] if h.get("has_alpha") else [])
    if h.get("channels") != chans or st not in ESZ:
        raise Dead("%s: channels or sample type inconsistent" % nid)
    C, esz = len(chans), ESZ[st]
    px = C * esz
    default = secs["default-pixel"]
    if len(default) != px:
        raise Dead("%s: default pixel is %d bytes" % (nid, len(default)))
    out = bytearray(default * (W * H))
    rows = secs.get("tile-index", b"")
    tile_files = h.get("tile_files") or []
    sums = h.get("tile_file_sha256")
    cache, seen = {}, set()
    T = 65536 * px
    for r in range(len(rows) // 16):
        tx, ty, fi, slot = struct.unpack_from("<iiii", rows, r * 16)
        if (tx, ty) in seen or not (0 <= fi < len(tile_files)):
            raise Dead("%s: bad tile index row" % nid)
        seen.add((tx, ty))
        if fi not in cache:
            _r, raw = pkg.by_role(nid, tile_files[fi])
            if raw[:4] != b"WKX0":
                try:
                    raw = zlib.decompress(raw)
                except zlib.error as e:
                    raise Dead("%s: tile file %s does not inflate: %s" % (nid, tile_files[fi], e))
            if sums is not None and _sha(raw) != sums[fi]:
                raise Dead("%s: tile envelope sha256 differs from tile_file_sha256" % nid)
            th, ts = envelope(raw, b"WKX0")
            for k in ("pixel_mode", "has_alpha", "channels", "sample_type"):
                if th.get(k) != h.get(k):
                    raise Dead("%s: tile file format differs from the index (%s)" % (nid, k))
            enc = th.get("sample_encoding", "raw")
            if enc not in ("raw", "planes-delta"):
                raise Dead("%s: unknown sample_encoding %s" % (nid, enc))
            cache[fi] = (ts["samples"], enc)
        samples, enc = cache[fi]
        if (slot + 1) * T > len(samples):
            raise Dead("%s: slot %d not in its tile file" % (nid, slot))
        tile = samples[slot * T:(slot + 1) * T]
        if enc == "planes-delta":
            tile = undelta(tile, C, esz)
        for rr in range(TILE):
            y = ty * TILE + rr
            if not (0 <= y < H):
                continue
            x0, x1 = max(0, tx * TILE), min(W, tx * TILE + TILE)
            if x0 >= x1:
                continue
            q0 = x0 - tx * TILE
            src = tile[(rr * TILE + q0) * px:(rr * TILE + q0 + (x1 - x0)) * px]
            out[(y * W + x0) * px:(y * W + x1) * px] = src
    return bytes(out), {"pixel_mode": mode, "channels": chans, "sample_type": st,
                        "stored_tiles": len(seen), "default_pixel": list(default)}


def read(path, dump=None):
    pkg = Package(path)
    m = pkg.manifest
    if m.get("profile") != PROFILE:
        raise Refusal("profile is %r, not %s" % (m.get("profile"), PROFILE))
    dead = []
    doc_id = (m.get("primary") or {}).get("document")
    try:
        doc = pkg.json_payload(doc_id)
    except Dead as e:
        raise Refusal("the structure node is unreadable: %s" % e)
    W, H = doc["width"], doc["height"]
    surfaces = {}

    def surf(nid):
        if nid is None:
            return None
        if nid in surfaces:
            return surfaces[nid]
        try:
            data, fmt = decode_surface(pkg, nid, W, H)
            fmt["samples_sha256"] = _sha(data)
            fmt["samples_bytes"] = len(data)
            fmt["node"] = nid
            if dump:
                os.makedirs(dump, exist_ok=True)
                with open(os.path.join(dump, nid + ".raw"), "wb") as fh:
                    fh.write(data)
            surfaces[nid] = fmt
        except (Dead, KeyError, ValueError, struct.error) as e:
            dead.append({"node": nid, "why": str(e)})
            surfaces[nid] = {"node": nid, "dead": True}
        return surfaces[nid]

    def layer(entry):
        nid = entry["layer"]
        out = {"id": nid}
        try:
            L = pkg.json_payload(nid)
        except Dead as e:
            dead.append({"node": nid, "why": str(e)})
            kids = []
            for ch in entry.get("children") or []:  # 3.2: the children move up
                r = layer(ch)
                kids.extend(r if isinstance(r, list) else [r])
            return kids
        c = L["content"]
        out.update({"name": L["name"], "kind": c["kind"], "visible": L["visible"], "blend": L["blend"],
                    "opacity": L["opacity"], "fill_opacity": L["fill_opacity"], "clipped": L["clipped"]})
        if c["kind"] == "raster":
            out["pixels"] = surf(c["pixels"])
        elif c["kind"] in ("text", "shape", "smart"):
            out["cache"] = surf(c.get("cache"))
        elif c["kind"] == "adjustment":
            out["adjustment"] = c["adjustment"]
        elif c["kind"] == "fill":
            out["fill"] = c["fill"]
        mk = L.get("mask")
        out["mask"] = None if mk is None else {"enabled": mk["enabled"], "density": mk["density"],
                                               "feather": mk["feather"], "surface": surf(mk["surface"])}
        if "children" in entry:
            kids = []
            for ch in entry["children"]:
                r = layer(ch)
                kids.extend(r if isinstance(r, list) else [r])
            out["children"] = kids
        return out

    tree = []
    for e in doc["layers"]:
        r = layer(e)
        tree.extend(r if isinstance(r, list) else [r])
    previews = {}
    for slot in ("image", "thumbnail"):
        nid = (m.get("primary") or {}).get(slot)
        if nid is None:
            continue
        try:
            _rec, png = pkg.payload(nid)
            if png[:8] != b"\x89PNG\r\n\x1a\n":
                raise Dead("not a PNG")
            w, h = struct.unpack(">II", png[16:24])
            previews[slot] = {"node": nid, "width": w, "height": h, "png_sha256": _sha(png)}
        except Dead as e:
            dead.append({"node": nid, "why": str(e)})
    known = ("core.spec", "core.loader", "core.license", "core.readme", "core.revisions", "core.tool")
    skipped = sorted(set(str(n.get("type")) for n in pkg.nodes.values()
                         if not str(n.get("type", "")).startswith("core.raster.") and n.get("type") not in known))
    nver, bad = pkg.verify_all()
    return {
        "profile": PROFILE, "name": doc["name"],
        "canvas": {"width": W, "height": H, "resolution_dpi": doc["resolution_dpi"],
                   "color_mode": doc["color_mode"], "sample_type": doc["sample_type"]},
        "layers": tree, "previews": previews,
        "dead": sorted(dead, key=lambda d: d["node"]), "skipped_types": skipped,
        "files_verified": nver, "file_failures": bad,
    }


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("package"); ap.add_argument("--json"); ap.add_argument("--dump")
    a = ap.parse_args(argv)
    try:
        res = read(a.package, a.dump)
    except Refusal as e:
        sys.stderr.write("refused: %s\n" % e)
        return 2
    emit(res, a.json)
    return 1 if (res["dead"] or res["file_failures"]) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
