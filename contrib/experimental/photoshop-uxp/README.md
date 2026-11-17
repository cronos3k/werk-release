# werk UXP plug-in for Photoshop 2022+ — EXPERIMENTAL, UNTESTED

**Not loaded or run in any Photoshop.** A manifest v5 command plug-in (`manifest.json`,
`index.js`) using the werk release library `werk.js` (Uint8Array build, byte-identical copy
of `libs/js/dist/werk.js`, sha256 `563b89c2…`):

* **Open werk package…** - verifies the package, writes its `primary.image` to the
  plug-in's temporary folder and opens it with Photoshop.
* **Export as werk image/1…** - saves a PNG copy of the active document
  (`doc.saveAs.png`) and packs it with `werk.buildImagePackage`.

Why untested: the UXP Developer Tool is not installed. `gate_uxp.py` (pack `werk-uxp.ccx`,
install it with `UnifiedPluginInstallerAgent /install`, start Photoshop 2024, let the
plug-in's load hook run the image/1 fixtures listed in `_selftest/request.json`, remove it
with `/remove`) was written but NOT run, because Photoshop 2024 under COM automation did not
complete even the ExtendScript gate reliably on the gate machine (`plugins/photoshop/GATE-RESULTS.md`).
`UnifiedPluginInstallerAgent /list all` showed 0 extensions for Photoshop 2024 (25.11.0);
nothing was installed.

Open points: `fs.createEntryWithUrl` needs UXP 7 (Photoshop 24.2+); the self-test hook is off
until `SELFTEST` in `index.js` is set to an absolute folder; no raster-layers/1; the export may meet the same refused saves
("User cancelled the operation") the ExtendScript plug-in met in Photoshop 2024.
