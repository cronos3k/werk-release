#!/usr/bin/env python3
"""Read, inventory, and verify gsplat-v1.werk without executing its payload.

This deliberately implements only the ZIP subset declared by MANIFEST.json:
stored members, little-endian headers, no data descriptors, one disk, no ZIP64.
It does not import zipfile and never imports or executes package members.
"""
from __future__ import annotations
import argparse, binascii, hashlib, json, struct, sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

LOCAL, CENTRAL, EOCD = 0x04034B50, 0x02014B50, 0x06054B50

@dataclass(frozen=True)
class Member:
    name: str
    offset: int
    size: int
    crc32: int
    local_offset: int

class Werk:
    def __init__(self, path: Path):
        self.path = path
        self.fp = path.open("rb")
        self.members = self._parse()
        self.by_name = {m.name: m for m in self.members}
        if len(self.by_name) != len(self.members):
            raise ValueError("duplicate member name")

    def close(self):
        self.fp.close()

    def _at(self, offset: int, count: int) -> bytes:
        self.fp.seek(offset)
        data = self.fp.read(count)
        if len(data) != count:
            raise ValueError(f"short read at {offset}: wanted {count}, got {len(data)}")
        return data

    def _parse(self) -> list[Member]:
        size = self.path.stat().st_size
        tail_n = min(size, 65557)
        tail = self._at(size - tail_n, tail_n)
        marker = struct.pack("<I", EOCD)
        rel = -1
        for candidate in range(len(tail) - 22, -1, -1):
            if tail[candidate:candidate+4] == marker:
                comment_n = struct.unpack_from("<H", tail, candidate + 20)[0]
                if candidate + 22 + comment_n == len(tail):
                    rel = candidate
                    break
        if rel < 0:
            raise ValueError("end-of-central-directory signature absent")
        eocd_at = size - tail_n + rel
        e = struct.unpack("<IHHHHIIH", self._at(eocd_at, 22))
        _, disk, cd_disk, disk_count, total_count, cd_size, cd_offset, comment_n = e
        if (disk_count == 0xffff or total_count == 0xffff or
                cd_size == 0xffffffff or cd_offset == 0xffffffff):
            raise ValueError("zip64-unsupported")
        if disk or cd_disk or disk_count != total_count:
            raise ValueError("multi-disk archive is outside the declared subset")
        if eocd_at + 22 + comment_n != size:
            raise ValueError("trailing bytes or malformed EOCD comment")
        if cd_offset + cd_size != eocd_at:
            raise ValueError("central-directory extent mismatch")

        central = []
        pos = cd_offset
        for _ in range(total_count):
            h = struct.unpack("<IHHHHHHIIIHHHHHII", self._at(pos, 46))
            (sig, _made, _need, flags, method, _tm, _dt, crc, csize, usize,
             name_n, extra_n, member_comment_n, disk_no, _iattr, _eattr, local_at) = h
            if sig != CENTRAL:
                raise ValueError(f"bad central signature at {pos}")
            if flags & 0x0008:
                raise ValueError("data descriptors are outside the declared subset")
            if method != 0 or csize != usize:
                raise ValueError("member is not stored")
            if disk_no != 0:
                raise ValueError("member starts on another disk")
            name_b = self._at(pos + 46, name_n)
            encoding = "utf-8" if flags & 0x0800 else "cp437"
            name = name_b.decode(encoding)
            if (PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts
                    or "\\" in name or (len(name) >= 2 and name[1] == ":")):
                raise ValueError(f"unsafe member name: {name!r}")
            if not (flags & 0x0800):
                raise ValueError(f"member name is not flagged UTF-8: {name!r}")
            central.append((name, crc, csize, local_at))
            pos += 46 + name_n + extra_n + member_comment_n
        if pos != eocd_at:
            raise ValueError("central-directory parsing did not end at EOCD")

        members = []
        for name, crc, csize, local_at in central:
            h = struct.unpack("<IHHHHHIIIHH", self._at(local_at, 30))
            sig, _need, flags, method, _tm, _dt, lcrc, lcsize, lusize, name_n, extra_n = h
            if sig != LOCAL or method != 0 or flags & 0x0008:
                raise ValueError(f"unsupported local header for {name}")
            lname_b = self._at(local_at + 30, name_n)
            encoding = "utf-8" if flags & 0x0800 else "cp437"
            lname = lname_b.decode(encoding)
            if (lname, lcrc, lcsize, lusize) != (name, crc, csize, csize):
                raise ValueError(f"local/central disagreement for {name}")
            members.append(Member(name, local_at + 30 + name_n + extra_n,
                                  csize, crc, local_at))
        return members

    def read(self, name: str) -> bytes:
        member = self.by_name[name]
        return self._at(member.offset, member.size)

    def manifest(self) -> dict:
        return json.loads(self.read("MANIFEST.json"))

    def verify(self) -> dict:
        crc_fail = []
        for m in self.members:
            actual = binascii.crc32(self.read(m.name)) & 0xFFFFFFFF
            if actual != m.crc32:
                crc_fail.append((m.name, f"{m.crc32:08x}", f"{actual:08x}"))

        manifest = self.manifest()
        declared = {}
        for node in manifest.get("nodes", []):
            version = next(v for v in node["versions"] if v["v"] == node["active"])
            for f in version.get("files", []):
                old = declared.setdefault(f["path"], (f["size"], f["sha256"]))
                if old != (f["size"], f["sha256"]):
                    raise ValueError(f"conflicting declarations for {f['path']}")
        hash_fail, missing = [], []
        for name, (wanted_size, wanted_hash) in declared.items():
            if name not in self.by_name:
                missing.append(name)
                continue
            data = self.read(name)
            actual_hash = hashlib.sha256(data).hexdigest()
            if len(data) != wanted_size or actual_hash != wanted_hash:
                hash_fail.append((name, wanted_size, len(data), wanted_hash, actual_hash))
        return {
            "archive_member_count": len(self.members),
            "crc_failures": crc_fail,
            "manifest_declared_file_count": len(declared),
            "manifest_missing": missing,
            "manifest_hash_or_size_failures": hash_fail,
            "ok": not crc_fail and not missing and not hash_fail,
        }

def meaning_map(manifest: dict) -> dict[str, str]:
    out = {
        "MANIFEST.json": "package manifest and logical graph",
        "SIGNATURE.json": "signature/integrity metadata",
        "LICENSE": "package licence",
        "README.txt": "human-readable package introduction",
    }
    for node in manifest.get("nodes", []):
        version = next(v for v in node["versions"] if v["v"] == node["active"])
        meaning = f"{node['type']} node {node['node_id']}: {version.get('note', '')}"
        for f in version.get("files", []):
            out[f["path"]] = meaning
    return out

def _mp_read(data: bytes, at: int = 0):
    if at >= len(data):
        raise ValueError("truncated MessagePack value")
    c, at = data[at], at + 1
    if c <= 0x7f:
        return c, at
    if c >= 0xe0:
        return c - 256, at
    if 0xa0 <= c <= 0xbf:
        n = c & 0x1f
        return data[at:at+n].decode("utf-8"), at + n
    if 0x90 <= c <= 0x9f:
        n = c & 0x0f
        out = []
        for _ in range(n):
            v, at = _mp_read(data, at)
            out.append(v)
        return out, at
    if 0x80 <= c <= 0x8f:
        n = c & 0x0f
        out = {}
        for _ in range(n):
            k, at = _mp_read(data, at)
            v, at = _mp_read(data, at)
            if not isinstance(k, str) or k in out:
                raise ValueError("MessagePack map key is not a unique string")
            out[k] = v
        return out, at
    if c in (0xc0, 0xc2, 0xc3):
        return {0xc0: None, 0xc2: False, 0xc3: True}[c], at
    scalar = {
        0xcc: (">B", 1), 0xcd: (">H", 2), 0xce: (">I", 4), 0xcf: (">Q", 8),
        0xd0: (">b", 1), 0xd1: (">h", 2), 0xd2: (">i", 4), 0xd3: (">q", 8),
        0xca: (">f", 4), 0xcb: (">d", 8),
    }
    if c in scalar:
        fmt, n = scalar[c]
        if at + n > len(data):
            raise ValueError("truncated MessagePack scalar")
        return struct.unpack_from(fmt, data, at)[0], at + n
    lengths = {
        0xd9: (">B", "str"), 0xda: (">H", "str"), 0xdb: (">I", "str"),
        0xc4: (">B", "bin"), 0xc5: (">H", "bin"), 0xc6: (">I", "bin"),
        0xdc: (">H", "array"), 0xdd: (">I", "array"),
        0xde: (">H", "map"), 0xdf: (">I", "map"),
    }
    if c in lengths:
        fmt, kind = lengths[c]
        nbytes = struct.calcsize(fmt)
        if at + nbytes > len(data):
            raise ValueError("truncated MessagePack length")
        n = struct.unpack_from(fmt, data, at)[0]
        at += nbytes
        if kind in ("str", "bin"):
            if at + n > len(data):
                raise ValueError("truncated MessagePack string/binary")
            raw = data[at:at+n]
            return (raw.decode("utf-8") if kind == "str" else raw), at + n
        if kind == "array":
            out = []
            for _ in range(n):
                v, at = _mp_read(data, at)
                out.append(v)
            return out, at
        out = {}
        for _ in range(n):
            k, at = _mp_read(data, at)
            v, at = _mp_read(data, at)
            if not isinstance(k, str) or k in out:
                raise ValueError("MessagePack map key is not a unique string")
            out[k] = v
        return out, at
    raise ValueError(f"banned/unsupported MessagePack byte 0x{c:02x}")

def mp_decode(data: bytes):
    value, at = _mp_read(data)
    if at != len(data):
        raise ValueError(f"{len(data)-at} trailing MessagePack bytes")
    return value

def read_envelope(data: bytes, expected_magic: bytes):
    import math
    if len(data) < 16:
        raise ValueError("envelope shorter than 16 bytes")
    magic = data[:4]
    if magic != expected_magic:
        raise ValueError(f"magic {magic!r}, expected {expected_magic!r}")
    version, header_len = struct.unpack_from("<II", data, 4)
    if version < 1 or 12 + header_len > len(data):
        raise ValueError("invalid envelope version/header length")
    header = mp_decode(data[12:12+header_len])
    if not isinstance(header, dict):
        raise ValueError("envelope header is not a map")
    origin = ((12 + header_len + 15) // 16) * 16
    for key in ("kind", "endianness", "payload_origin", "payload_size", "sections"):
        if key not in header:
            raise ValueError(f"missing envelope key {key}")
    if header["endianness"] != "le" or header["payload_origin"] != origin:
        raise ValueError("endianness/payload_origin mismatch")
    if origin + header["payload_size"] != len(data):
        raise ValueError("payload extent mismatch")
    if any(data[12+header_len:origin]):
        raise ValueError("nonzero header padding")

    dsize = {"u8":1, "i8":1, "u16":2, "i16":2, "u32":4, "i32":4,
             "u64":8, "i64":8, "f32":4, "f64":8}
    seen, previous_end = set(), origin
    for sec in header["sections"]:
        for key in ("name", "offset", "size", "dtype", "shape", "stride"):
            if key not in sec:
                raise ValueError(f"section missing {key}")
        name = sec["name"]
        if name in seen:
            raise ValueError(f"duplicate section {name}")
        seen.add(name)
        off, size, stride, shape = sec["offset"], sec["size"], sec["stride"], sec["shape"]
        if off % 16 or off < previous_end or off + size > len(data):
            raise ValueError(f"bad extent/alignment for section {name}")
        if off - previous_end > 15 or any(data[previous_end:off]):
            raise ValueError(f"bad inter-section padding before {name}")
        esz = stride if sec["dtype"] == "record" else dsize.get(sec["dtype"])
        if not esz:
            raise ValueError(f"unknown dtype {sec['dtype']}")
        product = 1
        if stride == esz:
            for dim in shape:
                product *= dim
        else:
            if not shape or stride < esz * shape[-1]:
                raise ValueError(f"bad component stride for {name}")
            for dim in shape[:-1]:
                product *= dim
        if size != stride * product:
            raise ValueError(f"declared size arithmetic fails for {name}")
        if sec["dtype"] in ("f32", "f64"):
            fmt, width = ("<f", 4) if sec["dtype"] == "f32" else ("<d", 8)
            for q in range(off, off + size, width):
                if not math.isfinite(struct.unpack_from(fmt, data, q)[0]):
                    raise ValueError(f"non-finite float in {name}")
        previous_end = off + size
    rounded_end = ((previous_end + 15) // 16) * 16
    if rounded_end != len(data) or any(data[previous_end:]):
        raise ValueError("bad trailing padding")
    return version, header

def _section(header: dict, name: str) -> dict:
    matches = [s for s in header["sections"] if s["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"wanted exactly one section {name}")
    return matches[0]

def validate_points(data: bytes):
    version, h = read_envelope(data, b"WKPC")
    if h["kind"] != "core.geom.points" or h["length_unit"] != "metre":
        raise ValueError("WKPC kind/unit mismatch")
    fields = h["fields"]
    if not fields or len(fields) != len(h["sections"]):
        raise ValueError("WKPC field count mismatch")
    if fields[0]["semantic"] != "position":
        raise ValueError("first WKPC field is not position")
    if sum(f["semantic"] == "position" for f in fields) != 1:
        raise ValueError("WKPC must contain exactly one position")
    for field, sec in zip(fields, h["sections"]):
        if field["section"] != sec["name"] or field["dtype"] != sec["dtype"]:
            raise ValueError("WKPC field/section mismatch")
        wanted_shape = [h["count"]] if field["components"] == 1 else [h["count"], field["components"]]
        if sec["shape"] != wanted_shape:
            raise ValueError("WKPC field shape mismatch")
        if field["semantic"] == "color" and "color_space" not in field:
            raise ValueError("WKPC color has no color_space")
    return version, h

def validate_gsplat(data: bytes):
    version, h = read_envelope(data, b"WKGS")
    if h["kind"] != "core.geom.gsplat" or h["length_unit"] != "metre":
        raise ValueError("WKGS kind/unit mismatch")
    if h["sh_degree"] not in range(4) or h["sh_coeff_count"] != (h["sh_degree"] + 1) ** 2:
        raise ValueError("WKGS SH metadata mismatch")
    if (h["quat_order"], h["scale_space"], h["opacity_space"]) != ("wxyz", "linear", "linear"):
        raise ValueError("WKGS convention mismatch")
    wanted = ["means", "scales", "rotations", "opacities", "sh-dc", "sh-rest"]
    if [s["name"] for s in h["sections"]] != wanted:
        raise ValueError("WKGS section list mismatch")
    return version, h

def crosscheck_points(w: Werk):
    pc = w.read("points/plush-dc.wkpc")
    gs = w.read("splats/plush.wkgs")
    _, ph = validate_points(pc)
    _, gh = validate_gsplat(gs)
    if ph["count"] != gh["count"]:
        raise ValueError("WKPC/WKGS count mismatch")
    count = ph["count"]
    ppos, means = _section(ph, "position"), _section(gh, "means")
    position_exact = pc[ppos["offset"]:ppos["offset"]+ppos["size"]] == gs[means["offset"]:means["offset"]+means["size"]]
    color = next(f for f in ph["fields"] if f["semantic"] == "color")
    csec, dcsec = _section(ph, color["section"]), _section(gh, "sh-dc")
    colors = pc[csec["offset"]:csec["offset"]+csec["size"]]
    mismatch = None
    c0 = 0.28209479177387814
    for i in range(count):
        dc = struct.unpack_from("<fff", gs, dcsec["offset"] + 12*i)
        expected = bytes(round(max(0.0, min(1.0, 0.5 + c0*x)) * 255.0) for x in dc)
        got = colors[3*i:3*i+3]
        if got != expected:
            mismatch = {"index": i, "expected": list(expected), "actual": list(got)}
            break
    return {"count": count, "positions_byte_exact": position_exact,
            "color_formula": "round-half-even(clamp(0.5 + 0.28209479177387814*dc, 0, 1)*255)",
            "color_mismatch": mismatch, "ok": position_exact and mismatch is None}

def verify_all(w: Werk):
    result = w.verify()
    raw_manifest = w.read("MANIFEST.json")
    sig = json.loads(w.read("SIGNATURE.json"))
    actual_manifest_hash = hashlib.sha256(raw_manifest).hexdigest()
    result["signature"] = {
        "state": "unverified",
        "declared_manifest_sha256": sig.get("manifest_sha256"),
        "actual_manifest_sha256": actual_manifest_hash,
        "manifest_hash_matches": sig.get("manifest_sha256") == actual_manifest_hash,
        "ed25519_checked": False,
        "reason": "No Ed25519 implementation was used; the bundled reader makes the same explicit limitation."
    }
    try:
        pv, ph = validate_points(w.read("points/plush-dc.wkpc"))
        gv, gh = validate_gsplat(w.read("splats/plush.wkgs"))
        result["envelopes"] = {
            "points": {"ok": True, "version": pv, "count": ph["count"],
                       "fields": ph["fields"], "sections": ph["sections"]},
            "gsplat": {"ok": True, "version": gv, "count": gh["count"],
                       "sh_degree": gh["sh_degree"], "sections": gh["sections"]},
        }
        result["crosscheck"] = crosscheck_points(w)
    except Exception as exc:
        result["envelopes"] = {"ok": False, "error": str(exc)}
        result["crosscheck"] = {"ok": False, "error": str(exc)}
    result["ok"] = (result["ok"] and result["signature"]["manifest_hash_matches"]
                    and result["envelopes"].get("points", {}).get("ok", False)
                    and result["envelopes"].get("gsplat", {}).get("ok", False)
                    and result["crosscheck"].get("ok", False))
    return result

def point_rows(w: Werk):
    data = w.read("points/plush-dc.wkpc")
    _, h = validate_points(data)
    pos_field = next(f for f in h["fields"] if f["semantic"] == "position")
    color_field = next(f for f in h["fields"] if f["semantic"] == "color")
    ps, cs = _section(h, pos_field["section"]), _section(h, color_field["section"])
    if (pos_field["dtype"], pos_field["components"], color_field["dtype"], color_field["components"]) != ("f32", 3, "u8", 3):
        raise ValueError("extractor supports this file's declared f32x3/u8x3 fields only")
    for i in range(h["count"]):
        xyz = struct.unpack_from("<fff", data, ps["offset"] + i*ps["stride"])
        rgb = struct.unpack_from("<BBB", data, cs["offset"] + i*cs["stride"])
        yield i, xyz, rgb, color_field["color_space"]

def extract_points(w: Werk, output: Path):
    import csv
    count = 0
    sample = []
    with output.open("w", newline="", encoding="utf-8") as fp:
        out = csv.writer(fp, lineterminator="\n")
        out.writerow(["index", "x_m", "y_m", "z_m", "r_u8", "g_u8", "b_u8", "color_space"])
        for i, xyz, rgb, space in point_rows(w):
            out.writerow([i, *(format(x, ".9g") for x in xyz), *rgb, space])
            if len(sample) < 5:
                sample.append({"index": i, "position_m": list(xyz), "color_u8": list(rgb),
                               "color_space": space})
            count += 1
    return {"output": str(output), "count": count, "sample": sample}

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("package", type=Path)
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    sub.add_parser("verify")
    get = sub.add_parser("get")
    get.add_argument("member")
    ep = sub.add_parser("extract-points")
    ep.add_argument("output", type=Path)
    ep.add_argument("--head", type=int, default=5)
    sub.add_parser("crosscheck")
    args = ap.parse_args()
    w = Werk(args.package)
    try:
        if args.command == "list":
            meanings = meaning_map(w.manifest())
            for i, m in enumerate(w.members, 1):
                print(f"{i:03d}\t{m.size:>9}\t{m.name}\t{meanings.get(m.name, 'container/support member')}")
        elif args.command == "verify":
            print(json.dumps(verify_all(w), indent=2))
        elif args.command == "get":
            sys.stdout.buffer.write(w.read(args.member))
        elif args.command == "extract-points":
            print(json.dumps(extract_points(w, args.output), indent=2))
        elif args.command == "crosscheck":
            print(json.dumps(crosscheck_points(w), indent=2))
    finally:
        w.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

