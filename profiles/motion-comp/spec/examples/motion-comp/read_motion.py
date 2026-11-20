#!/usr/bin/env python3
"""read_motion.py - read a `motion-comp/1` werk capsule with nothing but this file.

Python standard library only. It uses NO motion-graphics software and NO werk software: it is
one implementation of spec/PROFILE-MOTION-COMP.md sections 6.0 to 6.12, 6.16 (fills) and 6.18.4,
of spec/layouts/core.keyframe.tracks.layout.txt and spec/layouts/core.expr.baked.layout.txt,
written from those documents.

    python read_motion.py <capsule> list
        every composition with its layers (front first), each layer's parent, timing and blend
        mode, and every animated or expression-driven property
    python read_motion.py <capsule> value <comp id> <layer id> <property> <tick> [<tick> ...]
        a property's value at composition times given in ticks; <property> is a path of
        `match` names from the layer's root (transform/position) or a uid
    python read_motion.py <capsule> matrix <comp id> <layer id> <tick>
        the layer's 2D matrix (layer pixels -> composition pixels), parents included
    python read_motion.py <capsule> baked <comp id>
        the baked expression values of a composition
    python read_motion.py <capsule> frame <comp id> <frame> --out <file> [--rgb]
        render one frame: width*height*4 bytes R G B A (straight alpha, 8 bit), or with --rgb
        width*height*3 bytes R G B over black
    python read_motion.py <capsule> report --out <file.json> [--frame <comp id>:<frame> ...]
        everything above for the whole capsule, as one JSON document
    python read_motion.py <capsule> effects
        check this file's implementations of the defined effects against the test vectors in
        the capsule's effect catalog

<capsule> is a .werk file or a directory. Everything read is verified against the manifest
(size and sha256). What this program does not implement it SAYS (the `notes` it prints): text,
3D, footage other than PNG stills, strokes and gradients of shape layers, path operators,
effects without a definition, layer styles, motion blur, collapsed nested compositions.
"""

import hashlib
import json
import math
import os
import struct
import sys
import zipfile
import zlib

TPS = 254016000000
NOTES = []


def note(text):
    if text not in NOTES:
        NOTES.append(text)


# ------------------------------------------------------------------------------------------
# The container (SPEC.md section 1, CRAFT-BASE.md sections 3 and 4)
# ------------------------------------------------------------------------------------------

class Capsule:
    def __init__(self, path):
        self.path = path
        self.zip = None if os.path.isdir(path) else zipfile.ZipFile(path)
        self.manifest = json.loads(self._raw("MANIFEST.json").decode("utf-8"))
        if self.manifest.get("profile") != "motion-comp/1":
            raise SystemExit("not a motion-comp/1 capsule: profile is %r" % self.manifest.get("profile"))
        self.nodes = {n["node_id"]: n for n in self.manifest["nodes"]}
        self.dead = {}
        # The current document: the record of the `revisions` node's active version.
        self.uses = None
        rev = self.nodes.get("revisions")
        if rev is not None:
            try:
                ver = self._version(rev, rev["active"])
                record = json.loads(self._verified(ver["files"][0]).decode("utf-8"))
                self.uses = record["nodes"]
            except Exception as e:  # a dead revision log: every node's active version counts
                self.dead["revisions"] = str(e)
        self.primary = self.manifest.get("primary", {})

    def _raw(self, path):
        if self.zip is not None:
            return self.zip.read(path)
        with open(os.path.join(self.path, *path.split("/")), "rb") as fh:
            return fh.read()

    def _version(self, node, v):
        for ver in node["versions"]:
            if ver["v"] == v:
                return ver
        raise ValueError("node %s has no version %s" % (node["node_id"], v))

    def _verified(self, entry):
        data = self._raw(entry["path"])
        if len(data) != entry["size"]:
            raise ValueError("size-mismatch: %s" % entry["path"])
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError("hash-mismatch: %s" % entry["path"])
        return data

    def version_of(self, node_id):
        node = self.nodes.get(node_id)
        if node is None:
            raise ValueError("no node %s" % node_id)
        if self.uses is not None and node_id != "revisions":
            if node_id not in self.uses:
                raise ValueError("node %s is not part of the current document" % node_id)
            return node, self._version(node, self.uses[node_id])
        return node, self._version(node, node["active"])

    def files(self, node_id):
        """Every file of the node's version in the document: [(entry, bytes)], payload first."""
        if node_id in self.dead:
            raise ValueError(self.dead[node_id])
        try:
            _node, ver = self.version_of(node_id)
            entries = list(ver["files"])
            payload = ver.get("payload_file")
            if payload:
                entries.sort(key=lambda e: 0 if e["path"] == payload else 1)
            return [(e, self._verified(e)) for e in entries]
        except Exception as e:
            self.dead[node_id] = str(e)
            raise ValueError(str(e))

    def payload(self, node_id, node_type=None):
        if node_type is not None and node_id in self.nodes and self.nodes[node_id]["type"] != node_type:
            self.dead[node_id] = "node %s is a %s, not a %s" % (node_id, self.nodes[node_id]["type"], node_type)
            raise ValueError(self.dead[node_id])
        return self.files(node_id)[0][1]

    def json(self, node_id, node_type=None):
        value = json.loads(self.payload(node_id, node_type).decode("utf-8"))
        if value.get("schema_version") != 1:
            self.dead[node_id] = "schema-version-unknown"
            raise ValueError("node %s: schema_version is not 1" % node_id)
        return value

    def meta(self, node_id):
        _node, ver = self.version_of(node_id)
        return ver.get("meta") or {}

    def stale(self, node_id):
        """A derived node is stale when its `input_hash` is not what its inputs hash to NOW
        (CRAFT-BASE.md section 5): sha256 over each input file's sha256 as 32 raw bytes, in
        `input_files` order, then the canonical JSON of `input_params`."""
        _node, ver = self.version_of(node_id)
        current = {}
        for other in self.nodes:
            try:
                _n, v = self.version_of(other)
            except ValueError:
                continue
            for f in v["files"]:
                logical = f["path"]
                name = logical.rsplit("/", 1)[-1]
                if "@" in name:                      # a superseded file keeps its logical name
                    stem, _, rest = name.rpartition("@")
                    digits = rest.split(".", 1)[0]
                    if digits.isdigit():
                        ext = rest[len(digits):]
                        logical = logical[:len(logical) - len(name)] + stem + ext
                current[logical] = f["sha256"]
        acc = hashlib.sha256()
        for path in ver.get("input_files", []):
            if path not in current:
                return True
            acc.update(bytes.fromhex(current[path]))
        params = ver.get("input_params") or {}
        acc.update(json.dumps(params, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
        return acc.hexdigest() != ver.get("input_hash")


# ------------------------------------------------------------------------------------------
# The envelope (spec/layouts/ENVELOPE.layout.txt)
# ------------------------------------------------------------------------------------------

def msgpack(buf, at=0):
    """Decode one value of the MessagePack subset of ENVELOPE.layout.txt section 4."""
    b = buf[at]
    if b <= 0x7F:
        return b, at + 1
    if b >= 0xE0:
        return b - 256, at + 1
    if 0xA0 <= b <= 0xBF:
        n = b & 0x1F
        return buf[at + 1:at + 1 + n].decode("utf-8"), at + 1 + n
    if 0x90 <= b <= 0x9F:
        return _array(buf, at + 1, b & 0x0F)
    if 0x80 <= b <= 0x8F:
        return _map(buf, at + 1, b & 0x0F)
    fixed = {0xCC: ">B", 0xCD: ">H", 0xCE: ">I", 0xCF: ">Q", 0xD0: ">b", 0xD1: ">h", 0xD2: ">i", 0xD3: ">q", 0xCA: ">f", 0xCB: ">d"}
    if b in fixed:
        size = struct.calcsize(fixed[b])
        return struct.unpack(fixed[b], buf[at + 1:at + 1 + size])[0], at + 1 + size
    if b == 0xC0:
        return None, at + 1
    if b in (0xC2, 0xC3):
        return b == 0xC3, at + 1
    lengths = {0xD9: 1, 0xDA: 2, 0xDB: 4, 0xC4: 1, 0xC5: 2, 0xC6: 4, 0xDC: 2, 0xDD: 4, 0xDE: 2, 0xDF: 4}
    if b in lengths:
        w = lengths[b]
        n = int.from_bytes(buf[at + 1:at + 1 + w], "big")
        start = at + 1 + w
        if b in (0xD9, 0xDA, 0xDB):
            return buf[start:start + n].decode("utf-8"), start + n
        if b in (0xC4, 0xC5, 0xC6):
            return bytes(buf[start:start + n]), start + n
        if b in (0xDC, 0xDD):
            return _array(buf, start, n)
        return _map(buf, start, n)
    raise ValueError("envelope-invalid: MessagePack byte 0x%02x is not allowed in a werk header" % b)


def _array(buf, at, n):
    out = []
    for _ in range(n):
        v, at = msgpack(buf, at)
        out.append(v)
    return out, at


def _map(buf, at, n):
    out = {}
    for _ in range(n):
        k, at = msgpack(buf, at)
        v, at = msgpack(buf, at)
        out[k] = v
    return out, at


DTYPES = {"u8": ("B", 1), "i8": ("b", 1), "u16": ("H", 2), "i16": ("h", 2), "u32": ("I", 4), "i32": ("i", 4),
          "u64": ("Q", 8), "i64": ("q", 8), "f32": ("f", 4), "f64": ("d", 8)}


def envelope(buf, magic, kind):
    """ENVELOPE.layout.txt section 7. Returns (header, {section name: flat list of numbers})."""
    if buf[:4] != magic:
        raise ValueError("envelope-invalid: magic is %r, not %r" % (bytes(buf[:4]), magic))
    header_len = struct.unpack("<I", buf[8:12])[0]
    if 12 + header_len > len(buf):
        raise ValueError("envelope-invalid: the header runs past the end of the file")
    header, end = msgpack(buf, 12)
    if end != 12 + header_len or header.get("endianness") != "le" or header.get("kind") != kind:
        raise ValueError("envelope-invalid: header")
    origin = 16 * ((12 + header_len + 15) // 16)
    if header["payload_origin"] != origin or origin + header["payload_size"] != len(buf):
        raise ValueError("envelope-invalid: payload_origin / payload_size do not add up")
    sections = {}
    for s in header["sections"]:
        code, esz = DTYPES[s["dtype"]]
        count = 1
        for n in s["shape"]:
            count *= n
        if s["offset"] % 16 != 0 or s["offset"] + s["size"] > len(buf):
            raise ValueError("envelope-invalid: section %s lies outside the file or is not aligned" % s["name"])
        if s["stride"] == esz:
            ok = s["size"] == s["stride"] * count
        else:
            last = s["shape"][-1]
            ok = s["stride"] >= esz * last and s["size"] == s["stride"] * (count // last if last else 0)
        if not ok:
            raise ValueError("envelope-invalid: section %s: size does not follow from shape and stride" % s["name"])
        n = s["size"] // esz
        values = list(struct.unpack("<%d%s" % (n, code), buf[s["offset"]:s["offset"] + s["size"]]))
        if s["dtype"] in ("f32", "f64") and any(v != v or v in (float("inf"), float("-inf")) for v in values):
            raise ValueError("envelope-invalid: NaN or infinity in section %s" % s["name"])
        sections[s["name"]] = values
    return header, sections


KIND_WORD = {"scalar": "Scalar", "vec2": "Vec2", "vec3": "Vec3", "color": "Color"}


def read_tracks(buf):
    """spec/layouts/core.keyframe.tracks.layout.txt section 4: every track as (uid, keys)."""
    header, sec = envelope(buf, b"WKX3", "core.keyframe.tracks")
    words = header["interpolations"]
    out = []
    for t in header["tracks"]:
        c, e = t["components"], t["first_ease"]
        keys = []
        for j in range(t["keys"]):
            k = t["first_key"] + j
            value = sec["value"][t["first_value"] + j * c:t["first_value"] + (j + 1) * c]
            flags = sec["flags"][k]
            n_in, n_out = sec["ease-count"][2 * k], sec["ease-count"][2 * k + 1]
            eases = [{"speed": sec["ease"][2 * (e + i)], "influence": sec["ease"][2 * (e + i) + 1]} for i in range(n_in + n_out)]
            e += n_in + n_out
            if len(value) != c:
                raise ValueError("envelope-invalid: a key index lies outside its section")
            keys.append({
                "time": sec["at"][k],
                "value": {"t": KIND_WORD[t["kind"]], "v": value[0] if c == 1 else value},
                "in_interp": words[sec["interp"][2 * k]], "out_interp": words[sec["interp"][2 * k + 1]],
                "in_ease": eases[:n_in], "out_ease": eases[n_in:],
                "continuous": bool(flags & 1), "auto_bezier": bool(flags & 2), "spatial_auto": bool(flags & 4),
                "spatial_continuous": bool(flags & 8), "roving": bool(flags & 16),
                "label": sec["label"][k],
                "spatial_in": sec["spatial"][6 * k:6 * k + 3], "spatial_out": sec["spatial"][6 * k + 3:6 * k + 6],
            })
        out.append((t["uid"], keys))
    return out


def read_baked(buf):
    """spec/layouts/core.expr.baked.layout.txt."""
    header, sec = envelope(buf, b"WKX4", "core.expr.baked")
    samples = header["samples"]
    tracks = {}
    for t in header["tracks"]:
        c = t["components"]
        flat = sec["value"][t["first_value"]:t["first_value"] + samples * c]
        if len(flat) != samples * c:
            raise ValueError("envelope-invalid: a baked track lies outside section value")
        tracks[(t["layer"], t["uid"])] = {"kind": t["kind"], "components": c, "values": [flat[i * c:(i + 1) * c] for i in range(samples)]}
    return {"comp": header["comp"], "rate": (header["rate_num"], header["rate_den"]), "first_frame": header["first_frame"],
            "frame_step": header["frame_step"], "samples": samples, "tracks": tracks,
            "unbaked": [(u["layer"], u["uid"], u["reason"]) for u in header.get("unbaked", [])]}


# ------------------------------------------------------------------------------------------
# The document (profile document 6.0)
# ------------------------------------------------------------------------------------------

class Document:
    def __init__(self, capsule):
        self.c = capsule
        self.lost = []
        self.project = capsule.json(capsule.primary["document"], "core.motion.project")
        self.items, self.comps, self.layer_comp = {}, {}, {}
        for entry in self.project["items"]:
            try:
                if entry["kind"] == "comp":
                    self._read_comp(entry)
                else:
                    self.items[entry["id"]] = capsule.json(entry["node"], "core.motion.item")
            except ValueError as e:
                self.lost.append((entry["node"], str(e)))
        self._baked = {}

    def _attach(self, node, tracks):
        """Give every property that names a track its keys (layout section 4)."""
        if node.get("node") == "Prop" or ("value" in node and "children" not in node):
            if "track" in node:
                i = node.pop("track")
                if tracks is not None and i < len(tracks) and tracks[i][0] == node["uid"]:
                    node["keys"] = tracks[i][1]
                else:
                    self.lost.append(("property %d" % node["uid"], "its keyframe track is not available: the static value is used"))
            return
        for child in node.get("children", []):
            self._attach(child, tracks)

    def _tracks(self, payload):
        if not payload.get("tracks"):
            return None
        try:
            return read_tracks(self.c.payload(payload["tracks"], "core.keyframe.tracks"))
        except ValueError as e:
            self.lost.append((payload["tracks"], str(e)))
            return None

    def _read_comp(self, entry):
        payload = self.c.json(entry["node"], "core.motion.comp")
        comp = payload["comp"]
        tracks = self._tracks(payload)
        for name in ("angle", "altitude"):
            prop = comp.get("global_light", {}).get(name)
            if prop:
                self._attach(prop, tracks)
        layers = []
        for ref in payload["layers"]:
            try:
                lp = self.c.json(ref["node"], "core.motion.layer")
                self._attach(lp["layer"]["props"], self._tracks(lp))
                layers.append(lp["layer"])
                self.layer_comp[lp["layer"]["id"]] = payload["id"]
            except ValueError as e:
                self.lost.append((ref["node"], str(e)))
        self.comps[payload["id"]] = {"id": payload["id"], "name": payload["name"], "comp": comp, "layers": layers, "node": entry["node"]}

    def baked(self, comp_id):
        """The baked expression values of a composition, when they are there and not stale."""
        if comp_id not in self._baked:
            got = None
            node = "comp-%d-baked" % comp_id
            edges = self.c.nodes.get(self.comps[comp_id]["node"], {}).get("edges", [])
            for e in edges:
                if e.get("role") == "baked-expressions" and self.c.nodes.get(e["to"], {}).get("type") == "core.expr.baked":
                    node = e["to"]
            if node in self.c.nodes:
                try:
                    if self.c.stale(node):
                        note("the baked expression values of composition %d are stale and were not used" % comp_id)
                    else:
                        got = read_baked(self.c.payload(node, "core.expr.baked"))
                except ValueError as e:
                    self.lost.append((node, str(e)))
            self._baked[comp_id] = got
        return self._baked[comp_id]


def child(group, match):
    for n in group.get("children", []):
        if n.get("match") == match:
            return n
    return None


def find(group, path):
    """A node of a property tree by a path of `match` names, or by uid."""
    if isinstance(path, int) or (isinstance(path, str) and path.isdigit()):
        uid = int(path)
        stack = [group]
        while stack:
            n = stack.pop()
            if n.get("uid") == uid and "value" in n:
                return n
            stack.extend(n.get("children", []))
        return None
    node = group
    for part in path.split("/"):
        node = child(node, part)
        if node is None:
            return None
    return node


def walk_props(group, prefix=""):
    for n in group.get("children", []):
        path = prefix + n["match"]
        if "children" in n or n.get("node") == "Group":
            for x in walk_props(n, path + "/"):
                yield x
        else:
            yield path, n


# ------------------------------------------------------------------------------------------
# Time (6.1, 6.2)
# ------------------------------------------------------------------------------------------

def frame_start(f, rate):
    num, den = rate["num"], rate["den"]
    return -((-f * TPS * den) // num)          # ceiling, exact


def frame_at(t, rate):
    return (t * rate["num"]) // (TPS * rate["den"])


def frame_count(comp):
    return frame_at(comp["duration"] - 1, comp["frame_rate"]) + 1


def layer_time(layer, t):
    d = t - layer["start_time"]
    stretch = layer["stretch"]
    if abs(stretch - 100.0) < 1e-9:
        return d
    return int(d * 100.0 / stretch)             # truncates toward zero


# ------------------------------------------------------------------------------------------
# Keyframes (6.3, 6.4)
# ------------------------------------------------------------------------------------------

def bez(p0, p1, p2, p3, u):
    v = 1.0 - u
    return v * v * v * p0 + 3.0 * v * v * u * p1 + 3.0 * v * u * u * p2 + u * u * u * p3


def bez_d(p0, p1, p2, p3, u):
    v = 1.0 - u
    return 3.0 * v * v * (p1 - p0) + 6.0 * v * u * (p2 - p1) + 3.0 * u * u * (p3 - p2)


def cbrt(x):
    return math.copysign(abs(x) ** (1.0 / 3.0), x)


def solve_u(x1, x2, x):
    """The u in [0, 1] with B(0, x1, x2, 1; u) = x."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    if x1 == 1.0 and x2 == 0.0:
        return 0.5 + cbrt((x - 0.5) * 0.25)
    u = x
    for _ in range(8):
        f = bez(0.0, x1, x2, 1.0, u) - x
        d = bez_d(0.0, x1, x2, 1.0, u)
        if abs(d) < 1e-12:
            break
        if abs(f / d) < 1e-12:
            return u
        n = u - f / d
        if not (0.0 <= n <= 1.0):
            break
        u = n
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) * 0.5
        if bez(0.0, x1, x2, 1.0, mid) < x:
            lo = mid
        else:
            hi = mid
    return (lo + hi) * 0.5


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def ease_progress(os_, oi, is_, ii, x):
    oi, ii = clamp(oi, 0.0, 1.0), clamp(ii, 0.0, 1.0)
    u = solve_u(oi, 1.0 - ii, x)
    return bez(0.0, os_ * oi, 1.0 - is_ * ii, 1.0, u)


def comps_of(value):
    t, v = value["t"], value["v"]
    if t == "Scalar":
        return [float(v)]
    if t in ("Vec2", "Vec3", "Color"):
        return [float(x) for x in v]
    if t == "Bool":
        return [1.0 if v else 0.0]
    if t == "Enum":
        return [float(v)]
    return []


def with_comps(value, c):
    t = value["t"]
    if t == "Scalar":
        return {"t": t, "v": c[0]}
    return {"t": t, "v": list(c)}


def interpolates(value):
    return value["t"] in ("Scalar", "Vec2", "Vec3", "Color", "Path", "Gradient")


def vec3(value):
    c = comps_of(value) + [0.0, 0.0, 0.0]
    return c[:3]


def secs(t):
    return t / TPS


def ease_of(keys, i, d, spatial, out):
    """The ease of key i on one side for dimension d (6.3), or along the path (6.4)."""
    k = keys[i]
    if k.get("auto_bezier") and 0 < i < len(keys) - 1:
        dt = max(secs(keys[i + 1]["time"]) - secs(keys[i - 1]["time"]), 1e-12)
        if spatial:
            a, c = vec3(keys[i - 1]["value"]), vec3(keys[i + 1]["value"])
            slope = math.sqrt(sum((c[j] - a[j]) ** 2 for j in range(3))) / dt
        else:
            a, c = comps_of(keys[i - 1]["value"]), comps_of(keys[i + 1]["value"])
            slope = ((c[d] if d < len(c) else 0.0) - (a[d] if d < len(a) else 0.0)) / dt
        return slope, 1.0 / 6.0
    lst = k.get("out_ease" if out else "in_ease") or []
    e = lst[d] if d < len(lst) else (lst[0] if lst else None)
    if e is None:
        return 0.0, 1.0 / 6.0
    return e["speed"], e["influence"]


GAUSS = [(0.0, 0.5688888888888889), (-0.5384693101056831, 0.4786286704993665), (0.5384693101056831, 0.4786286704993665),
         (-0.906179845938664, 0.2369268850561891), (0.906179845938664, 0.2369268850561891)]
ARC_N = 96


class SpatialSeg:
    def __init__(self, p):
        self.p = p
        self.table = [0.0]
        acc = 0.0
        for i in range(1, ARC_N + 1):
            acc += self.arc((i - 1) / ARC_N, i / ARC_N)
            self.table.append(acc)

    def point(self, u):
        p = self.p
        return [bez(p[0][k], p[1][k], p[2][k], p[3][k], u) for k in range(3)]

    def tangent_len(self, u):
        p = self.p
        return math.sqrt(sum(bez_d(p[0][k], p[1][k], p[2][k], p[3][k], u) ** 2 for k in range(3)))

    def arc(self, a, b):
        m, h = (a + b) * 0.5, (b - a) * 0.5
        return sum(w * self.tangent_len(m + h * x) for x, w in GAUSS) * h

    def length(self):
        return self.table[-1]

    def at_length(self, s):
        length = self.length()
        if not (length > 0.0 and math.isfinite(length)):
            return self.p[0]
        s = clamp(s, 0.0, length)
        i = 0
        while i < len(self.table) and self.table[i] < s:
            i += 1
        i = int(clamp(i, 1, ARC_N))
        a, b = self.table[i - 1], self.table[i]
        u0, u1 = (i - 1) / ARC_N, i / ARC_N
        u = u0 + ((s - a) / (b - a) if b > a else 0.0) * (u1 - u0)
        for _ in range(4):
            d = self.tangent_len(u)
            if d <= 1e-12:
                break
            e = a + self.arc(u0, u) - s
            u = clamp(u - e / d, u0, u1)
            if abs(e) <= 1e-12 * max(length, 1.0):
                break
        return self.point(u)


def spatial_tangents(keys, i):
    k = keys[i]
    if k.get("spatial_auto", True):
        if len(keys) < 2:
            return [0.0] * 3, [0.0] * 3
        a = vec3(keys[max(i - 1, 0)]["value"])
        c = vec3(keys[min(i + 1, len(keys) - 1)]["value"])
        out = [(c[j] - a[j]) / 6.0 for j in range(3)]
        return [-x for x in out], out
    return list(k.get("spatial_in", [0.0] * 3)), list(k.get("spatial_out", [0.0] * 3))


def on_chord(a, c, b):
    d = [b[j] - a[j] for j in range(3)]
    v = [c[j] - a[j] for j in range(3)]
    dd = sum(x * x for x in d)
    if dd <= 1e-24:
        return False
    t = sum(v[j] * d[j] for j in range(3)) / dd
    off = [v[j] - d[j] * t for j in range(3)]
    return 0.0 <= t <= 1.0 and sum(x * x for x in off) <= dd * 1e-18


def lerp_value(a, b, f):
    t = a["t"]
    if t == "Path" and b["t"] == "Path":
        pa, pb = a["v"], b["v"]
        if len(pa["vertices"]) != len(pb["vertices"]):
            return a if f < 1.0 else b
        mix = lambda x, y: [[p[0] + (q[0] - p[0]) * f, p[1] + (q[1] - p[1]) * f] for p, q in zip(x, y)]
        out = {"vertices": mix(pa["vertices"], pb["vertices"]), "in_tangents": mix(pa["in_tangents"], pb["in_tangents"]),
               "out_tangents": mix(pa["out_tangents"], pb["out_tangents"]), "closed": pa["closed"]}
        if pa.get("feather") or pb.get("feather"):
            note("feather points of an animated path are not interpolated by this program")
        return {"t": "Path", "v": out}
    if t == "Gradient" and b["t"] == "Gradient":
        ga, gb = a["v"], b["v"]
        if len(ga["colors"]) == len(gb["colors"]) and len(ga["opacities"]) == len(gb["opacities"]):
            colors = [[x[0] + (y[0] - x[0]) * f, [x[1][i] + (y[1][i] - x[1][i]) * f for i in range(4)]] for x, y in zip(ga["colors"], gb["colors"])]
            opac = [[x[0] + (y[0] - x[0]) * f, x[1] + (y[1] - x[1]) * f] for x, y in zip(ga["opacities"], gb["opacities"])]
            return {"t": "Gradient", "v": {"colors": colors, "opacities": opac}}
        return a if f < 1.0 else b
    ca, cb = comps_of(a), comps_of(b)
    if interpolates(a) and ca and len(ca) == len(cb):
        return with_comps(a, [x + (y - x) * f for x, y in zip(ca, cb)])
    return a if f < 1.0 else b


def segment_value(keys, i, t, spatial):
    a, b = keys[i], keys[i + 1]
    if a.get("out_interp", "Linear") == "Hold" or not interpolates(a["value"]):
        return a["value"]
    t0, t1 = secs(a["time"]), secs(b["time"])
    dur = max(t1 - t0, 1e-12)
    x = clamp((secs(t) - t0) / dur, 0.0, 1.0)
    lin_out = a.get("out_interp", "Linear") == "Linear"
    lin_in = b.get("in_interp", "Linear") != "Bezier"
    if spatial and a["value"]["t"] in ("Vec2", "Vec3"):
        p0, p3 = vec3(a["value"]), vec3(b["value"])
        out_t = spatial_tangents(keys, i)[1]
        in_t = spatial_tangents(keys, i + 1)[0]
        seg = SpatialSeg([p0, [p0[j] + out_t[j] for j in range(3)], [p3[j] + in_t[j] for j in range(3)], p3])
        length = seg.length()
        if (lin_out and lin_in) or length <= 1e-12:
            f = x
        else:
            so, io = (length / dur, 1.0 / 3.0) if lin_out else ease_of(keys, i, 0, True, True)
            si, ii = (length / dur, 1.0 / 3.0) if lin_in else ease_of(keys, i + 1, 0, True, False)
            f = ease_progress(so * dur / length, io, si * dur / length, ii, x)
        if on_chord(p0, seg.p[1], p3) and on_chord(p0, seg.p[2], p3):
            p = [p0[j] + (p3[j] - p0[j]) * f for j in range(3)]
        else:
            p = seg.at_length(f * length)
        return with_comps(a["value"], p[:len(comps_of(a["value"]))])
    if lin_out and lin_in:
        return lerp_value(a["value"], b["value"], x)
    ca, cb = comps_of(a["value"]), comps_of(b["value"])
    if not ca or len(ca) != len(cb):
        so, io = (1.0 / dur, 1.0 / 3.0) if lin_out else ease_of(keys, i, 0, False, True)
        si, ii = (1.0 / dur, 1.0 / 3.0) if lin_in else ease_of(keys, i + 1, 0, False, False)
        return lerp_value(a["value"], b["value"], ease_progress(so * dur, io, si * dur, ii, x))
    out = []
    for d in range(len(ca)):
        dv = cb[d] - ca[d]
        so, io = (dv / dur, 1.0 / 3.0) if lin_out else ease_of(keys, i, d, False, True)
        si, ii = (dv / dur, 1.0 / 3.0) if lin_in else ease_of(keys, i + 1, d, False, False)
        io, ii = clamp(io, 0.0, 1.0), clamp(ii, 0.0, 1.0)
        u = solve_u(io, 1.0 - ii, x)
        out.append(bez(ca[d], ca[d] + so * io * dur, cb[d] - si * ii * dur, cb[d], u))
    return with_comps(a["value"], out)


def keyed_value(prop, lt):
    """A property's keyframed value at layer time lt (6.3)."""
    keys = prop.get("keys") or []
    if not keys:
        return prop["value"]
    if len(keys) == 1 or lt <= keys[0]["time"]:
        return keys[0]["value"]
    if lt >= keys[-1]["time"]:
        return keys[-1]["value"]
    i = 0
    while i + 1 < len(keys) and keys[i + 1]["time"] <= lt:
        i += 1
    return segment_value(keys, i, lt, bool(prop.get("spatial")))


class Eval:
    """The values of one composition at one composition time."""

    def __init__(self, doc, comp_id, t):
        self.doc, self.comp_id, self.t = doc, comp_id, t
        self.entry = doc.comps[comp_id]
        self.comp = self.entry["comp"]
        self.layers = {l["id"]: l for l in self.entry["layers"]}

    def at(self, t):
        return Eval(self.doc, self.comp_id, t)

    def has_expression(self, prop):
        e = prop.get("expr")
        return bool(e and e.get("enabled") and e.get("text", "").strip())

    def value(self, layer, prop):
        v = keyed_value(prop, layer_time(layer, self.t))
        if not self.has_expression(prop):
            return v
        # No expression engine here: the baked samples are the expression's results (6.18.4).
        baked = self.doc.baked(self.comp_id)
        track = baked["tracks"].get((layer["id"], prop["uid"])) if baked else None
        if track is None:
            note("property %d of layer %d has an expression and no usable baked values: its keyframed value is used" % (prop["uid"], layer["id"]))
            return v
        f = frame_at(self.t, self.comp["frame_rate"])
        i = int(clamp((f - baked["first_frame"]) // baked["frame_step"], 0, baked["samples"] - 1))
        s = track["values"][i]
        if track["kind"] == "bool":
            return {"t": "Bool", "v": s[0] >= 0.5}
        if track["kind"] == "enum":
            return {"t": "Enum", "v": int(s[0])}
        return with_comps(v, s)

    def get(self, layer, group, match, default):
        p = child(group, match) if group else None
        if p is None or "value" not in p:
            return default
        return self.value(layer, p)["v"]

    def num(self, layer, group, match, default):
        v = self.get(layer, group, match, default)
        return float(v[0]) if isinstance(v, list) else float(v)

    def vec(self, layer, group, match, default):
        v = self.get(layer, group, match, default)
        v = list(v) if isinstance(v, list) else [v]
        return [float(x) for x in v] + [float(x) for x in default[len(v):]]

    # ---- transform (6.7) -------------------------------------------------------------------

    def is_3d(self, layer):
        return layer["switches"].get("three_d") or layer["source"]["type"] in ("Camera", "Light")

    def position(self, layer, tr):
        if child(tr, "positionX") is not None:
            return [self.num(layer, tr, "positionX", 0.0), self.num(layer, tr, "positionY", 0.0), self.num(layer, tr, "positionZ", 0.0)]
        return self.vec(layer, tr, "position", [0.0, 0.0, 0.0])

    def par(self, layer):
        s = layer["source"]
        own = 1.0
        if s["type"] in ("Footage", "Solid"):
            item = self.doc.items.get(s.get("item"))
            if item:
                kind = item["kind"]
                own = (kind.get("Solid") or kind.get("Footage") or {}).get("pixel_aspect", 1.0)
        elif s["type"] == "Comp" and s.get("item") in self.doc.comps:
            own = self.doc.comps[s["item"]]["comp"]["pixel_aspect"]
        cp = self.comp["pixel_aspect"]
        r = own / (cp if cp > 0.0 else 1.0)
        return r if (math.isfinite(r) and r > 0.0 and abs(r - 1.0) > 1e-9) else 1.0

    def local(self, layer, par):
        """The 2D local matrix [[a, b, tx], [c, d, ty]]."""
        tr = child(layer["props"], "transform")
        if tr is None:
            return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
        if self.is_3d(layer):
            note("layer %d is a 3D layer: this program places it as a 2D layer" % layer["id"])
        a = self.vec(layer, tr, "anchor", [0.0, 0.0, 0.0])
        p = self.position(layer, tr)
        s = self.vec(layer, tr, "scale", [100.0, 100.0, 100.0])
        r = self.num(layer, tr, "rotation", 0.0)
        if layer.get("auto_orient", "Off") == "AlongPath":
            pos = child(tr, "position")
            moving = pos is not None and (len(pos.get("keys") or []) > 1 or self.has_expression(pos))
            if moving:
                dt = int(round(0.005 * TPS))
                q0, q1 = self.at(self.t - dt).position(layer, tr), self.at(self.t + dt).position(layer, tr)
                d = [q1[j] - q0[j] for j in range(3)]
                n = math.sqrt(sum(x * x for x in d))
                if n > 1e-9:
                    r += math.degrees(math.atan2(d[1] / n, d[0] / n))
        c, sn = math.cos(math.radians(r)), math.sin(math.radians(r))
        sx, sy = s[0] / 100.0 * par, s[1] / 100.0
        # T(p) * R(r) * S * T(-a)
        m00, m01, m10, m11 = c * sx, -sn * sy, sn * sx, c * sy
        return [[m00, m01, p[0] - (m00 * a[0] + m01 * a[1])], [m10, m11, p[1] - (m10 * a[0] + m11 * a[1])]]

    def world(self, layer):
        m = self.local(layer, self.par(layer))
        cur, guard = layer.get("parent"), 0
        while cur is not None and guard < 64:
            guard += 1
            p = self.layers.get(cur)
            if p is None:
                break
            m = mat_mul(self.local(p, 1.0), m)
            cur = p.get("parent")
        return m

    def opacity(self, layer):
        tr = child(layer["props"], "transform")
        return self.num(layer, tr, "opacity", 100.0) / 100.0


def mat_mul(a, b):
    return [[a[0][0] * b[0][0] + a[0][1] * b[1][0], a[0][0] * b[0][1] + a[0][1] * b[1][1], a[0][0] * b[0][2] + a[0][1] * b[1][2] + a[0][2]],
            [a[1][0] * b[0][0] + a[1][1] * b[1][0], a[1][0] * b[0][1] + a[1][1] * b[1][1], a[1][0] * b[0][2] + a[1][1] * b[1][2] + a[1][2]]]


def mat_inv(m):
    det = m[0][0] * m[1][1] - m[0][1] * m[1][0]
    if abs(det) < 1e-300 or not math.isfinite(det):
        return None
    i00, i01, i10, i11 = m[1][1] / det, -m[0][1] / det, -m[1][0] / det, m[0][0] / det
    return [[i00, i01, -(i00 * m[0][2] + i01 * m[1][2])], [i10, i11, -(i10 * m[0][2] + i11 * m[1][2])]]


def mat_apply(m, x, y):
    return m[0][0] * x + m[0][1] * y + m[0][2], m[1][0] * x + m[1][1] * y + m[1][2]


# ------------------------------------------------------------------------------------------
# Pictures (6.8): premultiplied binary32 pixels
# ------------------------------------------------------------------------------------------

_F = struct.Struct("f")


def f32(x):
    """Round to binary32, as the profile's pixel arithmetic is."""
    return _F.unpack(_F.pack(x))[0]


class Image:
    def __init__(self, w, h, fill=None):
        self.w, self.h = w, h
        self.px = [list(fill) if fill else [0.0, 0.0, 0.0, 0.0] for _ in range(w * h)]

    def get(self, x, y):
        if x < 0 or y < 0 or x >= self.w or y >= self.h:
            return (0.0, 0.0, 0.0, 0.0)
        return self.px[y * self.w + x]

    def get_clamped(self, x, y):
        return self.px[int(clamp(y, 0, self.h - 1)) * self.w + int(clamp(x, 0, self.w - 1))]


def levels_of(doc):
    return {"Bpc8": 255.0, "Bpc16": 32768.0}.get(doc.project["settings"]["bit_depth"])


def quantize_px(p, levels):
    if levels is None:
        return p
    inv = f32(1.0 / levels)

    def q(v, hi):
        v = v if v == v else 0.0
        v = min(max(v, 0.0), hi)
        return f32(math.floor(f32(f32(v * levels) + 0.5)) * inv)

    a = q(p[3], 1.0)
    return [q(p[0], a), q(p[1], a), q(p[2], a), a]


def quantize(img, levels):
    if levels is not None:
        img.px = [quantize_px(p, levels) for p in img.px]


def sample_bilinear(img, x, y):
    fx, fy = x - 0.5, y - 0.5
    x0, y0 = math.floor(fx), math.floor(fy)
    tx, ty = f32(fx - x0), f32(fy - y0)
    x0, y0 = int(x0), int(y0)
    a, b, c, d = img.get(x0, y0), img.get(x0 + 1, y0), img.get(x0, y0 + 1), img.get(x0 + 1, y0 + 1)
    out = []
    for i in range(4):
        top = f32(a[i] + f32(f32(b[i] - a[i]) * tx))
        bot = f32(c[i] + f32(f32(d[i] - c[i]) * tx))
        out.append(f32(top + f32(f32(bot - top) * ty)))
    return out


def halve(src):
    w, h = max((src.w + 1) // 2, 1), max((src.h + 1) // 2, 1)
    out = Image(w, h)
    for y in range(h):
        for x in range(w):
            acc = [0.0] * 4
            for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
                p = src.get_clamped(2 * x + dx, 2 * y + dy)
                for i in range(4):
                    acc[i] = f32(acc[i] + p[i])
            out.px[y * w + x] = [f32(v * 0.25) for v in acc]
    return out


# ---- blending (6.9) --------------------------------------------------------------------------

BLEND_MODES = ["Normal", "Dissolve", "DancingDissolve", "Darken", "Multiply", "ColorBurn", "ClassicColorBurn", "LinearBurn", "DarkerColor",
               "Add", "Lighten", "Screen", "ColorDodge", "ClassicColorDodge", "LinearDodge", "LighterColor", "Overlay", "SoftLight",
               "HardLight", "LinearLight", "VividLight", "PinLight", "HardMix", "Difference", "ClassicDifference", "Exclusion", "Subtract",
               "Divide", "Hue", "Saturation", "Color", "Luminosity", "StencilAlpha", "StencilLuma", "SilhouetteAlpha", "SilhouetteLuma",
               "AlphaAdd", "LuminescentPremul"]
STENCIL = ("StencilAlpha", "StencilLuma", "SilhouetteAlpha", "SilhouetteLuma")
NOT_HDR = ("ColorDodge", "ClassicColorDodge", "SoftLight", "HardLight", "LinearLight", "VividLight", "PinLight", "HardMix", "Hue", "Saturation", "Color")
CLASSIC = {"ClassicColorDodge": 0.0, "ClassicDifference": 0.0, "ClassicColorBurn": 1.0}


def luminance(c):
    return f32(f32(f32(0.2126 * c[0]) + f32(0.7152 * c[1])) + f32(0.0722 * c[2]))


def _burn(b, s):
    if b >= 1.0:
        return 1.0
    if s <= 0.0:
        return 0.0
    return 1.0 - min((1.0 - b) / s, 1.0)


def _dodge(b, s):
    if b <= 0.0:
        return 0.0
    if s >= 1.0:
        return 1.0
    return min(b / (1.0 - s), 1.0)


def _hard_light(b, s):
    if s <= 0.5:
        return b * 2.0 * s
    k = 2.0 * s - 1.0
    return b + k - b * k


def _separable(mode, b, s):
    if mode == "Darken":
        return min(b, s)
    if mode == "Multiply":
        return b * s
    if mode == "ColorBurn":
        return _burn(b, s)
    if mode == "ClassicColorBurn":
        return 0.0 if s <= 0.0 else 1.0 - (1.0 - b) / s
    if mode == "LinearBurn":
        return max(b + s - 1.0, 0.0)
    if mode in ("Add", "LinearDodge"):
        return b + s
    if mode == "Lighten":
        return max(b, s)
    if mode == "Screen":
        return b + s - b * s
    if mode == "ColorDodge":
        return _dodge(b, s)
    if mode == "ClassicColorDodge":
        return 1.0 if s >= 1.0 else min(b / (1.0 - s), 1.0)
    if mode == "Overlay":
        return _hard_light(s, b)
    if mode == "SoftLight":
        if s <= 0.5:
            return b - (1.0 - 2.0 * s) * b * (1.0 - b)
        d = ((16.0 * b - 12.0) * b + 4.0) * b if b <= 0.25 else math.sqrt(max(b, 0.0))
        return b + (2.0 * s - 1.0) * (d - b)
    if mode == "HardLight":
        return _hard_light(b, s)
    if mode == "LinearLight":
        return clamp(b + 2.0 * s - 1.0, 0.0, 1.0)
    if mode == "VividLight":
        return _burn(b, 2.0 * s) if s <= 0.5 else _dodge(b, 2.0 * (s - 0.5))
    if mode == "PinLight":
        return min(b, 2.0 * s) if s <= 0.5 else max(b, 2.0 * s - 1.0)
    if mode == "HardMix":
        return 1.0 if b + s >= 1.0 else 0.0
    if mode in ("Difference", "ClassicDifference"):
        return abs(b - s)
    if mode == "Exclusion":
        return b + s - 2.0 * b * s
    if mode == "Subtract":
        return max(b - s, 0.0)
    if mode == "Divide":
        if s <= 0.0:
            return 1.0 if b > 0.0 else 0.0
        return b / s
    return s


def _lum(c):
    return 0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]


def _clip_color(c):
    l, n, x = _lum(c), min(c), max(c)
    o = list(c)
    if n < 0.0:
        o = [l + (v - l) * l / max(l - n, 1e-9) for v in o]
    if x > 1.0:
        o = [l + (v - l) * (1.0 - l) / max(x - l, 1e-9) for v in o]
    return o


def _set_lum(c, l):
    d = l - _lum(c)
    return _clip_color([c[0] + d, c[1] + d, c[2] + d])


def _sat(c):
    return max(c) - min(c)


def _set_sat(c, s):
    mx, mn = max(c), min(c)
    if mx - mn <= 1e-9:
        return [0.0, 0.0, 0.0]
    return [(v - mn) * s / (mx - mn) for v in c]


def _formula(mode, b, s):
    if mode == "Hue":
        return _set_lum(_set_sat(s, _sat(b)), _lum(b))
    if mode == "Saturation":
        return _set_lum(_set_sat(b, _sat(s)), _lum(b))
    if mode == "Color":
        return _set_lum(s, _lum(b))
    if mode == "Luminosity":
        return _set_lum(b, _lum(s))
    if mode == "DarkerColor":
        return s if luminance(s) < luminance(b) else b
    if mode == "LighterColor":
        return s if luminance(s) > luminance(b) else b
    return [_separable(mode, b[i], s[i]) for i in range(3)]


def hash_noise(x, y, seed):
    m = 0xFFFFFFFF
    h = ((x * 0x8DA6B343) & m) ^ ((y * 0xD8163841) & m) ^ ((seed * 0xCB1AB31F) & m)
    h ^= h >> 13
    h = (h * 0x5BD1E995) & m
    h ^= h >> 15
    return (h & 0x00FFFFFF) / 16777216.0


def blend_pixel(mode, d, s, noise):
    """D (the composition so far) and S (the layer, opacity applied), premultiplied -> out."""
    sa, da = s[3], d[3]
    if mode == "Normal":
        k = f32(1.0 - sa)
        return [f32(s[i] + f32(d[i] * k)) for i in range(4)]
    if mode in ("Dissolve", "DancingDissolve"):
        if sa <= 0.0 or noise >= sa:
            return list(d)
        inv = f32(1.0 / sa)
        return [f32(s[0] * inv), f32(s[1] * inv), f32(s[2] * inv), 1.0]
    if mode == "StencilAlpha":
        return [f32(v * sa) for v in d]
    if mode == "SilhouetteAlpha":
        k = f32(1.0 - sa)
        return [f32(v * k) for v in d]
    if mode in ("StencilLuma", "SilhouetteLuma"):
        l = luminance(s)
        k = l if mode == "StencilLuma" else f32(1.0 - l)
        return [f32(v * k) for v in d]
    if mode in ("AlphaAdd", "LuminescentPremul"):
        k = f32(1.0 - sa)
        rgb = [f32(s[i] + f32(d[i] * k)) for i in range(3)]
        a = min(f32(sa + da), 1.0) if mode == "AlphaAdd" else f32(f32(sa + da) - f32(sa * da))
        return rgb + [a]
    if sa <= 0.0:
        return list(d)
    if da <= 0.0:
        return list(s)
    cs = [f32(s[i] / sa) for i in range(3)]
    cb = [f32(d[i] / da) for i in range(3)]
    if mode in NOT_HDR:
        cs = [clamp(v, 0.0, 1.0) for v in cs]
        cb = [clamp(v, 0.0, 1.0) for v in cb]
    ao = f32(f32(sa + da) - f32(sa * da))
    out = []
    if mode in CLASSIC:
        n = CLASSIC[mode]
        b = _formula(mode, cb, [f32(n + f32(sa * f32(v - n))) for v in cs])
        for i in range(3):
            out.append(f32(f32(f32(1.0 - da) * s[i]) + f32(da * f32(b[i]))))
    else:
        b = _formula(mode, cb, cs)
        for i in range(3):
            out.append(f32(f32(f32(f32(1.0 - da) * s[i]) + f32(f32(1.0 - sa) * d[i])) + f32(f32(sa * da) * f32(b[i]))))
    return out + [ao]


def place(target, src, m, mode, opacity, seed, sampling="Bilinear"):
    """Draw picture `src` through matrix m (source pixels -> target pixels) into `target`
    with a blend mode and an opacity (6.9)."""
    if src.w == 0 or src.h == 0 or opacity <= 0.0:
        return
    opacity = f32(opacity)
    # the drawn rectangle: the mapped buffer rectangle, grown by 1, rounded outward
    corners = [mat_apply(m, cx, cy) for cx, cy in ((0.0, 0.0), (src.w, 0.0), (src.w, src.h), (0.0, src.h))]
    bx0 = max(math.floor(min(c[0] for c in corners) - 1.0), 0)
    by0 = max(math.floor(min(c[1] for c in corners) - 1.0), 0)
    bx1 = min(math.ceil(max(c[0] for c in corners) + 1.0), target.w)
    by1 = min(math.ceil(max(c[1] for c in corners) + 1.0), target.h)
    scale = math.sqrt(abs(m[0][0] * m[1][1] - m[0][1] * m[1][0]))
    f = 1.0
    if scale < 0.5:
        src, f, scale = halve(src), f * 0.5, scale * 2.0
        while scale < 0.5 and src.w > 1 and src.h > 1:
            src, f, scale = halve(src), f * 0.5, scale * 2.0
    inv = mat_inv(m)
    if inv is None:
        return
    inv = [[inv[0][0] * f, inv[0][1] * f, inv[0][2] * f], [inv[1][0] * f, inv[1][1] * f, inv[1][2] * f]]
    stencil = mode in STENCIL
    for y in range(target.h):
        for x in range(target.w):
            px, py = mat_apply(inv, x + 0.5, y + 0.5)
            i = y * target.w + x
            inside = bx0 <= x < bx1 and by0 <= y < by1
            if not inside or px < -1.0 or py < -1.0 or px > src.w + 1.0 or py > src.h + 1.0:
                if stencil:
                    target.px[i] = [0.0, 0.0, 0.0, 0.0] if mode in ("StencilAlpha", "StencilLuma") else blend_pixel(mode, target.px[i], [0.0] * 4, 0.5)
                continue
            if sampling == "Nearest":
                s = list(src.get(int(math.floor(px)), int(math.floor(py))))
            else:
                s = sample_bilinear(src, px, py)
            if s[3] <= 0.0 and not stencil:
                continue
            if opacity < 1.0:
                s = [f32(v * opacity) for v in s]
            n = hash_noise(x, y, seed) if mode in ("Dissolve", "DancingDissolve") else 0.5
            target.px[i] = blend_pixel(mode, target.px[i], s, n)


def blend_from(target, src, mode, opacity, seed):
    opacity = f32(opacity)
    for i, sp in enumerate(src.px):
        if sp[3] <= 0.0 and mode not in STENCIL:
            continue
        s = [f32(v * opacity) for v in sp]
        n = hash_noise(i % target.w, i // target.w, seed) if mode in ("Dissolve", "DancingDissolve") else 0.5
        target.px[i] = blend_pixel(mode, target.px[i], s, n)


# ------------------------------------------------------------------------------------------
# Coverage (6.10 step 1): the fraction of each pixel inside a set of closed outlines
# ------------------------------------------------------------------------------------------

SUB = 16            # sub-scanlines per pixel row; the horizontal overlap is exact


def flatten(path, m=None, steps=24):
    """A Path value as a closed polygon [(x, y)], through an optional 2D matrix."""
    v, it, ot = path["vertices"], path["in_tangents"], path["out_tangents"]
    n = len(v)
    pts = []
    if n == 0:
        return pts
    count = n if path.get("closed") else n - 1
    for i in range(count):
        a, b = v[i], v[(i + 1) % n]
        o, t = ot[i], it[(i + 1) % n]
        if o[0] == 0.0 and o[1] == 0.0 and t[0] == 0.0 and t[1] == 0.0:
            pts.append((a[0], a[1]))
            continue
        c1, c2 = (a[0] + o[0], a[1] + o[1]), (b[0] + t[0], b[1] + t[1])
        for k in range(steps):
            u = k / steps
            pts.append((bez(a[0], c1[0], c2[0], b[0], u), bez(a[1], c1[1], c2[1], b[1], u)))
    if not path.get("closed"):
        pts.append((v[-1][0], v[-1][1]))
    if m is not None:
        pts = [mat_apply(m, x, y) for x, y in pts]
    return pts


def coverage(polygons, w, h, even_odd=False):
    """Coverage of `polygons` (lists of points in pixel coordinates), w*h floats row by row."""
    cov = [0.0] * (w * h)
    edges = []
    for poly in polygons:
        for i in range(len(poly)):
            (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % len(poly)]
            if y0 != y1:
                edges.append((x0, y0, x1, y1))
    if not edges:
        return cov
    ymin = max(0, int(math.floor(min(min(e[1], e[3]) for e in edges))))
    ymax = min(h, int(math.ceil(max(max(e[1], e[3]) for e in edges))))
    weight = 1.0 / SUB
    for y in range(ymin, ymax):
        row = y * w
        for sub in range(SUB):
            sy = y + (sub + 0.5) / SUB
            xs = []
            for x0, y0, x1, y1 in edges:
                if (y0 <= sy < y1) or (y1 <= sy < y0):
                    xs.append((x0 + (sy - y0) * (x1 - x0) / (y1 - y0), 1 if y1 > y0 else -1))
            xs.sort()
            wind, start = 0, None
            for x, d in xs:
                before = (wind % 2 != 0) if even_odd else (wind != 0)
                wind += d
                after = (wind % 2 != 0) if even_odd else (wind != 0)
                if not before and after:
                    start = x
                elif before and not after and start is not None:
                    a, b = max(start, 0.0), min(x, float(w))
                    if b > a:
                        i0, i1 = int(math.floor(a)), int(math.ceil(b))
                        for px in range(i0, min(i1, w)):
                            cov[row + px] += (min(b, px + 1.0) - max(a, float(px))) * weight
                    start = None
    return [min(max(c, 0.0), 1.0) for c in cov]


def box_blur_1d(values, n, stride, count, radius):
    """One box pass of window 2*radius+1 along lines of `n` values, zero outside."""
    if radius == 0:
        return values
    out = list(values)
    norm = 1.0 / (2 * radius + 1)
    for line in range(count):
        base = line * (n if stride == 1 else 1)
        idx = [base + k * stride for k in range(n)]
        acc = sum(values[idx[k]] for k in range(0, min(radius + 1, n)))
        for k in range(n):
            out[idx[k]] = acc * norm
            if k + radius + 1 < n:
                acc += values[idx[k + radius + 1]]
            if k - radius >= 0:
                acc -= values[idx[k - radius]]
    return out


def box_radii(sigma, n=3):
    if sigma <= 0.0:
        return [0] * n
    w = math.sqrt(12.0 * sigma * sigma / n + 1.0)
    wl = int(math.floor(w))
    if wl % 2 == 0:
        wl -= 1
    wu = wl + 2
    m = (12.0 * sigma * sigma - n * wl * wl - 4.0 * n * wl - 3.0 * n) / (-4.0 * wl - 4.0)
    m = int(math.floor(m + 0.5)) if m >= 0 else -int(math.floor(-m + 0.5))
    return [max(((wl if i < m else wu) - 1) // 2, 0) for i in range(n)]


def feather(cov, w, h, fx, fy, linear):
    if linear:
        rx = [max(int(math.floor(fx / 2.0 + 0.5)), 1)] if fx > 0.0 else []
        ry = [max(int(math.floor(fy / 2.0 + 0.5)), 1)] if fy > 0.0 else []
    else:
        rx = box_radii(fx / 2.0) if fx / 2.0 > 0.05 else []
        ry = box_radii(fy / 2.0) if fy / 2.0 > 0.05 else []
    for r in rx:
        cov = box_blur_1d(cov, w, 1, h, r)
    for r in ry:
        cov = box_blur_1d(cov, h, w, w, r)
    return cov


# ------------------------------------------------------------------------------------------
# PNG stills (MINI-SPECS.md section 8): 8-bit grey, RGB, RGBA, palette; no interlace
# ------------------------------------------------------------------------------------------

def read_png(data):
    if data[:8] != bytes([137, 80, 78, 71, 13, 10, 26, 10]):
        raise ValueError("not a PNG")
    at, idat, plte, trns = 8, b"", None, None
    w = h = depth = ctype = interlace = 0
    while at < len(data):
        n = struct.unpack(">I", data[at:at + 4])[0]
        kind = data[at + 4:at + 8]
        body = data[at + 8:at + 8 + n]
        if kind == b"IHDR":
            w, h, depth, ctype, _c, _f, interlace = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat += body
        elif kind == b"PLTE":
            plte = body
        elif kind == b"tRNS":
            trns = body
        at += 12 + n
    if depth != 8 or interlace != 0 or ctype not in (0, 2, 3, 4, 6):
        raise ValueError("this program reads 8-bit non-interlaced PNG only")
    ch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    raw = zlib.decompress(idat)
    stride = w * ch
    rows, prev = [], bytearray(stride)
    for y in range(h):
        ft = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - ch] if i >= ch else 0
            b = prev[i]
            c = prev[i - ch] if i >= ch else 0
            if ft == 1:
                line[i] = (line[i] + a) & 255
            elif ft == 2:
                line[i] = (line[i] + b) & 255
            elif ft == 3:
                line[i] = (line[i] + ((a + b) >> 1)) & 255
            elif ft == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(line)
        prev = line
    out = []
    for line in rows:
        for x in range(w):
            p = line[x * ch:(x + 1) * ch]
            if ctype == 0:
                out.append((p[0], p[0], p[0], 255))
            elif ctype == 2:
                out.append((p[0], p[1], p[2], 255))
            elif ctype == 3:
                i = p[0]
                out.append((plte[3 * i], plte[3 * i + 1], plte[3 * i + 2], trns[i] if trns and i < len(trns) else 255))
            elif ctype == 4:
                out.append((p[0], p[0], p[0], p[1]))
            else:
                out.append((p[0], p[1], p[2], p[3]))
    return w, h, out


# ------------------------------------------------------------------------------------------
# The defined effects (6.12): written from the catalog's `definition` texts
# ------------------------------------------------------------------------------------------

def _hsl(r, g, b):
    mx, mn = max(r, g, b), min(r, g, b)
    l = (mx + mn) / 2.0
    if abs(mx - mn) < 1e-7:
        return 0.0, 0.0, l
    d = mx - mn
    s = d / (2.0 - mx - mn) if l > 0.5 else d / (mx + mn)
    if mx == r:
        h = ((g - b) / d + (6.0 if g < b else 0.0)) / 6.0
    elif mx == g:
        h = ((b - r) / d + 2.0) / 6.0
    else:
        h = ((r - g) / d + 4.0) / 6.0
    return h, s, l


def _rgb(h, s, l):
    if s <= 0.0:
        return [l, l, l]
    q = l * (1.0 + s) if l < 0.5 else l + s - l * s
    p = 2.0 * l - q

    def f(t):
        t = t - math.floor(t)
        if t < 1.0 / 6.0:
            return p + (q - p) * 6.0 * t
        if t < 0.5:
            return q
        if t < 2.0 / 3.0:
            return p + (q - p) * (2.0 / 3.0 - t) * 6.0
        return p

    return [f(h + 1.0 / 3.0), f(h), f(h - 1.0 / 3.0)]


def _round_half_away(v):
    return math.floor(v + 0.5) if v >= 0 else -math.floor(-v + 0.5)


def effect_pixel(effect, params, p):
    """One premultiplied pixel through a defined effect; None when this program has no
    definition of the effect."""
    r, g, b, a = p
    if effect == "ec.channel.invert":
        k = 1.0 - params.get("blend", 0.0) / 100.0
        ch = int(params.get("channel", 0))
        if ch == 12:
            a2 = 1.0 - a
            q = a2 / a if a > 0.0 else 0.0
            inv = [r * q, g * q, b * q, a2]
            return [p[i] + (inv[i] - p[i]) * k for i in range(4)]
        if a <= 0.0:
            return list(p)
        s = [r / a, g / a, b / a]
        if ch == 0:
            o = [1.0 - v for v in s]
        elif ch in (1, 2, 3):
            o = list(s)
            o[ch - 1] = 1.0 - o[ch - 1]
        elif 4 <= ch <= 7:
            h, sat, l = _hsl(*s)
            if ch in (4, 5):
                h = 1.0 - h
            if ch in (4, 6):
                l = 1.0 - l
            if ch in (4, 7):
                sat = 1.0 - sat
            o = _rgb(h, sat, l)
        else:
            y = 0.299 * s[0] + 0.587 * s[1] + 0.114 * s[2]
            i = 0.596 * s[0] - 0.274 * s[1] - 0.322 * s[2]
            q = 0.211 * s[0] - 0.523 * s[1] + 0.312 * s[2]
            if ch in (8, 9):
                y = 1.0 - y
            if ch in (8, 10):
                i = -i
            if ch in (8, 11):
                q = -q
            o = [max(0.0, y + 0.956 * i + 0.621 * q), max(0.0, y - 0.272 * i - 0.647 * q), max(0.0, y - 1.106 * i + 1.703 * q)]
        return [(s[j] + (o[j] - s[j]) * k) * a for j in range(3)] + [a]
    if effect not in ("ec.color.tint", "ec.color.tritone", "ec.stylize.posterize", "ec.stylize.threshold"):
        return None
    if a <= 0.0:
        return list(p)
    c = [r / a, g / a, b / a]
    y = 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    if effect == "ec.color.tint":
        black, white = params.get("black", [0.0, 0.0, 0.0, 1.0]), params.get("white", [1.0, 1.0, 1.0, 1.0])
        l, k = clamp(y, 0.0, 1.0), params.get("amount", 100.0) / 100.0
        out = [c[j] + ((black[j] + (white[j] - black[j]) * l) - c[j]) * k for j in range(3)]
    elif effect == "ec.color.tritone":
        hi, mid, lo = params["highlights"], params["midtones"], params["shadows"]
        l, k = clamp(y, 0.0, 1.0), 1.0 - params.get("blend", 0.0) / 100.0
        if l < 0.5:
            t = [lo[j] + (mid[j] - lo[j]) * (2.0 * l) for j in range(3)]
        else:
            t = [mid[j] + (hi[j] - mid[j]) * (2.0 * (l - 0.5)) for j in range(3)]
        out = [c[j] + (t[j] - c[j]) * k for j in range(3)]
    elif effect == "ec.stylize.posterize":
        # "All arithmetic in binary32": rounding decides here, so every step is rounded to it.
        n = f32(clamp(_round_half_away(params.get("level", 6.0)), 2, 255) - 1.0)
        out = [f32(_round_half_away(f32(clamp(f32(p[j] / a), 0.0, 1.0) * n)) / n) for j in range(3)]
        return [f32(out[0] * a), f32(out[1] * a), f32(out[2] * a), a]
    else:
        c32 = [f32(p[j] / a) for j in range(3)]
        v = 1.0 if luminance(c32) >= f32(f32(params.get("level", 127.5)) / 255.0) else 0.0
        out = [v, v, v]
    return [out[0] * a, out[1] * a, out[2] * a, a]


def _srgb_decode(v):
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def effect_patch(name):
    """The 16 x 12 input picture of a test vector (the catalog's `primitives`, E7)."""
    px = []
    for y in range(12):
        for x in range(16):
            if name == "patch-a":
                e = [x / 15.0, y / 11.0, ((5 * x + 3 * y) % 16) / 15.0]
                alpha = 1.0 if x < 12 else 0.5 if x < 14 else 0.0
            else:
                e = [y / 11.0, 1.0 - x / 15.0, 0.25]
                alpha = 1.0
            px.append([f32(_srgb_decode(v) * alpha) for v in e] + [alpha])
    return px


def check_effect_vectors(capsule):
    """Run this file's effect implementations on the catalog's test vectors. (This file
    implements the pixel-by-pixel effects it needs to draw frames; `effects_ref.py`, beside it,
    implements every definition a catalog can carry.)"""
    project = capsule.json(capsule.primary["document"], "core.motion.project")
    node = project.get("effect_catalog")
    results = []
    if not node:
        return results
    catalog = capsule.json(node, "core.effect.catalog")
    for e in catalog["effects"]:
        if e["rendering"] not in ("exact", "tolerance"):
            continue
        defaults = {p["id"]: p["default"]["v"] for p in e["params"]}
        for n, vec in enumerate(e.get("test_vectors", [])):
            params = dict(defaults)
            params.update(vec["params"])
            want = [int(v) for v in vec["output"].split(",")]
            worst, known = 0, (vec["width"], vec["height"]) == (16, 12)
            if known:
                for i, p in enumerate(effect_patch(vec["input"])):
                    got = effect_pixel(e["id"], params, p)
                    if got is None:
                        known = False
                        break
                    worst = max(worst, max(abs(int(_round_half_away(got[j] * 65536.0)) - want[4 * i + j]) for j in range(4)))
            results.append({"effect": e["id"], "vector": n, "implemented": known, "max_error": worst if known else None,
                            "tolerance": e["tolerance"], "agrees": known and worst <= e["tolerance"]})
    return results


# ------------------------------------------------------------------------------------------
# Rendering a composition frame (6.8 to 6.13, 6.16)
# ------------------------------------------------------------------------------------------

class Renderer:
    def __init__(self, doc):
        self.doc = doc
        self.levels = levels_of(doc)
        s = doc.project["settings"]
        if s.get("working_space") or s.get("blend_linear"):
            note("the project uses colour management or linear blending: this program composites the stored values unconverted")
        self.depth = 0

    # ---- a layer's source picture: (image, offset): layer point p is picture pixel p + offset --

    def color_px(self, rgb):
        return quantize_px([f32(rgb[0]), f32(rgb[1]), f32(rgb[2]), 1.0], self.levels)

    def source(self, ev, layer):
        s = layer["source"]
        t = s["type"]
        if t == "Solid":
            item = self.doc.items.get(s["item"])
            if not item or "Solid" not in item["kind"]:
                return None
            sol = item["kind"]["Solid"]
            if layer["switches"].get("adjustment"):
                return Image(sol["width"], sol["height"], [1.0, 1.0, 1.0, 1.0]), (0.0, 0.0), True
            return Image(sol["width"], sol["height"], self.color_px(sol["color"])), (0.0, 0.0), True
        if t == "Shape":
            contents = child(layer["props"], "contents")
            if contents is None:
                return None
            img, off = self.shapes(ev, layer, contents)
            return img, off, False
        if t == "Comp":
            nested = self.doc.comps.get(s["item"])
            if nested is None or self.depth > 16:
                return None
            lt = self.source_time(ev, layer)
            if not (0 <= lt < nested["comp"]["duration"]):
                return None
            if layer["switches"].get("collapse"):
                note("layer %d collapses transformations: this program draws the nested composition as a picture" % layer["id"])
            self.depth += 1
            img = self.comp_frame(s["item"], lt)
            self.depth -= 1
            return img, (0.0, 0.0), False
        if t == "Footage":
            item = self.doc.items.get(s["item"])
            foot = (item or {}).get("kind", {}).get("Footage")
            if not foot or not foot.get("has_video"):
                return None
            node = (foot.get("media") or {}).get("node")
            if not node or self.doc.c.nodes.get(node, {}).get("type") != "core.media.png" or foot["kind"] != "Still":
                note("layer %d shows footage this program does not decode (it reads PNG stills): nothing is drawn" % layer["id"])
                return None
            try:
                w, h, px = read_png(self.doc.c.payload(node))
            except ValueError as e:
                note("layer %d: %s" % (layer["id"], e))
                return None
            img = Image(w, h)
            alpha = foot.get("alpha", "Straight")
            for i, (r, g, b, a) in enumerate(px):
                c = [f32(r / 255.0), f32(g / 255.0), f32(b / 255.0)]
                a = f32(a / 255.0)
                if alpha == "Ignore":
                    img.px[i] = c + [1.0]
                elif alpha == "Premultiplied":
                    m, k = foot.get("premul_color", [0.0, 0.0, 0.0]), f32(1.0 - a)
                    img.px[i] = [max(f32(c[j] - f32(m[j] * k)), 0.0) for j in range(3)] + [a]
                else:
                    img.px[i] = [f32(c[j] * a) for j in range(3)] + [a]
            if (w, h) != (foot["width"], foot["height"]):
                note("layer %d: the picture is not the item's size; it is used unscaled" % layer["id"])
            return img, (0.0, 0.0), False
        if t == "Text":
            note("layer %d is a text layer: text layout is not defined by the profile and nothing is drawn" % layer["id"])
        elif t in ("Model", "Primitive"):
            note("layer %d is a 3D model: nothing is drawn" % layer["id"])
        return None

    def source_time(self, ev, layer):
        remap = child(layer["props"], "timeRemap")
        if remap is not None and "value" in remap:
            v = ev.value(layer, remap)["v"]
            x = float(v) * TPS
            return int(math.floor(x + 0.5)) if x >= 0 else -int(math.floor(-x + 0.5))
        return layer_time(layer, ev.t)

    # ---- shape layers (6.16) ---------------------------------------------------------------

    def shapes(self, ev, layer, contents):
        draws = []
        self._collect(ev, layer, contents, [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], 1.0, draws)
        draws = [d for d in draws if d["opacity"] > 0.0 and d["polys"]]
        if not draws:
            return Image(1, 1), (0.0, 0.0)
        xs = [x for d in draws for poly in d["polys"] for x, _y in poly]
        ys = [y for d in draws for poly in d["polys"] for _x, y in poly]
        x0, y0 = math.floor(min(xs)) - 2, math.floor(min(ys)) - 2
        w, h = int(math.ceil(max(xs)) - x0 + 2), int(math.ceil(max(ys)) - y0 + 2)
        img = Image(w, h)
        for d in reversed(draws):                      # the last paint is at the bottom
            polys = [[(x - x0, y - y0) for x, y in poly] for poly in d["polys"]]
            cov = coverage(polys, w, h, d["even_odd"])
            col = d["color"]
            for i, c in enumerate(cov):
                if c <= 0.0:
                    continue
                a = f32(f32(f32(c) * d["opacity"]) * col[3])
                if a <= 0.0:
                    continue
                src = [f32(col[0] * a), f32(col[1] * a), f32(col[2] * a), a]
                img.px[i] = blend_pixel(d["mode"], img.px[i], src, 0.5)
        return img, (-x0, -y0)

    def _collect(self, ev, layer, contents, xf, opacity, draws):
        """Returns the live paths (polygons in layer space) at the end of the list."""
        live = []
        for g in contents.get("children", []):
            if "children" not in g or not g.get("enabled", True):
                continue
            m = g["match"]
            path = None
            if m == "rect":
                w, h = [abs(v) for v in ev.vec(layer, g, "size", [100.0, 100.0])]
                cx, cy = ev.vec(layer, g, "position", [0.0, 0.0])
                if ev.num(layer, g, "roundness", 0.0) > 0.0:
                    note("rounded rectangle corners are drawn square by this program")
                x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
                path = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
            elif m == "ellipse":
                w, h = ev.vec(layer, g, "size", [100.0, 100.0])
                cx, cy = ev.vec(layer, g, "position", [0.0, 0.0])
                rx, ry, k = w / 2, h / 2, 0.5522847498
                path = flatten({"vertices": [[cx, cy - ry], [cx + rx, cy], [cx, cy + ry], [cx - rx, cy]],
                                "in_tangents": [[-rx * k, 0], [0, -ry * k], [rx * k, 0], [0, ry * k]],
                                "out_tangents": [[rx * k, 0], [0, ry * k], [-rx * k, 0], [0, -ry * k]], "closed": True})
            elif m == "star":
                star = int(ev.get(layer, g, "type", 0)) == 0
                n = int(math.floor(max(ev.num(layer, g, "points", 5.0), 3.0) + 0.5))
                verts = n * 2 if star else n
                cx, cy = ev.vec(layer, g, "position", [0.0, 0.0])
                rot = ev.num(layer, g, "rotation", 0.0)
                outer, inner = ev.num(layer, g, "outerRadius", 100.0), ev.num(layer, g, "innerRadius", 50.0)
                if ev.num(layer, g, "outerRoundness", 0.0) != 0.0 or ev.num(layer, g, "innerRoundness", 0.0) != 0.0:
                    note("polystar roundness is not drawn by this program")
                path = []
                for i in range(verts):
                    r = inner if (star and i % 2 == 1) else outer
                    a = math.radians(rot - 90.0) + 2.0 * math.pi * i / verts
                    path.append((cx + r * math.cos(a), cy + r * math.sin(a)))
            elif m == "path":
                p = child(g, "path")
                if p is not None:
                    path = flatten(ev.value(layer, p)["v"])
            if path is not None:
                if int(ev.get(layer, g, "direction", 0)) == 1:
                    path = list(reversed(path))
                live.append([mat_apply(xf, x, y) for x, y in path])
            elif m == "fill":
                col = ev.vec(layer, g, "color", [1.0, 1.0, 1.0, 1.0])
                mode = BLEND_MODES[int(ev.get(layer, g, "blend", 0))] if int(ev.get(layer, g, "blend", 0)) < len(BLEND_MODES) else "Normal"
                if mode in ("Dissolve", "DancingDissolve"):
                    note("a dissolve blend mode on a shape paint is not defined by the profile; drawn Normal")
                    mode = "Normal"
                draws.append({"polys": list(live), "color": [f32(col[0]), f32(col[1]), f32(col[2]), 1.0],
                              "opacity": f32(f32(ev.num(layer, g, "opacity", 100.0) / 100.0) * opacity),
                              "even_odd": int(ev.get(layer, g, "rule", 0)) == 1, "mode": mode})
            elif m == "group":
                inner = child(g, "contents")
                if inner is None:
                    continue
                tr = child(g, "transform")
                gm, op = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], 1.0
                if tr is not None:
                    a = ev.vec(layer, tr, "anchor", [0.0, 0.0])
                    p = ev.vec(layer, tr, "position", [0.0, 0.0])
                    s = ev.vec(layer, tr, "scale", [100.0, 100.0])
                    rot, skew, axis = ev.num(layer, tr, "rotation", 0.0), ev.num(layer, tr, "skew", 0.0), ev.num(layer, tr, "skewAxis", 0.0)
                    gm = mat_mul(_translate(p[0], p[1]), mat_mul(_rotate(rot), mat_mul(_skew(-skew, axis), mat_mul(_scale(s[0] / 100.0, s[1] / 100.0), _translate(-a[0], -a[1])))))
                    op = f32(ev.num(layer, tr, "opacity", 100.0) / 100.0)
                live.extend(self._collect(ev, layer, inner, mat_mul(xf, gm), f32(opacity * op), draws))
            elif m in ("stroke", "gfill", "gstroke"):
                note("shape strokes and gradients are not drawn by this program")
            elif m in ("trim", "pucker", "round", "offset", "twist", "zigzag", "wiggle", "merge", "repeater"):
                note("the shape path operator `%s` is not applied by this program" % m)
        return live

    # ---- masks (6.10) ----------------------------------------------------------------------

    def masks(self, ev, layer, img, offset):
        group = child(layer["props"], "masks")
        if group is None:
            return False
        active = []
        for g in group.get("children", []):
            kind = g.get("kind", {})
            if kind.get("kind") != "Mask" or not g.get("enabled", True) or kind.get("mode") == "None":
                continue
            p = child(g, "path")
            if p is None:
                continue
            path = ev.value(layer, p)["v"]
            if path.get("closed"):
                active.append((g, kind, path))
        if not active:
            return False
        n = img.w * img.h
        acc = [1.0 if active[0][1]["mode"] == "Subtract" else 0.0] * n
        first = True
        for g, kind, path in active:
            if path.get("feather"):
                note("variable-width mask feather is not defined by the profile; the plain feather is used")
            poly = [(x + offset[0], y + offset[1]) for x, y in flatten(path)]
            cov = coverage([poly], img.w, img.h)
            if abs(ev.num(layer, g, "expansion", 0.0)) > 0.01:
                note("mask expansion is not applied by this program")
            fx, fy = ev.vec(layer, g, "feather", [0.0, 0.0])
            if fx > 0.0 or fy > 0.0:
                cov = feather(cov, img.w, img.h, fx, fy, kind.get("feather_falloff") == "Linear")
            op = f32(ev.num(layer, g, "opacity", 100.0) / 100.0)
            mode = kind["mode"]
            if first and mode in ("Intersect", "Darken"):
                mode = "Add"
            first = False
            for i in range(n):
                c = f32(cov[i])
                if kind.get("inverted"):
                    c = f32(1.0 - c)
                c = f32(c * op)
                a = acc[i]
                if mode == "Add":
                    acc[i] = f32(f32(a + c) - f32(a * c))
                elif mode == "Subtract":
                    acc[i] = f32(a * f32(1.0 - c))
                elif mode == "Intersect":
                    acc[i] = f32(a * c)
                elif mode == "Lighten":
                    acc[i] = max(a, c)
                elif mode == "Darken":
                    acc[i] = min(a, c)
                elif mode == "Difference":
                    acc[i] = abs(f32(a - c))
        for i in range(n):
            img.px[i] = [f32(v * acc[i]) for v in img.px[i]]
        return True

    # ---- effects (6.12) --------------------------------------------------------------------

    def effects(self, ev, layer, img):
        group = child(layer["props"], "effects")
        if group is None or not layer["switches"].get("effects", True):
            return
        for g in group.get("children", []):
            kind = g.get("kind", {})
            if kind.get("kind") != "Effect" or not g.get("enabled", True):
                continue
            params = {p["match"]: ev.value(layer, p)["v"] for p in g.get("children", []) if "value" in p}
            if effect_pixel(kind["effect"], params, [0.0, 0.0, 0.0, 0.0]) is None:
                note("effect `%s` on layer %d: rendering is not defined (or not implemented here); the layer is drawn without it" % (kind["effect"], layer["id"]))
                continue
            img.px = [[f32(v) for v in effect_pixel(kind["effect"], params, p)] for p in img.px]
            quantize(img, self.levels)

    # ---- one layer, finished: source -> masks -> effects ------------------------------------

    def layer_picture(self, ev, layer):
        got = self.source(ev, layer)
        if got is None:
            return None
        img, offset, solid = got
        if self.masks(ev, layer, img, offset) or not solid:
            quantize(img, self.levels)
        if not layer["switches"].get("adjustment"):
            self.effects(ev, layer, img)
        if child(layer["props"], "layerStyles") is not None:
            note("layer styles are not defined by the profile; layer %d is drawn without them" % layer["id"])
        return img, offset

    def matrix(self, ev, layer, offset):
        """Picture pixels -> composition pixels."""
        return mat_mul(ev.world(layer), _translate(-offset[0], -offset[1]))

    def sampling(self, layer):
        return "Nearest" if layer["switches"].get("quality") == "Draft" else "Bilinear"

    def comp_frame(self, comp_id, t):
        entry = self.doc.comps[comp_id]
        comp = entry["comp"]
        ev = Eval(self.doc, comp_id, t)
        canvas = Image(comp["width"], comp["height"])
        active = lambda l: l["in_point"] <= t < l["out_point"]
        has_picture = lambda l: l["source"]["type"] not in ("Camera", "Light", "Null")
        any_solo = any(l["switches"].get("solo") and has_picture(l) and active(l) for l in entry["layers"])
        for layer in reversed(entry["layers"]):
            sw = layer["switches"]
            if not (active(layer) and sw.get("video", True) and has_picture(layer)) or layer.get("environment"):
                continue
            if sw.get("guide") or (any_solo and not sw.get("solo")):
                continue
            opacity = ev.opacity(layer)
            if sw.get("motion_blur") and comp.get("enable_motion_blur", True):
                note("motion blur is not rendered by this program")
            if sw.get("adjustment"):
                self.adjustment(ev, layer, canvas, opacity)
                quantize(canvas, self.levels)
                continue
            if opacity <= 0.0:
                continue
            got = self.layer_picture(ev, layer)
            if got is None:
                continue
            img, offset = got
            m = self.matrix(ev, layer, offset)
            matte = self.matte(ev, layer, canvas)
            if matte is None and not layer.get("preserve_transparency"):
                place(canvas, img, m, layer["blend_mode"], opacity, layer["id"] & 0xFFFFFFFF, self.sampling(layer))
            else:
                iso = Image(canvas.w, canvas.h)
                place(iso, img, m, "Normal", 1.0, layer["id"] & 0xFFFFFFFF, self.sampling(layer))
                if matte is not None:
                    mimg, kind = matte
                    for i, q in enumerate(mimg.px):
                        k = {"Alpha": q[3], "AlphaInverted": f32(1.0 - q[3]), "Luma": luminance(q), "LumaInverted": f32(1.0 - luminance(q))}[kind]
                        k = clamp(k, 0.0, 1.0)
                        iso.px[i] = [f32(v * k) for v in iso.px[i]]
                if layer.get("preserve_transparency"):
                    for i, q in enumerate(canvas.px):
                        iso.px[i] = [f32(v * q[3]) for v in iso.px[i]]
                blend_from(canvas, iso, layer["blend_mode"], opacity, layer["id"] & 0xFFFFFFFF)
            quantize(canvas, self.levels)
        return canvas

    def matte(self, ev, layer, canvas):
        tm = layer.get("track_matte")
        if not tm or tm["layer"] == layer["id"] or tm["layer"] not in ev.layers:
            return None
        m = ev.layers[tm["layer"]]
        mimg = Image(canvas.w, canvas.h)
        if m["in_point"] <= ev.t < m["out_point"]:
            got = self.layer_picture(ev, m)
            if got is not None:
                place(mimg, got[0], self.matrix(ev, m, got[1]), "Normal", ev.opacity(m), m["id"] & 0xFFFFFFFF, self.sampling(m))
        return mimg, tm["kind"]

    def adjustment(self, ev, layer, canvas, opacity):
        got = self.source(ev, layer)
        if got is None:
            return
        foot, offset, _solid = got
        self.masks(ev, layer, foot, offset)
        matte = Image(canvas.w, canvas.h)
        place(matte, foot, self.matrix(ev, layer, offset), "Normal", 1.0, 0)
        adjusted = Image(canvas.w, canvas.h)
        adjusted.px = [list(p) for p in canvas.px]
        self.effects(ev, layer, adjusted)
        op = f32(opacity)
        for i in range(len(canvas.px)):
            k = f32(matte.px[i][3] * op)
            canvas.px[i] = [f32(c + f32(f32(a - c) * k)) for c, a in zip(canvas.px[i], adjusted.px[i])]


def _translate(x, y):
    return [[1.0, 0.0, x], [0.0, 1.0, y]]


def _scale(x, y):
    return [[x, 0.0, 0.0], [0.0, y, 0.0]]


def _rotate(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [[c, -s, 0.0], [s, c, 0.0]]


def _skew(skew, axis):
    k = math.tan(math.radians(skew))
    return mat_mul(_rotate(axis), mat_mul([[1.0, k, 0.0], [0.0, 1.0, 0.0]], _rotate(-axis)))


def to_rgba8(img):
    """Straight alpha, 8 bit."""
    out = bytearray()
    for p in img.px:
        a = clamp(p[3], 0.0, 1.0)
        inv = f32(1.0 / p[3]) if a > 0.0 else 0.0
        for c in range(3):
            out.append(int(f32(f32(clamp(f32(p[c] * inv), 0.0, 1.0) * 255.0) + 0.5)))
        out.append(int(f32(f32(a * 255.0) + 0.5)))
    return bytes(out)


def to_rgb8_over_black(img):
    out = bytearray()
    for p in img.px:
        for c in range(3):
            out.append(int(f32(f32(clamp(p[c], 0.0, 1.0) * 255.0) + 0.5)))
    return bytes(out)


# ------------------------------------------------------------------------------------------
# Commands
# ------------------------------------------------------------------------------------------

def describe(doc):
    comps = []
    for cid in sorted(doc.comps):
        e = doc.comps[cid]
        comp = e["comp"]
        layers = []
        for l in e["layers"]:
            props = []
            for path, p in walk_props(l["props"]):
                keys = p.get("keys") or []
                expr = p.get("expr")
                if keys or expr:
                    props.append({"path": path, "uid": p["uid"], "kind": p["value"]["t"], "keys": len(keys),
                                  "key_times": [k["time"] for k in keys],
                                  "expression": expr["text"] if expr else None, "expression_enabled": bool(expr and expr.get("enabled"))})
            layers.append({"id": l["id"], "name": l["name"], "source": l["source"], "parent": l.get("parent"),
                           "blend_mode": l["blend_mode"], "in_point": l["in_point"], "out_point": l["out_point"],
                           "start_time": l["start_time"], "stretch": l["stretch"], "track_matte": l.get("track_matte"),
                           "three_d": bool(l["switches"].get("three_d")), "animated": props})
        comps.append({"id": cid, "name": e["name"], "width": comp["width"], "height": comp["height"], "frame_rate": comp["frame_rate"],
                      "duration": comp["duration"], "frames": frame_count(comp), "layers": layers})
    items = [{"id": i, "name": it["name"], "kind": list(it["kind"].keys())[0]} for i, it in sorted(doc.items.items())]
    return {"compositions": comps, "items": items}


def plain(value):
    return value["v"] if value["t"] in ("Scalar", "Vec2", "Vec3", "Color", "Bool", "Enum") else value


def report(doc, frames):
    out = describe(doc)
    values, matrices, baked = [], [], []
    for cid in sorted(doc.comps):
        e = doc.comps[cid]
        comp = e["comp"]
        n = frame_count(comp)
        # ten instants: nine equal steps across the composition, each floored to a tick
        ticks = [comp["duration"] * i // 10 + (i * 7919) % 1000 for i in range(10)]
        for l in e["layers"]:
            for path, p in walk_props(l["props"]):
                if p.get("keys"):
                    rows = [{"tick": t, "value": plain(keyed_value(p, layer_time(l, t)))} for t in ticks]
                    values.append({"comp": cid, "layer": l["id"], "path": path, "uid": p["uid"], "spatial": bool(p.get("spatial")), "samples": rows})
            if l["source"]["type"] not in ("Camera", "Light") and not l["switches"].get("three_d"):
                for f in sorted(set([0, min(10, n - 1), n - 1])):
                    t = frame_start(f, comp["frame_rate"])
                    ev = Eval(doc, cid, t)
                    matrices.append({"comp": cid, "layer": l["id"], "frame": f, "tick": t, "matrix": ev.world(l), "opacity": ev.opacity(l)})
        b = doc.baked(cid)
        if b:
            for (layer, uid), tr in sorted(b["tracks"].items()):
                baked.append({"comp": cid, "layer": layer, "uid": uid, "kind": tr["kind"], "first_frame": b["first_frame"],
                              "frame_step": b["frame_step"], "samples": b["samples"], "values": tr["values"]})
    out["values"], out["matrices"], out["baked"] = values, matrices, baked
    out["frames"] = []
    r = Renderer(doc)
    for cid, f in frames:
        comp = doc.comps[cid]["comp"]
        img = r.comp_frame(cid, frame_start(f, comp["frame_rate"]))
        out["frames"].append({"comp": cid, "frame": f, "width": img.w, "height": img.h,
                              "rgba_hex": to_rgba8(img).hex(), "rgb_over_black_hex": to_rgb8_over_black(img).hex()})
    out["effect_vectors"] = check_effect_vectors(doc.c)
    out["lost"] = [list(x) for x in doc.lost]
    out["notes"] = list(NOTES)
    return out


def main(argv):
    if len(argv) < 3:
        print(__doc__.strip())
        return 2
    capsule = Capsule(argv[1])
    cmd, args = argv[2], argv[3:]
    out_path = None
    if "--out" in args:
        i = args.index("--out")
        out_path = args[i + 1]
        del args[i:i + 2]
    if cmd == "effects":
        res = check_effect_vectors(capsule)
        for r in res:
            word = "agrees" if r["agrees"] else "DIFFERS" if r["implemented"] else "not implemented in this file (see effects_ref.py)"
            print("%-28s vector %-3s %s  largest difference %s / 65536 (tolerance %g)" % (r["effect"], r["vector"], word, r["max_error"], r["tolerance"]))
        return 0 if all(r["agrees"] or not r["implemented"] for r in res) else 1
    doc = Document(capsule)
    status = 0
    if cmd == "list":
        d = describe(doc)
        for c in d["compositions"]:
            fr = c["frame_rate"]
            print("composition %d %r  %dx%d  %d/%d fps  %d frames" % (c["id"], c["name"], c["width"], c["height"], fr["num"], fr["den"], c["frames"]))
            for l in c["layers"]:
                src = l["source"]["type"] + (" %d" % l["source"]["item"] if "item" in l["source"] else "")
                print("  layer %d %r  %s  parent %s  %s  [%d, %d)" % (l["id"], l["name"], src, l["parent"], l["blend_mode"], l["in_point"], l["out_point"]))
                for p in l["animated"]:
                    what = ("%d keys" % p["keys"]) if p["keys"] else "static"
                    if p["expression"] is not None:
                        what += ", expression %r%s" % (p["expression"], "" if p["expression_enabled"] else " (disabled)")
                    print("    %s (uid %d, %s): %s" % (p["path"], p["uid"], p["kind"], what))
    elif cmd == "value":
        cid, lid = int(args[0]), int(args[1])
        ev0 = Eval(doc, cid, 0)
        layer = ev0.layers[lid]
        prop = find(layer["props"], args[2])
        if prop is None:
            raise SystemExit("layer %d has no property %s" % (lid, args[2]))
        for t in args[3:]:
            v = Eval(doc, cid, int(t)).value(layer, prop)
            print(t, json.dumps(plain(v)))
    elif cmd == "matrix":
        cid, lid, t = int(args[0]), int(args[1]), int(args[2])
        ev = Eval(doc, cid, t)
        m = ev.world(ev.layers[lid])
        print(json.dumps(m))
    elif cmd == "baked":
        b = doc.baked(int(args[0]))
        if not b:
            print("no usable baked values")
            status = 1
        else:
            print("first_frame %d, frame_step %d, %d samples" % (b["first_frame"], b["frame_step"], b["samples"]))
            for (layer, uid), tr in sorted(b["tracks"].items()):
                print("layer %d property %d (%s): %s ..." % (layer, uid, tr["kind"], json.dumps(tr["values"][:4])))
            for u in b["unbaked"]:
                print("layer %d property %d: no samples (%s)" % u)
    elif cmd == "frame":
        cid, f = int(args[0]), int(args[1])
        comp = doc.comps[cid]["comp"]
        img = Renderer(doc).comp_frame(cid, frame_start(f, comp["frame_rate"]))
        data = to_rgb8_over_black(img) if "--rgb" in args else to_rgba8(img)
        if out_path:
            with open(out_path, "wb") as fh:
                fh.write(data)
        print("%d x %d, %d bytes, sha256 %s" % (img.w, img.h, len(data), hashlib.sha256(data).hexdigest()))
    elif cmd == "report":
        frames = []
        while "--frame" in args:
            i = args.index("--frame")
            cid, f = args[i + 1].split(":")
            frames.append((int(cid), int(f)))
            del args[i:i + 2]
        text = json.dumps(report(doc, frames), indent=1)
        if out_path:
            with open(out_path, "w", encoding="utf-8") as fh:
                fh.write(text)
        else:
            print(text)
    else:
        print(__doc__.strip())
        return 2
    for node, reason in doc.lost:
        print("LOST %s: %s" % (node, reason), file=sys.stderr)
        status = 1
    for n in NOTES:
        print("NOTE %s" % n, file=sys.stderr)
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv))
