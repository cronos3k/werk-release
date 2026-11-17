# werk for After Effects 2020 (ExtendScript)

ExtendScript (ES3) for Adobe After Effects 2020 (17.x). No CEP panel, no
native code, nothing downloaded.

| | what it does |
|---|---|
| import **image/1** as footage (`werkAE.importImage`) | the package's primary image (SPEC 2.1 `primary.image`) becomes a footage item named after the entity; its comment records the package path, entity uuid, payload path and sha256. Any other profile with a `primary.image`: that image, reported. |
| export a comp frame to **image/1** (`werkAE.exportCompFrame`) | `comp.saveFrameToPng` at the given time, packed by the werk release library (`writeImagePackage`). |
| import **motion-comp/1** (`werkAEMotion.importProject`) - PARTIAL | folders, solid and footage items, compositions (size, pixel aspect, frame rate, duration, background), layers (Solid, Footage, nested Comp, Null, Camera, Light, Text with its text, size, fill colour and tracking; Shape layers EMPTY; Model / Primitive as nulls), timing (start, in, out, stretch), blend mode, switches (video, 3D, shy, locked), parenting, the transform group's static values and keyframes (inline or the `WKX3` tracks node, Linear / Bezier / Hold). See "Limits". |

Every import is verified by the werk release library (sha256 of every file,
Ed25519 signature); a damaged package still imports (law 3).

motion-comp/1 EXPORT is not implemented. The profile was written from After
Effects' own data model (the property tree, `match` names, ticks, WKX3 key
tracks map one to one), so the mapping is clean in principle; what it takes
is a writer for the property tree, the key tracks and the medium nodes, and a
template capsule for the profile's `spec/` - not done in this pass.

## Files

```
werk.jsx             the werk release library, ES3 build: byte-identical COPY of stage/libs/js/dist/werk.jsx
werk_ae_lib.jsx      image/1 import / frame export
werk_ae_motion.jsx   motion-comp/1 partial import
gate.py, gate_ae.jsx the gate (outside / inside After Effects)
tools/release_verify.py  one package through every release reader
GATE-RESULTS.md      the last gate run
```

## Install / use

**File > Scripts > Run Script File…** runs any `.jsx`; to have entries under
File > Scripts, copy the `.jsx` files into
`C:\Program Files\Adobe\Adobe After Effects 2020\Support Files\Scripts\`.
The gate installed nothing; it runs `AfterFX.exe -noui -r <runner.jsx>`.

```js
$.evalFile(new File("C:/path/to/plugins/aftereffects/werk.jsx"));
$.evalFile(new File("C:/path/to/plugins/aftereffects/werk_ae_lib.jsx"));
$.evalFile(new File("C:/path/to/plugins/aftereffects/werk_ae_motion.jsx"));
var r = werkAE.importImage("C:/in/picture.werk", {});        // r.item: the FootageItem
werkAE.exportCompFrame(app.project.activeItem, 0, "C:/out/frame.werk", {});
var m = werkAEMotion.importProject("C:/in/intro.werk", {});   // m.comps, m.report
```

Footage is a link to a file on disk, so imported media are extracted to
`_media/` in this folder (or `opts.mediaDir`), named by the sha256 of their
bytes, and kept (the project needs them). `_scratch/` holds a frame only
while it is being packed.

## Limits (stated, not hidden)

* `comp.saveFrameToPng` is asynchronous in 17.0; the library waits until the
  file's size is stable (up to 2 minutes).
* image/1 export: an 8-bit PNG as After Effects writes it; no thumbnail; unsigned.
* motion-comp/1 import does not build: shape contents, masks, effects, layer
  styles, text font face, animators and paragraph settings (text, size, fill colour and tracking ARE set), expressions, temporal and spatial eases
  / tangents (Bezier keys keep After Effects' default ease), markers, track
  mattes, time remapping, audio levels, camera and light options, essential
  properties, the render queue. Each is named in the report.
* Only After Effects 2020 (17.0.2) was run. `app.quit()` does not exit 17.0 in
  `-noui` mode; the gate ends the process it started.
