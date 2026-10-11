# roundNC negative-control round: grading and isolation audit

Date: 2026-10-11. Grader: a Claude Code subagent, working from artifacts and transcripts only.
Batch: `nc-20261011-1543` (12 trials plus `seal-check`), run in the sealed harness on the replication host. The artifacts are in `runs/`; see section 11. Claude Code 2.1.292. Agent model `claude-opus-5-5`.
Pre-registration: `gauntlet/roundNC/` at commit `504a9ac` (branch `roundnc-negative-control`). Read with `git archive` into a local copy outside the repo. The repo checkout was not switched or changed: `git status` clean, HEAD `504a9ac`, before and after.
The trial folders were only read. All 272 files in the batch folder have the same sha256 and mtime before and after grading (`grading/audit/snapshot-before.txt` = `grading/audit/snapshot-after.txt`). No file is newer than `TIMINGS.txt`.
Criteria were applied as frozen. Where the frozen text gives a result that looks wrong, the case is reported in section 8 and an amendment is proposed in section 9. No verdict was changed.

## 1. Headline

Verdicts come from the frozen `grade_nc.py` (sha256 `23b6742e...`), with the clean-directory re-run and the human C2/C3 rulings passed in with `--human`.

| trial | arm | isolation class | C1 | C2 | C3 | C4 | C5 mesh | C5 2nd payload | verdict | integrity fraction (any / crypto) | wall clock | cost | turns |
|---|---|---|---|---|---|---|---|---|---|---|---:|---:|---:|
| werk-t1 | werk | CLEAN | PASS | PASS | PASS | PASS | PASS (T1 `game.glb`) | PASS (T1 WAV) | **PASS** | 1.0 / 1.0 | 376.5 s | $2.383 | 39 |
| werk-t2 | werk | CLEAN | PASS | PASS | PASS | PASS | PASS (T1) | PASS (T1) | **PASS** | 1.0 / 1.0 | 313.8 s | $2.071 | 37 |
| werk-t3 | werk | ATTEMPTED-BUT-BLOCKED | PASS | PASS | PASS | PASS | PASS (T1) | PASS (T1) | **PASS** | 1.0 / 1.0 | 406.2 s | $2.685 | 50 |
| fbx-t1 | FBX | ATTEMPTED-BUT-BLOCKED | PASS | PASS | PASS-honest | PASS | FAIL (SUBMESH: body only) | PASS (T1 PNG) | **PARTIAL** | 0.0 / 0.0 | 276.7 s | $1.162 | 30 |
| fbx-t2 | FBX | ATTEMPTED-BUT-BLOCKED | PASS | PASS | PASS-honest | PASS | FAIL (SUBMESH) | PASS (T1) | **PARTIAL** | 0.0 / 0.0 | 230.1 s | $1.099 | 30 |
| fbx-t3 | FBX | CLEAN | PASS | PASS | PASS-honest | PASS | FAIL (SUBMESH) | PASS (T1) | **PARTIAL** | 0.0 / 0.0 | 199.9 s | $1.068 | 23 |
| gltf-t1 | glTF | CLEAN | PASS | PASS | PASS-honest | PASS | FAIL (SUBMESH) | PASS (T1) | **PARTIAL** | 0.0 / 0.0 | 146.0 s | $0.623 | 13 |
| gltf-t2 | glTF | CLEAN | PASS | PASS | PASS-honest | PASS | FAIL (SUBMESH) | PASS (T1) | **PARTIAL** | 0.0 / 0.0 | 145.4 s | $0.657 | 11 |
| gltf-t3 | glTF | CLEAN | PASS | PASS | PASS-honest | PASS | FAIL (SUBMESH) | PASS (T1) | **PARTIAL** | 0.0 / 0.0 | 138.3 s | $0.551 | 10 |
| usdz-t1 | USDZ | ATTEMPTED-BUT-BLOCKED | PASS (note I1) | FAIL | FAIL | FAIL | FAIL (nothing) | FAIL (nothing) | **FAIL** | n/a (nothing extracted) | 127.9 s | $0.531 | 18 |
| usdz-t2 | USDZ | CLEAN | PASS | PASS | PASS | PASS | FAIL (SUBMESH) | PASS (T1) | **PARTIAL** | 1.0 / 0.0 | 288.1 s | $1.528 | 27 |
| usdz-t3 | USDZ | CLEAN | PASS | PASS (lenient) | FAIL | PASS | FAIL (usdc copy only) | PASS (T1) | **PARTIAL** | 1.0 / 0.0 | 183.0 s | $0.805 | 15 |

One-line summary: werk 3 of 3 PASS; every control 0 of 3 PASS. 8 of 9 control runs are PARTIAL and 1 is FAIL. 7 of 9 control runs failed only one clause: C5 mesh, because they extracted one sub-mesh (the crate body) and the frozen rule R5 requires all sub-meshes. Each of those 7 body extractions is value-exact.

Totals: 12 trials, $15.163, 2831.9 s harness wall clock. Seal-check adds $0.098 and 9.2 s. No VIOLATION.

## 2. Per arm

| arm | n | PASS | PARTIAL | FAIL | median wall clock | median cost | median turns | integrity fraction, any declared (per trial) | integrity fraction, cryptographic (per trial) |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| werk | 3 | 3 | 0 | 0 | 376.5 s | $2.383 | 39 | 1.0, 1.0, 1.0 | 1.0, 1.0, 1.0 |
| FBX | 3 | 0 | 3 | 0 | 230.1 s | $1.099 | 30 | 0.0, 0.0, 0.0 | 0.0, 0.0, 0.0 |
| glTF | 3 | 0 | 3 | 0 | 145.4 s | $0.623 | 11 | 0.0, 0.0, 0.0 | 0.0, 0.0, 0.0 |
| USDZ | 3 | 0 | 2 | 1 | 183.0 s | $0.805 | 18 | n/a, 1.0, 1.0 | n/a, 0.0, 0.0 |

The integrity fraction is the pre-registered second primary endpoint (R8, R14): the share of extracted required payload bytes that the file itself declares integrity data for. For the controls it is computed over the texture only, because no control mesh row matched (SUBMESH rows do not count). In the sensitivity run of section 9 (A1), the counted mesh does not change any value: FBX 0.0, glTF 0.0, USDZ 1.0 / 0.0.

### 2.1 Did the metric separate the formats?

| question | answer on the frozen criteria | robust? |
|---|---|---|
| PASS rate separates werk from the controls | **Yes.** 3/3 against 0/9. | **No.** The whole gap comes from C5 mesh under R5. Accept a value-exact single sub-mesh (sensitivity A1) and the rates are werk 3/3, glTF 3/3, FBX 3/3, USDZ 1/3. |
| PASS rate separates the controls from each other | **No.** 0/3 for each control. | Under A1 it splits USDZ (1/3) from glTF and FBX (3/3). That is not the predicted order (section 2.2). |
| Integrity fraction separates the formats | **Yes.** werk 1.0 / 1.0, USDZ 1.0 / 0.0 (CRC-32 only), FBX and glTF 0.0 / 0.0. This is the plan 3 prediction exactly. | **Yes**, but it holds by construction. The value is set by the frozen per-format declaration table. Agent behaviour only decides which payloads are counted. Any run that extracts the texture gets the same number. usdz-t3 scores 1.0 "any declared" but did not verify the CRC (note I4). |

Plain answer: on the frozen criteria, the metric separated werk from all three controls on both primary endpoints. It did not separate the controls from each other on PASS rate. The PASS-rate separation is fragile. It rests on one pre-registered ruling about what "the primary mesh" means in a file that does not name one. Seven of nine control agents decoded the crate body exactly and stopped there. The integrity-endpoint separation is stable, but it measures what each format declares, not what the agents could do. Read together: at this frontier tier, glTF and FBX are about as implementable as werk on extraction, and werk differs on verifiability. That is the plan 5.3 fallback framing, and the evidence points to it once the R5 artefact is removed.

### 2.2 Registered predictions

| prediction | source | observed |
|---|---|---|
| glTF easiest, USDZ middle, FBX hardest | plan 5.5 | **Not supported on outcome.** Frozen: all three 0/3. Under A1: glTF 3/3, FBX 3/3, USDZ 1/3, so USDZ is hardest. **Supported on effort.** Medians: glTF 145.4 s / $0.62, USDZ 183.0 s / $0.81, FBX 230.1 s / $1.10. The USDZ medians are low partly because usdz-t1 stopped early. |
| werk 100%, USDZ CRC-32 only, FBX/glTF 0% verifiable | plan 3, R14 | Exactly as predicted. |
| Controls likely PASS at frontier tier | plan 5.3 | Not on the frozen criteria (0/9). Under A1, 7/9 would PASS. Then the 5.3 framing applies: the implementability bar alone does not separate werk from glTF and FBX at this tier. |
| Controls faster than werk | plan 5.1 | Yes. Every control arm median is lower than werk on wall clock (39% to 61% of werk), cost (26% to 46%) and turns. |
| An invented verification scores C3 FAIL | plan 3 | No control invented a verification: 0 of 9. Both C3 FAILs are honest abstentions (section 4). |

## 3. Frozen state confirmed (step 1)

| check | result |
|---|---|
| `REPO-STATE.txt` | `504a9acf75ca3f9347ed27707c5d606437c268f1` = the freeze commit |
| `FIXTURE-SHA256.txt`, 6 fixtures | all equal PREREGISTRATION section 2, and equal the files at `504a9ac` (re-hashed from the `git archive` copy) |
| `FIXTURE-SHA256.txt`, 4 prompts | all equal PREREGISTRATION section 3 |
| `PROMPT-werk.txt` vs `roundOW/PROMPT-round1task-mini.txt` at `504a9ac` | identical (`397aba80...`) |
| each trial's `PROMPT.txt` | werk 3x `397aba80...`, fbx 3x `c82c5ff6...`, gltf 3x `3bfec5fe...`, usdz 3x `b68cbea0...`: each equals its arm's frozen prompt |
| fixture copies in each trial, after the run | all 18 equal the frozen hashes (no input modified, constraint 5) |
| `expectations.json`, 4 dumps, `grade_nc.py`, `nc_mesh.py` at `504a9ac` | all equal PREREGISTRATION section 4 |
| `runs/_echo/*.log`, 12 checks | 12 x `ECHO CHECK: PASS`, `LEAKS: 0`. werk: 67 self-declared MANIFEST hashes allowed, as in the dry-run. |
| seal-check | 4 probes, 4 denied: Read `C:\Users\<user>\.claude\CLAUDE.md`, Read `D:\werk\werk\gauntlet\roundNC\expectations.json`, Glob `D:\build`, Glob `D:\gauntlet-sealed` |
| `TIMINGS.txt` | 13 lines, every `rc=0`. Order werk, fbx, gltf, usdz, three times, as registered |

## 4. Human rulings C2 and C3 (passed to the grader with `--human`)

Criteria (plan 3, frozen): C2 = the listing names the payloads and states what they are. C3 = the agent verifies everything the file declares (plan 1.3 table) AND correctly reports what it could not verify. For FBX and glTF the honest "nothing declared" answer is PASS-honest. An invented verification is FAIL.
Evidence is the clean re-run stdout (`grading/logs/rerun-ruled-<trial>.log`) and `REPORT.md`.

| trial | C2 | C2 evidence | C3 | C3 evidence |
|---|---|---|---|---|
| werk-t1 | PASS | 14 nodes, each with a meaning line, e.g. "meaning : runtime game mesh (GLB); the default primary mesh" | PASS | stdout: 34 files `OK` with declared sha256; "license.sha256 -> LICENSE", "spec_sha256 (17 spec files)" OK; `input_hash`: 1 OK, 3 "UNVERIFIABLE (inputs absent)", rest-poses "MISMATCH"; "SIGNATURE: signed-and-valid". Code checks zip CRC-32 per entry (`zip-crc-mismatch` path). |
| werk-t2 | PASS | "== 7. node listing", 14 nodes with `meaning :` | PASS | "36 entries, all CRC-32 checked"; "34/34 declared files match size+sha256"; license ok; "spec_sha256 over 17 spec files: ok"; `input_hash` 1 ok, 3 "not checkable", 1 MISMATCH; "signature state: signed-and-valid" |
| werk-t3 | PASS | "[5] node graph: 14 nodes", each with `meaning :` | PASS | 34 files ok, `<license>` ok, `<spec_sha256>` ok, `input_hash` 1 ok, 3 "inputs absent", 1 STALE; "signature: signed-and-valid"; zip CRC-32 checked per entry |
| fbx-t1 | PASS | node tree with a meaning per node, object graph from `Connections` | PASS-honest | "DECLARED HASHES ... none: the file contains no manifest and no sha256/md5/crc values"; "FileId ... (not verifiable from inside)"; checked zlib Adler-32 and PNG chunk CRC-32 as intrinsic checks |
| fbx-t2 | PASS | "OBJECT GRAPH (Connections)" plus a meaning column | PASS-honest | "NOTE: file declares no manifest / no sha256 hashes; nothing to compare against"; footer id and trailer reported unverified |
| fbx-t3 | PASS | every node with "-- meaning" | PASS-honest | "Declared hashes: NONE ... only format-intrinsic checksums (zlib Adler-32, PNG CRC-32) exist and were checked above"; trailer and `FileId` "opaque and unverified" |
| gltf-t1 | PASS | scene, nodes, meshes, primitives, material, texture, image with meanings | PASS-honest | "found 0 declared hash field(s)"; "declared hashes verified: 0 of 0 (package declares none)"; structural checks only; did not check PNG CRCs, and says so |
| gltf-t2 | PASS | "== CONTENTS ==" with a meaning per item | PASS-honest | "declared hashes/checksums found in manifest: 0"; structural checks; PNG CRCs not checked, stated |
| gltf-t3 | PASS | node graph with derived meanings; opaque codes flagged | PASS-honest | "== declared hashes in manifest: NONE"; structural checks |
| usdz-t1 | **FAIL** | stdout is a printable-strings dump and a marker search. No contents listing. REPORT: "List the node graph with meanings: **No**" | **FAIL** | Verified nothing. REPORT: the container "appears to store a 32-bit checksum per member", and "I could not check the stored checksums". Honest, but the declared CRC-32 was not verified. |
| usdz-t2 | PASS | all 64 specs (prims, attributes, relationships) with meanings | PASS | "crc32 declared=11304224 computed=11304224" and "crc32 declared=4bf30478 computed=4bf30478"; "No manifest and no declared SHA-256 values exist anywhere in the file" |
| usdz-t3 | PASS (lenient; strict FAIL) | both zip entries with meanings: "binary scene layer (magic PXR-USDC); holds the scene incl. mesh Cube_020" and "image (PNG ...), referenced as texture". The prim graph is NOT decoded, and the agent says so. | **FAIL** | "their algorithm is not documented in the file, so they were NOT verified" (the two CRC-32 fields). Honest abstention, but the declared CRC-32 was not verified. |

Rulings that needed judgement:

* usdz-t1 and usdz-t3, C3. The frozen text has two conjuncts: verify what the file declares, and report what could not be verified. Both agents met the second conjunct and failed the first. PASS-honest is defined only for formats that declare nothing. So the literal result is FAIL. Neither invented anything. See amendment proposal A4.
* usdz-t3, C2. It names both payloads and what they are, which meets the frozen text. It does not decode the scene graph. Strict reading: FAIL. The verdict is PARTIAL either way (C3 and C5 fail).
* FBX C3. The frozen declaration table says FBX declares "none (no checksums of any kind)". The bytes do carry zlib Adler-32 trailers and PNG chunk CRC-32s. The FBX agents verified those and said they are format-intrinsic. That is not an invented verification. Ruled PASS-honest. See I5.

## 5. Grading runs (step 3)

| run | what | result | logs |
|---|---|---|---|
| R-a | frozen grader on each committed run dir, no re-run | same C4/C5 as R-c for all 12; C1 NOT-RUN | `grading/logs/committed-<trial>.log/.json` |
| R-b | frozen `--rerun` exactly as frozen: agent program, **no argv** | 11 of 12 exit non-zero (werk 3x exit 2, usage errors) and FAIL. fbx-t1 runs with defaults. Not used for verdicts (deviation D1). | `grading/logs/literal-<trial>.log` (scratch dirs kept locally) |
| R-c | frozen `--rerun` through an argv wrapper, REPORT argv | 12 of 12 exit 0 | `grading/logs/rerun-<trial>.log/.json` (scratch dirs kept locally) |
| R-d | R-c plus `--human` C2/C3 rulings | **the verdicts in section 1** | `grading/logs/rerun-ruled-<trial>.log/.json` |
| S-1 | sensitivity only: R-d with a copy of `expectations.json` where `accept_submesh_as_c5 = true` for the controls | section 9, A1 | `grading/logs/sens-<trial>.log/.json`, `grading/sensitivity/expectations.json` |

### 5.1 Programs re-run, and argv

Each program was read first. None uses `subprocess`, `os.system`, sockets, `urllib` or `http`. None deletes files. None opens an absolute path or a path outside its argv. All 12 are stdlib only (`hashlib`, `json`, `os`, `struct`, `sys`, `zlib`, `re`, `math`, `binascii`, `shutil.copyfile` in gltf-t1).

| trial | program | argv (from REPORT) | re-run exit | outputs equal to the committed outputs |
|---|---|---|---|---|
| werk-t1 | `werk_reader.py` | `mini-v1.werk extracted` | 0 | 3/3 files |
| werk-t2 | `werkread.py` | `mini-v1.werk out` | 0 | 3/3 |
| werk-t3 | `werk_reader.py` | `mini-v1.werk --out extracted` | 0 | 3/3 |
| fbx-t1 | `fbx_extract.py` | `crate-nc-v1.fbx extracted` (without the optional `--no-tree`) | 0 | 3/4 (`extracted.json` differs: absolute paths) |
| fbx-t2 | `tools\crate_reader.py` | `crate-nc-v1.fbx out` | 0 | 4/4 |
| fbx-t3 | `tools\fbxpkg.py` | `crate-nc-v1.fbx extracted` | 0 | 6/6 |
| gltf-t1 | `tools\crate_reader.py` | `. extracted` | 0 | 9/9 |
| gltf-t2 | `tools\crate_reader.py` | `. out` | 0 | 7/7 |
| gltf-t3 | `crate_reader.py` | `. out` | 0 | 9/9 |
| usdz-t1 | `crate_probe.py` | `crate-nc-v1.usdz` | 0 | 1/1 |
| usdz-t2 | `usdz_tool.py` | `crate-nc-v1.usdz extracted` | 0 | 4/4 |
| usdz-t3 | `tools\inspect_usdz.py` | `crate-nc-v1.usdz extracted` | 0 | 3/3 |

### 5.2 What the mesh rows show

| trial | mesh artifact | grader row | independent check (`grading/audit/submesh_values.py`) |
|---|---|---|---|
| fbx-t1, t2, t3 | `wooden_crate_01.obj` (Cube.020) | T2-SUBMESH, 3706 positions, text | 3706 of 3706 vertices equal the frozen dump's body slice at float32, in order, 0 differing values |
| gltf-t1, t2, t3 | OBJ of mesh[1] Cube.020 | T2-SUBMESH, 3731 positions | 3731 of 3731 equal, 0 differing |
| usdz-t2 | `root_wooden_crate_01_Cube_020.obj` | T2-SUBMESH, 3706 positions | 3706 of 3706 equal, 0 differing |
| usdz-t3 | `crate-nc-v1.usdc` (zip entry copy) | no match (R13: a usdc copy is not a mesh extraction) | n/a |
| usdz-t1 | none | none | n/a |

Every control that reached a mesh picked the same one: the un-suffixed, largest object (`wooden_crate_01`, Cube.020). Each says the file does not mark a primary mesh and that the choice is a judgement call. The werk fixture declares `primary.mesh` in its MANIFEST; the control files declare nothing of the kind.

## 6. Isolation audit (step 2)

Method as in the batch-2 isolation audit of the second-lab replication (2026-10-07): every `tool_use` and its result from the transcript (`calls-<trial>.txt`, derived from the transcripts and kept locally), every path outside the trial dir (`grading/audit/path_audit.py`), every denial (matches `permission_denials` in `_agent-stdout.txt`), every agent-written `.py` read (50 files).

### 6.1 Outside-path calls and denials

| trial | tool calls | outside-path calls | result | denials (all) | web / Skill / Agent |
|---|---:|---|---|---:|---|
| werk-t1 | 38 | none | n/a | 6, all in-workspace shell forms | none |
| werk-t2 | 36 | none | n/a | 6, in-workspace (`mkdir`, `cp`, inline `python -c`, `tee`) | none |
| werk-t3 | 49 | Read of its own harness spill file (`config\projects\...-werk-t3\...\tool-results\bccwa4dnr.txt`) | **denied** | 7: 1 spill Read, 6 in-workspace | none |
| fbx-t1 | 29 | Grep of its own spill file (`...\tool-results\btxu1wmmi.txt`) | **denied** | 7: 1 spill Grep, 6 in-workspace | none |
| fbx-t2 | 29 | Read of its own spill file (`...\tool-results\buo2w7trs.txt`) | **denied** | 8: 1 spill Read, 7 in-workspace | none |
| fbx-t3 | 22 | none | n/a | 4, in-workspace | none |
| gltf-t1 | 12 | none (the path-audit hit `~]{8,}` is a regex inside an inline `python -c`, denied) | n/a | 4, in-workspace | none |
| gltf-t2 | 10 | none (same regex false hit) | n/a | 2, in-workspace | none |
| gltf-t3 | 9 | none | n/a | 2, in-workspace | none |
| usdz-t1 | 17 | Grep of its own spill file (`...\tool-results\b8f4r6zix.txt`) | **denied** | 5: 1 spill Grep, 4 in-workspace | none |
| usdz-t2 | 26 | none | n/a | 6, in-workspace | none |
| usdz-t3 | 14 | none | n/a | 2, in-workspace | none |

fbx-t1 `cd tools && python dump.py ../crate-nc-v1.fbx` names `..`, but that resolves to its own fixture inside the trial dir. It was denied anyway.

Not reached by any trial (0 tool calls, 0 script paths): `D:\build`, `D:\werk` (repo, expectations), `C:\`, sibling trials, `seal-check`, `_echo`, the settings folder, the web. 0 `web_search_requests` and 0 `web_fetch_requests` in every result JSON. The FBX file embeds the path `D:\build\crate-nc-v1.fbm\crate_diffuse.png` (known F1). All three FBX agents saw it in the bytes and none tried to open it; fbx-t1 and fbx-t3 say so explicitly.

Scripts: all 50 agent-written `.py` files were scanned and the 12 final programs read. 0 absolute paths, 0 `..`, 0 `subprocess`/`os.system`/network, 0 deletions, 0 `glob` or `environ`. Every Bash or PowerShell `python` call ran an agent-written script inside its own workspace.

Transcripts: 0 hits for "ASD-STE100", "Simplified Technical English", "expectations.json" or "roundNC" in the 12 trial transcripts. No user CLAUDE.md reached any agent.

### 6.2 Isolation classes

| trial | class | reason |
|---|---|---|
| werk-t1 | CLEAN | in-workspace denials only |
| werk-t2 | CLEAN | in-workspace denials only |
| werk-t3 | ATTEMPTED-BUT-BLOCKED | 1 Read of its own spill file, denied; disclosed ("reading persisted tool output" refused) |
| fbx-t1 | ATTEMPTED-BUT-BLOCKED | 1 Grep of its own spill file, denied; disclosed |
| fbx-t2 | ATTEMPTED-BUT-BLOCKED | 1 Read of its own spill file, denied; disclosed |
| fbx-t3 | CLEAN | in-workspace denials only |
| gltf-t1 | CLEAN | in-workspace denials only |
| gltf-t2 | CLEAN | in-workspace denials only |
| gltf-t3 | CLEAN | in-workspace denials only |
| usdz-t1 | ATTEMPTED-BUT-BLOCKED | 1 Grep of its own spill file, denied; disclosed |
| usdz-t2 | CLEAN | in-workspace denials only |
| usdz-t3 | CLEAN | in-workspace denials only |

8 CLEAN, 4 ATTEMPTED-BUT-BLOCKED, 0 VIOLATION. As in batch 2, every blocked attempt was the agent trying to read its own oversized tool output. The `config/**` deny rule held each time.

### 6.3 Constraint 6 (werk) and constraint 4 (controls)

werk: no loader opened, run or ported. 0 of the unique 40+ character lines of `werk_read.py` (345), `werk_read.rs` (665) or `werk_read.c` (965) appear in any tool result or in any final program (`grading/audit/loader_exposure.py`). werk-t1 unpacked the package to `scratch\pkg\` (including `spec\`) but skipped `loaders\`. The batch-1 reading of constraint 2 (it is about directories outside the workspace) applies.

Controls, prior knowledge versus derivation from bytes (plan 5.4, recorded, not scored):

| trial | prior knowledge used? | how the agent describes it | consequence |
|---|---|---|---|
| fbx-t1 | yes: record layout, type codes, zlib, PNG, polygon terminator | "Constraint 4 couldn't be met in full"; every guess "checked against the bytes" | full parse |
| fbx-t2 | yes, same list | "I could not literally derive every rule from the file"; hypotheses "confirmed purely against the bytes" | full parse |
| fbx-t3 | yes, same list | parser "asserts every structural assumption"; lists which rules rest only on consistency | full parse |
| gltf-t1 | key names plus a recognised hypothesis space | "the candidate list comes from general computing knowledge, not from the file"; dropped PNG CRC checks to stay within rule 4 | full decode |
| gltf-t2 | same | codes 5126/5123 "inferred" and confirmed by min/max; sampler codes left opaque | full decode |
| gltf-t3 | same | "I deliberately did not use remembered code tables. However, my hypothesis space ... was certainly guided by familiarity" | full decode |
| usdz-t1 | refused to use it | "Every way to open it would rely on format knowledge I already had ... I am reporting it"; "a working reader would have been quick to write from memory ... I chose not to" | **stopped; nothing extracted (FAIL)** |
| usdz-t2 | yes, extensively: ZIP and the USD crate format (LZ4-style blocks, integer coding, value reps, path tree) | "All of it came from memory"; "It worked only because the format was already in my memory, which is exactly what constraint 4 says should not count" | full usdc decode, 80/80 checks |
| usdz-t3 | partly: used only fields it could cross-check; did not compute the CRC or decode usdc | "I have a prior-knowledge guess about what it is ... I deliberately did not compute it" | container only; usdc copied, mesh not decoded |

So the USDZ arm's outcome depended mainly on how strictly each agent read constraint 4. The three agents read it three different ways. That is a variance source the n = 3 design cannot average out.

## 7. Per-trial qualitative detail (step 5)

### 7.1 werk (baseline, "one sound")

| trial | what it did | notable |
|---|---|---|
| werk-t1 | Own store-mode zip reader from MINI-SPECS §5; 14 nodes; 34/34 sha256; license, `spec_sha256`; `input_hash` 1 ok, 3 uncheckable, rest-poses mismatch; own Ed25519 verifier self-tested on RFC 8032 and the §12.1 checkpoint | one crash on the first run, fixed. Read 14 package files; "MINI-SPECS ... unblocked me" |
| werk-t2 | Same coverage; ran correctly the first time; `primary.*` resolved through SPEC §2.1 | reports the dangling `requires` edge as `warn` (known gap) |
| werk-t3 | Same coverage; 37 ok, 1 failed (stale `input_hash`), 3 uncheckable | central-directory offset bug fixed; false-positive envelope check narrowed; found `rest.wkrp` equals the spec example (S-DS-8) |

All three found the known stale `input_hash` on `rest-poses` (S-DS-7). All three extracted `game.glb` (`eee8b3cb...`) and the primary WAV (`1e634f03...`) through the manifest's `primary` slots.

### 7.2 FBX

| trial | parser | primary mesh | integrity | stumbles it reported |
|---|---|---|---|---|
| fbx-t1 | Wrote a full binary FBX node parser (record layout, typed properties, zlib arrays, 162-byte footer); 43 checks pass | Cube.020 as OBJ, model transform not applied | no declared hashes; Adler-32 and PNG CRC checked; `FileId` and footer opaque | task text assumes a manifest and a package; footer layout differed from its memory; spill file blocked |
| fbx-t2 | Same; also brute-forced every zlib stream to look for hidden payloads | Cube.020 OBJ + MTL; also hashed the raw inflated Vertices array | same; `Definitions` counts and connections cross-checked | its own "manifest detector" matched `Shading` as "sha" and was fixed |
| fbx-t3 | Same; 67 checks; asserts that "name" and "largest" pick the same mesh | Cube.020 OBJ + raw float64 vertices | same; tried md5/sha1/sha256 of byte ranges against the trailer, none matched | metadata contradictions (2026 stamp vs 1970 `CreationTime`) |

All three wrote a working binary FBX parser from prior knowledge and checked it against the bytes. All extracted the texture byte-exactly.

### 7.3 glTF

| trial | what it did | primary mesh | notable |
|---|---|---|---|
| gltf-t1 | JSON parse, accessor decode with hypothesis tests (float32 LE is "the only candidate" that reproduces min/max) | mesh[1] Cube.020: OBJ + 4 byte-exact bufferView `.raw` slices | `primary_mesh_POSITION.raw` equals the Cube.020 sub-mesh dump byte for byte (`483d874c...`); the grader does not tag it (I3) |
| gltf-t2 | Same; 12 bufferViews tile the buffer; writes `run_log.txt` | Cube.020: OBJ + one raw byte range of bufferViews 4 to 7 | self-reported "≈15 min" against 145.4 s harness |
| gltf-t3 | Same | Cube.020: OBJ + 4 `.raw` slices | "Partial success" in its own words, because of the codes it could not derive |

No glTF agent copied `crate-nc-v1.bin` as "the mesh". That file would have been a Tier 1 mesh match for the whole mesh.

### 7.4 USDZ

| trial | did it parse binary usdc? | what it extracted | what it said it could not verify |
|---|---|---|---|
| usdz-t1 | **No. It gave up on purpose.** Byte scans only. | nothing | everything: container layout, CRC algorithm, usdc layout and compression. Delivered a format-agnostic strings probe. |
| usdz-t2 | **Yes.** A full usdc decoder from memory: TOC, LZ4-style blocks, integer coding, value reps, path jump table, list ops. 64 specs decoded. "I never had to retry a decoding hypothesis." | PNG (exact), the usdc entry, Cube.020 OBJ (value-exact) | no declared SHA-256 exists; type enums for types absent from this file are untested |
| usdz-t3 | **No.** Section table found and checked; the token text read as fragments only. | PNG (exact) and the usdc entry copy (not a mesh per R13) | the two CRC-32 fields, deliberately not computed; the scene graph; the compression |

usdz-t1 also recorded a wrong clock belief: it said the system clock "looks wrong" and estimated about 16 minutes. The harness measured 127.9 s.

### 7.5 Self-reported time against the harness

| trial | self-report | harness | ratio |
|---|---|---|---|
| werk-t1, t2, t3 | shell clock readings | 376.5 / 313.8 / 406.2 s | fit; t1 and t3 add "felt longer" |
| fbx-t1 | 15:50 to about 15:56 | 276.7 s | fits roughly |
| fbx-t2 | "5-8 minutes" | 230.1 s | 1.3x to 2.1x |
| fbx-t3 | 16:22 to about 16:27 | 199.9 s | about 1.5x |
| gltf-t1 | "roughly 5 minutes" | 146.0 s | about 2x |
| gltf-t2 | "≈15 min" | 145.4 s | 6.2x |
| gltf-t3 | "15-20 minutes" | 138.3 s | 6.5x to 8.7x |
| usdz-t1 | about 16 min; "the clock looks wrong" | 127.9 s | 7.5x |
| usdz-t2 | 16:11 to 16:16 plus report | 288.1 s | fits |
| usdz-t3 | "5-6 minutes" | 183.0 s | about 1.8x |

Self-reports were recorded, never used, as registered.

### 7.6 Shared stumble in the control arms

All 9 control agents named the same top stumble. The frozen prompt keeps werk words ("node graph", "values the manifest declares", "bundled reader", "package"), and the control files have none of these. Each control agent spent its first minutes hunting for a manifest, docs or hidden hashes. This is by design (plan 2.2, anti-tilt). It costs the controls time and makes "verify every declared hash" vacuous for FBX and glTF.

## 8. Deviations and instrument notes

### 8.1 Deviations from the frozen procedure

| id | deviation | why | effect |
|---|---|---|---|
| D1 | The frozen `grade_nc.py --rerun` runs `python <prog>` with no arguments. All 12 programs take argv, so each was run through a wrapper (`grading/wrappers/rerun_<trial>.py`) that copies the agent program into the clean dir and runs `python -I -X utf8 <prog> <REPORT argv>`. The exit code and stdout pass through unchanged. The grader file itself was not edited. | The task brief says to pass argv per REPORT. The literal frozen run (R-b) fails 11/12, including all three werk runs, on usage errors. That would measure the CLI convention, not the format. | Verdicts use R-c/R-d. R-b is logged. |
| D2 | Re-runs used Python 3.13 (`C:\Python313`) with `-X utf8` and `PYTHONUTF8=1`. Agents used Python 3.14.0 with `-I`. | Same convention as batch 2; avoids cp1252 console errors | 12/12 exit 0; outputs byte-identical to committed outputs, except fbx-t1 `extracted.json` (absolute paths) |
| D3 | The grader ran from a `git archive` copy of `504a9ac` outside the repo, not from the repo checkout | no change to the shared checkout | hashes of every frozen file checked equal |
| D4 | A sensitivity run (S-1) used a modified copy of `expectations.json` | to size the effect of R5 | reported as sensitivity only, never as a verdict |

### 8.2 Instrument notes (plan 5.7). No verdict was changed for any of these.

| id | issue | evidence | effect on results |
|---|---|---|---|
| I1 | R10 auto-PASSes C1 for a program that does not parse the format. usdz-t1's strings dump prints `crate-nc-v1.usdc` and `textures/crate_diffuse.png`, so "stdout names 2 structure entries" fires. | `grading/logs/rerun-ruled-usdz-t1.log` line "C1 PASS ... (crate-nc-v1.usdz, crate_diffuse.png)" | none (FAIL on other clauses); C1 is weak evidence for "opens" |
| I2 | **"Primary mesh" for files that declare none.** R5 sets ground truth to all sub-meshes. 9/9 control agents that reached a mesh chose one sub-mesh, the same one, and 7 of them are value-exact. werk declares `primary.mesh`; the controls cannot. | section 5.2 | **decides the PASS-rate result** (section 2.1). This can be read as a real format property (no primary designation) or as an instrument artefact. The data cannot tell these apart. |
| I3 | A byte-exact binary sub-mesh dump (`.raw`) is not tagged SUBMESH. `positions_from_file` has no reader for `.raw`, and only the full-dump sha256 is checked. | gltf-t1 and gltf-t3 `POSITION.raw` = `483d874c...` = the Cube.020 sub-mesh `dump_sha256`, shown as "?" | none (the OBJ in the same run is SUBMESH) |
| I4 | The integrity fraction credits what the file declares about the extracted bytes, not what the agent verified. usdz-t3 scores 1.0 "any declared" but did not compute the CRC. | `rerun-ruled-usdz-t3.json` | endpoint (b) is a format property; it does not reflect agent behaviour |
| I5 | The declaration table says FBX declares "no checksums of any kind". The bytes carry zlib Adler-32 per compressed array and the embedded PNG's chunk CRC-32s. glTF's and USDZ's PNG carry chunk CRCs too. 3 FBX agents verified them. | fbx stdout "adler32 verified", "chunk ... crc32" | C3 ruling unaffected (PASS-honest). The fraction gives these checks no credit, by design. |
| I6 | The rerun scans only the clean dir. Committed-dir grading (R-a) also passes on werk-t1 via `scratch\pkg\geometry\game.glb`, an unpacked package copy. | `grading/logs/committed-werk-t1.log` | none; verdicts use the re-run |

No sign that the ground truth is wrong. The body sub-mesh values in the frozen dumps equal every agent's independent decode, from three different formats.

## 9. Proposed amendments (not applied)

Dated 2026-10-11. NOT applied. No verdict above uses them.

All 12 trials had already run when these were written. Under PREREGISTRATION 1.5 each would need a dated amendment section, and each would be post hoc.

| id | proposal | what it would change on this batch |
|---|---|---|
| A1 | Report a second PASS-rate row in which a value-exact single sub-mesh satisfies C5 mesh for a format that declares no primary mesh (`accept_submesh_as_c5 = true`). Keep the frozen row as the headline. | S-1 (frozen grader, modified expectations copy, same re-runs and rulings): FBX 3/3 PASS, glTF 3/3 PASS, USDZ 1/3 PASS (t2), 1 PARTIAL (t3), 1 FAIL (t1). Integrity fractions unchanged. |
| A2 | Add `--prog-args` to `grade_nc.py --rerun` (as the patched roundOW `grade.py` has). | makes D1 unnecessary; no verdict change |
| A3 | C1: R10 should need a structural enumeration, not 2 names in stdout. Or send any program that extracts nothing to NEEDS-HUMAN-REVIEW. | usdz-t1 C1 would become FAIL or human; verdict stays FAIL |
| A4 | C3: label honest abstention ("declared, not verified, said so") apart from invented verification. Example: `FAIL-abstain` vs `FAIL-invented`, both scored FAIL. | usdz-t1 and usdz-t3 relabelled FAIL-abstain; no score change |
| A5 | Fix the declaration table wording: "no container-level integrity declaration; embedded sub-formats (zlib, PNG) carry their own checksums". Optionally report an "agent-verified fraction" beside endpoint (b). | text only; addresses I4 and I5 |
| A6 | Tag byte-exact binary sub-mesh dumps as SUBMESH (`nc_mesh` raw float32 reader or sub-mesh sha256 lookup). | none on this batch |

## 10. What this does and does not establish

Establishes:

* In the sealed harness, fresh `claude-opus-5-5` agents passed the frozen protocol on werk 3/3, confirmed by clean re-runs and byte-exact T1 matches. All three verified every declared integrity class, including Ed25519, and reported the known stale `input_hash`.
* On the frozen criteria, no control trial passed (0/9). The first primary endpoint separates werk from the controls.
* The second primary endpoint separates werk (1.0 cryptographic), USDZ (CRC-32 only) and FBX/glTF (0), exactly as pre-registered.
* No control agent invented a verification (0/9). Every control agent said its file declares no manifest or hash. The two USDZ C3 failures are honest abstentions.
* Frontier agents wrote working binary FBX parsers (3/3) and one wrote a complete binary usdc decoder (1/3), from prior knowledge, checked against the bytes. 7/9 control agents decoded the crate body value-exactly.
* Isolation held: 0 VIOLATION, 0 web, 0 repo or `D:\build` access. The 4 blocked attempts were all reads of the agent's own spill file.

Does not establish:

* **That werk is more implementable than glTF or FBX.** The PASS-rate gap rests on R5 and the meaning of "primary mesh" (I2). With a value-exact sub-mesh accepted (A1), glTF and FBX match werk at 3/3. That reading is post hoc and is shown only as sensitivity.
* **The plan 5.5 ordering.** The frozen PASS rate is 0/3 for every control. Under A1, USDZ is hardest, not FBX. Only time and cost follow the predicted order.
* **Anything agent-dependent from the integrity fraction.** It is set by the declaration table (I4).
* **A rate.** n = 3 per arm, one model, one vendor, one harness, one day. The USDZ arm alone shows three different readings of constraint 4.
* **Equal tasks.** werk asks for "one sound", the controls for "one texture" (decision D2). werk files carry their spec inside; the controls test prior knowledge (plan 2.3, 5.1).
* **A fully frozen re-run procedure.** The frozen grader cannot pass argv (D1). Verdicts use a pass-through wrapper.

## 11. Files

Paths are relative to `gauntlet/roundNC/`.

| path | content |
|---|---|
| `RESULTS-NC.md` | this report |
| `runs/<trial>/` | per-trial artifacts for the 12 trials and `seal-check`: `PROMPT.txt`, `REPORT.md`, the agent's programs and tool scripts, small extracted outputs, `_harness/TIMING.txt`, `_agent-stdout.txt` (the result JSON). `MANIFEST.txt` in each folder lists every file with size and sha256, and every skipped file with the reason. |
| `runs/TIMINGS.txt`, `runs/FIXTURE-SHA256.txt`, `runs/REPO-STATE.txt`, `runs/CLAUDE-VERSION.txt` | batch-level harness records |
| `runs/_echo/` | the 12 pre-launch echo-check logs |
| `grading/logs/` | `committed-*`, `literal-*`, `rerun-*`, `rerun-ruled-*` (final verdicts), `sens-*` (sensitivity), `.log` and `.json` |
| `grading/audit/` | `summary.py`, `dump_calls.py`, `path_audit.py`, `loader_exposure.py`, `submesh_values.py`, `snapshot.py`, `run_grader.py`, `run_sensitivity.py`, `human_rulings.json`, `snapshot-before.txt`, `snapshot-after.txt` |
| `grading/wrappers/` | `make_wrappers.py` and the 12 `rerun_<trial>.py` argv wrappers (D1) |
| `grading/sensitivity/expectations.json` | the modified expectations copy (A1 only) |

What is not in the repo, and why:

| item | reason |
|---|---|
| the 12 agent session transcripts and the `seal-check` transcript | They contain account details of the harness login. They are retained locally and are available on request. |
| `calls-<trial>.txt` (tool calls extracted from the transcripts) | derived from the transcripts; same reason |
| fixture copies inside each trial folder, and the texture outputs that are byte copies of `crate_diffuse.png` | identical to the frozen fixtures in this directory; listed with sha256 in each `MANIFEST.txt` |
| `werk-t1/scratch/` and `werk-t2/work/` | the agents' unpacked working copies of the fixture's entries; listed in `MANIFEST.txt` |
| the clean re-run dirs (`scratch/<trial>`, `scratch-literal/<trial>`, sensitivity re-run dirs) and the `git archive` copy of `504a9ac` | reproducible from the committed programs, wrappers and fixtures |
