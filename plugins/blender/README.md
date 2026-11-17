# werk_blender — werk for Blender 4.2

Import and export werk packages in Blender 4.x (gated on 4.2.1 LTS):

* **3d-entity/1** — import a package as objects (mesh, materials + textures,
  colliders, skeleton, animation, point clouds); export the selection or the
  scene to a 3d-entity/1 package.
* **image/1** — import the package's primary image as an image datablock
  (the payload bytes are packed into the .blend unchanged); export an image
  datablock to image/1.

Standard library + `bpy`, no pip. Two readers are vendored, both
byte-identical copies, both hash-checked by the gates:

| file | copy of | used for |
|---|---|---|
| `werk_blender/vendor/werk_single.py` | the werk release library, `libs/python/werk_single.py` | signature verification (Ed25519) on every import, re-reading every export, all of image/1 |
| `werk_blender/vendor/werk_read.py` | the bootstrap loader, `loaders/werk_read.py` | the 3D importer's node walk |
| `werk_blender/spec/` | the release repository's `spec/` | carried inside every 3D export (the manifest's `schemas` paths must exist in the package) |

The 3D exporter keeps its own writer (it writes node types — skeleton, clip,
colliders, bounds, semantics — that the library's helpers do not), and the
release gate measures that it follows the library's determinism contract:
same conventions table (key order included), MANIFEST.json byte-identical
when re-emitted by `werk.json_pretty`, store-mode zip with the UTF-8 flag, no
extra fields, entry order equal to `werk.physical_order`.

## Install

**As a zip** (what you give someone else):

```
python tools/build_addon_zip.py            # -> dist/werk_blender-1.1.0.zip
```

Blender → `Edit > Preferences > Add-ons > Install…` → pick the zip → enable
**werk Entity (.werk)**. (Blender 4.2+ accepts this legacy add-on unchanged.)

**From this folder** (development, CI): put this folder on `sys.path`
(`import werk_blender` puts its own parent there), or add it to Blender's
script paths. Nothing has to be installed into a user profile.

`tools/vendor_spec.py` refreshes `spec/`, `vendor/werk_read.py` and
`vendor/werk_single.py` from the release repository and libraries
(`--check` only compares). Paths are found by `tools/werk_paths.py`: this
folder inside `<ws>/plugins/blender` next to `<ws>/stage/{werk,libs}`, or
`<repo>/plugins/blender`; override with `WERK_REPO`, `WERK_LIBS`,
`WERK_BLENDER_ADDON`.

## Use

**UI:** `File > Import > werk Entity (.werk)` (a 3D entity, or an image/1
package → an image datablock, chosen by the package's profile);
`File > Export > werk Entity (.werk)` (selection, or the whole scene with
"Selection only" off); `File > Export > werk Image (.werk)` (an image
datablock; default: the image in the active Image Editor).

**Headless:**

```bash
blender -b --factory-startup --python-expr "import sys; sys.path.insert(0, r'<this folder>'); \
  import werk_blender as w; r = w.import_file(r'crate-v1.werk'); \
  print(r.nodes_alive, r.signature_verified, r.errors()); \
  w.export_file(r'out.werk', objects=list(r.objects))"

blender -b --factory-startup --python-expr "import sys; sys.path.insert(0, r'<this folder>'); \
  import werk_blender as w; r = w.import_image_file(r'image.werk'); \
  w.export_image_file(r'image-out.werk', r.image)"
```

`import_file` returns a `Result` (or an `ImageResult` for image/1),
`export_file` an `ExportResult` (`.library_verdict` = the release library's
verdict on the file just written), `export_image_file` an
`ImageExportResult`.

## What round-trips (measured by `gate_release.py` on every release fixture)

| | import | export | round trip asserted |
|---|---|---|---|
| geometry (`core.geom.game` GLB) | Blender glTF I/O | glTF, modifiers applied | triangles, distinct positions, distinct (position, UV) corners, three order-independent hashes |
| point clouds (`core.geom.points`, splat means) | mesh vertices + `werk_color` | glTF POINTS primitive | vertex count + position hash; **colours not carried** |
| `core.tex`, `core.material` | images (colour space per texture), Principled BSDF | PNG + metallic-roughness | material and image counts |
| `core.skeleton`, `core.anim.clip` | armature, actions | ← | bone and action counts (rest/pose accuracy: `test_gate.py` rig clause) |
| entity uuid | custom properties | carried forward | uuid identical |
| image/1 | packed image datablock | 8-bit PNG → `write_image_package` | pixels identical (sha256 of the RGBA u8 buffer) |

## Limits (stated, not hidden)

* Raw vertex count is not a round-trip invariant of Blender's glTF exporter:
  it splits vertices where loop normals differ in the last bits (crate-cc0-*:
  4686 → 4737 with triangles, positions and (position, UV) corners
  unchanged). Normals are not compared by the gate.
* Point colours, LOD and source-hi export, imposters, `core.field.flow`,
  `core.pose.rest`, `core.destruct`, `core.props` authoring, audio export:
  not written. Importer reports unimplemented node types as
  `node-type-not-implemented`.
* image/1 export is 8-bit sRGB PNG; float images are converted linear → sRGB
  and clamped; 16-bit / HDR depth is not carried. No thumbnail is written.
* Exports are unsigned (`absent` is a legitimate SPEC §6 state).
* The 3D exports carry the add-on's vendored copy of the release repository's
  `spec/`, the image/1 exports the release library's bundle; both are the
  release-fixes commit 26e3e14 and both give spec_sha256 `55882f4b05e7fee1…`
  (measured on all 16 exports).
* Scratch: Blender's glTF/image I/O need files; the add-on uses
  `.werk-blender-tmp/` beside the package (removed afterwards) or
  `$WERK_BLENDER_TMP`; only if that directory is not writable does it fall
  back to the system temp directory, and it says so in the report.

## Who converts what

The brief asked for this surface to be tiny and explicit, so here it is in
full. `werk_blender/axes.py` is the only place the add-on converts anything,
and its `selftest()` checks every line of this against known vectors.

| data | converted by |
|---|---|
| positions, normals, tangents, UVs, vertex colour, node transforms, skin weights | **Blender's bundled glTF I/O** |
| `core.phys.bounds` AABB and sphere centre | `axes.py` |
| `core.phys.colliders` centres, half-extents, rotations | `axes.py` |
| `core.skeleton` rest translations, rotations, head/tail, `axis_along`/`axis_back` | `axes.py` |
| `core.anim.clip` root track | `axes.py` |
| `core.anim.clip` per-bone rotations | **nobody — they are invariant** |
| UV origin, colour space, audio, semantics, notes | nobody — no axes in them |

### The trap, stated because it cost this adapter a failed gate run

`M = werk → Blender = Rx(+90°)`, so `M·(0,1,0) = (0,0,1)`. That werk's forward
(−Z) lands on Blender's **+Y** rather than Blender's forward (−Y) is not a bug
and is not fixable: Blender's own glTF importer does exactly this. Matching it
is mandatory, because otherwise the geometry (converted by glTF I/O) and the
skeleton (converted by us) would disagree.

Quaternions then split three ways, and the question is always *does the frame
the rotation maps FROM change its convention too?*

* **Both ends convert → conjugate**, `q_M · q · q_M⁻¹`. Collider box
  orientations, because the exporter relabels the box's own axes too (its
  half-extents go through `vec_*` alongside).
* **Only the target converts → left-multiply**, `q_M · q`. Every bone's
  model-space orientation, because the skeleton schema pins Blender's own bone
  axes, so bone-local coordinates are identical on both sides.
  `model_rest_rotation`, a root bone's `rest_rotation`, a clip's root track.
* **Neither converts → unchanged.** A non-root bone's `rest_rotation` and
  every per-bone quaternion in a clip. `L = B_parent⁻¹ B_child`, and
  `(M⁻¹B_p)⁻¹(M⁻¹B_c) = B_p⁻¹B_c`: the M cancels.

Using a conjugation where a left-multiplication belonged put exactly 45° — the
half-angle of the 90° swing — on every posed bone. The gate caught it; the
`selftest()` case named *"identity bone frame → q_M (left-multiply, not
conjugate)"* is what stops it coming back.

## The gates

```
python test_gate.py [--keep] [--json out.json]   # the add-on's original 20 clauses
python gate_release.py [--json out.json] [--only KEY ...]   # every release fixture
```

Both run `blender -b --factory-startup` with `BLENDER_USER_{CONFIG,SCRIPTS,
DATAFILES,EXTENSIONS}` pointed into `_gate_out/blender-profile/`, the add-on
loaded from this folder. `gate_release.py` verifies every export outside
Blender with `python -m werk verify --json` (libs), `werkc verify --json`
(schema-validating) and the release repository's three loaders
(`werk_read.py`; `werk_read.c` and `werk_read.rs` compiled into `_bin/` with
gcc/rustc by `tools/release_verify.py`). Results: `GATE-RESULTS.md`.

## Files

```
README.md  GATE-RESULTS.md
test_gate.py, gate_in_blender.py              the original 20-clause gate (paths made relocatable)
gate_release.py, gate_release_in_blender.py   the release gate
tools/werk_paths.py      where the repo, libs and add-on are
tools/vendor_spec.py     refresh / check the vendored copies
tools/build_addon_zip.py the installable zip
tools/release_verify.py  one package through every release reader
werk_blender/            the add-on (importer, exporter, image_io, libwerk, axes, bounds, ...)
```
