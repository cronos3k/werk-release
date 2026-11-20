# werk Profile: Vector Art — `vector-art/1`

Status: **v1.** Manifest schema: `spec/schemas/manifest.vector-art.schema.json`.
Conventions map: `spec/conventions-map.vector-art.json`.

A `vector-art/1` capsule is one vector illustration document: artboards, layers of objects
(paths, type, images, groups, symbol instances and the live objects built from them), the
paints and styles they use, and the raster images, fonts and colour profiles they need. It is
the native format of VectorCraft and the vector primitive of the ArtCraft suite: the node types
named `core.*` below are meant to be read and written by any program, and this document, the
JSON Schemas in `spec/schemas/` and the format definitions in `spec/formats/` are everything
such a program needs. Nothing here says "as VectorCraft does it".

The manifesto's twelve laws govern everything; where this document is silent, they decide. It
builds on, and does not restate:

* `spec/SPEC.md` — container (§1), manifest (§2), which file is a node's payload (§2.1),
  versions (§5), signatures (§6), loaders (§7), reader checklist (§10);
* `spec/CRAFT-BASE.md` — what every ArtCraft capsule shares: the package root, the `revisions`
  node, paths and the `@N` marker, epistemic stamps, signatures across saves, writing a capsule
  without ArtCraft software, limits;
* `spec/MINI-SPECS.md` — zip, JSON, UTF-8, SHA-256, PNG, byte by byte.

Where this document and a schema disagree about a payload, the schema wins for that payload.

---

## 1. Container

Exactly `spec/SPEC.md` §1 and `spec/CRAFT-BASE.md` §1. The profile's own files:

```
vector/document.json                 the structure node's payload
vector/artboards/<node id>.json      one file per artboard
vector/layers/<node id>.json         one file per top-level layer
vector/symbols/<node id>.json        one file per symbol
vector/patterns/<node id>.json       one file per pattern
vector/…/<node id>.json.zlib         the payload of a layer, symbol or pattern when it is stored
                                     apart, compressed (§3.1: "A payload stored apart")
vector/swatches.json  vector/graphic-styles.json  vector/text-styles.json     the libraries
vector/images/<node id>.png          the pixels of one image, PNG
vector/sources/<node id>.<ext>       an image's own file when it is not that PNG; a placed document
vector/fonts/<node id>.<ext>         a font file
vector/profiles/<node id>.icc        an ICC profile
preview/artboard.png  preview/artboard.svg       renderings of the first artboard
x/vectorcraft/...                    what only VectorCraft interprets (§3.3)
```

These paths are where VectorCraft puts the files. A reader never relies on them: it finds every
file through `MANIFEST.json` (`nodes[].versions[].files[]`).

**Preview tier** (law 9), physically first in the zip form: the base tier (`MANIFEST.json`,
`SIGNATURE.json`, `LICENSE`, `README.txt`, `HOW-TO-READ.md`, `loaders/`, `spec/`,
`revisions/`), then `vector/document.json`, then `preview/`. A store that has fetched only that
prefix can show the document's title, its artboard and layer count, and a picture of its first
artboard. `container.preview_tier` lists these elements and is the authority.

## 2. MANIFEST.json

Validated by `spec/schemas/manifest.vector-art.schema.json`, which the manifest names in
`manifest_schema`.

* `profile` is `"vector-art/1"`.
* `conventions` has the keys of §5.
* `primary.document` is REQUIRED: the node_id of the one `core.vector.document` node.
  `primary.image` is the node_id of the `core.vector.preview` node, when the capsule has one
  (VectorCraft always writes one).
* `entity.uuid` identifies the document: every save of the same document carries it; a
  duplicate gets a new one. `entity.name` is a listing label (the title on one line); the title
  itself is in the structure node's payload.

## 3. Node families

| type | how many | payload | defined by |
|---|---|---|---|
| `core.spec`, `core.loader`, `core.license`, `core.readme`, `core.revisions` | base | — | `spec/CRAFT-BASE.md` §1, §3 |
| `core.vector.document` | exactly 1 | JSON | `spec/schemas/core.vector.document.schema.json` |
| `core.vector.artboard` | 0 or more | JSON | `spec/schemas/core.vector.artboard.schema.json` |
| `core.vector.layer` | 0 or more | JSON | `spec/schemas/core.vector.layer.schema.json` |
| `core.vector.symbol` | 0 or more | JSON | `spec/schemas/core.vector.symbol.schema.json` |
| `core.paint.pattern` | 0 or more | JSON | `spec/schemas/core.paint.pattern.schema.json` |
| `core.paint.swatches` | 0 or 1 | JSON | `spec/schemas/core.paint.swatches.schema.json` |
| `core.vector.styles` | 0 or 1 | JSON | `spec/schemas/core.vector.styles.schema.json` |
| `core.text.styles` | 0 or 1 | JSON | `spec/schemas/core.text.styles.schema.json` |
| `core.vector.image` | 0 or more | PNG | `spec/MINI-SPECS.md` §8 |
| `core.vector.image-source` | 0 or more | a JPEG, GIF, BMP, TIFF or WebP file, verbatim | the format definition `MANIFEST.json` → `formats` names for the node's `meta.payload_format`: `spec/formats/jpeg.md`, `gif.md`, `bmp.md`, `tiff.md`, `webp.md` |
| `core.vector.placed-document` | 0 or more | a VectorCraft native file, verbatim | `spec/formats/vectorcraft-native.md` |
| `core.text.font` | 0 or more | a TrueType / OpenType font file or collection, verbatim | `spec/formats/sfnt.md` |
| `core.color.icc-profile` | 0 or more | an ICC profile, verbatim | `spec/formats/icc.md` |
| `core.vector.preview` | 0 or 1 | PNG | `spec/MINI-SPECS.md` §8 |
| `core.vector.svg` | 0 or 1 | UTF-8 text (SVG 1.1) | — |
| `x.vectorcraft.*` | optional | JSON or opaque | §3.3 |
| any other `x.*` | optional | anything | the extension's own layout file |

### 3.1 The document, and how its parts are named

**`core.vector.document`** — node_id `document`, one file. It is the structure node: it lists
the artboards and the top-level layers by node_id in order, names the node of each symbol,
pattern and image, and holds the settings that belong to no unit (units shown, guides, document
setup, file information). It carries no art. `primary.document` names it.

**Every string in a payload says what it is**, in its schema: one of a closed set (`enum`),
a node_id (`"format": "werk-node-ref"`), a record of where a placed file came from
(`"format": "werk-provenance-note"`: `link.path`, `link.relative`; never followed), or content
(`"format": "werk-content-text"`): a name, a title, an image key, the characters of type. Content
is what a person or a file supplied. It may look like anything, a file path included; it is
never a path into the package and never a reference to a file outside it.

**Three kinds of name** occur inside payloads, and a reader resolves each the same way:

1. **A node_id** (`"layer-12"`, `"symbol-3"`): only in the structure node (and in the
   `x.vectorcraft.*` tables). Every such field is declared in its schema with
   `"format": "werk-node-ref"`. Resolve it through `MANIFEST.json` → `nodes[]`.
2. **A resource name**: an object tree names a symbol by the symbol's `name`, a pattern by the
   pattern's `name`, an image by its `key`, a swatch, a graphic style or a text style by its
   name or id within its library node. These are content strings compared for equality, byte
   for byte, with no normalisation. They are the document's own names for its resources —
   a symbol instance that names a symbol the document does not have is legal, draws nothing,
   and must survive a save. Resolve one through the structure node's tables: `symbols[]` and
   `patterns[]` map `name` → `node`, `images[]` maps `key` → `node` / `original`.
   When two entries of a table have the same name, the first wins.
3. **An object id** (an integer): every object has an `id`, unique among the objects of the
   document's layers. The structure node's `text_threads` and `guides[].layer`, and the
   `x.vectorcraft.*` nodes, name objects by it. Find an object by walking the layers.

**`core.vector.artboard`** — one node per artboard; node_id `artboard-<id>` where `<id>` is
the artboard's own `id` (never its name or its position). An artboard is a named rectangle on
the canvas; it owns no art.

**`core.vector.layer`** — one node per TOP-LEVEL layer; node_id `layer-<id>` where `<id>` is
the layer object's `id`. Its payload is `{"schema_version": 1, "layer": <object>}`: the layer
object with its whole tree (§4). Sublayers are objects inside it.

**`core.vector.symbol`** — one node per symbol; node_id `symbol-<n>`, a number given when
the symbol is first saved and kept for its life, through renames (it is never made from the
name). Payload `{"schema_version": 1, "name": …, "art": <object>}`. The `name` in the payload
is the symbol's name; the structure node's table repeats it.

**`core.paint.pattern`** — one node per pattern; node_id `pattern-<n>`, numbered like symbols.
Payload `{"schema_version": 1, "pattern": {name, tile, art: [<object>…], …}}`.

**A payload stored apart.** The object tree of a layer, a symbol or a pattern is what makes a
document large, so a writer may store such a payload compressed. The node's version then has
TWO files:

* its payload file (`…/<node id>.json`, `payload_file`), which is a stub of two members:

      {"schema_version": 1,
       "external": {"role": "content", "format": "zlib-deflate", "bytes": 15459845,
                    "sha256": "<64 hex digits>"}}

* a file with `"role": "content"` (`…/<node id>.json.zlib`): ONE zlib stream (RFC 1950; the
  format `zlib-deflate`, whose definition `MANIFEST.json` → `formats` names; the node's
  `meta.file_formats` is `{"content": "zlib-deflate"}`).

The zlib stream inflates to the complete payload: the JSON document the node type's schema
describes (`{"schema_version": 1, "layer": …}` and so on), `external.bytes` bytes long, with
sha256 `external.sha256`. To read a layer, symbol or pattern node: read its payload file; if the
object has a member `external`, find the file of role `content` among the files of the SAME
version of the node, check its `sha256` and `size` against the manifest, inflate it, check the
result against `external.bytes` and `external.sha256`, and parse that. Otherwise the payload file
is the payload. Both forms are valid for any such node and a reader MUST read both; a node may
be in one form in one version and in the other in the next. `external.sha256` is the
payload's identity: two versions with the same value hold the same content, whatever the bytes
of their zlib streams. VectorCraft stores a payload apart when its JSON, written without
white space, is longer than 32 KiB (level 6, no preset dictionary); a writer is free to never do
it (§7 does not). No other node type of this profile uses the stub.

**`core.paint.swatches`** (node_id `swatches`), **`core.vector.styles`** (`graphic-styles`),
**`core.text.styles`** (`text-styles`) — the document's libraries: named paints, named
appearances, named sets of text attributes. One node each. Objects link to their entries by
name (swatches, text styles) or by `id` (graphic styles); every object ALSO carries the paint or
attributes it actually has, so a reader that only draws never needs a library.

### 3.2 Images, fonts and colour profiles

Everything a document needs is in the capsule (law 1). A file in an encoding of its own (a
JPEG, a placed document) is carried verbatim, and is a `core.*` payload when the capsule also
carries a DEFINITION of its format: a document in `spec/formats/` from which a decoder can be
written, with test vectors to check one against, and (as a convenience) a reference decoder in
source under `tools/`. `MANIFEST.json` → `formats` maps each format id present to its
definition, and the node's `meta.payload_format` says which format its payload is in. The
definitions say exactly what they cover; read the `coverage_note` in the header of each.

**An image** is known to objects by a `key` (a string; VectorCraft uses a hash of the bytes).
The structure node's `images[]` has one entry per key:

* `node` — a **`core.vector.image`** node (node_id `image-<n>`): the image's pixels as a PNG,
  8 or 16 bits per channel, grey or RGB with or without alpha, straight alpha, row 0 at the
  top. This is what a reader shows for the key, without any other codec. Its `meta.key`
  repeats the key. A key that reads as a local file path (`C:\…`, `/home/…`, `file:…`: an
  image named after the file it came from) is not repeated as it is, because no string of
  `meta` may read as one: `meta.key_sha256` is then the sha256 of the key's UTF-8 bytes.
* `original` — when the image's own bytes are a JPEG, a GIF, a BMP, a TIFF or a WebP file: a
  **`core.vector.image-source`** node (node_id `source-<n>-<format>`, `<format>` one of `jpeg`,
  `gif`, `bmp`, `tiff`, `webp`) holding them verbatim (a JPEG stays the JPEG it was; nothing
  is re-encoded). The PNG of `node` is then a `measured` derivative decoded from it by the
  writing application (its version lists the original in `input_files`), and `requires` it.
  For JPEG, whose decoders may differ by rounding, the PNG is what THIS writer's decoder
  produced; the definition states the tolerance to others. A TIFF of CMYK ink amounts keeps
  them in the original; its PNG is the RGB the writer showed. The WebP definition covers the
  container, not the VP8 / VP8L bitstreams, and says so: for a WebP image the PNG is the only
  pixels a reader built from this file alone has.
* `mime` — the media type of the image's own bytes (absent: `image/png`).

An image whose bytes are in no encoding the writer recognised has no `original`; it has `node`
when the writer had pixels for it (the preview of a linked image), and its own bytes are
carried by an extension node (§3.3) that the `x-embedded` table names. A reader that ignores
extensions shows the PNG.

An `image` object draws the pixels through its `xf`, which maps pixel space — (0,0) at the
top-left corner of the top-left pixel, (`width`,`height`) at the bottom-right — into the
document.

**A placed document** (`placeddocument` object) shows one artboard of another document. Its
`key` is in `images[]` like an image's: `node` is a PNG preview of what it shows (drawn in the
object's box when the reader cannot read the placed file), `original` is a
**`core.vector.placed-document`** node (node_id `source-<n>-vectorcraft`) with the placed file
itself, verbatim, in the format `spec/formats/vectorcraft-native.md` defines. That definition
covers the container completely and names, member by member, the schema of this profile that
describes each part of the document inside.

**Fonts.** Type names its font by family, style and optionally version. The structure node's
`fonts[]` lists every face the document's type uses; `source` names a **`core.text.font`** node
(node_id `font-<n>`) with the font file, verbatim: a TrueType / OpenType file, or a collection
of them (then `face_index` picks the face), in the format `spec/formats/sfnt.md` defines (the
container, the character map, the metrics and TrueType outlines; not CFF outlines, hinting or
layout tables: its coverage note says so). Several faces of one file share one node. Every
face has its row, embedded or not, and `status` says which: `embedded`; `restricted` (the
Restricted License embedding permission of its OS/2 `fsType`, or its bitmap-only bit, forbids
it); `missing` (not installed, as a TrueType / OpenType file, where the document was saved);
`not-requested` (the writer was told not to embed fonts). A row that is not
`embedded` has no `source` and a `reason` in words; `preview/artboard.svg`, when written,
still carries the glyph outlines of an installed face.

**Colour profiles.** `color_profiles` names the document's RGB and CMYK profiles;
`icc_profiles[]` gives the node of each profile that was loaded from a file: a
**`core.color.icc-profile`** node (node_id `icc-<n>`) with the ICC profile, verbatim, in the
format `spec/formats/icc.md` defines. (A file handed to the writer as a profile that does not
begin as an ICC profile does is carried by an extension node instead, `x-icc-<n>`.)

**Renderings.** **`core.vector.preview`** (node_id `preview`, `primary.image`): a PNG of the
first artboard — else of the bounds of the art, else 1 × 1 transparent — rendered by the
writing application, transparent where nothing paints. **`core.vector.svg`** (node_id
`preview-svg`): the first artboard as SVG 1.1, type converted to outlines, images embedded;
written only when the document's images are small. Both are `measured`: `input_files` lists,
in order, the files of the structure node, the first artboard, then every layer, symbol,
pattern and image node (for a payload stored apart: its payload file, the stub, which names
the payload by its sha256), and `input_params` records the region, scale and size. The only
JSON numbers in `input_params` are integers: the region (`[x0, y0, x1, y1]`, points) and
`pixels_per_point` are decimal STRINGS (`"0.37925925925925924"`), because `input_hash` is
taken over the canonical JSON text of `input_params` and a fraction has no single spelling
across JSON parsers and printers. A writer of this profile MUST NOT put a non-integer number
in `input_params`. Both `requires`
the core nodes they were made from, so damage to a layer marks the renderings dead rather than
leaving a stale picture.

### 3.3 What only VectorCraft interprets — `x.vectorcraft.*`

A reader may skip every one of these and still has the whole artwork. Each has a schema or a
layout file in `spec/`.

| type | node_id | what |
|---|---|---|
| `x.vectorcraft.session` | `x-session` | the view the document was saved with, saved views and selections, the Layers panel's open rows, the last export and print settings |
| `x.vectorcraft.features` | `x-features` | variables and data sets (data merge), web slices, export assets, pattern-editing state, the list of graph designs |
| `x.vectorcraft.graph-design` | `x-graph-design-<n>` | art VectorCraft's graph generator draws marks with |
| `x.vectorcraft.object-data` | `x-objects-<host node_id>` | for some objects of ONE object tree: the graph data, Image Trace settings, Shaper composition, slice options or perspective plane the object was made with. Addressed by path and object id (see the schema). Without it a graph is the group of marks it drew |
| `x.vectorcraft.app-data` | `x-app-data` | open JSON: the current brush and symbol, symbol sizes, the perspective grid, data importers kept from other formats, and members a newer VectorCraft wrote |
| `x.vectorcraft.brushes` | `x-brushes` | the brush library. A stroke with `brush` is drawn as a plain stroke by a reader without it |
| `x.vectorcraft.embedded` | `x-embedded` | per image key: the low-resolution preview of a LINKED image (what it shows while its file cannot be read), and the node that holds the image's own bytes when they are in an encoding this profile has no definition for |
| `x.vectorcraft.proxy` | `x-proxy-<n>` | one such preview, PNG or JPEG |
| `x.vectorcraft.source.vectorcraft` | `x-source-<n>-vectorcraft` | a placed native file that does not begin with `{` or a gzip header (leading white space), verbatim |
| `x.vectorcraft.source.other` | `x-source-<n>-other` | an image's own bytes in an encoding VectorCraft did not recognise |
| `x.vectorcraft.source.icc` | `x-icc-<n>` | a file given as a colour profile that does not begin as an ICC profile does, verbatim (§3.2) |
| `x.vectorcraft.pdf` | `x-pdf` | a PDF of every artboard, when the user asked for one |

### 3.4 Edges, and which side dies

An edge reads source → target. `requires`: a dead target kills the source. `enhances`: a dead
target costs the source one feature.

| source | target | kind, role | why |
|---|---|---|---|
| `document` | every artboard, layer, symbol, pattern, image, image-source, placed-document, font, ICC profile and library node | `enhances`, `contains` | a document whose third layer is damaged is still a document |
| a layer, symbol or pattern | each symbol, pattern and image node its objects name | `enhances`, `uses` | art that uses a damaged symbol still draws everything else |
| a `core.vector.image` decoded from an original | that original | `requires`, `decoded-from` | derived pixels whose source is damaged can no longer be checked |
| `preview`, `preview-svg` | the core nodes they were rendered from | `requires`, `derived-from` | a rendering of damaged art is stale |
| every `x.vectorcraft.*` node | the node it adds to | `enhances`, `extends` (or `lists`, `preview-of`, `derived-from`) | extensions never hold anything up |

No `core.*` node `requires` an `x.*` node.

### 3.5 What a reader does when a node is dead, missing or unknown

* **A layer**: the document opens without that layer. **An artboard**: without that artboard.
* **A symbol or pattern**: instances and paints that name it draw nothing.
* **A library node**: the library is empty; objects keep the paints and attributes they carry.
* **An image's original**: the reader shows the PNG of `node`; a writer that saves again
  records the image as a PNG. **An image's PNG**: a reader that can decode the original shows
  that; otherwise the image draws nothing.
* **A font**: the type is set in a substitute font. **An ICC profile**: colours are shown
  through the reader's default profile of that kind.
* **The structure node**: the reader rebuilds the structure from the manifest — every live
  `core.vector.artboard` and `core.vector.layer` node of the current revision in manifest
  order, every symbol and pattern under the name in its own payload, every image under its
  node's `meta.key` (for a node with `meta.key_sha256`: the key, among those the image objects
  of the layers, symbols and patterns name, that has this sha256), default settings — and says
  that it did.
* **`preview` or `preview-svg`**: ignored; a writer makes them again.
* **Any `x.*` node**: skipped. A node of a type the reader does not know is skipped and
  reported, and a writer carries it through its next save unchanged.

In every case the reader reports the node and what was lost, and exits with status 1 rather
than 0 (`spec/SPEC.md` §10.1).

## 4. The object model

A layer, a symbol's art and a pattern's art are trees of **objects**. The complete, normative
description is `$defs/object` and the definitions it reaches in
`spec/schemas/core.vector.layer.schema.json`; every field there says its unit, range, default
and meaning. `spec/examples/vector-art/payloads/layer-every-kind.json` is a layer that uses
every kind of object and every field (one object per line). This section is the map.

**An object** is `{id, kind, …}`. `kind.type` says what it is; the other members of `kind`
are that kind's data. Common members (all optional, defaults in the schema): `name`, `visible`,
`locked`, `opacity` (0–1), `blend`, `isolate`, `knockout`, `knockout_shape`, `appearance`,
`mask` (an opacity mask), `wrap`, `graphic_style`, `attrs`, `bbox_angle`.

| `kind.type` | what | members |
|---|---|---|
| `layer` | a layer or sublayer | `children`, `color`, `template`, `printable`, `clip`, `preview`, `dim_images` |
| `group` | a group; with `clip`, its first child clips the others | `children`, `clip` |
| `path` | a Bézier path | `path`, `rule`, `live` (the shape it was generated from), `clipping`, `guide` |
| `compound` | member paths painted as one shape | `children`, `rule` |
| `text` | type: point, area or on a path | `kind`, `xf`, `runs`, `para`, `paras`, `area`, … |
| `image` | a raster image | `key`, `width`, `height`, `xf`, `link`, `placement` |
| `symbolinstance` | a symbol drawn through a transform | `symbol`, `xf` |
| `blend` | key objects; the reader interpolates the steps | `children`, `spec` |
| `envelope` | content distorted by a warp, a mesh or a path | `content`, `kind`, `fidelity`, `options`, `frame` |
| `mesh` | a gradient mesh | `rows`, `cols`, `points` |
| `repeat` | source art drawn radially, on a grid or mirrored | `kind`, `source` |
| `placeddocument` | an artboard of another document | `key`, `link`, `width`, `height`, `xf` |

**Paint order.** In every list of objects (`children`, `content`, `source`, a pattern's `art`,
the structure node's `layers`) the FIRST element is at the bottom; each later one paints over
it.

**Geometry.** A `path` is `{"subpaths": [{"anchors": [...], "closed": bool}]}`. An anchor is
`{"p": [x, y], "in": [x, y], "out": [x, y], "kind": "Corner"|"Smooth"}`; `in` and `out` are
absolute positions and each defaults to `p`. The segment from anchor A to the next anchor B is
the cubic Bézier with control points `A.p`, `A.out`, `B.in`, `B.p` — a straight line when
`A.out = A.p` and `B.in = B.p`. A closed subpath has one more segment, from its last anchor to
its first. In pseudocode:

    for sub in path.subpaths:
        move_to(sub.anchors[0].p)
        n = len(sub.anchors)
        for i in range(1, n + (1 if sub.closed else 0)):
            a, b = sub.anchors[i - 1], sub.anchors[i % n]
            curve_to(a.get("out", a.p), b.get("in", b.p), b.p)
        if sub.closed: close()

Regions are filled by the non-zero winding rule unless `rule` is `"EvenOdd"`.

**Transforms** are `[a, b, c, d, e, f]`: (x, y) ↦ (a·x + c·y + e, b·x + d·y + f). A path's
coordinates are already document coordinates; `xf` appears only where an object has a space of
its own (type, images, symbol instances, live shapes, pattern paints).

**Appearance.** `appearance.items` is a list of fills and strokes, bottom first, each
`{"kind": "fill"|"stroke", "paint": …}` with its own `opacity`, `blend`, `visible` and
`effects`; a stroke adds `width` (points), `cap`, `join`, `miter_limit`, `align`, `dash`,
arrowheads, a width `profile` and a `brush`. `appearance.effects` are live effects on the whole
object. A container (`layer`, `group`) or `text` object paints `contents_index` of its items
below its contents and the rest above. An object with no `appearance` paints nothing of its
own. To draw an object: paint its items in order into a group, apply the object's effects,
mask, `opacity` and `blend` to the group as a whole.

**Paint** is one of `{"type": "none"}`, `{"type": "solid", "color": …}`,
`{"type": "gradient", "gradient": {kind, stops}, "geom": {start, end, aspect, focal}, …}`,
`{"type": "pattern", "pattern": <name>, "xf": …}`. A **colour** is `{"model": "rgb", r, g,
b}`, `{"model": "cmyk", c, m, y, k}`, `{"model": "gray", k}` (k = black ink: 0 is white) or
`{"model": "lab", l, a, b}`; components are 0–1 (Lab: L 0–100, a and b about −128…127).

**Live effects** are `{"id": "<family>.<name>", "params": {…}, "visible": bool}`. The set of
ids is open. A reader draws the object without an effect it does not implement, and keeps the
effect when it writes the object back. `spec/examples/vector-art/effects.md` lists the ids
VectorCraft writes and the parameters of each.

**Type.** A `text` object has `runs`: `{"text": …, "style": {font_family, font_style, size,
fill, …}}` in reading order; U+000A ends a paragraph. `kind` is `{"kind": "point"}`,
`{"kind": "area", "frame": <path>}` or `{"kind": "onpath", "path": <path>, "start", "end"}`,
all in text space, which `xf` maps into the document. For point type the origin of text space
is the start of the first baseline, x along the baseline, y down. Line layout (which glyphs,
where lines break) is the reader's: the payload carries the text and its attributes, not glyph
positions. A reader that needs the exact look of the type without laying it out uses
`preview/artboard.svg`, where type is outlines.

## 5. Conventions and what each governs

Every value is in `MANIFEST.json` → `conventions`, pinned by the manifest schema.

| convention | value | governs | scope |
|---|---|---|---|
| `endianness` | `"le"` | any envelope binary of an `x.*` node, `core.embedding` | node |
| `alignment_bytes` | `16` | the same | node |
| `text_encoding` | `"utf-8"` | every text and JSON payload, `MANIFEST.json` | container |
| `id_case` | `"kebab-case"` | every node id | container |
| `hash_algorithm` | `"sha256"` | every hash | container |
| `signature_algorithm` | `"ed25519"` | `SIGNATURE.json` | signature |
| `length_unit` | `"point"` | every coordinate and length in the document, artboard, layer, symbol, pattern, styles and swatches payloads | node |
| `units_per_inch` | `72` | the same: 1 unit = 1/72 inch = 25.4/72 mm | node |
| `x_axis` | `"right"` | the same | node |
| `y_axis` | `"down"` | the same: larger y is lower; a rectangle's top edge is its smaller y | node |
| `angle_unit` | `"degree"` | every angle. Angles of gradients, pies, glyph rotation and `bbox_angle` are counter-clockwise AS SEEN ON SCREEN (so, with y down, clockwise in the coordinate plane's own sense: direction θ is the vector (cos θ, −sin θ)) | node |
| `affine_order` | `["a","b","c","d","e","f"]` | every transform: x′ = a·x + c·y + e, y′ = b·x + d·y + f | node |
| `curve_representation` | `"cubic-bezier-anchors"` | every path (§4) | node |
| `handle_coordinates` | `"absolute"` | anchors' `in` and `out` | node |
| `fill_rule_default` | `"nonzero"` | `path` and `compound` objects | node |
| `paint_order` | `"bottom-first"` | every list of layers, objects and appearance items | node |
| `stroke_miter_limit_default` | `10` | strokes: miter length ÷ stroke width past which a miter join is bevelled | node |
| `color_component_range` | `[0, 1]` | colour components, opacities, tints, gradient offsets | node |
| `color_space_rgb_default` | `"srgb"` | `rgb` colours when `color_profiles.rgb` is absent | node |
| `gray_polarity` | `"0-white-1-black"` | `gray` colours | node |
| `number_format` | `"shortest-round-trip-decimal"` | every JSON number: the shortest decimal that parses back to the same IEEE 754 value. Colour components, opacities, tints, gradient offsets and midpoints are binary32; every other number is binary64 | node |
| `pixel_origin` | `"top-left"` | `core.vector.image`, `core.vector.preview` | node |
| `alpha_mode` | `"straight"` | the same | node |
| `text_tracking_unit` | `"1/1000em"` | `tracking` and `kerning` of type | node |
| `time_base` | `"unix-seconds-utc"` | `metadata.created`, `metadata.modified` | node |

A reader that does not implement a node-scoped value refuses the node types it governs and
keeps everything else.

## 6. Reading

1. Open the container: a directory, or a store-mode zip (`spec/MINI-SPECS.md` §1).
2. Parse `MANIFEST.json`. Check `profile` is `vector-art/1` and each convention of §5.
3. `primary.document` → that node → its `active` version → its one file. Verify the file's
   sha256 against `files[].sha256`. Parse it: the structure.
4. For each node_id in `artboards`, then in `layers` (bottom first): node → `active` version →
   its payload file → verify → parse. If what you parsed has a member `external`, the payload
   is stored apart: verify and inflate the version's file of role `content` and parse that
   instead (§3.1). A node whose file is missing or fails its hash is dead: skip it, report it,
   continue.
5. Resolve what the layers name through the structure node's tables (§3.1): each `symbols[]`
   and `patterns[]` node, and for each image key `images[].node` (a PNG). The image's own file
   (`images[].original`), a font (`fonts[].source`) and a colour profile
   (`icc_profiles[].source`) are payloads in formats of their own: the node's
   `meta.payload_format` names the format, `MANIFEST.json` → `formats` its definition (§3.2).
6. Draw: layers bottom first, each object by §4.
7. Report the signature state in one of the four fixed words.

To read the document as it was at revision K: read record K of the `revisions` node
(`spec/CRAFT-BASE.md` §3); a node belongs to that revision only if the record lists it, and
"its `active` version" becomes "the version the record gives".

`spec/examples/vector-art/read_document.py` does steps 1–5 with the Python standard library
and prints the document as JSON: artboards, layers, every object with its geometry, paints and
text; with `--decode DIR` it also runs, on every payload in a foreign format, the reference
decoder the capsule carries for that format.

## 7. Writing a minimal valid `vector-art/1` capsule

This section is normative. A capsule built exactly as below is accepted by every
`vector-art/1` reader. `spec/examples/vector-art/write_minimal.py` does all of it with the
Python standard library and nothing else; it copies `loaders/` and `spec/` from any existing
`vector-art/1` capsule:

    python spec/examples/vector-art/write_minimal.py <existing capsule> <new.werk>

The document: one artboard 200 × 100 points, one layer, one red rectangle.

**7.1 The three payloads.** Each is one line of JSON followed by one line feed (`0x0A`),
UTF-8, no byte order mark. The bytes are in `spec/examples/vector-art/minimal/`.

`vector/artboards/artboard-1.json` — 89 bytes, sha256
`c317ee569895e512aab830a9caee0784cacc3370021b67eab3402f220c7bd67b`:

    {"schema_version":1,"id":1,"name":"Artboard 1","rect":{"x0":0,"y0":0,"x1":200,"y1":100}}

`vector/layers/layer-1.json` — 384 bytes, sha256
`69c19576e9a06c92cbb3357c7d95851ccb6e2cd3b99769c3e5e3c5a79326d850`:

    {"schema_version":1,"layer":{"id":1,"name":"Layer 1","kind":{"type":"layer","color":{"Preset":0},"children":[{"id":2,"name":"Red rectangle","appearance":{"items":[{"kind":"fill","paint":{"type":"solid","color":{"model":"rgb","r":1,"g":0,"b":0}}}]},"kind":{"type":"path","path":{"subpaths":[{"anchors":[{"p":[20,20]},{"p":[180,20]},{"p":[180,80]},{"p":[20,80]}],"closed":true}]}}}]}}}

`vector/document.json` — 87 bytes, sha256
`92c86b4bf15d587f5a610d9b7de016deed71c21c2e516741cf3bfdf88850da2d`:

    {"schema_version":1,"title":"Minimal","artboards":["artboard-1"],"layers":["layer-1"]}

If your hashes differ from these, you have a whitespace or line-ending difference; find it
before going further. (Any valid JSON spelling is a valid payload — these exact bytes are only
the checkpoint.) What the three say: the artboard is the rectangle (0,0)–(200,100); the layer
(object 1) holds one object (2), a closed path through (20,20), (180,20), (180,80), (20,80)
with no handles, i.e. four straight sides, filled with solid RGB (1, 0, 0) and not stroked; the
document lists the one artboard and the one layer.

**7.2 The base files.** Copy every current file under `loaders/` and `spec/` from the existing
capsule unchanged (skip files whose name carries an `@N` marker: superseded versions). Write
`LICENSE` (the full licence text of your content, or an honest statement that its terms are
not established); copy `README.txt` and `HOW-TO-READ.md`.

**7.3 The revision record** `revisions/revision.json`:

    {"schema_version":1,"revision":1,"kind":"save","note":"<why this file exists>",
     "created":"<RFC 3339 UTC>","producer":{"tool":"<your tool>","version":"<its version>"},
     "nodes":{"spec":1,"license":1,"readme":1,"loader-python":1,"loader-rust":1,
              "loader-c":1,"document":1,"artboard-1":1,"layer-1":1}}

**7.4 The manifest.** Ten nodes: `spec`, `license`, `readme`, `loader-python`, `loader-rust`,
`loader-c`, `revisions`, `document` (`core.vector.document`), `artboard-1`
(`core.vector.artboard`), `layer-1` (`core.vector.layer`). Each has one version:

    {"v":1, "files":[{"path":…,"sha256":…,"size":…}], "note":"<at least 8 characters>",
     "producer":{"tool":…,"version":…}, "epistemic":"authored", "created":"<RFC 3339 UTC>"}

with `"active":1` and `"edges":[]` — except `document`, whose edges are
`[{"to":"artboard-1","kind":"enhances","role":"contains"},
{"to":"layer-1","kind":"enhances","role":"contains"}]`. The `readme` version lists two files
and therefore carries `"payload_file":"README.txt"`. The three `core.loader` nodes carry the
`meta` block of the existing capsule unchanged. Copy `werk`, `profile`, `manifest_schema`,
`conventions_map`, `conventions` and `container` from the existing manifest; drop
`container.preview_prefix_bytes` (a hint) and set `container.total_size_bytes` to the sum of
the sizes of all the files you list. From the existing `schemas` and `layouts` maps keep only
the entries of the node types you wrote; leave `formats` out (no node you wrote is in a
foreign encoding). Set `primary` to `{"document":"document"}`, `license` to
`{"file":"LICENSE","sha256":<its sha256>}`, a fresh `entity.uuid`, and compute `spec_sha256`
by `spec/SPEC.md` §2 over every `spec/` path you list.

**7.5 The container.** A store-mode zip, `MANIFEST.json` first, then `LICENSE`, `README.txt`,
`HOW-TO-READ.md`, `loaders/…`, `spec/…`, `revisions/…`, `vector/document.json`, then the rest.

**7.6 Check.** `python loaders/werk_read.py <new.werk> --verify --strict` exits 0 and prints
`N/N files verified`.

**Going further.** Add a second layer: another `core.vector.layer` node, its node_id appended
to `layers` (it paints on top), one more `contains` edge, one more key in the revision record.
Add an image: a `core.vector.image` node with a PNG and `"meta": {"key": "<key>"}`
(`{"key_sha256": "<sha256 of the key>"}` when the key reads as a local file path), an entry
`{"key": "<key>", "node": "<node_id>"}` in `images`, and an `image` object naming the key.
Every payload you write must validate against its schema in `spec/schemas/`.

## 8. What this profile deliberately does not have

Named so that an absence reads as a decision:

* **No glyph positions.** Type is text and attributes; layout is the reader's. The SVG
  rendering carries outlines.
* **No expanded live objects.** A blend's steps, an envelope's distorted art, a repeat's
  copies, a live effect's result and a symbol instance's art are not stored; the reader
  computes them or draws the object without them. The PNG and SVG renderings show the result.
* **No node per object.** The unit of damage and of versioning is the top-level layer, the
  symbol, the pattern: an illustration can hold a hundred thousand paths, and a single-file
  capsule holds at most 65 534 files.
* **No node_ids inside object trees.** Trees name resources by the document's own names
  (§3.1), because a tree may legally name a resource the document does not have.
* **No references out.** A `link` records where a placed file came from; the file's content is
  in the capsule and the path is never followed.
* **No editing history beyond saves.** Undo steps are not stored; every save is a revision
  (`spec/CRAFT-BASE.md` §3) with a work note.

Within `vector-art/1`, evolution is additive only (law 12): a later revision of the profile may
add node types, optional members and enum values; a reader of this revision skips what it does
not know.
