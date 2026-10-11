#!/usr/bin/env python3
"""werkread.py - a reader for a .werk package, written only from the documentation
carried inside the package (spec/SPEC.md, spec/MINI-SPECS.md, spec/layouts/*).

Usage:  python -I werkread.py PACKAGE.werk [OUTDIR]

Opens the container (store-mode zip, MINI-SPECS §5), lists the node graph with
meanings, verifies every declared hash (files[].sha256/size, license.sha256,
spec_sha256, input_hash where inputs are present, zip CRC-32), verifies the
Ed25519 signature chain (MINI-SPECS §12, SPEC §6), parses the WKRP envelope,
and extracts the primary mesh and primary sound (SPEC §2 `primary`, §2.1
payload resolution) to OUTDIR.

Standard library only. Never executes anything found inside the package.
"""
import hashlib
import json
import os
import struct
import sys
import zlib

REPORT = []  # (severity, code, message)


def report(sev, code, msg):
    REPORT.append((sev, code, msg))
    print("  [%s] %s: %s" % (sev, code, msg))


# --------------------------------------------------------------------------
# Container: store-mode zip, MINI-SPECS §5
# --------------------------------------------------------------------------
class ContainerError(Exception):
    pass


def open_zip(buf):
    """Return {name: (local_header_offset, method, csize, usize, crc)}."""
    n = len(buf)
    eocd = -1
    for off in range(n - 22, max(0, n - 22 - 65535) - 1, -1):
        if buf[off:off + 4] == b"PK\x05\x06":
            eocd = off
            break
    if eocd < 0:
        raise ContainerError("no EOCD record found")
    (_sig, _disk, _cddisk, cnt_disk, cnt_total, cd_size, cd_off,
     _clen) = struct.unpack_from("<IHHHHIIH", buf, eocd)
    # §5.5: zip64 detection is required even of zip32-only readers
    if (cnt_disk == 0xFFFF or cnt_total == 0xFFFF or cd_size == 0xFFFFFFFF
            or cd_off == 0xFFFFFFFF or (eocd >= 20 and buf[eocd - 20:eocd - 16] == b"PK\x06\x07")):
        raise ContainerError("zip64-unsupported")
    entries = {}
    order = []
    p = cd_off
    for _ in range(cnt_total):
        if buf[p:p + 4] != b"PK\x01\x02":
            raise ContainerError("bad central directory signature at %d" % p)
        (flags, method, crc, csize, usize, nlen, mlen, klen,
         lho) = struct.unpack_from("<8xHH4xIIIHHH8xI", buf, p)
        name = buf[p + 46:p + 46 + nlen].decode("utf-8")
        if name in entries:
            raise ContainerError("duplicate zip entry %r" % name)
        if name.startswith("/") or ".." in name.split("/") or ":" in name or "\\" in name:
            raise ContainerError("illegal entry name %r" % name)
        entries[name] = (lho, method, csize, usize, crc, flags)
        order.append(name)
        p += 46 + nlen + mlen + klen
    return entries, order


def read_entry(buf, ent):
    lho, method, csize, usize, crc, _flags = ent
    if buf[lho:lho + 4] != b"PK\x03\x04":
        raise ContainerError("bad local header at %d" % lho)
    nlen, mlen = struct.unpack_from("<HH", buf, lho + 26)  # re-read from local header
    start = lho + 30 + nlen + mlen
    data = buf[start:start + csize]
    if method == 0:
        pass
    elif method == 8:
        data = zlib.decompress(data, -15)
    else:
        raise ContainerError("unsupported compression method %d" % method)
    if len(data) != usize:
        raise ContainerError("size mismatch")
    return data, (zlib.crc32(data) & 0xFFFFFFFF) == crc


# --------------------------------------------------------------------------
# JSON, MINI-SPECS §2/§3: UTF-8, no BOM, duplicate keys rejected
# --------------------------------------------------------------------------
def _no_dupes(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise ValueError("duplicate JSON key %r" % k)
        d[k] = v
    return d


def load_json(b):
    if b.startswith(b"\xef\xbb\xbf"):
        raise ValueError("UTF-8 BOM present")
    return json.loads(b.decode("utf-8"), object_pairs_hook=_no_dupes,
                      parse_constant=lambda c: (_ for _ in ()).throw(ValueError("non-finite " + c)))


def canonical_json(v):
    # MINI-SPECS §3 canonical form (used only for input_params)
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256(b):
    return hashlib.sha256(b).hexdigest()


# --------------------------------------------------------------------------
# Ed25519 verify, MINI-SPECS §12 (non-constant-time; inputs are public)
# --------------------------------------------------------------------------
P = 2 ** 255 - 19
L = 2 ** 252 + 27742317777372353535851937790883648493


def _inv(a):
    return pow(a, P - 2, P)


D = (-121665 * _inv(121666)) % P
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


def _decode_point(b):
    if len(b) != 32:
        return None
    yy = int.from_bytes(b, "little")
    sign = yy >> 255
    y = yy & ((1 << 255) - 1)
    if y >= P:
        return None
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
    return ((p1[0] * p2[2] - p2[0] * p1[2]) % P == 0 and
            (p1[1] * p2[2] - p2[1] * p1[2]) % P == 0)


_By = 4 * _inv(5) % P
_Bx = _recover_x(_By, 0)
BASE = (_Bx, _By, 1, _Bx * _By % P)


def ed25519_verify(pub, msg, sig):
    if len(sig) != 64:
        return False
    A = _decode_point(pub)
    R = _decode_point(sig[:32])
    if A is None or R is None:
        return False
    S = int.from_bytes(sig[32:], "little")
    if S >= L:
        return False
    k = int.from_bytes(hashlib.sha512(sig[:32] + pub + msg).digest(), "little") % L
    lhs = _mul(8, _mul(S, BASE))
    rhs = _mul(8, _add(R, _mul(k, A)))
    return _eq(lhs, rhs)


def ed25519_selftest():
    # RFC 8032 vector 1, as printed in MINI-SPECS §12
    pub = bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
    sig = bytes.fromhex("e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b")
    ok = ed25519_verify(pub, b"", sig)
    bad = ed25519_verify(pub, b"x", sig)
    # MINI-SPECS §12.1 worked message: construction checkpoint + signature
    msg = sig_message({"manifest_sha256": "c421d2e85a9455f0be794ca8ee673f727a7ef67485d631e374f95c4a6d6ce61a",
                       "signed_at": "2026-08-08T09:00:00Z",
                       "signer": {"uri": "urn:werk:fixture:rfc8032-vector-1", "kind": "service"}}, "0" * 64)
    ck = len(msg) == 203 and sha256(msg) == "11e260cc16bc454f39f1aa6d56679c868ba1e83d33e3c22a462040b32a92165a"
    ex = ed25519_verify(pub, msg, bytes.fromhex(
        "55720b6fc38d680f8ca7523c0d8cec5045c7247f7158ab54eafd03d6ea0eedb1"
        "aeb4902b4704a5c2e78d7713b375068748bea4fd116a2d3a49f6010074c6410d"))
    return ok and not bad and ck and ex


def sig_message(entry, prev):
    return "\n".join(["werk-sig/1", entry["manifest_sha256"], prev, entry["signed_at"],
                      entry["signer"]["uri"], entry["signer"]["kind"]]).encode("utf-8")


# --------------------------------------------------------------------------
# MessagePack subset, ENVELOPE.layout.txt §4
# --------------------------------------------------------------------------
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
    fixed = {0xCC: ">B", 0xCD: ">H", 0xCE: ">I", 0xCF: ">Q", 0xD0: ">b", 0xD1: ">h",
             0xD2: ">i", 0xD3: ">q", 0xCA: ">f", 0xCB: ">d"}
    if t in fixed:
        f = fixed[t]
        return struct.unpack_from(f, b, i)[0], i + struct.calcsize(f)
    if t == 0xC0:
        return None, i
    if t == 0xC2:
        return False, i
    if t == 0xC3:
        return True, i
    lens = {0xD9: ">B", 0xDA: ">H", 0xDB: ">I", 0xC4: ">B", 0xC5: ">H", 0xC6: ">I"}
    if t in lens:
        f = lens[t]
        n = struct.unpack_from(f, b, i)[0]
        i += struct.calcsize(f)
        raw = b[i:i + n]
        return (raw.decode("utf-8") if t in (0xD9, 0xDA, 0xDB) else bytes(raw)), i + n
    if t in (0xDC, 0xDD):
        f = ">H" if t == 0xDC else ">I"
        n = struct.unpack_from(f, b, i)[0]
        return _mp_arr(b, i + struct.calcsize(f), n)
    if t in (0xDE, 0xDF):
        f = ">H" if t == 0xDE else ">I"
        n = struct.unpack_from(f, b, i)[0]
        return _mp_map(b, i + struct.calcsize(f), n)
    raise ValueError("banned/unknown MessagePack byte 0x%02x" % t)


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


DTYPE = {"u8": 1, "i8": 1, "u16": 2, "i16": 2, "u32": 4, "i32": 4, "u64": 8, "i64": 8,
         "f32": 4, "f64": 8}
MAGIC_KIND = {b"WKFF": "core.field.flow", b"WKRP": "core.pose.rest", b"WKAC": "core.anim.clip",
              b"WKSK": "core.skeleton", b"WKEM": "core.embedding", b"WKPC": "core.geom.points",
              b"WKGS": "core.geom.gsplat"}


def prod(xs):
    r = 1
    for x in xs:
        r *= x
    return r


def read_envelope(buf):
    """ENVELOPE.layout.txt §7 reference reader. Raises on any failed check."""
    magic = buf[0:4]
    version, hlen = struct.unpack_from("<II", buf, 4)
    assert 12 + hlen <= len(buf), "header overruns file"
    header, end = mp_decode(buf[12:12 + hlen])
    assert end == hlen, "header length mismatch"
    assert header["endianness"] == "le", "endianness"
    Pp = 16 * ((12 + hlen + 15) // 16)
    assert header["payload_origin"] == Pp, "payload_origin %r != %r" % (header["payload_origin"], Pp)
    assert Pp + header["payload_size"] == len(buf), "payload_size"
    if magic in MAGIC_KIND:
        assert header["kind"] == MAGIC_KIND[magic], "kind/magic mismatch"
    prev_end = Pp
    secs = {}
    for s in header["sections"]:
        assert s["offset"] % 16 == 0, "unaligned section %s" % s["name"]
        assert s["offset"] >= prev_end and s["offset"] - prev_end < 16, "gap before %s" % s["name"]
        assert s["offset"] + s["size"] <= len(buf), "section %s overruns" % s["name"]
        esz = DTYPE.get(s["dtype"]) or s["stride"]
        shape = s["shape"]
        if s["stride"] == esz:
            assert s["size"] == s["stride"] * prod(shape), "size rule (branch 1) %s" % s["name"]
        else:
            assert s["stride"] >= esz * shape[-1], "stride rule %s" % s["name"]
            assert s["size"] == s["stride"] * prod(shape[:-1]), "size rule (branch 2) %s" % s["name"]
        secs[s["name"]] = (s, buf[s["offset"]:s["offset"] + s["size"]])
        prev_end = s["offset"] + s["size"]
    assert 16 * ((prev_end + 15) // 16) == Pp + header["payload_size"], "trailing data"
    return magic, version, header, secs


def decode_wkrp(header, secs):
    s, poses = secs["poses"]
    _, contacts = secs["contacts"]
    out = []
    total = 0
    for k in range(header["pose_count"]):
        w, x, y, z, cf, cc, prob, area = struct.unpack_from("<4fIIff", poses, k * s["stride"])
        pts = [struct.unpack_from("<3f", contacts, 12 * c) for c in range(cf, cf + cc)]
        out.append({"quat_wxyz": (w, x, y, z), "contact_first": cf, "contact_count": cc,
                    "probability": prob, "support_area_m2": area, "contacts": pts})
        total += cc
    assert total == header["contact_count"], "contact_count sum"
    probs = [p["probability"] for p in out]
    assert probs == sorted(probs, reverse=True), "poses not sorted by probability"
    if header["trials"] > 0:
        assert abs(sum(probs) - 1.0) <= 1e-3, "probabilities do not sum to 1"
    for p in out:
        n = sum(c * c for c in p["quat_wxyz"]) ** 0.5
        assert abs(n - 1.0) <= 1e-6, "non-unit quaternion"
    return out


# --------------------------------------------------------------------------
# GLB (MINI-SPECS §10) and WAV (§9) inspection
# --------------------------------------------------------------------------
def inspect_glb(b):
    magic, ver, total = struct.unpack_from("<4sII", b, 0)
    assert magic == b"glTF" and ver == 2, "not glTF 2"
    assert total == len(b), "GLB length field %d != %d" % (total, len(b))
    off = 12
    js = binc = None
    while off < len(b):
        clen, ctype = struct.unpack_from("<II", b, off)
        data = b[off + 8:off + 8 + clen]
        if ctype == 0x4E4F534A:
            js = json.loads(data.decode("utf-8"))
        elif ctype == 0x004E4942:
            binc = data
        off += 8 + clen
    info = {"generator": js.get("asset", {}).get("generator"), "bin_bytes": len(binc or b"")}
    prims = []
    for m in js.get("meshes", []):
        for pr in m.get("primitives", []):
            attrs = pr["attributes"]
            pos = js["accessors"][attrs["POSITION"]]
            tri = js["accessors"][pr["indices"]]["count"] // 3 if "indices" in pr else pos["count"] // 3
            prims.append({"mode": pr.get("mode", 4), "attributes": sorted(attrs),
                          "vertices": pos["count"], "triangles": tri,
                          "pos_min": pos.get("min"), "pos_max": pos.get("max")})
    info["primitives"] = prims
    return info


def inspect_wav(b):
    assert b[0:4] == b"RIFF" and b[8:12] == b"WAVE", "not RIFF/WAVE"
    riff_size = struct.unpack_from("<I", b, 4)[0]
    off = 12
    fmt = None
    data_len = None
    while off + 8 <= len(b):
        cid, csz = struct.unpack_from("<4sI", b, off)
        if cid == b"fmt ":
            af, ch, sr, br, ba, bps = struct.unpack_from("<HHIIHH", b, off + 8)
            fmt = {"audio_format": af, "channels": ch, "sample_rate_hz": sr,
                   "byte_rate": br, "block_align": ba, "bits_per_sample": bps}
        elif cid == b"data":
            data_len = csz
        off += 8 + csz + (csz & 1)
    frames = data_len // fmt["block_align"]
    return dict(fmt, riff_size_ok=(riff_size == len(b) - 8), frames=frames,
                seconds=frames / fmt["sample_rate_hz"])


# --------------------------------------------------------------------------
# Meanings, transcribed from SPEC.md §3 / spec/README.md tables
# --------------------------------------------------------------------------
TYPE_MEANING = {
    "core.spec": "the format specification travelling inside the file (law 2)",
    "core.loader": "embedded single-file reader source (SPEC §7) - inert data here",
    "core.license": "full licence text",
    "core.readme": "one page for humans",
    "core.geom.source": "archival source mesh (GLB)",
    "core.geom.game": "runtime game mesh (GLB)",
    "core.geom.lod": "LOD mesh (GLB)",
    "core.material": "PBR material parameters (JSON)",
    "core.phys.bounds": "physical bounds (JSON)",
    "core.semantics": "facet tags, palette, search text (JSON)",
    "core.provenance": "who made what from what (JSON)",
    "core.audio.effect": "one sound effect: WAV takes + JSON descriptor",
    "core.audio.package": "audio package index (JSON)",
    "core.pose.rest": "settled rest orientations, WKRP envelope binary",
}
CONVENTIONS_SUPPORTED = {
    "endianness": "le", "units_per_meter": 1.0, "length_unit": "metre", "angle_unit": "radian",
    "time_unit": "second", "mass_unit": "kilogram", "up_axis": "y", "forward_axis": "-z",
    "right_axis": "+x", "handedness": "right", "winding": "ccw", "quat_order": "wxyz",
    "oct_encoding_pole": "y", "sh_l1_order": ["dc", "y", "z", "x"], "color_space_default": "srgb",
    "uv_origin": "top-left", "alignment_bytes": 16, "text_encoding": "utf-8",
    "id_case": "kebab-case", "hash_algorithm": "sha256", "signature_algorithm": "ed25519",
}


def resolve_payload(node_type, version):
    """SPEC §2.1 normative resolution. Returns (path, rule) or (None, candidates)."""
    files = version["files"]
    if "payload_file" in version:
        hits = [f for f in files if f["path"] == version["payload_file"]]
        if len(hits) == 1:
            return hits[0]["path"], "rule 1 (payload_file)"
        report("error", "payload-file-invalid", "payload_file %r not in files[]" % version["payload_file"])
    if len(files) == 1:
        return files[0]["path"], "rule 2 (single file)"
    pl = [f for f in files if f.get("role") == "payload"]
    if len(pl) == 1:
        return pl[0]["path"], "rule 3 (role payload)"
    type_role = {"core.audio.effect": "best", "core.audio.ambience": "best",
                 "core.imposter": "atlas", "core.recipe": "record"}
    r = type_role.get(node_type)
    if r:
        hits = [f for f in files if f.get("role") == r]
        if len(hits) == 1:
            return hits[0]["path"], "rule 4 (type role %s)" % r
    report("warn", "payload-file-ambiguous", "candidates %s" % [f["path"] for f in files])
    return None, None


# --------------------------------------------------------------------------
def main(path, outdir):
    print("== werkread: %s" % path)
    buf = open(path, "rb").read()  # read-only; the package is never modified
    print("container sha256 %s, %d bytes" % (sha256(buf), len(buf)))

    # 1. container
    print("\n== 1. container (MINI-SPECS §5)")
    try:
        entries, order = open_zip(buf)
    except ContainerError as e:
        report("fatal", "container", str(e))
        return 2
    blobs = {}
    for name in order:
        data, crc_ok = read_entry(buf, entries[name])
        blobs[name] = data
        if not crc_ok:
            report("error", "zip-crc", "%s CRC-32 mismatch" % name)
        if entries[name][1] != 0:
            report("info", "zip-method", "%s uses method %d" % (name, entries[name][1]))
        if entries[name][5] & 0x08:
            report("warn", "zip-data-descriptor", "%s has flag bit 3 set" % name)
    print("  %d entries, all CRC-32 checked" % len(order))

    # 2. manifest
    print("\n== 2. MANIFEST.json")
    if "MANIFEST.json" not in blobs:
        report("fatal", "manifest-missing", "")
        return 2
    mbytes = blobs["MANIFEST.json"]
    man = load_json(mbytes)
    print("  werk %d.%d  profile %s" % (man["werk"]["major"], man["werk"]["minor"], man["profile"]))
    print("  entity %s  %r" % (man["entity"]["uuid"], man["entity"]["name"]))
    if man["werk"]["major"] != 1:
        report("fatal", "werk-major", "unsupported major %r" % man["werk"]["major"])
        return 2
    if man["profile"] != "3d-entity/1":
        report("warn", "unsupported-profile", man["profile"])

    # 3. conventions
    print("\n== 3. conventions (SPEC §2, §10.1)")
    refused_types = set()
    cmap = {}
    if man.get("conventions_map") in blobs:
        cmap = load_json(blobs[man["conventions_map"]])["conventions"]
    for k, want in CONVENTIONS_SUPPORTED.items():
        have = man["conventions"].get(k, None)
        if have != want:
            gov = cmap.get(k, {}).get("governs", [])
            report("warn", "unsupported-convention", "%s=%r; refusing node types %s" % (k, have, gov))
            refused_types.update(gov)
    extra = set(man["conventions"]) - set(CONVENTIONS_SUPPORTED)
    for k in sorted(extra):
        report("info", "unknown-convention", k)
    if not refused_types:
        print("  all %d conventions supported" % len(CONVENTIONS_SUPPORTED))

    # 4. signature
    print("\n== 4. SIGNATURE.json (SPEC §6, MINI-SPECS §12)")
    sig_state = "absent"
    if "SIGNATURE.json" in blobs:
        sj = load_json(blobs["SIGNATURE.json"])
        if not ed25519_selftest():
            sig_state = "unverified"
            report("warn", "signature-unverified", "Ed25519 self-test failed; not checking")
        else:
            print("  Ed25519 self-test (RFC 8032 vector 1 + MINI-SPECS §12.1 checkpoint) passed")
            ok = True
            prev = "0" * 64
            for e in sj["chain"]:
                if e["prev_entry_sha256"] != prev:
                    ok = False
                    report("error", "signature-invalid", "entry %d prev_entry_sha256 mismatch" % e["index"])
                msg = sig_message(e, prev)
                good = ed25519_verify(bytes.fromhex(e["public_key"]), msg, bytes.fromhex(e["signature"]))
                print("  entry %d signer %s key %s... -> %s" % (e["index"], e["signer"]["uri"],
                                                                e["public_key"][:16], "ok" if good else "FAIL"))
                ok = ok and good
                prev = sha256(e["signature"].encode("utf-8"))
            actual = sha256(mbytes)
            if sj["chain"][-1]["manifest_sha256"] != actual:
                ok = False
                report("error", "signature-invalid", "last entry manifest_sha256 != sha256(MANIFEST.json) %s" % actual)
            if sj.get("manifest_sha256") != actual:
                ok = False
                report("error", "signature-invalid", "top-level manifest_sha256 != actual")
            sig_state = "signed-and-valid" if ok else "present-and-invalid"
    print("  signature state: %s" % sig_state)
    print("  (a valid chain proves the named key signed this manifest; it says nothing about who holds the key)")

    # 5/6. nodes and hashes
    print("\n== 5. node graph and hash verification (SPEC §2, §10 steps 5-8)")
    nodes = {n["node_id"]: n for n in man["nodes"]}
    dead = {}
    owner = {}
    file_meta = {}
    n_files = n_ok = 0
    for n in man["nodes"]:
        vers = {v["v"]: v for v in n["versions"]}
        act = vers.get(n["active"])
        if act is None:
            report("error", "active-invalid", n["node_id"])
            dead[n["node_id"]] = "active version missing"
            continue
        for v in n["versions"]:
            for f in v["files"]:
                prevowner = owner.get(f["path"])
                if prevowner and prevowner != n["node_id"]:
                    report("error", "file-claimed-twice", "%s by %s and %s" % (f["path"], prevowner, n["node_id"]))
                owner[f["path"]] = n["node_id"]
        for f in act["files"]:
            n_files += 1
            p = f["path"]
            file_meta[p] = f
            if p not in blobs:
                report("error", "file-missing", "%s (node %s)" % (p, n["node_id"]))
                dead[n["node_id"]] = "missing %s" % p
                continue
            got_sz, got_h = len(blobs[p]), sha256(blobs[p])
            if got_sz != f["size"] or got_h != f["sha256"]:
                report("error", "hash-mismatch", "%s declared %s/%d got %s/%d" % (p, f["sha256"], f["size"], got_h, got_sz))
                dead[n["node_id"]] = "hash mismatch %s" % p
            else:
                n_ok += 1
    print("  %d/%d declared files match size+sha256" % (n_ok, n_files))

    # requires-edges into dead/absent nodes kill the source (SPEC §5)
    changed = True
    while changed:
        changed = False
        for n in man["nodes"]:
            if n["node_id"] in dead:
                continue
            for e in n["edges"]:
                if e["kind"] == "requires" and (e["to"] in dead or e["to"] not in nodes):
                    dead[n["node_id"]] = "requires %s which is %s" % (e["to"], "dead" if e["to"] in dead else "absent")
                    changed = True
    for n in man["nodes"]:
        for e in n["edges"]:
            if e["to"] not in nodes:
                report("info" if e["kind"] == "enhances" else "warn", "edge-target-absent",
                       "%s -%s/%s-> %s (no such node in this package)" % (n["node_id"], e["kind"], e.get("role"), e["to"]))

    # floating bytes (SPEC §2: everything except MANIFEST/SIGNATURE reachable from a node)
    for name in order:
        if name in ("MANIFEST.json", "SIGNATURE.json") or name.endswith("/"):
            continue
        if name not in owner:
            report("warn", "file-floating", "%s is in the zip but in no node's files[]" % name)

    # license, spec_sha256, input_hash
    print("\n== 6. other declared hashes")
    lic = man["license"]
    lh = sha256(blobs.get(lic["file"], b""))
    print("  license.sha256 %s" % ("ok" if lh == lic["sha256"] else "MISMATCH " + lh))
    if lh != lic["sha256"]:
        report("error", "license-hash", lh)
    spec_paths = sorted({p for p in owner if p.startswith("spec/")}, key=lambda s: s.encode("utf-8"))
    acc = b""
    for p in spec_paths:
        acc += p.encode("utf-8") + b"\n" + bytes.fromhex(file_meta.get(p, {}).get("sha256") or sha256(blobs[p])) + b"\n"
    ssh = sha256(acc)
    print("  spec_sha256 over %d spec files: %s" % (len(spec_paths), "ok" if ssh == man["spec_sha256"] else "MISMATCH " + ssh))
    if ssh != man["spec_sha256"]:
        report("error", "spec-sha256", "computed %s declared %s" % (ssh, man["spec_sha256"]))
    if "total_size_bytes" in man["container"]:
        tot = sum(file_meta[p]["size"] for p in file_meta)
        print("  total_size_bytes declared %d computed %d" % (man["container"]["total_size_bytes"], tot))
    for n in man["nodes"]:
        act = {v["v"]: v for v in n["versions"]}.get(n["active"])
        if not act or "input_hash" not in act:
            continue
        ins = act.get("input_files", [])
        missing = [p for p in ins if p not in blobs]
        if missing:
            print("  input_hash %-34s not checkable: inputs not in package %s" % (n["node_id"], missing))
            report("info", "input-hash-uncheckable", "%s: %s absent" % (n["node_id"], missing))
            continue
        h = hashlib.sha256()
        for p in ins:
            h.update(hashlib.sha256(blobs[p]).digest())
        h.update(canonical_json(act.get("input_params", {})))
        ok = h.hexdigest() == act["input_hash"]
        print("  input_hash %-34s %s" % (n["node_id"], "ok (not stale)" if ok else "MISMATCH -> derived data is stale"))
        if not ok:
            report("warn", "input-hash-stale", "%s computed %s declared %s" % (n["node_id"], h.hexdigest(), act["input_hash"]))
    pp = man["container"].get("preview_prefix_bytes")
    if pp is not None:
        print("  preview_prefix_bytes (a HINT, S-15) = %d" % pp)

    # listing
    print("\n== 7. node listing")
    for n in man["nodes"]:
        nid, t = n["node_id"], n["type"]
        act = {v["v"]: v for v in n["versions"]}.get(n["active"], {})
        meaning = TYPE_MEANING.get(t, "extension node (x.*), skipped by core readers" if t.startswith("x.") else "UNKNOWN TYPE - skipped")
        status = "DEAD (%s)" % dead[nid] if nid in dead else ("REFUSED (convention)" if t in refused_types else "live")
        print("\n  %s  [%s]  %s" % (nid, t, status))
        print("    meaning : %s" % meaning)
        print("    active v%s, %s, producer %s %s%s" % (n["active"], act.get("epistemic"), act.get("producer", {}).get("tool"),
                                                     act.get("producer", {}).get("version"),
                                                     (" model " + act["producer"]["model"]) if "model" in act.get("producer", {}) else ""))
        print("    note    : %s" % act.get("note"))
        for f in act.get("files", []):
            print("    file    : %-48s %8d  %s%s" % (f["path"], f["size"], f["sha256"][:16], ("  role=" + f["role"]) if "role" in f else ""))
        for e in n["edges"]:
            print("    edge    : %s %s -> %s" % (e["kind"], e.get("role", ""), e["to"]))

    # 8. payload inspection
    print("\n== 8. payload inspection (§10 step 7)")
    for n in man["nodes"]:
        if n["node_id"] in dead or n["type"] in refused_types:
            continue
        act = {v["v"]: v for v in n["versions"]}[n["active"]]
        for f in act["files"]:
            p, b = f["path"], blobs[f["path"]]
            try:
                if p.endswith(".json"):
                    load_json(b)
                elif p.endswith(".glb"):
                    print("  %s: %s" % (p, inspect_glb(b)))
                elif p.endswith(".wav"):
                    print("  %s: %s" % (p, inspect_wav(b)))
                elif b[:4] in MAGIC_KIND or b[:3] == b"WKX":
                    magic, ver, hdr, secs = read_envelope(b)
                    print("  %s: envelope %s v%d kind=%s sections=%s" % (p, magic.decode(), ver, hdr["kind"], list(secs)))
                    shown = {k: v for k, v in hdr.items() if k != "sections"}
                    print("    header: %s" % shown)
                    if magic == b"WKRP":
                        for i, pose in enumerate(decode_wkrp(hdr, secs)):
                            print("    pose %d: q(wxyz)=%s p=%.4f area=%.5f m2 contacts=%s" % (
                                i, tuple(round(c, 6) for c in pose["quat_wxyz"]), pose["probability"],
                                pose["support_area_m2"], [tuple(round(c, 4) for c in pt) for pt in pose["contacts"]]))
                        if hdr.get("input_hash") and hdr["input_hash"] != act.get("input_hash"):
                            report("warn", "envelope-input-hash-disagrees",
                                   "%s header input_hash %s != manifest %s" % (p, hdr["input_hash"], act.get("input_hash")))
            except Exception as ex:  # node-scoped refusal (§10.1)
                report("error", "payload-malformed", "%s: %s" % (p, ex))
                dead[n["node_id"]] = "malformed payload %s" % p

    # 9. extract primary mesh + sound
    print("\n== 9. extraction (SPEC §2 primary, §2.1 payload resolution)")
    os.makedirs(outdir, exist_ok=True)
    prim = man.get("primary", {})
    results = []
    for slot in ("mesh", "sound"):
        nid = prim.get(slot)
        if nid is None:
            report("warn", "primary-fallback", "no primary.%s" % slot)
            continue
        n = nodes.get(nid)
        if n is None or nid in dead:
            report("error", "primary-unavailable", "%s -> %s" % (slot, nid))
            continue
        act = {v["v"]: v for v in n["versions"]}[n["active"]]
        pth, rule = resolve_payload(n["type"], act)
        if pth is None:
            continue
        data = blobs[pth]
        dest = os.path.join(outdir, os.path.basename(pth))
        with open(dest, "wb") as fh:
            fh.write(data)
        declared = file_meta[pth]["sha256"]
        written = sha256(open(dest, "rb").read())
        print("  primary.%s = %s -> %s via %s" % (slot, nid, pth, rule))
        print("    wrote %s (%d bytes)" % (dest, len(data)))
        print("    declared sha256 %s" % declared)
        print("    on-disk  sha256 %s  %s" % (written, "MATCH" if written == declared else "MISMATCH"))
        results.append((slot, nid, pth, dest, declared, written))

    # summary
    print("\n== summary")
    print("  signature: %s" % sig_state)
    print("  dead nodes: %s" % (dead or "none"))
    sev = {}
    for s, c, _ in REPORT:
        sev.setdefault(s, []).append(c)
    for s in ("fatal", "error", "warn", "info"):
        if s in sev:
            print("  %s: %d  %s" % (s, len(sev[s]), sorted(set(sev[s]))))
    ok = all(r[4] == r[5] for r in results) and len(results) == 2
    print("  extraction: %s" % ("OK, both hashes match the manifest" if ok else "INCOMPLETE"))
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "out"))
