# werk roadmap

Stages with hard acceptance gates. Nothing advances on assertion — every
gate is a measurement (house rule).

## Stage R — Gregor's rulings, 2026-08-08 ✅

The consolidated decision list, answered and implemented.
`docs/RULINGS-2026-08-08.md` is the canonical record; the implementation of
rulings 1–6, 8–15 and 20 is measured in **`results/STAGE-RULINGS-RESULTS.md`**
(rulings 16, 18 and 19 belong to the pipeline wave).

**Gate:** every ruling implemented in spec, schema and writer; every fixture
rebuilt; every existing gate re-run with fresh numbers; nothing claimed green
that was not run.

DONE 2026-08-08, MEASURED: Stage 2 **11 PASS / 0 FAIL / 1 SKIP**, Stage 3A
**9 / 0**, Stage 3B **19 / 0**, Stage 6 **34 / 0**, Stage 9 **15 / 0**, Blender
**18 / 0**, the engine-free WerkLink `werk_gate` **10 / 0**, the Unreal 10B
roundtrip gate **16 / 0**, `cub-werk` **35 + 7 + 1 tests ok**.

The Unreal gate refused on the first attempt — it will not run while an editor
holds the assets it rewrites, and killing a live testbed to make a number appear
is the opposite of what that refusal is for. Recorded as NOT RUN rather than as
a pass, which is why the gap it was hiding got found: on the re-run it went
11 PASS / 5 FAIL, four stale counts and **one real defect — WerkLink's C++
exporter never emitted the now-mandatory `spec_sha256`** (S-R-6). Fixed,
rebuilt, and its digest is byte-identical to the Python and Rust
implementations of the same algorithm.

The spec gained `spec_sha256` (mandatory), a declared convention→node map,
`core.retarget.bind`, an optional per-bone translation section at animclip
grammar revision 2, and **§12, the self-indexing recovery appendix**. The
skeleton canon went `draft` → `approved` / `canon_version 1.0` with the
thigh/shin swap applied. Fixture sizes and hashes now live in exactly one
generated place, `fixtures/fixtures.json` + `FIXTURES.md`, pinned by every gate
through `tests/fixture_pin.py` — which is the structural fix for S8-1…S8-5.

**Open from this wave: ruling 9's "bone count +1"** cannot be applied, because
the drafted skeleton already carried the base root the ruling describes.
Implemented in substance (the topology is now normative rather than incidental)
and filed as **S-R-1** rather than satisfied by inventing a 24th bone with no
role. Needs one yes or one correction.

## Stage 0 — Doctrine ✅
Manifesto v0.1 (twelve laws), profile-1 spec draft, CUB renderer analysis,
VLocalZ VCS analysis. DONE 2026-07-22.

## Stage 1 — Spec complete ✅
Author every ⛏ item: JSON Schemas for all structured nodes, layout.txt
grammars (flow field, rest poses, anim tracks, imposter descriptor,
skeleton bin), facets.json v1, the canonical humanoid bone set with numeric
canonical pose, MNFL-style envelope spec for binary nodes.
**Gate:** spec/ folder is self-contained — an agent reading only spec/ can
answer any encoding question without asking.

DONE 2026-08-08. Delivered: `spec/README.md` (index + the ten questions),
`spec/SPEC.md` (all ⛏ resolved), `spec/MINI-SPECS.md` (zip/JSON/UTF-8/PNG/
WAV/GLB/CRC-32/zlib byte-level, SHA-256 + Ed25519 test vectors), 16 JSON
Schemas, 6 layout grammars, `facets.json` v1, the 23-bone canonical humanoid
+ 30-bone hands extension, and `spec/examples/` (schema-valid manifest, a
real 560-byte WKRP binary, annotated hex dump, one stdlib generator).

Gate measurement, self-audit pass: 0 failures across 8 checks — every path
referenced by a spec document exists; every schema is valid draft 2020-12;
the example manifest validates and every schema/layout path it maps to
exists; every `core.*` node type in the schema enum appears in both SPEC.md
and README.md; both skeletons validate and their local→model recomposition
residual is 5.6e-10 against a declared 1e-5 tolerance; the facet registry
validates and its scale bands are contiguous; every envelope magic appears
in both ENVELOPE.layout.txt and its own layout file; the binary fixture
satisfies every envelope assertion. The audit also found and fixed one real
spec contradiction (payload_size vs trailing alignment padding).

~~Still open: the canonical humanoid is `status: "draft"`.~~ **Closed
2026-08-08 (Stage R):** the canon is `status: "approved"`,
`canon_version: "1.0"`, with the thigh/shin swap applied — thigh 0.43, shin
0.42, which moves the knee from y = 0.50 to y = 0.49 and moves nothing else.
The golden sample exists (Stage 2 item 3, five fixtures now); the fresh-agent
measurement is Stage 4's and has been run twice.

## Stage 2 — Reference implementation (Rust core, three faces)
`werk-core` in Rust, built as cdylib with a C ABI (`werk.h`) → ONE
`werk.dll/.so/.dylib`: read/write/verify/materialize, manifest validation,
Ed25519 signature chain, version ops, graceful-degradation loader. C++
consumes header+DLL; Python binds via ctypes over the same DLL — zero pip
dependencies anywhere. Separately: the embedded single-file zero-dep
bootstrap readers (`loaders/werk_read.{py,rs,c}`) that ship INSIDE every
werk file (core.loader nodes; source always, binaries opt-in + signed +
never auto-executed). Container default: store-mode zip.
**Gate:** round-trip byte-identity on untouched nodes; damage gauntlet
passes; the same .werk opens from Rust, C++, and Python through the one
DLL; each embedded bootstrap reader parses the golden sample standalone.

DONE 2026-08-08, gate PASSED and re-measured after the spec repair:
`python tests/run_gate.py` → **10 PASS, 0 FAIL, 0 SKIP**. 44 cargo tests
green; round-trip byte-identical from the zip, from the committed directory
form, and from a freshly materialised directory; four damage scenarios each
asserting the exact report and the exact survivors; the same 15 nodes and the
same `signed-and-valid` verdict from Rust, C++ (MSVC 19.38) and Python
(ctypes) over one 879616-byte `werk.dll`; all three bootstrap readers verify
26/26 files across 15 nodes standalone (`werk_read.py` stdlib-only,
`werk_read.rs` under bare `rustc -D warnings`, `werk_read.c` under both
`gcc -std=c99 -Wall -Wextra` and `cl /W3`, byte-identical output). Full
numbers in HANDOVER.md.

Spec repair (2026-08-08): the eight findings Stage 2 filed (S-1..S-8) are all
resolved — see HANDOVER.md "Stage 1 decisions 17–24". The gate above is the
post-repair measurement, not the original run.

## Stage 3 — Enrichment pipeline ✅
Extend the splat-foley pipeline to emit full .werk: LOD chain, imposter
baker (beauty-shot renderer generalized), V-HACD colliders, mass/inertia,
rest-pose drop sim, flow field, MikkTSpace tangents, texture cook
(linear-space mips), semantics (facet tags + embedding + palette),
properties block. HF-hostable variant with clean-licensed model set.
**Gate:** bare GLB in → conformant fully-enriched .werk out, unattended;
every derived node carries input_hash + epistemic stamps.

Part A DONE 2026-08-08 — the golden sample, which is the gate's output side
proven on one real asset before the pipeline is generalised.
`fixtures/crate-v1.werk`: 13262619 bytes, 157 zip entries, 36 nodes, 155
declared files, a 78507-byte manifest, `preview_prefix_bytes` 723944 (5.46 %
of the archive carries the browsable tier), one signature chain entry,
store-mode. Built by `fixtures/build_golden.py` from
`<lab>\splat-foley\outputs\example` — 20 effects, 73 WAVs, 6 orbit views, 10
segment crops, all copied byte for byte; bounds Welzl-exact and checked
against every vertex; facet tags and the wood property block authored and
stamped. Two runs produce byte-identical output.
`fixtures/crate-v1-damaged.werk` carries one flipped payload byte and one
unknown node type.

**Gate A measured:** `python tests/run_gate_a.py` → **7 PASS, 0 FAIL,
0 SKIP**. Round-trip byte-identical (12.6 MiB in 0.11 s); the damaged variant
reports exactly one `hash-mismatch` (1 node dead), three
`node-skipped-unknown-type`, keeps 33 nodes alive and stays
`signed-and-valid` — because a corrupt payload is not a forged manifest; all
three bootstrap readers verify 155/155 files across 36 nodes standalone.

Part B DONE 2026-08-08 — the pipeline itself. `pipeline/enrich.py
<input.glb> <out.werk>` turns a bare GLB into a signed, schema-valid,
fully-enriched `.werk` unattended: thirteen producers (geometry + tangents,
bounds, texture cook with linear-space mips, materials, two-tier octahedral
imposters, the LOD chain, convex colliders, mass properties, drop-sim rest
poses, SDF + flow field, semantics, simulation properties, provenance), each
an island that yields a missing node and a report rather than a dead run.

**Gate B measured:** `python tests/run_gate_3b.py` → **19 PASS, 0 FAIL,
0 WARN** over three real GLBs (`wooden-crate-01`, the Khronos `lantern`, and
`example` — 408 triangles with no images and no material block).

| | `wooden-crate-01` | `lantern` | `example` |
|---|---|---|---|
| bytes | 17 936 593 | 26 871 359 | 7 551 623 |
| nodes / declared files | 37 / 108 | 38 / 123 | 33 / 74 |
| derived nodes, input_hash recomputed | 27 / 27 | 28 / 28 | 23 / 23 |
| werk-core | 0 err, 0 dead | 0 err, 0 dead | 0 err, 0 dead |
| producers | 16 ok, 0 failed | 16 ok, 0 failed | **15 ok, 1 failed** |
| wall | 196.9 s | 88.9 s | 72.3 s |

All 108 node versions carry an epistemic stamp; all 78 stamped `measured` or
`inferred` carry `input_files` + `input_params` + `input_hash`, and the gate
**recomputes every one of those 78 hashes from the packages' own bytes** —
78/78 match. All three verify standalone through `loaders/werk_read.py` and
validate against the JSON Schemas the package itself carries. Two
`--reproducible` runs are byte-identical. The `example` asset is the island
rule under test rather than described: the texture cook failed with a named
exception, the failure landed in `x/pipeline-report.json`, and the package
came out anyway with 0 dead nodes.

Honest gaps, in full under HANDOVER "Stage 3 Part B results": the
vision-language path is implemented and env-driven but has **never completed**
(the endpoint refused every connection, so `epistemic: "inferred"` properties
are a stub with a note); tangents are NOT MikkTSpace and say so; V-HACD is not
vendored and what runs is a declared-worse `voxel-hacd-lite/0.1` with its fit
measured both ways; no audio, skeleton, animation or destruction; only three
small assets. Eight spec findings filed, S3-1…S3-8.

## Stage 4 — The agent gauntlet (the paper's experiment) ✅ run 1
N fresh agents × M languages, file-only, write loaders. Measure success
rate, time-to-loader, coverage, degradation behavior. Iterate spec until
the numbers are publishable.
**Gate:** ≥ agreed success threshold across languages; every failure
becomes a spec fix, not an excuse.

RUN 1 MEASURED 2026-08-08 — full write-up in `gauntlet/RESULTS.md`:

| | |
|---|---|
| success rate | **4 / 4** (Python, JavaScript, Rust, C) |
| median time to a working reader | **637 s**; mean 642 s; range 486–806 s |
| used the bundled loaders to understand the format | **0 / 4** |
| extracted mesh + sound, hashes matching the manifest | 4 / 4 |
| distinct spec bugs surfaced | **12** (S-10 … S-21), 8 fixed, 4 filed for Gregor |

Every agent worked from `spec/` alone; two checked a bundled loader at the
end and found it did *less* than what they had already built. Unprompted, all
four synthesised damaged copies and ran them, and each independently got
right the thing Stage 2 flagged as easy to reverse: a corrupt payload leaves
the signature valid, a corrupt manifest does not.

Not yet publishable, and `gauntlet/RESULTS.md` says why: n = 1 per language,
one model family, no zip64 fixture, and **the fixture used carries no custom
binary**, so the entire envelope apparatus went untested. The honest next run
is more agents per language, at least one non-Claude model, and a fixture
with a binary payload — in that order.

**The binary-payload fixture arrived in round 2. The non-Claude model arrived
2026-08-08 in the cross-vendor round ✅** — two of them, four runs, **4/4**:
OpenAI Codex CLI 0.144.1 on `gpt-5.6-sol` (558 s round-1 task, 512 s splat
task) and Moonshot Kimi Code CLI 0.15.0 on `kimi-for-coding` (106 s, 377 s),
on the **pinned committed** fixtures, graded by hashing the extracted bytes
against the manifest rather than by report. **0/4 used a bundled loader to
learn the format, 0/4 ported one, 0/4 wanted anything from outside the file**;
both reproduced round 3's 281 498-point sample exactly; **S-10 (`input_hash`)
held at 25/25 first pass in a foreign model**. Five findings filed,
**S-XV-1 … S-XV-5**, none fixed — they are spec-edit work and this wave edited
no spec. The sharpest, **S-XV-5**, is about the experiment: the Moonshot agent
met all five of round 1's success clauses in 106 s having read **only
`MANIFEST.json`**, so round 1's criteria are satisfiable without the
specification; the same model on the splat task read fourteen files, so it is
the *task* that forces `spec/` open, not the vendor. Verdict recorded as
**softened, not removed** — vendor diversity, not implementer diversity.
Full record: `results/STAGE-CROSSVENDOR-RESULTS.md`;
`gauntlet/RESULTS.md` "cross-vendor round"; `gauntlet/roundXV/`.

**Still open after it:** S-XV-1, S-XV-2 and S-XV-3 as spec edits (**S-XV-4 is
CLOSED** — `SPEC` §2.1 `payload_file`, 2026-08-09, PROPOSED pending Gregor); a
cross-vendor damage gauntlet (neither vendor synthesised damage and the damaged
fixture was not handed out); a zip64 fixture; and the paper-body edit to §7
replacing "remains untaken" with what was actually measured (proposed wording in
the result file's §6). *"An implementer that is not a frontier agentic coding
model" is no longer open: the open-weights round and its post-fix arm ran eight
of them.*

## Stage OW-FIX — the open-weights findings turned into spec ✅

Every gauntlet failure becomes a spec fix (house rule). S-OW-1 (the
signed-message construction), S-OW-2 (which file in a node is THE payload),
S-OW-3 (a worked hex example for every envelope magic) and S-OW-4 (say that the
zip library exists) implemented; all seven fixtures rebuilt; the models that
found the gaps re-run against the fixed package.

**Gate:** every fix in spec, schema and writer; `spec_sha256` moved and every
fixture rebuilt; every gate re-run with fresh numbers; and the post-fix model
arm reported straight whatever it says.

DONE 2026-08-09, MEASURED. `spec_sha256` **`3984a555…450ebd`**. Gates: Stage 2
**11/0/1 SKIP**, 3A **10/0** (one NEW clause executing the S-OW-2 failure), 3B
**19/0**, 6 **34/0**, 9 **15/0**, 12 **18/0**, Blender **20/0**, Unreal
**16/0**, cub-werk **43 passed / 0 failed**. Post-fix arm, 5 models / 9 runs,
graded by artifact: **the claim "gap fixed → same model now passes" did NOT
hold** — `llama-3.1-8b` took `files[0]` again with `payload_file` in front of it,
`qwen3.8-4B` still fails though its failure moved off the zip container. The
control `glm-4.6v-flash` improved to a first-attempt pass, **0/9 false tampering
alarms**, and `google/gemma-4-e4b` is the **first sub-9B pass** in any
open-weights round while `nvidia/nemotron-3-nano-4b` confirms the 4B floor from a
second lineage. Full record: **`results/STAGE-SPECFIX-OW-RESULTS.md`**.

**Still open after it:** **S-XV-4/S-OW-2's `payload_file` needs Gregor's
ruling** — it ships marked PROPOSED. Then S-SFX-2 (two manifest schemas with
independently maintained `$defs/version`), S-SFX-3 (gates should build the cdylib
rather than trust a stale one), S-SFX-4 (`PYTHONIOENCODING=utf-8` for generated
programs), S-SFX-5 (move the construction line into §12's opening paragraph);
`google/gemma-4-12b-qat` still unloadable, so the 9.4B–27B band is unmeasured;
and the package now costs **32 722–39 767 tokens**, over the 35 000 budget for
the densest tokenizers, which wants a bisect of what can be cut.

## Stage 5 — CUB consumption
CUB loads .werk core + x.cub tier with zero cook step; fsepw-scale
instancing test with imposters + LOD selection from payload metrics.
**Gate:** measured load-time and frame-time vs. today's GLB path.

## Stage 6 — Skeleton & retarget proof ✅
Canonical humanoid + calibration solver; retarget one Mixamo clip, one UE
mannequin clip, one raw mocap take.
**Gate:** three successful retargets with residuals below declared
tolerance.

DONE 2026-08-08, gate **MEASURED and PASSED**:
`python tests/run_gate_6.py` → **33 PASS, 0 FAIL, 0 SKIP** in 29.2 s.
`retarget/` is the implementation; `fixtures/humanoid-retarget-v1.werk` is the
artifact. Tolerances are declared in the gate file above the measurement code.

The three rigs, all real and all foreign (the Mixamo clip was substituted — see
"Stage 6 results" in HANDOVER.md for why, and what replaced it):

| rig | source | bones | solved stature scale | round trip through `core.anim.clip` |
|---|---|---|---|---|
| Khronos **CesiumMan** | glTF-Sample-Assets, CC-BY | 19 joints | 1.35696 | **5.16e-08 rad** |
| **UE 5.7 mannequin** | `SK_Mannequin` + `ThirdPersonWalk`, exported headless from a live editor | 68 bones | 0.99052 | **5.22e-08 rad** |
| **CMU mocap 02_01** | raw BVH, free for all uses | 31 joints | 0.06152 | **8.80e-08 rad** |

Declared tolerance was **1.0e-4 rad** — the format's own stated
interoperability unit, quoted from `animclip.layout.txt`. Every measured
residual is three orders of magnitude inside it. Six cross-rig transits
(A → canonical → B → canonical, crossing the real f32 payload twice) all land
between 5.2e-08 and 8.8e-08 rad, and each names the bones that cannot cross
rather than averaging them away.

The scale in that table is the whole claim in one column: nothing told the
solver that a BVH unit is 6.15 cm or that Unreal is centimetres. It recovered
each one from a single calibration pose, and the retargeted figures land with
their hips 0.84–1.09 m above the declared floor.

Five findings filed as **S6-1…S6-5**, including evidence from two independent
human-derived rigs that one canonical draft number — `l-shin`/`r-shin` at
0.43 m against `l-thigh`/`r-thigh` at 0.42 m — is anatomically backwards.
Filed, not applied: the canon stays `status: "draft"` pending Gregor.

## Stage 7 — Stage-two VCS (separate project, same doctrine)
CAS (VLocalZ donation) + manifest diff + byte-exact verified
materialization + node-granular sync + CDC chunking + multi-root GC.
**Gate:** store round-trip proves byte-identity against signatures;
dedup ratio measured on a real asset corpus.

## Stage 11 — Blender adapter ✅
`adapters/blender/werk_blender/`: a Blender 4.x add-on that imports and
exports werk 3D entities, installable as a zip and callable headless, with
zero external dependencies (stdlib + `bpy`, werk parsing vendored
byte-identically from `loaders/werk_read.py`).
**Gate:** import the golden fixture; import the damaged fixture with the exact
skip report; round-trip werk → Blender → werk with vertex count, entity uuid
and tags surviving, and the exported package verified by werk-core and by
`werk_read.py` standalone; timings recorded.

DONE 2026-08-08, gate **MEASURED and PASSED** on a real Blender:
`python adapters/blender/test_gate.py` → **16 PASS, 0 FAIL, 0 SKIP** in 3.5 s
under **Blender 4.2.1 LTS**, a system install found by the gate's own search.

| | |
|---|---|
| import `crate-v1.werk` | 36 nodes, 34 alive, **0 dead**, 2 skipped-unknown, **0 unexpected skips**, 272 verts / 408 tris, 0.329 s |
| import `crate-v1-damaged.werk` | exactly `{hash-mismatch: 1, node-skipped-unknown-type: 3}`, 1 node dead, 33 alive, mesh still imported, 0.149 s |
| round trip | uuid **survived**, tags **survived**, verts **272 → 272**, materials 1 → 1; 0.151 s in, 0.220 s out, 0.022 s back |
| exported package | 624539 B, 50 entries, 8 nodes, 49 files, manifest 18591 B, preview prefix 597751 B (95.71 %) |
| verified by werk-core | 8 nodes, 8 alive, **0 errors, 0 warnings** |
| verified by `werk_read.py` standalone | **49/49 files** across 8 nodes, exit 0 |
| writer determinism | 49/49 payload entries byte-identical across two exports, entry order identical |
| rig round trip (built in Blender) | 3 bones, worst rest-head error **0 m**, worst posed rotation error **8.4e-08 rad**, skeleton recomposition residual 6.0e-08 against a 1e-5 tolerance |
| textured round trip (built in Blender) | 2 `core.tex` nodes, colour space **sRGB and Non-Color both preserved**, both material slots recovered |
| install from zip | 246356 B, 53 entries, imported from the unpacked zip and registered |

The gate found five real bugs before it passed, all of them the silent kind —
a conjugation where a left-multiplication belonged (exactly 45° on every posed
bone), a `frame_set` that discarded each pose before keying it, two authorities
for one armature, `is` instead of `==` on Blender's RNA wrappers, and a `meta`
block the bootstrap reader never carries. Details in HANDOVER "Stage 11
results".

## Stage 9 — AI-generation recipe, disclosure, and profile 2 ✅
`core.recipe` (the full reproduction record: models with weight hashes,
prompts, seeds, samplers, LoRAs by hash, embedded pipeline graphs, tool
versions, every input medium by hash, and a declared reproducibility grade),
`core.disclosure` (machine-readable facts, no enforcement of any kind),
`core.embedding` (`WKEM`), profile 2 `image/1`, an honest `x.c2pa.export`
stub, and conformance fixture #2 — a real AI-generated image with its real
recipe, carrying a custom binary so `ENVELOPE.layout.txt` finally gets
exercised by a handed-out fixture.
**Gate:** fixture #2 conformant, all existing gates still green after the
spec touches, and 2/2 fresh gauntlet agents parse the envelope payload and
state the image's recipe and disclosure correctly from the file alone.

DONE 2026-08-08.

**Fixture clause MEASURED:** `python tests/run_gate_9.py` → **14 PASS,
0 FAIL, 0 SKIP**. `fixtures/ista-varun-v1.werk`, 9 969 937 bytes, 63 zip
entries, 15 nodes (14 alive, 1 skipped — the `x.c2pa.export` node, by
design), 0 dead, `signed-and-valid`, 0 errors; round-trip byte-identical;
the builder deterministic across two runs; all three bootstrap readers verify
60/60 files standalone. The two checks that carry the weight: every
`ENVELOPE.layout.txt` §7 assertion holds on the `WKEM` payload with **one
section on each branch** of the section consistency rule, and the descriptor
**recomputes from `image/source.png`** with a worst component drift of
**1.381e-08** against the header's declared 1e-06 tolerance — which is what
turns `epistemic: "measured"` from a claim into a measurement.
`preview_prefix_bytes` recomputes to the byte (998 658, 10.02 % of the
archive); the S-14 two-pass order reproduces exactly with five exact paths
interleaved between prefixes; the S-18 case is present (two files listed by
both versions of the recipe node with identical hash and size); recipe
hermeticity holds (every referenced input embedded, in the node's `files[]`,
hashes agreeing); and the JSON and `WKEM` palettes agree to 1e-6.

**Existing gates re-measured after the spec touches**, not assumed:
Stage 2 `run_gate.py` → 10 PASS, 0 FAIL, 1 SKIP (this host's mingw gcc
cannot compile a hello-world; MSVC builds the same loader and it passes).
Stage 3A `run_gate_a.py` → 7 PASS, 0 FAIL, 0 SKIP. 44 cargo tests green.

**Gauntlet clause MEASURED: 2/2, gate PASSED.** Two fresh agents, Python and
Rust, one file and nothing else. Both parsed the `WKEM` envelope and checked
BOTH branches of the section consistency rule; both stated the recipe and the
disclosure correctly, including the reproducibility grade and what it does not
promise; neither wanted anything from outside the file; neither used the
bundled loaders. **Both independently recomputed `werk.descriptor.labhog/1`
from the source pixels — the Python agent bit-exactly, 0.000e+00 drift against
a declared 1e-6 tolerance** — which is what turns `epistemic: "measured"` from
a claim a package makes into one a stranger can check. The Python agent
implemented Ed25519 from the embedded `MINI-SPECS.md` §12 and reported
`signed-and-valid`; the Rust agent declined the curve arithmetic and reported
`signature-unverified`, the fourth fixed token §10.0 defines for that case.
Two readers, two honest verdicts, no guessing. Three spec bugs filed (S-26,
S-27, S-28), all fixed; one follow-on (S-30) open. Caveats, including a first
Rust attempt that died without a report and two lost transcripts, are in
`gauntlet/RESULTS.md` round 2.

Five spec findings from this stage: S-24 (a top-N palette's weights do not
sum to 1 and must say so rather than renormalise) and S-25 (a reader's
convention set belongs to the profile, not the reader — all three bootstrap
loaders accused a well-formed `image/1` package of fourteen missing
conventions) are RULED and implemented, as are S-26, S-27 and S-28 — the
three that the round-2 gauntlet agents filed against the fixture itself.
S-14, S-15, S-17 and S-18 are now written into `spec/SPEC.md` as
**PROPOSED, draft-pending-Gregor**.

Finding numbers S-22 and S-23 were claimed by three stages at once while they
ran in parallel against one working tree. The reconciliation table, with every
old label, is in HANDOVER under "Finding numbers, reconciled".

## Stage 8 — The paper
"Agent-implementability as a format-quality metric" + the format itself.
Written only after stages 1–6 hold, so every number is measured.

## Stage 8B — The second edition ✅
A superior draft: same facts, real scientific-paper structure, every number
re-traced. Record: **`results/STAGE8B-RESULTS.md`**.

**Gate:** the PDF compiles clean; NUMBERS.md complete for every quantitative
claim; no unmeasured claim stated as measured; CHANGES.md accurate.

DONE 2026-08-08, MEASURED: `paper/v2/werk-paper-v2.pdf` — **16 pages, 0
warnings, 0 overfull/underfull boxes**, 14 tables, 1 figure, 26 references.
The `.tex` is now GENERATED from `paper/v2/PAPER.md` by `paper/v2/md2tex.py`,
so the prose master and the typeset paper cannot drift — v1 maintained two
hand-written copies of one document, which is the problem `spec_sha256` exists
to prevent. New measured material that postdates v1: gauntlet round 3 (the
splat mini-gauntlet), the self-regenerating fixture, the pixel-identical
Blender→Unreal texture handoff, the three-language `spec_sha256` agreement,
the first real VLM run (and the oak-wood street lamp), reference V-HACD and
MikkTSpace, and every gate re-measured after the ruling-21/22 rebuild.
Seven inconsistencies found while re-tracing are **filed, not fixed**
(`paper/v2/NUMBERS.md` §12); N2-2 is a real disagreement inside
`results/STAGE12-RESULTS.md` (1 568 vs 1 440 values on the same clause) and
wants a re-run of `tests/run_gate_12.py` to settle.

## Stage 10 — WerkLink, the Unreal Engine adapter ✅
`adapters/unreal/WerkLink` — one editor-only UE5 plugin, two directions.
Import `.werk` → `UStaticMesh` (with LODs), `UTexture2D`, `UMaterialInstance`,
simple collision, `USoundWave`, plus bounds/props/semantics as metadata.
Export selected assets + their real dependency closure → a conformant unsigned
`.werk`, read from editor SOURCE data because UE's mesh exporters assert
headless. One static facade behind a Content Browser menu AND a commandlet
with JSON batch mode.
**Gate:** compile the plugin against a real UE toolchain and run the
commandlet import of `fixtures/crate-v1.werk`; fall back to a standalone MSVC
target over the basis-change, zip and manifest paths if no engine is reachable.

DONE 2026-08-08. **Both gates ran** — a UE 5.7 install and MSVC 2022 Build
Tools were present, so the strong gate was available and is the one that
counts; the standalone target ran as well, because it is what keeps the
engine-free core honest when no editor is around.

Gate A (UE 5.7, MSVC 14.43.34808): plugin compiled (`Result: Succeeded`);
commandlet import **exit 0**, 36 nodes → 25 imported, 11 skipped, 0 refused,
22 assets, 22 packages saved, **164 files hash-verified**, signature reported
`unverified`, 0.382 s. Damaged fixture: **exit 1** (correct — an error entry
exists), 1 node refused and 21 assets still created, with the
unknown-because-newer node reported as unknown rather than broken. Export:
exit 0, 8 nodes, 49 files, 851 055 bytes, preview prefix measured at 805 998,
spec + loaders embedded. Batch mode: exit 0.

Round trip is the number that matters: 272 verts / 408 tris in, **272 / 408
out**, identical UE-space AABB, and the WAV **byte-identical** (sha256
`1e634f03…`). Three independent readers agree on the exported package — this
adapter's core, the unrelated `loaders/werk_read.py` (whose independently
computed manifest sha256 matched to the character), and `jsonschema` against
`spec/schemas/manifest.schema.json` with **0 errors**.

Gate B (standalone, engine-free core compiled with `/W4 /WX`): **10 PASS,
0 FAIL**, 0.310 s.

Three spec findings, labelled by stage to avoid the shared-counter collision
three earlier stages hit: **S10-1** (`schemas` is required and
`minProperties: 1`, but a package of only geometry/text/loader nodes has no
node type that HAS a schema — measured, a mesh-only export was rejected and
adding one audio node made it valid), **S10-2** (`preview_prefix_bytes` is a
measurement of the container that contains it, so it is not a fixed point —
concrete evidence for the unruled S-15), **S10-3** (`core.phys.body` declares
no space although `center_of_mass_m` is required, while its two siblings each
declare one and disagree). Details and proposed rulings in HANDOVER under
"Stage 10 results".

## Stage 10B — textures for real, import all, and a live testbed under MCP ✅

Gregor's ruling: *"deliberately not implemented is not an option."* Stage 10's
texture export gap is closed, everything imports, and there is a standing UE 5.7
project that a script or a Claude Code session can drive.

Landed: real PNG texture export through Unreal's own ImageWrapper; `core.material`
texture slots in BOTH directions; a shipped master material
(`WerkLink/Content/M_WerkPBR`, a build product of a committed script) so material
import works out of the box; material instances assigned to the meshes they
govern; `core.image.*` (profile 2) imported as textures; a textured conformance
fixture, `fixtures/crate-tex-v1.werk`; the testbed at `<lab>\UnrealWerkTest\`
(outside git) with `adapters/unreal/TESTBED.md`; and an MCP server
(`tools/ue_mcp/werk_ue_mcp.py`, registered in `.mcp.json`) over Epic's Remote
Control API.

Gates, both MEASURED on this box: `python adapters/unreal/tests/roundtrip_gate.py`
→ **16 PASS, 0 FAIL**, including all three textures round-tripping
**pixel-identical**; `python tools/ue_mcp/proof_session.py` → **6 PASS, 0 FAIL**
with screenshots under `<lab>\UnrealWerkTest\proof\`.

Three more findings, all silent-failure class: **S10-4** (a bad `-Dest` reached a
CHECKED path conversion and killed the process; SPEC 10.1 has no "die" outcome),
**S10-5** (the editor accepts a screenshot command and writes nothing when its
window is not in the foreground, with no warning), **S10-6**
(`SetNumUVChannels` invalidates a UV attribute ref taken before it; the write
silently goes nowhere and every UV collapses to (0,0) while every count stays
correct). Numbers and the argument in HANDOVER under "Stage 10B results".

## Stage 12 — point clouds, Gaussian splats, and embedded tools ✅

Gregor's order, 2026-08-08: werk must hold point clouds and Gaussian splats as
first-class node families, must record the tools used to create or convert them
AS PART OF THE DATA, and must be able to EMBED THE CODE of those tools and their
configurations in the file.

Landed: **four node types and two envelope magics** — `core.geom.points`
(`WKPC`, `spec/layouts/points.layout.txt`), `core.geom.gsplat` (`WKGS`,
`spec/layouts/gsplat.layout.txt`), and `core.tool` + `core.tool.config`, which
are base doctrine and extend the `core.loader` safety rule verbatim (source
always; a prebuilt binary is inert data and is NEVER auto-executed, with
`never_auto_execute` a schema `const` rather than a switch). `core.recipe` gained
`tool_node`/`config_node`, so "which tool" points INTO the file, and an
`intermediates[]` array with a stated rule: an intermediate an embedded tool
reproduces from an embedded input need not be carried, provided the recipe
records its hash, its size and the exact invocation. Two OPTIONAL conventions,
`sh_coeff_order` and `sh_degree`; `spec/conventions-map.json` gained `optional`
and `advisory` flags so "may be omitted" is machine-readable.

The splat→point-cloud degradation is **normative in both directions**: a reader
that understands only positions and colours consumes a splat by reading two of
its six sections, and it is a conformant consumer of the node rather than a
degraded one.

**Fixture #5: `fixtures/gsplat-v1.werk`** — 30 159 206 B, 77 entries, 17 nodes,
built from a REAL photogrammetric capture (`plush.splat`, **281 498 Gaussians**,
whole: no crop, no decimation). It carries the source, the splat, its exact
point-cloud degradation, and **the source code of the three tools that made
them**.

Gate, MEASURED: `python tests/run_gate_12.py` → **18 PASS, 0 FAIL, 0 SKIP**.
The two clauses that earn it: the package **regenerates itself** — the gate
extracts the embedded tools and the embedded input into a neutral directory
with nothing from this repo on the path, runs them, and gets the recipe's
declared intermediate hash and a **byte-identical** WKGS back in 0.54 s; and the
splat **reparses from its own declared offsets** using a decoder written in the
gate file. The DC-band degradation is exact over all 281 498 points (0 position
and 0 colour mismatches), and the mandatory INRIA PLY path is measured on real
trainer output: **1 920 000 Gaussians in 1.25 s**.

**Mini-gauntlet: 1 fresh agent, the file and nothing else — SUCCESS**, in ~25
minutes. It wrote its own loader, extracted 281 498 positions and colours by the
normative two-section path, cross-checked them bit-for-bit against the shipped
point cloud, named all three tools and quoted their embedded source. It also
found **six defects, four of them real, all four now fixed** — three of which
were the format overstating what it had proved.

All fixtures rebuilt (spec changed, so `spec_sha256` changed) and every affected
gate re-run: Stage 2 **11/0/1 SKIP**, Stage 3A **9/0**, Stage 3B **19/0**,
Stage 6 **34/0**, Stage 9 **15/0**, Blender **20/0** (two new clauses, including
the real splat imported into Blender 4.2.1 as 281 498 mesh vertices with colour
on the POINT domain).

Nine findings, **S12-1 … S12-9**. Two needed Gregor: **S12-7** (`primary` has no
slot for geometry that is not a mesh) and **S12-9** (this fixture's content
licence is genuinely not established, and the package says so instead of
guessing). Full record: `results/STAGE12-RESULTS.md`.

Not done, declared: UE and CUB adapters (mapping notes filed as findings), LAS
ingest for point clouds, and a preview render of the splat.

## Stage 12B — rulings 21 and 22 (S12-9 and S12-7 closed) ✅

Gregor's same-day rulings on Stage 12's two open findings, implemented and
re-measured; full record `results/STAGE12B-RESULTS.md`.

**Ruling 21 — S12-9, content licensing: IGNORE, by doctrine.** The licensing
doctrine stands in SPEC §2's license section as the licence-side twin of
§3.12's disclosure no-enforcement doctrine: the format provides the structured
place for licence facts; filling it truthfully is the author's and their
tool's responsibility; the format neither vets nor enforces content licensing,
and no conformance clause turns on what the licence text says. The `gsplat-v1`
LICENSE stays as shipped — the honest terms-not-established notice is the
doctrine's worked example.

**Ruling 22 — S12-7: `primary.geometry`, implemented as proposed.** The
type-agnostic slot naming any `core.geom.*` node, in `manifest.schema.json`
and SPEC §2, with `mesh` kept as the narrower key; the rebuilt fixture
declares `primary: {geometry: "gsplat"}`.

Consequences drilled: `spec_sha256` → `331519c8…`, **all seven fixtures
rebuilt**, `fixtures.json`/`FIXTURES.md` refreshed, Blender vendored spec
re-vendored 51/51 byte-identical, and every gate re-run and MEASURED: Stage 2
**11/0/1 SKIP**, 3A **9/0**, 3B **19/0**, Stage 6 **34/0**, Stage 9 **15/0**,
Stage 12 **18/0**, Blender **20/0**, **Unreal 16/0** (UE 5.7), **CUB cub-werk
43/0**. The UE and CUB gates ran for the first time since Stage 12 grew the
vendored spec by four files; both failed correctly on stale pins (+4
files-verified everywhere, nothing else moved) and were
rebaselined/re-pinned with the cause stated beside the numbers.
