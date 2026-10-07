#!/usr/bin/env python3
"""
make_prompts.py -- generate the roundNC task prompts by scripted substitution.

Plan section 2.1/2.2: every control prompt is PROMPT-round1task-mini.txt
reproduced byte-for-byte with ONLY these permitted edits:

  E1  filename swap: mini-v1.werk -> control filename (all 3 occurrences:
      TASK line, hard constraint 1, hard constraint 5).
  E2  (only with --payload texture) EVERY occurrence of "one sound" ->
      "one texture": the TASK sentence and REPORTING bullet 1 (2 occurrences).
      Amendment to ruling R2 (Yuvraj, 2026-10-07, decision D2): the texture
      variant must be internally consistent, so E2 covers both places. All
      other REPORTING wording ("node graph", "values the manifest declares",
      ...) stays verbatim.
  E3  (glTF only) hard constraint 1: "is mini-v1.werk and its contents" ->
      "is crate-nc-v1.gltf and the N files it references (...)".

This script IS the proof that no other edit exists: the substitution table
below is the complete list, each substitution asserts its exact occurrence
count, and a line diff against the source is checked to touch only the lines
those substitutions own. The werk baseline is the source file verbatim and is
asserted byte-identical.

Usage:
  py -3.13 make_prompts.py [--src PATH] [--out DIR] [--payload sound|texture|both]
  py -3.13 make_prompts.py --check       # re-derive and compare with files on disk

Standard library only. Output files are written as raw bytes (UTF-8, LF), the
same encoding and line endings as the source.
"""

import argparse
import difflib
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SRC = os.path.normpath(os.path.join(
    HERE, "..", "werk", "gauntlet", "roundOW", "PROMPT-round1task-mini.txt"))
if not os.path.exists(DEFAULT_SRC):  # after the move to gauntlet/roundNC/
    DEFAULT_SRC = os.path.normpath(os.path.join(
        HERE, "..", "roundOW", "PROMPT-round1task-mini.txt"))

SRC_NAME = "mini-v1.werk"

# Control fixtures (plan 1.2). GLTF_SIDECARS are the URIs the built
# crate-nc-v1.gltf references (buffers[0].uri, images[0].uri), checked by
# build_gltf_usdz.py. They equal the plan's names, so clause E3 holds.
CONTROLS = {
    "fbx": "crate-nc-v1.fbx",
    "gltf": "crate-nc-v1.gltf",
    "usdz": "crate-nc-v1.usdz",
}
GLTF_SIDECARS = ["crate-nc-v1.bin", "crate_diffuse.png"]

_NUMWORD = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}

# E2 anchor. "one sound" occurs exactly TWICE in the source: the TASK line
# ("extracts the primary mesh and one sound to disk") and REPORTING bullet 1
# ("and one sound, and do the extracted bytes hash ..."). R2 as amended:
# both are replaced, and the count assertion below pins the 2.
E2_OLD = "one sound"
E2_NEW = "one texture"
E2_COUNT = 2

# E3 anchor (hard constraint 1).
E3_OLD = "is " + SRC_NAME + " and its contents"


def e3_new(fname, sidecars):
    return "is %s and the %s files it references (%s)" % (
        fname, _NUMWORD[len(sidecars)], ", ".join(sidecars))


def substitutions(fmt, payload):
    """The COMPLETE list of edits for one prompt. (tag, old, new, count)."""
    if fmt == "werk":
        return []
    fname = CONTROLS[fmt]
    subs = []
    if fmt == "gltf":
        # E3 must run before E1, because E1 would otherwise consume the
        # filename inside the E3 anchor.
        subs.append(("E3 glTF multi-file clause (constraint 1)",
                     E3_OLD, e3_new(fname, GLTF_SIDECARS), 1))
        subs.append(("E1 filename swap (TASK line, constraint 5)",
                     SRC_NAME, fname, 2))
    else:
        subs.append(("E1 filename swap (TASK line, constraint 1, constraint 5)",
                     SRC_NAME, fname, 3))
    if payload == "texture":
        subs.append(("E2 sound->texture (TASK sentence + REPORTING bullet 1, R2 amended)",
                     E2_OLD, E2_NEW, E2_COUNT))
    return subs


def generate(src_text, fmt, payload):
    t = src_text
    applied = []
    for tag, old, new, n in substitutions(fmt, payload):
        got = t.count(old)
        if got != n:
            raise SystemExit("ABORT %s/%s: %r occurs %d times, expected %d"
                             % (fmt, payload, old, got, n))
        t = t.replace(old, new)
        applied.append((tag, old, new, n))
    if fmt != "werk" and SRC_NAME in t:
        raise SystemExit("ABORT %s: source filename survived substitution" % fmt)
    return t, applied


def changed_lines(a, b):
    """Indices (0-based, in the source) of lines that differ."""
    sm = difflib.SequenceMatcher(a=a.splitlines(), b=b.splitlines(), autojunk=False)
    out = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op != "equal":
            out.extend(range(i1, max(i2, i1 + 1)))
    return out


def owned_lines(src, applied):
    """Source line indices that contain an anchor of an applied substitution."""
    lines = src.splitlines()
    own = set()
    for _, old, _, _ in applied:
        for i, ln in enumerate(lines):
            if old in ln:
                own.add(i)
    return own


def out_name(fmt):
    return "PROMPT-%s.txt" % fmt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--out", default=os.path.join(HERE, "prompts"))
    ap.add_argument("--payload", choices=["sound", "texture", "both"], default="both")
    ap.add_argument("--check", action="store_true",
                    help="do not write; compare re-derived bytes with files on disk")
    args = ap.parse_args()

    with open(args.src, "rb") as f:
        src_bytes = f.read()
    src = src_bytes.decode("utf-8")
    if b"\r\n" in src_bytes:
        raise SystemExit("ABORT: source has CRLF line endings; expected LF")
    print("source        : %s" % args.src)
    print("source sha256 : %s  (%d bytes)" % (hashlib.sha256(src_bytes).hexdigest(), len(src_bytes)))

    payloads = ["sound", "texture"] if args.payload == "both" else [args.payload]
    bad = 0
    for payload in payloads:
        outdir = os.path.join(args.out, payload)
        if not args.check:
            os.makedirs(outdir, exist_ok=True)
        for fmt in ["werk", "fbx", "gltf", "usdz"]:
            # The werk baseline keeps "one sound" verbatim in BOTH payload
            # sets (plan 2.1: "The werk baseline trials keep 'one sound'
            # verbatim"). It is copied into each set so each directory is a
            # complete prompt set for its D2 option.
            text, applied = generate(src, fmt, "sound" if fmt == "werk" else payload)
            data = text.encode("utf-8")
            if fmt == "werk":
                assert data == src_bytes, "werk baseline is not byte-identical"
            # Diff-ownership proof: every changed line must contain an anchor.
            ch = set(changed_lines(src, text))
            own = owned_lines(src, applied)
            stray = sorted(ch - own)
            if stray:
                raise SystemExit("ABORT %s/%s: unowned changed source lines %s"
                                 % (fmt, payload, [i + 1 for i in stray]))
            path = os.path.join(outdir, out_name(fmt))
            print("\n=== %s/%s ===" % (payload, out_name(fmt)))
            print("sha256 %s  %d bytes" % (hashlib.sha256(data).hexdigest(), len(data)))
            if fmt == "werk":
                print("  verbatim copy of source (asserted byte-identical)")
            for tag, old, new, n in applied:
                print("  %s  x%d" % (tag, n))
                print("      - %r" % old)
                print("      + %r" % new)
            print("  changed source lines: %s" % (sorted(i + 1 for i in ch) or "none"))
            for d in difflib.unified_diff(src.splitlines(), text.splitlines(),
                                          "source", out_name(fmt), n=0, lineterm=""):
                print("    " + d)
            if args.check:
                try:
                    with open(path, "rb") as f:
                        disk = f.read()
                except OSError:
                    disk = None
                ok = disk == data
                bad += 0 if ok else 1
                print("  CHECK on-disk file: %s" % ("IDENTICAL" if ok else "DIFFERS/MISSING"))
            else:
                with open(path, "wb") as f:
                    f.write(data)
    if args.check and bad:
        sys.exit(1)


if __name__ == "__main__":
    main()
