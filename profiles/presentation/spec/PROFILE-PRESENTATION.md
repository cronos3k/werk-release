# werk Profile: Presentation — `presentation/1`

Status: **v1.** Manifest schema: `spec/schemas/manifest.presentation.schema.json`.
Conventions map: `spec/conventions-map.presentation.json`.

A `presentation/1` capsule is one slide deck: slides with their shapes, text, speaker notes,
transitions, animation timelines and review comments; the masters and layouts the slides are
built on, with their themes; and every picture, sound, video and font the deck embeds. It is
the native format of DeckCraft. The node types named `core.*` below are meant to be read and
written by any program, and this document, the JSON Schemas in `spec/schemas/` and the format
definitions in `spec/formats/` are everything such a program needs. Nothing here says "as
DeckCraft does it".

The manifesto's twelve laws govern everything; where this document is silent, they decide. It
builds on, and does not restate:

* `spec/SPEC.md` — container (§1), manifest (§2), which file is a node's payload (§2.1),
  versions (§5), signatures (§6), loaders (§7), reader checklist (§10);
* `spec/CRAFT-BASE.md` — what every ArtCraft capsule shares: the package root, the `revisions`
  node, paths and the `@N` marker, epistemic stamps, foreign-encoded files and their format
  definitions (§6.1), signatures across saves, writing a capsule without ArtCraft software;
* `spec/MINI-SPECS.md` — zip, JSON, UTF-8, SHA-256, PNG, WAV, byte by byte.

Where this document and a schema disagree about a payload, the schema wins for that payload.

---

## 1. Container

Exactly `spec/SPEC.md` §1 and `spec/CRAFT-BASE.md` §1. The profile's own files:

```
deck/document.json                 the structure node's payload
deck/slides/<node id>.json         one file per slide
deck/masters/<node id>.json        one file per master
deck/layouts/<node id>.json        one file per layout
deck/geometry/<owner node id>.json the resolved shape outlines of one slide, layout or master
media/<node id>/asset.json         the descriptor of one embedded file
media/<node id>/media.<ext>        that file, byte for byte
media/renditions/<asset id>.png    a picture decoded to PNG
media/posters/<asset id>.png       one frame of a video
media/excerpts/<asset id>.wav      the first seconds of a sound
preview/slide.png                  the first slide as a picture
preview/outline.txt                the text of every slide
x/deckcraft/ooxml/<owner id>.json  XML kept from an imported file (§3.7)
```

These paths are where DeckCraft puts the files. A reader never relies on them: it finds every
file through `MANIFEST.json` (`nodes[].versions[].files[]`).

**Preview tier** (law 9), physically first in the zip form: the base tier (`MANIFEST.json`,
`SIGNATURE.json`, `LICENSE`, `README.txt`, `HOW-TO-READ.md`, `loaders/`, `spec/`,
`revisions/`), then `deck/document.json`, then `preview/`. A store that has fetched only that
prefix can show the deck's title, its slide count, a picture of its first slide and the text
of every slide. `container.preview_tier` lists these elements and is the authority.

## 2. MANIFEST.json

Validated by `spec/schemas/manifest.presentation.schema.json`, which the manifest names in
`manifest_schema`.

* `profile` is `"presentation/1"`.
* `conventions` has the keys of §5.
* `primary.document` is REQUIRED: the node_id of the one `core.slide.document` node.
  `primary.image` is the node_id of the `core.slide.preview` node; it is absent when the deck
  has no slide or the writer has no renderer.
* `formats` maps the id of every foreign media format present AND defined in this package to
  its definition document (`spec/CRAFT-BASE.md` §6.1). §3.3 says which formats those are.
* `entity.uuid` identifies the document: every save of the same document carries it; a
  duplicate gets a new one. `entity.name` is a listing label (the title on one line); the title
  itself is `props.title` in the structure node's payload.

## 3. Node families

| type | how many | payload | defined by |
|---|---|---|---|
| `core.spec`, `core.loader`, `core.license`, `core.readme`, `core.revisions` | base | — | `spec/CRAFT-BASE.md` §1, §3 |
| `core.tool` | one per format definition that has a reference decoder | JSON + source | `spec/SPEC.md` §3.17, `spec/CRAFT-BASE.md` §6.1 |
| `core.slide.document` | exactly 1 | JSON | `spec/schemas/core.slide.document.schema.json` |
| `core.slide.slide` | 0 or more | JSON | `spec/schemas/core.slide.slide.schema.json` |
| `core.slide.master` | 0 or more | JSON | `spec/schemas/core.slide.master.schema.json` |
| `core.slide.layout` | 0 or more | JSON | `spec/schemas/core.slide.layout.schema.json` |
| `core.media.asset` | 0 or more | JSON, plus the embedded file (role `media`) | `spec/schemas/core.media.asset.schema.json`; the file: §3.3 |
| `core.media.image` | 0 or more | PNG | `spec/MINI-SPECS.md` §8 |
| `core.media.audio` | 0 or more | WAV | `spec/MINI-SPECS.md` §9 |
| `core.slide.geometry` | 0 or more | JSON | `spec/schemas/core.slide.geometry.schema.json` |
| `core.slide.preview` | 0 or 1 | PNG | `spec/MINI-SPECS.md` §8 |
| `core.slide.outline` | 0 or 1 | UTF-8 text | §3.6 |
| `x.deckcraft.ooxml` | optional | JSON | `spec/schemas/x.deckcraft.ooxml.schema.json` |
| any other `x.*` | optional | anything | the extension's own layout file |

Every JSON payload is an object with `"schema_version": 1`. Any valid JSON spelling is a
valid payload. What DeckCraft writes, so that a payload is small and still reads and compares
line by line: keys sorted by their UTF-8 bytes, no indentation and no spaces, one line per
member of the payload object and one line per member or element of each of those (a slide is
one shape per line), everything deeper on that line; one line feed at the end. The examples
under `spec/examples/presentation/` are the same payloads indented for reading.

### 3.1 The structure node, and how its parts are named

**`core.slide.document`** — node_id `document`, one file. It lists the slides in show order
and the masters with their layouts, each by node_id; it holds the table of embedded files; and
it holds what belongs to no single slide: the slide size, sections, custom shows, slide-show
settings, header and footer settings, document properties, the default text style. It carries
no slide content. `primary.document` names it.

**Three kinds of name** occur inside payloads, and a reader resolves each the same way:

1. **A node_id** (`"slide-12"`, `"master-3"`). Every such member is declared in its schema with
   `"format": "werk-node-ref"`: the structure node's tables, a layout's `master`, the `owner`
   of a geometry or kept-XML node. Resolve it through `MANIFEST.json` → `nodes[]`.
2. **An object id** (an unsigned integer): what the CONTENT uses. A slide names its layout by
   the layout's `id`; a picture, a bullet, a sound names its embedded file by the media `id`;
   a hyperlink names a slide by the slide's `id`. Resolve one through the structure node's
   tables: `slides[]`, `masters[].layouts[]` and `media[]` each map `id` → `node`. When two
   entries of a table carry the same id, the FIRST is meant. An id with no entry names nothing
   — a picture whose media id has no entry is an empty box, a link to a slide that is not there
   does nothing — and that is a legal document which a writer keeps as it is.
3. **A shape id**: every shape has an `id`, unique among the shapes of its slide (members of
   groups included). Animations (`shape`, `trigger`), comments (`shape`) and connectors
   (`start.shape`, `end.shape`) name shapes of the SAME slide by it.

### 3.2 Slides, layouts, masters

**`core.slide.slide`** — one node per slide; node_id `slide-<id>` where `<id>` is the slide's
own `id` (never its title or its position). Payload `{"schema_version": 1, "slide": {…}}`: the
slide's shapes (bottom first), background, speaker `notes`, `transition`, `animations` and
`comments`. Reordering slides changes only the structure node.

**`core.slide.master`** — one node per master; node_id `master-<id>` for a slide master,
`notes-master` for the master of notes pages, `handout-master` for the master of printed
handouts. Payload `{"schema_version": 1, "role": "slide"|"notes"|"handout", "master": {…}}`:
the theme (twelve colours, two font sets, a format scheme), the master's shapes, its
background, the three text-style lists and the colour map. Its layouts are separate nodes.

**`core.slide.layout`** — one node per layout; node_id `layout-<id>` (`notes-layout-<id>`,
`handout-layout-<id>` under the other two masters). Payload
`{"schema_version": 1, "master": "<node_id of its master>", "layout": {…}}`.

When two objects of one kind carry the same `id` (it happens in imported files), the second
and later get node_ids with a suffix `-d1`, `-d2`, …; nothing is ever looked up by parsing a
node_id.

### 3.3 Embedded files

**`core.media.asset`** — one node per embedded file; node_id `media-<id>` where `<id>` is the
media id. The node has TWO files:

* its payload `asset.json` (named by the version's `payload_file`): the media `id`, the file's
  original `name`, the `content_type` the source declared, whether bytes are `embedded`, a
  `link` note for an item that was only linked, and what the bytes are (`encoding`,
  `definition`);
* the file itself, the ONE file of the version whose `role` is `media`: the bytes exactly as
  they were embedded. Nothing is re-encoded, ever. It is absent when `embedded` is false.

To get the bytes of media id N: structure node `media[]` → entry with `id` N → `node` → that
node's version → the file with `role: "media"`. **Do not take `files[0]`, and do not take the
payload:** the payload is the descriptor.

What the bytes are is recognised by the writer from their first bytes, never from the name, and
stated in `encoding`. `definition` says where a definition of that encoding is, from which a
decoder can be built:

| `definition` | `encoding` | where the definition is |
|---|---|---|
| `base` | `png`, `wav` | `spec/MINI-SPECS.md` §8, §9 |
| `formats` | `jpeg`, `gif`, `bmp`, `tiff`, `webp`, `sfnt`, `emf-wmf`, `pdf`, `zip`, and any of `isobmff`, `matroska`, `ogg`, `mp3`, `flac`, `aiff`, `aac` whose definition this package holds | `MANIFEST.json` → `formats[<encoding>]` → `spec/formats/<encoding>.md`; the node's `meta.file_formats` is `{"media": "<encoding>"}`; a reference implementation in source is the `core.tool` node the definition's header names. Each definition states what it covers in its `coverage_note` — read it: the `webp` one defines the container and NOT the picture bitstreams |
| `pending` | `isobmff`, `matroska`, `ogg`, `mp3`, `flac`, `aiff`, `aac` (when `MANIFEST.json` `formats` has no entry of that name), `caf`, `asf`, `rf64`, `svg`, `unknown` | NOT in this package |
| `none` | `none` | there are no bytes |

**`pending` is a stated gap, not a convention.** The video, audio and embedded-document
formats in that row are public standards, the file is carried byte for byte
and is hash-checked like every other file, and this profile's format library does not yet hold
a definition of them. The node type is the one such a file keeps when its definition exists:
the definition document then joins `spec/formats/`, the node gains
`meta.file_formats = {"media": "<id>"}`, `definition` becomes `formats`, and neither the node
type, nor the node_id, nor the bytes change. Until then a reader that needs the content of
such a file must bring its own decoder; for a video and a sound it can use the derived
renditions below without one. What the names mean: `isobmff` = ISO base media file
format (MP4, MOV, M4A); `matroska` = Matroska or WebM; `ogg` = an Ogg stream; `aac` = AAC in
ADTS frames; `asf` = Advanced Systems Format (WMA, WMV); `rf64` = a WAVE file with 64-bit
sizes; `caf` = Core Audio Format; `svg` = an SVG document; `zip` = a zip package (an embedded
workbook or document). The `definition` member of the descriptor, and nothing else, says
which of the two rows a file is in: the same `encoding` name is `pending` in a package written
before the format library defined it and `formats` in one written after. Of the defined ones: `sfnt`
= a TrueType/OpenType font or collection; `emf-wmf` = a Windows or Enhanced Metafile.

A `link` is text about where a linked item was when the document was made. A reader never
follows it and never needs it.

### 3.4 What is decoded from an embedded file

Where the writer can decode an embedded file it also writes a boring rendition, as a node of
its own. The structure node's `media[]` entry names them:

* `rendition` → a **`core.media.image`** node (node_id `<asset>-png`, `meta.role`
  `rendition`): a picture that is not a PNG, decoded to PNG — 8 bits per channel, RGBA,
  straight alpha, row 0 at the top, the first frame of an animation. A reader that knows only
  PNG shows this for the media id.
* `poster` → a **`core.media.image`** node (node_id `<asset>-poster`, `meta.role` `poster`):
  the frame of a video shown at time 0, as PNG, at the video's own pixel size.
* `excerpt` → a **`core.media.audio`** node (node_id `<asset>-excerpt`, `meta.role`
  `excerpt`): the first `excerpt_seconds` (5) seconds of a sound, or of a video's sound track,
  as a canonical WAV: 44-byte header, PCM (format tag 1), signed 16-bit little-endian,
  interleaved, at the source's sample rate and channel count.

Each is stamped `measured`: its version lists the asset's `media` file in `input_files`, and
`input_params` records the decoder and its settings. `meta.of` is the asset's node_id. They are
conveniences: the document's content is the asset. A writer without a decoder writes none, and
the `media[]` entry then has `null` (or nothing) for that member.

### 3.5 Resolved outlines — `core.slide.geometry`

A shape's outline is either explicit (`geom.kind: "custom"`, §4.4) or a named preset
(`geom.kind: "preset"`). The presets are a large family; §4.4 defines six of them. So that a
reader need not implement the rest, a writer that does computes the outline of every preset
shape that has a box of its own and stores it: one **`core.slide.geometry`** node per slide,
layout or master (node_id `<owner>-geometry`), listing for each such shape its JSON Pointer in
the owner's payload, its `id`, and its sub-paths in the shape's own space in points, with the
rectangle text is laid out in. A reader draws a preset shape from this entry; a reader that
finds none for a shape (the writer had no generator, or the shape inherits its box) draws the
preset from §4.4, and an unknown preset as `rect`.

The node is `measured` from the owner's payload file and `requires` the owner: when the owner
changes or is damaged, the outlines are stale or dead with it.

### 3.6 The preview tier — `core.slide.preview`, `core.slide.outline`

**`core.slide.preview`** (node_id `preview`, `primary.image`): the first slide of the show
order rendered to PNG by the writing application — the slide's background, the layout's and
master's shapes where the slide shows them, the slide's shapes in their final (un-animated)
state, hidden shapes not drawn, 8 bits per channel RGBA, at most 960 pixels on its longer
side. `measured`: `input_files` lists, in order, the structure node's file, the slide's, its
layout's, its master's, then the `media` file of every embedded file those three name;
`input_params` records the renderer, the scale (`pixels_per_point`), the pixel size and the
text shown in date fields. It `requires` those nodes: damage to the slide marks the picture
dead rather than leaving a stale one.

**`core.slide.outline`** (node_id `outline`): the text of the deck as UTF-8, lines ending in
U+000A, in exactly this form:

    Slide <n>: <title>                   n counts from 1 in show order; the title is the text
                                         of the slide's first title placeholder (§6 step 6)
    <TAB × (level+1)><paragraph text>    one line per non-empty paragraph of each shape that
                                         is not that title, shapes bottom first, group members
                                         after their group; level is the paragraph's `level`
    <TAB><cell> | <cell> | …             one line per table row that has text: the text of each
                                         cell of the row that is not covered (neither `h_merge`
                                         nor `v_merge`), its paragraphs joined by U+000A
    Notes: <paragraph text>              one line per non-empty paragraph of the notes
    <empty line>                         between slides

A paragraph's text is its runs' `text` in order, a `break` run counting as U+000B; a
paragraph whose text is empty writes no line, and neither does a table row in which no
uncovered cell has a character other than white space. Inside a line (a title, a paragraph, a
cell), each U+000A, U+000D, U+0009 and U+000B is written as one space, and any other control
character (U+0000 to U+001F, U+007F to U+009F) as U+FFFD. A deck with no slide has the single line
`(no slides)`. `measured` from the slide payload files in show order; `requires` them.

### 3.7 XML kept from an imported file — `x.deckcraft.ooxml`

DeckCraft imports Office Open XML presentations and keeps, verbatim, fragments it does not
model (extension lists, tags, 3-D settings, the markup of an object it shows only as a
picture, the typeset form of an equation), so that exporting to that format again loses
nothing. Those fragments are NOT part of this profile's content model and are not in the core
payloads. Each owner node that has any gets one `x.deckcraft.ooxml` node (node_id
`x-ooxml-<owner>`): `{"schema_version": 1, "owner": "<node_id>", "entries": [{"pointer",
"xml"}]}`, where `pointer` is the RFC 6901 JSON Pointer, in the owner's payload, of the member
the fragment is the value of — a member that is absent there. The member names are `raw_ext`,
`raw`, `raw_extra`, `raw3d`, `xml` and `omml`; a reader that does not export to Office Open
XML ignores the node and loses nothing this profile defines. What stays in the core payload:
a shape of kind `opaque` keeps its box, its `label` and its `preview` picture; an equation run
(`kind: "math"`) keeps its linear text.

### 3.8 Edges, and which side dies

An edge reads source → target. `requires`: a dead target kills the source. `enhances`: a dead
target costs the source one feature.

| source | target | kind, role | why |
|---|---|---|---|
| `document` | every slide, master, layout, asset and derived media node | `enhances`, `contains` | a deck whose third slide is damaged is still a deck |
| a slide | its layout | `enhances`, `layout` | a slide whose layout is damaged is still a slide: it is shown on another layout |
| a layout | its master | `requires`, `master` | a layout has no meaning without the master it inherits from |
| a slide, layout or master | each asset its payload names | `enhances`, `uses` | a slide whose picture is damaged still shows everything else |
| a `core.media.image` / `core.media.audio` | the asset it was decoded from | `enhances`, `derived-from` | decoded pixels and samples still show what the file showed when the file is damaged |
| a `core.slide.geometry` | its owner | `requires`, `derived-from` | outlines of a damaged slide are stale |
| `preview`, `outline` | the nodes they were made from | `requires`, `derived-from` | a rendering of damaged content is stale |
| an `x.deckcraft.ooxml` | its owner | `enhances`, `extends` | extensions never hold anything up |

No `core.*` node `requires` an `x.*` node.

### 3.9 What a reader does when a node is dead, missing or unknown

* **A slide**: the deck opens without that slide; the others keep their order.
* **A layout**: slides that name it use the first layout of the first master.
* **A master**: its layouts die with it (they `require` it); slides that used them use the
  first layout of the first master that is left. With no master left at all, a reader
  supplies a plain one (white background, no placeholders).
* **An asset**: shapes that name its id show an empty box, sounds are silent. For a picture
  whose `rendition` is alive, the reader shows the rendition instead.
* **A rendition, poster or excerpt; a geometry node; `preview`; `outline`**: ignored; nothing
  of the document is lost, and a writer makes them again.
* **The structure node**: the reader rebuilds the structure from the manifest — every live
  `core.slide.slide` node of the current revision in manifest order; every `core.slide.master`
  under the `role` in its own payload, with the `core.slide.layout` nodes whose `master` names
  it; every `core.media.asset` under the `id` in its own payload — with default settings
  (slide size 960 × 540 points, first slide number 1), and says that it did.
* **An `x.deckcraft.ooxml` node**: the fragments are not restored; nothing else changes.
* **Any other `x.*` node, or a node of a type the reader does not know**: skipped and
  reported, and a writer carries it through its next save unchanged.

In every case the reader names the node and what was lost, and exits with status 1 rather
than 0 (`spec/SPEC.md` §10.1).

### 3.10 Versions

Exactly `spec/CRAFT-BASE.md` §3 and §4. A Save declares every node of the document; a node
whose files did not change gains no version and its bytes are stored once, so that editing one
slide stores that slide again and nothing else. A slide that was deleted is no longer listed
in the newest revision record and in the structure node; its node and its bytes stay in the
package. A derived node whose inputs changed gains a version even when its own bytes did not
(its `input_hash` did). Each revision record carries the work note of that Save.

## 4. The object model

The complete, normative description of every member is in the schemas. Every member there says
its unit, range, default and meaning. `spec/examples/presentation/slide-every-kind.example.json`
is a slide with one shape of every kind. This section is the map, and it defines what a schema
cannot: arithmetic, drawing order and inheritance.

### 4.1 The stored form

* **Absent, `null` and "not set" are the same thing** for every member a schema allows to be
  `null`, with one stated exception: the two chart members `title` and `legend` are always
  written (their schema says so). A writer may write `null` or leave the member out.
* **A member that is absent has its default**, stated in its schema description ("Default
  …"). A minimal object is therefore valid: `{"id": 4}` is a shape — a `rect`, with no box of
  its own, no fill of its own, no text.
* A tagged object is told apart by one member: `kind` for fills, colours' bases, gradient
  shapes, picture modes, dashes, geometries, bullets, actions, autofit, backgrounds and runs;
  `type` for what a shape is (`shape.kind.type`). The schema gives each variant its members.
* Lists of four numbers have a fixed order, stated where they occur: a crop and a picture
  inset are left, top, right, bottom; cell borders and cell margins are left, right, top,
  bottom; a focus rectangle is left, top, right, bottom; a text rectangle is x0, y0, x1, y1.

### 4.2 Coordinates, boxes and groups

Lengths are points (1/72 inch); the origin is the slide's top-left corner; x grows to the
right and y downwards. A shape's `xfrm` is its box `(x, y, w, h)` in its parent's space, a
rotation `rot` in degrees clockwise about the box's centre, and two flips about the centre.
A point `(u, v)` of the shape's own space — (0, 0) the box's top-left corner, (w, h) its
bottom-right — is in parent space:

    cx, cy = x + w/2, y + h/2
    u1 = (w - u) if flip_h else u                    # flips first
    v1 = (h - v) if flip_v else v
    dx, dy = u1 - w/2, v1 - h/2
    a = radians(rot)                                 # then the rotation, clockwise on screen
    X = cx + dx*cos(a) - dy*sin(a)
    Y = cy + dx*sin(a) + dy*cos(a)

A shape with `xfrm` absent is a placeholder that takes its box from its layout's or master's
matching placeholder (§4.6); if none gives one, its box is `(0.1·W, 0.1·H, 0.8·W, 0.2·H)` for
a slide of size W × H.

A **group** (`kind.type: "group"`) has its own box and a child space `kind.child`. A member's
`xfrm` is in child space; the rectangle `(child.x, child.y, child.w, child.h)` of child space
is mapped onto the group's box:

    sx = group.w / child.w   (1 if child.w is 0)     sy = group.h / child.h   (1 if child.h is 0)
    u = (X_child - child.x) * sx                     v = (Y_child - child.y) * sy

and `(u, v)` is then a point of the group's own space, mapped to the slide by the group's
`xfrm` as above. Groups nest.

A slide is drawn in this order: the background (§4.6); the master's shapes that are not
placeholders, then the layout's — each only where §4.6 says they show; then the slide's own
shapes. Within every list the first shape is at the bottom. A shape with `hidden: true` is not
drawn.

### 4.3 Colours

A colour is `{"base": …, "mods": […]}`. Resolve the base to an sRGB colour with straight alpha
(r, g, b, a each 0..255):

* `rgb` → its `rgb` object;
* `scheme` → the theme colour of the slot: the master's `theme.colors.colors` in the order
  dk1, lt1, dk2, lt2, accent1 … accent6, hlink, folHlink. The aliases `bg1`, `tx1`, `bg2`,
  `tx2` are first replaced through the master's `color_map` (the entry whose `alias` equals
  the slot gives the `slot` to use; with no entry: bg1 → lt1, tx1 → dk1, bg2 → lt2,
  tx2 → dk2). `phClr` is the colour a theme style reference supplies (§4.6); where none
  does, it is accent1. "The master" is the master of the slide's layout;
* `preset` → the sRGB value of the CSS named colour of that name (`red` = 255, 0, 0; `green`
  = 0, 128, 0; …), opaque; a name the reader does not know is black;
* `system` → its `last` object.

Then apply each transform in order. `p = val / 100000`. `lin` and `srgb` are the sRGB
transfer functions on a 0..1 value:

    lin(c)  = c / 12.92                    if c <= 0.04045    else ((c + 0.055) / 1.055) ** 2.4
    srgb(l) = 12.92 * l                    if l <= 0.0031308  else 1.055 * l ** (1 / 2.4) - 0.055

| `op` | effect |
|---|---|
| `tint` | each of r, g, b: `round(255 * srgb(lin(c/255) * k + (1 - k)))` with `k = clamp(p, 0, 1)` — towards white, in linear light |
| `shade` | each of r, g, b: `round(255 * srgb(lin(c/255) * k))` with `k = clamp(p, 0, 1)` — towards black, in linear light |
| `lumMod`, `lumOff` | convert to HSL; `L = L * p`, respectively `L = L + p`; convert back |
| `satMod`, `satOff` | the same on S |
| `hueMod` | `H = H * p` |
| `hueOff` | `H = H + val / 60000` (degrees) |
| `comp` | `H = H + 180` |
| `alpha` | `a = round(255 * clamp(p, 0, 1))` |
| `alphaMod` | `a = clamp(round(a * p), 0, 255)` |
| `alphaOff` | `a = clamp(round(a + 255 * p), 0, 255)` |
| `inv` | each of r, g, b: `255 - c` |
| `gray` | r = g = b = `round(0.299 r + 0.587 g + 0.114 b)` |
| `redMod`, `greenMod`, `blueMod` | that one channel: `clamp(round(c * p), 0, 255)` |

HSL is computed on r, g, b divided by 255: `max`, `min` the largest and smallest of the
three, `L = (max + min) / 2`; if `max = min` then `H = S = 0`, else with `d = max - min`:
`S = d / (2 - max - min)` if `L > 0.5` else `d / (max + min)`; `H = 60 × ((g - b)/d + (6 if
g < b else 0))` if max is r, `60 × ((b - r)/d + 2)` if max is g, `60 × ((r - g)/d + 4)` if
max is b. Converting back: H is taken modulo 360, S and L are clamped to 0..1; if `S = 0`
then r = g = b = L; else `q = L(1 + S)` if `L < 0.5` else `L + S - L·S`, `p0 = 2L - q`, and
each channel is `f(t)` for `t = H/360 + 1/3` (r), `H/360` (g), `H/360 - 1/3` (b), t wrapped
into 0..1: `f = p0 + (q - p0)·6t` if `t < 1/6`; `q` if `t < 1/2`; `p0 + (q - p0)(2/3 - t)·6`
if `t < 2/3`; else `p0`. Each channel is then `round(255 × value)`. Alpha is untouched by the
HSL operations. Rounding is to nearest, halves away from zero.

Worked examples (a reader that reproduces this table implements the transforms):

<!-- colour-examples:begin -->
| base `RRGGBBAA` | transforms, in order | result `RRGGBBAA` |
|---|---|---|
| `2E6FD8FF` | (none) | `2E6FD8FF` |
| `2E6FD8FF` | `tint` 40000 | `CDD5F0FF` |
| `2E6FD8FF` | `shade` 75000 | `2761BEFF` |
| `2E6FD8FF` | `lumMod` 60000 | `194284FF` |
| `2E6FD8FF` | `lumMod` 20000, then `lumOff` 80000 | `D5E2F7FF` |
| `2E6FD8FF` | `satMod` 50000 | `5879AEFF` |
| `2E6FD8FF` | `satOff` -20000 | `4775BFFF` |
| `2E6FD8FF` | `hueMod` 50000 | `4ED82EFF` |
| `2E6FD8FF` | `hueOff` 3600000 (60 degrees) | `972ED8FF` |
| `2E6FD8FF` | `comp` | `D8972EFF` |
| `2E6FD8FF` | `inv` | `D19027FF` |
| `2E6FD8FF` | `gray` | `686868FF` |
| `2E6FD8FF` | `alpha` 55000 | `2E6FD88C` |
| `2E6FD8FF` | `alpha` 55000, then `alphaMod` 50000 | `2E6FD846` |
| `2E6FD8FF` | `alpha` 55000, then `alphaOff` 20000 | `2E6FD8BF` |
| `2E6FD8FF` | `redMod` 200000, `greenMod` 50000, `blueMod` 0 | `5C3800FF` |
<!-- colour-examples:end -->

### 4.4 Geometry

A shape's outline is in its own space (§4.2), given its box size w × h.

**Custom** (`geom.kind: "custom"`): `paths` is a list of sub-paths, painted in order. Each has
a path `d` in its own coordinate space of size `w` × `h` (the sub-path's members, not the
shape's): every coordinate is multiplied by `shape.w / path.w` and `shape.h / path.h` (by 1
where the path's `w`, resp. `h`, is 0 or less). `d` is commands separated by white space,
all coordinates absolute:

    M x y                  begin a sub-path at (x, y)
    L x y                  a straight line to (x, y)
    C x1 y1 x2 y2 x y      a cubic Bezier: control points (x1, y1), (x2, y2), end (x, y)
    Q x1 y1 x y            a quadratic Bezier: control point (x1, y1), end (x, y)
    Z                      close the sub-path with a straight line to its beginning

`fill` says how the sub-path is filled: `norm` with the shape's fill; `none` not at all;
`lighten`, `lightenLess`, `darken`, `darkenLess` with the fill's colour mixed 40 %, 20 %
towards white, 40 %, 20 % towards black (each channel `c + (target - c) × fraction`, rounded).
`stroke` says whether it is outlined with the shape's line. Filling uses the non-zero winding
rule.

**Preset** (`geom.kind: "preset"`): `name` and optional adjust values `adj`. Six presets are
defined here; with `ss = min(w, h)`:

| name | outline | adjust value 0 |
|---|---|---|
| `rect` | the box: (0,0) (w,0) (w,h) (0,h), closed | — |
| `ellipse` | the ellipse with centre (w/2, h/2) and radii w/2, h/2 | — |
| `roundRect` | the box with each corner replaced by a quarter circle of radius `r = ss × a / 100000` | `a`, default 16667, clamped to 0..50000 |
| `triangle` | (0,h) (`w × a / 100000`, 0) (w,h), closed | `a`, default 50000, clamped to 0..100000 |
| `diamond` | (w/2,0) (w,h/2) (w/2,h) (0,h/2), closed | — |
| `line` | one straight segment from (0,0) to (w,h); stroked, never filled | — |

Text is laid out in the box, except: `ellipse` in the rectangle (0.14645w, 0.14645h)–(0.85355w,
0.85355h); `roundRect` in the box inset by `0.29289 r` on every side; `triangle` in
(`a'/2`, h/2)–((`a'` + w)/2, h) with `a' = w × a / 100000`; `diamond` in (w/4, h/4)–(3w/4, 3h/4).

Every other name is one of the preset shapes of office documents (`rightArrow`, `star5`,
`flowChartDecision`, `wedgeRectCallout`, `bentConnector3`, …). Its outline is in the owner's
`core.slide.geometry` node (§3.5), as sub-paths in the same grammar as above, already at the
shape's size (no scaling). A reader without that node, or without an entry for the shape,
draws the six presets above from this table and anything else as `rect`. A writer that
cannot generate a preset writes a `custom` geometry instead — every outline can be said that
way.

A **picture** (`kind.type: "picture"`) is drawn into the shape's box and clipped to the
outline. With `crop = [l, t, r, b]` the part of the picture from fraction `l` to `1 - r` of
its width and `t` to `1 - b` of its height is what is shown (a negative value leaves an empty
margin); with `mode.kind: "stretch"` that part is stretched to the box inset by `fill_rect`.

### 4.5 Fills, lines, effects

A shape is painted in this order: its fill inside the outline; its line along the outline,
centred on it; its text. `effects` are applied to the shape as a whole: an outer shadow is
drawn beneath it, a glow around it, a reflection below it. A reader may omit an effect it does
not implement; it must not omit the shape.

A gradient's stops are interpolated linearly in sRGB between neighbours; a stop's `pos` is
clamped to 0..1 and the stops are taken in ascending `pos`. With the box (x0, y0)–(x1, y1) of
the painted shape, width W and height H:

* `linear` with `angle` θ: direction `d = (cos θ, sin θ)` with y down (0 = left to right,
  90 = top to bottom); `half = (W·|cos θ| + H·|sin θ|) / 2`; position 0 is at
  `centre - d·half`, position 1 at `centre + d·half`.
* `path`: position 0 is at the centre of the focus rectangle,
  `(x0 + W·(focus[0] + 1 - focus[2])/2, y0 + H·(focus[1] + 1 - focus[3])/2)`, and position 1
  at the distance of the box corner farthest from it; colours are constant on circles around
  that point. (A reader may shape the contours as rectangles for `path: "rect"`.)

A line's `width` is in points; `dash` lengths are multiples of the width; `head` is the
arrowhead at the START of the path and `tail` the one at its END.

### 4.6 Inheritance

A deck states most things once, on a master, and slides inherit them. A reader that draws or
that reports effective formatting resolves, for a shape S on a slide:

**The placeholders S inherits from.** If S has no `ph`: none. Otherwise, with the slide's
layout (the first layout whose `id` equals `slide.layout`; if none, the first layout of the
first master) and that layout's master:

1. The layout placeholder LP: among the layout's top-level shapes that have a `ph`, the first
   that satisfies, tried in this order: (a) if `S.ph.idx` is not 0: same `idx` and a
   compatible kind; (b) same `kind`, and (`S.ph.idx` is 0, or same `idx`, or the kind is a
   title kind); (c) same `kind`; (d) a compatible kind. Kinds are compatible when both are
   title kinds (`title`, `ctrTitle`); or S's kind is one of `subTitle`, `body`, `obj`, `chart`,
   `table`, `clipArt`, `diagram`, `media`, `picture` and the other is none of `title`,
   `ctrTitle`, `date`, `footer`, `slideNum`, `header`; or they are equal.
2. The master placeholder MP: with `k` = LP's kind if there is an LP, else S's kind — the
   master's first top-level shape whose `ph.kind` is `title` if `k` is a title kind; `k`
   itself if `k` is `date`, `footer`, `slideNum` or `header`; otherwise `body`.

For a shape of a layout, LP is none and MP is found from the shape's own kind. For a shape of
a master, there are none.

**Box**: S's `xfrm`, else LP's, else MP's, else the default of §4.2.

**Fill**: walk S, LP, MP in that order; the first that has a `fill` gives it; else the first
that has a `style` gives the theme fill `style.fill_ref.index` selects (0 = none; 1..3 =
`theme.format.fills[index - 1]`; 1001..1003 = `theme.format.bg_fills[index - 1001]`), painted
with `phClr` = `style.fill_ref.color`. If none of the three has either: no fill.

**Line**: start with an empty line. Walk S, LP, MP: a `line` fills in the members still unset;
at the first that has a `style`, the theme line `theme.format.lines[index - 1]` fills in the
rest (index 0: no line) with `phClr` = `style.line_ref.color`, and the walk stops. A line whose
`fill` is still unset is not drawn.

**Effects**: like the fill, with `effects` and `style.effect_ref` (index 0 = none).

**Body properties**: S's `text.body`, unset members from LP's, then MP's `text.body`, then
these defaults: insets 7.2 (left, right) and 3.6 (top, bottom) points; `anchor` `middle` for
a shape that is not a placeholder, not a text box and not a table, else `top`; `wrap` true;
`autofit` `shape` for a text box, else `none`; one column; horizontal.

**Paragraph and character formatting** of a paragraph at level n, each member taken from the
first source that sets it:

1. the run's own `props` (the paragraph's own `props` for paragraph members);
2. level n of S's `text.list_style`, then of LP's, then of MP's;
3. S's `style.font_ref` (else LP's): font `+mj-lt` for `major`, `+mn-lt` for `minor`, and its
   colour as the text fill;
4. level n of the master's `title_style` if S is a title placeholder; of `body_style` if S is
   a placeholder of kind `body`, `obj`, `subTitle`, `table`, `chart`, `diagram`, `media`,
   `picture` or `clipArt`; of `other_style` for any other placeholder; of the structure
   node's `default_text_style` if S is not a placeholder;
5. level n of the structure node's `default_text_style`;
6. size 18 points, font `+mn-lt`, not bold, not italic, left aligned, no margins.

A run with a `link` and no `fill` of its own is drawn in the theme's `hlink` colour, and
underlined unless it sets `underline` itself. A font named `+mj-lt`, `+mn-lt`, `+mj-ea`, … is
the master theme's `fonts.major` / `fonts.minor` `latin`, `ea` or `cs` entry.

**Background**: the slide's `background`, else the layout's, else the master's, else a solid
fill of `bg1`. A `ref` background is `theme.format.bg_fills[idx - 1001]` (for an `idx` below
1001: `theme.format.fills[idx - 1]`) painted with `phClr` = its `color`; if the theme has no
such entry, a solid fill of that colour.

**Master and layout shapes on a slide**: the layout's shapes that are not placeholders are
drawn when the slide's `show_master_shapes` is true; the master's when, in addition, the
layout's `show_master_shapes` is true. Placeholders of layouts and masters are never drawn on
a slide; they only lend their properties. The slide's own shapes are all drawn, its date,
footer and slide-number placeholders included: the structure node's `header_footer` records
the settings a person chose, and an application applies them by putting those placeholders on
slides or taking them off — it is not a filter a reader applies again.

### 4.7 Transitions

A slide's `transition` says how the show arrives AT that slide. `kind` and `option` are
tokens; this is the complete list DeckCraft writes, with the name it shows and the default
duration:

<!-- transitions:begin -->
| `kind` | shown as | default `duration_ms` | `option` values |
|---|---|---|---|
| `none` | None | 0 | - |
| `morph` | Morph | 2000 | `objects` `words` `characters` |
| `fade` | Fade | 700 | `smoothly` `throughBlack` |
| `push` | Push | 1000 | `u` `d` `l` `r` |
| `wipe` | Wipe | 1000 | `r` `l` `u` `d` `ru` `lu` `rd` `ld` |
| `split` | Split | 1500 | `vertOut` `vertIn` `horzOut` `horzIn` |
| `reveal` | Reveal | 2000 | `smoothlyLeft` `smoothlyRight` `blackLeft` `blackRight` |
| `cut` | Cut | 0 | (empty) `throughBlack` |
| `randomBar` | Random Bars | 1000 | `vert` `horz` |
| `shape` | Shape | 2000 | `circle` `diamond` `plus` `in` `out` |
| `uncover` | Uncover | 1000 | `l` `r` `u` `d` `lu` `ru` `ld` `rd` |
| `cover` | Cover | 1000 | `l` `r` `u` `d` `lu` `ru` `ld` `rd` |
| `flash` | Flash | 1000 | - |
| `fallOver` | Fall Over | 2000 | `l` `r` |
| `drape` | Drape | 2000 | `l` `r` |
| `curtains` | Curtains | 2000 | - |
| `wind` | Wind | 2000 | `l` `r` |
| `prestige` | Prestige | 2000 | - |
| `fracture` | Fracture | 2000 | - |
| `crush` | Crush | 2000 | - |
| `peelOff` | Peel Off | 1500 | `l` `r` |
| `pageCurlDouble` | Page Curl | 1500 | `l` `r` |
| `airplane` | Airplane | 2000 | `l` `r` |
| `origami` | Origami | 2000 | `l` `r` |
| `dissolve` | Dissolve | 1200 | - |
| `checker` | Checkerboard | 1500 | `horz` `vert` |
| `blinds` | Blinds | 1600 | `vert` `horz` |
| `clock` | Clock | 2000 | `clockwise` `counterClockwise` `wedge` |
| `ripple` | Ripple | 1400 | `center` `lu` `ru` `ld` `rd` |
| `honeycomb` | Honeycomb | 3000 | - |
| `glitter` | Glitter | 2500 | `l` `r` `u` `d` |
| `vortex` | Vortex | 3000 | `l` `r` `u` `d` |
| `shred` | Shred | 2000 | `strips` `particles` |
| `switch` | Switch | 1250 | `l` `r` |
| `flip` | Flip | 1250 | `l` `r` |
| `gallery` | Gallery | 1500 | `l` `r` |
| `cube` | Cube | 1250 | `l` `r` `u` `d` |
| `doors` | Doors | 1400 | `vert` `horz` |
| `box` | Box | 1250 | `l` `r` `u` `d` |
| `comb` | Comb | 1000 | `horz` `vert` |
| `zoom` | Zoom | 1000 | `in` `out` |
| `random` | Random | 2000 | - |
| `pan` | Pan | 1000 | `u` `d` `l` `r` |
| `ferris` | Ferris Wheel | 2000 | `l` `r` |
| `conveyor` | Conveyor | 2000 | `l` `r` |
| `rotate` | Rotate | 2000 | `l` `r` `u` `d` |
| `window` | Window | 1250 | `vert` `horz` |
| `orbit` | Orbit | 2000 | `l` `r` `u` `d` |
| `flythrough` | Fly Through | 1000 | `in` `out` `inBounce` `outBounce` |
<!-- transitions:end -->

Direction options: `l` from the right towards the left, `r` towards the right, `u` upwards,
`d` downwards, and their pairs (`lu` = left and up). This profile fixes the tokens and the
timing members; it does not define the pixels of each effect. A reader that does not
implement a `kind` plays `fade`, and a reader that plays no transitions shows the slide.

### 4.8 Animations

`animations` is the slide's timeline: effects in order. An effect starts on the next click
(`onClick`), together with the effect before it (`withPrevious`), or when the effect before it
has ended (`afterPrevious`); `delay_ms` later it runs for `duration_ms`. An effect with a
`trigger` is outside that sequence: it starts when the shape with that id is clicked. An
`entrance` effect means the shape is NOT shown before the effect starts; an `exit` effect
means it is not shown after it ends. The complete list of `effect` tokens per `class`:

<!-- animations:begin -->
| `class` | `effect` | shown as | default `duration_ms` | `option` values |
|---|---|---|---|---|
| `entrance` | `appear` | Appear | 0 | - |
| `entrance` | `fade` | Fade | 500 | - |
| `entrance` | `fly` | Fly In | 500 | `b` `lb` `l` `lt` `t` `rt` `r` `rb` |
| `entrance` | `float` | Float In | 1000 | `u` `d` |
| `entrance` | `split` | Split | 500 | `horzIn` `horzOut` `vertIn` `vertOut` |
| `entrance` | `wipe` | Wipe | 500 | `b` `l` `t` `r` |
| `entrance` | `shape` | Shape | 2000 | `circleIn` `circleOut` `boxIn` `boxOut` `diamondIn` `diamondOut` `plusIn` `plusOut` |
| `entrance` | `wheel` | Wheel | 2000 | `1` `2` `3` `4` `8` |
| `entrance` | `randomBars` | Random Bars | 500 | `horz` `vert` |
| `entrance` | `grow` | Grow & Turn | 500 | - |
| `entrance` | `zoom` | Zoom | 500 | `in` `out` |
| `entrance` | `swivel` | Swivel | 2000 | `horz` `vert` |
| `entrance` | `bounce` | Bounce | 2000 | - |
| `entrance` | `blinds` | Blinds | 500 | `horz` `vert` |
| `entrance` | `box` | Box | 500 | `in` `out` |
| `entrance` | `checkerboard` | Checkerboard | 500 | `across` `down` |
| `entrance` | `circle` | Circle | 500 | `in` `out` |
| `entrance` | `diamond` | Diamond | 500 | `in` `out` |
| `entrance` | `dissolve` | Dissolve In | 500 | - |
| `entrance` | `peek` | Peek In | 500 | `b` `l` `t` `r` |
| `entrance` | `strips` | Strips | 500 | `lu` `ru` `ld` `rd` |
| `entrance` | `expand` | Expand | 500 | - |
| `entrance` | `rise` | Rise Up | 1000 | - |
| `entrance` | `spinner` | Spinner | 1000 | - |
| `emphasis` | `pulse` | Pulse | 500 | - |
| `emphasis` | `colorPulse` | Color Pulse | 500 | - |
| `emphasis` | `teeter` | Teeter | 1000 | - |
| `emphasis` | `spin` | Spin | 2000 | `clockwise` `counterClockwise` |
| `emphasis` | `growShrink` | Grow/Shrink | 2000 | `both` `horz` `vert` |
| `emphasis` | `desaturate` | Desaturate | 500 | - |
| `emphasis` | `darken` | Darken | 500 | - |
| `emphasis` | `lighten` | Lighten | 500 | - |
| `emphasis` | `transparency` | Transparency | 500 | - |
| `emphasis` | `objectColor` | Object Color | 2000 | - |
| `emphasis` | `complementaryColor` | Complementary Color | 500 | - |
| `emphasis` | `lineColor` | Line Color | 2000 | - |
| `emphasis` | `fillColor` | Fill Color | 2000 | - |
| `emphasis` | `fontColor` | Font Color | 2000 | - |
| `emphasis` | `underline` | Underline | 500 | - |
| `emphasis` | `boldFlash` | Bold Flash | 500 | - |
| `emphasis` | `wave` | Wave | 500 | - |
| `exit` | `disappear` | Disappear | 0 | - |
| `exit` | `fadeOut` | Fade | 500 | - |
| `exit` | `flyOut` | Fly Out | 500 | `b` `lb` `l` `lt` `t` `rt` `r` `rb` |
| `exit` | `floatOut` | Float Out | 1000 | `u` `d` |
| `exit` | `splitOut` | Split | 500 | `horzIn` `horzOut` `vertIn` `vertOut` |
| `exit` | `wipeOut` | Wipe | 500 | `b` `l` `t` `r` |
| `exit` | `shapeOut` | Shape | 2000 | `circleIn` `circleOut` |
| `exit` | `wheelOut` | Wheel | 2000 | `1` `2` `3` `4` `8` |
| `exit` | `randomBarsOut` | Random Bars | 500 | `horz` `vert` |
| `exit` | `shrinkTurn` | Shrink & Turn | 500 | - |
| `exit` | `zoomOut` | Zoom | 500 | `in` `out` |
| `exit` | `swivelOut` | Swivel | 2000 | `horz` `vert` |
| `exit` | `bounceOut` | Bounce | 2000 | - |
| `exit` | `dissolveOut` | Dissolve Out | 500 | - |
| `path` | `lines` | Lines | 2000 | `down` `up` `right` `left` |
| `path` | `arcs` | Arcs | 2000 | `down` `up` `right` `left` |
| `path` | `turns` | Turns | 2000 | `down` `up` `right` `left` |
| `path` | `shapes` | Shapes | 2000 | `circle` `diamond` `hexagon` `triangle` `square` `trapezoid` `octagon` `parallelogram` `pentagon` |
| `path` | `loops` | Loops | 2000 | - |
| `path` | `customPath` | Custom Path | 2000 | - |
| `media` | `play` | Play | 0 | - |
| `media` | `pause` | Pause | 0 | - |
| `media` | `stop` | Stop | 0 | - |
<!-- animations:end -->

As with transitions, the tokens and the timing are fixed and the motion of each effect is not
defined here. A reader that does not implement an `entrance` or `exit` effect plays `fade`,
respectively `fadeOut`; it skips an `emphasis` or `path` effect it does not implement; and a
reader that plays no animations shows every shape in its final state — which is what
`core.slide.preview` shows.

### 4.9 Text

A text body is paragraphs of runs. The characters of a paragraph are its runs' `text` in
order; a run of kind `break` contributes one line break; a `field` run's `text` is its last
shown value and a reader may recompute it (`slidenum`: the slide's 0-based position in the
show order plus the structure node's `first_slide_number`); a `math` run's `text` is the
equation in linear form. Strings are Unicode, stored as written — no normalisation. Which
glyphs are used and where lines break is the reader's: the payload carries text and
attributes, not glyph positions.

### 4.10 Tables and charts

A **table** is `cols` (column widths) and `rows`; each row has one cell per column. A cell
with `grid_span` > 1 or `row_span` > 1 covers its neighbours to the right and below, and each
covered cell is still present with `h_merge` or `v_merge` set (it draws nothing). The table is
laid out from the top-left corner of the shape's box.

A **chart** carries its data: `categories` and, per series, `values` (one per category,
`null` for a missing point). How a chart type is drawn — axes, bar widths, label placement —
is the reader's; the members that constrain it (`gap_width`, `overlap`, `hole_size`, `y_min`,
`y_max`, `legend`, `data_labels`, `gridlines`) are defined in the schema.

## 5. Conventions and what each governs

Every value is in `MANIFEST.json` → `conventions`, pinned by the manifest schema.

| convention | value | governs | scope |
|---|---|---|---|
| `text_encoding` | `"utf-8"` | every text and JSON payload, `MANIFEST.json` | container |
| `id_case` | `"kebab-case"` | every node id | container |
| `hash_algorithm` | `"sha256"` | every hash | container |
| `signature_algorithm` | `"ed25519"` | `SIGNATURE.json` | signature |
| `endianness`, `alignment_bytes` | `"le"`, `16` | any envelope binary of an `x.*` node | node |
| `length_unit` | `"point"` | every coordinate, length, font size and line width of the document, slide, layout, master and geometry payloads | node |
| `points_per_inch` | `72` | the same: 1 point = 1/72 inch = 25.4/72 mm | node |
| `x_axis` | `"right"` | slide, layout, master, geometry | node |
| `y_axis` | `"down"` | the same: larger y is lower | node |
| `angle_unit` | `"degree"` | every angle of those payloads, except the two below | node |
| `angle_direction` | `"clockwise"` | the same: a positive angle turns clockwise on screen | node |
| `paint_order` | `"bottom-first"` | every list of shapes | node |
| `ratio_file_unit_per_whole` | `100000` | colour-transform operands; preset adjust ratios | node |
| `angle_file_unit_per_degree` | `60000` | the `hueOff` operand; preset adjust angles | node |
| `number_format` | `"shortest-round-trip-decimal"` | every JSON number: the shortest decimal that parses back to the same IEEE 754 binary64 value | node |
| `color_space` | `"srgb"` | every colour value; `core.media.image`, `core.slide.preview` | node |
| `color_component_max` | `255` | r, g, b, a of every colour | node |
| `alpha_mode` | `"straight"` | colours; `core.media.image`, `core.slide.preview` | node |
| `pixel_origin` | `"top-left"` | `core.media.image`, `core.slide.preview` | node |
| `time_unit` | `"millisecond"` | every duration, delay and media position of a slide | node |
| `paragraph_index_base` | `0` | an animation's `paragraph` | node |
| `show_range_base` | `1` | `show.range` of the structure node | node |
| `style_index_base` | `1` | theme style reference `index` (0 = none) | node |
| `pointer_syntax` | `"rfc6901"` | `pointer` of `core.slide.geometry` and `x.deckcraft.ooxml` | node |
| `excerpt_sample_format` | `"pcm-s16le"` | `core.media.audio` | node |
| `excerpt_seconds` | `5` | `core.media.audio`: the longest excerpt | node |
| `outline_line_ending` | `"lf"` | `core.slide.outline` | node |

A reader that does not implement a node-scoped value refuses the node types it governs and
keeps everything else.

## 6. Reading

1. Open the container: a directory, or a store-mode zip (`spec/MINI-SPECS.md` §1).
2. Parse `MANIFEST.json`. Check `profile` is `presentation/1` and each convention of §5.
3. `primary.document` → that node → its `active` version → its one file. Verify the file's
   sha256 against `files[].sha256`. Parse it: the structure.
4. For each entry of `masters` (then `notes_master`, `handout_master` if not null): the
   `node` → `active` version → its file → verify → parse; then each of its `layouts` the same
   way. A node whose file is missing or fails its hash is dead: skip it, report it, continue
   (§3.9).
5. For each entry of `slides`, in order: node → `active` version → its file → verify → parse.
6. A slide's title is the text of its first top-level shape whose `ph.kind` is `title` or
   `ctrTitle`: its paragraphs joined by U+000A, a `break` run as one space; empty if there is
   none.
7. For an embedded file: `media[]` entry → `node` → the file with `role: "media"` (§3.3);
   or, for a reader of PNG and WAV only, the `rendition`, `poster` or `excerpt` node (§3.4).
8. Draw, if you draw: §4.2 for the order, §4.6 for what a shape inherits, §4.4 and the
   slide's `core.slide.geometry` node for outlines.
9. Report the signature state in one of the four fixed words.

To read the document as it was at revision K: read record K of the `revisions` node
(`spec/CRAFT-BASE.md` §3); a node belongs to that revision only if the record lists it, and
"its `active` version" becomes "the version the record gives". A record lists the nodes in its
`nodes` member. A writer of a large document may instead write a DELTA record, which has no
`nodes` and has `base` (the number of an earlier record that has `nodes`), `changed` (node_id
→ version, for the nodes that differ from that record or are not in it) and optionally
`removed` (node ids): the document is then record `base`'s `nodes` with `changed` laid over
it and `removed` taken out. Accept both.

`spec/examples/presentation/read_presentation.py` does steps 1–7 with the Python standard
library and writes the deck as JSON: every slide with its shapes, their boxes and text, its
notes, transition, animations and comments; the masters and layouts; every embedded file with
its encoding, size and sha256. With `--media DIR` it writes every embedded file out byte for
byte.

## 7. Writing a minimal valid `presentation/1` capsule

This section is normative. A capsule built exactly as below is accepted by every
`presentation/1` reader. `spec/examples/presentation/write_minimal.py` does all of it with the
Python standard library and nothing else; it copies `loaders/` and `spec/` from any existing
`presentation/1` capsule:

    python spec/examples/presentation/write_minimal.py <existing capsule> <new.werk>

The document: a 960 × 540 point deck with one master, one layout and one slide; on the slide
a yellow rectangle at (80, 60), 400 × 120 points, with the text "Hello, werk" in bold 32 point
type, and the speaker note "Written by a stranger."

**7.1 The four payloads.** Each is one line of JSON followed by one line feed (`0x0A`), UTF-8,
no byte order mark, members in the order shown, no space after `:` or `,`.

`deck/document.json` — 295 bytes, sha256
`d31d9dcc0074b892b533d79988256242561399c2816d0e8d1846ca5f109da647`:

    {"schema_version":1,"slide_size":{"width":960,"height":540},"notes_size":{"width":540,"height":720},"first_slide_number":1,"next_id":4,"slides":[{"id":3,"node":"slide-3"}],"masters":[{"id":1,"node":"master-1","layouts":[{"id":2,"node":"layout-2"}]}],"media":[],"props":{"title":"Minimal deck"}}

`deck/masters/master-1.json` — 743 bytes, sha256
`264af6d327b02adb4f5f7de4ea60c201b7db4bc8d513cbd0176006a9817eec6d`:

    {"schema_version":1,"role":"slide","master":{"id":1,"name":"Minimal master","theme":{"name":"Minimal","colors":{"name":"Minimal","colors":[{"r":0,"g":0,"b":0,"a":255},{"r":255,"g":255,"b":255,"a":255},{"r":30,"g":43,"b":60,"a":255},{"r":237,"g":235,"b":231,"a":255},{"r":46,"g":111,"b":216,"a":255},{"r":242,"g":107,"b":29,"a":255},{"r":46,"g":163,"b":111,"a":255},{"r":138,"g":92,"b":216,"a":255},{"r":216,"g":63,"b":107,"a":255},{"r":227,"g":178,"b":28,"a":255},{"r":46,"g":111,"b":216,"a":255},{"r":122,"g":91,"b":166,"a":255}]},"fonts":{"name":"Minimal","major":{"latin":"Inter"},"minor":{"latin":"Inter"}},"format":{"name":"Minimal"}},"background":{"kind":"fill","fill":{"kind":"solid","color":{"base":{"kind":"scheme","slot":"bg1"}}}}}}

`deck/layouts/layout-2.json` — 89 bytes, sha256
`2cd72e5ecbb3f7c82ce59bce5264d0fe3c12051c899fb864da64cc3e7fdd065b`:

    {"schema_version":1,"master":"master-1","layout":{"id":2,"name":"Blank","kind":"blank"}}

`deck/slides/slide-3.json` — 476 bytes, sha256
`08a83e517074e446a85bba7bed9bce0cc01289c4736bbe6d331123eb8d9507f3`:

    {"schema_version":1,"slide":{"id":3,"layout":2,"shapes":[{"id":4,"name":"Hello box","xfrm":{"x":80,"y":60,"w":400,"h":120},"kind":{"type":"shape"},"geom":{"kind":"preset","name":"rect"},"fill":{"kind":"solid","color":{"base":{"kind":"rgb","rgb":{"r":255,"g":204,"b":0,"a":255}}}},"line":{"fill":{"kind":"none"}},"text":{"paragraphs":[{"runs":[{"text":"Hello, werk","props":{"size":32,"bold":true}}]}]}}],"notes":{"paragraphs":[{"runs":[{"text":"Written by a stranger."}]}]}}}

If your hashes differ from these, you have a whitespace, ordering or line-ending difference;
find it before going further. (Any valid JSON spelling is a valid payload — these exact bytes
are only the checkpoint.) What the four say: the structure lists one slide (id 3), one master
(id 1) with one layout (id 2), no embedded files, and the slide size. The master states the
twelve theme colours — dk1 black, lt1 white, …, accent1 (46, 111, 216) — two fonts, and a
background of the theme colour `bg1`, which with no colour map is `lt1`: white. The layout is
an empty one named "Blank". The slide uses layout 2 and has one shape, id 4: the preset `rect`
in the box (80, 60, 400, 120), filled solid (255, 204, 0), with no line, holding one paragraph
of one bold 32 point run. Every member not written has its default (§4.1): the shape is not a
placeholder, the slide is not hidden, it has no transition and no animations.

**7.2 The base files.** Copy every current file under `loaders/` and `spec/` from the
existing capsule unchanged (skip files whose name carries an `@N` marker: superseded
versions; and skip `spec/formats/`, which belongs to media this document does not have).
Write `LICENSE` (the full licence text of your content, or an honest statement that its terms
are not established); copy `README.txt` and `HOW-TO-READ.md`.

**7.3 The revision record** `revisions/revision.json`:

    {"schema_version":1,"revision":1,"kind":"save","note":"<why this file exists>",
     "created":"<RFC 3339 UTC>","producer":{"tool":"<your tool>","version":"<its version>"},
     "nodes":{"spec":1,"license":1,"readme":1,"loader-python":1,"loader-rust":1,
              "loader-c":1,"document":1,"master-1":1,"layout-2":1,"slide-3":1}}

**7.4 The manifest.** Eleven nodes: `spec`, `license`, `readme`, `loader-python`,
`loader-rust`, `loader-c`, `revisions`, `document` (`core.slide.document`), `master-1`
(`core.slide.master`), `layout-2` (`core.slide.layout`), `slide-3` (`core.slide.slide`). Each
has one version:

    {"v":1, "files":[{"path":…,"sha256":…,"size":…}], "note":"<at least 8 characters>",
     "producer":{"tool":…,"version":…}, "epistemic":"authored", "created":"<RFC 3339 UTC>"}

with `"active":1` and these `edges` (§3.8), every other node `[]`:

    document   [{"to":"slide-3","kind":"enhances","role":"contains"},
                {"to":"master-1","kind":"enhances","role":"contains"},
                {"to":"layout-2","kind":"enhances","role":"contains"}]
    layout-2   [{"to":"master-1","kind":"requires","role":"master"}]
    slide-3    [{"to":"layout-2","kind":"enhances","role":"layout"}]

The `readme` version lists two files and therefore carries `"payload_file":"README.txt"`. The
three `core.loader` nodes carry the `meta` block of the existing capsule unchanged. Copy
`werk`, `profile`, `manifest_schema`, `profile_spec`, `conventions_map`, `conventions` and
`container` from the existing manifest; drop `container.preview_prefix_bytes` (a hint) and
set `container.total_size_bytes` to the sum of the sizes of all the files you list. From the
existing `schemas` map keep only the entries of the node types you wrote; leave `formats` out
(no file you wrote is in a foreign encoding) and leave out the `core.tool` nodes (they are
the reference decoders of those formats). Set `primary` to `{"document":"document"}`,
`license` to `{"file":"LICENSE","sha256":<its sha256>}`, a fresh `entity.uuid`, and compute
`spec_sha256` by `spec/SPEC.md` §2 over every `spec/` path you list.

**7.5 The container.** A store-mode zip, `MANIFEST.json` first, then `LICENSE`, `README.txt`,
`HOW-TO-READ.md`, `loaders/…`, `spec/…`, `revisions/…`, `deck/document.json`, then the rest.

**7.6 Check.** `python loaders/werk_read.py <new.werk> --verify --strict` exits 0 and prints
`N/N files verified`.

**Going further.** Add a second slide: another `core.slide.slide` node with a new `id`, an
entry appended to the structure's `slides`, one more `contains` edge, one more key in the
revision record, `next_id` raised to the largest id in use. Add a picture: a
`core.media.asset` node `media-5` with two files — `asset.json`
(`{"schema_version":1,"id":5,"name":"photo.png","content_type":"image/png","embedded":true,
"link":null,"encoding":"png","definition":"base"}`, named by `payload_file`) and the PNG with
`"role":"media"` — an entry `{"id":5,"node":"media-5"}` in the structure's `media`, and on a
slide a shape `{"id":6,"xfrm":{…},"kind":{"type":"picture","fill":{"media":5}}}`. A JPEG goes
the same way with `"encoding":"jpeg","definition":"formats"`, the node's
`"meta":{"file_formats":{"media":"jpeg"}}`, the manifest's `formats` entries for `jpeg` and
for every definition its header `requires`, and those definition documents and their
`core.tool` nodes copied from the existing capsule. Every payload you write must validate against its schema in `spec/schemas/`.

## 8. What this profile deliberately does not have

Named so that an absence reads as a decision:

* **No glyph positions and no line breaks.** Text is characters and attributes; layout is the
  reader's. `core.slide.preview` shows the writer's layout of the first slide.
* **No pixels for transitions and animation effects.** Tokens and timing are fixed (§4.7,
  §4.8); what "Origami" looks like is not.
* **No formulae for the preset shapes beyond six.** Their outlines are carried, resolved, in
  `core.slide.geometry` (§3.5), so a reader needs none.
* **No node per shape, and none per chart or table.** The unit of damage and of versioning is
  the slide, the layout, the master, the embedded file. A chart's data is in the slide.
* **No theme node.** A theme belongs to exactly one master and travels in it.
* **No node_ids inside slide content.** Content names layouts, slides and embedded files by
  the document's own ids (§3.1), because content may legally name something the document does
  not have.
* **No Office Open XML in core payloads.** What DeckCraft keeps of an imported file's markup
  is in `x.deckcraft.ooxml` (§3.7).
* **No references out.** A hyperlink's address and a linked item's `link` are content; a
  reader never needs them to read the deck. A `program` action is never run.
* **No editing history beyond saves.** Undo steps are not stored; every save is a revision
  (`spec/CRAFT-BASE.md` §3) with a work note.
* **No definition, yet, of the video and compressed audio formats** an asset may be in
  (§3.3). The files are carried exactly; the gap is stated per file in
  `definition: "pending"`.

Within `presentation/1`, evolution is additive only (law 12): a later revision of the profile
may add node types, optional members and enum values; a reader of this revision skips what it
does not know.

## 9. Relation to the other ArtCraft profiles (informative)

`presentation/1` shares with `vector-art/1`, `rich-document/1`, `raster-layers/1` and
`spreadsheet/1` the container, the base nodes, the revision log, the rule that a foreign-
encoded original is carried verbatim with its format definition, and these conventions with
the same keys and values as `vector-art/1`: `length_unit`, `x_axis`, `y_axis`, `paint_order`,
`pixel_origin`, `alpha_mode`, `number_format`. Its `core.media.image` is, like
`rich-document/1`'s node of the same name, a PNG that is a picture's pixels.

It does NOT reuse their content node types, and a reader of one of those profiles cannot read
a slide without this document: a shape here is positioned by a box, a rotation and two flips
and outlined by a preset or a path string (`vector-art/1`: anchors with absolute handles and
an affine matrix); a colour is a theme slot or an 8-bit sRGB value with an ordered list of
transforms (`vector-art/1`: unit-range components in one of four colour models); text is
paragraphs of runs that inherit through placeholders and master text styles
(`rich-document/1`: blocks with a style sheet); a chart carries its own data
(`spreadsheet/1`'s `core.sheet.chart` names cell ranges of a sheet). Each of those is what a
slide deck is, not a variation in spelling, and each is defined completely here.
