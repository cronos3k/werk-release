# The self-running model — a package that carries its own engine

**Wave:** the 2026-08-09 self-run experiment.
**Owner of this file:** the self-run agent.
**Subtree owned for this wave:** `gauntlet/roundSR/`, `docs/PROFILE-MODEL-DRAFT.md`,
this file. **Nothing under `spec/` or `fixtures/` was written by this wave** — a
concurrent agent held those, and §1.3 records the one place where that constraint
changed a decision.

Gregor's order: bundle a small LLM runtime's **source code** together with a
model inside one `.werk`, hand the file and nothing else to a foreign coding
agent, and measure whether it can make the model **run**. This is the
paper-facing version of the question and no proprietary executor is involved
anywhere in it.

---

## 0. The headline

**Two coding agents from two vendors, each given one 62 MB file and one
sentence, made the model produce text on the first attempt — 98 seconds and
648 seconds — and both outputs matched the package's embedded temperature-0
test vectors byte for byte. 2/2, no retries.**

Neither opened the manifest. Neither opened the specification. Neither touched
the three bundled loaders. OpenAI's read four things — the zip entry listing,
`README.txt`, `tools/llama2c/BUILD-AND-RUN.md`, `testvectors/vectors.json` —
and Moonshot's read those plus the three C sources and the instrumentation
diff. That was sufficient, because those are the things the package put in
front of them.

The second arm produced the round's sharpest evidence that documentation is
load-bearing: it never found MSVC, went down the mingw path the package
**documents as failing**, hit both documented errors, and applied **exactly the
two source fixes the package's own build note says are needed** — one cast and
one `#if !defined(__MINGW32__)` guard, both inside `win.c`, with `run.c`
untouched. Then it applied the package's instrumentation diff and matched the
**token ids** too.

Graded by artifact: this agent re-extracted the committed fixture in a third
directory, rebuilt the runtime with a **different compiler version** from the
one that produced the vectors, re-ran both invocations and hashed the bytes
itself; and re-ran the Moonshot agent's static binary and hashed those. All of
it reproduces. Nothing below is taken from either agent's report.

---

## 1. The fixture

### 1.1 What it is

`gauntlet/roundSR/selfrun-v1.werk`

| | |
|---|---|
| bytes | **62 525 273** |
| sha256 | **`1f8e1270b89371a5acc80aa854db3572631f7dac9a053fd045da0af112d51f17`** |
| zip entries | 85 (all STORED) |
| declared files | 83 |
| nodes | 14 |
| profile | **`model/1-draft`** |
| `spec_sha256` | `3decb3978e99f593572da026f69fb9d3472f75cfbd2c6f25f3c1505e4d87caff` |
| `preview_prefix_bytes` | 1 221 844 |
| signature | dev-key Ed25519 chain, verifies |
| pin | `gauntlet/roundSR/fixture-pin.json` |
| build | `python gauntlet/roundSR/build_selfrun_fixture.py` |
| check | `python gauntlet/roundSR/verify_selfrun.py` → **29 PASS, 0 FAIL** |

Contents, by node:

| node | type | what it carries |
|---|---|---|
| `weights` | `x.model.weights` | `model/stories15M.bin`, 60 816 028 B, **15 191 712 parameters**, f32, 6 layers, dim 288, 6 heads, vocab 32 000, context 256 |
| `tokenizer` | `x.model.tokenizer` | `model/tokenizer.bin`, 433 869 B, 32 000 BPE entries |
| `runtime` | `core.tool` (`role: creator`, `form: source`) | `run.c` + `win.h` + `win.c` + `BUILD-AND-RUN.md` + the MIT text — the **complete inference engine as source** |
| `testvectors` | `x.model.testvectors` | two temperature-0 runs: argv, exact stdout, LF and CRLF hashes, token ids, and the instrumentation diff that captured the ids |
| `tool-config-llama2c-testvector-run` | `core.tool.config` | the one configuration the package makes a claim about |
| `spec` | `core.spec` | profile 1's whole spec tree **plus four package-local files** |
| `recipe`, `disclosure`, `provenance`, `license`, `readme` | base doctrine | see §1.4 |
| `loader-python`, `loader-rust`, `loader-c` | `core.loader` | the three bootstrap readers, unchanged |

The four package-local spec files, which are the interesting part:

* `spec/layouts/llama2c-checkpoint.layout.txt` — a byte-exact grammar for the
  weights file. Seven `i32` header fields with their measured values, thirteen
  tensors with **absolute offsets**, the sign-of-`vocab_size` shared-weights
  flag, and the two **dead RoPE tables** that must still be skipped. Its
  arithmetic accounts for **all 60 816 028 bytes with nothing left over**, and
  that check is what licenses the document to say MUST.
* `spec/layouts/llama2c-tokenizer.layout.txt` — the record walk, the `<0xNN>`
  byte-fallback spelling, and the fact that **the file does not contain its own
  entry count** (it comes from the checkpoint header). Walk consumes exactly
  433 869 bytes for exactly 32 000 entries.
* `spec/PROFILE-MODEL-DRAFT.md` — the draft profile (§4).
* `spec/schemas/manifest.model-draft.schema.json` — derived mechanically from
  `manifest.schema.json` with four changes, so the node/version/edge definitions
  cannot drift from the real ones.

### 1.2 Provenance and licences, recorded because S12-9 said to

Everything third-party is carried **byte-identical**, so every hash below is
comparable against its publisher's own distribution. Full table with URLs:
`gauntlet/roundSR/SOURCES.md`.

| | source | licence |
|---|---|---|
| `run.c` / `win.h` / `win.c` / `LICENSE` | `github.com/karpathy/llama2.c`, master, fetched 2026-08-09 | **MIT**, text carried verbatim in the package |
| `tokenizer.bin` | same repository | MIT |
| `stories15M.bin` | `huggingface.co/karpathy/tinyllamas` | **MIT by the publisher's assertion** — there is no LICENSE file in that repository, only the model card's `license: mit` front matter. The card is carried verbatim at `recipe/inputs/tinyllamas-model-card.md` |
| TinyStories (the corpus) | not carried | terms **not established here**; named in `unrecorded[]` and in §3 of the package's LICENSE, granted nothing |

**This fixture is handable to a stranger** — which `gsplat-v1.werk` is not, and
which was the point of S12-9. The one soft spot is stated rather than hidden:
the weights' grant is two lines of YAML, and the package says so in those words.

### 1.3 Where it lives, and the one place the brief was not followed literally

**The fixture is in `gauntlet/roundSR/`, not `fixtures/`.** `fixtures/` is the
pinned conformance corpus: every package in it declares `3d-entity/1` or
`image/1`, is recorded in `fixtures/fixtures.json`, and is rebuilt by every spec
wave. This one declares a profile that **does not exist in `spec/`** and
validates against a manifest schema that travels **inside it**. Putting it in
the corpus would either break the corpus's rebuild or force a spec change to
accommodate an experiment. It is pinned in its own
`gauntlet/roundSR/fixture-pin.json`, in the same shape `fixtures/fixtures.json`
uses.

**The draft profile is at `docs/PROFILE-MODEL-DRAFT.md`, not
`spec/PROFILE-MODEL-DRAFT.md`.** The brief asked for the latter. The reason for
the change is measured, not stylistic: **`spec_sha256` is computed over the
`spec/` tree a package carries**, so adding *any* file to the repository's
`spec/` directory moves that digest and invalidates every conformance fixture's
manifest — and while this ran, another agent was mid-wave rebuilding exactly
those fixtures. The draft is additive and non-normative, so the cost of putting
it in `docs/` is zero and the cost of putting it in `spec/` was somebody else's
re-run. The file carries the move instruction for the next spec wave
(`git mv`, then rebuild fixtures and re-record `fixtures.json`). The *package*
carries it at `spec/PROFILE-MODEL-DRAFT.md`, where it belongs, because the
package's spec tree is the package's own.

### 1.4 The test vectors, and why they are the load-bearing node

Two deterministic runs, produced by **building the carried runtime and running
it**, not by assertion:

| vector | prompt | steps | LF bytes | sha256 (LF) | tokens |
|---|---|---:|---:|---|---:|
| `once-upon-a-time` | `Once upon a time` | 64 | **234** | `32680de023a55d9eda57ec35c0a134eac7907285edf9b83827a946e2afaadfb5` | 65 |
| `the-little-robot` | `The little robot` | 32 | **140** | `eeeb4eb0a7f1f3b2f6a213a03317338c3ddf6de738b4aeaf0a55ceb5dd22540c` | 33 |

Three decisions inside that node are worth keeping, because each of them was a
mistake avoided rather than a feature added:

1. **Determinism is selected explicitly and named.** `-t 0.0` takes the greedy
   argmax branch of `sample()`; the RNG is never consulted. A vector recorded
   under sampling is not a vector.
2. **The hash is declared over the CRLF→LF-normalised bytes, and the raw form is
   recorded too.** `run.c` writes to a text-mode stream, so an identical model
   computation emits `\n` on POSIX and `\r\n` through a Windows console. A
   package that hashed raw stdout would be declaring a platform, not a result.
   Recording both is what makes the normalisation itself checkable — and the
   agent under test checked **both**, and both matched.
3. **The node says what a MISMATCH means.** Three distinguishable cases: fluent
   English diverging after N tokens (floating-point reassociation — an
   arithmetic difference, not a broken reader); fluent English different from
   token 1 (prompt encoding — BOS and the SentencePiece dummy-prefix space);
   garbage from token 1 (wrong tensor offsets — the dead RoPE tables). A vector
   that only says "should equal" turns a diagnosable divergence into a dead end.

Token ids are the stronger anchor because integers have no newline convention.
**The unmodified `run.c` does not print them**, so they were captured with a
two-line instrumentation — and that instrumentation travels in the package as
`testvectors/tokens_instrumentation.diff`, a unified diff against the package's
own `run.c`, so the capture is reproducible instead of asserted.

### 1.5 Build environment for the vectors

Windows 10 Enterprise 10.0.19045 x64, AMD Ryzen Threadripper 3970X,
**MSVC 19.38.33143** (VS 2022 Community), `cl /nologo /O2 /Fe:run.exe run.c win.c`,
`run.exe` 218 624 B, 93.75 and 94.51 tok/s from the runtime's own stderr line.
No GPU anywhere.

### 1.6 Two toolchain facts, measured, and one not measured

* **MSVC builds it.** Verified, twice, with two different compiler versions.
* **mingw-w64 gcc 15.2.0 does NOT build it unmodified.** Measured; both errors
  are in `win.c`, not in `run.c`: `VirtualProtect`'s fourth argument is
  `uint32_t*` where mingw wants `PDWORD`, and `win.c` redefines
  `clock_gettime`, which mingw's own `<pthread_time.h>` already defines inline.
  Working around them from the command line (`-Wno-incompatible-pointer-types`,
  `-Dclock_gettime=…`) also fails, because the rename applies to mingw's inline
  definition too. **Not fixed, deliberately**: patching `win.c` would change
  bytes whose whole value is that they hash to upstream. The package says all of
  this in `BUILD-AND-RUN.md` §2c, including the twenty minutes.
* **The POSIX line `cc -O3 -o run run.c -lm` was NOT verified here** and is
  labelled as upstream's, unmeasured. This box's only POSIX-ish compiler is the
  mingw one; its WSL Ubuntu has no compiler installed and installing one was out
  of scope. The package says "NOT VERIFIED HERE" in those words rather than
  claiming a build nobody ran.

---

## 2. The experiment

### 2.1 Protocol

Fresh neutral directory `<lab>\werk-selfrun-run1\workspace\` containing **only**
`selfrun-v1.werk` — the committed fixture, pinned above. One sentence, committed
verbatim at `gauntlet/roundSR/PROMPT-selfruntask.txt` **before the run**:

> This file contains a language model and everything needed to run it. Make the
> model run and produce text. Verify your result against whatever correctness
> information the file provides. Report what you did.

No hint about zip, about C, about llama2.c, about anything. Cap 45 minutes,
enforced by `timeout 2700`. One retry permitted (not needed). Harness:
`gauntlet/roundSR/run_codex.sh`, which records process wall clock around the CLI
process rather than asking the agent — round XV measured self-reported time
running **2.2× to 11×** long and that lesson is applied here.

| | |
|---|---|
| CLI | `codex` (OpenAI Codex CLI) **0.144.1** |
| model | **`gpt-5.6-sol`** |
| reasoning effort | `high`, set explicitly |
| invocation | `codex exec --skip-git-repo-check --sandbox workspace-write -c model_reasoning_effort=high --json` |
| network | restricted by the sandbox contract, same as round XV |
| tokens | 336 478 input (309 504 cached), 4 111 output, 1 346 reasoning |

### 2.2 Result — **SUCCESS, first attempt, 98.2 s**

| | |
|---|---|
| wall clock, process start to exit | **98.2 s** |
| shell commands | **14** (4 of them failed and were recovered from) |
| files read from inside the package | **4** |
| both vectors matched | **yes**, LF hash **and** CRLF hash, both vectors |
| checkpoint sha256 checked against `vectors.json` | yes, matched |
| its `run.exe` | 213 504 B, built with **MSVC 19.43.34808** (VS 2022 **BuildTools**) — a *different* toolchain from the one that made the vectors |

The generated text, from the agent's own `vector1.stdout` (archived at
`gauntlet/roundSR/runs/codex-vector1.stdout`):

> Once upon a time, there was a little girl named Lily. She loved to play
> outside in the sunshine. One day, she saw a big, red ball in the sky. It was
> the sun! She thought it was so pretty. / Lily wanted to play with the ball,
> but it was

### 2.3 What it read, in what order — the metric this round exists for

| # | command | what it learned |
|---:|---|---|
| 01 | `Get-ChildItem` + `rg --files -g AGENTS.md` | one 62.5 MB file, no repo instructions. `rg` absent → exit 1 |
| 02 | `Format-Hex -Count 256` | **failed**: PowerShell 5.1's `Format-Hex` has no `-Count` |
| 03 | `Get-Content -Encoding Byte -TotalCount 512 \| Format-Hex` | the first 512 bytes → `PK` |
| 04 | `tar -tf` | **failed**: Git-for-Windows `tar.exe` crashed with a cygwin `CreateFileMapping` fatal error |
| 05 | `System.IO.Compression.ZipFile` entry listing | **the whole manifest of contents, without reading `MANIFEST.json`** |
| 06 | extract to `selfrun-v1/` **and cat `README.txt` and `tools/llama2c/BUILD-AND-RUN.md` in the same command** | what the package is and exactly how to build it |
| 07–09 | hunt for `cl`/`clang`/`gcc`/`cc`, then `vswhere`, then two known VS roots | found `BuildTools\VC\Auxiliary\Build\vcvars64.bat` |
| 10 | `vcvars64.bat && cl /nologo /O2 /Fe:run.exe tools\llama2c\run.c tools\llama2c\win.c` | **`BUILD-AND-RUN.md` §2b, verbatim.** Built clean |
| 11 | `cmd /c 'run.exe … 1> vector1.stdout'` | **failed**, exit 1, silently — `run.exe` not on PATH and not prefixed |
| 12 | `.\run.exe … -n 8` | smoke test: eight tokens of correct text |
| 13 | `Start-Process` both vectors with redirected stdout/stderr | both full runs |
| 14 | read `testvectors/vectors.json`, LF-normalise, SHA-256, compare | both hashes matched, plus the checkpoint hash |

**Four files opened, in this order: the zip entry listing (not a file), then
`README.txt`, then `tools/llama2c/BUILD-AND-RUN.md`, then
`testvectors/vectors.json`.** The one that unblocked it was `BUILD-AND-RUN.md`:
its message between commands 06 and 07 says, unprompted, *"Its documented Windows
path is MSVC; I'll check available compilers"*, and command 10 is that document's
§2b command with nothing changed.

**Not opened at all:** `MANIFEST.json`, `SIGNATURE.json`, any file under
`spec/` (including both layout grammars), any of the three `loaders/`,
`recipe/`, `disclosure/`, `provenance/`, `LICENSE`. It verified no manifest hash
and made no claim about the signature.

### 2.4 Grading by artifact — done by this agent, not accepted from the report

1. The agent's own `vector1.stdout` / `vector2.stdout` were hashed here: 234 and
   140 bytes after normalisation, both matching the declared LF digests.
2. **A third directory**, `<lab>\werk-selfrun-regrade\`, was created from the
   **committed** fixture, extracted fresh, and the runtime rebuilt with
   `vcvars64.bat && cl /nologo /O2 /Fe:run.exe tools\llama2c\run.c tools\llama2c\win.c`
   → `run.exe` 213 504 B, **MSVC 19.43.34808**. Both invocations were re-run and
   hashed:

   ```
   once-upon-a-time   lf=234  match_lf=True  match_crlf=True
   the-little-robot   lf=140  match_lf=True  match_crlf=True
   ```

**That is the round's second measurement and it was not planned.** The vectors
were produced by **MSVC 19.38.33143**; they were reproduced by **19.43.34808**
producing a binary 5 120 bytes smaller, and by a third build inside the agent's
own sandbox. Two compiler versions, three builds, identical bytes out. The
`BUILD-AND-RUN.md` caveat about vectorising compilers reassociating the
reductions is still correct as a caveat — it simply did not bite across these
two MSVC releases at `/O2`, and now that is a measurement instead of a worry.

### 2.5 Second arm — Moonshot Kimi: **SUCCESS, 647.5 s, and it went further**

Protocol identical: fresh directory `<lab>\werk-selfrun-kimi\workspace\`, only the
committed fixture in it, the same sentence, the same 45-minute cap.
`kimi` (Kimi Code CLI) **0.15.0**, `--output-format stream-json`.

**One harness note, because the harness gets the same honesty as the result:**
the first launch died in 0.6 s on `error: Cannot combine --prompt with --yolo`
— CLI argument validation that never reached the model. It is not a run and is
not counted as one; the flag was removed and the run relaunched.
`gauntlet/roundSR/run_kimi.sh` carries the corrected line.

| | |
|---|---|
| wall clock | **647.5 s** (10 min 48 s) |
| tool calls | **98** — `Bash` ×82, `Read` ×7, `Write` ×7, `Edit` ×2 |
| files read from the package | **7**: `README.txt`, `tools/llama2c/BUILD-AND-RUN.md`, `run.c`, `win.c`, `win.h`, `testvectors/vectors.json`, `testvectors/tokens_instrumentation.diff` |
| toolchain found | **mingw-w64 gcc only** — it never found MSVC |
| both vectors matched | **yes**, LF **and** CRLF |
| **token ids also matched** | **yes** — 65 and 33, verified by applying the package's own instrumentation diff |

**The interesting part is the toolchain.** Kimi never located Visual Studio. It
went down the mingw path — the one `BUILD-AND-RUN.md` §2c says **fails** — hit
both documented errors, and then **applied exactly the two fixes §2c describes**:

```
-    if (VirtualProtect(addr, len, newProtect, &oldProtect))
+    if (VirtualProtect(addr, len, newProtect, (PDWORD)&oldProtect))
...
+#if !defined(__MINGW32__)
 int clock_gettime(int clk_id, struct timespec *tp) { … }
+#endif
```

§2c's sentence was *"the two changes a consumer needs, if a mingw build is what
they want, are one cast and one `#if !defined(__MINGW32__)` guard, both inside
`win.c`"*. It made one cast and one `#if !defined(__MINGW32__)` guard, both
inside `win.c`. **`run.c` it did not touch — verified byte-identical against the
package.** The patch is archived at `gauntlet/roundSR/runs/kimi-win-c.patch`.

It then hit a *third* problem the package could not have warned about: this
mingw's `libwinpthread-1.dll` does not export the `clock_gettime64` symbol the
dynamic build wanted, so the binary built and would not load. It diagnosed that
with `objdump` and rebuilt with `-static` → `run_static.exe`, 592 601 B.

Then it did the thing Codex did not: it **applied
`testvectors/tokens_instrumentation.diff`**, rebuilt, and compared the token-id
sequences — 65 and 33, both exact. That is the package's stronger anchor, used
as designed, by the arm that had the harder time getting there.

**Regraded by artifact here:** its `run_static.exe` was re-run by this agent
from the same directory and both stdouts hashed:

```
once-upon-a-time   lf=234  match_lf=True  match_crlf=True
the-little-robot   lf=140  match_lf=True  match_crlf=True
```

Its own outputs are archived at `gauntlet/roundSR/runs/kimi-vector*.stdout.bin`,
its report at `kimi-REPORT.md`, its build script at `kimi-build_static.bat`.

### 2.6 Both arms, side by side

| | OpenAI `gpt-5.6-sol` | Moonshot Kimi 0.15.0 |
|---|---|---|
| result | **SUCCESS** | **SUCCESS** |
| wall clock | **98.2 s** | **647.5 s** |
| tool calls | 14 | 98 |
| package files read | **4** | **7** |
| compiler | MSVC 19.43.34808 (BuildTools) | mingw-w64 gcc 15.2.0, `-static` |
| source modified | **none** | `win.c`, exactly the two changes the package documented; `run.c` untouched |
| stdout LF hash | match ×2 | match ×2 |
| stdout CRLF hash | match ×2 | match ×2 |
| token ids | not attempted | **match ×2** |
| opened `MANIFEST.json` | no | no |
| opened anything under `spec/` | no | no |
| used a bundled loader | no | no |

**2/2 success, two vendors, zero retries.** Every byte was hashed by this agent,
not accepted from either report. Between them, four independent builds of the
same source — three MSVC (two versions) and one mingw-static — produced
identical model output.

---

## 3. Findings

### S-SR-1 — `core.tool.role` has no word for an *executor*, and the two candidates are both wrong

`viewer` is defined as *"renders or plays it and produced nothing that is in
here"*. The runtime in this package **did** produce something that is in here —
the test vectors — so `viewer` is false. `creator` is used instead, with a note,
and it is only true because generating text from a prompt is genuinely
creation. Neither word describes "the program that executes the payload", which
is the role a model package's central tool always has. **Not fixed.** Proposed:
an `executor` role, or a rewording of `viewer` that drops the
produced-nothing clause.

### S-SR-2 — §3.11's hermeticity rule cannot be satisfied by any real model package

"Every input medium a recipe names must be present in the package" is right for
an image made from a photograph and **impossible** for weights made from a
corpus: the training set is orders of magnitude larger than the artifact.
§3.17's intermediate exemption does not cover it either, because no embedded
tool reproduces a training corpus. The only honest construction available is to
name the corpus in `unrecorded[]` and in prose and to keep it out of every
step's `inputs[]` — which this package does. **Every author will rediscover
this**, and the specification says nothing about it. **Not fixed.** Proposed: a
sentence in §3.11 naming the corpus case explicitly, so the absence is a stated
exemption rather than a rule everyone quietly breaks.

### S-SR-3 — `core.recipe` has no `train` role

The `role` enum is `plan | generate | edit | inpaint | upscale | interpolate |
transcode | select | convert | ingest | other` — a **generation** vocabulary,
written when the model was the *tool*. In a model package the model is the
*target* and the step that made it is a training run. `other` is the only honest
choice today and is what this package uses. **Not fixed.**

### S-SR-4 — `core.tool.config.environment` is interpreter-shaped and cannot describe a compiled tool

Its five permitted keys are `platform`, `runtime_version`, `library_versions`,
`device`, `note`. For a Python tool those are exactly the facts a re-run is
sensitive to. For a **compiled** tool the facts a re-run is sensitive to are the
**compiler, its version, its optimisation flags and the resulting binary**, and
there is nowhere to put any of them: `additionalProperties` is `false`. This
package puts the compiler in `runtime_version` (the closest true reading) and
the build command, the binary size and the machine in `note` — prose where
structure was wanted. The structured copy exists only in
`testvectors/vectors.json`, which is a package payload and not a schema-validated
werk field. **Measured consequence, not hypothetical:** §2.4 above compares two
compiler versions, and the format has no field in which that comparison could
have been declared. **Not fixed.** Proposed: `environment.toolchain`
(`{name, version, flags, target}`) alongside `runtime_version`.

### S-SR-5 — a recipe step cannot say its tool is deliberately NOT carried

`core.recipe`'s `tool` block is `name | version | source_file | tool_node |
config_node | repository_revision | host`, `additionalProperties: false`.
`source_file` and `tool_node` both mean *"and it is in this package"*. A step
whose tool is **deliberately absent** — a training script that would be
misleading to carry without its corpus — can say so only by omitting two
optional keys, which is indistinguishable from an author who forgot. The
sentence had to go in the step's `note`. **Not fixed.** Proposed: a `carried`
boolean, or a `not_carried_reason` string.

### S-SR-6 — `core.provenance.consumed[]` cannot record where anything came from

Its four permitted keys are `path`, `sha256`, `external`, `license`. No `size`
and, more to the point, **no note and no origin**. So a package can say *what*
it consumed and not *where from* — for a package whose entire value proposition
is third-party provenance, that is the field one wants most. Every URL and byte
count in this package's provenance node is therefore prose in the run's `note`.
**Not fixed.** Proposed: `origin` (free text) and `size`. (This is adjacent to
S-XV-1: the manifest's hash checklist and `consumed[]` keep drifting apart.)

### S-SR-7 — `primary` still has no slot for a model, which is S12-7 recurring

Profile 1 offers `mesh`, `sound`, `image` and (ruling 22) `geometry`. A model
package fits none. The draft proposes **four** slots —
`weights` / `tokenizer` / `runtime` / `testvectors` — because the thing a model
package is *about* is a four-part assembly and a consumer that resolves three of
four can do nothing at all. That is a real departure from profile 1's
one-slot-per-kind shape and it is written down to be argued about, not adopted
quietly. **The finding is that the gap was found the same way S12-7 was: by
building a package and discovering it had nowhere to declare itself.**

### S-SR-8 — every bundled loader skips the three nodes that hold the model

Measured, `python loaders/werk_read.py gauntlet/roundSR/selfrun-v1.werk`:

```
14 nodes: 11 live, 0 dead, 3 skipped for unknown type
weights      x.model.weights      skipped: unknown node type `x.model.weights`
tokenizer    x.model.tokenizer    skipped: unknown node type `x.model.tokenizer`
testvectors  x.model.testvectors  skipped: unknown node type `x.model.testvectors`
```

This is **law 12 working exactly as designed** — an unknown `x.*` type is
skipped and reported, and the loader still lists the graph and reports the
signature as `unverified`. It is also a shape worth naming: a package whose
*entire payload* is in the extension namespace gets a clean, honest,
completely uninformative report from every conformant bootstrap loader. Nothing
is wrong; the reader is simply not the right reader. **Not a bug and not
fixed.** It is the strongest available argument for promoting
`x.model.*` to `core.model.*` under a ruled profile, and it is the reason §1 of
the draft lists the node types as `core.model.*`.

### S-SR-9 — a runtime's "completeness" is measured by building it, never by counting files

`run.c` includes `win.h` behind `#if defined _WIN32`. `win.h` **declares**
`mmap`, `munmap` and `clock_gettime`; a **fourth file**, `win.c`, defines them.
A package carrying `run.c` + `win.h` looks complete, reads complete, compiles
on POSIX, and **fails to link on Windows**. This was hit while building the
fixture — the first Windows build attempt died on `undefined reference to
'mmap'` — and it is the concrete form of the profile's central requirement. A
`model/1` conformance clause that says "carries a complete runtime" is
unenforceable unless "complete" means *builds, on each platform the package
claims*. **Recorded as doctrine for the draft, §1.1.**

### S-SR-10 — the round's own finding: the task got done without the format being read

Between them the two agents read four and seven files, and **none of the eleven
was the manifest, the specification or a loader**. That is **S-XV-5 confirmed on
a completely different task and across both vendors**: what an agent reads is
determined by the *task*, not by the vendor and not by the format. Round XV's
splat task forced fourteen files open because it could not be done from the
manifest; this task was done from a README and a build note because those were
sufficient.

The consequence is not that the specification is unnecessary — it is that
**"N/N opened the specification" and "0/N used the loaders" are task-relative
metrics and must always be reported with the task beside them.** For this round
the honest line is: **0/2 opened the specification, 0/2 used a loader, 2/2
succeeded**, and the reason is that the package deliberately put a human-readable
on-ramp in front of the machine-readable one. Law 9's preview-first ordering did
the rest: `README.txt` and `BUILD-AND-RUN.md` are both inside the first 1.22 MB
of a 62.5 MB file.

### S-SR-11 — a *documented failure* did more work than a documented success

`BUILD-AND-RUN.md` §2c exists because the mingw build was measured to fail while
the fixture was being built. It records both compiler errors verbatim, says the
fix is one cast and one `#if !defined(__MINGW32__)` guard inside `win.c`, says
why the package does not ship that fix (it would change bytes whose value is
that they hash to upstream), and ends "Recorded so nobody spends the twenty
minutes again."

The Moonshot agent, which never found MSVC, hit exactly those two errors and
applied exactly those two fixes — **and left `run.c` byte-identical**, which is
the part that matters, because the runtime whose output is being checked against
the vectors was not modified. A section that only said "use MSVC" would have
left it stuck; a section that said "mingw fails" and stopped would have left it
guessing.

**The generalisable claim:** in a package that must be *built*, the negative
results are payload. A build note that records what does not work, with the
error text and the reason the package declines to fix it, is the difference
between an agent recovering in minutes and an agent failing. This is the
build-time twin of §3.12's "a guess that is recorded and a guess that is silent
are different things", and it is the strongest single argument in this round for
`model/1` requiring build instructions as a *node* rather than as prose somebody
might write.

---

## 4. The draft profile

`docs/PROFILE-MODEL-DRAFT.md` (repository) = `spec/PROFILE-MODEL-DRAFT.md`
(inside the package), 12 874 B. **DRAFT, not normative, not ruled on.** Its
completeness test is deliberately operational:

> A `model/1` package is complete when a competent stranger, given the file and
> nothing else, can make the model produce output and check that the output is
> right.

which is testable, and was tested, in 98 seconds.

Required nodes: weights, tokenizer, **runtime as source**, **test vectors**,
recipe, disclosure, plus base doctrine's unconditional set. Conventions by
subtraction from profile 1 (`image/1`'s precedent), keeping only the
profile-agnostic constants plus `float_format` — with a drafting note **in the
schema** saying `float_format` is probably wrong as a package-wide constant and
belongs per-node the moment quantised weights are admitted.

**The open problem is named and not solved: `core.model.graph`.** A weights node
plus a layout grammar says where every number is; it does not say what the
numbers *mean* as an architecture. In this package all of that lives in the C
source, which is *sufficient* (you can read it, and the vectors prove you read it
right) and *not structured* (you cannot query it, diff it, or check a second
runtime against it). A real `model/1` needs a declarative computation graph with
one requirement the prior art (ONNX, GGUF metadata, safetensors headers) does
not carry: **it must be checkable against the runtime the package also ships**,
or it is a second statement of the same fact with no way to catch a
disagreement.

**Optimised executors are an extension-tier concern by design, not by
omission.** The draft says so in §6 and this result file repeats it: base
doctrine's job is that a stranger can get output *at all*; vendor kernels,
quantised kernels and accelerator backends are `x.*` nodes, and a reader that
has never heard of one skips it and still runs the model. No such executor is
named anywhere in the draft, the fixture or this file.

---

## 5. What this demonstrates for the format, and what it does not

**It demonstrates, measured:**

1. **The self-containment property extends past documents to executable
   artifacts.** A werk package can carry a model *and its engine* such that one
   file plus one sentence is enough for a foreign agent to produce correct
   output. Previous rounds proved a stranger could *read* a package; this one
   proves a stranger can *run* one — **twice, on two vendors, across two
   different toolchains, with no retry.**
2. **The correctness anchor is the difference between a demo and a result.**
   Without `testvectors/`, "the model ran" would have rested on the agent's word
   that fluent English is right output. With it, a run is a measurement, and the
   agent performed the comparison unprompted because the file told it how.
3. **Preview-first ordering is not decoration.** The agent's whole path
   — listing, README, build note — is inside the first 1.22 MB of a 62.5 MB
   file, because the entry order was chosen to put it there.
4. **"Source always, never auto-execute" survives contact with the one case that
   stresses it.** The package that most obviously *wants* to ship a binary ships
   none, and the experiment shows it does not need to: one agent compiled it in
   under a minute, the other in ten, on a toolchain the package said would fail.
   §7.1's rule cost nothing here and that is worth having measured, because the
   argument against it is always "but then nobody can run it".
5. **Recorded negative build results are payload, not commentary** — S-SR-11,
   and the only reason the second arm finished at all.

**It does not demonstrate:**

* **Anything statistical.** Two vendors, two models, two runs, one task. Both
  are frontier commercial coding models inside agentic harnesses, which is
  *vendor* diversity and not *implementer* diversity. Round XV's caveat stands
  unchanged.
* **That the format was necessary.** A plain zip with the same README would very
  likely have produced the same 98 seconds. What the format supplied that a zip
  does not is everything the agent *did not need* on this task and a stranger
  would need on a harder one — the manifest's hashes, the layout grammars, the
  provenance, the licences, the signature — and this run did not exercise any of
  it. That is stated plainly rather than argued around. **The obvious next
  experiment is the adversarial one:** hand out a *damaged* self-run package, or
  one whose weights layout the agent must recover without a README, and see
  whether the layout grammars earn their bytes.
* **That small or non-agentic implementers can do this.** The open-weights round
  found the reader task degrades at 8B and is absent at 4B. This task is
  strictly harder — it requires finding a toolchain and compiling — and no small
  model was tried.
* **That the profile is right.** It is a draft with ten findings against the
  existing doctrine, five of which are schema gaps that a real `model/1` would
  have to close first.

---

## 6. Reproducing this

```
python gauntlet/roundSR/build_selfrun_fixture.py     # needs data/selfrun/, see SOURCES.md
python gauntlet/roundSR/verify_selfrun.py            # 29 PASS, 0 FAIL
bash   gauntlet/roundSR/run_codex.sh <fresh-dir> <out-prefix>
bash   gauntlet/roundSR/run_kimi.sh  <fresh-dir> <out-prefix>
```

Artifacts: `gauntlet/roundSR/runs/` holds the full Codex JSONL stream, a
readable transcript, the run metadata and the two stdout files the agent
produced. `gauntlet/roundSR/PROMPT-selfruntask.txt` is the task sentence,
committed before the run.

The fixture build is **deterministic**: rebuilt from the committed authored
sources against the same upstream bytes it produces the same 62 525 273 bytes
and the same sha256. Measured twice on 2026-08-09.
