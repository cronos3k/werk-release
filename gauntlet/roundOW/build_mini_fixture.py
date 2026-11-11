#!/usr/bin/env python3
"""
build_mini_fixture.py -- the small-context gauntlet fixture.

Deterministic. Produces the small-context fixture from bytes that are
already inside two PINNED, COMMITTED fixtures; it invents no payload and it
touches neither of them.

Its output is `gauntlet/roundOW/mini-v1.werk`. Ruling on #11: the same 36
entries as the package the trials ran on, minus its three edges into dropped
nodes (see "WHAT IT DROPS"), so it verifies clean. Only MANIFEST.json and
SIGNATURE.json differ from that package's entries.

The trials ran on the earlier mini-v1.werk (sha256 f7bdcc85...e9837), built
by an earlier version of this script that kept the three edges. Those exact
bytes are kept at gauntlet/roundOW/historical/mini-v1-f7bdcc85.werk, so every
pinned trial stays checkable.

WHY IT EXISTS. The open-weights round's operative protocol inlines everything
the model may read. `fixtures/crate-v1.werk`'s package is 107 388 tokens
(measured, not estimated -- LM Studio's own `prompt_tokens` for the exact
message). That is a 6.8-minute cold prefill on one RTX 4090 and it locks the
round out of every model whose window is smaller. Gregor's instruction: make
the test work in **under 35 000 tokens of inline context**. So the *fixture*
shrinks, not the specification's role in it.

WHAT IT KEEPS, and why each one is load-bearing for the round-1 task sentence
("opens it, lists its contents with their meanings, verifies integrity, and
extracts the primary mesh and one sound to disk"):

  core.geom.game        geometry/game.glb          the primary mesh -- extraction target 1
  core.audio.effect     audio/sfx/crate-impact-    the primary sound -- extraction target 2,
                        hard-surface.{json,wav,     and a node whose payload family
                        raw.wav}                    (a take plus its raw take) is the
                                                    "meanings" part of the listing
  core.material         materials/wood.json        a node the mesh refers to
  core.phys.bounds      physics/bounds.json        a numeric node with conventions attached
  core.semantics        semantics/semantics.json   what the thing IS, in the file
  core.provenance       provenance/provenance.json the attribution chain, incl. consumed[]
  x.splat-foley.        x/.../seg_00.png           one PNG: an unknown-namespace node, so
    segments                                        law 12 (skip what you don't know,
                                                    report it) is still exercised
  core.pose.rest        poses/rest.wkrp            ONE binary envelope (WKRP, 560 B) --
                                                    kept because S-XV-5 says the manifest-only
                                                    path satisfies round 1 by itself; the
                                                    envelope is what forces the layout
                                                    grammar to be read
  core.spec, core.loader, core.license, core.readme -- the file stays a real werk
  package: it carries its whole spec/ tree (so `spec_sha256` remains valid and
  recomputable) and all three bundled loaders (so the 0/N-loaders metric and the
  graded-effort argument still mean something).

WHAT IT DROPS: 26 of the 28 audio nodes, the rendered evidence views, the props
node, and all but one segment crop.

That is NOT "nothing structural", as this docstring used to say. Dropping a
node leaves every edge into it pointing at nothing. The historical mini-v1
(f7bdcc85...) carries three such edges: `geom-game --enhances--> geom-source`,
`audio-crate-impact-hard-surface --enhances--> audio-package`, and
`evidence-segments --requires--> evidence-views`. The last one is the case
SPEC section 5 now rules on: a `requires` edge to an absent node kills the
source node (`requires-missing-node`, severity error), so every conformant
reader reports `evidence-segments` dead in that file and exits 1. SPEC
section 5 also says a writer MUST NOT emit such an edge. This script now
drops every edge whose target it did not keep, and says which ones it
dropped. The node `evidence-segments` is kept: it is the package's only
unknown-namespace node, which is what exercises law 12.

The manifest is rebuilt, `preview_prefix_bytes` is re-converged to its fixed
point, and the package is re-signed with the same publicly derived DEV key the
golden fixture uses, so the signature is `signed-and-valid` and every one of the
four signature states remains reachable.

Usage:  python build_mini_fixture.py [--out PATH]   (default: mini-v1.werk here)
"""

import argparse
import json
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "fixtures"))

import build_golden as BG                                    # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "tools"))
from payload_file import annotate_payload_files              # noqa: E402
from edge_targets import refuse_dangling_edges               # noqa: E402

SRC = os.path.join(ROOT, "fixtures", "crate-v1.werk")
ENV_SRC = os.path.join(ROOT, "tests", "fixtures", "crate.werk")

KEEP_NODES = [
    "geom-game",
    "material-wood",
    "bounds",
    "semantics",
    "provenance",
    "audio-crate-impact-hard-surface",
    "spec",
    "loader-python",
    "loader-rust",
    "loader-c",
    "license",
    "readme",
]
KEEP_SEGMENT = "x/splat-foley/segments/seg_00.png"

# The spec/ tree the small fixture carries. Trimmed to the documents that
# describe THIS package's own node types plus the two normative documents every
# package needs, because every extra spec file costs ~350 characters of
# MANIFEST.json and the manifest is inlined whole. `spec_sha256` is recomputed
# over exactly this set, so the field stays meaningful.
KEEP_SPEC = [
    "spec/README.md",
    "spec/SPEC.md",
    "spec/MINI-SPECS.md",
    "spec/conventions-map.json",
    "spec/facets.json",
    "spec/layouts/ENVELOPE.layout.txt",
    "spec/layouts/restposes.layout.txt",
    # S-OW-3: the worked hex example is part of the MINIMUM set for any package
    # carrying an envelope, not an optional extra. The grammar was in the round's
    # package and this file was not, and the strongest model in it responded by
    # printing fabricated floats labelled "demonstration".
    "spec/examples/restposes.example.hex.txt",
    "spec/examples/restposes.example.wkrp",
    "spec/schemas/manifest.schema.json",
    "spec/schemas/signature.schema.json",
    "spec/schemas/conventions-map.schema.json",
    "spec/schemas/core.material.schema.json",
    "spec/schemas/core.phys.bounds.schema.json",
    "spec/schemas/core.audio.effect.schema.json",
    "spec/schemas/core.semantics.schema.json",
    "spec/schemas/core.provenance.schema.json",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "mini-v1.werk"))
    args = ap.parse_args()

    zs = zipfile.ZipFile(SRC)
    man = json.loads(zs.read("MANIFEST.json"))
    ze = zipfile.ZipFile(ENV_SRC)
    eman = json.loads(ze.read("MANIFEST.json"))

    by_id = {n["node_id"]: n for n in man["nodes"]}
    nodes = [json.loads(json.dumps(by_id[k])) for k in KEEP_NODES]

    # the spec node keeps only the documents this package needs (see KEEP_SPEC)
    for n in nodes:
        if n["node_id"] == "spec":
            for v in n["versions"]:
                v["files"] = [f for f in v["files"] if f["path"] in KEEP_SPEC]
                if len(v["files"]) != len(KEEP_SPEC):
                    raise SystemExit("spec trim missed a file")

    # one segment crop only: same node, one file, so the node type survives
    seg = json.loads(json.dumps(by_id["evidence-segments"]))
    for v in seg["versions"]:
        v["files"] = [f for f in v["files"] if f["path"] == KEEP_SEGMENT]
    nodes.append(seg)

    # the envelope node, lifted verbatim from the minimal test fixture
    env_node = None
    for n in eman["nodes"]:
        if any(f["path"] == "poses/rest.wkrp" for v in n["versions"] for f in v["files"]):
            env_node = json.loads(json.dumps(n))
    if env_node is None:
        raise SystemExit("no .wkrp node found in %s" % ENV_SRC)
    nodes.append(env_node)

    # SPEC section 5: a writer that drops a node MUST also drop or rewrite
    # every edge into it. Drop each edge whose target was not kept, and say so.
    kept = {n["node_id"] for n in nodes}
    for n in nodes:
        for e in n["edges"]:
            if e["to"] not in kept:
                print("dropped edge %s --%s--> %s (target not kept)"
                      % (n["node_id"], e["kind"], e["to"]))
        n["edges"] = [e for e in n["edges"] if e["to"] in kept]

    # collect the bytes every kept file needs
    files = {}
    for n in nodes:
        for v in n["versions"]:
            for f in v["files"]:
                p = f["path"]
                src = ze if p.startswith("poses/") else zs
                files[p] = src.read(p)

    # sanity: declared hashes must match the bytes we copied
    for n in nodes:
        for v in n["versions"]:
            for f in v["files"]:
                got = BG.sha256(files[f["path"]])
                if got != f["sha256"]:
                    raise SystemExit("hash drift on %s" % f["path"])
                if len(files[f["path"]]) != f["size"]:
                    raise SystemExit("size drift on %s" % f["path"])

    # the layouts map must now name the envelope grammar this package carries
    layouts = dict(man.get("layouts") or {})
    layouts[env_node["type"]] = "spec/layouts/restposes.layout.txt"
    schemas = {k: v for k, v in man["schemas"].items() if v in KEEP_SPEC}

    summary = ("The small-context conformance fixture: the golden crate reduced "
               "to one mesh, one sound, one image, one binary envelope and the "
               "nodes that describe them, so that a package's whole manifest and "
               "the specification excerpts a reader needs fit inside a small "
               "model's context window. Built from fixtures/crate-v1.werk and "
               "tests/fixtures/crate.werk; no payload byte was invented.")

    def build(preview):
        m = {
            "werk": man["werk"],
            "profile": man["profile"],
            "entity": {"uuid": "6c1b90d4-2f5a-4a77-b3e0-9c8b1d54ae21",
                       "name": "Wooden crate (small-context fixture)",
                       "summary": summary,
                       "created": man["entity"]["created"]},
            "conventions": man["conventions"],
            "container": {"form": "zip", "zip_compression": "store",
                          "entry_order": man["container"]["entry_order"],
                          "preview_prefix_bytes": preview},
            "primary": {"mesh": "geom-game", "sound": "audio-crate-impact-hard-surface"},
            "license": {"spdx_id": man["license"]["spdx_id"], "file": "LICENSE",
                        "sha256": BG.sha256(files["LICENSE"])},
            "spec_sha256": BG.spec_sha256_of_files(files),
            "conventions_map": man["conventions_map"],
            "schemas": schemas,
            "layouts": layouts,
            "parts": man["parts"],
            "materials": man["materials"],
            "nodes": nodes,
        }
        return m

    # SPEC 2.1 (S-XV-4 / S-OW-2): declare each multi-file node's payload file.
    # The nodes are copies lifted from the source fixtures, so this re-derives
    # rather than inherits, and the round's measured failure -- an 8B model
    # taking files[0] and shipping the descriptor as the sound -- now has an
    # answer inside MANIFEST.json itself.
    annotate_payload_files(nodes)
    # SPEC 5: never write an edge to a node not in nodes[].
    refuse_dangling_edges(nodes)

    # converge preview_prefix_bytes exactly as build_golden.assemble does
    preview = 0
    for _ in range(8):
        mb = BG.jbytes(build(preview))
        sb = BG.jbytes(BG.sign(mb, "Signed with the same publicly derived DEV key as "
                                   "the golden fixture. Not a trust anchor."))
        allf = dict(files)
        allf["MANIFEST.json"] = mb
        allf["SIGNATURE.json"] = sb
        order = BG.order_entries(allf.keys())
        entries = [(p, allf[p]) for p in order]
        cursor = prefix = 0
        for name, data in entries:
            this = 30 + len(name.encode("utf-8")) + len(data)
            if BG.is_preview(name):
                prefix = cursor + this
            cursor += this
        if prefix == preview:
            break
        preview = prefix
    else:
        raise SystemExit("preview_prefix_bytes did not converge")

    blob = BG.write_zip(entries)
    with open(args.out, "wb") as fh:
        fh.write(blob)

    ndecl = sum(len(v["files"]) for n in nodes for v in n["versions"])
    print("wrote %s" % args.out)
    print("  %d bytes, sha256 %s" % (len(blob), BG.sha256(blob)))
    print("  %d entries, %d nodes, %d declared files" % (len(entries), len(nodes), ndecl))
    print("  manifest %d bytes, sha256 %s" % (len(mb), BG.sha256(mb)))
    print("  spec_sha256 %s" % json.loads(mb)["spec_sha256"])
    print("  preview_prefix_bytes %d (%.2f%%)" % (preview, 100.0 * preview / len(blob)))


if __name__ == "__main__":
    main()
