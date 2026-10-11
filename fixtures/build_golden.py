#!/usr/bin/env python3
"""build_golden.py — conformance fixture #1: the golden crate.

Builds `fixtures/crate-v1.werk` (and its directory form, and the damaged
variant) from a REAL splat-foley package: <WERK_LAB>/splat-foley/outputs/example.
Nothing here is invented. Every sha256 is the hash of bytes that are really in
the package; every number in `physics/bounds.json` is computed from the mesh;
every audio effect, take, refined block and transcript is copied from what
splat-foley actually produced.

    python fixtures/build_golden.py [--src DIR] [--out DIR]

Stdlib only, except that it imports werkstore's pure-Python Ed25519 (which is
itself stdlib-only) so the fixture carries a real signature chain rather than a
stub. Deterministic: two runs produce byte-identical output, which is the only
way a checked-in fixture is an artifact rather than an accident.

What is DELIBERATELY ABSENT, because absence is legal and that legality is
itself under test (law 3, the island rule): no LODs, no imposters, no skeleton,
no animation, no colliders, no rigid body, no flow field, no rest poses, no
destruction. And no `core.tex`: this crate is vertex-coloured and carries no
texture maps at all, so inventing one would have been the one thing a
conformance fixture must never do.
"""

import argparse
import hashlib
import json
import math
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# S-29, ruled 2026-08-08: every manifest declares a spec_sha256 over the spec/
# tree it carries. tools/spec_sha256.py is the reference implementation and
# carries the algorithm in its docstring; importing it rather than re-deriving
# it here is the point of having one.
sys.path.insert(0, os.path.join(ROOT, "tools"))
from spec_sha256 import spec_sha256_of_files          # noqa: E402
from payload_file import annotate_payload_files       # noqa: E402
from loader_caps import loader_capabilities        # noqa: E402
from edge_targets import refuse_dangling_requires     # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "store"))
from werkstore import ed25519  # noqa: E402  (path set above, on purpose)
from werkstore.signature import build_chain  # noqa: E402

CREATED = "2026-08-08T10:00:00Z"
ENTITY_UUID = "4f2a1c86-7b3d-4e59-9a02-6d1e8c4b0f37"

# The dev key. DERIVED, PUBLISHED, AND NOT SECRET: it is sha256 of the sentence
# below, so anyone can regenerate it, which is precisely why it must never sign
# anything that matters. A fixture that shipped a real key would be a leak, and
# a fixture that shipped a random key would not be reproducible.
DEV_KEY_PHRASE = b"werk dev key, publicly derived, fixtures only, 2026-08-08"
DEV_SK = hashlib.sha256(DEV_KEY_PHRASE).digest()

PREVIEW_SLUG = "crate-impact-hard-surface"
PREVIEW_ONE_SHOT = "audio/sfx/%s.wav" % PREVIEW_SLUG

ENTRY_ORDER = [
    "MANIFEST.json",
    "SIGNATURE.json",
    "LICENSE",
    "README.txt",
    "loaders/",
    "spec/",
    "semantics/",
    PREVIEW_ONE_SHOT,
    "materials/",
    "physics/",
    "properties/",
    "provenance/",
    "geometry/",
    "audio/",
    "x/",
]
# Everything at or before the preview one-shot is the browsable tier (law 9).
PREVIEW_SET = ENTRY_ORDER[: ENTRY_ORDER.index(PREVIEW_ONE_SHOT) + 1]

AMBIENCE_SLUGS = {"crate-wind-desert", "crate-wind-forest", "crate-wind-forest-dense"}


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def sha256(b):
    return hashlib.sha256(b).hexdigest()


def jbytes(v):
    """The on-disk spelling werk uses: two-space indent, trailing newline."""
    return (json.dumps(v, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def input_hash(paths, files):
    """sha256 over each input's 32 RAW digest bytes in order, then canonical
    JSON of input_params — which is `{}` here, always (manifest.schema.json's
    `input_hash` description; werk-core's hashing.rs is the executable copy)."""
    h = hashlib.sha256()
    for p in paths:
        h.update(hashlib.sha256(files[p]).digest())
    h.update(b"{}")
    return h.hexdigest()


def slug_id(prefix, slug):
    return "%s-%s" % (prefix, slug)


# ---------------------------------------------------------------------------
# PNG / WAV headers — MINI-SPECS sections 8 and 9, only what the meta needs
# ---------------------------------------------------------------------------

def png_info(b):
    assert b[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    ln, tag = struct.unpack(">I4s", b[8:16])
    assert tag == b"IHDR"
    w, h, depth, color = struct.unpack(">IIBB", b[16:26])
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
    return {"width": w, "height": h, "bit_depth": depth, "channels": channels}


def wav_info(b):
    assert b[:4] == b"RIFF" and b[8:12] == b"WAVE", "not a WAV"
    off, fmt, data_len = 12, None, 0
    while off + 8 <= len(b):
        cid, sz = struct.unpack("<4sI", b[off:off + 8])
        body = b[off + 8:off + 8 + sz]
        if cid == b"fmt ":
            tag, ch, rate, _brate, _align, bits = struct.unpack("<HHIIHH", body[:16])
            fmt = {"format_tag": tag, "channels": ch, "sample_rate_hz": rate, "bit_depth": bits}
        elif cid == b"data":
            data_len = sz
        off += 8 + sz + (sz & 1)
    assert fmt, "WAV has no fmt chunk"
    frame = fmt["channels"] * fmt["bit_depth"] // 8
    fmt["frames"] = data_len // frame if frame else 0
    fmt["seconds"] = round(fmt["frames"] / float(fmt["sample_rate_hz"]), 6)
    # 1 = PCM integer, 3 = IEEE float. The schema wants the word, not the number.
    fmt["sample_format"] = {1: "pcm-int", 3: "float"}.get(fmt.pop("format_tag"), "other")
    return fmt


# ---------------------------------------------------------------------------
# GLB — MINI-SPECS section 10
# ---------------------------------------------------------------------------

def glb_read(b):
    magic, version, total = struct.unpack("<4sII", b[:12])
    assert magic == b"glTF" and version == 2 and total == len(b), "not a glTF 2.0 GLB"
    off, js, bin_ = 12, None, b""
    while off < len(b):
        ln, ty = struct.unpack("<II", b[off:off + 8])
        chunk = b[off + 8:off + 8 + ln]
        if ty == 0x4E4F534A:
            js = json.loads(chunk.decode("utf-8"))
        elif ty == 0x004E4942:
            bin_ = chunk
        off += 8 + ln
    return js, bin_


def glb_write(js, bin_):
    jb = json.dumps(js, separators=(",", ":")).encode("utf-8")
    jb += b" " * ((4 - len(jb) % 4) % 4)
    bb = bin_ + b"\x00" * ((4 - len(bin_) % 4) % 4)
    total = 12 + 8 + len(jb) + 8 + len(bb)
    out = struct.pack("<4sII", b"glTF", 2, total)
    out += struct.pack("<II", len(jb), 0x4E4F534A) + jb
    out += struct.pack("<II", len(bb), 0x004E4942) + bb
    return out


def accessor(js, bin_, idx):
    a = js["accessors"][idx]
    bv = js["bufferViews"][a["bufferView"]]
    start = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    ncomp = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[a["type"]]
    fmt = {5121: "B", 5123: "H", 5125: "I", 5126: "f"}[a["componentType"]]
    size = struct.calcsize("<" + fmt)
    raw = bin_[start:start + a["count"] * ncomp * size]
    flat = struct.unpack("<" + fmt * (a["count"] * ncomp), raw)
    return [flat[i * ncomp:(i + 1) * ncomp] for i in range(a["count"])]


def srgb_to_linear(u8):
    c = u8 / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def vertex_normals(pos, idx):
    """Area-weighted face normals accumulated per vertex, then normalised. The
    weighting is the area because the cross product's magnitude already is
    twice the triangle area — the cheap thing and the right thing agree here."""
    acc = [[0.0, 0.0, 0.0] for _ in pos]
    for a, b, c in idx:
        pa, pb, pc = pos[a], pos[b], pos[c]
        u = (pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2])
        v = (pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2])
        n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        for k in (a, b, c):
            acc[k][0] += n[0]
            acc[k][1] += n[1]
            acc[k][2] += n[2]
    out = []
    for i, n in enumerate(acc):
        ln = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
        if ln < 1e-12:  # a fully degenerate vertex: point it outward from origin
            p = pos[i]
            ln = math.sqrt(p[0] ** 2 + p[1] ** 2 + p[2] ** 2) or 1.0
            out.append((p[0] / ln, p[1] / ln, p[2] / ln))
        else:
            out.append((n[0] / ln, n[1] / ln, n[2] / ln))
    return out


def mesh_stats(pos, idx):
    area = 0.0
    vol = 0.0
    edges = {}
    for a, b, c in idx:
        pa, pb, pc = pos[a], pos[b], pos[c]
        u = (pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2])
        v = (pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2])
        n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        area += 0.5 * math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
        # signed volume of the tetrahedron to the origin
        vol += (pa[0] * n[0] + pa[1] * n[1] + pa[2] * n[2]) / 6.0
        for e in ((a, b), (b, c), (c, a)):
            edges[tuple(sorted(e))] = edges.get(tuple(sorted(e)), 0) + 1
    watertight = bool(edges) and all(v == 2 for v in edges.values())
    return area, abs(vol), watertight


# --- Welzl's exact minimal enclosing sphere ---------------------------------

def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _sphere_from(pts):
    """The trivial cases of Welzl: the sphere through 0..4 boundary points."""
    if not pts:
        return ((0.0, 0.0, 0.0), -1.0)
    if len(pts) == 1:
        return (tuple(pts[0]), 0.0)
    if len(pts) == 2:
        a, b = pts
        c = tuple((a[i] + b[i]) / 2.0 for i in range(3))
        return (c, math.dist(c, a))
    if len(pts) == 3:
        a, b, c = pts
        u, v = _sub(b, a), _sub(c, a)
        w = _cross(u, v)
        d = 2.0 * _dot(w, w)
        if d < 1e-24:
            return max((_sphere_from([x, y]) for x, y in
                        ((a, b), (a, c), (b, c))), key=lambda s: s[1])
        t = _cross(_sub([_dot(u, u) * v[i] for i in range(3)],
                        [_dot(v, v) * u[i] for i in range(3)]), w)
        cen = tuple(a[i] + t[i] / d for i in range(3))
        return (cen, max(math.dist(cen, p) for p in pts))
    a, b, c, d = pts[:4]
    m = [[2.0 * (p[i] - a[i]) for i in range(3)] for p in (b, c, d)]
    rhs = [sum(p[i] ** 2 - a[i] ** 2 for i in range(3)) for p in (b, c, d)]

    def det3(m3):
        return (m3[0][0] * (m3[1][1] * m3[2][2] - m3[1][2] * m3[2][1])
                - m3[0][1] * (m3[1][0] * m3[2][2] - m3[1][2] * m3[2][0])
                + m3[0][2] * (m3[1][0] * m3[2][1] - m3[1][1] * m3[2][0]))

    det = det3(m)
    if abs(det) < 1e-24:  # coplanar: the best 3-point sphere that holds all four
        best = None
        for tri in ((a, b, c), (a, b, d), (a, c, d), (b, c, d)):
            s = _sphere_from(list(tri))
            if all(math.dist(s[0], p) <= s[1] + 1e-9 for p in pts[:4]):
                if best is None or s[1] < best[1]:
                    best = s
        return best or _sphere_from(pts[:3])
    cen = []
    for col in range(3):
        mm = [row[:] for row in m]
        for r in range(3):
            mm[r][col] = rhs[r]
        cen.append(det3(mm) / det)
    cen = tuple(cen)
    return (cen, max(math.dist(cen, p) for p in pts[:4]))


def _in_ball(sphere, p, eps=1e-9):
    return sphere[1] >= 0.0 and math.dist(sphere[0], p) <= sphere[1] + eps


def welzl(points):
    """Welzl's exact minimal enclosing sphere.

    The point order is randomised with a FIXED seed: randomisation is what makes
    the expected running time linear, and the fixed seed is what makes the
    fixture reproducible. Every input point is checked against the result before
    it is allowed out of here — an approximate sphere labelled `welzl-exact`
    would be exactly the kind of quiet lie this format exists to prevent."""
    import random
    import threading

    pts = [tuple(p) for p in points]
    random.Random(20260808).shuffle(pts)
    sys.setrecursionlimit(max(3000, len(pts) * 8))

    def rec(n, bound):
        if n == 0 or len(bound) == 4:
            return _sphere_from(bound)
        p = pts[n - 1]
        s = rec(n - 1, bound)
        if _in_ball(s, p):
            return s
        return rec(n - 1, bound + [p])

    # rec's depth equals len(pts), and on CPython <= 3.10 every pure-Python
    # frame also consumes C stack — a few thousand points overflow the default
    # stack and the process dies with 0xC00000FD before any traceback. Run the
    # SAME recursion in a worker thread with a roomier stack; the result and
    # therefore the fixture bytes are unchanged.
    box = {}

    def _run():
        try:
            box["sphere"] = rec(len(pts), [])
        except BaseException as e:  # noqa: BLE001 — re-raised in the caller
            box["error"] = e

    old_stack = threading.stack_size(64 * 1024 * 1024)
    try:
        worker = threading.Thread(target=_run)
        worker.start()
        worker.join()
    finally:
        threading.stack_size(old_stack)
    if "error" in box:
        raise box["error"]
    return box["sphere"]


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


# The same fixed DOS timestamp core/src/zipstore.rs uses: 2026-08-08 09:00:00.
# A wall clock in a local header would destroy byte-identity on rewrite for no
# benefit whatsoever, so both writers agree on one constant instead.
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


def order_entries(paths):
    remaining = sorted(paths)
    out = []
    for pat in ENTRY_ORDER:
        picked = [p for p in remaining
                  if (p.startswith(pat) if pat.endswith("/") else p == pat)]
        for p in picked:
            remaining.remove(p)
            out.append(p)
    return out + remaining


def is_preview(name):
    return any(name.startswith(p) if p.endswith("/") else name == p for p in PREVIEW_SET)


# ---------------------------------------------------------------------------
# the build
# ---------------------------------------------------------------------------

def collect(src, out_dir):
    files = {}          # container path -> bytes
    nodes = []

    def put(path, data):
        assert path not in files, "two nodes claim %s" % path
        files[path] = data
        return {"path": path, "sha256": sha256(data), "size": len(data)}

    def node(node_id, ntype, ver, edges=(), meta=None, part=None, material=None):
        n = {"node_id": node_id, "type": ntype, "versions": [ver], "active": 1,
             "edges": list(edges)}
        if part:
            n["part_id"] = part
        if material:
            n["material_id"] = material
        if meta:
            n["meta"] = meta
        nodes.append(n)
        return n

    def version(fs, note, tool, tver, epistemic, model=None, inputs=None,
                confidence=None):
        v = {"v": 1, "files": fs, "note": note,
             "producer": {"tool": tool, "version": tver},
             "epistemic": epistemic, "created": CREATED}
        if model:
            v["producer"]["model"] = model
        if inputs:
            v["input_files"] = list(inputs)
            v["input_hash"] = input_hash(inputs, files)
            # MINI-SPECS section 11: an absent input_params is the empty object
            # and the two bytes "{}" are appended either way — but a writer
            # SHOULD spell it out, so that no reader has to discover that for
            # itself. Three gauntlet readers did, the hard way. (S-10.)
            v["input_params"] = {}
        if confidence is not None:
            v["confidence"] = confidence
        return v

    # -- LICENSE / README ------------------------------------------------
    lic = (
        "Creative Commons Attribution 4.0 International (CC BY 4.0)\n"
        "\n"
        "This is the FULL LICENCE TEXT, embedded, because law 7 says a licence\n"
        "travels as text and never as a link. A werk file that pointed at a URL\n"
        "for its terms would be a promise about another file, which law 1 bans.\n"
        "\n"
        "You are free to:\n"
        "  Share - copy and redistribute the material in any medium or format.\n"
        "  Adapt - remix, transform, and build upon the material for any\n"
        "  purpose, even commercially.\n"
        "The licensor cannot revoke these freedoms as long as you follow the\n"
        "licence terms.\n"
        "\n"
        "Under the following terms:\n"
        "  Attribution - You must give appropriate credit, provide a link to\n"
        "  the licence, and indicate if changes were made. You may do so in any\n"
        "  reasonable manner, but not in any way that suggests the licensor\n"
        "  endorses you or your use.\n"
        "  No additional restrictions - You may not apply legal terms or\n"
        "  technological measures that legally restrict others from doing\n"
        "  anything the licence permits.\n"
        "\n"
        "Notices:\n"
        "  You do not have to comply with the licence for elements of the\n"
        "  material in the public domain or where your use is permitted by an\n"
        "  applicable exception or limitation.\n"
        "  No warranties are given. The licence may not give you all of the\n"
        "  permissions necessary for your intended use. For example, other\n"
        "  rights such as publicity, privacy, or moral rights may limit how you\n"
        "  use the material.\n"
        "\n"
        "Full legal code: Creative Commons Attribution 4.0 International Public\n"
        "Licence. By exercising the Licensed Rights you accept and agree to be\n"
        "bound by its terms. Section 2 grants a worldwide, royalty-free,\n"
        "non-sublicensable, non-exclusive, irrevocable licence to reproduce and\n"
        "share the Licensed Material, in whole or in part, and to produce,\n"
        "reproduce and share Adapted Material. Section 3 requires retention of\n"
        "attribution, a copyright notice, a notice referring to this licence, a\n"
        "notice referring to the disclaimer of warranties, and an indication of\n"
        "modification. Section 5 disclaims warranties and limits liability to\n"
        "the greatest extent permissible. Section 6 terminates the rights on\n"
        "breach, with automatic reinstatement on cure within 30 days of\n"
        "discovery.\n"
    )
    readme = (
        "werk conformance fixture #1 - the golden crate\n"
        "==============================================\n"
        "\n"
        "A wooden crate with a complete sound world, packaged as one hermetic\n"
        "file. Everything needed to read this file is inside it: spec/ carries\n"
        "the format specification, its schemas and its binary layout grammars,\n"
        "and loaders/ carries three single-file, dependency-free readers - one\n"
        "Python, one Rust, one C. Start with spec/README.md, or just run\n"
        "loaders/werk_read.py against this file.\n"
        "\n"
        "The geometry, the vertex colours, the rendered views, the segment\n"
        "crops and every one of the twenty sound effects came out of a real\n"
        "splat-foley run. The bounds are computed from the mesh. The facet tags\n"
        "and the wood property block are hand-authored, and say so. Nothing in\n"
        "here is a placeholder.\n"
        "\n"
        "It is signed with a DEV KEY that is derived from a published sentence\n"
        "and is therefore not secret. The signature proves the chain works; it\n"
        "proves nothing whatsoever about authorship.\n"
        "\n"
        "Deliberately absent: LODs, imposters, skeleton, animation, colliders,\n"
        "rigid body, flow field, rest poses, destruction - and textures, because\n"
        "this crate is vertex-coloured and has none. A werk is legal with any\n"
        "subset of node families present; that is the island rule, and this file\n"
        "is the test of it.\n"
    )
    lic_f = put("LICENSE", lic.encode("utf-8"))
    readme_f = put("README.txt", readme.encode("utf-8"))

    # -- spec/ and loaders/ ---------------------------------------------
    spec_files = []
    for dirpath, _dirs, names in os.walk(os.path.join(ROOT, "spec")):
        for nm in sorted(names):
            if nm.endswith(".pyc"):
                continue
            full = os.path.join(dirpath, nm)
            rel = "spec/" + os.path.relpath(full, os.path.join(ROOT, "spec")).replace("\\", "/")
            with open(full, "rb") as fh:
                spec_files.append(put(rel, fh.read()))
    spec_files.sort(key=lambda f: f["path"])

    loader_specs = [
        # The capability list is NOT typed here: each loader states its own in
        # one line and it is read from the bytes embedded (tools/loader_caps.py).
        ("loader-python", "werk_read.py", "python", "python>=3.8", None, None),
        ("loader-rust", "werk_read.rs", "rust", "rustc>=1.70 --edition 2021",
         "rustc -O --edition 2021 loaders/werk_read.rs -o werk_read", None),
        ("loader-c", "werk_read.c", "c", "c99",
         "cc -std=c99 -O2 loaders/werk_read.c -o werk_read", None),
    ]

    # -- geometry --------------------------------------------------------
    with open(os.path.join(src, "model.glb"), "rb") as fh:
        src_glb = fh.read()
    js, bin_ = glb_read(src_glb)
    prim = js["meshes"][0]["primitives"][0]
    pos = accessor(js, bin_, prim["attributes"]["POSITION"])
    col = accessor(js, bin_, prim["attributes"]["COLOR_0"])
    flat_idx = accessor(js, bin_, prim["indices"])
    idx = [(flat_idx[i][0], flat_idx[i + 1][0], flat_idx[i + 2][0])
           for i in range(0, len(flat_idx), 3)]
    nrm = vertex_normals(pos, idx)
    area, volume, watertight = mesh_stats(pos, idx)
    centre, radius = welzl(pos)
    assert all(math.dist(centre, p) <= radius + 1e-6 for p in pos), "sphere misses a vertex"
    amin = [min(p[i] for p in pos) for i in range(3)]
    amax = [max(p[i] for p in pos) for i in range(3)]

    # A conformant werk GLB (SPEC 3.10): POSITION and NORMAL are required, and
    # COLOR_0 is linear, never sRGB. The source has neither normals nor linear
    # colour, so this is a real derivation with a real input_hash.
    ib = b"".join(struct.pack("<I", v) for tri in idx for v in tri)
    pb = b"".join(struct.pack("<fff", *p) for p in pos)
    nb_ = b"".join(struct.pack("<fff", *n) for n in nrm)
    cb = b"".join(struct.pack("<ffff", srgb_to_linear(c[0]), srgb_to_linear(c[1]),
                              srgb_to_linear(c[2]), c[3] / 255.0) for c in col)
    views, off = [], 0
    blob = bytearray()
    for data, target in ((ib, 34963), (pb, 34962), (nb_, 34962), (cb, 34962)):
        pad = (4 - len(blob) % 4) % 4
        blob += b"\x00" * pad
        views.append({"buffer": 0, "byteOffset": len(blob), "byteLength": len(data),
                      "target": target})
        blob += data
    off = len(blob)
    game_js = {
        "asset": {"version": "2.0", "generator": "werk fixtures/build_golden.py"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"name": "crate", "mesh": 0}],
        "meshes": [{"name": "crate", "primitives": [{
            "mode": 4, "indices": 0,
            "attributes": {"POSITION": 1, "NORMAL": 2, "COLOR_0": 3}}]}],
        "accessors": [
            {"bufferView": 0, "componentType": 5125, "count": len(idx) * 3,
             "type": "SCALAR", "min": [0], "max": [len(pos) - 1]},
            {"bufferView": 1, "componentType": 5126, "count": len(pos), "type": "VEC3",
             "min": amin, "max": amax},
            {"bufferView": 2, "componentType": 5126, "count": len(pos), "type": "VEC3"},
            {"bufferView": 3, "componentType": 5126, "count": len(pos), "type": "VEC4"},
        ],
        "bufferViews": views,
        "buffers": [{"byteLength": off}],
    }
    game_glb = glb_write(game_js, bytes(blob))

    src_f = put("geometry/source.glb", src_glb)
    game_f = put("geometry/game.glb", game_glb)

    node("geom-source", "core.geom.source",
         version([src_f], "The mesh exactly as the splat-foley run produced it: "
                          "positions, u8 vertex colours, no normals. Kept verbatim "
                          "because it is the anchor every derivation is checked "
                          "against, and a rewritten source is not a source.",
                 "splat-foley", "0.4", "authored"),
         part="crate")
    node("geom-game", "core.geom.game",
         version([game_f],
                 "Runtime mesh: area-weighted vertex normals computed and vertex "
                 "colours converted from sRGB u8 to linear f32, because SPEC 3.10 "
                 "requires NORMAL and requires COLOR_0 to be linear.",
                 "fixtures/build_golden.py", "1", "measured",
                 inputs=["geometry/source.glb"]),
         edges=[{"to": "geom-source", "kind": "enhances", "role": "derived-from"}],
         part="crate")

    # -- material --------------------------------------------------------
    mat = {
        "material_id": "wood", "name": "Crate softwood", "model": "metallic-roughness",
        "base_color_factor": [1.0, 1.0, 1.0, 1.0],
        "metallic_factor": 0.0, "roughness_factor": 0.72,
        "alpha_mode": "opaque", "double_sided": False,
        "epistemic": "authored",
        "note": "No texture maps: this crate is vertex-coloured, so base colour "
                "comes from COLOR_0 and the factor is a neutral multiplier. "
                "Roughness is an authored judgement about dry sawn softwood, not a "
                "measurement, and is labelled as such.",
    }
    mat_f = put("materials/wood.json", jbytes(mat))
    node("material-wood", "core.material",
         version([mat_f], "Authored PBR parameters for the crate's only material.",
                 "fixtures/build_golden.py", "1", "authored"),
         edges=[{"to": "geom-game", "kind": "enhances", "role": "shades"}],
         part="crate", material="wood")

    # -- bounds ----------------------------------------------------------
    bounds = {
        "schema_version": 1, "space": "model",
        "entity": {
            "aabb_min": [round(v, 7) for v in amin],
            "aabb_max": [round(v, 7) for v in amax],
            "sphere_center": [round(v, 7) for v in centre],
            "sphere_radius": round(radius, 7),
            "sphere_method": "welzl-exact",
            "surface_area_m2": round(area, 7),
            "volume_m3": round(volume, 7),
            "watertight": watertight,
            "longest_axis_m": round(max(amax[i] - amin[i] for i in range(3)), 7),
        },
        "epistemic": "measured",
        "note": "Computed from geometry/game.glb: the AABB over every vertex, and "
                "the true minimal enclosing sphere by Welzl - not the sphere "
                "circumscribing the box, which would be 8 percent larger here.",
    }
    bounds_f = put("physics/bounds.json", jbytes(bounds))
    node("bounds", "core.phys.bounds",
         version([bounds_f], "Measured bounds for culling, placement and LOD "
                             "selection maths.", "fixtures/build_golden.py", "1",
                 "measured", inputs=["geometry/game.glb"]),
         edges=[{"to": "geom-game", "kind": "requires", "role": "bounds-of"}],
         part="crate")

    # -- the splat-foley evidence: views and segment crops ----------------
    view_fs, seg_fs, view_meta, seg_meta = [], [], [], []
    for nm in sorted(os.listdir(os.path.join(src, "views"))):
        with open(os.path.join(src, "views", nm), "rb") as fh:
            data = fh.read()
        f = put("x/splat-foley/views/" + nm, data)
        f["role"] = "view"
        view_fs.append(f)
        view_meta.append(dict(png_info(data), file=f["path"]))
    for nm in sorted(os.listdir(os.path.join(src, "segments"))):
        with open(os.path.join(src, "segments", nm), "rb") as fh:
            data = fh.read()
        f = put("x/splat-foley/segments/" + nm, data)
        f["role"] = "crop"
        seg_fs.append(f)
        seg_meta.append(dict(png_info(data), file=f["path"]))

    node("evidence-views", "x.splat-foley.views",
         version(view_fs, "Six orbit views rendered from the source mesh. They are "
                          "the pixels the vision model actually saw, kept so the "
                          "inferred description can be audited rather than trusted.",
                 "splat-foley", "0.4", "measured", inputs=["geometry/source.glb"]),
         edges=[{"to": "geom-source", "kind": "enhances", "role": "rendered-from"}],
         meta={"count": len(view_fs), "images": view_meta,
               "why": "An x.* node because a rendered evidence view is not a "
                      "core.tex: it is never sampled by a material. Law 12 says "
                      "every other reader skips this and loses nothing."})
    node("evidence-segments", "x.splat-foley.segments",
         version(seg_fs, "SAM segment crops: the sub-object regions the description "
                         "and the sound plan were derived from.",
                 "splat-foley", "0.4", "inferred", model="segment-anything",
                 inputs=[f["path"] for f in view_fs], confidence=0.9),
         edges=[{"to": "evidence-views", "kind": "requires", "role": "cropped-from"}],
         meta={"count": len(seg_fs), "images": seg_meta})

    # -- audio: the complete family --------------------------------------
    with open(os.path.join(src, "asset.json"), encoding="utf-8") as fh:
        asset = json.load(fh)
    with open(os.path.join(src, "description.json"), encoding="utf-8") as fh:
        desc = json.load(fh)
    with open(os.path.join(src, "segments.json"), encoding="utf-8") as fh:
        segs = json.load(fh)
    with open(os.path.join(src, "sfx_plan.json"), encoding="utf-8") as fh:
        plan = json.load(fh)

    seg_by_crop = {s["crop"]: s for s in segs["segments"]}
    objects = []
    for o in desc["objects"]:
        obj = {k: v for k, v in o.items() if k in
               ("name", "materials", "size_class", "condition", "notes",
                "provenance", "part_of")}
        if o.get("segment"):
            s = dict(o["segment"])
            src_seg = seg_by_crop.get(s.get("crop"), {})
            if "area_frac" in src_seg:
                s["area_frac"] = src_seg["area_frac"]
            if "stability" in src_seg:
                s["stability"] = src_seg["stability"]
            s["view"] = "x/splat-foley/views/" + s["view"]
            s["crop"] = "x/splat-foley/segments/" + s["crop"]
            obj["segment"] = s
        if o["name"] == "wooden crate":
            obj["part_id"] = "crate"
        objects.append(obj)

    effect_nodes = []
    pkg_effects = []
    pending_effects = []   # built now, turned into nodes after audio/package.json
    total_wavs = 0
    for eff in plan["effects"]:
        slug = eff["slug"]
        sidecar_path = os.path.join(src, "sfx", slug + ".json")
        with open(sidecar_path, encoding="utf-8") as fh:
            side = json.load(fh)
        category = "ambience" if slug in AMBIENCE_SLUGS else "interaction"
        takes, fs = [], []
        best = "audio/sfx/%s.wav" % slug
        candidates = [("%s.wav" % slug, "best"), ("%s.raw.wav" % slug, "raw"),
                      ("%s.var2.wav" % slug, "variation"),
                      ("%s.var3.wav" % slug, "variation")]
        var_scores = {v["file"]: v.get("clap_score") for v in side.get("variations", [])}
        audio_format = None
        for nm, role in candidates:
            full = os.path.join(src, "sfx", nm)
            if not os.path.isfile(full):
                continue
            with open(full, "rb") as fh:
                data = fh.read()
            f = put("audio/sfx/" + nm, data)
            f["media_type"] = "audio/wav"
            f["role"] = role
            fs.append(f)
            info = wav_info(data)
            if role == "best":
                audio_format = {"sample_rate_hz": info["sample_rate_hz"],
                                "channels": info["channels"],
                                "bit_depth": info["bit_depth"],
                                "sample_format": info["sample_format"]}
            takes.append({"file": "audio/sfx/" + nm, "role": role,
                          "clap_score": side.get("clap_score") if role == "best"
                          else var_scores.get(nm)})
            total_wavs += 1

        # The per-effect sidecar, validated by core.audio.effect.schema.json.
        eff_json = {
            "slug": slug,
            "prompt_used": side["prompt_used"],
            "seconds": side["seconds"],
            "loopable": side["loopable"],
            "clap_score": side["clap_score"],
            "accepted": side["accepted"],
            "category": category,
            "object": eff.get("object"),
            "material": eff.get("material"),
            "interaction": eff.get("interaction"),
            "epistemic": "inferred",
            "note": "Generated audio. The CLAP score is the acceptance gate's own "
                    "number and the 'heard' string is an audio model's transcript "
                    "of the result - both are evidence, not proof.",
        }
        if "attempts" in side:
            eff_json["attempts"] = side["attempts"]
        if side.get("variations"):
            eff_json["variations"] = [
                {"file": "audio/sfx/" + v["file"], "clap_score": v["clap_score"]}
                for v in side["variations"]]
        if side.get("refined"):
            eff_json["refined"] = side["refined"]
        if audio_format:
            eff_json["audio_format"] = audio_format
        if eff.get("object") == "wooden crate":
            eff_json["part_id"] = "crate"
        eff_json["material_id"] = "wood"

        meta_path = "audio/sfx/%s.json" % slug
        meta_f = put(meta_path, jbytes(eff_json))
        meta_f["media_type"] = "application/json"
        meta_f["role"] = "descriptor"
        node_id = slug_id("audio", slug)
        effect_nodes.append(node_id)
        pending_effects.append({
            "node_id": node_id, "category": category, "files": [meta_f] + fs,
            "object": eff.get("object", slug),
            "interaction": eff.get("interaction", category),
            "clap": round(float(side["clap_score"]), 4),
            "part": "crate" if eff.get("object") == "wooden crate" else None,
        })

        pkg_eff = {k: eff[k] for k in ("slug", "object", "material", "category",
                                       "interaction", "prompt", "seconds", "loopable")
                   if k in eff}
        pkg_eff["category"] = category
        pkg_eff["accepted"] = side["accepted"]
        pkg_eff["clap_score"] = side["clap_score"]
        pkg_eff["refined"] = side.get("refined")
        pkg_eff["meta"] = meta_path
        pkg_eff["takes"] = takes
        pkg_eff["node_id"] = node_id
        pkg_effects.append(pkg_eff)

    audio_pkg = {
        "format": "splat-foley-asset", "version": 2,
        "asset": asset["asset"], "source": asset.get("source"),
        "geometry": {"kind": asset.get("kind"), "n_vertices": asset.get("n_vertices"),
                     "n_faces": asset.get("n_faces")},
        "model": "geometry/source.glb",
        "textures": [],
        "views": [f["path"] for f in view_fs],
        "segments": [f["path"] for f in seg_fs],
        "objects": objects,
        "effects": pkg_effects,
        "counts": {"objects": len(objects), "effects": len(pkg_effects),
                   "wavs": total_wavs},
        "preview_effect": PREVIEW_SLUG,
    }
    pkg_f = put("audio/package.json", jbytes(audio_pkg))
    node("audio-package", "core.audio.package",
         version([pkg_f],
                 "The sound world index: what was described, what was planned, "
                 "which takes exist and which gate scores they earned - including "
                 "the ones that were rolled back.",
                 "splat-foley", "0.4", "inferred", model="qwen2.5-vl-7b-instruct",
                 inputs=[f["path"] for f in view_fs], confidence=0.75),
         edges=[{"to": "evidence-views", "kind": "enhances", "role": "described-from"},
                {"to": "geom-game", "kind": "enhances", "role": "sounds-for"}],
         part="crate")
    # The effects come after the index they were planned from, so the manifest
    # reads top-down for a human — one of the two masters (law 9).
    for pe in pending_effects:
        node(pe["node_id"],
             "core.audio.ambience" if pe["category"] == "ambience"
             else "core.audio.effect",
             version(pe["files"],
                     "Sound for '%s': %s. Best take plus every variation and the "
                     "pre-refinement raw, so an A/B is possible from the file alone."
                     % (pe["object"], pe["interaction"]),
                     "splat-foley", "0.4", "inferred", model="stable-audio-open-1.0",
                     inputs=["audio/package.json"], confidence=pe["clap"]),
             edges=[{"to": "audio-package", "kind": "enhances", "role": "sounds-for"}],
             part=pe["part"], material="wood")

    # -- semantics: hand-authored facet tags -----------------------------
    facets_reg = json.load(open(os.path.join(ROOT, "spec", "facets.json"),
                                encoding="utf-8"))
    facets = {
        "style": ["rustic", "utilitarian", "industrial"],
        "function": ["container", "storage", "packaging"],
        "environment": ["warehouse", "interior", "exterior"],
        "era": ["timeless"],
        "mood": ["utilitarian", "neutral"],
        "condition": ["new", "clean"],
        "scale-class": ["medium"],
    }
    for facet, tags in facets.items():
        legal = set(facets_reg["facets"][facet]["tags"])
        bad = [t for t in tags if t not in legal and not t.startswith("x.")]
        assert not bad, "tag(s) %s are not in facets.json's %s" % (bad, facet)
    band = facets_reg["facets"]["scale-class"]["tag_meta"]["medium"]
    longest = max(amax[i] - amin[i] for i in range(3))
    assert band["longest_axis_min_m"] <= longest < band["longest_axis_max_m"], \
        "scale-class 'medium' does not contain the measured longest axis %.4f" % longest

    sem = {
        "schema_version": 1, "facets_version": facets_reg["version"],
        "facets": facets,
        "tag_stamps": {"%s/%s" % (facet, t): {"epistemic": "authored"}
                       for facet, tags in facets.items() for t in tags},
        "palette": {
            "method": "authored",
            "colors": [
                {"hex_srgb": "#ab7f53", "linear_rgb": [0.3712, 0.2158, 0.0865],
                 "weight": 0.82, "name": "softwood"},
                {"hex_srgb": "#6d4622", "linear_rgb": [0.1620, 0.0648, 0.0152],
                 "weight": 0.18, "name": "shadowed grain"},
            ],
            "dominant_index": 0, "average_luminance": 0.31,
        },
        "description": "A slatted wooden shipping crate with open sides and a "
                       "hollow interior, roughly a metre on a side. The gaps "
                       "between slats are why it rings rather than thuds.",
        "keywords": ["crate", "wooden", "container", "slatted", "hollow", "prop"],
        "note": "Facet tags are hand-authored against spec/facets.json, which "
                "travels in this package, and every tag is stamped 'authored' "
                "rather than laundered from the vision model's guesses. "
                "scale-class 'medium' was checked arithmetically against the "
                "registry's own band: the measured longest axis is %.4f m and the "
                "band is [%.1f, %.1f)." % (longest, band["longest_axis_min_m"],
                                           band["longest_axis_max_m"]),
    }
    sem_f = put("semantics/semantics.json", jbytes(sem))
    node("semantics", "core.semantics",
         version([sem_f], "Hand-authored facet tags, palette and search text. This "
                          "node alone renders a browser listing (law 9).",
                 "fixtures/build_golden.py", "1", "authored"),
         edges=[{"to": "geom-game", "kind": "enhances", "role": "describes"}])

    # -- properties: the authored wood region ----------------------------
    def num(value, unit, src_txt, rng=None):
        d = {"value": value, "unit": unit, "epistemic": "authored", "source": src_txt}
        if rng:
            d["range"] = rng
        return d

    props = {
        "schema_version": 1, "registry_version": 1,
        "regions": [{
            "region_id": "crate-body", "material_id": "wood", "part_id": "crate",
            "label": "Sawn softwood slats and frame",
            "properties": {
                "mechanical": {
                    "density": num(500.0, "kg/m^3", "engineering handbook, "
                                   "kiln-dried softwood at 12 percent moisture",
                                   [350.0, 650.0]),
                    "youngs_modulus": num(1.1e10, "Pa", "along the grain; across "
                                          "the grain it is roughly 30x lower",
                                          [8.0e9, 1.4e10]),
                    "poisson_ratio": num(0.37, "1", "handbook value for softwood "
                                         "longitudinal-radial"),
                    "compressive_strength": num(4.0e7, "Pa", "parallel to grain"),
                    "hardness_mohs": num(2.5, "1", "scratched by a copper coin, not "
                                         "by a fingernail"),
                },
                "thermal": {
                    "conductivity": num(0.13, "W/(m*K)", "dry softwood across grain"),
                    "specific_heat": num(1700.0, "J/(kg*K)", "dry wood"),
                    "emissivity": num(0.9, "1", "long-wave infrared, unfinished wood"),
                    "chars_before_melting": {"value": True, "epistemic": "authored",
                                             "source": "wood pyrolyses; it has no "
                                                       "melting point at all"},
                },
                "flammability": {
                    "class": {"value": "flammable", "epistemic": "authored",
                              "source": "untreated softwood"},
                    "autoignition_point": num(300.0, "degC", "typical for cellulose",
                                              [250.0, 350.0]),
                    "heat_of_combustion": num(18.0, "MJ/kg", "dry wood"),
                    "produces_embers": {"value": True, "epistemic": "authored",
                                        "source": "glowing char is the point"},
                    "self_extinguishing": {"value": False, "epistemic": "authored"},
                },
            },
        }],
        "note": "AUTHORED, not inferred: these are handbook values for kiln-dried "
                "softwood written down by a person, with the reference named in "
                "each 'source'. No vision model guessed a Young's modulus here - "
                "and if one ever does, law 5 requires it be stamped 'inferred' with "
                "a plausible range, never laundered into these numbers.",
    }
    props_f = put("properties/properties.json", jbytes(props))
    node("props", "core.props",
         version([props_f], "Authored simulation properties for the crate's wood, "
                            "with every value carrying its own unit and stamp.",
                 "fixtures/build_golden.py", "1", "authored"),
         edges=[{"to": "material-wood", "kind": "enhances", "role": "properties-of"}])

    # -- provenance ------------------------------------------------------
    prov = {
        "schema_version": 1,
        "runs": [
            {"run_id": "splat-foley-example", "started": "2026-07-30T00:00:00Z",
             "finished": "2026-07-30T00:00:00Z",
             "tool": {"name": "splat-foley", "version": "0.4"},
             "models": [{"role": "describe", "id": "qwen2.5-vl-7b-instruct"},
                        {"role": "segment", "id": "segment-anything"},
                        {"role": "generate-audio", "id": "stable-audio-open-1.0"},
                        {"role": "score-clap", "id": "clap"},
                        {"role": "caption-audio", "id": "audio-captioner"}],
             "produced": ([{"node_id": "evidence-views", "v": 1},
                           {"node_id": "evidence-segments", "v": 1},
                           {"node_id": "audio-package", "v": 1}]
                          + [{"node_id": n, "v": 1} for n in effect_nodes]),
             "note": "The original splat-foley run. Its outputs are copied into this "
                     "package byte for byte; nothing was regenerated."},
            {"run_id": "werk-golden-build", "started": CREATED, "finished": CREATED,
             "tool": {"name": "fixtures/build_golden.py", "version": "1"},
             "consumed": [{"path": "geometry/source.glb",
                           "sha256": sha256(files["geometry/source.glb"])}],
             "produced": [{"node_id": "geom-game", "v": 1},
                          {"node_id": "bounds", "v": 1},
                          {"node_id": "material-wood", "v": 1},
                          {"node_id": "semantics", "v": 1},
                          {"node_id": "props", "v": 1}],
             "gates": [{"name": "minimal-sphere-encloses-every-vertex", "passed": True},
                       {"name": "facet-tags-in-registry", "passed": True},
                       {"name": "scale-class-band-contains-longest-axis",
                        "passed": True}],
             "note": "The werk packaging pass: normals, linear vertex colour, exact "
                     "bounds, authored material, facets and properties. Each gate "
                     "above is asserted in build_golden.py, so a failure stops the "
                     "build rather than shipping a wrong number."},
        ],
    }
    prov_f = put("provenance/provenance.json", jbytes(prov))
    node("provenance", "core.provenance",
         version([prov_f], "Who made what, from what, with which models, and which "
                           "gates it had to pass.",
                 "fixtures/build_golden.py", "1", "authored"))

    # -- spec + loaders + license + readme nodes -------------------------
    node("spec", "core.spec",
         version(spec_files, "The format specification, its schemas and its binary "
                             "layout grammars, travelling inside the file it "
                             "describes (law 2).",
                 "werk", "0.1", "authored"))
    for node_id, fname, lang, toolchain, build, caps in loader_specs:
        with open(os.path.join(ROOT, "loaders", fname), "rb") as fh:
            data = fh.read()
        f = put("loaders/" + fname, data)
        meta = {"language": lang, "form": "source", "entrypoint": "loaders/" + fname,
                "toolchain": toolchain, "dependencies": [],
                "capabilities": caps or loader_capabilities(data)}
        if build:
            meta["build_command"] = build
        node(node_id, "core.loader",
             version([f], "A single-file, dependency-free reader for this package, "
                          "carried as payload so the file brings its own reader "
                          "(law 1).", "werk", "0.1", "authored"),
             meta=meta)
    node("license", "core.license",
         version([lic_f], "The full licence text, embedded, never a link (law 7).",
                 "werk", "0.1", "authored"))
    node("readme", "core.readme",
         version([readme_f], "One page for a human who opened this file and wants "
                             "to know what it is.", "werk", "0.1", "authored"))

    return files, nodes, {"longest": longest, "radius": radius, "verts": len(pos),
                          "tris": len(idx), "wavs": total_wavs,
                          "effects": len(pkg_effects)}


def build_manifest(files, nodes, preview_prefix, extra_summary=""):
    schemas = {
        "core.material": "spec/schemas/core.material.schema.json",
        "core.phys.bounds": "spec/schemas/core.phys.bounds.schema.json",
        "core.audio.package": "spec/schemas/core.audio.package.schema.json",
        "core.audio.effect": "spec/schemas/core.audio.effect.schema.json",
        "core.audio.ambience": "spec/schemas/core.audio.effect.schema.json",
        "core.semantics": "spec/schemas/core.semantics.schema.json",
        "core.props": "spec/schemas/core.props.schema.json",
        "core.provenance": "spec/schemas/core.provenance.schema.json",
    }
    return {
        "werk": {"major": 1, "minor": 0},
        "profile": "3d-entity/1",
        "entity": {
            "uuid": ENTITY_UUID,
            "name": "Wooden crate",
            "summary": "A slatted wooden shipping crate with a complete sound "
                       "world: twenty generated effects and ambiences, every take "
                       "and every gate score kept. Conformance fixture #1, built "
                       "from a real splat-foley run - the geometry, the views, the "
                       "segment crops and every WAV are that run's actual output. "
                       "Signed with a publicly derived DEV key that proves the "
                       "chain works and nothing about authorship." + extra_summary,
            "created": CREATED,
        },
        "conventions": {
            "endianness": "le", "units_per_meter": 1.0, "length_unit": "metre",
            "angle_unit": "radian", "time_unit": "second", "mass_unit": "kilogram",
            "up_axis": "y", "forward_axis": "-z", "right_axis": "+x",
            "handedness": "right", "winding": "ccw", "quat_order": "wxyz",
            "oct_encoding_pole": "y", "sh_l1_order": ["dc", "y", "z", "x"],
            "color_space_default": "srgb", "uv_origin": "top-left",
            "alignment_bytes": 16, "text_encoding": "utf-8", "id_case": "kebab-case",
            "hash_algorithm": "sha256", "signature_algorithm": "ed25519",
        },
        "container": {
            "form": "zip", "zip_compression": "store",
            "entry_order": list(ENTRY_ORDER),
            "preview_prefix_bytes": preview_prefix,
        },
        # Which node to reach for when a consumer wants exactly one of
        # something. No `image`: this crate has no imposter and no base-colour
        # texture, and the rendered evidence views sit outside the preview
        # prefix, so claiming one would break the schema's own guidance. An
        # absent key is the honest answer. (S-13.)
        "primary": {"mesh": "geom-game",
                    "sound": slug_id("audio", PREVIEW_SLUG)},
        "license": {"spdx_id": "CC-BY-4.0", "file": "LICENSE",
                    "sha256": sha256(files["LICENSE"])},
        # S-29: the revision of spec/ this package carries, so a reader can
        # tell in one comparison whether the schemas travelling inside the
        # file are the ones it already knows. Mandatory.
        "spec_sha256": spec_sha256_of_files(files),
        # S-17: the convention -> node-type map as DATA, declared rather than
        # derived, so a reader that does not support a convention refuses
        # exactly the nodes it governs instead of transcribing a prose table
        # into a constant.
        "conventions_map": "spec/conventions-map.json",
        "schemas": schemas,
        "layouts": {},
        "parts": [{"part_id": "crate", "name": "Wooden crate", "parent": None,
                   "transform": {"translation": [0.0, 0.0, 0.0],
                                 "rotation": [1.0, 0.0, 0.0, 0.0],
                                 "scale": [1.0, 1.0, 1.0]}}],
        "materials": [{"material_id": "wood", "part_id": "crate",
                       "name": "Crate softwood", "class": "wood"}],
        "nodes": nodes,
    }


def sign(manifest_bytes, role_note):
    return build_chain(sha256(manifest_bytes), [{
        "secret": DEV_SK,
        "name": "werk dev key (publicly derived, fixtures only)",
        "uri": "urn:werk:dev-key:build-golden",
        "kind": "service",
        "role": "author",
        "signed_at": CREATED,
        "note": role_note,
    }])


def assemble(files, nodes, extra_summary=""):
    """Iterate preview_prefix_bytes to a fixed point: the prefix length depends
    on the manifest's own size and the manifest declares the prefix length."""
    # SPEC 2.1 (S-XV-4 / S-OW-2): say which file IS each multi-file node's
    # payload, before anything hashes the manifest.
    annotate_payload_files(nodes)
    # SPEC 5: never write a `requires` edge to a node not in nodes[].
    refuse_dangling_requires(nodes)
    preview = 0
    for _round in range(8):
        manifest_bytes = jbytes(build_manifest(files, nodes, preview, extra_summary))
        sig_bytes = jbytes(sign(manifest_bytes,
                                "Signed with a DEV key derived from a published "
                                "sentence. It is not secret, it is not a trust "
                                "anchor, and it proves only that the chain verifies."))
        allf = dict(files)
        allf["MANIFEST.json"] = manifest_bytes
        allf["SIGNATURE.json"] = sig_bytes
        order = order_entries(allf.keys())
        entries = [(p, allf[p]) for p in order]
        cursor, prefix = 0, 0
        for name, data in entries:
            this = 30 + len(name.encode("utf-8")) + len(data)
            if is_preview(name):
                prefix = cursor + this
            cursor += this
        if prefix == preview:
            return manifest_bytes, sig_bytes, entries
        preview = prefix
    raise SystemExit("preview_prefix_bytes did not converge")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(
        os.environ.get("WERK_LAB", "<WERK_LAB unset>"), "splat-foley", "outputs", "example"))
    ap.add_argument("--out", default=HERE)
    args = ap.parse_args(argv)

    files, nodes, stats = collect(args.src, args.out)
    manifest_bytes, sig_bytes, entries = assemble(files, nodes)
    blob = write_zip(entries)
    zip_path = os.path.join(args.out, "crate-v1.werk")
    with open(zip_path, "wb") as fh:
        fh.write(blob)

    print("wrote %s" % zip_path)
    print("  %d bytes, sha256 %s" % (len(blob), sha256(blob)))
    print("  %d entries, %d nodes, %d declared files"
          % (len(entries), len(nodes), sum(len(v["files"])
                                           for n in nodes for v in n["versions"])))
    print("  manifest %d bytes, sha256 %s" % (len(manifest_bytes),
                                              sha256(manifest_bytes)))
    prefix = json.loads(manifest_bytes)["container"]["preview_prefix_bytes"]
    print("  preview_prefix_bytes %d (%.2f%% of the archive)"
          % (prefix, 100.0 * prefix / len(blob)))
    print("  mesh %d verts / %d tris, longest axis %.4f m, sphere r=%.4f m"
          % (stats["verts"], stats["tris"], stats["longest"], stats["radius"]))
    print("  audio %d effects, %d wavs" % (stats["effects"], stats["wavs"]))

    # ---- the damaged variant ------------------------------------------
    # Order matters and is the point: the mystery node goes in BEFORE signing,
    # so the chain is valid; the payload byte is flipped AFTER, so the damage is
    # caught by the per-file hash and NOT by the signature. Corrupting a payload
    # does not invalidate a signature - the chain signs the manifest and the
    # manifest hashes the files - and a reader that says otherwise is naming the
    # wrong fact.
    dfiles = dict(files)
    dnodes = [json.loads(json.dumps(n)) for n in nodes]
    # Deliberately NOT an envelope binary: no WK** magic, so a reader has no
    # grammar to try and nothing to fail at. The point of this node is law 12 —
    # listed, hash-verified, resolved, and SKIPPED with a report — not damage.
    # Unknown-because-newer and broken-because-damaged must degrade through the
    # same path, and the damaged fixture carries one of each so the two report
    # codes can be told apart.
    mystery = (b"x.werk-future.mystery v1\n"
               b"A payload shape that does not exist yet. If you are reading this "
               b"in a reader that understands it, this fixture is older than you.\n")
    dfiles["x/mystery/blob.bin"] = mystery
    dnodes.append({
        "node_id": "mystery", "type": "x.werk-future.mystery",
        "versions": [{"v": 1,
                      "files": [{"path": "x/mystery/blob.bin",
                                 "sha256": sha256(mystery), "size": len(mystery)}],
                      "note": "A node type from a version of the format this reader "
                              "has never heard of. It must be listed, hash-verified "
                              "and skipped WITH A REPORT - never a failure (law 12).",
                      "producer": {"tool": "fixtures/build_golden.py", "version": "1"},
                      "epistemic": "authored", "created": CREATED}],
        "active": 1, "edges": []})
    dmanifest, dsig, dentries = assemble(
        dfiles, dnodes,
        " DAMAGED VARIANT: one node's payload byte is flipped and one node "
        "carries a type no current reader knows.")
    target = "audio/sfx/crate-impact-hard-surface.wav"
    dentries = [(p, (d[:1000] + bytes([d[1000] ^ 0xFF]) + d[1001:]) if p == target else d)
                for p, d in dentries]
    dblob = write_zip(dentries)
    dpath = os.path.join(args.out, "crate-v1-damaged.werk")
    with open(dpath, "wb") as fh:
        fh.write(dblob)
    print("wrote %s" % dpath)
    print("  %d bytes, sha256 %s" % (len(dblob), sha256(dblob)))
    print("  damage: 1 flipped byte in %s (offset 1000), plus node type "
          "x.werk-future.mystery" % target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
