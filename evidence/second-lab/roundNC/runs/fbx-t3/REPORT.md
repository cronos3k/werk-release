# REPORT — crate-nc-v1.fbx

## Outcome

| Requirement | Result |
|---|---|
| Open the container | **Yes.** The whole file parses as one tree to a top-level terminator at 0x3c9ad. Every declared end offset and property length matches exactly, with nothing left over. |
| List the node graph with meanings | **Yes.** All nodes are printed with offsets, values and a one-line meaning, followed by the object graph resolved from `Connections` (child → parent). |
| Verify every declared hash | **Nothing to verify.** The file declares **no** hashes: there is no manifest, no sha256/md5 field, and no checksum list anywhere. I verified every integrity mechanism the file does carry (below). |
| Extract the primary mesh | **Yes.** `extracted/wooden_crate_01.obj` (Cube.020::Geometry: 3706 vertices, 5508 triangles, 16524 corners). |
| Extract one texture | **Yes.** `extracted/crate_diffuse.png` (256×256 RGBA, 8-bit). I viewed it: it is a wood-plank texture. |
| Extracted bytes hash to manifest values? | **Cannot be answered: there is no manifest and there are no declared values.** I computed the hashes myself, below. The PNG is a byte-exact copy of the embedded `Content` blob, and its own CRC-32 values all pass. |

The task text talks about a manifest, a package of files, documentation, and a bundled reader program. **None of these exist in this file.** It is a plain Blender-exported binary FBX (`Creator: Blender (stable FBX IO) - 4.2.1 LTS - 5.12.4`). Its only embedded payload is one PNG. I'm assuming the "nc" in the file name means a no-container / control variant, but that is my inference.

## The program

`tools/fbxpkg.py` uses only the Python standard library. Run it as:

`python -I tools/fbxpkg.py crate-nc-v1.fbx extracted`

It lists the node graph with meanings, runs 67 integrity checks (all pass, exit code 0), and writes its outputs to `extracted/`. Helper scripts I used while exploring: `tools/hexdump.py`, `tools/strings.py`, `tools/dump.py` and `tools/probe.py`.

### Integrity checks performed (67, all PASS)
- **Structure:** every node's end offset and property-byte length matches; the tree closes with a top-level terminator.
- **Compressed arrays:** all 21 compressed arrays across the 3 geometries inflate cleanly. zlib checks each stream's built-in **Adler-32**. Each decompressed size equals count × element size.
- **Cross-references:**
  - every `Connections` endpoint exists;
  - the per-type counts in `Definitions` match the number of objects of that type;
  - the header `FBXVersion` equals the version at offset 23 and the copy in the trailer.
- **Mesh consistency, for all 3 geometries:**
  - vertex, normal and UV arrays split evenly into 3- or 2-component tuples;
  - every polygon is closed;
  - all vertex, normal, UV and edge indices are in range;
  - the per-corner index arrays have the same length as the corner list.
- **Embedded PNG:** signature, chunk **CRC-32** for IHDR/IDAT/IEND, no trailing bytes, and the IDAT data inflates to exactly height × (1 + width × 4) bytes.

### What I could not verify
- **Two 16-byte trailer values** (`fabcab09…267e` straight after the terminator, `f85a8c6a…290b` at end of file) and the 16-byte `FileId` (`28b32aeb…fcf1`). Nothing in the file says what they mean. I tested md5/sha1/sha256 of several byte ranges against them and none matched. I treat them as opaque and **unverified**.

## Extracted files

| File | Size | sha256 (computed) | Declared sha256 |
|---|---|---|---|
| `extracted/wooden_crate_01.obj` | 861,591 B | `2cd3e0284fca6706ccd425eff8b38709ce55c6071765a4f8c0177dc47c6b6690` | none in file |
| `extracted/crate_diffuse.png` | 9,460 B | `af85a84d80b8fee7bf413a5edc2e722f4442df09a5d2d064d8b16dfb0a51ec1f` | none in file |
| `extracted/wooden_crate_01.vertices.f64le` (raw vertex array, little-endian float64) | 88,944 B | `248680133659898f248f8f19a241f080a1b6faa05aa9acc7e11367b071f2adbc` | none in file |
| `extracted/crate_wood.mtl` (written by me, links the OBJ to the PNG) | 58 B | `9414da65d763d1be03a2b4fb3fbaeddc4369cfdad9f77047b01cc583dd74b107` | n/a |

- The PNG's sha256 equals the sha256 of the `Video/Content` bytes inside the FBX, so the extraction is byte-exact.
- The OBJ is my own conversion, so it has no "true" hash to compare against. Its coordinates are the raw geometry-local values. The model's `Lcl Rotation (-90,0,0)` and `Lcl Scaling (100,100,100)` are **not** applied, and the OBJ header comment says so.

**How I picked the primary mesh.** Nothing in the file declares a "primary" mesh. I chose Cube.020, which is attached to model `wooden_crate_01`, because two heuristics agree:
1. It is the only model without a `_lid` or `_latch` suffix.
2. It is by far the largest mesh: 3706 vertices, against 596 and 384 for the other two.

The program asserts that both heuristics pick the same mesh.

## Reader programs bundled in the file

**None exist, so I opened, ran and ported none.** The only embedded blob is the PNG. I wrote the parser from scratch, and never executed anything that came out of the file.

## Files inside the package I read, in order

There is no package, just one FBX stream. In the order I read its parts:
1. The 23-byte magic and the u32 version.
2. `FBXHeaderExtension` and its children, from a raw hexdump.
3. A whole-file printable-strings scan, looking for manifest/README/spec/hash/reader. **Nothing found.**
4. The full node tree via `tools/dump.py`.
5. The `Video/Content` blob (PNG).
6. The 162-byte trailer.

**What unblocked me:** the first hexdump of the header. It showed a regular length-prefixed record layout (`u32 end, u32 nprops, u32 proplen, u8 namelen, name, props`) that I could check against the bytes. Once the full-tree parse closed exactly on every declared offset, I knew the layout was right.

## Things I wanted from outside the file and could not get

- **A specification for the container.** Without one, these points can only be checked indirectly:
  - **Property type letters.** The scalar types (`Y C I F D L`), strings and raw blobs (`S R`), and arrays (`f d l i b`) come from **prior knowledge of FBX**, which rule 4 says I may not lean on. I confirmed them only by internal consistency: the parse lands exactly on every end offset, decompressed arrays are exactly count × element size, and floats decode to sensible geometry. That is strong evidence but not proof. For example, `Y`, `F`, `l` and `b` never appear in this file, so their sizes are untested.
  - **Array encoding 1 = zlib.** The file never says this. I inferred it from the `78 01` zlib header and from the fact that decompression gives exactly the declared size.
  - **`PolygonVertexIndex` convention.** A negative value `v` marks the last corner of a polygon, and the real index is `-v-1`. This is prior knowledge. The file supports it: every polygon closes, all decoded indices fall within the vertex count, and every polygon comes out as a triangle (692, 5508 and 376 of them).
  - **`Edges` meaning.** Prior knowledge; the file only confirms that every value is a valid corner index.
  - **Connection direction.** `OO child parent` *can* be derived from the file: `Models → 0`, where `Documents/RootNode` is 0, and Geometry → Model. `OP … 'DiffuseColor'` means the texture drives the material's DiffuseColor property, which is readable from the strings.
  - **Trailer and `FileId` meaning.** Not derivable. They stay unverified.
- **A manifest or declared hashes.** Required by the task, absent from the file.
- **A statement of which mesh is "primary".** Absent, so I used heuristics.
- **Units and up-axis for the OBJ.** `GlobalSettings` gives UpAxis 1, FrontAxis 2, CoordAxis 0 and UnitScaleFactor 1.0, plus the per-model rotation and scale. I left the geometry untransformed rather than guess a convention.

## Stumbles (honest list)

1. **The task's premise didn't match the file.** I spent the first minutes hunting for a manifest, docs and a reader. A strings scan and the full tree dump showed none exist. This cost the most thought: I had to redefine "verify every declared hash" as "there are zero declared hashes, so verify the intrinsic checksums instead".
2. **Shell friction, not format friction.** My first commands (`cd … && xxd | head`, `awk` filters, `>` redirection) were refused by the permission layer. I switched to small Python helpers under `tools/`, run with `python -I`. This cost a few minutes.
3. **Recognising the format.** I recognised "Kaydara FBX Binary" immediately. Rule 4 forbids relying on that, so I wrote the parser to *assert* every structural assumption and listed above which rules rest only on consistency evidence. Some of my type-table knowledge was therefore used, and checked rather than independently derived. I am reporting that rather than hiding it.
4. **Contradictory metadata in the file:**
   - `CreationTimeStamp` says 2026-10-06 03:06:39.604, but `CreationTime` says `1970-01-01 10:00:00:000`, and `Original|DateTime_GMT` says `01/01/1970 00:00:00.000`.
   - The Creator string carries a puzzling extra version, `5.12.4`.
   - The texture paths point to `D:\build\crate-nc-v1.fbm\crate_diffuse.png`, which is outside the file and off-limits. I did not look for it. The embedded `Content` was enough.

   None of this blocks extraction, but the file's own metadata is not self-consistent.
5. **Normal and vertex counts differ.** For example, Cube.020 has 3706 vertices but 3696 normals. That is expected with IndexToDirect mapping and not damage, but I checked it explicitly before trusting it.
6. **Choosing the primary mesh** is a judgement call (see above).

## Damaged or corrupted data

**None found.** Every structural, Adler-32, CRC-32 and index-range check passes, so I made no repair attempts. The input file was never modified; I only opened it read-only.

## Wall-clock (rough; session 16:22 → ~16:27)

- Orientation, permission friction, first hexdump: ~1 min
- Strings scan and finding there was no manifest: ~0.5 min
- Writing and running the structural dumper: ~1 min
- Writing the main program (listing, checks, OBJ/PNG extraction): ~2 min
- Probes (texture view, trailer hash tests, mesh stats) and this report: ~2 min
