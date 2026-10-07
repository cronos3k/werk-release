# roundNC pre-registration

Date: 2026-10-07. Branch: `roundnc-negative-control` (local). Basis: `main` at `6d547d0`.

## 1. Statement

1. The commit that adds this file is the freeze. It is the pre-registration of roundNC.
2. Frozen with it: `PLAN.md`, the prompts, `expectations.json` and `expectations-data/`, the fixtures, the builders, the grader, the dry-run logs, the runner and `README.md` (all rulings and amendments).
3. No agent trial ran before this commit.
4. After this commit, the grading criteria, the ground truth, the prompts, the fixtures and the trial matrix cannot change without a dated amendment.
5. An amendment is a new section at the end of this file. It states the date, what changed, why, and whether any trial had already run. The original text stays.
6. Every trial and every grade is reported, including FAIL, PARTIAL and aborted runs. Deviations are recorded, not hidden.

## 2. Fixture hashes (sha256)

| fixture file | size (B) | sha256 |
|---|---|---|
| `gauntlet/roundOW/mini-v1.werk` | 960 061 | `f7bdcc853009504b1d31b2934a7a8294cbf0e6f227c95f7de1e81af0947e9837` |
| `gauntlet/roundNC/crate-nc-v1.fbx` | 248 412 | `ca28bbe959e14dc54ed40f29e1ce2f12530fc46f15976681e7bece9d626816ef` |
| `gauntlet/roundNC/crate-nc-v1.gltf` | 4 122 | `3f9a6a472de5a08573b4fa1cf4c3de53fffa03ec2c3fdb5b8a2d89c5bb919f69` |
| `gauntlet/roundNC/crate-nc-v1.bin` | 191 040 | `02148a5ba343d0d1eba4664be44416db5594c8a2147f61067c0ef5af010630ab` |
| `gauntlet/roundNC/crate_diffuse.png` | 9 460 | `af85a84d80b8fee7bf413a5edc2e722f4442df09a5d2d064d8b16dfb0a51ec1f` |
| `gauntlet/roundNC/crate-nc-v1.usdz` | 487 957 | `14cd873a32574a7fd30f9b3599b64ca128ff105ef992329a74794ecdedd806b7` |

`run_nc_trials.sh` holds the same values and aborts on any mismatch.

## 3. Prompt hashes (sha256)

Trial set: `prompts/texture/` (decision D2).

| prompt | used for | sha256 |
|---|---|---|
| `prompts/texture/PROMPT-werk.txt` | werk baseline (byte-identical to `roundOW/PROMPT-round1task-mini.txt`, "one sound") | `397aba804e83938068eb2967b32f961253a031cdecb694e8b8aa4129760119d4` |
| `prompts/texture/PROMPT-fbx.txt` | FBX control | `c82c5ff6cf7a8f545b91b48aee6d83f11afbb71e5b6a51f7f8d5424c93297988` |
| `prompts/texture/PROMPT-gltf.txt` | glTF control | `3bfec5fe499f3db6b6bc1c9fc6841dd303148f924bfe934e2620a24230d244a9` |
| `prompts/texture/PROMPT-usdz.txt` | USDZ control | `b68cbea04eb7d52ddd23f20949b6ff10dcc26383f4b83a9d02e1f4cc8984ec93` |

Permitted edits from the source, and only these (proved by `make_prompts.py`):

| edit | text | count |
|---|---|---|
| E1 | `mini-v1.werk` to the control file name | 3 (glTF: 2, the third is inside E3) |
| E2 | `one sound` to `one texture` (TASK line and REPORTING bullet 1; R2 as amended) | 2 |
| E3 | glTF only: `is mini-v1.werk and its contents` to `is crate-nc-v1.gltf and the two files it references (crate-nc-v1.bin, crate_diffuse.png)` | 1 |

`prompts/sound/` holds the rejected D2 option. It is not used.

## 4. Ground truth and grader hashes (sha256)

| file | sha256 |
|---|---|
| `expectations.json` | `c3f7091ad71357a3c9c2ae9f27ad893d14d3aab95fe596c187bbb6f4934a28e5` |
| `expectations-data/werk-mesh-dump.f32` | `7d31a7c0bb2d0ab4fc0fe7b16243abe0e2fa7fe71c279760d137daab1eff27d2` |
| `expectations-data/gltf-mesh-dump.f32` | `2cc01e4cfe33827249196e6bdfaeac26d45675fa56a999d6d52de589bf1f503c` |
| `expectations-data/fbx-mesh-dump.f32` | `d5a32ab5669b03cf9e08fe5cc592b18cff62fabdaf0b8e5bdeb108866438066e` |
| `expectations-data/usdz-mesh-dump.f32` | `d5a32ab5669b03cf9e08fe5cc592b18cff62fabdaf0b8e5bdeb108866438066e` (equal to the FBX dump, see README 3.3) |
| `grade_nc.py` | `23b6742e1070d0e5eedb4cab4ebfcdf19714e5e1f7c5f6abbdf7a206be20c163` |
| `nc_mesh.py` | `f0abef3e130c0ab61fb2da3754f664fdb640e27578ed3ab2306951ceb78efced` |

## 5. Trial matrix

| arm | fixture in the workspace | prompt | n | graded with |
|---|---|---|---|---|
| baseline | `mini-v1.werk` | `PROMPT-werk.txt` | 3 | `--format werk --payload sound` |
| control | `crate-nc-v1.fbx` | `PROMPT-fbx.txt` | 3 | `--format fbx --payload texture` |
| control | `crate-nc-v1.gltf` + `.bin` + `crate_diffuse.png` | `PROMPT-gltf.txt` | 3 | `--format gltf --payload texture` |
| control | `crate-nc-v1.usdz` | `PROMPT-usdz.txt` | 3 | `--format usdz --payload texture` |

- Agent: claude CLI only (D5), through `run_nc_trials.sh`, with the sealed config `D:/gauntlet-sealed/config`.
- Order: interleaved, werk, fbx, gltf, usdz, three times (12 trials).
- Each workspace holds the fixture file(s) and `PROMPT.txt` only, and passes the echo check before the agent starts.

## 6. Grading criteria (plan section 3, as implemented in `grade_nc.py`)

| clause | graded how |
|---|---|
| C1 open | The agent's program exits 0 in a clean re-run (`--rerun`) and its stdout names at least 2 known structure entries (R10). Else NEEDS-HUMAN-REVIEW. |
| C2 list with meanings | Human ruling from the excerpted evidence. |
| C3 verify integrity | Human ruling. The agent must verify what the file declares and report what it could not verify. For FBX and glTF the honest answer ("nothing declared") is C3 = PASS-honest. An invented verification is C3 = FAIL. |
| C4 extract | A file of each required class (mesh + second payload) exists in the run dir. Inputs at their own paths do not count (R4). |
| C5 hash match | Tier 1 sha256 match, or Tier 2 mesh match (exact dump bytes, values in order, or count + bbox for a text dump only, R7). A wrong-hash file named like a payload fails the class (R6). |

| verdict | rule |
|---|---|
| PASS | C1 to C5 all pass (C3 = PASS-honest allowed). |
| PARTIAL | At least one graded artifact is exact, but not all clauses pass. |
| FAIL | The program does not run clean, or no graded artifact matches. |
| PENDING | Not final: auto clauses pass, a human ruling or the re-run is missing. |

Primary endpoints, both fixed now: (a) PASS rate per format, (b) the verifiable-integrity fraction per format (R8, R14).

Integrity each file declares (fixed, plan 1.3):

| format | declares |
|---|---|
| werk | sha256 per file, zip CRC-32, spec_sha256, input_hash, Ed25519 chain |
| FBX | nothing |
| glTF | nothing (structural consistency only) |
| USDZ | zip CRC-32 per entry |

Rulings R1 to R17 and the known limits F2, F3 are in `README.md` section 4. They are part of this pre-registration.

## 7. Instrument check before the freeze

50 of 50 dry-run checks as expected on the frozen fixtures (`dryrun/SUMMARY.txt`, `dryrun/fbx/SUMMARY.txt`, `dryrun/usdz/SUMMARY.txt`). `make_prompts.py --check`: 8 of 8 identical. Runner dry test with a stub claude: all paths as expected (`dryrun/RUNNER-STUBTEST.txt`).

## Amendments

None.
