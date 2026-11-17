# werk for Illustrator 2020 (ExtendScript)

ExtendScript (ES3) for Adobe Illustrator 2020 (24.x) that opens and exports
`.werk` packages. No CEP panel, no native code, nothing downloaded.

| | what it does |
|---|---|
| open **vector-art/1** | builds the art in a new Illustrator document from the package's object model (PROFILE-VECTOR-ART.md section 4): artboards (rectangles, names), top-level layers and sublayers (name, visibility, lock, opacity, blend, printable, template), groups (with clipping), paths (anchors, both handles, smooth / corner, open / closed, fill rule; a multi-contour path becomes a compound path), compound paths, point and area type (text, font family / style, size, tracking, fill per run), images (the package's PNG placed and embedded through the object's transform), fills and strokes (solid RGB / CMYK / grey / Lab colour, linear / radial gradients by angle, width, cap, join, miter limit, dashes), opacity, blend modes, hidden, locked. Layer payloads stored apart (zlib, section 3.1) are inflated and checked against `external.bytes` / `external.sha256`. |
| open **image/1** | the primary image (SPEC 2.1 `primary.image`) opened by Illustrator. Any other profile with a `primary.image`: that image, said in the report. |
| export **vector-art/1** | the document's art in the same object model: one artboard node per artboard, one layer node per top-level layer, the structure node, `core.vector.preview` (the first artboard as Illustrator's PNG-24 export) and `core.vector.svg` (Illustrator's own SVG 1.1 export, type as outlines, images embedded) as `measured` renderings with their inputs, and the revision record. Rasters are written as images (their pixels rendered alone at 72 ppi). |
| export **image/1** | the first artboard as Illustrator's PNG-24 export. |

Every open is verified by the werk release library (sha256 of every file,
Ed25519 signature); a damaged package still opens (law 3).

## Files

```
werk_ai_load.jsx     loads the modules below from this folder (evaluate it at global scope)
werk.jsx             the werk release library, ES3 build: byte-identical COPY of stage/libs/js/dist/werk.jsx
werk_ai_lib.jsx      open / export (werkAI.openWerk, exportVectorArt, exportImage, dumpDocument)
gate.py, gate_ai.jsx the gate (outside / inside Illustrator)
tools/adobe_com.py   COM driver (attaches to a running Illustrator, else starts and quits its own)
tools/release_verify.py  one package through every release reader
GATE-RESULTS.md      the last gate run
```

## Install / use

Illustrator 2020 runs any script from **File > Scripts > Other Script…**; there
is no File > Open hook for a script format, so the entry points are:

```js
// File > Scripts > Other Script... on a small file like this one, or the ExtendScript of your own panel:
$.evalFile(new File("C:/path/to/plugins/illustrator/werk_ai_load.jsx"));
var r = werkAI.openWerk("C:/in/drawing.werk");                       // r.doc, r.verdict, r.report
werkAI.exportVectorArt(app.activeDocument, "C:/out/drawing.werk", { template: "C:/t/neon-drive.werk" });
werkAI.exportImage(app.activeDocument, "C:/out/drawing-preview.werk", {});
```

To get menu entries, copy all `.jsx` files of this folder into
`C:\Program Files\Adobe\Adobe Illustrator 2020\Presets\en_US\Scripts\` and add
two three-line scripts that call `werkAI.openWerk(File.openDialog(...))` and
`werkAI.exportVectorArt(...)`; the gate did not install anything.

vector-art/1 export needs a **template**: an existing vector-art/1 capsule
whose `spec/` (PROFILE-VECTOR-ART.md, schemas, format definitions) is carried
into the new file, because vector-art/1 is not part of the werk release's own
`spec/` (the GIMP and Photoshop plug-ins do the same for raster-layers/1). The
gate used the ArtCraft VectorCraft sample `neon-drive.werk`.

## Limits (stated, not hidden)

* Not built on open (each named in the report, the rest of the document
  opens): symbol instances, blends, envelopes, meshes, repeats, placed
  documents, pattern paints, live effects (glows, shadows ...), opacity masks,
  text wraps, more than one fill or stroke per object (the top one of each is
  kept), on-path type (opened as point type), per-paragraph styles, gradient
  geometry (placed by angle only), symbols and patterns as resources.
* Fonts: matched by family and style among the fonts installed; a missing
  font is substituted by Illustrator and reported. Embedded fonts in the
  package are not installed.
* Export writes paths, compound paths, groups (clipping), layers / sublayers
  (sublayers are listed after the layer's own items: Illustrator's DOM does not
  give one stacking order for both), point and area type (one run per
  paragraph, attributes of its first character), rasters and placed images as
  images (pixels rendered alone at 72 ppi, not the original file), solid and
  gradient paints. Items and sublayers of one layer are ordered by Illustrator's
  `absoluteZOrderPosition` (an empty sublayer goes on top). Not written: symbols, meshes, plugin art, live effects,
  pattern paints (written as none), graphic styles, swatches.
* Coordinates are Illustrator's document coordinates with y flipped
  (vector-art/1 is y down).
* Speed: ExtendScript's SHA-256 verifies roughly 0.1-0.2 MB/s, so opening a
  3 MB package takes minutes on a loaded machine; very large documents (the
  20 000-path sample, `--big` in the gate) were not run.
* Exports are unsigned.
* Coordinates beyond Illustrator's canvas (|x| > 16 383 pt) cannot be represented: a
  path with such coordinates opens clamped by Illustrator, and a number Illustrator
  then reports as infinite or past 2^53 is written as a binary64 / 0 and counted
  (`number-out-of-range`).
* Illustrator 2020 stopped answering inside a script call 5 times during this work's
  ~11 gate runs (four times with a crash-dump child process); the same steps passed
  otherwise. For batch use, run one document per Illustrator instance.
