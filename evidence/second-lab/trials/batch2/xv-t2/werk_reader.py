#!/usr/bin/env python3
"""werk_reader.py - an independent reader for werk 3d-entity/1 packages.

Written from the package's own spec/SPEC.md and spec/MINI-SPECS.md only.
It does not import, run or port the loaders/ bundled inside the package.

    python -I werk_reader.py crate-v1.werk [outdir]

Steps (SPEC.md section 10):
  1. open the store-mode zip (MINI-SPECS 5), with zip64 detection (5.5)
  2. read MANIFEST.json, structural check, werk.major
  3. check conventions against what this reader supports (SPEC 2 / 10.1)
  4. verify SIGNATURE.json chain with a from-spec Ed25519 (MINI-SPECS 12)
  5-6. walk nodes, active version, check size + sha256 of every file
  + license.sha256, spec_sha256 (SPEC 2), input_hash (MINI-SPECS 11)
  + "nothing floats" / one-node-per-path (SPEC 2)
  then list the graph with meanings and extract primary.mesh and
  primary.sound via the SPEC 2.1 payload resolution rules.
Exit status per SPEC 10.2: 0 ok, 1 errors, 2 container refusal.
"""
import hashlib
import json
import os
import struct
import sys
import zlib

# ---------------------------------------------------------------- reporting
REPORT = []


def report(code, severity, subject, detail=""):
    REPORT.append((code, severity, subject, detail))
    print(f"  [{severity:5}] {code}: {subject}" + (f" - {detail}" if detail else ""))


# ---------------------------------------------------------------- zip (MINI-SPECS 5)
class ContainerRefused(Exception):
    pass


class Zip:
    def __init__(self, path):
        with open(path, "rb") as f:
            self.data = f.read()
        d = self.data
        n = len(d)
        lo = max(0, n - 22 - 65535)
        eocd = -1
        for off in range(n - 22, lo - 1, -1):          # MINI-SPECS 5.1
            if d[off:off + 4] == b"PK\x05\x06":
                eocd = off
                break
        if eocd < 0:
            raise ContainerRefused("no EOCD record: not a zip")
        (_, disk, cd_disk, n_here, n_total, cd_size, cd_off, clen) = struct.unpack_from("<IHHHHIIH", d, eocd)
        # zip64 detection is mandatory even for zip32-only readers (5.5)
        if (n_here == 0xFFFF or n_total == 0xFFFF or cd_size == 0xFFFFFFFF or cd_off == 0xFFFFFFFF
                or (eocd >= 20 and d[eocd - 20:eocd - 16] == b"PK\x06\x07")):
            raise ContainerRefused("zip64-unsupported")
        self.entries = {}
        self.order = []
        p = cd_off
        for _ in range(n_total):                        # MINI-SPECS 5.2
            if d[p:p + 4] != b"PK\x01\x02":
                raise ContainerRefused(f"bad central directory signature at {p}")
            (flags, method, crc, csize, usize, nl, ml, kl, lho) = (
                struct.unpack_from("<H", d, p + 8)[0], struct.unpack_from("<H", d, p + 10)[0],
                *struct.unpack_from("<IIIHHH", d, p + 16), struct.unpack_from("<I", d, p + 42)[0])
            raw = d[p + 46:p + 46 + nl]
            name = raw.decode("utf-8" if flags & 0x800 else "cp437")
            p += 46 + nl + ml + kl
            if usize == 0xFFFFFFFF or csize == 0xFFFFFFFF or lho == 0xFFFFFFFF:
                raise ContainerRefused("zip64-unsupported")
            self.entries[name] = dict(method=method, crc=crc, csize=csize, usize=usize, lho=lho, flags=flags)
            self.order.append(name)

    def names(self):
        return list(self.order)

    def read(self, name):
        """Return bytes, or raise ValueError with a reason (method 8 unsupported, CRC)."""
        e = self.entries[name]
        d = self.data
        lho = e["lho"]
        if d[lho:lho + 4] != b"PK\x03\x04":                # MINI-SPECS 5.3
            raise ValueError("local header signature missing")
        nl, ml = struct.unpack_from("<HH", d, lho + 26)  # re-read n, m from LOCAL header
        start = lho + 30 + nl + ml
        blob = d[start:start + e["csize"]]
        if e["method"] == 0:
            out = blob
        elif e["method"] == 8:
            # The spec says a reader SHOULD support deflate; Python's zlib is stdlib.
            out = zlib.decompress(blob, -15)
        else:
            raise ValueError(f"compression method {e['method']} unsupported")
        if len(out) != e["usize"]:
            raise ValueError("uncompressed size mismatch")
        if zlib.crc32(out) & 0xFFFFFFFF != e["crc"]:
            raise ValueError("zip CRC-32 mismatch")
        return out

    def local_end(self, name):
        e = self.entries[name]
        nl, ml = struct.unpack_from("<HH", self.data, e["lho"] + 26)
        return e["lho"] + 30 + nl + ml + e["csize"]


# ---------------------------------------------------------------- Ed25519 verify (MINI-SPECS 12)
P = 2 ** 255 - 19
L = 2 ** 252 + 27742317777372353535851937790883648493


def inv(a):
    return pow(a, P - 2, P)


D = (-121665 * inv(121666)) % P
I = pow(2, (P - 1) // 4, P)


def decompress(b):
    if len(b) != 32:
        return None
    yy = int.from_bytes(b, "little")
    sign = yy >> 255
    y = yy & ((1 << 255) - 1)
    if y >= P:
        return None
    u = (y * y - 1) % P
    v = (D * y * y + 1) % P
    x = (u * pow(v, 3, P) * pow(u * pow(v, 7, P), (P - 5) // 8, P)) % P
    if (v * x * x) % P == (-u) % P:
        x = (x * I) % P
    if (v * x * x) % P != u % P:
        return None
    if x == 0 and sign == 1:
        return None
    if (x & 1) != sign:
        x = P - x
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


def smul(k, pt):
    q = (0, 1, 1, 0)
    while k:
        if k & 1:
            q = padd(q, pt)
        pt = padd(pt, pt)
        k >>= 1
    return q


def peq(a, b):
    return (a[0] * b[2] - b[0] * a[2]) % P == 0 and (a[1] * b[2] - b[1] * a[2]) % P == 0


# base point: y = 4/5, even x (the decompression with sign bit 0)
_By = (4 * inv(5)) % P
BASE = decompress(_By.to_bytes(32, "little"))


def ed25519_verify(pub, msg, sig):
    if len(sig) != 64:
        return False
    S = int.from_bytes(sig[32:], "little")
    if S >= L:
        return False
    A = decompress(pub)
    R = decompress(sig[:32])
    if A is None or R is None:
        return False
    k = int.from_bytes(hashlib.sha512(sig[:32] + pub + msg).digest(), "little") % L
    lhs = smul(8, smul(S, BASE))
    rhs = smul(8, padd(R, smul(k, A)))
    return peq(lhs, rhs)


def ed25519_selftest():
    # RFC 8032 test 1, as printed in MINI-SPECS 12
    pub = bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
    sig = bytes.fromhex("e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b")
    good = ed25519_verify(pub, b"", sig)
    bad = ed25519_verify(pub, b"x", sig)
    return good and not bad


def sha256_selftest():
    return (hashlib.sha256(b"abc").hexdigest() == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
            and hashlib.sha512(b"abc").hexdigest().startswith("ddaf35a193617aba"))


def sig_message(entry):
    # MINI-SPECS 12.1 / SPEC 6
    fields = ["werk-sig/1", entry["manifest_sha256"], entry["prev_entry_sha256"], entry["signed_at"],
              entry["signer"]["uri"], entry["signer"]["kind"]]
    for f in fields:
        if "\n" in f:
            raise ValueError("field contains LF")
    return "\n".join(fields).encode("utf-8")


def verify_chain(sigdoc, manifest_bytes):
    """Returns one of the four fixed tokens (SPEC 10 step 4)."""
    try:
        chain = sigdoc["chain"]
        if sigdoc.get("algorithm") != "ed25519":
            report("signature-unverified", "warn", "SIGNATURE.json", f"algorithm {sigdoc.get('algorithm')!r} unsupported")
            return "unverified"
        prev = "0" * 64
        for i, e in enumerate(chain):
            if e.get("prev_entry_sha256") != prev:
                report("signature-invalid", "error", f"chain[{i}]", "prev_entry_sha256 mismatch")
                return "present-and-invalid"
            msg = sig_message(e)
            if not ed25519_verify(bytes.fromhex(e["public_key"]), msg, bytes.fromhex(e["signature"])):
                report("signature-invalid", "error", f"chain[{i}]", "Ed25519 signature does not verify")
                return "present-and-invalid"
            print(f"    chain[{i}] signer={e['signer']['uri']} msg_sha256={hashlib.sha256(msg).hexdigest()} ok")
            prev = hashlib.sha256(e["signature"].encode("utf-8")).hexdigest()
        actual = hashlib.sha256(manifest_bytes).hexdigest()
        if chain[-1]["manifest_sha256"] != actual:
            report("signature-invalid", "error", "SIGNATURE.json", f"last entry anchors {chain[-1]['manifest_sha256']}, MANIFEST.json is {actual}")
            return "present-and-invalid"
        if sigdoc.get("manifest_sha256") != actual:
            report("signature-invalid", "error", "SIGNATURE.json", "top-level manifest_sha256 disagrees with MANIFEST.json")
            return "present-and-invalid"
        return "signed-and-valid"
    except (KeyError, TypeError, ValueError) as ex:
        # could not build the message: that is our failure, not tampering (MINI-SPECS 12.2)
        report("signature-unverified", "warn", "SIGNATURE.json", f"could not evaluate: {ex}")
        return "unverified"


# ---------------------------------------------------------------- JSON (MINI-SPECS 3)
def strict_json(b, what):
    if b.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"{what}: UTF-8 BOM is forbidden")
    text = b.decode("utf-8")

    def no_dupes(pairs):
        d = {}
        for k, v in pairs:
            if k in d:
                raise ValueError(f"{what}: duplicate key {k!r}")
            d[k] = v
        return d

    def no_const(c):
        raise ValueError(f"{what}: non-finite number {c}")
    return json.loads(text, object_pairs_hook=no_dupes, parse_constant=no_const)


def canonical_json(v):
    # MINI-SPECS 3 "Canonical JSON (for hashing only)"
    if isinstance(v, dict):
        items = sorted(v.items(), key=lambda kv: kv[0].encode("utf-8"))
        return "{" + ",".join(canonical_json(k) + ":" + canonical_json(x) for k, x in items) + "}"
    if isinstance(v, list):
        return "[" + ",".join(canonical_json(x) for x in v) + "]"
    if isinstance(v, str):
        out = ['"']
        short = {'"': '\\"', "\\": "\\\\", "\b": "\\b", "\f": "\\f", "\n": "\\n", "\r": "\\r", "\t": "\\t"}
        for ch in v:
            if ch in short:
                out.append(short[ch])
            elif ord(ch) < 0x20:
                out.append("\\u%04x" % ord(ch))
            else:
                out.append(ch)
        return "".join(out) + '"'
    if v is True:
        return "true"
    if v is False:
        return "false"
    if v is None:
        return "null"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if v.is_integer() and abs(v) < 2 ** 53:   # interpretation: "integers written without a decimal point"
            return str(int(v))
        return repr(v)
    raise TypeError(type(v))


# ---------------------------------------------------------------- what this reader supports
SUPPORTED_MAJOR = {1}
SUPPORTED_CONVENTIONS = {  # SPEC 2, the 3d-entity/1 set
    "endianness": "le", "units_per_meter": 1.0, "length_unit": "metre", "angle_unit": "radian",
    "time_unit": "second", "mass_unit": "kilogram", "up_axis": "y", "forward_axis": "-z",
    "right_axis": "+x", "handedness": "right", "winding": "ccw", "quat_order": "wxyz",
    "oct_encoding_pole": "y", "sh_l1_order": ["dc", "y", "z", "x"], "color_space_default": "srgb",
    "uv_origin": "top-left", "alignment_bytes": 16, "text_encoding": "utf-8", "id_case": "kebab-case",
    "hash_algorithm": "sha256", "signature_algorithm": "ed25519",
}

# Node-type meanings, from spec/README.md and SPEC.md section 3.
TYPE_MEANING = {
    "core.spec": "the format specification travelling inside the file (law 2)",
    "core.loader": "a bundled single-file reader program (inert data here - never run)",
    "core.license": "full licence text, embedded",
    "core.readme": "human-readable one-pager",
    "core.geom.source": "archival source mesh (GLB); the anchor derived nodes hash against",
    "core.geom.game": "runtime mesh (GLB) with required POSITION+NORMAL",
    "core.geom.lod": "level-of-detail mesh (GLB)",
    "core.material": "PBR material parameters (JSON)",
    "core.phys.bounds": "bounding volumes in model space (JSON)",
    "core.audio.package": "the sound-world index: descriptions, plan, takes, gate scores (JSON)",
    "core.audio.effect": "one sound effect: best take + variations + raw + descriptor (WAV+JSON)",
    "core.audio.ambience": "one ambience loop: takes + descriptor (WAV+JSON)",
    "core.semantics": "facet tags, palette, search text (JSON)",
    "core.props": "simulation properties, each value with unit and epistemic stamp (JSON)",
    "core.provenance": "producers, inputs, models, gates (JSON)",
}
PAYLOAD_ROLE = {"core.audio.effect": "best", "core.audio.ambience": "best", "core.imposter": "atlas",
                "core.recipe": "record"}


def resolve_payload(node, version, quiet=False):
    """SPEC 2.1 normative resolution. Returns (path, rule) or (None, candidates).
    quiet=True is for the listing, where nobody has asked for "the one payload"."""
    files = version["files"]
    paths = [f["path"] for f in files]
    if "payload_file" in version:
        pf = version["payload_file"]
        if paths.count(pf) == 1:
            return pf, "rule 1: payload_file"
        report("payload-file-invalid", "warn", node["node_id"], f"payload_file {pf!r} not exactly one of files[]")
    if len(files) == 1:
        return paths[0], "rule 2: single file"
    pl = [f["path"] for f in files if f.get("role") == "payload"]
    if len(pl) == 1:
        return pl[0], "rule 3: role=payload"
    role = PAYLOAD_ROLE.get(node["type"])
    if role:
        c = [f["path"] for f in files if f.get("role") == role and f.get("role") != "descriptor"]
        if len(c) == 1:
            return c[0], f"rule 4: type role={role}"
    if not quiet:
        report("payload-file-ambiguous", "warn", node["node_id"], f"candidates {paths}")
    return None, paths


# ---------------------------------------------------------------- payload sanity parsers
def glb_info(b):
    if b[:4] != b"glTF":
        raise ValueError("not GLB magic")
    ver, total = struct.unpack_from("<II", b, 4)
    if ver != 2 or total != len(b):
        raise ValueError(f"GLB version {ver}, length field {total} vs {len(b)}")
    clen, ctype = struct.unpack_from("<II", b, 12)
    if ctype != 0x4E4F534A:
        raise ValueError("first chunk not JSON")
    doc = json.loads(b[20:20 + clen].decode("utf-8"))
    off = 20 + clen
    binlen = 0
    if off < len(b):
        binlen, btype = struct.unpack_from("<II", b, off)
        if btype != 0x004E4942:
            raise ValueError("second chunk not BIN")
    info = {"bin_bytes": binlen, "primitives": []}
    for m in doc.get("meshes", []):
        for pr in m["primitives"]:
            acc = doc["accessors"]
            idx = acc[pr["indices"]] if "indices" in pr else None
            info["primitives"].append({
                "mode": pr.get("mode", 4),
                "attributes": {k: f"{acc[v]['type']}/{acc[v]['componentType']} x{acc[v]['count']}" for k, v in pr["attributes"].items()},
                "indices": f"{idx['componentType']} x{idx['count']}" if idx else None,
                "triangles": idx["count"] // 3 if idx else None,
                "pos_min": acc[pr["attributes"]["POSITION"]].get("min"),
                "pos_max": acc[pr["attributes"]["POSITION"]].get("max"),
            })
    return info


def wav_info(b):
    if b[:4] != b"RIFF" or b[8:12] != b"WAVE":
        raise ValueError("not RIFF/WAVE")
    p = 12
    fmt = None
    data_size = None
    while p + 8 <= len(b):
        cid = b[p:p + 4]
        size = struct.unpack_from("<I", b, p + 4)[0]
        if cid == b"fmt ":
            af, ch, sr, br, ba, bps = struct.unpack_from("<HHIIHH", b, p + 8)
            fmt = dict(format={1: "PCM", 3: "float", 0xFFFE: "extensible"}.get(af, af), channels=ch,
                       sample_rate=sr, block_align=ba, bits=bps)
        elif cid == b"data":
            data_size = size
        p += 8 + size + (size & 1)      # pad byte rule
    if fmt is None or data_size is None:
        raise ValueError("missing fmt or data chunk")
    fmt["frames"] = data_size // fmt["block_align"]
    fmt["seconds"] = round(fmt["frames"] / fmt["sample_rate"], 4)
    return fmt


# ---------------------------------------------------------------- main
def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    path = argv[1]
    outdir = argv[2] if len(argv) > 2 else "extracted"
    print(f"== werk_reader: {path}")
    print("\n-- self-tests (MINI-SPECS 11/12 vectors)")
    st_hash, st_ed = sha256_selftest(), ed25519_selftest()
    print(f"  sha256/sha512 vectors: {'ok' if st_hash else 'FAIL'};  Ed25519 RFC 8032 vector 1: {'ok' if st_ed else 'FAIL'}")

    # 1. container
    print("\n-- 1. container")
    try:
        z = Zip(path)
    except ContainerRefused as ex:
        report("container-refused", "error", path, str(ex))
        return 2
    names = z.names()
    methods = {z.entries[n]["method"] for n in names}
    print(f"  {len(names)} entries, compression methods {sorted(methods)}, size {len(z.data)} bytes")
    for n in names:
        if n.startswith("/") or ".." in n.split("/") or ":" in n or "\\" in n:
            report("unsafe-entry-name", "error", n)

    # 2. manifest
    print("\n-- 2. MANIFEST.json")
    if "MANIFEST.json" not in z.entries:
        report("manifest-absent", "error", "MANIFEST.json")
        return 2
    try:
        mbytes = z.read("MANIFEST.json")
        man = strict_json(mbytes, "MANIFEST.json")
    except ValueError as ex:
        report("manifest-unparseable", "error", "MANIFEST.json", str(ex))
        return 2
    if not isinstance(man.get("nodes"), list) or not all(isinstance(v.get("files"), list) for n in man["nodes"] for v in n.get("versions", [])):
        report("manifest-structurally-invalid", "error", "MANIFEST.json")
        return 2
    print(f"  sha256 {hashlib.sha256(mbytes).hexdigest()}")
    print(f"  werk {man['werk']['major']}.{man['werk']['minor']}  profile {man['profile']}")
    print(f"  entity: {man['entity']['name']} ({man['entity']['uuid']})")
    print(f"  summary: {man['entity']['summary']}")
    if man["werk"]["major"] not in SUPPORTED_MAJOR:
        report("unsupported-major", "error", "werk.major", str(man["werk"]["major"]))
    if man.get("profile") != "3d-entity/1":
        report("unsupported-profile", "warn", man.get("profile"), "payload meaning not claimed; still listing and hashing")
    if man.get("manifest_schema"):
        print(f"  manifest_schema: {man['manifest_schema']}")
    print("  (structural check only - JSON Schema validation NOT performed; this is a bootstrap-class reader)")

    # 3. conventions
    print("\n-- 3. conventions")
    conv = man.get("conventions", {})
    bad = []
    for k, want in SUPPORTED_CONVENTIONS.items():
        if k not in conv:
            bad.append(k)
            report("convention-missing", "error", k)
        elif conv[k] != want:
            bad.append(k)
            report("unsupported-convention", "error", k, f"{conv[k]!r} (supported: {want!r})")
    for k in conv:
        if k not in SUPPORTED_CONVENTIONS:
            report("unknown-convention", "info", k, repr(conv[k]))
    print(f"  {len(SUPPORTED_CONVENTIONS) - len(bad)}/{len(SUPPORTED_CONVENTIONS)} conventions supported")

    # 4. signature
    print("\n-- 4. signature chain (SPEC 6)")
    if "SIGNATURE.json" not in z.entries:
        sig_state = "absent"
        report("signature-absent", "warn", "SIGNATURE.json")
    elif not st_ed:
        sig_state = "unverified"
        report("signature-unverified", "warn", "SIGNATURE.json", "Ed25519 self-test failed, not trusting own verifier")
    else:
        try:
            sigdoc = strict_json(z.read("SIGNATURE.json"), "SIGNATURE.json")
            sig_state = verify_chain(sigdoc, mbytes)
            for e in sigdoc.get("chain", []):
                print(f"    note: {e.get('note', '')}")
        except ValueError as ex:
            sig_state = "present-and-invalid"
            report("signature-invalid", "error", "SIGNATURE.json", f"unreadable: {ex}")
    print(f"  signature state: {sig_state}")

    # 5-6. graph walk + hashes
    print("\n-- 5/6. node graph and file hashes")
    owner = {}
    dead = {}
    file_sha = {}
    cache = {}

    def get(p):
        if p not in cache:
            cache[p] = z.read(p)
        return cache[p]

    nodes = {n["node_id"]: n for n in man["nodes"]}
    active_ver = {}
    for n in man["nodes"]:
        nid = n["node_id"]
        vers = {v["v"]: v for v in n["versions"]}
        if n["active"] not in vers:
            report("active-invalid", "warn", nid, f"active={n['active']}")
            v = vers[max(vers)]
        else:
            v = vers[n["active"]]
        active_ver[nid] = v
        for vv in n["versions"]:
            for f in vv["files"]:
                o = owner.setdefault(f["path"], nid)
                if o != nid:
                    report("path-claimed-twice", "error", f["path"], f"{o} and {nid}")
        for f in v["files"]:
            p = f["path"]
            if p not in z.entries:
                report("file-missing", "error", nid, p)
                dead.setdefault(nid, []).append(p)
                continue
            try:
                b = get(p)
            except ValueError as ex:
                report("entry-unreadable", "error", nid, f"{p}: {ex}")
                dead.setdefault(nid, []).append(p)
                continue
            h = hashlib.sha256(b).hexdigest()
            file_sha[p] = h
            if len(b) != f["size"]:
                report("size-mismatch", "error", nid, f"{p}: declared {f['size']} actual {len(b)}")
                dead.setdefault(nid, []).append(p)
            elif h != f["sha256"]:
                report("hash-mismatch", "error", nid, f"{p}: declared {f['sha256']} actual {h}")
                dead.setdefault(nid, []).append(p)
    nfiles = sum(len(active_ver[n]["files"]) for n in active_ver)
    print(f"  {len(nodes)} nodes, {nfiles} declared files, {nfiles - sum(len(v) for v in dead.values())} hash+size OK")

    # requires edges into dead nodes kill the source (SPEC 5)
    changed = True
    while changed:
        changed = False
        for n in man["nodes"]:
            if n["node_id"] in dead:
                continue
            for e in n["edges"]:
                if e["kind"] == "requires" and (e["to"] in dead or e["to"] not in nodes):
                    dead[n["node_id"]] = [f"requires dead/missing node {e['to']}"]
                    report("requires-dead-node", "error", n["node_id"], e["to"])
                    changed = True

    # nothing floats (SPEC 2)
    floating = [p for p in names if p not in owner and p not in ("MANIFEST.json", "SIGNATURE.json") and not p.endswith("/")]
    for p in floating:
        report("floating-entry", "warn", p, "in container but in no node's files[]")
    if not floating:
        print("  nothing floats: every entry except MANIFEST.json/SIGNATURE.json belongs to exactly one node")

    # license
    lic = man.get("license", {})
    if lic.get("file") in file_sha or lic.get("file") in z.entries:
        h = hashlib.sha256(get(lic["file"])).hexdigest()
        print(f"  license {lic['file']} ({lic.get('spdx_id')}): {'OK' if h == lic['sha256'] else 'MISMATCH'}")
        if h != lic["sha256"]:
            report("hash-mismatch", "error", "license", lic["file"])

    # spec_sha256 (SPEC 2, S-29)
    spec_paths = sorted({p for p in owner if p.startswith("spec/")}, key=lambda s: s.encode("utf-8"))
    acc = b""
    for p in spec_paths:
        acc += p.encode("utf-8") + b"\n" + bytes.fromhex(file_sha.get(p) or hashlib.sha256(get(p)).hexdigest()) + b"\n"
    spec_h = hashlib.sha256(acc).hexdigest()
    ok = spec_h == man.get("spec_sha256")
    print(f"  spec_sha256 over {len(spec_paths)} spec files: {'OK' if ok else 'MISMATCH'} ({spec_h})")
    if not ok:
        report("spec-sha256-mismatch", "error", "spec_sha256", f"declared {man.get('spec_sha256')} computed {spec_h}")

    # input_hash (MINI-SPECS 11, "What gets hashed")
    ih_ok = ih_n = 0
    for n in man["nodes"]:
        for v in n["versions"]:
            if "input_hash" not in v:
                if v.get("epistemic") in ("measured", "inferred"):
                    report("input-hash-missing", "warn", n["node_id"], f"v{v['v']} is {v['epistemic']}")
                continue
            ih_n += 1
            h = hashlib.sha256()
            try:
                for p in v.get("input_files", []):
                    h.update(bytes.fromhex(file_sha.get(p) or hashlib.sha256(get(p)).hexdigest()))
            except KeyError as ex:
                report("input-file-missing", "warn", n["node_id"], str(ex))
                continue
            h.update(canonical_json(v.get("input_params") or {}).encode("utf-8"))
            if h.hexdigest() == v["input_hash"]:
                ih_ok += 1
            else:
                report("input-hash-stale", "warn", n["node_id"], f"v{v['v']} declared {v['input_hash']} computed {h.hexdigest()}")
    print(f"  input_hash: {ih_ok}/{ih_n} versions current")

    # container hints (SPEC 1): report only, never damage
    cont = man.get("container", {})
    pv = man.get("primary", {}).get("sound")
    tier = cont.get("preview_tier") or ["MANIFEST.json", "SIGNATURE.json", "LICENSE", "README.txt", "loaders/", "spec/", "semantics/", "imposters/"]
    tier_files = [p for p in names if any(p == t or (t.endswith("/") and p.startswith(t)) for t in tier)]
    if pv and pv in nodes:
        tier_files.append(resolve_payload(nodes[pv], active_ver[pv])[0])
    tier_end = max(z.local_end(p) for p in tier_files if p in z.entries)
    print(f"  preview_prefix_bytes (hint): declared {cont.get('preview_prefix_bytes')}, recomputed end of preview tier {tier_end}")

    # 7/8. listing with meanings
    print("\n-- 7/8. node graph with meanings")
    for n in man["nodes"]:
        nid = n["node_id"]
        v = active_ver[nid]
        meaning = TYPE_MEANING.get(n["type"])
        if meaning is None:
            meaning = "extension node (x.*): skipped for interpretation, hashes still checked" if n["type"].startswith("x.") else "UNKNOWN type: skipped"
            report("node-skipped-unknown-type" if not n["type"].startswith("x.") else "node-extension-skipped", "info", nid, n["type"])
        status = "DEAD" if nid in dead else "live"
        print(f"\n  {nid}  <{n['type']}>  [{status}]  v{v['v']}/{len(n['versions'])}  {v['epistemic']}"
              + (f" conf={v['confidence']}" if "confidence" in v else "")
              + (f"  part={n['part_id']}" if n.get("part_id") else ""))
        print(f"     means : {meaning}")
        print(f"     note  : {v['note']}")
        prod = v["producer"]
        print(f"     made by: {prod.get('tool')} {prod.get('version')}" + (f" (model {prod['model']})" if prod.get("model") else ""))
        for e in n["edges"]:
            print(f"     edge  : --{e['kind']}/{e.get('role', '')}--> {e['to']}")
        if len(v["files"]) > 1:
            pf, rule = resolve_payload(n, v, quiet=True)
            print(f"     payload: {pf}  ({rule})" if pf else f"     payload: none single - a {len(v['files'])}-file collection")
        for f in v["files"][:6]:
            print(f"       - {f['path']}  {f['size']} B" + (f"  role={f['role']}" if f.get("role") else ""))
        if len(v["files"]) > 6:
            print(f"       ... and {len(v['files']) - 6} more files")

    # extraction
    print("\n-- extraction of primary.mesh and primary.sound (SPEC 2 / 2.1)")
    os.makedirs(outdir, exist_ok=True)
    prim = man.get("primary") or {}
    targets = []
    if "mesh" in prim:
        targets.append(("mesh", prim["mesh"]))
    else:
        g = [n["node_id"] for n in man["nodes"] if n["type"] == "core.geom.game"]
        report("primary-fallback", "info", "mesh", f"no primary.mesh; using core.geom.game {g[:1]}")
        targets += [("mesh", g[0])] if g else []
    if "sound" in prim:
        targets.append(("sound", prim["sound"]))
    else:
        a = [n["node_id"] for n in man["nodes"] if n["type"] == "core.audio.effect"]
        report("primary-fallback", "info", "sound", f"no primary.sound; using first core.audio.effect {a[:1]}")
        targets += [("sound", a[0])] if a else []
    results = []
    for kind, nid in targets:
        if nid not in nodes:
            report("primary-missing", "error", kind, nid)
            continue
        if nid in dead:
            report("primary-dead", "error", kind, nid)
            continue
        v = active_ver[nid]
        pf, rule = resolve_payload(nodes[nid], v)
        if pf is None:
            continue
        decl = next(f for f in v["files"] if f["path"] == pf)
        data = get(pf)
        dest = os.path.join(outdir, os.path.basename(pf))     # basename only: no path traversal
        with open(dest, "wb") as fh:
            fh.write(data)
        with open(dest, "rb") as fh:
            on_disk = hashlib.sha256(fh.read()).hexdigest()
        ok = on_disk == decl["sha256"]
        print(f"  {kind}: primary.{kind}={nid} -> {pf} ({rule})")
        print(f"     wrote {dest} ({len(data)} B)")
        print(f"     declared sha256 {decl['sha256']}")
        print(f"     on-disk  sha256 {on_disk}  -> {'MATCH' if ok else 'MISMATCH'}")
        if not ok:
            report("extract-hash-mismatch", "error", pf)
        try:
            info = glb_info(data) if kind == "mesh" else wav_info(data)
            print(f"     parsed: {json.dumps(info)}")
            if kind == "mesh":
                for pr in info["primitives"]:
                    if pr["mode"] != 4 or pr["indices"] is None or "NORMAL" not in pr["attributes"]:
                        report("glb-nonconformant", "warn", pf, "SPEC 3.10 requires mode 4, indices, NORMAL")
        except (ValueError, KeyError, struct.error) as ex:
            report("payload-parse-failed", "warn", pf, str(ex))
        results.append((kind, nid, pf, dest, decl["sha256"], on_disk, ok))

    # summary
    errs = [r for r in REPORT if r[1] == "error"]
    warns = [r for r in REPORT if r[1] == "warn"]
    print("\n== summary")
    print(f"  signature: {sig_state}")
    print(f"  dead nodes: {sorted(dead) or 'none'}")
    print(f"  report entries: {len(errs)} error, {len(warns)} warn, {len(REPORT) - len(errs) - len(warns)} info")
    for kind, nid, pf, dest, d, c, ok in results:
        print(f"  extracted {kind}: {dest}  {'MATCH' if ok else 'MISMATCH'}")
    return 1 if errs else 0


class _Tee:
    def __init__(self, *s):
        self.s = s

    def write(self, x):
        for s in self.s:
            s.write(x)

    def flush(self):
        for s in self.s:
            s.flush()


if __name__ == "__main__":
    args = list(sys.argv)
    if "--log" in args:            # --log FILE: also write everything printed to FILE
        i = args.index("--log")
        sys.stdout = _Tee(sys.stdout, open(args[i + 1], "w", encoding="utf-8"))
        del args[i:i + 2]
    sys.exit(main(args))
