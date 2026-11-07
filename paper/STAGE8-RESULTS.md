# Stage 8 results — the paper

**2026-08-08.** Written per the shared-tree rule: this file holds Stage 8's
results so that `HANDOVER.md` and `ROADMAP.md` can be merged by one editor
afterwards. Nothing outside `paper/` was touched.

## Deliverables

| file | what it is |
|---|---|
| `paper/PAPER.md` | the prose master, full text, markdown |
| `paper/werk-paper.tex` | the LaTeX source (arXiv-style two-column, preamble adapted from `F:\splat-foley\paper\PAPER.tex`) |
| `paper/werk-paper.pdf` | the compiled paper, **14 pages** |
| `paper/NUMBERS.md` | the trace table: every number in the paper → file + section it was recorded in |
| `paper/STAGE8-RESULTS.md` | this file |

Title: **"Agent-implementability as a format-quality metric — the werk hermetic
self-describing artifact container, and an experiment that measures whether a
stranger can read it."** Author: Gregor Hubert Max Koch, with agent authorship
disclosed in a section of its own (§11 of the markdown, §12 of the PDF) rather
than in a footnote, because the paper is about agent-implementability and the
meta-fact is part of the result.

## Gate

The Stage 8 gate was: *PDF compiles clean; every number in the paper traces to a
recorded source (NUMBERS.md complete); no unmeasured claim stated as measured.*

| clause | measurement |
|---|---|
| PDF compiles | `pdflatex` (MiKTeX, 3 passes) → **exit 0** |
| clean | **0 overfull boxes, 0 underfull boxes, 0 LaTeX warnings** (the only line in the log is MiKTeX's "you have not checked for updates" notice) |
| page count | **14 pages**, 321 964 bytes, target was 10–14 |
| trace table | `paper/NUMBERS.md` complete — every table and every inline number has a row naming its source file and section; §9 of that document additionally lists the numbers **deliberately not used** and why |
| no unmeasured claim stated as measured | enforced by construction; see "Claims deliberately weakened" below |

Toolchain: MiKTeX `pdflatex` at
`C:\Users\gregor\AppData\Local\Programs\MiKTeX\miktex\bin\x64\pdflatex`, with
`newtxtext`/`newtxmath` present (the splat-foley preamble's preferred branch).

Rebuild with:

```
cd F:\werk\paper
pdflatex -interaction=nonstopmode werk-paper.tex
pdflatex -interaction=nonstopmode werk-paper.tex
pdflatex -interaction=nonstopmode werk-paper.tex
```

## Sources read

`MANIFESTO.md` (all 238 lines), `ROADMAP.md` (all 395), `HANDOVER.md` (all 3 250),
`gauntlet/RESULTS.md` (all 680, both rounds), `spec/SPEC.md` §§1–3 and the section
index, and the three adapter READMEs (`adapters/unreal`, `adapters/blender`,
`F:\CUB\crates\cub-werk`).

## Verification pass — measured for this stage

The paper contains one measurement made by Stage 8 itself rather than transcribed:
the four shipped conformance fixtures were re-opened with the Python standard
library alone and re-measured independently of every gate harness (the script is in
`NUMBERS.md` §8).

| fixture | bytes | sha256[:16] | zip entries | nodes | distinct declared files | manifest B | preview prefix |
|---|---|---|---|---|---|---|---|
| `crate-v1.werk` | 13 430 904 | `0e45deb97edc15dc` | 166 | 36 | 164 | 81 216 | 892 407 |
| `crate-v1-damaged.werk` | 13 432 056 | `7892729533d6177d` | — | — | — | — | — |
| `ista-varun-v1.werk` | 9 973 037 | `2fdfde3049f1c679` | 63 | 15 | 61 | 33 332 | 1 001 758 |
| `crate-tex-v1.werk` | 696 545 | `8a6488bd5de7abbc` | 53 | 11 | 52 | 22 269 | 604 527 |
| `humanoid-retarget-v1.werk` | 1 251 512 | `b0f361a1f24bd2d7` | 57 | 8 | 55 | 21 858 | 966 124 |

Confirmed exactly against the record: the image fixture's `preview_prefix_bytes`
1 001 758 and `total_size_bytes` 9 930 116 (gauntlet round 2, Rust agent); the
retarget fixture's 55 declared files / 21 858-byte manifest / 966 124-byte preview
prefix (HANDOVER "Stage 6 results → The fixture"); the textured fixture's
696 545 bytes, sha256 `8a6488bd…`, 53 entries, 11 nodes, 52 files, preview prefix
604 527 (HANDOVER "Stage 10B results → The textured fixture"); and both crate
fixture sizes in HANDOVER "Stage 10B results → Gate A".

## Findings — inconsistencies between recorded numbers

**Filed, not silently reconciled**, per the house rule. All five are bookkeeping
about which build a measurement was taken against; none of them is a defect in the
format, an implementation or a gate's logic. They are numbered `S8-n` by stage and
ordinal so they cannot collide with a concurrent stage.

* **S8-1 — one fixture size, two recorded sha256, and the shipped file matches only
  one of them.** `fixtures/crate-v1.werk` is recorded at **13 430 904 bytes with
  sha256 `8cace0b9e2e90cf5…`** in HANDOVER "Stage 10 results" (twice: the fixture
  caveat paragraph and the Gate B block) and at the **same 13 430 904 bytes with
  sha256 `0e45deb9…27f90ea1`** in HANDOVER "Stage 10B results → Gate A". The file on
  disk today is 13 430 904 bytes, sha256
  `0e45deb97edc15dc…`. So one of the two Stage 10 measurements was taken against a
  build that has since been replaced **without a size change** — the hardest kind of
  drift to notice, and precisely the case Stage 10's own fixture caveat was written
  to catch (it pins a hash, and the hash it pins is no longer the fixture's).
  *Proposed:* pin each fixture's sha256 in the harness that measures it and fail the
  gate on a mismatch, so a rebuild fails loudly rather than quietly changing what the
  gate measured. Related to the unresolved **S-29** (`spec_version`/`spec_sha256` in
  the manifest), which is the format-level version of the same problem.

* **S8-2 — the retarget fixture drifted by two bytes after its results were
  written.** HANDOVER "Stage 6 results → The fixture" records
  **1 251 514 bytes, sha256 `c0448cc4c5abeec8…`**; the shipped file is
  **1 251 512 bytes, sha256 `b0f361a1f24bd2d7…`**. Every other recorded property of
  that fixture — 57 zip entries, 8 nodes, 55 declared files, 21 858-byte manifest,
  `preview_prefix_bytes` 966 124 (77.20 %) — matches the shipped file exactly, so the
  package is structurally the one described. Two bytes and a different hash is
  consistent with a rebuild that changed a timestamp-like field, not with a content
  change. *Proposed:* same as S8-1, plus a rebuild-and-recheck of the Stage 6 numbers
  when `HANDOVER.md` is next merged.

* **S8-3 — the profile-2 gate's "60/60 files" is stale against the shipped
  package.** HANDOVER "Stage 9 results → Gate measurement" records the three
  bootstrap readers verifying **60/60 files standalone**, and ROADMAP Stage 9 repeats
  it. The shipped `ista-varun-v1.werk` declares **61 distinct files**, which is also
  what the round-2 Rust agent independently counted and reported ("61 distinct
  declared files"). The gate number is against the earlier 9 969 937-byte build; the
  shipped one is 9 973 037 bytes. Not wrong when written; wrong now.
  *Proposed:* re-run `tests/run_gate_9.py` against the shipped build and update the
  recorded count in the same pass as S8-1.

* **S8-4 — `crate-v1.werk` has at least four recorded sizes and three recorded file
  counts, and no document says which stage measured which build.** Recorded values:
  13 262 619 B / 157 entries / 155 declared files (ROADMAP Stage 3, HANDOVER
  "Stage 3 Part A", gauntlet run 1); 13 279 385 B / 155 files (HANDOVER "Stage 10
  results", labelled superseded in its own paragraph); "12.79 MiB, 166 files"
  (HANDOVER "Stage 7 CDC results → Corpus"); 13 427 826 B (HANDOVER "Stage 11 results
  → Gate measurement"); 13 430 904 B / 164 files (HANDOVER "Stage 10 results",
  "Stage 10B results", and the shipped file). Only the Stage 10 caveat acknowledges
  the rebuild at all. Consequence for a reader: the same fixture name denotes
  different bytes in different sections of one document, and only one section says
  so. *Proposed:* a short fixture-provenance table in HANDOVER giving, per fixture
  build, its sha256, its byte count and which stages measured against it.

* **S8-5 — "166 files" in the CDC corpus is a zip-entry count labelled as a file
  count.** HANDOVER "Stage 7 CDC results → Corpus" lists
  `fixtures/crate-v1.werk (12.79 MiB, 166 files)`. The shipped package has **166 zip
  entries and 164 distinct declared files** (`MANIFEST.json` and `SIGNATURE.json` are
  entries but are deliberately not in any node's `files[]`, per SPEC §2 / D-MAN-1).
  Minor, and worth fixing because "files" and "entries" differ by exactly the two
  paths the format's own reachability rule excludes, which is the kind of off-by-two
  that reads as a bug in the rule. *Proposed:* say "166 zip entries".

None of these five were reconciled in any file. The paper reports S8-1, S8-2 and
S8-3 in its "verification pass at writing time" section, and `NUMBERS.md` §9 records
why the S8-4 and S8-5 values were not quoted anywhere in the paper.

## Claims deliberately weakened, so that no unmeasured claim is stated as measured

Recorded because the gate's third clause is unfalsifiable without a list.

1. **The engine's frame-time claim is stated as untested**, not as a result. HANDOVER
   "Stage 5 results → What is NOT proven" says the gate is half measured; the paper
   says so too, and never quotes a frame-time number because none exists.
2. **The 6.7× three-material load row is quoted only with its caveat.** HANDOVER's own
   instruction is that 3.7× is the honest headline because it is the row where both
   paths handle the identical vertex set; the paper follows it and says why.
3. **The store's 1.9970× and the CDC 1.4524× are attributed to their own corpora**
   (a real production asset pair, and the fixture corpus plus a synthetic 4 KiB edit)
   rather than merged into one dedup number.
4. **"15 distinct specification bugs" in the conclusion** counts round 1's twelve plus
   round 2's three, both agent-surfaced. The larger ledger (S-1…S-9, S3-n, S6-n, S7-n,
   S10-n, S-29) is described separately and is not folded into the gauntlet total,
   because those came from implementations rather than from isolated agents.
5. **"6/6 agents"** counts the four of round 1 and the two counted agents of round 2.
   The Rust agent that died without a report is explicitly excluded from both the
   numerator and the denominator, and the exclusion is stated in the Limitations
   section rather than only in a footnote.
6. **No claim is made about non-Claude models**, about zip64, about deflate, about
   MikkTSpace, about a damage gauntlet on profile 2, or about the vision-language
   inference path, each of which is named as untested.
7. **The paper does not claim the twelve laws are novel.** §1.3 states which parts are
   prior art and confines the novelty claim to the combination plus the measurement
   discipline.

## Notes for whoever merges the shared docs

* ROADMAP Stage 8 can be marked DONE with: *"DONE 2026-08-08. `paper/PAPER.md` +
  `paper/werk-paper.tex` → `paper/werk-paper.pdf`, 14 pages, compiles with 0 overfull
  boxes and 0 LaTeX warnings. Every number traced in `paper/NUMBERS.md`. Five
  bookkeeping findings filed as S8-1…S8-5 in `paper/STAGE8-RESULTS.md` — all of them
  fixture-build drift between recorded measurements and the shipped fixtures, none of
  them a defect in the format or an implementation."*
* The five findings need a home in HANDOVER's findings list. They are labelled `S8-n`
  by stage and ordinal per the process lesson in "Finding numbers, reconciled", so
  they cannot collide with a concurrent stage's allocation.
* Nothing in `spec/`, `fixtures/`, `core/`, `loaders/`, `adapters/`, `pipeline/`,
  `store/`, `retarget/` or `tests/` was modified by this stage.
