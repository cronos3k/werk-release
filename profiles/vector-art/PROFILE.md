# `vector-art/1` — vector illustration documents

Status: in the release as a profile carried in its packages (SPEC §2.2). Origin: VectorCraft
(ArtCraft suite), `werk-native` branch; copied unchanged except for the alignment edit below.

## 1. Where the definition is, and how it travels

The normative definition is the set of files under [`spec/`](spec/). A package carries them
as files of its `core.spec` node, at the same paths, beside the release `spec/`:

| file in the package | role |
|---|---|
| `spec/PROFILE-VECTOR-ART.md` | the narrative; manifest `profile_spec` |
| `spec/schemas/manifest.vector-art.schema.json` | the manifest schema; manifest `manifest_schema` |
| `spec/conventions-map.vector-art.json` | manifest `conventions_map` |
| `spec/CRAFT-BASE.md`, `spec/NOT-CARRIED.md` | rules every ArtCraft profile shares |
| `spec/schemas/core.vector.{document,artboard,layer,symbol,styles}.schema.json`, `core.paint.{pattern,swatches}.schema.json`, `core.text.styles.schema.json` | payload schemas; manifest `schemas` |
| `spec/schemas/x.vectorcraft.*.schema.json`, `spec/layouts/x.vectorcraft.*.layout.txt` | VectorCraft-only extensions |
| `spec/examples/vector-art/` | worked examples, `read_document.py`, `write_minimal.py`, `effects.md` |

Release copies, provenance and the one alignment edit (loader capabilities): as for every
profile here, see [`../README.md`](../README.md), [`../VENDORED.json`](../VENDORED.json),
[`../ALIGNMENT.json`](../ALIGNMENT.json). Format definitions the profile names for embedded
originals (`jpeg`, `gif`, `bmp`, `tiff`, `webp`, `sfnt`, `icc`, `vectorcraft-native`) are not
in this release; a package that embeds such a file must carry its definition (CRAFT-BASE §6.1).

## 2. Node kinds (summary; `spec/PROFILE-VECTOR-ART.md` §3 is normative)

| type | count | payload |
|---|---|---|
| `core.vector.document` | exactly 1 (`primary.document`) | JSON: artboards and top-level layers by node id, library and font tables, settings |
| `core.vector.artboard` | 0..n | JSON: a named rectangle |
| `core.vector.layer` | 0..n | JSON `{schema_version, layer: <object tree>}`, or a stub with `external` + a zlib `content` file |
| `core.vector.symbol`, `core.paint.pattern` | 0..n | JSON (object trees) |
| `core.paint.swatches`, `core.vector.styles`, `core.text.styles` | 0..1 | JSON libraries |
| `core.vector.image` | 0..n | PNG |
| `core.vector.image-source`, `core.vector.placed-document`, `core.text.font`, `core.color.icc-profile` | 0..n | originals, verbatim, with a format definition |
| `core.vector.preview` | 0..1 (`primary.image`) | PNG, `measured` |
| `core.vector.svg` | 0..1 | SVG text, `measured` |

Object model (§4): objects `{id, kind:{type,…}}` of types layer, group, path, compound, text,
image, symbolinstance, blend, envelope, mesh, repeat, placeddocument; cubic Bézier anchors with
absolute handles; paints none / solid / gradient / pattern; colours rgb, cmyk, gray, lab;
live effects by id. Conventions: 25, pinned (§5).

## 3. What a reader outputs (normative for the release reference reader)

`read_vector_art.py PACKAGE` prints one JSON object (UTF-8, keys sorted, indent 1):
`profile`, `title`; `artboards` (node, id, name, rect); `layers` bottom first (node, the
complete `layer` object tree, external stubs resolved and checked); `libraries` (swatches,
graphic styles, text styles payloads); `symbols`; `images` (key, node, PNG sha256); `fonts`
(the structure node's table); `objects` (every object in tree order: id, kind, name, its path
in the tree); `object_counts`; `text` (the concatenated runs of each text object, paint order);
`preview` (node, width, height, sha256); `dead`, `files_verified`, `file_failures`. Exit 0 / 1
/ 2 as for every reader here. Not implemented: drawing, effects, type layout, revisions.

## 4. The release fixture

[`../fixtures/vector-art-v1.werk`](../fixtures/) — "Harbour Lights logo": one artboard
400 × 200 pt; layer "Mark" (a disc with a linear gradient, a beam with a radial gradient fading
to transparent, a group of four solid paths of which one is an even-odd compound path); layer
"Type" (point type in two runs, Source Sans 3 Bold and Regular, named and not embedded:
`status: not-requested`); a swatch library; a preview PNG rendered by the builder (type is not
drawn in it, and its `input_params` say `type_drawn: false`). Built by
[`build_vector_art.py`](build_vector_art.py). The whole package is embedded, byte for byte, in
the presentation/1 fixture.
