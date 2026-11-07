# CC0 public-domain fixtures — the publicly reproducible arm

These fixtures resolve **Finding #1** of the independent replication (issue #1/#2,
Yuvraj Puyam): the shipped gate suite depended on fixtures built from private
trees (`<lab>/splat-foley`, `<lab>/SFNovels`) and hosted downloads that 404'd, so no
outsider could run the crate gates end to end.

The answer is a two-tier model. The **golden** crate (`crate-v1.werk` + Gate A)
stays the author-lab, real-content arm. This is the **public arm**: crate
fixtures built entirely from **CC0 / public-domain** inputs, in pure Python, with
no Blender and no network — so anyone can regenerate the exact bytes and verify
them from the file alone.

## What ships

| fixture | bytes | sha256 |
|---|---|---|
| crate-cc0-lean-v1.werk | 1481529 | 299ded3d7d9f9935b4aa1611a57ce1ebe062746f03a2eccc9fc947b9620f60cc |
| crate-cc0-lean-v1-damaged.werk | 1482732 | 51752bd1b2160ea2d71e50306204850f72e6831e104be46befc0697d3913c51c |
| crate-cc0-full-v1.werk | 1535104 | 4b62cd9ab61cda099762f5b7fa6bb7b828c018e8abbb41f6e4be028e03281e31 |
| crate-cc0-full-v1-damaged.werk | 1536307 | 3ae6b6356472d92187da3e04a41bacf945baae716642e804bb1b6b2f4af07d63 |

- **Lean** (13 nodes): mesh + 3 procedural textures + material + measured bounds +
  a `core.disclosure` blob + spec/loader/license/readme/provenance. The smallest
  fixture that still exercises every crate-gate clause.
- **Full** (18 nodes): lean plus a synthetic deterministic WAV, two procedural
  evidence PNGs, `semantics` (facets validated against `spec/facets.json`) and
  `props` — structurally echoing the golden crate.
- Each damaged variant corrupts one payload (→ that node **dead** via
  hash-mismatch) and adds an unknown-type node (→ **skipped**), proving the key
  property: **corrupting a payload does not invalidate the signature** (the chain
  signs the manifest; per-file hashes catch the damage).

## Sources (all CC0 / public domain)

- Mesh: Poly Haven **Wooden Crate 01**, CC0 — `fixtures/sources/crate-cc0/`
  (`https://polyhaven.com/a/wooden_crate_01`).
- Textures: generated procedurally in stdlib (`build_crate_tex.py`'s maps) —
  CC0 by construction, every byte a pure function of a stated hash.
- Embedded LICENSE node: CC0 1.0. Poly Haven credited as a courtesy.

## How to reproduce

```
python fixtures/build_crate_cc0.py --variant lean   [--check-determinism]
python fixtures/build_crate_cc0.py --variant full   [--check-determinism]
python tests/run_gate_cc0_public.py
```

The builds are **byte-deterministic** (whole-file sha256 identical across runs —
no wall clock in any payload), so the hashes above are reproducible on any
machine with Python. No `gamedev.tech`, no private tree, no host.

## Validation

- `tests/run_gate_cc0_public.py` — **20 PASS, 0 FAIL, 0 SKIP** (release measurement, 2026-11-07): binding load
  (exact node/alive/skip counts, signed-and-valid, 0 dead), round-trip byte
  identity, `loaders/werk_read.py --verify --strict`, mesh extraction, and
  `primary.mesh` resolution; the damaged variants assert the exact dead/skipped
  report with the signature still valid.
- **Cross-vendor agent check** (the same two CLIs the round-1 cross-vendor round
  used): an isolated **Kimi Code CLI 0.15.0** agent, given only
  `crate-cc0-lean-v1.werk` and forbidden the bundled loaders, wrote its **own**
  reader — including a pure-Python RFC 8032 Ed25519 verifier that it first
  validated against the spec's published test vector — and independently reported
  `verified 69/69 files, 13 nodes, signature signed-and-valid`. (A parallel
  **Codex CLI 0.144.1** run was inconclusive: the CLI hung at startup without
  creating a session — an environment issue, not a fixture issue.)

## The other CC0 fixtures (image, splat, hardcopy)

The same pattern — CC0/synthetic source, pure-Python deterministic build,
regenerable with no host — is applied to the remaining crate-independent
fixtures, completing Finding #1.

### Image — `image-cc0-v1.werk` (+ `-damaged`)
Profile `image/1`, 11 nodes. Source: a CC0 image
(`fixtures/sources/image-cc0/`, Poly Haven), carried verbatim as `image/source`
with deterministic Lanczos-3 preview/thumbnail and a labhog style embedding.
The public-domain counterpart to the golden `ista-varun-v1.werk` (which is
model-generated and carries a recipe; this one is not — `ai_generated=false`).
Build: `python fixtures/build_image_cc0.py [--check-determinism]` (byte-exact
reproduction needs the pinned Pillow — see `fixtures/requirements-build.txt`).
Gate: `tests/run_gate_cc0_image.py` — **11 PASS** (release measurement).

| fixture | bytes | sha256 |
|---|---|---|
| image-cc0-v1.werk | 5535758 | 582489761b29f2a2f02a2539b9d642684cb94fe1e6fb89eeb9b173fb5de27358 |
| image-cc0-v1-damaged.werk | 5536807 | d841db4d83f66ac292a0da641ca27883178a5db6ed56762de35af608c8cb0fac |

### Gaussian splat — `gsplat-cc0-v1.werk` (+ `-damaged`)
Profile `3d-entity/1`, 10 nodes. Source: a **synthetic** Gaussian splat
(6000 gaussians, generated deterministically — CC0 by construction, so it sidesteps
the research-only licences on the usual 3DGS scenes), fed through the real
`pipeline/p_gsplat` + `p_pointcloud` machinery (WKGS + WKPC payloads). Build:
`python fixtures/build_gsplat_cc0.py [--check-determinism]`. Gate:
`tests/run_gate_cc0_gsplat.py` — **11 PASS** (release measurement).

| fixture | bytes | sha256 |
|---|---|---|
| gsplat-cc0-v1.werk | 1750927 | 43f9bea9a027c911e9e437d1f48c8f99d23e474d87ba1640d8855ea590947046 |
| gsplat-cc0-v1-damaged.werk | 1751977 | 44d5334d2ed5323fe66c1b92040d8dde96aa3f70f04a6136b4f900538d257832 |

### Hardcopy — already reproducible, no new file
`gauntlet/roundHC/` is self-contained: `make_smiley.py` → `build_smiley_werk.py`
→ `make_pages.py` → `degrade.py` regenerate the round from committed inputs with
no private data and no network (only Pillow + a system monospace font, both
recorded). Verified: `make_smiley.py` + `build_smiley_werk.py` reproduce
`smiley-v1.werk` byte-for-byte (sha256 `b0823016712e4770…`). The private scanned
originals are needed only for the archaeology experiment's own provenance, never
to reproduce the fixture.

All four families are byte-deterministic and each damaged variant proves a
corrupt payload goes dead by hash while the signature stays valid.
