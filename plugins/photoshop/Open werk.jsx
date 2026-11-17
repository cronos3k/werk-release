// File > Scripts > Open werk...  (Photoshop 2020, ExtendScript)
// Opens a .werk package: image/1 -> its primary image; raster-layers/1 -> a
// layered document. Every load is verified (hashes, signature); the verdict is shown.
#target photoshop
#include "werk_ps_load.jsx"
(function () {
  var f = File.openDialog("Open a werk package", "werk packages:*.werk,All files:*.*");
  if (!f) { return; }
  try {
    var r = werkPS.openWerk(f.fsName.replace(/\\/g, "/"));
    var msg = "werk " + r.profile + "\nverification: exit " + r.verdict.exit + ", signature " + r.verdict.signature +
              ", nodes alive/skipped/dead " + r.verdict.alive + "/" + r.verdict.skipped + "/" + r.verdict.dead;
    var lines = [], i;
    for (i = 0; i < r.report.length && lines.length < 25; i++) { if (r.report[i].severity !== "info" || r.report.length < 25) { lines.push("[" + r.report[i].severity + "] " + r.report[i].code + ": " + r.report[i].message); } }
    if (r.verdict.exit !== 0 || lines.length) { alert(msg + (lines.length ? "\n\n" + lines.join("\n") : "")); }
  } catch (e) { alert("werk: could not open " + f.fsName + "\n" + e.message); }
})();
