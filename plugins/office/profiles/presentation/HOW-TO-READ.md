# How to read this presentation

This file is a slide deck saved as a werk capsule, profile `presentation/1`. It is either one
`.werk` file — an ordinary store-mode zip — or the same tree as a directory. You need no
presentation application to read it. Everything below uses only what is inside it.

## The quick way (Python 3.8+, standard library only)

Unzip the file (or use the directory as it is), then:

    python spec/examples/presentation/read_presentation.py <the .werk file or directory>
        lists the slides: number, title, how many shapes, the layout

    python spec/examples/presentation/read_presentation.py <file> --text
        the text of every slide: title, body text by outline level, tables, speaker notes

    python spec/examples/presentation/read_presentation.py <file> --json out.json
        everything: every slide with its shapes (kind, box, text runs), notes, transition,
        animations, comments; the masters and layouts; every embedded file with its
        encoding, size and sha256

    python spec/examples/presentation/read_presentation.py <file> --media out_dir
        writes every embedded picture, sound and video to out_dir, byte for byte

    python spec/examples/presentation/read_presentation.py <file> --revision 1 --json old.json
        the same for an earlier saved revision (every Save is kept in the file)

    python loaders/werk_read.py <file> --verify          re-hashes every byte against MANIFEST.json
    python loaders/werk_read.py <file> --list            every node, its type and its files

Two files need no program at all: `preview/slide.png` is a picture of the first slide, and
`preview/outline.txt` is the text of every slide.

## By hand

1. `MANIFEST.json` is the only index. `primary.document` names the structure node; its file
   is `deck/document.json`: the slides in show order, the masters with their layouts and the
   embedded files, each as `{"id": …, "node": "<node id>"}`.
2. Each slide node (`slide-<id>`) has one JSON file, `{"schema_version": 1, "slide": {…}}`.
   `slide.shapes` is the list of shapes, bottom first. A shape has an `id`, a `name`, a box
   `xfrm` (`x`, `y`, `w`, `h` in points from the slide's top-left corner, y down), what it is
   (`kind.type`: `shape`, `picture`, `group`, `connector`, `table`, `chart`, `media`, `ink`,
   `opaque`) and its `text`: paragraphs of runs, each run with its `text`.
3. A member that is absent has its default, and `null` means "not set": a shape with no
   `fill` inherits one. `spec/PROFILE-PRESENTATION.md` section 4.6 says from where.
4. A picture names its file by a media id (`kind.fill.media`). `deck/document.json` →
   `media` maps the id to a node `media-<id>`; that node has two files: `asset.json` (what the
   file is) and the file itself, the one whose `role` in the manifest is `media`.
5. A shape's outline is a named preset (`geom.name`) or a path. The node
   `slide-<id>-geometry` lists the outline of every preset shape of the slide as a path, so
   you never need a table of presets.

## Where everything is defined

    spec/PROFILE-PRESENTATION.md        what every node means; drawing order, colour arithmetic,
                                        inheritance; how to WRITE such a file (section 7)
    spec/schemas/core.slide.*.json      every member of every JSON file, with units and defaults
    spec/schemas/core.media.asset.schema.json
    spec/formats/                       JPEG / GIF / BMP / TIFF / WebP / fonts / metafiles, if
                                        this deck embeds such files, each with a reference
                                        implementation in source under tools/
    spec/examples/presentation/         a real small payload of every kind, and the two scripts
    spec/CRAFT-BASE.md, spec/SPEC.md    the container, versions, signatures

Nothing in this file refers to anything outside it. A hyperlink on a slide, or the recorded
location of a linked video, is content: it is never needed to read the deck. An embedded
file whose descriptor says `"definition": "pending"` (a video, a compressed sound) is
carried exactly as it was embedded, and this file does not yet contain a definition of its
format: for a video see its poster frame (`media/posters/`), for a sound its first seconds as
plain WAV (`media/excerpts/`). XML under `x/deckcraft/ooxml/` is markup kept from an imported
file for exporting it again; nothing in it is needed to read the deck. A "program" action on
a shape is a record of what the author set: never run it.
