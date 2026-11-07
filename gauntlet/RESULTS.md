# The agent gauntlet — run 1

**2026-08-08.** Four fresh agents, four languages, one file and nothing else.

The manifesto's law 10 says agent-implementability is the format's quality
metric and that it is **tested, not asserted**. This is the first test.

---

## Headline

| | |
|---|---|
| **Success rate** | **4 / 4** |
| Languages | Python, JavaScript, Rust, C |
| Median time to a working reader | **637 s (10 min 37 s)** |
| Mean | 642 s |
| Range | 486 s – 806 s |
| Agents that used the bundled loaders to understand the format | **0 / 4** |
| Agents that read a bundled loader at all | 2 / 4, both *after* their own reader already ran clean, as a cross-check |
| Agents that wanted something from outside the file | 3 / 4, all on the **same two** gaps (Ed25519 internals, SHA-512) |
| Distinct spec bugs surfaced | **12** (S-10 … S-21) |
| Total stumbles reported | 38, deduplicating to those 12 |

Every agent opened the container, listed the graph with meanings, verified
every declared hash, extracted `geometry/game.glb` and one WAV, and matched
the manifest's declared sha256 on both extracted files.

**The single most useful number in this table is the 0 / 4.** The format's
claim is that the *specification travels with the file*; the bundled
`core.loader` readers are a convenience, not the mechanism. Nobody used them
to learn the format — two agents checked them at the end and both found the
loaders did *less* than what they had already built from `spec/`. Had the
loaders been the path of least resistance, this experiment would have been
measuring "can an agent port a program", which is a different and much easier
question.

---

## Setup

**Artifact under test:** `fixtures/crate-v1.werk`
sha256 `93d1657948dda0ef43871c67a1824ff84572b6cd31c6a9e87381263e3305a384`,
13 262 619 bytes, 157 zip entries, 36 nodes, 155 declared files.

> That is the fixture **as the agents saw it**. The committed fixture has
> since been rebuilt with the fixes below and hashes differently. Between the
> two, `spec/` gained the S-10…S-21 corrections. Nothing about the container,
> the graph or the payloads changed.

**Prompt**, identical for all four but for the language, and taken verbatim
from `briefs/STAGE3-BRIEF.md`:

> Here is a file: `…\crate-v1.werk`. Write a program in ⟨L⟩ that opens it,
> lists its contents with their meanings, verifies integrity, and extracts
> the primary mesh and one sound to disk. You may read anything inside the
> file. You may not search the web or read anything outside the file.

**Isolation, enforced:** the fixture was copied to a neutral directory
outside every werk repository. Agents were told, as hard constraints, that
the only permitted input was that file and its contents; that
`<repo>`, `<lab>\splat-foley` and any `spec`/`werk`/`loaders` directory
elsewhere on the machine were off limits; that WebSearch and WebFetch were
forbidden; and that recognising the format from prior knowledge did not
license using it — everything had to be derived from the file. Each agent had
its own workspace and was told not to modify the fixture.

**Deviations from the brief, recorded rather than hidden.** Three, and the
first is the one that matters:

1. **The prompt was not literally the only text.** Each agent also received
   the isolation rules above, a workspace path, a timing instruction, an
   instruction to report stumbles honestly, and one environment note (gcc
   fails silently under one of the available shells on this machine — a
   sandbox artifact that would otherwise have been recorded as a format
   failure). The task sentence itself is verbatim.
2. **The reporting instruction is not neutral.** Agents were told that a
   stumble is worth more than a clean run and that under-reporting to look
   competent would corrupt the experiment. This certainly inflates the
   stumble count relative to a silent run — which is the intent, since the
   stumbles are the product. It also means the count is not comparable to a
   number gathered without that instruction.
3. **The damaged fixture was never handed out.** The brief says to rerun two
   agents against `crate-v1-damaged.werk`. In the event all four synthesised
   their own damage without being asked to, so there was nothing left to
   rerun — see "Damage, unprompted" below. That is a stronger result than the
   brief asked for and a weaker one than it specified: nobody was tested
   against damage *they did not design*.

C++ was in the brief's language list and was not run; four languages were
requested for this round. The three-face test in Stage 2 already exercises
C++ against the same DLL, so C++ is covered as a *consumer* and untested as
an *implementer*.

---

## Per agent

### Python — SUCCESS, 486 s

Fastest of the four. Hand-rolled the store-mode zip reader rather than using
`zipfile`, implemented SHA-256 from `MINI-SPECS` §11's structural facts, and
implemented **Ed25519 verification from scratch** in ~60 lines of
extended-coordinate Edwards arithmetic — then gated the whole program on the
RFC 8032 vector the file supplies, and additionally checked that a *wrong*
message is rejected, so a constant-true `verify` could not pass its own gate.

Read, in order: `README.txt` → `spec/README.md` → `spec/SPEC.md` →
`spec/MINI-SPECS.md` (**the one that unblocked it**) →
`spec/schemas/manifest.schema.json` → `spec/schemas/core.audio.effect.schema.json`.
Opened `loaders/werk_read.py` **once, at the very end**, after its own reader
was already producing a clean run — and found the loader implements neither
`input_hash` nor Ed25519, so it could not have helped with either of the two
things that cost time. Never opened the Rust or C loaders.

Coverage beyond the task: zip64 detection and container refusal, UTF-8 BOM
rejection, duplicate-JSON-key rejection, "nothing floats" reachability, all
21 conventions checked, `preview_prefix_bytes` recomputed to the byte
(724 832 == 724 832), 25/25 `input_hash` freshness, transitive
`requires`/`enhances` death propagation, active-version fallback, 12 distinct
report codes, §10.1 exit statuses, and a self-test gate over CRC-32, SHA-256
and the Ed25519 vector.

10 stumbles.

### JavaScript — SUCCESS, 519 s

The control for "what if there is no loader in your language at all": there
is no `werk_read.js`, and it made no difference. Node built-ins only.

Wrote a 40-line zip lister from general knowledge *before* reading any spec —
purely to get at the text inside — then retro-confirmed it against
`MINI-SPECS` §5 and discovered the zip64 detection rule it had not
implemented. Grepped `loaders/` for `input_hash` (zero hits), and ran
`werk_read.py` once at the very end as an independent cross-check. Nothing
was ported.

Used Node's `crypto` for Ed25519 and had to supply the SubjectPublicKeyInfo
DER prefix from memory to turn 32 raw key bytes into a key object — then
proved the guess with the file's own RFC 8032 vector. "The file's test vector
rescued the guess. Still: a gap." That gap is now S-12.

8 stumbles.

### Rust — SUCCESS, 755 s

`rustc -O --edition 2021`, no cargo, no crates. Derived every SHA-2 round
constant **at run time** from the primes rather than typing any in from
memory, computed `sqrt(-1)` and the Ed25519 base point from their
definitions, and gated the whole stack on the package's own test vector.

Never read, ran or ported `loaders/werk_read.rs` — a sibling implementation
in its own language, sitting in the same file, untouched. One grep over
`loaders/` for `input_hash` returned nothing, which is how it learned the
loaders do not implement the staleness check.

Declared its own narrowness explicitly, in the format's vocabulary:
implemented `read-manifest` (structural, not schema-validated), conventions
check, `verify-hashes`, `verify-signature` with real Ed25519, `input_hash`
staleness, reachability, envelope parsing, GLB/WAV/PNG structural parse,
`materialize`; **not** implemented: JSON Schema validation of payloads
(§10 step 7 `[F]`), deflate, zip64 reading. It reported that rather than
claiming it, which is exactly what §10.0 asks for.

9 stumbles.

### C — SUCCESS, 806 s

Slowest and the most thorough. Single-file C99, standard library only,
56 KB of source. Refused to memorise any constant: SHA-256/SHA-512 IVs and
round constants derived at run time from the fractional parts of the square
and cube roots of the primes; curve constant `d`, `sqrt(-1)` and the base
point computed from their definitions. Everything gated on the file's own
vectors.

Did **not** read `loaders/werk_read.c` — the C loader shipping inside the
very file it was reading — before writing its own.

The only agent to demonstrate all three signature states by construction,
including **present-and-invalid** on a manifest it tampered with itself.

11 stumbles.

---

## Damage, unprompted

Nobody was asked to test degradation. All four did.

| agent | damage it built | result |
|---|---|---|
| Python | one byte flipped in `crate-kicked-hard.wav`; separately an injected unknown type `core.holo.field`; separately `SIGNATURE.json` removed | exit 1, `present-and-invalid` (the injected node re-serialised the manifest), 34/36 nodes still loaded, mesh and sound still extracted; the stripped-signature copy → exit 0, `absent` |
| Rust | one byte flipped in `plank-impact-hard-surface.var3.wav` | exit 1, `zip-crc-mismatch` + `hash-mismatch` on that path, **35 live / 1 dead**, signature still `signed-and-valid` |
| C (run 1) | one byte flipped in `spec/MINI-SPECS.md` — i.e. damage to the *specification* the reader had just used | exit 1, `zip-crc-mismatch` + `hash-mismatch`, 1 node dead, 35 alive, signature still `signed-and-valid` |
| C (run 2) | one byte flipped in `MANIFEST.json` | exit 1, `signature-invalid`, **0 nodes dead, 0 files failed**, state `present-and-invalid` |
| JS | corruption run over two output sets | degraded, reported, continued |

Two of these are the finding Stage 2 flagged as easy to get backwards, and
four independently-written readers got it right: **corrupting a payload does
not invalidate the signature** (the chain signs the manifest; the manifest
hashes the files; detection belongs to the per-file hash), while **corrupting
the manifest does**, with a different code. Nobody had to be told.

Three of the four also produced the three-state doctrine as three distinct
outputs rather than two — `signed-and-valid`, `absent`, `present-and-invalid`
— which is §6's central demand and the thing it warns tools get wrong.

---

## The stumbles, deduplicated

Twelve distinct spec bugs. Each is filed in `../HANDOVER.md` with its ruling;
the "seen by" column is what makes the priority ordering an observation
rather than an opinion.

| # | seen by | one line | status |
|---|---|---|---|
| **S-10** | **Py, JS, Rust** | `input_hash` with an absent `input_params`: is the appended canonical JSON `{}` or nothing? | **fixed** |
| S-11 | Rust, C | SHA-512 is undocumented, and Ed25519 needs it | **fixed** |
| S-12 | Py, JS, Rust, C | "use a library" is unfollowable in a hermetic reader, and the curve parameters were not in the file | **fixed** |
| S-13 | Py, JS, Rust | "the primary mesh" is nowhere a machine-readable fact | **fixed** |
| S-14 | Py | `container.entry_order` mixes exact paths and directory prefixes with nothing marking which | filed |
| S-15 | Py | `preview_prefix_bytes` does not say what it measures *to* | filed |
| S-16 | Py, Rust | `SPEC.md` §11 still said no golden sample existed, inside the golden sample | **fixed** |
| S-17 | — (from §10.1) | which nodes a given unsupported convention actually kills is not tabulated | filed |
| S-18 | Py | "reachable from exactly one `files[]`" versus a node with several versions | filed |
| S-19 | Py | loader capabilities and signature-state words drift between the manifest, the loaders and the spec | **fixed** |
| S-20 | Py | `audio/package.json` says `prompt`; the sidecar says `prompt_used`; same value, no warning | **fixed** |
| S-21 | Py, Rust | minors: `layouts` is `{}` and the whole envelope apparatus is unexercised by this fixture; the EOCD paragraph printed a superseded bound beside the correct one | **partly fixed** |

### S-10 is the finding of the run

Three agents, three languages, no contact with each other, and the *same*
longest detour. All three read "followed by the UTF-8 bytes of the canonical
JSON of `input_params`" the natural way — no params, append nothing — and all
three got 0 of 25 hashes right.

The Python agent brute-forced ten candidate conventions against three known
targets before finding it. The Rust agent found it by discovering
`h.update(b"{}")` inside `spec/examples/make-examples.py` — a *generator
script that happened to travel in the package* — and noted that the generator
and the fixture disagreed about whether the field was even present. The
JavaScript agent brute-forced it too.

Two things make this the most valuable result of the run:

* **The bundled loaders could not have saved anyone.** None of the three
  implements `input_hash` at all. Two agents checked; both said so.
* **It is exactly the failure mode the format claims to prevent.**
  `spec/README.md` lists ten questions the folder must answer alone. Question
  six is *"Is this derived data stale? → recompute `input_hash` from
  `input_files` and compare."* It was the one of the ten the folder could not
  actually answer.

The rule is now stated, with an executable pseudocode block and a worked
example checkable by hand against this very package; writers are told to emit
`"input_params": {}` explicitly; and both werk writers now do.

### What nobody stumbled on

Worth recording, because a list of only failures reads as a worse format than
the measurements support. Not one agent needed anything external for: the zip
container, CRC-32, SHA-256, WAV, GLB, PNG, JSON, UTF-8, the manifest's
structure, the node graph, the edge semantics, the version-resolution rules,
the three signature states, the message the signature covers, the refusal
scopes, or the exit statuses. The Python agent put it plainly: *"zip, CRC-32,
WAV, GLB, PNG and SHA-256 were all covered to byte level by `MINI-SPECS.md`,
and I never wanted an external reference for any of them. That part of the
claim holds."*

Both fixes made in the spec-repair pass immediately before this run were
picked up and used correctly: the Rust agent implemented the **corrected**
EOCD scan bound and cited the correction, and every agent used the
`[F]`/`[B]` reader-class split to declare its own narrowness rather than
overclaim.

---

## Threats to validity

Stated so the numbers are not read for more than they are worth.

* **n = 1 per language.** Four data points. A success rate of 4/4 is
  consistent with a true rate anywhere above roughly 40 %; this run cannot
  distinguish a good format from a lucky one, only rule out a bad one.
* **All four agents are the same model family.** A shared blind spot would
  look like a shared success. The one place this is visible is Ed25519: three
  of four reached for constants they already knew, and only the file's test
  vector caught whether they were right.
* **Recognition is not fully excluded.** Agents were instructed to derive
  everything from the file, and their logs are consistent with that, but zip
  and glTF are ubiquitous — the JavaScript agent wrote its zip reader from
  prior knowledge *before* opening the spec and said so. What that measures
  is that the spec **retro-confirmed** a from-memory implementation and
  caught a gap in it (zip64), which is a weaker but still real result.
* **The stumble count is instruction-inflated.** See deviation 2.
* **One fixture, no custom binaries.** The golden sample carries no `WKFF`,
  `WKRP`, `WKAC` or `WKSK` payload, so the entire binary-envelope apparatus —
  `ENVELOPE.layout.txt`, the MessagePack subset, the section consistency rule
  — went completely untested by this run. Two agents implemented an envelope
  parser from the spec and never got to run it against anything. `S-21`.
  `tests/fixtures/crate.werk` does exercise it, and was not handed out.
* **No zip64 fixture exists**, so every zip64 path written by these agents is
  unexercised code.
* **Timing is wall-clock over a whole agent session**, including reading,
  writing, compiling, debugging and report-writing. It is not
  time-to-first-working-parse, and it is not comparable to a human baseline
  that was never measured.

## Re-running this

The four workspaces, with each agent's source, output listings, damaged
copies and notes, are under
`<user-home>\AppData\Local\Temp\claude\gauntlet\{python,js,rust,c}\`.
They are scratch, not committed: the artifact under test is committed and
reproducible (`python fixtures/build_golden.py`), which is what a later run
needs in order to be a comparison rather than a fresh experiment.

The honest next run is **more agents per language, at least one non-Claude
model, and a fixture carrying a custom binary** — in that order.

---

# The agent gauntlet — run 2

**2026-08-08.** Fresh agents, one file and nothing else — and this time the
file contains a **custom binary**, which is the gap run 1 declared and could
not close.

Run 1's own verdict was that its fixture "carries no custom binary, so the
entire envelope apparatus went untested. Two agents wrote envelope parsers and
never got to run one." Run 2 exists to fix exactly that, so the task list grew:
not only open, list, verify and extract, but **parse the envelope payload** and
**state the recipe and the disclosure in plain language** from the file alone.

---

## Headline

| | |
|---|---|
| **Success rate** | **2 / 2** (Python, Rust) — see the relaunch caveat below |
| Parsed the `WKEM` envelope payload | **2 / 2** |
| Checked **both** branches of the section consistency rule | **2 / 2** |
| Stated the recipe correctly, including its grade and its caveats | **2 / 2** |
| Stated the disclosure correctly, including that it binds nobody | **2 / 2** |
| Used the bundled loaders to understand the format | **0 / 1 recorded** (Rust: explicitly not; Python: *not recorded*) |
| New spec bugs surfaced | **3** (S-26, S-27, S-28) |
| Wanted something from outside the file | **0 / 2** |

**Gate, quoted from `briefs/STAGE9-BRIEF.md`:** "2/2 gauntlet agents parse the
envelope payload and can state the image's recipe and disclosure correctly from
the file alone." **PASSED, 2/2 on all three clauses.**

**The result worth putting first**, because nothing in run 1 came close: a
fresh agent, working only from `spec/layouts/embedding.layout.txt` §4,
**reimplemented `werk.descriptor.labhog/1` and recomputed it from the source
pixels bit-exactly** — `max |recomputed - stored| = 0.000e+00` on both the
72-component vector and the 8-swatch palette, against a declared tolerance of
1e-6. The spec's claim is that a `core.embedding` node can be `measured` rather
than asserted, *because* the descriptor is defined completely enough to redo.
An agent that had never seen the format redid it, in a different language, and
hit every bit.

**Second**, and it is the sharper result for the reader doctrine: the two
agents took **opposite and both-correct** routes through §6. The Python agent
implemented **Ed25519 from `MINI-SPECS.md` §12** and reported
`signed-and-valid`. The Rust agent deliberately did not implement the curve
arithmetic and reported **`signature-unverified`** — the fourth fixed token
§10.0 step 4 defines for exactly this case — while still rebuilding the signed
message bytes, checking the chain linkage and checking the anchor against the
manifest actually present. Two readers, two honest verdicts, neither one
guessing. In run 1, three of four agents named Ed25519 internals as the thing
they wanted from outside the file; run 2 has one agent building it from the
inside and one declining it by the book.

---

## Setup

**Prompt**, identical for each but for the language, extended from
`briefs/STAGE3-BRIEF.md`'s wording with the two new tasks:

> Here is a file: `…\artifact.werk`. Write a program in ⟨L⟩ that: opens it and
> lists its contents with their meanings; verifies its integrity; extracts the
> primary image and one other payload to disk; **parses the custom binary
> payload it contains** and prints what is inside it; and **reports, in plain
> language, how the image in it was generated (the recipe) and what the file
> declares about that generation (the disclosure)**. You may read anything
> inside the file. You may not search the web, and you may not read anything
> outside that file.

**Isolation, per `briefs/STAGE3-BRIEF.md`, enforced.** The fixture was copied
to a neutral directory outside every werk repository —
`<user-home>\AppData\Local\Temp\claude\gauntlet2\` — one workspace per
agent. Each agent was told, as a hard constraint, to work only inside its own
directory; not to read, list or search any other directory on the machine; not
to look for documentation, specifications or source anywhere except inside the
file; and to report rather than fetch if it thought it needed something from
outside. No agent was shown `<repo>`, `spec/`, or any werk code outside the
fixture. Neither asked for anything from outside.

**Artifact under test:** `fixtures/ista-varun-v1.werk`, profile `image/1`,
15 nodes. The two agents saw **different builds**, recorded rather than
smoothed over:

| agent | sha256 | bytes | entries | why it differs |
|---|---|---|---|---|
| Python | `a59a5083…` | 9 969 937 | 63 | the build the run started with |
| Rust | `2fdfde30…` | 9 973 037 | 63 | rebuilt after the Python agent's own findings were fixed, plus the S-nn renumbering |

Between the two, `spec/` gained the S-26 and S-27 corrections and the package
gained a `provenance/` bucket in `entry_order` (S-28). Nothing about the graph,
the payloads, the recipe or the disclosure changed. The Rust agent therefore
tested the *corrected* file — a weaker test of those three findings and a fair
test of everything else.

**Deviations from the brief, recorded rather than hidden.**

1. **Two agents, not four, both from one model family.** The brief asked for
   two. It is not a sample, and run 2 does not claim to be one.
2. **C was dropped for an environment reason, not a design one.** This host's
   mingw gcc cannot compile `int main(void){return 0;}` — cc1 exits 1 with no
   diagnostics — so a C agent would have measured a broken toolchain rather
   than the format. Run 1 did test C, on the same spec, successfully.
3. **The first Rust agent died without delivering a report**, 21 minutes in,
   after building a complete 3 520-line reader across eight modules
   (`zipfile.rs`, `jsonlite.rs`, `msgpack.rs`, `crypto.rs`, `inflate.rs`,
   `png.rs`, `labhog.rs`, `werk_inspect.rs`) and extracting the source image,
   the style plate and the `WKEM` payload. Its workspace survives and shows how
   far it got; its report does not exist. **It is counted neither as a success
   nor as a failure of the format** — it is a harness loss. The run was
   repeated **fresh**: a new agent in a new workspace, never a resume, per the
   house rule. The counted Rust result is that second run.
4. **Neither agent's transcript was retained.** The harness wrote both task
   output files as zero bytes. The Rust agent's report survived because it came
   back in its completion message; the Python agent's per-agent process detail
   — the order in which it read the embedded resources, per-part timings,
   whether it looked at the bundled loaders — **cannot be reported**, and is
   marked *not recorded* below rather than guessed. The Python agent's *program
   and its output* survive and are the evidence for everything claimed about
   it. This is the run's own finding: an experiment whose evidence lives only
   in a transcript is one lost file away from being an anecdote. Run 3 must
   have every agent write its report to a file in its own workspace — and note
   that the tool layer blocked the relaunched agent from doing so when asked
   mid-run, so that has to be arranged some other way.
5. **Wall-clock times are not comparable to run 1.** Run 1's 486–806 s bought
   open/list/verify/extract. Run 2's task set adds an envelope parser and two
   plain-language reports. Compare the numbers to each other, not across runs.

**Logs, committed so every number below can be checked rather than believed:**

| file | what it is |
|---|---|
| `gauntlet/round2/python-werk_inspect.py` | the Python agent's program, verbatim (1 277 lines) |
| `gauntlet/round2/python-run.txt` | its complete output |
| `gauntlet/round2/rust-werk_tool.rs` | the Rust agent's program, verbatim (1 728 lines) |
| `gauntlet/round2/rust-run.txt` | its complete output |

---

## Agent 1 — Python

**Succeeded, all five tasks.** One file, 1 277 lines, standard library only.
Wall clock from workspace timestamps: fixture handed over 11:25:17, first
extraction 11:31:46, final program 11:33:23 — about **8 minutes**. Per-part
timings: *not recorded*.

Its own verdict line: **23 hard checks run, 0 failed.** Signature state
`SIGNED-AND-VALID`.

| check | result |
|---|---|
| all 7 declared `input_hash` values recompute | PASS — "so no derived node is stale" |
| Ed25519 against RFC 8032 vector 1, from `MINI-SPECS` §12 | PASS |
| chain entry 0 signature, `prev_entry_sha256`, anchor equality | PASS |
| `container.total_size_bytes` | 9 927 038 — "it is NOT the zip's own size, 9 969 937" |
| `preview_prefix_bytes` recomputed from the zip's own local headers | declared 998 658, computed 998 658, covering 58 entries |
| every preview-tier entry physically precedes that offset | PASS — "a ranged read really does yield the browsable tier" |
| physical order vs `entry_order` under the S-14 two-pass rule | **62 of 63 matched** — the one miss is S-28 |
| generated source is `inferred`, not `measured` | PASS — "grade 'descriptive' and stamp 'inferred' agree" |
| both derived images `measured`, sourced, naming `lanczos3` | PASS |
| recipe and disclosure name the same models | PASS — SPEC §3.12 rule 5 |
| `reproducibility_note` present, `unrecorded[]` non-empty | PASS — 6 facts |
| every input medium the recipe names is embedded by hash | PASS — law 1, "only weights may be absent" |

**The envelope.** Magic `WKEM`; `payload_origin` recomputed as
`16*ceil((12+header_len)/16)` and confirmed against the declared 704; both
branches checked explicitly — "`vector` takes the FIRST … `palette` takes the
SECOND (stride 16 != esz 4 -> size==16*8==128). Both checked." It then decoded
the descriptor *semantically*: named the 4×4×4 CIELAB histogram, printed which
10 of 64 colour bins are occupied with their percentages, and drew the 8-bin
orientation histogram as a bar chart.

**Then it recomputed it** — steps 1–9 of `embedding.layout.txt` §4 over
`image/source.png`, in its own code:

```
max |recomputed - stored| : vector  0.000e+00   (tolerance 1.0e-06)
max |recomputed - stored| : palette 0.000e+00
-> [PASS] the stored descriptor really is a measurement of these pixels.
```

It independently noticed the palette "weights sum to 0.995117 — these are the
top 8 bins, not a cover", which is S-24 found from the outside.

**Recipe and disclosure.** It reconstructed the v1/v2 prompt split unprompted,
printed the difference byte for byte (1 716 → 1 816), and repeated the file's
own caveat: "RECONSTRUCTED, not recorded. It is very probably what was sent and
it is not evidence that it was." On the disclosure it got the doctrine right
without being told:

> "the format ships facts, the viewer applies jurisdiction, and the format
> contains no enforcement of any kind. Nothing here obliges any viewer to do
> anything; a viewer that ignores every field above is still conformant. What
> this program must not do is paraphrase the claim into a different one."

Unprompted, it drew the two distinctions the spec cares most about: the chain
"verifies, but its key is a published dev key with no external root of trust,
so `declared_by` is an assertion by a party and must not be presented as
verified authorship", and `x/c2pa/export.json` "is a DECLARED BUT UNIMPLEMENTED
mapping and proves nothing about C2PA interoperability".

---

## Agent 2 — Rust

**Succeeded, all five tasks.** One program, 1 728 lines, built with bare
`rustc -O` (1.94.0, no cargo, no crates, std only). **16 checks passed, 0
failed, 1 note** — the note being the deliberate `signature-unverified` state.

Self-reported timings, the only per-part breakdown this run has:

| part | time |
|---|---|
| working out the format from the file (reading, not coding) | ~20 min |
| writing the Rust, one pass | ~35 min |
| first compile — **clean, first try** | ~1 min |
| polishing output | ~10 min |
| **total** | **~65 min** |

Everything it needed it wrote from scratch from the spec inside the package:
SHA-256, CRC-32, a JSON parser, canonical-JSON serialisation, a MessagePack
subset decoder, a store-mode zip reader **with zip64 detection and refusal**,
and the `WKEM` envelope parser.

**Which resources it used, in order** — the one clean answer run 2 has to run
1's most interesting question:

1. `README.txt` — "highest-value file in the package"
2. `spec/README.md` — "row 0 sends you to `manifest_schema` before anything
   else; its node-type→schema→layout table is the whole dispatch table on one
   page"
3. `MANIFEST.json`
4. `spec/layouts/ENVELOPE.layout.txt` §1–7 — "alone sufficient to write the
   envelope + MessagePack reader"
5. `spec/layouts/embedding.layout.txt`
6. `spec/SPEC.md` §6, §10, §10.1
7. `spec/MINI-SPECS.md` §3, §5, §11
8. `spec/schemas/manifest.image.schema.json` — "only for `total_size_bytes` and
   `entry_order`'s matching rule"
9. the payload JSON

> "I did **not** open `loaders/werk_read.rs` or the C/Python loaders. The
> grammar files were sufficient, and writing the reader from the spec rather
> than from someone else's reader seemed like the point."

That is run 1's headline finding — 0/4 used the bundled loaders — reproducing
under a harder task list, and this time with the agent stating the reason.

**Verification.** CRC-32 + size on all 63 container entries; SHA-256 + size on
all 61 distinct declared files; `LICENSE` against `license.sha256`;
`input_hash` recomputed from scratch for all 7 derived versions; both
`total_size_bytes` and `preview_prefix_bytes` recomputed from the zip; physical
order against `entry_order` under the S-14 two-pass rule. It resolved the
primary image through `primary.image` → node → active version → files,
"never a guessed path".

**Every number it reported checks out against the file it was given:**
`preview_prefix_bytes` 1 001 758, `total_size_bytes` 9 930 116, 63 entries, 61
distinct declared files, 15 nodes, 7 derived versions. Verified independently
while writing this document.

**The envelope.** Header dumped with banned MessagePack format bytes rejected;
both statements of `payload_origin` agreeing (computed 704 = declared 704);
`payload_origin + payload_size == 1120 ==` file length; **both** branches of the
consistency rule; NaN/inf check; then the data — the vector's L2 norm
(1.000000006, so `normalized: true` holds), the 10 occupied colour bins decoded
back to their (L,a,b) quarters, the orientation histogram, and the 8 palette
swatches re-encoded from linear to sRGB hex **and cross-checked against the JSON
duplicate in `semantics.json` — all 8 agreeing to 1e-6, hex included.** That
cross-check is law 9's "two spellings of one fact" being audited by a stranger,
which is the only way to know it works.

**Its verdict on the file, quoted because it is the point of the exercise:**

> "Honestly: **almost nothing, and that is unusual.** … Every declared number
> is correct, including the two I expected to be approximate."

It named the traps the file defuses before a reader hits them — MessagePack's
big-endianness flagged three separate times, the `input_hash` absent-
`input_params` rule given as executable pseudocode with a note that three
earlier readers lost time to it, and ENVELOPE §4.4's worked example correcting
its own previously-printed error.

**One observation that is not a spec bug and is worth more than most of them.**
The prompt's exclusion list says "no militaria" and "no Warhammer 40000 or
grimdark iconography"; the delivered image has uniformed figures with plumed
helmets and epaulettes. The agent's own reading:

> "That is the DESCRIPTIVE grade doing exactly what the recipe warns it does —
> the recipe records the instructions, not a guarantee about the pixels."

A reader with no context inferred, from the grade alone, the single most
important thing a recipe does *not* promise. That is `core.recipe` working.

---

## Spec bugs surfaced

| id | filed as | agent | finding | status |
|---|---|---|---|---|
| S-26 | S-24 | Python (confirmed independently by Rust) | `container.total_size_bytes` has no definition anywhere; established by trying candidates against the file | **fixed** — defined in both manifest schemas |
| S-27 | S-25 | Python | the image profile's schema stated the preview tier flatly, dropping the "where `preview_tier` is absent" clause; read literally it gives 2 556 862 against the declared 998 658 | **fixed** — schema and `PROFILE-IMAGE.md` |
| S-28 | S-26 | Python | `entry_order` named no bucket for `provenance/`; 62 of 63 entries matched the declared order | **fixed** — and `run_gate_9.py` now fails on any unlisted entry |

The *filed as* column is the label each carried before the three-way S-nn
collision between stages 5, 9 and 11 was reconciled; the table is in HANDOVER
under "Finding numbers, reconciled".

**S-26 is the interesting one, because the second agent hit it after it was
fixed.** The Rust agent lost ~5 minutes to `total_size_bytes` — "it is neither
the file size nor the sum of all entry sizes, and my first read was that it was
wrong" — and then found the answer *in the schema description that the first
agent's finding had put there*. Its verdict:

> "It *is* defined precisely … but that definition lives only in the schema's
> `description` string, not in `SPEC.md` and not in the manifest. … A
> documented spec bug that was documented rather than fixed."

That is a real follow-on: a definition reachable only from a schema
`description` is worth less than one in `SPEC.md`, and the fix should be
promoted. **Filed as S-30**, open.

**Both PROPOSED rulings bit, and both held.** The Rust agent hit S-14 (it
implemented the two-pass reading and "it holds") and S-18 (the two files listed
by both versions of the `recipe` node — "exactly the S-18 case"), noted both
are marked `PROPOSED — draft-pending-Gregor`, and implemented the proposed
reading in each case without difficulty. The markers did their job: the agent
knew which sentences were still moving.

**Not a bug, recorded because the next agent will raise it too.**
`PROFILE-IMAGE.md` §9 and the manifests' `producer` blocks name builder scripts
that are not in the package. They are tool identifiers, not input media: law 1
binds what a recipe *consumed*, and every one of those is embedded by hash.

---

## What run 2 does and does not establish

**Establishes.** The envelope apparatus works from the file alone — magic,
MessagePack header, `payload_origin` agreement, both branches of the section
consistency rule, and a descriptor recomputed to the bit from a prose grammar,
twice, in two languages. The fixture gap run 1 declared is closed.
`core.recipe` and `core.disclosure` are not merely parseable but
*comprehensible*: both agents stated the reproducibility grade and what it does
not promise, the reconstruction caveat on the prompt, the unrecorded facts, and
the disclosure doctrine including the parts that limit what may be claimed —
the no-enforcement rule, the dev key proving nothing about authorship, and the
C2PA node being an explicit stub. Neither wanted anything from outside the
file. Neither used the bundled loaders, and the one whose reasoning survives
said the grammar files were the point.

**Does not establish.** Two agents in two languages from one model family is
not a sample. The per-agent process data run 1 collected was lost for one of
the two to a harness failure. Nothing here measures whether a *non-Claude*
model can do it — which run 1 already named as the honest next step and which
remains the honest next step. Nor does it test zip64, a deflate container, a
package with more than one custom-binary kind, or a damaged copy of this
fixture: run 2 ran no damage gauntlet at all.

---

# The agent gauntlet — cross-vendor round

**2026-08-08.** Two model families that are **not ours**, four runs, the same
file and nothing else.

Round 1 named it: *"The honest next run is more agents per language, **at least
one non-Claude model**, and a fixture carrying a custom binary."* The custom
binary arrived in round 2. The non-Claude model arrives here — two of them.

Full detail, every quotation in context, the isolation audit and the committed
programs: **`../results/STAGE-CROSSVENDOR-RESULTS.md`**.

---

## Headline

| | |
|---|---|
| Vendors | **2** — OpenAI (Codex CLI) and Moonshot AI (Kimi Code CLI) |
| Runs | **4** — each vendor on round 1's task and on round 3's splat task |
| **Success rate** | **4 / 4** |
| Round-1 task times | **558 s** (OpenAI) · **106 s** (Moonshot) |
| Splat task times | **512 s** (OpenAI) · **377 s** (Moonshot) |
| Used a bundled loader to learn the format | **0 / 4** |
| Ported a bundled loader | **0 / 4** |
| Read a bundled loader at all | 1 / 4, *after* its own reader already ran clean |
| Wanted anything from outside the file | **0 / 4** |
| Opened `spec/` at all | **3 / 4** — the exception is the finding |
| Splat point count, both vendors | **281 498**, matching round 3's committed sample to the printed digit |
| Defects found in the (post-round-3) splat package | **0** |
| New findings | **5** (S-XV-1 … S-XV-5) |

---

## The two vendors, exactly

| | OpenAI | Moonshot AI |
|---|---|---|
| CLI | `codex` **0.144.1** | `kimi` (Kimi Code CLI) **0.15.0** |
| model id, as the harness records it | **`gpt-5.6-sol`** (`model_provider: "openai"`, from the session rollout) | **`kimi-for-coding`** (`provider=kimi model=kimi-for-coding modelAlias=kimi-code/kimi-for-coding`) |
| effort | `high` (set for this run) | `thinkingEffort=high` (CLI default for this profile) |
| endpoint | OpenAI, via the CLI's existing sign-in | `https://api.kimi.com/coding/v1` |
| network posture | **none** — the sandbox contract reads *"Network access is restricted"* | available, **not used**: 12 tool calls, no URL or host anywhere in the transcript |

The Moonshot model id is a coding-plan alias, not a dated checkpoint, and three
names for it disagree: config `display_name` `Kimi-k2.6`, self-report
`kimi-k2.5`, wire id `kimi-for-coding`. All three are recorded and none is
claimed; a model's self-report is not evidence.

**Isolation was audited, not believed.** Every absolute path in both transcripts
was extracted: the OpenAI transcript contains seven, all inside its own
workspace; the Moonshot transcript contains none at all. Neither touched a werk
repository. The artifact was the **committed pinned fixture** —
`fixtures/crate-v1.werk` `d5fd9007…79fabf` — which makes this the first round
directly re-runnable as a comparison rather than as a fresh experiment.

---

## Round-1 task, per vendor

| | OpenAI `gpt-5.6-sol` | Moonshot `kimi-for-coding` |
|---|---|---|
| result | **SUCCESS**, 558 s | **SUCCESS**, 106 s |
| declared hashes verified | **203** in 10 families | **172** manifest file hashes |
| zip CRC-32 | 174 / 174 | not a separate pass |
| `input_hash` freshness | **25 / 25** | not attempted |
| `spec_sha256` | 1 / 1 | not attempted |
| conventions | 21 / 21 | not attempted |
| Ed25519 | verified, gated on the package's own RFC 8032 vector | declined, by name |
| package files read for meaning | 9 | **1** |
| used the bundled loaders | no | no |
| wanted anything outside the file | no | no |
| stumbles | 10 | 5 |

Both extractions were graded by the orchestrating agent against `MANIFEST.json`
rather than accepted from the reports: `geometry/game.glb` to `eee8b3cb…4ef2ce`
and `audio/sfx/crate-impact-hard-surface.wav` to `1e634f03…59aa5e`, identical in
both cases, both vendors. Both programs were re-run in a third directory and
their complete output is committed.

**The result that matters most for the ledger: `gpt-5.6-sol` did not stumble on
`input_hash`.** S-10 — three of four round-1 agents' longest detour, 0 of 25
hashes for all three — was implemented correctly first pass by a foreign model
and appears nowhere in its stumble list. **25/25.** The fix holds outside the
model family that found the bug.

**Its refusal of the loaders is the cleanest yet, and a weaker datum for it:**

> "I did **not** open any bundled reader as source, run it, import it, compile
> it, or port it. … The Python source would have been permissible to read, but
> doing so was unnecessary and would have weakened the result of the isolation
> experiment."

An agent reasoning about the protocol is no longer a naive implementer.
Recorded, not smoothed over.

**The Moonshot run read one file.** It recognised the container from `xxd`,
listed entries, extracted `MANIFEST.json`, read it — and wrote the program. It
never opened `README.txt`, `spec/README.md`, `SPEC.md` or `MINI-SPECS.md`:

> "No other internal files needed to be read individually before writing the
> program; `MANIFEST.json` is self-contained enough for the required tasks."

And it was right: 172/172 hashes, all 36 nodes listed with their meanings, both
payloads written with matching digests, 106 seconds. On the signature it
declined rather than guessed — round 2's Rust move, arrived at independently by a
third vendor:

> "I did not verify the signature because … doing so correctly would require
> understanding the exact signed payload construction from the spec."

---

## Splat task, per vendor

| | OpenAI | Moonshot |
|---|---|---|
| result | **SUCCESS**, all three tasks, 512 s | **SUCCESS**, all three tasks, 377 s |
| point count | **281 498** | **281 498** |
| zip CRC | 77 / 77 | all |
| declared file hashes | 75 / 75 | 75 / 75 |
| `spec_sha256` | not attempted | verified |
| Ed25519 | not implemented; state reported **`unverified`** | not implemented; said so and why |
| WKPC against WKGS | positions **byte-exact**; **all 844 494 colour bytes** recomputed and matched | all 281 498 positions matched; formula confirmed |
| three embedded tools, roles, paths, source quoted | yes | yes |
| executed anything from the file | no | no |
| package files read | ~17 | **14** |

Round 3's agent (ours) recorded `[0] -0.06007473 1.62525749 0.93507129 -> 39 19
6`. `gpt-5.6-sol` wrote `-0.0600747317, 1.62525749, 0.93507129, 39, 19, 6` as row
0 of a 281 498-row CSV; `kimi-for-coding` printed `-0.060075 +1.625257 +0.935071`
and `39 19 6`. **Three independent readers, three model families, one set of
numbers.**

The OpenAI cross-check goes past round 3's:

> "All 3 377 976 position bytes equal the WKGS means section byte-for-byte. For
> every point I recomputed each colour channel as
> `round-half-even(clamp(0.5 + 0.28209479177387814 * sh_dc, 0, 1) * 255)`; all
> 844 494 stored colour bytes matched."

It found the round-half-even rule in `tools/werk-pointcloud-run.config.json` —
the one place it is written down.

**Neither found a defect in the splat package**, which had already been through
round 3's four fixes. The absence is the point: two foreign models read the
corrected package end to end and had nothing to say about it.

### Two round-1 behaviours reproduced verbatim in a foreign model

**The loader read at the end as a cross-check, never before.** Round 1: "2/4
read a bundled loader at all, both *after* their own reader already ran clean."
The OpenAI splat agent did exactly that, and named the reason — to confirm the
bundled reader *also* reports Ed25519 as unverified. Across this round's four
runs: **0/4 used a loader to learn the format, 0/4 ported one, 1/4 read one after
the fact.** Round 1's ratio, from vendors that never saw round 1.

**Recognition is not fully excluded — and the specification caught it again,
three times over.** Round 1's JavaScript agent wrote a zip reader from memory
before opening the spec, and the spec caught one gap (zip64). The OpenAI splat
agent did the same, flagged itself unprompted, and the spec caught three:

> "I wrote the provisional central-directory parser using remembered ZIP field
> positions before opening the package's own ZIP mini-spec. That evidentiary
> order was too eager under this experiment's rules. I later read
> `spec/MINI-SPECS.md` from inside the package, audited the parser, and
> found/fixed three robustness gaps: EOCD false-signature disambiguation,
> explicit ZIP64 sentinel rejection, and drive-letter path rejection."

That is §7's recognition threat behaving exactly as §7 says it does, in a model
family that is not ours, self-reported.

---

## Findings — S-XV-1 … S-XV-5

| id | seen by | one line | status |
|---|---|---|---|
| **S-XV-1** | OpenAI | "every declared hash" has no single exhaustive list; `core.provenance`'s `consumed[].sha256` is a current-package declaration the manifest checklist does not cover | filed, real |
| **S-XV-2** | OpenAI | the `spec_sha256` construction says each file's "own sha256" without saying *declared* or *recomputed* — identical on a valid package, divergent on a damaged one | filed, real |
| **S-XV-3** | OpenAI | `spec/examples/MANIFEST.example.json` carries valid-looking hashes for a different, abridged package; telling example literals from current declarations is reader work | filed, low |
| **S-XV-4** | Moonshot | `primary.sound` names a *node*; which file inside is the sound is carried only by `role: "best"` — the successor to S-13 | filed, real |
| **S-XV-5** | Moonshot, by omission | a reader that reads **only `MANIFEST.json`** passes round 1's criteria — so those criteria can be met without the specification | filed; a finding about the **experiment** |

### S-XV-5 is the finding of the round

Round 1's headline is *0/4 used the bundled loaders*, and its justification is
that the metric means what we claim **only if the specification is the path of
least resistance**. The Moonshot run shows that for round 1's task, on this
fixture, it is not — **`MANIFEST.json` is**. One file, 106 seconds, all five
declared success clauses met, `spec/` never opened.

That is not a failure of the format; a manifest rich enough to drive a correct
reader on its own is the design working. It *is* a limit on what round 1's
criteria can measure, invisible for three rounds because every previous agent
chose to read the specification when it did not have to.

**And the control arrived the same afternoon.** The *same* Moonshot model, given
round 3's splat task — which cannot be done from the manifest — read **fourteen**
files, named `spec/README.md` and `ENVELOPE.layout.txt` as its unblockers, and
took 377 s instead of 106. The manifest-only behaviour is a property of the
**task**, not the vendor.

Three consequences, stated rather than resolved: round 1's criteria under-test
the specification; *"0/N used the loaders"* should be reported beside *"N/N
opened the specification at all"*; and a future round should say "verify every
hash the package declares, wherever it declares it" — which is exactly the
sentence S-XV-1 says is missing from the specification itself.

---

## A measured caveat on self-reported times

Both agents were asked for their own wall-clock sense, and both were wrong by a
large factor against the process clock:

| run | measured | agent's estimate |
|---|---:|---|
| OpenAI, round-1 task | **558 s** | "roughly 20–25 minutes" |
| OpenAI, splat task | **512 s** | "~48 minutes" |
| Moonshot, round-1 task | **106 s** | "~15–20 minutes" |
| Moonshot, splat task | **377 s** | "roughly 50–55 minutes" |

Every time above is the measured one. Rounds 1 and 3 recorded harness-observed
wall clock and are comparable; **round 2's ~65 min Rust breakdown is
self-reported** and on this evidence should be read as an impression rather than
a measurement.

---

## What this does and does not establish

**Establishes.** Two model families that are not ours, on the same fixture, the
same task sentence and the same isolation rules, both succeeded — and in the
same *shape*: extraction resolved through `primary` rather than guessed, hashes
checked rather than assumed, the bundled loaders declined, nothing wanted from
outside the file, and Ed25519 either built from the file and gated on the file's
own vector or declined by name using the specification's fourth token. The two
behaviours round 1 named as its most likely shared blind spots — the loaders, and
remembered cryptographic constants — both reproduced, and both reproduced with
the same mitigation working.

**Does not establish.** n = 1 per vendor per task; four runs add two model
families, not statistical power. Both vendors are frontier commercial coding
models inside agentic harnesses: *not our model family* is not the same as *a
different kind of implementer*, and small open-weights models, non-agentic
implementers and humans remain untested. The two harnesses are not equivalent —
one had no network at all, the other had network and did not use it, and that
second isolation claim rests on transcript audit rather than on a sandbox. No
damage gauntlet was run: neither vendor synthesised its own damage, and the
damaged fixture was not handed out. And round 1's criteria turned out to be
satisfiable without the specification, so any strengthening of the cross-vendor
claim belongs against the harder tasks, where both vendors did open `spec/`.

**The "one model family" threat is softened, not removed**, and the paper's §7
should say which of the two it is.

---

# The agent gauntlet — open-weights round

**2026-08-09.** Six small local models, no agentic CLI, one GPU, and a test
that fits in 31 490 tokens.

Full record: **`results/STAGE-OPENWEIGHTS-RESULTS.md`**. Harness, fixture
builder, grader, prompts and every run's program and transcript:
**`gauntlet/roundOW/`**.

This round exists because the cross-vendor round closed the *vendor* gap and
said so in its own verdict — "small open-weights models, non-agentic
implementers and humans remain untested". Two of those three are now tested.

## Headline

| | |
|---|---|
| Models | **6** — 30B-A3B MoE coder, 30B MoE reasoner, 27B dense, 9.4B, 8B non-coder, 4B |
| Harness | `gauntlet/roundOW/driver.py` — **no tools**: the whole self-description is inlined in the prompt, the model emits one complete program, the harness runs it and feeds back stdout/stderr/traceback. 8 iterations or 45 min. |
| Inline context package | **31 490 tokens**, measured (LM Studio's own `prompt_tokens`) |
| **Success, first attempt** | **1 / 6** |
| **Success, best of attempt + one retry** | **4 / 6** |
| Size threshold | passes from **9.4B up**; degrades at **8B**; absent at **4B** |
| Spec-forcing envelope task | **0 / 2** |
| Extracted bytes graded by the orchestrator | 4 / 4, both digests, **identical to the cross-vendor round's** |
| Used a bundled loader to learn the format | **0 / 6** |
| Wanted anything from outside the file | **0 / 6** |
| Findings | **S-OW-1 … S-OW-6** |

## Per model — round 1's task sentence on `mini-v1.werk`

| model | params / quant | loaded ctx | attempt 1 | retry | final | wall (harness-measured) |
|---|---|---:|---|---|---|---|
| `qwen/qwen3-coder-30b` | 30B-A3B / Q4_K_M | 65536 | **PASS** | — | **PASS** | **74.0 s** |
| `zai-org/glm-4.7-flash` | 30B / Q4_K_M | 65536 | FAIL — 3 replies of pure reasoning, 0 chars content | **PASS** (generation cap raised 16k→32k) | **PASS\*** | 1152.5 s |
| `ebai3.6-27b-unscensored` | 27B / unlisted | 65536 | FAIL — same `SyntaxError` 5× | **PASS** | **PASS** | 724.6 s |
| `zai-org/glm-4.6v-flash` | 9.4B / Q8_0 | 131072 | FAIL — clean exit, **wrote nothing**, declared success | **PASS** | **PASS** | 435.4 s |
| `llama-3.1-8b-lexi-uncensored` | 8B / unlisted | 131072 | FAIL — `json.loads` on the container itself, 8× | PARTIAL — mesh byte-exact, **descriptor JSON extracted instead of the WAV** | **FAIL** | 288.6 s |
| `qwen3.8_4b_distilled` | 4B / Q8_0 | 131072 | FAIL — `EOCD not found`, 8× | FAIL — again | **FAIL** | 593.7 s |
| — *added 2026-08-10, **frontier-open-weights class**, a different round and not part of the 1 / 6 and 4 / 6 rates above* | | | | | | |
| `deepseek-ai/DeepSeek-V4-Flash-0731` | **284B-A13B / MXFP4** | **1048576** | **PASS** — byte-exact, first clean run at iteration 2 | not needed | **PASS** | **2 991.2 s** |

Envelope task (adapted prompt, same fixture): `qwen3-coder-30b` passed the
listing and the loader-identification clauses and **fabricated** the decoded
values rather than implementing the MessagePack header — it printed
`71554213196777853550592.0000` for a quaternion component and never reported
`pose_count` (truth: 2). `llama-3.1-8b` never opened the file. **0 / 2.**

## What broke, and what it says

Every failure of a *boring* encoding was a capability failure at 8B and below —
no model above 9B stumbled on zip, JSON, GLB, WAV or SHA-256. What defeated
everyone was the two places werk is **not** boring:

* **the signature.** `mini-v1.werk` is `signed-and-valid`; models that tried
  reported `present-and-invalid` — *tampering, on an intact package*. The
  sentence that says what werk signs (`werk-sig/1 LF manifest_sha256 LF …`)
  lives only in `spec/SPEC.md` and `signature.schema.json`, neither of which fit
  the 31 490-token package. **S-OW-1.**
* **the binary envelope.** The grammar was in the package; the *worked hex
  example* was not. **S-OW-3.**

And the one wrong artifact produced by a model that thought it had succeeded:
`primary.sound` names a **node**, the node's `files[]` starts with a
`descriptor`, and the 8B model took `files[0]`. That is **S-XV-4/S-13 with a
measured consequence** — **S-OW-2**.

**Small models are a better instrument for finding spec gaps than large ones:**
a frontier model routes around a missing sentence, a small one walks into it.
All three knowledge-barrier findings were invisible to every agent in rounds
1–3 and the cross-vendor round.

## Verdict

The implementer-diversity threat is **materially reduced**: five weight classes,
four architectures, four training lineages, none ours, none agentic, no network,
four byte-exact artifacts. It is **not** extended downward — below 9B this
protocol did not get a working reader out of these models, and the rung below
that (a human supplying hands and judgement) remains untested.

---

# The agent gauntlet — self-run round (2026-08-09)

Full record: **`results/STAGE-SELFRUN-RESULTS.md`**. Fixture builder, verifier,
harness scripts, the task sentence, both transcripts and every produced byte:
**`gauntlet/roundSR/`**.

## Headline

**A werk package that carries a language model AND the complete source of a
runtime that executes it. Two agents, two vendors, one sentence each, one file
each. 2 / 2 SUCCESS, no retries, both verified against the package's own
temperature-0 test vectors — byte for byte, by the orchestrator, not by the
agents' reports.**

## The fixture

`gauntlet/roundSR/selfrun-v1.werk` — **62 525 273 B**, sha256
`1f8e1270b89371a5acc80aa854db3572631f7dac9a053fd045da0af112d51f17`, 85 entries,
14 nodes, profile **`model/1-draft`**, pinned in
`gauntlet/roundSR/fixture-pin.json`. `python gauntlet/roundSR/verify_selfrun.py`
→ **29 PASS, 0 FAIL**.

It carries Karpathy's **stories15M** (15 191 712 parameters, f32, 6 layers,
dim 288, vocab 32 000) and its tokenizer, **byte-identical to their
publishers'**; **llama2.c's `run.c` + `win.h` + `win.c` as a `core.tool` in
`form: source`, with no prebuilt artifact anywhere in the package**; a
byte-exact layout grammar for each of the two foreign binary formats (the
checkpoint grammar's offsets account for all 60 816 028 bytes with nothing left
over); a `BUILD-AND-RUN.md` with the exact command per platform and which of
them were measured; and two temperature-0 test vectors produced by building that
runtime and running it. Licences: MIT runtime, MIT-by-model-card weights, corpus
terms explicitly not established — `gauntlet/roundSR/SOURCES.md` has every URL
and hash. **It is handable to a stranger**, which is the S12-9 lesson applied.

## The task, committed verbatim before the run

> This file contains a language model and everything needed to run it. Make the
> model run and produce text. Verify your result against whatever correctness
> information the file provides. Report what you did.

No hint about zip, about C, about llama2.c. Fresh directory containing only the
`.werk`. Cap 45 min. Wall clock measured around the CLI process, never
self-reported.

## Per vendor

| | OpenAI `gpt-5.6-sol` (codex 0.144.1) | Moonshot Kimi 0.15.0 |
|---|---|---|
| result | **SUCCESS**, first attempt | **SUCCESS**, first attempt |
| wall clock | **98.2 s** | **647.5 s** |
| tool calls | 14 shell commands | 98 (`Bash` 82, `Read` 7, `Write` 7, `Edit` 2) |
| files read from the package | **4** | **7** |
| what unblocked it | `tools/llama2c/BUILD-AND-RUN.md` | same |
| compiler | MSVC 19.43.34808 (VS BuildTools) | mingw-w64 gcc 15.2.0, `-static` |
| source modified | **none** | `win.c` only, exactly the two fixes the package documents; **`run.c` byte-identical** |
| stdout LF sha256 | match ×2 | match ×2 |
| stdout CRLF sha256 | match ×2 | match ×2 |
| token ids | not attempted | **match ×2** (65, 33) — applied the package's own instrumentation diff |
| opened `MANIFEST.json` | no | no |
| opened anything under `spec/` | no | no |
| used a bundled loader | no | no |

The generated text, identical from both and from three independent rebuilds:

> Once upon a time, there was a little girl named Lily. She loved to play
> outside in the sunshine. One day, she saw a big, red ball in the sky. It was
> the sun! She thought it was so pretty. / Lily wanted to play with the ball,
> but it was

## What the round measured that nobody planned

**Four independent builds, two compilers, identical model output.** The vectors
were produced with MSVC **19.38.33143**; they were reproduced by MSVC
**19.43.34808** (a binary 5 120 B smaller), by a third MSVC build inside the
OpenAI agent's sandbox, and by a **static mingw-w64 gcc** build. The
`BUILD-AND-RUN.md` caveat that a vectorising compiler may reassociate the
reductions in `rmsnorm`/`softmax`/`matmul` is still a correct caveat — it simply
did not bite across these toolchains at `-O2`/`-O3`, and that is now a
measurement rather than a worry.

**A documented FAILURE did more work than a documented success.**
`BUILD-AND-RUN.md` §2c records, verbatim, the two errors mingw-w64 gcc produces
on `win.c` and says the fix is one cast and one `#if !defined(__MINGW32__)`
guard — and says why the package declines to ship it (patching `win.c` would
change bytes whose whole value is that they hash to upstream). The Moonshot
agent, which never found MSVC, hit both errors and applied exactly those two
fixes, then diagnosed a third problem the package could not have known about
(this mingw's `libwinpthread-1.dll` does not export `clock_gettime64`) and
rebuilt `-static`. **In a package that must be BUILT, the negative results are
payload.** Filed as **S-SR-11**.

## Findings — S-SR-1 … S-SR-11

Eleven, none fixed, all in `results/STAGE-SELFRUN-RESULTS.md` §3. Five are
schema gaps a real `model/1` would have to close first: **S-SR-1**
`core.tool.role` has no word for an *executor* and both candidates are wrong;
**S-SR-2** §3.11's hermeticity rule cannot be satisfied by any model package,
because a training corpus is orders of magnitude larger than the artifact and no
embedded tool reproduces it; **S-SR-3** `core.recipe` has no `train` role, so a
training step must be `other`; **S-SR-4** `core.tool.config.environment` is
interpreter-shaped — five keys, none of them a compiler, a flag set or a binary
— so a compiled tool's re-run-sensitive facts have nowhere structured to go;
**S-SR-5** a recipe step cannot say its tool is deliberately NOT carried;
**S-SR-6** `core.provenance.consumed[]` records what was consumed and has no
field for where it came from. Plus **S-SR-7** (`primary` has no model slot —
S12-7 recurring), **S-SR-8** (every bundled loader skips all three nodes that
hold the model, which is law 12 working and also an argument for promoting
`x.model.*` to `core.model.*`), **S-SR-9** (a runtime's "completeness" is
measured by building it, not by counting files — `win.h` declares `mmap` and
`win.c` defines it), **S-SR-10** (S-XV-5 confirmed on both vendors: 0/2 opened
the specification, 0/2 used a loader, 2/2 succeeded — what an agent reads is set
by the task) and **S-SR-11** above.

## Verdict

Previous rounds proved a stranger can **read** a werk package. This one proves a
stranger can **run** one: the format's self-containment property extends from
documents to executable artifacts, and the "source always, never auto-execute"
doctrine cost nothing in the one case that most obviously stresses it — the
package that most wants to ship a binary ships none, and both agents compiled it
themselves.

What it does **not** establish is stated plainly in the result file's §5: two
frontier agentic models is vendor diversity, not implementer diversity; and this
task did not exercise the manifest, the hashes, the layout grammars, the
provenance or the signature at all, so it does not show the format was
*necessary* — a plain zip with the same README would likely have produced the
same 98 seconds. The obvious next experiment is the adversarial one: a *damaged*
self-run package, or one whose weights layout must be recovered without a
README, so the layout grammars have to earn their bytes.

---

# The agent gauntlet — hardcopy round (2026-08-09)

**One werk package, printed on three sheets of A4 as plain prose plus 2D
barcodes, where the printed prose is the only specification of the barcode.**
Full record with every number and S-HC-1 … S-HC-6:
**`../results/STAGE-HARDCOPY-RESULTS.md`**. Design draft:
**`../docs/HARDCOPY-DRAFT.md`**. Everything else: **`roundHC/`**.

## Headline

| | |
|---|---|
| Serialization | **`werk-hardcopy/1`** — a purpose-built matrix code, invented for this round, designed to be describable in two printed pages. **Not QR**, and the decisive reason is experimental, not size: a code that already exists cannot distinguish "read the printed prose" from "called a library". |
| Payload | `roundHC/smiley-v1.werk` — 8168 B, profile `image/1`, `signed-and-valid`, one 64×64 PNG of a smiling face. A deliberately REDUCED package that vendors no `spec/` and no `loaders/`, and says so in its own `README.txt`. |
| The artifact | **3 sheets of A4** at 300 DPI: 2 of prose, 1 carrying the last of the prose plus all nine symbols |
| Test input | the degraded arm — rotation 0.55–0.90°, 1.1 px blur, illumination ramp to 62 %, σ = 9 noise, JPEG q82 |
| Control (reference decoder, written only from the printed prose) | **PASS**: 8/9 symbols read, **`seq 7` repaired by the parity symbol**, sha256 exact, smiley pixel-identical over 4096 pixels |
| Archaeology agent | Codex CLI **0.144.1** on **`gpt-5.6-sol`**, effort `high`, a fresh directory holding **only the three JPEGs**, task sentence committed verbatim beforehand, **no format hint**, network absent (audited) |
| **Result** | **5 / 5 on the success ladder, first attempt, in 206.7 s** — process wall clock |
| Byte grade | `recovered.werk` is **byte-identical** to the printed payload; the extracted PNG is identical to the generator's reference, **0 pixel differences over 4096** |
| Prose or prior knowledge? | **prose, and it cannot be otherwise** — no library and no training data contains `werk-hardcopy/1` |
| Density | 1112 file bytes per symbol; 12 symbols per symbols-only A4 sheet; **11 861 file bytes per sheet = 88.4 sheets per MiB** |

## The success ladder, graded by the orchestrator from the artifacts

| step | verdict |
|---|---|
| read the prose | **PASS** — it stated the file length, the 8-data-plus-1-parity structure and the SHA-256 before writing any code |
| implemented a decoder | **PASS** — `decode_werk.py`, 6 414 B, from scratch |
| reassembled, CRCs pass | **PASS, 9/9** — every recomputed CRC matched both the codeword's own and the caption printed beneath the symbol |
| whole-file sha256 | **PASS** — `b0823016…7617a6`, byte-identical to the printed payload |
| recognised and opened the `.werk` | **PASS** — "a ZIP-compatible WERK 1.0 package named *Smiley*", all five entries, uuid, profile, and every declared hash re-verified |
| **the recovered image IS the smiley** | **PASS** — 0 pixel differences |
| the signature | **correctly declined** — see S-HC-4 |

## What the round measured that nobody planned

**Prose that describes a code is a program, and it has bugs.** Two were found
by implementing the decoder from the draft prose alone and running it on a
degraded photograph, and both fixes went onto the printed sheet as WARNINGs with
their measurements: "take the topmost/leftmost/rightmost/bottommost pixel" is
wrong at one degree of rotation (a 600-px edge 6 px thick has hundreds of pixels
sharing the smallest column — measured side lengths 470/237/497/125 for a
593-px symbol), and the frame must not be assumed to be one connected piece
under an illumination gradient. **The generalisation is uncomfortable and worth
stating: every prose specification in `spec/` is in exactly this position.**

**The emptiest symbol is the hardest to read.** `seq 7` carries mostly zero
padding, so its data area is nearly blank, so its tiles have no contrast, so the
local thresholder falls back and admits noise. It is the one symbol the
reference decoder lost, on every run. (S-HC-3.)

**S-OW-1 reproduced at the paper tier.** The signed-message construction
`werk-sig/1 LF …` is in `spec/SPEC.md` and the signature schema and nowhere
else. The agent tried three candidate messages, all failed, and — unlike the
open-weights models, which raised a false tampering alarm — **correctly refused
to render a verdict**. Two independent rounds, three model families, five weight
classes; still open. (S-HC-4.)

**"Sufficient" and "used" are different claims.** Two of the seven printed steps
were not implemented as written: the local threshold was replaced by a global
sweep, and the page-wide symbol search by nine crop rectangles read off the
image by eye. The load-bearing sections were geometry, bit order, codeword
layout, CRC-32 and reassembly — the parts no amount of looking supplies. Any
future self-description claim should report which sections the implementer
actually needed. (S-HC-5.)

## Verdict

Previous rounds proved a stranger can read a werk package, and the self-run
round proved a stranger can run one. This one moves the claim one substrate
down: **the specification survives the loss of every byte.** Given photographs
of paper and one sentence naming no format, a fresh agent implemented a code
that did not exist, recovered 8168 bytes exactly, checked them against a digest
printed in words, opened the package, verified every hash it declares, and
extracted a smiling face — in three and a half minutes.

What it does **not** establish: N = 1, one vendor; nobody printed or
photographed anything, so the degradation is a stated model and not a camera;
the page-scan half of the printed procedure went unexercised; and the page
arithmetic is unflattering — at 88.4 sheets per MiB, `fixtures/crate-v1.werk` is
**1 154 sheets** and `fixtures/gsplat-v1.werk` is **2 550**. Paper proves the
property. It does not store the corpus.

---

# The agent gauntlet — the open-weights POST-FIX arm

**2026-08-09.** The three knowledge-barrier findings of the open-weights round
were turned into spec (S-OW-1, S-OW-2, S-OW-3, plus S-OW-4), the package was
rebuilt, and the models that had failed were run again against it.

Full record: **`results/STAGE-SPECFIX-OW-RESULTS.md`**. Runs, programs and
transcripts: `gauntlet/roundOW/runs/postfix-*`.

**The claim under test, registered before the runs:** *a failure located a spec
gap; the gap was fixed; does the same model now pass?* **It did not hold for
either failing model.** Reported straight.

| | |
|---|---|
| Protocol | identical: `driver.py`, no tools, inline context, 8 feedback iterations, one model loaded and one request in flight, cold start per run |
| Package | **32 722 – 39 767 tokens** depending on tokenizer (was 28 220 – 33 044): the worked WKRP hex example is now an eighteenth item, per S-OW-3 |
| Fixture | rebuilt `mini-v1.werk` `f7bdcc85…`, carrying `payload_file` on the audio node and the worked hex example in its `spec/` tree |
| Models run | **5** (9 runs) — 3 re-runs, 2 post-fix-only lineages, 1 unloadable |
| Graded by artifact | always |

### Re-run population

| model | pre-fix | post-fix attempt 1 | retry | final |
|---|---|---|---|---|
| `zai-org/glm-4.6v-flash` 9.4B *(control)* | PASS on retry | **PASS** | — | **PASS**, first clean run at iteration **1** (was 3) |
| `llama-3.1-8b-lexi-uncensored` 8B | FAIL | FAIL — **descriptor JSON written as the sound, again** | FAIL — wrote nothing | **FAIL** |
| `qwen3.8_4b_distilled` 4B | FAIL | FAIL — `EOCD not found` | FAIL — **`import zipfile`, container open, 34 entries listed**, then died on a console `✗` | **FAIL** |

### Post-fix-only population (no pre-fix baseline; none implied)

| model | class | final |
|---|---|---|
| `google/gemma-4-e4b` | 7.5B raw, "effective 4B", Google | **PASS** on retry — **the first sub-9B pass in any open-weights round** |
| `nvidia/nemotron-3-nano-4b` | 4.0B, NVIDIA, `nemotron_h` | **FAIL** — computed both correct digests including the right WAV, never wrote the files |
| `google/gemma-4-12b-qat` | 12B, Google | **not run** — `lms load` fails at every context on this host; excluded, not scored |

### What it says

* **The 4B floor survives a second, independent lineage.** NVIDIA's
  nemotron-3-nano-4b failed too, so 4B was a class property rather than a quirk
  of one distill.
* **`payload_file` was in the manifest and the 8B still took `files[0]`.**
  The needed fact is now present, findable and unambiguous, and this implementer
  did not use it. Under the round's own triage that reclassifies the failure from
  knowledge to **capability** — and it is the wave's sharpest measurement:
  **making a fact machine-readable does not make a weak implementer read it.**
* **The zip advice moved the 4B one layer.** Sixteen iterations of `EOCD not
  found` became `import zipfile` and a correct listing of all 34 entries. Still a
  FAIL, but no longer at the container.
* **No false tampering alarm in nine runs**, and the weakest model in the arm
  restated the new rule back — *"reports `present-and-invalid` only when a link
  fails, not when the message construction is wrong"*. The honest limit: 1 of 13
  pre-fix runs had made that claim, and that model is not in this arm, so
  **1/13 → 0/9 with a changed roster** is consistent with the fix, not proof of it.
* Both passes reproduced `eee8b3cb…4ef2ce` and `1e634f03…59aa5e` — **the same two
  digests as rounds 1–3, the cross-vendor round and the pre-fix round**, now from
  two more model families.

**A spec fix removes an excuse; it does not supply a capability.**

---

# The agent gauntlet — gap-completion round (2026-08-09)

Three of the previous rounds' own *"what this does not establish"* sentences,
taken as a work list. Full record with every number, the discarded runs and
S-GF-1 … S-GF-5: **`../results/STAGE-GAPFILL-RESULTS.md`**. Harnesses, graders,
context packages and every run's artifacts: **`roundGF/`**.

## Headline

| | |
|---|---|
| **The finding of the round is a defect in a previous round's instrument** | **S-GF-1** — `roundOW`'s `mini` context packer dropped **every byte of every layout grammar**, silently. The banner promised "the whole normative grammar"; the block was empty; `included` still counted it; `omitted` was still `[]`. Proven against the committed `roundOW/context_package.mini.txt`. |
| Hardcopy round, second vendor | **SUCCESS — 6 / 6 rungs, first attempt, 1367.4 s, byte-identical payload AND byte-identical image.** N = 1 becomes N = 2. |
| Splat task on local models | **2 models run, both FAIL.** 3 of 5 could not be served the package on a 24 GB card. **No pass rate is reported**, and §2.5 of the result file says why. |
| Adapted self-run on a local model | **FAIL** — correct prediction, correct digest, correct `argv`, and it **never opened the container**. |
| Splat package, the number that decided the arm | **166 642 characters = 55 376 – 65 775 tokens** depending on tokenizer, against the 35 000-token budget every previous open-weights arm was built around |
| Runs discarded ungraded, both **harness** defects, both kept | **2** |
| Grader defects caught before a result was recorded | **1** |
| New spec bugs found | **0** |

## S-GF-1 is the finding, and it reaches backwards

`pick()` matched a section number with `re.match` anchored at the start of the
whole matched heading. `## 5. zip` matched. A layout grammar's heading —

```
------------------------------------------------------------
3. The header map
------------------------------------------------------------
```

— did not, so **every section of every `.layout.txt` was dropped**, in every run
of both the pre-fix and post-fix open-weights arms.

* **S-OW-3's first clause is false.** It reads *"the grammar was in the package;
  the worked hex example was not."* Neither was.
* **The spec-forcing envelope arm's `0 / 2` was never a test of the
  specification's sufficiency** — those models had a magic number, a hex head
  and a manifest, and no grammar.
* **The round-1 arm is unaffected**; its encodings came through a `##`-headed
  document the picker handled, and both passing digests stand.
* **The lesson is the uncomfortable half.** Every round enforces *"an agent's
  report is evidence about the agent, not about the artifact."* Nobody applied
  it to the harness, and the harness's own instruments — the banner, `included`,
  `omitted`, the console line — all reported a complete package.

## The three arms

### Splat task, five rostered models, two servable

Round 3's task sentence, verbatim, on `fixtures/gsplat-v1.werk`; roundOW's
protocol; graded by artifact against ground truth the grader **derives** from
the fixture (a sixth independent reproduction of `281 498` and
`-0.06007473 1.62525749 0.93507129 -> 39 19 6`).

| model | weights | ctx | package, own tokenizer | iters | wall | verdict |
|---|---:|---:|---:|---:|---:|---|
| `google/gemma-4-e4b` | 6.33 GB | 131072 | 65 775 | 8 / 8 | 749.2 s | **FAIL** — never opened the file; 0 of 8 programs mention `zipfile` or the fixture |
| `zai-org/glm-4.6v-flash` | 11.79 GB | 131072 | 55 376 | 8 / 8 | 1 489.4 s | **FAIL** — opened it, listed it, died in its own integrity pass; 3 of 8 replies were `finish_reason=length` with **0 characters** |
| `qwen/qwen3-coder-30b` | 18.63 GB | — | — | — | — | **not run** — cannot be served a 65 775-token prompt on 24 GB |
| `zai-org/glm-4.7-flash` | 18.13 GB | — | — | — | — | **not run** — same |
| `ebai3.6-27b-unscensored` | 18.46 GB | — | — | — | — | **not run** — same |

**Why three models are missing is a measurement, not an excuse.**
`qwen3-coder-30b` prefills a 30 715-token prompt at **3 751 tok/s at ctx 65536**
and a 69 485-token prompt at **274 tok/s at ctx 262144** — a 13.7× collapse, and
the cause is KV residency, not context length. `gemma-4-e4b` serves the
identical package **27× faster** because 6.33 GB of weights leave room for the
cache. A first run at 262144 was killed after 75 minutes without iteration 1
returning and is kept, ungraded, as `roundGF/runs/_discarded-ctx262144/`.

**S-GF-2, the round's second finding, is about the protocol.** `gemma-4-e4b`
said it in its first reply, before any feedback existed: *"Since actual binary
reading/execution is forbidden and only file contents are visible, the program
**simulates** the analysis."* It read the isolation clause *"do not execute
anything that came out of the file"* as *"do not read the file"*, and read
65 775 tokens of inlined self-description as the corpus rather than as
documentation of an artifact on disk. At 31 490 tokens the package plainly was
not the data. At 65 775 it plainly can be mistaken for it.

### Hardcopy, replicated — the one gap that closed

`roundHC/run_codex.sh` with the CLI swapped and nothing else: the same task
sentence naming no format, the same three **degraded** page JPEGs, the same
60-minute cap, process wall clock.

| | Codex `gpt-5.6-sol` (roundHC) | **Kimi Code CLI 0.15.0** |
|---|---|---|
| result | 5 / 5, first attempt | **6 / 6, first attempt** |
| wall | **206.7 s** | **1 367.4 s** (6.6× slower) |
| `recovered.werk` | byte-identical | **byte-identical**, `b0823016…7617a6` |
| the smiley PNG | 0 pixel differences | **byte-identical**, `9082008d…3d285` |
| decoder | written from the printed prose | **written from the printed prose**, `decoder.py` 10 414 B plus 5 analysis scripts |
| the signature | correctly declined | **correctly declined** |
| network | none (sandbox) | **available and used** — it installed numpy and opencv |

**Two behaviours reproduced that matter more than the pass.** The symbol it lost
was **`seq 7`** — the emptiest one, mostly zero padding, exactly S-HC-3 — and it
repaired it from parity and reported the difference as 592 bytes, all padding
past the file length. Three independent decoders now, the same symbol every
time. And it hit the **S-HC-4 / S-OW-1** signature wall, tried three candidate
messages, failed all three, and **declined to render a verdict** rather than
reporting tampering: four model families, three rounds, still open.

**The asymmetry is stated rather than buried (S-GF-5).** Kimi installed tooling
Codex could not. That is tooling, not knowledge — no library anywhere decodes
`werk-hardcopy/1` — so the decoder came from the prose either way. But *"two
vendors recovered it"* and *"two vendors recovered it under the same isolation"*
are different claims and only the first is measured.

### Adapted self-run — the protocol works, the model did not

The model gets no shell, so it writes **one bash script and the harness executes
it**. `driver_selfrun.py`'s docstring states the doctrine question rather than
assuming it: *source always, never auto-execute* is about a package's shipped
binaries, and a supervised harness compiling `run.c` — reviewed, committed,
byte-identical to upstream, statically screened — is not a reader executing a
stranger's binary. What cannot be claimed from this arm is roundSR's claim: this
is not an unsupervised stranger.

`qwen/qwen3-coder-30b`, ctx 65536, package **97 181 chars / 29 920 tokens**,
prefill 4 156 tok/s, 6 / 6 iterations, **140.6 s**, **FAIL**. It printed a
correct prediction every time — the unblocking file, the MSVC line verbatim, the
POSIX alternative, the `argv`, the expected text and `32680de0…afaadfb5` — and
then compiled `tools/llama2c/run.c` **directly, without ever extracting the
container**, so all six scripts died in 0.1 s. By iteration 4 it was quoting the
package's own documented mingw caveat as the reason not to try — **a documented
failure borrowed as an excuse by an implementer that never triggered it**, which
is the mirror image of S-SR-11.

Two things were thrown away to get that number honestly. The first attempt ran
under **WSL's** bash, which has no compiler at all, while the model's
`command -v gcc` probe was correct and `gcc` was on the box — a harness defect,
discarded ungraded, kept as `roundGF/runs/_discarded-wsl-bash/`. And the
grader's first version called the run **PASS**, because the expected text
appears in what it produced — it appears there because
`testvectors/generate-*.stdout.txt` is *inside the package* and therefore
inlined in the prompt. **The model printed the answer key.** Grade A is now an
echo check and only grade B — the grader invoking a binary the run built —
decides. There was no binary.

## The coverage matrix, completed

Rows are what an implementer is; columns are what it was asked to do. **bold** =
measured in this round.

| implementer | round-1 task (read a package) | spec-forcing task (decode a custom binary) | build-and-run | recover from paper |
|---|---|---|---|---|
| frontier agentic, our family | 4/4 (r1), 2/2 (r2) | 1/1 (r3) | — | — |
| frontier agentic, OpenAI | 1/1 (XV) | 1/1 (XV) | 1/1 (SR) | 1/1 (HC) |
| frontier agentic, Moonshot | 1/1 (XV) | 1/1 (XV) | 1/1 (SR) | **1/1 (GF)** |
| local, ≥ 27B, no tools | 3/3 (OW, on retry) | **not servable — a 65 775-token package on a 24 GB card (GF)** | **0/1 (GF)** | — |
| local, 9–12B, no tools | 1/1 (OW) | **0/1 (GF)** | — | — |
| local, ~4–8B, no tools | 1/3 (OW + SFX) | **0/1 (GF)**, and 0/2 (OW) on a package that had no grammar | — | — |
| human, unaided | — | — | — | — |

**What the matrix now says.** The *vendor* row is full — three frontier
families, four task kinds, every cell a pass. The *local* rows are zeros in
every column except the one task that `MANIFEST.json` alone can satisfy
(S-XV-5), and the two most interesting cells are still empty for reasons that
are **not** about model capability: the 27–30B spec-forcing cell is empty
because the specification does not fit the hardware, and the human row has never
been attempted.

## Verdict

**One gap closed, one gap re-opened as mis-measured, one gap relocated.**

The hardcopy claim is now two vendors and can drop its N = 1 caveat. The
spec-forcing claim is worse than it looked and better understood: no local model
has passed it, but until this round no local model had ever been *shown the
grammar*, so the previous `0 / 2` measured something else. And the binding
constraint on that cell turns out to be neither capability nor spec
completeness — it is that the travelling specification for a Gaussian-splat
package is **65 775 tokens**, and 65 775 tokens of KV cache plus 18.6 GB of
weights do not fit on a 24 GB card. That is a real, quantified price for the
format's central property, and it belongs in the paper beside the property.

**The round's largest defect was its predecessor's instrument, and its second
and third were its own.** Two runs discarded for harness bugs, one grader
corrected for accepting an answer key — all three caught before anything was
recorded as a result, all three committed. Zero new bugs were found in `spec/`.

---

# The agent gauntlet — frontier open-weights round (2026-08-10)

**2026-08-10.** DeepSeek-V4-Flash-0731 — 284B total / 13B active — downloaded,
verified against its publisher's digests, and served by a `llama-server` we
compiled, on eight Tesla V100s. **No vendor API and no LM Studio.**

Full record: **`../results/STAGE-DSV4-RESULTS.md`**. Harness, prompts, run
directories and every artifact: **`roundDS/`**.

This round fills the cell the coverage matrix had left explicitly empty —
*frontier capability* × *open weights, self-hosted* — and, on the way, serves a
package that the gap-completion round could not serve at all.

## Headline

| | |
|---|---|
| Serving stack | **ours**: llama.cpp **b10333** built for sm_70 with CUDA 12.8, 8× V100, port 8123, `--parallel 1` |
| Quant | **MXFP4**, the publisher's native expert format — **zero requantisation loss**, 154 991 539 328 B, both shards re-hashed on the box and matched |
| Loaded context | **1 048 576 — the model's full nominal maximum**, no KV-cache-forced reduction; the whole 1 M KV costs ~33 GiB of the 251 GiB available |
| Throughput | prefill **215–257 tok/s**; decode **26.3 tok/s** short, **18.75 tok/s** at ~40k depth |
| Round-1 crate task | **PASS** — byte-exact, reproduced clean |
| Splat task | **servable**, 2 of 3 clauses passed, grader verdict **FAIL** on one colour sub-test (S-DS-6) |
| Envelope task | **decoded** — the first open-weights run to decode a `werk` binary envelope |
| Adapted self-run | **FAIL** — grade B 0 / 2 |
| **New spec/fixture bugs** | **1**, and it is real: **S-DS-7** |
| Instrument defects found | **3** — S-DS-5, S-DS-6, S-DS-8 |
| Findings | **S-DS-1 … S-DS-8** |

## Per task

| task | package, model's own tokenizer | iters | first clean | wall | verdict |
|---|---:|---:|---:|---:|---|
| round-1 crate, `mini-v1.werk` | 39 351 | 4 | 2 | 2 991.2 s | **PASS** — `eee8b3cb…` + `1e634f03…`, graded and re-run clean |
| splat, `gsplat-v1.werk` *(attempt 1)* | 54 889 | 4 | 1 | 2 969.5 s | **discarded, harness-corrupted, ungraded** (S-DS-5) |
| splat, `gsplat-v1.werk` *(retry)* | 54 889 | **2** | **1** | **507.5 s** | **FAIL** by the grader — clauses 1 and 3 pass, count and position exact, colour sub-test fails (S-DS-6) |
| envelope, `mini-v1.werk` | 39 337 | 4 | 1 | 3 718.8 s | **decoded** — `pose_count: 2`, both pose entries correct |
| adapted self-run, `selfrun-v1.werk` | 28 833 | 4 | 1 | 2 813.5 s | **FAIL** — grade B 0 / 2, no binary |

## The three results that are not about the model

**1. The specification's travelling weight is affordable, and the invoice is in
VRAM.** The gap-completion round could not run the splat task on three of five
local models — *"not servable: a 65 775-token package on a 24 GB card"* — and
measured a 13.7× prefill collapse on the one 30B it probed. The **identical
package is 54 889 tokens here and serves with 70 GiB spare** on top of 144 GiB
of weights, with no collapse. The cell was blocked by a graphics card, not by
the format and not by capability. **That is a better sentence for the paper than
"it did not fit": the price of a file that carries its own specification is
payable, and it is about 200 GB if you also want a frontier reader.**

**2. A spec fix that a weak implementer ignored, a strong one reads and uses.**
The post-fix arm concluded *"making a fact machine-readable does not make a weak
implementer read it"* — the 8B took `files[0]` with `payload_file` in front of
it. Read off this round's programs rather than its reports: `werk-sig/1` built
with the six fields exactly as `MINI-SPECS` §12.1 specifies, **Ed25519
implemented from scratch**, `primary.sound` resolved through `payload_file` and
`role`, and — its own curve arithmetic having a bug — the verdict **`unverified`**
rather than `present-and-invalid`. **Zero false tampering alarms in four runs.**
The two findings are one sentence: *a spec fix removes an excuse, and the excuse
being gone only helps an implementer that was going to read it.*

**3. The round's three worst defects were instruments, again.** S-DS-5: the
inherited `extract_program()` ended a fenced block at the first ``` anywhere,
including one inside a Python string literal — so a program that writes a
`REPORT.md` quoting source was truncated mid-statement and handed back its own
apparent `SyntaxError`. Proven from the stored reply (old 18 441 chars, does not
parse; new 21 924 chars, parses), it destroyed both complete programs of the
splat attempt, which is discarded ungraded. S-DS-6: the splat grader tests a
storage representation rather than a value. S-DS-8: `poses/rest.wkrp` is
**byte-identical** to the worked example whose decode S-OW-3 inlines, so the
envelope task has carried its own answer key since the post-fix arm. **Three
consecutive rounds — S-OW-5, S-GF-1, now S-DS-5 — have found their largest
defect in the measuring apparatus rather than in `spec/`.**

## The one real bug in the tree — S-DS-7

The model reported an `input_hash` mismatch on `mini-v1.werk`'s `rest-poses`
node. **It is right.** Recomputed independently from the rule `MINI-SPECS` §11
states executably:

| fixture | nodes with `input_hash` | verifiable | mismatched |
|---|---:|---:|---|
| `fixtures/crate-v1.werk` | 25 | 25 | **0** |
| `fixtures/gsplat-v1.werk` | 3 | 3 | **0** |
| **`gauntlet/roundOW/mini-v1.werk`** | 5 | 2 | **1 — `rest-poses`** |

Six construction variants were tried and none reproduces the declared value; the
sibling node in the same fixture verifies. `build_mini_fixture.py` recomputes
`spec_sha256` and re-signs but never recomputes `input_hash`. **Consequence: for
as long as that fixture has existed, a reader that implemented `input_hash`
correctly was told an intact package was damaged** — S-OW-1's failure mode in a
different field, with the fixture at fault rather than the model. Filed for the
owner of `roundOW/` and `fixtures/`; the roundDS agent changed nothing there.

## What this round does not establish

**n = 1 model.** One frontier open-weights family, not a population. **Every run
ended on the wall cap or a truncated reply**: at 18.75 tok/s at depth a full
16 384-token reply costs ~875 s, so **7 of 14 iterations were `finish=length`**
and the 8-iteration protocol was never reachable — the iteration counts below
are not evidence the model ran out of ideas (S-DS-3). **The envelope row is
weakened by its own fixture** (S-DS-8): the decode is genuine, proven by values
absent from the package, but the header clause was echoable and the task needs a
non-example payload before it can be quoted as a clean spec-forcing pass. And
the splat row's verdict turns on an unresolved question about what "the colours
it contains" means (S-DS-6), which is Gregor's to rule on, not this agent's.
