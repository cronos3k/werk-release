#!/usr/bin/env python3
"""werk_inspect.py -- open a .werk package, list its contents with their
meanings, verify integrity, and extract point positions + colours.

Written from the spec/ carried INSIDE the package (MINI-SPECS.md sections
3, 5, 6, 11, 12; SPEC.md sections 1, 2, 6; spec/layouts/ENVELOPE, gsplat,
points). It never imports or executes anything from the package.
Stdlib only: struct, hashlib (sha256/sha512), json, zlib is NOT used.

    python -I werk_inspect.py PACKAGE.werk [--out DIR]
"""
import hashlib
import json
import math
import os
import struct
import sys

REPORT = []          # (severity, code, text)


def rep(sev, code, text):
    REPORT.append((sev, code, text))
    print("  [%s] %s: %s" % (sev, code, text))


# ---------------------------------------------------------------- zip (MINI-SPECS 5)
def crc32(data):
    # MINI-SPECS 6: reflected, poly 0xEDB88320, init/final xor 0xFFFFFFFF.
    # Table-driven version of the bitwise pseudocode (same function).
    tbl = crc32.tbl
    if tbl is None:
        tbl = []
        for i in range(256):
            c = i
            for _ in range(8):
                c = (c >> 1) ^ (0xEDB88320 if c & 1 else 0)
            tbl.append(c)
        crc32.tbl = tbl
    c = 0xFFFFFFFF
    for b in data:
        c = tbl[(c ^ b) & 0xFF] ^ (c >> 8)
    return c ^ 0xFFFFFFFF
crc32.tbl = None


def crc32_fast(data):
    # Same reflected CRC-32. Pure-python bytewise loop over 30 MB is slow, so
    # use binascii.crc32 -- the IEEE function -- after proving it equal to the
    # spec's own definition on the spec's test vector and on sample data.
    import binascii
    return binascii.crc32(data) & 0xFFFFFFFF


def read_zip(buf):
    n = len(buf)
    lo = max(0, n - 22 - 65535)
    eocd = -1
    for off in range(n - 22, lo - 1, -1):
        if buf[off:off + 4] == b"PK\x05\x06":
            clen = struct.unpack_from("<H", buf, off + 20)[0]
            if off + 22 + clen == n:
                eocd = off
                break
    if eocd < 0:
        raise SystemExit("no EOCD record found")
    (_, disk, cddisk, ndisk, ntot, cdsize, cdoff, clen) = struct.unpack_from(
        "<IHHHHIIH", buf, eocd)
    if ndisk == 0xFFFF or ntot == 0xFFFF or cdsize == 0xFFFFFFFF or cdoff == 0xFFFFFFFF \
            or (eocd >= 20 and buf[eocd - 20:eocd - 16] == b"PK\x06\x07"):
        raise SystemExit("zip64-unsupported: this reader is zip32-only")
    entries = []
    p = cdoff
    for _ in range(ntot):
        if buf[p:p + 4] != b"PK\x01\x02":
            raise SystemExit("bad central directory signature at %d" % p)
        (ver_made, ver_need, flags, method, mtime, mdate, crc, csize, usize,
         nlen, mlen, klen, dstart, iattr, eattr, lho) = struct.unpack_from(
            "<HHHHHHIIIHHHHHII", buf, p + 4)
        name = buf[p + 46:p + 46 + nlen].decode("utf-8")
        p += 46 + nlen + mlen + klen
        if buf[lho:lho + 4] != b"PK\x03\x04":
            raise SystemExit("bad local header for %s" % name)
        lflags, lmethod = struct.unpack_from("<HH", buf, lho + 6)
        lcrc, lcsize, lusize, ln, lm = struct.unpack_from("<IIIHH", buf, lho + 14)
        lname = buf[lho + 30:lho + 30 + ln].decode("utf-8")
        start = lho + 30 + ln + lm
        entries.append(dict(name=name, method=method, flags=flags, crc=crc,
                            csize=csize, usize=usize, lho=lho, start=start,
                            lname=lname, lmethod=lmethod, lcrc=lcrc,
                            lcsize=lcsize, lusize=lusize))
    if p != cdoff + cdsize:
        rep("warn", "zip-cd-size", "central directory size mismatch")
    return entries, cdoff, eocd


# ---------------------------------------------------------------- JSON (MINI-SPECS 3)
def no_dupes(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise ValueError("duplicate JSON key %r" % k)
        d[k] = v
    return d


def load_json(b, name):
    if b.startswith(b"\xef\xbb\xbf"):
        raise ValueError("%s has a BOM (MINI-SPECS 2 says reject)" % name)
    def bad_const(c):
        raise ValueError("%s contains %s" % (name, c))
    return json.loads(b.decode("utf-8"), object_pairs_hook=no_dupes,
                      parse_constant=bad_const)


def canon_json(v):
    """MINI-SPECS 3 'Canonical JSON (for hashing only)'."""
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if not math.isfinite(v):
            raise ValueError("non-finite number")
        if v.is_integer() and abs(v) < 2 ** 53:
            return str(int(v))   # rule 4: integers without a decimal point
        return repr(v)           # shortest round-trip form
    if isinstance(v, str):
        out = ['"']
        for ch in v:
            o = ord(ch)
            if ch == '"':
                out.append('\\"')
            elif ch == "\\":
                out.append("\\\\")
            elif o < 0x20:
                out.append({8: "\\b", 12: "\\f", 10: "\\n", 13: "\\r",
                            9: "\\t"}.get(o, "\\u%04x" % o))
            else:
                out.append(ch)
        out.append('"')
        return "".join(out)
    if isinstance(v, list):
        return "[" + ",".join(canon_json(x) for x in v) + "]"
    if isinstance(v, dict):
        ks = sorted(v.keys(), key=lambda k: k.encode("utf-8"))
        return "{" + ",".join(canon_json(k) + ":" + canon_json(v[k]) for k in ks) + "}"
    raise TypeError(type(v))


# ---------------------------------------------------------------- MessagePack (ENVELOPE 4)
class MP(object):
    def __init__(self, b):
        self.b = b
        self.p = 0

    def take(self, n):
        if self.p + n > len(self.b):
            raise ValueError("msgpack truncated")
        r = self.b[self.p:self.p + n]
        self.p += n
        return r

    def u(self, fmt, n):
        return struct.unpack(">" + fmt, self.take(n))[0]

    def val(self):
        t = self.take(1)[0]
        if t <= 0x7F:
            return t
        if t >= 0xE0:
            return t - 256
        if 0xA0 <= t <= 0xBF:
            return self.take(t & 0x1F).decode("utf-8")
        if 0x90 <= t <= 0x9F:
            return [self.val() for _ in range(t & 0x0F)]
        if 0x80 <= t <= 0x8F:
            return self.map(t & 0x0F)
        simple = {0xC0: None, 0xC2: False, 0xC3: True}
        if t in simple:
            return simple[t]
        ints = {0xCC: ("B", 1), 0xCD: ("H", 2), 0xCE: ("I", 4), 0xCF: ("Q", 8),
                0xD0: ("b", 1), 0xD1: ("h", 2), 0xD2: ("i", 4), 0xD3: ("q", 8),
                0xCA: ("f", 4), 0xCB: ("d", 8)}
        if t in ints:
            return self.u(*ints[t])
        if t in (0xD9, 0xDA, 0xDB):
            n = self.u(*{0xD9: ("B", 1), 0xDA: ("H", 2), 0xDB: ("I", 4)}[t])
            return self.take(n).decode("utf-8")
        if t in (0xC4, 0xC5, 0xC6):
            n = self.u(*{0xC4: ("B", 1), 0xC5: ("H", 2), 0xC6: ("I", 4)}[t])
            return bytes(self.take(n))
        if t in (0xDC, 0xDD):
            n = self.u(*{0xDC: ("H", 2), 0xDD: ("I", 4)}[t])
            return [self.val() for _ in range(n)]
        if t in (0xDE, 0xDF):
            n = self.u(*{0xDE: ("H", 2), 0xDF: ("I", 4)}[t])
            return self.map(n)
        raise ValueError("banned/unknown msgpack byte 0x%02x" % t)

    def map(self, n):
        d = {}
        for _ in range(n):
            k = self.val()
            if k in d:
                raise ValueError("duplicate msgpack key")
            d[k] = self.val()
        return d


DSZ = {"u8": 1, "i8": 1, "u16": 2, "i16": 2, "u32": 4, "i32": 4, "u64": 8,
       "i64": 8, "f32": 4, "f64": 8}
DFMT = {"u8": "B", "i8": "b", "u16": "H", "i16": "h", "u32": "I", "i32": "i",
        "u64": "Q", "i64": "q", "f32": "f", "f64": "d"}
MAGICS = {b"WKFF": "core.field.flow", b"WKRP": "core.pose.rest",
          b"WKAC": "core.anim.clip", b"WKSK": "core.skeleton",
          b"WKEM": "core.embedding", b"WKPC": "core.geom.points",
          b"WKGS": "core.geom.gsplat"}


def read_envelope(buf):
    """ENVELOPE.layout.txt section 7, plus section 5 ordering rules."""
    magic = bytes(buf[0:4])
    version, hlen = struct.unpack_from("<II", buf, 4)
    assert 12 + hlen <= len(buf), "header overruns file"
    mp = MP(bytes(buf[12:12 + hlen]))
    hdr = mp.val()
    assert mp.p == hlen, "header_len does not match msgpack length"
    assert hdr["endianness"] == "le", "endianness"
    assert MAGICS.get(magic) == hdr["kind"], "magic/kind mismatch"
    P = 16 * ((12 + hlen + 15) // 16)
    assert hdr["payload_origin"] == P, "payload_origin"
    assert P + hdr["payload_size"] == len(buf), "payload_size"
    assert all(b == 0 for b in buf[12 + hlen:P]), "nonzero header padding"
    prev_end = P
    secs = {}
    for i, s in enumerate(hdr["sections"]):
        assert s["offset"] % 16 == 0, "unaligned section %s" % s["name"]
        assert s["offset"] + s["size"] <= len(buf), "section overruns"
        if i == 0:
            assert s["offset"] == P, "section 0 not at payload_origin"
        else:
            assert prev_end <= s["offset"] <= prev_end + 15, "section gap/order"
            assert all(b == 0 for b in buf[prev_end:s["offset"]]), "gap not zero"
        esz = DSZ.get(s["dtype"]) or s["stride"]
        if s["stride"] == esz:
            assert s["size"] == s["stride"] * math.prod(s["shape"]), "size rule 1"
        else:
            assert s["stride"] >= esz * s["shape"][-1], "stride rule"
            assert s["size"] == s["stride"] * math.prod(s["shape"][:-1]), "size rule 2"
        prev_end = s["offset"] + s["size"]
        assert s["name"] not in secs, "duplicate section name"
        secs[s["name"]] = s
    assert 16 * ((prev_end + 15) // 16) == P + hdr["payload_size"], "trailing data"
    return magic, version, hdr, secs


def section_values(buf, s):
    """Flat tuple of scalars for a dense (stride == esz*components) section."""
    fmt = DFMT[s["dtype"]]
    count = s["size"] // DSZ[s["dtype"]]
    comps = 1 if s["stride"] == DSZ[s["dtype"]] else s["shape"][-1]
    assert s["stride"] == DSZ[s["dtype"]] * comps, "padded stride not handled"
    return struct.unpack_from("<%d%s" % (count, fmt), buf, s["offset"]), comps


# ---------------------------------------------------------------- Ed25519 (MINI-SPECS 12)
P25519 = 2 ** 255 - 19
L25519 = 2 ** 252 + 27742317777372353535851937790883648493
D25519 = (-121665 * pow(121666, P25519 - 2, P25519)) % P25519
I25519 = pow(2, (P25519 - 1) // 4, P25519)


def _inv(a):
    return pow(a, P25519 - 2, P25519)


def _recover_x(y, sign):
    if y >= P25519:
        return None
    u = (y * y - 1) % P25519
    v = (D25519 * y * y + 1) % P25519
    x = (u * pow(v, 3, P25519) * pow(u * pow(v, 7, P25519), (P25519 - 5) // 8, P25519)) % P25519
    vx2 = (v * x * x) % P25519
    if vx2 == (-u) % P25519:
        x = (x * I25519) % P25519
    vx2 = (v * x * x) % P25519
    if vx2 != u % P25519:
        return None
    if x == 0 and sign == 1:
        return None
    if (x & 1) != sign:
        x = P25519 - x
    return x


def _decompress(b):
    yv = int.from_bytes(b, "little")
    sign = yv >> 255
    y = yv & ((1 << 255) - 1)
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, (x * y) % P25519)


def _add(Pt, Q):
    X1, Y1, Z1, T1 = Pt
    X2, Y2, Z2, T2 = Q
    p = P25519
    A = (Y1 - X1) * (Y2 - X2) % p
    B = (Y1 + X1) * (Y2 + X2) % p
    C = T1 * 2 * D25519 * T2 % p
    D = Z1 * 2 * Z2 % p
    E, F, G, H = B - A, D - C, D + C, B + A
    return (E * F % p, G * H % p, F * G % p, E * H % p)


def _mul(s, Pt):
    Q = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            Q = _add(Q, Pt)
        Pt = _add(Pt, Pt)
        s >>= 1
    return Q


def _eq(Pt, Q):
    X1, Y1, Z1, _ = Pt
    X2, Y2, Z2, _ = Q
    p = P25519
    return (X1 * Z2 - X2 * Z1) % p == 0 and (Y1 * Z2 - Y2 * Z1) % p == 0


_By = 4 * _inv(5) % P25519
_B = (_recover_x(_By, 0), _By, 1, _recover_x(_By, 0) * _By % P25519)


def ed25519_verify(pub, msg, sig):
    if len(pub) != 32 or len(sig) != 64:
        return False
    S = int.from_bytes(sig[32:], "little")
    if S >= L25519:
        return False
    A = _decompress(pub)
    R = _decompress(sig[:32])
    if A is None or R is None:
        return False
    k = int.from_bytes(hashlib.sha512(sig[:32] + pub + msg).digest(), "little") % L25519
    lhs = _mul(S, _B)
    rhs = _add(R, _mul(k, A))
    if _eq(lhs, rhs):
        return True
    return _eq(_mul(8, lhs), _mul(8, rhs))   # cofactored form, also accepted


def self_tests():
    ok = True
    t = crc32(b"123456789") == 0xCBF43926 and crc32_fast(b"123456789") == 0xCBF43926
    print("  crc32 test vector 0xCBF43926 (spec impl + fast impl): %s" % t)
    ok &= t
    t = hashlib.sha512(b"abc").hexdigest().startswith("ddaf35a193617aba")
    print("  sha512('abc') matches MINI-SPECS 11.1 vector: %s" % t)
    ok &= t
    t = ed25519_verify(
        bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"),
        b"",
        bytes.fromhex("e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"))
    t2 = not ed25519_verify(
        bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"),
        b"x",
        bytes.fromhex("e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"))
    print("  ed25519 RFC 8032 vector 1 verifies: %s; wrong message rejected: %s" % (t, t2))
    ok &= t and t2
    return ok


def sig_message(e):
    return "\n".join(["werk-sig/1", e["manifest_sha256"], e["prev_entry_sha256"],
                      e["signed_at"], e["signer"]["uri"], e["signer"]["kind"]]).encode("utf-8")


def verify_chain(sigdoc, manifest_bytes, label):
    chain = sigdoc.get("chain") or []
    if not chain:
        return "absent"
    prev = "0" * 64
    for i, e in enumerate(chain):
        if e["prev_entry_sha256"] != prev:
            rep("error", "sig-prev", "%s entry %d prev_entry_sha256 mismatch" % (label, i))
            return "present-and-invalid"
        msg = sig_message(e)
        if not ed25519_verify(bytes.fromhex(e["public_key"]), msg, bytes.fromhex(e["signature"])):
            rep("error", "sig-bad", "%s entry %d signature does not verify" % (label, i))
            return "present-and-invalid"
        print("  %s entry %d: message %d bytes sha256 %s -> Ed25519 OK"
              % (label, i, len(msg), hashlib.sha256(msg).hexdigest()[:16]))
        prev = hashlib.sha256(e["signature"].encode("utf-8")).hexdigest()
    actual = hashlib.sha256(manifest_bytes).hexdigest()
    if chain[-1]["manifest_sha256"] != actual or sigdoc.get("manifest_sha256") != actual:
        rep("error", "sig-anchor", "%s: last entry / top-level manifest_sha256 != sha256(MANIFEST)" % label)
        return "present-and-invalid"
    return "signed-and-valid"


# ---------------------------------------------------------------- main
def main(argv):
    path = argv[1]
    outdir = argv[argv.index("--out") + 1] if "--out" in argv else None
    with open(path, "rb") as fh:
        buf = fh.read()
    print("== werk_inspect: %s (%d bytes, sha256 %s)" % (path, len(buf), hashlib.sha256(buf).hexdigest()))

    print("\n== self-tests (spec test vectors)")
    if not self_tests():
        raise SystemExit("self-tests failed; refusing to report verdicts")

    print("\n== container (MINI-SPECS 5)")
    entries, cdoff, eocd = read_zip(buf)
    print("  %d entries, central directory at %d, EOCD at %d" % (len(entries), cdoff, eocd))
    data = {}
    zip_ok = True
    for e in entries:
        n = e["name"]
        if e["method"] != 0:
            rep("error", "zip-method", "%s uses method %d; this reader is store-only" % (n, e["method"]))
            zip_ok = False
            continue
        if e["flags"] & 0x08:
            rep("warn", "zip-flag3", "%s has a data descriptor flag" % n)
        if n != e["lname"] or e["lmethod"] != 0 or e["lcrc"] != e["crc"] or e["lcsize"] != e["csize"]:
            rep("warn", "zip-local-mismatch", "%s local header disagrees with CD" % n)
        if n.startswith("/") or ".." in n.split("/") or ":" in n or "\\" in n:
            rep("error", "zip-name", "unsafe entry name %r" % n)
            zip_ok = False
            continue
        if e["csize"] != e["usize"]:
            rep("error", "zip-size", "%s stored but csize != usize" % n)
        b = buf[e["start"]:e["start"] + e["csize"]]
        if crc32_fast(b) != e["crc"]:
            rep("error", "zip-crc", "%s CRC-32 mismatch" % n)
            zip_ok = False
        if n.endswith("/"):
            continue
        data[n] = b
    print("  CRC-32 of every entry checked: %s" % ("all OK" if zip_ok else "FAILURES"))

    print("\n== MANIFEST.json")
    mbytes = data["MANIFEST.json"]
    man = load_json(mbytes, "MANIFEST.json")
    print("  werk %d.%d profile %s, entity %r (%s)" % (man["werk"]["major"], man["werk"]["minor"],
          man["profile"], man["entity"]["name"], man["entity"]["uuid"]))
    print("  summary: %s" % man["entity"]["summary"])
    want_conv = {"endianness": "le", "length_unit": "metre", "quat_order": "wxyz",
                 "hash_algorithm": "sha256", "signature_algorithm": "ed25519",
                 "up_axis": "y", "forward_axis": "-z", "handedness": "right"}
    for k, v in want_conv.items():
        if man["conventions"].get(k) != v:
            rep("error", "convention", "%s = %r, reader supports %r" % (k, man["conventions"].get(k), v))
    print("  conventions checked against what this reader supports: %s" %
          ("OK" if all(man["conventions"].get(k) == v for k, v in want_conv.items()) else "MISMATCH"))

    # ---- listing with meanings
    owner = {}
    for node in man["nodes"]:
        act = [v for v in node["versions"] if v["v"] == node["active"]]
        if len(act) != 1:
            rep("error", "active", "node %s has no unique active version" % node["node_id"])
        for ver in node["versions"]:
            for f in ver["files"]:
                prev = owner.get(f["path"])
                if prev and prev[0]["node_id"] != node["node_id"]:
                    rep("error", "file-two-nodes", "%s claimed by %s and %s" % (f["path"], prev[0]["node_id"], node["node_id"]))
                owner[f["path"]] = (node, ver, f)

    print("\n== contents (zip order), with meaning from the manifest node that owns each file")
    print("  %-46s %10s  %-22s %s" % ("path", "bytes", "node (type)", "meaning"))
    special = {"MANIFEST.json": "the package graph: hashes, conventions, nodes (not itself listed, SPEC 2)",
               "SIGNATURE.json": "Ed25519 signature chain over MANIFEST.json bytes (SPEC 6)"}
    for e in entries:
        n = e["name"]
        if n in special:
            print("  %-46s %10d  %-22s %s" % (n, e["usize"], "-", special[n]))
            continue
        if n not in owner:
            rep("error", "floating-file", "%s is in the zip but in no node's files[]" % n)
            continue
        node, ver, f = owner[n]
        meaning = describe(n, node, ver)
        print("  %-46s %10d  %-22s %s" % (n, e["usize"], "%s (%s)" % (node["node_id"], node["type"]), meaning))

    # ---- file hashes and sizes
    print("\n== integrity: files[] sha256 + size")
    bad = 0
    for p, (node, ver, f) in sorted(owner.items()):
        if p not in data:
            rep("error", "missing-file", "%s declared by %s but absent" % (p, node["node_id"]))
            bad += 1
            continue
        h = hashlib.sha256(data[p]).hexdigest()
        if h != f["sha256"] or len(data[p]) != f["size"]:
            rep("error", "hash-mismatch", "%s: sha256/size disagree with manifest" % p)
            bad += 1
    print("  %d declared files, %d mismatches" % (len(owner), bad))
    lic = man["license"]
    print("  license.sha256 (%s): %s" % (lic["file"], hashlib.sha256(data[lic["file"]]).hexdigest() == lic["sha256"]))
    tot = sum(f["size"] for (_, _, f) in owner.values())
    print("  total payload bytes (distinct declared paths): %d" % tot)

    # ---- spec_sha256 (SPEC 2)
    specfiles = sorted([p for p in owner if p.startswith("spec/")], key=lambda s: s.encode("utf-8"))
    acc = b""
    for p in specfiles:
        acc += p.encode("utf-8") + b"\n" + bytes.fromhex(owner[p][2]["sha256"]) + b"\n"
    ss = hashlib.sha256(acc).hexdigest()
    print("  spec_sha256 over %d spec/ files: %s -> %s" % (len(specfiles), ss,
          "MATCH" if ss == man["spec_sha256"] else "MISMATCH (declared %s)" % man["spec_sha256"]))

    # ---- input_hash (MINI-SPECS 11)
    print("\n== integrity: input_hash of derived nodes")
    for node in man["nodes"]:
        for ver in node["versions"]:
            if "input_hash" not in ver:
                continue
            h = hashlib.sha256()
            for ip in ver.get("input_files", []):
                h.update(bytes.fromhex(owner[ip][2]["sha256"]))
            h.update(canon_json(ver.get("input_params", {})).encode("utf-8"))
            got = h.hexdigest()
            print("  %-12s v%d inputs %s -> %s" % (node["node_id"], ver["v"], ver.get("input_files"),
                  "MATCH" if got == ver["input_hash"] else "MISMATCH (got %s)" % got))
            if got != ver["input_hash"]:
                rep("error", "input-hash", node["node_id"])

    # ---- signatures
    print("\n== signature chain (SPEC 6, MINI-SPECS 12.1)")
    sigdoc = load_json(data["SIGNATURE.json"], "SIGNATURE.json") if "SIGNATURE.json" in data else {}
    verdict = verify_chain(sigdoc, mbytes, "SIGNATURE.json") if sigdoc else "absent"
    print("  verdict: %s" % verdict)
    if sigdoc:
        print("  signer: %s (%s) key %s" % (sigdoc["chain"][-1]["signer"]["name"],
              sigdoc["chain"][-1]["signer"]["uri"], sigdoc["chain"][-1]["public_key"]))
        print("  NOTE: the chain has no external root of trust (SPEC 6); this key is a"
              " self-described public DEV key, so 'valid' proves only internal consistency.")
    # The worked example in spec/examples, as a construction check
    if "spec/examples/SIGNATURE.example.json" in data:
        ex = load_json(data["spec/examples/SIGNATURE.example.json"], "example")
        v2 = verify_chain(ex, data["spec/examples/MANIFEST.example.json"], "example")
        print("  spec/examples signature example: %s" % v2)

    # ---- envelopes
    print("\n== binary envelopes")
    env = {}
    for p in sorted(data):
        b = data[p]
        if b[:2] == b"WK" and b[:4] in MAGICS:
            try:
                magic, version, hdr, secs = read_envelope(b)
            except (AssertionError, ValueError, KeyError) as ex:
                rep("error", "envelope-dead", "%s: %s" % (p, ex))
                continue
            env[p] = (magic, version, hdr, secs)
            node = owner[p][0] if p in owner else None
            print("  %s: magic %s v%d kind %s count %s, sections: %s" % (
                p, magic.decode(), version, hdr["kind"], hdr.get("count"),
                ", ".join("%s[%s %s @%d +%d]" % (s["name"], s["dtype"], s["shape"], s["offset"], s["size"])
                          for s in hdr["sections"])))
            if node and "input_hash" in hdr and "input_hash" in owner[p][1] and hdr["input_hash"] != owner[p][1]["input_hash"]:
                rep("error", "env-input-hash", p)
    return man, owner, data, env, outdir, verdict


def describe(path, node, ver):
    t = node["type"]
    base = {
        "core.spec": "format specification travelling with the file",
        "core.loader": "bundled reader source (%s) -- NOT run" % node.get("meta", {}).get("language", "?"),
        "core.license": "full licence text",
        "core.readme": "human README",
        "core.tool": "SOURCE of embedded tool '%s' (%s) -- text, never executed" % (
            node.get("meta", {}).get("tool_id"), node.get("meta", {}).get("role")),
        "core.tool.config": "recorded run settings for %s" % node.get("meta", {}).get("tool_node"),
        "core.geom.gsplat": "3D Gaussian splat payload, magic WKGS",
        "core.geom.points": "point cloud (position+colour), magic WKPC",
        "core.recipe": "reproduction record",
        "core.semantics": "facet tags + palette",
        "core.provenance": "source / build provenance",
    }.get(t, t)
    if t == "core.spec":
        sub = path.split("/")
        if "schemas" in sub:
            base = "JSON Schema"
        elif "layouts" in sub:
            base = "binary layout grammar"
        elif "examples" in sub:
            base = "worked example"
    if t == "core.recipe" and path.endswith(".splat"):
        base = "ORIGINAL input .splat the chain started from (data)"
    if t == "core.tool" and path.endswith("tool.json"):
        base = "tool descriptor for '%s'" % node.get("meta", {}).get("tool_id")
    return base


def extract_points(man, owner, data, env, outdir):
    print("\n== task 2: positions and colours")
    C0 = 0.28209479177387814
    # SPEC 2 / 2.1: primary.geometry names a NODE; resolve active version, then
    # its payload file (payload_file, else the single file). Never "first WKGS
    # in the zip" -- spec/examples/ carries a 3-Gaussian example WKGS too.
    nodes = {nd["node_id"]: nd for nd in man["nodes"]}

    def payload_of(node_id):
        nd = nodes[node_id]
        ver = [v for v in nd["versions"] if v["v"] == nd["active"]][0]
        if "payload_file" in ver:
            return ver["payload_file"]
        assert len(ver["files"]) == 1, "payload-file-ambiguous for %s" % node_id
        return ver["files"][0]["path"]

    gs_node = man["primary"]["geometry"]
    gs_path = payload_of(gs_node)
    print("  primary.geometry -> node %r -> %s" % (gs_node, gs_path))
    magic, version, hdr, secs = env[gs_path]
    b = data[gs_path]
    n = hdr["count"]
    # gsplat.layout.txt section 8 checks 1-4
    assert hdr["sh_coeff_count"] == (hdr["sh_degree"] + 1) ** 2 and 0 <= hdr["sh_degree"] <= 3
    assert [s["name"] for s in hdr["sections"]] == ["means", "scales", "rotations", "opacities", "sh-dc", "sh-rest"]
    for s in hdr["sections"]:
        assert s["shape"][0] == n
    assert (hdr["quat_order"], hdr["scale_space"], hdr["opacity_space"], hdr["length_unit"]) == \
        ("wxyz", "linear", "linear", "metre")
    print("  %s: %d Gaussians, sh_degree %d; reading ONLY 'means' and 'sh-dc' (layout section 7);"
          " skipping scales, rotations, opacities, sh-rest" % (gs_path, n, hdr["sh_degree"]))
    means, _ = section_values(b, secs["means"])
    dc, _ = section_values(b, secs["sh-dc"])
    assert all(math.isfinite(x) for x in means) and all(math.isfinite(x) for x in dc), "NaN/inf"
    rgb = [min(1.0, max(0.0, 0.5 + C0 * x)) for x in dc]

    # WKPC: independent materialised copy
    pc_nodes = [nd["node_id"] for nd in man["nodes"] if nd["type"] == "core.geom.points"
                and any(e["to"] == gs_node for e in nd["edges"])]
    pc_path = payload_of(pc_nodes[0])
    print("  node %r (core.geom.points, edge -> %s) -> %s" % (pc_nodes[0], gs_node, pc_path))
    _, _, ph, psecs = env[pc_path]
    pb = data[pc_path]
    fields = ph["fields"]
    assert fields[0]["semantic"] == "position" and fields[0]["components"] == 3
    assert len(fields) == len(ph["sections"])
    pos_f = fields[0]
    col_f = [f for f in fields if f["semantic"] == "color"][0]
    print("  %s: %d points, fields %s; colour dtype %s x%d color_space %s" % (
        pc_path, ph["count"], [f["name"] for f in fields], col_f["dtype"], col_f["components"], col_f.get("color_space")))
    ppos, _ = section_values(pb, psecs[pos_f["section"]])
    pcol, _ = section_values(pb, psecs[col_f["section"]])

    # cross-checks
    same_pos = ppos == means
    # recompute u8: rint (round-half-even, as the tool's recorded formula says) of rgb*255
    u8 = [min(255, max(0, round(x * 255.0))) for x in rgb]   # Python round() is half-even
    same_col = list(pcol) == u8
    print("  WKPC positions == WKGS means bit-for-bit: %s" % same_pos)
    print("  WKPC colours == recomputed round_half_even(255*clamp(0.5+C0*dc,0,1)): %s" % same_col)

    # independent check against the ORIGINAL input .splat (32-byte records, layout quoted
    # in tools/splat-to-ply/splat_to_ply.py's docstring -- read as data, not run)
    sp = [p for p in data if p.endswith(".splat")]
    if sp:
        sb = data[sp[0]]
        ns = len(sb) // 32
        pos_ok = True
        col_ok = True
        for i in range(ns):
            r = sb[i * 32:(i + 1) * 32]
            x, y, z = struct.unpack_from("<3f", r, 0)
            if (x, y, z) != means[3 * i:3 * i + 3]:
                pos_ok = False
            if tuple(r[24:27]) != tuple(pcol[3 * i:3 * i + 3]):
                col_ok = False
        print("  original %s: %d records; positions == WKGS means: %s; rgb bytes == WKPC colours: %s"
              % (sp[0], ns, pos_ok, col_ok))

    xs, ys, zs = means[0::3], means[1::3], means[2::3]
    print("  POINT COUNT: %d" % n)
    print("  bounds min (%.6f, %.6f, %.6f) max (%.6f, %.6f, %.6f) metres" % (
        min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)))
    print("  header bounds hint: %s" % hdr.get("bounds"))
    print("  sample (index: x y z | linear rgb from sh-dc | WKPC u8):")
    for i in list(range(5)) + [n // 2, n - 1]:
        print("    %6d: %+.6f %+.6f %+.6f | %.6f %.6f %.6f | %3d %3d %3d" % (
            i, means[3 * i], means[3 * i + 1], means[3 * i + 2],
            rgb[3 * i], rgb[3 * i + 1], rgb[3 * i + 2], pcol[3 * i], pcol[3 * i + 1], pcol[3 * i + 2]))
    if outdir:
        os.makedirs(outdir, exist_ok=True)
        csvp = os.path.join(outdir, "points.csv")
        with open(csvp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("x,y,z,r_lin,g_lin,b_lin,r_u8,g_u8,b_u8\n")
            for i in range(n):
                fh.write("%.9g,%.9g,%.9g,%.6f,%.6f,%.6f,%d,%d,%d\n" % (
                    means[3 * i], means[3 * i + 1], means[3 * i + 2],
                    rgb[3 * i], rgb[3 * i + 1], rgb[3 * i + 2], pcol[3 * i], pcol[3 * i + 1], pcol[3 * i + 2]))
        print("  wrote %s" % csvp)
    return n


if __name__ == "__main__":
    man, owner, data, env, outdir, verdict = main(sys.argv)
    extract_points(man, owner, data, env, outdir)
    errs = [r for r in REPORT if r[0] == "error"]
    print("\n== summary: %d errors, %d other report entries; signature %s" % (
        len(errs), len(REPORT) - len(errs), verdict))
