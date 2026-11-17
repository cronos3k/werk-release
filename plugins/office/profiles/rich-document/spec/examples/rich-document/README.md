# Worked examples of profile `rich-document/1`

Everything here is real: the payload files are byte for byte what the WordCraft application
writes for one small document ("Field notes"), and the two scripts run with the Python
standard library and nothing else.

## The document

"Field notes" has: a heading; a paragraph with a bold word, a footnote reference and a
commented range; a numbered list of two items; a table of two rows and two columns; a picture
(24 × 24 points, a 2 × 2 pixel PNG); a paragraph inserted with change tracking on; a page
header with a page-number field; A4 pages. It is set in Source Serif 4.

| file | payload of node | type |
|---|---|---|
| `document.example.json` | `document` | `core.text.document` — the structure |
| `blocks.example.json` | `body-000001` | `core.text.blocks` — the whole body (one run): the header |
| `blocks.example.blocks.zlib` | `body-000001`, its file with role `blocks` | the blocks, a zlib stream |
| `blocks.example.blocks.json` | — | what that stream inflates to: the blocks, as JSON you can read |
| `blocks-story.example.json`, `.blocks.zlib`, `.blocks.json` | `story-1` | `core.text.blocks` — the page header, the same three ways |
| `plain-text.example.txt.zlib` | `text-000001` | `core.preview.text` — derived from `body-000001`, a zlib stream |
| `plain-text.example.txt` | — | what that stream inflates to |
| `styles.example.json` | `styles` | `core.style.sheet` |
| `numbering.example.json` | `numbering` | `core.style.numbering` |
| `settings.example.json` | `settings` | `core.text.settings` (every field at its default) |
| `properties.example.json` | `properties` | `core.text.properties` |
| `comments.example.json` | `comments` | `core.text.comments` |
| `tracked-changes.example.json` | `tracked-changes` | `core.text.tracked-changes` |
| `bibliography.example.json` | `bibliography` | `core.text.bibliography` |

Not shown as files: the footnote (`story-2`) and the comment text (`story-3`), which look like
`blocks-story.example.json` with `"kind":"footnote"` / `"kind":"comment"`, the picture
(`media-image1-png-…`, a `core.media.image` node whose payload is the PNG itself), and the
font (`font-…`, a `core.text.font` node whose payload is the font file itself;
`document.example.json` → `fonts` names it).

How the pieces refer to each other, all by values you can see in the files:

* `document.example.json` → `body: ["body-000001"]`, `stories: ["story-1","story-2","story-3"]`,
  `media[0].key = "image1.png"`.
* `blocks.example.json` → `blocks.inflated_sha256` is the SHA-256 of
  `blocks.example.blocks.json`, and `blocks.stored_sha256` that of `blocks.example.blocks.zlib`.
* `blocks.example.blocks.json`, second paragraph: the text holds three U+FFFC characters;
  `objects[0]` is `{"type":"noteRef","kind":"footnote","id":2}` → the story whose
  `story.id` is 2; `objects[1]` and `objects[2]` are `commentStart` / `commentEnd` with
  `id: 0` → the entry with `id` 0 in `comments.example.json`, whose `part: 3` is the story
  that holds the comment's text.
* Its `runs` are `[{"len":4},{"len":5,"props":{"bold":true}},{"len":44}]`: bytes 0–3 `The `,
  bytes 4–8 `quick` (bold), the remaining 44 bytes plain. 4 + 5 + 44 = 53 = the UTF-8 length of
  the text (each U+FFFC is 3 bytes).
* The third and fourth paragraphs have `props.numbering = {"num":1,"level":0}` → the list with
  `id` 1 in `numbering.example.json`, which instantiates the definition with `id` 0.
* The first paragraph has `props.style = "Heading1"` → the style with that `id` in
  `styles.example.json`, based on `Normal`.
* The picture paragraph: `objects[0].media = "image1.png"` → the `media` entry with that key.
* The last paragraph's run has `props.ins = 0` → entry `id` 0 of
  `tracked-changes.example.json`: text inserted by "An Author" with change tracking on.
* `document.example.json` → `finalSection.headers.default = 1` → the story with `story.id` 1,
  the header in `blocks-story.example.json`. Its text ends in U+FFFC, a `field` object with
  the code `PAGE`; `result` is what it showed when saved.
* `plain-text.example.txt` is what the procedure of the profile document's §3.11 gives for
  `blocks.example.blocks.json`. The table rows are `Item<tab>Count` and `Apples<tab>3`; the picture
  paragraph is an empty line.

## A chart read from another format

`chart-data.example.json` is a payload of the `core.chart.data` node: the series of one chart
whose chart part (`word/charts/chart1.xml`) was preserved. Its `source`, `69497532ba3ed5a4`, is
the key of that chart in `embedded.example.json` → `objects`, and the value the chart's object
in the blocks carries as `ooxmlSource`.

## Extension nodes

`embedded.example.json` is a payload of the `x.wordcraft.ooxml.embedded` extension node
(original markup of one chart, and one piece of uninterpreted inline markup).
`part-descriptor.example.json` and `source-descriptor.example.json` are the descriptor files of
an `x.wordcraft.ooxml.part` node (a preserved package part in no defined format) and an
`x.wordcraft.source.other` node; their layout files are
`spec/layouts/x.wordcraft.ooxml.part.layout.txt` and
`spec/layouts/x.wordcraft.source.other.layout.txt`. A reader may skip all of them.

## The scripts

    python read_document.py FILE [--text | --json | --extract DIR] [--revision K]

reads any `rich-document/1` capsule: the executable form of the profile document's §6.

    python write_minimal.py <existing rich-document/1 capsule> <new.werk>

writes a new, valid, two-paragraph capsule from scratch: the executable form of §7. Its
docstring lists the sizes and SHA-256 values of the payloads it writes.
