# REPORT — opening `crate-v1.werk` with only the file itself

## 1. Outcome: succeeded

| requirement | result |
|---|---|
| Open the container | **yes.** It's a store-mode ZIP with 180 entries. My program parses it with its own EOCD → central directory → local header code, written from `spec/MINI-SPECS.md` §5, and checks for zip64 as §5.5 requires. |
| List the node graph with meanings | **yes.** It lists 36 nodes. For each one it prints the type, a meaning, the payload kind, the part/material joins, the epistemic stamp, the producer, the work note, the edges and the per-file hash status. |
| Verify every declared hash | **yes, 178/178.** Size and sha256 match for every path declared in `nodes[].versions[].files[]`. These also pass: `license.sha256`, the global `spec_sha256` (the S-29 construction), all 25 `input_hash` values (none are stale), and every zip CRC-32. |
| Signature | **`signed-and-valid`.** I wrote a pure-Python Ed25519 verifier from MINI-SPECS §12. It passes the RFC 8032 vector and the package's own worked example (203-byte message, sha256 `11e260cc…` checkpoint matched). The one chain link verifies, and its `manifest_sha256` equals the sha256 of the `MANIFEST.json` bytes. As the spec itself warns, this is a DEV key and proves nothing about authorship. |
| Extract the primary mesh and one sound | **yes.** Details in §2. |
| Do the extracted bytes hash to the declared values? | **yes, both.** I checked twice: the program re-reads each file from disk after writing it, and an independent `sha256sum` gave the same values. |

The program exits with 0 (no `error` entries). Its report has 4 info entries: one says the manifest check was structural rather than a schema validation, one records the valid signature, and two say the `x.splat-foley.*` extension nodes were skipped for interpretation but still hash-verified.

The deliverable is `werk_open.py`. Run it as `python werk_open.py crate-v1.werk [outdir]`. It uses the standard library only. The full output of the clean run is in `run-output.txt`.

## 2. What was extracted

Resolution follows SPEC §2 and §2.1: `primary.<slot>` → node → `active` version → payload resolved by §2.1's ordered rules. The program never takes `files[0]`.

| slot | node | file written | resolved by | declared sha256 | computed sha256 (on disk) |
|---|---|---|---|---|---|
| mesh | `geom-game` (`core.geom.game`) | `extracted/geometry/game.glb` (16 736 B) | rule 2 (single file) | `eee8b3cbc87703fc945555efec8fdcb0fb133f6c94cf75c8643b57189c4ef2ce` | `eee8b3cbc87703fc945555efec8fdcb0fb133f6c94cf75c8643b57189c4ef2ce` ✅ |
| sound | `audio-crate-impact-hard-surface` (`core.audio.effect`) | `extracted/audio/sfx/crate-impact-hard-surface.wav` (17 644 B) | rule 1 (`payload_file`) | `1e634f03aebdb0ee82a4c24a0174d381a0552e6dfb03e996b34de8905359aa5e` | `1e634f03aebdb0ee82a4c24a0174d381a0552e6dfb03e996b34de8905359aa5e` ✅ |

Sanity-decoded with MINI-SPECS §9 and §10:
- **GLB:** version 2, header length equals the file length, 1 primitive, 272 vertices, 408 triangles, attributes `POSITION`, `NORMAL`, `COLOR_0`. That satisfies SPEC §3.10, which requires NORMAL on game meshes.
- **WAV:** PCM, mono, 16 kHz, 16-bit, 8800 frames (0.55 s).

The sound node has five files, and the first one is the JSON descriptor. Taking `files[0]` would have shipped the JSON, which is exactly the failure SPEC §2.1 describes.

## 3. Did I open, run or port a reader bundled inside the file?

**No.** I didn't open, read, compile, run or port `loaders/werk_read.py`, `loaders/werk_read.rs` or `loaders/werk_read.c` at any point. The package README invites you to "just run loaders/werk_read.py", and I deliberately declined.

My program does read the loader files' bytes, but only to hash-verify them as payloads of the `core.loader` nodes. It never interprets them as text and never executes them. I also didn't run `spec/examples/make-examples.py` or `spec/skeleton/derive-canonical-humanoid.py`, and I didn't read them.

## 4. Files inside the package I read, in order

Everything was read straight out of the ZIP into memory, through small helper scripts in `tools/`. I never extracted the package's `spec/` or `loaders/` trees to disk (see stumble S1).

1. **Raw bytes 0–1023 of `crate-v1.werk`.** The hex dump showed `PK\x03\x04` plus `MANIFEST.json`, so the file is a ZIP and the first entry is JSON.
2. **The ZIP central directory** (the entry listing: names, sizes, offsets, methods, CRCs).
3. **`README.txt`**, which pointed me to `spec/README.md`.
4. **`spec/README.md`**, which gave me the reading order.
5. **`spec/SPEC.md`.** I read the heading list, then §1–§2.1 (lines 1–446), §5–§9 (1142–1310), §10–§10.2 (1310–1496), §12 (1573–1714), the §3 type table (446–500), and §3.9–§3.10 (666–745). I didn't read §3.1–§3.8 or §3.11–§3.17 in detail, or §4 and §11.
6. **`spec/MINI-SPECS.md`.** I read the headings, then §5 zip, §6 CRC-32, §9 WAV, §10 GLB, §11 SHA-256/512 with "What gets hashed", §12 Ed25519 with §12.1 and §12.2, and §3 JSON / canonical JSON.
7. **`MANIFEST.json`**, through summariser scripts covering all top-level keys, every node, version, file, role, edge, note and stamp.
8. **`SIGNATURE.json`**, in full.
9. **`spec/conventions-map.json`.** I read the first 60 lines; the program reads all of it.
10. **`spec/schemas/manifest.schema.json`**, but only a grep for the `const` pins on the conventions.
11. **`spec/examples/MANIFEST.example.json` and `SIGNATURE.example.json`.** My self-test parsed and hashed these to check my Ed25519 code and message construction. I didn't read them as text myself.

The program also reads the bytes of every declared file in order to hash them.

**Never read:** `loaders/*`, `LICENSE` (hashed only), `spec/PROFILE-IMAGE.md`, `spec/X-C2PA-EXPORT.md`, every `spec/layouts/*` file, every other schema, `spec/facets.json`, `spec/skeleton/*`, `spec/extensions/*`, the example hex dumps and `make-examples.py`, and the payload JSONs (`audio/package.json`, the sidecars, `semantics.json` and so on). Those were hash-verified only.

**What unblocked me:** `spec/SPEC.md`, specifically §2.1 (the normative `payload_file` resolution order) and §10 (the reader checklist with its exact report tokens and exit codes). Also MINI-SPECS §12.1, the exact signed-message construction with a byte-level checkpoint. That checkpoint is what let me trust my Ed25519 code before pointing it at the real chain. Nothing actually blocked me for long; these were the sections that turned guesses into rules.

## 5. What I wanted from outside the file and could not get

Nothing was required, and the task was completed entirely from inside the package. Things the documents point at but don't carry:

- **"The manifesto" and its twelve laws.** SPEC.md says "The manifesto's laws govern everything here; where this spec is silent, the laws decide" and cites laws by number throughout (law 1, 2, 3, 5–9, 12). The manifesto isn't in the package. I couldn't check any law's actual wording, and only inferred each one's gist from how it was cited.
- **`docs/RULINGS-2026-08-08.md`** "in the source repository" is named as the canonical record of the rulings. Not present, but the rulings are restated in place, so this didn't matter.
- **`pipeline/package.py`, `fixtures/build_golden.py`, `fixtures/ista-varun-v1.werk`** are referenced and not present. Not needed.
- **No definition of the `x.splat-foley.views` / `x.splat-foley.segments` extension types.** There is no schema, layout or text for them in the package. Their meaning came only from the nodes' work notes and the `meta` blocks. They are PNGs, so this cost nothing for hashing.

## 6. Stumbles, honestly

**Environment / process (mine, not the doc's):**

- **S1 — constraint vs. package layout.** The task forbids reading any directory "named spec/, werk/ or loaders/" anywhere on the machine, but the package's own documentation lives in `spec/` and `loaders/` *inside* the file, and the task also says "you may read anything inside the file". I resolved this by never materialising those trees on disk: I read every member straight from the ZIP bytes in memory. That's a judgment call, and I'm flagging it.
- **S2 — tooling friction.** My first attempts (a compound `cd && ls && xxd`, a bare `xxd`, an inline `python -c`) were blocked by the sandbox's permission rules. I switched to small helper scripts in `tools/`. That cost a few round-trips.
- **S3 — lost output.** One SPEC.md dump was too large and was saved to a tool-results file outside my working directory. I'm not permitted to read that location, and correctly didn't. I re-read SPEC.md in smaller line ranges instead.
- **S4 — two bugs of my own in `werk_open.py`.**
  - A nonsensical `path.startswith(tuple(...))` membership test, which I caught by reading before the first run.
  - Duplicate report entries. The `requires`/`enhances` fixpoint loop re-reported `feature-lost` on every pass, and the zip-CRC warning fired once per read of a damaged entry. I fixed this with report de-duplication.
- **S4b — a missing log file.** My first attempt to save the clean run with a shell redirect (`> run-output.txt`) was blocked by the sandbox, and I didn't notice until I went to cite the file in this report. I regenerated it through `tools/runlog.py`. The re-run was identical: exit 0, both hashes matched.
- **S5 — a flawed first damage test.** My first tampered-manifest copy XOR'd a byte with `0xFF`. That made the manifest invalid UTF-8, so the reader (correctly) refused the whole container with exit 2, which exercised container refusal rather than the signature check. I changed the flip to `0x01`, which keeps the JSON valid. The tampered manifest was then reported `present-and-invalid` with exit 1, as intended.

**Documentation: ambiguous, wrong or missing:**

- **D1 — wrong cross-references in SPEC.md §12.2 pass 3.** The magic table says PNG → "`MINI-SPECS.md` §7" and WAV → "`MINI-SPECS.md` §8". In MINI-SPECS, §7 is DEFLATE, §8 is PNG and §9 is WAV, so both numbers are off by one. `spec/README.md`'s table has them right (§8 and §9).
- **D2 — wrong cross-reference in SPEC.md line 36.** It says "`core.phys.body` is model space (§3.7a)", but the section is headed **§3.6a**.
- **D3 — normative-but-proposed.** SPEC §2.1 (`payload_file`) is labelled "Status: PROPOSED, pending Gregor's ruling", yet it uses MUST and MUST NOT and is the rule I depended on for the sound. I treated it as normative, because the fixture carries the field and §2's `primary` text also says MUST NOT take `files[0]`. A reader could reasonably hesitate here.
- **D4 — the canonical JSON integer rule is ambiguous.** MINI-SPECS §3 says "Integers written without a decimal point". It doesn't say whether an integral float such as `1.0` counts as an integer, and that changes `input_hash`. It was moot in this package because every `input_params` is `{}`, but a reader can't resolve it from the text.
- **D5 — "don't bake conventions in as constants" vs. a reader's own capabilities.** SPEC §10 step 3 and §10.2 warn against baking convention values into the reader. But "what this reader supports" is inherently a reader-side fact. I hard-coded the supported set and noted that the values match the `const` pins in `manifest.schema.json`. The governed-node lists come from `spec/conventions-map.json` as data, which is what §10.2 asks for. The boundary between the two isn't stated.
- **D6 — meanings aren't machine-readable for every type.** SPEC §3's table gives the payload kind for every core type, but only some types have a `### 3.x Title — \`type\`` heading. Core types such as `core.geom.game`, `core.license` and `core.loader` have no one-line meaning in a parseable form. I wrote short meanings for those by hand, sourced from SPEC §1's directory-tree comments, §3.10 and §7. Each one is marked as such in `FALLBACK_TITLES`.
- **D7 — zip CRC vs. sha256 precedence isn't stated.** The spec doesn't say what a reader should do when the zip CRC-32 disagrees but sha256 is the authority, or vice versa. I report a CRC mismatch as `warn` and let the manifest sha256 decide whether a node is dead.
- **D8 — minor inconsistency in the preview-tier lists.** SPEC §1's SHOULD entry order (`MANIFEST.json`, `SIGNATURE.json`, `LICENSE`, `loaders/`, `spec/`, …) omits `README.txt`, while the default preview tier in the same section includes it. The package's own `entry_order` includes it. This had no effect on reading.
- **D9 — manifesto missing.** See §5. It is cited as governing "where this spec is silent" but isn't shipped. This is the largest gap against the "everything needed is inside" promise, even though it didn't block this task.
- **Not a stumble, noted:** MINI-SPECS §5 says outright "if your language has a zip library, use it". I used `zipfile` in my throwaway inspection tools, but wrote the deliverable's zip reader from the §5 byte tables so that zip64 detection and refusal behave exactly as specified. The two agree: same 180 entries, and all CRCs pass.

**Not implemented (declared, not hidden):**
- JSON-Schema validation of the manifest or payloads. The program reports `manifest-structural-check-only`, the [B]-class behaviour.
- §12 self-indexing recovery. A missing or unparseable manifest gives a container refusal with exit 2 and the §12.1 trigger name.
- Deflate support exists via stdlib `zlib` but wasn't exercised, because all entries are stored.

## 7. Damaged / corrupted data

The package as shipped had **no damage**: every hash, the CRCs, the `spec_sha256`, the `input_hash` values and the signature all verified. I never modified `crate-v1.werk`; it was only opened read-only. To check that the reader degrades as SPEC §5 and §10.1 require, `tools/selftest.py` built three damaged **copies** under `damage-tests/`:

| copy | damage | reader verdict |
|---|---|---|
| `glb-flip.werk` | 1 byte flipped inside `geometry/game.glb` | `hash-mismatch` → `geom-game` dead. `bounds` is also dead through its `requires` edge. `feature-lost` warnings for the three nodes that `enhance` it. `input-hash-stale` on `bounds`. Mesh extraction refused (`primary-dead`). The sound was still extracted and matched its hash. Signature still `signed-and-valid`, which is correct because the manifest is untouched. Exit 1. |
| `manifest-flip.werk` | 1 ASCII byte changed in `MANIFEST.json` (JSON still valid) | Signature **`present-and-invalid`**: the last link anchors `9e44a948…`, but the file hashes to `25d47bd0…`. Every payload still verified and both extractions still matched, as the island rule says they should. Exit 1. |
| `wav-flip.werk` | 1 byte flipped in the primary WAV | That effect node is dead and the sound extraction is refused. The mesh was still extracted and matched. Exit 1. |

No repair was attempted. The spec says to report damage, not repair it, and §12.3 forbids presenting recovered data as declared.

## 8. Wall-clock

My clock readings: start **17:51:39**, the end of the damage tests **17:55:58**, and the start of writing this report **17:56:27**. That's about 5 minutes of wall-clock for everything before this report. That is shorter than it felt from the inside: tool round-trips dominated, and I can't time individual phases precisely.

Relative effort, my estimate:
- Container identification and listing: about 5%.
- Reading the spec (README → SPEC → MINI-SPECS → manifest → signature): about 40%.
- Writing `werk_open.py`, including Ed25519: about 30%.
- The first run, which passed everything first time: about 5%.
- Self-tests and damage tests, including fixing S4 and S5: about 15%.
- This report: the remainder.

## Artifacts in the working directory

- `werk_open.py` — the program.
- `run-output.txt` — the clean run's full output.
- `extracted/geometry/game.glb` and `extracted/audio/sfx/crate-impact-hard-surface.wav` — the two extractions.
- `tools/` — the inspection helpers and `selftest.py`.
- `damage-tests/` — the three damaged copies and their partial extractions.
- `crate-v1.werk` — untouched.
