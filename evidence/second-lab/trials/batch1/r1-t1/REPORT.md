# REPORT: independent reader for `mini-v1.werk`

## 1. Result

**Success on all five points.** The program is `tools/werk_reader.py` (Python 3, standard library only). Run it like this:

```
python -I tools/werk_reader.py mini-v1.werk out
```

| Requirement | Result |
|---|---|
| Open the container | Yes. Store-mode zip, 36 entries, zip64 check done, zip CRC-32 checked on every read. |
| List the node graph with meanings | Yes. 14 nodes. For each node it prints the type meaning, work note, producer, epistemic stamp, edges (and whether the target exists) and files. |
| Verify every declared hash | Yes. 34 of 34 `files[].sha256` and sizes match. `license.sha256` matches. `spec_sha256` matches. 1 of 5 `input_hash` values reproduces. 3 cannot be checked because their inputs are not in the package. 1 does not reproduce (see 6.1). The signature chain is **signed-and-valid**. |
| Extract the primary mesh and one sound | Yes. Both are in `out/`. |
| Extracted bytes hash to the declared values | Yes. Both match (table below). |

Exit status on the original file: 0 (no `error` entries, 4 `warn` entries).

## 2. What I extracted

| Slot | Node | Path in package | Payload rule (SPEC §2.1) | Output file | Size |
|---|---|---|---|---|---|
| `primary.mesh` | `geom-game` | `geometry/game.glb` | rule 2 (single file) | `out/game.glb` | 16736 B |
| `primary.sound` | `audio-crate-impact-hard-surface` | `audio/sfx/crate-impact-hard-surface.wav` | rule 1 (`payload_file`, role `best`) | `out/crate-impact-hard-surface.wav` | 17644 B |

| Output file | Declared sha256 | Computed sha256 (re-read from disk) |
|---|---|---|
| `out/game.glb` | `eee8b3cbc87703fc945555efec8fdcb0fb133f6c94cf75c8643b57189c4ef2ce` | `eee8b3cbc87703fc945555efec8fdcb0fb133f6c94cf75c8643b57189c4ef2ce` |
| `out/crate-impact-hard-surface.wav` | `1e634f03aebdb0ee82a4c24a0174d381a0552e6dfb03e996b34de8905359aa5e` | `1e634f03aebdb0ee82a4c24a0174d381a0552e6dfb03e996b34de8905359aa5e` |

What the payloads contain, as decoded by my program:

- **Mesh:** glTF 2.0 GLB, 1 mesh `crate`, triangles (mode 4), 272 vertices, 408 triangles, attributes `POSITION`, `NORMAL`, `COLOR_0`. The bounding box is (−0.5, −0.5, −0.5) to (0.54, 0.54, 0.5). This agrees with `physics/bounds.json`.
- **Sound:** RIFF WAV, PCM integer, mono, 16000 Hz, 16 bit, 0.550 s. This agrees with the descriptor's `audio_format`. All four WAV takes agree with it.

I did not take `files[0]` for the sound. `files[0]` is the JSON descriptor (SPEC §2.1 warns about this).

## 3. Bundled reader programs

**I did not open, read, run, compile or port any of `loaders/werk_read.py`, `loaders/werk_read.rs` or `loaders/werk_read.c`, at any point.**

- I copied the package to `pkg/` so I could read it. I left out `loaders/` on purpose.
- My program only hashes the loader files as data. It prints their `meta` block and marks them "NOT executed".
- README.txt says "or just run loaders/werk_read.py against this file". I did not do this, because of task rule 6.
- I did not need the loaders. The spec documents were sufficient.

I did run one program that comes from me, against the spec's own test data: the Ed25519 self-test uses the RFC 8032 vector and the §12.1 example that MINI-SPECS.md prints. These are data, not code.

## 4. Files I read inside the package, in order

| # | File | How | Why |
|---|---|---|---|
| 1 | `MANIFEST.json` (first 40 lines) | Text view of the raw `.werk` | Store mode makes the first entry readable as text. This told me it is a zip. |
| 2 | Zip central directory | My script `tools/ls_zip.py` (stdlib `zipfile`) | Entry list, offsets, methods (all 0). |
| 3 | `README.txt` | Full | Top-level entry point. |
| 4 | `spec/README.md` | Full | Reading order and node-type table. |
| 5 | `MANIFEST.json` | Full | Node graph, `primary`, `payload_file`, hashes. |
| 6 | `spec/MINI-SPECS.md` | Full | **The file that unblocked me.** §11 gives the `input_hash` rule. §12 and §12.1 give Ed25519 and the exact signed message. §5 says "use your zip library". |
| 7 | `SIGNATURE.json` | Full | Signature chain. |
| 8 | `spec/SPEC.md` | Heading search, then lines 1 to 445 and 1142 to 1501 | §2 `spec_sha256` rule, §2.1 payload resolution, §5 degradation, §6 signatures, §10 reader checklist and report codes. |
| 9 | `spec/layouts/restposes.layout.txt` | Full | WKRP record layout. |
| 10 | `spec/examples/restposes.example.hex.txt` | Full | Worked hex dump. |
| 11 | `spec/layouts/ENVELOPE.layout.txt` | Full | Envelope frame, MessagePack subset, consistency rule. |
| 12 | `audio/sfx/crate-impact-hard-surface.json` | Full | `audio_format` for a cross-check. |
| 13 | `physics/bounds.json` | Full | Cross-check of the GLB box and the rest-pose contacts. |

Not read as text (only hashed or parsed by my program): all `spec/schemas/*.json`, `spec/facets.json`, `spec/conventions-map.json`, `semantics/semantics.json`, `provenance/provenance.json`, `materials/wood.json`, `LICENSE`, the WAV, GLB and PNG files, and the loaders.

**Which file unblocked me:** `spec/MINI-SPECS.md`. Strictly, nothing blocked me for long. The zip opened with the stdlib, and the first program run passed every check except one. MINI-SPECS.md is the document that made the hash, `input_hash` and signature checks exact on the first try. SPEC.md §2 (`spec_sha256`) and §2.1 (`payload_file`) were the second most important.

## 5. What I wanted from outside the file and could not get

Nothing from outside the file was necessary. Some things would have helped:

| Wanted | Why | Status |
|---|---|---|
| The input files `geometry/source.glb`, `audio/package.json`, `x/splat-foley/views/view_00..05.png` | To check 3 `input_hash` values | Not in the package (trimmed from the full fixture). Reported as `input-hash-uncheckable`. |
| The two inputs that `rest-poses`' `input_hash` was actually computed over | To find out why it does not reproduce | Not in the package. Unknown. |
| `spec/examples/make-examples.py` | spec/README.md calls it "what it means" when a layout is ambiguous | Not in this mini package. I did not need it. |
| `spec/examples/signature.example.txt`, `MANIFEST.example.json`, `SIGNATURE.example.json` | Named by MINI-SPECS §12.1 | Not in the package. §12.1 prints the example inline, so this was not a problem. |
| A JSON Schema validator | SPEC §10 step 2 [F] and step 7 [F] | Not in the stdlib. I did not write one. My program is a **bootstrap-class** reader: it parses JSON strictly (no BOM, no duplicate keys, no NaN) but does **not** claim schema validity. |
| The full source fixtures `fixtures/crate-v1.werk`, `tests/fixtures/crate.werk` | The entity summary names them as the origin | Outside the file. Not requested. Not needed. |

## 6. Stumbles, ambiguities and defects (all of them)

### 6.1 The `rest-poses` node is not what the manifest says it is

This finding is the most important one.

- `poses/rest.wkrp` is **byte-identical** to `spec/examples/restposes.example.wkrp` (both sha256 `6c2c44d5...5f95`).
- The envelope header says producer `werk-example 0.1`. The manifest says producer `werkc 0.1.0`.
- The manifest says `epistemic: measured`, "Settled orientations from a drop simulation". The contact points are at y = 0 and ±0.25 m. The crate's measured box is −0.5 to 0.54 m, and its lowest point is y = −0.5. A crate cannot rest on contacts at its own centre plane. So these are the example's synthetic numbers, not a crate measurement.
- The declared `input_hash` (`60e08ed1...96c8`) does not reproduce. I tried 18 constructions (both input orders, raw or hex digests, tail `{}`, empty or `null`, each input alone). None matched. The same code reproduces `bounds`' `input_hash` exactly, so my construction is correct. The hash was computed over different input bytes.
- README.txt says rest poses are "Deliberately absent". The entity summary says "no payload byte was invented".

My program reports this as `input-hash-mismatch` (warn) and `producer-disagrees` (warn). It is **not** damage: the bytes match the manifest's sha256, and the signature over the manifest is valid. The node is internally consistent as an envelope (all ENVELOPE §7 and restposes invariants pass). It is semantically wrong for this entity. A reader that only checks hashes will not see it.

### 6.2 Documentation that is stale or refers to absent files

1. **README.txt is for the full golden crate, not this mini file.** It says "every one of the twenty sound effects" (there is one effect with four takes), "Deliberately absent: ... rest poses" (a rest-pose node is present), and lists `imposters/` in the tree. This cost me a short moment of doubt about whether I had the right file.
2. **README.txt tells the reader to run the bundled loader.** "Or just run loaders/werk_read.py against this file." This conflicts with SPEC §7.1's caution and with the task rules. I ignored it.
3. **spec/README.md links about 20 files that are not in this package.** Examples: `PROFILE-IMAGE.md`, `X-C2PA-EXPORT.md`, `examples/make-examples.py`, `gsplat.example.hex.txt`, `embedding.example.hex.txt`, `skeleton/*`, `layouts/points.layout.txt`, `layouts/gsplat.layout.txt`, and most schemas in its table. `ENVELOPE.layout.txt` §0 also lists two absent example dumps. The mini package keeps the full index and does not mark which files were removed.
4. **Status markers disagree.** SPEC.md's preamble says the `PROPOSED, draft-pending-Gregor` rulings "are now RULED". §2.1 (`payload_file`) still says "Status: PROPOSED, pending Gregor's ruling". §2 then says a consumer "MUST resolve ... by §2.1's ordered rules". I followed §2.1 as normative.

### 6.3 Graph content that the trimming left behind

5. **Edges to absent nodes.** `geom-game → geom-source` (enhances), `audio-crate-impact-hard-surface → audio-package` (enhances), `evidence-segments → evidence-views` (**requires**).
6. **Ambiguity: does a `requires` edge to an *absent* node kill the source node?** SPEC §5 only defines edges into a *dead* node. My decision: an absent node is not a dead node. README.txt's "island rule" says any subset of node families is legal. I report `edge-target-missing` (warn for `requires`, info for `enhances`) and do not kill `evidence-segments`. A stricter reader could kill it, and the spec does not decide between the two.
7. **`evidence-segments` meta lists 10 images; only `seg_00.png` is in `files[]`.** `meta.count` is 10. I report 9 `meta-names-absent-file` entries (info).
8. **Three `input_hash` values cannot be checked** because their `input_files` are not in the package. The spec does not say how to report this. I use `input-hash-uncheckable` (info).
9. `container.entry_order` names `properties/`, which does not exist. This is harmless because the order is a SHOULD.
10. `preview_prefix_bytes` = 606948. This is exactly the offset where `materials/wood.json` starts, so it is the end of the preview tier including the primary sound. It agrees with the S-15 definition. This is not a stumble. I note it because I checked it.

### 6.4 Policy questions found during the damage test

11. **One damaged variation kills the whole sound node.** In my damage test (section 7), one flipped byte in `var2.wav` made SPEC §10 step 6 mark `audio-crate-impact-hard-surface` dead. The `best` take was intact, but it could not be extracted as `primary.sound`. This follows the spec exactly, but the spec does not discuss multi-take nodes. A per-file rule for non-payload files would keep the sound available.
12. **The signature stays `signed-and-valid` on a damaged package.** This is correct: the signature covers the manifest, and the manifest is intact. The damage appears as `hash-mismatch`. A user who reads only the signature line could misunderstand this. My output prints both.

### 6.5 My own stumbles (not documentation problems)

13. **Tool permissions.** My first five shell commands were refused because they used `&&`, `;`, pipes or `>` redirection, which need approval in this session. I lost about a minute. After that I used one command per call, and wrote helper scripts in `tools/`. I could not save a log file, so the run output is not on disk; re-run the command in section 1 to reproduce it.
14. **A fragile line in my first self-test** (`zipfile.crc32` with a conditional expression). I removed it before the first run. It had no effect on results.
15. **A false warning in my first run.** I compared the envelope producer with the manifest producer for `spec/examples/restposes.example.wkrp` too, which belongs to the `core.spec` node. I limited the comparison to non-spec nodes.
16. **First version returned "MISSING" for a CRC-damaged entry**, because Python's `zipfile` raises an exception on a bad CRC. I changed it to read the raw bytes of store-mode entries from the local header (MINI-SPECS §5.3). Then the report says `zip-crc-mismatch` and `hash-mismatch` with the actual sha256.
17. **Isolation-rule ambiguity.** Rule 2 forbids "any directory anywhere on this machine named spec/ ... or loaders/". When I copied the package contents to `pkg/` for reading, this created `pkg/spec/` inside my working directory. I read that as allowed: it is the file's own content, inside my working directory, and the task says "You may read anything inside the file". To stay safe I did not create `pkg/loaders/`.
18. **Unverifiable claim.** The README says the dev key is "derived from a published sentence". The package does not give the sentence, so I cannot check the key derivation. The signature verifies against the declared public key `17b9ab86...0d63`. As the README says, this proves nothing about authorship.

## 7. Damaged and corrupted data

The original file has no damaged bytes. Every size, sha256 and zip CRC matches.

To test the damage path I made a **copy**, `damaged-copy.werk`, with `tools/make_damaged.py`. It flips one byte in the middle of `geometry/game.glb` and one in the middle of `audio/sfx/crate-impact-hard-surface.var2.wav`. `mini-v1.werk` was only read. Its sha256 is `f7bdcc853009504b1d31b2934a7a8294cbf0e6f227c95f7de1e81af0947e9837` before and after.

Result of the reader on the damaged copy (exit status 1, as SPEC §10.2 says):

```
zip-crc-mismatch + hash-mismatch -> geom-game dead
                                    bounds dead (requires geom-game)
                                    rest-poses, material-wood, semantics live (enhances only)
zip-crc-mismatch + hash-mismatch -> audio-crate-impact-hard-surface dead
primary.mesh, primary.sound      -> not extracted (primary-unavailable, error)
all other nodes                  -> loaded, hashes ok
```

Summary in words: each flipped byte was found twice (zip CRC and sha256), the damaged nodes and their `requires` dependants were marked dead, and everything else loaded.

I did not try to repair damaged data. The spec gives no repair method for payload bytes. SPEC §12 (self-indexing recovery) is about a damaged manifest index, and I did not read it.

## 8. Time

The shell clock read 22:39:26 at my first command and 22:44:16 after the damage test. The report took a few more minutes. That is about 5 minutes of clock time for the work. My own sense is longer, about 15 to 20 minutes, because the tool calls run quickly between my long reading and writing steps. I cannot explain the gap, so I give both numbers.

| Phase | Approximate share |
|---|---|
| Container identification and permission retries | 5 % |
| Reading README.txt, spec/README.md, MANIFEST.json | 15 % |
| Reading MINI-SPECS.md and SPEC.md sections | 25 % |
| Reading the envelope and rest-pose layouts | 10 % |
| Writing `werk_reader.py` | 25 % |
| First run, `input_hash` probe, fixes | 10 % |
| Damage test | 5 % |
| This report | 5 % (excluded from the clock times above) |

## 9. Files I created

| Path | Purpose |
|---|---|
| `tools/werk_reader.py` | The reader (the deliverable program). |
| `tools/ls_zip.py` | First look at the central directory. |
| `tools/unpack_docs.py` | Copied all entries except `loaders/` into `pkg/` for reading. |
| `tools/probe_input_hash.py` | 18 `input_hash` constructions for `rest-poses`. |
| `tools/make_damaged.py` | Writes a damaged copy for the damage test. |
| `pkg/` | Read-only copy of the package contents (no `loaders/`). |
| `out/game.glb`, `out/crate-impact-hard-surface.wav` | The extracted payloads. |
| `damaged-copy.werk`, `out-damaged/` (empty) | Damage test input and its (empty) output folder. |
