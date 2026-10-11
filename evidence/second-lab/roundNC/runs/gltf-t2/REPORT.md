# REPORT — crate-nc-v1.gltf

## Outcome

| Requirement | Result |
|---|---|
| Open the container | **Yes.** The manifest is UTF-8 JSON; it references `crate-nc-v1.bin` and `crate_diffuse.png`, and both loaded. |
| List the node graph with meanings | **Yes.** 1 scene → 3 nodes → 3 meshes (1 triangle primitive each) → 1 material → 1 texture → 1 image plus 1 sampler. There are 12 accessors, 12 bufferViews and 1 buffer. The full listing is in `out/run_log.txt`. |
| Verify every declared hash | **Nothing to verify.** The manifest declares **zero** hashes, checksums or digests. My program walks every key looking for `hash`/`sha`/`digest`/`crc`/`checksum` and finds none. The `.bin` and `.png` don't contain any either (details below). So this requirement is met only in the empty sense. Instead I computed sha256 for every file and ran the structural checks listed below. All of them passed. |
| Extract the primary mesh and one texture | **Yes.** |
| Do the extracted bytes match the manifest's declared hashes? | **Can't be answered: the manifest declares no hashes.** The texture I extracted is byte-identical to the packaged image (same sha256). |

So I opened, listed, checked and extracted everything. I could not do hash verification because there were no declared hashes to check against. I did not invent any.

## Program

- `tools/crate_reader.py` — run as `python -I tools/crate_reader.py <package_dir> <out_dir>`.
  - It lists the contents, runs the checks, extracts the files and writes `out/run_log.txt`.
  - It exits non-zero if any check fails.
- `tools/probe.py` — my first look at the files: sizes, sha256, strings embedded in the `.bin` and `.png`, and the head and tail bytes.

## Extracted files (in `out/`)

| File | What it is | Declared sha256 | Computed sha256 |
|---|---|---|---|
| `primary_mesh_wooden_crate_01.bin` | Raw bytes [24056, 176496) of `crate-nc-v1.bin`: bufferViews 4–7, which hold mesh[1]'s POSITION, NORMAL, TEXCOORD_0 and indices (152440 bytes) | none declared | `f3d98f3d9c6b830577a79792b52abcf220ab310d4da789069b3cdf772ee50889` |
| `primary_mesh_wooden_crate_01.obj` | The same mesh decoded to text OBJ: 3731 vertices, 5508 triangles, normals and UVs, V not flipped (860249 bytes) | none declared | `1a76387f9c35bf7a069351c701253f806f031bd6d5a08157f8fb5aaf269c2002` |
| `crate_diffuse.png` | The base-color texture of material `crate_wood`, copied unchanged (9460 bytes) | none declared | `af85a84d80b8fee7bf413a5edc2e722f4442df09a5d2d064d8b16dfb0a51ec1f` (same as the source file) |

sha256 of the package inputs, for the record:

- `crate-nc-v1.gltf` `3f9a6a472de5a08573b4fa1cf4c3de53fffa03ec2c3fdb5b8a2d89c5bb919f69`
- `crate-nc-v1.bin` `02148a5ba343d0d1eba4664be44416db5594c8a2147f61067c0ef5af010630ab`
- `crate_diffuse.png` `af85a84d80b8fee7bf413a5edc2e722f4442df09a5d2d064d8b16dfb0a51ec1f`

The manifest was not modified; nothing was written into the package files.

## Integrity checks performed (all PASS)

- **Buffer size:** the `.bin` file is 191040 bytes, which matches the declared `byteLength`.
- **bufferView layout:** all 12 bufferViews:
  - fall inside the buffer;
  - don't overlap;
  - tile the buffer exactly from 0 to 191040 with no gaps.
- **Accessor sizes:** for every accessor, `count` × the bytes per element equals the length of its bufferView.
- **Positions:** for each POSITION accessor, the min and max I decoded equal the declared `min`/`max` exactly, after rounding the declared values to float32.
- **Normals:** every NORMAL vector has unit length (worst deviation is about 1.2e-7).
- **Texture coordinates:** all TEXCOORD_0 values are finite and lie within about [0.005, 0.995].
- **Indices:**
  - each index count is divisible by 3;
  - the largest index is below the vertex count;
  - every vertex is referenced;
  - there are no degenerate triangles.
- **`target` codes:** they are consistent with how each accessor is used (attribute vs. index).
- **PNG chunks:** the PNG has only three chunks — IHDR, IDAT (length 0x24BB) and IEND. Their sizes add up exactly to the file size, so nothing is hidden after IEND. Its magic bytes contain "PNG", which matches `mimeType`. The image is 256×256 and shows wood planks when viewed.

I did **not** check the PNG's internal CRCs or decompress the IDAT data. The package doesn't describe the PNG format, and the image viewer opening it was enough of a sanity check.

## Node graph with meanings

- `asset`: generator "Khronos glTF Blender I/O v4.2.60", version "2.0". These are the producing tool and a format version.
- `scene` 0, named "Scene", is the root. Its nodes:
  - node[0] `wooden_crate_01_lid` → mesh[0] `Cube.005`: 622 vertices, 692 triangles.
  - node[1] `wooden_crate_01` → mesh[1] `Cube.020`: 3731 vertices, 5508 triangles. **I chose this as the primary mesh.**
  - node[2] `wooden_crate_01_latch` → mesh[2] `Cube.001`: 384 vertices, 376 triangles.
  - No node has a transform or children, so all are placed at the identity position.
- **Primitives:** each mesh has one primitive, with POSITION (VEC3), NORMAL (VEC3), TEXCOORD_0 (VEC2), indices (SCALAR) and material 0.
- **Material:** material[0] `crate_wood` is double-sided, metallic 0, roughness 0.5, and its base color comes from texture[0].
- **Texture:** texture[0] = image[0] (`crate_diffuse.png`, image/png) + sampler[0], which has magFilter 9729 and minFilter 9987.
- **Buffer:** buffer[0] is `crate-nc-v1.bin` (191040 bytes). It is split into 12 bufferViews, read through 12 accessors.

## Did I open, run or port a reader program bundled inside the file?

**No.** The package contains no reader program, no script and no documentation of any kind:

- The `.gltf` is pure data.
- The `.bin` has no readable text (only coincidental ASCII inside float data).
- The `.png` has no text chunks.

I ran nothing that came out of the file.

## Files read, in order

1. `crate-nc-v1.gltf`, read whole as text. This **unblocked everything**. It is the only source of structure, and it is self-describing enough (key names, `type` strings, counts, byte lengths, min/max) that the remaining rules could be inferred and checked.
2. `crate-nc-v1.bin` and `crate_diffuse.png`, via `tools/probe.py`: hashes, a string scan, and the head and tail bytes. I was looking for an embedded manifest, hashes or documentation, and found none.
3. All three again, via `tools/crate_reader.py`.
4. `out/crate_diffuse.png`, viewed as an image to sanity-check it.

I did not read `PROMPT.txt` or anything outside the working directory. I used no web access.

## What I wanted from outside the file and could not get

- **Declared hashes.** The task assumes the manifest declares some; it doesn't. I would need a sidecar manifest or a spec saying where hashes live.
- **A definition of the numeric codes.**
  - `componentType` 5126 and 5123: I inferred these as float32 LE and uint16 LE, and the checks above confirm that empirically.
  - `target` 34962 and 34963: I inferred these from usage only.
  - Sampler `magFilter` 9729 and `minFilter` 9987: **these could not be derived at all** and are reported as opaque.
- **Primitive topology.** There is no `mode` field. I treated index triples as triangles because the counts are divisible by 3 and no triangle is degenerate. That is consistent, but it is not stated anywhere.
- **Conventions:** the coordinate system and handedness, the units (the bounding box of about 0.8 × 0.32 × 0.41 suggests metres), the UV origin (whether V should be flipped), and the byte order. I couldn't get any of these from the file. Byte order was settled by the min/max match.
- **The PNG format itself**, for CRC or IDAT validation. I didn't validate those.
- **What "primary mesh" means.** Nothing marks a mesh as primary.

## Stumbles, ambiguities and time lost

1. **No hashes anywhere.** The task's central check ("verify every declared hash", "do the extracted bytes hash to the declared values") has nothing to work with. I spent time scanning the `.bin` and `.png` for a hidden manifest before concluding there is none. This is the biggest gap between the task and the package.
2. **"Primary mesh" is undefined.** I used two heuristics:
   - the node whose bare name prefixes the others (`wooden_crate_01` vs. `_lid` and `_latch`);
   - the mesh with the most vertices.

   Both pick mesh[1]. A reader could reasonably argue for "all three meshes as one crate" or "mesh[0] because it is first".
3. **Mesh names don't match node names.** The node is `wooden_crate_01` but its mesh is `Cube.020`. I picked by node name.
4. **The magic numbers are undocumented** (see the previous section). Two hypotheses were confirmed by data. The sampler codes stay unexplained.
5. **No output format was specified for "the mesh".** I emitted two:
   - the raw byte slice, which is exact and hashable;
   - an OBJ, which is readable but whose sha256 depends on my float formatting (Python `repr`), so it isn't canonical.

   OBJ comes from my own prior knowledge; it is an output choice, not something read from the package.
6. **The UV V-direction is unknown.** I wrote UVs as-is. They could be upside-down in some viewers.
7. **Tooling friction, not the package:** the sandbox rejected inline `python -c` and a `; echo $?` chain. I moved the code into script files, which cost a couple of minutes.

## Damaged or corrupted data

I found none, and attempted no repair. Every structural and numeric consistency check passed.

## Wall-clock sense

| Phase | Time |
|---|---|
| Reading the manifest and probing the `.bin`/`.png` for embedded docs or hashes | ~3 min |
| Writing the reader and checks | ~6 min |
| Running it, viewing the texture, writing this report | ~5 min |
| **Total** | **≈15 min** |
