# WerkLink — design of the Unreal Engine adapter

> **Release note.** The release copy of WerkLink in this folder is built and
> gated on **Unreal Engine 5.8.2** only (`README.md`, `GATE-RESULTS.md`).
> Unreal Engine 5.7, which this document was first written against, is
> untested for this release.

One editor-only UE5 plugin, two directions. `.werk` → real UAssets, and
selected UAssets → a conformant unsigned `.werk`.

Almost source-only: **one** `.uasset` ships with it — the master material
`Content/M_WerkPBR`, so `core.material` import produces working material
instances out of the box — and it is a build product of a committed script.
No third-party dependency, no network. Built and gated for this release on
**Unreal Engine 5.8.2** with MSVC 2022 (5.7 untested).

There is a standing test project: see **`TESTBED.md`** for how to launch it,
drive it over MCP, and run both gates.

---

## Install

1. Copy `plugins/unreal/WerkLink/` into your project's `Plugins/` folder.
2. Regenerate project files, or just open the project and let it compile.
3. Configure **Project Settings → Plugins → WerkLink** (see *Settings* below).

## Use

**Content Browser.** Right-click a folder → *Import .werk here...*.
Right-click one or more assets → *Export to .werk...*.

**Commandlet.**

```
UnrealEditor-Cmd.exe <Project.uproject> -run=WerkLink \
    -Import=<file.werk> [-Dest=/Game/Werk] [-Master=/Game/M_Werk.M_Werk] \
    [-DryRun] [-NoSave] [-NoAudio] [-NoCollision]

UnrealEditor-Cmd.exe <Project.uproject> -run=WerkLink \
    -Export=<out.werk> -Assets=/Game/A.A,/Game/B.B [-Spec=<werk-repo-dir>] \
    [-Name="Entity name"] [-Hermetic] [-DryRun]

UnrealEditor-Cmd.exe <Project.uproject> -run=WerkLink -Manifest=batch.json
```

`batch.json` is a JSON array of operations, parsed by the format's own JSON
reader (so a duplicate key in your batch file is refused, not silently
resolved):

```json
[ { "op": "import", "file": "<repo>/fixtures/crate-v1.werk", "dest": "/Game/Werk" },
  { "op": "export", "file": "<lab>/out/crate.werk",
    "assets": ["/Game/Werk/WoodenCrate/SM_GeomGame.SM_GeomGame"],
    "spec": "<repo>", "name": "Wooden crate" } ]
```

**Exit status** follows `SPEC.md` §10.1 in all three modes: `0` clean, `1` the
container opened but at least one report entry has severity `error`, `2` a
container-scoped refusal.

---

## The conventions bridge

This is the part to check rather than believe. `Private/Core/werk_basis.h`
carries the derivation; `BasisSelftest()` carries the numbers, and the gate
runs it.

| | werk | Unreal |
|---|---|---|
| up | +Y | +Z |
| forward | −Z | +X |
| right | +X | +Y |
| handedness | **right** | **left** |
| unit | metre | centimetre |
| quaternion | w x y z | x y z w |
| winding | ccw | (see below) |

The map, before the unit scale:

```
M = [[ 0,  0, -1],      X = -z        det(M) = -1
     [ 1,  0,  0]       Y =  x
     [ 0,  1,  0]]      Z =  y
```

All three named axes land on their named counterparts, which is only possible
because the determinant is **negative** — no rotation carries a right-handed
frame onto a left-handed one. Everything else follows from that one number.

**Test vectors, all asserted numerically by `BasisSelftest()`:**

| input (werk) | output (Unreal) | what it proves |
|---|---|---|
| `(0, 1, 0)` | `(0, 0, 1)` | up → up |
| `(0, 0, −1)` | `(1, 0, 0)` | forward → forward |
| `(1, 0, 0)` | `(0, 1, 0)` | right → right |
| `(0, 1, 0)` m | `(0, 0, 100)` cm | the unit factor, on positions only |
| scale `(2, 3, 5)` | `(5, 2, 3)` | extents permute and never negate |
| aabb `(−0.5,−0.5,−0.5)…(0.54,0.54,0.5)` | `(−50,−50,−50)…(50,54,54)` cm | corners must be re-min/re-maxed, not carried positionally |
| yaw +90° about werk up | −90° about UE up | the mirror inverts the SENSE of a rotation |

**Quaternions.** A rotation's axis is a pseudovector, so under an
orientation-reversing map it goes to `det(M)·M·a = −M·a` while the angle is
unchanged. With the `wxyz` → `xyzw` order swap folded in:

```
q_ue(xyzw)   = ( z, -x, -y, w )      from q_werk(wxyz) = (w, x, y, z)
q_werk(wxyz) = ( W, -Y, -Z, X )      from q_ue(xyzw)   = (X, Y, Z, W)
```

The selftest proves this closed form three ways: against an independently
computed `M R Mᵀ` (quaternion → matrix → conjugate → quaternion, deliberately
not reusing the closed form), against named rotations, and against the
property that actually makes a mesh and a skeleton agree —

```
convert(rotate(q, v)) == rotate(convert(q), convert(v))
```

— which a round-trip test alone cannot catch, because a conjugation written
the wrong way round round-trips perfectly.

**Winding is a theorem, not a preference.** `det(M) < 0` reverses
orientation, so every triangle's index order reverses in both directions.
Checked on a real triangle rather than asserted in a comment: a werk triangle
whose right-hand-rule normal is werk up, mapped with the winding KEPT, comes
out with normal `(0, 0, −1)` — inverted. Reversed, it comes out `(0, 0, 1)` =
`M · (werk up)`. Normals themselves transform by `M` directly, because `M` is
orthogonal and its inverse transpose is itself.

**UVs do not flip.** `uv_origin` is top-left on both sides. That is a
deliberate non-conversion and it is listed as one.

---

## What imports

| werk node | becomes | notes |
|---|---|---|
| `core.geom.game` | `UStaticMesh` (LOD 0) | `core.geom.lod` nodes attach as LOD 1–4, ordered by `meta.lod_level`, never by node order |
| `core.geom.source` | its own `UStaticMesh` | the archival anchor is a different thing, not a better LOD (`SPEC.md` §3.10) |
| `core.tex` | `UTexture2D` | colour space from `meta.color_space`, **not** the PNG's sRGB chunk (law 8) |
| `core.image.source`, `core.image.derived` | `UTexture2D` | profile 2 (`image/1`). Same path as `core.tex` — a PNG with a declared colour space is the same thing — so an image package produces textures and metadata and no geometry, which is the right answer and not a degraded one |
| `core.material` | `UMaterialInstanceConstant` | on `M_WerkPBR` by default; texture slots bound and their static switches turned on; unbound parameters are reported, never silently dropped. The instance is then **assigned to the meshes it governs**, so an imported entity is shaded without a human step |
| `core.phys.colliders` | simple collision | spheres + oriented boxes, per the real `groups[]` schema |
| `core.phys.bounds`, `core.phys.body`, `core.props` | package metadata | converted to centimetres where they are lengths |
| `core.semantics` | package metadata keys | `werk.semantics.<facet>` |
| `core.audio.effect`, `core.audio.ambience` | `USoundWave` | only the take whose `files[].role` is `best`; the others are counted and reported |

Identity is stored, not recomputed: the werk node id, entity uuid, part and
material ids, source path, sha256, resolved version, work note and epistemic
stamp all go into `UWerkAssetUserData` and into package metadata. Export reads
them back, so a round trip preserves the original kebab-case ids exactly.
kebab-case → Unreal name is lossy, which is precisely why the reverse
direction is a lookup and never a computation.

## What does not import, and says so

* `core.skeleton`, `core.anim.clip` — an honest "not yet". The payload is
  present and hash-verified in the package; it is simply not turned into a
  UAsset.
* `core.spec`, `core.loader`, `core.license`, `core.readme`,
  `core.provenance`, `core.audio.package` — carried by the package for a
  reader, not assets.
* Any `x.*` node — skipped as unknown. Unknown-because-newer and
  unknown-because-extension degrade through the same path
  (`SPEC.md` §10 step 8).

Every one of these produces an `FWerkNodeOutcome` in the result struct.
**Outcomes are data, not log lines** — that is what makes graceful degradation
inspectable by a commandlet rather than something you have to read a log to
discover.

## What exports

Static meshes (from `GetMeshDescription`, **never** an exporter), their simple
collision, material parameters flattened to the PBR JSON, and sound waves
(the imported WAV bytes verbatim, so the round trip is byte-identical).

Textures, as **real PNGs**, encoded by Unreal's own image wrapper
(`FImageUtils::CompressImage(..., TEXT("png"), ...)` resolves
`EImageFormat::PNG` through `IImageWrapperModule` — the same
`FPngImageWrapper` the content browser writes a `.png` with). Nothing here
re-implements a PNG encoder.

The source is read with `FTextureSource::GetMipImage`, not `GetMipData`, which
means a **compressed** `FTextureSource` (a JPEG- or PNG-wrapped asset) is
decoded on the way out with no second code path.

`color_space` is `srgb` when the texture's `SRGB` flag is set and `linear`
otherwise — the declared value, from the one place Unreal actually shades from,
never recovered from the PNG's own chunks (law 8). `usage` is looked up in
`UWerkAssetUserData` when the texture came in through WerkLink, because
`CompressionSettings` can only tell a normal map from everything else and
recomputing would flatten five declared values into two.

**Lossless is a claim, so it is checked.** The work note names the source
`ETextureSourceFormat`, the decoded `ERawImageFormat`, and whether PNG stores
that format directly. `G8`, `G16`, `BGRA8` and `RGBA16` go through unchanged —
that set is exactly what `FPngImageWrapper::GetSupportedRawFormat` returns
unchanged, not a table typed from memory. Everything else (`BGRE8`, `RGBA16F`,
`RGBA32F`, `R16F`, `R32F`) is blitted to `RGBA16` by the image wrapper before
encoding, and the note says **LOSSY** in as many words.

A texture whose mip cannot be decoded is one refused node with a named report
entry, never a fabricated payload and never a failed package (the island rule).

Material texture slots are exported too: a `core.material` slot names the
`core.tex` NODE and mirrors its path, per the schema. A slot whose texture is
outside the export closure is **dropped with a report entry** rather than
written as a dangling reference, and a texture parked on a parameter whose
static switch is off is not a binding and is not exported.

## Hermetic, and what that costs

The exported package references nothing external. The closure walk separates
`/Engine/` packages out; each one is either baked in or replaced with a
declared fallback plus a work note. There is no third branch. `-Hermetic`
(commandlet) or *Fail On Unresolvable External Reference* (settings) turns the
substitution into a refusal instead.

`spec/` and `loaders/` are payload, not documentation (law 2). Point
**Spec Source Directory** at the werk repository root and they are embedded,
and the package is redistributable-conformant. Leave it empty and the package
is written anyway, with a report entry saying in as many words that it is not.

Loader nodes are emitted **one per file**, because `loaderMeta` describes one
reader — a single language, entrypoint and toolchain — and a node bundling
`werk_read.py`, `.rs` and `.c` cannot honestly answer any of the three.
Language, entrypoint and toolchain are facts about the file; `capabilities` is
a claim about code this exporter merely copied, so it is declared at the
conservative minimum and the work note says exactly that.

---

## Which mesh gets which material, and which rule fired

Three rules, tried in order, and the outcome line names the one that fired —
because two of the three are inferences and an inference reported as a fact is
the thing this project exists to argue against.

1. the geometry node itself declares this `material_id` — a fact;
2. the manifest's `materials[]` maps this `material_id` to a `part_id` and the
   geometry node declares that `part_id` — a fact, one hop through the manifest,
   which is what `materials[]` is for;
3. the package declares exactly **one** `core.material` — an **inference**, and
   the report says `INFERRED`.

---

## Out of scope in v1, named so an absence is a decision

* **OFPA / external actors.** One File Per Actor puts actor packages outside
  the level's folder, so a path-scoped walk misses them. WerkLink v1 exports
  **entities, not levels**, so this does not apply — but it will the moment
  someone points it at a map.
* **Signature verification.** WerkLink carries no Ed25519. When
  `SIGNATURE.json` is present it reports the fourth word, **`unverified`**,
  and never `absent` for a file that is present or `signed-and-valid` for a
  check it did not make (`SPEC.md` §10 step 4).
* **Signing on export.** Packages are unsigned. Signature absence is a valid
  three-state, and key handling belongs in something audited for it.
* **Skinning, morph targets, animation** on the import path.

## Why direct `FMeshDescription` and not Interchange

The brief required picking one and justifying it.

* Interchange's GLB path builds its own materials from the GLB. `SPEC.md`
  §10.2 says *a reader that takes material parameters from the GLB instead of
  from `materials/` is non-conformant* — so a pipeline that helpfully does
  that is actively wrong here.
* The GLB has to be parsed anyway to cross the basis, and `MINI-SPECS.md` §10
  pins the subset tightly enough that the parser is small.
* Interchange import is asynchronous; its commandlet story is more moving
  parts, not fewer.

The cost is honest: no skinning and no animation on the import path in v1.

---

## Architecture

```
Private/Core/          engine-free C++17. std::string, no FString, no UE headers.
  werk_basis           the conventions bridge + its selftest
  werk_sha256          FIPS 180-4 (UE Core ships SHA-1, Blake3, City, xxhash — no SHA-256)
  werk_zip             store-only reader/writer, crc32, zip64 detect-and-refuse
  werk_json            the MINI-SPECS 3 subset, incl. duplicate-key REJECTION
  werk_glb             the MINI-SPECS 10 subset, one parser for both directions
  werk_manifest        the SPEC 10 reader checklist, node-scoped refusal
Private/               the Unreal layer: importer, exporter, closure walk, module
Public/                FWerkLinkAction (the static facade), settings, user data, commandlet
```

The Core files compile into the UE module **and** into the standalone gate
target, so the gate measures the shipping code rather than a copy of it.

`werk_json` exists rather than `FJsonObject` for a concrete reason:
`MINI-SPECS.md` §3 says duplicate object keys are illegal and a reader **MUST
reject the file** rather than pick a winner. A `TMap`-backed parser picks a
winner by construction, silently. It also accepts a BOM (§2 says reject, never
strip, because a stripped BOM changes the file's sha256 and sha256 is the
store key) and the `NaN`/`Infinity` spellings §3 bans.

`Private/Core` is excluded from unity builds and from the shared PCH, and the
`Build.cs` says why in both cases.

---

## The gate

Two targets, both measured, both reproducible.

**Standalone** (no engine needed):

```
plugins\unreal\tests\build_gate.bat
plugins\unreal\tests\.build\werk_gate.exe fixtures\crate-v1.werk fixtures\crate-v1-damaged.werk
```

**Unreal** (needs UE 5.8 + MSVC; tested on 5.8.2 only). The standing testbed is `TESTBED.md`; the
gate starts its own commandlets:

```
python plugins\unreal\tests\roundtrip_gate.py
```

It imports all four fixtures and asserts the exact node/asset counts and the
exact SPEC 10.1 exit status for each, exports the textured entity back out,
compares texture PIXELS across the round trip (two PNG encoders will never agree
on bytes and calling that a failure would be dishonest), re-imports, and runs
three independent readers over the result.

**Editor control** (needs a running editor):

```
python tools\ue_mcp\launch_testbed.py
python tools\ue_mcp\proof_session.py
```

All three were run for Stage 10B. The numbers are in `HANDOVER.md` under
*Stage 10 results* and *Stage 10B results*.

## Landmines

The landmine notes behind this adapter came from an internal review of an
earlier private Unreal plugin; that review is not part of this repository.
What it taught is recorded in the source, beside each fix.

One landmine this build **found** rather than inherited, recorded in
`WerkLinkImport.cpp` beside the fix:

> Importing a WAV through `USoundFactory` in a commandlet trips a handled
> ensure — *"Decoder for AudioFormat 'BINKA' not found"*, `SoundWave.cpp:248`.
> `FSoundWaveData::CacheRuntimeFormatDependentState` asks the audio info
> factory registry for a decoder for the project's default wave format, and in
> a commandlet nothing has loaded the `BinkAudioDecoder` module that registers
> it. `-nosound` does not help: the ensure is in the ASSET path, not the device
> path. The sound waves import correctly either way, but an ensure logs as an
> Error and `UnrealEditor-Cmd` then exits non-zero, so an otherwise clean batch
> reports failure. Loading the module by name fixes it; WerkLink does that
> lazily, once, and reports whether it worked.

Stage 10B found three more, and all three are the silent kind — recorded here
because each produced a correct-looking report while the result was wrong.

* **A checked path conversion kills the process.** A destination that is not a
  valid long package name reached `FPackageName::LongPackageNameToFilename`,
  which calls `appError`. SPEC 10.1 has no "die" outcome; `-Dest` is now
  validated at the point of use and a bad one is a container-scoped refusal
  with exit 2. (S10-4.)
* **`SetNumUVChannels` invalidates a UV attribute ref taken before it.**
  Writing through the stale ref succeeds with no assert and no warning, and the
  mesh comes out with every UV at (0, 0) — a textured mesh that samples one
  texel while every count and every report stays correct. The channel count is
  now decided before the refs are taken, and the importer prints the UV extent
  of the built mesh so a collapse is a number rather than a discovery. (S10-6.)
* **A mesh built through `CreateMeshDescription` has an empty
  `StaticMaterials` array**, and `SetMaterial(0, ...)` on it silently does
  nothing. The material import reported "assigned to 1 mesh" while assigning to
  zero slots. One slot is now created at build time, and an assignment to zero
  slots is counted as zero.

And two about driving the editor, both in `TESTBED.md`: it will not screenshot
a window that is not in the foreground, and it does not say so (S10-5); and
`URemoteControlSettings` is `UCLASS(config = RemoteControl)`, so its settings in
`DefaultEngine.ini` are read by nobody.
