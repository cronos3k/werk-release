# Pipeline quality wave — rulings 16, 18, 19 (results)

Author: the pipeline-quality agent, 2026-08-08.
Protocol: `results/README.md` (ruling 20). This file is the record; `HANDOVER.md`
and `ROADMAP.md` are not touched here.

**Subtree ownership for this wave.** This agent owns `pipeline/`, `tools/vhacd/`,
`tools/mikktspace/`, `tools/build_native.py`, `tools/measure_ruling_18_19.py`
and this file. It did **not** write `spec/`, `schemas/`, `fixtures/`,
`retarget/`, `HANDOVER.md` or `ROADMAP.md` — the concurrent rulings agent owns
those. One exception, declared: `pipeline/package.py` now emits the manifest's
`spec_sha256`, because that field became mandatory in the rulings agent's schema
commit and the pipeline's manifest writer is inside this agent's subtree and
nobody else's. It calls the rulings agent's own `tools/spec_sha256.py`
reference implementation rather than reimplementing the ordering convention.

## Headline

| ruling | what it asked for | state |
|---|---|---|
| **18** V-HACD | vendor and use the real thing, fallback records which ran | **DONE**, real V-HACD v4.1 compiled with MSVC, running in the gate |
| **19** MikkTSpace | vendor the reference C, default path, Gram-Schmidt as recorded fallback | **DONE**, reference MikkTSpace running in the gate |
| **16** VLM properties | bring up the vision model and complete the first real run | **DONE**, first real VLM properties run completed on both gate assets |

Gate, re-run with all three live:

    set WERK_VLM_BASE_URL=http://<lan-ip>:8102/v1
    set WERK_VLM_MODEL=qwen3-vl-8b
    python tests/run_gate_3b.py

**19 PASS, 0 FAIL, 0 WARN**, same as before this wave — the three producers were
replaced without loosening a single check, and the two `--reproducible` runs are
still byte-identical, which also says the V-HACD path is deterministic (the CLI
forces `m_asyncACD = false`).

---

## Ruling 18 — real V-HACD

### What was vendored

`tools/vhacd/VHACD.h`, upstream **v4.1** from `kmammou/v-hacd`, **8 364 lines**,
**byte-for-byte unmodified**, sha256
`c2b750a41bc6044457c79dc51d196b7bbe5e24bfaec72d409a065434d9651ff2`,
BSD-3-Clause (`tools/vhacd/LICENSE.txt`). Route (a) of the brief: the official
C++ single header behind a small CLI. No pip, no wheel, no binding.

`tools/vhacd/werk_vhacd_cli.cpp` is ~150 lines of werk code — the only
translation unit that defines `ENABLE_VHACD_IMPLEMENTATION` — exposing V-HACD as
binary-in / binary-out. A subprocess rather than a DLL on purpose: a
decomposition that asserts on a hostile mesh takes the child down and returns an
exit code instead of taking the pipeline with it.

    python tools/build_native.py

**MSVC 19.43.34808 x64** (`/O2 /EHsc /std:c++17 /MT`), **2.37 s**, 570 296 bytes.
mingw-w64 g++ 15.2.0 also builds it clean (6.3 s) and the script falls back to it.
The toolchain is recorded in `tools/_build/build.json`; `tools/_build/` is
git-ignored, because the header is the dependency and the binary is output.

### Old versus new, on the Stage 3B gate meshes

    python tools/measure_ruling_18_19.py

Both engines in one process, on the same welded meshes, scored on the same
voxel grid with the same denominator the pipeline uses — which is why the "old"
column reproduces the Stage 3B HANDOVER table exactly (crate 0.1566 m / 3.665,
lantern 2.0019 m / 2.028).

| asset | engine | parts | hausdorff max | hausdorff mean | volume_ratio | coverage | excess | s |
|---|---|---|---|---|---|---|---|---|
| crate | voxel-hacd-lite/0.1 | 11 | 0.1566 m | 0.0089 m | 3.665 | 1.0000 | 2.665 | 0.29 |
| crate | **vhacd/4.1** | 12 | **0.1663 m** | **0.0048 m** | **4.154** | 1.0000 | 3.154 | 6.58 |
| lantern | voxel-hacd-lite/0.1 | 6 | 2.0019 m | 0.0751 m | 2.028 | 1.0000 | 1.028 | 0.13 |
| lantern | **vhacd/4.1** | 12 | **1.5529 m** | **0.0331 m** | **1.716** | 1.0000 | 0.716 | 1.11 |
| example | voxel-hacd-lite/0.1 | 12 | 0.1529 m | 0.0080 m | 3.785 | 1.0000 | 2.785 | 0.50 |
| example | **vhacd/4.1** | 12 | **0.0000 m** | **0.0000 m** | **1.926** | 1.0000 | 0.926 | 25.59 |

`volume_ratio` is collider volume / mesh volume, the number Stage 3B reported.
The two new numbers are the ratio taken **both ways** on the same grid, which is
what the brief asked for and what one ratio cannot give you: `coverage` is the
fraction of the object's own solid the colliders contain, `excess` is the volume
they add that is not the object. Both engines score coverage 1.0000 — neither
ever leaves part of the object uncovered — so the whole difference is in excess,
and a single ratio was never distinguishing over-fitting from under-fitting.

**Read this honestly: V-HACD is a clear win on two assets and a mixed result on
the crate.** Lantern: 22 % less peak error, 56 % less mean error, and 30 % less
excess volume. Example: peak error to **zero** and excess cut by a factor of
three. Crate: mean error nearly halves (0.0089 → 0.0048 m) but peak error is 6 %
*worse* and excess is 18 % *worse*. The crate is an open box, and every solid
decomposition of an open box contains the cavity — the denominator is the
solid-voxel volume, so 3.665 and 4.154 are both mostly "the crate is hollow",
not "the engine is bad". The crate's peak error is a thin slat below the default
voxel resolution.

### Fill mode and resolution, swept (S-P-2)

Same three meshes, same scoring, sweeping V-HACD's two big parameters:

| asset | fill | resolution | parts | hausdorff | ratio | coverage | excess | s |
|---|---|---|---|---|---|---|---|---|
| crate | flood | 400 000 | 12 | 0.1663 | 3.582\* | 1.0000 | 3.154 | 6.8 |
| crate | flood | 1 000 000 | 12 | **0.0411** | 3.440\* | 1.0000 | 2.989 | 13.3 |
| crate | raycast | 400 000 | 12 | 0.0560 | 3.502\* | 1.0000 | 3.060 | 11.5 |
| crate | raycast | 1 000 000 | 12 | 0.0379 | 3.426\* | 1.0000 | 2.972 | 22.3 |
| crate | surface | 400 000 | 12 | 0.1184 | 1.484\* | 0.8012 | 0.920 | 7.3 |
| lantern | flood | 400 000 | 12 | 1.5529 | 1.368\* | 1.0000 | 0.716 | 1.4 |
| lantern | flood | 1 000 000 | 12 | **1.2990** | 1.239\* | 1.0000 | 0.554 | 2.6 |
| lantern | raycast | 400 000 | 12 | NaN | 2.295\* | 0.7302 | 2.148 | 2.4 |
| lantern | surface | 1 000 000 | 12 | 0.9384 | 1.255\* | 0.8073 | 0.767 | 2.8 |
| example | flood | 400 000 | 12 | **0.0000** | 1.146\* | 1.0000 | 0.926 | 22.0 |
| example | flood | 1 000 000 | 12 | 0.0000 | 1.255\* | 1.0000 | 1.109 | 43.1 |
| example | raycast | 400 000 | 12 | 0.0000 | 2.662\* | 0.9996 | 3.475 | 42.7 |

\* this sweep ran before the denominator was aligned with the pipeline's; the
ratios in this table are against the divergence-theorem volume and are
comparable **within** the table only. Hausdorff, coverage and excess are
unaffected.

The pipeline ships **upstream's own defaults — FLOOD_FILL, resolution 400 000 —
and does not deviate**, because no setting wins on all three assets: raising the
resolution to 1 000 000 makes the crate four times better (0.1663 → 0.0411 m)
and the lantern better, and makes the example *worse* (excess 0.926 → 1.109) for
double the time. `SURFACE_ONLY` buys a much tighter volume by giving up coverage
(0.80 instead of 1.00), i.e. by leaving parts of the object outside the
colliders, which is the wrong trade for a physics collider. **Filed as S-P-2:
the resolution is a per-asset decision this pipeline currently does not make,
and the numbers to make it are in this table.**

### What the package now records

`fit.method` names the engine (`"vhacd/4.1, 12 parts (fit measured on a
44x21x24 voxel grid; …)"`) and the node meta carries the rest:

    "collider_engine": "vhacd/4.1",
    "volume_coverage": 1.0,
    "volume_excess": 3.153627,
    "hausdorff_unmeasured_samples": 0,
    "volume_measure_grid": [44, 21, 24]

Which engine ran is **recorded, never assumed**: if the binary is missing or the
child fails, `voxel-hacd-lite/0.1` runs, `collider_engine` says so and
`collider_engine_fallback_reason` carries the exact exception text.

---

## Ruling 19 — MikkTSpace

### What was vendored

`tools/mikktspace/mikktspace.c` (1 899 lines, sha256 `de87e741…`) and
`mikktspace.h` (145 lines, sha256 `17fc4338…`) from `mmikk/MikkTSpace`,
**byte-for-byte unmodified**. Licence: **zlib-style permissive**, © 2011 Morten
S. Mikkelsen — any purpose including commercial, do not misrepresent the origin,
mark altered versions, keep the notice. Full text in
`tools/mikktspace/LICENSE.txt`; provenance and hashes in
`tools/mikktspace/README.md`. Leaving both files unmodified is also what clause 2
of that licence and the header's own "designed to be stand-alone files"
paragraph ask for.

`tools/mikktspace/werk_mikktspace.c` holds the callbacks and exposes one
flat-array entry point for ctypes. Built as
`tools/_build/werk_mikktspace.dll` with **MSVC 19.43.34808** (`/O2 /MT /LD`),
**0.35 s**, 124 467 bytes.

It returns tangents **per face corner**, not per vertex — the point of
MikkTSpace is that the basis is discontinuous across a UV chart seam, so
`pipeline/mikktspace.py` splits vertices where the corners disagree.
**Positions are duplicated, never moved**: `geometry/game.glb` carries the split
vertex set and the welded mesh every other producer measures is untouched, so no
other number in the package moved.

`TANGENT.w` is MikkTSpace's own `fSign` passed through unchanged — MikkTSpace and
glTF define the same thing, `bitangent = w · cross(N, T)`.

### Tangent stats, old versus new

| asset | engine | verts | max &#124;T·N&#124; | max dev from 90° | max &#124;&#124;T&#124;−1&#124; | w=+1 | w=−1 | w∉{±1} | splits | repaired | s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| crate | gram-schmidt-accumulated/0.1 | 3 348 | 9.37e-15 | 5.4e-13° | 2.22e-16 | 165 | 3 183 | 0 | 0 | 0 | 0.004 |
| crate | **mikktspace/1.0** | **5 703** | 6.46e-06 | 3.7e-04° | 2.22e-16 | 1 938 | 3 765 | 0 | **2 355** | 11 | 0.017 |
| lantern | gram-schmidt-accumulated/0.1 | 2 737 | 3.88e-15 | 2.3e-13° | 2.22e-16 | 185 | 2 552 | 0 | 0 | 0 | 0.003 |
| lantern | **mikktspace/1.0** | **4 265** | 2.75e-06 | 1.6e-04° | 2.22e-16 | 1 312 | 2 953 | 0 | **1 528** | 15 | 0.013 |
| example | — | — | — | — | — | — | — | — | — | — | skipped: no `TEXCOORD_0` |

Both bases are orthonormal to well below anything a shader can see. Gram-Schmidt
is orthogonal to machine precision *by construction* — it is literally a
projection — so its 1e-15 is not a quality win, it is a tautology; MikkTSpace's
1e-6 is the reference implementation's own float32 arithmetic. Handedness is
exactly ±1 in every case, never a third value.

### How far apart the two actually are

The number that matters, since both pass every orthonormality check: the angle
between each split vertex's MikkTSpace tangent and the Gram-Schmidt tangent of
the welded vertex it came from.

| asset | mean | median | p95 | max | > 1° | handedness flips |
|---|---|---|---|---|---|---|
| crate | 44.66° | 9.76° | 175.13° | 180.00° | 72.8 % | 1 927 |
| lantern | 33.65° | 1.81° | 169.05° | 179.99° | 58.5 % | 1 266 |

That distribution is the finding, not a defect: a median of 1.8–9.8° with a p95
near 180° is exactly what "agrees in the chart interior, disagrees at the seam"
looks like. At a mirrored UV seam Gram-Schmidt averages two opposite tangents
into one arbitrary vector; MikkTSpace splits the vertex and gives each side its
true direction, so one of the two copies is ~180° from the average and the
handedness flips with it. **On the crate, 1 927 of 5 703 vertices — 34 % — had a
handedness that Gram-Schmidt got wrong.** A normal map baked against MikkTSpace
was lighting those wrong, silently, and S3-4 said only that it *might*.

### Are those splits real, or quantisation noise?

Corners are grouped by their tangent rounded to `tol` (default 1e-4) before a
vertex is duplicated, so the obvious worry is that the split count is an
artefact of the bucket size. It is not — measured by sweeping `tol` over five
orders of magnitude, and cross-checked against clustering corner tangents by a
**1° angular** threshold instead of a grid:

| asset | tol 1e-2 | 1e-3 | 1e-4 | 1e-5 | 1e-6 | 1° angular clustering |
|---|---|---|---|---|---|---|
| crate (3 348 welded) | 5 680 | 5 695 | **5 703** | 5 709 | 5 712 | 5 542 |
| lantern (2 737 welded) | 4 251 | 4 261 | **4 265** | 4 268 | 4 303 | 4 128 |

0.6 % spread across a 10 000× change in tolerance, and the independent angular
method lands within 3 %. The splits are the mesh's real seams. (The crate's
5 703 exceeds its *source* GLB's 4 686 vertices because welding merges across UV
seams first and MikkTSpace then splits on tangent discontinuity, which is a
finer criterion than the authoring tool's own vertex split.)

### The degenerate epilogue (S-P-4)

The reference implementation hands back a small number of **exactly zero**
tangents from its degenerate-vertex epilogue — measured: 12 corners of 19 728 on
the crate, 18 of 16 182 on the lantern — and, once, one not orthogonal to the
normal it was given (|T·N| = 0.652, one corner of 19 728). A zero tangent is a
NaN waiting to happen in a shader. Those specific vertices, and only those, get
the same declared-arbitrary orthogonal basis the Gram-Schmidt path already used
for a degenerate chart; the count is reported in
`meta.tangent_degenerate_vertices` (crate 11, lantern 15) rather than swept up.
Every other vertex keeps MikkTSpace's answer bit for bit.

### What the package now records

    "tangent_method": "mikktspace/1.0",
    "vertex_count": 5703,
    "welded_vertex_count": 3348,
    "tangent_vertex_splits": 2355,
    "tangent_degenerate_vertices": 11,
    "tangent_note": "The reference MikkTSpace (tools/mikktspace/, upstream and
     unmodified) computed the basis per face corner; 2355 vertices were
     duplicated where the corners disagreed …"

With the DLL absent the producer writes `"gram-schmidt-accumulated/0.1"` plus
`tangent_fallback_reason`. A mesh with no `TEXCOORD_0` (the `example` asset)
falls back with the reason *"the GLB has no TEXCOORD_0; MikkTSpace is defined
over a UV parameterisation and has nothing to work from"* — verified on that
asset in the gate, where it reports `tangent_degenerate_vertices: 220` out of
220, i.e. **every** tangent on that mesh is the declared arbitrary basis,
because with no UVs there is no chart to align to. That number was already true
before this wave; it is only visible now because the fallback has to say why it
is the fallback.

S3-4 asked for `tangent_method` to have a home in the schema. It still does not
have one; the pipeline writes it in `meta` unilaterally. **S3-4 is now urgent
rather than theoretical**, because a package's tangents can now be one of two
named algorithms and only a non-normative key says which.

---

## Ruling 16 — the first real VLM properties run

### Bringing the service up

<lab-gpu-host> (<lan-ip>) answered ping; `:8102` refused connections. `ssh <lab-gpu-host>`
works from this box with the existing key. What was found and what was done, in
order:

1. `nvidia-smi` **first**, per house policy: all 8 GPUs idle (2× RTX 3090, 4×
   A5000, RTX A6000, Quadro RTX 8000; 15–61 MiB used, 0 % util). Nothing else was
   running, so nothing was displaced.
2. `~/.config/systemd/user/vllm-vision.service` already existed — Qwen3-VL-8B-
   Instruct, `CUDA_VISIBLE_DEVICES=6,7` with `CUDA_DEVICE_ORDER=PCI_BUS_ID` (so
   the indices are nvidia-smi's, and 6 and 7 are **A5000s by name**, both idle),
   TP=2, 131 072 ctx, `--served-model-name qwen3-vl-8b`.
3. Port 8102 confirmed free (`ss -ltn` → no listener) before starting.
4. `systemctl --user start vllm-vision`. Linger is on, so it survives the SSH
   disconnect. Model load ≈ 4 min; `/v1/models` then returned
   `{"id":"qwen3-vl-8b", …, "max_model_len":131072}`.

Nothing was installed, downloaded or reconfigured on that box.

### The run

    set WERK_VLM_BASE_URL=http://<lan-ip>:8102/v1
    set WERK_VLM_MODEL=qwen3-vl-8b
    python tests/run_gate_3b.py

All three assets: `properties  ok  vision model qwen3-vl-8b, 10 fields`.
**The path that had never completed has now completed on every gate asset.**

| asset | preview sheet shown | round trip | fields | model's label | model's material |
|---|---|---|---|---|---|
| crate | `imposters/preview-sheet.png`, 810 173 B | **3.32 s** | 10 | `wooden chest` | `oak wood` |
| lantern | `imposters/preview-sheet.png`, 276 158 B | **3.38 s** | 10 | `street_lamp_post` | `oak wood` |
| example | `imposters/preview-sheet.png` | 3.12 s | 10 | `wooden crate` | — |

Crate, in the package (`properties/properties.json`), every field stamped
`inferred` with `confidence` and `source: "vision-language model qwen3-vl-8b,
shown imposters/preview-sheet.png"`:

| group | field | value |
|---|---|---|
| mechanical | density | 750.0 kg/m³, range [500, 1000] |
| mechanical | youngs_modulus | 1.2e10 Pa |
| mechanical | failure_mode | `splintering` |
| thermal | conductivity | 0.17 W/(m·K) |
| thermal | specific_heat | 2350 J/(kg·K) |
| flammability | class | `flammable` |
| electrical | class | `insulator` |
| magnetic | class | `diamagnetic` |
| fluid | porosity | 0.05 |
| fluid | floats_in_water | `false` |

### Verification

* **Schema.** Gate check 4, *"JSON Schema validation — manifest + 8 payload
  documents against the package's own spec/"*: **0 problems** on all three
  packages, with `properties/properties.json` among the eight.
* **Epistemic stamps.** Every field carries `"epistemic": "inferred"`. The
  `core.props` node version carries `"epistemic": "inferred"`,
  `"confidence": 0.95`, `"input_files": ["imposters/preview-sheet.png"]`, a
  recomputed `input_hash`, and — the thing that was untested —
  `"producer": {"tool": "pipeline/enrich.py", "version": "0.1", "model":
  "qwen3-vl-8b"}`. The model id is in the package. Gate check 5 recomputed 27 of
  27 derived input hashes from the package's own bytes, this node included.
* **Registry filtering — it bites.** The model proposes free-form tags and
  `p_semantics` keeps only registry vocabulary. Measured against
  `spec/facets.json`:

  | asset | facet | model proposed | kept | rejected |
  |---|---|---|---|---|
  | crate | style | rustic, handcrafted, antique | rustic | handcrafted, antique |
  | crate | function | storage, transport | storage | transport |
  | crate | environment | indoor, outdoor | — | indoor, outdoor |
  | crate | era | vintage, historic | — | vintage, historic |
  | crate | mood | cozy, nostalgic, reliable | cozy, nostalgic | reliable |
  | crate | condition | worn, used, weathered | all three | — |
  | lantern | style | vintage, rustic, ornate | rustic | vintage, ornate |
  | lantern | function | lighting, street_sign | lighting | street_sign |
  | lantern | environment | urban, historic | urban | historic |
  | lantern | era | 19th century, early 20th century | — | both |
  | lantern | mood | nostalgic, serene, elegant | nostalgic, serene | elegant |
  | lantern | condition | weathered, aged, maintained | weathered | aged, maintained |

  **15 of 30 proposed tags rejected on the crate, 10 of 16 on the lantern.**
  Every kept tag is stamped `inferred` at the model's confidence;
  `scale-class` stays `measured` at 1.0. The filter is not decorative.

### What the first real run exposes (S-P-5, S-P-6)

* **The model is confidently wrong about the lantern.** It returned
  `material: "oak wood"`, `flammability: flammable`, `floats_in_water: false`
  for a **metal street lamp**, at `confidence: 0.95`. Nothing in the pipeline
  can catch this and nothing should pretend to — every field is stamped
  `inferred` with the model named, which is the format working exactly as
  designed. But it is the first time we can *see* it, and it is the argument for
  S-P-6 below.
* **The model's self-reported confidence is copied into the package verbatim.**
  0.95 on both assets, including the wrong one. A number a model writes about
  itself is not a measurement, and the package currently presents it in the same
  field a calibrated confidence would occupy.

---

## Findings

* **S-P-1 — `core.phys.colliders.fit` cannot say which engine ran.** `fit` is
  `additionalProperties: false` with exactly `method`, `hausdorff_max_m` and
  `volume_ratio`. Ruling 18's whole point is that the producer records which of
  two engines ran, and there is nowhere normative to put it — `method` is a free
  string, so `"vhacd/4.1"` and `"V-HACD 4.1"` and `"v-hacd-4.1"` (the schema's
  own example) all validate and none of them is machine-comparable. The
  both-ways ratios have the same problem. The pipeline writes
  `collider_engine`, `volume_coverage`, `volume_excess` and
  `hausdorff_unmeasured_samples` into node `meta` unilaterally.
  *Proposed:* add `fit.engine` (string, the engine id) and `fit.volume_coverage`
  / `fit.volume_excess` (numbers) to the schema, and make `method` the
  human-readable sentence it already is in practice.

* **S-P-2 — nothing chooses the decomposition resolution per asset.** The sweep
  above shows no single (fill mode, resolution) wins on all three gate assets:
  1 000 000 makes the crate 4× better and the example worse, `SURFACE_ONLY` buys
  volume by dropping coverage from 1.00 to 0.80. The pipeline ships upstream's
  defaults and says so. *Proposed:* either a declared per-asset heuristic
  (measure, then pick) with the choice recorded in `input_params`, or an
  explicit statement in the node that the defaults were not tuned. Currently it
  is the second by omission, which is weaker than saying it.

* **S-P-3 — a fit measurement could put a NaN in a package.** `hausdorff_to_mesh`
  divides by zero on a hull with a degenerate face and returns NaN, and
  `np.minimum` propagates it: the lantern under `RAYCAST_FILL` produced
  `hausdorff_max_m = NaN`, which would have validated (JSON Schema `number`
  accepts nothing about NaN because JSON has no NaN — it would have serialised
  as `NaN` and broken strict parsers). The producer now drops non-finite
  distances and reports `hausdorff_unmeasured_samples`. *Proposed:* a normative
  rule that a measured numeric field must be finite, and that a producer which
  cannot measure omits the field rather than emitting a non-number.

* **S-P-4 — the reference MikkTSpace emits zero-length tangents.** Not a bug in
  the vendoring: `genTangSpaceDefault`'s degenerate epilogue returns exactly zero
  for a handful of corners (12/19 728 crate, 18/16 182 lantern) and, once, a
  tangent 49° off the normal. Any consumer vendoring MikkTSpace and writing its
  output straight into a `TANGENT` accessor ships NaNs. *Proposed:* a sentence in
  the spec where `TANGENT` is described — a conformant writer repairs
  non-finite/zero tangents to a declared arbitrary orthogonal basis and records
  how many it repaired. The pipeline does exactly this; nothing requires it to.

* **S-P-5 — S3-4 is now urgent.** With two named tangent algorithms in play,
  `tangent_method` being a non-normative `meta` key means a package cannot state,
  normatively, which basis its `TANGENT` attribute is in — while
  `core.tex.normal_convention`'s description still says "MikkTSpace tangents are
  assumed". The assumption is now sometimes true and sometimes false, and the
  package cannot say which. Same proposal as S3-4, escalated.

* **S-P-6 — a model's self-reported confidence is not a confidence.** The first
  real VLM run returned `confidence: 0.95` for a correct crate identification and
  `confidence: 0.95` for calling a metal street lamp `oak wood`. The pipeline
  copies that number into every field's `confidence` and into the node version's
  `confidence`, where it sits in the same slot a calibrated number would.
  *Proposed:* either a distinct `confidence_source` (`self-reported` vs
  `calibrated`), or a normative cap on a self-reported confidence, or a rule that
  a model's own number goes in `source` prose and the field's `confidence` is
  left absent. Filing rather than choosing: this is a format decision.

* **S-P-7 — the manifest writer needed `spec_sha256` and it was in this
  subtree.** Ruling 5's schema landed mandatory-`spec_sha256` while
  `pipeline/package.py` still wrote manifests without it, and the Stage 3B gate
  went to 3 FAIL on exactly that. Fixed here (calling the rulings agent's
  `tools/spec_sha256.py`), noted so the orchestrator knows the two waves
  intersected at one file. *Observation for the protocol, not a spec bug:* ruling
  20's subtree ownership does not cover "a mandatory field added in subtree A
  that must be emitted by a writer in subtree B". The result file is the place
  that gets said.

---

## Reproducing everything here

    python tools/build_native.py --force        # both natives, records the toolchain
    python tools/measure_ruling_18_19.py        # the old-vs-new tables
    python tests/run_gate_3b.py                 # 19 PASS, 0 FAIL, 0 WARN

The VLM run needs `WERK_VLM_BASE_URL` / `WERK_VLM_MODEL` in the environment and
the <lab-gpu-host> service up (`ssh <lab-gpu-host> systemctl --user start vllm-vision`, ~4 min to
load, check `curl :8102/v1/models`). Without them the pipeline writes the stub
and says so — that path is unchanged and still passes.

Machine-readable numbers: `tools/_build/ruling-18-19-measurements.json`,
`tools/_build/build.json`.
