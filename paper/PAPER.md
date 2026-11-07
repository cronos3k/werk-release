# Agent-Implementability as a Format-Quality Metric

**The werk hermetic self-describing artifact container, and an experiment that
measures whether a stranger can read it**

Technical Report, werk Stage 8 — version 0.1
Gregor Hubert Max Koch · <gregor.koch@gmail.com>
8 August 2026

> This is the prose master of `paper/werk-paper.tex`, which typesets to
> `paper/werk-paper.pdf` (14 pages). Every number in either document is traced to
> its recorded source in `paper/NUMBERS.md`.

---

## Abstract

Asset formats rot. They rot because the knowledge required to read a file lives
outside the file: in a companion directory, in an application's undocumented
encoder, in a wiki that has since vanished, in one engineer who has since retired.
The bytes survive; the ability to use them does not. We argue that the arrival of
language-model agents as first-class producers and consumers of files turns a
previously untestable design virtue into a *measurable property*: given a file and
nothing else — no web, no library, no prior familiarity — can a fresh agent write a
correct reader for it? We call this **agent-implementability**, and we make it a
format's acceptance gate rather than its marketing copy.

We present **werk**, a container doctrine built to be measured this way. A werk
file is hermetic (no external references), self-describing (it carries its own
narrative specification, JSON Schemas and byte-level layout grammars),
self-historied (multiple coexisting node versions, each with a mandatory work note)
and self-attributed (an append-only Ed25519 custody chain with an explicit
three-state doctrine and no enforcement mechanism of any kind).

The experiment is the paper's heart. In round 1, four fresh isolated agents in four
languages (Python, JavaScript, Rust, C) were handed one 13 MB package and the
instruction to open it, list it, verify it and extract from it. All four succeeded:
486 s, 519 s, 755 s and 806 s, median 637 s. **None of the four used the readers
bundled inside the file** to learn the format; the two that looked at one did so
only after their own reader already ran clean. Twelve distinct specification bugs
were surfaced. In round 2, on a second profile carrying a custom binary payload,
two agents parsed the binary envelope, stated the file's AI-generation recipe and
disclosure correctly, and **recomputed an embedded image descriptor bit-exactly
from the source pixels** using only the in-file layout grammar — one of them then
implementing Ed25519 from the embedded mini-specification and reporting
`signed-and-valid`, while the other declined the curve arithmetic and correctly
reported `signature-unverified`.

Around that experiment we report four independent consumers, each with a measured
gate: a Rust reference core (10/10), a game engine (3.7× faster cooked-tier load,
cross-validated by a reader that has never heard of it), a Blender add-on (16/16,
deterministic writer, 8.4e-08 rad rig round-trip), and an Unreal Engine plugin
(16/16, pixel-identical texture round-trip). We report an unattended enrichment
pipeline (19/19 with 78/78 input-hash recomputations) and a content-defined-chunking
store (1.45× dedup, 94.7 % boundary stability). And we report, at length, what none
of this establishes: n=1 per language per round, a single model family, a lost
transcript, a vision path that never once completed, and a generated image that
violates its own prompt's exclusion list — which an agent correctly read as evidence
that a recipe records instructions, not guarantees.

---

## 1. Introduction

### 1.1 The failure mode

A modern digital artifact is usually a promise about other files. A mesh promises
materials it does not carry. An engine asset promises fifty siblings in a sidecar
directory. A document promises fonts. A video promises a codec. And every one of
them promises a *program*: some specific application, at some specific version, on
some specific machine, without which the bytes are noise.

This is not an aesthetic complaint. It is the mechanism by which formats die. The
applications rot, the documentation vanishes, the one engineer who knew the quirks
retires, and the bytes remain, mute. The failure is not that the data was lost —
the data is right there — but that the *knowledge required to interpret* the data
was never stored alongside it.

Existing interchange formats attack part of this and share one shape of gap,
examined in §11: the file is complete about its *bytes* and incomplete about its
*meaning*.

### 1.2 Why this is newly measurable

The usual defence of a well-documented format is a claim of the form "a competent
engineer could implement this from the specification." That claim has never been
cheap to test. Hiring four engineers who have never seen your format, isolating
them from the internet, and paying for a week of their time in order to find out
whether your section 4.4 has an arithmetic error is not a practice any format has
ever been able to afford, which is why no format has ever done it.

Language-model agents change the economics. An agent can be instantiated fresh,
denied network access, pointed at exactly one file, and asked to produce a working
program — repeatedly, in several languages, for the cost of a few hours of compute.
The question "can an isolated intelligence write a correct reader for this file,
from the file alone?" stops being a rhetorical virtue and becomes a *measurement
with a number attached*.

We claim three things:

1. **Agent-implementability is a well-defined, repeatable format-quality metric.**
   It has a protocol, a success criterion, a failure taxonomy, and a falsifier.
2. **It is a metric a format can be designed *against*.** We present werk, a
   container doctrine of twelve laws whose acceptance gates are stated in terms of
   it, and whose specification is required to travel inside every file it describes.
3. **The failures the metric produces are its product.** Every agent stumble in
   this work became a specification fix, tracked in an append-only findings ledger.
   Thirty-eight reported stumbles deduplicated to twelve distinct specification bugs
   in round 1 alone; the single most expensive one — three agents, three languages,
   no contact between them, the same longest detour — was a two-byte ambiguity in a
   hashing rule that no amount of internal review had caught in a year of writing.

### 1.3 What is new here, and what is not

Hermetic packaging is not new (USDZ, OCI images, self-extracting archives).
Self-describing serialisation is not new (JSON, ASN.1, FlatBuffers with reflection).
Cryptographic provenance for media is not new (C2PA). Content addressing is not new.
What is new is (a) the combination held to a constitutional rule — "a werk answers
every question it raises" — and, more importantly, (b) the proposition that *whether
a format actually achieves this is an empirical question, answerable by experiment,
and that the experiment should be part of conformance*. This is a technical report
on a system built and measured over a short, intense development period, not a
controlled study; §10 states the limits at greater length than convention would,
because a paper arguing for honesty about what is known cannot practise otherwise.

---

## 2. Design: the twelve laws

werk is deliberately not a file format. It is a doctrine for building file formats:
twelve laws that govern every concrete *profile*. Profile 1 is a 3D entity; profile
2 is an image. The laws mention no triangles, and both profiles instantiate them
unchanged.

**Table 1 — the twelve laws** (`MANIFESTO.md` v0.1). Law 10 is the subject of this
paper.

| # | Law | In one sentence |
|---|---|---|
| 1 | Hermeticity | A werk answers every question it raises; no external references, ever. |
| 2 | Self-description | The knowledge to read the file travels inside it: narrative spec, JSON Schemas, byte-level layout grammars. |
| 3 | Islands | Every node is self-contained; edges are `requires` or `enhances`; a node that cannot be parsed costs one feature, never the file. |
| 4 | Identity over indices | Stable ids survive re-export; indices rot. |
| 5 | Provenance & epistemic status | Every derived node records who made it, from what (input hashes), and how sure: `authored` / `measured` / `inferred`. |
| 6 | Versions live in the file | Multiple coexisting versions, append-only, one advisory `active` pointer, mandatory work note per version. |
| 7 | The signature chain | Append-only Ed25519 custody over the manifest hash; three states, surfaced, never enforced. |
| 8 | Conventions declared numerically | Units, handedness, axes, colour spaces, quaternion order, alignment — machine-checkable values, never prose. |
| 9 | Two masters | Every payload earns its bytes twice (runtime and tooling); preview-tier bytes physically first in the container. |
| 10 | Agent-first, measured | Implementable from the payload alone, and this is tested, not asserted. |
| 11 | Boring encodings | Flat POD arrays, explicit strides, little-endian, magic + version + header length + payload. |
| 12 | Extension without breakage | `core.*` is the constitution, `x.*` the frontier; readers skip what they do not know, for free. |

### 2.1 Container and self-description

A werk package is a directory tree; the interchange form is that tree zipped,
extension `.werk`. Both forms are the format. Compression defaults to zip *store*
mode, for one reason that is entirely about law 10: a zero-dependency zip reader is
roughly a hundred lines in any language *without* an inflate implementation, and
several hundred more with one. The payloads that dominate a package's size (PNG,
WAV, GLB) are already internally compressed, so deflating the container buys
single-digit percentages on the bytes that matter. Cross-file redundancy is the
companion store's job (§9.7), not the format's.

Self-description is three-layered. `spec/SPEC.md` is the narrative specification of
the profile. `spec/schemas/*.json` are JSON Schemas (draft 2020-12) for every
structured node, stored as ordinary data. And `spec/layouts/*.layout.txt` are
plain-text layout grammars for every custom binary: endianness, alignment, offsets,
types, counts, field semantics, precise enough to write a parser from scratch. Where
a boring ubiquitous encoding exists (PNG, WAV, GLB, JSON, UTF-8, CRC-32, zlib,
SHA-256, Ed25519), werk uses it *and still embeds a byte-level mini-specification
with test vectors*, so that law 2's guarantee holds literally rather than
approximately. That decision is the one the experiment vindicated hardest: in round
1 no agent needed anything external for the zip container, CRC-32, SHA-256, WAV,
GLB, PNG, JSON, UTF-8, the manifest structure, the node graph, the edge semantics,
the version-resolution rules, the three signature states, the refusal scopes, or the
exit statuses.

### 2.2 Islands and graceful degradation

Every node is an island: self-contained, meaningful alone, never reaching into
another node's bytes. Cross-references go through the manifest by identity. Edges
are typed `requires` or `enhances`, and almost everything is `enhances`. Corruption
is quarantined per node — hash mismatch marks the node dead, logs a report entry,
and continues. Unknown-because-newer and unreadable-because-broken degrade through
the same code path, which is what makes law 12 free rather than expensive.

The operational meaning of "refuse, do not guess" was itself a specification bug,
found by two independently written bootstrap readers and ruled during this work.
Refusal now has three *scopes*, and a reader picks the smallest that contains the
problem: **value** (one field), **node** (bytes, envelope, schema, or a `requires`
edge failed), and **container** (not a zip, no end-of-central-directory record,
zip64 in a zip32-only reader, or an unparseable manifest — the only scope permitted
to come back empty-handed). Command-line exit status is pinned to the same taxonomy:
0 opened with no error entry, 1 opened with at least one error entry, 2
container-scoped refusal.

### 2.3 Epistemic provenance

Law 5 is the one that most directly attacks the "silently wrong answer" class of
bug. Every derived node records its producer (tool, model, version), its ordered
input files, its input parameters, and a hash over both — and carries an epistemic
stamp of `authored`, `measured` or `inferred`. An inferred value is useful *because*
it is labelled inferred; laundering it into fact is the failure.

Crucially this is machine-enforced rather than hoped for. The manifest schema
carries an `if`/`then`: a stamp of `measured` or `inferred` *requires* `input_hash`
and an *ordered* `input_files` array, because an unordered input set cannot produce
a reproducible hash. Two independent adapter authors (Blender, Unreal)
independently attempted to stamp an authored artifact as `measured` and were
rejected by the schema rather than by a reviewer — in both cases correctly, because
a live scene is not a file in the package and there is nothing to recompute against.

The payoff is that stale derived data is detectable from the file alone. In the
enrichment pipeline (§9.6), all 78 stamped-derived node versions across three
packages had their `input_hash` recomputed *from the packages' own bytes* by the
acceptance gate: 78/78 matched.

### 2.4 Versions in the file, and the signature chain

A node may hold multiple coexisting versions, append-only, with one `active` pointer
that is the author's recommendation and not a command. Every version carries a
mandatory work note — one sentence of why it exists — as payload, not tooling
metadata. Old versions are never rewritten; compaction is an explicit, signed,
logged choice.

Authorship is an append-only Ed25519 chain. Each entry signs the manifest hash, and
the manifest hashes every file, so a signature covers the entire package state
transitively. Conformant tools must surface three states: **signed-and-valid**;
**absent** (anonymous, by choice or by stripping — nothing breaks, but the absence
is visible); and **present-and-invalid** (tampering under an existing signature: the
state that catches bad actors). A fourth fixed token, `unverified`, exists for a
reader that did not check, so that declared narrowness is available and silent
narrowness is a bug.

The distinction that four independently written readers got right without being
told, and that we had flagged as the easiest thing to get backwards, is this:
**corrupting a payload does not invalidate the signature** (the chain signs the
manifest; the manifest hashes the files; detection belongs to the per-file hash),
while **corrupting the manifest does**, under a different report code.

### 2.5 Disclosure without enforcement

Profile 2 introduced two base-doctrine node types that every profile inherits:
`core.recipe` (the full reproduction record — models with weight hashes where they
exist, prompts as files rather than strings, seeds, samplers, LoRAs by hash, tool
versions, every input medium by hash, and a declared reproducibility grade) and
`core.disclosure` (machine-readable facts about synthetic content).

`core.disclosure` carries *no enforcement of any kind*. The format ships facts; the
viewer applies its own jurisdiction; a viewer that ignores every disclosure field is
still conformant. The schema's `jurisdiction_note` field exists precisely so that
authors stop writing that sentence into free text where no reader can find it, and
its own description forbids a tool from reporting compliance on the strength of it.
§11 contrasts this with C2PA, whose provenance model is coupled to an enforcement
and trust-list apparatus.

One design decision inside `core.recipe` is worth naming because it is the single
hermeticity exception in the whole doctrine. Input *media* MUST be embedded in the
package and listed in the recipe node's own `files[]`. Model *weights* may be named
by hash without being carried, and a recipe that does not carry them must say so
rather than stay silent. A 12 GB checkpoint inside every generated image is not a
format; and the distinction is not arbitrary, because input media are small and they
are the thing the model actually saw.

---

## 3. Method: the agent gauntlet

### 3.1 Protocol

A conformance fixture is copied to a neutral directory outside every project
repository. A fresh agent is instantiated with its own workspace and given one task
sentence, verbatim:

> Here is a file: `...\crate-v1.werk`. Write a program in ⟨L⟩ that opens it, lists
> its contents with their meanings, verifies integrity, and extracts the primary
> mesh and one sound to disk. You may read anything inside the file. You may not
> search the web or read anything outside the file.

Isolation is enforced as a hard constraint: the only permitted input is that file
and its contents; the project repositories and any `spec`/`werk`/`loaders` directory
elsewhere on the machine are off limits; web search and web fetch are forbidden; and
*recognising the format from prior knowledge does not license using it* — everything
must be derived from the file.

Success is not self-reported. An agent succeeds if its program opens the container,
lists the node graph with meanings, verifies every declared hash, extracts the named
payloads, and the extracted bytes hash to the values the manifest declares. In round
2 three further clauses were added: parse the custom binary payload and print what
is inside it; state in plain language how the image was generated; and state what
the file declares about that generation.

### 3.2 What is recorded

Five things: success or failure; wall-clock time to a working reader; whether the
agent used the readers bundled *inside* the file; whether the agent wanted anything
from outside the file; and every stumble, deduplicated into distinct specification
bugs.

The third is the load-bearing one. Every werk package embeds `core.loader` nodes —
single-file, zero-dependency bootstrap readers in Python, Rust and C — as payload.
If agents learned the format by reading those, the experiment would be measuring
"can an agent port a program," a different and much easier question. The metric
means what we claim only if the *specification* is the path of least resistance.

### 3.3 Deviations, recorded rather than hidden

**(1) The task sentence was not literally the only text.** Each agent also received
the isolation rules above, a workspace path, a timing instruction, an instruction to
report stumbles honestly, and one environment note (this host's MinGW gcc fails
silently under one available shell — a sandbox artifact that would otherwise have
been recorded as a format failure). The task sentence itself is verbatim.

**(2) The reporting instruction is not neutral.** Agents were told that a stumble is
worth more than a clean run and that under-reporting to look competent would corrupt
the experiment. This inflates the stumble count relative to a silent run — which is
the intent, since the stumbles are the product — and it means the count is not
comparable to one gathered without that instruction.

**(3) The damaged fixture was never handed out in round 1.** The brief called for
re-running two agents against a deliberately corrupted copy. In the event all four
synthesised their own damage without being asked, so there was nothing left to
re-run. That is a stronger result than the brief asked for and a weaker one than it
specified: nobody was tested against damage *they did not design*.

C++ was in the brief's language list and was not run in round 1. It is covered as a
*consumer* by the three-face test of the reference core (§9.1) and remains untested
as an *implementer*.

---

## 4. Results, round 1: four languages

### 4.1 Setup

The artifact under test was `fixtures/crate-v1.werk` as it stood on 2026-08-08:
sha256 `93d16579...5a384`, 13 262 619 bytes, 157 zip entries, 36 nodes, 155 declared
files. It is a wooden crate with a complete sound world, built from a real production
run of a separate 3D-to-audio pipeline, not a mock-up: 272 vertices and 408 triangles
of source geometry, a minimal bounding sphere of r = 0.8893 m computed by Welzl's
algorithm and checked against all 272 points, 20 audio effects (17 interaction plus 3
ambience) across 73 WAV files, six rendered orbit views and ten segmentation crops
carried as `x.*` extension nodes, and one signature chain entry. Its preview prefix —
manifest, signature, licence, readme, all three bootstrap loaders, the whole of
`spec/`, the semantics node and one audible one-shot — was 723 944 bytes, 5.46 % of
the archive.

The fixture has since been rebuilt several times as specification fixes landed; §8
re-measures the shipped fixtures at writing time and §10 records the bookkeeping
problem that created.

### 4.2 Headline

**Table 2 — agent gauntlet, round 1.**

| Measurement | Value |
|---|---|
| Success rate | **4 / 4** |
| Languages | Python, JavaScript, Rust, C |
| Median time to a working reader | **637 s** |
| Mean | 642 s |
| Range | 486–806 s |
| Used bundled loaders to learn the format | **0 / 4** |
| Read a bundled loader at all | 2 / 4, both after their own reader ran clean |
| Extracted mesh + sound, hashes matching | 4 / 4 |
| Wanted something from outside the file | 3 / 4, on the same two gaps |
| Distinct spec bugs surfaced | **12** |
| Total stumbles reported | 38 |

Every agent opened the container, listed the graph with meanings, verified every
declared hash, extracted `geometry/game.glb` and one WAV, and matched the manifest's
declared sha256 on both extracted files.

**The single most useful number in that table is the 0/4.** The format's claim is
that the specification travels with the file and that the bundled readers are a
convenience rather than the mechanism. Nobody used them to learn the format. Two
agents checked one at the very end and both found the loader did *less* than what
they had already built: neither implements the `input_hash` staleness check, and none
implements Ed25519 — the two things that cost the most time. Had the loaders been the
path of least resistance, this experiment would have measured program porting.

The three agents that wanted something external all wanted the *same two* things:
Ed25519 internals and SHA-512. Both are now in the file (§6).

### 4.3 Per agent

**Table 3 — round 1, per agent.** "Stumbles" is the raw count each agent reported;
the 38 deduplicate to the 12 distinct bugs of Table 6.

| Language | Time | Stumbles | What it did |
|---|---|---|---|
| Python | 486 s | 10 | Fastest. Hand-rolled the store-mode zip reader rather than using `zipfile`; implemented SHA-256 from the embedded structural facts; implemented Ed25519 verification from scratch in ~60 lines of extended-coordinate Edwards arithmetic, then gated the whole program on the RFC 8032 vector the file supplies *and* checked that a wrong message is rejected, so a constant-true `verify` could not pass its own gate. Recomputed `preview_prefix_bytes` to the byte (724 832 = 724 832), checked 25/25 `input_hash` values, implemented 12 distinct report codes. Opened a bundled loader once, at the very end. |
| JavaScript | 519 s | 8 | The control for "what if there is no loader in your language at all": there is no `werk_read.js`, and it made no difference. Node built-ins only. Wrote a 40-line zip lister from prior knowledge *before* reading any specification, then retro-confirmed it against the embedded mini-spec and discovered the zip64 detection rule it had not implemented. Used Node's `crypto` for Ed25519 and had to supply the 12-byte SubjectPublicKeyInfo DER prefix from memory — then proved the guess with the file's own test vector. |
| Rust | 755 s | 9 | `rustc -O`, no cargo, no crates. Derived every SHA-2 round constant *at run time* from the primes rather than typing any in from memory; computed sqrt(-1) and the Ed25519 base point from their definitions. Never read, ran or ported `werk_read.rs` — a sibling implementation in its own language, sitting inside the very file it was reading. Declared its own narrowness in the format's own vocabulary, naming what it did not implement (schema validation, deflate, zip64 reading) rather than claiming it. |
| C | 806 s | 11 | Slowest and most thorough. Single-file C99, standard library only, 56 KB of source. Refused to memorise any constant: SHA-256/SHA-512 initialisation vectors and round constants derived at run time from the fractional parts of square and cube roots of the primes; curve constant d, sqrt(-1) and the base point computed from their definitions. Did not read `werk_read.c` — the C loader shipping inside the file it was reading — before writing its own. The only agent to demonstrate all three signature states by construction, including **present-and-invalid** on a manifest it tampered with itself. |

Two patterns are worth naming.

First, **the agents were more paranoid than the specification asked them to be**, and
in a specific direction: three of four refused to trust remembered constants and
derived them instead, and all four gated their cryptographic stack on the test
vectors the file supplies. This is a property of the file, not of the agents — a
package that ships an RFC 8032 vector makes "prove your guess" the cheap move, and
the JavaScript agent's own note ("the file's test vector rescued the guess. Still: a
gap.") is the mechanism working exactly as intended, and also the report of a real
specification bug.

Second, **the slowest agent was the most thorough one**, and the fastest was not the
least. Wall-clock time here spans reading, writing, compiling, debugging and
report-writing for a whole agent session. It is not time-to-first-parse, and it is
not comparable to a human baseline that was never measured.

### 4.4 Damage, unprompted

Nobody was asked to test degradation. All four did.

**Table 4 — damage the agents built themselves.**

| Agent | Damage it built | Result |
|---|---|---|
| Python | one flipped byte in a WAV; separately an injected unknown node type; separately the signature file removed | exit 1, state *present-and-invalid* (the injection re-serialised the manifest), 34/36 nodes still loaded, mesh and sound extracted; the stripped copy → exit 0, *absent* |
| Rust | one flipped byte in a WAV | exit 1, `zip-crc-mismatch` + `hash-mismatch` on that path, **35 live / 1 dead**, signature still `signed-and-valid` |
| C (1) | one flipped byte in `MINI-SPECS.md`, i.e. damage to the *specification* it had just used | exit 1, 1 node dead, 35 alive, signature still `signed-and-valid` |
| C (2) | one flipped byte in `MANIFEST.json` | exit 1, `signature-invalid`, **0 nodes dead, 0 files failed**, state `present-and-invalid` |
| JS | corruption run over two output sets | degraded, reported, continued |

This is, we think, the strongest single piece of evidence in round 1, because it was
not asked for. Four independently written readers each got right the distinction we
had flagged as easiest to invert — payload corruption leaves the signature valid,
manifest corruption does not — and three of the four produced the three-state
doctrine as three *distinct* outputs rather than two, which is the thing the
specification warns tools get wrong. Nobody had to be told.

---

## 5. Results, round 2: the custom binary

Round 1's own verdict was that its fixture carried no custom binary, so the entire
binary-envelope apparatus went untested: two agents wrote envelope parsers from the
specification and never got to run one. Round 2 exists to close exactly that gap, on
a second profile, with a longer task list.

### 5.1 Setup

The artifact was `fixtures/ista-varun-v1.werk`, profile `image/1`, 15 nodes — a real
AI-generated character plate with its real recipe. It was chosen after auditing three
candidates, and the two rejections are the useful part: a video first frame whose
prompt sidecar records the *pre-wrap* input rather than the string sent (the recipe
would have been confident and wrong), and reference sheets that are deterministic
image montages rather than model output at all (a fixture for AI-generation recipes
must not be built from something that was not generated).

The two agents saw *different builds*, recorded rather than smoothed over: the Python
agent got sha256 `a59a5083...`, 9 969 937 bytes, 63 entries; the Rust agent got
`2fdfde30...`, 9 973 037 bytes, 63 entries, rebuilt after the Python agent's own
findings were fixed. Nothing about the graph, the payloads, the recipe or the
disclosure changed between them. The Rust agent therefore tested the *corrected*
file: a weaker test of those three findings and a fair test of everything else.

### 5.2 Headline

**Table 5 — agent gauntlet, round 2.**

| Measurement | Value |
|---|---|
| Success rate | **2 / 2** |
| Parsed the `WKEM` envelope payload | **2 / 2** |
| Checked *both* branches of the section consistency rule | **2 / 2** |
| Stated the recipe correctly, with grade and caveats | **2 / 2** |
| Stated the disclosure correctly, incl. that it binds nobody | **2 / 2** |
| Used bundled loaders to learn the format | **0 / 1 recorded** |
| Wanted anything from outside the file | **0 / 2** |
| New spec bugs surfaced | **3** |

### 5.3 The result worth putting first

A fresh agent, working only from `spec/layouts/embedding.layout.txt` §4,
reimplemented the image descriptor `werk.descriptor.labhog/1` and **recomputed it
from the source pixels bit-exactly**:

```
max |recomputed - stored| : vector  0.000e+00
max |recomputed - stored| : palette 0.000e+00
      (declared tolerance 1.0e-06)
```

on both the 72-component vector and the 8-swatch palette. The second agent, in a
different language, reproduced the descriptor as well and cross-checked its eight
palette swatches against the duplicate copy of the same palette in the package's
JSON semantics node, agreeing to 1e-6 including the re-encoded sRGB hex values.

This is what law 5's `epistemic: "measured"` is *for*. The claim a package makes when
it stamps a node `measured` is that the value is a measurement of bytes that are also
in the package, and that the procedure is defined completely enough for a stranger to
redo. A stranger redid it, twice, in two languages, from a prose grammar in a text
file, and hit every bit. The package's own builder had previously measured a worst
drift of 1.381e-08 against the same declared 1e-6; the agents did better than the
builder, which is the correct direction for that particular surprise.

### 5.4 The second result: two honest verdicts

The two agents took *opposite and both-correct* routes through the signature section.
The Python agent implemented Ed25519 from the package's embedded mini-specification
§12 and reported `signed-and-valid`. The Rust agent deliberately did not implement
the curve arithmetic and reported `signature-unverified` — the fourth fixed token the
specification defines for exactly this case — while still rebuilding the signed
message bytes, checking the chain linkage, and checking the anchor against the
manifest actually present.

Two readers, two honest verdicts, neither one guessing. In round 1, three of four
agents named Ed25519 internals as the thing they wanted from outside the file. Round
2 has one agent building it from the inside and one declining it by the book, and the
difference between those two rounds is a specification fix (S-12).

### 5.5 Verification detail

**Table 6 — round 2, checks the agents ran that we did not ask for.**

| Check | Result |
|---|---|
| Python agent's own verdict line | 23 hard checks, 0 failed |
| Rust agent's own verdict line | 16 passed, 0 failed, 1 note (the deliberate `unverified`) |
| All declared `input_hash` values recompute | 7/7 (both agents) |
| Ed25519 vs RFC 8032 vector 1 | PASS (Python) |
| `preview_prefix_bytes` recomputed from local headers | declared 998 658, computed 998 658, over 58 entries (Python); 1 001 758 on the rebuilt package (Rust) |
| Every preview-tier entry physically precedes that offset | PASS |
| Physical order vs `entry_order` under the two-pass rule | 62 of 63 matched; the one miss was a real bug (S-28) |
| `payload_origin` recomputed as 16·ceil((12+h)/16) | 704 computed = 704 declared |
| payload_origin + payload_size = file length | 1120 = 1120 |
| Both branches of the section consistency rule | explicitly checked, both agents |
| Vector L2 norm vs declared `normalized: true` | 1.000000006 |
| Palette: `WKEM` vs JSON duplicate | all 8 agree to 1e-6, hex included |

Two entries deserve comment. The palette cross-check is law 9 — "every payload serves
at least two masters" — being *audited by a stranger*: the same eight colours are
stated twice, once in a binary payload and once in a JSON node, and the only way to
know that redundancy is not silently diverging is for someone with no stake to
compare them. And the Python agent independently noticed that the palette weights sum
to 0.995117 rather than 1, correctly diagnosing it as a top-N palette rather than a
cover, which is a specification bug (S-24) found from the outside.

### 5.6 Comprehension, not merely parsing

Both agents stated the recipe and the disclosure correctly, including the parts that
limit what may be claimed. The Python agent reconstructed the v1/v2 prompt split
unprompted, printed the byte-level difference (1 716 → 1 816 characters), and
repeated the file's own caveat that the v2 prompt is "RECONSTRUCTED, not recorded".
On disclosure it produced the doctrine without being told it:

> "the format ships facts, the viewer applies jurisdiction, and the format contains
> no enforcement of any kind. Nothing here obliges any viewer to do anything; a viewer
> that ignores every field above is still conformant. What this program must not do
> is paraphrase the claim into a different one."

It also drew, unprompted, the two distinctions the specification cares most about:
that the chain verifies but its key is a published development key with no external
root of trust, so the declared author "is an assertion by a party and must not be
presented as verified authorship"; and that the package's C2PA export node "is a
DECLARED BUT UNIMPLEMENTED mapping and proves nothing about C2PA interoperability".

The Rust agent produced the observation we consider the most valuable single sentence
either round generated, and it is not about parsing at all. The recipe's prompt
carries an exclusion list — among other things "no militaria" — and the delivered
image contains uniformed figures with plumed helmets and epaulettes. The agent's
reading:

> "That is the DESCRIPTIVE grade doing exactly what the recipe warns it does — the
> recipe records the instructions, not a guarantee about the pixels."

A reader with no context inferred, from a declared reproducibility grade alone, the
single most important thing a recipe does *not* promise. We report this as a positive
result about `core.recipe` and as a permanent caveat about all recipe data
everywhere: a recorded prompt is evidence of intent, never of outcome.

---

## 6. Spec bugs as the metric working

A success rate is the least interesting output of this experiment. The interesting
output is the failure list, because in this design every failure has exactly one
legitimate response: a specification fix. The house rule is that a failed gate is a
spec bug and not an excuse.

**Table 7 — round 1's twelve distinct specification bugs.** "Seen by" is what makes
the priority ordering an observation rather than an opinion.

| # | Seen by | One line | Status |
|---|---|---|---|
| S-10 | Py, JS, Rust | `input_hash` with an absent `input_params`: append `{}` or nothing? | fixed |
| S-11 | Rust, C | SHA-512 undocumented, and Ed25519 needs it | fixed |
| S-12 | all four | "use a library" is unfollowable in a hermetic reader | fixed |
| S-13 | Py, JS, Rust | "the primary mesh" is nowhere a machine-readable fact | fixed |
| S-14 | Py | `entry_order` mixes exact paths and prefixes, unmarked | filed |
| S-15 | Py | `preview_prefix_bytes` does not say what it measures *to* | filed |
| S-16 | Py, Rust | the spec inside the fixture denied the fixture existed | fixed |
| S-17 | — | which nodes an unsupported convention kills is not tabulated | filed |
| S-18 | Py | "exactly one `files[]`" vs. a multi-version node | filed |
| S-19 | Py | loader capability and state words drift between manifest, loaders and spec | fixed |
| S-20 | Py | one package, two vocabularies for the same value | fixed |
| S-21 | Py, Rust | minors, incl. the entire envelope apparatus untested | partly |

### 6.1 S-10: the finding of the run

Three agents, three languages, no contact with each other, and the *same* longest
detour. All three read the sentence "followed by the UTF-8 bytes of the canonical
JSON of `input_params`" the natural way — no params, append nothing — and all three
got **0 of 25** hashes right.

The Python agent brute-forced ten candidate conventions against three known targets
before finding it. The Rust agent found it by discovering `h.update(b"{}")` inside a
generator script that happened to travel in the package, and noted that the generator
and the fixture disagreed about whether the field was even present. The JavaScript
agent brute-forced it too.

Two things make this the most valuable result of round 1. First, **the bundled
loaders could not have saved anyone**: none of the three implements `input_hash` at
all, and two agents checked and said so. Second, **it is exactly the failure mode the
format claims to prevent**. The package's `spec/README.md` lists ten questions the
folder must answer alone; question six is "*Is this derived data stale? Recompute*
`input_hash` *from* `input_files` *and compare*." It was the one of the ten the folder
could not actually answer.

The ruling: an absent `input_params` *is* the empty object, its canonical JSON is the
two bytes `{}`, and they are appended exactly as if the key were written out. Nothing
is ever appended as nothing. The rule is now stated with executable pseudocode and a
worked example checkable by hand against the package itself, writers are told to emit
`"input_params": {}` explicitly, and both werk writers do. The fix is verified: a
later independent implementation (the game-engine reader of §9.2) implemented the
rule straight from the pseudocode with no detour at all.

### 6.2 S-12: "use a library" is unfollowable

All four agents hit this one. The embedded mini-specification said, of Ed25519, "Do
not implement this from a description; use a library" — while the format's own thesis
is that an isolated intelligence has no library to reach for, and the specification
separately forbids the embedded Rust and C loaders from having one. Three agents
implemented it anyway; the fourth supplied a DER prefix from memory and proved the
guess against the file's own vector.

The ruling keeps the advice — it is correct, and a subtly wrong signature check is
worse than none — but makes the file sufficient. The mini-spec now carries p, d, L,
sqrt(-1), the base point definition, point encoding and decompression, the extended
twisted-Edwards group law, the canonical-S check, both verification equations, the
SubjectPublicKeyInfo DER prefix, and a statement that *signing* is deliberately out of
scope because key handling belongs in an audited library. Round 2 measures that fix:
one agent built verification from the file and one declined it correctly, and neither
wanted anything from outside.

### 6.3 The ledger, and a process failure in it

Findings are tracked in an append-only ledger: eight from the first two independently
written bootstrap readers (S-1…S-8, all resolved), the golden-sample finding S-9,
round 1's twelve, five from the retarget work, eight from the enrichment pipeline, six
from the Unreal adapter, two from the store, one from the Blender adapter, four from
profile 2 and round 2, and one still open.

The ledger itself produced a finding about ledgers. Three development stages ran
concurrently against one working tree, and each allocated "the next free finding
number" from the tree as it stood when it started. All three picked S-22 and two
picked S-23. The reconciliation table is kept rather than quietly renumbered, because
the old labels are in commit messages that cannot be edited, and the rule applied is
that the earliest commit keeps the number. The process lesson is worth more than the
table: *a monotonically increasing counter kept in one prose document is not a
concurrency-safe allocator*, and three agents proved it in one afternoon. Later stages
label findings by stage and ordinal (S10-4) so that collision is impossible by
construction.

---

## 7. Ecosystem validation

Agent-implementability is a necessary condition, not a sufficient one. A format that
a stranger can read and that nothing real consumes has proven only half of something.

**Table 8 — measured acceptance gates.** Every one is a committed, re-runnable
harness; none is a self-report.

| Gate (harness) | Result |
|---|---|
| Reference core, three faces (`run_gate.py`) | 10 PASS, 0 FAIL, 0 SKIP |
| Golden fixture (`run_gate_a.py`) | 7 PASS, 0 FAIL |
| Enrichment pipeline (`run_gate_3b.py`) | 19 PASS, 0 FAIL, 0 WARN |
| Retarget, three foreign rigs (`run_gate_6.py`) | 33 PASS, 0 FAIL (29.2 s) |
| Profile 2 fixture (`run_gate_9.py`) | 14 PASS, 0 FAIL |
| Blender adapter (`test_gate.py`) | 16 PASS, 0 FAIL (3.5 s) |
| Unreal round trip (`roundtrip_gate.py`) | 16 PASS, 0 FAIL |
| Unreal engine-free core (`build_gate.bat`) | 10 PASS, 0 FAIL (0.31 s) |
| Unreal live editor control (`proof_session.py`) | 6 PASS, 0 FAIL |
| Store, whole-blob (`measure_gate.py`) | 43 tests green |
| Store, chunked (`measure_gate_cdc.py`) | 59 tests green |

### 7.1 The reference core, and three faces of one DLL

`werk-core` is a Rust `cdylib` behind a C ABI. C++ consumes header plus DLL; Python
binds by `ctypes` over the same DLL; there are no package-manager dependencies
anywhere in the consumption path. On conformance fixture #1 (413 741 bytes, 28 zip
entries, 15 nodes, 26 declared files), all three faces report the same 15 nodes, the
same 14-alive/1-skipped split, the same `signed-and-valid` verdict, and the same
manifest sha256, over one 879 616-byte `werk.dll`. Round-trip byte-identity holds
three ways — from the zip, from the committed directory form, and from a freshly
materialised directory — because the physical entry order is a pure function of the
manifest and the zip writer uses a fixed DOS timestamp.

The damage gauntlet asserts *exact* reports and *exact* survivors rather than "did not
crash". Four scenarios: a flipped texture byte plus a deleted semantics file (two
nodes dead, eleven alive; a material that merely `enhances` the dead texture survives
and reports it); a corrupt mesh (two nodes die through `requires` edges while a node
that only `enhances` it stays alive); a schema-invalid payload that was *re-hashed*,
so only the schema can catch it (zero hash mismatches, `payload-schema-invalid`); and
a corrupted binary envelope header (`envelope-invalid`, one node dead).

Separately, three single-file zero-dependency bootstrap readers ship *inside* every
package as `core.loader` nodes. On fixture #1 all three verify 26/26 files across 15
nodes standalone, sharing no code with each other or with the core: `werk_read.py`
under stdlib only, `werk_read.rs` under bare `rustc` with `-D warnings`, and
`werk_read.c` under both `gcc -std=c99 -Wall -Wextra` and MSVC `/W3`, with
byte-identical output.

One measurement in this stage proves that the code and the specification agree rather
than merely coexist: the fixture's binary rest-pose payload, produced by the Rust
envelope writer, is **byte-identical** to the example payload the specification's own
generator script produces — 560 bytes, same sha256, and the same value the
specification's annotated hex dump records.

### 7.2 A game engine: zero-cook load

The CUB engine's importer implements the container *natively* rather than binding the
reference core's C ABI — store-mode zip from the embedded mini-spec §5, and the
envelope header's MessagePack subset from the embedded envelope grammar §4 — which
makes it a second independent implementation, and the first consumer to exercise the
binary-envelope apparatus round 1 recorded as untested. It reports the signature chain
as `unverified` and never as `signed-and-valid`, because it carries no Ed25519:
declared narrowness, not silent narrowness.

Loading the golden fixture with no cook step, no sidecar and no import dialog: exit 0,
36 nodes, 34 live, **0 dead**, 2 skipped as unknown types, 139 files verified by size
and sha256 over 12 865 205 bytes, 272 verts / 408 tris, `welzl-exact` bounds at
r = 0.889269 m, 20 audio nodes with takes and roles resolved.

Two independently written readers then agreed on exactly what dies in the damaged
copy, down to the node id and the file within it: 37 nodes, 33 live, 1 dead, one
`hash-mismatch` on the same audio node, three unknown-type skips.

**Table 9 — load time, decode only, both paths starting from a byte slice already in
RAM. Median of 50 iterations.**

| Mesh | GLB | `x.cub` | Speedup |
|---|---|---|---|
| crate, 272 v / 408 t | 0.043 ms | 0.022 ms | 1.9× |
| grid, 502 681 v / 1 002 528 t, 1 material | 88.95 ms | 24.00 ms | **3.7×** |
| same grid, 3 materials | 145.51 ms | 21.69 ms | 6.7× |

**3.7× is the honest headline**, and the three-material row must not be quoted instead
of it: a per-material GLB split duplicates vertices at the seams, so that path is
processing 1 005 360 vertices against the cooked tier's 502 681, and its slower time is
partly a different job rather than only a slower one. The absolute number matters as
much as the ratio — 65 ms saved per million-triangle mesh is the difference between a
level streaming in and a level hitching.

The result that vindicates law 12 is not a benchmark. The engine's exported package,
carrying an engine-specific cooked tier as an `x.cub.v1` node, was handed to
`werk_read.py` — the embedded zero-dependency bootstrap reader, which has never heard
of this engine — and it reported **9 nodes: 8 live, 0 dead, 1 skipped for unknown
type**, the skipped one being the cooked tier. Its manifest also validates against the
schema the package carries with 0 errors.

Two engine bugs were found by the werk path on the way past, and neither was found by
reading the engine. Its loaders defaulted an absent bounds to a zero-radius sphere at
the origin, which a culler will happily cull; and its cooking step stored the sphere
*circumscribing* the bounding box rather than the minimal one. Both surfaced because a
schema field would not let itself go unanswered — an argument for the format that no
benchmark makes.

### 7.3 Blender: import, export, determinism

The Blender adapter is a 4.x add-on, installable as a zip and callable headless, with
zero external dependencies: stdlib plus `bpy`, with werk parsing vendored
byte-identically from the bootstrap reader. Its gate ran on a real Blender 4.2.1 LTS
found by the gate's own filesystem search, launched with `--background
--factory-startup` so that no user add-on, preference or startup file contributes to
the result: **16 PASS, 0 FAIL, 0 SKIP** in 3.5 s.

**Table 10 — Blender adapter: the measured clauses.**

| Clause | Measurement |
|---|---|
| import clean fixture | 36 nodes, 34 alive, 0 dead, 2 unknown-type skips, **0 unexpected skips**, 272 v / 408 t, 0.329 s |
| import damaged fixture | exactly {hash-mismatch: 1, unknown-type: 3}, 1 dead, 33 alive, mesh still imports, 0.149 s |
| round trip | uuid survived, all 7 facets / 15 tags survived, 272 → 272 verts; 0.151 s in, 0.220 s out, 0.022 s back |
| exported package | 624 539 B, 50 entries, 8 nodes, 49 files |
| verified by the reference core | 8 alive, **0 errors, 0 warnings** |
| verified by `werk_read.py` | **49/49 files**, exit 0 |
| writer determinism | **49/49 payload entries byte-identical** across two exports, same entry order |
| rig round trip | worst rest-head error **0 m**, worst posed rotation error **8.4e-08 rad**, recomposition residual 5.96e-08 vs a declared 1e-5 |
| textured round trip | sRGB and Non-Color **both preserved**; both material slots recovered |

*Writer determinism* matters because a format whose acceptance test is byte-identity
needs writers that do not drift: two exports of the same scene produced 49/49
byte-identical payload entries in the same order, with only the manifest's wall clock
differing — excluded from the comparison and named rather than hidden. And the
*colour-space* clause is the assertion that matters in the texture path, because a data
map read as sRGB is wrong mathematics and is invisible in review.

The gate caught five real bugs before it passed, and all five were of the silent kind
— each passed every structural check while producing wrong data. A conjugation where
a left-multiplication belonged, producing exactly 45° of error on every posed bone. A
frame-set call after setting a pose, which re-evaluated the half-built action and
discarded every value before it was keyed: the clip was structurally perfect and
animated nothing. Two authorities for one armature, producing duplicate rigs on
re-import. An identity comparison on Blender's RNA wrappers, where the API hands out a
fresh Python object per access, so *every texture slot silently vanished from every
exported material* while the texture nodes themselves were written correctly. And a
bootstrap-reader structure that does not carry node metadata, so every imported
texture fell to the default colour space — the fallback being deliberately the safe
direction, which is exactly why nothing looked wrong.

A sixth bug was in the *gate itself* and is worth as much: comparing quaternions after
rounding components to five decimals manufactured 8e-3 rad of "error" out of a round
trip exact to 1e-7. It would have been called a tolerance and lived with.

### 7.4 Unreal Engine: and the bug only rendering could find

The Unreal adapter is an editor-only UE5 plugin with two directions: import a `.werk`
into real engine assets, and export selected assets plus their real dependency closure
into a conformant unsigned package. Both a real UE 5.7 toolchain and MSVC 2022 build
tools were present, so the strong gate ran: the plugin compiled, and the import
commandlet ran against the golden fixture with exit 0 — 36 nodes, 25 imported, 11
skipped, 0 refused, 22 assets, 22 packages saved, **164 files hash-verified**,
signature reported `unverified`, 0.382 s inside the facade. The damaged fixture
returned **exit 1**, which is correct rather than a failure, with one node refused, 21
assets still created, and the unknown-because-newer node reported as unknown rather
than as broken.

Round trip: 272 verts / 408 tris in, **272 / 408 out**, identical engine-space
axis-aligned bounding box, and the WAV **byte-identical**. Three independent readers
agree on the exported package: the adapter's own engine-free core (9 PASS, 0 FAIL), the
unrelated `werk_read.py` whose independently computed manifest sha256 matched to the
character, and a standard JSON Schema validator against the schema the package
carries, with **0 errors**.

A second pass closed the texture gap, and its gate is **16 PASS, 0 FAIL** including all
three textures round-tripping **pixel-identical** — while the gate simultaneously
prints that PNG *bytes* are identical for **0 of 3**, because two different PNG
encoders will not agree on bytes and calling that a failure would be dishonest. Pixels
are the claim.

The most important result of this adapter is a bug, S10-6, and it is the argument of
the whole project turned on its author. Setting a mesh's UV channel count *invalidates*
a UV attribute reference taken before it. Writing through the stale reference raised no
assertion, logged no warning and returned no error, and the mesh came out with **every
UV at (0,0)**. Every count in every report stayed correct — 730 verts, 408 tris, three
textures imported, three slots bound, three switches on — and the crate rendered as one
flat texel of its own albedo. It was invisible from inside the adapter and invisible in
the package: the round-trip *pixel* comparison passed, because the texture bytes were
never the problem.

**The only thing that found it was pointing a camera at it.** The general lesson is the
one this paper is otherwise arguing for a format: *a report is not a measurement*.
Everything the adapter said about that import was true, and the import was wrong. The
regression test is now a number read back off the artifact — the measured UV extent of
the built mesh — and not a count of things attempted.

Two smaller findings of the same family were recorded alongside it: an engine
material-assignment call that silently does nothing on a freshly built mesh with an
empty material array while the importer reported "assigned to 1 mesh"; and a
material-graph connection API that returns false and logs nothing when it cannot find a
named input, producing a master material that compiled fine, listed every parameter
correctly, and rendered black.

### 7.5 Retarget: recovering units from bone directions

The skeleton work binds three real, foreign, independently authored rigs to a canonical
humanoid from *one* calibration pose each, and retargets real motion in both
directions. Gate: **33 PASS, 0 FAIL, 0 SKIP** in 29.2 s.

**Table 11 — three foreign rigs, one calibration pose each.** Round trip is through
the real f32 animation payload on disk. Declared tolerance 1.0e-4 rad, quoted from the
format's own animation layout grammar.

| Rig | Bones | Solved scale | Round trip |
|---|---|---|---|
| CesiumMan (glTF) | 19 | 1.35696 | 5.157e-08 rad |
| UE 5.7 mannequin | 68 | 0.99052 | 5.217e-08 rad |
| CMU mocap 02_01 (BVH) | 31 | 0.06152 | 8.803e-08 rad |

The scale column is the whole claim. Nothing told the solver that a BVH unit in that
capture is 6.15 cm, that Unreal is centimetres, or that CesiumMan is a 1.29 m figure.
It recovered each from one pose, together with the whole-body rotation that turns Z-up
into Y-up and left-handed into right-handed. The proof that it got the metre right is
physical rather than algebraic: the retargeted canonical figures land with their hips
0.837–1.092 m above the floor plane the skeleton declares, against a canonical rest hip
height of 0.98 m, with the lowest toe between −0.050 m and +0.034 m. A wrong scale
cannot produce those.

Six cross-rig transits — rig A to canonical to file to rig B and back — land between
5.2e-08 and 8.8e-08 rad, three orders of magnitude inside the declared tolerance. Each
transit *names* the bones that cannot cross rather than averaging them into a residual:
CesiumMan has no clavicles and no third spine joint, so a shoulder shrug captured
elsewhere does not survive a trip through it, and the gate says which bones those are.

The stage also produced a measurement that corrected its own argument, and the
corrected version is the finding. Retargeting error is frame-invariant *when* the
corresponding bones are parent and child in both rigs — measured spread across all
frames, 3.03e-14 rad and 7.60e-14 rad on two rigs. Where a foreign rig *interposes* an
animated joint, the invariance fails by exactly that joint's motion: 0.2217 rad. The
gate gates on the adjacent set and reports the interposed set beside it, never inside
it; the format's inability to say which interposed joints are artefacts and which are
real motion is filed as S6-3.

### 7.6 An unattended enrichment pipeline

The producer side is a pipeline that turns a bare GLB into a signed, schema-valid,
fully-enriched package with no human in the loop and no prompt at any point: thirteen
producers covering geometry, bounds, texture cook with linear-space mips, materials,
two-tier octahedral imposters, an LOD chain with a *rendered* screen-space error metric,
convex colliders, mass properties, drop-simulated rest poses, a signed distance field
and flow field, semantics, simulation properties and provenance. Gate: **19 PASS,
0 FAIL, 0 WARN** over three real GLBs.

**Table 12 — enrichment pipeline over three real assets.** The third is deliberately
the awkward one: 408 triangles, vertex colours, no images and no material block.

| | crate | lantern | example |
|---|---|---|---|
| bytes | 17 936 593 | 26 871 359 | 7 551 623 |
| nodes / files | 37 / 108 | 38 / 123 | 33 / 74 |
| derived nodes, `input_hash` recomputed | 27/27 | 28/28 | 23/23 |
| reference core | 0 err, 0 dead | 0 err, 0 dead | 0 err, 0 dead |
| producers | 16 ok | 16 ok | **15 ok, 1 failed** |
| wall | 196.9 s | 88.9 s | 72.3 s |

All 108 node versions across the three packages carry an epistemic stamp; all 78
stamped `measured` or `inferred` carry ordered inputs, parameters and a hash, and the
gate **recomputes every one of those 78 from the packages' own bytes** — 78/78 match.
All three verify standalone through the bootstrap reader and validate against the JSON
Schemas *the package itself carries*, never the repository's copy. Two runs with the
reproducibility flag are byte-identical.

The third column is the island rule under test rather than described. The texture
producer raised a named exception ("the GLB carries no embedded images"), the failure
landed in the package's own pipeline report with its exact exception text, and the
package came out anyway — 33 nodes, no source texture node, 0 dead nodes, 0 errors. A
producer failing yields a missing node and a report, never a dead pipeline and never a
fabricated node.

One more refusal is worth recording. One sample declares a longest axis of 25.66 m;
glTF units are metres and the manifest pins its unit scale to 1.0, so the pipeline takes
that at face value and does *not* rescale — its mass comes out at 130 tonnes. Silently
"fixing" a source's scale would make every downstream number a different lie, so instead
the bounds payload, the README and the run report all note that the axis is implausible,
that nothing was rescaled, and that the fix is to rescale the source.

### 7.7 The companion store

Law 1 forbids the *format* from being clever about redundancy; the companion doctrine
puts that cleverness in a version-control store, under a strict ordering of authority:
the materialised package is truth, the store is a cache. The store is Python with
*zero* third-party dependencies, including the cryptography. On a real production
corpus (a 43 MB photogrammetry mesh, a JPEG texture set, six rendered views, sixteen
recorded WAVs) with a real append-only edit, whole-blob content addressing measured a
dedup ratio of **1.9970×**, a marginal ingest cost for the second version of
**0.2404 %** of its own size, and a sync to a store already holding v1 that moved
**0.27 %** of v2's bytes. Both packages materialise *identical to the originals* under
a whole-tree hash comparison against the source directories.

Content-defined chunking (a FastCDC-style Gear chunker, 64 KiB/256 KiB/1 MiB, whose
gear table is derived deterministically from SHA-256 so that a foreign implementation
needs one sentence rather than 256 constants) was then measured on the conformance
fixture corpus plus a 4096-byte edit at a fixed offset of the corpus's largest payload:

**Table 13 — content-defined chunking vs. whole-blob.**

| | whole-blob | CDC |
|---|---|---|
| logical | 31.79 MiB | 31.79 MiB |
| physical | 26.72 MiB | **21.89 MiB** |
| dedup ratio | 1.1897× | **1.4524×** |
| edited pkg, marginal ingest | 5.15 MiB | **0.31 MiB** |

Chunk-boundary stability is the number that makes chunking worth having: the 4 KiB edit
changed **1 of 19 chunks**, so 18/19 (**94.7 %**) kept their hash, and syncing the
edited package to a remote already holding v1 moved **3.63 %** of its bytes. The
byte-exactness invariant is untouched by any of this: materialisation still re-reads the
*destination* and rehashes every file against the manifest, so chunking cannot weaken
the proof even in principle, and a materialisation that cannot prove byte-identity
raises and deletes its own output. The inverse is tested too — a test corrupts one
object inside the store and requires materialisation to fail and leave nothing behind —
because a round-trip assertion that compared the store against itself would be checking
our own bookkeeping.

Handed the deliberately damaged fixture, the store **refuses** it in 1.43 s with the
exact hash-mismatch report and records no reference. The refusal is the correct measured
behaviour: a store must not contain a package it cannot give back verified.

---

## 8. A verification pass at writing time

Every number above is transcribed from a recorded measurement. Because this paper is
about not trusting reports, we re-opened the four shipped conformance fixtures while
writing it and re-measured them independently of every harness, using nothing but the
Python standard library.

**Table 14 — the shipped fixtures, re-measured at writing time (2026-08-08)** directly
from the zip and its manifest. "Files" counts distinct paths reachable from
`nodes[].versions[].files[]`.

| Fixture | Bytes | Entries | Nodes | Files | Preview prefix |
|---|---|---|---|---|---|
| crate-v1 | 13 430 904 | 166 | 36 | 164 | 892 407 |
| crate-v1-damaged | 13 432 056 | — | — | — | — |
| ista-varun-v1 | 9 973 037 | 63 | 15 | 61 | 1 001 758 |
| crate-tex-v1 | 696 545 | 53 | 11 | 52 | 604 527 |
| humanoid-retarget-v1 | 1 251 512 | 57 | 8 | 55 | 966 124 |

It confirms most recorded values — the image fixture's declared preview prefix, total
size and node count exactly; the retarget fixture's 55 declared files, 21 858-byte
manifest and 966 124-byte preview prefix exactly; the textured fixture's size, hash,
node and file counts exactly — and it disagrees with the record in three places, which
we report as findings rather than reconcile silently:

1. **One fixture size, two recorded hashes.** `crate-v1.werk` is recorded once at
   13 430 904 bytes with sha256 `8cace0b9…` and once at the *same* byte count with
   sha256 `0e45deb9…`. The shipped file is the second. At least one recorded
   measurement was therefore taken against a build that has since been replaced without
   a size change, which is the hardest kind of drift to notice.
2. **A two-byte drift in the retarget fixture.** It is recorded at 1 251 514 bytes; the
   shipped file is 1 251 512 bytes with a different sha256. Every other recorded
   property of that fixture matches exactly.
3. **A stale file count in the profile-2 gate.** The gate records the three bootstrap
   readers verifying 60/60 files; the shipped package declares 61 distinct files, which
   is what the round-2 Rust agent independently counted.

The cause is the same in all three cases and is a real process finding: the fixtures
were rebuilt several times as specification fixes landed, several stages ran
concurrently against one working tree, and no document records which build each stage
measured. The format's own answer exists and is not yet applied to its own repository —
finding S-29 proposes a `spec_version` or `spec_sha256` in the manifest. On this
evidence we further recommend that a conformance fixture's sha256 be pinned in the
harness that measures it, so that a rebuild fails a gate instead of quietly changing
what the gate measured.

---

## 9. Limitations

This section is longer than convention would have it, because the format's central
claim is honesty about what is known, and a paper about that format cannot practise
otherwise.

### 9.1 Limits on the experiment

**n = 1 per language per round.** Round 1 is four data points and round 2 is two. A
success rate of 4/4 is consistent with a true rate anywhere above roughly 40 %. This
design can rule out a bad format; it cannot distinguish a good one from a lucky one.

**One model family.** Every agent in both rounds is from the same model family. A
shared blind spot would look exactly like a shared success. The one place this is
visible is Ed25519: three of four round-1 agents reached for constants they already
knew, and only the file's own test vector caught whether they were right. Testing at
least one non-Claude model has been the stated "next honest step" since round 1 and
remains untaken.

**Recognition is not fully excluded.** Agents were instructed to derive everything from
the file and their logs are consistent with that, but zip and glTF are ubiquitous. The
JavaScript agent wrote its zip reader from prior knowledge *before* opening the
specification and said so. What that measures is that the specification
*retro-confirmed* a from-memory implementation and caught a gap in it (zip64) — a
weaker but still real result.

**The stumble count is instruction-inflated**, by design, and is therefore not
comparable to a count gathered without that instruction.

**Timing is wall-clock over a whole agent session**, including reading, writing,
compiling, debugging and report-writing. It is not time-to-first-working-parse, and
there is no human baseline: we did not measure one, and until someone does, the times
in Table 2 are internally comparable and externally meaningless.

**Fixture gaps were closed only progressively.** Round 1's fixture carried no custom
binary at all, so the entire envelope apparatus — the layout grammar, the MessagePack
subset, the section consistency rule — went untested by that round; two agents wrote
envelope parsers and never got to run one. Round 2 closed that and opened others: it
ran no damage gauntlet at all, tested no zip64 container, no deflate container, and no
package with more than one kind of custom binary. No zip64 fixture exists anywhere in
the project, so every zip64 path any agent or implementation has written is unexercised
code.

**Two harness failures, counted as harness failures.** The first round-2 Rust agent died
21 minutes in, after building a complete 3 520-line reader across eight modules and
extracting the payloads, without delivering a report. Its workspace survives and shows
how far it got; its report does not exist. It is counted *neither as a success nor as a
failure of the format*, and the run was repeated fresh — a new agent in a new workspace,
never a resume. Separately, the harness wrote both round-2 agents' task transcripts as
**zero-byte files**, so the per-agent process data round 1 collected — the order in
which resources were read, per-part timings, whether the bundled loaders were consulted
— cannot be reported for the Python agent and is marked *not recorded* rather than
guessed. That is the run's own finding about itself: *an experiment whose evidence lives
only in a transcript is one lost file away from being an anecdote.* The agents' programs
and complete outputs are committed, and are the evidence for everything claimed about
them.

### 9.2 Limits on the implementations

**The vision-language properties path has never completed.** It is implemented,
environment-driven, and was exercised against a real endpoint that refused every
connection — all three gate runs record the connection refusal against the configured
address. The pipeline did not hard-require it and did not fail: it wrote a stub carrying
exactly one field and a note saying in plain words that no model was consulted. The
model-supplied path is therefore code that has been run only as far as the socket, and
it is the largest untested surface in that component.

**Tangents are not MikkTSpace**, and the package says so, declaring an
accumulate-then-Gram-Schmidt basis by name with a note stating exactly where it diverges
(UV chart seams, where MikkTSpace splits a vertex and this does not). The associated
finding, S3-4, records that no geometry node currently has anywhere to *declare* which
tangent algorithm produced its data, so a package whose tangents are not MikkTSpace is
silently inconsistent with a normal map that assumes they are.

**The convex decomposition is a measured-worse substitute.** V-HACD proper is roughly
6 000 lines of C++ and its maintained Python bindings are compiled wheels; vendoring
either would put a build toolchain or an opaque binary into a repository whose entire
argument is that you can read what you depend on. What runs instead is a declared
`voxel-hacd-lite/0.1` — V-HACD's three-step shape without its plane search, hull
simplification or volume-conservative merge. It is a worse decomposition, the fit method
says so, and *both* fit metrics are measured so a consumer can see how much worse:
Hausdorff 0.157–2.002 m and volume ratios of 2.0–3.8 rather than near 1.

**Frame invariance has a measured exception** (S6-3), stated in §7.5: 0.2217 rad of
frame-dependent error where a foreign rig interposes an animated joint, against 3e-14
where it does not, and no way in the format to say which interposed joints are artefacts
and which are real motion.

**Half a gate is measured for the engine consumer.** Its acceptance criterion names load
time *and* frame time; only load time was measured. Nothing in that work has been
through a renderer: no GPU upload, no draw call, no frame. The cooked tier's frame-time
claim is plausible and untested, and the engine-scale instancing test with imposters and
LOD selection did not happen at all, because the golden fixture carries neither.

**Coverage gaps that are real rather than rhetorical.** One Blender version on one
operating system; one build target for the reference core; no deflate and no zip64
support anywhere (both detected and refused by name); no skeleton or animation import in
the Unreal adapter; no Ed25519 in three of the consumers, each reporting `unverified`
rather than guessing; and only three small assets through the enrichment pipeline, none
above 6 576 triangles.

### 9.3 The limit that is a result

The round-2 fixture's own recipe carries an exclusion list that the delivered image
violates. We could have chosen a fixture without that property. We did not, because the
honest reading of it — supplied unprompted by an agent that had never seen the format —
is the most useful thing either round produced about recipes: *a recipe records
instructions, not guarantees*. Any system that treats a recorded prompt as evidence
about the pixels is wrong, and the reproducibility grade in the file is the field that
says so.

---

## 10. Related work

**glTF 2.0 / GLB** is the closest thing to a universal runtime interchange format for
3D, and werk uses it: geometry payloads inside a werk package *are* GLBs, because law 11
prefers a boring ubiquitous encoding over a clever new one. What werk adds is the layer
glTF deliberately does not have: glTF's semantics live in an external specification and
its extension ecosystem is a set of external agreements, so a GLB does not carry the
knowledge of how to read a GLB. The difference is measurable — agents here parsed GLB
from an embedded mini-specification without wanting anything external. werk also
overrides glTF's stated forward axis inside a package, because a convention has to be
one declared number rather than two conflicting documents.

**USD and USDZ** are the industrial answer to scene-scale composition, and their defining
strength — layered references and overrides across files — is structurally the pattern
law 1 forbids. This is a difference in purpose rather than a criticism: USD is a
composition system for live pipelines, and werk is an artifact doctrine for things that
must survive their tools. USDZ packages a scene for delivery; it does not package the
specification, the schemas, the readers, the provenance, the version history or the
custody chain, and a USDZ whose authoring application is gone is in exactly the position
this paper's introduction describes.

**C2PA** is the closest relative on provenance, and the contrast is the sharpest point of
design disagreement in this work. C2PA binds content credentials cryptographically and
derives its meaning from an enforcement-and-trust-list apparatus: a claim is worth what
its signer's position in a trust hierarchy makes it worth. werk's chain is deliberately
*facts-only*. It records who signed what state, it surfaces three states plus a fourth
"I did not check" token, and it enforces nothing — there is no trust list, no revocation
authority, and no notion of a compliant viewer. The format cannot prevent plagiarism; it
makes clean provenance the cheapest path and its absence conspicuous. Round 2's Python
agent articulated the consequence better than our own specification did: the chain
verifies, but its key is a published development key with no external root of trust, so
the declared author "is an assertion by a party and must not be presented as verified
authorship." The two models are complementary rather than competing, and the package
carries an explicitly labelled, explicitly unimplemented C2PA export stub rather than a
claim of interoperability — which the same agent correctly reported as proving nothing.

**FlatBuffers, Cap'n Proto, Protocol Buffers** and the self-describing serialisation
family solve zero-copy structured access with excellent engineering, conditional on the
consumer possessing the schema. werk's position is that the schema is part of the
artifact: schemas are stored as ordinary data files inside the package and the manifest
names their paths *inside this package*, never by convention. The cost is duplication —
every conformant writer must vendor a copy of every schema it emits — which is finding
S-29, filed by the Blender adapter, whose mitigation (a byte-identical vendored copy,
refreshed by one script, verified by that script's check mode, run as a gate clause) is
offered as the shape of a general answer rather than as one.

**Content-addressed stores** — Git, IPFS, OCI, Perforce's and Unity's asset databases —
solve dedup, transfer and identity, and werk's companion store is squarely in that
tradition, down to sharing the manifest's per-file sha256 as the store key with no
translation layer. The doctrinal difference is the ordering of authority: the
materialised package is truth and the store is a cache, never the reverse, enforced
structurally by making every round-trip assertion compare against the original on disk
and by a test that corrupts the store and requires materialisation to fail loudly and
leave nothing behind. **Reproducible builds** and the software bill-of-materials movement
share werk's instinct that an artifact should carry a checkable account of its own
production; `core.recipe` and the `input_hash` discipline are that idea applied to media
rather than to binaries, with the one difference that a model's weights may be named by
hash rather than carried.

---

## 11. On the authorship of this work

This paper is about whether autonomous agents can implement a format from a file. It
would be incoherent to obscure the fact that autonomous agents also built and tested the
thing being measured, so we state it plainly.

The doctrine, the twelve laws, the design decisions, every ruling on a filed finding, and
the acceptance criteria are the author's. The implementation work — the reference core,
the three bootstrap readers, the enrichment pipeline, the retarget solver, the store, the
Blender and Unreal adapters, the fixtures and the gate harnesses — was carried out by
Claude agents (Anthropic) working in a loop against written briefs, under a house rule
that nothing advances on assertion and every gate is a measurement. The gauntlet agents of
§4 and §5 are from the same model family, which is stated in §9 as the sharpest limit on
the experiment's external validity. The prose of this paper was drafted by an agent from
the recorded measurements and is the author's responsibility.

**First, the separation that makes the experiment valid is not between human and machine
but between *implementer* and *measurer*.** The gauntlet agents were isolated from the
repository, from the web, and from every artifact of the development process except the
single file handed to them. Whether the implementer of a package's producer was a human
or a model is irrelevant to whether a stranger can read the package; what matters is that
the stranger had nothing but the package.

**Second, agent-built systems make the "silently wrong answer" failure mode more
dangerous, not less**, and this work has the receipts. Five of the Blender adapter's bugs
and three of the Unreal adapter's passed every structural check while producing wrong
data; one was invisible in the package, invisible in the round-trip pixel comparison,
correctly reported by every count in every report, and found only by pointing a camera at
the result. An agent that writes plausible code and an agent that writes a plausible
report are the same agent. The defence here is structural: gates that assert exact sets
rather than absence of crashes, numbers read back off artifacts rather than counted at
attempt time, and independent readers that share no code grading each other's output.

**Third, the process failures are as reportable as the results.** Concurrent agents
sharing one working tree collided on a shared findings counter three times in one
afternoon and swept two stages' documents into a third stage's commit twice. Both are
recorded rather than tidied, on the same principle that governs the format: a history that
gets quietly corrected stops being a history.

---

## 12. Conclusion

Formats die when their knowledge dies. The response proposed here is neither a better
schema language nor a better archive: it is a constitutional rule that a file must answer
every question it raises, plus an experiment that tells you whether it does.

The experiment works. Six agents across two rounds, four languages and two profiles, each
given one file and nothing else, produced working readers — 6/6 — and between them
surfaced fifteen distinct specification bugs that internal review had not. None of them
learned the format from the readers bundled inside the file, which is the single result
that makes the metric mean what we want it to mean. Two recomputed an embedded,
epistemically stamped measurement from source pixels and hit every bit, which turns a
claim a package makes into one a stranger can check. Four spontaneously built damaged
copies and each got right the signature-versus-payload distinction we had flagged as the
easiest thing in the format to invert. And one, from a declared reproducibility grade
alone, correctly inferred the most important thing a generation recipe does not promise.

The honest next steps have not changed since round 1 named them, and they are named again
here because naming them and not taking them is the state of the work: more agents per
language, at least one model family that is not ours, a fixture carrying zip64 and a
deflate container, a damage gauntlet against profile 2, a frame-time measurement to close
the half-measured engine gate, and one vision model that answers so that an inference path
stops being code that has only ever reached a socket.

What we believe generalises beyond werk is the metric itself. Any format — scientific
data, documents, model checkpoints, medical imaging — can be handed to an isolated agent
with the instruction "write a reader". The success rate is interesting. The list of things
the agent had to guess is the product.

---

## Availability and acknowledgements

The specification, the reference implementation, the bootstrap readers, the adapters, the
pipeline, the store, all conformance fixtures, every gate harness, and the gauntlet
agents' verbatim programs and outputs are committed in the project repository. Every gate
in Table 8 is re-runnable, and every number in this paper is traced to its recorded
source, file and section, in `paper/NUMBERS.md`.

The manifesto is co-authored with Ken Gamble; the audio node family is adopted verbatim
from the splat-foley pipeline. The Khronos Group's CesiumMan and Lantern assets, Carnegie
Mellon University's motion capture database and Epic Games' mannequin were the foreign
rigs that made the interoperation measurements possible.
