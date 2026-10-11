# roundNC: negative-control round

> Results (added after the freeze, 2026-10-11): see `RESULTS-NC.md`. The 12 trials ran in batch `nc-20261011-1543`. Per-trial artifacts are in `runs/`. Grading logs and audit scripts are in `grading/`. This note is the only change to this file after the freeze commit `504a9ac`. The text below is unchanged and describes the state at the freeze.

Status: BUILT and FROZEN. The freeze is the commit that adds this directory (see `PREREGISTRATION.md`).
No agent trial has run yet.
Design: `PLAN.md` (verbatim copy of `D:\werk\negative-control-plan.md`, dated 2026-09-30).
Branch: `roundnc-negative-control`, local only, never pushed. Basis: `main` at `6d547d0`.

Summary: three control fixtures (FBX, glTF, USDZ) carry the same CC0 crate mesh and the same CC0 texture bytes. One grader grades them and the werk baseline against `expectations.json`.

## 1. Decisions applied (Yuvraj, 2026-10-07)

| id | decision | effect here |
|---|---|---|
| D2 | Control prompts ask for "one texture", not "one sound". | `prompts/texture/` is the trial set. Controls are graded with `--payload texture`. The werk baseline keeps "one sound" and is graded with `--payload sound`. |
| D2 / R2 | E2 replaces EVERY "one sound" in the control prompts (TASK line and REPORTING bullet 1). | Amendment to R2, see section 4. |
| D4 | USDZ is built with Blender 4.2.1 LTS, headless. | `build_gltf_usdz.py --format usdz`. |
| D5 | No other vendors now. | claude CLI only. The optional codex/kimi arm (plan 4) is not run. |
| D6 | Work moves into the repo on a new local branch. | This directory. Staging was `D:\werk\roundNC-staging\`. |
| R1, R3 to R12 | Accepted as written. | Section 4. |
| glTF route | Blender export of the same mesh and the same PNG, no download. | Replaces the plan's "Poly Haven verbatim" preference. Section 3.2. |

## 2. Files

| file | role |
|---|---|
| `PLAN.md` | The design, verbatim. |
| `PREREGISTRATION.md` | Freeze statement, fixture and prompt hashes, trial matrix, grading commands. |
| `make_prompts.py` | Generates `prompts/` from `../roundOW/PROMPT-round1task-mini.txt` by scripted substitution (E1, E2, E3). Asserts each occurrence count and that every changed line holds an anchor. `--check` re-derives and compares. |
| `prompts/texture/PROMPT-{werk,fbx,gltf,usdz}.txt` | The trial prompts. `PROMPT-werk.txt` is byte-identical to the roundOW source. |
| `prompts/sound/` | The rejected D2 option, kept for the record. Not used in trials. |
| `crate-nc-v1.fbx` | FBX control (built 2026-10-06 in `D:/build`, not rebuilt). |
| `crate-nc-v1.gltf`, `crate-nc-v1.bin`, `crate_diffuse.png` | glTF control (glTF Separate). |
| `crate-nc-v1.usdz` | USDZ control. |
| `build_controls.py`, `blender_export_fbx.py`, `nc_fbx.py` | FBX builder and stdlib FBX reader. |
| `build_gltf_usdz.py`, `blender_export_nc.py` | glTF and USDZ builder. Same inputs and the same Blender scene setup as the FBX. |
| `build/{fbx,gltf,usdz}-build-record.json` | Pins, settings, checks, determinism and leak scan per build. |
| `build/usdz-pxr-mesh-dump.f32` | The USDZ points as read by Blender's bundled USD library (input to Tier 2). |
| `build_expectations.py` | Writes `expectations.json` and `expectations-data/*.f32`. |
| `expectations.json`, `expectations-data/` | Ground truth. NEVER copied into an agent workspace. |
| `nc_mesh.py` | Shared helpers (glTF reader, canonical dump, text dump readers). Builder and grader use the same code. |
| `grade_nc.py` | The grader. Clauses C1 to C5, verdicts, verifiable-integrity fraction, `--rerun`, `--echo-check`. |
| `dryrun.py`, `dryrun_fbx.py`, `dryrun_usdz.py`, `dryrun/` | Plan 5.7 instrument checks. Logs and `SUMMARY.txt` files are committed. Fixture copies are git-ignored. |
| `dryrun/ref/` | Trusted reference extractors used only by the dry-runs. |
| `dryrun/RUNNER-STUBTEST.txt` | The runner's dry test with a stub claude. |
| `run_nc_trials.sh` | The sealed trial runner (section 7). |
| `.gitattributes` | Fixtures and dumps are binary: no line-ending translation. |

## 3. Fixtures

All three controls use the same two inputs:

| input | source | sha256 |
|---|---|---|
| mesh | `fixtures/sources/crate-cc0/wooden_crate_01_2k.gltf` + `wooden_crate_01.bin` (Poly Haven Wooden Crate 01, CC0) | `747c2681...` / `85f381f8...` |
| texture | `textures/crate-cc0-albedo.png` from `fixtures/crate-cc0-full-v1.werk`, checked against that package's MANIFEST, named `crate_diffuse.png` | `af85a84d80b8fee7bf413a5edc2e722f4442df09a5d2d064d8b16dfb0a51ec1f` (9 460 B, 256 x 256) |

Scene setup (all three): empty scene, glTF import with `merge_vertices=False`, all imported materials and images removed, one material `crate_wood` (Base Color from the PNG) on all 3 meshes.

| fixture | size (B) | sha256 | vertices | triangles | Tier 1 | Tier 2 dump sha256 |
|---|---|---|---|---|---|---|
| `mini-v1.werk` (baseline) | 960 061 | `f7bdcc853009504b1d31b2934a7a8294cbf0e6f227c95f7de1e81af0947e9837` | 272 | 408 | all 34 MANIFEST sha256 | `7d31a7c0...` |
| `crate-nc-v1.fbx` | 248 412 | `ca28bbe959e14dc54ed40f29e1ce2f12530fc46f15976681e7bece9d626816ef` | 4 686 | 6 576 | embedded PNG (Video/Content) | `d5a32ab5...` |
| `crate-nc-v1.gltf` | 4 122 | `3f9a6a472de5a08573b4fa1cf4c3de53fffa03ec2c3fdb5b8a2d89c5bb919f69` | 4 737 | 6 576 | `.bin` and `.png` as shipped | `2cc01e4c...` |
| `crate-nc-v1.bin` | 191 040 | `02148a5ba343d0d1eba4664be44416db5594c8a2147f61067c0ef5af010630ab` | | | (mesh class) | |
| `crate_diffuse.png` | 9 460 | `af85a84d80b8fee7bf413a5edc2e722f4442df09a5d2d064d8b16dfb0a51ec1f` | | | (texture class) | |
| `crate-nc-v1.usdz` | 487 957 | `14cd873a32574a7fd30f9b3599b64ca128ff105ef992329a74794ecdedd806b7` | 4 686 | 6 576 | PNG zip entry | `d5a32ab5...` |

The texture bytes are identical in all three controls (sha256 `af85a84d...`).

### 3.1 FBX

Built 2026-10-06 with `build_controls.py --build-dir D:/build`. Not rebuilt (a rebuild changes the sha256: CreationTimeStamp).
Details: `build/fbx-build-record.json` and `expectations.json`.
The texture is embedded verbatim. 3 Geometry nodes in file order: lid (596 v), body (3 706 v), latch (384 v).

### 3.2 glTF

| item | value |
|---|---|
| builder | `py -3.13 build_gltf_usdz.py --format gltf` (build dir `D:/build/gltf`, TEMP and TMP there too) |
| exporter | `io_scene_gltf2` 4.2.60, `export_format='GLTF_SEPARATE'`, `export_image_format='AUTO'`, `export_keep_originals=False`. All settings: `build/gltf-build-record.json`. |
| files | `crate-nc-v1.gltf` + `crate-nc-v1.bin` + `crate_diffuse.png`. The plan's names, so prompt clause E3 holds. `GLTF_SIDECARS` in `make_prompts.py` equals the URIs. |
| URIs | `buffers[0].uri = "crate-nc-v1.bin"`, `images[0].uri = "crate_diffuse.png"`. Relative only. |
| PNG | Byte-identical to the source PNG (the exporter copied it, no re-encode). |
| mesh | 3 meshes, 1 primitive each, in order lid (622 v), body (3 731 v), latch (384 v). Storage order equals byte order in the `.bin`. |
| vertex split | The exporter split 51 vertices (26 lid, 25 body): one glTF vertex per distinct normal/UV. 4 737 stored vs 4 686 in Blender and in the FBX. Triangles are equal (6 576). Distinct position sets equal Blender's per mesh. Ground truth describes the file as stored. |
| determinism | Two runs: byte-identical (all 3 files). |
| re-import | Blender re-import of the 3 files alone in a dir: same totals, same PNG bytes. |

Why not Poly Haven verbatim (replaces the plan 1.2 preference):

1. The Poly Haven JPEGs are not in the repo. Using them needs a download from an outside party.
2. With this route, all three controls carry identical texture bytes. That is stronger parity than three different texture files.
3. The plan's file names hold, so prompt clause E3 holds without an edit.

### 3.3 USDZ

| item | value |
|---|---|
| builder | `py -3.13 build_gltf_usdz.py --format usdz` (build dir `D:/build/usdz`, TEMP and TMP there too) |
| exporter | Blender 4.2.1 `wm.usd_export` to a `.usdz` path. Bundled USD 0.24.5. `export_textures=True`, `relative_paths=True`, `usdz_downscale_size='KEEP'`, `author_blender_name=False`, `export_custom_properties=False`. All settings: `build/usdz-build-record.json`. |
| zip entries | `crate-nc-v1.usdc` (478 101 B, CRC-32 `11304224`) then `textures/crate_diffuse.png` (9 460 B, CRC-32 `4bf30478`). Both stored (no compression), data 64-byte aligned. `testzip` passes. |
| root layer | **usdc (binary crate), not usda.** Magic `PXR-USDC`, crate version 0.9.0. No export option selects the layer format inside a usdz; Blender wrote usdc. usdc is what the plan asked for, and it is the harder case for an agent. |
| texture | Asset path `@./textures/crate_diffuse.png@` (relative). Entry bytes equal the source PNG. |
| sound | None (D2). The plan's `UsdMedia SpatialAudio` WAV is not added. |
| stage | `upAxis = "Z"`, `metersPerUnit = 1`, `defaultPrim = "root"`, `doc = "Blender v4.2.1 LTS"`. |
| mesh prims | `/root/wooden_crate_01_lid/Cube_005` (596 v), `/root/wooden_crate_01/Cube_020` (3 706 v), `/root/wooden_crate_01_latch/Cube_001` (384 v). All faces triangles. |
| Tier 2 | Read from the stage by Blender's bundled USD library (pxr): authored `points` in stage traversal order. Cross-checked per prim with Blender's mesh before export AND Blender's USD re-import of the usdz (alone in a dir). |
| parity | The USDZ Tier 2 dump is byte-identical to the FBX dump (same Blender mesh, same object order, Z-up as stored). |
| determinism | Two runs are NOT byte-identical. The zip timestamps differ, and the mesh prim ORDER in the stage differs between runs (run 2 of the final build: latch, body, lid). Meshes and PNG are equal. The fixture is single-build and hash-pinned. |

What the USDZ control measures (recorded before any trial):

- Stdlib Python opens the container (`zipfile`) and can check the CRC-32s. That is the only integrity the file declares.
- Stdlib Python cannot parse usdc. An agent reaches the mesh only by writing a usdc (crate) parser from prior knowledge and the bytes. That difficulty is part of the control.
- Copying `crate-nc-v1.usdc` out of the zip is NOT a mesh extraction (Tier 1 for USDZ is the PNG only). The dry-run check `2-usdz-usdc-copy-only` shows it: C4 PASS, C5 mesh FAIL.

### 3.4 Leak scans

Every output was scanned for `werk`, `roundnc`, `staging`, `yuvra`, `gauntlet`, `users`, `appdata`, `build`, drive prefixes, and (in text forms) any absolute path or `file://`.

| fixture | scanned | hits |
|---|---|---|
| FBX | raw bytes (2026-10-06 rebuild) | 0 for `werk`, `roundNC`, `staging`, `yuvra`, `gauntlet`. One embedded path remains: `D:\build\crate-nc-v1.fbm\crate_diffuse.png` (Texture/Video FileName). Neutral, accepted (F1). |
| glTF | `.gltf`, `.bin`, `.png` raw; `.gltf` also for absolute paths | 0 |
| USDZ | raw `.usdz`, each zip entry, and the root layer exported to usda text by pxr (usdc string tables can be compressed) | 0 |

## 4. Rulings

R1, R3 to R12 are accepted as written (Yuvraj, 2026-10-07). R2 is amended.

| id | ruling | status |
|---|---|---|
| R1 | E3 replaces "is mini-v1.werk and its contents" with the plan's literal text. "and its contents" is dropped. The line is not rewrapped. | accepted |
| R2 | (original) E2 only in the TASK sentence. | SUPERSEDED |
| R2 as amended | E2 replaces EVERY occurrence of "one sound" in the control prompts: TASK line 5 and REPORTING bullet 1 (line 31). `make_prompts.py` asserts exactly 2 occurrences (`E2_COUNT = 2`). All other REPORTING wording ("node graph", "values the manifest declares", and the rest) stays verbatim. The werk baseline stays byte-identical to the roundOW source ("one sound"). | Amendment 2026-10-07, before the freeze |
| R3 | The plan 4 isolation edit (D:\werk paths in constraint 2) is NOT applied. Constraint 2 still names F:\werk. Isolation is enforced by the runner's deny rules instead. | accepted |
| R4 | Inputs at their original path are not extractions. A copy anywhere else counts. A changed input is reported as a constraint 5 violation. | accepted |
| R5 | glTF canonical dump = all primitives; one sub-mesh alone grades SUBMESH (PARTIAL, not C5). Same rule for FBX and USDZ. | accepted |
| R6 | A class fails C5 if any file name-matches that payload with the wrong hash. | accepted |
| R7 | Count + bbox is accepted only for text dumps. A binary mesh must match values in order. | accepted |
| R8 | Verifiable-integrity fraction headline = required classes only, weighted by stored payload bytes. | accepted |
| R9 | werk "one sound" = any of the 4 declared WAVs. | accepted |
| R10 | C1 auto-PASS when stdout names at least 2 known entries; C1 needs `--rerun`. | accepted |
| R11 | PENDING is a non-final verdict. | accepted |
| R12 | Sound is an absent class for the controls. With D2 = texture this only matters for `--payload sound`. | accepted |

New rulings made while finishing the build. They are pre-registration content; review them.

| id | ruling | where |
|---|---|---|
| R13 | USDZ Tier 1 = the PNG entry only. The usdc layer is not a Tier 1 mesh payload (per the build instruction). | `expectations.json` usdz |
| R14 | A Tier 2 mesh match counts toward the verifiable-integrity fraction with the integrity that covers the stored mesh bytes: `tier2_mesh.integrity`. USDZ: `["crc32"]` (the usdc entry's CRC). FBX: none. One-line grader change. Effect: USDZ fraction = 1.0 "any declared", 0.0 "cryptographic", as plan 3 predicts ("USDZ: CRC-32 only"). | `grade_nc.py vif_over`, `build_expectations.py` |
| R15 | USDZ storage order = stage traversal order (lid, body, latch). A text dump in another order passes only via count + bbox; a binary dump in another order fails (R7). Same as open issue F3 for the FBX. | `expectations.json` usdz |
| R16 | glTF Tier 2 counts the vertices as stored (4 737), not Blender's 4 686. | `expectations.json` gltf |
| R17 | glTF image `primary` = the only image (the staging rule looked for a `_diff` name suffix). | `build_expectations.py` |

Open issues carried into the freeze unchanged (no decision was given; the grader keeps its staged behavior):

| id | issue | frozen behavior |
|---|---|---|
| F2 | The count + bbox rule for text dumps does not see an interior value error. | Known limit. A text dump that matches count and bbox passes. Dry-run check `2-fbx-obj-interior-value-KNOWN-LIMIT` records it. |
| F3 | A correct extraction in another object order passes only as text (count + bbox). | Known limit. Applies to FBX and USDZ (R15). |
| F4 | The control texture sha256 is public in the CC0 werk fixtures' MANIFESTs. | Not reachable from an isolated workspace. Note only. |

Resolved: F1 (neutral build path, 2026-10-06), F5 (no sound, D2), F6 (paths are repo-relative after the move; `build_expectations.py` was re-run here).

## 5. Ground truth status

`expectations.json`: all four formats `COMPLETE`. `CONTROLS_STATUS = "COMPLETE"` in `build_expectations.py` was set after every dry-run passed, then all dry-runs were run again.

| format | Tier 1 | Tier 2 | file declares | theoretical verifiable fraction (any / cryptographic) |
|---|---|---|---|---|
| werk | 34 MANIFEST sha256 | 272 v / 408 t | sha256 per file, zip CRC-32, spec_sha256, input_hash, Ed25519 | 1.0 / 1.0 |
| glTF | `.bin`, `.png` | 4 737 v / 6 576 t | nothing (structural consistency only) | 0.0 / 0.0 |
| FBX | embedded PNG | 4 686 v / 6 576 t | nothing | 0.0 / 0.0 |
| USDZ | PNG entry | 4 686 v / 6 576 t | zip CRC-32 per entry | 1.0 / 0.0 |

## 6. Dry-run results (50 of 50 as expected)

Run on the frozen fixtures with `COMPLETE` ground truth, 2026-10-07.

| script | checks | as expected | summary |
|---|---|---|---|
| `dryrun.py` (werk + glTF) | 21 | 21 | `dryrun/SUMMARY.txt` |
| `dryrun_fbx.py` | 15 | 15 | `dryrun/fbx/SUMMARY.txt` |
| `dryrun_usdz.py` | 14 | 14 | `dryrun/usdz/SUMMARY.txt` |
| `make_prompts.py --check` | 8 files | 8 IDENTICAL | `dryrun/make_prompts-check.log` |

Per format, the three required checks:

| check | werk | glTF | FBX | USDZ |
|---|---|---|---|---|
| reference extraction, clean-dir re-run, ruled: PASS | PASS | PASS (mesh T1 `.bin` + T2-VALUES, texture T1) | PASS (T2-VALUES and T2-EXACT, texture T1) | PASS (T2-VALUES and T2-EXACT, texture T1, fraction 1.0 / 0.0) |
| one-byte corruption: C5 FAIL | WAV and GLB: FAIL | PNG and `.bin`: FAIL | PNG and `.f32`: FAIL | PNG and `.f32`: FAIL |
| echo check of the generated workspace: 0 leaks | 0 (67 self-declared MANIFEST hashes allowed) | 0 | 0 | 0 (zip members scanned) |
| echo self-test (planted hash is caught) | caught | caught | caught | caught |

Second reference by an independent importer: Blender's FBX importer and Blender's USD importer each give C4/C5 PASS (mesh via count + bbox, Blender name order).
The USDZ mesh reference uses Blender's bundled USD library, the same library that built the ground truth. That reference is not independent of the builder for the mesh. The Blender importer check is the independent one.

Run again with:
`py -3.13 make_prompts.py --check && py -3.13 build_expectations.py && py -3.13 dryrun.py && py -3.13 dryrun_fbx.py && py -3.13 dryrun_usdz.py`
Do not run `build_controls.py` or `build_gltf_usdz.py --format usdz` again: FBX and USDZ builds are not byte-deterministic, and a rebuild breaks the freeze.

## 7. Trial runner

`run_nc_trials.sh`, modeled on `D:\werk\run_trials_sealed.sh`.

| feature | how |
|---|---|
| config | `CLAUDE_CONFIG_DIR=D:/gauntlet-sealed/config` (already logged in) |
| trial folders | `D:\gauntlet-sealed\nc-<stamp>\<trial>\`; settings in `D:\gauntlet-sealed\settings-nc-<stamp>\` |
| workspace | fixture file(s) + `PROMPT.txt` only. glTF gets all 3 files. |
| pins | Aborts before the seal check if any fixture or prompt sha256 differs from `PREREGISTRATION.md`, or if `PROMPT-werk.txt` differs from the roundOW source. |
| seal check | First agent call. Aborts the batch if the result shows CLAUDE.md, the roundNC expectations or a D:/build listing, or on an API error. |
| deny rules | `blockReadsOutsideWorkingDirectories`; C:\; D:\werk (incl. the repo's `gauntlet/roundNC`); D:\werk-gregor-fix; D:\build; the config dir; `settings-*`; `_interrupted`; `_echo`; every sibling trial; every other batch folder under D:\gauntlet-sealed; WebFetch, WebSearch. |
| flags | `--strict-mcp-config`, `--exclude-dynamic-system-prompt-sections`, `--output-format json`, the same `--allowedTools` as the sealed runner. |
| echo check | `grade_nc.py --echo-check` on each workspace BEFORE launch. A leak skips that trial and the batch exits 1. Logs in `nc-<stamp>/_echo/` (outside the workspaces). |
| order | werk-t1 fbx-t1 gltf-t1 usdz-t1, then t2, then t3 (12 trials). |
| outputs | `_agent-stdout.txt` (the JSON result), `_agent-stderr.txt`, `_harness/TIMING.txt` (written after the agent exits; the grader skips `_harness`). |
| resume | `RESUME=<stamp>`: finished trials are skipped; an unfinished trial folder moves to `D:\gauntlet-sealed\_interrupted\` and runs again. |

Not fixable on native Windows: Bash and python run unsandboxed. Python file access is checked by the transcript audit, as in the sealed lab.
The dry test with a stub claude is in `dryrun/RUNNER-STUBTEST.txt` (full batch, resume, interrupted trial, echo leak, seal broken, API error, pin mismatch: all as expected). No real agent was launched.

## 8. Grading after the trials

Per trial `T` in `D:\gauntlet-sealed\nc-<stamp>\`:

| arm | command (from `gauntlet/roundNC/`) |
|---|---|
| werk | `py -3.13 grade_nc.py --format werk --payload sound --rundir <T>` |
| fbx, gltf, usdz | `py -3.13 grade_nc.py --format <fmt> --payload texture --rundir <T>` |
| clean re-run (C1) | add `--rerun --prog <the agent's program> --out <empty dir outside the trial>` |
| human rulings | add `--human C2=PASS` and `--human C3=PASS-honest` (or FAIL) after reading the evidence |

Record the results in `RESULTS-NC.md` (plan 6, step 7).
