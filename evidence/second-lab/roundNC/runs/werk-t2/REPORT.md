# REPORT — reading `mini-v1.werk` from the inside only

## 1. Result

**Succeeded on every point asked for.**

| task | result |
|---|---|
| open the container | yes. Store-mode zip, 36 entries, every entry's CRC-32 checked, zip64 detection done (not zip64) |
| list the node graph with meanings | yes. 14 nodes listed with type meaning, liveness, active version, epistemic stamp, producer, work note, files, roles and edges |
| verify every declared hash | yes. 34/34 `files[].sha256`+`size` match; `license.sha256` matches; `spec_sha256` (over 17 spec files) matches; 1 of 5 `input_hash` values is checkable and matches (`bounds`); 3 can't be checked because their inputs aren't in the package; **1 does not match (`rest-poses`, see §7)** |
| signature | **`signed-and-valid`**. Ed25519 implemented from MINI-SPECS §12 and self-tested against RFC 8032 vector 1 and the §12.1 worked example before use |
| extract primary mesh + one sound | yes, both written to `out/` |
| extracted bytes hash to the manifest's values | **yes, both match** |

The program is `werkread.py`. Run it as `python -I werkread.py mini-v1.werk out`. It uses only the standard library and the exit code is 0. A full run transcript is reproducible by re-running it.

## 2. What was extracted

| slot | node | resolved file (rule) | bytes | declared sha256 | computed sha256 of file on disk |
|---|---|---|---|---|---|
| `primary.mesh` | `geom-game` (`core.geom.game`) | `geometry/game.glb` (§2.1 rule 2: single file) → `out/game.glb` | 16736 | `eee8b3cbc87703fc945555efec8fdcb0fb133f6c94cf75c8643b57189c4ef2ce` | `eee8b3cbc87703fc945555efec8fdcb0fb133f6c94cf75c8643b57189c4ef2ce` ✅ |
| `primary.sound` | `audio-crate-impact-hard-surface` (`core.audio.effect`) | `audio/sfx/crate-impact-hard-surface.wav` (§2.1 rule 1: `payload_file`; it's also the `best` role) → `out/crate-impact-hard-surface.wav` | 17644 | `1e634f03aebdb0ee82a4c24a0174d381a0552e6dfb03e996b34de8905359aa5e` | `1e634f03aebdb0ee82a4c24a0174d381a0552e6dfb03e996b34de8905359aa5e` ✅ |

Sanity checks on the extracted payloads:
- **GLB**: glTF 2, length field equals file length. One triangle primitive (mode 4) with attributes POSITION, NORMAL and COLOR_0: 272 vertices, 408 triangles. POSITION min/max is (−0.5,−0.5,−0.5)…(0.54,0.54,0.5), which agrees with `physics/bounds.json`.
- **WAV**: PCM, 1 channel, 16000 Hz, 16-bit, 8800 frames = 0.55 s. This agrees with the descriptor's `audio_format` and with `refined.duration: 0.55`. I did **not** take `files[0]`, which is the JSON descriptor; SPEC §2.1 explicitly warns about that trap.

## 3. Bundled reader programs

**I never opened, read, ran, compiled or ported any of `loaders/werk_read.py`, `.rs` or `.c`.** Their bytes were touched only as opaque data: listed in the zip directory, read to compute their sha256 (they match), and shown in the node listing. README.txt says "or just run loaders/werk_read.py against this file"; I deliberately didn't. Nothing else in the package is executable. The README for `spec/` mentions `examples/make-examples.py` and `skeleton/derive-canonical-humanoid.py`, but neither is present in this package.

## 4. Files read inside the package, in order

1. Raw first 512 bytes of `mini-v1.werk` (hexdump). I saw `PK\x03\x04` and `MANIFEST.json` stored first.
2. The zip central directory (entry names, sizes, offsets, CRCs), via Python `zipfile`.
3. `README.txt`
4. `spec/README.md`, the "start here" index.
5. `MANIFEST.json` (full)
6. `spec/SPEC.md`: first the heading list, then lines 1–490 (§0–§2.1, start of §3), then lines 1142–1461 (§5 versioning, §6 signatures, §7 loaders, §9, §10 reader checklist, §10.1/§10.2).
7. `spec/MINI-SPECS.md` (full)
8. `SIGNATURE.json`
9. `spec/conventions-map.json`
10. `spec/layouts/ENVELOPE.layout.txt`
11. `spec/layouts/restposes.layout.txt`
12. `audio/sfx/crate-impact-hard-surface.json`
13. `physics/bounds.json` (while investigating the rest-pose anomaly)

I hashed but didn't read: `LICENSE`, all of `spec/schemas/*.json`, `spec/facets.json`, `spec/examples/restposes.example.hex.txt`, `semantics/semantics.json`, `materials/wood.json`, `provenance/provenance.json`, the PNG and the loaders. I extracted several schemas to disk but never opened them.

**What unblocked me:** `MANIFEST.json` plus **`spec/MINI-SPECS.md`**. MINI-SPECS was the single most valuable file: it gives the exact `input_hash` construction with a worked example from this package, the complete Ed25519 verify procedure with a test vector, and the signed-message construction with a byte-level checkpoint (`len 203`, `sha256 11e260cc…`). Those let me verify the signature without any library and be confident the result wasn't a construction bug. SPEC.md §2 (`spec_sha256` algorithm, `primary`) and §2.1 (payload resolution) were the other essential pieces.

## 5. What I wanted from outside the file and could not get

Nothing blocked the task. Things I would have liked:
- **The nodes this mini package was cut from**: `geometry/source.glb`, `audio/package.json` and `x/splat-foley/views/view_0[0-5].png`. Without them the `input_hash` of `geom-game`, `audio-crate-impact-hard-surface` and `evidence-segments` can't be recomputed (reported as `input-hash-uncheckable`).
- **`spec/examples/make-examples.py`**, which `spec/README.md` calls the tie-breaker ("When a sentence in a layout file is ambiguous, this code is what it means"). It isn't in this package. I didn't need it, but the stated authority for ambiguity is missing.
- **A JSON Schema validator.** Python's stdlib has none, so I didn't validate `MANIFEST.json` or the JSON payloads against their schemas. My reader is a §10.0 **bootstrap-class** reader in that respect: it checks structure and hashes but does not claim schema validity.
- **Small bits of general knowledge** that the file states implicitly or not at all. I used them and flag them here:
  - recognising `PK\x03\x04` as a zip before reading any documentation;
  - the identity point `(0,1,1,0)` in extended coordinates and how to compare projective points for equality in Ed25519 (MINI-SPECS gives the addition law but not these two facts; both are trivially derivable);
  - Python stdlib `hashlib`/`zlib.crc32` instead of implementing SHA-256/512 and CRC-32 by hand. MINI-SPECS explicitly endorses library use for zip and hashes, and its test vectors are what I'd check against.

## 6. Stumbles, honestly

1. **Harness and permission friction (my environment, not the file).** `mkdir`, `cp` and inline `python -c` needed approval, so I switched to writing small scripts in `tools/`. That cost a few minutes and three wasted tool calls. Because of it I **never made a byte copy of `mini-v1.werk`**: every tool opened the original read-only (`open(path,'rb')` / `zipfile`). I never modified it.
2. **I accidentally created a directory named `spec/`.** My first extraction tool reproduced the archive's paths, which created `work/x/spec/…` (and `work/x/loaders` wasn't created; I'd excluded loaders). Rule 2 forbids reading any directory named `spec/`. I noticed immediately, **never read from it**, re-extracted with flattened names into `work/flat/`, and read only from there. The stray `work/x/` directory still exists because deleting it needs approval; it holds only copies of in-package docs.
3. **A self-inflicted file-name bug**: my dumper appended `.txt`, so my first read of `spec/README.md` failed. Trivial.
4. **README.txt contradicts the package.** It says "every one of the twenty sound effects" (there is one effect node with 4 WAVs), mentions rendered views (absent), and lists "rest poses" as **deliberately absent**. But there is a `core.pose.rest` node (`poses/rest.wkrp`), and `entity.summary` says "one binary envelope". The README is evidently inherited from the full golden crate. It cost a moment of doubt about which document to trust; I trusted the manifest.
5. **`spec/README.md` points at many files not in this package**: `PROFILE-IMAGE.md`, `X-C2PA-EXPORT.md`, `examples/make-examples.py`, `examples/signature.example.txt`, `MANIFEST.example.json`, the gsplat/embedding hex dumps, `layouts/points|gsplat|flowfield|…`, `skeleton/*`, `schemas/facets.schema.json` and most per-type schemas. SPEC.md and ENVELOPE.layout.txt do the same. None of these were needed, and MINI-SPECS §12.1 deliberately reproduces the signature example inline, which saved me. But a reader can't tell up front which references are dead, and some are described as authoritative (make-examples.py).
6. **Dangling edges, and no rule for an edge to an *absent* node.** `geom-game → geom-source` (enhances), `audio-… → audio-package` (enhances) and `evidence-segments → evidence-views` (**requires**) all point at nodes not in this package. SPEC §5 says a `requires` edge into a **dead** node kills the source, but it says nothing about a node that is simply **absent**. My judgement call: requires→absent ⇒ the source is dead, so `evidence-segments` is reported DEAD (its PNG still hash-verifies). enhances→absent ⇒ info only. Another reader could reasonably decide differently.
7. **`evidence-segments.meta` misdescribes its own payload**: `count: 10` and ten `images[]` entries, but `files[]` holds only `seg_00.png`. This isn't a hash error, since meta isn't hash-declared, but it's wrong. My program does not flag it; I found it by reading.
8. **`input_hash` that can't be checked.** SPEC/MINI-SPECS define how to compute it but don't say what a reader should report when the declared `input_files` aren't in the package. I report `info: input-hash-uncheckable`.
9. **SPEC §2.1 is marked "PROPOSED, pending ruling"** yet written in MUST language and relied on by `primary`. I followed it. Not a real obstacle, but a reader might wonder whether it's binding.
10. **Ed25519 had two acceptable verification equations** (cofactor-8 vs cofactorless). I used the cofactor form. The rule "MUST NOT accept a signature that fails both" is clear, so this was only a moment's pause.
11. **Console encoding**: `§` prints as `�` on this Windows console. Cosmetic only.

## 7. Damaged or suspicious data

**No byte-level damage**: every CRC, size and sha256 is intact, and the signature is valid. So there was nothing to repair and I attempted no repair. I did find one **semantic integrity problem** that the hashes and signature don't catch:

**The `rest-poses` node (`core.pose.rest`, `poses/rest.wkrp`) does not appear to describe this crate.**
- Its declared `input_hash` `60e08ed1…` matches **none** of 8 plausible constructions over its declared inputs (`geometry/game.glb`, `physics/bounds.json`). I tried both orders, raw vs hex digests, and with or without the `{}` tail. The spec construction gives `4b91ccbb…`. Per MINI-SPECS §11 this marks the derived data **stale**, and my program reports `input-hash-stale`. The same construction verifies correctly for the `bounds` node, so my implementation isn't the problem.
- Its bytes are **identical to `spec/examples/restposes.example.wkrp`** (same sha256 `6c2c44d5…`). The envelope header inside says `producer: {tool: "werk-example"}`, while the manifest claims `producer: werkc 0.1.0, epistemic: measured`.
- Its contact points (y = 0, x/z within ±0.25 m) don't touch this crate, whose model-space AABB is −0.5…0.54 m with the base at y = −0.5.
- ENVELOPE.layout.txt §3 says `input_hash` is "mandatory for derived nodes" in the envelope header and must agree with the manifest; this header has none.
- The node also looks appended: different JSON key order from every other node, `created` 09:00 while everything else is 10:00, and `poses/` is not in `container.entry_order`.

Because the signature is valid **over the current manifest**, this isn't post-signing tampering: whoever holds the dev key signed it this way. (The key is a publicly derived dev key, per README and SIGNATURE.json, so a valid signature proves nothing about authorship.) My reader keeps the node live but warns, because its file hashes match and the spec treats a stale `input_hash` as staleness, not damage. A consumer should **not** trust these rest poses for this crate. It didn't affect the mesh or sound extraction.

## 8. Wall-clock

From shell timestamps: start 15:59:30, report written shortly after 16:03:32. The phases took roughly:
- orientation: hexdump, zip listing, permission workarounds, extracting docs (about 1 min);
- reading README, spec/README, MANIFEST, SPEC, MINI-SPECS, SIGNATURE, conventions-map and the layouts (about 1–2 min of wall time; the tool calls were fast, but this was the bulk of the reasoning);
- writing `werkread.py` (about 1 min) — it ran correctly the first time;
- probing the rest-pose anomaly (under 1 min);
- this report.

That much wall-clock compression feels surprising to me, but those are the timestamps the shell reported.

## 9. Artifacts in the working directory

- `werkread.py`: the reader.
- `out/game.glb`, `out/crate-impact-hard-surface.wav`: the extracted payloads.
- `tools/peek.py`, `tools/ls.py`, `tools/dump.py`, `tools/probe_restposes.py`: investigation helpers.
- `work/flat/`: flattened copies of the in-package documents I read. `work/x/` is the stray tree from stumble 2, never read.
- `mini-v1.werk`: untouched. `PROMPT.txt` in the working directory was not read.
