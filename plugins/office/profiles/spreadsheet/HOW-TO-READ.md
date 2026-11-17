# How to read this spreadsheet

This file is a spreadsheet workbook saved as a werk capsule, profile `spreadsheet/1`. It is
either one `.werk` file — an ordinary store-mode zip — or the same tree as a directory. You
need no spreadsheet application to read it. Everything below uses only what is inside it.

## The quick way (Python 3.8+, standard library only)

Unzip the file (or use the directory as it is), then:

    python spec/examples/spreadsheet/read_spreadsheet.py <the .werk file or directory>
        lists the sheets: name, number of cells, formulas, charts, pictures

    python spec/examples/spreadsheet/read_spreadsheet.py <file> --csv "<sheet name>" out.csv
        writes one sheet as CSV: every value, formula cells as their last calculated result

    python spec/examples/spreadsheet/read_spreadsheet.py <file> --json out.json
        writes everything: every cell of every sheet with its value, formula text and format
        number, the defined names, charts, pivots, pictures

    python spec/examples/spreadsheet/read_spreadsheet.py <file> --revision 1 --json old.json
        the same for an earlier saved revision (every Save is kept in the file)

    python loaders/werk_read.py <file> --verify          re-hashes every byte against MANIFEST.json
    python loaders/werk_read.py <file> --list            every node, its type and its files

Two files need no program at all: `preview/preview.png` is a picture of the first sheet, and
`preview/first-rows.csv` is its first rows as plain CSV.

## By hand

1. `MANIFEST.json` is the only index. `primary.document` names the workbook node; its file is
   `workbook/workbook.json`: the sheets in tab order, as node ids.
2. Each sheet node (`sheet-<n>`) has a JSON file with the name and layout of the sheet, and
   names two more nodes: `cells` and, if the sheet has formulas, `computed`.
3. The cells node has a small JSON index (`sheets/sheet-<n>/cells.json`) and one file per
   BAND of rows (`sheets/sheet-<n>/cells/rows-0000000.wkx.zlib`, …). The index lists the
   bands, each with the rows it covers and the sha256 of its file. A band file is one zlib
   stream: inflate it (`zlib.decompress` in Python; `spec/formats/zlib-deflate.md` defines the
   format and `tools/format-zlib-deflate-reference/inflate.py` is an inflater in plain Python).
4. An inflated band is a small binary: flat little-endian arrays, one entry per cell — `row`,
   `col` (both zero-based: A1 is 0,0), `kind` (1 number, 2 text, 3 boolean, 4 error),
   `number`, `ref` (for text: an index into a string table), `style`, `formula` (an index into
   a table of formula texts). `spec/layouts/core.sheet.cells.layout.txt` defines every byte,
   and `spec/examples/spreadsheet/cells.example.hex.txt` walks through a real one.
5. The computed node has the same shape (an index and bands) and holds the last calculated
   result of each formula cell (`spec/layouts/core.sheet.computed.layout.txt`).
6. A date is a number of days: in date system `D1900` (see `date_system` in the workbook
   file), day 45000 is 2023-03-15. `spec/PROFILE-SPREADSHEET.md` section 5.3 has the rule.

## Where everything is defined

    spec/PROFILE-SPREADSHEET.md      what every node means; how to WRITE such a file (section 7)
    spec/schemas/core.sheet.*.json   every field of every JSON file, with units and ranges
    spec/layouts/                    the two binaries (an inflated band), byte by byte
    spec/formats/                    every foreign format this file uses, byte by byte: zlib (the
                                     cell bands); JPEG / GIF / BMP / TIFF / EMF / WMF pictures; the
                                     VBA project container - each only if this workbook has one
    tools/format-*-reference/        a reference reader for each of those, as Python source
    spec/CRAFT-BASE.md, spec/SPEC.md the container, versions, signatures

Nothing in this file refers to anything outside it. A hyperlink in a cell, or the recorded
location of another workbook, is content: it is never needed to read this one. If the file
carries a VBA macro project (`workbook/vbaProject.bin`), it is embedded code: read it as data
if you wish (`spec/formats/ovba.md`), do not run it.
