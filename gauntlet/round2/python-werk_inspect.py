#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
werk_inspect.py -- open, verify, extract from and explain a .werk package
(profile image/1).

Everything this program knows about the format was read out of the package
itself, in this order:

  README.txt                       -> "start with spec/README.md, row 0"
  spec/README.md                   -> read-in-this-order table
  MANIFEST.json (profile key)      -> "image/1"
  spec/PROFILE-IMAGE.md            -> profile 2 rules, node families, fallbacks
  spec/SPEC.md  3.11-3.13, 5, 6, 1, 2 -> recipe/disclosure/embedding doctrine,
                                      signature message bytes, S-14/S-15/S-18
  spec/MINI-SPECS.md  3, 5, 11, 12 -> canonical JSON, zip, what gets hashed,
                                      Ed25519 parameters + test vector
  spec/layouts/ENVELOPE.layout.txt -> the envelope + the MessagePack subset
  spec/layouts/embedding.layout.txt-> WKEM, and werk.descriptor.labhog/1

No third-party format knowledge is used. numpy/Pillow are used only as fast
array/PNG plumbing for the optional descriptor recomputation; the arithmetic
is the layout file's.

Usage:  python werk_inspect.py [path/to/artifact.werk] [--out DIR] [--no-recompute]
"""

import hashlib
import json
import math
import os
import struct
import sys
import zipfile

# ===========================================================================
# 0. small output helpers
# ===========================================================================

_OK, _BAD, _NOTE = "PASS", "FAIL", "note"


class Report(object):
    def __init__(self):
        self.checks = []

    def check(self, ok, name, detail=""):
        self.checks.append((bool(ok), name, detail))
        print("  [%s] %s%s" % (_OK if ok else _BAD, name,
                               ("  -- " + detail) if detail else ""))
        return ok

    def note(self, name, detail=""):
        self.checks.append((None, name, detail))
        print("  [%s] %s%s" % (_NOTE, name,
                               ("  -- " + detail) if detail else ""))

    def summary(self):
        hard = [c for c in self.checks if c[0] is not None]
        failed = [c for c in hard if not c[0]]
        return len(hard), len(failed), failed


def head(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def sub(title):
    print("\n--- %s ---" % title)


def wrap(text, width=76, indent="    "):
    out, line = [], ""
    for word in str(text).split():
        if len(line) + len(word) + 1 > width:
            out.append(indent + line)
            line = word
        else:
            line = (line + " " + word).strip()
    if line:
        out.append(indent + line)
    return "\n".join(out)


# ===========================================================================
# 1. MessagePack subset  (ENVELOPE.layout.txt section 4)
#    All multi-byte integers/floats INSIDE MessagePack are BIG-ENDIAN.
# ===========================================================================

_MP_BANNED = {0xC1, 0xC7, 0xC8, 0xC9, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8}


class MsgpackError(Exception):
    pass


def mp_decode(buf):
    val, off = _mp_read(buf, 0)
    if off != len(buf):
        raise MsgpackError("trailing bytes after header value (%d of %d)"
                           % (off, len(buf)))
    return val


def _mp_read(b, o):
    if o >= len(b):
        raise MsgpackError("truncated at offset %d" % o)
    c = b[o]
    if c in _MP_BANNED:
        raise MsgpackError("banned msgpack format byte 0x%02x at %d "
                           "(ENVELOPE section 4.2)" % (c, o))
    o += 1
    if c <= 0x7F:
        return c, o
    if c >= 0xE0:
        return c - 256, o
    if 0xA0 <= c <= 0xBF:
        n = c & 0x1F
        return b[o:o + n].decode("utf-8"), o + n
    if 0x90 <= c <= 0x9F:
        return _mp_seq(b, o, c & 0x0F, "array")
    if 0x80 <= c <= 0x8F:
        return _mp_seq(b, o, c & 0x0F, "map")
    if c == 0xC0:
        return None, o
    if c == 0xC2:
        return False, o
    if c == 0xC3:
        return True, o
    if c in (0xCC, 0xCD, 0xCE, 0xCF):
        n = 1 << (c - 0xCC)
        return int.from_bytes(b[o:o + n], "big", signed=False), o + n
    if c in (0xD0, 0xD1, 0xD2, 0xD3):
        n = 1 << (c - 0xD0)
        return int.from_bytes(b[o:o + n], "big", signed=True), o + n
    if c == 0xCA:
        return struct.unpack_from(">f", b, o)[0], o + 4
    if c == 0xCB:
        return struct.unpack_from(">d", b, o)[0], o + 8
    if c in (0xD9, 0xDA, 0xDB):
        w = 1 << (c - 0xD9)
        n = int.from_bytes(b[o:o + w], "big")
        o += w
        return b[o:o + n].decode("utf-8"), o + n
    if c in (0xC4, 0xC5, 0xC6):
        w = 1 << (c - 0xC4)
        n = int.from_bytes(b[o:o + w], "big")
        o += w
        return bytes(b[o:o + n]), o + n
    if c in (0xDC, 0xDD):
        w = 2 if c == 0xDC else 4
        n = int.from_bytes(b[o:o + w], "big")
        return _mp_seq(b, o + w, n, "array")
    if c in (0xDE, 0xDF):
        w = 2 if c == 0xDE else 4
        n = int.from_bytes(b[o:o + w], "big")
        return _mp_seq(b, o + w, n, "map")
    raise MsgpackError("unknown msgpack format byte 0x%02x at %d" % (c, o - 1))


def _mp_seq(b, o, n, kind):
    if kind == "array":
        out = []
        for _ in range(n):
            v, o = _mp_read(b, o)
            out.append(v)
        return out, o
    out = {}
    for _ in range(n):
        k, o = _mp_read(b, o)
        v, o = _mp_read(b, o)
        if k in out:
            raise MsgpackError("duplicate header key %r" % (k,))
        out[k] = v
    return out, o


# ===========================================================================
# 2. Ed25519 verify, pure  (MINI-SPECS.md section 12)
# ===========================================================================

_P = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493
_D = (-121665 * pow(121666, _P - 2, _P)) % _P
_I = pow(2, (_P - 1) // 4, _P)


def _recover_x(y, sign):
    if y >= _P:
        return None
    u = (y * y - 1) % _P
    v = (_D * y * y + 1) % _P
    x = (u * pow(v, 3, _P) * pow(u * pow(v, 7, _P), (_P - 5) // 8, _P)) % _P
    if (v * x * x - u) % _P != 0:
        if (v * x * x + u) % _P == 0:
            x = (x * _I) % _P
        else:
            return None
    if x == 0 and sign == 1:
        return None
    if (x & 1) != sign:
        x = _P - x
    return x


def _decompress(b32):
    y = int.from_bytes(b32, "little") & ((1 << 255) - 1)
    sign = b32[31] >> 7
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, (x * y) % _P)


_B = None


def _basepoint():
    global _B
    if _B is None:
        y = (4 * pow(5, _P - 2, _P)) % _P
        x = _recover_x(y, 0)
        _B = (x, y, 1, (x * y) % _P)
    return _B


def _add(p, q):
    x1, y1, z1, t1 = p
    x2, y2, z2, t2 = q
    a = ((y1 - x1) * (y2 - x2)) % _P
    b = ((y1 + x1) * (y2 + x2)) % _P
    c = (t1 * 2 * _D * t2) % _P
    d = (z1 * 2 * z2) % _P
    e, f, g, h = b - a, d - c, d + c, b + a
    return ((e * f) % _P, (g * h) % _P, (f * g) % _P, (e * h) % _P)


def _mul(p, n):
    q = (0, 1, 1, 0)
    while n > 0:
        if n & 1:
            q = _add(q, p)
        p = _add(p, p)
        n >>= 1
    return q


def _eq(p, q):
    x1, y1, z1, _ = p
    x2, y2, z2, _ = q
    return (x1 * z2 - x2 * z1) % _P == 0 and (y1 * z2 - y2 * z1) % _P == 0


def ed25519_verify(pub32, sig64, msg):
    """RFC 8032 pure Ed25519 verify. Public inputs only -> non-constant-time
    ladder is explicitly permitted here (MINI-SPECS section 12)."""
    if len(pub32) != 32 or len(sig64) != 64:
        return False
    r_b, s_b = sig64[:32], sig64[32:]
    s = int.from_bytes(s_b, "little")
    if s >= _L:                       # canonical S -- not optional
        return False
    A = _decompress(pub32)
    R = _decompress(r_b)
    if A is None or R is None:
        return False
    k = int.from_bytes(hashlib.sha512(r_b + pub32 + msg).digest(), "little") % _L
    lhs = _mul(_basepoint(), s)                 # cofactorless form (stricter)
    rhs = _add(R, _mul(A, k))
    if _eq(lhs, rhs):
        return True
    return _eq(_mul(lhs, 8), _mul(rhs, 8))      # cofactor-8 form


def ed25519_selftest():
    """RFC 8032 test vector, quoted verbatim in MINI-SPECS section 12."""
    pk = bytes.fromhex(
        "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
    sg = bytes.fromhex(
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555f"
        "b8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b")
    return ed25519_verify(pk, sg, b"") and not ed25519_verify(pk, sg, b"x")


# ===========================================================================
# 3. canonical JSON  (MINI-SPECS.md section 3)  -- used only by input_hash
# ===========================================================================

def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha256_hex(b):
    return hashlib.sha256(b).hexdigest()


# ===========================================================================
# 4. envelope reader  (ENVELOPE.layout.txt sections 1, 3, 5, 6, 7)
# ===========================================================================

_DTYPE_SIZE = {"u8": 1, "i8": 1, "u16": 2, "i16": 2, "u32": 4, "i32": 4,
               "u64": 8, "i64": 8, "f32": 4, "f64": 8}
_DTYPE_NP = {"u8": "<u1", "i8": "<i1", "u16": "<u2", "i16": "<i2",
             "u32": "<u4", "i32": "<i4", "u64": "<u8", "i64": "<i8",
             "f32": "<f4", "f64": "<f8"}
_MAGIC_KIND = {b"WKFF": "core.field.flow", b"WKRP": "core.pose.rest",
               b"WKAC": "core.anim.clip", b"WKSK": "core.skeleton",
               b"WKEM": "core.embedding"}


class EnvelopeError(Exception):
    pass


def read_envelope(data, report=None, label="envelope"):
    """Normative pseudocode, ENVELOPE.layout.txt section 7. Every failure is
    an EnvelopeError -> caller marks the node dead and carries on (law 3)."""
    def chk(cond, msg):
        if not cond:
            raise EnvelopeError(msg)

    chk(len(data) >= 12, "file shorter than the 12-byte fixed prefix")
    magic = bytes(data[0:4])
    version = struct.unpack_from("<I", data, 4)[0]
    header_len = struct.unpack_from("<I", data, 8)[0]
    chk(12 + header_len <= len(data), "header_len runs past end of file")
    header = mp_decode(data[12:12 + header_len])
    chk(isinstance(header, dict), "header is not a MessagePack map")

    for k in ("kind", "endianness", "payload_origin", "payload_size",
              "sections"):
        chk(k in header, "mandatory header key %r missing" % k)
    chk(header["endianness"] == "le",
        "endianness is %r, must be 'le'" % header["endianness"])
    if magic in _MAGIC_KIND:
        chk(header["kind"] == _MAGIC_KIND[magic],
            "kind %r does not match magic %r" % (header["kind"], magic))

    P = 16 * ((12 + header_len + 15) // 16)
    chk(header["payload_origin"] == P,
        "declared payload_origin %d != computed %d"
        % (header["payload_origin"], P))
    chk(P + header["payload_size"] == len(data),
        "payload_origin+payload_size (%d) != file size (%d)"
        % (P + header["payload_size"], len(data)))
    chk(all(x == 0 for x in data[12 + header_len:P]),
        "padding between header and payload is not all zero")

    secs, prev_end = [], None
    for i, s in enumerate(header["sections"]):
        for k in ("name", "offset", "size", "dtype", "shape", "stride"):
            chk(k in s, "section %d missing key %r" % (i, k))
        off, size, dt, shape, stride = (s["offset"], s["size"], s["dtype"],
                                        list(s["shape"]), s["stride"])
        chk(off % 16 == 0, "section %r offset %d is not 16-aligned"
            % (s["name"], off))
        chk(off + size <= len(data),
            "section %r runs past end of file" % s["name"])
        if i == 0:
            chk(off == P, "section 0 does not start at payload_origin")
        else:
            chk(0 <= off - prev_end <= 15,
                "gap of %d bytes before section %r (0..15 permitted)"
                % (off - prev_end, s["name"]))
            chk(all(x == 0 for x in data[prev_end:off]),
                "inter-section padding before %r is not zero" % s["name"])
        esz = _DTYPE_SIZE.get(dt, stride)          # "record" -> stride
        if stride == esz:
            want = stride
            for d in shape:
                want *= d
            chk(size == want, "section %r: first-branch size %d != %d"
                % (s["name"], size, want))
        else:
            chk(stride >= esz * shape[-1],
                "section %r: stride %d < esz*shape[-1] %d"
                % (s["name"], stride, esz * shape[-1]))
            want = stride
            for d in shape[:-1]:
                want *= d
            chk(size == want, "section %r: second-branch size %d != %d"
                % (s["name"], size, want))
        prev_end = off + size
        secs.append(dict(s, _bytes=bytes(data[off:off + size])))

    last_end16 = 16 * ((prev_end + 15) // 16) if prev_end is not None else P
    chk(last_end16 == P + header["payload_size"],
        "last section end rounded to 16 (%d) != payload end (%d)"
        % (last_end16, P + header["payload_size"]))
    return magic, version, header, secs


def section_array(sec):
    """Materialise a section as a numpy array honouring the declared stride."""
    import numpy as np
    dt = sec["dtype"]
    if dt not in _DTYPE_NP:
        return None
    esz, shape, stride = _DTYPE_SIZE[dt], list(sec["shape"]), sec["stride"]
    raw = np.frombuffer(sec["_bytes"], dtype="<u1")
    if stride == esz:
        return np.frombuffer(sec["_bytes"], dtype=_DTYPE_NP[dt]).reshape(shape)
    n = 1
    for d in shape[:-1]:
        n *= d
    view = raw.reshape(n, stride)[:, :esz * shape[-1]]
    arr = np.ascontiguousarray(view).view(_DTYPE_NP[dt])
    return arr.reshape(shape)


# ===========================================================================
# 5. the descriptor werk.descriptor.labhog/1
#    (embedding.layout.txt section 4, arithmetic in binary64)
# ===========================================================================

def labhog(png_bytes):
    import numpy as np
    from PIL import Image
    import io

    im = Image.open(io.BytesIO(png_bytes))
    im = im.convert("RGB")                    # alpha, if any, is IGNORED
    src = np.asarray(im, dtype=np.float64)
    H, W, _ = src.shape

    # step 1 -- box resample to 32x32, arithmetic mean, binary64
    cell = np.empty((32, 32, 3), dtype=np.float64)
    ys = [(int(cy * H // 32), int((cy + 1) * H // 32)) for cy in range(32)]
    xs = [(int(cx * W // 32), int((cx + 1) * W // 32)) for cx in range(32)]
    ys = [(a, min(a + 1, H) if b <= a else b) for a, b in ys]
    xs = [(a, min(a + 1, W) if b <= a else b) for a, b in xs]
    for cy, (y0, y1) in enumerate(ys):
        for cx, (x0, x1) in enumerate(xs):
            cell[cy, cx] = src[y0:y1, x0:x1].reshape(-1, 3).mean(axis=0)

    # step 2 -- sRGB -> linear
    s = cell / 255.0
    lin = np.where(s <= 0.04045, s / 12.92, ((s + 0.055) / 1.055) ** 2.4)

    # step 3 -- linear sRGB -> CIE XYZ (D65)
    M = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]], dtype=np.float64)
    XYZ = lin @ M.T

    # step 4 -- XYZ -> CIELAB
    wp = np.array([0.95047, 1.00000, 1.08883], dtype=np.float64)
    t = XYZ / wp
    eps = 216.0 / 24389.0
    f = np.where(t > eps, np.cbrt(t), (841.0 / 108.0) * t + 4.0 / 29.0)
    L = 116.0 * f[..., 1] - 16.0
    a = 500.0 * (f[..., 0] - f[..., 1])
    b = 200.0 * (f[..., 1] - f[..., 2])

    # step 5 -- 4x4x4 CIELAB histogram
    Lb = np.clip(np.floor(L / 25.0), 0, 3).astype(np.int64)
    ab = np.clip(np.floor((a + 100.0) / 50.0), 0, 3).astype(np.int64)
    bb = np.clip(np.floor((b + 100.0) / 50.0), 0, 3).astype(np.int64)
    idx = 16 * Lb + 4 * ab + bb
    counts = np.bincount(idx.ravel(), minlength=64).astype(np.float64)
    colour_bins = counts / 1024.0

    # step 6 -- 8-bin gradient orientation histogram over the L plane,
    #           Sobel with edge replication
    Lp = np.pad(L, 1, mode="edge")
    gxk = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float64)
    gyk = np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]], dtype=np.float64)
    gx = np.zeros_like(L)
    gy = np.zeros_like(L)
    for j in range(3):
        for i in range(3):
            win = Lp[j:j + 32, i:i + 32]
            gx += gxk[j, i] * win
            gy += gyk[j, i] * win
    mag = np.sqrt(gx * gx + gy * gy)
    th = np.arctan2(gy, gx)
    th = np.where(th < 0, th + math.pi, th)
    th = np.where(th >= math.pi, th - math.pi, th)
    obin = np.clip(np.floor(th * 8.0 / math.pi), 0, 7).astype(np.int64)
    orient = np.bincount(obin.ravel(), weights=mag.ravel(), minlength=8)
    total = orient.sum()
    orient = orient / total if total > 0 else np.zeros(8)

    # step 7/8 -- concatenate, L2-normalise, store as f32
    vec = np.concatenate([colour_bins, orient])
    norm = math.sqrt(float((vec * vec).sum()))
    if norm > 0:
        vec = vec / norm
    vec32 = vec.astype(np.float32)

    # step 9 -- palette: 8 largest bins, ties by ascending bin index
    order = sorted(range(64), key=lambda i: (-counts[i], i))[:8]
    pal = []
    flat_idx = idx.ravel()
    flat_lin = lin.reshape(-1, 3)
    for bi in order:
        c = counts[bi]
        if c <= 0:
            pal.append((0.0, 0.0, 0.0, 0.0))
            continue
        m = flat_lin[flat_idx == bi].mean(axis=0)
        pal.append((float(m[0]), float(m[1]), float(m[2]), float(c / 1024.0)))
    pal.sort(key=lambda r: -r[3])
    return vec32, np.array(pal, dtype=np.float32), (W, H)


def linear_to_hex(r, g, b):
    def enc(v):
        v = max(0.0, min(1.0, float(v)))
        s = v * 12.92 if v <= 0.0031308 else 1.055 * (v ** (1 / 2.4)) - 0.055
        return int(round(s * 255.0))
    return "#%02x%02x%02x" % (enc(r), enc(g), enc(b))


# ===========================================================================
# 6. the package
# ===========================================================================

NODE_MEANING = {
    "core.spec": "the specification, travelling inside the file (law 2)",
    "core.loader": "an embedded single-file zero-dependency reader",
    "core.license": "the full licence text, embedded not linked (law 7)",
    "core.readme": "one page for a human who opened the zip by hand",
    "core.image.source": "THE IMAGE as the producing process delivered it "
                         "(archival anchor)",
    "core.image.derived": "a re-rendering of those pixels (thumbnail/preview)",
    "core.recipe": "the reproduction record: models, prompts, params, input media",
    "core.disclosure": "machine-readable synthetic-content facts",
    "core.embedding": "WKEM custom binary: style descriptor + palette",
    "core.semantics": "facet tags, palette, keywords",
    "core.provenance": "who ran what, when, consuming and producing what",
    "x.c2pa.export": "extension: a DECLARED, UNIMPLEMENTED C2PA mapping",
}


class Werk(object):
    def __init__(self, path):
        self.path = path
        self.zf = zipfile.ZipFile(path, "r")
        self.names = self.zf.namelist()
        self.raw = {}
        self.manifest_bytes = self.read("MANIFEST.json")
        self.manifest = json.loads(self.manifest_bytes.decode("utf-8"))
        self.sig = None
        if "SIGNATURE.json" in self.names:
            self.sig = json.loads(self.read("SIGNATURE.json").decode("utf-8"))

    def read(self, name):
        if name not in self.raw:
            self.raw[name] = self.zf.read(name)
        return self.raw[name]

    def active_version(self, node):
        for v in node["versions"]:
            if v["v"] == node.get("active"):
                return v
        return None

    def node(self, node_id):
        for n in self.manifest["nodes"]:
            if n["node_id"] == node_id:
                return n
        return None

    def entry_end_offsets(self):
        """End byte offset of each zip entry's data, from the local headers
        (MINI-SPECS section 5). Needed to recompute preview_prefix_bytes."""
        ends = {}
        with open(self.path, "rb") as fh:
            for i in self.zf.infolist():
                fh.seek(i.header_offset)
                lh = fh.read(30)
                if lh[:4] != b"PK\x03\x04":
                    continue
                nlen, elen = struct.unpack_from("<HH", lh, 26)
                data_start = i.header_offset + 30 + nlen + elen
                ends[i.filename] = data_start + i.compress_size
        return ends


# ---------------------------------------------------------------------------
# 1. LIST
# ---------------------------------------------------------------------------

def do_list(w):
    head("1. CONTENTS AND WHAT EACH THING MEANS")
    m = w.manifest
    print("file            : %s (%d bytes on disk)"
          % (os.path.abspath(w.path), os.path.getsize(w.path)))
    print("format          : werk %d.%d, profile %r"
          % (m["werk"]["major"], m["werk"]["minor"], m["profile"]))
    print("manifest schema : %s" % m.get("manifest_schema"))
    print("entity          : %s" % m["entity"]["name"])
    print("uuid            : %s" % m["entity"]["uuid"])
    print("created         : %s" % m["entity"]["created"])
    print("licence         : %s (embedded as %s)"
          % (m["license"]["spdx_id"], m["license"]["file"]))
    print("container       : %s, compression=%s, %d zip entries"
          % (m["container"]["form"], m["container"]["zip_compression"],
             len(w.names)))
    print("primary image   : node %r" % m.get("primary", {}).get("image"))
    print("primary thumb   : node %r" % m.get("primary", {}).get("thumbnail"))
    print("\nsummary:")
    print(wrap(m["entity"]["summary"]))

    print("\nconventions (each governs a scope; refuse what you do not support):")
    for k, v in m["conventions"].items():
        print("    %-22s %s" % (k, v))

    print("\nnodes -- every byte except MANIFEST.json and SIGNATURE.json hangs "
          "off exactly one of these:\n")
    for n in m["nodes"]:
        act = n.get("active")
        print("  node %-16s type %-20s active v%s of %d"
              % (n["node_id"], n["type"], act, len(n["versions"])))
        print("      meaning : %s"
              % NODE_MEANING.get(n["type"], "unknown type -- skipped, "
                                            "reported, nothing else lost (law 3)"))
        if n.get("edges"):
            for e in n["edges"]:
                print("      edge    : --%s/%s--> %s"
                      % (e["kind"], e["role"], e["to"]))
        for v in n["versions"]:
            mark = "*" if v["v"] == act else " "
            print("     %sv%-2d epistemic=%-9s producer=%s%s"
                  % (mark, v["v"], v.get("epistemic", "-"),
                     v.get("producer", {}).get("tool", "-"),
                     (" model=" + v["producer"]["model"])
                     if v.get("producer", {}).get("model") else ""))
            if v.get("note"):
                print(wrap(v["note"], indent="          "))
            for f in v["files"]:
                role = ("  role=" + f["role"]) if f.get("role") else ""
                print("          %-45s %9d  %s%s"
                      % (f["path"], f["size"], f.get("media_type", "?"), role))
        print("")


# ---------------------------------------------------------------------------
# 2. VERIFY
# ---------------------------------------------------------------------------

def do_verify(w):
    head("2. INTEGRITY")
    r = Report()
    m = w.manifest

    sub("2.1 profile and conventions")
    r.check(m["profile"] == "image/1",
            "profile is image/1, so manifest.image.schema.json is the authority",
            "read before anything else, per spec/README.md row 0")
    r.check(m["conventions"]["hash_algorithm"] == "sha256"
            and m["conventions"]["signature_algorithm"] == "ed25519"
            and m["conventions"]["endianness"] == "le"
            and m["conventions"]["text_encoding"] == "utf-8",
            "declared conventions are ones this reader supports")

    sub("2.2 per-file sha256 (files[].sha256 over the exact container bytes)")
    listed, bad, claims = {}, [], {}
    for n in m["nodes"]:
        for v in n["versions"]:
            for f in v["files"]:
                p = f["path"]
                claims.setdefault(p, set()).add(n["node_id"])
                if p in listed:
                    prev = listed[p]
                    if (prev["sha256"], prev["size"]) != (f["sha256"], f["size"]):
                        bad.append("%s relisted with a different hash/size" % p)
                    continue
                listed[p] = f
                try:
                    data = w.read(p)
                except KeyError:
                    bad.append("%s: declared but not present in container" % p)
                    continue
                if len(data) != f["size"]:
                    bad.append("%s: size %d != declared %d"
                               % (p, len(data), f["size"]))
                if sha256_hex(data) != f["sha256"]:
                    bad.append("%s: sha256 mismatch" % p)
    r.check(not bad, "all %d declared files present, right size, right hash"
            % len(listed), "; ".join(bad))

    sub("2.3 hermeticity / reachability (SPEC 2, D-MAN-1, S-18)")
    container_files = set(n for n in w.names if not n.endswith("/"))
    floating = sorted(container_files - set(listed) -
                      {"MANIFEST.json", "SIGNATURE.json"})
    r.check(not floating, "nothing floats: every byte is reachable from a node",
            "unreachable: %s" % floating if floating else "")
    missing = sorted(set(listed) - container_files)
    r.check(not missing, "no node names a file the package does not carry "
                         "(law 1)", "%s" % missing if missing else "")
    multi = {p: sorted(s) for p, s in claims.items() if len(s) > 1}
    r.check(not multi, "no path is claimed by two DIFFERENT nodes",
            "%s" % multi if multi else "")
    shared = [p for p, f in listed.items()
              if sum(1 for n in m["nodes"] for v in n["versions"]
                     for g in v["files"] if g["path"] == p) > 1]
    if shared:
        r.note("S-18 exercised: %d file(s) listed by several versions of ONE "
               "node" % len(shared), ", ".join(sorted(shared)))

    sub("2.4 licence hash")
    r.check(sha256_hex(w.read(m["license"]["file"])) == m["license"]["sha256"],
            "license.sha256 matches the embedded LICENSE bytes")

    sub("2.5 input_hash recomputation (MINI-SPECS 11 'What gets hashed')")
    ih_bad = []
    ih_n = 0
    for n in m["nodes"]:
        for v in n["versions"]:
            if "input_hash" not in v:
                continue
            ih_n += 1
            h = hashlib.sha256()
            for p in v.get("input_files", []):
                try:
                    h.update(hashlib.sha256(w.read(p)).digest())   # RAW 32 bytes
                except KeyError:
                    ih_bad.append("%s v%d: input %s absent" % (n["node_id"], v["v"], p))
            h.update(canonical_json(v.get("input_params") or {}))  # "{}" when absent
            if h.hexdigest() != v["input_hash"]:
                ih_bad.append("%s v%d: input_hash mismatch (got %s, declared %s)"
                              % (n["node_id"], v["v"], h.hexdigest(), v["input_hash"]))
    r.check(not ih_bad, "all %d declared input_hash values recompute "
                        "(so no derived node is stale)" % ih_n,
            "; ".join(ih_bad))

    sub("2.6 signature chain (SPEC 6, three states, never two)")
    if w.sig is None:
        r.note("state = ABSENT", "anonymous, and visibly so -- NOT 'not "
                                 "AI-generated' and NOT 'invalid'")
    else:
        r.check(ed25519_selftest(),
                "Ed25519 implementation passes RFC 8032 vector 1 "
                "(the vector printed in MINI-SPECS 12)")
        actual = sha256_hex(w.manifest_bytes)
        ok_chain, prev = True, None
        for e in w.sig["chain"]:
            msg = "\n".join(["werk-sig/1", e["manifest_sha256"],
                             e["prev_entry_sha256"], e["signed_at"],
                             e["signer"]["uri"], e["signer"]["kind"]]
                            ).encode("utf-8")
            good = ed25519_verify(bytes.fromhex(e["public_key"]),
                                  bytes.fromhex(e["signature"]), msg)
            want_prev = ("0" * 64) if prev is None else sha256_hex(prev.encode("utf-8"))
            link = (e["prev_entry_sha256"] == want_prev)
            ok_chain = ok_chain and good and link
            r.check(good, "entry %d: Ed25519 signature verifies "
                          "(signer %s)" % (e["index"], e["signer"]["uri"]))
            r.check(link, "entry %d: prev_entry_sha256 links correctly" % e["index"])
            prev = e["signature"]
        last = w.sig["chain"][-1]
        anchor = r.check(last["manifest_sha256"] == actual,
                         "last entry's manifest_sha256 == sha256 of the "
                         "MANIFEST.json bytes actually present")
        r.check(w.sig["manifest_sha256"] == last["manifest_sha256"],
                "top-level manifest_sha256 is a faithful convenience copy "
                "of the current anchor")
        state = ("SIGNED-AND-VALID" if (ok_chain and anchor)
                 else "PRESENT-AND-INVALID")
        r.note("state = %s" % state,
               "honest limit: the chain has NO external root of trust. "
               "This key is a published dev key -- it proves the chain "
               "verifies, and nothing about authorship.")

    sub("2.7 container bookkeeping (S-14 / S-15, both PROPOSED)")
    total = sum(f["size"] for f in listed.values())
    r.check(total == m["container"]["total_size_bytes"],
            "container.total_size_bytes == sum of declared file sizes",
            "got %d, declared %d (it is NOT the zip's own size, %d)"
            % (total, m["container"]["total_size_bytes"],
               os.path.getsize(w.path)))

    ends = w.entry_end_offsets()
    tier = m["container"].get("preview_tier") or []
    exacts = [t for t in tier if not t.endswith("/")]
    prefixes = [t for t in tier if t.endswith("/")]
    sel = set(t for t in exacts if t in ends)                 # pass 1: exact
    for pre in prefixes:                                      # pass 2: prefixes
        for name in ends:
            if name.startswith(pre) and name not in exacts:
                sel.add(name)
    computed = max((ends[n] for n in sel), default=0)
    r.check(computed == m["container"]["preview_prefix_bytes"],
            "preview_prefix_bytes recomputed from the zip's own local headers",
            "computed %d, declared %d, covering %d entries"
            % (computed, m["container"]["preview_prefix_bytes"], len(sel)))
    order_ok = all(ends[n] <= computed for n in sel)
    r.check(order_ok, "every preview-tier entry physically precedes that offset "
                      "(law 9: a ranged read really does yield the browsable tier)")

    # S-15's authority question, exercised: manifest.image.schema.json's own
    # description of preview_prefix_bytes names the tier as "... disclosure/,
    # recipe/ and the node named by primary.thumbnail" WITHOUT SPEC 1's
    # "where container.preview_tier is absent" caveat. Taken literally it
    # sweeps in recipe/inputs/ and yields a different number.
    lit = ["MANIFEST.json", "SIGNATURE.json", "LICENSE", "README.txt",
           "loaders/", "spec/", "semantics/", "disclosure/", "recipe/",
           "image/thumb-256.png"]
    lsel = set(t for t in lit if t in ends)
    for pre in [t for t in lit if t.endswith("/")]:
        lsel |= set(n for n in ends if n.startswith(pre))
    lcomp = max((ends[n] for n in lsel), default=0)
    if lcomp != computed:
        r.note("AMBIGUITY: the image schema's literal tier sentence gives %d, "
               "container.preview_tier gives %d" % (lcomp, computed),
               "resolved in favour of the explicit container.preview_tier, "
               "because SPEC.md 1 (S-15) and manifest.schema.json both add the "
               "'where that key is absent' caveat that the image schema's "
               "description drops. The declared value matches preview_tier.")

    # S-14 two-pass matching of container.entry_order, applied for real.
    eo = m["container"]["entry_order"]
    exact = [t for t in eo if not t.endswith("/")]
    rank = {t: eo.index(t) for t in exact if t in ends}          # pass 1
    for t in eo:                                                  # pass 2
        if t.endswith("/"):
            for n in ends:
                if n.startswith(t) and n not in exact and n not in rank:
                    rank[n] = eo.index(t)
    physical = [i.filename for i in w.zf.infolist()]
    matched = [n for n in physical if n in rank]
    ranks = [rank[n] for n in matched]
    r.check(all(ranks[i] <= ranks[i + 1] for i in range(len(ranks) - 1)),
            "physical zip order agrees with container.entry_order under the "
            "S-14 two-pass rule (exact paths first, then directory prefixes)",
            "%d of %d entries matched" % (len(matched), len(physical)))
    unmatched = [n for n in physical if n not in rank]
    if unmatched:
        r.note("entry_order names no bucket for %d entry/entries: %s"
               % (len(unmatched), ", ".join(unmatched)),
               "SPEC.md 1 describes entry_order as listing every bucket in the "
               "package; here it does not. Order is explicitly advisory ('a "
               "reader that ignores entry_order entirely is conformant'), so "
               "this is an inconsistency, not damage. The entry sits last in "
               "the file, outside the preview tier.")

    sub("2.8 doctrine cross-checks a reader is told to make")
    src = w.node("image-source")
    srcv = w.active_version(src)
    rec = json.loads(w.read(w.active_version(w.node("recipe"))["files"][0]["path"]))
    dis = json.loads(w.read(w.active_version(w.node("disclosure"))["files"][0]["path"]))
    r.check(srcv["epistemic"] == "inferred",
            "generated source image is epistemic 'inferred', not 'measured' "
            "(PROFILE-IMAGE 3)",
            "grade %r and stamp %r agree" % (rec["reproducibility"],
                                             srcv["epistemic"]))
    for nid in ("image-preview", "image-thumb"):
        v = w.active_version(w.node(nid))
        r.check(v["epistemic"] == "measured"
                and v.get("input_files") == ["image/source.png"]
                and w.node(nid)["meta"].get("resample") in
                ("lanczos3", "box", "bilinear", "nearest", "none"),
                "%s is 'measured', points at the source, and names a concrete "
                "resample filter (%s)" % (nid, w.node(nid)["meta"]["resample"]))
    rmodels = set(s["model"]["id"] for s in rec["steps"])
    dmodels = set(x["id"] for x in dis["models"])
    r.check(rmodels == dmodels,
            "recipe and disclosure name the same model(s) -- nothing to report "
            "as a disagreement (SPEC 3.12 rule 5)",
            ", ".join(sorted(rmodels)))
    r.check(bool(rec.get("reproducibility_note")) and bool(rec.get("unrecorded")),
            "recipe carries the mandatory reproducibility_note and a "
            "non-empty unrecorded[]",
            "%d unrecorded facts" % len(rec["unrecorded"]))
    inputs_ok = []
    for s in rec["steps"]:
        for inp in s.get("inputs", []):
            f = listed.get(inp["path"])
            inputs_ok.append(bool(f) and f["sha256"] == inp["sha256"])
    r.check(all(inputs_ok) and inputs_ok,
            "every input medium the recipe names is embedded here by hash "
            "(law 1 hermeticity; only weights may be absent)")

    # the S-22 finding the package itself flags
    sem = json.loads(w.read(w.active_version(w.node("semantics"))["files"][0]["path"]))
    wsum = sum(c["weight"] for c in sem["palette"]["colors"])
    r.note("semantics palette weights sum to %.4f, not 1.0" % wsum,
           "the package flags this itself as spec finding S-22: a top-N "
           "palette cannot cover everything, but core.semantics.schema.json "
           "asks for 1.0 +/-1e-3. A schema/payload contradiction, disclosed.")

    return r, rec, dis, sem


# ---------------------------------------------------------------------------
# 3. EXTRACT
# ---------------------------------------------------------------------------

def do_extract(w, outdir):
    head("3. EXTRACTION")
    os.makedirs(outdir, exist_ok=True)
    m = w.manifest
    picked = []

    # primary image -- 4 steps, per PROFILE-IMAGE section 8.3
    nid = m.get("primary", {}).get("image")
    if nid:
        print("  primary.image names node %r (declared, no fallback needed)" % nid)
    else:                                        # documented fallback
        cands = [n for n in m["nodes"] if n["type"] == "core.image.source"]
        nid = cands[0]["node_id"]
        print("  primary absent -> FELL BACK to the core.image.source node %r, "
              "and this reader reports having done so" % nid)
    node = w.node(nid)
    v = w.active_version(node)
    picked.append(("primary image", node, v, v["files"][0]))

    # one other payload: the style plate the generation actually consumed
    rnode = w.node("recipe")
    rv = w.active_version(rnode)
    inp = [f for f in rv["files"] if f.get("role") == "input-media"]
    if inp:
        picked.append(("recipe input medium (the style plate the model saw)",
                       rnode, rv, inp[0]))

    for label, node, v, f in picked:
        data = w.read(f["path"])
        got = sha256_hex(data)
        dest = os.path.join(outdir, os.path.basename(f["path"]))
        with open(dest, "wb") as fh:
            fh.write(data)
        print("\n  %s" % label)
        print("    node        : %s (%s) v%d" % (node["node_id"], node["type"], v["v"]))
        print("    source path : %s" % f["path"])
        print("    written to  : %s" % os.path.abspath(dest))
        print("    bytes       : %d (declared %d)" % (len(data), f["size"]))
        print("    sha256      : %s  [%s]"
              % (got, "verified against manifest" if got == f["sha256"] else "MISMATCH"))
        meta = node.get("meta") or {}
        if meta.get("width"):
            print("    pixels      : %dx%d, %d channels, %d-bit, %s, alpha=%s"
                  % (meta["width"], meta["height"], meta["channels"],
                     meta["bit_depth"], meta["color_space"], meta["has_alpha"]))
        if meta.get("aspect_note"):
            print(wrap("aspect: " + meta["aspect_note"], indent="      "))
    return [os.path.join(outdir, os.path.basename(f["path"]))
            for _, _, _, f in picked]


# ---------------------------------------------------------------------------
# 4. PARSE THE CUSTOM BINARY
# ---------------------------------------------------------------------------

def do_binary(w, recompute=True):
    head("4. THE CUSTOM BINARY PAYLOAD")
    node = w.node("style-embedding")
    v = w.active_version(node)
    path = v["files"][0]["path"]
    data = w.read(path)
    print("  file   : %s (%d bytes)" % (path, len(data)))
    print("  layout : %s  (named by MANIFEST.layouts, never derived)"
          % w.manifest["layouts"][node["type"]])

    try:
        magic, version, header, secs = read_envelope(data)
    except (EnvelopeError, MsgpackError) as exc:
        print("  MALFORMED -> node marked dead, rest of package still loads "
              "(law 3): %s" % exc)
        return None

    sub("4.1 fixed prefix (little-endian)")
    print("    magic          : %r = %s  -> payload kind %s"
          % (magic.decode("ascii"), magic.hex(" "), _MAGIC_KIND[magic]))
    print("    version        : %d" % version)
    print("    header_len     : %d bytes of MessagePack (BIG-endian inside!)"
          % struct.unpack_from("<I", data, 8)[0])
    print("    payload_origin : %d  (declared AND recomputed as "
          "16*ceil((12+header_len)/16) -- both agree)" % header["payload_origin"])
    print("    payload_size   : %d  (origin+size == file size)"
          % header["payload_size"])

    sub("4.2 header map, decoded")
    for k in sorted(header):
        if k == "sections":
            continue
        val = header[k]
        if isinstance(val, str) and len(val) > 60:
            print("    %-14s :" % k)
            print(wrap(val, indent="        "))
        else:
            print("    %-14s : %r" % (k, val))
    print("\n    what the mandatory WKEM keys mean:")
    print("      model        -- WHAT PRODUCED THE VECTOR. Mandatory, because a")
    print("                      vector whose model is unknown is noise: distance")
    print("                      between vectors from two models means nothing.")
    print("      metric       -- the distance to use (%r), declared not guessed."
          % header["metric"])
    print("      normalized   -- %r; a reader must READ this, never assume it."
          % header["normalized"])
    print("      dim          -- %d, and it MUST equal shape[0] of 'vector'."
          % header["dim"])
    print("      swatch_count -- %d, and it MUST equal shape[0] of 'palette'."
          % header["swatch_count"])
    print("      tolerance    -- %g absolute per component that a conformant"
          % header["tolerance"])
    print("                      RE-COMPUTATION is expected to reach.")

    sub("4.3 sections (offsets ABSOLUTE and DECLARED, never computed)")
    arrays = {}
    for s in secs:
        print("    %-8s offset=%-6d size=%-5d dtype=%-4s shape=%-9s stride=%d"
              % (s["name"], s["offset"], s["size"], s["dtype"],
                 str(list(s["shape"])), s["stride"]))
        arrays[s["name"]] = section_array(s)
    print("    consistency rule: 'vector' takes the FIRST branch "
          "(stride==esz==4 -> size==4*72==%d)," % (4 * header["dim"]))
    print("    'palette' takes the SECOND (stride 16 != esz 4 -> "
          "size==16*8==%d). Both checked." % (16 * header["swatch_count"]))
    assert header["dim"] == secs[0]["shape"][0]
    assert header["swatch_count"] == secs[1]["shape"][0]
    print("    header dim/swatch_count agree with the section shapes.  PASS")

    vec = arrays["vector"]
    pal = arrays["palette"]

    sub("4.4 the 72-component descriptor  (%s)" % header["model"])
    import numpy as np
    print("    L2 norm = %.9f  (header says normalized=%s)"
          % (float(np.sqrt((vec.astype(np.float64) ** 2).sum())),
             header["normalized"]))
    print("    finite  = %s  (no NaN, no Inf permitted in any core payload)"
          % bool(np.isfinite(vec).all()))
    print("\n    components 0..63 = a 4x4x4 CIELAB histogram, index = 16*L + 4*a + b")
    print("    (L bin = floor(L/25), a bin = floor((a+100)/50), same for b)")
    nz = [(i, float(vec[i])) for i in range(64) if vec[i] != 0]
    print("    %d of the 64 colour bins are non-empty:" % len(nz))
    for i, val in sorted(nz, key=lambda t: -t[1]):
        Lb, ab, bb = i // 16, (i % 16) // 4, i % 4
        print("      bin %2d (L=%d a=%d b=%d)  %.6f   ~%.2f%% of the image"
              % (i, Lb, ab, bb, val, 100.0 * val /
                 sum(x for _, x in nz) if nz else 0))
    print("\n    components 64..71 = an 8-bin gradient-orientation histogram over")
    print("    the 32x32 L plane (Sobel, edge-replicated, angles folded to [0,pi)):")
    for j in range(8):
        lo, hi = j * 180.0 / 8, (j + 1) * 180.0 / 8
        bar = "#" * int(round(60 * float(vec[64 + j]) / max(1e-12, float(vec[64:].max()))))
        print("      %3.0f-%3.0f deg  %.6f  %s" % (lo, hi, float(vec[64 + j]), bar))

    sub("4.5 the 8-swatch palette  (%s, sorted by weight DESCENDING)"
        % header["colour_space"])
    print("      #  linear r,g,b                     weight    sRGB hex")
    for i, row in enumerate(pal):
        r_, g_, b_, wgt = [float(x) for x in row]
        print("      %d  %.6f %.6f %.6f   %.6f  %s   %s"
              % (i, r_, g_, b_, wgt, linear_to_hex(r_, g_, b_),
                 "<- dominant colour, by construction" if i == 0 else ""))
    print("    weights sum to %.6f -- these are the top 8 bins, not a cover."
          % float(pal[:, 3].sum()))

    if recompute:
        sub("4.6 RECOMPUTING the descriptor from image/source.png")
        print("    embedding.layout.txt section 4 defines the descriptor as pure")
        print("    arithmetic precisely so this node can be MEASURED rather than")
        print("    asserted. Running steps 1-9 over the source image now...")
        try:
            src = w.read(header.get("source_path", "image/source.png"))
            rvec, rpal, (W, H) = labhog(src)
            dv = float(np.abs(rvec.astype(np.float64) -
                              vec.astype(np.float64)).max())
            dp = float(np.abs(rpal.astype(np.float64) -
                              pal.astype(np.float64)).max())
            tol = header["tolerance"]
            print("    source %dx%d" % (W, H))
            print("    max |recomputed - stored| : vector  %.3e   (tolerance %.1e)"
                  % (dv, tol))
            print("    max |recomputed - stored| : palette %.3e" % dp)
            print("    -> [%s] the stored descriptor really is a measurement of "
                  "these pixels." % (_OK if (dv <= tol and dp <= tol) else _BAD))
        except Exception as exc:
            print("    recomputation skipped: %s" % exc)
    return header, vec, pal


# ---------------------------------------------------------------------------
# 5. PLAIN LANGUAGE
# ---------------------------------------------------------------------------

def do_plain(w, rec, dis):
    head("5. HOW THE IMAGE WAS MADE (RECIPE) AND WHAT THE FILE DECLARES "
         "(DISCLOSURE)")
    m = w.manifest
    src = w.node("image-source")
    meta = src["meta"]
    rnode = w.node("recipe")
    step = rec["steps"][0]

    sub("5.1 The recipe, in plain language")
    print(wrap(
        "The picture is a %dx%d pixel character design plate called %r. It was "
        "not drawn, photographed or edited by a person: it was generated in one "
        "shot by a hosted AI image model, %r, run by %s and reached through the "
        "google-genai Python SDK's models.generate_content(). The pipeline that "
        "called it was %r."
        % (meta["width"], meta["height"], m["entity"]["name"],
           step["model"]["id"], step["model"]["operator"], step["tool"]["name"]),
        indent="    "))
    print()
    print(wrap(
        "The model was given two things. First, a long human-written text prompt "
        "describing the character (a young outer-worlds scholar in austere "
        "layered robes), the house style register ('realistic detailed colour "
        "digital oil painting', retro-futurist, in the manner of Hans Holbein "
        "the Younger), the framing ('centered full-body portrait, the subject "
        "fully visible'), the palette words (bone white, slate grey, muted "
        "bronze) and a long 'Do NOT include' exclusion list that keeps other "
        "people's franchises and real-world political and military insignia out "
        "of the picture. Second, one attached reference image, the house style "
        "plate recipe/inputs/imperial-painterly.png, attached automatically "
        "because the client's use_style_refs option defaults to true. That plate "
        "is carried inside this package by hash, so 'what the model saw' is not "
        "a promise about a file somewhere else.", indent="    "))
    print()
    print(wrap(
        "The only settings passed were aspect_ratio 3:4, image_size 2K, "
        "response_modalities TEXT+IMAGE, and a client-side retry policy of up to "
        "%d attempts with %.1fs backoff. No seed, no sampler, no steps, no cfg, "
        "no LoRAs: %s"
        % (step["params"]["retries"], step["params"]["backoff_seconds"],
           step["seed"]["reason"]), indent="    "))
    print()
    print(wrap(
        "The delivered pixels were written to disk with Pillow's Image.save(), "
        "with no resize and no crop. So the pixels are the model's and the PNG "
        "byte stream is Pillow's -- which matters to anyone comparing hashes. "
        "The image came back at %dx%d, an aspect of %.4f rather than the "
        "requested 0.7500, and the package records that difference instead of "
        "cropping it away. Two later files, a 1024-wide preview and a 256-wide "
        "thumbnail, are plain Lanczos-3 downscales of that source and are marked "
        "'measured' because they genuinely are reproducible from it."
        % (meta["width"], meta["height"], meta["width"] / float(meta["height"])),
        indent="    "))
    print()
    print(wrap(
        "REPRODUCIBILITY: the recipe is graded %r -- the weakest of the three "
        "grades -- and the file says exactly why: %s"
        % (rec["reproducibility"], rec["reproducibility_note"]), indent="    "))
    print()
    print("    THE PROMPT IS TWO DIFFERENT CLAIMS, and the package keeps them apart:")
    v1 = [v for v in rnode["versions"] if v["v"] == 1][0]
    v2 = [v for v in rnode["versions"] if v["v"] == 2][0]
    print(wrap(
        "recipe node v%d (superseded, kept) carries recipe/prompt-recorded.txt "
        "-- the string the producing pipeline actually persisted. recipe node "
        "v%d (active) adds recipe/prompt-transmitted.txt, marked provenance "
        "'%s', because an audit of the pipeline's source showed the string that "
        "was SENT is one sentence longer: the client appends a style-reference "
        "sentence after the caller has already stored the prompt. The code "
        "excerpts it was rebuilt from ride along as "
        "recipe/evidence/pipeline-source.txt. v1 is not rewritten, because law 6 "
        "does not rewrite history."
        % (v1["v"], v2["v"],
           step["prompt"]["positive"]["provenance"]), indent="    "))
    rt = w.read("recipe/prompt-recorded.txt").decode("utf-8")
    tt = w.read("recipe/prompt-transmitted.txt").decode("utf-8")
    print()
    print("    the difference, byte for byte (%d -> %d bytes):"
          % (len(rt.encode()), len(tt.encode())))
    print(wrap("+ " + tt[len(rt):].strip(), indent="      "))
    print()
    print(wrap("And the record is honest about the limit of even that: %s"
               % step["prompt"]["positive"]["note"], indent="    "))
    print()
    print("    NOT RECORDED -- %d facts nobody captured and nobody can recover:"
          % len(rec["unrecorded"]))
    for u in rec["unrecorded"]:
        print(wrap("- " + u, indent="      "))

    sub("5.2 The disclosure, in plain language")
    print(wrap(
        "The package declares, in a machine-readable node, that this image IS "
        "AI-generated (ai_generated=%s), that the whole work is generated rather "
        "than one region (generation_scope=%r), and that it has NOT been "
        "AI-modified afterwards (ai_modified=%s). The declaration is made by %r "
        "on %s, and it points at the recipe node as its backing."
        % (dis["ai_generated"], dis["generation_scope"], dis["ai_modified"],
           dis["declared_by"]["name"], dis["declared_at"]), indent="    "))
    print()
    ha = dis["human_authorship"]
    print(wrap("HUMAN CONTRIBUTION, claimed=%s: %s Contributor named: %s."
               % (ha["claimed"], ha["description"],
                  ", ".join(c["name"] for c in ha["contributors"])),
               indent="    "))
    print()
    print(wrap("SUBJECT: no real person and no real event is depicted; the "
               "character is fictional, from the %r setting, and the only image "
               "attached to the generation was a house style plate -- not a "
               "photograph of anyone." % dis["subject"]["fictional_universe"],
               indent="    "))
    print()
    print(wrap("MARKERS: no C2PA manifest is present (c2pa_manifest_present=%s), "
               "and embedded PNG metadata was stripped "
               "(embedded_metadata_stripped=%s -- MEASURED by walking the PNG "
               "chunk list, not assumed). Deliberately there is NO "
               "declared_watermarks array, because an empty array would read as "
               "'checked and found none' and nobody checked."
               % (dis["synthetic_markers"]["c2pa_manifest_present"],
                  dis["synthetic_markers"]["embedded_metadata_stripped"]),
               indent="    "))
    print()
    print(wrap("TRAINING DATA: status %r. %s"
               % (dis["training_data_statement"]["status"],
                  dis["training_data_statement"]["text"]), indent="    "))
    print()
    print("    ADDITIONAL STATEMENTS the node makes:")
    for s in dis["statements"]:
        print(wrap("[%s, %s] %s" % (s["id"], s["epistemic"], s["text"]),
                   indent="      "))
    print()
    print(wrap("JURISDICTION: %s" % dis["jurisdiction_note"], indent="    "))
    print()
    print(wrap(
        "AND WHAT THE DISCLOSURE IS NOT. The format's own doctrine, which this "
        "program obeys: the format ships facts, the viewer applies "
        "jurisdiction, and the format contains no enforcement of any kind. "
        "Nothing here obliges any viewer to do anything; a viewer that ignores "
        "every field above is still conformant. What this program must not do "
        "is paraphrase the claim into a different one -- so: the package says "
        "AI-generated: true, and that is what is reported. The signature chain "
        "covering it verifies, but its key is a published dev key with no "
        "external root of trust, so 'declared_by' is an assertion by a party "
        "and must not be presented as verified authorship. Separately, the "
        "x/c2pa/export.json node is a DECLARED BUT UNIMPLEMENTED mapping and "
        "proves nothing about C2PA interoperability.", indent="    "))


# ===========================================================================
# main
# ===========================================================================

def main(argv):
    path = "artifact.werk"
    outdir = "extracted"
    recompute = True
    args = argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--out":
            outdir = args[i + 1]
            i += 2
        elif args[i] == "--no-recompute":
            recompute = False
            i += 1
        else:
            path = args[i]
            i += 1

    w = Werk(path)
    do_list(w)
    r, rec, dis, sem = do_verify(w)
    do_extract(w, outdir)
    do_binary(w, recompute=recompute)
    do_plain(w, rec, dis)

    head("VERDICT")
    total, nfail, failed = r.summary()
    print("  %d hard checks run, %d failed." % (total, nfail))
    for _, name, detail in failed:
        print("    FAILED: %s -- %s" % (name, detail))
    print("  signature state : %s"
          % ("ABSENT" if w.sig is None else "SIGNED-AND-VALID"
             if nfail == 0 else "see above"))
    print("  disclosure      : ai_generated = %s (reported as the node says it)"
          % dis["ai_generated"])
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main(sys.argv))
