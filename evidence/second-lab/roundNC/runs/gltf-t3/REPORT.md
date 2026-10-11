# REPORT — crate-nc-v1.gltf

## Summary: partial success

| Requirement | Result |
|---|---|
| Open the container | **Yes.** The .gltf is plain JSON; it references `crate-nc-v1.bin` (191040 bytes, matches the declared `byteLength`) and `crate_diffuse.png`. |
| List the node graph with meanings | **Yes, with caveats.** Scene → 3 nodes → 3 meshes → 1 material → 1 texture → 1 image. The meanings come from the English key names and from checks against the data. Some numeric codes could not be given a meaning (see below). |
| Verify every declared hash | **Not possible: the file declares no hashes.** There is no manifest, no `extras`, no sha256/digest/checksum field anywhere in the .gltf, and the .bin and .png contain no embedded text that could hold one. "Verify every declared hash" is vacuously true: there are zero. I computed sha256 of everything instead, and ran structural integrity checks. |
| Extract the primary mesh and one texture | **Yes.** Primary mesh = node 1 `wooden_crate_01` (mesh `Cube.020`). Texture = `crate_diffuse.png`. Choosing the "primary" mesh took a judgement call (see stumbles). |
| Do the extracted bytes hash to the declared values? | **Cannot be checked: nothing is declared to compare against.** |

Program: `crate_reader.py`. Run it as `python -I crate_reader.py <input dir> <out dir>`. Output goes to `out/`.
Helper: `tools/probe.py` (read-only hex/strings/sha256 probe of the three input files).

## What was extracted (`out/`)

| File | Declared sha256 | Computed sha256 |
|---|---|---|
| `wooden_crate_01.POSITION.raw` (bufferView 4, 44772 B, raw slice) | none | `483d874cf4231c9596ae3bee3783b6e4c23931460f1915b5234f7912d11bc241` |
| `wooden_crate_01.NORMAL.raw` (bufferView 5, 44772 B) | none | `40ab5b444be0a40e893e730d5cc00976a4d3d9c754c18159a5c12c5fbee3f1be` |
| `wooden_crate_01.TEXCOORD_0.raw` (bufferView 6, 29848 B) | none | `99229d659e6ecf6a7e67041c5d37a9aab2876b180d5322dd2efbe0d784c95cd9` |
| `wooden_crate_01.INDICES.raw` (bufferView 7, 33048 B) | none | `521568faf4fbb11a6d78ab0703773fc794cb7d5b5e2279e8ef691bb8bb673c35` |
| `wooden_crate_01.obj` (3731 vertices, 5508 triangles, converted by me) | none | `a0c13410e03cb631185c9422f9cc54c63b2581f8d7ac918c1d0812c9ed030a9e` |
| `crate_diffuse.png` (byte-for-byte copy) | none | `af85a84d80b8fee7bf413a5edc2e722f4442df09a5d2d064d8b16dfb0a51ec1f` |

Input hashes, for the record:
- `crate-nc-v1.gltf`: `3f9a6a472de5a08573b4fa1cf4c3de53fffa03ec2c3fdb5b8a2d89c5bb919f69` (not modified)
- `crate-nc-v1.bin`: `02148a5ba343d0d1eba4664be44416db5594c8a2147f61067c0ef5af010630ab`
- `crate_diffuse.png`: `af85a84d80b8fee7bf413a5edc2e722f4442df09a5d2d064d8b16dfb0a51ec1f`

## Node graph and meanings (as derived)

- `asset`: generator "Khronos glTF Blender I/O v4.2.60", version "2.0". These are informational strings only.
- `scene: 0` → scene `Scene`, root nodes [0, 1, 2]. No node has `children`, `matrix`, `translation`, `rotation` or `scale`, so the graph is flat. I **assumed** that a missing transform means identity placement. The file does not say so.
  - node 0 `wooden_crate_01_lid` → mesh 0 `Cube.005`: 622 vertices, 2076 indices (692 triangles if read as triples)
  - node 1 `wooden_crate_01` → mesh 1 `Cube.020`: 3731 vertices, 16524 indices (5508 triangles)
  - node 2 `wooden_crate_01_latch` → mesh 2 `Cube.001`: 384 vertices, 1128 indices (376 triangles)
- Each mesh has one primitive. It holds the attributes POSITION, NORMAL and TEXCOORD_0 plus `indices`, each pointing to an accessor, and uses material 0.
- material 0 `crate_wood`: doubleSided, base colour from texture 0, metallicFactor 0, roughnessFactor 0.5. These are read literally from the key names. Their rendering meaning is not defined in the file.
- texture 0 → image 0 (`crate_diffuse.png`, image/png) + sampler 0 (`magFilter 9729`, `minFilter 9987`). **The meaning of these sampler codes cannot be derived.**
- accessor → bufferView → buffer: `byteOffset`/`byteLength` select a slice of the .bin. The 12 views tile the buffer exactly (0..191040, no gaps or overlaps).

### Rules I derived from the data, not from a spec
- **`componentType` 5126**: bytes per component = byteLength / (count × components) = 4. Reading the data as **little-endian float32** reproduces every declared `min`/`max` exactly, for all three POSITION accessors. I take that as conclusive.
- **`componentType` 5123**: 2 bytes per component. Read as **little-endian unsigned 16-bit**, every index is below the vertex count of its primitive. **Signed vs unsigned cannot be distinguished** because all values are under 32768. My endianness loop accepts the first candidate that passes and tries LE first. I did not separately prove that BE fails for the indices. It almost certainly does, since byte-swapped values would exceed the vertex count.
- **`type`** VEC2/VEC3/SCALAR → 2/3/1 components. I took this from the names, and it is consistent with byteLength/count for every accessor.
- **`target`** 34962 is used only by attribute views and 34963 only by index views. That partition is the only "meaning" I can attach. The codes themselves are unexplained.
- **Indices form triangles**: an **assumption**. There is no `mode` key and nothing in the file says triangles. Supporting evidence: every index count is divisible by 3, and all NORMAL vectors are unit length, which fits per-vertex normals of a surface mesh.
- **UV origin**: not stated. When writing the OBJ I flipped V (v → 1−v). That is a convention I brought in myself, not something the file states. The `.raw` files are untouched.

## Integrity checks performed (no declared hashes exist)
- The buffer file length equals the declared `byteLength`.
- The bufferViews tile the buffer contiguously with no gaps, overlaps or overrun.
- For each accessor, byteLength is an exact multiple of count × components, and each code has a consistent component size.
- The decoded POSITION min/max equal the declared min/max exactly. This is the closest thing to a checksum the file has.
- Within each primitive, all attributes have the same count. Index count is divisible by 3, and every index is below the vertex count.
- All normals are unit length (tolerance 1e-3).
- The PNG's leading bytes spell "PNG", which matches its declared mimeType. I did **not** CRC-check or decode the PNG. That would need knowledge of the PNG format that this file does not supply.
- Result: **no structural problems found**.

## Did I open, run or port a reader bundled inside the file?
**No.** There is none. The package is the .gltf (JSON), a .bin of float/uint16 data, and a PNG. The PNG's only visible chunk tags are IHDR, IDAT and IEND. I found no code, script or documentation anywhere. Nothing that came out of the file was executed.

## Files read, in order
1. Directory listing of the working directory (shows PROMPT.txt, the three inputs, and two empty agent log files). I did not open PROMPT.txt; the task text was given to me directly.
2. `crate-nc-v1.gltf`: full read. **This is what unblocked me.** It is the only source of structure. Everything else was derived by testing hypotheses about its fields against the .bin.
3. `crate-nc-v1.bin` and `crate_diffuse.png`: hex head/tail and printable-string scans (via `tools/probe.py`) looking for embedded docs or hashes. None found.
4. Then the full read of `crate-nc-v1.bin` and `crate_diffuse.png` by `crate_reader.py`.

Nothing outside the working directory was read, listed or searched. No URLs were fetched.

## What I wanted from outside the file and could not get
- **A specification for the format.** It would give the authoritative meaning of `componentType` codes (5126, 5123), `target` codes (34962, 34963), sampler filter codes (9729, 9987), the default primitive topology (triangles?), default node transforms, UV origin convention, and how to interpret signedness. The file only names its format ("version 2.0", generator string) and contains no documentation. I did not consult one.
- **A manifest of declared hashes.** The task asks me to verify them, but the package contains none. I could not get the "expected" values for the extracted files.
- **The definition of "primary mesh".** Nothing in the file marks one.
- **PNG format rules** (chunk layout, CRC, zlib), to verify the texture internally. Not in the file. I limited myself to a byte-exact copy plus a sha256.

## Stumbles, honestly
1. **The expected manifest/hashes do not exist.** The task wording ("verify every declared hash", "values the manifest declares") made me expect a manifest. I spent a few minutes scanning all three files for one (JSON keys, printable strings in .bin/.png) before concluding there is none. This is the biggest gap: half of the success criteria cannot be met as worded.
2. **There is no documentation inside the file at all.** The constraint "derive every rule from the file itself" can only be met by inference. Key names are English and partly self-explanatory, but the numeric codes are opaque. I got around this for the component types by testing hypotheses against `min`/`max`. For `target` I could only infer which role each code plays. For sampler codes I got nothing.
3. **I recognise this format from prior knowledge.** I deliberately did not use remembered code tables. However, my *hypothesis space* (try float32, try LE/BE, assume triangle lists) was certainly guided by familiarity. A truly naive reader would have had to try more candidates. I can't fully separate "derived" from "guided by recognition", and I'm flagging that here.
4. **"Primary mesh" is ambiguous.** My heuristic is the node whose name is a prefix of all other node names (`wooden_crate_01` vs `_lid`, `_latch`). It is also the mesh with by far the most vertices, which my fallback rule would have picked too. Someone else could reasonably have meant "all three meshes merged", since together they form the crate, or "mesh 0" (the first one).
5. **Triangle topology and identity transforms are assumptions.** The evidence fits them, but the file never states them.
6. **Signedness of 5123 is undetermined**, and my endianness check for indices is weaker than the one for floats (first passing candidate wins).
7. **OBJ output conventions** (1-based indices, V flip) are my own additions. The flip in particular could be wrong. The raw slices are provided so nothing is lost.
8. Minor tooling friction: the sandbox rejected compound shell pipelines (`xxd | head`, etc.), so I wrote `tools/probe.py` instead. That cost about 1 minute.

## Damaged / corrupted data
None detected. Every structural check passed and the declared min/max were reproduced exactly. I attempted no repair.

## Wall-clock (rough self-estimate)
- Listing + reading the .gltf: ~1 min
- Probing .bin/.png for embedded docs/hashes: ~3 min (including the shell-pipeline detour)
- Writing `crate_reader.py` (derivation, listing, verification, extraction): ~8 min
- Running and checking output: ~1 min
- Writing this report: ~5 min
- Total: roughly 15–20 minutes.
