# Photoshop 2020 / 2024 scripts - gate results

**Status in one paragraph.** FINAL: run F, Photoshop 2020 21.0.3, final library (werk.jsx `b38b1990…`, bundle 26e3e14, release-fixes fixtures): **35 PASS, 0 FAIL, 0 SKIP, 5 NOTE (1843 s)**, 2026-11-08, in the user's own Photoshop 2020 (saved once, so no first-save dialog); log `_logs/runF-final-b38b1990.txt`, JSON `_logs/runF-final-b38b1990-gate.json`. Photoshop 2024 (25.11): in-host self-test PASS only, no complete run - a Photoshop started by the gate opens a "Save As" dialog on its first save that no unattended run can answer. Earlier history follows.

Run 2026-11-07 on <lab-workstation> (Windows 10 19045), from `<plugins>\photoshop`.

| | |
|---|---|
| host | Adobe Photoshop 2020 **21.0.3**, ExtendScript **4.5.11**, `C:\Program Files\Adobe\Adobe Photoshop 2020\Photoshop.exe` |
| how it ran | COM `Photoshop.Application.140` `.DoJavaScript` (`tools/adobe_com.py`). Photoshop 2020 was **already running with the user's own documents** (pid 34312, not started by this work; 1 document in the morning, 2 in the evening - the user opened one meanwhile). The gate ATTACHED, created and closed only documents of its own, checked the document count before and after every call (unchanged every time: 1 -> 1, later 2 -> 2), re-activated the document that had been active, and never quit Photoshop. The scripts were run from this folder; nothing was copied into `Presets\Scripts`. Ruler / type units and dialog mode are set for each call and restored. |
| library gated | `werk.jsx` sha256 `17c9127e101d7ff771c6cae35e4a948944d3a6f0c70e5075c6082fe01c59f46e` (byte-identical copy of `stage/libs/js/dist/werk.jsx` as rebuilt 19:25), lib 0.1.0, bundle `source_rev` **a432b71** (`bundle/bundle.json` sha256 `83ed91b9f986caf8…`); `tools/werk_single.py` = `stage/libs/python/werk_single.py` (sha256 `4d51216e…`) |
| release repo | `<repo>` @ **4ba7792** (19:57); fixtures pinned by its `fixtures/fixtures.json` (the image fixtures were rebuilt by another workstream twice during this work) |
| readers on every export | `python -m werk verify --json` (stage/libs/python), `werkc verify --json` (stage/libs/_target/release/werkc.exe, JSON Schema validated; for raster-layers/1 the package's own manifest schema), `loaders/werk_read.py --verify`, `werk_read.c` (gcc 15.2.0, -std=c99 -O2), `werk_read.rs` (rustc -O) - `tools/release_verify.py` |
| raster-layers/1 capsules | not in the release repo; used read-only: `<artcraft-samples>\photocraft\simple.werk` (also the export template) and `maximal.werk` |

## Final library (bundle 26e3e14, werk.jsx `b38b1990…`) - not complete

Library and fixtures: `werk.jsx` sha256 `b38b19905266d152591f049e69725c1866095b515866a62790c30594d483dfa9`,
`tools/werk_single.py` from the same build; `stage\werk` on branch release-fixes @ 26e3e14 (clean;
`python tools/fetch_fixtures.py --from-dir ../assets-fixes --check`: all present and verified). The
plug-in's own `werk_inflate.jsx` is gone: this build's `werk.inflateRaw` is linear and is what
`werk_raster.jsx` now uses.

| run | host | result |
|---|---|---|
| `_logs/ps2020-fresh-instance.txt` | Photoshop 2020 21.0.3, started by the gate as a normal application (no 2020 / 2024 was running; the user's instance was closed) | 9 PASS, 1 FAIL: library vendored, `werk.jsx inflateRaw` vs zlib (60 streams), werk_raster vs GIMP decoder (106 surfaces), 3 fixtures pinned, in-host self-test (profile test vector `9666edb4…` and the 7.2 checkpoint `b8770665…` / `08000f03…`) PASS; `img-ista-varun-v1` FAIL: Photoshop opened its "Save As" dialog on the first save (the watchdog saw it, ended our instance) |
| `_logs/ps2024-fresh-instance.txt`, `_logs/ps2024-gui-selftest.json` | Photoshop 2024 25.11.0 (ExtendScript 4.5.12), started by the gate as a normal application | self-test PASS (same vector and checkpoint); then the COM call did not return and the run was ended by hand |
| `_logs/ps2024-selftest-result.json` | Photoshop 2024 started through COM (`/Automation -Embedding`) | self-test PASS |

What was learned in Photoshop 2024 (25.11), all under COM automation, all on this machine:
* COM `Photoshop.Application.180` starts 2024 when 2020 is closed (8-58 s); twice the first start
  answered `Server execution failed` and the retry started it. The coordinator's pid 40024 was an
  instance this work had started, not the user's Photoshop 2020.
* An instance COM starts itself (no window) refused saves ("User cancelled the operation") and
  stopped answering at document close or after a call returned; one image task did complete all its
  in-host steps once (open, Photoshop's own open of the primary, export through the Save for Web
  fallback, re-open), but the run never finished, so no numbers are claimed.
* The window titles of the instance the gate started showed Photoshop's "Save As" dialog
  (`Save to cloud documents`, `As a Copy`, folder `<a user folder>`) waiting during a `saveAs` with
  `DialogModes.NO` - in 2020 and 2024 alike.

Code changes made for this (not yet covered by a complete run; harmless in the user's instance by
construction): a failed PNG `saveAs` falls back to an Action Manager "save a copy" (PNG method set)
and then to Save for Web PNG-24; the Raw save of a layer is retried; an opened primary keeps its file
until the document is closed; scratch file names are plain; `gate_ps.jsx` sets `DialogModes.NO`
while it runs and restores it; `tools/adobe_com.py` starts Photoshop as a normal application, ends
it after a bounded `Quit()`, and its watchdog ends our own instance on a "Save As" window, a crash
child or no progress.

## Photoshop 2024 UXP plug-in

`contrib/experimental/photoshop-uxp/` (repository root; was `contrib/experimental/uxp/` in this folder) - manifest v5, `werk.js` (sha256 `563b89c2…`), Open / Export image/1
commands and a gate (`gate_uxp.py`, UPIA side-load + self-test hook). **Not loaded, not run**:
nothing was installed (UnifiedPluginInstallerAgent `/list all` showed 0 extensions for Photoshop
2024 before and nothing was added), because Photoshop 2024 could not be driven reliably here.

## Run E - last complete run: 35 PASS, 0 FAIL, 0 SKIP, 5 NOTE (2757 s), library a432b71

```
py -3.12 gate.py        # log: _logs/runE-final-a432b71.txt, measurements: _logs/runE-final-a432b71-gate.json
```

| clause | result |
|---|---|
| werk.jsx and tools/werk_single.py byte-identical to the release libraries | 2 PASS |
| werk_inflate.jsx vs zlib (Node; 60 streams: levels 0/1/6/9, fixed / Huffman-only / dynamic, 0 B - 400 KB) | PASS |
| werk_raster.jsx decoder vs the GIMP plug-in's Python decoder (Node), every surface of simple + maximal | PASS, 106 u8/u16 surfaces byte-identical (the 9 f32 surfaces are converted to u16 by design, not compared) |
| 3 image/1 fixtures pinned | 3 PASS (10 881 124 / 5 803 605 / 5 804 654 B) |
| host runs: selftest / ista-varun / image-cc0 / image-cc0-damaged / simple / maximal | 6 PASS (10 / 212 / 178 / 177 / 290 / 1836 s) |
| inside Photoshop: profile test vector `tiles.example.wkxz` decoded (sha256 `9666edb4…`) and the PROFILE-RASTER-LAYERS 7.2 writer checkpoint (tiles 262 432 B `b8770665…`, index 400 B `08000f03…`) | PASS |
| image/1 x 3: open through werk == Photoshop opening the primary file the release library extracts | 3 PASS, identical |
| image/1: Photoshop's decode of the primary vs Pillow | ista-varun (PNG) PASS identical; image-cc0 and -damaged (JPEG) 2 NOTE: max 18/255, mean <= 0.69 (two JPEG decoders) |
| image/1 x 3: export verified - lib exit 0, werkc exit 0 + schema, py/c/rs 70/70 | 3 PASS (6 379 113 / 6 378 848 / 6 378 848 B) |
| image/1 x 3: exported pixels == the opened document; re-open == export | 6 PASS, identical |
| raster-layers **simple**: open - each of the 3 layers read back from Photoshop (u8 RGBA, straight alpha) vs its surface decoded by the reference decoder | PASS, 3/3 identical, names 3/3 |
| simple: export raster-layers/1 verified | PASS, 6 518 461 B, werkc exit 0 + schema, py/c/rs 137/137 |
| simple: export image/1 verified | PASS, 1 343 451 B, 70/70 |
| simple: re-open raster-layers/1 == first open; re-open image/1 == composite | 2 PASS (3/3 layers' RGBA identical, names equal; composite identical) |
| raster-layers **maximal**: open - every layer read back vs its surface | PASS: 137 leaf layers, 10 groups, names 137/137; of the 59 layers with decodable pixels 55 identical and 4 within 1/255 (16-bit / float surfaces: Photoshop's 16-bit is 0..32768, float clamped), 0 differ; 78 open empty and are reported (41 fill + 24 adjustment layers not rendered, 7 without pixels, 3 cmyk + 3 lab surfaces not decoded) |
| maximal: raster-layers/1 export | NOTE: not run by design (see below) |
| maximal: export image/1 verified; re-open == composite | 2 PASS (1 341 852 B, identical) |

The damaged fixture (`image-cc0-v1-damaged`) opened with verdict exit 1 (a damaged node): the
image still opens (law 3). `maximal.werk` is signed and verified `signed-and-valid`.

## Earlier runs (in `_logs/`)

* runA (`runA-all.txt`, werk.jsx `ae8508a8…`, bundle fa32df8, old fixtures): 31 PASS, 1 FAIL - maximal
  failed: its JSON holds U+2028 inside strings, which ExtendScript's eval refuses ("Unterminated
  string constant"). Fixed in all three plug-ins (U+2028 / U+2029 escaped before eval).
* runB (`runB-fail.txt`): maximal failed on a fully transparent layer - Photoshop cannot make a
  mask from an empty selection; such a layer is now created empty.
* runC (`runC-maximal-oldlib.txt`): maximal alone, PASS (open 59/59 layers as above); its first two
  rows FAIL because the release library had been rebuilt during the run (werk.jsx `d5eec059…`).
* runD (`runD-final.txt`, werk.jsx `d5eec059…`, bundle fa32df8, repo 550c885): 35 PASS, 0 FAIL, 5 NOTE.
* runE: the result above, after the library was rebuilt once more (bundle a432b71).

## Not run

* raster-layers/1 EXPORT of maximal.werk (137 layers): ExtendScript hashes and CRCs ~1.2 MB of
  tiles per layer at roughly 0.1-0.2 MB/s, i.e. hours; `py -3.12 gate.py --maximal-export` runs it.
* The two scripts' dialogs (`Open werk.jsx`, `Export werk.jsx`: File.openDialog / saveDialog /
  confirm / alert) were not clicked; the gate calls the same functions without UI.
* A complete Photoshop 2024 run and a complete run with the final library (see the top).
* Directory-form packages; signed exports (not implemented); 16-bit image/1 export; CMYK / Lab
  layer pixels (not decoded); masks / effects / adjustment layers (not applied).

## What this work did to the user's Photoshop

* All gate calls ran inside the user's running Photoshop 2020 and blocked its UI while they ran
  (runA 25 min, runD 50 min, runE 46 min, the maximal runs 30-35 min each).
* An early experiment (`exp1.jsx`: the library's own `werk.inflateRaw` on a 1.5 MB tile stream)
  kept that Photoshop busy for about 80 minutes (12:20-13:40); a synthetic Escape key press did not
  interrupt it. That is how the ExtendScript array slowdown was found.
* No user document was modified, saved, closed or left inactive; preferences touched (ruler units,
  type units, dialog mode) were restored after every call.
