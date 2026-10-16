#!/usr/bin/env python3
"""package_rebuild.py: rebuild a shipped fixture from the inputs it carries.

Law 1 says a werk answers every question it raises. A fixture whose builder
read its inputs from the author's own disk still carries those inputs (the
source binaries, and the records the JSON inputs became), so a gate can
rebuild it on any machine. This module holds the shared steps for the rebuild
clauses of Gate 9 (ista-varun-v1) and Gate A (crate-v1, crate-v1-damaged):

  1. read the shipped package and check every entry used as an input against
     the sha256 its manifest declares,
  2. lay out an overlay root in the gate's work dir: the repo's builder code
     (fixtures/*.py, tools/, store/) plus the package's OWN spec/ and loaders/
     (ruling R1: the shipped spec snapshot is CRLF, the checkout is LF),
  3. reconstruct the source tree the builder reads, from the package,
  4. run the builder into the work dir (never into fixtures/),
  5. compare the result at three levels, which the gates report separately:

     L1 archive reassembly       the whole .werk is byte-identical to the pin
     L2 computed payloads        every entry the builder COMPUTES (not copies)
                                 is identical to the shipped entry
     L3 original-input           the builder runs on the original upstream
        generation               inputs (the author's tree). Packaged inputs
                                 cannot stand in for this level.

Nothing here writes outside the directories the caller passes in.

Run as a script, it is the subprocess wrapper the Gate 9 clause uses:

    python tests/package_rebuild.py image OVERLAY_ROOT SRC OUT EVIDENCE [--restock]
"""

import hashlib
import io
import json
import os
import shutil
import sqlite3
import struct
import sys
import zipfile
import zlib


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def read_zip(path):
    """name -> bytes, plus the physical entry order."""
    with zipfile.ZipFile(path) as z:
        infos = sorted(z.infolist(), key=lambda i: i.header_offset)
        return {i.filename: z.read(i) for i in infos}, [i.filename for i in infos]


def declared_sha256(manifest):
    out = {}
    for n in manifest["nodes"]:
        for v in n["versions"]:
            for f in v["files"]:
                out[f["path"]] = f["sha256"]
    return out


def check_declared(entries, names):
    """The inputs a rebuild takes from the package must be the bytes the
    manifest declares. Returns a list of problems (empty when all match)."""
    decl = declared_sha256(json.loads(entries["MANIFEST.json"]))
    bad = []
    for nm in sorted(names):
        if nm not in entries:
            bad.append("%s: not in the package" % nm)
        elif nm not in decl:
            bad.append("%s: not declared in the manifest" % nm)
        elif decl[nm] != sha256_bytes(entries[nm]):
            bad.append("%s: sha256 %s, manifest declares %s"
                       % (nm, sha256_bytes(entries[nm])[:16], decl[nm][:16]))
    return bad


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)


def make_overlay(repo_root, entries, dest):
    """A scratch root for a builder: the repo's builder code, and the spec/
    and loaders/ trees the PACKAGE carries. Returns the list of package
    entries used (spec/** and loaders/**)."""
    if os.path.exists(dest):
        shutil.rmtree(dest)
    os.makedirs(os.path.join(dest, "fixtures"))
    fx = os.path.join(repo_root, "fixtures")
    for nm in os.listdir(fx):
        if nm.endswith(".py") and os.path.isfile(os.path.join(fx, nm)):
            shutil.copyfile(os.path.join(fx, nm),
                            os.path.join(dest, "fixtures", nm))
    for d in ("tools", "store"):
        shutil.copytree(os.path.join(repo_root, d), os.path.join(dest, d),
                        ignore=shutil.ignore_patterns("__pycache__", "*.werk",
                                                      "target", ".gate*"))
    used = sorted(nm for nm in entries
                  if nm.startswith("spec/") or nm.startswith("loaders/"))
    for nm in used:
        _write(os.path.join(dest, nm.replace("/", os.sep)), entries[nm])
    return used


# --- ista-varun-v1 (Gate 9) -------------------------------------------------

IMAGE_SRC_IMAGE = ("output/visual-bible/01-the-concordance-of-echoes/"
                   "characters/ista-varun.png")
IMAGE_SRC_PLATE = "platform5d6/data/style/plates/5d6/imperial-painterly.png"
IMAGE_SRC_DB = "platform5d6/data/artifacts.db"
IMAGE_DB_URN = "book/01-the-concordance-of-echoes/design/characters/ista-varun"
IMAGE_EVIDENCE = "recipe/evidence/pipeline-source.txt"
IMAGE_CLIENT = "visual_bible_engine/src/nanobanana_client.py"
# Entries the image builder takes as input. Everything else it computes.
IMAGE_INPUTS = ["image/source.png", "recipe/inputs/imperial-painterly.png",
                "recipe/prompt-recorded.txt", IMAGE_EVIDENCE]

# The limits of the ista-varun rebuild, named once and quoted by the gate.
IMAGE_SUBSTITUTIONS = [
    "artifacts.db row reconstructed from recipe/prompt-recorded.txt (the "
    "builder reads only the prompt from it, and asserts the output path)",
    "pipeline-source.txt copied from the package: the four producer source "
    "files (design_book.py, forge.py, nanobanana_client.py, style_bible.py) "
    "are carried only as excerpts plus whole-file sha256, so the evidence "
    "cannot be regenerated",
    "nanobanana_client.py stubbed from its evidence excerpts, to satisfy the "
    "builder's three content asserts",
    "preview PNGs re-deflated with the interpreter's stock zlib (level 6, "
    "memLevel 9, Z_FILTERED, 65536-byte IDAT chunks): the fixture was written "
    "by a stock-zlib Pillow, current Pillow wheels link zlib-ng",
]


def image_source_tree(entries, dest):
    """Reconstruct the <WERK_LAB>/SFNovels files build_image_fixture.py reads."""
    def P(rel):
        p = os.path.join(dest, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        return p
    if os.path.exists(dest):
        shutil.rmtree(dest)
    _write(P(IMAGE_SRC_IMAGE), entries["image/source.png"])
    _write(P(IMAGE_SRC_PLATE), entries["recipe/inputs/imperial-painterly.png"])
    prompt = entries["recipe/prompt-recorded.txt"].decode("utf-8")
    if not prompt.endswith("\n"):
        raise ValueError("recipe/prompt-recorded.txt has no final newline")
    con = sqlite3.connect(P(IMAGE_SRC_DB))
    try:
        con.execute("create table artifacts "
                    "(urn text, recipe text, outputs text, updated_at text)")
        con.execute("insert into artifacts values (?,?,?,?)",
                    (IMAGE_DB_URN, json.dumps({"prompt": prompt[:-1]}),
                     json.dumps([IMAGE_SRC_IMAGE]), "reconstructed"))
        con.commit()
    finally:
        con.close()
    # The client stub: every excerpt of nanobanana_client.py, at its
    # recorded first line. The builder asserts three strings in it.
    ev = entries[IMAGE_EVIDENCE].decode("utf-8").split("\n")
    blocks, i = [], 0
    while i < len(ev):
        if ev[i].startswith("file      : ") and \
                ev[i][12:].strip() == IMAGE_CLIENT:
            head = ev[i + 2]                    # "extracted : def X, lines A-B"
            a, b = head.rsplit("lines ", 1)[1].split("-")
            first, last = int(a), int(b)
            blocks.append((first, ev[i + 5:i + 5 + (last - first + 1)]))
            i += 5
        else:
            i += 1
    lines = []
    for first, body in sorted(blocks):
        while len(lines) < first - 1:
            lines.append("")
        lines += body
    text = "\n".join(lines) + "\n"
    if 'MODEL = "gemini-3.1-flash-image"' not in text:
        text += '\nMODEL = "gemini-3.1-flash-image"\n'
    _write(P(IMAGE_CLIENT), text.encode("utf-8"))


def zlib_is_stock():
    """(ok, description). Python's own zlib module is the stock zlib on
    CPython up to 3.13; the 3.14 Windows build links zlib-ng."""
    ver = zlib.ZLIB_RUNTIME_VERSION
    ng = getattr(zlib, "ZLIBNG_VERSION", None)
    if ng or "ng" in ver.lower():
        return False, "this interpreter's zlib is zlib-ng (%s)" % ver
    return True, "stock zlib %s" % ver


def _png_chunks(png):
    i, out = 8, []
    while i < len(png):
        n, = struct.unpack(">I", png[i:i + 4])
        out.append((png[i + 4:i + 8], png[i + 8:i + 8 + n]))
        i += 12 + n
    return out


def png_scanlines(png):
    """(non-IDAT chunks, decompressed IDAT): equal for two PNGs whose only
    difference is the deflate stream."""
    ch = _png_chunks(png)
    return ([c for c in ch if c[0] != b"IDAT"],
            zlib.decompress(b"".join(d for t, d in ch if t == b"IDAT")))


def restock_png(png):
    """Re-deflate a PNG's IDAT with the stock zlib parameters that reproduce
    the shipped fixture, in 65536-byte IDAT chunks as Pillow writes them."""
    chunks = _png_chunks(png)
    c = zlib.compressobj(6, zlib.DEFLATED, 15, 9, zlib.Z_FILTERED)
    z = c.compress(zlib.decompress(b"".join(d for t, d in chunks
                                             if t == b"IDAT"))) + c.flush()

    def ch(t, d):
        return (struct.pack(">I", len(d)) + t + d
                + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff))
    out, done = png[:8], False
    for t, d in chunks:
        if t != b"IDAT":
            out += ch(t, d)
        elif not done:
            for k in range(0, len(z), 65536):
                out += ch(b"IDAT", z[k:k + 65536])
            done = True
    return out


def _run_image(argv):
    """Subprocess wrapper: run build_image_fixture.main from the overlay root
    with the evidence substitution, and optionally the stock-zlib one."""
    import importlib.util
    root, src, out, evidence = argv[:4]
    restock = "--restock" in argv[4:]
    if restock:
        from PIL import Image
        orig = Image.Image.save

        def save(self, fp, format=None, **kw):
            if (format or "").upper() == "PNG" and isinstance(fp, io.BytesIO):
                tmp = io.BytesIO()
                orig(self, tmp, format=format, **kw)
                fp.write(restock_png(tmp.getvalue()))
                return None
            return orig(self, fp, format=format, **kw)
        Image.Image.save = save
    spec = importlib.util.spec_from_file_location(
        "build_image_fixture",
        os.path.join(root, "fixtures", "build_image_fixture.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    with open(evidence, "rb") as fh:
        ev = fh.read()
    m.build_evidence = lambda src_root: ev
    os.makedirs(out, exist_ok=True)
    return m.main(["--src", src, "--out", out])


# --- crate-v1 (Gate A) --------------------------------------------------------

GOLDEN_SUBSTITUTIONS = [
    "asset.json, description.json, segments.json, sfx_plan.json and "
    "sfx/<slug>.json reconstructed from audio/package.json and the "
    "audio/sfx/*.json records, with only the fields build_golden.py reads",
]


def golden_source_tree(entries, dest):
    """Reconstruct the <WERK_LAB>/splat-foley/outputs/example files build_golden.py
    reads. Binaries are copied verbatim. Returns (copied, records): the
    package entries copied in as binary inputs, and the JSON records the
    JSON inputs were reconstructed from. A rebuild that reproduces a record
    is circular evidence for it, so a gate reports records apart from the
    computed payloads."""
    if os.path.exists(dest):
        shutil.rmtree(dest)
    for sub in ("views", "segments", "sfx"):
        os.makedirs(os.path.join(dest, sub))
    copied, records = [], []

    def J(nm):
        records.append(nm)
        return json.loads(entries[nm].decode("utf-8"))

    def W(rel, obj):
        with open(os.path.join(dest, rel), "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=1)

    def copy(nm, rel):
        copied.append(nm)
        _write(os.path.join(dest, rel), entries[nm])

    copy("geometry/source.glb", "model.glb")
    for sub in ("views", "segments"):
        pre = "x/splat-foley/%s/" % sub
        for nm in sorted(e for e in entries if e.startswith(pre)):
            copy(nm, os.path.join(sub, nm[len(pre):]))
    ap = J("audio/package.json")
    W("asset.json", {"asset": ap["asset"], "source": ap["source"],
                     "kind": ap["geometry"]["kind"],
                     "n_vertices": ap["geometry"]["n_vertices"],
                     "n_faces": ap["geometry"]["n_faces"]})
    objs, segs = [], []
    for o in ap["objects"]:
        d = {k: v for k, v in o.items() if k != "part_id"}
        if "segment" in d:
            s = dict(d["segment"])
            s["view"] = s["view"].split("/")[-1]
            s["crop"] = s["crop"].split("/")[-1]
            d["segment"] = s
            segs.append({k: s[k] for k in ("crop", "area_frac", "stability")
                         if k in s})
        objs.append(d)
    W("description.json", {"objects": objs})
    W("segments.json", {"segments": segs})
    effs = []
    for e in ap["effects"]:
        effs.append({k: e[k] for k in ("slug", "object", "material", "category",
                                       "interaction", "prompt", "seconds",
                                       "loopable") if k in e})
        m = J(e["meta"])
        side = {k: m[k] for k in ("prompt_used", "seconds", "loopable",
                                  "clap_score", "accepted")}
        if "attempts" in m:
            side["attempts"] = m["attempts"]
        if "variations" in m:
            side["variations"] = [{"file": v["file"].split("/")[-1],
                                   "clap_score": v["clap_score"]}
                                  for v in m["variations"]]
        if m.get("refined"):
            side["refined"] = m["refined"]
        W(os.path.join("sfx", e["slug"] + ".json"), side)
        for t in e["takes"]:
            copy(t["file"], os.path.join("sfx", t["file"].split("/")[-1]))
    W("sfx_plan.json", {"effects": effs})
    return sorted(set(copied)), sorted(set(records))


# --- comparison ---------------------------------------------------------------

JSON_REL_TOL = 1e-12


def json_float_diff(a, b):
    """Largest relative difference between two JSON documents that have the
    same structure and differ only in floating-point values, or None. Floats
    computed through pow/exp can differ in the last digit between C maths
    libraries (glibc vs MSVC), so such entries reproduce the computation but
    not the bytes."""
    try:
        x, y = json.loads(a), json.loads(b)
    except (ValueError, UnicodeDecodeError):
        return None
    worst = [0.0]

    def walk(u, v):
        if isinstance(u, dict) and isinstance(v, dict):
            return u.keys() == v.keys() and all(walk(u[k], v[k]) for k in u)
        if isinstance(u, list) and isinstance(v, list):
            return len(u) == len(v) and all(walk(i, j) for i, j in zip(u, v))
        if isinstance(u, float) and isinstance(v, float):
            d = abs(u - v) / max(abs(u), abs(v), 1e-300)
            worst[0] = max(worst[0], d)
            return d <= JSON_REL_TOL
        return type(u) is type(v) and u == v
    return worst[0] if walk(x, y) else None


def compare(shipped, rebuilt, inputs, png_by_pixels=()):
    """Entry-by-entry comparison. `inputs` are entries copied into the build
    (they are not evidence of computation). MANIFEST.json and SIGNATURE.json
    are container entries (level 1). Every other entry is a computed payload
    (level 2). PNG entries named in `png_by_pixels` count as reproduced at
    level 2 when their chunks and decompressed scanlines are identical, even
    if the deflate stream differs."""
    names = sorted(set(shipped) | set(rebuilt))
    container = {"MANIFEST.json", "SIGNATURE.json"}
    r = {"total": len(names), "identical": 0, "differ": [],
         "computed": [], "computed_bad": [], "png_scanline_only": [],
         "json_float_only": [], "json_max_rel_diff": 0.0, "inputs_bad": []}
    for nm in names:
        a, b = shipped.get(nm), rebuilt.get(nm)
        same = a == b
        if same:
            r["identical"] += 1
        else:
            r["differ"].append(nm)
        if nm in container:
            continue
        if nm in inputs:
            if not same:
                r["inputs_bad"].append(nm)
            continue
        r["computed"].append(nm)
        if same:
            continue
        if nm in png_by_pixels and a is not None and b is not None \
                and png_scanlines(a) == png_scanlines(b):
            r["png_scanline_only"].append(nm)
        elif nm.endswith(".json") and a is not None and b is not None                 and json_float_diff(a, b) is not None:
            r["json_float_only"].append(nm)
            r["json_max_rel_diff"] = max(r["json_max_rel_diff"],
                                         json_float_diff(a, b))
        else:
            r["computed_bad"].append(nm)
    return r


if __name__ == "__main__":
    if len(sys.argv) >= 6 and sys.argv[1] == "image":
        sys.exit(_run_image(sys.argv[2:]))
    sys.stderr.write(__doc__)
    sys.exit(2)
