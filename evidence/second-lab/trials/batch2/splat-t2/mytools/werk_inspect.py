#!/usr/bin/env python3
"""werk_inspect.py -- an independent reader for a .werk package.

Written from the package's own spec/ text (SPEC.md, MINI-SPECS.md,
layouts/ENVELOPE, gsplat, points). It does NOT import, run or port any code
carried inside the package. Standard library only.

    python -I werk_inspect.py PACKAGE.werk [--out DIR]

Does:
  1. open the zip (store-mode, zip64 detection per MINI-SPECS 5.5)
  2. list every entry with its meaning (node id, node type, note)
  3. verify integrity: zip CRC, size+sha256 per file, license.sha256,
     spec_sha256, input_hash per derived node, floating/missing/double-claimed
     files, Ed25519 signature chain (implemented here from MINI-SPECS 12),
     envelope structure of every WKGS/WKPC payload, recipe cross-references
  4. decode the splat's means + sh-dc (gsplat.layout.txt section 7) and the
     WKPC point cloud, check they agree exactly, write positions+colours out.
"""

import hashlib
import json
import math
import os
import struct
import sys
import zipfile
from array import array

REPORT = []          # (severity, code, subject, message)


def rep(sev, code, subject, msg):
    REPORT.append((sev, code, subject, msg))
    print("  [%s] %s %s: %s" % (sev, code, subject, msg))


def sha256(b):
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------- zip --------

def check_eocd(raw):
    """MINI-SPECS 5.1 / 5.5: find the EOCD ourselves and detect zip64."""
    size = len(raw)
    lo = max(0, size - 22 - 65535)
    for off in range(size - 22, lo - 1, -1):
        if raw[off:off + 4] == b"PK\x05\x06":
            break
    else:
        raise SystemExit("container: no EOCD")
    (_, disk, cd_disk, n_here, n_total, cd_size, cd_off, clen) = struct.unpack_from(
        "<IHHHHIIH", raw, off)
    zip64 = (n_here == 0xFFFF or n_total == 0xFFFF or cd_size == 0xFFFFFFFF
             or cd_off == 0xFFFFFFFF or raw[off - 20:off - 16] == b"PK\x06\x07")
    return {"eocd_offset": off, "entries": n_total, "cd_size": cd_size,
            "cd_offset": cd_off, "comment_len": clen, "zip64": zip64}


# ---------------------------------------------------------------- canonical JSON

def canon(v):
    """MINI-SPECS 3, 'Canonical JSON (for hashing only)'."""
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
    if isinstance(v, list):
        return "[" + ",".join(canon(x) for x in v) + "]"
    if isinstance(v, dict):
        keys = sorted(v.keys(), key=lambda k: k.encode("utf-8"))
        return "{" + ",".join(canon(k) + ":" + canon(v[k]) for k in keys) + "}"
    raise TypeError(type(v))


def no_dup_keys(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise ValueError("duplicate JSON key %r" % k)
        d[k] = v
    return d


def load_json(b, what):
    if b.startswith(b"\xef\xbb\xbf"):
        raise ValueError("%s has a UTF-8 BOM (MINI-SPECS 2 says reject)" % what)
    return json.loads(b.decode("utf-8"), object_pairs_hook=no_dup_keys)


# ---------------------------------------------------------------- Ed25519 ----
# MINI-SPECS 12, transcribed. Verify only; non-constant-time is acceptable
# for a verifier (all inputs public), as that section says.

P = 2 ** 255 - 19
L = 2 ** 252 + 27742317777372353535851937790883648493
D = (-121665 * pow(121666, P - 2, P)) % P
I = pow(2, (P - 1) // 4, P)


def _recover_x(y, sign):
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


_BY = (4 * pow(5, P - 2, P)) % P
_BX = _recover_x(_BY, 0)
B = (_BX, _BY, 1, (_BX * _BY) % P)
IDENT = (0, 1, 1, 0)


def _add(p1, p2):
    X1, Y1, Z1, T1 = p1
    X2, Y2, Z2, T2 = p2
    A = (Y1 - X1) * (Y2 - X2) % P
    Bv = (Y1 + X1) * (Y2 + X2) % P
    C = T1 * 2 * D * T2 % P
    Dd = Z1 * 2 * Z2 % P
    E, F, G, H = Bv - A, Dd - C, Dd + C, Bv + A
    return (E * F % P, G * H % P, F * G % P, E * H % P)


def _mul(s, pt):
    q = IDENT
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


def _decode(b):
    if len(b) != 32:
        return None
    n = int.from_bytes(b, "little")
    sign = n >> 255
    y = n & ((1 << 255) - 1)
    if y >= P:
        return None
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, (x * y) % P)


def ed25519_verify(pub, msg, sig):
    if len(sig) != 64:
        return False
    A = _decode(pub)
    R = _decode(sig[:32])
    if A is None or R is None:
        return False
    S = int.from_bytes(sig[32:], "little")
    if S >= L:
        return False
    k = int.from_bytes(hashlib.sha512(sig[:32] + pub + msg).digest(), "little") % L
    lhs = _mul(8, _mul(S, B))
    rhs = _mul(8, _add(R, _mul(k, A)))
    return _eq(lhs, rhs)


def sig_message(entry):
    """MINI-SPECS 12.1 / SPEC.md 6."""
    return "\n".join(["werk-sig/1", entry["manifest_sha256"],
                      entry["prev_entry_sha256"], entry["signed_at"],
                      entry["signer"]["uri"], entry["signer"]["kind"]]).encode("utf-8")


# ---------------------------------------------------------------- MessagePack (ENVELOPE 4)

class MP(object):
    def __init__(self, b):
        self.b, self.i = b, 0

    def take(self, n):
        if self.i + n > len(self.b):
            raise ValueError("msgpack truncated")
        r = self.b[self.i:self.i + n]
        self.i += n
        return r

    def u(self, n):
        return int.from_bytes(self.take(n), "big")

    def s(self, n):
        return int.from_bytes(self.take(n), "big", signed=True)

    def val(self):
        t = self.u(1)
        if t <= 0x7f:
            return t
        if t >= 0xe0:
            return t - 256
        if 0xa0 <= t <= 0xbf:
            return self.take(t & 0x1f).decode("utf-8")
        if 0x90 <= t <= 0x9f:
            return [self.val() for _ in range(t & 0x0f)]
        if 0x80 <= t <= 0x8f:
            return self.map(t & 0x0f)
        if t == 0xc0:
            return None
        if t == 0xc2:
            return False
        if t == 0xc3:
            return True
        if t in (0xcc, 0xcd, 0xce, 0xcf):
            return self.u({0xcc: 1, 0xcd: 2, 0xce: 4, 0xcf: 8}[t])
        if t in (0xd0, 0xd1, 0xd2, 0xd3):
            return self.s({0xd0: 1, 0xd1: 2, 0xd2: 4, 0xd3: 8}[t])
        if t == 0xca:
            return struct.unpack(">f", self.take(4))[0]
        if t == 0xcb:
            return struct.unpack(">d", self.take(8))[0]
        if t in (0xd9, 0xda, 0xdb):
            return self.take(self.u({0xd9: 1, 0xda: 2, 0xdb: 4}[t])).decode("utf-8")
        if t in (0xc4, 0xc5, 0xc6):
            return bytes(self.take(self.u({0xc4: 1, 0xc5: 2, 0xc6: 4}[t])))
        if t in (0xdc, 0xdd):
            return [self.val() for _ in range(self.u(2 if t == 0xdc else 4))]
        if t in (0xde, 0xdf):
            return self.map(self.u(2 if t == 0xde else 4))
        raise ValueError("banned/unknown msgpack byte 0x%02x" % t)

    def map(self, n):
        d = {}
        for _ in range(n):
            k = self.val()
            if k in d:
                raise ValueError("duplicate header key %r" % k)
            d[k] = self.val()
        return d


DTYPE = {"u8": (1, "B"), "i8": (1, "b"), "u16": (2, "H"), "i16": (2, "h"),
         "u32": (4, "I"), "i32": (4, "i"), "u64": (8, "Q"), "i64": (8, "q"),
         "f32": (4, "f"), "f64": (8, "d")}


def prod(xs):
    r = 1
    for x in xs:
        r *= x
    return r


def read_envelope(buf, subject):
    """ENVELOPE.layout.txt section 7, plus section 5's ordering/padding rules."""
    if len(buf) < 12:
        raise ValueError("shorter than 12 bytes")
    magic = bytes(buf[0:4]).decode("ascii")
    version = struct.unpack_from("<I", buf, 4)[0]
    hlen = struct.unpack_from("<I", buf, 8)[0]
    if 12 + hlen > len(buf):
        raise ValueError("header_len runs past end of file")
    mp = MP(bytes(buf[12:12 + hlen]))
    header = mp.val()
    if mp.i != hlen:
        raise ValueError("header map is %d bytes, header_len says %d" % (mp.i, hlen))
    if header.get("endianness") != "le":
        raise ValueError("endianness != le")
    Pexp = 16 * ((12 + hlen + 15) // 16)
    if header["payload_origin"] != Pexp:
        raise ValueError("payload_origin %r != computed %d" % (header["payload_origin"], Pexp))
    if any(buf[12 + hlen:Pexp]):
        rep("warn", "envelope-nonzero-padding", subject, "header padding is not zero")
    if Pexp + header["payload_size"] != len(buf):
        raise ValueError("payload_origin+payload_size != file size")
    prev_end = Pexp
    secs = {}
    for s in header["sections"]:
        if s["offset"] % 16:
            raise ValueError("section %s offset not 16-aligned" % s["name"])
        if s["offset"] + s["size"] > len(buf):
            raise ValueError("section %s overruns file" % s["name"])
        if s["offset"] < prev_end or s["offset"] - prev_end > 15:
            raise ValueError("section %s not in order / gap > 15" % s["name"])
        if any(buf[prev_end:s["offset"]]):
            rep("warn", "envelope-nonzero-padding", subject, "before %s" % s["name"])
        esz = DTYPE[s["dtype"]][0] if s["dtype"] != "record" else s["stride"]
        if s["stride"] == esz:
            ok = s["size"] == s["stride"] * prod(s["shape"])
        else:
            ok = (s["stride"] >= esz * s["shape"][-1]
                  and s["size"] == s["stride"] * prod(s["shape"][:-1]))
        if not ok:
            raise ValueError("section %s fails the consistency rule" % s["name"])
        if s["name"] in secs:
            raise ValueError("duplicate section name %s" % s["name"])
        secs[s["name"]] = s
        prev_end = s["offset"] + s["size"]
    if 16 * ((prev_end + 15) // 16) != Pexp + header["payload_size"]:
        raise ValueError("trailing data after last section")
    return magic, version, header, secs


def column(buf, s, ncomp):
    """Read a section as a flat array, honouring its declared stride."""
    esz, code = DTYPE[s["dtype"]]
    n = s["shape"][0]
    if s["stride"] == esz * ncomp:
        a = array(code)
        a.frombytes(bytes(buf[s["offset"]:s["offset"] + s["size"]]))
        if sys.byteorder != "little":
            a.byteswap()
        return a
    a = array(code)
    for i in range(n):
        o = s["offset"] + i * s["stride"]
        a.frombytes(bytes(buf[o:o + esz * ncomp]))
    if sys.byteorder != "little":
        a.byteswap()
    return a


def all_finite(a):
    return all(math.isfinite(x) for x in a)


# ---------------------------------------------------------------- main -------

SUPPORTED_CONVENTIONS = {
    # The values this reader implements. Taken from SPEC.md section 2's list
    # for profile 3d-entity/1 -- and this reader really implements them for
    # the two node types it decodes (le, metre, wxyz, ...).
    "endianness": "le", "units_per_meter": 1.0, "length_unit": "metre",
    "angle_unit": "radian", "time_unit": "second", "mass_unit": "kilogram",
    "up_axis": "y", "forward_axis": "-z", "right_axis": "+x",
    "handedness": "right", "winding": "ccw", "quat_order": "wxyz",
    "oct_encoding_pole": "y", "sh_l1_order": ["dc", "y", "z", "x"],
    "color_space_default": "srgb", "uv_origin": "top-left",
    "alignment_bytes": 16, "text_encoding": "utf-8", "id_case": "kebab-case",
    "hash_algorithm": "sha256", "signature_algorithm": "ed25519",
}

SPECIAL = {
    "MANIFEST.json": "the package graph: hashes, conventions, nodes (not itself listed in any files[])",
    "SIGNATURE.json": "Ed25519 signature chain over MANIFEST.json's bytes (not itself listed in any files[])",
}

C0 = 0.28209479177387814


def main(argv):
    path = argv[1]
    out = None
    if "--out" in argv:
        out = argv[argv.index("--out") + 1]
        os.makedirs(out, exist_ok=True)

    with open(path, "rb") as fh:
        raw = fh.read()
    print("== %s  (%d bytes, sha256 %s)" % (path, len(raw), sha256(raw)))

    # ---- 1. container
    print("\n== 1. container")
    eocd = check_eocd(raw)
    print("  EOCD at %(eocd_offset)d, %(entries)d entries, central dir %(cd_size)d bytes at %(cd_offset)d, zip64=%(zip64)s" % eocd)
    if eocd["zip64"]:
        rep("error", "zip64-unsupported", path, "zip64 container")
        return 2
    z = zipfile.ZipFile(path)
    infos = z.infolist()
    data = {}
    for zi in infos:
        n = zi.filename
        if n.startswith("/") or ".." in n.split("/") or ":" in n or "\\" in n:
            rep("error", "zip-bad-name", n, "unsafe entry name")
            continue
        if zi.compress_type not in (0, 8):
            rep("error", "zip-method-unsupported", n, "method %d" % zi.compress_type)
            continue
        if zi.compress_type != 0:
            rep("info", "zip-deflate", n, "entry is deflated (zipfile inflates it)")
        if zi.flag_bits & 0x8:
            rep("warn", "zip-data-descriptor", n, "flag bit 3 set (MINI-SPECS 5.4)")
        if n.endswith("/"):
            continue
        data[n] = z.read(zi)            # zipfile checks CRC-32 on read
    print("  %d file entries read, every zip CRC-32 checked by zipfile on read" % len(data))

    # ---- 2. manifest
    print("\n== 2. manifest")
    man_bytes = data["MANIFEST.json"]
    man = load_json(man_bytes, "MANIFEST.json")
    print("  werk %d.%d, profile %s, entity %r (%s)" % (
        man["werk"]["major"], man["werk"]["minor"], man["profile"],
        man["entity"]["name"], man["entity"]["uuid"]))
    if man["werk"]["major"] != 1:
        rep("error", "unsupported-major", "MANIFEST.json", str(man["werk"]["major"]))
    if man["profile"] != "3d-entity/1":
        rep("warn", "unsupported-profile", "MANIFEST.json", man["profile"])
    if man.get("manifest_schema", "spec/schemas/manifest.schema.json") not in data:
        rep("warn", "manifest-schema-missing", "MANIFEST.json", man.get("manifest_schema"))
    rep("info", "manifest-not-schema-validated", "MANIFEST.json",
        "structural checks only; this reader carries no JSON Schema validator")
    for k, want in SUPPORTED_CONVENTIONS.items():
        got = man["conventions"].get(k)
        if got != want:
            rep("error", "unsupported-convention", k, "%r (support %r)" % (got, want))
    print("  conventions: all %d checked against what this reader supports" % len(SUPPORTED_CONVENTIONS))

    # ---- 3. listing + per-file integrity
    print("\n== 3. contents (path -> node, type, meaning) and per-file integrity")
    owner = {}       # path -> node_id
    dead = set()
    for node in man["nodes"]:
        vs = {v["v"]: v for v in node["versions"]}
        act = vs.get(node["active"])
        if act is None:
            rep("error", "active-version-invalid", node["node_id"], str(node["active"]))
            continue
        node["_act"] = act
        for f in act["files"]:
            p = f["path"]
            if p in owner and owner[p] != node["node_id"]:
                rep("error", "file-claimed-twice", p, "%s and %s" % (owner[p], node["node_id"]))
            owner[p] = node["node_id"]
            b = data.get(p)
            if b is None:
                rep("error", "file-missing", p, "declared by %s" % node["node_id"])
                dead.add(node["node_id"])
                continue
            if len(b) != f["size"]:
                rep("error", "size-mismatch", p, "%d != %d" % (len(b), f["size"]))
                dead.add(node["node_id"])
            if sha256(b) != f["sha256"]:
                rep("error", "hash-mismatch", p, "")
                dead.add(node["node_id"])
    nodes = {n["node_id"]: n for n in man["nodes"]}
    listing = []
    for p in sorted(data, key=lambda s: [i.filename for i in infos].index(s)):
        if p in SPECIAL:
            listing.append((p, len(data[p]), "-", "-", SPECIAL[p]))
            continue
        nid = owner.get(p)
        if nid is None:
            rep("error", "file-floating", p, "in the zip but in no node's files[]")
            listing.append((p, len(data[p]), "?", "?", "FLOATING"))
            continue
        n = nodes[nid]
        listing.append((p, len(data[p]), nid, n["type"], n["_act"]["note"]))
    for p, size, nid, typ, note in listing:
        print("  %-46s %9d  %-32s %-18s %s" % (p, size, nid, typ, note[:90] + ("..." if len(note) > 90 else "")))
    nfiles = sum(len(n["_act"]["files"]) for n in man["nodes"] if "_act" in n)
    ok = [p for p in owner if p in data]
    print("  %d declared files, %d present; %d nodes dead from file checks" % (nfiles, len(ok), len(dead)))
    if not any(r[1] in ("hash-mismatch", "size-mismatch", "file-missing") for r in REPORT):
        print("  every declared file: size OK, sha256 OK")

    # licence
    lic = man["license"]
    if sha256(data[lic["file"]]) == lic["sha256"]:
        print("  license.sha256 OK (%s)" % lic["file"])
    else:
        rep("error", "hash-mismatch", "license", lic["file"])

    # spec_sha256 (SPEC.md section 2, S-29)
    spec_files = sorted({f["path"] for n in man["nodes"] if "_act" in n
                         for f in n["_act"]["files"] if f["path"].startswith("spec/")},
                        key=lambda s: s.encode("utf-8"))
    h = hashlib.sha256()
    for p in spec_files:
        h.update(p.encode("utf-8") + b"\n" + hashlib.sha256(data[p]).digest() + b"\n")
    if h.hexdigest() == man["spec_sha256"]:
        print("  spec_sha256 OK over %d spec/ files: %s" % (len(spec_files), man["spec_sha256"]))
    else:
        rep("error", "spec-sha256-mismatch", "MANIFEST.json", "%s != %s" % (h.hexdigest(), man["spec_sha256"]))

    # input_hash (MINI-SPECS 11)
    for n in man["nodes"]:
        v = n.get("_act")
        if not v or v.get("epistemic") not in ("measured", "inferred"):
            continue
        if "input_hash" not in v or "input_files" not in v:
            rep("error", "input-hash-missing", n["node_id"], "")
            continue
        h = hashlib.sha256()
        for p in v["input_files"]:
            h.update(hashlib.sha256(data[p]).digest())
        h.update(canon(v.get("input_params", {})).encode("utf-8"))
        if h.hexdigest() == v["input_hash"]:
            print("  input_hash OK: %s (from %s)" % (n["node_id"], ", ".join(v["input_files"])))
        else:
            rep("error", "input-hash-mismatch", n["node_id"], "%s != %s" % (h.hexdigest(), v["input_hash"]))

    # total_size_bytes, if declared
    if "total_size_bytes" in man["container"]:
        tot = sum(len(data[p]) for p in owner if p in data)
        print("  total_size_bytes declared %d, computed %d" % (man["container"]["total_size_bytes"], tot))

    # ---- 4. signature
    print("\n== 4. signature chain")
    state = "absent"
    if "SIGNATURE.json" in data:
        # self-test first: RFC 8032 vector 1 and the package's own worked example
        rfc_ok = ed25519_verify(
            bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"), b"",
            bytes.fromhex("e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"))
        neg_ok = not ed25519_verify(
            bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"), b"x",
            bytes.fromhex("e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"))
        ex_ok = None
        if "spec/examples/SIGNATURE.example.json" in data:
            exs = load_json(data["spec/examples/SIGNATURE.example.json"], "example sig")
            e0 = exs["chain"][0]
            m = sig_message(e0)
            ex_ok = (sha256(data["spec/examples/MANIFEST.example.json"]) == e0["manifest_sha256"]
                     and len(m) == 203 and sha256(m) == "11e260cc16bc454f39f1aa6d56679c868ba1e83d33e3c22a462040b32a92165a"
                     and ed25519_verify(bytes.fromhex(e0["public_key"]), m, bytes.fromhex(e0["signature"])))
        print("  verifier self-test: RFC 8032 vector 1 %s, tampered-message rejected %s, package example %s"
              % (rfc_ok, neg_ok, ex_ok))
        if not (rfc_ok and neg_ok and ex_ok is not False):
            state = "unverified"
            rep("warn", "signature-unverified", "SIGNATURE.json", "own verifier failed self-test")
        else:
            sig = load_json(data["SIGNATURE.json"], "SIGNATURE.json")
            good = sig.get("algorithm") == "ed25519"
            prev = "0" * 64
            for e in sig["chain"]:
                m = sig_message(e)
                link = (e["prev_entry_sha256"] == prev and
                        ed25519_verify(bytes.fromhex(e["public_key"]), m, bytes.fromhex(e["signature"])))
                print("  entry %d by %s (%s): message %d bytes sha256 %s -> %s"
                      % (e["index"], e["signer"]["uri"], e["signer"]["kind"], len(m), sha256(m),
                         "valid" if link else "INVALID"))
                good = good and link
                prev = sha256(e["signature"].encode("utf-8"))
            mh = sha256(man_bytes)
            anchor = sig["chain"][-1]["manifest_sha256"] == mh and sig.get("manifest_sha256") == mh
            print("  last entry anchors MANIFEST.json bytes (sha256 %s): %s" % (mh, anchor))
            state = "signed-and-valid" if (good and anchor) else "present-and-invalid"
            if state == "present-and-invalid":
                rep("error", "signature-invalid", "SIGNATURE.json", "")
            for e in sig["chain"]:
                if "note" in e:
                    print("  signer note: %s" % e["note"])
    print("  SIGNATURE STATE: %s" % state)

    # ---- 5. recipe / tool cross references
    print("\n== 5. recipe and tool cross-references")
    rec = load_json(data["recipe/recipe.json"], "recipe")
    for st in rec["steps"]:
        t = st["tool"]
        tn = nodes.get(t.get("tool_node"))
        tj = load_json(data[[f["path"] for f in tn["_act"]["files"] if f["path"].endswith("tool.json")][0]], "tool.json")
        agree = tj["entrypoint"] == t.get("source_file")
        cfg = nodes.get(t.get("config_node"))
        print("  step %-20s tool_node %-22s entrypoint==source_file %s, config_node %s present %s"
              % (st["step_id"], t["tool_node"], agree, t.get("config_node"), cfg is not None))
        if not agree:
            rep("warn", "recipe-tool-disagree", st["step_id"], "")
        for tf in tj["files"]:
            mf = [f for f in tn["_act"]["files"] if f["path"] == tf["path"]]
            if not mf or mf[0]["sha256"] != tf["sha256"]:
                rep("warn", "tool-json-file-disagree", tf["path"], "")
        for io in st.get("inputs", []) + st.get("outputs", []):
            if io["path"] not in data or sha256(data[io["path"]]) != io["sha256"]:
                rep("error", "recipe-io-mismatch", io["path"], "")
            else:
                print("      %s sha256 matches the recipe" % io["path"])
        for im in st.get("intermediates", []):
            print("      intermediate %s NOT carried (sha256 %s, %d bytes) - reproducible only by running %s; NOT checked here"
                  % (im["name"], im["sha256"], im["size"], im["reproduced_by"]))
            rep("info", "intermediate-not-verified", im["name"], "would require executing an embedded tool")

    # ---- 6. payloads
    print("\n== 6. payloads")
    gs_node = nodes[man["primary"]["geometry"]]
    gs_path = gs_node["_act"]["files"][0]["path"]
    gbuf = memoryview(data[gs_path])
    magic, ver, gh, gsec = read_envelope(gbuf, gs_path)
    print("  %s: magic %s v%d kind %s count %d sh_degree %d K %d" % (
        gs_path, magic, ver, gh["kind"], gh["count"], gh["sh_degree"], gh["sh_coeff_count"]))
    assert magic == "WKGS" and gh["kind"] == "core.geom.gsplat"
    N = gh["count"]
    # gsplat.layout.txt section 8, checks 1-4
    assert gh["sh_coeff_count"] == (gh["sh_degree"] + 1) ** 2 and 0 <= gh["sh_degree"] <= 3
    assert list(gsec) == ["means", "scales", "rotations", "opacities", "sh-dc", "sh-rest"], list(gsec)
    for s in gsec.values():
        assert s["shape"][0] == N, s
    assert gsec["sh-rest"]["shape"][1] == gh["sh_coeff_count"] - 1
    assert (gh["quat_order"], gh["scale_space"], gh["opacity_space"], gh["length_unit"]) == \
        ("wxyz", "linear", "linear", "metre")
    if gh.get("input_hash") and gh["input_hash"] != gs_node["_act"].get("input_hash"):
        rep("error", "envelope-input-hash-disagree", gs_path, "")
    for k in ("count", "sh_degree", "sh_coeff_count", "sh_coeff_order", "quat_order",
              "scale_space", "opacity_space", "length_unit", "source_convention", "activation",
              "bounds", "opacity_note", "producer", "epistemic", "input_hash", "note"):
        if k in gh:
            print("    header %-17s %s" % (k, json.dumps(gh[k])[:150]))
    print("    sections:")
    for s in gsec.values():
        print("      %-10s offset %9d size %9d dtype %s shape %s stride %d" % (
            s["name"], s["offset"], s["size"], s["dtype"], s["shape"], s["stride"]))
    # the normative point-cloud path reads ONLY means and sh-dc; the other
    # four are read here as well purely for the SHOULD checks 5-8.
    means = column(gbuf, gsec["means"], 3)
    dc = column(gbuf, gsec["sh-dc"], 3)
    scales = column(gbuf, gsec["scales"], 3)
    rots = column(gbuf, gsec["rotations"], 4)
    opac = column(gbuf, gsec["opacities"], 1)
    for nm, a in (("means", means), ("sh-dc", dc), ("scales", scales),
                  ("rotations", rots), ("opacities", opac)):
        if not all_finite(a):
            rep("error", "non-finite", gs_path, nm)
    bad_scale = next((i // 3 for i, v in enumerate(scales) if not v > 0), None)
    bad_op = next((i for i, v in enumerate(opac) if not 0.0 <= v <= 1.0), None)
    qdev, bad_q = 0.0, None
    for i in range(N):
        w, x, y, zz = rots[4 * i:4 * i + 4]
        d = abs(math.sqrt(w * w + x * x + y * y + zz * zz) - 1.0)
        qdev = max(qdev, d)
        if (d > 1e-6 or w < 0) and bad_q is None:
            bad_q = i
    print("    checks: scales>0 first-bad=%s, opacity in [0,1] first-bad=%s, max | |q|-1 | = %.3g, first q off/neg-w=%s"
          % (bad_scale, bad_op, qdev, bad_q))
    if bad_q is not None:
        rep("warn", "quat-not-unit", gs_path, "first index %d" % bad_q)
    mins = [min(means[j::3]) for j in range(3)]
    maxs = [max(means[j::3]) for j in range(3)]
    print("    computed bounds min %s max %s" % (mins, maxs))
    if "bounds" in gh:
        same = all(abs(a - b) == 0 for a, b in zip(mins + maxs, gh["bounds"]["min"] + gh["bounds"]["max"]))
        print("    header bounds hint equals computed bounds exactly: %s" % same)

    # derived colours, gsplat.layout.txt section 5/7
    rgb = [min(1.0, max(0.0, 0.5 + C0 * v)) for v in dc]

    # WKPC
    pc_node = nodes["points-dc"]
    pc_path = pc_node["_act"]["files"][0]["path"]
    pbuf = memoryview(data[pc_path])
    magic, ver, ph, psec = read_envelope(pbuf, pc_path)
    print("  %s: magic %s v%d kind %s count %d" % (pc_path, magic, ver, ph["kind"], ph["count"]))
    assert magic == "WKPC" and ph["kind"] == "core.geom.points"
    flds = ph["fields"]
    # points.layout.txt section 6
    assert len(flds) == len(psec) and [f["section"] for f in flds] == list(psec)
    assert flds[0]["semantic"] == "position" and flds[0]["dtype"] in ("f32", "f64") and flds[0]["components"] == 3
    assert sum(f["semantic"] == "position" for f in flds) == 1
    for f in flds:
        s = psec[f["section"]]
        assert s["dtype"] == f["dtype"]
        assert s["shape"] == ([ph["count"]] if f["components"] == 1 else [ph["count"], f["components"]])
        print("    field %-9s semantic %-9s dtype %s x%d %s section@%d size %d" % (
            f["name"], f["semantic"], f["dtype"], f["components"],
            ("color_space=" + f["color_space"]) if "color_space" in f else ("unit=" + f.get("unit", "-")),
            s["offset"], s["size"]))
        if f["semantic"] == "color" and "color_space" not in f:
            rep("warn", "color-space-missing", pc_path, f["name"])
    for k in ("source", "bounds", "producer", "epistemic", "input_hash", "length_unit"):
        if k in ph:
            print("    header %-12s %s" % (k, json.dumps(ph[k])[:150]))
    pfield = flds[0]
    cfield = next(f for f in flds if f["semantic"] == "color")
    ppos = column(pbuf, psec[pfield["section"]], 3)
    pcol = column(pbuf, psec[cfield["section"]], cfield["components"])
    if not all_finite(ppos):
        rep("error", "non-finite", pc_path, "position")

    # compare: positions exact, colours = quantised DC band
    pos_equal = (ph["count"] == N and ppos.tobytes() == means.tobytes())
    # Quantisation: points.layout.txt says only "u8 is 0..255 mapping to 0..1".
    # The rounding rule (round-half-even of v*255, then clip) is NOT in spec/;
    # it is read from tools/werk-pointcloud/p_pointcloud.py from_gsplat().
    q = bytes(min(255, max(0, round(v * 255.0))) for v in rgb)
    col_equal = cfield["components"] == 3 and q == pcol.tobytes()
    maxdiff = max(abs(a - b) for a, b in zip(q, pcol.tobytes())) if cfield["components"] == 3 else None
    print("    positions == WKGS means, byte for byte: %s" % pos_equal)
    print("    colours  == round(255*clamp(0.5+C0*sh_dc,0,1)) of the WKGS, byte for byte: %s (max |diff| %s)"
          % (col_equal, maxdiff))
    if not pos_equal:
        rep("error", "points-disagree-with-splat", pc_path, "positions")
    if not col_equal:
        rep("warn", "points-colour-disagree-with-splat", pc_path, "max diff %s" % maxdiff)

    print("\n== POINT COUNT: %d (WKGS count %d, WKPC count %d, manifest gaussian_count %d / point_count %d)"
          % (N, gh["count"], ph["count"], gs_node["meta"]["gaussian_count"], pc_node["meta"]["point_count"]))
    print("  sample (i: position m | linear rgb float | WKPC u8):")
    for i in [0, 1, 2, 3, 4, N // 2, N - 1]:
        print("   %6d: (% .6f, % .6f, % .6f) | (%.6f, %.6f, %.6f) | (%3d, %3d, %3d)" % (
            i, means[3 * i], means[3 * i + 1], means[3 * i + 2],
            rgb[3 * i], rgb[3 * i + 1], rgb[3 * i + 2],
            pcol[3 * i], pcol[3 * i + 1], pcol[3 * i + 2]))
    mean_rgb = [sum(rgb[j::3]) / N for j in range(3)]
    print("  mean linear rgb: %s" % mean_rgb)

    if out:
        with open(os.path.join(out, "points.csv"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("index,x,y,z,r_linear,g_linear,b_linear,r_u8,g_u8,b_u8\n")
            for i in range(N):
                fh.write("%d,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,%d,%d,%d\n" % (
                    i, means[3 * i], means[3 * i + 1], means[3 * i + 2],
                    rgb[3 * i], rgb[3 * i + 1], rgb[3 * i + 2],
                    pcol[3 * i], pcol[3 * i + 1], pcol[3 * i + 2]))
        # an ordinary ASCII-free binary PLY point cloud for viewing, colours
        # sRGB-encoded for display (linear -> sRGB transfer function)
        def enc(c):
            return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
        with open(os.path.join(out, "points_srgb.ply"), "wb") as fh:
            fh.write(("ply\nformat binary_little_endian 1.0\ncomment from %s, WKGS means + DC band, colour sRGB-encoded\n"
                      "element vertex %d\nproperty float x\nproperty float y\nproperty float z\n"
                      "property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n"
                      % (os.path.basename(path), N)).encode("ascii"))
            rec = bytearray()
            for i in range(N):
                rec += struct.pack("<fffBBB", means[3 * i], means[3 * i + 1], means[3 * i + 2],
                                   *[min(255, max(0, round(enc(rgb[3 * i + j]) * 255))) for j in range(3)])
            fh.write(rec)
        print("  wrote %s/points.csv and %s/points_srgb.ply" % (out, out))

    # ---- summary
    print("\n== REPORT SUMMARY")
    errs = [r for r in REPORT if r[0] == "error"]
    for r in REPORT:
        print("  %-5s %-34s %s %s" % r)
    print("  errors: %d, signature: %s" % (len(errs), state))
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
