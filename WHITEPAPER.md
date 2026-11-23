# `werk` — a file that carries everything it is

**Whitepaper, v1.0 — August 2026**
Gregor Hubert Max Koch

*This is the position document: what `werk` is and why it exists. The
measured study behind it is published open access — **werk: The File That Carries Its Interpreter Through the Ages** (Koch & Puyam, 2026), DOI [10.5281/zenodo.24451043](https://doi.org/10.5281/zenodo.24451043), CC BY 4.0 — and every number cited here is traced to a recorded gate in [`paper/NUMBERS.md`](paper/NUMBERS.md).*

*The format's name is `werk` (German: Werk — a work, an opus); files carry the extension `.werk`. The name is set in typewriter face throughout, to distinguish it from the ordinary German word.*

---

## 1. The problem: files that need a world around them

Open a ten-year-old game asset today. The mesh file references textures
by path — gone. The material references a shader graph in a tool you no
longer own. The rig assumes a skeleton convention nobody wrote down. The
metadata says "made with Tool X 2.3", which tells you nothing you can
act on. The file is technically intact and practically dead.

This is not an accident of one vendor. It is the default outcome of how
asset formats are designed: the file is a *node in a dependency graph*,
and the graph lives outside the file — in a project folder, an engine's
asset registry, a database, someone's head. Unreal's asset system is the
canonical example: powerful inside the project, and a notorious mess the
moment content has to leave it. Every studio that has tried to move a
marketplace pack between projects knows the failure mode; we wrote an
entire production tool just to work around it, and what that tool taught
us is in this format.

Two new pressures make the old default untenable:

**AI systems are now first-class producers and consumers of files.**
A generated asset without its generation record is an orphan: you cannot
reproduce it, audit it, or honestly answer what went into it. And an AI
agent asked to *read* a proprietary format faces the same wall a human
does — documentation that lives somewhere else, if it exists at all.

**Provenance is becoming a legal surface.** The EU AI Act and similar
regimes want synthetic content identified and its origins stated.
Today's answer is watermarks and side-channel manifests — enforcement
bolted on where structure is missing.

`werk`'s answer to both is the same answer: **put everything in the
file.**

## 2. What `werk` is

`werk` is a hermetic, self-describing container format. One `.werk` file
is a store-mode zip holding a directory tree with a single manifest, and
it obeys twelve laws (the full normative text is
[`MANIFESTO.md`](MANIFESTO.md)). The load-bearing ones:

**Hermeticity.** A `werk` file references nothing outside itself. Not a
texture path, not a URL, not an engine asset id. If a payload needs an
input, the input is embedded; if it was too large to embed, its hash is
recorded and the absence is declared. Dependency hell is banned
constitutionally, not managed.

**Self-description.** The specification travels inside the file: the
spec document, JSON Schemas for every structured node, byte-level layout
grammars for every binary, and single-file zero-dependency reader
programs in three languages. The measured claim — and it is measured,
not aspirational — is that a stranger given only the file can write a
correct loader. Strangers have. Repeatedly. (§6.)

**Islands and graceful degradation.** Content lives in nodes with
declared edges. A node your reader doesn't understand, or one that
arrives damaged, is skipped *and reported* — everything else loads. A
damaged fixture is part of the test suite: the required behavior on
corruption is exact, down to the report codes.

**Provenance with epistemic status.** Every node version records who
made it, from what inputs (by hash), and whether the content is
*authored*, *measured*, or *inferred*. A vision model's guess about a
material is recorded as a guess. In one of our own fixtures the model
confidently called a metal street lamp "oak wood" — and the file says
exactly that, stamped `inferred`, confidence included. The format
records what was claimed; it does not launder claims into facts.

**In-file versions with work notes.** A node can carry several versions
of itself, with a mandatory human-readable note per version and an
`active` pointer. "The skin update broke the hand posing" is a
five-second check against the previous version in the *same file* — no
external history needed.

**Signature chain, three-state.** An Ed25519 chain over the manifest
yields *valid*, *absent*, or *invalid* — and readers that cannot do the
curve math report the honest fourth word, *unverified*, rather than
guessing. Absence is legal. Absence is also a signal.

**Conventions as numbers.** Units, axes, handedness, quaternion order,
color spaces, spherical-harmonic ordering — all declared as
machine-checked values in the manifest. A reader that cannot honor them
must refuse rather than silently transform wrong.

## 3. What a `werk` file holds

The first profile is the **3D entity**: source and game meshes, LOD
chains, PBR materials and textures, octahedral imposters (which double
as the asset browser's preview — the low-bandwidth view is *in the
file*), convex colliders, mass and inertia, settled rest poses, flow
fields, a quaternion skeleton with a canonical humanoid and
one-calibration-pose retargeting, sampled animation with event tracks,
a complete sound-effect package with takes and timings, damage and
destruction data, VLM-evaluated simulation properties, and semantic
facets — tags, a style embedding, a palette — that make
"select this crate, show me everything else that fits #sci-fi #corridor"
a filter over data the assets brought with them.

The second profile is the **image**, built for the AI-generation era:
the image plus its complete recipe — models by weight hash, prompts,
seeds, samplers, embedded pipeline graphs, all input media by hash —
with a declared reproducibility grade, and a machine-readable disclosure
block stating what is synthetic.

Stage 12 added **point clouds and Gaussian splats** as first-class
payloads, with every historically ambiguous detail (SH coefficient
order, scale and opacity spaces, quaternion order) pinned in the layout
grammar, and a normative degradation path: a reader that only
understands points renders the splat's DC band as a colored point
cloud.

And a `werk` file can embed **the tools themselves**: the source code and
configuration of the programs that created or converted its content,
under the same safety doctrine as the bootstrap readers — source always,
prebuilt binaries opt-in, signed, and never auto-executed. Our splat
fixture demonstrates the endpoint of this idea: run the tools embedded
in the file on the input embedded in the file, in an empty directory,
and the payload regenerates **byte-identically**. The file carries the
code that made it, and that code provably still works.

## 4. The structured canvas

`werk` ships facts and enforces nothing. This is a design decision, stated
normatively in the spec, and it cuts both ways:

- The **disclosure** block carries synthetic-content facts. What a
  viewer does with them is the viewer's responsibility under the
  viewer's local law — the format contains no locks, no DRM, no
  mandatory behavior. Anyone with a compiler may write a viewer that
  ignores every disclosure. That freedom is intentional. A format that
  tried to enforce policy would be forked into one that doesn't within
  a month, and would deserve it.
- The **license** section works the same way. The format offers a
  structured place for license facts; filling it truthfully is the
  author's and their tooling's responsibility. The format neither vets
  nor enforces content licensing. It is a structured canvas — the rest
  is up to everybody else.
- The only MUST-level demands are about honest *reading and reporting*:
  a conformant reader does not misrepresent what the file says.

This is how `werk` is "EU AI Act ready" without containing a single line
of enforcement: the data a regulator wants is present, structured, and
signed — and the format's integrity does not depend on anyone's
jurisdiction.

## 5. Redundancy is the store's problem, not the file's

Hermetic files duplicate data — that is the point, and it has a cost.
`werk` pays that cost in the right place: **werkstore**, a version control
system designed for this format rather than adapted to it.
Content-addressed storage dedups identical payloads across files and
versions; content-defined chunking dedups *within* large payloads
(measured: a 4 KiB edit inside a 5 MiB texture costs 0.31 MiB of new
storage and 3.6 % of the file in sync transfer); materialization is
byte-exact, verified against the manifest hashes every time; sync moves
nodes, not files. The store is specified to the byte — a foreign
implementation can reproduce its chunk boundaries — and a store is
never required: the `.werk` file alone is always complete.

## 6. Proof, not promises

Every claim above is gated by a measurement, and the project's house
rule is that nothing advances on assertion. Highlights, all reproduced
in the repository's test harnesses with fixture hashes pinned:

| claim | measurement |
|---|---|
| a stranger can implement the format from the file alone | 6/6 fresh agents (Python, JS, Rust, C ×2 rounds) wrote working loaders, file-only (round 1's four: median ~11 min); 0 of them needed the bundled readers |
| self-description reaches the byte level | an agent reimplemented the style-embedding descriptor from the in-file grammar and recomputed it from the source pixels **bit-exactly**; another built Ed25519 verification from the embedded mini-spec |
| engines consume it without cooking | CUB loads the cooked extension tier 3.7× faster than parsing GLB; Blender round-trips rigs to 8.4e-8 rad; Unreal imports, exports, and round-trips textures pixel-identically; three implementations in three languages agree on the spec-hash digest byte-for-byte |
| graceful degradation is exact | damaged fixtures produce the same skip reports across four independent readers, down to the node id |
| retargeting from one calibration pose | three foreign rigs (glTF, UE mannequin, raw mocap) retarget at 5e-8…9e-8 rad against a 1e-4 tolerance; unit scale recovered from bone directions alone |
| the file can rebuild itself | the splat fixture's embedded tools regenerate its payload byte-identically in a clean directory |
| enrichment is unattended | bare GLB → 30+-node enriched `werk` with all 78 derived-node input hashes recomputing from the package's own bytes |

The deeper result is methodological: **agent-implementability is a
measurable format-quality metric.** Every gauntlet failure became a spec
fix with a ledger entry, not an excuse — the specification was debugged
the way code is. The scientific paper formalizes this; the ledger of
findings (S-1 through S12-9 and counting) is in the repository, none of
them erased.

## 7. What `werk` is not

- **Not a runtime or an engine.** Engines keep their native fast paths —
  as extension namespaces (`x.cub.*`, and whatever yours is called)
  that other readers skip losslessly. Extension is designed in; core
  stays boring.
- **Not a scene description.** USD composes scenes; `werk` carries
  entities. A `werk` file is closer to "a shipping container for one
  thing and everything true about it" than to a stage.
- **Not a rights-management system.** See §4. It will not lock, phone
  home, or refuse. Ever.
- **Not clever.** Store-mode zip, JSON, PNG, WAV, GLB, flat binary
  streams with declared offsets. Every encoding choice is the boring
  one, because boring is what survives.

## 8. Status

The reference implementation is one Rust core compiled to a single
`werk.dll` with a C ABI — C++ consumes the header, Python binds over
ctypes, zero package-manager dependencies anywhere. Adapters exist and
are gated for Blender (4.x add-on), Unreal Engine 5.7 (WerkLink plugin,
import and closure-walking export), and the CUB engine. An unattended
enrichment pipeline turns a bare GLB into a fully-loaded entity. The
agent gauntlet, the damage gauntlet, and every adapter gate run today,
green, with pinned fixtures.

The philosophy is not limited to 3D. Any file type that suffers from
external dependencies and vanishing context — video projects, documents,
datasets — can be a `werk` profile. The laws don't care what the payload
is.

The format stays open and clean. The rest is up to everybody else.

---

*Specification, schemas, reference implementation, fixtures, test
harnesses, the finding ledger, and the scientific paper are in the `werk`
repository. Contact: Gregor Koch.*
