# Stage GAP-FILL results — the three holes in the gauntlet's coverage matrix

**Author:** the gap-completion agent. **Owns for this wave:**
`gauntlet/roundGF/`, `results/STAGE-GAPFILL-RESULTS.md`, the gap-completion
rows in `gauntlet/RESULTS.md`, and the gap-completion addendum in
`paper/v2/NUMBERS.md` and `paper/v2/CHANGES.md`. It writes nowhere else. A
second agent was adding `gauntlet/roundDS/` during this wave; there is no
overlap.

**Date:** 2026-08-09.

> **Note on `paper/v2/NUMBERS.md`.** This round's numbers block (§5.10) was
> appended to that file and is **on disk but deliberately NOT in this round's
> commit**. When staging, `git diff --numstat` showed `151 insertions, 50
> deletions` for `NUMBERS.md` against roughly 48 lines of mine — i.e. another
> agent has uncommitted work in it during this wave. Rule 4 of
> `results/README.md` is "commit by explicit path, never `git add -A`", and its
> stated reason is that a wildcard commits somebody else's half-finished work
> under your message; committing a *file* that contains somebody else's
> half-finished work is the same act with extra steps. `paper/v2/CHANGES.md`
> was a clean append (`55 / 0`) and **is** committed. Whoever next commits
> `NUMBERS.md` will carry §5.10 with it.

Every round so far ended with a verdict naming what it did not establish. This
round takes three of those sentences and tries to close them. It closes one
completely, and turns the other two into measurements that say the gaps are not
where anybody thought they were.

---

## 0. Headline

| | |
|---|---|
| **The finding of the round** | **S-GF-1** — the open-weights round's `mini` context packer silently dropped **every byte of every layout grammar**. Its spec-forcing envelope arm's `0 / 2` was measured against a package that advertised the grammar in its own banner and shipped an empty section. Verified against the committed `gauntlet/roundOW/context_package.mini.txt`. |
| **Job 2 — hardcopy replication, second vendor** | **SUCCESS. 6 / 6 rungs, first attempt, 1367.4 s.** `recovered.werk` byte-identical to the printed payload; the smiley PNG byte-identical. Two vendors now. |
| **Job 1 — splat task on local models** | see §2. The arm's headline is **not** a pass rate: with S-GF-1 fixed, the splat task's minimum self-description is **65 775 tokens**, and on a 24 GB card that excludes every 27–30B model in the roster by KV residency, measured. |
| **Job 3 — adapted self-run on a local model** | **FAIL**, and the reason is specific: `qwen3-coder-30b` predicted the build command, the runner `argv` and the right expected digest correctly, then compiled a path that does not exist because **it never opened the container**. §4 |
| Splat arm, graded | **2 models run, both FAIL**; 3 of 5 could not be served the package on 24 GB. **No `n/5` is reported** — that would be a hardware number wearing a capability number's clothes. §2.5 |
| Runs discarded ungraded, both for **harness** defects, both kept | **2** — a 262144 context that never returned an iteration (§2.4), and a WSL bash with no compiler (§4.2) |
| Grader defects found and fixed **before** a result was recorded | **1** — `grade_selfrun.py` was calling an echoed answer key a PASS (§4.3) |
| Splat context package | **166 642 characters**, **65 775 tokens** (`google/gemma-4-e4b`'s tokenizer), 12 of 12 items, nothing omitted |
| Harness changes, all declared | **GF-1** third context packer · **GF-2** S-SFX-4 applied (`PYTHONIOENCODING=utf-8`) · **GF-3** console echo kept · **GF-4** the S-GF-1 fix |
| Serial LM Studio | enforced throughout: `lms unload --all` before every load, `--parallel 1`, one model resident, one request in flight |
| Grading | by artifact, always: `gauntlet/roundGF/grade_gsplat.py`, `grade_hardcopy.py`, `grade_selfrun.py`, each deriving ground truth from the pinned fixture rather than hard-coding it |

---

## 1. S-GF-1 — the open-weights round's package had no layout grammar in it

**Severity: high. It invalidates one previously-reported diagnosis and it
changes what one previously-reported number means. Fixed in this round's
harness (GF-4); `gauntlet/roundOW/driver.py` is left as it was, because it is
the record of what those runs actually received.**

`pack_context_mini()` cuts each spec document to the sections a task needs,
through two helpers:

```python
def sections(text, pattern):
    """Split a spec document into (heading, body) by a heading regex."""
    ...
def pick(text, pattern, wanted):
    got, keep = sections(text, pattern), []
    for h, body in got:
        n = re.match(r"^[#\s]*(\d+)\.", h)      # <-- the bug
        if n and int(n.group(1)) in wanted:
            keep.append(body)
    return "".join(keep)
```

`re.match` anchors at the start of the whole matched heading. A `MINI-SPECS.md`
heading is `## 5. zip`, and `^[#\s]*(\d+)\.` matches it. A layout-grammar
heading is three lines:

```
------------------------------------------------------------
3. The header map
------------------------------------------------------------
```

`.strip()` leaves that starting with a dash, `re.match` fails, and **every
section of every `.layout.txt` file is dropped**. Measured against the fixture
those runs used:

```
roundOW pick(ENVELOPE, 0..7) -> 0 chars
roundOW sections(ENVELOPE)   -> 9 sections found
  heading repr: '------------------------------------------------------------'
roundOW pick(MINI-SPECS, {5}) -> 7973 chars
```

Nine sections found, zero kept. And the committed package proves it shipped
that way — `gauntlet/roundOW/context_package.mini.txt`, at the envelope banner:

```
===== FILE spec/layouts/ENVELOPE.layout.txt -- SECTIONS 0 to 7 ONLY (the whole normative grammar; section 8, the decision log, was cut). =====
werk binary envelope - layout grammar v1

===== FILE spec/layouts/restposes.layout.txt (complete) =====
```

One synthesized title line, then the next file. **The banner claims the whole
normative grammar and delivers nothing.** `restposes.layout.txt` survived only
because it is read whole rather than through `pick`.

**Why nothing caught it.** The item was *included*, not *omitted* — the block
existed, it was merely empty — so the package header said `Included: 18 of 18
items`, `run.json`'s `included` list named the envelope, `omitted` was `[]`, and
the console said `omitted=0`. Every instrument in the harness reported success.
The strict-prefix budget machinery, which exists precisely so that "what this
model received" is a describable quantity, described it wrongly.

**What it changes in the ledger.**

* **S-OW-3's first clause is wrong.** It reads *"the binary envelope. The
  grammar was in the package; the **worked hex example** was not."* The grammar
  was not in the package either. The models that failed the envelope task were
  asked to decode a MessagePack-headed binary having been shown the magic, the
  hex head and the manifest — and no grammar at all.
* **The post-fix arm's envelope conclusion needs re-reading.** S-OW-3's fix
  added `spec/examples/restposes.example.hex.txt` as an eighteenth item. On this
  measurement, that worked hex example was not the *rung above* the grammar; for
  the whole of both arms it was **the only envelope information present**.
* **The round-1 task arm is unaffected.** That task decodes zip, JSON, GLB and
  WAV, whose mini-specs came through `MINI-SPECS.md` and `pick` correctly. Both
  passing digests are unchanged and remain the same two the other five rounds
  produced.
* **`pack_context()` — the non-mini packer used for `crate-v1.werk` and
  `gsplat-v1.werk` — never called `pick`.** It inlines whole files. So the
  cross-vendor and round-1/2/3 packages are untouched by this.

**The general lesson, which is the uncomfortable half.** The harness's own
self-report is not evidence about the harness. Every round has enforced "an
agent's report is evidence about the agent, not about the artifact"; this is the
same rule applied one level up, and it went unenforced for two arms. *Proposed:*
`_assemble()` should refuse to include a block whose body is shorter than some
floor and should record it in `omitted` with the reason. **Open**, filed for
Gregor, not applied to `roundOW/driver.py` because that file is the record of
what those runs received and editing it would destroy the evidence.

---

## 2. Job 1 — the splat task on the passing local models

### 2.1 What the arm is

Round 3's splat task, `gauntlet/roundGF/PROMPT-gsplattask.txt`, **verbatim** —
byte-identical to `roundOW/PROMPT-gsplattask.txt` and to the sentence both
cross-vendor vendors were given. Three clauses: open and list with meanings and
verify integrity; extract the point positions and colours and say how many
points; identify the tools that made the file, say what each does, and show
their source.

Fixture: `fixtures/gsplat-v1.werk`, sha256
`ede0aee6cc5659af741059b747dc3f3459db220234e7ffb95c4437c02337090a`, 30 235 611
B, 85 entries. Protocol: roundOW's, unchanged except GF-1…GF-4 — no tools, the
whole self-description inlined, one complete Python program per turn, the
harness runs it in an isolated directory against the real fixture and feeds back
stdout/stderr/traceback, 8 iterations or 45 minutes, cold start per run.

### 2.2 Ground truth, derived not asserted

`grade_gsplat.py` decodes the fixture itself, with its own MessagePack and
envelope reader, by the normative path (`gsplat.layout.txt` §5 and §7):

```
ground truth   : count=281498  declared_files=81
  WKGS means == WKPC position bytes : True
  colours recomputed from sh-dc     : 281498 / 281498 match
  point[0] pos = -0.06007473 1.62525749 0.93507129   col = 39 19 6
```

That is **a sixth independent reproduction** of round 3's row 0 — round 3's own
agent, `gpt-5.6-sol`, `kimi-for-coding`, and now this round's grader, all
printing `-0.06007473 1.62525749 0.93507129 -> 39 19 6` and `281 498`.

### 2.3 The package, and the number that decided the arm

With GF-4 applied, the complete package is **213 737 characters ≈ 95 000
tokens**. Trimmed to the items the three task clauses can actually use — README,
the complete MANIFEST, the complete zip listing, MINI-SPECS §§1–6 and 11, the
ENVELOPE grammar §§0–7, the **gsplat** grammar §§0–8, the **points** grammar
§§0–7, the worked WKGS hex decode, two hex heads, `semantics.json` and
`conventions-map.json` — it is:

| | |
|---|---|
| characters | **166 642** |
| items | **12 of 12, nothing omitted** |
| tokens, `google/gemma-4-e4b` | **65 775** (2.57 chars/token) |

Cut, and recorded as cut rather than as silence (S-GF-1's lesson): MINI-SPECS
§12 (Ed25519 — the task does not ask for the signature), the WKEM worked example
(an envelope kind this file does not contain), `LICENSE`, `SIGNATURE.json`,
`spec/README.md`, `recipe/recipe.json`, `provenance/provenance.json`, and the
hex head of the *ingested* `.splat` input.

**65 775 tokens is the arm's real headline.** The previous rounds' budget was
35 000, and Gregor's ruling for this round was that the splat package may exceed
it — record the size, these models load ≥ 64k. It exceeds it by 1.9×, and the
consequence is not about loading.

### 2.4 The serving measurement, which is why three models are not in the table

All on this box: RTX 4090, 24 564 MiB, one GPU, nothing else resident
(1 297 MiB of desktop).

| model | weights | loaded ctx | prompt | cold prefill | tok/s |
|---|---:|---:|---:|---:|---:|
| `qwen/qwen3-coder-30b` Q4_K_M | 18.63 GB | 262144 | 69 485 | **253.4 s** | **274** |
| `qwen/qwen3-coder-30b` Q4_K_M | 18.63 GB | 131072 | 69 485 | **241.8 s** | **286** |
| `qwen/qwen3-coder-30b` Q4_K_M | 18.63 GB | 65536 | 30 715 (roundOW's package) | **8.2 s** | **3 751** |
| `google/gemma-4-e4b` | 6.33 GB | 131072 | 65 775 | **8.8 s** | **7 474** |

The 30B *loads* at 262144 — `lms load` reports success in 25.4 s — and then
prefills 13.7× slower than the same model at 65536, because at 65536 the KV
cache fits in the 5.9 GB the weights leave and above that it does not. This is
roundOW's own measured rule ("the largest context that does not collapse is what
gets loaded") arriving at a harder conclusion: **a 65 775-token prompt needs a
context ≥ 98 304, and a 27–30B Q4 model on a 24 GB card cannot serve one at
speed.** `gemma-4-e4b`, at 6.33 GB, serves the identical prompt **27× faster**.

A first run was started at 262144 under the round's normal 45-minute cap and
**killed after 75 minutes without iteration 1 returning**. It is kept, ungraded
and unscored, as `_discarded-ctx262144` — a discarded protocol is part of the
experimental record (roundOW's `driver_toolloop.py` precedent).

*This is a hardware result, not a format result, and not a model result.* It is
recorded here because the alternative — quietly running the 30B models at a
context that cannot hold the package, or quietly shrinking the package until it
fits — is exactly the class of silent substitution S-GF-1 is about.

### 2.5 The roster, and which of it could be run

The five models named for this arm are the ones that have ever passed anything
in an open-weights round — `qwen/qwen3-coder-30b`, `zai-org/glm-4.7-flash`,
`ebai3.6-27b-unscensored`, `zai-org/glm-4.6v-flash` and `google/gemma-4-e4b`.

| model | weights | can hold a 65 775-token prompt on 24 GB? | run |
|---|---:|---|---|
| `google/gemma-4-e4b` | 6.33 GB | **yes** — ctx 131072, prefill 7 474 tok/s | **run** |
| `zai-org/glm-4.6v-flash` | 11.79 GB | **yes** — ctx 131072, prefill 3 984 tok/s | **run** |
| `qwen/qwen3-coder-30b` | 18.63 GB | **no** — needs ctx ≥ 98 304; measured 274–286 tok/s there vs 3 751 at 65536 | **not run**, §2.4 |
| `zai-org/glm-4.7-flash` | 18.13 GB | **no** — same class | **not run** |
| `ebai3.6-27b-unscensored` | 18.46 GB | **no** — same class | **not run** |

**No `n / 5` pass rate is reported.** Three of the five were excluded by KV
residency on a 24 GB card, which is a statement about this box and not about
those models, this task or werk. Reporting `0 / 5` or `0 / 2` as *the* number
would be the same category error as reporting a serving-stack failure as a
model failure, which S-OW-5 exists to forbid.

### 2.6 The two runs, graded by artifact

Both graded by `gauntlet/roundGF/grade_gsplat.py`, which was itself self-tested
first: fed a reference artifact built from its own ground truth, it returns
`VERDICT: PASS`, so a `FAIL` below is a statement about the run and not about
the grader.

| | `google/gemma-4-e4b` | `zai-org/glm-4.6v-flash` |
|---|---|---|
| class | 7.5 B raw / "effective 4B", `gemma4` | 9.4 B, `glm4`, Q8_0 |
| loaded context | **131 072** | **131 072** |
| package, its own tokenizer | **65 775** tokens (2.57 chars/token) | **55 376** tokens (3.05 chars/token) |
| cold prefill | 8.8 s (**7 474 tok/s**) | 13.9 s (**3 984 tok/s**) |
| outcome | iteration-cap, **8 / 8 used** | iteration-cap, **8 / 8 used** |
| first clean run | **never** | iteration **1** |
| wall (harness-measured) | **749.2 s** | **1 489.4 s** |
| truncated replies (`finish_reason=length`, 0 chars) | 0 | **3** |
| opened the container | **never, in any of 8 programs** | yes, iteration 1 |
| point count | claimed, from the manifest | not reached |
| positions / colours | **none** | **none** |
| tools named / paths / source quoted | named ✓, paths ✓, **source ✗** | **✗ / ✗ / ✗** |
| **verdict** | **FAIL** | **FAIL** |

**`gemma-4-e4b` never opened the file.** Measured directly: across all eight
generated programs, `grep -c "import zipfile\|zipfile.ZipFile\|gsplat-v1.werk"`
returns **0, eight times out of eight**. Instead it transcribed the inlined
context package into Python literals — iterations 6, 7 and 8 are 36–38 KB
programs that are mostly a hand-copied `MANIFEST.json`, and each one died on
`SyntaxError: '{' was never closed`. It said why in its very first reply, before
any feedback existed:

> "Since actual binary reading/execution is forbidden and only file contents are
> visible, the program **simulates** the analysis by extracting structured
> information from the manifest and associated documentation files."

That is **S-GF-2**: the isolation clause *"do not execute anything that came out
of the file"* was read as *"do not read the file"*, and the 65 775-token inline
package was read as the corpus rather than as documentation of an artifact on
disk. The system prompt states the opposite in the second sentence — *"your
program will be run in a directory that contains exactly one other thing, the
file named in the task"* — and eight rounds of feedback did not dislodge it.

**`glm-4.6v-flash` opened the container and stalled one layer in.** Its first
program ran clean at iteration 1: it listed the entries, then died inside its
own integrity pass on `'ZipFile' object has no attribute 'file_size'`, and
across seven revisions it never got past that line to the envelope, the points
or the tools. Its final output is 737 B: a contents listing in which fourteen
entries are labelled `Unknown entry`, and `Error processing file` where the
hashes should be. **Three of its eight iterations returned `finish_reason=length`
with zero characters of content** — S-OW-5's reasoning-model failure mode,
reproduced, and it cost this run 37 % of its iteration budget.

### 2.7 What the arm establishes and what it does not

**Establishes.** The spec-forcing task remains unpassed by any local model, now
on a second task and two more model families, and **for the first time the
package the models were given actually contained the layout grammars** — which
means this is the first honest measurement of that cell in any round. The two
failures are of different kinds and neither is a knowledge barrier: one model
never read the artifact at all, the other read it and could not sustain a
correct program across eight revisions. Under S-SFX §4.4's triage, both are
**capability**, and under §6's ruling both are the void condition — no shell, no
scratch space, no supervision — which is the weakest rung of the ladder by
construction.

**Does not establish.** Nothing about the 27–30B class on this task: those three
models were never served the package. Nothing about a pass rate. And the two
runs used the 8-iteration cap rather than roundOW's attempt-plus-retry, so there
is no retry column; roundOW's own data says the retry is where four of its six
passes came from, so a retry arm would be the cheapest next measurement.

---

## 3. Job 2 — the hardcopy round, replicated on a second vendor

**The gap, in the hardcopy round's own words:** *"What it does not establish:
N = 1, one vendor."*

### 3.1 Protocol

`gauntlet/roundGF/run_kimi_hardcopy.sh` is `gauntlet/roundHC/run_codex.sh` with
the CLI swapped and nothing else changed:

| | Codex arm (roundHC) | **Kimi arm (this round)** |
|---|---|---|
| CLI | `codex` 0.144.1, `gpt-5.6-sol`, effort `high` | **`kimi` 0.15.0** (Kimi Code CLI) |
| task sentence | `roundHC/PROMPT-archaeology.txt`, verbatim, committed before the run | **the same file, unchanged** |
| input | a fresh directory holding only the three **degraded** page JPEGs | **the same three files**, sha256 `a0631045…c726b54`, `fef9d5ed…45bf4c14`, `e25dad57…82727560` |
| format hint | none | **none** |
| cap | 60 min, `timeout` | **60 min, `timeout`** |
| clock | process wall clock | **process wall clock** |

The Codex-only `sandbox_workspace_write.exclude_*` settings were not ported:
they are a documented fix for a Windows restricted-token sandbox bug in Codex
specifically, and there is nothing in Kimi they correspond to.

### 3.2 Result

```
exit_code=0
wall_seconds=1367.4
```

Graded by `gauntlet/roundGF/grade_hardcopy.py`, from the bytes:

| rung | verdict |
|---|---|
| read the prose | **PASS** — it quoted the 8168-byte length, the 8-data-plus-1-parity structure and the printed SHA-256 before writing a decoder |
| implemented a decoder | **PASS** — `decoder.py`, 10 414 B, plus five analysis scripts, all from scratch |
| reassembled, CRCs pass | **PASS** — a per-symbol table, 8/9 matching the printed captions on the first pass |
| whole-file sha256 | **PASS** — `recovered.werk`, 8168 B, **byte-identical**, `b0823016…7617a6` |
| recognised and opened the `.werk` | **PASS** — all five entries extracted to `recovered_pkg/`, every digest re-verified against the manifest |
| **the recovered image IS the smiley** | **PASS** — `recovered_pkg/image/smiley.png` **byte-identical**, `9082008d…3d285` |
| the signature | **correctly declined** — see below |

**6 / 6, first attempt, 1367.4 s.** Codex was 5/5 in 206.7 s. Kimi is 6.6×
slower and arrives at the same bytes.

### 3.3 What replicated, and it is more than the pass

**S-HC-3 reproduced exactly.** The hardcopy round found that the *emptiest*
symbol is the hardest to read, because `seq 7` is mostly zero padding, so its
tiles have no contrast. Kimi lost exactly `seq 7` and nothing else — computed
CRC `DC2D2CC9` against the printed `E20A2CD2` — repaired it from the parity
symbol, and reported that the difference was 592 bytes, all of them padding past
the 8168-byte file length. Three independent decoders now (the reference
control, Codex, Kimi), one lost symbol, the same one.

**S-HC-4 / S-OW-1 reproduced on a fourth model family.** Kimi found PyNaCl,
built three candidate signed messages, got `Signature was forged or corrupt`
three times, and — like Codex, and unlike the pre-fix open-weights models —
**did not render a tampering verdict**. It reported the package's own README
sentence instead: the key is a publicly known dev key, so the chain is *evidence
of integrity and not of authorship*. The `werk-sig/1` construction lives in
`spec/SPEC.md` and the signature schema, neither of which is printed on the
sheets, and the reduced package vendors no `spec/`. **Three rounds, five model
families, still open.**

**Prior knowledge is still excluded by construction.** `werk-hardcopy/1` did not
exist before the hardcopy round; no library and no training corpus contains it.
Kimi's decoder is written from the printed prose or it is not written.

### 3.4 The one asymmetry, stated rather than buried

**Kimi had a network and used it.** It created a venv, failed to install into
it, then `pip install`-ed `numpy` 2.5.2 and `opencv-python` 4.13.0 into the
machine's user site-packages and used them. Codex had no network at all — the
hardcopy round records its `pip install` failing with *"no matching
distribution"* — and did the same job without them.

This is **tooling, not knowledge**, and the distinction is checkable rather than
asserted: there is no library anywhere that decodes `werk-hardcopy/1`, so
`opencv` supplied connected-component labelling and a JPEG decoder, not a single
fact about the code. But the two arms are therefore **not isolation-equivalent**,
and the honest form of the replication claim is: *a second vendor recovered the
printed payload byte-exactly from the printed prose, with more tooling and 6.6×
more wall clock.* A future arm that wants strict equivalence should run Kimi
behind a blocked network.

---

## 4. Job 3 — the adapted self-run arm

**The gap, in the self-run round's own words:** *"two frontier agentic models is
vendor diversity, not implementer diversity."* Both roundSR agents had a shell.
An LM Studio model does not.

### 4.1 The adaptation, and the doctrine question, stated before the result

roundOW's answer to "no shell" was *the model writes one Python program and the
harness runs it*. A **building** task cannot be squeezed into that shape without
changing what is measured: the interesting steps are `cl.exe` / `gcc` and an
`argv` line, not Python. So `gauntlet/roundGF/driver_selfrun.py`:

* inlines exactly what roundSR recorded as load-bearing — the zip entry
  listing, `README.txt`, `tools/llama2c/BUILD-AND-RUN.md`, the **complete
  source** of the embedded tool (`run.c`, `win.c`, `win.h`), its `tool.json` and
  run config, **both** layout grammars for the two foreign binary formats, the
  package's own `vectors.json` and both expected stdouts, and hex heads of the
  checkpoint and the tokenizer. **15 items, 97 181 characters.**
* **cuts `MANIFEST.json`, `recipe.json` and `provenance.json`**, on evidence
  rather than for room: roundSR records, for *both* successful agents,
  `opened MANIFEST.json: no` and `opened anything under spec/: no`, and names
  `BUILD-AND-RUN.md` as what unblocked both. The cut is stated in the driver, in
  `run.json`'s `items` and here — S-GF-1's lesson applied on the same day it was
  found. It does mean this arm exercises the build path and not the manifest,
  which is what roundSR's own verdict said its task exercised.
* has the model emit **one bash script**, which the harness screens and then
  **executes**.

**On "source always, never auto-execute".** That doctrine is about a package's
shipped binaries: a werk package carries source and no prebuilt artifact, so
nothing inside a file a stranger hands you runs unless a human decides it
should. This harness is that human's proxy. The source it compiles is `run.c`,
which roundSR established is byte-identical to llama2.c upstream and which is
committed in this repository and has been read; the script that compiles it is
statically screened for network use and for data paths outside the run
directory, is written to disk before it runs, and is committed with the run.
**A supervised harness compiling reviewed source is not a reader auto-executing
a stranger's binary.** What cannot be claimed from this arm is roundSR's claim:
this is not an unsupervised stranger, and every number below should be read with
that label attached.

### 4.2 The run that was thrown away, and why

The first attempt was **discarded ungraded**, and the defect was the harness's.
`subprocess.run(["bash", ...])` from a Windows Python resolves `bash` against
the *Windows* PATH, which on this box finds **WSL's** bash before MSYS2's — a
separate Linux userland with no `gcc`, no `cl.exe`, and no path to either. The
tell is in its own output: `drwxrwxrwx 1 root root`. The model's compiler probe
was **correct** —

```bash
elif command -v gcc &> /dev/null; then
    echo "Using GCC compiler (gcc)"
    BUILD_CMD="gcc -O3 -o run tools/llama2c/run.c -lm"
```

— and `gcc` **is** on this box at `/c/msys64/mingw64/bin/gcc`. Under the bash
the harness should have used, that branch fires. Scoring it would have recorded
our environment as the model's capability: the S-OW-5 error, in the round that
found S-GF-1. Fixed (the interpreter now defaults to
`C:/msys64/usr/bin/bash.exe`, is overridable with `GF_BASH`, and is **recorded
in every `run.json`**), and the arm was re-run cold. Kept as
`gauntlet/roundGF/runs/_discarded-wsl-bash/`.

### 4.3 Result

| | |
|---|---|
| model | `qwen/qwen3-coder-30b`, Q4_K_M, the strongest local model in the roster |
| loaded context | **65 536** — the largest rung that does not collapse for 18.63 GB of weights on this card, and the package fits it with room for the loop |
| package | **97 181 characters**, 15 items, **29 920 tokens** |
| cold prefill | 7.2 s (**4 156 tok/s**) — the fast regime, unlike the splat arm |
| interpreter | `C:/msys64/usr/bin/bash.exe`, recorded |
| outcome | **iteration-cap, 6 / 6 used, 140.6 s**, first clean run **never** |
| grade A (echo check, **not evidence**) | 2 / 2 |
| **grade B (decides)** | **0 / 2 — no executable was ever produced** |
| **verdict** | **FAIL** |

**What it got right, and it is not nothing.** Before building, in every
iteration, it printed a prediction, and the prediction was correct and correctly
sourced: the unblocking file (`tools/llama2c/BUILD-AND-RUN.md`), the MSVC build
line verbatim, the POSIX alternative, the runner `argv`, the expected generated
text, and `32680de0…afaadfb5` as the expected LF digest. It located every one of
those inside the package. It also probed for a compiler rather than assuming
one, which the system prompt asked for and which the discarded run shows it did
correctly.

**What it never did: open the container.** All six scripts compile
`tools/llama2c/run.c` **directly**, as though the package were already
unpacked — none contains `unzip`, `zipfile`, or any extraction step, and all six
exited in 0.1 s because that path does not exist. This is **S-GF-2 in a second
guise**: the inlined zip entry listing was treated as a filesystem listing. By
iterations 4–6 it had converted the failure into a claim, printing *"GCC
detected but will fail as documented in BUILD-AND-RUN.md section 2c ... MSVC is
required"* — a real sentence from the package, used to explain away a failure
that had a different cause.

**The contrast with roundSR is the finding.** Kimi, with a shell, hit the *real*
mingw errors on `win.c`, read the two fixes out of `BUILD-AND-RUN.md` §2c,
applied exactly those two, diagnosed a third problem the package could not have
known about, and rebuilt `-static`. This model, without a shell, never reached
the errors — it never produced any — and then cited the same §2c as a reason not
to try. **S-SR-11 said the package's documented failures are payload; this run
says a documented failure can also be borrowed as an excuse by an implementer
that never triggered it.** Filed as part of S-GF-2.

**A grader defect, found and fixed before this result was recorded.**
`grade_selfrun.py`'s first version called this run **PASS**, because both
vectors' exact text appears in what the run produced. It appears there because
`testvectors/generate-*.stdout.txt` is *inside the package* and therefore
*inlined in this arm's prompt* — the model printed the answer key. Grade A is
now labelled an echo check and **only grade B decides**: the grader invoking a
binary the run actually built. There was no binary. This is the same rule the
gauntlet applies to agents, applied to a grader that was accepting the package's
own answer key, and it is recorded rather than quietly corrected.

### 4.4 What the arm establishes

**Almost nothing about implementer diversity, and that is the honest report.**
It establishes that the adapted protocol *runs* — the model writes a build
script, the harness screens and executes it, the errors come back — and it
produces one clean negative: the strongest local model in the roster, given
everything roundSR's two agents said unblocked them, at a context where it is
fast, did not build the runtime, because it never opened the container. The
self-run round's "implementer diversity" gap is **not** closed. What this arm
adds to it is a specific, fixable reason, and a protocol that is now debugged
and can be re-pointed at the same model with one sentence added to its system
prompt.

---

## 5. Findings

**S-GF-1 — the open-weights context packer shipped empty layout grammars, and
every instrument said the package was complete.** Full detail in §1. It
invalidates S-OW-3's first clause, re-frames what the post-fix arm's worked hex
example was, and leaves the round-1 arm untouched. *Fixed* in this round's
harness as GF-4; deliberately **not** fixed in `roundOW/driver.py`, which is the
record of what those runs received. *Proposed:* `_assemble()` should refuse a
block whose body is below a length floor and record it in `omitted` with a
reason, so that "included" cannot mean "present and empty". **Severity: high.
Open.**

**S-GF-2 — with the whole self-description inlined, a small model can read the
prompt as the corpus and never open the artifact.** `google/gemma-4-e4b`
produced eight programs, none of which mentions `zipfile` or the fixture's name,
and said in its first reply that because reading and executing the file's
contents is forbidden it would *"simulate the analysis"* from the pasted
manifest. This is an **interaction between two things the protocol needs
separately**: the isolation clause *"do not execute anything that came out of
the file"*, and the inline-context protocol that exists because these models
have no tools. At 31 490 tokens (roundOW) the package plainly was not the data;
at 65 775 it plainly can be mistaken for it. *Proposed:* one sentence in the
driver's system prompt — *"the pasted material is documentation of a file, not
the file; your program must open the file"* — and a harness check that a
generated program references the fixture at all before it is run, fed back as a
refusal rather than scored as a failure. **Severity: medium. Open**, and it is a
finding about **the experiment**, in S-XV-5's sense, not about werk.

**S-GF-3 — the spec-forcing task's minimum self-description does not fit the
hardware the previous rounds' roster runs on.** 166 642 characters / 55 376 –
65 775 tokens depending on tokenizer, against a 35 000-token budget every
open-weights arm was built around, because this task needs the envelope grammar
*and* two payload grammars *and* a 36 KB manifest. A prompt that size needs
ctx ≥ 98 304, and a 27–30B Q4 model on a 24 GB card cannot be served one at
speed — the same model measures **3 751 tok/s at ctx 65536** and **274 tok/s at
ctx 262144**. The consequence is not a slower run; it is that three of five
rostered models could not participate. *This is a finding about the tokens the
format costs a reader,* and it is the number to put beside "the specification
travels with the file": for this payload the travelling specification is
**65 775 tokens**, and that is the price of admission. **Severity: informational
but load-bearing for the paper. Open.**

**S-GF-4 — S-OW-5's reasoning-model failure mode reproduced, and it is
expensive.** `zai-org/glm-4.6v-flash` returned `finish_reason=length` with
**zero characters of content** on 3 of 8 iterations, costing 37 % of its budget.
Nothing to do with werk; recorded because a round that reports "8 iterations"
should say how many of them were real. **Severity: none for the format. Open**
against the harness — a zero-character reply arguably should not consume an
iteration.

**S-GF-5 — the hardcopy replication is not isolation-equivalent to the
original, and saying so is the finding.** Kimi had a network and used it to
install `numpy` and `opencv`; Codex had none. The replication still holds where
it matters — no library decodes `werk-hardcopy/1`, so the decoder came from the
printed prose either way — but "two vendors recovered it" and "two vendors
recovered it under the same isolation" are different claims and only the first
is measured. *Proposed:* a third arm with Kimi behind a blocked network.
**Severity: low. Open.**

**S-HC-3, S-HC-4 and S-OW-5 reproduced; no new spec bug found.** Two rounds of
running foreign implementers over the corrected packages produced **zero** new
defects in `spec/`. That absence is recorded as a result, exactly as the
cross-vendor round recorded its own.

---

## 6. Verdict

**One gap is closed.** The hardcopy round's N = 1 is N = 2: a second vendor,
same photographs, same sentence, same cap, byte-identical payload and
byte-identical image, and the two most interesting behaviours of the original —
losing the emptiest symbol and refusing to guess at the signature — both
reproduced. The paper's hardcopy claim can drop "one vendor" and add "with more
tooling and 6.6× the wall clock".

**One gap is now known to have been mis-measured.** No local model has passed
the spec-forcing task — but until this round, no local model had ever been
*shown the grammar* either. S-GF-1 means the open-weights round's `0 / 2` was
never a test of the specification's sufficiency; it was a test of what a model
can do with a manifest, a magic number and a hex head. This round is the first
measurement of that cell with the grammars present, and the answer is still
`FAIL` on both models it could serve — but for reasons that are now legible: one
model never opened the artifact, the other could not sustain a correct program.
Neither failure is a missing sentence in `spec/`.

**One gap moved somewhere nobody was looking.** The binding constraint on the
spec-forcing cell turned out not to be model capability, spec completeness or
the harness — it is that the travelling specification for a Gaussian-splat
package is 65 775 tokens, and 65 775 tokens of KV plus 18.6 GB of weights do not
fit on a 24 GB card. That is a real, quantified cost of the format's central
property, and it is the honest thing to put in the paper beside the property
itself.

**And the round's own instrument was the largest defect it found**, which is the
sentence every future round should read first.
