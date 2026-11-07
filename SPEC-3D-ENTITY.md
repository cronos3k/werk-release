# werk Profile 1: 3D Entity — SPEC v0.1 (DRAFT — SUPERSEDED)

> **This is the Stage 0 draft, kept for history. The current specification
> is [`spec/SPEC.md`](spec/SPEC.md)**, which resolves every ⛏ below and is
> the copy that travels inside a `.werk` package. Read that one.

Status: DRAFT — structure settled, encodings being finalized alongside the
reference implementation. Every section marked ⛏ still needs its schema or
layout file authored. The manifesto's laws govern everything here; where
this spec is silent, the laws decide.

---

## 1. Container

A werk 3D entity is a **directory tree**; the interchange form is that tree
zipped (store or deflate), extension `.werk`. Directory and zip layouts are
identical. Both are the format.

**Preview-first byte layout (law 9):** when zipping, entries are written in
this physical order: `MANIFEST.json`, `SIGNATURE.json`, `LICENSE`,
`semantics/`, `imposters/`, one preview one-shot from `audio/`, then
everything else. A ranged read of the first bytes yields a browsable,
searchable, auditable listing.

```
entity.werk/
├─ MANIFEST.json          the graph, hashes, conventions, versions
├─ SIGNATURE.json         signature chain (may be absent — three-state)
├─ LICENSE                full license text, embedded
├─ README.txt             one paragraph for humans
├─ spec/                  ← the format travels with the file (law 2)
│  ├─ SPEC.md             this document (the version the file conforms to)
│  ├─ schemas/*.json      JSON Schema per structured node type
│  ├─ layouts/*.layout.txt  grammar per custom binary
│  └─ facets.json         the semantic tag registry (versioned)
├─ geometry/              source-hi, game, lod1..4 (GLB) ⛏
├─ textures/              PNG (color space declared per texture)
├─ materials/             PBR parameter JSON per material id
├─ imposters/             octahedral atlases, 2 tiers, G-buffer channels ⛏
├─ physics/               colliders, bounds, mass/CoM/inertia, regions
├─ fields/                flow field grid (bin + layout) ⛏
├─ poses/                 32 settled rest orientations (bin + layout) ⛏
├─ skeleton/              canonical-pose quaternion skeleton ⛏
├─ animation/             sampled clips + event tracks ⛏
├─ audio/                 the splat-foley package schema, verbatim
├─ destruction/           fracture sets, thresholds, debris mapping ⛏
├─ properties/            VLM-inferred sim properties per region
├─ semantics/             facet tags, style embedding, palette
├─ provenance/            producers, inputs, costs, conjure prompts
└─ x/                     extension namespaces (e.g. x/cub/ cooked tier)
```

## 2. MANIFEST.json

Single source of structure. Contains:

- `werk`: format major.minor; `profile`: `"3d-entity/1"`.
- `entity`: `{uuid, name, summary}` — identity for recognition, never for
  external reference (laws 1, 4).
- `conventions` (law 8), machine-checked, all mandatory:
  `{endianness:"le", units_per_meter:1.0, up_axis:"y", forward_axis:"-z",
  handedness:"right", winding:"ccw", quat_order:"wxyz",
  oct_encoding_pole:"y", sh_l1_order:["dc","y","z","x"],
  color_space_default:"srgb"}` — readers MUST verify they support these
  values before consuming payloads, and MUST refuse silently-wrong instead
  of guessing.
- `parts[]`: `{part_id, name, parent, transform}` — the stable-id join key
  across every node family (law 4).
- `materials[]`: `{material_id, part_id, name}` → materials/, properties/,
  audio material-sound sets.
- `nodes[]`: the graph. Each node: `{node_id, type (namespaced), part_id?,
  versions[], active, edges[{to, kind: requires|enhances}]}`.
  Each version: `{v, files[{path, sha256, size, offset_hint?}], note,
  producer{tool, model?, version}, input_hash?, epistemic:
  authored|measured|inferred, confidence?, created}`.
  Work note mandatory (law 6). `input_hash` mandatory on derived nodes
  (law 5).
- Every byte in the container except MANIFEST.json itself is reachable from
  exactly one node version's `files[]`. Nothing floats.

## 3. Node families (core.*)

⛏ = schema/layout file still to be authored in spec/.

| Type | Payload | Notes |
|---|---|---|
| `core.geom.source` | GLB | high-poly truth |
| `core.geom.game` | GLB | authored/derived game mesh |
| `core.geom.lod` | GLB | levels 1–4, `lod_of` edge, screen-space-error metric in node meta ⛏ |
| `core.tex` | PNG | `color_space` per texture mandatory |
| `core.material` | JSON | PBR params, texture refs by path |
| `core.imposter` | PNG ×4 + JSON ⛏ | per tier: albedo/normal/depth/MRAO atlases + view-encoding descriptor |
| `core.phys.colliders` | JSON | sphere set + OBB set, per part |
| `core.phys.bounds` | JSON | AABB + true minimal sphere (+ per-part) |
| `core.phys.body` | JSON | mass, CoM, inertia tensor, per-region density |
| `core.field.flow` | bin + layout ⛏ | 3D grid: SDF + flow response |
| `core.pose.rest` | bin + layout ⛏ | 32 settled orientations: quat + contacts |
| `core.skeleton` | JSON + bin ⛏ | bones: parent, rest quat+t, length; canonical pose numeric; retarget maps |
| `core.anim.clip` | bin + layout + JSON ⛏ | uniform-rate quat tracks; explicit root track; event track → audio effect ids |
| `core.audio.*` | splat-foley schema | description, segments, plan, effects with takes/timings/transcripts |
| `core.destruct` | GLB + JSON ⛏ | fracture pieces, thresholds per region, debris map |
| `core.props` | JSON | sim properties per material region, epistemic-stamped |
| `core.semantics` | JSON | facet tags (registry), style embedding {model, dim, vec}, palette |

## 4. Versioning, signatures, degradation

Per manifesto laws 6, 7, 3 — normative text lives there; this profile adds:
version directories are suffixed `@N` when multiple versions coexist on
disk; readers resolve through `nodes[].versions[]`, never by globbing.
If `active` is invalid, a resilient reader MAY fall back to the newest
valid earlier version and MUST report having done so.

## 5. Extension: x.cub.v1 (informative)

The CUB engine's cooked tier, demonstrating law 12: interleaved
`BakedVertex` streams (144 B, declared per-field offsets), SH-L1 per-vertex
irradiance in the declared basis order, per-triangle analytic shadow
records, position-only streams for BLAS/physics. Any other consumer skips
`x.cub.*` and loses nothing but CUB's fast path. CUB is the proving-ground
consumer for this entire profile.

## 6. Conformance (gate for v1.0)

1. **Agent gauntlet**: fresh agents, given one `.werk` and nothing else,
   produce working loaders (law 10). Measured: success rate,
   time-to-loader, feature coverage.
2. **Damage gauntlet**: corrupted node + unknown node type → everything
   else loads, skips reported precisely.
3. **Retarget test**: one calibration pose binds a foreign rig; a clip
   retargets with declared tolerance.
4. **Round-trip**: read → write → byte-identical re-emission of untouched
   nodes (hashes prove it).
5. **CUB ingest**: the proving-ground engine consumes core + x.cub with
   zero cook step.
