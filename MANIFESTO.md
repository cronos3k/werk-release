# The werk Manifesto

**Self-carrying digital artifacts**

Version 0.1 — July 2026
Gregor Hubert Max Koch · Ken Gamble
License: CC BY-SA 4.0 (this document); the format itself is an open specification.

---

## Preamble

A digital artifact should bring all its logic along for a consumer to use,
rather than to set up painfully after the fact.

Today's files are promises: a mesh promises materials it doesn't carry, an
engine asset promises fifty sibling files, a document promises fonts, a video
promises codecs, and every one of them promises a *program* — some specific
application, at some specific version, on some specific machine — without
which the bytes are noise. The knowledge needed to use a file lives everywhere
except inside it.

werk inverts this. A werk file is **hermetic** (it contains everything it
needs), **self-describing** (it contains the knowledge required to read it),
**self-historied** (it contains its own versions and the reasons for them),
and **self-attributed** (it contains its authorship, cryptographically).
It is not a file format so much as a doctrine for building file formats —
this document defines the laws; concrete **profiles** (a 3D entity, a video,
a document, a dataset) instantiate them.

The test of the doctrine is not elegance. It is this: *an isolated
intelligence — human or machine — given a werk file and nothing else, can
write a working reader for it.* Agent-implementability is the quality metric.

---

## The Laws

### 1. Hermeticity

**A werk answers every question it raises.** No external references. No
companion files. No "also download." If a node needs a texture, a font, a
schema, a license text, a spec — it is in the payload. The dependency-hell
failure mode (a file that is secretly a promise about other files) is banned
at the constitutional level, not discouraged at the style level.

Redundancy between files is real and is *not* this format's problem. It is
the problem of the companion version control system (see: The Companion),
which dedups content-addressed storage *at rest* while every materialized
werk remains complete. Working copies are whole; the store is clever. Never
the reverse.

### 2. Self-description

The knowledge to read the file travels inside the file, in three layers:

1. **`SPEC.md`** — the narrative specification of this profile, readable by
   a human or agent with no prior context.
2. **Schemas** — machine-checkable definitions (JSON Schema) for every
   structured node, themselves stored as plain data.
3. **Layout grammars** — for every custom binary payload, a plain-text
   layout file (`*.layout.txt`) declaring endianness, alignment, offsets,
   types, counts and field semantics, precise enough to write a parser from
   scratch.

Where a ubiquitous, boring encoding exists (PNG, WAV, GLB, JSON, plain
text), use it — and still include its one-page mini-spec, so the guarantee
holds literally. Custom binaries are permitted only where no boring standard
exists, and always with their grammar beside them.

### 3. Islands and graceful degradation

**Every node is an island.** Self-contained, meaningful alone, never
reaching into another node's bytes. Cross-references are by identity through
the manifest only.

Edges are typed **`requires`** or **`enhances`**, and almost everything is
`enhances`. A reader that cannot parse one node loses one feature — never
the file. Corruption is quarantined per node (hash mismatch → mark dead,
log, continue). Unknown-because-newer and unreadable-because-broken degrade
through the same code path. The minimum viable artifact is tiny; everything
above it is enrichment; every rung of the degradation ladder still loads.

### 4. Identity over indices

Every entity, node, part and material carries a **stable id**. Ids survive
re-export; indices rot. The entity itself carries a UUID — not to reference
outward (Law 1 forbids it) but so that two hermetic copies of the same
entity are *recognizable* as the same, by tools, by engines instancing at
runtime, and by the store.

### 5. Provenance and epistemic status

Every derived node records **who made it** (tool, model, version), **from
what** (input content hashes), and **how sure we are** (`authored` /
`measured` / `inferred` + confidence). An inferred value is useful *because*
it is labeled inferred — never laundered into fact. Authored beats inferred.

Every precomputed node carries the **hash of its inputs**: a consumer
validates-or-recomputes rather than trusts. Stale derived data is
detectable, always, from the file alone.

### 6. Versions live in the file

A node may hold **multiple coexisting versions**, append-only, with one
`active` pointer as the author's recommendation — not a command. Consumers
may select any version. A regression is fixed by pointing back, in seconds,
without a second file.

Every version carries a mandatory **work note**: one sentence of why it
exists. Notes are payload, not tooling metadata — the artifact carries its
own reasoning. Old versions are never rewritten; **compaction is an
explicit, signed, logged choice**, never silent housekeeping.

### 7. The signature chain

Authorship is cryptographic. `SIGNATURE.json` holds an append-only chain:
each signer (human and producing agent both, identified by name and
resolvable URI) signs the manifest hash — and the manifest hashes every
file, so a signature covers the entire package state transitively.
Enrichment appends; it never overwrites earlier custody.

The three-state doctrine, surfaced by conformant tools:
**signed-and-valid** (verified) · **absent** (anonymous, by choice or by
stripping — nothing breaks, but the absence is visible) · **present-and-
invalid** (tampering under an existing signature — the state that catches
bad actors). The format cannot prevent plagiarism; it makes clean provenance
the cheapest path and its absence conspicuous. The license travels as full
embedded text, never as a link.

### 8. Conventions are declared numerically

Units, coordinate handedness, up and forward axes, color spaces per texture,
quaternion component order, encoding pole axes, basis orderings, endianness,
alignment — all declared **as machine-checkable values in the manifest**,
never as prose, never as an application's implicit assumption, never as an
advisory string a reader may ignore. Canonical poses are numbers, not words.

Corollary, learned from the field: **every offset and size is declared in
the manifest; a reader never computes them from a struct definition.**
Comments lie; declared offsets are testable.

### 9. Every payload serves at least two masters

Precomputed data must earn its bytes twice: once for the runtime, once for
the tooling around the artifact's life. Preview renders are also LOD
billboards. Descriptions are also the search index. Audio is also the hover
preview. Version notes are also the changelog. The manifest alone renders a
browser listing.

Corollary: the **preview-first byte layout** — manifest and preview-tier
nodes physically first in the container, so a store or browser can display,
search, audition and trust-check a multi-gigabyte artifact from its first
few hundred kilobytes.

### 10. Agent-first, measured

The format is designed to be implemented by an isolated intelligence from
the payload alone — and this is **tested, not asserted**: conformance
includes handing the file (and nothing else) to fresh agents who must
produce working readers, and handing them deliberately damaged files that
must degrade gracefully. A format change that lowers agent-implementability
is a regression, whatever else it improves.

### 11. Boring encodings

Flat POD arrays. Explicit strides. Little-endian. Magic + version + header
length + self-describing header + raw payload, so a node can be inspected
without inflation and sliced without parsing. No varints, no clever
packing in core, no compression that a stdlib cannot open. Cleverness is
the extension namespace's privilege and the core's forbidden fruit.

### 12. Extension without breakage

Namespaced node types: `core.*` is the profile's constitution; `x.*` is
open frontier. Readers ignore what they don't know (Law 3 makes this free).
Evolution within a major version is additive-only. An engine may ship its
own cooked payloads (`x.cub.*`) beside the universal core — and every other
consumer skips them gracefully, which is not a compromise but the system
working as designed.

---

## Genericity: one doctrine, many profiles

The laws above mention no triangles. They apply to any artifact class:

| Concept | 3D entity | Video | Document | Dataset |
|---|---|---|---|---|
| Source of truth | high-poly mesh | camera master | canonical content | raw captures |
| Derived representations | LODs, game mesh | proxies, transcodes | print/web renders | splits, features |
| Preview tier | imposter atlas | poster + strip | first page | sample rows |
| Semantic enrichment | materials, tags, properties | shot list, transcript | outline, entities | schema, stats |
| Modality enrichment | sound world | subtitles, dubs | narration | embeddings |
| Versions-in-file | skin@1, skin@2 | three grades | revisions | dataset versions |
| Custody | author + pipeline chain | crew + post chain | authorship chain | collection chain |

A werk profile for each class chooses its node families; the laws are
invariant. The first profile is the 3D entity (`SPEC-3D-ENTITY.md`); its
first consumer and proving ground is the CUB engine — which consumes the
universal core *and* its own `x.cub.*` cooked tier, testing constitution
and frontier at once.

---

## The Companion: the store is a cache, never the truth

Stage two is a format-aware version control system, designed against these
constraints, in this order of authority:

1. **The materialized werk is truth.** The store dedups, transfers, and
   remembers — it never becomes authoritative. Materialization from the
   store is byte-exact and verified against the signed manifest, or it
   failed.
2. **Content addressing is shared.** The manifest's per-file sha256 *is*
   the store key. No translation layer.
3. **Diff is manifest-aware.** The unit of change is the node version, not
   the byte range; the changelog is the work notes, already written,
   already signed.
4. **Sync is node-version-granular**: have/want negotiation over hashes,
   transferring only missing objects, resumable.
5. **Cross-package redundancy** (chunking, packing, delta) lives here and
   only here — the format stays dumb and complete; the store gets to be
   clever.
6. **GC is multi-rooted and pin-aware**, with integrity scrub; a store that
   cannot verify every blob rehashes to its name is broken.

---

## Coda

Formats die when their knowledge dies. The applications rot, the wikis
vanish, the one engineer who knew the quirks retires — and the bytes remain,
mute. A werk file is designed to outlive its tools: it explains itself,
proves itself, remembers its own history, and credits its own makers.

The file is the format. The file is the documentation. The file is the
archive. **The file is enough.**
