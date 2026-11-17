# GIMP plug-in — gate results

> **Re-gate on the re-vendored release library (W10, 2026-11-17):** **34 PASS, 0 FAIL, 0 SKIP, 3 NOTE** (107.5 s), GIMP 3.2.4, run from `<repo-archive>` = `git archive c5276a1` + release assets, `plug-ins/file-werk/werk_single.py` `ff3de49b…` (byte-identical to `libs/`, bundle `509ebf8`); raster-layers/1 capsules from `<artcraft-samples>` as below.

Run 2026-11-07 on <lab-workstation> (final re-run: library and fixtures at release-fixes 26e3e14) (Windows 10 19045), from `<plugins>\gimp`.

| | |
|---|---|
| host | GIMP 3.2.4, `C:\Program Files\GIMP 3\bin\gimp-console-3.exe` (bundled Python 3.14.4) |
| command (inside the gate) | `gimp-console-3.exe -i -n -d -f -c --batch-interpreter python-fu-eval -b "exec(open(r'<plugins>/gimp/gate_in_gimp.py').read())" --quit` |
| GIMP profile | `GIMP3_DIRECTORY=<plugins>\gimp\_gate_out\gimp-profile` (fresh each run), its `gimprc` = `(plug-in-path "${gimp_dir}/plug-ins;${gimp_plug_in_dir}/plug-ins;<plugins>/gimp/plug-ins")`. The plug-in was **not** copied anywhere; pluginrc shows it registered from `<plugins>\gimp\plug-ins\file-werk\file-werk.py`. Checked afterwards: nothing new under `%APPDATA%\GIMP` or `%LOCALAPPDATA%`. |
| release repo / libs | release-fixes @ `26e3e14`, the `git archive` copy at `<repo-archive>` (`WERK_REPO`), assets from `stage\assets-fixes`; `<libs>` (`WERK_LIBS`): `werk_single.py` lib 0.1.0, bundle source_rev `26e3e14`, sha256 `082420506e949d10…`, 663 120 B, bundle spec_sha256 `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3`; `werkc.exe` from `libs/_target/release` |
| loaders | `loaders/werk_read.py` (Python 3.12), `werk_read.c` (gcc 15.2.0 MSYS2, `-std=c99 -O2`), `werk_read.rs` (rustc `-O --edition 2021`), built into `_bin/` |
| image/1 fixtures | the three image/1 entries of `fixtures/fixtures.json` (ista-varun-v1, image-cc0-v1, image-cc0-v1-damaged) of release-fixes, pinned by size + sha256 (all match) |
| raster-layers/1 capsules | NOT in the release repo. Used read-only: `<artcraft-samples>\photocraft\simple.werk` (also the export template) and `…\maximal.werk` |

Command: `WERK_REPO=<repo-archive> WERK_LIBS=<libs> python gate.py --json _logs/gate.json`

## Result — 34 PASS, 0 FAIL, 0 SKIP, 3 NOTE

```
python gate.py --json _logs/gate.json
```

Exact output: `_logs/gate.log`; raw measurements `_logs/gate.json`; GIMP's
console: `_logs/gimp-console.txt`. 66.3 s total, GIMP part 62.8 s,
GIMP exit 0, "batch command executed successfully".

| clause | result |
|---|---|
| library bundle: lib 0.1.0, source_rev 26e3e14, spec_sha256 55882f4b… | PASS |
| release library vendored byte-identical (sha256 08242050…) | PASS |
| raster-layers decoder reproduces the profile's test vector (`spec/examples/raster-layers/tiles.example.wkxz`, zlib + planes-delta → samples sha256 `9666edb4…`) | PASS |
| raster-layers writer reproduces PROFILE-RASTER-LAYERS.md §7.2 (tiles-p0-p0.wkx 262 432 B `b8770665…`, surface.wkx 400 B `08000f03…`) | PASS |
| 3 image fixtures pinned | 3 PASS |
| GIMP located / plug-in registered from this folder / GIMP run | 3 PASS |
| image/1 × 3: open — pixels (merged visible, R'G'B'A u8 sha256) == the primary file extracted by the release library and opened by GIMP directly; 1792×2400 and 2048×2048 | 3 PASS |
| image/1 × 3: export verified — lib exit 0, werkc exit 0 + schema validated, loaders .py/.c/.rs 70/70 files each | 3 PASS |
| image/1 × 3: export spec_sha256 == the bundle's `55882f4b…` | 3 PASS |
| image/1 × 3: re-open — pixels identical | 3 PASS |
| raster-layers simple: open — 3 layers, names match, 3/3 surfaces byte-identical when read back from GIMP in their own format | PASS |
| raster-layers maximal: open — 147 GIMP layers (137 leaves = 137 in the tree, 10 groups), 59/59 decoded surfaces byte-identical (u8, u16, f32 incl. the non-finite one; gray read back via R), names equal except GIMP's uniqueness suffix on 7 (`Black & White`→`Black & White #1`, `Color Lookup`→`#1`, `Adjustment`→`#1`, `Levels`→`#1`/`#2`, `Curves`→`#1`/`#2`); opened at float precision | PASS |
| export raster-layers/1 verified (now written by `PackageWriter` + `add_spec_file`): simple 6 604 634 B (137/137 files), maximal 40 958 834 B (456/456 files) — lib exit 0, werkc exit 0 + schema validated (package's own schemas, 0 errors), loaders .py/.c/.rs all files | 2 PASS |
| NOTE × 2: raster-layers exports' spec_sha256 = `b74d1eedc21876e9…` — the bundle's spec/ plus 55 profile files (PROFILE-RASTER-LAYERS.md, its schemas, layouts, examples) added with add_spec_file, so by construction not the bundle value; the library verdict's `spec_sha256_ok` is true | NOTE |
| export image/1 (flattened) verified: simple 1 344 184 B, maximal 1 342 787 B, 70/70 each; spec_sha256 == `55882f4b…` | 4 PASS |
| re-open raster-layers/1: simple 3/3 layers' RGBA u8 identical, names identical, merged picture identical; maximal 137/137 layers identical, names identical | 2 PASS |
| re-open image/1 (flattened): pixels == the merged visible layers before export | 2 PASS |
| NOTE: maximal's merged picture after the raster-layers round trip differs — expected from the stated limits (10 groups flattened, float → u8); the merged-picture identity is asserted only for a group-free u8 document (simple) | NOTE |

What "pixels identical" means here: sha256 over GIMP's own buffer read as
R'G'B'A u8 (image/1) or in the surface's own babl format (raster-layers
open). For the image/1 open check, both sides are decoded by GIMP's own
PNG/JPEG loader — it shows the plug-in hands GIMP exactly the primary file,
not that GIMP's decoder is right.

## Not run

* The interactive UI: File > Open / Export As dialogs were not clicked; the
  `GimpUi.ProcedureDialog` branch of the export never ran (batch runs are
  NONINTERACTIVE). The GIMP GUI (`gimp-3.2.exe`) was not started.
* Any GIMP other than 3.2.4; Linux / macOS GIMP.
* Thumbnail procedure (none is registered).
* Directory-form (`*.werk/` folder) packages: GIMP passes files, the
  directory form was not tried (`maximal-dir.werk` was not used).
* raster-layers/1 capsules other than the two PhotoCraft samples; documents
  with cmyk / lab layers are read (layers left empty, reported) but their
  pixels are not checked; masks, adjustment / fill layers and effects are not
  rendered, so no claim is made about the merged picture of such documents
  matching PhotoCraft's composite.
* Signed exports (not implemented).

## raster-layers/1 writer on PackageWriter

`werk_raster.write_capsule` builds the package with the library's public API
only for the profile itself: `werk.PackageWriter("raster-layers/1", ...,
conventions=, manifest_schema=, profile_spec=, spec_files=, conventions_map=)`
and `add_readme_file("HOW-TO-READ.md", ...)`. `spec/` and `loaders/` are the
library's bundle (release-fixes); the 55 template spec files the bundle lacks
are added with `add_spec_file` (via `spec_files=`); where both have a path the
release bytes are kept. The earlier workarounds are gone: no `write_container`,
no `ptab` poke (now `conventions_map=`), no separate how-to-read node (now
`add_readme_file`).

One bridge remains, and it is a schema-revision conflict rather than a library
gap: the template's `manifest.raster-layers.schema.json` (PhotoCraft's older
profile revision) permits 10 loader capabilities, while the release
`werk_read.py` record declares also `summarize-points` and `summarize-gsplat`
(re-checked in the final bundle). Unbridged, werkc marks `loader-python` dead
(schema-invalid). The writer narrows the loader records to the capabilities
the carried schema can express — a true subset computed from the schema.
Real fix: a newer raster-layers/1 profile schema (W6 / ArtCraft).
