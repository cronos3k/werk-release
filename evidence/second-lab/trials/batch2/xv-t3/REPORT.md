# REPORT — crate-v1.werk

## Result: success

| task | result |
|---|---|
| Open the container | **yes.** It is a store-mode zip with 180 entries and only method 0. Zip64 detection ran and found none. Every entry's CRC-32 was checked. |
| List the node graph with meanings | **yes.** 36 nodes, each with its type, a meaning, the active version, the work note, the producer/model, the epistemic stamp, confidence and edges. |
| Verify every declared hash | **yes, 0 mismatches.** That covers 178 `files[].sha256` and `size` values, `license.sha256`, `spec_sha256` (over 56 `spec/` files), all 25 `input_hash` values, and the Ed25519 signature chain, which came out **signed-and-valid**. That signature uses a DEV key, so it proves the chain verifies and says nothing about authorship. |
| Extract the primary mesh and one sound | **yes.** Both come from `MANIFEST.json → primary`, so no fallback was needed. |
| Extracted bytes hash to the manifest's values | **yes, both match.** I re-read each file from disk after writing it and hashed it. |

Program: `werk_reader.py`. Run it as `python -I werk_reader.py crate-v1.werk --out extracted`. It exits with 0 on this file.
It uses only the Python standard library (`zipfile`, `zlib`, `hashlib`, `json`, `struct`). I wrote Ed25519 verification
by hand from `spec/MINI-SPECS.md` §12, because Python has no built-in Ed25519. It passes the RFC 8032 vector printed there.

## What I extracted

| slot | node | resolved by | file written | declared sha256 | computed sha256 |
|---|---|---|---|---|---|
| primary.mesh | `geom-game` (`core.geom.game`) | SPEC §2.1 rule 2 (single file) | `extracted/geometry_game.glb` (16736 B) | `eee8b3cbc87703fc945555efec8fdcb0fb133f6c94cf75c8643b57189c4ef2ce` | `eee8b3cbc87703fc945555efec8fdcb0fb133f6c94cf75c8643b57189c4ef2ce` ✔ |
| primary.sound | `audio-crate-impact-hard-surface` (`core.audio.effect`) | SPEC §2.1 rule 1 (`payload_file`) | `extracted/audio_sfx_crate-impact-hard-surface.wav` (17644 B) | `1e634f03aebdb0ee82a4c24a0174d381a0552e6dfb03e996b34de8905359aa5e` | `1e634f03aebdb0ee82a4c24a0174d381a0552e6dfb03e996b34de8905359aa5e` ✔ |

Structural checks on the payloads:
- **GLB:** glTF v2 with a correct length. 408 triangles and 272 vertices. All primitives are mode 4 and indexed. Attributes are POSITION, NORMAL and COLOR_0, which meets the §3.10 requirement for renderable meshes. Every accessor fits inside its buffer view.
- **WAV:** RIFF/WAVE, PCM, 16-bit, mono, 16 kHz. 8800 frames, which is 0.55 s. This agrees with the sidecar's `audio_format` and with `refined.duration` = 0.55.

The sound node lists five files, and `files[0]` is the JSON descriptor. The reader never takes `files[0]`. It follows `payload_file`, as §2.1 requires.

## Did I open, run or port a bundled reader?

**No.** I never opened, read, ran or ported `loaders/werk_read.py`, `loaders/werk_read.rs` or `loaders/werk_read.c`.
`README.txt` suggests "just run loaders/werk_read.py"; I did not. My reader only hashes the three loader files as data.
I also did not read or run `spec/examples/make-examples.py` or `spec/skeleton/derive-canonical-humanoid.py`.

When I unpacked a working copy (`scratch/pkg/`) to read the documentation, the unpack wrote the loader files to disk as plain bytes. Nothing in that copy was executed.

## Files I read inside the package, in order

1. The zip itself. I hex-dumped the first 1 KB, which is the start of `MANIFEST.json`, and listed the central directory with `zipfile`.
2. `README.txt`
3. `spec/README.md`. It told me the reading order.
4. `spec/SPEC.md`: lines 1–899 (§1–§3.14 start) and 1131–1715 (§4–§12). **I skipped §3.14–§3.17** (retarget, points, gsplat, tools) because they don't apply to this package.
5. `spec/MINI-SPECS.md`: §1–§5 plus the start of §6, then §9–§13. **I skipped CRC/DEFLATE/PNG detail (§6–§8)** because zlib and zipfile cover them.
6. `SIGNATURE.json`
7. `MANIFEST.json`, through my own summary scripts: the top-level keys, a one-line summary of all 36 nodes, and five nodes in full. The program then parses all of it.
8. `spec/conventions-map.json` (first 60 lines)
9. `audio/sfx/crate-impact-hard-surface.json`, to learn the `audio_format` field names.

**Not read at all:** `loaders/*`, `spec/schemas/*`, `spec/layouts/*`, `spec/examples/*`, `spec/extensions/*`,
`spec/facets.json`, `spec/skeleton/*`, `spec/PROFILE-IMAGE.md`, `spec/X-C2PA-EXPORT.md`, `LICENSE`.

**What unblocked me:** I was never truly blocked. **`spec/SPEC.md`** did most of the work: §10 gave the reader checklist, §2.1 gave the payload resolution order, §2 gave the `spec_sha256` algorithm, and §6 gave the chain procedure. **`spec/MINI-SPECS.md` §11–§12.1** made the integrity work possible: the `input_hash` construction with a worked example, the Ed25519 parameters and verify equation, and the exact signed-message string. Without §12 I would have had to report the signature as `unverified`.

## What I wanted from outside the file and could not get

- **A JSON Schema validator.** The SPEC §10 [F] step 2 asks you to validate `MANIFEST.json` and the JSON payloads against their schemas. Python's standard library has no validator, and I did not write one. My reader only does the [B] structural check and says so in its output. I am **not** claiming any schema validity.
- Nothing else. Everything else I needed was inside the file. I did not fetch anything, search the web, or look outside the working directory.

Prior knowledge I used anyway, stated honestly:
- I recognised `PK\x03\x04` as a zip from the first 16 bytes before reading MINI-SPECS §5. MINI-SPECS §5 later confirmed it and explicitly endorses using the zip library.
- General Python knowledge: the stdlib `zipfile`, `hashlib` and `zlib` APIs, and the meaning of raw-deflate wbits=-15. The deflate path is never used by this store-only file.
- I did not recognise the werk format itself. Every format rule came from the spec text inside the file.

## Stumbles, honestly

1. **A bug in my own reader** (about 1 minute). In the self-made damage test, Python's `zipfile.read()` raised on the CRC mismatch. The node loop caught it, but the later `input_hash` pass re-read the same entry and crashed. That violates SPEC §10.1 ("never exit, mark the node dead"). I fixed it by reading stored bytes straight from the local header (MINI-SPECS §5.3) and recording CRC failures as report entries.
2. **Harness friction, not doc friction.** The sandbox rejected inline `python -c`, pipes and shell redirects. I had to write small helper scripts under `tools/` for each inspection step. That cost a few round-trips. I could also not save the run log by redirecting to a file. The output shown above is from a direct run.
3. **Wrong cross-references in SPEC §12.2 (Pass 3 table).** It sends PNG to "`MINI-SPECS.md` §7" and WAV to "§8". In the MINI-SPECS that ships here, §7 is DEFLATE, §8 is PNG and §9 is WAV. `spec/README.md`'s table has it right (§8 PNG, §9 WAV). It cost me no time because I navigated by heading, but it is a wrong pointer.
4. **SPEC contradicts itself on the canonical skeleton.** §3.5 says "Bone count stayed at 23" and that the "+1" was filed rather than applied. §11 says ruling 9 changed the "bone count 23 → 24". `spec/README.md` still says the skeleton is "Status: draft, pending approval", while SPEC §3.5 and §11 say both files are `approved`. This doesn't affect this package, which has no skeleton, but a reader could not tell which number is true.
5. **SPEC §11 has piled-up history.** Its bullets say "Two conformance fixtures now exist", then "Three…", then "Four…", one after another, and the first ruling bullet still says "Four rulings are PROPOSED" (struck through). Readable, but you have to work out which bullet is current.
6. **`payload_file` (§2.1) is marked "Status: PROPOSED, pending Gregor's ruling".** Yet its resolution order is labelled NORMATIVE, and the document's preamble says all PROPOSED rulings are now RULED. I followed it because it is additive and this package uses it. Its status is still ambiguous.
7. **MINI-SPECS §5.4 reads like a MUST but the ruling is a SHOULD.** It says "Entry order is the preview-first order declared in `container.entry_order`", while SPEC §1 / S-14 rules entry order a SHOULD that readers must never depend on. My reader does not check order.
8. **No definition for the `x.splat-foley.*` node types.** Nothing in `spec/` defines `x.splat-foley.views` or `x.splat-foley.segments`. Their meanings in my listing come only from the node `note` and `meta`. SPEC §8 only requires x.* *binaries* to ship a layout, and these are PNGs, so this is probably conformant. My reader labels them `node-skipped-unknown-type` (info) even though it still hash-verifies them. The label is slightly misleading.
9. **Canonical JSON is only partly implemented.** My `canonical_json` uses `json.dumps(sort_keys, compact)`. That matches MINI-SPECS §3 for this package, where every `input_params` is `{}`. I did not check non-integer float formatting or the sort order of non-ASCII keys against the §3 rules.
10. **`container.total_size_bytes` is missing from the manifest.** SPEC §2 says S-30 "promoted" it, yet it is optional and absent here. I computed it (13,571,735) and reported it rather than checking it.
11. **I did not run the §12.1 example checkpoint** (`sha256(message)` over `MANIFEST.example.json`). The real chain verified on the first try, so I didn't need it. My only proof that the verifier rejects bad signatures is the RFC vector with a changed message.
12. **Partial reading.** I skipped parts of SPEC.md and MINI-SPECS.md (listed above) and all of the schemas and layouts. If those hold rules that affect this package, I did not apply them.

## Damaged or corrupted data

The original file was intact; there were no mismatches. To test the failure path I made **a copy**, `scratch/damaged-glb.werk`, with one byte flipped inside `geometry/game.glb`. The original `crate-v1.werk` was never written to. On the damaged copy the reader:
- reported `zip-crc-mismatch` and `hash-mismatch` for `geometry/game.glb` and marked `geom-game` dead;
- also marked `bounds` dead, because of its `requires` edge (SPEC §5);
- flagged `input-hash-stale` on `bounds`;
- refused to extract the dead primary mesh (`primary-dead`) but still extracted the sound with a matching hash;
- kept the signature at `signed-and-valid`. That is correct: the manifest bytes were untouched, so the chain is valid and the damage shows up at the file-hash level;
- exited with status 1, as §10.2 specifies.

I did not try recovery when the manifest itself is damaged (SPEC §12). The reader exits with code 2 and `manifest-absent`/`manifest-unparseable` instead.

## Wall-clock

Timestamps from `date`. Total is about 4 minutes from the first command to a verified run, plus writing this report.

| phase | approx. |
|---|---|
| 00:53:02 Orientation: hex dump, zip listing, unpacking a doc copy | ~0.5 min (plus permission round-trips) |
| Reading README.txt, spec/README.md, SPEC.md, MINI-SPECS.md, SIGNATURE.json, manifest summaries | ~1.5 min |
| Writing `werk_reader.py` | ~1 min |
| First run: all checks passed first time | seconds |
| Damage test, CRC-crash bug, fix, re-test | ~1 min |
| 00:56:55 Report | ~1–2 min |

## Files in this directory

- `werk_reader.py` — the program
- `extracted/geometry_game.glb`, `extracted/audio_sfx_crate-impact-hard-surface.wav` — the extracted payloads
- `tools/` — small inspection helpers I wrote (hexdump, zip listing, unpack copy, manifest summary, damage maker)
- `scratch/pkg/` — an unpacked read-only copy used for reading docs. `scratch/damaged-glb.werk` is the damaged test copy.
- `crate-v1.werk` — untouched
