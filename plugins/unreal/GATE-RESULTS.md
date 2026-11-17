# WerkLink on UE 5.8 -- gate results

## Re-gate on the re-vendored release library (W10, 2026-11-17)

**147 PASS, 0 FAIL, 4 NOT-RUN** (gate 129 s after the plug-in build), the same clause set and
counts as the W5c run below: A 14, A2 22 (21 of 21 reader-rule variants agree with
`python -m werk` and werkc, + exit status), B 18, C 93 PASS + 4 NOT-RUN (the same four: gsplat
and retarget fixtures import correctly but create no assets).

| | |
|---|---|
| host | Unreal Engine 5.8.2-56702186+++UE5+Release-5.8, `UnrealEditor-Cmd.exe`, Windows 10 19045, MSVC 2022 |
| plug-in | this folder at release commit `c5276a1` (`git archive` of `main`, plug-in code unchanged since W9), `RunUAT BuildPlugin -TargetPlatforms=Win64 -Rocket`: `BUILD SUCCESSFUL`, exit 0, 0 warnings, 0 errors |
| gate project | a fresh `project/WerkGate` (Config + uproject only; plug-in installed as a copy) |
| repository | `<repo-archive>` = `git archive c5276a1` + the release assets via `tools/fetch_fixtures.py --from-dir <release-assets>` (all present and verified) |
| library gated | `libs/` of that archive, bundle `source_rev` `509ebf83be6dd998a255cceca234ceca0b8ac025`; vendored `vendor/werk_single.py` sha256 **`ff3de49babadffa942469a8d6103cac0ecd13804b847b75cabe70acb3a680600`**; werkc built from the archive's `core/` into `libs/_target` |

Command: `sh tests/rebuild_and_gate.sh` from `<repo-archive>/plugins/unreal` (defaults:
`WERK_REPO` = the archive, `WERK_LIBS` = its `libs/`).

**Found, not fixed (recorded for the next release):** WerkLink's own C++ reader does not apply
MINI-SPECS 5.4 to the paths `MANIFEST.json` declares. A `files[]` path `../evil.png` whose zip
entry carries that name is read and verified (`werk_gate.exe --verdict`: exit 0, nothing dead,
no error), where werk-core, the three bootstrap loaders and the libraries refuse that version
(a single-version node dies; a multi-version node falls back; exit 1). No file is written
outside the project (the bytes come from the zip in memory), but the verdict disagrees. The fix
belongs in `Private/Core/werk_manifest.cpp` (version loop: `IsSafeZipName(F.path)` before
`Reader.Read`, then report every unsafe path in a version the loop did not try) plus an A2
variant; it was not made because it changes a shipped plug-in after the release-commit runs.

---

## W5c, 2026-11-07, final re-vendor

Final run, against the **release-fixes** library and repository: **147 PASS, 0 FAIL, 4 NOT-RUN**
(140 s). Raw output `_gate_out/gate-run.txt`, per-clause JSON `_gate_out/gate.json`, in-editor
results `_gate_out/python/ue_result.json`, exports `_gate_out/python/exports/`, the reader-rule
variants and their verdicts `_gate_out/agree/` (`agree.json`), commandlet logs
`_gate_out/commandlet/logs/`.

| | |
|---|---|
| host | Unreal Engine **5.8.2-56702186+++UE5+Release-5.8** (reported by the editor), `UnrealEditor-Cmd.exe`, Windows 10 19045, MSVC 2022 |
| plug-in | WerkLink 0.2 (this folder), `RunUAT BuildPlugin -TargetPlatforms=Win64 -Rocket`: exit 0, 0 compiler warnings / errors (`_build/build.log`) |
| gate project | `project/WerkGate/WerkGate.uproject` (content-only; plug-in installed as a copy) |
| werk release repo | branch `release-fixes` of `stage\werk` @ **26e3e14**, taken with `git archive 26e3e14` into `_repo/` (stage\werk's checkout untouched), plus the 6 asset fixtures from `stage\assets-fixes\fixtures\`; all 15 fixtures pinned OK by `_repo/tests/fixture_pin.py` |
| library gated | `stage\libs` lib_version **0.1.0**, bundle `source_rev` **26e3e143b2e7dd2787df411967486157097a0a67** (bundle.json sha256 `9088d1bc…`); vendored `vendor/werk_single.py` sha256 **`082420506e949d100ba05daf40d513e0dd9689507dc7e1653c1e18d4db62864e`**; werkc `stage\libs\_target\release\werkc.exe` (built 22:38) |
| readers | `python -m werk` (stage/libs/python), vendored `werk_single.py`, `node js/bin/werk.js` (Node v22.14.0), `werkc verify --json` (JSON Schema validation), `_repo/loaders/werk_read.py`, `.c` (MSYS2 gcc `-std=c99 -O2`), `.rs` (rustc `-O --edition 2021`); bootstrap loaders judged on `--verify --strict` |
| ports | WerkLink has no network code (no socket / HTTP / listen in `WerkLink/Source`); no server was started |

Command: `sh tests/rebuild_and_gate.sh` (RunUAT build, install into the gate project, then
`py -3.12 tests/gate.py --repo _repo --libs <libs>`).

## Clause counts

| part | what | PASS | FAIL | NOT-RUN |
|---|---|---|---|---|
| A | engine-free core, MSVC `cl /std:c++17 /W4 /WX`: build, 11 clauses on crate-v1 + damaged twin (selftests incl. the dangling-edge guard and the MINI-SPECS 5.4 zip rules), exit status, deflated fixture (13 nodes, 76 files hashed) | 14 | 0 | 0 |
| A2 | **reader-rule agreement** (`tests/agree_release_fixes.py`): 21 damaged variants of crate-tex-v1 (unsigned) and crate-cc0-lean-v1 (signed); WerkLink's core verdict (exit status, dead-node set, signature word) vs `python -m werk` vs werkc: 21 of 21 agree, + exit status | 22 | 0 | 0 |
| B | `tests/roundtrip_gate.py` (commandlet route, counts derived from the manifests): 17 clauses + exit status | 18 | 0 | 0 |
| C | `-run=pythonscript` route: 12 `3d-entity/1` fixtures imported (exit status, node count and files-verified equal to the release reader's / the manifest's); 8 exports, each through 7 readers, edge check, re-import | 93 | 0 | 4 |

A2 variants and the agreed verdict: baseline unsigned (0, absent) and signed (0; WerkLink
`unverified`, full readers `signed-and-valid`); **duplicate entry name** (2); SIGNATURE.json not
JSON / not an object / wrong `manifest_sha256` in the last chain entry (1, `present-and-invalid`);
foreign `algorithm` (0, `unverified`); a `files[]` record without `size` / with a string size,
`active` not an integer, empty `versions`, node without `type` (1, node `bounds` dead, rest
loads); `nodes` not an array / missing, MANIFEST.json not an object / unparseable / absent (2); flag bit 3 (2); a byte after the EOCD that its comment
length does not cover (2); invalid UTF-8 in MANIFEST.json's directory name (2) and in the last
record's name (1, `bounds` and `geom-game` dead: their file is missing).

**NOT-RUN (4):** gsplat-cc0-v1, gsplat-cc0-v1-damaged, gsplat-v1, humanoid-retarget-v1 import
correctly (exit and counts match) but create no assets -- WerkLink does not turn points, Gaussian
splats, skeletons or retarget binds into UAssets -- so there is nothing to export.

## Reader changes for release-fixes (SPEC §1 / §6 / §12.1, MINI-SPECS §5.4)

WerkLink's reader is its own engine-free C++ (it does not link werk-core), so the new rules were
implemented there and then measured against the release readers (part A2):

* **zip (MINI-SPECS §5.4, six rules):** EOCD = highest matching record whose comment length
  reaches the end of the file; exactly *total records* are walked, the directory's byte size is
  not used; names decoded as lossy UTF-8 (U+FFFD); flag bit 3 refuses the container, bit 0 the
  entry; **two records with one name refuse the container (`bad-container`, exit 2)**; the
  central directory is the authority, a bad local header / data past the end is
  `zip-entry-invalid`; method-0 data is checked by the manifest's size + sha256, not the CRC
  (inflated data still against the CRC).
* **manifest (SPEC §12.1):** `nodes` missing or not an array, or the manifest not an object, is
  `manifest-structurally-invalid` (exit 2; an unparseable one `manifest-unparseable`, a
  missing one `manifest-absent`); a node without a string `node_id` / `type`, an
  integer `active`, a non-empty `versions[]`, a version without an integer `v` or a `files`
  array, or a file record without a string `path`, a string `sha256` and an integer `size` is
  dead under its id (`node-dead`); the rest loads. Sizes are always compared (0 is a size).
* **signature (SPEC §6):** WerkLink still has no Ed25519 and says `unverified`, but it now checks
  what it can: SIGNATURE.json must be a JSON object whose last chain entry's (and top-level,
  when present) `manifest_sha256` is the sha256 of MANIFEST.json, else `present-and-invalid`
  (error, exit 1). A foreign `algorithm` is a warning, state `unverified`.
* Version fallback already reported the failed file as an error (status 1) and an `active`
  naming a missing version with a warning alone, as §10.1 now says; unchanged.

The edit is recorded in `tools/patch_release_fixes.py` and `tools/patch_release_fixes_selftest.py`.

## The "+8 files verified" question (first pass, still true)

The recon's 4 FAILs were files-verified +8 per fixture. Diffing the `spec` node of
`crate-tex-v1.werk` at werk-artcraft `e8c52e3` (the last baseline, 66 files) against the release
fixture (74): exactly 8 added, 0 removed (WRITING-3D-ENTITY.md, WRITING-IMAGE.md,
examples/write_minimal_3d_entity.py, examples/write_minimal_image.py, formats/splat-32.md,
schemas/core.revisions / core.scene / manifest.base schema), from artcraft-profiles `c8f9266`.
Re-pins change spec bytes, not the count (release-fixes fixtures give the same 186 / 74 / 82 /
182). `roundtrip_gate.py` therefore derives node count and files-verified from each manifest
with the vendored reader; only WerkLink's own behaviour counts stay pinned.

## Defects this gate found and fixed (first pass)

1. **Two meshes, one zip entry name** (`geometry/game.glb` twice): readers disagreed (py / js /
   werk_read.py: 2 dead nodes; werkc / C / Rust: clean). Fixed: one path per node + a writer
   guard refusing a path listed by two nodes. (The release readers now refuse such a zip
   outright, release-fixes `77b91b0` / `e82a446` / `10aa250`.)
2. **Constant UV channel exported** (crate-v1 re-import exit 1). Fixed.
3. **No deflate** (deflated fixture refused, exit 2). Inflate added.
4. **Dangling-edge guard** added, and exported materials write their `requires` edges. The
   negative path is covered by the core selftest only (the exporter cannot produce one).

First-pass runs, for the record: 87 PASS / 27 FAIL -> 123 / 2 -> 125 / 0 (against fa32df8);
release-fixes runs 144 / 0, then 147 / 0 after the manifest-level codes were split
(`manifest-absent` / `-unparseable` / `-structurally-invalid`) and three variants added.

## Not run

* UE 5.7 (not installed); the changed source was not compiled against 5.7.
* The live-editor / Remote Control gate and the Content Browser menu (no interactive editor,
  no screen access).
* Export of points / gsplat / skeleton / retarget content (not supported by WerkLink).
* Ed25519 verification (WerkLink has none; reports `unverified`).
* Linux / macOS builds.
