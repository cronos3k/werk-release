# REPORT — crate-nc-v1.gltf

Program: `tools/crate_reader.py` (run: `python -I tools/crate_reader.py <pkg_dir> <out_dir>`).
Helper probe used once before it: `tools/probe.py`.
Output: `extracted/`.

## 1. Did it succeed?

| Requirement | Result |
|---|---|
| Open the container | **Yes.** The `.gltf` is plain JSON that parses cleanly. Its single buffer `crate-nc-v1.bin` and its image `crate_diffuse.png` both load. |
| List the node graph with meanings | **Yes, partly.** I listed the scene, nodes, meshes, primitives, material, texture, image, sampler, buffer, bufferViews and accessors. Meanings come from key names and from empirical inference. Some numeric codes (sampler filters, bufferView `target`) have **no meaning stated in the file**; I report only what I observed about them (§6). |
| Verify every declared hash | **Vacuously yes: there are none.** The program searches the JSON for any key containing hash/sha/digest/checksum/crc/md5 and finds 0. The PNG has no text chunks and the .bin has no embedded text. There is no manifest. **0 of 0 declared hashes verified.** The task's premise of "the values the manifest declares" does not hold for this package. |
| Extract the primary mesh and one texture | **Yes.** The mesh is `mesh[1] "Cube.020"`, used by node `wooden_crate_01`: 3731 vertices and 5508 triangles. The texture is `crate_diffuse.png`, the material's base colour texture. |
| Do the extracted bytes match declared hashes? | **Cannot be answered: nothing is declared.** I give the computed sha256 values below. The texture copy is byte-identical to the source file. |

Structural integrity checks the program does pass (0 failures):
- The buffer file size equals the declared `byteLength` (191040).
- All 12 bufferViews lie inside the buffer and tile it exactly, with no gaps or overlaps.
- For every accessor, `byteLength` is divisible by count × components.
- The decoded POSITION min/max equal the declared min/max for all 3 meshes.
- All NORMAL vectors are unit length.
- TEXCOORD values lie within [0,1].
- Every index is less than its mesh's vertex count.
- Every index count is divisible by 3.

## 2. What was extracted

| File | Bytes | Declared sha256 | Computed sha256 |
|---|---|---|---|
| `extracted/primary_mesh.obj` (positions, UVs, normals, faces; my conversion) | 644404 | none | `dfb015e22c787af0e56502df7df9758e4a74a0bf3dd3c85256b0d54ca0a851e0` |
| `extracted/primary_mesh_POSITION.raw` (bufferView 4, byte-exact) | 44772 | none | `483d874cf4231c9596ae3bee3783b6e4c23931460f1915b5234f7912d11bc241` |
| `extracted/primary_mesh_NORMAL.raw` (bufferView 5) | 44772 | none | `40ab5b444be0a40e893e730d5cc00976a4d3d9c754c18159a5c12c5fbee3f1be` |
| `extracted/primary_mesh_TEXCOORD_0.raw` (bufferView 6) | 29848 | none | `99229d659e6ecf6a7e67041c5d37a9aab2876b180d5322dd2efbe0d784c95cd9` |
| `extracted/primary_mesh_indices.raw` (bufferView 7) | 33048 | none | `521568faf4fbb11a6d78ab0703773fc794cb7d5b5e2279e8ef691bb8bb673c35` |
| `extracted/crate_diffuse.png` (byte copy) | 9460 | none | `af85a84d80b8fee7bf413a5edc2e722f4442df09a5d2d064d8b16dfb0a51ec1f` |

Input hashes for reference: `crate-nc-v1.gltf` = `3f9a6a47…919f69`, `crate-nc-v1.bin` = `02148a5b…0630ab`.

## 3. Bundled reader programs

**None exists, so none was opened, run or ported.** The package contains no code, no docs and no spec text of any kind. The program in `tools/` is entirely my own.

## 4. Files read, in order

1. `crate-nc-v1.gltf`: read in full as text. This is the file that unblocked me, because all the structure is here.
2. `crate_diffuse.png`: parsed into chunks by `probe.py`, looking for embedded text or hashes. There were none.
3. `crate-nc-v1.bin`: hashed and scanned for printable strings. There was nothing meaningful.

I also listed my working directory, which contains `PROMPT.txt`. I did not open `PROMPT.txt` because the task text was given to me directly. Nothing outside the working directory was touched.

## 5. What I wanted from outside the file and could not get

- **A specification of this format.** The file names itself (`asset.version "2.0"`, generator "Khronos glTF Blender I/O"), but it explains nothing.
- **The meaning of the `componentType` codes 5126 and 5123.** I inferred them empirically (§6).
- **The meaning of the bufferView `target` codes 34962 and 34963.** Only a correlation was observed.
- **The meaning of the sampler codes `magFilter` 9729 and `minFilter` 9987.** These are unexplained, so the program lists them raw.
- **The primitive topology when `mode` is absent.** I assumed a triangle list, supported only by every index count being divisible by 3.
- **The UV origin convention**, i.e. whether V needs flipping when converting to OBJ. Not stated, so the OBJ writes UVs as stored.
- **Whether 5123 is signed or unsigned.** The data can't decide this: every index is below 32768, so int16 and uint16 decode identically.
- **A definition of "primary mesh".**
- **Declared hashes / a manifest.** The task assumes these exist; they don't.
- **The PNG format definition**, if the texture were to be verified internally (see stumble 3).

## 6. Stumbles (honest list)

1. **The task's premises do not match the package.** The task talks about a manifest, declared hashes and possibly a bundled reader. The package has none of them, and no documentation at all. I spent time confirming the absence: a JSON key search, a PNG chunk scan and a .bin string scan. "Verify every declared hash" is therefore vacuous, and I am reporting it as such rather than claiming a pass.
2. **No documentation inside the file.** Every "meaning" I give is derived in one of three ways:
   - **From key names:** `POSITION`, `NORMAL`, `TEXCOORD_0`, `indices`, `baseColorTexture`, `byteOffset`, and so on.
   - **By arithmetic:** `byteLength / (count × components)` gives 4 bytes for 5126 and 2 bytes for 5123. The component counts per type come from the names `VEC3`/`VEC2`/`SCALAR`, and the arithmetic confirms them.
   - **By testing hypotheses against the file's own data:**
     - 5126 = little-endian float32 is the only candidate whose decoded data reproduces the declared min/max exactly. Big-endian gives non-finite values; int32 and uint32 give a min/max mismatch.
     - 5123 = little-endian 16-bit, since the big-endian reading puts indices out of range. Signedness stays unresolved.
   
   The *candidate list* (float32, int32, uint16, endianness and so on) comes from general computing knowledge, not from the file. Only the selection among candidates is derived from the file.
3. **Prior-knowledge leak (I am disclosing it).** In `probe.py` I walked the PNG chunk layout: an 8-byte signature, then length + type + data + CRC per chunk. That layout came from my prior knowledge of PNG, not from anything in the package. I used it only to *look for* embedded docs or hashes, not to validate or decode the texture. To stay within the rules, the final program does **not** check PNG CRCs or decode the image. It treats the texture as opaque bytes and copies them. As a result, the texture's internal integrity is **unverified**.
4. **Prior knowledge was also recognition-level in general.** I recognised the format as glTF 2.0 from the asset block. I deliberately did not rely on spec facts I "know", such as what 9729 means or the default topology. Where I had to make an assumption (triangle list, identity transforms when no transform keys are present), it is labelled as an assumption in the program output.
5. **"Primary mesh" is ambiguous.** I chose the mesh with the most triangles (5508 vs 692 and 376). It is also the node with the unsuffixed name `wooden_crate_01`, while the others are `_lid` and `_latch`. Someone else might pick the first node (`mesh[0]`, the lid).
6. **OBJ output is my own choice of format**, written from general knowledge. It is not a file-derived rule. Because the OBJ's bytes depend on my float formatting, I also wrote byte-exact `.raw` slices of the source bufferViews, so the extraction can be checked against the original buffer.
7. **Tooling friction, about 1 minute.** The sandbox rejected inline `python -c`, `cd` combined with relative paths, and the PowerShell invocation. I had to put the scripts in a file and call them with absolute paths from Bash.

## 7. Damaged or corrupted data

None detected: every structural and consistency check passed. No repair was attempted or needed. Integrity here means internal consistency (sizes, ranges, min/max, unit normals), **not** cryptographic verification, because nothing is declared to verify against.

## 8. Wall-clock (approximate)

- Reading the .gltf and probing the PNG and .bin: about 1 minute, including the permission-error detours.
- Writing the reader program: about 1 minute.
- Running and verifying: under 1 minute.
- Writing this report: about 2 minutes.

Total: roughly 5 minutes (15:54 to about 16:00 local).
