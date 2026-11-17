# ArtCraft base rules — what every ArtCraft werk capsule shares

Status: **v1**. This document travels inside every capsule written by an ArtCraft
application, as `spec/CRAFT-BASE.md`. It is normative for every ArtCraft profile.

The werk manifesto's twelve laws govern everything here. `spec/SPEC.md` owns the
container (§1), the manifest (§2, §2.1), the binary envelope (§3.1), the base-doctrine
node types (§3.11–§3.13, §3.17), versioning (§5), signatures (§6), loaders (§7) and the
reader checklist (§10); none of that is restated. This document adds only what the
ArtCraft profiles have in common, and a profile's own document
(`spec/PROFILE-<NAME>.md`, named by `README.txt`) adds what is specific to one kind of
document.

If you hold only this file and need its content, start with `HOW-TO-READ.md` at the
package root. If you need to WRITE such a file, read §8 here and then the section
"Writing a minimal valid … capsule" of the profile document.

---

## 1. What is in the package root

```
MANIFEST.json     the only index: profile, conventions, nodes, versions, sha256 of every file
SIGNATURE.json    the signature chain (may be absent)
LICENSE           the full licence text of the document's content
README.txt        one page for a human who opened the file by hand
HOW-TO-READ.md    task-oriented: how to get THIS profile's content out
loaders/          werk_read.py, werk_read.rs, werk_read.c — zero-dependency readers
spec/             the format: SPEC.md, MINI-SPECS.md, this file, the profile document,
                  schemas/, layouts/, examples/, conventions maps
revisions/        one small JSON record per Save (§3)
…                 the profile's own directories
```

Every file except `MANIFEST.json` and `SIGNATURE.json` is listed in exactly one node's
`files[]`. Nothing floats, and nothing in the package refers to anything outside it.

The base nodes, present in every capsule, with these exact `node_id` values:

| node_id | type | files |
|---|---|---|
| `spec` | `core.spec` | everything under `spec/` (which files: §1.1) |
| `license` | `core.license` | `LICENSE` |
| `readme` | `core.readme` | `README.txt` (the payload, `payload_file`) and `HOW-TO-READ.md` (role `how-to-read`) |
| `loader-python`, `loader-rust`, `loader-c` | `core.loader` | one file each under `loaders/` |
| `revisions` | `core.revisions` | the revision records (§3) |

### 1.1 What `spec/` holds — and what it deliberately does not

`spec/` of this package holds, in full and unmodified, everything a reader or writer of THIS
package can reach:

* from the werk reference specification: `SPEC.md` (container, manifest, node model,
  versions, signatures, conventions, the reader's duties), `MINI-SPECS.md`, `README.md`,
  `layouts/ENVELOPE.layout.txt`, `schemas/signature.schema.json`,
  `schemas/conventions-map.schema.json`, the schemas of the base node types
  (`core.recipe`, `core.disclosure`, `core.provenance`, `core.semantics`, `core.tool`,
  `core.tool.config`), `layouts/embedding.layout.txt` for `core.embedding`, and the signature
  and embedding examples;
* this document, `schemas/core.revisions.schema.json`, and the profile's own documents,
  schemas, layouts, conventions map and examples;
* `formats/`: the definition documents of the formats in use (§6.1).

The reference specification also defines two profiles this package is not — `3d-entity/1`
and `image/1` — and `SPEC.md` and `README.md` describe their node families (animation,
skeleton, physics, audio, geometry, imposters, materials, facets, the `x.cub` extension) and
name the files that define them. **Those files are not in this package**: no node here is of
such a family, and a reader of this package cannot need them. So that a reference to one of
them is still answered inside the package, **`spec/NOT-CARRIED.md` lists every reference
file that was left out**, with its size, its sha256 in the reference tree, and what it
defines; it also names the sections of `SPEC.md` that concern only those families.

A writer may instead carry the whole reference tree; then there is no `NOT-CARRIED.md`.
Both are conformant. `spec_sha256` is always computed as `SPEC.md` §2 says: over the `spec/`
files this manifest declares — it identifies the specification THIS package carries, not a
canonical tree. A writer that appends to a package never removes a `spec/` file it finds.

## 2. Which schema validates the manifest, and which document describes the profile

`MANIFEST.json` → `manifest_schema` names it: `spec/schemas/manifest.<profile-name>.schema.json`.
It is the reference's profile-2 schema (the manifest schema of `image/1`; not carried, §1.1) with the
profile-specific parts replaced: the `profile` constant, the `conventions` block, the
`primary` slots, the list of `core.*` node types, and one addition to the version rules
(§5). `MANIFEST.json` → `conventions_map` names the machine-readable map of which node
types each convention governs. `schemas` maps each node type that has a JSON payload to its
JSON Schema; `layouts` maps each node type that has a custom binary payload to its layout
grammar. Never derive any of these paths from a naming convention — read them from the
manifest.

**Annotations in payload schemas.** A JSON Schema of this package may mark a string with one
of four `format` values; they are annotations (a validator that does not know them ignores
them) and they say what the string IS:

| `format` | the string is | a reader |
|---|---|---|
| `werk-node-ref` | a `node_id` of this package | resolves it in `MANIFEST.json`; it must exist |
| `werk-path` | a package-relative path | finds it in some node's `files[]`; it must be declared |
| `werk-provenance-note` | free text ABOUT an origin (where a file was imported from) | never follows it |
| `werk-content-text` | CONTENT that a person typed or a source file contained — a cell, a comment, a layer name, a work note | never follows it, whatever it looks like |

A string that looks like a local filesystem path (`C:\...`, `/home/...`, `file:...`) and
carries neither of the last two annotations is a reference out of the package: a law-1
failure. The annotation is per field and is a promise by the profile that no reader of that
field resolves it.

`MANIFEST.json` → **`profile_spec`** names the NARRATIVE specification of the profile: the
document a reader starts with, and the one that carries the normative "Writing a minimal
valid ..." section. A reader resolves it in this order and says which rule it used:

1. the manifest's `profile_spec`;
2. for the two reference profiles, whose closed manifest schemas have no such key, the
   reference's own narrative: `spec/SPEC.md` for `3d-entity/1`, `spec/PROFILE-IMAGE.md` for
   `image/1`;
3. for a package written before the key existed: the single `spec/PROFILE-*.md` whose text
   names the profile id. If there is none, or more than one, the narrative is unresolved and
   that is a law-2 failure.

The reference narratives of `3d-entity/1` and `image/1` carry no "Writing a minimal valid"
walkthrough. A conformance check reports that as a named **reference spec gap** — a finding
about the reference specification, stated in the report, neither a failure of the package nor
silently passed. A package closes the gap by carrying a supplement at
**`spec/WRITING-<PROFILE NAME, UPPER CASE>.md`** (`spec/WRITING-3D-ENTITY.md`,
`spec/WRITING-IMAGE.md`) as a file of its `core.spec` node: a markdown document that names the
profile id and has a heading containing "Writing a minimal valid". With it the check passes.

## 3. Document revisions — `core.revisions`

Law 6 keeps versions **per node**. A document made of many nodes also needs to say which
version of each node belonged to one Save. The node `revisions` says it.

* Every Save appends ONE version to the node `revisions`. Version `N` of that node lists
  exactly one file, a JSON record validated by
  `spec/schemas/core.revisions.schema.json`, and that record's `revision` equals `N`.
* The record's `nodes` object maps `node_id` → the version number `v` of that node which
  the document uses at this revision. It lists every node that is part of the document
  at that revision, and every base node except `revisions` itself.
* **The document NOW** is the record of the `revisions` node's `active` version. A node of
  the package that is not a key of that record is not part of the current document — it
  was removed in an earlier Save, and its bytes stay because versions are append-only.
  For every node that IS a key, the node's `active` equals the record's value.
* **The document at revision K**: read record K; for each key, read that node at that
  version (`nodes[].versions[]` entry with that `v`).
* `kind` is `save`, `rollback` (with `restores`: the revision pointed back at),
  `set-active` or `compaction`. A rollback deletes nothing: it is a new revision whose
  `nodes` equal an earlier one's, and every `active` pointer moves back.

A node's `edges` and `meta` in `MANIFEST.json` describe the CURRENT document only; they
are not versioned. Anything that must be recoverable for an earlier revision lives in a
payload file, which is.

A reader that finds the `revisions` node dead or absent treats every node's `active`
version as the current document and reports that it did.

## 4. Paths, and the `@N` version marker

* Every path matches `^[A-Za-z0-9][A-Za-z0-9._@/-]*$`: ASCII, forward slashes, no spaces,
  no `..` segment, at most 1024 characters. A user-facing name (a layer called
  "Hintergrund #2") is NEVER a path; it lives in the node's payload, and the path is a
  stable kebab-case handle.
* A **logical path** is a path with no `@` in it. It is the stable name of a file within
  its node.
* When a Save changes the bytes of a file, the NEWEST bytes take the plain logical path
  and the superseded bytes move to `stem@N.ext`, where `N` is the version number of the
  node that introduced them: `doc/body.json` becomes `doc/body@1.json`. The marker goes
  before the last extension of the file name; a name with no extension gets the marker
  at its end. This is the arrangement of the reference fixture (`recipe/recipe@1.json`).
* The `files[]` entries of EARLIER versions are updated to the moved path; their
  `sha256` and `size` never change. A file a later version did not change is listed again
  by that version with the identical `path`, `sha256` and `size` — one copy of the bytes,
  several versions pointing at it (SPEC.md §2, ruling S-18).
* To find the file with logical path `L` in version `v` of a node: take that version's
  `files[]` and pick the entry whose `path`, with any `@<digits>` marker removed from its
  file name, equals `L`. **Resolve through `nodes[].versions[]`; never glob the
  container.**

## 5. Epistemic stamps (law 5), as ArtCraft applies them

* Content a person made in the editor — a layer, a paragraph, a clip arrangement — is
  `authored`. A live editor state is not a file in the package, so nothing can be
  recomputed against it, and stamping it `measured` would be a false claim.
* A payload an application COMPUTED from other files of the same package — a flattened
  composite, a thumbnail, waveform peaks, extracted text, a cache — is `measured`. It
  carries `input_files` (ORDERED, each a path declared in this package), `input_params`
  (the computation's parameters; `{}` when there are none) and `input_hash`, constructed
  exactly as `spec/MINI-SPECS.md` §11 says: the concatenation, in `input_files` order, of
  each input's sha256 as 32 raw bytes, followed by the UTF-8 bytes of the canonical JSON
  of `input_params` — the two bytes `{}` when it is empty or absent. A reader recomputes
  it; a mismatch is `stale-derived-data`.
* Content a model produced is `inferred`, with the same three fields, plus — this is the
  one rule the ArtCraft manifest schemas add to the reference — a mandatory `confidence`
  (0..1) and a mandatory `producer.model`.

## 6. Encodings (law 11), and where cleverness may live

**The principle (ruling of 2026-10-12).** The self-describing part of each node is a format
declaration and definition from which a human or an AI agent can build a working codec. For
convenience a reference implementation in source form may additionally be included. The test
for a `core.*` payload is therefore not "a standard library can open it" but "**this package
carries a definition from which a codec for it can be built**".

A `core.*` node's payload is one of:

1. UTF-8 JSON with a JSON Schema in `schemas`; UTF-8 text. **A text payload is declared as
   text**: its entry in `files[]` has a `media_type` that is `text/...` (or an XML type). A
   reader goes by that declaration first — a file declared as text and holding valid UTF-8
   without a NUL character is text, even when its content happens to parse as JSON (a CSV
   whose only cell is `42`) or contains a control character such as a form feed;
2. PNG, WAV, GLB — the base set defined in `spec/MINI-SPECS.md` (a bare zlib or gzip stream is
   declared as format `zlib-deflate`, item 4);
3. a werk binary envelope (`spec/layouts/ENVELOPE.layout.txt`: raw little-endian arrays at
   declared offsets, magic `WKX0`..`WKX9` for the types an ArtCraft profile defines, the node
   type in the header's `kind`) with its layout grammar in `layouts`;
4. a **foreign-encoded original carried verbatim** — a JPEG, a TIFF, a font, an ICC profile,
   a metafile, a video or audio stream — in a format whose **definition document** travels in
   this package (§6.1).

**Floating-point sections hold finite values.** The envelope grammar forbids NaN and infinity
in a float section of a `core.*` node. A node whose samples may legitimately be non-finite
(an HDR layer) stores their IEEE-754 bit patterns in an integer section of the same width
(`u32` for binary32) and says so in its layout file and in a declared convention; that is the
sanctioned form, and it round-trips exactly.

Nothing else. Bytes with no definition in the package — a compressed blob in an
application's private packing, another vendor's undocumented chunk — are never a `core.*`
payload.

### 6.1 Foreign-encoded payloads and their format definitions

* `MANIFEST.json` → **`formats`** maps a **format id** (kebab-case, e.g. `jpeg`) to the path,
  inside this package, of that format's definition document: `spec/formats/<id>.md`. It is
  parallel to `schemas` and `layouts`, lists the formats of the nodes actually present (and
  the definitions those build on, `requires` below), and is
  absent when no node carries a foreign-encoded payload. The documents are part of `spec/` and
  so are covered by `spec_sha256`.
* A node whose payload is foreign-encoded says which format in **`meta.payload_format`**: a
  format id that is a key of `formats`. A node never changes format; a re-encoding in another
  format is a different node. The payload file's `media_type` is the format's media type.
* A node may also carry files that are NOT its payload in a foreign encoding — the input
  media of a recipe, an imported original kept beside its conversion. Such a file has a `role`,
  and the node says which format each such role is in with **`meta.file_formats`**: an object
  mapping a file role to a format id, e.g. `{"input": "ply-3dgs"}`. Every file of the node's
  version that carries the role is in that format. The ids are keys of `formats`, exactly as
  for `payload_format`; `formats` lists every format named either way.
* **A definition travels with its payloads, not ahead of them.** `spec/formats/<id>.md`, the
  vector files it declares and the `core.tool` nodes of its reference implementations are in
  the package exactly while some node of the package — in any version it still holds — names
  that format, or a definition in the package `requires` it. A package that holds no JPEG
  carries no JPEG definition, however many formats its profile admits. **The Save that adds
  the first payload of a format adds its definition, vector files and reference tools**, and
  the `formats` entry, in the same step (the `spec` node gains a version). The profile
  document names the format ids each node type admits; a writer takes the definition files,
  unchanged, from another package that holds the format or from the shared library the
  profile's software publishes (one id, one document). A profile may instead declare that its
  packages carry every definition it admits from the start; its profile document says so.
* **To decode such a payload:** node → `meta.payload_format` (or `meta.file_formats[<role>]`
  for a non-payload file) → `formats[<id>]` → read that document. Never infer the format from
  a file extension.
* **One id, one document.** A format id names exactly one definition document, byte for byte,
  wherever it appears. Two writers that carry the same format carry the same file; a writer
  that needs a different text uses a different id.
* **A package of a profile whose manifest schema has no `formats` property** (the two
  reference profiles `3d-entity/1` and `image/1` are closed against unknown top-level keys)
  cannot carry the map in the manifest. It carries the same map on each node that needs it, as
  **`meta.format_definitions`**: format id → path of the definition document, beside
  `meta.payload_format` / `meta.file_formats`. A reader looks in the manifest's `formats`
  first and in the node's `meta.format_definitions` second. Everything else in this section
  applies unchanged.

**A definition document** (`spec/formats/<id>.md`) is normative and self-contained: byte-level,
complete enough to write a decoder (and an encoder where the document says so), modelled on
`spec/MINI-SPECS.md`. It begins with a machine-readable header, a fenced block whose info
string is `werk-format`, containing one JSON object:

```
format_id        the id; equals the key in `formats`
format_version   1
title, media_type, extensions
sniff            how a payload is recognised from its first 64 bytes: a NON-EMPTY list of
                 alternatives, each either {"magic": [{"offset": N, "hex": "..."} ...]}  (ALL
                 listed byte strings present at their offsets) or {"rule": "zlib-header"}
                 (CMF & 15 == 8, CMF >> 4 <= 7, (CMF*256 + FLG) % 31 == 0).
                 A payload of this format matches at least one alternative.
                 A format with NO magic and no header (records from byte 0) says so with the
                 single alternative {"rule": "none", "note": "<why there is nothing to sniff,
                 at least 20 characters>", "size_multiple_of": N}; `size_multiple_of` is
                 optional and is the record size when records are fixed-size. Such a format is
                 always NAMED by the node (`meta.payload_format` / `meta.file_formats`) and
                 never guessed from bytes; the size rule is the one check the bytes allow.
                 An empty list is not a declaration and is refused.
defines          {"decode": bool, "encode": bool}: what the document suffices to build
coverage         "complete" or "partial"
coverage_note    mandatory when partial: exactly what is and is NOT defined
lossy, tolerance when two conformant decoders need not agree bit for bit: how close they are
requires         optional: the ids of OTHER format definitions this document builds on by
                 reference (a PNG's IDAT data is a zlib stream: "requires": ["zlib-deflate"]).
                 A package that carries this definition carries each of those as well, and
                 lists them in `formats`: a reference from one definition to another is
                 never a reference to something outside the package.
normative_sources  the standards restated (named for attribution; the document does not
                 depend on them)
reference_tools  [{tool_id, language, entrypoint}]: reference implementations in this package
test_vectors     [{id, description, input_bytes, input_sha256, output_form, output_bytes,
                  output_sha256, input_file?}]
vector_files     optional: [{path, sha256, bytes, role, vector?}] - see below
```

**How test vectors are carried — exactly two ways, and nothing else.**

1. **Printed.** The vector's INPUT is printed in full in the document, in a fenced block whose
   info string is `hex <id>` (lowercase hexadecimal, whitespace ignored), and hashes to
   `input_sha256`. This is the default and the right choice up to a few kilobytes: the
   definition is then one self-checking text file.
2. **As a declared vector file**, for an input too large to print (a font, a video frame), and
   for expected-output or intermediate data a builder of a codec benefits from. The file
   travels at `spec/formats/vectors/<format id>.<name>`, is a file of the `core.spec` node (so
   it is covered by `spec_sha256`), and is DECLARED in the header's `vector_files`: `path`,
   `sha256`, `bytes` (its size), `role` — `input`, `expected-output` or `intermediate` — and
   optionally `vector`, the id of the test vector it belongs to. A test vector whose input is
   such a file names it in `input_file` instead of having a hex block; that file has role
   `input` and its `sha256` equals the vector's `input_sha256`.

A binary file under `spec/formats/vectors/` that no definition document in the package
declares, or whose bytes do not hash to the declared `sha256`, is an undefined binary in a
`core.*` node: a law-11 failure. There is no third way — not a file "obviously" belonging to a
definition by its name, not a vector only a reference tool knows about.

`output_form` states the canonical decoded form (for example "width*height*4
bytes RGBA8, top row first") and `output_sha256` is the sha256 of the decoded output in that
form. **An implementation built from the document is checked by decoding each input and
comparing hashes** — or, for a lossy format, by comparing within the stated tolerance.

A definition that covers only part of a format says so (`coverage: "partial"` and the note);
a reader that meets something the definition excludes refuses that payload by name. A
definition is never an empty pointer to someone else's standard.

**Reference implementations** are optional and are a convenience; the definition document is
the norm. Each one the header names is a `core.tool` node of this package whose `node_id` is
the `tool_id`: SOURCE files only (`form: "source"`, never a prebuilt binary), with
`config.test_vectors` listing the vector ids it reproduces. Like every embedded tool it is
inert data: a conformant werk tool never runs it automatically (`spec/SPEC.md` §3.17, §7.1).
Its command-line contract is fixed: `<interpreter> <entrypoint> <input file>` writes the
canonical decoded output, exactly as `output_form` describes, to standard output, and exits
non-zero when it refuses the input.

### 6.2 Where cleverness and undefined bytes may live

An application's cooked or cached representation — a compressed tile pyramid, a GPU
texture, a waveform cache in the application's own packing — may be carried in an
`x.<app>.*` node, connected to the core node it accelerates by an `enhances` edge, with
a layout file in `spec/layouts/` saying what the bytes are. A reader that skips every
`x.*` node loses speed and nothing else. No `core.*` node may `requires` an `x.*` node.

A foreign block an application must preserve WITHOUT a definition (an unknown chunk of an
imported file, another vendor's private data) is carried verbatim the same way: an
`x.<app>.*` node whose layout file names the format and states that the bytes are opaque
and preserved. As soon as a definition document for it exists, it can be a `core.*` node.

## 7. Signatures (law 7) across Saves

`SIGNATURE.json` is an append-only chain; each entry signs the sha256 of `MANIFEST.json`
as it stood when that signer signed (SPEC.md §6). Consequences an implementer must not
invert:

* A changed PAYLOAD byte does not invalidate the signature. The manifest's per-file
  sha256 catches it: that node is dead (`hash-mismatch`), every other node loads, and the
  signature state is unchanged.
* A changed MANIFEST does (`signature-invalid`, state `present-and-invalid`) — and that
  includes an honest Save after signing that nobody signed. The remedy is to APPEND a
  chain entry over the new manifest; the earlier entries stay, keep verifying
  cryptographically, and are not re-checked against bytes that no longer exist.
* A reader reports exactly one of four fixed words: `signed-and-valid`, `absent`,
  `present-and-invalid`, `unverified` (it did not check).
* Compaction — removing the bytes of old versions — is never silent: the version keeps
  its record with `compacted: {at, by, reason}`, the removal is listed in
  `SIGNATURE.json` → `compaction_log` with the sha256 of everything removed, and a chain
  entry signs the result.

## 8. Writing a capsule without this software

Everything needed is in this package. In order:

1. Choose the files of your document's nodes as the profile document says, and compute
   each file's sha256 and size.
2. Copy `loaders/` and `spec/` from an existing capsule of the same profile unchanged
   (their content is the format; you are not expected to regenerate it; if your document
   holds a foreign-encoded payload whose definition that capsule lacks, add the definition
   as §6.1 says), plus a `LICENSE`
   with the full text of your content's licence — or an honest statement that the terms
   are not established — and a `README.txt` and `HOW-TO-READ.md`.
3. Write `revisions/revision.json` for revision 1 (§3): every node id of the package
   except `revisions`, each mapped to `1`.
4. Write `MANIFEST.json`: take the package's own manifest as the model. Every node gets
   `node_id`, `type`, `versions` (one entry, `v: 1`, with `files`, `note` of at least 8
   characters, `producer {tool, version}`, `epistemic`, `created`), `active: 1` and
   `edges`. Compute `spec_sha256` exactly as SPEC.md §2 says (over every `spec/` path the
   manifest declares). Validate the result against the schema `manifest_schema` names,
   and each JSON payload against the schema `schemas` names for its node type.
5. Container: either leave the tree as a directory, or zip it in STORE mode (method 0, no
   data descriptors, UTF-8 names) with `MANIFEST.json` first and the entries of
   `container.preview_tier` before everything else. `container.preview_prefix_bytes` is a
   hint and may be omitted.
6. Check your work with the reader in `loaders/`:
   `python loaders/werk_read.py <your file> --verify --strict` must exit 0.

A capsule written this way is accepted by every ArtCraft application's strict reader,
which validates the manifest and every payload against its own copy of the schemas and
refuses by the smallest scope that contains a problem (value, node, container —
SPEC.md §10.1).

## 9. Limits stated rather than hidden

* The single-file form is a 32-bit zip: members and offsets below 4 GiB, at most 65534
  entries. ArtCraft applications do not write ZIP64 and refuse a ZIP64 container by name
  (`zip64-unsupported`) without reading from it. A larger document is saved in directory
  form, which has no ceiling and is the same format.
* ArtCraft applications write store mode only and do not read deflated members; a
  method-8 member is reported `zip-entry-unsupported` and its bytes are never returned.
* `container.form` records the form the package was last written in and is advisory: a
  directory copy of a `.werk` file carries the identical `MANIFEST.json`, which is what
  keeps its signature valid.
