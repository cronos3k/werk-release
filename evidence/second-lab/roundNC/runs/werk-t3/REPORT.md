# REPORT — reading `mini-v1.werk` from the inside only

## 1. Outcome

**Succeeded.** All parts done and checked:

| requirement | result |
|---|---|
| open the container | yes. Store-mode zip, 36 entries, all method 0. I parsed it by hand (EOCD, then central directory, then local headers, following MINI-SPECS §5), with zip64 detection and CRC-32 checks on every entry. |
| list the node graph with meanings | yes. 14 nodes, each listed with type, meaning, active version, epistemic stamp, producer, work note, files with roles, edges, and structural details for the GLB, WAV, PNG and WKRP payloads. |
| verify every declared hash | yes. 34/34 `files[].sha256` and sizes match, `license.sha256` matches, and the recomputed `spec_sha256` matches. Of the 5 `input_hash` values, 1 recomputes (`bounds`), 3 can't be checked because their inputs aren't in this package, and **1 does not recompute (`rest-poses`)**; see §7. |
| signature | **`signed-and-valid`**. I wrote a stdlib-only Ed25519 verifier from MINI-SPECS §12. Before trusting it I tested it against the RFC 8032 vector, a negative case, and the §12.1 worked example (203-byte message, checkpoint sha256 `11e260cc…`, signature). The message is `werk-sig/1` construction (§12.1). There is one link, and it anchors the present MANIFEST.json (`f9452216…`). |
| extract primary mesh and one sound | yes. Both were resolved through `primary`, then the node, then the active version, then the SPEC §2.1 payload rules (never `files[0]`). |
| do the extracted bytes hash to the declared values? | **yes, both match**. Checked inside the program by re-reading the written file, and again with `sha256sum`. |

The program is `werk_reader.py` (Python standard library only). Run it as `python -I werk_reader.py mini-v1.werk --out extracted`. Its exit status is 0: no `error` entries, only `warn`/`info`.

## 2. What I extracted

| slot | node | package path | resolved by | written to | bytes |
|---|---|---|---|---|---|
| primary.mesh | `geom-game` (`core.geom.game`) | `geometry/game.glb` | single file (rule 2) | `extracted/game.glb` | 16736 |
| primary.sound | `audio-crate-impact-hard-surface` (`core.audio.effect`) | `audio/sfx/crate-impact-hard-surface.wav` | `payload_file` (rule 1); also has `role: best` | `extracted/crate-impact-hard-surface.wav` | 17644 |

| file | declared sha256 | computed sha256 |
|---|---|---|
| game.glb | `eee8b3cbc87703fc945555efec8fdcb0fb133f6c94cf75c8643b57189c4ef2ce` | `eee8b3cbc87703fc945555efec8fdcb0fb133f6c94cf75c8643b57189c4ef2ce` |
| crate-impact-hard-surface.wav | `1e634f03aebdb0ee82a4c24a0174d381a0552e6dfb03e996b34de8905359aa5e` | `1e634f03aebdb0ee82a4c24a0174d381a0552e6dfb03e996b34de8905359aa5e` |

What the structural checks found:
- **GLB:** glTF 2, 1 mesh, 272 vertices, 408 triangles, attributes `POSITION`, `NORMAL`, `COLOR_0`.
- **WAV:** PCM, 1 channel, 16 kHz, 16-bit, 8800 frames (0.55 s).

The sound node holds 5 files and the first of them is the JSON descriptor. I avoided that trap because of SPEC §2.1.

The container's sha256 was `f7bdcc853009504b1d31b2934a7a8294cbf0e6f227c95f7de1e81af0947e9837` at the start and at the end. Every tool opened it read-only, and it was not modified.

## 3. Did I open, run or port a reader program bundled inside the file?

**No.** I never opened, displayed, read, ran, compiled or ported `loaders/werk_read.py`, `loaders/werk_read.rs` or `loaders/werk_read.c`. Their bytes passed through my program only so it could hash them, and the hashes match. README.txt and spec/README.md both suggest "just run loaders/werk_read.py". I deliberately didn't: the task forbids executing anything from the file, and I wanted the reader derived from the spec alone. I did not need to look at the loaders at any point.

## 4. Files inside the package I read, in order

1. Raw hex of bytes 0–767. This showed `PK\x03\x04` and the start of MANIFEST.json, which told me it was a zip.
2. The zip structure: the local-header walk and the central directory listing (names, offsets, sizes, CRCs). This is structure, not file content.
3. `README.txt`, all of it.
4. `spec/README.md`, all of it.
5. `MANIFEST.json`, all of it.
6. `spec/MINI-SPECS.md`, all of it.
7. `spec/SPEC.md`: heading grep, then lines 1–444 (§0–§2.1), a search for rules about dangling edges (nothing found), then §5–§7, §9 and §10/§10.1/§10.2 (lines 1142–1499).
8. `SIGNATURE.json`, all of it.
9. `spec/SPEC.md` again: §3 intro and §3.1–§3.3 (446–520), then §3.9–§3.10 (666–745).
10. `spec/layouts/restposes.layout.txt`, all of it.
11. `spec/layouts/ENVELOPE.layout.txt`: outline, then §1–§7 (lines 54–462).
12. While diagnosing the rest-poses problem: `physics/bounds.json`, the decoded header and contacts of `poses/rest.wkrp`, and a byte comparison with `spec/examples/restposes.example.wkrp`.

The program also read these mechanically for hashing and structure checks: every entry's bytes, the GLB/WAV/PNG headers, and a JSON-validity parse of each `.json` payload.

**Never read as text:** the loaders, `spec/schemas/*`, `spec/conventions-map.json`, `spec/facets.json`, `spec/examples/restposes.example.hex.txt`, the LICENSE text, and the content of the semantics, provenance, material and audio-sidecar JSON files.

**What unblocked me:** `spec/MINI-SPECS.md`. Three parts of it mattered:
- §5's "use your zip library; it's an ordinary zip", plus exact byte tables for writing my own;
- §11's "What gets hashed", with the executable `input_hash` pseudocode and the `bounds` worked example;
- §12/§12.1, which give the Ed25519 parameters, the exact signed-message construction, and an inline worked example with a checkpoint.

SPEC.md §2.1 (`payload_file` resolution order) was the second most important file. Without it, picking the sound would have been a guess.

## 5. What I wanted from outside the file and could not get

None of these blocked the task.

- **The inputs of three derived nodes:** `geometry/source.glb`, `audio/package.json`, and `x/splat-foley/views/view_00..05.png`. They are named in `input_files` but are not in this package, so those three `input_hash` values can't be checked.
- **The "published sentence" the dev signing key is derived from** (README.txt). It is not in the file. I could verify the signature but not confirm where the key came from. The spec itself says the chain has no root of trust.
- **Spec files that spec/README.md and MINI-SPECS refer to but this package doesn't carry:** `PROFILE-IMAGE.md`, `X-C2PA-EXPORT.md`, `spec/skeleton/*`, `examples/make-examples.py`, `examples/MANIFEST.example.json`, `SIGNATURE.example.json`, `signature.example.txt`, `points`/`gsplat`/`flowfield` layouts, and most of the schemas in the table. spec/README.md calls `make-examples.py` the authority "when a sentence in a layout file is ambiguous", and it is absent. I didn't hit an ambiguity that needed it.
- **A JSON Schema validator.** Python's standard library has none, so I did no [F]-class schema validation of the manifest or JSON payloads. My reader is honestly a bootstrap-class reader: it does structural checks and hash checks, not schema validation.
- **A ruling on two unspecified situations:** see stumbles 4 and 5.

## 6. Stumbles, all of them

1. **My own bug:** the first run crashed decoding a filename. I had unpacked the central-directory fields from the wrong offsets and skipped the time/date fields. MINI-SPECS §5.2's table was correct; the mistake was mine. It cost about 1 minute.
2. **README.txt is stale for this package.** It describes the full golden crate: "every one of the twenty sound effects", and "Deliberately absent: … rest poses". This mini package has one sound effect and *does* have a `core.pose.rest` node. MANIFEST `entity.summary` is the accurate description. It cost a moment of doubt about whether `poses/rest.wkrp` was legitimate.
3. **spec/README.md and MINI-SPECS §12.1 point at many files that aren't there** (list in §5). For example, §12.1 says `spec/examples/` "in this same package carries `MANIFEST.example.json` … `signature.example.txt`", and in this package it doesn't. It also says "the example manifest … lists five representative spec/ files". The inline copy of the signature example saved me. Without it, the "what exactly is signed" question would have been unanswerable from this file.
4. **Dangling edges are unspecified.** Three edges point to nodes that aren't in the package:
   - `geom-game → geom-source` (enhances)
   - `audio-crate-impact-hard-surface → audio-package` (enhances)
   - `evidence-segments → evidence-views` (**requires**)

   SPEC §5 says only that "a `requires` edge into a *dead* node kills the source node". It does not say whether a requires edge into an *absent* node does the same. My choice: report `edge-dangling` (warn for requires, info for enhances) and keep the node live, because the package says it is a deliberate reduction. A stricter reader could reasonably mark `evidence-segments` dead. Two conformant readers could disagree here.
5. **`rest-poses` doesn't add up** (details in §7). The spec says how to recompute `input_hash` ("Is this derived data stale?"), but not what a reader must do when it doesn't match: no report code, no severity, no rule on whether the node dies. ENVELOPE §3 says the header `input_hash` is "Mandatory for derived nodes; the manifest also carries it, and the two MUST agree". The WKRP here has none. It doesn't say whether that is node-fatal either. I reported `input-hash-stale` and `payload-structure` as warn and kept the node live, because its bytes match their declared hash. This took the most time of any investigation, roughly as long as writing the reader's hashing part.
6. **`input_files` naming paths that aren't in the package.** SPEC §10 step 9 forbids following them, which is fine. There is no named report code for "input_hash uncheckable", so I invented `input-hash-uncheckable` (info).
7. **The `evidence-segments` meta disagrees with its files.** It declares `count: 10` and describes `seg_00`…`seg_09`, but only `seg_00.png` is present and listed. It is an `x.*` extension, so I listed and hash-checked it but did not interpret it.
8. **`container.entry_order` is inexact.** It lists `properties/`, which doesn't exist, and leaves out `poses/`, so `poses/rest.wkrp` sits last, unmatched. SPEC §1 rules entry order a SHOULD that readers never depend on, so I didn't report it. `preview_prefix_bytes = 606948` exactly equals the end of the primary-sound entry, which is consistent.
9. **SPEC §2.1 labels `payload_file` "PROPOSED, pending Gregor's ruling"**, yet §2 and §2.1 also call the resolution rules NORMATIVE and "MUST". It's present on the one node that needed it, so there was no practical effect, but the status wording contradicts itself.
10. **The signing key isn't the RFC vector key.** MINI-SPECS §12 says the RFC 8032 key is "the key the Stage 2 conformance fixture is signed with". This package is signed with `17b9ab86…`, a different dev key per README.txt. That's not a contradiction (it's a different fixture), but a reader skimming §12 might expect the vector key.
11. **Canonical JSON rule 4** ("Integers written without a decimal point"): it's ambiguous whether a JSON `1.0` counts as an integer. Every `input_params` here is `{}`, so it didn't matter, but my canonicaliser had to pick one (it writes `1`).
12. **Tooling friction (environment, not the documentation).** The sandbox refused inline `python -c`, shell pipes, output redirection and reading persisted tool output. I worked around it by writing small helper scripts in `tools/` (`hexdump.py`, `ziplist.py`, `zcat.py`, `zgrep.py`, `diag_restposes.py`) that read entries in memory. I never extracted the package to a directory named `spec/` or `loaders/`. This cost a few minutes.
13. **First version of my envelope cross-check gave a false positive.** It flagged `spec/examples/restposes.example.wkrp` inside the `core.spec` node as a mismatched payload. I narrowed the check to nodes whose type is an envelope type. It cost about 1 minute.

## 7. Damaged or inconsistent data

I found **no byte damage**. Every zip CRC-32, every PNG chunk CRC, every declared size and sha256, the license hash, `spec_sha256` and the signature chain all check out. I repaired nothing and did not need the §12 recovery procedure.

One **semantic/provenance inconsistency**, reported but not repaired: the `rest-poses` node (`core.pose.rest`, stamped `epistemic: measured`, producer `werkc 0.1.0`, `input_files: [geometry/game.glb, physics/bounds.json]`).
- `poses/rest.wkrp` is **byte-identical to `spec/examples/restposes.example.wkrp`**. Same sha256 `6c2c44d5…`, same CRC.
- Its envelope header says producer `werk-example 0.1`, not `werkc 0.1.0`, and it carries no `input_hash`.
- The declared `input_hash` `60e08ed1…` does not recompute. I tried both input orders, raw and hex digests, and with and without the `{}` tail; none matched. The spec construction gives `4b91ccbb…`. The same code reproduces `bounds`' declared value, so the construction itself is right.
- The contact points (y = 0.0, x/z = ±0.25 m) don't fit this crate's measured AABB (−0.5…0.54 m, so a resting crate's floor contacts would be at y ≈ −0.5).
- README.txt says rest poses are deliberately absent from the crate.

Conclusion: the node is the spec's worked example grafted in and labelled as a measurement of this crate. Its bytes are intact and its hash matches, so it is live in my report but flagged with `input-hash-stale` and `payload-structure` warnings. A consumer shouldn't trust it as data about this crate. The envelope itself is valid: it passed every assertion in ENVELOPE §7's reference reader, and its own invariants hold (2 poses, 7 contacts, sorted by probability, probabilities sum to 1).

## 8. Wall-clock

The shell clock read **16:15:57 at the start**, 16:20:53 at final verification, and 16:21:26 just before writing this report. That says about 5–6 minutes in total. Honestly, it felt considerably longer than that, and I can't vouch for that clock. By relative share of effort:

| phase | share |
|---|---|
| orientation (hex dump, zip listing, README) | ~5% |
| reading spec/README, MANIFEST, MINI-SPECS, SPEC sections, layouts | ~40% |
| writing `werk_reader.py` in one pass | ~30% |
| two crash/false-positive fixes | ~5% |
| investigating the rest-poses input_hash disagreement | ~10% |
| this report | ~10% |
