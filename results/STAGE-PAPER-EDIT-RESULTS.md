# Stage PAPER-EDIT results — the second editing pass on the v2 paper

**Author:** the paper-edit agent. **Owns for this wave:** `paper/v2/PAPER.md`,
`paper/v2/werk-paper-v2.tex`, `paper/v2/werk-paper-v2.pdf`, the second-editing-pass
section of `paper/v2/CHANGES.md`, the consolidation of `paper/v2/NUMBERS.md`, and
this file. It edits no `spec/`, no fixture, no gate and no round artifact. A
concurrent gap-completion agent held `gauntlet/roundGF/` and appended to
`NUMBERS.md` and `CHANGES.md` during this wave; its blocks were left intact and
merged around, per `results/README.md`.

**Date:** 2026-08-09. **Work order:** fold every measured round that existed only
as an addendum into the paper body.

---

## 0. Headline

| | |
|---|---|
| Rounds folded into the body | **4** — cross-vendor, open-weights (+ post-fix arm), self-run, hardcopy |
| New body sections | §5.5, §5.6, §5.7, §5.8, §5.9 (coverage), §9.4 (capability ladder), §9.5 (survivability) |
| Rewritten | §7 (threats) in full; §4.3 and §4.5; §1.3 (six contributions → eight); §11 |
| New tables | **3** — Table 7 (cross-vendor), Table 8 (void arm), Table 9 (coverage, with the pending cell) |
| Renumbered | old Tables 7–14 → 10–17, with every in-text reference moved |
| Build | **23 pages, 0 warnings, 0 overfull, 0 underfull** (was 16 pages, 0 warnings) |
| New measurements | **none.** Every number was already traced in `NUMBERS.md` |
| In-flight cells | **1**, marked *in progress at time of writing*, not filled in |
| Inconsistencies filed | **5** (N2-8 … N2-12), none silently fixed |
| Result withdrawn | **1** — the open-weights spec-forcing envelope arm, instrument-invalidated by S-GF-1 |

---

## 1. What entered the body, and where

* **§5.5 — round 4, cross-vendor.** Two vendors that are not ours, four runs,
  4/4, on the pinned committed fixtures; `input_hash` correct first pass at
  25/25 in a foreign model; the splat cross-check going past round 3's own
  (3 377 976 position bytes byte-exact, 844 494 colour bytes recomputed under
  round-half-even); both declining Ed25519 and reporting `unverified`; and
  **S-XV-5** — round 1's criteria satisfiable from `MANIFEST.json` alone, with
  the same-day within-vendor control on the splat task. Harness-measured times
  only, with the 2.2–11× self-report inflation stated as a caveat on the whole
  ledger.
* **§5.6 — round 5, the void arm.** The inline-context + error-feedback protocol
  as a distinct methods arm; **31 490 tokens** as the measured minimum-sufficient
  self-description for round 1's task; the ~9B threshold with the 4B floor
  surviving a second lineage and `gemma-4-e4b`'s 7.5B-raw pass; small models as
  spec-gap microscopes (the false tampering alarm, the descriptor-as-payload
  wrong artifact, the unstated zip-library path); the post-fix arm and **"a spec
  fix removes an excuse; it does not supply a capability"**.
* **§5.6 closing paragraph + §9.4 — Gregor's §6 interpretation ruling, applied as
  required.** The sub-9B failures are reported as worst-case-by-construction
  benchmark data *outside* the format's use case — bare API, no scaffolding, no
  supervision — with the explicit statement that in any real deployment the
  environment supplies the capability and that the archaeologist is part of the
  system. Acknowledged as novelty; not overemphasised as a limitation. The paper
  says in those words that it "declines to report it as a limitation of the
  format".
* **§5.7 — round 6, self-run.** 2/2, model + runtime source + vectors in one
  file, 98.2 s and 647.5 s, four independent builds agreeing; **S-SR-11**, the
  documented failure that carried the second vendor through; the honest limit in
  the same breath as the result — 0/2 opened the specification, 0/2 used a
  loader, 2/2 succeeded, so the round proves self-carrying and not that
  werk-specific structure was load-bearing; and the `model/1` draft's gaps in one
  paragraph.
* **§5.8 — round 7, hardcopy.** 5/5, the custom prose-describable code and the
  decisive reason QR was rejected (an existing code cannot prove the prose was
  used); byte-identical recovery from degraded photographs; 88.4 sheets/MiB with
  the fixture costs beside it; **S-HC-1 elevated to a named insight** — a prose
  spec is a program and implement-from-prose is its only test — and the
  sufficient-versus-used distinction.
* **§8 — related work.** The digital-preservation paragraph now has an
  operational experiment on the werk side: **channel independence**, the artifact
  surviving transcription into a medium sharing nothing with the one it was
  written for. The reproducibility paragraph gains the executable-payload case.
* **§9.4 — the capability ladder.** Knowledge / hands / working memory; a format
  removes only the first and werk drives it to zero; the protocol ladder as a
  capability-axis sweep; graded tiers as graceful degradation **for
  implementers**; the bottom two rungs argued and explicitly not measured.
* **§9.5 — survivability**, with both limits (88.4 sheets/MiB; the degradation
  model is not a camera).
* **§5.9 + Table 9 — coverage**, including the pending row.

## 2. The rewritten threats section

§7 keeps its structure and changes its content. "One model family" is replaced by
**"Three model families, five open-weights lineages, and still no humans"** —
softened, not removed: n is still one per cell in most cells, the void arm is one
protocol on one machine, no damage gauntlet has run outside our own family, and
the two rungs below the void arm have never been run. Three paragraphs are new:
what an implementer reads is set by the task (S-XV-5 and S-SR-10, with the
reporting rule that *declined the loaders*, *opened the specification* and
*succeeded* must be quoted together); self-reported time is not time; and the
void arm's condition is not the format's use case. The sample-size paragraph is
restated over 15/15 in the agentic arm. The observer problem becomes "reduced but
not removed" — the implementers are no longer ours, the measurers still are, and
the defence is structural. Table 17's fixture record is updated to the shipped
post-spec-fix build, with the statement that each round quotes the build it was
handed.

## 2b. The gap-completion round, folded in mid-pass

Commit `b91aced` landed while this pass was running and changed the text rather
than only extending it.

* **S-GF-1 — an instrument defect in our own harness.** The open-weights context
  packer's section selector matched one heading shape only, so every section of
  the binary-envelope grammar was dropped while every counter in the harness
  reported eighteen of eighteen items included and nothing omitted. Three
  consequences, all in the body: §5.6 now states what the package **actually**
  contained, so the 31 490-token figure stands as measured but describes *less*
  specification than the first write-up implied — the four passing readers had no
  envelope grammar, which makes the crate-task result stronger and the claim's
  shape different; the round's spec-forcing arm is **withdrawn as
  instrument-invalidated** rather than reported as a capability result; and §7
  gains a paragraph, *the instrument is not exempt from the rule it enforces*,
  framed as the methodology working, beside the grader that accepted an inlined
  answer key and the run that resolved the wrong shell interpreter. Both passing
  digests are unchanged and the non-mini packagers never called the defective
  selector, which the body says.
* **The spec-forcing cell, measured honestly for the first time** (§5.6): the
  splat task at the void rung, with the hardware boundary stated — 65 775 tokens
  needs a served context of at least 98 304, which a 27–30B four-bit model cannot
  be given on a 24 GB card, so three of five were excluded by KV residency and
  **no rate is reported** — and both servable models failing behaviourally.
  **S-GF-2** gets its sentence: *do not execute anything that came out of the
  file* read as *do not read the file*, which recurs in the adapted self-run arm,
  where a local model predicted the build command, the arguments and the expected
  digest correctly and then compiled a path that did not exist. Gregor's
  worst-case-by-construction framing is applied to these too.
* **The hardcopy round replicated on a second vendor** (§5.8): 6/6, 1 367.4 s,
  byte-identical, same lost symbol, same correct refusal of a signature verdict —
  three rounds and five model families on that gap, still open — with the
  asymmetry stated: the second vendor had a network and used it, so the two arms
  are not isolation-equivalent.
* **§4.2 gains a grading sentence**: an echo of inlined test vectors is not
  evidence; the self-run grade requires the grader to invoke a binary the run
  built.
* **Counts moved**: fourteen agentic runs became **fifteen** in §7, §11 and
  Table 9, which gains three measured rows and loses one pending one.

## 3. What was deliberately kept out

* **The open-weights envelope arm's `0 / 2`** — withdrawn, not reinterpreted.
  Filed as **N2-8**.
* **The one remaining in-flight row of Table 9**: the frontier open-weights arm
  (`STAGE-DSV4-RESULTS.md` §§2–3 are literally *(pending)*), marked *in progress
  at time of writing*. No result invented; the paper is publishable with that
  cell pending.
* **Any pass rate for the splat cell**, for the KV-residency reason above.
* **Confidentiality.** Nothing from any patent material is anywhere in the paper.
  Executors beyond the bundled open-source ones appear nowhere; the phrase
  "an extension-tier concern by design" was available and was not needed.

## 4. NUMBERS.md consolidation

The addenda are now part of the main trace rather than a tail:

* §5.6 (cross-vendor), §5.7 (open-weights pre-fix), §5.8 (self-run) and §5.9
  (hardcopy) lost their "nothing in this block is in the paper body yet"
  preambles and gained a pointer to the body section and table they now support.
  The hardcopy block was physically moved out of the file's tail (it had been
  appended after §12) into section order.
* **New §5.11** — the open-weights POST-FIX arm, every row traced to
  `STAGE-SPECFIX-OW-RESULTS.md`, including Gregor's §6 ruling as a row.
* **New §5.12** — the counts the body derives by arithmetic (14 agentic runs;
  0/10 recorded on the loaders; 19 + 28 + 5 findings; the populations), each with
  its arithmetic shown so a reader can re-add it.
* **New §5.13** — the capability ladder, with the two unmeasured rungs marked.
* §1 (abstract) gained rows for every new abstract claim. §7 gained the shipped
  fixture record, the superseded build, the three experiment packages pinned
  outside the corpus, and the later rounds' harness failures. §9 gained
  `payload_file`-is-proposed, `model/1`-is-draft and channel independence.
* Source keys added: **ROW**, **RSF**, **RSR**, **RHC**, **RDS**.
* The concurrent agent's §5.10 (gap-completion) was left exactly as written, with
  only its heading marked as in flight.

**Rule held:** no number appears in the paper that does not have a row.

## 5. Inconsistencies found while consolidating — filed, not fixed

Recorded in `NUMBERS.md` §12.

* **N2-8** — `S-GF-1` supersedes part of S-OW-3's diagnosis (the envelope arm's
  context package shipped no layout grammar). Consequence for the body: the arm
  is omitted, not re-interpreted.
* **N2-9** — `STAGE-SELFRUN-RESULTS.md` §3 files **eleven** findings; its §5 says
  the draft profile has "**ten** findings against the existing doctrine, five of
  which are schema gaps", while `CHANGES.md` §9 says **six** are schema-shaped.
  The body follows §3 and the ledger: eleven findings, six schema gaps.
* **N2-10** — the open-weights fixture and package exist in two states one day
  apart (938 756 B / 31 490 tokens pre-fix; 960 061 B / 32 722 tokens post-fix).
  Both correct for their arm; the body quotes the pre-fix measurement and names
  the growth without re-quoting it.
* **N2-12** — the gap-completion round's headline says the packer dropped "every
  byte of every layout grammar", while its §1 records that `restposes.layout.txt`
  survived because it is inlined whole rather than through the selector. The body
  follows §1: one payload layout grammar was present, the envelope grammar was
  not.
* **N2-11** — every fixture size and digest in the previous Table 14/17 was
  superseded by the spec-fix wave's rebuild, and each round in §5 quotes the
  build it was handed. Not a contradiction, but the builds cannot be compared
  without being named, which §7 now says in the body.

## 6. Build and gate

```
python paper/v2/md2tex.py
cd paper/v2 && pdflatex werk-paper-v2.tex     (three passes)
```

| gate clause | result |
|---|---|
| PDF compiles clean | **23 pages, 0 warnings, 0 overfull, 0 underfull boxes** |
| every number traced | yes — `NUMBERS.md`, including four new blocks |
| no unmeasured claim stated as measured | the two argued rungs of §9.4, the frame-time gap, the recovery appendix and the unrun adversarial follow-ups are each labelled as unmeasured in the body |
| in-flight cells marked pending, not filled | Table 9, one row (the frontier open-weights arm) |
| no patent material, no non-public executor | verified by search over the body |

Two errors were hit and fixed during the build, recorded because a discarded
step is part of the record: a Unicode σ that `md2tex.py` has no mapping for
(rewritten in words), and an overfull table box in the first draft of Table 7
(column widths changed). The paper grew from 16 to 23 pages against a ~20-page
expectation; the new prose was condensed once after the first compile, and the
excess is four experimental rounds, the gap-completion material folded in
mid-pass, and two discussion subsections, rather than looser writing.
