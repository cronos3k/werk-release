# After Effects 2020 scripts - gate results

Run 2026-11-07 on <lab-workstation> (Windows 10 19045), from `<plugins>\aftereffects`.

| | |
|---|---|
| host | Adobe After Effects 2020 **17.0.2 (x26)**, ExtendScript **4.5.6**, `C:\Program Files\Adobe\Adobe After Effects 2020\Support Files\AfterFX.exe` |
| how it ran | `AfterFX.exe -noui -r <plugins>\aftereffects\_gate_out\runner.jsx` (the runner sets `WERK_ARGS` and evaluates `gate_ae.jsx`). After Effects was not running before (the gate refuses to start otherwise); it was started by the gate, its project was closed without saving, and since `app.quit()` does not exit 17.0 in `-noui` mode the gate ended the process it had started (pid 88940) 30 s after the script's own `ALL DONE`. Nothing was installed into After Effects' Scripts folders. |
| library gated | **final** `werk.jsx` sha256 `b38b19905266d152591f049e69725c1866095b515866a62790c30594d483dfa9` (byte-identical copy of `stage/libs/js/dist/werk.jsx`), lib 0.1.0, bundle `source_rev` **26e3e14** (release-fixes; `bundle/bundle.json` sha256 `9088d1bca0a7c4e6…`) |
| release repo | `<repo>`, branch **release-fixes @ 26e3e14** (clean; its fixtures verified with `python tools/fetch_fixtures.py --from-dir ../assets-fixes --check`: all present and verified); the gate pins each fixture by the size + sha256 in `fixtures/fixtures.json` |
| readers on every export | `python -m werk verify --json`, `werkc verify --json` (JSON Schema), `loaders/werk_read.py`, `werk_read.c` (gcc 15.2.0), `werk_read.rs` (rustc) - `tools/release_verify.py` |
| motion-comp/1 sample | `<artcraft-samples>\effectcraft\intro.werk` (read-only; not a release fixture) |

## Result - 28 PASS, 0 FAIL, 0 SKIP, 4 NOTE (565 s), final library (bundle 26e3e14)

```
py -3.12 gate.py        # log: _logs/run5-final-26e3e14.txt, measurements: _logs/run5-final-26e3e14-gate.json
```

The same gate gave the same 28 / 0 / 0 / 4 with the two earlier library builds (`run3-final.txt`:
werk.jsx `d5eec059…` / bundle fa32df8; `run4-final-a432b71.txt`: `17c9127e…` / a432b71). Only the
export sizes and the fixture pins differ between them.

| clause | result |
|---|---|
| werk.jsx vendored byte-identical | PASS |
| 3 image/1 fixtures pinned | 3 PASS (10 881 124 / 5 803 605 / 5 804 654 B) |
| After Effects run | PASS (script ran to `ALL DONE`, 551 s; process ended by the gate) |
| image/1 x 3: imported footage - size, and the media file on disk is byte-identical (sha256) to the primary the release library extracts | 3 PASS (1792x2400 PNG; 2048x2048 JPEG x 2) |
| image/1 x 3: frame 0 of a comp holding the footage vs the primary decoded by Pillow | ista-varun (PNG) PASS identical; image-cc0 and -damaged (JPEG) NOTE: max 19/255, mean <= 0.91 (After Effects' JPEG decoder vs Pillow's) |
| image/1 x 3: frame exported as image/1, verified (lib exit 0, werkc exit 0 + schema, py/c/rs 70/70) | 3 PASS (7 408 200 / 8 185 529 / 8 185 529 B) |
| image/1 x 3: the exported PNG is byte-identical to the frame After Effects wrote | 3 PASS |
| image/1 x 3: re-imported export, its frame == the exported frame | 3 PASS, identical |
| synthetic comp (two solids): export verified + pixels (blue left, red right) | 2 PASS |
| motion-comp/1 (partial import) host run | PASS: 3 comps, 22 layers, 6 solids, 2 footage items, 2 folders, 25 keyframes on 12 animated properties, 4 shape layers created empty |
| motion: compositions - size, frame rate, duration, layer count | PASS, 3/3 |
| motion: layer order, names, in / out / start times | PASS; times to half a frame (After Effects puts every time on a frame: 4.004 s becomes 4.004004 s at 29.97 fps). 2 out points lie past the end of the layer's source (a 4.004 s nested comp ending at 9.5095 s, a 1 s WAV ending at 1.001 s); After Effects ends those layers with their source, which is what is expected and reported (`out-point-clamped`) |
| motion: transform values and keyframes | PASS: 154 transform properties, 142 static values, 25 keyframes (time + value), max difference 7.1e-15; 1 audio-only layer skipped (After Effects hides its transform) |
| motion: poster frame vs EffectCraft's own poster | NOTE: large difference, expected - shape contents, effects and text fonts are not built |

The damaged fixture imported with verdict exit 1 (law 3: the image still comes in).

## Runs before this one (kept in `_logs/`)

* run1 (`_logs/run1.txt`): 25 PASS, 3 FAIL - the motion checks compared times exactly
  (After Effects snaps them to frames), the frame rate to 1e-6 (After Effects stores
  29.97003173828125), and parenting was set AFTER the transforms (After Effects then
  re-expresses a child's transform; fixed: parents first, then transforms); the audio
  layer's transform is hidden in After Effects (now skipped and reported).
* run2 (`_logs/run2.txt`): 27 PASS, 1 FAIL - the audio test also skipped the camera
  (cameras have `hasVideo == false`); fixed (audio-only = footage with audio and no video).
* run3 (`_logs/run3-final.txt`): 28 PASS, 0 FAIL with library d5eec059 / fa32df8.
* run4 (`_logs/run4-final-a432b71.txt`): 28 PASS, 0 FAIL with library 17c9127e / a432b71.

## Not run

* motion-comp/1 EXPORT (not implemented), and the motion import's unbuilt parts listed in README.md.
* After Effects with its UI (only `-noui`); the scripts from File > Scripts menus.
* Any After Effects other than 17.0.2; directory-form packages; signed exports.
