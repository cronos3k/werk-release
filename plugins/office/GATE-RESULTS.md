# werk-office -- gate results

## Re-gate on the re-vendored release library (W10, 2026-11-17)

**60 PASS, 0 FAIL, 0 NOT-RUN** (318 s), the same clause set and counts as the W5c run below:
A 4, B 3, C 29, D 6, E 6, F 6, G 6. Hosts as below (Word / Excel / PowerPoint 2016, `16.0`,
private `DispatchEx` instances; the instances the gate started and could not quit were ended
by pid, as before; a Word process already running on the desktop was not touched).

| | |
|---|---|
| repository | `<repo-archive>` = `git archive c5276a1` (release commit content) + the release assets via `tools/fetch_fixtures.py --from-dir <release-assets>` |
| library gated | `libs/` of that archive, bundle `source_rev` `509ebf83be6dd998a255cceca234ceca0b8ac025`; vendored `vendor/werk_single.py` sha256 **`ff3de49babadffa942469a8d6103cac0ecd13804b847b75cabe70acb3a680600`**; werkc built from the archive into `libs/_target` |
| ArtCraft samples | `<artcraft-samples>` (read-only), part G |

Command: `PYTHONIOENCODING=utf-8 py -3.12 gate/gate.py --libs <repo-archive>/libs --repo <repo-archive> --samples <artcraft-samples>`.
A first attempt without `PYTHONIOENCODING=utf-8` stopped at clause E with a
`UnicodeEncodeError` from the Windows console encoding while printing a passing clause's
non-ASCII detail (no gate clause had failed); set the variable when running the gate from a
console that is not UTF-8.

---

## (W5c, 2026-11-07/08, final re-vendor to release-fixes 26e3e14)

Final run: **60 PASS, 0 FAIL, 0 NOT-RUN** (1163 s), release-fixes library and loaders. The
attempt just before it (same code) was 59 PASS / 1 FAIL: reopening the rebuilt `sales.xlsx` hung
in Excel twice (420 s each; both instances killed by pid) while a UE plug-in build and gate ran
beside it; the same reopen run alone afterwards took 12 s, and the clean full re-run passed
(`_gate_out/gate-run-attempt1.txt`, `gate-attempt1.json`). Raw output `_gate_out/gate-run.txt`,
per-clause JSON `_gate_out/gate.json`, inputs `_gate_out/inputs/` (+ `inputs.json`), packages
`_gate_out/packages/`, Office files written back `_gate_out/imported/`.

| | |
|---|---|
| hosts | Microsoft Word 2016 16.0.4393.1000, Excel 2016 16.0.4393.1000, PowerPoint 2016 16.0.4266.1001 (file versions; COM reports `16.0`), each a private `DispatchEx` instance |
| tool | werk-office 0.1.0 (`werk_office.py`), Python 3.12.12, pywin32 |
| library gated | `stage\libs` lib_version **0.1.0**, bundle `source_rev` **26e3e143b2e7dd2787df411967486157097a0a67** (bundle.json sha256 `9088d1bc…`); vendored `vendor/werk_single.py` sha256 **`082420506e949d100ba05daf40d513e0dd9689507dc7e1653c1e18d4db62864e`**; werkc `stage\libs\_target\release\werkc.exe` |
| readers | as in `gate/readers.py`: `python -m werk`, vendored `werk_single.py`, `node js/bin/werk.js` (v22.14.0), `werkc verify --json` (JSON Schema), `loaders/werk_read.py` / `.c` (MSYS2 gcc) / `.rs` (rustc) from branch `release-fixes` @ 26e3e14 (`git archive` into `<repo-archive>`; stage\werk's checkout untouched), `--verify --strict`; python `jsonschema` 4.26.0; the profile reader each package carries in `spec/examples/` |
| profile definitions | copied by `tools/vendor_profiles.py` from wordcraft `report.werk`, gridcraft `sales.werk`, deckcraft `sample-deck.werk` and `<artcraft-formats>` (zlib-deflate, zip, opc, pdf); `profiles/VENDORED.json` |

Command: `py -3.12 gate/gate.py --libs <libs> --repo <repo-archive>`

## Clause counts

| part | what | PASS | FAIL |
|---|---|---|---|
| A | test documents written by Word / Excel / PowerPoint (`make_inputs.py`) + their hashes | 4 | 0 |
| B | `export` of test.docx / .xlsx / .pptx (PDF by the host) | 3 | 0 |
| C | per package: 7 release readers (all exit 0; werkc `schema_validated true`), jsonschema over manifest + JSON payloads + inflated blocks (9 / 10 / 10 documents, 0 errors), the package's own profile reader (exit 0), expected text present (docx 7/7 strings, pptx 5/5) | 29 | 0 |
| D | original carried byte for byte (12 098 / 9 154 / 32 416 bytes, sha256 equal to the input); PDF starts `%PDF-1.5` (docx, xlsx, pptx) | 6 | 0 |
| E | `import` (original route): output sha256 equal to the input; reopened in Office | 6 | 0 |
| F | `import --rebuild` from the structured nodes; reopened in Office; docx: all 7 strings, 1 table, 2 pages; xlsx: sheets `Prices`, `Notes`, 7 cells incl. `=SUM(B2:B4)` = 8.5, `=B2*2` = 9, TRUE, `#DIV/0!`, A5000 (second band), non-ASCII text; pptx: 2 slides 960 x 540, all 5 strings | 6 | 0 |
| G | `import` of ArtCraft `wordcraft/report.werk`, `gridcraft/sales.werk`, `deckcraft/sample-deck.werk` (no original inside -> rebuilt) and reopened in Office | 6 | 0 |

Package census (werkc): test-docx.werk 16 nodes (10 alive, 6 skipped = types werkc does not
interpret, 0 dead), 128 files; test-xlsx.werk 17 nodes, 128 files; test-pptx.werk 17 nodes,
112 files. sales.werk rebuilt with **7 formulas Excel refused** (structured references to the
table `Sales`, which werk-office does not rebuild) written as text and listed in the output.

## Findings along the way

* **Word 2016 `Documents.Open` hangs as the first operation of a fresh automation instance**
  on this machine (Dragon, Acrobat PDFMaker and 3Dconnexion COM add-ins load into every
  instance): 4 of 5 such attempts blocked (killed after 150-600 s; no dialog window found in the
  process by window enumeration), 2 of 2 attempts that first created and closed an empty
  document returned at once, and in the last three full gate runs every Word job (export, 2
  reopens, rebuild, sample rebuild + reopen) completed with the warm-up and no retry. Kept: warm-up +
  per-job child process + kill-own-pid + one retry.
* **PowerPoint**: as recon said, `Close` / `Quit` hang; also the release of a presentation
  reference blocked the worker after `SaveAs`. The job now reports its result first and the
  instance is killed by pid.
* **Excel cell `.Text` is locale-formatted** (`8,5` on this machine); the gate compares `Value2`.

## Library / profile issues to report (stage/libs untouched)

1. **Release loader capabilities vs. the Office profile schemas.** The release loaders' meta
   lists `summarize-points` and `summarize-gsplat`; the `loaderMeta` enum in
   `manifest.rich-document` / `manifest.spreadsheet` / `manifest.presentation` (written before
   them) does not, so werkc kills `loader-python` as schema-invalid. werk-office declares the
   intersection (an under-claim). Fix belongs in the profile schemas (or the bundle's meta per profile).
2. ~~PackageWriter gaps (`conventions_map`, a second readme file)~~ -- **resolved** in the final
   library: werk-office now uses `conventions_map=` and `add_readme_file` (its subclass no longer
   touches the writer's node table for these). `add_readme_file` takes no `role`, so
   HOW-TO-READ.md is listed without the `how-to-read` role CRAFT-BASE §1 shows; the profile
   schemas do not require it. Item 1 is still the one hand edit (loader `meta`).
3. **spreadsheet/1 has no core node type for the original package**, so the original `.xlsx` is
   an `x.werk-office.source` extension node (rich-document uses `core.package.binary` / `opc`,
   presentation `core.media.asset` / `zip`). No profile has a core type for a PDF rendition
   except presentation's asset; docx / xlsx PDFs are `x.werk-office.rendition`.

## Not run / not done

* VBA / ribbon add-in: not built (the CLI is the deliverable; see README).
* Structured mapping beyond the README's list (styles, lists, headers, pictures, cell formats,
  cached formula results / `core.sheet.computed`, masters, notes, ...). No previews
  (`core.preview.page`, `core.sheet.preview`, `core.slide.preview`).
* `.docm` / `.xlsm` / `.pptm`, legacy `.doc` / `.xls` / `.ppt`, password-protected files.
* Signing (`werk sign` can sign a package afterwards; not exercised here).
* Directory-form packages; packages larger than a few MB.
* A visible-UI check of the files reopened in Office (all reopen checks are COM reads).
* Note: the Office user name configured on this machine ("Second Reviewer") is written by
  Office into the test documents' `lastModifiedBy` and so into `core.text.properties`.
