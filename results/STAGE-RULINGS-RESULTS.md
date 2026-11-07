# Rulings wave — results (2026-08-08)

**Author:** the rulings agent. **Owned for this wave:** `spec/`, `retarget/`,
`fixtures/`, `tests/run_gate*.py`, `tests/fixture_pin.py`, the adapters'
vendored spec copies and their gate harnesses, `tools/spec_sha256.py`,
`core/src/bin/werkc.rs` (the fixture builder only), and
`<lab>\CUB\crates\cub-werk\tests\fixtures.rs`.
**Not touched:** `paper/` (Stage 8 agent), the `pipeline/` producers beyond the
one line ruling 15 forced, `HANDOVER.md` / `ROADMAP.md` until the single merge
commit at the end of this wave.

**Scope:** `docs/RULINGS-2026-08-08.md` rulings **1–6, 8–15, 20**. Rulings 16,
18 and 19 belong to another agent. Ruling 7 approved the body proportions as
drafted and needed no edit beyond ruling 8's correction; ruling 17 is "ignore
for now".

**Status: complete.** Every gate below was RUN, not recalled. One was refused
by its own safety check and says so instead of claiming a pass.

---

## 1. Per-ruling implementation status

| # | ruling | status | where |
|---|---|---|---|
| 1 | S-14 entry order is a **SHOULD** | **done** | `spec/SPEC.md` §1; `manifest.schema.json` → `container.entry_order` |
| 2 | S-15 `preview_prefix_bytes` is a **HINT** | **done** | `SPEC.md` §1; both manifest schemas |
| 3 | S-17 convention→node map, **plus the self-indexing recovery appendix** | **done** | `SPEC.md` §10.1 (marker removed), new §10.2, new **§12** (6 passes, 3 triggers); `spec/conventions-map.json`, `spec/conventions-map.image.json`, `spec/schemas/conventions-map.schema.json`; manifest key `conventions_map` |
| 4 | S-18 reword + **incremental integers** | **done** | `SPEC.md` §2 ("at least one version, exactly one active"); schema `version.v` description |
| 5 | `spec_sha256` global mandatory + per-node optional | **done** | `SPEC.md` §2 (algorithm in full); both manifest schemas (`required`); `versions[].spec_sha256` optional; `tools/spec_sha256.py` |
| 6 | S-30 `total_size_bytes` promoted into SPEC.md | **done** | `SPEC.md` §2, container bullet |
| 7 | body proportions approved as drafted | **done** | no numeric change except ruling 8 |
| 8 | S6-5 thigh 0.43 / shin 0.42 | **done** | `derive-canonical-humanoid.py`; knee y 0.50 → **0.49**, ankle unchanged |
| 9 | root is a **base bone at the origin**, pelvis parented to it | **done in substance; count conflict filed** | `SPEC.md` §3.5; `retarget/retarget.py` decision 1. See **S-R-1** |
| 10 | +Y-along-bone | **done** (already true, now approved) | canon `axis_along` |
| 11 | 8×8 is the canonical full tier | **done** | `spec/layouts/imposter.layout.txt` §4; no number changed |
| 12 | `core.retarget.bind` node type | **done, and exercised** | `spec/schemas/core.retarget.bind.schema.json`; `SPEC.md` §3.14; real node in `humanoid-retarget-v1.werk` |
| 13 | per-bone translation, incremental layout version | **done** | `animclip.layout.txt` **revision 2** (+ D-AC-6); `ENVELOPE.layout.txt` **§5a**; `core.anim.clip.schema.json` `bone_translation` |
| 14 | S10-1 `schemas` may be empty | **done** | both manifest schemas; Blender exporter workaround deleted |
| 15 | S10-3 `core.phys.body` is **model** space | **done** | schema `space` const; `SPEC.md` §3.6a; `pipeline/p_body.py` emits it |
| 20 | shared-doc serialization protocol | **done, first** | `results/README.md`; one paragraph in HANDOVER's working agreements |

### The two rulings that came back *weaker* than the draft

S-14 and S-15 were proposed as MUSTs and ruled a SHOULD and a hint. That is not
a softening to note in passing — **an implementation that hardened either one is
now stricter than the format and will reject conformant packages.** `SPEC.md`
§11 says so in the open-items list rather than leaving it to be discovered.

S-15's ruling is also the right one on the evidence: S10-2 measured that the
field is a measurement *of the container that contains it*, so writing it moves
every later entry and changes the measurement. Every writer here iterates to a
fixed point and every one converges — but a MUST a correct writer can fail for
arithmetic reasons is a MUST in the wrong place.

### Ruling 13, and why nothing broke

The version integer now declares the **minimum grammar revision needed to read
the file completely** (`ENVELOPE.layout.txt` §5a). A clip that carries no
translation section is still written as version **1**, byte-identical to what a
revision-1 writer produced — which is why every existing fixture, reader and
adapter is untouched by an extension that adds a payload section. §5a also
makes normative what was previously only implied: an unknown section is
**skipped and reported**, and a higher version integer is **never** grounds to
refuse a payload. `retarget/writers.py` was refusing on exactly that, and now
does not.

---

## 2. The gate re-run table — every number measured on 2026-08-08

| gate | command | before | **after** |
|---|---|---|---|
| Stage 2 | `python tests/run_gate.py` | 10 PASS / 0 FAIL / 1 SKIP | **11 PASS / 0 FAIL / 1 SKIP** |
| Stage 3A | `python tests/run_gate_a.py` | 7 PASS / 0 FAIL | **9 PASS / 0 FAIL** |
| Stage 3B | `py -3.10 tests/run_gate_3b.py` | 19 PASS / 0 FAIL / 0 WARN | **19 PASS / 0 FAIL / 0 WARN** |
| Stage 6 | `py -3.10 tests/run_gate_6.py` | 33 PASS / 0 FAIL / 0 SKIP (29 s) | **34 PASS / 0 FAIL / 0 SKIP (30.8 s)** |
| Stage 9 | `py -3.10 tests/run_gate_9.py` | 14 PASS / 0 FAIL | **15 PASS / 0 FAIL** |
| Blender (Stage 11) | `python adapters/blender/test_gate.py` | 16 PASS / 0 FAIL | **18 PASS / 0 FAIL (3.6 s)** |
| WerkLink standalone | `adapters\unreal\tests\.build\werk_gate.exe` | 10 PASS / 0 FAIL | **10 PASS / 0 FAIL (0.31 s)** |
| Unreal 10B roundtrip | `python adapters/unreal/tests/roundtrip_gate.py` | 16 PASS / 0 FAIL | **16 PASS / 0 FAIL** (after the WerkLink exporter was fixed and rebuilt) |
| CUB `cub-werk` | `cargo test -p cub-werk` (CUB_WERK_FIXTURES) | 35 + 7 + 1 ok | **35 + 7 + 1 ok, 0 failed** |

The counts that went **up** are the new fixture-pin clauses, one per fixture the
gate measures (Stage 3A +2, Stage 6 +1, Stage 9 +1, Blender +2, Stage 2 +1).
Every pre-existing clause passed.

**The Unreal 10B gate: refused first, then run, and it found a real gap.** Its
own first check refuses while an editor holds the assets it rewrites, and one
was running (PID 21064). The coordinator closed the editor and re-ran, which
produced **11 PASS / 5 FAIL** — four stale expectations and one genuine defect,
both now closed and the gate re-run to **16 PASS / 0 FAIL**:

* **Four stale expectations.** Every import row moved by exactly **+4 files
  verified** (crate-v1 164 -> **168**, crate-tex 52 -> **56**, ista-varun 60 ->
  **64**, damaged 160 -> **164**) and *nothing else moved* — node, imported,
  skipped, refused, asset and package counts are identical in all four rows.
  The +4 is checkable rather than accepted: the vendored `spec/` tree gained
  exactly four files (`conventions-map.json`, `conventions-map.image.json`,
  `schemas/conventions-map.schema.json`,
  `schemas/core.retarget.bind.schema.json`). Rebaselined with that reasoning
  written into the table.
* **S-R-6, a real gap I missed: the WerkLink C++ exporter was not among the
  writers I updated**, so its exported package failed jsonschema with
  `'spec_sha256' is a required property`. It is a *sixth* writer — I counted the
  four fixture builders, `werkc`, the Blender exporter and the pipeline, and did
  not think of the one that lives in another language behind a compile step.
  Implemented in `WerkLinkExport.cpp` with the canonical algorithm re-derived
  against `SPEC.md` section 2 (it cannot import `tools/spec_sha256.py`), rebuilt
  with `Build.bat WerkTestEditor Win64 Development` against the testbed project
  (UE 5.7, `Result: Succeeded`, 23 s), and verified two ways: the exported
  package declares
  `f087dbcbf6819095833847f41ccc92b1ded24a670afd1d4c6fbcbd8fc815e700` over its 46
  embedded spec files, **byte-identical to what `tools/spec_sha256.py` computes
  from the same bytes**. Three independent implementations — Python, Rust,
  C++ — now agree on one digest, which is the only kind of evidence a hash
  algorithm written down in prose can have.
  It also emits the **optional per-node-version `spec_sha256`**, the first one
  anywhere: `d7e34379...` on the `core.material` node, over the single schema
  that node conforms to, and demonstrably **not** that file own sha256
  (`487505e7...`) — the footgun SPEC section 2 warns about, now shown rather
  than asserted. And `conventions_map`, declared only because the file is
  really embedded.
* A package exported with **no** spec source directory cannot honestly declare
  the field, so the exporter warns and emits nothing rather than inventing a
  digest over an empty set. Such a package is correctly non-conformant now,
  which is the field doing its job: an export with no `spec/` was always a
  promise about other files, and it is finally visible.

**One SKIP, unchanged and honest:** `bootstrap: werk_read.c (gcc.EXE)` — the
msys2 gcc on this box exits 1 with no diagnostics. The same source compiles and
passes under MSVC in the very next clause, so it is a broken toolchain on this
host, not a source failure.

**A measurement trap worth recording:** the first run of three gates FAILED on
`schema-invalid: /spec_sha256: property not permitted`, which looks exactly like
a bad schema edit. It was a **stale `werk.dll`**: another agent's `run_gate_3b`
was holding `core/target/release/werk.dll` open, `cargo build --release` failed
with "Access is denied", and the gates went on loading the pre-ruling binary.
Confirmed by re-running with `WERK_DLL` pointed at the freshly built debug
build, which passed. Every number in the table above is from a run against a
rebuilt release DLL.

---

## 3. Stage 6 residuals — old vs new

The skeleton changed under ruling 8 (thigh 0.43 / shin 0.42, knee y 0.50 →
0.49). The prediction was that **rotations would not move and lengths would**,
and that is exactly what the re-run measured.

**Unchanged, to the last printed digit** — round trip through the real
`core.anim.clip` f32 payload:

| rig | round-trip max | rms |
|---|---|---|
| CesiumMan | 5.157e-08 rad | 1.352e-08 |
| UE mannequin | 5.217e-08 rad | 1.730e-08 |
| CMU 02_01 | 8.803e-08 rad | 1.492e-08 |

against a declared tolerance of **1.0e-4 rad**. All six cross-rig transits are
identical to the pre-ruling run in both max and rms (5.157e-08, 5.157e-08,
5.275e-08, 5.217e-08, 8.803e-08, 8.803e-08 rad). Frame-invariance is unchanged
(2.35e-06 / 3.03e-14 / 7.60e-14 rad adjacent; 0.2217 rad interposed, still
reported separately and still not averaged in).

**Changed, by ~0.1 %, and only where a length is involved:**

| quantity | old | new | Δ |
|---|---|---|---|
| CesiumMan solved scale | 1.356963 | **1.358670** | +0.13 % |
| UE solved scale | 0.990520 | **0.991813** | +0.13 % |
| CMU solved scale | 0.0615230 | **0.0616003** | +0.13 % |
| CesiumMan hips y range (m) | 0.87653 … 0.97139 | **0.87541 … 0.97038** | −1.1 mm |
| UE hips y range (m) | 0.83735 … 0.94569 | **0.83625 … 0.94473** | −1.1 mm |
| CMU hips y range (m) | 0.93436 … 1.09198 | **0.93339 … 1.09121** | −1.0 mm |
| CesiumMan calibration position rms (m) | 0.148678 | **0.148763** | +0.09 mm |
| UE calibration position rms (m) | 0.149825 | **0.149971** | +0.15 mm |
| CMU calibration position rms (m) | 0.067262 | **0.067494** | +0.23 mm |

`calibration_direction_rms_rad` and `_max_rad` did **not** move on any rig
(0.42955 / 0.42857 / 0.15896), which is the check that the change was a length
change: thigh and shin are colinear in the T-pose, so swapping their lengths
moves the knee and rotates nothing.

Every declared tolerance held with the same margins. The old file is kept as
`tests/stage6-gate-result-2026-08-08-pre-rulings.json` beside the new
`tests/stage6-gate-result.json`, so the comparison above is re-checkable rather
than transcribed.

---

## 4. Fixtures — rebuilt, and recorded in one place

| fixture | bytes | sha256 | zip entries | declared files | nodes |
|---|---:|---|---:|---:|---:|
| `fixtures/crate-v1.werk` | 13 510 877 | `a5e110d33a5acb548a4b7e0155d48de972dbfdcff8deae3ab224b12cee208925` | 170 | 168 | 36 |
| `fixtures/crate-v1-damaged.werk` | 13 512 029 | `7b28eca09c0aa17af1578f5cbf6e99e148218a8d4a71f04be7eceb4a452f0df8` | 171 | 169 | 37 |
| `fixtures/crate-tex-v1.werk` | 776 518 | `b1fa4333f0e35045deea5eb54463de9eb571e910f67a3d5babc0ebd83e0885b1` | 57 | 56 | 11 |
| `fixtures/ista-varun-v1.werk` | 10 019 649 | `a76171f1a654bb520f5397f2223899ab52c4c464479a9b05efe581f32339ffce` | 67 | 65 | 15 |
| `fixtures/humanoid-retarget-v1.werk` | 1 342 190 | `d2d7cb67ef44c1ffba5e0ad311dcd8ec7e78f7f321c4b14dfa995f00bd50f35d` | 62 | 60 | 9 |
| `tests/fixtures/crate.werk` | 626 728 | `aee365af88e8fc460b8ad5dbf5dd9503ae9acce48489a23d1212e64206c25dc3` | 37 | 35 | 15 |

All six carry `spec_sha256` **`f087dbcbf6819095833847f41ccc92b1ded24a670afd1d4c6fbcbd8fc815e700`**,
which is what the field is for: one comparison says they came from one revision
of `spec/`. Three independent routes agree on that digest — the directory tree,
the zip, and each writer's own computation.

**This table is generated, not typed.** `fixtures/fixtures.json` is the record,
`fixtures/FIXTURES.md` is rendered from it by
`python fixtures/record_fixtures.py`, and `--check` verifies without writing.

### S8-1 … S8-5 (the paper agent's findings): resolved

The cause of all five was one number transcribed into prose in several places
where the copies could not disagree loudly. Fixed structurally, not by
correcting the copies:

* **S8-1** (`crate-v1`: one size, two hashes) and **S8-4** (four recorded sizes,
  three file counts, nothing saying which build was which) → the record above,
  in one file, generated. Every gate harness now calls `tests/fixture_pin.py`
  **before it measures anything**, so a rebuild fails the gate with both hashes
  in the message. `cub-werk`'s test pins `crate-v1` the same way, in its own
  repository, with its own copy of the reason.
* **S8-2** (retarget fixture 2 bytes off its record) → rebuilt and re-measured;
  the new value is in the table and the Stage 6 numbers are re-run against it.
* **S8-3** (`ista-varun` declared 61 files, gate recorded 60) → rebuilt,
  re-measured: **65 declared files, 67 zip entries**, both counted by the same
  script that writes the record, and Stage 9 re-run against it (15 PASS).
* **S8-5** ("166 files" was a zip-entry count) → the record counts and **names
  the two separately**, and `FIXTURES.md` states why they differ by exactly two:
  `MANIFEST.json` and `SIGNATURE.json` are entries and are deliberately in no
  node's `files[]` (SPEC §2, D-MAN-1).

**The paper's numbers stay valid as history.** `paper/` cites the runs it cites,
and those runs happened. Where it quotes a fixture size or hash, that fixture
has since been rebuilt for these rulings, and the current values are the table
above. Nothing in the paper became wrong; some of it became historical, which is
what a dated measurement is.

---

## 5. Findings

**S-R-1 — ruling 9's "bone count +1" cannot be applied, because the drafted
skeleton already had the base root.** The ruling says the root is a base bone at
the origin with the pelvis parented to it, and directs a restructure with bone
count +1. The *substance* was already true of
`spec/skeleton/canonical-humanoid-v1.json` as first committed: `root` at
`(0,0,0)`, identity rotation, no parent, `role: "locomotion-root"`, with `hips`
parented to it at model y = 0.98 — and `retarget/retarget.py` decision 1 already
derived the root track from the hips and never let a mapped foreign bone drive
the root. There is therefore no 24th bone to add that has an anatomical or
functional role, and inventing one to satisfy an arithmetic instruction would
put a bone in the canon that nothing needs. **Bone count stands at 23.**
Implemented instead: the topology is now *normative rather than incidental*
(SPEC §3.5 states the rule, the three consequences and the display-stub status
of the root's 0.1 m extent), and `retarget.py`'s docstring records that what it
did by argument the canon now requires. **This is filed rather than
reinterpreted, per the rulings document's own instruction, and it is the one
item in this wave that needs Gregor's yes.** If "+1" meant something specific —
a separate pelvis bone, a floor marker — say which and it is a small change.

**S-R-2 — a mandatory manifest field breaks every writer at once, and that is
the field working.** Adding `spec_sha256` to `required` immediately failed
`werkc`'s fixture, the Blender exporter, the enrichment pipeline and four
builders. Every one was a real gap: each had been vendoring `spec/` with no
statement of which revision. Worth recording because the *next* mandatory field
will cost the same, and the cost is proportional to how many writers exist —
which is an argument for adding mandatory fields early, while there are few.

**S-R-3 — a stale locked DLL is indistinguishable from a bad schema edit.**
Three gates reported `schema-invalid: property not permitted` for the two new
manifest keys, which reads exactly like a schema mistake. The cause was
`cargo build --release` failing with "Access is denied" because another agent's
gate held `werk.dll` open, leaving the gates loading a pre-ruling binary while
printing FAIL against post-ruling packages. *Proposed:* the gate harnesses
should report the **build timestamp and sha256 of the `werk.dll` they loaded**
alongside the fixture pin they already print. A gate that pins its fixture and
not its binary is pinning half the measurement. *Filed, not implemented.*

**S-R-4 — the skeleton's `status` enum could not carry "1.0".** The brief asked
for `status: "1.0"`, and `core.skeleton.schema.json` types `status` as a
lifecycle enum (`draft` / `approved` / `deprecated`). Putting a version string
in it would make one field mean two things and break every existing validator.
Implemented as `status: "approved"` **plus** a new `canon_version: "1.0"` and an
`approval` block naming the ruling and its date — the state and the version are
separate fields on purpose. Recorded because it is a deliberate deviation from
the wording of the instruction, not an oversight.

**S-R-6 — "all the writers" is a set you cannot enumerate from one language.**
Making `spec_sha256` mandatory broke six writers; I found five by running things
and missed the sixth, the WerkLink C++ exporter, because it lives behind a
compile step in another repository's engine and its gate was refusing to run for
an unrelated reason. Two lessons worth more than the fix. First: **a
mandatory-field change is not done until every writer has been RUN**, and a gate
that refuses is not a gate that passed — the honest NOT RUN row is exactly what
made this findable instead of shippable. Second: the algorithm survived being
re-implemented from the spec text alone into a third language and produced a
byte-identical digest, which is the strongest evidence available that SPEC
section 2's wording is executable rather than merely clear. *Proposed:* SPEC
section 2 should name the writers that implement it, or better, a `tools/`
script should enumerate them, so the next mandatory field has a checklist
instead of a memory. *Filed, not implemented.*

**S-R-5 — the solver measures residuals per *correspondence*, not per bone, and
`core.retarget.bind` asks for per bone.** `bind.residuals.per_bone_direction_rad`
is keyed `"parent->child"`: it is the angle between the source segment and the
canonical segment joining those two bone heads. Attributing it to a single bone
needs a convention, so the fixture **states** one rather than assuming it — the
residual is recorded on the **child**, the bone the direction points at — and
says so in the node's own note. It keeps the interesting story readable
(`hips->l-thigh` 0.32 rad lands on `l-thigh`, the bone CMU's zero-length
`LHipJoint` sits above, which is S6-3's whole point), and 5 of 22 bound bones
are nobody's child in a measured pair and carry **no** residual rather than a
fabricated zero.

---

## 6. What a reader should check next

1. **Ruling 9 / S-R-1** needs a yes or a correction. Everything else in this
   wave is implemented and measured.
2. ~~The Unreal 10B gate needs the editor closed.~~ **Done — 16 PASS / 0 FAIL**,
   and it earned its keep: it was the only gate that caught the missing
   `spec_sha256` in the C++ exporter (S-R-6). Every gate in the table has now
   produced a number.
3. The recovery appendix (§12) is **specified and not implemented** — no reader
   in this repository rebuilds an index from container bytes yet. It is written
   as six executable passes precisely so that the first implementation is a
   transcription rather than a design exercise, but until one exists, §12 is a
   promise about behaviour rather than a measurement of it. Say so when quoting
   it.
4. `core.retarget.bind` has one real payload (the CMU bind) and no reader that
   consumes one. Same caveat, smaller surface.
