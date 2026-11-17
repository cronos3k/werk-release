// Gate steps run INSIDE Photoshop 2020 (through COM .DoJavaScript, see tools/ps_run.py).
// WERK_ARGS = {task, in, out, outdir, template, log}. Writes <outdir>/<task>.json and
// returns its text. Only documents this script opens or creates are touched; they are
// all closed before it returns, and the document that was active before is made active again.
$.evalFile(new File(File($.fileName).parent.fsName + "/werk_ps_load.jsx"));
(function () {
  var DD = null, A = WERK_ARGS, out = { task: A.task, input: A["in"], ok: false, steps: [] }, mine = [], prev = null, t0 = new Date().getTime();
  var LOGP = A.log;
  werkPS.setLog(LOGP);
  function step(s) { out.steps.push(s); var f = new File(LOGP); f.encoding = "UTF-8"; f.open("a"); f.writeln(new Date().getTime() + " [gate] " + s); f.close(); }
  var temps = [];
  function own(d) { mine.push(d); return d; }
  function writeBin(p, b) { var f = new File(p); f.encoding = "BINARY"; f.open("w"); f.write(b); f.close(); }
  function closeMine() {
    var i;
    for (i = mine.length - 1; i >= 0; i--) { try { mine[i].close(SaveOptions.DONOTSAVECHANGES); } catch (e) { } }
    mine = [];
    for (i = 0; i < temps.length; i++) { werkPS.rm(temps[i]); }
    temps = [];
  }
  function layerDump(r, dir) {
    var i, list = [];
    for (i = 0; i < r.built.length; i++) {
      var b = r.built[i], e = { node_id: b.node_id, name: b.name, group: b.group, visible: b.visible };
      if (!b.group && b.item) {
        var px = werkPS.layerRGBA8(r.doc, b.item, {});
        e.file = dir + "/" + A.task + "-L" + (i + 1) + ".rgba"; writeBin(e.file, px);
        e.ps_name = b.item.name; e.ps_opacity = b.item.opacity; e.ps_visible = b.item.visible; e.ps_blend = String(b.item.blendMode);
        try { e.ps_fill_opacity = b.item.fillOpacity; } catch (x) { }
      }
      list.push(e);
    }
    return list;
  }
  function docLayers(doc) {
    var acc = [];
    (function walk(c) { var i; for (i = c.layers.length - 1; i >= 0; i--) { if (c.layers[i].typename === "LayerSet") { walk(c.layers[i]); } else { acc.push(c.layers[i]); } } })(doc);
    return acc;
  }
  try {
    prev = app.documents.length ? app.activeDocument : null;
    DD = app.displayDialogs; app.displayDialogs = DialogModes.NO;   // restored in finally
    out.docs_before = app.documents.length;
    out.host = { app: app.name, version: app.version, extendscript: $.version };
    var r, sd = A.outdir;
    if (A.task.indexOf("img-") === 0) {
      r = werkPS.openWerk(A["in"], { log: LOGP, scratch: A.outdir }); own(r.doc); if (r.temp) { temps.push(r.temp); }
      out.verdict = r.verdict; out.report = r.report; out.profile = r.profile;
      out.width = r.doc.width.as("px"); out.height = r.doc.height.as("px"); out.bits = String(r.doc.bitsPerChannel); out.mode = String(r.doc.mode);
      step("opened " + out.width + "x" + out.height);
      writeBin(sd + "/" + A.task + "-open.png", werkPS.compositePNG(r.doc, sd, false));
      step("open.png");
      if (A.direct) {   // the primary file extracted OUTSIDE Photoshop by the release library, opened by Photoshop directly
        var dd = own(app.open(new File(A.direct)));
        writeBin(sd + "/" + A.task + "-direct.png", werkPS.compositePNG(dd, sd, false));
        step("direct.png");
      }
      out.export_result = werkPS.exportImage(r.doc, A.out, { log: LOGP, scratch: A.outdir });
      step("exported " + A.out);
      closeMine();
      var r2 = werkPS.openWerk(A.out, { log: LOGP, scratch: A.outdir }); own(r2.doc); if (r2.temp) { temps.push(r2.temp); }
      out.reopen_verdict = r2.verdict;
      writeBin(sd + "/" + A.task + "-reopen.png", werkPS.compositePNG(r2.doc, sd, false));
      step("reopen.png");
    } else if (A.task.indexOf("rl-") === 0) {
      r = werkPS.openWerk(A["in"], { log: LOGP, scratch: A.outdir }); own(r.doc);
      out.verdict = r.verdict; out.report = r.report; out.profile = r.profile; out.counts = r.counts;
      out.width = r.doc.width.as("px"); out.height = r.doc.height.as("px"); out.bits = String(r.doc.bitsPerChannel);
      step("opened, " + r.built.length + " tree entries");
      out.layers = layerDump(r, sd);
      step("layers dumped");
      writeBin(sd + "/" + A.task + "-open.png", werkPS.compositePNG(r.doc, sd, true));
      if (A.export_layers !== "0") {
        out.export_layers = werkPS.exportRasterLayers(r.doc, A.out, { template: A.template, log: LOGP, scratch: A.outdir });
        step("exported raster-layers " + A.out);
      }
      out.export_image = werkPS.exportImage(r.doc, A.out_image, { log: LOGP, scratch: A.outdir });
      step("exported image " + A.out_image);
      closeMine();
      if (A.export_layers !== "0") {
        var r3 = werkPS.openWerk(A.out, { log: LOGP, scratch: A.outdir }); own(r3.doc);
        out.reopen_verdict = r3.verdict; out.reopen_counts = r3.counts; out.reopen_report = r3.report;
        out.reopen_layers = layerDump({ doc: r3.doc, built: r3.built }, sd + "/re");
        writeBin(sd + "/" + A.task + "-reopen.png", werkPS.compositePNG(r3.doc, sd, true));
        step("reopened");
        closeMine();
      }
      var r4 = werkPS.openWerk(A.out_image, { log: LOGP, scratch: A.outdir }); own(r4.doc); if (r4.temp) { temps.push(r4.temp); }
      out.reopen_image_verdict = r4.verdict;
      writeBin(sd + "/" + A.task + "-reopen-flat.png", werkPS.compositePNG(r4.doc, sd, false));
      step("reopened flattened");
    } else if (A.task === "selftest") {
      // the raster-layers module against the profile's own vectors, inside the host
      var t = werk.open(A.template);
      var raw = t.readFile("spec/examples/raster-layers/tiles.example.wkxz"), env = werkRaster.inflateZlib(raw), h = werk.readEnvelope(env).header, sec = null, i;
      for (i = 0; i < h.sections.length; i++) { if (h.sections[i].name === "samples") { sec = h.sections[i]; } }
      out.vector_decode_sha256 = werk.sha256Hex(werkRaster.undelta(env.substring(sec.offset, sec.offset + sec.size), h.channels.length, 1));
      var px = [], y, x, rows = [];
      for (y = 0; y < 256; y++) { px = []; for (x = 0; x < 256; x++) { px.push(String.fromCharCode(x, y, (x + y) % 256, 255)); } rows.push(px.join("")); }
      var sf = werkRaster.surfaceFilesRGBA8(rows.join(""), 256, 256);
      out.writer_tiles = { bytes: sf.tiles.length, sha256: werk.sha256Hex(sf.tiles) };
      out.writer_index = { bytes: sf.index.length, sha256: werk.sha256Hex(sf.index) };
      step("selftest done");
    }
    out.ok = true;
    out.written_before_close = true;
    writeBin(A.outdir + "/" + A.task + ".json", werk.jsonPretty(out));   // before closing: a host that hangs on close keeps the result
  } catch (e) {
    out.error = e.message + (e.line ? " (line " + e.line + ")" : "");
    step("ERROR " + out.error);
  } finally {
    closeMine();
    if (DD !== null) { app.displayDialogs = DD; }
    if (prev) { try { app.activeDocument = prev; } catch (e2) { } }
    out.docs_after = app.documents.length;
    out.png_save_for_web_fallbacks = werkPS.pngFallbacks();
    out.seconds = (new Date().getTime() - t0) / 1000;
  }
  var txt = werk.jsonPretty(out), f = new File(A.outdir + "/" + A.task + ".json");
  f.encoding = "BINARY"; f.open("w"); f.write(txt); f.close();
  return "done " + A.task + " ok=" + out.ok;
})();
