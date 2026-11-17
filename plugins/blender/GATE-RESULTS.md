# Blender add-on — gate results

Run 2026-11-07 on <lab-workstation> (final re-run: library and fixtures at release-fixes 26e3e14) (Windows 10 19045), from `<plugins>\blender`.

| | |
|---|---|
| host | Blender 4.2.1 LTS (hash 396f546c9d82, built 2024-08-20), `C:\Program Files\Blender Foundation\Blender 4.2\blender.exe`, run as `blender -b --factory-startup --python <script> -- <payload>` |
| Blender user profile | redirected: `BLENDER_USER_{CONFIG,SCRIPTS,DATAFILES,EXTENSIONS}` = `_gate_out/blender-profile/*` (checked afterwards: nothing new under `%APPDATA%\Blender Foundation` or `%LOCALAPPDATA%`) |
| add-on | loaded from this folder (`sys.path`), and from the built zip (clause "install from zip"), version 1.1.0 |
| release repo | branch `release-fixes` @ `26e3e14` of `<repo>`, exported read-only with `git archive release-fixes` into `<repo-archive>` (stage\werk's checkout and branch untouched; `git status` clean after the runs); assets from `<release-assets>` via `python tools/fetch_fixtures.py --from-dir <release-assets>` (all present and verified); werk-core `werk.dll` for the binding built from that archive (`cargo build --release --lib`, target `plugins\blender\_target`) |
| release libs | `<libs>` — `werk_single.py` lib 0.1.0, bundle source_rev `26e3e14`, sha256 `082420506e949d10…`, 663 120 B, bundle spec_sha256 `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3`; `werkc.exe` from `libs/_target/release` |
| loaders | `loaders/werk_read.py` (Python 3.12), `werk_read.c` built with gcc 15.2.0 (MSYS2) `-std=c99 -O2`, `werk_read.rs` built with rustc `-O --edition 2021`, into `_bin/` |
| fixtures | the 16 entries of release-fixes' `fixtures/fixtures.json`, every one pinned by size + sha256 (all match; e.g. crate-v1 13 965 429 B `e13b8ba9…`, gsplat-v1 30 519 513 B `fbe7b32c…`, ista-varun-v1 10 881 124 B `9bacd802…`) |

Environment for every run: `WERK_REPO=<repo-archive>`, `WERK_LIBS=<libs>`, `WERK_DLL=<cargo-target>
elease\werk.dll` (Blender `test_gate.py` only).

## 1. The add-on's original gate — 20 PASS, 0 FAIL, 0 SKIP

```
python test_gate.py --keep --json _logs/test_gate.json
```

Exact output: `_logs/test_gate.log`. The 20 clauses of the stage repo's
`plugins/blender/test_gate.py`, unchanged except that paths are resolved by
`tools/werk_paths.py`, the vendor check now also covers
`vendor/werk_single.py` (66/66 byte-identical) and Blender's profile is
redirected. Highlights: zip 847 100 B, 78 entries; clean import 36 nodes / 272
verts / 408 tris; damaged import exactly 1 hash-mismatch + 1 dead node;
round trip 272 → 272 verts, uuid survived; export verified by werk-core
(8/8 alive, 0 errors) and `werk_read.py` (71/71 files); determinism 71
payload entries byte-identical; rig worst rest-head error 0 m, worst posed
rotation error 8.43e-08 rad; point cloud 281 498 points; textured round trip
sRGB / Non-Color preserved, metallic 0.25 → 0.25.

## 2. The release gate — 88 PASS, 0 FAIL, 0 SKIP, 0 NOTE

```
python gate_release.py --json _logs/gate_release.json
```

Exact output: `_logs/gate_release.log`; raw measurements:
`_logs/gate_release.json`. 41.7 s total.

| clause group | count | result |
|---|---:|---|
| release library vendored byte-identical (sha256 08242050…) | 1 | PASS |
| fixtures pinned (fixtures.json) | 16 | 16 PASS |
| Blender located / Blender run (16 fixtures, exit 0) | 2 | PASS |
| import (13 × 3d-entity/1, 3 × image/1) | 16 | 16 PASS — dead-node count and signature state equal the release library's verdict for every fixture (damaged twins: exactly 1 dead) |
| export verified by lib + werkc (schema-validated) + loaders .py/.c/.rs | 16 | 16 PASS — every reader exit 0, 0 failed file checks |
| writer = library (conventions / JSON spelling / zip layout), on the crate-v1 export | 3 | 3 PASS |
| round trip (re-import of the export) | 16 | 16 PASS |
| library bundle vs release repo spec/ + loaders/ | 1 | PASS — bundle source_rev 26e3e14, 0 files differ from release-fixes (history: 6bf77f3 had 7 differing files, reported as a NOTE in the first run) |
| library bundle spec_sha256 | 1 | PASS — `55882f4b05e7fee1…` |
| export spec_sha256 = library bundle (13 × 3d-entity/1 exports carrying the add-on's vendored spec/, 3 × image/1 exports written by the library) | 16 | 16 PASS — every export's manifest says `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3` |

Round-trip asserts, per 3d-entity fixture: triangle count, distinct world
positions, distinct (position, UV) corners, sha256 of the sorted position
set, of the sorted triangle list and of the sorted corner set (positions
rounded to 1e-4), bones, actions, materials, images, entity uuid; for point
clouds also the vertex count. Per image fixture: packed bytes == the primary
payload (sha256), RGBA u8 pixel sha256 == the extracted primary file loaded
directly, pixel sha256 identical after export + re-import, uuid kept.

Measured values worth knowing:
* crate-cc0-* (5 fixtures): vertices 4686 → 4737 while triangles (6576),
  positions (3348 distinct), corners (4628) and all three hashes are
  unchanged. Cause measured on the GLBs: the 51 extra vertices duplicate
  (position, normal to 1e-3, UV) — Blender's glTF exporter splits on
  last-bit normal differences. Raw vertex count is therefore NOT asserted
  (it is printed).
* gsplat-v1 281 498 points and gsplat-cc0 6 000 points survive the round
  trip (needed an exporter fix: face-less meshes are now written as glTF
  POINTS; before it, 281 498 → 0 was measured). Point colours are not carried.
* humanoid-retarget-v1: armature-only package, 23 bones, 1 action, exported
  and re-imported (the gate exports the whole scene).

## Changes to the add-on made for this (vs the earlier `adapters/blender` of `fa32df8`)

* `vendor/werk_single.py` (the release library, copied) + `libwerk.py`.
* importer: library verdict + Ed25519-verified `signature_verified` on every
  import; image/1 packages dispatch to `image_io.import_image_file`.
* exporter: re-reads every export with the library (`library_verdict`,
  `self-verify-*` error entries); point clouds as glTF POINTS; version 1.1.0.
* `image_io.py`: image/1 import (packed datablock) and export
  (`write_image_package`); `File > Export > werk Image (.werk)`.
* gates and tools relocatable (`tools/werk_paths.py`); Blender profile and
  scratch redirected into `_gate_out/`.
* `vendor/README.md`: the stale `werk_read.py` hash (64de154c…, 31 997 B)
  corrected to the current copy (1a839b6b…, 55 480 B).

## Not run

* The UI: operators were registered and re-registered (clause
  "registration"), but no File > Import / Export dialog was clicked; the
  "werk Image" export operator's `invoke` / `draw` never ran.
* Any Blender other than 4.2.1 (4.0–4.4 and 4.5/5.x not tested; 4.5 and 5.2
  profile folders exist on this machine but those builds were not run).
* Linux / macOS Blender.
* Directory-form (`*.werk/` folder) packages through the add-on.
* The gauntlet packages (`gauntlet/round*/…werk`) — not fixtures, not run.
* Signing on export (not implemented by design).
* Normals, tangents, vertex colours and skin weights are not compared by the
  release gate; animation curves are compared only in `test_gate.py`'s
  synthetic rig.

## Reproducing (the scratch copies were deleted after the run to save disk)

```
mkdir <repo-archive>
git -C <repo> archive release-fixes | tar -x -C <repo-archive>
cd <repo-archive> && python tools/fetch_fixtures.py --from-dir <release-assets>
cd core && CARGO_INCREMENTAL=0 CARGO_TARGET_DIR=<cargo-target> cargo build --release --lib
set WERK_REPO / WERK_LIBS / WERK_DLL as above, then the two gate commands (and gimp\gate.py)
```
