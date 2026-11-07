#!/usr/bin/env python3
"""build_selfrun_fixture.py -- the SELF-RUNNING MODEL fixture.

    python gauntlet/roundSR/build_selfrun_fixture.py [--src DIR] [--out PATH]

Builds `gauntlet/roundSR/selfrun-v1.werk`: a werk package that carries a
language model, the COMPLETE SOURCE of a runtime that executes it, layout
grammars for both of its binary payloads, and a deterministic test vector that
says what the model must produce.

WHY IT IS HERE AND NOT IN fixtures/
-----------------------------------
`fixtures/` is the pinned conformance corpus. Every package in it declares
`profile: "3d-entity/1"` or `"image/1"`, is recorded in `fixtures/fixtures.json`
and is rebuilt by every spec wave. This package declares
`profile: "model/1-draft"`, a profile that DOES NOT EXIST in `spec/` and has not
been ruled on, and it validates against a manifest schema that travels inside it
rather than one that lives in the repository. Putting a draft-profile package in
the conformance corpus would either break the corpus's rebuild or force a spec
change to accommodate an experiment. It is experiment-local, so it lives with
its experiment.

WHAT IT DOES NOT TOUCH
----------------------
`spec/` in the repository is NOT modified by this script. The package's `spec/`
tree is the repository's, byte for byte, PLUS four package-local files (two
layout grammars, the draft profile, the draft manifest schema). The package's
`spec_sha256` therefore differs from the pinned fixtures' and that is correct:
the field's question is which spec tree travelled inside THIS file.

THE CHAIN, WHICH IS THE POINT
-----------------------------
    stories15M.bin  +  tokenizer.bin
                    +  run.c / win.h / win.c   (the runtime, as SOURCE)
                    +  two layout grammars     (where every byte is)
                    +  testvectors/vectors.json (what it must produce)
    ------------------------------------------------------------------
    = a file that a stranger can turn back into running text.

Nothing in the package is executed by any werk tool, ever. SPEC.md 7.1 is
unchanged here: source is always allowed and reading it is the point; there is
no prebuilt artifact in this package at all.
"""

import argparse
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)

from pipeline.common import Ctx, jbytes, sha256, uuid_from, write_zip   # noqa: E402
from pipeline import package as PKG                                     # noqa: E402
from pipeline import p_tool                                             # noqa: E402
from tools.payload_file import annotate_payload_files                   # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "tools"))
from spec_sha256 import spec_sha256_of_files                            # noqa: E402

CREATED = "2026-08-09T00:00:00Z"
PROFILE = "model/1-draft"
BUILDER = "gauntlet/roundSR/build_selfrun_fixture.py"
BUILDER_VERSION = "1.0"

# Preview-first (law 9): everything a reader can READ comes before the 58 MB of
# weights. `model/` is last on purpose -- a consumer that has fetched the first
# ~1.5 MB of this file already holds the manifest, the whole specification, the
# layout grammars for the payloads it has not fetched yet, the entire runtime
# source and the test vectors.
ENTRY_ORDER = [
    "MANIFEST.json",
    "SIGNATURE.json",
    "LICENSE",
    "README.txt",
    "loaders/",
    "spec/",
    "testvectors/",
    "tools/",
    "recipe/",
    "disclosure/",
    "provenance/",
    "model/",
]
PREVIEW_SET = ENTRY_ORDER[:ENTRY_ORDER.index("tools/") + 1]

# Profile-agnostic conventions only. Profile 1's block is 3D-shaped
# (`up_axis`, `winding`, `quat_order`, `oct_encoding_pole`, `sh_l1_order`) and a
# language model has no up axis; declaring one in a schema-validated field would
# be a lie a validator would happily accept. `image/1` set the precedent for
# subtraction; this follows it. See spec/PROFILE-MODEL-DRAFT.md section 2.
CONVENTIONS = {
    "endianness": "le",
    "alignment_bytes": 16,
    "text_encoding": "utf-8",
    "id_case": "kebab-case",
    "hash_algorithm": "sha256",
    "signature_algorithm": "ed25519",
    "float_format": "ieee754-binary32",
}


def read(path):
    with open(path, "rb") as fh:
        return fh.read()


def text(path):
    return io.open(path, encoding="utf-8", newline="").read()


# ---------------------------------------------------------------------------
# the package-local draft manifest schema, DERIVED from the repository's
# ---------------------------------------------------------------------------

def draft_manifest_schema(base_bytes):
    """profile 1's manifest schema, with the four changes the draft profile
    argues for, and nothing else. Derived rather than hand-written so that the
    node/version/edge definitions cannot silently drift from the real one."""
    s = json.loads(base_bytes.decode("utf-8"))
    s["$id"] = ("https://werk.format/spec/schemas/"
                "manifest.model-draft.schema.json")
    s["title"] = "werk MANIFEST.json - profile model/1 (DRAFT, not normative)"
    s["description"] = (
        "DRAFT. Derived mechanically from manifest.schema.json by "
        "gauntlet/roundSR/build_selfrun_fixture.py in the werk repository, with "
        "exactly four changes, each argued in spec/PROFILE-MODEL-DRAFT.md: (1) "
        "`profile` is pinned to \"model/1-draft\"; (2) `parts` and `materials` "
        "leave the required list, as image/1 already does, because a language "
        "model has neither; (3) the conventions block keeps only the "
        "profile-agnostic constants and gains `float_format`, because up_axis, "
        "winding, quat_order, oct_encoding_pole and sh_l1_order are 3D facts "
        "and a package that declares them is lying in a validated field; (4) "
        "`primary` gains weights/tokenizer/runtime/testvectors, because the "
        "thing a model package is ABOUT is a four-part assembly and a consumer "
        "that resolves one part of it can do nothing. Everything else -- node, "
        "version, edge, epistemic, law 5's input_hash conditional -- is profile "
        "1's, unchanged, on purpose. NOT RULED ON. No conformance clause turns "
        "on this file. Original description follows. || "
        + s.get("description", ""))
    s["properties"]["profile"] = {
        "type": "string", "const": PROFILE,
        "description": "DRAFT profile id. A reader that has never heard of it "
                       "reports it as a note and carries on (SPEC.md 10.2).",
    }
    s["required"] = [k for k in s["required"] if k not in ("parts", "materials")]

    conv = s["properties"]["conventions"]
    keep = set(CONVENTIONS)
    conv["properties"] = {k: v for k, v in conv["properties"].items() if k in keep}
    conv["properties"]["float_format"] = {
        "type": "string", "const": "ieee754-binary32",
        "description": "The element format of the weights this package carries. "
                       "DRAFTING NOTE, stated in the schema so it cannot be "
                       "missed: this is probably wrong as a package-wide "
                       "constant and belongs per-node the moment quantised "
                       "weights are admitted. It is a const here so that the "
                       "first package has something to declare and the question "
                       "is visibly open.",
    }
    conv["required"] = [k for k in CONVENTIONS]

    s["properties"]["primary"] = {
        "type": "object", "additionalProperties": False,
        "description": "DRAFT, section 3 of PROFILE-MODEL-DRAFT.md. Four slots "
                       "rather than profile 1's one-per-kind, because getting "
                       "output out of a model needs the weights, the "
                       "vocabulary, a runtime and something to check against, "
                       "and three of four is nothing.",
        "properties": {
            "weights": {"type": "string", "pattern": "^[a-z0-9]+(-[a-z0-9]+)*$"},
            "tokenizer": {"type": "string", "pattern": "^[a-z0-9]+(-[a-z0-9]+)*$"},
            "runtime": {"type": "string", "pattern": "^[a-z0-9]+(-[a-z0-9]+)*$"},
            "testvectors": {"type": "string", "pattern": "^[a-z0-9]+(-[a-z0-9]+)*$"},
        },
    }
    return jbytes(s)


# ---------------------------------------------------------------------------
# manifest / assemble -- profile 1's, with this profile's constants
# ---------------------------------------------------------------------------

def build_manifest(ctx, files, preview_prefix, license_block, summary):
    m = {
        "werk": {"major": 1, "minor": 0},
        "profile": PROFILE,
        "manifest_schema": "spec/schemas/manifest.model-draft.schema.json",
        "spec_sha256": spec_sha256_of_files(files),
        "entity": {"uuid": ctx.entity_uuid, "name": ctx.name,
                   "summary": summary, "created": ctx.created},
        "conventions": dict(CONVENTIONS),
        "container": {"form": "zip", "zip_compression": "store",
                      "entry_order": list(ENTRY_ORDER),
                      "preview_prefix_bytes": preview_prefix},
        "license": license_block,
        "schemas": {k: v for k, v in ctx.schemas.items() if v},
        "layouts": dict(ctx.layouts),
        "primary": dict(ctx.primary),
        "nodes": list(ctx.nodes),
    }
    return m


def assemble(ctx, license_block, summary):
    annotate_payload_files(ctx.nodes)
    preview = 0
    for _round in range(8):
        manifest_bytes = jbytes(build_manifest(ctx, ctx.files, preview,
                                               license_block, summary))
        sig_bytes = jbytes(PKG.sign(manifest_bytes, ctx.created))
        allf = dict(ctx.files)
        allf["MANIFEST.json"] = manifest_bytes
        allf["SIGNATURE.json"] = sig_bytes
        entries = [(p, allf[p])
                   for p in PKG.order_entries(allf.keys(), ENTRY_ORDER)]
        cursor, prefix = 0, 0
        for name, data in entries:
            this = 30 + len(name.encode("utf-8")) + len(data)
            if PKG.is_preview(name, PREVIEW_SET):
                prefix = cursor + this
            cursor += this
        if prefix == preview:
            return manifest_bytes, sig_bytes, entries
        preview = prefix
    raise SystemExit("preview_prefix_bytes did not converge")


# ---------------------------------------------------------------------------

def build(src, out_path):
    def up(rel):
        return os.path.relpath(os.path.join(src, rel), ROOT).replace(os.sep, "/")

    def here(rel):
        return os.path.relpath(os.path.join(HERE, rel), ROOT).replace(os.sep, "/")

    # Two source trees, deliberately separate. `src` holds bytes fetched from
    # their publishers and carried unmodified (gauntlet/roundSR/SOURCES.md has
    # every URL and hash, and `data/` is gitignored precisely because those
    # bytes belong to their publishers and not to this repository). HERE holds
    # everything written FOR this package, which is committed.
    vectors = json.loads(text(os.path.join(HERE, "vectors.json")))
    ckpt = read(os.path.join(src, "stories15M.bin"))
    tokzr = read(os.path.join(src, "tokenizer.bin"))
    cfg = vectors["model"]["config"]

    ctx = Ctx(CREATED, uuid_from(ckpt + tokzr), "stories15M", record_timings=False)

    # ---- spec + loaders, the repository's tree byte for byte ------------
    PKG.embed_spec_and_loaders(ctx)

    # ---- four package-local spec files ----------------------------------
    extra_spec = []
    for repo_rel, pkg_path in [
        (None, "spec/layouts/llama2c-checkpoint.layout.txt"),
        (None, "spec/layouts/llama2c-tokenizer.layout.txt"),
        (None, "spec/PROFILE-MODEL-DRAFT.md"),
    ]:
        data = read(os.path.join(HERE, "pkgsrc", os.path.basename(pkg_path)))
        extra_spec.append(ctx.put(pkg_path, data))
    base_schema = read(os.path.join(ROOT, "spec", "schemas", "manifest.schema.json"))
    extra_spec.append(ctx.put("spec/schemas/manifest.model-draft.schema.json",
                              draft_manifest_schema(base_schema)))
    # They belong to the core.spec node: they ARE part of the specification
    # this package travels with, and a spec file outside the spec node would be
    # a file no node reaches (SPEC.md 2.1's every-file-reachable rule).
    spec_node = next(n for n in ctx.nodes if n["node_id"] == "spec")
    spec_node["versions"][0]["files"].extend(extra_spec)
    spec_node["versions"][0]["files"].sort(key=lambda f: f["path"])
    spec_node["versions"][0]["note"] = (
        "The format specification, its schemas and its binary layout grammars, "
        "travelling inside the file they describe (law 2). Four of these files "
        "are NOT in the werk repository's spec/ tree and are specific to this "
        "package: two layout grammars for the model's foreign binary formats, "
        "the DRAFT model profile, and the DRAFT manifest schema this package "
        "validates against. That is why this package's spec_sha256 does not "
        "match the conformance fixtures': the field says which spec tree "
        "travelled in THIS file, and this one is profile 1's plus four.")

    ctx.layouts["x.model.weights"] = "spec/layouts/llama2c-checkpoint.layout.txt"
    ctx.layouts["x.model.tokenizer"] = "spec/layouts/llama2c-tokenizer.layout.txt"

    # ---- licence ---------------------------------------------------------
    lic_bytes = read(os.path.join(HERE, "pkgsrc", "LICENSE"))
    lf = ctx.put("LICENSE", lic_bytes)
    ctx.node("license", "core.license",
             ctx.version([lf], "The full text of every licence that meets in "
                               "this package - the runtime's, the weights' and "
                               "what is known about the training corpus's - "
                               "embedded, never a link (law 7).", "authored",
                         tool=BUILDER, tver=BUILDER_VERSION))
    license_block = {"file": "LICENSE", "sha256": sha256(lic_bytes),
                     "spdx_id": "MIT"}

    # ---- the runtime, as SOURCE -----------------------------------------
    runtime_license = {
        "spdx_id": "MIT",
        "file": "tools/llama2c/LICENSE-llama2c.txt",
        "holder": "Andrej Karpathy",
        "note": "The MIT licence text as published in the llama2.c repository, "
                "carried verbatim. sha256 "
                "e87b912002f04cdfa837eaf7f70548ab79b9cb62a285495edf575f3da875aec4. "
                "It is the RUNTIME's licence and not the weights' - they happen "
                "to agree here, and core.tool.license exists because that is "
                "the thing people forget.",
    }
    p_tool.embed(
        ctx, "llama2c", "run.c (llama2.c)", "master@2026-08-09-fetch", "creator",
        "c",
        [(up("run.c"), "tools/llama2c/run.c"),
         (up("win.h"), "tools/llama2c/win.h"),
         (up("win.c"), "tools/llama2c/win.c"),
         (here("pkgsrc/BUILD-AND-RUN.md"), "tools/llama2c/BUILD-AND-RUN.md"),
         (up("LICENSE"), "tools/llama2c/LICENSE-llama2c.txt")],
        runtime_license,
        {"example": 'run model/stories15M.bin -z model/tokenizer.bin '
                    '-t 0.0 -n 64 -i "Once upon a time"',
         "argv": ["run", "model/stories15M.bin", "-z", "model/tokenizer.bin",
                  "-t", "0.0", "-n", "64", "-i", "Once upon a time"],
         "working_directory": ".",
         "toolchain": "any hosted C99 compiler; libm",
         "dependencies": [],
         "note": "BUILD FIRST. tools/llama2c/BUILD-AND-RUN.md carries the exact "
                 "compile line for each platform, which of them was measured on "
                 "which machine, and the one that is upstream's and was NOT "
                 "measured here. On Windows both run.c AND win.c must be "
                 "compiled: win.h only DECLARES mmap/munmap/clock_gettime and "
                 "win.c defines them, which is why a package carrying only "
                 "run.c and win.h looks complete and fails to link."},
        node_id="runtime",
        entrypoint="tools/llama2c/run.c",
        repository={"url": "https://github.com/karpathy/llama2.c",
                    "revision": "not-recorded",
                    "path_in_repository": "run.c"},
        produced=["testvectors"],
        note="The whole inference engine: ~970 lines of C99, zero dependencies "
             "beyond the standard library and libm, no build system, no "
             "network. It is carried as SOURCE and there is no prebuilt "
             "artifact anywhere in this package, so SPEC.md 7.1's inert-binary "
             "clause has nothing to bite on and the safety question does not "
             "arise: every executable byte a consumer ends up with, the "
             "consumer produced. `role` is `creator` rather than `viewer` "
             "because this program did produce something that IS in this "
             "package - the test vectors - and `viewer` is defined as having "
             "produced nothing here. Neither word is right for an EXECUTOR; "
             "see spec/PROFILE-MODEL-DRAFT.md section 5 item 4.",
        root=ROOT)

    p_tool.embed_config(
        ctx, "llama2c-testvector-run", "runtime",
        {"checkpoint": "model/stories15M.bin",
         "tokenizer": "model/tokenizer.bin",
         "temperature": 0.0,
         "topp": 0.9,
         "topp_note": "recorded because run.c parses it, and INERT at "
                      "temperature 0: sample() takes the argmax branch and "
                      "never consults the nucleus sampler or the RNG.",
         "rng_seed": "not set; irrelevant at temperature 0",
         "mode": "generate",
         "steps": [v["steps"] for v in vectors["vectors"]],
         "prompts": [v["prompt"] for v in vectors["vectors"]]},
        "recorded",
        # FINDING S-SR-4: core.tool.config.environment is INTERPRETER-SHAPED.
        # Its five permitted keys are platform / runtime_version /
        # library_versions / device / note, which are exactly the facts a Python
        # or JavaScript tool's re-run is sensitive to. For a tool that is
        # COMPILED, the facts a re-run is sensitive to are the compiler, its
        # version, its optimisation flags and the resulting binary -- and there
        # is nowhere to put any of them. Nothing is invented here: the compiler
        # goes in `runtime_version`, which is the closest true reading, and the
        # rest is prose in `note`. The structured copy that a machine could
        # compare is in testvectors/vectors.json, which is this package's own
        # payload and not a schema-validated werk field.
        environment={
            "platform": vectors["environment"]["platform"],
            "runtime_version": vectors["environment"]["compiler"],
            "device": vectors["environment"]["device"],
            "note": "COMPILED TOOL. Build command: %s. Resulting binary: %d "
                    "bytes. Machine: %s, %s. `runtime_version` carries the "
                    "COMPILER because this schema's environment block has no "
                    "key for one -- see spec/PROFILE-MODEL-DRAFT.md section 5. "
                    "The structured form of all of it is in "
                    "testvectors/vectors.json under `environment`."
                    % (vectors["environment"]["build_command"],
                       vectors["environment"]["binary_bytes"],
                       vectors["environment"]["os"],
                       vectors["environment"]["cpu"]),
        },
        determinism="deterministic",
        determinism_note=(
            "Temperature 0 selects the greedy argmax branch of sample() in "
            "run.c, so no random source is consulted at all and the run is a "
            "pure function of the weights, the tokenizer and the prompt. The "
            "scope of the byte-exact claim is ONE build on ONE machine, both "
            "named in `environment`: the forward pass is scalar C and a "
            "vectorising compiler may reassociate the reductions in rmsnorm, "
            "softmax and matmul. A greedy argmax over 32000 logits is usually "
            "robust to that and is not guaranteed to be, which is why "
            "testvectors/vectors.json says what a mismatch means instead of "
            "only what a match means."),
        unrecorded=["the exact libm build that evaluated expf, sqrtf and powf",
                    "the machine's microcode and whether FMA contraction was "
                    "applied by the compiler; /fp:precise is MSVC's default and "
                    "was not overridden, but it was not verified in the "
                    "disassembly either"],
        ran_at=CREATED,
        note="The one configuration this package makes a claim about. Any other "
             "temperature produces a legal run that no test vector covers.")

    # ---- the weights -----------------------------------------------------
    wf = ctx.put("model/stories15M.bin", ckpt)
    ctx.node("weights", "x.model.weights",
             ctx.version([wf],
                         "The model: %d transformer layers, dim %d, %d heads, "
                         "vocab %d, context %d, f32 throughout, %d bytes. "
                         "Carried BYTE-IDENTICAL to what its publisher released "
                         "- no conversion, no re-serialisation into a werk "
                         "envelope - because a payload that does not hash to "
                         "the upstream artifact cannot be checked against "
                         "upstream at all. Where every number lives: "
                         "spec/layouts/llama2c-checkpoint.layout.txt, whose "
                         "offsets were computed from this file's own header and "
                         "account for all %d bytes with nothing left over."
                         % (cfg["n_layers"], cfg["dim"], cfg["n_heads"],
                            cfg["vocab_size"], cfg["seq_len"], len(ckpt),
                            len(ckpt)),
                         "authored", tool=BUILDER, tver=BUILDER_VERSION),
             edges=[{"to": "runtime", "kind": "requires", "role": "executed-by"},
                    {"to": "tokenizer", "kind": "requires", "role": "vocabulary"},
                    {"to": "testvectors", "kind": "enhances", "role": "checked-by"},
                    {"to": "recipe", "kind": "enhances", "role": "recorded-by"}],
             meta={"architecture": "llama-2", "parameters_f32": cfg["parameters"],
                   "dtype": "f32", "quantised": False,
                   "shared_classifier_weights": True,
                   **{k: cfg[k] for k in ("dim", "hidden_dim", "n_layers",
                                          "n_heads", "n_kv_heads", "vocab_size",
                                          "seq_len", "head_size", "kv_dim")}})

    tf = ctx.put("model/tokenizer.bin", tokzr)
    ctx.node("tokenizer", "x.model.tokenizer",
             ctx.version([tf],
                         "The vocabulary: %d entries, a greedy-merge BPE, %d "
                         "bytes. THE FILE DOES NOT CONTAIN ITS OWN ENTRY COUNT "
                         "- run.c carries the author's note about that - so the "
                         "count is taken from the CHECKPOINT header and is "
                         "restated in this node's meta, which is werk stating a "
                         "cross-file dependency rather than leaving a reader to "
                         "find it. Layout: "
                         "spec/layouts/llama2c-tokenizer.layout.txt."
                         % (cfg["vocab_size"], len(tokzr)),
                         "authored", tool=BUILDER, tver=BUILDER_VERSION),
             edges=[{"to": "weights", "kind": "requires", "role": "vocabulary-of"}],
             meta={"kind": "sentencepiece-bpe-export",
                   "vocab_size": cfg["vocab_size"],
                   "vocab_size_source": "checkpoint header field 6 "
                                        "(model/stories15M.bin, offset 20)",
                   "max_token_length_declared": 27,
                   "max_token_length_measured": 27,
                   "bos_id": 1, "eos_id": 2, "unk_id": 0,
                   "byte_fallback_ids": [3, 258]})

    # ---- the correctness anchor -----------------------------------------
    tv_files = [ctx.put("testvectors/vectors.json",
                        read(os.path.join(HERE, "vectors.json")))]
    for v in vectors["vectors"]:
        tv_files.append(ctx.put("testvectors/" + v["stdout_file"],
                                read(os.path.join(HERE, v["stdout_file"]))))
    tv_files.append(ctx.put("testvectors/tokens_instrumentation.diff",
                            read(os.path.join(HERE, "tokens_instrumentation.diff"))))
    ctx.node("testvectors", "x.model.testvectors",
             ctx.version(tv_files,
                         "What this model MUST produce. Two temperature-0 runs, "
                         "each with its full argv, its exact stdout as bytes, "
                         "the sha256 of that stdout after CRLF->LF "
                         "normalisation, and its token-id sequence. Produced by "
                         "building the runtime in this package and running it, "
                         "on the machine named in the payload; the "
                         "instrumentation that captured the token ids travels "
                         "beside them as a diff against this package's own "
                         "run.c, so the capture is reproducible rather than "
                         "asserted. This node is the difference between 'the "
                         "model ran' and 'the model ran CORRECTLY': a runtime "
                         "reading the weights at the wrong offsets still emits "
                         "confident text.",
                         "measured",
                         inputs=["model/stories15M.bin", "model/tokenizer.bin",
                                 "tools/llama2c/run.c"],
                         params={"temperature": 0.0, "decode": "greedy-argmax",
                                 "compiler": vectors["environment"]["compiler"],
                                 "build_command": vectors["environment"]["build_command"]},
                         tool=BUILDER, tver=BUILDER_VERSION),
             edges=[{"to": "weights", "kind": "enhances", "role": "checks"},
                    {"to": "runtime", "kind": "requires", "role": "produced-by"}],
             meta={"vector_count": len(vectors["vectors"]),
                   "deterministic": True,
                   "normalisation": "crlf-to-lf-before-hashing"})

    # ---- the record ------------------------------------------------------
    inputs_readme = ctx.put("recipe/inputs/llama2c-README.md",
                            read(os.path.join(src, "README.md")))
    inputs_card = ctx.put("recipe/inputs/tinyllamas-model-card.md",
                          read(os.path.join(src, "tinyllamas-README.md")))
    recipe = {
        "recipe_version": 1,
        "target": {
            "node_id": "weights", "version": 1,
            "files": [{"path": "model/stories15M.bin", "sha256": sha256(ckpt),
                       "size": len(ckpt), "role": "weights"}],
        },
        "reproducibility": "descriptive",
        "reproducibility_note": (
            "DESCRIPTIVE, and the grade is the honest one rather than a "
            "modest one. This package did not train these weights and cannot "
            "reproduce them. What is recorded below is what the publisher "
            "published about the run, carried as his own words in "
            "recipe/inputs/, plus the architecture read out of the checkpoint's "
            "own header. Nothing here is a reproduction claim. Note that "
            "SPEC.md 3.11's hermeticity rule - every input medium a recipe "
            "names must be present in the package - CANNOT be satisfied by any "
            "real model package: the training corpus is orders of magnitude "
            "larger than the artifact, and 3.17's intermediate rule does not "
            "cover it because no embedded tool reproduces a corpus. The corpus "
            "is therefore named in `unrecorded` and in this note and is "
            "deliberately NOT in any step's `inputs[]`, where it would be a "
            "promise about another file. See "
            "spec/PROFILE-MODEL-DRAFT.md section 5 item 2."),
        "generated_at": CREATED,
        "pipeline": {"kind": "local"},
        "steps": [
            {
                "step_id": "train-tinystories-15m",
                "role": "other",
                # FINDING S-SR-5: `tool` here has no `note` and no way to say
                # NOT CARRIED. Its keys are name / version / source_file /
                # tool_node / config_node / repository_revision / host, and
                # `source_file` and `tool_node` both mean "it IS in this
                # package". A step whose tool is deliberately absent can only
                # say so by omitting two optional keys, which is indistinguish-
                # able from an author who forgot. The sentence goes in the
                # step's `note` instead.
                "tool": {"name": "karpathy/llama2.c train.py",
                         "version": "not-recorded",
                         "repository_revision": "not-recorded"},
                "params": {"architecture": "llama-2",
                           "dataset_name": "TinyStories",
                           "dataset_carried": False,
                           **{k: cfg[k] for k in ("dim", "hidden_dim",
                                                  "n_layers", "n_heads",
                                                  "n_kv_heads", "vocab_size",
                                                  "seq_len")}},
                "outputs": [{"path": "model/stories15M.bin",
                             "sha256": sha256(ckpt), "size": len(ckpt),
                             "role": "weights"}],
                "note": "THE TRAINING SCRIPT IS NOT CARRIED. It is named "
                        "because naming it is true; it is absent because "
                        "carrying it without the corpus would suggest a "
                        "reproducibility this recipe explicitly disclaims. That "
                        "sentence is here rather than in the `tool` block "
                        "because the tool block has no field for it. "
                        "The `role` is `other` because core.recipe's role enum "
                        "is a GENERATION vocabulary - plan, generate, edit, "
                        "inpaint, upscale, interpolate, transcode, select, "
                        "convert, ingest - written when the model was the TOOL. "
                        "Here the model is the TARGET and the step is a "
                        "training run. There is no `train` role. Recorded as a "
                        "finding rather than shoehorned into `generate`, which "
                        "would have been false.",
            },
            {
                "step_id": "publish-checkpoint",
                "role": "select",
                "tool": {"name": "huggingface.co/karpathy/tinyllamas",
                         "version": "not-recorded",
                         "repository_revision": "not-recorded"},
                "params": {"file": "stories15M.bin",
                           "retrieved": "2026-08-09",
                           "declared_sha256": sha256(ckpt),
                           "declared_size": len(ckpt)},
                "inputs": [{"path": "recipe/inputs/tinyllamas-model-card.md",
                            "sha256": inputs_card["sha256"],
                            "size": inputs_card["size"],
                            "role": "publisher-statement"}],
                "note": "The publisher's model card is carried verbatim because "
                        "it is the ONLY licence statement that exists for these "
                        "weights: two lines of YAML front matter saying "
                        "`license: mit`. A licence that is a publisher's "
                        "assertion and a licence that is a document are "
                        "different things, and the package carries the "
                        "assertion rather than paraphrasing it into a grant "
                        "nobody wrote (ruling 21).",
            },
        ],
        "unrecorded": [
            "the TinyStories corpus itself - not carried, see "
            "reproducibility_note; the dataset is published separately by its "
            "own authors under its own terms, which are NOT the weights' terms "
            "and are recorded in LICENSE as a fact rather than as a grant",
            "the training run's hyperparameters: optimiser, learning-rate "
            "schedule, batch size, token count, number of epochs and seed. None "
            "of them are in the checkpoint and none can be recovered from it",
            "the hardware the training ran on and what it cost",
            "which revision of llama2.c's train.py produced it, and therefore "
            "whether today's train.py would produce the same thing",
        ],
        "note": "A recipe for an artifact this package DID NOT MAKE. That is a "
                "legal and common case and the format has a grade for it; what "
                "the format does not yet have is a `train` role or a way to "
                "name a corpus without either carrying it or lying about it.",
    }
    rf = ctx.put("recipe/recipe.json", jbytes(recipe))
    ctx.node("recipe", "core.recipe",
             ctx.version([rf, inputs_readme, inputs_card],
                         "Where these weights came from, graded DESCRIPTIVE, "
                         "with the publisher's own two documents carried "
                         "verbatim beside it so the record is checkable against "
                         "its source rather than paraphrased.",
                         "authored", tool=BUILDER, tver=BUILDER_VERSION),
             edges=[{"to": "weights", "kind": "enhances", "role": "records"}])
    ctx.schemas["core.recipe"] = "spec/schemas/core.recipe.schema.json"

    # ---- the facts -------------------------------------------------------
    disclosure = {
        "disclosure_version": 1,
        "ai_generated": True,
        "ai_modified": False,
        "generation_scope": "partial",
        "scope_note": (
            "Two different facts share one boolean here and the package splits "
            "them rather than picking one. (a) THE WEIGHTS "
            "(model/stories15M.bin) are the output of a gradient-descent "
            "training run over the TinyStories corpus. No generative model "
            "produced them; they ARE a generative model. (b) THE TEXT in "
            "testvectors/ WAS produced by a generative model - this one, at "
            "temperature 0, from the prompts recorded beside it - and is "
            "synthetic content in the ordinary sense. (c) Everything else in "
            "this package - the specification, the layout grammars, the "
            "licence, the readme, the recipe and this disclosure - was written "
            "by a human-directed agent and is not model output in the sense "
            "this node is about. The single ai_generated axis is a fact about "
            "CONTENT and this artifact is a PRODUCER of content; see "
            "spec/PROFILE-MODEL-DRAFT.md section 5 item 3."),
        "declared_by": {"name": "the werk self-running-model experiment",
                        "kind": "agent"},
        "declared_at": CREATED,
        "recipe_node": "recipe",
        "models": [{
            "id": "stories15M (TinyStories, llama-2 architecture)",
            "role": "generate",
            "operator": "Andrej Karpathy (karpathy/tinyllamas)",
            "hosted": False,
            "version_note": "The model is IN THIS PACKAGE, at "
                            "model/stories15M.bin, sha256 in the manifest. That "
                            "is the unusual case: a disclosure normally names a "
                            "model that produced the content and lives "
                            "somewhere else, and `hosted: false` is as close as "
                            "this schema comes to saying 'and here it is'.",
        }],
        "training_data_statement": {
            "status": "partially-disclosed",
            "text": "The publisher's model card states, in full: 'This is a "
                    "Llama 2 architecture model series trained on the "
                    "TinyStories dataset, intended for use in the llama2.c "
                    "project.' The corpus is therefore NAMED and is not "
                    "otherwise described: no size, no filtering, no cut-off, no "
                    "sampling. TinyStories is itself a SYNTHETIC corpus - "
                    "short children's stories generated by larger language "
                    "models - so this model's training data is model output, "
                    "which is a fact about the artifact worth stating and is "
                    "not a judgement about it.",
            "source": "the publisher's Hugging Face model card, carried "
                      "verbatim in this package",
            "retrieved_at": CREATED,
            "embedded_path": "recipe/inputs/tinyllamas-model-card.md",
        },
        "human_authorship": {
            "claimed": True,
            "description": "Everything in this package EXCEPT the weights and "
                           "the text in testvectors/ was written by a "
                           "human-directed agent: the specification, the two "
                           "layout grammars, the draft profile, the build "
                           "instructions, the licence notice, the recipe and "
                           "this disclosure. The weights are a training run's "
                           "output and no human wrote them. The test-vector "
                           "text is this model's output and no human wrote it "
                           "either.",
        },
        "statements": [
            {"id": "artifact-is-a-generator",
             "text": "The single `ai_generated` axis is a fact about CONTENT, "
                     "and this artifact is a PRODUCER of content. Both readings "
                     "are true here and they are different claims: the weights "
                     "are the output of gradient descent (not of a generative "
                     "model), and they will generate synthetic content for "
                     "anyone who runs them. A model profile probably wants a "
                     "distinct 'this artifact GENERATES synthetic content' "
                     "statement beside 'this artifact IS synthetic content'. "
                     "Recorded here because `statements[]` is where the schema "
                     "says to put a declaration it has no key for, rather than "
                     "inventing one.",
             "epistemic": "authored"},
            {"id": "no-enforcement",
             "text": "There is no enforcement anywhere in this node and none is "
                     "wanted. The format ships facts; the viewer applies "
                     "jurisdiction (SPEC.md 3.12).",
             "epistemic": "authored"},
            {"id": "testvector-text-is-model-output",
             "text": "The 234 and 140 bytes of English in testvectors/ were "
                     "produced by model/stories15M.bin at temperature 0 from "
                     "the prompts 'Once upon a time' and 'The little robot'. "
                     "Measured, not asserted: the invocation, the machine and "
                     "the compiler are all recorded in "
                     "testvectors/vectors.json.",
             "epistemic": "measured",
             "basis": "testvectors/vectors.json, two runs of the runtime this "
                      "package carries"},
        ],
    }
    df = ctx.put("disclosure/disclosure.json", jbytes(disclosure))
    ctx.node("disclosure", "core.disclosure",
             ctx.version([df], "Machine-readable facts about what in this "
                               "package is model output and what is not.",
                         "authored", tool=BUILDER, tver=BUILDER_VERSION),
             edges=[{"to": "weights", "kind": "enhances", "role": "describes"}])
    ctx.schemas["core.disclosure"] = "spec/schemas/core.disclosure.schema.json"

    # ---- provenance ------------------------------------------------------
    prov = {
        "schema_version": 1,
        "runs": [{
            "run_id": "selfrun-fixture-build",
            "started": CREATED, "finished": CREATED,
            "tool": {"name": BUILDER, "version": BUILDER_VERSION},
            "produced": [{"node_id": "weights", "v": 1},
                         {"node_id": "tokenizer", "v": 1},
                         {"node_id": "runtime", "v": 1},
                         {"node_id": "testvectors", "v": 1}],
            # FINDING S-SR-6: consumed[] permits path / sha256 / external /
            # license and nothing else -- no size, and no note. So a package can
            # say WHAT it consumed and cannot say WHERE FROM, which for a
            # package whose entire value proposition is third-party provenance
            # is the field one wants most. The origins go in the run's `note`.
            "consumed": [
                {"path": "model/stories15M.bin", "sha256": sha256(ckpt),
                 "external": False, "license": "MIT (publisher's model card)"},
                {"path": "model/tokenizer.bin", "sha256": sha256(tokzr),
                 "external": False, "license": "MIT (llama2.c)"},
                {"path": "tools/llama2c/run.c",
                 "sha256": sha256(read(os.path.join(src, "run.c"))),
                 "external": False, "license": "MIT (llama2.c)"},
            ],
            "note": "ORIGINS, which consumed[] has no field for. "
                    "model/stories15M.bin: huggingface.co/karpathy/tinyllamas, "
                    "file stories15M.bin, retrieved 2026-08-09 over HTTPS, "
                    "60816028 bytes. model/tokenizer.bin and "
                    "tools/llama2c/{run.c,win.h,win.c,LICENSE-llama2c.txt}: "
                    "github.com/karpathy/llama2.c at master, retrieved "
                    "2026-08-09, 433869 / 38545 / 1612 / 6142 / 1063 bytes. "
                    "Every third-party byte is carried UNMODIFIED, so each "
                    "sha256 in the manifest can be compared against its "
                    "publisher's own distribution by anyone. The test vectors "
                    "were MEASURED by building tools/llama2c/run.c with the "
                    "compiler named in testvectors/vectors.json and running it "
                    "twice.",
        }],
    }
    pf = ctx.put("provenance/provenance.json", jbytes(prov))
    ctx.node("provenance", "core.provenance",
             ctx.version([pf], "Where every byte came from and what this build "
                               "did with it.", "authored",
                         tool=BUILDER, tver=BUILDER_VERSION))
    ctx.schemas["core.provenance"] = "spec/schemas/core.provenance.schema.json"

    # ---- readme ----------------------------------------------------------
    rmf = ctx.put("README.txt", read(os.path.join(HERE, "pkgsrc", "README.txt")))
    ctx.node("readme", "core.readme",
             ctx.version([rmf], "One page for whoever opened this file and "
                                "wants to know what it is and how to get text "
                                "out of it.", "authored",
                         tool=BUILDER, tver=BUILDER_VERSION))

    ctx.primary.update({"weights": "weights", "tokenizer": "tokenizer",
                        "runtime": "runtime", "testvectors": "testvectors"})

    summary = ("A 15 M-parameter language model, the complete C source of a "
               "runtime that executes it, layout grammars for both of its "
               "binary formats, and the deterministic output it must produce.")

    manifest_bytes, sig_bytes, entries = assemble(ctx, license_block, summary)
    blob = write_zip(entries)
    with open(out_path, "wb") as fh:
        fh.write(blob)
    return {"path": out_path, "bytes": len(blob), "sha256": sha256(blob),
            "entries": len(entries), "nodes": len(ctx.nodes),
            "files": sum(len(v["files"]) for n in ctx.nodes for v in n["versions"]),
            "manifest_bytes": len(manifest_bytes),
            "spec_sha256": json.loads(manifest_bytes)["spec_sha256"],
            "preview_prefix_bytes":
                json.loads(manifest_bytes)["container"]["preview_prefix_bytes"]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--src", default=os.path.join(ROOT, "data", "selfrun"))
    ap.add_argument("--out", default=os.path.join(HERE, "selfrun-v1.werk"))
    ap.add_argument("--json")
    args = ap.parse_args(argv)
    res = build(args.src, args.out)
    print(json.dumps(res, indent=2))
    if args.json:
        with io.open(args.json, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(res, fh, indent=2)
            fh.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
