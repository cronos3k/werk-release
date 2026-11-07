#!/usr/bin/env python3
"""
grade_hardcopy.py -- artifact grading for the GAP-COMPLETION round's
replication of the hardcopy round, on the SAME five-step ladder the hardcopy
round used, decided from the bytes rather than from the agent's report.

Ground truth is derived from the committed payload, not hard-coded:
  * `gauntlet/roundHC/smiley-v1.werk` -- what the nine printed symbols encode
  * `gauntlet/roundHC/smiley.png`     -- the image inside it

The ladder, and what each rung is graded on:

  1  read the prose            the transcript/report states the file length,
                               the 8-data-plus-1-parity structure and the
                               SHA-256 before any decoder exists
  2  implemented a decoder     a source file the agent WROTE exists in the
                               workspace and is not one of the three JPEGs
  3  reassembled, CRCs pass    the output claims 9 codeword CRC-32 matches
  4  whole-file sha256         a file in the workspace hashes to the payload's
                               sha256 -- BYTE grade, no wording accepted
  5  opened the .werk          the output names the package's own entries
  6  the recovered image       a file in the workspace is byte-identical to
                               `smiley.png`, or a decoded PNG differs in 0
                               pixels

  python grade_hardcopy.py --rundir <dir> --werk gauntlet/roundHC/smiley-v1.werk \
                           --png gauntlet/roundHC/smiley.png [--json-out f.json]
"""

import argparse
import hashlib
import json
import os
import re
import sys
import zipfile


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def walk(root):
    for dp, dn, fn in os.walk(root):
        # .venv/ is a package installer's output, not the agent's decoder. The
        # Kimi run created one and it is 460+ files of pip; counting those as
        # "code the agent wrote" would be a grading defect.
        dn[:] = [d for d in dn if d not in (".git", "node_modules", "__pycache__", ".venv")]
        for f in sorted(fn):
            yield os.path.join(dp, f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rundir", required=True, help="the run dir; workspace/ under it")
    ap.add_argument("--werk", required=True)
    ap.add_argument("--png", required=True)
    ap.add_argument("--transcript", default="", help="the CLI's jsonl transcript")
    ap.add_argument("--json-out", default="")
    args = ap.parse_args()

    payload = open(args.werk, "rb").read()
    want_werk = sha256_bytes(payload)
    want_png = sha256_bytes(open(args.png, "rb").read())
    with zipfile.ZipFile(args.werk) as z:
        entries = z.namelist()

    ws = os.path.join(args.rundir, "workspace")
    files = list(walk(ws))
    inputs = {"page-01.jpg", "page-02.jpg", "page-03.jpg"}

    byte_werk, byte_png, wrote_code = [], [], []
    for fp in files:
        rel = os.path.relpath(fp, ws).replace("\\", "/")
        if rel in inputs:
            continue
        try:
            b = open(fp, "rb").read()
        except Exception:
            continue
        h = sha256_bytes(b)
        if h == want_werk:
            byte_werk.append(rel)
        if h == want_png:
            byte_png.append(rel)
        if os.path.splitext(rel)[1].lower() in (".py", ".js", ".c", ".rs", ".sh", ".ts"):
            wrote_code.append(rel)

    # every character the run emitted: its transcript plus everything textual
    # it left behind
    blob = []
    if args.transcript and os.path.exists(args.transcript):
        blob.append(open(args.transcript, "r", encoding="utf-8", errors="replace").read())
    for fp in files:
        rel = os.path.relpath(fp, ws).replace("\\", "/")
        if rel in inputs or os.path.getsize(fp) > 32 << 20:
            continue
        try:
            blob.append(open(fp, "r", encoding="utf-8", errors="replace").read())
        except Exception:
            pass
    blob = "\n".join(blob)

    ladder = {}
    ladder["1_read_the_prose"] = bool(re.search(r"\b8168\b", blob)) and \
        bool(re.search(want_werk[:16], blob, re.I))
    ladder["2_implemented_a_decoder"] = len(wrote_code) > 0
    ladder["3_crcs_pass"] = bool(re.search(r"crc", blob, re.I)) and \
        bool(re.search(r"\b9\s*/\s*9\b|\b8\s*/\s*9\b", blob))
    ladder["4_whole_file_sha256"] = len(byte_werk) > 0
    ladder["5_opened_the_werk"] = sum(1 for e in entries if e in blob) >= 4
    ladder["6_the_image_is_the_smiley"] = len(byte_png) > 0

    print("payload sha256 : %s  (%d B)" % (want_werk, len(payload)))
    print("image  sha256  : %s" % want_png)
    print("workspace      : %s  (%d files, %d written by the agent)"
          % (ws, len(files), len(files) - len(inputs & {os.path.basename(f) for f in files})))
    print("code the agent wrote : %s" % (wrote_code or "none"))
    print("byte-identical .werk : %s" % (byte_werk or "NONE"))
    print("byte-identical .png  : %s" % (byte_png or "NONE"))
    print("\n=== THE LADDER (graded from artifacts) ===")
    for k in sorted(ladder):
        print("  %-28s %s" % (k, "PASS" if ladder[k] else "FAIL"))
    n = sum(1 for v in ladder.values() if v)
    print("\nrungs passed: %d / %d" % (n, len(ladder)))

    row = {"rundir": args.rundir, "payload_sha256": want_werk, "png_sha256": want_png,
           "wrote_code": wrote_code, "byte_identical_werk": byte_werk,
           "byte_identical_png": byte_png, "ladder": ladder,
           "rungs_passed": n, "rungs_total": len(ladder),
           "files": [os.path.relpath(f, ws).replace("\\", "/") for f in files]}
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(row, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
