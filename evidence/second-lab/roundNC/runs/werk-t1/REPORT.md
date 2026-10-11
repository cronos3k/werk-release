# REPORT — mini-v1.werk

## 1. Outcome

**Succeeded on every point the task asks for.**

| requirement | result |
|---|---|
| open the container | yes. I wrote my own store-mode zip reader from MINI-SPECS §5 (EOCD scan from the end, zip64 detection, central directory, local headers, CRC-32 per §6). It found 36 entries, all method 0, all CRCs good. Python's `zipfile`, which §5 recommends, gives the same result. |
| list the node graph with meanings | yes. All 14 nodes, with type, meaning, work note, producer, epistemic stamp, files with roles, and edges. Edges whose target node is not in the package are flagged. |
| verify every declared hash | yes. All 34 `files[].sha256` and sizes match (every container entry except MANIFEST.json and SIGNATURE.json; nothing is unlisted), and so do `license.sha256` and `spec_sha256` (rebuilt over the 17 declared spec files using the S-29 construction). For `input_hash`: 1 matches (`bounds`), 1 does not match (`rest-poses`, see §7), and 3 cannot be checked because their inputs are not in the package. The signature chain also verifies (`signed-and-valid`) with an Ed25519 verifier I wrote from MINI-SPECS §12. It passes the RFC 8032 vector and the §12.1 message checkpoint before the program trusts it. |
| extract the primary mesh and one sound | yes. I followed `primary.*` to the node, then its active version, then the SPEC §2.1 payload rules. I did not take `files[0]`. |
| extracted bytes hash to the declared values | **yes, both match** (table below). |

Program: `werk_reader.py` (Python stdlib only). Run it with `python -I werk_reader.py mini-v1.werk extracted`. It exits with 0, which per SPEC §10.2 means no report entry has severity `error`. It reports 7 `warn` entries and 6 `info` entries.

## 2. What I extracted

| slot | node → resolved path (rule) | output file | size | declared sha256 | computed sha256 |
|---|---|---|---|---|---|
| primary.mesh | `geom-game` v1 → `geometry/game.glb` (§2.1 rule 2, single file) | `extracted/geometry__game.glb` | 16736 | `eee8b3cbc87703fc945555efec8fdcb0fb133f6c94cf75c8643b57189c4ef2ce` | `eee8b3cbc87703fc945555efec8fdcb0fb133f6c94cf75c8643b57189c4ef2ce` |
| primary.sound | `audio-crate-impact-hard-surface` v1 → `audio/sfx/crate-impact-hard-surface.wav` (§2.1 rule 1, `payload_file`; the `role: best` entry agrees) | `extracted/audio__sfx__crate-impact-hard-surface.wav` | 17644 | `1e634f03aebdb0ee82a4c24a0174d381a0552e6dfb03e996b34de8905359aa5e` | `1e634f03aebdb0ee82a4c24a0174d381a0552e6dfb03e996b34de8905359aa5e` |

I checked the structure of both files:
- **Mesh:** GLB version 2, 272 vertices, 408 triangles, attributes POSITION, NORMAL and COLOR_0. The vertex AABB I computed from the BIN chunk is [-0.5,-0.5,-0.5]..[0.54,0.54,0.5], which exactly matches `physics/bounds.json`.
- **Sound:** RIFF/WAVE PCM, 16 kHz, mono, 16-bit, 0.550 s. That matches the descriptor's `audio_format` and `refined.duration`.

## 3. Bundled reader programs

**I never opened, read, ran or ported any of `loaders/werk_read.py`, `loaders/werk_read.rs` or `loaders/werk_read.c`.**
- My dump script skipped `loaders/` when copying entries into `scratch/pkg/`.
- The only thing my reader does with those three files is hash them against the manifest; all three match.
- I never needed them. The spec gave everything required, including Ed25519.
- README.txt says "or just run loaders/werk_read.py". I deliberately didn't.

## 4. Files I read inside the package, in order

1. Raw header bytes of the container (first 512 bytes, hex dump). This showed `PK\x03\x04` and that MANIFEST.json comes first.
2. A walk of the local file headers (names, offsets, sizes only). That gave me the entry list.
3. `README.txt`
4. `spec/README.md`. It set the reading order.
5. `MANIFEST.json` (in full)
6. `spec/SPEC.md`: the heading list, then §0–§3 header table (lines 1–490), then §5–§10.2 (lines 1142–1500)
7. `spec/MINI-SPECS.md`: the heading list, then §1–§8.1 (lines 1–400), then §9–§13 (lines 488–977). I skipped the PNG filter details (§8.2–8.3) because I never decode pixels.
8. `SIGNATURE.json`
9. `audio/sfx/crate-impact-hard-surface.json`
10. `spec/layouts/restposes.layout.txt`
11. `spec/examples/restposes.example.hex.txt`
12. `spec/layouts/ENVELOPE.layout.txt`
13. `physics/bounds.json`
14. `spec/conventions-map.json`

My program parses the other payloads (material, semantics, provenance, the PNG) as data, but I never read them myself. I did not open any of the JSON schemas, `spec/facets.json`, `LICENSE`, or `provenance.json`.

**What unblocked me:** `spec/MINI-SPECS.md`, together with SPEC.md §2/§2.1.
- MINI-SPECS supplied the exact zip record layouts, the `input_hash` construction with a worked example from this package, and complete Ed25519 verification parameters. Its §12.1 also gave the signed-message construction with a byte-level checkpoint, which let me prove my verifier before trusting it.
- SPEC §2.1's payload-resolution rules are what stop the classic mistake of extracting the sound's JSON descriptor instead of the WAV.

Nothing ever really blocked me.

## 5. What I wanted from outside the file and could not get

Nothing was required. Things I would have used if they had been present:
- **A JSON Schema validator** (that would be an outside library). I did not validate any JSON against its schema. The reader says so on screen and claims structural checks only, which SPEC §10 step 2 [B] allows.
- **The files spec/README.md says should exist but this package does not carry:**
  - `spec/examples/make-examples.py`, called "what it means" when a layout sentence is ambiguous
  - `spec/examples/signature.example.txt`, `MANIFEST.example.json` and `SIGNATURE.example.json`
  - `PROFILE-IMAGE.md` and `X-C2PA-EXPORT.md`
  - the `skeleton/` folder
  - most of the schemas and layouts in its tables

  None of them were needed here, but a reader following the README's own instructions hits dead links.
- **The inputs needed to check three `input_hash` values:**
  - `geometry/source.glb` (for `geom-game`)
  - `audio/package.json` (for the audio effect)
  - `x/splat-foley/views/view_00..05.png` (for `evidence-segments`)

  These were left out when the package was cut down from a bigger one, so those hashes cannot be checked from inside the file.

## 6. Stumbles and documentation problems (honest list)

**My own mistakes:**
1. My tool environment blocked inline `python -c`, `&&` chains and PowerShell pipelines, so I had to write every probe as a script file. That cost a few minutes and is unrelated to the format.
2. My first run of `werk_reader.py` crashed on `memoryview.decode` (I had wrapped the file in a memoryview). I switched to `bytes`. This was the only code bug.

**Problems in the documentation inside the file:**

3. **README.txt does not describe this file.**
   - It talks about "every one of the twenty sound effects"; the package has one sound effect node.
   - It says rest poses are "deliberately absent", yet the package has a `core.pose.rest` node (`poses/rest.wkrp`).
   - It is the golden crate's README, copied into a cut-down package. A reader trusting it is misled about what is inside.
4. **spec/README.md points to many files that are not here.** These include `PROFILE-IMAGE.md`, `X-C2PA-EXPORT.md`, `examples/make-examples.py`, `signature.example.txt`, `skeleton/*`, and the points/gsplat/flowfield/skeleton/animclip/imposter layouts and schemas. Its row 5 also promises "a real binary and an annotated hex dump for every envelope magic", but only the WKRP pair is shipped. Not knowing what had been cut cost me time.
5. **`entry_order` in MANIFEST.json does not match the container.**
   - It lists `properties/`, which does not exist.
   - It omits `poses/`, which does exist; `poses/rest.wkrp` is physically the last entry.
   - This is harmless, since S-14 says readers never depend on order, but it is inconsistent.
6. **Edges point at nodes that are not in the package.** `geom-game` → `geom-source`, `audio-crate-impact-hard-surface` → `audio-package`, and `evidence-segments` → `evidence-views` (a **requires** edge).
   - SPEC §5 says a `requires` edge into a *dead* node kills the source node. It does not say what happens when the target node is *absent*.
   - I chose to report these as `warn` (`edge-target-missing`) and keep `evidence-segments` live, because its own bytes verify.
   - That is a judgement call the spec does not settle, so another reader could reasonably kill the node.
7. **`evidence-segments` meta does not match its files.** `meta.count = 10` and `meta.images` describes 10 PNGs (`seg_00`..`seg_09`), but `files[]` carries only `seg_00.png`. SPEC's "never follow a path not in some files[]" saved me, but nothing says whether meta is allowed to name absent files.
8. **SPEC.md cites "§3.7a"** (for the S10-3 ruling on `core.phys.body` space) in its status block, but the section is numbered §3.6a. A small cross-reference error.
9. **The envelope `input_hash` rule is not met.** ENVELOPE §3 says `input_hash` in a header is "Mandatory for derived nodes; the manifest also carries it, and the two MUST agree". The WKRP header in `poses/rest.wkrp` has no `input_hash`, yet the manifest marks the node `measured` and gives one.
10. **"Two different nodes claiming one path" leaves a case open.** It is defined as an error, but nothing says what it means when two nodes carry byte-identical content under different paths. That happens here (see §7). I reported it as a warning, not an error.
11. **Small mismatch between the envelope grammar and the hex example.** ENVELOPE §3 defines `payload_size` as "total bytes from P to end of file", which includes trailing padding. The hex example confirms this, and so does §5's rounding rule. This is not wrong, but the wording "total bytes" next to "exact byte length of the section" made me stop and check.
12. **Payload-role ambiguity, now resolved by the spec.** Without SPEC §2.1, `files[0]` of the sound node is the JSON descriptor. The spec handles this well now, but I note it as the most likely trap.

## 7. Damaged or suspicious data

No byte-level damage: every CRC, size and sha256 is good, and the signature verifies. There is **one inconsistency that the format's own checks expose**:

**`rest-poses` (`core.pose.rest`, `poses/rest.wkrp`) is the spec's example binary, labelled as a measurement of this crate.**
- Its sha256 (`6c2c44d5…5f95`) is identical to `spec/examples/restposes.example.wkrp`. It decodes to exactly the example in `restposes.example.hex.txt`: 2 poses, 7 contacts, envelope producer `werk-example 0.1`.
- The manifest says the producer was `werkc 0.1.0`, with `epistemic: measured`, "settled orientations from a drop simulation", and `input_files` `geometry/game.glb` + `physics/bounds.json`.
- The declared `input_hash` (`60e08ed1…96c8`) does **not** reproduce. I rebuilt it as `4b91ccbb…b983` using the documented construction (raw digests in `input_files` order, then `{}`). I also tried both orderings, with and without `{}`, and hex concatenation; none match. The same code verifies `bounds`' `input_hash`, so the construction itself is right.
- It is also physically implausible. Pose 0 is the identity rotation, but its contacts sit at y = 0, not on the crate's bottom face at y = −0.5 (per bounds.json and the mesh). The contact square of ±0.25 m is not this 1.04 m crate's footprint.
- The envelope itself is well formed. It passes every ENVELOPE/restposes check: payload_origin, payload_size, alignment, both size-rule branches, contact sums, probability order and sum, and unit quaternions.

What I did: reported it (`input-hash-mismatch`, `envelope-producer-disagrees`, `payload-is-spec-example`, `rest-pose-implausible`, all `warn`), kept the node listed, and did **not** attempt any repair. The data is not corrupt bytes; it is a mislabelled payload. Nothing in the file says what the correct poses are, so there is nothing to recover. I did not use the recovery procedure in SPEC §12, because the container and manifest are intact.

## 8. Rough timing

The shell clock read 15:44:03 at the start and 15:49:01 just before I wrote this report. That is the only hard data I have, and it seems short compared with my sense of the work. My subjective split:

| phase | time |
|---|---|
| fighting tool permissions, recon | ~10% |
| reading README, spec/README, MANIFEST, SPEC | ~30% |
| reading MINI-SPECS, envelope and layout docs | ~20% |
| writing the reader (one pass, one crash fix) | ~30% |
| investigating the rest-pose `input_hash` and writing this report | ~10% |

## 9. Artifacts in the working directory

- `werk_reader.py`: the reader.
- `extracted/`: the two extracted files.
- `tools/`: my probe scripts (`peek.py`, `walk.py`, `dump_entries.py`, `crosscheck.py`, `strings.py`; `strings.py` was never run).
- `scratch/pkg/`: copies of every package entry except `loaders/`, made for reading.

`mini-v1.werk` was not modified; it was only ever opened read-only.
