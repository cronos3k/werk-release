#!/usr/bin/env python3
"""build_image_fixture.py — conformance fixture #2: a real generated image.

Builds `fixtures/ista-varun-v1.werk`, profile `image/1`
(`spec/PROFILE-IMAGE.md`), from a genuinely AI-generated image and its
genuinely recorded recipe.

    python fixtures/build_image_fixture.py [--src <WERK_LAB>/SFNovels] [--out DIR]

WHY THIS IMAGE. It is the only candidate in the source repository whose
assembled prompt was actually PERSISTED at generation time — in
`platform5d6/data/artifacts.db`, in a row whose `updated_at` matches the PNG's
mtime to two milliseconds — and whose one input medium (the style plate) is
still on disk. Everything in `recipe/recipe.json` is read out of that database,
out of that image, or out of the producing pipeline's own source, at build
time. Nothing is typed in from memory.

WHAT IS DELIBERATELY IMPERFECT, because it is what actually happened:

  * the recipe is graded `descriptive`, not `deterministic` — the model is
    hosted, no weight file exists to hash and the API exposes no seed;
  * the prompt the pipeline persisted is ONE SENTENCE SHORTER than the string
    it transmitted, because the client appends a style-reference sentence
    after the caller has already recorded the prompt. Recipe v1 records what
    was persisted; recipe v2 records the reconstructed transmitted string plus
    the code excerpt it was rebuilt from. That is why the recipe node has two
    versions, and it is the honest shape of an audit rather than a tidy-up;
  * `unrecorded[]` names six facts nobody captured.

WHAT IT EXERCISES that no previously handed-out fixture did:

  * a **custom binary**: `semantics/style-embedding.wkem`, magic `WKEM`, so
    `spec/layouts/ENVELOPE.layout.txt` finally gets run rather than merely
    read (the fixture gap `gauntlet/RESULTS.md` declared after run 1);
  * both branches of the envelope's section consistency rule, one section
    each;
  * `core.recipe` and `core.disclosure`;
  * the S-18 case: one node whose v2 relists a file v1 already listed,
    unchanged, with identical path, hash and size;
  * the S-14 case: an `entry_order` with exact paths interleaved between
    directory prefixes, including a prefix listed AFTER exact members of the
    same directory;
  * an `x.*` node a reader must skip and report (`x.c2pa.export`).

DEPENDENCIES. Unlike `build_golden.py` this builder is not stdlib-only: it
needs Pillow (to decode and resample the PNGs) and numpy (for the descriptor
in `labhog.py`). Neither travels inside the package — law 1's dependency ban
is about what ships in the file, and a builder is not a `core.loader`.
"""

import argparse
import hashlib
import importlib.util
import json
import math
import os
import sqlite3
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# S-29, ruled 2026-08-08: every manifest declares a spec_sha256 over the spec/
# tree it carries. tools/spec_sha256.py is the reference implementation and
# carries the algorithm in its docstring; importing it rather than re-deriving
# it here is the point of having one.
sys.path.insert(0, ROOT)                                 # pipeline.det_png
sys.path.insert(0, os.path.join(ROOT, "tools"))
from spec_sha256 import spec_sha256_of_files          # noqa: E402
from payload_file import annotate_payload_files       # noqa: E402
from loader_caps import loader_capabilities        # noqa: E402
from edge_targets import refuse_dangling_edges     # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "store"))
sys.path.insert(0, HERE)
from werkstore.signature import build_chain  # noqa: E402
import labhog  # noqa: E402

# The canonical MessagePack writer already lives in the spec's own example
# generator, and there must be exactly one of it: if this file carried a second
# copy, a divergence between them would be a spec bug nobody could see.
_mk_spec = importlib.util.spec_from_file_location(
    "werk_make_examples", os.path.join(ROOT, "spec", "examples", "make-examples.py"))
_mk = importlib.util.module_from_spec(_mk_spec)
_mk_spec.loader.exec_module(_mk)
mp_encode = _mk.mp_encode
align16 = _mk.align16

CREATED = "2026-08-08T12:00:00Z"
ENTITY_UUID = "b9c4e0d1-5a68-4f2b-8c73-1e0a95d7f4a6"

# The dev key, derived from a published sentence exactly as fixture #1's is,
# and for the same reason: a fixture that shipped a real key would be a leak
# and one that shipped a random key would not be reproducible.
DEV_KEY_PHRASE = b"werk dev key, publicly derived, fixtures only, 2026-08-08"
DEV_SK = hashlib.sha256(DEV_KEY_PHRASE).digest()

# The generation, as recorded by the producing pipeline.
GENERATED_AT = "2026-07-17T03:34:31Z"
DB_URN = "book/01-the-concordance-of-echoes/design/characters/ista-varun"
SRC_IMAGE = "output/visual-bible/01-the-concordance-of-echoes/characters/ista-varun.png"
SRC_PLATE = "platform5d6/data/style/plates/5d6/imperial-painterly.png"
SRC_DB = "platform5d6/data/artifacts.db"
SRC_CODE = [
    ("visual_bible_engine/src/design_book.py", "design_book"),
    ("visual_bible_engine/src/forge.py", "design"),
    ("visual_bible_engine/src/nanobanana_client.py", "design"),
    ("platform5d6/core/style_bible.py", "design_prompt"),
    ("platform5d6/core/style_bible.py", "for_model"),
]

# The sentence the client appends AFTER the caller has recorded the prompt.
# Asserted against the source at build time, never trusted from memory.
TRAILING_SENTENCE = (
    " The attached 1 image(s) are STYLE references \u2014 match their painterly "
    "rendering, palette and mood.")

PREVIEW_W, THUMB_W = 1024, 256

ENTRY_ORDER = [
    "MANIFEST.json",
    "SIGNATURE.json",
    "LICENSE",
    "README.txt",
    "loaders/",
    "spec/",
    "semantics/",
    "disclosure/",
    # Exact paths, deliberately listed BEFORE the "recipe/" prefix below, so
    # the browsable tier gets the record and the prompts without dragging the
    # 1.5 MB of embedded input media in with them. This is the S-14 two-pass
    # matching rule being used rather than described.
    "recipe/recipe.json",
    "recipe/recipe@1.json",
    "recipe/prompt-recorded.txt",
    "recipe/prompt-transmitted.txt",
    "recipe/evidence/",
    "image/thumb-256.png",
    "recipe/",
    "image/",
    "provenance/",
    "x/",
]
PREVIEW_SET = ENTRY_ORDER[: ENTRY_ORDER.index("image/thumb-256.png") + 1]

FLAG_UTF8 = 0x0800
# The one fixed timestamp werk uses, so a rewrite is byte-identical: 2026-08-08
# 09:00:00. It MUST match core/src/zipstore.rs — a different constant here
# costs nothing visible and fails the round-trip gate by three bytes per
# entry, which is exactly how it was found.
DOS_TIME = (9 << 11) | (0 << 5)
DOS_DATE = ((2026 - 1980) << 9) | (8 << 5) | 8


# ---------------------------------------------------------------------------
# small helpers, same spellings as build_golden.py
# ---------------------------------------------------------------------------

def sha256(b):
    return hashlib.sha256(b).hexdigest()


def jbytes(v):
    return (json.dumps(v, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def input_hash(paths, files):
    h = hashlib.sha256()
    for p in paths:
        h.update(hashlib.sha256(files[p]).digest())
    h.update(b"{}")
    return h.hexdigest()


CRC_TABLE = []


def crc32(data):
    if not CRC_TABLE:
        for i in range(256):
            c = i
            for _ in range(8):
                c = (c >> 1) ^ (0xEDB88320 if c & 1 else 0)
            CRC_TABLE.append(c)
    c = 0xFFFFFFFF
    for b in data:
        c = CRC_TABLE[(c ^ b) & 0xFF] ^ (c >> 8)
    return c ^ 0xFFFFFFFF


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


def matches(path, pattern):
    """The S-14 rule: a trailing '/' is a directory prefix, anything else is an
    exact path."""
    return path.startswith(pattern) if pattern.endswith("/") else path == pattern


def order_entries(paths):
    remaining = sorted(paths)
    out = []
    for pat in ENTRY_ORDER:
        picked = [p for p in remaining if matches(p, pat)]
        for p in picked:
            remaining.remove(p)
            out.append(p)
    return out + remaining


def is_preview(name):
    return any(matches(name, p) for p in PREVIEW_SET)


def png_info(b):
    assert b[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    ln, tag = struct.unpack(">I4s", b[8:16])
    assert tag == b"IHDR"
    w, h, depth, color = struct.unpack(">IIBB", b[16:26])
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
    return {"width": w, "height": h, "bit_depth": depth, "channels": channels,
            "color_type": color}


def png_chunks(b):
    """Chunk type list, so 'this file carries no text metadata' is a
    measurement rather than an assumption."""
    off, out = 8, []
    while off + 8 <= len(b):
        ln, tag = struct.unpack(">I4s", b[off:off + 8])
        out.append(tag.decode("ascii", "replace"))
        off += 12 + ln
    return out


def derived_height(src_w, src_h, dst_w):
    """floor(w * H / W + 0.5) — stated, because 'resize to 1024 wide' does not
    say what happens to the odd half pixel and two libraries disagree."""
    return int(math.floor(dst_w * src_h / float(src_w) + 0.5))


def linear_to_hex(rgb):
    def enc(c):
        c = min(1.0, max(0.0, c))
        s = 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055
        return int(math.floor(s * 255.0 + 0.5))
    return "#%02x%02x%02x" % tuple(enc(c) for c in rgb)


# ---------------------------------------------------------------------------
# the WKEM writer — spec/layouts/embedding.layout.txt
# ---------------------------------------------------------------------------

def build_wkem(vec, palette, extra_header):
    vec_bytes = labhog.as_f32_bytes(vec)
    pal_bytes = labhog.as_f32_bytes(palette.reshape(-1))
    dim = len(vec)
    swatches = palette.shape[0]

    # Two passes: the header declares absolute offsets, and the offsets depend
    # on the header's own length. Write it once with placeholders, measure, and
    # write it again — never compute an offset a reader is told is declared.
    def emit(payload_origin, off_vec, off_pal):
        head = dict(extra_header)
        head.update({
            "kind": "core.embedding",
            "endianness": "le",
            "payload_origin": payload_origin,
            "payload_size": (off_pal + len(pal_bytes)) - payload_origin,
            "sections": [
                {"name": "vector", "offset": off_vec, "size": len(vec_bytes),
                 "dtype": "f32", "shape": [dim], "stride": 4},
                {"name": "palette", "offset": off_pal, "size": len(pal_bytes),
                 "dtype": "f32", "shape": [swatches, 4], "stride": 16},
            ],
        })
        return mp_encode(head)

    hdr = emit(0, 0, 0)
    for _ in range(8):
        origin = align16(12 + len(hdr))
        off_vec = origin
        off_pal = align16(off_vec + len(vec_bytes))
        nxt = emit(origin, off_vec, off_pal)
        if len(nxt) == len(hdr):
            hdr = nxt
            break
        hdr = nxt
    else:
        raise SystemExit("WKEM header length did not converge")

    origin = align16(12 + len(hdr))
    off_vec = origin
    off_pal = align16(off_vec + len(vec_bytes))
    out = bytearray()
    out += b"WKEM" + struct.pack("<II", 1, len(hdr)) + hdr
    out += b"\x00" * (origin - len(out))
    out += vec_bytes
    out += b"\x00" * (off_pal - len(out))
    out += pal_bytes
    if len(out) % 16:
        out += b"\x00" * (16 - len(out) % 16)
    return bytes(out)


# ---------------------------------------------------------------------------
# reading the evidence out of the producing pipeline
# ---------------------------------------------------------------------------

def extract_def(text, name):
    """Return (first_line_no, lines) for `def <name>(`, to the end of its block
    by indentation. Anchored on the name rather than on a line number, because
    a line number in a file nobody in this repo controls is a footgun."""
    lines = text.splitlines()
    start = None
    for i, ln in enumerate(lines):
        s = ln.lstrip()
        if s.startswith("def %s(" % name):
            start = i
            indent = len(ln) - len(s)
            break
    if start is None:
        raise SystemExit("no def %s( found" % name)
    end = start + 1
    while end < len(lines):
        ln = lines[end]
        if ln.strip() and (len(ln) - len(ln.lstrip())) <= indent:
            break
        end += 1
    return start + 1, lines[start:end]


def read_recorded_prompt(db_path):
    con = sqlite3.connect(db_path)
    try:
        row = con.execute(
            "select recipe, outputs, updated_at from artifacts where urn = ?",
            (DB_URN,)).fetchone()
    finally:
        con.close()
    if not row:
        raise SystemExit("no artifacts.db row for %s" % DB_URN)
    recipe = json.loads(row[0])
    return recipe["prompt"], json.loads(row[1]), row[2]


def build_evidence(src_root):
    """One text file carrying the exact source the reconstruction was made
    from, with each source file's own sha256, so the evidence is checkable
    against the repository it came out of."""
    parts = [
        "werk fixture #2 — pipeline source evidence",
        "=" * 64,
        "",
        "Why this file exists: recipe/prompt-transmitted.txt is RECONSTRUCTED,",
        "not recorded. core.recipe.schema.json requires a reconstruction to say",
        "how it was rebuilt and from what. This is the what: the exact source of",
        "the producing pipeline, as it stood when this package was built,",
        "extracted verbatim and hashed.",
        "",
        "Each block gives the source file's path in its own repository, that",
        "FILE's sha256 (not this excerpt's), and the line range extracted.",
        "",
    ]
    for rel, defname in SRC_CODE:
        full = os.path.join(src_root, rel.replace("/", os.sep))
        with open(full, "rb") as fh:
            raw = fh.read()
        text = raw.decode("utf-8")
        first, block = extract_def(text, defname)
        parts += [
            "-" * 64,
            "file      : %s" % rel,
            "sha256    : %s   (of the whole file, %d bytes)" % (sha256(raw), len(raw)),
            "extracted : def %s, lines %d-%d" % (defname, first, first + len(block) - 1),
            "-" * 64,
            "",
        ]
        parts += block
        parts += [""]
    return ("\n".join(parts) + "\n").encode("utf-8")


# ---------------------------------------------------------------------------
# payload documents
# ---------------------------------------------------------------------------

LICENSE_TEXT = """werk conformance fixture #2 — licence

Creative Commons Attribution 4.0 International (CC BY 4.0), to the extent that
copyright subsists in the image at all. This is the FULL LICENCE TEXT,
embedded, because law 7 says a licence travels as text and never as a link. A
werk file that pointed at a URL for its terms would be a promise about another
file, which law 1 bans.

You are free to:
  Share - copy and redistribute the material in any medium or format.
  Adapt - remix, transform, and build upon the material for any purpose, even
  commercially.
The licensor cannot revoke these freedoms as long as you follow the licence
terms.

Under the following terms:
  Attribution - You must give appropriate credit, provide a link to the
  licence, and indicate if changes were made. You may do so in any reasonable
  manner, but not in any way that suggests the licensor endorses you or your
  use.
  No additional restrictions - You may not apply legal terms or technological
  measures that legally restrict others from doing anything the licence
  permits.

Notices:
  You do not have to comply with the licence for elements of the material in
  the public domain or where your use is permitted by an applicable exception
  or limitation.
  No warranties are given. The licence may not give you all of the permissions
  necessary for your intended use.

A NOTE ON WHAT IS BEING LICENSED, because a licence that overclaims is worse
than none. The image in this package was produced wholly by a generative
model from a prompt a human wrote. Whether copyright subsists in such an
image, and in whom, is unsettled in several jurisdictions. This licence
grants what the licensor has to grant and makes no claim beyond it. The
prompt, the subject description, the style register and the exclusion list
are human-authored and are licensed on the same terms. See
disclosure/disclosure.json for the machine-readable version of these facts,
and spec/SPEC.md section 3.12 for why this file states them rather than
enforcing anything about them.

Attribution: Gregor Hubert Max Koch, "Ista Varun" character design plate,
from the 5D6 Space setting.
"""

README_TEXT = """werk conformance fixture #2 - a real generated image
====================================================

This is a werk package, profile image/1. It is hermetic: everything needed to
read it is inside it. spec/ carries the specification, the schemas and the
layout grammars; loaders/ carries three single-file zero-dependency readers,
one Python, one Rust, one C. Start with spec/README.md - and note its row 0,
because this package is profile image/1 and its manifest is validated by
spec/schemas/manifest.image.schema.json, not by the 3D profile's schema.

What is in it: one AI-generated image, two derived sizes of it, the real
recipe that produced it, a machine-readable disclosure, a style descriptor as
a custom binary, facet tags and a palette, a provenance record, and a
signature chain.

Three things worth knowing before you read the recipe:

1. The recipe is graded DESCRIPTIVE, not deterministic. The model is hosted:
   there is no weight file to hash and the API exposes no seed. Re-running the
   recipe would produce a different image that follows the same instructions.
   recipe/recipe.json says so in reproducibility_note, and its unrecorded[]
   array names six facts nobody captured at the time.

2. The recipe node has TWO VERSIONS, and that is the point. v1 records the
   prompt the pipeline actually persisted. Auditing the pipeline's source
   later showed that the string TRANSMITTED to the model was one sentence
   longer - the client appends a style-reference sentence after the caller has
   already stored the prompt. v2 records the reconstructed transmitted string
   and the code excerpt it was rebuilt from, and relists the files that did
   not change. v1 is kept, because law 6 says old versions are never
   rewritten.

3. semantics/style-embedding.wkem is a CUSTOM BINARY. Magic "WKEM", read
   spec/layouts/ENVELOPE.layout.txt first and then
   spec/layouts/embedding.layout.txt. It carries a 72-component descriptor and
   an 8-swatch palette, and the descriptor is defined completely enough in the
   layout file that you can recompute it from image/source.png and check it.

It is signed with a DEV KEY derived from a published sentence, so it is not
secret and it is not a trust anchor. The signature proves the chain works; it
proves nothing about authorship.

Two rulings this package leans on are marked PROPOSED - draft-pending-Gregor
in spec/SPEC.md: S-14 (how container.entry_order matches) and S-18 (a file may
be listed by several versions of ONE node). The recipe node's v2 relies on
S-18. If S-18 is decided the other way, that version copies a file and nothing
else here moves.
"""


# ---------------------------------------------------------------------------
# the build
# ---------------------------------------------------------------------------

def collect(src_root):
    from PIL import Image

    files = {}
    nodes = []
    stats = {}

    def put(path, data, media=None, role=None):
        assert path not in files, "two nodes claim %s" % path
        files[path] = data
        f = {"path": path, "sha256": sha256(data), "size": len(data)}
        if media:
            f["media_type"] = media
        if role:
            f["role"] = role
        return f

    def ref(path, media=None, role=None):
        """A second reference to a file that is already in the package — the
        S-18 case. Same path, same hash, same size, by construction."""
        data = files[path]
        f = {"path": path, "sha256": sha256(data), "size": len(data)}
        if media:
            f["media_type"] = media
        if role:
            f["role"] = role
        return f

    def node(node_id, ntype, versions, edges=(), meta=None, active=None):
        n = {"node_id": node_id, "type": ntype, "versions": versions,
             "active": active or len(versions), "edges": list(edges)}
        if meta:
            n["meta"] = meta
        nodes.append(n)
        return n

    def version(v, fs, note, tool, tver, epistemic, created=CREATED,
                model=None, inputs=None, confidence=None, supersedes=None):
        out = {"v": v, "files": fs, "note": note,
               "producer": {"tool": tool, "version": tver},
               "epistemic": epistemic, "created": created}
        if model:
            out["producer"]["model"] = model
        if inputs:
            out["input_files"] = list(inputs)
            out["input_hash"] = input_hash(inputs, files)
            out["input_params"] = {}
        if confidence is not None:
            out["confidence"] = confidence
        if supersedes:
            out["supersedes"] = supersedes
        return out

    # -- LICENSE / README -------------------------------------------------
    lic_f = put("LICENSE", LICENSE_TEXT.encode("utf-8"), "text/plain")
    readme_f = put("README.txt", README_TEXT.encode("utf-8"), "text/plain")

    # -- spec/ and loaders/ -----------------------------------------------
    spec_files = []
    for dirpath, _dirs, names in os.walk(os.path.join(ROOT, "spec")):
        for nm in sorted(names):
            if nm.endswith(".pyc"):
                continue
            full = os.path.join(dirpath, nm)
            rel = "spec/" + os.path.relpath(
                full, os.path.join(ROOT, "spec")).replace("\\", "/")
            with open(full, "rb") as fh:
                data = fh.read()
            media = ("application/json" if nm.endswith(".json")
                     else "text/markdown" if nm.endswith(".md") else "text/plain")
            spec_files.append(put(rel, data, media))
    spec_files.sort(key=lambda f: f["path"])

    loader_meta = [
        ("loader-python", "loaders/werk_read.py", "python", "python>=3.8", "",
         "text/x-python"),
        ("loader-rust", "loaders/werk_read.rs", "rust", "rustc>=1.70",
         "rustc -O --edition 2021 -o werk_read loaders/werk_read.rs", "text/x-rust"),
        ("loader-c", "loaders/werk_read.c", "c", "c99",
         "cc -std=c99 -O2 -o werk_read loaders/werk_read.c", "text/x-c"),
    ]

    # -- the image and its derivatives ------------------------------------
    with open(os.path.join(src_root, SRC_IMAGE.replace("/", os.sep)), "rb") as fh:
        src_png = fh.read()
    info = png_info(src_png)
    chunks = png_chunks(src_png)
    text_chunks = [c for c in chunks if c in ("tEXt", "iTXt", "zTXt", "eXIf")]
    stats["src"] = info
    stats["text_chunks"] = text_chunks
    # disclosure/disclosure.json states, as a MEASURED statement, that this PNG
    # carries no text metadata. Assert it, so the statement cannot quietly go
    # stale if the source image is ever replaced by one that does.
    assert not text_chunks, (
        "the source PNG carries %s; disclosure's embedded_metadata_stripped "
        "and its png-metadata-measured statement would be false" % text_chunks)

    src_img = Image.open(os.path.join(src_root, SRC_IMAGE.replace("/", os.sep)))
    src_img.load()

    def derive(width, path):
        h = derived_height(info["width"], info["height"], width)
        im = src_img.convert("RGB").resize((width, h), Image.LANCZOS)
        # Pillow supplies the pixels; the PNG stream is pipeline/det_png.py's,
        # the same bytes on every OS (finding N3).
        from pipeline import det_png
        return h, det_png.encode_pil(im)

    prev_h, prev_png = derive(PREVIEW_W, "image/preview-1024.png")
    thumb_h, thumb_png = derive(THUMB_W, "image/thumb-256.png")

    src_f = put("image/source.png", src_png, "image/png")
    prev_f = put("image/preview-1024.png", prev_png, "image/png")
    thumb_f = put("image/thumb-256.png", thumb_png, "image/png")

    # -- the recipe -------------------------------------------------------
    recorded_prompt, db_outputs, db_updated = read_recorded_prompt(
        os.path.join(src_root, SRC_DB.replace("/", os.sep)))
    assert db_outputs and db_outputs[0].replace("\\", "/").endswith(SRC_IMAGE), (
        "the artifacts.db row does not name the image this fixture is built from")

    nb_path = os.path.join(src_root, "visual_bible_engine", "src",
                           "nanobanana_client.py")
    with open(nb_path, "r", encoding="utf-8") as fh:
        nb_src = fh.read()
    assert "are STYLE references \u2014 match " in nb_src, (
        "the client no longer contains the sentence this reconstruction depends on")
    assert "their painterly rendering, palette and mood." in nb_src
    assert 'MODEL = "gemini-3.1-flash-image"' in nb_src

    transmitted_prompt = recorded_prompt + TRAILING_SENTENCE

    with open(os.path.join(src_root, SRC_PLATE.replace("/", os.sep)), "rb") as fh:
        plate_png = fh.read()
    plate_info = png_info(plate_png)

    evidence = build_evidence(src_root)

    prompt_rec_f = put("recipe/prompt-recorded.txt",
                       (recorded_prompt + "\n").encode("utf-8"), "text/plain",
                       "prompt-recorded")
    plate_f = put("recipe/inputs/imperial-painterly.png", plate_png, "image/png",
                  "input-media")
    evidence_f = put("recipe/evidence/pipeline-source.txt", evidence, "text/plain",
                     "evidence")
    prompt_tx_f = put("recipe/prompt-transmitted.txt",
                      (transmitted_prompt + "\n").encode("utf-8"), "text/plain",
                      "prompt-transmitted")

    def plain(f):
        return {k: v for k, v in f.items() if k in ("path", "sha256", "size")}

    common_step = {
        "step_id": "design",
        "role": "generate",
        "model": {
            "id": "gemini-3.1-flash-image",
            "family": "gemini-image",
            "hosted": True,
            "operator": "Google",
            "weights": {
                "available": False,
                "reason": "Hosted model: the operator publishes no weight file, "
                          "so there is nothing to hash. The id is not a version "
                          "either - the weights behind it may change without "
                          "notice.",
            },
            "note": "Reached through the google-genai Python SDK's "
                    "models.generate_content(). The concrete HTTPS endpoint is "
                    "chosen by the SDK and was not recorded, so no 'endpoint' "
                    "key is given rather than a plausible one being written in.",
        },
        "tool": {
            "name": "visual_bible_engine design_book -> forge.design -> "
                    "NanoBanana2.design",
            "version": "not-recorded",
            "repository_revision": "not-recorded",
        },
        "params": {
            "aspect_ratio": "3:4",
            "image_size": "2K",
            "response_modalities": ["TEXT", "IMAGE"],
            "retries": 4,
            "backoff_seconds": 3.0,
        },
        "seed": {
            "controlled": False,
            "reason": "The hosted image API exposes no seed parameter; the call "
                      "config carries aspect_ratio, image_size and "
                      "response_modalities and nothing else.",
        },
        "inputs": [{
            "role": "style-reference",
            "path": "recipe/inputs/imperial-painterly.png",
            "sha256": plate_f["sha256"],
            "size": plate_f["size"],
            "order": 0,
            "note": "The house style plate, attached automatically because "
                    "use_style_refs defaults to true. No identity references "
                    "were passed, which is why the client took its "
                    "single-style-image branch - the branch whose trailing "
                    "sentence recipe v2 reconstructs.",
        }],
        "outputs": [dict(plain(src_f), media_type="image/png")],
        "note": "One model call. There is no second 'realize' stage in this "
                "path: the compose-then-realize chain belongs to a different "
                "entry point in the same repository and did not run here. The "
                "params above were read from the calling source, not from a "
                "record written at generation time - see unrecorded[].",
    }

    postprocess = [{
        "op": "png-encode",
        "tool": {"name": "Pillow (PIL.Image.save)", "version": "not-recorded"},
        "description": "The API returns pixels; the pipeline wrote them with "
                       "PIL Image.save(). The PNG byte stream is therefore "
                       "Pillow's encoding of the model's output rather than "
                       "bytes the model produced. The pixels are the model's; "
                       "the file is Pillow's, and a reader comparing hashes "
                       "needs to know that.",
        "params": {"format": "PNG", "resize": "none", "crop": "none"},
    }]

    unrecorded_common = [
        "the google-genai client library version, and the Python version, at "
        "generation time",
        "the call parameters as SENT: aspect_ratio, image_size, "
        "response_modalities, retries and backoff are read from the calling "
        "source as it stands today, not from a record written at generation time",
        "the repository revision of the producing pipeline: the writing script "
        "and the image were both untracked in that repository when this image "
        "was made, and its HEAD at the time predates the script",
        "the Pillow version that encoded the PNG",
        "whether the API call was retried: the client retries up to four times "
        "on an empty response and does not record whether it did",
    ]

    recipe_v1 = {
        "recipe_version": 1,
        "target": {"node_id": "image-source", "version": 1,
                   "files": [dict(plain(src_f), media_type="image/png")]},
        "reproducibility": "descriptive",
        "reproducibility_note": "The model is hosted: no weight file exists to "
                                "hash, the API exposes no seed, and the operator "
                                "may change the weights behind the id "
                                "'gemini-3.1-flash-image' without notice. "
                                "Re-running this recipe would produce a "
                                "different image that follows the same "
                                "instructions.",
        "generated_at": GENERATED_AT,
        "pipeline": {"kind": "hosted-api"},
        "steps": [dict(common_step, prompt={
            "positive": {
                "file": "recipe/prompt-recorded.txt",
                "sha256": prompt_rec_f["sha256"],
                "provenance": "recorded",
                "encoding": "utf-8",
                "note": "Persisted by the producing pipeline at generation time "
                        "in its artifact database, in a row whose timestamp "
                        "matches the image file's to two milliseconds.",
            },
            "negative_absent_reason": "This model has no negative-prompt field. "
                                      "The exclusion list was folded into the "
                                      "positive text by the pipeline's "
                                      "per-model prompt router and appears in "
                                      "it after 'Do NOT include:'.",
        })],
        "postprocess": postprocess,
        "unrecorded": unrecorded_common + [
            "the exact string transmitted to the model: the pipeline persists "
            "the assembled prompt but not the trailing style-reference sentence "
            "its client appends afterwards, so the text above is what was "
            "recorded and not necessarily what was sent",
        ],
        "note": "Recipe as first written, from the pipeline's own recorded "
                "fields alone. Superseded by v2, which is kept separate rather "
                "than merged because the difference between what a pipeline "
                "records and what it sends is exactly the kind of fact this "
                "format exists to make visible.",
    }

    recipe_v2 = {
        "recipe_version": 1,
        "target": recipe_v1["target"],
        "reproducibility": "descriptive",
        "reproducibility_note": recipe_v1["reproducibility_note"],
        "generated_at": GENERATED_AT,
        "pipeline": {"kind": "hosted-api"},
        "steps": [dict(common_step, prompt={
            "positive": {
                "file": "recipe/prompt-transmitted.txt",
                "sha256": prompt_tx_f["sha256"],
                "provenance": "reconstructed",
                "encoding": "utf-8",
                "reconstruction": {
                    "method": "The pipeline persisted the assembled prompt but "
                              "not the string it transmitted. The transmitted "
                              "string is the persisted text (kept in this "
                              "package as recipe/prompt-recorded.txt, byte for "
                              "byte) followed by the sentence the client "
                              "appends when it attaches style references and no "
                              "identity references: ' The attached 1 image(s) "
                              "are STYLE references - match their painterly "
                              "rendering, palette and mood.' - with an em dash "
                              "where this sentence shows a hyphen, and with the "
                              "count 1 because exactly one style plate was "
                              "attached. The branch taken is the else-branch of "
                              "the client's style-reference block, which is "
                              "reached when the identity-reference list is "
                              "empty. Both source blocks are in "
                              "recipe/evidence/pipeline-source.txt with the "
                              "sha256 of the files they came from.",
                    "evidence": [
                        {"path": "recipe/evidence/pipeline-source.txt",
                         "sha256": evidence_f["sha256"],
                         "note": "Verbatim extracts of the five functions that "
                                 "assemble and send the prompt, each with the "
                                 "sha256 of the source file it came from."},
                        {"path": "recipe/prompt-recorded.txt",
                         "sha256": prompt_rec_f["sha256"],
                         "note": "The persisted text this reconstruction "
                                 "extends. It is the first N bytes of the "
                                 "transmitted string, exactly."},
                    ],
                },
                "note": "RECONSTRUCTED, not recorded. It is very probably what "
                        "was sent and it is not evidence that it was.",
            },
            "negative_absent_reason": recipe_v1["steps"][0]["prompt"][
                "negative_absent_reason"],
            "note": "recipe/prompt-recorded.txt is still in this node's files "
                    "and is still the pipeline's own record. This version does "
                    "not replace it; it says what it is missing.",
        })],
        "postprocess": postprocess,
        "unrecorded": unrecorded_common + [
            "which of the client's up-to-four attempts produced the saved "
            "pixels, and therefore whether the transmitted string was byte-"
            "identical to the reconstruction on the attempt that succeeded",
        ],
        "note": "Recipe after auditing the producing pipeline's source. The "
                "only change is the prompt: v1's positive text is what the "
                "pipeline persisted, v2's is the reconstructed string it "
                "actually transmitted, one sentence longer.",
    }

    recipe_v1_f = put("recipe/recipe@1.json", jbytes(recipe_v1),
                      "application/json", "record")
    recipe_v2_f = put("recipe/recipe.json", jbytes(recipe_v2),
                      "application/json", "record")

    # -- the descriptor ---------------------------------------------------
    vec, palette, diag = labhog.descriptor(src_img)
    lin = labhog.srgb_to_linear(labhog.box_resample(
        __import__("numpy").asarray(src_img.convert("RGB"))))
    avg_lum = float((lin[..., 0] * 0.2126729 + lin[..., 1] * 0.7151522
                     + lin[..., 2] * 0.0721750).mean())
    wkem = build_wkem(vec, palette, {
        "model": labhog.MODEL_ID,
        "dim": labhog.DIM,
        "normalized": True,
        "metric": "cosine",
        "swatch_count": int(palette.shape[0]),
        "colour_space": "linear-srgb",
        "source_path": "image/source.png",
        "tolerance": labhog.TOLERANCE,
        "epistemic": "measured",
        "input_hash": input_hash(["image/source.png"], files),
        "producer": {"tool": "fixtures/labhog.py", "version": "1"},
        "note": "64 CIELAB histogram bins then 8 gradient-orientation bins, "
                "L2-normalised. Defined completely in "
                "spec/layouts/embedding.layout.txt section 4, so it can be "
                "recomputed from image/source.png and checked.",
    })
    wkem_f = put("semantics/style-embedding.wkem", wkem,
                 "application/octet-stream")
    stats["descriptor"] = diag

    # -- semantics --------------------------------------------------------
    swatches = [
        {"hex_srgb": linear_to_hex(palette[i, 0:3]),
         "linear_rgb": [float(palette[i, 0]), float(palette[i, 1]),
                        float(palette[i, 2])],
         "weight": float(palette[i, 3])}
        for i in range(palette.shape[0]) if palette[i, 3] > 0.0
    ]
    weight_sum = sum(s["weight"] for s in swatches)
    semantics = {
        "schema_version": 1,
        "facets_version": 1,
        "facets": {
            "style": ["hand-painted", "retro-futurist", "x.character-design"],
            "function": ["x.portrait", "x.reference-plate"],
            "era": ["far-future"],
            "mood": ["austere", "solemn"],
            "condition": ["worn"],
        },
        "tag_stamps": {
            "style/hand-painted": {"epistemic": "authored"},
            "style/retro-futurist": {"epistemic": "authored"},
            "mood/austere": {"epistemic": "authored", "confidence": 0.8},
            "mood/solemn": {"epistemic": "authored", "confidence": 0.7},
            "condition/worn": {"epistemic": "authored", "confidence": 0.6},
        },
        "palette": {
            "method": "werk.descriptor.labhog/1 top-8 CIELAB histogram bins, "
                      "mean linear sRGB per bin",
            "colors": swatches,
            "dominant_index": 0,
            "average_luminance": avg_lum,
        },
        "description": "Character design plate: a young outer-worlds scholar in "
                       "austere layered administrator robes, painted in the "
                       "house oil-painting register of the 5D6 Space setting.",
        "keywords": ["character", "portrait", "scholar", "design-plate",
                     "oil-painting", "far-future"],
        "note": "NO `embedding` block here on purpose: the vector lives in the "
                "core.embedding node (semantics/style-embedding.wkem) and "
                "duplicating 72 floats as JSON would create two authorities for "
                "one fact. The palette IS duplicated, deliberately and exactly, "
                "because law 9 says a payload serves two masters and a listing "
                "wants eight hex strings without parsing an envelope; both "
                "spellings come from the same pass over the same pixels. "
                "MEASURED AND WORTH KNOWING: these eight swatches are the eight "
                "largest of ten non-empty histogram bins, so their weights sum "
                "to %.4f rather than 1.0. core.semantics.schema.json describes "
                "palette weights as summing to 1.0 within 1e-3, which assumes a "
                "palette that covers everything; a top-N palette does not. "
                "Filed as spec finding S-24." % weight_sum,
    }
    sem_f = put("semantics/semantics.json", jbytes(semantics), "application/json")
    stats["weight_sum"] = weight_sum

    # -- disclosure -------------------------------------------------------
    disclosure = {
        "disclosure_version": 1,
        "ai_generated": True,
        "ai_modified": False,
        "generation_scope": "whole-work",
        "declared_by": {
            "name": "werk fixture builder (fixtures/build_image_fixture.py)",
            "kind": "service",
            "uri": "urn:werk:dev-key:build-image-fixture",
        },
        "declared_at": CREATED,
        "recipe_node": "recipe",
        "models": [{
            "id": "gemini-3.1-flash-image",
            "role": "generate",
            "operator": "Google",
            "hosted": True,
            "version_note": "A hosted model id is not a version. The weights "
                            "behind this id may have changed since the image "
                            "was made, and nothing in this package can detect "
                            "that.",
        }],
        "human_authorship": {
            "claimed": True,
            "description": "A human wrote the character's subject description, "
                           "chose the style register, and authored the "
                           "exclusion list that the prompt was assembled from. "
                           "A human did not draw the pixels and no human "
                           "retouched them.",
            "contributors": [{
                "name": "Gregor Hubert Max Koch",
                "contribution": "subject description, style register, exclusion "
                                "list, and the decision to publish this image as "
                                "a conformance fixture",
            }],
        },
        "synthetic_markers": {
            "c2pa_manifest_present": False,
            "embedded_metadata_stripped": True,
        },
        "training_data_statement": {
            "status": "not-disclosed-by-operator",
            "text": "No training-data statement for this model was obtained by "
                    "the declarer. This field records that absence rather than "
                    "implying anything from it.",
            "source": "none retrieved",
        },
        "subject": {
            "depicts_real_person": False,
            "depicts_real_event": False,
            "fictional_universe": "5D6 Space",
            "note": "Ista Varun is a fictional character. No living or "
                    "historical person was used as a reference, and the only "
                    "image attached to the generation was a house style plate.",
        },
        "statements": [
            {"id": "watermark-unverified",
             "text": "No detector has been run over these bytes, so this "
                     "package makes no claim either way about an invisible "
                     "watermark. synthetic_markers deliberately carries no "
                     "declared_watermarks array: an empty array would read as "
                     "'checked and found none', which nobody did.",
             "epistemic": "authored"},
            {"id": "png-metadata-measured",
             "text": "The source PNG carries no tEXt, iTXt, zTXt or eXIf "
                     "chunk. This was measured by walking the chunk list at "
                     "build time, not assumed; it is why "
                     "embedded_metadata_stripped is true.",
             "epistemic": "measured", "confidence": 1.0,
             "basis": "PNG chunk walk over image/source.png during the build"},
            {"id": "copyright-unsettled",
             "text": "Whether copyright subsists in a wholly AI-generated "
                     "image, and in whom, is unsettled in several "
                     "jurisdictions. The embedded LICENSE grants what the "
                     "licensor has to grant and says so rather than "
                     "overclaiming.",
             "epistemic": "authored"},
            {"id": "no-enforcement",
             "text": "Nothing in this node obliges any viewer to do anything. "
                     "The format ships facts; the viewer applies "
                     "jurisdiction; see spec/SPEC.md section 3.12. A viewer "
                     "that ignores every field here is conformant.",
             "epistemic": "authored"},
        ],
        "jurisdiction_note": "Written with transparency-of-synthetic-content "
                             "regimes in mind. This is NOT a compliance claim, "
                             "it binds no viewer, and no tool may report this "
                             "package as compliant with anything on the "
                             "strength of it.",
    }
    disc_f = put("disclosure/disclosure.json", jbytes(disclosure),
                 "application/json")

    # -- the c2pa export stub ---------------------------------------------
    c2pa = {
        "export_version": 1,
        "status": "intent",
        "target_spec": {
            "name": "C2PA content credentials",
            "version": "2.x (as understood by the author, unverified)",
            "consulted_at": CREATED,
            "note": "The C2PA specification text was NOT consulted while this "
                    "mapping was written. Treat every row as a hypothesis. "
                    "spec/X-C2PA-EXPORT.md leads with a table saying exactly "
                    "how much has been done, which is: a table has been "
                    "written and nothing else.",
        },
        "mapping": [
            {"werk": "core.disclosure /ai_generated",
             "c2pa": "an action whose digitalSourceType is the IPTC "
                     "trainedAlgorithmicMedia term",
             "fidelity": "approximate",
             "note": "C2PA describes an asset's source TYPE; werk describes "
                     "whether a model produced the content. They coincide for a "
                     "whole-work generation and diverge for partial scope."},
            {"werk": "core.recipe /steps/0/model/id",
             "c2pa": "c2pa.actions -> the acting software agent",
             "fidelity": "lossy",
             "note": "A chain of steps flattens into a list of actions."},
            {"werk": "core.recipe /steps/0/inputs",
             "c2pa": "c2pa.ingredient assertions",
             "fidelity": "lossy",
             "note": "werk CARRIES the input bytes; an ingredient references "
                     "them. Exporting keeps the hash and drops the guarantee."},
            {"werk": "core.recipe /reproducibility",
             "c2pa": "(nothing)",
             "fidelity": "lossy",
             "note": "No counterpart exists. Listed here rather than silently "
                     "dropped."},
            {"werk": "SIGNATURE.json chain",
             "c2pa": "claim signature",
             "fidelity": "approximate",
             "note": "NOT EQUIVALENT. werk's chain has no trust list and no "
                     "certificate authority; it proves that named keys signed "
                     "named manifest states and explicitly refuses to say "
                     "whether a key belongs to anyone you trust."},
        ],
        "gaps": [
            {"direction": "werk-has-no-c2pa-counterpart",
             "subject": "core.recipe reproducibility grade and unrecorded[]",
             "detail": "The grade and the explicit list of facts that were "
                       "never captured are the two most useful fields in a "
                       "recipe and there is nowhere to put either."},
            {"direction": "werk-has-no-c2pa-counterpart",
             "subject": "the self-description layer",
             "detail": "Embedded schemas, layout grammars and bootstrap "
                       "readers have no analogue, because C2PA is making a "
                       "claim checkable today rather than making a file "
                       "readable in fifty years."},
            {"direction": "c2pa-requires-what-werk-lacks",
             "subject": "certificate chain and trust list",
             "detail": "A C2PA validator reports a validation status derived "
                       "from a trust anchor. werk has no external root of "
                       "trust and says so in spec/SPEC.md section 6."},
            {"direction": "c2pa-requires-what-werk-lacks",
             "subject": "hard binding inside the asset",
             "detail": "A C2PA manifest is normally embedded in the asset "
                       "itself. A werk package is a container of many files, "
                       "and a package is not an asset."},
        ],
        "note": "This node is x.* on purpose. A reader that does not know it "
                "skips it and reports the skip, and nothing in core depends on "
                "it - which is the whole argument for keeping another "
                "consortium's schema out of a constitution.",
    }
    c2pa_f = put("x/c2pa/export.json", jbytes(c2pa), "application/json")

    # -- provenance --------------------------------------------------------
    provenance = {
        "schema_version": 1,
        "runs": [
            {"run_id": "design-nb2",
             "started": GENERATED_AT,
             "finished": GENERATED_AT,
             "tool": {"name": "visual_bible_engine design_book",
                      "version": "not-recorded",
                      "commit": "not-recorded"},
             "models": [{"id": "gemini-3.1-flash-image", "role": "generate"}],
             "consumed": [
                 {"path": "recipe/inputs/imperial-painterly.png",
                  "sha256": plate_f["sha256"]},
             ],
             "produced": [{"node_id": "image-source", "v": 1}]},
            {"run_id": "package-build",
             "started": CREATED,
             "finished": CREATED,
             "tool": {"name": "fixtures/build_image_fixture.py", "version": "1"},
             "consumed": [{"path": "image/source.png", "sha256": src_f["sha256"]}],
             "produced": [{"node_id": "image-preview", "v": 1},
                          {"node_id": "image-thumb", "v": 1},
                          {"node_id": "style-embedding", "v": 1},
                          {"node_id": "semantics", "v": 1}]},
        ],
    }
    # core.provenance.schema.json is additionalProperties:false at the root and
    # has no `note` key. A first draft of this payload carried one and werk-core
    # reported `payload-schema-invalid` and marked the node dead — which is the
    # schema doing its job, so the sentence moved to the node's version note
    # where the format actually provides for it (law 6). Recorded because a
    # later reader will otherwise wonder where the commentary went.
    prov_f = put("provenance/provenance.json", jbytes(provenance),
                 "application/json")

    # -- nodes -------------------------------------------------------------
    node("spec", "core.spec", [version(
        1, spec_files,
        "The specification this package conforms to, travelling inside it so "
        "the file explains itself (law 2). Profile image/1 is "
        "spec/PROFILE-IMAGE.md; the base families it uses are SPEC.md 3.11-3.13.",
        "fixtures/build_image_fixture.py", "1", "authored")])

    node("license", "core.license", [version(
        1, [lic_f], "Full licence text embedded, never a link (law 7), "
        "including what is and is not being claimed for an AI-generated image.",
        "fixtures/build_image_fixture.py", "1", "authored")])

    node("readme", "core.readme", [version(
        1, [readme_f], "One page for a human who opened the archive by hand, "
        "pointing at the three things that are unusual about this package.",
        "fixtures/build_image_fixture.py", "1", "authored")])

    for node_id, rel, lang, toolchain, build_command, media in loader_meta:
        with open(os.path.join(ROOT, rel.replace("/", os.sep)), "rb") as fh:
            data = fh.read()
        f = put(rel, data, media)
        meta = {"language": lang, "form": "source", "entrypoint": rel,
                "toolchain": toolchain, "dependencies": [],
                "capabilities": loader_capabilities(data)}
        if build_command:
            meta["build_command"] = build_command
        node(node_id, "core.loader", [version(
            1, [f],
            "Single-file zero-dependency bootstrap reader. Profile-agnostic: it "
            "walks the manifest, verifies hashes and parses envelopes, none of "
            "which needs to know what the payloads mean.",
            "fixtures/build_image_fixture.py", "1", "authored")], meta=meta)

    node("image-source", "core.image.source", [version(
        1, [src_f],
        "The image as the model delivered it, re-encoded by Pillow and not "
        "otherwise touched: no crop, no resize. This is the archival anchor "
        "every derived node hashes against.",
        "visual_bible_engine design_book", "not-recorded", "inferred",
        created=GENERATED_AT, model="gemini-3.1-flash-image",
        inputs=["recipe/inputs/imperial-painterly.png"], confidence=None)],
        edges=[{"to": "recipe", "kind": "enhances", "role": "made-by"}],
        meta={"width": info["width"], "height": info["height"],
              "channels": info["channels"], "bit_depth": info["bit_depth"],
              "color_space": "srgb", "encoding": "png", "has_alpha": False,
              "aspect_note": "Requested 3:4 (0.7500); delivered %d x %d "
                             "(%.4f). Hosted image models rarely return exactly "
                             "the requested ratio, and this package records the "
                             "difference rather than cropping it away."
                             % (info["width"], info["height"],
                                info["width"] / float(info["height"]))})

    node("image-preview", "core.image.derived", [version(
        1, [prev_f],
        "Mid-size web render. Lanczos-3 from the source at build time, so it "
        "is reproducible from the source and its input_hash proves it.",
        "fixtures/build_image_fixture.py", "1", "measured",
        inputs=["image/source.png"])],
        edges=[{"to": "image-source", "kind": "requires", "role": "derived-from"}],
        meta={"width": PREVIEW_W, "height": prev_h, "channels": 3, "bit_depth": 8,
              "color_space": "srgb", "encoding": "png", "has_alpha": False,
              "derived_role": "preview", "resample": "lanczos3"})

    node("image-thumb", "core.image.derived", [version(
        1, [thumb_f],
        "Listing tier. It sits inside container.preview_prefix_bytes on "
        "purpose, so a browser showing a thousand of these pays a ranged read "
        "and not a download (law 9).",
        "fixtures/build_image_fixture.py", "1", "measured",
        inputs=["image/source.png"])],
        edges=[{"to": "image-source", "kind": "requires", "role": "derived-from"}],
        meta={"width": THUMB_W, "height": thumb_h, "channels": 3, "bit_depth": 8,
              "color_space": "srgb", "encoding": "png", "has_alpha": False,
              "derived_role": "thumbnail", "resample": "lanczos3"})

    # The two-version node. v2 RELISTS recipe/prompt-recorded.txt and
    # recipe/inputs/imperial-painterly.png unchanged — the S-18 case, and the
    # honest shape of an audit: the prompt record and the input medium did not
    # move, only what we know about them did.
    node("recipe", "core.recipe", [
        version(1, [recipe_v1_f, prompt_rec_f, plate_f],
                "The recipe as first written, from the fields the producing "
                "pipeline actually persisted.",
                "fixtures/build_image_fixture.py", "1", "authored",
                inputs=["image/source.png"]),
        version(2, [recipe_v2_f, ref("recipe/prompt-recorded.txt", "text/plain",
                                     "prompt-recorded"),
                    prompt_tx_f, evidence_f,
                    ref("recipe/inputs/imperial-painterly.png", "image/png",
                        "input-media")],
                "Auditing the pipeline's source showed the persisted prompt is "
                "one sentence shorter than the string transmitted; v2 records "
                "the reconstructed transmitted prompt and the code excerpt it "
                "was rebuilt from. v1 stays, because law 6 does not rewrite "
                "history and because the difference is the interesting part.",
                "fixtures/build_image_fixture.py", "1", "authored",
                inputs=["image/source.png"], supersedes=1),
    ], edges=[{"to": "image-source", "kind": "requires", "role": "recipe-for"}])

    node("disclosure", "core.disclosure", [version(
        1, [disc_f],
        "Machine-readable facts about how this image came to exist. Facts "
        "only: the format contains no enforcement and this node obliges no "
        "viewer to do anything (SPEC.md 3.12).",
        "fixtures/build_image_fixture.py", "1", "authored")],
        edges=[{"to": "image-source", "kind": "requires", "role": "discloses"},
               {"to": "recipe", "kind": "enhances", "role": "backed-by"}])

    node("style-embedding", "core.embedding", [version(
        1, [wkem_f],
        "A 72-component style descriptor and an 8-swatch palette from one pass "
        "over the source, in a WKEM envelope. Measured, and recomputable from "
        "image/source.png by anyone with spec/layouts/embedding.layout.txt.",
        "fixtures/labhog.py", "1", "measured",
        inputs=["image/source.png"])],
        edges=[{"to": "image-source", "kind": "requires", "role": "derived-from"}])

    node("semantics", "core.semantics", [version(
        1, [sem_f],
        "Facet tags against spec/facets.json, plus the palette in both sRGB hex "
        "and linear float so a listing never has to parse an envelope.",
        "fixtures/build_image_fixture.py", "1", "authored",
        inputs=["semantics/style-embedding.wkem"])],
        edges=[{"to": "image-source", "kind": "enhances", "role": "describes"},
               {"to": "style-embedding", "kind": "enhances", "role": "embedding"}])

    node("provenance", "core.provenance", [version(
        1, [prov_f],
        "Two runs, months apart: the generation and the packaging. One is "
        "reproducible and one is not, and merging them would hide that.",
        "fixtures/build_image_fixture.py", "1", "authored")],
        edges=[{"to": "image-source", "kind": "enhances", "role": "records"}])

    node("c2pa-export", "x.c2pa.export", [version(
        1, [c2pa_f],
        "A declared, unimplemented mapping to C2PA. An x.* node on purpose: a "
        "reader that does not know this type skips it and reports the skip, "
        "and loses nothing (law 12).",
        "fixtures/build_image_fixture.py", "1", "authored")],
        edges=[{"to": "disclosure", "kind": "enhances", "role": "exports"}])

    return files, nodes, stats


def build_manifest(files, nodes, preview_prefix, extra_summary=""):
    total = sum(len(v) for v in files.values())
    return {
        "werk": {"major": 1, "minor": 0},
        "profile": "image/1",
        "manifest_schema": "spec/schemas/manifest.image.schema.json",
        "entity": {
            "uuid": ENTITY_UUID,
            "name": "Ista Varun — character design plate",
            "summary": (
                "werk conformance fixture #2, profile image/1: one genuinely "
                "AI-generated image with its genuinely recorded recipe. A "
                "character design plate for the 5D6 Space setting, produced by "
                "a hosted image model from a human-written subject description "
                "and one attached style plate, which is embedded here by hash. "
                "The recipe is graded DESCRIPTIVE and says why; its "
                "unrecorded[] array names six facts nobody captured. The "
                "recipe node carries two versions because the prompt the "
                "pipeline persisted turned out to be one sentence shorter than "
                "the one it sent. semantics/style-embedding.wkem is a custom "
                "binary and is the first thing in any handed-out werk fixture "
                "to exercise spec/layouts/ENVELOPE.layout.txt." + extra_summary),
            "created": CREATED,
        },
        "conventions": {
            "endianness": "le",
            "color_space_default": "srgb",
            "pixel_origin": "top-left",
            "alpha_mode": "straight",
            "alignment_bytes": 16,
            "text_encoding": "utf-8",
            "id_case": "kebab-case",
            "hash_algorithm": "sha256",
            "signature_algorithm": "ed25519",
        },
        "container": {
            "form": "zip",
            "zip_compression": "store",
            "entry_order": list(ENTRY_ORDER),
            "preview_tier": list(PREVIEW_SET),
            "total_size_bytes": total,
            "preview_prefix_bytes": preview_prefix,
        },
        "primary": {"image": "image-source", "thumbnail": "image-thumb"},
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
        "conventions_map": "spec/conventions-map.image.json",
        "schemas": {
            "core.recipe": "spec/schemas/core.recipe.schema.json",
            "core.disclosure": "spec/schemas/core.disclosure.schema.json",
            "core.semantics": "spec/schemas/core.semantics.schema.json",
            "core.provenance": "spec/schemas/core.provenance.schema.json",
            "x.c2pa.export": "spec/schemas/x.c2pa.export.schema.json",
        },
        "layouts": {"core.embedding": "spec/layouts/embedding.layout.txt"},
        "nodes": nodes,
        "signature_file": "SIGNATURE.json",
        "generator": {"tool": "fixtures/build_image_fixture.py", "version": "1"},
    }


def sign(manifest_bytes):
    return build_chain(sha256(manifest_bytes), [{
        "secret": DEV_SK,
        "name": "werk dev key (publicly derived, fixtures only)",
        "uri": "urn:werk:dev-key:build-image-fixture",
        "kind": "service",
        "role": "author",
        "signed_at": CREATED,
        "note": "Signed with a DEV key derived from a published sentence. It is "
                "not secret, it is not a trust anchor, and it proves only that "
                "the chain verifies.",
    }])


def assemble(files, nodes):
    # SPEC 2.1 (S-XV-4 / S-OW-2)
    annotate_payload_files(nodes)
    # SPEC 5: never write a `requires` edge to a node not in nodes[].
    refuse_dangling_edges(nodes)
    preview = 0
    for _round in range(8):
        manifest_bytes = jbytes(build_manifest(files, nodes, preview))
        sig_bytes = jbytes(sign(manifest_bytes))
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
        os.environ.get("WERK_LAB", "<WERK_LAB unset>"), "SFNovels"))
    ap.add_argument("--out", default=HERE)
    args = ap.parse_args(argv)

    files, nodes, stats = collect(args.src)
    manifest_bytes, sig_bytes, entries = assemble(files, nodes)
    blob = write_zip(entries)
    path = os.path.join(args.out, "ista-varun-v1.werk")
    with open(path, "wb") as fh:
        fh.write(blob)

    prefix = json.loads(manifest_bytes)["container"]["preview_prefix_bytes"]
    print("wrote %s" % path)
    print("  %d bytes, sha256 %s" % (len(blob), sha256(blob)))
    print("  %d entries, %d nodes, %d declared file references"
          % (len(entries), len(nodes),
             sum(len(v["files"]) for n in nodes for v in n["versions"])))
    print("  manifest %d bytes, sha256 %s"
          % (len(manifest_bytes), sha256(manifest_bytes)))
    print("  preview_prefix_bytes %d (%.2f%% of the archive)"
          % (prefix, 100.0 * prefix / len(blob)))
    print("  source image %dx%d, %d bytes; PNG text chunks: %s"
          % (stats["src"]["width"], stats["src"]["height"],
             len(files["image/source.png"]),
             stats["text_chunks"] or "none"))
    print("  WKEM %d bytes; descriptor %s" % (len(files["semantics/style-embedding.wkem"]),
                                              stats["descriptor"]))
    print("  palette weights sum to %.6f (S-24)" % stats["weight_sum"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
