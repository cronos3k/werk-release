# NUMBERS.md — every number in the paper, traced to its recorded source

Stage 8 companion document. **Rule: no number appears in `paper/PAPER.md` or
`paper/werk-paper.tex` that does not have a row here.** A row names the value, the
file it was recorded in, and the section of that file.

Source abbreviations:

| key | file |
|---|---|
| **H** | `F:\werk\HANDOVER.md` |
| **R** | `F:\werk\ROADMAP.md` |
| **G** | `F:\werk\gauntlet\RESULTS.md` |
| **M** | `F:\werk\MANIFESTO.md` |
| **S** | `F:\werk\spec\SPEC.md` |
| **P8** | measured during Stage 8 itself, by re-opening the shipped fixtures (§ "Verification pass at writing time"); the script is inline in this document |

---

## 1. Abstract

| Claim in paper | Value | Source |
|---|---|---|
| round 1 success | 4 / 4 | G "run 1 → Headline"; H "Stage 4 results"; R Stage 4 |
| round 1 times | 486 / 519 / 755 / 806 s | G "run 1 → Per agent" (one heading per agent) |
| round 1 median | 637 s | G "run 1 → Headline" |
| bundled loaders used to learn the format | 0 / 4 | G "run 1 → Headline" |
| spec bugs, round 1 | 12 | G "run 1 → The stumbles, deduplicated" |
| round 2 success | 2 / 2 | G "run 2 → Headline"; R Stage 9 |
| descriptor recomputed bit-exactly | 0.000e+00, tol 1e-6 | G "run 2 → Agent 1 — Python" (verbatim output block) |
| Ed25519 built from embedded mini-spec / declined | Python `signed-and-valid`, Rust `signature-unverified` | G "run 2 → Headline" + "Agent 2 — Rust" |
| reference core gate | 10/10 | H "Stage 2 results → Gate measurement" |
| engine cooked-tier load | 3.7× | H "Stage 5 results → 3. Load time" |
| Blender gate | 16/16 | H "Stage 11 results → Gate measurement" |
| Blender rig round trip | 8.4e-08 rad | H "Stage 11 results → Gate measurement" (`8.43e-08` in the clause detail) |
| Unreal gate | 16/16, pixel-identical | H "Stage 10B results → Gate A" |
| pipeline gate | 19/19, 78/78 | H "Stage 3 Part B results → Gate measurement" |
| CDC dedup / boundary stability | 1.4524×, 94.7 % | H "Stage 7 CDC results → Gate measurement" |

## 2. Design section

| Claim | Value | Source |
|---|---|---|
| the twelve laws (Table 1) | all twelve, paraphrased | M "The Laws" §§1–12 |
| store-mode default and its reason (~100 lines without inflate) | — | S §1 "Compression: store by default" |
| three self-description layers | SPEC.md / schemas / layout grammars | M law 2; S §1 tree |
| what nobody needed externally (zip, CRC-32, SHA-256, WAV, GLB, PNG, JSON, UTF-8, manifest structure, node graph, edge semantics, version rules, three signature states, refusal scopes, exit statuses) | — | G "run 1 → What nobody stumbled on" |
| refusal scopes value/node/container; exit 0/1/2 | — | H "Stage 1 decisions 17–24", decision 23 (S-6); S §10.1 |
| `measured`/`inferred` requires `input_hash` + ordered `input_files`, schema-enforced | — | H "Stage 1 decisions", decision 11 |
| two adapters independently rejected for stamping `measured` | Blender, Unreal | H "Stage 11 results → Decisions", item 2; H "Stage 10B results → Decisions", item 4 |
| 78/78 input_hash recomputation | 78 | H "Stage 3 Part B results → Gate measurement" |
| three signature states + fourth token `unverified` | — | M law 7; H decision 24 (S-7) |
| payload corruption keeps signature valid; manifest corruption does not | — | H "Stage 2 results → 2. Damage gauntlet"; G "run 1 → Damage, unprompted" |
| `core.recipe` / `core.disclosure` / no enforcement | — | H "Stage 9 results → What landed" and "Design decisions" (`jurisdiction_note`) |
| D-REC-1, the one hermeticity exception (media in, weights by hash) | — | H "Stage 9 results → Design decisions", D-REC-1 |

## 3. Method

| Claim | Value | Source |
|---|---|---|
| the task sentence, verbatim | — | G "run 1 → Setup" (quoted block) |
| isolation rules | — | G "run 1 → Setup"; G "run 2 → Setup" |
| round 2 extended task sentence | — | G "run 2 → Setup" (quoted block) |
| three recorded deviations | — | G "run 1 → Setup → Deviations from the brief" 1–3 |
| C++ in the brief, not run; covered as consumer | — | G "run 1 → Setup", closing paragraph |

## 4. Round 1

| Claim | Value | Source |
|---|---|---|
| fixture as handed out | sha256 `93d1657948dda0ef…`, 13 262 619 B, 157 entries, 36 nodes, 155 declared files | G "run 1 → Setup" |
| fixture content: 272 v / 408 t | — | H "Stage 3 Part A results" table |
| minimal sphere r = 0.8893 m, Welzl, checked against all 272 points | — | H "Stage 3 Part A results" table |
| 20 effects (17 interaction + 3 ambience), 73 WAVs | — | H "Stage 3 Part A results" table |
| 6 orbit views + 10 segment crops as `x.*` | — | H "Stage 3 Part A results" table |
| preview prefix 723 944 B = 5.46 % | — | H "Stage 3 Part A results" table; R Stage 3 |
| headline table (Table 2) | all rows | G "run 1 → Headline" |
| mean 642 s, range 486–806 s | — | G "run 1 → Headline" |
| 38 stumbles total | 10 + 8 + 9 + 11 | G "run 1 → Per agent" (per-agent counts); total in Headline |
| 3/4 wanted external, same two gaps (Ed25519 internals, SHA-512) | — | G "run 1 → Headline" |
| Python: hand-rolled zip, SHA-256 from structural facts, ~60-line Ed25519, wrong-message check | — | G "run 1 → Python" |
| Python: preview prefix recomputed 724 832 == 724 832; 25/25 input_hash; 12 report codes | — | G "run 1 → Python" (Coverage beyond the task) |
| JS: no `werk_read.js` exists; 40-line zip lister before spec; SPKI DER prefix from memory | — | G "run 1 → JavaScript" |
| Rust: derived SHA-2 constants at run time; never read `werk_read.rs`; declared narrowness | — | G "run 1 → Rust" |
| C: 56 KB single-file C99; derived all constants; only agent to build present-and-invalid | — | G "run 1 → C" |
| damage table (Table 4) | all rows | G "run 1 → Damage, unprompted" |
| three of four produced three distinct signature states | — | G "run 1 → Damage, unprompted", closing |

## 5. Round 2

| Claim | Value | Source |
|---|---|---|
| profile `image/1`, 15 nodes | — | G "run 2 → Setup"; H "Stage 9 results → Gate measurement" |
| two builds: `a59a5083…` 9 969 937 B / `2fdfde30…` 9 973 037 B, 63 entries each | — | G "run 2 → Setup" (table) |
| three audited candidates, two rejections | — | H "Stage 9 results → The fixture, and why this image" |
| headline table (Table 5) | all rows | G "run 2 → Headline" |
| descriptor recomputation, both components 0.000e+00 vs 1e-6 | — | G "run 2 → Agent 1 — Python" (verbatim block) |
| builder's own worst drift 1.381e-08 | — | H "Stage 9 results → Gate measurement" table |
| Rust agent palette cross-check, all 8 to 1e-6 incl. hex | — | G "run 2 → Agent 2 — Rust", "The envelope" |
| Python 23 checks / 0 failed; Rust 16 passed / 0 failed / 1 note | — | G "run 2 → Agent 1", "Agent 2" |
| 7/7 input_hash recomputed | — | G "run 2 → Agent 1" table; "Agent 2 → Verification" |
| preview prefix 998 658 == 998 658 over 58 entries | — | G "run 2 → Agent 1" table |
| Rust build's 1 001 758 / 9 930 116 / 63 entries / 61 distinct files | — | G "run 2 → Agent 2 — Rust", "Every number it reported checks out" |
| 62 of 63 entries matched entry_order (the miss = S-28) | — | G "run 2 → Agent 1" table |
| payload_origin 704 computed = 704 declared; origin+size = 1120 = file length | — | G "run 2 → Agent 1" and "Agent 2 → The envelope" |
| vector L2 norm 1.000000006 | — | G "run 2 → Agent 2 — Rust", "The envelope" |
| palette weights sum 0.995117 (S-24 found from outside) | — | G "run 2 → Agent 1"; H "Stage 9 results → Spec findings", S-24 |
| prompt v1→v2 1 716 → 1 816 | — | G "run 2 → Agent 1", "Recipe and disclosure" |
| disclosure quotation | verbatim | G "run 2 → Agent 1", block quote |
| dev-key / C2PA-stub quotations | verbatim | G "run 2 → Agent 1", closing paragraph |
| militaria / DESCRIPTIVE-grade quotation | verbatim | G "run 2 → Agent 2 — Rust", "One observation that is not a spec bug" |

## 6. Spec bugs

| Claim | Value | Source |
|---|---|---|
| Table 6 (S-10…S-21, seen-by, status) | all rows | G "run 1 → The stumbles, deduplicated" (table) |
| S-10: 0 of 25 hashes right; brute-forced ten candidates; found in a generator script | — | G "run 1 → S-10 is the finding of the run"; H "Stage 4 results → S-10" |
| spec/README.md question 6 | verbatim | G "run 1 → S-10 …"; H "Stage 4 results → S-10" |
| S-10 ruling (absent = `{}`, two bytes appended) | — | H "Stage 4 results", item 10 |
| S-10 fix verified by a later independent implementation with no detour | — | H "Stage 5 results → Spec findings", "Confirmation, not a finding" |
| S-12 ruling contents (p, d, L, sqrt(-1), base point, group law, canonical-S, both verification equations, SPKI DER prefix) | — | H "Stage 4 results", item 12 |
| ledger composition (S-1…S-8, S-9, 12, S6-n ×5, S3-n ×8, S10-n ×6, S7-n ×2, S-29, S-24…S-28, S-30 open) | — | H "Stage 2 results → Spec findings"; "Stage 6 results → Spec findings"; "Stage 3 Part B → Findings"; "Stage 10 results → Spec findings"; "Stage 10B results → Spec and platform findings"; "Stage 7 CDC results → Findings"; "Stage 11 results → Spec finding"; "Stage 9 results → Spec findings"; "Gauntlet round 2 → S-30" |
| three stages collided on S-22, two on S-23; earliest commit keeps the number | — | H "Finding numbers, reconciled" |

## 7. Ecosystem

### 7.1 Reference core

| Claim | Value | Source |
|---|---|---|
| gate 10 PASS / 0 FAIL / 0 SKIP | — | H "Stage 2 results → Gate measurement" |
| fixture #1: 413 741 B, 28 entries, 15 nodes, 26 declared files | — | H "Stage 2 results → Conformance fixture #1" |
| three faces agree: 15 nodes, 14 alive / 1 skipped, same manifest sha256, one 879 616-byte DLL | — | H "Stage 2 results → 3. One .werk, three faces, one DLL" |
| round trip proven three ways; fixed DOS timestamp | — | H "Stage 2 results → 1. Round-trip byte-identity" |
| four damage scenarios and their exact reports | — | H "Stage 2 results → 2. Damage gauntlet" (table) |
| three bootstrap readers, 26/26 files over 15 nodes, toolchains | — | H "Stage 2 results → 4. Each bootstrap reader parses the fixture standalone" (table) |
| WKRP byte-identical to the spec's own example: 560 B, sha256 `6c2c44d5…` | — | H "Stage 2 results → The one measurement that proves the code and the spec agree" |

### 7.2 CUB engine

| Claim | Value | Source |
|---|---|---|
| native container implementation, not the C ABI | — | H "Stage 5 results → The reader" |
| reports `unverified`, never `signed-and-valid` | — | H "Stage 5 results → The reader" |
| zero-cook load: exit 0, 36 nodes, 34 live, 0 dead, 2 skipped, 139 files, 12 865 205 bytes, 272 v / 408 t, r = 0.889269 m, 20 audio nodes | — | H "Stage 5 results → 1. Zero-cook load" (table) |
| damage agreement with werk-core: 37 / 33 live / 1 dead / 1 hash-mismatch / 3 unknown-type | — | H "Stage 5 results → 2. Damage gauntlet, independently reproduced" (table) |
| load times 0.043/0.022, 88.95/24.00, 145.51/21.69 ms; 1.9× / 3.7× / 6.7× | — | H "Stage 5 results → 3. Load time" (table) |
| 3-material caveat: 1 005 360 vs 502 681 vertices | — | H "Stage 5 results → 3. Load time", paragraph after the table |
| 65 ms saved per million-triangle mesh | — | H "Stage 5 results → 3. Load time", final paragraph |
| exported package read by `werk_read.py`: 9 nodes, 8 live, 0 dead, 1 skipped | — | H "Stage 5 results → 7. Cross-validated" |
| manifest validates with 0 errors | — | H "Stage 5 results → 7. Cross-validated" |
| two engine bugs (zero-bounds default; AABB-diagonal radius) | — | H "Stage 5 results → 6. Two CUB bugs" |

### 7.3 Blender

| Claim | Value | Source |
|---|---|---|
| Blender 4.2.1 LTS, found not downloaded, `--background --factory-startup` | — | H "Stage 11 results", preamble |
| 16 PASS, 0 FAIL, 0 SKIP in 3.5 s | — | H "Stage 11 results → Gate measurement" |
| Table 10 rows (import clean/damaged, round trip, exported package, two verifiers, determinism, rig, textures) | — | H "Stage 11 results → The four briefed clauses" and "→ Three clauses the brief did not ask for" |
| 624 539 B, 50 entries, 8 nodes, 49 files | — | H "Stage 11 results → 3. Round trip" (table) |
| rig: worst rest-head 0 m, worst posed 8.43e-08 rad, recomposition 5.96e-08 vs 1e-5 | — | H "Stage 11 results → Three clauses…", rig bullet |
| the five silent bugs + the sixth in the gate itself | — | H "Stage 11 results → The five bugs the gate caught" |

### 7.4 Unreal

| Claim | Value | Source |
|---|---|---|
| UE 5.7 + MSVC 2022, plugin compiled | — | H "Stage 10 results → Which gate ran" and "→ Gate A" |
| import: exit 0, 36 nodes, 25 imported, 11 skipped, 0 refused, 22 assets, 164 files verified, `unverified`, 0.382 s | — | H "Stage 10 results → Gate A" |
| damaged: exit 1, 1 refused, 21 assets | — | H "Stage 10 results → Gate A" |
| round trip 272/408 in and out, identical AABB, WAV byte-identical | — | H "Stage 10 results → Round-trip" (table) |
| three readers agree (own core 9 PASS; `werk_read.py` matching manifest sha256; jsonschema 0 errors) | — | H "Stage 10 results → Three independent readers agree" |
| Stage 10B gate 16 PASS, 0 FAIL; three textures pixel-identical; PNG bytes identical for 0 of 3 | — | H "Stage 10B results → Gate A" and "→ The texture round trip" |
| engine-free core gate 10 PASS, 0 FAIL, 0.310 s | — | H "Stage 10 results → Gate B" |
| S10-6: every UV at (0,0), 730 verts / 408 tris / three textures / three slots / three switches all reported correct | — | H "Stage 10B results → Spec and platform findings", S10-6 |
| "a report is not a measurement" | verbatim | H "Stage 10B results", S10-6 closing |
| two more bugs of the same family; the sun-direction non-bug | — | H "Stage 10B results → Two more bugs of the same family" |

### 7.5 Retarget

| Claim | Value | Source |
|---|---|---|
| 33 PASS, 0 FAIL, 0 SKIP in 29.2 s | — | H "Stage 6 results", gate block; R Stage 6 |
| three rigs: 19 / 68 / 31 bones; scales 1.35696 / 0.99052 / 0.06152; round trips 5.157e-08 / 5.217e-08 / 8.803e-08 rad | — | H "Stage 6 results → The three retargets" (table) |
| declared tolerance 1.0e-4 rad, quoted from `animclip.layout.txt` | — | H "Stage 6 results → The three retargets", paragraph after the table |
| hips 0.837–1.092 m above floor; canonical rest hip 0.98 m; lowest toe −0.050 / −0.016 / +0.034 m | — | H "Stage 6 results → The scale column is the claim" |
| six cross-rig transits, 5.2e-08 to 8.8e-08 rad, named uncrossable bones | — | H "Stage 6 results → Cross-rig transit" (table) |
| frame-invariance spreads 3.03e-14 / 7.60e-14 rad; interposed 0.2217 rad | — | H "Stage 6 results → Why one pose is enough" (table) |
| S6-3 filed | — | H "Stage 6 results → Spec findings", S6-3 |

### 7.6 Enrichment pipeline

| Claim | Value | Source |
|---|---|---|
| 19 PASS, 0 FAIL, 0 WARN | — | H "Stage 3 Part B results", header; R Stage 3 |
| thirteen producers, named | — | H "Stage 3 Part B results → What it is" |
| Table 12 rows (bytes, nodes/files, derived hashes, core result, producers, wall) | — | R Stage 3 table + H "Stage 3 Part B results → Gate measurement" table |
| 108 node versions, 78 stamped derived, 78/78 recomputed | — | H "Stage 3 Part B results → Gate measurement", paragraph after the table |
| verified against the schemas the package itself carries | — | same |
| two `--reproducible` runs byte-identical | — | H "Stage 3 Part B results → Reproducibility, measured" |
| the `example` asset: 15 ok / 1 failed, exact exception, 33 nodes, 0 dead | — | H "Stage 3 Part B results → Per-stage timings", `example` paragraph |
| lantern 25.66 m, 130 tonnes, not rescaled | — | H "Stage 3 Part B results → One more thing the pipeline refuses to do" |

### 7.7 Store

| Claim | Value | Source |
|---|---|---|
| zero third-party dependencies including crypto | — | H "Stage 7 results", "What landed" |
| corpus: 43 MB photogrammetry GLB, JPEG set, six view PNGs, sixteen WAVs | — | H "Stage 7 results → Corpus" |
| dedup 1.9970×; v2 marginal 0.2404 %; sync moved 0.27 % (99.73 % did not) | — | H "Stage 7 results → Corpus" (table) |
| materialization identical to originals (whole-tree sha256 vs sources) | — | H "Stage 7 results → Gate wording, checked literally" |
| CDC params 64 KiB / 256 KiB / 1 MiB; gear table derived from SHA-256 | — | H "Stage 7 CDC results", "What landed" |
| Table 13: 31.79 MiB logical; 26.72 → 21.89 MiB; 1.1897× → 1.4524×; 5.15 → 0.31 MiB | — | H "Stage 7 CDC results → Gate measurement" (table) |
| 1 of 19 chunks changed, 18/19 = 94.7 %; sync moved 3.63 % | — | H "Stage 7 CDC results → Gate measurement" (second table) |
| damaged fixture refused in 1.43 s, nothing entered as a ref | — | H "Stage 7 CDC results → Gate measurement" (second table, last row) |
| test that corrupts the store and requires failure | — | H "Stage 7 results → Gate wording, checked literally" |

## 8. Verification pass at writing time (P8)

Measured on 2026-08-08 by opening each shipped `.werk` with the Python standard
library only and counting distinct paths reachable from
`nodes[].versions[].files[]`:

```python
import zipfile, json, os, hashlib
for p in ['fixtures/crate-v1.werk', 'fixtures/ista-varun-v1.werk',
          'fixtures/crate-tex-v1.werk', 'fixtures/humanoid-retarget-v1.werk',
          'fixtures/crate-v1-damaged.werk']:
    z = zipfile.ZipFile(p); m = json.loads(z.read('MANIFEST.json'))
    files = {f['path'] for n in m['nodes'] for v in n['versions'] for f in v['files']}
    print(p, os.path.getsize(p), len(z.namelist()), len(m['nodes']), len(files),
          m['container'].get('preview_prefix_bytes'))
```

| fixture | bytes | sha256[:16] | entries | nodes | distinct files | manifest B | preview prefix |
|---|---|---|---|---|---|---|---|
| `crate-v1.werk` | 13 430 904 | `0e45deb97edc15dc` | 166 | 36 | 164 | 81 216 | 892 407 |
| `crate-v1-damaged.werk` | 13 432 056 | `7892729533d6177d` | — | — | — | — | — |
| `ista-varun-v1.werk` | 9 973 037 | `2fdfde3049f1c679` | 63 | 15 | 61 | 33 332 | 1 001 758 |
| `crate-tex-v1.werk` | 696 545 | `8a6488bd5de7abbc` | 53 | 11 | 52 | 22 269 | 604 527 |
| `humanoid-retarget-v1.werk` | 1 251 512 | `b0f361a1f24bd2d7` | 57 | 8 | 55 | 21 858 | 966 124 |

Values confirmed against the record: the image fixture's declared
`preview_prefix_bytes` 1 001 758 and `total_size_bytes` 9 930 116 (G run 2, Agent
2); the retarget fixture's 55 declared files, 21 858-byte manifest and 966 124-byte
preview prefix (H "Stage 6 results → The fixture"); the textured fixture's
696 545 bytes, sha256 `8a6488bd…`, 53 entries, 11 nodes, 52 files, preview prefix
604 527 (H "Stage 10B results → The textured fixture"); `crate-v1-damaged.werk` at
13 432 056 bytes and `crate-v1.werk` at 13 430 904 bytes with sha256 `0e45deb9…`
(H "Stage 10B results → Gate A", fixture header block).

Disagreements with the record — reported in the paper as findings, and in
`paper/STAGE8-RESULTS.md` in full:

| # | disagreement | recorded in |
|---|---|---|
| 1 | `crate-v1.werk` recorded at 13 430 904 B with sha256 `8cace0b9…` **and** at 13 430 904 B with sha256 `0e45deb9…` | H "Stage 10 results → One fixture caveat" / "→ Gate B" vs. H "Stage 10B results → Gate A" |
| 2 | `humanoid-retarget-v1.werk` recorded at 1 251 514 B, sha256 `c0448cc4…`; on disk 1 251 512 B, sha256 `b0f361a1…` | H "Stage 6 results → The fixture" |
| 3 | profile-2 gate records the three bootstrap readers at 60/60 files; the shipped package declares 61 | H "Stage 9 results → Gate measurement" vs. G run 2 Agent 2 and P8 |

## 9. Numbers deliberately NOT used in the paper

Recorded here so their absence is a decision rather than an oversight.

| number | why not used |
|---|---|
| `crate-v1.werk` "12.79 MiB, 166 files" (H "Stage 7 CDC results → Corpus") | 166 is the zip **entry** count, not the declared-file count (P8: 166 entries, 164 files); and 12.79 MiB matches none of the recorded byte counts exactly. Filed as a finding, not quoted. |
| Blender gate's "crate-v1 13 427 826 B, damaged 13 428 978 B" (H "Stage 11 results → Gate measurement") | a third build state of the same fixture; the paper quotes only the as-handed-out build (round 1) and the as-shipped build (P8). |
| Stage 10's early standalone run "155 files, sha256 `acabb461…`, 13 279 385 B" | superseded in the same section by the re-measurement; the source already labels it superseded. |
| Stage 3A "preview prefix 723 944 (5.46 %)" vs the Python agent's recomputed 724 832 | both are quoted, each attributed to its own build, and the paper never presents them as the same measurement. |
| store synthetic-pair control 1.485× (H "Stage 7 results → Corpus") | the source itself says the real-corpus number is the one that counts. |
| `x.cub` 6.7× three-material row | quoted **only** with its caveat, never as the headline, per H's own instruction. |
| imposter IoU, LOD screen-space errors, collider Hausdorff per asset | not load-bearing for any claim the paper makes; the Hausdorff range 0.157–2.002 m is quoted once, in Limitations, from H "Stage 3 Part B → Per-stage timings" (0.1566 m) and (2.0019 m). |
