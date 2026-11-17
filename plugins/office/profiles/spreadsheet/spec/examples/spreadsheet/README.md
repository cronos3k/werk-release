# Examples for profile `spreadsheet/1`

Everything here is real output: the payload examples are cut from one small workbook by the
same code that saves a real one, and the test suite fails if they drift.

The example workbook — one sheet, `Prices` (uid 1), date system D1900:

           A        B             C            D
      1    Item     Price         Bought       =SEQUENCE(2)     (a dynamic array: spills into D2)
      2    Tea      4.5           2023-03-15   2                (C2 is the number 45000, format yyyy-mm-dd)
      3    Coffee   3             (empty, bold)
      4    Total    =SUM(B2:B3)
      5    TRUE     #N/A

| file | what it is |
|---|---|
| `workbook.example.json` | the `core.sheet.workbook` payload |
| `sheet.example.json` | the `core.sheet.sheet` payload of `Prices` (a comment, a hyperlink, a merge, a conditional format, one chart, one pivot) |
| `styles.example.json` | `core.sheet.styles`: three cell formats (default, a date format, bold), one named style, the theme |
| `names.example.json` | `core.sheet.names`: a workbook-wide name and a sheet-local one |
| `chart.example.json`, `pivot.example.json` | one `core.sheet.chart`, one `core.sheet.pivot` |
| `cells.example.json` | the `core.sheet.cells` payload: the index of the cells store (one band) |
| `cells.rows-0000000.example.wkx.zlib` | that band as it is stored: one zlib stream, 570 bytes |
| `cells.example.wkx` | the same band INFLATED (1744 bytes): the envelope holding the 14 stored cells |
| `cells.example.hex.txt` | the inflated band, every byte annotated, down to the decoded cells |
| `computed.example.json` | the `core.sheet.computed` payload: the index of the computed store |
| `computed.rows-0000000.example.wkx.zlib` | its one band as stored |
| `computed.example.wkx` | that band inflated: two formula results and one spilled value |
| `computed.example.hex.txt` | the inflated band annotated |
| `first-rows.example.csv` | the `core.sheet.preview-rows` payload |
| `preview.example.png` | the `core.sheet.preview` payload (640x360) |
| `external-values.example.json` | `core.sheet.external-values`: the cached cells of one external workbook |
| `ooxml-index.example.json` | the index of an `x.gridcraft.ooxml` node keeping one OOXML part |
| `vba.example.json` | the descriptor of a `core.sheet.vba-project` node (the project itself is a test vector of `spec/formats/ovba.md`) |
| `read_spreadsheet.py` | a complete reader, Python standard library only: `python read_spreadsheet.py <capsule>` |
| `write_minimal.py` | a complete writer of a minimal capsule, standard library only: `python write_minimal.py <existing capsule> <new.werk>` |

To check a reader you are writing: inflate `cells.rows-0000000.example.wkx.zlib` (the result
must be `cells.example.wkx`, byte for byte, and its sha256 the `inflated_sha256` in
`cells.example.json`), decode it and compare with the table at the end of
`cells.example.hex.txt`. To check a writer: produce the checkpoints of
`spec/PROFILE-SPREADSHEET.md` section 7.1 and compare sizes and hashes.
