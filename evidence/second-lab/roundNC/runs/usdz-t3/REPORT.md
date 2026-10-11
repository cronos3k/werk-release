# REPORT — crate-nc-v1.usdz

Program: `tools/inspect_usdz.py`, run as `python -I tools/inspect_usdz.py crate-nc-v1.usdz extracted`.
It uses only the Python standard library (`hashlib`, `struct`, `re`, `os`, `sys`).
Helper probes I used along the way: `tools/peek.py`, `tools/scan.py`, `tools/hexdump.py`.

## 1. Did it succeed?

Partial success. The core blocker is that **the package contains no documentation of any kind**: no spec, no README, no manifest, no declared sha256 values, and no reader program.

| Goal | Result |
|---|---|
| Open the container | **Yes.** I derived the layout from internal consistency, and 22/22 run-time cross-checks pass (details below). |
| List the contents with meanings | **Partly.** Both stored entries are listed with their meanings, and so are the six sections of the scene layer. **The scene's node graph (prim hierarchy) is not decoded.** Its PATHS, SPECS, FIELDS and TOKENS sections are compressed with a scheme the file does not document. I list only the readable fragments of the token text (e.g. `Cube_020`, `Mesh`, `points`, `Principled_BSDF`, `Image_Texture`, `wooden_c…_01_lid`, `_latch`, `_materials`), and I label them as partial, not a decoded graph. |
| Verify every declared hash | **No declared sha256 exists**, so there was nothing to verify against. The package contains no 32+ character hex strings at all, and no "manifest" or "sha" token is readable. The only integrity-looking values are two 4-byte fields per entry (`0x11304224` for the .usdc, `0x4bf30478` for the .png). The file does not say what algorithm produces them, so **I did not verify them** (see §5). |
| Extract the primary mesh | **Only as the containing scene layer**, `crate-nc-v1.usdc`, which holds mesh `Cube_020`. **Mesh geometry (points and indices) was NOT extracted**, because that needs the scene-layer format and its compression scheme. Neither is in the file. |
| Extract one texture | **Yes**: `textures/crate_diffuse.png`. |
| Do the extracted bytes hash to the declared values? | **Cannot be answered: no values are declared.** The computed hashes are below. Re-reading the written files gives the same hashes as the in-memory payload slices. |

## 2. What I extracted

| Output file | Source entry | Bytes | Declared sha256 | Computed sha256 |
|---|---|---|---|---|
| `extracted/crate-nc-v1.usdc` | `crate-nc-v1.usdc` (payload @64) | 478101 | none declared | `a7eed1afb71e2f47fc4ba94c6899e0ebc5b77bf240f78af4ae2d5c41530d3faa` |
| `extracted/textures_crate_diffuse.png` | `textures/crate_diffuse.png` (payload @478272) | 9460 | none declared | `af85a84d80b8fee7bf413a5edc2e722f4442df09a5d2d064d8b16dfb0a51ec1f` |

The container itself is 487957 bytes with sha256 `14cd873a32574a7fd30f9b3599b64ca128ff105ef992329a74794ecdedd806b7`. It was opened read-only and never modified.

## 3. Bundled reader programs

**None exists**, so I never opened, ran or ported one. The package holds exactly two entries (a binary scene layer and a PNG), and a scan for record markers found no hidden or orphan entries outside the trailing table.

## 4. What I read inside the package, in order

1. The container's first and last 256 bytes. These showed the entry names `crate-nc-v1.usdc` and `textures/crate_diffuse.png`, plus the trailing table.
2. A full-file scan for the 4-byte record markers and for printable strings of 8+ characters. This found 2 entries, 2 table records, 1 end record, and no text documentation anywhere.
3. A hexdump of bytes 475900–478400: the tail of the .usdc (token text, the section table naming TOKENS / STRINGS / FIELDS / FIELDSETS / PATHS / SPECS) and the PNG entry header.
4. Hexdumps of bytes 0–96 (the first entry header and the start of the .usdc) and 487700–EOF (the trailing table and end record).

**Nothing "unblocked" me**, because there was no documentation to find. What made the container work was **internal consistency**: every length or offset field I relied on equals a span I could observe directly. For example, 478101 = 478165 − 64, the table offset plus table size equals the end-record position, and the section-table count of 6 matches the six visible section names, which end exactly at the end of the layer. I kept a field only when it passed such a check. The program re-checks all of these at run time.

## 5. What I wanted from outside the file and could not get

1. **The container format spec.** It would tell me what the 4-byte "check32" field is and confirm the meanings of the version, flags/method and stamp fields. I inferred only the fields I could cross-check. "Stored verbatim" is inferred from the two size fields being equal and from the payloads starting with recognisable magic bytes, not from a documented method code.
2. **The checksum algorithm for the 4-byte check fields.** I have a prior-knowledge guess about what it is. The rules say recognising a format does not license using it, so I deliberately did not compute it. These values are therefore **unverified**.
3. **The binary scene-layer ("PXR-USDC") format spec.** I need it to decode the PATHS, SPECS and FIELDS sections into a node graph and to find the mesh's attribute arrays.
4. **The compression scheme used inside those sections.** The token text is visibly a mix of literal runs and back-references. I need it to decode the token list, the hierarchy and the indices.
5. **A declared-hash manifest.** The task assumes one exists, but this package has none. If a manifest was meant to be included, it is missing from this file.
6. (Optional) **The PNG spec**, to validate the texture's internal chunk checksums. I checked only that it starts with the PNG signature and ends with the `IEND` trailer bytes seen in the file.

## 6. Stumbles (honest list)

- **The task description does not match the file.** It refers to a manifest, declared hashes, a node graph "with meanings", and possibly a bundled reader. None of these exist here. I spent time scanning the whole package for documentation, hex digests and hidden entries before concluding they are absent. This was the main cost.
- **Tooling friction:** my first attempts used `cd … &&` chains and `python -c` inline code. The sandbox's permission checks blocked both, so I switched to script files in `tools/` run with `python -I`. This cost a couple of minutes.
- **Inferring rather than knowing:** some field meanings are inferred, not documented.
  - "64-byte alignment padding" for the extra field: both payloads start at multiples of 64 and the padding bytes are zero.
  - "stamp" for the bytes `4f 8c 47 5d` / `4e 8c 47 5d`: the two values differ by 1 between entries, which suggests a timestamp. I did not decode it.
  - The meaning of the `0x1986` two-byte tag at the start of each extra field is unknown.
  - The 8 bytes after `PXR-USDC` (`00 09 00 …`) are unknown, probably a version.
- **Line-reading the token table is lossy.** Fragments like `typeNamea`, `Mesha`, `qIndicesN` and `bdiffusI` are compression artefacts (literal runs cut by back-reference codes), not real names. I report them as fragments only.
- **I deliberately did not scrape float arrays** out of the .usdc to pass them off as "the mesh". Without the spec I cannot tell which run is points, which is normals and which is UVs, so any result would be a guess.

## 7. Damaged or corrupted data

I found no evidence of damage, and I did not attempt any repair.
- All 29 run-time checks pass (22 on the container, 6 on the section table, 1 on the PNG trailer): names match between entry headers and the table, header fields are byte-identical to the table copies, the spans tile the file with no gaps or overlaps, the end record reaches EOF exactly, and the section table tiles the .usdc exactly.
- The PNG ends with the expected trailer.
- The 4-byte check values were not verified (see §5), so silent corruption inside the payloads cannot be ruled out.

## 8. Wall-clock (rough)

- Start: about 16:28, from the working-directory timestamps.
- Initial probing, plus the time lost to tooling friction: about 1 minute.
- String and marker scans and hexdumps; concluding that no docs, manifest or reader exist: about 1 minute.
- Writing and running the program: about 1 minute (it finished at 16:30:30).
- Writing the report: about 2–3 minutes.
- Total: roughly 5–6 minutes. Most of the thinking went into deciding where derivation from the file ends and prior knowledge begins.
