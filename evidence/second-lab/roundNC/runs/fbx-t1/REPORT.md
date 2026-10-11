# REPORT — crate-nc-v1.fbx

Program: `fbx_extract.py` (run as `python -I fbx_extract.py crate-nc-v1.fbx extracted [--no-tree]`).
Exploration helpers I wrote are in `tools/` (`peek.py` hexdump, `strings.py`, `dump.py`, `pngchunks.py`). None of them came from the file.
Input sha256 (read-only, never modified): `ca28bbe959e14dc54ed40f29e1ce2f12530fc46f15976681e7bece9d626816ef`, 248,412 bytes.

## 1. Did it succeed?

| Requirement | Result |
|---|---|
| Open the container | **Yes.** The whole file parses as one tree: a 27-byte header, 11 top-level nodes, a null terminator, and a 162-byte footer. Every node's end offset and property-list length checks out, and the parse ends exactly at EOF. |
| List node graph with meanings | **Yes.** It prints the full node tree with a meaning for each node name, then the object graph from the `Connections` (child → parent). |
| Verify every declared hash | **Partly; the premise doesn't hold.** The file declares **no** hashes: there is no manifest and no sha256/md5 value anywhere. I searched the raw strings, every node and property, and the PNG chunks (there are no text chunks). The only checks the file carries are implicit, and all pass: 21 zlib adler32 trailers in compressed arrays, and 3 PNG chunk CRC32s. There are also three opaque 16-byte values (`FileId`, a footer id and a footer trailer) that can't be verified from inside the file. Altogether 43 structural and integrity checks ran, 0 failed. |
| Extract primary mesh | **Yes.** `extracted/wooden_crate_01.obj` |
| Extract one texture | **Yes.** `extracted/crate_diffuse.png`, the embedded bytes written verbatim (256×256 RGBA; I viewed it and it shows wood planks). |
| Extracted bytes match manifest-declared hashes? | **Can't be done: there is no manifest.** Computed hashes are below. Declared: none. |

## 2. What was extracted

| File | What | Declared sha256 | Computed sha256 |
|---|---|---|---|
| `extracted/wooden_crate_01.obj` | Primary mesh: model `wooden_crate_01` → geometry `Cube.020`, 3706 vertices, 5508 polygons (all triangles), 16,524 corners, per-corner UVs and normals. Converted to Wavefront OBJ in the geometry's local space. The model's transform (Lcl Rotation −90° X, Lcl Scaling 100) is recorded in a comment, **not applied**. | none in file | `838a683c8611f219ad2cc9be7f86683a9376380ae8433021e0660db13453b382` |
| `extracted/crate_diffuse.png` | Contents of the `Video "crate_diffuse.png"` node's `Content` field. The texture `base_color_texture` uses it, and it is wired to material `crate_wood`'s DiffuseColor. | none in file | `af85a84d80b8fee7bf413a5edc2e722f4442df09a5d2d064d8b16dfb0a51ec1f` |

`extracted/extracted.json` records the same data plus every check result.

**Why I picked this mesh as "primary":** there are three models: `wooden_crate_01`, `wooden_crate_01_lid` and `wooden_crate_01_latch`. I chose the one whose name has no part suffix. It is also by far the largest geometry (5508 polygons, against 692 and 376). The file itself doesn't mark any mesh as primary.

## 3. Bundled reader programs

**None exists, and I never opened, ran or ported one.** The file contains no executable or script content. The only blobs are numeric arrays and one PNG.

## 4. What I read inside the file, in order

The file is not a multi-file package, so there were no internal files. These are the regions I read, in order:

1. Bytes 0x000–0x400 (hexdump). This gave me the magic string, the version number (7400) and the node record layout.
2. A printable-strings scan of the whole file, looking for docs, a manifest or hashes. Found none, but it showed the embedded PNG and the external path `D:\build\crate-nc-v1.fbm\...`.
3. Hexdumps of 0x3A200–0x3A400 (the start of the PNG) and 0x3C900–EOF (the Connections, the end of the tree and the footer).
4. A full walk of the node tree (`tools/dump.py`), decompressing every array.
5. The chunks of the embedded PNG.

**What unblocked me:** step 4, the node tree itself. Once the record layout from step 1 parsed the whole file to EOF with every offset consistent, everything else followed. There was no documentation to unblock anything.

## 5. What I wanted from outside the file and couldn't get

- **A format specification.** The file contains no documentation: no rules, no glossary, no schema. Everything I used was inferred from byte patterns, from the self-describing node names, and (see §6) from prior knowledge.
- **The zlib/DEFLATE spec.** Arrays with encoding = 1 begin `78 DA`, and I can't derive DEFLATE from the file. I decoded them with Python's stdlib `zlib`. Nothing was fetched, but identifying the encoding as zlib was prior knowledge.
- **The PNG spec** (chunk layout and CRC32). Same situation: verified with stdlib `zlib.crc32` on the strength of prior knowledge.
- **How `FileId`, the footer id and the 16-byte trailer are computed**, which would be needed to verify them. Not in the file, so they remain unverified.
- **The manifest with declared sha256 values** that the task refers to. It doesn't exist in this file.
- **`D:\build\crate-nc-v1.fbm\crate_diffuse.png`**, the external path the file points to. I deliberately didn't look: it is outside my working directory, and the embedded copy made it unnecessary.

## 6. Stumbles (honest list)

1. **The task's description doesn't match the file.** It talks about a package with internal files, documentation, a manifest with declared hashes, and possibly a bundled reader. This file is a single ordinary binary 3D scene (the creator string says a Blender 4.2.1 exporter) with none of those. I spent part of the exploration phase searching for them: the strings scan, the PNG text-chunk check, and checking the 162 trailing bytes. The result is that "verify every declared hash" is vacuous, and "extracted bytes match the declared values" can't be answered.
2. **Constraint 4 couldn't be met in full, and I want to be explicit about where prior knowledge came in.**
   - I recognised the `Kaydara FBX Binary` magic immediately. Recognition shaped my first guesses at the record layout: a u32 end offset, u32 property count, u32 property-list length and u8 name length, with a 13-byte all-zero record as the terminator.
   - I then checked those guesses against the bytes. The first child's end offset 0x5C landed exactly on the next record, and the full walk reached EOF with every end offset and length consistent. So the layout is confirmed by the file, but it wasn't discovered from nothing.
   - The same goes for the property type codes (`I`, `D`, `L`, `S`, `R`, `C` and the lowercase array codes) and the array header (count, encoding, compressed length). They were guessed with prior knowledge and confirmed because each decoded array is exactly count × element size.
   - zlib and PNG can't be derived from the file at all.
   - Some semantics are prior knowledge only partly backed by data: "a negative index means ~v and closes the polygon", the `ByPolygonVertex`/`IndexToDirect` meanings, and rotations being in degrees. For the polygon rule, every value is in [0, n) or, after ~, in [0, n), and the last corner is always negative, which is consistent but not proof. All the "meanings" in the listing are my interpretation.
3. **Footer layout.** I modelled it as: 16-byte id, zero padding to a 16-byte boundary (6 bytes here), u32 version (7400, matching the header), 120 zero bytes, then a 16-byte trailer ending at EOF. That fits this file exactly. My memory of the format had a slightly different shape (I half-remembered an extra 4 zero bytes before the version), so I went with what the bytes showed.
4. **"Primary mesh" is ambiguous** (see §2). I chose by name and size, and the two criteria agree.
5. **The mesh has no byte-exact form inside the file.** It is stored as zlib-compressed arrays, so any "extracted mesh" is a conversion, and its hash depends on my choices of OBJ format and float formatting. Only the PNG is a verbatim extraction. I did not apply the model transform; OBJ consumers will see the crate rotated and scaled as stored.
6. **Small inconsistencies in the metadata (harmless):** `CreationTimeStamp` says 2026-10-06 03:06:39.604, while `CreationTime` and the `DateTime_GMT` fields say 1970. `DocumentUrl` is the placeholder `/foobar.fbx`. The `Path`/`FileName` fields point to an absolute `D:\build\...` path rather than to the embedded data.
7. **Tooling friction (cost a few minutes, not a format issue):**
   - The sandbox blocked shell pipes and `>` redirects, and PowerShell commands with relative paths. I worked around this with small helper scripts and absolute paths.
   - Full output from the program (38 KB, mostly the `P` property lines) was saved outside my working directory, which I'm not allowed to read. I added a `--no-tree` flag to see the summary instead.
   - The file viewer refused to show `.obj` as text, so I inspected it with my hexdump helper.

## 7. Damaged or corrupted data

None found: every structural, adler32 and CRC check passed. I attempted no repairs, and no copies were needed because the original was only ever opened for reading.

## 8. Wall-clock (my clock: started 15:50:24, done about 15:56)

- Orientation and header hexdump: about 1 minute.
- Strings scan and the search for docs or a manifest: about 1 minute.
- Full tree walk with the exploratory dumper: about 1 minute.
- PNG check, writing the final program and running it: about 2 minutes.
- Sanity checks (viewing the PNG, reading the start of the OBJ) and this report: about 1–2 minutes.
