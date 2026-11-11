"""werkread.py -- an independent reader for a .werk package.

Written from the specification travelling inside the package (spec/SPEC.md,
spec/MINI-SPECS.md, spec/layouts/*.layout.txt). It does NOT use, import, or
port any of the bundled loaders/. Standard library only; the zip container is
parsed by hand per MINI-SPECS §5 and cross-checked against `zipfile`.

usage: python -I werkread.py PACKAGE.werk
"""
import hashlib
import json
import math
import struct
import sys
import zipfile
import zlib

REPORT = []          # (severity, code, subject, detail)


def report(sev, code, subject, detail=""):
    REPORT.append((sev, code, subject, detail))


# --------------------------------------------------------------------------
# Primitives proven against the test vectors printed in MINI-SPECS
# --------------------------------------------------------------------------

def crc32(data):                                  # MINI-SPECS §6
    crc = 0xFFFFFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ (0xEDB88320 if crc & 1 else 0)
    return crc ^ 0xFFFFFFFF


def crc32_fast(data):
    # zlib.crc32 is the same reflected 0xEDB88320 function; proven equal to
    # the spec's bitwise definition in self_test() before it is used.
    return zlib.crc32(data) & 0xFFFFFFFF


def sha256(b):
    return hashlib.sha256(b).hexdigest()


# Ed25519 verification, MINI-SPECS §12 -- every constant derived from the text
P = 2 ** 255 - 19
L = 2 ** 252 + 27742317777372353535851937790883648493


def inv(a):
    return pow(a, P - 2, P)


D = (-121665 * inv(121666)) % P
I = pow(2, (P - 1) // 4, P)


def recover_x(y, sign):
    u = (y * y - 1) % P
    v = (D * y * y + 1) % P
    x = (u * pow(v, 3, P) * pow(u * pow(v, 7, P), (P - 5) // 8, P)) % P
    if (v * x * x - (-u)) % P == 0:
        x = (x * I) % P
    if (v * x * x - u) % P != 0:
        return None
    if x == 0 and sign == 1:
        return None
    if (x & 1) != sign:
        x = P - x
    return x


def decompress(b32):
    if len(b32) != 32:
        return None
    n = int.from_bytes(b32, "little")
    sign = n >> 255
    y = n & ((1 << 255) - 1)
    if y >= P:
        return None
    x = recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, (x * y) % P)


def padd(p1, p2):
    X1, Y1, Z1, T1 = p1
    X2, Y2, Z2, T2 = p2
    A = (Y1 - X1) * (Y2 - X2) % P
    B = (Y1 + X1) * (Y2 + X2) % P
    C = T1 * 2 * D * T2 % P
    Dd = Z1 * 2 * Z2 % P
    E, F, G, H = B - A, Dd - C, Dd + C, B + A
    return (E * F % P, G * H % P, F * G % P, E * H % P)


def pmul(s, pt):
    q = (0, 1, 1, 0)                              # neutral element
    while s > 0:
        if s & 1:
            q = padd(q, pt)
        pt = padd(pt, pt)
        s >>= 1
    return q


def peq(p1, p2):
    X1, Y1, Z1, _ = p1
    X2, Y2, Z2, _ = p2
    return (X1 * Z2 - X2 * Z1) % P == 0 and (Y1 * Z2 - Y2 * Z1) % P == 0


_by = 4 * inv(5) % P
BASE = (recover_x(_by, 0), _by, 1, recover_x(_by, 0) * _by % P)


def ed25519_verify(pub, msg, sig):
    if len(sig) != 64:
        return False
    A = decompress(pub)
    R = decompress(sig[:32])
    S = int.from_bytes(sig[32:], "little")
    if A is None or R is None or S >= L:
        return False
    k = int.from_bytes(hashlib.sha512(sig[:32] + pub + msg).digest(), "little") % L
    lhs = pmul(8, pmul(S, BASE))
    rhs = pmul(8, padd(R, pmul(k, A)))
    return peq(lhs, rhs)


def self_test():
    ok = True
    ok &= crc32(b"123456789") == 0xCBF43926
    ok &= crc32_fast(b"123456789") == 0xCBF43926
    ok &= sha256(b"") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    ok &= sha256(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    ok &= hashlib.sha512(b"abc").hexdigest().startswith("ddaf35a193617aba")
    # RFC 8032 vector 1, as printed in MINI-SPECS §12
    ok &= ed25519_verify(
        bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"), b"",
        bytes.fromhex("e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"))
    # MINI-SPECS §12.1 worked message; checkpoint sha256 then the signature
    m = ("werk-sig/1\nc421d2e85a9455f0be794ca8ee673f727a7ef67485d631e374f95c4a6d6ce61a\n" + "0" * 64 +
         "\n2026-08-08T09:00:00Z\nurn:werk:fixture:rfc8032-vector-1\nservice").encode()
    ok &= len(m) == 203 and sha256(m) == "11e260cc16bc454f39f1aa6d56679c868ba1e83d33e3c22a462040b32a92165a"
    ok &= ed25519_verify(
        bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"), m,
        bytes.fromhex("55720b6fc38d680f8ca7523c0d8cec5045c7247f7158ab54eafd03d6ea0eedb1"
                      "aeb4902b4704a5c2e78d7713b375068748bea4fd116a2d3a49f6010074c6410d"))
    # a tampered message must fail
    ok &= not ed25519_verify(
        bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"), b"x",
        bytes.fromhex("e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"))
    return ok


# --------------------------------------------------------------------------
# Container: store-mode zip, MINI-SPECS §5
# --------------------------------------------------------------------------

class Entry:
    pass


def open_zip(buf):
    n = len(buf)
    eocd = -1
    for off in range(n - 22, max(0, n - 22 - 65535) - 1, -1):
        if buf[off:off + 4] == b"PK\x05\x06":
            eocd = off
            break
    if eocd < 0:
        raise SystemExit("container refused: no EOCD")
    _, disk, cddisk, n_disk, n_total, cd_size, cd_off, clen = struct.unpack_from("<IHHHHIIH", buf, eocd)
    if 0xFFFF in (n_disk, n_total) or 0xFFFFFFFF in (cd_size, cd_off) or \
            (eocd >= 20 and buf[eocd - 20:eocd - 16] == b"PK\x06\x07"):
        report("error", "zip64-unsupported", "container")
        raise SystemExit(2)
    entries = []
    p = cd_off
    for _ in range(n_total):
        if buf[p:p + 4] != b"PK\x01\x02":
            raise SystemExit("container refused: bad central directory signature at %d" % p)
        (flags, method, crc, csize, usize, nlen, mlen, klen) = struct.unpack_from("<HH4xIIIHHH", buf, p + 8)
        lho = struct.unpack_from("<I", buf, p + 42)[0]
        e = Entry()
        e.name = buf[p + 46:p + 46 + nlen].decode("utf-8")
        e.flags, e.method, e.crc, e.csize, e.usize, e.lho = flags, method, crc, csize, usize, lho
        p += 46 + nlen + mlen + klen
        if buf[lho:lho + 4] != b"PK\x03\x04":
            raise SystemExit("container refused: bad local header for %s" % e.name)
        ln, lm = struct.unpack_from("<HH", buf, lho + 26)
        e.data_off = lho + 30 + ln + lm
        entries.append(e)
    return {"eocd": eocd, "cd_off": cd_off, "cd_size": cd_size, "count": n_total}, entries


def entry_bytes(buf, e):
    if e.method != 0:
        report("error", "unsupported-compression", e.name, "method %d" % e.method)
        return None
    return buf[e.data_off:e.data_off + e.csize]


# --------------------------------------------------------------------------
# JSON, strict per MINI-SPECS §3
# --------------------------------------------------------------------------

def _no_dupes(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise ValueError("duplicate key %r" % k)
        d[k] = v
    return d


def _no_nonfinite(s):
    raise ValueError("non-finite number %s" % s)


def strict_json(b):
    if b.startswith(b"\xef\xbb\xbf"):
        raise ValueError("BOM")
    return json.loads(b.decode("utf-8"), object_pairs_hook=_no_dupes, parse_constant=_no_nonfinite)


def canonical_json(v):
    def enc(x):
        if isinstance(x, dict):
            items = sorted(x.items(), key=lambda kv: kv[0].encode("utf-8"))
            return "{" + ",".join(enc(k) + ":" + enc(val) for k, val in items) + "}"
        if isinstance(x, list):
            return "[" + ",".join(enc(i) for i in x) + "]"
        if isinstance(x, str):
            out = []
            for ch in x:
                c = ord(ch)
                if ch == '"': out.append('\\"')
                elif ch == "\\": out.append("\\\\")
                elif ch in "\b\f\n\r\t":
                    out.append({"\b": "\\b", "\f": "\\f", "\n": "\\n", "\r": "\\r", "\t": "\\t"}[ch])
                elif c < 0x20: out.append("\\u%04x" % c)
                else: out.append(ch)
            return '"' + "".join(out) + '"'
        if x is True: return "true"
        if x is False: return "false"
        if x is None: return "null"
        if isinstance(x, int): return str(x)
        if isinstance(x, float):
            return str(int(x)) if x.is_integer() else repr(x)
        raise TypeError(type(x))
    return enc(v).encode("utf-8")


# --------------------------------------------------------------------------
# Envelope: spec/layouts/ENVELOPE.layout.txt
# --------------------------------------------------------------------------

class EnvelopeError(Exception):
    pass


BANNED = {0xc1, 0xc7, 0xc8, 0xc9, 0xd4, 0xd5, 0xd6, 0xd7, 0xd8}


def mp_decode(b, i=0):
    """MessagePack subset of ENVELOPE §4.1. Big-endian inside. Returns (value, next)."""
    t = b[i]
    i += 1
    if t in BANNED:
        raise EnvelopeError("banned MessagePack byte 0x%02x" % t)
    if t <= 0x7f: return t, i
    if t >= 0xe0: return t - 256, i
    if 0xa0 <= t <= 0xbf:
        n = t & 0x1f
        return b[i:i + n].decode("utf-8"), i + n
    if 0x90 <= t <= 0x9f: return _mp_arr(b, i, t & 0x0f)
    if 0x80 <= t <= 0x8f: return _mp_map(b, i, t & 0x0f)
    if t == 0xc0: return None, i
    if t == 0xc2: return False, i
    if t == 0xc3: return True, i
    fixed = {0xcc: ">B", 0xcd: ">H", 0xce: ">I", 0xcf: ">Q", 0xd0: ">b", 0xd1: ">h",
             0xd2: ">i", 0xd3: ">q", 0xca: ">f", 0xcb: ">d"}
    if t in fixed:
        f = fixed[t]
        return struct.unpack_from(f, b, i)[0], i + struct.calcsize(f)
    lens = {0xd9: ">B", 0xda: ">H", 0xdb: ">I", 0xc4: ">B", 0xc5: ">H", 0xc6: ">I"}
    if t in lens:
        f = lens[t]
        n = struct.unpack_from(f, b, i)[0]
        i += struct.calcsize(f)
        raw = b[i:i + n]
        return (raw.decode("utf-8") if t in (0xd9, 0xda, 0xdb) else bytes(raw)), i + n
    if t == 0xdc: return _mp_arr(b, i + 2, struct.unpack_from(">H", b, i)[0])
    if t == 0xdd: return _mp_arr(b, i + 4, struct.unpack_from(">I", b, i)[0])
    if t == 0xde: return _mp_map(b, i + 2, struct.unpack_from(">H", b, i)[0])
    if t == 0xdf: return _mp_map(b, i + 4, struct.unpack_from(">I", b, i)[0])
    raise EnvelopeError("unknown MessagePack byte 0x%02x" % t)


def _mp_arr(b, i, n):
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
        if k in out:
            raise EnvelopeError("duplicate header key %r" % k)
        out[k] = v
    return out, i


DTYPE = {"u8": ("<B", 1), "i8": ("<b", 1), "u16": ("<H", 2), "i16": ("<h", 2),
         "u32": ("<I", 4), "i32": ("<i", 4), "u64": ("<Q", 8), "i64": ("<q", 8),
         "f32": ("<f", 4), "f64": ("<d", 8)}
MAGICS = {b"WKFF": "core.field.flow", b"WKRP": "core.pose.rest", b"WKAC": "core.anim.clip",
          b"WKSK": "core.skeleton", b"WKEM": "core.embedding", b"WKPC": "core.geom.points",
          b"WKGS": "core.geom.gsplat"}


def prod(xs):
    r = 1
    for x in xs:
        r *= x
    return r


def read_envelope(buf):
    """ENVELOPE §7 reference reader, every assertion made explicit."""
    def need(cond, why):
        if not cond:
            raise EnvelopeError(why)
    need(len(buf) >= 12, "file shorter than 12 bytes")
    magic = bytes(buf[0:4])
    version, header_len = struct.unpack_from("<II", buf, 4)
    need(header_len >= 1, "empty header")
    need(12 + header_len <= len(buf), "header_len runs past end of file")
    header, end = mp_decode(buf[12:12 + header_len])
    need(end == header_len, "header map ends at %d, header_len says %d" % (end, header_len))
    need(isinstance(header, dict), "header is not a map")
    for k in ("kind", "endianness", "payload_origin", "payload_size", "sections"):
        need(k in header, "mandatory header key %r missing" % k)
    need(header["endianness"] == "le", "endianness is not 'le'")
    if magic in MAGICS:
        need(header["kind"] == MAGICS[magic], "kind %r does not match magic %r" % (header["kind"], magic))
    elif not (magic[:3] == b"WKX" and magic[3:4].isdigit()):
        raise EnvelopeError("unrecognised magic %r" % magic)
    Pc = 16 * math.ceil((12 + header_len) / 16)
    need(header["payload_origin"] == Pc, "payload_origin %d != computed %d" % (header["payload_origin"], Pc))
    need(Pc + header["payload_size"] == len(buf), "payload_origin+payload_size != file size")
    pad = buf[12 + header_len:Pc]
    if any(pad):
        report("warn", "envelope-nonzero-padding", "", "writer emitted nonzero padding")
    sections = {}
    prev_end = Pc
    names = set()
    for idx, s in enumerate(header["sections"]):
        for k in ("name", "offset", "size", "dtype", "shape", "stride"):
            need(k in s, "section %d missing key %r" % (idx, k))
        need(s["name"] not in names, "duplicate section name %r" % s["name"])
        names.add(s["name"])
        off, size, stride, shape = s["offset"], s["size"], s["stride"], s["shape"]
        need(off % 16 == 0, "section %s offset %d not 16-aligned" % (s["name"], off))
        if idx == 0:
            need(off == Pc, "section 0 does not start at payload_origin")
        need(prev_end <= off <= prev_end + 15 and not any(buf[prev_end:off]),
             "section %s: gap other than 0..15 zero bytes before it" % s["name"])
        need(off + size <= len(buf), "section %s runs past end of file" % s["name"])
        if s["dtype"] == "record":
            esz = stride
        else:
            need(s["dtype"] in DTYPE, "unknown dtype %r" % s["dtype"])
            esz = DTYPE[s["dtype"]][1]
        if stride == esz:
            need(size == stride * prod(shape), "section %s: size != stride*prod(shape)" % s["name"])
        else:
            need(stride >= esz * shape[-1], "section %s: stride < esz*shape[-1]" % s["name"])
            need(size == stride * prod(shape[:-1]), "section %s: size != stride*prod(shape[:-1])" % s["name"])
        prev_end = off + size
        sections[s["name"]] = (s, buf[off:off + size])
    last = header["sections"][-1] if header["sections"] else None
    tail = (16 * math.ceil(prev_end / 16)) if last else Pc
    need(tail == Pc + header["payload_size"], "trailing data after last section")
    return magic, version, header, sections


def decode_restposes(header, sections):
    """spec/layouts/restposes.layout.txt"""
    for k in ("pose_count", "contact_count", "trials"):
        if k not in header:
            raise EnvelopeError("WKRP header key %r missing" % k)
    for nm in ("poses", "contacts"):
        if nm not in sections:
            raise EnvelopeError("WKRP section %r missing" % nm)
    known = {"poses", "contacts"}
    for nm in sections:
        if nm not in known:
            report("info", "section-skipped-unknown", nm)
    ps, pb = sections["poses"]
    cs, cb = sections["contacts"]
    if ps["dtype"] != "record" or ps["stride"] != 32 or ps["shape"] != [header["pose_count"]]:
        raise EnvelopeError("poses section does not match layout (record, stride 32, shape [pose_count])")
    if cs["dtype"] != "f32" or cs["stride"] != 12 or cs["shape"] != [header["contact_count"], 3]:
        raise EnvelopeError("contacts section does not match layout (f32, stride 12, shape [n,3])")
    poses = []
    for n in range(header["pose_count"]):
        w, x, y, z, cf, cc, prob, area = struct.unpack_from("<4f2I2f", pb, n * ps["stride"])
        poses.append({"quat_wxyz": (w, x, y, z), "contact_first": cf, "contact_count": cc,
                      "probability": prob, "support_area_m2": area})
    contacts = [struct.unpack_from("<3f", cb, c * cs["stride"]) for c in range(header["contact_count"])]
    # NaN / inf ban (ENVELOPE §6)
    for p in poses:
        for v in list(p["quat_wxyz"]) + [p["probability"], p["support_area_m2"]]:
            if not math.isfinite(v):
                raise EnvelopeError("non-finite float in poses")
    for c in contacts:
        if not all(math.isfinite(v) for v in c):
            raise EnvelopeError("non-finite float in contacts")
    checks = []
    checks.append(("sum(contact_count) == header contact_count",
                   sum(p["contact_count"] for p in poses) == header["contact_count"]))
    checks.append(("every contact_count >= 1", all(p["contact_count"] >= 1 for p in poses)))
    checks.append(("contact ranges inside section 1",
                   all(p["contact_first"] + p["contact_count"] <= header["contact_count"] for p in poses)))
    checks.append(("sorted by probability descending",
                   all(poses[i]["probability"] >= poses[i + 1]["probability"] for i in range(len(poses) - 1))))
    if header["trials"] > 0:
        checks.append(("sum(probability) == 1 +/- 1e-3", abs(sum(p["probability"] for p in poses) - 1.0) <= 1e-3))
    else:
        checks.append(("trials == 0 -> every probability == 0", all(p["probability"] == 0.0 for p in poses)))
    checks.append(("|q| within 1e-6 of 1",
                   all(abs(math.sqrt(sum(c * c for c in p["quat_wxyz"])) - 1.0) <= 1e-6 for p in poses)))
    checks.append(("w >= 0 (canonical sign)", all(p["quat_wxyz"][0] >= 0 for p in poses)))
    checks.append(("support_area 0 when < 3 contacts",
                   all(p["support_area_m2"] == 0.0 for p in poses if p["contact_count"] < 3)))
    return poses, contacts, checks


# --------------------------------------------------------------------------
# Payload sniffing for the listing (MINI-SPECS §8-10)
# --------------------------------------------------------------------------

def sniff(path, b):
    try:
        if b[:8] == b"\x89PNG\r\n\x1a\n":
            w, h, bd, ct, _, _, il = struct.unpack_from(">IIBBBBB", b, 16)
            # verify every chunk CRC
            p, bad = 8, 0
            while p + 8 <= len(b):
                ln = struct.unpack_from(">I", b, p)[0]
                typ = b[p + 4:p + 8]
                if crc32_fast(b[p + 4:p + 8 + ln]) != struct.unpack_from(">I", b, p + 8 + ln)[0]:
                    bad += 1
                p += 12 + ln
                if typ == b"IEND":
                    break
            return "PNG %dx%d, bit depth %d, colour type %d, interlace %d, chunk CRCs %s" % (
                w, h, bd, ct, il, "ok" if bad == 0 else "%d BAD" % bad)
        if b[:4] == b"RIFF" and b[8:12] == b"WAVE":
            p, fmt, dsz = 12, None, None
            while p + 8 <= len(b):
                cid, sz = b[p:p + 4], struct.unpack_from("<I", b, p + 4)[0]
                if cid == b"fmt ":
                    fmt = struct.unpack_from("<HHIIHH", b, p + 8)
                elif cid == b"data":
                    dsz = sz
                p += 8 + sz + (sz & 1)
            af, ch, sr, br, ba, bps = fmt
            frames = dsz // ba
            return "WAV format %d (%s), %d ch, %d Hz, %d-bit, %d frames = %.3f s" % (
                af, {1: "PCM", 3: "float", 0xFFFE: "extensible"}.get(af, "?"), ch, sr, bps, frames, frames / sr)
        if b[:4] == b"glTF":
            ver, total = struct.unpack_from("<II", b, 4)
            jl, jt = struct.unpack_from("<II", b, 12)
            gj = json.loads(b[20:20 + jl].decode("utf-8"))
            prims = sum(len(m.get("primitives", [])) for m in gj.get("meshes", []))
            acc = gj.get("accessors", [])
            attrs = []
            for m in gj.get("meshes", []):
                for pr in m.get("primitives", []):
                    attrs = sorted(pr.get("attributes", {}))
                    pos = acc[pr["attributes"]["POSITION"]]
                    idx = acc[pr["indices"]]["count"] if "indices" in pr else None
            return "GLB v%d, %d bytes (header says %d), %d mesh(es) %d primitive(s), attrs %s, %d verts, %s indices" % (
                ver, len(b), total, len(gj.get("meshes", [])), prims, attrs, pos["count"], idx)
        if b[:2] == b"WK":
            return "werk envelope, magic %r" % bytes(b[:4])
        if path.endswith(".json"):
            strict_json(b)
            return "JSON (strict parse ok)"
        b.decode("utf-8")
        return "UTF-8 text, %d lines" % (b.count(b"\n"))
    except Exception as ex:                       # describe, never crash
        return "could not sniff: %s" % ex


TYPE_MEANING = {
    "core.geom.game": "runtime mesh (GLB)",
    "core.geom.source": "source mesh (GLB)",
    "core.material": "PBR material parameters (JSON)",
    "core.phys.bounds": "measured bounding volumes (JSON)",
    "core.semantics": "facet tags, palette, search text (JSON)",
    "core.provenance": "who made what, from what (JSON)",
    "core.audio.effect": "sound effect: WAV takes + JSON descriptor",
    "core.spec": "the format specification travelling with the file",
    "core.loader": "bundled single-file reader (source)",
    "core.license": "embedded licence text",
    "core.readme": "human one-pager",
    "core.pose.rest": "settled rest poses (WKRP binary envelope)",
}


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main(path):
    print("== self-test (MINI-SPECS test vectors: CRC-32, SHA-256, SHA-512, Ed25519 x2) ==")
    st = self_test()
    print("   ", "PASS" if st else "FAIL")
    if not st:
        report("error", "self-test-failed", "reader")

    buf = open(path, "rb").read()
    print("\n== container ==")
    info, entries = open_zip(buf)
    print("    %d bytes, %d entries, central directory @%d (%d bytes), EOCD @%d"
          % (len(buf), info["count"], info["cd_off"], info["cd_size"], info["eocd"]))
    files = {}
    for e in entries:
        bad_name = e.name.startswith("/") or ".." in e.name.split("/") or ":" in e.name or "\\" in e.name
        if bad_name:
            report("error", "zip-bad-name", e.name)
        if e.flags & 0x8:
            report("warn", "zip-data-descriptor", e.name)
        if not e.flags & 0x800:
            report("info", "zip-utf8-flag-unset", e.name)
        data = entry_bytes(buf, e)
        if data is None:
            continue
        if len(data) != e.usize:
            report("error", "zip-size-mismatch", e.name)
        if crc32_fast(data) != e.crc:
            report("error", "zip-crc-mismatch", e.name)
        files[e.name] = bytes(data)
    # cross-check the hand parser against the stdlib zip library
    with zipfile.ZipFile(path) as z:
        lib = {i.filename: z.read(i) for i in z.infolist()}
    agree = lib.keys() == files.keys() and all(lib[k] == files[k] for k in files)
    print("    hand-rolled zip parser agrees with stdlib zipfile:", agree)
    print("    all entries store-mode:", all(e.method == 0 for e in entries))
    print("    all zip CRC-32s verified:", not any(r[1] == "zip-crc-mismatch" for r in REPORT))

    print("\n== MANIFEST.json ==")
    if "MANIFEST.json" not in files:
        report("error", "manifest-missing", "container")
        raise SystemExit(2)
    mbytes = files["MANIFEST.json"]
    m = strict_json(mbytes)
    print("    werk %s.%s  profile %s" % (m["werk"]["major"], m["werk"]["minor"], m["profile"]))
    print("    entity: %s  (%s)" % (m["entity"]["name"], m["entity"]["uuid"]))
    if m["werk"]["major"] != 1 or m["profile"] != "3d-entity/1":
        report("error", "unsupported-profile", m["profile"])
    SUPPORTED = {"endianness": "le", "units_per_meter": 1.0, "length_unit": "metre", "angle_unit": "radian",
                 "time_unit": "second", "mass_unit": "kilogram", "up_axis": "y", "forward_axis": "-z",
                 "right_axis": "+x", "handedness": "right", "winding": "ccw", "quat_order": "wxyz",
                 "alignment_bytes": 16, "text_encoding": "utf-8", "id_case": "kebab-case",
                 "hash_algorithm": "sha256", "signature_algorithm": "ed25519"}
    conv = m["conventions"]
    for k, want in SUPPORTED.items():
        if conv.get(k) != want:
            report("error", "unsupported-convention", k, "%r" % conv.get(k))
    print("    conventions checked against this reader's support set: %d keys, %d refusals"
          % (len(SUPPORTED), sum(1 for r in REPORT if r[1] == "unsupported-convention")))

    # ---- listing + per-file integrity
    print("\n== contents (node -> files), with meanings and integrity ==")
    declared = {}
    dead = set()
    nodes = {n["node_id"]: n for n in m["nodes"]}
    for n in m["nodes"]:
        versions = {v["v"]: v for v in n["versions"]}
        if n.get("active") not in versions:
            report("error", "active-version-invalid", n["node_id"])
            continue
        v = versions[n["active"]]
        print("  [%s] %s  -- %s" % (n["node_id"], n["type"], TYPE_MEANING.get(n["type"], "(unknown type: skipped)")))
        print("        epistemic=%s producer=%s  note: %s" % (
            v.get("epistemic"), v.get("producer", {}).get("tool"), v.get("note", "")[:110]))
        if n["type"] not in TYPE_MEANING and not n["type"].startswith("x."):
            report("info", "node-skipped-unknown-type", n["node_id"])
        for f in v["files"]:
            declared[f["path"]] = f
            b = files.get(f["path"])
            if b is None:
                report("error", "file-missing", n["node_id"], f["path"])
                dead.add(n["node_id"])
                print("        MISSING %s" % f["path"])
                continue
            size_ok = len(b) == f["size"]
            hash_ok = sha256(b) == f["sha256"]
            if not size_ok:
                report("error", "size-mismatch", n["node_id"], f["path"])
            if not hash_ok:
                report("error", "hash-mismatch", n["node_id"], f["path"])
            if not (size_ok and hash_ok):
                dead.add(n["node_id"])
            print("        %-48s %7d B  sha256 %s  %s" % (
                f["path"], len(b), "ok " if (size_ok and hash_ok) else "BAD", sniff(f["path"], b)))
        if "payload_file" in v and v["payload_file"] not in [f["path"] for f in v["files"]]:
            report("error", "payload-file-not-in-files", n["node_id"])
        # input_hash (MINI-SPECS §11 "What gets hashed")
        if "input_hash" in v:
            raws = []
            missing = []
            for ip in v.get("input_files", []):
                if ip in files:
                    raws.append(hashlib.sha256(files[ip]).digest())
                else:
                    missing.append(ip)
            if missing:
                report("info", "input-hash-not-checkable", n["node_id"], "inputs not in package: %s" % missing)
                print("        input_hash: not checkable (inputs not in package: %s)" % ", ".join(missing))
            else:
                got = sha256(b"".join(raws) + canonical_json(v.get("input_params", {})))
                ok = got == v["input_hash"]
                print("        input_hash: %s" % ("ok (inputs are current)" if ok else "STALE (recomputed %s)" % got))
                if not ok:
                    report("warn", "input-hash-stale", n["node_id"])
        for e in n.get("edges", []):
            if e["to"] not in nodes:
                report("info" if e["kind"] == "enhances" else "warn", "edge-target-absent", n["node_id"],
                       "%s edge -> %s (not in this package)" % (e["kind"], e["to"]))
            elif e["kind"] == "requires" and e["to"] in dead:
                dead.add(n["node_id"])

    undeclared = [p for p in files if p not in declared and p not in ("MANIFEST.json", "SIGNATURE.json")]
    for p in undeclared:
        report("warn", "file-undeclared", p)
    print("\n    container entries not declared in any files[] (besides MANIFEST/SIGNATURE):", undeclared or "none")

    # license hash
    lic = m.get("license", {})
    if lic:
        ok = sha256(files.get(lic["file"], b"")) == lic["sha256"]
        print("    license.sha256 (%s): %s" % (lic["file"], "ok" if ok else "MISMATCH"))
        if not ok:
            report("error", "hash-mismatch", "license")

    # spec_sha256 (SPEC §2, S-29)
    spec_paths = sorted({p for p in declared if p.startswith("spec/")}, key=lambda s: s.encode("utf-8"))
    acc = b"".join(p.encode("utf-8") + b"\n" + bytes.fromhex(declared[p]["sha256"]) + b"\n" for p in spec_paths)
    got = sha256(acc)
    print("    spec_sha256 over %d declared spec/ files: %s" % (len(spec_paths), "ok" if got == m.get("spec_sha256") else "MISMATCH " + got))
    if got != m.get("spec_sha256"):
        report("error", "spec-sha256-mismatch", "spec")

    # preview_prefix_bytes is a HINT (SPEC §1, S-15): report, never fail
    ppb = m.get("container", {}).get("preview_prefix_bytes")
    if ppb is not None:
        tier = {"MANIFEST.json", "SIGNATURE.json", "LICENSE", "README.txt"}
        prim = nodes.get(m.get("primary", {}).get("sound"))
        prim_path = prim["versions"][0].get("payload_file") if prim else None
        ends = [e.data_off + e.csize for e in entries
                if e.name in tier or e.name.startswith(("loaders/", "spec/", "semantics/", "imposters/"))
                or e.name == prim_path]
        print("    preview_prefix_bytes (hint) declared %d, recomputed %d" % (ppb, max(ends)))
        if ppb != max(ends):
            report("info", "preview-prefix-differs", "container", "declared %d recomputed %d" % (ppb, max(ends)))

    # ---- signature chain (SPEC §6, MINI-SPECS §12)
    print("\n== SIGNATURE.json ==")
    state = "absent"
    if "SIGNATURE.json" in files:
        s = strict_json(files["SIGNATURE.json"])
        if not st:
            state = "unverified"
        else:
            all_ok = True
            prev = "0" * 64
            for i, ent in enumerate(s["chain"]):
                msg = "\n".join(["werk-sig/1", ent["manifest_sha256"], ent["prev_entry_sha256"],
                                 ent["signed_at"], ent["signer"]["uri"], ent["signer"]["kind"]]).encode("utf-8")
                sig_ok = ed25519_verify(bytes.fromhex(ent["public_key"]), msg, bytes.fromhex(ent["signature"]))
                prev_ok = ent["prev_entry_sha256"] == prev
                print("    entry %d signer=%s key=%s..  sig %s, prev link %s" % (
                    i, ent["signer"]["uri"], ent["public_key"][:16], "valid" if sig_ok else "INVALID",
                    "ok" if prev_ok else "BROKEN"))
                all_ok &= sig_ok and prev_ok
                prev = sha256(ent["signature"].encode("utf-8"))
            actual = sha256(mbytes)
            anchor_ok = s["chain"][-1]["manifest_sha256"] == actual and s.get("manifest_sha256") == actual
            print("    last entry + top-level manifest_sha256 == sha256(MANIFEST.json bytes):", anchor_ok)
            all_ok &= anchor_ok
            state = "signed-and-valid" if all_ok else "present-and-invalid"
            if not all_ok:
                report("error", "signature-invalid", "SIGNATURE.json")
    print("    signature state:", state)
    print("    (the key is a publicly derived DEV key -- valid means 'this key signed this state', nothing more)")

    # ---- envelopes
    print("\n== binary envelopes ==")
    for n in m["nodes"]:
        layout = m.get("layouts", {}).get(n["type"])
        v = {x["v"]: x for x in n["versions"]}[n["active"]]
        for f in v["files"]:
            b = files.get(f["path"])
            if b is None or b[:2] != b"WK":
                continue
            print("  node %s  file %s  (layout: %s)" % (n["node_id"], f["path"], layout))
            try:
                magic, ver, hdr, secs = read_envelope(b)
                print("    magic %r -> %s, envelope version %d, header %d keys, payload_origin %d, payload_size %d"
                      % (magic.decode(), MAGICS.get(magic, "?"), ver, len(hdr), hdr["payload_origin"], hdr["payload_size"]))
                if ver > 1:
                    report("info", "layout-version-newer", n["node_id"])
                print("    header:", json.dumps(hdr, sort_keys=True))
                for sn, (sd, _) in secs.items():
                    print("    section %-9s dtype %-6s shape %-8s stride %3d offset %4d size %4d"
                          % (sn, sd["dtype"], sd["shape"], sd["stride"], sd["offset"], sd["size"]))
                # header vs manifest agreement (ENVELOPE §3 optional keys) -- only
                # meaningful when the envelope IS this node's payload
                is_payload = hdr.get("kind") == n["type"]
                if not is_payload:
                    print("    (file of node type %s, not its payload: decoded for reference only)" % n["type"])
                if not is_payload:
                    pass
                elif "input_hash" in v and "input_hash" not in hdr:
                    report("warn", "envelope-input-hash-absent", n["node_id"],
                           "manifest declares input_hash; envelope header carries none (ENVELOPE §3: mandatory for derived nodes)")
                elif "input_hash" in hdr and hdr["input_hash"] != v.get("input_hash"):
                    report("warn", "envelope-input-hash-disagrees", n["node_id"])
                if is_payload and "producer" in hdr and hdr["producer"].get("tool") != v.get("producer", {}).get("tool"):
                    report("warn", "envelope-producer-disagrees", n["node_id"],
                           "header %r vs manifest %r" % (hdr["producer"], v.get("producer")))
                if is_payload and hdr.get("epistemic") and hdr["epistemic"] != v.get("epistemic"):
                    report("warn", "envelope-epistemic-disagrees", n["node_id"])
                if magic == b"WKRP":
                    poses, contacts, checks = decode_restposes(hdr, secs)
                    print("    KIND: settled rest poses. ENTRIES: %d poses, %d contact points, from %d drop trials"
                          % (len(poses), len(contacts), hdr["trials"]))
                    for i, p in enumerate(poses):
                        q = p["quat_wxyz"]
                        print("    pose %d: quat(w,x,y,z)=(%.7f, %.7f, %.7f, %.7f)  contacts[%d..%d)  p=%.6f  support_area=%.6f m^2"
                              % (i, *q, p["contact_first"], p["contact_first"] + p["contact_count"],
                                 p["probability"], p["support_area_m2"]))
                        for c in range(p["contact_first"], p["contact_first"] + p["contact_count"]):
                            print("        contact %d: (%.6f, %.6f, %.6f) m, model space" % (c, *contacts[c]))
                    for name, ok in checks:
                        print("    invariant %-45s %s" % (name, "ok" if ok else "FAILED"))
                        if not ok:
                            report("error", "envelope-invalid", n["node_id"], name)
                # is this payload byte-identical to anything else in the package?
                twins = [p for p, bb in files.items() if bb == bytes(b) and p != f["path"]]
                if twins and is_payload:
                    report("warn", "payload-identical-to-other-file", n["node_id"],
                           "%s is byte-identical to %s" % (f["path"], ", ".join(twins)))
            except (EnvelopeError, struct.error, IndexError, KeyError, UnicodeDecodeError) as ex:
                report("error", "envelope-invalid", n["node_id"], str(ex))
                print("    DEAD:", ex)

    print("\n== report ==")
    for sev, code, subj, det in REPORT:
        print("  %-5s %-34s %-26s %s" % (sev, code, subj, det))
    errors = [r for r in REPORT if r[0] == "error"]
    print("\n  dead nodes:", sorted(dead) or "none")
    print("  exit status:", 1 if errors else 0)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
