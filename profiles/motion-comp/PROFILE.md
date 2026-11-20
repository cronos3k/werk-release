# `motion-comp/1` — motion-graphics compositions

Status: in the release as a profile carried in its packages (SPEC §2.2). Origin: EffectCraft
(ArtCraft suite), `werk-native` branch; copied unchanged except for the alignment edit below.

## 1. Where the definition is, and how it travels

The normative definition is the set of files under [`spec/`](spec/), carried as files of a
package's `core.spec` node beside the release `spec/`:

| file in the package | role |
|---|---|
| `spec/PROFILE-MOTION-COMP.md` | the narrative (time, keyframe interpolation, transforms, blending, masks, effects, expressions); manifest `profile_spec` |
| `spec/schemas/manifest.motion-comp.schema.json` | the manifest schema; manifest `manifest_schema` |
| `spec/conventions-map.motion-comp.json` | manifest `conventions_map` |
| `spec/CRAFT-BASE.md`, `spec/NOT-CARRIED.md` | rules every ArtCraft profile shares (this profile's copy is the later CRAFT-BASE revision with §6.3, §6.4, §10-§12) |
| `spec/schemas/core.motion.{project,item,comp,layer,lottie}.schema.json`, `core.effect.catalog.schema.json`, `x.effectcraft.view.schema.json` | payload schemas |
| `spec/layouts/core.keyframe.tracks.layout.txt` | the keyframe-tracks envelope `WKX3` |
| `spec/examples/motion-comp/` | worked examples, `read_motion.py` (evaluator and renderer), `write_minimal.py` |

| `spec/layouts/core.expr.baked.layout.txt`, `x.effectcraft.media.layout.txt`; `spec/schemas/core.motion.render-queue`, `core.expr.language`, `core.expr.baked-values`, `x.effectcraft.plugin-state` `.schema.json` | the files of node types the sample did not hold (see below) |

The EffectCraft sample (`intro.werk`) carries only the schemas and layouts of the node types it
holds. The other six files the narrative names come from the EffectCraft repository: the two
layouts from `werk-native` (`crates/werk/spec/layouts/`), the four schemas from the
application's schema generator (`effectcraft_werk::schema::of`, run in a mirror build on the
release core; the seven schemas the sample also carries came out byte-identical to the
sample's copies). `../VENDORED.json` records each one's origin.

## 2. Node kinds (summary; `spec/PROFILE-MOTION-COMP.md` §3.1 is normative)

| type | count | payload |
|---|---|---|
| `core.motion.project` | exactly 1 (`primary.document`) | JSON: settings, folders, the item table, fonts |
| `core.motion.item` | per footage or solid | JSON |
| `core.motion.comp` | per composition | JSON: settings, layers FRONT FIRST |
| `core.motion.layer` | per layer | JSON: source, timing, switches, blend, parent, the property tree |
| `core.keyframe.tracks` | 0..1 per layer or comp | envelope `WKX3`: numeric keyframes as flat arrays |
| `core.media.source`, `core.media.png`, `core.media.text`, `core.color.lut`, `core.text.font`, `core.motion.data` | per distinct medium | verbatim |
| `core.effect.catalog`, `core.expr.language`, `core.expr.baked`, `core.expr.baked-values`, `core.motion.lottie`, `core.motion.render-queue` | 0..1 | JSON / envelopes |
| `core.preview.poster` (`primary.image`), `core.preview.strip`, `core.preview.proxy` | 0..1 | PNG / zlib envelope, `measured` |

Time is in ticks, 254 016 000 000 per second. Conventions: 52, pinned (§5).

## 3. What a reader outputs (normative for the release reference reader)

`read_motion_comp.py PACKAGE` prints one JSON object (UTF-8, keys sorted, indent 1):
`profile`, `settings`, `items` (id, node, name, kind), `fonts`; `comps`, each with id, node,
name, width, height, frame_rate, duration, `frames` (= duration × num ÷ (ticks per second ×
den), floor) and `layers` FRONT FIRST, each with id, node, name, source, in/out point,
start time, stretch, blend mode, parent, `static` (every non-animated property by its `match`
path, value verbatim) and `animated`: for every property with keyframes (inline `keys` or a
`track` of the layer's tracks node), its value at EVERY frame f of the composition (composition
time f × ticks-per-second × den ÷ num, layer time by start time and stretch), evaluated by §6.3
(Linear, Hold, Bezier with eases, auto-Bezier). A spatial Vec2/Vec3 segment that is not Linear
on both sides (a motion path, §6.4) is not evaluated: the property's series is `null` and a note
says so. Also `notes`, `dead`, `files_verified`, `file_failures`. Not implemented: rendering,
§6.4 motion paths, expressions, effects, nested composition time remapping.

## 4. The release fixture

[`../fixtures/motion-comp-v1.werk`](../fixtures/) — "Beacon sweep": two solids, one
composition 320 × 180, 25 fps, 2 s (50 frames), layer "Beacon" (position: 3 keys in the tracks
node, Linear then Hold; rotation: 2 keys in the tracks node, Bezier with symmetric eases,
0 → 360°; opacity: 2 inline Linear keys) in front of layer "Night" (static). No poster (the
builder renders no pictures). Built by [`build_motion_comp.py`](build_motion_comp.py).
