# werk Profile 2: Image — `image/1`

Status: **v0.1, authored Stage 9.** Manifest schema:
`spec/schemas/manifest.image.schema.json`. Conformance fixture:
`fixtures/ista-varun-v1.werk`.

The manifesto's twelve laws govern everything here; where this document is
silent, the laws decide, and where it and a `spec/layouts/*.layout.txt`
disagree about a byte, the layout file wins for that payload kind. Profile 1
(`spec/SPEC.md`) is not a prerequisite *except* for the sections it owns on
behalf of every profile: **§3.11 `core.recipe`, §3.12 `core.disclosure`,
§3.13 `core.embedding`, §6 signatures, §7 loaders**. Those are base doctrine
and are not restated here.

This is deliberately **the smallest werk that is still a werk**. If the
doctrine only works when there is a mesh, an audio package and a skeleton to
hang it on, it is not a doctrine.

---

## 1. Container

Identical to profile 1 §1: a directory tree, whose zipped form is the
interchange file, extension `.werk`. Store-mode by default — and the argument
is stronger here, because a PNG is already deflated and deflating the
container again spends CPU to gain nothing.

```
image.werk/
├─ MANIFEST.json        the graph, hashes, conventions, versions
├─ SIGNATURE.json       signature chain (may be absent — three-state)
├─ LICENSE              full licence text, embedded
├─ README.txt           one paragraph for a human who opened the zip by hand
├─ loaders/             single-file zero-dependency readers (SPEC.md §7)
├─ spec/                ← the format travels with the file (law 2)
├─ image/               the source image, and its derived sizes and formats
├─ recipe/              the reproduction record + prompts + INPUT MEDIA
├─ disclosure/          the machine-readable synthetic-content facts
├─ semantics/           facet tags, palette, and the embedding binary
├─ provenance/          producers, inputs, costs
└─ x/                   extension namespaces
```

**Preview-first order** (law 9): `MANIFEST.json`, `SIGNATURE.json`, `LICENSE`,
`README.txt`, `loaders/`, `spec/`, `semantics/`, `disclosure/`, **the recipe's
record and prompt files but not its embedded input media**, then the thumbnail
named by `primary.thumbnail`, then everything else.
`container.preview_prefix_bytes` is the byte offset of the end of the last of
those entries, and `container.preview_tier` **lists them explicitly** — which
is what actually decides, so this paragraph is a default and never an
authority (the S-15 rule, applied here from the start rather than
retrofitted).

Note what is inside that prefix: the disclosure and the recipe record. A store
browsing a hundred thousand images can answer *"which of these were generated,
by what model, and under what licence"* from a ranged read of the first few
hundred kilobytes of each, without ever fetching a pixel. That is law 9's
corollary doing real work, and it is the main reason `disclosure/` and the
recipe record sit where they do.

And note what is deliberately *outside* it: `recipe/inputs/`. Embedded input
media are frequently larger than the image they conditioned, and dragging a
megabyte and a half of style plate into every listing fetch would defeat the
whole point of a preview tier. This is the S-14 two-pass matching rule earning
its keep rather than being described: the recipe's exact paths are listed
*before* the `recipe/` prefix, so the record travels early and the media do
not.

## 2. MANIFEST.json

`spec/schemas/manifest.image.schema.json`, and the manifest names it in
`manifest_schema`. Differences from profile 1, all of them subtractions except
the last two:

* **No `parts[]`, no `materials[]`.** An image has no articulation and no
  material assignment. They are not "empty arrays" — they are absent, because
  a required-but-always-empty field teaches a reader to ignore a field.
* **Nine conventions instead of twenty-one** (§6). An image has no handedness,
  no up axis and no quaternions, and declaring conventions the payloads do not
  have is exactly the advisory noise law 8 exists to remove.
* **`primary` is `{image?, thumbnail?}`** and is expected rather than
  optional in practice, because in an image package "give me the one image" is
  nearly the whole interface. It is still formally optional, with a fallback
  (§3), and a reader that falls back MUST report having done so.
* **`entity` still carries a uuid.** Two hermetic copies of one image are
  recognisable as the same image; a re-generation is a different entity even
  when the prompt was identical, because it is.

Every byte except `MANIFEST.json` and `SIGNATURE.json` is reachable from
exactly one **node**'s `files[]` — the S-18 reading, which this profile's
fixture exercises on purpose (see §4).

## 3. Node families

| type | payload | where it is defined |
|---|---|---|
| `core.spec` | this folder | — |
| `core.loader` | source | `SPEC.md` §7 |
| `core.license`, `core.readme` | text | — |
| `core.image.source` | PNG (or a declared encoding) | node `meta` → `$defs/imageMeta` |
| `core.image.derived` | PNG etc. | node `meta` → `$defs/derivedImageMeta` |
| `core.recipe` | JSON + prompt files + **input media** | `SPEC.md` §3.11 |
| `core.disclosure` | JSON | `SPEC.md` §3.12 |
| `core.embedding` | `WKEM` binary | `SPEC.md` §3.13, `layouts/embedding.layout.txt` |
| `core.tool`, `core.tool.config` | JSON + the tool's own source | `SPEC.md` §3.17, `schemas/core.tool.schema.json`, `schemas/core.tool.config.schema.json` |
| `core.semantics` | JSON | `schemas/core.semantics.schema.json` |
| `core.provenance` | JSON | `schemas/core.provenance.schema.json` |
| `core.revisions` | JSON, one record per Save | `SPEC.md` §3.19, `schemas/core.revisions.schema.json` (PROPOSED 2026-10-13) |

**`core.image.source`** is the image as the producing process delivered it —
the archival anchor, the thing every derived node's `input_hash` is computed
against. It is never rewritten to be more convenient, for the same reason
`core.geom.source` is not (`SPEC.md` §3.10): rewriting it would break every
hash that points at it and the package would no longer contain the thing it
says it contains.

**An image that is not a PNG is carried as it is — ruling 1 of 2026-10-13,
PROPOSED.** `meta.encoding` has a small closed vocabulary (`png`, `jpeg`,
`webp`, `tiff`, `other`), and until that ruling a camera raw file, a HEIF or a
JPEG XL was `other` and nothing in the package said what `other` was: the
writers that hit this put the answer in a sidecar file of their own. The
binding is now a field. **`meta.payload_format`** names a **format id**; the
manifest's **`formats`** map gives the path of that format's definition
document inside the package; and the definition — normative, self-contained,
with test vectors — is what makes the payload a described one
(`SPEC.md` §3.18). `encoding` stays the quick answer for the four boring
cases and agrees with `payload_format` where both are present. The source is
still never re-encoded: the bytes the camera wrote are the bytes that travel.

**`core.image.derived`** is any other rendering of those pixels: a thumbnail,
a web preview, a crop, a transcode. Its `meta` MUST name the `resample` filter
concretely (`lanczos3`, `box`, `bilinear`, `nearest`, `none`) — not a hint,
but the difference between a reproducible derivative and a lookalike — and its
version MUST be `epistemic: "measured"` with `input_files` pointing at the
source, because a downscale genuinely is reproducible from its inputs.

**Epistemic status, the one thing most often got backwards here:** a generated
image is **`inferred`**. A model guessed it, and it is not reproducible from
its inputs. A deterministic downscale of that image is **`measured`**. If a
package says its generated source is `measured`, its recipe's reproducibility
grade and its epistemic stamp are contradicting each other and a reader should
say so.

**Fallback when `primary` is absent**, so a reader is never stuck: the image
is the `core.image.source` node — never a `core.image.derived`; the thumbnail
is the `core.image.derived` with `derived_role: "thumbnail"` and the smallest
`width`, and failing that there is no thumbnail and a reader says so rather
than substituting the full-size image into a listing.

## 4. Derived sizes as in-file versions (law 6)

Two different mechanisms exist and they are not interchangeable:

* **Different renderings are different nodes.** A 512-pixel thumbnail and a
  1024-pixel preview coexist as two `core.image.derived` nodes, because a
  consumer wants to choose between them by size.
* **Different attempts at the same rendering are versions of one node.** A
  thumbnail re-encoded because the first attempt banded, a crop redone because
  the framing was wrong: `versions[]`, append-only, one `active` pointer, and
  a mandatory work note saying why. The old version stays. Pointing back at it
  is a manifest edit, not a second file.

The fixture carries one node with two versions where **v2 relists a file v1
already listed, unchanged, with identical path, hash and size** — the case
S-18 rules on. It is there because it is the normal shape of a re-encode
(pixels changed, sidecar did not) and because a rule nothing exercises is a
rule nobody has tested.

## 5. Recipe and disclosure

Both are base doctrine — `SPEC.md` §3.11 and §3.12 — and this profile only
says where they sit and what it expects.

* An image package that was AI-generated SHOULD carry both. Neither is
  mandatory: a scanned photograph carries a recipe describing a scanner, or no
  recipe at all, and the format does not require a package to explain itself
  in order to be valid.
* `recipe/` **owns the embedded input media**. Every conditioning image,
  style plate, mask or reference sheet the generation consumed is a file in
  the recipe node's `files[]` with `role: "input-media"`, and hermeticity
  (law 1) is not satisfied by naming one it does not carry.
* The disclosure doctrine applies in full and is worth repeating because it is
  the sentence people will look for: **the format ships facts; the viewer
  applies jurisdiction; the format contains no enforcement of any kind.**

## 6. Conventions and what each governs

The `image/1` answer to `SPEC.md` §10.1's blast-radius question. Nine
conventions; look one up, refuse those node types, keep everything else.

| convention | governs | scope |
|---|---|---|
| `endianness` | every envelope binary: `core.embedding`, any `x.*` binary | node |
| `alignment_bytes` | the same set | node |
| `color_space_default` | `core.image.*` and `core.semantics` (palette) — only where the node does not declare its own `color_space`, which every conformant image node does | node |
| `pixel_origin` | `core.image.*`, and any payload indexing pixels (`core.embedding`'s descriptor grid) | node |
| `alpha_mode` | `core.image.*` where `has_alpha` is true | node |
| `text_encoding` | every text and JSON payload, **including `MANIFEST.json`** | **container** |
| `id_case` | every id in the manifest and in every payload | **container** |
| `hash_algorithm` | every `files[].sha256`, every `input_hash`, `license.sha256` | **container** |
| `signature_algorithm` | `SIGNATURE.json` only; refusing it is the `unverified` state, not damage | signature chain |

## 7. Signatures, loaders, degradation

Unchanged from profile 1, and that is the point of having a doctrine rather
than a family of formats:

* **Signature chain** — `SPEC.md` §6, `schemas/signature.schema.json`,
  Ed25519, per-entry manifest anchor, three states surfaced distinctly
  (`signed-and-valid` / `absent` / `present-and-invalid`), plus `unverified`
  for a reader that did not check. The honest limit is the same one: the chain
  has no external root of trust.
* **Embedded loaders** — `SPEC.md` §7. The three bootstrap readers in
  `loaders/` are profile-agnostic: they walk the manifest, verify hashes,
  parse envelopes and extract files, none of which needs to know what the
  payloads mean. They report an unknown profile as a note and carry on, which
  is law 3 working exactly as designed and was verified against this
  profile's fixture rather than assumed.
* **Degradation** — `SPEC.md` §5 and §10.1 unchanged. A corrupt payload kills
  one node; an unknown node type is skipped and reported; a corrupt payload
  does **not** invalidate the signature, because the chain signs the manifest
  and the per-file hash is what catches a bad byte.

## 8. Reader checklist, the delta only

`SPEC.md` §10 applies as written. The three things that differ:

1. Read `profile` before anything else. On `"image/1"`, validate against
   `manifest_schema` (or `spec/schemas/manifest.image.schema.json`), not
   against `manifest.schema.json` — whose `profile` is pinned to
   `"3d-entity/1"` and will reject this package for the right reason. The
   general procedure — the base schema a reader holds itself, the schema the
   package carries, and what validating against the latter does and does not
   establish — is `SPEC.md` §2.2 and §10.3, and it is the same for this
   profile as for one no reader has heard of.
2. There are no `parts[]` or `materials[]` to join through. Nodes reference
   each other by `edges` alone.
3. Decode order: `MANIFEST.json` → `primary.image` → that node's active
   version → **its payload file, resolved by `SPEC.md` §2.1** — which for an
   image node is its single file, so the step is free here and is written down
   anyway because it is not free everywhere. A viewer that wants nothing else
   is finished in four steps, and everything above it is enrichment.
   **`primary` names a NODE, and a node may hold several files** (this
   profile's `core.recipe` holds five). A consumer reads that version's
   optional `payload_file` and, where it is absent, applies §2.1's ordered
   rules; it MUST NOT take `files[0]`. Measured, S-OW-2: an implementer that
   took the first entry shipped a descriptor JSON where a payload was asked
   for, and reported success.

## 9. Conformance fixtures

`fixtures/ista-varun-v1.werk`, built by `fixtures/build_image_fixture.py`
from a real AI-generated image with its real recipe. It carries a
`core.recipe` graded **`descriptive`** — the model is hosted, no seed exists,
and the record says exactly which facts were never captured — a
`core.disclosure`, a `WKEM` `core.embedding`, and the style plate the
generation actually consumed, embedded by hash. It exists to close the gap
`gauntlet/RESULTS.md` declared after run 1: no fixture handed to an agent had
ever contained a custom binary, so `ENVELOPE.layout.txt` was the largest
untested surface in the spec.

`fixtures/image-cc0-v1.werk` is the publicly reproducible arm: the same node
families built from public-domain inputs by `fixtures/build_image_cc0.py`,
with a damaged sibling.

## 10. Writing a minimal valid `image/1` package (normative)

**Ruling 3 of 2026-10-13, PROPOSED.** Until this revision this document said
how to read an image package and nothing about how to write one.

**`spec/WRITING-IMAGE.md`** is the normative walkthrough: the two payloads of
the smallest useful image package — a source and a thumbnail measured from
it — the `meta` each node needs, the nine conventions, the manifest key by
key, the `input_hash` construction with its canonical parameters spelled out,
the container order that puts the thumbnail in the first bytes, and the
command that checks the result. **`spec/examples/write_minimal_image.py`**
does all of it with the Python standard library and nothing else, taking the
`spec/` and `loaders/` it must carry from a package you already hold; the
hashes the walkthrough quotes are the ones that script produces, and a gate
runs it and verifies the output with the reference core and all three
loaders.
