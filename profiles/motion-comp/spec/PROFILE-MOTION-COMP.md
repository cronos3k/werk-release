# werk Profile: Motion Composition - `motion-comp/1`

Status: revision 1, written by EffectCraft 0.9.2. Manifest schema:
`spec/schemas/manifest.motion-comp.schema.json`. Conventions map:
`spec/conventions-map.motion-comp.json`. Examples and two reference programs:
`spec/examples/motion-comp/` (start with its `README.md`).

A `motion-comp/1` capsule is one motion-graphics project: compositions made of layers, every
layer property a value that may be animated by keyframes or driven by an expression, the
effects, masks and mattes on the layers, and every medium, font and lookup table the project
uses - inside the file, each stored once.

This document builds on, and does not restate:

* `spec/SPEC.md` sections 1 (container), 2 (manifest), 3.1 (binary envelope), 5 (epistemic
  stamps), 6 (versions), 10 (refusal and exit statuses);
* `spec/CRAFT-BASE.md` (the base nodes every ArtCraft capsule carries, the revision log,
  format definitions, the licence and the signature chain);
* `spec/MINI-SPECS.md` section 8 (PNG) for the PNG payloads;
* `spec/layouts/ENVELOPE.layout.txt` for the three envelope binaries of this profile.

Everything else a reader or a writer needs is in this document, in the JSON Schemas under
`spec/schemas/`, in the layout grammars under `spec/layouts/`, and - for the meaning of effect
ids, blend modes and the expression language - in two nodes of the capsule itself
(`effect-catalog`, `expr-language`). No application is needed, and none is assumed: where this
text says "the writing application" it means the program that wrote the file, and what it says
about that program is a fact about how numbers in the file were made.

HOW MUCH OF THE PICTURE IS DEFINED. A motion-graphics project is a program for making
pictures. This profile defines, exactly: time; every interpolation of a keyframed value; layer
timing; the transform of 2D and 3D layers with parenting; the camera projection; the colour
pipeline; all 38 blend modes; masks; mattes; adjustment layers; nested compositions;
motion blur; the geometry and painting of shape layers except the path operators named in
section 6.16; 117 of the writing application's 306 effects (section 6.12). It does NOT define, in this
revision: the other effects, text layout, lights and shadows, the physically based 3D renderer,
3D model formats, and the generators behind `random` and `wiggle` in expressions. Section 8
lists every one of these by name; what is not defined is still carried completely as
parameters, and for expressions the evaluated values travel beside the text (section 6.18).

## 1. Container

A capsule is a store-mode zip (`.werk` file) or a directory of the same name with the same
files (SPEC.md section 1). A writer of this profile makes a zip unless the capsule would exceed
what a zip without zip64 can hold (4 GiB minus 64 MiB in total, 4 GiB per member, 65 535
members): then it makes the directory form. A reader accepts both; nothing else differs.

Directories of this profile (paths inside the capsule):

| path | holds |
|---|---|
| `project/` | `project.json` (the structure node), `render-queue.json` |
| `items/` | `item-<id>.json`: one footage or solid item each |
| `comps/comp-<id>/` | `comp.json`, `comp.keys.wkx`, and per layer `layer-<id>.json`, `layer-<id>.keys.wkx` |
| `media/<node id>/` | the files of one medium, under their own (made safe) names |
| `data/` | the text of data footage |
| `luts/` | lookup-table files named by effect parameters |
| `fonts/<node id>/` | one font file each |
| `effects/` | `catalog.json` |
| `expressions/` | `language.json`, `prelude.js`, and per composition `comp-<id>.baked.wkx`, `comp-<id>.baked-values.json` |
| `lottie/` | `comp-<id>.json` |
| `preview/` | `poster.png`, `strip-<id>.png`, `proxy.wkx.zlib` |
| `view/` | `view.json` (application-private) |
| `x/effectcraft/` | application-private state |

A path is only where a file sits. WHICH node a file belongs to, and which node holds which item,
composition or layer, is said by `MANIFEST.json` and by the payloads (section 3) - never by a
path pattern.

Preview tier (`MANIFEST.json` -> `container.preview_tier`), in this order at the front of a zip:
`MANIFEST.json`, `SIGNATURE.json` (when signed), `LICENSE`, `README.txt`, `HOW-TO-READ.md`,
`loaders/`, `spec/`, `revisions/`, `project/project.json`, `preview/`. A program that has read
this prefix can list the project's compositions and items and show the poster, the contact
strips and the first frames in motion without reading a medium.

## 2. MANIFEST.json

* `profile`: `"motion-comp/1"`. `profile_spec`: `"spec/PROFILE-MOTION-COMP.md"` (this document).
* `primary.document`: the node id of the one `core.motion.project` node (`project`). Required.
* `primary.image`: the node id of the `core.preview.poster` node (`preview-poster`). Optional:
  absent when the capsule was saved by a program that renders no pictures.
* `entity.name`: the project's listing name. `entity.uuid`: made once, when the capsule is
  created; it is the identity of the project through every later Save and Save As copy keeps
  it (a copy is the same work).
* `formats`: the id of every foreign encoding a payload of this capsule is in, with the path
  of its definition document. A capsule carries the definition of a media format only while
  one of its nodes (in any version it still holds) is in that format; the Save that embeds the
  first medium of a format adds the definition in the same step.
* `conventions`: section 5. Every value there is pinned by the manifest schema.

## 3. Node families

### 3.1 The table

| type | how many | payload | defined by |
|---|---|---|---|
| `core.spec`, `core.loader`, `core.license`, `core.readme`, `core.revisions`, `core.tool` | base | - | `spec/CRAFT-BASE.md` |
| `core.motion.project` | exactly 1 | JSON | `spec/schemas/core.motion.project.schema.json` |
| `core.motion.item` | 1 per footage or solid item | JSON | `spec/schemas/core.motion.item.schema.json` |
| `core.motion.comp` | 1 per composition | JSON | `spec/schemas/core.motion.comp.schema.json` |
| `core.motion.layer` | 1 per layer | JSON | `spec/schemas/core.motion.layer.schema.json` |
| `core.keyframe.tracks` | 0 or 1 per layer, 0 or 1 per composition | envelope `WKX3` | `spec/layouts/core.keyframe.tracks.layout.txt` |
| `core.motion.render-queue` | 0 or 1 | JSON | `spec/schemas/core.motion.render-queue.schema.json` |
| `core.motion.data` | 1 per distinct data text | UTF-8 text | section 3.7 |
| `core.media.source` | 1 per distinct medium in a defined foreign format | the file(s), verbatim | the definition `MANIFEST.json` -> `formats` names for the node's `meta.payload_format` |
| `core.media.png` | 1 per distinct PNG medium | PNG file(s), verbatim | `spec/MINI-SPECS.md` section 8 |
| `core.media.text` | 1 per distinct text medium | UTF-8 text, verbatim | section 3.6 |
| `core.color.lut` | 1 per distinct lookup table | UTF-8 text, verbatim | section 6.15 |
| `core.text.font` | 1 per distinct font file | a TrueType / OpenType file or collection, verbatim | `spec/formats/sfnt.md` |
| `core.effect.catalog` | 0 or 1 (1 in every capsule the writing application saves) | JSON | `spec/schemas/core.effect.catalog.schema.json`, section 6.12 |
| `core.expr.language` | 0 or 1 (1 when any property has an expression) | JSON + a source file | `spec/schemas/core.expr.language.schema.json`, section 6.18 |
| `core.expr.baked` | 0 or 1 per composition | envelope `WKX4` | `spec/layouts/core.expr.baked.layout.txt` |
| `core.expr.baked-values` | 0 or 1 per composition | JSON | `spec/schemas/core.expr.baked-values.schema.json` |
| `core.motion.lottie` | 0 or 1 per composition | JSON (a Lottie animation) | `spec/schemas/core.motion.lottie.schema.json`, section 3.9 |
| `core.preview.poster` | 0 or 1 | PNG | `spec/MINI-SPECS.md` section 8 |
| `core.preview.strip` | 0 or 1 per composition | PNG | the same |
| `core.preview.proxy` | 0 or 1 | zlib stream around envelope `WKX2` | `spec/formats/zlib-deflate.md`, `spec/examples/motion-comp/core.preview.proxy.layout.txt` |
| `x.effectcraft.media` | 1 per distinct medium in a format with no definition here | the file(s), verbatim, opaque | `spec/layouts/x.effectcraft.media.layout.txt` |
| `x.effectcraft.view` | 0 or 1 | JSON | `spec/schemas/x.effectcraft.view.schema.json` |
| `x.effectcraft.plugin-state` | 1 per third-party effect plug-in in use | JSON | `spec/schemas/x.effectcraft.plugin-state.schema.json`, section 6.14 |
| any other `x.*` | optional | anything | the extension's own layout file |

Every node of this profile has ONE payload file except: a medium with several files (an image
sequence, a 3D model with files beside it) and `core.expr.language` (its second file is a
reference source). Where a version has several files its `payload_file` names the payload.

### 3.2 The project and its items

**`core.motion.project`** - node id `project`; file `project/project.json`. The STRUCTURE node:
the project settings (bit depth, colour management), the folders, and three tables that say
which node is what:

* `items`: `[{id, kind, node}]` for every item that is not a folder, ascending by id. `kind` is
  `comp`, `footage` or `solid`. `node` is a `core.motion.comp` node for `comp`, a
  `core.motion.item` node otherwise. THIS table - not the node id's spelling - binds an item to
  its node.
* `folders`: the folders themselves (they have no node): `{id, name, label, comment, parent, proxy}`.
* `fonts`: `[{family, style, node, status}]`, every face a text layer names (section 3.7).

and the node ids of the three singletons it uses: `effect_catalog`, `expression_language`,
`render_queue` (each null or absent when there is none). `next_id` is the next id the project
hands out: items, layers, properties and property groups share one counter, every id in the
document is below it, and an id is never reused. `app_schema` (1 or 2) selects one meaning that
changed between two revisions of the writing application (section 6.12, effect space).

Edges (all `enhances`): to every item and composition node (role `contains`), to the catalog
(`defines-effects`), the language node (`defines-expressions`), the queue (`render-queue`),
every font (`font`), every plug-in record (`plugin-state`). Stamp: `authored`.

An item's place in the project tree is its `parent`: the id of a folder, or null for the
root. Folder ids and item ids are from the same counter.

**`core.motion.item`** - node id `item-<id>`; file `items/item-<id>.json`. One item that is
not a composition and not a folder: `{schema_version, id, name, label, comment, parent, proxy,
kind}`; `kind` has exactly one key:

* `{"Solid": {color, width, height, pixel_aspect}}` - a rectangle of one colour. `color` is
  `[r, g, b]`, 0..1, in the encoding of authored colours (section 6.8).
* `{"Footage": {...}}` - a medium and how it is interpreted: `media` (which node holds its
  bytes, section 3.6), `kind` (`Video`, `Still`, `Sequence`, `Audio`, `Model`, `Data`), `width`,
  `height`, `pixel_aspect`, `frame_rate`, `duration`, `has_video`, `has_audio`, `alpha`
  (`Straight`, `Premultiplied`, `Ignore`), and the optional interpretation fields the schema
  lists. Section 6.19 says how a frame of it becomes pixels.

`proxy`, when not null, is a second footage description (`{enabled, footage}`) that stands in
for the item while `enabled` is true. Edges (`enhances`): the medium (role `media`), the proxy's
medium (`proxy`), the data text (`data`). Stamp: `authored`.

### 3.3 Compositions and layers

**`core.motion.comp`** - node id `comp-<id>`; file `comps/comp-<id>/comp.json`. One
composition: `{schema_version, id, name, label, comment, parent, proxy, comp, layers, tracks}`.

* `comp` holds the composition's own settings: `width`, `height` (pixels), `pixel_aspect`,
  `frame_rate` (`{num, den}`), `duration`, `display_start`, `background`, `work_area`, the
  motion-blur settings (section 6.6), the switches, `markers`, `renderer` (`Classic3D` or
  `Advanced3D`), `global_light`, `guides`, `essential` (the controls it exposes to compositions
  that nest it), `resolution`.
* `layers` is `[{id, node}]`: the layers in STACKING ORDER, FRONT FIRST. `layers[0]` is drawn
  last, on top. The layer nodes are found through this list.
* `tracks`, when present, names the composition's own `core.keyframe.tracks` node (the
  keyframes of `global_light`).

Edges (`enhances`): each layer node (role `layer`), its tracks node (`keyframes`), its proxy's
medium (`proxy`), and its derived nodes: baked expressions (`baked-expressions`), Lottie
(`lottie`), contact strip (`preview`). Stamp: `authored`.

**`core.motion.layer`** - node id `layer-<id>`; file `comps/comp-<owner id>/layer-<id>.json`.
One layer: `{schema_version, comp, layer, tracks}`. `comp` is the id of the composition the
layer is in (so the node is meaningful alone); `layer` is the layer (below); `tracks`, when
present, names the layer's `core.keyframe.tracks` node.

A layer has: `id`, `name`, `label`, `comment`; `source` - what it shows, `{"type": ...}` with
`item` for `Footage`, `Comp`, `Solid` and `Model`, `kind` for `Light` and `Primitive`:

| `source.type` | the layer shows | size of its picture in layer pixels |
|---|---|---|
| `Footage` | a frame of footage item `item` | the item's `width` x `height` |
| `Comp` | a frame of composition `item`, nested | that composition's size |
| `Solid` | the colour of solid item `item` | the solid's size |
| `Text` | the text of property group `text` | none: the text lies around the layer origin |
| `Shape` | the shapes of property group `contents` | none: around the layer origin |
| `Null` | nothing (it exists to be a `parent`) | 100 x 100 |
| `Camera` | nothing; it is the view of 3D layers | - |
| `Light` | nothing; `kind`: `Parallel`, `Spot`, `Point`, `Ambient`, `Environment` | - |
| `Model` | a 3D model (footage item `item` of kind `Model`) | - |
| `Primitive` | a parametric solid; `kind` is its shape | - |

then its timing: `start_time`, `in_point`, `out_point`, `stretch` (section 6.2); `switches`;
`blend_mode` (section 6.9); `preserve_transparency`, `track_matte` (section 6.11); `parent`
(section 6.7); `markers`; `auto_orient`; and `props`, the root of its property tree (3.4).

Edges (`enhances`): the node of its source item (role `source`: `item-<id>` or `comp-<id>`),
its tracks node (`keyframes`), every file its effect parameters name (`file`). Stamp:
`authored`.

WHY ONE NODE PER LAYER. A layer is the unit a person edits and the unit that can be lost alone:
a reader that cannot parse one layer shows the composition without it. And a Save after an edit
to one layer stores one small file.

### 3.4 The property tree

Everything about a layer that can be animated is a PROPERTY in a tree of GROUPS.

A group is `{"node": "Group", uid, match, name, enabled, kind, children}`; the root of a layer
(`layer.props`) is a group without the `node` key whose `match` is `layer`. A property is
`{"node": "Prop", uid, match, name, value, keys | track, expr, ui, spatial, ...}`.

* `match` says what the node IS within its parent: a reader finds things by `match`, never by
  `name` (a display string a person may change) and never by position. Among the children of a
  group, `match` values are unique except in the lists a person orders - masks, effects, shape
  items, text animators - where order is the meaning.
* `uid` is the node's id in the project: unique, never reused, unchanged by rename and reorder.
  Expressions, baked tracks and essential-property links name a property by `uid`.
* `value` is the static value, a tagged pair `{"t": kind, "v": ...}`:

| `t` | `v` | interpolates between keys |
|---|---|---|
| `Scalar` | a number | yes |
| `Vec2` | `[x, y]` | yes |
| `Vec3` | `[x, y, z]` | yes |
| `Color` | `[r, g, b, a]`, straight alpha, nominal 0..1 | yes |
| `Bool` | `true` / `false` | no |
| `Enum` | an integer: the 0-based index of the choice | no |
| `Path` | a Bezier path (below) | yes, when both keys have the same number of vertices |
| `Gradient` | `{colors: [[pos, [r,g,b,a]]...], opacities: [[pos, a]...]}` | yes, when both keys have the same number of stops |
| `Text` | a text document (section 6.17) | no |
| `Layer` | the id of a layer of the same composition, or null | no |
| `Str` | a string | no |
| `File` | `{node, origin}`: a file in this package (section 3.6) | no |

* A property is ANIMATED when it has keyframes: either `keys` (inline, the full keyframe objects
  of the schema) or `track` (an index into the owner's tracks node, section 3.5) - never both.
  Its value at a time is then section 6.3; otherwise it is `value`.
* `expr`, when present, is `{text, enabled}`: an expression (section 6.18).
* `ui` says how an editor presents the property (a slider's range, a popup's option names). It
  never changes what the value means - except that a `Popup`'s `options` are the names of an
  `Enum`'s indices, and `File` marks a `File` value.

A PATH is `{vertices, in_tangents, out_tangents, closed, feather}`: tangents are RELATIVE to
their vertex. Segment i runs from `vertices[i]` to `vertices[i+1]` as the cubic Bezier with
control points

    P0 = vertices[i]
    P1 = vertices[i] + out_tangents[i]
    P2 = vertices[i+1] + in_tangents[i+1]
    P3 = vertices[i+1]

and a closed path has one more segment from the last vertex to the first. A segment whose two
tangents are both zero is a straight line.

The groups of a layer's root, by `match` (each present only where the table says):

| `match` | on | holds |
|---|---|---|
| `transform` | every layer | `anchor`, `position`, `scale`, `orientation`, `rotationX`, `rotationY`, `rotation`, `opacity` (section 6.7); cameras and lights have `poi` and no `anchor`, `scale`, `opacity` |
| `masks` | layers with a picture | one child group per mask, `kind.kind` = `Mask` (section 6.10) |
| `effects` | layers with a picture, and null layers | one child group per effect instance, `kind` = `{"kind": "Effect", "effect": <effect id>}` (section 6.12) |
| `contents` | shape layers | the shape items (section 6.16) |
| `text` | text layers | `sourceText` and the animators (section 6.17) |
| `cameraOptions`, `lightOptions` | cameras, lights | zoom, depth of field; intensity, colour, cone, shadows |
| `materialOptions`, `geometryOptions` | layers that can be 3D | how the layer takes light; extrusion (not defined here, section 8) |
| `layerStyles` | layers with layer styles | drop shadow, glow, bevel, stroke... (not defined here) |
| `essential` | layers whose source is a composition | one property per control the nested composition exposes (section 6.13) |
| `audio` | layers with sound | `levels` |

A root-level PROPERTY with `match` `timeRemap` exists when time remapping is on (section 6.2).
With separated position dimensions, `transform` also has `positionX`, `positionY`,
`positionZ` (Scalar each); when `positionX` exists, the layer's position is
`[positionX, positionY, positionZ]` and `position` is not used.

A reader that meets a group or property `match` it does not know skips that node and keeps the
rest of the layer; a writer that rewrites the layer keeps the node.

### 3.5 Keyframe tracks

**`core.keyframe.tracks`** - node id `layer-<id>-keys` (a layer's) or `comp-<id>-keys` (a
composition's own); file `comps/comp-<id>/layer-<id>.keys.wkx` or `comps/comp-<id>/comp.keys.wkx`.
The keyframes of every property of ONE owner whose keys are all finite numbers of one kind
(Scalar, Vec2, Vec3 or Color), as flat little-endian arrays in a werk envelope. Layout, with an
annotated dump of a real file: `spec/layouts/core.keyframe.tracks.layout.txt`.

The owner's JSON says `"track": i` on such a property, and names the node in its top-level
`tracks` field; track `i` of the file holds exactly the fields an inline keyframe has (time,
value, the two interpolations, the eases, the spatial tangents, the flags, the label), so the
two spellings carry the same information and a writer may use either for any property. The
writing application uses a track whenever it can and inline `keys` for the kinds a track cannot
hold (Path, Gradient, Text, Bool, Enum, Layer, Str) and for a key whose numbers are not finite.

Edge: the tracks node `requires` its owner (role `animates`): keyframes without the property
they belong to mean nothing. The owner `enhances` the tracks node (role `keyframes`). When the
tracks node is dead and the owner is alive, the properties that name a track have their static
`value` (the animation is lost, the layer is not), and a reader says so. Stamp: `authored`.

### 3.6 Media

Every file the project uses is IN the capsule, once: a medium used by ten items is one node.
There is no link to a file outside the package; `origin` strings are notes for a person.

A footage item names its medium by `media`: `{"node": <node id or null>, "origin": <the path
the file had when it was imported>, "frame_origins": [...]}`. `node` null means the file was
not available when the project was saved: the item is OFFLINE, a reader shows a placeholder and
names the item and its `origin`. An effect parameter that names a file names it the same way:
`{"t": "File", "v": {"node": ..., "origin": ...}}`. That is every parameter whose `ui.kind` is
`File`, and the text parameters the writing application reads a file name from (Lumetri Color's
Input LUT File and Look File, the Mocha shape data); the same parameter HOLDING the file's
text - a value with a line break, `.cube` text, JSON - stays a `Str` and is complete as it is.
A file that names further files travels with them: a medium node's files with role
`dependency` are the files its main file names, at the relative paths it names them by - the
buffers, textures and material libraries of a 3D model, and the look-up tables an OpenColorIO
configuration finds on its search path inside its own folder. What such a file names outside
its folder cannot travel and is reported by name when the project is saved.

The node id of a medium comes from its content: `media-` + the first 20 hexadecimal digits of
the sha256 of the file (for several files: of the sha256 of the concatenation of their 32-byte
digests in order). Its files are `media/<node id>/<name>`, `<name>` being the file's own name
with every character outside `A-Z a-z 0-9 . _ -` replaced by `_`; the original name is in
`meta.file_name`.

Which type carries a medium is decided by what the bytes ARE:

| the file is | type | definition |
|---|---|---|
| a PNG (every file of it) | `core.media.png` | MINI-SPECS.md section 8 |
| in a format the shared definition library defines (`meta.payload_format` names it) | `core.media.source` | `spec/formats/<id>.md`, carried with the capsule |
| UTF-8 text with one of the extensions `svg`, `obj`, `mtl`, `gltf`, `ocio`, `csp`, `cc`, `ccc`, `cdl`, `spi1d`, `spi3d`, `spimtx`, `json`, `csv`, `tsv`, `txt` | `core.media.text` | the text is readable; what it means is NOT defined here (section 8); `meta.text_format` names the public format |
| UTF-8 text with the extension `cube` or `3dl` | `core.color.lut` | section 6.15 |
| anything else, or a 3D model with files beside it | `x.effectcraft.media` | none: opaque bytes, byte for byte |

The definition library of this build defines, for media: `wav`, `aiff`, `flac`, `mp3`, `mpa`, `aac`, `ogg`, `ac3`, `jpeg`, `tiff`, `bmp`, `gif`, `webp`, `isobmff`, `matroska`, `avi`, `mxf`, `mpegts`, `psd`, `pdf`. A capsule carries
only the definitions of the formats its nodes are in.

`meta` of a media node: `media_kind` (`movie`, `audio`, `still`, `image-sequence`, `model`,
`data`, `lut`, `file`, `unknown`), `file_name`, `extension`, `media_type`, `codec` (the label the
importing program reported), `files` (how many), and `payload_format` / `text_format` as above.

A movie or sound file is a CONTAINER: `payload_format` names the container's definition, and
`contained_formats` (an array of format ids, each a key of the manifest's `formats`) names the
formats of the streams inside it, as far as the importing program named them and this build
defines them: `h264`, `hevc`, `prores`, `dnx`, `mjpeg`, `vp8`, `apv`, `aac`, `opus`, `mp3`, `ac3`, `flac`. In this revision that is ONE stream per file - the picture
stream, or the sound stream of a file without picture; the sound stream of a movie is not
named. A stream that is not listed is in a format the writer did not name: `codec` still says
what the importer called it, and nothing is claimed about its definition.

An IMAGE SEQUENCE is one node with one file per frame: the payload file is frame 0 and the
files with role `frame` follow in the order the manifest's `files` lists them, which is playing
order. Frame i of the sequence is file number i. `frame_origins` gives, as notes, the path each
frame had.

A 3D MODEL whose main file names other files (buffers, textures, material libraries) is one
node: the files with role `dependency` sit at the relative paths the main file names them by,
under `media/<node id>/`.

Stamp: `authored` (an imported original, proxies included: nothing in the document records how
a proxy was made). No edges.

### 3.7 Lookup tables, fonts, data

**`core.color.lut`** - node id `lut-<20 hex digits of its sha256>`; file `luts/<node id>.<ext>`.
A lookup table an effect parameter names, as text; `meta` = `{lut_format: "cube" | "3dl",
file_name}`. Section 6.15 defines both formats.

**`core.text.font`** - node id `font-<20 hex digits>`; file `fonts/<node id>/font.<ttf|otf|ttc>`.
One font FILE, byte for byte, never subsetted; `meta` = `{family, style}` of the face the
writer resolved. The structure node's `fonts` table lists every face a text layer names with a
`status`:

* `embedded` - the file is in the capsule; `node` names it;
* `restricted` - the saving computer had the font and the font's own licence bits forbid
  passing it on: OS/2 `fsType` has bit 1 set (value 2) and neither bit 2 nor bit 3
  (`spec/formats/sfnt.md`). In a collection, one such face restricts the file;
* `missing` - the saving program had no font file for the face.

A reader draws a face that is not embedded with a substitute and SAYS which faces it
substituted.

**`core.motion.data`** - node id `data-<20 hex digits>`; file `data/<node id>.<json|csv|tsv>`.
The text of a data footage item (which expressions read), byte for byte; `meta.data_format`
says which of the three it is. The item's `data` field names the node.

### 3.8 The effect catalog and the expression language

**`core.effect.catalog`** - node id `effect-catalog`; file `effects/catalog.json` (the
payload) and, when the catalog defines an effect, `effects/effects_ref.py` (role
`reference-source`: program text carried as a reference, never run by reading). What the
effect ids and blend-mode words of this document MEAN (section 6.12): for every effect id an
effect group of the document uses, its parameter schema and - where this profile defines the
effect - its arithmetic with test vectors, together with the words that arithmetic is written
in (`primitives`, `sections`); and the formula of every blend mode. Stamp: `authored`.

**`core.expr.language`** - node id `expr-language`; files `expressions/language.json` (the
payload) and `expressions/prelude.js` (role `reference-source`). The definition of the
language expressions are written in (section 6.18). Present when any property of the document
has an expression. The second file is program text carried as a reference: NOTHING runs it
because it is in the file. Stamp: `authored`.

### 3.9 Derived nodes

Everything in this section is computed from the document by the writing application and is
stamped `measured`: the version's `input_files` lists, in order, the PATHS of the payload
files it was computed from, `input_params` says with which settings, and `input_hash` is the
sha256 over the sha256 values those files had at that moment (each as 32 raw bytes, in that
order) followed by the canonical JSON of `input_params` (CRAFT-BASE.md section 5). A reader
recomputes the hash from the files the CURRENT document has under those paths: when it differs
the node is STALE - it describes an earlier revision. A reader uses a stale preview as a
picture of the past, and does NOT use stale baked values or a stale Lottie file as the
document. Each derived node `requires` each input node (role `derived-from`); `enhances`
instead when the input is an `x.*` node.

* **`core.expr.baked`** (node id `comp-<id>-baked`, file `expressions/comp-<id>.baked.wkx`) and
  **`core.expr.baked-values`** (`comp-<id>-baked-values`,
  `expressions/comp-<id>.baked-values.json`): the evaluated values of the expression-driven
  properties of one composition, section 6.18.4.
* **`core.motion.lottie`** (`comp-<id>-lottie`, `lottie/comp-<id>.json`): the composition
  exported as a Lottie animation (the open JSON animation format of the Lottie Animation
  Community), for players that read Lottie. The payload IS the Lottie file: its outermost keys
  are Lottie's own (`v`, `fr`, `ip`, `op`, `w`, `h`, `layers`...). It is a SECOND MASTER, not
  the document: Lottie cannot express everything, and `meta.not_expressed` lists, one sentence
  each, what of this composition it left out. The Lottie format is not defined in this package
  and nothing of the document depends on this node.
* **`core.preview.poster`** (`preview-poster`, `preview/poster.png`): one frame of the MAIN
  composition: the one that was in front in the editor when the file was saved; else the
  composition with the lowest id that no composition nests; else the composition with the
  lowest id. The frame is the one containing the composition's `poster_time` when that lies
  strictly inside the composition, else the one containing a third of its duration. 8-bit RGB;
  the picture has the composition's display shape (width * pixel_aspect : height) with the
  longer side at most 480 pixels.
* **`core.preview.strip`** (`preview-strip-<comp id>`, `preview/strip-<comp id>.png`): eight
  frames of one composition side by side, each 90 pixels high: the frames containing the times
  duration * (2 i + 1) / 16 for i = 0..7, left to right.
* **`core.preview.proxy`** (`preview-proxy`, `preview/proxy.wkx.zlib`): the start of the main
  composition as up to 36 frames, 90 pixels high, raw RGB: every `step`-th composition frame
  from frame 0, `step` = max(1, round(frames per second / 12)). The payload is ONE zlib stream
  (RFC 1950, `spec/formats/zlib-deflate.md`) that inflates to a werk envelope; `meta` gives the
  inflated size and sha256. Layout of the inflated bytes and a dump:
  `spec/examples/motion-comp/core.preview.proxy.layout.txt`.

Preview pictures are the composition over black, in the project's output encoding.

### 3.10 What only the writing application interprets

* **`x.effectcraft.media`** - a medium in a format this package has no definition of (section
  3.6). The bytes are intact and hash-listed; a reader that knows the format from elsewhere
  (`meta.extension`, `meta.codec` are hints) may use them. `spec/layouts/x.effectcraft.media.layout.txt`
  says what is and is not known about such a payload.
* **`x.effectcraft.view`** - node id `view`: which composition was in front in the editor and
  which were open. No effect on the document.
* **`x.effectcraft.plugin-state`** - node id `plugin-<slug of the effect id>`: what the saving
  host knew about one third-party effect plug-in (section 6.14).

### 3.11 When a node is dead, missing or unknown

A reader verifies what it reads (SPEC.md section 10). A node whose file is missing, fails its
hash, fails its schema or layout, or is of a type or schema revision the reader does not know,
is DEAD FOR THAT READER; every other node is unaffected. What the reader then does:

| dead node | the reader |
|---|---|
| `project` | rebuilds a project from the item, composition and layer nodes it finds in the manifest (by type): every item in the root, default settings, no folders. It says the settings and folders are lost. |
| an item | draws nothing for the layers that use it, and names the item |
| a composition | drops it; layers that nest it show nothing; names it |
| a layer | shows the composition without that layer; layers parented to it are placed as if unparented; a layer whose track matte it was is drawn unmatted; names the layer |
| a tracks node | uses the static `value` of the properties that named a track; names the owner |
| a medium, a font, a lookup table, a data text | treats it as not embedded: placeholder, substitute font, the effect without its table |
| the effect catalog | still has every parameter value; knows no meaning of the effect ids beyond what it implements itself |
| the language node | still has every expression's text, and the baked values |
| baked values, Lottie, previews | does without |
| any `x.*` node, any unknown type | skips it; a writer that saves the capsule again KEEPS it, byte for byte |

A reader reports each dead node once, with its reason code, and exits with the status SPEC.md
section 10.1 gives (1 when something was lost, 2 when the container itself was refused).

## 4. Versions

The rules are CRAFT-BASE.md sections 3 and 4; this section says what a Save of this profile
appends.

EVERY SAVE IS A REVISION. A Save appends one version to the node `revisions`: a record with the
revision number, `kind` (`save`), the time, the producer, a WORK NOTE - one sentence saying why
this revision exists - and `nodes`, the map from node id to the version of that node the
document uses at this revision. The note is mandatory: a person supplies it, or the writer
generates a truthful one from what changed (`Changed 1 layer of composition "Stage"; embedded 1
media file (15404 bytes)`). A note of fewer than 8 characters is refused.

What gets a new version in a Save:

* a layer node, a tracks node, an item node, a composition node, the queue: when its payload
  bytes differ from the version the last revision used. A unit that did not change is NOT
  stored again: the new revision's record names the version it already had;
* the `project` node: when the settings, the folders or one of its tables changed;
* a new unit: a new node. A unit that is gone: no entry in the new revision's record. Its
  bytes stay in the file - earlier revisions use them - and a node id is never given to
  another unit;
* a medium: never. A medium is immutable; "replacing footage" is a new node (its id comes from
  its content) and a new version of the item that names it;
* derived nodes (previews, baked values, Lottie): when a program that can compute them saves
  and their inputs changed. A Save by a program that cannot keeps the existing versions; they
  are then stale and say so by their `input_files` (section 3.9).

THE DOCUMENT AT REVISION K is read as CRAFT-BASE.md section 3 says: record K of `revisions`,
and each node at the version that record names. Opening an earlier revision changes nothing in
the file. RESTORING revision K appends a new revision (`kind` `rollback`, `restores` K) whose
`nodes` equal record K's: nothing is deleted, and the revisions in between stay readable.

AUTOSAVE. A revision whose note begins with the word `Autosave` was written by the application
on a timer, not by a person's Save. It is an ordinary revision in every other respect. A
history listing may show such revisions folded under the next revision a person made; no
reader may treat them as less real - they are the only record of the work between two Saves.

COMPACTION is the only operation that removes bytes, and it is explicit: it drops the payload
files of versions that no revision at or after a chosen revision uses, marks those versions
`compacted` in the manifest with the reason, and appends a revision of `kind` `compaction`
whose note says how many files and bytes were dropped. Media that the kept revisions do not
use go with them.

SIGNATURES. `SIGNATURE.json` signs the manifest (CRAFT-BASE.md section 7). A Save by someone
who does not sign leaves the chain intact and the newest manifest unsigned: a reader reports
`present-and-invalid` for the manifest it has and can still verify every earlier link.

## 5. Conventions

Every value below is a machine value in `MANIFEST.json` -> `conventions`, pinned by the
manifest schema; `spec/conventions-map.motion-comp.json` is the machine-readable form of the
"governs" column. Type names are shortened by dropping `core.` (`motion.layer` is
`core.motion.layer`). A reader that does not implement a node-scoped value refuses the node
types it governs and keeps everything else.

| convention | value | governs | scope | meaning |
|---|---|---|---|---|
| `endianness` | `"le"` | keyframe.tracks, expr.baked, embedding, x.* | node | Every envelope binary is little-endian. MessagePack header integers inside an envelope are big-endian by MessagePack's own definition (spec/layouts/ENVELOPE.layout.txt section 4). |
| `alignment_bytes` | `16` | keyframe.tracks, expr.baked, embedding, x.* | node | Payload sections of envelope binaries start on this boundary. |
| `text_encoding` | `"utf-8"` | * | container | Every text and JSON payload, INCLUDING MANIFEST.json - which is why the scope is container. |
| `id_case` | `"kebab-case"` | * | container | Every id matches ^[a-z0-9]+(-[a-z0-9]+)*$. |
| `hash_algorithm` | `"sha256"` | * | container | Every files[].sha256, every input_hash, license.sha256, and spec_sha256. |
| `signature_algorithm` | `"ed25519"` | - | signature | SIGNATURE.json only. Refusing it is the 'unverified' state, not damage. |
| `ticks_per_second` | `254016000000` | motion.project, motion.item, motion.comp, motion.layer, motion.render-queue, keyframe.tracks, expr.baked, expr.baked-values | node | Every instant and length is an integer count of ticks; 254 016 000 000 ticks are one second. One frame at num/den fps is 254016000000 * den / num ticks (exact for every broadcast rate). |
| `time_origin` | `0` | motion.project, motion.item, motion.comp, motion.layer, motion.render-queue, keyframe.tracks, expr.baked, expr.baked-values | node | Tick 0 is the start of a composition (composition time), the layer's own zero (layer time) or the first frame of a medium (source time). Instants may be negative. |
| `range_form` | `"half-open"` | motion.project, motion.item, motion.comp, motion.layer, motion.render-queue, keyframe.tracks, expr.baked, expr.baked-values | node | A range [start, end) holds start and excludes its end: a layer is active for in_point <= t < out_point, a composition has frames for 0 <= t < duration. |
| `frame_start_rounding` | `"ceiling"` | motion.comp, motion.layer, expr.baked, expr.baked-values | node | Frame f of a rate num/den starts at tick ceil(f * 254016000000 * den / num). |
| `frame_index_rounding` | `"floor"` | motion.comp, motion.layer, expr.baked, expr.baked-values | node | The frame containing tick t is floor(t * num / (254016000000 * den)). |
| `keyframe_time` | `"layer"` | motion.comp, motion.layer, keyframe.tracks | node | Keyframe times are LAYER time: composition time minus the layer's start_time, divided by stretch / 100 (profile document 6.2). The keyframes of a composition's own properties (the global light) are composition time. |
| `layer_time_rounding` | `"truncate"` | motion.comp, motion.layer, keyframe.tracks | node | Layer time of a stretched layer: (t - start_time) * 100 / stretch computed in binary64 and truncated toward zero to an integer tick. With stretch exactly 100 it is the integer t - start_time. |
| `keyframe_extrapolation` | `"hold"` | motion.comp, motion.layer, keyframe.tracks | node | Before the first keyframe a property has the first keyframe's value, after the last the last's. |
| `temporal_ease_model` | `"speed-influence"` | motion.comp, motion.layer, keyframe.tracks | node | A Bezier side of a key is given by a speed (value units per second) and an influence (fraction of the segment's duration): profile document 6.3. |
| `ease_default_speed` | `0.0` | motion.comp, motion.layer, keyframe.tracks | node | The speed of a Bezier side that has no stored ease: 0. |
| `ease_default_influence` | `0.16666666666666666` | motion.comp, motion.layer, keyframe.tracks | node | The influence of a Bezier side that has no stored ease: 1/6. (Profile timeline/1 uses 1/3 for its own, different, ease model.) |
| `ease_influence_clamp` | `[0.0,1.0]` | motion.comp, motion.layer, keyframe.tracks | node | An ease influence is clamped to this range before use. |
| `linear_side_influence` | `0.3333333333333333` | motion.comp, motion.layer, keyframe.tracks | node | A Linear side that meets a Bezier side in one segment acts as an ease along the straight segment with this influence (1/3). |
| `spatial_auto_tangent_divisor` | `6` | motion.comp, motion.layer, keyframe.tracks | node | An automatic spatial tangent of key i is (value[i+1] - value[i-1]) / 6 (out) and its negative (in); an end key uses itself for the missing neighbour. |
| `spatial_arc_table_cells` | `96` | motion.comp, motion.layer, keyframe.tracks | node | Arc length along a spatial segment is tabulated at 96 equal parameter steps, each cell integrated by 5-point Gauss-Legendre quadrature (profile document 6.4). |
| `stretch_unit` | `"percent"` | motion.layer | node | A layer's `stretch`: 100 = normal speed, 200 = half speed, negative = reversed. |
| `time_remap_unit` | `"second"` | motion.layer | node | The value of a layer's `timeRemap` property is source time in seconds (binary64); it is converted to ticks by round(seconds * 254016000000), halves away from zero. |
| `shutter_unit` | `"degree-of-frame"` | motion.comp | node | Shutter angle and phase are in degrees of one frame: 360 = one frame duration. |
| `pixel_origin` | `"top-left"` | motion.comp, motion.layer, motion.item, effect.catalog | node | Pixel coordinates have their origin at the top-left corner of the frame or picture; x grows to the right, y DOWNWARD. The centre of the top-left pixel is (0.5, 0.5). |
| `angle_unit` | `"degree"` | motion.comp, motion.layer, motion.item, effect.catalog | node | Angles are in degrees. |
| `angle_direction` | `"clockwise"` | motion.comp, motion.layer, motion.item, effect.catalog | node | A positive angle turns clockwise on screen (from +x towards +y, y being down). |
| `handedness` | `"left"` | motion.comp, motion.layer, motion.item, effect.catalog | node | 3D space is left-handed: +x right, +y down, +z INTO the screen (away from the viewer). |
| `transform_order` | `["anchor","scale","rotate-x","rotate-y","rotate-z","orientation","position"]` | motion.comp, motion.layer, motion.item, effect.catalog | node | A layer point p becomes parent-space P = T(position) * O(orientation) * Rz * Ry * Rx * S(scale / 100) * T(-anchor) * p; a 2D layer has only Rz (`rotation`), no orientation, and z scale 1 (profile document 6.7). |
| `scale_unit` | `"percent"` | motion.comp, motion.layer, motion.item, effect.catalog | node | Scale values: 100 = unscaled. |
| `opacity_unit` | `"percent"` | motion.comp, motion.layer, motion.item, effect.catalog | node | Opacity values: 100 = opaque, 0 = transparent. |
| `layer_order` | `"first-is-front"` | motion.comp | node | `layers[0]` of a composition is the FRONT (top) layer; layers are composited from the last to the first. |
| `compositing_space` | `"working-encoding-premultiplied"` | motion.comp, motion.layer, motion.item, effect.catalog | node | Layers are composited as premultiplied RGBA, binary32, in the ENCODING of the working space (not linearised) unless the project's `linearize` or `blend_linear` says otherwise (profile document 6.8). |
| `color_value_encoding` | `"authored-straight"` | motion.comp, motion.layer, motion.item, effect.catalog | node | A colour value is [r, g, b, a] in 0..1, straight (not premultiplied) alpha, in the working space's encoding as authored (sRGB-encoded when there is no working space). |
| `luminance_weights` | `[0.2126,0.7152,0.0722]` | motion.comp, motion.layer, motion.item, effect.catalog | node | Luminance of a colour for mattes, stencils and effects: 0.2126 r + 0.7152 g + 0.0722 b (binary32). |
| `blend_lum_weights` | `[0.3,0.59,0.11]` | effect.catalog, motion.layer | node | Lum() of the Hue, Saturation, Color and Luminosity blend modes: 0.3 r + 0.59 g + 0.11 b. |
| `quantization_levels_8bpc` | `255` | motion.comp, motion.layer, motion.item, effect.catalog | node | In an 8 bits per channel project: after a layer's source and masks, after each effect, and after each layer is blended, every pixel is clamped (alpha to 0..1, colour to 0..alpha) and each component rounded to a multiple of 1/255, halves up. |
| `quantization_levels_16bpc` | `32768` | motion.comp, motion.layer, motion.item, effect.catalog | node | In a 16 bits per channel project: the same with multiples of 1/32768. In a 32 bits per channel project nothing is clamped or rounded. |
| `mask_feather_sigma` | `"feather/2"` | motion.layer | node | A Smooth mask feather of f pixels is a Gaussian blur of the coverage with standard deviation f / 2 per axis. |
| `matte_luminance_of` | `"premultiplied"` | motion.layer | node | A luma matte takes the luminance of the matte layer's PREMULTIPLIED colour. |
| `json_integer_width` | `64` | * | node | Integers in JSON payloads are exact and may need 64 bits (signed for times, unsigned for ids); a reader must not pass them through binary64. |
| `json_binary32` | `"widened-binary64"` | * | node | A binary32 quantity (a solid's colour, a gradient stop, a text fill) is written as the shortest decimal of the binary64 number equal to it; narrowing what is read to binary32 gives the exact value. |
| `json_spelling` | `"canonical"` | * | node | JSON payloads this writer makes are one line: keys sorted by their UTF-8 bytes, no whitespace, one line feed at the end. Any JSON spelling that satisfies the schemas is valid. |
| `text_index_unit` | `"unicode-scalar-value"` | motion.layer | node | Character counts of text runs count Unicode scalar values (code points), not bytes or UTF-16 units. |
| `baked_sample_instant` | `"frame-start"` | expr.baked, expr.baked-values | node | Sample i of a baked track is the property's value at the start tick of composition frame first_frame + i * frame_step. |
| `baked_max_samples` | `3600` | expr.baked, expr.baked-values | node | A baked track has at most this many samples: frame_step is the smallest integer that keeps it so. |
| `preview_pixel_format` | `"srgb-rgb8"` | preview.poster, preview.strip, preview.proxy | node | Preview pictures are 8-bit, opaque, in the project's output encoding (sRGB unless the project names another output space), composited over black; row 0 is the top row. |
| `poster_max_side` | `480` | preview.poster | node | The longer side of the poster is at most this many pixels. |
| `strip_frames` | `8` | preview.strip | node | A contact strip holds this many frames, at times duration * (2 i + 1) / 16 for i = 0..7, left to right. |
| `strip_frame_height` | `90` | preview.strip | node | Height of a contact strip and of each of its frames, pixels. |
| `proxy_max_frames` | `36` | preview.proxy | node | The preview proxy holds at most this many frames. |
| `proxy_frame_height` | `90` | preview.proxy | node | Height of a preview proxy frame, pixels. |

### 5.1 Relation to profile `timeline/1`

`timeline/1` (an edit of clips on tracks) is the nearest profile. What is THE SAME, so that one
implementation serves both:

* the tick: 254 016 000 000 per second, signed 64-bit; frame start = ceiling, frame index =
  floor; ranges half-open (conventions `ticks_per_second`, `frame_start_rounding`,
  `frame_index_rounding`, `range_form`);
* picture space: origin top-left, x right, y down, pixel centres at half-integers, angles in
  degrees clockwise, luminance weights 0.2126 / 0.7152 / 0.0722;
* media: one node per distinct medium, id from the content hash, the types `core.media.source`
  and `core.media.png`, the `meta` fields `media_kind`, `file_name`, `extension`, `media_type`,
  `files`, `payload_format`; `core.color.lut`; `core.text.font`; `origin` as a note;
* the derived previews: `core.preview.poster`, `core.preview.strip`, `core.preview.proxy` with
  the same sizes, times and the same envelope (`WKX2`) inside the zlib stream;
* the node types `core.effect.catalog` (a catalog of the effect ids a document uses, with
  parameter schemas, definitions and test vectors) and `x.<app>.plugin-state`, and the rule for
  third-party plug-ins (section 6.14).

What DIFFERS, and why:

* **Keyframes.** A `timeline/1` key has one interpolation word for the segment leaving it and
  two ease INFLUENCES; its Bezier segment is a timing curve from (0, 0) to (1, 1) with control
  points (out_influence, 0) and (1 - in_influence, 1) - an ease always starts and ends at zero
  speed. A key of this profile has, per side and per dimension, a SPEED (value units per
  second) and an influence, and for a motion path spatial tangents and an ease along the arc
  length: the model these documents are authored in, which the other cannot hold. Hence a node
  type of its own, `core.keyframe.tracks` (envelope `WKX3`), beside `timeline/1`'s
  `core.keyframe.curves`. The mapping is exact in one direction: a `timeline/1` Bezier segment
  is a segment of this profile whose two Bezier sides have speed 0 and the same influences
  (its Linear side beside a Bezier side is this profile's rule too: section 6.3), with these
  differences in the conventions: an absent influence is 1/3 there and 1/6 here
  (`ease_default_influence`); influences are clamped to 0.01..1 there and to 0..1 here.
* **Keyframe time.** Here keyframe times are LAYER time (they move with the layer). In
  `timeline/1` a clip's keyframes are media time of the clip's source.
* **Compositing space.** `timeline/1` composites in linear light and computes its blend modes
  on sRGB-encoded colour. This profile composites in the ENCODING of the working space unless
  the project asks for linear blending (section 6.8), and computes blend modes in the space it
  composites in.
* **Layer order.** `timeline/1`: `video_tracks[0]` is the back. Here: `layers[0]` is the front.
* **Effects.** The catalogs have the same shape and the definition libraries the same form
  (section 6.12: primitives, sections, `exact` / `tolerance` / parameters-only, vectors over
  the same two patches). The effects themselves are not shared: the two applications compute
  them differently (here on the working-space numbers as they are, there on linear light with
  a display encoding inside most colour effects), so no id is shared. Every id of this profile
  begins with `ec.`; no `timeline/1` id does.
* **Blend modes.** This profile has 38 (section 6.9), `timeline/1` 27. Each profile states
  its formulas in full, and the frame around them (how a partly transparent source and backdrop
  combine); a mode of the same name is not assumed to be the same arithmetic.
* **Expressions, property trees, masks, mattes, 3D, shape and text layers** have no
  counterpart in `timeline/1`.

### 5.2 Relation to profile `vector-art/1`

A shape layer holds vector art, and `vector-art/1` defines node types for vector art
(`core.vector.layer`: a tree of objects with appearances). This profile does NOT store shape
layers in those types, for three reasons a converter must know:

1. Every number of a shape layer is a PROPERTY - a value with keyframes and possibly an
   expression. `vector-art/1` objects hold plain numbers.
2. A shape layer's contents are a STACK of items in which path operators (trim, repeat,
   merge...) act on the paths above them and paints paint the paths above them (section 6.16).
   `vector-art/1` has objects with their own geometry and appearance.
3. Conventions differ, exactly: (a) path handles here are RELATIVE to their vertex; there `in`
   and `out` are absolute: `in = vertex + in_tangent`, `out = vertex + out_tangent`. (b) Order:
   here the FIRST item of a list is in front; there the first is at the bottom. (c) Units: here
   composition pixels; there points (1/72 inch). (d) Colour: here `[r, g, b, a]` in the
   project's authored encoding; there a colour model object.

What does carry over one to one: path geometry (cubic Bezier anchors), the non-zero / even-odd
fill rules, stroke cap, join and miter limit, linear and radial gradients with stops.

### 5.3 Relation to profile `rich-document/1`

A text layer holds formatted text, and `rich-document/1` defines `core.text.blocks`. This
profile does NOT use it: the value of a text layer's `sourceText` is ONE text document that may
be keyframed as a whole (each key holds a complete document), with character formatting as
runs. The differences, exactly: (a) a run's length here counts Unicode scalar values
(convention `text_index_unit`); there UTF-8 bytes. (b) Sizes here are composition pixels;
there points. (c) Colours here are `[r, g, b, a]` binary32 0..1; there integers 0..255 without
alpha. (d) There are no stories, tables, lists or inline objects here.

What IS shared: `core.text.font` - one node per font file, byte for byte, never subsetted,
`meta.payload_format` `sfnt` - and the same licence rule for which font files may travel
(section 3.7).

## 6. Reading

`spec/examples/motion-comp/read_motion.py` (Python standard library only, no other software)
does what sections 6.0 to 6.11, 6.16 (fills of basic shapes) and 6.18.4 say: it lists a
capsule's compositions with their layer trees and animation, evaluates any property at any
time, computes layer matrices, reads baked expression values, and renders a frame of a
composition made of solids, masks and filled shapes. It is a reference, not a dependency: this
section is the definition, and the program is one implementation of it.

Notation: `TPS` = 254 016 000 000 (ticks per second). `floor`, `ceil`, `round` (to nearest,
halves away from zero), `clamp(v, lo, hi)`. Unless a formula says binary32, arithmetic is IEEE
754 binary64.

### 6.0 From MANIFEST.json to the project

1. Open the container (SPEC.md section 1) and parse `MANIFEST.json`. Check `profile` is
   `motion-comp/1`. Verify the signature if you were asked to (CRAFT-BASE.md section 7).
2. Find the current document: the record of the `revisions` node's `active` version
   (CRAFT-BASE.md section 3); its `nodes` map says which version of which node is in the
   document. (For revision K take record K instead; everything below is the same.)
3. Read the node named by `primary.document`: type `core.motion.project`. Verify its file's
   size and sha256 against the manifest, validate it against its schema. Do this for every
   payload you read; a node that fails is dead (section 3.11) and you go on.
4. For each entry of its `items`: read the node. `kind` `solid` / `footage`: a
   `core.motion.item` payload. `kind` `comp`: a `core.motion.comp` payload; for each entry of
   ITS `layers`, read the `core.motion.layer` node. If a composition or a layer payload has
   `tracks`, read that `core.keyframe.tracks` node and attach track i to the property that says
   `"track": i`.
5. Build the tree: an item's `parent` is a folder id or null. Layers are in the order of the
   composition's `layers` list: the first is in front.
6. For media: a footage item's `media.node` (and its proxy's) names the node holding the bytes;
   read those bytes only when you need pixels or sound.
7. Read `effect-catalog` to learn what the effect ids mean, and `expr-language` if you intend
   to evaluate expressions; otherwise read the baked values of the compositions you render.

That is the whole document. Nothing else in the file is needed to know what the project IS;
the derived nodes (previews, baked values, Lottie) are conveniences.

### 6.1 Time

Every instant and duration is an integer number of TICKS; `TPS` ticks are one second. A time in
seconds, where a formula needs one, is `ticks / TPS` in binary64.

A frame rate is `{num, den}` frames per second, both positive integers (25 fps is 25/1,
"29.97" is 30000/1001). At that rate:

    frame f starts at tick      ceil(f * TPS * den / num)          (exact integer arithmetic)
    the frame containing tick t is   floor(t * num / (TPS * den))

One 25 fps frame is 10 160 640 000 ticks; one 30000/1001 frame is 8 475 667 200 ticks. For
every rate whose `num` divides `TPS * den` the frame starts are exact.

A composition has frames 0 .. N-1 where N = (the frame containing tick `duration - 1`) + 1.
Frame f of a composition is the picture at COMPOSITION TIME `start(f)`: every property is
evaluated at that tick. A layer is ACTIVE at composition time t when `in_point <= t <
out_point`.

### 6.2 Layer time

Keyframes, layer markers and a layer's source move with the layer: their times are LAYER TIME.
For composition time t:

    stretch == 100 (within 1e-9):  layer_time = t - start_time                    (exact, integer)
    otherwise:                     layer_time = trunc((t - start_time) * 100.0 / stretch)

the product and quotient in binary64, `trunc` toward zero. `stretch` 200 plays at half speed; a
negative stretch runs layer time backward. Example: `start_time` = TPS (1 s), `stretch` = 200,
t = 2 TPS: layer_time = trunc(254016000000 * 100 / 200) = 127 008 000 000 (0.5 s).

A PROPERTY's value at composition time t is its keyframed value at `layer_time(t)` (sections
6.3, 6.4), then its expression if it has an enabled one (section 6.18). The keyframes of a
composition's own properties (`global_light`) are composition time.

SOURCE TIME - which instant of the layer's source (a footage frame, a nested composition's
time) is shown - is:

1. with a root property `timeRemap`: its value at t is source time in SECONDS;
   source_time = round(value * TPS);
2. else, for a layer whose source is a composition with PROTECTED REGIONS (markers of the
   nested composition with `protected` true and a positive `duration`) and whose `stretch` is
   not 100 and is positive: the protected regions play at their own speed and the rest absorbs
   the stretch. With D = the nested composition's duration in seconds, the regions merged and
   clamped to 0..D, P = their total length, U = D - P, s = stretch / 100,
   k = (D * s - P) / U (k = 1 when U <= 1e-9): if k <= 1e-9 this rule does not apply; else walk
   the nested composition from 0, each protected stretch lasting its own length and each other
   stretch lasting its length * k, until e = (t - start_time) / TPS seconds are used up; the
   source time is the point reached (before 0: e / k; past the end: D + the rest / k), converted
   with round(seconds * TPS);
3. else: source_time = layer_time(t).

For a layer whose source is a composition with `preserve_frame_rate` true, source time is then
floored to that composition's frame: start(frame containing source_time).

### 6.3 Keyframes: interpolation in time

A property with keyframes has keys k[0..n-1] in ascending `time` (no two equal). Its value at
layer time t:

    if n == 1 or t <= k[0].time:   k[0].value
    if t >= k[n-1].time:           k[n-1].value
    else, with i the largest index with k[i].time <= t, a = k[i], b = k[i+1]:
        if a.out_interp is Hold, or the kind does not interpolate (section 3.4):  a.value
        else                        segment(a, b, t)

A key has an interpolation word for each side: `in_interp` (arriving) and `out_interp`
(leaving), each `Linear`, `Bezier` or `Hold`; and per side a list of EASES `{speed, influence}`:
`speed` in value units per second, `influence` a fraction of the segment's duration. The ease of
key K on a side for dimension d is: if K has `auto_bezier` true and has a key on both sides,
`{speed: (next.value[d] - prev.value[d]) / max(next.time - prev.time, 1e-12 s), influence: 1/6}`;
otherwise entry d of that side's list, else entry 0, else `{speed: 0, influence: 1/6}`.

SEGMENT for the kinds Scalar, Vec2, Vec3, Color of a property that is NOT spatial (section
6.4), each dimension d on its own. With times in seconds (`ticks / TPS`):

    dur = max(tb - ta, 1e-12)
    x   = clamp((t - ta) / dur, 0, 1)
    lin_out = a.out_interp is Linear
    lin_in  = b.in_interp is not Bezier          (Linear or Hold)
    if lin_out and lin_in:   value[d] = a[d] + (b[d] - a[d]) * x
    else:
        dv = b[d] - a[d]
        (so, io) = (dv / dur, 1/3) if lin_out else the ease of a, out side, dimension d
        (si, ii) = (dv / dur, 1/3) if lin_in  else the ease of b, in side, dimension d
        io = clamp(io, 0, 1);  ii = clamp(ii, 0, 1)
        u = the solution in [0, 1] of  B(0, io, 1 - ii, 1; u) = x
        value[d] = B(a[d], a[d] + so * io * dur, b[d] - si * ii * dur, b[d]; u)

where B(p0, p1, p2, p3; u) = (1-u)^3 p0 + 3 (1-u)^2 u p1 + 3 (1-u) u^2 p2 + u^3 p3.

In words: the segment is a cubic Bezier curve in the (time, value) plane from (ta, a) to
(tb, b); its first handle leaves a with slope `so` and reaches `io * dur` forward in time, its
second arrives at b with slope `si` from `ii * dur` back. A Linear side beside a Bezier side
acts as an ease along the straight line with influence 1/3.

Solving for u: B(0, io, 1 - ii, 1; u) does not decrease as u grows, so the solution is unique
up to flat stretches. x <= 0 gives 0, x >= 1 gives 1. When io = 1 and ii = 1 exactly:
u = 0.5 + cbrt((x - 0.5) / 4). Otherwise any method that finds u to within 1e-12 conforms (the
writing application uses Newton's iteration from u = x, then bisection).

The result of `Bool` after interpolation does not arise (it does not interpolate); a `Color`
interpolates its four numbers; nothing is clamped.

PATH and GRADIENT values (kinds without numeric dimensions). When both sides are Linear the
progress is f = x. Otherwise f = E(so * dur, io, si * dur, ii, x) with the eases of dimension 0,
a Linear side having speed 1 / dur and influence 1/3, where

    E(os, oi, is, ii, x):  oi = clamp(oi, 0, 1); ii = clamp(ii, 0, 1)
                           u = the solution of B(0, oi, 1 - ii, 1; u) = x
                           return B(0, os * oi, 1 - is * ii, 1; u)

(here a speed is progress per second). Then: two paths with the same number of vertices
interpolate every vertex and every tangent linearly by f (`closed` is a's; feather points
interpolate when both have the same number, else a's until f reaches 1); two gradients with the
same numbers of colour and opacity stops interpolate every stop's position and value linearly
by f; in every other case the value is a's while f < 1 and b's from f = 1.

WORKED EXAMPLE 1 (checkable). The layer `Card` of the example project
(`spec/examples/motion-comp/stage.*`) has `opacity` with two keys:

    key 0: time 0,              value 100, out_interp Bezier, out_ease [{speed -10, influence 0.6}]
    key 1: time 406425600000,   value 40,  in_interp Bezier,  in_ease  [{speed -90, influence 0.2}]

dur = 1.6 s. The (time, value) curve has control points (0, 100), (0.96, 90.4), (1.28, 68.8),
(1.6, 40). Its value at ten times, as the writing application evaluates it (a conforming
evaluator agrees within 1e-9):

    tick             seconds   value
    0                0.0       100.0
    50803200000      0.2       97.71097246784096
    101606400000     0.4       94.73402149418061
    152409600000     0.6       90.84845137469367
    203212800000     0.8       85.7228768047363
    254016000000     1.0       78.84758164646463
    304819200000     1.2       69.45407017133107
    355622400000     1.4       56.5915902586642
    406425600000     1.6       40.0
    457228800000     1.8       40.0

### 6.4 Keyframes: motion paths

A property with `spatial` true whose kind is Vec2 or Vec3 moves along a PATH in space between
keys, and its eases act on the DISTANCE travelled along that path. (A Vec2 is treated as a Vec3
with z = 0 and gives a Vec2 back.) The value rule of section 6.3 holds up to "segment(a, b, t)";
the segment is:

1. THE PATH. The cubic Bezier with control points

       P0 = a.value
       P1 = a.value + T_out(a)
       P2 = b.value + T_in(b)
       P3 = b.value

   The spatial tangents of key number j: when its `spatial_auto` is false, `spatial_in` and
   `spatial_out` as stored. When true (the default): T_out = (v[min(j+1, n-1)] -
   v[max(j-1, 0)]) / 6 and T_in = -T_out - a sixth of the way from the previous key's value to
   the next one's, an end key standing in for its missing neighbour. (So two auto keys alone
   give a straight path.)

2. ITS LENGTH. Divide the parameter range 0..1 into 96 equal cells. The length of the cell
   [u0, u1] is the 5-point Gauss-Legendre rule applied to |dP/du|:

       m = (u0 + u1) / 2;  h = (u1 - u0) / 2
       cell = h * sum over the five (x, w) of  w * |P'(m + h * x)|
       (x, w) = (0, 0.5688888888888889), (-0.5384693101056831, 0.4786286704993665),
                (0.5384693101056831, 0.4786286704993665), (-0.906179845938664, 0.2369268850561891),
                (0.906179845938664, 0.2369268850561891)

   L = the sum of the 96 cells; table[i] = the sum of the first i cells.

3. PROGRESS f along the length. With x and dur as in section 6.3:
   * both sides Linear (as defined there), or L <= 1e-12:  f = x;
   * otherwise f = E(so * dur / L, io, si * dur / L, ii, x) (E as in section 6.3), the ease of
     a side being entry 0 of the key's list on that side - `speed` in PIXELS PER SECOND along
     the path - or, for a key with `auto_bezier` and a key on both sides, `{speed: |next.value -
     prev.value| / max(next.time - prev.time, 1e-12 s), influence: 1/6}` (Euclidean distance);
     a Linear side has speed L / dur and influence 1/3.

4. THE POINT.
   * When P1 and P2 both lie on the straight segment P0-P3 (for C in (P1, P2): with
     d = P3 - P0, w = C - P0, s = (w . d) / (d . d): 0 <= s <= 1 and |w - s d|^2 <=
     (d . d) * 1e-18; never when d . d <= 1e-24), the path is that segment:
     value = P0 + (P3 - P0) * f. f is NOT clamped here: an ease may overshoot.
   * Otherwise the point at arc length s = clamp(f * L, 0, L): find the cell i (1..96) with
     table[i-1] < s <= table[i] (the first cell whose end is not below s); start at
     u = u0 + (s - table[i-1]) / (table[i] - table[i-1]) * (u1 - u0) (u = u0 when the cell has no
     length); then up to four Newton steps u = clamp(u - e / |P'(u)|, u0, u1) with
     e = table[i-1] + (the Gauss-Legendre length of [u0, u]) - s, stopping when |P'(u)| <=
     1e-12 or, after a step, |e| <= 1e-12 * max(L, 1). value = P(u).

WORKED EXAMPLE 2 (checkable). `Card`'s `position` (spatial, both keys automatic tangents):

    key 0: time 0,             value [-10, 4, 0],  Bezier both sides, eases [{speed 0, influence 1/3}]
    key 1: time 254016000000,  value [14, -6, 0],  the same

The path is the straight segment (case one of step 4), L = 26, and the progress is
f = E(0, 1/3, 0, 1/3, x), which is 3 u^2 - 2 u^3 at u = x. Values:

    tick             seconds   value
    0                0.0       [-10.0, 4.0]
    50803200000      0.2       [-7.504, 2.9599999999999995]
    101606400000     0.4       [-1.5519999999999996, 0.4800000000000004]
    152409600000     0.6       [5.552, -2.4800000000000004]
    203212800000     0.8       [11.504000000000005, -4.960000000000001]
    254016000000     1.0       [14.0, -6.0]
    304819200000     1.2       [14.0, -6.0]
    355622400000     1.4       [14.0, -6.0]
    406425600000     1.6       [14.0, -6.0]
    457228800000     1.8       [14.0, -6.0]

WORKED EXAMPLE 3 (checkable). The layer `Badge`'s `position` has three keys with automatic
tangents, so its path curves:

    key 0: time 0,             value [20, 12, 0], Linear both sides
    key 1: time 101606400000,  value [48, 27, 0], Bezier both sides,
                               in_ease [{speed 40, influence 0.5}], out_ease [{speed 40, influence 0.25}]
    key 2: time 304819200000,  value [80, 40, 0], Bezier both sides, eases [{speed 0, influence 1/3}]

The tangents: T_out(key 0) = (k1 - k0) / 6 = [4.666..., 2.5, 0]; T_out(key 1) = (k2 - k0) / 6 =
[10, 4.666..., 0], T_in(key 1) = -T_out(key 1); T_in(key 2) = -(k2 - k1) / 6. The lengths of the
two segments are 31.771471729498586 and 34.54522367334413. Values (a conforming evaluator agrees within 1e-6:
the arc-length table is an approximation the application makes, and this text fixes it):

    tick             seconds   value
    0                0.0       [20.0, 12.0]
    38102400000      0.15      [32.56927510524098, 19.001576414907596]
    76204800000      0.3       [43.495875452738176, 24.806035096025578]
    114307200000     0.45      [50.02893613645631, 27.927223782722724]
    152409600000     0.6       [57.52222373306188, 31.13120135275109]
    190512000000     0.75      [65.43627849749664, 34.31387116021728]
    228614400000     0.9       [72.54207700400374, 37.0859966687704]
    266716800000     1.05      [77.82816899895528, 39.137569129044856]
    304819200000     1.2       [80.0, 40.0]
    342921600000     1.35      [80.0, 40.0]

### 6.5 Where keyframes are stored

As section 3.5: a property has `keys` (inline keyframe objects) OR `track` (an index into the
owner's `core.keyframe.tracks` node, named by the owner payload's `tracks`), never both, and the
two carry the same fields. `spec/layouts/core.keyframe.tracks.layout.txt` gives the byte layout
and the steps that turn track i back into a list of keyframe objects.

### 6.6 Motion blur

A layer is motion blurred when the composition's `enable_motion_blur` and the layer's
`switches.motion_blur` are both true (and the render asks for motion blur; a final render
does). The SHUTTER is open from `shutter_phase / 360` to `(shutter_phase + shutter_angle) /
360` of a frame duration after the frame's time (phase -90 and angle 180: from a quarter frame
before to a quarter frame after).

Sub-sample i of n (i = 0..n-1) is at composition time

    t_i = t + round(((shutter_phase + shutter_angle * i / (n - 1)) / 360) * frame_seconds * TPS)

A 2D layer: its finished picture (source, masks, effects - made ONCE, at t) is placed with the
layer's transform evaluated at each t_i; the n placements are summed, each weighted 1/n, into a
transparent buffer, and that buffer is blended into the composition with the layer's blend
mode and its opacity at t. The number of sub-samples: let `travel` be the longest path any of
five points of the layer's picture (its four corners and its centre) travels across eight
placements at the times of n = 8; if travel < 0.001 pixels the layer is drawn once, unblurred;
otherwise n = clamp(ceil(travel), lo, hi) with lo = clamp(`motion_blur_samples`, 2, 64) and
hi = max(clamp(`motion_blur_adaptive_limit`, 16, 256), lo).

A shape or text layer whose CONTENT changes within the shutter is drawn at
clamp(`motion_blur_samples`, 2, 64) sub-sample times and the pictures are averaged, before the
steps above. A mask whose path is animated, on a blurred layer (or with its own
`motion_blur` `On`), has its coverage averaged over max(`motion_blur_samples`, 2) sub-sample
times. A 3D layer uses `motion_blur_samples` sub-samples.

### 6.7 Transform, parenting, 3D and the camera

Space: pixels; origin at the top-left corner; x to the right, y DOWN, z INTO the screen
(left-handed). Angles are degrees; a positive rotation about z turns clockwise on screen.
Matrices are 4 x 4 and act on column vectors (p' = M p); the elementary ones:

    T(x, y, z):  translation        S(x, y, z):  scale on the diagonal
    Rx(a) = | 1  0   0 |     Ry(a) = |  c  0  s |     Rz(a) = | c  -s  0 |     c = cos(a), s = sin(a)
            | 0  c  -s |             |  0  1  0 |             | s   c  0 |
            | 0  s   c |             | -s  0  c |             | 0   0  1 |

A layer's `transform` group gives, at a composition time: `anchor` A, `position` P, `scale`
(percent), `rotation` r (about z), and for 3D layers `orientation` (ox, oy, oz), `rotationX`,
`rotationY`. All are Vec3 or Scalar; a 2D layer uses only the x and y of the Vec3 values.

THE LOCAL MATRIX of a layer (layer space -> the space of its parent, or of the composition):

    2D layer:   L = T(Px, Py, 0) * Rz(r + o) * S(k * sx/100, sy/100, 1) * T(-Ax, -Ay, 0)
    3D layer:   L = T(P) * O * Rz(r) * Ry(rotationY) * Rx(rotationX) * S(k * sx/100, sy/100, sz/100) * T(-A)
                with O = Rz(oz) * Ry(oy) * Rx(ox)
    camera or light:   L = T(P) * G        (G: below)

* A layer is 3D when its `switches.three_d` is true, or it is a camera or a light.
* k is the PIXEL-ASPECT factor: the pixel aspect of the layer's source (the footage's, the
  solid's or the nested composition's `pixel_aspect`; 1 for layers without one) divided by the
  composition's; k = 1 unless the quotient is finite, positive and differs from 1 by more than
  1e-9. k is used in the layer's OWN matrix only - not when the layer acts as a parent.
* o is the 2D auto-orientation: 0 unless `auto_orient` is `AlongPath` and the position is
  animated (more than one key, or an expression); then with d = position(t + 0.005 s) -
  position(t - 0.005 s) and |d| > 1e-9: o = atan2(dy, dx) in degrees. For a 3D layer with
  `AlongPath`, O is replaced by the rotation whose x axis is d/|d|, whose y axis is the down
  direction (0, 1, 0) made perpendicular to it and normalised (if that vanishes: (0, 0, 1)
  likewise), and whose z axis is x cross y. With `TowardsCamera`, O is replaced by the rotation
  whose +z points from the active camera's eye (in the parent's space) to P and whose +y is as
  close to (0, 1, 0) as possible (the basis construction below).

THE WORLD MATRIX (layer space -> composition space) follows the `parent` chain:

    W = L(parent_n) * ... * L(parent_1) * L(layer)

`parent` names a layer of the same composition by id; the chain ends at a layer without a
parent, at an id that names no layer, or after 64 steps. Parents' matrices are evaluated at the
same composition time. A parent need not be visible or active.

For a 2D layer the map from layer pixels to composition pixels is the affine

    | W00  W01  W03 |
    | W10  W11  W13 |
    |  0    0    1  |

WORKED EXAMPLE 4 (checkable). In the example project, at composition frame 10 (tick
101 606 400 000, 0.4 s): `Rig` (a null layer; anchor (0, 0), position (50, 30), scale (90, 110),
rotation keyframed linearly 0 -> 75 degrees over 2 s, so 15 degrees) and `Card` (parent `Rig`;
anchor (20, 12), scale (120, 80), position as in worked example 2, rotation given by an
expression: 32.0 degrees, from the baked track of section 6.18.4).

    L(Rig)  = [0.8693332436601615, -0.2847009496127728, 50.0] / [0.23293714059226867, 1.0625184089179753, 30.0]
    L(Card) = [1.017657715387711, -0.42393541138656393, -16.817929371115454] / [0.6359031170798458, 0.6784384769251408, -20.379324064698604]
    W(Card) = L(Rig) * L(Card) = [0.7036414613594341, -0.5616932249175175, 41.18162782184683] / [0.912709046509733, 0.6221030685270419, 4.429072641562268]

(each written as the two rows [a, b, tx] / [c, d, ty] of the affine above). The centre of the
card, layer point (20, 12), lands on composition point (48.514138350025306, 30.148490394081428).

THE CAMERA. A composition with 3D layers is seen through its ACTIVE CAMERA: the first layer in
stacking order whose source is `Camera`, whose `switches.video` is true and which is active at
t. Without one: a default camera with zoom Z = composition width * 50 / 36, its eye at
(width/2, height/2, -Z), looking along +z with +y down - which shows the plane z = 0 at exactly
100 %.

A camera layer gives: eye E = (the world matrix of its parent chain) applied to its position;
G = [for a camera whose `auto_orient` is `TowardsPointOfInterest` and that has a `poi`
property: the basis rotation for the direction poi - position] * Rz(oz) * Ry(oy) * Rx(ox) *
Rz(rotation) * Ry(rotationY) * Rx(rotationX); forward f = G (0, 0, 1) and down hint g =
G (0, 1, 0), both carried through the parent chain as directions and normalised; zoom Z = the
value of `cameraOptions/zoom` (pixels; at least 0.001).

BASIS for a forward direction f and a down hint g (unit f; f = (0, 0, 1) when it has no
length): d = g - f (g . f); if |d| < 1e-9 take g = (0, 1, 0) when |f.y| < 0.99, else (0, 0, -1),
and repeat; d = d / |d|; r = (d cross f) / |d cross f|. The VIEW matrix is

    V = | rx ry rz 0 |
        | dx dy dz 0 | * T(-E)
        | fx fy fz 0 |
        | 0  0  0  1 |

and the "basis rotation" used above is the transpose of its upper 3 x 3 block. A world point
p with (xc, yc, zc) = V p is at composition pixel

    x = Z * xc / zc + width / 2        y = Z * yc / zc + height / 2

and zc is its DEPTH. Points with zc < 1 are not drawn. A 3D layer is the plane z = 0 of its
layer space: layer point (u, v) is the world point W (u, v, 0).

Consecutive 3D layers in the stacking order form a GROUP that is composited together: at each
output pixel, the layers of the group that cover it are blended from the largest depth to the
smallest, each with its own blend mode and opacity; layers at equal depth keep their stacking
order. A 2D layer between two 3D layers separates two groups. When the composition has light
layers, a 3D layer's picture is shaded by them before blending; lights, shadows, material
options, depth of field, the `Advanced3D` renderer, models, primitives and extruded shapes are
NOT defined by this revision (section 8).

### 6.8 Colour, bit depth and the pixel model

A picture is a rectangle of pixels; a pixel is (r, g, b, a) in binary32, PREMULTIPLIED: the
colour components already multiplied by alpha a. "Straight" colour is (r/a, g/a, b/a).
Coordinates: pixel (i, j) covers the square [i, i+1) x [j, j+1); its centre is (i + 0.5,
j + 0.5).

The project settings decide in what encoding pixels are computed:

* `working_space` null (the default): NO COLOUR MANAGEMENT. Component values are used as they
  are stored: a solid's colour, a shape's fill colour and the decoded values of a medium go
  into the pixel unchanged, and the rendered frame's values are the output values. (For an
  8-bit medium, decoded value v / 255.)
* `working_space` W (one of the eight below): a medium is converted from its own space
  (`color_profile`, else sRGB) to W; the top-level composition's result is converted from W to
  `output_space` (else sRGB). A footage item with `preserve_rgb` is not converted.
* `linearize` true (with a working space), or a working space that is linear by definition:
  the working space is LINEAR LIGHT: media are converted to linear W, and authored colours
  (solids, shape and text colours) are decoded from W's curve to linear before use.
* `blend_linear` true (and the working space not already linear): sources, masks and effects
  work on encoded values; each layer's finished picture is decoded to linear just before it is
  placed and blended (section 6.9); when a composition is complete it is encoded again. The
  curve is W's, or without a working space the sRGB curve when `working_gamma` is 2.2 and a
  pure 2.4 power when it is 2.4.

A conversion acts on STRAIGHT colour (pixels with a <= 0 are left alone): decode with the
source curve unless the source is linear; multiply by the 3 x 3 matrix M(to)^-1 * M(from)
unless the two spaces have the same primaries; encode with the destination curve unless the
destination is linear. M(space) maps linear RGB to CIE XYZ: with the chromaticities (x, y) of
the three primaries and the white point, the columns are (x/y, 1, (1-x-y)/y) of each primary,
scaled so that RGB (1, 1, 1) maps to the white point's (x/y, 1, (1-x-y)/y); a space whose white
is not D65 is then multiplied by the Bradford adaptation to D65 (cone matrix rows
(0.8951, 0.2664, -0.1614), (-0.7502, 1.7135, 0.0367), (0.0389, -0.0685, 1.0296)). The matrix
is computed in binary64 and applied in binary32.

| space | primaries (x, y): red, green, blue | white (x, y) | curve |
|---|---|---|---|
| `Srgb` | (0.640, 0.330) (0.300, 0.600) (0.150, 0.060) | D65 (0.3127, 0.3290) | sRGB |
| `Rec709` | as Srgb | D65 | power 2.4 |
| `Rec2020` | (0.708, 0.292) (0.170, 0.797) (0.131, 0.046) | D65 | power 2.4 |
| `DisplayP3` | (0.680, 0.320) (0.265, 0.690) (0.150, 0.060) | D65 | sRGB |
| `AcesCg` | (0.713, 0.293) (0.165, 0.830) (0.128, 0.044) | (0.32168, 0.33767) | linear |
| `Aces2065` | (0.7347, 0.2653) (0.0, 1.0) (0.0001, -0.0770) | (0.32168, 0.33767) | linear |
| `Rec2100Pq` | as Rec2020 | D65 | SMPTE ST 2084 (PQ); linear 1.0 = 203 cd/m2 |
| `Rec2100Hlg` | as Rec2020 | D65 | BT.2100 HLG; linear 1.0 = scene light 0.26496256 |

Curves, for v >= 0 (a negative value is mirrored: f(-v) = -f(v)): sRGB decode: v / 12.92 when
v <= 0.04045, else ((v + 0.055) / 1.055)^2.4; sRGB encode: 12.92 v when v <= 0.0031308, else
1.055 v^(1/2.4) - 0.055. Power 2.4: decode v^2.4, encode v^(1/2.4). PQ and HLG are the
functions of ITU-R BT.2100 with the scalings in the table.

`hdr` (output of a managed project to a standard-dynamic-range `output_space`): `Clip` - the
plain conversion; `Compand` - in linear output primaries each channel v > 0.8 becomes
0.8 + 0.2 * (1 - exp(-(v - 0.8) / 0.2)); `ToneMap` - with Y = 0.2126 r + 0.7152 g + 0.0722 b > 0
the colour is multiplied by (1 + Y / 16) / (1 + Y); then the output curve is applied.

BIT DEPTH. Pixels are binary32 throughout; `bit_depth` says where they are QUANTISED:

    Bpc8:  levels = 255        Bpc16:  levels = 32768        Bpc32:  never quantised

Quantising a pixel: a = floor(clamp(a, 0, 1) * levels + 0.5) / levels; then each colour
component c = floor(clamp(c, 0, a) * levels + 0.5) / levels (the clamp against the QUANTISED
alpha; a NaN counts as 0). It happens: to a layer's picture after its source and masks (a solid
without masks is filled with the quantised colour (r, g, b, 1)); after each effect; to the
composition after each layer is blended into it; after the conversion out of the blending space
and after the output conversion. So with 8 bits per channel every stage holds multiples of
1/255.

AUTHORED COLOURS. A colour stored in the document (`[r, g, b]` of a solid, a `Color` value) is
straight, in the encoding of the working space as a person picked it (sRGB-encoded values when
there is no working space). It is used as stored, or decoded to linear when the working space
is linear.

AN OUTPUT FRAME of a composition is its W x H premultiplied picture after the steps above. To
show it over a background colour (r, g, b): out = c + bg * (1 - clamp(a, 0, 1)) per channel. As
8-bit values: floor(clamp(v, 0, 1) * 255 + 0.5). The composition's `background` is an editor
backdrop only: a render's pixels where no layer draws are transparent.

### 6.9 Blending a layer into the composition

A composition frame starts as transparent black. Layers are blended into it from the LAST of
the composition's `layers` list (the back) to the first (section 6.11 says which layers are
drawn). For each output pixel, D is the composition's pixel so far and S the layer's finished,
placed picture at that pixel (section 6.10 and the placement below), premultiplied, ALREADY
MULTIPLIED by the layer's opacity (all four components times `opacity` / 100).

PLACING. A layer's finished picture (its buffer) is drawn through the layer's matrix: for the
output pixel centre q = (i + 0.5, j + 0.5), the buffer point is p = M^-1 q, M being the map
from buffer pixels to output pixels (section 6.7; for a source at full resolution buffer pixels
ARE layer pixels). S is the buffer SAMPLED at p:

* `Bilinear` (the default at `Best` quality): with f = p - (0.5, 0.5), i0 = floor(f),
  t = f - i0: the four pixels (i0), (i0 + (1, 0)), (i0 + (0, 1)), (i0 + (1, 1)) mixed
  top = a + (b - a) tx, bottom = c + (d - c) tx, result = top + (bottom - top) ty, per
  component in binary32; a pixel outside the buffer is transparent (0, 0, 0, 0). So a layer's
  edge is anti-aliased by the sampling itself.
* `Draft` quality: the pixel containing p (nearest neighbour).
* `Bicubic`: the Catmull-Rom cubic over the 4 x 4 neighbourhood: with f, i0, t as above and
  W(t) = (-0.5 t^3 + t^2 - 0.5 t, 1.5 t^3 - 2.5 t^2 + 1, -1.5 t^3 + 2 t^2 + 0.5 t,
  0.5 t^3 - 0.5 t^2) for the offsets -1, 0, 1, 2: the sum over the sixteen pixels
  (i0 + (a, b)) of pixel * W(tx)[a] * W(ty)[b], pixels outside the buffer transparent; every
  component of the result below 0 is set to 0.
* Points p outside the buffer by more than one pixel are not drawn.
* Only the output pixels inside the DRAWN RECTANGLE are touched: the bounding box of the four
  corners of the buffer's rectangle mapped by M, grown by 1 on every side, its minimum
  rounded down and its maximum rounded up. (So a picture enlarged more than twice ends at
  most two output pixels beyond its mapped edge, although the sampling above would fade
  further.)
* When an AFFINE M shrinks the picture to less than half (the square root of |det M| < 0.5),
  the buffer is first halved by 2 x 2 averaging (edge pixels repeated; a side of odd length
  rounds up) - once, and again while the factor is still below 0.5 and both sides are longer
  than one pixel - and M is adjusted to match. A map with perspective is never pre-filtered.

THE BLEND, for mode word m (the layer's `blend_mode`):

    Normal:      out = S + D * (1 - S.a)                         (all four components)
    for the other modes, unless the table below says otherwise:
        if S.a <= 0: out = D            if D.a <= 0: out = S
        s = S.rgb / S.a;  b = D.rgb / D.a;  both clamped to 0..1 unless m is marked "hdr"
        out.rgb = (1 - D.a) * S.rgb + (1 - S.a) * D.rgb + S.a * D.a * B(b, s)
        out.a   = S.a + D.a - S.a * D.a
    CLASSIC frame (the three modes that say so), with neutral n:
        s' = n + S.a * (s - n)
        out.rgb = (1 - D.a) * S.rgb + D.a * B(b, s')          out.a as above

B is the mode's formula, applied per channel unless it speaks of whole colours. In the table,
`Y(c)` = 0.2126 r + 0.7152 g + 0.0722 b, and for the four modes that use them:

    Lum(c) = 0.3 r + 0.59 g + 0.11 b
    Sat(c) = max(r, g, b) - min(r, g, b)
    SetSat(c, s): with mx, mn the largest and smallest of c: (0, 0, 0) when mx - mn <= 1e-9,
                  else each channel (v - mn) * s / (mx - mn)
    SetLum(c, l): c + (l - Lum(c)) on each channel, then ClipColor
    ClipColor(c): l = Lum(c), n = min, x = max of c;
                  if n < 0: each v = l + (v - l) * l / max(l - n, 1e-9)
                  if x > 1: each v = l + (v - l) * (1 - l) / max(x - l, 1e-9)

| `blend_mode` | hdr | what it computes |
|---|---|---|
| `Normal` | hdr | out = S + D * (1 - S.a) on all four premultiplied components (S already multiplied by the layer opacity). No formula B. |
| `Dissolve` | hdr | Per pixel, taken or left: n = noise(x, y, layer id) (above); if S.a <= 0 or n >= S.a the backdrop stays; else the pixel becomes (S.rgb / S.a, 1): opaque source colour. |
| `DancingDissolve` | hdr | As Dissolve (this revision does not vary the noise over time). |
| `Darken` | hdr | B = min(b, s) per channel |
| `Multiply` | hdr | B = b * s |
| `ColorBurn` | hdr | B = 1 if b >= 1; else 0 if s <= 0; else 1 - min(1, (1 - b) / s) |
| `ClassicColorBurn` | hdr | CLASSIC frame (above) with neutral 1: B = 0 if s' <= 0, else 1 - (1 - b) / s' (negative results are kept) |
| `LinearBurn` | hdr | B = max(0, b + s - 1) |
| `DarkerColor` | hdr | B = the whole colour s if Y(s) < Y(b), else b; Y(c) = 0.2126 r + 0.7152 g + 0.0722 b |
| `Add` | hdr | B = b + s |
| `Lighten` | hdr | B = max(b, s) per channel |
| `Screen` | hdr | B = b + s - b * s |
| `ColorDodge` |  | B = 0 if b <= 0; else 1 if s >= 1; else min(1, b / (1 - s)) |
| `ClassicColorDodge` |  | CLASSIC frame with neutral 0: B = 1 if s' >= 1, else min(1, b / (1 - s')) |
| `LinearDodge` | hdr | B = b + s |
| `LighterColor` | hdr | B = the whole colour s if Y(s) > Y(b), else b; Y as in DarkerColor |
| `Overlay` | hdr | B = HardLight with b and s exchanged: 2 b s if b <= 0.5, else s + (2 b - 1) - s (2 b - 1) |
| `SoftLight` |  | if s <= 0.5: B = b - (1 - 2 s) * b * (1 - b); else B = b + (2 s - 1) * (d - b) with d = ((16 b - 12) b + 4) b if b <= 0.25, else sqrt(max(b, 0)) |
| `HardLight` |  | B = 2 b s if s <= 0.5, else b + (2 s - 1) - b (2 s - 1) |
| `LinearLight` |  | B = clamp(b + 2 s - 1, 0, 1) |
| `VividLight` |  | B = ColorBurn(b, 2 s) if s <= 0.5, else ColorDodge(b, 2 (s - 0.5)) |
| `PinLight` |  | B = min(b, 2 s) if s <= 0.5, else max(b, 2 s - 1) |
| `HardMix` |  | B = 1 if b + s >= 1, else 0 |
| `Difference` | hdr | B = \|b - s\| |
| `ClassicDifference` | hdr | CLASSIC frame with neutral 0: B = \|b - s'\| |
| `Exclusion` | hdr | B = b + s - 2 b s |
| `Subtract` | hdr | B = max(0, b - s) |
| `Divide` | hdr | B = b / s if s > 0; else 1 if b > 0, else 0 |
| `Hue` |  | B = SetLum(SetSat(s, Sat(b)), Lum(b)) |
| `Saturation` |  | B = SetLum(SetSat(b, Sat(s)), Lum(b)) |
| `Color` |  | B = SetLum(s, Lum(b)) |
| `Luminosity` | hdr | B = SetLum(b, Lum(s)) |
| `StencilAlpha` | hdr | The layer cuts everything below it: out = D * S.a on all four components (S multiplied by the layer opacity). No formula B. |
| `StencilLuma` | hdr | out = D * Y(S.rgb) on all four components, Y of the PREMULTIPLIED source colour (S multiplied by the layer opacity). |
| `SilhouetteAlpha` | hdr | out = D * (1 - S.a) on all four components. |
| `SilhouetteLuma` | hdr | out = D * (1 - Y(S.rgb)) on all four components. |
| `AlphaAdd` | hdr | out.rgb = S.rgb + D.rgb * (1 - S.a); out.a = min(1, S.a + D.a). |
| `LuminescentPremul` | hdr | out.rgb = S.rgb + D.rgb * (1 - S.a); out.a = S.a + D.a - S.a * D.a. |

The NOISE of the two dissolve modes, for output pixel (x, y) and the layer's id as `seed`, all
in unsigned 32-bit arithmetic that wraps:

    h = x * 0x8da6b343  XOR  y * 0xd8163841  XOR  seed * 0xcb1ab31f
    h = h XOR (h >> 13);   h = h * 0x5bd1e995;   h = h XOR (h >> 15)
    n = (h AND 0x00ffffff) / 16777216

The stencil and silhouette modes change what is BELOW the layer; `StencilAlpha` and
`StencilLuma` also clear every pixel the layer's picture does not reach. `linear blending`
(section 6.8) changes only the encoding S and D are in.

After each layer, an 8- or 16-bit project quantises the composition (section 6.8).

### 6.10 Masks

The children of a layer's `masks` group are its masks, in order. A mask is a group with
`kind` = `{"kind": "Mask", mode, inverted, color, locked, motion_blur, feather_falloff,
roto_bezier}` and the properties `path` (a Path, in LAYER pixels), `feather` (Vec2, pixels),
`opacity` (percent), `expansion` (pixels). `mode` is one of `None`, `Add`, `Subtract`,
`Intersect`, `Lighten`, `Darken`, `Difference`. `color`, `locked` and `roto_bezier` are for the
editor.

Masks act on the layer's SOURCE picture, before effects. Only masks that are `enabled`, whose
mode is not `None` and whose path is CLOSED take part (an open path cuts nothing). With none,
the picture is unchanged. Otherwise:

1. COVERAGE of one mask: for every pixel of the layer's picture, the fraction of the pixel's
   area that is inside the path, by the non-zero winding rule. (The path is in layer pixels;
   a picture at full resolution has one pixel per layer pixel, origin at the layer's origin.)
   This is the one place where this profile defines an ideal and not a procedure: the
   writing application approximates the area with an anti-aliasing rasteriser that is exact
   for pixels the outline does not cross and within about 1/16 of the true area elsewhere, in
   steps of 1/255. Section 6.20 states the tolerance a reader's picture is checked with.
2. `expansion` e, when |e| > 0.01: let R be the coverage of the path stroked with width 2 |e|
   and round joins (the band within |e| of the outline). e > 0: c = min(1, c + R - c R);
   e < 0: c = max(0, c * (1 - R)).
3. `feather` (fx, fy), when either is positive: the coverage picture is blurred, pixels beyond
   its edge counting as 0. `feather_falloff` `Smooth` (the default): a Gaussian of standard
   deviation fx / 2 horizontally and fy / 2 vertically, computed as THREE box blurs per axis
   (an axis with deviation <= 0.05 is not blurred): for deviation g, n = 3,
   w = sqrt(12 g^2 / n + 1); wl = floor(w), made odd by subtracting 1 if even; wu = wl + 2;
   m = round((12 g^2 - n wl^2 - 4 n wl - 3 n) / (-4 wl - 4)); the first m passes have window wl,
   the rest wu; a pass of window k replaces each value by the mean of the k values centred on
   it. `Linear`: one box blur per axis of window 2 r + 1, r = max(round(f / 2), 1) for a
   positive f.
4. `inverted`: c = 1 - c. Then `opacity`: c = c * opacity / 100.
5. COMBINING, in order, into an accumulator A that starts at 0 (at 1 when the first mask's
   mode is `Subtract`):

       Add:         A = A + c - A c          Lighten:     A = max(A, c)
       Subtract:    A = A * (1 - c)          Darken:      A = min(A, c)
       Intersect:   A = A * c                Difference:  A = |A - c|

   The FIRST mask that takes part is combined as `Add` when its mode is `Intersect` or
   `Darken` (there is nothing yet to intersect with).
6. Every component of each pixel of the picture is multiplied by A. Then, in an 8- or 16-bit
   project, the picture is quantised.

A path with FEATHER POINTS (`path.feather`: a position on the outline with a signed radius)
has a feather whose width varies along the outline; steps 1 to 3 are then one computation from
the signed distance to the outline, which this revision does not define (section 8). The
points are carried.

### 6.11 Which layers are drawn, mattes, and adjustment layers

At composition time t the layers DRAWN are those that are active (in_point <= t < out_point),
have `switches.video` true, have a picture (every `source.type` except `Camera`, `Light`,
`Null`), are not `environment`, and - in a render - are not `switches.guide`. If any layer with
a picture that is active at t has `switches.solo`, only solo layers are drawn. They are blended
back to front: from the last of `layers` to the first.

A layer's picture is made in this order: SOURCE (section 6.19, or the solid's colour, the
shapes, the text) -> MASKS (6.10) -> EFFECTS (6.12, when `switches.effects`) -> layer styles
(not defined here) -> PLACED by its transform with motion blur (6.6, 6.7) -> matte, preserve
transparency -> BLENDED with its mode and opacity (6.9). A layer whose opacity is <= 0 is not
drawn.

`track_matte` = `{layer, kind}` names another layer of the composition as this layer's MATTE.
The layer's picture is placed alone on a transparent frame (mode Normal, opacity 100 %); the
matte layer's finished picture is placed on another transparent frame with ITS transform and
ITS opacity (transparent when the matte layer is not active at t; the matte layer's own
`video` switch does not matter); then every component of each pixel of the first frame is
multiplied by k, clamped to 0..1:

    Alpha:          k = matte.a                 Luma:          k = Y(matte.rgb)
    AlphaInverted:  k = 1 - matte.a             LumaInverted:  k = 1 - Y(matte.rgb)

(Y of the PREMULTIPLIED matte colour) and the result is blended into the composition with the
layer's mode and opacity. A matte that names the layer itself or no layer is ignored.

`preserve_transparency`: the layer's picture, placed alone as above (after the matte, if any),
is multiplied in every component by the alpha of the composition below it before it is blended.

AN ADJUSTMENT LAYER (`switches.adjustment`) has no picture of its own: its effects are applied
to the composition as it stands below it. Its footprint F is the alpha of its source rectangle
(a solid's size, filled with 1) after its masks, placed with its transform. The composition so
far C (converted out of the linear blending space if that is on) is run through the layer's
effects as one picture, giving C'; then C = C + (C' - C) * F * opacity / 100 in every
component.

### 6.12 Effects

An effect instance is a child group of a layer's `effects` group with `kind` =
`{"kind": "Effect", "effect": <id>}`; its child properties are its PARAMETERS, found by
`match`. The MEANING of an id is in the capsule's `effect-catalog` node, never in an
application: for each id the document uses, the catalog has

* `id`, `name`, `category`, `kind` (`video`, `audio`, or `control`: an effect that only holds
  values), `third_party`;
* `params`: the parameter list - `id` (the property's `match`), `name`, `kind` (the value
  kind), `ui` (range, option names), `default`. The `default` of a POINT parameter (`ui.kind`
  `Point`) is a fraction of the layer's size - [0.5, 0.5] is its centre - while an instance
  stores layer pixels;
* `rendering`: `exact` or `tolerance` - the effect is DEFINED: `definition` is its arithmetic,
  normative, in words and formulas (below); `none` - the effect computes nothing;
  `parameters-only` - THIS REVISION DOES NOT DEFINE WHAT THE EFFECT COMPUTES: `definition` is
  null; its parameters are complete and typed; its picture (or sound) is undefined.

THE DEFINITIONS. A definition is written with a small vocabulary that travels in the same node:
the catalog's `primitives` (the pixel model; colour words such as `luma`, `rgb_to_hsl`,
`STRAIGHT`; filters such as `GAUSSIAN` and `MORPH`; the hash; how another layer is read; the
test patches) and, in `sections`, the words the definitions of one section share (the entry's
`section` names its section). A definition, its section and the primitives are complete: they
name no application and no other definition. With a definition an entry has

* `tolerance`: the largest difference of a test-vector value a conforming implementation may
  show, in units of 1/65536. `exact`: the arithmetic is given completely and the tolerance only
  covers binary32 against binary64 rounding. `tolerance`: the result is reproducible within the
  tolerance only;
* `limits`: settings of the effect the definition does not cover (usually none). A reader that
  meets an instance with such a setting treats that instance as `parameters-only`;
* `test_vectors`: each vector names its `input` (PATCH A or PATCH B of the primitives: 16 x 12
  pictures built from a formula, not stored), the `params` that differ from the defaults, and
  gives the `width`, `height` and `origin` of the result and the result itself (`output`: one
  string of integers round(value * 65536), with its `output_sha256`), made by the writing
  application's own renderer in a 32-bit-float project. An implementation is right when it
  reproduces every vector within `tolerance`.

DEFINITIONS FOLLOW USE: the catalog of a capsule holds the entries, sections and vectors of the
effects ITS document uses, and the primitives only when one of them is defined. Nothing about
an effect the document does not use is in the file.

A catalog node that has a definition has a second file, `effects/effects_ref.py` (role
`reference-source`): a reference program in Python (standard library) written from these texts
alone. It implements every definition of this revision, reads the catalog of a capsule and
checks itself against the vectors (`python effects_ref.py <capsule>`). It is program text
carried as a reference - NOTHING runs it because it is in the file - and an example, not the
norm: the texts are.

THE SAME FORM AS `timeline/1`. This library has the form of `timeline/1`'s effect library: a
primitives text, sections of definitions keyed by id, `exact` / `tolerance` / parameters-only,
vectors from the normative renderer over the same two patches, tolerances in the same unit.
The words of the primitives marked `(=)` compute what the words of the same name compute there
(checked: the two profiles' reference programs give the same patches and the same results for
those words to binary32 rounding). The EFFECTS are not shared: an effect of this profile
computes on the working-space numbers of a layer as they are (section 6.8), an effect of
`timeline/1` on linear light, most colour effects there converting to a display encoding and
back; their parameters differ too. So every effect here has its own id and its own definition,
also where an effect of the same name exists there (Tint, Posterize, Levels, Gaussian Blur...).

`unknown` lists effect ids the document uses that the writing application itself did not know
(a layer made by another program); `blend_modes` repeats section 6.9's formulas by mode word.

The effects of a layer run in the order of the list, each on the result of the one before,
skipping instances whose group has `enabled` false and every effect when the layer's
`switches.effects` is false. An effect's parameters are evaluated at the composition time like
any property. In an 8- or 16-bit project the picture is quantised after each effect.

A reader that meets an effect it cannot compute (no definition, or one it does not implement)
draws the layer WITHOUT that effect and reports the effect by id and layer. It keeps the
instance when it writes the layer back.

EFFECT SPACE. An effect works on the layer's picture in coordinates measured from the top-left
corner of the layer's EFFECT BOUNDS: for a layer with a source rectangle, that rectangle (so
effect space is layer space); for a shape or text layer, a rectangle the size of the
composition centred on the layer's origin - effect point (x, y) is layer point (x - width/2,
y - height/2). That is the meaning of `app_schema` 2 in the structure node; with `app_schema`
1 the effect points of shape and text layers are measured from the layer's origin instead.

What this revision defines, of the 306 effect ids of the writing application:

| | count |
|---|---|
| defined, `exact` | 117 |
| defined, `tolerance` | 0 |
| compute nothing (`none`) | 9 |
| PARAMETERS ONLY - RENDERING UNDEFINED | 180 |

6 of the defined ones state a limit:

* `ec.color.autocolor`: With `temporalSmoothing` above 0 the histograms of the layer's
  neighbouring frames are added; that case is not defined in this revision.
* `ec.color.autocontrast`: With `temporalSmoothing` above 0 the histograms of the layer's
  neighbouring frames are added; that case is not defined in this revision.
* `ec.color.autolevels`: With `temporalSmoothing` above 0 the histograms of the layer's
  neighbouring frames are added; that case is not defined in this revision.
* `ec.color.shadowhighlight`: With `autoAmounts` on and `temporalSmoothing` above 0 the
  measurement includes the layer's neighbouring frames; that case is not defined in this
  revision.
* `ec.distort.transform`: With a shutter (Use Composition's Shutter Angle on a motion-blurred
  layer, or a Shutter Angle above 0) the result is the mean of the drawings at several times of
  the shutter; that case is not defined in this revision.
* `ec.generate.fill`: With `allMasks`, or `fillMask` naming a mask, on a layer that has
  masks, the fill is limited to those masks; that case is not defined in this revision.

Defined, by section (353 test vectors in all; the reference program reproduces every one
within its tolerance):

| section | exact | tolerance | ids |
|---|---|---|---|
| `blur` | 6 | 0 | `ec.blur.directional`, `ec.blur.fastbox`, `ec.blur.gaussian`, `ec.blur.radial`, `ec.blur.sharpen`, `ec.blur.unsharp` |
| `channel` | 13 | 0 | `ec.channel.arithmetic`, `ec.channel.blend`, `ec.channel.calculations`, `ec.channel.cccomposite`, `ec.channel.combiner`, `ec.channel.compoundarithmetic`, `ec.channel.invert`, `ec.channel.minimax`, `ec.channel.removecolormatting`, `ec.channel.setchannels`, `ec.channel.setmatte`, `ec.channel.shiftchannels`, `ec.channel.solidcomposite` |
| `color` | 15 | 0 | `ec.color.blackwhite`, `ec.color.brightnesscontrast`, `ec.color.changetocolor`, `ec.color.channelmixer`, `ec.color.colorama`, `ec.color.colorbalance`, `ec.color.exposure`, `ec.color.gammapedestalgain`, `ec.color.huesaturation`, `ec.color.leavecolor`, `ec.color.levels`, `ec.color.photofilter`, `ec.color.tint`, `ec.color.tritone`, `ec.color.vibrance` |
| `color2` | 18 | 0 | `ec.color.autocolor`, `ec.color.autocontrast`, `ec.color.autolevels`, `ec.color.broadcast`, `ec.color.cccolorneutralizer`, `ec.color.cccoloroffset`, `ec.color.cckernel`, `ec.color.cctoner`, `ec.color.changecolor`, `ec.color.colorbalancehls`, `ec.color.colorlink`, `ec.color.curves`, `ec.color.equalize`, `ec.color.levelsic`, `ec.color.psarbitrarymap`, `ec.color.selectivecolor`, `ec.color.shadowhighlight`, `ec.color.videolimiter` |
| `distort` | 10 | 0 | `ec.distort.bulge`, `ec.distort.cornerpin`, `ec.distort.mirror`, `ec.distort.offset`, `ec.distort.polar`, `ec.distort.ripple`, `ec.distort.spherize`, `ec.distort.transform`, `ec.distort.twirl`, `ec.distort.wavewarp` |
| `generate` | 6 | 0 | `ec.generate.checkerboard`, `ec.generate.circle`, `ec.generate.fill`, `ec.generate.fourcolor`, `ec.generate.gradientramp`, `ec.generate.grid` |
| `key` | 12 | 0 | `ec.key.advancedspill`, `ec.key.colordifference`, `ec.key.colorkey`, `ec.key.colorrange`, `ec.key.differencematte`, `ec.key.extract`, `ec.key.keycleaner`, `ec.key.linearcolor`, `ec.key.luma`, `ec.key.screen`, `ec.key.spill`, `ec.key.unmult` |
| `noise` | 1 | 0 | `ec.noise.noise` |
| `perspective` | 1 | 0 | `ec.perspective.dropshadow` |
| `stylize` | 17 | 0 | `ec.stylize.brushstrokes`, `ec.stylize.cartoon`, `ec.stylize.cckaleida`, `ec.stylize.ccrepetile`, `ec.stylize.ccthreshold`, `ec.stylize.ccthresholdrgb`, `ec.stylize.ccvignette`, `ec.stylize.coloremboss`, `ec.stylize.emboss`, `ec.stylize.findedges`, `ec.stylize.glow`, `ec.stylize.mosaic`, `ec.stylize.motiontile`, `ec.stylize.posterize`, `ec.stylize.scatter`, `ec.stylize.strobe`, `ec.stylize.threshold` |
| `transition` | 10 | 0 | `ec.transition.blockdissolve`, `ec.transition.ccgridwipe`, `ec.transition.cclightwipe`, `ec.transition.ccradialscalewipe`, `ec.transition.ccscalewipe`, `ec.transition.gradientwipe`, `ec.transition.iriswipe`, `ec.transition.linearwipe`, `ec.transition.radialwipe`, `ec.transition.venetian` |
| `utility` | 8 | 0 | `ec.obsolete.basic3d`, `ec.obsolete.gaussianlegacy`, `ec.utility.applylut`, `ec.utility.ccoverbrights`, `ec.utility.cineon`, `ec.utility.growbounds`, `ec.utility.hdrcompander`, `ec.utility.hdrcompression` |

Compute nothing (they hold values that expressions read): `ec.control.angle`, `ec.control.checkbox`, `ec.control.color`, `ec.control.dropdown`,
`ec.control.layer`, `ec.control.point3d`, `ec.control.point`, `ec.control.slider`,
`ec.control.stereo3d`.

PARAMETERS ONLY - RENDERING UNDEFINED. These ids are carried with their parameter schemas and
no definition:

* 3D Channel (8): `ec.3d.channelextract`, `ec.3d.cryptomatte`, `ec.3d.depthmatte`,
  `ec.3d.depthoffield`, `ec.3d.extractor`, `ec.3d.fog3d`, `ec.3d.identifier`, `ec.3d.idmatte`.
* Audio (13): `ec.audio.backwards`, `ec.audio.basstreble`, `ec.audio.compressor`,
  `ec.audio.delay`, `ec.audio.distortion`, `ec.audio.flangechorus`, `ec.audio.gate`,
  `ec.audio.highlowpass`, `ec.audio.modulator`, `ec.audio.parametriceq`, `ec.audio.reverb`,
  `ec.audio.stereomixer`, `ec.audio.tone`.
* Blur & Sharpen (10): `ec.blur.bilateral`, `ec.blur.cameralens`,
  `ec.blur.camerashakedeblur`, `ec.blur.cccross`, `ec.blur.ccradial`, `ec.blur.ccradialfast`,
  `ec.blur.ccvector`, `ec.blur.channel`, `ec.blur.compound`, `ec.blur.smart`.
* Color Correction (7): `ec.color.colorstabilizer`, `ec.color.lumetri`, `ec.color.ociocdl`,
  `ec.color.ociocolorspace`, `ec.color.ociodisplay`, `ec.color.ociofile`, `ec.color.ociolook`.
* Distort (29): `ec.distort.bezierwarp`, `ec.distort.ccbender`, `ec.distort.ccbendit`,
  `ec.distort.ccblobbylize`, `ec.distort.ccflomotion`, `ec.distort.ccgriddler`,
  `ec.distort.cclens`, `ec.distort.ccpageturn`, `ec.distort.ccpowerpin`,
  `ec.distort.ccripplepulse`, `ec.distort.ccslant`, `ec.distort.ccsmear`, `ec.distort.ccsplit`,
  `ec.distort.ccsplit2`, `ec.distort.cctiler`, `ec.distort.displacementmap`,
  `ec.distort.liquify`, `ec.distort.magnify`, `ec.distort.meshwarp`,
  `ec.distort.opticscompensation`, `ec.distort.puppet`, `ec.distort.reshape`,
  `ec.distort.rollingshutterrepair`, `ec.distort.smear`, `ec.distort.turbulentdisplace`,
  `ec.distort.twirllegacy`, `ec.distort.upscale`, `ec.distort.warp`,
  `ec.distort.warpstabilizer`.
* Generate (20): `ec.generate.advancedlightning`, `ec.generate.audiospectrum`,
  `ec.generate.audiowaveform`, `ec.generate.beam`, `ec.generate.ccgluegun`,
  `ec.generate.cclightburst`, `ec.generate.cclightrays`, `ec.generate.cclightsweep`,
  `ec.generate.ccthreads`, `ec.generate.cellpattern`, `ec.generate.ellipse`,
  `ec.generate.eyedropperfill`, `ec.generate.fractal`, `ec.generate.lensflare`,
  `ec.generate.paintbucket`, `ec.generate.radiowaves`, `ec.generate.scribble`,
  `ec.generate.stroke`, `ec.generate.vegas`, `ec.generate.writeon`.
* Immersive Video (12): `ec.vr.blur`, `ec.vr.chromaticaberrations`, `ec.vr.colorgradients`,
  `ec.vr.converter`, `ec.vr.denoise`, `ec.vr.digitalglitch`, `ec.vr.fractalnoise`,
  `ec.vr.glow`, `ec.vr.planetosphere`, `ec.vr.rotatesphere`, `ec.vr.sharpen`,
  `ec.vr.spheretoplane`.
* Keying (3): `ec.key.ccsimplewireremoval`, `ec.key.innerouter`, `ec.keying.keylight`.
* Matte (6): `ec.matte.mattechoker`, `ec.matte.refinehard`, `ec.matte.refinesoft`,
  `ec.matte.rotobrush`, `ec.matte.simplechoker`, `ec.obsolete.mochashape`.
* Noise & Grain (12): `ec.noise.addgrain`, `ec.noise.curlnoise`, `ec.noise.dustscratches`,
  `ec.noise.fractal`, `ec.noise.matchgrain`, `ec.noise.median`, `ec.noise.medianlegacy`,
  `ec.noise.noisealpha`, `ec.noise.noisehls`, `ec.noise.noisehlsauto`, `ec.noise.removegrain`,
  `ec.noise.turbulent`.
* Obsolete (4): `ec.blur.reduceflicker`, `ec.obsolete.basictext`, `ec.obsolete.lightning`,
  `ec.obsolete.pathtext`.
* Paint (1): `ec.paint.paint`.
* Perspective (9): `ec.perspective.3dglasses`, `ec.perspective.bevelalpha`,
  `ec.perspective.beveledges`, `ec.perspective.cameratracker`, `ec.perspective.cccylinder`,
  `ec.perspective.ccenvironment`, `ec.perspective.ccsphere`, `ec.perspective.ccspotlight`,
  `ec.perspective.radialshadow`.
* Simulation (18): `ec.sim.carddance`, `ec.sim.caustics`, `ec.sim.ccballaction`,
  `ec.sim.ccbubbles`, `ec.sim.ccdrizzle`, `ec.sim.cchair`, `ec.sim.ccmrmercury`,
  `ec.sim.ccparticlesystems2`, `ec.sim.ccparticleworld`, `ec.sim.ccpixelpolly`,
  `ec.sim.ccrainfall`, `ec.sim.ccscatterize`, `ec.sim.ccsnowfall`, `ec.sim.ccstarburst`,
  `ec.sim.foam`, `ec.sim.particleplayground`, `ec.sim.shatter`, `ec.sim.waveworld`.
* Stylize (8): `ec.stylize.ccblockload`, `ec.stylize.ccburnfilm`, `ec.stylize.ccglass`,
  `ec.stylize.cchextile`, `ec.stylize.ccmrsmoothie`, `ec.stylize.ccplastic`,
  `ec.stylize.roughenedges`, `ec.stylize.texturize`.
* Text (2): `ec.text.numbers`, `ec.text.timecode`.
* Time (8): `ec.time.ccforcemotionblur`, `ec.time.ccwidetime`, `ec.time.echo`,
  `ec.time.pixelmotionblur`, `ec.time.posterizetime`, `ec.time.timedifference`,
  `ec.time.timedisplacement`, `ec.time.timewarp`.
* Transition (7): `ec.transition.cardwipe`, `ec.transition.ccglasswipe`,
  `ec.transition.ccimagewipe`, `ec.transition.ccjaws`, `ec.transition.cclinesweep`,
  `ec.transition.cctwister`, `ec.transition.ccwarpomatic`.
* Utility (3): `ec.utility.colorprofileconverter`, `ec.utility.facemeasurements`,
  `ec.utility.facetrackpoints`.

The writing application reports the same count for one project (command `werk.check`, field
`effectDefinitions`: `exact`, `tolerance`, `none`, `parametersOnly`, `notInCatalog`, and the
ids without a definition in `undefined`).

### 6.13 Nested compositions

A layer whose source is `Comp` shows composition `item` at source time (section 6.2): that
composition is rendered as a picture of its own size - transparent where nothing draws, its
own layers, effects and blend modes inside it - and that picture is the layer's source, to
which the layer's masks, effects, transform and blend mode apply. Nothing is drawn when source
time is before 0 or at or after the nested composition's duration. A composition that
(directly or through others) contains itself draws nothing at the point of recursion.

`switches.collapse` on such a layer (COLLAPSE TRANSFORMATIONS) changes this, but ONLY when
the layer has no masks, no enabled effects (or its `switches.effects` is false), no layer
styles and no overridden essential properties; otherwise the layer is drawn as above. When it
applies, the nested composition is not made into a picture: its drawn layers (section 6.11, at
the nested composition's time = the outer layer's source time) are drawn into the OUTER
composition, each with its own masks, effects and blend mode, placed through the matrix
(outer layer's matrix) * (its own matrix). Nothing is clipped to the nested composition's
frame. Then:

* outer layer's `blend_mode` is `Normal`, it has no track matte and no
  `preserve_transparency`: the nested layers are blended one by one straight into the outer
  composition, the opacity of each multiplied by the outer layer's opacity;
* otherwise: the nested layers are blended into a transparent frame of the outer
  composition's size (opacities unchanged); that frame takes the outer layer's matte and
  preserve-transparency (section 6.11) and is blended with the outer layer's mode and opacity.

3D layers of the nested composition join the outer composition's 3D space: their world matrix
is (outer layer's world matrix) * (their own), seen through the OUTER composition's camera.
Collapsing nests: a collapsed layer inside a collapsed composition multiplies matrices and
opacities again, to a depth of 12.

ESSENTIAL PROPERTIES. A composition's `essential.controls` lists properties of its layers that
it exposes (`{id, name, kind}`; `kind` names the layer and property by id). A layer that nests
it has a property group `essential` whose `kind` is `{"kind": "Essential", "overridden":
[uids]}` with one child property per control, `match` = `eg` followed by the control's id. For
every child whose `uid` is in `overridden`: the nested composition is rendered, for THIS layer
only, with the exposed property's keyframes removed and its value replaced by the child's
value at the composition time (the exposed property's own expression, if it has one, still
applies). A child that is not in `overridden` changes nothing.

A composition (or footage) item with a `proxy` whose `enabled` is true is replaced, where it
is used as a source, by a frame of the proxy's medium scaled to the item's size.

### 6.14 Third-party plug-ins

An effect whose code is not part of the writing application (`third_party` true in the
catalog) is carried so:

1. The effect instance stays in the layer like every other: its id and every parameter value
   the plug-in declares to its host, typed. Any reader knows which effect sits where and with
   what values.
2. What the saving host knew about the plug-in travels in an `x.effectcraft.plugin-state`
   node: `{schema_version, effect, name, version, api, manifest}` - the effect id, the
   plug-in's name and version, the revision of the plug-in interface it was loaded with, and
   `manifest`: the plug-in's own manifest as the host read it, verbatim and OPAQUE to this
   profile (no definition of it is in the package). The project `enhances` the node (role
   `plugin-state`). A reader that does not know the plug-in skips the node; a writer keeps it
   while the effect is used.
3. A plug-in's PRIVATE state would travel in the same node. The plug-in interface of this
   revision's writing application has none: everything a plug-in holds is a declared
   parameter, and those are ordinary properties of the effect instance (item 1).
4. The plug-in's executable code is NEVER in the package.
5. A writer may add a rendered result as a derived (`measured`) medium; this revision's writer
   does not.

The rendering of a third-party effect is undefined for every reader that does not have that
plug-in; such a reader draws the layer without it and names it.

### 6.15 Lookup-table files

A `core.color.lut` node holds one of two text formats (`meta.lut_format`). Both describe a
function from a colour (r, g, b) to a colour.

`cube`. Lines; a line that is empty or starts with `#` is skipped. `TITLE ...` is skipped.
`LUT_1D_SIZE n` and `LUT_3D_SIZE n` give table sizes (n at least 2; a 3D n at most 256).
`DOMAIN_MIN a b c` and `DOMAIN_MAX a b c` give the input range per channel (defaults 0 0 0 and
1 1 1); `LUT_1D_INPUT_RANGE lo hi` and `LUT_3D_INPUT_RANGE lo hi` set both ends for all three
channels. Any other line that begins with a letter is skipped. Every other line is three
numbers: a table row. The 1D rows come first (n of them), then the 3D rows (n^3 of them); the
file is invalid when the count is not exactly that. In the 3D table RED VARIES FASTEST: row
index = r + g * n + b * n^2.

`3dl`. Lines; empty lines and lines starting with `#` or `<` are skipped. A line that begins
with a letter is a keyword: `Mesh <input bits> <output bits>` sets the output bit depth, any
other is skipped. The first line of more than three numbers (before any row) is the INPUT
MESH: its count n is the lattice size. Every line of exactly three numbers is a row. Without a
mesh line, n is the cube root of the row count (when the file has 28 rows and that is not a
cube, the first row is the mesh of a 3-point lattice). There must be exactly n^3 rows, n at
least 2. Output values are integers scaled by `out_max`: 2^(output bits) - 1 when the `Mesh`
line gave one (1..31), else the smallest of 255, 1023, 4095, 65535 that is not below the
largest value in the file. BLUE VARIES FASTEST: row k is r = floor(k / n^2), g = floor(k / n)
mod n, b = k mod n; table value = row / out_max. The input range is 0..1.

APPLYING a table to a colour c: first, if there is a 1D table, per channel i:
x = clamp((c[i] - min[i]) / max(max[i] - min[i], 1e-9), 0, 1) * (n1 - 1); i0 = min(floor(x),
n1 - 2); c[i] = row[i0][i] + (row[i0 + 1][i] - row[i0][i]) * (x - i0). Then, if there is a 3D
table: normalise each channel as above to t in 0..1, v = t * (n - 1), cell index
i = min(floor(v), n - 2), fraction f = v - i, and interpolate TETRAHEDRALLY: with the eight
corners C(dr, dg, db) of the cell, C000 and C111, and the fractions (fr, fg, fb):

    fr > fg:   fg > fb:  w = (fr, fg, fb), P1 = C100, P2 = C110
               else fr > fb:  w = (fr, fb, fg), P1 = C100, P2 = C101
               else:          w = (fb, fr, fg), P1 = C001, P2 = C101
    else:      fb > fg:  w = (fb, fg, fr), P1 = C001, P2 = C011
               else fb > fr:  w = (fg, fb, fr), P1 = C010, P2 = C011
               else:          w = (fg, fr, fb), P1 = C010, P2 = C110
    result = C000 + w1 (P1 - C000) + w2 (P2 - P1) + w3 (C111 - P2)

all in binary32. Which effect applies the table, and to what encoding, is that effect's
definition (the catalog).

### 6.16 Shape layers

A layer whose `source.type` is `Shape` draws the items of its property group `contents`. The
children of `contents` are ITEMS: groups whose `match` says what they are. Every number of an
item is a property and may be animated; "the value of X" below means its value at the
composition time. Coordinates are layer pixels around the layer's origin (0, 0), y down.

The items of a list are processed from the FIRST to the last, and they act on what came BEFORE
them in the same list:

* a PATH item adds one path to the list's LIVE PATHS;
* a PAINT item (fill, stroke, gradient fill, gradient stroke) paints ALL the live paths that
  precede it in its list, together, as one shape;
* a PATH OPERATOR rewrites all the live paths that precede it - and what paints that come
  earlier in the list draw: a paint draws the paths as they are after EVERY operator of the
  list;
* a GROUP (`match` `group`) has its own list (`contents`) and a transform; its paths, after
  its transform, join the live paths of the list the group is in, so a paint that follows the
  group paints them too; its paints keep painting what they painted.

A disabled item (`enabled` false) is skipped. What is drawn FIRST in the list is IN FRONT: the
paints are composited in reverse order of appearance, the last one first (at the bottom).

PATH ITEMS (each has `direction`: Enum, 1 = every subpath reversed):

| `match` | properties | the path |
|---|---|---|
| `rect` | `size` (w, h), `position` (cx, cy), `roundness` | the rectangle of that centre and size (|w|, |h|), from its top-left corner clockwise on screen: (x0, y0), (x1, y0), (x1, y1), (x0, y1). `roundness` r = clamp(roundness, 0, min(|w|, |h|) / 2): with r > 0 the corners are quarter circles of radius r |
| `ellipse` | `size` (w, h), `position` (cx, cy) | four cubic arcs with handle length 0.5522847498 * radius: from the top point (cx, cy - h/2) clockwise on screen through (cx + w/2, cy), (cx, cy + h/2), (cx - w/2, cy) |
| `star` | `type` (Enum: 0 star, 1 polygon), `points`, `position`, `rotation`, `outerRadius`, `outerRoundness`, and for a star `innerRadius`, `innerRoundness` | n = round(max(points, 3)); a polygon has n vertices, a star 2 n alternating outer and inner. Vertex i is at angle (rotation - 90 degrees) + i * 360 degrees / (vertex count), measured clockwise on screen from +x, at its radius from `position`. With both roundness values 0 the sides are straight; a vertex with roundness q percent has tangents perpendicular to its radius of length radius * (2 pi / vertex count) * q / 400 |
| `path` | `path` (a Path value) | that path |

PAINT ITEMS. Each has `opacity` (percent) and `blend` (Enum: an index into the list of blend
modes in the order of section 6.9's table; 0 = Normal).

| `match` | properties | paints |
|---|---|---|
| `fill` | `color`, `rule` (Enum: 0 non-zero winding, 1 even-odd) | the inside of the live paths taken together, in `color` (its alpha is ignored: opacity is the `opacity` property) |
| `stroke` | `color`, `width`, `cap` (0 butt, 1 round, 2 square), `join` (0 miter, 1 round, 2 bevel), `miter`, and optional groups `dashes`, `taper`, `wave` | the set of points within width / 2 of the live paths, with those caps on open ends and those joins at corners; a miter join longer than `miter` * width / 2 from the corner is bevelled. `dashes`: `dash`, `gap` (and `dash2`, `gap2`, `dash3`, `gap3` when present; a gap of 0 equals its dash), `offset`: the pattern repeats along each path |
| `gfill` | `type` (0 linear, 1 radial), `start`, `end`, `colors` (a Gradient), `rule`, `highlightLength`, `highlightAngle` | as `fill`, the colour at point p taken from the gradient at position g(p) |
| `gstroke` | the stroke properties and the gradient properties | as `stroke`, coloured as `gfill` |

The gradient position, in the space of the list the paint is in: linear:
g = ((p - start) . (end - start)) / |end - start|^2; radial: g = |p - start| / |end - start|
(with a highlight length h not 0: the focal point is start + R * clamp(h / 100, -0.99, 0.99) in
direction atan2(end - start) + highlightAngle, R = |end - start|, and g = |p - focal| / (the
distance from the focal point to the circle of radius R around `start` along the ray through
p)). The colour of a Gradient at g (clamped to 0..1): the colour stops `[position, [r, g, b,
a]]` interpolated linearly between the two stops around g (the first stop's colour before it,
the last after), and its alpha multiplied by the opacity stops `[position, alpha]`
interpolated the same way.

GROUPS. A group's `transform` has `anchor` A, `position` P, `scale` S (percent), `rotation` r,
`skew` k, `skewAxis` x (degrees) and `opacity`. Its matrix, as 2D:

    G = T(P) * R(r) * K * S(S/100) * T(-A)          K = R(x) * | 1  tan(-k) | * R(-x)
                                                               | 0     1    |

R being the 2 x 2 rotation of section 6.7. The group's paths are transformed by G; the
opacity of its paints is multiplied by the group's opacity; a stroke's width is multiplied by
sqrt(|det G|); a gradient's `start` and `end` are in the group's own space. Groups nest.

REPEATER (`match` `repeater`: `copies`, `offset`, `composite` (0 below, 1 above), and
`transform` with `anchor`, `position`, `scale`, `rotation`, `startOpacity`, `endOpacity`).
With n = ceil(max(copies, 0)): everything before the repeater in its list - paths and paints -
is replaced by n copies; copy i (0..n-1) is transformed by

    M(j) = T(position * j) * T(anchor) * R(rotation * j) * S((scale/100)^j) * T(-anchor),  j = i + offset

its paints' opacity multiplied by startOpacity + (endOpacity - startOpacity) * i / (n - 1)
(startOpacity when n = 1), percent, and - for the last copy when `copies` has a fraction - by
that fraction. `composite` 0: copy 0 in front; 1: the last copy in front.

PAINTING. The layer's picture starts transparent. For each paint, from the LAST in drawing
order to the first: its COVERAGE c per pixel (the covered fraction of the pixel's area, as for
masks, section 6.10 step 1); source S = (colour.rgb, 1) * (c * opacity/100 * colour alpha),
premultiplied; blended over the picture with the paint's blend mode by section 6.9's rule
(mode `Normal`: S + D (1 - S.a)).

The picture is then the layer's source: masks, effects, transform and blend mode apply as for
every layer (section 6.11). Shapes stay sharp under scaling: the writing application
rasterises a shape layer in layer space magnified by a factor f - with s the larger of the
lengths the layer's matrix gives the unit x and unit y vectors at its anchor point,
f = 2^(ceil(4 log2(s) - 1e-6) / 4) clamped to 1/16..64 - and places that raster with the
bilinear sampling of section 6.9. A reader may equally compute coverage directly in
composition pixels; the two agree within the tolerance of section 6.20.

NOT DEFINED in this revision (carried as parameters; a reader draws the paths as they are
without the operator and says so): the path operators `trim`, `pucker`, `round`, `offset`,
`twist`, `zigzag`, `wiggle`, `merge`; the stroke options `taper` and `wave`; the two dissolve
modes as a paint's `blend`; the surface colour items of extruded shapes.

### 6.17 Text layers

A layer whose `source.type` is `Text` has a property group `text` with:

* `sourceText`: a `Text` value - the TEXT DOCUMENT: `text` (the characters; lines separated
  by U+000D or U+000A), document-wide character formatting (`font`, `style`, `size` in layer
  pixels per em, `fill`, `stroke`, `stroke_width`, `tracking` in 1/1000 em, `leading`,
  `baseline_shift`, scales, caps, `kerning`, OpenType features), paragraph formatting
  (`justify`, indents, spacing, `direction`, `composer`, `vertical`), `box_size` / `box_pos`
  for paragraph text (null: point text, laid out from the layer's origin), `runs` -
  `[{len, style}]`, consecutive stretches of characters with their own character formatting,
  `len` counting Unicode scalar values - and `paragraphs`. The schema's `$defs/text_doc` gives
  every field with its unit and default. A keyframe of `sourceText` holds a whole document;
  text does not interpolate.
* `pathOptions` (text along a mask path), `moreOptions`, and `animators`: per-character
  animation - each animator has `selectors` (range, wiggly or expression selectors that give
  each character an amount) and `properties` (what is changed by that amount: position,
  scale, rotation, opacity, fill colour...).

This revision carries text COMPLETELY and defines its layout NOT AT ALL: which glyphs a font
gives the characters, where lines break, where each glyph sits, and how animators move them,
are the writing application's text engine and are not specified here (section 8). A reader
shows the text by laying it out itself with the embedded font files (section 3.7) - it will be
the same words in the same fonts at the same sizes, and may differ in line breaks and glyph
positions - or shows the poster and strip pictures, in which the text is as the writer drew it.

### 6.18 Expressions

#### 6.18.1 What an expression is

A property's `expr` is `{text, enabled}`. `text` is a PROGRAM in the expression language,
carried verbatim - byte for byte what the person wrote. When `enabled` is true and the text is
not blank, the property's value at a composition time is the RESULT of evaluating the program,
which can read the property's keyframed value, the time, and the rest of the project. When the
evaluation fails, the property has its keyframed value.

#### 6.18.2 The language

The language is defined by the capsule's `expr-language` node, as far as this revision
defines it:

* `host_language`: it is ECMAScript (JavaScript), run as a sloppy-mode script; this package
  does not restate ECMAScript.
* `rewriting`: before a program runs, its text is rewritten so that `+ - * /` and unary minus
  work component-wise on arrays. The rule is stated completely.
* `names`: every name of the object model a program can use (267 of them), each with what it is
  a member of (`global`, `comp`, `layer`, `property`, `group`, `footage`, `marker`, `path`,
  `text-style`, `project`), its signature, and its meaning - in words for the names programs
  use most, and for the others by reference to the function of that name in the node's second
  file, `expressions/prelude.js`: the object model's source as the writing application runs it.
* `evaluation`: the inputs, what the result of a program is (the completion value of its last
  statement), how a result becomes a value of each kind, when an evaluation fails.
* `sandbox`: what a program cannot do, and its limits.
* `test_vectors`: 20 programs with the scene they run in, the time, and their results, for
  checking an implementation.
* `coverage`: what is and is not defined, in one paragraph. NOT defined: ECMAScript itself;
  the pseudo-random and noise generators behind `random`, `gaussRandom`, `noise`, `wiggle`,
  `temporalWiggle` (deterministic in the writing application, unspecified here); `sampleImage`.

A reader that implements the language evaluates expressions itself and can check its results
against the baked samples. A reader that does not uses the baked samples.

#### 6.18.3 What an application does with expressions, exactly

OPENING A FILE RUNS NO EXPRESSION. The writing application evaluates an expression only when
the value of its property is needed: to render a frame, to show the value, to export - which
an editor does as soon as it shows a composition - and when it saves, to write the baked
samples. An evaluation is a pure function of the document and the time: it cannot read or
write files, reach the network, start programs, or change the document; one outermost
evaluation with everything it reads is limited to 20 000 script runs, 5 seconds, and 16
levels of expressions reading expressions. The source file `expressions/prelude.js` and every
`expr.text` are DATA: no conformant tool executes them because they are in the file, and a
tool that lists, verifies, converts or archives a capsule never needs to.

#### 6.18.4 Baked samples

So that the animation an expression makes is in the file even for a reader with no expression
engine, a writer that can evaluate stores the RESULTS: for each composition with expressions,

* **`core.expr.baked`** - the properties whose results are numbers: one track per property,
  `kind` `scalar`, `vec2`, `vec3`, `color`, `bool` (0 or 1) or `enum` (the 0-based index), the
  samples as binary64. Layout and a dump: `spec/layouts/core.expr.baked.layout.txt`;
* **`core.expr.baked-values`** - the properties whose results are not numbers (text, paths,
  strings...): per property a run-length list `[{frames, value}]` of tagged values (section
  3.4).

Both are sampled at the same instants: sample i is the property's value at the START of
composition frame `first_frame + i * frame_step`; `samples` of them cover the whole
composition; `frame_step` is the smallest integer that keeps `samples` at or below 3600 (1 for
compositions up to 3600 frames). A track names its property by `layer` (the layer's id) and
`uid` (the property's). The header lists as `unbaked` every expression-driven property that
has no track, with the reason: `per-character` (an expression selector of a text animator,
evaluated per character, not per frame), `evaluation-failed`, `kind-changes`, `non-finite`.

A reader WITHOUT an expression engine takes a property's value at composition frame f from its
track: sample (f - first_frame) / frame_step when that is an integer; between samples (only
when frame_step > 1, or for a time inside a frame) the earlier sample - it does not
interpolate, because it does not know the function. A property that is `unbaked` has its
keyframed value.

The two nodes are derived (`measured`, section 3.9): `input_files` lists every authored
payload of the document an expression could read (compositions, layers, tracks, items, data
texts), `input_params` the composition, the frame plan and the engine. STALE samples (their
input hashes no longer match) must not be used as values of the current document.

WORKED EXAMPLE 5 (checkable). `Card`'s `rotation` (static value 20) has the expression
`value + time * 30`. Its baked track in `expressions/comp-111.baked.wkx` of the example
(layer 60, uid 70, kind `scalar`, 50 samples, first_frame 0, frame_step 1) begins

    sample  composition frame  tick           value
    0       0                  0              20.0
    1       1                  10160640000    21.2
    2       2                  20321280000    22.4
    3       3                  30481920000    23.6
    4       4                  40642560000    24.8
    5       5                  50803200000    26.0

and sample i is 20 + (i / 25) * 30.

### 6.19 Footage: from a medium to a layer's picture, and sound

A layer whose source is a footage item shows ONE FRAME of the item's medium, chosen by source
time s (section 6.2) and the item's interpretation:

* `Still`, `Model`, `Data`: the one picture (a `Data` item has none).
* `Video`: with r = `frame_rate` and N = round(duration * r.num / (TPS * r.den)) frames:
  frame index = clamp(floor(s * r.num / (TPS * r.den)), 0, N * max(loop_count, 1) - 1) mod N.
  `frame_rate` is the rate the item is INTERPRETED at; `native_rate`, when present, is the
  rate of the file's own timing, and frame k of the item is frame k of the file.
* `Sequence`: the same with N = the number of files; frame k is file k of the medium's node
  (section 3.6).
* With `fields` not `Off` (a `Video` or `Sequence`): fields are frames at twice the rate:
  F = floor(s * 2 r.num / (TPS * r.den)), at least 0; the file frame is floor(F / 2); the field
  kept is the UPPER one (rows 0, 2, 4...) when (F even) == (`fields` is `UpperFirst`), else
  the lower; each row of the other field is replaced by the mean of the rows above and below
  it (by the one neighbour at the top or bottom edge).
* With the layer's `switches.frame_blend` not `Off` and the composition's
  `enable_frame_blending` true, for `Video` and `Sequence`: with i = floor and w = the
  fractional part of s * r.num / (TPS * r.den): when w > 1e-6 the picture is
  frame i + (frame (i+1) - frame i) * w per component (`FrameMix`); `PixelMotion` synthesises
  an in-between picture by optical flow, which this revision does not define.

DECODING the frame is the definition of the medium's format (`MANIFEST.json` -> `formats`).
The decoded pixel (r, g, b, a) - components 0..1, an 8-bit value v as v / 255 - becomes a
premultiplied pixel by the item's `alpha`:

    Straight:        (r a, g a, b a, a)
    Premultiplied:   (max(0, r - m.r (1 - a)), max(0, g - m.g (1 - a)), max(0, b - m.b (1 - a)), a),
                     m = `premul_color` (the colour the file was premultiplied against)
    Ignore:          (r, g, b, 1)

then `invert_alpha` (a = 1 - a, colour kept straight) and `linear_light` (the file's values
are linear light: they are encoded with the curve of the item's colour profile, or sRGB) when
set; then the colour conversion of section 6.8. The picture is scaled to the item's `width` x
`height` layer pixels if the file's frame has another size (bilinear, section 6.9), and that
is the layer's source. A footage item that is offline (`media.node` null), or whose medium is
dead or in a format the reader cannot decode, has no picture: the layer draws nothing and the
reader names the item.

SOUND. A layer is heard when its `switches.audio` is true, it is active, and its source has
sound (a footage item with `has_audio`, or a nested composition that has): its sound is the
medium's sound from source time on, time-stretched with the layer, each channel multiplied by
10^(dB / 20) with dB from the property `audio/levels` (left, right; -96 or lower is silence);
a composition's sound is the sum of its layers'. The sample-exact arithmetic of the mix
(resampling to the project's `audio_sample_rate`, the block size at which levels are
evaluated, audio effects) is not defined in this revision (section 8).

### 6.20 A whole frame, worked

The example project (`spec/examples/motion-comp/stage.project.json` and the files beside it;
the same project is what `read_motion.py` is tested against) has one composition, `Stage`:
96 x 54 pixels, 25 fps, 2 seconds, 8 bits per channel, no colour management. Its layers,
front first:

1. `Badge` - a shape layer: one group with an ellipse (size 30 x 20 at (0, 0)) and a fill
   (1.0, 0.6, 0.2); blend mode `Screen`; position animated along the curved path of worked
   example 3.
2. `Card` - a 40 x 24 solid of colour (0.1, 0.3, 0.9) with one mask (five vertices, one curved
   side, mode `Add`, mask opacity 80 %); parent `Rig`; opacity as in worked example 1, position
   as in example 2, rotation from the expression of example 5; scale (120, 80).
3. `Rig` - a null layer (never drawn), turning (worked example 4).
4. `Back` - a 96 x 54 solid of colour (0.8, 0.1, 0.1), at the centre, unanimated.

Frame 10 (composition time 101 606 400 000) is made so:

* Start: 96 x 54 transparent pixels.
* `Back`: the solid's colour quantised to 8 bits is (204, 26, 26) / 255; its matrix is the
  identity (anchor and position are both the centre); after it every pixel is that colour
  with alpha 255.
* `Rig` has no picture.
* `Card`: a 40 x 24 picture of (26, 77, 230) / 255, alpha 255 [(0.1, 0.3, 0.9) quantised]; the
  mask's coverage times 0.8 multiplies every component; quantise; place through W(Card) of
  worked example 4 with bilinear sampling, the sampled pixel multiplied by the opacity
  94.73402149418061 / 100; blend `Normal`; quantise.
* `Badge`: position at frame 10 is exactly key 1: (48, 27). The ellipse's coverage times the
  fill colour (1.0, 0.6, 0.2), quantised, is placed by the translation; blend `Screen` (per
  channel B = b + s - b s in the frame of section 6.9); quantise.

The writing application's frame, as 8-bit RGB over black, row by row: sha256 `a309b453d9be35c183549980ccd4038ccfaf91d64ae094a3b67565e03d72872b`
(15552 bytes). Some of its pixels (x, y: r g b):

    ( 2,  2)  (204, 26, 26)    Back alone
    (48, 27)  (255, 179, 196)  the middle of Badge, over Card over Back
    (36, 27)  (255, 163, 72)   Badge over Back
    (41, 17)  (69, 65, 181)    Card over Back (the pixel holding layer point (8, 10) of Card)
    (33, 27)  (252, 155, 69)   on the outline of Badge
    (42,  9)  (204, 26, 26)    on the outline of Card's mask (its first vertex)

TOLERANCE. Anti-aliased coverage (masks, shapes) is the one place where two correct
implementations differ (section 6.10, step 1). A reader's frame AGREES with a reference frame
of the same document when, comparing 8-bit values: every FLAT pixel - one whose eight
neighbours in the reference frame all equal it - differs by at most 1 in each channel; every
other pixel by at most 40; and the mean absolute difference over all channels of the frame is
at most 0.5. `read_motion.py` computes coverage with 16 sub-scanlines per pixel row and exact
horizontal overlap, after flattening each curve to 24 chords; against the three frames of this
composition that its test compares (0, 10 and 31) its flat pixels are identical to the
writing application's and its other pixels differ by at most 20.

## 7. Writing a minimal valid `motion-comp/1` capsule

NORMATIVE. `spec/examples/motion-comp/write_minimal.py` (Python standard library, no other
software) does everything in this section; run

    python write_minimal.py <any existing motion-comp/1 capsule> <new.werk> [--tracks]

It takes from the existing capsule only what is the format itself - `spec/`, `loaders/`,
`README.txt`, `HOW-TO-READ.md`, and the manifest's constant parts - and writes everything
else. (CRAFT-BASE.md section 8 is the general recipe; this is its instance.)

### 7.1 The smallest project

One solid, and one composition with one layer that shows the solid and moves it: an 8 x 8
square travelling one pixel per frame across a 32 x 18 frame, 25 frames per second, 1 second.
Four payloads. Their bytes are fixed, so their sizes and hashes are checkpoints. Each is ONE
line of JSON: keys sorted by their UTF-8 bytes, no spaces, numbers as below, one line feed
(0x0A) at the end. (Any JSON spelling that satisfies the schemas is valid; this is the
spelling whose hashes are given.)

`project/project.json` - 280 bytes, sha256 `8f883448e669765bfbbf47824984dbd17214f3d82966116eaa4574d2e5c23ce4`:

    {"app_schema":2,"folders":[],"fonts":[],"items":[{"id":1,"kind":"solid","node":"item-1"},{"id":2,"kind":"comp","node":"comp-2"}],"next_id":11,"schema_version":1,"settings":{"audio_sample_rate":48000,"bit_depth":"Bpc8","frame_start":0,"linearize":false,"time_display":"Timecode"}}

`items/item-1.json` - 141 bytes, sha256 `9b77b7eb31ea760aa50999e6b1a3373c9f45867886589d11b5a1a37254c44bfe`:

    {"id":1,"kind":{"Solid":{"color":[1.0,0.5,0.25],"height":8,"pixel_aspect":1.0,"width":8}},"label":"None","name":"Square","schema_version":1}

`comps/comp-2/comp.json` - 347 bytes, sha256 `bf9ca3dae4b5b838e564f74a18e5925a95803d24055aa483e4c2c3509265200b`:

    {"comp":{"background":[0.0,0.0,0.0],"display_start":0,"duration":254016000000,"frame_rate":{"den":1,"num":25},"height":18,"motion_blur_samples":16,"pixel_aspect":1.0,"shutter_angle":180.0,"shutter_phase":-90.0,"width":32,"work_area":[0,254016000000]},"id":2,"label":"None","layers":[{"id":3,"node":"layer-3"}],"name":"Minimal","schema_version":1}

`comps/comp-2/layer-3.json` - 1191 bytes, sha256 `dd7e6c214469dbaa075eebbb15dd7c9c65a49328aae7f6b4d04b87db8a652ae2`:

    {"comp":2,"layer":{"blend_mode":"Normal","id":3,"in_point":0,"label":"None","name":"Square","out_point":254016000000,"props":{"children":[{"children":[{"match":"anchor","name":"Anchor Point","node":"Prop","uid":6,"value":{"t":"Vec3","v":[4.0,4.0,0.0]}},{"keys":[{"time":0,"value":{"t":"Vec3","v":[4.0,9.0,0.0]}},{"time":254016000000,"value":{"t":"Vec3","v":[29.0,9.0,0.0]}}],"match":"position","name":"Position","node":"Prop","uid":7,"value":{"t":"Vec3","v":[4.0,9.0,0.0]}},{"match":"scale","name":"Scale","node":"Prop","uid":8,"value":{"t":"Vec3","v":[100.0,100.0,100.0]}},{"match":"rotation","name":"Rotation","node":"Prop","uid":9,"value":{"t":"Scalar","v":0.0}},{"match":"opacity","name":"Opacity","node":"Prop","uid":10,"value":{"t":"Scalar","v":100.0}}],"match":"transform","name":"Transform","node":"Group","uid":5}],"match":"layer","name":"Square","uid":4},"source":{"item":1,"type":"Solid"},"start_time":0,"stretch":100.0,"switches":{"adjustment":false,"audio":true,"collapse":false,"effects":true,"frame_blend":"Off","guide":false,"locked":false,"motion_blur":false,"quality":"Best","sampling":"Bilinear","shy":false,"solo":false,"three_d":false,"video":true}},"schema_version":1}

The numbers: 254016000000 is one second in ticks. Ids 1 to 3 are the solid, the composition
and the layer; 4 to 10 are the layer's property groups and properties; `next_id` is 11. The
layer's root group has ONE child group, `transform`, with five properties; `position` has two
inline keyframes - at time 0 the value [4, 9, 0], at time 254016000000 the value [29, 9, 0] -
with nothing else stated, so both are `Linear` (the defaults of the schema). A property or
group this document does not write (masks, effects, the 3D rotations) is simply absent: an
absent property has its default, and an application that opens the file may add the groups it
wants to show.

What it means: the layer's anchor (4, 4) is the centre of the 8 x 8 square; at frame f
(0..24) its position is (4 + f, 9), so the square covers columns f .. f+7 and rows 5 .. 12.
FRAME 10 of the composition is therefore: pixels with 10 <= x < 18 and 5 <= y < 13 have the
solid's colour (1.0, 0.5, 0.25), which 8-bit quantisation makes (255, 128, 64) with alpha 255;
every other pixel is transparent (0, 0, 0, 0). As 32 x 18 x 4 bytes R G B A (straight alpha),
row by row, that frame has sha256 `af71f757edec05cce04efcf6ceba2946960385be5b8fcdad3e1188bf01d4732a` - an application that implements this
profile renders exactly these bytes, because nothing in this frame is anti-aliased.

With `--tracks` the two keyframes are NOT in the layer's JSON: the `position` property says
`"track":0` instead of `"keys":[...]`, the layer payload has `"tracks":"layer-3-keys"`, and a
fifth payload holds the keys:

`comps/comp-2/layer-3.keys.wkx` - 912 bytes, sha256 `a16742d394e98e7027bd91195cec32cc8c0268987e10658963d1f04b076fedb1`, written as
`spec/layouts/core.keyframe.tracks.layout.txt` says (that document's dump IS this file). The
layer payload is then 1104 bytes, sha256 `66e9fc14134cf254fe573e0476757e0575faa6235610370c498d8e817bee6fbd`. Both spellings are the same
project.

### 7.2 The nodes and edges

Besides the base nodes of CRAFT-BASE.md section 1 (`spec`, `license`, `readme`, the three
loaders, `revisions`):

| node_id | type | file | edges |
|---|---|---|---|
| `item-1` | `core.motion.item` | `items/item-1.json` | - |
| `layer-3` | `core.motion.layer` | `comps/comp-2/layer-3.json` | `enhances` `item-1` (role `source`); with `--tracks` also `enhances` `layer-3-keys` (role `keyframes`) |
| `layer-3-keys` (only with `--tracks`) | `core.keyframe.tracks` | `comps/comp-2/layer-3.keys.wkx` | `requires` `layer-3` (role `animates`) |
| `comp-2` | `core.motion.comp` | `comps/comp-2/comp.json` | `enhances` `layer-3` (role `layer`) |
| `project` | `core.motion.project` | `project/project.json` | `enhances` `item-1` and `comp-2` (role `contains`) |

Each node has one version: `v` 1, `epistemic` `authored`, `producer` (`tool`, `version`),
`created`, a `note` of at least 8 characters, and `files` with `path`, `sha256`, `size` (and
`media_type`: `application/json`, or `application/octet-stream` for the tracks file). `active`
is 1.

### 7.3 The manifest

Copied unchanged from the existing capsule: `werk`, `profile`, `manifest_schema`,
`conventions_map`, `conventions`, `profile_spec`, and `container` (with `form` set to `zip`,
`preview_prefix_bytes` removed, `total_size_bytes` = the sum of the sizes of all files other
than `MANIFEST.json`). Written new:

* `primary`: `{"document": "project"}` (no poster: optional);
* `license`: `{"file": "LICENSE", "sha256": ...}` for the licence text written;
* `schemas`: the entries of the copied map for the node types actually present;
* `layouts`: `{}`, or with `--tracks` the copied entry for `core.keyframe.tracks`;
* `formats`: `{}` - no payload is in a foreign encoding. The files under `spec/formats/` of
  the existing capsule (definitions of encodings its payloads used) are therefore NOT copied,
  and neither are its `core.tool` nodes; every other file under `spec/` is;
* `spec_sha256`: as SPEC.md section 2 defines it, over the `spec` node's files as written;
* `entity`: a new random `uuid` (version 4), `name`, `created`, `summary`;
* `nodes`; `generator`.

The revision record (`revisions/revision.json`): `{"schema_version": 1, "revision": 1, "kind":
"save", "note": ..., "created": ..., "producer": ..., "nodes": {<every node id except
revisions>: 1}}`.

### 7.4 The container and the check

A store-mode zip (method 0, no data descriptors, no zip64): `MANIFEST.json` first, then every
file in the order of `container.preview_tier` and, within a tier and after the tiers,
ascending by the UTF-8 bytes of the path.

Check the result with the reader that travels in it, and with the example reader:

    python loaders/werk_read.py new.werk --verify --strict
    python read_motion.py new.werk --frame 10 --out frame.rgba

The first must report every file verified. The second must write 2304 bytes whose sha256 is
the one given in 7.1. An application that implements this profile opens the file as a project
with one solid and one composition named `Minimal`, and shows the square crossing the frame.

Adding to it. A second layer is another `core.motion.layer` node listed in the composition's
`layers` (before `layer-3` to be in front of it). A mask is a group in a `masks` group of the
layer's root (section 6.10). An effect is a group in an `effects` group, with a
`core.effect.catalog` node describing its id (section 6.12). An imported picture is a
`core.media.png` node (or `core.media.source` with a `formats` entry and its definition
document), a footage item naming it, and a layer whose source is that item. A poster is a
`core.preview.poster` node (a PNG stamped `measured` with `input_files`) named by
`primary.image`.

## 8. What this profile deliberately does not have, and what this revision leaves undefined

DELIBERATE ABSENCES - decisions, not gaps:

* **No link to a file outside the package.** `origin` and `frame_origins` are notes for a
  person. There is no "project with linked media" form: a capsule that named bytes it does not
  carry would break when it is moved. A project whose media could not be read when it was
  saved says so item by item (`media.node` null) instead.
* **No executable content that runs on open.** Expressions and the object-model source are
  text; scripts and plug-in code are not carried at all. Automation scripts a person keeps
  beside a project are not part of the project and are not in the file.
* **No render output.** The render queue is carried (what was to be rendered, with which
  settings, to which path - the path a note); rendered movies are not.
* **No caches.** Disk caches, RAM previews, thumbnails of footage, waveform peaks: none. The
  three preview pictures are the only derived pixels, and they are stamped as derived.
* **No undo history.** The file holds saved revisions (section 4), not the editing steps
  between them.
* **No application preferences, window layout or workspace.** `x.effectcraft.view` holds only
  which compositions were open.
* **No subsetted or converted media.** A medium is the file that was imported, byte for byte.
  The file is as large as its media.

UNDEFINED IN THIS REVISION - carried completely as data, their rendering not specified. A
reader that meets one draws without it and SAYS so; a writer that rewrites the document keeps
it. Revision 2 of this profile may define them; a document does not change when they are
defined.

| what | where its data is | what a reader does |
|---|---|---|
| 180 of 306 effects (section 6.12 lists the ids) | the effect group's properties; schemas in the catalog | draws the layer without the effect |
| text layout: glyph choice, line breaking, glyph positions, text animators, text on a path | `text` group, section 6.17 | lays the text out itself, or shows the previews |
| layer styles (drop shadow, glows, bevel, overlays, stroke) | `layerStyles` group | draws the layer without them |
| shape path operators `trim`, `pucker`, `round`, `offset`, `twist`, `zigzag`, `wiggle`, `merge`; stroke `taper` and `wave`; dissolve as a paint's blend mode | `contents` items, section 6.16 | draws the paths unmodified |
| variable-width mask feather (`path.feather` points) | the mask's path | uses the plain `feather` property only |
| lights, shadows, material options; depth of field; the `Advanced3D` renderer (physically based shading, environment light, extrusion and bevel of text and shapes) | `lightOptions`, `materialOptions`, `geometryOptions`, `cameraOptions`; the composition's `renderer` | draws 3D layers as unlit planes through the camera (section 6.7) |
| 3D model layers and primitives; the model file formats (glTF, OBJ, FBX, STL...) | the layer's source; the medium, byte for byte | draws nothing for the layer |
| `PixelMotion` frame blending (optical flow) | `switches.frame_blend` | uses `FrameMix` |
| the sample arithmetic of the sound mix, and audio effects | section 6.19 | plays the media's sound by its own means |
| the random and noise generators of the expression language; `sampleImage` | `expr-language` -> `coverage` | uses the baked samples |
| the meaning of text media (`svg`, `gltf-json`, colour configurations...) and of media in `x.effectcraft.media` | the bytes | uses them if it knows the format from elsewhere |
| motion-tracker analysis (how tracks are computed) | the tracker groups hold the settings and the RESULTING keyframes | uses the keyframes; they are ordinary properties |
| Lottie (`core.motion.lottie`) | section 3.9 | hands the payload to a Lottie player, or ignores it |

Everything not in this table and not in the list of undefined effects is defined by sections
3 to 7, and a reader is expected to implement it or to refuse the node types it cannot
(section 5).

