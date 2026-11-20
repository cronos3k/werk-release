# `raster-layers/1` — layered raster image documents

Status: in the release as a profile carried in its packages (SPEC §2.2). Origin: PhotoCraft
(ArtCraft suite), `werk-native` branch; copied unchanged except for the alignment edit below.

## 1. Where the definition is, and how it travels

The normative definition is the set of files under [`spec/`](spec/) in this folder. A package
of this profile carries them as files of its `core.spec` node, at the same paths, beside the
release `spec/` (which the package also carries, unchanged):

| file in the package | role |
|---|---|
| `spec/PROFILE-RASTER-LAYERS.md` | the profile narrative; manifest `profile_spec` |
| `spec/schemas/manifest.raster-layers.schema.json` | the manifest schema (a refinement of the release base schema); manifest `manifest_schema` |
| `spec/conventions-map.raster-layers.json` | manifest `conventions_map` (SPEC §10.2) |
| `spec/CRAFT-BASE.md`, `spec/NOT-CARRIED.md` | the rules every ArtCraft profile shares (revisions, paths, `@N`, epistemic stamps, format definitions) |
| `spec/schemas/core.raster.*.schema.json` | one JSON Schema per JSON payload type; manifest `schemas` |
| `spec/layouts/core.raster.surface.layout.txt`, `core.raster.lut3d.layout.txt` | byte grammars of the binary payloads; manifest `layouts` |
| `spec/layouts/x.photocraft.*.layout.txt` | extension payloads (only PhotoCraft interprets them) |
| `spec/examples/raster-layers/` | worked examples and `write_minimal.py` |
| `spec/formats/zlib-deflate.md` (from [`../_formats/`](../_formats/)) | SPEC §3.18 definition of the tile compression, with its reference tool as `core.tool` node `format-zlib-deflate-reference` (SPEC §3.17) |

`spec/SPEC.md`, `MINI-SPECS.md`, `README.md`, `layouts/ENVELOPE.layout.txt` and
`schemas/core.revisions.schema.json` are the RELEASE copies (spec digest `55882f4b…` unchanged);
the ArtCraft packages carried earlier revisions of them. Provenance of every file:
[`../VENDORED.json`](../VENDORED.json). The edits, in [`../ALIGNMENT.json`](../ALIGNMENT.json):
the `core.loader` capabilities of the manifest schema extended by `summarize-points` and
`summarize-gsplat` (which the release loaders declare), and in `HOW-TO-READ.md` (not
specification) "saved by PhotoCraft" replaced by "saved by a raster-layers/1 writer".

## 2. Node kinds (summary; `spec/PROFILE-RASTER-LAYERS.md` §3 is normative)

| type | count | payload |
|---|---|---|
| `core.raster.document` | exactly 1 (`primary.document`) | JSON: canvas, colour model, the layer tree bottom to top |
| `core.raster.layer` | 0..n | JSON: one layer (`content.kind`: raster, group, adjustment, fill, text, shape, smart; mask, blend, opacity, effects) |
| `core.raster.surface` | 0..n | envelope `WKX0`: an index file + tile files (raw, or zlib streams of `planes-delta` tiles) |
| `core.raster.lut3d` | 0..n | envelope `WKX1` |
| `core.raster.channel`, `.pattern`, `.path`, `.comp` | 0..n | JSON |
| `core.raster.text-styles`, `.variables`, `.metadata` | 0..1 | JSON |
| `core.raster.preview` | 0..2 (`primary.image`, `primary.thumbnail`) | PNG, `measured` |
| `core.raster.source`, `.source-svg`, `core.text.font` | 0..n | embedded originals, verbatim, with a format definition |
| base: `core.spec`, `core.loader`, `core.license`, `core.readme`, `core.revisions`, `core.tool` | | `spec/CRAFT-BASE.md` §1 |

Required: `primary.document`, the structure node, the base nodes. Everything else is optional.
Conventions: 33, pinned by the manifest schema (`spec/PROFILE-RASTER-LAYERS.md` §5.1).

## 3. What a reader outputs (normative for the release reference reader)

`read_raster_layers.py PACKAGE` prints one JSON object (UTF-8, keys sorted, indent 1):

* `profile`, `name`, `canvas` {`width`, `height`, `resolution_dpi`, `color_mode`, `sample_type`};
* `layers`: the tree bottom to top; per layer `id`, `name`, `kind`, `visible`, `blend`,
  `opacity`, `fill_opacity`, `clipped`, `mask` (null or {`enabled`, `density`, `feather`,
  `surface`}), `children` for a group, `adjustment` / `fill` verbatim for those kinds, and for
  every surface it names (`pixels`, `cache`, a mask's `surface`): `pixel_mode`, `channels`,
  `sample_type`, `default_pixel`, `stored_tiles` and `samples_sha256` — the sha256 of the
  surface's samples over the canvas (W × H × C × bytes per sample, little-endian, rows top to
  bottom, default pixel where no tile is stored). `--dump DIR` writes those bytes;
* `previews`: per primary slot `image` / `thumbnail`: node, PNG width, height, sha256;
* `dead` (node, why), `skipped_types`, `files_verified`, `file_failures`.

Exit 0 nothing dead; 1 something dead (listed); 2 not this profile, or the structure node is
unreadable. Not implemented by the reference reader: compositing, effects, text layout, colour
management, revisions other than the active one, recovery of the tree from a dead structure
node (it refuses instead).

## 4. The release fixture

[`../fixtures/raster-layers-v1.werk`](../fixtures/) — "Harbour at dusk", 512 × 384 px, RGB
8 bit: background (PhotoCraft's form: zlib + `planes-delta` tiles), a pass-through group
holding a lighthouse layer with a layer mask (minimal-writer form: raw tiles), a Levels
adjustment layer at 75 % opacity; composite and thumbnail previews; the reference reader as
`core.tool` node `reader-raster-layers`. Built by [`build_raster_layers.py`](build_raster_layers.py);
pins in [`../PINS.md`](../PINS.md).
