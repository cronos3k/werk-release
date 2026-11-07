# CHANGES.md — what the second edition changes, and what new measured material entered

`paper/v2/` supersedes `paper/`. The first edition (`paper/PAPER.md`,
`paper/werk-paper.pdf`, 14 pages) stays committed as history: it is the document
the fixture-pinning work was a response to, and §7 of this edition cites its
verification pass as a finding.

## 1. The thesis is now stated once and never left

The first edition opened on the failure mode (formats rot) and arrived at the
metric in §1.2. This edition states the claim in the first paragraph of the
abstract and again in the first paragraph of §1.2, and every later section is
written as a consequence of it:

* **§2 is now "Design principles derived from the metric"**, not "Design: the
  twelve laws". The laws are still tabulated, but the prose argues hermeticity,
  layered self-description, degradation-as-control-flow, schema-enforced epistemic
  stamps and facts-without-enforcement as things an isolated implementer forces on
  you. The normative choices that a reviewer would question — store-mode default,
  the two hermeticity exceptions, entry order as a SHOULD, the prefix as a hint,
  `never_auto_execute` as a constant — are argued rather than listed.
* **The format is framed as the apparatus and the metric as the contribution**,
  in the abstract, in §1.3 and in §11.

## 2. Structure now matches a systems/measurement paper

| first edition | second edition |
|---|---|
| Abstract, Introduction, Design, Method, Results r1, Results r2, Spec bugs, Ecosystem, Verification pass, Limitations, Related work, Authorship, Conclusion | Abstract, Introduction (with a contributions list), Design principles, The werk Container, The Experiment (methods), Results (all three rounds + qualitative findings), Ecosystem Validation, **Threats to Validity**, **Related Work with citations**, Discussion & Limitations, Authorship, Conclusion, References |

Specific structural changes:

* **A contributions list with forward references** (§1.3) — absent in v1.
* **A container section (§3)** with a figure-worthy layout listing (Figure 1),
  the manifest, the envelope and the profiles. v1 had this scattered through its
  design section.
* **A proper methods section (§4)**: protocol, isolation, *success criteria
  declared before the runs*, what is recorded and why the loader question is
  load-bearing, deviations, and the three runs.
* **Threats to Validity (§7)** is now its own section, separated from
  implementation limits (§9.2), and carries the fixture-evolution problem and
  the observer problem explicitly.
* **Related Work (§8) is now cited**, with 26 numbered references. v1 named
  systems in prose without a bibliography. The new material is the digital
  preservation and reproducibility literature: PDF/A, the Library of Congress
  format sustainability factors, PREMIS, FAIR, HDF5/netCDF, reproducible builds,
  SPDX and ACM artifact badging. The paper's strongest transferable claim is now
  positioned against its true prior art — self-containment as a quality dimension
  that has never had an operational test.
* **No bullet-point walls in the body.** Every table is introduced and
  interpreted in the paragraph that follows it; the ecosystem section is one
  argued paragraph per consumer plus a table row, not a stage diary.

## 3. New measured material that postdates the first edition

| result | where in v2 | source |
|---|---|---|
| **Round 3 of the gauntlet** — a mini-gauntlet on the Gaussian-splat package: one fresh agent, ~25 min, splat reader written from the layout grammars, point cloud cross-checked at max 8-bit difference 0 over 281 498 points, six defect reports of which four were real and three were the same defect (a provenance format overstating what it had proved) | §5.4 | `results/STAGE12-RESULTS.md` §4 |
| **The self-regenerating fixture** — the package's own embedded tools, run on its own embedded input in a neutral directory, reproduce the payload byte-identically in 0.54 s | §5.4, §8 (reproducibility) | `results/STAGE12-RESULTS.md` §3; re-verified in `results/STAGE12B-RESULTS.md` §3 |
| **The pixel-identical cross-engine handoff** — a Blender-authored textured package imported and re-exported by Unreal with all three maps pixel-identical, and PNG bytes identical for 0 of 3, printed rather than hidden | §6.4 | `HANDOVER.md` "Stage 10B results" |
| **One digest, three languages** — the prose-defined `spec_sha256` implemented independently in Python, Rust and C++ and agreeing byte-for-byte over 46 spec files; six writers broken by making the field mandatory | §6.8, §2.5 | `results/STAGE-RULINGS-RESULTS.md` §2, S-R-6 |
| **The first real vision-model run**, and the model calling a metal street lamp *oak wood* at 0.95 confidence inside a package that stamps it `inferred` | §6.6, §9.3 | `results/STAGE-PIPELINE-QUALITY-RESULTS.md` "Ruling 16" |
| **Reference V-HACD and reference MikkTSpace** replacing declared substitutes, with the honest mixed result on one asset and the 34 % handedness finding | §6.6 | same file, rulings 18 and 19 |
| **Point clouds, splats and embedded tools** as node families, with the quaternion-order ambiguity measured on real trainer output | §3.2 | `results/STAGE12-RESULTS.md` §§1, 6 |
| **`primary.geometry` and the licence doctrine** (rulings 21 and 22) | §2.6, §3.1 | `results/STAGE12B-RESULTS.md` §§1–2 |
| **Every gate re-measured after the final spec revision** — Table 8 is now the post-rebuild state (Blender 20, retarget 34, image profile 15, golden fixture 9, splat 18, CUB 43) | §6 Table 8 | `results/STAGE12B-RESULTS.md` §3 |
| **The fixture-pin mechanism**, which exists because of the first edition's own verification pass, and which caught two stale pins within a day | §7 | `results/STAGE-RULINGS-RESULTS.md` §4 |

## 4. Numbers that changed, and why

Nothing in the first edition became wrong; some of it became historical.

* Retarget solved scales moved by 0.13 % (1.35696 → 1.358670, 0.99052 →
  0.991813, 0.06152 → 0.0616003) and hip heights by about a millimetre, because
  ruling 8 swapped two limb-segment lengths. Every rotation residual is identical
  to the last printed digit. v2 quotes the post-ruling values.
* Gate counts grew where clauses were added: reference core 10 → 11, golden
  fixture 7 → 9, retarget 33 → 34, image profile 14 → 15, Blender 16 → 20.
* Every fixture was rebuilt twice (rulings wave, then rulings 21/22), so all
  sizes and digests in v2's Table 14 are the shipped build and differ from v1's.
* v1's §8 "verification pass at writing time" is gone as a section. Its three
  findings were resolved structurally (one generated fixture record, a pin check
  before every gate), so the material now appears in §7 as a threat that was
  closed rather than as a standing discrepancy.

## 5. Prose-level changes

* Marketing adjectives removed; every number is stated with its conditions
  (median of 50 iterations, decode only, from a byte slice already in RAM;
  wall-clock over a whole agent session; declared tolerance quoted from the
  file's own grammar).
* The honest-failure material is placed where a reviewer looks for weaknesses:
  the oak-wood lamp in §6.6 *and* §9.3, the frame-invariance exception in §6.5
  and §9.2, the dead gauntlet agent and the zero-byte transcripts in §7, the
  half-measured engine gate in §9.2, and the unimplemented recovery appendix in
  §9.2 — which v1 did not mention at all.
* The authorship section keeps v1's argument and sharpens it: the separation
  that matters is implementer/measurer, not human/machine; agent-built systems
  make silent wrongness *more* dangerous; the structural defences are named.
* Length: 16 pages, 0 LaTeX warnings, against v1's 14 pages. The paper is
  denser rather than longer in content terms — v1's ecosystem section was a stage
  diary of roughly 4 900 words and is now roughly 3 300, while three new
  experimental results entered.

## 6. Build

`paper/v2/PAPER.md` is the master. `paper/v2/md2tex.py` converts it to
`paper/v2/werk-paper-v2.tex`, which pdflatex compiles to
`paper/v2/werk-paper-v2.pdf`. The converter exists so that the prose master and
the typeset paper cannot drift — v1 maintained the two by hand, which is the same
class of problem the format's `spec_sha256` exists to prevent.

```
python paper/v2/md2tex.py
cd paper/v2 && pdflatex werk-paper-v2.tex   (three passes)
```

Measured on this host: **16 pages, 0 warnings, 0 overfull or underfull boxes.**

## 7. Addendum, 2026-08-08 — the cross-vendor round (measured after the body was written)

**Not yet in the paper body; recorded here and in `NUMBERS.md` §5.6 so that the
later editing pass has a traced source.** §7's sharpest stated limit was that
every agent in all three rounds came from one model family, and that testing a
family which is not ours "has been the stated next honest step since round 1 and
remains untaken". It is now taken. Two vendors were run against the pinned
committed fixtures under round 1's isolation rules — OpenAI's Codex CLI 0.144.1
on `gpt-5.6-sol` and Moonshot's Kimi Code CLI 0.15.0 on `kimi-for-coding` — each
given round 1's task sentence verbatim and then round 3's splat task, four runs
in all, **4/4 successes**, in 558 s and 106 s on the round-1 task and 512 s and
377 s on the splat task. Both resolved the payloads through `primary` rather than
guessing paths; the extracted bytes were hashed against the manifest by the
orchestrator rather than accepted from the reports, and matched in both cases;
both reported 281 498 points on the splat package, matching round 3's committed
sample to the printed digit, with the OpenAI run recomputing all 844 494 stored
colour bytes under round-half-even and finding no mismatch. Across the four runs
**0/4 used a bundled loader to learn the format and 0/4 ported one**, exactly
round 1's headline, and the one loader that was opened at all was opened after
the agent's own reader already ran, as a cross-check — round 1's pattern
reproduced by a vendor that never saw round 1. Two of §7's own claims were
directly re-tested and held: `input_hash` (S-10), the longest detour of round 1
for three of four agents, was implemented correctly first pass by a foreign model
at 25/25 and appears nowhere in its stumble list; and the recognition threat
behaved exactly as §7 predicts, with an agent writing a zip parser from
remembered field positions, flagging itself for it unprompted, then auditing
against the package's own mini-specification and finding three gaps in its own
code. Five findings were filed (S-XV-1 … S-XV-5); the sharpest is **S-XV-5**,
which is a finding about the experiment rather than the format: the Moonshot
agent passed all five of round 1's declared success clauses in 106 seconds having
read **only `MANIFEST.json`**, never opening `spec/` at all — so round 1's
criteria can be satisfied without the specification, which bounds what the
0/N-loaders metric can be read to establish, and the paper should report
"N/N opened the specification" beside it. The same model, given the harder splat
task, read fourteen files and named `spec/README.md` and `ENVELOPE.layout.txt` as
its unblockers, so the behaviour belongs to the task and not to the vendor. The
honest summary for §7 is that the one-model-family threat is **softened, not
removed**: two families, four runs and no statistical power, both of them
frontier commercial coding models inside agentic harnesses, which is vendor
diversity rather than implementer diversity — small open-weights models,
non-agentic implementers and humans remain untested, and no damage gauntlet was
run cross-vendor. One further caveat the round produced by measurement: all four
agents overestimated their own elapsed time by factors of 2.2 to 11 against the
process clock, so **round 2's self-reported ~65-minute Rust breakdown should be
read as an impression rather than a measurement**, while rounds 1 and 3, which
recorded harness-observed wall clock, remain comparable. Full record:
`results/STAGE-CROSSVENDOR-RESULTS.md`; per-vendor summary and quotations:
`gauntlet/RESULTS.md` "The agent gauntlet — cross-vendor round"; programs,
outputs and reports: `gauntlet/roundXV/`.

---

## 8. Addendum, 2026-08-09 — the open-weights round (measured after the body was written)

**The paper body is again not rewritten; this records what §7 must say when it
is.** Full record: `results/STAGE-OPENWEIGHTS-RESULTS.md`; summary table:
`gauntlet/RESULTS.md` "The agent gauntlet — open-weights round"; harness,
fixture builder, grader, prompts, programs and transcripts:
`gauntlet/roundOW/`. Every number traces through `paper/v2/NUMBERS.md` §5.7.

§7's cross-vendor sentence — that the round tested *vendor* diversity rather
than *implementer* diversity, and that "small open-weights models, non-agentic
implementers and humans remain untested" — is now two-thirds discharged. Six
open-weights models were run locally on one RTX 4090 with no network and **no
agentic harness at all**: the whole of the package's self-description is inlined
into the prompt, the model emits one complete Python program, and the harness
runs it and feeds back the traceback. Five weight classes (30B-A3B MoE coder,
30B MoE reasoner, 27B dense, 9.4B, 8B non-coder generalist, 4B), four
architectures, four training lineages, none of them ours. **1 / 6 on the first
attempt, 4 / 6 with the one permitted retry**, graded by artifact — the
orchestrator hashed the extracted bytes and re-ran every final program in a
clean directory — and the two payload digests are **identical to the ones the
OpenAI and Moonshot agents produced**. Success is available from **9.4B**
upward, degrades at **8B** and is absent at **4B**, on one model per class.

Three things §7 should take from it, none of which the frontier rounds could
have produced.

**First, a number the paper does not currently have: how much specification the
format actually needs.** The whole test — complete manifest, complete entry
listing, the zip/UTF-8/JSON/CRC/SHA-256 sections of `MINI-SPECS`, the entire
envelope grammar, the payload layout, and hex heads — is **31 490 prompt
tokens**, measured as the server's own `prompt_tokens`, against 107 388 for the
full golden fixture. Four models built a correct reader from it. That is an
upper bound on the minimum sufficient self-description for round 1's task, and
it is the form in which the self-containment claim becomes checkable rather than
rhetorical.

**Second, small models are a better instrument for finding specification gaps
than frontier ones**, because a large model routes around a missing sentence and
a small one walks into it. Three findings, all invisible to every agent in
rounds 1–3 and to both cross-vendor vendors: **S-OW-1**, the signed-message
construction (`werk-sig/1 LF manifest_sha256 LF …`) lives only in `SPEC.md` and
`signature.schema.json`, so a reader on a small documentation budget cannot
verify a signature and — measured — reports `present-and-invalid` on a package
that is `signed-and-valid`, a *false tampering alarm*; **S-OW-2**, `primary.sound`
names a node whose `files[]` begins with a `descriptor`, and an 8B model
extracted the descriptor JSON where a WAV was asked for, which turns S-XV-4 and
S-13 from an observation into a wrong artifact produced by a program that
believed it had succeeded; **S-OW-3**, the envelope's MessagePack grammar was
present and the *worked hex example* was not, and the round's strongest model
responded by printing fabricated floats labelled "demonstration". §7's
threats-to-validity discussion should say that the format's damage reporting was
found to fail in the alarming direction, and that this was found only by
lowering the implementer's capability.

**Third, the honest boundary.** Every failure of a *boring* encoding was a
capability failure at 8B and below; no model above 9B stumbled on zip, JSON,
GLB, WAV or SHA-256. What defeated all of them was the two places werk is not
boring — its binary envelope and its signature construction. Law 11 is therefore
neither confirmed as strongly as it might have been nor refuted: it holds
exactly where it applies, and the round's findings all come from the edges where
it does not. And the claim does not extend downward: below 9B **this protocol**
did not get a working reader out of these models, which is a statement about the
rung and not about the format, since the next rung down — a determined human
supplying hands and judgement to a weak model, and below that a motivated novice
with no model at all, reaching the preview tier through a store-mode zip and the
structured tier through the bundled zero-dependency `werk_read.py` — is argued
in the result file and **has not been measured**. A user study on that rung is
the obvious next step and the paper should name it as such.

Two predictions were **pre-registered with a timestamp before any run was
started or graded**, and are recorded in `results/STAGE-OPENWEIGHTS-RESULTS.md`
§0 with the verdict in §8: the project author's ("zero failures across all
models on both tasks", on the grounds that every encoding werk uses is already
in every model's training data) is **falsified**; the coordinating agent's
counter-prediction is **half-supported**, with its deciding cell — at least one
failure in the ≤8B class on the spec-forcing task — **confirmed**. Pre-registration
is cheap and it is the reason those two sentences can be read as evidence rather
than as hindsight; future rounds should keep doing it.

## 9. Addendum, 2026-08-09 — the self-run round (measured after the body was written)

**The paper body is again not rewritten.** This addendum records what the
self-run round adds and where it would go. Full record:
`results/STAGE-SELFRUN-RESULTS.md`; summary in `gauntlet/RESULTS.md` "self-run
round"; every number traced in `NUMBERS.md` §5.8.

**What is new, in one sentence.** Every gauntlet round so far has asked whether
a stranger can **read** a werk package. This one asked whether a stranger can
**run** one — the package carries a language model *and the complete source of a
runtime that executes it* — and the answer, on two vendors with one sentence and
one file each, is **2 / 2, first attempt, 98.2 s and 647.5 s, with both agents'
output matching the package's embedded temperature-0 test vectors byte for byte
under the orchestrator's own hashing**.

**Where it belongs in the paper.** §1's contributions list gains a fourth
artifact class: a package whose payload is *executable*, with the executor
carried as source under §7.1's never-auto-execute doctrine. §5 (the gauntlet)
gains a fourth round. §7 (threats) gains the honest limit below. §9 gains the
`model/1` question.

**The three claims worth putting in the body.**

1. **Self-containment extends past documents to executable artifacts.** The
   operational test — "a competent stranger, given the file and nothing else,
   can make the model produce output *and check that the output is right*" — was
   run and passed. The second clause is the one that makes it a measurement:
   without the embedded test vectors, "it ran" would have rested on an agent's
   word that fluent English is correct output, and a runtime reading the weights
   at the wrong offsets emits confident text.
2. **"Source always, never auto-execute" cost nothing in the case that most
   stresses it.** The package that most obviously wants to ship a binary ships
   none; one agent compiled it in under a minute, the other in ten on a
   toolchain the package documents as failing. The standing objection to §7.1 is
   "but then nobody can run it", and that objection is now measured false for at
   least this class of consumer.
3. **A documented FAILURE was load-bearing.** `BUILD-AND-RUN.md` §2c records the
   two errors mingw-w64 gcc produces on the runtime's Windows shim and says the
   fix is one cast and one `#if !defined(__MINGW32__)` guard — and says why the
   package declines to ship it. The agent that never found MSVC hit both errors
   and applied exactly those two fixes, leaving the runtime itself
   byte-identical. In a package that must be *built*, negative results are
   payload. This is the build-time twin of §3.12's recorded-guess doctrine and
   is filed as S-SR-11.

**The limit, stated as plainly as the result.** Neither agent opened
`MANIFEST.json`, anything under `spec/`, or a bundled loader. **0 / 2 opened the
specification, 0 / 2 used a loader, 2 / 2 succeeded** — so this round does not
show any werk-specific structure was load-bearing: a plain zip carrying the same
README would very likely have produced the same 98 seconds. That is S-XV-5
confirmed on a third task and on both vendors — *what an agent reads is set by
the task*, not by the vendor and not by the format — and the paper should say it
in exactly those words rather than reporting "0/N used the loaders" as though it
were a property of the format. The adversarial follow-up the result file names
(a damaged self-run package, or one whose weights layout must be recovered
without a README) is what would make the layout grammars earn their bytes, and
it has not been run.

**Eleven findings, S-SR-1 … S-SR-11, none fixed**, and six of them are
schema-shaped gaps that a ruled `model/1` profile would have to close first: no
`executor` role in `core.tool`; §3.11's hermeticity rule unsatisfiable by any
model package, because a training corpus cannot be carried and no embedded tool
reproduces one; no `train` role in `core.recipe`; a
`core.tool.config.environment` block with five interpreter-shaped keys and
nowhere to put a compiler, its flags or the resulting binary — which bit
immediately, since this round's own headline comparison is across two compiler
versions and the format has no field in which to declare it; no way for a recipe
step to say its tool is deliberately not carried; and a
`core.provenance.consumed[]` that records *what* was consumed with no field for
*where from*. `docs/PROFILE-MODEL-DRAFT.md` is the draft that collects them, is
explicitly NOT ruled on, and names its own unsolved half: a `core.model.graph`
that says what the numbers mean as an architecture, and that must be
**checkable against the runtime the package also ships** or it is a second
statement of one fact with no way to catch a disagreement.

**One methodological note for §7.** The draft profile is committed to `docs/`
rather than `spec/` because `spec_sha256` is computed over the `spec/` tree a
package carries, so adding any file to `spec/` moves that digest and invalidates
every fixture's manifest. That is the `spec_sha256` mechanism (S-29, ruling 5)
doing exactly what it was built to do — making a specification change impossible
to slip in unnoticed — observed here as a *cost*, which is the honest way to
report a design working.

## 10. Addendum, 2026-08-09 — the hardcopy round (measured after the body was written)

Full record: `results/STAGE-HARDCOPY-RESULTS.md`. Summary: `gauntlet/RESULTS.md`,
"hardcopy round". Every number traced in `paper/v2/NUMBERS.md` §5.9. Design
draft: `docs/HARDCOPY-DRAFT.md`, which is a DRAFT and not a `spec/` edit.
**The paper body was not rewritten.**

Every previous round handed an agent **the file**, so "the file explains itself"
was never separated from "the substrate already knows how to open it" — the
container is a zip because zip readers exist everywhere, and the manifest is
JSON for the same reason. This round separates them by printing a werk package
on **three sheets of A4**: a prose tier in plain text, and a payload tier of 2D
barcodes for which **the printed prose is the only specification**. A fresh
Codex 0.144.1 agent on `gpt-5.6-sol` was given a directory containing **only
three degraded photographs** and one sentence naming no format, and in
**206.7 seconds** it implemented a decoder, recovered **8168 bytes
byte-identically**, matched the SHA-256 printed in words on the paper, opened
the package, verified every hash it declares, and extracted a 64×64 PNG of a
smiling face that is **pixel-identical over all 4096 pixels** to the generator's
reference. **5/5 on the declared success ladder, first attempt**, graded by the
orchestrator from the artifacts rather than from the report.

**The methodological point that makes it evidence rather than a demonstration is
that the code was invented for the round.** Standard QR was rejected for two
reasons and the second is decisive. The first is size: ISO/IEC 18004 needs
finder rectification, a 40-row alignment table, BCH format and version
information, eight masks with penalty scoring, a 160-row block-structure table
and Reed–Solomon over GF(256), which is a specification and not two printed
pages. The second is that **a code which already exists cannot distinguish "read
the printed prose" from "recognised a QR code and called a library"**, so a
QR-based artifact could not have measured self-description at all.
`werk-hardcopy/1` has no library and appears in no training data, so the prose is
the only possible path — which is also why the optional QR "convenience arm" was
deliberately not built: it would have offered the archaeology run a silent
alternative.

**Two numbers, one for §5 and one for §7.** Density: 1112 file bytes per symbol,
12 symbols on a symbols-only A4 sheet, **11 861 file bytes per sheet, which is
88.4 sheets per MiB** — making `fixtures/crate-v1.werk` **1 154 sheets** and
`fixtures/gsplat-v1.werk` **2 550**. Paper proves the property; it does not store
the corpus, and the result file says so in those words. And the round's control
did real work: the reference decoder, written only from the printed prose, read
8 of 9 symbols on the degraded pages and **recovered the ninth from the XOR
parity symbol** — the one it lost being, counter-intuitively, the *emptiest*
symbol, whose zero padding leaves the local thresholder with no contrast to work
from (S-HC-3).

**Six findings, S-HC-1 … S-HC-6, none fixed.** The one that transfers furthest
is **S-HC-1: prose that describes a code is a program, and it has bugs.** Two
were found the only way they can be — by implementing the decoder from the draft
prose alone and running it against a degraded photograph — and both corrections
are now printed on the sheet together with the measurement that motivated them:
"topmost, rightmost, bottommost, leftmost" is wrong at one degree of rotation,
where a 600-pixel edge six pixels thick has hundreds of pixels sharing the
smallest column (measured side lengths 470/237/497/125 for a symbol whose side
is 593), and the locator frame must not be assumed to be a single connected
piece under an illumination gradient. **Every prose specification in `spec/` is
in exactly that position, and the only rounds that have ever found bugs in them
are the ones where somebody implemented from the prose and ran the result.**

**S-HC-4 is the ledger item.** The signed-message construction
(`werk-sig/1 LF manifest_sha256 LF …`) lives only in `spec/SPEC.md` and
`signature.schema.json`; the printed prose does not state it and the reduced
package vendors neither file. The agent tried three candidate messages, all
failed, and **correctly declined to render a verdict** — better than the
open-weights round's models, which reported `present-and-invalid` on an intact
package. But **S-OW-1 is now measured in two independent rounds across three
model families and five weight classes and is still open**, and its proposed fix
— four lines into `MINI-SPECS` §12, plus one sentence naming `unverified` as the
right answer when the construction is unavailable — is unchanged.

**S-HC-5 and S-HC-6 sharpen how any self-description claim should be reported.**
S-HC-5: "the prose was sufficient" and "the prose was used" are different claims
and only the second is measurable — two of the seven printed steps went
unimplemented (a global threshold replaced the local one; nine hand-written crop
rectangles replaced the page-wide symbol search), so those sections are
untested. S-HC-6: on paper the minimum sufficient specification is **a function
of the payload**, not a fixed package — the open-weights round's 31 490-token
kernel was sized for a fixture with four payload families and a binary envelope,
and the archaeology agent opened, verified and explained this package from **ten
printed lines**. That refines the open-weights headline number rather than
contradicting it, and it is why the prose tier deviates from the brief's
instruction to reprint that kernel.

## Addendum — the gap-completion round (2026-08-09, after the body was written)

Three of the previous rounds' own "what this does not establish" sentences were
taken as a work list. Full record: `results/STAGE-GAPFILL-RESULTS.md`. Numbers:
`NUMBERS.md` §5.10.

**The round's largest result is a defect in a previous round's instrument, not
a result about the format.** `gauntlet/roundOW/driver.py`'s section picker
matched section numbers with `re.match` anchored at the start of the whole
matched heading. `MINI-SPECS.md` headings are `## 5. zip` and matched; a layout
grammar's heading is a number between two rules of dashes and did not. Every
section of every `.layout.txt` was therefore dropped, silently: the block still
carried its banner, the item was still counted as *included*, `omitted` was
still `[]`, and every instrument in the harness reported a complete package.
The committed `context_package.mini.txt` preserves the evidence — the ENVELOPE
banner promising "the whole normative grammar" is followed by one synthesized
title line and then the next file.

**What that changes in the paper's ledger.** S-OW-3 is quoted as *"the binary
envelope. The grammar was in the package; the worked hex example was not."*
The first clause is false. The open-weights spec-forcing arm's `0 / 2` was
measured against a package containing no envelope grammar at all, and the
worked hex example added by the post-fix wave was not a rung above the grammar
but the only envelope information those models ever received. The round-1 task
arm is unaffected, because its encodings were documented in a `##`-headed file
the picker handled correctly, and both passing digests are unchanged.
**The general form of the lesson is uncomfortable and belongs in §7: every
round has enforced "the agent's report is evidence about the agent, not about
the artifact", and nobody applied that rule to the harness.**

**The hardcopy round's N = 1 is now N = 2.** A second vendor — Kimi Code CLI
0.15.0 — was given the same three degraded page photographs, the same task
sentence naming no format, and the same 60-minute cap, and recovered the
8168-byte payload **byte-identically** in 1367.4 s, then opened it and extracted
the smiley **byte-identically**. Two behaviours reproduced that matter more than
the pass: the symbol it lost was `seq 7` again — the emptiest one, S-HC-3, now
three independent decoders and the same symbol — and it hit the S-HC-4 signature
wall and *declined to render a verdict* rather than reporting tampering, which
is now four model families on the same open finding. The replication is honest
about one asymmetry: Kimi had a network and installed `numpy` and `opencv`,
where Codex had none. That is tooling, not knowledge, and it is checkable —
no library anywhere decodes `werk-hardcopy/1`.

**The spec-forcing task on local models produced a hardware finding before it
could produce a capability finding.** With the picker fixed, the splat task's
minimum inline self-description is **166 642 characters / 65 775 tokens** —
1.9× the 35 000-token budget every previous open-weights arm was built around,
because the task needs the envelope grammar *and* both payload grammars *and* a
36 KB manifest. A prompt that size needs a context of at least 98 304, and on a
24 GB card a 27–30B Q4 model cannot be served one: measured, the same model
prefills at **3 751 tok/s at ctx 65536** and at **274 tok/s at ctx 262144**,
because the KV cache stops fitting. Three of the five rostered models are
excluded by KV residency rather than by anything about them or about werk. The
result file reports no `n/5` pass rate for that reason.

---

## 11. The second editing pass, 2026-08-09 — the addenda enter the body

Addenda 7 to 10 above were written on the standing rule that the paper body was
not to be rewritten while a round was in flight. This pass rewrites it. Every
number folded in was already traced in `NUMBERS.md`; nothing new was measured by
this pass, and nothing in flight was filled in.

**What moved where.**

| material | from | to |
|---|---|---|
| cross-vendor round (4 vendors×tasks, 4/4, S-XV-5) | addendum 7 | body §5.5 + **Table 7** |
| open-weights void arm (6 models, 31 490 tokens, the ~9B threshold) | addendum 8 | body §5.6 + **Table 8** |
| the post-fix arm (`e4b`'s 7.5B pass, nemotron confirming the 4B floor, "a spec fix removes an excuse") | `STAGE-SPECFIX-OW-RESULTS.md` | body §5.6, second half |
| Gregor's §6 interpretation ruling on the sub-9B failures | `STAGE-SPECFIX-OW-RESULTS.md` §6 | body §5.6 closing paragraph and §9.4 |
| self-run round (2/2, 98 s, S-SR-11, the honest limit) | addendum 9 | body §5.7 |
| hardcopy round (5/5, the custom code, why not QR, 88.4 sheets/MiB, S-HC-1) | addendum 10 | body §5.8 + §8 + §9.5 |
| the capability ladder and the three implementer tiers | `STAGE-OPENWEIGHTS-RESULTS.md` §0b | body **§9.4** (new subsection) |
| survivability / channel independence | hardcopy round | body **§9.5** (new subsection) |
| coverage, including the pending cells | — | body §5.9 + **Table 9** |

**Structural changes.**

* **§4.5 is now "Four protocol arms"** — agentic, void, self-run, hardcopy —
  followed by the seven runs in order. The arms are reported separately because
  their conditions are not comparable, which is the honest way to put a
  no-harness open-weights run beside a frontier agentic one.
* **§4.3 gains the S-XV-5 correction**: "declined the loaders" and "opened the
  specification" are two measurements, both task-relative, and every round from
  §5.5 onward reports them together.
* **§5 gains four round subsections and a coverage table**; the specification-bug
  section is renumbered §5.10. Tables 7–9 are new, so the old Tables 7–14 are
  now 10–17 and every in-text reference moved with them.
* **§7 is rewritten.** "One model family" becomes "three model families, five
  open-weights lineages, and still no humans" — softened, not removed. New
  paragraphs: what an implementer reads is set by the task; self-reported time is
  not time; the void arm's condition is not the format's use case. The observer
  problem is now "reduced but not removed", because the implementers are no
  longer ours and the measurers still are. The sample-size paragraph is restated
  over 14/14 in the agentic arm. Table 17's fixture record is updated to the
  shipped post-spec-fix build, with a sentence saying that each round quotes the
  build it was handed.
* **§9 gains §9.4 (the ladder) and §9.5 (survivability)**; §9.2 records that
  `payload_file` is implemented but proposed, and that `model/1` is a draft.
* **§1.3** grows from six contributions to eight; **§11** is rewritten over the
  fourteen agentic runs and the honest next steps are shortened, two of them
  having been taken.

**The gap-completion round landed mid-pass and is folded in too.** Its
measurements arrived while this pass was running and three of them change the
text rather than extend it:

* **S-GF-1, an instrument defect in our own harness.** The open-weights context
  packer's section selector matched only one heading shape, so every section of
  the binary-envelope grammar was dropped while every counter reported eighteen
  of eighteen items included. The body now says so in §5.6: the 31 490-token
  figure stands as measured but describes a package with **less** in it than the
  first write-up implied (the four passing readers had no envelope grammar), the
  round's spec-forcing arm is **withdrawn as instrument-invalidated** rather than
  reported, and §7 gains a paragraph — *the instrument is not exempt from the
  rule it enforces* — beside the grader that accepted an inlined answer key and
  the run that resolved the wrong shell. Both passing digests are unchanged; the
  non-mini packagers never called the defective selector.
* **The spec-forcing cell, measured honestly for the first time**, on the splat
  task at the void rung: a hardware boundary (65 775 tokens needs a served
  context of at least 98 304, which a 27–30B four-bit model cannot get on a
  24 GB card, so three of five were excluded by residency and **no rate is
  reported**), two behavioural failures, and **S-GF-2** — *do not execute
  anything that came out of the file* read as *do not read the file* — which
  recurs in the adapted self-run arm and is now a sentence in §5.6.
* **The hardcopy round replicated on a second vendor**, 6/6 byte-identical in
  1 367.4 s, with the same lost symbol and the same correct refusal to render a
  signature verdict; §5.8 carries it, including the asymmetry that the second
  vendor had a network and used it, so the two arms are not
  isolation-equivalent. The agentic-arm count is therefore **fifteen**, not
  fourteen, in §7 and §11, and Table 9 gains three measured rows and loses one
  pending one.
* **§4.2 gains a grading sentence**: an echo of inlined test vectors is not
  evidence, and the self-run grade requires the grader to invoke a binary the run
  actually built.

**What was deliberately NOT put in the body.**

* **The open-weights envelope arm's `0 / 2`** — withdrawn, not reinterpreted,
  per S-GF-1. Filed as **N2-8** in `NUMBERS.md` §12.
* **The remaining in-flight row of Table 9**, the frontier open-weights arm
  (`STAGE-DSV4-RESULTS.md`, whose §§2–3 are literally *(pending)*), is marked
  *in progress at time of writing*. No result is invented and no claim rests on
  it.
* **No pass rate for the splat cell**, because three of five rostered models
  could not be served the package on a 24 GB card; reporting `0 / 5` would be a
  hardware statistic wearing a capability statistic's clothes.
* **Anything from the extension tier.** Optimised executors remain an
  extension-tier concern by design and are not named anywhere.

**Build.** `python paper/v2/md2tex.py`, then three pdflatex passes. Measured on
this host: **23 pages, 0 warnings, 0 overfull or underfull boxes**, against the
first pass's 16. The growth is four new experimental rounds and two new
discussion subsections; the new prose was condensed once after the first
compile, and the round sections carry no bullet lists.

**Typographic convention pass (post-edition).** The format name is now set in
typewriter face everywhere it appears in running text (`werk`, files `*.werk`),
with a first-use footnote noting the German origin of the word; identifiers such
as `werkstore`, `WerkLink` and file paths keep their exact forms. Applied to
`PAPER.md`/the typeset paper, `WHITEPAPER.md`, and the public repository's
whitepaper and README. Recompiled: 0 warnings.

---

## Addendum — the frontier open-weights round lands (2026-08-10)

Written after the second editing pass by the roundDS agent, who owns
`gauntlet/roundDS/` and `results/STAGE-DSV4-RESULTS.md` and **has not edited
`PAPER.md`**. This section says what the body can now change and why; the edit
itself is the paper-edit agent's.

**The in-flight row is no longer in flight.** `CHANGES.md` above records, under
*"What was deliberately NOT put in the body"*:

> **The remaining in-flight row of Table 9**, the frontier open-weights arm
> (`STAGE-DSV4-RESULTS.md`, whose §§2–3 are literally *(pending)*), is marked
> *in progress at time of writing*.

Those sections are complete. **DeepSeek-V4-Flash-0731 — 284B total / 13B active,
MXFP4, served by a `llama-server` we compiled for sm_70, on eight Tesla V100s, at
the model's full 1 048 576 context — passes the reader task byte-exact and
decodes the binary envelope.** The measured Table 9 row and the caveat it must
carry are in `NUMBERS.md` §13.1.

**Three things the body should gain, in decreasing order of how much they change
an argument.**

1. **§5.9's "not servable" caveat becomes a measurement.** The body currently
   says a zero in the splat cell is partly "about a graphics card". It is now
   quantified from both sides: the same 166 642-character package is **54 889
   tokens**, and it serves with **70 GiB spare** on hardware that has it. This is
   the strongest form of the paper's own thesis about layered self-description —
   *the format's central property has a price, the price is VRAM, and the
   invoice is about 200 GB if the reader is also to be frontier-capable*. It is a
   better sentence than "it did not fit" and it belongs beside the property in
   §2, not only in §5. Filed as **N2-13**.

2. **§5.6's conclusion about spec fixes gains its second half.** The post-fix arm
   concluded *"making a fact machine-readable does not make a weak implementer
   read it"*. Read off this round's **programs** rather than its reports: the
   `werk-sig/1` message built with the six fields exactly as `MINI-SPECS` §12.1
   specifies, **Ed25519 implemented from scratch**, `primary.sound` resolved
   through `payload_file` and `role`, and the verdict **`unverified`** — not
   `present-and-invalid` — when its own curve arithmetic failed. **Zero false
   tampering alarms in four runs.** The two halves are one sentence: *a spec fix
   removes an excuse, and the excuse being gone only helps an implementer that
   was going to read it.*

3. **§7's discussion of the apparatus should say the pattern out loud.** S-OW-5,
   S-GF-1 and now **S-DS-5** — three consecutive rounds whose largest defect was
   in the measuring instrument, not in `spec/`. This round found three at once
   (a truncating code extractor, a grader testing a storage representation, and
   an envelope task that has been carrying its own answer key since S-OW-3), and
   zero new bugs in `spec/`. The honest framing is that **the gauntlet's
   instruments are the least-tested component of the experiment**, and that the
   discipline which caught all three — grade by artifact, keep the discarded run,
   re-derive ground truth rather than hard-code it — is itself a result.

**What must NOT be claimed from this round.**

* **n = 1 model.** One frontier open-weights family is a corner of the grid, not
  a population, and the row should say so.
* **No clean spec-forcing pass.** The envelope decode is genuine — proven by
  values that appear nowhere in the package — but the task is compromised by
  **S-DS-8** and cannot be quoted as a clean spec-forcing result until it points
  at a payload that is not the worked example. The splat verdict is a grader
  `FAIL` turning on **S-DS-6**, which is unresolved.
* **The protocol was never reached.** At 18.75 tok/s at depth a full
  16 384-token reply costs ~875 s, so **7 of 14 iterations ended `finish=length`**
  and no run got near its 8-iteration budget. Iteration counts from this round
  are not comparable to the 24 GB rounds' and must not be read as the model
  running out of ideas.
* **One new bug, and it is in a fixture, not the specification.** **S-DS-7**:
  `mini-v1.werk` declares a wrong `input_hash` on `rest-poses`. It changes no
  printed number, and it means the fixture has been telling correct readers that
  an intact package is damaged. Filed as **N2-14**.
