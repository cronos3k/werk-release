# Stage 12B results — rulings 21 and 22, and the rebuild that follows

**Owner of this file:** the Stage 12B agent. **Subtrees owned during this
wave:** `spec/SPEC.md` (§2 license + primary), `spec/schemas/manifest*.json`,
`fixtures/` (all builders' outputs, `fixtures.json`, `FIXTURES.md`),
`pipeline/package.py` (one comment), `fixtures/build_gsplat_fixture.py`,
`adapters/blender/werk_blender/spec/` (vendored refresh),
`adapters/unreal/tests/roundtrip_gate.py` (rebaseline),
`<lab>\CUB\crates\cub-werk\tests\fixtures.rs` (re-pin). Closure notes appended to
S12-7 and S12-9 in `results/STAGE12-RESULTS.md`.

Gregor's Stage 12 rulings of 2026-08-08 (`docs/RULINGS-2026-08-08.md`,
rulings 21 and 22), implemented and re-measured. Every number below is
transcribed from one run of a committed harness on this host; interpreters
were Python 3.10.0 (numpy 1.26.4) for every builder and gate, Blender for the
crate-tex build and the Blender gate, UE 5.7 for the Unreal gate, cargo for
werk-core and cub-werk.

---

## 1. Ruling 21 — S12-9, fixture/content licensing: IGNORE, by doctrine

> "We just offer a structured canvas and the rest is up to everybody else."

The doctrine now stands in **SPEC.md §2, inside the `license` key's section**,
as the licence-side twin of §3.12's disclosure no-enforcement doctrine: the
format provides the structured place for licence facts — an embedded `LICENSE`
hashed, manifested and signed like every other file — and that is all it
provides. Filling that place truthfully is the responsibility of the author
and of the tool or export implementation that wrote the package; **the format
neither vets nor enforces content licensing.** No conformance clause turns on
what the licence text *says*: a package whose `LICENSE` honestly states that
its content's terms are not established is exactly as conformant as one under
CC0. What the format guarantees is the same thing it guarantees a disclosure —
the text cannot be swapped or stripped silently, because the manifest hashes
it and the chain signs the manifest.

The same sentence, shortened, went into both manifest schemas' `license`
descriptions (`manifest.schema.json`, `manifest.image.schema.json`), each
pointing back at SPEC §2 as the doctrine's home.

**The `gsplat-v1` fixture's LICENSE stays as shipped** — the honest
terms-not-established notice is now the doctrine's worked example rather than
an open question. S12-9 is closed in the Stage 12 findings ledger citing the
ruling.

## 2. Ruling 22 — S12-7, `primary.geometry`: implemented as proposed

* **`spec/schemas/manifest.schema.json`**: `primary` gained a `geometry`
  property — the type-agnostic slot, the `node_id` of any `core.geom.*` node.
  `mesh` is kept as the narrower existing key and still means a mesh; where a
  package's primary geometry IS a mesh and both keys appear they name the same
  node, and a reader that finds them disagreeing reports the disagreement
  rather than picking one. The image-profile schema is untouched: its
  `primary` is `{image?, thumbnail?}` and an image package has no
  `core.geom.*` node to name.
* **SPEC.md §2**: `primary` is now `{mesh?, geometry?, sound?, image?}`, with
  the S12-7 story written out — before this key existed, a splat package's
  only honest move was to omit `primary` entirely and leave the reader a
  documented mesh fallback that finds nothing.
* **`fixtures/build_gsplat_fixture.py`** sets it, and the rebuilt fixture
  carries it — read back from the shipped bytes, not from the builder:

  ```
  primary = {'geometry': 'gsplat'}
  ```

S12-7 is closed in the Stage 12 findings ledger citing the ruling.

---

## 3. The consequences drill — rebuild everything, re-run everything

The spec tree changed, so `spec_sha256` changed:
`7ea40675…` → **`331519c8d96aca0f8ea31200c68a6b28d62205f8458038a06cf2057fa5734575`**,
shared by all six Python-built fixtures (the synthetic crate carries its own,
`a595815b…`, as it always has — its vendored spec subset is a different byte
set). Vendored Blender spec refreshed first (`tools/blender/vendor_spec.py`:
**vendored 51, verified 51/51 byte-identical**), because the Blender exporter
is what builds `crate-tex-v1` and it embeds its vendored copy.

### Rebuilt fixtures (`fixtures/fixtures.json` + `FIXTURES.md` refreshed)

| fixture | bytes | sha256 |
|---|---:|---|
| `crate-v1.werk` | 13 611 141 | `d5fd9007f61872e6986b06e046057b0499d5ababa8d951f6bf42110b2679fabf` |
| `crate-v1-damaged.werk` | 13 612 293 | `f56fd0820a296d5350f9aa0fef77decc97c14424cdc4ced882ecbbe421cec3a6` |
| `crate-tex-v1.werk` | 876 621 | `8c79775ba101fbdaaac3055e57d253213af18aaae59f346fe83403279177ac7b` |
| `ista-varun-v1.werk` | 10 120 093 | `7be6a5ff5178238a378529036043b3ea9eba5b1f674f78384761775cde22e12d` |
| `humanoid-retarget-v1.werk` | 1 442 453 | `2aadd1da8571ec316116f25d985f3ce0555e1866657a5c00d61fe70f16d21b7f` |
| **`gsplat-v1.werk`** | **30 163 573** | **`04f657d0e09ba97f7c373f0c96dc167965cf3f5146835e6358db6939b3477147`** |
| `tests/fixtures/crate.werk` | 667 395 | `d58d39929e6f19e9499564c590951138f2f93d297ed047fae876759562444148` |

`gsplat-v1` grew by 4 367 bytes over Stage 12's build: the enlarged vendored
SPEC.md/schemas plus the new `primary` block. Its manifest is now 34 829 B,
sha256 `e197af7f…`, `preview_prefix_bytes` 1 160 246. One nuance stated rather than hidden: `crate-tex-v1` is
built through Blender and its manifest carries a wall-clock `created`, so its
whole-file hash changes on every rebuild by design (the builder's own
`--check-determinism` prints "DIFFERS, as expected"); the pinned bytes are the
shipped build, exactly as in Stage 12.

### Gates, all re-run fresh

| gate | command | result |
|---|---|---|
| Stage 2 | `python tests/run_gate.py` | **11 PASS, 0 FAIL, 1 SKIP** — the skip is the same pre-existing broken msys2 `gcc.EXE` on this host |
| Stage 3A | `python tests/run_gate_a.py` | **9 PASS, 0 FAIL, 0 SKIP** |
| Stage 3B | `python tests/run_gate_3b.py` | **19 PASS, 0 FAIL, 0 WARN** |
| Stage 6 | `python tests/run_gate_6.py` | **34 PASS, 0 FAIL, 0 SKIP** (30.4 s) |
| Stage 9 | `python tests/run_gate_9.py` | **15 PASS, 0 FAIL, 0 SKIP** |
| Stage 12 | `python tests/run_gate_12.py` | **18 PASS, 0 FAIL, 0 SKIP** (15.8 s) — includes the self-regeneration clause: the rebuilt package still regenerates its WKGS byte-identically from its own embedded tools |
| Stage 11 (Blender) | `python adapters/blender/test_gate.py` | **20 PASS, 0 FAIL, 0 SKIP** (6.3 s) |
| Stage 10B (Unreal, UE 5.7) | `python adapters/unreal/tests/roundtrip_gate.py` | **16 PASS, 0 FAIL** — see the rebaseline note below |
| CUB | `cargo test` in `<lab>\CUB\crates\cub-werk`, `CUB_WERK_FIXTURES=<repo>\fixtures` | **43 passed, 0 failed** (35 unit + 7 fixture integration + 1 doc) — see the re-pin note below |

### Two stale pins found and corrected, both with the same checkable cause

Stage 12 added **four files** to the vendored spec tree
(`layouts/points.layout.txt`, `layouts/gsplat.layout.txt`,
`schemas/core.tool.schema.json`, `schemas/core.tool.config.schema.json`) and
declared the UE and CUB adapters out of scope, so their gates were not re-run
in that wave. Both therefore failed here on their pins, correctly, one rebuild
late:

* **UE roundtrip gate** — first run of this wave: 12 PASS, 4 FAIL, all four
  being clause-1 import rows where **only** the files-verified count moved, by
  exactly **+4** in every row (`crate-v1` 168→172, `crate-tex-v1` 56→60,
  `ista-varun-v1` 64→68, `crate-v1-damaged` 164→168); node, imported,
  skipped, refused, asset and package counts unchanged in all four rows.
  Rebaselined in `roundtrip_gate.py` with the reason written beside the
  numbers; re-run → **16 PASS, 0 FAIL**. The texture round trip remains
  pixel-identical on all three maps of the rebuilt `crate-tex-v1`.
* **cub-werk fixture pin** — still pinned to the pre-Stage-12 build
  (13 510 877 B, `a5e110d3…`); it failed loudly with both hashes in the
  message, which is the pin doing its job. Re-pinned to this wave's build
  (13 611 141 B, `d5fd9007…`) and `files_verified` re-measured 152 → **156**
  (the same +4, same four files). All 43 tests pass.

The UE gate ran with the WerkTest editor closed (checked: no `UnrealEditor`
process before launch), against `<lab>/UnrealWerkTest/WerkTest` on
`C:/Program Files/Epic Games/UE_5.7`.

---

## 4. What moved, by path

* `spec/SPEC.md` — the licensing doctrine in §2's license section (ruling
  21); `primary` gains `geometry` with the S12-7 story (ruling 22).
* `spec/schemas/manifest.schema.json` — `primary.geometry`; doctrine sentence
  in the `license` description.
* `spec/schemas/manifest.image.schema.json` — doctrine sentence in the
  `license` description only.
* `fixtures/build_gsplat_fixture.py` — declares `primary: {geometry:
  "gsplat"}`.
* `pipeline/package.py` — the S12-7 comment updated to say the finding is
  closed; behaviour unchanged (an empty `primary` is still omitted).
* `fixtures/*.werk`, `tests/fixtures/crate.werk` + materialised `crate/` dir,
  `fixtures/fixtures.json`, `fixtures/FIXTURES.md` — the rebuild.
* `adapters/blender/werk_blender/spec/` — vendored refresh, 51/51
  byte-identical.
* `adapters/unreal/tests/roundtrip_gate.py` — clause-1 rebaseline (+4
  files-verified per row, reason stated).
* `<lab>\CUB\crates\cub-werk\tests\fixtures.rs` — pin + `files_verified`
  re-measured (CUB repository, committed there).
* `results/STAGE12-RESULTS.md` — closure notes appended to findings S12-7 and
  S12-9.

Both rulings closed. No new findings: the two pin failures were the pin
mechanism working as designed, one wave late, and each is recorded beside the
number it corrected.
