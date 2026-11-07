# Writing a minimal valid `3d-entity/1` package

**NORMATIVE.** Ruling 3 of 2026-10-13, PROPOSED pending Gregor's ruling.
This is the writing half of `spec/SPEC.md`: everything a writer has to produce
for a package a conformant reader accepts, in the order to produce it, with a
worked example whose every hash you can reproduce.

`spec/examples/write_minimal_3d_entity.py`, which travels beside this file,
does all of it with the Python standard library and nothing else:

    python spec/examples/write_minimal_3d_entity.py <a werk package> <out.werk>
    python spec/examples/write_minimal_3d_entity.py <a werk package> <out-dir> --dir

The first argument is any werk package you hold — very likely the one this
document came out of. The script copies `spec/` and `loaders/` from it and
writes everything else from scratch, and prints the numbers quoted below. It
shares no code with any werk tool. Its output is verified by the reference
core and by all three bootstrap loaders on every gate run
(`tests/run_gate_writing.py` in the source repository).

A package is a **directory tree**, or that tree in a store-mode zip
(`SPEC.md` §1). You produce the tree; zipping it is the last step.

---

## 1. Carry the specification and the readers

Copy every file under `spec/` and under `loaders/` from a package you hold,
**byte for byte**. They are the format; you do not regenerate them and you do
not edit them. Each group is a node of your package:

* one node of type `core.spec` listing every `spec/` file;
* one node of type `core.loader` per reader (`loaders/werk_read.py`,
  `werk_read.rs`, `werk_read.c`), each with the `meta` block the package you
  copied from gives it (`language`, `form`, `entrypoint`, `toolchain`,
  `dependencies: []`, `capabilities`).

Take them from the donor's manifest at each node's **active** version: a
package that has been saved more than once also holds superseded files
(`spec/SPEC@1.md`, §9 below) which you do not need. Check each file against
the sha256 the donor declares before you copy it — a damaged specification is
worse than none.

## 2. Embed a licence and a readme

* **`LICENSE`** — the full text of the licence of *your content*, never a
  link. If the terms are not established, say exactly that in the file: an
  honest "terms not established" is conformant and an invented licence is
  not (`SPEC.md` §2, `license`). One node of type `core.license`.
* **`README.txt`** — one page for a human who opened the archive by hand. One
  node of type `core.readme`.

The licence of your content is not the licence of `spec/` and `loaders/`;
those keep the terms they had where you copied them from.

## 3. Write the payloads

The smallest thing a `3d-entity/1` package can usefully hold is one mesh. The
worked example adds one **derived** node, because a package without one never
exercises `input_hash`, and that is the construction writers get wrong.

**`geometry/triangle.glb` — a `core.geom.game` payload.** A GLB
(`MINI-SPECS.md` §10) that meets `SPEC.md` §3.10: every primitive `mode` 4
(triangles) with an `indices` accessor of component type 5123 or 5125;
`POSITION` (VEC3 f32, metres) with `min` and `max`; `NORMAL` (VEC3 f32, unit
length). Axes and units are the manifest's, not glTF's: metres, +Y up, −Z
forward, +X right, counter-clockwise front faces.

The example is one triangle with vertices (−0.5, 0, 0), (0.5, 0, 0),
(0, 1, 0) — counter-clockwise seen from +Z, so every normal is (0, 0, 1) — and
indices 0, 1, 2 as u16. Its BIN chunk is 36 bytes of positions, 36 bytes of
normals, 6 bytes of indices and 2 bytes of zero padding; its JSON chunk is the
glTF document serialised with no whitespace and padded with spaces to a
multiple of 4. **You must get:**

```
geometry/triangle.glb   776 bytes
                        sha256 babc2d4708737b7915c2bd983912a1d46e3447a0579e99d0af1476cad7549b68
```

(The hash depends on the exact JSON text, key order included; the script's
`triangle_glb()` is that text. A GLB with the same content and another key
order is equally valid and hashes differently.)

**`physics/bounds.json` — a `core.phys.bounds` payload**, valid against
`spec/schemas/core.phys.bounds.schema.json`. For this triangle the
axis-aligned box is (−0.5, 0, 0)…(0.5, 1, 0) and the smallest enclosing sphere
is the circumscribed circle: centre (0, 0.375, 0), radius 0.625, both exact.
Written as JSON with a two-space indent and one trailing newline:

```
physics/bounds.json     462 bytes
                        sha256 c9ecbdcba6339ba3fae515f7dbf9f213e51262f9e41fb6aef99abd78a6077324
```

## 4. Write the node records

Every file except `MANIFEST.json` and `SIGNATURE.json` is listed by **exactly
one node**. Nothing floats, and nothing is listed that is not there.

A **node** is

| key | value |
|---|---|
| `node_id` | lower-case kebab-case, unique in the manifest, and **stable**: it survives every later save. Never derive it from a display name or a position in a list |
| `type` | one of the `core.*` types of `SPEC.md` §3, or `x.<owner>.<name>` for your own |
| `part_id`, `material_id` | optional: the part or material of `parts[]` / `materials[]` this node belongs to |
| `versions` | an array, here of one version |
| `active` | the `v` of the version you recommend: `1` |
| `edges` | an array, possibly empty, of `{"to": <node_id>, "kind": "requires" or "enhances", "role": <kebab-case label>}` |
| `meta` | optional object; some types require keys in it (`core.loader`, `core.geom.lod`, `core.tex`) |

A **version** is

| key | value |
|---|---|
| `v` | `1` for the first. An incremental integer — never semver |
| `files` | an array of `{"path", "sha256", "size"}` and optionally `media_type` and `role`. `sha256` is 64 lower-case hex digits over the file's exact bytes; `size` is its length in bytes |
| `payload_file` | the path of THE payload among `files`, when there is more than one file (`SPEC.md` §2.1) |
| `note` | **mandatory**, at least 8 characters: one sentence saying why this version exists. "update" is not a note |
| `producer` | `{"tool": <name>, "version": <string>}`, plus `"model"` when a model produced it |
| `epistemic` | `"authored"` — a person made it. `"measured"` — computed from other files of this package and recomputable from them. `"inferred"` — a model's output |
| `created` | RFC 3339, UTC, `Z` suffix |
| `input_files`, `input_params`, `input_hash` | **mandatory when `epistemic` is `measured` or `inferred`** |

**Choosing the edge kind is choosing which side dies.** With `requires`, a
dead *target* kills the *source*; with `enhances`, a dead target costs the
source one feature. The example's bounds node `requires` the mesh — bounds of
a mesh that is gone describe nothing — and nothing requires the bounds.

**`input_hash`, exactly** (`MINI-SPECS.md` §11): take each path of
`input_files`, *in the order listed*; append that file's sha256 as **32 raw
bytes** (not 64 hex characters); then append the UTF-8 bytes of the
**canonical JSON** of `input_params` (`MINI-SPECS.md` §3: keys sorted by UTF-8
bytes, no whitespace, non-ASCII characters written as themselves) — which for
no parameters is the two bytes `{}`. The sha256 of the whole is `input_hash`.
Write `"input_params": {}` out even when it is empty.

For the example, `input_files` is `["geometry/triangle.glb"]` and
`input_params` is `{}`, so the hashed message is the 32 bytes of the GLB's
digest followed by `{}`:

```
bounds input_hash       c97e11654401f0b4fab9fec0d38bb8189ec4938b67cd4f57a60f6a1a864512c9
```

If your number matches, your digest handling and your canonical JSON are
right. If it does not: you hashed the hex string, or you forgot the `{}`.

## 5. Write `MANIFEST.json`

Valid against `spec/schemas/manifest.schema.json`, UTF-8, no BOM.

| key | value |
|---|---|
| `werk` | `{"major": 1, "minor": 0}` |
| `profile` | `"3d-entity/1"` |
| `manifest_schema` | `"spec/schemas/manifest.schema.json"` |
| `spec_sha256` | below |
| `entity` | `{"uuid", "name", "summary", "created"}`. `uuid` is a **new random** RFC 4122 UUID in lower case for a new entity, and is kept for ever after: two packages with one uuid claim to be the same entity. `name` is 1–200 characters |
| `conventions` | the twenty-one values of `SPEC.md` §2, **exactly**: every one is fixed by the profile and a reader refuses a package that declares anything else. Copy them from the package you hold, or from the script |
| `conventions_map` | `"spec/conventions-map.json"` |
| `container` | `{"form": "zip" or "directory", "zip_compression": "store", "entry_order": [...]}` (§6) |
| `license` | `{"file": "LICENSE", "sha256": <sha256 of LICENSE>}`, plus `"spdx_id"` when there is one |
| `schemas` | node type → schema path, for every type present whose payload is JSON and has a schema: here `{"core.phys.bounds": "spec/schemas/core.phys.bounds.schema.json"}`. `{}` when there is none |
| `layouts` | node type → layout path for every type present with a custom binary payload. `{}` here |
| `formats` | only when a node names a format (`SPEC.md` §3.18): format id → definition path |
| `parts` | one entry per part: `{"part_id", "name", "parent": <part_id or null>, "transform": {"translation": [x,y,z] in metres, "rotation": [w,x,y,z] a unit quaternion, "scale": [x,y,z] never zero}}` |
| `materials` | `[]`, or one entry per material |
| `primary` | which node to reach for when a consumer wants one of something: `{"mesh": "geom-game"}` |
| `nodes` | the node records |
| `generator` | `{"tool", "version"}`: what wrote this manifest |

**`spec_sha256`, exactly** (`SPEC.md` §2): take every path under `spec/` that
your manifest declares; sort the paths ascending by their UTF-8 bytes; for
each, append the path's bytes, one byte `0x0A`, that file's sha256 as 32 raw
bytes, one byte `0x0A`; `spec_sha256` is the sha256 of the result. It depends
on the `spec/` you copied, so this document cannot quote it — the script
prints it, and a full reader recomputes it and tells you if you got it wrong
(`spec-sha256-mismatch`).

Because the manifest is hashed and signed **as the bytes it is**, how you
spell the JSON is free — indentation, key order — but once written it must
not be reserialised by anything that claims to preserve it.

## 6. Make the container

Directory form: you are done; the tree is the package.

Single-file form: zip the tree (`MINI-SPECS.md` §5) with

* **method 0** (store) for every entry — do not compress;
* **UTF-8 names** with general-purpose flag bit 11 set, forward slashes, no
  leading slash, no `..`;
* **no data descriptors** (flag bit 3 clear): sizes and CRC-32 go in the
  local header;
* **no zip64**: every entry and the whole file below 4 GiB, at most 65 534
  entries. A larger package stays in directory form;
* `MANIFEST.json` as the **first** entry, then the entries matching each
  element of `container.entry_order` in turn — an element ending in `/` is a
  directory prefix, any other is an exact path, and exact paths are placed
  before prefixes are expanded — each group sorted, then anything left,
  sorted. The order is a SHOULD: a reader never depends on it, and what a
  badly ordered package loses is the cheap read of its first bytes.

The example uses

```
entry_order   MANIFEST.json  SIGNATURE.json  LICENSE  README.txt  loaders/  spec/  physics/  geometry/
```

and has no `SIGNATURE.json`, which is the legitimate state *absent*: an
anonymous package. To sign it, `SPEC.md` §6 and `MINI-SPECS.md` §12 are the
whole procedure, with a worked signature in `spec/examples/`.

## 7. Check it

With the reader you copied in step 1:

    python loaders/werk_read.py <your package> --verify --strict

Exit status 0 and `N/N files verified` means every byte is where the manifest
says, with the hash it says. For the example: **6 nodes, every one live**, and
`N` is 4 plus the number of `spec/` and `loaders/` files you copied. A full
reader additionally validates the manifest and the bounds payload against
their schemas, recomputes `spec_sha256` and `input_hash`, and reports no
error.

## 8. What "minimal" left out, and where it is

Each is optional and each is additive: textures and materials (`SPEC.md` §3,
`core.tex`, `core.material`), LODs (§4), colliders and mass properties, audio,
semantics (§3.8, the node a store indexes from), provenance, a recipe and a
disclosure for generated content (§3.11, §3.12), embedded tools (§3.17), a
foreign-encoded original (§3.18), the scene record (§3.20) and a signature
(§6). None of them changes anything above.

## 9. Saving a later version

Never rewrite: **append**. A node whose content changed gains a version
`v + 1` with its own note, producer, stamp and time, and `active` moves to
it. A node whose content did not change is left exactly as it is.

When a file's bytes change, the **new bytes take the file's plain path and
the superseded bytes move to `stem@N.ext`**, `N` being the version that
introduced them (`SPEC.md` §5): after the second save of the bounds,
`physics/bounds.json` is version 2 and `physics/bounds@1.json` is version 1,
and version 1's `files[]` entry now names the moved path — its `sha256` and
`size` do not change. A file of a multi-file version that did not change is
listed again by the new version, identically, and does not move.

Recompute `spec_sha256` only if the `spec/` files changed; recompute every
`input_hash` whose inputs changed, or the derived node is stale and a reader
will say so. If the package was signed, the old chain no longer matches the
manifest: append a chain entry over the new one (`SPEC.md` §6) — earlier
entries stay.
