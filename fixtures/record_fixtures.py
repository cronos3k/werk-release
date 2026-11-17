#!/usr/bin/env python3
"""record_fixtures.py -- the ONE place a fixture's size and sha256 are recorded.

    python fixtures/record_fixtures.py            # rewrite fixtures.json + FIXTURES.md
    python fixtures/record_fixtures.py --check    # verify without writing (gate use)

WHY THIS EXISTS. Stage 8's paper agent re-measured the shipped fixtures against
the numbers the documents recorded and found five bookkeeping drifts (S8-1 to
S8-5): `crate-v1.werk` recorded at one byte count with TWO different sha256s in
two sections of one document; the retarget fixture two bytes off its record;
a profile-2 file count stale by one; four recorded sizes for one fixture name
with nothing saying which build was which; and a zip-entry count labelled a
file count. None of them is a format defect. All of them are the same mistake:
a number transcribed into prose in more than one place, where the copies cannot
disagree loudly.

So the numbers live HERE, once, as data. `FIXTURES.md` is generated from this
file and never hand-edited, HANDOVER points at it instead of repeating it, and
every gate harness pins the fixture it measures by calling
`tests/fixture_pin.py`, which reads this file. A rebuild that changes a fixture
now fails the gate with the old and new hash in the message, instead of quietly
changing what the gate measured.

Run it after any fixture rebuild. `--check` is what a gate runs.
"""

import argparse
import hashlib
import json
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
JSON_PATH = os.path.join(HERE, "fixtures.json")
MD_PATH = os.path.join(HERE, "FIXTURES.md")

#: (key, package-relative path, builder, one-line purpose)
FIXTURES = [
    ("crate-v1", "fixtures/crate-v1.werk", "fixtures/build_golden.py",
     "The golden sample: profile 3d-entity/1, built from a real splat-foley run. "
     "A complete audio family, no custom binaries, vertex-coloured so it has no core.tex."),
    ("crate-v1-damaged", "fixtures/crate-v1-damaged.werk", "fixtures/build_golden.py",
     "The golden sample with one flipped byte in a WAV and one unknown node type, "
     "so a reader's damage path is measured rather than argued about."),
    ("crate-tex-v1", "fixtures/crate-tex-v1.werk", "fixtures/build_crate_tex.py",
     "The TEXTURED fixture: three generated maps and their material slots, built "
     "through the gate-proven Blender exporter so the texture path has a measured input."),
    ("ista-varun-v1", "fixtures/ista-varun-v1.werk", "fixtures/build_image_fixture.py",
     "Profile image/1: a real AI-generated image with its true recipe, a "
     "core.disclosure, a WKEM envelope payload, and the S-18 shared-file case on purpose."),
    ("humanoid-retarget-v1", "fixtures/humanoid-retarget-v1.werk", "fixtures/build_retarget_fixture.py",
     "The first package to carry a core.skeleton and a core.anim.clip: CMU take "
     "02_01 retargeted onto the canonical humanoid, so WKAC stops being unexercised."),
    ("gsplat-v1", "fixtures/gsplat-v1.werk", "fixtures/build_gsplat_fixture.py",
     "Stage 12: a REAL captured 3D Gaussian splat (281 498 Gaussians), its exact "
     "DC-band point-cloud degradation, and the SOURCE CODE of the three tools that "
     "made them -- the first package to carry a WKGS, a WKPC, a core.tool or a "
     "core.tool.config, and the first whose gate regenerates the payload by running "
     "the file's own embedded converters on the file's own embedded input."),
    ("crate-synthetic", "tests/fixtures/crate.werk", "cargo run --bin werkc -- build-fixture tests/fixtures",
     "The minimal synthetic fixture: every custom-binary path exercised, small "
     "enough to check by hand, signed with the RFC 8032 test key."),
    ("mini-v1", "gauntlet/roundOW/mini-v1.werk",
     "gauntlet/roundOW/build_mini_fixture.py",
     "The small-context fixture, rebuilt under the ruling on #11: the same 36 "
     "entries as the package the trials ran on, minus its three edges to absent "
     "nodes (SPEC section 5), so it verifies clean. It carries a trimmed spec/ "
     "tree (the documents its own node types need), so its spec_sha256 is the "
     "hash of that subset. The trials' bytes are kept at "
     "gauntlet/roundOW/historical/mini-v1-f7bdcc85.werk."),
    ("mini-v1-historical", "gauntlet/roundOW/historical/mini-v1-f7bdcc85.werk",
     "an earlier build_mini_fixture.py (kept, not rebuilt)",
     "The exact mini-v1.werk that the open-weights, DeepSeek and second-lab "
     "trials ran on, built from an earlier spec revision. It carries three edges "
     "to absent nodes, so a conformant reader reports one dead node. Kept so "
     "pinned trials stay checkable."),
    # The public-domain arm (fixtures/CC0-FIXTURES.md). Recorded HERE since
    # 2026-10-13: until then these eight were pinned by nothing but a
    # hand-typed table in that document, which is the S8 mistake this file
    # exists to end, and one of their gates rebuilt them in place on every run
    # (finding F-AC-5).
    ("crate-cc0-lean-v1", "fixtures/crate-cc0-lean-v1.werk", "fixtures/build_crate_cc0.py --variant lean",
     "The public-domain crate, lean: mesh, three procedural textures, material, "
     "measured bounds, a disclosure. Rebuildable from this repository alone."),
    ("crate-cc0-lean-v1-damaged", "fixtures/crate-cc0-lean-v1-damaged.werk", "fixtures/build_crate_cc0.py --variant lean",
     "The lean CC0 crate with one flipped payload byte and one unknown node type."),
    ("crate-cc0-full-v1", "fixtures/crate-cc0-full-v1.werk", "fixtures/build_crate_cc0.py --variant full",
     "The public-domain crate, full: lean plus a synthetic WAV, evidence images, "
     "semantics and properties."),
    ("crate-cc0-full-v1-damaged", "fixtures/crate-cc0-full-v1-damaged.werk", "fixtures/build_crate_cc0.py --variant full",
     "The full CC0 crate with one flipped payload byte and one unknown node type."),
    ("image-cc0-v1", "fixtures/image-cc0-v1.werk", "fixtures/build_image_cc0.py",
     "Profile image/1 from public-domain inputs: the publicly reproducible twin "
     "of ista-varun-v1 (ruling R3 of 2026-09-09)."),
    ("image-cc0-v1-damaged", "fixtures/image-cc0-v1-damaged.werk", "fixtures/build_image_cc0.py",
     "The CC0 image package with one flipped payload byte and one unknown node type."),
    ("gsplat-cc0-v1", "fixtures/gsplat-cc0-v1.werk", "fixtures/build_gsplat_cc0.py",
     "A synthetic public-domain Gaussian splat and its DC-band point cloud: the "
     "publicly reproducible twin of gsplat-v1."),
    ("gsplat-cc0-v1-damaged", "fixtures/gsplat-cc0-v1-damaged.werk", "fixtures/build_gsplat_cc0.py",
     "The CC0 splat package with one flipped payload byte."),
    ("crate-cc0-lean-v1-deflated", "fixtures/crate-cc0-lean-v1-deflated.werk", "fixtures/build_deflated_fixture.py",
     "The ONLY fixture whose zip entries are DEFLATED (method 8): the lean CC0 "
     "crate's content, byte for byte, compressed by zlib, so that the four "
     "reference readers' inflate is tested against streams none of them wrote "
     "(ruling 9 of 2026-10-13). Its bytes depend on the zlib version that built it."),
]


def measure(rel):
    path = os.path.join(ROOT, rel.replace("/", os.sep))
    with open(path, "rb") as fh:
        data = fh.read()
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        manifest = json.loads(z.read("MANIFEST.json"))
    declared = set()
    for n in manifest.get("nodes", []):
        for v in n.get("versions", []):
            for f in v.get("files", []):
                declared.add(f["path"])
    return {
        "path": rel,
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        # Counted separately and NAMED separately, because "166 files" was a
        # zip-entry count wearing a file count's label (S8-5), and the two
        # differ by exactly the two paths the format's own reachability rule
        # excludes: MANIFEST.json and SIGNATURE.json are entries and are
        # deliberately in no node's files[] (SPEC section 2, D-MAN-1).
        "zip_entries": len(names),
        "declared_files": len(declared),
        "nodes": len(manifest.get("nodes", [])),
        "profile": manifest.get("profile"),
        "manifest_sha256": hashlib.sha256(z_read_manifest(path)).hexdigest(),
        "spec_sha256": manifest.get("spec_sha256"),
    }


def z_read_manifest(path):
    with zipfile.ZipFile(path) as z:
        return z.read("MANIFEST.json")


def build():
    out = {
        "note": ("Generated by fixtures/record_fixtures.py. THE numbers for "
                 "every conformance fixture, recorded once. Do not transcribe "
                 "them into prose in more than one place; point at this file. "
                 "Gates pin against it through tests/fixture_pin.py."),
        "recorded": "2026-10-13",
        "fixtures": {},
    }
    for key, rel, builder, purpose in FIXTURES:
        rec = measure(rel)
        rec["builder"] = builder
        rec["purpose"] = purpose
        out["fixtures"][key] = rec
    return out


def render_md(doc):
    L = []
    L.append("# The conformance fixtures — sizes, hashes, and what each is for")
    L.append("")
    L.append("**Generated by `fixtures/record_fixtures.py`. Do not hand-edit.**")
    L.append("Re-run it after any fixture rebuild; `--check` is what a gate runs.")
    L.append("")
    L.append("This file exists because the same fixture name denoted different")
    L.append("bytes in different sections of `HANDOVER.md`, and only one section")
    L.append("said so (findings S8-1 … S8-5). A number transcribed into prose in")
    L.append("several places is a number whose copies cannot disagree loudly. The")
    L.append("numbers now live in `fixtures/fixtures.json`, this table is rendered")
    L.append("from it, and every gate harness pins the fixture it measures against")
    L.append("it through `tests/fixture_pin.py` — so a rebuild fails a gate with")
    L.append("the old and the new hash in the message instead of quietly changing")
    L.append("what the gate measured.")
    L.append("")
    L.append("Recorded: **%s**" % doc["recorded"])
    L.append("")
    L.append("| fixture | bytes | sha256 | zip entries | declared files | nodes | profile |")
    L.append("|---|---:|---|---:|---:|---:|---|")
    for key, r in doc["fixtures"].items():
        L.append("| `%s` | %s | `%s` | %d | %d | %d | `%s` |"
                 % (r["path"], "{:,}".format(r["size_bytes"]).replace(",", " "),
                    r["sha256"], r["zip_entries"], r["declared_files"],
                    r["nodes"], r["profile"]))
    L.append("")
    L.append("**Zip entries and declared files are different counts and are named")
    L.append("differently on purpose.** They differ by exactly two: `MANIFEST.json`")
    L.append("and `SIGNATURE.json` are container entries and are deliberately in no")
    L.append("node's `files[]`, because the manifest hashes every file it lists and")
    L.append("the signature signs the manifest (SPEC §2, D-MAN-1). Calling entries")
    L.append("\"files\" makes that off-by-two read as a bug in the rule (S8-5).")
    L.append("")
    L.append("## What each one is for, and what builds it")
    L.append("")
    for key, r in doc["fixtures"].items():
        L.append("### `%s`" % r["path"])
        L.append("")
        L.append(r["purpose"])
        L.append("")
        L.append("* built by `%s`" % r["builder"])
        L.append("* manifest sha256 `%s`" % r["manifest_sha256"])
        L.append("* `spec_sha256` `%s`" % r["spec_sha256"])
        L.append("")
    L.append("Every fixture in this table carries the same `spec_sha256`, which is")
    L.append("the point of the field (S-29): they were all built from one revision")
    L.append("of `spec/`, and a package built from another one says so in a single")
    L.append("comparison rather than by a schema diff nobody runs. Three rows differ")
    L.append("on purpose: `crate-synthetic` and `mini-v1` carry a trimmed `spec/`")
    L.append("tree (byte-identical documents, fewer of them), so the field hashes")
    L.append("that subset; `mini-v1-historical` is the earlier build the trials ran")
    L.append("on and carries the earlier spec revision.")
    L.append("")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="verify the recorded numbers without writing")
    args = ap.parse_args(argv)
    doc = build()
    if args.check:
        if not os.path.isfile(JSON_PATH):
            raise SystemExit("fixtures.json is missing; run without --check")
        with open(JSON_PATH, encoding="utf-8") as fh:
            old = json.load(fh)
        bad = []
        for key, rec in doc["fixtures"].items():
            prev = old["fixtures"].get(key)
            if prev is None:
                bad.append("%s: not recorded" % key)
            elif prev["sha256"] != rec["sha256"] or prev["size_bytes"] != rec["size_bytes"]:
                bad.append("%s: recorded %d B / %s, on disk %d B / %s"
                           % (key, prev["size_bytes"], prev["sha256"][:16],
                              rec["size_bytes"], rec["sha256"][:16]))
        for line in bad:
            print("DRIFT " + line)
        print("%d/%d fixtures match their record"
              % (len(doc["fixtures"]) - len(bad), len(doc["fixtures"])))
        return 1 if bad else 0
    with open(JSON_PATH, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=2, sort_keys=False)
        fh.write("\n")
    with open(MD_PATH, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(render_md(doc))
    print("wrote %s and %s (%d fixtures)"
          % (os.path.relpath(JSON_PATH, ROOT), os.path.relpath(MD_PATH, ROOT),
             len(doc["fixtures"])))
    for key, r in doc["fixtures"].items():
        print("  %-24s %10d B  %s" % (key, r["size_bytes"], r["sha256"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
