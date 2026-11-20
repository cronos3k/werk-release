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

**Definitions follow use.** What the PROFILE defines travels with what it defines, not
before:

* the schema, the layout grammar and the examples of a node type are in a package from the
  Save that writes the first node of that type;
* the definition of a format (§6.1), its vector files and its reference implementation are
  in a package from the Save that writes the first node naming that format;
* a definition a package has ever carried is never removed from it (the node may leave the
  document; its earlier versions are still in the package and still need their definition);
* a profile may mark a node type, or everything, as needed in every package — the types a
  stranger adds first, or a profile whose packages are grown by writers that hold nothing but
  the package; such definitions are then always there;
* a definition of at most 1024 bytes always travels.

So an empty drawing does not carry the schema of every kind of object it does not contain.
**A reader of a package never lacks a definition**: every node present has its schema, layout
or format definition present, and `schemas`, `layouts` and `formats` of the manifest name
them. What is absent is not needed to READ this package, and it is absent by rule, stated in
the package: **`spec/NOT-CARRIED.md` also lists every definition of the profile that was left
out**, with its path, its size, its sha256 and what it defines.

**A writer that wants to add a node of a type whose definition is not in the package** needs
that definition from somewhere: the sha256 in `spec/NOT-CARRIED.md` identifies the exact
file; it is in every package of the profile that holds such a node, and in the application
named by `generator` in the manifest. The Save that adds the node adds the file. The profile
document (`profile_spec`) describes every node type of the profile whether or not this
package has one, so what CAN be added is always known from the package alone.

A writer may instead carry the whole reference tree, and every definition of its profile;
with nothing left out there is no `NOT-CARRIED.md`.
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
of five `format` values; they are annotations (a validator that does not know them ignores
them) and they say what the string IS:

| `format` | the string is | a reader |
|---|---|---|
| `werk-node-ref` | a `node_id` of this package | resolves it in `MANIFEST.json`; it must exist |
| `werk-path` | a package-relative path | finds it in some node's `files[]`; it must be declared |
| `werk-file-sha256` | the sha256 (64 lowercase hex digits) of a FILE OF THE SAME NODE: how an index payload names the files it indexes, since a file's path gains the `@N` marker when it is superseded and its hash never changes | finds the file with that sha256 among the files of the node's version; it must be there |
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

**Convention values (law 8).** A convention is a machine value: a number, a boolean, a
token (ASCII letters, digits and `+ - . _ / :`, no white space, at most 64 bytes), a list of
those, or a TABLE — a list of rows, each row a list of those (a units-code table: `[[1,
0.0254], [4, 0.001]]`). Never deeper, never prose. A character that is not a token character
(a separator such as `|`) is stated as its code point, a number.

## 3. Document revisions — `core.revisions`

Law 6 keeps versions **per node**. A document made of many nodes also needs to say which
version of each node belonged to one Save. The node `revisions` says it.

* Every Save appends ONE version to the node `revisions`. Version `N` of that node lists
  exactly one file, a JSON record validated by
  `spec/schemas/core.revisions.schema.json`, and that record's `revision` equals `N`.
* A record is **full** or a **delta**, never both:
  * a FULL record has a `nodes` object mapping `node_id` → the version number `v` of that
    node which the document uses at this revision. It lists every node that is part of the
    document at that revision, and every base node except `revisions` itself;
  * a DELTA record has `base` — the revision number of an EARLIER record that is full — and
    `changed`, an object of the same shape holding only the nodes whose version differs from
    the base record's or which the base record does not list, and optionally `removed`, the
    node ids the base record lists that are not part of the document at this revision. **The
    document at a delta revision is the base record's `nodes`, with `changed` laid over it
    and `removed` taken out.** A delta never names another delta as its base, so any
    revision is resolved by reading at most two records.
  The first record of a package is full. A writer may write every record full; a writer of
  large documents writes deltas so that a Save which touched one node of 150,000 adds a
  record of a few hundred bytes instead of megabytes (the ArtCraft writer: a delta when the
  document has more than 256 nodes and at most one node in eight differs from the newest
  full record; otherwise a full record, which becomes the next base). A reader MUST accept
  both. A delta whose base is unreadable, is itself a delta, or is not an earlier revision
  is a damaged record: skipped and reported, never guessed.
* **The document NOW** is the (resolved) record of the `revisions` node's `active` version. A
  node of the package that is not a key of it is not part of the current document — it
  was removed in an earlier Save, and its bytes stay because versions are append-only.
  For every node that IS a key, the node's `active` equals the record's value.
* **The document at revision K**: read record K (and its base, if it is a delta); for each
  key of the resolved map, read that node at that version (`nodes[].versions[]` entry with
  that `v`).
* `kind` is `save`, `rollback` (with `restores`: the revision pointed back at),
  `set-active` or `compaction`. A rollback deletes nothing: it is a new revision whose
  `nodes` equal an earlier one's, and every `active` pointer moves back.

A node's `edges` and `meta` in `MANIFEST.json` describe the CURRENT document only; they
are not versioned. Anything that must be recoverable for an earlier revision lives in a
payload file, which is.

A reader that finds the `revisions` node dead or absent treats every node's `active`
version as the current document and reports that it did.

**Retired nodes.** A node that is no key of the current revision record has left the
document; its versions stay (law 6). If those versions are then compacted (SPEC.md §6:
explicit, signed, logged) — which is how removing a large file from a document makes the
package smaller — the node is **retired**: its manifest entry, its file hashes and sizes and
its work notes remain, every one of its versions up to `active` carries `compacted`, and its
bytes are in the package in no form. A retired node is not damage: a reader reports it as
retired (informational) and does not count it against the package. A revision that used a
retired node can no longer be materialised, and a reader says so when asked for it. A version
the CURRENT document uses is never compacted.

**A node another writer added.** Law 12 lets any writer add an `x.*` node of its own to a
package. Such a writer need not keep this log, so its node may be a key of NO revision
record. That node did not "leave the document": it never was in a revision. A reader treats
an `x.*` node that holds bytes and that no revision record lists as part of the current
document, at its `active` version; a compaction never treats it as removable; and the next
Save by a writer that does keep the log lists it in the new revision record, from when on it
is a node like any other (and may be dropped from the document by a later Save, knowingly).
A `core.*` node is always written by a writer that follows this document and is therefore
always in the log.

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
* A payload in a CONTAINER format holds streams in further formats — a movie file holds
  pictures in one codec and sound in another. The node names them in
  **`meta.contained_formats`**: an array of format ids, each a key of `formats`. Naming a
  format there is a use of it exactly like `payload_format`: its definition, the definitions
  it requires, its vector files and its reference implementations travel while a node names
  it. The key says WHICH definitions decode what is inside; which stream is in which format
  is the payload's own business, described by the container's definition or the node's
  payload schema. The same key serves a payload in a boring encoding whose MEANING a format
  definition gives (the raw groups of a DXF object kept as JSON: the node names `dxf`, and
  the document that says what group 330 means travels with it).
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

**Worked examples in a foreign format.** A file under `spec/examples/` that is in a foreign
format (a small JPEG that shows what a placed picture looks like) is admissible exactly when
the definition of its format is in the package: it is judged by that definition's sniff rule,
like a payload. The definition travels only while a node uses the format, so such an example
belongs to a node type's examples (which travel with the first node of that type, §1.1), not
to the examples every capsule of the profile carries.

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

### 6.3 Declared partial definitions

Law 2 asks that what a document uses is defined in the package. Where a profile carries a
catalogue of meanings (effects, blend modes, functions, operators) and cannot define every
entry a document uses, the honest form of the gap is a DECLARATION, in the file, with counts.
The node that carries the catalogue says in **`meta.definition_coverage`** — an array of
objects, one per kind of thing:

```json
[{"what": "effect definitions", "defined": 31, "within_tolerance": 2,
  "partial": ["morph-cut", "studio-reverb"]}]
```

`what` names what is counted; `defined` is how many of the things this document uses are
defined exactly (an implementation written from the definition reproduces the test vectors
bit for bit); `within_tolerance` how many are defined within the tolerance the definition
states; `partial` lists the ids of those that are used and NOT completely defined (their
parameters are carried, their arithmetic is not). The numbers describe THIS package, not the
application's whole catalogue. A conformance check prints the declaration with its counts as
a `noted` finding (`2.declared-definition-coverage`) — never a silent pass, and not by itself
a failure; a malformed declaration is a failure. A format definition's own `coverage:
"partial"` (§6.1) is the same idea for one format and is reported beside it.

### 6.4 An envelope inside a declared wrapper

A node may hold many files of one kind that are each a werk envelope, compressed: the bands
of a cell store, the tiles of a surface. The payload of such a node is a JSON index; each
band is a file with a `role`; `meta.file_formats` declares the role's format (§6.1), and
**`meta.file_inner`** declares what the file's bytes ARE once that format is decoded:

```json
"meta": {"file_formats": {"band": "zlib-deflate"},
         "file_inner":   {"band": "envelope:core.sheet.cells"}}
```

One inner form is defined: `envelope:<kind>` — the decoded bytes are a werk envelope
(`spec/layouts/ENVELOPE.layout.txt`) whose header `kind` is `<kind>`, satisfying every
assertion of that grammar's section 7, and for a `core.*` kind holding no NaN and no infinity.
The wrapper is one of the formats a checker can decode from its definition in this package;
today that is `zlib-deflate`. The node's type has a layout grammar in `layouts` (alongside its
schema in `schemas`) that describes the envelope's sections. A conformance check inflates
every such file and checks the envelope inside exactly as it checks a bare one
(`2.envelopes-parse`). The index names its bands by their sha256 (`format: werk-file-sha256`,
§2), not by path.

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

## 9. Limits and costs, stated rather than hidden

**What a Save costs.** `MANIFEST.json` is the one index and is written whole by every Save;
everything else is written only where it changed.

* Directory form: a Save writes the files that changed, moves the files they supersede to
  their `@N` names, and writes `MANIFEST.json`. Cost: what changed, plus one manifest.
* Single-file form: a Save writes a NEW zip — every member that stays is copied (not
  re-hashed, not re-compressed), in the physical order §1 prescribes — and replaces the old
  file atomically. Cost: the size of the file, sequentially, plus one manifest. The file is
  never appended to in place, for three reasons that are properties of the format and not of
  an implementation: `MANIFEST.json` is the FIRST member and the preview tier follows it
  (law 9: a reader of the first `preview_prefix_bytes` has the manifest and the preview), so
  a grown manifest cannot stay where it is; a superseded file changes its name to `stem@N.ext`
  and a zip member's name is stored in front of its data; and a single-file capsule is a
  pure function of its manifest (two writers given the same manifest produce the same bytes)
  — a file with dead regions and a history-dependent order is none of these. A document that
  is saved often and is large is kept in directory form while it is worked on and written as
  one file when it is handed over; or it is a capsule of nested capsules (§10).
* The manifest itself grows with the number of nodes and versions (about 1.2 kB per node as
  written here). A document of 150,000 nodes has a manifest of about 100 MB, read on every
  open and written on every Save. That is the scaling limit of ONE manifest; §10 is the
  answer to it.
* The single-file form holds at most 65,534 files (below).
* Validating a payload costs what its schema asks. In the validator this package's schemas
  are written for, a chain of `if`/`then` branches that dispatches on a `type` member is
  tried branch by branch for every item (30 kinds: 30 tests per item); a keyed union
  (`{"<kind>": {...}}` with `minProperties`/`maxProperties` 1) is one lookup. For arrays of
  many thousands of records, write keyed unions.
* A `pattern` in a schema is for short strings: ids, hashes, paths, dates. A reader may
  decline to evaluate a pattern on a very long string and then refuses that payload by name
  (`pattern-subject-too-long`) instead of evaluating it — the ArtCraft library does so above
  65,536 bytes for a pattern with one level of grouping, less for deeper ones. Bulk data
  (ten thousand numbers) belongs in a JSON array or in a binary section, not in one string
  under a pattern.
* A reader that takes a member out of the single-file form with a general zip library may
  get a container-level error for a damaged member (a CRC-32 mismatch) before it ever
  compares a sha256. That error is damage to the NODE that owns the member (law 3), not to
  the container: catch it per member and go on.

* The single-file form is a 32-bit zip: members and offsets below 4 GiB, at most 65534
  entries. ArtCraft applications do not write ZIP64 and refuse a ZIP64 container by name
  (`zip64-unsupported`) without reading from it. A larger document is saved in directory
  form, which has no ceiling and is the same format.
* ArtCraft applications write store mode only and do not read deflated members; a
  method-8 member is reported `zip-entry-unsupported` and its bytes are never returned.
* `container.form` records the form the package was last written in and is advisory: a
  directory copy of a `.werk` file carries the identical `MANIFEST.json`, which is what
  keeps its signature valid.

## 10. Nested capsules — PROPOSED, pending the ruling of the werk owner

**Status.** Everything in this section is implemented by the ArtCraft library and checked by
its conformance checker. The rule marked **(P)** below bends law 1 as the manifesto words it
and is therefore a proposal: until it is ruled on, a writer that wants no part of it writes
nested capsules in their complete form, which this section also defines and which bends
nothing.

**What it is.** A node may hold, as its payload, a complete werk capsule: a single-file
capsule (store-mode zip) with its own `MANIFEST.json`, its own nodes, versions and revision
log, and its own `SIGNATURE.json` if it is signed. Such a node:

* has a payload in the format `werk`, defined by `spec/formats/werk.md` of this package (so it
  is a defined `core.*` payload like any other foreign-encoded one, §6.1):
  `meta.payload_format` is `"werk"`;
* says what it holds in `meta.capsule`: `{"profile": <the nested capsule's profile id>,
  "entity_uuid": <its entity uuid>, "manifest_sha256": <sha256 of its MANIFEST.json bytes>}`
  — readable from the outer manifest without opening the nested capsule;
* is otherwise an ordinary node: one file, listed with its sha256 and size; versions; edges.

**Why.** One manifest lists every version of every node and is written whole on every Save
(§9). A library of 50,000 photographs is 150,000 nodes. Nesting leaves the manifest law as
it is and changes the shape of the document: the library has fifty nodes, each a capsule of
a thousand photographs with a manifest of its own. A Save that touches one photograph
writes one nested capsule and a small outer manifest; a reader opens the outer capsule and
only the nested capsules it needs, verifying each when it opens it.

**Reading.** A nested capsule is read where it lies: every member of a store-mode zip is a
contiguous range of the file that contains it, at any depth. A reader opens the outer
capsule, resolves the node, and reads the nested capsule's `MANIFEST.json` from the payload's
bytes; from there it is a capsule like any other. The outer manifest's sha256 of the payload
covers every byte the nested capsule stores, so verifying the outer capsule verifies the
inner ones as blobs, and a signature over the outer manifest covers them (a Merkle tree, one
level per nesting). Verifying a nested capsule's own files, node by node, happens when it is
opened.

**Identity.** A nested capsule has its own entity uuid; node ids are unique within one
manifest, not across them. An edge names a node of the SAME manifest. To refer from the outer
document to something inside a nested capsule, name the outer node that holds it and then the
inner node id, as two fields of a payload (`format: werk-node-ref` for the first); there is
no path syntax and no edge across manifests.

**Versions.** The nested capsule keeps its own history (law 6, inside it). The outer node
gets a new version whenever its payload changes, and the superseded payload stays in the
outer capsule like any superseded file — so the earlier state of a nested capsule is then
held twice: by the nested capsule's own versions, and by the outer node's earlier version.
Removing that second copy is a compaction (§3, SPEC.md §6): explicit, signed, logged. A
version of the outer node whose nested capsule is wholly contained in the current one (every
file it declares is declared, with the same sha256, by the current one) loses nothing when
compacted.

**The complete form.** The nested archive contains every file its manifest declares. Copied
out of the outer capsule byte for byte, it is a standalone `.werk` file. Fifty thousand of
them carry fifty thousand copies of the specification.

**(P) The nested form.** The nested archive contains `MANIFEST.json`, `SIGNATURE.json` if
present, and every declared file EXCEPT those the enclosing capsule already holds: a declared
file is left out exactly when the ENCLOSING capsule's manifest declares, in a node of type
`core.spec` or `core.loader`, a file with the same `sha256` and `size`. Content, licence and
README are never left out. The nested `MANIFEST.json` and `SIGNATURE.json` are byte-identical
in both forms: the nested capsule still DECLARES its specification and loaders, with their
hashes; it does not repeat their bytes.

* *Reading a nested-form capsule:* a declared file that is not a member of the nested archive
  is the file with the same sha256 among the files of the enclosing capsule's `core.spec` and
  `core.loader` nodes (any version whose bytes are present). Match by hash. A file found in
  neither place is missing and its node is damaged, reported for that node only.
* *Taking it out (materialising):* write a new single-file capsule with the nested manifest's
  members in the order it prescribes — own files copied, inherited files copied from the
  enclosing capsule, each verified against its sha256 — and `MANIFEST.json` / `SIGNATURE.json`
  unchanged. The result is a complete standalone capsule, byte-identical to what a standalone
  writer produces for that manifest, with the same signature state. If a file cannot be
  supplied the materialisation fails; an incomplete file is never written.
* *The enclosing capsule's duty:* it keeps every file a capsule nested in it takes from it.
  A compaction that would remove the only copy of such a file is refused.

**The argument, against the manifesto.**

* *Law 1 — "A werk answers every question it raises. No external references. No companion
  files."* The werk is the file. Every question any part of it raises — including "where is
  the specification this nested manifest declares?" — is answered inside the same file, by a
  rule stated in the same file, by content hash. Nothing is referred to that is outside the
  file; nothing has to be downloaded; there is no companion.
* *Law 1, second paragraph — "every materialized werk remains complete. Working copies are
  whole; the store is clever. Never the reverse."* This is the sentence the nested form
  bends. A nested-form archive, cut out of its enclosing capsule byte for byte, is NOT a
  complete werk: its manifest declares files it does not hold. The proposal's answer: a
  nested capsule is a payload, not a materialised werk — the same manifesto section gives the
  companion store exactly this licence ("dedups content-addressed storage at rest", "the
  manifest's per-file sha256 IS the store key", "materialization from the store is byte-exact
  and verified against the signed manifest, or it failed"), and the enclosing capsule is
  acting as that store for the capsules inside it. What leaves the enclosing capsule as a
  werk of its own leaves by materialisation and is complete. The risk it accepts: a tool that
  ignores this section and copies the payload out raw gets a capsule that reports its
  specification and loader nodes as missing files — loudly, per node, with every content node
  intact (law 3) — rather than a silently wrong one.
* *Law 2 — "The knowledge to read the file travels inside the file."* It does, once: the
  enclosing capsule carries the specification, the schemas and the loaders, and
  `spec/formats/werk.md` and this section say how the nested capsules use them. What a nested
  capsule's profile adds (its own profile document, schemas, layouts, format definitions) is
  not in the enclosing capsule's `core.spec` and therefore stays inside the nested capsule.
* *Law 3.* A damaged nested capsule is one dead node of the outer capsule; a damaged file
  inside a nested capsule is one dead node of the nested capsule.
* *Law 7.* The nested capsule's signature chain signs its own manifest and is unchanged by
  nesting and by materialising. The outer chain signs the outer manifest, which holds the
  payload's hash.
* *Law 11.* A store-mode zip inside a store-mode zip is addressable by offset and defined in
  this package; it is not a "clever" encoding.

**What a ruling against (P) would change:** writers store the complete form (one flag);
readers and the checker are unaffected, because a complete nested capsule simply inherits
nothing. What a ruling for it should also settle: whether the rule belongs in SPEC.md (so
that the three reference loaders can follow a nested capsule's inherited files), and whether
`core.license` may be shared the same way.

**Limits.** A reader follows nesting to a stated depth (the ArtCraft library: 8). A nested
capsule is a single-file capsule and has that form's limits (§9); the outer capsule may be in
either form.

## 11. Packages of the reference profiles (`image/1`, `3d-entity/1`) written by this library

An ArtCraft application whose document IS a werk reference profile — a photograph is
`image/1`, a 3-D asset is `3d-entity/1` — writes that profile under the REFERENCE's manifest
schema, unchanged (`spec/schemas/manifest.image.schema.json`,
`spec/schemas/manifest.schema.json`). The reference core and the reference loaders accept
such a package as their own. The reference schemas are closed where this document's rules
want room; what has no room there is said where there is room, and nothing is written that
the schema does not admit:

| this document | in a reference-profile package |
|---|---|
| the revision log, a `core.revisions` node (§3) | the same payload in a node `revisions` of type **`x.craft.revisions`** (schema `spec/schemas/x.craft.revisions.schema.json`). A reader that knows only the reference skips it as an extension and reads every node at its `active` version |
| `MANIFEST.json` → `formats` (§6.1) | the `spec` node's **`meta.format_definitions`**: format id → path of the definition document |
| a node's `meta.payload_format` (§6.1) | unchanged where the node's `meta` is open. Where the reference closes it (`core.image.source`, `core.image.derived`: the `imageMeta` object), the `spec` node's **`meta.node_formats`**: node id → format id. The node's own `meta.encoding` keeps the reference's vocabulary (`png`, `jpeg`, `webp`, `tiff`, `other`) |
| `MANIFEST.json` → `profile_spec` (§2) | absent. The narrative is the reference's (`spec/PROFILE-IMAGE.md`, `spec/SPEC.md`); the writing walkthrough it lacks travels as `spec/WRITING-<NAME>.md` (§2) |
| profile-declared conventions and `primary` slots | the reference's, exactly; none may be added |
| new `core.*` node types | none: a reference profile is extended in `x.<app>.*` only |
| definitions follow use (§1.1) | the whole reference `spec/` tree travels, as the reference writes it, plus this document |

Everything else in this document applies as written: paths and `@N` (§4), stamps (§5),
encodings (§6), signatures (§7), costs (§9).

What a reference profile cannot express today, and is therefore NOT written (each is a
request for a change to the reference specification, listed for its owner — none is worked
around by a field that pretends):

1. a `core.*` revision log (the `x.craft.revisions` node is skipped by a reference-only
   reader, which then cannot tell which versions belonged together at a Save);
2. `formats` in the manifest, and `payload_format` in `imageMeta` (a reference-only reader
   sees `encoding: other` and does not find the definition that is in the package);
3. `profile_spec`;
4. a `core.tool.config` whose tool is the application named in `producer` and not a
   `core.tool` node of the package (`tool_node` is mandatory);
5. an `inferred` stamp without a `confidence` where no probability is meaningful (a
   rendering that a model contributed to).

## 12. Shared base node types — PROPOSED, not yet in force

**Status.** A proposal for the profiles of the ArtCraft suite. Nothing in this section is
required of a package today, and no profile is changed by it. It lists what every profile
has, what each calls it now, and one name for each.

Every ArtCraft profile carries the same four things under different names, so a reader
written for one profile does not find them in a package of another:

| what | called today | proposed |
|---|---|---|
| the picture a listing shows | `core.vector.preview` under `primary.image` (vector-art), `core.preview.page` under `primary.preview` (rich-document), `core.raster.preview` (raster-layers), `core.layout.preview` under `primary.image` (layout) | **`core.preview.image`** — a PNG, sRGB, 8 bits per channel; `primary.preview` names it; `measured` or `inferred` with its inputs (§5) |
| the words of a unit, as plain text | `core.preview.text` (rich-document, layout) | **`core.preview.text`** — UTF-8 text; `primary.text` names the one for the whole document |
| an embedded font | `core.text.font` (vector-art, layout, raster-layers, drawing), one of the things `core.raster.source` holds (raster-layers, earlier) | **`core.text.font`** — one font file, foreign-encoded (`sfnt`, `woff`), `meta.payload_format` names the format; embedded only where its own embedding permission allows, otherwise listed by name and not carried |
| a placed raster image, and the original it was decoded from | `core.vector.image` + `core.vector.image-source` (vector-art, layout), `core.media.image` + `core.media.original` (rich-document), `core.raster.source` (raster-layers) | **`core.media.image`** — the decoded picture as PNG (`measured`, input: the original) — and **`core.media.original`** — the file as it came, foreign-encoded, `meta.payload_format` naming its format. The image `enhances` its original and lists it in `input_files` |

A profile adopting a shared type uses it exactly as defined here, lists it among its node
types, and keeps its own type names readable for the packages already written (a node never
changes type). The definitions — payload, meta, edges, the `primary` slot — would move into
this document; a profile document would then say only where the type occurs.

**A shared convention key.** Two profiles state how an exact binary32 number is spelled in
JSON, under one key with two values that mean the same thing (`json_binary32`:
`widened-to-binary64` / `shortest-decimal`); both round-trip. Proposed: the key
`json_binary32` with the single value `shortest-decimal-roundtrip` — "the shortest decimal
that parses back to the same binary32; a reader parses it as binary64 and narrows".
