# werk Profile: Raster Layers — `raster-layers/1`

Status: **v1.** Manifest schema: `spec/schemas/manifest.raster-layers.schema.json`.
Conventions map: `spec/conventions-map.raster-layers.json`.

A `raster-layers/1` package is a **layered raster image document**: a canvas, a tree of
layers (pixel layers, groups, adjustment layers, fill layers, text, vector shapes, smart
objects), their masks, blend modes and layer styles, extra channels, paths, and everything
else an image editor of the Photoshop kind keeps in a document. It is the native document
format of PhotoCraft, and it is written so that someone who has **only this file** can read
every layer's exact pixels and every property — and can write such a file.

The werk manifesto's twelve laws govern everything here; where this document is silent, the
laws decide. It builds on, and does not restate:

* `spec/SPEC.md` — the container (§1), `MANIFEST.json` (§2), which file of a node is its
  payload (§2.1), the binary envelope (§3.1), versions (§5), signatures (§6), the embedded
  loaders (§7), the reader checklist and refusal scopes (§10);
* `spec/CRAFT-BASE.md` — what every ArtCraft package shares: the package root, the
  `revisions` node, path rules and the `@N` marker, epistemic stamps, signatures across
  saves, writing a package without ArtCraft software, limits;
* `spec/MINI-SPECS.md` — zip, JSON, UTF-8, SHA-256, PNG, byte by byte;
* `spec/layouts/ENVELOPE.layout.txt` — the frame of every binary file below.

If you only want the content out, start with `HOW-TO-READ.md` in the package root.

Two rules of reading this document. Every JSON payload has a JSON Schema under
`spec/schemas/` in which **every field carries a description with its unit, range and
meaning**; this document describes structure and semantics and does not repeat field lists —
the schema is normative for fields. Every binary file has a layout grammar under
`spec/layouts/`; where this document and a layout file disagree about a byte, the layout file
wins.

---

## 1. Container

Exactly `spec/SPEC.md` §1 and `spec/CRAFT-BASE.md` §1: a directory tree, or that tree as a
store-mode zip (`.werk`). The profile's own files:

```
document/document.json                 the structure node: canvas, colour, layer tree
layers/layer-<n>/layer.json            one file per layer
surfaces/<node id>/surface.wkx         a pixel surface: format, default pixel, tile index
surfaces/<node id>/tiles-<bx>-<by>.wkxz  … and its tiles: a zlib stream of a tile envelope
surfaces/<node id>/tiles-<bx>-<by>.wkx   … or the tile envelope itself (a minimal writer's form)
luts/<node id>.wkx                     a 3D colour lookup table
channels/<node id>.json                an alpha or spot channel, or the Quick Mask
patterns/<node id>.json                a pattern tile's description
paths/<node id>.json                   a saved vector path
comps/<node id>.json                   a layer comp
styles/text-styles.json                named character and paragraph styles
variables/variables.json               variables and data sets
metadata/metadata.json                 XMP, text metadata
preview/thumbnail.png                  a small picture of the document (derived)
preview/composite.png                  the flattened document (derived)
sources/<node id>/original.<ext>       an embedded original file, verbatim
x/photocraft/psd/<node id>.wkx         verbatim Photoshop blocks (extension)
x/photocraft/sources/<node id>/…       an embedded original in a format without a definition here (extension)
```

Paths are handles. Never derive meaning from a path, and never build a path yourself when
reading: every file is found through `MANIFEST.json` → node → version → `files[]`.

**Preview tier** (law 9), in physical order in the zip form: the base tier (`MANIFEST.json`,
`SIGNATURE.json`, `LICENSE`, `README.txt`, `HOW-TO-READ.md`, `loaders/`, `spec/`,
`revisions/`), then `document/document.json`, `preview/`, `layers/`. A program that has
fetched only that prefix can show the picture, the canvas size, and the name, kind, blend
mode and opacity of every layer, without fetching a pixel surface.
`container.preview_tier` lists these elements and is the authority.

## 2. MANIFEST.json

Validated by `spec/schemas/manifest.raster-layers.schema.json`, which the manifest names in
`manifest_schema`. Relative to the reference's profile 2:

* `profile` is `"raster-layers/1"`.
* `conventions` has 33 keys (§5.1), each pinned to one value.
* `primary` has three slots, each a node id:
  * `document` — REQUIRED: the one `core.raster.document` node. Its node id is `document`.
  * `image` — the flattened picture of the document (`core.raster.preview`, node id
    `composite`). Present when the writer rendered one.
  * `thumbnail` — a small picture for listings (`core.raster.preview`, node id `thumbnail`).
    Present when the writer rendered one.
  A program that wants "the picture" takes `primary.image` and reads a PNG. A program that
  wants the document takes `primary.document`.
* `entity.uuid` identifies the document and is the same in every Save of it. `entity.name`
  is a listing label; the document's real title is `name` in the structure node's payload.

## 3. Node families

| type | how many | payload | defined by |
|---|---|---|---|
| `core.spec`, `core.loader`, `core.license`, `core.readme`, `core.revisions` | base | — | `spec/CRAFT-BASE.md` §1, §3 |
| `core.raster.document` | exactly 1 | JSON | `spec/schemas/core.raster.document.schema.json` |
| `core.raster.layer` | 0 or more | JSON | `spec/schemas/core.raster.layer.schema.json` |
| `core.raster.surface` | 0 or more | envelope `WKX0`, several files | `spec/layouts/core.raster.surface.layout.txt` |
| `core.raster.lut3d` | 0 or more | envelope `WKX1` | `spec/layouts/core.raster.lut3d.layout.txt` |
| `core.raster.channel` | 0 or more | JSON | `spec/schemas/core.raster.channel.schema.json` |
| `core.raster.pattern` | 0 or more | JSON | `spec/schemas/core.raster.pattern.schema.json` |
| `core.raster.path` | 0 or more | JSON | `spec/schemas/core.raster.path.schema.json` |
| `core.raster.comp` | 0 or more | JSON | `spec/schemas/core.raster.comp.schema.json` |
| `core.raster.text-styles` | 0 or 1 | JSON | `spec/schemas/core.raster.text-styles.schema.json` |
| `core.raster.variables` | 0 or 1 | JSON | `spec/schemas/core.raster.variables.schema.json` |
| `core.raster.metadata` | 0 or 1 | JSON | `spec/schemas/core.raster.metadata.schema.json` |
| `core.raster.preview` | 0, 1 or 2 | PNG | `spec/MINI-SPECS.md` §8; node `meta` (§3.12) |
| `core.raster.source` | 0 or more | an original file, verbatim (PNG, JPEG, GIF, BMP, TIFF, WebP, PDF, a Photoshop file, a werk container, an ICC profile, an EXIF block) | §3.13; `spec/formats/<meta.payload_format>.md` |
| `core.raster.source-svg` | 0 or more | an original file that is an SVG document, verbatim: UTF-8 text | §3.13 |
| `core.text.font` | 0 or more | one font file the text is set in, verbatim (TrueType / OpenType, or a collection) | §3.13; `spec/formats/sfnt.md` |
| `core.tool` | 0 or more | the source of a format definition's reference decoder | `spec/CRAFT-BASE.md` §6.1; never run automatically |
| `x.photocraft.source.<format>` | 0 or more | an original file, verbatim | §3.13; `spec/layouts/x.photocraft.source.<format>.layout.txt` |
| `x.photocraft.psd-blocks` | 0 or more | envelope `WKX2` | `spec/layouts/x.photocraft.psd-blocks.layout.txt` |
| other `x.*` | any | anything | the extension's own layout file |

**How nodes refer to each other.** Only by node id, in JSON payload fields whose schema says
`"format": "werk-node-ref"`. Every such reference is also an edge in the manifest (below),
but the payload field is what a reader follows: edges are not versioned, payloads are.

**Strings that are not references.** Two more annotations say what a string is NOT. A field
with `"format": "werk-content-text"` holds content — a name a person typed, the text of a
text layer, a keyword from an imported file. A field with `"format": "werk-provenance-note"`
(always called `origin_note`) holds a remark about where a file once was. Neither is ever
followed, whatever it looks like: a layer may be called `D:\scans\page 1.tif` and that is its
name. A writer puts such text there verbatim; a reader never opens it.

**Node ids.** Kebab-case, stable for the life of the unit:

| unit | node id | where the number comes from |
|---|---|---|
| the structure node | `document` | fixed |
| a layer | `layer-<n>` | n is the layer's number: a positive integer without leading zeros, unique in the document, never reused, never changed by renaming, moving or re-saving |
| a layer's pixels / mask / filter mask / rendered cache / fill cache | `layer-<n>-pixels`, `-mask`, `-filter-mask`, `-cache`, `-fill-cache` | the layer |
| a video layer's frame k / original frame k | `layer-<n>-frame-<k>`, `layer-<n>-original-frame-<k>` | k is the frame number, from 0 |
| a Color Lookup table | `layer-<n>-lut` | the layer |
| a channel, and its pixels | `channel-<k>`, `channel-<k>-surface` | k is allocated when the channel is first saved |
| the Quick Mask, and its pixels | `quick-mask`, `quick-mask-surface` | fixed |
| the selection | `selection` | fixed |
| a pattern, and its pixels | `pattern-<k>`, `pattern-<k>-surface` | allocated at first save |
| a saved path | `path-<k>` | allocated at first save |
| a layer comp | `comp-<id>` (`comp-last-document-state` for the one with id 0) | the comp's own id |
| styles, variables, metadata | `text-styles`, `variables`, `metadata` | fixed |
| the previews | `thumbnail`, `composite` | fixed |
| an embedded original | `icc-profile`, `exif`, `smart-<contents id>-<format>`, `linked-<16 hex>`, `font-<16 hex>` | §3.13 |
| a decoded original | `<source node id>-decoded` | §3.13 |
| Photoshop blocks | `layer-<n>-psd`, `psd-document` | the owner |

A reader MUST NOT parse meaning out of a node id except in one place: **the number of a layer
is the decimal integer after `layer-`**. Other payloads that remember a layer which no longer
exists store that number (fields `layer_gone` / `layerGone`). A writer that invents ids may
use any kebab-case ids it likes for everything except layers.

### 3.1 `core.raster.document` — the structure node

One file, `document/document.json`. It holds what belongs to no single unit: the canvas
(`width`, `height` in pixels, `resolution_dpi`), the colour model and depth of the document,
the **layer tree**, the lists of channels, patterns, paths and comps by node id, and the
document-level settings (guides, global light, colour table, duotone inks, measurement
marks, notes, slices, timeline). It carries none of their content.

**The layer tree.** `layers` is an array of entries `{"layer": "<node id>"}` from the BOTTOM
layer to the TOP layer: entry 0 is drawn first and everything after it is drawn over it. An
entry whose layer is a group has `"children"`: the group's own layers, again bottom to top
(an empty array for an empty group). An entry without `children` is not a group. Depth is
limited to 100 nested groups.

```
"layers": [
  {"layer": "layer-1"},                                  bottom
  {"layer": "layer-7", "children": [                     a group
      {"layer": "layer-3"},                              bottom of the group
      {"layer": "layer-4"}]},
  {"layer": "layer-9"}                                   top
]
```

**Colour.** `color_mode` is one of `Rgb`, `Grayscale`, `Cmyk`, `Lab`, `Bitmap`, `Indexed`,
`Duotone`, `Multichannel`; `sample_type` is `U8`, `U16` or `F32`. These describe the
document; **every pixel surface states its own format** in its own header and a reader
decodes a surface by that header alone. `icc_profile` names the node carrying the document's
ICC colour profile (§3.13) or is null; `color_space` is a numeric summary of that profile
(white point, RGB→XYZ matrix and tone curves where the profile is of the matrix kind) written
so that a reader without an ICC implementation still knows what the numbers mean. When both
are null the file declares no colour space: the sample values are uncalibrated.

**Fonts.** `fonts` lists every font face the text layers name, each once. The document model
refers to fonts by name. An entry's `source` names the node carrying the font file, or is
**null: the font file is not in this package**. This is the one place where a
`raster-layers/1` file can name something it does not carry, and it says so explicitly rather
than staying silent; the rendered appearance of every text layer IS carried (§3.2, `cache`).

*Edges.* `enhances` to every node the payload names (role `contains` for layers, and
`channel`, `quick-mask`, `selection`, `pattern`, `saved-path`, `layer-comp`,
`last-document-state`, `text-styles`, `variables`, `metadata`, `color-profile`, `font`).
`enhances`, never `requires`: a document whose third layer is damaged is still a document.

*If it is dead or missing:* the layer order, grouping, canvas size and settings are lost. A
reader lists every live `core.raster.layer` node in manifest order as a flat stack (which is
bottom-to-top as a conformant writer writes it), takes the canvas from the extent of their
pixel surfaces, and says that it did.

### 3.2 `core.raster.layer` — one layer

One file, `layers/<node id>/layer.json`: everything about one layer except pixels. Common to
every kind: `name`, `visible`, `locks`, `blend` (§5.2), `opacity`, `fill_opacity`, `clipped`,
`mask` (a raster mask: a one-channel surface plus `enabled`, `linked`, `density`, `feather`),
`vector_mask`, `effects` (the layer style: drop/inner shadow, outer/inner glow, stroke,
colour/gradient/pattern overlay, satin, bevel & emboss), `label`, `blend_if`, `advanced`,
`link_group`, `excluded_channels`, `video`.

`content.kind` says what the layer holds:

| `kind` | what it is | where its pixels are |
|---|---|---|
| `raster` | a pixel layer | `content.pixels` → a surface, in document coordinates |
| `group` | a group; its children are in the structure node's tree. `artboard` set: an artboard | — |
| `adjustment` | a function applied to everything beneath it (`content.adjustment`, 16 kinds) | none; a Color Lookup's table is the `core.raster.lut3d` node `…ColorLookup.lut` names |
| `fill` | a solid colour, gradient or pattern over the whole canvas | none (computed); `fill_cache` may hold a rendering |
| `text` | text with character and paragraph runs, a transform, an optional warp | `content.cache` → the text rendered to pixels |
| `shape` | a vector path with fill and stroke | `content.cache` → the shape rendered to pixels |
| `smart` | a placed file shown through a transform and non-destructive filters | `content.cache` → the smart object as it looks in the document; `content.decoded` → the placed file's own pixels; `content.source` → the placed file itself (§3.13) |

**To show a layer you never need to implement text layout, path filling or a file decoder:**
for `text`, `shape` and `smart` layers the `cache` surface holds the layer's rendered pixels
in document coordinates. It is null only when the writer never rendered the layer.

Text run lengths (`runs[].len`, `paragraphs[].len`) count **UTF-8 bytes** of `content.text`,
in order; sizes ending in `_pt` are points (`pixels = points × resolution_dpi / 72`).

*Edges.* `enhances` to each surface, table, source and block node the payload names (roles
`pixels`, `mask`, `smart-filter-mask`, `rendered-cache`, `fill-cache`, `video-frame`,
`video-original-frame`, `lookup-table`, `embedded-source`, `linked-source`,
`decoded-source`, `linked-footage`).

*If it is dead or missing:* that layer is lost. A reader drops it from the tree; if it was a
group, its children stay and move up into the group's place. Every surface that `requires`
the layer (its masks and caches) is dead with it; its `-pixels` surface is not (see §3.3).

### 3.3 `core.raster.surface` — pixels

The universal pixel container: a sparse grid of 256 × 256 tiles of little-endian samples,
plus one default pixel for everywhere else. **`spec/layouts/core.raster.surface.layout.txt` is
the complete grammar**; `spec/examples/raster-layers/surface.example.hex.txt` and
`tiles.example.hex.txt` walk through a real one byte by byte. In short: the node's payload is
an index file (`surface.wkx`: pixel format, default pixel, one row per stored tile saying
which tile file and which slot holds it), and the tile files hold the samples, each tile
65 536 pixels, rows top to bottom, samples interleaved. Samples are `u8` (0..255 ↔ 0.0..1.0),
`u16` (0..65535 ↔ 0.0..1.0) or IEEE-754 `f32`; colour is never premultiplied by alpha.

**Tile files are compressed, and the file says how to undo it.** A tile file is either a
tile envelope as it is (what a minimal writer produces, §7) or — what PhotoCraft writes — a
**zlib stream** whose inflated bytes are a tile envelope. The node's `meta.file_formats` maps
the role of every such file to the format id `zlib-deflate`, and `MANIFEST.json` → `formats`
gives the path of that format's definition inside this package (enough to write an inflater,
with test vectors, and a reference inflater in source). Inside such an envelope the samples
are stored with `sample_encoding` `"planes-delta"`: split into byte planes, each byte the
difference to the same channel of the previous pixel — exact for 8-bit, 16-bit and float
samples, and undone in a dozen lines (layout §5.2, with a worked example). The index records
the sha256 of every tile envelope (`tile_file_sha256`), so each stage of decoding can be
checked. Photo-like documents come out at roughly half the size of the same document as a
PSD; flat artwork far smaller.

A surface is unbounded: tiles may lie partly or wholly outside the canvas, and at negative
coordinates. Pixel (0, 0) is the canvas's top-left pixel; y grows downward.

What a surface is FOR is said by whoever names it, and repeated for listings in the node's
`meta.usage` (`layer-pixels`, `layer-mask`, `smart-filter-mask`, `layer-cache`, `fill-cache`,
`video-frame`, `video-original-frame`, `channel`, `pattern`, `selection`,
`decoded-original`). `meta` also carries `owner` (a node id), `channels`,
`bits_per_sample` and, when tile files are compressed, `file_formats`; the payload's own
header is the authority.

*Edges and stamps.*

| surface | edge | epistemic stamp |
|---|---|---|
| a layer's pixels, a channel, a pattern, the selection | none: it is meaningful alone | `authored` |
| a layer mask, a smart filter mask, a video frame | `requires` its layer (role `belongs-to`): a mask without its layer masks nothing | `authored` |
| a rendered cache (`-cache`, `-fill-cache`) | `requires` its layer | `measured`: `input_files` is the layer's `layer.json`; `input_params` `{"derivation": "rasterized-layer-content"}` |
| a decoded original (`…-decoded`) | `enhances` the source node | `measured` from the source file; `{"derivation": "decoded-embedded-original"}` |

*If it is dead or missing:* a pixel layer is shown empty; a mask is treated as absent (the
layer is shown unmasked); a cache is treated as null (render the layer again, or show
nothing); a channel, pattern or selection is absent. A reader says which.

### 3.4 `core.raster.lut3d` — a colour lookup table

One envelope file (`WKX1`): the grid size and N³ RGB triplets of 32-bit floats.
`spec/layouts/core.raster.lut3d.layout.txt`. Named by a Color Lookup adjustment layer; no
edges; `authored`. *Dead or missing:* that adjustment changes nothing.

### 3.5 `core.raster.channel`

One JSON file: an extra channel's name, overlay colour and — for a spot colour — its ink
colour, plus `surface`, the node id of its pixels (one gray channel: 1.0 selected or full
ink, 0.0 masked or no ink). The same type carries the Quick Mask (node id `quick-mask`).
Edge: `enhances` its surface (role `pixels`). *Dead:* that channel is absent.

### 3.6 `core.raster.pattern`

One JSON file: a pattern tile's own `id` (the string fills and effects name it by), `name`,
`width`, `height`, and `surface`, the node id of its pixels (x in 0..width, y in 0..height;
any pixel format). Edge: `enhances` its surface. *Dead:* fills and effects that use the
pattern paint nothing.

### 3.7 `core.raster.path`

One JSON file: a saved path's `name` and `path` — cubic Bézier subpaths in document pixels
with a fill rule and per-subpath combine operations (the schema's `path` definition states
the geometry exactly). No edges. *Dead:* that path is absent.

### 3.8 `core.raster.comp`

One JSON file: a layer comp — per layer, optionally, its visibility, position and appearance
(blend mode, opacities, layer style), and three flags saying which of those applying the comp
restores. A state names its layer by node id (`layer`), or by number (`layer_gone`) when the
layer has since been deleted. Edges: `enhances` each layer named (role `records-state-of`).
*Dead:* that comp is absent.

### 3.9 `core.raster.text-styles`, 3.10 `core.raster.variables`, 3.11 `core.raster.metadata`

One JSON file each; node ids `text-styles`, `variables`, `metadata`; present only when the
document has such data. Text styles are named partial attribute sets; text layers keep fully
resolved attributes in their runs, so a reader that ignores this node loses nothing visible.
Variables bind named data slots to layers and list data sets of values; a pixel value names
an image by `origin_note` (never followed) and, when the package carries it, `embedded`.
Metadata holds the XMP packet as text, free-form key/value text, and the node id of the EXIF
block (§3.13). *Dead:* that data is absent.

### 3.12 `core.raster.preview` — the pictures

A PNG: 8 bits per channel, RGBA, sRGB, straight alpha, as `meta` declares (`usage`
`thumbnail` or `composite`, `width`, `height`, `color_space` `"srgb"`, `bits_per_sample` 8,
`channels`, `alpha_mode` `"straight"`). `composite` is the whole document flattened —
every visible layer blended, scaled so that its longer side is at most
`input_params.max_side` pixels; `thumbnail` is the same at a smaller size.

They are **derived**: `epistemic` is `measured`, `input_files` lists, in order, every file of
every `core.*` node of the document except the two previews themselves and the decoded
originals of §3.13 (the structure node first, then each node in manifest order), `input_params` is
`{"derivation": "flattened-composite", "max_side": N, "resample": "area-average"}`, and
`input_hash` is constructed as `spec/CRAFT-BASE.md` §5 says. A reader that recomputes
`input_hash` and finds it different knows the picture is stale. Edges: `requires` every node
whose files are inputs (role `rendered-from`) — a picture of a document with a dead layer is
not that document's picture.

A writer that cannot render a composite writes neither node and sets neither `primary` slot.

### 3.13 Embedded originals — `core.raster.source`, `core.raster.source-svg`, `core.text.font` and `x.photocraft.source.<format>`

Some things a document holds are whole files in an encoding of their own, kept byte for
byte: the file placed as a smart object, the ICC colour profile, the EXIF block, a font, a
copy of a file the document only linked to. Each is one node with exactly ONE file whose bytes
are exactly the original's; `files[].sha256` is the hash of the original.

* **`core.raster.source`** — the encoding is one for which this package carries a **format
  definition**: a document under `spec/formats/` from which a decoder (and where stated an
  encoder) can be built, with hash-checkable test vectors. In this profile version the
  formats are `png`, `jpeg`, `gif`, `bmp`, `tiff`, `webp`, `pdf`, `psd` (a Photoshop file,
  PSD or PSB: its structure, layers' channel data and merged image, NOT how layers
  composite), `zip` (a placed werk
  container: a ZIP whose own contents describe themselves), `icc` (a colour profile) and
  `exif` (an EXIF block). A definition may
  build on another (`requires` in its header: `png` on `zlib-deflate`, `jpeg` on
  `jpeg-segments`); the package then carries that one too. To decode the payload:

  1. the node's **`meta.payload_format`** is the format id (never guess it from a file name);
  2. `MANIFEST.json` → **`formats[<id>]`** is the path of the definition inside this package
     (`spec/formats/<id>.md`); it is listed there only when a node of the package uses it;
  3. the definition opens with a fenced `werk-format` block (JSON): what it covers
     (`coverage`, `coverage_note` — a definition may cover a stated SUBSET of the format,
     and says exactly which), whether decoders may differ (`lossy`, `tolerance`), the
     canonical decoded form of each test vector (`output_form`), and `reference_tools`.
     Read the coverage note before relying on a definition: `webp` defines the container
     and NOT the VP8 / VP8L bitstreams (the pixels of a WebP original are in this package
     only as its `-decoded` surface, below); `icc` defines the structure and the matrix/TRC
     arithmetic and NOT the evaluation of lookup-table profiles; `sfnt` defines the
     container, character map, metrics and TrueType outlines and NOT CFF outlines, hinting
     or layout tables; `pdf` defines the file structure down to every object and decoded
     page content stream and NOT what the content draws; `tiff` and `jpeg` each cover a
     stated subset;
  4. each reference tool is a `core.tool` node of this package whose node id is the tool's
     `tool_id` and whose files are SOURCE (Python, standard library only):
     `python <entrypoint> <payload file>` writes the canonical decoded form to standard
     output. It is a convenience. The definition document is the norm, and nothing runs a
     tool automatically.

  The other `meta` fields: `format` (the writer's name for the format: the same word),
  `media_type`, `has_file_name`.
* **`core.raster.source-svg`** — the original is an SVG document in UTF-8 (no NUL
  character): plain text, one of the container's own encodings, read as it is. `meta`:
  `format` = `"svg"`, `media_type`, `has_file_name`.
* **`core.text.font`** — one font file (format `sfnt`: a TrueType / OpenType font, or a
  collection), found the same way (`meta.payload_format` = `sfnt`). It is the node type the
  sibling ArtCraft profiles use for fonts. See "Fonts" below.
* **`x.photocraft.source.<format>`** — the same thing for an encoding this package carries
  NO definition for yet: `pcraft` (PhotoCraft's earlier bundle), `other` (a file the
  writer could not identify), and a file of one of the defined formats
  whose first bytes the definition's own `sniff` rule does not accept, an SVG that is not
  UTF-8 text, or a font that is not a TrueType / OpenType container (the types
  `x.photocraft.source.png`, `.jpeg`, `.gif`, `.bmp`, `.tiff`, `.webp`, `.pdf`, `.psd`,
  `.svg`, `.werk`, `.icc`, `.exif` and `.font` exist for those cases only). The type name says which;
  `spec/layouts/x.photocraft.source.<format>.layout.txt` names the public standard and how
  to recognise it. It is an extension node only for that reason: a reader that does not
  implement that standard skips it. A later version of this profile moves a format to
  `core.raster.source` when its definition exists; readers decide by node type, so both
  spellings stay readable.

A writer chooses the carrier from the original's bytes, never from its name.

Which node a reference means is said by the payload field that names it:

| field | node id | what the file is |
|---|---|---|
| structure node `icc_profile` | `icc-profile` | the document's ICC profile |
| metadata `exif` | `exif` | the EXIF block |
| structure node `fonts[].node` | `font-<16 hex>` | a font file (`core.text.font`) |
| layer `content.source.source` (kind `smart`, source kind `embedded`) | `smart-<contents id>-<format>` | the placed file; `content.source.file_name` is its original name |
| layer `content.source.embedded` (source kind `linked`), `video.source.embedded`, variables `…embedded` | `linked-<16 hex>` | a copy, made at save time, of a file the document only referred to; `origin_note` beside it says where that file was and is never followed |

The 16 hex digits are the first 16 of the file's sha256. Smart objects with the same
`contents_id` share one source node.

**Fonts.** Text layers name their fonts by family and style. The structure node's `fonts`
lists every face the text is set in, once, with a `status`:

| `status` | meaning | `node` |
|---|---|---|
| `embedded` | the font file is in the package | the `core.text.font` node; `faceIndex` is the face's index in that file (0 unless it is a collection) |
| `restricted` | the writer had the font, and the font's own licence bits forbid passing it on: its OS/2 table's `fsType` has Restricted License embedding (0x0002) and neither Preview & Print (0x0004) nor Editable (0x0008) | null |
| `missing` | the writer did not have the font | null |

A writer embeds every font it has whose `fsType` allows it; one file is one node, shared by
every face that comes from it. A reader registers the embedded files with its text engine
before it renders or edits text, so the text is set in its own fonts on a machine that never
had them. For a `restricted` or `missing` face the text layer's `cache` (its rendered
appearance, §3.2) is what is shown; a reader that re-renders such text substitutes a font and
says so. A font that is in the package stays in it when a later save is made on a machine
that does not have the font. The row also carries `use` (always `text` here) and what the
runs ask for (`postscript_name`, `weight`, `italic`).

**No content hides in an original.** Wherever the writing application could decode an
original, the decoded content is ALSO present as plain pixels: a smart object's `cache` (how
it looks in the document) and `decoded` (the placed file's own pixels at its own size, origin
(0, 0), a `core.raster.surface` named `<source node id>-decoded`); a text layer's `cache`;
the numeric `color_space` summary of the ICC profile. What exists only inside an original:
the internal structure of a placed file (its own layers), font outlines, EXIF fields, and
those parts of an ICC profile that are lookup tables rather than a matrix and curves.

**What a reader that skips every `x.*` node does not get** (this is the complete list for
`x.photocraft.source.*`; §3.14 has the list for Photoshop blocks): the bytes of placed or
linked files in the formats listed above as having no definition — PhotoCraft's earlier
bundle, unidentified — (their rendered appearance and decoded pixels stay). The ICC
profile, the EXIF block, fonts and placed PNG, JPEG, GIF, BMP, TIFF, WebP, PDF, Photoshop,
SVG and werk files are core nodes.
(A font file that is not a TrueType / OpenType container would travel as
`x.photocraft.source.font`; PhotoCraft's text engine reads no such fonts.)

*Edges.* None from the source node. *Dead or missing:* a smart object keeps its rendered
appearance and cannot be re-rendered from source; the document opens without its colour
profile, EXIF block or font. A reader says which.

### 3.14 `x.photocraft.psd-blocks` — verbatim Photoshop blocks

Extension. Blocks of an imported Photoshop file kept byte for byte so that exporting to that
format again reproduces them; `spec/layouts/x.photocraft.psd-blocks.layout.txt`. Everything
the application understood of those blocks is in the core nodes, so a reader that skips this
type loses no layer, pixel or property — with the one exception that layout file names (an
adjustment kind PhotoCraft cannot evaluate, payload `{"Unsupported": …}`). Edge: `enhances`
its owner (role `psd-data-of`). Named by the owner's payload field `psd`.

### 3.15 Nodes of a type you do not know

Skip them and say so (`node-skipped-unknown-type`); everything else loads. A writer that
saves a document it opened MUST carry every such node of the current document through
unchanged (same node id, same version, same bytes), unless the user deleted what it belongs
to.

## 4. Versions

`spec/CRAFT-BASE.md` §3 and §4 apply unchanged: every Save appends one revision record to
the `revisions` node; a node whose files did not change gains no version and stores no byte.
In this profile that means:

* painting on one layer appends a version to that layer's `-pixels` surface only — and inside
  it, only the tile files whose bytes changed are new; the others are listed again by the new
  version with their identical path, sha256 and size;
* changing a layer's opacity, name or style appends a version to that layer's `layer.json`
  node only;
* adding, deleting, grouping or reordering layers appends a version to the structure node
  (and adds or drops nodes from the revision record); a deleted layer's nodes stay in the
  package, out of the current revision;
* the previews gain a version whenever anything they were derived from changed.

To read the document as it was at revision K: take record K of the `revisions` node; it maps
each node id to the version number that revision used; read every node at that version.
References between payloads are node ids, so they need no translation.

## 5. Conventions and meaning

### 5.1 The conventions

Every one is a value in `MANIFEST.json` → `conventions`, pinned by the manifest schema;
`spec/conventions-map.raster-layers.json` says which node types each governs. A reader that
does not support a value refuses the node types it governs and keeps everything else.

| convention | value | meaning |
|---|---|---|
| `endianness` | `"le"` | every envelope binary is little-endian |
| `alignment_bytes` | `16` | envelope sections start on 16-byte boundaries |
| `text_encoding` | `"utf-8"` | every text and JSON file |
| `id_case` | `"kebab-case"` | every id |
| `hash_algorithm` | `"sha256"` | every hash |
| `signature_algorithm` | `"ed25519"` | `SIGNATURE.json` |
| `pixel_origin` | `"top-left"` | pixel (0, 0) is the canvas's top-left pixel; integer (x, y) names the pixel whose top-left corner is at (x, y) |
| `x_axis`, `y_axis` | `"right"`, `"down"` | x grows to the right, y grows DOWN |
| `length_unit` | `"pixel"` | every length and position, unless the field name ends in `_pt` |
| `resolution_unit` | `"pixels-per-inch"` | `resolution_dpi` |
| `points_per_inch` | `72` | `_pt` fields: pixels = points × resolution_dpi / 72 |
| `angle_unit`, `angle_zero`, `angle_direction` | `"degree"`, `"+x"`, `"counter-clockwise"` | angle 0 points to 3 o'clock; 90 points UP on screen |
| `alpha_mode` | `"straight"` | colour samples are not premultiplied by alpha |
| `layer_order` | `"bottom-to-top"` | entry 0 of a layer list is drawn first |
| `tile_size_px` | `256` | a tile is 256 × 256 pixels |
| `tile_scan_order` | `"row-major"` | rows top to bottom, pixels left to right |
| `sample_layout` | `"interleaved"` | the samples of one pixel are stored together |
| `white_u8`, `white_u16`, `white_f32` | `255`, `65535`, `1.0` | the sample value that means 1.0 |
| `float_format` | `"ieee754-binary32"` | 32-bit samples |
| `gray_zero` | `"black"` | gray 0.0 is black |
| `mask_zero` | `"hidden"` | mask / selection / channel 0.0 hides or is unselected |
| `cmyk_zero` | `"no-ink"` | CMYK components are ink amounts |
| `lab_l_scale`, `lab_ab_scale`, `lab_ab_offset` | `100`, `255`, `128` | L\* = 100·v; a\* = 255·v − 128 |
| `text_run_unit` | `"utf-8-byte"` | text run lengths |
| `affine_layout` | `"a-b-c-d-e-f"` | x′ = a·x + c·y + e, y′ = b·x + d·y + f |
| `preview_color_space` | `"srgb"` | the preview PNGs |

JSON numbers are decimal text of IEEE-754 values. A field the application holds as a 32-bit
float is written as the decimal expansion of that float widened to 64 bits (so `0.1` held as
a 32-bit float reads `0.10000000149011612`); parse it as a 64-bit float and narrow it, and
you have the exact value. NaN and infinities never occur in JSON payloads.

### 5.2 Blend modes

`blend` names how a layer's colour `s` (source) combines with the colour `b` beneath it
(backdrop), per colour channel on the 0.0–1.0 scale, before the result is mixed in by the
layer's coverage: `result = (1 − α)·b + α·B(b, s)`, where α is the layer's alpha × `opacity`
(× mask) at that pixel. `B(b, s)`:

| `blend` | B(b, s) |
|---|---|
| `Normal` | s |
| `Dissolve` | s; instead of mixing by α, each pixel shows s with probability α, else b |
| `PassThrough` | groups only: the group is not composited on its own; its children blend directly with what lies beneath the group |
| `Darken` | min(b, s) |
| `Multiply` | b·s |
| `ColorBurn` | 1 if b ≥ 1; else 0 if s ≤ 0; else 1 − min(1, (1 − b)/s) |
| `LinearBurn` | max(0, b + s − 1) |
| `Lighten` | max(b, s) |
| `Screen` | b + s − b·s |
| `ColorDodge` | 0 if b ≤ 0; else 1 if s ≥ 1; else min(1, b/(1 − s)) |
| `LinearDodge` | min(1, b + s) (no upper clip in 32-bit float documents) |
| `Overlay` | HardLight with b and s exchanged: 2·b·s if b ≤ 0.5, else 1 − 2·(1 − b)·(1 − s) |
| `SoftLight` | if s ≤ 0.5: 2·b·s + b²·(1 − 2·s); else 2·b·(1 − s) + √b·(2·s − 1) |
| `HardLight` | 2·b·s if s ≤ 0.5, else 1 − 2·(1 − b)·(1 − s) |
| `VividLight` | 0 if s ≤ 0; 1 if s ≥ 1; ColorBurn(b, 2·s) if s ≤ 0.5; else ColorDodge(b, 2·(s − 0.5)) |
| `LinearLight` | clamp(b + 2·s − 1, 0, 1) |
| `PinLight` | min(b, 2·s) if s ≤ 0.5, else max(b, 2·s − 1) |
| `HardMix` | 1 if VividLight(b, s) ≥ 0.5, else 0 |
| `Difference` | \|b − s\| |
| `Exclusion` | b + s − 2·b·s |
| `Subtract` | max(0, b − s) |
| `Divide` | if s ≤ 0: 0 when b ≤ 0, else 1; otherwise min(1, b/s) (no upper clip in 32-bit float documents) |
| `Reflect` | 1 if s ≥ 1, else min(1, b²/(1 − s)) |
| `Glow` | Reflect with b and s exchanged |
| `Negation` | 1 − \|1 − b − s\| |
| `Xor` | on 8-bit values: (round(255·b) XOR round(255·s)) / 255 |
| `PaintNetColorBurn` | 0 if s ≤ 0, else max(0, 1 − (1 − b)/s) |
| `PaintNetColorDodge` | 1 if s ≥ 1, else min(1, b/(1 − s)) |

The six remaining modes work on the whole RGB triple, with
`lum(c) = 0.3·r + 0.59·g + 0.11·b`, `sat(c) = max(c) − min(c)`, `SetLum(c, l)` = c shifted so
that its `lum` is l and then pulled towards its grey until every channel is within 0..1, and
`SetSat(c, v)` = c rescaled so that its smallest channel is 0 and its largest is v (the W3C
*Compositing and Blending Level 1* definitions):

| `blend` | B(b, s) |
|---|---|
| `Hue` | SetLum(SetSat(s, sat(b)), lum(b)) |
| `Saturation` | SetLum(SetSat(b, sat(s)), lum(b)) |
| `Color` | SetLum(s, lum(b)) |
| `Luminosity` | SetLum(b, lum(s)) |
| `DarkerColor` | s if lum(s) < lum(b), else b |
| `LighterColor` | s if lum(s) > lum(b), else b |

### 5.3 How a document becomes a picture

Not needed to read the file, and not part of what a reader must implement — `primary.image`
is the picture. For someone who wants to draw it: walk the tree bottom to top. A layer
contributes its content (pixels, or the `cache` of a text, shape or smart layer, or its
computed fill), with coverage = content alpha × `fill_opacity` × `opacity` × mask value ×
vector mask coverage, blended by §5.2. A raster mask's value at a pixel is
`1 − density × (1 − v)` where v is the mask surface's gray value there (1.0 when `enabled` is
false). A layer with `clipped: true` is confined to the coverage of the nearest non-clipped
layer beneath it in the same list. A group other than `PassThrough` is composited on its own
onto transparency and then blended as one layer. An adjustment layer replaces the picture
beneath it, within its coverage, by its function of that picture. Invisible layers
(`visible: false`) contribute nothing. Layer effects are drawn around their layer's content
as the layer schema's `effects` definitions describe.

## 6. Reading: the document in nine steps

1. Open the container (directory, or store-mode zip).
2. Parse `MANIFEST.json`. Check `profile` is `raster-layers/1`. Check the conventions of §5.1
   that your reader depends on.
3. Take `primary.document` → that node → its `active` version → its one file. Verify its
   sha256 and size against the manifest. Parse it as JSON: you have the canvas and the tree.
4. Walk `layers` (bottom to top; recurse into `children`). For each entry: the node named
   `layer` → its `active` version → its one file → verify → parse.
5. For each surface a layer names (`content.pixels`, `mask.surface`, `content.cache`, …):
   that node → its `active` version → **its payload file by `payload_file`** (or its only
   file) → verify → parse the envelope: this is the index. For each tile file the index
   names, find the entry of the SAME version's `files[]` with that `role`, verify it, parse
   it. Place the tiles (`spec/layouts/core.raster.surface.layout.txt` §6).
6. The same for `channels`, `patterns`, `selection` and whatever else you want.
7. A node whose file is missing, fails its hash, or does not parse is dead: apply the "dead
   or missing" rule of its type (§3), say so, continue. A node of a type you do not know is
   skipped: say so, continue.
8. For an embedded original you want to decode: its node's `meta.format` → `MANIFEST.json`
   `formats[<id>]` → that definition document.
9. Report the signature state in one of the four fixed words (`spec/CRAFT-BASE.md` §7).

To read the document as it was at revision K instead, replace "its `active` version"
everywhere by "the version record K of the `revisions` node gives for that node" (§4).

## 7. Writing a minimal valid `raster-layers/1` capsule

This section is normative. A capsule built exactly as below is accepted by every
`raster-layers/1` reader, PhotoCraft's strict one included.
`spec/examples/raster-layers/write_minimal.py` does all of it with the Python standard
library and nothing else; run it against any `raster-layers/1` capsule (it copies `loaders/`
and `spec/` from there):

    python spec/examples/raster-layers/write_minimal.py <existing capsule> <new.werk>

The document: a 256 × 256 px RGB canvas, 8 bits per channel, one pixel layer "Layer 1" whose
pixel (x, y) has red = x, green = y, blue = (x + y) mod 256, alpha = 255. The steps, with the
values the script produces, so that you can check your own implementation against them:

**7.1 The two JSON payloads.** Each is one line of JSON followed by one line feed (`0x0A`),
UTF-8, no byte-order mark. EVERY field of the schema is present; a field you have nothing to
say in is `null`, `[]`, `{}` or its neutral value exactly as below.

`document/document.json` — 842 bytes, sha256
`7c4c3a0eb96550bb3bb143f2f6dd26c10fb77a1dee5ef71b08bc08aab0eefb45`:

    {"schema_version":1,"name":"Minimal","width":256,"height":256,"resolution_dpi":72.0,"color_mode":"Rgb","sample_type":"U8","color_space":null,"icc_profile":null,"layers":[{"layer":"layer-1"}],"channels":[],"quick_mask":null,"quick_mask_unselected":false,"selection":null,"patterns":[],"paths":[],"work_path":null,"clipping_path":null,"layer_comps":[],"last_applied_comp":null,"last_document_state":null,"text_styles":null,"variables":null,"metadata":null,"guides":{"horizontal":[],"vertical":[]},"global_light":{"angle":120.0,"altitude":30.0},"color_table":null,"duotone":null,"measurement":{"scale":{"pixel_length":1.0,"logical_length":1.0,"units":"pixels"},"count_groups":[],"active_count_group":0,"ruler":null},"notes":[],"slices":{"groupName":"","list":[]},"timeline":null,"file_encoding":{},"psd":null,"fonts":[],"app":{"document_id":0}}

`layers/layer-1/layer.json` — 647 bytes, sha256
`40e59226cc2329f12b7c4624c29c3398f5abf097070286084e9d1c839f45f874`:

    {"schema_version":1,"name":"Layer 1","visible":true,"locks":{"transparency":false,"pixels":false,"position":false,"artboard":false,"all":false},"blend":"Normal","opacity":1.0,"fill_opacity":1.0,"clipped":false,"mask":null,"vector_mask":null,"effects":{"enabled":true,"items":[],"reference":null},"label":"None","content":{"kind":"raster","pixels":"layer-1-pixels"},"psd_id":null,"psd":null,"fill_cache":null,"link_group":null,"excluded_channels":0,"blend_if":{"ranges":[]},"advanced":{"knockout":"none","blendInterior":false,"blendClipped":true,"transparencyShapes":true,"layerMaskHidesEffects":false,"vectorMaskHidesEffects":false},"video":null}

If your hashes differ you have a whitespace, key-order or line-ending difference; find it
before going further. (Any valid JSON spelling of the same values is a valid payload — these
exact bytes are only the checkpoint.)

**7.2 The surface: two envelope files** (`spec/layouts/core.raster.surface.layout.txt` §7).

`surfaces/layer-1-pixels/tiles-p0-p0.wkx` — 262 432 bytes, sha256
`b87706652c2b888f1c1727fa34e27a1ad08f55e6005205ceb7147fcc1a510fcc`. Magic `WKX0`, version 1.
Header (MessagePack map, keys in byte order): `channels` `["red","green","blue","alpha"]`,
`endianness` `"le"`, `has_alpha` true, `kind` `"core.raster.surface"`, `nonfinite` false,
`part` `"tiles"`, `payload_origin` 288, `payload_size` 262144, `pixel_mode` `"rgb"`,
`sample_type` `"u8"`, `sections` (one: `name` `"samples"`, `offset` 288, `size` 262144,
`dtype` `"u8"`, `shape` `[1,256,256,4]`, `stride` 4), `tile_count` 1, `tile_size` 256. The
section is 65 536 pixels of 4 bytes: for y = 0..255, for x = 0..255: `x, y, (x+y) mod 256, 255`.

`surfaces/layer-1-pixels/surface.wkx` — 400 bytes, sha256
`08000f038cf0eae6eef93922bbc3d70280625dea8de6bb2b994f464d5b9c1074`. The same format keys with
`part` `"index"` and `tile_files` `["tiles-p0-p0"]`; two sections: `default-pixel` (dtype
`u8`, shape `[4]`, stride 1, the 4 bytes `00 00 00 00`) and `tile-index` (dtype `i32`, shape
`[1,4]`, stride 16, the 16 bytes of four little-endian zeros: tile (0, 0), file 0, slot 0).

**7.3 The base files.** Copy every current file under `loaders/` and `spec/` from the
existing capsule unchanged (skip files whose name carries an `@N` marker — superseded
versions). Write `LICENSE` (the full licence text of your content, or an honest statement
that its terms are not established), and copy `README.txt` and `HOW-TO-READ.md`.

**7.4 The revision record** `revisions/revision.json` (`spec/CRAFT-BASE.md` §3):

    {"schema_version":1,"revision":1,"kind":"save","note":"<why this file exists>",
     "created":"<RFC 3339 UTC>","producer":{"tool":"<your tool>","version":"<its version>"},
     "nodes":{"spec":1,"license":1,"readme":1,"loader-python":1,"loader-rust":1,
              "loader-c":1,"document":1,"layer-1":1,"layer-1-pixels":1}}

**7.5 The manifest.** Ten nodes: `spec`, `license`, `readme`, `loader-python`,
`loader-rust`, `loader-c`, `revisions`, `document`, `layer-1`, `layer-1-pixels`. Each has one
version:

    {"v":1, "files":[{"path":…,"sha256":…,"size":…}], "note":"<at least 8 characters>",
     "producer":{"tool":…,"version":…}, "epistemic":"authored", "created":"<RFC 3339 UTC>"}

with `"active":1` and `"edges":[]`, except:

* `document` — type `core.raster.document`; edges
  `[{"to":"layer-1","kind":"enhances","role":"contains"}]`; `meta`
  `{"width":256,"height":256,"color_mode":"Rgb","sample_type":"U8"}`.
* `layer-1` — type `core.raster.layer`; edges
  `[{"to":"layer-1-pixels","kind":"enhances","role":"pixels"}]`; `meta` `{"kind":"raster"}`.
* `layer-1-pixels` — type `core.raster.surface`; its version lists TWO files, the index with
  `"role":"payload"` and the tile file with `"role":"tiles-p0-p0"`, and carries
  `"payload_file":"surfaces/layer-1-pixels/surface.wkx"`; `meta` (REQUIRED for this type)
  `{"usage":"layer-pixels","owner":"layer-1","channels":["red","green","blue","alpha"],"bits_per_sample":8}`.
* `readme` — two files, `"payload_file":"README.txt"`; the three `core.loader` nodes carry
  the `meta` block of the existing capsule unchanged.

Copy `werk`, `profile`, `manifest_schema`, `conventions_map`, `conventions`, `container` and
— restricted to the node types your file contains — `schemas`, `layouts` and `formats` from
the existing manifest; drop `container.preview_prefix_bytes` (a hint) and set
`container.total_size_bytes` to the sum of the sizes of all the files you list. Set `primary`
to `{"document":"document"}`, `license` to `{"file":"LICENSE","sha256":<its sha256>}`, a
fresh `entity.uuid`, and compute `spec_sha256` by `spec/SPEC.md` §2 over every `spec/` path
you list.

**7.6 The container.** A store-mode zip, `MANIFEST.json` first, then the entries of
`container.preview_tier` in order, then the rest.

**7.7 Check.** `python loaders/werk_read.py <new.werk> --verify --strict` exits 0 and prints
`N/N files verified`, N being the number of files your manifest lists (the base files you
copied plus your four).

**Growing from here.** More layers: more `layer-<n>` nodes and tree entries. A mask: a second
surface with `pixel_mode` `"grayscale"`, named by the layer's `mask.surface`, with a
`requires` edge to the layer and `meta.usage` `"layer-mask"`. A bigger layer: more tiles in
the tile file and more index rows. Every other field has its meaning in the schema.

## 8. What this profile deliberately does not have

Named so that an absence reads as a decision.

* **No compressed pixels in core.** Surfaces are raw samples. A package is larger than a
  compressed format's file, and in exchange any reader reads any pixel with arithmetic.
  Redundancy between versions is removed by not storing unchanged tile blocks twice;
  redundancy between packages is the companion store's job. A compressed tile tier, if one is
  ever added, will be an `x.*` node beside the surface, never a replacement for it.
* **No full-resolution flattened image.** `composite` is a preview at a declared maximum
  side. The document IS its layers; a full-size flattening is recomputed from them.
* **No undo history.** The file keeps Saves (revisions), not the editor's undo steps.
* **No editor view state** (zoom, scroll, selected tool, open panels).
* **No guaranteed fonts.** The file states which faces it names and whether it carries them
  (§3.1); it does not promise to carry them, because a font's licence may forbid it.
* **No one-file-per-tile.** Tiles are grouped into files; a single-file package stays far
  below the zip's 65 534-entry ceiling, and a document too large for a 4 GiB zip is saved in
  directory form, the same format.

Within `raster-layers/1` evolution is additive only (law 12): a later writer may add node
types and `x.*` nodes; it will not change the meaning of anything described here. A change
that would is `raster-layers/2`.
