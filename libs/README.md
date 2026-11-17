# werk libraries: read and write werk packages from any host

Every application that supports werk needs two things: **read** a package
(list it, verify it, take the payload out) and **write** one (a valid,
self-describing package that every reader accepts). This folder holds those
two abilities in three languages, plus a CLI in each. None of them has a
dependency to install:

| | what | runs on | dependencies |
|---|---|---|---|
| `python/werk/` | the Python package (`import werk`) and its CLI (`python -m werk`) | Python 3.7+ (tested on 3.8, 3.10, 3.11, 3.12); Python 2.7 (Cinema 4D R21 embeds 2.7.14), tested | standard library only |
| `python/werk_single.py` | the same code as one file, with the vendored `spec/` and `loaders/` inside it | the same | standard library only |
| `js/dist/werk.js` | the JavaScript library, Uint8Array bytes | Node 18+, Adobe UXP, browsers | none |
| `js/dist/werk.jsx` | the same core, ES3, binary-string bytes | Adobe ExtendScript (Photoshop, Illustrator, InDesign, After Effects, Premiere ...) | none |
| `werkc` (Rust) | the reference tool, with the release commands added | anything Rust builds for | the werk-core crate (`serde_json`, `sha2`, `ed25519-dalek`) |

The four writers produce **the same bytes** for the same input (the
cross-matrix in `tests/` proves it on every run), and every package they write
verifies under werk-core, the reference full reader, with its JSON Schema
validation, and under the three bootstrap loaders the package itself carries.

The normative ground truth is the `spec/` tree these libraries vendor (in
`bundle/`): `SPEC.md` §1, §2, §2.1, §5, §6, §7, §10, `MINI-SPECS.md`,
`PROFILE-IMAGE.md`, `WRITING-IMAGE.md`, `WRITING-3D-ENTITY.md`.

---

## Install / vendor

Nothing is installed from a network. Copy files into your plug-in:

* **Python host** (Blender, 3ds Max, Cinema 4D, GIMP, Unreal, Maya ...): copy
  `python/werk_single.py` next to your plug-in and `import werk_single as werk`.
  It is the whole library plus the embedded `spec/` + `loaders/` bundle
  (≈ 640 KB). Or copy the package `python/werk/` (code + `werk/bundle/`).
* **Node / UXP / browser**: copy `js/dist/werk.js`; `require("./werk.js")`.
  In UXP and browsers there is no `fs`: read with `werk.openBytes(bytes)`,
  write with `writer.toBytes()` (or pass your own `io` object, see `js/src/io-node.js`).
* **ExtendScript** (CC 2020 apps and older): copy `js/dist/werk.jsx` and
  `#include "werk.jsx"` (or `$.evalFile(new File(".../werk.jsx"))`). Files are
  read and written through `File` objects with `encoding = "BINARY"`.
* **Rust / command line**: `werkc` is in this repository's `core/`
  (release commands in `core/src/bin/werkc_rel/`):
  `cd core && cargo build --release --bin werkc`.

The bundle is the werk specification at one revision (`bundle/bundle.json` →
`source_rev`). To move every library to another revision of `spec/` and
`loaders/`:

    python tools/make_bundle.py --git <repo> --rev <commit>   # bundle/ + python/werk/bundle/
    python tools/build_single.py                              # python/werk_single.py
    python tools/build_js.py                                  # js/dist/werk.js, werk.jsx
    python tools/build_rust_bundle.py [<repo>]                # werkc's copy in core/src/bin/werkc_rel/ (default: this repository)

---

## Read a package — three lines

Python (3.7+, and 2.7):

```python
import werk
pkg = werk.open("thing.werk")                       # zip or directory form
node_id, path, png = pkg.primary_image()            # THE image: primary.image, by SPEC 2.1
print(pkg.verdict()["signature"], pkg.census())     # 'signed-and-valid' (alive, skipped, dead)
```

JavaScript (Node / UXP / browser):

```js
const werk = require("./werk.js");
const pkg = werk.open("thing.werk");                // or werk.openBytes(uint8array)
const { nodeId, path, bytes } = pkg.primaryMesh();  // THE mesh (a GLB), never files[0]
```

ExtendScript:

```js
#include "werk.jsx"
var pkg = werk.open("C:/assets/thing.werk");
var img = pkg.primaryImage();                       // img.bytes is a binary string
```

Command line (all four CLIs take the same commands):

```
python -m werk verify thing.werk          node js/bin/werk.js verify thing.werk
werkc verify thing.werk --json            python werk_single.py extract thing.werk out/
```

## Write a package

Python:

```python
werk.write_image_package("sunset.werk", png_bytes, name="Sunset", thumbnail_png=thumb,
                         recipe=None, disclosure=None)               # image/1
werk.write_mesh_package("crate.werk", glb_bytes, name="Crate",
                        textures=[{"id": "albedo", "png": albedo_png}],
                        materials=[{"id": "wood", "base_color": "albedo", "class": "wood"}],
                        preview_png=render_png,
                        sign_key=hex_seed, signer={"uri": "mailto:me@example.com"})  # 3d-entity/1
werk.append_version("crate.werk", "crate-v2.werk", "tex-albedo",
                    [werk.PackageWriter.file("textures/albedo.png", new_png)],
                    note="Albedo re-exported at 2K.")
```

JavaScript (same names in camelCase, an options object):

```js
werk.writeImagePackage("sunset.werk", png, { name: "Sunset", thumbnailPng: thumb });
const w = werk.buildMeshPackage(glb, { name: "Crate", textures: [{ id: "albedo", png }] });
const zipBytes = w.toBytes();                        // UXP: hand these to uxp.storage
```

Anything else (other node types, other profiles, measured derivatives) goes
through `PackageWriter` directly — see the API reference below.

---

## API reference

Python names are given; JavaScript uses the camelCase spelling of each (keyword
arguments become one options object), and the ExtendScript build has exactly
the JavaScript API with binary strings for bytes.

### Reading

| Python | JavaScript | what |
|---|---|---|
| `werk.open(path)` | `werk.open(path)`, `werk.openBytes(bytes)` | open a package (zip or directory). Raises `ContainerRefusal` (`.code` = `bad-container`, `zip64-unsupported`, `manifest-absent`, `manifest-unparseable`, `manifest-structurally-invalid`) only for SPEC §10.1's container scope; all other damage is in the report and the load succeeds |
| `pkg.verdict()` | `pkg.verdict()` | `{exit, profile, form, signature, nodes, alive, skipped, dead, dead_nodes, error_codes, envelopes, manifest_sha256, spec_sha256_ok, schema_validated}` |
| `pkg.report` | `pkg.report` | a list of report entries. Python: `werk.Entry` objects with attributes `.severity` (`info`/`warn`/`error`), `.code`, `.node` (node id or `None`), `.message`; `pkg.errors()` is the `error` ones. JavaScript: plain objects `{severity, code, node, message}`. Codes are SPEC §10.2's closed vocabulary |
| `pkg.signature_state` | `pkg.signatureState` | exactly one of `signed-and-valid`, `absent`, `present-and-invalid` (Ed25519 is verified, in pure Python / pure JS) |
| `pkg.nodes`, `pkg.node(id)` | same | `Node`: `node_id`, `type`, `status` (`alive`/`skipped`/`dead`), `resolved` (the version used), `versions`, `meta` |
| `pkg.payload_path(id, version=None)` | `pkg.payloadPath(id, v)` | SPEC §2.1's ordered rules (`payload_file`, single file, role `payload`, the type's payload role); raises `payload-file-ambiguous` instead of taking `files[0]` |
| `pkg.read_payload(id, version=None)` | `pkg.readPayload(id, v)` | the bytes of that file |
| `pkg.read_file(path)` | `pkg.readFile(path)` | one declared file; an undeclared path is refused (step 9) |
| `pkg.primary(key)` | `pkg.primary(key)` | `(node_id, fell_back)` for `image`, `mesh`, `thumbnail`, …: `primary.*` or the documented fallback |
| `pkg.primary_image()`, `pkg.primary_mesh()` | `primaryImage()`, `primaryMesh()` | `(node_id, path, bytes)` |
| `pkg.extract(out_dir, node_ids=None, all_versions=False)` | `pkg.extract(dir, ids, all)` | materialise files; returns the paths written |

What the Python and JavaScript readers do: every [B] step of SPEC §10 (both
zip methods 0 and 8, zip64 refused from the tail, and the six reader rules
for a damaged container of `MINI-SPECS.md` §5.4: the EOCD is the highest record
whose comment length is exact, the directory is walked by its record count,
names are decoded lossily (a damaged name is a `file-missing`), bit 3 refuses
and bit 0 is per entry, two entries of one name refuse the container
(`bad-container`, exit 2), and the central directory is the authority with the
local header giving only its signature and lengths; SPEC §6's signature rules:
`SIGNATURE.json` present but unreadable or without `algorithm` is
`present-and-invalid`, a foreign `algorithm` is `unverified`; SPEC §12.1's
node rule: a node without a string `node_id`/`type`, an integer `active`, a
non-empty `versions[]` of objects with integer `v` and a `files[]` of objects
is dead and the rest loads; a `files[]` entry without a string `path`, a string `sha256` or an
integer `size` makes its node dead (SPEC §12.1); `werk.major` other than 1 is an error entry, not a
refusal. Also conventions per profile and
the six base ones for any other profile, per-file size and sha256 with node
quarantine and version fallback, `requires`/`enhances` propagation, envelope
frames, floating files, `x.*` skipped and reported), plus from the [F] list
Ed25519 chain verification, `spec_sha256` recomputation
(`spec-sha256-mismatch`) and `input_hash` staleness (`stale-derived-data`).
What they do **not** do: JSON Schema validation of the manifest or of payloads
— `verdict()["schema_validated"]` is `false` to say so. `werkc verify` does it.

### Writing

`PackageWriter(profile, name, summary=None, uuid=None, created=None,
conventions=None, generator=None, producer=None, license_text=None,
spdx_id=None, readme_text=None, manifest_schema=None, profile_spec=None,
spec_files=None, conventions_map=None)`

* `profile` `image/1` and `3d-entity/1` are built in (conventions, schema
  path, conventions map). Any other profile needs `conventions=` and
  `manifest_schema=` (SPEC §2.2).
* `spec/` and the three `loaders/` are carried byte for byte from the bundle,
  with their `core.spec` / `core.loader` nodes; `LICENSE` defaults to an honest
  "terms not established" text and `README.txt` to a short note (both nodes).
* `w.file(path, data, media_type=None, role=None)` — one file of a node. Paths
  are checked against the manifest schema's `$defs/path` (ASCII, no `..`).
  `data` may be `werk.LocalFile(path)` to stream a large file (directory form).
* `w.add_node(node_id, type, files, note, epistemic="authored", producer=None,
  meta=None, edges=None, input_files=None, input_params=None,
  payload_file=None, part_id=None, material_id=None, confidence=None)` — the
  work note is mandatory (8–2000 characters); `measured` / `inferred` need
  `input_files` and get their `input_hash` computed (MINI-SPECS §11);
  `payload_file` is set automatically when one file has role `payload`;
  `schemas` / `layouts` entries are added for types the bundle has them for.
* `w.add_spec_file(path, data, media_type=None)` (JS `addSpecFile`; CLI
  `--spec-file spec/PATH=FILE`, repeatable; constructor `spec_files={path: bytes}`
  / JS `specFiles`) — carry a specification file the bundle does not have (a
  profile narrative and schema such as raster-layers/1, a format definition
  under `spec/formats/`) or replace a vendored one. Paths start with `spec/`.
  The file becomes part of the `core.spec` node (files kept sorted by UTF-8
  path), so it is hashed, verified and covered by `spec_sha256`; returns
  whether it replaced a bundled file. Point `manifest_schema=`, `profile_spec=`,
  `set_schema()`, `set_layout()`, `set_format()` at it as the profile requires.
  This is the supported route for profiles outside the bundle — do not build
  manifests by hand through the internal `write_container`.
* `conventions_map="spec/…json"` (JS `opts.conventionsMap`; CLI
  `--conventions-map spec/PATH`) — the manifest's `conventions_map` (SPEC
  §10.2) for a profile whose map is not the bundled one. It must name a
  `spec/` file the package carries (bundled or via `add_spec_file`); writing
  refuses otherwise. Default (`None`): the built-in profile's map, when present.
* `w.add_readme_file(path, data, media_type=None)` (JS `addReadmeFile`; CLI
  `--readme-file PKGPATH=FILE`, repeatable; helpers `readme_files=[(path,
  bytes)]` / `readmeFiles: [[path, bytes]]`) — add a file such as
  `HOW-TO-READ.md` to the `core.readme` node beside `README.txt`. The version
  then declares `payload_file: "README.txt"`, so the node's payload stays
  determinable (SPEC §2.1); files keep the order they were added in.
* `w.set_primary(key, node_id)`, `w.add_part(...)`, `w.add_material(...)`,
  `w.set_schema/set_layout/set_format(...)`, `w.preview(path)` (place an exact
  path in the preview tier, early in the zip).
* `w.sign(secret_key, uri, kind="human", name=None, role="author", note=None,
  signed_at=None)` — Ed25519 (pure Python / pure JS), SPEC §6 message;
  `kind` is `human`, `agent` or `service`. Several calls co-sign.
* `w.write(out, form=None)` — `.werk`/`.zip` → store-mode zip, otherwise
  directory form; `w.to_bytes()` → the zip in memory.
* Helpers: `write_image_package(out, png, name, …, thumbnail_png=None,
  thumbnail_params=None, recipe=None, disclosure=None, epistemic="authored",
  model=None, input_files=None, sign_key=None, signer=None, attachments=None)`
  and `write_mesh_package(out, glb, name, …, textures=None, materials=None,
  preview_png=None, …)`. The recipe and disclosure objects are written as given
  and must satisfy their schemas (`core.recipe`, `core.disclosure`).
* `append_version(src, out, node_id, files, note, …, node_type=None,
  sign_key=None, drop_signature=False)` — SPEC §5: the new bytes take the
  plain path, the superseded bytes move to `stem@N.ext`, earlier records keep
  hash and size, unchanged files are relisted. With `node_type` and a new id it
  adds a node. A signed source needs a key (a new chain entry) or
  `drop_signature=True`; it is never silently left `present-and-invalid`.
* `sign_package(src, out, secret_key, uri, …)` — append a chain entry over the
  current manifest without touching it.

### Command line

```
werk info    <pkg>
werk verify  <pkg> [--json] [--strict]
werk extract <pkg> <out-dir> [--node ID ...] [--all-versions]
werk cat     <pkg> <path> | --payload NODE [--version N]
werk pack-image <out> --png F --name N [--summary S] [--uuid U] [--created T] [--thumb F]
                [--recipe F.json] [--disclosure F.json] [--model M --epistemic inferred --input PATH]
                [--license F] [--spdx ID] [--attach ID:TYPE:PKGPATH=FILE ...] [--dir]
                [--sign-key HEX|FILE --signer-uri U --signer-kind K --signer-name N]
                [--spec-file spec/PATH=FILE ...] [--conventions-map spec/PATH] [--readme-file PKGPATH=FILE ...]
werk pack-mesh  <out> --glb F --name N [--texture ID=F[:usage] ...] [--material ID[:TEXTURE-ID] ...]
                [--preview F] (+ the common options)
werk append  <pkg> <out> --node ID --file PKGPATH=FILE ... --note TEXT [--type T] [--created T]
                [--sign-key ... | --drop-signature]
werk sign    <pkg> <out> --sign-key HEX --signer-uri U [--signer-kind K] [--signer-name N] [--signed-at T]
```

`werk` is `python -m werk`, `python werk_single.py`, `node js/bin/werk.js`,
`node js/bin/werk-es3.js` or `werkc`. Exit status (SPEC §10.2): **0** opened, no
`error` entry; **1** opened with `error` entries (dead node, hash mismatch,
invalid signature) — or a write that was refused; **2** container-scoped
refusal (nothing loaded) or a command line that cannot be acted on.
`--strict` promotes warnings and says so.

---

## The determinism contract (why the bytes are equal)

For identical input every writer emits identical bytes. What that takes, so a
fifth implementation can join:

* **JSON files**: two-space indent, `": "` after a key, `,` + newline between
  items, `[]`/`{}` for empty containers, keys in insertion order, non-ASCII
  written as UTF-8, escapes only for `"` `\` and U+0000–U+001F (`\b \f \n \r \t`,
  else `\u00XX`), one trailing LF — what Python's
  `json.dumps(v, indent=2, ensure_ascii=False) + "\n"` gives.
* **Numbers**: integers as integers; a non-integer (or a number spelled with
  a fraction or exponent in the input, such as `1.0`) in **Python `repr`
  spelling**: shortest round-trip digits, ties to even, fixed notation for
  decimal exponents −4…15, else `d.ddde±XX`. JavaScript keeps `1.0` apart
  from `1` with `werk.WFloat`; the ES3 build computes the digits with exact
  integer arithmetic because ExtendScript's own `parseFloat` is not correctly
  rounded. Canonical JSON (for `input_hash`) is the same spelling, keys sorted
  by UTF-8 bytes, no whitespace — MINI-SPECS §3 rule 4 is still open upstream
  (F-AC-3) for exponent forms; keep `input_params` numbers to integers or plain
  decimals as that section asks.
* **The zip**: store mode, version 20, flag 0x0800, no extra fields, no data
  descriptors, no directory entries, no zip64; every entry's DOS timestamp is
  the package's `created` (for `sign`, the `signed_at`); physical order is
  `MANIFEST.json` first, then `container.entry_order` with the two-pass rule,
  each group sorted by UTF-8 bytes.
* **The manifest**: the key order of `PackageWriter.manifest()`, the texts and
  tables of `bundle.json`, `generator` and every default `producer` =
  `{"tool": "werk", "version": "<lib version>"}` in all languages — the
  implementation language is not a fact about the content. Pass your host's
  name as `generator=` / `producer=`.
* **Not deterministic unless you pass them**: `created` (default: now) and the
  entity `uuid` (default: random). Pass both for reproducible output.

---

## Tests and their results

| test | command | result (Windows 10 workstation; re-run 2026-11-17 on this repository, unless noted) |
|---|---|---|
| spec test vectors in every library | `python tests/test_vectors.py` | 20 PASS, 0 FAIL (SHA-256, MINI-SPECS §3 canonical vector, RFC 8032 key + signature, `spec/examples` signature, WRITING-IMAGE PNG + `input_hash`, 20 011 doubles spelled like Python in `werk.js` and `werk.jsx`) |
| Rust float spelling | `WERK_FLOATS=_scratch/floats.txt cargo test --release --bin werkc` | 2 passed (20 011 doubles, 0 differ) |
| Python API | `python tests/test_api.py` (3.12 and 3.8) | 27 PASS, 0 FAIL each (incl. a raster-layers/1 package carried with `add_spec_file`, `conventions_map=`, `add_readme_file`, duplicate-entry refusal) |
| JavaScript API, both builds | `node js/tests/api_smoke.js _scratch/inputs` (needs `_scratch/inputs` from `tests/make_inputs.py`, a signed `_scratch/img2.werk` packed from its `source.png` + `thumb.png` with `key.hex`, and `_scratch/dup.werk` from `test_api.py`) | 15 PASS, 0 FAIL |
| ES3 syntax | `node --expose-internals js/tests/es3_check.js` | `werk.jsx` parses as ECMAScript 3 (acorn), no ES5+ API outside the Node-only IO block |
| inside real ExtendScript | `js/tests/extendscript_host_wrapper.jsx` in Illustrator 2020 | see `tests/results/extendscript-illustrator2020.txt` (2026-11-07, an earlier build of `werk.jsx`; not re-run on this build) |
| writers × readers | `python tests/cross_matrix.py --fixtures <fixtures dir>` | 22 cases + the 15 release fixtures, 0 failures: `tests/results/CROSS-MATRIX.md` |
| one-bit damage, readers agree | `python tests/damage_agree.py` | see `tests/results/damage_agree.json` (1532 variants: py = js = es3 on 1532; werkc agrees on 1524, the 8 are listed under known gaps) |

`tests/cross_matrix.py` is pure standard library and path-agnostic: on Linux
it finds `node`, `cc`/`gcc`/`clang`, `rustc` and `werkc` on `PATH` (or take
`--node --cc --rustc --werkc`). `--fixtures` points at any directory of
`*.werk` files for reader-only rows.

## Speed of the ES3 build (ExtendScript)

ExtendScript interprets every operation and charges super-linearly for
growing arrays, so the ES3 build avoids array growth on its hot paths:
SHA-256 with preallocated schedule and unrolled rounds, CRC-32 slicing-by-4,
base64 in bounded chunks, and an inflate that copies back-references as
substrings of a string window (the approach of the Adobe plug-ins'
`werk_inflate.jsx`; in V8 a preallocated byte ring is used instead -- same
bytes). `inflateRaw(data)` without a limit no longer throws.

| Illustrator 2020 (ExtendScript 4.5.6) | before | after |
|---|---|---|
| sha256 | 0.174 MB/s | 0.241 MB/s |
| crc32 | 0.575 MB/s | 0.872 MB/s |
| inflateRaw | 0.007 MB/s (64 KB; super-linear, hangs on MB-sized entries) | 0.413 MB/s (1 MB, linear) |
| inflateRaw without limit | throws | works |
| smoke: verify a signed image package / write one | 14.0 s / 21.9 s | 9.4 s / 13.3 s |
| the deflated release fixture (crate-cc0-lean-v1-deflated) | did not finish | 32.3 s, signed-and-valid |

Node 22 (`node js/tests/bench.js 8`): werk.js sha256 68.8 → 71.1 MB/s, crc32
235.6 → 475.2 MB/s, inflate 31.4 → 150.6 MB/s; werk.jsx sha256 62.3 →
65.8 MB/s, crc32 236.4 → 335.7 MB/s, inflate 30.3 → 88.2 MB/s.
`tests/results/extendscript-bench-illustrator2020.txt` holds the host run.
SHA-256 in ExtendScript is bounded by the interpreter (~13 M simple
operations per second): about 4 s per MB is what ES3 allows there.

## Known gaps

* `tests/damage_agree.py` (1532 one-bit damages of a signed package, bundle at
  release-fixes 26e3e14): the libraries agree with each other on all 1532 and
  with `werk_read.py` on all 1532; werkc agrees on 1524 -- the 8 others are
  nodes werkc kills because a flip breaks a JSON Schema constraint, which the
  libraries do not check. The C and Rust loaders agree on 1531; on the one
  left (a convention key renamed) they print no signature word the harness
  can parse, which is a harness limit, not a different verdict.

* No JSON Schema validation in the Python and JavaScript readers (declared in
  every verdict). `werkc verify` validates; use it in a gate.
* `preview_prefix_bytes` is not written (it is an optional hint, SPEC S-15);
  `preview_tier` is. On append/sign an existing value is left as it was —
  a hint may be stale and a reader must not treat it as exact.
* Writers emit store mode only (deflate is read, never written), and refuse
  zip64 by design: past 4 GiB or 65 534 entries, write the directory form.
* JavaScript object keys that look like array indices (`"1"`, `"42"`) are
  enumerated first by every JS engine, so a JSON object with such keys is
  re-emitted in a different order by the JS writers than by the Python and
  Rust ones. No werk manifest key is like that; user `meta` could be.
* Signing is not constant-time in Python or JavaScript: sign on your own
  machine, not as a service an attacker can time.
* Python 3.7 itself was not run (3.8, 3.10, 3.11, 3.12 and 2.7.14 were). On
  2.7 the read half (zip and directory, Ed25519 included) and `pack-image` were
  run (`pack-image` output byte-identical to 3.12's). Cinema 4D R21's own
  `python.exe` returns exit status 1 for ANY script file, even `sys.exit(0)`
  (measured): inside C4D use the library, not the exit status.
* Photoshop 2024 did not start on this machine (COM `Photoshop.Application.180`:
  CO_E_SERVER_EXEC_FAILURE; launched directly it exits with status 1), and the
  bare `Photoshop.Application` ProgID is Photoshop 2020, which was already open
  and was not touched. The ExtendScript gate therefore ran in Illustrator 2020
  (ExtendScript 4.5.6). Only the zip form was exercised there, not directory
  form through `Folder`.
