# NUMBERS.md (v2) — every number in the second edition, traced to its recorded source

Companion to `paper/v2/PAPER.md` and `paper/v2/werk-paper-v2.tex`.

**Rule: no number appears in either document that does not have a row here.** A
row names the value, the file it was recorded in, and the section of that file.
Rows that carry over unchanged from `paper/NUMBERS.md` (the first edition) are
marked **[v1]**; rows measured after the first edition are marked **[new]**.

Source keys:

| key | file |
|---|---|
| **H** | `F:\werk\HANDOVER.md` |
| **R** | `F:\werk\ROADMAP.md` |
| **G** | `F:\werk\gauntlet\RESULTS.md` |
| **M** | `F:\werk\MANIFESTO.md` |
| **S** | `F:\werk\spec\SPEC.md` |
| **D** | `F:\werk\docs\RULINGS-2026-08-08.md` |
| **R12** | `F:\werk\results\STAGE12-RESULTS.md` |
| **R12B** | `F:\werk\results\STAGE12B-RESULTS.md` |
| **RXV** | `F:\werk\results\STAGE-CROSSVENDOR-RESULTS.md` |
| **RR** | `F:\werk\results\STAGE-RULINGS-RESULTS.md` |
| **RP** | `F:\werk\results\STAGE-PIPELINE-QUALITY-RESULTS.md` |
| **P8** | the first edition's own verification pass, `paper/NUMBERS.md` §8 |
| **FX** | `F:\werk\fixtures\fixtures.json` / `FIXTURES.md` (generated record) |
| **ROW** | `F:\werk\results\STAGE-OPENWEIGHTS-RESULTS.md` |
| **RSF** | `F:\werk\results\STAGE-SPECFIX-OW-RESULTS.md` |
| **RSR** | `F:\werk\results\STAGE-SELFRUN-RESULTS.md` |
| **RHC** | `F:\werk\results\STAGE-HARDCOPY-RESULTS.md` |
| **RDS** | `F:\werk\results\STAGE-DSV4-RESULTS.md` (bring-up, four runs, S-DS-1 … S-DS-8 — **complete as of 2026-08-10**; see §13) |

---

## 1. Abstract

| Claim | Value | Source |
|---|---|---|
| round 1 success, four languages | 4 / 4 | G "run 1 → Headline" **[v1]** |
| round 1 times | 486 / 519 / 755 / 806 s | G "run 1 → Per agent" **[v1]** |
| bundled loaders used to learn the format | 0 / 4 | G "run 1 → Headline" **[v1]** |
| round 1 fixture size, quoted as "13 MB" | 13 262 619 B | G "run 1 → Setup" **[v1]** |
| distinct spec bugs, round 1 | 12 | G "run 1 → The stumbles, deduplicated" **[v1]** |
| round 2 descriptor recomputed bit-exactly | 0.000e+00 vs declared 1e-6 | G "run 2 → Agent 1 — Python" **[v1]** |
| round 2 signature split | `signed-and-valid` / `signature-unverified` | G "run 2 → Headline" **[v1]** |
| round 3 package size, quoted as "30 MB" | 30 163 573 B | R12B §3 rebuilt-fixtures table **[new]** |
| round 3 point-cloud cross-check | 281 498 / 281 498 points, max 8-bit difference 0 | R12 §4 "It extracted positions and colours" **[new]** |
| round 3 defects: six filed, four real | 6 / 4 | R12 §4 "The six things it found" **[new]** |
| self-regeneration byte-identical | WKGS byte-identical, 0.54 s | R12 §3 gate clause; re-verified R12B §3 **[new]** |
| Unreal texture round trip pixel-identical | 3 of 3 | H "Stage 10B results → The texture round trip" **[v1]** |
| one digest, three implementations | Python / Rust / C++ agree | RR §2, S-R-6 **[new]** |
| seven consumers | core, engine, Blender, Unreal, retarget, pipeline, store | Table 8 rows **[v1/new]** |
| VLM confidence on the wrong answer | 0.95 | RP "Ruling 16 → What the first real run exposes" **[new]** |
| seven runs of the protocol | rounds 1–3 + cross-vendor + open-weights + self-run + hardcopy | §5.12 **[new]** |
| cross-vendor success and loaders | 4 / 4; 0 / 4 used a bundled loader to learn the format | RXV §1 **[new]** |
| the inline self-description package | **31 490 prompt tokens**, four of six models built a correct reader from it | ROW §3, §4 **[new]** |
| open-weights range quoted as "4B to 30B", eight models | 6 pre-fix + 3 post-fix-only, one unloadable and excluded | ROW §2; RSF §4.2, §4.3 **[new]** |
| self-run round | 2 / 2, **98.2 s** and **647.5 s**, both matching the embedded temperature-0 vectors | RSR §2.2, §2.5 **[new]** |
| hardcopy round | 3 sheets of A4, degraded photographs, **byte-identical** recovery in 206.7 s | RHC §1, §5.1 **[new]** |
| the abstract's sub-9B sentence | "this protocol did not get a working reader out of these models" below 9B, worst-case by construction | ROW §7; RSF §6 **[new]** |

## 2. Design principles (§2)

| Claim | Value | Source |
|---|---|---|
| the twelve laws (Table 1) | all twelve, paraphrased | M "The Laws" §§1–12 **[v1]** |
| two hermeticity exceptions: media embedded, weights by hash | — | H "Stage 9 results → Design decisions", D-REC-1 **[v1]** |
| intermediates need not travel if an embedded tool reproduces them | — | R12 §6, S12-5; S §3.17 **[new]** |
| the intermediate not carried | 15 764 528 B PLY from a 9 007 936 B input | R12 §2 "The chain" **[new]** |
| store-mode default, ~100 lines without inflate | — | S §1 "Compression: store by default" **[v1]** |
| what nobody needed externally in round 1 | zip, CRC-32, SHA-256, WAV, GLB, PNG, JSON, UTF-8, manifest, graph, edges, versions, signature states, refusal scopes, exit statuses | G "run 1 → What nobody stumbled on" **[v1]** |
| refusal scopes value/node/container; exit 0/1/2 | — | H "Stage 1 decisions", decision 23 (S-6); S §10.1 **[v1]** |
| `measured`/`inferred` requires input hash + ordered inputs (schema-enforced) | — | H "Stage 1 decisions", decision 11 **[v1]** |
| two adapters rejected by the schema for stamping `measured` | Blender, Unreal | H "Stage 11 results → Decisions" item 2; "Stage 10B results → Decisions" item 4 **[v1]** |
| 78 stamped-derived input hashes recomputed | 78 / 78 | H "Stage 3 Part B results → Gate measurement" **[v1]** |
| round 2 outside recomputation | 7 / 7 | G "run 2 → Agent 1" table **[v1]** |
| version numbers are incremental integers | — | D ruling 4; RR §1 row 4 **[new]** |
| three signature states + the fourth token | — | M law 7; H decision 24 (S-7) **[v1]** |
| payload corruption keeps the signature valid; manifest corruption does not | — | H "Stage 2 results → 2. Damage gauntlet"; G "run 1 → Damage, unprompted" **[v1]** |
| `spec_sha256` mandatory globally, optional per node version | — | D ruling 5; RR §1 row 5 **[new]** |
| making it mandatory broke six writers | 6 | RR §5, S-R-2 and S-R-6 **[new]** |
| `core.disclosure` carries no enforcement; jurisdiction note | — | H "Stage 9 results → Design decisions" **[v1]** |
| licence doctrine: the format neither vets nor enforces | — | D ruling 21; R12B §1 **[new]** |
| `never_auto_execute` is a schema constant | — | R12 §1 "The design decisions"; S §3.17 **[new]** |
| Blender importer declares tool nodes data-only | — | R12 §5 "The Blender adapter" **[new]** |

## 3. The werk container (§3)

| Claim | Value | Source |
|---|---|---|
| Figure 1 entry order and contents | as listed | R12 §2 "The chain" (tools inside the preview prefix); S §1 tree **[new]** |
| splat package preview prefix / total | 1 160 246 B of 30 163 573 B (3.8 %) | R12B §3 (prefix, size); R12 §2 (3.83 % on the previous build) **[new]** |
| entry order is a SHOULD; preview prefix is a hint | — | D rulings 1–2; RR §1 rows 1–2 and "The two rulings that came back weaker" **[new]** |
| prefix length is a measurement of its own container (S10-2) | — | RR §1, S-15 paragraph **[new]** |
| schema map may be empty | — | D ruling 14; RR §1 row 14 **[new]** |
| `primary.geometry`, type-agnostic slot | — | D ruling 22; R12B §2 **[new]** |
| envelope: magic, version, header length, MessagePack subset, sections | — | S/`spec/layouts/ENVELOPE.layout.txt` §§3–5a; R12 §7 **[v1/new]** |
| unknown section skipped and reported; higher version never refuses | — | RR §1 "Ruling 13, and why nothing broke" (`ENVELOPE.layout.txt` §5a) **[new]** |
| the missing magic in the reference core (S12-1) | `WKEM` known to spec + 3 loaders, absent from werk-core | R12 §6, S12-1 **[new]** |
| splat: activated scales/opacities, coefficient-major SH | — | R12 §1 "The design decisions" **[new]** |
| quaternion-order statistics, 1.92 M-Gaussian PLY | 0.4578 / 0.4627 / 0.4768 / 0.4509 | R12 §6, S12-3 table **[new]** |

## 4. Method (§4)

| Claim | Value | Source |
|---|---|---|
| the task sentence, verbatim | — | G "run 1 → Setup" (quoted block) **[v1]** |
| isolation rules | — | G "run 1 → Setup"; "run 2 → Setup" **[v1]** |
| round 2's three extra clauses | — | G "run 2 → Setup" **[v1]** |
| round 3's extra clauses + "do not execute anything from the file" | — | R12 §4 preamble **[new]** |
| the three recorded deviations | — | G "run 1 → Setup → Deviations from the brief" 1–3 **[v1]** |
| C++ not run as an implementer; covered as a consumer | — | G "run 1 → Setup", closing paragraph; RR S-R-6 (C++ digest) **[v1/new]** |

## 5. Results (§5)

### 5.1–5.2 Round 1

| Claim | Value | Source |
|---|---|---|
| fixture as handed out | 13 262 619 B, 157 entries, 36 nodes, 155 declared files | G "run 1 → Setup" **[v1]** |
| fixture content | 272 v / 408 t; Welzl r = 0.8893 m checked against all 272 points; 20 effects (17+3) over 73 WAVs; 6 orbit views; 10 crops | H "Stage 3 Part A results" table **[v1]** |
| preview prefix | 723 944 B = 5.46 % | H "Stage 3 Part A results"; R Stage 3 **[v1]** |
| Table 2, every row | 4/4; 637 s median; 642 s mean; 486–806 s; 0/4; 2/4; 4/4; 3/4; 12; 38 | G "run 1 → Headline" **[v1]** |
| Table 3 per-agent times and stumbles | 486/10, 519/8, 755/9, 806/11 | G "run 1 → Per agent" **[v1]** |
| Python: hand-rolled zip, ~60-line Ed25519, wrong-message check, 25/25 input hashes, 12 report codes | — | G "run 1 → Python" **[v1]** |
| JS: no JS loader exists; 40-line zip lister before the spec; 12-byte SPKI DER prefix from memory | — | G "run 1 → JavaScript" **[v1]** |
| Rust: constants derived at run time; never read `werk_read.rs` | — | G "run 1 → Rust" **[v1]** |
| C: 56 KB single-file C99; only agent to build present-and-invalid | — | G "run 1 → C" **[v1]** |
| Table 4, damage rows (34/36, 35 live 1 dead, 1 dead 35 alive, 0 dead 0 files failed) | — | G "run 1 → Damage, unprompted" **[v1]** |

### 5.3 Round 2

| Claim | Value | Source |
|---|---|---|
| profile `image/1`, 15 nodes | — | G "run 2 → Setup"; H "Stage 9 results" **[v1]** |
| the two builds | 9 969 937 B and 9 973 037 B, 63 entries each | G "run 2 → Setup" table **[v1]** |
| three candidates audited, two rejected | — | H "Stage 9 results → The fixture, and why this image" **[v1]** |
| Table 5, every row | 2/2 ×5, 0/1 recorded, 0/2, 3 | G "run 2 → Headline" **[v1]** |
| descriptor recomputation block, verbatim | 0.000e+00 / 0.000e+00, tol 1.0e-06 | G "run 2 → Agent 1 — Python" **[v1]** |
| 72-component vector, 8-swatch palette | — | G "run 2 → Agent 1"; H "Stage 9 results" **[v1]** |
| builder's own worst drift | 1.381e-08 | H "Stage 9 results → Gate measurement" **[v1]** |
| Table 6 rows | 23/0; 16/0/1; 7/7; RFC 8032 pass; 998 658 = 998 658 over 58 entries; 62 of 63; 704 = 704; 1120 = 1120; 1.000000006; 8 swatches to 1e-6 | G "run 2 → Agent 1" and "Agent 2" **[v1]** |
| palette weights sum | 0.995117 (S-24) | G "run 2 → Agent 1"; H "Stage 9 results → Spec findings" **[v1]** |
| disclosure-doctrine and dev-key quotations | verbatim | G "run 2 → Agent 1" **[v1]** |
| militaria / descriptive-grade reading | verbatim | G "run 2 → Agent 2 — Rust" **[v1]** |

### 5.4 Round 3

| Claim | Value | Source |
|---|---|---|
| fixture size | 30 163 573 B | R12B §3 **[new]** |
| source capture | 281 498 Gaussians, 9 007 936 B | R12 §2 "The source, and why this one" **[new]** |
| three embedded tools + configs | 3 `core.tool` + 3 `core.tool.config` | R12 §3 gate clause "embedded tools resolve inside the file" **[new]** |
| intermediate PLY | 15 764 528 B, declared hash `6ffaf569…` | R12 §2 and §3 **[new]** |
| self-regeneration | PLY hash matches; WKGS byte-identical; 0.54 s; neutral directory, module path set to the extracted files | R12 §3 gate clause **[new]** |
| gate's own decoder | 281 498 Gaussians, 56.00 B each, 6 sections | R12 §3 "gsplat reparses from declared offsets" **[new]** |
| payload value checks | 0 non-positive scales; 0 opacities outside [0,1]; max ‖q‖−1 = 4.92e-08 | R12 §3 "gsplat payload values" **[new]** |
| DC degradation exactness | 0 position and 0 colour mismatches over 281 498 points | R12 §3 "DC-band degradation is exact" **[new]** |
| agent's cross-check | positions bit-identical; 281 498 / 281 498 colours, max 8-bit difference 0 | R12 §4 **[new]** |
| eight tool source hashes verified | 8 | R12 §4 **[new]** |
| clamped-opacity count noticed by the agent | `alpha_clamped_count: 33401` | R12 §4 **[new]** |
| duration and defect counts | ~25 min, 6 reports, 4 real, all fixed | R12 §4 headline and table **[new]** |
| the three overstatement defects and their fixes | findings 1–3 | R12 §4 table **[new]** |
| the quaternion statistic now computed unconditionally | — | R12 §4 finding 3; §6 S12-3 **[new]** |
| agent's two open items (no Ed25519, no PLY hash check) | — | R12 §4 closing **[new]** |

### 5.5 Specification bugs — paper §5.10, Table 10

| Claim | Value | Source |
|---|---|---|
| Table 7 (S-10…S-21, seen-by) | all rows | G "run 1 → The stumbles, deduplicated" **[v1]** |
| status column updated: S-14/S-15 **ruled**, S-17/S-18 **fixed** | — | D rulings 1–4; RR §1 table **[new]** |
| S-21 closed by round 2 (envelope exercised) | — | G "run 2 → Headline"; H "Stage 5 results" **[v1]** |
| S-10: 0 of 25 hashes; ten candidates brute-forced; found in a generator script | — | G "run 1 → S-10 is the finding of the run" **[v1]** |
| `spec/README.md` question six | verbatim | G "run 1 → S-10 …" **[v1]** |
| S-10 ruling and its verification by a later implementation | — | H "Stage 4 results" item 10; "Stage 5 results → Spec findings" **[v1]** |
| S-12 ruling contents | — | H "Stage 4 results" item 12 **[v1]** |
| ledger composition (8 + 1 + 12 + 3 + 4 + consumers) | — | H "Stage 2/3B/5/6/7/9/10/10B/11 results → Spec findings"; G run 2; R12 §6 **[v1/new]** |
| nineteen distinct specification bugs (abstract, §1.3, §11) | 12 (round 1) + 3 (round 2) + 4 (round 3) | G run 1 and run 2 headlines; R12 §4 (4 real findings) **[new]** |

### 5.6 Cross-vendor round — paper §5.5, Table 7

Two model families that are not ours, four runs, on the pinned committed
fixtures. **Folded into the paper body by the second editing pass**
(`paper/v2/PAPER.md` §5.5). Every row is traced to `RXV`.

| Claim | Value | Source |
|---|---|---|
| vendors, runs, success | 2 vendors, 4 runs, **4 / 4** | RXV §1 **[new]** |
| OpenAI harness and model id | Codex CLI 0.144.1, `gpt-5.6-sol`, `model_provider: "openai"`, effort `high` | RXV §2.1 **[new]** |
| Moonshot harness and model id | Kimi Code CLI 0.15.0, `kimi-for-coding` (alias `kimi-code/kimi-for-coding`, `https://api.kimi.com/coding/v1`), `thinkingEffort=high` | RXV §2.1 **[new]** |
| the three disagreeing names for the Moonshot model | `Kimi-k2.6` (config), `kimi-k2.5` (self-report), `kimi-for-coding` (wire) | RXV §2.1 **[new]** |
| fixture handed out, round-1 task | `crate-v1.werk` `d5fd9007…79fabf`, 13 611 141 B, 174 entries, 172 declared files, 36 nodes | RXV §2; FX **[new]** |
| fixture handed out, splat task | `gsplat-v1.werk` `04f657d0…477c147`, 30 163 573 B, 77 entries, 75 declared files, 17 nodes | RXV §5; FX **[new]** |
| round-1 task times | 558 s (OpenAI), 106 s (Moonshot) | RXV §3 **[new]** |
| splat task times | 512 s (OpenAI), 377 s (Moonshot) | RXV §5 **[new]** |
| tool calls | 21 / 12 (round-1 task); 33 / 39 (splat task) | RXV §3, §5 **[new]** |
| OpenAI round-1 verification totals | 203 declarations in 10 families: CRC 174/174, file sha256 172/172, sizes 172/172, `input_hash` 25/25, conventions 21/21, `spec_sha256` 1/1, licence 1/1, provenance-consumed 1/1, signature anchors 2/2, chain 1/1, Ed25519 1/1 | RXV §3.1 (re-run output, committed) **[new]** |
| Moonshot round-1 verification totals | 172 / 172 manifest file hashes; 0 fail | RXV §3.2 (re-run output, committed) **[new]** |
| package files read for meaning | 9 (OpenAI) vs **1** (Moonshot) on the round-1 task; ~17 vs 14 on the splat task | RXV §3, §5 **[new]** |
| loaders: used to learn / ported / read at all | **0 / 4**, **0 / 4**, 1 / 4 (after its own reader ran) | RXV §1, §5.1 **[new]** |
| wanted anything from outside the file | **0 / 4** | RXV §1 **[new]** |
| extracted-byte grading (by the orchestrator, not self-reported) | 2 / 2 vendors, both payloads, digests identical to the manifest | RXV §3 **[new]** |
| splat point count, both vendors | 281 498, matching R12 §4's committed sample to the printed digit | RXV §5 **[new]** |
| OpenAI splat cross-check | 3 377 976 position bytes byte-exact; **844 494** colour bytes recomputed under round-half-even, all matched | RXV §5 **[new]** |
| splat signature state, both vendors | `unverified`, neither implemented Ed25519 | RXV §5 **[new]** |
| defects found in the post-round-3 splat package | **0** | RXV §5.3 **[new]** |
| S-10 (`input_hash`) survives a foreign model | 25 / 25, first pass, absent from the stumble list | RXV §3.1 **[new]** |
| the specification caught a from-memory zip parser again | 3 gaps (EOCD false-signature, zip64 sentinel, drive-letter path) vs round 1's 1 (zip64) | RXV §5.1 **[new]** |
| new findings | 5 (S-XV-1 … S-XV-5) | RXV §4 **[new]** |
| self-reported times vs measured | 2.2–11× overestimates on all four runs | RXV §5.2 **[new]** |

### 5.7 Open-weights round, pre-fix arm — paper §5.6, Table 8

Six small local models, no agentic harness, one RTX 4090. **Folded into the
paper body by the second editing pass** (§5.6). Every row traces to `ROW` =
`results/STAGE-OPENWEIGHTS-RESULTS.md`; `GOW` = `gauntlet/RESULTS.md`
"open-weights round".

| Claim | Value | Source |
|---|---|---|
| models, first-attempt success, best-of-retry success | 6 models, **1 / 6**, **4 / 6** | ROW §1, §4 **[new]** |
| size threshold | passes from **9.4B**; degrades at **8B**; absent at **4B** | ROW §7 **[new]** |
| inline context package | **31 490 prompt tokens** (91 059 chars, 2.97 chars/token), 17 of 17 items, nothing omitted | ROW §3 **[new]** |
| per-model package token counts (different tokenizers, same package) | 28 220 – 33 044 | ROW §3 **[new]** |
| full-fixture package, for contrast | **107 388 tokens**, 409 s cold prefill | ROW §3, §2.1 **[new]** |
| prefill collapse when the KV cache does not fit | 293 / 386 / **1881** tok/s at 262144 / 131072 / 65536 | ROW §2.1 **[new]** |
| small fixture `gauntlet/roundOW/mini-v1.werk` | 938 756 B, sha256 `86dec8c0…6db75713`, 34 entries, 14 nodes, 32 declared files, `signed-and-valid` | ROW §3 **[new]** |
| extracted-byte grading (orchestrator, not self-reported) | 4 / 4 passes, both payloads; `eee8b3cb…4ef2ce` and `1e634f03…59aa5e` — **the same digests as the cross-vendor round** | ROW §4 **[new]** |
| harness wall clocks, passes | 74.0 / 435.4 / 724.6 / 1152.5 s | ROW §4 **[new]** |
| loaders used to learn the format / wanted anything outside the file | **0 / 6**, **0 / 6** | ROW §1 **[new]** |
| spec-forcing envelope task | **0 / 2**; ground truth `pose_count = 2`, `contact_count = 7`, `trials = 4096` | ROW §5 **[new]** |
| signature verdicts | package is `signed-and-valid`; every model that tried reported `present-and-invalid` | ROW §4.3 **[new]** |
| new findings | 6 (S-OW-1 … S-OW-6) | ROW §6 **[new]** |
| pre-registered predictions | registered 2026-08-08T21:07:30Z before any run; Gregor's **falsified**, the coordinator's **half-supported** with its deciding cell confirmed | ROW §0, §8 **[new]** |

**Not to be quoted as a threshold.** One model per size class. "Passes from
9.4B" is an observation over six single runs, not an established boundary.


### 5.8 Self-run round — paper §5.7

The first werk package to carry an executable payload: a language model plus
the complete SOURCE of a runtime that executes it. **Folded into the paper body
by the second editing pass** (§5.7). `RSR` = `results/STAGE-SELFRUN-RESULTS.md`; `GSR` =
`gauntlet/RESULTS.md` "self-run round".

| Claim | Value | Source |
|---|---|---|
| fixture | `gauntlet/roundSR/selfrun-v1.werk`, **62 525 273 B**, sha256 `1f8e1270…d51f17`, 85 entries, 83 declared files, 14 nodes, profile `model/1-draft` | RSR §1.1 **[new]** |
| model carried | stories15M — **15 191 712 parameters**, f32, 6 layers, dim 288, 6 heads, vocab 32 000, ctx 256; checkpoint 60 816 028 B, tokenizer 433 869 B | RSR §1.1 **[new]** |
| runtime carried | llama2.c `run.c` + `win.h` + `win.c`, `core.tool` `form: source`, **no prebuilt artifact anywhere in the package** | RSR §1.1 **[new]** |
| checkpoint layout grammar | 7 header i32 + 13 tensors, absolute offsets, total **60 816 028 B — exact, no slack** | RSR §1.1 **[new]** |
| tokenizer layout grammar | walk consumes **433 869 B** for exactly **32 000** entries; `max_token_length` declared 27, measured 27 | RSR §1.1 **[new]** |
| test vectors (temperature 0, greedy argmax) | 234 B / `32680de0…afdb5` / 65 tokens; 140 B / `eeeb4eb0…22540c` / 33 tokens | RSR §1.4 **[new]** |
| fixture self-check | `verify_selfrun.py` → **29 PASS, 0 FAIL** | RSR §1.1 **[new]** |
| agents, task, isolation | 2 vendors, one sentence, fresh directory holding only the `.werk`, 45 min cap | RSR §2.1 **[new]** |
| **result** | **2 / 2 SUCCESS, first attempt, no retries** | RSR §2.2, §2.5 **[new]** |
| wall clock, process-measured | **98.2 s** (OpenAI `gpt-5.6-sol`), **647.5 s** (Moonshot Kimi 0.15.0) | RSR §2.2, §2.5 **[new]** |
| tool calls | 14 / 98 | RSR §2.3, §2.5 **[new]** |
| package files read | **4 / 7**; neither opened `MANIFEST.json`, `spec/` or a loader | RSR §2.3, §2.6 **[new]** |
| vector match, hashed by the orchestrator | LF **and** CRLF, both vectors, both agents; token ids also matched for Moonshot (65, 33) | RSR §2.4, §2.5 **[new]** |
| independent rebuilds agreeing byte-for-byte | **4** — MSVC 19.38.33143, MSVC 19.43.34808 ×2, mingw-w64 gcc 15.2.0 `-static` | RSR §2.4, §2.5 **[new]** |
| source modified by an agent | OpenAI **none**; Moonshot `win.c` only (the two fixes the package documents), `run.c` byte-identical | RSR §2.5 **[new]** |
| bundled loader behaviour on this package | 14 nodes: 11 live, 0 dead, **3 skipped for unknown type** (`x.model.*`) — law 12 as designed | RSR §3 S-SR-8 **[new]** |
| new findings | **11** (S-SR-1 … S-SR-11) | RSR §3 **[new]** |
| draft profile | `docs/PROFILE-MODEL-DRAFT.md`, 12 874 B, DRAFT, not ruled on | RSR §4 **[new]** |

**Not to be quoted as evidence the format was necessary.** Neither agent
touched the manifest, the hashes, the layout grammars, the provenance or the
signature. A plain zip carrying the same `README.txt` and `BUILD-AND-RUN.md`
would very likely have produced the same result on this task. What the round
establishes is that self-containment extends to **executable** artifacts and
that the never-auto-execute doctrine costs nothing; what it does not establish
is that any werk-specific structure was load-bearing here. RSR §5 says so
explicitly and names the adversarial follow-up.

**Not to be quoted as a determinism guarantee.** Four builds agreeing is four
builds on one CPU with two compiler families. The package's own text says a
vectorising compiler may reassociate the reductions and that a divergence after
N tokens is an arithmetic difference rather than a broken reader.

### 5.9 Hardcopy round — paper §5.8, §8 (preservation), §9.5

Source: `results/STAGE-HARDCOPY-RESULTS.md`; summary in `gauntlet/RESULTS.md`
("hardcopy round"); design draft `docs/HARDCOPY-DRAFT.md`; artifacts in
`gauntlet/roundHC/`. **Folded into the paper body by the second editing
pass.**

| claim | value | traced to |
|---|---|---|
| the printed artifact | **3 sheets of A4 at 300 DPI** (2 prose + 1 prose-and-symbols) | `make_pages.py` output, committed under `gauntlet/roundHC/pages/` |
| payload | `smiley-v1.werk`, **8168 B**, profile `image/1`, `signed-and-valid`, sha256 `b0823016…7617a6` | `build_smiley_werk.py`; signature re-checked with `store/werkstore/signature.py` |
| the picture | 64×64 indexed-colour PNG, **315 B**, sha256 `9082008d…3d285` | `make_smiley.py`, deterministic from integer arithmetic |
| symbol | 99×99 modules + 4-module quiet zone; module **6 px = 0.508 mm**; block **642 px = 54.4 mm** | `wcode.py`, `make_pages.py` |
| codeword | **1128 B**, of which 16 B header, so **1112 payload bytes per symbol**; header overhead **1.42 %** | `wcode.py` |
| parity | one XOR symbol per 8 data symbols, so **11.11 %** overhead | `wcode.py` |
| symbols per symbols-only A4 sheet | **12** (3 × 4) | computed from the page geometry in `make_pages.py` |
| **file bytes per symbols-only sheet** | **11 861** (11.58 KiB), so **88.4 sheets per MiB** | 12 × 1112 × 8/9 |
| page cost of the shipped fixtures | `mini-v1.werk` **81** sheets, `crate-v1.werk` **1 154**, `gsplat-v1.werk` **2 550** | the same arithmetic over `os.path.getsize` |
| density against QR | `werk-hardcopy/1` **0.11346** payload bytes per module raw, **0.10085** net of parity; QR version 40-L **0.09426**, so **1.07× denser after parity** | 2953 B in 177×177 modules for QR-40-L; `wcode.py` constants for ours |
| degradation applied | rotation 0.55–0.90°, Gaussian blur radius **1.1 px**, illumination ramp to **62 %** plus vignette, noise **σ = 9/255**, JPEG **q82** | `degrade.py`, all constants literal in the file |
| control, degraded arm | **8/9** symbols read, **1 repaired by parity**, sha256 exact, **0** pixel differences over 4096 | `verify_roundtrip.py` output, quoted in the result file §4 |
| control, clean arm | **9/9**, no parity needed | same |
| archaeology run | Codex CLI **0.144.1** on `gpt-5.6-sol`, effort `high`, **206.7 s** process wall clock, `exit_code=0` | `gauntlet/roundHC/runs/attempt1/codex-a1.meta` |
| archaeology result | **5/5 success ladder**, first attempt; `recovered.werk` **byte-identical** to the payload; extracted PNG **0 pixel differences over 4096** | the orchestrator's own re-grade, result file §5.1 |
| prior-knowledge confound | **eliminated by construction** — `werk-hardcopy/1` did not exist before this round | design decision, `docs/HARDCOPY-DRAFT.md` §2 |
| network audit | the agent's pip install failed with "no matching distribution"; a case-insensitive grep for http, https, qrcode, ISO/IEC, 18004 and reed-solomon over the 45 654-byte transcript returns **0** | `gauntlet/roundHC/runs/attempt1/codex-a1.jsonl` |
| findings | **S-HC-1 … S-HC-6**, none fixed | result file §6 |

**Numbers deliberately NOT quoted from this round.** The agent's own token
counts (681 627 input, 9 286 output) are harness accounting, not a property of
the format. And no claim is made about print-and-photograph: nobody printed
anything, and `degrade.py` is a stated model whose multiplicative illumination
ramp leaves ink near zero — which is why one global threshold sufficed and the
printed local-threshold recipe went unexercised.

### 5.10 Gap-completion round (in flight at the time of the second editing pass)

Source: `results/STAGE-GAPFILL-RESULTS.md`; summary in `gauntlet/RESULTS.md`
("gap-completion round"); artifacts, harnesses and graders in
`gauntlet/roundGF/`. **The paper body was not rewritten.**

| claim | value | traced to |
|---|---|---|
| **the open-weights `mini` package contained no layout grammar** | `pick()` returned **0 characters** for every section of every `.layout.txt`; the committed `gauntlet/roundOW/context_package.mini.txt` shows the ENVELOPE banner followed by one title line and then the next file | S-GF-1; reproduced against `gauntlet/roundOW/driver.py` and the committed package |
| consequence for S-OW-3 | its first clause — *"the grammar was in the package"* — is **false**; the worked hex example added by the post-fix arm was the **only** envelope information present in either arm | S-GF-1 |
| consequence for the round-1 arm | **none** — that task's mini-specs came through a `##`-headed document, which `pick()` handled correctly; both passing digests are unchanged | S-GF-1 |
| splat-task inline package, complete | **213 737 characters ≈ 95 000 tokens** | `gauntlet/roundGF/driver.py`, `pack_context_gsplat_mini` with GF-4 applied |
| splat-task inline package, as run | **166 642 characters**, 12 of 12 items, nothing omitted; **65 775 tokens** (`google/gemma-4-e4b`), **55 376 tokens** (`zai-org/glm-4.6v-flash`) | LM Studio `prompt_tokens`, per run in `runs/*/run.json` |
| the previous rounds' budget, for comparison | 31 490 tokens (pre-fix) and 32 722 – 39 767 (post-fix) | `STAGE-OPENWEIGHTS-RESULTS.md`, `STAGE-SPECFIX-OW-RESULTS.md` |
| **serving limit, measured, RTX 4090 24 GB** | `qwen/qwen3-coder-30b` Q4 (18.63 GB) prefills a 69 485-token prompt at **274 tok/s at ctx 262144** and **286 tok/s at ctx 131072**, but a 30 715-token prompt at **3 751 tok/s at ctx 65536**. `google/gemma-4-e4b` (6.33 GB) prefills the 65 775-token package at **7 474 tok/s at ctx 131072** | four timed preflights, §2.4 of the result file |
| what that limit means | a 65 775-token prompt needs ctx ≥ 98 304, and on 24 GB a 27–30B Q4 model cannot be served one at speed — **three of the five rostered models are excluded by KV residency, not by capability** | §2.4 |
| hardcopy replication, second vendor | Kimi Code CLI **0.15.0**, the same three degraded JPEGs, the same task sentence, 60-min cap: **6 / 6 rungs, first attempt, 1367.4 s**, `exit_code=0` | `gauntlet/roundGF/runs/hc-kimi/kimi-hc.meta`, `grade.json` |
| hardcopy replication, byte grade | `recovered.werk` **byte-identical** (`b0823016…7617a6`); `image/smiley.png` **byte-identical** (`9082008d…3d285`) | `gauntlet/roundGF/grade_hardcopy.py` |
| hardcopy, Codex for comparison | 5 / 5 in **206.7 s** — Kimi is **6.6× slower** to the same bytes | `STAGE-HARDCOPY-RESULTS.md` |
| **S-HC-3 reproduced** | the lost symbol is `seq 7` again — the emptiest one. Computed `DC2D2CC9` vs printed `E20A2CD2`, repaired from parity, difference **592 bytes, all padding past the 8168-byte file length** | Kimi transcript, §3.3 |
| **S-HC-4 / S-OW-1 reproduced** | a fourth model family tried three candidate signed messages, failed all three, and **declined to render a verdict** rather than reporting tampering | Kimi transcript, §3.3 |
| the replication's one asymmetry | Kimi **had a network and used it** — `pip install numpy 2.5.2 opencv-python 4.13.0`; Codex had none. Tooling, not knowledge: no library decodes `werk-hardcopy/1` | §3.4 |
| point-cloud ground truth, sixth independent reproduction | **281 498** points; `point[0] = -0.06007473 1.62525749 0.93507129 -> 39 19 6`; WKGS `means` **byte-equal** to WKPC `position`; **281 498 / 281 498** colours recomputed from `sh-dc` match | `gauntlet/roundGF/grade_gsplat.py`, deriving it from the fixture rather than quoting it |

**Numbers deliberately NOT quoted from this round.** No splat pass rate is
reported as a rate: two of five rostered models were run and three could not be
served the package on this hardware, so `n/5` would be a hardware statistic
wearing a capability statistic's clothes. And the 262144 run that was killed
after 75 minutes is recorded as discarded, not as a failure.

### 5.11 Open-weights POST-FIX arm — paper §5.6, Table 8

Source key **RSF** = `results/STAGE-SPECFIX-OW-RESULTS.md`; summary in
`gauntlet/RESULTS.md` ("the open-weights POST-FIX arm").

| Claim | Value | Source |
|---|---|---|
| findings actioned into spec text | S-OW-1 … S-OW-4 (S-OW-5/6 recorded as no-spec-change) | RSF §0, §5 **[new]** |
| new spec text | `MINI-SPECS` §12.1 + §12.2, `MINI-SPECS` §5 preamble, `SPEC` §2.1, `ENVELOPE.layout.txt` §0 | RSF §0 **[new]** |
| the worked signed-message example | 6 fields, message 203 B, `len` + `sha256` CHECKPOINT, `verify -> TRUE`, generated by `make-examples.py` into §12.1 between markers | RSF §1 **[new]** |
| `payload_file` | optional per-version field + normative resolution order; **PROPOSED, pending a ruling**; gate clause added to `run_gate_a.py` | RSF §1 **[new]** |
| `spec_sha256` after the wave | `331519c8…` → **`3984a555…450ebd`** | RSF §0, §3 **[new]** |
| package size, post-fix | **31 490 → 32 722 tokens** (18 of 18 items, nothing omitted), still inside the 35 000-token budget | RSF §4.1 **[new]** |
| runs | **5 models, 9 runs**; 1 model (gemma-4-12b-qat) unloadable and excluded | RSF §4, §4.3 **[new]** |
| re-run population | glm-4.6v-flash **PASS on attempt 1** (was PASS on retry, first clean run 3 → 1); llama-3.1-8b **FAIL**; qwen3.8-4B **FAIL** | RSF §4.2 **[new]** |
| post-fix-only population | gemma-4-e4b **PASS** on retry (7.5B raw, "effective 4B"); nemotron-3-nano-4b **FAIL** (second 4B lineage) | RSF §4.2 **[new]** |
| the two digests, again | `eee8b3cb…4ef2ce` and `1e634f03…59aa5e` — **the same as every previous round** | RSF §4.2 **[new]** |
| the claim under test | *failure locates a gap → gap fixed → same model passes*: **did not hold for either failing model** | RSF §0, §4.4 **[new]** |
| S-OW-2 at 8B, post-fix | identical wrong artifact with `payload_file` present in the manifest it had read | RSF §4.4 **[new]** |
| S-OW-4 at 4B, post-fix | `import zipfile`, container open, all 34 entries listed; died on a cp1252 console | RSF §4.4 **[new]** |
| false tampering alarms | **0 / 9** post-fix, against **1 / 13** pre-fix on a changed roster | RSF §4.4 **[new]** |
| the sentence | "a spec fix removes an excuse; it does not supply a capability" | RSF §4.4 **[new]** |
| new findings | S-SFX-1 … S-SFX-5 | RSF §5 **[new]** |
| **interpretation ruling (binding)** | sub-9B failures are worst-case-by-construction benchmark data outside the format's use case; the environment supplies the capability; the archaeologist is part of the system | RSF §6 (Gregor, 2026-08-09) **[new]** |
| fixtures rebuilt by the wave | `crate-v1` 13 684 477 `0a7a7341`; `crate-v1-damaged` 13 685 629 `01348a10`; `crate-tex-v1` 948 659 `0b43cfb8`; `ista-varun-v1` 10 192 487 `923ab39f`; `humanoid-retarget-v1` 1 514 545 `916cf5c1`; `gsplat-v1` 30 235 611 `ede0aee6`; `mini-v1` 960 061 `f7bdcc85` | RSF §3 **[new]** |
| gates re-run after the wave | 9, all green (Stage 3A now **10 PASS**, the tenth being the `primary.*` clause) | RSF §3 **[new]** |

### 5.12 Counts derived for the body (arithmetic over the blocks above)

| Claim | Value | Source |
|---|---|---|
| agentic-arm runs, all successes | **15** = 4 (r1) + 2 (r2) + 1 (r3) + 4 (RXV) + 2 (RSR) + 2 (hardcopy: Codex 5/5 and the gap-completion round's Kimi 6/6) | arithmetic over G, R12, RXV, RSR, RHC, §5.10 **[new]** |
| loaders: used to learn the format, agentic arm | **0 / 10 recorded** = 4 (r1) + 1 recorded (r2) + 1 (r3) + 4 (RXV); r6 and r7 opened none either but are reported separately | G run 1/2, R12 §4, RXV §1 **[new]** |
| rounds 1–3 distinct specification bugs | 19 = 12 + 3 + 4 | G, R12 **[v1/new]** |
| later-round findings | 28 = 5 (S-XV) + 6 (S-OW) + 11 (S-SR) + 6 (S-HC); plus 5 (S-SFX) from the spec-fix wave | RXV §4, ROW §6, RSR §3, RHC §6, RSF §5 **[new]** |
| implementer populations in Table 9 | 3 commercial families; 5 open-weights lineages (Qwen, Meta, Google, NVIDIA, Z.ai) | RXV §2.1, ROW §2, RSF §4.2 **[new]** |
| ~~pending cell, **not filled in**~~ → **now measured** | frontier open-weights served locally: DeepSeek-V4-Flash-0731, MXFP4, our own `llama-server` on 8× V100. **The Table 9 row can now be filled — row text in §13.** | RDS §0a, §2 **[new]** |
| the void arm's two harder cells, now measured | splat task 0 / 2 servable of 5 (3 excluded by KV residency); adapted self-run FAIL | §5.10 (gap-completion) **[new]** |

### 5.12b Instrument defects, folded into §4.2, §5.6 and §7

| Claim | Value | Source |
|---|---|---|
| the context packer's dropped grammar | `pick(ENVELOPE, 0..7)` → **0 chars**, 9 sections found and 0 kept, while the header reported 18 of 18 items and `omitted=[]` | §5.10, S-GF-1 **[new]** |
| what it invalidates | the open-weights **spec-forcing envelope arm**; the body withdraws that arm rather than reporting it | §5.10; ROW §5 **[new]** |
| what it does **not** touch | the round-1 task arm (its mini-specs came through a `##`-headed document) and every non-mini package, which inlines whole files — both passing digests unchanged | §5.10 **[new]** |
| the grader that accepted an answer key | `grade_selfrun.py` v1 scored a PASS on inlined test-vector text; grade A is now an echo check and only grade B (the harness invoking a built binary) decides | §5.10, §4.3 of the gap-completion file **[new]** |
| the wrong-shell run, discarded before grading | Windows `bash` resolved to WSL, which has no compiler; re-run cold with the interpreter recorded in every `run.json` | §5.10, §4.2 of the gap-completion file **[new]** |

### 5.13 The capability ladder (§9.4) — what is measured and what is argued

| Claim | Value | Source |
|---|---|---|
| the three requirements: knowledge, hands, working memory; a format removes only the first | — | ROW §0b (Gregor's framing) **[new]** |
| the four rungs, and which are measured | autonomous agent (measured); small model + inline context + feedback (measured); any model + a determined human (**not measured**); novice human, no model (**not measured**) | ROW §0b table **[new]** |
| the three implementer tiers | preview (rename the zip; imposters are the preview) / structured (run `loaders/werk_read.py`) / exact-offset (write a decoder from `spec/layouts/*.layout.txt`) | ROW §0b second table **[new]** |
| "the bottom rung is argued, not measured" | verbatim in spirit | ROW §0b closing **[new]** |

## 6. Ecosystem (§6)

### Table 11 (paper) — gate state at the time of writing

| Gate | Value | Source |
|---|---|---|
| reference core, three faces (`run_gate.py`) | 11 PASS, 0 FAIL, 1 SKIP | R12B §3 gate table **[new]** |
| golden fixture (`run_gate_a.py`) | 9 PASS, 0 FAIL | R12B §3 **[new]** |
| enrichment pipeline (`run_gate_3b.py`) | 19 PASS, 0 FAIL, 0 WARN | R12B §3; RP "Headline" **[new]** |
| retarget (`run_gate_6.py`) | 34 PASS, 0 FAIL, 0 SKIP, 30.4 s | R12B §3 **[new]** |
| image profile (`run_gate_9.py`) | 15 PASS, 0 FAIL | R12B §3 **[new]** |
| splat/tools (`run_gate_12.py`) | 18 PASS, 0 FAIL, 0 SKIP, 15.8 s | R12B §3 **[new]** |
| Blender (`test_gate.py`) | 20 PASS, 0 FAIL, 0 SKIP, 6.3 s | R12B §3 **[new]** |
| Unreal round trip (`roundtrip_gate.py`, UE 5.7) | 16 PASS, 0 FAIL | R12B §3 **[new]** |
| Unreal engine-free core (`werk_gate.exe`) | 10 PASS, 0 FAIL, 0.31 s | RR §2 gate table **[new]** |
| Unreal live editor control (`proof_session.py`) | 6 PASS, 0 FAIL | H "Stage 10B results → Gate B" **[v1]** |
| game engine (`cargo test -p cub-werk`) | 43 passed, 0 failed (35 + 7 + 1) | R12B §3 **[new]** |
| store (`pytest store/tests`) | 59 passed | H "Stage 7 CDC results", preamble **[v1]** |
| the single SKIP is this host's msys2 gcc | — | RR §2 "One SKIP, unchanged and honest" **[new]** |

### 6.1 Reference core

| Claim | Value | Source |
|---|---|---|
| fixture #1 | 413 741 B, 28 entries, 15 nodes, 26 declared files | H "Stage 2 results → Conformance fixture #1" **[v1]** |
| three faces agree; one 879 616-byte library | 15 nodes, 14 alive / 1 skipped | H "Stage 2 results → 3. One .werk, three faces, one DLL" **[v1]** |
| round trip proven three ways; fixed DOS timestamp | — | H "Stage 2 results → 1." **[v1]** |
| re-hashed schema-invalid payload scenario | 0 hash mismatches, `payload-schema-invalid` | H "Stage 2 results → 2. Damage gauntlet" **[v1]** |
| three bootstrap readers standalone | 26/26 files over 15 nodes; stdlib Python, bare `rustc`, gcc and MSVC | H "Stage 2 results → 4." **[v1]** |
| rest-pose payload identical to the spec's own example | 560 B, same sha256 | H "Stage 2 results → The one measurement…" **[v1]** |

### 6.2 Game engine

| Claim | Value | Source |
|---|---|---|
| native implementation, not the C ABI; reports `unverified` | — | H "Stage 5 results → The reader" **[v1]** |
| zero-cook load | exit 0, 36 nodes, 34 live, 0 dead, 2 skipped, 139 files, 12 865 205 B, r = 0.889269 m | H "Stage 5 results → 1." **[v1]** |
| damage agreement with werk-core | same dead node and file | H "Stage 5 results → 2." **[v1]** |
| Table 9 load times and ratios | 0.043/0.022 (1.9×), 88.95/24.00 (3.7×), 145.51/21.69 (6.7×) ms | H "Stage 5 results → 3." **[v1]** |
| three-material caveat | 1 005 360 vs 502 681 vertices | H "Stage 5 results → 3.", paragraph after the table **[v1]** |
| 65 ms per million-triangle mesh | — | H "Stage 5 results → 3.", final paragraph **[v1]** |
| exported package read by the bootstrap reader | 9 nodes, 8 live, 0 dead, 1 skipped; manifest validates 0 errors | H "Stage 5 results → 7." **[v1]** |
| two engine bugs (zero-radius bounds default; circumscribing sphere) | — | H "Stage 5 results → 6." **[v1]** |

### 6.3 Blender

| Claim | Value | Source |
|---|---|---|
| Blender 4.2.1 LTS, found by the gate, factory settings | — | H "Stage 11 results", preamble **[v1]** |
| Table 10 rows 1–9 | 36/34/0/2/0, 272 v / 408 t, 0.329 s; 1 dead / 33 alive, 0.149 s; uuid + 7 facets + 15 tags; 624 539 B / 50 entries / 8 nodes / 49 files; 0 errors 0 warnings; 49/49; 49/49 byte-identical; 0 m and 8.43e-08 rad vs 1e-5; colour spaces preserved | H "Stage 11 results → The four briefed clauses" and "→ Three clauses the brief did not ask for" **[v1]** |
| Table 10 point-cloud row | 281 498 points, colour attribute, splat not imported twice, 2.08 s | R12 §5 "The Blender adapter" **[new]** |
| five silent bugs + the sixth in the gate (8e-3 rad vs 1e-7) | — | H "Stage 11 results → The five bugs the gate caught" **[v1]** |

### 6.4 Unreal

| Claim | Value | Source |
|---|---|---|
| import: exit 0, 36 nodes, 164 files verified, `unverified`, 0.382 s | — | H "Stage 10 results → Gate A" **[v1]** |
| damaged: exit 1, 1 refused, 21 assets | — | H "Stage 10 results → Gate A" **[v1]** |
| round trip 272/408 in and out, identical AABB, byte-identical WAV | — | H "Stage 10 results → Round-trip" **[v1]** |
| three independent readers agree (own core, `werk_read.py`, jsonschema 0 errors) | — | H "Stage 10 results → Three independent readers agree" **[v1]** |
| the textured fixture is built by driving the Blender add-on | — | H "Stage 10B results → The textured fixture" **[v1]** |
| three maps pixel-identical; PNG bytes identical for 0 of 3 | — | H "Stage 10B results → The texture round trip" **[v1]** |
| colour spaces in and out: albedo srgb, mr linear, normal linear | — | H "Stage 10B results → Gate A" **[v1]** |
| metallic channel uniformly zero by construction | — | H "Stage 10B results → The textured fixture" **[v1]** |
| S10-6: every UV at the origin, with 730 verts / 408 tris / three textures / three slots all reported correct | — | H "Stage 10B results → Spec and platform findings", S10-6 **[v1]** |
| "a report is not a measurement" | verbatim | H "Stage 10B results", S10-6 closing **[v1]** |

### 6.5 Retarget

| Claim | Value | Source |
|---|---|---|
| Table 11 bones | 19 / 68 / 31 | H "Stage 6 results → The three retargets" **[v1]** |
| Table 11 solved scales (post-ruling-8) | 1.358670 / 0.991813 / 0.0616003 | RR §3 "Changed, by ~0.1 %" **[new]** |
| Table 11 round trips | 5.157e-08 / 5.217e-08 / 8.803e-08 rad | RR §3 "Unchanged, to the last printed digit" **[new, confirms v1]** |
| declared tolerance 1.0e-4 rad, from the animation grammar | — | H "Stage 6 results → The three retargets" **[v1]** |
| hips 0.836–1.091 m; canonical rest hip 0.98 m | 0.83625 … 1.09121 m | RR §3 hips table (post-ruling values) **[new]** |
| CesiumMan is a 1.29 m figure | — | H "Stage 6 results → The scale column is the claim" **[v1]** |
| six cross-rig transits, 5.2e-08 … 8.8e-08 rad | — | RR §3 (identical to the pre-ruling run) **[new, confirms v1]** |
| named uncrossable bones (no clavicles, no third spine joint) | — | H "Stage 6 results → Cross-rig transit" **[v1]** |
| frame-invariance spreads | 2.35e-06 / 3.03e-14 / 7.60e-14 rad adjacent; 0.2217 rad interposed | RR §3 closing paragraph **[new; v1 quoted only two of the three adjacent values]** |
| S6-3 filed | — | H "Stage 6 results → Spec findings" **[v1]** |

### 6.6 Enrichment pipeline

| Claim | Value | Source |
|---|---|---|
| sixteen producers, named | — | H "Stage 3 Part B results → What it is"; per-asset "16 ok" **[v1]** |
| Table 12 rows | 17 936 593 / 26 871 359 / 7 551 623 B; 37/108, 38/123, 33/74; 27/27, 28/28, 23/23; 0 err 0 dead ×3; 16 ok / 16 ok / 15 ok + 1 failed; 196.9 / 88.9 / 72.3 s | H "Stage 3 Part B results → Gate measurement"; R Stage 3 **[v1]** |
| 108 versions stamped; 78 derived; 78/78 recomputed | — | H "Stage 3 Part B results → Gate measurement" **[v1]** |
| validated against the schemas the package carries; two reproducible runs byte-identical | — | H "Stage 3 Part B results → Reproducibility, measured" **[v1]** |
| the failing producer, its exception, 33 nodes, 0 dead | — | H "Stage 3 Part B results → Per-stage timings" **[v1]** |
| 25.66 m longest axis, 130 tonnes, not rescaled | — | H "Stage 3 Part B results → One more thing the pipeline refuses to do" **[v1]** |
| V-HACD vendored: 8 364 lines, unmodified, subprocess | — | RP "Ruling 18 → What was vendored" **[new]** |
| V-HACD vs the substitute | peak 0.1529 → 0.0000 m and excess 2.785 → 0.926 (example); peak 2.0019 → 1.5529 m (−22 %), excess 1.028 → 0.716 (−30 %) (lantern); mean 0.0089 → 0.0048 m, peak +6 %, excess +18 % (crate) | RP "Old versus new" table and paragraph **[new]** |
| the open-box explanation and both-way ratios | coverage 1.0000 for both engines | RP "Old versus new" **[new]** |
| upstream defaults shipped; no setting wins on all three | — | RP "Fill mode and resolution, swept (S-P-2)" **[new]** |
| MikkTSpace vendored, unmodified | 1 899 + 145 lines | RP "Ruling 19 → What was vendored" **[new]** |
| angle between the two tangent bases | median 9.76°, p95 175.13° | RP "How far apart the two actually are" (crate row) **[new]** |
| handedness the old method got wrong | 1 927 of 5 703 = 34 % | RP same table + paragraph **[new]** |
| splits are real seams | 0.6 % spread over a 10 000× tolerance change; angular method within 3 % | RP "Are those splits real…" **[new]** |
| VLM path completed for the first time, all three assets | 3.32 / 3.38 / 3.12 s, 10 fields each | RP "Ruling 16 → The run" table **[new]** |
| the ten field names | density, Young's modulus, failure mode, thermal conductivity, specific heat, flammability, electrical, magnetic, porosity, floats-in-water | RP "Crate, in the package" table **[new]** |
| every field stamped `inferred`; model named; preview sheet as input; 27 of 27 hashes recomputed | — | RP "Verification" **[new]** |
| the wrong answer | metal street lamp → `oak wood`, flammable, does not float, confidence 0.95 | RP "What the first real run exposes (S-P-5, S-P-6)" **[new]** |
| S-P-6: a self-reported confidence is not a confidence | — | RP "Findings", S-P-6 **[new]** |

### 6.7 Store

| Claim | Value | Source |
|---|---|---|
| zero third-party dependencies including the cryptography | — | H "Stage 7 results → What landed" **[v1]** |
| whole-blob corpus results | 1.9970×; 0.2404 %; 0.27 % | H "Stage 7 results → Corpus" **[v1]** |
| materialisation identical to the originals (whole-tree comparison) | — | H "Stage 7 results → Gate wording, checked literally" **[v1]** |
| Table 13 | 31.79 MiB logical; 26.72 → 21.89 MiB; 1.1897× → 1.4524×; 5.15 → 0.31 MiB | H "Stage 7 CDC results → Gate measurement" **[v1]** |
| chunker parameters and the SHA-256-derived gear table | 64 KiB / 256 KiB / 1 MiB | H "Stage 7 CDC results → What landed" **[v1]** |
| 1 of 19 chunks changed; sync moved 3.63 % | — | H "Stage 7 CDC results → Gate measurement" **[v1]** |
| damaged fixture refused in 1.43 s, no reference recorded | — | H "Stage 7 CDC results → Gate measurement" **[v1]** |

### 6.8 One digest, three languages

| Claim | Value | Source |
|---|---|---|
| 46 embedded spec files, digest `f087dbcb…e700`, C++ equals the Python reference | — | RR §2, S-R-6 bullet **[new]** |
| six writers broken by the mandatory field | four fixture builders, `werkc`, Blender exporter, pipeline, C++ exporter | RR §5, S-R-2 and S-R-6 **[new]** |
| the sixth found by a gate that had earlier refused to run | — | RR §2 "The Unreal 10B gate: refused first, then run" **[new]** |
| first optional per-node digest, distinct from the file's own hash | `d7e34379…` vs `487505e7…` | RR §2 **[new]** |

## 7. Threats to validity (§7)

| Claim | Value | Source |
|---|---|---|
| 14/14 across the agentic arm | 4 + 2 + 1 + 4 + 2 + 1 | §5.11 above **[new]** |
| "consistent with a true rate above roughly four-fifths" | one-sided binomial reasoning on 14/14 | arithmetic on the counts above; stated as an interval, no external source **[new]** |
| three commercial families + five open-weights lineages | — | RXV §2.1; ROW §2; RSF §4.2 **[new]** |
| self-reported time inflation | 2.2–11× on all four cross-vendor runs | RXV §5.2 **[new]** |
| JS agent wrote its zip reader before opening the spec | — | G "run 1 → JavaScript" **[v1]** |
| Table 17 fixture record (**the shipped build at the time of writing**) | 13 684 477 / 13 685 629 / 948 659 / 10 192 487 / 1 514 545 / 30 235 611 B and their digests | RSF §3 "Rebuilt fixtures" **[new]** |
| the superseded build the rounds were handed | 13 611 141 / 13 612 293 / 876 621 / 10 120 093 / 1 442 453 / 30 163 573 B | R12B §3; FX **[new]** |
| one shared `spec_sha256` across the six | `331519c8…` → **`3984a555…450ebd`** after the spec-fix wave | R12B §3; RSF §3 **[new]** |
| three experiment packages pinned outside the corpus | `mini-v1.werk`, `selfrun-v1.werk`, `smiley-v1.werk` | ROW §3; RSR §1.3; RHC §3.1 **[new]** |
| harness failures recorded, not scored, in the later rounds | zero-content reasoning replies + HTTP 400; a `U+2011` that killed the driver; the discarded hardcopy sandbox run | ROW §6 (S-OW-5); RSF §4.3; RHC §5.3 **[new]** |
| the Blender-built fixture's hash changes by design | — | R12B §3 closing nuance **[new]** |
| first edition's three fixture disagreements | one size / two digests; two-byte drift; 60 vs 61 files | paper/NUMBERS.md §8 (P8) **[v1]** |
| all three resolved structurally; every gate calls a pin check first | S8-1 … S8-5 resolved | RR §4 "S8-1 … S8-5 (the paper agent's findings): resolved" **[new]** |
| two stale pins caught by the pin mechanism, one in another repository | UE gate +4 files; cub-werk pin | R12B §3 "Two stale pins found and corrected" **[new]** |
| round-2 Rust agent died at 21 min after 3 520 lines across eight modules | — | H "Findings from gauntlet round 2 itself"; G "run 2" **[v1]** |
| both round-2 transcripts written as zero-byte files | — | G "run 2 → Setup"/H same section **[v1]** |

## 8. Related work (§8)

No measured numbers. Citations [1]–[26] are bibliographic references, listed in
`paper/v2/PAPER.md` under "References"; none is used to support a measurement.

## 9. Discussion (§9)

| Claim | Value | Source |
|---|---|---|
| no deflate, no zip64 anywhere; both refused by name; no zip64 fixture | — | H "Stage 2 results → Implementation decisions"; G "run 1 → Python" (zip64 refusal) **[v1]** |
| three consumers report `unverified` | CUB, Unreal, round-2 Rust reader | H "Stage 5 results"; "Stage 10 results → Gate A"; G "run 2 → Agent 2" **[v1]** |
| Unreal imports no skeletons or animation | — | H "Stage 10B results → Not done here" **[v1]** |
| Blender: one version, one OS | — | H "Stage 11 results → Not done here" **[v1]** |
| pipeline assets, none above 6 576 triangles | — | H "Stage 3 Part B results → Gate measurement" **[v1]** |
| engine gate half measured (load time only, no frame) | — | H "Stage 5 results → What is NOT proven" **[v1]** |
| no real splat above the DC band; synthetic ascii PLY covers the rest | 32 Gaussians × 16 coefficients | R12 §6, S12-6 **[new]** |
| the recovery appendix is specified and unimplemented (six passes) | — | RR §6 item 3; D ruling 3 **[new]** |
| the round-2 recipe's exclusion list vs the delivered image | — | G "run 2 → Agent 2 — Rust" **[v1]** |
| the VLM's wrong answer at 0.95 | — | RP "What the first real run exposes" **[new]** |
| `payload_file` is implemented but **PROPOSED**, pending a ruling | — | RSF §1 (S-OW-2) **[new]** |
| the model profile is a DRAFT with 11 findings and an unsolved `core.model.graph` | — | RSR §3, §4 **[new]** |
| channel independence, §9.5 | 8168 B recovered byte-exact from degraded photographs; 88.4 sheets/MiB | RHC §4, §3.3 **[new]** |

## 10. Authorship (§10)

| Claim | Value | Source |
|---|---|---|
| five Blender and three Unreal silent bugs | — | H "Stage 11 results → The five bugs…"; "Stage 10B results" S10-6 + "Two more bugs of the same family" **[v1]** |
| concurrent agents collided on a shared findings counter three times | — | H "Finding numbers, reconciled" **[v1]** |
| per-stage result files, serialized merge | ruling 20 | D ruling 20; RR §1 row 20; `results/README.md` **[new]** |

---

## 11. Numbers deliberately NOT used

Recorded so their absence is a decision rather than an oversight.

| number | why not used |
|---|---|
| the 6.7× three-material engine row | quoted **only** with its caveat, never as the headline, per H's own instruction |
| Stage 12's pre-rebuild fixture sizes (e.g. `gsplat-v1` at 30 159 206 B, `crate-v1` at 13 606 819 B) | superseded within a day by the ruling-21/22 rebuild; the paper quotes the shipped build only (R12B §3) |
| the rulings wave's intermediate fixture record (`crate-v1` 13 510 877 B, `spec_sha256` `f087dbcb…`) | one rebuild older than the shipped set; the `f087dbcb…` digest is quoted only where it is the *subject* of the claim (§6.8, the three-language agreement measured on that revision) |
| `crate-v1.werk` "12.79 MiB, 166 files" (H, Stage 7 CDC corpus) | 166 is a zip **entry** count, not a declared-file count; filed as S8-5 and fixed by the generated record |
| Blender gate's own build-state fixture sizes | a third build state; superseded by the generated record |
| store synthetic-pair control 1.485× | the source itself says the real-corpus number is the one that counts |
| imposter IoU, LOD screen-space errors, per-asset collider Hausdorff beyond the three quoted values | not load-bearing for any claim the paper makes |
| V-HACD parameter-sweep table (fill mode × resolution) | quoted only as "no setting wins on all three assets"; the ratios in that table are comparable within the table only, as RP states |
| MikkTSpace degenerate-tangent counts (12/19 728, 18/16 182) and the one 0.652 |T·N| | a real finding (S-P-4) but not load-bearing for any claim in this paper |
| VLM tag-filtering counts (15 of 30, 10 of 16) | the sentence carrying them was cut for length; the finding remains in RP |
| round-3 gate's INRIA ingest (1 920 000 Gaussians, 107 520 363 B, 1.25 s, 721 568 opacities at exactly 1.0) | only the quaternion-order statistic from that run is used, in §3.2 |
| Stage 6 calibration position/direction residuals | not load-bearing; the paper uses round-trip and scale only |

---

## 12. Inconsistencies found while re-tracing (filed, not silently fixed)

These are disagreements between recorded sources, or between the first edition
and the record. None is corrected in place; each is reported here.

| # | disagreement | where |
|---|---|---|
| N2-1 | The first edition's Table 8 records the reference-core gate as "10 PASS, 0 FAIL, **0 SKIP**"; every run of that harness in the record has **1 SKIP** (this host's msys2 gcc). The SKIP was dropped in transcription. | `paper/PAPER.md` §7 Table 8 vs H "Stage 2 results → Gate measurement" and RR §2 |
| N2-2 | `results/STAGE12-RESULTS.md` states the synthetic ascii-PLY clause two ways: the §3 gate table says "0 SH-transpose and 0 quaternion-reorder mismatches over **1 568** values", finding S12-6 says "0 transpose mismatches over **1 440** values". Same clause, two totals. | R12 §3 vs R12 §6 (S12-6) |
| N2-3 | The first edition's §7.4 presents Stage 10 and Stage 10B Unreal numbers in one paragraph; the two runs disagree on the import split (Stage 10: 25 imported / 11 skipped / 22 assets; Stage 10B: 26 / 10 / 23), because 10B imports more node types. Both are correct for their run; the first edition does not say which run each number is from. | `paper/PAPER.md` §7.4 vs H "Stage 10 results → Gate A" and "Stage 10B results → Gate A" |
| N2-4 | The first edition quotes the pre-ruling-8 retarget scales (1.35696 / 0.99052 / 0.06152) and hip ranges. Ruling 8 changed two limb lengths and every scale moved by 0.13 %. The first edition is historical rather than wrong; this edition quotes the post-ruling values. | `paper/PAPER.md` §7.5 vs RR §3 |
| N2-5 | The first edition's §7.5 reports frame-invariance spreads on "two rigs" (3.03e-14, 7.60e-14 rad); the record has three (2.35e-06 also). Omission, not contradiction. | `paper/PAPER.md` §7.5 vs RR §3 |
| N2-6 | `WHITEPAPER.md` §6 attributes "median ~11 min" to all "6/6 fresh agents". The median of 637 s is round 1's four agents; round 2's agents were not timed. | `WHITEPAPER.md` §6 table vs G run 1 and run 2 |
| N2-12 | The gap-completion round's own headline says the packer "silently dropped **every byte of every layout grammar**", while its §1 records that `restposes.layout.txt` survived because it is inlined whole rather than through the selector. The body follows §1: one payload layout grammar was present, the envelope grammar was not. | `results/STAGE-GAPFILL-RESULTS.md` §0 vs §1 |
| N2-8 | **S-GF-1 (gap-completion round, in flight) supersedes part of S-OW-3's diagnosis**: the open-weights `mini` context packer dropped every byte of every `.layout.txt`, so the envelope arm's `0 / 2` was measured against a package whose banner advertised the grammar and delivered nothing. The second editing pass therefore **omits the open-weights envelope arm from the paper body entirely** and quotes only the primary arm, whose packing is unaffected. Filed, not fixed here. | `results/STAGE-GAPFILL-RESULTS.md` §1 vs ROW §5, §6 |
| N2-9 | `results/STAGE-SELFRUN-RESULTS.md` §3 files **eleven** findings (S-SR-1 … S-SR-11) and §5 says the draft profile has "**ten** findings against the existing doctrine, five of which are schema gaps", while `CHANGES.md` §9 says **six** are schema-shaped. The body quotes eleven findings and six schema gaps, per §3 and the ledger. | RSR §3 vs RSR §5 vs CHANGES §9 |
| N2-10 | The open-weights fixture and its package exist in two states one day apart: `mini-v1.werk` 938 756 B / `86dec8c0…` at 31 490 tokens (pre-fix) and 960 061 B / `f7bdcc85…` at 32 722 tokens (post-fix). Both are correct for their arm; the body quotes 31 490 as the pre-fix measurement and names the post-fix growth in §5.6 without re-quoting the number. | ROW §3 vs RSF §3, §4.1 |
| N2-11 | Every fixture size and digest in the first edition of Table 17 was superseded by the spec-fix wave's rebuild, and every gauntlet round in §5 quotes the build it was handed rather than the shipped one. Not a contradiction, but the two cannot be compared without the build beside them, which §7 now says in the body. | R12B §3 vs RSF §3 |
| N2-7 | Several gate counts quoted in the first edition are superseded rather than wrong: Blender 16 → 20 PASS, retarget 33 → 34, image profile 14 → 15, golden fixture 7 → 9. Each grew by new fixture-pin or new-feature clauses recorded in RR §2 and R12B §3. | `paper/PAPER.md` §7 Table 8 vs RR §2, R12B §3 |

---

## 13. Addendum — the frontier open-weights round (RDS), 2026-08-10

Added after the second editing pass. `results/STAGE-DSV4-RESULTS.md` was
*(pending)* when the body was written; it is complete now. **Every number below
is new and traceable to RDS.** Nothing in the body depends on them, so this
addendum is additive: it does not revise a printed claim, it supplies the one
the body deliberately left open.

### 13.1 The Table 9 row that can now replace *in progress*

The body's Table 9 (§5.9) carries:

> `| open weights, frontier class, served locally | void arm | — | **in progress at time of writing** |`

Measured replacement, with the caveat the row must carry:

> `| open weights, frontier class, served locally | void arm, our own llama.cpp | 5 | reader task PASS byte-exact; binary envelope decoded; splat package servable (54 889 tokens) but one grader sub-test fails; self-run FAIL |`

**The sentence in §5.9 that names the pending row should also change**, because
what it promised has been delivered *and* qualified: the corner of the grid is
filled, and the round's own limits (n = 1 model; every run ended on the wall cap
or a truncated reply; the envelope task is compromised by S-DS-8) belong beside
it. **Flagged for the paper-edit agent — this agent owns `gauntlet/roundDS/` and
`results/STAGE-DSV4-RESULTS.md` only and has not edited `PAPER.md`.**

### 13.2 Bring-up and serving

| Claim | Value | Source |
|---|---|---|
| model | DeepSeek-V4-Flash-0731, 284B total / 13B active, 43 layers, 256 routed + 1 shared expert, 6 used per token | RDS §1.2 **[new]** |
| quant | MXFP4, the publisher's native expert format — zero requantisation loss | RDS §1.2 **[new]** |
| weights | 154 991 539 328 B, two shards, both re-hashed on the box and matching the publisher's digests | RDS §1.2, §1.6 **[new]** |
| serving stack | our own `llama-server`, llama.cpp **b10333** (`08659901c`), CUDA 12.8, `CMAKE_CUDA_ARCHITECTURES=70` | RDS §1.4 **[new]** |
| hardware | 8× Tesla V100-SXM2-32GB, 257 416 MiB free, no competing tenant | RDS §1.1 **[new]** |
| **loaded context** | **1 048 576 — the model's full nominal maximum, no KV-forced reduction** | RDS §1.9 **[new]** |
| KV cost of the whole 1 M window | ~33 GiB (181 GiB used at 1 M vs 165 GiB at 524 288) | RDS §1.9 **[new]** |
| prefill | 215–257 tok/s | RDS §2.1–§2.4 **[new]** |
| decode | 26.3 tok/s short; **18.75 tok/s at ~40 000 tokens of depth** | RDS §1.9, §2.0 **[new]** |
| download | 154 991 539 328 B in **7 h 09 min**, 6.2 MB/s sustained, WAN-limited | RDS §1.6 **[new]** |

### 13.3 The runs

| Claim | Value | Source |
|---|---|---|
| round-1 crate task | **PASS**, graded by artifact and reproduced in a clean directory; `eee8b3cb…` + `1e634f03…`, the same two digests as every previous round | RDS §2.1 **[new]** |
| its package | 127 814 chars, 18 of 18 items, **39 351 `prompt_tokens`**, 165.4 s cold prefill | RDS §2.1 **[new]** |
| splat package, this tokenizer | **54 889 `prompt_tokens`** (roundGF measured 55 376–65 775 across tokenizers for the identical 166 642-char package) | RDS §2.2.1 **[new]** |
| splat: servability | served with **70 GiB spare**, no prefill collapse — against roundGF's "not servable on a 24 GB card" for 3 of 5 models | RDS §2.2.1 **[new]** |
| splat retry | `model-finished`, clean on iteration 1, 507.5 s; clauses 1 and 3 pass; count 281 498 recovered from WKGS *and* WKPC and cross-checked; point[0] position exact | RDS §2.2.3 **[new]** |
| splat: the failing sub-test | grader wants `39 19 6`; run reports `0.152941 / 0.074510 / 0.023529` = those values ÷ 255 | RDS §2.2.3, S-DS-6 **[new]** |
| envelope task | decoded: `pose_count: 2`, `contact_count: 7`, `trials: 4096`, both pose entries with quaternions, probabilities and support areas, all confirmed against the package's own annotated hex decode | RDS §2.3 **[new]** |
| adapted self-run | **FAIL**, grade B 0 / 2, no binary; build failed for a missing `-I tools/llama2c` | RDS §2.4 **[new]** |
| iterations, whole round | **14 iterations, 7 of them `finish=length`** | RDS §3 (S-DS-3) **[new]** |
| false tampering alarms | **0 in 4 runs**; verdict `unverified` when its own Ed25519 had a bug | RDS §2.1, §3 (S-DS-2) **[new]** |
| new findings | **8** — S-DS-1 … S-DS-8 | RDS §3 **[new]** |
| new spec/fixture bugs | **1** — S-DS-7 | RDS §2.3.2 **[new]** |

### 13.4 Two rows that revise things the body says about OTHER rounds

**These are the load-bearing ones, and both are corrections rather than
additions.**

| # | what changes | where |
|---|---|---|
| N2-13 | **The gap-completion round's "not servable" is a statement about a graphics card and the body should say so with a number beside it.** RGF reports the splat cell as 3 of 5 models excluded by KV residency; RDS serves the *identical package* — 54 889 tokens — with 70 GiB spare and no collapse. The constraint is hardware, it is quantified from both sides, and §5.9's caveat ("a zero there is … about a graphics card") is now measurable rather than argued. | RGF §2.5 vs RDS §2.2.1 |
| N2-14 | **`gauntlet/roundOW/mini-v1.werk` declares a wrong `input_hash` on node `rest-poses`** (declared `60e08ed1…`, documented construction yields `4b91ccbb…`; six variants tried; `crate-v1` 25/25 and `gsplat-v1` 3/3 verify). Every open-weights round used this fixture, so **a reader that implemented `input_hash` correctly was told an intact package was damaged**. No number printed in the body is wrong because of it — no round got far enough to check — but any future statement about that fixture's integrity must account for it. | RDS §2.3.2 (S-DS-7) |

### 13.5 Instrument defects — the third consecutive round to find one

Filed beside S-OW-5 and S-GF-1 in §5.12b's story rather than as new body text.

| # | defect | consequence |
|---|---|---|
| S-DS-5 | `roundOW`'s `extract_program()` ended a fenced block at the first ``` anywhere, including inside a Python string literal | destroyed both complete programs of the splat attempt (18 441 chars, does not parse → 21 924 chars, parses, from the same stored reply); that attempt is discarded ungraded |
| S-DS-6 | `grade_gsplat.py`'s colour clause tests a storage representation, not a value | decides the splat verdict; unresolved, filed for a ruling |
| S-DS-8 | `poses/rest.wkrp` is **byte-identical** to `spec/examples/restposes.example.wkrp`, whose full decoded header S-OW-3 inlines into the package | the envelope task has carried its own answer key since the post-fix arm; this round's decode is genuine (proven by values absent from the package) but the task needs a non-example payload |

**The pattern is now three for three and belongs in §7's discussion of the
apparatus:** S-OW-5, S-GF-1, S-DS-5. Every round enforces *"an agent's report is
evidence about the agent, not about the artifact"* — and the harnesses have been
the least-tested component in the experiment each time.
