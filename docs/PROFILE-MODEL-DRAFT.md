<!-- Repository copy. The authoritative copy for the fixture is
     gauntlet/roundSR/pkgsrc/PROFILE-MODEL-DRAFT.md, which is what
     gauntlet/roundSR/selfrun-v1.werk carries at spec/PROFILE-MODEL-DRAFT.md. -->

> **WHY THIS FILE IS IN `docs/` AND NOT IN `spec/`.** The brief that produced it
> asked for `spec/PROFILE-MODEL-DRAFT.md`. It is here instead, deliberately, for
> one measured reason: **`spec_sha256` is computed over the `spec/` tree a
> package carries**, so adding any file to the repository's `spec/` directory
> moves that digest and invalidates every conformance fixture's manifest — and
> at the moment this was written another agent was mid-wave rebuilding exactly
> those fixtures. Adding a file to `spec/` would have silently invalidated a
> rebuild that had just been measured. The draft is additive and non-normative,
> so the cost of the correct placement is zero and the cost of the requested one
> was somebody else's re-run.
>
> **The move, when a spec wave next runs:** `git mv docs/PROFILE-MODEL-DRAFT.md
> spec/PROFILE-MODEL-DRAFT.md`, then rebuild all fixtures and re-record
> `fixtures/fixtures.json`, because the digest will move. Do it in the same
> commit as another spec change rather than on its own.

# werk profile `model/1` — DRAFT

**STATUS: DRAFT. NOT NORMATIVE. NOT RULED ON.** No conformance clause anywhere
turns on this document. It exists because a package was built that had nowhere
to declare what it was, and the honest response to that is a written sketch
rather than a quiet extension of profile 1.

Profiles that ARE normative: `3d-entity/1` (`spec/SPEC.md`) and `image/1`
(`spec/PROFILE-IMAGE.md`). This one is written in their shape and mostly
by subtraction from profile 1, exactly as `image/1` is.

The package you are reading this inside declares
`profile: "model/1-draft"` and validates against
`spec/schemas/manifest.model-draft.schema.json`, which travels beside it. A
reader that has never heard of the profile reports it as a note and carries on,
which is what `SPEC.md` §10.2 already says to do.

## 0. Why a profile at all

A werk profile answers one question: *what must a package of this kind carry
before it is allowed to call itself complete?* For a 3D entity that answer is a
mesh and the conventions to interpret it. For an image it is pixels and a colour
space. For a **model**, the answer this draft argues for is:

> A `model/1` package is complete when a competent stranger, given the file and
> nothing else, can make the model produce output and check that the output is
> right.

Everything below follows from that sentence. It is deliberately an
*operational* completeness test rather than a structural one, and it is
testable: hand the file to somebody who has never seen the format and see
whether they get output. This draft was written from one such run.

## 1. Required nodes

| node | type | why it is required |
|---|---|---|
| the weights | `core.model.weights` | the thing itself |
| the vocabulary | `core.model.tokenizer` | text models are unreadable without it, and a tokenizer is not a detail of the weights: it is a second artifact with a second format |
| the runtime | `core.tool`, `role: "viewer"` or `"creator"` | **source**, under §7.1's existing doctrine. This is the load-bearing requirement and the reason the profile is interesting |
| the anchor | `core.model.testvectors` | a deterministic input, its exact expected output, and the environment that produced it |
| the record | `core.recipe` | how the weights came to exist, honestly graded |
| the facts | `core.disclosure` | base doctrine, §3.12; a model is a generator of synthetic content and often the product of one |

Plus base doctrine's unconditional set, unchanged: `core.spec`, `core.loader`,
`core.license`, `core.readme`, `core.provenance`.

Optional but expected: `core.model.graph` (see §4, the open problem),
`core.tool.config` for the runtime's canonical invocation, `core.embedding` and
`core.semantics` where they mean anything.

### 1.1 The runtime requirement, stated properly

Law 1 makes a werk package carry a reader for its *container*. `model/1` extends
that one step: the package carries a reader for its *payload* — an executor.

> **A `model/1` package MUST carry, as SOURCE, a complete runtime that produces
> output from the weights it carries, together with the exact build and
> invocation commands, and MUST NOT depend on any runtime it does not carry.**

"Complete" is the word doing the work, and the failure mode is specific and was
hit while building the first such package: the runtime's Windows shim
(`win.h`) *declares* `mmap` and a second file (`win.c`) *defines* it. A package
carrying only `run.c` and `win.h` looks complete, compiles on POSIX, and fails
to link on Windows. **Completeness is measured by building it, on each platform
the package claims, not by counting files.**

### 1.2 The test-vector requirement

> **A `model/1` package MUST carry at least one test vector: a fully specified
> deterministic invocation, its exact expected output as bytes, a hash of those
> bytes, and the environment (OS, CPU, compiler and version, build flags) the
> expectation was measured in.**

Without it "the model runs" is unfalsifiable — a model that reads its weights at
the wrong offsets still emits confident text. With it, a stranger's run is a
measurement. Three things this draft has learned to require of the vector:

* **determinism must be selected explicitly and named.** Here that is
  temperature 0 / greedy argmax. A vector recorded under sampling is not a
  vector.
* **the output must be normalised for line endings before hashing**, and the
  raw form recorded too, so the normalisation is itself checkable. The same
  model computation emits `\n` on POSIX and `\r\n` through a Windows text-mode
  stream, and a package that hashes the raw stdout declares a platform, not a
  result.
* **the vector must say what a MISMATCH means.** Floating-point reassociation
  under vectorising compilers is expected and is not the same failure as reading
  the weights at the wrong offset. A vector that only says "should equal" turns
  a diagnosable divergence into a dead end.

Where the runtime cannot emit the strongest form of the anchor (here: run.c
prints text, not token ids), the package carries the instrumentation that
produced the stronger form — as a diff against its own carried source — rather
than asserting numbers nobody can regenerate.

## 2. Conventions

Profile 1's convention block is 3D-shaped: `up_axis`, `winding`, `quat_order`,
`oct_encoding_pole`, `sh_l1_order`. A language model has no up axis, and a
package that declares one is lying in a schema-validated field. `model/1`
therefore takes the `image/1` route — subtraction — and keeps only the
profile-agnostic set, plus one:

```
endianness            "le"                  const
alignment_bytes       16                    const
text_encoding         "utf-8"               const
id_case               "kebab-case"          const
hash_algorithm        "sha256"              const
signature_algorithm   "ed25519"             const
float_format          "ieee754-binary32"    const     <- new
```

`float_format` is new because it is the one numerical convention a weights
payload actually has, and because the moment a profile admits quantised weights
it becomes a per-node property rather than a package-wide one. Drafting note:
this is probably wrong as a package-wide const and should be per-node
(`meta.dtype`) with the manifest convention reserved for the *activation*
format. Left as a const in the draft so that the first package has something to
declare and the question is visibly open.

## 3. `primary`

Profile 1 offers `primary.mesh`, `.sound`, `.image` and (ruling 22)
`.geometry`. A model package fits none of them, which is finding **S12-7 all
over again** — the same shape of gap, found the same way, by building a package
and discovering it had no slot. `model/1` proposes:

```
primary.weights      node_id of the core.model.weights a consumer should load
primary.tokenizer    node_id of the core.model.tokenizer that goes with it
primary.runtime      node_id of the core.tool to build
primary.testvectors  node_id of the core.model.testvectors to check against
```

Four slots rather than one, because "the thing" in a model package is a
four-part assembly and a consumer that resolves only one of them cannot do
anything at all. This is a genuine departure from profile 1's one-slot-per-kind
shape and it should be argued about rather than adopted quietly.

## 4. The open problem: `core.model.graph`

This draft **does not solve** the interesting half of the problem, and says so
rather than gesturing.

A `core.model.weights` node plus a layout grammar tells a reader where every
number is. It does not tell a reader what the numbers *mean* — the residual
stream, the norm epsilon, the RoPE base, the activation function, the attention
mask. In the first `model/1` package all of that lives in one place: the C
source of the carried runtime. That is *sufficient* (you can read it, and the
test vectors prove you read it right) and it is *not structured* (you cannot
query it, diff it, or check a second runtime against it).

A real `model/1` needs a `core.model.graph`: a declarative description of the
computation, in the same spirit as the layout grammars — every operator named,
every tensor bound to a name in the weights layout, every scalar constant
declared rather than compiled in. That is a substantial design job with real
prior art (ONNX, GGUF's metadata, safetensors' header) and the werk-shaped
version of it has one extra requirement the prior art does not carry: **it must
be checkable against the runtime the package also ships**, or it is a second
statement of the same fact with no way to catch a disagreement — which is the
construction §3.17 and `core.recipe` both exist to avoid.

Until that exists, this draft's honest position is: the runtime source IS the
graph, the package says so, and a reader is told it is reading a program rather
than a specification.

## 5. Where the existing core doctrine does not fit, measured

Five places, all found by building one package. None are fixed here.

1. **`core.recipe` has no `train` role.** The `role` enum is
   `plan|generate|edit|inpaint|upscale|interpolate|transcode|select|convert|ingest|other`
   — a generation vocabulary, written when the model was the *tool*. In a model
   package the model is the *target* and the step that produced it is a training
   run. `other` is the only honest choice today.
2. **`core.recipe`'s hermeticity rule (§3.11) cannot be satisfied by any
   real model package.** "Every input medium a recipe names must be present"
   is right for an image made from a photograph and impossible for weights made
   from a corpus: the training set is orders of magnitude larger than the
   artifact. §3.17's intermediate rule does not cover it either, because no
   embedded tool reproduces a training set. A `model/1` recipe must therefore
   name its corpus in `unrecorded[]` and prose rather than in `inputs[]`, and
   the profile should say so explicitly instead of leaving every author to
   discover that `inputs[]` would be a lie.
3. **`core.disclosure` has one axis where a model package has two.**
   `ai_generated` is a fact about the *content*. A model package's content is a
   model: its weights were produced by gradient descent (not by a generative
   model), and its carried test-vector text was produced by the model itself.
   The first package resolves this with `generation_scope: "partial"` and a
   `scope_note`, which is honest and is clearly the wrong shape. A model
   profile probably wants a distinct statement — "this artifact GENERATES
   synthetic content" — beside "this artifact IS synthetic content".
4. **`core.tool.role` has no slot for an executor.** `viewer` is defined as
   "renders or plays it and produced nothing that is in here", which is nearly
   right and false in the one case that matters: the runtime produced the test
   vectors, which are in here. `creator` is used in the first package for that
   reason, with a note. Neither word is the word.
5. **The weights node type does not exist.** The first package uses
   `x.model.weights` / `x.model.tokenizer` / `x.model.testvectors`, which is
   what the `x.` namespace is for (law 12) and is the correct way to build a
   package under a profile that has not been ruled on. They are written above
   as `core.model.*` because that is what they would become.

## 6. What a `model/1` deliberately does NOT promise

* **Not a runtime standard.** The profile requires *a* working runtime in
  source; it does not standardise one, does not require it to be fast, and
  explicitly leaves optimised executors — vendor kernels, quantised kernels,
  accelerator backends — to the **extension tier** (`x.*`), by design and not by
  omission. Base doctrine's job is that a stranger can get output at all; going
  fast is somebody's product and does not belong in a constitution. An extension
  that adds an optimised backend is a conformant `x.*` node, and a reader that
  has never heard of it skips it and still runs the model.
* **Not a benchmark.** Test vectors check *correctness of execution*, not
  quality. A model/1 package makes no claim about how good the model is.
* **Not a licence launderer.** Three separate licences meet in a model package —
  the runtime's, the weights', and the training corpus's — and §2's licensing
  doctrine (ruling 21) applies unchanged: the format provides the structured
  place, filling it truthfully is the author's job, and the format neither vets
  nor enforces. The first package states all three and states which of them is a
  publisher's assertion rather than a document.

## 7. Status of this draft

Written 2026-08-09 while building the first `model/1-draft` package, as a record
of what that package needed and could not declare. It has not been ruled on, no
implementation depends on it, and the five items in §5 are the agenda.

---

## 8. What the experiment showed — appended 2026-08-09, AFTER the fixture was built

**This section is in the repository copy only.** The copy inside
`gauntlet/roundSR/selfrun-v1.werk` is the build-time revision (12 874 B) and is
deliberately not rebuilt: rebuilding the package to add a paragraph would change
the hash of the artifact the experiment was run against.

The first `model/1-draft` package was handed to two coding agents from two
vendors, each in a fresh directory containing only the file, each given one
sentence and no hints. **Both made the model produce text on the first attempt —
98.2 s and 647.5 s — and both matched the embedded temperature-0 vectors byte
for byte.** Full record: `results/STAGE-SELFRUN-RESULTS.md`.

Four things the run says about this draft:

1. **§0's completeness test is the right test, and it is cheap.** "A competent
   stranger, given the file and nothing else, can make the model produce output
   and check that the output is right" took 98 seconds to evaluate. A profile
   whose completeness clause can be *run* is worth more than one that can only
   be inspected.
2. **§1.2's test-vector requirement is the load-bearing one.** Both agents
   verified unprompted, because the file told them how. Without it "the model
   ran" is unfalsifiable, and both agents would have been right to claim success
   from fluent English alone.
3. **§1.1's "complete runtime" needs BUILD INSTRUCTIONS AS A REQUIRED PART, and
   they must include the failures.** The agent that never found MSVC recovered
   only because the build note recorded, verbatim, the two errors mingw-w64 gcc
   produces and named the two-line fix — and it applied exactly those two fixes
   while leaving the runtime itself byte-identical. A build note that lists only
   what works would have left it stuck. Proposed for the next revision: build
   instructions are a required `files[]` role of the runtime `core.tool`, and
   they must state, per platform, whether the command was **measured** and what
   was measured to **fail**.
4. **§5 item 4 got worse, not better.** `core.tool.config.environment` has five
   interpreter-shaped keys and no compiler field — and the round's own headline
   comparison turned out to be *across two compiler versions producing identical
   output*, which is exactly the fact the format had nowhere to declare.

Neither agent opened the manifest, the specification or a bundled loader, which
is the honest limit on all of the above: this run exercised the profile's
human-facing half and none of its machine-checkable half. The adversarial
follow-up — a damaged self-run package, or one whose weights layout must be
recovered without a README — is what would test §2, §3 and the layout grammars,
and it has not been run.
