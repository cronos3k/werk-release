# Stage CROSS-VENDOR results — the gauntlet run against two model families that are not ours

**Author:** the cross-vendor gauntlet agent. **Owns for this wave:**
`gauntlet/roundXV/`, `results/STAGE-CROSSVENDOR-RESULTS.md`, and the
cross-vendor rows in `paper/v2/NUMBERS.md` and `paper/v2/CHANGES.md`. No other
agent ran during this wave; the HANDOVER/ROADMAP/`gauntlet/RESULTS.md` merge was
done by this agent, per `results/README.md` clause 3.

**Date:** 2026-08-08.

This round exists to address one sentence in `paper/v2/PAPER.md` §7:

> "Every agent in all three rounds is from the same model family, so a shared
> blind spot would look exactly like a shared success. … Testing a model family
> that is not ours has been the stated next honest step since round 1 and
> remains untaken."

It is now taken. Two vendors, neither of them ours, each given the round-1 task
verbatim under the round-1 isolation rules, and then each given the round-3
mini-gauntlet task as well.

---

## 1. Headline

| | |
|---|---|
| Vendors run | **2** — OpenAI (Codex CLI) and Moonshot AI (Kimi Code CLI) |
| Runs | **4** — each vendor on round 1's task and on round 3's splat task |
| **Success rate** | **4 / 4** |
| Round-1 task times | 558 s (OpenAI), 106 s (Moonshot) |
| Splat task times | 512 s (OpenAI), 377 s (Moonshot) |
| Used a bundled loader to learn the format | **0 / 4** |
| Ported a bundled loader | **0 / 4** |
| Read a bundled loader at all | 1 / 4 — after its own reader already ran, as a cross-check |
| Wanted anything from outside the file | **0 / 4** |
| Opened `spec/` at all | **3 / 4** — the exception is the finding, S-XV-5 |
| Extracted bytes hashed to the manifest's declared values (graded by this agent, not self-reported) | **2 / 2** on the round-1 task |
| Splat point count, both vendors, matching round 3 exactly | **281 498 / 281 498** |
| New findings filed | **S-XV-1 … S-XV-5** |
| Defects found in the splat package (post-round-3 fixes) | **0** |

---

## 2. Setup

**Artifact under test:** `fixtures/crate-v1.werk`, the **committed current
build**, pinned in `fixtures/FIXTURES.md` at

```
sha256 d5fd9007f61872e6986b06e046057b0499d5ababa8d951f6bf42110b2679fabf
13 611 141 bytes, 174 zip entries, 172 declared files, 36 nodes, profile 3d-entity/1
```

Both handed-out copies were hashed before the runs and both matched that pin.
This is the first gauntlet round whose artifact is the pinned committed fixture
rather than a build that has since been superseded — rounds 1 and 2 both had to
record that the agents saw different bytes from the ones in the tree. This round
is therefore directly re-runnable as a comparison rather than as a fresh
experiment.

**Isolation, enforced, identical for both vendors.** Each vendor got its own
fresh neutral directory containing *only* the fixture:
`<lab>\werk-gauntlet-xv-openai\workspace\` and
`<lab>\werk-gauntlet-xv-moonshot\workspace\`. The prompt file lived one directory
up so that the workspace itself held nothing but `crate-v1.werk`. The task
sentence is round 1's, verbatim:

> Here is a file: `crate-v1.werk` (in your working directory). Write a program in
> Python that opens it, lists its contents with their meanings, verifies
> integrity, and extracts the primary mesh and one sound to disk. You may read
> anything inside the file. You may not search the web or read anything outside
> the file.

The hard constraints were round 1's, restated: the only permitted input is that
file; `<repo>`, `<lab>\splat-foley` and any `spec`/`werk`/`loaders` directory
elsewhere on the machine are off limits; no web search and no URL fetch;
recognising the format from prior knowledge does not license using it; do not
modify the fixture; do not execute anything that came out of the file. The full
prompt as handed out is committed at `gauntlet/roundXV/PROMPT-round1task.txt`.

**Language was assigned, not chosen.** Both vendors were told Python. Round 1
varied the language across agents; this round varies the *vendor* and holds the
language fixed, so that the only moving part is the model.

**Reporting instruction.** Both were told to write `REPORT.md` into their own
workspace — round 2's lesson, that an experiment whose evidence lives only in a
transcript is one lost file away from being an anecdote — and both were told that
a stumble is worth more than a clean run. That instruction inflates the stumble
count exactly as it did in rounds 1 and 2, and for the same reason.

**Grading is by artifact.** The extracted files were hashed against
`MANIFEST.json` by this agent, and each agent's program was re-run by this agent
in a third directory with its own captured output. Nothing below is graded on an
agent's own narrative.

### 2.1 The two harnesses, and their network posture, recorded honestly

| | OpenAI | Moonshot |
|---|---|---|
| CLI | `codex` (OpenAI Codex CLI) | `kimi` (Kimi Code CLI) |
| CLI version | **0.144.1** | **0.15.0** |
| model id as the harness records it | **`gpt-5.6-sol`** (`model_provider: "openai"`, from the session rollout `turn_context`) | **`kimi-for-coding`** (log line `provider=kimi model=kimi-for-coding modelAlias=kimi-code/kimi-for-coding`) |
| reasoning effort | `high` (set explicitly for this run) | `thinkingEffort=high` (the CLI's default for this profile) |
| endpoint | OpenAI, via the CLI's existing ChatGPT sign-in | `https://api.kimi.com/coding/v1` |
| invocation | `codex exec --skip-git-repo-check --sandbox workspace-write --json` | `kimi -p … --output-format stream-json` |
| **network posture** | **No network.** The sandbox contract the CLI injected reads, verbatim: *"`sandbox_mode` is `workspace-write`: The sandbox permits reading files, and editing files in `cwd` and `writable_roots`. Network access is restricted."* | **Network was available to the harness and was not used.** The CLI exposes 24 tools; the agent used exactly three of them — `Read`, `Bash`, `Write` — across 12 calls, and no call in the transcript names a URL or a host. |
| filesystem posture | reads were *not* sandboxed — the agent could have read `<repo>` and did not | reads were not sandboxed either — same |

**Both filesystem-isolation claims were audited, not believed.** Every absolute
path appearing anywhere in either transcript was extracted. The OpenAI
transcript contains exactly seven absolute paths, all of them
`<lab>\werk-gauntlet-xv-openai\workspace\…`, plus the PowerShell interpreter. The
Moonshot transcript contains **no absolute path at all** — every tool call is
relative to its working directory. Neither agent touched a werk repository.

**On the Moonshot model id.** The exact string the harness sends is
`kimi-for-coding`, which is a coding-plan alias rather than a dated checkpoint.
Three names for it disagree and all three are recorded rather than reconciled:
the CLI config's `display_name` is `Kimi-k2.6`; the model, asked directly in a
throwaway session before the run, answered `kimi-k2.5`; the wire model id is
`kimi-for-coding`. A model's self-report is not evidence, and this round does
not claim to know which checkpoint served it — only that it is Moonshot's K2
coding model as served on 2026-08-08, and not ours.

---

## 3. Round-1 task — per vendor

| | OpenAI `gpt-5.6-sol` | Moonshot `kimi-for-coding` |
|---|---|---|
| result | **SUCCESS** | **SUCCESS** |
| wall clock, process start to process exit | **558 s** (9 min 18 s) | **106 s** (1 min 46 s) |
| tool calls | 21 shell executions | 12 (`Read` ×4, `Bash` ×6, `Write` ×2) |
| program | `inspect_werk.py`, 16 614 B, stdlib only | `read_crate.py`, 10 375 B, stdlib only |
| declared hashes verified | **203** declarations in 10 families | **172** manifest file hashes |
| zip CRC-32 checked | 174 / 174 | not checked as a separate pass |
| `input_hash` freshness | 25 / 25 | not attempted |
| `spec_sha256` aggregate | 1 / 1 | not attempted |
| Ed25519 signature | verified, `signed-and-valid`, gated on the in-package RFC 8032 vector | deliberately not attempted, and said so |
| conventions | 21 / 21 | not attempted |
| package files read for meaning | **9** | **1** |
| used the bundled loaders | no | no |
| wanted anything outside the file | no | no |
| stumbles reported | 10 | 5 |

**Both extractions were graded by this agent against `MANIFEST.json`, not
accepted from the report:**

| output | source path | declared sha256 | computed | verdict |
|---|---|---|---|---|
| OpenAI `primary_mesh.glb` | `geometry/game.glb` | `eee8b3cb…4ef2ce` | identical | OK |
| OpenAI `primary_sound.wav` | `audio/sfx/crate-impact-hard-surface.wav` | `1e634f03…59aa5e` | identical | OK |
| Moonshot `game.glb` | `geometry/game.glb` | `eee8b3cb…4ef2ce` | identical | OK |
| Moonshot `crate-impact-hard-surface.wav` | `audio/sfx/crate-impact-hard-surface.wav` | `1e634f03…59aa5e` | identical | OK |

Both agents resolved the payloads through `primary.mesh` → node → active version
→ `files[]` and `primary.sound` → node → the version file whose `role` is
`"best"`. Neither guessed a path. Both programs were re-run by this agent in a
third directory and their complete output is committed
(`gauntlet/roundXV/openai-run.txt`, `gauntlet/roundXV/moonshot-run.txt`).

### 3.1 OpenAI — `gpt-5.6-sol`, 558 s, SUCCESS

The deep run, and a near-exact independent reproduction of round 1's Python
agent — by a different vendor, from the same file, with no contact with that
result. Its own summary line, reproduced by this agent from a clean re-run:

```
Entity: Wooden crate (36 nodes, 174 entries)
Signature: signed-and-valid
archive-crc32: 174/174 passed
convention: 21/21 passed
ed25519-signature: 1/1 passed
global-spec-sha256: 1/1 passed
input-hash: 25/25 passed
license-sha256: 1/1 passed
manifest-file-sha256: 172/172 passed
manifest-file-size: 172/172 passed
provenance-consumed-sha256: 1/1 passed
signature-manifest-sha256: 2/2 passed
signature-prev-entry-sha256: 1/1 passed
All structural checks and declared current-package hashes passed.
```

**Reading order, quoted from its report**: `MANIFEST.json` (read directly out of
the first stored local record, before any zip library was used) → `README.txt` →
`spec/README.md` → `spec/SPEC.md` → `spec/MINI-SPECS.md` →
`spec/schemas/manifest.schema.json` → `spec/schemas/signature.schema.json` →
`SIGNATURE.json` → `provenance/provenance.json`. It names `spec/README.md` as the
file that unblocked it, "because it prescribed the authoritative reading order
and mapped each question to a file" — which is round 2's Rust agent's verdict on
the same file, from a different vendor.

**On the bundled loaders**, verbatim:

> "I did **not** open any bundled reader as source, run it, import it, compile
> it, or port it. … I deliberately made this choice after `spec/SPEC.md`
> explained the loader model. The Python source would have been permissible to
> read, but doing so was unnecessary and would have weakened the result of the
> isolation experiment."

That is the first time in four rounds that an agent has declined the loaders
*because it understood it was inside an experiment about the loaders*. It is a
cleaner refusal than round 1's and a weaker datum: an agent reasoning about the
protocol is no longer a naive implementer. Recorded, not smoothed over.

**The result that matters most for the spec ledger: it did not stumble on
`input_hash`.** S-10 — the absent-`input_params` rule, three of four round-1
agents' longest detour, 0 of 25 hashes for all three — was implemented correctly
by a foreign model, first pass, and does not appear anywhere in its stumble list.
25/25. The fix holds outside the model family that found the bug.

Likewise unstumbled: the zip container, CRC-32, SHA-256, the manifest structure,
the node graph, edge semantics, version resolution, the three signature states,
the message the signature covers, and the exit statuses. Ed25519 — round 1's
single clearest shared-blind-spot candidate, where three of four agents reached
for constants they already knew — was implemented and **gated on the package's own
RFC 8032 vector** by this agent too, unprompted.

**Its own honest limit**, verbatim: it reports a valid cryptographic chain and
declines to claim authorship, "because the package says this is a public DEV key
with no external root of trust". Round 2's agents drew the same line unprompted.

### 3.2 Moonshot — `kimi-for-coding`, 106 s, SUCCESS

The fast run, and the more interesting one, because of what it did **not** read.

It recognised the container from `xxd` output, listed entries with `unzip -l`,
extracted `MANIFEST.json`, read it in three chunks — **and then wrote the
program**. It never opened `README.txt`. It never opened `spec/README.md`,
`spec/SPEC.md` or `spec/MINI-SPECS.md`. Its report's "files read, in order"
section has two entries: the raw bytes, and `MANIFEST.json`. Its own words:

> "No other internal files needed to be read individually before writing the
> program; `MANIFEST.json` is self-contained enough for the required tasks."

And it is right. Re-run by this agent, its program reports `Files checked: 172 /
Files OK: 172 / Files FAIL: 0`, prints all 36 nodes with their meanings taken
from each active version's `note`, and writes both payloads with matching
digests. Against the success criteria fixed in `briefs/STAGE3-BRIEF.md` before
round 1 — opens the container, lists the node graph with meanings, verifies every
declared hash, extracts the named payloads, extracted bytes hash to the declared
values — it passes all five clauses in 106 seconds having read one file.

**It declined the loaders too**, and for a reason no previous agent gave:

> "The task explicitly forbids executing any program that came out of the file,
> and I treated the bundled loaders as off-limits for execution *and for
> reverse-engineering*."

**What it declined to claim** is the second-best thing in its report. On the
signature:

> "`SIGNATURE.json` exists and declares an `ed25519` signature, but the task only
> asked to verify declared *hashes*, not cryptographic signatures. I did not
> verify the signature because … doing so correctly would require understanding
> the exact signed payload construction from the spec."

That is round 2's Rust agent's move — decline rather than guess — arrived at
independently by a third vendor. It is also the honest reading of why its run was
106 seconds and the OpenAI run was 558: it scoped itself to the sentence it was
given and said so, rather than silently under-delivering.

**Its two substantive observations are both about the manifest read alone**, and
both are filed below: that `primary.sound` names a node and not a file, so a
reader has to know that `role: "best"` is the selector (S-XV-4); and that it
added a fallback for a missing `active` field because nothing it had read told it
what `active` means when absent (S-XV-5, the manifest-only reader's blind spot).

---

## 4. Findings

Filed with `S-XV-` ids, per this wave's brief. Two are real specification gaps in
the sense rounds 1–3 used the word; two are documentation-scope problems; one is
a finding about the **experiment** rather than the format, and it is the most
important thing this round produced.

| id | found by | one line | disposition |
|---|---|---|---|
| **S-XV-1** | OpenAI | "every declared hash" has no single exhaustive list: `core.provenance`'s `consumed[].sha256` is a current-package hash declaration that the manifest checklist does not cover, and finding it required auditing every JSON value in the package | **open**, real |
| **S-XV-2** | OpenAI | the `spec_sha256` construction says to append each file's "own sha256" without saying *declared* or *recomputed*; identical on a valid package, divergent on a damaged one, and the diagnostic choice is the unstated one | **open**, real |
| **S-XV-3** | OpenAI | `spec/examples/MANIFEST.example.json` carries valid-looking hashes for a different, abridged package, and telling example literals from current-package declarations is work the reader must do; `spec/README.md` does say the example is abridged, which is what resolved it | **open**, low — partially mitigated already |
| **S-XV-4** | Moonshot | `primary.sound` names a *node*, and which file inside that node is the sound is carried only by `role: "best"`; there is no single field a reader can follow to a path | **open**, real — the successor to S-13 |
| **S-XV-5** | Moonshot (by omission) | a reader that reads **only `MANIFEST.json`** can pass the round-1 criteria, and will then guess at anything the manifest does not restate — this one invented a fallback for a missing `active` because it had never read the rule | **open** — and it is a finding about the *task*, not only the format |

### S-XV-1, in the finder's words

> "The task phrase 'every declared hash' is broader than the manifest checklist.
> The central 'What gets hashed?' discussion covers manifest file hashes,
> manifest anchors, and derivation hashes, but `core.provenance` may itself
> declare consumed-file hashes. I had to audit the in-package JSON
> schemas/values to discover that this fixture has one such claim. I verified it
> too. This was the main documentation-scope ambiguity that cost reasoning time."

It is the same shape as S-26 (`total_size_bytes` had no definition anywhere) and
S-30 (a definition reachable only from a schema `description`): the fact exists,
is correct, and is not where a reader looking for it will look. Its closing line
is the ruling this finding asks for: *"The largest avoidable cost was that
payload-level hash claims are not included in one central exhaustive 'all
current-package hash declarations' list."*

### S-XV-2, in the finder's words

> "The global `spec_sha256` construction says to append each file's 'own
> sha256.' I used the digest recomputed from the actual bytes, after separately
> comparing it to the declared file digest. On this valid package those are
> identical. In a damaged package, computing the aggregate from actual bytes
> gives the more diagnostic result, but the wording could make an implementer
> briefly wonder whether to concatenate declared or recomputed digests."

This is a genuinely new one: nothing in rounds 1–3 touched it, because nobody
before had computed the aggregate over a *damaged* package in their head. The
agent picked the diagnostic reading and said why, which is the behaviour §10.0
asks for — but it picked it, rather than being told.

### S-XV-5 is the finding of the round, and it is about the experiment

Round 1's headline number is **0 / 4 used the bundled loaders**, and its
justification is explicit: if agents learned the format by reading the bundled
readers, the experiment would measure *can an agent port a program*, which is a
different and much easier question. The metric means what the paper claims only
if **the specification is the path of least resistance**.

The Moonshot run shows that for round 1's task, on this fixture, the
specification is not the path of least resistance either — **`MANIFEST.json`
is**. One file, three reads, 106 seconds, all five success clauses met, and the
`spec/` folder never opened. That is not a failure of the format: a manifest rich
enough to drive a correct reader on its own is arguably the design working. But
it *is* a limit on what round 1's criteria can measure, and it has been invisible
for three rounds because every previous agent chose to read the specification
when it did not have to.

Three consequences, stated rather than resolved:

1. **Round 1's success criteria under-test the specification.** They can be
   satisfied without it. The clauses that force `spec/` open are the ones round 2
   and round 3 added — parse the custom binary, restate the recipe and the
   disclosure, verify the signature, identify the embedded tools — and those are
   exactly the clauses the Moonshot agent declined or was not asked for.
2. **"0 / N used the bundled loaders" should be reported beside "N / N read the
   specification at all."** For rounds 1–3 both numbers happen to be the good
   one. This round is **2 / 2 loaders declined, 1 / 2 specification opened**, and
   the second number is new information that the first hides.
3. **A future round should make hash-scope explicit in the task** — "verify
   every hash the package declares, wherever it declares it" — which is exactly
   the sentence S-XV-1 says is missing from the specification, and which would
   have forced the manifest-only reader into `spec/` on the first attempt.

**And the control arrived the same afternoon.** §5 gave the *same Moonshot
model* the round-3 splat task, which cannot be done from the manifest. It read
**fourteen** files inside the package, named `spec/README.md` and
`ENVELOPE.layout.txt` as its two unblockers, and took 377 seconds instead of
106. So the manifest-only behaviour is a property of **the task**, not of the
vendor. S-XV-5 is a finding about the round-1 protocol, and it now has a
within-vendor control.

---

## 5. The splat mini-gauntlet — round 3's task, both vendors

Time permitted, so both vendors were also given round 3's task on
`fixtures/gsplat-v1.werk` (pinned sha256
`04f657d0e09ba97f7c373f0c96dc167965cf3f5146835e6358db6939b3477147`, 30 163 573
bytes, 77 entries, 75 declared files, 17 nodes) in a second pair of fresh
neutral directories, with the same isolation rules plus round 3's extra clause —
**do not execute anything that came out of the file**, explicitly extended to the
embedded tools the task asks them to identify. Prompt committed at
`gauntlet/roundXV/PROMPT-gsplattask.txt`.

| | OpenAI `gpt-5.6-sol` | Moonshot `kimi-for-coding` |
|---|---|---|
| result | **SUCCESS**, all three tasks | **SUCCESS**, all three tasks |
| wall clock | **512 s** (8 min 32 s) | **377 s** (6 min 17 s) |
| tool calls | 33 shell executions | 39 (`Read` ×20, `Bash` ×13, `Edit` ×4, `Write` ×2) |
| point count | **281 498** | **281 498** |
| zip CRC | 77 / 77 | all, via its own check |
| declared file hashes | 75 / 75 | 75 / 75 |
| `spec_sha256` | not attempted | verified, `331519c8…5734575` |
| manifest ↔ signature anchor | matches | matches |
| Ed25519 | **not implemented; state reported as `unverified`** | not implemented; said so and why |
| WKPC ↔ WKGS cross-check | positions **byte-exact**; **all 844 494 colour bytes** recomputed and matched | all 281 498 positions matched; colour formula confirmed |
| three embedded tools identified with roles and exact paths | yes, with source quoted verbatim | yes, with source quoted verbatim |
| executed anything from the file | no | no |
| package files read | ~17 named | 14 named |
| self-estimated time | "~48 minutes" | "roughly 50–55 minutes" |

**Both reproduce round 3's committed sample exactly.** Round 3's agent (ours)
recorded:

```
[0] -0.06007473  1.62525749  0.93507129   ->  39 19  6
[1] -0.03502635  1.57806265  1.03217006   ->  60 30 29
[2] -0.10943363  1.61571956  1.00538695   -> 109 71 26
```

`gpt-5.6-sol` wrote `-0.0600747317, 1.62525749, 0.93507129, 39, 19, 6` as row 0
of an 281 498-row CSV; `kimi-for-coding` printed `-0.060075 +1.625257 +0.935071`
and `39 19 6`. Three independent readers, three model families, one set of
numbers. *(Grading note: this agent verified the two foreign outputs against each
other and against round 3's committed record, and confirmed the CSV row count at
281 498 — it did not re-decode the payload a fourth time itself, because the
grading interpreter on this host has no numpy. The agreement of three
independently written decoders is the evidence offered.)*

**The OpenAI agent's cross-check is the strongest single measurement this round
produced**, and it goes past round 3's:

> "The point node is an exact materialized degradation of the splat: all
> 3 377 976 position bytes equal the WKGS means section byte-for-byte. For every
> point I recomputed each colour channel as
> `round-half-even(clamp(0.5 + 0.28209479177387814 * sh_dc, 0, 1) * 255)`; all
> 844 494 stored colour bytes matched."

It found the **round-half-even** rule — the detail that decides the last bit —
in `tools/werk-pointcloud-run.config.json`, and said so: "the primary unblocker
was `MANIFEST.json`; for decoding point bytes, `ENVELOPE.layout.txt` was the
technical unblocker; `werk-pointcloud-run.config.json` supplied the exact
round-half-even quantization rule."

**Both used the fourth signature token correctly, unprompted.** Neither
implemented Ed25519; neither claimed a verdict it had not earned.
`gpt-5.6-sol`: *"SIGNATURE.json names Ed25519; its manifest SHA-256 matches the
actual manifest, but I did not implement or invoke Ed25519, so the honest
signature state is **unverified**, not signed-and-valid."* `kimi-for-coding`
declined for the same reason and added the package's own note that the dev key
"is not a trust anchor". Round 2 recorded one agent doing this; the count is now
three agents across three model families.

### 5.1 Two behaviours from round 1 reproduced verbatim in a foreign model

**The loader, opened at the end as a cross-check and not before.** Round 1: "2/4
read a bundled loader at all, both *after* their own reader already ran clean."
On the splat task the OpenAI agent did exactly that, and named the reason:

> "I **opened/read relevant portions** of `loaders/werk_read.py` as text only,
> after my provisional parser could already enumerate the package. I used it to
> confirm that the bundled bootstrap reader also reports Ed25519 as unverified
> and to compare its ZIP/envelope approach. … I did **not port** a bundled
> reader."

So across this round's four runs: **0 / 4 used a bundled loader to learn the
format, 0 / 4 ported one, 1 / 4 read one — after the fact, as a cross-check.**
That is round 1's ratio, from vendors that never saw round 1.

**Recognition is not fully excluded — and the specification caught it again.**
Round 1's JavaScript agent wrote a zip reader from prior knowledge before opening
the specification, and the specification then caught one gap (zip64). The
OpenAI agent did the same thing on the splat package, flagged itself for it, and
the specification caught **three**:

> "After `MANIFEST.json` declared ZIP/store I wrote the provisional
> central-directory parser using remembered ZIP field positions before opening
> the package's own ZIP mini-spec. That evidentiary order was too eager under
> this experiment's rules. I later read `spec/MINI-SPECS.md` from inside the
> package, audited the parser, and found/fixed three robustness gaps: EOCD
> false-signature disambiguation, explicit ZIP64 sentinel rejection, and
> drive-letter path rejection. The final reader now follows the embedded rules;
> the fixture's results did not change."

This is the paper's §7 recognition threat behaving exactly as §7 says it does,
observed in a model family that is not ours, and self-reported unprompted. It
also raises the retro-confirmation count from 1 gap to 4 across two rounds.

### 5.2 A measured caveat on every self-reported time in the ledger

Both agents were asked for their own wall-clock sense. Both were wrong by a
factor of five to nine against the process clock:

| run | measured, process start to exit | agent's own estimate | ratio |
|---|---|---|---|
| OpenAI, round-1 task | 558 s | "roughly 20–25 minutes" | 2.2–2.7× over |
| OpenAI, splat task | 512 s | "~48 minutes" | 5.6× over |
| Moonshot, round-1 task | 106 s | "~15–20 minutes" | 8.5–11× over |
| Moonshot, splat task | 377 s | "roughly 50–55 minutes" | 8–9× over |

Every time in this document is the measured one. Rounds 1 and 3 recorded
harness-observed wall clock and are comparable; round 2's Rust breakdown
(~65 min) is **self-reported** and, on this evidence, should be read as an
agent's impression rather than a measurement. Filed as a note on the numbers
rather than a new finding.

### 5.3 New findings from the splat task

Neither vendor found a defect in the splat package. Round 3 found six things and
fixed four; this round found none, on a package that had already been through
that pass. The absence is worth recording precisely because round 3's four fixes
are what stand between the two results: two foreign models read the corrected
package end to end and neither had anything to say about it.

The one thing both declined — Ed25519 — is not a defect and is a known
consequence of a hermetic reader with no crypto library, already ruled on as
S-12 and answered by the package carrying its own test vector.

---

## 6. Can the "one model family" threat be softened?

**Yes, partially, and the paper should say exactly how much.**

**What is now measured.** Two model families that are not ours, on the same
fixture and the same task sentence, under the same isolation rules, both
succeeded — and succeeded in the *same shape* as our agents did: extraction
resolved through `primary` rather than guessed paths, hashes checked rather than
assumed, the bundled loaders declined, nothing wanted from outside the file,
Ed25519 either built from the file and gated on the file's own vector or
declined by name using the specification's fourth token. The two behaviours
round 1 called out as the most likely shared blind spots — the loaders, and
reaching for remembered cryptographic constants — both reproduced, and both
reproduced with the *same* mitigation working: the specification retro-confirmed
the remembered implementation and caught what it had got wrong.

**What is still not measured.**

* **n = 1 per vendor per task.** Four runs total. This adds two model families,
  not statistical power; the sample-size paragraph of §7 is untouched.
* **Both vendors are frontier commercial coding models with agentic harnesses.**
  "Not our model family" is not the same as "a different kind of implementer".
  A small open-weights model, a model without an agentic loop, or a human were
  all untested.
* **The two harnesses are not equivalent.** The OpenAI run had no network at
  all; the Moonshot run had network available and did not use it. The isolation
  claim for the second rests on transcript audit rather than on a sandbox, and
  is recorded that way.
* **Round 1's criteria turned out to be satisfiable without the
  specification** (S-XV-5). Any strengthening of the cross-vendor claim should
  be stated against the *harder* tasks, where both vendors did open `spec/`, and
  not against the round-1 task alone.

**Proposed wording change to §7**, for the later editing pass — not applied
here, per this wave's scope:

> Replace "Testing a model family that is not ours has been the stated next
> honest step since round 1 and remains untaken" with a statement that it has now
> been taken for two families across two tasks, four runs, 4/4 success, and that
> what remains untested is implementer *diversity* — non-frontier models,
> non-agentic implementers, and humans — rather than vendor diversity.

The threat is **softened, not removed**, and the sentence that replaces it should
say which of the two it is.

---

## 7. Deviations from the protocol, recorded rather than hidden

1. **Language was assigned to both vendors (Python), not varied.** Round 1
   varied language and held the vendor fixed; this round does the reverse. The
   times are therefore comparable across vendors within this round and **not**
   comparable to round 1's per-language times.
2. **The reasoning effort was set to `high` on the OpenAI run** (the CLI's
   stored default on this host is `low`), and left at the Kimi CLI's own default
   for this profile, which its log reports as `thinkingEffort=high`. Both runs
   are therefore at each harness's high setting, which is the closest available
   match and not an identical one.
3. **No second attempt was needed.** Both vendors succeeded first time on both
   tasks. Three harness-level failures occurred before any agent ran and are not
   results: `codex exec` refused a non-git directory until `--skip-git-repo-check`
   was passed; `kimi -p` refuses to combine with `--yolo` and with `--auto`. All
   three were fixed by changing the invocation, and no agent had started.
4. **No damage gauntlet was run.** Round 1's agents synthesised their own damage
   unprompted; neither of these did, and neither was asked to. `crate-v1-damaged.werk`
   was not handed out. The cross-vendor damage question is open.
5. **Both agents wrote a few files into their workspace beside the fixture**
   (`MANIFEST.json` extracted, an `extracted/` tree, `__pycache__`). The fixture
   itself was untouched in every case — re-hashed after both runs and still
   `d5fd9007…79fabf` / `04f657d0…477c147`.
6. **The optional gsplat round was run on both vendors, not only the first to
   succeed.** The brief allowed one; running both cost eight minutes and turned
   S-XV-5 from an observation into a controlled one, which is why it was done.

---

## 8. What is committed

| path | what it is |
|---|---|
| `gauntlet/roundXV/PROMPT-round1task.txt` | the round-1 task prompt as handed to both vendors |
| `gauntlet/roundXV/PROMPT-gsplattask.txt` | the splat task prompt as handed to both vendors |
| `gauntlet/roundXV/openai-inspect_werk.py` | OpenAI's round-1 program, verbatim |
| `gauntlet/roundXV/openai-run.txt` | its complete output, from a re-run by this agent |
| `gauntlet/roundXV/openai-CONTENTS.md` | its node listing |
| `gauntlet/roundXV/openai-REPORT.md` | its report |
| `gauntlet/roundXV/moonshot-read_crate.py` | Moonshot's round-1 program, verbatim |
| `gauntlet/roundXV/moonshot-run.txt` | its complete output, from a re-run by this agent |
| `gauntlet/roundXV/moonshot-REPORT.md` | its report |
| `gauntlet/roundXV/openai-gsplat-inspect_werk.py` | OpenAI's splat program |
| `gauntlet/roundXV/openai-gsplat-REPORT.md` | its splat report, including the verbatim tool-source appendix |
| `gauntlet/roundXV/openai-gsplat-POINTS.head.csv` | the first rows of its 281 498-row extraction |
| `gauntlet/roundXV/moonshot-gsplat-inspect_werk.py` | Moonshot's splat program |
| `gauntlet/roundXV/moonshot-gsplat-run.txt` | its complete output |
| `gauntlet/roundXV/moonshot-gsplat-REPORT.md` | its splat report |

The four workspaces are at `<lab>\werk-gauntlet-xv-{openai,moonshot}\` and
`<lab>\werk-gauntlet-xv-{openai,moonshot}-gsplat\`; they are scratch, and the
artifacts under test are the committed pinned fixtures, which is what makes this
round re-runnable as a comparison.

