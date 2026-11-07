#!/usr/bin/env python3
"""verify_roundtrip.py -- the control run.

Decodes a directory of page images with `wcode`'s reference decoder, reassembles
the file, checks its sha256 against the payload the pages were made from, and --
because the payload is a picture -- checks the recovered image pixel for pixel
against `make_smiley.py`'s reference output.

This is the experiment's own control, not its result. It establishes that the
degraded pages ARE recoverable before a fresh agent is asked to recover them, so
that a failure by that agent is a statement about the printed prose and not
about the paper.

Usage:  python verify_roundtrip.py [--pages pages/scanned] [--payload smiley-v1.werk]
"""
import argparse, hashlib, io, json, os, sys, time, zipfile
import wcode, make_smiley

HERE = os.path.dirname(os.path.abspath(__file__))

ap = argparse.ArgumentParser()
ap.add_argument("--pages", default=os.path.join(HERE, "pages", "scanned"))
ap.add_argument("--payload", default=os.path.join(HERE, "smiley-v1.werk"))
args = ap.parse_args()

want = open(args.payload, "rb").read()
want_sha = hashlib.sha256(want).hexdigest()

t0 = time.monotonic()
recs = []
for name in sorted(os.listdir(args.pages)):
    if not name.lower().endswith((".png", ".jpg", ".jpeg")):
        continue
    got, diag = wcode.decode_image(os.path.join(args.pages, name))
    print("%-16s regions=%-3d sampled=%-3d frame_reject=%-3d crc_fail=%-3d decoded=%d"
          % (name, diag["boxes"], diag["sampled"], diag["frame_reject"],
             diag["crc_fail"], len(got)))
    recs.extend(got)
elapsed = time.monotonic() - t0

data, rep = wcode.assemble(recs)
print("assemble:", json.dumps(rep))
if data is None:
    sys.exit("FAIL: could not assemble")

got_sha = hashlib.sha256(data).hexdigest()
print("recovered %d bytes, sha256 %s" % (len(data), got_sha))
print("sha256 matches payload: %s" % (got_sha == want_sha))
if got_sha != want_sha:
    sys.exit("FAIL: digest mismatch")

z = zipfile.ZipFile(io.BytesIO(data))
man = json.loads(z.read("MANIFEST.json"))
print("opens as a werk package: profile=%s entity=%r entries=%d"
      % (man["profile"], man["entity"]["name"], len(z.namelist())))
for n in man["nodes"]:
    for v in n["versions"]:
        for f in v["files"]:
            b = z.read(f["path"])
            ok = hashlib.sha256(b).hexdigest() == f["sha256"] and len(b) == f["size"]
            print("  %-20s %-6d %s" % (f["path"], f["size"], "hash OK" if ok else "HASH FAIL"))
            if not ok:
                sys.exit("FAIL: declared hash mismatch")

png = z.read("image/smiley.png")
print("smiley bytes identical to make_smiley.py: %s" % (png == make_smiley.build()))
from PIL import Image
a = Image.open(io.BytesIO(png)).convert("RGB")
b = Image.open(io.BytesIO(make_smiley.build())).convert("RGB")
diff = sum(1 for p, q in zip(a.getdata(), b.getdata()) if p != q)
print("pixel differences over %d pixels: %d" % (a.width * a.height, diff))
print("decode wall clock: %.1f s" % elapsed)
print("RESULT: PASS" if diff == 0 else "RESULT: FAIL")
