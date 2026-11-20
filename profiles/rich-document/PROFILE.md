# `rich-document/1` — styled text documents

Status: in the release as a profile carried in its packages (SPEC §2.2). Origin: WordCraft
(ArtCraft suite), `werk-native` branch; copied unchanged except for the alignment edit below.

## 1. Where the definition is, and how it travels

The normative definition is the set of files under [`spec/`](spec/), carried as files of a
package's `core.spec` node beside the release `spec/`:

| file in the package | role |
|---|---|
| `spec/PROFILE-RICH-DOCUMENT.md` | the narrative; manifest `profile_spec` |
| `spec/schemas/manifest.rich-document.schema.json` | the manifest schema |
| `spec/conventions-map.rich-document.json` | manifest `conventions_map` |
| `spec/CRAFT-BASE.md`, `spec/NOT-CARRIED.md` | rules every ArtCraft profile shares |
| `spec/schemas/core.text.{document,blocks,properties,settings,comments,tracked-changes,bibliography}.schema.json`, `core.style.{sheet,numbering}.schema.json`, `core.chart.data.schema.json` | payload schemas (`core.text.blocks` also defines `$defs/BlockList`, the inflated blocks array) |
| `spec/schemas/x.wordcraft.*`, `spec/layouts/x.wordcraft.*` | WordCraft-only extensions (OOXML round trip) |
| `spec/examples/rich-document/` | worked examples, `read_document.py`, `write_minimal.py` |
| `spec/formats/zlib-deflate.md` (from [`../_formats/`](../_formats/)) | the blocks and plain-text compression, with its reference tool |

Format definitions named for embedded pictures, fonts and package parts (`jpeg`, `gif`, `bmp`,
`tiff`, `webp`, `emf-wmf`, `sfnt`, `cfb`, `ovba`, `zip`, `opc`) are not in this release except
`zip`; a package that embeds such a file must carry its definition.

## 2. Node kinds (summary; `spec/PROFILE-RICH-DOCUMENT.md` §3 is normative)

| type | count | payload |
|---|---|---|
| `core.text.document` | exactly 1 (`primary.document`) | JSON: the order of the body's runs, stories, pictures table, single-table node ids |
| `core.text.blocks` | per run of the body, per story | JSON header + the blocks as ONE zlib stream (role `blocks`), checked by `stored_*` / `inflated_*` |
| `core.style.sheet`, `core.style.numbering`, `core.text.settings`, `core.text.properties`, `core.text.comments`, `core.text.tracked-changes`, `core.text.bibliography` | 0..1 each | JSON |
| `core.media.image` | per picture | PNG (`meta.role` original or rendition) |
| `core.media.original` | per picture in another encoding | verbatim + format definition |
| `core.text.font`, `core.package.binary`, `core.package.text`, `core.chart.data` | 0..n | verbatim / JSON |
| `core.preview.text` | per run of the body | zlib stream of the run's plain text, `measured` (procedure `rich-document-plain-text-1`) |
| `core.preview.page` | 0..1 (`primary.preview`) | PNG |

A paragraph's `runs[].len` counts UTF-8 BYTES of its `text`. Conventions: 37, pinned (§5).

## 3. What a reader outputs (normative for the release reference reader)

`read_rich_document.py PACKAGE` prints one JSON object (UTF-8, keys sorted, indent 1):
`profile`, `properties` (payload), `style_ids`; `blocks` (the body's blocks, in order, as
stored); `block_count`; `tables` (each table as rows of cell texts, by the plain-text rule);
`media` (key, mediaType, imageIs, image node, PNG sha256 and size); `stories` (node, story,
plain text); `plain_text` (procedure `rich-document-plain-text-1`, §3.11, over the body) and
`plain_text_stored_matches` (whether the stored `core.preview.text` nodes equal it); `notes`,
`dead`, `files_verified`, `file_failures`. `--text` prints the plain text only. Not
implemented: style resolution, list numbering labels, layout, revisions.

## 4. The release fixture

[`../fixtures/rich-document-v1.werk`](../fixtures/) — "Harbour report": one run of the body
(a Heading 1, a paragraph with bold, italic and coloured runs and a three-byte character, an
inline picture with its caption in the Caption style, a second heading, a 4 × 6 table with a
bold header and total row, a closing italic paragraph), style sheet, properties, the picture
(a PNG byte-identical to the raster-layers/1 fixture's composite preview), the stored plain
text. Built by [`build_rich_document.py`](build_rich_document.py). The inflated blocks array
validates against `$defs/BlockList` ([`../tools/probe_blocklist.py`](../tools/probe_blocklist.py)).
