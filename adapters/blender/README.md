# werk_blender — the Blender adapter

Import and export werk 3D entity packages in Blender 4.x. Stdlib + `bpy`, no
pip, ever: werk parsing is vendored byte-identically from
`loaders/werk_read.py`.

Blender is the friendly port. Its native conventions already match werk on
almost everything that usually hurts — metres, right-handed, **wxyz**
quaternions, and a bone convention (+Y head-to-tail, +Z roll reference) that
`core.skeleton.schema.json` pins by name. Only the up axis differs, and
Blender's bundled glTF I/O already swings Y-up⇄Z-up for anything travelling
through a GLB.

## Install

**As a zip** (what you give someone else):

```
python tools/blender/build_addon_zip.py
# -> adapters/blender/dist/werk_blender-1.0.0.zip
```

Blender → `Edit > Preferences > Add-ons > Install…` → pick the zip → enable
**werk Entity (.werk)**.

**From this checkout** (what you use while developing): add
`<repo>\adapters\blender` to Blender's script paths, or just put it on
`sys.path` — the package puts its own parent there on import, so
`import werk_blender` works from a checkout without any Blender configuration.

Both shapes are gate clauses, so neither is a claim.

## Use

**UI:** `File > Import > werk Entity (.werk)` and
`File > Export > werk Entity (.werk)`.

**Headless**, for CI and pipelines:

```bash
blender --background --python-expr \
  "import sys; sys.path.insert(0, r'<repo>/adapters/blender'); \
   import werk_blender; r = werk_blender.import_file(r'fixtures/crate-v1.werk'); \
   print(r.nodes_alive, 'alive', r.errors(), 'errors')"

blender --background --python-expr \
  "import sys; sys.path.insert(0, r'<repo>/adapters/blender'); \
   import werk_blender; werk_blender.export_file(r'out.werk')"
```

`import_file` returns a `Result` and `export_file` an `ExportResult`; both
carry the numbers the gate asserts on, so a pipeline can check them instead of
scraping stdout.

## What round-trips

Measured by `python adapters/blender/test_gate.py` — see HANDOVER "Stage 11
results" for the run.

| | in | out | round-trips |
|---|---|---|---|
| `core.geom.game` | glTF import | glTF export, modifiers applied | **yes**, vertex count preserved |
| `core.geom.lod` | optional, into `lod1..4` collections | not written | import only |
| `core.geom.source` | optional toggle, off by default | not written | import only |
| `core.tex` | PNG → packed image, **colour space per texture** | image → PNG, colour space declared | **yes**, sRGB/Non-Color preserved |
| `core.material` | → Principled BSDF, textures wired | ← Principled BSDF, flattened to metallic-roughness | **yes**, factors and slots |
| `core.phys.bounds` | data only (not scene data) | recomputed, AABB + **Welzl-exact** sphere | recomputed every export |
| `core.phys.colliders` | sphere/box empties in a `colliders` collection | ← those empties | **yes** |
| `core.skeleton` | armature, roll from `axis_back` | ← armature, local **and** model rest values | **yes**, rest heads exact |
| `core.anim.clip` | WKAC → action, LINEAR keys | ← action, uniform grid, WKAC + JSON | **yes**, 8.4e-08 rad worst error |
| `core.audio.*` | listed in the report; preview WAV optional | not written | import only |
| `core.semantics` | tags → custom properties on the root | ← the carried payload / `werk_facet_*` props | **yes** |
| entity uuid, node ids, parts, materials table, licence text | custom properties on the root empty | read back | **yes** (law 4) |
| `core.props`, `core.provenance`, `core.spec`, `core.loader` | verified, extractable, no Blender form | `spec/` + `werk_read.py` re-embedded | data only |

**Stubbed, and named rather than quietly missing:** LOD and source-hi export,
imposters, `core.field.flow`, `core.pose.rest`, `core.destruct`, `core.props`
authoring, audio export, and signing. Every one of them is reported by the
importer as `node-type-not-implemented` when a package contains it, because
SPEC §10.0 is explicit that *declared narrowness is the design and undeclared
silence is the failure*.

**Exports are unsigned.** Signing needs a private key, and SPEC §6 makes
`absent` a legitimate, visible state. An exporter that minted a key so the
output looked signed would defeat the doctrine it implements.

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

## Scratch files

Blender's glTF and image I/O only work through the filesystem, so the add-on
needs somewhere to put an intermediate GLB or PNG. It uses
`.werk-blender-tmp/` **beside the package being read or written**, and removes
it afterwards. Never a user-profile directory. Override with
`$WERK_BLENDER_TMP`; if the package's own directory is not writable it falls
back to the system temp directory and **says so in the report**.

## The gate

```
python adapters/blender/test_gate.py            # measures; exit 1 on any FAIL
python adapters/blender/test_gate.py --keep     # keep the exported packages
python adapters/blender/test_gate.py --json out.json
```

Sixteen clauses. Four of them verify what Blender wrote using readers that
share no code with it — the Rust core through `bindings/python/werk.py`, and
`loaders/werk_read.py` standalone — because one implementation agreeing with
itself is not a measurement. Two clauses (the rig and the textured cube) build
their input in Blender rather than loading a fixture, and say so, because the
golden fixture has no skeleton, no animation and no textures.

If Blender cannot be found the Blender clauses report **SKIP with the reason**.
`16 PASS 0 FAIL 0 SKIP` and `4 PASS 0 FAIL 12 SKIP` are different results.

## Files

```
adapters/blender/
├─ README.md              this
├─ test_gate.py           the gate; finds Blender, runs it, verifies the output
├─ gate_in_blender.py     the half that runs inside Blender; measures, never judges
└─ werk_blender/
   ├─ __init__.py         bl_info, operators, menus, headless entry points
   ├─ axes.py             the one axis conversion + its known-vector selftest
   ├─ bounds.py           AABB, Welzl-exact sphere, area/volume/watertight
   ├─ common.py           scratch dirs, JSON spelling, input_hash, kebab ids
   ├─ envelope.py         canonical MessagePack + the WKAC envelope writer
   ├─ wzip.py             store-mode zip, entry order, preview prefix
   ├─ importer.py         werk -> Blender
   ├─ exporter.py         Blender -> werk
   ├─ spec/               VENDORED, byte-identical (see below)
   └─ vendor/werk_read.py VENDORED, byte-identical
```

`spec/` and `vendor/werk_read.py` are byte-identical copies, refreshed by
`python tools/blender/vendor_spec.py` and gate-checked. They exist because a
conformant manifest's `schemas` map points at paths **inside the package**, so
a writer cannot emit a self-validating werk without carrying the schemas it
references — and a zip-installed add-on has no path back to this repository.
**Re-run the vendor script after editing `spec/` or `loaders/`.**
