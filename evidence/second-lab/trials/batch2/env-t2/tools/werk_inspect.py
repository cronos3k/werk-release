"""werk_inspect.py - my own reader for mini-v1.werk.

Written from the rules found inside the package (MANIFEST.json, spec/README.md,
spec/layouts/ENVELOPE.layout.txt, spec/layouts/restposes.layout.txt).
It does NOT import, execute or port any code from the package's loaders/.
The zip container is walked by hand (EOCD -> central directory -> local
headers); only store mode (method 0) is accepted, as the manifest declares.

Read-only: the package is opened "rb" and nothing is ever written.

usage: python -I werk_inspect.py <package.werk>
"""
import hashlib
import json
import math
import struct
import sys
import zlib


# ---------------------------------------------------------------- zip ----

def read_zip(buf):
    eocd = buf.rfind(b"PK\x05\x06")
    if eocd < 0:
        raise ValueError("no end-of-central-directory record")
    (_sig, _disk, _cd_disk, _n_here, n_total, cd_size, cd_off,
     clen) = struct.unpack_from("<IHHHHIIH", buf, eocd)
    entries = []
    p = cd_off
    for _ in range(n_total):
        if buf[p:p + 4] != b"PK\x01\x02":
            raise ValueError("bad central-directory signature at %d" % p)
        (method, crc, csize, usize, nlen, xlen, klen,
         lho) = (struct.unpack_from("<H", buf, p + 10)[0],
                 *struct.unpack_from("<III", buf, p + 16),
                 *struct.unpack_from("<HHH", buf, p + 28),
                 struct.unpack_from("<I", buf, p + 42)[0])
        name = buf[p + 46:p + 46 + nlen].decode("utf-8")
        p += 46 + nlen + xlen + klen
        if buf[lho:lho + 4] != b"PK\x03\x04":
            raise ValueError("bad local header for %s" % name)
        ln, lx = struct.unpack_from("<HH", buf, lho + 26)
        data_off = lho + 30 + ln + lx
        entries.append(dict(name=name, method=method, crc=crc, csize=csize,
                            usize=usize, header_off=lho, data_off=data_off))
    return entries, dict(eocd=eocd, cd_off=cd_off, cd_size=cd_size,
                         count=n_total, comment_len=clen)


# ------------------------------------------------- MessagePack subset ----

BANNED = {0xc1, 0xc7, 0xc8, 0xc9, 0xd4, 0xd5, 0xd6, 0xd7, 0xd8}


def mp_decode(b, i=0):
    t = b[i]
    i += 1
    if t <= 0x7f:
        return t, i
    if t >= 0xe0:
        return t - 256, i
    if 0xa0 <= t <= 0xbf:
        n = t & 0x1f
        return b[i:i + n].decode("utf-8"), i + n
    if 0x90 <= t <= 0x9f:
        return _mp_array(b, i, t & 0x0f)
    if 0x80 <= t <= 0x8f:
        return _mp_map(b, i, t & 0x0f)
    if t in BANNED:
        raise ValueError("banned MessagePack byte 0x%02x" % t)
    simple = {0xc0: None, 0xc2: False, 0xc3: True}
    if t in simple:
        return simple[t], i
    ints = {0xcc: ">B", 0xcd: ">H", 0xce: ">I", 0xcf: ">Q",
            0xd0: ">b", 0xd1: ">h", 0xd2: ">i", 0xd3: ">q",
            0xca: ">f", 0xcb: ">d"}              # BIG-endian, per section 4
    if t in ints:
        f = ints[t]
        return struct.unpack_from(f, b, i)[0], i + struct.calcsize(f)
    lens = {0xd9: ">B", 0xda: ">H", 0xdb: ">I"}
    if t in lens:
        n = struct.unpack_from(lens[t], b, i)[0]
        i += struct.calcsize(lens[t])
        return b[i:i + n].decode("utf-8"), i + n
    blens = {0xc4: ">B", 0xc5: ">H", 0xc6: ">I"}
    if t in blens:
        n = struct.unpack_from(blens[t], b, i)[0]
        i += struct.calcsize(blens[t])
        return bytes(b[i:i + n]), i + n
    if t in (0xdc, 0xdd):
        f = ">H" if t == 0xdc else ">I"
        n = struct.unpack_from(f, b, i)[0]
        return _mp_array(b, i + struct.calcsize(f), n)
    if t in (0xde, 0xdf):
        f = ">H" if t == 0xde else ">I"
        n = struct.unpack_from(f, b, i)[0]
        return _mp_map(b, i + struct.calcsize(f), n)
    raise ValueError("unknown MessagePack byte 0x%02x" % t)


def _mp_array(b, i, n):
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


# ------------------------------------------------------------ envelope ----

DTYPE = {"u8": 1, "i8": 1, "u16": 2, "i16": 2, "u32": 4, "i32": 4,
         "u64": 8, "i64": 8, "f32": 4, "f64": 8}
MAGICS = {b"WKFF": "flow field grid", b"WKRP": "settled rest poses",
          b"WKAC": "animation clip", b"WKSK": "skeleton mirror",
          b"WKEM": "style embedding + palette", b"WKPC": "point cloud",
          b"WKGS": "3D Gaussian splat"}


def read_envelope(buf):
    """ENVELOPE.layout.txt section 7, check by check."""
    checks = []
    magic = bytes(buf[0:4])
    version, header_len = struct.unpack_from("<II", buf, 4)
    checks.append(("12+header_len <= len", 12 + header_len <= len(buf)))
    header, end = mp_decode(buf, 12)
    checks.append(("header consumed exactly header_len", end == 12 + header_len))
    checks.append(("endianness == le", header.get("endianness") == "le"))
    P = 16 * math.ceil((12 + header_len) / 16)
    checks.append(("payload_origin == %d" % P, header.get("payload_origin") == P))
    checks.append(("P + payload_size == file size",
                   P + header.get("payload_size", -1) == len(buf)))
    checks.append(("padding is zero", not any(buf[12 + header_len:P])))
    sections = {}
    for s in header["sections"]:
        off, size, stride, shape = s["offset"], s["size"], s["stride"], s["shape"]
        esz = DTYPE.get(s["dtype"], stride)
        checks.append(("%s offset %% 16 == 0" % s["name"], off % 16 == 0))
        checks.append(("%s inside file" % s["name"], off + size <= len(buf)))
        if stride == esz:
            ok = size == stride * math.prod(shape)
        else:
            ok = stride >= esz * shape[-1] and size == stride * math.prod(shape[:-1])
        checks.append(("%s size/stride/shape consistent" % s["name"], ok))
        sections[s["name"]] = bytes(buf[off:off + size])
    return magic, version, header_len, header, sections, checks


def decode_wkrp(header, sections):
    """restposes.layout.txt: 32-byte pose records + f32[contact_count,3]."""
    poses = []
    raw = sections["poses"]
    for k in range(header["pose_count"]):
        w, x, y, z, cfirst, ccount, prob, area = struct.unpack_from(
            "<4fIIff", raw, 32 * k)
        poses.append(dict(quat_wxyz=(w, x, y, z), contact_first=cfirst,
                          contact_count=ccount, probability=prob,
                          support_area_m2=area))
    craw = sections["contacts"]
    contacts = [struct.unpack_from("<3f", craw, 12 * c)
                for c in range(header["contact_count"])]
    checks = [
        ("sum contact_count == header contact_count",
         sum(p["contact_count"] for p in poses) == header["contact_count"]),
        ("probabilities sorted descending",
         all(a["probability"] >= b["probability"] for a, b in zip(poses, poses[1:]))),
        ("sum probability == 1 +/- 1e-3 (trials > 0)",
         header["trials"] == 0 or abs(sum(p["probability"] for p in poses) - 1) <= 1e-3),
        ("|q| within 1e-6 of 1",
         all(abs(math.sqrt(sum(c * c for c in p["quat_wxyz"])) - 1) <= 1e-6 for p in poses)),
        ("no NaN/inf", all(math.isfinite(v) for p in poses for v in
                           (*p["quat_wxyz"], p["probability"], p["support_area_m2"]))
         and all(math.isfinite(v) for c in contacts for v in c)),
    ]
    return poses, contacts, checks


# ----------------------------------------------------------------- main ----

def main(path):
    with open(path, "rb") as f:
        buf = f.read()
    print("== container: %s (%d bytes)" % (path, len(buf)))
    entries, eocd = read_zip(buf)
    print("   zip: %d entries, central directory @0x%X (%d bytes), EOCD @0x%X"
          % (eocd["count"], eocd["cd_off"], eocd["cd_size"], eocd["eocd"]))

    files = {}
    zip_ok = True
    for e in entries:
        data = buf[e["data_off"]:e["data_off"] + e["csize"]]
        stored = e["method"] == 0 and e["csize"] == e["usize"]
        crc_ok = stored and (zlib.crc32(data) & 0xffffffff) == e["crc"]
        zip_ok &= crc_ok
        files[e["name"]] = data if stored else None
        e["crc_ok"] = crc_ok

    manifest = json.loads(files["MANIFEST.json"].decode("utf-8"))
    print("   profile %s, werk %d.%d, entity %r"
          % (manifest["profile"], manifest["werk"]["major"],
             manifest["werk"]["minor"], manifest["entity"]["name"]))

    # map every path to the node that declares it, with its meaning
    declared = {}
    for n in manifest["nodes"]:
        for v in n["versions"]:
            for fdecl in v["files"]:
                declared[fdecl["path"]] = (n["node_id"], n["type"], v.get("note", ""), fdecl)

    print("\n== contents (offset, size, crc, node -> meaning)")
    for e in entries:
        nm = e["name"]
        if nm in declared:
            nid, typ, note, _ = declared[nm]
            meaning = "%s [%s] %s" % (nid, typ, note[:70])
        elif nm == "MANIFEST.json":
            meaning = "package manifest (node graph, conventions, hashes)"
        elif nm == "SIGNATURE.json":
            meaning = "ed25519 signature chain over the manifest"
        else:
            meaning = "NOT DECLARED BY ANY NODE"
        print("  @0x%06X %7d crc %s  %-48s %s"
              % (e["data_off"], e["usize"], "ok " if e["crc_ok"] else "BAD",
                 nm, meaning))

    print("\n== integrity")
    print("  zip CRC-32 all entries: %s" % ("ok" if zip_ok else "FAILURES"))
    bad = 0
    for p, (nid, _t, _n, fdecl) in sorted(declared.items()):
        data = files.get(p)
        if data is None:
            print("  MISSING  %s (node %s)" % (p, nid)); bad += 1; continue
        h = hashlib.sha256(data).hexdigest()
        okh = h == fdecl["sha256"]
        oks = len(data) == fdecl["size"]
        if not (okh and oks):
            bad += 1
        print("  %s %s %s" % ("ok  " if okh and oks else "FAIL", p,
                              "" if okh else "sha256 %s != %s" % (h, fdecl["sha256"])))
    print("  declared files: %d, failures: %d" % (len(declared), bad))
    lic = manifest["license"]
    print("  license.sha256 matches LICENSE: %s"
          % (hashlib.sha256(files[lic["file"]]).hexdigest() == lic["sha256"]))
    sig = json.loads(files["SIGNATURE.json"].decode("utf-8"))
    msha = hashlib.sha256(files["MANIFEST.json"]).hexdigest()
    print("  SIGNATURE.json manifest_sha256 == sha256(MANIFEST.json bytes): %s (%s)"
          % (sig["manifest_sha256"] == msha, msha))
    print("  ed25519 signature: PRESENT, NOT VERIFIED (no ed25519 implementation here)")

    print("\n== binary envelopes")
    for p, data in files.items():
        if data is None or data[:4] not in MAGICS:
            continue
        magic, version, hl, header, sections, checks = read_envelope(data)
        print("  %s: magic %s (%s), version %d, header_len %d"
              % (p, magic.decode(), MAGICS[magic], version, hl))
        print("    header: " + json.dumps(header, sort_keys=True))
        if magic == b"WKRP":
            poses, contacts, c2 = decode_wkrp(header, sections)
            checks += c2
            print("    poses (%d entries):" % len(poses))
            for k, pz in enumerate(poses):
                print("      [%d] q(wxyz)=(%s) contacts %d..%d p=%.6g area=%.6g m^2"
                      % (k, ", ".join("%.8g" % c for c in pz["quat_wxyz"]),
                         pz["contact_first"],
                         pz["contact_first"] + pz["contact_count"] - 1,
                         pz["probability"], pz["support_area_m2"]))
            print("    contacts (%d points, model space, metres):" % len(contacts))
            for k, c in enumerate(contacts):
                print("      [%d] (%s)" % (k, ", ".join("%.8g" % v for v in c)))
        for name, ok in checks:
            print("    check %-46s %s" % (name, "ok" if ok else "FAIL"))


if __name__ == "__main__":
    main(sys.argv[1])
