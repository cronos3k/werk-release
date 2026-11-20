# werk Profile: Spreadsheet — `spreadsheet/1`

Status: **v1.** Manifest schema: `spec/schemas/manifest.spreadsheet.schema.json`.
Conventions map: `spec/conventions-map.spreadsheet.json`.

A spreadsheet workbook: sheets of cells holding numbers, text and formulas, with their
formats, names, tables, charts and everything else a spreadsheet application keeps. This
document is written to be implemented from — a reader AND a writer — by someone who has this
package and nothing else, and has never seen the application that wrote it.

The werk manifesto's twelve laws govern everything here; where this document is silent, the
laws decide. It builds on, and does not restate:

* `spec/SPEC.md` — the container (§1), the manifest (§2), which file of a node is its payload
  (§2.1), the binary envelope (§3.1), versions (§5), signatures (§6), loaders (§7), the reader
  checklist and refusal scopes (§10);
* `spec/CRAFT-BASE.md` — what every ArtCraft capsule shares: the package root, the `revisions`
  node (§3), paths and the `@N` marker (§4), epistemic stamps (§5), encodings and
  foreign-encoded payloads with their format definitions (§6, §6.1), signatures across Saves
  (§7), writing a capsule without this software (§8);
* `spec/MINI-SPECS.md` — zip, JSON, UTF-8, SHA-256, PNG, byte by byte;
* `spec/layouts/ENVELOPE.layout.txt` — the frame of the two binaries, and its MessagePack subset;
* `spec/formats/<id>.md` — the definition of each foreign format a file uses: `zlib-deflate`
  for the compressed cell bands (§3.3), the picture formats (§3.6), `ovba` and `cfb` for a VBA
  project (§3.7). Each is a byte-level definition with test vectors, and names a reference
  implementation that travels as source under `tools/`.

Its own parts: this narrative; a JSON Schema per JSON node type (`spec/schemas/core.sheet.*`,
`x.gridcraft.*` — every field has a description with its unit, range and meaning; **the
schemas are normative for field-level detail and this document does not repeat them**); two
layout grammars (`spec/layouts/core.sheet.cells.layout.txt`, `core.sheet.computed.layout.txt`);
and worked examples under `spec/examples/spreadsheet/` (§9).

If you only want the content out, read `HOW-TO-READ.md` at the package root first.

---

## 1. Container

Exactly `spec/SPEC.md` §1 and `spec/CRAFT-BASE.md` §1: a directory tree, or that tree as a
store-mode zip (`.werk`). The profile's own files:

```
workbook/workbook.json            the structure node
workbook/styles.json              cell formats, named styles, theme
workbook/names.json               defined names
workbook/external-values.json     cached values of other workbooks' cells (if any)
preview/preview.png               a picture of the first visible sheet's top-left region
preview/first-rows.csv            that sheet's leading rows
sheets/sheet-<uid>/sheet.json     one sheet: name, geometry, attached features
sheets/sheet-<uid>/cells.json     the INDEX of its authored cells (§3.3)
sheets/sheet-<uid>/cells/rows-<first row, 7 digits>.wkx.zlib
                                  one BAND of rows: a zlib stream; inflated, an envelope WKX0
sheets/sheet-<uid>/computed.json  the index of its cached formula results (§3.4)
sheets/sheet-<uid>/computed/rows-<first row>.wkx.zlib
                                  one band: a zlib stream; inflated, an envelope WKX1
sheets/sheet-<uid>/chart-<id>.json, pivot-<id>.json
media/<hash>.png                  a picture that is PNG
media/<hash>.jpg | .gif | .bmp | .tif | .emf | .wmf
                                  a picture in a defined foreign format, verbatim
media/<hash>.rendition.png        a PNG decoded from a JPEG picture
workbook/vba.json, workbook/vbaProject.bin
                                  a VBA project, verbatim, with its descriptor (§3.7)
tools/format-<id>-reference/      reference implementation (source) of a foreign format in use
x/gridcraft/...                   extension nodes (§3.7)
```

`<uid>` is the sheet's stable number (§3.2); `<hash>` is a prefix (16 hex digits, longer only
on a collision) of the sha256 of the picture's original bytes. **Never derive a path from these
patterns: every path is declared in `MANIFEST.json`, and a superseded version of a file has an
`@N` marker in its name (`spec/CRAFT-BASE.md` §4).**

**Preview tier** (law 9), physically first in the zip form, in this order: the base tier
(`MANIFEST.json`, `SIGNATURE.json`, `LICENSE`, `README.txt`, `HOW-TO-READ.md`, `loaders/`,
`spec/`, `revisions/`), then `workbook/workbook.json`, then `preview/`. A store that has
fetched only that prefix can show the workbook's picture, its first rows, its sheet count and
its history. `container.preview_tier` is the authority.

## 2. MANIFEST.json

Validated by `spec/schemas/manifest.spreadsheet.schema.json`, which the manifest names in
`manifest_schema`.

* `profile` is `"spreadsheet/1"`.
* `conventions` — the 34 values of §5. A reader checks them before reading payloads.
* `primary.document` (REQUIRED): the node_id of the one `core.sheet.workbook` node.
  `primary.preview` (present unless the workbook has no sheet): the node_id of the
  `core.sheet.preview` node, the PNG a file browser shows.
* `entity.uuid` identifies the DOCUMENT: every Save of the same workbook carries the same
  uuid; a duplicate saved as a new document gets a new one. `entity.name` is a listing label
  only — the workbook's title is `props.title` in the workbook node.
* `formats` maps each foreign format in use to its definition document
  (`spec/CRAFT-BASE.md` §6.1): `zlib-deflate` whenever a sheet holds a cell; `jpeg` (with
  `jpeg-segments`, which it builds on), `gif`, `bmp`, `tiff`, `emf-wmf` for pictures; `ovba` and
  `cfb` for a VBA project. A format is listed only when a file in it is present.
* Which file is in which format is said per node, in its `meta`: `payload_format` names the
  format of the node's payload; `file_formats` maps a file ROLE to a format id for the node's
  other files (`{"band": "zlib-deflate"}`, `{"project": "ovba"}`). A file's role is the `role`
  of its entry in the version's `files` list.

## 3. Node families

| type | how many | payload | defined by |
|---|---|---|---|
| `core.spec`, `core.loader`, `core.license`, `core.readme`, `core.revisions` | base | — | `spec/CRAFT-BASE.md` §1, §3 |
| `core.sheet.workbook` | exactly 1 | JSON | `spec/schemas/core.sheet.workbook.schema.json` |
| `core.sheet.styles` | 1 | JSON | `spec/schemas/core.sheet.styles.schema.json` |
| `core.sheet.names` | 1 | JSON | `spec/schemas/core.sheet.names.schema.json` |
| `core.sheet.sheet` | 1 per sheet | JSON | `spec/schemas/core.sheet.sheet.schema.json` |
| `core.sheet.cells` | 1 per sheet | JSON index + band files (zlib; inflated: envelope `WKX0`) | `spec/schemas/core.sheet.cells.schema.json`, `spec/formats/zlib-deflate.md`, `spec/layouts/core.sheet.cells.layout.txt` |
| `core.sheet.computed` | 0 or 1 per sheet | JSON index + band files (zlib; inflated: envelope `WKX1`) | `spec/schemas/core.sheet.computed.schema.json`, `spec/formats/zlib-deflate.md`, `spec/layouts/core.sheet.computed.layout.txt` |
| `core.sheet.chart` | 1 per chart | JSON | `spec/schemas/core.sheet.chart.schema.json` |
| `core.sheet.pivot` | 1 per PivotTable | JSON | `spec/schemas/core.sheet.pivot.schema.json` |
| `core.sheet.image` | 1 per distinct PNG picture, and per rendition | PNG | `spec/MINI-SPECS.md` §8 |
| `core.sheet.picture` | 1 per distinct JPEG / GIF / BMP / TIFF / EMF / WMF picture | the original bytes | `spec/formats/<id>.md` via `meta.payload_format` |
| `core.sheet.vba-project` | 0 or 1 | JSON descriptor + the project, verbatim | `spec/schemas/core.sheet.vba-project.schema.json`, `spec/formats/ovba.md` (on `cfb.md`) via `meta.file_formats` |
| `core.sheet.preview` | 0 or 1 | PNG | §3.6 |
| `core.sheet.preview-rows` | 0 or 1 | UTF-8 text (CSV) | §3.6 |
| `core.sheet.external-values` | 0 or 1 | JSON | `spec/schemas/core.sheet.external-values.schema.json` |
| `core.tool` | 1 per foreign format in use | source + JSON | `spec/SPEC.md` §3.17; written by the container library |
| `x.gridcraft.ooxml` | 0 or 1 per owner | JSON index + part files | `spec/schemas/x.gridcraft.ooxml.schema.json` |
| `x.gridcraft.vba` | 0 or 1 | JSON descriptor + bytes in no defined format | `spec/schemas/x.gridcraft.vba.schema.json` |
| `x.gridcraft.source.media` | 1 per picture in an undefined format | opaque | `spec/layouts/x.gridcraft.source.media.layout.txt` |
| other `x.*` | any | anything | the extension's own layout file |

One node names another by `node_id`, in a payload field whose schema says
`"format": "werk-node-ref"`. A payload names a file only where its schema says so: the band
list of a store index (§3.3), by hash. Every string that a schema marks
`"format": "werk-content-text"` is CONTENT a person or a source file supplied, and every string
marked `"format": "werk-provenance-note"` is a note about an origin: **a reader never resolves
either** — not a hyperlink target, not a path that appears in a cell comment, not the recorded
location of an external workbook.

### 3.1 `core.sheet.workbook` — node_id `workbook`

One file, `workbook/workbook.json`. The ORDER of the sheets (`sheets`: node_ids, first tab
first), which sheet is active, the date system (§5.3), calculation settings, document
properties, structure protection, custom lists, and the node_ids of the styles, names and —
when present — VBA, kept-OOXML and external-values nodes. It carries no sheet content.

### 3.2 `core.sheet.sheet` — node_id `sheet-<uid>`

One file, `sheets/sheet-<uid>/sheet.json`. `<uid>` is a positive integer that identifies the
sheet for the life of the document: it does NOT change when the sheet is renamed or moved, it
is never reused after the sheet is deleted, and it is the `uid` field of the payload. A writer
adding a sheet takes a number larger than every `sheet-<n>` node id anywhere in the manifest
(including nodes that are no longer part of the document).

The payload holds the sheet's name; column and row sizes, visibility and outline (`cols`,
`rows`: only the ones that differ from the default); merged cells; frozen panes; view
settings; conditional formats; data validations; tables; the AutoFilter; comments and
hyperlinks (keyed by the cell's A1 address); shapes, sparklines, slicers; protection; page
setup; and the node_ids of what has a node of its own: `cells`, `computed`, `charts`, `pivots`,
and — inside `images` and `cell_pictures` — the pictures. A minimal sheet payload is in §7.

### 3.3 `core.sheet.cells` — node_id `sheet-<uid>-cells`

Every stored cell's position, constant value, formula source text and format index. Stamp:
`authored`. A formula cell's value is NOT here (its `kind` is 0): results are derived data
(§3.4).

The node is a **banded store**: a small index and one file per band of rows.

* **The index** is the node's payload, `sheets/sheet-<uid>/cells.json`
  (`spec/schemas/core.sheet.cells.schema.json`):

      {"schema_version":1, "store":"cells", "sheet_uid":1, "band_rows":4096,
       "band_format":"zlib-deflate", "inflated_layout":"spec/layouts/core.sheet.cells.layout.txt",
       "entry_count":14,
       "bands":[{"path":"sheets/sheet-1/cells/rows-0000000.wkx.zlib",
                 "first_row":0, "row_count":4096, "entry_count":14,
                 "stored_size":570,  "stored_sha256":"325dd827…",
                 "inflated_size":1744, "inflated_sha256":"47660b75…"}]}

* **A band** holds the cells of rows `first_row` to `first_row + row_count - 1` and no others.
  Bands are listed in ascending row order and do not overlap; a range of rows with no stored
  cell has no band; a sheet with no stored cell has `"bands": []` and no band file.
* **A band file** is a file of the same node version with role `band`. It is ONE zlib stream
  (RFC 1950: a two-byte header, raw DEFLATE data, a four-byte Adler-32 of the inflated bytes).
  The format is defined, byte by byte, in `spec/formats/zlib-deflate.md`; every common
  platform has an inflater (`zlib.decompress` in Python, `inflate` in zlib, `DecompressionStream
  ("deflate")` in a browser), and a complete one in plain Python travels in the package
  (`tools/format-zlib-deflate-reference/inflate.py`). The node's `meta` says
  `{"file_formats": {"band": "zlib-deflate"}}`.
* **Inflated**, a band is one werk binary envelope, exactly as
  `spec/layouts/core.sheet.cells.layout.txt` describes: flat little-endian columns, its own
  string table and formula table. A band is complete in itself — it can be read without any
  other band. Rows and columns in it are absolute (not relative to the band).

To read the store: for each band in the index, in order — find the file in the node version's
`files` whose `sha256` equals the band's `stored_sha256` (do not build its path: an earlier
version's file carries an `@N` marker, §1); verify it as any file; inflate it; check
`inflated_size` and `inflated_sha256`; decode the envelope; refuse the node if a cell lies
outside the band's rows. The sheet's cells are the cells of all bands.

Why it is built this way. A Save stores a file again only when its bytes changed (§4), so
changing one cell of a 100,000-row sheet stores the one band that holds its row — and the
index — and relists the rest. Compression is there because a column of row numbers or of
small format indices is mostly zero bytes: a million-cell sheet is about 39 MiB as one
envelope and about 5 MiB as bands. It is applied per band, never to the zip (which stays
store-mode), so a band is an ordinary hashed file.

A writer chooses `band_rows` (this application writes 4096; 1048576 means one band for the
whole sheet); band k then starts at row k × `band_rows`. A reader does not depend on the
choice. A writer may compress at any level and with any DEFLATE implementation: two correct
writers produce different band bytes for the same cells, and the same inflated bytes.

### 3.4 `core.sheet.computed` — node_id `sheet-<uid>-computed`

The cached result of every formula cell and every value a dynamic-array formula spilled.
Absent for a sheet with no formulas. It is a banded store exactly like §3.3: the index
`sheets/sheet-<uid>/computed.json` (`"store":"computed"`), band files
`sheets/sheet-<uid>/computed/rows-<first row>.wkx.zlib`; a band, inflated, is the envelope of
`spec/layouts/core.sheet.computed.layout.txt`, holding the entries of its rows; the rectangle a
dynamic array fills (`spill-ranges`) is recorded in the band of its anchor cell.

Stamp: **`measured`** (law 5). Its `input_files`, in this order: the workbook node's file; the
names node's file; then, for each sheet in the set D, in tab order, that sheet's `sheet.json`
and its cells INDEX `cells.json` (the index holds the sha256 of every band, so it stands for
the whole store). D is the sheet itself plus every sheet its formulas can read — through a
sheet-qualified reference (`Other!A1`), a 3-D span (`First:Last!A1`: every sheet between the
two, inclusive), a defined name (followed through its own formula), or a table name —
transitively (if it reads B and B reads C, then C is in D). A sheet holding a formula that can
address cells it does not name — `INDIRECT`, `CELL`, `INFO`, `SHEET`, `SHEETS`, `GETPIVOTDATA`
— has D = every sheet. `input_hash` is computed over them as `spec/CRAFT-BASE.md` §5 says.
`input_params` records `formula_grammar`, the workbook's `calc_mode` at the time, and
`volatile_functions`: `true` when a formula of the sheet uses `NOW`, `TODAY`, `RAND`,
`RANDBETWEEN`, `RANDARRAY`, `OFFSET`, `INDIRECT`, `CELL` or `INFO`, whose results a
recomputation does not reproduce.

What the stamp promises and what it does not: the values are what the writing application held
for these formulas when it saved. With `calc_mode` `Manual` they may predate the last edit.
A reader with a formula engine recomputes when the `input_hash` no longer matches the inputs it
finds, or whenever it prefers to; a reader without one shows these values and says they are
cached.

### 3.5 Styles, names, charts, pivots

**`core.sheet.styles`** (node_id `styles`, `workbook/styles.json`): `cell_formats` — the array
a cell's `style` number indexes, entry 0 being the default format; it only grows, so an index
keeps its meaning across revisions — plus the named styles and the theme (twelve colours and
two font names). A format is complete: font, fill, six border lines, alignment, number format
code, protection.

**`core.sheet.names`** (node_id `names`, `workbook/names.json`): the defined names; a name
local to a sheet names that sheet by node_id (`scope_sheet`).

**`core.sheet.chart`** (node_id `sheet-<uid>-chart-<id>`, file
`sheets/sheet-<uid>/chart-<id>.json`): one chart, DESCRIBED — its type, anchor, titles and the
cell ranges of its series as reference text. `<id>` is the chart's object id. If two charts of
one sheet carry the same object id (possible in imported files), the second and later get the
suffix `-dup1`, `-dup2`, … in node id and file name. The sheet node lists its charts in
drawing order.

**`core.sheet.pivot`** (node_id `sheet-<uid>-pivot-<id>`): one PivotTable's definition. The
report a pivot produces is ordinary cells of its sheet (written by the last refresh, stored in
the cells store), so a reader that does not implement pivots still reads the report.

### 3.6 Pictures, the preview, external values

**Pictures.** A picture is stored once, whatever the number of places that show it, in a node
named by its content: node_id `media-<hash>`.

* original bytes are PNG → type `core.sheet.image`, file `media/<hash>.png`;
* original bytes are JPEG, GIF, BMP, TIFF, an Enhanced Metafile (EMF) or a Windows Metafile
  (WMF) → type `core.sheet.picture`, file `media/<hash>.jpg` / `.gif` / `.bmp` / `.tif` /
  `.emf` / `.wmf`, the bytes VERBATIM. The node's `meta.payload_format` is the format id
  (`jpeg`, `gif`, `bmp`, `tiff`, `emf-wmf`), and `MANIFEST.json` → `formats[<id>]` is the path
  of that format's definition document (`spec/formats/jpeg.md` …): a normative, byte-level
  definition with test vectors from which a reader can be built. A reference implementation in
  standard-library Python travels as a `core.tool` node (`tools/format-<id>-reference/`); it
  is source, a convenience, and never run automatically;
* anything else → type `x.gridcraft.source.media` (§3.7).

The format of a picture is decided by its leading bytes (the `sniff` rules of each definition),
never by a file name or a declared media type. A definition states its own coverage, in its
header (`coverage`, `coverage_note`) — for example, the `emf-wmf` definition defines both
containers, every record's name and a drawing subset as a display list, and does not define
rasterisation. A picture outside a definition's coverage is still carried verbatim under that
definition; a reader built from it reports what it cannot decode instead of guessing.

Beside a JPEG that the writer could decode there is a second node, `media-<hash>-png`, type
`core.sheet.image`, file `media/<hash>.rendition.png`: the same picture decoded to 8-bit PNG,
stamped `measured` with the JPEG as its one input. It is a second master for readers that only
decode PNG; the original is authoritative.

The sheet node places pictures: `images` (floating: object id, anchor) and `cell_pictures`
(the content of a cell), each with `mime`, `alt`, `media` (the node of the original bytes) and,
where it exists, `png` (the rendition).

**`core.sheet.preview`** (node_id `preview`, `preview/preview.png`): a 640×360, 8-bit RGB
picture of the top-left region of the first VISIBLE sheet (the first sheet when none is
visible) — row and column headers, gridlines, fills, borders, each cell's displayed text in a
built-in 5×7 pixel font, and an outlined box where a chart, picture or shape sits. A legible
sketch for a file browser, not a rendering of record. `measured`; inputs: the workbook, styles
and sheet files, the sheet's cells and (if any) computed file; `input_params` names the sheet
(`sheet`), the size and the renderer.

**`core.sheet.preview-rows`** (node_id `preview-rows`, `preview/first-rows.csv`): the same
sheet's leading rows as CSV, for a reader that wants numbers before it wants a parser. Line 1
is a header of column letters (`A,B,C`); then rows 1 to min(last used row, 50), columns A to
min(last used column, Z). UTF-8; `,` between fields; every line ends with one LF; a field
containing `,`, `"`, CR or LF is wrapped in `"` with each `"` doubled. Values are RAW, with no
number format applied: a whole number of magnitude below 1e15 as plain digits (`42`); another
number from 1e-5 up to 1e15 in magnitude as a plain decimal with the fewest digits that read
back to the same value (`4.5`); anything else as mantissa `e` exponent (`1e300`, `1.5e-7`);
`TRUE` / `FALSE`; an error as its text (`#N/A`); a formula cell shows its cached result; an
empty cell is an empty field; a control character other than TAB, LF, CR is written as U+FFFD.
A date is therefore its day number (§5.3). `measured`; inputs: the sheet's cells and computed
files.

**`core.sheet.external-values`** (node_id `external-values`): a formula may read a cell of
ANOTHER workbook — `[1]Rates!$A$1` reads cell A1 of sheet `Rates` of external workbook number
1. That workbook is not in this file and can never be obtained from it (law 1). What travels
is the value the application last saw there, in this node: per external workbook its number,
the sheets and their cached cells. `origin` is a note of where that workbook once was; a reader
MUST NOT open it. The node is `measured`, decoded from the kept OOXML part that holds the same
cache (§3.7); the application itself does not read it back.

### 3.7 Extension nodes

**The VBA project — `core.sheet.vba-project`** (node_id `vba`). A macro-enabled workbook's VBA
project is kept verbatim: `workbook/vbaProject.bin`, the file of role `project`, byte for byte
as it was in the source file. It is a Compound File Binary container holding the VBA project
storage, and both layers are defined in the package: `meta.file_formats` is
`{"project": "ovba"}`, `spec/formats/ovba.md` defines the project storage (its `dir` stream,
the compression of module source, the module streams) on top of `spec/formats/cfb.md` (the
compound file), and `tools/format-ovba-reference/` lists a project's modules and recovers their
source text. The payload is a descriptor, `workbook/vba.json`
(`spec/schemas/core.sheet.vba-project.schema.json`), whose `never_auto_execute` is the constant
`true`. **The project is embedded code. A consumer never executes, loads, compiles or
interprets it automatically — not on open, not on preview, not on any event.** Reading it as
data is not executing it. This application keeps it and never runs it.

A reader that skips every `x.*` node still has the whole spreadsheet: every cell, formula,
format, name, chart, pivot, the VBA project, and every picture in a defined format (PNG, JPEG,
GIF, BMP, TIFF, EMF, WMF). What lives ONLY in `x.gridcraft.*`:

* **`x.gridcraft.ooxml`** (node_id `ooxml-workbook`, and `sheet-<uid>-ooxml` per sheet):
  content of an imported OOXML (`.xlsx` / `.xlsm`) file that GridCraft does not model and
  keeps verbatim so that exporting to OOXML again loses nothing — custom XML, external-link
  records, connections, query tables, printer settings, form controls, OLE objects. The payload
  is an index (`x/gridcraft/ooxml/<owner>/index.json`); each kept part is a file of the same
  node beside it (`part-0001.bin`, …, `vml.bin`), byte for byte, with its size and sha256 in the
  index. Nothing in it is executed or fetched.
  It is in the extension namespace because the package carries no definition of what an OOXML
  part means (most parts are XML text; a printer-settings part is a device-specific binary).
* **`x.gridcraft.vba`** (node_id `vba-opaque`): bytes that a source file called its VBA project
  and that are NOT a compound file (a damaged or foreign macro part). They are kept verbatim
  (`x/gridcraft/vba/vbaProject.bin`) with the same descriptor and the same rule — never
  executed — and no definition is claimed for them. A workbook has either this node or the
  `vba` node above, never both.
* **`x.gridcraft.source.media`**: a picture's original bytes in a format this profile carries
  no definition for. The sheet's picture record says its media type.

### 3.8 Edges, and what dies with what

An edge reads source → target. With `requires`, a dead target kills the source; with
`enhances`, a dead target costs the source one feature.

| source | kind | target | why |
|---|---|---|---|
| `workbook` | enhances | each sheet, `styles`, `names`, `vba` (or `vba-opaque`), `ooxml-workbook`, `external-values` | a workbook with a damaged sheet is still a workbook |
| `sheet-<uid>` | enhances | its cells, computed, charts, pivots, pictures, kept OOXML | a sheet with a damaged chart is still a sheet |
| `sheet-<uid>-computed` | requires | every node whose file is one of its inputs (§3.4) | a cache cannot be trusted without what it was computed from |
| `preview`, `preview-rows` | requires | the nodes of their inputs | likewise |
| `media-<hash>-png` | enhances | `media-<hash>` | the rendition must survive damage to the original — that is what it is for |
| `external-values` | enhances | `ooxml-workbook` | a core node never requires an extension node |

What a reader does when a node is dead (bytes fail their hash, payload fails its schema or
layout, a `requires` target is dead) or of a type it does not know:

* `workbook` dead → load every `core.sheet.sheet` node that is part of the document, in
  manifest order, with default settings (date system D1900); say so.
* a sheet node dead, its cells node alive → load the cells as a sheet named
  `Recovered sheet <uid>` with default layout; say so. Both dead → the sheet is missing; say so.
* a cells node dead (its index, or ANY of its bands, fails) → the sheet is there, empty. A
  reader does not load the bands that are intact and present the result as the sheet.
* a computed node dead or absent → formula cells have no cached value; a reader with a formula
  engine recalculates, any other reader shows the formula.
* `styles` dead → every cell in the default format. `names` dead → no defined names.
* a chart, pivot or picture node dead → that object is missing; if a picture's original is dead
  and its PNG rendition is alive, show the rendition.
* `preview`, `preview-rows`, `external-values` dead → nothing of the document is lost.
* an unknown node type → skip it, report it, and (a writer) carry it unchanged through the next
  Save.

Never substitute an EARLIER version of one node into the current document because the current
one is damaged: a revision is a consistent set of node versions (§4).

## 4. Versions

`spec/CRAFT-BASE.md` §3 and §4 apply unchanged. Each Save appends one revision record with a
work note of at least 8 characters saying why the Save exists. A node gains a version only if
its content changed: editing one cell of one sheet versions that sheet's `cells` node, re-stamps
the `computed` nodes that list it as an input (same bytes, new `input_hash` — relisted, not
copied) and nothing else, and every other sheet's bytes stay in the file exactly once. Within
the new version of the cells node only the files whose bytes changed are stored — the index
and the band that holds the edited row; every other band is the same file, listed again. A
deleted sheet's nodes leave the document (the revision record no longer lists them) and stay
in the file. To read the workbook as it was at revision K, read revision record K and take
each node at the version it names (§6, last paragraph).

## 5. Conventions

### 5.1 The declared values

Every value below is in `MANIFEST.json` → `conventions` and pinned by the manifest schema;
`spec/conventions-map.spreadsheet.json` says which node types each governs.

| convention | value | meaning |
|---|---|---|
| `endianness` | `"le"` | every binary section is little-endian |
| `alignment_bytes` | `16` | sections of a binary start on this boundary |
| `text_encoding` | `"utf-8"` | every text, everywhere |
| `id_case` | `"kebab-case"` | every id |
| `hash_algorithm` | `"sha256"` | every hash |
| `signature_algorithm` | `"ed25519"` | `SIGNATURE.json` |
| `grid_rows` / `grid_cols` | `1048576` / `16384` | a sheet has rows 0..1048575, columns 0..16383 |
| `cell_index_base` | `0` | every NUMERIC row / column index is zero-based: A1 is row 0, col 0 |
| `a1_row_base` | `1` | a cell written as TEXT (`B7`, in formulas, comment and hyperlink keys) has a one-based row; column `A` is index 0 |
| `number_type` | `"ieee754-binary64"` | every numeric cell value, bit-exact |
| `date_serial_unit` | `"day"` | a date is a number of days; the fraction is the time of day |
| `date_1900_serial_of_1900_01_01` | `1` | §5.3 |
| `date_1900_fictitious_leap_day_serial` | `60` | §5.3 |
| `date_1900_serial_of_1900_03_01` | `61` | §5.3 |
| `date_1904_serial_of_1904_01_01` | `0` | §5.3 |
| `formula_grammar` | `"excel-a1-en-us"` | §5.2 |
| `formula_leading_equals` | `false` | stored formula text has no leading `=` |
| `formula_argument_separator` | `"comma"` | `,` between arguments |
| `formula_decimal_separator` | `"period"` | `.` in number literals |
| `formula_array_row_separator` | `"semicolon"` | `{1,2;3,4}`: `;` between rows, `,` within a row |
| `length_unit` / `points_per_inch` | `"point"` / `72` | widths, heights, offsets, font sizes |
| `page_margin_unit` | `"inch"` | page margins |
| `angle_unit` | `"degree"` | text rotation, counter-clockwise positive |
| `y_axis_direction` | `"down"` | rows, offsets and pixel rows grow downwards |
| `color_space` | `"srgb"` | every colour and every picture |
| `color_rgb_packing` | `"0xRRGGBB"` | an RGB colour is red*65536 + green*256 + blue |
| `theme_tint_scale` | `1000` | a tint is in thousandths, -1000..1000 |
| `preview_pixel_origin` | `"top-left"` | preview row 0 is the top row |
| `preview_sample_format` | `"rgb8"` | 8 bits per channel, no alpha |
| `csv_field_separator` / `csv_record_terminator` / `csv_quote` | `"comma"` / `"lf"` / `"double-quote"` | the preview CSV |

A reader that does not implement a node-scoped value refuses the node types it governs and
still lists, verifies and extracts everything; a container-scoped one (`text_encoding`,
`id_case`, `hash_algorithm`) refuses the file.

### 5.2 Formula text

Formula text appears in cells (the cells store, §3.3), defined names, conditional formats, validations,
table columns, chart series and pivot definitions. It is the spreadsheet formula language as an
en-US user types it, without the leading `=` unless a field's description says otherwise.

```
formula    := expr
expr       := expr binop expr | prefix expr | expr "%" | "(" expr ")" | atom
atom       := number | string | "TRUE" | "FALSE" | error | array | reference | name
            | function "(" [ arg { "," arg } ] ")"
arg        := expr | (nothing: an omitted argument, as in  F(1,,3) )
number     := digits [ "." digits ] [ ("E"|"e") ["+"|"-"] digits ]        e.g. 12  0.5  1E-7
string     := '"' characters, a quote written as two quotes '"'         e.g. "say ""hi"""
error      := #NULL! | #DIV/0! | #VALUE! | #REF! | #NAME? | #NUM! | #N/A | #SPILL! | #CALC!
array      := "{" row { ";" row } "}"      row := constant { "," constant }
function   := an upper-case English function name: SUM, IF, VLOOKUP, XLOOKUP, SEQUENCE, ...
              (LET and LAMBDA parameters and defined names are spelled as the author did)
```

Binary operators, tightest-binding first:

| operators | meaning |
|---|---|
| `:` | range between two references (`A1:B9`) |
| (a space) | intersection of two references |
| `,` inside parentheses | union of references |
| `^` | power |
| `*` `/` | multiply, divide |
| `+` `-` | add, subtract |
| `&` | join two texts |
| `=` `<>` `<` `>` `<=` `>=` | comparison, giving TRUE or FALSE |

Prefix `-` and `+`; postfix `%` (divide by 100); prefix `@` (implicit intersection); postfix
`#` on a cell reference (`D1#`: the whole block a dynamic-array formula in D1 spilled into).

References (A1 style; the row number is ONE-based):

| form | example | means |
|---|---|---|
| cell | `B7` | column B, row 7 → numeric row 6, col 1 |
| absolute markers | `$B$7`, `B$7`, `$B7` | the same cell; `$` only says which part stays fixed when the formula is copied |
| range | `A1:C9` | the rectangle, corners included |
| whole columns / rows | `A:C`, `3:5` | every row of the columns / every column of the rows |
| another sheet | `Sheet2!A1`, `'My Sheet'!A1:B2` | the name is quoted with `'` when it is not letters, digits, `_`, `.`; a `'` inside is doubled |
| 3-D | `Jan:Mar!B2` | the same cell on every sheet from `Jan` to `Mar` in tab order |
| another workbook | `[1]Rates!$A$1` | external workbook number 1 — cached values in §3.6 |
| structured | `Sales[Amount]`, `Sales[[#Totals],[Amount]]`, `[@Amount]` | a table's column; `#All`, `#Data`, `#Headers`, `#Totals`, `@` (this row) |
| name | `TaxRate` | a defined name (`core.sheet.names`) or a table |

Sheet names compare case-insensitively. A formula that does not parse in this grammar is kept
as its text and has the value `#NAME?`.

This profile fixes the SYNTAX. It does not define what each of the several hundred functions
computes: a reader that needs results without implementing them reads the computed store (§3.4).

### 5.3 Dates

There is no date type. A date or time is a NUMBER whose cell format (`num_fmt`, e.g.
`yyyy-mm-dd`, `hh:mm`) displays it as one. The number counts days; its fraction is the time of
day (0.5 = 12:00:00). `date_system` in the workbook node selects day zero:

* `"D1900"` — serial 1 is 1900-01-01. Serial 60 is 1900-02-29, **a day that never existed**
  (an error of early spreadsheets that every spreadsheet keeps). Therefore, for serial n ≥ 61:
  date = 1899-12-30 + n days; for 1 ≤ n ≤ 59: date = 1899-12-31 + n days. Check: 45000 is
  2023-03-15; 61 is 1900-03-01; 59 is 1900-02-28.
* `"D1904"` — serial 0 is 1904-01-01; date = 1904-01-01 + n days. No fictitious day.

### 5.4 Number format codes, colours, sizes

`num_fmt` is a format code: sections separated by `;` (positive; negative; zero; text), in
which `0` is a required digit, `#` an optional digit, `.` the decimal point, `,` a thousands
separator, `%` multiplies by 100, `E+00` is scientific notation, `"text"` and `\c` are
literals, `@` is the cell's text, `[Red]`-style brackets set a colour, and `y m d h s` (with
`AM/PM`) are date and time parts. `General` is the default: as many digits as needed. The code
decides only how a number is SHOWN; the stored number is in the cells store.

A colour is `"Auto"`, `{"Rgb": n}` with n = red*65536 + green*256 + blue, or
`{"Theme": [slot, tint]}`; the schemas give the tint arithmetic. Column widths, row heights and
anchor offsets are in points (1/72 inch); a column or row without a record has the sheet's
default size.

## 6. Reading

1. Open the container: a directory, or a store-mode zip (`spec/MINI-SPECS.md` §1).
2. Parse `MANIFEST.json`. Check `profile` is `spreadsheet/1` and the conventions of §5.1 you
   rely on have the values of §5.1.
3. Take `primary.document` → that node → its `active` version → its payload file. To get any
   node's payload: the version's `payload_file` if it has one, else its only file — never
   `files[0]` of several (`spec/SPEC.md` §2.1). Verify the file's sha256 and size against the
   manifest before using it. Parse the workbook JSON.
4. Read the `styles` node (cell formats) and the `names` node.
5. For each node_id in `sheets`, in order: read the sheet JSON. Read its `cells` node: the
   payload is an index (§3.3); for each band it lists, take the file of the node version whose
   sha256 is the band's `stored_sha256`, inflate it (zlib), and decode the result with
   `spec/layouts/core.sheet.cells.layout.txt`: each cell's row, column, value, format index and
   formula text. If the sheet has a `computed` node, read its bands the same way with
   `spec/layouts/core.sheet.computed.layout.txt` and give each formula cell its cached value
   and each spilled cell its value (the layout's section 2.1 gives the order of precedence).
6. Charts, pivots, pictures: follow the node_ids in the sheet JSON. For a picture whose `media`
   node is a `core.sheet.picture`, the format is `meta.payload_format` of that node and its
   definition is at `formats[<that id>]` in the manifest. A VBA project, if the workbook names
   one, is data to keep or to list (§3.7), never to run.
7. A node that is dead or unknown costs that node (§3.8): say what was lost and continue.
8. Report the signature state in one of the four fixed words (`spec/CRAFT-BASE.md` §7).

To read the workbook as it was at revision K: read version K of the node `revisions`; its
`nodes` object maps node_id → version number; use that version of each node in steps 3–6
instead of `active` (a node that is not a key was not part of the document then).

`spec/examples/spreadsheet/read_spreadsheet.py` does all of this with the Python standard
library (about 650 lines) and prints or exports the content.

## 7. Writing a minimal valid `spreadsheet/1` capsule

This section is normative. A capsule built exactly as below is accepted by every
`spreadsheet/1` reader. `spec/examples/spreadsheet/write_minimal.py` does all of it with the
Python standard library and nothing else; run it against any `spreadsheet/1` capsule that
holds at least one cell (it copies `loaders/`, `spec/` and the zlib reference tool from there,
which is what `spec/CRAFT-BASE.md` §8 prescribes):

    python spec/examples/spreadsheet/write_minimal.py <existing capsule> <new.werk>

The document: one sheet, `Prices`, with `A1` "Item", `B1` "Price", `A2` "Tea", `B2` 4.5,
`A3` "Coffee", `B3` 3, `A4` "Total", `B4` the formula `SUM(B2:B3)`.

**7.1 The five nodes.** Four have one file; the cells store has two (its index and one band).
The JSON payloads are one line of JSON (no spaces after `,` and `:`, keys in the order the
script writes them) followed by one line feed. These are the checkpoints; if your bytes
differ, find the difference before going on. (Any valid spelling of the same JSON is an equally
valid payload.)

| what | bytes | sha256 |
|---|---|---|
| the cells envelope: the ONE band of the cells store, before compression (§7.2) | 1472 | `ae1390ac8b28a96a9ce9d9b03c964fab5efcd0db664f8625bb310741fa457a6b` |
| `sheets/sheet-1/sheet.json` | 921 | `ad90845425cb78a2a182f2408cf9962680f603d412c0011e203544b127b5c708` |
| `workbook/workbook.json` | 413 | `4e5bb51b250cbf1fb253cd6ecb08496596d8d8c825e338965c0092686ced5f5d` |
| `workbook/styles.json` | 827 | `4867c00782e6e418aa7b2e053c860b4f435effb79e17966d84312b851f04f39f` |
| `workbook/names.json` | 32 | `7636b464392b6011215a6d3599d14115b20a878f0b24d35c288274e54cc1a8bc` |

`workbook/names.json` is exactly `{"schema_version":1,"names":[]}` and a line feed.

The band file `sheets/sheet-1/cells/rows-0000000.wkx.zlib` (the envelope as one zlib stream)
and the index `sheets/sheet-1/cells.json` (which records the band file's hash) are NOT
checkpoints: a zlib stream is not unique, so another compressor gives other bytes for the same
envelope. Check them the other way round — inflate your band and compare with the first row of
the table; the index's `inflated_sha256` is that hash.

`workbook/workbook.json`:

    {"schema_version":1,"sheets":["sheet-1"],"active_sheet":"sheet-1","active_sheet_index":0,
     "date_system":"D1900","calc":{"mode":"Automatic","iterative":false,"max_iterations":100,
     "max_change":0.001,"precision_as_displayed":false},"props":{"title":"Minimal prices",
     "subject":"","author":"","company":"","keywords":"","description":""},
     "protected_structure":false,"custom_lists":[],"styles":"styles","names":"names"}

(shown wrapped; the file is one line). `workbook/styles.json` holds one cell format — the
default, every part spelled out — no named styles, and a theme; `sheets/sheet-1/sheet.json`
holds the sheet's name and uid, `"cells":"sheet-1-cells"`, and every other field of the sheet
schema at its empty or default value. Both are written in full by `styles_payload()` and
`sheet_payload()` of the script, and both validate against their schemas.

**7.2 The cells store** (§3.3). All eight cells are in rows 0..4095: one band. First the
band's envelope (`spec/layouts/core.sheet.cells.layout.txt`). Eight cells sorted by
(row, col); zero-based positions:

| cell | row | col | kind | number | ref | style | formula |
|---|---|---|---|---|---|---|---|
| A1 | 0 | 0 | 2 text | 0 | 0 ("Item") | 0 | 4294967295 |
| B1 | 0 | 1 | 2 text | 0 | 1 ("Price") | 0 | 4294967295 |
| A2 | 1 | 0 | 2 text | 0 | 2 ("Tea") | 0 | 4294967295 |
| B2 | 1 | 1 | 1 number | 4.5 | 0 | 0 | 4294967295 |
| A3 | 2 | 0 | 2 text | 0 | 3 ("Coffee") | 0 | 4294967295 |
| B3 | 2 | 1 | 1 number | 3.0 | 0 | 0 | 4294967295 |
| A4 | 3 | 0 | 2 text | 0 | 4 ("Total") | 0 | 4294967295 |
| B4 | 3 | 1 | 0 empty | 0 | 0 | 0 | 0 (`SUM(B2:B3)`) |

String table: `Item`, `Price`, `Tea`, `Coffee`, `Total` (offsets 0, 4, 9, 12, 18, 23). Formula
table: one entry, `SUM(B2:B3)` (offsets 0, 10), `formula-array` entry `0 0 0 0 0`. The array
table is empty. Sections are written in the order of the layout's table, each on a 16-byte
boundary; the header carries `sheet_uid` 1 and the six counts; envelope version 1, magic
`WKX0`. The header is canonical MessagePack (`spec/layouts/ENVELOPE.layout.txt` §4.3); because
the header contains the sections' absolute offsets and its own length decides where the
payload starts, lay the file out, measure the header, and repeat until the payload origin
stops moving (two passes). The result is 1472 bytes: header length 1075, payload origin 1088.

Then compress those 1472 bytes as one zlib stream (any level; `zlib.compress(data)` in
Python): that is the band file `sheets/sheet-1/cells/rows-0000000.wkx.zlib`. Then write the
index `sheets/sheet-1/cells.json`:

    {"schema_version":1,"store":"cells","sheet_uid":1,"band_rows":4096,
     "band_format":"zlib-deflate","inflated_layout":"spec/layouts/core.sheet.cells.layout.txt",
     "entry_count":8,"bands":[{"path":"sheets/sheet-1/cells/rows-0000000.wkx.zlib",
     "first_row":0,"row_count":4096,"entry_count":8,
     "stored_size":<size of the band file>,"stored_sha256":<its sha256>,
     "inflated_size":1472,"inflated_sha256":"ae1390ac…457a6b"}]}

No `core.sheet.computed` node is written: a writer without a formula engine does not cache
results (§3.4), and the sheet payload then has no `computed` field.

**7.3 The base files.** Copy every current file under `loaders/` and `spec/` from the existing
capsule unchanged (skip files whose name carries an `@N` marker); `spec/formats/zlib-deflate.md`
is among them when the existing capsule holds a cell. Copy the tool node
`format-zlib-deflate-reference` with its files (`tools/format-zlib-deflate-reference/…`): a
package that uses a format carries the reference implementation its definition names. Write
`LICENSE` (the full
licence text of your content, or an honest statement that its terms are not established),
`README.txt` and `HOW-TO-READ.md` (copy them).

**7.4 The revision record** `revisions/revision.json` (`spec/CRAFT-BASE.md` §3): `revision` 1,
`kind` `"save"`, a `note`, `created`, `producer`, and `nodes` mapping each of these twelve
node ids to `1`: `spec`, `license`, `readme`, `loader-python`, `loader-rust`, `loader-c`,
`format-zlib-deflate-reference`, `workbook`, `styles`, `names`, `sheet-1`, `sheet-1-cells`.

**7.5 The manifest.** Thirteen nodes (the twelve above and `revisions`), each with one version:

    {"v":1, "files":[{"path":…,"sha256":…,"size":…}], "note":"<at least 8 characters>",
     "producer":{"tool":…,"version":…}, "epistemic":"authored", "created":"<RFC 3339 UTC>"}

`"active":1`. Types: `workbook` `core.sheet.workbook`, `styles` `core.sheet.styles`, `names`
`core.sheet.names`, `sheet-1` `core.sheet.sheet`, `sheet-1-cells` `core.sheet.cells`. Edges:
`workbook` → `sheet-1` (role `sheet`), `styles` (role `styles`), `names` (role `names`), all
`enhances`; `sheet-1` → `sheet-1-cells` (`enhances`, role `cells`); every other node has
`"edges":[]`. The `readme` version lists two files and carries `"payload_file":"README.txt"`;
the three `core.loader` nodes carry the `meta` block of the existing capsule unchanged, and so
does the `core.tool` node (with its `payload_file`). The `sheet-1-cells` version lists two
files — the index with `"role":"payload"` and the band with `"role":"band"`,
`"media_type":"application/zlib"` — and carries `"payload_file":"sheets/sheet-1/cells.json"`;
the node carries `"meta":{"file_formats":{"band":"zlib-deflate"}}`. Copy
`werk`, `profile`, `manifest_schema`, `conventions_map`, `conventions` and `container` from
the existing manifest; drop `container.preview_prefix_bytes`; set `container.total_size_bytes`
to the sum of the sizes of all the files you list; copy from `schemas` and `layouts` only the
entries for node types you actually have; set `formats` to
`{"zlib-deflate": <the path the existing manifest gives>}`. Set `primary` to `{"document":"workbook"}`,
`license` to `{"file":"LICENSE","sha256":<its sha256>}`, a fresh `entity.uuid`, and compute
`spec_sha256` by `spec/SPEC.md` §2 over every `spec/` path you list.

**7.6 The container.** A store-mode zip: `MANIFEST.json` first, then the entries matching
`container.preview_tier` in its order, then the rest.

**7.7 Check.** `python loaders/werk_read.py <new.werk> --verify --strict` exits 0 and prints
`N/N files verified` (N is the number of files your manifest lists). Then read it back:
`python spec/examples/spreadsheet/read_spreadsheet.py <new.werk>` lists one sheet, `Prices`,
with 8 cells and 1 formula.

**Beyond the minimum.** A formatted cell: append a format to `cell_formats` and put its index
in the cell's `style`. A second sheet: nodes `sheet-2` and `sheet-2-cells`, its node_id
appended to the workbook's `sheets`, edges as above. A date: the day number (§5.3) in a cell
whose format's `num_fmt` is a date code. Cached results: a `core.sheet.computed` node per
§3.4, stamped `measured` with its inputs.

## 8. What this profile deliberately does not have

So that an absence reads as a decision:

* **No function semantics.** The grammar of formulas is fixed (§5.2); what `VLOOKUP` returns
  is not specified here. Cached results travel instead (law 5).
* **No rich text within a cell** (a cell's text has one format) and no cell-level font files:
  fonts are named, never embedded.
* **No rendering of record.** Charts are described, not drawn; the preview is a sketch.
* **No external data.** A link to another workbook travels as its cached values and a note;
  queries and connections are kept, opaquely, only for round trips to OOXML (§3.7).
* **No macro execution.** A VBA project is carried verbatim, with the definition of its
  format, and never run.
* **No encryption or access control.** Protection fields are settings of the editing
  application; password fields are hashes; nothing in the file is encrypted.
* **No cell-level deltas.** The unit of storage is a band of rows (§3.3): a Save that changes
  one cell stores that band again. Inserting a row moves every later cell, and so stores every
  later band of that sheet.
* **No compression beyond zlib, and none of the container.** The zip is store-mode; only the
  cell bands are compressed, each as one RFC 1950 stream whose definition travels in the file.

Within `spreadsheet/1` evolution is additive only (law 12): new optional fields, new node
types, new sections in the binaries (found by name; unknown ones are skipped). A change that
would make an existing reader read wrong values is `spreadsheet/2`.

## 9. Examples in this package

Under `spec/examples/spreadsheet/` (see its `README.md`): one real payload of every node type
(`workbook.example.json`, `sheet.example.json`, `styles.example.json`, `names.example.json`,
`chart.example.json`, `pivot.example.json`, `external-values.example.json`,
`ooxml-index.example.json`, `vba.example.json`, `first-rows.example.csv`,
`preview.example.png`), all cut from one small example workbook; for each of the two stores its
index (`cells.example.json`, `computed.example.json`), its one band as stored
(`cells.rows-0000000.example.wkx.zlib`, `computed.rows-0000000.example.wkx.zlib`), the same
band inflated (`cells.example.wkx`, `computed.example.wkx`) and an annotated hex dump of the
inflated bytes, byte by byte down to the decoded cells (`cells.example.hex.txt`,
`computed.example.hex.txt`); and the two standard-library programs, `read_spreadsheet.py` and
`write_minimal.py`.
