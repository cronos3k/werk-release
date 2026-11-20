# Examples of profile `motion-comp/1`

Two programs (Python standard library only; they are examples, never run by opening a capsule):

| file | what it is |
|---|---|
| `read_motion.py` | a reader written from the profile document: lists compositions, evaluates properties, computes matrices, reads baked expression values, renders frames of solids, masks, filled shapes, PNG stills and nested compositions, and checks the few effects it implements against the catalog's test vectors (every defined effect is implemented by `effects/effects_ref.py`, which travels in a capsule whose catalog has definitions) |
| `write_minimal.py` | the profile document's section 7 as a program: writes a minimal valid capsule |

The EXAMPLE PROJECT `Stage` of the profile document's worked examples (sections 6.3, 6.4, 6.7,
6.18.4, 6.20), as the payloads a capsule of it has. Ids: composition 111; layers `Badge` 3,
`Card` 60, `Rig` 48, `Back` 88.

| file | node type | what |
|---|---|---|
| `stage.project.json` | `core.motion.project` | the structure node |
| `stage.item-solid.json` | `core.motion.item` | the solid `Card` shows |
| `stage.comp.json` | `core.motion.comp` | the composition |
| `stage.layer-badge.json` | `core.motion.layer` | a shape layer; `position` names track 0 |
| `stage.layer-card.json` | `core.motion.layer` | a solid with a mask, a parent, an expression |
| `stage.layer-card.keys.wkx`, `.txt` | `core.keyframe.tracks` | `Card`'s two tracks, and their decoded content as text |
| `stage.baked.wkx` | `core.expr.baked` | the baked values of the one expression |
| `stage.catalog.json` | `core.effect.catalog` | the catalog of a project without effects: the blend modes |
| `stage.frame10.png` | - | frame 10 as the writing application renders it (8-bit RGB PNG, 96 x 54); its pixels, row by row as R G B bytes, have the sha256 the profile document gives in section 6.20 |

Other node types, one small real payload each:

| file | node type | what |
|---|---|---|
| `minimal.layer-3.keys.wkx` | `core.keyframe.tracks` | the tracks file of section 7.1; dumped byte by byte in the layout document |
| `proxy.example.wkx.zlib` | `core.preview.proxy` | two frames of 4 x 2 pixels |
| `core.preview.proxy.layout.txt` | - | the layout of what a `core.preview.proxy` payload inflates to, with a dump of the example |
| `catalog.tint.example.json` | `core.effect.catalog` | a catalog with one DEFINED effect and its test vectors |
| `footage.item.example.json` | `core.motion.item` | a footage item naming an embedded medium |
| `baked-values.example.json` | `core.expr.baked-values` | a text property driven by an expression |
| `render-queue.example.json` | `core.motion.render-queue` | one queued render |
| `view.example.json` | `x.effectcraft.view` | which compositions were open |
| `plugin-state.example.json` | `x.effectcraft.plugin-state` | the record of a third-party plug-in |
| `data.example.csv` | `core.motion.data` | a data text |
| `lut.example.cube` | `core.color.lut` | a 2 x 2 x 2 lookup table |

Not here, because no small real payload exists: `core.media.source` and `core.media.png` (any
media file is one), `core.media.text` (any text file), `core.text.font` (a font file),
`core.expr.language` (large; every capsule with an expression carries it), `core.motion.lottie`
(a Lottie file), `core.preview.poster` and `core.preview.strip` (PNG pictures; every capsule the
writing application saves has them under `preview/`).
