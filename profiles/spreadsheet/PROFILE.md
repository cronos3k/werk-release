# `spreadsheet/1` — workbooks

Status: in the release as a profile carried in its packages (SPEC §2.2). Origin: GridCraft
(ArtCraft suite), `werk-native` branch; copied unchanged except for the alignment edit below.

## 1. Where the definition is, and how it travels

The normative definition is the set of files under [`spec/`](spec/), carried as files of a
package's `core.spec` node beside the release `spec/`:

| file in the package | role |
|---|---|
| `spec/PROFILE-SPREADSHEET.md` | the narrative (incl. §5.2 formula grammar, §5.3 dates); manifest `profile_spec` |
| `spec/schemas/manifest.spreadsheet.schema.json` | the manifest schema |
| `spec/conventions-map.spreadsheet.json` | manifest `conventions_map` |
| `spec/CRAFT-BASE.md`, `spec/NOT-CARRIED.md` | rules every ArtCraft profile shares |
| `spec/schemas/core.sheet.{workbook,sheet,cells,computed,styles,names,chart,pivot,external-values,vba-project}.schema.json` | payload schemas |
| `spec/layouts/core.sheet.cells.layout.txt`, `core.sheet.computed.layout.txt` | the band envelopes `WKX0` (cells) and `WKX1` (cached results) |
| `spec/schemas/x.gridcraft.*`, `spec/layouts/x.gridcraft.*` | GridCraft-only extensions |
| `spec/examples/spreadsheet/` | worked examples, `read_spreadsheet.py`, `write_minimal.py` |
| `spec/formats/zlib-deflate.md` (from [`../_formats/`](../_formats/)) | band compression, with its reference tool |

Format definitions named for pictures and VBA (`jpeg`, `cfb`, `ovba`, …) are not in this release.

## 2. Node kinds (summary; `spec/PROFILE-SPREADSHEET.md` §3 is normative)

| type | count | payload |
|---|---|---|
| `core.sheet.workbook` | exactly 1 (`primary.document`) | JSON: sheet order, date system, calculation settings |
| `core.sheet.styles`, `core.sheet.names` | 1 each | JSON |
| `core.sheet.sheet` | per sheet | JSON: layout, merges, panes, validations, … and node ids of its stores |
| `core.sheet.cells` | per sheet | JSON index + band files (zlib streams of `WKX0`): positions, constants, formula text, format index |
| `core.sheet.computed` | 0..1 per sheet | JSON index + bands (`WKX1`): cached formula results, `measured` over the sheets its formulas can read |
| `core.sheet.chart`, `core.sheet.pivot`, `core.sheet.image`, `core.sheet.picture`, `core.sheet.vba-project`, `core.sheet.preview`, `core.sheet.preview-rows`, `core.sheet.external-values` | 0..n | JSON / PNG / verbatim |

Formula text: grammar `excel-a1-en-us`, no leading `=`. Conventions: 34, pinned (§5).

## 3. What a reader outputs (normative for the release reference reader)

`read_spreadsheet.py PACKAGE` prints one JSON object (UTF-8, keys sorted, indent 1):
`profile`, `title`, `date_system`, `active_sheet`; `sheets` in tab order, each with node, uid,
name, `cells` keyed by A1 address — `value` (the constant, or the cached result of the formula
from the computed store: number, string, boolean, `{"error": …}`, `{"nonfinite": …}`,
`{"array": …}`, or null), `formula` (text or null), `style` (format index), `num_fmt`, and
`cached` / `spilled` where they apply — `cell_count`, `formula_count`, and
`computed_input_hash_ok` (the computed node's `input_hash` recomputed by MINI-SPECS §11 from the
files the package now holds: true, false, or null without a computed node); `notes`, `dead`,
`files_verified`, `file_failures`. It evaluates no formula. Not implemented: charts, pivots,
pictures, number-format rendering, revisions.

## 4. The release fixture

[`../fixtures/spreadsheet-v1.werk`](../fixtures/) — "Lighthouse costs": sheet "Costs" (work
items, a `B*C` formula per row, `SUM` totals) and sheet "Summary" (`Costs!D6`,
`MAX(Costs!D2:D5)`, VAT, gross, a share), cached results for both (the Summary cache lists both
sheets as inputs), money and percent number formats. Built by
[`build_spreadsheet.py`](build_spreadsheet.py) (it reuses the default payloads of the profile's
own `write_minimal.py`).
