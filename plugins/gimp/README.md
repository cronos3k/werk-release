# file-werk — werk for GIMP 3

A Python-Fu 3 file plug-in for GIMP 3 (gated on GIMP 3.2.4, Windows, its
bundled Python 3.14.4). It registers two file procedures for the extension
`.werk`:

| procedure | what it does |
|---|---|
| `file-werk-load` (File > Open) | **image/1**: the package's primary image (SPEC 2.1 `primary.image`, never `files[0]`), decoded by GIMP's own loader for its format (PNG, JPEG, …). **raster-layers/1**: the layer tree — pixel layers, the rendered caches of text / shape / smart layers, groups, names, opacity × fill opacity, visibility, blend modes. The image opens at the deepest precision any layer has (u8 / u16 / float), so no layer is quantised on the way in. |
| `file-werk-export` (File > Export As…, `name.werk`) | argument `profile` = `image/1` (default): the visible layers merged into one 8-bit PNG inside an image/1 package (`werk.write_image_package`). `profile` = `raster-layers/1`: every pixel layer as a layer (u8 RGBA), plus the merged picture as `primary.image`; needs argument `template` (or `$WERK_RASTER_LAYERS_TEMPLATE`) = an existing raster-layers/1 capsule whose `spec/` and `loaders/` are copied in (PROFILE-RASTER-LAYERS.md §7.3). |

Every load is verified by the werk release library (hashes, Ed25519
signature); a package with errors still opens (law 3) and GIMP shows the
verdict. The entity uuid is kept in an image parasite (`werk-entity-uuid`) and
written back on export, so a re-export is a new version of the same entity.

## Files

```
plug-ins/file-werk/file-werk.py    the plug-in (GIMP requires folder name == script name)
plug-ins/file-werk/werk_single.py  the werk release library, a byte-identical COPY of libs/python/werk_single.py
plug-ins/file-werk/werk_raster.py  raster-layers/1 reader + writer (the writer uses werk_single.PackageWriter + add_spec_file)
gate.py, gate_in_gimp.py           the gate (outside / inside GIMP)
tools/release_verify.py            one package through every release reader
tools/werk_paths.py                where the release repo and libs are ($WERK_REPO, $WERK_LIBS)
GATE-RESULTS.md                    the last run
```

## Install

GIMP 3 loads plug-ins from the folders on its `plug-in-path`. Either:

* **copy** the folder `plug-ins/file-werk/` (all three .py files) into the
  `plug-ins` folder of your GIMP profile (`Edit > Preferences > Folders >
  Plug-ins` shows where that is), or
* add this folder's `plug-ins` directory to that list in
  `Edit > Preferences > Folders > Plug-ins` (GIMP stores it in your gimprc).

Restart GIMP. `File > Open` now accepts `.werk`; `File > Export As…` with a
`.werk` name selects "werk package". No pip, nothing downloaded.

For automation without touching a user profile, point GIMP at a profile
folder of your own: `GIMP3_DIRECTORY=<dir>` and a `<dir>/gimprc` containing

    (plug-in-path "${gimp_dir}/plug-ins;${gimp_plug_in_dir}/plug-ins;<this folder>/plug-ins")

(forward slashes; that is exactly what `gate.py` does).

## Use from scripts (batch)

```
gimp-console-3.2 -i -n -d -f -c --batch-interpreter python-fu-eval -b "<python>" --quit
```

```python
from gi.repository import Gimp, Gio
img = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(r"in.werk"))
proc = Gimp.get_pdb().lookup_procedure("file-werk-export")
cfg = proc.create_config()
cfg.set_property("run-mode", Gimp.RunMode.NONINTERACTIVE)
cfg.set_property("image", img)
cfg.set_property("file", Gio.File.new_for_path(r"out.werk"))
cfg.set_property("profile", "image/1")          # or "raster-layers/1" + "template"
proc.run(cfg)
```

Scratch: an image/1 primary is handed to GIMP's loader through one file in
`.werk-gimp-tmp/` beside the package (removed afterwards) or in
`$WERK_GIMP_TMP`; raster-layers pixels and every export go through memory.

## Limits (stated, not hidden)

* **image/1 export is 8-bit**: a 16-bit / float image is converted to
  R'G'B'A u8; RGB is written when every pixel is opaque, RGBA otherwise. No
  thumbnail is written. The PNG is zlib level 6, unfiltered — larger than
  most encoders' output (ista-varun: 5.4 MB source PNG → 9.7 MB package).
* **raster-layers/1 read**: cmyk and lab surfaces are not decoded (the layer
  is created empty and the report says `pixel-mode-cmyk-not-decoded` /
  `-lab-`); masks, clipping, layer effects, adjustment and fill layers are not
  applied (each is named in the report); blend modes without a GIMP
  equivalent (Reflect, Glow, Negation, Xor, DarkerColor, LighterColor,
  PaintNet*) open as Normal, and GIMP's modes are not the profile's §5.2
  formulas byte for byte, so the merged picture is GIMP's, not PhotoCraft's.
  GIMP makes duplicate layer names unique (`Levels` → `Levels #1`), and those
  suffixed names are what a re-export writes.
* **raster-layers/1 write**: pixel layers only, u8 RGBA, raw (uncompressed)
  tiles, groups flattened to their children (group opacity / mode lost),
  masks not written. Needs a template capsule for the profile's own spec
  files, which the werk release's `spec/` lacks (the only capsules on this
  machine are the ArtCraft PhotoCraft samples); spec/ and loaders/ otherwise
  come from the library. The loader records are narrowed to the capabilities
  the template's profile schema permits (see GATE-RESULTS.md).
* The interactive export dialog (`GimpUi.ProcedureDialog`) is written but was
  not run (see GATE-RESULTS.md).
* Exports are unsigned (`absent`).
