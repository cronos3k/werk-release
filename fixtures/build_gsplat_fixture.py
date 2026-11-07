#!/usr/bin/env python3
"""build_gsplat_fixture.py -- Stage 12 conformance fixture: a real Gaussian
splat, its point-cloud degradation, and the CODE that made both.

    python fixtures/build_gsplat_fixture.py [--out DIR] [--source PATH]
                                            [--scratch DIR] [--json OUT.json]

Builds `fixtures/gsplat-v1.werk`, profile `3d-entity/1`. It is the first werk
package to carry a `core.geom.gsplat` (`WKGS`), a `core.geom.points` (`WKPC`),
a `core.tool` or a `core.tool.config`, so four node types and two envelope
magics stop being published-but-unexecuted in the same package.

THE SOURCE, AND WHY THIS ONE.

`plush.splat` -- 281 498 Gaussians, 9 007 936 bytes, a REAL PHOTOGRAMMETRIC
CAPTURE of a physical object, published as demo data at
antimatter15.com/splat-data and vendored in the sibling project <WERK_LAB>/splat-foley
as `data/samples/plush.splat` with its provenance recorded in that project's
`data/samples/README.md`.

Three requirements had to hold at once, exactly as Stage 6's fixture argued
for its mocap take:

  * the splat must be REAL, not authored for the test. A synthetic Gaussian
    field would exercise the layout and prove nothing about the ingest, which
    is where every splat bug lives;
  * it must be small-to-medium. The other real splat available to the lab is
    a 1 920 000-Gaussian generated world, 107 520 363 bytes, which is a
    perfectly good splat and a 110 MB fixture. It is used by the Stage 12 gate
    as an INGEST test -- the real INRIA PLY path, measured on real trainer
    output -- and is deliberately not shipped;
  * the terms must be stateable. They are stated, and what is NOT known about
    them is stated too: see the LICENSE this script writes, which is the
    format's licence-unknown doctrine applied honestly rather than a guess
    dressed as a grant.

THE CHAIN, WHICH IS THE POINT OF THE FIXTURE.

    plush.splat  --[ pipeline/splat_to_ply.py ]-->  plush.ply
                 --[ pipeline/p_gsplat.py     ]-->  splats/plush.wkgs
                 --[ pipeline/p_pointcloud.py ]-->  points/plush-dc.wkpc

All three tools are embedded in the package as `core.tool` nodes, with their
configurations as `core.tool.config` nodes, and the `core.recipe` names them by
NODE ID rather than by hash. The input, `plush.splat`, is embedded too, so the
whole chain is hermetic. The INTERMEDIATE `plush.ply` is NOT embedded, and that
is a rule rather than an omission: SPEC.md section 3.17 says an intermediate an
embedded tool reproduces from an embedded input need not be carried provided
the recipe records its sha256, its size and the exact invocation -- which makes
it MORE verifiable than a copy, because the gate runs the regeneration and
compares. `tests/run_gate_12.py` does exactly that.

WHAT IT DELIBERATELY DOES NOT EXERCISE: `sh_degree` above 0. Neither splat
available to the lab stores anything beyond the DC band, so `sh-rest` is a
present-and-empty section here and the degree-1..3 index arithmetic is
exercised by a synthetic PLY in the gate instead. Recorded as S12-6 rather than
papered over with an invented coefficient set.

DEPENDENCIES: numpy. Nothing third-party travels inside the package as
executable code; law 1's ban is about what ships in the file.
"""

import argparse
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np                                       # noqa: E402

from pipeline.common import Ctx, jbytes, sha256, uuid_from, linear_to_srgb_f  # noqa: E402
from pipeline import package as PKG                      # noqa: E402
from pipeline import p_gsplat, p_pointcloud, p_tool      # noqa: E402
from pipeline.ply import dc_to_linear_rgb, SH_C0         # noqa: E402
from pipeline.splat_to_ply import convert as splat_convert  # noqa: E402

DEFAULT_SOURCE = os.path.join(os.environ.get("WERK_LAB", "<WERK_LAB unset>"), "splat-foley", "data", "samples",
                              "plush.splat")
CREATED = "2026-08-08T00:00:00Z"

ENTRY_ORDER = [
    "MANIFEST.json",
    "SIGNATURE.json",
    "LICENSE",
    "README.txt",
    "loaders/",
    "spec/",
    "semantics/",
    "tools/",
    "recipe/recipe.json",
    "provenance/",
    "points/",
    "splats/",
    "recipe/",
    "x/",
]
#: The browsable prefix stops before the payloads. `tools/` is INSIDE it on
#: purpose: a consumer doing a ranged read of the first few hundred kilobytes
#: gets the manifest, a reader, the spec, the semantics AND the source of every
#: tool that made the file -- which is the whole Stage 12 claim, expressed as a
#: byte layout rather than as a sentence. (S-14 makes the order a SHOULD, so
#: nothing here is load-bearing for correctness.)
PREVIEW_SET = ENTRY_ORDER[:ENTRY_ORDER.index("recipe/recipe.json") + 1]

POLYFORM_NOTE = (
    "PolyForm Noncommercial License 1.0.0 -- the terms the werk reference "
    "implementation is published under. Full text: this package carries it as "
    "part of the LICENSE file below, because law 7 says a licence travels as "
    "text and never as a link.")


def license_text(source_name, source_sha, source_bytes):
    return ("""werk conformance fixture gsplat-v1 -- licence notice

THIS PACKAGE CONTAINS THREE KINDS OF CONTENT UNDER THREE DIFFERENT TERMS, AND
THE HONEST ANSWER FOR ONE OF THEM IS "NOT ESTABLISHED".

1. THE FORMAT SPECIFICATION (spec/) is open. It is published so that anyone
   may implement werk, and this package carries it because law 2 says the
   format travels with the file.

2. THE READERS AND TOOLS (loaders/, tools/) are the werk reference
   implementation, (c) Gregor Hubert Max Koch and Ken Gamble, 2026, published
   under the PolyForm Noncommercial License 1.0.0. You may read them, study
   them, run them and modify them for any noncommercial purpose; commercial
   licensing is available from the authors. They are embedded here as SOURCE
   because a package that carries the code that made it can be CHECKED instead
   of believed -- and because nothing in a werk package is ever executed
   automatically (spec/SPEC.md section 7.1).

3. THE GAUSSIAN SPLAT (recipe/inputs/%s, and therefore splats/ and points/,
   which are re-encodings of it) IS THIRD-PARTY CONTENT WHOSE TERMS THIS
   PACKAGE CANNOT STATE.

   What IS known, and is recorded rather than smoothed over:

     * the file is %s, %d bytes, sha256
       %s;
     * it was obtained from the openly published demo-data set at
       antimatter15.com/splat-data, a set of WebGL splat-viewer sample files
       converted from published 3D-Gaussian-Splatting captures;
     * the capture itself is a photograph-derived reconstruction of a physical
       object, and the reconstruction's author is not named by that
       distribution;
     * the sibling project this file was taken from records the set as
       "research/test use" and says, in its own words, to check before any
       redistribution.

   So: NO LICENCE IS GRANTED HERE FOR THE SPLAT CONTENT. This package exists
   as a CONFORMANCE FIXTURE -- a real payload for testing readers against --
   and anyone redistributing it beyond that purpose MUST establish the
   capture's terms first and replace this notice.

   A format whose entire argument is that provenance should be visible must
   not invent a licence for content it did not author. Law 7 says a licence
   travels as embedded text and never as a link; it does not say a tool may
   supply text nobody wrote. This section is what the doctrine looks like when
   the answer is "unknown" instead of "CC BY".

DERIVED NODES. The WKGS payload, the WKPC preview, the semantics and the
recipe are arithmetic performed on content covered by (3) and are dedicated to
the public domain by this package's authors under CC0 1.0 to the extent they
are separable -- which, for a re-encoding of a third-party capture, is a small
extent, and is stated as a limit rather than as a grant.
""" % (source_name, source_name, source_bytes, source_sha)).encode("utf-8")


def readme_text(stats, pc_stats, source_name):
    return ("""plush -- a 3D Gaussian splat, its point cloud, and the code that made both
=========================================================================

This is a werk package: one file carrying an asset AND everything needed to
understand it. spec/ is the format specification. loaders/ carries three
single-file, dependency-free readers -- Python, Rust, C. Start with
spec/README.md, or just run

    python loaders/werk_read.py gsplat-v1.werk --verify

WHAT IS IN IT

  splats/plush.wkgs     %d Gaussians, magic WKGS, SH degree %d.
                        Six declared streams: means, scales, rotations,
                        opacities, sh-dc, sh-rest. Grammar:
                        spec/layouts/gsplat.layout.txt.

  points/plush-dc.wkpc  the same %d points as a plain point cloud, magic
                        WKPC: position + colour, nothing else. It is the
                        splat's DC band through the line above and it is
                        EXACT -- nothing was resampled or decimated. Grammar: spec/layouts/points.layout.txt.

  The colour line in full, because a constant a reader has to get from
  somewhere else is a promise about another file:

      C0         = 0.28209479177387814          ( = 1 / (2*sqrt(pi)) )
      rgb_linear = clamp(0.5 + C0 * sh_dc, 0, 1)

IF YOU ONLY WANT POSITIONS AND COLOURS you do not need to understand Gaussian
splatting at all. Read the WKGS header's section table, take the "means"
section and the "sh-dc" section, skip the other four, and apply that one line.
That path is NORMATIVE (spec/layouts/gsplat.layout.txt section 7): a reader
that does it is a conformant consumer of the node, not a degraded one. Or read
points/plush-dc.wkpc, which is the same answer already computed.

THE PART THAT IS NEW IN THIS PACKAGE

  tools/                the SOURCE CODE of the three tools that made this
                        file, embedded as core.tool nodes with their
                        configurations as core.tool.config nodes.
  recipe/recipe.json    the conversion, step by step, naming those tools BY
                        NODE ID rather than by a hash you would have to
                        resolve somewhere else.
  recipe/inputs/%s
                        the original file the chain started from, so the
                        whole thing is reproducible from inside the package.

The intermediate PLY is deliberately NOT here: the recipe records its sha256
and the exact command that regenerates it from the input above using the tool
above. See spec/SPEC.md section 3.17.

NOTHING IN THIS PACKAGE IS EVER EXECUTED AUTOMATICALLY. The tools are text.
Read them. That is what they are for.
""" % (stats["count"], stats["sh_degree"], pc_stats["count"], source_name)).encode("utf-8")


def hexcolor(lin):
    return "#" + "".join("%02x" % int(round(linear_to_srgb_f(float(c)) * 255.0))
                         for c in lin)


def palette_from_dc(rgb_lin, bins=4, top=8):
    """A measured palette: a 4x4x4 histogram of the DC-band linear colours,
    the top `top` bins by population, each swatch the MEAN linear colour of the
    points that fell in it. Deliberately the same shape of computation
    embedding.layout.txt section 4 step 9 defines, so the two spellings of "the
    dominant colours" in this format agree about what the words mean."""
    idx = np.clip((rgb_lin * bins).astype(np.int64), 0, bins - 1)
    key = (idx[:, 0] * bins + idx[:, 1]) * bins + idx[:, 2]
    counts = np.bincount(key, minlength=bins ** 3)
    order = np.argsort(-counts, kind="stable")[:top]
    out = []
    n = len(rgb_lin)
    for b in order:
        if counts[b] == 0:
            continue
        mean = rgb_lin[key == b].mean(axis=0)
        out.append({"hex_srgb": hexcolor(mean),
                    "linear_rgb": [round(float(v), 6) for v in mean],
                    "weight": round(float(counts[b]) / n, 6)})
    return out


def build(source_path, scratch_dir, out_path):
    t0 = time.perf_counter()
    os.makedirs(scratch_dir, exist_ok=True)
    source_name = os.path.basename(source_path)
    with open(source_path, "rb") as fh:
        source_bytes = fh.read()
    source_sha = sha256(source_bytes)

    # ---- step 1: .splat -> INRIA PLY, by the tool this package will carry
    ply_path = os.path.join(scratch_dir, os.path.splitext(source_name)[0] + ".ply")
    conv = splat_convert(source_path, ply_path)

    # ---- step 2: PLY -> WKGS
    blob_gs, stats, arrays = p_gsplat.ingest(ply_path, quat_order="wxyz")
    means, scales, rot, opac, sh = arrays

    # ---- step 3: WKGS -> WKPC (the normative DC-band degradation)
    blob_pc, pc_stats = p_pointcloud.from_gsplat(
        means, sh[:, 0, :],
        {"note": "derived from splats/plush.wkgs, sections `means` and `sh-dc`, "
                 "by spec/layouts/gsplat.layout.txt section 7. Exact: nothing "
                 "resampled, nothing decimated."})

    ctx = Ctx(CREATED, uuid_from(source_bytes), "plush", record_timings=False)
    ctx.entry_order = ENTRY_ORDER
    ctx.preview_set = PREVIEW_SET
    ctx.conventions_map = "spec/conventions-map.json"
    ctx.parts = [{"part_id": "whole", "name": "plush", "parent": None,
                  "transform": {"translation": [0.0, 0.0, 0.0],
                                "rotation": [1.0, 0.0, 0.0, 0.0],
                                "scale": [1.0, 1.0, 1.0]}}]

    PKG.embed_spec_and_loaders(ctx)

    lic_bytes = license_text(source_name, source_sha, len(source_bytes))
    lf = ctx.put("LICENSE", lic_bytes)
    ctx.node("license", "core.license",
             ctx.version([lf], "The full licence text, embedded, never a link "
                               "(law 7) -- including the part where the splat's "
                               "own terms are NOT established and the package "
                               "says so instead of guessing.", "authored"))
    license_block = {"file": "LICENSE", "sha256": sha256(lic_bytes)}

    # ---- the tools, as code -------------------------------------------
    tool_license = {
        "spdx_id": "PolyForm-Noncommercial-1.0.0",
        "file": "LICENSE",
        "holder": "Gregor Hubert Max Koch and Ken Gamble",
        "note": POLYFORM_NOTE,
    }
    env = {
        "platform": sys.platform,
        "runtime_version": "CPython %d.%d.%d" % sys.version_info[:3],
        "library_versions": {"numpy": np.__version__},
        "device": "cpu",
        "note": "The arithmetic is numpy float64 throughout with a float32 "
                "store; exp, log and the logistic function are the only "
                "libm calls, and they are the reason this run is reproducible "
                "to the bit on this machine and to ~1 ulp across machines.",
    }

    # Each tool node carries a COMPLETE copy of what it needs, including its own
    # copy of ply.py. Three copies of a 13 KB reader is a deliberate trade: a
    # core.tool that cannot be extracted and run on its own is a tool node that
    # made a promise about a sibling node, and the whole doctrine is about not
    # doing that. Recorded as decision D-TOOL-1 in results/STAGE12-RESULTS.md.
    p_tool.embed(
        ctx, "splat-to-ply", "pipeline/splat_to_ply.py", "1.0", "converter",
        "python",
        [("pipeline/splat_to_ply.py", "tools/splat-to-ply/splat_to_ply.py"),
         ("pipeline/ply.py", "tools/splat-to-ply/ply.py")],
        tool_license,
        {"example": "python splat_to_ply.py plush.splat plush.ply",
         "argv": ["python", "splat_to_ply.py",
                  "recipe/inputs/" + source_name, "plush.ply"],
         "toolchain": "python>=3.8",
         "dependencies": ["numpy"],
         "note": "Reads the 32-byte-record .splat the WebGL viewers use and "
                 "writes the INRIA-convention PLY that p_gsplat.py ingests. "
                 "Every transform is the exact inverse of what the .splat "
                 "writer applied, except the alpha clamp, which is counted."},
        produced=["gsplat"],
        note="The converter that turned the embedded source into the PLY the "
             "next tool read. That PLY is NOT in this package and does not "
             "need to be: this tool plus recipe/inputs/ regenerates it, and "
             "the recipe records its sha256 so the regeneration is checkable "
             "(SPEC.md section 3.17).")

    p_tool.embed(
        ctx, "werk-gsplat", "pipeline/p_gsplat.py", p_gsplat.TOOL_VERSION,
        "converter", "python",
        [("pipeline/p_gsplat.py", "tools/werk-gsplat/p_gsplat.py"),
         ("pipeline/ply.py", "tools/werk-gsplat/ply.py"),
         ("pipeline/common.py", "tools/werk-gsplat/common.py")],
        tool_license,
        {"example": "python p_gsplat.py plush.ply plush.wkgs --quat-order wxyz",
         "argv": ["python", "p_gsplat.py", "plush.ply",
                  "splats/plush.wkgs", "--quat-order", "wxyz"],
         "toolchain": "python>=3.8",
         "dependencies": ["numpy"],
         "note": "Ingests an INRIA-convention Gaussian-splatting PLY into the "
                 "six declared streams of spec/layouts/gsplat.layout.txt. "
                 "common.py is here because it holds the envelope writer, and "
                 "a tool that could not be extracted whole would be making a "
                 "promise about another node."},
        produced=["gsplat"],
        note="This is the file that wrote splats/plush.wkgs. If you want to "
             "know exactly what `exp`, `sigmoid` and the SH transpose did to "
             "your numbers, read it -- that is why it is here.")

    p_tool.embed(
        ctx, "werk-pointcloud", "pipeline/p_pointcloud.py",
        p_pointcloud.TOOL_VERSION, "processor", "python",
        [("pipeline/p_pointcloud.py", "tools/werk-pointcloud/p_pointcloud.py"),
         ("pipeline/ply.py", "tools/werk-pointcloud/ply.py"),
         ("pipeline/common.py", "tools/werk-pointcloud/common.py")],
        tool_license,
        {"example": "python -c \"from p_pointcloud import from_gsplat; ...\"",
         "toolchain": "python>=3.8",
         "dependencies": ["numpy"],
         "note": "Two producers share one writer here: `ingest_ply` for a PLY "
                 "point cloud, and `from_gsplat` for the normative DC-band "
                 "degradation this package used."},
        produced=["points-dc"],
        note="The processor that derived points/plush-dc.wkpc from the splat. "
             "Its `from_gsplat` is nine lines and they are the whole of "
             "gsplat.layout.txt section 7.")

    p_tool.embed_config(
        ctx, "splat-to-ply-run", "tool-splat-to-ply",
        {"input": "recipe/inputs/" + source_name,
         "output": "plush.ply",
         "alpha_clamp": list(conv["alpha_clamp"]),
         "alpha_clamped_count": conv["alpha_clamped_count"],
         "degenerate_quaternions": conv["degenerate_quaternions"],
         "quat_order_in": conv["quat_order_in"],
         "quat_order_out": conv["quat_order_out"],
         "transforms": conv["transforms"]},
        "recorded",
        environment=env, determinism="deterministic",
        determinism_note=(
            "Every operation is a fixed-point arithmetic transform of the "
            "input bytes with no random source and no wall-clock input, so two "
            "runs on this machine produce the same %d-byte PLY; the recipe "
            "carries that file's sha256 and the gate re-runs the conversion "
            "and compares." % conv["output"]["size"]),
        unrecorded=["the exact libm build that evaluated log(); its last-bit "
                    "result is the only thing that could differ across "
                    "machines, and only in the final float32 rounding"],
        ran_at=CREATED,
        note="%d of %d alpha values were at a byte endpoint and were clamped "
             "half a quantisation step inwards before the logit, because "
             "logit(0) and logit(1) are infinities and ENVELOPE.layout.txt "
             "section 6 forbids one in a core payload. The count is here "
             "rather than in a comment because a conversion that silently "
             "clamped and a conversion that silently produced infinities are "
             "both wrong."
             % (conv["alpha_clamped_count"], conv["count"]))

    p_tool.embed_config(
        ctx, "werk-gsplat-run", "tool-werk-gsplat",
        {"input": "plush.ply",
         "output": "splats/plush.wkgs",
         "quat_order": "wxyz",
         "quat_order_source": "declared by the caller",
         "source_convention": "inria-3dgs/1",
         "activation": {"scale": "exp", "opacity": "sigmoid", "sh": "identity"},
         "sh_coeff_order": "coefficient-major",
         "resample": False, "recentre": False, "rescale": False},
        "recorded",
        environment=env, determinism="deterministic",
        determinism_note=(
            "exp() and the logistic function are the only inexact operations "
            "and both are applied elementwise to declared inputs; the writer "
            "emits a canonical MessagePack header, so the %d-byte payload is "
            "byte-identical across runs on this machine."
            % len(blob_gs)),
        unrecorded=[],
        ran_at=CREATED,
        note="quat_order was DECLARED rather than inferred, and the same pass "
             "measured the statistic anyway: %s. A declared value and an "
             "inferred one are different claims, so the package records which "
             "this is AND what the measurement would have said (S12-3). The "
             "first cold reader of this fixture found this exact sentence "
             "empty, because the writer interpolated an evidence string that "
             "said only 'declared by the caller'; the statistic is computed "
             "unconditionally now."
             % stats["quat_order_statistic"])

    p_tool.embed_config(
        ctx, "werk-pointcloud-run", "tool-werk-pointcloud",
        {"producer": "from_gsplat",
         "input_sections": ["means", "sh-dc"],
         "color_dtype": "u8",
         "color_space": "linear-srgb",
         "sh_c0": SH_C0,
         "formula": "clamp(0.5 + sh_c0 * dc, 0, 1) * 255, rounded half to even",
         "decimate": False, "resample": False},
        "recorded",
        environment=env, determinism="deterministic",
        determinism_note=(
            "Three multiplies, a clamp and a round-to-nearest-even on declared "
            "inputs. No libm call at all."),
        unrecorded=[],
        ran_at=CREATED,
        note="The colour is quantised to 8 bits per channel, which is the one "
             "lossy step in this package. It is lossy against the DC band, not "
             "against the splat: the splat keeps its f32 sh-dc section and a "
             "consumer that wants full precision reads that. Measured on this "
             "asset it is lossless in practice: the source's colours were "
             "8-bit to begin with and never left the 1/255 lattice, which the "
             "first cold reader of this fixture verified over all 281 498 "
             "points.")

    # ---- the source, owned by the recipe node (section 3.11 hermeticity) --
    src_file = ctx.put("recipe/inputs/" + source_name, source_bytes)

    # ---- the splat -----------------------------------------------------
    p_gsplat.run(
        ctx, ply_path, node_id="gsplat", path="splats/plush.wkgs",
        quat_order="wxyz", epistemic="measured",
        inputs=["recipe/inputs/" + source_name],
        params={"chain": ["pipeline/splat_to_ply.py", "pipeline/p_gsplat.py"],
                "intermediate_ply_sha256": conv["output"]["sha256"],
                "intermediate_ply_bytes": conv["output"]["size"],
                "alpha_clamped_count": conv["alpha_clamped_count"]},
        edges=[{"to": "tool-werk-gsplat", "kind": "enhances", "role": "made-by"},
               {"to": "recipe", "kind": "enhances", "role": "recorded-by"}],
        part="whole")

    # S12-7, RULING (2026-08-08 ruling 22), implemented: `primary.geometry` is
    # the type-agnostic slot, so a splat package gets a primary key like
    # everyone else instead of omitting the block and leaving the reader a
    # mesh fallback that finds nothing. NOT `primary.mesh`: that key still
    # means a mesh, and a Gaussian splat is not one.
    ctx.primary["geometry"] = "gsplat"

    # ---- the point cloud ------------------------------------------------
    p_pointcloud.run(
        ctx, "points-dc", "points/plush-dc.wkpc", blob_pc, pc_stats,
        note=("%d points: the splat's means EXACTLY, and its degree-0 SH band "
              "through clamp(0.5 + %.17g*dc, 0, 1) quantised to 8 bits per "
              "channel, in LINEAR sRGB. Nothing was resampled and nothing was "
              "decimated -- this is the whole splat seen by a consumer that "
              "does not implement Gaussian splatting, which "
              "spec/layouts/gsplat.layout.txt section 7 makes a NORMATIVE path "
              "rather than a courtesy. A reader holding the WKGS can recompute "
              "every byte of this node and check it (law 5)."
              % (pc_stats["count"], SH_C0)),
        epistemic="measured", inputs=["splats/plush.wkgs"],
        params={"derivation": "gsplat-dc-band",
                "sh_c0": SH_C0,
                "color_dtype": "u8",
                "color_space": "linear-srgb",
                "decimated": False, "resampled": False},
        edges=[{"to": "gsplat", "kind": "enhances", "role": "preview"},
               {"to": "tool-werk-pointcloud", "kind": "enhances",
                "role": "made-by"}],
        part="whole")

    # ---- the recipe -----------------------------------------------------
    recipe = {
        "recipe_version": 1,
        "target": {
            "node_id": "gsplat", "version": 1,
            "files": [{"path": "splats/plush.wkgs",
                       "sha256": sha256(blob_gs), "size": len(blob_gs),
                       "role": "gsplat"}],
        },
        "reproducibility": "deterministic",
        "reproducibility_note": (
            "Every step is a fixed arithmetic transform of bytes this package "
            "carries, performed by source this package carries: no model, no "
            "seed, no sampler, and no wall-clock or random input anywhere in "
            "the chain. Re-running the two recorded invocations on "
            "recipe/inputs/%s reproduces splats/plush.wkgs, and that has been "
            "measured rather than asserted -- but the SCOPE of the byte-exact "
            "claim is one machine, not all of them: exp(), log() and the "
            "logistic function are libm calls whose last bit is not specified "
            "across implementations, so a different platform may differ in the "
            "final float32 rounding. The gate that performs the comparison "
            "(tests/run_gate_12.py) lives in the werk source repository and "
            "does NOT travel in this package; what travels is everything it "
            "needs -- the input, the tools, and the intermediate's hash -- so "
            "any consumer can perform the same comparison with a five-line "
            "driver. A first cold reader of this fixture correctly caught the "
            "earlier wording of this note claiming otherwise."
            % source_name),
        "generated_at": CREATED,
        "pipeline": {"kind": "local"},
        "steps": [
            {
                "step_id": "splat-to-inria-ply",
                "role": "convert",
                "tool": {"name": "pipeline/splat_to_ply.py", "version": "1.0",
                         "source_file": "tools/splat-to-ply/splat_to_ply.py",
                         "tool_node": "tool-splat-to-ply",
                         "config_node": "tool-config-splat-to-ply-run",
                         "repository_revision": "not-recorded"},
                "params": {"alpha_clamp": list(conv["alpha_clamp"]),
                           "alpha_clamped_count": conv["alpha_clamped_count"]},
                "inputs": [{"path": "recipe/inputs/" + source_name,
                            "sha256": source_sha, "size": len(source_bytes),
                            "role": "source-splat"}],
                "intermediates": [{
                    "name": os.path.basename(ply_path),
                    "sha256": conv["output"]["sha256"],
                    "size": conv["output"]["size"],
                    "media_type": "application/x-ply",
                    "carried": False,
                    "reproduced_by": "tool-splat-to-ply",
                    "invocation": "python tools/splat-to-ply/splat_to_ply.py "
                                  "recipe/inputs/%s plush.ply" % source_name,
                    "note": "Deliberately not carried. SPEC.md section 3.17: an "
                            "intermediate an embedded tool reproduces from an "
                            "embedded input need not travel, provided the "
                            "recipe records its hash, its size and the exact "
                            "invocation -- which makes it MORE verifiable than "
                            "a copy, because a consumer can run the check "
                            "instead of comparing two blobs it was handed. "
                            "Carrying it would have added %d bytes to this "
                            "package to prove something the file can prove by "
                            "arithmetic." % conv["output"]["size"],
                }],
                "note": "The .splat stores ACTIVATED values quantised to bytes; "
                        "the INRIA PLY stores the pre-activation parameters. "
                        "This step is the exact inverse of the viewer's export, "
                        "except at the two alpha endpoints where no logit "
                        "exists.",
            },
            {
                "step_id": "ply-to-wkgs",
                "role": "ingest",
                "tool": {"name": "pipeline/p_gsplat.py",
                         "version": p_gsplat.TOOL_VERSION,
                         "source_file": "tools/werk-gsplat/p_gsplat.py",
                         "tool_node": "tool-werk-gsplat",
                         "config_node": "tool-config-werk-gsplat-run",
                         "repository_revision": "not-recorded"},
                "params": {"quat_order": "wxyz",
                           "source_convention": "inria-3dgs/1",
                           "activation": {"scale": "exp", "opacity": "sigmoid"},
                           "sh_coeff_order": "coefficient-major"},
                "outputs": [{"path": "splats/plush.wkgs",
                             "sha256": sha256(blob_gs), "size": len(blob_gs),
                             "role": "gsplat"}],
                "note": "Applies exp to the log scales, the logistic function "
                        "to the logit opacity, and TRANSPOSES the SH "
                        "coefficients from the source's channel-major layout to "
                        "werk's coefficient-major one. Nothing is resampled, "
                        "recentred or rescaled.",
            },
            {
                "step_id": "wkgs-to-wkpc",
                "role": "convert",
                "tool": {"name": "pipeline/p_pointcloud.py",
                         "version": p_pointcloud.TOOL_VERSION,
                         "source_file": "tools/werk-pointcloud/p_pointcloud.py",
                         "tool_node": "tool-werk-pointcloud",
                         "config_node": "tool-config-werk-pointcloud-run",
                         "repository_revision": "not-recorded"},
                "params": {"sh_c0": SH_C0, "color_dtype": "u8",
                           "color_space": "linear-srgb"},
                "outputs": [{"path": "points/plush-dc.wkpc",
                             "sha256": sha256(blob_pc), "size": len(blob_pc),
                             "role": "preview"}],
                "note": "The normative degradation of "
                        "spec/layouts/gsplat.layout.txt section 7, materialised "
                        "so a consumer can hash and cache it rather than "
                        "perform it.",
            },
        ],
        "unrecorded": [
            "who captured the source scene, and with what rig -- the "
            "distribution this file came from does not name them",
            "the training run that produced the Gaussians: its iteration "
            "count, its densification schedule and its seed are not in the "
            ".splat and cannot be recovered from it",
            "the scene's real-world scale. The means are treated as metres "
            "because the format requires a unit and the file declares none",
        ],
        "note": "A recipe for a CONVERSION rather than a generation. Every "
                "`tool` block points INTO this package with `tool_node`, so "
                "'which tool' is answered by a node id resolved here rather "
                "than by a hash somebody else has to look up (SPEC.md section "
                "3.17). No step has a `model` because no model ran, which the "
                "schema permits for the convert and ingest roles as of Stage "
                "12 (S12-2).",
    }
    rf = ctx.put("recipe/recipe.json", jbytes(recipe))
    # SPEC.md section 3.18 (ruling 1 of 2026-10-13, PROPOSED). The source is a
    # `.splat` file: an encoding that is neither JSON, nor a werk envelope, nor
    # one of the base set MINI-SPECS defines. Until that ruling the only thing
    # in this package that said what its bytes mean was the converter's source
    # code - a reference implementation with no definition beside it, which is
    # the wrong way round. It is now declared by ROLE, and the definition
    # document travels in spec/formats/ like every other part of the
    # specification.
    ctx.formats["splat-32"] = "spec/formats/splat-32.md"
    ctx.node("recipe", "core.recipe",
             ctx.version([rf, dict(src_file, role="input-media")],
                         "How this package's payloads were made, step by step, "
                         "naming the embedded tools by node id. The source "
                         ".splat travels in this node's files[] because "
                         "SPEC.md section 3.11 says a recipe that names an "
                         "input it does not carry is a promise about another "
                         "file. The one intermediate is recorded rather than "
                         "carried, by section 3.17's rule, with the exact "
                         "invocation that regenerates it.",
                         "authored"),
             edges=[{"to": "tool-splat-to-ply", "kind": "requires",
                     "role": "step-1"},
                    {"to": "tool-werk-gsplat", "kind": "requires",
                     "role": "step-2"},
                    {"to": "tool-werk-pointcloud", "kind": "requires",
                     "role": "step-3"}],
             meta={"file_formats": {"input-media": "splat-32"}})
    ctx.schemas["core.recipe"] = "spec/schemas/core.recipe.schema.json"

    # ---- semantics ------------------------------------------------------
    rgb = dc_to_linear_rgb(sh[:, 0, :])
    sem = {
        "schema_version": 1,
        "facets_version": 1,
        "facets": {
            "function": ["decor"],
            "scale-class": ["handheld"],
            "condition": ["used"],
            "style": ["x.photogrammetric-capture"],
            "mood": ["x.plush"],
        },
        "description": ("A photogrammetric 3D-Gaussian-Splatting capture of a "
                        "small plush toy: %d Gaussians spanning %.3f x %.3f x "
                        "%.3f in the capture's own units, treated as metres "
                        "because the source declares no unit."
                        % (stats["count"],
                           stats["bounds_max_m"][0] - stats["bounds_min_m"][0],
                           stats["bounds_max_m"][1] - stats["bounds_min_m"][1],
                           stats["bounds_max_m"][2] - stats["bounds_min_m"][2])),
        "keywords": ["gaussian-splat", "point-cloud", "photogrammetry",
                     "plush-toy", "capture"],
        "palette": {
            "method": "histogram-4x4x4-top-8-on-the-dc-band, truncated: the "
                      "weights sum to less than 1 by construction and are NOT "
                      "renormalised (S-24)",
            "colors": palette_from_dc(rgb),
        },
        "note": "The palette is MEASURED, over all %d DC-band colours of the "
                "splat, not sampled from a render. That is the point of "
                "computing it here: a consumer holding splats/plush.wkgs can "
                "recompute every swatch and check it." % stats["count"],
    }
    sf = ctx.put("semantics/semantics.json", jbytes(sem))
    ctx.node("semantics", "core.semantics",
             ctx.version([sf],
                         "Facet tags and a palette measured from the splat's "
                         "own DC band. The two style/mood tags are x.-prefixed "
                         "because spec/facets.json v1 has no tag for 'this is a "
                         "capture rather than an authored asset', and inventing "
                         "one in a fixture would be extending the registry by "
                         "the back door.",
                         "measured", inputs=["splats/plush.wkgs"],
                         params={"palette_method": "histogram-4x4x4-top-8",
                                 "palette_source": "sh-dc"}),
             edges=[{"to": "gsplat", "kind": "enhances", "role": "describes"}],
             part="whole")
    ctx.schemas["core.semantics"] = "spec/schemas/core.semantics.schema.json"

    # ---- provenance -----------------------------------------------------
    prov = {
        "schema_version": 1,
        "runs": [{
            "run_id": "stage-12-gsplat-fixture",
            "started": CREATED, "finished": CREATED,
            "tool": {"name": "fixtures/build_gsplat_fixture.py",
                     "version": "1.0"},
            "produced": [{"node_id": "gsplat", "v": 1},
                         {"node_id": "points-dc", "v": 1},
                         {"node_id": "semantics", "v": 1}],
            "note": ("Built from %s (%d bytes, sha256 %s), obtained from the "
                     "openly published antimatter15 splat-data demo set and "
                     "vendored in the sibling project splat-foley as "
                     "data/samples/%s. The other real splat available to the "
                     "lab, a 1 920 000-Gaussian generated world of "
                     "107 520 363 bytes, is used by tests/run_gate_12.py as an "
                     "INGEST test and is deliberately not shipped: it would "
                     "have made this fixture 110 MB to prove the same thing."
                     % (source_name, len(source_bytes), source_sha, source_name)),
        }],
    }
    pf = ctx.put("provenance/provenance.json", jbytes(prov))
    ctx.node("provenance", "core.provenance",
             ctx.version([pf], "Where the source came from and what this build "
                               "did with it, including the splat that was "
                               "considered and rejected for size.", "authored"))
    ctx.schemas["core.provenance"] = "spec/schemas/core.provenance.schema.json"

    rf2 = ctx.put("README.txt", readme_text(stats, pc_stats, source_name))
    ctx.node("readme", "core.readme",
             ctx.version([rf2], "One page for a human who opened this file and "
                                "wants to know what it is -- including the "
                                "two-section shortcut for a reader that does "
                                "not implement Gaussian splatting.", "authored"))

    summary = ("A real 3D Gaussian splat, its exact point-cloud degradation, "
               "and the source code of the three tools that made them.")
    res = PKG.finish(ctx, out_path, license_block, summary)
    res.update({
        "seconds": round(time.perf_counter() - t0, 2),
        "gaussians": stats["count"],
        "sh_degree": stats["sh_degree"],
        "wkgs_bytes": len(blob_gs),
        "wkpc_bytes": len(blob_pc),
        "source": {"path": source_path, "sha256": source_sha,
                   "size": len(source_bytes)},
        "intermediate_ply": conv["output"],
        "gsplat_stats": stats,
        "points_stats": {k: v for k, v in pc_stats.items() if k != "fields"},
    })
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=os.path.join(ROOT, "fixtures"))
    ap.add_argument("--source", default=DEFAULT_SOURCE)
    ap.add_argument("--scratch", default=os.path.join(ROOT, "data", "stage12"))
    ap.add_argument("--json")
    args = ap.parse_args(argv)
    if not os.path.isfile(args.source):
        raise SystemExit(
            "source splat not found: %s\nPass --source. The Stage 12 fixture is "
            "built from a REAL captured splat and this script will not invent "
            "one." % args.source)
    os.makedirs(args.out, exist_ok=True)
    out_path = os.path.join(args.out, "gsplat-v1.werk")
    res = build(args.source, args.scratch, out_path)
    print(json.dumps({k: v for k, v in res.items() if k != "gsplat_stats"},
                     indent=2))
    print("\nwrote %s\n  %d bytes, %d entries, %d nodes, sha256 %s"
          % (out_path, res["bytes"], res["entries"], res["nodes"], res["sha256"]))
    if args.json:
        with open(args.json, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(res, fh, indent=2)
            fh.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
