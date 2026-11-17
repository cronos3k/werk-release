# werk for Photoshop 2020 (ExtendScript)

Two scripts for Adobe Photoshop 2020 (21.x, ExtendScript 4.5) that open and
export `.werk` packages, plus the modules they load. Pure ExtendScript (ES3),
no CEP panel, no native code, nothing downloaded.

| script | what it does |
|---|---|
| `Open werk.jsx` | **image/1**: the package's primary image (SPEC 2.1 `primary.image`, never `files[0]`), decoded by Photoshop's own PNG/JPEG reader. **raster-layers/1**: a layered RGB document: pixel layers (and the rendered caches of text / shape / smart layers), groups as layer groups, names, opacity, fill opacity, visibility, blend modes. Any other profile: its `primary.image`, said in the report. Every open is verified by the werk release library (sha256 of every file, Ed25519 signature); a damaged package still opens (law 3) and the verdict is shown. |
| `Export werk.jsx` | the active document as **image/1** (the visible composite as one PNG, Photoshop's encoder) or **raster-layers/1** (every pixel layer as a u8 RGBA surface + the composite as `primary.image`). |

## Files

```
Open werk.jsx, Export werk.jsx  the two user-facing scripts
werk_ps_load.jsx                loads the modules below from this folder
werk.jsx                        the werk release library, ES3 build: a byte-identical COPY of stage/libs/js/dist/werk.jsx
werk_raster.jsx                 raster-layers/1 surface decoder + u8 RGBA writer (port of the GIMP plug-in's werk_raster.py)
werk_ps_lib.jsx                 open / export
gate.py, gate_ps.jsx            the gate (outside / inside Photoshop)
tools/adobe_com.py              COM driver used by the gate (attach-only when Photoshop is already open)
tools/release_verify.py         one package through every release reader
tools/ref_werk_raster.py, tools/werk_single.py   the reference decoder the gate compares against (GIMP plug-in copy + release library copy)
GATE-RESULTS.md                 the last gate run
```

## Install

Nothing has to be installed to use them: **File > Scripts > Browse…** and pick
`Open werk.jsx` or `Export werk.jsx` in this folder. To get them as menu
entries under File > Scripts, copy the WHOLE folder's `.jsx` files (all of
them: the two scripts load their siblings) into
`C:\Program Files\Adobe\Adobe Photoshop 2020\Presets\Scripts\` and restart
Photoshop. (The gate did not do this; it runs the scripts from this folder.)

raster-layers/1 export needs a **template**: an existing raster-layers/1
capsule whose `spec/` (the profile text, schemas, layouts) is carried into
the new file (PROFILE-RASTER-LAYERS.md 7.3) - raster-layers/1 is not part of
the werk release's own `spec/`. Set `WERK_RASTER_LAYERS_TEMPLATE` to its path,
or the script asks for it. The only such capsules on the gate machine are the
ArtCraft PhotoCraft samples (`simple.werk` was the template in the gate).

## Use from a script

```js
#include "C:/path/to/plugins/photoshop/werk_ps_load.jsx"
var r = werkPS.openWerk("C:/in/thing.werk");          // r.doc, r.verdict, r.report, r.profile
werkPS.exportImage(app.activeDocument, "C:/out/flat.werk", {});
werkPS.exportRasterLayers(app.activeDocument, "C:/out/layers.werk", { template: "C:/t/simple.werk" });
```

Scratch files (the primary image handed to Photoshop, Photoshop Raw files of
layers) go to `_scratch/` in this folder (or `opts.scratch`); Raw and PNG files
are removed right after use, an opened primary when the caller closes it.

## Limits (stated, not hidden)

* **Speed.** ExtendScript is slow: opening verifies every byte with the
  library's pure-ES3 SHA-256 (roughly 0.1-0.2 MB/s on the gate machine; a
  10 MB package takes minutes), and Photoshop is blocked while a script runs.
  ExtendScript arrays become very slow beyond a few ten thousand elements
  (measured in Illustrator's identical engine: 10 000 pushes 74 ms, 80 000
  pushes 13.8 s), so every module here works in small chunks. The final release
  library (werk.jsx `b38b1990…`) has a linear inflate (about 0.4 MB/s in
  ExtendScript), used for layer tiles and deflated zip entries; earlier builds
  did not, and this plug-in carried its own inflate until then.
* **raster-layers/1 open:** cmyk and lab surfaces are not decoded (the layer is
  created empty and reported); 16-bit surfaces open in a 16-bit document
  (Photoshop's 16-bit mode is 0..32768, so the lowest bit is not kept);
  32-bit float surfaces are converted to 16 bits, clamped to 0..1; masks,
  clipping, layer effects, adjustment and fill layers are not applied (each is
  named in the report); blend modes without a Photoshop equivalent open as
  Normal; the composite is Photoshop's, not PhotoCraft's.
* **raster-layers/1 export:** pixel layers only, u8 RGBA (a 16-bit document is
  converted to 8 bits per layer), raw tiles, groups flattened to their
  children (group opacity / blend dropped), masks not written, text / shape /
  smart layers written as their pixels; needs a template capsule; unsigned.
* **image/1 export:** the visible composite as Photoshop writes PNG (16-bit
  documents give a 16-bit PNG); no thumbnail; unsigned.
* Gated in Photoshop 2020 (21.0.3) only. **Photoshop 2024 (25.11) is not
  gated**: it starts through COM `Photoshop.Application.180` when Photoshop 2020
  is closed, and the scripts' self-test passed inside it (ExtendScript 4.5.12),
  but under COM automation it refused PNG saves ("User cancelled the operation")
  and stopped answering at document close / between calls, so no complete run
  exists (`GATE-RESULTS.md`). The workarounds that are in the code (Action
  Manager PNG save with a PNG method, retries, Save for Web fallback, keeping
  the opened file until the document closes, plain scratch file names) are
  harmless in 2020. `py -3.12 gate.py --host photoshop2024` runs the gate there.
  A UXP plug-in for 2022+ is in `contrib/experimental/photoshop-uxp/` (repository root), untested.
* In a Photoshop started just for the gate (2020 or 2024) the first save of the
  session opens Photoshop's "Save As" dialog even with `DialogModes.NO`; run the
  gate (and batch use) in a Photoshop that has already saved once in its session.
* Exports save a merged copy as PNG (`saveAs`); if Photoshop refuses that, an
  Action Manager "save a copy" (PNG method set), then Save for Web PNG-24.
* An opened image/1 primary stays in `_scratch/` (Photoshop 2024 stalls when an
  open document's file disappears); delete the folder when no such document is open.
