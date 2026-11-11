# REPORT: reading mini-v1.werk

## 1. Result

**Success on every requested item.** The program is `werk_reader.py`. Run it with `python -I werk_reader.py mini-v1.werk extracted`. The full log is in `extracted/reader-log.txt`.

| Task | Result |
|---|---|
| Open the container | Yes. It is a store-mode ZIP with 36 entries. I checked for zip64 first (none). |
| List the node graph with meanings | Yes. 14 nodes, each with type, meaning, work note, producer, epistemic stamp, files and edges. |
| Verify every declared hash | Yes. All 34 `files[].sha256` and sizes match. `license.sha256` matches. `spec_sha256` (17 spec files) matches. Every ZIP CRC-32 passed. |
| Verify the signature | `signed-and-valid`. Chain entry 0 verified with my own Ed25519, written from MINI-SPECS §12. It passed the RFC 8032 vector and the §12.1 worked example first. The manifest anchor matches. |
| Extract the primary mesh | Yes. `primary.mesh` = `geom-game` → `geometry/game.glb` (rule 2: single file). |
| Extract one sound | Yes. `primary.sound` = `audio-crate-impact-hard-surface` → `payload_file` → the `best` take `.wav`. It is not `files[0]`, which is the JSON descriptor. |
| Extracted bytes hash to the declared values | Yes, both. My program hashed the written files. PowerShell `Get-FileHash` confirmed the same values. |

The program exits with status 1, not 0. That is deliberate and follows SPEC §10.2: one node (`evidence-segments`) is marked dead (see 6.2). Nothing was damaged.

## 2. Extracted files

| File on disk | Source in package | Declared sha256 | Computed sha256 (on disk) |
|---|---|---|---|
| `extracted/geometry_game.glb` (16736 B) | `geometry/game.glb` | `eee8b3cbc87703fc945555efec8fdcb0fb133f6c94cf75c8643b57189c4ef2ce` | `eee8b3cbc87703fc945555efec8fdcb0fb133f6c94cf75c8643b57189c4ef2ce` |
| `extracted/audio_sfx_crate-impact-hard-surface.wav` (17644 B) | `audio/sfx/crate-impact-hard-surface.wav` | `1e634f03aebdb0ee82a4c24a0174d381a0552e6dfb03e996b34de8905359aa5e` | `1e634f03aebdb0ee82a4c24a0174d381a0552e6dfb03e996b34de8905359aa5e` |

What the payloads are:
- Mesh: GLB v2 with 1 mesh, 272 vertices and 408 triangles. Attributes: `POSITION`, `NORMAL`, `COLOR_0`. It is indexed triangles, as SPEC §3.10 requires.
- Sound: 16-bit PCM WAV, mono, 16 kHz, 8800 frames (0.55 s). The sidecar prompt is "a wooden crate struck hard by a metal pipe...".

## 3. Node graph (summary)

| node_id | type | meaning | status |
|---|---|---|---|
| geom-game | core.geom.game | runtime mesh, primary mesh | live |
| material-wood | core.material | PBR parameters, authoritative over the GLB | live |
| bounds | core.phys.bounds | measured AABB and sphere, model space | live, `input_hash` reproduces |
| semantics | core.semantics | facet tags, palette, search text | live |
| provenance | core.provenance | who made what, from what | live |
| audio-crate-impact-hard-surface | core.audio.effect | 1 descriptor, best take, raw take, 2 variations | live, primary sound |
| spec | core.spec | the 17 spec files | live |
| loader-python / -rust / -c | core.loader | embedded reader sources | live, hashed, **never opened or run** |
| license | core.license | CC-BY-4.0 text | live |
| readme | core.readme | human page | live |
| evidence-segments | x.splat-foley.segments | SAM crop image (extension type) | **dead**: `requires` edge to the absent node `evidence-views` |
| rest-poses | core.pose.rest | WKRP envelope: 2 poses, 4096 trials, 7 contacts | live, envelope valid, but see 6.1 |

## 4. Embedded reader programs

**I never opened, read, ran, compiled or ported any of the three loaders** (`loaders/werk_read.py`, `.rs`, `.c`). My program treats them only as data: it lists and hashes them. README.txt says "just run loaders/werk_read.py". I did not. I wrote every check from the spec text.

I also did not run any other program from the file. `spec/examples/make-examples.py` is named as an authority, but it is not in this package.

## 5. Files I read inside the package, in order

1. ZIP central directory (entry listing, using Python `zipfile`)
2. `README.txt`
3. `spec/README.md`
4. `MANIFEST.json`
5. `SIGNATURE.json`
6. `spec/MINI-SPECS.md` (all of it)
7. `spec/SPEC.md`: heading list, then §0-§2.1, §3-§3.10, §5-§10.2
8. `spec/conventions-map.json`
9. `spec/layouts/restposes.layout.txt`
10. `spec/examples/restposes.example.hex.txt`
11. `spec/layouts/ENVELOPE.layout.txt`
12. `physics/bounds.json` (to check the rest-pose finding)

Read only by the program, not by me: all other payloads, which are hashed and parsed.
Never read: `LICENSE` text, `spec/schemas/*`, `spec/facets.json`, all loaders.

**The file that unblocked me: `spec/MINI-SPECS.md`.** §11 ("What gets hashed", with the `input_hash` pseudocode) and §12/§12.1 (Ed25519 parameters and the exact signed message with a checkpoint) made the signature and staleness checks possible without outside knowledge. `SPEC.md` §2.1 (`payload_file`, never `files[0]`) was second. Without it I would have had to guess which of the five audio files is "the sound".

## 6. Findings about the package content

### 6.1 `rest-poses` does not describe this crate (not damage, but a real inconsistency)
- `poses/rest.wkrp` is byte-identical to `spec/examples/restposes.example.wkrp` (same sha256 `6c2c44d5...`).
- The envelope header says producer `werk-example 0.1`. The manifest says producer `werkc 0.1.0`, epistemic `measured`, and claims the data came from `geometry/game.glb` + `physics/bounds.json`.
- The declared `input_hash` (`60e08ed1...`) does not reproduce. I tried 8 variants (both input orders, raw or hex digests, with or without `{}`). None matched. The same code reproduces `bounds`' `input_hash` exactly, so I believe the construction is correct.
- Physically it does not fit. Pose 0 is identity with floor contacts at y = 0 in a 0.5 m square. The crate's AABB is about 1.04 m wide with its bottom at y = -0.5.
- The node is inside the signed manifest and every hash matches, so this is not tampering. My reader reports `input-hash-stale` (warn) and `producer-disagrees` (info) and still loads the node, as SPEC requires.
- README.txt also says rest poses are "deliberately absent", but this package has a rest-poses node.

### 6.2 Dangling edges
- `geom-game` → `geom-source` (enhances) and `audio-…` → `audio-package` (enhances): the targets are absent. Under SPEC §5 an `enhances` edge costs at most one feature, so I report these as info.
- `evidence-segments` → `evidence-views` (**requires**): the target is absent. SPEC §5 says a `requires` edge into a **dead** node kills the source. It does not say what an **absent** node means. I treated absent as dead, so the node is reported dead and the exit status is 1. Its PNG still hash-verifies.

### 6.3 Inputs that cannot be checked
- `input_hash` cannot be recomputed for `geom-game` (`geometry/source.glb`), the audio node (`audio/package.json`) or `evidence-segments` (6 `views/*.png`). Those inputs are not in the package. I report this as `input-hash-unverifiable`, not as stale.
- `evidence-segments.meta` describes 10 images, but only `seg_00.png` is shipped.

## 7. What I wanted from outside the file and could not get

Nothing was blocking. Things I would have liked:
- `spec/examples/make-examples.py`. ENVELOPE.layout.txt and spec/README.md call it the authority when a layout sentence is ambiguous. It is not in the package.
- `spec/examples/signature.example.txt`, `MANIFEST.example.json` and `SIGNATURE.example.json`. MINI-SPECS §12.1 says "this same package carries" them. It does not. The inline copy in §12.1 was enough.
- The "manifesto laws" (law 3 especially) that SPEC §5 defers to ("normative text lives there"). The manifesto is not in the package, so the absent-versus-dead question in 6.2 has no authority I can read.
- `geometry/source.glb`, `audio/package.json` and the view images, to finish the `input_hash` checks.
- A JSON Schema validator. Python's stdlib has none. My reader is a structural ("bootstrap") reader and does not claim schema validation.

I used general prior knowledge only for the boring things the spec itself tells you to take from a library: Python `zipfile`, `hashlib` (sha256/sha512) and `json`. I proved each against the spec's test vectors. Ed25519, MessagePack, the envelope rules and the werk-specific rules were written from the spec text.

## 8. Stumbles, honestly

1. **Environment friction (not a doc problem).** Shell pipes, redirects and chained commands in this harness needed approval. I could not `xxd`, `head` or redirect to a file. I wrote small helpers (`tools/peek.py`, `ls.py`, `cat.py`, `zgrep.py`) to read members straight from the ZIP. This cost about a minute.
2. **spec/README.md describes a bigger package than this one.** It links about 20 files that are not here: `PROFILE-IMAGE.md`, `X-C2PA-EXPORT.md`, `layouts/points|gsplat|embedding|…`, most schemas, `skeleton/`, `examples/make-examples.py`, the gsplat and embedding hex dumps. A reader cannot tell "missing because reduced" from "missing because damaged" without the manifest. The manifest's `spec` node is the true list.
3. **MINI-SPECS §12.1 makes a false claim** that `spec/examples/` in "this same package" carries the signature example files. The inline copy saved me.
4. **README.txt is the golden crate's README, not this fixture's.** It says "twenty sound effects", "deliberately absent: … rest poses", and "Nothing in here is a placeholder". This package has one effect, does have rest poses, and the rest poses are the spec example binary (6.1).
5. **SPEC §5 does not define "absent" for edges** (6.2). I made a choice and recorded it.
6. **The `rest-poses` `input_hash` mismatch** cost a few minutes. I had to rule out my own construction before I believed the data was wrong.
7. **Preview tier definition.** SPEC §1 S-15 says the default tier includes "the one entry named by `primary.sound`", but `primary.sound` names a node with five files. I took its `payload_file`. My recomputed value (606948) equals the hint exactly, so the reading is probably right, but the text is loose.
8. **Small inconsistencies in SPEC.md:**
   - The preamble cites "§3.7a" for `core.phys.body` space, but the section is numbered §3.6a.
   - §1's preview-first write order omits `README.txt`, but the S-15 default tier includes it.
   - `container.entry_order` lists `properties/`, which has no entries, and omits `poses/`.
   - SPEC §5 says only "dead node" for edges, but the §10.1 table uses "a `requires` edge failed".
9. **MessagePack duplicate keys** are not covered by ENVELOPE §4. I chose to reject them, in line with the JSON rule in MINI-SPECS §3. The rule was not exercised.
10. **The canonical-JSON float rule** ("shortest form that round-trips") is not exercised, because every `input_params` here is `{}`. My float path is untested against this package.

## 9. Damaged or corrupted data

None found. Every ZIP CRC, every size, every sha256, `spec_sha256`, `license.sha256` and the signature check out. I did not repair or change anything. `mini-v1.werk` was opened read-only and never written. Its size (960061) and modification time (2026-10-05 22:52:26) are unchanged. Its sha256 after the run is `f7bdcc853009504b1d31b2934a7a8294cbf0e6f227c95f7de1e81af0947e9837`. I did not hash it before the run, so this is a reference value, not proof.

The rest-pose inconsistency (6.1) is a content and provenance problem under a valid signature, not byte damage. I only reported it.

## 10. Wall-clock time (approximate)

The session clock read 22:52:31 at the start and 22:57:00 near the end. Most of that time was model reasoning between tool calls.

| Phase | Approx. |
|---|---|
| Identify container, list entries | under 1 min |
| Read README, spec/README, manifest, signature | about 1 min |
| Read MINI-SPECS, SPEC sections, layouts | about 1-2 min |
| Write the reader, first run (all checks passed first time) | about 1 min |
| Diagnose the rest-poses `input_hash`, preview check, cross-checks | about 1 min |
| Write this report | about 1 min |
