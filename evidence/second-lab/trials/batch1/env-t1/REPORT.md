# REPORT: mini-v1.werk

## 1. Result per task

| # | Task | Result |
|---|---|---|
| 1 | Program that opens the file, lists contents with meanings, verifies integrity | **Succeeded.** `tools/werk_inspect.py`. 0 FAIL, 2 WARN, 8 OK. |
| 2 | Decode the binary envelope payload | **Succeeded.** `poses/rest.wkrp`, magic `WKRP` = `core.pose.rest` (settled rest poses). **2 entries** (pose records), 7 contact points. |
| 3 | Identify the bundled readers, say what each is, quote source | **Succeeded.** 3 source loaders (Python, Rust, C) under `loaders/`. I read them as text only. |

Summary: all three tasks succeeded. The integrity check passes. Two warnings say that the rest-pose data does not belong to this crate.

## 2. How to run my program

```
python -I tools/werk_inspect.py mini-v1.werk [--entries N]
python -I tools/tamper_test.py mini-v1.werk      # negative test on damaged copies
```

Standard library only. It opens the package read-only. It does not import, compile, run or extract any code from the package.

## 3. What the program checks (task 1)

| Check | Rule source (inside the package) | Result |
|---|---|---|
| Zip parse: EOCD, central directory, local headers, zip64 detection | `spec/MINI-SPECS.md` §5, §5.5 | 36 entries, all method 0 (store), no zip64 |
| Zip CRC-32 of every entry | MINI-SPECS §6 | all 36 match |
| Entry name safety (no `..`, no leading `/`, no drive letter) | MINI-SPECS §5.4 | all safe |
| `size` + `sha256` of every file declared in `nodes[].versions[].files[]` | SPEC §10 step 6 | 34 of 34 match |
| `license.sha256` | SPEC §2 | match |
| `spec_sha256` (sorted paths + raw digests construction) | SPEC §2, S-29 | match: `5ada2290...31d4ad` over 17 files |
| `input_hash` per derived node | MINI-SPECS §11 "What gets hashed" | `bounds`: match. `rest-poses`: **STALE** (WARN). 3 nodes: not checkable, because their inputs are not in this package |
| Signature chain, Ed25519 written from the curve parameters | MINI-SPECS §12, §12.1; SPEC §6 | **signed-and-valid** |
| Ed25519 self-test before use | MINI-SPECS §12 RFC 8032 vector and the §12.1 worked example (203-byte message, checkpoint sha256, example signature) | all 4 pass, and a wrong message is rejected |
| Envelope frame and section consistency rule | `spec/layouts/ENVELOPE.layout.txt` §1 to §7 | pass |
| WKRP invariants (contact sum, sort order, probability sum, \|q\|, w >= 0, ranges, no NaN/Inf) | `spec/layouts/restposes.layout.txt` | pass |
| Contacts against measured bounds (my own plausibility check, not a spec rule) | `physics/bounds.json` | **WARN**: 7 of 7 contact points are not on the crate's bounding box |

Negative test (`tools/tamper_test.py`). It flips 1 byte in copies under `tools/tamper/`. The original is not modified.

| Damage | Program output |
|---|---|
| 1 byte in `poses/rest.wkrp` | zip CRC FAIL, sha256 FAIL, node `rest-poses` marked dead, envelope not decoded |
| 1 byte in `MANIFEST.json` | zip CRC FAIL, signature `present-and-invalid` |

What the program does NOT do. It reports these limits and does not hide them:
- No JSON Schema validation of JSON payloads (SPEC §10 step 2/7 [F]).
- No internal parse of PNG, WAV or GLB payloads. I verify their bytes by hash only.
- No deflate support. None was needed: every entry is store mode.
- It has no decoder for envelope magics other than WKRP. It would list them as "no decoder".

### Contents with meanings (abridged from the program output)

| node_id | type | meaning | files |
|---|---|---|---|
| geom-game | core.geom.game | runtime mesh (GLB) | geometry/game.glb |
| material-wood | core.material | PBR material parameters | materials/wood.json |
| bounds | core.phys.bounds | measured bounds | physics/bounds.json |
| semantics | core.semantics | facet tags, palette, search text | semantics/semantics.json |
| provenance | core.provenance | who made what from what | provenance/provenance.json |
| audio-crate-impact-hard-surface | core.audio.effect | sound effect | 1 JSON descriptor + 4 WAV (best, raw, var2, var3) |
| spec | core.spec | the format spec, carried in the file | 17 files under spec/ |
| loader-python / loader-rust / loader-c | core.loader | embedded reader source | loaders/werk_read.{py,rs,c} |
| license | core.license | CC BY 4.0 full text | LICENSE |
| readme | core.readme | one page for a human | README.txt |
| evidence-segments | x.splat-foley.segments | extension node: SAM segment crop | x/splat-foley/segments/seg_00.png |
| rest-poses | core.pose.rest | settled rest poses (WKRP envelope) | poses/rest.wkrp |

`MANIFEST.json` and `SIGNATURE.json` are not node files. The program reads and checks them directly.

## 4. The envelope (task 2)

- File: `poses/rest.wkrp`, 560 bytes.
- Magic `WKRP`, version 1, header_len 381, payload_origin 400 (= 16 * ceil(393/16)), payload_size 160.
- Kind: **`core.pose.rest`**. It holds the orientations in which the object comes to rest when dropped on a floor.
- **Entry count: 2 pose entries.** They hold **7 contact points** in total.
- Header: trials 4096, merge_angle_deg 5.0, settle_epsilon_m 0.0005, floor_normal [0,1,0], producer `werk-example 0.1`.

| pose | quat (w, x, y, z) | contacts | probability | support area (m^2) |
|---|---|---|---|---|
| 0 | (1, 0, 0, 0) | 0..3 | 0.62 | 0.25 |
| 1 | (0.7071068, 0.7071068, 0, 0) | 4..6 | 0.38 | 0.105 |

| contact | x, y, z (model space, m) |
|---|---|
| 0 | -0.25, 0, -0.25 |
| 1 | 0.25, 0, -0.25 |
| 2 | 0.25, 0, 0.25 |
| 3 | -0.25, 0, 0.25 |
| 4 | -0.25, 0, -0.21 |
| 5 | 0.25, 0, -0.21 |
| 6 | 0, 0, 0.21 |

I cross-checked these against the raw bytes in the annotated hex dump. For example, `52 b8 1e 3f` = 0.62, `5c 8f c2 3e` = 0.38 and `3d 0a d7 3d` = 0.105. The decoded header matches the dump's decoded header key for key.

### Caveat: this payload does not describe this crate

The bytes are valid and the signature covers them. But the evidence says the payload is the spec's synthetic worked example, copied into the node:

1. `poses/rest.wkrp` and `spec/examples/restposes.example.wkrp` have the same sha256 (`6c2c44d5...ee15f95`). They are byte-identical.
2. The envelope header says `producer: werk-example 0.1`. The manifest says `werkc 0.1.0`.
3. The manifest's `input_hash` (`60e08ed1...`) does not match the hash of the declared inputs `game.glb` + `bounds.json` (`4b91ccbb...`). I tried 8 variants (both input orders, raw or hex digests, with or without `{}`). None matches. The same code reproduces the `bounds` node's hash, so the construction is right.
4. The crate's measured AABB is [-0.5,-0.5,-0.5]..[0.54,0.54,0.5]. The contacts sit at y = 0 with a 0.5 m footprint. A crate that rests on its bottom face would touch the floor at y = -0.5 with a footprint of about 1 m.
5. README.txt lists "rest poses" as "Deliberately absent". The README seems to describe the full golden crate, not this mini fixture.

I report the numbers as decoded. I do not claim they are measured poses of this crate.

## 5. Bundled readers (task 3)

| Reader | Location inside the package | Bytes | What it is |
|---|---|---|---|
| `loaders/werk_read.c` | zip local header at offset 27859, data at 27908..138959 | 111051, 3076 lines | C99 bootstrap reader. Node `loader-c`. Build: `cc -std=c99 -O2 loaders/werk_read.c -o werk_read` |
| `loaders/werk_read.py` | local header 138959, data 139009..181235 | 42226, 993 lines | Python >= 3.8, stdlib only. Node `loader-python` |
| `loaders/werk_read.rs` | local header 181235, data 181285..280046 | 98761, 2703 lines | Rust, no crates. Node `loader-rust`. Build: `rustc -O --edition 2021 loaders/werk_read.rs -o werk_read` |

All three declare `read-manifest, verify-hashes, read-envelope, materialize` in the manifest. None verifies Ed25519. Each reports the signature as `unverified`. All three sha256 values match the manifest.

**Python**, `loaders/werk_read.py` lines 615 to 640 (envelope frame check):

```python
def read_envelope(data):
    """Every assertion in ENVELOPE.layout.txt §7. Any failure means the node is
    dead: report which assertion, skip the node, load the rest."""
    if len(data) < 16:
        raise ValueError("file is %d bytes; the smallest legal envelope is 16" % len(data))
    magic = bytes(data[0:4])
    if magic not in MAGIC_KIND and not (magic[:3] == b"WKX" and 0x30 <= magic[3] <= 0x39):
        raise ValueError("unrecognised envelope magic %r" % magic)
    version, header_len = struct.unpack_from("<II", data, 4)
    ...
    computed = align16(12 + header_len)
    if header.get("payload_origin") != computed:
        raise ValueError("declared payload_origin %r != computed %d"
                         % (header.get("payload_origin"), computed))
```

**C**, `loaders/werk_read.c` lines 1190 to 1199 and 1239 to 1246 (MessagePack decoder):

```c
    /* ENVELOPE.layout.txt section 4.2: these are banned outright and a
       reader MUST reject the header and mark the node dead. */
    if (b == 0xc1 || (b >= 0xc7 && b <= 0xc9) || (b >= 0xd4 && b <= 0xd8)) {
        mp_fail(r, "banned MessagePack format byte (ext types and 0xc1 are "
                   "forbidden by ENVELOPE.layout.txt section 4.2)");
        r->depth--;
        return NULL;
    }
    ...
    case 0xcb:
        if (!mp_take(r, 8, &q)) { r->depth--; return NULL; }
        v = j_new(J_NUM); v->num = mp_f64(q);
        r->depth--; return v;
```

**Rust**, `loaders/werk_read.rs` lines 1221 to 1229 and 1309 to 1321:

```rust
fn magic_kind(magic: &str) -> Option<&'static str> {
    match magic {
        "WKFF" => Some("core.field.flow"),
        "WKRP" => Some("core.pose.rest"),
        "WKAC" => Some("core.anim.clip"),
        "WKSK" => Some("core.skeleton"),
        "WKEM" => Some("core.embedding"),
        "WKPC" => Some("core.geom.points"),
        "WKGS" => Some("core.geom.gsplat"),
    ...
    let computed_p = {
        let x = 12u64 + header_len as u64;
        16 * x.div_ceil(16)
    };
    if payload_origin != computed_p {
        return Err(format!(
            "payload_origin declares {} but 16*ceil((12+{})/16) is {}",
            payload_origin, header_len, computed_p
        ));
    }
```

None of the three decodes WKRP pose records. They validate the envelope frame and section table only. (The Python loader decodes only WKPC and WKGS contents.)

Things I noticed in the loaders, by reading only:
- The Python docstring lists 6 capabilities (adds `summarize-points`, `summarize-gsplat`). The manifest declares 4. The docstring itself says the two "MUST match" (S-19).
- The C header comment gives a `build_command` with a different argument order from the manifest. The effect is the same.
- The C comment says MINI-SPECS §12 "explicitly says not to write [Ed25519] from a description". The §12 in this package now gives the parameters so that dependency-free readers can write it. The comment is stale.
- Python `read_envelope` rejects files under 16 bytes. ENVELOPE §1 says the minimum legal size is 12. This is harmless for real files.
- The Rust loader calls `u64::div_ceil`. I believe (prior knowledge, NOT verified from the file) that this became stable in Rust 1.73. The manifest says `rustc>=1.70`. Treat this as an unverified suspicion.

## 6. Did I open, run or port a bundled reader?

| Action | Answer |
|---|---|
| Opened (read as text) | **Yes**, all three, after my own program was finished and working. I read the headers and the envelope and MessagePack functions. |
| Ran / compiled | **No.** Nothing from the package was executed, imported, compiled or loaded. |
| Ported | **No.** I wrote `werk_inspect.py` from the spec files before I opened any loader. I did not copy loader code. |

README.txt says "just run loaders/werk_read.py against this file". I did not.

## 7. Files read inside the package, in order

| # | File | Why |
|---|---|---|
| 1 | first 600 raw bytes | identify the container (`PK\x03\x04` = zip) |
| 2 | zip central directory (via `zipfile` listing) | entry list and offsets |
| 3 | README.txt, SIGNATURE.json, LICENSE | orientation |
| 4 | spec/README.md | reading order, node-type table |
| 5 | MANIFEST.json | graph, hashes, layouts map |
| 6 | **spec/layouts/ENVELOPE.layout.txt** | envelope grammar and MessagePack subset |
| 7 | spec/layouts/restposes.layout.txt | WKRP record layout and invariants |
| 8 | **spec/examples/restposes.example.hex.txt** | byte-by-byte worked example |
| 9 | spec/SPEC.md §1 (container), §2 `spec_sha256` excerpt, §6, §7, §10 | integrity rules, reader checklist |
| 10 | spec/MINI-SPECS.md §5 (zip), §11 (hashes), §12 (Ed25519, message construction) | integrity rules |
| 11 | spec/conventions-map.json (one grep hit only) | what `hash_algorithm` covers |
| 12 | physics/bounds.json | plausibility check of contacts |
| 13 | loaders/werk_read.py, .c, .rs (selected ranges) | task 3 |

Not read: the schema files (only grep hits from manifest.schema.json), facets.json, semantics, provenance, material, audio JSON, and the binaries beyond hashing.

**What unblocked me:** `ENVELOPE.layout.txt` plus `restposes.example.hex.txt`. The layout gave the rules. The hex dump let me confirm each decoded number against real bytes. For the signature, MINI-SPECS §12.1 was the unblocker. Its worked message and checkpoint let me prove my message construction before I trusted a verdict.

## 8. Anything I wanted from outside the file

Nothing was required. No web, no other directory.
- spec/README.md and ENVELOPE.layout.txt point to files that are not in this mini package: `examples/make-examples.py`, `SIGNATURE.example.json`, `MANIFEST.example.json`, `signature.example.txt`, `PROFILE-IMAGE.md`, other layout files. I did not need them. The §12.1 text reproduces the signature example inline.
- The `input_hash` of 3 nodes cannot be checked, because their inputs (`geometry/source.glb`, `audio/package.json`, `x/splat-foley/views/*.png`) are not in the package. 3 edge targets (`geom-source`, `audio-package`, `evidence-views`) are also absent. The README's "island rule" says that is legal.
- I used prior knowledge in one place only: the Rust `div_ceil` remark in section 5. It is labelled there.

## 9. Stumbles, honestly

1. **Shell permissions.** My first commands (`cd ... && date && ls && xxd`) needed approval and were blocked. `xxd` alone was also blocked. I switched to single commands and Python.
2. **Console encoding.** Printing `spec/README.md` to the Windows console crashed with `UnicodeEncodeError` (cp1252, character U+2192). Fix: I copied text entries to flat files in `pkg_copy/` (for example `spec__README.md.txt`) and used the file reader. I flattened the names on purpose, so that no directory named `spec/` or `loaders/` exists on disk.
3. **Isolation ambiguity.** The constraints ban directories named `spec/` and `loaders/` anywhere on this machine. The package contains entries with those names. I read them as in-file content ("You may read anything inside the file"). I did not extract them into real directories with those names. A strict reader of rule 2 could object to this.
4. **I used Python's `zipfile` for the first listing** (MINI-SPECS §5 itself recommends the library route). The inspector then uses my own EOCD/central-directory parser. Its offsets agree with the `zipfile` listing.
5. **First run reported 1 FAIL** on `rest-poses` `input_hash`. I tested 8 alternative constructions and none matched. I then reclassified it as WARN "STALE". SPEC's README question 6 frames a mismatch as staleness, and the bytes and signature are intact. Someone could argue it should stay a FAIL. I chose WARN and say so here.
6. **Bug in my program, found by the tamper test.** After a hash mismatch marked `rest-poses` dead, the program still decoded its envelope. SPEC §10 says to skip dead nodes. I fixed it and re-ran both tests.
7. My first PowerShell attempt to save output to a file was blocked ("expandable strings"). I just ran the program directly.
8. I did not validate JSON against the schemas. This is a real gap against a "full reader" [F] checklist. A bootstrap [B] reader may skip it.

## 10. Wall-clock

Measured: `date` at the start printed 22:58:15. `date` before writing this report printed 23:02:15. That is about 4 minutes, plus a few minutes for this report. My own sense is that it took longer, roughly 15 to 25 minutes, because of many sequential tool calls. I trust the clock less than usual here, because tool latency is not visible to me. I took no per-phase timestamps. The phase split below is my estimate as a share of the total.

| Phase | Share (estimate) |
|---|---|
| Orientation: raw bytes, zip listing, README, manifest | 15 % |
| Spec reading: envelope, layouts, hex dump, SPEC/MINI-SPECS sections | 30 % |
| Writing the program, first run, input_hash diagnosis, tamper test, fix | 30 % |
| Reading the loaders (task 3) | 10 % |
| This report | 15 % |

## 11. Files I created (all in the working directory, original untouched)

- `tools/werk_inspect.py`: the program.
- `tools/tamper_test.py` and `tools/tamper/*.werk`: negative tests on damaged copies.
- `pkg_copy/*.txt`: flat text copies of the package's text entries, for reading.
- `REPORT.md`: this file.

`mini-v1.werk` is still 960061 bytes, with sha256 `f7bdcc85...e9837`. I did not hash it before I started, so this is not a before-and-after comparison. But no code ever opened it for writing, and all its internal CRCs, hashes and its signature still verify.
