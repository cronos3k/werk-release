// Gate steps run INSIDE Illustrator 2020 (COM .DoJavaScript, see tools/ai_run.py).
// WERK_ARGS = {task, in, out, out_image, outdir, template, log}. Writes <outdir>/<task>.json.
// Only documents this script creates are touched; all are closed before it returns.
$.evalFile(new File(File($.fileName).parent.fsName + "/werk_ai_load.jsx"));
(function () {
  var A = WERK_ARGS, out = { task: A.task, input: A["in"], ok: false, steps: [] }, mine = [], t0 = new Date().getTime();
  function step(s) { out.steps.push(s); var f = new File(A.log); f.encoding = "UTF-8"; f.open("a"); f.writeln(new Date().getTime() + " [gate] " + A.task + ": " + s); f.close(); }
  function writeBin(p, b) { var f = new File(p); f.encoding = "BINARY"; f.open("w"); f.write(b); f.close(); }
  function readBin(p) { var f = new File(p); f.encoding = "BINARY"; f.open("r"); var s = f.read(); f.close(); return s; }
  function closeMine() { var i; for (i = mine.length - 1; i >= 0; i--) { try { mine[i].close(SaveOptions.DONOTSAVECHANGES); } catch (e) { } } mine = []; }
  function png(doc, name) {
    var o = new ExportOptionsPNG24(); o.artBoardClipping = true; o.transparency = true; o.antiAliasing = true;
    doc.artboards.setActiveArtboardIndex(0);
    var p = A.outdir + "/" + A.task + "-" + name + ".png";
    doc.exportFile(new File(p), ExportType.PNG24, o);
    return p;
  }
  function dumpTo(doc, name) {
    var d = werkAI.dumpDocument(doc), j = { artboards: d.artboards, layers: d.layers, counts: d.counts, skipped: d.skipped, notes: d.notes, bad_numbers: d.bad_numbers || [] };
    writeBin(A.outdir + "/" + A.task + "-" + name + ".json", werk.jsonPretty(j));
    return d;
  }
  try {
    out.docs_before = app.documents.length;
    out.host = { app: app.name, version: app.version, extendscript: $.version };
    step("start");
    var r = werkAI.openWerk(A["in"], { scratch: A.outdir + "/scratch" });
    mine.push(r.doc);
    out.verdict = r.verdict; out.report = r.report; out.profile = r.profile; out.counts = r.counts; out.skipped = r.skipped;
    step("opened " + r.profile);
    png(r.doc, "open"); step("open.png");
    if (r.profile === "vector-art/1") {
      var d = dumpTo(r.doc, "dump"); out.dump_counts = d.counts; out.dump_skipped = d.skipped;
      step("dumped");
      var ex = werkAI.exportVectorArt(r.doc, A.out, { template: A.template, scratch: A.outdir + "/scratch", name: (r.entity || {}).name, withImages: A.with_images !== "0" });
      out.export_result = { manifest_sha256: ex.manifest_sha256, report: ex.report, counts: ex.counts, skipped: ex.skipped };
      step("exported vector-art/1");
    }
    out.export_image = werkAI.exportImage(r.doc, A.out_image, { scratch: A.outdir + "/scratch" });
    step("exported image/1");
    closeMine();
    if (r.profile === "vector-art/1") {
      var r2 = werkAI.openWerk(A.out, { scratch: A.outdir + "/scratch" }); mine.push(r2.doc);
      out.reopen_verdict = r2.verdict; out.reopen_counts = r2.counts; out.reopen_report = r2.report;
      dumpTo(r2.doc, "redump"); png(r2.doc, "reopen");
      step("reopened vector-art/1");
      closeMine();
    }
    var r3 = werkAI.openWerk(A.out_image, { scratch: A.outdir + "/scratch" }); mine.push(r3.doc);
    out.reopen_image_verdict = r3.verdict; png(r3.doc, "reopen-image");
    step("reopened image/1");
    out.ok = true;
  } catch (e) {
    out.error = e.message + (e.line ? " (line " + e.line + ")" : "");
    step("ERROR " + out.error);
  } finally {
    closeMine();
    out.docs_after = app.documents.length;
    out.seconds = (new Date().getTime() - t0) / 1000;
  }
  writeBin(A.outdir + "/" + A.task + ".json", werk.jsonPretty(out));
  return "done " + A.task + " ok=" + out.ok;
})();
