#!/usr/bin/env python3
"""build_smiley_werk.py -- the hardcopy round's payload.

`gauntlet/roundHC/smiley-v1.werk`: the smallest package this repository can
write that is still recognisably a werk -- profile `image/1`, one
`core.image.source` node carrying one 64x64 PNG, plus the licence and readme
nodes, a valid Ed25519 signature chain over the manifest, and every mandatory
manifest key present and correct.

WHY IT EXISTS. The hardcopy experiment prints a werk file onto paper as 2D
barcodes and asks a stranger to recover it. Every payload byte becomes ink, so
the payload had to be chosen for the *principle* rather than for coverage:
prose teaches a decoder, the decoder unlocks the barcodes, the barcodes yield a
file, the file opens and a smiling face appears. `mini-v1.werk` (938 756 B)
would have been 76 sheets of paper; this is one.

**THIS IS A DELIBERATELY REDUCED PACKAGE, and here is exactly what is missing
and why.** A full conformance fixture vendors its own `spec/` tree and its own
bootstrap `loaders/`; the smallest such tree in this repository
(`gauntlet/roundOW/mini-v1.werk`'s) is 252 KB of the file's 938 KB, and the
loaders are another 252 KB. On paper that is fifty sheets to say what the
printout is already saying in plain language on sheet one. So:

  * `spec/` is EMPTY. `schemas` is `{}` and `spec_sha256` is therefore the
    sha256 of the empty concatenation, `e3b0c442...b855`, which is the correct
    value of the declared algorithm over the empty file set and NOT a
    placeholder. A reader that compares it against a spec tree it knows will
    correctly conclude that this package vendors none.
  * `loaders/` is absent. The graded-effort argument's "structured access" tier
    is supplied here by the printed prose instead, which is the entire point of
    the artifact.
  * There is no `core.provenance`, no `core.semantics` and no
    `core.disclosure` node. Those are doctrine for a published asset and this
    package is a test payload.

`README.txt` inside the package says the same thing to whoever recovers it, so
the reduction is declared to the reader and not only to the repository.

Everything that IS present is real: the PNG is a valid PNG, every declared
sha256 is the sha256 of the bytes actually stored, the container is a store-mode
zip in declared `entry_order`, `preview_prefix_bytes` is converged to its fixed
point exactly as `fixtures/build_golden.py` does it, and the signature verifies
as `signed-and-valid` under the same publicly derived DEV key every fixture in
this repository uses.

Usage:  python build_smiley_werk.py [--out smiley-v1.werk]
"""

import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "fixtures"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import build_golden as BG                                    # noqa: E402
from spec_sha256 import spec_sha256_over                     # noqa: E402
from edge_targets import refuse_dangling_edges               # noqa: E402

import make_smiley                                           # noqa: E402

CREATED = "2026-08-09T00:00:00Z"
ENTITY_UUID = "3a7d5f02-9c14-4b6e-8f31-0d2e7a6c5b48"

MIT = """MIT License

Copyright (c) 2026 the werk project

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

README = """This file is a werk package: a zip container whose first entry,
MANIFEST.json, describes every other entry -- what it is, how big it is, and
its sha256. Open it with any zip tool; the entries are STORED, not deflated.

It carries one thing: a 64x64 PNG of a smiling face, at image/smiley.png.

REDUCED PACKAGE -- READ THIS. A normal werk package vendors its own copy of
the specification under spec/ and its own zero-dependency reader under
loaders/, so that the file explains itself to someone who has never heard of
the format. This one does not, and the omission is deliberate: this package was
built to be PRINTED ON PAPER as 2D barcodes, and the specification travels on
that paper, in plain language, beside the barcodes. If you are holding the
bytes and not the paper, the format's own documents are what is missing.

Consequently schemas is {} and spec_sha256 is the sha256 of the empty file set,
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855. That is the
declared algorithm's correct answer over nothing, not a placeholder.

The signature chain in SIGNATURE.json is real Ed25519 over the manifest, made
with a key that is published in the source tree and is therefore NOT a trust
anchor. Verify it if you like; do not trust it.
"""


def build():
    png = make_smiley.build()

    files = {
        "LICENSE": MIT.encode("utf-8"),
        "README.txt": README.encode("utf-8"),
        "image/smiley.png": png,
    }

    nodes = [
        {"node_id": "readme", "type": "core.readme",
         "versions": [{"v": 1,
                       "files": [{"path": "README.txt",
                                  "sha256": BG.sha256(files["README.txt"]),
                                  "size": len(files["README.txt"]),
                                  "media_type": "text/plain"}],
                       "note": "What this package is, and what it deliberately omits.",
                       "producer": {"tool": "gauntlet/roundHC/build_smiley_werk.py",
                                    "version": "1"},
                       "epistemic": "authored",
                       "created": CREATED}],
         "active": 1, "edges": []},
        {"node_id": "license", "type": "core.license",
         "versions": [{"v": 1,
                       "files": [{"path": "LICENSE",
                                  "sha256": BG.sha256(files["LICENSE"]),
                                  "size": len(files["LICENSE"]),
                                  "media_type": "text/plain"}],
                       "note": "Full licence text embedded, never a link (law 7).",
                       "producer": {"tool": "gauntlet/roundHC/build_smiley_werk.py",
                                    "version": "1"},
                       "epistemic": "authored",
                       "created": CREATED}],
         "active": 1, "edges": []},
        {"node_id": "image-source", "type": "core.image.source",
         "versions": [{"v": 1,
                       "files": [{"path": "image/smiley.png",
                                  "sha256": BG.sha256(png),
                                  "size": len(png),
                                  "media_type": "image/png"}],
                       "note": "A smiling face, 64x64, indexed colour, three palette "
                               "entries. Generated by gauntlet/roundHC/make_smiley.py "
                               "from integer arithmetic alone, so the bytes are the "
                               "same on every machine.",
                       "producer": {"tool": "gauntlet/roundHC/make_smiley.py",
                                    "version": "1"},
                       "epistemic": "authored",
                       "created": CREATED}],
         "active": 1, "edges": [],
         "meta": {"width": 64, "height": 64, "channels": 3, "bit_depth": 8,
                  "color_space": "srgb", "encoding": "png", "has_alpha": False}},
    ]

    entry_order = ["MANIFEST.json", "SIGNATURE.json", "LICENSE", "README.txt",
                   "image/"]

    def manifest(preview):
        return {
            "werk": {"major": 1, "minor": 0},
            "profile": "image/1",
            "entity": {
                "uuid": ENTITY_UUID,
                "name": "Smiley",
                "summary": "The hardcopy round's payload: the smallest recognisable "
                           "werk package, carrying one 64x64 PNG of a smiling face. "
                           "DELIBERATELY REDUCED -- it vendors no spec/ tree and no "
                           "loaders/, because it was built to be printed on paper as "
                           "2D barcodes and the specification travels on that paper. "
                           "See README.txt.",
                "created": CREATED},
            "conventions": {
                "endianness": "le", "color_space_default": "srgb",
                "pixel_origin": "top-left", "alpha_mode": "straight",
                "alignment_bytes": 16, "text_encoding": "utf-8",
                "id_case": "kebab-case", "hash_algorithm": "sha256",
                "signature_algorithm": "ed25519"},
            "container": {"form": "zip", "zip_compression": "store",
                          "entry_order": entry_order,
                          "preview_tier": entry_order,
                          "preview_prefix_bytes": preview},
            "primary": {"image": "image-source"},
            "license": {"spdx_id": "MIT", "file": "LICENSE",
                        "sha256": BG.sha256(files["LICENSE"])},
            "spec_sha256": spec_sha256_over({}),
            "schemas": {},
            "signature_file": "SIGNATURE.json",
            "nodes": nodes,
        }

    refuse_dangling_edges(nodes)       # SPEC section 5

    # converge preview_prefix_bytes to its fixed point, as build_golden does
    preview = 0
    entries = None
    for _ in range(8):
        mb = BG.jbytes(manifest(preview))
        sb = BG.jbytes(BG.sign(mb, "Signed with the same publicly derived DEV key as "
                                   "every fixture in this repository. Not a trust anchor."))
        allf = dict(files)
        allf["MANIFEST.json"] = mb
        allf["SIGNATURE.json"] = sb
        order = [p for p in ["MANIFEST.json", "SIGNATURE.json", "LICENSE",
                             "README.txt", "image/smiley.png"]]
        entries = [(p, allf[p]) for p in order]
        cursor = prefix = 0
        for name, data in entries:
            prefix = cursor = cursor + 30 + len(name.encode("utf-8")) + len(data)
        if prefix == preview:
            break
        preview = prefix
    else:
        raise SystemExit("preview_prefix_bytes did not converge")

    return BG.write_zip(entries), mb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "smiley-v1.werk"))
    args = ap.parse_args()
    blob, mb = build()
    with open(args.out, "wb") as fh:
        fh.write(blob)
    print("wrote %s" % args.out)
    print("  %d bytes, sha256 %s" % (len(blob), hashlib.sha256(blob).hexdigest()))
    print("  manifest %d bytes, sha256 %s" % (len(mb), BG.sha256(mb)))
    print("  spec_sha256 %s" % json.loads(mb)["spec_sha256"])


if __name__ == "__main__":
    main()
