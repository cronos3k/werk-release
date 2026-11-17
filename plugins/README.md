# werk host plug-ins

One folder per host. A plug-in is here only if its gate ran inside the real
host; each folder's `GATE-RESULTS.md` says what ran, on which version, and with
which library. Untested work is under `contrib/experimental/` at the
repository root, never here.

| folder | host, version gated | reads / writes | gate result (final run) |
|---|---|---|---|
| [blender/](blender/) | Blender 4.2.1 add-on 1.1.0 | 3d-entity/1, image/1 | 20 PASS / 0 FAIL (add-on gate) + 88 PASS / 0 FAIL (release gate) |
| [gimp/](gimp/) | GIMP 3.2.4 plug-in | image/1, raster-layers/1 | 34 PASS / 0 FAIL / 3 NOTE |
| [unreal/](unreal/) | Unreal Engine **5.8.2** (WerkLink 0.2); 5.7 untested | 3d-entity/1, textures of image/1 | 147 PASS / 0 FAIL / 4 NOT-RUN |
| [photoshop/](photoshop/) | Photoshop **2020 (21.0.3)**, ExtendScript; 2024 (25.11): self-test only, no complete gate run | image/1, raster-layers/1 | 35 PASS / 0 FAIL / 5 NOTE |
| [illustrator/](illustrator/) | Illustrator 2020, ExtendScript | vector-art/1, image/1 | 35 PASS / 0 FAIL / 9 NOTE |
| [aftereffects/](aftereffects/) | After Effects 2020, ExtendScript | image/1 import/export; motion-comp/1 import (partial) | 28 PASS / 0 FAIL / 4 NOTE |
| [office/](office/) | Microsoft Office 2016 via COM (`werk-office` CLI) | docx/xlsx/pptx to and from rich-document/1, spreadsheet/1, presentation/1 | 60 PASS / 0 FAIL |

All gates ran on Windows 10 against the release library (`libs/`:
`werk_single.py` `08242050…`, `werk.jsx` `b38b1990…`) and the release fixtures
of `release-fixes` @ `26e3e14`. Every plug-in vendors a byte-identical copy of
the library; the gates check that.

**Re-vendored after the gates (2026-11-17).** The bootstrap loader
`loaders/werk_read.py` changed after these runs (an unsafe `files[]` path now
kills its node instead of refusing the package at `--extract`; `--help`).
The libraries embed that loader, so every plug-in now vendors the rebuilt
library (`werk_single.py` `272e0bbe…`, `werk.jsx` `78011d6e…`, `werk.js`
`dd679b65…`, bundle at `bc23529`). Only the embedded loader bytes and the
bundle's record of them differ from what was gated; the plug-in code did
not change. Which gates were re-run on the re-vendored library is recorded
in `RELEASE-PINS.md`.

**What is not in the repository.** The gates' raw logs (`_logs/`) and their
outputs (`_gate_out/`) are not committed; the `GATE-RESULTS.md` files quote
their numbers and name the log files. Workspace paths in those files read
`<repo>`, `<libs>`, `<plugins>`, `<release-assets>`; the host machine reads
`<lab-workstation>`.

**ArtCraft samples.** The Photoshop, GIMP, Illustrator, After Effects and
Office gates also open ArtCraft sample capsules (raster-layers/1, vector-art/1,
motion-comp/1, office profiles). Those capsules are not part of this
repository; point `WERK_ARTCRAFT_SAMPLES` (or Office's `--samples`) at a
folder holding them. Without it, those tasks cannot run.

**Paths.** Each plug-in's `tools/werk_paths.py` finds the repository and
`libs/` from its own location (`<repo>/plugins/<host>/`); override with
`WERK_REPO` and `WERK_LIBS`.
