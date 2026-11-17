# Stage ARTCRAFT — results

Branch `artcraft-profiles`, cut from `master` at `099167b`. Measured
2026-10-13 on Windows 10, rustc and MSVC as on the host, Python 3, Blender
4.2. The rulings this stage implements are PROPOSED and are in
`docs/RULINGS-2026-10-13.md`; this file is the measurements only.

"Before" was measured in a second, untouched worktree at `099167b` with an LF
checkout (`<lab>\werk-artcraft-base`, removed afterwards), not in the tree being
edited. "After" is this branch with every fixture rebuilt by its builder from
the branch's `spec/` and `loaders/`, and `fixtures/fixtures.json` re-recorded.

## 1. Gates, before and after

Table 11 of the paper, same rows, same format, plus the rows this stage adds.

| Gate (harness) | Before, `master` `099167b` | After, `artcraft-profiles` |
|---|---|---|
| Reference core, three faces (`tests/run_gate.py`) | 11 PASS, 0 FAIL, 1 SKIP | 11 PASS, 0 FAIL, 1 SKIP |
| Golden fixture (`tests/run_gate_a.py`) | 10 PASS, 0 FAIL | 10 PASS, 0 FAIL |
| Enrichment pipeline (`tests/run_gate_3b.py`) | 19 PASS, 0 FAIL, 0 WARN | 19 PASS, 0 FAIL, 0 WARN |
| Retarget, three foreign rigs (`tests/run_gate_6.py`) | 34 PASS, 0 FAIL (28.4 s) | 34 PASS, 0 FAIL (27.8 s) |
| Image profile fixture (`tests/run_gate_9.py`) | **14 PASS, 1 FAIL** | 15 PASS, 0 FAIL |
| Splat, tools, self-regeneration (`tests/run_gate_12.py`) | **17 PASS, 1 FAIL** (16.1 s) | 18 PASS, 0 FAIL (15.3 s) |
| Blender adapter (`adapters/blender/test_gate.py`) | 20 PASS, 0 FAIL (6.7 s) | 20 PASS, 0 FAIL (9.7 s) |
| Unreal round trip (UE 5.7) | not run | not run |
| Unreal engine-free core | not run | not run |
| Unreal live editor control | not run | not run |
| Game engine consumer (CUB) | not run | not run |
| Store, whole-blob and chunked (`store/`, pytest) | 59 tests, 0 failed | 59 tests, 0 failed |
| CC0 public crate (`tests/run_gate_cc0_public.py`) | 14 PASS, 0 FAIL | 18 PASS, 0 FAIL |
| CC0 image (`tests/run_gate_cc0_image.py`) | 9 PASS, 0 FAIL | 11 PASS, 0 FAIL |
| CC0 splat (`tests/run_gate_cc0_gsplat.py`) | 8 PASS, 0 FAIL | 10 PASS, 0 FAIL |
| Fixture pins (`tests/fixture_pin.py`) | 7 of 7 match | 16 of 16 match |
| Reference core, `cargo test --release` | 44 tests, 0 failed (19 unit, 25 conformance) | 82 tests, 0 failed (28 unit, 25 conformance, 29 profiles) |
| **ArtCraft corpus** (`tests/run_gate_artcraft.py`) | did not exist | 71 PASS, 0 FAIL, 0 SKIP |
| **Container** (`tests/run_gate_container.py`) | did not exist | 25 PASS, 0 FAIL, 0 SKIP |
| **Envelope magic** (`tests/run_gate_magic.py`) | did not exist | 22 PASS, 0 FAIL, 0 SKIP |
| **Reference consistency** (`tests/run_gate_reference.py`) | did not exist | 19 PASS, 0 FAIL, 0 SKIP |
| **Writing walkthroughs** (`tests/run_gate_writing.py`) | did not exist | 26 PASS, 0 FAIL, 0 SKIP |

Notes on the table.

* The single SKIP in the first row is the one the paper describes: this
  host's MinGW gcc exits 1 with no diagnostics; the same C source compiles and
  passes under MSVC in the next clause. *(Correction, release finding N2: the toolchain was not broken. Git for Windows' `/mingw64/bin` preceded MSYS2's on PATH, so `cc1.exe` could not load its DLLs (exit 127, nothing printed); with the compiler's own `bin` first on PATH it builds the loader. The gates now run every compiler that way.)*
* The two FAILs before are the same clause in both gates, "the builder
  reproduces the shipped fixture byte for byte" (gate 9: the image builder;
  gate 12: rebuild `e7d3af8d…` against shipped `ede0aee6…`). The shipped
  fixtures embed three spec files with CRLF line endings; a fresh checkout has
  them LF (finding F-AC-6; ruling R1 of 2026-09-09 had left the fixtures on
  the CRLF snapshot). After: every fixture is built from an LF tree.
* The paper's Table 11 says 9 PASS for the golden fixture; `master` measures
  10. That difference predates this branch.
* The three CC0 gates gained pin clauses (4, 2 and 2): finding F-AC-5.
* The store tests use pytest's default temporary directory, which is under
  the user profile on Windows. That is the suite's behaviour on `master` too.

## 2. Old fixtures, new readers

The fifteen fixtures as committed on `master` (taken with `git show
master:<path>`, so they are the bytes pinned there) read by the branch's core
and three loaders. Loaders run `--verify --strict`.

| fixture (as on `master`) | sha256[:16] | old core: exit, dead | new core: exit, dead | new core census | py / rs / c exit |
|---|---|---|---|---|---|
| `crate-cc0-full-v1-damaged.werk` | `53a09de86195681b` | 1, audio-cc0-click | 1, audio-cc0-click | 19 nodes: 15 alive, 3 skipped, 1 dead | 1 / 1 / 1 |
| `crate-cc0-full-v1.werk` | `32b1f4d5d0adbed8` | 0, - | 0, - | 18 nodes: 16 alive, 2 skipped, 0 dead | 0 / 0 / 0 |
| `crate-cc0-lean-v1-damaged.werk` | `7195ead783a30dbc` | 1, disclosure-cc0 | 1, disclosure-cc0 | 14 nodes: 12 alive, 1 skipped, 1 dead | 1 / 1 / 1 |
| `crate-cc0-lean-v1.werk` | `99ba09931c67346f` | 0, - | 0, - | 13 nodes: 13 alive, 0 skipped, 0 dead | 0 / 0 / 0 |
| `crate-tex-v1.werk` | `0b43cfb86a061aaf` | 0, - | 0, - | 11 nodes: 11 alive, 0 skipped, 0 dead | 0 / 0 / 0 |
| `crate-v1-damaged.werk` | `01348a10f0863802` | 1, audio-crate-impact-hard-surface | 1, audio-crate-impact-hard-surface | 37 nodes: 33 alive, 3 skipped, 1 dead | 1 / 1 / 1 |
| `crate-v1.werk` | `0a7a7341d5d508c7` | 0, - | 0, - | 36 nodes: 34 alive, 2 skipped, 0 dead | 0 / 0 / 0 |
| `crate.werk` | `089929d0593b614e` | 0, - | 0, - | 15 nodes: 14 alive, 1 skipped, 0 dead | 0 / 0 / 0 |
| `gsplat-cc0-v1-damaged.werk` | `043340c8440547bc` | 1, points-dc | 1, points-dc | 11 nodes: 9 alive, 1 skipped, 1 dead | 1 / 1 / 1 |
| `gsplat-cc0-v1.werk` | `0f735a338a62e288` | 0, - | 0, - | 10 nodes: 10 alive, 0 skipped, 0 dead | 0 / 0 / 0 |
| `gsplat-v1.werk` | `ede0aee6cc5659af` | 0, - | 0, - | 17 nodes: 17 alive, 0 skipped, 0 dead | 0 / 0 / 0 |
| `humanoid-retarget-v1.werk` | `916cf5c1049f17c6` | 0, - | 0, - | 9 nodes: 8 alive, 1 skipped, 0 dead | 0 / 0 / 0 |
| `image-cc0-v1-damaged.werk` | `4fab20f90d45e14b` | 1, disclosure | 1, disclosure | 12 nodes: 10 alive, 1 skipped, 1 dead | 1 / 1 / 1 |
| `image-cc0-v1.werk` | `6ec5ce122ed28747` | 0, - | 0, - | 11 nodes: 11 alive, 0 skipped, 0 dead | 0 / 0 / 0 |
| `ista-varun-v1.werk` | `923ab39f1742e0b2` | 0, - | 0, - | 15 nodes: 14 alive, 1 skipped, 0 dead | 0 / 0 / 0 |

Result: 15 of 15. Every fixture has the same exit status and the same dead
node in the old core, the new core and the three new loaders. The new core
adds one `info` entry per fixture, `manifest-schema-revision` (the fixture
carries the earlier revision of its manifest schema and was validated against
its own copy), and zero warnings from the second pass against the new
revision, which is what "additive within a major version" predicts.

## 3. The ArtCraft corpus

`<lab>\ArtCraft\werk-integration\samples` at the time of the last measurement:
40 packages from 10 applications in 11 profiles. "Before" is `werkc verify`
built from `master`; "after" is this branch. The census is `nodes: alive,
skipped, dead`. The corpus grew during the stage (34 packages from 9
applications when SPEC §2.2 and §3.1 were written; `soundcraft` arrived
later), and every package that arrived passed the first time it was read.

| package | form | profile | before: exit (error) | after: exit | after: census | signature |
|---|---|---|---|---|---|---|
| `cadcraft/apartment-directory.werk` | directory | `cad-drawing/1` | 1 (unsupported-convention) | 0 | 47: 9, 38, 0 | absent |
| `cadcraft/apartment.werk` | zip | `cad-drawing/1` | 1 (unsupported-convention) | 0 | 47: 9, 38, 0 | absent |
| `deckcraft/every-field-signed-directory` | directory | `presentation/1` | 1 (unsupported-convention) | 0 | 99: 14, 85, 0 | signed-and-valid |
| `deckcraft/every-field-signed.werk` | zip | `presentation/1` | 1 (unsupported-convention) | 0 | 99: 14, 85, 0 | signed-and-valid |
| `deckcraft/sample-deck-directory` | directory | `presentation/1` | 1 (unsupported-convention) | 0 | 50: 7, 43, 0 | absent |
| `deckcraft/sample-deck.werk` | zip | `presentation/1` | 1 (unsupported-convention) | 0 | 50: 7, 43, 0 | absent |
| `deckcraft/with-video-and-sound.werk` | zip | `presentation/1` | 1 (unsupported-convention) | 0 | 105: 14, 91, 0 | absent |
| `designcraft/sample-magazine.folder.werk` | directory | `page-layout/1` | 1 (unsupported-convention) | 0 | 62: 8, 54, 0 | absent |
| `designcraft/sample-magazine.werk` | zip | `page-layout/1` | 1 (unsupported-convention) | 0 | 62: 8, 54, 0 | absent |
| `filmcraft/two-scenes-folder.werk` | directory | `timeline/1` | 1 (unsupported-convention) | 0 | 27: 11, 16, 0 | absent |
| `filmcraft/two-scenes.werk` | zip | `timeline/1` | 1 (unsupported-convention) | 0 | 27: 11, 16, 0 | absent |
| `gridcraft/every-field-signed-directory` | directory | `spreadsheet/1` | 1 (unsupported-convention) | 0 | 73: 16, 57, 0 | signed-and-valid |
| `gridcraft/every-field-signed.werk` | zip | `spreadsheet/1` | 1 (unsupported-convention) | 0 | 73: 16, 57, 0 | signed-and-valid |
| `gridcraft/sales-directory` | directory | `spreadsheet/1` | 1 (unsupported-convention) | 0 | 18: 8, 10, 0 | signed-and-valid |
| `gridcraft/sales.werk` | zip | `spreadsheet/1` | 1 (unsupported-convention) | 0 | 18: 8, 10, 0 | signed-and-valid |
| `lightcraft/library.werk` | zip | `catalog/1` | 1 (unsupported-convention) | 0 | 29: 12, 17, 0 | absent |
| `lightcraft/library.werk.d` | directory | `catalog/1` | 1 (unsupported-convention) | 0 | 29: 12, 17, 0 | absent |
| `lightcraft/photograph-dunes.werk` | zip | `image/1` | 0 (-) | 0 | 17: 16, 1, 0 | absent |
| `lightcraft/photograph-harbour.werk.d` | directory | `image/1` | 0 (-) | 0 | 17: 16, 1, 0 | absent |
| `photocraft/maximal-dir.werk` | directory | `raster-layers/1` | 1 (unsupported-convention) | 0 | 353: 20, 333, 0 | signed-and-valid |
| `photocraft/maximal.werk` | zip | `raster-layers/1` | 1 (unsupported-convention) | 0 | 353: 20, 333, 0 | signed-and-valid |
| `photocraft/simple.werk` | zip | `raster-layers/1` | 1 (unsupported-convention) | 0 | 17: 8, 9, 0 | absent |
| `soundcraft/maximal-3-revisions-signed.werk` | zip | `audio-session/1` | 1 (unsupported-convention) | 0 | 72: 18, 54, 0 | signed-and-valid |
| `soundcraft/maximal-directory.werk` | directory | `audio-session/1` | 1 (unsupported-convention) | 0 | 72: 18, 54, 0 | absent |
| `soundcraft/maximal.werk` | zip | `audio-session/1` | 1 (unsupported-convention) | 0 | 72: 18, 54, 0 | absent |
| `soundcraft/minimal-written-by-script.werk` | zip | `audio-session/1` | 1 (unsupported-convention) | 0 | 13: 8, 5, 0 | absent |
| `soundcraft/simple-directory.werk` | directory | `audio-session/1` | 1 (unsupported-convention) | 0 | 30: 11, 19, 0 | absent |
| `soundcraft/simple.werk` | zip | `audio-session/1` | 1 (unsupported-convention) | 0 | 30: 11, 19, 0 | absent |
| `spark/cc0-sphere-3-versions-signed.werk` | zip | `3d-entity/1` | 0 (-) | 0 | 12: 10, 2, 0 | signed-and-valid |
| `spark/cc0-sphere-3-versions-v1-restored-signed.werk` | zip | `3d-entity/1` | 0 (-) | 0 | 12: 10, 2, 0 | signed-and-valid |
| `spark/cc0-sphere-directory` | directory | `3d-entity/1` | 0 (-) | 0 | 12: 10, 2, 0 | absent |
| `spark/cc0-sphere.werk` | zip | `3d-entity/1` | 0 (-) | 0 | 12: 10, 2, 0 | absent |
| `spark/maximal-scene-signed-one-byte-damaged.werk` | zip | `3d-entity/1` | 1 (hash-mismatch, node-dead) | 1 | 22: 14, 7, 1 (dead: `gsplat-hero`) | signed-and-valid |
| `spark/maximal-scene-signed.werk` | zip | `3d-entity/1` | 0 (-) | 0 | 22: 15, 7, 0 | signed-and-valid |
| `wordcraft/field-notes-directory.werk` | directory | `rich-document/1` | 1 (unsupported-convention) | 0 | 26: 9, 17, 0 | signed-and-valid |
| `wordcraft/field-notes.werk` | zip | `rich-document/1` | 1 (unsupported-convention) | 0 | 26: 9, 17, 0 | signed-and-valid |
| `wordcraft/maximal.werk` | zip | `rich-document/1` | 1 (unsupported-convention) | 0 | 101: 19, 82, 0 | signed-and-valid |
| `wordcraft/report-directory.werk` | directory | `rich-document/1` | 1 (unsupported-convention) | 0 | 21: 9, 12, 0 | absent |
| `wordcraft/report.werk` | zip | `rich-document/1` | 1 (unsupported-convention) | 0 | 21: 9, 12, 0 | absent |
| `wordcraft/written-by-a-stranger.werk` | zip | `rich-document/1` | 1 (unsupported-convention) | 0 | 22: 9, 13, 0 | absent |

Totals. Before: 32 of 32 third-profile packages exit 1 with
`unsupported-convention` ("this build carries no manifest schema for
profile …"); 7 packages of the two reference profiles exit 0; the damaged
package exits 1. After: 39 exit 0; the damaged package exits 1 with exactly
one dead node, `gsplat-hero`, and the other 21 nodes alive or skipped. The
three bootstrap loaders give the same exit status for all 40 and name the same
dead node.

Loaders, before: the Rust and C loaders on `master` refused all six Spark
packages (profile `3d-entity/1`) with "unknown convention" for
`sh_coeff_order` and `sh_degree`.

## 4. Containers

Measured by `tests/run_gate_container.py`; every container is real.

| container | core | py | rs | c |
|---|---|---|---|---|
| `crate-cc0-lean-v1-deflated.werk`, 78 entries all method 8, zlib 1.3.1 | exit 0, counts equal to the store-mode twin | same | same | same |
| the same with one stream made undecodable | exit 1, `zip-entry-invalid`, node `readme` dead | same | same | same |
| store-mode twin with one entry rewritten as method 12 (bzip2) | exit 1, `zip-entry-unsupported`, node `readme` dead | same | same | same |
| twin rewritten with zip64 extra fields in local headers only | exit 0, counts equal to the original | same | same | same |
| zip64, 70,001 entries (Python `zipfile`) | exit 2, `zip64-unsupported` | same | same | same |
| zip64, 4,362,076,500 bytes (Python `zipfile`; `--big`, run once) | exit 2, `zip64-unsupported` | same | same | same |

Before, on `master`: the core reported one deflated entry as `file-missing`
and a fully deflated package as `bad-manifest: MANIFEST.json is not in …`;
the 70,001-entry zip64 file made all four readers exit 1 with four different
messages, the Python loader's a traceback.

## 5. Not run, not done, open

* **Unreal gates (three rows) and the CUB consumer gate: not run.** The
  Unreal plugin's C++ reader and the CUB reader were not changed. Whether
  they read the rebuilt fixtures was not measured. The Unreal exporter
  computes `spec_sha256` over the embedded spec tree; the tree now has more
  files than the 46 the paper quotes.
* **The gauntlet rounds were not re-run.** No agent was handed the new
  specification.
* **`--big` (zip64 over 4 GiB) is opt-in** in the container gate; it was run
  once in this stage.
* **`core.revisions` consistency** (record values exist in `versions[]`,
  `active` agrees with the active record) is specified and not checked by the
  core.
* **`part-reflection-unsupported` and `scene-display-unsupported`** are in
  the code table and emitted by nothing here; no consumer in this repository
  draws.
* **Nesting (SPEC §13)** is not implemented in any reader; §13.2 is an open
  question for Gregor.
* **F-AC-3, canonical number spelling,** is open: MINI-SPECS §3 documents the
  disagreement and the safe subset; no rule was chosen.
* **The Rust and C loaders do not print `[severity] code` report lines** on
  `--verify`; they print per-file words of their own and name a table code
  only for the refusals this stage unified. The reference gate's code clause
  holds for the core and the Python loader only.
* **`<repo>` still has three CRLF working-tree files** (F-AC-6). It was not
  touched. Until they are re-checked-out, every builder on this branch will
  refuse to build from that tree, by design.
* **HANDOVER.md, ROADMAP.md and the paper were not edited.**
