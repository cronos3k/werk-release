#!/usr/bin/env python3
"""inspect_werk.py — open gsplat-v1.werk, list contents with meanings, verify
integrity, and extract point positions and colours.

This script uses only the Python 3 standard library and the format rules
derived from the files inside the package (spec/README.md, SPEC.md,
ENVELOPE.layout.txt, gsplat.layout.txt, points.layout.txt, MINI-SPECS.md and
the manifest).  It does NOT import or run any code that came out of the
package.
"""

import hashlib
import json
import math
import os
import struct
import sys
import zipfile
from io import BytesIO

PATH = "gsplat-v1.werk"

DTYPE_SIZE = {
    "u8": 1, "i8": 1, "u16": 2, "i16": 2, "u32": 4, "i32": 4,
    "u64": 8, "i64": 8, "f32": 4, "f64": 8,
}

# ---------------------------------------------------------------------------
# Minimal MessagePack decoder for the werk header subset.
# Derived from spec/layouts/ENVELOPE.layout.txt section 4.
# ---------------------------------------------------------------------------

class MsgpackError(Exception):
    pass

class Decoder:
    def __init__(self, data):
        self.data = data
        self.i = 0

    def _read(self, n):
        if self.i + n > len(self.data):
            raise MsgpackError("truncated")
        out = self.data[self.i:self.i + n]
        self.i += n
        return out

    def decode(self):
        if self.i >= len(self.data):
            raise MsgpackError("empty")
        b = self.data[self.i]
        # Fixed-width literals: consume the single byte first.
        if 0x00 <= b <= 0x7f:
            self.i += 1
            return b
        if 0xe0 <= b <= 0xff:
            self.i += 1
            return b - 256
        if b == 0xc0:
            self.i += 1
            return None
        if b == 0xc2:
            self.i += 1
            return False
        if b == 0xc3:
            self.i += 1
            return True

        # Helper: consume the type byte, then read n payload bytes.
        def payload(n):
            self.i += 1
            return self._read(n)

        if b == 0xcc:
            return struct.unpack(">B", payload(1))[0]
        if b == 0xcd:
            return struct.unpack(">H", payload(2))[0]
        if b == 0xce:
            return struct.unpack(">I", payload(4))[0]
        if b == 0xcf:
            return struct.unpack(">Q", payload(8))[0]
        if b == 0xd0:
            return struct.unpack(">b", payload(1))[0]
        if b == 0xd1:
            return struct.unpack(">h", payload(2))[0]
        if b == 0xd2:
            return struct.unpack(">i", payload(4))[0]
        if b == 0xd3:
            return struct.unpack(">q", payload(8))[0]
        if b == 0xca:
            return struct.unpack(">f", payload(4))[0]
        if b == 0xcb:
            return struct.unpack(">d", payload(8))[0]
        if 0xa0 <= b <= 0xbf:
            n = b & 0x1f
            return payload(n).decode("utf-8")
        if b == 0xd9:
            n = struct.unpack(">B", payload(1))[0]
            return self._read(n).decode("utf-8")
        if b == 0xda:
            n = struct.unpack(">H", payload(2))[0]
            return self._read(n).decode("utf-8")
        if b == 0xdb:
            n = struct.unpack(">I", payload(4))[0]
            return self._read(n).decode("utf-8")
        if b == 0xc4:
            n = struct.unpack(">B", payload(1))[0]
            return self._read(n)
        if b == 0xc5:
            n = struct.unpack(">H", payload(2))[0]
            return self._read(n)
        if b == 0xc6:
            n = struct.unpack(">I", payload(4))[0]
            return self._read(n)
        if 0x90 <= b <= 0x9f:
            self.i += 1
            n = b & 0x0f
            return [self.decode() for _ in range(n)]
        if b == 0xdc:
            self.i += 1
            n = struct.unpack(">H", self._read(2))[0]
            return [self.decode() for _ in range(n)]
        if b == 0xdd:
            self.i += 1
            n = struct.unpack(">I", self._read(4))[0]
            return [self.decode() for _ in range(n)]
        if 0x80 <= b <= 0x8f:
            self.i += 1
            n = b & 0x0f
            return {self.decode(): self.decode() for _ in range(n)}
        if b == 0xde:
            self.i += 1
            n = struct.unpack(">H", self._read(2))[0]
            return {self.decode(): self.decode() for _ in range(n)}
        if b == 0xdf:
            self.i += 1
            n = struct.unpack(">I", self._read(4))[0]
            return {self.decode(): self.decode() for _ in range(n)}
        raise MsgpackError("banned or unsupported type byte 0x%02x" % b)


def msgpack_decode(data):
    d = Decoder(data)
    v = d.decode()
    if d.i != len(data):
        raise MsgpackError("trailing bytes after header")
    return v


# ---------------------------------------------------------------------------
# Envelope parsing / verification.
# ---------------------------------------------------------------------------

def prod(shape):
    p = 1
    for x in shape:
        p *= x
    return p


def verify_envelope(name, blob):
    """Parse and verify a werk binary envelope.  Return (header, sections_data).
    Raises AssertionError on failure."""
    if len(blob) < 12:
        raise AssertionError("%s: file too short" % name)
    magic = blob[0:4].decode("ascii")
    version, header_len = struct.unpack("<II", blob[4:12])
    if 12 + header_len > len(blob):
        raise AssertionError("%s: header_len %d exceeds file size" % (name, header_len))
    header = msgpack_decode(blob[12:12 + header_len])
    P = 16 * math.ceil((12 + header_len) / 16)
    if header.get("payload_origin") != P:
        raise AssertionError("%s: payload_origin %s != computed %d" %
                             (name, header.get("payload_origin"), P))
    if P + header.get("payload_size", -1) != len(blob):
        raise AssertionError("%s: payload_origin+payload_size != file size" % name)
    sections = header.get("sections", [])
    prev_end = P
    for s in sections:
        off = s["offset"]
        size = s["size"]
        dtype = s["dtype"]
        shape = s["shape"]
        stride = s["stride"]
        if off % 16 != 0:
            raise AssertionError("%s section %s: offset %d not 16-byte aligned" %
                                 (name, s["name"], off))
        if off < prev_end:
            raise AssertionError("%s section %s: overlaps previous section" %
                                 (name, s["name"]))
        if off + size > len(blob):
            raise AssertionError("%s section %s: extends past file end" %
                                 (name, s["name"]))
        esz = DTYPE_SIZE.get(dtype, stride)
        if stride == esz:
            expect = stride * prod(shape)
        else:
            if not shape or stride < esz * shape[-1]:
                raise AssertionError("%s section %s: stride %d < esz %d * last_shape %d" %
                                     (name, s["name"], stride, esz, shape[-1] if shape else 0))
            expect = stride * prod(shape[:-1])
        if size != expect:
            raise AssertionError("%s section %s: size %d != expected %d" %
                                 (name, s["name"], size, expect))
        prev_end = off + size
    if math.ceil(prev_end / 16) * 16 != P + header["payload_size"]:
        raise AssertionError("%s: trailing alignment mismatch" % name)
    return header, {s["name"]: blob[s["offset"]:s["offset"] + s["size"]]
                    for s in sections}


def floats_ok(data, dtype):
    if dtype not in ("f32", "f64"):
        return True
    fmt = "<f" if dtype == "f32" else "<d"
    sz = 4 if dtype == "f32" else 8
    for i in range(0, len(data), sz):
        v = struct.unpack(fmt, data[i:i + sz])[0]
        if math.isnan(v) or math.isinf(v):
            return False
    return True


# ---------------------------------------------------------------------------
# Main inspection.
# ---------------------------------------------------------------------------

def main():
    print("Opening %s ..." % PATH)
    z = zipfile.ZipFile(PATH)

    # Basic zip integrity.
    bad = z.testzip()
    if bad:
        print("ZIP integrity FAIL: first corrupt entry: %s" % bad)
    else:
        print("ZIP integrity: OK (all CRCs match)")

    # Read manifest and signature.
    manifest_bytes = z.read("MANIFEST.json")
    sig_bytes = z.read("SIGNATURE.json")
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    signature = json.loads(sig_bytes.decode("utf-8"))

    print("\nProfile: %s" % manifest["profile"])
    print("Entity:  %s (%s)" % (manifest["entity"]["name"],
                                manifest["entity"]["uuid"]))
    print("Manifest schema: %s" % manifest.get("manifest_schema",
                                                "spec/schemas/manifest.schema.json"))

    # Build a path -> meaning map from the manifest nodes.
    path_meaning = {}
    node_for_path = {}
    declared_files = set()
    for node in manifest.get("nodes", []):
        node_id = node["node_id"]
        ntype = node["type"]
        active = node["active"]
        for ver in node.get("versions", []):
            vnum = ver["v"]
            for f in ver.get("files", []):
                p = f["path"]
                declared_files.add(p)
                meaning = "%s node '%s' v%d (active=%s)" % (ntype, node_id, vnum, active)
                if p in path_meaning:
                    # Same node may list same file in multiple versions.
                    if node_for_path[p] != node_id:
                        print("WARNING: path %s claimed by two different nodes" % p)
                else:
                    path_meaning[p] = meaning
                    node_for_path[p] = node_id

    print("\n--- Contents (%d zip entries) ---" % len(z.namelist()))
    categories = {}
    for p in z.namelist():
        info = z.getinfo(p)
        meaning = path_meaning.get(p, "container framing / not declared")
        cat = p.split("/")[0] if "/" in p else "(root)"
        categories.setdefault(cat, []).append((p, info.file_size, meaning))

    for cat in sorted(categories):
        print("\n[%s]" % cat)
        for p, size, meaning in categories[cat]:
            print("  %-50s  %10d bytes  -> %s" % (p, size, meaning))

    # Verify every declared file's sha256.
    print("\n--- File hash verification ---")
    hash_ok = 0
    hash_bad = 0
    for node in manifest.get("nodes", []):
        for ver in node.get("versions", []):
            for f in ver.get("files", []):
                p = f["path"]
                if p not in z.namelist():
                    print("  MISSING: %s" % p)
                    hash_bad += 1
                    continue
                actual = hashlib.sha256(z.read(p)).hexdigest()
                if actual == f["sha256"]:
                    hash_ok += 1
                else:
                    print("  MISMATCH: %s  declared=%s  actual=%s" %
                          (p, f["sha256"], actual))
                    hash_bad += 1
    print("Declared files: %d OK, %d bad" % (hash_ok, hash_bad))

    # Check no floating entries.
    floating = [p for p in z.namelist() if p not in declared_files and
                p not in ("MANIFEST.json", "SIGNATURE.json")]
    if floating:
        print("Floating entries (not declared by any node): %s" % floating)
    else:
        print("No floating entries besides MANIFEST.json and SIGNATURE.json")

    # spec_sha256 verification.
    spec_files = {}
    for node in manifest.get("nodes", []):
        for ver in node.get("versions", []):
            for f in ver.get("files", []):
                p = f["path"]
                if p.startswith("spec/"):
                    spec_files[p] = bytes.fromhex(f["sha256"])
    ordered = sorted(spec_files.items(), key=lambda kv: kv[0].encode("utf-8"))
    h = hashlib.sha256()
    for p, digest in ordered:
        h.update(p.encode("utf-8"))
        h.update(b"\n")
        h.update(digest)
        h.update(b"\n")
    computed_spec_sha = h.hexdigest()
    declared_spec_sha = manifest.get("spec_sha256")
    print("\nspec_sha256 declared: %s" % declared_spec_sha)
    print("spec_sha256 computed: %s" % computed_spec_sha)
    if computed_spec_sha == declared_spec_sha:
        print("spec_sha256: OK")
    else:
        print("spec_sha256: FAIL")

    # Manifest signature check (hash only; we do not have an Ed25519 verifier
    # in the stdlib, and the package itself says this dev key is not a trust
    # anchor).
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    print("\nMANIFEST.json sha256: %s" % manifest_hash)
    print("SIGNATURE.json manifest_sha256: %s" % signature.get("manifest_sha256"))
    if manifest_hash == signature.get("manifest_sha256"):
        print("Manifest hash matches signature record: OK")
    else:
        print("Manifest hash does NOT match signature record")

    # -----------------------------------------------------------------------
    # Extract point positions and colours from points/plush-dc.wkpc.
    # -----------------------------------------------------------------------
    print("\n=== Point cloud (points/plush-dc.wkpc) ===")
    pc_blob = z.read("points/plush-dc.wkpc")
    pc_header, pc_sections = verify_envelope("points/plush-dc.wkpc", pc_blob)
    count = pc_header["count"]
    fields = pc_header["fields"]
    print("count: %d" % count)
    print("fields:")
    for fld in fields:
        print("  %s  semantic=%s  dtype=%s  components=%d" %
              (fld["name"], fld["semantic"], fld["dtype"], fld["components"]))

    pos_meta = fields[0]
    col_meta = fields[1]
    pos_raw = pc_sections[pos_meta["section"]]
    col_raw = pc_sections[col_meta["section"]]

    positions = []
    for i in range(count):
        x, y, pz = struct.unpack("<fff", pos_raw[i * 12:i * 12 + 12])
        positions.append((x, y, pz))
    colors = []
    for i in range(count):
        r, g, b = struct.unpack("<BBB", col_raw[i * 3:i * 3 + 3])
        colors.append((r, g, b))

    if not floats_ok(pos_raw, "f32"):
        print("WARNING: position data contains NaN or infinity")
    print("\nFirst 5 positions (metres):")
    for i in range(min(5, count)):
        print("  [%d]  %+.6f  %+.6f  %+.6f" % (i, *positions[i]))
    print("\nFirst 5 colours (u8, linear-srgb):")
    for i in range(min(5, count)):
        print("  [%d]  %3d  %3d  %3d" % (i, *colors[i]))

    # -----------------------------------------------------------------------
    # Also read the Gaussian splat and confirm the same positions/means.
    # -----------------------------------------------------------------------
    print("\n=== Gaussian splat (splats/plush.wkgs) ===")
    gs_blob = z.read("splats/plush.wkgs")
    gs_header, gs_sections = verify_envelope("splats/plush.wkgs", gs_blob)
    gs_count = gs_header["count"]
    print("Gaussian count: %d" % gs_count)
    print("sh_degree: %d" % gs_header.get("sh_degree"))

    means_raw = gs_sections["means"]
    shdc_raw = gs_sections["sh-dc"]
    means = []
    for i in range(gs_count):
        means.append(struct.unpack("<fff", means_raw[i * 12:i * 12 + 12]))
    c0 = 0.28209479177387814
    gs_colors = []
    for i in range(gs_count):
        dc = struct.unpack("<fff", shdc_raw[i * 12:i * 12 + 12])
        gs_colors.append(tuple(max(0.0, min(1.0, 0.5 + c0 * c)) for c in dc))

    for sec in gs_header["sections"]:
        if not floats_ok(gs_sections[sec["name"]], sec["dtype"]):
            print("WARNING: section %s contains NaN or infinity" % sec["name"])

    print("\nFirst 5 splat means (metres):")
    for i in range(min(5, gs_count)):
        print("  [%d]  %+.6f  %+.6f  %+.6f" % (i, *means[i]))
    print("\nFirst 5 splat DC colours (linear-srgb, 0..1):")
    for i in range(min(5, gs_count)):
        print("  [%d]  %.6f  %.6f  %.6f" % (i, *gs_colors[i]))

    # Spot-check that the point cloud really is the splat degradation.
    mismatch = 0
    for i in range(min(count, gs_count)):
        if positions[i] != means[i]:
            mismatch += 1
            if mismatch <= 3:
                print("position mismatch at %d: pc=%s gs=%s" % (i, positions[i], means[i]))
    if mismatch:
        print("Position mismatches between WKPC and WKGS: %d" % mismatch)
    else:
        print("\nSpot-check: first %d positions match between WKPC and WKGS" %
              min(count, gs_count))

    # Final summary block, easy to grep.
    print("\n--- SUMMARY ---")
    print("points: %d" % count)
    print("gsplat Gaussians: %d" % gs_count)
    print("file hashes OK: %d" % hash_ok)
    print("file hashes bad: %d" % hash_bad)
    print("spec_sha256 OK: %s" % (computed_spec_sha == declared_spec_sha))
    print("manifest hash OK: %s" % (manifest_hash == signature.get("manifest_sha256")))


if __name__ == "__main__":
    raise SystemExit(main())
