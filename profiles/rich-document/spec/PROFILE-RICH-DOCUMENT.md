# werk Profile: Rich Document — `rich-document/1`

Status: **v1.** Manifest schema: `spec/schemas/manifest.rich-document.schema.json`.
Conventions map: `spec/conventions-map.rich-document.json`.

A `rich-document/1` capsule is a rich-text document — the kind a word processor edits: text
with character and paragraph formatting, styles, lists, tables, pictures, drawings, equations,
sections with page setup, headers and footers, footnotes and endnotes, comments, tracked
changes, a bibliography — together with every state it was ever saved in. It is written by the
WordCraft application and is meant to be read and written by anyone who has this package and
nothing else. Every sentence here is meant to be implemented from.

The node types are named for what they hold (`core.text.*`, `core.style.*`, `core.media.*`),
not for the application: any application whose documents contain rich text may use them.

The manifesto's twelve laws govern everything here; where this document is silent, the laws
decide. It builds on, and does not restate:

* `spec/SPEC.md` — container (§1), manifest (§2), payload resolution (§2.1), versions (§5),
  signatures (§6), loaders (§7), reader checklist (§10);
* `spec/CRAFT-BASE.md` — what every ArtCraft capsule shares: the package root, the
  `revisions` node (§3), the path rules and the `@N` marker (§4), epistemic stamps (§5),
  encodings and format definitions (§6), signatures across Saves (§7), writing without
  ArtCraft software (§8), limits (§9);
* `spec/MINI-SPECS.md` — zip, JSON, UTF-8, PNG, SHA-256, Ed25519, byte by byte;
* `spec/formats/jpeg.md`, `gif.md`, `bmp.md`, `tiff.md`, `webp.md`, `emf-wmf.md` — the
  definition of each foreign picture encoding a `core.media.original` node may hold. Each
  says exactly what it covers and what it does not (§3.8);
* `spec/formats/zlib-deflate.md` — the compression of the text files (§3.2, §3.11);
  `spec/formats/sfnt.md` — font files (§3.13); `spec/formats/cfb.md`, `ovba.md`, `zip.md`,
  `opc.md` — the container formats of preserved package parts (§3.14).

A format's definition travels in a capsule only when a node of that capsule names the format
(`MANIFEST.json` → `formats`): a capsule without a JPEG carries no JPEG definition.

Every FIELD of every JSON payload — its type, unit, range, default and meaning — is in the
JSON Schema of its node type (`spec/schemas/`, one file per type; `MANIFEST.json` → `schemas`
names them). This document says how the nodes fit together; the schemas say what is in them.
`spec/examples/rich-document/` holds a real payload of every type and two standard-library
scripts: a reader (§6) and a writer (§7).

---

## 1. Container

Exactly `spec/SPEC.md` §1 and `spec/CRAFT-BASE.md` §1. The profile's own directories:

```
document/document.json            the structure node's payload (§3.1)
document/settings.json            properties.json  comments.json  tracked-changes.json  bibliography.json
document/chart-data.json          the data of charts read from another format (§3.15)
styles/styles.json                styles/numbering.json
text/<node_id>.json               the header of one run of the body or of one secondary story,
text/<node_id>.blocks.zlib        and its blocks, a zlib stream (§3.2)
media/<node_id>.png               a picture as PNG (§3.7)
media/<node_id>.<ext>             a picture's original bytes in a defined encoding (§3.8);
                                  <ext> is jpeg, gif, bmp, tiff, webp, emf or wmf
fonts/<node_id>.<ext>             a font file, verbatim (§3.13); <ext> is ttf, otf or ttc
package/<node_id>.<ext>           a part of the package the document was opened from, verbatim
                                  (§3.14); <ext> is cfb, bin, zip, xml or txt
preview/page-1.png                page 1 rendered (§3.12)
preview/text/<body node_id>.txt.zlib   the plain text of one run of the body, a zlib stream (§3.11)
tools/format-<id>-reference/      reference decoder (source) of each format in use
x/wordcraft/…                     extension nodes (§3.9, §3.10) — safe to skip
```

A path is a handle (`spec/CRAFT-BASE.md` §4). Nothing may be concluded from a path or a
node id: resolve every file through `MANIFEST.json` → `nodes[]` → `versions[]` → `files[]`.

**Preview tier** (law 9), in physical order in the zip form: the base tier (`MANIFEST.json`,
`SIGNATURE.json`, `LICENSE`, `README.txt`, `HOW-TO-READ.md`, `loaders/`, `spec/`,
`revisions/`), then `document/document.json`, then `preview/page-1.png`, then the rest of
`document/` and of `preview/`. A store that has fetched only that prefix can show the page
picture, the title, the outline of what the document contains, its plain text and its whole
save history without fetching a block of formatted text or a picture.
`container.preview_tier` lists these elements and is the authority.

**Container form.** A document is written as a single `.werk` file unless it would not fit
one (`spec/CRAFT-BASE.md` §9): WordCraft writes a NEW document as a directory when its files
exceed 3 500 000 000 bytes or 60 000 in number, and refuses — with a message naming the
directory form — a Save that would grow an existing single file past either number. The two
forms hold the identical tree and the identical `MANIFEST.json`.

## 2. MANIFEST.json

Validated by `spec/schemas/manifest.rich-document.schema.json`, which the manifest names in
`manifest_schema`. Relative to the reference's profile 2:

* `profile` is `"rich-document/1"`.
* `conventions` has 37 keys (§5).
* `primary.document` is REQUIRED: the node_id of the one `core.text.document` node.
* `primary.preview` is optional: the node_id of the `core.preview.page` node. Absent when
  the capsule was written without a page picture.
* `formats` maps each format id a node of this capsule names (`zlib-deflate`, `sfnt`,
  `jpeg`, `gif`, `bmp`, `tiff`, `webp`, `emf-wmf`, `cfb`, `ovba`, `zip`, `opc`), and each
  definition one of those requires, to its definition document (`spec/CRAFT-BASE.md` §6.1).
  A node names a format in `meta.payload_format` (the format of its payload file) or in
  `meta.file_formats` (an object: the `role` of one of its other files → format id).
* `entity.uuid` identifies the document. Every Save of the same document carries the same
  uuid; "Save As" keeps it (and the history); a duplicate made as a NEW document gets a new one.
* `entity.name` is a listing label (the title, else the file name). The document's title is
  in the `core.text.properties` payload (`core.title`), which is the authority.

## 3. Node families

| type | how many | payload | defined by |
|---|---|---|---|
| `core.spec`, `core.loader`, `core.license`, `core.readme`, `core.revisions` | base | — | `spec/CRAFT-BASE.md` §1, §3 |
| `core.text.document` | exactly 1 | JSON | `spec/schemas/core.text.document.schema.json` |
| `core.text.blocks` | 1 per run of the body, 1 per secondary story, 1 per note separator | JSON header + a zlib stream of JSON | `spec/schemas/core.text.blocks.schema.json`, `spec/formats/zlib-deflate.md` |
| `core.style.sheet` | 0 or 1 | JSON | `spec/schemas/core.style.sheet.schema.json` |
| `core.style.numbering` | 0 or 1 | JSON | `spec/schemas/core.style.numbering.schema.json` |
| `core.text.settings` | 0 or 1 | JSON | `spec/schemas/core.text.settings.schema.json` |
| `core.text.properties` | 0 or 1 | JSON | `spec/schemas/core.text.properties.schema.json` |
| `core.text.comments` | 0 or 1 | JSON | `spec/schemas/core.text.comments.schema.json` |
| `core.text.tracked-changes` | 0 or 1 | JSON | `spec/schemas/core.text.tracked-changes.schema.json` |
| `core.text.bibliography` | 0 or 1 | JSON | `spec/schemas/core.text.bibliography.schema.json` |
| `core.media.image` | 0 or more | PNG | `spec/MINI-SPECS.md` §8 |
| `core.media.original` | 0 or more | JPEG, GIF, BMP, TIFF, WebP, EMF or WMF, verbatim | `spec/formats/jpeg.md`, `gif.md`, `bmp.md`, `tiff.md`, `webp.md`, `emf-wmf.md` |
| `core.text.font` | 1 per font FILE the document is set in and may carry | a TrueType / OpenType file or collection, verbatim | §3.13, `spec/formats/sfnt.md` |
| `core.package.binary` | 0 or more | a compound file, a VBA project storage, a ZIP archive or an OPC package, verbatim | §3.14, `spec/formats/cfb.md`, `ovba.md`, `zip.md`, `opc.md` |
| `core.package.text` | 0 or more | UTF-8 text (XML or plain), verbatim | §3.14 |
| `core.chart.data` | 0 or 1 | JSON | §3.15, `spec/schemas/core.chart.data.schema.json` |
| `core.preview.text` | at most 1 per run of the body | a zlib stream of UTF-8 text | §3.11, `spec/formats/zlib-deflate.md` |
| `core.preview.page` | 0 or 1 | PNG | §3.12, `spec/MINI-SPECS.md` §8 |
| `core.tool` | 1 per reference implementation of a format definition in use | JSON + source | `spec/SPEC.md` §3.17, `spec/CRAFT-BASE.md` §6.1 |
| `core.disclosure`, `core.provenance`, `core.recipe`, `core.tool.config` | optional | JSON | `spec/SPEC.md` §3.11, §3.12, §3.17 |
| `x.wordcraft.ooxml.embedded` | 0 or 1 | JSON | `spec/schemas/x.wordcraft.ooxml.embedded.schema.json` |
| `x.wordcraft.ooxml.part` | 0 or more | opaque bytes | `spec/layouts/x.wordcraft.ooxml.part.layout.txt` |
| `x.wordcraft.source.other` | 0 or more | opaque bytes | `spec/layouts/x.wordcraft.source.other.layout.txt` |
| other `x.*` | optional | anything | the extension's own layout file |

WordCraft always writes the seven single JSON nodes, also when they are empty. A reader
accepts a capsule without them (§3.3 gives the value each one has when absent).

**Node ids** are stable handles: a node keeps its id for as long as the unit it holds
exists, through every Save, rename and reorder. WordCraft uses the ids below. A reader MUST
NOT rely on them: it finds every node through the structure node, and — when that node is
dead — through each node's own `type`, `story` and `meta`. A writer may use any ids
(kebab-case, `spec/CRAFT-BASE.md` §4).

| node | WordCraft's node_id |
|---|---|
| structure | `document` |
| a run of the body | `body-` + a number of at least 6 digits (`body-000017`); the number is never reused (§4) |
| a secondary story | `story-` + its `story.id` (`story-12`) |
| a note separator | `separator-footnote-separator`, `…-continuation-separator`, `…-continuation-notice`, and the same three with `endnote` |
| single nodes | `styles`, `numbering`, `settings`, `properties`, `comments`, `tracked-changes`, `bibliography` |
| a picture as PNG | `media-` + handle of its key; a picture's defined original: `original-` + the same handle |
| plain text of run `body-N` | `text-N` |
| chart data | `chart-data` |
| page picture | `preview-page-1` |
| a font file | `font-` + the first 16 hex digits of the SHA-256 of the file |
| a preserved package part | `part-` + handle of the part name |
| extensions | `x-ooxml-embedded`; `x-part-` + handle of the part name; `x-source-` + handle of the picture's key |

The handle of a name is: at most its first 40 characters, lower-cased, every run of
characters other than `a`–`z`, `0`–`9` replaced by one `-`, leading and trailing `-` removed;
then `-` and the first 6 hex digits of the SHA-256 of the name's UTF-8 bytes
(`image1.png` → `image1-png-94a7c7`).

### 3.1 `core.text.document` — the structure

One node, one file `document/document.json`, named by `primary.document`. It holds what
belongs to no unit: the ORDER of the body's runs (`body`), the list of secondary stories
(`stories`) and note separators (`noteSeparators`), the page setup of the last section
(`finalSection`), the pictures (`media`: key → the nodes that hold the bytes), which node
holds each single table (`styles`, `numbering`, `settings`, `properties`, `comments`,
`trackedChanges`, `bibliography`), the plain-text nodes (`plainText`), and the counter for
new body runs (`bodyNextId`), the fonts (`fonts`, §3.13), the preserved parts of the
package the document was opened from (`packageParts`, §3.14) and the chart-data node
(`chartData`, §3.15). It carries no text and no formatting.

Every string in it whose schema says `"format": "werk-node-ref"` is the `node_id` of a node
of this package that is part of the current document.

### 3.2 `core.text.blocks` — the text

A node of this type holds a list of **blocks** in reading order, and says in `story` what
they are, so that the node is meaningful alone. It has two files:

* the payload (role `payload`, the version's `payload_file`): a small JSON object, the
  **header** — `{"schema_version":1,"story":{…},"blocks":{…}}`. Its `blocks` member does not
  hold the blocks; it describes the file that does: `count` (how many blocks), `role`
  (`"blocks"`: the role of that file in this version's `files[]`), `format`
  (`"zlib-deflate"`), `stored_size` and `stored_sha256` (of the file as stored),
  `inflated_size` and `inflated_sha256` (of what it inflates to);
* the **blocks file** (role `blocks`): one zlib stream (RFC 1950, `spec/formats/zlib-deflate.md`).
  Inflated, it is UTF-8 JSON: ONE array, the blocks. WordCraft writes `[`, a line feed, one
  block per line with a comma between lines, and `]` with a line feed; any JSON spelling of
  the array is valid. The schema's `$defs/BlockList` validates the array.

A reader inflates the blocks file, checks size and SHA-256 against the header, and parses.
Text is compressed because it is the bulk of a document and compresses to about a fourteenth
(§4.1); the header stays plain JSON so that what a node is can be read without inflating
anything. `meta.file_formats` is `{"blocks":"zlib-deflate"}`. WordCraft compresses at zlib
level 6 with no preset dictionary; the same blocks always give the same bytes. A writer may
use any level, including stored blocks (level 0), which need no compressor (§7.1).

The `story` of the header:

* `{"kind":"body"}` — a run of the document's main text. The body is the concatenation of
  the `blocks` of the nodes in the structure's `body` array, in THAT array's order. Where one
  run ends and the next begins has no meaning: a writer may cut the body anywhere between
  two blocks, into any number of runs (§4 says how WordCraft cuts it and why).
* `{"kind":"header"|"footer"|"footnote"|"endnote"|"comment"|"textBox","id":N}` — one whole
  secondary story. `id` (an integer, unique among the stories of the document) is the value
  everything else refers to it by: a section's `headers` / `footers`, a note reference's
  `id`, a comment's `part`, a text-box shape's `story`.
* `{"kind":"noteSeparator","notes":"footnote"|"endnote","role":…}` — the blocks drawn
  between the page's text and its notes, when the document replaces the default rule.

**A block** is a paragraph or a table.

A **paragraph** is `{"kind":"para","text":…,"runs":[…]}` plus optional `props` (direct
paragraph formatting), `objects`, `mark` (formatting of the paragraph mark) and `section`.

* `text` is the paragraph's characters, UTF-8, stored as typed (no normalisation). Six
  characters in it have a fixed meaning: U+FFFC marks an inline object; U+000A is a manual
  line break inside the paragraph; U+0009 a tab; U+000C a page break; U+000E a column break;
  U+00AD an optional hyphen. A paragraph never contains its own end: one block is one
  paragraph.
* `runs` cut the text into stretches of equal character formatting. They are consecutive
  from byte 0, each `{"len":L,"props":{…}}`, and **`len` counts BYTES of the UTF-8 encoding
  of `text`**; the lengths sum to the byte length of `text`, and a run never ends inside a
  character. (A reader that finds runs covering fewer or more bytes applies what fits and
  treats the rest of the text as unformatted.) Example: text `Bold and plain.`, runs
  `[{"len":4,"props":{"bold":true}},{"len":11}]` — bytes 0–3 bold, bytes 4–14 not.
* `objects` are the inline objects, in text order: the k-th U+FFFC of `text` (k from 0) is
  `objects[k]`. An object has a `type`: `image` (a picture, by `media` key), `graphic` (a
  chart or diagram as drawing items), `shape`, `group`, `field` (a computed value: its code
  `instr` and the text it last showed, `result`), `fieldStart` / `fieldEnd` (a field whose
  result is ordinary document content between the two marks), `noteRef` (a footnote or
  endnote reference: the story with that `id`), `commentStart` / `commentEnd` (the range a
  comment is about), `bookmarkStart` / `bookmarkEnd`, `controlStart` / `controlEnd` (a
  content control: a form field wrapping content), `permStart` / `permEnd` (a range that
  stays editable in a protected document), `equation`, `ruby` (text with a pronunciation
  guide above it), `separatorLine` (the rule of a note separator), `opaque` (content of the
  original file format that this profile does not interpret: show its `text`).
* `section`, when present, says this paragraph is the LAST of a section that is not the
  document's last one, and holds that section's page setup; the next section starts with the
  next block. The last section's page setup is the structure's `finalSection`.

A **table** is `{"kind":"table","grid":[column widths in points],"rows":[…]}`; a row is
`{"cells":[…]}`; a cell is `{"blocks":[…]}` — blocks again, so tables nest. A cell that
spans columns has `props.span`; one merged with the cell above has `props.vmerge`.

**Formatting** is resolved in this order, later wins: the reader's defaults; the
stylesheet's `defaultChr` / `defaultPara`; the paragraph style's chain from the root of
`basedOn` down to the style named in `props.style`; a character style named in a run's
`props.style`; the direct properties in `props`. A property that is `null` or absent is "not
set here": it is inherited. This is why almost every property is optional.

**Lists.** A paragraph with `props.numbering = {"num":N,"level":L}` is item of list `N`
(the entry with that `id` in the numbering node's `nums`) at level `L` (0 = outermost). The
label is computed by the reader from the list's definition; it is not in the text.

**Lengths are points** (1/72 inch) unless a field's description says otherwise; colours are
`[red, green, blue]`, each 0–255, sRGB; angles are degrees, clockwise on the page. §5 lists
every convention.

### 3.3 The single tables

Each is one node with one JSON file. A reader that finds one absent uses the stated value.

| type | holds | when absent |
|---|---|---|
| `core.style.sheet` | document defaults and the named styles (`id` is what `props.style` names) | the reader's own defaults: every paragraph in its default font, no named style |
| `core.style.numbering` | list definitions (`abstracts`) and lists (`nums`) | list paragraphs are shown without labels |
| `core.text.settings` | document-wide switches: hyphenation, theme fonts, note numbering, protection, compatibility | every setting at the default its schema states |
| `core.text.properties` | title, author, dates (`core`); custom name/value properties (`custom`) | no title, no author |
| `core.text.comments` | one entry per comment: author, date, the story holding its text, the comment it replies to | comment ranges in the text have no author or date |
| `core.text.tracked-changes` | one entry per tracked change: kind, author, date (§4.2) | marks in the text that name an entry are treated as changes by an unknown author |
| `core.text.bibliography` | the sources that citations name by `tag` | citations show their cached text |

### 3.4 Edges, and which side dies

An edge reads "source → target". With `requires`, a dead TARGET kills the SOURCE; with
`enhances`, a dead target costs the source one feature (`spec/SPEC.md` §2).

| from | to | kind | role | why this kind |
|---|---|---|---|---|
| structure | each run of the body | `enhances` | `body` | a document with one unreadable run is still a document: a placeholder stands where the run was |
| structure | each story / note separator | `enhances` | `story` / `note-separator` | a document without one footnote is still a document |
| structure | the seven single tables | `enhances` | `styles`, `numbering`, `settings`, `properties`, `comments`, `tracked-changes`, `bibliography` | each has a stated fallback (§3.3) |
| structure | each picture node | `enhances` | `picture` (PNG), `picture-original` (original) | a missing picture is a placeholder box |
| structure | each plain-text node, the page picture, the chart data | `enhances` | `plain-text`, `preview`, `chart-data` | derived data: recomputable, or done without |
| chart data | each chart part it was read from | `requires` | `extracted-from` | numbers read from an unreadable part describe nothing |
| structure | each font file | `enhances` | `font` | without it a reader substitutes a font |
| structure | each preserved package part, core or extension | `enhances` | `package-part` | a lost part costs that part |
| structure | each other extension node | `enhances` | `preserved-markup`, `picture-original` | law 12: nothing core depends on an extension |
| plain text `text-N` | its run `body-N` | `requires` | `extracted-from` | text extracted from an unreadable run describes nothing |
| page picture | every core node it was rendered from, the font files included | `requires` | `rendered-from` | a picture of a page whose content is unreadable is not a preview of this document |
| page picture | originals held in extension nodes | `enhances` | `rendered-from` | law 12: a core node never requires an extension node |
| a PNG rendition | the picture's original | `enhances` | `rendition-of` | the rendition stands in for the original: it must SURVIVE a damaged original. (It is still a derived node: `measured`, with the original as its one input.) |

A blocks node has no edges. It refers to other units by VALUE — a story id, a media key, a
style id, a list id, a tracked-change id — which the reader resolves through the structure
node and the single tables. A value that resolves to nothing (a note reference to a story
that is dead) is a problem of that one value: the reader shows what it can (the reference
mark without the note) and continues.

### 3.5 Epistemic stamps and `meta`

Everything a person made — the structure, every blocks node, the single tables, an original
picture, a font file, a preserved package part, the extension nodes — is `authored`. Four
kinds of node are `measured`
(`spec/CRAFT-BASE.md` §5), each with `input_files`, `input_params` and `input_hash`:

| node | `input_files` | `input_params` |
|---|---|---|
| `core.preview.text` | the header file of its run (which pins the blocks by `inflated_sha256`) | `{"method":"rich-document-plain-text-1"}` (§3.11) |
| `core.media.image` with `meta.role` = `rendition` | the one file of the original | `{"method":"wordcraft-rendition-1"}` (§3.7) |
| `core.chart.data` | the chart parts (`core.package.text` nodes) it was read from, in ascending order of node id | `{"method":"drawingml-chart-cache-1"}` (§3.15) |
| `core.preview.page` | the structure, the seven single tables, the header of every run of the body, of every story and separator, every picture's original, every font file — in that order | `{"method":"wordcraft-page-render-1","page":1,"pixels_per_point":1,"fonts":"embedded-then-saving-machine"}` (§3.12) |

`meta` (current document only, not versioned):

* `core.media.image`: `width`, `height` (pixels), `role` (`original` or `rendition`),
  `original_media_type`, and `media_key` (a copy of the picture's key);
* `core.media.original`: `payload_format` (`jpeg`, `gif`, `bmp`, `tiff`, `webp` or
  `emf-wmf` — the key into `MANIFEST.json` → `formats`), and `media_key`;
* `core.preview.page`: `width`, `height`, `page` (1), `pixels_per_point` (1);
* `core.text.blocks`: `file_formats` (`{"blocks":"zlib-deflate"}`);
* `core.preview.text`: `payload_format` (`zlib-deflate`);
* `core.text.font`: `payload_format` (`sfnt`);
* `core.package.binary`: `payload_format` (`cfb`, `ovba`, `zip` or `opc`) and `part_name` (a
  copy of the part's name); `core.package.text`: `part_name`.

The `media_key` and `part_name` copies exist so that a reader that has lost the structure
node can still name its pictures and parts. The structure node is the authority. (A copy is
omitted when the name would read as a path on somebody's disk.)

### 3.6 What a reader does with a dead or unknown node

A node is dead when a file of it is missing or does not hash to its `sha256`, when its
payload fails its schema, or when a node it `requires` is dead. When the ACTIVE version of
a node is damaged and an earlier version is intact, a reader MAY load that earlier version
in its place and MUST say that it did (`version-fallback`). In every case the reader names
the node and continues. WordCraft does exactly this:

| dead node | the document that loads | the user is told |
|---|---|---|
| a run of the body | everything else; ONE paragraph stands where the run was: `[This part of the text could not be read from the file: node <id> is damaged.]` | "A part of the body text" |
| a story | everything else; references to that story id dangle (a note mark without a note, a section without that header) | "A header, footer, footnote, endnote, comment or text box" |
| the structure | all text, stories, tables and pictures, found by type, `story` and `meta.media_key`: body runs in ascending order of the number in their id (their order of CREATION — the reading order is lost if runs were ever reordered), the default page setup (612 × 792 points, 72-point margins) for the last section | "The document's structure: the order of the text, the page setup of the last section and the picture names were rebuilt from the other nodes" |
| a single table | the fallback of §3.3 | which table, and the fallback used |
| an original PNG (`role: original`) | the picture is missing; objects that name its key show an empty frame of the object's `w` × `h` | "The picture `<key>`" |
| a picture's original (`core.media.original` or `x.wordcraft.source.other`) | where the picture has a PNG rendition (§3.7), the rendition takes its place, under a key ending in `.png`, and every object that named the old key names the new one; where it has none, the picture is missing and objects that name its key show an empty frame | "The original bytes of the picture `<key>` (its PNG rendition is used where there is one)" |
| a PNG rendition | nothing is missing while the original is readable | nothing |
| plain text, page picture, chart data | nothing of the document | nothing; the node is listed as dead |
| `x.wordcraft.ooxml.embedded` | charts, diagrams and embedded objects still show (their drawing items and pictures are core); writing a .docx can no longer reproduce their original markup | "The exact original markup of charts, diagrams and embedded objects (they still show)" |
| a font file | everything; text set in that font is drawn in the reader's own copy of the font, else in a substitute, and lines may break elsewhere | "A font the document is set in (a similar font is used unless this computer has it)" |
| `core.package.binary`, `core.package.text`, `x.wordcraft.ooxml.part` | nothing visible; writing a .docx no longer reproduces that part | "A preserved part of the original .docx package (<name>)" |

A node of a type the reader does not know (`x.other.*`, or a `core.*` type of a later
revision of this profile) is **skipped and reported**, and a writer that saves the document
again carries it through unchanged — same bytes, same node id, still part of the document.

### 3.7 `core.media.image` — a picture as PNG

One node per picture, one file, a PNG (`spec/MINI-SPECS.md` §8). `meta.role` says which of
two things it is:

* `original` — the picture's own bytes: the author supplied a PNG, and this is it, byte for
  byte, in whatever bit depth and colour type its header declares.
* `rendition` — a PNG DECODED from a picture in another encoding, whose original bytes are
  kept verbatim in a `core.media.original` node (§3.8) or, failing a definition, in an
  `x.wordcraft.source.other` node (§3.9). It is 8 bits per channel RGBA, straight alpha, sRGB
  assumed, in the original's pixel size; the first frame of an animation; for a vector
  original (EMF, WMF) a rasterisation on white at up to 2048 pixels on its longer side.

**A rendition is written only where this package cannot give a reader the pixels
otherwise** — it is then the only copy whose pixels can be decoded from the package alone:

| the original | PNG rendition |
|---|---|
| JPEG whose frame is Huffman-coded baseline, extended or progressive with 8-bit samples (its first SOF marker is SOF0, SOF1 or SOF2 and the frame's precision is 8) | none: `spec/formats/jpeg.md` decodes it |
| any other JPEG (arithmetic-coded, lossless, hierarchical, 12-bit) | written |
| GIF | none: `spec/formats/gif.md` decodes it |
| BMP with a DIB header of 12, 40, 52, 56, 108 or 124 bytes, 1, 4, 8, 16, 24 or 32 bits per pixel, compression 0, 1, 2, 3 or 6 | none: `spec/formats/bmp.md` decodes it |
| any other BMP (an embedded JPEG or PNG, an OS/2 2.x header) | written |
| classic TIFF whose first image has Compression 1, 5, 8, 32773 or 32946, PhotometricInterpretation 0, 1, 2, 3 or 5 and SampleFormat 1 or 3 | none: `spec/formats/tiff.md` decodes it |
| any other TIFF (BigTIFF, CCITT, JPEG-in-TIFF, YCbCr, CIELab) | written |
| WebP (the definition covers the container, not the pixel bitstreams) | written |
| EMF, WMF (drawings) | written |
| bytes in no defined encoding that WordCraft can decode | written |

A photograph's PNG is several times the photograph, so a document full of JPEGs is not
stored twice. A writer may add a rendition to any picture; a reader never requires one.

The structure's `media` entry for the picture's key says which nodes exist: `original` (the
`core.media.original` node, or null), `image` (the PNG node, or null) and `imageIs`
(`original`, `rendition` or `none`). `imageIs` = `none` with an `original` is the ordinary
state of a JPEG: the picture is that node. A reader decodes the original with its own codec
or with the definition in this package; where a PNG exists, any reader can use the PNG.

### 3.8 `core.media.original` — a picture's original bytes in a defined encoding

One node per picture whose author-supplied bytes are JPEG, GIF, BMP, TIFF, WebP, EMF or WMF:
one file, those bytes verbatim, never re-encoded. `meta.payload_format` names the encoding;
`MANIFEST.json` → `formats[<that id>]` is the path of its **definition document** inside this
package (`spec/formats/jpeg.md` …): a byte-level definition with hash-checkable test
vectors, which also names a reference implementation that travels as source in a
`core.tool` node (`tools/format-jpeg-reference/jpeg_decode.py` …).

Each definition states exactly what it covers, and the differences matter to a reader:

| `payload_format` | what the definition in this package gives a reader |
|---|---|
| `jpeg` | the pixels (Huffman-coded baseline, extended and progressive, 8-bit). Lossy: two conformant decoders differ by a few levels of 255, and the definition says by how much |
| `gif` | the pixels of every frame, exactly |
| `bmp` | the pixels, exactly |
| `tiff` | the pixels, exactly, of classic TIFF and BigTIFF in strips or tiles, uncompressed, PackBits, LZW or Deflate; bilevel, greyscale, palette, RGB, CMYK; not CCITT, JPEG-in-TIFF |
| `webp` | the container: canvas size, frames, metadata. **Not the pixels** (the VP8 and VP8L bitstreams are not defined): use the PNG rendition |
| `emf-wmf` | the records as a display list (shapes, pens, brushes, text), not a rasterisation: use the PNG rendition for pixels |

A picture whose bytes lie outside what its definition covers (a JPEG-in-TIFF, an
arithmetic-coded JPEG) is still carried here, verbatim; the PNG rendition (§3.7) is then what
a reader without that codec shows.

Which encoding a picture is in is decided from its leading bytes — the definition's own
`sniff` rule — never from its key (a key may end in `.jpg` and name a PNG).

### 3.9 `x.wordcraft.source.other` — original bytes in no defined encoding

Bytes in an encoding WordCraft does not recognise, or that do not begin as the definition of
the encoding requires, are kept verbatim in an extension node, because this package carries
nothing from which their decoder could be built. Two files: the original (role `payload`)
and a `descriptor.json` (role `descriptor`) naming the picture's key;
`spec/layouts/x.wordcraft.source.other.layout.txt` gives the exact fields. Where WordCraft
can nevertheless decode the bytes, a `core.media.image` rendition stands beside the node;
where it cannot, the structure's `media` entry says `"imageIs":"none"`: that picture lives
only in the extension node, and a reader that skips extensions shows an empty frame.

### 3.10 `x.wordcraft.ooxml.*` — what is kept only to write a .docx back

A document opened from a WordprocessingML (.docx) file may contain things this profile does
not interpret. They are kept so that saving a .docx again loses nothing, and they are kept
OUT of the core nodes: **no core payload contains markup of another file format.**

* `x.wordcraft.ooxml.embedded` (one node, JSON) holds, by key: `objects` — the original
  markup of charts, diagrams, ink and embedded (OLE) objects; and `fragments` — small pieces
  of markup: an inline element this profile does not interpret, an equation's original
  markup, a content control's uninterpreted properties, a custom property of a type this
  profile does not interpret. A core object that has such an original carries the key in
  `ooxmlSource`. A reader that skips this node ignores every `ooxmlSource` and has the whole
  object: a chart is its drawing items, an embedded object its picture, an equation its
  `nodes` and `linear` text, an uninterpreted inline element its `text`.
* `x.wordcraft.ooxml.part` (one node per part, opaque bytes) holds a preserved package part
  that is in NO format this package can define: neither a compound file, a ZIP archive nor
  UTF-8 text (§3.14 says where every other part is). Examples: an embedded object stored as
  a bare binary stream, printer settings, an obfuscated embedded font.
  `spec/layouts/x.wordcraft.ooxml.part.layout.txt` gives the node's two files.

What a reader that skips every `x.*` node does NOT get, stated exactly — four things:

1. the original .docx MARKUP of charts, diagrams, ink, embedded objects, equations and
   uninterpreted inline elements (`x.wordcraft.ooxml.embedded`): what it loses is the ability
   to write that markup back, not the objects, which are core (below);
2. the VALUE of a custom property of kind `raw` (same node);
3. a picture that has neither a core original nor a PNG (`original` null and `imageIs`
   `none`: bytes in no defined encoding that WordCraft could not decode;
   `x.wordcraft.source.other`);
4. a preserved package part that is in no defined format (`x.wordcraft.ooxml.part`).

Everything else is in core nodes: every paragraph, table, picture, style, note, comment and
tracked change; every font file; and of the things a word processor embeds:

* a **chart** is an `objects[]` entry of type `graphic` with `graphic.kind` = `chart`. It
  always has `items`: what to draw, as shapes, paths and lines of TEXT in points (a display
  list, not pixels). Its DATA — chart type, title, category labels, every series with its
  name and its values as numbers — is in one of two places. A chart made in WordCraft, or
  one read from a file that holds no more than WordCraft's chart model, carries it in the
  object itself, as `graphic.chart` (`$defs/ChartSpec`). A chart read from another format
  that holds more (nearly every chart Microsoft Word writes: styles, axes options) has no
  `graphic.chart`; its data is in the `core.chart.data` node (§3.15), matched by the object's
  `ooxmlSource`. Its package parts (the chart XML, the workbook the numbers came from) are
  `core.package.*` nodes (§3.14);
* a **diagram** (SmartArt) is a `graphic` with `graphic.kind` = `diagram`: its drawn form as
  `items`, in which every piece of the diagram's text is a `text` item; and, for a diagram
  made in WordCraft, `graphic.smartArt` — the layout kind and the items' text as an outline
  (`$defs/SmartArtSpec`). The data-model parts of a diagram read from another format are
  `core.package.text` nodes;
* an **equation** is an `objects[]` entry of type `equation`: `nodes`, a tree of
  mathematical structure — fraction, radical, script, n-ary operator, delimiter, matrix,
  accent, function, run of text … (`$defs/MNode`; each node kind and its children are
  described there) — and `linear`, the same expression as one line of text;
* an **embedded object** (OLE) is its picture (a `media` key) plus, in a `core.package.binary`
  node, the object's own bytes in the compound-file format `cfb`;
* a **macro project** is a `core.package.binary` node in the format `ovba`, from whose
  definition the source text of every module can be read. Nothing in it is ever executed.

### 3.11 `core.preview.text` — the plain text of a run of the body

For search, and for a reader that wants words without formatting. One node per run of the
body whose text is not blank; one file: a zlib stream (RFC 1950; `meta.payload_format` is
`zlib-deflate`) that inflates to UTF-8 text with no byte order mark. The structure's
`plainText` array runs parallel to `body`: entry i is the text node of `body[i]`, or null.
The body's whole plain text is the concatenation of those inflated files in that order.

The text of a list of blocks is computed like this (the procedure named
`rich-document-plain-text-1`; `plain_text` in `spec/examples/rich-document/read_document.py`
is its executable form):

1. For each block in order, append the block's text.
2. A **paragraph** contributes its `text`, character by character, then one U+000A. In the
   text: the k-th U+FFFC is replaced by the plain text of `objects[k]` — a `field`'s
   `result`, an `equation`'s `linear`, a `ruby`'s `base`, an `opaque`'s `text`, and nothing
   for every other object type; U+000C and U+000E become U+000A; U+000A and U+0009 stay;
   every other control character (U+0000–U+001F, U+007F–U+009F) is dropped. The same
   replacement of control characters applies to the text an object contributes.
3. A **table** contributes one line per row: the texts of the row's cells joined by U+0009,
   then one U+000A. A cell's text is the text of its blocks by this same procedure, with
   trailing U+000A removed and every remaining U+000A replaced by one space. Tables nested
   more than 16 deep contribute nothing.

Text that is hidden, and text marked as deleted by a tracked change, IS included: both are
stored text. Headers, footers, notes, comments and text boxes are not part of the body and
are not included; their text is in their own blocks nodes.

A run whose text is blank (nothing but white space) has no text node: `plainText[i]` is
null.

Worked example: `spec/examples/rich-document/plain-text.example.txt` is the text of
`blocks.example.blocks.json`, and `plain-text.example.txt.zlib` is the file as stored.

### 3.12 `core.preview.page` — page 1 as a picture

One node, one PNG, named by `primary.preview`: the first page as WordCraft lays it out and
draws it, at 1 pixel per point (a 612 × 792 point page is 612 × 792 pixels), 8 bits per
channel RGBA, tracked changes shown as markup. It is drawn with the document's fonts: the
font files of the capsule are among its inputs, and a font that could only be named (§3.13)
was the saving computer's own copy or a substitute, which its `input_params` say
(`"fonts":"embedded-then-saving-machine"`). It is a preview: nothing may be measured from it.

### 3.13 `core.text.font` — the fonts, and the names of those that could not travel

A document names its fonts by family (`"font":"Source Serif 4"`); how its lines break
depends on the font files. The capsule therefore carries them (law 1): one node per font
FILE, the file byte for byte — a TrueType or OpenType font (`.ttf`, `.otf`) or a collection
(`.ttc`) — with `meta.payload_format` = `sfnt`, whose definition (`spec/formats/sfnt.md`)
and reference reader travel with it. A font file is never subsetted or re-encoded: a subset
is a different font file, and nothing here could prove that it lays the document out the
same.

Which fonts: every face that DRAWS a glyph of the document as WordCraft lays it out (all
pages; the faces that stood in for characters a font lacks included), and every family that
a run, a paragraph mark, a style, the document defaults or the theme NAMES.

A font's own licence bits decide whether its file may travel: OS/2 `fsType` (`spec/formats/sfnt.md`).
A face whose `fsType` has bit 1 set (value 2, "restricted licence embedding") and none of
bits 2 and 3 (preview-and-print, editable) is NOT embedded. Every other face is.

The structure's `fonts` array has one row per face, sorted by family, then style, then use:

| property | meaning |
|---|---|
| `family`, `style` | the face: `"Source Serif 4"`, `"Regular"` |
| `status` | `embedded` — the file is in this capsule; `restricted` — the saving computer had the font and its licence bits forbid passing it on; `missing` — the saving computer did not have it (the text was drawn with a substitute, which is itself listed with `use` = `fallback`) |
| `use` | `text` — a run or a paragraph mark names the family, or the face draws; `style` — only a style, the defaults or the theme name it; `fallback` — nothing names it: it drew characters another font lacked, or stood in for a font that was not there |
| `node` | with `embedded`: the `core.text.font` node holding the file |
| `faceIndex` | with `embedded`, when the file is a collection and the face is not its first: the face's index in the collection |

A reader that draws the document loads the embedded files before it lays out, and prefers
them to nothing: where the reader's computer already has a face of the same family and
style, WordCraft keeps the one it has. For a `restricted` or `missing` row the reader uses
its own copy of that family when it has one and a substitute otherwise, and says so — the
open result lists every such row with whether the font was found. With every row `embedded`,
a reader that has none of the fonts lays the document out as the writer did (verified by
WordCraft's tests: a process without the font renders page 1 to the identical bytes).

The row schema and the node type are shared with the other ArtCraft profiles that carry
fonts (`page-layout`): an embedded font means the same in each.

A font node is named by its content, so the same font is stored once however many Saves
follow, and a font that is no longer used leaves the document (§4.1).

### 3.14 `core.package.binary`, `core.package.text` — parts of the package the document came from

A document opened from a WordprocessingML (.docx) package may bring parts that are files in
their own right: the workbook behind a chart, an embedded (OLE) object, a macro project,
custom XML data, the XML of a chart or a diagram. WordCraft keeps each byte for byte, so
that saving a .docx again reproduces the package, and types each by what its bytes ARE:

| the part's bytes | node type | `meta.payload_format` | file |
|---|---|---|---|
| a compound file ([MS-CFB]: signature `D0 CF 11 E0 A1 B1 1A E1`, a valid header) named `…vbaProject.bin` | `core.package.binary` | `ovba` | `package/<node_id>.bin` |
| any other compound file — an embedded object | `core.package.binary` | `cfb` | `package/<node_id>.cfb` |
| a ZIP archive (local header `PK 03 04` and an end-of-central-directory record) whose part name ends in an Office extension (`.docx`, `.xlsx`, `.pptx`, their macro and template forms, `.vsdx`) | `core.package.binary` | `opc` | `package/<node_id>.zip` |
| any other ZIP archive | `core.package.binary` | `zip` | `package/<node_id>.zip` |
| UTF-8 text without a NUL character: XML (the name ends in `.xml` or `.rels`, or the text starts with `<`) | `core.package.text` | — (`media_type` `text/xml`) | `package/<node_id>.xml` |
| other UTF-8 text without a NUL character | `core.package.text` | — (`media_type` `text/plain`) | `package/<node_id>.txt` |
| anything else | `x.wordcraft.ooxml.part` (§3.10) | — | `x/wordcraft/parts/…` |

The format definitions say what each gives a reader: `cfb` the storages and streams of a
compound file; `ovba` the project's records and the source text of every module; `zip` the
members; `opc` the parts, content types and relationships of a package. What is INSIDE a
stream of an embedded object, or what the elements of a chart's XML mean, is the business of
the application that made it: a `core.package.text` node holding chart XML is readable as
text, and its vocabulary (ISO/IEC 29500 DrawingML) is not defined in this package. The
document does not depend on it: the chart's appearance is in the blocks and its data in the
blocks or in the `core.chart.data` node (§3.10, §3.15).

The structure's `packageParts` array has one row per part, in ascending order of name:
`{"name":…,"role":…,"node":…}`.

* `role` `package-part`: `name` is the part's name inside the original package, without a
  leading slash (`word/charts/chart1.xml`, `word/embeddings/oleObject1.bin`). It is a NAME
  that says where the bytes go when a .docx is written. It is not a path in this capsule and
  names no file on any disk.
* `role` `bookkeeping`: `name` starts with `wordcraft:`. The bytes are a small table WordCraft
  wrote itself, saying how the preserved parts were wired into the package. There are three
  (`wordcraft:embedded.parts`, `wordcraft:vbaProject.related`, `wordcraft:customXml.roots`).
  All three are UTF-8 text — so they are `core.package.text` nodes — one record per line,
  each line ended by U+000A, fields separated by U+0009; a field is never empty and never
  contains a tab, a carriage return or a line feed:

      wordcraft:embedded.parts      P <tab> part name <tab> content type
                                    R <tab> part name <tab> relationship id <tab> relationship type <tab> target <tab> I|E
      wordcraft:vbaProject.related  relationship type <tab> part name <tab> content type
      wordcraft:customXml.roots     owner <tab> relationship type <tab> part name

  A `P` line declares a part and its content type in the package's `[Content_Types].xml`; an
  `R` line is one relationship OF that part: the id its markup uses, the relationship type,
  and its target — for `I` (internal) the name of another preserved part, for `E` (external)
  a note of the outside address the original pointed at, which is never followed. All `P`
  lines come first, in ascending order of part name. `owner` is `P` when the package itself
  related to the custom XML part and `D` when the main document part did.

Nothing in a preserved part is ever executed, fetched or followed by a reader of this
profile. A part may contain addresses outside the package (a chart linked to a workbook
elsewhere); they are data.

### 3.15 `core.chart.data` — what the charts read from another format plot

One node (`chart-data`, `document/chart-data.json`), present when the document has a chart
whose data is not in its own object (§3.10). It is derived (`measured`): the series, category
labels and values that the preserved DrawingML chart parts cache, read out by the procedure
`drawingml-chart-cache-1`:

1. take every object of the `x.wordcraft.ooxml.embedded` node's `objects` that has an
   internal relationship of type
   `http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart`; the target
   is the name of a preserved part (a `core.package.text` node);
2. in that part's XML (root element `chartSpace`; element names are compared without their
   namespace prefix): every `ser` element whose parent's name ends in `Chart` is a series,
   and that parent's name without `Chart` is the series' `plot` (`bar`, `line`, `pie` …);
3. inside a series, a `v` element's text goes to the series' name when its nearest enclosing
   element among `tx`, `cat`, `xVal`, `val`, `yVal` is `tx`; to `categories` for `cat` or
   `xVal`; to `values`, parsed as a decimal number, for `val` or `yVal`. A `v` inside a `pt`
   element takes that point's `idx` attribute as its position; a `ptCount` element's `val`
   is the length of its list, and positions without a `v` are null (gaps). Everything inside
   `bubbleSize`, `errBars`, `trendline`, `dLbls` and `dPt` is ignored;
4. the chart's `type` is the `plot` of its first series; `title` is the concatenated text of
   the `t` elements inside the `title` element that is a child of `chart`; `barDirection`
   is the `val` of the first `barDir` element.

Each entry of `charts` has `source` — the string the chart's object carries as
`ooxmlSource`, so a reader pairs object and data by comparing two strings in core payloads —
and `part`, the name of the part. The values are the ones the source file cached for
display; a chart WordCraft's own model holds completely is not listed (its object has
`chart`). A reader that lost this node still has the chart as drawing items.

This is not the spreadsheet profile's `core.sheet.chart`: that node DESCRIBES a chart over
cell ranges (its series are references into a sheet); a document's chart has no sheet, so
its series are the literal labels and numbers. The property names agree where the meaning
does (`title`, `series`, a series' `name`, `categories`, `values`).

## 4. Versions

`spec/CRAFT-BASE.md` §3 and §4 apply unchanged. Every Save appends one revision record with
a note saying why the version exists (the note the user typed, or a one-line summary of what
changed that the application writes; an automatic save is noted `AutoSave.`).

### 4.1 What a Save appends

A Save declares every node of the document as it stands. A node whose bytes did not change
gains nothing. So:

* An edit inside one paragraph appends a version to the ONE run of the body that holds the
  paragraph, and to that run's plain-text node. Nothing else is written.
* Reordering whole runs, adding or removing a story or a picture appends a version to the
  structure node.
* Editing a header appends a version to that story's node only.
* Changing a style appends a version to the stylesheet node only.
* A node that is no longer declared leaves the document (the revision record no longer
  lists it) and its bytes stay in the file.

**How WordCraft cuts the body, and keeps the runs' identity.** The document model gives
paragraphs no identity, so the FILE owns it. A new body is cut into runs of about 32 768
bytes of payload: a run is closed when it reaches 32 768 bytes or 128 blocks, a heading
paragraph starts a new run once the current one holds at least 8 192 bytes, and a run always
ends where a section ends. Each run is a node `body-N`; N comes from the structure's
`bodyNextId`, which only grows. On every later Save the new body is aligned against the runs
the file holds, by the content of their blocks:

1. a run whose blocks all reappear, in order and adjacent, keeps its id and its bytes —
   also when it MOVED (a chapter dragged elsewhere);
2. blocks between two such runs go to the old runs that stood between them, which gain a
   version;
3. blocks inserted where no old run stood join the run before them while it stays within
   32 768 bytes and 128 blocks, and otherwise become new runs with new numbers;
4. a run that an edit made larger than 65 536 bytes or 256 blocks is split; its first part
   keeps the id.

Measured on a body of 2000 paragraphs — 472 301 bytes of block JSON, stored as 34 059 bytes
in 50 runs (headers and compressed blocks together): rewriting one paragraph re-stores 677
bytes of body (1.99 % of it) and 240 bytes of plain text; the 49 other runs exist once. A
reader needs none of this: it concatenates.

### 4.2 Tracked changes are not saved versions

Two different things are called "revisions" around a word processor. This profile keeps
them apart, and a reader must not confuse them:

* **Saved versions** are the werk revisions of `spec/CRAFT-BASE.md` §3: states of the FILE.
  Every Save appends one. No payload refers to them. They are listed by the `revisions`
  node, and "restore version 3" is a new revision that points back at it.
* **Tracked changes** are document CONTENT: text an author inserted or deleted while change
  tracking was on, still marked as such until someone accepts or rejects it. They live in
  the payloads: a run's `props.ins` / `props.del` (and a formatting change's `rev`) hold the
  `id` of an entry of the `core.text.tracked-changes` node, which says who and when. Deleted
  text is still in `text`, marked. Every saved version of the document carries its tracked
  changes as they were then.

Accepting a tracked change is an edit (a new saved version in which the mark is gone).
Restoring a saved version restores the tracked changes it held.

### 4.3 What a Save never does

A Save never removes or rewrites an earlier version. Removing old versions' bytes
("Reduce File Size") is a separate, explicit command that asks how many of the newest
versions to keep whole, is signed, and is logged in the file (`spec/CRAFT-BASE.md` §7); an
earlier revision then still opens, with a placeholder where a removed run was. A Save made
without signing after the document was signed leaves the signature
`present-and-invalid` until someone signs again; the chain is never stripped.

## 5. Conventions and what each governs

Every value below is a machine value in `MANIFEST.json` → `conventions`, pinned by the
manifest schema; `spec/conventions-map.rich-document.json` is the machine-readable form of
the "governs" column. Type names are shortened: `blocks` = `core.text.blocks`, `document` =
`core.text.document`, `sheet` = `core.style.sheet`, `numbering` = `core.style.numbering`,
`settings` = `core.text.settings`, `image` = `core.media.image`, `original` =
`core.media.original`, `page` = `core.preview.page`, `text` = `core.preview.text`.

| convention | value | governs | scope | meaning |
|---|---|---|---|---|
| `length_unit` | `"point"` | blocks, document, sheet, numbering, settings | node | Every length is in points unless its schema description names another unit. |
| `points_per_inch` | `72` | the same five | node | 1 point = 1/72 inch = 20 twips = 12700 EMU = 0.352777… mm. |
| `emu_per_inch` | `914400` | blocks | node | The one EMU-valued field: a text box story's `textBody.inset`. |
| `char_pitch_units_per_point` | `4096` | the same five | node | Unit of a document grid's `charSpace`: 1/4096 point. |
| `wrap_polygon_extent` | `21600` | blocks | node | A wrap polygon's coordinate space: 21600 units span the object's width, and its height. |
| `coordinate_origin` | `"top-left"` | blocks, image, original, page | node | Offsets, drawing items and pixels are measured from the top-left corner. |
| `axis_x` | `"right"` | blocks | node | x grows to the right. |
| `axis_y` | `"down"` | blocks | node | y grows downwards. |
| `angle_unit` | `"degree"` | blocks, sheet, numbering | node | Rotations, shadow and gradient directions. |
| `angle_direction` | `"clockwise"` | blocks, sheet, numbering | node | A positive angle turns clockwise as seen on the page (y down). |
| `text_offset_unit` | `"utf8-byte"` | blocks | node | A run's `len` counts bytes of the paragraph text's UTF-8 encoding. |
| `text_normalization` | `"none"` | the same five | node | Text is stored as authored; no Unicode normalisation is applied or assumed. |
| `object_char` | `65532` | blocks | node | U+FFFC in a paragraph's text marks an inline object: the k-th one is `objects[k]`. |
| `line_break_char` | `10` | blocks | node | U+000A in a paragraph's text is a manual line break within the paragraph. |
| `page_break_char` | `12` | blocks | node | U+000C in a paragraph's text is a page break. |
| `column_break_char` | `14` | blocks | node | U+000E in a paragraph's text is a column break. |
| `tab_char` | `9` | blocks | node | U+0009 in a paragraph's text is a tab. |
| `soft_hyphen_char` | `173` | blocks | node | U+00AD is an optional hyphen: shown only where a line breaks at it. |
| `nonbreaking_hyphen_char` | `8209` | blocks | node | U+2011 is a hyphen no line breaks at. |
| `nonbreaking_space_char` | `160` | blocks | node | U+00A0 is a space no line breaks at. |
| `color_model` | `"srgb"` | the same five | node | A colour is `[red, green, blue]`, sRGB (IEC 61966-2-1), no alpha. |
| `color_component_max` | `255` | the same five | node | Colour components are integers 0..255. |
| `percent_scale` | `100` | the same five | node | A value described as a percentage runs 0..100 (not 0..1), unless its description says fraction. |
| `number_precision` | `"binary32"` | the same five | node | Non-integer numbers are IEEE 754 binary32 values written in the shortest decimal form that reads back to the same binary32 (chart values: binary64). |
| `language_tags` | `"bcp-47"` | the same five | node | Languages are BCP 47 tags (`en-US`, `ja-JP`). |
| `date_format` | `"iso-8601"` | properties, comments, tracked-changes, blocks | node | Dates and times are ISO 8601 text (`2026-03-01T10:15:00Z`). |
| `image_bit_depth` | `8` | image, page | node | A rendition and the page preview are 8 bits per channel RGBA; an original PNG is whatever its own header says. |
| `image_alpha_mode` | `"straight"` | image, page | node | Alpha is not premultiplied. |
| `image_color_space` | `"srgb"` | image, page | node | Renditions and the preview are sRGB; an original PNG's own colour chunks win. |
| `preview_pixels_per_point` | `1` | page | node | The page preview is rendered at 1 pixel per point (72 dpi). |
| `line_ending` | `"lf"` | text | node | The plain-text derivative ends every paragraph and table row with U+000A. |
| `endianness` | `"le"` | `core.embedding`, any `x.*` envelope binary | node | Base convention; no node type of this profile is an envelope binary. |
| `alignment_bytes` | `16` | the same set | node | Base convention, as above. |
| `text_encoding` | `"utf-8"` | every text and JSON payload, including `MANIFEST.json` | container | |
| `id_case` | `"kebab-case"` | every id | container | Every id matches `^[a-z0-9]+(-[a-z0-9]+)*$`. |
| `hash_algorithm` | `"sha256"` | every hash | container | |
| `signature_algorithm` | `"ed25519"` | `SIGNATURE.json` only | signature | |

A reader that does not support a node-scoped value refuses the node types it governs and
still lists, verifies and extracts everything else. Example: a reader that cannot count
UTF-8 bytes (`text_offset_unit`) refuses `core.text.blocks` for formatting purposes and can
still take every paragraph's `text`.

## 6. Reading: the document in nine steps

`spec/examples/rich-document/read_document.py` does all of it with the Python standard
library.

1. Open the container (a directory, or a store-mode zip).
2. Parse `MANIFEST.json`. Check `profile` is `rich-document/1` and that each convention of
   §5 has the value of §5.
3. Find the current document: the record of the `revisions` node's `active` version
   (`spec/CRAFT-BASE.md` §3). Its `nodes` object says which nodes are part of the document
   and at which version. (No readable record: every node's `active` version, and say so.)
4. Take `primary.document` → that node → the version the record names → its one file.
   Verify the file's size and sha256 against the manifest. Parse it: the structure (§3.1).
5. For each node id in `body`, in order: that node → its version → its payload file → verify
   → parse: the header. Then the version's file with role `blocks` → verify → inflate (zlib)
   → check the inflated size and sha256 against the header → parse: an array of blocks
   (§3.2). Append them to the body. A dead node (§3.6): append the placeholder paragraph,
   name the node, continue.
6. For each node id in `stories` and `noteSeparators`: read it the same way; its `story`
   says what it is and under which `id` the rest of the document refers to it.
7. For each entry of `media`: if `original` names a node and you can decode its encoding
   (`meta.payload_format`; the definition is in this package), read that node's payload;
   otherwise read the PNG node named by `image` when `imageIs` is not `none`.
8. Read the single tables the structure names (§3.3); use the stated fallback for one that
   is absent or dead. To DRAW the document, load the font file of every `fonts` row whose
   `status` is `embedded` (§3.13) before laying out, and note the rows that are names only.
9. Report: the nodes that were dead, the nodes that were skipped (unknown types), and the
   signature state in one of the four fixed words (`signed-and-valid`, `absent`,
   `present-and-invalid`, `unverified`).

To read the document as it was at revision K, use record K in step 3. A version whose
record says `compacted` has no bytes any more: treat that node as dead for that revision.

For the words alone: after step 4, read the nodes named in `plainText`, inflate each and
concatenate.

Resolving a node's payload file is `spec/SPEC.md` §2.1: the version's `payload_file`, else
its only file, else the file whose `role` is `payload`. Never "the first file". (A blocks
node and an extension node have two files. The files of a superseded version, and its
`payload_file`, carry the `@N` marker of `spec/CRAFT-BASE.md` §4.)

## 7. Writing a minimal valid `rich-document/1` capsule

This section is normative. A capsule built exactly as below is accepted by every
`rich-document/1` reader, opens in WordCraft, and can be saved into by it.
`spec/examples/rich-document/write_minimal.py` does all of it with the Python standard
library and nothing else; run it against any `rich-document/1` capsule (it copies
`loaders/` and `spec/` from there):

    python spec/examples/rich-document/write_minimal.py <existing capsule> <new.werk>

The smallest document is a structure node and one run of the body. The steps, with the
values the script produces so that you can check your own implementation against them:

**7.1 The body.** A blocks node is two files (§3.2).

The blocks, before compression — two paragraphs, the second with a bold word. Four lines,
each ended by one line feed (`0x0A`), UTF-8, no byte order mark; 156 bytes, sha256
`e3accf6c015d73be5c749c01cbcd8718498c4cf99f9439d19171a83da86e5dc8`:

    [
    {"kind":"para","text":"Hello, werk.","runs":[{"len":12}]},
    {"kind":"para","text":"Bold and plain.","runs":[{"len":4,"props":{"bold":true}},{"len":11}]}
    ]

`len` counts bytes: `Hello, werk.` is 12 bytes; `Bold` is 4 and ` and plain.` is 11.

`text/body-000001.blocks.zlib` is those bytes as a zlib stream. No compressor is needed: a
zlib stream may hold its data in STORED blocks. For data of at most 65 535 bytes that is:
the two bytes `78 01`; the byte `01` (final block, stored); the data's length as two bytes,
low byte first; the same two bytes inverted (each bit flipped); the data; and the Adler-32
checksum of the data as four bytes, high byte first (`spec/formats/zlib-deflate.md`). For
longer data repeat the five-byte block header per 65 535 bytes, with `00` instead of `01` in
all but the last. The script does exactly this: 167 bytes, sha256
`db2370ffd562dee692eda074dee27b3113cd7aa7dbc698598109569e8da142d4`. (A writer that has a compressor uses it; WordCraft does.)

`text/body-000001.json` — the header. One line and one line feed; 312 bytes, sha256
`f1c694e138926da281a8f601143f8f24358d1b35119b79e8a5a87f018752915e`:

    {"schema_version":1,"story":{"kind":"body"},"blocks":{"count":2,"role":"blocks","format":"zlib-deflate","stored_size":167,"stored_sha256":"db2370ffd562dee692eda074dee27b3113cd7aa7dbc698598109569e8da142d4","inflated_size":156,"inflated_sha256":"e3accf6c015d73be5c749c01cbcd8718498c4cf99f9439d19171a83da86e5dc8"}}

`stored_*` are the size and SHA-256 of the `.zlib` file, `inflated_*` those of the 156 bytes.

**7.2 The structure.** `document/document.json` — one line and one line feed; 149 bytes,
sha256 `475be196cfbbf4e7546d3644e0eba3551139f0718005a31991113e7aa626a5f6`:

    {"schema_version":1,"body":["body-000001"],"bodyNextId":2,"finalSection":{},"stories":[],"noteSeparators":[],"media":[],"plainText":["text-000001"]}

`finalSection: {}` is a section with every property at its default: a 612 × 792 point page
with 72-point margins. `bodyNextId` is one more than the highest body number used.

If your hashes differ from these, you have a white-space or line-ending difference; find it
before going further. (Any valid JSON spelling is a valid payload — these exact bytes are
only the checkpoint.)

**7.3 The derived plain text** (optional; omit the node and the `plainText` property
together). The text — 29 bytes, sha256
`f2a1a185d8beee94a3c2f3cf785e462caa5c5f5555be736149d93f8bebc3c60b`:

    Hello, werk.
    Bold and plain.

`preview/text/body-000001.txt.zlib` is that text as a zlib stream, stored blocks as in 7.1:
40 bytes, sha256 `108a7b06b121cc87cc1885fd2eced08c09d9f75df4e190776c856a90d1ffdee1`.

Its version is `"epistemic":"measured"` with `"input_files":["text/body-000001.json"]`,
`"input_params":{"method":"rich-document-plain-text-1"}` and `input_hash` =
SHA-256 of (the 32 raw bytes of the header file's sha256, followed by the 39 bytes
`{"method":"rich-document-plain-text-1"}`) =
`09a55075cc8505563cb334a222529d8398a02be38dfebc1c4289a928cfab00b7`.

**7.4 The base files.** Copy every current file under `loaders/` and `spec/` from the
existing capsule unchanged (skip files whose name carries an `@N` marker — those are
superseded versions), except `spec/formats/`: of the format definitions copy
`spec/formats/zlib-deflate.md` only, the one format this capsule's files are in, and copy
the files of its reference decoder, the `core.tool` node `format-zlib-deflate-reference`
(under `tools/format-zlib-deflate-reference/`). Write `LICENSE` (the full licence text of your content, or an honest
statement that its terms are not established), `README.txt` and `HOW-TO-READ.md` (copy
them).

**7.5 The revision record** `revisions/revision.json`:

    {"schema_version":1,"revision":1,"kind":"save","note":"<why this file exists>",
     "created":"<RFC 3339 UTC>","producer":{"tool":"<your tool>","version":"<its version>"},
     "nodes":{"spec":1,"license":1,"readme":1,"loader-python":1,"loader-rust":1,
              "loader-c":1,"format-zlib-deflate-reference":1,"body-000001":1,
              "text-000001":1,"document":1}}

**7.6 The manifest.** Eleven nodes: `spec`, `license`, `readme`, `loader-python`,
`loader-rust`, `loader-c`, `revisions`, `format-zlib-deflate-reference` (`core.tool`, copied
with its `meta`), `body-000001` (`core.text.blocks`), `text-000001` (`core.preview.text`),
`document` (`core.text.document`). Each has one version:

    {"v":1, "files":[{"path":…,"sha256":…,"size":…}], "note":"<at least 8 characters>",
     "producer":{"tool":…,"version":…}, "epistemic":"authored", "created":"<RFC 3339 UTC>"}

with `"active":1`. Edges: `document` has
`[{"to":"body-000001","kind":"enhances","role":"body"},{"to":"text-000001","kind":"enhances","role":"plain-text"}]`;
`text-000001` has `[{"to":"body-000001","kind":"requires","role":"extracted-from"}]` and
its version is the `measured` one of 7.3; every other node has `"edges":[]`. The
`body-000001` version lists two files — the header with `"role":"payload"`, the blocks file
with `"role":"blocks"` — and carries `"payload_file":"text/body-000001.json"`; the node has
`"meta":{"file_formats":{"blocks":"zlib-deflate"}}`, and `text-000001` has
`"meta":{"payload_format":"zlib-deflate"}`. Set `"formats":{"zlib-deflate":"spec/formats/zlib-deflate.md"}`.
The `readme` version lists two files and therefore carries `"payload_file":"README.txt"`. The three
`core.loader` nodes carry the `meta` block of the existing capsule unchanged. Copy `werk`,
`profile`, `manifest_schema`, `conventions_map`, `conventions` and `container` from the
existing manifest, and from its `schemas` and `layouts` the entries of the node types you
use; drop `container.preview_prefix_bytes` (a hint) and set `container.total_size_bytes` to
the sum of the sizes of all the files you list. Set `primary` to
`{"document":"document"}`, `license` to `{"file":"LICENSE","sha256":<its sha256>}`, a
fresh `entity.uuid`, and compute `spec_sha256` by `spec/SPEC.md` §2 over every `spec/` path
you list.

**7.7 The container.** A store-mode zip, `MANIFEST.json` first, then `LICENSE`,
`README.txt`, `HOW-TO-READ.md`, `loaders/…`, `spec/…`, `revisions/…`,
`document/document.json`, `preview/…`, then `text/…` and `tools/…`. Or leave the tree as a
directory.

**7.8 Check.** `python loaders/werk_read.py <new.werk> --verify --strict` exits 0 and prints
`N/N files verified`; `python spec/examples/rich-document/read_document.py <new.werk> --text`
prints the two lines of 7.3 and says the stored text equals the recomputed one.

**Growing it.** Each further thing is one more node and one more entry in the structure:

* a footnote: a blocks node with `"story":{"kind":"footnote","id":2}`, listed in `stories`,
  and a `{"type":"noteRef","kind":"footnote","id":2}` object at a U+FFFC in the body;
* a picture: a `core.media.image` node holding a PNG with
  `meta {"width":…,"height":…,"role":"original","original_media_type":"image/png","media_key":"image1.png"}`,
  an entry `{"key":"image1.png","mediaType":"image/png","original":null,"image":"<node id>","imageIs":"original"}`
  in `media`, and an `{"type":"image","media":"image1.png","w":…,"h":…}` object (size in points);
* a JPEG (or GIF, BMP, TIFF, WebP, EMF, WMF): a `core.media.original` node holding the bytes with
  `meta {"payload_format":"jpeg","media_key":"photo.jpeg"}`, the entry
  `{"key":"photo.jpeg","mediaType":"image/jpeg","original":"<node id>","image":null,"imageIs":"none"}`,
  and, copied from a capsule that holds a JPEG: the `MANIFEST.json` → `formats` entries of
  `jpeg` and of every definition its header lists under `requires`, and the `core.tool` nodes
  those definitions name (`format-jpeg-reference` …) with their files under `tools/`;
* styles: a `core.style.sheet` node, named in the structure's `styles`;
* a font: a `core.text.font` node holding the font file with `meta {"payload_format":"sfnt"}`,
  a row `{"family":…,"style":…,"status":"embedded","use":"text","node":"<node id>"}` in the
  structure's `fonts`, and the `formats` entry and `core.tool` node of `sfnt`, copied from a
  capsule that holds a font. Embed a font only when its licence allows it (§3.13).

`spec/examples/rich-document/` shows each of these in a real document.

## 8. What this profile deliberately does not have

Named so that an absence reads as a decision, and so that a limit is not mistaken for a
promise:

* **No font the licence of which forbids it, and no font subsets.** Fonts travel whole
  (§3.13). A font whose own licence bits forbid embedding, and a font the saving computer
  did not have, are named and not carried: for those — and only those — a reader without the
  font substitutes one, and lines break elsewhere. Whole files cost bytes: a document set in
  one family carries that family's file (hundreds of kilobytes to a few megabytes), once,
  however many Saves follow.
* **No layout results.** Line breaks, page breaks and page numbers are computed by the
  reader; only authored breaks (U+000C, U+000E, a section's start) are stored. Two readers
  may paginate differently. The page preview shows page 1 only.
* **No evaluated fields.** A field stores its code and the text it last showed. A reader
  that does not evaluate field codes shows the stored text.
* **No dependency on anything outside the file.** A hyperlink target, a linked picture's
  former address, an attached template's former location are kept as TEXT the user or a
  later tool may act on; a reader never fetches them, and the document is complete without
  them. A picture that was only linked, never embedded, is not in the document.
* **No executable content.** A macro project read from a .docx is carried as data (§3.14)
  and never run.
* **No password protection or encryption.** WordCraft refuses to save a `.werk` with a
  password rather than write one that looks protected and is not.
* **No per-paragraph identity.** Identity is per node (a run of the body, a story). A
  paragraph is addressed by its position in its run.
* **No compression of the container.** Store-mode zip only (`spec/CRAFT-BASE.md` §9). The
  text files are zlib streams INSIDE it (§3.2, §3.11), declared by format; pictures and fonts
  are stored as they are.
* **No markup of another format in the document's content.** No node that holds text,
  formatting, styles or settings contains markup of another file format (§3.10). A preserved
  package part that IS such a file travels as that file (§3.14).
* **No chart linked to cells.** A chart holds its numbers (§3.10, §3.15); it is not a view
  of a spreadsheet range, which is what the spreadsheet profile's chart node is.

Within `rich-document/1` evolution is additive only (law 12): a later writer may add node
types and optional properties; it never changes the meaning of what is here.
