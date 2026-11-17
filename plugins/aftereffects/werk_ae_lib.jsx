// werk for After Effects 2020 (ExtendScript, ES3). Needs werk.jsx first.
//
//   werkAE.importImage(path, opts)              -> {item (FootageItem), report[], verdict, media_path}
//   werkAE.exportCompFrame(comp, time, out, opts) -> {manifest_sha256, png_sha256, png_bytes}
//
// After Effects footage is a LINK to a file on disk, so an imported image/1
// primary is extracted to a media folder that stays: opts.mediaDir, else
// <this folder>/_media. The file is content-addressed (sha256 of the bytes), so
// importing the same package twice reuses one file. Nothing is deleted from it.
var werkAE = (function () {
  var TOOL = "werk-aftereffects", VERSION = "1.0.0";
  function rep(list, sev, code, msg) { list.push({ severity: sev, code: code, message: msg }); }
  function here() { return File($.fileName).parent.fsName.replace(/\\/g, "/"); }
  function ensureDir(d) { var f = new Folder(d); if (!f.exists) { f.create(); } return f.fsName.replace(/\\/g, "/"); }
  function writeBin(path, bytes) {
    var f = new File(path); f.encoding = "BINARY"; f.lineFeed = "Unix";
    if (!f.open("w")) { throw new Error("cannot write " + path); }
    f.write(bytes); f.close();
  }
  function readBin(path) {
    var f = new File(path); f.encoding = "BINARY";
    if (!f.open("r")) { throw new Error("cannot read " + path); }
    var parts = [], s; while (!f.eof) { s = f.read(1048576); if (s === "" && f.eof) { break; } parts.push(s); }
    f.close(); return parts.join("");
  }
  // a node's payload file -> <mediaDir>/<sha256 prefix>.<ext>, written once, kept
  function extractMedia(pkg, nodeId, mediaDir) {
    var p = pkg.payloadPath(nodeId), b = pkg.readPayload(nodeId), ext = /\.(\w+)$/.exec(p), sha = werk.sha256Hex(b);
    var dir = ensureDir(mediaDir || (here() + "/_media")), mp = dir + "/" + sha.substring(0, 32) + "." + (ext ? ext[1].toLowerCase() : "bin");
    var mf = new File(mp);
    if (!mf.exists || mf.length !== b.length) { writeBin(mp, b); }
    return mp;
  }
  function importImage(path, opts) {
    opts = opts || {};
    var report = [], pkg = werk.open(path), v = pkg.verdict(), i;
    for (i = 0; i < pkg.report.length; i++) { var e = pkg.report[i]; report.push({ severity: e.severity, code: e.code, message: (e.node ? e.node + ": " : "") + e.message }); }
    var profile = pkg.manifest.profile;
    var pi = pkg.primaryImage();
    if (profile !== "image/1") { rep(report, "info", "imported-primary-image", "profile " + profile + ": only primary.image (" + pi.path + ") was imported"); }
    var ext = /\.(\w+)$/.exec(pi.path), sha = werk.sha256Hex(pi.bytes);
    var dir = ensureDir(opts.mediaDir || (here() + "/_media"));
    var mp = dir + "/" + sha.substring(0, 32) + "." + (ext ? ext[1].toLowerCase() : "png");
    var mf = new File(mp);
    if (!mf.exists || mf.length !== pi.bytes.length) { writeBin(mp, pi.bytes); }
    var io = new ImportOptions(new File(mp));
    if (io.canImportAs(ImportAsType.FOOTAGE)) { io.importAs = ImportAsType.FOOTAGE; }
    var item = app.project.importFile(io);
    var nm = (pkg.manifest.entity || {}).name;
    if (nm) { item.name = nm; }
    item.comment = "werk " + profile + " " + path + " (entity " + ((pkg.manifest.entity || {}).uuid || "") + ", primary " + pi.path + ", sha256 " + sha + ")";
    return { item: item, report: report, verdict: v, media_path: mp, primary_path: pi.path, primary_sha256: sha, profile: profile };
  }
  // comp.saveFrameToPng is asynchronous in After Effects 2020: wait for the file to be complete.
  function waitFile(p, ms) {
    var f = new File(p), t0 = new Date().getTime(), last = -1, stable = 0;
    while (new Date().getTime() - t0 < ms) {
      f = new File(p);
      if (f.exists && f.length > 0) {
        if (f.length === last) { stable++; if (stable >= 3) { return true; } } else { stable = 0; last = f.length; }
      }
      $.sleep(200);
    }
    return f.exists && f.length > 0;
  }
  function framePNG(comp, time, opts) {
    var dir = ensureDir((opts && opts.scratch) || (here() + "/_scratch"));
    var p = dir + "/frame-" + new Date().getTime() + "-" + Math.floor(Math.random() * 1e6) + ".png";
    comp.saveFrameToPng(time, new File(p));
    if (!waitFile(p, (opts && opts.timeoutMs) || 120000)) { throw new Error("After Effects wrote no frame to " + p); }
    var b = readBin(p);
    try { new File(p).remove(); } catch (e) { }
    return b;
  }
  function exportCompFrame(comp, time, out, opts) {
    opts = opts || {};
    var png = framePNG(comp, time, opts), producer = { tool: TOOL, version: VERSION };
    var w = werk.writeImagePackage(out, png, { name: opts.name || comp.name || "Frame", created: opts.created, uuid: opts.uuid,
      summary: opts.summary === undefined ? null : opts.summary, generator: producer, producer: producer });
    return { manifest_sha256: werk.sha256Hex(w.build("zip").manifestBytes), png_sha256: werk.sha256Hex(png), png_bytes: png.length };
  }
  return { importImage: importImage, exportCompFrame: exportCompFrame, framePNG: framePNG, extractMedia: extractMedia, version: VERSION };
})();
