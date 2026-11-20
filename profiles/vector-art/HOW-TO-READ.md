# How to read this file

This is a **werk capsule of profile `vector-art/1`**: one vector illustration document
(artboards, layers of paths, type and images) saved by VectorCraft or by any program that
follows `spec/PROFILE-VECTOR-ART.md`. Everything needed to read it is inside it. A `.werk`
file is an ordinary store-mode zip; a capsule directory is the same tree unzipped.

## The quick way: the readers that travel in the file

Python 3.8+, standard library only (unzip the file first, or run the scripts from a copy):

    python loaders/werk_read.py <file> --list                     every node, its type and files
    python loaders/werk_read.py <file> --verify --strict          re-hash every byte; exit 0 = intact
    python loaders/werk_read.py <file> --cat preview/artboard.png > preview.png      the picture
    python loaders/werk_read.py <file> --cat vector/document.json                    the structure

    python spec/examples/vector-art/read_document.py <file>       the whole document as JSON:
                                                                  artboards, layers bottom first,
                                                                  every object with its path, paints
                                                                  and text, image pixel hashes
    python spec/examples/vector-art/read_document.py <file> --revision 1      as first saved
    python spec/examples/vector-art/read_document.py <file> --images out/     also write the PNGs
    python spec/examples/vector-art/read_document.py <file> --originals out/  also write each image's
                                                                  own file (JPEG, TIFF, …)
    python spec/examples/vector-art/read_document.py <file> --decode out/     also decode every payload
                                                                  in a foreign format with the
                                                                  reference decoder this file carries

`preview/artboard.svg`, when present, is the first artboard as plain SVG with type as outlines:
any browser shows it.

## By hand

1. `MANIFEST.json` is the only index. `primary.document` names the structure node (node_id
   `document`); `primary.image` names the preview PNG.
2. For a node: `nodes[]` entry with that `node_id` → the entry of `versions[]` whose `v` equals
   `active` → its `files[]`. One file: that is the payload. Several: `payload_file` names it.
   Check the file's `sha256` and `size`.
3. The structure node's payload (`vector/document.json`) lists `artboards` and `layers` (bottom
   first) by node_id, and has tables for `symbols`, `patterns`, `images`, `fonts`.
4. A layer's payload is `{"schema_version": 1, "layer": <object>}`. A large one is stored
   compressed: the payload file is then `{"schema_version": 1, "external": {…}}` and the real
   payload is what the node's second file (`"role": "content"`, a zlib stream:
   `zlib.decompress` in Python) inflates to. Symbols and patterns likewise. An object is
   `{"id", "kind": {"type": …, …}, "appearance": {"items": [fills and strokes, bottom first]}}`;
   containers hold `kind.children`, bottom first.
5. A path is `kind.path.subpaths[].anchors[]`, each `{"p": [x, y], "in": [x, y], "out": [x, y]}`
   (handles absolute, absent = no handle). Segment A→B is the cubic Bézier
   `A.p, A.out, B.in, B.p`. Units are points (1/72 inch), y grows DOWN.
6. An image object names a `key`; the structure node's `images[]` gives the node with its
   pixels as a PNG (`node`) and, when the image came as a JPEG or the like, the node with those
   original bytes (`original`).
7. A payload that is a file in a format of its own (an image's JPEG, GIF, BMP, TIFF or WebP, a
   placed VectorCraft document, a font, an ICC profile) says which in its node's
   `meta.payload_format`. `MANIFEST.json` → `formats` maps that id to a definition document in
   `spec/formats/`: enough to write a decoder from, with test vectors to check it against. Its
   header says what it covers and what it does not (`coverage_note`), and names a reference
   decoder whose source is in `tools/`. Nothing runs those for you.

Every field of every payload is described in `spec/schemas/<node type>.schema.json`. The
narrative is `spec/PROFILE-VECTOR-ART.md`: §3 the node types, §4 the object model, §5 the
numeric conventions, §6 reading, §7 writing a minimal file (with
`spec/examples/vector-art/write_minimal.py`, which does it).

## Earlier versions

Every save is a revision with a work note. `revisions/` holds one record per save
(`spec/CRAFT-BASE.md` §3): record K maps each node_id to the version of that node the document
used at revision K. Superseded files keep their bytes under `name@N.ext`.

## What you may skip

Nodes whose type starts with `x.` hold what only VectorCraft interprets (its view state,
variables, graph and trace settings, brushes, previews of linked images). The artwork is
complete without them.
