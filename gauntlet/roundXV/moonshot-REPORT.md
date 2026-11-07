# REPORT: Reading crate-v1.werk

## Success

Yes. The program `read_crate.py` succeeded in every required task:

1. **Opened the container** — `crate-v1.werk` is a zip archive (magic `PK\x03\x04`, compression method `store`). It was opened with Python's standard-library `zipfile` module.
2. **Listed the node graph with meanings** — All 36 nodes from `MANIFEST.json` were printed with `node_id`, `type`, the active version's human-readable `note` (meaning), file list, and edges.
3. **Verified every declared hash** — Every file entry under the active versions of every node that carried a `sha256` was checked. 172 files were checked; 172 passed. No hash mismatches and no missing files.
4. **Extracted the primary mesh and one sound** —
   - Primary mesh node `geom-game` → `geometry/game.glb` → extracted as `game.glb`.
   - Primary sound node `audio-crate-impact-hard-surface`, role `best` → `audio/sfx/crate-impact-hard-surface.wav` → extracted as `crate-impact-hard-surface.wav`.
5. **Extracted bytes match the manifest hashes** — both computed sha256 values equal the declared values.

## Extracted files

| File | Source path in archive | Declared sha256 | Computed sha256 | Size | Match |
|------|------------------------|-----------------|-----------------|------|-------|
| `game.glb` | `geometry/game.glb` | `eee8b3cbc87703fc945555efec8fdcb0fb133f6c94cf75c8643b57189c4ef2ce` | `eee8b3cbc87703fc945555efec8fdcb0fb133f6c94cf75c8643b57189c4ef2ce` | 16 736 bytes | Yes |
| `crate-impact-hard-surface.wav` | `audio/sfx/crate-impact-hard-surface.wav` | `1e634f03aebdb0ee82a4c24a0174d381a0552e6dfb03e996b34de8905359aa5e` | `1e634f03aebdb0ee82a4c24a0174d381a0552e6dfb03e996b34de8905359aa5e` | 17 644 bytes | Yes |

`file` confirms `game.glb` is a glTF binary model version 2 and `crate-impact-hard-surface.wav` is a RIFF/WAVE PCM 16-bit mono 16000 Hz file.

## Use of bundled reader programs

**None.** I never opened, ran, or ported `loaders/werk_read.py`, `loaders/werk_read.rs`, or `loaders/werk_read.c`. The task explicitly forbids executing any program that came out of the file, and I treated the bundled loaders as off-limits for execution and for reverse-engineering. Every rule used by `read_crate.py` was derived directly from `MANIFEST.json` and the zip container structure.

## Files inside the package read, in order

1. **`crate-v1.werk` (raw bytes)** — first 32 bytes via `xxd` to recognise the zip magic and locate `MANIFEST.json`.
2. **`MANIFEST.json`** — extracted from the zip and read fully. This was the unblocking file. It contains the complete node graph, file paths, sha256 hashes, sizes, the `primary` block, and human-readable notes for every node.

No other internal files needed to be read individually before writing the program; `MANIFEST.json` is self-contained enough for the required tasks. During program execution, all 172 payload files were read once from the zip so their hashes could be verified, and the two primary assets were written to disk.

## What I wanted from outside the file and could not get

Nothing. Every piece of information required to complete the task was present inside `crate-v1.werk`:
- Container format (zip) from the file magic and from `container.form`.
- Compression method (`store`) from `container.zip_compression`.
- File list, hashes, sizes from each node's active version.
- Primary asset IDs from the `primary` block.
- Meaningful descriptions from each version's `note` field.

## Stumbles, ambiguities, and time costs

1. **Initial tool failure (under 1 minute).** My first attempt to read `crate-v1.werk` with the `Read` tool failed because it is binary. I switched to `Bash` with `xxd` and `file`, which immediately revealed the zip structure. This was a minor tooling stumble, not a format problem.
2. **No clear "primary sound file" field (2 minutes).** The `primary.sound` value is a node ID (`audio-crate-impact-hard-surface`). The node contains five files: a JSON descriptor, a `best` WAV, a `raw` WAV, and two `variation` WAVs. The meaning of each file is given by the `role` field, so I chose `role == "best"` as the canonical primary sound. This is reasonable but not explicitly stated in a single "primary_sound_file" field; a reader has to know to look at `role`.
3. **Active version selection (1 minute).** Nodes have a `versions` array and an `active` integer. I selected the version whose `v` matched `active`. In this file every node has exactly one version (`v: 1`) and `active: 1`, so the rule was trivial, but the spec could have left room for ambiguity if `active` were missing. I added a fallback to the first version just in case.
4. **Compression sanity check (negligible).** The manifest says `zip_compression: "store"`. I verified this with `zipfile` and would have warned if any entry used a different method. All entries were stored uncompressed, as expected.
5. **Signature not verified (intentional).** `SIGNATURE.json` exists and declares an `ed25519` signature, but the task only asked to verify declared *hashes*, not cryptographic signatures. I did not verify the signature because (a) the task did not require it, (b) doing so correctly would require understanding the exact signed payload construction from the spec, and (c) that would risk going beyond the simple hash-verification requirement.

## Damaged or corrupted data

None encountered. Every one of the 172 declared files was present in the archive, every size matched, and every sha256 verified. The extracted `game.glb` and `crate-impact-hard-surface.wav` are recognised by `file` as valid glTF and WAV respectively, and their computed hashes match the manifest exactly.

## Wall-clock time estimate

| Phase | Approximate time |
|-------|------------------|
| Recognise file as zip and inspect header | < 1 min |
| Extract and read full `MANIFEST.json` | 1–2 min |
| Understand node structure, primary block, and `role` semantics | 2–3 min |
| Write `read_crate.py` | 5–7 min |
| Run program, verify output, check extracted files | 2–3 min |
| Write `REPORT.md` | 5 min |
| **Total** | **~15–20 minutes** |

The program's own runtime was ~0.025 s.

## Program

`read_crate.py` in the working directory implements the above. It uses only `zipfile`, `hashlib`, `json`, and standard path/time utilities.
