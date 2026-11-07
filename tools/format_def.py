#!/usr/bin/env python3
"""format_def.py -- check (and, for the definitions this repository owns,
regenerate the vectors of) werk FORMAT DEFINITION documents.

    python tools/format_def.py --check spec/formats/splat-32.md [more.md ...]
    python tools/format_def.py --check-package some.werk        # every definition a package carries
    python tools/format_def.py --vectors splat-32               # print the vector block to paste

SPEC.md section 3.18: a foreign-encoded payload is a legitimate core payload
when the package carries a DEFINITION of its encoding from which a codec can be
built. A definition is a markdown document with a machine header (a fenced
block whose info string is `werk-format`) and hash-checkable test vectors.

`--check` does what any reader can do without a codec, and is the same list the
reference core applies (core/src/formats.rs) -- written a second time here, in
another language, on purpose: two implementations of the header rules that
share no code is how a rule in prose gets found out.

  1  the document is UTF-8 and has exactly one `werk-format` header
  2  the header is one JSON object with the mandatory keys
  3  `coverage` is complete|partial, and partial carries a coverage_note
  4  `sniff` is a NON-EMPTY list of known alternatives
  5  there is at least one test vector, and every vector's input is either a
     printed `hex <id>` block hashing to input_sha256 and of input_bytes
     length, or names an input_file the header's vector_files declares
  6  for a definition this script has a DECODER for (below): decoding each
     vector input reproduces output_sha256 and output_bytes -- the check that
     the document's hashes are the hashes of what the document describes

Stdlib only. Exit 0 only when every document passes every check.
"""

import hashlib
import json
import struct
import sys
import zipfile

MANDATORY = ["format_id", "format_version", "title", "media_type", "sniff",
             "defines", "coverage", "test_vectors"]
SNIFF_RULES = ("zlib-header", "none")


def fenced_blocks(text):
    """[(info string, body)] for every ``` fenced block."""
    out, cur = [], None
    for line in text.splitlines():
        if line.startswith("```"):
            if cur is None:
                cur = [line[3:].strip(), []]
            else:
                out.append((cur[0], "\n".join(cur[1])))
                cur = None
        elif cur is not None:
            cur[1].append(line)
    return out


def parse(doc_bytes):
    text = doc_bytes.decode("utf-8")          # check 1 (raises on bad UTF-8)
    blocks = fenced_blocks(text)
    headers = [b for info, b in blocks if info == "werk-format"]
    if len(headers) != 1:
        raise ValueError("%d `werk-format` header blocks; exactly one is required"
                         % len(headers))
    header = json.loads(headers[0])
    if not isinstance(header, dict):
        raise ValueError("the header is not a JSON object")
    hexes = {}
    for info, body in blocks:
        if info.startswith("hex "):
            hexes[info[4:].strip()] = bytes.fromhex("".join(body.split()))
    return header, hexes


def check_header(header, hexes, declared_files=None):
    """Checks 2-5. Returns a list of problems (empty = fine)."""
    bad = []
    for k in MANDATORY:
        if k not in header:
            bad.append("mandatory key `%s` is absent" % k)
    if bad:
        return bad
    if header["coverage"] not in ("complete", "partial"):
        bad.append("`coverage` is %r; it is `complete` or `partial`" % header["coverage"])
    if header["coverage"] == "partial" and not str(header.get("coverage_note", "")).strip():
        bad.append("`coverage` is partial and there is no `coverage_note`")
    sniff = header["sniff"]
    if not isinstance(sniff, list) or not sniff:
        bad.append("`sniff` is absent or empty: an empty list is an omission, not a "
                   "declaration")
    else:
        for alt in sniff:
            if "magic" in alt:
                if not alt["magic"] or any("hex" not in m for m in alt["magic"]):
                    bad.append("a `magic` alternative with no usable byte strings")
            elif alt.get("rule") not in SNIFF_RULES:
                bad.append("sniff alternative %r is neither `magic` nor a known rule"
                           % (alt,))
            elif alt.get("rule") == "none" and len(str(alt.get("note", ""))) < 20:
                bad.append("a `none` sniff rule says WHY in a note of at least 20 "
                           "characters")
    vectors = header["test_vectors"]
    if not isinstance(vectors, list) or not vectors:
        bad.append("no test vectors: a definition nobody can check an implementation "
                   "against is a description")
        return bad
    vfiles = {v["path"]: v for v in header.get("vector_files", [])}
    for v in vectors:
        vid = v.get("id", "?")
        if v.get("input_file"):
            if v["input_file"] not in vfiles:
                bad.append("vector `%s`: input_file %s is not declared in vector_files"
                           % (vid, v["input_file"]))
            elif vfiles[v["input_file"]].get("sha256") != v.get("input_sha256"):
                bad.append("vector `%s`: input_file's declared sha256 is not the "
                           "vector's input_sha256" % vid)
            elif declared_files is not None and \
                    declared_files.get(v["input_file"]) != v.get("input_sha256"):
                bad.append("vector `%s`: the package does not declare %s with that "
                           "sha256" % (vid, v["input_file"]))
            continue
        if vid not in hexes:
            bad.append("vector `%s`: neither a `hex %s` block nor an input_file"
                       % (vid, vid))
            continue
        data = hexes[vid]
        if hashlib.sha256(data).hexdigest() != v.get("input_sha256"):
            bad.append("vector `%s`: the printed input hashes to %s, the header says %s"
                       % (vid, hashlib.sha256(data).hexdigest(), v.get("input_sha256")))
        if "input_bytes" in v and len(data) != v["input_bytes"]:
            bad.append("vector `%s`: the printed input is %d bytes, the header says %d"
                       % (vid, len(data), v["input_bytes"]))
    return bad


# ---------------------------------------------------------------------------
# Decoders for the definitions THIS repository owns. Each is written from the
# document's own decoding procedure and from nothing else, and exists so that
# check 6 is a measurement: the hashes in the document are the hashes of what
# the document describes.
# ---------------------------------------------------------------------------

def decode_splat_32(data):
    """spec/formats/splat-32.md section 5 and section 6, transcribed."""
    if len(data) % 32 != 0:
        raise ValueError("%d bytes is not a whole number of 32-byte records" % len(data))
    out = bytearray()
    for i in range(0, len(data), 32):
        x, y, z, sx, sy, sz = struct.unpack_from("<6f", data, i)
        r, g, b, a, qw, qx, qy, qz = struct.unpack_from("<8B", data, i + 24)
        vals = [x, y, z, sx, sy, sz,
                r / 255.0, g / 255.0, b / 255.0, a / 255.0,
                (qw - 128) / 128.0, (qx - 128) / 128.0,
                (qy - 128) / 128.0, (qz - 128) / 128.0]
        out += struct.pack("<14f", *vals)
    return bytes(out)


DECODERS = {"splat-32": decode_splat_32}


def check_decode(header, hexes):
    """Check 6, for the ids this script can decode."""
    fn = DECODERS.get(header.get("format_id"))
    if fn is None:
        return None
    bad = []
    for v in header["test_vectors"]:
        if v["id"] not in hexes:
            continue
        out = fn(hexes[v["id"]])
        if len(out) != v.get("output_bytes"):
            bad.append("vector `%s`: decodes to %d bytes, the header says %s"
                       % (v["id"], len(out), v.get("output_bytes")))
        if hashlib.sha256(out).hexdigest() != v.get("output_sha256"):
            bad.append("vector `%s`: decodes to sha256 %s, the header says %s"
                       % (v["id"], hashlib.sha256(out).hexdigest(), v.get("output_sha256")))
    return bad


# ---------------------------------------------------------------------------
# The vectors of splat-32, generated from TYPED values: the expected output is
# built from the numbers below, not by running the decoder above, so the two
# are independent statements of one fact.
# ---------------------------------------------------------------------------

SPLAT32_RECORDS = [
    # position            scale (linear)            r    g    b    a    qw   qx   qy   qz
    ((0.0, 0.0, 0.0),     (1.0, 1.0, 1.0),          255, 255, 255, 255, 255, 128, 128, 128),
    ((0.5, -0.25, 2.0),   (0.125, 0.25, 0.5),       0,   128, 255, 1,   128, 255, 128, 128),
    ((-1.5, 3.0, -0.75),  (0.0625, 1.5, 2.0),       17,  34,  51,  128, 0,   128, 128, 128),
    ((100.0, -200.0, 0.001953125), (4.0, 0.5, 0.03125), 64, 64, 64, 0,  192, 64,  192, 64),
]


def splat32_vectors():
    inp, exp = bytearray(), bytearray()
    for pos, scl, r, g, b, a, qw, qx, qy, qz in SPLAT32_RECORDS:
        inp += struct.pack("<6f", *(pos + scl)) + bytes([r, g, b, a, qw, qx, qy, qz])
        exp += struct.pack("<14f", *(pos + scl + (
            r / 255.0, g / 255.0, b / 255.0, a / 255.0,
            (qw - 128) / 128.0, (qx - 128) / 128.0, (qy - 128) / 128.0, (qz - 128) / 128.0)))
    return [("four-records", bytes(inp), bytes(exp)), ("no-records", b"", b"")]


def print_vectors(fid):
    if fid != "splat-32":
        raise SystemExit("this script generates vectors for: splat-32")
    for vid, inp, exp in splat32_vectors():
        print("vector %s" % vid)
        print("  input_bytes   %d" % len(inp))
        print("  input_sha256  %s" % hashlib.sha256(inp).hexdigest())
        print("  output_bytes  %d" % len(exp))
        print("  output_sha256 %s" % hashlib.sha256(exp).hexdigest())
        hx = inp.hex()
        for i in range(0, len(hx), 64):
            print("  " + " ".join(hx[j:j + 8] for j in range(i, min(i + 64, len(hx)), 8)))


def check_doc(name, doc_bytes, declared_files=None):
    try:
        header, hexes = parse(doc_bytes)
    except (ValueError, UnicodeDecodeError) as e:
        print("FAIL %s: %s" % (name, e))
        return False
    bad = check_header(header, hexes, declared_files)
    dec = check_decode(header, hexes) if not bad else None
    if dec:
        bad += dec
    if bad:
        for b in bad:
            print("FAIL %s: %s" % (name, b))
        return False
    n = sum(1 for v in header["test_vectors"] if v["id"] in hexes)
    print("OK   %s: format `%s` v%s, coverage %s, %d vector(s), %d printed input(s) "
          "re-hashed%s"
          % (name, header["format_id"], header["format_version"], header["coverage"],
             len(header["test_vectors"]), n,
             ", every one DECODED and compared" if dec is not None else
             " (no decoder for this id here: hashes of inputs only)"))
    return True


def main(argv):
    if len(argv) >= 2 and argv[0] == "--vectors":
        print_vectors(argv[1])
        return 0
    if len(argv) >= 2 and argv[0] == "--check":
        ok = True
        for p in argv[1:]:
            with open(p, "rb") as fh:
                ok &= check_doc(p, fh.read())
        return 0 if ok else 1
    if len(argv) == 2 and argv[0] == "--check-package":
        z = zipfile.ZipFile(argv[1])
        m = json.loads(z.read("MANIFEST.json"))
        declared = {f["path"]: f["sha256"] for n in m["nodes"]
                    for v in n["versions"] for f in v["files"]}
        formats = dict(m.get("formats") or {})
        for n in m["nodes"]:
            for fid, path in ((n.get("meta") or {}).get("format_definitions") or {}).items():
                formats.setdefault(fid, path)
        if not formats:
            print("%s declares no format definitions" % argv[1])
            return 0
        ok = True
        for fid, path in sorted(formats.items()):
            ok &= check_doc("%s -> %s" % (fid, path), z.read(path), declared)
        return 0 if ok else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
