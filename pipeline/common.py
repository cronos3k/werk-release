#!/usr/bin/env python3
"""common.py — the parts every producer in the enrichment pipeline shares.

Hashing, the on-disk JSON spelling, the node/version builders, the canonical
MessagePack encoder and the binary-envelope writer, and the zip writer that is
byte-for-byte what `core/src/zipstore.rs` emits.

Nothing here is werk-specific policy; the policy lives in `spec/` and in the
producer modules. This file is the plumbing, and it is deliberately the only
place in the pipeline that knows how to turn bytes into a container.

Stdlib only, except `werkstore.ed25519` (itself stdlib-only) for signing.
"""

import hashlib
import json
import math
import os
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if os.path.join(ROOT, "store") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "store"))

TOOL = "pipeline/enrich.py"
TOOL_VERSION = "0.1"


# ---------------------------------------------------------------------------
# hashing, JSON, ids
# ---------------------------------------------------------------------------

def sha256(b):
    return hashlib.sha256(b).hexdigest()


def jbytes(v):
    """The on-disk spelling werk uses: two-space indent, trailing newline."""
    return (json.dumps(v, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def canon(v):
    """Canonical JSON, as `input_params` is hashed (MINI-SPECS section 11)."""
    # ensure_ascii=False is NOT cosmetic. MINI-SPECS section 3 rule 3 writes a
    # character outside ASCII as its UTF-8 bytes; json.dumps escapes it to
    # \uXXXX unless told not to, which is valid JSON, parses to the same
    # value, and hashes to something else than werk-core computes. This
    # function had the default for as long as it existed, and nothing caught it
    # because no input_params anywhere held a non-ASCII character AND the gate
    # that recomputes input_hash carried the same line (finding F-AC-2,
    # 2026-10-13; tests/run_gate_reference.py now holds the spec's vector).
    # sort_keys orders by code point, which is the UTF-8 byte order the rule
    # asks for; allow_nan=False because a werk number is always finite.
    return json.dumps(v, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def uuid_from(seed_bytes):
    """A deterministic RFC-4122 v4-shaped uuid derived from content.

    A pipeline that stamped a random uuid would make two runs over one GLB
    two different entities, which is a lie about identity (law 4). Derived
    from the source bytes, the uuid says 'this entity is that GLB enriched'
    and says it the same way on every machine.
    """
    d = hashlib.sha256(b"werk-entity-uuid/1\x00" + seed_bytes).digest()
    b = bytearray(d[:16])
    b[6] = (b[6] & 0x0F) | 0x40
    b[8] = (b[8] & 0x3F) | 0x80
    h = b.hex()
    return "%s-%s-%s-%s-%s" % (h[0:8], h[8:12], h[12:16], h[16:20], h[20:32])


def kebab(s):
    out = []
    prev_dash = True
    for ch in s.lower():
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        elif not prev_dash:
            out.append("-")
            prev_dash = True
    while out and out[-1] == "-":
        out.pop()
    return "".join(out) or "entity"


# ---------------------------------------------------------------------------
# canonical MessagePack (writer subset of ENVELOPE.layout.txt section 4)
# ---------------------------------------------------------------------------

def mp_encode(v):
    if v is True:
        return b"\xc3"
    if v is False:
        return b"\xc2"
    if v is None:
        raise ValueError("werk headers never carry nil; omit the key instead")
    if isinstance(v, int):
        if 0 <= v <= 127:
            return struct.pack("B", v)
        if -32 <= v < 0:
            return struct.pack("b", v)
        if 0 <= v <= 0xFF:
            return b"\xcc" + struct.pack(">B", v)
        if 0 <= v <= 0xFFFF:
            return b"\xcd" + struct.pack(">H", v)
        if 0 <= v <= 0xFFFFFFFF:
            return b"\xce" + struct.pack(">I", v)
        if 0 <= v <= 0xFFFFFFFFFFFFFFFF:
            return b"\xcf" + struct.pack(">Q", v)
        if -0x80 <= v < 0:
            return b"\xd0" + struct.pack(">b", v)
        if -0x8000 <= v < 0:
            return b"\xd1" + struct.pack(">h", v)
        if -0x80000000 <= v < 0:
            return b"\xd2" + struct.pack(">i", v)
        return b"\xd3" + struct.pack(">q", v)
    if isinstance(v, float):
        # section 4.3: every non-integral number is float64, never float32.
        if math.isnan(v) or math.isinf(v):
            raise ValueError("no NaN and no infinity in a werk payload")
        return b"\xcb" + struct.pack(">d", v)
    if isinstance(v, str):
        b = v.encode("utf-8")
        n = len(b)
        if n <= 31:
            return struct.pack("B", 0xA0 | n) + b
        if n <= 0xFF:
            return b"\xd9" + struct.pack(">B", n) + b
        if n <= 0xFFFF:
            return b"\xda" + struct.pack(">H", n) + b
        return b"\xdb" + struct.pack(">I", n) + b
    if isinstance(v, (list, tuple)):
        n = len(v)
        if n <= 15:
            head = struct.pack("B", 0x90 | n)
        elif n <= 0xFFFF:
            head = b"\xdc" + struct.pack(">H", n)
        else:
            head = b"\xdd" + struct.pack(">I", n)
        return head + b"".join(mp_encode(x) for x in v)
    if isinstance(v, dict):
        items = sorted(v.items(), key=lambda kv: kv[0].encode("utf-8"))
        n = len(items)
        if n <= 15:
            head = struct.pack("B", 0x80 | n)
        elif n <= 0xFFFF:
            head = b"\xde" + struct.pack(">H", n)
        else:
            head = b"\xdf" + struct.pack(">I", n)
        return head + b"".join(mp_encode(k) + mp_encode(x) for k, x in items)
    raise TypeError("not encodable in the werk MessagePack subset: %r" % type(v))


DTYPE_SIZE = {"u8": 1, "i8": 1, "u16": 2, "i16": 2, "u32": 4, "i32": 4,
              "u64": 8, "i64": 8, "f32": 4, "f64": 8}


def write_envelope(magic, kind, header_extra, sections):
    """Build a conformant werk binary envelope.

    `sections` is a list of (name, dtype, shape, stride, payload_bytes) in file
    order. Offsets, sizes, payload_origin and payload_size are computed here
    and DECLARED in the header — never left for a reader to derive (law 8).
    The section consistency rule of ENVELOPE.layout.txt section 3 is asserted
    on the way out, so a malformed writer fails here and not in someone else's
    reader.
    """
    assert len(magic) == 4
    # payload_origin depends on header_len, which depends on the offsets, which
    # depend on payload_origin. Iterate to the fixed point; it converges in two
    # rounds because only the digit count of the offsets can move.
    origin = 16
    for _ in range(8):
        secs, cursor = [], origin
        for name, dtype, shape, stride, data in sections:
            esz = DTYPE_SIZE.get(dtype, stride)
            prod_all = 1
            for d in shape:
                prod_all *= d
            if stride == esz:
                expect = stride * prod_all
            else:
                assert shape and stride >= esz * shape[-1], \
                    "%s: stride %d < esz %d * shape[-1] %d" % (name, stride, esz,
                                                               shape[-1] if shape else 0)
                prod_head = 1
                for d in shape[:-1]:
                    prod_head *= d
                expect = stride * prod_head
            assert len(data) == expect, \
                "%s: %d payload bytes, consistency rule says %d" % (name, len(data), expect)
            secs.append({"name": name, "offset": cursor, "size": len(data),
                         "dtype": dtype, "shape": [int(d) for d in shape],
                         "stride": int(stride)})
            cursor += len(data)
            cursor = (cursor + 15) // 16 * 16
        header = dict(header_extra)
        header.update({"kind": kind, "endianness": "le",
                       "payload_origin": origin, "payload_size": cursor - origin,
                       "sections": secs})
        hb = mp_encode(header)
        new_origin = 16 * ((12 + len(hb) + 15) // 16)
        if new_origin == origin:
            break
        origin = new_origin
    else:
        raise RuntimeError("envelope header size did not converge")

    out = bytearray()
    out += magic.encode("ascii") + struct.pack("<II", 1, len(hb)) + hb
    out += b"\x00" * (origin - len(out))
    for sec, (_n, _d, _s, _st, data) in zip(secs, sections):
        assert len(out) == sec["offset"]
        out += data
        pad = (16 - (len(out) % 16)) % 16
        out += b"\x00" * pad
    assert len(out) == origin + header["payload_size"]
    return bytes(out)


# ---------------------------------------------------------------------------
# zip writer — byte-for-byte what core/src/zipstore.rs::write_zip emits
# ---------------------------------------------------------------------------

CRC_TABLE = []
for _n in range(256):
    _c = _n
    for _ in range(8):
        _c = (_c >> 1) ^ (0xEDB88320 if _c & 1 else 0)
    CRC_TABLE.append(_c)


def crc32(data):
    c = 0xFFFFFFFF
    for b in data:
        c = (c >> 8) ^ CRC_TABLE[(c ^ b) & 0xFF]
    return c ^ 0xFFFFFFFF


DOS_TIME = (9 << 11) | (0 << 5)
DOS_DATE = ((2026 - 1980) << 9) | (8 << 5) | 8
FLAG_UTF8 = 0x0800


def write_zip(entries):
    out, central, count = bytearray(), bytearray(), 0
    for name, data in entries:
        lho = len(out)
        crc = crc32(data)
        nb = name.encode("utf-8")
        out += struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, FLAG_UTF8, 0, DOS_TIME,
                           DOS_DATE, crc, len(data), len(data), len(nb), 0)
        out += nb + data
        central += struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, 20, 20, FLAG_UTF8, 0,
                               DOS_TIME, DOS_DATE, crc, len(data), len(data), len(nb),
                               0, 0, 0, 0, 0, lho)
        central += nb
        count += 1
    cd_off, cd_size = len(out), len(central)
    out += central
    out += struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, count, count, cd_size, cd_off, 0)
    return bytes(out)


# ---------------------------------------------------------------------------
# the build context every producer writes into
# ---------------------------------------------------------------------------

class Report(object):
    """One line of the pipeline's own honesty. A producer that fails writes
    one of these and the run continues (the island rule): a failed producer
    yields a MISSING NODE plus a report, never a dead pipeline."""

    def __init__(self, stage, status, seconds, detail="", nodes=(), error=None):
        self.stage = stage
        self.status = status          # "ok" | "skipped" | "failed"
        self.seconds = seconds
        self.detail = detail
        self.nodes = list(nodes)
        self.error = error

    record_timings = True

    def as_json(self):
        d = {"stage": self.stage, "status": self.status, "nodes": self.nodes}
        if self.record_timings:
            d["wall_seconds"] = round(self.seconds, 4)
        if self.detail:
            d["detail"] = self.detail
        if self.error:
            d["error"] = self.error
        return d


class Ctx(object):
    def __init__(self, created, entity_uuid, name, record_timings=True):
        # Wall times are honest measurements of ONE run and therefore the one
        # thing in the package that cannot be byte-identical across runs.
        # `record_timings=False` drops them so that byte-identity becomes a
        # checkable property; it does not make the pipeline more deterministic,
        # it stops the package from recording the one thing that isn't.
        self.record_timings = record_timings
        self.files = {}
        self.nodes = []
        self.reports = []
        self.created = created
        self.entity_uuid = entity_uuid
        self.name = name
        self.parts = []
        self.materials = []
        self.schemas = {}
        self.layouts = {}
        # format id -> path of its definition document (SPEC.md section 3.18):
        # the third map of the same kind, for files in an encoding that is
        # neither JSON nor a werk envelope. Empty unless a node names a format.
        self.formats = {}
        self.primary = {}
        self.stats = {}
        self.notes = []

    # -- files ----------------------------------------------------------
    def put(self, path, data):
        if path in self.files:
            raise AssertionError("two nodes claim %s" % path)
        self.files[path] = data
        return {"path": path, "sha256": sha256(data), "size": len(data)}

    def input_hash(self, paths, params=None):
        """sha256 over each input's 32 RAW digest bytes in order, then the
        canonical JSON of input_params. The executable copy is werk-core's
        hashing.rs; this must agree with it byte for byte."""
        h = hashlib.sha256()
        for p in paths:
            h.update(hashlib.sha256(self.files[p]).digest())
        h.update(canon(params if params is not None else {}))
        return h.hexdigest()

    # -- nodes ----------------------------------------------------------
    def node(self, node_id, ntype, ver, edges=(), meta=None, part=None,
             material=None):
        n = {"node_id": node_id, "type": ntype, "versions": [ver], "active": 1,
             "edges": [dict(e) for e in edges]}
        if part:
            n["part_id"] = part
        if material:
            n["material_id"] = material
        if meta:
            n["meta"] = meta
        self.nodes.append(n)
        return n

    def version(self, fs, note, epistemic, inputs=None, params=None,
                confidence=None, tool=TOOL, tver=TOOL_VERSION, model=None):
        v = {"v": 1, "files": list(fs), "note": note,
             "producer": {"tool": tool, "version": tver},
             "epistemic": epistemic, "created": self.created}
        if model:
            v["producer"]["model"] = model
        if epistemic in ("measured", "inferred"):
            assert inputs, "%s node without input_files: law 5 forbids it" % epistemic
        if inputs:
            v["input_files"] = list(inputs)
            v["input_params"] = dict(params or {})
            v["input_hash"] = self.input_hash(inputs, v["input_params"])
        if confidence is not None:
            v["confidence"] = confidence
        return v

    # -- reports --------------------------------------------------------
    def report(self, r):
        r.record_timings = self.record_timings
        self.reports.append(r)
        return r


class Stage(object):
    """Context manager implementing the island rule.

        with Stage(ctx, "lod") as st:
            ...
            st.produced("geom-lod1")

    An exception inside the block is caught, timed, recorded as a failed
    stage, and swallowed. The pipeline continues and the package simply lacks
    that node — which the format says is legal and which is exactly the
    behaviour under test.
    """

    def __init__(self, ctx, name, verbose=True):
        self.ctx = ctx
        self.name = name
        self.verbose = verbose
        self.nodes = []
        self.detail = ""
        self.t0 = None
        self.ok = False

    def produced(self, *node_ids):
        self.nodes.extend(node_ids)

    def says(self, text):
        self.detail = text

    def __enter__(self):
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        dt = time.perf_counter() - self.t0
        if exc_type is None:
            self.ok = True
            r = Report(self.name, "ok", dt, self.detail, self.nodes)
        else:
            import traceback
            err = "".join(traceback.format_exception_only(exc_type, exc)).strip()
            r = Report(self.name, "failed", dt, self.detail, [], err)
            r.traceback = "".join(traceback.format_exception(exc_type, exc, tb))
        self.ctx.report(r)
        if self.verbose:
            print("  [%-7s] %-14s %7.2fs  %s" % (r.status, self.name, dt,
                                                 r.error or r.detail))
        return exc_type is not None       # swallow: the island rule


# ---------------------------------------------------------------------------
# PNG (writer only; Pillow is a PIPELINE dependency and never ships inside a
# package — law 1 governs what travels in the file, not what built it)
# ---------------------------------------------------------------------------

def png_bytes(arr, mode):
    """arr: numpy array. mode in {'RGBA','RGB','L16'}. Deterministic PNG."""
    import io
    import numpy as np
    from PIL import Image
    if mode == "L16":
        img = Image.fromarray(np.ascontiguousarray(arr.astype("<u2")), mode="I;16")
    else:
        img = Image.fromarray(np.ascontiguousarray(arr.astype("u1")), mode=mode)
    buf = io.BytesIO()
    # optimize=False + fixed compress_level keeps two runs byte-identical.
    img.save(buf, format="PNG", optimize=False, compress_level=6)
    return buf.getvalue()


def png_info(b):
    assert b[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    ln, tag = struct.unpack(">I4s", b[8:16])
    assert tag == b"IHDR" and ln == 13
    w, h, depth, ctype = struct.unpack(">IIBB", b[16:26])
    return {"width": w, "height": h, "bit_depth": depth, "color_type": ctype}


def srgb_to_linear_f(u8):
    s = u8 / 255.0
    return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4


def linear_to_srgb_f(x):
    x = max(0.0, min(1.0, x))
    return x * 12.92 if x <= 0.0031308 else 1.055 * (x ** (1.0 / 2.4)) - 0.055


def hexcolor(rgb_lin):
    return "#" + "".join("%02x" % int(round(linear_to_srgb_f(c) * 255.0))
                         for c in rgb_lin)
