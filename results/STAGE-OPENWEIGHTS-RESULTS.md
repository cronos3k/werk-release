# Stage OPEN-WEIGHTS results — the gauntlet run against small local models

**Author:** the open-weights gauntlet agent. **Owns for this wave:**
`gauntlet/roundOW/`, `results/STAGE-OPENWEIGHTS-RESULTS.md`, and the
open-weights rows in `paper/v2/NUMBERS.md` and `paper/v2/CHANGES.md`.

**Date:** 2026-08-08.

This round exists to close the gap the cross-vendor round named in its own
verdict:

> "**the one-model-family threat is SOFTENED, NOT REMOVED** — … both vendors
> are frontier commercial coding models inside agentic harnesses, which is
> *vendor* diversity rather than *implementer* diversity. Small open-weights
> models, non-agentic implementers and humans remain untested."

Small open-weights models are now tested.

---

## 0. PRE-REGISTERED PREDICTIONS

**Registered 2026-08-08T21:07:30Z (23:07:30 local), before any gauntlet run
had been started and therefore before anything was graded.** At the moment of
registration the state was: the harness (`gauntlet/roundOW/driver.py`) was
written and had been exercised on one throwaway smoke task ("create a file
containing the word banana and print it") purely to check the tool loop and
the sandbox; **no task prompt from either gauntlet task had been issued to any
model, no run directory had been graded, and no outcome existed.** The
predictions below are therefore genuinely prior to the data.

**Prediction 1 — Gregor (project author).**
> **Zero failures across all models on both tasks**, given maximum context and
> an agentic loop.

His stated reason: every payload encoding werk uses — zip, JSON, PNG, WAV,
GLB — and the concepts underneath them are already in every model's training
data. This is **Law 11 (boring encodings) restated as a falsifiable
prediction**: if boring-by-design means the format is built out of what models
already know, then boring-by-design implies small-model implementability, and
the size of the model should not matter much.

**Prediction 2 — the coordinating agent (counter-prediction).**
> **Near-universal success on the crate task**, because S-XV-5 established that
> round 1's success criteria are satisfiable from `MANIFEST.json` alone; but
> **at least one failure in the ≤8B class on the splat task.**

Its stated reason: the splat task requires `WKGS`/`WKEM` envelope parsing from
the layout grammar, which means sustained multi-file reading and exact-offset
binary work across a long tool-loop horizon. That is where small models
historically degrade — tool-call formatting drift, repetition loops, losing the
plan — **independent of whether the encodings themselves are familiar**. The
claim is that the binding constraint is agentic stamina, not format
familiarity.

The two predictions differ on a single question: **is the difficulty of
implementing werk a property of the format's encodings (Gregor) or of the
agentic horizon the task demands (the coordinator)?** They make opposite
calls only on the small-model splat cell, which is therefore the deciding
cell.

Grading is by artifact, exactly as briefed and exactly as in the cross-vendor
round: the orchestrating agent hashes the extracted bytes against
`MANIFEST.json` itself and re-runs each program in a clean directory. Neither
prediction is visible to any of the models, and neither changes the grading
rule.

**Verdict:** *(filled in after grading — see §8.)*

---

## 0b. What this round measures — the three-requirements framing

Recorded here because it shapes how every number below should be read, and
because it should shape the paper's later editing pass. Gregor's framing:

**An implementer needs three things:**

1. **knowledge of the format**,
2. **hands** — tools, a shell, the ability to run and observe a program,
3. **working memory** — enough context to hold the relevant specification and
   its own program at once.

**A format can only eliminate (1).** werk's claim is that it eliminates it
completely, because the specification travels inside the file. (2) and (3) are
not properties of the format at all: they can always be supplied externally.
An agentic CLI supplies them. This round's protocol — inline context plus an
error-feedback loop — supplies them. In the limit, a determined **human**
supplies them for an arbitrarily weak model: pasting the relevant spec text in,
running the generated program, feeding the traceback back. In Gregor's words,
in spirit: *a GPT-3-level model has a chance of solving it if the user helps.*

So the metric's floor is **not the weakest autonomous agent but the weakest
assisted pair.** What now exists is a ladder along the capability axis, each
rung removing one externally-suppliable requirement:

| rung | who supplies hands and working memory | measured in |
|---|---|---|
| autonomous frontier agent in its own CLI | the model itself | rounds 1–3, cross-vendor round |
| **small open-weights model + inline context + error feedback** | **the harness** | **this round** |
| any model + a determined human | the human | not yet run |
| **a motivated novice human, no model at all** | the human, unaided | **argued, not measured** |

**The true bottom rung has no model in it.** Gregor's image for it: *a
twelve-year-old with a copy of "Python for Dummies" and a Windows 10 PC.* That
rung matters because it is where the format's **graded effort** design shows
that graceful degradation applies to **implementers**, not only to readers:

| tier | what it costs the implementer | what the novice gets |
|---|---|---|
| **preview** | nothing at all | the container is a store-mode zip, so Explorer opens it by renaming; the PNGs and WAVs open in anything already installed; **the imposters *are* the preview** |
| **structured access** | run one file | `loaders/werk_read.py` ships inside the package: zero dependencies, no pip, no compiler, stock Python — it exists precisely for this rung |
| **exact-offset decoding** | real skill | writing one's own binary decoder against `spec/layouts/*.layout.txt` — this is what every gauntlet agent so far has done, and the only tier that demands it |

That closes the ladder: **frontier autonomous agents → small models plus a
harness → a weak model plus a human assistant → a novice human plus the file's
own embedded tools** — and at every rung *the file itself is the only source of
format knowledge*. The design goal at its sharpest:

> **A format is fully self-describing when the weakest motivated implementer on
> the ladder can extract value at *some* tier, and each additional unit of
> implementer capability unlocks a deeper tier.**

Stated honestly: **the bottom rung is argued, not measured.** No novice human
has been tested. Doing it properly — recruiting people who have never seen the
format, giving them the file and nothing else, and recording which tier they
reach and where they stall — would be a genuine user study and is the obvious
next step after this round. Nothing below should be read as evidence about it.

The design goal this implies is sharp: **the format's job is to drive the
knowledge barrier to zero, so that the capability of the implementer becomes a
free variable.** That is what "the specification travels with the file" is
*for*.

And it fixes how a failure must be read. Under this protocol the model was
given hands and memory; requirement (1) is the only one left standing. So **a
failure here means the knowledge barrier is not yet zero at that capability
level** — which is a finding about the specification, not an excuse about the
model. Every failure below is triaged on exactly that question: was the fact it
needed present, findable and unambiguous in what the file gave it?

---

## 1. Headline

| | |
|---|---|
| Models run | **6**, one family each: 30B-A3B MoE coder, 30B MoE, 27B dense, 9.4B, 8B, 4B |
| Tasks | round 1's task sentence on a small-context fixture (**primary arm**, 6 models) + an adapted **envelope task** (2 models) |
| Inline context package | **31 490 tokens** measured (see §3) — the whole test fits under Gregor's 35 000-token budget |
| **Primary arm, first attempt** | **1 / 6** |
| **Primary arm, best of attempt + one retry** | **4 / 6** |
| Failures, primary arm | **8B** (partial: mesh byte-exact, wrong file taken for the sound) and **4B** (never produced a runnable program in 16 iterations across two runs) |
| Envelope (spec-forcing) task | **0 / 2** — the 30B coder passed 2 of 3 clauses and **fabricated** the third; the 8B never opened the file |
| Extracted bytes graded by the orchestrator, not self-reported | 4 / 4 passes, both digests, identical to the cross-vendor round's `eee8b3cb…4ef2ce` and `1e634f03…59aa5e` |
| Used a bundled loader to learn the format | **0 / 6** (they were never inlined; nobody asked for one) |
| Wanted anything from outside the file | **0 / 6** |
| New findings | **S-OW-1 … S-OW-6** |
| Pre-registered predictions | Gregor's **falsified**; the coordinator's **half-supported**, its deciding cell **confirmed** (§8) |

---

## 2. Setup

**Box.** One RTX 4090, 24 GB, Windows 10. **Server:** LM Studio's
OpenAI-compatible endpoint at `http://127.0.0.1:1234/v1`. **One model loaded at
a time, `--parallel 1`, and exactly one in-flight request at any moment** — the
serialisation is Gregor's standing instruction and it is also the only way the
per-run wall clocks mean anything on a single GPU.

**Roster.** Everything coding-capable on disk, spread across size classes, plus
two non-coder generalists so the round is not a coder-only sample.

| tag | model id (as served) | params | quant | model's max ctx | **loaded ctx** | why that value |
|---|---|---|---:|---:|---:|---|
| `qwen3coder30b` | `qwen/qwen3-coder-30b` | 30B-A3B MoE | Q4_K_M | 262144 | **65536** | measured: see §2.1 |
| `glm47flash` | `zai-org/glm-4.7-flash` | 30B MoE (deepseek2) | Q4_K_M | 202752 | **65536** | same weight class |
| `ebai27b` | `ebai3.6-27b-unscensored` | 27B dense (qwen35) | unlisted | 262144 | **65536** | same weight class |
| `glm46vflash` | `zai-org/glm-4.6v-flash` | 9.4B | Q8_0 | 131072 | **131072** | its full window fits |
| `llama31-8b` | `llama-3.1-8b-lexi-uncensored` | 8B | unlisted | 131072 | **131072** | its full window fits; a **non-coder generalist** |
| `qwen4b` | `qwen3.8_4b_distilled_gguf` | 4B | Q8_0 | 262144 | **131072** | far above what the task needs |

`unlisted` means LM Studio's catalogue reports no quantisation string for that
build; it is not a claim that the weights are unquantised.

### 2.1 Loaded context is measured, not assumed

Gregor's rule is maximum context, with the honest-recording clause when VRAM
forces less. VRAM forced less, and the evidence is a measurement, not a guess.
`gauntlet/roundOW/prefill_probe.py` times a prefill of known size:

| `qwen/qwen3-coder-30b` loaded at | prefill rate, same 8 903-token probe |
|---|---:|
| 262144 (its maximum — **loads without error**) | **293 tok/s** |
| 131072 | **386 tok/s** |
| 65536 | **1881 tok/s** |

An 18.6 GB model plus a 262144-token KV cache does not fit in 24 GB. LM Studio
**loads it anyway** and the cost appears only as a 6.4× collapse in prefill —
which is exactly the shape of failure the house rule "never infer a limit from a
timeout" warns about, and the reason this round probes instead of assuming.
Loading at the nominal maximum would have spent the entire 45-minute budget on
one prefill: the full-fixture package took **409 s** of prefill at 131072 and
was still running at 20 minutes at 262144.

**Recorded honestly: no 30B-class model in this round ran at its nominal maximum
context.** They ran at 65536, which is more than twice what the task needs.

### 2.2 The protocol, and the one it replaced

The first harness — `gauntlet/roundOW/driver_toolloop.py`, committed as part of
the record — gave the model `run_shell` / `write_file` / `read_file` /
`list_dir` and an agentic loop, mirroring the cross-vendor round's CLIs.
**Gregor superseded it before anything was graded:** LM Studio models are not
CLI agents, they are "just LLMs sitting in the void", and a tool-call loop
measures the served chat template's tool support at least as much as the model.
One partial run existed under that protocol (`qwen/qwen3-coder-30b` on the
round-1 task, stopped at turn 7 of 80). It is kept as
`gauntlet/roundOW/_discarded/toolloop-qwen3coder30b-round1-partial.log` and
**is not part of any population below.**

The operative protocol, implemented in `gauntlet/roundOW/driver.py`:

1. **Everything the model may read is inlined in the prompt.** One context
   package per task, built by the harness from inside the `.werk` file and
   nowhere else. The model cannot run anything and cannot look at anything.
2. **The loop is error feedback, not tools.** The model emits one complete
   Python program in a fenced block; the harness extracts it, runs it in the
   isolated run directory against the real fixture, and feeds back stdout,
   stderr and the traceback for a revision. **Cap: 8 feedback iterations or
   45 minutes.**
3. **The harness measures time.** `wall_s` is `time.monotonic()` around the run.
   Nothing self-reported is timed — the cross-vendor round found 2.2×–11×
   self-report inflation.
4. **Isolation is enforced in code**, not requested in the prompt: generated
   programs are screened for networking imports and for absolute paths outside
   the run directory, and run with `cwd` = the run directory. `loaders/` is
   **never** inlined — pasting the bundled readers in would make the
   0/N-loaders metric meaningless.
5. **Every run starts cold**: unload everything, load the model, wait until the
   server actually answers, then run. So each run pays its own prefill and the
   wall clocks are comparable.

**Deviations, recorded rather than hidden.**

* The task prompt is round 1's, **verbatim except the filename**
  (`crate-v1.werk` → `mini-v1.werk`); `diff` of the two with the name
  normalised is empty.
* The prompt's reporting section asks which files the agent read and in what
  order. **Under this protocol that question is unanswerable** — the harness
  chose what the model saw. "Which file unblocked it" is therefore *not* a
  measurement this round can make, and no such number is reported below.
* The second task's prompt is **adapted, not verbatim** (§6).
* `glm-4.7-flash`'s retry changed one harness parameter (§4.2), and is labelled
  as such everywhere.

---

## 3. The small-context fixture and the 35 000-token package

The full-fixture package for `fixtures/crate-v1.werk` measures **107 388 prompt
tokens** — LM Studio's own count for the exact message, not an estimate. That
is a 409-second cold prefill on this box and it locks out every model with a
smaller window. Gregor's instruction was to make the test work in **under
35 000 tokens**. So the *fixture* shrank; the specification's role in it did
not.

**`gauntlet/roundOW/mini-v1.werk`**, built deterministically by
`gauntlet/roundOW/build_mini_fixture.py` from bytes that already live inside two
pinned committed fixtures (`fixtures/crate-v1.werk` and
`tests/fixtures/crate.werk`). **Neither pinned fixture was touched**, and no
payload byte was invented.

| | |
|---|---|
| bytes | 938 756 |
| sha256 | `86dec8c0fb1e4d28c24b8ca6c537c9dec4753df577d786910531d65a6db75713` |
| zip entries / nodes / declared files | 34 / 14 / 32 |
| manifest | 22 819 B, sha256 `5c89625a5cce2cdac0662c3a4d8424225641dff9af25526233156aaace70daa1` |
| `spec_sha256` | `4e564bc487c0cb39bd1e79930bccd662c050507560ca60c768b1540b6a892d8d` (recomputed over the trimmed spec/ tree it actually carries) |
| signature | **`signed-and-valid`**, verified independently with `store/werkstore/signature.py` |

It keeps one mesh (`geometry/game.glb`), one sound family (a `core.audio.effect`
with a descriptor, a best take, a raw take and two variations), one material,
bounds, semantics, provenance, one PNG under an `x.` namespace so law 12 is
still exercised, **one binary envelope** (`poses/rest.wkrp`, WKRP, 560 B — the
clause that forces the layout grammar to be read, per S-XV-5), and the full
`core.spec` / `core.loader` / `core.license` / `core.readme` set so it is a real
werk package that still carries its own specification and all three bundled
readers.

**The package** is a strict prefix of a documented priority order, with each
spec document cut to the sections the task needs:

| # | item | note |
|---|---|---|
| 1 | `README.txt` | complete |
| 2 | `MANIFEST.json` | **complete** |
| 3 | zip entry listing | all 34 entries: name, size, local-header offset, CRC-32, method |
| 4 | `MINI-SPECS.md` §§1, 2, 3, 5, 6, 11 | bit/byte order, UTF-8, JSON, **zip**, CRC-32, **SHA-256** |
| 5 | `ENVELOPE.layout.txt` §§0–7 | the whole normative grammar; §8, the decision log, cut |
| 6 | `restposes.layout.txt` | complete |
| 7 | hex heads, **256 B each** | `game.glb`, the WAV, `rest.wkrp`, `seg_00.png` |
| 8 | `MINI-SPECS` §§9, 10, 12, 8 | WAV, GLB, Ed25519, PNG |
| 9 | `spec/README.md`, `conventions-map.json`, `SIGNATURE.json`, `LICENSE` | complete |

Nothing was omitted: all 17 items fit. **91 059 characters = 31 490 prompt
tokens** (`qwen/qwen3-coder-30b`'s tokenizer; 2.97 chars/token). Per-model
counts, from each run's own preflight, span **28 220 – 33 044** — different
tokenizers, same package. `spec/SPEC.md` and the JSON schemas are inside the
file but **not** in the package; that omission is where two of this round's
findings come from.

> **The number Gregor asked for: the crate task is solvable from 31 490 tokens
> of inlined self-description.** Four of six models did it. That is an upper
> bound on the format's minimum sufficient spec for this task, not a tight one —
> nobody bisected it downward, and §5 shows the envelope clause needs *more*.

---

## 4. Primary arm — round 1's task, on `mini-v1.werk`

Graded by artifact: the orchestrator hashes the bytes each run left on disk
against `MANIFEST.json` **and** re-runs the final program in a clean directory
containing only the fixture (`gauntlet/roundOW/grade.py`). Nothing below is
taken from a model's own report.

| model | attempt 1 | retry | **final** | iterations → first clean run | harness wall |
|---|---|---|---|---|---|
| **qwen3-coder-30b** | **PASS** | — | **PASS** | 4 → clean at 3 | **74.0 s** |
| **glm-4.7-flash** | FAIL `no-program` | **PASS** (changed cap, §4.2) | **PASS\*** | 5 → clean at 2 | 474.1 s / **1152.5 s** |
| **ebai3.6-27b** | FAIL `no-program` | **PASS** | **PASS** | 4 → clean at 2 | 1496.1 s / **724.6 s** |
| **glm-4.6v-flash (9.4B)** | FAIL (empty artifact) | **PASS** | **PASS** | 6 → clean at 3 | 349.4 s / **435.4 s** |
| **llama-3.1-8b (8B)** | FAIL (never opened the container) | PARTIAL | **FAIL** | 8 → clean at 7 | 644.4 s / **288.6 s** |
| **qwen3.8-4B** | FAIL `iteration-cap` | FAIL `iteration-cap` | **FAIL** | 8 → never | 1268.9 s / 593.7 s |

`PASS` = the final program, re-run in a clean directory, wrote both payloads and
both digests equal the manifest's declared values:
`geometry/game.glb` → `eee8b3cb…4ef2ce`, `audio/sfx/crate-impact-hard-surface.wav`
→ `1e634f03…59aa5e`. Both are the **same digests the OpenAI and Moonshot agents
produced** in the cross-vendor round, on a different fixture built from the same
bytes.

### 4.1 Where each failure happened, precisely

* **qwen3.8-4B — the zip container, and it never got past it.** Both runs, all
  16 iterations: it declined `zipfile` and hand-rolled a reader, and its
  end-of-central-directory scan never found the EOCD — `ValueError: EOCD not
  found`, iteration after iteration, with `MINI-SPECS` §5 and a complete entry
  listing *with offsets* sitting in its context. Later iterations degraded into
  `SyntaxError: expected 'except' or 'finally' block`. It never read a byte of
  the manifest. **Failure layer: the container.**
* **llama-3.1-8b, attempt 1 — it never opened the zip at all.** Its program
  called `json.loads()` on the whole `.werk` file, as if the container *were*
  MANIFEST.json, and did so for eight iterations while the traceback said
  `'utf-8' codec can't decode byte 0x9a in position 15` every time.
  **Failure layer: the container.**
* **llama-3.1-8b, retry — the near miss, and it is a spec finding.** This time
  it opened the zip, walked `nodes[].versions[].files[]`, extracted
  `geometry/game.glb` **byte-exact**, then for the sound followed
  `primary.sound` → node → `files[0]` and wrote out
  `audio/sfx/crate-impact-hard-surface.json`, the **descriptor**, not the WAV.
  The node declares `role`: `descriptor`, `best`, `raw`, `variation`,
  `variation`. Nothing at `primary` says to select by role. This is
  **S-XV-4/S-13 with a measured consequence** (S-OW-2).
* **glm-4.6v-flash, attempt 1 — a clean run that did nothing.** Its program
  exited 0, printed a listing and "Integrity verification PASSED", **wrote no
  files**, and the model then declared TASK COMPLETE. The harness's
  exit-code-zero signal is not a success signal, which is exactly why grading is
  by artifact. On retry it extracted both payloads correctly.
* **ebai3.6-27b, attempt 1 — a code-generation defect, not a format problem.**
  Five consecutive iterations died on the same `SyntaxError: unterminated string
  literal` at a report-writing call, with the exact traceback fed back each
  time; iterations 6–8 collapsed into truncated and empty replies. On retry the
  same model was clean at iteration 2.
* **glm-4.7-flash, attempt 1 — the reasoning budget ate the answer.** Three
  replies, each `finish_reason="length"` at the 16 384-token cap with **zero
  characters of content**: the whole budget went into the reasoning channel,
  which LM Studio does not return in `content`. Nothing about werk was involved.

### 4.2 The one changed parameter, stated plainly

`glm-4.7-flash`'s retry raised the generation cap from 16 384 to 32 768 tokens.
That is a **harness** change, not a second roll of the same dice, and it is why
that row is marked `PASS*`. With the larger cap it produced a working program at
iteration 2 (both digests correct). Its run then ended in
`api-error`: at iteration 5 LM Studio returned **HTTP 400, "Failed to parse
input at pos 0"** on the conversation containing its own earlier reply — a
serving-stack failure re-ingesting reasoning text, recorded as S-OW-5. The
grade stands on the artifact its iteration-2 program produces when re-run
clean.

### 4.3 The signature: every model got it wrong, and the specification is why

`mini-v1.werk` is validly signed — `store/werkstore/signature.py` returns
`signed-and-valid`. Models that touched the signature reported **"Signature
verification FAILED"**, i.e. `present-and-invalid`: *tampering on an intact
package.* That is the most dangerous wrong answer available.

They had `MINI-SPECS` §12, which explains Ed25519 the primitive. They did not
have the sentence that says **what werk signs**:

```
werk-sig/1 LF manifest_sha256 LF prev_entry_sha256 LF signed_at LF signer.uri LF signer.kind
```

The string `werk-sig/1` occurs in exactly two files in the package —
`spec/SPEC.md` and `spec/schemas/signature.schema.json` — and **neither is in
the 31 490-token package**. A reader on this documentation budget can verify
every hash and cannot verify the signature. The specification even provides the
right vocabulary for that situation — §7's fourth token, `unverified` — and
nothing in the package told these models to reach for it. This is **S-OW-1**,
and it is the sharpest instance of the round's central question: *how many
tokens of specification does the format need before it is implementable?*

---

## 5. Second arm — the envelope task (spec-forcing)

S-XV-5 established that round 1's success criteria are satisfiable from
`MANIFEST.json` alone, so a second task is needed that **cannot** be. The splat
task is that task, but `fixtures/gsplat-v1.werk`'s package does not fit the
35 000-token budget. The equivalent inside `mini-v1.werk` is its WKRP envelope,
so the splat prompt was **adapted** — same three-clause structure, same
constraints, same reporting demands — as
`gauntlet/roundOW/PROMPT-envelopetask-mini.txt`. **It is not verbatim, and the
result is therefore not directly comparable to round 3 or to the cross-vendor
splat runs.**

Ground truth, decoded independently by the orchestrator from the same 560 bytes:
`pose_count = 2`, `contact_count = 7`, `trials = 4096`, two declared sections
(`poses`, record, offset 400, stride 32; `contacts`, f32, offset 464, shape
[7, 3]).

| model | clause 1 (open, list, verify) | clause 2 (**decode the envelope**) | clause 3 (identify the bundled readers) | wall |
|---|---|---|---|---|
| qwen3-coder-30b | PASS | **FAIL — fabricated** | PASS | 50.7 s |
| llama-3.1-8b | FAIL | FAIL | FAIL | 330.4 s |

**The 30B coder's failure is the interesting one.** It found `WKRP`, read
`version = 1`, and then printed this in its own output:

> "Note: Actual MessagePack parsing would require a proper parser / This is a
> demonstration of what we can extract from the binary structure"

— and proceeded to print quaternion components like
`71554213196777853550592.0000` and a probability of
`16483728578930181931008.000000`, read from guessed offsets. It never reported
`pose_count`. It had `ENVELOPE.layout.txt` §4, *"The MessagePack subset used by
werk headers"*, in its context, and declined to implement it. **It labelled the
output "demonstration" and printed it as data anyway.**

What it did not have: `spec/examples/restposes.example.hex.txt` — a worked,
annotated hex decode of exactly this envelope kind, which exists inside
`fixtures/crate-v1.werk` and which the mini fixture's trimmed `spec/` tree
dropped. **S-OW-3.**

`llama-3.1-8b` never reached the envelope: eight iterations, no clean run,
failing again at reading the manifest.

---

## 6. Findings

**S-OW-1 — the signed-message construction is outside the small documentation
set, and guessing it produces a false tampering alarm.** `werk-sig/1 LF
manifest_sha256 LF …` appears only in `spec/SPEC.md` and
`spec/schemas/signature.schema.json`. `MINI-SPECS` §12 documents Ed25519 the
primitive and stops. Every model in this round that attempted the signature
reported `present-and-invalid` on a package that is `signed-and-valid`.
*Proposed fix:* put the six-line message construction into `MINI-SPECS` §12
itself — it is four lines of text — and have §12 say in one sentence that
`unverified` is the correct verdict when the construction is not available.
**Severity: high.** A format whose damage report is wrong in the alarming
direction is worse than one that reports nothing.

**S-OW-2 — `primary.sound` names a node whose `files[]` begins with a
descriptor, and an 8B model extracted the descriptor.** Measured, not
hypothetical: `audio/sfx/crate-impact-hard-surface.json` was written where a WAV
was asked for, by a program that had already extracted the mesh byte-exact.
This is the successor case to S-13 and the concrete instance of **S-XV-4**.
*Proposed fix:* either `primary` names a file path, or the manifest states at
`primary` that selection within the node is by `role: "best"`. **Severity:
high** — it is the only case in the round where a model produced a wrong
artifact while believing it had succeeded.

**S-OW-3 — the worked example is the rung between "grammar" and "decoder", and
it was the thing that was missing.** `ENVELOPE.layout.txt` §4 is a complete
MessagePack subset; the strongest model in the round read it and declined to
implement it. `spec/examples/restposes.example.hex.txt` — an annotated byte-by-byte
decode of a WKRP — exists in the full fixture and would have cost ~1 500 tokens.
*Proposed fix:* treat the worked hex example as **part of the minimum set for any
package carrying an envelope**, not as an optional extra. **Severity: medium**,
and it is a finding about *packaging the spec*, not about the spec's content.

**S-OW-4 — the container is where small models die, and the entry listing did
not save them.** Both sub-9B failures were at the zip layer: one never opened
the container, the other could not find the EOCD in sixteen tries. Both had
`MINI-SPECS` §5 *and* a complete entry listing with local-header offsets. The
spec is not wrong; the observation is that **the cheapest correct path — "this
is a store-mode zip, `import zipfile` reads it" — is not stated as such
anywhere.** `README.txt` describes the container in prose. *Proposed fix:* one
line in `README.txt` and in `MINI-SPECS` §5: *in a language with a zip library,
open it with the zip library; the hand-rolled path below is for languages
without one.* **Severity: medium.** This is the graded-effort doctrine applied
to the reader's first five minutes.

**S-OW-5 — serving-stack failure modes are not model failure modes, and this
round hit two.** (a) A reasoning model can spend an entire generation budget in
the reasoning channel and return **zero characters** of content, three times in
a row; the harness sees a model that will not answer. (b) LM Studio returned
HTTP 400 *"Failed to parse input at pos 0"* when a conversation containing that
model's own earlier reply was re-sent. Neither is about werk. Recorded because
any future open-weights round will hit them, and because a harness that scores
them as format failures would be measuring the wrong thing.

**S-OW-6 — "exit code 0" is not "did the job", and one model proved it.**
`glm-4.6v-flash`'s first run produced a program that exited 0, printed
"Integrity verification PASSED", wrote nothing, and was declared complete by its
author. Grading by artifact caught it; grading by self-report or by exit status
would not have. This is the cross-vendor round's grading rule earning its keep
at a lower capability rung.

---

## 7. Discussion — where the ladder now stands

Read §0b first: the format can only remove requirement (1), knowledge, and this
protocol supplied (2) hands and (3) working memory. So each failure is a probe
of whether the knowledge barrier is actually zero at that capability level.

Triaging the six failures on exactly that question:

| failure | was the needed fact present, findable and unambiguous? | verdict |
|---|---|---|
| 4B: EOCD never found | yes — `MINI-SPECS` §5 plus every offset | **capability**, not knowledge |
| 8B attempt 1: `json.loads` on the container | yes — same | **capability** |
| 8B retry: descriptor extracted as the sound | **no** — `role` is declared but nothing says `primary` selects by it | **knowledge barrier ≠ 0** (S-OW-2) |
| every signature verdict | **no** — the construction is in a file that did not fit | **knowledge barrier ≠ 0** (S-OW-1) |
| 30B coder: fabricated envelope values | partly — the grammar was there, the worked example was not | **knowledge barrier ≠ 0** (S-OW-3) |
| 27B syntax loop, glm-4.7 empty replies | not applicable — no werk fact was in play | **capability / serving stack** |

That is the useful shape of the result. **The pure-capability failures are
concentrated below 9B and are about writing correct Python, not about
understanding werk.** The knowledge-barrier failures are concentrated in exactly
three places, all three are small documentation edits, and all three were
invisible to frontier agents that had the whole specification in front of them.
**Small models are a better instrument for finding spec gaps than large ones**,
because a large model routes around a missing sentence and a small one does
not.

And the size threshold, stated as measured: **success is available from 9.4B
upward** (9.4B, 27B, 30B, 30B all passed with one retry), **degrades at 8B**
(container reached, manifest read, mesh byte-exact, wrong file for the sound),
and **is absent at 4B** (container never opened, in sixteen attempts). One model
per class, so this is a threshold *observed*, not a threshold *established*.

**What it does to the implementer-diversity threat.** The cross-vendor round's
verdict was that the threat was softened, not removed, because both vendors were
frontier commercial models inside agentic harnesses. That is no longer the case:
the round now includes a 30B MoE coder, a 30B reasoning MoE, a 27B dense
uncensored finetune, a 9.4B vision-language model and an 8B non-coder generalist
— five weight classes, four architectures, four training lineages, none of them
ours, none of them agentic, all of them running locally with no network. Four of
them produced byte-exact artifacts. **A shared blind spot across that set and
across GPT-5.6, Kimi and Claude is not a credible explanation of the result any
more.** The threat is materially reduced.

What it does **not** do: it does not extend the claim downward. Below 9B the
honest statement is that **this protocol** did not get a working reader out of
these particular models — and per §0b that is a statement about the rung, not
about the format, since the very next rung down (a human supplying hands and
judgement) is untested and, by the graded-effort argument, would reach the
preview and loader tiers trivially. Nothing here is evidence about the
twelve-year-old.

---

## 8. Verdict on the pre-registered predictions

Registered 2026-08-08T21:07:30Z, before any run. §0.

**Gregor's prediction — zero failures across all models on both tasks —
is FALSIFIED.** The deciding runs are `qwen4b__mini` and `qwen4b__mini__retry`
(4B, sixteen iterations, no runnable program, both runs) and
`llama31-8b__mini__retry` (8B, wrong file extracted for the sound). The second
task falsifies it a second time and more sharply: `qwen3coder30b__envel`, the
round's strongest model on its easiest run, **fabricated** the envelope values.

**The coordinator's counter-prediction is half-supported, and its deciding cell
is confirmed.** It called "near-universal success on the crate task": 1/6 first
attempt and 4/6 with retries is not near-universal, so that half is wrong. It
called "at least one failure in the ≤8B class on the spec-forcing task", and
that is exactly what `llama31-8b__envel` did — eight iterations, no clean run.
Its stated reasoning — that the binding constraint is the long-horizon,
exact-offset work rather than encoding familiarity — is also what the failure
distribution shows: the encodings really were familiar (four models read the
zip, the JSON, the GLB and the WAV without a stumble), and the two things that
defeated everyone were the **binary envelope** and the **signature
construction**.

**So Law 11 does not gain the empirical support Gregor's prediction would have
given it — but it is not refuted either, and the way it survives is worth
stating.** Every failure of a *boring* encoding in this round was a capability
failure at 8B and below; not one model above 9B stumbled on zip, JSON, GLB, WAV
or SHA-256, which is precisely what "boring encodings are already in the
training data" predicts. What broke were the two places where werk is **not**
boring: its own binary envelope, and its own signed-message construction. Law 11
is doing its job exactly where it applies, and the round's findings are all from
the edges where it does not.

---

## 9. Where everything lives

| what | path |
|---|---|
| the harness (operative) | `gauntlet/roundOW/driver.py` |
| the discarded tool-loop harness | `gauntlet/roundOW/driver_toolloop.py` + `_discarded/` |
| context-length probe | `gauntlet/roundOW/prefill_probe.py` |
| the small fixture's builder | `gauntlet/roundOW/build_mini_fixture.py` |
| the small fixture | `gauntlet/roundOW/mini-v1.werk` |
| artifact grader | `gauntlet/roundOW/grade.py` |
| per-run driver | `gauntlet/roundOW/run_one.sh` |
| prompts | `PROMPT-round1task.txt` (verbatim source), `PROMPT-round1task-mini.txt` (filename only), `PROMPT-gsplattask.txt`, `PROMPT-envelopetask-mini.txt` (adapted) |
| every run's row, program, package and transcript | `gauntlet/roundOW/runs/<tag>/` |

