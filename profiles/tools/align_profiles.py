#!/usr/bin/env python3
"""align_profiles.py -- the edits that make the vendored ArtCraft profile definitions accept a
package written by the release library (release spec 55882f4b..., libs bundle 509ebf8).

Every edit is listed in EDITS with its reason; the script applies them to the files that
vendor_artcraft.py copied (idempotent: an edit already applied is skipped) and writes
profiles/ALIGNMENT.json with the sha256 of each file before and after. No file of the release
spec/ is touched: these are the profiles' own documents, which travel in their packages
(SPEC section 2.2).

usage: align_profiles.py --repo <stage/werk>
"""
import argparse, hashlib, json, os

PROFILES = ["raster-layers", "vector-art", "motion-comp", "rich-document", "spreadsheet", "presentation"]
RELEASE_CAPS = ["read-manifest", "verify-hashes", "read-envelope", "read-geometry", "read-textures",
                "read-audio", "read-skeleton", "read-animation", "materialize", "verify-signature",
                "summarize-points", "summarize-gsplat"]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def dump(obj):
    return (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def edit_loader_caps(obj):
    """core.loader capabilities: the release loaders declare `summarize-points` and
    `summarize-gsplat` (release spec/schemas/manifest.schema.json $defs/loaderMeta); the ArtCraft
    schemas predate them and refused the release loader nodes (found by W5a/W5b/W5c)."""
    items = obj["$defs"]["loaderMeta"]["properties"]["capabilities"]["items"]
    if items["enum"] == RELEASE_CAPS:
        return False
    assert all(c in RELEASE_CAPS for c in items["enum"]), items["enum"]
    items["enum"] = list(RELEASE_CAPS)
    return True


EDITS = [("spec/schemas/manifest.{name}.schema.json", "loader-capabilities", edit_loader_caps)]

# Text edits of files that are not specification (the package-root reading guide is a file of
# the readme node, copied from one PhotoCraft sample, and named the application that saved it).
TEXT_EDITS = [("raster-layers", "HOW-TO-READ.md", "writer-neutral",
               "The guide said the file was saved by PhotoCraft; a package written by another writer "
               "(the release builder) must not say so.",
               "It was saved by PhotoCraft,\nand it carries everything needed to read it without PhotoCraft.",
               "It was saved by a\nraster-layers/1 writer, and it carries everything needed to read it without that program.")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    a = ap.parse_args()
    root = os.path.join(a.repo, "profiles")
    rec_path = os.path.join(root, "ALIGNMENT.json")
    record = json.load(open(rec_path, encoding="utf-8")) if os.path.exists(rec_path) else {"edits": []}
    seen = {(e["file"], e["edit"]) for e in record["edits"]}
    for name in PROFILES:
        for pat, eid, fn in EDITS:
            rel = "%s/%s" % (name, pat.format(name=name))
            p = os.path.join(root, rel)
            before = open(p, "rb").read()
            obj = json.loads(before)
            if fn(obj):
                after = dump(obj)
                open(p, "wb").write(after)
                if (rel, eid) not in seen:
                    record["edits"].append({"file": rel, "edit": eid, "reason": " ".join(fn.__doc__.split()),
                                            "sha256_before": sha(before), "sha256_after": sha(after)})
                print("edited", rel, eid)
    for name, rel_file, eid, reason, old, new in TEXT_EDITS:
        rel = "%s/%s" % (name, rel_file)
        p = os.path.join(root, rel)
        before = open(p, "rb").read()
        text = before.decode("utf-8")
        if old in text:
            after = text.replace(old, new).encode("utf-8")
            open(p, "wb").write(after)
            if (rel, eid) not in seen:
                record["edits"].append({"file": rel, "edit": eid, "reason": reason,
                                        "sha256_before": sha(before), "sha256_after": sha(after)})
            print("edited", rel, eid)
    with open(rec_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(record, fh, indent=1, ensure_ascii=False)
        fh.write("\n")


if __name__ == "__main__":
    main()
