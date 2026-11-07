# spec/ — start here

This folder is the format. It travels inside every `.werk` package, and it
is written so that an isolated intelligence with **only this folder** can
answer any encoding question about the package it came in — no wiki, no
application, nothing to download. That is the manifesto's law 2 and Stage
1's acceptance gate.

## Read in this order

| # | file | what it answers |
|---|---|---|
| 0 | **Which profile is this package?** | Read `MANIFEST.json` → `profile` FIRST. `"3d-entity/1"` → row 1 below. `"image/1"` → [`PROFILE-IMAGE.md`](PROFILE-IMAGE.md) and [`schemas/manifest.image.schema.json`](schemas/manifest.image.schema.json). The manifest may also name its own schema in `manifest_schema`, and where it does, that is the authority. **Any other profile** names its schema in `manifest_schema` and its narrative in `profile_spec`, both paths inside the package: start there. What every manifest of every profile has in common is [`schemas/manifest.base.schema.json`](schemas/manifest.base.schema.json) and `SPEC.md` §2.2. |
| 1 | [`SPEC.md`](SPEC.md) | What is a werk 3D entity? What is in the container, what is in the manifest, what node families exist, how do signatures and versions work, what must a reader do? §10 is a reader checklist. **§3.11-§3.13 and §3.17 are base doctrine and apply to every profile:** `core.recipe`, `core.disclosure`, `core.embedding`, `core.tool`/`core.tool.config`. §3.15-§3.17 are Stage 12: point clouds, Gaussian splats and embedded tools. |
| 2 | [`MINI-SPECS.md`](MINI-SPECS.md) | How do I parse the boring encodings? zip, JSON, UTF-8, PNG, WAV, GLB, CRC-32, zlib framing, plus SHA-256 and Ed25519 test vectors. |
| 3 | [`schemas/manifest.schema.json`](schemas/manifest.schema.json) | The exact shape of `MANIFEST.json`, field by field, with every convention pinned to a constant. |
| 4 | [`layouts/ENVELOPE.layout.txt`](layouts/ENVELOPE.layout.txt) | How every custom binary is framed, including a complete spec of the MessagePack subset used in headers. |
| 4a | [`layouts/points.layout.txt`](layouts/points.layout.txt), [`layouts/gsplat.layout.txt`](layouts/gsplat.layout.txt) | How a point cloud and a 3D Gaussian splat are stored, including the exact INRIA-PLY mapping, the activation transforms and their inverses, and the normative splat→point-cloud degradation path. |
| 4b | [`formats/`](formats/) | How a file in any OTHER encoding is decoded: one self-contained definition document per format, with test vectors (`SPEC.md` §3.18). [`formats/splat-32.md`](formats/splat-32.md) is the one this repository's own fixtures need, and the worked example of what a definition looks like. |
| 4c | [`WRITING-3D-ENTITY.md`](WRITING-3D-ENTITY.md), [`WRITING-IMAGE.md`](WRITING-IMAGE.md) | **How do I WRITE a package?** Normative, step by step, with a worked example whose hashes you can reproduce, and a standard-library script for each in `examples/` that does it from a package you already hold. |
| 5 | [`examples/`](examples/) | The worked examples, all regenerable byte-identically from one stdlib script (`examples/make-examples.py`). A schema-valid manifest; **a real binary and an annotated byte-by-byte hex dump for every envelope magic** — `restposes.example.hex.txt` (WKRP), `gsplat.example.hex.txt` (WKGS), `embedding.example.hex.txt` (WKEM); and **`signature.example.txt`**, the signed-message construction worked end to end over the example manifest's real bytes with the published RFC 8032 test key. **Read the relevant hex dump before writing a decoder** — a grammar is not a decoder, and the gap between them is where implementations invent numbers (S-OW-3). The manifest is **abridged on purpose** — it lists five representative `spec/` files and one loader, where a real package lists every file (see its own `entity.summary`). Model structure on it; never model completeness on it. |

## Which file describes which node type

A package's `MANIFEST.json` carries `schemas` and `layouts` maps that point
at these files, so a reader never derives a path. This table is the same
information for a human.

| node type | payload | schema | layout |
|---|---|---|---|
| `core.spec` | text + JSON | — | — |
| `core.loader` | source (+ optional prebuilt) | `manifest.schema.json` → `$defs/loaderMeta` | — |
| `core.license`, `core.readme` | text | — | — |
| `core.geom.source`, `core.geom.game` | GLB | — | `MINI-SPECS.md` §10 |
| `core.geom.lod` | GLB | node `meta` in `manifest.schema.json` | `MINI-SPECS.md` §10 |
| `core.tex` | PNG | node `meta` in `manifest.schema.json` | `MINI-SPECS.md` §8 |
| `core.material` | JSON | [`core.material.schema.json`](schemas/core.material.schema.json) | — |
| `core.imposter` | PNG ×4/tier + JSON | [`core.imposter.schema.json`](schemas/core.imposter.schema.json) | [`imposter.layout.txt`](layouts/imposter.layout.txt) |
| `core.phys.colliders` | JSON | [`core.phys.colliders.schema.json`](schemas/core.phys.colliders.schema.json) | — |
| `core.phys.bounds` | JSON | [`core.phys.bounds.schema.json`](schemas/core.phys.bounds.schema.json) | — |
| `core.phys.body` | JSON | [`core.phys.body.schema.json`](schemas/core.phys.body.schema.json) | — |
| `core.field.flow` | `WKFF` binary | — | [`flowfield.layout.txt`](layouts/flowfield.layout.txt) |
| `core.pose.rest` | `WKRP` binary | — | [`restposes.layout.txt`](layouts/restposes.layout.txt) |
| `core.skeleton` | JSON (+ `WKSK` mirror) | [`core.skeleton.schema.json`](schemas/core.skeleton.schema.json) | [`skeleton.layout.txt`](layouts/skeleton.layout.txt) |
| `core.anim.clip` | `WKAC` binary + JSON | [`core.anim.clip.schema.json`](schemas/core.anim.clip.schema.json) | [`animclip.layout.txt`](layouts/animclip.layout.txt) |
| `core.audio.package` | JSON | [`core.audio.package.schema.json`](schemas/core.audio.package.schema.json) | — |
| `core.audio.effect`, `core.audio.ambience` | WAV + JSON | [`core.audio.effect.schema.json`](schemas/core.audio.effect.schema.json) | `MINI-SPECS.md` §9 |
| `core.destruct` | GLB + JSON | [`core.destruct.schema.json`](schemas/core.destruct.schema.json) | — |
| `core.props` | JSON | [`core.props.schema.json`](schemas/core.props.schema.json) | — |
| `core.semantics` | JSON | [`core.semantics.schema.json`](schemas/core.semantics.schema.json) | — |
| `core.provenance` | JSON | [`core.provenance.schema.json`](schemas/core.provenance.schema.json) | — |
| `core.recipe` † | JSON | [`core.recipe.schema.json`](schemas/core.recipe.schema.json) | — |
| `core.disclosure` † | JSON | [`core.disclosure.schema.json`](schemas/core.disclosure.schema.json) | — |
| `core.embedding` † | `WKEM` binary | — | [`embedding.layout.txt`](layouts/embedding.layout.txt) |
| `core.geom.points` | `WKPC` binary | — | [`points.layout.txt`](layouts/points.layout.txt) |
| `core.geom.gsplat` | `WKGS` binary | — | [`gsplat.layout.txt`](layouts/gsplat.layout.txt) |
| `core.tool` † | JSON + the tool's own source | [`core.tool.schema.json`](schemas/core.tool.schema.json) | — |
| `core.tool.config` † | JSON | [`core.tool.config.schema.json`](schemas/core.tool.config.schema.json) | — |
| `core.revisions` † | JSON, one record per Save | [`core.revisions.schema.json`](schemas/core.revisions.schema.json) (PROPOSED) | — |
| `core.scene` | JSON | [`core.scene.schema.json`](schemas/core.scene.schema.json) (PROPOSED) | — |
| any `core.*` type whose node names a format | the original bytes, in that format | — | the definition document `formats` names: [`formats/`](formats/) |
| `core.image.source`, `core.image.derived` ‡ | PNG (or another declared encoding) | node `meta` in `manifest.image.schema.json` | `MINI-SPECS.md` §8 |
| `x.c2pa.export` | JSON, **stub** | [`x.c2pa.export.schema.json`](schemas/x.c2pa.export.schema.json) | — |
| `x.*` | anything | supplied by the extension | supplied by the extension |
| a `core.*` type of another profile | as that profile defines | the schema `schemas` names, in the package | the grammar `layouts` names, in the package |

† **base doctrine — every profile.** ‡ profile `image/1` only.

Not node types, but validated here too:

* `MANIFEST.json`, of ANY profile → [`schemas/manifest.base.schema.json`](schemas/manifest.base.schema.json), the shape a reader holds itself, plus the profile's own schema
* `SIGNATURE.json` → [`schemas/signature.schema.json`](schemas/signature.schema.json)
* `spec/facets.json` → [`schemas/facets.schema.json`](schemas/facets.schema.json)

## The other files

* [`PROFILE-IMAGE.md`](PROFILE-IMAGE.md) — profile 2, `image/1`. The smallest
  useful werk: a source image, its derived sizes as in-file versions, a
  recipe, a disclosure, semantics, a signature chain. Same twelve laws.
* [`X-C2PA-EXPORT.md`](X-C2PA-EXPORT.md) — the intended C2PA mapping and its
  gaps in both directions. **Nothing in it is implemented or validated**, and
  it leads with a table saying so.
* [`facets.json`](facets.json) — the semantic tag registry v1. Seven facets,
  15–40 canonical kebab-case tags each, an alias map, and numeric size bands
  for `scale-class`. A tag outside the registry must start with `x.`.
* [`skeleton/canonical-humanoid-v1.json`](skeleton/canonical-humanoid-v1.json)
  — 23 bones, 1.75 m reference stature, T-pose with palms down, every rest
  rotation and translation as an exact number in both parent-local and model
  space. **Status: approved, canon 1.0** (ruled 2026-08-08; this line said
  "draft" for two months after the file it describes said otherwise).
* [`skeleton/core.hands.v1.json`](skeleton/core.hands.v1.json) — 15 bones per
  hand, attached to `l-hand`/`r-hand`. Also approved.
* [`skeleton/derive-canonical-humanoid.py`](skeleton/derive-canonical-humanoid.py)
  — how those numbers were derived. Pure stdlib, not a dependency of
  anything, and the executable statement of the quaternion convention.
* [`examples/write_minimal_3d_entity.py`](examples/write_minimal_3d_entity.py),
  [`examples/write_minimal_image.py`](examples/write_minimal_image.py) — the
  executable halves of the two writing walkthroughs. Standard library only;
  each takes a package you hold and writes a new, minimal, valid one.
* [`examples/make-examples.py`](examples/make-examples.py) — regenerates
  everything else in `examples/`. Its `mp_encode`/`mp_decode` pair is a complete
  canonical MessagePack codec for the werk subset, and `build_wkrp` is a
  complete envelope writer. When a sentence in a layout file is ambiguous,
  this code is what it means.

## The fourteen questions this folder must be able to answer alone

Kept here as a checklist, because Stage 1's gate is a measurement and not a
feeling. Each has a pointer to where the answer lives.

1. How do I open the container? → `SPEC.md` §1, `MINI-SPECS.md` §5.
2. Which byte order? → `MANIFEST.json` `conventions.endianness`, defined in
   `manifest.schema.json`; the one exception (MessagePack is big-endian
   internally) is called out in `ENVELOPE.layout.txt` §0 and §4.
3. What order are quaternion components in? → `conventions.quat_order` =
   `wxyz`, everywhere, including inside GLB-adjacent data — and glTF's own
   `xyzw` mismatch is flagged in `MINI-SPECS.md` §10.2.
4. Where does a node's payload live and how big is it? → `nodes[].versions[]
   .files[]`, with `path`, `sha256` and `size` all declared.
5. Where does a binary section start? → its `offset` in the envelope header,
   absolute, declared. Never computed from a struct.
6. Is this derived data stale? → recompute `input_hash` from `input_files`
   and compare (`MINI-SPECS.md` §11, "What gets hashed").
7. Who made this and how sure are they? → `producer` and `epistemic` on every
   version; per-value stamps inside `core.props`.
8. Is this package authentic? → `SPEC.md` §6 and `signature.schema.json`;
   three states, never two.
9. What happens when a node is corrupt or of an unknown type? → `SPEC.md` §5
   and §10 step 8: mark dead, report precisely, load everything else.
10. What is the rest pose of the canonical rig, numerically? →
    `skeleton/canonical-humanoid-v1.json`, both local and model space, with
    a stated verification tolerance.
11. Was this made by a model, and how? → `core.recipe` (`SPEC.md` §3.11,
    `schemas/core.recipe.schema.json`) for the reproduction record, and
    `core.disclosure` (§3.12) for the machine-readable facts. Read §3.12's
    doctrine before writing a viewer: the format ships facts, the viewer
    applies jurisdiction, and the format enforces nothing.
12. Which profile is this, and which schema validates its manifest? →
    `MANIFEST.json` → `profile`, and `manifest_schema` where it is present.
    See row 0 of the table at the top of this file.

13. How do I WRITE one? → `WRITING-3D-ENTITY.md`, `WRITING-IMAGE.md`, and
    the two scripts in `examples/` (`SPEC.md` §14, `PROFILE-IMAGE.md` §10).
    For a profile that is not one of the two here: the "Writing a minimal
    valid" section of the document `profile_spec` names.
14. This payload is not JSON, not a `WK…` binary and not a PNG, WAV or GLB.
    What is it? → the node's `meta.payload_format` (or
    `meta.file_formats[<role>]`) is a format id; `MANIFEST.json` → `formats`
    maps it to a definition document in `formats/`; read that
    (`SPEC.md` §3.18). No format id on the node and none of the above: the
    package does not say, and that is a defect in the package.

If you had to ask a person something this folder did not answer, that is a
spec bug. Report it; it is worth more than a patch.
