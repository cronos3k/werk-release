# werk-office -- Word, Excel and PowerPoint 2016 to werk and back

A command-line tool (`werk_office.py`) that turns a `.docx`, `.xlsx` or `.pptx` into a werk
package of the matching ArtCraft office profile, and turns such a package back into an Office
file. It drives the installed Office application through COM for what only Office can do (the
PDF rendition, rebuilding a document) and reads the OOXML itself, with the Python standard
library, for the structured nodes.

**The CLI is the deliverable.** No VBA / ribbon add-in was built: an add-in would need either
the same Python + pywin32 behind it or a second werk writer in VBA, and its gate would need an
interactive Office session; neither is cheap, so it is listed under *Not done*.

| input | profile | the original file | PDF rendition (made by Office) | structured nodes (decoded by werk-office) |
|---|---|---|---|---|
| `.docx` | `rich-document/1` | `core.package.binary`, `meta.payload_format` `opc` | `x.werk-office.rendition` | `core.text.document`, one `core.text.blocks` body run (paragraphs with bold / italic / underline / strike / size runs, alignment, outline level, tables, line / page breaks), `core.preview.text`, `core.text.properties` |
| `.xlsx` | `spreadsheet/1` | `x.werk-office.source` (the profile has no core node type for a whole package) | `x.werk-office.rendition` | `core.sheet.workbook`, `core.sheet.sheet` + `core.sheet.cells` per sheet (constants, formula text, booleans, error values, banded store of 4096 rows), `core.sheet.styles` (default only), `core.sheet.names` (empty) |
| `.pptx` | `presentation/1` | `core.media.asset`, encoding `zip` | `core.media.asset`, encoding `pdf` | `core.slide.document`, one plain master + blank layout, `core.slide.slide` per slide with its text shapes (position, preset geometry, paragraphs, bold / italic / size runs) |

Every package also carries what the profile requires of every capsule: `spec/` (the release
specification from the vendored library plus the profile's own documents, schemas, layouts,
examples and the format definitions in use: `zlib-deflate`, `zip`, `opc`, `pdf`), the three
bootstrap loaders, `LICENSE`, `README.txt` + `HOW-TO-READ.md`, the `revisions` record and the
reference decoders of the formats as `core.tool` nodes. Structured nodes and the PDF are stamped
`measured` with the original file as their input (`input_hash` per MINI-SPECS §11).

The profile definitions come from the ArtCraft capsules (`<artcraft-samples>`:
wordcraft `report.werk`, gridcraft `sales.werk`, deckcraft `sample-deck.werk`) and the format
library (`<artcraft-formats>`), copied into `profiles/` by
`tools/vendor_profiles.py` (sources and hashes in `profiles/VENDORED.json`).

## Install

* Windows, Microsoft Office 2016 (Word, Excel, PowerPoint), Python 3.8+ with **pywin32**
  (`win32com`). Nothing else: the werk library is vendored (`vendor/werk_single.py`, stdlib only;
  the release library at bundle `26e3e14`, sha256 `08242050…`). The packages are written through
  its documented API: `PackageWriter(..., conventions_map=...)`, `add_readme_file`,
  `add_spec_file`, `set_format`, `set_schema` / `set_layout`. One thing is still done by hand: the
  loader nodes' `capabilities` are cut to the list the Office profiles' schemas allow (see
  GATE-RESULTS.md).
* Copy this folder anywhere. `py -3.12 werk_office.py --help`.

## Use

    py -3.12 werk_office.py export report.docx report.werk          # also .xlsx, .pptx
    py -3.12 werk_office.py export deck.pptx deck.werk --no-pdf --name "Q3 deck"
    py -3.12 werk_office.py import report.werk report-back.docx       # the carried original, hash-checked
    py -3.12 werk_office.py import report.werk rebuilt.docx --rebuild # a NEW file from the structured nodes
    py -3.12 werk_office.py info report.werk                          # the release reader's verdict

`import` without `--rebuild` writes the carried original byte for byte; a package that carries
none (any ArtCraft wordcraft / gridcraft / deckcraft capsule) is rebuilt through Office from its
structured nodes. Output is one JSON object, including every Office instance the run started and
how it ended.

**How Office is driven.** Every Office job runs in a child process with its own instance from
`DispatchEx` (never `GetObject`, never the user's window). The child writes the pid of the
instance it started; on a hang the parent kills exactly that pid and retries once
(`WERK_OFFICE_TIMEOUT`, default 420 s). Word and Excel are asked to `Quit` and killed only if
their process stays; PowerPoint (whose `Close` / `Quit` hang) is killed right after its file is
written, and PowerPoint work is refused when a PowerPoint is already running (it is
single-instance, so `DispatchEx` would attach to it). Word opens a document only after creating
and closing an empty one in the same instance: on the gate machine a first-action
`Documents.Open` blocked in 4 of 5 tries (see GATE-RESULTS.md).

## Gate

    py -3.12 gate/gate.py --libs <libs> --repo <repo> [--reuse-inputs]

Writes three test documents with Word, Excel and PowerPoint (`gate/make_inputs.py`), exports
them, verifies every package with every release reader (`gate/readers.py`) and with jsonschema,
runs the profile reader the package itself carries, checks the original is byte-identical and the
PDF is a PDF, imports both ways, reopens every result in Office and compares text / cells /
slides, and rebuilds the three ArtCraft samples. Results: `GATE-RESULTS.md`, raw `_gate_out/`.

## Limits (what werk-office 0.1.0 does not map; all of it stays in the carried original)

* Word: styles (beyond direct run formatting), lists / numbering, headers, footers, footnotes,
  comments, tracked changes, pictures, fields, section setup, fonts. One body run node.
* Excel: cell formats, column widths, merges, charts, pictures, defined names, **cached formula
  results** (no `core.sheet.computed` node), shared-formula followers (kept as their cached value
  and counted in the export notes).
* PowerPoint: masters, layouts, themes, pictures, tables, charts, notes, transitions,
  animations; a placeholder whose box comes from its layout gets a default box (said in the
  slide's work note).
* Rebuild (`--rebuild`, and every ArtCraft capsule) restores text, run formatting and tables
  (Word), values and formulas (Excel), text boxes at their positions (PowerPoint) -- not layout
  fidelity.
* Office writes its own state while it runs, under the user profile (Normal.dotm, MRU lists,
  crash-resiliency records after a killed instance). werk-office asks Word not to add to recent
  files (`AddToRecentFiles=False`; Excel's `Workbooks.Open` default is no MRU entry); PowerPoint's
  `Presentations.Open` has no such switch. werk-office changes no Office setting or registry key.
* Windows + Office 2016 only; no macOS Office, no LibreOffice.
