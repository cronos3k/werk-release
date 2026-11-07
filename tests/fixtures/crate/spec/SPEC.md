# werk Profile 1: 3D Entity — SPEC v0.1

Status: **Stage 1 complete; the six spec rulings of 2026-08-08 applied.** Every item the draft marked ⛏ now has its
schema or layout file authored, and every one of those files travels in
`spec/` inside the package. The manifesto's laws govern everything here;
where this spec is silent, the laws decide. Where this spec and a specific
`spec/layouts/*.layout.txt` disagree about a byte, the layout file wins for
that payload kind.

Open items are listed honestly in §11 rather than hidden behind a pickaxe.

**Two things in this document are not profile-1 material and say so where they
appear.** §3.11 (`core.recipe`), §3.12 (`core.disclosure`) and §3.13
(`core.embedding`) are **base doctrine**: they belong to every werk profile,
they are instantiated by profile 2 (`spec/PROFILE-IMAGE.md`) exactly as they
are here, and they live in this file only because this is where the narrative
spec lives. When a third profile arrives they move to a document of their own
and nothing about them changes.

**The four `PROPOSED — draft-pending-Gregor` rulings are now RULED.**
`docs/RULINGS-2026-08-08.md` in the source repository is the canonical record;
the rules themselves are stated in place below and no longer carry a marker.
Two of them were ruled *weaker* than the draft proposed, and that matters to
anyone who implemented against the draft:

| id | where | ruled |
|---|---|---|
| **S-14** `container.entry_order` | §1 | **SHOULD, not MUST.** Readers never depend on entry order; writers SHOULD write preview-first. |
| **S-15** `preview_prefix_bytes` | §1 | **A HINT.** Approximate, declared-not-guaranteed; a reader MUST NOT treat it as exact. |
| **S-17** convention → node map | §10.1 | **Adopted**, and extended: the map is *declared* by the package (§10.2), and §12 adds the recovery procedure for when it is damaged. |
| **S-18** one `files[]` | §2 | **Adopted**, reworded: a node has *at least one version and exactly one active version*, and version numbers are **incremental integers**, never semver. |

Five further rulings of the same date are implemented here and named where
they land: **S-29** → `spec_sha256` (§2), **S-30** → `total_size_bytes`
promoted into §2, **S10-1** → `schemas` may be empty (§2), **S10-3** →
`core.phys.body` is model space (§3.7a), **S6-2/S6-4** → `core.retarget.bind`
(§3.14) and optional translation tracks in `core.anim.clip` (§3.4).

**Nine entries of 2026-10-13 are IMPLEMENTED in this revision and PROPOSED —
pending Gregor's ruling.** They came out of the first time applications
outside this repository — ten of them, through writers in three languages —
wrote werk files, most in profiles this repository had never seen, and each
answers a measured failure recorded in
`docs/RULINGS-2026-10-13.md` in the source repository. They are marked
"ruling *N* of 2026-10-13, PROPOSED" where they land. Every one is additive
within major version 1 (law 12): every package written before them verifies
unchanged, and that was measured on the pinned fixtures rather than assumed.

| # | what | where |
|---|---|---|
| 1 | **Format definitions** are base doctrine: a foreign-encoded payload is a legitimate core payload when its definition travels in the package. `formats` in the manifest, `payload_format` / `file_formats` / `contained_formats` on a node. Also adopted as base doctrine: the document revision log `core.revisions` | §2, §3.18, §3.19 |
| 2 | **Any profile, not two.** The manifest's schema is named inside the package and validated from the package; a reader holds a base schema of its own; profile-defined node types degrade through the skip path; what all that does and does not establish is stated | §2, §2.2, §10 steps 2–3, §10.3 |
| 3 | **Writing** is normative: a walkthrough with a hash-checkable worked example for each reference profile | §14, `WRITING-3D-ENTITY.md`, `PROFILE-IMAGE.md` §10, `WRITING-IMAGE.md` |
| 4 | **Envelopes are recognised by their frame**, and their grammar is found through the header's `kind` and the `layouts` map — not through a table of magics | §3.1, §12.2, `layouts/ENVELOPE.layout.txt` §2 |
| 5 | **Scene state** of a 3D entity: reflections in a part's scale, a versioned `core.scene` node for visibility, opacity and tint, and `meta.modified_by` for what stays in an extension | §3.20 |
| 6 | **The `@N` marker** goes on the superseded file | §5 |
| 7 | **A package carried as a payload** of another | §13 |
| 8 | Four inconsistencies inside the reference, fixed with a test each | `docs/RULINGS-2026-10-13.md` |
| 9 | **Deflate is read; zip64 is refused, uniformly and by name**; exit statuses agree across the reference readers | §1, §10.1, `MINI-SPECS.md` §5.5, §7.1 |

---

## 1. Container

A werk 3D entity is a **directory tree**; the interchange form is that tree
zipped, extension `.werk`. Directory and zip layouts are identical. Both are
the format.

**Compression: store by default.** A conformant writer emits zip method 0
(store) unless the author asks otherwise, and every conformance fixture is
store-mode. The reason is bootstrap cost: a zero-dependency zip reader is
about a hundred lines in any language *without* an inflate implementation,
and inflate is several hundred more. The payloads that dominate a package's
size — PNG, WAV, GLB — are already internally compressed, so deflating the
container buys single-digit percentages on the bytes that matter. Cross-file
redundancy is the companion store's job (see the manifesto's *Companion*
section), not the format's. Method 8 (deflate) remains legal and a reader
SHOULD support it, but a reader that supports only store mode is conformant
against the store-mode fixtures and must say so rather than return wrong bytes.
`MANIFEST.json` → `container.zip_compression` declares which was used.

**Deflate is read by every reference reader — ruling 9 of 2026-10-13,
PROPOSED.** Until then "a reader SHOULD support it" was true of no reader in
this repository: the reference core and all three bootstrap loaders refused a
method-8 entry, and the core did so under the wrong name (`file-missing`,
while the code it had defined for the purpose, `zip-entry-unsupported`, was
never emitted). The bitstream is now defined in `MINI-SPECS.md` §7.1 with test
vectors, all four readers implement it from that text, and
`fixtures/crate-cc0-lean-v1-deflated.werk` — written by an unrelated encoder —
is the fixture that exercises them. A reader hands inflated bytes over only
after checking them against the directory's size and CRC-32; a stream that
does not decode is damage to that entry (`zip-entry-invalid`, node scope).
**Writers are unaffected: store stays the default and stays what every
conformance fixture but that one uses.** Any method other than 0 and 8, and an
encrypted entry, is refused for that entry by name (`zip-entry-unsupported`).

**werk does not use zip64 — same ruling.** A single-file package is a 32-bit
zip: every entry and the whole file below 4 GiB, at most 65 534 entries. A
package past that is carried in **directory form**, which §1's first sentence
already makes the same format, and which has no ceiling. A reader that meets a
zip64 container refuses it whole, by name (`zip64-unsupported`), with exit
status 2, having read nothing but the container's last 64 KiB — `MINI-SPECS.md`
§5.5 says how it is recognised, and that part is mandatory for every reader.

**Preview-first byte layout (law 9) — SHOULD, S-14, RULING, implemented.**
When zipping, a writer **SHOULD** write entries in this physical order:
`MANIFEST.json`, `SIGNATURE.json`, `LICENSE`, `loaders/`, `spec/`,
`semantics/`, `imposters/` (preview tier first), one preview one-shot from
`audio/`, then everything else. A ranged read of the first bytes then yields a
browsable, searchable, auditable listing — and, because `loaders/` is in that
prefix, a reader with which to browse it.
`container.preview_prefix_bytes` declares roughly how many leading bytes that
is.

It is a SHOULD and not a MUST, and that is the ruling rather than a softening:
**readers never depend on entry order.** A package written in any order at all
is fully conformant and every conformant reader loads it identically; what a
badly-ordered package loses is the cheap ranged read, which is a store's
optimisation and never a correctness property. A writer that cannot control
its zip's entry order — several can't — is still a conformant writer.

**`container.entry_order`: how an element is matched — S-14, RULING,
implemented.** The array mixes exact paths and directory prefixes and nothing
marked which was which; every implementation resolved it the same way by
inspection, so the ruling only writes down what is already true:

> An element ending in `/` is a **directory prefix** and matches every entry
> beneath it. Anything else is an **exact path**. Matching is two-pass —
> every exact path first, then the prefixes — so an exact entry listed
> *between* two prefixes lands where it is listed instead of being swallowed
> by the prefix above it.

Order affects only how early the browsable tier appears. It never affects
correctness, and a reader that ignores `entry_order` entirely is conformant.

**`container.preview_prefix_bytes` is a HINT — S-15, RULING, implemented.**
The field used to have no defined endpoint, and `entry_order` could not supply
one because it lists every bucket in the package rather than only the
browsable ones — the golden fixture's list ends in `x/`, i.e. the whole
archive. The endpoint is now defined, **and the number is declared, not
guaranteed**:

> `preview_prefix_bytes` is an **approximate** byte offset of the end of the
> last container entry belonging to the preview tier, measured from the start
> of the zip. The preview tier is named explicitly by
> `container.preview_tier`; where that key is absent, this profile's default
> tier is `MANIFEST.json`, `SIGNATURE.json`, `LICENSE`, `README.txt`,
> `loaders/`, `spec/`, `semantics/`, `imposters/`, and the one entry named by
> `primary.sound`. A writer **SHOULD** emit the recomputed number rather than
> an estimate. **A reader MUST NOT treat it as exact**: it MUST NOT compute a
> range request from it without checking what it actually received, MUST NOT
> report a disagreement as damage, and MUST NOT refuse a package because the
> two disagree. Cut short, fetch more; cut long, you fetched some bytes you
> did not need.

The reason it is a hint and not the checkable assertion the draft proposed is
S10-2, measured: the field is a measurement *of the container that contains
it*, so writing the number changes `MANIFEST.json`'s length, which moves every
later entry, which changes the measurement. Every werk writer in this
repository iterates it to a fixed point and every one converges — but "measure,
then write the measurement" does not terminate on its own, and a MUST that a
correct writer can fail to satisfy for arithmetic reasons is a MUST in the
wrong place. A conformance harness therefore recomputes the value and
**reports** the difference; only a writer's own gate may treat a non-zero
difference as a failure.

```
entity.werk/
├─ MANIFEST.json          the graph, hashes, conventions, versions
├─ SIGNATURE.json         signature chain (may be absent — three-state)
├─ LICENSE                full license text, embedded
├─ README.txt             one paragraph for humans
├─ loaders/               single-file zero-dependency readers (§7)
├─ spec/                  ← the format travels with the file (law 2)
│  ├─ README.md           index: which file answers which question
│  ├─ SPEC.md             this document (the version the file conforms to)
│  ├─ MINI-SPECS.md       PNG, WAV, GLB, JSON, zip, and the rest, in full
│  ├─ schemas/*.json      JSON Schema per structured node type
│  ├─ layouts/*.layout.txt  grammar per custom binary
│  ├─ facets.json         the semantic tag registry (versioned)
│  ├─ skeleton/           the canonical humanoid + hands, numeric
│  └─ examples/           a valid manifest, a real binary, an annotated dump
├─ geometry/              source-hi, game, lod1..4 (GLB)
├─ textures/              PNG (color space declared per texture)
├─ materials/             PBR parameter JSON per material id
├─ imposters/             octahedral atlases, 2 tiers, G-buffer channels
├─ physics/               colliders, bounds, mass/CoM/inertia, regions
├─ fields/                flow field grid (bin + layout)
├─ poses/                 settled rest orientations (bin + layout)
├─ skeleton/              this entity's rig, if it has one
├─ animation/             sampled clips + event tracks
├─ audio/                 the splat-foley package schema, verbatim
├─ destruction/           fracture sets, thresholds, debris mapping
├─ properties/            VLM-inferred sim properties per region
├─ semantics/             facet tags, style embedding, palette
├─ provenance/            producers, inputs, costs, conjure prompts
└─ x/                     extension namespaces (e.g. x/cub/ cooked tier)
```

## 2. MANIFEST.json

Single source of structure. Schema: **`spec/schemas/manifest.schema.json`**.

- `werk`: `{major, minor}` as numbers; `profile`: `"3d-entity/1"`.
- `manifest_schema` (optional): the path, **inside this package**, of the
  schema that validates this manifest. It exists because there is now more
  than one profile (`image/1` is `spec/schemas/manifest.image.schema.json`),
  and "which schema validates the manifest" had until then been answered by
  knowing — which is precisely what law 8's corollary forbids, since deriving
  a filename from a profile string is deriving. Absent means
  `spec/schemas/manifest.schema.json`, which is what every package written
  before the key existed means. **For any profile other than the two reference
  profiles the key is MANDATORY** — nothing else says where that profile's
  schema is — and §2.2 says what a reader does with it.
- `profile_spec` (optional; ruling 2 of 2026-10-13, PROPOSED): the path,
  inside this package, of the profile's **narrative** specification — the
  document a reader starts with and the one that carries the normative
  "Writing a minimal valid package" section. Declared for the same reason
  `manifest_schema` is. Absent means this document for `3d-entity/1` and
  `spec/PROFILE-IMAGE.md` for `image/1`.
- `entity`: `{uuid, name, summary}` — identity for recognition, never for
  external reference (laws 1, 4).
- `conventions` (law 8), machine-checked, all mandatory:
  `{endianness:"le", units_per_meter:1.0, length_unit:"metre",
  angle_unit:"radian", time_unit:"second", mass_unit:"kilogram",
  up_axis:"y", forward_axis:"-z", right_axis:"+x", handedness:"right",
  winding:"ccw", quat_order:"wxyz", oct_encoding_pole:"y",
  sh_l1_order:["dc","y","z","x"], color_space_default:"srgb",
  uv_origin:"top-left", alignment_bytes:16, text_encoding:"utf-8",
  id_case:"kebab-case", hash_algorithm:"sha256",
  signature_algorithm:"ed25519"}` — readers MUST verify they support these
  values before consuming payloads, and MUST refuse silently-wrong instead
  of guessing. The schema pins each to a `const`, so "does this reader
  support it" is a validation result, not a judgement call.
- `container`: `{form, zip_compression, entry_order, preview_prefix_bytes?,
  preview_tier?, total_size_bytes?}`.

  **`total_size_bytes` — S-30, RULING, implemented; the definition lives
  here.** It is the sum of the `size` fields of every **distinct path**
  declared in `nodes[].versions[].files[]`: payload bytes only, excluding
  `MANIFEST.json`, `SIGNATURE.json` and all container framing, so it is the
  same number in the directory form and in the zip. **A path listed by several
  versions of one node counts once** — the S-18 reading of what a file belongs
  to, applied arithmetically. It exists so a store can size a fetch before
  parsing the graph, it is optional, and it is advisory: a reader that needs
  the number computes it. The field previously had a definition only inside a
  schema `description`, and a gauntlet reader lost minutes to it *after* that
  fix, then called it "a documented spec bug that was documented rather than
  fixed". A definition a reader must find by opening a schema is a definition
  in the wrong file; container semantics belong in the container section.

  `form` is **advisory and frozen at authoring time** — it records the form
  the package was written in when it was last signed, not the form you are
  holding. §1 says directory and zip are identical and both are the format;
  §6 says the signature covers the manifest's exact bytes. Both cannot be
  true if a reader is expected to "correct" `form` on unzip, so it does not:
  a mismatch is an informational note, never damage and never a rewrite.
- `primary` (optional): `{mesh?, geometry?, sound?, image?}`, each a
  `node_id` — which
  node to reach for when a consumer wants exactly **one** of something. A
  runtime asking "give me the mesh" and a store's browser listing asking
  "what do I show and what do I play" are the same question (law 9), and
  before this block existed both had to guess. **Fallback when it is
  absent**, so a reader is never stuck: the mesh is the `core.geom.game`
  node — never a `core.geom.lod`, and never `core.geom.source`, which is the
  archival anchor and may lack the attributes a renderer needs (§3.10); the
  sound is the `core.audio.package`'s `preview_effect` slug resolved to its
  effect node, and failing that the first `core.audio.effect` in `nodes[]`;
  the image is the lowest-numbered imposter tier, and failing that any
  `core.tex` with `usage: "base-color"`. A reader MUST report that it fell
  back. Where `primary` is present it wins, because a declared value beats an
  inference every time.

  **`primary` names a NODE, and a node may hold several files.** Following
  `primary.sound` to its node is only half the journey; §2.1 is the other
  half and is normative. A consumer MUST resolve the node's payload by §2.1's
  ordered rules — `payload_file` first — and **MUST NOT take `files[0]`**. A
  `core.audio.effect`'s `files[]` begins with its `descriptor`, and an
  implementer that took the first entry shipped the JSON as the sound while
  reporting success (S-OW-2, measured).

  **`geometry` — S12-7, RULING, implemented.** The type-agnostic slot: the
  `node_id` of any `core.geom.*` node, for the package whose one geometry is
  not a mesh. `mesh` offered mesh, sound and image offered themselves, and a
  Gaussian splat or a point cloud is none of the three — so before this key
  existed, a splat package's only honest move was to omit `primary` entirely
  and leave the reader a documented fallback ("the `core.geom.game` node")
  that finds nothing in a package that has no mesh. Putting a splat in
  `primary.mesh` would be calling it a mesh; `primary: {}` would look
  declared while declaring nothing. `mesh` is kept as the narrower existing
  key and still means a mesh; in a package whose primary geometry IS a mesh
  the two keys, where both appear, name the same node, and a reader that
  finds them disagreeing in such a package reports the disagreement rather
  than picking one. Splat and point-cloud packages get a primary key like
  everyone else — the `gsplat-v1` fixture declares
  `primary: {geometry: "gsplat"}`.
- `license`: `{spdx_id?, file:"LICENSE", sha256}` — full text, never a link.

  **The licensing doctrine — S12-9, RULING, the licence-side twin of §3.12's
  no-enforcement doctrine.** The format provides the structured place for
  licence facts — an embedded `LICENSE` whose exact bytes are hashed here,
  listed in the manifest and covered by the signature chain like every other
  file — and that is ALL it provides. Filling that place truthfully is the
  responsibility of the author and of the tool or export implementation that
  wrote the package; **the format neither vets nor enforces content
  licensing.** No conformance clause in this spec turns on what the licence
  text *says*: a package whose `LICENSE` honestly states that its content's
  terms are not established is exactly as conformant as one under CC0, and a
  validator that rejected the first would be enforcing a policy the format
  does not contain. What the format does guarantee is the same thing §3.12
  guarantees a disclosure: the text cannot be swapped or stripped silently,
  because the manifest hashes it and the chain signs the manifest.
  Honest-but-unknown beats invented-and-clean — `pipeline/package.py`'s
  licence-unknown notice is that sentence as code, and the `gsplat-v1`
  fixture ships it applied to a real case.
- `schemas`: node type → path of its JSON Schema **inside this package**.
  **It maps only the node types actually present that have a schema, and an
  empty map is a conformant answer — S10-1, RULING, implemented.** A package
  holding only `core.geom.*`, `core.license`, `core.readme`, `core.spec` and
  `core.loader` nodes has no schema-bearing node type at all, and `{}` is then
  the truthful map rather than a defect. This was measured, not theorised: a
  mesh-only export was rejected by a validator for an empty `schemas` and
  validated with zero errors the moment one audio node was added, which is a
  schema punishing a package for being small.
- `layouts`: node type → path of its layout grammar inside this package. Same
  rule: only the types present that have one; empty is conformant.
  Both maps exist so a reader never derives a path from a filename
  convention.
- `formats` (optional; ruling 1 of 2026-10-13, PROPOSED): **format id** → path
  of that format's **definition document** inside this package. The third map
  of the same kind: `schemas` describes JSON payloads, `layouts` describes
  werk's own binaries, `formats` describes every *other* encoding a file of
  the package is in — a JPEG, a font, a camera raw file. It lists the formats
  the package's nodes name and the definitions those build on; it is absent or
  `{}` when no node names one. §3.18 is the whole mechanism.
- **`spec_sha256` — MANDATORY, S-29, RULING, implemented.** One lowercase-hex
  sha256 over the `spec/` tree **this package carries**, so a reader can tell
  in one comparison whether the schemas travelling inside the file are the
  ones it already knows. Vendoring `spec/` is structural for every writer in
  every language — a Blender add-on installed from a zip onto a machine that
  has never seen the source repository cannot ship a path, it has to ship
  bytes — and until this field existed nothing said *which* revision those
  bytes were, so two tools could emit mutually contradictory schemas while both
  claiming `profile: "3d-entity/1"`. The algorithm, stated completely because a
  hash whose input order is a convention is not a hash:

  > Take every file under `spec/` that this manifest declares in some node's
  > `files[]`. Sort by package-relative path, ascending, comparing **UTF-8
  > bytes**. For each, append: the path's UTF-8 bytes, one `0x0A`, the file's
  > own sha256 as **32 raw bytes**, one `0x0A`. `spec_sha256` is the sha256 of
  > that concatenation.

  Paths are included, so moving a file changes the hash; raw hash bytes are
  used rather than hex for the same reason `input_hash` does it (§2,
  `input_hash`), and the two constructions are deliberately the same shape.
  Note the consequence, because it catches people: for a set of exactly one
  file the result is **not** that file's own sha256.

  Three consequences of "every file under `spec/` that this manifest
  declares", stated because three writers each had to work them out (ruling 2
  of 2026-10-13, PROPOSED — a statement of what the algorithm already meant):

  * It is a function of the **manifest alone**: the paths and the sha256
    values are the ones `files[]` declares. Whether the bytes match those
    declarations is the per-file hash's job (§10 step 6). A full reader
    therefore **recomputes it on every open** and reports a disagreement as
    `spec-sha256-mismatch`, severity `error`: the manifest's statement of
    which specification it carries is then not true of the specification it
    lists. Until this revision no reader checked the field it was mandatory to
    write.
  * **Every version counts.** A `spec/` path a superseded version of the
    `core.spec` node still declares (`spec/SPEC@1.md`, §5) is under `spec/`
    and is declared, so it is in the hash. The value identifies *the
    specification this package carries, with its history* — it equals a
    canonical tree's digest only for a package whose `core.spec` node has one
    version.
  * **It covers exactly what `core.spec` nodes declare.** A profile's own
    documents, its schemas and layouts, its format definitions (§3.18) and
    their vector files are all files of a `core.spec` node, live under
    `spec/`, and are therefore covered. A file under `spec/` declared by a
    node of another type would be hashed here and yet not be specification;
    writers do not do that, and a reader that needs a specification file
    (§2.2) accepts it only from a `core.spec` node.

- **Per-node-version `spec_sha256` — OPTIONAL, same ruling.** Any entry of
  `nodes[].versions[]` MAY carry its own `spec_sha256`: the same construction
  over exactly the spec files **that version's payload conforms to** — its
  entry in `schemas`, its entry in `layouts`, or both, sorted by the same rule.
  It answers a narrower question than the global field ("which revision of
  *this* schema was this payload written against"), which is the question that
  actually bites when an append-only node gains a v2 years later under a newer
  spec. Global is mandatory because a package always has a `spec/` tree;
  per-version is optional because most nodes never outlive a revision.
- `parts[]`: `{part_id, name, parent, transform{translation, rotation,
  scale}}` — the stable-id join key across every node family (law 4).
  Transforms are TRS, never a matrix: a matrix hides its own transposition.
- `materials[]`: `{material_id, part_id, name, class}` → materials/,
  properties/, audio material-sound sets.
- `nodes[]`: the graph. Each node: `{node_id, type (namespaced), part_id?,
  material_id?, versions[], active, edges[{to, kind: requires|enhances,
  role?}], meta?}`.
  Each version: `{v, files[{path, sha256, size, media_type?, offset_hint?,
  role?}], payload_file?, note, producer{tool, model?, version}, input_hash?,
  input_files?, input_params?, epistemic: authored|measured|inferred,
  confidence?, created, supersedes?, compacted?, spec_sha256?}`.

  **A node has at least one version and exactly one active version** — and
  `v` is an **incremental integer**: 1, 2, 3, … . It is not semver, it has no
  dots, no minor, no patch and no ordering rule beyond integer comparison; a
  writer that wants to say "this was a small change" says it in the mandatory
  work note, which is what the note is for. `active` names one of those
  integers. Versions coexist append-only (law 6), so "at least one" is the
  floor and there is no ceiling; "exactly one active" is what stops a reader
  having to arbitrate between two recommendations.
  Work note mandatory (law 6). `input_hash` + `input_files` mandatory
  whenever `epistemic` is `measured` or `inferred` — the schema enforces it
  with an `if`/`then`, which is law 5 made machine-checkable.
- Every byte in the container except `MANIFEST.json` **and
  `SIGNATURE.json`** is reachable from exactly one **node**'s `files[]`.
  Nothing floats. (The draft said "except MANIFEST.json"; `SIGNATURE.json`
  must also be excluded, because the manifest hashes every file it lists and
  the signature signs the manifest — listing it would be circular. Recorded
  as decision D-MAN-1.)

  **The unit is the node, not the node version — S-18, RULING, implemented.**
  The sentence used to read "exactly one node
  version's `files[]`", which forbade two versions of one node from both
  listing an unchanged file — and law 6, where versions coexist append-only,
  makes that arrangement completely normal. Under the ruling a file belongs
  to one **node** and may be listed by several of that node's versions, with
  identical `path`, `sha256` and `size` in each. Two **different** nodes
  claiming one path stays an error.

  The alternative is defensible and was rejected on the record: forbid
  sharing, make the second version copy the bytes, and let the store dedup
  them. It was rejected because the copy makes the file a *worse record of
  what happened* — "v2 changed only the sidecar" is visible when v2 relists
  the unchanged image and invisible when it carries a twin — for a saving the
  companion store already provides at rest. `fixtures/ista-varun-v1.werk`
  exercises this case deliberately; it was the one thing in that fixture that
  depended on an undecided ruling, and the ruling went the way the fixture was
  built, so nothing in it moved.

### 2.1 Which file in a node is THE payload — `payload_file`

**S-XV-4 / S-OW-2, and the successor to S-13. Status: PROPOSED, pending
Gregor's ruling; implemented in the schema, the writers and the fixtures
because it is purely additive and a package built without it stays
conformant.**

The measured failure this answers, because it is the sharpest kind — a
program that produced a **wrong artifact while believing it had succeeded**:
an 8B model followed `primary.sound` to its node exactly as this document
told it to, took `files[0]`, and wrote out
`audio/sfx/crate-impact-hard-surface.json` — the *descriptor* — where a WAV
had been asked for. It had already extracted the mesh byte-exact. Nothing was
malformed, no hash disagreed and no verdict was wrong; the node simply has
five files and the format never said which one *is the sound*. Law 8: a
convention is a machine-checkable value, never an inference.

**The field.** Any entry of `nodes[].versions[]` MAY carry

```
"payload_file": "<one of the paths in this version's files[]>"
```

— the package-relative path of the file that *is* this node's payload: the
one a consumer asking "give me the sound", "give me the mesh", "give me the
image" is asking for. It MUST equal the `path` of exactly one entry in the
**same version's** `files[]`. It is the single field a reader follows to a
path, and a manifest-only reader — which S-XV-5 measured as a real and common
kind of reader — sees it directly beside the array it would otherwise have had
to interpret.

**A writer SHOULD emit it on every version whose `files[]` has more than one
entry.** On a single-file version it is redundant and MAY be omitted.

**Resolution, NORMATIVE, in this order.** A consumer that needs the one
payload file of a node version resolves it thus and stops at the first rule
that answers:

1. **`payload_file` is present** → that file. Declared beats inferred, always.
2. **`files[]` has exactly one entry** → that file.
3. **Exactly one entry carries the reserved role `payload`** → that file.
4. **The node type has a documented payload role and exactly one entry
   carries it** → that file. The type→role table, which is normative and
   extends as node families do:

   | node type | payload role |
   |---|---|
   | `core.audio.effect`, `core.audio.ambience` | `best` |
   | `core.imposter` | `atlas` |
   | `core.recipe` | `record` |
   | `core.anim.clip` | the single `.wkac` envelope |
   | `core.tex`, `core.image.*` | the node's single image file (rule 2) |

5. **Otherwise the payload is NOT machine-determinable.** The consumer MUST
   report it — report code `payload-file-ambiguous`, severity `warn`, naming
   the node and every candidate — and MUST NOT silently take `files[0]`.
   Taking the first entry is exactly the failure above and it is now
   explicitly forbidden rather than merely unmentioned.

**Reserved `role` values, which a reader may rely on.** `role` stays an open
kebab-case vocabulary (law 12), and these three values are reserved with
fixed meanings across every node type:

* **`payload`** — this file IS the node's payload. At most one per version.
* **`descriptor`** — a sidecar *about* the payload, typically JSON. **A
  `descriptor` is NEVER the payload**, and rules 3–5 never select one.
* **`best`** — of several interchangeable takes, the one the producer
  recommends. It is the payload role for the audio families, where it has
  meant this since the first fixture.

**Where `primary` fits.** `primary.{mesh, geometry, sound, image}` names a
**node**, and it deliberately keeps naming a node: a node is the unit of
version history and the answer must stay stable as versions accumulate. Two
hops, both mechanical: `primary.sound` → the node → its `active` version →
that version's `payload_file`. **A consumer resolving `primary.*` MUST apply
the rules above and MUST NOT take `files[0]`.**

**Why not make `primary` name a path directly** — the alternative S-13
recorded. Because a path is a version-level fact and `primary` is a
package-level one: a package whose sound gains a v2 would have to rewrite
`primary` as well as the node, and the two could then disagree. The node
reference stays; the missing hop is the one that was added.

**Backward compatibility, stated exactly.** `payload_file` is optional and
additive. A package written before this field resolves through rules 2–5 and
is unaffected; the fixtures in this revision all carry it; a reader that has
never heard of it behaves exactly as it did, and one that has, stops guessing.

### 2.2 Any profile: the base shape, and the schema a package carries

**Ruling 2 of 2026-10-13. Status: PROPOSED, pending Gregor's ruling;
implemented in the schemas, the reference core, the three loaders and a gate
over 40 packages in eleven profiles, nine of them unknown to this repository,
written by ten applications outside it. This
section is base doctrine — it applies to every profile and will move with
§3.11–§3.13 when they move.**

The measured failure: the reference core answered every package of a profile
other than `3d-entity/1` and `image/1` with `error unsupported-convention:
this build carries no manifest schema for profile …` and exit status 1 —
thirty-two of thirty-two — although every hash and
every signature in them verified. Two profiles were a table in the reader. `manifest_schema` had
been added so that "which schema validates the manifest" is declared rather
than known, and the reader then looked the declared path up *in its own
table*, which is knowing with an extra step.

**A profile is defined by documents that travel in the package.** For any
profile:

* `profile` names it: `<name>/<revision>`, a kebab-case name and an
  incremental integer.
* `manifest_schema` names the JSON Schema that validates the manifest, a path
  **inside this package**. It is mandatory for every profile except the two
  reference ones, whose default paths are fixed (§2).
* `profile_spec` names the profile's narrative document.
* `schemas`, `layouts` and `formats` name the schema, the grammar and the
  format definition of every payload kind the package holds.
* `conventions_map` names the machine-readable table of which node types each
  convention governs (§10.2).
* Every one of those files is a file of a `core.spec` node, so it is listed,
  hashed and covered by `spec_sha256`.

**The base shape.** `spec/schemas/manifest.base.schema.json` is what *every*
manifest of major version 1 looks like, whatever its profile: the `werk`
block, `profile`, `entity`, the six **base conventions**, `container`,
`license`, the maps, `spec_sha256`, and the shape of a node, a version and a
file record — including law 5's rule that a `measured` or `inferred` version
carries its inputs. A profile's manifest schema is a **refinement** of it: it
pins `profile`, closes what the base leaves open, adds its conventions, its
`primary` slots and its node types. A profile schema that contradicts the base
shape is not a werk profile.

The six base conventions are the ones a reader depends on to read *any* werk —
the container, the manifest and the envelope frame — and therefore the ones
every profile declares, with these values:
`endianness: "le"`, `alignment_bytes: 16`, `text_encoding: "utf-8"`,
`id_case: "kebab-case"`, `hash_algorithm: "sha256"`,
`signature_algorithm: "ed25519"`.

**What a full reader does, NORMATIVE** (§10 step 2 points here):

1. It validates the manifest against the **base schema, which it has built
   in**. Always. This is the one part of manifest validation that does not
   come from the package, and a package cannot loosen it.
2. It resolves the profile's schema: the `manifest_schema` path, or the
   default for a reference profile. The file MUST be declared by a `core.spec`
   node of the manifest, MUST be in the container, and MUST be the bytes the
   manifest hashes. Failing any of the three it is unusable, and the reader
   says which (`manifest-schema-unusable`).
3. **A profile the reader has built in** (it carries that profile's schema
   itself): if the package's copy is byte-identical to the reader's, or the
   package carries none, it validates against its own. If the package carries
   **another revision** of the schema, it validates against the **package's**
   copy — the package is the authority for its own contents — reports that it
   did (`manifest-schema-revision`, `info`), and reports anything its own
   revision would say differently as **warnings**, never as errors. That last
   pass is what law 12 looks like when it is executed: on a package written
   under an *earlier* revision it must be silent, because evolution within a
   major version is additive; on a package written under a *later* one it
   names what this reader does not know yet.
4. **Any other profile**: it validates against the package's own schema and
   emits exactly one `unsupported-profile` entry, severity `warn`, that says
   what was done and what that establishes (§10.3). A profile other than the
   reference two that names no schema, or names an unusable one, is
   `manifest-schema-unusable` at severity `error`, and only the base shape was
   checked.
5. **Conventions.** For a built-in profile, the profile's whole set against
   the reader's own pins, as before. For any other profile, the **six base
   conventions** against the reader — a mismatch is `unsupported-convention` —
   while the profile's own conventions govern payload meaning this reader does
   not claim; they are named in the `unsupported-profile` entry and not
   refused.
6. **Node types.** A type the reader does not interpret — a profile-defined
   `core.*` type as much as an `x.*` one — goes down the skip path of §10 step
   8: listed, hash-verified, extractable, reported once as
   `node-skipped-unknown-type`, and **never an error**. Where the manifest's
   `schemas` map names a schema for such a type, a full reader still validates
   the node's payload file (§2.1) against it: that is structure, not meaning,
   and it is what catches a payload that was damaged and re-hashed.

A package of a profile no reader has ever heard of therefore opens with exit
status 0, a census, one warning that says exactly how far the reader got, and
one warning per skipped node — which is what law 3 promised and the two-entry
table had been refusing.

**What a bootstrap loader does.** It carries no validator, so steps 1–4 reduce
to: read the manifest, check structurally what it uses, check the base
conventions for a profile it does not have built in, and emit the same single
`unsupported-profile` entry saying that the manifest was **not** validated
against the schema it names. It skips no `core.*` type — it interprets no
payload, so there is nothing for a list of types to gate — and it skips and
reports every `x.*` type. Two of the three loaders used to carry a list of the
core types they had been told about; the lists had fallen five types behind
the manifest schema, the same failure as the envelope magic table (§3.1) with
the same cure.

## 3. Node families (core.*)

Every type below now has its schema or layout, and the manifest's `schemas`
and `layouts` maps point at them.

| Type | Payload | Schema / layout |
|---|---|---|
| `core.spec` | this folder | — (plain text and JSON) |
| `core.loader` | source + optional prebuilt | `manifest.schema.json` → `$defs/loaderMeta`; §7 |
| `core.license` | text | — |
| `core.readme` | text | — |
| `core.geom.source` | GLB | `MINI-SPECS.md` §10 |
| `core.geom.game` | GLB | `MINI-SPECS.md` §10 |
| `core.geom.lod` | GLB | node `meta` requires `lod_level`, `screen_space_error_px`, `reference_resolution_px` (1080), `triangle_count`; see §4 |
| `core.geom.points` | bin | `layouts/points.layout.txt`; §3.15 |
| `core.geom.gsplat` | bin | `layouts/gsplat.layout.txt`; §3.16 |
| `core.tool` ‡ | JSON (+ the tool's own files) | `schemas/core.tool.schema.json`; §3.17 |
| `core.tool.config` ‡ | JSON | `schemas/core.tool.config.schema.json`; §3.17 |
| `core.tex` | PNG | node `meta` requires `color_space`, `usage`, size, `bit_depth` |
| `core.material` | JSON | `schemas/core.material.schema.json` |
| `core.imposter` | PNG ×4 per tier + JSON | `schemas/core.imposter.schema.json` + `layouts/imposter.layout.txt` |
| `core.phys.colliders` | JSON | `schemas/core.phys.colliders.schema.json` |
| `core.phys.bounds` | JSON | `schemas/core.phys.bounds.schema.json` |
| `core.phys.body` | JSON | `schemas/core.phys.body.schema.json` |
| `core.field.flow` | bin | `layouts/flowfield.layout.txt` |
| `core.pose.rest` | bin | `layouts/restposes.layout.txt` |
| `core.skeleton` | JSON (+ optional bin) | `schemas/core.skeleton.schema.json` + `layouts/skeleton.layout.txt` |
| `core.anim.clip` | bin + JSON | `layouts/animclip.layout.txt` + `schemas/core.anim.clip.schema.json` |
| `core.retarget.bind` | JSON | `schemas/core.retarget.bind.schema.json`; §3.14 |
| `core.audio.package` | JSON | `schemas/core.audio.package.schema.json` |
| `core.audio.effect` | WAV + JSON | `schemas/core.audio.effect.schema.json` |
| `core.audio.ambience` | WAV + JSON | same schema, `category: "ambience"` |
| `core.destruct` | GLB + JSON | `schemas/core.destruct.schema.json` |
| `core.props` | JSON | `schemas/core.props.schema.json` |
| `core.semantics` | JSON | `schemas/core.semantics.schema.json` |
| `core.provenance` | JSON | `schemas/core.provenance.schema.json` |
| `core.recipe` † | JSON | `schemas/core.recipe.schema.json`; §3.11 |
| `core.disclosure` † | JSON | `schemas/core.disclosure.schema.json`; §3.12 |
| `core.embedding` † | bin | `layouts/embedding.layout.txt`; §3.13 |
| `core.revisions` † | JSON, one record per Save | `schemas/core.revisions.schema.json`; §3.19 (PROPOSED) |
| `core.scene` | JSON | `schemas/core.scene.schema.json`; §3.20 (PROPOSED) |

† **base doctrine — every profile, not just this one.**
‡ **base doctrine too** (§3.17): a tool that made an image is as much a fact
about the image as a tool that made a mesh is about the mesh.

**A payload in any other encoding** — a JPEG, a font, a camera raw file, a
movie — is a legitimate payload of a `core.*` node of *any* type whose profile
admits it, on one condition: its **format definition** travels in the package
(§3.18, base doctrine).

### 3.1 The binary envelope

Every custom binary in werk — `WKFF`, `WKRP`, `WKAC`, `WKSK`, and any `x.*`
binary — shares one frame: 4 ASCII magic, `u32` version, `u32` header
length, a MessagePack header, zero padding to a 16-byte boundary, then raw
payload sections. Every section's absolute offset, size, dtype, shape and
stride is **declared in the header**, never derived from a struct.
**`spec/layouts/ENVELOPE.layout.txt`** is normative and includes a complete
specification of the MessagePack subset used, so the format is readable with
no external knowledge (law 2).

**How an envelope is recognised, and how its grammar is found — ruling 4 of
2026-10-13, PROPOSED, implemented in the core, the three loaders and a
gate.** Until this revision an envelope was "recognised" only when its magic
was in a table, the table existed in four files — the reference core and the
three bootstrap loaders — and a reader that did not have a magic in its copy
did not parse that file and **reported nothing**, because an unrecognised
magic was by rule not damage. The reference core lacked `WKEM` for three
stages; the omission was indistinguishable from a package with no envelopes
in it. And nothing said what magic a *new profile's* binary takes, so every
profile outside this repository shares `WKX0`–`WKX9` — ten magics for however
many profiles there will be. The rule that replaces the table:

1. **A file is an envelope when its first four bytes are `W`, `K` and two
   characters each an ASCII capital letter or digit**, unless its node
   *declares* it to be in another format (§3.18) — a declaration beats a
   sniff. Every reserved magic and every `WKX` magic has that shape, and so
   does any magic a later revision reserves.
2. **Every envelope is validated structurally**, by every reader that declares
   `read-envelope`, whatever its magic: the fixed prefix, the header, the
   section table and every assertion of `ENVELOPE.layout.txt` §7. A frame
   that fails is `envelope-invalid` and the node is dead. A reader **states
   how many envelopes it validated**, so "no complaints" and "nothing was
   looked at" stop being the same output.
3. **The grammar is found through the header's `kind` and the manifest's
   `layouts` map** — `layouts[kind]` — never through the magic. Outside a
   `core.spec` node, an envelope's `kind` is **its node's `type`**, and that
   type has an entry in `layouts` naming a grammar the package carries. A
   well-formed envelope whose kind has no grammar in the package is reported
   as `envelope-undeclared` (`warn`): the frame was validated, the contents
   are not described by the file, and law 2 is not met for that payload.
   Measured before it was written down: in the fifteen fixtures of this
   repository and the 40 packages of the outside corpus, all 376 envelopes
   outside `core.spec` nodes (11 and 365) already satisfy both halves.
4. **The seven reserved magics each bind one kind** (`ENVELOPE.layout.txt`
   §2); a reserved magic over another `kind` is `envelope-invalid`. That table
   is now a consistency check and nothing else, and a gate
   (`tests/run_gate_magic.py`) holds the four copies of it equal to the
   layout file's. **`WKX0`–`WKX9` bind no kind**: they are for every binary
   this document does not define — a profile's own `core.*` binaries and any
   `x.*` binary alike — the digit means nothing, and two different kinds may
   share one. `kind` is what identifies the payload.
5. **An envelope inside a `core.spec` node is a worked example.** Its `kind`
   is the type it illustrates, its grammar is the layout file beside it, and
   rule 3's two requirements do not apply to it; rule 2 does.

### 3.2 Flow field — `core.field.flow`

**`spec/layouts/flowfield.layout.txt`.** A cubic-celled axis-aligned grid
carrying an f32 signed-distance field in metres (negative inside) and a
co-located 3×f32 flow-response field. X is the fastest-varying index;
`shape` is `[nz, ny, nx]` and is authoritative over `dims`. Trilinear
sampling and out-of-grid extrapolation are specified so two readers agree to
the bit.

### 3.3 Settled rest poses — `core.pose.rest`

**`spec/layouts/restposes.layout.txt`.** Two fixed-stride sections instead
of the draft's variable-length records: a 32-byte pose entry (quaternion,
contact index and count, settle probability, support area) and a flat
`[n, 3]` f32 contact array. Entries are sorted by probability descending, so
"the" rest pose is entry 0 and no consumer needs a policy of its own.

### 3.4 Animation clips — `core.anim.clip`

**`spec/layouts/animclip.layout.txt`** plus
**`spec/schemas/core.anim.clip.schema.json`.** Uniform-rate sampling, an
explicit root track carrying position and rotation, bone-major per-bone
quaternion tracks, and a `bones` name array in the header so the clip is an
island that can be bound by name to any rig. Events (audio, footstep,
contact, marker) live in the header and resolve to `core.audio` effect
slugs; an unresolvable event is dropped with a report, never a failure.

**Optional per-bone translation — S6-4, RULING, implemented; layout version
2.** D-AC-4 ruled translation on non-root bones a rig feature and the argument
was good — admitting it doubles every track for the clips that need it. The
measurement said the exception is not rare: Unreal keys `pelvis` translation as
a matter of course (0.111 m on a one-second walk, which is the whole vertical
bob of the gait) and a COLLADA-exported glTF keys translation on **every**
joint. So `WKAC` version 2 adds **one optional section**, `bone_translation`,
an `[frames, n_translated_bones, 3]` f32 array whose bones are named by a
header key rather than implied, alongside a `source_had_bone_translation`
record for clips that dropped it. Rotation tracks, the root track, the header
grammar and every existing key are **unchanged**.

The version bump is **incremental and backward compatible in the direction
that matters**: a version-1 reader meeting a version-2 clip finds every section
it knows exactly where it knows, and finds one section in the header's section
table whose name it does not recognise. `ENVELOPE.layout.txt` already requires
that such a section be **skipped and reported**, never guessed at and never
treated as damage — so an old reader plays the clip with rotations only, says
so, and is conformant. That is the whole reason offsets and sizes are declared
in the header instead of derived from a struct. The layout file states the rule
in its own grammar; see `spec/layouts/animclip.layout.txt` §0 and §6.

### 3.5 Skeleton — `core.skeleton`

**`spec/schemas/core.skeleton.schema.json`** is normative;
**`spec/layouts/skeleton.layout.txt`** describes an optional binary mirror
for very large rigs, which must carry the JSON's hash so it can never
silently drift. The canonical humanoid is
**`spec/skeleton/canonical-humanoid-v1.json`** — **23 bones**, 1.75 m
reference stature, T-pose with palms down, with every rest rotation and
translation as an exact number in both parent-local and model space, plus
`axis_along` and `axis_back` per bone to fix the roll. Hands are the separate
extension **`spec/skeleton/core.hands.v1.json`**, 15 bones per hand. Retarget
name maps for Mixamo, the UE mannequin and VRM 1.0 travel with the skeleton as
data. **Both files are now `status: "approved"`, `canon_version: "1.0"`**
as of the 2026-08-08 rulings. The lifecycle state and the version of the
numbers are two fields on purpose: a value that is both a state and a
number is a field two readers disagree about. The
numbers are approved and two of them changed on the way in.

**The root is a base bone at the origin, and `hips` hangs off it — ruling 9,
now normative.** The structure is:

```
root   at (0, 0, 0), identity rotation, no parent, never driven
└─ hips at (0, 0.98, 0) in model space, a body bone like any other
   └─ …spine, legs, arms, unchanged
```

The purpose is that a clip which is not in-place has somewhere honest to put
its locomotion. If the pelvis were the root, a walk cycle's forward travel and
the pelvis's own vertical bob and lateral sway would be the same three numbers
and nothing could separate them; with a base bone at the origin, the **root
carries the trajectory** and the **pelvis stays a body bone**. In-place clips
leave the root at identity and lose nothing (`flags` bit 0, IN_PLACE).

Three consequences, stated because they are what an implementer needs:

* `root` is **never driven by a mapped foreign bone**, even when a name map
  offers one — the UE mannequin map does. A foreign rig's root is sometimes the
  pelvis, sometimes a floor-locked node keyed at identity for the whole clip,
  and sometimes absent; deriving the root track from the **hips** is the only
  rule that behaves the same for all three.
* Its 0.1 m extent is a **display stub with no anatomical meaning**. Nothing
  parents to its tail and no length calculation uses it.
* The hands extension parents to `l-hand`/`r-hand` exactly as before and does
  not move.

**Bone count stayed at 23**, and the ruling's "+1" is filed rather than
applied: the shipped draft already carried this base root, so there was no
23rd-plus-one bone to add without inventing one with no role. Recorded as
finding **S-R-1** in `results/STAGE-RULINGS-RESULTS.md`, because a ruling and
an artifact disagreeing is exactly the thing that must be written down instead
of quietly reinterpreted.

**The thigh is longer than the shin — ruling 8, S6-5.** The draft had
`l-thigh`/`r-thigh` at 0.42 m and `l-shin`/`r-shin` at 0.43 m: a shin/thigh
ratio of 1.024, which no human skeleton has. Both human-derived rigs measured
in Stage 6 disagreed after their own solved stature scale — CMU take 02_01
(a capture of a real person) 0.960, the UE 5.7 mannequin 0.944. The two are
swapped: **thigh 0.43, shin 0.42.** Total leg length is unchanged at 0.85 m,
so the ankle, the foot and the toe do not move and nothing below the knee is
affected.

### 3.6 Imposters — `core.imposter`

**`spec/schemas/core.imposter.schema.json`** for the descriptor;
**`spec/layouts/imposter.layout.txt`** for the atlas tiling arithmetic, the
normative octahedral encode/decode (including `sgn(0) = +1`, which is a real
one-texel seam if you get it wrong) and the G-buffer channel packing:
albedo RGBA sRGB, normal RG octahedral linear, depth 16-bit normalised by a
declared range, MRAO 8-bit linear. There is deliberately no custom binary,
and that decision is argued in the layout file rather than assumed.

### 3.6a Which space the physics nodes are in — S10-3, RULING, implemented

Stated here, once, because a consumer needs to know whether a transform sits
between two of these nodes and the answer used to be spread across three
schemas that did not agree:

| node | space | declared by |
|---|---|---|
| `core.phys.bounds` | **model** | `space`, `const "model"` |
| `core.phys.colliders` | **part-local** | `space`, `const "part-local"` |
| `core.phys.body` | **model** | `space`, `const "model"` — **new** |

So yes: a transform sits between colliders and the other two, and it is the
part's transform in `parts[]`. `core.phys.body` previously declared no space
at all while *requiring* `center_of_mass_m`, and its space could only be
inferred from a sibling field (`inertia.frame`, `const "model-axes"`) — an
inference, in the one schema family that elsewhere refuses to let a reader
infer anything. The ruling is **model**, it is now a `const` in the schema, and
it agrees with the `inertia.frame` that was the only previous evidence, so no
existing conformant package changes meaning.

### 3.7 Simulation properties — `core.props`

**`spec/schemas/core.props.schema.json`** carries the **v1 property
registry**: `flammability`, `electrical`, `thermal`, `mechanical`, `fluid`,
`magnetic`. Every single value is an object with its own `value`, `unit` and
`epistemic` stamp, plus an optional plausible `range` — because most of
these will be a vision-language model's guess about a picture of a crate,
and an inferred Young's modulus is only useful while it is still labelled a
guess. Units are SI and stated per field.

### 3.8 Semantics — `core.semantics`

**`spec/schemas/core.semantics.schema.json`** plus the registry
**`spec/facets.json`** (validated by `spec/schemas/facets.schema.json`).
Seven facets — `style`, `function`, `environment`, `era`, `mood`,
`condition`, `scale-class` — with 15–40 canonical kebab-case tags each, an
alias map, and, for `scale-class`, numeric size bands so a size filter is
arithmetic. Any tag outside the registry must start with `x.`; a tag that is
neither is a validation error. The node also carries the style embedding
(`{model, dim, vec, normalized, dtype}` — `model` mandatory, because a
vector whose model is unknown is noise) and the palette in both sRGB hex and
linear float.

### 3.9 Audio — `core.audio.*`

**`spec/schemas/core.audio.package.schema.json`** and
**`spec/schemas/core.audio.effect.schema.json`**, both adopted from
splat-foley's real production output rather than designed fresh: `slug`,
`prompt_used`, `clap_score`, `accepted`, `variations[]`, and the `refined`
block with `kept`, `cut`, `events`, `heard` and the roll-back `reason`. The
roll-back record is kept deliberately: a format that only records successes
cannot be audited.

**Two vocabularies, one value — read this before writing code against either.**
`core.audio.package` was adopted verbatim from splat-foley's production
output, and `core.audio.effect` is the werk per-effect sidecar. They disagree
about the names of fields that mean the same thing, because adopting the
donor format *verbatim* was the deliberate choice (§3.9's whole point) and
renaming its fields would have made the werk package a lossy copy of a real
pipeline's output rather than a faithful one. The disagreement is therefore
permanent, and the only honest fix is to state it:

| meaning | in `audio/package.json` (`core.audio.package`) | in `audio/sfx/<slug>.json` (`core.audio.effect`) |
|---|---|---|
| the text the model was given | `effects[].prompt` | `prompt_used` |
| sample rate | *(not carried)* | `audio_format.sample_rate_hz` |
| the takes on disk | `effects[].takes[]` with `role` ∈ `best`/`raw`/`variation` | `variations[]`, plus the node's own `files[].role` |
| where the sidecar is | `effects[].meta` | *(it is the file)* |

The sidecar is the authority on one effect; the package file is the
authority on the set. A reader that carries a field name across from one to
the other gets an empty string and no error, which is exactly what happened
to a gauntlet reader (S-20). If you take one thing from this table: it is
`prompt` there and `prompt_used` here.

### 3.10 Geometry conventions inside a GLB

`MINI-SPECS.md` §10 says how to parse a GLB. This says what a werk GLB must
contain, because "it's a GLB" is not an answer to "which attributes am I
guaranteed".

* **Every primitive** has `mode` 4 (triangles) and an `indices` accessor of
  component type 5123 (u16) or 5125 (u32). Non-indexed primitives are not
  conformant.
* **Required attributes:** `POSITION` (VEC3 f32, metres, werk model space)
  and `NORMAL` (VEC3 f32, unit length, in the same space) — **for renderable
  geometry**, which is `core.geom.game` and `core.geom.lod`.
  `core.geom.source` is the exception, and requires only `POSITION`: it is
  the master as the capture, scan or sculpt produced it, and it is the anchor
  that every derived node's `input_hash` is computed against. Rewriting a
  source to add attributes it never had would break every one of those hashes
  and would mean the package no longer contains the thing it says it
  contains. A source without normals is therefore conformant, and the game
  mesh derived from it — which computes them, and says so with a `measured`
  stamp and an `input_files` pointing at the source — is where the
  requirement bites. (Real assets forced this: the golden fixture's source
  GLB carries `POSITION` and `COLOR_0` and no normals at all. Recorded as
  Stage 3 spec finding S-9, resolved as Stage 1 decision 25.)
* **`TANGENT`**, when present, is VEC4 f32: `xyz` is the unit tangent and
  `w` is the bitangent sign, `+1` or `-1` exactly, such that
  `bitangent = cross(normal, tangent.xyz) * tangent.w`. Tangents are
  MikkTSpace. A normal map's green-channel direction is declared per texture
  in the node `meta`'s `normal_convention`, not inferred from the tangents.
* **UV sets:** `TEXCOORD_0` is the material UV set and is what
  `core.material` texture slots sample by default. `TEXCOORD_1` is the
  non-overlapping lightmap/bake set when one exists. A material slot's
  `uv_set` field names which one it uses, so nothing is positional.
  UV origin is top-left (`conventions.uv_origin`), matching PNG raster order.
* **`COLOR_0`**, when present, is VEC4 in **linear** space, never sRGB —
  vertex colour is a multiplier on a linear base colour, and glTF leaves this
  ambiguous enough to be worth pinning.
* **`JOINTS_0` / `WEIGHTS_0`** index the `core.skeleton` node's bones **by
  the position of the bone id in that skeleton's `bones` array**. Weights are
  normalised to sum to 1.0 within 1e-4. A skinned GLB carries a `requires`
  edge to its skeleton node.
* **Scale:** node transforms in the GLB may carry non-uniform scale, but the
  entity's parts and their transforms in `MANIFEST.json` are the authority on
  placement. Where the two disagree the manifest wins and a reader reports it.
* **Units and axes** are the manifest's, not glTF's: metres, +Y up, −Z
  forward, +X right, counter-clockwise front faces. See `MINI-SPECS.md`
  §10.3.

### 3.11 The reproduction record — `core.recipe` (base doctrine)

**`spec/schemas/core.recipe.schema.json`.** Applies to every profile.

Law 5 already demands that a derived node record who made it, from what, and
how sure we are. A generated node needs more, because "who made it" is a model
and "from what" is a prompt, a seed, a sampler and a stack of conditioning
images — none of which fit in a `producer` block, and all of which are the
first thing anyone asks six months later. `core.recipe` is that record:

* **models**, with weight hashes where weight hashes exist;
* **prompts**, positive and negative, carried as *files* with their own
  hashes rather than inline — a prompt is thousands of characters with
  newlines and non-ASCII in it, and it is the single field most often mangled
  by quoting;
* **seeds**, samplers, steps, cfg, schedulers, denoise, and whatever else the
  caller actually passed, under the caller's own key names;
* **LoRAs by hash**, because two adapters with the same name is a routine
  occurrence and a name is not an identity;
* **the pipeline graph embedded verbatim** — a ComfyUI workflow JSON goes in
  byte-for-byte, so it can be loaded back into the thing that produced it;
* **tool versions**, with the string `not-recorded` as a legal honest value;
* **every input medium, embedded by hash**.

**Hermeticity, and its one stated exception (D-REC-1).** Every input *medium*
a recipe names — conditioning images, masks, reference sheets, init frames,
audio — MUST be present in this package and MUST appear in the recipe node's
own `files[]`. A recipe that names an input it does not carry is a promise
about another file, which law 1 bans at the constitutional level. **Model
weights are the exception**: they are identified by sha256, MAY be embedded,
and when they are not the recipe says so in `model.weights` rather than
staying silent. A 12 GB checkpoint inside every generated image is not a
format, it is a mistake. The distinction is not arbitrary: input media are
small, and they are *the thing the model actually saw*.

**The reproducibility grade is declared, and it is a claim about the record.**
Exactly one of:

| grade | what it promises |
|---|---|
| `deterministic` | re-running this recipe on these inputs, with the named tool versions and the named weights, returns the output **byte for byte** |
| `stochastic` | every parameter is recorded but one random source is not pinned: another run draws another sample from the same distribution — the same recipe, not the same bytes |
| `descriptive` | the record is truthful and a re-run cannot be expected to reproduce the output at all |

`reproducibility_note` is mandatory and must say *which specific fact* puts
the recipe in that grade. A hosted API image is `descriptive` however good it
looks — the operator may change the weights behind a stable model id without
telling anyone, which is a property of hosting rather than a criticism of a
vendor — and saying so plainly is the entire point of the field.

**`unrecorded[]` is mandatory too.** It lists the facts about this generation
that were *not* captured and cannot be recovered: the client library version,
which self-correction iteration produced the saved pixels, the operator's
sampler. Law 5 says an inferred value is useful *because* it is labelled
inferred; this array is the same idea one step further, for values that are
not even inferred. It is what lets a reader tell a recipe that is complete
from one that is merely confident.

**Prompt provenance is its own field**, because "the prompt" is three
different claims wearing one word. `recorded` means the producing pipeline
persisted this exact string at generation time. `reconstructed` means it did
not, and the string was rebuilt from the pipeline's own source — legitimate,
common, and *not the same thing*, so it carries a mandatory `reconstruction`
block naming the source file and lines, and the package SHOULD carry that
source as evidence. `authored-after` means a human wrote down what they
believe the prompt was, and it must never be presented as the first.

### 3.12 Disclosure — `core.disclosure` (base doctrine, normative)

**`spec/schemas/core.disclosure.schema.json`.** Applies to every profile.

The node carries machine-readable **facts**: `ai_generated`, `ai_modified`,
`generation_scope`, who declared them and when, the models involved, what a
human contributed, which synthetic-content markers are and are not claimed to
be present, and what is known — usually nothing — about the training data.

**The doctrine, which is Gregor's explicit ruling and is constitutional:**

> **The format ships facts; the viewer applies jurisdiction. The format
> contains NO enforcement of any kind.**

No locks. No DRM. No mandatory viewer behaviour. No policy gate. No field a
conformant reader is obliged to obey. **Anyone with a compiler may write a
viewer that ignores every disclosure in every werk file, and that freedom is
intentional** — it is what "open and clean" means, and a format that tried to
prevent it would be lying about what a file can do.

The format's only MUST-level demands are about **honest reading and
reporting**, and they are these:

1. A tool that reports a package's disclosure MUST report what the node
   **says**. It MUST NOT paraphrase it into a different claim, and it MUST
   NOT report `ai_generated: false` for a package that says `true`.
2. **Absence is its own answer.** A package with no `core.disclosure` node
   MUST be reported as *no disclosure recorded*. It MUST NOT be reported as
   "not AI-generated". Those are different sentences and collapsing them is
   the failure this clause exists to name.
3. A tool MUST NOT invent a disclosure for a package that carries none, and
   MUST NOT present `declared_by` as verified when no signature chain covers
   it. A disclosure is an assertion **by a party**; §6's three states say
   what, if anything, binds it to that party.
4. A tool MUST NOT report a package as *compliant* with any jurisdiction on
   the strength of these fields. `jurisdiction_note` is informational and the
   schema says so in its own description.
5. Where a `core.recipe` and a `core.disclosure` disagree — different model
   ids, say — a reader reports the disagreement rather than picking one.

**What replaces enforcement.** Nothing in the format stops a tool stripping
the disclosure node. It does not need to: removing the file changes the
manifest, and the manifest is what the chain signs, so a stripped disclosure
lands in §6's `present-and-invalid` state and is *conspicuous*. That is the
same mechanism law 7 already uses for authorship — make the clean path the
cheapest one and make its absence visible — applied to one more kind of fact.
It is a property of the design, not a rule anybody has to obey.

**Interop.** `spec/X-C2PA-EXPORT.md` plus
`spec/schemas/x.c2pa.export.schema.json` document the intended C2PA mapping,
its gaps in both directions, and — first, in a table — the fact that nothing
in it has been implemented or validated. It is an `x.*` extension precisely so
that no `core.*` node is hostage to another consortium's schedule.

### 3.13 Embeddings and palette — `core.embedding` (base doctrine)

**`spec/layouts/embedding.layout.txt`**, magic `WKEM`. A fixed-length
descriptor vector plus the dominant-colour palette computed in the same pass
(law 9: one derivation, two masters — the vector serves search, the palette
serves the browser listing). The header's `model` key is mandatory: a vector
whose model is unknown is noise, since distance between vectors from two
different models means nothing at all. `metric` is declared rather than
assumed for the same reason.

The layout file defines one descriptor completely — `werk.descriptor.labhog/1`,
a 72-component CIELAB histogram plus gradient-orientation histogram — so that
an embedding node can be **`measured`** rather than merely asserted: a reader
holding the source image can recompute it and check. A named neural embedding
would be a better descriptor and a worse example, because its weights are not
in the package and the node could then only ever be an assertion. Both are
legal; the fixture uses the one a reader can check.

The 3D profile's `core.semantics` keeps its JSON style embedding and that
stays legal. `WKEM` is for the case where the vector *is* the payload.

### 3.14 The solved bind — `core.retarget.bind` (S6-2, RULING, implemented)

**`spec/schemas/core.retarget.bind.schema.json`.** Profile-1 material.

Stage 6 measured the gap: a conformant package could contain a clip that was
retargeted, and contain the skeleton it was retargeted onto, and say **nothing
at all** about the pose the bind was taken in, the scale that was solved, or
the rotation that was recovered. Two of the three real rigs measured there have
a neutral that is not the canonical T-pose — the UE mannequin's A-pose is
0.419 rad away in mean bone direction, CesiumMan's bind pose 0.430 rad — and
binding neutral-to-neutral is the *correct* answer in both cases, not an error.
The retarget fixture had to hide all three numbers in an `x.werk.retarget`
node, which is honest and unreadable to anyone else.

A bind is a **reusable artifact**, and today every tool that wants one
recomputes it from scratch. The node carries the solved result:

* **`source`** — the foreign rig's identity as this package can honestly state
  it: a `skeleton_id`, the `bone_count`, the file it came from and its sha256
  where the package carries it, plus the declared or *recovered* unit scale and
  axis convention. "Recovered" is a real value here: nothing told the Stage 6
  solver that a CMU BVH unit is 6.15 cm.
* **`target`** — the `core.skeleton` node this binds onto, by `node_id`, plus
  that skeleton's own `skeleton_id` so the bind survives being copied into a
  package whose node ids differ.
* **`calibration_pose`** — the pose the bind was taken in, in the shape
  `core.skeleton.schema.json` already defines, on **both** sides. Absent on a
  side means that side's rest pose was the calibration pose, which is the same
  rule the skeleton schema already states.
* **`scale`** — the solved uniform stature scale, source→target.
* **`rotation`** — the solved source→target basis rotation as a `wxyz`
  quaternion, which is where a Z-up left-handed rig stops being a special case
  in somebody's code and becomes a number in a file.
* **`bones[]`** — per-bone: the foreign name, the canonical `bone_id`, the
  solved rest-offset quaternion, and the **measured residual in radians**. A
  bind that does not carry its residuals is an assertion; one that does is
  `epistemic: "measured"` and a consumer can decide whether 0.22 rad on one
  joint is acceptable for its use.
* **`residual`** — the summary: mean, max, and the bone the max was on.
* **`unmapped[]`** — foreign bones with no canonical correspondence, and
  canonical bones the source cannot drive, both listed rather than silently
  absent. A bind that hides what it could not match is the failure mode this
  whole node exists to make visible.

The node is `epistemic: "measured"` when a solver produced it against declared
inputs, and its `input_files` name the source rig and the target skeleton, so
a consumer can tell a bind that is stale from one that is current without
trusting a date.

### 3.15 Point clouds — `core.geom.points` (Stage 12)

**`spec/layouts/points.layout.txt`**, magic `WKPC`. Profile-1 material.

A point cloud is the rawest 3D measurement there is — a LiDAR sweep, a
photogrammetric tie-point set, a scanner export, a mesh sampled for a physics
pass, the preview derived from a Gaussian splat — and until Stage 12 werk had
nowhere to put one. A GLB can carry points (`mode` 0) but a werk GLB is
required to be `mode` 4 triangles with indices (§3.10), and stretching that
rule would have made "is this a mesh" unanswerable.

The design question is that a point cloud has **no fixed field set**. Position
is universal; everything else — colour, normal, intensity, return number,
class code, confidence, four things a research capture invented last week —
varies per instrument. PLY, LAS and E57 all arrived at a per-field type system
for this reason. So does werk, and it reuses machinery it already had rather
than inventing any: **each field is one payload section**, and the header's
`fields` array declares each one's `name`, `section`, `semantic`, `dtype` and
`components`. `ENVELOPE.layout.txt` §5a already requires a reader to find
sections **by name** and to skip-and-report the ones it does not know, so a
reader written before a field existed handles that field correctly — it takes
`position` and whatever else it recognises and reports the rest. The `fields`
array is what makes the skip *informed*: it says what the field meant, in what
unit, in what colour space, so a consumer can tell what it declined.

The semantic registry v1 is `position` (mandatory, exactly one, first, f32 or
f64 ×3, metres, werk model space), `color` (`color_space` mandatory on the
field — a colour whose space is unstated is gamma-wrong in half its
consumers), `normal`, `intensity`, `classification` (with its label map
carried **as data**, because a class scheme living in a consumer's constants is
a class scheme two consumers disagree about) and `custom`, whose field names
must begin with `x-` for the same reason a facet tag outside `spec/facets.json`
must begin with `x.`.

**PLY is the ingest source and two things are deliberately dropped**, both
reported rather than silent: a `face` element (a PLY with faces is a mesh and
belongs in `core.geom.source`, and quietly discarding its faces would turn a
mesh into a point cloud without telling anyone), and `nx/ny/nz` that are
exactly zero for every point — the signature of the INRIA splat writer reusing
a point-cloud writer, where carrying the zeros as "normals" would be worse than
carrying nothing because a consumer would light with them.

### 3.16 Gaussian splats — `core.geom.gsplat` (Stage 12)

**`spec/layouts/gsplat.layout.txt`**, magic `WKGS`. Profile-1 material.

Six declared streams — `means`, `scales`, `rotations`, `opacities`, `sh-dc`,
`sh-rest` — one record per Gaussian, no index and no sort order. Three
decisions in it are the ones an implementer needs, and each is a place where a
wrong answer produces a file that parses, renders, and is wrong.

**werk stores the ACTIVATED values, and says so in the file.** The training
representation stores `log` scales and `logit` opacity because an optimiser
wants an unconstrained parameterisation; a file format has no optimiser. A
consumer reading a scale wants metres and a consumer reading an opacity wants a
number it can multiply by, and storing the raw parameters would put `exp` and
`sigmoid` into every reader in every language for the benefit of the one
consumer in a thousand that is resuming training. So `scale_space` and
`opacity_space` are both `"linear"` in grammar revision 1 — stated as header
keys anyway, on exactly the argument `endianness` makes, that a file states its
own facts rather than relying on this document — and the layout gives the exact
inverse, which makes that thousandth consumer's job three lines rather than
impossible. **The inverse is not total and the layout says so where it bites**:
`logit(0)` and `logit(1)` do not exist, `ENVELOPE.layout.txt` §6 forbids an
infinity in any core payload, and a fully opaque Gaussian is the single most
common value in a trained splat. Exact `0.0` and `1.0` are therefore **legal**,
and a producer converting *into* logit space must clamp, must state its clamp,
and should record how many records it clamped.

**SH coefficients are stored coefficient-major, transposed from the source.**
The INRIA PLY writes `f_rest_*` channel-major — all K−1 coefficients of red,
then green, then blue — because that is how a training tensor happened to be
shaped. Evaluating spherical harmonics is a loop over *coefficients*
accumulating into an RGB triple, so coefficient-major is the order the
consumers read in; the transpose is paid once, by the ingester. A renderer
written against the PLY layout and pointed at a `WKGS` payload without
transposing produces plausible colours and wrong view-dependence, which is the
kind of wrong that survives review, so the layout states the index arithmetic
in both directions. The manifest gains an optional convention
**`sh_coeff_order`** for this, and it is deliberately **not** `sh_l1_order`:
that one names the *basis* order an `x.*` extension uses for per-vertex L1
irradiance, this one names the *memory* order of a per-primitive coefficient
array, and collapsing them would give one convention two meanings. An optional
**`sh_degree`** rides beside it as a package-level maximum so a store can size a
buffer before parsing 100 MB — **it is not the authority on any payload**; each
envelope declares its own, a payload declaring more than the manifest is a
producer error, and a reader reports the disagreement rather than picking one.

**The dual-consumer path is normative (law 9, law 3).** A `WKGS` payload
*contains* a point cloud, exactly, with no approximation and no resampling:
`position[i] = means[i]` and `color[i] = clamp(0.5 + C0·sh-dc[i], 0, 1)` with
`C0 = 0.28209479177387814`. So a reader that understands only positions and
colours **MUST** be able to consume a splat by reading exactly two of its six
sections and skipping the other four by the section table without parsing them
— and it is a **conformant consumer of the node**, not a degraded one; nothing
in the format asks it to apologise for not being a splat renderer. In the other
direction a writer **SHOULD** also materialise the derived `core.geom.points`
node with an `enhances` edge, because a browser and a physics pass want the
point cloud as a payload they can hash and cache rather than as an arithmetic
they have to perform — and because that node is then `epistemic: "measured"`
over a derivation stated completely in the layout, so a consumer can recompute
it and check. The two statements are not redundant: the first says the
degradation always exists, the second says a good writer materialises it, and a
package carrying only the splat is conformant.

The 0.5 in that colour line is not decorative. The training code centres colour
on 0.5 so a zeroed coefficient is mid-grey rather than black, and a reader that
drops it renders everything uniformly too dark by exactly half the range.

**The one field the source does not declare is the quaternion order.** The
reference implementation stores `w` first; several widely used exporters store
`w` last under identical property names, and nothing in a PLY header
distinguishes them. An ingester is therefore told the order or infers it, and
in both cases it **must record which, and how**, in the node's `input_params`.
werk's ingester records the mean absolute components its inference compared, so
a weak inference is visible as a weak inference — and it can be genuinely weak:
measured on a real 1.92 M-Gaussian scene the four means were 0.4578 / 0.4627 /
0.4768 / 0.4509, which decides nothing. A guess that is recorded and a guess
that is silent are different things (finding S12-3).

### 3.17 Embedded tools — `core.tool` and `core.tool.config` (base doctrine)

**`spec/schemas/core.tool.schema.json`** and
**`spec/schemas/core.tool.config.schema.json`**. Applies to every profile.

Gregor's order of 2026-08-08: werk must record the tools used to create or
convert its content **as part of the data**, and must be able to **embed the
code** of those tools and their configurations in the file.

Law 1 already made the format carry a reader (`core.loader`, §7). This is the
same move applied to the other end of the pipeline: a package carries the code
that **made** it, so "what produced this" stops being a name in a `producer`
block and becomes a thing a reader can open. `core.tool` is the code and its
identity — `role` (creator | converter | processor | packager | validator |
viewer), `language`, `entrypoint`, `files[]` with hashes, `invocation`, and its
**own licence**, which is not the content's licence and is the thing people
forget. `core.tool.config` is one *run's* settings: `params` under the tool's
own key names, unrenamed and unvalidated by werk, plus config **files** carried
verbatim rather than reserialised, plus the environment facts a re-run is
sensitive to.

They are two node types rather than one because they have different lifetimes.
One tool is run twenty times with twenty configurations, and duplicating a
source tree twenty times to record that would be absurd; a configuration is
also the thing most likely to be corrected later, which law 6's append-only
versions handle cleanly for a node of its own.

**`params_provenance` is mandatory**, and it is the same three-way distinction
§3.11 makes about prompts, for the same reason: `recorded` means the running
tool persisted this exact object; `reconstructed` means it did not and the
object was rebuilt from the tool's own source or defaults — legitimate, common,
and *not the same claim*, so it carries a mandatory `reconstruction` block; and
`authored-after` means a human wrote down what they believe the settings were.

**The safety rule is §7.1's, verbatim, and this node does not weaken it.**
Source is always allowed and reading it is the point. A prebuilt binary is
inert data: a conformant tool **MUST NOT** execute, load, `dlopen`, link or JIT
one automatically under any circumstance, including when the signature chain
verifies, and may *offer* to run one only when the chain verifies **and** the
signing identity is one the **user** marked trusted in that tool **and** the
user takes a deliberate per-package action. `prebuilt.built_from` must name a
source entrypoint **in the same package**, so a suspicious consumer can rebuild
and compare rather than trust. The schema carries
`never_auto_execute: {"const": true}` — a constant, not a switch, so the rule
is machine-visible to a consumer that never reads §7.1 and a package cannot opt
out of it.

**The recipe can now point INTO the file.** `core.recipe`'s tool block gains
optional `tool_node` and `config_node` (§3.11), so "which tool" is answered by
a node id resolved inside this package instead of by a hash somebody else has
to resolve. Where both `tool_node` and `source_file` are present they must
agree — the named node's `entrypoint` is that path — and a reader that finds
otherwise reports the disagreement rather than picking one.

**Hermeticity and intermediates — the one extension to §3.11's rule.** §3.11
says every input *medium* a recipe names must be present in the package,
because a recipe that names an input it does not carry is a promise about
another file. An **intermediate** — a file a tool in the package produced from
an input in the package and then consumed — is a different case, and the rule
for it is:

> An intermediate **NEED NOT** be carried when an embedded `core.tool` and an
> embedded input reproduce it. The recipe **MUST** then record the
> intermediate's `sha256`, its size and the exact invocation that produces it,
> so the claim is checkable rather than asserted. Where no embedded tool
> reproduces it, it is an input medium like any other and §3.11 applies
> unchanged.

That is not a loophole, it is the point of embedding the code: a 15 MB
intermediate that the file's own converter regenerates byte-for-byte from a
9 MB input the file carries is *more* verifiable than a copy, because a
consumer can run the check instead of comparing two blobs it was handed.
`fixtures/gsplat-v1.werk` exercises exactly this and its gate performs the
regeneration. Recorded as finding **S12-5**.

### 3.18 Format definitions — any encoding, defined in the file (base doctrine)

**Ruling 1 of 2026-10-13. Status: PROPOSED, pending Gregor's ruling;
implemented in both manifest schemas, the base schema, the reference core and
a gate. Applies to every profile.**

The ruling this section implements, in Gregor's words (2026-10-12):

> The self-describing part of each node is a format declaration and
> definition from which an LLM / AI agent can build a working codec. This is
> the fundamental principle. For convenience a reference implementation in
> Python or Rust or C++ may additionally be included.

Law 2 said it for three kinds of payload — a narrative spec, a JSON Schema per
structured node, a layout grammar per custom binary — and law 11 named a short
list of "boring" encodings for everything else, each with a mini-spec. What
neither said is what happens to the JPEG a photographer imported, the font a
document embeds, the camera raw file an archive exists to keep. The measured
answer was that eight applications each invented one: an extension node, a
`meta` key, an `encoding: "other"`. The principle above settles it and it is
one rule:

> **A payload in any encoding is a legitimate `core.*` payload when — and only
> when — the package carries a definition of that encoding from which a codec
> can be built.** The test for a core payload is not "a standard library opens
> it"; it is "this file says how to decode it".

The original bytes then travel **verbatim**. They are not re-encoded into
something boring, not wrapped, and not exiled to `x.*`.

**One mechanism, four places.**

1. **The definition document** — one markdown file per format, at
   `spec/formats/<format id>.md`, a file of a `core.spec` node. It is
   normative, self-contained and byte-level: it restates what a decoder needs
   and depends on no document outside the package. Its form is below.
2. **The manifest's `formats` map** (§2): format id → the document's path.
   Parallel to `schemas` and `layouts`.
3. **The node's declaration**, in its `meta`:
   * **`payload_format`** — the format id of the node's **payload file**
     (§2.1). A node does not change format; a re-encoding in another format is
     another node.
   * **`file_formats`** — an object, file **role** → format id, for files of
     the node that are not its payload: the input media of a recipe, an
     original kept beside its conversion. Every file of the version carrying
     that role is in that format.
   * **`contained_formats`** — an array of format ids, for a payload in a
     *container* format that holds streams in further formats (a movie file:
     pictures in one codec, sound in another). It says which definitions
     decode what is inside; which stream is in which is the container's own
     business.

   Every id named in any of the three is a key of `formats`.
4. **`spec_sha256`** covers the documents and their vector files, because they
   are files of a `core.spec` node (§2).

**To decode a foreign-encoded file:** node → `meta.payload_format` (or
`meta.file_formats[<the file's role>]`) → `formats[<id>]` → read that
document. Never infer a format from a file extension, and never from the
bytes when the node has named one: **a declaration beats a sniff**, and a file
a node declares to be in a format is not examined as an envelope or as a JSON
payload whatever it begins with.

**The definition document.** It begins with a machine-readable header: a
fenced code block whose info string is `werk-format`, holding one JSON object.

| key | meaning |
|---|---|
| `format_id` | the id; equals the key in `formats`. Kebab-case |
| `format_version` | an incremental integer, 1 for the first text. A revised document keeps its id and raises this; a package carries the copy it was written with |
| `title`, `media_type`, `extensions` | for humans and for a file record's `media_type` |
| `sniff` | how a file of this format is recognised from its first 64 bytes: a **non-empty** list of alternatives, a file matching at least one. `{"magic": [{"offset": N, "hex": "…"}, …]}` — every listed byte string present at its offset. `{"rule": "zlib-header"}` — `CMF & 15 == 8`, `CMF >> 4 <= 7`, `(CMF*256 + FLG) % 31 == 0`. A format with nothing to recognise says so with the single alternative `{"rule": "none", "note": "<why>", "size_multiple_of": N}` (`N` optional: the record size); such a format is always *named* by its node. An empty list is an omission, not a declaration |
| `defines` | `{"decode": bool, "encode": bool}`: what the document suffices to build |
| `coverage` | `"complete"` or `"partial"` |
| `coverage_note` | mandatory when partial: exactly what is and is **not** defined |
| `lossy`, `tolerance` | when two conformant decoders need not agree bit for bit: how close they are, measured |
| `requires` | ids of other definitions this one builds on **by reference**. A package carrying this definition carries each of those and lists it in `formats`: a pointer from one definition to another never leaves the package (law 1) |
| `normative_sources` | the standards restated, named for attribution only |
| `reference_tools` | `[{tool_id, language, entrypoint}]`: reference implementations in this package (below) |
| `test_vectors` | `[{id, description, input_bytes, input_sha256, output_form, output_bytes, output_sha256, input_file?}]` — at least one |
| `vector_files` | `[{path, sha256, bytes, role, vector?}]`, see below |

**Test vectors are what make it a definition and not a description.**
`output_form` states the canonical decoded form — sample order, row order,
bit depth, or for a container the exact listing — and `output_sha256` is the
sha256 of the decoded output in that form. An implementation built from the
document is checked by decoding each input and comparing hashes, or within
`tolerance` for a lossy format. A vector's **input** is carried in exactly one
of two ways:

* **printed** — in full, in a fenced block whose info string is
  `hex <vector id>` (lowercase hex, whitespace ignored), hashing to
  `input_sha256`. The default, and right up to a few kilobytes: the definition
  is then one self-checking text file;
* **as a declared vector file** — at `spec/formats/vectors/<format id>.<name>`,
  a file of a `core.spec` node, declared in the header's `vector_files` with
  its `path`, `sha256`, size in `bytes` and `role` (`input`,
  `expected-output` or `intermediate`); the vector names it in `input_file`.

A file under `spec/formats/vectors/` that no definition declares is an
undescribed binary inside the specification.

**Partial coverage is legal and must be exact.** A definition that covers the
container and not the bitstream says so, in `coverage_note`, specifically
enough that a reader knows for a given file whether the document suffices; a
reader that meets something the definition excludes refuses that payload by
name. What a definition may never be is an empty pointer to someone else's
standard, or a summary that claims to be complete: a provenance format
overstating what it has described is the failure this whole doctrine exists to
avoid.

**Reference implementations are a convenience and are `core.tool` nodes
(§3.17).** Each one the header names is a `core.tool` node whose `node_id` is
the `tool_id`: **source only**, never a prebuilt binary, and — because the
tool schema's `never_auto_execute` is a constant — **never run automatically
by any conformant tool**, §7.1 unchanged. Its contract, so that anyone can use
it to check their own codec: `<interpreter> <entrypoint> <input file>` writes
the canonical decoded output, exactly as `output_form` describes, to standard
output, and exits non-zero when it refuses the input. Where a reference and
its document disagree the **document** is the norm and the disagreement is a
bug in one of them, to be found by the vectors.

**Identity.** Within a package a format id names exactly one document. Across
packages an id is a name and the document a package carries is the authority
for that package — the same rule §2.2 gives a schema — which is what lets a
definition be revised (`format_version`) without invalidating a file already
written. Writers that share a library of definitions keep an id meaningful by
keeping its document byte-identical; that is good practice and a property of
the library, not a rule a reader can check.

**What a reader does.** A full reader does the part of this that needs no
codec, and reports it:

* every path in `formats` is a file of a `core.spec` node, in the container
  and matching its hash, with a `werk-format` header naming that id — else
  `format-definition-invalid` (`warn`);
* every printed test-vector input hashes to its `input_sha256`, and every
  declared vector file is in the manifest with the declared sha256 — else the
  same code;
* every id a definition `requires`, and every id a node names, is a key of
  `formats` — else `format-undeclared` (`warn`): the bytes are carried and
  verified, and the file does not say how to decode them;
* a file a node declares to be in a format matches one of that format's
  `sniff` alternatives — else `format-mismatch` (`warn`).

All four are warnings on purpose. The bytes are intact and hash-verified
either way, law 3 says a reader that cannot interpret a payload loses one
feature, and a reader that *can* decode the format is the one that will find
out whether the definition is right. A reader states how many definitions it
read and how many vector inputs it re-hashed. **A reader never decodes a
payload in order to validate a definition, and never runs a reference
implementation.**

**The base set is the same mechanism, older.** PNG, WAV, GLB, zip, JSON and
UTF-8 are defined in `MINI-SPECS.md`, which is the definition document of
those encodings in all but its header; a node whose type implies one of them
(`core.tex` is a PNG) need not name a format. Until this revision that
document stopped short of DEFLATE and said so; §7.1 of it now defines the
bitstream, so a PNG's pixels are decodable from this folder alone.

**Where a package written before this section put the map.** Both reference
manifest schemas were closed against an unknown top-level key, so a package of
`3d-entity/1` or `image/1` could not carry `formats`, and writers carried the
same map on a node instead, as `meta.format_definitions` (format id → path).
The schemas now admit `formats`, and writers use it. **A reader looks in the
manifest's `formats` first and in any node's `meta.format_definitions`
second**, so the packages already written keep resolving.

`fixtures/gsplat-v1.werk` exercises the mechanism in this repository: its
recipe's input medium is a `.splat` file, declared with
`file_formats: {"input-media": "splat-32"}` and defined by
`spec/formats/splat-32.md`, which is also the worked example of a definition
document.

### 3.19 The document revision log — `core.revisions` (base doctrine)

**Ruling 1 of 2026-10-13 (part c). Status: PROPOSED, pending Gregor's
ruling; the schema and both manifest schemas admit it.**
**`spec/schemas/core.revisions.schema.json`.** Applies to every profile.

Law 6 keeps versions **per node**. A document made of many nodes — forty
layers, three hundred paragraphs, a scene of twelve parts — also has to say
which version of each node belonged together at one Save, and the per-node
record cannot: after three Saves that each touched different nodes, "the
document as it was at the second Save" is not derivable from `versions[]`
arrays that only know their own node. Measured: three independently written
writers each built a log for exactly this and each put it somewhere a reader
of the core does not look — a base type of their own, an `x.*` scene node,
an `x.*` photo node. A reader that skips extensions then sees every node and
every version and cannot tell which belonged together. That is content, lost
silently, and it is why this is a core type.

* A package MAY carry **one** node of type `core.revisions`. Every Save
  appends one version to it. Version *N* of that node lists exactly one file,
  a JSON record, and the record's `revision` equals *N*.
* The record's `nodes` object maps `node_id` → the version number `v` of that
  node which the document uses at this revision, for every node that is part
  of the document at that revision except the revisions node itself.
* **The document now** is the record of the node's `active` version. A node of
  the package that is not a key of that record is not part of the current
  document — it was removed in an earlier Save; its bytes stay, because
  versions are append-only. For every node that is a key, the node's `active`
  equals the record's value.
* **The document at revision K**: read record K; for each key, read that node
  at that version.
* `kind` is `save`, `rollback` (with `restores`: the revision pointed back
  at), `set-active` or `compaction`. A rollback deletes nothing: it is a new
  revision whose `nodes` equal an earlier one's.
* The record's `note` is the work note of the Save, and the log is therefore
  the document's changelog (law 9).

A reader that finds no revisions node, or finds it dead, treats every node's
`active` version as the current document and reports that it did. A node's
`edges` and `meta` and the manifest's `parts[]` describe the **current**
document only; what must be recoverable for an earlier revision lives in a
payload file, which is versioned (§3.20 is that rule applied to placement).

Stated rather than hidden: a record names every node of the document, so its
size is linear in the node count and a library of 150 000 nodes writes a
four-megabyte record per Save. That is the price of a record that is complete
on its own — an island, readable without its predecessors — and it was chosen
over a delta chain, which is smaller and makes every revision depend on all
the earlier ones. §13 is the format's answer to very large documents.

### 3.20 Scene state — reflections, `core.scene`, and what stays in an extension

**Ruling 5 of 2026-10-13. Status: PROPOSED, pending Gregor's ruling;
implemented in the manifest schema, `schemas/core.scene.schema.json`, the
conventions map and the reference core's report. Profile-1 material, except
the last rule, which is base doctrine.**

The measured gap: a writer of `3d-entity/1` scenes had three things with no
place in the core — whether a part is shown and how (visible, an opacity, a
tint), the non-destructive edit layers of its application, and a part scaled
by a negative number — and put all three in an extension node. A reader that
skips extensions, which is every reader but that application, then draws a
hidden part, loses a tint, shows the unedited splat, and gets the absolute
value of a mirrored part with nothing to say it was mirrored. Law 3 promises
that skipping a node loses one feature. It did not mean "and shows something
its author never saw, without a word".

Three rules, the smallest that close it.

**1. A part's scale may be negative, and is never zero.** `parts[].transform
.scale` was required to be strictly positive, so a mirrored part — an entirely
ordinary thing: the left door is the right door reflected — could only be
written as its absolute value. A negative component is a **reflection** along
that axis. With an odd number of negative components the part's contents are
mirrored: a consumer drawing triangles **reverses the effective winding** for
that part and everything parented to it, and a consumer that does not
implement reflections reports `part-reflection-unsupported` (`warn`, value
scope) and says it drew the absolute value — it does not do so silently. Zero
stays illegal: a part is hidden by saying so (rule 2), not by collapsing it.
Every package written under the old rule is unaffected.

**2. `core.scene` — the versioned record of placement and display.** One JSON
node, at most one per package, named by `primary.scene`. Per part, by
`part_id`: its `transform` (TRS, the same shape as `parts[]`), `visible`, an
optional `opacity` multiplier 0..1 and an optional `tint_linear_rgb`
multiplier applied to linear colour. It exists for two reasons:

* `parts[]` has nowhere to say *hidden*. A consumer showing the scene as its
  author left it does not draw a part whose entry says `visible: false`. As
  everywhere in this format, that is a fact shipped and not a behaviour
  enforced (§3.12): what is required is honest reporting — a consumer that
  does not implement `visible`, `opacity` or `tint_linear_rgb` draws without
  them and reports `scene-display-unsupported` (`warn`, value scope) rather
  than presenting the result as the scene.
* `parts[]` is the manifest's **current** state and is not versioned, so the
  placement an earlier Save had was recoverable from nothing. `core.scene` is
  a node, so it has versions, a work note each, and a place in
  `core.revisions`.

Two statements of one fact, deliberately, with a stated winner: for the
node's **active** version each `transform` equals the same part's transform
in `parts[]`; where a reader finds them disagreeing, **`parts[]` wins for
placement** and the disagreement is a report entry — the rule §3.10 already
states for a GLB's own node transforms. A package without a `core.scene`
shows every part, opaque and untinted, where `parts[]` puts it, which is what
every package written before this section means.

**3. `meta.modified_by` — an extension that changes how a core payload is
shown says so on the core node. Base doctrine, every profile.** Edit layers,
deformers, procedural recolourings and shader graphs are an application's own
model; freezing one renderer's arithmetic into the constitution would be
exactly what law 12 gives the frontier for, and they stay `x.*`. What the
core owes its readers is not the edit but the *knowledge that there is one*:

> A core node whose payload is shown differently by its authoring application
> because of state held in other nodes lists those nodes' ids in
> **`meta.modified_by`** (an array of `node_id`). A reader that skips or loses
> a node named there reports `modified-by-skipped-node` (`warn`) for the core
> node: what it read is the unmodified payload, not what the author saw.

A writer that can afford it SHOULD also ship the result — a derived core node
holding the payload **as shown**, `measured`, with the unmodified node and the
modifying node as its `input_files` — because a reader then gets the picture
and not merely the warning. The declaration is what is cheap enough to
require, and it turns a silent loss into a reported one.

## 4. LOD selection metric

`core.geom.lod` nodes carry, in the manifest node's `meta`:
`lod_level` (1–4), `triangle_count`, `reference_resolution_px` (fixed at
1080) and `screen_space_error_px` — the maximum silhouette deviation from
`core.geom.game`, in pixels, when the entity's bounding sphere is rendered
at 1080 vertical pixels with a 60° vertical field of view. A selector
compares its own pixel budget against that number. It is a measurement, not
a hint, and it is why the metric names its reference resolution and field of
view instead of leaving them to the reader.

## 5. Versioning and degradation

Per manifesto laws 6 and 3 — normative text lives there; this profile adds:
files of coexisting versions are told apart on disk by an `@N` marker (below);
readers resolve through `nodes[].versions[]`, never by globbing.

**Where the `@N` marker goes — ruling 6 of 2026-10-13, PROPOSED; a writer
rule, base doctrine.** This paragraph used to read "version *directories* are
suffixed `@N` when multiple versions coexist on disk", which no writer ever
did: the one fixture with two versions of a file marks the *file name*
(`recipe/recipe@1.json`), and of the writers measured outside this repository
five put the marker on the superseded file and two on the new one. Both read
correctly — a reader goes through the manifest — and a format whose files look
different depending on who saved them has a rule missing. The rule:

> A **logical path** is a path with no `@` in it; it is the stable name of a
> file within its node. When a Save changes the bytes of a file, **the new
> bytes take the logical path and the superseded bytes move to
> `stem@N.ext`**, where `N` is the `v` of the version that *introduced* the
> superseded bytes. The marker goes before the last extension of the file
> name — `doc/body.json` → `doc/body@1.json` — and at the end of a name with
> no extension. It is part of the **file name**, never of a directory. The
> `files[]` entries of the earlier versions are updated to the moved path;
> their `sha256` and `size` never change. A file a later version did not
> change is listed again by that version with the identical path, hash and
> size (S-18) and does not move.

Why the superseded file moves and not the new one, since the opposite is
defensible and two writers chose it: the plain path then always names the
**current** bytes. `container.entry_order` and `container.preview_tier` list
exact paths, and under the opposite rule the preview tier of a document saved
twice names its first version for ever; a human who unzips the file finds the
current document under the name it has always had; and §12's recovery, which
has no manifest to ask, can say "the unmarked file is the newest" instead of
"the unmarked file is the oldest unless a marked sibling exists". The cost is
stated: an earlier version's `path` string changes once, at the Save that
supersedes it. "Old versions are never rewritten" (law 6) is a statement about
bytes and records — the hash, the size, the note, the producer, the stamp —
and a path is a location, which is why a file's identity in this format is
its sha256. A payload that names another file by *path* goes stale when that
file is superseded; payloads name **nodes**.

**Readers are unaffected, and no package becomes non-conformant.** A reader
never derives a version from a file name; a package written with the marker on
the newer file resolves through `versions[]` exactly as before and stays
valid. To find the file with logical path `L` in version `v`: take that
version's `files[]` and pick the entry whose path, with any `@<digits>` marker
removed from its file name, equals `L`.

If `active` is invalid, a resilient reader MAY fall back to the newest
valid earlier version and MUST report having done so. A `requires` edge into
a dead node kills the source node too; an `enhances` edge into a dead node
costs exactly one feature.

**Edge targets.** Every `edges[].to` names a `node_id` in the same
manifest's `nodes[]`. A writer MUST NOT emit an edge whose target is absent
from `nodes[]`. A writer that drops a node MUST also drop or rewrite every
edge into it. A reader MUST still handle a package that breaks this rule, and
it handles it on the path a dead target already takes. A `requires` edge to
an absent node kills the source node exactly as a `requires` edge into a dead
node does: the death propagates along `requires` edges to a fixed point, and
the reader reports `requires-missing-node` at severity `error` on the source
node. The source node's files are still size- and hash-checked and reported
(§10 step 6). An `enhances` edge to an absent node costs one feature, as one
into a dead node does, and is reported `edge-dangling` at severity `warn`. A
node that is *skipped* (§10 step 8) is not dead: its bytes are intact, so a
`requires` edge into it kills nothing. A skipped node whose own `requires`
edge kills it is reported both ways, `node-skipped-unknown-type` and dead.

| edge target | `requires` | `enhances` |
|---|---|---|
| alive | no effect | no effect |
| skipped (§10 step 8) | no effect | no effect |
| dead | source node dies: `requires-dead-node`, `error` | one feature lost: `enhances-dead-node`, `warn` |
| absent from `nodes[]` | source node dies: `requires-missing-node`, `error` | one feature lost: `edge-dangling`, `warn` |

A declared node that is not there is the same kind of failure as a declared
file that is not there (`file-missing`, `error`), and it degrades through the
same path (law 3).

## 6. Signatures

**`spec/schemas/signature.schema.json`.** Ed25519 (RFC 8032, pure), keys and
signatures as lowercase hex. The bytes an entry signs are exactly:

```
werk-sig/1 LF manifest_sha256 LF prev_entry_sha256 LF signed_at LF signer.uri LF signer.kind
```

UTF-8, LF line endings, no trailing newline. `manifest_sha256` here is **the
entry's own** `manifest_sha256` — every chain entry carries one — taken over
the exact bytes of `MANIFEST.json` as they stood when that signer signed,
never a reserialisation. The manifest hashes every other file, so one
signature covers that whole package state transitively.
`prev_entry_sha256` is 64 zeros for entry 0 and otherwise the sha256 of the
previous entry's `signature` string, which makes the chain immune to
reformatting.

**Per-entry, because enrichment appends (law 7).** A single shared anchor
would mean that the moment a package is enriched — one node added, the
manifest rehashed — appending a new link makes every *earlier* link fail
verification, which is the opposite of "enrichment appends; it never
overwrites earlier custody". So each signer signs the state in front of
them. Verification is therefore:

1. For each entry in order, rebuild the message from **that entry's** fields
   and check the Ed25519 signature and `prev_entry_sha256`.
2. Check that the **last** entry's `manifest_sha256` equals the sha256 of
   the `MANIFEST.json` bytes actually present, and that the file's top-level
   `manifest_sha256` equals it too (the top-level field is a convenience
   copy of the current anchor, never a second authority).
3. Earlier entries name manifest states that are no longer in the package.
   They are not re-checkable against bytes and a verifier MUST NOT report
   that as a failure. Successive entries may repeat a hash (two parties
   co-signing one state) or differ (enrichment re-anchored).

Honest limit, stated because a signature that is trusted for more than it
proves is worse than none: the chain has no external root of trust. It
proves that the named keys signed the named states. Whether a key belongs to
someone you trust is a question this file cannot answer, and §7.1's
"trusted in that tool, by the user" is the only place that question is
allowed to be answered.

The three states a conformant tool MUST surface distinctly:
**signed-and-valid** · **absent** (anonymous, and visibly so) ·
**present-and-invalid** (tampering under an existing signature). A tool that
collapses the last two into one warning has defeated the doctrine.

## 7. Embedded loaders — `core.loader`

Law 1 taken to its conclusion: a werk does not merely describe how to read
it, **it carries a working reader**.

`loaders/` holds single-file, zero-dependency reference readers:

| file | toolchain | dependencies |
|---|---|---|
| `loaders/werk_read.py` | python ≥ 3.8 | standard library only |
| `loaders/werk_read.rs` | bare `rustc`, no cargo | no crates |
| `loaders/werk_read.c` | any C99 compiler | C standard library only |

Each is a `core.loader` node with the usual `versions[]`, work note,
producer and epistemic stamp, and a `meta` block validated by
`manifest.schema.json` → `$defs/loaderMeta`. The block declares `language`,
`form`, `entrypoint`, `toolchain`, `build_command`, an honest `capabilities`
list (`read-manifest`, `verify-hashes`, `read-envelope`, `read-geometry`, …)
and `dependencies`, which **MUST be an empty array** — a loader with a
dependency is a promise about other files, which law 1 bans at the
constitutional level.

**A loader states its own capabilities, once, and writers read them from it —
ruling 8 of 2026-10-13, PROPOSED.** Each reference loader carries, in a
comment within its first 200 lines, one line of the form

```
WERK-LOADER-CAPABILITIES: read-manifest verify-hashes read-envelope materialize
```

and a writer that embeds the loader fills `meta.capabilities` from the bytes
it is embedding. Before this the list was typed by hand in nine places — each
loader's header and eight writers — and they disagreed: the Python loader said
six capabilities, every writer declared four for it, and the schema's enum
admitted neither of the other two, so a writer that copied the loader's own
list produced a manifest its own schema rejected (S-19 again, found by a
writer outside this repository). The enum now admits `summarize-points` and
`summarize-gsplat`, and the loader is the single authority on what the loader
does.

**What counts as a dependency**, since "C standard library only" and
"writes files to disk" cannot both be literally true: a **dependency is
something a consumer must acquire** — a package, a crate, a pip install, a
vendored third-party source file, anything not already present once the
named `toolchain` is installed. The platform's own headers, shipped with
every hosted implementation of that toolchain, are **not** dependencies:
nothing is fetched, nothing can be missing, nothing is a promise about
another file.

Concretely, and this is normative rather than a shrug:

* A loader MAY include platform headers **for the `materialize` capability
  only** — creating a directory and putting an already-open stream into
  binary mode are the two things the C standard genuinely does not provide.
  (`fopen(path, "wb")` *is* standard C and needs nothing; `mkdir` and
  `_setmode(_fileno(stdout), _O_BINARY)` are not.)
* Those includes MUST be behind a platform `#if`, MUST name in a comment
  which symbol each is for, and MUST NOT be reachable from any other
  capability. `werk_read.c` does exactly this: `<direct.h>`/`<io.h>`/
  `<fcntl.h>` on Windows, `<sys/stat.h>` elsewhere, four symbols in total.
* Every other declared capability MUST work in strict, hosted C99 with the
  standard library alone. A loader that cannot be built that way, minus
  `materialize`, is non-conformant.
* `dependencies` stays `[]`, and that is not a fiction: there is nothing to
  install.

(Recorded as Stage 2 spec finding S-8, resolved as Stage 1 decision 22.)

These are *bootstrap* loaders: read-only, simplified, enough to enumerate
the graph, verify hashes and pull payload bytes out. They are not the
reference implementation and are not expected to be fast.

### 7.1 Prebuilt binaries — normative safety rule

A package MAY carry prebuilt binaries (a `.dll`, `.so`, `.dylib`, `.exe`, a
`.wasm` module) as `core.loader` nodes with `form: "prebuilt"`. Then:

* A conformant tool **MUST NOT** execute, load, link, `dlopen`, JIT or
  otherwise run a prebuilt binary from a package automatically, under any
  circumstance, including when the signature chain verifies.
* A conformant tool **MUST** treat a prebuilt binary as inert data by
  default: it may hash it, list it, extract it and show its metadata.
* A tool **MAY** *offer* to run one only when **all** of the following hold,
  and it must show the user each of them: the signature chain is
  present and every link verifies; the signing identity is one the **user**
  has explicitly marked trusted in that tool, not merely one the package
  claims; and the user takes a deliberate, per-package action to allow it.
  The three-state doctrine of §6 applies unchanged — *absent* and
  *present-and-invalid* both mean "never offer".
* `prebuilt.built_from` MUST name the source entrypoint **in the same
  package** that the binary was built from, and
  `prebuilt.reproducible_build_command` SHOULD be present, so a suspicious
  consumer can rebuild and compare rather than trust.
* Source loaders carry no such restriction: they are text, a human or an
  agent can read them, and reading them is the point.

The asymmetry is deliberate. A format whose whole argument is "you can see
everything inside" must not become a delivery vehicle for something you
cannot see inside.

## 8. Extension: x.cub.v1 (informative)

The CUB engine's cooked tier, demonstrating law 12: interleaved
`BakedVertex` streams (144 B, declared per-field offsets), SH-L1 per-vertex
irradiance in the declared basis order (`conventions.sh_l1_order`),
per-triangle analytic shadow records, position-only streams for BLAS and
physics. Any other consumer skips `x.cub.*` and loses nothing but CUB's fast
path. An `x.*` binary uses the same envelope (§3.1) with a `WKX0`–`WKX9`
magic and MUST ship its own `*.layout.txt` inside the package.

## 9. Conformance (gate for v1.0)

1. **Agent gauntlet**: fresh agents, given one `.werk` and nothing else,
   produce working loaders (law 10). Measured: success rate,
   time-to-loader, feature coverage.
2. **Damage gauntlet**: corrupted node + unknown node type → everything
   else loads, skips reported precisely.
3. **Retarget test**: one calibration pose binds a foreign rig; a clip
   retargets with declared tolerance (`core.anim.clip` →
   `retarget.tolerance_rad`).
4. **Round-trip**: read → write → byte-identical re-emission of untouched
   nodes (hashes prove it).
5. **CUB ingest**: the proving-ground engine consumes core + x.cub with
   zero cook step.
6. **Self-containment**: an agent given only `spec/` answers every encoding
   question in a fixed question set without asking. This is Stage 1's gate
   and it is a measurement like the others.

## 10. Reader checklist

The short version of everything above, for someone writing a loader.

### 10.0 Two reader classes, because one checklist cannot fit both

A step marked **[F]** is a MUST for a **full reader** (werk-core and
anything of that weight: it may carry a JSON Schema validator and a
signature library). A step marked **[B]** is a MUST for a **bootstrap
loader** too — the single-file, zero-dependency `core.loader` readers of §7,
which cannot carry a schema validator or an Ed25519 implementation without
becoming the thing they exist to avoid. Every step is **[F]**; the **[B]**
marks say which subset a bootstrap loader must also do.

This split is not a licence to skip work quietly. A loader declares what it
actually does in `loaderMeta.capabilities`, the conformance harness runs
each declared capability, and a reader that omits a step it did not declare
is non-conformant. Undeclared silence is the failure; declared narrowness is
the design.

1. **[B]** Open the container (directory, or zip — `MINI-SPECS.md` §5; an
   entry is method 0 or method 8, §7.1; zip64 detection and refusal is §5.5,
   is required of every reader, and is done from the container's tail before
   anything else is read).
2. **[F]** Read `MANIFEST.json` and validate it — against the base schema the
   reader has built in, and against the profile's schema, which the manifest
   names and the package carries. §2.2 is the procedure and §10.3 says what
   it establishes. Recompute `spec_sha256` (§2). **[B]** Read `MANIFEST.json` and
   check structurally what you use: that the keys you read exist and have
   the type you assume, and that `werk.major` is one you support. Do not
   pretend a structural check is a schema validation — declare
   `read-manifest`, not a validation you did not do.
3. **[B]** Check every value in `conventions` against what you support.
   Refuse, do not guess — see §10.1 for what "refuse" means operationally.

   **The convention set is a property of the PROFILE, not of the reader —
   S-25, RULING, implemented.** A reader checks the set belonging to the
   profile the package declares. Against a profile it does not implement it
   MUST NOT report its own profile's conventions as missing: it emits one
   `unsupported-profile` entry, claims no payload meaning, and still lists,
   hash-verifies and extracts every file. This is not hypothetical — the first
   time a second profile existed, all three bootstrap loaders reported
   fourteen "missing convention" errors about a perfectly well-formed
   `image/1` package, because twenty-one values were baked in as a reader
   constant. Fixed in all three; recorded here so nobody re-derives it.

   **Not checking the profile's conventions is not the same as checking
   none — ruling 2 of 2026-10-13, PROPOSED.** The six **base conventions**
   (§2.2) are what a reader depends on to read any werk at all, so every
   reader checks them against itself in every profile, including one it has
   never heard of, and a mismatch there is `unsupported-convention`. The fix
   above had left the loaders checking *nothing* about an unknown profile,
   and the reference core refusing it *entirely*; both were wrong in opposite
   directions.
4. **[F]** If `SIGNATURE.json` exists, verify the chain (§6) and report
   which of the three states you are in. Load either way. **[B]** A
   bootstrap loader that does not implement Ed25519 MUST report the chain as
   *unverified* — a fourth word, distinct from all three states, meaning "I
   did not check" — and MUST NOT report `absent` for a file that is present
   or `signed-and-valid` for a signature it never checked. It declares
   `verify-signature` only if it really verifies.

   **The four words are fixed strings**, because a tool comparing them is a
   normal thing to write and three near-synonyms would defeat the three-state
   doctrine as surely as collapsing two states would. The state is exactly
   one of `signed-and-valid`, `absent`, `present-and-invalid`, `unverified`;
   the matching report codes are `signature-valid`, `signature-absent`,
   `signature-invalid`, `signature-unverified`. Prose around them is free;
   the token is not. (`present-unverified` was one embedded loader's
   spelling — recorded as S-19 and corrected.)
5. **[B]** Walk `nodes[]`. For each, take `active`, or the newest valid
   earlier version if `active` is broken — and report that you did.
6. **[B]** For each file: check `size`, check `sha256`. Mismatch → mark the
   node dead, log it, continue.
7. Dispatch by `type`: **[F]** JSON payload → validate against
   `schemas[type]`; **[B]** custom binary → recognise it by its frame and
   validate the frame, whatever its magic (§3.1), and parse it per
   `layouts[kind]`, including the envelope's section consistency rule;
   PNG/WAV/GLB → `MINI-SPECS.md`; **[F]** a file its node declares to be in
   another format → §3.18: check the declaration against the `formats` map
   and the definition, and hand the bytes over undecoded unless you implement
   that format. A bootstrap loader that does not validate JSON payloads
   still verifies their bytes against the manifest hash and still hands them
   over; it simply does not claim they satisfy their schema.
8. **[B]** Unknown `type`, or a type you chose not to implement → skip it
   and say so. Unknown-because-newer and broken degrade through the same
   path.
9. **[B]** Never follow a path that is not in some `files[]`. Nothing floats
   and nothing outside the package is ever fetched.
10. **[B]** Resolve edges (§5) after steps 6 to 8, to a fixed point. A
    `requires` edge into a dead node, or to a node absent from `nodes[]`,
    kills the source node (`requires-dead-node`, `requires-missing-node`,
    both `error`). A `requires` edge into a skipped node does not. An
    `enhances` edge never kills its source: into a dead node it is
    `enhances-dead-node`, to an absent node it is `edge-dangling`, both `warn`.

### 10.1 What "refuse, do not guess" means, operationally

Step 3's instruction was prose, and two conformant readers could read it two
ways. It is now defined, because a damage gauntlet cannot grade an
undefined verb.

**Refuse means: produce no interpreted value, produce a named report entry,
and continue with everything not affected.** It never means "exit". Refusal
has exactly three scopes, and a reader picks the smallest one that contains
the problem:

| scope | when | what still happens |
|---|---|---|
| **value** | one field you cannot interpret | everything else in that payload is still returned |
| **node** | the node's bytes, envelope or schema failed, or a `requires` edge points into a dead node or to a node absent from `nodes[]` (§5) | every other node still loads; law 3 |
| **container** | the bytes cannot be traversed at all: not a zip, no EOCD, a zip64 container in a zip32-only reader (`MINI-SPECS.md` §5.5), or `MANIFEST.json` missing or unparseable | nothing loads; this is the only scope that may be empty-handed |

A **`conventions` value you do not support is node-scoped, not
container-scoped**, and it applies to the nodes whose payloads that
convention governs. A reader that does not implement `quat_order: "wxyz"`
refuses the nodes carrying quaternions and still lists the graph, still
verifies every hash, still extracts every texture. The graph listing, the
hashes and the work notes are readable knowledge that no convention gates,
and law 9 says they earn their bytes for exactly this kind of consumer.

**Which nodes each convention governs — S-17, RULING, implemented.** The rule
above is right and no reader could apply it mechanically, because nothing said
that `quat_order` governs `core.pose.rest`, `core.skeleton` and
`core.anim.clip` and nothing else. It does now. Look up the convention, refuse
those node types, keep everything else. **The map also travels as data** —
see §10.2, which is the part of this ruling a reader can execute rather than
read.

| convention | governs | scope |
|---|---|---|
| `endianness` | every envelope binary: `core.field.flow`, `core.pose.rest`, `core.anim.clip`, `core.skeleton` (binary mirror only), `core.embedding`, `core.geom.points`, `core.geom.gsplat`, any `x.*` binary | node |
| `alignment_bytes` | the same set as `endianness` | node |
| `units_per_meter`, `length_unit` | `core.geom.*` (including `core.geom.points` positions and `core.geom.gsplat` means **and scales**), `core.phys.bounds`, `core.phys.colliders`, `core.phys.body`, `core.field.flow`, `core.skeleton`, `core.anim.clip` (root translation and any bone-translation section), `core.retarget.bind` (the solved stature scale), `core.imposter` (depth range), `core.destruct`, `core.props` (any length-valued property), `core.scene` (part translations) | node |
| `angle_unit` | `core.skeleton` (joint limits), `core.anim.clip`, `core.retarget.bind` (residuals and tolerances), `core.props` (any angle-valued property) | node |
| `time_unit` | `core.anim.clip`, `core.audio.package`, `core.audio.effect`, `core.audio.ambience`, `core.props` (any time-valued property) | node |
| `mass_unit` | `core.phys.body`, `core.destruct`, `core.props` | node |
| `up_axis`, `forward_axis`, `right_axis`, `handedness` | every node carrying a direction or a position in model space: `core.geom.*`, `core.phys.*`, `core.field.flow`, `core.pose.rest`, `core.skeleton`, `core.anim.clip`, `core.retarget.bind` (the solved basis rotation is source→**these** axes), `core.imposter`, `core.destruct`, `core.scene` | node |
| `winding` | `core.geom.source`, `core.geom.game`, `core.geom.lod`, `core.destruct` | node |
| `quat_order` | `core.pose.rest`, `core.skeleton`, `core.anim.clip`, `core.retarget.bind`, `core.geom.gsplat` (the per-Gaussian rotation stream), `core.scene` (part rotations) — **and `parts[].transform.rotation` in the manifest itself** | node, **plus part placement** |
| `oct_encoding_pole` | `core.imposter` (the octahedral normal channel), any `x.*` using octahedral encoding | node |
| `sh_l1_order` | **no core node today.** It is declared because `x.cub.*` and any other extension carrying L1 spherical harmonics needs it pinned, and a convention agreed on only once an extension arrives is a convention nobody agreed on | extension only |
| `color_space_default` | `core.tex`, `core.imposter`, `core.semantics` (the palette) — and only where the node does not declare its own `color_space`, which every conformant `core.tex` does, and which a `core.geom.points` `color` field is likewise required to do | node |
| `sh_coeff_order` | `core.geom.gsplat`. **Optional** (Stage 12); absence means `coefficient-major`, which `layouts/gsplat.layout.txt` §4 requires anyway | node |
| `sh_degree` | `core.geom.gsplat`, and **advisory even there**: the payload's own header declares the degree that governs it, and this is a package-level maximum a store can size a buffer with. A payload exceeding it is a reported disagreement, not a refusal | node, advisory |
| `uv_origin` | `core.geom.*` (`TEXCOORD_*`), `core.tex`, `core.imposter`, `core.material` (texture slots) | node |
| `text_encoding` | every text and JSON payload in the package, **including `MANIFEST.json`** | **container** |
| `id_case` | every id in the manifest and in every payload | **container** |
| `hash_algorithm` | every `files[].sha256`, every `input_hash`, `license.sha256` | **container** |
| `signature_algorithm` | `SIGNATURE.json` only. Refusing it is the `unverified` state of §10 step 4, not damage | signature chain |

Three rows are marked **container** on purpose: a reader that cannot do UTF-8,
kebab-case ids or sha256 cannot read the manifest at all, so its refusal is
container-scoped by the table above rather than node-scoped. That is a real
answer to a question the earlier prose left open, and it is why this table is
a design commitment rather than documentation.

The image profile has its own, shorter table: `spec/PROFILE-IMAGE.md` §6.

### 10.2 The map as data — `spec/conventions-map.json`

The table above is normative and a human can apply it. A reader cannot,
without transcribing it into a constant — which is precisely the mistake §10
step 3 already records: three bootstrap loaders once baked twenty-one
convention values in as reader constants and then reported fourteen "missing
convention" errors about a perfectly well-formed package from a second profile.
A table that only exists as prose gets copied into code, and a copy in code
goes stale silently.

So the map travels as data. **`spec/conventions-map.json`**, validated by
**`spec/schemas/conventions-map.schema.json`**, is the machine-readable form of
the §10.1 table: for each convention, the scope (`node`, `container`,
`extension` or `signature`), the node types it governs, and a note. The
manifest declares its path in the optional key **`conventions_map`**, exactly
as it declares `manifest_schema`, `schemas` and `layouts` — declared beats
derived, and deriving a filename is deriving.

**Absence means the profile's table** as printed in the vendored `SPEC.md`
§10.1, which is what every package written before the key existed means. The
JSON and the table are the same content and a package carries both; if they
ever disagree in a package, the **JSON in that package wins for that package**
and the disagreement is a report entry, because that is the copy a reader can
check.

A reader unsupporting `quat_order` therefore does: look the convention up in
the map, take its `governs` list, mark those nodes refused with
`unsupported-convention`, and load everything else. No transcription, no
constant, no staleness.

**Reporting.** Every refusal is one report entry with a stable machine code
(`unsupported-convention`, `unsupported-profile`, `hash-mismatch`,
`envelope-invalid`, `payload-schema-invalid`, `node-skipped-unknown-type`,
`requires-dead-node`, `requires-missing-node`, `enhances-dead-node`,
`edge-dangling`, `zip64-unsupported`, …), a severity (`info` / `warn` / `error`), and the node id or path it
concerns. Silence is not a refusal; an unreported skip is a bug.

**The codes are a closed vocabulary, and this is the list.** "…" at the end of
the sentence above is how four readers of one format came to print four
vocabularies (S-19, S-20, and again in 2026-10: the core reported a deflated
entry as `file-missing`). A reader that needs a code that is not here adds it
to this table in the same change; an extension's own codes begin with `x-`.

| code | usual severity | scope | meaning |
|---|---|---|---|
| `bad-container` | error | container | not a zip and not a directory, or the zip directory is malformed |
| `zip64-unsupported` | error | container | a zip64 container; nothing was read (§1, `MINI-SPECS.md` §5.5) |
| `manifest-absent`, `manifest-unparseable`, `manifest-structurally-invalid` | error | container | §12.1; a reader that implements §12 enters recovery instead |
| `schema-invalid` | error | package or node | the manifest fails a schema it was held against (§2.2) |
| `manifest-schema-unusable` | error / warn | package | the schema the manifest names is not named, not a `core.spec` file, not in the container, not the hashed bytes, or not a schema |
| `manifest-schema-revision` | info | package | the package carries another revision of a built-in profile's schema; its own copy was used |
| `spec-sha256-mismatch` | error | package | `spec_sha256` is not the digest of the `spec/` files the manifest declares |
| `unsupported-profile` | warn | package | the profile is not built into this reader; one entry, saying what was established (§10.3) |
| `unsupported-convention` | error | node or container | a convention value this reader does not implement |
| `file-missing`, `size-mismatch`, `hash-mismatch` | error | node | a declared file is absent, or is not the declared bytes |
| `zip-entry-unsupported` | error | node | a zip method other than 0 and 8, or an encrypted entry |
| `zip-entry-invalid` | error | node | a deflate stream that does not decode, or inflated bytes that disagree with the directory |
| `version-fallback`, `version-compacted` | warn / info | node | `active` was unusable and an earlier version was used; a version's bytes were compacted away |
| `node-dead` | error | node | no usable version; the reason is in the entry |
| `node-skipped-unknown-type` | warn | node | a type this reader does not interpret; bytes verified, nothing else lost |
| `requires-dead-node`, `requires-missing-node`, `enhances-dead-node`, `edge-dangling` | error / error / warn / warn | node | §5 |
| `floating-file` | warn | package | a file no node declares |
| `payload-schema-invalid` | error | node | a JSON payload fails the schema `schemas` names for its type |
| `payload-file-ambiguous` | warn | node | §2.1 rule 5 |
| `envelope-invalid` | error / warn | node | an envelope fails `ENVELOPE.layout.txt` §7, or (warn) its `kind` is not its node's type |
| `envelope-undeclared` | warn | node | a well-formed envelope whose kind has no grammar in `layouts` (§3.1) |
| `format-undeclared`, `format-definition-invalid`, `format-mismatch` | warn | node or package | §3.18 |
| `modified-by-skipped-node` | warn | node | §3.20 rule 3 |
| `part-reflection-unsupported`, `scene-display-unsupported` | warn | value | §3.20 rules 1 and 2 |
| `stale-derived-data` | warn | node | a declared `input_hash` is not the hash of the declared inputs |
| `signature-valid`, `signature-absent`, `signature-invalid`, `signature-unverified` | info / info / error / warn | signature chain | §10 step 4 |
| `prebuilt-not-executed` | info | node | §7.1 |

**Exit status, for a command-line reader**, so two implementations agree:

| status | meaning |
|---|---|
| 0 | the container opened and no report entry has severity `error` |
| 1 | the container opened; at least one `error` entry (a dead node, a hash mismatch, an invalid signature) |
| 2 | container-scoped refusal: nothing could be loaded |

A bootstrap loader, which reports dead nodes without failing the load
(below), returns 1 only when it is asked to (`--strict`) or when it refuses
the conventions; all four reference readers return **2** for a
container-scoped refusal, with the refusal's code at the start of the message.
Until ruling 9 of 2026-10-13 they did not agree: the core and two loaders
returned 1 for an unreadable container, and one loader returned 3 for
`--strict`. Status 2 is also what the reference tools return for a command
line they cannot act on; no package was loaded then either.

A `--strict` mode MAY promote `warn` to `error`, and MUST say that it did.
A load is never failed by damage alone: `open()` succeeds on a package with
dead nodes and the report says what died. A reader that throws away
ninety live nodes because one texture is corrupt has misread law 3.

### 10.3 What validating a package against its own schema establishes

**Ruling 2 of 2026-10-13, PROPOSED. Normative for what a reader may CLAIM.**

§2.2 has a reader validate a manifest against a schema that came out of the
package it is validating. That is the right design — it is what makes a
profile something a file can carry instead of something a reader must have
been told about — and it is circular, so what it proves has to be said
exactly. A signature trusted for more than it proves is worse than none (§6);
the same goes for a validation.

**It establishes:**

* that the manifest is a well-formed werk manifest of major version 1 — the
  **base schema**, which the reader holds itself and no package can loosen;
* that the manifest is **consistent with the schema the package ships**, and
  that the schema is the one the manifest hashes, a file of a `core.spec`
  node, covered by `spec_sha256` — so the package is internally coherent, and
  if it is signed, the signer signed *this* schema with it;
* through the per-file hashes, that every payload is the bytes the manifest
  declares; and where `schemas` names a schema for a node type, that the
  payload satisfies the schema *the package ships* for it.

**It does not establish:**

* that the schema is the one the profile's author published. A package can
  ship any schema under any profile name, including one that permits
  everything. Two packages claiming one profile may carry different schemas;
  `spec_sha256` and the schema's own sha256 are how a reader that cares
  compares them, and a reader that holds a copy it trusts validates against
  that (§2.2 step 3 does exactly this for the built-in profiles).
* anything about what the payloads **mean**. The profile's own conventions
  were not interpreted, its node types were skipped, and a consumer that goes
  on to interpret them is doing so on the strength of the profile's documents,
  which it should read, and not on the strength of this validation.
* that the reader **supports** the package. Support is decided by the
  conventions check against the reader's own values and by the node types the
  reader implements — never by a schema, the package's or the reader's.

**Therefore a reader:**

1. MUST apply its built-in base schema whatever the package says, and MUST
   check the six base conventions against itself.
2. MUST report a profile it does not have built in as exactly that — one
   `unsupported-profile` entry — and MUST say which schema it validated
   against and where that schema came from. It MUST NOT report such a package
   as "valid `<profile>`" without qualification, and MUST NOT present "the
   manifest validates against the package's schema" as "this is a conformant
   package of that profile".
3. MUST treat a schema from a package as **untrusted input**, like any other
   payload: bound its recursion (a `$ref` cycle is four tokens), bound the
   length of a string it will evaluate a `pattern` on, and report a keyword it
   does not implement once, as a constraint that was not checked, rather than
   ignore it silently or fail the manifest for it. Resolve no `$ref` that
   leaves the document, and fetch nothing.
4. MUST NOT let a package's schema *widen* what it accepts beyond the base
   shape, and MUST NOT execute, load or follow anything a schema, a format
   definition or a profile document names. They are text.

A bootstrap loader, which validates nothing, says so in the same entry: the
manifest names a schema and this reader did not validate against it.

## 11. Open items after Stage 1

Recorded rather than hidden:

* ~~The canonical humanoid and hands are `status: "draft"`.~~ **Ruled
  2026-08-08: `status: "approved"`, `canon_version: "1.0"`.** The numbers were approved with two
  corrections: the thigh/shin swap (ruling 8) and a base root bone at the
  origin with the pelvis parented to it (ruling 9, bone count 23 → 24). §3.5
  states both.
* ~~No golden sample `.werk` exists yet.~~ **Two conformance fixtures now
  exist** and one of them is very likely the file you are reading this
  inside. `tests/fixtures/crate.werk` is the minimal synthetic one (15 nodes,
  every custom-binary path exercised); `fixtures/crate-v1.werk` is the golden
  sample built from a real production asset (36 nodes, a complete audio
  family, no custom binaries at all). Both are reproducible from a committed
  builder. `spec/examples/` still holds a deliberately **abridged**
  `MANIFEST.example.json` and one real `WKRP` binary with an annotated hex
  dump, both regenerated by `spec/examples/make-examples.py`: model structure
  on those, never completeness. (A gauntlet reader found this bullet still
  claiming no fixture existed while the package's own `README.txt` called
  itself conformance fixture #1 — recorded as S-16.)
* Morphs/blend shapes, cloth cages and LOD-specific UV sets have no node
  family yet. They are additive when they arrive (law 12).
* The reference implementation is Stage 2: a Rust core (`cdylib` behind a C
  ABI `werk.h`), with C++ consuming header plus DLL and Python via `ctypes`
  over the same DLL — no pip dependencies. The `core.loader` bootstrap
  readers described in §7 are a separate, simpler thing and must not be
  confused with it.
* ~~Zip64 support is permitted but not exercised by any fixture.~~ **werk does
  not use zip64** (ruling 9 of 2026-10-13, PROPOSED; §1): a package past the
  zip32 ceiling is carried in directory form. The refusal is implemented in
  all four reference readers and measured against two real zip64 archives
  written by an unrelated tool — one of 70 001 entries, one of 4.06 GiB.
  Deflate reading, which the same sentence used to cover by implication, is
  implemented and has a fixture (§1).
* ~~Four rulings are `PROPOSED — draft-pending-Gregor`.~~ **All four ruled
  2026-08-08**; see the table at the head of this document. Two came back
  weaker than the draft proposed — `entry_order` is a SHOULD and
  `preview_prefix_bytes` is a hint — so an implementation that hardened either
  into a MUST is now stricter than the format and will reject conformant
  packages. That is the one place where "implement the proposal and expect the
  marker to disappear" was the wrong advice, and it is recorded rather than
  quietly corrected.
* **There are now two profiles.** `3d-entity/1` is this document;
  `image/1` is `spec/PROFILE-IMAGE.md`, whose manifest schema is
  `spec/schemas/manifest.image.schema.json`. §3.11-§3.13 (`core.recipe`,
  `core.disclosure`, `core.embedding`) are **base doctrine** shared by both
  and live here only because this is where the narrative spec lives; a third
  profile is the trigger to move them into a document of their own.
* **Three conformance fixtures now exist.** `tests/fixtures/crate.werk`
  (minimal synthetic, every custom-binary path), `fixtures/crate-v1.werk`
  (golden sample from a real production asset, no custom binaries) and
  `fixtures/ista-varun-v1.werk` (profile `image/1`: a real AI-generated image
  with its true recipe, a `core.disclosure`, and a `WKEM` envelope payload —
  built to close the gauntlet's declared fixture gap, which was that no
  handed-out fixture had ever exercised `ENVELOPE.layout.txt`).
* **Four conformance fixtures now exist** in `fixtures/`, plus the minimal
  synthetic `tests/fixtures/crate.werk`: `crate-v1.werk` (+ its damaged
  variant), `crate-tex-v1.werk`, `ista-varun-v1.werk` (profile `image/1`) and
  `humanoid-retarget-v1.werk`, the first to carry a `core.skeleton` and a
  `core.anim.clip`. All were rebuilt against this revision of the spec on
  2026-08-08 and every one carries `spec_sha256`.
* `x.c2pa.export` is a **stub**: a mapping written down, nothing implemented,
  nothing validated. `spec/X-C2PA-EXPORT.md` leads with a table saying so.
* **Stage 12 added four node types and two magics** — `core.geom.points`
  (`WKPC`), `core.geom.gsplat` (`WKGS`), `core.tool` and `core.tool.config` —
  and a fifth conformance fixture, `fixtures/gsplat-v1.werk`, built from a real
  captured Gaussian splat and carrying the source of the two tools that made
  it. What that fixture does **not** exercise, stated rather than implied:
  **`sh_degree` above 0**. Both splats available to the lab store the DC band
  only, so `sh-rest` is a present-and-empty section in the only real package
  that has one, and the degree-1..3 index arithmetic of
  `layouts/gsplat.layout.txt` §4 is exercised by a synthetic PLY in the Stage
  12 gate rather than by a shipped payload. A real degree-3 capture is the
  test that would earn it (finding **S12-6**).
* **`core.geom.points` has no LAS/LAZ ingester.** PLY is mandatory and
  implemented, ascii and binary, both endiannesses; LAS was scoped as optional
  in the Stage 12 brief and is not done. It is additive when it arrives
  (law 12) and needs no format change — the `fields` mechanism of §3.15 was
  designed against LAS's dimension list precisely so that it would not.
* **The 2026-10-13 entries leave these open**, each stated where it lives:
  * `core.scene` and reflections (§3.20) are in the schema and the core's
    report and are **implemented by no consumer**: no adapter in this
    repository draws a hidden part differently, and no fixture carries a
    `core.scene` node or a negative scale. They are a proposal with a schema,
    not a measured feature.
  * `core.revisions` (§3.19) is admitted by both manifest schemas and written
    by no builder in this repository; the packages that exercise it are the
    outside corpus's.
  * The nested form of a package carried as a payload (§13.2) is a question,
    not a rule.
  * **Canonical JSON does not pin how a non-integer number is spelled**
    (`MINI-SPECS.md` §3, rule 4). Measured: `1e-05` in one language's
    serialiser is `1e-5` in another's and `0.00001` in a third's, and `1.0` is
    `1` in the third. Every `input_params` in every fixture stays inside the
    values on which all of them agree; a writer in another language that does
    not will produce an `input_hash` two readers recompute differently. Filed
    as finding F-AC-3, **not fixed**: any fix changes what existing packages
    hash to, which is a ruling and not an edit.
  * The self-indexing recovery of §12 is still implemented by no reader.

---

## 12. Appendix: self-indexing recovery (S-17 extension, RULING, implemented)

**The rule this appendix implements:** a reader MUST be able to rebuild an
index of a package **from the container contents alone**, when
`MANIFEST.json` is missing, unparseable, or has been edited into disagreement
with the bytes. Everything so recovered is reported as **degraded** and is
never presented as if it had been declared.

This is not a licence to skip the manifest. §10 step 2 stands: a reader reads
the manifest and uses it. Recovery is what happens *after* the manifest has
failed, and it exists because the alternative — the container-scoped refusal of
§10.1, "nothing loads" — throws away a package whose payloads are all intact
because one JSON file was mangled by a text editor that helpfully re-encoded
it. Law 3 says an island survives its neighbours; the manifest is the one file
whose loss used to sink every island at once. It no longer does.

### 12.1 When to enter recovery

Exactly three triggers, and a reader MUST report which one fired:

| trigger | report code |
|---|---|
| `MANIFEST.json` absent from the container | `manifest-absent` |
| `MANIFEST.json` present but not parseable as UTF-8 JSON | `manifest-unparseable` |
| `MANIFEST.json` parses, but a **structural** key a reader needs is absent or of the wrong type (`nodes` missing, `nodes` not an array, `files` not an array) | `manifest-structurally-invalid` |

A manifest that parses and is structurally sound but fails **schema**
validation, or names a file that is not in the container, or carries a hash
that does not match, is **not** a recovery trigger. That is ordinary damage and
§10.1's node scope handles it: refuse the affected nodes, load the rest, and
keep using the manifest for everything else. Entering recovery there would
discard good declared knowledge in favour of guesses, which is strictly worse.

A reader MAY also be *asked* to recover — a `--recover` flag, an audit tool
comparing declared structure against recovered structure. That is the useful
case in practice, and a package that has never been damaged should produce a
recovery that matches its manifest. Where it does not, one of the two is wrong
and the tool has just found it.

### 12.2 The procedure

Six passes, in order. Each pass may only use what the passes before it
established; nothing here reads the manifest.

**Pass 1 — enumerate.** Walk the container: for a zip, parse the central
directory (`MINI-SPECS.md` §5), and if the central directory itself is
unreadable, scan forward for local file header signatures (`50 4B 03 04`) from
offset 0. For a directory, walk it. Record for every entry: path, uncompressed
size, and its sha256 over the actual bytes. This list is the recovered ground
truth, and every later pass only annotates it. Report `recovered-entries` with
the count.

**Pass 2 — recover the spec.** If `spec/` is present, it is the format's own
documentation and it is the first thing to trust, because law 2 put it there
for exactly this moment. Compute `spec_sha256` over the recovered `spec/` tree
by §2's algorithm and report it: a reader holding a known revision can now say
which spec these bytes were written against, without a manifest. If `spec/` is
absent the recovery continues, degraded further, and says so
(`recovered-without-spec`).

**Pass 3 — classify by payload magic.** Read the first four bytes of every
entry. These are self-identifying and are the strongest evidence in the
container:

| bytes | magic | node type | grammar |
|---|---|---|---|
| `57 4B 46 46` | `WKFF` | `core.field.flow` | `layouts/flowfield.layout.txt` |
| `57 4B 52 50` | `WKRP` | `core.pose.rest` | `layouts/restposes.layout.txt` |
| `57 4B 41 43` | `WKAC` | `core.anim.clip` | `layouts/animclip.layout.txt` |
| `57 4B 53 4B` | `WKSK` | `core.skeleton` (binary mirror) | `layouts/skeleton.layout.txt` |
| `57 4B 45 4D` | `WKEM` | `core.embedding` | `layouts/embedding.layout.txt` |
| `57 4B 50 43` | `WKPC` | `core.geom.points` | `layouts/points.layout.txt` |
| `57 4B 47 53` | `WKGS` | `core.geom.gsplat` | `layouts/gsplat.layout.txt` |
| `57 4B 58 30`–`57 4B 58 39` | `WKX0`–`WKX9` | a profile-defined or `x.*` binary; the header's `kind` says which | the `*.layout.txt` the package carries for that kind |
| `57 4B` + two of `A`–`Z` / `0`–`9`, none of the above | any other envelope magic | an envelope reserved after this reader was written; `kind` says which | the same (§3.1: recognised by its frame, never by this table) |
| `89 50 4E 47` | PNG | `core.tex` or `core.imposter` | `MINI-SPECS.md` §7 |
| `52 49 46 46` + `WAVE` | WAV | `core.audio.*` | `MINI-SPECS.md` §8 |
| `67 6C 54 46` | glTF/GLB | `core.geom.*` or `core.destruct` | `MINI-SPECS.md` §10 |
| `7B` / `5B` | JSON | a structured node — pass 4 decides which | — |

An envelope binary also carries its own header, and that header is a second,
independent statement of what the payload is: parse it per
`ENVELOPE.layout.txt`, and where it declares `payload_origin` or a section
table, that is recovered structure the manifest never had to be consulted for.
A magic a reader does not recognise is recorded as `unknown-payload-kind` with
the four bytes, never guessed.

**Pass 4 — classify JSON payloads by schema, then by path.** A JSON payload
that names a schema inside `spec/schemas/` identifies its own node type: map
the schema filename back to the type through the recovered `spec/` tree.
Failing that, validate the payload against each recovered schema in turn and
take a unique match; two matches or none is `payload-type-ambiguous` and the
entry stays typed only as "JSON". Path is the **last** resort and is recorded
as such, because directory names are a convention this appendix must not turn
into a load-bearing rule: `textures/` suggests `core.tex`, `audio/` suggests
`core.audio.*`, `materials/` suggests `core.material`. A type recovered from a
path is reported with evidence `path-convention`, and a consumer is entitled to
distrust it.

**Pass 5 — recover node grouping and versions.** Group entries into nodes:
files under one directory that a single schema and a single part cohere around
are one node; a `@N` path suffix (§5) is a version marker and recovers the
version number; sidecars beside a payload (a PNG and its JSON, a WAV and its
effect JSON) belong to the payload's node. Every recovered node gets a
**synthetic** `node_id` derived from its path and marked as synthetic, never
presented as the author's id — the author's ids are in the manifest and the
manifest is what failed. Where versions cannot be ordered, the recovery
declares one version and says the history was not recoverable
(`history-not-recovered`).

This is the pass that loses the most, and the honest statement is that node
identity and edges are **not** recoverable from bytes: `requires`/`enhances`
edges, `part_id`/`material_id` joins, work notes, producers, epistemic stamps
and `input_hash` chains exist only in the manifest. A recovery that invents any
of them is lying. It reports them as `not-recoverable`.

**Pass 6 — report, and mark everything degraded.** The output is a recovered
index with, per entry: path, size, sha256, recovered type, the **evidence**
that produced that type (`payload-magic`, `envelope-header`, `payload-schema`,
`path-convention`), and a per-entry confidence the reader is willing to state.
The index as a whole carries `degraded: true` and the trigger code from §12.1.

### 12.3 What a recovered index may and may not be used for

* It **MAY** be used to list, extract, hash-verify against itself, and decode
  payloads whose grammar was recovered. That is most of what a reader does.
* It **MAY** be diffed against a partially-readable manifest to show a human
  exactly where the two disagree. This is the audit use and it is the best one.
* It **MUST NOT** be written back out as a `MANIFEST.json` and presented as
  the package's manifest. A recovered index has no work notes, no producers, no
  epistemic stamps and no edges; emitting one as a manifest would replace a
  damaged record of what happened with a confident record of what is currently
  on disk, which is the single worst thing a format like this can do. A tool
  MAY write it to a **differently named** file (`RECOVERED-INDEX.json` is the
  suggested name), which no reader treats as authority.
* It **MUST NOT** be reported as signed, valid or verified under any
  circumstance. The signature chain signs the manifest's exact bytes; if the
  manifest is gone or altered, the chain's state is `present-and-invalid` or
  `absent`, and recovery does not change that. A recovered package is an
  anonymous package.
* Every consumer of it **MUST** be told it is degraded. Silence here is the
  same failure §3.12 clause 2 names for disclosure: absence reported as
  presence.

---

## 13. A package carried as the payload of another (base doctrine)

**Ruling 7 of 2026-10-13. §13.1 is PROPOSED as a statement of what the laws
already say. §13.2 is NOT a rule: it is a question about law 1 and law 2, put
to Gregor, with the reference's position stated and nothing implemented.**

The measured pressure: one manifest lists every version of every node and is
written whole on every Save. A photograph library of 50 000 pictures is
150 000 nodes; measured outside this repository, its manifest is 183 MB, and
rating one photograph — a kilobyte of content — rewrites all of it. The
proposal on the table is to make the library fifty nodes, each of which *is* a
package of a thousand photographs with a manifest of its own.

### 13.1 The complete form — what the doctrine says today

A node's payload may be a complete werk package in its single-file form. That
needs no new mechanism, only §3.18:

* The payload is in the format **`werk`** — this specification — and the node
  says so: `meta.payload_format: "werk"`. Where the enclosing package's
  `formats` map names a definition for `werk`, it is a short document that
  points at the `spec/` it travels in; the definition of a werk package is the
  specification every werk package already carries.
* The node SHOULD say what it holds, so the outer manifest can be browsed
  without opening the inner one: `meta.package: {"profile": …,
  "entity_uuid": …, "manifest_sha256": …}`.
* **The inner package is hermetic on its own (law 1).** It carries its own
  `MANIFEST.json`, its own `spec/` and `loaders/`, its own `LICENSE`, and its
  own `SIGNATURE.json` if it is signed. Copied out of the outer package byte
  for byte, it is a standalone `.werk` that every reader opens, with the same
  hashes and the same signature state.
* **It is an island of the outer package (law 3).** The outer manifest hashes
  it as one file; a damaged inner package is one dead node outside, and a
  damaged file inside it is one dead node *inside*. Its node ids, its
  versions, its revision log and its signature chain are its own: ids are
  unique within one manifest, an edge names a node of the same manifest, and
  nothing reaches from one manifest into another's nodes except by naming the
  outer node and then an inner node id as two values of a payload.
* **Custody composes (law 7).** The outer chain signs the outer manifest,
  which holds the inner package's hash, so it covers every byte inside; the
  inner chain is unchanged by being nested and by being taken out.
* A reader that does not follow nesting treats the node as what it is to the
  outer package: one verified file of a named format. A reader that does
  follow it states a depth limit and stops at it.
* The single-file form inside a single-file form is addressable by offset
  when both are store mode, and a nested package is bounded by the single-file
  ceiling (§1) while the outer one may be a directory.

The cost of the complete form is the one hermeticity always has and the
manifesto assigns to the companion store, not to the format: fifty inner
packages carry fifty copies of the specification and the loaders — about half
a megabyte each as measured outside this repository, 27 MB for the library
above — and fifty *thousand* of them, one per photograph, would carry 27 GB.

### 13.2 The deduplicated form — a question for Gregor, not a rule

The proposal made outside this repository is to let an inner package **omit**
a file it declares — in practice its `spec/` and `loaders/` — when the
*enclosing* package holds a file with the same sha256, and to have a reader
resolve the omitted file from the enclosing package by hash. The inner
`MANIFEST.json` and `SIGNATURE.json` are byte-identical in both forms; taking
an inner package out ("materialising" it) copies the inherited files back in
and yields the complete, standalone package.

**It is a law-1 and a law-2 question, and this document does not answer it.**
The two readings, as exactly as they can be put:

* *For.* The werk is the outermost file. Every question any part of it raises
  — including "where are the files this inner manifest declares?" — is
  answered inside that file, by a rule stated in that file, by content hash.
  Nothing is fetched and nothing is outside. The manifesto's *Companion*
  section already licenses exactly this arrangement for a store — dedup at
  rest, the per-file sha256 as the key, materialisation byte-exact and
  verified or failed — and the enclosing package is acting as that store for
  what it encloses.
* *Against.* Law 1's second paragraph is specific: "every materialized werk
  remains complete. Working copies are whole; the store is clever. **Never the
  reverse.**" A deduplicated inner package, cut out of its parent byte for
  byte by any tool that does not know this section — a zip utility, a file
  manager — is a `.werk` whose manifest declares files it does not hold, and
  law 2's "the knowledge to read the file travels inside the file" is then
  false of it. It fails loudly (every `core.spec` and `core.loader` node is
  dead with `file-missing`, every content node is intact) rather than
  silently, which is the best that can be said. And it makes "is this file a
  werk?" depend on where the file is, which no other rule in this document
  does.

**The reference position until it is ruled:** the complete form is the only
form a reference writer emits and the only form a reference reader resolves.
A reference reader that meets a deduplicated inner package reports its missing
files as what they are to it — `file-missing` — and resolves nothing from an
enclosing package. Three things a ruling *for* it would have to settle, since
they are not details: whether the inherited-file rule belongs in this document
(it must, if the three bootstrap loaders are to follow it — and they can only
ever be handed the inner file); whether the form gets its own extension or
`container.form` value so that a cut-out deduplicated package is *recognisable*
as incomplete instead of merely failing; and whether anything but
`core.spec` and `core.loader` files may be inherited. A ruling *against* it
changes one writer flag and no reader.

There is a cheaper measure that needs no ruling about law 1 and removes most
of the pressure that produced the proposal: a writer may keep a large
document in **directory form**, where a Save writes the files that changed and
one manifest. It does not shrink the manifest. §3.19 says what it costs to
keep a revision record complete, and that cost is the same question one level
down.

---

## 14. Writing a minimal valid `3d-entity/1` package (normative)

**Ruling 3 of 2026-10-13, PROPOSED.** Law 10 asks that an isolated
intelligence can *implement the format from the file alone*, and until this
revision every measurement of that and every sentence of this document was
about **reading**. Nothing here said how to write a package, and the first
tool that checked a third-party writer's output against the laws reported
exactly that, by name, as a gap in the reference specification.

**`spec/WRITING-3D-ENTITY.md`** is the normative walkthrough, and it travels
in this folder: the files a minimal package has, the manifest key by key, the
node and version records, how `spec_sha256` and `input_hash` are constructed
with checkpoints to compare against, the container, and the command that
checks the result. **`spec/examples/write_minimal_3d_entity.py`** does all of
it with the Python standard library and nothing else, taking the `spec/` and
`loaders/` it must carry from the package it was found in; the hashes the
walkthrough quotes are the ones that script produces, and a gate runs it and
verifies its output with the reference core and all three loaders
(`tests/run_gate_writing.py`). `spec/PROFILE-IMAGE.md` §10 and
`spec/WRITING-IMAGE.md` are the same thing for `image/1`.

What a profile's narrative owes its writers is part of the base doctrine from
here on: **a profile document carries a normative section whose heading
contains "Writing a minimal valid", with a worked example whose hashes a
stranger can reproduce.**
