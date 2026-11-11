#!/usr/bin/env python3
"""werk_reader.py: an independent reader for a werk 3D-entity package.

Written only from the documents carried inside the package
(spec/README.md, spec/SPEC.md, spec/MINI-SPECS.md,
spec/layouts/ENVELOPE.layout.txt, spec/layouts/restposes.layout.txt).
It does not use, import or port the loaders/ inside the package.

Usage:
    python -I werk_reader.py PACKAGE.werk OUT_DIR

What it does:
  1. opens the zip container (zip64 detection, store/deflate check)
  2. parses MANIFEST.json strictly (no BOM, no duplicate keys, no NaN)
  3. checks every convention value against what this reader supports
  4. verifies the SIGNATURE.json chain with a pure-Python Ed25519
  5. lists the node graph with the meaning of each node type
  6. verifies size + sha256 of every declared file, the licence hash,
     spec_sha256 and every input_hash whose inputs are present
  7. parses the payload formats it knows (GLB, WAV, PNG, WKRP envelope)
  8. extracts primary.mesh and primary.sound and re-hashes the written bytes

Exit status follows SPEC.md 10.2: 0 = no error entries, 1 = some error
entries, 2 = container-scoped refusal.
"""
import hashlib
import io
import json
import math
import os
import struct
import sys
import zipfile

# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------

REPORT = []


def report(code, severity, subject, detail=""):
    REPORT.append((code, severity, subject, detail))


# --------------------------------------------------------------------------
# What each node type means (spec/README.md table and SPEC.md section 3)
# --------------------------------------------------------------------------

TYPE_MEANING = {
    "core.spec": "the format specification travelling inside the file (law 2)",
    "core.loader": "a reader program carried as payload (SPEC 7); inert data here",
    "core.license": "full licence text, embedded",
    "core.readme": "one page for a human",
    "core.geom.source": "archival source mesh (GLB)",
    "core.geom.game": "runtime mesh (GLB); the primary-mesh fallback",
    "core.geom.lod": "level-of-detail mesh (GLB)",
    "core.tex": "texture (PNG)",
    "core.material": "PBR material parameters (JSON); authoritative over GLB materials",
    "core.imposter": "octahedral imposter atlases (PNG + JSON)",
    "core.phys.colliders": "collision shapes (JSON)",
    "core.phys.bounds": "bounding volumes (JSON)",
    "core.phys.body": "mass, centre of mass, inertia (JSON)",
    "core.field.flow": "flow field grid (WKFF envelope)",
    "core.pose.rest": "settled rest orientations from a drop simulation (WKRP envelope)",
    "core.skeleton": "skeleton (JSON + WKSK mirror)",
    "core.anim.clip": "animation clip (WKAC envelope + JSON)",
    "core.audio.package": "audio package descriptor (JSON)",
    "core.audio.effect": "sound effect (WAV takes + JSON descriptor)",
    "core.audio.ambience": "ambience loop (WAV + JSON)",
    "core.destruct": "fracture set (GLB + JSON)",
    "core.props": "inferred simulation properties (JSON)",
    "core.semantics": "facet tags, palette and search text (JSON)",
    "core.provenance": "who made what, from what, with which models (JSON)",
    "core.recipe": "reproduction record (JSON)",
    "core.disclosure": "machine-readable generation facts (JSON)",
    "core.embedding": "style embedding + palette (WKEM envelope)",
    "core.geom.points": "point cloud (WKPC envelope)",
    "core.geom.gsplat": "3D Gaussian splat (WKGS envelope)",
    "core.tool": "embedded tool (JSON + source)",
    "core.tool.config": "embedded tool configuration (JSON)",
}

# The convention set of profile 3d-entity/1 (SPEC.md section 2).
SUPPORTED_CONVENTIONS = {
    "endianness": "le", "units_per_meter": 1.0, "length_unit": "metre",
    "angle_unit": "radian", "time_unit": "second", "mass_unit": "kilogram",
    "up_axis": "y", "forward_axis": "-z", "right_axis": "+x",
    "handedness": "right", "winding": "ccw", "quat_order": "wxyz",
    "oct_encoding_pole": "y", "sh_l1_order": ["dc", "y", "z", "x"],
    "color_space_default": "srgb", "uv_origin": "top-left",
    "alignment_bytes": 16, "text_encoding": "utf-8", "id_case": "kebab-case",
    "hash_algorithm": "sha256", "signature_algorithm": "ed25519",
}

# SPEC.md 2.1 rule 4: payload role per node type.
PAYLOAD_ROLE = {
    "core.audio.effect": "best", "core.audio.ambience": "best",
    "core.imposter": "atlas", "core.recipe": "record",
}

# --------------------------------------------------------------------------
# Strict JSON (MINI-SPECS 2 and 3)
# --------------------------------------------------------------------------


class StrictJSONError(ValueError):
    pass


def _no_dupes(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise StrictJSONError("duplicate key %r" % k)
        d[k] = v
    return d


def _no_const(name):
    raise StrictJSONError("non-finite number %s" % name)


def strict_json(data):
    if data.startswith(b"\xef\xbb\xbf"):
        raise StrictJSONError("UTF-8 BOM present")
    text = data.decode("utf-8")  # strict decoding rejects surrogates/overlongs
    return json.loads(text, object_pairs_hook=_no_dupes, parse_constant=_no_const)


def canonical_json(v):
    """MINI-SPECS 3, canonical JSON (for input_params only)."""
    if isinstance(v, dict):
        items = sorted(v.items(), key=lambda kv: kv[0].encode("utf-8"))
        return "{" + ",".join(canonical_json(k) + ":" + canonical_json(x) for k, x in items) + "}"
    if isinstance(v, list):
        return "[" + ",".join(canonical_json(x) for x in v) + "]"
    if isinstance(v, str):
        out = ['"']
        short = {'"': '\\"', "\\": "\\\\", "\b": "\\b", "\f": "\\f",
                 "\n": "\\n", "\r": "\\r", "\t": "\\t"}
        for ch in v:
            if ch in short:
                out.append(short[ch])
            elif ord(ch) < 0x20:
                out.append("\\u%04x" % ord(ch))
            else:
                out.append(ch)
        out.append('"')
        return "".join(out)
    if v is True:
        return "true"
    if v is False:
        return "false"
    if v is None:
        return "null"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if v.is_integer() and abs(v) < 2 ** 53:
            return str(int(v))
        return repr(v)
    raise TypeError(type(v))


# --------------------------------------------------------------------------
# Ed25519 verification (MINI-SPECS 12), pure Python, non-constant-time.
# Only public inputs pass through this code; it is a verifier, never a signer.
# --------------------------------------------------------------------------

P = 2 ** 255 - 19
L = 2 ** 252 + 27742317777372353535851937790883648493
D = (-121665 * pow(121666, P - 2, P)) % P
I_SQRT = pow(2, (P - 1) // 4, P)


def _inv(a):
    return pow(a, P - 2, P)


def _recover_x(y, sign):
    if y >= P:
        return None
    u = (y * y - 1) % P
    v = (D * y * y + 1) % P
    x = (u * pow(v, 3, P) * pow(u * pow(v, 7, P), (P - 5) // 8, P)) % P
    if (v * x * x - (-u)) % P == 0:
        x = (x * I_SQRT) % P
    if (v * x * x - u) % P != 0:
        return None
    if x == 0 and sign == 1:
        return None
    if (x & 1) != sign:
        x = P - x
    return x


def _decompress(b):
    if len(b) != 32:
        return None
    n = int.from_bytes(b, "little")
    sign = n >> 255
    y = n & ((1 << 255) - 1)
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, (x * y) % P)


def _add(p1, p2):
    X1, Y1, Z1, T1 = p1
    X2, Y2, Z2, T2 = p2
    A = (Y1 - X1) * (Y2 - X2) % P
    B = (Y1 + X1) * (Y2 + X2) % P
    C = T1 * 2 * D * T2 % P
    Dd = Z1 * 2 * Z2 % P
    E, F, G, H = B - A, Dd - C, Dd + C, B + A
    return (E * F % P, G * H % P, F * G % P, E * H % P)


def _mul(s, pt):
    q = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            q = _add(q, pt)
        pt = _add(pt, pt)
        s >>= 1
    return q


def _eq(p1, p2):
    X1, Y1, Z1, _ = p1
    X2, Y2, Z2, _ = p2
    return (X1 * Z2 - X2 * Z1) % P == 0 and (Y1 * Z2 - Y2 * Z1) % P == 0


_BY = (4 * _inv(5)) % P
BASE = (_recover_x(_BY, 0), _BY, 1, (_recover_x(_BY, 0) * _BY) % P)


def ed25519_verify(pub, msg, sig):
    if len(sig) != 64:
        return False
    A = _decompress(pub)
    R = _decompress(sig[:32])
    if A is None or R is None:
        return False
    S = int.from_bytes(sig[32:], "little")
    if S >= L:
        return False
    k = int.from_bytes(hashlib.sha512(sig[:32] + pub + msg).digest(), "little") % L
    lhs = _mul(8, _mul(S, BASE))
    rhs = _mul(8, _add(R, _mul(k, A)))
    return _eq(lhs, rhs)


def self_test_crypto():
    """Prove the primitives against the vectors MINI-SPECS 6, 11, 12 print."""
    ok = True
    ok &= hashlib.sha256(b"abc").hexdigest() == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    ok &= hashlib.sha512(b"abc").hexdigest().startswith("ddaf35a193617abacc417349ae204131")
    import zlib
    ok &= zlib.crc32(b"123456789") == 0xCBF43926
    pub = bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
    sig = bytes.fromhex("e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b")
    ok &= ed25519_verify(pub, b"", sig)
    ok &= not ed25519_verify(pub, b"x", sig)
    # MINI-SPECS 12.1 worked example: message construction + verification.
    msg = sig_message("c421d2e85a9455f0be794ca8ee673f727a7ef67485d631e374f95c4a6d6ce61a",
                      "0" * 64, "2026-08-08T09:00:00Z",
                      "urn:werk:fixture:rfc8032-vector-1", "service")
    ok &= len(msg) == 203
    ok &= hashlib.sha256(msg).hexdigest() == "11e260cc16bc454f39f1aa6d56679c868ba1e83d33e3c22a462040b32a92165a"
    ex_sig = bytes.fromhex("55720b6fc38d680f8ca7523c0d8cec5045c7247f7158ab54eafd03d6ea0eedb1"
                           "aeb4902b4704a5c2e78d7713b375068748bea4fd116a2d3a49f6010074c6410d")
    ok &= ed25519_verify(pub, msg, ex_sig)
    return bool(ok)


def sig_message(manifest_sha, prev_sha, signed_at, uri, kind):
    return "\n".join(["werk-sig/1", manifest_sha, prev_sha, signed_at, uri, kind]).encode("utf-8")


# --------------------------------------------------------------------------
# Container (MINI-SPECS 5)
# --------------------------------------------------------------------------


def detect_zip64(raw):
    """MINI-SPECS 5.5 detection, done on raw bytes before trusting a library."""
    n = len(raw)
    lo = max(0, n - 22 - 65535)
    for off in range(n - 22, lo - 1, -1):
        if raw[off:off + 4] == b"PK\x05\x06":
            disk_cnt, total, cd_size, cd_off = struct.unpack_from("<HHII", raw, off + 8)
            sentinel = disk_cnt == 0xFFFF or total == 0xFFFF or cd_size == 0xFFFFFFFF or cd_off == 0xFFFFFFFF
            locator = off >= 20 and raw[off - 20:off - 16] == b"PK\x06\x07"
            return off, (sentinel or locator)
    return None, False


class Container:
    def __init__(self, path):
        with open(path, "rb") as f:
            self.raw = f.read()
        eocd, z64 = detect_zip64(self.raw)
        if eocd is None:
            raise RuntimeError("container: no EOCD record found (not a zip)")
        if z64:
            raise RuntimeError("zip64-unsupported")
        self.zip = zipfile.ZipFile(io.BytesIO(self.raw))
        self.entries = {}
        self._crc_reported = set()
        for info in self.zip.infolist():
            if info.filename.endswith("/"):
                continue
            n = info.filename
            if n.startswith("/") or ".." in n.split("/") or ":" in n or "\\" in n:
                report("unsafe-path", "error", n, "zip entry name violates MINI-SPECS 5.4")
                continue
            if info.flag_bits & 0x08:
                report("data-descriptor", "warn", n, "flag bit 3 set (MINI-SPECS 5.4 forbids it for writers)")
            if info.compress_type not in (0, 8):
                report("unsupported-compression", "error", n, "method %d" % info.compress_type)
                continue
            self.entries[n] = info

    def read(self, name):
        """Return bytes or None. zipfile checks the zip CRC-32 on read."""
        info = self.entries.get(name)
        if info is None:
            return None
        try:
            return self.zip.read(info)
        except zipfile.BadZipFile as e:
            if name not in self._crc_reported:
                report("zip-crc-mismatch", "error", name, str(e))
                self._crc_reported.add(name)
            if info.compress_type != 0:
                return None
            # Store mode: take the bytes from the local header (MINI-SPECS 5.3)
            # so the sha256 check can say precisely what is wrong.
            off = info.header_offset
            n, mlen = struct.unpack_from("<HH", self.raw, off + 26)
            start = off + 30 + n + mlen
            return self.raw[start:start + info.compress_size]


# --------------------------------------------------------------------------
# Payload parsers
# --------------------------------------------------------------------------


def parse_glb(b):
    if len(b) < 12 or b[:4] != b"glTF":
        raise ValueError("bad GLB magic")
    ver, total = struct.unpack_from("<II", b, 4)
    if ver != 2:
        raise ValueError("GLB version %d" % ver)
    if total != len(b):
        raise ValueError("GLB length field %d != file size %d" % (total, len(b)))
    off, js, binc = 12, None, None
    while off + 8 <= len(b):
        ln, typ = struct.unpack_from("<II", b, off)
        data = b[off + 8: off + 8 + ln]
        if len(data) != ln:
            raise ValueError("GLB chunk overruns file")
        if typ == 0x4E4F534A:
            js = strict_json(data.rstrip(b" "))
        elif typ == 0x004E4942:
            binc = data
        off += 8 + ln
    if js is None:
        raise ValueError("GLB has no JSON chunk")
    comp_n = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}
    comp_sz = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
    views = js.get("bufferViews", [])
    blen = len(binc or b"")
    for i, a in enumerate(js.get("accessors", [])):
        v = views[a["bufferView"]]
        esz = comp_sz[a["componentType"]] * comp_n[a["type"]]
        stride = v.get("byteStride", esz)
        end = v.get("byteOffset", 0) + a.get("byteOffset", 0) + stride * (a["count"] - 1) + esz
        if end > v.get("byteOffset", 0) + v["byteLength"] or end > blen:
            raise ValueError("accessor %d overruns its bufferView/BIN chunk" % i)
    summary = []
    for m in js.get("meshes", []):
        for p in m.get("primitives", []):
            attrs = p.get("attributes", {})
            vcount = js["accessors"][attrs["POSITION"]]["count"] if "POSITION" in attrs else 0
            icount = js["accessors"][p["indices"]]["count"] if "indices" in p else vcount
            pos = js["accessors"][attrs["POSITION"]] if "POSITION" in attrs else {}
            summary.append("mesh %r: mode %s, %d vertices, %d triangles, attributes %s, bbox min %s max %s"
                           % (m.get("name", ""), p.get("mode", 4), vcount, icount // 3,
                              sorted(attrs), pos.get("min"), pos.get("max")))
    return js, summary


def parse_wav(b):
    if b[:4] != b"RIFF" or b[8:12] != b"WAVE":
        raise ValueError("not RIFF/WAVE")
    riff_size = struct.unpack_from("<I", b, 4)[0]
    if riff_size + 8 != len(b):
        report("wav-riff-size", "warn", "", "RIFF size %d + 8 != %d" % (riff_size, len(b)))
    off, fmt, data_len = 12, None, None
    while off + 8 <= len(b):
        cid = b[off:off + 4]
        csz = struct.unpack_from("<I", b, off + 4)[0]
        body = b[off + 8: off + 8 + csz]
        if cid == b"fmt ":
            fmt = struct.unpack_from("<HHIIHH", body, 0)
        elif cid == b"data":
            data_len = len(body)
        off += 8 + csz + (csz & 1)
    if fmt is None or data_len is None:
        raise ValueError("missing fmt or data chunk")
    afmt, ch, sr, brate, balign, bits = fmt
    frames = data_len // balign
    return {"format": {1: "pcm-int", 3: "ieee-float", 0xFFFE: "extensible"}.get(afmt, afmt),
            "channels": ch, "sample_rate_hz": sr, "bit_depth": bits,
            "frames": frames, "seconds": frames / sr}


def parse_png_ihdr(b):
    if b[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("bad PNG signature")
    import zlib
    off, ihdr = 8, None
    while off + 12 <= len(b):
        ln = struct.unpack_from(">I", b, off)[0]
        typ = b[off + 4: off + 8]
        data = b[off + 8: off + 8 + ln]
        crc = struct.unpack_from(">I", b, off + 8 + ln)[0]
        if zlib.crc32(typ + data) != crc:
            raise ValueError("PNG chunk %r CRC mismatch" % typ)
        if typ == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", data)
        off += 12 + ln
        if typ == b"IEND":
            break
    w, h, depth, ctype, _, _, interlace = ihdr
    return {"width": w, "height": h, "bit_depth": depth,
            "channels": {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype], "color_type": ctype,
            "interlace": interlace}


# MessagePack subset (ENVELOPE.layout.txt section 4). Big-endian inside.
def mp_decode(b, off=0):
    t = b[off]
    off += 1
    if t <= 0x7F:
        return t, off
    if t >= 0xE0:
        return t - 256, off
    if 0xA0 <= t <= 0xBF:
        n = t & 0x1F
        return b[off:off + n].decode("utf-8"), off + n
    if 0x90 <= t <= 0x9F:
        return _mp_arr(b, off, t & 0x0F)
    if 0x80 <= t <= 0x8F:
        return _mp_map(b, off, t & 0x0F)
    if t == 0xC0:
        return None, off
    if t == 0xC2:
        return False, off
    if t == 0xC3:
        return True, off
    fixed = {0xCC: ">B", 0xCD: ">H", 0xCE: ">I", 0xCF: ">Q", 0xD0: ">b", 0xD1: ">h",
             0xD2: ">i", 0xD3: ">q", 0xCA: ">f", 0xCB: ">d"}
    if t in fixed:
        f = fixed[t]
        return struct.unpack_from(f, b, off)[0], off + struct.calcsize(f)
    lens = {0xD9: ">B", 0xDA: ">H", 0xDB: ">I", 0xC4: ">B", 0xC5: ">H", 0xC6: ">I"}
    if t in lens:
        f = lens[t]
        n = struct.unpack_from(f, b, off)[0]
        off += struct.calcsize(f)
        raw = b[off:off + n]
        return (raw.decode("utf-8") if t in (0xD9, 0xDA, 0xDB) else bytes(raw)), off + n
    if t in (0xDC, 0xDD):
        f = ">H" if t == 0xDC else ">I"
        return _mp_arr(b, off + struct.calcsize(f), struct.unpack_from(f, b, off)[0])
    if t in (0xDE, 0xDF):
        f = ">H" if t == 0xDE else ">I"
        return _mp_map(b, off + struct.calcsize(f), struct.unpack_from(f, b, off)[0])
    raise ValueError("banned or unknown MessagePack byte 0x%02x" % t)


def _mp_arr(b, off, n):
    out = []
    for _ in range(n):
        v, off = mp_decode(b, off)
        out.append(v)
    return out, off


def _mp_map(b, off, n):
    out = {}
    for _ in range(n):
        k, off = mp_decode(b, off)
        v, off = mp_decode(b, off)
        if k in out:
            raise ValueError("duplicate header key %r" % k)
        out[k] = v
    return out, off


DTYPE_SIZE = {"u8": 1, "i8": 1, "u16": 2, "i16": 2, "u32": 4, "i32": 4,
              "u64": 8, "i64": 8, "f32": 4, "f64": 8}
MAGIC_KIND = {b"WKFF": "core.field.flow", b"WKRP": "core.pose.rest", b"WKAC": "core.anim.clip",
              b"WKSK": "core.skeleton", b"WKEM": "core.embedding", b"WKPC": "core.geom.points",
              b"WKGS": "core.geom.gsplat"}


def read_envelope(buf):
    """ENVELOPE.layout.txt section 7, every assertion kept."""
    if len(buf) < 12:
        raise ValueError("envelope shorter than 12 bytes")
    magic = buf[:4]
    version, header_len = struct.unpack_from("<II", buf, 4)
    if 12 + header_len > len(buf):
        raise ValueError("header_len runs past end of file")
    header, end = mp_decode(buf, 12)
    if end != 12 + header_len:
        raise ValueError("header occupies %d bytes, header_len says %d" % (end - 12, header_len))
    if header.get("kind") != MAGIC_KIND.get(magic):
        raise ValueError("kind %r does not match magic %r" % (header.get("kind"), magic))
    if header.get("endianness") != "le":
        raise ValueError("endianness is not 'le'")
    Pp = 16 * math.ceil((12 + header_len) / 16)
    if header["payload_origin"] != Pp:
        raise ValueError("payload_origin %d != computed %d" % (header["payload_origin"], Pp))
    if Pp + header["payload_size"] != len(buf):
        raise ValueError("payload_origin + payload_size != file size")
    secs = {}
    prev_end = Pp
    for i, s in enumerate(header["sections"]):
        if s["offset"] % 16:
            raise ValueError("section %s offset not 16-aligned" % s["name"])
        if i == 0 and s["offset"] != Pp:
            raise ValueError("section 0 does not start at payload_origin")
        if not (0 <= s["offset"] - prev_end <= 15):
            raise ValueError("gap/overlap before section %s" % s["name"])
        if s["offset"] + s["size"] > len(buf):
            raise ValueError("section %s overruns file" % s["name"])
        esz = DTYPE_SIZE.get(s["dtype"], s["stride"])
        if s["stride"] == esz:
            if s["size"] != s["stride"] * math.prod(s["shape"]):
                raise ValueError("section %s size rule (branch 1) fails" % s["name"])
        else:
            if s["stride"] < esz * s["shape"][-1]:
                raise ValueError("section %s stride too small" % s["name"])
            if s["size"] != s["stride"] * math.prod(s["shape"][:-1]):
                raise ValueError("section %s size rule (branch 2) fails" % s["name"])
        prev_end = s["offset"] + s["size"]
        secs[s["name"]] = buf[s["offset"]: s["offset"] + s["size"]]
    if 16 * math.ceil(prev_end / 16) != Pp + header["payload_size"]:
        raise ValueError("trailing data after last section")
    return magic, version, header, secs


def decode_wkrp(header, secs):
    poses = []
    for i in range(header["pose_count"]):
        w, x, y, z, cf, cc, prob, area = struct.unpack_from("<ffffIIff", secs["poses"], 32 * i)
        poses.append({"quat_wxyz": (w, x, y, z), "contact_first": cf, "contact_count": cc,
                      "probability": prob, "support_area_m2": area})
    contacts = [struct.unpack_from("<fff", secs["contacts"], 12 * c) for c in range(header["contact_count"])]
    problems = []
    if sum(p["contact_count"] for p in poses) != header["contact_count"]:
        problems.append("sum of contact_count != header contact_count")
    probs = [p["probability"] for p in poses]
    if probs != sorted(probs, reverse=True):
        problems.append("entries not sorted by probability descending")
    if header.get("trials", 0) > 0 and abs(sum(probs) - 1.0) > 1e-3:
        problems.append("probabilities sum to %.6f, not 1.0" % sum(probs))
    for p in poses:
        n = math.sqrt(sum(c * c for c in p["quat_wxyz"]))
        if abs(n - 1.0) > 1e-6:
            problems.append("non-unit quaternion |q|=%.8f" % n)
        if p["quat_wxyz"][0] < 0:
            problems.append("quaternion with w < 0")
    for v in [c for xyz in contacts for c in xyz] + probs:
        if not math.isfinite(v):
            problems.append("NaN/inf in payload")
    return poses, contacts, problems


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def sha(b):
    return hashlib.sha256(b).hexdigest()


def resolve_payload(node, version):
    """SPEC.md 2.1, normative order. Returns (path, rule) or (None, reason)."""
    files = version.get("files", [])
    paths = [f["path"] for f in files]
    if "payload_file" in version:
        if paths.count(version["payload_file"]) == 1:
            return version["payload_file"], "rule 1 (payload_file)"
        return None, "payload_file %r is not exactly one entry of files[]" % version["payload_file"]
    if len(files) == 1:
        return paths[0], "rule 2 (single file)"
    pl = [f for f in files if f.get("role") == "payload"]
    if len(pl) == 1:
        return pl[0]["path"], "rule 3 (role payload)"
    role = PAYLOAD_ROLE.get(node["type"])
    if role:
        c = [f for f in files if f.get("role") == role]
        if len(c) == 1:
            return c[0]["path"], "rule 4 (role %s)" % role
    return None, "payload-file-ambiguous: candidates %s" % paths


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    pkg, outdir = argv[1], argv[2]
    print("=" * 78)
    print("werk_reader: %s" % pkg)
    print("=" * 78)

    crypto_ok = self_test_crypto()
    print("crypto self-test (SHA-256/512, CRC-32, Ed25519 RFC 8032 vector, MINI-SPECS 12.1 example): %s"
          % ("PASS" if crypto_ok else "FAIL"))

    # 1. Container ----------------------------------------------------------
    try:
        c = Container(pkg)
    except Exception as e:
        print("CONTAINER REFUSED: %s" % e)
        return 2
    print("\n[1] container: zip, %d bytes, %d file entries, sha256 %s"
          % (len(c.raw), len(c.entries), sha(c.raw)))
    methods = sorted({i.compress_type for i in c.entries.values()})
    print("    compression methods used: %s (0 = store)" % methods)

    # 2. Manifest -----------------------------------------------------------
    mbytes = c.read("MANIFEST.json")
    if mbytes is None:
        print("CONTAINER REFUSED: MANIFEST.json missing")
        return 2
    try:
        m = strict_json(mbytes)
    except Exception as e:
        print("CONTAINER REFUSED: MANIFEST.json unparseable: %s" % e)
        return 2
    print("\n[2] manifest: werk %s.%s, profile %s, sha256 %s"
          % (m["werk"]["major"], m["werk"]["minor"], m.get("profile"), sha(mbytes)))
    print("    entity: %s  (%s)" % (m["entity"]["name"], m["entity"]["uuid"]))
    if m["werk"]["major"] != 1:
        report("unsupported-major", "error", "MANIFEST.json", "werk.major %s" % m["werk"]["major"])
    if m.get("profile") != "3d-entity/1":
        report("unsupported-profile", "warn", "MANIFEST.json", m.get("profile"))

    # 3. Conventions --------------------------------------------------------
    conv = m.get("conventions", {})
    bad = [k for k, v in SUPPORTED_CONVENTIONS.items() if conv.get(k) != v]
    print("\n[3] conventions: %d checked, %s" % (len(SUPPORTED_CONVENTIONS),
                                               "all supported" if not bad else "UNSUPPORTED: %s" % bad))
    for k in bad:
        report("unsupported-convention", "error", k, "value %r" % conv.get(k))

    # 4. Signature ----------------------------------------------------------
    sbytes = c.read("SIGNATURE.json")
    if sbytes is None:
        sig_state = "absent"
    elif not crypto_ok:
        sig_state = "unverified"
    else:
        try:
            s = strict_json(sbytes)
            sig_state = "signed-and-valid"
            prev_sig = None
            for i, e in enumerate(s["chain"]):
                want_prev = "0" * 64 if i == 0 else sha(prev_sig.encode("utf-8"))
                if e["prev_entry_sha256"] != want_prev:
                    sig_state = "present-and-invalid"
                    print("    chain[%d]: prev_entry_sha256 mismatch" % i)
                msg = sig_message(e["manifest_sha256"], e["prev_entry_sha256"], e["signed_at"],
                                  e["signer"]["uri"], e["signer"]["kind"])
                ok = ed25519_verify(bytes.fromhex(e["public_key"]), msg, bytes.fromhex(e["signature"]))
                print("    chain[%d]: signer %r (%s), key %s..., message sha256 %s, ed25519 %s"
                      % (i, e["signer"]["name"], e["signer"]["kind"], e["public_key"][:16],
                         sha(msg)[:16], "VALID" if ok else "INVALID"))
                if not ok:
                    sig_state = "present-and-invalid"
                prev_sig = e["signature"]
            last = s["chain"][-1]["manifest_sha256"]
            if last != sha(mbytes) or s.get("manifest_sha256") != sha(mbytes):
                sig_state = "present-and-invalid"
                print("    anchor: manifest sha256 does not match the signed state")
            else:
                print("    anchor: last entry and top-level manifest_sha256 == sha256(MANIFEST.json)")
        except Exception as e:
            print("    could not evaluate SIGNATURE.json: %s" % e)
            sig_state = "unverified"
    code = {"signed-and-valid": ("signature-valid", "info"), "absent": ("signature-absent", "warn"),
            "present-and-invalid": ("signature-invalid", "error"),
            "unverified": ("signature-unverified", "warn")}[sig_state]
    report(code[0], code[1], "SIGNATURE.json", sig_state)
    print("[4] signature state: %s" % sig_state)

    # 5 + 6. Node graph and hashes -----------------------------------------
    nodes = {n["node_id"]: n for n in m["nodes"]}
    declared = {}          # path -> (node_id, sha256, size)
    owner_conflicts = []
    file_ok = {}           # path -> bool
    dead = set()
    print("\n[5] node graph: %d nodes" % len(nodes))
    for n in m["nodes"]:
        nid, typ = n["node_id"], n["type"]
        vers = {v["v"]: v for v in n["versions"]}
        act = vers.get(n.get("active"))
        if act is None:
            valid = sorted(k for k in vers if k < (n.get("active") or 0))
            if valid:
                act = vers[valid[-1]]
                report("active-fallback", "warn", nid, "active %r invalid, using v%d" % (n.get("active"), valid[-1]))
            else:
                report("no-active-version", "error", nid, "")
                dead.add(nid)
                continue
        meaning = TYPE_MEANING.get(typ)
        if meaning is None:
            if typ.startswith("x."):
                meaning = "extension type (x.*); its meaning is supplied by the extension, not by spec/"
                report("extension-type-uninterpreted", "info", nid,
                       "%s: hashes and file formats checked, semantics not interpreted" % typ)
            else:
                meaning = "UNKNOWN type"
                report("node-skipped-unknown-type", "info", nid, typ)
        for im in n.get("meta", {}).get("images", []):
            if not any(f["path"] == im.get("file") for f in act["files"]):
                report("meta-names-absent-file", "info", nid, "meta.images lists %s, not in files[]" % im.get("file"))
        print("\n  - %s  [%s]  v%d of %d, epistemic=%s%s"
              % (nid, typ, act["v"], len(vers), act.get("epistemic"),
                 (", confidence=%s" % act["confidence"]) if "confidence" in act else ""))
        print("      type meaning : %s" % meaning)
        print("      work note    : %s" % act.get("note", "(missing: law 6 says mandatory)"))
        p = act.get("producer", {})
        print("      producer     : %s %s%s" % (p.get("tool"), p.get("version"),
                                               (" model=" + p["model"]) if "model" in p else ""))
        for k in ("part_id", "material_id"):
            if k in n:
                print("      %-12s : %s" % (k, n[k]))
        for e in n.get("edges", []):
            tgt = "present" if e["to"] in nodes else "NOT IN PACKAGE"
            print("      edge         : %s --%s/%s--> %s (%s)" % (nid, e["kind"], e.get("role", ""), e["to"], tgt))
            if e["to"] not in nodes:
                sev = "warn" if e["kind"] == "requires" else "info"
                report("edge-target-missing", sev, nid, "%s edge to absent node %r" % (e["kind"], e["to"]))
        if act.get("epistemic") in ("measured", "inferred") and not ("input_hash" in act and "input_files" in act):
            report("missing-input-hash", "warn", nid, "derived version lacks input_hash/input_files")
        node_alive = True
        for f in act["files"]:
            path = f["path"]
            if path in declared and declared[path][0] != nid:
                owner_conflicts.append(path)
            declared[path] = (nid, f["sha256"], f["size"])
            b = c.read(path)
            if b is None:
                status, ok = "MISSING", False
            elif len(b) != f["size"]:
                status, ok = "SIZE %d != declared %d" % (len(b), f["size"]), False
            elif sha(b) != f["sha256"]:
                status, ok = "SHA256 MISMATCH (got %s)" % sha(b), False
            else:
                status, ok = "ok", True
            file_ok[path] = ok
            print("      file         : %-50s %7d B %s%s  sha256 %s"
                  % (path, f["size"], ("role=" + f["role"] + " ") if "role" in f else "", status, f["sha256"]))
            if not ok:
                node_alive = False
                report("hash-mismatch", "error", nid, "%s: %s" % (path, status))
        if not node_alive:
            dead.add(nid)
        if "meta" in n and typ == "core.loader":
            print("      loader meta  : %s, %s, capabilities=%s (NOT executed: SPEC 7.1 / task rule)"
                  % (n["meta"].get("language"), n["meta"].get("form"), n["meta"].get("capabilities")))

    # requires-edge propagation (SPEC 5)
    changed = True
    while changed:
        changed = False
        for n in m["nodes"]:
            if n["node_id"] in dead:
                continue
            for e in n.get("edges", []):
                if e["kind"] == "requires" and e["to"] in dead:
                    dead.add(n["node_id"])
                    report("requires-dead", "error", n["node_id"], "requires dead node %s" % e["to"])
                    changed = True

    print("\n[6] integrity")
    nfiles = len(file_ok)
    print("    declared files: %d, verified ok: %d" % (nfiles, sum(file_ok.values())))
    for pth in owner_conflicts:
        report("path-claimed-twice", "error", pth, "two different nodes list this path")
    # Licence hash
    lic = m.get("license", {})
    lb = c.read(lic.get("file", "LICENSE"))
    lic_ok = lb is not None and sha(lb) == lic.get("sha256")
    print("    license.sha256 (%s): %s" % (lic.get("file"), "ok" if lic_ok else "MISMATCH"))
    if not lic_ok:
        report("hash-mismatch", "error", "license", lic.get("file"))
    # Nothing floats
    floating = [n for n in c.entries if n not in declared and n not in ("MANIFEST.json", "SIGNATURE.json")]
    print("    zip entries not reachable from any node: %s" % (floating or "none"))
    for fl in floating:
        report("floating-file", "warn", fl, "not listed by any node")
    # spec_sha256 (SPEC 2)
    spec_files = sorted((p for p in declared if p.startswith("spec/")), key=lambda s: s.encode("utf-8"))
    hh = hashlib.sha256()
    for pth in spec_files:
        hh.update(pth.encode("utf-8") + b"\n" + bytes.fromhex(declared[pth][1]) + b"\n")
    spec_ok = hh.hexdigest() == m.get("spec_sha256")
    print("    spec_sha256 over %d spec/ files: computed %s, declared %s -> %s"
          % (len(spec_files), hh.hexdigest(), m.get("spec_sha256"), "ok" if spec_ok else "MISMATCH"))
    if not spec_ok:
        report("spec-sha256-mismatch", "error", "spec/", "")
    # input_hash (MINI-SPECS 11)
    print("    input_hash checks:")
    for n in m["nodes"]:
        for v in n["versions"]:
            if "input_hash" not in v:
                continue
            missing = [p for p in v.get("input_files", []) if c.read(p) is None]
            if missing:
                print("      %-32s v%d: NOT CHECKABLE, inputs not in package: %s" % (n["node_id"], v["v"], missing))
                report("input-hash-uncheckable", "info", n["node_id"], "absent inputs %s" % missing)
                continue
            h = hashlib.sha256()
            for pth in v["input_files"]:
                h.update(hashlib.sha256(c.read(pth)).digest())
            h.update(canonical_json(v.get("input_params") or {}).encode("utf-8"))
            ok = h.hexdigest() == v["input_hash"]
            print("      %-32s v%d: computed %s -> %s" % (n["node_id"], v["v"], h.hexdigest(), "ok" if ok else "STALE/MISMATCH"))
            if not ok:
                report("input-hash-mismatch", "warn", n["node_id"], "derived data may be stale")

    # 7. Payload parsing ----------------------------------------------------
    print("\n[7] payload parsing")
    for n in m["nodes"]:
        nid = n["node_id"]
        if nid in dead:
            print("    %s: dead, skipped" % nid)
            continue
        act = next(v for v in n["versions"] if v["v"] == n["active"])
        for f in act["files"]:
            pth = f["path"]
            b = c.read(pth)
            try:
                if pth.endswith(".glb"):
                    gj, summ = parse_glb(b)
                    for s_ in summ:
                        print("    %s: GLB ok, %s" % (pth, s_))
                    bnode = next((x for x in m["nodes"] if x["type"] == "core.phys.bounds"
                                  and any(e["to"] == nid for e in x.get("edges", []))), None)
                    if bnode:
                        bv = next(v for v in bnode["versions"] if v["v"] == bnode["active"])
                        bj = strict_json(c.read(bv["files"][0]["path"]))["entity"]
                        pos = [gj["accessors"][p["attributes"]["POSITION"]]
                               for mm in gj.get("meshes", []) for p in mm["primitives"]]
                        gmin = [min(a["min"][i] for a in pos) for i in range(3)]
                        gmax = [max(a["max"][i] for a in pos) for i in range(3)]
                        agree = all(abs(x - y) < 1e-5 for x, y in zip(gmin + gmax, bj["aabb_min"] + bj["aabb_max"]))
                        print("        bounds node %s aabb %s..%s vs GLB accessor min/max: %s"
                              % (bnode["node_id"], bj["aabb_min"], bj["aabb_max"], "agree" if agree else "DISAGREE"))
                        if not agree:
                            report("bounds-disagree", "warn", bnode["node_id"], "aabb != GLB POSITION min/max")
                elif pth.endswith(".wav"):
                    w = parse_wav(b)
                    print("    %s: WAV ok, %s, %d ch, %d Hz, %d bit, %.3f s"
                          % (pth, w["format"], w["channels"], w["sample_rate_hz"], w["bit_depth"], w["seconds"]))
                elif pth.endswith(".png"):
                    ih = parse_png_ihdr(b)
                    print("    %s: PNG ok, %dx%d, %d-bit, %d channels, interlace %d"
                          % (pth, ih["width"], ih["height"], ih["bit_depth"], ih["channels"], ih["interlace"]))
                    for im in n.get("meta", {}).get("images", []):
                        if im["file"] == pth and (im["width"], im["height"], im["channels"]) != (ih["width"], ih["height"], ih["channels"]):
                            report("meta-disagrees", "warn", nid, "%s IHDR != meta" % pth)
                elif pth.endswith(".json") or pth == "LICENSE" or pth.endswith((".txt", ".md")):
                    if pth.endswith(".json"):
                        strict_json(b)
                    else:
                        b.decode("utf-8")
                elif b[:2] == b"WK":
                    magic, ver, hdr, secs = read_envelope(b)
                    print("    %s: envelope %s v%d ok, kind %s, sections %s"
                          % (pth, magic.decode(), ver, hdr["kind"], [s_["name"] for s_ in hdr["sections"]]))
                    print("        header producer %s, trials %s, epistemic %s"
                          % (hdr.get("producer"), hdr.get("trials"), hdr.get("epistemic")))
                    if magic == b"WKRP":
                        poses, contacts, probs = decode_wkrp(hdr, secs)
                        for i, p_ in enumerate(poses):
                            print("        pose %d: q(wxyz)=%s p=%.4f contacts %d..%d area %.4f m2"
                                  % (i, tuple(round(q, 6) for q in p_["quat_wxyz"]), p_["probability"],
                                     p_["contact_first"], p_["contact_first"] + p_["contact_count"] - 1,
                                     p_["support_area_m2"]))
                        print("        contacts (model space, m): %s" % [tuple(round(x, 4) for x in c3) for c3 in contacts])
                        for pr in probs:
                            report("envelope-invariant", "error", nid, pr)
                    mp = act.get("producer", {})
                    if n["type"] != "core.spec" and hdr.get("producer") and hdr["producer"].get("tool") != mp.get("tool"):
                        report("producer-disagrees", "warn", nid, "envelope header producer %s != manifest producer %s"
                               % (hdr["producer"], mp))
            except Exception as e:
                report("payload-invalid", "error", nid, "%s: %s" % (pth, e))
                print("    %s: INVALID: %s" % (pth, e))
    # Sound descriptor vs WAV
    snd = nodes.get(m.get("primary", {}).get("sound", ""))
    if snd:
        act = next(v for v in snd["versions"] if v["v"] == snd["active"])
        desc = [f["path"] for f in act["files"] if f.get("role") == "descriptor"]
        if desc:
            af = strict_json(c.read(desc[0])).get("audio_format", {})
            for f in act["files"]:
                if f["path"].endswith(".wav"):
                    w = parse_wav(c.read(f["path"]))
                    same = (af.get("sample_rate_hz"), af.get("channels"), af.get("bit_depth"), af.get("sample_format")) == \
                           (w["sample_rate_hz"], w["channels"], w["bit_depth"], w["format"])
                    if not same:
                        report("audio-format-disagrees", "warn", snd["node_id"], f["path"])
            print("    descriptor audio_format %s checked against every WAV take" % af)

    # 8. Extraction ---------------------------------------------------------
    print("\n[8] extraction to %s" % outdir)
    os.makedirs(outdir, exist_ok=True)
    primary = m.get("primary", {})
    results = []
    for slot, fallback_type in (("mesh", "core.geom.game"), ("sound", "core.audio.effect")):
        nid = primary.get(slot)
        if nid is None:
            cand = [n["node_id"] for n in m["nodes"] if n["type"] == fallback_type]
            nid = cand[0] if cand else None
            report("primary-fallback", "warn", slot, "primary.%s absent, fell back to %s" % (slot, nid))
        n = nodes.get(nid)
        if n is None or nid in dead:
            report("primary-unavailable", "error", slot, "node %r missing or dead" % nid)
            continue
        act = next(v for v in n["versions"] if v["v"] == n["active"])
        path, rule = resolve_payload(n, act)
        if path is None:
            report("payload-file-ambiguous", "warn", nid, rule)
            print("    primary.%s -> %s: %s" % (slot, nid, rule))
            continue
        decl = next(f for f in act["files"] if f["path"] == path)
        data = c.read(path)
        out = os.path.join(outdir, path.split("/")[-1])
        with open(out, "wb") as fh:
            fh.write(data)
        with open(out, "rb") as fh:
            written = fh.read()
        got = sha(written)
        ok = got == decl["sha256"] and len(written) == decl["size"]
        results.append((slot, nid, path, out, decl["sha256"], got, ok))
        print("    primary.%s -> node %s -> %s via %s" % (slot, nid, path, rule))
        print("        wrote %s (%d B)\n        declared sha256 %s\n        computed sha256 %s -> %s"
              % (out, len(written), decl["sha256"], got, "MATCH" if ok else "MISMATCH"))
        if not ok:
            report("extract-mismatch", "error", nid, out)

    # Report ----------------------------------------------------------------
    print("\n[9] report entries")
    for code_, sev, subj, det in REPORT:
        print("    %-5s %-28s %-34s %s" % (sev, code_, subj, det))
    errors = [r for r in REPORT if r[1] == "error"]
    print("\nsummary: signature=%s, dead nodes=%s, errors=%d, extracted=%d/2 matching"
          % (sig_state, sorted(dead) or "none", len(errors), sum(r[6] for r in results)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
