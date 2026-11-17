"""werk_inspect.py: open a .werk package, list its contents with meanings,
verify integrity, and decode its binary envelope(s).

Written from the spec files carried INSIDE the package (spec/README.md,
spec/SPEC.md, spec/MINI-SPECS.md, spec/layouts/*.layout.txt and the worked
hex dump). Standard library only. It never imports, runs or writes out any
code from the package; loaders are treated as inert text.

usage: python -I werk_inspect.py PACKAGE.werk [--entries N]
"""
import hashlib
import json
import math
import struct
import sys
import zlib

# ---------------------------------------------------------------------------
# Node type meanings, from the table in spec/README.md
# ---------------------------------------------------------------------------
TYPE_MEANING = {
    "core.spec": "the format specification travelling with the file (text + JSON)",
    "core.loader": "embedded single-file reader program (source)",
    "core.license": "full licence text",
    "core.readme": "one page for a human",
    "core.geom.source": "source mesh (GLB)",
    "core.geom.game": "runtime mesh (GLB)",
    "core.geom.lod": "level-of-detail mesh (GLB)",
    "core.tex": "texture (PNG)",
    "core.material": "PBR material parameters (JSON)",
    "core.phys.bounds": "physical bounds (JSON)",
    "core.phys.colliders": "collision shapes (JSON)",
    "core.phys.body": "mass / centre of mass / inertia (JSON)",
    "core.pose.rest": "settled rest poses (WKRP envelope binary)",
    "core.audio.effect": "sound effect (WAV + JSON descriptor)",
    "core.audio.ambience": "ambience sound (WAV + JSON)",
    "core.audio.package": "audio package descriptor (JSON)",
    "core.semantics": "facet tags, palette, search text (JSON)",
    "core.provenance": "who made what from what (JSON)",
}
MAGIC_KIND = {b"WKFF": "core.field.flow", b"WKRP": "core.pose.rest",
              b"WKAC": "core.anim.clip", b"WKSK": "core.skeleton",
              b"WKEM": "core.embedding", b"WKPC": "core.geom.points",
              b"WKGS": "core.geom.gsplat"}


def meaning(t):
    if t in TYPE_MEANING:
        return TYPE_MEANING[t]
    if t.startswith("x."):
        return "extension node (meaning supplied by the extension, not core)"
    return "UNKNOWN type (skipped per SPEC 10 step 8)"


# ---------------------------------------------------------------------------
# Zip, MINI-SPECS.md section 5 (store mode only; zip64 detected and refused)
# ---------------------------------------------------------------------------
class ZipError(Exception):
    pass


def crc32(data):
    return zlib.crc32(data) & 0xFFFFFFFF


def read_zip(buf):
    size = len(buf)
    lo = max(0, size - 22 - 65535)
    eocd = -1
    for off in range(size - 22, lo - 1, -1):
        if buf[off:off + 4] == b"PK\x05\x06":
            eocd = off
            break
    if eocd < 0:
        raise ZipError("no EOCD")
    (_, _, _, n_disk, n_total, cd_size, cd_off, _) = struct.unpack_from(
        "<IHHHHIIH", buf, eocd)
    if 0xFFFF in (n_disk, n_total) or 0xFFFFFFFF in (cd_size, cd_off) \
            or (eocd >= 20 and buf[eocd - 20:eocd - 16] == b"PK\x06\x07"):
        raise ZipError("zip64-unsupported")
    entries = []
    p = cd_off
    for _ in range(n_total):
        if buf[p:p + 4] != b"PK\x01\x02":
            raise ZipError("bad central directory signature at %d" % p)
        (flags, method, crc, csize, usize, n, m, k, lho) = (
            struct.unpack_from("<H", buf, p + 8)[0],
            struct.unpack_from("<H", buf, p + 10)[0],
            *struct.unpack_from("<III", buf, p + 16),
            *struct.unpack_from("<HHH", buf, p + 28),
            struct.unpack_from("<I", buf, p + 42)[0])
        name = buf[p + 46:p + 46 + n].decode("utf-8")
        p += 46 + n + m + k
        if buf[lho:lho + 4] != b"PK\x03\x04":
            raise ZipError("bad local header for %s" % name)
        ln, lm = struct.unpack_from("<HH", buf, lho + 26)
        data_off = lho + 30 + ln + lm
        entries.append(dict(name=name, flags=flags, method=method, crc=crc,
                            csize=csize, usize=usize, lho=lho,
                            data_off=data_off))
    return entries, eocd


# ---------------------------------------------------------------------------
# MessagePack subset, ENVELOPE.layout.txt section 4 (big-endian inside)
# ---------------------------------------------------------------------------
class MPError(Exception):
    pass


def mp_decode(b, i=0):
    t = b[i]
    i += 1
    if t <= 0x7F:
        return t, i
    if t >= 0xE0:
        return t - 256, i
    if 0xA0 <= t <= 0xBF:
        n = t & 0x1F
        return b[i:i + n].decode("utf-8"), i + n
    if 0x90 <= t <= 0x9F:
        return _mp_arr(b, i, t & 0x0F)
    if 0x80 <= t <= 0x8F:
        return _mp_map(b, i, t & 0x0F)
    simple = {0xC0: None, 0xC2: False, 0xC3: True}
    if t in simple:
        return simple[t], i
    fixed = {0xCC: ">B", 0xCD: ">H", 0xCE: ">I", 0xCF: ">Q",
             0xD0: ">b", 0xD1: ">h", 0xD2: ">i", 0xD3: ">q",
             0xCA: ">f", 0xCB: ">d"}
    if t in fixed:
        f = fixed[t]
        return struct.unpack_from(f, b, i)[0], i + struct.calcsize(f)
    lens = {0xD9: ">B", 0xDA: ">H", 0xDB: ">I",
            0xC4: ">B", 0xC5: ">H", 0xC6: ">I"}
    if t in lens:
        f = lens[t]
        n = struct.unpack_from(f, b, i)[0]
        i += struct.calcsize(f)
        raw = b[i:i + n]
        return (raw.decode("utf-8") if t >= 0xD9 else bytes(raw)), i + n
    if t in (0xDC, 0xDD):
        f = ">H" if t == 0xDC else ">I"
        n = struct.unpack_from(f, b, i)[0]
        return _mp_arr(b, i + struct.calcsize(f), n)
    if t in (0xDE, 0xDF):
        f = ">H" if t == 0xDE else ">I"
        n = struct.unpack_from(f, b, i)[0]
        return _mp_map(b, i + struct.calcsize(f), n)
    raise MPError("banned or unknown MessagePack byte 0x%02x" % t)


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
        out[k] = v
    return out, i


# ---------------------------------------------------------------------------
# Envelope, ENVELOPE.layout.txt sections 1, 3, 5, 6, 7
# ---------------------------------------------------------------------------
DTYPE = {"u8": ("B", 1), "i8": ("b", 1), "u16": ("H", 2), "i16": ("h", 2),
         "u32": ("I", 4), "i32": ("i", 4), "u64": ("Q", 8), "i64": ("q", 8),
         "f32": ("f", 4), "f64": ("d", 8)}


class EnvError(Exception):
    pass


def check(cond, msg):
    if not cond:
        raise EnvError(msg)


def read_envelope(buf):
    check(len(buf) >= 12, "file shorter than 12 bytes")
    magic = bytes(buf[0:4])
    version, header_len = struct.unpack_from("<II", buf, 4)
    check(header_len >= 1 and 12 + header_len <= len(buf), "header_len out of range")
    header, end = mp_decode(buf[12:12 + header_len])
    check(end == header_len, "header map does not fill header_len exactly")
    check(isinstance(header, dict), "header is not a map")
    for k in ("kind", "endianness", "payload_origin", "payload_size", "sections"):
        check(k in header, "mandatory header key missing: " + k)
    check(header["endianness"] == "le", "endianness is not 'le'")
    check(MAGIC_KIND.get(magic) == header["kind"], "magic does not match kind")
    P = 16 * math.ceil((12 + header_len) / 16)
    check(header["payload_origin"] == P, "payload_origin %r != computed %d"
          % (header["payload_origin"], P))
    check(P + header["payload_size"] == len(buf), "payload_origin+payload_size != file size")
    secs = {}
    prev_end = P
    for s in header["sections"]:
        off, size, stride, shape = s["offset"], s["size"], s["stride"], s["shape"]
        check(off % 16 == 0, "section %s offset not 16-aligned" % s["name"])
        check(prev_end <= off < prev_end + 16 or (off == prev_end),
              "section %s not in file order / gap > 15" % s["name"])
        check(off + size <= len(buf), "section %s overruns file" % s["name"])
        esz = DTYPE[s["dtype"]][1] if s["dtype"] in DTYPE else stride
        if stride == esz:
            check(size == stride * math.prod(shape), "size rule (branch 1) fails for " + s["name"])
        else:
            check(stride >= esz * shape[-1], "stride rule fails for " + s["name"])
            check(size == stride * math.prod(shape[:-1]), "size rule (branch 2) fails for " + s["name"])
        secs[s["name"]] = (s, bytes(buf[off:off + size]))
        prev_end = off + size
    check(16 * math.ceil(prev_end / 16) == P + header["payload_size"],
          "last section end (rounded) != payload end")
    return magic, version, header, secs


def decode_wkrp(header, secs):
    """restposes.layout.txt: 'poses' record stride 32, 'contacts' f32[c,3]."""
    s, raw = secs["poses"]
    poses = []
    for r in range(s["shape"][0]):
        w, x, y, z, cfirst, ccount, prob, area = struct.unpack_from(
            "<ffffIIff", raw, r * s["stride"])
        poses.append(dict(quat_wxyz=(w, x, y, z), contact_first=cfirst,
                          contact_count=ccount, probability=prob,
                          support_area_m2=area))
    s, raw = secs["contacts"]
    contacts = [struct.unpack_from("<fff", raw, c * s["stride"])
                for c in range(s["shape"][0])]
    # invariants a reader MUST check
    problems = []
    if len(poses) != header["pose_count"]:
        problems.append("pose_count mismatch")
    if sum(p["contact_count"] for p in poses) != header["contact_count"]:
        problems.append("sum(contact_count) != header contact_count")
    if len(contacts) != header["contact_count"]:
        problems.append("contacts section length != header contact_count")
    probs = [p["probability"] for p in poses]
    if probs != sorted(probs, reverse=True):
        problems.append("poses not sorted by probability descending")
    if header["trials"] > 0 and abs(sum(probs) - 1.0) > 1e-3:
        problems.append("probabilities sum to %r, not 1 +/- 1e-3" % sum(probs))
    for i, p in enumerate(poses):
        q = p["quat_wxyz"]
        n = math.sqrt(sum(c * c for c in q))
        if abs(n - 1.0) > 1e-6:
            problems.append("pose %d |q| = %.9f (outside 1e-6 of 1)" % (i, n))
        if q[0] < 0:
            problems.append("pose %d has w < 0 (non-canonical sign)" % i)
        if p["contact_count"] < 1:
            problems.append("pose %d has contact_count < 1" % i)
        if p["contact_first"] + p["contact_count"] > len(contacts):
            problems.append("pose %d contact range overruns contacts" % i)
    for v in [c for p in poses for c in p["quat_wxyz"]] + [c for t in contacts for c in t]:
        if math.isnan(v) or math.isinf(v):
            problems.append("NaN/Inf in payload")
            break
    return poses, contacts, problems


# ---------------------------------------------------------------------------
# Ed25519 verify, MINI-SPECS.md section 12 (verify only; inputs are public)
# ---------------------------------------------------------------------------
_p = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493
_d = -121665 * pow(121666, _p - 2, _p) % _p
_I = pow(2, (_p - 1) // 4, _p)


def _add(P, Q):
    X1, Y1, Z1, T1 = P
    X2, Y2, Z2, T2 = Q
    A = (Y1 - X1) * (Y2 - X2) % _p
    B = (Y1 + X1) * (Y2 + X2) % _p
    C = T1 * 2 * _d * T2 % _p
    D = Z1 * 2 * Z2 % _p
    E, F, G, H = B - A, D - C, D + C, B + A
    return (E * F % _p, G * H % _p, F * G % _p, E * H % _p)


def _mul(s, P):
    Q = (0, 1, 1, 0)
    while s:
        if s & 1:
            Q = _add(Q, P)
        P = _add(P, P)
        s >>= 1
    return Q


def _decompress(b):
    if len(b) != 32:
        return None
    y = int.from_bytes(b, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    if y >= _p:
        return None
    u = (y * y - 1) % _p
    v = (_d * y * y + 1) % _p
    x = u * pow(v, 3, _p) * pow(u * pow(v, 7, _p), (_p - 5) // 8, _p) % _p
    if v * x * x % _p == (-u) % _p:
        x = x * _I % _p
    if v * x * x % _p != u:
        return None
    if x == 0 and sign == 1:
        return None
    if (x & 1) != sign:
        x = _p - x
    return (x, y, 1, x * y % _p)


def _eq(P, Q):
    X1, Y1, Z1, _ = P
    X2, Y2, Z2, _ = Q
    return (X1 * Z2 - X2 * Z1) % _p == 0 and (Y1 * Z2 - Y2 * Z1) % _p == 0


_By = 4 * pow(5, _p - 2, _p) % _p
_B = _decompress(_By.to_bytes(32, "little"))  # sign bit 0 -> even x


def ed25519_verify(pub, msg, sig):
    if len(sig) != 64:
        return False
    S = int.from_bytes(sig[32:], "little")
    if S >= _L:
        return False
    A = _decompress(pub)
    R = _decompress(sig[:32])
    if A is None or R is None:
        return False
    k = int.from_bytes(hashlib.sha512(sig[:32] + pub + msg).digest(), "little") % _L
    return _eq(_mul(8, _mul(S, _B)), _mul(8, _add(R, _mul(k, A))))


def ed25519_self_test():
    # RFC 8032 test 1, as printed in MINI-SPECS.md section 12
    pub = bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
    sig = bytes.fromhex("e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b")
    ok1 = ed25519_verify(pub, b"", sig)
    bad = ed25519_verify(pub, b"x", sig)
    # the worked werk-sig/1 example in MINI-SPECS.md section 12.1
    msg = sig_message("c421d2e85a9455f0be794ca8ee673f727a7ef67485d631e374f95c4a6d6ce61a",
                      "0" * 64, "2026-08-08T09:00:00Z",
                      "urn:werk:fixture:rfc8032-vector-1", "service")
    ck = (len(msg) == 203 and hashlib.sha256(msg).hexdigest() ==
          "11e260cc16bc454f39f1aa6d56679c868ba1e83d33e3c22a462040b32a92165a")
    sig2 = bytes.fromhex("55720b6fc38d680f8ca7523c0d8cec5045c7247f7158ab54eafd03d6ea0eedb1"
                         "aeb4902b4704a5c2e78d7713b375068748bea4fd116a2d3a49f6010074c6410d")
    ok2 = ed25519_verify(pub, msg, sig2)
    return ok1 and not bad and ck and ok2, dict(rfc_vector=ok1, rejects_wrong_msg=not bad,
                                               message_checkpoint=ck, example_sig=ok2)


def sig_message(manifest_sha, prev, signed_at, uri, kind):
    return "\n".join(["werk-sig/1", manifest_sha, prev, signed_at, uri, kind]).encode("utf-8")


# ---------------------------------------------------------------------------
# Hash constructions, MINI-SPECS.md 11 "What gets hashed" and SPEC.md 2
# ---------------------------------------------------------------------------
def canonical_json(obj):
    # Only ever applied to input_params here, which is {} in this package.
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def input_hash(paths, digests, params):
    h = hashlib.sha256()
    for p in paths:
        h.update(bytes.fromhex(digests[p]))
    h.update(canonical_json(params or {}).encode("utf-8"))
    return h.hexdigest()


def spec_hash(spec_files):
    h = hashlib.sha256()
    for path, sha in sorted(spec_files, key=lambda t: t[0].encode("utf-8")):
        h.update(path.encode("utf-8") + b"\n" + bytes.fromhex(sha) + b"\n")
    return h.hexdigest()


# ---------------------------------------------------------------------------
def main(argv):
    path = argv[1]
    n_show = 5
    if "--entries" in argv:
        n_show = int(argv[argv.index("--entries") + 1])
    buf = open(path, "rb").read()
    report = {"ok": [], "fail": [], "warn": [], "info": []}

    def ok(m): report["ok"].append(m); print("  OK    " + m)
    def fail(m): report["fail"].append(m); print("  FAIL  " + m)
    def warn(m): report["warn"].append(m); print("  WARN  " + m)
    def info(m): report["info"].append(m); print("  INFO  " + m)

    print("=" * 78)
    print("CONTAINER  %s  (%d bytes)" % (path, len(buf)))
    print("=" * 78)
    entries, eocd = read_zip(buf)
    print("  %d zip entries, EOCD at %d" % (len(entries), eocd))
    files = {}
    for e in entries:
        if e["method"] != 0:
            fail("%s: compression method %d unsupported (store-only reader)" % (e["name"], e["method"]))
            continue
        if e["flags"] & 0x08:
            fail("%s: flag bit 3 (data descriptor) set" % e["name"])
        n = e["name"]
        if n.startswith("/") or ".." in n.split("/") or ":" in n or "\\" in n:
            fail("unsafe entry name %r" % n)
        data = buf[e["data_off"]:e["data_off"] + e["csize"]]
        if e["csize"] != e["usize"]:
            fail("%s: store entry with csize != usize" % n)
        if crc32(data) != e["crc"]:
            fail("%s: zip CRC-32 mismatch" % n)
        files[n] = data
    ok("all %d entries are store-mode; zip CRC-32 checked on each" % len(files))

    man_bytes = files["MANIFEST.json"]
    man = json.loads(man_bytes.decode("utf-8"))
    print("\nMANIFEST  werk %d.%d  profile %s" % (man["werk"]["major"], man["werk"]["minor"], man["profile"]))
    print("  entity: %s  (%s)" % (man["entity"]["name"], man["entity"]["uuid"]))
    if man["werk"]["major"] != 1:
        fail("unsupported werk.major %r" % man["werk"]["major"])
    if man["profile"] != "3d-entity/1":
        info("profile %s not implemented here: listing and hashing only" % man["profile"])

    # ---- contents listing with meanings, and per-file hash checks
    print("\n" + "=" * 78)
    print("NODES (graph), with meanings and per-file size + sha256 checks")
    print("=" * 78)
    digests = {}
    declared = set()
    dead = set()
    node_ids = {n["node_id"] for n in man["nodes"]}
    for node in man["nodes"]:
        act = node.get("active")
        ver = next((v for v in node["versions"] if v["v"] == act), None)
        print("\n[%s]  type=%s" % (node["node_id"], node["type"]))
        print("    meaning : " + meaning(node["type"]))
        if ver is None:
            fail("%s: active version %r missing" % (node["node_id"], act))
            continue
        print("    v%d  epistemic=%s  producer=%s" % (ver["v"], ver.get("epistemic"),
              json.dumps(ver.get("producer"))))
        if ver.get("note"):
            print("    note    : " + ver["note"])
        for e in node.get("edges", []):
            tag = "" if e["to"] in node_ids else "   (target node not in this package)"
            print("    edge    : %s --%s/%s--> %s%s" % (node["node_id"], e["kind"], e.get("role"), e["to"], tag))
        for f in ver["files"]:
            p = f["path"]
            declared.add(p)
            digests[p] = f["sha256"]
            if p not in files:
                fail("%s: declared file %s missing from container" % (node["node_id"], p))
                continue
            d = files[p]
            good = len(d) == f["size"] and hashlib.sha256(d).hexdigest() == f["sha256"]
            print("    file    : %-48s %7d B  %s%s" % (p, f["size"], "sha256 OK" if good else "MISMATCH",
                  ("  role=" + f["role"]) if f.get("role") else ""))
            if not good:
                dead.add(node["node_id"])
                fail("%s: %s size/sha256 mismatch -> node dead" % (node["node_id"], p))
        if node["type"] == "core.loader":
            m = node.get("meta", {})
            print("    loader  : language=%s form=%s toolchain=%s deps=%s caps=%s"
                  % (m.get("language"), m.get("form"), m.get("toolchain"),
                     m.get("dependencies"), ",".join(m.get("capabilities", []))))
            print("              (inert text here: not compiled, not run)")
    undeclared = [n for n in files if n not in declared and n not in ("MANIFEST.json", "SIGNATURE.json")]
    for n in undeclared:
        info("container entry not declared by any node: %s" % n)
    ok("per-file size+sha256 checked for %d declared files" % len(declared))

    # ---- package-level hashes
    print("\n" + "=" * 78)
    print("PACKAGE-LEVEL INTEGRITY")
    print("=" * 78)
    lic = man["license"]
    if hashlib.sha256(files[lic["file"]]).hexdigest() == lic["sha256"]:
        ok("license.sha256 matches %s" % lic["file"])
    else:
        fail("license.sha256 mismatch")
    spec_files = [(p, digests[p]) for p in declared if p.startswith("spec/")]
    sh = spec_hash(spec_files)
    (ok if sh == man["spec_sha256"] else fail)("spec_sha256 over %d spec/ files: %s" % (len(spec_files), sh))
    for node in man["nodes"]:
        ver = next((v for v in node["versions"] if v["v"] == node.get("active")), None)
        if ver is None or "input_hash" not in ver:
            continue
        missing = [p for p in ver["input_files"] if p not in digests]
        if missing:
            info("%s input_hash not checkable: inputs not in package: %s" % (node["node_id"], ", ".join(missing)))
            continue
        ih = input_hash(ver["input_files"], digests, ver.get("input_params"))
        if ih == ver["input_hash"]:
            ok("%s input_hash recomputed and matches" % node["node_id"])
        else:
            # spec/README.md question 6: a mismatch means the derived data is
            # STALE relative to its declared inputs. It is not file damage:
            # every byte still matches its sha256 and the signature.
            warn("%s input_hash STALE: declared %s..., recomputed %s... from %s"
                 % (node["node_id"], ver["input_hash"][:16], ih[:16], ver["input_files"]))
    co = man["container"]
    ppb = co.get("preview_prefix_bytes")
    if ppb is not None:
        info("preview_prefix_bytes (a hint, never checked as exact) = %d" % ppb)

    # ---- signature
    print("\n" + "=" * 78)
    print("SIGNATURE")
    print("=" * 78)
    selftest, detail = ed25519_self_test()
    print("  Ed25519 self-test against spec vectors: %s %s" % (selftest, detail))
    if "SIGNATURE.json" not in files:
        state = "absent"
    elif not selftest:
        state = "unverified"
    else:
        sig = json.loads(files["SIGNATURE.json"].decode("utf-8"))
        man_sha = hashlib.sha256(man_bytes).hexdigest()
        state = "signed-and-valid"
        prev = "0" * 64
        for ent in sig["chain"]:
            if ent["prev_entry_sha256"] != prev:
                state = "present-and-invalid"
            msg = sig_message(ent["manifest_sha256"], ent["prev_entry_sha256"], ent["signed_at"],
                              ent["signer"]["uri"], ent["signer"]["kind"])
            v = ed25519_verify(bytes.fromhex(ent["public_key"]), msg, bytes.fromhex(ent["signature"]))
            print("  chain[%d] signer=%s  ed25519=%s" % (ent["index"], ent["signer"]["uri"], v))
            if not v:
                state = "present-and-invalid"
            prev = hashlib.sha256(ent["signature"].encode("utf-8")).hexdigest()
        if sig["chain"][-1]["manifest_sha256"] != man_sha or sig["manifest_sha256"] != man_sha:
            state = "present-and-invalid"
        print("  sha256(MANIFEST.json bytes) = %s" % man_sha)
    (ok if state == "signed-and-valid" else fail if state == "present-and-invalid" else info)(
        "signature state: %s" % state)
    if state == "signed-and-valid":
        info("the signing key is a publicly derived DEV key (README): proves the chain, not authorship")

    # ---- envelopes
    print("\n" + "=" * 78)
    print("BINARY ENVELOPES")
    print("=" * 78)
    for node in man["nodes"]:
        ver = next((v for v in node["versions"] if v["v"] == node.get("active")), None)
        for f in (ver or {}).get("files", []):
            d = files.get(f["path"], b"")
            if d[:2] != b"WK" or f["path"].startswith("spec/"):
                continue
            print("\n[%s] %s" % (node["node_id"], f["path"]))
            if node["node_id"] in dead:
                info("%s is dead (hash mismatch): envelope not decoded" % node["node_id"])
                continue
            try:
                magic, version, header, secs = read_envelope(d)
            except (EnvError, MPError, KeyError, IndexError, struct.error) as ex:
                fail("%s: envelope rejected -> node dead: %s" % (node["node_id"], ex))
                continue
            print("  magic=%s version=%d kind=%s  layout=%s" % (magic.decode(), version, header["kind"],
                  man.get("layouts", {}).get(node["type"])))
            print("  header = " + json.dumps(header, sort_keys=True))
            ok("envelope structure and section consistency rules pass")
            if header.get("input_hash") and header["input_hash"] != ver.get("input_hash"):
                fail("envelope input_hash disagrees with manifest")
            elif ver.get("input_hash") and not header.get("input_hash"):
                info("manifest has input_hash for this node; envelope header has none (cannot cross-check)")
            if header.get("producer") and header["producer"] != ver.get("producer"):
                info("header producer %s != manifest producer %s" % (header["producer"], ver.get("producer")))
            if magic != b"WKRP":
                info("no decoder for %s here; sections listed only" % magic)
                continue
            poses, contacts, probs = decode_wkrp(header, secs)
            for pmsg in probs:
                fail("WKRP invariant: " + pmsg)
            if not probs:
                ok("WKRP invariants pass (contact sum, sort order, probability sum, |q|, ranges)")
            # plausibility: contacts are model-space points that touch the
            # floor, so they should lie on this entity's measured bounds
            bnode = next((n for n in man["nodes"] if n["type"] == "core.phys.bounds"), None)
            if bnode:
                bpath = bnode["versions"][0]["files"][0]["path"]
                ent = json.loads(files[bpath].decode("utf-8"))["entity"]
                lo, hi = ent["aabb_min"], ent["aabb_max"]
                on_box = [c for c in contacts if any(abs(c[a] - lo[a]) < 1e-3 or abs(c[a] - hi[a]) < 1e-3
                                                     for a in range(3))]
                if len(on_box) < len(contacts):
                    warn("%d of %d contact points do not lie on any face of the measured AABB %s..%s "
                         "(pose data may not describe this mesh)" % (len(contacts) - len(on_box),
                                                                     len(contacts), lo, hi))
            print("\n  KIND: core.pose.rest (settled rest poses).  %d pose entries, %d contact points"
                  % (len(poses), len(contacts)))
            for i, p in enumerate(poses[:n_show]):
                print("  pose %d: quat(w,x,y,z)=(%.7g, %.7g, %.7g, %.7g)  contacts[%d..%d)  p=%.7g  area=%.7g m^2"
                      % ((i,) + p["quat_wxyz"] + (p["contact_first"], p["contact_first"] + p["contact_count"],
                                                  p["probability"], p["support_area_m2"])))
                for c in range(p["contact_first"], p["contact_first"] + p["contact_count"]):
                    print("          contact %d (model space, m): (%.7g, %.7g, %.7g)" % ((c,) + contacts[c]))

    print("\n" + "=" * 78)
    print("SUMMARY: %d ok, %d fail, %d warn, %d info" % (len(report["ok"]), len(report["fail"]),
                                                          len(report["warn"]), len(report["info"])))
    return 1 if report["fail"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
