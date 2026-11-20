#!/usr/bin/env python3
"""read_motion_comp.py -- reference reader of werk profile motion-comp/1 (werk release).

    python read_motion_comp.py PACKAGE [--json OUT]

Reads a motion-comp/1 package (directory or .werk zip) the way spec/PROFILE-MOTION-COMP.md
section 6.0 says, reads keyframes inline or from the owner's keyframe-tracks file
(spec/layouts/core.keyframe.tracks.layout.txt section 4), and prints the extraction
profiles/motion-comp/PROFILE.md ("What a reader outputs") defines, as canonical JSON (UTF-8,
keys sorted, indent 1): the project settings, the items, every composition with its layers
front first, each layer's static property values, and for every ANIMATED property its value at
every frame of the composition, evaluated by section 6.3 (Linear, Hold, Bezier with eases,
auto-Bezier). A spatial Vec2/Vec3 property whose segments are not all Linear (a motion path,
section 6.4) is reported, not evaluated. Every file it uses is checked against MANIFEST.json
first. Pure Python 3.8+ standard library; it runs nothing it finds in the package.

Exit status: 0 read, nothing dead; 1 read, with dead or missing nodes (listed under "dead");
2 not readable as a motion-comp/1 package.
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

PROFILE = "motion-comp/1"
TPS = 254016000000
NUMERIC = {"Scalar": 1, "Vec2": 2, "Vec3": 3, "Color": 4}
KIND_OF_TRACK = {"scalar": "Scalar", "vec2": "Vec2", "vec3": "Vec3", "color": "Color"}


def read_tracks(data):
    """layout section 4: every track back into keyframe objects."""
    h, s = envelope(data, b"WKX3")
    K = len(s["at"]) // 8
    at = struct.unpack("<%dq" % K, s["at"])
    vals = struct.unpack("<%dd" % (len(s["value"]) // 8), s["value"])
    eases = struct.unpack("<%dd" % (len(s["ease"]) // 8), s["ease"])
    words = h["interpolations"]
    out = []
    for t in h["tracks"]:
        c, e, keys = t["components"], t["first_ease"], []
        for j in range(t["keys"]):
            k = t["first_key"] + j
            v = list(vals[t["first_value"] + j * c:t["first_value"] + (j + 1) * c])
            fl = s["flags"][k]
            n_in, n_out = s["ease-count"][2 * k], s["ease-count"][2 * k + 1]
            ie = [{"speed": eases[2 * (e + q)], "influence": eases[2 * (e + q) + 1]} for q in range(n_in)]
            e += n_in
            oe = [{"speed": eases[2 * (e + q)], "influence": eases[2 * (e + q) + 1]} for q in range(n_out)]
            e += n_out
            kind = KIND_OF_TRACK[t["kind"]]
            keys.append({"time": at[k], "value": {"t": kind, "v": v[0] if kind == "Scalar" else v},
                         "in_interp": words[s["interp"][2 * k]], "out_interp": words[s["interp"][2 * k + 1]],
                         "auto_bezier": bool(fl & 2), "in_ease": ie, "out_ease": oe})
        out.append({"uid": t["uid"], "keys": keys})
    return out


def comps_of(value):
    v = value["v"]
    return [float(v)] if value["t"] == "Scalar" else [float(x) for x in v]


def bez(p0, p1, p2, p3, u):
    a = 1 - u
    return a * a * a * p0 + 3 * a * a * u * p1 + 3 * a * u * u * p2 + u * u * u * p3


def solve_u(io, ii, x):
    """The u in [0, 1] with B(0, io, 1 - ii, 1; u) = x (section 6.3): Newton from u = x, then
    bisection, to 1e-14."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    if io == 1 and ii == 1:
        d = (x - 0.5) / 4
        return 0.5 + (abs(d) ** (1.0 / 3) if d >= 0 else -(abs(d) ** (1.0 / 3)))
    p1, p2 = io, 1 - ii
    u = x
    for _ in range(20):
        f = bez(0, p1, p2, 1, u) - x
        if abs(f) < 1e-14:
            return u
        a = 1 - u
        d = 3 * a * a * p1 + 6 * a * u * (p2 - p1) + 3 * u * u * (1 - p2)
        if d <= 1e-12:
            break
        nu = u - f / d
        if not (0 <= nu <= 1):
            break
        u = nu
    lo, hi = 0.0, 1.0
    for _ in range(200):
        u = (lo + hi) / 2
        if bez(0, p1, p2, 1, u) < x:
            lo = u
        else:
            hi = u
        if hi - lo < 1e-15:
            break
    return (lo + hi) / 2


def ease_of(keys, i, d, side):
    """The ease of key i on `side` ('in' or 'out') for dimension d (section 6.3)."""
    k = keys[i]
    if k.get("auto_bezier") and 0 < i < len(keys) - 1:
        p, n = keys[i - 1], keys[i + 1]
        dt = max((n["time"] - p["time"]) / float(TPS), 1e-12)
        return (comps_of(n["value"])[d] - comps_of(p["value"])[d]) / dt, 1.0 / 6
    lst = k.get(side + "_ease") or []
    if d < len(lst):
        return lst[d]["speed"], lst[d]["influence"]
    if lst:
        return lst[0]["speed"], lst[0]["influence"]
    return 0.0, 1.0 / 6


def keyed(keys, t, spatial):
    """Value of a keyed numeric property at layer time t (ticks), or raise ValueError when the
    segment is a motion path this reader does not evaluate."""
    n = len(keys)
    if n == 1 or t <= keys[0]["time"]:
        return comps_of(keys[0]["value"])
    if t >= keys[-1]["time"]:
        return comps_of(keys[-1]["value"])
    i = max(j for j in range(n) if keys[j]["time"] <= t)
    a, b = keys[i], keys[i + 1]
    if a.get("out_interp", "Linear") == "Hold" or a["value"]["t"] not in NUMERIC:
        return comps_of(a["value"])
    ta, tb = a["time"] / float(TPS), b["time"] / float(TPS)
    dur = max(tb - ta, 1e-12)
    x = min(1.0, max(0.0, (t / float(TPS) - ta) / dur))
    lin_out = a.get("out_interp", "Linear") == "Linear"
    lin_in = b.get("in_interp", "Linear") != "Bezier"
    va, vb = comps_of(a["value"]), comps_of(b["value"])
    if spatial and a["value"]["t"] in ("Vec2", "Vec3") and not (lin_out and lin_in):
        raise ValueError("spatial segment with eases (section 6.4) not evaluated")
    out = []
    for d in range(len(va)):
        if lin_out and lin_in:
            out.append(va[d] + (vb[d] - va[d]) * x)
            continue
        dv = vb[d] - va[d]
        so, io = (dv / dur, 1.0 / 3) if lin_out else ease_of(keys, i, d, "out")
        si, ii = (dv / dur, 1.0 / 3) if lin_in else ease_of(keys, i + 1, d, "in")
        io, ii = min(1.0, max(0.0, io)), min(1.0, max(0.0, ii))
        u = solve_u(io, ii, x)
        out.append(bez(va[d], va[d] + so * io * dur, vb[d] - si * ii * dur, vb[d], u))
    return out


def props_of(group, prefix, out):
    for ch in group.get("children") or []:
        m = ch.get("match")
        path = m if not prefix else prefix + "/" + m
        if ch.get("node") == "Group":
            props_of(ch, path, out)
        elif ch.get("node") == "Prop":
            out.append((path, ch))


def read(path):
    pkg = Package(path)
    m = pkg.manifest
    if m.get("profile") != PROFILE:
        raise Refusal("profile is %r, not %s" % (m.get("profile"), PROFILE))
    dead, notes = [], []
    pid = (m.get("primary") or {}).get("document")
    try:
        project = pkg.json_payload(pid)
    except Dead as e:
        raise Refusal("the structure node is unreadable: %s" % e)

    def get(nid):
        try:
            return pkg.json_payload(nid)
        except (Dead, ValueError) as e:
            dead.append({"node": nid, "why": str(e)})
            return None

    items, comps = [], []
    for it in project.get("items") or []:
        if it["kind"] == "comp":
            continue
        p = get(it["node"])
        if p is not None:
            items.append({"id": it["id"], "node": it["node"], "name": p.get("name"), "kind": p.get("kind")})
    for it in project.get("items") or []:
        if it["kind"] != "comp":
            continue
        c = get(it["node"])
        if c is None:
            continue
        s = c["comp"]
        rate = s["frame_rate"]
        nframes = int(s["duration"] * rate["num"] // (TPS * rate["den"]))
        layers = []
        for ent in c.get("layers") or []:
            p = get(ent["node"])
            if p is None:
                continue
            L = p["layer"]
            tracks = None
            if p.get("tracks"):
                try:
                    _r, raw = pkg.payload(p["tracks"])
                    tracks = read_tracks(raw)
                except (Dead, KeyError, ValueError, struct.error) as e:
                    dead.append({"node": p["tracks"], "why": str(e)})
                    notes.append("%s: keyframe tracks dead, animated properties keep their static value" % ent["node"])
            plist = []
            props_of(L["props"], "", plist)
            static, animated = {}, {}
            for pth, pr in plist:
                keys = pr.get("keys")
                if "track" in pr and tracks is not None:
                    tr = tracks[pr["track"]] if pr["track"] < len(tracks) else None
                    if tr is None or tr["uid"] != pr["uid"]:
                        notes.append("%s %s: track binding lost, static value used" % (ent["node"], pth))
                    else:
                        keys = tr["keys"]
                if not keys or pr["value"]["t"] not in NUMERIC:
                    static[pth] = pr["value"]
                    continue
                series = []
                for f in range(nframes):
                    ct = f * TPS * rate["den"] // rate["num"]
                    lt = (ct - L.get("start_time", 0)) * 100.0 / L.get("stretch", 100.0)
                    try:
                        v = keyed(keys, lt, bool(pr.get("spatial")))
                        series.append(v[0] if pr["value"]["t"] == "Scalar" else v)
                    except ValueError as e:
                        notes.append("%s %s: %s" % (ent["node"], pth, e))
                        series = None
                        break
                animated[pth] = series
            layers.append({"id": L["id"], "node": ent["node"], "name": L.get("name"), "source": L.get("source"),
                           "in_point": L.get("in_point"), "out_point": L.get("out_point"),
                           "start_time": L.get("start_time"), "stretch": L.get("stretch"),
                           "blend_mode": L.get("blend_mode"), "parent": L.get("parent"),
                           "static": static, "animated": animated})
        comps.append({"id": c["id"], "node": it["node"], "name": c.get("name"),
                      "width": s["width"], "height": s["height"], "frame_rate": rate,
                      "duration": s["duration"], "frames": nframes, "layers": layers})
    nver, bad = pkg.verify_all()
    return {"profile": PROFILE, "settings": project.get("settings"), "items": items, "comps": comps,
            "fonts": project.get("fonts") or [], "notes": notes,
            "dead": sorted(dead, key=lambda d: str(d["node"])), "files_verified": nver, "file_failures": bad}


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("package"); ap.add_argument("--json")
    a = ap.parse_args(argv)
    try:
        res = read(a.package)
    except Refusal as e:
        sys.stderr.write("refused: %s\n" % e)
        return 2
    emit(res, a.json)
    return 1 if (res["dead"] or res["file_failures"]) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
