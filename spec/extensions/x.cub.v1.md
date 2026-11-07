# `x.cub.v1` — the CUB engine's cooked tier

Status: **informative addendum.** Nothing here is normative for the werk core
profile. This is what law 12's open frontier looks like when a real engine uses
it, written down so the frontier is inspectable rather than folklore.

Namespace owner: the CUB engine (`crates/cub-werk` in the CUB repository).
Profile it extends: `3d-entity/1`.
First implemented: werk Stage 5, 2026-08-08.

---

## 1. Why this exists

`SPEC.md` §8 promises this extension in one paragraph and leaves it there. This
file is that paragraph made checkable, and the reason it is worth writing down
is that `x.cub.v1` is the format's own test of law 12:

> An engine may ship its own cooked payloads (`x.cub.*`) beside the universal
> core — and every other consumer skips them gracefully, which is not a
> compromise but the system working as designed.

A cooked tier that made the core tier optional would have broken that. A cooked
tier that duplicated the core tier's *meaning* would have made the package
self-contradicting. So the design constraint is narrow and worth stating up
front: **`x.cub.v1` may carry the same geometry in a faster arrangement, plus
data the core tier has no node for. It may never be the only place a fact
lives.**

Everything below follows from that one sentence.

## 2. Node types

| type | payload | magic | layout grammar |
|---|---|---|---|
| `x.cub.v1.geom.baked` | one binary envelope | `WKX0` | `spec/layouts/x.cub.v1.baked.layout.txt` |

One node type today. The namespace is versioned in the type string itself
(`x.cub.v1.*`), not only in the envelope's `version` field, so a future
`x.cub.v2.geom.baked` is a *different node* that can coexist with this one in
the same package rather than a breaking change to this one. That is law 12
applied to the extension's own evolution.

### The magic is `WKX0`, and that is not a free choice

`ENVELOPE.layout.txt` §2 reserves `WKX0`..`WKX9` for extension binaries and
lists no mechanism for registering a bespoke four-letter magic. A distinctive
magic would have read better in a hex dump; the rule wins, and the header's
mandatory `kind` key is what actually identifies the payload:

```
kind == "x.cub.v1.geom.baked"
```

A reader MUST dispatch on `kind` and MUST NOT dispatch on the magic alone,
because `WKX0` says only "some extension's binary".

## 3. What the payload carries

The interleaved 144-byte `BakedVertex` record and a u32 index buffer, in two
declared sections. The full field table, with byte offsets, is in the layout
grammar, which travels inside every package that carries the node. Summarised:

* `position`, `normal`, `uv`, `tangent`, `material_id` — the same values the
  `core.geom.game` GLB carries, in the engine's memory order.
* `sh_r`, `sh_g`, `sh_b` — SH-L1 irradiance per vertex, in the basis order the
  manifest declares as `conventions.sh_l1_order` (`["dc","y","z","x"]`).
* `curvature`, `cavity`, `bent_normal_oct` — surface detail from the bake;
  the octahedral encoding folds about the pole `conventions.oct_encoding_pole`
  declares (`y`).
* `tex_slots_0`, `tex_slots_1` — texture-array slot indices.

The first group is duplication and the rest is not. That split is the whole
argument for the node, and §5 is about the first group specifically.

## 4. Degradation: what a reader loses by skipping it

Everything, and nothing. A consumer that does not know `x.cub.*`:

* still gets the geometry, from `core.geom.game`, which is a plain GLB;
* still gets correct bounds, materials, physics, audio and semantics;
* loses the fast load path, and loses the baked lighting fields, for which the
  core tier has no node and for which a GLB-only reader substitutes documented
  defaults (DC 0.5, cavity 1.0, zero curvature, `oct_encode(normal)`).

The edge from the cooked node to the game mesh is therefore **`enhances`**,
never `requires`. A `requires` edge would have inverted the dependency and made
a CUB-specific payload load-bearing for a universal one, which is the exact
failure law 3 exists to prevent.

The converse edge does not exist. `core.geom.game` knows nothing about the
cooked node, which is what lets a non-CUB tool strip `x/cub/` out of a package
and hand back a complete, valid werk.

## 5. Staleness, and why the duplication is safe

A cooked tier is derived data, so law 5 applies without exception: the node is
`epistemic: "measured"`, and it carries `input_files: ["geometry/game.glb"]`
and the `input_hash` defined in `MINI-SPECS.md` §11 — the 32 raw digest bytes of
each input in order, then the UTF-8 bytes of the canonical JSON of
`input_params`, which is the two bytes `{}` when there are none.

The same hash is written **twice**: once in the manifest node version, and once
in the envelope header's `input_hash` key. The two MUST agree. A consumer that
distrusts the cooked tier — which is the correct posture, per law 5's
"validates-or-recomputes rather than trusts" — recomputes the hash from the GLB
it can see and compares. If it does not match, the cooked node is stale and the
consumer falls back to the GLB. Stale derived data is detectable from the file
alone, and this is how.

That is what makes the geometry duplication safe rather than a second source of
truth: the GLB is the truth, and the cooked node carries a proof of which GLB it
was cooked from.

## 6. Struct-size refusal

`vertex_stride` is declared in the envelope header and is 144. A reader MUST
compare it against its own `BakedVertex` and MUST refuse the node when they
differ, rather than reinterpreting the bytes.

This is not defensive programming, it is law 8's corollary being taken
seriously: a cooked tier is a memory image, and a memory image whose layout is
assumed rather than declared is the single most dangerous kind of payload a
format can carry. Declaring the stride, declaring every field offset inside it,
and refusing on mismatch is what makes shipping one defensible at all.

The layout grammar's field table is duplicated into the header's `fields` key
for the same reason. When the two disagree, the header is what the bytes
actually are and the layout file is what someone meant — treat the disagreement
as damage and mark the node dead.

## 7. Conformance expectations for a package carrying `x.cub.v1`

A conformant package with this node:

1. carries `spec/layouts/x.cub.v1.baked.layout.txt` as a file of that node's
   version (SPEC §8: an `x.*` binary MUST ship its own `*.layout.txt`);
2. maps the node type to that path in the manifest's `layouts` block, so no
   reader derives the path from a filename convention;
3. also carries a live `core.geom.game` node — a package whose only geometry is
   cooked is not a conformant 3d-entity, because the universal tier is the
   constitution and this is the frontier;
4. declares `conventions.sh_l1_order` and `conventions.oct_encoding_pole`
   consistently with the envelope header's copies of both.

## 8. What is deliberately NOT in `x.cub.v1`

Recorded so the omissions read as decisions rather than gaps:

* **Per-triangle analytic shadow records (`TriShadow`).** They exist in CUB, but
  they are per-primitive rather than per-vertex and belong in a separate node
  when they land, not bolted onto this one.
* **Position-only streams for BLAS and physics.** Trivially derivable from
  section 0 by a strided read, so carrying them would be bytes that serve one
  master (law 9) and a second place for the positions to disagree.
* **Index width u16.** The tier exists for meshes whose load time anyone
  measures, and those are not the meshes that fit in u16. One width, one code
  path.
* **Compression.** Law 11 bans it in core and permits it here, and it is still
  the wrong trade: the point of the node is that loading is a `memcpy`.

## 9. Measured, Stage 5

Load time on one machine, decode only — both paths starting from a byte slice
already in RAM, so the number is parse cost and not disk cost. Full conditions
and the raw figures are in `HANDOVER.md`, "Stage 5 results".

Median of 50 iterations, release build, AMD Ryzen Threadripper 3970X.

| mesh | GLB parse | `x.cub` memcpy | speedup |
|---|---|---|---|
| `crate-v1` golden fixture, 272 verts | 0.043 ms | 0.022 ms | 1.9× |
| synthetic grid, 502 681 verts / 1 002 528 tris, 1 material | 88.95 ms | 24.00 ms | 3.7× |
| the same grid split across 3 materials | 145.51 ms | 21.69 ms | 6.7× |

The three-material row is the honest one to read carefully: the GLB path is
doing more work there because a per-material split duplicates vertices at the
seams (1 005 360 vertices against 502 681), so its slower time is partly a
different job and not only a slower one. The single-material row is the
apples-to-apples comparison, and **3.7× is the number to quote**.
