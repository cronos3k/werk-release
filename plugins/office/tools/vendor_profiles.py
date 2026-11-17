#!/usr/bin/env python3
"""vendor_profiles.py -- copy the three Office profile definitions into this plug-in.

    py -3.12 tools/vendor_profiles.py [--samples <artcraft-samples>]
                                      [--formats <artcraft-formats>]
                                      [--libs <repo>/libs]

The profile definitions (rich-document/1, spreadsheet/1, presentation/1) are not in
the werk release spec; they travel inside the ArtCraft capsules that use them
(wordcraft, gridcraft, deckcraft samples). This script takes, from one sample
capsule per profile, every `spec/` file the release libs bundle does NOT carry
(the profile narrative, CRAFT-BASE.md, the profile's schemas, layouts,
conventions map and examples) plus HOW-TO-READ.md and the manifest facts a
writer must copy (conventions, schemas/layouts maps, container order), and from
the ArtCraft format library the definitions this plug-in names (zlib-deflate,
zip, opc, pdf) with their reference tools as core.tool nodes. Files the bundle
already carries (SPEC.md, MINI-SPECS.md, base schemas, loaders) are NOT copied:
the package carries the release's revision of those.

Output: profiles/<profile-name>/ and profiles/_formats/, plus profiles/VENDORED.json
(source of every file and its sha256). Read-only on every source.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))

SAMPLES = {
    "rich-document": "wordcraft/report.werk",
    "spreadsheet": "gridcraft/sales.werk",
    "presentation": "deckcraft/sample-deck.werk",
}
# format id -> a sample capsule that already carries its core.tool node (copied
# byte for byte), or None: built here from the format library's ref/ file.
FORMATS = {
    "zlib-deflate": "gridcraft/sales.werk",
    "zip": "wordcraft/maximal.werk",
    "pdf": "pdfcraft/signed-fixture.werk",
    "opc": None,
}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def superseded(path):
    name = path.rsplit("/", 1)[-1]
    return "@" in name and name.rsplit("@", 1)[1].split(".", 1)[0].isdigit()


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", required=True)
    ap.add_argument("--formats", required=True)
    ap.add_argument("--libs", default=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "libs"))
    a = ap.parse_args()
    bundle = json.load(open(os.path.join(a.libs, "bundle", "bundle.json"), encoding="utf-8"))
    in_bundle = {f["path"] for f in bundle["files"]}
    out = os.path.join(ROOT, "profiles")
    if os.path.isdir(out):
        shutil.rmtree(out)
    record = {"bundle_source_rev": bundle["source_rev"], "profiles": {}, "formats": {}}

    for prof, rel in SAMPLES.items():
        src = os.path.join(a.samples, rel)
        z = zipfile.ZipFile(src)
        m = json.loads(z.read("MANIFEST.json"))
        d = os.path.join(out, prof)
        files = {}
        for n in sorted(z.namelist()):
            if not n.startswith("spec/") or n in in_bundle or superseded(n):
                continue
            if n.startswith("spec/formats/") or n == "spec/NOT-CARRIED.md":
                continue   # formats come from the library; NOT-CARRIED describes THAT capsule's cut
            data = z.read(n)
            write(os.path.join(d, n), data)
            files[n] = sha(data)
        how = z.read("HOW-TO-READ.md")
        write(os.path.join(d, "HOW-TO-READ.md"), how)
        files["HOW-TO-READ.md"] = sha(how)
        facts = {
            "profile": m["profile"], "manifest_schema": m["manifest_schema"],
            "profile_spec": m.get("profile_spec"), "conventions_map": m["conventions_map"],
            "conventions": m["conventions"], "schemas": m["schemas"], "layouts": m.get("layouts", {}),
            "entry_order": m["container"]["entry_order"], "preview_tier": m["container"]["preview_tier"],
            "loader_meta": {n["node_id"]: n["meta"] for n in m["nodes"] if n["type"] == "core.loader"},
        }
        write(os.path.join(d, "profile.json"),
              (json.dumps(facts, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
        record["profiles"][prof] = {"source": rel, "source_sha256": sha(open(src, "rb").read()),
                                    "files": files}

    fd = os.path.join(out, "_formats")
    for fid, rel in FORMATS.items():
        defn = open(os.path.join(a.formats, fid + ".md"), "rb").read()
        write(os.path.join(fd, "spec", "formats", fid + ".md"), defn)
        head = json.loads(re.search(rb"```werk-format\n(.*?)\n```", defn, re.S).group(1))
        entry = {"definition_sha256": sha(defn), "requires": head.get("requires", []), "tools": []}
        for rt in head.get("reference_tools", []):
            tid, ep = rt["tool_id"], rt["entrypoint"]
            refname = ep.rsplit("/", 1)[-1]
            ref = open(os.path.join(a.formats, "ref", refname), "rb").read()
            if rel:
                z = zipfile.ZipFile(os.path.join(a.samples, rel))
                m = json.loads(z.read("MANIFEST.json"))
                node = [n for n in m["nodes"] if n["node_id"] == tid][0]
                ver = [v for v in node["versions"] if v["v"] == node["active"]][0]
                if "spec/formats/%s.md" % fid in z.namelist():
                    assert sha(z.read("spec/formats/%s.md" % fid)) == sha(defn), fid + ": definition differs"
                for f in ver["files"]:
                    data = z.read(f["path"])
                    write(os.path.join(fd, f["path"]), data)
                    if f.get("role") == "source":
                        assert sha(data) == sha(ref), "%s: sample's tool source differs from the library" % tid
                tool = {"node_id": tid, "files": ver["files"], "payload_file": ver.get("payload_file"),
                        "note": ver["note"], "meta": node.get("meta"), "from": rel}
            else:
                # built by the format library's packaging rule (formats/README.txt), in the
                # shape of the tool.json the ArtCraft writers emit (keys sorted, 2-space indent)
                src_path = "tools/%s/%s" % (tid, refname)
                tj = {
                    "config": {"definition": "spec/formats/%s.md" % fid, "format": fid,
                               "test_vectors": [v["id"] for v in head.get("test_vectors", [])]},
                    "entrypoint": src_path,
                    "files": [{"path": src_path, "role": "source", "sha256": sha(ref), "size": len(ref)}],
                    "form": "source",
                    "invocation": {"dependencies": [],
                                   "example": "python %s <package>   # writes the listing of section 8 to stdout" % src_path,
                                   "toolchain": "python>=3.8"},
                    "language": "python",
                    "license": {"spdx_id": "MIT OR Apache-2.0"},
                    "name": "%s reference decoder" % fid,
                    "role": "viewer",
                    "schema_version": 1,
                    "tool_id": tid,
                    "version": "1",
                }
                tjb = (json.dumps(tj, indent=2, sort_keys=True) + "\n").encode("utf-8")
                tj_path = "tools/%s/tool.json" % tid
                write(os.path.join(fd, tj_path), tjb)
                write(os.path.join(fd, src_path), ref)
                tool = {"node_id": tid, "payload_file": tj_path, "from": "formats/ref/" + refname,
                        "note": "Reference implementation (source) of a format this document's payloads "
                                "are encoded in, named by that format's definition.",
                        "meta": None,
                        "files": [{"path": tj_path, "sha256": sha(tjb), "size": len(tjb),
                                   "media_type": "application/json", "role": "payload"},
                                  {"path": src_path, "sha256": sha(ref), "size": len(ref),
                                   "media_type": "text/x-python", "role": "source"}]}
            entry["tools"].append(tool)
        record["formats"][fid] = entry
    write(os.path.join(out, "VENDORED.json"),
          (json.dumps(record, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print("vendored %d profiles, %d formats into %s" % (len(SAMPLES), len(FORMATS), out))


if __name__ == "__main__":
    main()
