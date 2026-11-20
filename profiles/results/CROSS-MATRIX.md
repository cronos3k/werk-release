# werk libs cross-matrix

machine `<lab-workstation>` | Windows-10-10.0.19045-SP0 | python 3.12.8 | node v24.10.0 | started 2026-11-20T05:56:20Z

Writers: py, py1, js, es3, rust. Readers: py, js, es3, werkc, ref-py, ref-c, ref-rs.

## Writers x cases (byte identity) and readers x outputs (verdict + extraction)

| case | form | byte-identical (py/py1/js/es3/rust) | sha256 | full verdict (exit / signature / dead) | py | js | es3 | werkc | ref-py | ref-c | ref-rs |
|---|---|---|---|---|---|---|---|---|---|---|---|

A reader cell is `outputs read with an agreeing verdict and byte-exact extraction / outputs`.

## Fixtures (reader-only)

| fixture | agree | py verdict (exit / signature / dead) | py | js | es3 | werkc | ref-py | ref-c | ref-rs |
|---|---|---|---|---|---|---|---|---|---|
| motion-comp-v1.werk | yes | 0 / absent / none | 0/absent/0 | 0/absent/0 | 0/absent/0 | 0/absent/0 | 0/absent/0 | 0/absent/0 | 0/absent/0 |
| presentation-v1.werk | yes | 0 / absent / none | 0/absent/0 | 0/absent/0 | 0/absent/0 | 0/absent/0 | 0/absent/0 | 0/absent/0 | 0/absent/0 |
| raster-layers-v1.werk | yes | 0 / absent / none | 0/absent/0 | 0/absent/0 | 0/absent/0 | 0/absent/0 | 0/absent/0 | 0/absent/0 | 0/absent/0 |
| rich-document-v1.werk | yes | 0 / absent / none | 0/absent/0 | 0/absent/0 | 0/absent/0 | 0/absent/0 | 0/absent/0 | 0/absent/0 | 0/absent/0 |
| spreadsheet-v1.werk | yes | 0 / absent / none | 0/absent/0 | 0/absent/0 | 0/absent/0 | 0/absent/0 | 0/absent/0 | 0/absent/0 | 0/absent/0 |
| vector-art-v1.werk | yes | 0 / absent / none | 0/absent/0 | 0/absent/0 | 0/absent/0 | 0/absent/0 | 0/absent/0 | 0/absent/0 | 0/absent/0 |

Fixture cells: `exit/signature/dead-count` per reader; bootstrap loaders run with `--strict`.

## Failures: 0

