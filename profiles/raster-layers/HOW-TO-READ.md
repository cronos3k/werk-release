# How to read this file

This is a **layered raster image document** (werk profile `raster-layers/1`): a canvas and a
stack of layers with their pixels, masks, blend modes and effects. It was saved by a
raster-layers/1 writer, and it carries everything needed to read it without that program.

If the file is a single `.werk`, it is an ordinary ZIP archive stored without compression:
unzip it, or read it in place. If it is a directory, you are already looking at the contents.

## The picture, in one step

`preview/composite.png` is the whole document flattened to one image (8-bit sRGB, straight
alpha, scaled down to the size its node's `meta` states). `preview/thumbnail.png` is a smaller
one. Any image viewer opens them. (Find them properly through `MANIFEST.json` → `primary.image`
/ `primary.thumbnail` → that node → its active version → its file; a document saved without a
rendering has neither.)

## Everything, with the reader inside the file

No installation; Python 3.8 or newer, standard library only:

    python loaders/werk_read.py <this file> --verify --strict                 every file's sha256; exit 0 = sound
    python loaders/werk_read.py <this file>                                   every node: id, type, files
    python loaders/werk_read.py <this file> --cat document/document.json      the document structure (JSON)
    python loaders/werk_read.py <this file> --cat layers/layer-1/layer.json   one layer's properties (JSON)
    python loaders/werk_read.py <this file> --envelope surfaces/layer-1-pixels/surface.wkx
                                                                              a surface's header and sections
    python loaders/werk_read.py <this file> --extract layer-1-pixels --out <dir>
                                                                              the files of one node

(`--cat` and `--envelope` take a file path as `MANIFEST.json` lists it; `--extract` takes a
node id. The layer numbers above are examples: take real ids from the listing.)

(`loaders/werk_read.rs` and `loaders/werk_read.c` do the same; build lines are in each node's
`meta` in `MANIFEST.json`.) The reader knows the container, the hashes and the binary
envelope; it does not know what a layer is. That part is below.

## The layers and their pixels, by hand

1. **`MANIFEST.json`** is the only index. `nodes[]` lists every unit: `node_id`, `type`,
   `versions[]` (each with `files[]`: `path`, `sha256`, `size`, sometimes `role`), and
   `active`, the number of the version in use. Always go node → active version → file; never
   guess a path.
2. **The structure**: the node named by `primary.document` (its id is `document`). Its one
   file is JSON: `width`, `height`, `color_mode`, `sample_type`, and `layers` — the layer
   tree, **bottom layer first**; an entry with `children` is a group.
3. **A layer**: each tree entry's `layer` is a node id (`layer-<n>`). Its one file is JSON:
   `name`, `visible`, `blend`, `opacity`, `mask`, `effects`, and `content`, whose `kind` is
   one of `raster`, `group`, `adjustment`, `fill`, `text`, `shape`, `smart`.
4. **Its pixels**: `content.pixels` (a pixel layer) or `content.cache` (the rendered picture
   of a text, shape or smart-object layer) is the node id of a *surface*. A surface node has
   an index file — the one its version's `payload_file` names, or its only file — and tile
   files. Both are werk binary envelopes: 4 bytes magic `WKX0`, `u32` version, `u32` header
   length, a MessagePack header, then raw little-endian arrays at offsets the header declares.
   A tile file that does not begin with `WKX0` is a **zlib stream** of such an envelope:
   inflate it first (Python: `zlib.decompress`; the node's `meta.file_formats` names the
   format, `zlib-deflate`, and `MANIFEST.json` `formats` points to its definition and a
   reference inflater inside this file).
   * The index header gives `pixel_mode` (`rgb`, `grayscale`, `cmyk`, `lab`, …), `channels`
     (e.g. `["red","green","blue","alpha"]`), `sample_type` (`u8`, `u16`, `f32`) and
     `tile_files`. Its section `tile-index` is rows of four `i32`: tile x, tile y, which tile
     file, which slot. Its section `default-pixel` is the pixel everywhere no tile is.
   * A tile file's section `samples` is tiles of 256 × 256 pixels, one after another, rows top
     to bottom, the samples of each pixel together. When the tile file's header says
     `sample_encoding` `planes-delta`, each tile is stored as byte planes of differences;
     undo that first — for one 8-bit channel it is a running sum of the bytes modulo 256,
     and `spec/layouts/core.raster.surface.layout.txt` §5.2 gives the general dozen lines. Tile (tx, ty) covers pixels x from 256·tx,
     y from 256·ty; (0, 0) is the canvas's top-left corner and y grows downward.
   * To find tile file k: `tile_files[k]` is a *role*; the file of the same node version whose
     `role` equals it is the one.

That is all it takes to get every layer's exact pixels. The complete rules:

| you want | read |
|---|---|
| the whole format of this kind of document, and how to WRITE one | `spec/PROFILE-RASTER-LAYERS.md` (reading: §6; writing: §7) |
| every field of a JSON file, with units and ranges | `spec/schemas/<node type>.schema.json` (`MANIFEST.json` → `schemas`) |
| every byte of a surface | `spec/layouts/core.raster.surface.layout.txt`, with a worked example in `spec/examples/raster-layers/` |
| the envelope and its MessagePack subset | `spec/layouts/ENVELOPE.layout.txt` |
| an embedded original (a placed or linked PNG, JPEG, GIF, BMP, TIFF, WebP, PDF, Photoshop or werk file, the ICC colour profile, the EXIF block) or a font the text is set in | its node (type `core.raster.source`, or `core.text.font` for a font: the structure node's `fonts` says which faces are embedded and which are only named) → `meta.payload_format` → `MANIFEST.json` `formats` → `spec/formats/<id>.md`: a definition a decoder can be written from, with test vectors; its reference decoder's source is the node named by the definition's `reference_tools` (`tools/…`, Python, never run automatically) |
| an original in a format this file has no definition for (type `x.photocraft.source.<format>`: PhotoCraft's earlier bundle, a file nobody could identify) | `spec/layouts/x.photocraft.source.<format>.layout.txt` names the public standard; `spec/PROFILE-RASTER-LAYERS.md` §3.13 says what is also present as plain pixels |
| a placed SVG (type `core.raster.source-svg`) | its one file is the SVG document, UTF-8 text |
| the container, hashes, versions, signatures | `spec/SPEC.md`, `spec/CRAFT-BASE.md`, `spec/MINI-SPECS.md` |

## Earlier versions of the document

Every Save is kept. `revisions/` holds one small JSON record per Save (node `revisions`,
one version per Save, newest = active): its `note` says why that Save was made and its `nodes`
maps each node id to the version of that node the document used then. To see the document as
it was, read each node at that version instead of its active one (a superseded file has `@N`
in its name; resolve it through the node's `versions[]`, never by guessing the name).

## Damage

Each file is hashed in the manifest. A file that fails its hash costs the node it belongs to
— one layer's pixels, one mask — and nothing else: read the rest, and say what is missing.
