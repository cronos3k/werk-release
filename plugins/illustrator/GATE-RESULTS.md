# Illustrator 2020 scripts - gate results

Run 2026-11-07 on <lab-workstation> (Windows 10 19045), from `<plugins>\illustrator`.

| | |
|---|---|
| host | Adobe Illustrator 2020 **24.0.2**, ExtendScript **4.5.6**, `C:\Program Files\Adobe\Adobe Illustrator 2020\Support Files\Contents\Windows\Illustrator.exe` |
| how it ran | COM `Illustrator.Application.24` `.DoJavaScript` (`tools/adobe_com.py`). Illustrator was not running; the gate started a FRESH instance for every task (86-89 s each), and after each task called `Quit()` and ended the instance it had started (Illustrator 2020 stays alive after `Quit()`, as `_recon/HOSTS.md` says). A watchdog kills our own instance on a crash-dump child or 900 s without progress, and the task is run once more in a fresh instance; in the final run it fired once (below). Nothing was installed into Illustrator's Scripts folders. |
| library gated | **final** `werk.jsx` sha256 `b38b19905266d152591f049e69725c1866095b515866a62790c30594d483dfa9` (byte-identical copy of `stage/libs/js/dist/werk.jsx`), lib 0.1.0, bundle `source_rev` **26e3e14** (release-fixes; `bundle/bundle.json` sha256 `9088d1bca0a7c4e6…`). The plug-in's own `werk_inflate.jsx` was dropped: this build's `werk.inflateRaw` is linear and is what the plug-in uses (the gate checks it against zlib on 60 streams in Node). |
| release repo | `<repo>`, branch **release-fixes @ 26e3e14** (clean; fixtures verified with `python tools/fetch_fixtures.py --from-dir ../assets-fixes --check`); fixtures pinned by its `fixtures/fixtures.json`, release loaders of that commit |
| readers on every export | `python -m werk verify --json`, `werkc verify --json` (JSON Schema; for vector-art/1 the package's own manifest schema), `loaders/werk_read.py`, `werk_read.c` (gcc 15.2.0), `werk_read.rs` (rustc) - `tools/release_verify.py` |
| vector-art/1 samples | `<artcraft-samples>\vectorcraft\neon-drive.werk` (also the export template) and `every-field-signed.werk`, read-only; not release fixtures |

## Result - 35 PASS, 0 FAIL, 0 SKIP, 9 NOTE (895 s), final library (bundle 26e3e14)

```
py -3.12 gate.py        # log: _logs/run8-final-26e3e14.txt, measurements: _logs/run8-final-26e3e14-gate.json
```

The ninth NOTE: **Illustrator crashed on the first attempt of `img-image-cc0-v1`** (crash-dump
child pid 62944; the watchdog ended our instance; COM returned `RPC failed`); the retry in a fresh
instance passed. The same gate gave 35 / 0 / 0 / 8 with library d5eec059 / fa32df8 (`run6`, no
crash) and 35 / 0 / 0 / 9 with 17c9127e / a432b71 (`run7`, one crash on img-image-cc0-v1-damaged);
the numbers below differ between those runs only in export sizes and fixture pins.

| clause | result |
|---|---|
| werk.jsx vendored byte-identical | PASS |
| werk.jsx `inflateRaw` vs zlib (Node, 60 streams) | PASS |
| 3 image/1 fixtures pinned | 3 PASS (10 881 124 / 5 803 605 / 5 804 654 B) |
| host runs (5 tasks, each in its own instance; document count 0 -> 0) | 5 PASS (112 / 120 / 148 / 136 / 137 s); 1 NOTE: the first attempt of img-image-cc0-v1 crashed Illustrator, the retry passed |
| **neon-drive** open: geometry Illustrator holds vs the package's payload - kinds in paint order, every anchor and both handles, text | PASS: 83 items, 78 paths, 434 anchors, max deviation 5e-07 pt (the dump's 6-decimal rounding), text 3/3 |
| neon-drive: picture vs VectorCraft's own preview | NOTE: mean 6.4/255 (glow effects not applied, Source Sans 3 not installed so substituted) |
| neon-drive: export vector-art/1 verified | PASS: 2 904 662 B, lib exit 0, werkc exit 0 + schema, py/c/rs 126/126 |
| neon-drive: re-open of the export == first open | PASS: 83 items, 434 anchors, deviation 0 pt, text 3/3; picture max 1/255 |
| neon-drive: export image/1 verified; payload == the artboard PNG; re-open picture | 3 PASS (identical) |
| **every-field-signed** open geometry | PASS: 65 items, 36 paths, 158 anchors, max deviation 4.9e-07 pt, text 6/6. 1 path has coordinates of 1e21 / 1.8e308 on purpose (the corpus' number test): Illustrator cannot hold it, so it is not compared (reported). Not built (named in the report): 1 placed document, 3 blends, 3 envelopes, 1 mesh, 3 repeats, 2 symbol instances; 13 live effects, pattern paints |
| every-field: export vector-art/1 verified | PASS: 2 769 127 B, werkc exit 0 + schema, py/c/rs 143/143 (the out-of-range numbers were written as binary64 and counted: `number-out-of-range` 7) |
| every-field: re-open == first open | PASS: 65 items, 158 anchors, 0 pt, text 6/6 |
| every-field: re-open picture | NOTE: mean 0.38/255, max 109 - the 14 rasters are re-exported as their pixels rendered at 72 ppi and placed again |
| every-field: export image/1 verified; payload == artboard PNG | 2 PASS; re-open picture NOTE (mean 0.002, max 136 on a few edge pixels) |
| image/1 x 3: open - artboard size == the primary's pixel size | 3 PASS (1792x2400, 2048x2048 x 2) |
| image/1 x 3: artboard pixels vs the primary decoded by Pillow | ista-varun (PNG) PASS identical; JPEG x 2 NOTE (max 19, mean 0.51: Illustrator's JPEG decoder) |
| image/1 x 3: export verified (70/70 each; 6 808 279 / 7 592 290 / 7 592 290 B), payload == artboard PNG, re-open identical | 9 PASS |

The damaged fixture opened with verdict exit 1 (the image still opens, law 3).

## Earlier runs (in `_logs/`), and the Illustrator crashes

* run1 (`run1-full.txt`, older code + werk.jsx `ae8508a8…`): 29 PASS, 1 FAIL - every-field
  failed on a number past 2^53 in the dump (fixed: such numbers are written as binary64).
* run2 (`run2-every-field.txt`): every-field alone, 11 PASS, 0 FAIL, after the fixes
  (sublayer stacking order read through `absoluteZOrderPosition`; area-type frames).
* run3-run5 (`run3-hung*`, `run4-hung*`, `run5-hung*`): **Illustrator 2020 stopped answering
  inside a script call three times** (once during a re-open of an exported package, once
  during a re-open of an image/1 export, once at the start of every-field). Twice it had
  spawned a child `Illustrator.exe` (a crash-dump process: no handles, access denied, cannot be
  ended; pids 152732 and 16856 were still listed at the end), once it sat idle with no visible
  window. The same steps pass in other runs; no cause was found without screen access. The gate
  was changed to start a fresh Illustrator per task with a watchdog and one retry.
* run6 (`run6-final.txt`): 35 PASS, 0 FAIL, 8 NOTE, library d5eec059 / fa32df8, no crash.
* run7 (`run7-final-a432b71.txt`): 35 / 0 / 0 / 9, one crash caught and retried.
* run8 (`run8-final-26e3e14.txt`): the result above (final library); one crash caught and retried.

## Not run

* Interactive use: no dialog of Illustrator was clicked; the File > Scripts route was not used.
* The 20 000-path sample (`--big`): not run (an estimate of tens of minutes of ExtendScript was not measured).
* Any Illustrator other than 24.0.2; directory-form packages; signed exports.
* vector-art/1 symbols, patterns, blends, envelopes, meshes, repeats, placed documents, live effects (not implemented, see README).
