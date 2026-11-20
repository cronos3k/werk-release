# How to read this file

This is a werk capsule of profile `motion-comp/1`: a motion-graphics project - compositions
of layers, their animation, and every medium they use. It is a zip archive in store mode (or a
directory with the same files); any unzip tool opens it. You need no application.

## With the programs inside it (Python 3, standard library only)

    unzip project.werk -d project            (or use the .werk file directly below)

    python project/loaders/werk_read.py project.werk --verify
        lists every node and checks every file against its hash

    python project/spec/examples/motion-comp/read_motion.py project.werk list
        every composition, its layers (front first), parents, timing, blend modes,
        and every animated or expression-driven property

    python project/spec/examples/motion-comp/read_motion.py project.werk value <comp id> <layer id> transform/position <tick> ...
        a property's value at composition times in ticks (254016000000 ticks = 1 second)

    python project/spec/examples/motion-comp/read_motion.py project.werk frame <comp id> <frame> --out frame.rgba
        one frame rendered as width*height*4 bytes R G B A; it says what it could not draw

    python project/effects/effects_ref.py project.werk
        (present when the project uses an effect this format defines) implements those effects
        from their definitions in effects/catalog.json and checks itself against the test vectors

    python project/loaders/werk_read.py project.werk --cat media/<node id>/<file name> > original.file
        a medium, byte for byte as it was imported

Pictures of the project that need no rendering: `preview/poster.png` (one frame),
`preview/strip-<composition id>.png` (eight frames side by side).

## By hand

1. `MANIFEST.json` is the index. `primary.document` names the structure node (`project`);
   `nodes[]` lists every node with its files, sizes and sha256 values. The node `revisions`
   says which version of each node is the current document (`spec/CRAFT-BASE.md` section 3).
2. `project/project.json`: the settings, the folders, and `items` - which node holds which
   item. A `comp` item's node is a composition (`comps/comp-<id>/comp.json`); its `layers` list
   names the layer nodes, FRONT FIRST (`comps/comp-<id>/layer-<id>.json`).
3. A layer is JSON: what it shows (`source`), when (`in_point`, `out_point`, ticks), and a tree
   of properties under `props`. Find a property by its `match` path: `transform` ->
   `position`. Its `value` is the static value; `keys` are keyframes; `"track": i` means the
   keyframes are track i of the binary file named by the payload's `tracks`
   (`spec/layouts/core.keyframe.tracks.layout.txt` has a byte-by-byte example); `expr` is an
   expression - program text, never run by opening the file; its results are in
   `expressions/comp-<id>.baked.wkx` (`spec/layouts/core.expr.baked.layout.txt`).
4. A footage item (`items/item-<id>.json`) names its medium by `media.node`; the medium's files
   are that node's `files[]` in the manifest. `media.node` null: the file was not available
   when the project was saved.
5. What the numbers mean - time, interpolation between keyframes, transforms, blending, masks -
   is `spec/PROFILE-MOTION-COMP.md` section 6, with worked examples you can check. What an
   effect id means is in `effects/catalog.json`: its parameters and, for the effects this
   format defines, the arithmetic with test vectors. What is NOT defined (the other effects,
   text layout, 3D lighting) is listed in section 8 of that document.

To write such a file: section 7 of `spec/PROFILE-MOTION-COMP.md`, and
`spec/examples/motion-comp/write_minimal.py`, which does it with the standard library.
