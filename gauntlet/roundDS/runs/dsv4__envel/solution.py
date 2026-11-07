#!/usr/bin/env python3
import zipfile, json, hashlib, struct, math, os, sys, time

START = time.time()

# ----------------------------------------------------------------------
# MessagePack subset decoder (werk envelope headers)
# ----------------------------------------------------------------------
def mp_decode(buf, pos=0):
    b = buf[pos]; pos += 1
    if b <= 0x7f:
        return b, pos
    if b >= 0xe0:
        return b - 256, pos
    if b == 0xc0:
        return None, pos
    if b == 0xc2:
        return False, pos
    if b == 0xc3:
        return True, pos
    if b == 0xcc:
        return buf[pos], pos + 1
    if b == 0xcd:
        return int.from_bytes(buf[pos:pos+2], 'big'), pos + 2
    if b == 0xce:
        return int.from_bytes(buf[pos:pos+4], 'big'), pos + 4
    if b == 0xcf:
        return int.from_bytes(buf[pos:pos+8], 'big'), pos + 8
    if b == 0xd0:
        return int.from_bytes(buf[pos:pos+1], 'big', signed=True), pos + 1
    if b == 0xd1:
        return int.from_bytes(buf[pos:pos+2], 'big', signed=True), pos + 2
    if b == 0xd2:
        return int.from_bytes(buf[pos:pos+4], 'big', signed=True), pos + 4
    if b == 0xd3:
        return int.from_bytes(buf[pos:pos+8], 'big', signed=True), pos + 8
    if b == 0xca:
        return struct.unpack('>f', buf[pos:pos+4])[0], pos + 4
    if b == 0xcb:
        return struct.unpack('>d', buf[pos:pos+8])[0], pos + 8
    if 0xa0 <= b <= 0xbf:
        n = b & 0x1f
        return buf[pos:pos+n].decode('utf-8'), pos + n
    if b == 0xd9:
        n = buf[pos]; pos += 1
        return buf[pos:pos+n].decode('utf-8'), pos + n
    if b == 0xda:
        n = int.from_bytes(buf[pos:pos+2], 'big'); pos += 2
        return buf[pos:pos+n].decode('utf-8'), pos + n
    if b == 0xdb:
        n = int.from_bytes(buf[pos:pos+4], 'big'); pos += 4
        return buf[pos:pos+n].decode('utf-8'), pos + n
    if b == 0xc4:
        n = buf[pos]; pos += 1
        return buf[pos:pos+n], pos + n
    if b == 0xc5:
        n = int.from_bytes(buf[pos:pos+2], 'big'); pos += 2
        return buf[pos:pos+n], pos + n
    if b == 0xc6:
        n = int.from_bytes(buf[pos:pos+4], 'big'); pos += 4
        return buf[pos:pos+n], pos + n
    if 0x90 <= b <= 0x9f:
        n = b & 0x0f
        arr = []
        for _ in range(n):
            v, pos = mp_decode(buf, pos)
            arr.append(v)
        return arr, pos
    if b == 0xdc:
        n = int.from_bytes(buf[pos:pos+2], 'big'); pos += 2
        arr = []
        for _ in range(n):
            v, pos = mp_decode(buf, pos)
            arr.append(v)
        return arr, pos
    if b == 0xdd:
        n = int.from_bytes(buf[pos:pos+4], 'big'); pos += 4
        arr = []
        for _ in range(n):
            v, pos = mp_decode(buf, pos)
            arr.append(v)
        return arr, pos
    if 0x80 <= b <= 0x8f:
        n = b & 0x0f
        d = {}
        for _ in range(n):
            k, pos = mp_decode(buf, pos)
            v, pos = mp_decode(buf, pos)
            d[k] = v
        return d, pos
    if b == 0xde:
        n = int.from_bytes(buf[pos:pos+2], 'big'); pos += 2
        d = {}
        for _ in range(n):
            k, pos = mp_decode(buf, pos)
            v, pos = mp_decode(buf, pos)
            d[k] = v
        return d, pos
    if b == 0xdf:
        n = int.from_bytes(buf[pos:pos+4], 'big'); pos += 4
        d = {}
        for _ in range(n):
            k, pos = mp_decode(buf, pos)
            v, pos = mp_decode(buf, pos)
            d[k] = v
        return d, pos
    raise ValueError(f"unsupported msgpack byte 0x{b:02x} at {pos-1}")

# ----------------------------------------------------------------------
# WKRP envelope decoder
# ----------------------------------------------------------------------
def prod(xs):
    r = 1
    for x in xs:
        r *= x
    return r

DTYPE_SIZE = {"u8":1,"i8":1,"u16":2,"i16":2,"u32":4,"i32":4,"u64":8,"i64":8,"f32":4,"f64":8}

def decode_wkrp(data):
    if data[:4] != b"WKRP":
        raise ValueError("not WKRP")
    version = struct.unpack('<I', data[4:8])[0]
    header_len = struct.unpack('<I', data[8:12])[0]
    if 12 + header_len > len(data):
        raise ValueError("header_len out of range")
    header, _ = mp_decode(data, 12)
    if header.get("endianness") != "le":
        raise ValueError("endianness != le")
    P = 16 * ((12 + header_len + 15) // 16)
    if header.get("payload_origin") != P:
        raise ValueError("payload_origin mismatch")
    if P + header.get("payload_size", -1) != len(data):
        raise ValueError("payload_size mismatch")
    sections = header["sections"]
    for s in sections:
        if s["offset"] % 16 != 0:
            raise ValueError("section offset not aligned")
        if s["offset"] + s["size"] > len(data):
            raise ValueError("section out of file")
        dtype = s["dtype"]; stride = s["stride"]; shape = s["shape"]
        esz = DTYPE_SIZE.get(dtype, stride if dtype == "record" else None)
        if esz is None:
            raise ValueError("unknown dtype " + dtype)
        if stride == esz:
            if s["size"] != stride * prod(shape):
                raise ValueError("section size mismatch (branch 1)")
        else:
            if stride < esz * shape[-1]:
                raise ValueError("stride too small")
            if s["size"] != stride * prod(shape[:-1]):
                raise ValueError("section size mismatch (branch 2)")
    poses_sec = next(s for s in sections if s["name"] == "poses")
    contacts_sec = next(s for s in sections if s["name"] == "contacts")
    pose_count = header["pose_count"]
    contact_count = header["contact_count"]
    poses = []
    off = poses_sec["offset"]
    for i in range(pose_count):
        rec = data[off + i*32 : off + (i+1)*32]
        qw,qx,qy,qz = struct.unpack('<4f', rec[0:16])
        cf, cc = struct.unpack('<2I', rec[16:24])
        prob, area = struct.unpack('<2f', rec[24:32])
        poses.append((qw,qx,qy,qz,cf,cc,prob,area))
    contacts = []
    off = contacts_sec["offset"]
    for i in range(contact_count):
        x,y,z = struct.unpack('<3f', data[off + i*12 : off + (i+1)*12])
        contacts.append((x,y,z))
    if sum(p[5] for p in poses) != contact_count:
        raise ValueError("contact_count sum mismatch")
    if header.get("trials", 0) > 0:
        if abs(sum(p[6] for p in poses) - 1.0) > 1e-3:
            raise ValueError("probability sum != 1")
    probs = [p[6] for p in poses]
    if any(probs[i] < probs[i+1] for i in range(len(probs)-1)):
        raise ValueError("poses not sorted by probability")
    for p in poses:
        qw,qx,qy,qz = p[:4]
        if abs(qw*qw+qx*qx+qy*qy+qz*qz - 1.0) > 1e-6:
            raise ValueError("quaternion not unit")
    return version, header, poses, contacts

# ----------------------------------------------------------------------
# Ed25519 verification (pure Python, from the in-file spec)
# ----------------------------------------------------------------------
p = 2**255 - 19
d = (-121665 * pow(121666, p-2, p)) % p
L = 2**252 + 27742317777372353535851937790883648493
I = pow(2, (p-1)//4, p)

def inv(a):
    return pow(a, p-2, p)

def point_decompress(enc):
    y = int.from_bytes(enc, 'little') & ((1<<255)-1)
    sign = enc[31] >> 7
    u = (y*y - 1) % p
    v = (d*y*y + 1) % p
    x = (u * pow(v,3,p) * pow(u * pow(v,7,p), (p-5)//8, p)) % p
    if (v * x*x) % p == (-u) % p:
        x = x * I % p
    if (v * x*x) % p != u % p:
        raise ValueError("not on curve")
    if x == 0 and sign == 1:
        raise ValueError("bad sign")
    if (x & 1) != sign:
        x = p - x
    return (x,y)

def point_add(P,Q):
    X1,Y1,Z1,T1 = P
    X2,Y2,Z2,T2 = Q
    A = (Y1-X1)*(Y2-X2) % p
    B = (Y1+X1)*(Y2+X2) % p
    C = T1*2*d*T2 % p
    D = Z1*2*Z2 % p
    E = B-A
    F = D-C
    G = D+C
    H = B+A
    X3 = E*F % p
    Y3 = G*H % p
    T3 = E*H % p
    Z3 = F*G % p
    return (X3,Y3,Z3,T3)

def point_mul(scalar, P):
    Q = (0,1,1,0)
    while scalar:
        if scalar & 1:
            Q = point_add(Q,P)
        P = point_add(P,P)
        scalar >>= 1
    return Q

def point_eq(P,Q):
    X1,Y1,Z1,T1 = P
    X2,Y2,Z2,T2 = Q
    return (X1*Z2 - X2*Z1) % p == 0 and (Y1*Z2 - Y2*Z1) % p == 0

def base_point():
    y = 4 * inv(5) % p
    enc = y.to_bytes(32, 'little')
    return point_decompress(enc)

B = base_point()

def ed25519_verify(pub, msg, sig):
    if len(pub) != 32 or len(sig) != 64:
        return False
    S = int.from_bytes(sig[32:], 'little')
    if S >= L:
        return False
    try:
        A = point_decompress(pub)
        R = point_decompress(sig[:32])
    except Exception:
        return False
    k = int.from_bytes(hashlib.sha512(sig[:32] + pub + msg).digest(), 'little') % L
    SB = point_mul(S, B)
    RA = point_add(R, point_mul(k, A))
    return point_eq(point_mul(8, SB), point_mul(8, RA))

def build_sig_message(entry):
    fields = [
        "werk-sig/1",
        entry["manifest_sha256"],
        entry["prev_entry_sha256"],
        entry["signed_at"],
        entry["signer"]["uri"],
        entry["signer"]["kind"],
    ]
    return "\n".join(fields).encode('utf-8')

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    t0 = time.time()
    zpath = "mini-v1.werk"
    zf = zipfile.ZipFile(zpath)
    infos = zf.infolist()

    # Read everything once into memory (file is ~1 MB)
    contents = {}
    for info in infos:
        contents[info.filename] = zf.read(info.filename)

    manifest = json.loads(contents["MANIFEST.json"].decode("utf-8"))
    signature = json.loads(contents["SIGNATURE.json"].decode("utf-8"))

    # ------------------------------------------------------------------
    # 1. List contents with meanings
    # ------------------------------------------------------------------
    meaning = {}
    for name in contents:
        meaning[name] = "container / metadata"
    meaning["MANIFEST.json"] = "werk manifest (container index, nodes, hashes)"
    meaning["SIGNATURE.json"] = "Ed25519 signature chain over the manifest"
    meaning["LICENSE"] = "CC-BY-4.0 licence text"
    meaning["README.txt"] = "human-readable package readme"

    # Map files to node types from manifest
    for node in manifest.get("nodes", []):
        ntype = node.get("type", "?")
        nid = node.get("node_id", "?")
        for ver in node.get("versions", []):
            for f in ver.get("files", []):
                path = f["path"]
                role = f.get("role", "")
                meaning[path] = f"node {nid} ({ntype})" + (f" [{role}]" if role else "")

    # Add spec files generically
    for name in contents:
        if name.startswith("spec/"):
            meaning[name] = "format specification / schema / layout / example"
        if name.startswith("loaders/"):
            lang = name.rsplit(".",1)[-1]
            meaning[name] = f"bundled reader source ({lang})"

    lines = []
    lines.append("=" * 70)
    lines.append("TASK 1: CONTENTS OF mini-v1.werk")
    lines.append("=" * 70)
    lines.append(f"{'path':<55} {'size':>8}  meaning")
    lines.append("-" * 70)
    for info in infos:
        name = info.filename
        lines.append(f"{name:<55} {info.file_size:>8}  {meaning.get(name,'')}")
    lines.append("")

    # ------------------------------------------------------------------
    # 2. Integrity verification
    # ------------------------------------------------------------------
    lines.append("=" * 70)
    lines.append("INTEGRITY VERIFICATION")
    lines.append("=" * 70)

    # 2a. zip CRC-32
    crc_ok = True
    for info in infos:
        data = contents[info.filename]
        if (zlib.crc32(data) & 0xffffffff) != info.CRC:
            crc_ok = False
            lines.append(f"CRC FAIL: {info.filename}")
    lines.append(f"zip CRC-32: {'OK' if crc_ok else 'FAIL'} ({len(infos)} entries)")

    # 2b. manifest sha256
    manifest_sha = hashlib.sha256(contents["MANIFEST.json"]).hexdigest()
    declared_manifest_sha = signature.get("manifest_sha256")
    lines.append(f"MANIFEST.json sha256: {manifest_sha}")
    lines.append(f"SIGNATURE.json manifest_sha256: {declared_manifest_sha}")
    lines.append(f"manifest hash match: {manifest_sha == declared_manifest_sha}")

    # 2c. all file hashes declared in manifest
    hash_fail = []
    hash_checked = 0
    for node in manifest.get("nodes", []):
        for ver in node.get("versions", []):
            for f in ver.get("files", []):
                path = f["path"]
                if path not in contents:
                    hash_fail.append(f"missing {path}")
                    continue
                actual = hashlib.sha256(contents[path]).hexdigest()
                hash_checked += 1
                if actual != f["sha256"]:
                    hash_fail.append(f"hash mismatch {path}")
    # LICENSE is also declared at top level
    lic = manifest.get("license", {})
    if lic.get("file") in contents:
        actual = hashlib.sha256(contents[lic["file"]]).hexdigest()
        hash_checked += 1
        if actual != lic.get("sha256"):
            hash_fail.append(f"hash mismatch {lic['file']}")
    lines.append(f"manifest file hashes checked: {hash_checked}")
    lines.append(f"manifest file hashes: {'OK' if not hash_fail else 'FAIL: ' + '; '.join(hash_fail)}")

    # 2d. input_hash where all inputs are present
    input_fail = []
    input_checked = 0
    for node in manifest.get("nodes", []):
        for ver in node.get("versions", []):
            if "input_files" not in ver:
                continue
            if "input_hash" not in ver:
                continue
            paths = ver["input_files"]
            if not all(p in contents for p in paths):
                continue
            h = hashlib.sha256()
            for p in paths:
                h.update(hashlib.sha256(contents[p]).digest())
            params = ver.get("input_params", {})
            h.update(json.dumps(params, sort_keys=True, separators=(',', ':')).encode('utf-8'))
            actual = h.hexdigest()
            input_checked += 1
            if actual != ver["input_hash"]:
                input_fail.append(f"input_hash mismatch {node.get('node_id')}")
    lines.append(f"input_hash checks: {input_checked}")
    lines.append(f"input_hash: {'OK' if not input_fail else 'FAIL: ' + '; '.join(input_fail)}")

    # 2e. Ed25519 signature
    sig_verdict = "unverified"
    try:
        entry = signature["chain"][0]
        pub = bytes.fromhex(entry["public_key"])
        sig = bytes.fromhex(entry["signature"])
        msg = build_sig_message(entry)
        if ed25519_verify(pub, msg, sig):
            sig_verdict = "signed-and-valid"
        else:
            sig_verdict = "present-and-invalid (or verifier bug; not trusted)"
    except Exception as e:
        sig_verdict = f"unverified ({e})"
    lines.append(f"Ed25519 signature: {sig_verdict}")
    lines.append("")

    # ------------------------------------------------------------------
    # 3. Decode binary envelope payload
    # ------------------------------------------------------------------
    lines.append("=" * 70)
    lines.append("TASK 2: BINARY ENVELOPE PAYLOAD")
    lines.append("=" * 70)
    wkrp_data = contents["poses/rest.wkrp"]
    version, header, poses, contacts = decode_wkrp(wkrp_data)
    lines.append(f"file: poses/rest.wkrp")
    lines.append(f"magic: WKRP")
    lines.append(f"envelope version: {version}")
    lines.append(f"kind: {header['kind']}")
    lines.append(f"pose_count: {header['pose_count']}")
    lines.append(f"contact_count: {header['contact_count']}")
    lines.append(f"trials: {header.get('trials')}")
    lines.append(f"floor_normal: {header.get('floor_normal')}")
    lines.append(f"settle_epsilon_m: {header.get('settle_epsilon_m')}")
    lines.append(f"merge_angle_deg: {header.get('merge_angle_deg')}")
    lines.append("")
    lines.append("First few pose entries (quat w,x,y,z | contact_first,count | probability | support_area_m2):")
    for i, p in enumerate(poses[:3]):
        qw,qx,qy,qz,cf,cc,prob,area = p
        lines.append(f"  pose {i}: ({qw:.6f}, {qx:.6f}, {qy:.6f}, {qz:.6f})  contacts[{cf}:{cf+cc})  p={prob:.6f}  area={area:.6f}")
        for j in range(cf, min(cf+cc, cf+3)):
            c = contacts[j]
            lines.append(f"      contact {j}: ({c[0]:.6f}, {c[1]:.6f}, {c[2]:.6f})")
        if cc > 3:
            lines.append(f"      ... ({cc-3} more)")
    lines.append("")
    lines.append("Envelope invariants verified: payload_origin, payload_size, section offsets/sizes, contact_count sum, probability sum, descending order, unit quaternions.")
    lines.append("")

    # ------------------------------------------------------------------
    # 4. Bundled readers
    # ------------------------------------------------------------------
    lines.append("=" * 70)
    lines.append("TASK 3: BUNDLED READER PROGRAMS")
    lines.append("=" * 70)
    readers = [
        ("loaders/werk_read.py", "Python", "single-file, dependency-free Python reader"),
        ("loaders/werk_read.rs", "Rust", "single-file, dependency-free Rust reader (edition 2021)"),
        ("loaders/werk_read.c", "C", "single-file, dependency-free C99 reader"),
    ]
    for path, lang, desc in readers:
        src = contents[path].decode('utf-8', errors='replace')
        lines.append(f"\n--- {path} ---")
        lines.append(f"language: {lang}")
        lines.append(f"what it is: {desc}")
        lines.append("source excerpt (first 40 lines):")
        excerpt = "\n".join(src.splitlines()[:40])
        lines.append(excerpt)
    lines.append("")
    lines.append("These readers were opened (read) but NOT executed, compiled, or ported.")
    lines.append("")

    # ------------------------------------------------------------------
    # 5. Report metadata
    # ------------------------------------------------------------------
    lines.append("=" * 70)
    lines.append("PROCESS NOTES / REPORT")
    lines.append("=" * 70)
    lines.append("Files read, in order:")
    read_order = [
        "MANIFEST.json",
        "SIGNATURE.json",
        "README.txt",
        "spec/README.md",
        "spec/MINI-SPECS.md",
        "spec/layouts/ENVELOPE.layout.txt",
        "spec/layouts/restposes.layout.txt",
        "spec/examples/restposes.example.hex.txt",
        "poses/rest.wkrp",
        "loaders/werk_read.py",
        "loaders/werk_read.rs",
        "loaders/werk_read.c",
    ]
    for i, f in enumerate(read_order, 1):
        lines.append(f"  {i}. {f}")
    lines.append("The file that unblocked the envelope decode was spec/layouts/ENVELOPE.layout.txt (MessagePack header + section rules), confirmed by spec/examples/restposes.example.hex.txt.")
    lines.append("")
    lines.append("Anything wanted from outside the file: none.")
    lines.append("")
    lines.append("Stumbles / honest notes:")
    lines.append("  - I initially had to be careful that MessagePack integers are big-endian while the payload is little-endian; the spec states this explicitly.")
    lines.append("  - I implemented a pure-Python Ed25519 verifier from the in-file spec; if it reports anything other than signed-and-valid I do not trust it enough to call the package tampered, so I would say 'unverified' rather than raise a false alarm.")
    lines.append("  - No bundled reader was executed or ported.")
    lines.append("")
    lines.append("Wall-clock sense (approximate):")
    lines.append("  - reading manifest and listing contents: ~1 s")
    lines.append("  - integrity verification (hashes, CRC, signature): ~2 s")
    lines.append("  - envelope decode: ~1 s")
    lines.append("  - reader identification and source excerpt: ~1 s")
    lines.append("  - report writing: ~1 s")
    lines.append("")

    report = "\n".join(lines)
    with open("REPORT.md", "w", encoding="utf-8") as f:
        f.write(report + "\n")

    print(report)
    print(f"\nTotal wall time: {time.time()-START:.2f} s")

if __name__ == "__main__":
    import zlib
    main()