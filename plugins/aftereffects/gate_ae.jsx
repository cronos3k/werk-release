// Gate steps run INSIDE After Effects 2020: AfterFX.exe -noui -r <runner.jsx>, where the
// runner sets WERK_ARGS = {outdir, log, tasks: [{task, in}], synthetic: true} and evaluates
// this file. Results: <outdir>/<task>.json; the last log line is "ALL DONE".
$.evalFile(new File(File($.fileName).parent.fsName + "/werk.jsx"));
$.evalFile(new File(File($.fileName).parent.fsName + "/werk_ae_lib.jsx"));
$.evalFile(new File(File($.fileName).parent.fsName + "/werk_ae_motion.jsx"));
(function () {
  var A = WERK_ARGS;
  function logl(s) { var f = new File(A.log); f.encoding = "UTF-8"; f.open("a"); f.writeln(new Date().getTime() + " " + s); f.close(); }
  function writeBin(p, b) { var f = new File(p); f.encoding = "BINARY"; f.open("w"); f.write(b); f.close(); }
  function save(task, out) { writeBin(A.outdir + "/" + task + ".json", werk.jsonPretty(out)); }
  function frameOf(item, task, name) {
    var c = app.project.items.addComp("werk-check-" + name, item.width, item.height, 1, 1 / 24, 24);
    c.layers.add(item);
    var png = werkAE.framePNG(c, 0, { scratch: A.outdir + "/scratch" });
    writeBin(A.outdir + "/" + task + "-" + name + ".png", png);
    return c;
  }
  logl("start " + app.version + " ES " + $.version);
  var i;
  for (i = 0; i < A.tasks.length; i++) {
    var T = A.tasks[i], out = { task: T.task, input: T["in"], ok: false, steps: [] }, t0 = new Date().getTime();
    try {
      out.host = { app: "After Effects", version: app.version, extendscript: $.version };
      var r = werkAE.importImage(T["in"], { mediaDir: A.outdir + "/media" });
      out.verdict = r.verdict; out.report = r.report; out.profile = r.profile; out.primary_path = r.primary_path; out.primary_sha256 = r.primary_sha256;
      out.media_sha256 = werk.sha256Hex((function (p) { var f = new File(p); f.encoding = "BINARY"; f.open("r"); var s = f.read(); f.close(); return s; })(r.media_path));
      out.footage = { name: r.item.name, width: r.item.width, height: r.item.height, typename: r.item.typeName, has_alpha: r.item.hasAlpha };
      logl(T.task + " imported " + r.item.width + "x" + r.item.height);
      var comp = frameOf(r.item, T.task, "open");
      out.export_result = werkAE.exportCompFrame(comp, 0, A.outdir + "/" + T.task + "-out.werk", { scratch: A.outdir + "/scratch" });
      logl(T.task + " exported");
      var r2 = werkAE.importImage(A.outdir + "/" + T.task + "-out.werk", { mediaDir: A.outdir + "/media" });
      out.reopen_verdict = r2.verdict; out.reopen_footage = { width: r2.item.width, height: r2.item.height };
      frameOf(r2.item, T.task, "reopen");
      logl(T.task + " re-imported");
      out.ok = true;
    } catch (e) { out.error = e.message + (e.line ? " (line " + e.line + ")" : ""); logl(T.task + " ERROR " + out.error); }
    out.seconds = (new Date().getTime() - t0) / 1000;
    save(T.task, out);
  }
  if (A.motion) {
    var om = { task: "motion", input: A.motion, ok: false }, tm = new Date().getTime();
    try {
      var mr = werkAEMotion.importProject(A.motion, { mediaDir: A.outdir + "/media" });
      om.verdict = mr.verdict; om.report = mr.report; om.counts = mr.counts; om.comps = [];
      var XFN = ["ADBE Anchor Point", "ADBE Position", "ADBE Scale", "ADBE Orientation", "ADBE Rotate X", "ADBE Rotate Y", "ADBE Rotate Z", "ADBE Opacity"];
      for (var cid in mr.comps) {
        if (!mr.comps.hasOwnProperty(cid)) { continue; }
        var C = mr.comps[cid], cd = { id: Number(cid), name: C.name, width: C.width, height: C.height, frameRate: C.frameRate, duration: C.duration, layers: [] };
        for (var li = 1; li <= C.numLayers; li++) {
          var L = C.layer(li), ld = { index: li, name: L.name, startTime: L.startTime, inPoint: L.inPoint, outPoint: L.outPoint, props: {} };
          var g = L.property("ADBE Transform Group");
          for (var pi = 0; pi < XFN.length; pi++) {
            var pr = g ? g.property(XFN[pi]) : null;
            if (!pr) { continue; }
            var pd = { numKeys: pr.numKeys, keys: [] };
            try { pd.value0 = pr.valueAtTime(L.startTime, true); } catch (x0) { }
            for (var kk = 1; kk <= pr.numKeys; kk++) { pd.keys.push({ t: pr.keyTime(kk), v: pr.keyValue(kk), inI: String(pr.keyInInterpolationType(kk)), outI: String(pr.keyOutInterpolationType(kk)) }); }
            ld.props[XFN[pi]] = pd;
          }
          cd.layers.push(ld);
        }
        om.comps.push(cd);
        if (Number(cid) === A.poster_comp) {
          var fpng = werkAE.framePNG(C, A.poster_tick / werkAEMotion.TPS, { scratch: A.outdir + "/scratch" });
          writeBin(A.outdir + "/motion-poster-frame.png", fpng);
        }
      }
      om.ok = true;
    } catch (em) { om.error = em.message + (em.line ? " (line " + em.line + ")" : ""); }
    om.seconds = (new Date().getTime() - tm) / 1000;
    save("motion", om);
    logl("motion " + om.ok);
  }
  if (A.synthetic) {
    var o2 = { task: "synthetic", ok: false };
    try {
      var c = app.project.items.addComp("werk-synthetic", 320, 180, 1, 2, 24);
      c.bgColor = [0, 0, 0];
      c.layers.addSolid([1, 0, 0], "red", 320, 180, 1);
      var b = c.layers.addSolid([0, 0, 1], "blue", 160, 180, 1);
      b.property("Position").setValue([80, 90]);
      o2.export_result = werkAE.exportCompFrame(c, 0, A.outdir + "/synthetic-out.werk", { scratch: A.outdir + "/scratch", name: "werk synthetic comp" });
      var r3 = werkAE.importImage(A.outdir + "/synthetic-out.werk", { mediaDir: A.outdir + "/media" });
      o2.reopen_verdict = r3.verdict; o2.reopen_footage = { width: r3.item.width, height: r3.item.height };
      o2.ok = true;
    } catch (e3) { o2.error = e3.message + (e3.line ? " (line " + e3.line + ")" : ""); }
    save("synthetic", o2);
    logl("synthetic " + o2.ok);
  }
  try { app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES); } catch (e4) { logl("close " + e4); }
  logl("ALL DONE");
  app.quit();
})();
