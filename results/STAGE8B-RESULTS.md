# Stage 8B results — the second edition of the paper

**Owner of this file:** the Stage 8B (paper v2) agent. **Subtrees owned during
this wave:** `paper/v2/` only. Nothing outside `paper/v2/` and this results file
was edited: no spec, no schema, no fixture, no gate, no adapter. The first
edition in `paper/` is left exactly as committed, because §7 of the new edition
cites its verification pass as evidence.

Gregor's order: *a superior and well-written scientific paper about this* — the
first draft was solid on facts, this one had to be excellent as writing.

---

## 1. What was produced

| file | what it is |
|---|---|
| `paper/v2/PAPER.md` | the prose master, 16 087 words |
| `paper/v2/md2tex.py` | the converter: PAPER.md → werk-paper-v2.tex |
| `paper/v2/werk-paper-v2.tex` | generated, not hand-maintained |
| `paper/v2/werk-paper-v2.pdf` | **16 pages, 0 warnings** |
| `paper/v2/NUMBERS.md` | every quantitative claim traced, with a not-quoted list and a filed-inconsistencies list |
| `paper/v2/CHANGES.md` | what improved over v1 and what new measured material entered |

**The .tex is generated.** v1 maintained an 80 KB markdown master and a 90 KB
LaTeX file by hand, which is exactly the class of problem `spec_sha256` exists to
prevent: two copies of one thing with no mechanism keeping them honest. In v2 the
markdown is the source and `md2tex.py` is the only path to the PDF, so the two
cannot drift.

## 2. Compile measurement

```
python paper/v2/md2tex.py
cd paper/v2 && pdflatex -interaction=nonstopmode werk-paper-v2.tex   (x3)

Output written on werk-paper-v2.pdf (16 pages, 319065 bytes).
grep -cE "Overfull|Underfull|Warning:" werk-paper-v2.log  ->  0
```

Target was 12–16 pages; the result is 16. Two-column 10pt, 0.7 in margins,
14 tables, 1 figure, 26 references.

## 3. New material in v2 that v1 could not have carried

All of it postdates the first edition's writing:

* **Gauntlet round 3** (the splat mini-gauntlet): one fresh agent, ~25 minutes,
  a splat reader written from the layout grammars alone, the shipped point cloud
  cross-checked at a maximum 8-bit difference of **0** over 281 498 points, and
  six defect reports of which four were real — three of them the same defect, *a
  provenance format overstating what it had proved*.
* **The self-regenerating fixture**: embedded tools run on embedded input in a
  neutral directory reproduce the payload **byte-identically** in 0.54 s.
* **The pixel-identical Blender → Unreal texture handoff**, with the gate
  simultaneously printing that PNG bytes match for 0 of 3.
* **One digest, three languages**: `spec_sha256` implemented independently in
  Python, Rust and C++, agreeing byte-for-byte over 46 spec files; six writers
  broken by making the field mandatory.
* **The first real vision-model run**, including the model calling a metal street
  lamp *oak wood* at 0.95 confidence inside a package that stamps it `inferred`.
* **Reference V-HACD and reference MikkTSpace**, with the honest mixed result on
  one asset and the 34 % handedness finding.
* **Every gate re-measured** after the ruling-21/22 rebuild.

## 4. Inconsistencies found while re-tracing numbers

Filed, not silently fixed. Full detail in `paper/v2/NUMBERS.md` §12.

| # | what |
|---|---|
| N2-1 | v1's Table 8 records the reference-core gate as "10 PASS, 0 FAIL, **0 SKIP**"; every recorded run has **1 SKIP** (this host's msys2 gcc). Dropped in transcription. |
| N2-2 | `results/STAGE12-RESULTS.md` states the synthetic ascii-PLY clause two ways: §3's gate table says "over **1 568** values", S12-6 says "over **1 440** values". Same clause, two totals. **This one is a real disagreement inside a results file and wants a re-run to settle.** |
| N2-3 | v1 §7.4 mixes Stage 10 and Stage 10B Unreal numbers in one paragraph without saying which run each is from (25/11/22 against 26/10/23). Both correct for their run. |
| N2-4 | v1 quotes pre-ruling-8 retarget scales and hip heights; ruling 8 moved every scale by 0.13 %. Historical, not wrong. v2 quotes the post-ruling values. |
| N2-5 | v1 reports frame-invariance spreads on two rigs; the record has three (2.35e-06 also). Omission. |
| N2-6 | `WHITEPAPER.md` §6 attributes "median ~11 min" to all 6/6 agents; the 637 s median is round 1's four. Round 2's agents were not timed. |
| N2-7 | Several v1 gate counts are superseded rather than wrong (Blender 16→20, retarget 33→34, image profile 14→15, golden fixture 7→9), each by added clauses. |

## 5. What this wave did NOT do

* Did not touch `spec/`, `fixtures/`, `tests/`, `adapters/`, `pipeline/`,
  `core/`, `store/` or any gate. No number in the paper was produced by this
  wave; every one is transcribed from a committed record.
* Did not re-run any gate. Table 8 in the paper is the state recorded by the
  Stage 12B wave, cited as such.
* Did not correct N2-1 … N2-7 in place. N2-2 in particular is a disagreement
  between two sections of one results file and should be settled by re-running
  `tests/run_gate_12.py` and reading the clause output, not by choosing a number.
* Did not retire `paper/`. The first edition is history and is cited by the
  second.
