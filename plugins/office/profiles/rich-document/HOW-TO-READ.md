# How to read this file

This is a **werk capsule** of profile `rich-document/1`: a rich-text document (text with
formatting, tables, pictures, headers and footers, footnotes, comments, tracked changes) and
every state it was ever saved in. You need no application. Everything below works with
Python 3.8+ and its standard library, using readers that are inside this file.

A `.werk` file is an ordinary store-mode zip; a directory capsule is the same tree unzipped.
Replace `FILE` by either. To get the readers out of a zip first:
`python -m zipfile -e FILE out/` (in a directory capsule they are already there, and `out/` is
the capsule).

## Get the content out

    python out/spec/examples/rich-document/read_document.py FILE
        what the document holds: paragraphs, tables, stories, pictures, revisions

    python out/spec/examples/rich-document/read_document.py FILE --text
        the body as plain text, one line per paragraph or table row

    python out/spec/examples/rich-document/read_document.py FILE --extract DIR
        text.txt, every picture and every font file, written into DIR

    python out/spec/examples/rich-document/read_document.py FILE --revision 3 --text
        the same for the document as it was at saved revision 3

    python out/loaders/werk_read.py FILE --list
        every node of the package (any werk capsule, any profile)

    python out/loaders/werk_read.py FILE --verify --strict
        re-hashes every byte; exit status 0 means nothing is damaged

    python out/loaders/werk_read.py FILE --cat preview/page-1.png > page-1.png
        page 1 as a picture (present unless the file was written without a preview)

## The same thing without the readers

1. `MANIFEST.json` → `primary.document` is a node id. Find that node in `nodes[]`; take the
   entry of its `versions[]` whose `v` equals the node's `active`; it lists one file. `path` is
   where it is, `sha256` what it must hash to. (Where a version lists several files,
   `payload_file` or the file with `role: "payload"` is the payload — never assume the first.)
2. That file is JSON, the document's STRUCTURE: `body` is an array of node ids in reading
   order; `stories` lists the headers, footers, footnotes, endnotes, comments and text boxes;
   `media` lists the pictures.
3. For each id in `body`: find the node and its active version. It lists two files. The one
   with `role: "payload"` is a small JSON header. The one with `role: "blocks"` is a zlib
   stream (RFC 1950: `zlib.decompress` in Python, `inflate` anywhere; `spec/formats/zlib-deflate.md`
   defines it byte by byte and `tools/format-zlib-deflate-reference/inflate.py` is a decoder
   in source). Inflated, it is JSON: an array of blocks. Concatenate the arrays of all of them
   in the order of `body`: that is the document's text. A block is a paragraph
   (`"kind":"para"`: `text`, and `runs` that give each stretch of the text its formatting) or
   a table (`"kind":"table"`: `rows` → `cells` → `blocks` again).
4. In a paragraph's `text`, the character U+FFFC marks an inline object: the k-th U+FFFC is
   `objects[k]` (a picture, a footnote reference, a field …). `runs[].len` counts UTF-8 BYTES.
5. A picture object names a `key`; the structure's `media` entry with that key names the node
   that holds the bytes: `original` (a JPEG, GIF, BMP, TIFF, WebP, EMF or WMF, verbatim —
   `spec/formats/` defines each encoding and `tools/` holds a reference reader), and / or
   `image` (a PNG: the picture itself, or — for a WebP, a metafile and anything else the
   definitions here do not decode to pixels — a decoded copy of the original).
6. The structure's `fonts` lists the fonts the document is set in. A row with
   `"status":"embedded"` names the node that holds the font FILE (TrueType / OpenType,
   verbatim; `spec/formats/sfnt.md`): install or load it to see the document as it was laid
   out. A row with `restricted` or `missing` is a name only: that font could not travel.
7. A file that is missing or does not hash to its `sha256` belongs to a dead node: skip that
   node, keep the rest, and say which node it was.

If you only want the words: the files under `preview/text/` are the body's plain text, one
zlib stream per entry of `body`, named in the structure's `plainText` in the same order;
inflate and concatenate.

## Earlier versions of the document

Every Save is kept. `revisions/` holds one small JSON record per Save, with a note saying why
it was made; the record's `nodes` object says which version of each node the document used
then. To read the document as it was at revision K, use those version numbers instead of
`active`. `spec/CRAFT-BASE.md` §3 and §4 give the exact rules, including where the bytes of an
earlier version of a file live (`name@N.ext`).

These saved versions are not "tracked changes". Tracked changes (text marked as inserted or
deleted by a named author) are part of the document's content, in every version of it; see
`spec/PROFILE-RICH-DOCUMENT.md` §4.

## Everything else

    spec/PROFILE-RICH-DOCUMENT.md   every node type, the conventions, how to WRITE a valid file
    spec/schemas/core.text.*.json   every field of every payload, with units and meaning
    spec/examples/rich-document/    a worked example of every payload; a reader; a writer
    spec/formats/                   the definition of each format a file here is in: the text
                                    compression, the picture encodings, fonts, containers
    spec/CRAFT-BASE.md              the rules all ArtCraft capsules share
    spec/SPEC.md                    the werk container, manifest, signatures
    spec/MINI-SPECS.md              zip, JSON, PNG, SHA-256, Ed25519, byte by byte
