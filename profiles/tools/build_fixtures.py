#!/usr/bin/env python3
"""build_fixtures.py -- build the six profile fixtures in dependency order, twice, and pin them.

    python profiles/tools/build_fixtures.py [--out profiles/fixtures] [--check]

Order: raster-layers, vector-art, motion-comp, spreadsheet, then rich-document (embeds the
raster composite) and presentation (embeds the vector-art package and the raster composite).
Each builder asserts its own ground truth (its reference reader must give back what it wrote).
Every fixture is built a second time into a scratch directory and compared byte for byte.
Writes <out>/fixtures.json (name, profile, bytes, sha256, manifest sha256, spec_sha256).
--check: build into scratch only and compare with the committed fixtures and fixtures.json.
"""
import argparse
import hashlib
import importlib
import json
import os
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILES = os.path.dirname(HERE)
ORDER = ["raster-layers", "vector-art", "motion-comp", "spreadsheet", "rich-document", "presentation"]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def builder(name):
    d = os.path.join(PROFILES, name)
    if d not in sys.path:
        sys.path.insert(0, d)
    return importlib.import_module("build_" + name.replace("-", "_"))


def build_all(out):
    os.makedirs(out, exist_ok=True)
    res = {}
    for name in ORDER:
        b = builder(name)
        path = os.path.join(out, "%s-v1.werk" % name)
        if name == "rich-document":
            b.build(path, os.path.join(out, "raster-layers-v1.werk"))
        elif name == "presentation":
            b.build(path, os.path.join(out, "vector-art-v1.werk"), os.path.join(out, "raster-layers-v1.werk"))
        else:
            b.build(path)
        data = open(path, "rb").read()
        man = zipfile.ZipFile(path).read("MANIFEST.json")
        m = json.loads(man)
        res[name] = {"file": "%s-v1.werk" % name, "profile": m["profile"], "bytes": len(data), "sha256": sha(data),
                     "manifest_sha256": sha(man), "spec_sha256": m["spec_sha256"], "nodes": len(m["nodes"]),
                     "files": sum(len(n["versions"][n["active"] - 1]["files"]) for n in m["nodes"])}
        print("%-14s %8d  %s" % (name, len(data), res[name]["sha256"]))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(PROFILES, "fixtures"))
    ap.add_argument("--scratch", default=None)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    scratch = a.scratch or os.path.join(PROFILES, "_scratch_build")
    if os.path.isdir(scratch):
        shutil.rmtree(scratch)
    if a.check:
        second = build_all(scratch)
        pinned = json.load(open(os.path.join(a.out, "fixtures.json"), encoding="utf-8"))["fixtures"]
        bad = [n for n in ORDER if second[n]["sha256"] != pinned[n]["sha256"]
               or sha(open(os.path.join(a.out, pinned[n]["file"]), "rb").read()) != pinned[n]["sha256"]]
        shutil.rmtree(scratch)
        print("check: %s" % ("all six reproduce byte for byte" if not bad else "DIFFER: %s" % bad))
        return 1 if bad else 0
    first = build_all(a.out)
    print("-- second build (determinism) --")
    second = build_all(scratch)
    shutil.rmtree(scratch)
    same = all(first[n]["sha256"] == second[n]["sha256"] for n in ORDER)
    print("deterministic: %s" % same)
    if not same:
        return 1
    doc = {"note": "The six profile fixtures of the werk release, built by profiles/tools/build_fixtures.py "
                   "(Python %d.%d, zlib %s). zlib streams inside them come from the zlib the builder ran with; "
                   "another zlib build may compress differently (the inflated bytes, and every reader's result, "
                   "are the same)." % (sys.version_info[0], sys.version_info[1], __import__("zlib").ZLIB_RUNTIME_VERSION),
           "fixtures": first}
    with open(os.path.join(a.out, "fixtures.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
