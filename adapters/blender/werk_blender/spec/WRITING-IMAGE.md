# Writing a minimal valid `image/1` package

**NORMATIVE.** Ruling 3 of 2026-10-13, PROPOSED pending Gregor's ruling.
This is the writing half of `spec/PROFILE-IMAGE.md`: everything a writer has
to produce for an image package a conformant reader accepts, in the order to
produce it, with a worked example whose every hash you can reproduce.

`spec/examples/write_minimal_image.py`, which travels beside this file, does
all of it with the Python standard library and nothing else:

    python spec/examples/write_minimal_image.py <a werk package> <out.werk>
    python spec/examples/write_minimal_image.py <a werk package> <out-dir> --dir

The first argument is any werk package you hold that carries the reference
`spec/` tree. The script copies `spec/` and `loaders/` from it, writes
everything else from scratch, and prints the numbers quoted below. It shares
no code with any werk tool. Its output is verified by the reference core and
by all three bootstrap loaders on every gate run
(`tests/run_gate_writing.py` in the source repository).

Steps 1, 2, 4, 6 and 7 are the same for every profile and are written out in
full in `spec/WRITING-3D-ENTITY.md`; this document repeats them briefly and
spends its length on what `image/1` changes.

---

## 1. Carry the specification and the readers

Copy every file under `spec/` and `loaders/` from a package you hold, byte
for byte, at the active version of its `core.spec` and `core.loader` nodes,
checking each against the hash the donor declares. One `core.spec` node; one
`core.loader` node per reader, with its `meta` block.

## 2. Embed a licence and a readme

`LICENSE` (full text of your content's licence, or an honest "terms not
established"; a `core.license` node) and `README.txt` (a `core.readme` node).

## 3. Write the payloads

**The source image — a `core.image.source` payload.** The image as the
process that made it delivered it. It is never rewritten to be more
convenient: every derived node's `input_hash` is computed against it. PNG
(`MINI-SPECS.md` §8) is this profile's boring encoding; an image in another
encoding — a JPEG, a camera raw file — is carried **as it is**, with
`meta.encoding` set to its name or to `other`, `meta.payload_format` naming
its format and the format's definition document in the package (`SPEC.md`
§3.18).

The example is an 8 × 8 RGBA picture, 8 bits per channel, sRGB, straight
alpha, top row first: at pixel (x, y), red is `36·x`, green is `36·y`, blue is
192 where `(x div 2) + (y div 2)` is even and 64 where it is odd, and alpha is
128 in the bottom-right quadrant (x ≥ 4 and y ≥ 4) and 255 elsewhere — so
every channel, the origin and the alpha mode can each be read off the
picture. It is written as a PNG of colour type 6, bit depth 8, filter type 0
on every scanline, in **one IDAT chunk whose zlib stream uses stored deflate
blocks** (`MINI-SPECS.md` §7.1): header bytes `78 01`, one stored block, the
Adler-32. No compressor is involved, so the bytes are the same on every
machine. **You must get:**

```
image/source.png        332 bytes
                        sha256 564ee5f1f8ff4190b4683e3de4ec8775966988ae8be4de3a5aee61d643090b7d
```

**The thumbnail — a `core.image.derived` payload.** Any other rendering of
those pixels: a thumbnail, a preview, a crop, a transcode. Its `meta` names
the resampling filter concretely and its version is `measured`, with the
source as its input, because a downscale genuinely is reproducible.

The example is the 4 × 4 picture in which each pixel is the mean of a 2 × 2
block of the source, per channel, on the **stored** values (no
linearisation), rounded half up: `(a + b + c + d + 2) div 4`. Written as a PNG
the same way:

```
image/thumb.png         136 bytes
                        sha256 ec2ef05cdd0cb0456eed470cecda3c0d778ca27704c26ef52a79cf33cd2e9c1c
```

Its top-left pixel is (18, 18, 192, 255) and its bottom-right pixel is
(234, 234, 192, 128).

## 4. Write the node records

As `spec/WRITING-3D-ENTITY.md` §4: every file but `MANIFEST.json` and
`SIGNATURE.json` belongs to exactly one node; a node is `node_id`, `type`,
`versions`, `active`, `edges` and optionally `meta`; a version is `v`,
`files`, `note` (mandatory, at least 8 characters), `producer`, `epistemic`,
`created`, and for a derived version `input_files`, `input_params`,
`input_hash`. An image package has no `parts` and no `part_id`.

What `image/1` requires beyond that:

* **`core.image.source` → `meta`** (`$defs/imageMeta`): `width`, `height`,
  `channels` (1–4), `bit_depth` (8 or 16), `color_space` (`srgb` or `linear`),
  `encoding` (`png`, `jpeg`, `webp`, `tiff`, `other`); optionally `has_alpha`,
  `payload_format`, `file_formats`. The example:
  `{"width": 8, "height": 8, "channels": 4, "bit_depth": 8, "color_space":
  "srgb", "encoding": "png", "has_alpha": true}`.
* **`core.image.derived` → `meta`** (`$defs/derivedImageMeta`): the same, plus
  `derived_role` (`thumbnail`, `preview`, `print`, `crop`, `transcode`,
  `other`) and `resample` — the filter, concretely: `box`, `lanczos3`,
  `bilinear`, `nearest`, `none`. The example adds
  `"derived_role": "thumbnail", "resample": "box"`.
* **The epistemic stamp, which is the thing most often got backwards.** A
  picture a person made is `authored`. A picture **a model generated is
  `inferred`**, with `producer.model`, its conditioning inputs as
  `input_files`, and normally a `core.recipe` and a `core.disclosure` beside
  it (`PROFILE-IMAGE.md` §5). A deterministic derivative of either is
  `measured`. The example's source is `authored` — the script's author
  decided every pixel — and its thumbnail is `measured`.
* **Edges.** The thumbnail `requires` the source (role `derived-from`): a
  thumbnail of a source that is gone is a picture of nothing. The source has
  no edges.

**The example's `input_hash`.** `input_files` is `["image/source.png"]` and
`input_params` is

```
{"resample": "box", "width": 4, "height": 4, "on": "stored-values", "rounding": "half-up"}
```

whose canonical JSON (`MINI-SPECS.md` §3: keys sorted, no whitespace) is the
81 bytes

```
{"height":4,"on":"stored-values","resample":"box","rounding":"half-up","width":4}
```

So the hashed message is the 32 raw bytes of the source PNG's sha256 followed
by those 81 bytes, and:

```
thumbnail input_hash    9208123a577abd68619a99ac332ccb84c3063f57e0853fc69fae090ba376edaf
```

`input_params` is where a derivative says how it was made, under the tool's
own key names; write there whatever a stranger needs to make it again.

## 5. Write `MANIFEST.json`

Valid against `spec/schemas/manifest.image.schema.json`.

| key | value |
|---|---|
| `werk` | `{"major": 1, "minor": 0}` |
| `profile` | `"image/1"` |
| `manifest_schema` | `"spec/schemas/manifest.image.schema.json"` |
| `spec_sha256` | as in `WRITING-3D-ENTITY.md` §5: over every declared `spec/` path, ascending by bytes — path, `0x0A`, the sha256 as 32 raw bytes, `0x0A` |
| `entity` | `{"uuid", "name", "summary", "created"}`; a new random uuid for a new image. A re-generation is a new entity even when the prompt was identical |
| `conventions` | the **nine** values of `PROFILE-IMAGE.md` §6, exactly: `endianness: "le"`, `color_space_default: "srgb"`, `pixel_origin: "top-left"`, `alpha_mode: "straight"`, `alignment_bytes: 16`, `text_encoding: "utf-8"`, `id_case: "kebab-case"`, `hash_algorithm: "sha256"`, `signature_algorithm: "ed25519"` |
| `conventions_map` | `"spec/conventions-map.image.json"` |
| `container` | `{"form", "zip_compression": "store", "entry_order": [...], "preview_tier": [...]}` (§6) |
| `primary` | `{"image": <the source node>, "thumbnail": <the thumbnail node>}` |
| `license` | `{"file": "LICENSE", "sha256": …}` |
| `schemas` | node type → schema path for JSON payloads present; `{}` in the example, which has none |
| `layouts` | `{}` unless the package holds an envelope binary (`core.embedding`) |
| `formats` | only when a node names a format |
| `nodes` | the node records |
| `generator` | `{"tool", "version"}` |

There is **no `parts` and no `materials` key**. They are not empty arrays in
this profile; they are absent.

## 6. Make the container

As `WRITING-3D-ENTITY.md` §6: the tree as it is, or a store-mode zip with
UTF-8 names, no data descriptors, no zip64, `MANIFEST.json` first, then
`container.entry_order`.

The example shows the one thing about order worth knowing in this profile:

```
entry_order    MANIFEST.json  SIGNATURE.json  LICENSE  README.txt  loaders/  spec/  image/thumb.png  image/
preview_tier   MANIFEST.json  SIGNATURE.json  LICENSE  README.txt  loaders/  spec/  image/thumb.png
```

`image/thumb.png` is an **exact path listed before the prefix `image/`**, and
exact paths are placed first, so the thumbnail travels in the first bytes of
the file and the full-size source does not. A store listing a hundred
thousand images shows each from a ranged read.

## 7. Check it

    python loaders/werk_read.py <your package> --verify --strict

Exit status 0 and `N/N files verified`; for the example **6 nodes, every one
live**, and `N` is 4 plus the number of `spec/` and `loaders/` files you
copied. A full reader additionally validates the manifest against its schema —
which is where a missing `resample` or a `measured` version without inputs is
caught — and recomputes `spec_sha256` and `input_hash`.

## 8. What "minimal" left out

A recipe and a disclosure for a generated image (`SPEC.md` §3.11, §3.12 — an
AI-generated image SHOULD carry both), a descriptor and palette
(`core.embedding`, `core.semantics`), provenance, more derived sizes, a
signature (`SPEC.md` §6). Saving a later version is `WRITING-3D-ENTITY.md` §9
unchanged: append a version, the new bytes keep the plain path, the
superseded bytes move to `stem@N.ext`.
