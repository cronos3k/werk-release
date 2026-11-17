// File > Scripts > Export werk...  (Photoshop 2020, ExtendScript)
// Exports the active document as a .werk package:
//   image/1          the visible composite as one PNG (Photoshop's encoder)
//   raster-layers/1  every pixel layer (u8 RGBA) + the composite; needs a template
//                    raster-layers/1 capsule to carry its spec/ from (see README.md)
#target photoshop
#include "werk_ps_load.jsx"
(function () {
  if (!app.documents.length) { alert("werk: no document is open"); return; }
  var doc = app.activeDocument;
  var layered = confirm("Export as raster-layers/1 (every layer)?\n\nYes: raster-layers/1   No: image/1 (flattened)");
  var out = File.saveDialog("Export werk package", "werk packages:*.werk");
  if (!out) { return; }
  var path = out.fsName.replace(/\\/g, "/");
  if (!/\.werk$/i.test(path)) { path += ".werk"; }
  try {
    var r;
    if (layered) {
      var tpl = $.getenv("WERK_RASTER_LAYERS_TEMPLATE");
      if (!tpl) { var t = File.openDialog("Choose a raster-layers/1 capsule to carry the profile's spec/ from", "werk packages:*.werk"); if (!t) { return; } tpl = t.fsName; }
      r = werkPS.exportRasterLayers(doc, path, { template: tpl.replace(/\\/g, "/") });
      alert("werk: wrote " + path + "\nraster-layers/1, " + r.layers + " layer(s), manifest sha256 " + r.manifest_sha256.substring(0, 16));
    } else {
      r = werkPS.exportImage(doc, path, {});
      alert("werk: wrote " + path + "\nimage/1, manifest sha256 " + r.manifest_sha256.substring(0, 16));
    }
  } catch (e) { alert("werk: export failed\n" + e.message); }
})();
