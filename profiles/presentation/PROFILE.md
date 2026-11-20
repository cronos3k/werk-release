# `presentation/1` — slide decks

Status: in the release as a profile carried in its packages (SPEC §2.2). Origin: DeckCraft
(ArtCraft suite), `werk-native` branch; copied unchanged except for the alignment edit below.
Compositional: a deck embeds pictures, documents and other werk packages as files, by content.

## 1. Where the definition is, and how it travels

The normative definition is the set of files under [`spec/`](spec/), carried as files of a
package's `core.spec` node beside the release `spec/`:

| file in the package | role |
|---|---|
| `spec/PROFILE-PRESENTATION.md` | the narrative (geometry, colours, inheritance, transitions, animations, the outline form); manifest `profile_spec` |
| `spec/schemas/manifest.presentation.schema.json` | the manifest schema |
| `spec/conventions-map.presentation.json` | manifest `conventions_map` |
| `spec/CRAFT-BASE.md`, `spec/NOT-CARRIED.md` | rules every ArtCraft profile shares |
| `spec/schemas/core.slide.{document,slide,master,layout,geometry}.schema.json`, `core.media.asset.schema.json` | payload schemas |
| `spec/schemas/x.deckcraft.ooxml.schema.json` | DeckCraft-only extension (OOXML round trip) |
| `spec/examples/presentation/` | worked examples, `read_presentation.py`, `write_minimal.py` |
| `spec/formats/zip.md`, `spec/formats/zlib-deflate.md` (from [`../_formats/`](../_formats/)) | definitions of the embedded zip file's encoding (`zip` requires `zlib-deflate`), each with its reference tool |

## 2. Node kinds (summary; `spec/PROFILE-PRESENTATION.md` §3 is normative)

| type | count | payload |
|---|---|---|
| `core.slide.document` | exactly 1 (`primary.document`) | JSON: slide size, slides in show order, masters with layouts, the media table |
| `core.slide.slide`, `core.slide.master`, `core.slide.layout` | per object | JSON |
| `core.media.asset` | per embedded file | JSON descriptor (`encoding`, `definition`) + the file, verbatim, role `media` |
| `core.media.image`, `core.media.audio` | per rendition / poster / excerpt | PNG / WAV, `measured` from the asset |
| `core.slide.geometry` | 0..1 per owner | JSON: resolved preset outlines, `measured` |
| `core.slide.preview` (`primary.image`), `core.slide.outline` | 0..1 | PNG / UTF-8 text, `measured` |

**Reuse by content.** An embedded file is carried byte for byte; nothing is re-encoded. A
vector-art/1 or raster-layers/1 package embedded in a deck is a `core.media.asset` of encoding
`zip` (definition `formats`); its file has the same sha256 as the package itself, so a content
store keeps one copy, and a PNG rendition stands in for readers that only show pictures.
Conventions: 28, pinned (§5).

## 3. What a reader outputs (normative for the release reference reader)

`read_presentation.py PACKAGE` prints one JSON object (UTF-8, keys sorted, indent 1):
`profile`, `title`, `slide_size`; `masters` (id, node, name, layouts: id, node, name, kind);
`slides` in show order (id, node, layout id, `title` by §6 step 6, hidden, `shapes` — id, name,
type, xfrm, placeholder kind, hidden, paragraph texts, picture `media` id, table `cells` — and
`notes`); `media` (id, node, name, encoding, definition, content type, embedded, sha256 and size
of the `media` file, sha256 and pixel size of rendition / poster / excerpt); `outline` (§3.6,
recomputed) and `outline_matches` (whether the stored outline node equals it); `dead`,
`files_verified`, `file_failures`. `--media DIR` writes every embedded file. An embedded werk
package is listed, never opened. Not implemented: drawing, inheritance, colour transforms,
animations, revisions.

## 4. The release fixture

[`../fixtures/presentation-v1.werk`](../fixtures/) — "Harbour Lights review", 960 × 540 pt,
one master, two layouts, three slides (title slide with the logo; a photograph with caption; a
cost table with speaker notes). Media 10 is the vector-art/1 fixture package itself (sha256
equal to `vector-art-v1.werk`), with its preview PNG as rendition (sha256 equal to that
package's preview node); media 11 is the raster-layers/1 fixture's composite PNG (equal to the
rich-document/1 fixture's picture). The stored outline. Built by
[`build_presentation.py`](build_presentation.py).
