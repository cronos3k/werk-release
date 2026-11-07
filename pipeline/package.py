#!/usr/bin/env python3
"""package.py — turn a Ctx full of nodes into a signed, conformant .werk.

Embeds the spec and the three bootstrap loaders (law 2: the file carries the
knowledge needed to read it), writes the LICENSE and the README, writes the
provenance node and the pipeline's own run report, then builds the manifest,
signs it and lays the zip out preview-first (law 9).
"""

import json
import os
import sys

from .common import ROOT, jbytes, kebab, sha256, write_zip, TOOL, TOOL_VERSION

sys.path.insert(0, os.path.join(ROOT, "store"))
from werkstore.signature import build_chain           # noqa: E402

# Ruling 5 / S-29: the manifest declares a spec_sha256 over the spec/ tree the
# package carries. tools/spec_sha256.py is the reference implementation and
# werkc.rs is the executable second opinion; this writer calls the reference
# rather than reimplementing an ordering convention for the third time.
sys.path.insert(0, os.path.join(ROOT, "tools"))
from spec_sha256 import spec_sha256_of_files          # noqa: E402
from payload_file import annotate_payload_files       # noqa: E402
from loader_caps import loader_capabilities        # noqa: E402

import hashlib                                        # noqa: E402

# The dev key, DERIVED AND PUBLISHED, exactly as fixtures/build_golden.py does
# it: sha256 of the sentence below. It proves the chain verifies and it proves
# nothing whatsoever about authorship. A pipeline that generated a random key
# per run would produce unverifiable packages; one that shipped a real key
# would be a leak.
DEV_KEY_PHRASE = b"werk dev key, publicly derived, pipeline only, 2026-08-08"
DEV_SK = hashlib.sha256(DEV_KEY_PHRASE).digest()

ENTRY_ORDER = [
    "MANIFEST.json",
    "SIGNATURE.json",
    "LICENSE",
    "README.txt",
    "loaders/",
    "spec/",
    "semantics/",
    "imposters/preview-sheet.png",
    "imposters/preview-albedo.png",
    "imposters/",
    "materials/",
    "physics/",
    "properties/",
    "provenance/",
    "textures/",
    "geometry/",
    "fields/",
    "x/",
]
PREVIEW_SET = ENTRY_ORDER[:ENTRY_ORDER.index("imposters/preview-albedo.png") + 1]

CONVENTIONS = {
    "endianness": "le", "units_per_meter": 1.0, "length_unit": "metre",
    "angle_unit": "radian", "time_unit": "second", "mass_unit": "kilogram",
    "up_axis": "y", "forward_axis": "-z", "right_axis": "+x",
    "handedness": "right", "winding": "ccw", "quat_order": "wxyz",
    "oct_encoding_pole": "y", "sh_l1_order": ["dc", "y", "z", "x"],
    "color_space_default": "srgb", "uv_origin": "top-left",
    "alignment_bytes": 16, "text_encoding": "utf-8", "id_case": "kebab-case",
    "hash_algorithm": "sha256", "signature_algorithm": "ed25519",
}

LICENSE_UNKNOWN = """werk enrichment pipeline output - licence notice

THE SOURCE ASSET'S TERMS ARE NOT KNOWN TO THIS PIPELINE.

This package was produced unattended from a GLB file handed to
pipeline/enrich.py. That file carried no licence text, and a pipeline that
invented one would be doing the single most dangerous thing a provenance
format can do: making a legal claim it cannot support. Law 7 says a licence
travels as embedded text and never as a link; it does not say a tool may
supply text nobody wrote.

So this file says what is actually true:

  * The GEOMETRY, TEXTURES and any other content that originated in the input
    GLB are covered by whatever terms that GLB came with. Those terms are not
    reproduced here because they were not supplied. Anyone redistributing this
    package MUST establish them and replace this file.

  * The DERIVED nodes this pipeline computed - the LOD chain, the imposter
    atlases, the colliders, the mass properties, the rest poses, the flow
    field, the descriptors - are dedicated to the public domain by the
    pipeline's authors under CC0 1.0 to the extent they are separable, which
    for a derived work of an unknown-licence input is a small extent and is
    stated as a limit rather than as a grant.

Pass --spdx and --license-file to pipeline/enrich.py to replace this notice
with the real terms. Until someone does, this package is INTERNAL and this
file is the reason.
"""


def embed_spec_and_loaders(ctx):
    spec_files = []
    for dirpath, _dirs, names in os.walk(os.path.join(ROOT, "spec")):
        for nm in sorted(names):
            if nm.endswith(".pyc"):
                continue
            full = os.path.join(dirpath, nm)
            rel = "spec/" + os.path.relpath(
                full, os.path.join(ROOT, "spec")).replace("\\", "/")
            with open(full, "rb") as fh:
                spec_files.append(ctx.put(rel, fh.read()))
    spec_files.sort(key=lambda f: f["path"])
    ctx.node("spec", "core.spec",
             ctx.version(spec_files,
                         "The format specification, its schemas and its binary "
                         "layout grammars, travelling inside the file they "
                         "describe (law 2).", "authored"))

    loaders = [
        ("loader-python", "werk_read.py", "python", "python>=3.8", None),
        ("loader-rust", "werk_read.rs", "rust", "rustc>=1.70 --edition 2021",
         "rustc -O --edition 2021 loaders/werk_read.rs -o werk_read"),
        ("loader-c", "werk_read.c", "c", "c99",
         "cc -std=c99 -O2 loaders/werk_read.c -o werk_read"),
    ]
    for node_id, fname, lang, toolchain, build in loaders:
        with open(os.path.join(ROOT, "loaders", fname), "rb") as fh:
            data = fh.read()
        f = ctx.put("loaders/" + fname, data)
        meta = {"language": lang, "form": "source",
                "entrypoint": "loaders/" + fname, "toolchain": toolchain,
                "dependencies": [],
                # What the loader does is stated by the loader, once, and read
                # from the bytes being embedded (tools/loader_caps.py).
                "capabilities": loader_capabilities(data)}
        if build:
            meta["build_command"] = build
        ctx.node(node_id, "core.loader",
                 ctx.version([f], "A single-file, dependency-free reader for "
                                  "this package, carried as payload so the file "
                                  "brings its own reader (law 1).", "authored"),
                 meta=meta)


def write_license(ctx, license_file=None, spdx=None):
    if license_file:
        with open(license_file, "rb") as fh:
            text = fh.read()
    else:
        text = LICENSE_UNKNOWN.encode("utf-8")
    f = ctx.put("LICENSE", text)
    ctx.node("license", "core.license",
             ctx.version([f], "The full licence text, embedded, never a link "
                              "(law 7).", "authored"))
    lic = {"file": "LICENSE", "sha256": sha256(text)}
    if spdx:
        lic["spdx_id"] = spdx
    return lic


def write_readme(ctx, summary_lines):
    text = (
        "%s\n%s\n\n"
        "This is a werk package: one file that carries an asset AND everything\n"
        "needed to understand it. spec/ is the format specification. loaders/\n"
        "carries three single-file, dependency-free readers - one Python, one\n"
        "Rust, one C. Start with spec/README.md, or just run\n"
        "loaders/werk_read.py against this file.\n\n"
        "It was produced UNATTENDED by pipeline/enrich.py from a bare GLB. No\n"
        "human authored any node below except the licence notice, the spec and\n"
        "the loaders. Every derived node therefore carries input_files, an\n"
        "input_hash over those inputs, and an epistemic stamp saying whether it\n"
        "is arithmetic on the mesh (measured) or a guess (inferred). Where a\n"
        "producer failed, its node is simply ABSENT and the failure is recorded\n"
        "in x/pipeline-report.json - that is the island rule, and a package\n"
        "with holes in it is a legal package.\n\n"
        "What the pipeline measured:\n%s\n"
        % (ctx.name, "=" * len(ctx.name),
           "\n".join("  " + s for s in summary_lines))
    ).encode("utf-8")
    f = ctx.put("README.txt", text)
    ctx.node("readme", "core.readme",
             ctx.version([f], "One page for a human who opened this file and "
                              "wants to know what it is.", "authored"))


def write_provenance(ctx, started, finished, host_info, extra_runs=()):
    runs = []
    for r in ctx.reports:
        if r.status != "ok" or not r.nodes:
            continue
        run = {
            "run_id": kebab("stage-" + r.stage),
            "started": started,
            "finished": finished,
            "tool": {"name": TOOL, "version": TOOL_VERSION, **host_info},
            "produced": [{"node_id": n, "v": 1} for n in r.nodes],
        }
        if ctx.record_timings:
            run["cost"] = {"wall_seconds": round(r.seconds, 4)}
        if r.detail:
            run["note"] = r.detail
        runs.append(run)
    runs.extend(extra_runs)
    if not runs:
        runs = [{"run_id": "stage-none", "started": started, "finished": finished,
                 "tool": {"name": TOOL, "version": TOOL_VERSION, **host_info},
                 "produced": [{"node_id": "geom-source", "v": 1}],
                 "note": "every derived producer failed; see x/pipeline-report.json"}]
    doc = {"schema_version": 1, "runs": runs}
    f = ctx.put("provenance/provenance.json", jbytes(doc))
    ctx.node("provenance", "core.provenance",
             ctx.version([f], "One entry per producer that succeeded, with what "
                              "it made and what it cost in wall seconds.",
                         "authored"))
    ctx.schemas["core.provenance"] = "spec/schemas/core.provenance.schema.json"


def write_report(ctx, argv, host_info):
    doc = {
        "tool": TOOL, "version": TOOL_VERSION, "argv": list(argv),
        "host": host_info,
        "stages": [r.as_json() for r in ctx.reports],
        "notes": list(ctx.notes),
        "summary": {
            "ok": sum(1 for r in ctx.reports if r.status == "ok"),
            "failed": sum(1 for r in ctx.reports if r.status == "failed"),
            "skipped": sum(1 for r in ctx.reports if r.status == "skipped"),
        },
        "island_rule": "A failed producer yields a MISSING NODE and this report "
                       "entry, never a dead pipeline and never a fabricated "
                       "node. Absence here is the format working as designed.",
    }
    f = ctx.put("x/pipeline-report.json", jbytes(doc))
    ctx.node("pipeline-report", "x.werk-pipeline.report",
             ctx.version([f], "The pipeline's own run log: every producer, its "
                              "wall time, and the exact error where one failed. "
                              "An x.* node, so a reader that has never heard of "
                              "it skips it and loses nothing (law 12).",
                         "authored"),
             meta={"stage_count": len(ctx.reports)})
    return doc


# ---------------------------------------------------------------------------
# manifest, signature, container
# ---------------------------------------------------------------------------

def order_entries(paths, order=None):
    remaining = sorted(paths)
    out = []
    for pat in (order or ENTRY_ORDER):
        picked = [p for p in remaining
                  if (p.startswith(pat) if pat.endswith("/") else p == pat)]
        for p in picked:
            remaining.remove(p)
            out.append(p)
    return out + remaining


def is_preview(name, preview=None):
    return any(name.startswith(p) if p.endswith("/") else name == p
               for p in (preview or PREVIEW_SET))


def entry_order_of(ctx):
    """A builder MAY declare its own container entry order by setting
    `ctx.entry_order` (and `ctx.preview_set`). S-14 ruled the order a SHOULD
    and never a correctness property, so this is purely about which bytes land
    in the browsable prefix — and a package whose payload directories this
    module has never heard of (Stage 12's `splats/`, `points/`, `tools/`)
    should be able to say where they go without editing the enrichment
    pipeline's constant."""
    return list(getattr(ctx, "entry_order", None) or ENTRY_ORDER)


def preview_set_of(ctx):
    return list(getattr(ctx, "preview_set", None) or PREVIEW_SET)


def build_manifest(ctx, files, preview_prefix, license_block, summary):
    schemas = {k: v for k, v in ctx.schemas.items() if v}
    m = {
        "werk": {"major": 1, "minor": 0},
        "profile": "3d-entity/1",
        "manifest_schema": "spec/schemas/manifest.schema.json",
        # Over the spec/ files in THIS package, not the repo's spec/ tree: the
        # question the field answers is which schemas travelled inside the file.
        "spec_sha256": spec_sha256_of_files(files),
        "entity": {"uuid": ctx.entity_uuid, "name": ctx.name,
                   "summary": summary, "created": ctx.created},
        "conventions": dict(CONVENTIONS),
        "container": {"form": "zip", "zip_compression": "store",
                      "entry_order": entry_order_of(ctx),
                      "preview_prefix_bytes": preview_prefix},
        "license": license_block,
        "schemas": schemas,
        "layouts": dict(ctx.layouts),
        "parts": list(ctx.parts),
        "materials": list(ctx.materials),
        "nodes": list(ctx.nodes),
    }
    # `conventions_map` is optional (SPEC section 10.2) and declared beats
    # derived: a builder that carries spec/conventions-map.json says so here
    # rather than leaving a reader to guess the filename.
    # An EMPTY `primary` is worse than an absent one: it looks declared and
    # declares nothing, and SPEC section 2's fallback rule exists precisely for
    # the absent case. A package with nothing to declare omits the key rather
    # than shipping `{}`. (Stage 12's splat package once had no slot to fill —
    # finding S12-7 — until ruling 22 added the type-agnostic
    # `primary.geometry`; it now declares {"geometry": "gsplat"}.)
    if ctx.primary:
        m["primary"] = dict(ctx.primary)
    if getattr(ctx, "conventions_map", None):
        m["conventions_map"] = ctx.conventions_map
    # `formats` (SPEC.md section 3.18) is absent when no node names a format,
    # for the reason `primary` is: an empty map looks declared and declares
    # nothing.
    if getattr(ctx, "formats", None):
        m["formats"] = dict(ctx.formats)
    return m


def sign(manifest_bytes, created):
    return build_chain(sha256(manifest_bytes), [{
        "secret": DEV_SK,
        "name": "werk dev key (publicly derived, pipeline only)",
        "uri": "urn:werk:dev-key:pipeline-enrich",
        "kind": "service",
        "role": "author",
        "signed_at": created,
        "note": "Signed with a DEV key derived from a published sentence. It is "
                "not secret, it is not a trust anchor, and it proves only that "
                "the chain verifies.",
    }])


def assemble(ctx, license_block, summary):
    # SPEC 2.1 (S-XV-4 / S-OW-2): declare which file IS each multi-file node's
    # payload, so a consumer following primary.* never has to take files[0].
    annotate_payload_files(ctx.nodes)
    preview = 0
    for _round in range(8):
        manifest_bytes = jbytes(build_manifest(ctx, ctx.files, preview,
                                               license_block, summary))
        sig_bytes = jbytes(sign(manifest_bytes, ctx.created))
        allf = dict(ctx.files)
        allf["MANIFEST.json"] = manifest_bytes
        allf["SIGNATURE.json"] = sig_bytes
        order = order_entries(allf.keys(), entry_order_of(ctx))
        entries = [(p, allf[p]) for p in order]
        cursor, prefix = 0, 0
        preview_set = preview_set_of(ctx)
        for name, data in entries:
            this = 30 + len(name.encode("utf-8")) + len(data)
            if is_preview(name, preview_set):
                prefix = cursor + this
            cursor += this
        if prefix == preview:
            return manifest_bytes, sig_bytes, entries
        preview = prefix
    raise SystemExit("preview_prefix_bytes did not converge")


def finish(ctx, out_path, license_block, summary):
    manifest_bytes, sig_bytes, entries = assemble(ctx, license_block, summary)
    blob = write_zip(entries)
    with open(out_path, "wb") as fh:
        fh.write(blob)
    return {"bytes": len(blob), "sha256": sha256(blob), "entries": len(entries),
            "nodes": len(ctx.nodes),
            "files": sum(len(v["files"]) for n in ctx.nodes for v in n["versions"]),
            "manifest_bytes": len(manifest_bytes),
            "preview_prefix_bytes": json.loads(manifest_bytes)["container"]
                                              ["preview_prefix_bytes"]}
