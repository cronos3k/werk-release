# Stage SPECFIX-OW results — the open-weights findings turned into spec, and the same models run again

**Author:** the open-weights spec-fix agent. **Owns for this wave:** `spec/`,
`tools/payload_file.py`, the fixture builders, `fixtures/*.werk`,
`gauntlet/roundOW/` (post-fix runs only), `results/STAGE-SPECFIX-OW-RESULTS.md`,
and — this wave being the only one running — the final `HANDOVER.md` /
`ROADMAP.md` merge.

**Date:** 2026-08-09. **Work order:** `results/STAGE-OPENWEIGHTS-RESULTS.md`
§6, findings S-OW-1 … S-OW-6. **House rule applied:** every gauntlet failure
becomes a spec fix.

---

## 0. Headline

| | |
|---|---|
| Findings actioned | **S-OW-1, S-OW-2, S-OW-3, S-OW-4** (S-OW-5 and S-OW-6 are harness findings and are recorded as no-spec-change, §5) |
| New spec text | `MINI-SPECS` §12.1 + §12.2, `MINI-SPECS` §5 preamble, `SPEC` §2.1, `ENVELOPE.layout.txt` §0 worked-example clause |
| New machine-readable field | `payload_file` (optional, per node version) — **PROPOSED, pending Gregor's ruling** |
| New worked examples | WKGS and WKEM annotated hex dumps + their binaries; the signed-message construction end to end |
| Bug found and fixed while rebuilding | `make-examples.py` wrote CRLF on Windows, so a regenerated `spec/examples/` differed from a fresh checkout — every fixture hashing those bytes would have differed too |
| `spec_sha256` | `331519c8…` → **`3984a5550b8a4be95501c37544d36b90ac2f3834bdddf8007597a41405450ebd`** |
| Fixtures rebuilt | **7 of 7**, plus `gauntlet/roundOW/mini-v1.werk` |
| Gates re-run | **9**, all green (§3) |
| Post-fix model arm | **5 models run, 9 runs** — 3 re-runs against the fixed package, 2 new lineages post-fix-only, 1 (gemma-4-12b) unloadable (§4) |
| **The claim under test** | *failure located a spec gap → gap fixed → same model now passes* — **it did not hold for either failing model** (§4.4) |
| What did move | the 4B stopped fighting the zip container; **0 / 9 false tampering alarms**; the 9.4B control went pass-on-retry → **pass on attempt 1**; `gemma-4-e4b` is the **first sub-9B pass** in any open-weights round |
| The limit it measured | **making a fact machine-readable does not make a weak implementer read it** — the 8B took `files[0]` again with `payload_file` in the manifest in front of it |

---

## 1. The three knowledge-barrier failures, and what each one now says

### S-OW-1 — the signed-message construction

**The measured failure.** `mini-v1.werk` is `signed-and-valid`. Every model in
the round that touched the signature reported `present-and-invalid` — *tampering
on an intact package*. The string `werk-sig/1` occurred in exactly two files,
`spec/SPEC.md` and `spec/schemas/signature.schema.json`, and neither fitted the
31 490-token package. A reader on that budget could verify every hash and could
not verify a signature, and rather than say so it raised a false alarm.

**The fix.** `spec/MINI-SPECS.md` gains two subsections, in the file
implementers actually open for crypto:

* **§12.1 — what werk actually signs.** The six-field `werk-sig/1 LF …`
  construction; a table saying which field is read from *where* (and that
  `manifest_sha256` is **the entry's own**, not the top-level copy, and that
  `prev_entry_sha256` is the sha256 of the previous entry's `signature`
  **string**, the hex text, not the 64 raw bytes it denotes); then **a complete
  worked example on real bytes** — the six field values, the message as text
  with the LFs shown and the absence of a trailing one called out, the message
  as all 203 of its bytes in hex, a **CHECKPOINT** (`len(message)` and
  `sha256(message)`) to compare *before* comparing a signature, and the public
  key, the signature and `verify -> TRUE`.
* **§12.2 — the fourth token.** `unverified` is the correct verdict when you did
  not do the check; `present-and-invalid` means a link *failed*; reporting the
  second because you could not build the message is a false tampering alarm and
  is the most damaging answer available. If the checkpoint does not match, you
  have a construction bug, not a tampered package.

**The example is real and it is generated.** `spec/examples/` now carries
`SIGNATURE.example.json` — a one-link chain over the actual bytes of
`MANIFEST.example.json`, signed with the published RFC 8032 §7.1 test key that
`MINI-SPECS` §12 already prints — and `signature.example.txt`, the same thing
worked end to end in four steps. `make-examples.py` signs it, verifies it, and
**rewrites the block inside `MINI-SPECS` §12.1 between two markers**, so the
numbers in the prose cannot drift from the files beside them. That is
`fixtures/record_fixtures.py`'s rule applied to a second place: a number
transcribed into prose in more than one place is a number whose copies cannot
disagree loudly.

Honest note on the choice: the example is over `MANIFEST.example.json` rather
than over a shipped fixture's own manifest, and deliberately. A worked example
inside `spec/` that quoted its own package's signature would be circular —
editing the spec moves `spec_sha256`, which moves the manifest, which moves the
signature, which is in the spec. The example manifest does not depend on
`MINI-SPECS.md`, so the loop is broken and the numbers are stable, real, and
verifiable by anyone holding the file.

### S-OW-2 — which file in a node is THE payload

**The measured failure.** An 8B model opened the container, walked
`nodes[].versions[].files[]`, extracted `geometry/game.glb` **byte-exact**, then
followed `primary.sound` → node → `files[0]` and wrote out
`audio/sfx/crate-impact-hard-surface.json` — the **descriptor** — where a WAV
was asked for, and reported success. It is the round's only wrong artifact
produced by a program that believed it had succeeded, and nothing about it was
malformed: `primary` names a node, the node has five files, and the format never
said which one *is the sound*.

**Lineage.** S-13 ruled `primary: {mesh?, sound?, image?}` into existence and
left the within-node hop to prose. S-XV-4 (Moonshot, cross-vendor round) filed
it as still open: *"there is no single field a reader can follow to a path."*
S-OW-2 is the same gap with a measured consequence. Gregor has ruled on S-13; he
has **not** ruled on S-XV-4, so the shape below is **PROPOSED** and filed for
him — implemented now because it is optional and purely additive, so a package
written without it stays conformant and a reader that has never heard of it
behaves exactly as before.

**The fix — `SPEC.md` §2.1.**

1. An optional per-version field **`payload_file`**: the package-relative path of
   the file that IS this node's payload. It MUST equal the `path` of exactly one
   entry in the **same version's** `files[]`. A writer SHOULD emit it on every
   version whose `files[]` has more than one entry.
2. **Normative resolution order**, first rule that answers wins: `payload_file`;
   a single file; the reserved role `payload`; the node type's documented payload
   role (audio → `best`, `core.imposter` → `atlas`, `core.recipe` → `record`,
   `core.anim.clip` → the `.wkac`); **otherwise the payload is not
   machine-determinable** — report `payload-file-ambiguous` (severity `warn`,
   naming every candidate) and **MUST NOT** silently take `files[0]`.
3. **Three reserved `role` values** a reader may rely on across every node type:
   `payload` (this file IS the payload), **`descriptor` — never the payload**,
   and `best` (the recommended one of several interchangeable takes).
4. At `primary`: it keeps naming a **node**, because a node is the unit of
   version history and the answer must stay stable as versions accumulate — and
   a consumer resolving `primary.*` MUST apply the rules above.

Why not let `primary` name a path, which is the other half of S-13's ruling: a
path is a version-level fact and `primary` is a package-level one, so a package
whose sound gained a v2 would have to rewrite `primary` too and the two could
then disagree. The node reference stays; the missing hop is what was added.

**Where it landed:** `spec/SPEC.md` §2.1 and the `primary` bullet;
`spec/schemas/manifest.schema.json` (`payload_file`, the `role` vocabulary, the
`primary` description); `spec/schemas/manifest.image.schema.json` and
`spec/PROFILE-IMAGE.md` §8 (profile 2 inherits it — its `core.recipe` holds
five files); `tools/payload_file.py`, the single place a writer in this
repository computes it, called from `fixtures/build_golden.py`,
`build_image_fixture.py`, `build_retarget_fixture.py`, `pipeline/package.py`
and `gauntlet/roundOW/build_mini_fixture.py`.

**And it is now a gate clause, not a sentence.** `tests/run_gate_a.py` gained a
tenth check that executes the failure: resolve every `primary.*` key through
§2.1 and assert the result is the payload and not a `.json` descriptor, plus
`check_payload_files` over the whole manifest. Measured:
`mesh -> geometry/game.glb`, `sound -> audio/sfx/crate-impact-hard-surface.wav`.

### S-OW-3 — the worked example is the rung between a grammar and a decoder

**The measured failure.** `qwen3-coder-30b`, the strongest model in the round,
had `ENVELOPE.layout.txt` §4 — a *complete* MessagePack subset — in context, read
it, wrote *"Actual MessagePack parsing would require a proper parser / This is a
demonstration"*, and then printed quaternion components like
`71554213196777853550592.0000` read from guessed offsets, as data. What it did
not have was `spec/examples/restposes.example.hex.txt`, which the mini fixture's
trimmed `spec/` tree had dropped.

**The fix, in three places.**

* Every envelope magic the core spec defines now ships a real binary and an
  annotated byte-by-byte hex dump, all regenerated byte-identically by
  `spec/examples/make-examples.py`:

  | file | magic | size | what makes it worth annotating |
  |---|---|---:|---|
  | `restposes.example.hex.txt` | WKRP | 560 B | 2 poses, 7 contacts (already existed) |
  | **`gsplat.example.hex.txt`** | **WKGS** | **1120 B** | 3 Gaussians at `sh_degree` 1, so `sh-rest` is **non-empty** and coefficient-major ordering — the format's single most expensive mistake — is visible in the bytes |
  | **`embedding.example.hex.txt`** | **WKEM** | **512 B** | `dim` 8 and 3 swatches: one section of **each branch** of the envelope's section-consistency rule |

  Each dump annotates the magic, the version, `header_len`, the whole
  MessagePack header, the alignment padding, **record 0 of every section on its
  own line** with the field meanings, the remaining records, the trailing
  padding — then prints the decoded header as JSON and the decoded payload as
  values (for WKGS: mean, scale, quaternion, opacity, `sh-dc` **and the linear
  RGB it becomes**, and all three `sh-rest` coefficients, per Gaussian).
* `ENVELOPE.layout.txt` §0 names all three and states the doctrine: a complete
  grammar is still not a decoder, and the worked example is **part of the
  minimum documentation set for any package carrying an envelope**, not an
  optional extra. `gsplat.layout.txt` and `embedding.layout.txt` each point at
  theirs in their opening paragraphs.
* `gauntlet/roundOW/build_mini_fixture.py` keeps
  `spec/examples/restposes.example.hex.txt` (and its binary) in the small
  fixture's trimmed spec tree, and `driver.py` inlines it. That is the fix under
  test in §4's envelope arm.

### S-OW-4 — nobody told them the zip library existed

Both sub-9B failures were at the container: one called `json.loads()` on the
whole `.werk` for eight iterations; the other hand-rolled an EOCD scan that never
found the EOCD, in sixteen. Both had `MINI-SPECS` §5 **and** a complete entry
listing with local-header offsets. The spec was not wrong — the cheapest correct
path was simply never stated. `MINI-SPECS` §5 now opens with it: **if your
language has a zip library, use it**; a `.werk` is an ordinary standards-
conformant zip; nothing in this format asks you to write a zip parser; the
byte-level description below is the fallback for the reader that has no library
(the embedded Rust and C loaders may use none), for ranged reads, and for
checking what a library said. Graded effort applied to the reader's first five
minutes.

---

## 2. One bug found by doing the drill

`spec/examples/make-examples.py` wrote its outputs with `write_text(...,
encoding="utf-8")` and no `newline=`, so on Windows it emitted **CRLF**.
`.gitattributes` pins the whole tree to LF precisely because *"a spec file whose
line endings change between checkouts has a different sha256, and sha256 is the
store key"* — so a fixture built after running the generator on Windows embedded
CRLF bytes that a fresh clone does not have, and the rebuild would not reproduce.
It was invisible until this wave because the generator is rarely run. Every write
in that file is now `newline="\n"`, and the first fixture set built this session
was discarded and rebuilt. Filed as **S-SFX-1** (§5).

---

## 3. The consequences drill

`spec_sha256`: `331519c8d96aca0f8ea31200c68a6b28d62205f8458038a06cf2057fa5734575`
→ **`3984a5550b8a4be95501c37544d36b90ac2f3834bdddf8007597a41405450ebd`**.
Blender vendored spec re-vendored **first** (it is what builds `crate-tex-v1`):
`tools/blender/vendor_spec.py` → **vendored 57, verified 57/57 byte-identical**
(51 → 57: the six new worked-example files).

### Rebuilt fixtures

| fixture | bytes | sha256 |
|---|---:|---|
| `fixtures/crate-v1.werk` | 13 684 477 | `0a7a7341d5d508c75925a8c3be0b6c8ccdcced607d9bdd0b26f04e264f029106` |
| `fixtures/crate-v1-damaged.werk` | 13 685 629 | `01348a10f08638020542b2eb426d06603c32dc817883cec4cf77d42df1d137ac` |
| `fixtures/crate-tex-v1.werk` | 948 659 | `0b43cfb86a061aaf18885198971cf1612eb2eceff6fb387ab4467071c2a1d76b` |
| `fixtures/ista-varun-v1.werk` | 10 192 487 | `923ab39f1742e0b2368cdfdd01352ce89cbdc820206007c2d62bae92e5881553` |
| `fixtures/humanoid-retarget-v1.werk` | 1 514 545 | `916cf5c1049f17c6eccec31744683706a0077b7ce428f6f8e91fdaf42b13ad94` |
| `fixtures/gsplat-v1.werk` | 30 235 611 | `ede0aee6cc5659af741059b747dc3f3459db220234e7ffb95c4437c02337090a` |
| `tests/fixtures/crate.werk` | 684 925 | `089929d0593b614e91c1d41aba3515a14faf653f8dde076475651498aac5083d` |
| `gauntlet/roundOW/mini-v1.werk` | 960 061 | `f7bdcc853009504b1d31b2934a7a8294cbf0e6f227c95f7de1e81af0947e9837` |

`crate-v1` gains 20 `payload_file` declarations (one per audio node) and six
files in its `spec/` tree; `mini-v1` gains one `payload_file` — the one the 8B
model got wrong — and the worked WKRP hex example. `crate-tex-v1` is built
through Blender and carries a wall-clock `created`, so its whole-file hash
changes on every rebuild by design; the pinned bytes are the shipped build.

### Gates, all re-run fresh against the rebuilt fixtures

| gate | command | result |
|---|---|---|
| Stage 2 | `python tests/run_gate.py` | **11 PASS, 0 FAIL, 1 SKIP** — the skip is the same pre-existing broken msys2 `gcc.EXE` on this host |
| Stage 3A | `python tests/run_gate_a.py` | **10 PASS, 0 FAIL, 0 SKIP** — 9 + the new `primary.* resolves to a payload file (S-OW-2)` clause |
| Stage 3B | `python tests/run_gate_3b.py` | **19 PASS, 0 FAIL, 0 WARN** |
| Stage 6 | `python tests/run_gate_6.py` | **34 PASS, 0 FAIL, 0 SKIP** (30.5 s) |
| Stage 9 | `python tests/run_gate_9.py` | **15 PASS, 0 FAIL, 0 SKIP** |
| Stage 12 | `python tests/run_gate_12.py` | **18 PASS, 0 FAIL, 0 SKIP** (14.7 s) — the rebuilt package still regenerates its WKGS byte-identically from its own embedded tools |
| Stage 11 (Blender) | `python adapters/blender/test_gate.py` | **20 PASS, 0 FAIL, 0 SKIP** (5.9 s) |
| Stage 10B (Unreal, UE 5.7) | `python adapters/unreal/tests/roundtrip_gate.py` | **16 PASS, 0 FAIL** — after the +6 rebaseline below |
| CUB | `cargo test` in `<lab>\CUB\crates\cub-werk`, `CUB_WERK_FIXTURES=<repo>\fixtures` | **43 passed, 0 failed** |

**Two pins moved, both for one checkable reason.** This wave added **six** files
to the vendored `spec/` tree — `examples/gsplat.example.wkgs`,
`examples/gsplat.example.hex.txt`, `examples/embedding.example.wkem`,
`examples/embedding.example.hex.txt`, `examples/SIGNATURE.example.json`,
`examples/signature.example.txt`. The Unreal gate's four import rows each moved
by exactly **+6** files-verified (`crate-v1` 172→178, `crate-tex-v1` 60→66,
`ista-varun-v1` 68→74, `crate-v1-damaged` 168→174) with node, imported, skipped,
refused, asset and package counts unchanged in every row; rebaselined with the
reason written beside the numbers. `cub-werk`'s pin failed loudly with both
hashes, which is the pin doing its job; re-pinned and `files_verified`
re-measured **156 → 162**, same +6. The UE gate ran with no `UnrealEditor`
process alive (checked before launch).

**One real failure caught by the drill, not by a pin.** The first
`run_gate_a`/`run_gate_9` runs after the schema edit reported
`schema-invalid: property 'payload_file' is not permitted here`, killing 20
audio nodes and the image fixture's recipe node. Two distinct causes, both
correct behaviour: the werk-core `.dll` the Python binding loads was stale
(`manifest.schema.json` is `include_str!`-ed into the Rust core, so the schema
change needs a rebuild — HANDOVER's "stale-DLL trap", hit again), and
`manifest.image.schema.json` genuinely had not been updated. Both fixed;
profile 2 now carries the field and the reserved-role vocabulary too.

---

## 4. The post-fix model arm

**The claim under test, stated before the runs:** *a failure located a spec gap;
the gap was fixed; does the same model, under the same protocol, now pass?*
Whatever the outcome — improvement, no change or regression — it is the result.

### 4.1 Protocol, and what is and is not comparable

Identical to the pre-fix round in every controllable respect:
`gauntlet/roundOW/driver.py`, no tools, the whole self-description inlined,
one complete program per turn, the harness runs it in an isolated directory
against the real fixture and feeds back stdout/stderr/traceback, **8 feedback
iterations or 45 minutes**, generation cap 16 384 tokens, LM Studio at
`127.0.0.1:1234`, `--parallel 1`, **one model loaded and one request in flight
at any moment** (Gregor's standing order), every run cold-started with
`lms unload --all` first so each pays its own prefill.

**What deliberately changed, because it *is* the fix:** the fixture is the
rebuilt `mini-v1.werk` (`f7bdcc85…`), whose `MANIFEST.json` now carries
`payload_file` on the audio node and whose trimmed `spec/` tree now carries the
worked WKRP hex example; the inlined `MINI-SPECS` §5 and §12 are the rewritten
ones; and `driver.py` adds `spec/examples/restposes.example.hex.txt` as an
eighteenth package item, per S-OW-3's ruling that the worked example belongs to
the minimum set. The package therefore grew from **31 490 → 32 722 tokens**
(`llama-3.1-8b`'s own tokenizer; 103 573 characters, 18 of 18 items included,
**nothing omitted**) — still inside Gregor's 35 000-token budget, which was the
constraint the whole experiment is built around.

**Two populations, kept apart.**

* **Re-run population** — `llama-3.1-8b-lexi-uncensored`, `qwen3.8_4b_distilled`
  and, as a control, `zai-org/glm-4.6v-flash`. These have a pre-fix baseline and
  are the actual test of the claim.
* **Post-fix-only population** — `nvidia/nemotron-3-nano-4b`,
  `google/gemma-4-e4b` and `google/gemma-4-12b-qat`, which arrived after the
  fixes landed. **They have no pre-fix baseline and nothing below implies one.**
  They are worth running for three separate reasons: nemotron-3-nano-4b is a
  **second, independent 4B lineage**, which tests whether the 4B floor is a class
  property or was specific to one distill; gemma-4-12b fills the empty band
  between 9.4B and 27B in the threshold table; and gemma-4-e4b is an
  *effective-4B* — LM Studio reports **7.5B** raw parameters at 6.33 GB with a
  `gemma4` architecture, i.e. an elastic/nested model whose "e4b" name is a
  compute claim rather than a parameter count, which makes it its own data-point
  class rather than a 4B or an 8B. NVIDIA and Google are also two training
  lineages the round did not have.

**Loaded context, measured not assumed** (the round's own rule). Every model in
this arm ran at **131 072**. For `llama-3.1-8b`, `qwen3.8_4b_distilled`,
`glm-4.6v-flash` and `gemma-4-e4b` that is the model's own nominal maximum. For
`nemotron-3-nano-4b` (nominal 1 048 576) and `gemma-4-12b-qat` (nominal 262 144)
it is **below** nominal, and that is recorded rather than hidden: 24 GB of VRAM
does not hold those KV caches, the round already measured what LM Studio does
when asked anyway (it loads, and prefill collapses 6.4×), and holding the loaded
window identical across the whole arm is what makes the six wall clocks
comparable. 131 072 is ~4× what the 32 722-token package needs.

### 4.2 Results, graded by artifact

Nine runs. Every row below is decided by `gauntlet/roundOW/grade.py` hashing the
bytes the run left on disk against `MANIFEST.json`, never by a model's report.
Both passes were additionally re-run in a clean directory containing only the
fixture, and reproduced.

**Re-run population — the actual test of the claim.**

| model | class | pre-fix final | **post-fix attempt 1** | **post-fix retry** | **post-fix final** | first clean run | wall |
|---|---|---|---|---|---|---:|---:|
| `zai-org/glm-4.6v-flash` *(control)* | 9.4B | PASS (needed the retry) | **PASS** — both digests | not needed | **PASS** | **1** (was 3) | 229.2 s |
| `llama-3.1-8b-lexi-uncensored` | 8B | FAIL | FAIL — mesh byte-exact, **descriptor JSON written as the sound** | FAIL — clean exit, **wrote nothing** | **FAIL** | 4 / 7 | 317.4 s / 340.3 s |
| `qwen3.8_4b_distilled` | 4B | FAIL | FAIL — hand-rolled zip, `Failed to read EOCD`, 8× | FAIL — **`import zipfile`, container open, all 34 entries listed**, then died printing `✗` to a cp1252 console, 8× | **FAIL** | never | 533.4 s / 620.5 s |

**Post-fix-only population — no pre-fix baseline exists and none is implied.**

| model | class (as served) | attempt 1 | retry | **final** | first clean run | wall |
|---|---|---|---|---|---:|---:|
| `google/gemma-4-e4b` | 7.5B raw / "effective 4B", `gemma4`, vision-capable | FAIL — clean exit, wrote nothing | **PASS** — both digests | **PASS** | 3 / **1** | 171.3 s / 48.2 s |
| `nvidia/nemotron-3-nano-4b` | 4.0B, `nemotron_h`, tool-trained | **harness/serving failure**, not scored (§4.3) | FAIL — computed **both correct digests, including the right WAV**, and never wrote the files | **FAIL** | 3 | 38.6 s |
| `google/gemma-4-12b-qat` | 12B, `gemma4` | **could not be loaded** (§4.3) | — | **not run** | — | — |

`PASS` = the program, re-run clean, wrote both payloads and both digests equal
the manifest's: `geometry/game.glb` → `eee8b3cb…4ef2ce`,
`audio/sfx/crate-impact-hard-surface.wav` → `1e634f03…59aa5e`. **The same two
digests as rounds 1–3, the cross-vendor round and the pre-fix open-weights
round**, now produced by two more model families.

Package size, per model's own tokenizer (LM Studio's `prompt_tokens` for the
exact message): **32 722** (llama-3.1-8b), **33 333** (glm-4.6v-flash),
**37 032** (qwen3.8-4B), **37 834** (nemotron), **39 767** (gemma-4-e4b).

### 4.3 The two runs that are not results

Recorded rather than scored, exactly as S-OW-5 requires — a serving-stack or
harness failure is not a model failure and is certainly not a format failure.

* **`nvidia/nemotron-3-nano-4b`, attempt 1 — a HARNESS defect, and it was ours.**
  The model emitted `U+2011` (non-breaking hyphen) in its first reply; the
  driver echoes replies to a cp1252 console and died with `UnicodeEncodeError`
  mid-run. **Fixed in `driver.py`** — `say()` now degrades the console echo and
  keeps the UTF-8 log intact — and the run was repeated. Its second attempt then
  hit **HTTP 500** from LM Studio on the follow-up request, the same class as the
  pre-fix round's HTTP 400; the third attempt ran clean and is the row above.
* **`google/gemma-4-12b-qat` — could not be loaded at any context.**
  `lms load` fails with an uninformative *"Failed to load model"* at 131 072,
  65 536, 32 768, 16 384, 8 192 and at defaults, with 23.9 GB of the 4090 free
  and no other model resident; a JIT load through the API brings it up only at
  **4 096 context, `--parallel 4`**, which cannot hold a 37k-token package, and a
  direct API request to it then returns HTTP 400. LM Studio 0.4.12+1, `gemma4`
  runtime. **Excluded from the arm.** No claim is made about this model, and the
  9.4B–27B gap in the threshold table stays empty.

### 4.4 What moved, what did not, and the one thing that moved most

Read straight, without smoothing:

**S-OW-2 (`primary.sound` → descriptor): NOT FIXED at 8B.** The 8B model did the
identical thing again — followed `primary.sound` to its node and took `files[0]`
— and `payload_file` was **right there in the manifest it had read**, on that
node, naming the WAV. Its program contains an early `return` inside the
`for file in version['files']` loop. It never looked at `payload_file` and never
looked at `role`. *The fact is now present, findable and unambiguous — and this
implementer still did not use it.* Under §0b's triage that reclassifies the
failure: it was a knowledge-barrier failure while the fact was absent, and with
the fact present it is a **capability** failure. **Making a fact machine-readable
does not make a weak implementer read it.** That is the sharpest thing this arm
measured and it is a limit on what a format can do.

**S-OW-4 (the zip layer at 4B): MOVED, one layer.** Pre-fix, `qwen3.8-4B` spent
sixteen iterations across two runs never finding the EOCD, and never read a byte
of the manifest. Post-fix its retry **imported `zipfile`**, opened the container
on the first try and printed a complete, correct listing of all 34 entries with
sizes — then died, eight times, on `print()`ing a `✗` to a cp1252 console. The
grade is still FAIL and the failure layer moved from *the container* to *its own
program's console I/O*. That is what one sentence of documentation bought at 4B:
not a pass, but the end of the sixteen-iteration EOCD loop.

**S-OW-1 (the false tampering alarm): no false alarm in this arm, on small
numbers.** Zero of the nine post-fix runs claimed a signature verdict it had not
earned. One of them — `qwen3.8-4B`, the weakest model in the arm — **restated the
new rule back**, in its own words, as something the specification requires:

> "`SPEC.md` §6 (signature verification) require that a verifier reports
> `present-and-invalid` only when a link fails, not when the message construction
> is wrong."

and `google/gemma-4-e4b` **quoted the construction verbatim** in its report —
`werk-sig/1 LF manifest_sha256 LF prev_entry_sha256 LF signed_at LF signer.uri
LF signer.kind` — while noting it is *"only fully detailed in an example
section"*, which is a fair complaint and is filed as **S-SFX-5**.
**The honest limitation:** in the pre-fix arm exactly **one of thirteen** runs
put a false verdict in its own text (`glm-4.7-flash`'s retry: *"Signature
verification FAILED"*), and that model is not in the post-fix arm. So the
comparison is **1/13 → 0/9 with a changed roster**: consistent with the fix
working, nowhere near sufficient to establish it. What *is* established is
narrower and still worth having: **the construction is now inside the
documentation budget** — two models read it and one of them quoted the rule that
depends on it, neither of which was possible before.

**The control improved.** `glm-4.6v-flash` needed a retry pre-fix (its first
program exited 0, printed "Integrity verification PASSED" and wrote nothing) and
now passes on **attempt 1, with its first clean run at iteration 1** instead of 3.
One model, one run: suggestive, not decisive.

**The threshold table, extended, with every caveat attached.**

| class | model | lineage | post-fix result | note |
|---|---|---|---|---|
| 4B | `qwen3.8_4b_distilled` | Qwen | **FAIL** | pre-fix FAIL too; failure layer moved container → console I/O |
| 4B | `nvidia/nemotron-3-nano-4b` | **NVIDIA**, `nemotron_h` | **FAIL** | **a second, independent 4B lineage.** Resolved both payloads correctly and verified both digests; never wrote the files (S-OW-6 again) |
| ~4B effective / 7.5B raw | `google/gemma-4-e4b` | **Google**, `gemma4` | **PASS** (retry) | the first sub-9B pass in any open-weights round — but its *raw* parameter count is 7.5B, so it does not lower the 4B floor |
| 8B | `llama-3.1-8b-lexi-uncensored` | Meta | **FAIL** | same wrong artifact as pre-fix, with the fix present in the manifest |
| 9.4B | `zai-org/glm-4.6v-flash` | Z.ai | **PASS** (attempt 1) | improved from PASS-on-retry |
| 12B | `google/gemma-4-12b-qat` | Google | **not run** | could not be loaded (§4.3) |
| 27B, 30B, 30B-A3B | (pre-fix roster) | — | PASS | not re-run this wave |

**So the 4B floor holds against a second, independent lineage** — nemotron-3
failed too, which is evidence that 4B was a class property and not a quirk of one
distill — **and the sub-9B band is no longer empty**: `gemma-4-e4b` passed. It is
a 7.5B model marketed at effective-4B compute, so it belongs in its own row and
lowers the *compute* floor without lowering the *parameter* floor.

**Verdict, stated as measured.** The claim under test was *"failure located a
spec gap → gap fixed → same model now passes"*. **It did not hold for either
model that had failed.** Both re-runs still fail, one of them in the identical
way with the fix visible in front of it. What did change is real but smaller than
the claim: the 4B stopped fighting the container, nobody raised a false tampering
alarm, the weakest model in the arm cited the new rule, the 9.4B control moved
from pass-on-retry to pass-on-first-attempt, and two lineages that had never seen
werk produced the same two digests every previous round produced. **A spec fix
removes an excuse; it does not supply a capability.**

---

## 5. Findings

**S-SFX-1 — the worked-example generator wrote CRLF, so regenerating `spec/`
broke byte-reproducibility against a fresh clone.** `spec/examples/make-examples.py`
used `write_text(..., encoding="utf-8")` with no `newline=`, which on Windows
emits CRLF. `.gitattributes` pins the whole tree to LF for exactly the reason
stated in its own comment — a spec file whose line endings change has a different
sha256, and sha256 is the store key — so a fixture built after running the
generator embedded bytes a fresh checkout does not have, and the rebuild did not
reproduce. Latent since the generator was written, invisible because it is rarely
run, and caught here only because this wave both edited it and rebuilt everything.
*Fixed:* every write in that file is `newline="\n"`; the first fixture set built
this session was discarded and rebuilt. **Severity: medium**, and it is a finding
about *tooling*, not about the format. **Closed.**

**S-SFX-2 — `manifest.image.schema.json` had to be updated separately, and
nothing would have told us.** Adding `payload_file` to `manifest.schema.json`
silently killed profile 2's `core.recipe` node with `schema-invalid`, because the
image profile carries its own copy of the version object and the two schemas
share no `$ref`. Both were fixed, and the duplication is the real finding: two
manifest schemas with independently maintained copies of one `$defs/version`
shape will drift again. *Proposed:* either `$ref` profile 2's version object at
profile 1's, or add a gate clause that diffs the two `$defs/version` property
sets and fails on divergence. **Severity: low-medium. Open**, filed for Gregor.

**S-SFX-3 — the stale-DLL trap caught this wave too, and it is now three for
three.** `manifest.schema.json` is `include_str!`-ed into the Rust core, so a
schema edit needs `cargo build --release` before the Python binding's
`werk.dll` reflects it; without that, `run_gate_a` and `run_gate_9` report 40
`schema-invalid` errors that look exactly like a bad schema. HANDOVER already
records this trap from Stage 9. *Proposed:* have the gate harnesses build the
cdylib themselves (or assert the DLL's mtime is newer than
`spec/schemas/manifest.schema.json`) rather than trusting whatever is on disk.
**Severity: low** — it always fails loudly, it just fails *misleadingly*.
**Open.**

**S-SFX-4 — the harness runs generated programs on a cp1252 console, and that
kills programs that are otherwise correct.** `qwen3.8-4B`'s retry opened the
container correctly and died eight times printing a `✗`; `nemotron`'s first run
killed the *driver itself* on a `U+2011`. The driver is fixed; the child process
is not. *Proposed:* run `solution.py` with `PYTHONIOENCODING=utf-8` in its
environment. Deliberately **not** applied retroactively to this arm — changing
the harness mid-experiment is what the pre-fix round refused to do — so it is
filed for the next round. **Severity: medium** for any future Windows run.
**Open.**

**S-SFX-5 — a model found the signed-message construction and called it "only
in an example section".** `google/gemma-4-e4b` quoted the construction verbatim
and then listed it under *missing information* because it read it out of §12.1's
generated worked block rather than out of the surrounding normative prose. The
prose *is* there — the six-field line and the field-provenance table sit above
the block — but the block is what a reader lands on. *Proposed:* move the
one-line construction and the "no trailing newline" sentence into §12's opening
paragraph, so it is the first thing in the section rather than the middle.
**Severity: low. Open**, filed for Gregor.

**S-OW-5 and S-OW-6 need no spec change, recorded so the ledger says so.**
S-OW-5 is two serving-stack failure modes (a reasoning model returning zero
characters of content three times; LM Studio 400-ing on a conversation
containing its own earlier reply) and S-OW-6 is "exit code 0 is not did-the-job".
Neither is a property of werk. S-OW-6's lesson is already institutionalised —
grading is by artifact, in `gauntlet/roundOW/grade.py`, and this wave's arm is
graded the same way; **it fired again here**, see §4.2.

---

## 6. Interpretation ruling (Gregor, 2026-08-09) — what the sub-9B failures mean

Binding framing for how the open-weights failures are reported going forward,
including the paper's eventual editing pass. Recorded in Gregor's argument,
lightly edited for the page:

**The failure mode measured here is worst-case by construction, and it sits
outside the format's actual use case.** These runs put small models behind a
bare OpenAI-compatible API in LM Studio — no agent harness, no ability to
build their own tooling or scaffolding, no scratch Python, no supplementary
notes as external memory, and no second intelligence supervising. That is the
weakest possible link, deliberately: the same models inside any real agent
harness would have had the safety net the frontier models had, and — decisive
for the survivability scenario — **the archaeologist is part of the system.**
If a human managed to start the computer, a human is sitting at the keyboard.
A model that writes 90 % of a correct loader and then fails to print the
output file has made an error a supervising human sees and fixes in a minute
(or simply tells the model to fix). Both failing models in this arm were of
exactly that kind: nemotron-3 resolved both payloads and verified both digests
and only failed to write files; the 4B's residual failure was console
encoding. Unsupervised-tiny-model-in-a-broken-environment is not a scenario
anyone will operate — nobody in the future is choosing an outdated small
model, poorly set up, in an incomplete environment, alone, as their
archaeology instrument.

**Therefore:** the sub-9B threshold is an interesting *benchmark* result about
internal model capability under zero support, worth reporting as the novelty
it is — and it is **irrelevant to the format's premise**, because the ladder
(harness → supervision → human) supplies exactly what these conditions
removed, and every rung above the void condition passed everything. Report it,
acknowledge it, do not overemphasize it as a problem, because it isn't one.

This is consistent with what the rounds themselves measured: the post-fix arm
concluded "a spec fix removes an excuse; it does not supply a capability" —
this ruling adds that in every real deployment, *the environment supplies the
capability*. The two claims together close the question.
