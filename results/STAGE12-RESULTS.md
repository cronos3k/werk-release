# Stage 12 results — point clouds, Gaussian splats, and embedded tools

**Owner of this file:** the Stage 12 agent. **Subtrees owned during this wave:**
`spec/layouts/points.layout.txt`, `spec/layouts/gsplat.layout.txt`,
`spec/schemas/core.tool*.schema.json`, `pipeline/ply.py`,
`pipeline/splat_to_ply.py`, `pipeline/p_gsplat.py`, `pipeline/p_pointcloud.py`,
`pipeline/p_tool.py`, `fixtures/build_gsplat_fixture.py`, `core/src/geom.rs`,
`tests/run_gate_12.py`. Edits elsewhere are listed in "What else moved".

Gregor's order, 2026-08-08: **werk must hold point clouds and Gaussian splats
as first-class node families, must record the tools used to create or convert
them AS PART OF THE DATA, and must be able to EMBED THE CODE of those tools and
their configurations in the file.** All three are implemented, and the third one
is not merely specified — the shipped fixture is regenerated, byte for byte, by
running its own embedded tools on its own embedded input, in a directory with
nothing from this repository on the path.

Every number below is transcribed from one run of a committed harness. Re-measure
rather than trust this file.

---

## 1. What was added

### Four node types, two envelope magics

| type | payload | magic | grammar / schema |
|---|---|---|---|
| `core.geom.points` | binary | **`WKPC`** (`57 4B 50 43`) | `spec/layouts/points.layout.txt` |
| `core.geom.gsplat` | binary | **`WKGS`** (`57 4B 47 53`) | `spec/layouts/gsplat.layout.txt` |
| `core.tool` | JSON + the tool's own source | — | `spec/schemas/core.tool.schema.json` |
| `core.tool.config` | JSON | — | `spec/schemas/core.tool.config.schema.json` |

Narrative spec: **SPEC.md §3.15, §3.16, §3.17**. `core.tool`/`core.tool.config`
are **base doctrine** — a tool that made an image is as much a fact about the
image as a tool that made a mesh is about the mesh — so they sit beside
`core.recipe`, `core.disclosure` and `core.embedding` rather than inside
profile 1.

### The design decisions that will be argued about

* **`WKGS` stores ACTIVATED values and says so in the file.** `scale_space` and
  `opacity_space` are both `"linear"`; the layout gives the exact `log`/`logit`
  inverse. The alternative puts `exp` and `sigmoid` into every reader in every
  language for the benefit of the one consumer in a thousand resuming training.
  **The inverse is not total and the layout says so where it bites**: `logit(0)`
  and `logit(1)` do not exist, and a fully opaque Gaussian is the commonest
  value in a trained splat. Exact `0.0`/`1.0` are therefore **legal** (D-GS-5),
  and this is measured, not hypothetical — the real 1.92 M-Gaussian scene the
  gate ingests has **721 568 opacities at exactly 1.0**.
* **SH is stored coefficient-major, transposed from the source's
  channel-major.** Evaluating spherical harmonics is a loop over coefficients
  accumulating into RGB; the transpose is paid once, by the ingester. A renderer
  written against the PLY layout and pointed at a `WKGS` without transposing
  gets plausible colours and wrong view-dependence.
* **The splat→point-cloud degradation is NORMATIVE in both directions**
  (`gsplat.layout.txt` §7). A reader that understands only positions and colours
  **MUST** be able to consume a splat by reading two of its six sections and
  skipping the other four — and it is a **conformant consumer of the node**, not
  a degraded one. A writer **SHOULD** also materialise the derived
  `core.geom.points` node so a browser can hash and cache it.
* **A point cloud's fields are DATA**, one payload section each, declared in the
  header with a `semantic` from a v1 registry plus an `x-`-prefixed escape
  hatch. `ENVELOPE.layout.txt` §5a already made unknown sections
  skip-and-report, so a reader written before a field existed handles that field
  correctly today.
* **`core.tool` extends the `core.loader` doctrine verbatim**: source always,
  prebuilt never automatically. The schema carries
  `never_auto_execute: {"const": true}` — a constant, not a switch, so a package
  cannot opt out and a consumer that never reads §7.1 still sees the rule.

### Two new OPTIONAL conventions

`sh_coeff_order` (const `"coefficient-major"`) and `sh_degree` (integer 0..3).
Both are **optional**, which is the whole point: a convention added years after
a package was written must not retroactively make that package non-conformant.
`sh_degree` is additionally **advisory** — each `WKGS` header declares the
degree that governs it, and a payload exceeding the manifest's number is a
*reported disagreement*, never a refusal. `spec/conventions-map.json` gained an
`optional` and an `advisory` flag to say both mechanically, and
`conventions-map.schema.json` defines them.

`sh_coeff_order` is deliberately **not** `sh_l1_order`: that one names a *basis*
order for an extension's per-vertex L1 irradiance, this one names the *memory*
order of a per-primitive coefficient array, and collapsing them would give one
convention two meanings (D-GS-3).

### `core.recipe` can now point INTO the file, and can describe a conversion

* `$defs/tool` gained optional **`tool_node`** and **`config_node`**: "which
  tool" is answered by a node id resolved inside this package instead of by a
  hash somebody else has to look up. Where `tool_node` and `source_file` are
  both present they MUST agree, and a reader that finds otherwise reports the
  disagreement rather than picking one.
* A step gained optional **`intermediates[]`**, and SPEC §3.17 states the rule:
  an intermediate an embedded tool reproduces from an embedded input **need not
  be carried**, provided the recipe records its `sha256`, size and the exact
  invocation. That is not a loophole — a 15 MB intermediate the file's own
  converter regenerates byte-for-byte from a 9 MB input the file carries is
  **more** verifiable than a copy, because a consumer can run the check instead
  of comparing two blobs it was handed. The gate runs it.
* `model` is no longer required on every step. See finding **S12-2**.

---

## 2. The fixture — `fixtures/gsplat-v1.werk`

**30 159 206 bytes**, sha256
`408cda84c8af8746504d91a1fbeb53dfab616173cec1809eb530419df8f1b0e3`, **77 zip
entries**, **17 nodes**, **75 declared files**, store mode, manifest 34 784 B
(sha256 `3f90d9a5…`), `spec_sha256`
`7ea40675efb7dcfa5ce19e70469d103ecd5d94c2bb0d9bdee3ce6f445192511c`,
`preview_prefix_bytes` 1 155 879 (3.83 %). Pinned in `fixtures/fixtures.json`;
built by `fixtures/build_gsplat_fixture.py`.

It is the first werk package to carry a `WKGS`, a `WKPC`, a `core.tool` or a
`core.tool.config`.

### The source, and why this one

`plush.splat` — **281 498 Gaussians**, 9 007 936 bytes, sha256
`80e0ae67…`, a **real photogrammetric capture** of a physical object, taken
from `<lab>\splat-foley\data\samples\plush.splat` where that project records its
provenance (the openly published antimatter15 splat-data demo set, converted
from published 3DGS captures).

Both real splats on this machine were examined before choosing:

| candidate | what it is | Gaussians | bytes | verdict |
|---|---|---:|---:|---|
| `data/samples/plush.splat` | a real capture of a physical object | 281 498 | 9 007 936 | **chosen** — real, small-to-medium, whole (no crop, no decimation) |
| `data/generated/marble-cellar.ply` | a genuine INRIA-convention binary PLY, a World Labs Marble generation | 1 920 000 | 107 520 363 | **not shipped** — it would be a 110 MB fixture. Used by the gate as the **ingest** test instead, so the mandatory PLY path is measured on real trainer output |

The other `outputs/*` directories in splat-foley hold renders and audio, not
splats; `data/test-torus.splat` is synthetic. Nothing was cropped or decimated
to make the fixture fit: the package carries the asset entire.

### The chain, which is the point of the fixture

```
plush.splat  --[ pipeline/splat_to_ply.py ]-->  plush.ply   (15 764 528 B)
             --[ pipeline/p_gsplat.py     ]-->  splats/plush.wkgs   (15 764 784 B)
             --[ pipeline/p_pointcloud.py ]-->  points/plush-dc.wkpc (4 223 440 B)
```

All three tools travel as `core.tool` nodes with `core.tool.config` siblings;
the source `.splat` travels in the recipe node's `files[]` (§3.11 hermeticity);
the intermediate PLY does **not** travel and its hash and invocation are
recorded instead (§3.17). `tools/` sits **inside** the preview prefix on
purpose: a ranged read of the first megabyte yields the manifest, a reader, the
spec, the semantics **and the source of every tool that made the file**.

`primary` is **omitted** rather than emitted empty — see **S12-7**.

---

## 3. Gate — `python tests/run_gate_12.py`

```
18 PASS, 0 FAIL, 0 SKIP    (15.7 s total)
STAGE 12 GATE (harness clauses): PASSED
```

| clause | measured |
|---|---|
| fixture pinned | 30 159 206 B, sha256 `408cda84…` matches `fixtures/fixtures.json` |
| fixture present | 77 zip entries, 17 nodes, profile `3d-entity/1` |
| werk-core verify | **0 errors, 0 warnings**, exit 0 |
| bootstrap `werk_read.py` | **75/75 files** over 17 resolved nodes |
| bootstrap `werk_read.rs` | 75 file checks passed, 0 failed, 0 of 17 nodes dead |
| bootstrap `werk_read.c` | 75 files PASS, 0 FAIL, 0 dead, 8 skipped |
| **gsplat reparses from declared offsets** | 281 498 Gaussians, sh_degree 0, 6 sections, **56.00 B/Gaussian** — decoded by a decoder written **in the gate file**, from the header's own offsets, never the writer's arithmetic |
| gsplat payload values, **all 281 498** | scales 6.826e-08 … 0.244545 m, **0** non-positive; **0** opacities outside [0,1]; max ‖q‖−1 **4.92e-08**; **0** with w < 0 |
| **DC-band degradation is exact** | 281 498 points recomputed from `means`+`sh-dc`: **0 position and 0 colour mismatches**, 15.00 B/point |
| **package regenerates itself from its own tools** | intermediate PLY **matches** the recipe's declared `6ffaf569…` (15 764 528 B); WKGS **byte-identical** (`b4510cb2…`) in **0.54 s**, run in a neutral directory with `PYTHONPATH` set to the extracted files alone |
| embedded tools resolve inside the file | 3 `core.tool` + 3 `core.tool.config`; every recipe step's `tool_node` and `config_node` resolves; every claimed file hash matches; every `entrypoint` agrees with its step's `source_file` |
| round trip | a fresh build is **byte-identical**: `408cda84…` = `408cda84…` |
| damaged variant | one flipped byte inside `splats/plush.wkgs` → werk-core exit 1, 1 `hash-mismatch`, **exactly 1 dead node**; both readers name the same path; **2 `enhances` edges degrade and say so**; `werk_read.py` still verifies **74/74 files over 16 of 17 nodes** |
| **INRIA PLY ingest, real trainer output** | **1 920 000 Gaussians** out of a 107 520 363 B binary PLY in **1.25 s** → a 107 521 088 B WKGS that reparses; **721 568 opacities exactly 1.0** |
| ascii PLY, sh_degree 3, xyzw reorder | 32 Gaussians × 16 coefficients: **0** SH-transpose and **0** quaternion-reorder mismatches over 1 568 values |
| fixtures.json record | 7/7 fixtures match |
| Blender vendored spec | 51/51 byte-identical |

Two clauses earn this gate's keep. The **self-regeneration** clause turns "the
file carries the code that made it" from a sentence into a byte comparison. The
**reparse** clause decodes the splat with a decoder written in the gate file, so
a broken writer cannot be agreed with by its own reader.

---

## 4. Mini-gauntlet — 1 fresh agent, the file and nothing else

The fixture was copied to a neutral directory (`<lab>\werk-gauntlet-12\`) and a
fresh agent was spawned with **only that path**: no repository, no
documentation, no internet, and an explicit instruction not to execute anything
that came out of the file.

**Outcome: SUCCESS on all three tasks, in ~25 minutes and ~20 tool calls, plus
six defect reports — four of them real, and all four are now fixed.**

### It extracted positions and colours

It wrote its own loader (stdlib + numpy, hand-rolled MessagePack subset — it
imported nothing from the package), found the store-mode zip, found the `WKGS`
envelope, read the header **big-endian inside a little-endian payload** without
being caught by it, and took **the normative two-section path of §7**:

```
TOTAL COUNT: 281498
[0] -0.06007473  1.62525749  0.93507129   ->  39 19  6
[1] -0.03502635  1.57806265  1.03217006   ->  60 30 29
[2] -0.10943363  1.61571956  1.00538695   -> 109 71 26
```

It then cross-checked against the shipped `WKPC`: positions **bit-identical**,
colours matching its own computation on **281 498 / 281 498 points, maximum
8-bit difference 0**. It independently verified every payload sha256 against
`recipe.json`, all eight tool source hashes against their `tool.json`, and the
manifest hash against `SIGNATURE.json` — and it noticed that the recipe's
`alpha_clamped_count: 33401` is exactly the number of opacities sitting on the
clamp endpoints, which it counted itself.

### It named the tools and showed their source

It identified **all three** tools with their roles and their exact locations,
and quoted `gsplat_arrays()` from `tools/werk-gsplat/ply.py` verbatim —
including the `exp`, the logistic function, the `w >= 0` canonicalisation and
the channel-major → coefficient-major transpose — plus the inverse in
`splat_to_ply.py` and the nine-line degradation in `p_pointcloud.py`. It did
not run any of it.

Its own summary of the format: *"The grammar files alone were sufficient to
write a reader from zero; I never needed outside knowledge of Gaussian
splatting, PLY, or MessagePack."*

### The six things it found, and what was done

| # | finding | disposition |
|---|---|---|
| 1 | `recipe.json` and `p_gsplat.py`'s docstring both read as if `tests/run_gate_12.py` **travels with the package**. It does not. "The reproducibility claim is therefore *asserted*, exactly what the note says it isn't." | **FIXED.** The note now says plainly that the gate lives in the source repository, that what travels is everything it needs, and that any consumer can run the same comparison with a five-line driver. |
| 2 | The byte-identity claim was **scoped inconsistently**: the recipe said "byte for byte" unqualified while the config said "on this machine" and "~1 ulp across machines". "Those cannot both be right." | **FIXED.** The recipe's note now carries the machine-scoped claim and names `exp`/`log`/logistic as the reason. |
| 3 | A **garbled sentence** in `werk-gsplat-run.config.json`: "it measures mean\|q0\| declared by the caller --". A botched interpolation, so *"the one place designed to make a weak inference visible is empty"*. | **FIXED, at the root.** `detect_gsplat` now computes the statistic **unconditionally**, even when the order is declared, and records both. The config now reads "the same pass measured mean\|q0\| 0.8647 vs mean of the other three 0.2188". |
| 4 | `README.txt` **truncated** the SH constant to `0.28209479` where the normative value is `0.28209479177387814` — harmless on this asset, but the README presents it as the formula to apply. | **FIXED.** The README now prints the constant in full, with its closed form. |
| 5 | `ENVELOPE.layout.txt` §3's worked example listed `pc-color` as `[count,4]`; the real WKPC has 3 components. Illustrative, not a conformance failure — but *"it briefly sent me looking for an alpha channel that isn't there (my first cross-check crashed on it)"*. | **FIXED.** The row is written with the symbol `C` and says why. |
| 6 | Node ids live under `node_id`, not `id`; anything walking `nodes` expecting `id` gets 17 `None`s. | **Not a defect.** `node_id` is what SPEC §2 and the schema specify and every reader in the tree uses. Recorded as a reader expectation, not a format change. |

Findings 1–3 are the valuable ones and they are all the same shape: **a
provenance format overstating what it had proved**. A cold reader caught all
three in twenty-five minutes. Its two open items are honest ones — it did not
verify Ed25519 (no library, and the dev key's own note says it is not a trust
anchor) and it could not check the intermediate PLY's hash, because doing so
requires running an embedded tool, which the exercise forbade and which the
gate does instead.

---

## 5. Gates re-run, with fresh numbers

Every spec file added or edited changes `spec_sha256`, so **all six
Python-built fixtures were rebuilt** and every affected gate re-measured.
(`fixtures/crate-tex-v1.werk` was rebuilt through Blender, as its builder
requires.)

| gate | command | result |
|---|---|---|
| Stage 2 | `python tests/run_gate.py` | **11 PASS, 0 FAIL, 1 SKIP** — the skip is the pre-existing broken msys2 `gcc.EXE` on this host, unchanged from the last recorded run |
| Stage 3A | `python tests/run_gate_a.py` | **9 PASS, 0 FAIL, 0 SKIP** |
| Stage 3B | `python tests/run_gate_3b.py` | **19 PASS, 0 FAIL, 0 WARN** |
| Stage 6 | `python tests/run_gate_6.py` | **34 PASS, 0 FAIL, 0 SKIP** (30.5 s) |
| Stage 9 | `python tests/run_gate_9.py` | **15 PASS, 0 FAIL, 0 SKIP** |
| Stage 11 (Blender) | `python adapters/blender/test_gate.py` | **20 PASS, 0 FAIL, 0 SKIP** (was 18; two new clauses) |
| Stage 12 | `python tests/run_gate_12.py` | **18 PASS, 0 FAIL, 0 SKIP** |

Stage 9 **failed once on the way**, correctly: its `builder is deterministic`
clause compares a fresh build against the shipped bytes, and the shipped image
fixture still carried the old `spec_sha256`. That is the clause doing its job,
and it is why every fixture was rebuilt rather than only the new one.

### Rebuilt fixtures

| fixture | bytes | sha256 |
|---|---:|---|
| `crate-v1.werk` | 13 606 819 | `25738d87a2bc0037db055dc30c30bb2e50604fa15f24aad324537d41b909cd0f` |
| `crate-v1-damaged.werk` | 13 607 971 | `26c141be981d800ad6181850e306308c92c49bbdc9c97343594d50e578e08a5d` |
| `crate-tex-v1.werk` | 872 299 | `4a914e31e8f5d229244592660a532ea647ed05d731efbf7e488fc8741259d1d7` |
| `ista-varun-v1.werk` | 10 115 771 | `a4c20f2ff2d32a04e26d83a480902b9080edeb4a66ab57c6fbc8566edd6bfe3d` |
| `humanoid-retarget-v1.werk` | 1 438 131 | `d9263c77bfecff70fe11a5c3abbc82a1640b4a352f5e06c46107075e433995de` |
| **`gsplat-v1.werk`** | **30 159 206** | **`408cda84c8af8746504d91a1fbeb53dfab616173cec1809eb530419df8f1b0e3`** |
| `tests/fixtures/crate.werk` | 663 073 | `848022b5c4438ef3b70ef44fb7c414926dcb6e8899e602bc72e6f153be037e1e` |

All six Python-built fixtures share `spec_sha256`
`7ea40675efb7dcfa5ce19e70469d103ecd5d94c2bb0d9bdee3ce6f445192511c`, which is
the point of the field. `crate-synthetic` carries its own, as it did before.

### The Blender adapter

`adapters/blender/werk_blender/importer.py` gained `_import_points`: every
`core.geom.points` node becomes a Blender **mesh with vertices and no faces**
plus a `werk_color` attribute on the POINT domain, and a `core.geom.gsplat`
is degraded in place **only when no points node was derived from it** — so a
conformant splat package that carries both does not put two identical
million-vertex clouds in the scene. Measured, on the real fixture, inside
Blender 4.2.1 LTS:

```
281498 points as mesh vertices (declared 281498), werk_color on the POINT
domain with 281498 entries, first vertex matches the splat's first mean
through the Y-up->Z-up swing, splat not imported twice
(points-imported, gsplat-degradation-skipped), 0 dead node(s), 2.08 s
```

`core.tool` and `core.tool.config` are declared `data-only` by the importer,
with the reason written out: *"an importer that ran an embedded tool would be
the exact thing that doctrine forbids."*

---

## 6. Findings — S12-1 … S12-9

**S12-1 — `WKEM` was in the spec, in all three bootstrap loaders, and NOT in
werk-core.** `core/src/envelope.rs::kind_for_magic` knew `WKFF`, `WKRP`, `WKAC`
and `WKSK` and not `WKEM`, so werk-core silently declined to parse the one
envelope in the `image/1` fixture — and reported nothing, because §2 says an
unrecognised magic is not damage. The omission was therefore
**indistinguishable from a package with no envelopes in it**. Found by adding
two magics beside it. *Fixed*: `WKEM`, `WKPC` and `WKGS` added; the image
fixture's `WKEM` now parses and checks with 0 errors. The general lesson is
that a table which must be edited in four files when one magic is added has no
mechanism keeping the four honest, and nothing measured the gap.

Same shape, found in the same table: **`core.retarget.bind` was missing from
`manifest.rs::KNOWN_TYPES`**, so the one package carrying a solved bind had it
skipped as an unknown type since ruling 12 shipped. *Fixed and re-measured*:
the retarget fixture now reports only its deliberate `x.werk.retarget` skip.

**S12-2 — `core.recipe` could not express a CONVERSION.** `steps[]` required a
`model` on every step, which was right while every recipe described a
generation and wrong the moment one described a conversion: a splat PLY turned
into a werk payload by a 200-line Python file has no model, no weights and no
seed, and the schema was asking a producer to invent a fact. *Fixed*: `model`
is required exactly for the roles that invoke one (`plan`, `generate`, `edit`,
`inpaint`, `upscale`, `interpolate`) and optional for `transcode`, `select`,
`other` and the two new roles `convert` and `ingest`. A `generate` step with no
model is still invalid, which is where the requirement was earning anything.

**S12-3 — the quaternion order is the one field the source does not declare,
and inference on real data can be worthless.** The INRIA reference stores `w`
first; several widely used exporters store `w` last under identical property
names; nothing in a PLY header distinguishes them. Measured:

| splat | mean absolute components | inference |
|---|---|---|
| `plush` (via the .splat converter) | 0.8647 / 0.2188 (mean of the other three) | strong, `wxyz` |
| `marble-cellar` (real trainer output, 1.92 M) | **0.4578 / 0.4627 / 0.4768 / 0.4509** | **decides nothing** |

So an ingester must either be told or must record what it guessed *and how
weakly*. `gsplat.layout.txt` §6 makes recording it mandatory, and the statistic
is now computed **unconditionally**, including when the order was declared —
that second half came directly from the mini-gauntlet, which found the field
empty on exactly the run where the order had been declared (finding 3 above).

**S12-4 — `nx/ny/nz` in a splat PLY are always exactly zero, and a reader that
trusts them renders black.** The INRIA writer reuses a point-cloud writer. Both
ingesters drop them **and report the drop with the count that triggered it**;
carrying three million zeros as "normals" would be worse than carrying nothing,
because a consumer would light with them. Recorded in the layout rather than in
a comment, because every splat reader rediscovers this.

**S12-5 — hermeticity needed a rule for INTERMEDIATES, and embedded tools are
what makes it safe.** §3.11 says a recipe that names an input it does not carry
is a promise about another file. An intermediate is a different case, and
SPEC §3.17 now states the rule: it need not be carried when an embedded
`core.tool` and an embedded input reproduce it, provided the recipe records its
hash, its size and the exact invocation. The fixture would have been **15 764 528
bytes larger** under the strict reading, to prove something the file proves by
arithmetic — and the gate performs the regeneration in 0.54 s and gets the
declared hash back.

**S12-6 — no real splat available to this lab carries SH above degree 0.** Both
the shipped fixture and the 1.92 M-Gaussian PLY store the DC band only, so
`sh-rest` is a present-and-empty section in the only real package that has one,
and the degree-1..3 index arithmetic is exercised by a **synthetic** ascii PLY
in the gate (32 Gaussians, 16 coefficients, 0 transpose mismatches over 1 440
values). That is honest coverage and it is not the same as a real degree-3
capture. *Filed, not resolved.* The cold reader independently reached the same
conclusion and put it more sharply: *"the 'hard' part is dead code on this
file."*

**S12-7 — `primary` has no slot for geometry that is not a mesh.** It offers
`mesh`, `sound` and `image`; a Gaussian splat and a point cloud are none of the
three, and SPEC §2's fallback rule ("the mesh is the `core.geom.game` node")
finds nothing in a package that has no mesh. Putting a splat in `primary.mesh`
would be calling it a mesh; emitting `primary: {}` would look declared while
declaring nothing. The fixture **omits the key**, which is legal and which
leaves a reader with the documented fallback and nothing to fall back to.
**Proposed**: a type-agnostic `primary.geometry` slot naming any `core.geom.*`
node, with `mesh` kept as the narrower existing key. *Filed for Gregor, not
implemented* — it changes what a conformant writer may emit.

> **CLOSED 2026-08-08, ruling 22 (docs/RULINGS-2026-08-08.md): apply as
> proposed.** `primary.geometry` is in `manifest.schema.json` and SPEC §2;
> the rebuilt `gsplat-v1.werk` declares `primary: {geometry: "gsplat"}`.
> Numbers for the rebuild and the gate re-runs:
> `results/STAGE12B-RESULTS.md`.

**S12-8 — this is the largest fixture in the repository by 2.2×**, at 30 159 206
bytes against `crate-v1`'s 13 606 819. Stated rather than hidden: 9.0 MB of it
is the embedded source `.splat`, 15.8 MB the WKGS, 4.2 MB the point cloud, and
~1.2 MB the spec, the loaders and the tools. A Gaussian splat is simply a large
payload, and the alternatives were all worse — cropping or decimating a real
capture would have made the fixture an asset nobody has, and dropping the
embedded source would have broken the hermeticity the whole stage is
demonstrating. The 110 MB candidate was rejected for exactly this reason and is
used as an unshipped ingest test instead.

**S12-9 — the fixture's content licence is genuinely NOT ESTABLISHED, and the
package says so.** The splat is third-party capture data from an openly
published demo set whose distribution names no author and whose terms the
sibling project records as "research/test use, check before redistribution".
The embedded `LICENSE` states all of that, states that **no licence is granted
here for the splat content**, and says the package exists as a conformance
fixture. This is the licence-unknown doctrine already written into
`pipeline/package.py` applied to a real case rather than a hypothetical one —
but it is worth Gregor's explicit attention, because every previous fixture had
terms that permitted handing the result to a stranger and this one does not.
*Filed for Gregor.* If the answer is that a conformance fixture must be
freely redistributable, the fallback is to rebuild it from
`marble-cellar.ply` — Gregor's own generation — and accept either a 110 MB
package or a declared crop.

> **CLOSED 2026-08-08, ruling 21 (docs/RULINGS-2026-08-08.md): IGNORE, by
> doctrine.** The licence status of content is the author's and their tool's
> responsibility, not the format's — "we just offer a structured canvas and
> the rest is up to everybody else." The doctrine now stands in SPEC §2's
> license section as the licence-side twin of §3.12's no-enforcement
> doctrine; the fixture's honest terms-not-established LICENSE stays as
> shipped. Details: `results/STAGE12B-RESULTS.md`.

---

## 7. What else moved

* `spec/SPEC.md` — §3.15/§3.16/§3.17, four rows in the §3 node-family table,
  three new rows and two amended rows in the §10.1 convention table, two rows
  in the §12 recovery magic table, two new §11 open items.
* `spec/layouts/ENVELOPE.layout.txt` — two magics, five worked section rows,
  the applies-to list.
* `spec/schemas/manifest.schema.json` — four node types in the enum, two
  optional conventions.
* `spec/schemas/core.recipe.schema.json` — `tool_node`, `config_node`,
  `intermediates[]`, two roles, the conditional `model` requirement.
* `spec/schemas/conventions-map.schema.json` — `optional` and `advisory`.
* `spec/conventions-map.json`, `spec/README.md` — the new types and conventions.
* `core/src/geom.rs` (new) — `gsplat.layout.txt` §8 and `points.layout.txt` §6
  executed, with the kill/warn split kept apart.
* `core/src/package.rs`, `core/src/manifest.rs`, `core/src/envelope.rs`,
  `core/src/lib.rs` — the hook, `KNOWN_TYPES`, the magics, and the fix to
  `unsupported_conventions` that made "which conventions are mandatory" read
  the schema's `required` list instead of "every key with a const".
* `loaders/werk_read.py` — the two magics, plus **`--points` and `--gsplat`**
  summary decode and two honestly-declared new capabilities,
  `summarize-points` and `summarize-gsplat`. `werk_read.rs` and `werk_read.c`
  get the magics only; reading a section table and interpreting a section's
  contents are different claims and the two smaller loaders make only the
  first.
* `pipeline/package.py` — a builder may declare its own `entry_order` /
  `preview_set` and its `conventions_map`; `primary` is omitted when empty.
* `fixtures/record_fixtures.py`, `fixtures/fixtures.json`,
  `fixtures/FIXTURES.md` — `gsplat-v1` registered; all seven re-measured.
* `adapters/blender/` — the point-cloud importer, the vendored spec (51 files,
  byte-identical), and a new gate clause.

## 8. Out of scope, declared

* **UE and CUB adapters.** Neither was touched. Mapping notes, filed as
  findings rather than code: Unreal has no first-class point-cloud or splat
  primitive in 5.7 without a plugin, so a `WKPC` maps most honestly to a
  `UStaticMesh` of points or to a Niagara data-interface array, and a `WKGS`
  needs a third-party splat plugin whose data layout would have to be recorded
  as an `x.*` extension rather than pretended into core. CUB's cooked tier
  already has position-only streams for BLAS and physics (`x.cub.v1`), which is
  exactly the shape a `WKPC` position section has, so the CUB path is a
  reinterpret rather than a conversion — but that is an inspection of the
  documents, not a measurement, and it is recorded as such.
* **LAS/LAZ ingest** for `core.geom.points`. PLY was mandatory and is done
  (ascii, binary LE, binary BE); LAS was optional. Additive when it arrives
  (law 12) and needs no format change — §3.15's `fields` mechanism was designed
  against LAS's dimension list precisely so that it would not.
* **An imposter/preview render of the splat.** The brief made it optional and
  it was skipped: splat-foley's orbit renderer would have added a dependency
  and a several-minute step to a gate that already measures the payload
  exactly.
