// werk for Photoshop 2020 (ExtendScript, ES3): open and export .werk packages,
// profiles image/1 and raster-layers/1. Evaluate werk.jsx and
// werk_raster.jsx first (werk_ps_load.jsx does it).
//
//   werkPS.openWerk(path, opts)              -> {doc, report[], verdict, profile, layers[]}
//   werkPS.exportImage(doc, out, opts)       -> {manifest_sha256, png_sha256, bytes}
//   werkPS.exportRasterLayers(doc, out, opts)-> {manifest_sha256, layers, report[]}
//   werkPS.layerRGBA8(doc, layer)            -> W*H*4 bytes, straight alpha, alpha-0 pixels zero
//
// Every pixel decode and encode of PNG / JPEG is Photoshop's own: an image/1
// primary is opened from a scratch copy, a raster-layers/1 surface is handed to
// Photoshop as a Photoshop Raw file, and exports go through "Save As" PNG / Raw.
// Scratch files live in <this folder>/_scratch (or opts.scratch) and are removed.
var werkPS = (function () {
  var TOOL = "werk-photoshop", VERSION = "1.0.0";
  function cTID(s) { return charIDToTypeID(s); }
  function sTID(s) { return stringIDToTypeID(s); }
  function hasOwn(o, k) { return Object.prototype.hasOwnProperty.call(o, k); }
  function rep(list, sev, code, msg) { list.push({ severity: sev, code: code, message: msg }); }
  var LOG = null;
  function log(s) { if (!LOG) { return; } var f = new File(LOG); f.encoding = "UTF-8"; f.open("a"); f.writeln(new Date().getTime() + " " + s); f.close(); }
  function scratchDir(opts) {
    var d = (opts && opts.scratch) ? opts.scratch : (File($.fileName).parent.fsName + "/_scratch");
    var f = new Folder(d); if (!f.exists) { f.create(); }
    return f.fsName.replace(/\\/g, "/");
  }
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
  function rm(p) { try { var f = new File(p); if (f.exists) { f.remove(); } } catch (e) { } }
  function fastJson(bytes) {
    // U+2028 / U+2029 are legal inside JSON strings but end a line in an ES3 string literal
    var text = werk.utf8Decode(bytes).replace(/\u2028/g, "\\u2028").replace(/\u2029/g, "\\u2029");
    var t = text.replace(/\\(?:["\\\/bfnrt]|u[0-9a-fA-F]{4})/g, "@")
      .replace(/"[^"\\\n\r]*"|true|false|null|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?/g, "]")
      .replace(/(?:^|:|,)(?:\s*\[)+/g, "");
    if (!/^[\],:{}\s]*$/.test(t)) { return werk.jsonParse(text); }
    return eval("(" + text + ")");
  }
  function num(v) { return (v instanceof werk.WFloat) ? v.value : v; }
  function safeName(s) { return String(s || "werk").replace(/[^A-Za-z0-9 ._-]+/g, "_").substring(0, 80) || "werk"; }
  function withPrefs(fn) {
    var ru = app.preferences.rulerUnits, tu = app.preferences.typeUnits, dd = app.displayDialogs;
    app.preferences.rulerUnits = Units.PIXELS; app.preferences.typeUnits = TypeUnits.PIXELS; app.displayDialogs = DialogModes.NO;
    try { return fn(); }
    finally { app.preferences.rulerUnits = ru; app.preferences.typeUnits = tu; app.displayDialogs = dd; }
  }

  // ------------------------------------------------------------------ blend modes
  var PAIRS = null;
  function pairs() {
    if (PAIRS) { return PAIRS; }
    PAIRS = [["Normal", BlendMode.NORMAL], ["Dissolve", BlendMode.DISSOLVE], ["Darken", BlendMode.DARKEN], ["Multiply", BlendMode.MULTIPLY],
      ["ColorBurn", BlendMode.COLORBURN], ["LinearBurn", BlendMode.LINEARBURN], ["DarkerColor", BlendMode.DARKERCOLOR],
      ["Lighten", BlendMode.LIGHTEN], ["Screen", BlendMode.SCREEN], ["ColorDodge", BlendMode.COLORDODGE], ["LinearDodge", BlendMode.LINEARDODGE],
      ["LighterColor", BlendMode.LIGHTERCOLOR], ["Overlay", BlendMode.OVERLAY], ["SoftLight", BlendMode.SOFTLIGHT], ["HardLight", BlendMode.HARDLIGHT],
      ["VividLight", BlendMode.VIVIDLIGHT], ["LinearLight", BlendMode.LINEARLIGHT], ["PinLight", BlendMode.PINLIGHT], ["HardMix", BlendMode.HARDMIX],
      ["Difference", BlendMode.DIFFERENCE], ["Exclusion", BlendMode.EXCLUSION], ["Subtract", BlendMode.SUBTRACT], ["Divide", BlendMode.DIVIDE],
      ["Hue", BlendMode.HUE], ["Saturation", BlendMode.SATURATION], ["Color", BlendMode.COLORBLEND], ["Luminosity", BlendMode.LUMINOSITY],
      ["PassThrough", BlendMode.PASSTHROUGH]];
    return PAIRS;
  }
  function toPSBlend(name) { var p = pairs(), i; for (i = 0; i < p.length; i++) { if (p[i][0] === name) { return p[i][1]; } } return null; }
  function fromPSBlend(m) { var p = pairs(), i; for (i = 0; i < p.length; i++) { if (p[i][1] === m) { return p[i][0]; } } return "Normal"; }

  // ------------------------------------------------------------------ Action Manager helpers
  function selectChannel(enumId) {   // load a channel ('Trsp' transparency, 'Msk ' mask) as the selection
    var d = new ActionDescriptor(), r = new ActionReference(), r2 = new ActionReference();
    r.putProperty(cTID("Chnl"), cTID("fsel")); d.putReference(cTID("null"), r);
    r2.putEnumerated(cTID("Chnl"), cTID("Chnl"), cTID(enumId)); d.putReference(cTID("T   "), r2);
    executeAction(cTID("setd"), d, DialogModes.NO);
  }
  function makeMask(using) {          // 'RvlS' reveal selection, 'Trns' from transparency
    var d = new ActionDescriptor(), r = new ActionReference();
    d.putClass(cTID("Nw  "), cTID("Chnl"));
    r.putEnumerated(cTID("Chnl"), cTID("Chnl"), cTID("Msk ")); d.putReference(cTID("At  "), r);
    d.putEnumerated(cTID("Usng"), cTID("UsrM"), cTID(using));
    executeAction(cTID("Mk  "), d, DialogModes.NO);
  }
  function applyMask() {
    var d = new ActionDescriptor(), r = new ActionReference();
    r.putEnumerated(cTID("Chnl"), cTID("Chnl"), cTID("Msk ")); d.putReference(cTID("null"), r);
    d.putBoolean(cTID("Aply"), true);
    executeAction(cTID("Dlt "), d, DialogModes.NO);
  }
  function setMaskEnabled(on) {
    var d = new ActionDescriptor(), r = new ActionReference(), l = new ActionDescriptor();
    r.putEnumerated(cTID("Lyr "), cTID("Ordn"), cTID("Trgt")); d.putReference(cTID("null"), r);
    l.putBoolean(cTID("UsrM"), on); d.putObject(cTID("T   "), cTID("Lyr "), l);
    executeAction(cTID("setd"), d, DialogModes.NO);
  }

  // ------------------------------------------------------------------ OPEN
  function openWerk(path, opts) {
    opts = opts || {};
    LOG = opts.log || null;
    return withPrefs(function () {
      log("open " + path);
      var report = [], pkg = werk.open(path), v = pkg.verdict(), i;
      log("verified exit=" + v.exit + " sig=" + v.signature);
      for (i = 0; i < pkg.report.length; i++) { var e = pkg.report[i]; report.push({ severity: e.severity, code: e.code, message: (e.node ? e.node + ": " : "") + e.message }); }
      var profile = pkg.manifest.profile;
      if (profile === "raster-layers/1") { return openRasterLayers(pkg, v, report, opts); }
      return openImage(pkg, v, report, opts, profile);
    });
  }
  function openImage(pkg, v, report, opts, profile) {
    var pi = pkg.primaryImage(), ext = /\.(\w+)$/.exec(pi.path), sd = scratchDir(opts);
    // a plain file name: Photoshop 2024 under automation refused to save a copy of a document
    // opened from a file whose name had spaces ("User cancelled the operation")
    var p = sd + "/" + safeName((pkg.manifest.entity || {}).name).replace(/[^A-Za-z0-9_-]+/g, "-") + "-" + new Date().getTime() + "." + (ext ? ext[1].toLowerCase() : "png");
    writeBin(p, pi.bytes);
    var doc = app.open(new File(p));
    // The file stays while the document is open: Photoshop 2024 under automation stalls
    // ("User cancelled the operation" after minutes) when a document's file vanishes.
    // werkPS.closeDoc(doc) / the caller removes it (result.temp); a user's copy stays in _scratch.
    if (profile !== "image/1") { rep(report, "info", "opened-primary-image", "profile " + profile + ": only primary.image (" + pi.path + ") was opened"); }
    log("opened image " + pi.path);
    return { doc: doc, report: report, verdict: v, profile: profile, primary_path: pi.path, entity: pkg.manifest.entity, temp: p };
  }
  function rawOpen(path, w, h, ch, bits) {
    var o = new RawFormatOpenOptions();
    o.width = w; o.height = h; o.channelNumber = ch; o.bitsPerChannel = bits;
    o.byteOrder = ByteOrder.IBM; o.interleaveChannels = true; o.headerSize = 0; o.retainHeader = false;
    return app.open(new File(path), o);
  }
  // Build one pixel layer from a decoded surface inside `target`, at the top of `container`.
  function surfaceLayer(target, container, surf, W, H, sd, name) {
    var split = werkRaster.toRGBandA(surf), stamp = new Date().getTime() + "-" + Math.floor(Math.random() * 1e6);
    var prgb = sd + "/rgb-" + stamp + ".raw", pa = sd + "/a-" + stamp + ".raw";
    if (split.alpha !== null && !/[^\x00]/.test(split.alpha)) {
      // fully transparent: Photoshop cannot make a mask from an empty selection - an empty layer is the same picture
      app.activeDocument = target;
      var e0 = container.artLayers.add(); e0.name = name; toTop(e0, container);
      return e0;
    }
    writeBin(prgb, split.rgb);
    var d1 = rawOpen(prgb, W, H, 3, split.bits), d2 = null;
    try {
      app.activeDocument = d1;
      var L = d1.artLayers[0];
      L.isBackgroundLayer = false;
      if (split.alpha !== null) {
        writeBin(pa, split.alpha);
        d2 = rawOpen(pa, W, H, 1, split.bits);
        app.activeDocument = d2;
        d2.channels[0].duplicate(d1);            // the alpha becomes an alpha channel of d1
        d2.close(SaveOptions.DONOTSAVECHANGES); d2 = null;
        app.activeDocument = d1;
        var ch = d1.channels[d1.channels.length - 1];
        d1.activeLayer = L;
        d1.selection.load(ch, SelectionType.REPLACE);
        makeMask("RvlS");
        applyMask();
        d1.selection.deselect();
        ch.remove();
      }
      var dup = L.duplicate(container, ElementPlacement.PLACEATBEGINNING);
      app.activeDocument = target;
      dup.name = name;
      return dup;
    } finally {
      if (d2) { d2.close(SaveOptions.DONOTSAVECHANGES); }
      d1.close(SaveOptions.DONOTSAVECHANGES);
      app.activeDocument = target;
      rm(prgb); rm(pa);
    }
  }
  function toTop(item, container) {
    var first = container.layers[0];
    if (first === item || (first.name === item.name && first.id === item.id)) { return; }
    if (container.typename === "LayerSet") { item.move(container, ElementPlacement.PLACEATBEGINNING); }
    else { item.move(first, ElementPlacement.PLACEBEFORE); }
  }
  function openRasterLayers(pkg, v, report, opts) {
    var m = pkg.manifest, docId = (m.primary || {}).document, dj = fastJson(pkg.readPayload(docId)), sd = scratchDir(opts);
    var W = num(dj.width), H = num(dj.height), st = dj.sample_type || "U8";
    var bits = st === "U8" ? BitsPerChannelType.EIGHT : BitsPerChannelType.SIXTEEN;
    if (st === "F32") { rep(report, "info", "float-document-as-16-bit", "a 32-bit float document opens at 16 bits per channel, values clamped to 0..1"); }
    var res = num(dj.resolution_dpi) || 72;
    var target = app.documents.add(W, H, res, safeName(dj.name || (m.entity || {}).name), NewDocumentMode.RGB, DocumentFill.TRANSPARENT, 1, bits);
    var placeholder = target.artLayers[0], built = [], counts = { pixel: 0, group: 0, empty: 0 };
    function props(item, lj, isGroup) {
      var op = num(lj.opacity === undefined ? 1 : lj.opacity), fo = num(lj.fill_opacity === undefined ? 1 : lj.fill_opacity);
      item.opacity = Math.round(op * 10000) / 100;
      if (!isGroup) { item.fillOpacity = Math.round(fo * 10000) / 100; }
      var b = lj.blend || (isGroup ? "PassThrough" : "Normal"), pm = toPSBlend(b);
      if (pm && !(pm === BlendMode.PASSTHROUGH && !isGroup)) { item.blendMode = pm; }
      else if (b !== "Normal") { rep(report, "info", "blend-not-mapped", (lj.name || "") + ": blend " + b + " opens as Normal"); }
    }
    function build(entries, container, path) {
      var i;
      for (i = 0; i < entries.length; i++) {
        var ent = entries[i], nid = ent.layer, lj;
        try { lj = fastJson(pkg.readPayload(nid)); }
        catch (e) {
          rep(report, "error", "layer-dead", nid + ": " + e.message + "; dropped (children kept)");
          if (ent.children) { build(ent.children, container, path); }
          continue;
        }
        var c = lj.content || {}, name = lj.name || nid, item = null, notes = [];
        if (lj.mask) { notes.push("mask-not-applied"); }
        if (lj.clipped) { notes.push("clipping-not-applied"); }
        if ((lj.effects || {}).items && lj.effects.items.length) { notes.push("effects-not-applied"); }
        if (hasOwn(ent, "children")) {
          item = container.layerSets.add(); item.name = name;
          toTop(item, container);   // add() puts it above the ACTIVE layer
          counts.group++;
          build(ent.children || [], item, path + "/" + name);
          props(item, lj, true);
        } else {
          var sid = c.kind === "raster" ? c.pixels : c.cache, surf = null;
          if (c.kind === "adjustment" || c.kind === "fill") { notes.push(c.kind + "-layer-not-rendered"); }
          else if (sid) {
            try {
              log("decode " + sid);
              surf = werkRaster.decodeSurface(pkg, sid, W, H);
              if (!surf.colour) { notes.push("pixel-mode-" + surf.mode + "-not-decoded"); surf = null; }
            } catch (e2) { rep(report, "error", "surface-dead", sid + ": " + e2.message + "; layer shown empty"); surf = null; }
          } else { notes.push("no-pixels"); }
          if (surf) {
            log("layer " + name);
            item = surfaceLayer(target, container, surf, W, H, sd, name);
            counts.pixel++;
            if (surf.sample_type === "f32") { notes.push("f32-surface-as-16-bit"); }
          } else {
            item = container.artLayers.add(); item.name = name;
            toTop(item, container);
            counts.empty++;
          }
          props(item, lj, false);
        }
        var k;
        for (k = 0; k < notes.length; k++) { rep(report, "info", notes[k], nid + " (" + name + ")"); }
        built.push({ node_id: nid, name: name, item: item, group: hasOwn(ent, "children"), visible: lj.visible !== false, surface: !!(item && !hasOwn(ent, "children") && c && (c.kind === "raster" ? c.pixels : c.cache)) });
      }
    }
    app.activeDocument = target;
    build(dj.layers || [], target, "");
    if (target.layers.length > 1) { placeholder.remove(); }
    // visibility last: hidden layers cannot be targeted by the steps above
    var i;
    for (i = 0; i < built.length; i++) { if (!built[i].visible && built[i].item) { built[i].item.visible = false; } }
    var layers = [];
    for (i = 0; i < built.length; i++) { layers.push({ node_id: built[i].node_id, name: built[i].name, group: built[i].group, visible: built[i].visible }); }
    log("raster-layers open done: " + counts.pixel + " pixel, " + counts.group + " groups, " + counts.empty + " empty");
    return { doc: target, report: report, verdict: v, profile: "raster-layers/1", layers: layers, built: built, counts: counts, entity: m.entity };
  }

  // ------------------------------------------------------------------ EXPORT
  function utcNow() {
    var d = new Date();
    function p2(n) { return (n < 10 ? "0" : "") + n; }
    return d.getUTCFullYear() + "-" + p2(d.getUTCMonth() + 1) + "-" + p2(d.getUTCDate()) + "T" + p2(d.getUTCHours()) + ":" + p2(d.getUTCMinutes()) + ":" + p2(d.getUTCSeconds()) + "Z";
  }
  // the document's visible composite as an 8-bit PNG (straight alpha), Photoshop's encoder
  // Save a copy of `d` as PNG through the Action Manager ("save", As PNGF, Cpy):
  // Photoshop 2024 hangs in Document.duplicate(name, true) under COM automation,
  // and a PNG copy of a layered document is its visible composite anyway.
  var PNG_FALLBACKS = 0;
  function savePNGCopy(d, path) {
    app.activeDocument = d;
    var desc = new ActionDescriptor(), fmt = new ActionDescriptor();
    // Photoshop 2023+ asks for a PNG method when the descriptor names none (a dialog,
    // i.e. "User cancelled" under DialogModes.NO); older versions ignore the key.
    fmt.putEnumerated(sTID("method"), sTID("PNGMethod"), sTID("quick"));
    desc.putObject(cTID("As  "), cTID("PNGF"), fmt);
    desc.putPath(cTID("In  "), new File(path));
    desc.putBoolean(cTID("Cpy "), true);
    // Photoshop 2022+ may still be writing the previous file ("save in background"); a save
    // started meanwhile fails with "User cancelled the operation". Retry, then wait for the file.
    var i, err = null;
    for (i = 0; i < 3; i++) {
      try { executeAction(cTID("save"), desc, DialogModes.NO); err = null; break; }
      catch (e) { err = e; $.sleep(1500); }
    }
    if (err) {
      // Photoshop 2024 under COM automation keeps refusing some saves ("User cancelled the
      // operation"); Save for Web writes the same composite through another path.
      var o = new ExportOptionsSaveForWeb();
      o.format = SaveDocumentType.PNG; o.PNG8 = false; o.transparency = true; o.interlaced = false;
      o.includeProfile = false; o.optimized = false;
      d.exportDocument(new File(path), ExportType.SAVEFORWEB, o);
      PNG_FALLBACKS++;
    }
    var f = new File(path), last = -1, t0 = new Date().getTime();
    while (new Date().getTime() - t0 < 120000) {
      f = new File(path);
      if (f.exists && f.length > 0 && f.length === last) { break; }
      last = f.exists ? f.length : -1;
      $.sleep(300);
    }
  }
  // the document's visible composite as a PNG (straight alpha), Photoshop's encoder;
  // eightBit: an 8-bit PNG also for a 16-bit document (through a converted duplicate)
  // the document's visible composite as a PNG (straight alpha), Photoshop's encoder:
  // a merged duplicate saved as PNG (the path gated in Photoshop 2020); when Photoshop
  // refuses that (2024 under COM automation), an Action Manager / Save for Web copy.
  function compositePNG(doc, sd, eightBit) {
    var p = sd + "/composite-" + new Date().getTime() + ".png", tmp = null, saved = false, dd = app.displayDialogs;
    app.activeDocument = doc;
    // a freshly started Photoshop has DialogModes.ALL: "Save As" would then open its dialog and wait
    app.displayDialogs = DialogModes.NO;
    try {
      tmp = doc.duplicate("werk-composite", true);     // merged copy
      if (eightBit && tmp.bitsPerChannel !== BitsPerChannelType.EIGHT) { tmp.bitsPerChannel = BitsPerChannelType.EIGHT; }
      var o = new PNGSaveOptions(); o.compression = 6; o.interlaced = false;
      try { tmp.saveAs(new File(p), o, true, Extension.LOWERCASE); saved = true; }
      catch (eSave) { log("PNG saveAs refused (" + eSave.message + "): Action Manager / Save for Web copy"); }
      if (!saved) { savePNGCopy(tmp, p); }
    } finally { if (tmp) { tmp.close(SaveOptions.DONOTSAVECHANGES); } app.activeDocument = doc; app.displayDialogs = dd; }
    var b = readBin(p); rm(p);
    return b;
  }
  function exportImage(doc, out, opts) {
    opts = opts || {};
    LOG = opts.log || LOG;
    return withPrefs(function () {
      var sd = scratchDir(opts), png = compositePNG(doc, sd, false), producer = { tool: TOOL, version: VERSION };
      log("image/1 composite " + png.length + " B");
      var w = werk.writeImagePackage(out, png, { name: opts.name || doc.name.replace(/\.[^.]*$/, "") || "Untitled", created: opts.created, uuid: opts.uuid, generator: producer, producer: producer });
      return { manifest_sha256: werk.sha256Hex(w.build("zip").manifestBytes), png_sha256: werk.sha256Hex(png), png_bytes: png.length };
    });
  }
  // One layer's own pixels (not composited, not its opacity / blend), canvas-sized,
  // u8 RGBA straight alpha; pixels with alpha 0 are written as 0,0,0,0.
  function layerRGBA8(doc, layer, opts) {
    var sd = scratchDir(opts), W = Math.round(doc.width.as("px")), H = Math.round(doc.height.as("px"));
    var stamp = new Date().getTime() + "-" + Math.floor(Math.random() * 1e6), p = sd + "/layer-" + stamp + ".raw";
    app.activeDocument = doc;
    var tmp = app.documents.add(W, H, doc.resolution, "werk-layer", NewDocumentMode.RGB, DocumentFill.TRANSPARENT, 1, doc.bitsPerChannel);
    var empty = false;
    try {
      var first = tmp.artLayers[0];
      app.activeDocument = doc;
      var dup = layer.duplicate(tmp, ElementPlacement.PLACEATBEGINNING);
      app.activeDocument = tmp;
      first.remove();
      dup.visible = true; dup.opacity = 100; dup.fillOpacity = 100; dup.blendMode = BlendMode.NORMAL;
      if (tmp.bitsPerChannel !== BitsPerChannelType.EIGHT) { tmp.bitsPerChannel = BitsPerChannelType.EIGHT; }
      tmp.activeLayer = dup;
      var b = dup.bounds;
      if (b[2].as("px") - b[0].as("px") <= 0 || b[3].as("px") - b[1].as("px") <= 0) { empty = true; }
      else {
        selectChannel("Trsp");
        var ach = tmp.channels.add(); ach.name = "werk-alpha";
        tmp.selection.store(ach, SelectionType.REPLACE);
        tmp.selection.deselect();
        tmp.activeLayer = dup;
        makeMask("Trns");
        setMaskEnabled(false);
        var o = new RawSaveOptions(); o.alphaChannels = true; o.spotColors = false;
        var k, e1 = null;   // the same "save in background" retry as savePNGCopy
        for (k = 0; k < 20; k++) { try { tmp.saveAs(new File(p), o, true, Extension.LOWERCASE); e1 = null; break; } catch (eS) { e1 = eS; $.sleep(1500); } }
        if (e1) { throw e1; }
        var fr = new File(p), lastR = -1, tR = new Date().getTime();
        while (new Date().getTime() - tR < 120000) { fr = new File(p); if (fr.exists && fr.length === W * H * 4 && fr.length === lastR) { break; } lastR = fr.exists ? fr.length : -1; $.sleep(300); }
      }
    } finally { tmp.close(SaveOptions.DONOTSAVECHANGES); app.activeDocument = doc; }
    if (empty) { return repeat0(W * H * 4); }
    var raw = readBin(p); rm(p);
    if (raw.length !== W * H * 4) { throw new Error("Photoshop Raw export of layer " + layer.name + " is " + raw.length + " bytes, expected " + (W * H * 4)); }
    return zeroTransparent(raw, W, H);
  }
  function repeat0(n) { var s = "\x00", out = ""; while (n > 0) { if (n & 1) { out += s; } n >>= 1; if (n) { s += s; } } return out; }
  function zeroTransparent(raw, W, H) {
    var rows = [], y, x, row, parts, start, a, Z = "\x00\x00\x00\x00", changed;
    for (y = 0; y < H; y++) {
      row = raw.substring(y * W * 4, (y + 1) * W * 4);
      if (row.indexOf("\x00") < 0) { rows.push(row); continue; }
      parts = []; start = 0; changed = false;
      for (x = 0; x < W; x++) {
        if (row.charCodeAt(x * 4 + 3) === 0 && row.substring(x * 4, x * 4 + 3) !== "\x00\x00\x00") {
          parts.push(row.substring(start, x * 4)); parts.push(Z); start = x * 4 + 4; changed = true;
        }
      }
      if (changed) { parts.push(row.substring(start)); rows.push(parts.join("")); } else { rows.push(row); }
    }
    return rows.join("");
  }
  function pixelLayers(container, out) {   // bottom to top, groups flattened to their children
    var i, L = container.layers;
    for (i = L.length - 1; i >= 0; i--) {
      if (L[i].typename === "LayerSet") { pixelLayers(L[i], out); }
      else if (L[i].kind === LayerKind.NORMAL) { out.push(L[i]); }
      else { out.push(L[i]); }
    }
    return out;
  }
  // LIBRARY GAP (reported): the release loaders' meta lists capabilities the
  // profile's manifest schema does not permit; keep the permitted ones.
  function restrictLoaderCaps(w, schemaBytes) {
    if (!schemaBytes) { return; }
    var sch = fastJson(schemaBytes), allowed = null, i, j;
    try { allowed = sch["$defs"].loaderMeta.properties.capabilities.items["enum"]; } catch (e) { return; }
    if (!allowed) { return; }
    var ok = {}; for (i = 0; i < allowed.length; i++) { ok[allowed[i]] = true; }
    for (i = 0; i < w.nodes.length; i++) {
      var n = w.nodes[i];
      if (n.type !== "core.loader" || !n.meta || !n.meta.capabilities) { continue; }
      var keep = []; for (j = 0; j < n.meta.capabilities.length; j++) { if (ok[n.meta.capabilities[j]]) { keep.push(n.meta.capabilities[j]); } }
      var m = {}, k; for (k in n.meta) { if (hasOwn(n.meta, k)) { m[k] = n.meta[k]; } }
      m.capabilities = keep; n.meta = m;
    }
  }
  // PROFILE-RASTER-LAYERS.md section 7 grown to N pixel layers (as the GIMP plug-in writes it).
  // opts.template: an existing raster-layers/1 capsule whose spec/ (profile text, schemas,
  // layouts) is carried into the new capsule (section 7.3).
  function exportRasterLayers(doc, out, opts) {
    opts = opts || {};
    LOG = opts.log || LOG;
    return withPrefs(function () {
      if (!opts.template) { throw new Error("exportRasterLayers needs opts.template: a raster-layers/1 capsule to carry spec/ from"); }
      var report = [], created = opts.created || utcNow(), sd = scratchDir(opts), producer = { tool: TOOL, version: VERSION };
      var tpl = werk.open(opts.template), tm = tpl.manifest, i, k;
      if (tm.profile !== "raster-layers/1") { throw new Error("template is profile " + tm.profile); }
      var sv = werkRaster.resolvedVersion(tpl, "spec"), specFiles = {};
      for (i = 0; i < sv.files.length; i++) { var sp = sv.files[i].path; if (!/@\d+(\.|$)/.test(sp.replace(/^.*\//, ""))) { specFiles[sp] = tpl.readFile(sp); } }
      var W = Math.round(doc.width.as("px")), H = Math.round(doc.height.as("px")), name = opts.name || doc.name.replace(/\.[^.]*$/, "") || "Untitled";
      var w = new werk.PackageWriter("raster-layers/1", { name: name, uuid: opts.uuid, created: created, conventions: tm.conventions,
        manifestSchema: tm.manifest_schema, profileSpec: tm.profile_spec || null, specFiles: specFiles, generator: producer, producer: producer,
        summary: null, conventionsMap: tm.conventions_map });
      // an older werk.jsx has no conventionsMap option: set it the only way that build allows
      if (w.conventionsMap === undefined) { w.ptab.conventions_map = tm.conventions_map; }
      // the profile's reading guide beside README.txt, as the template carries it
      var howto = null;
      try { howto = tpl.readFile("HOW-TO-READ.md"); } catch (eH) { howto = null; }
      if (typeof w.addReadmeFile === "function" && howto) { w.addReadmeFile("HOW-TO-READ.md", howto, "text/markdown"); }
      restrictLoaderCaps(w, specFiles[tm.manifest_schema]);
      var layers = pixelLayers(doc, []), entries = [], docEdges = [], layerIds = [], inputs = ["document/document.json"], nTiles = 0;
      if (doc.layerSets.length) { rep(report, "info", "groups-flattened", doc.layerSets.length + " top-level group(s): their layers are written in order, group opacity / blend dropped"); }
      for (i = 0; i < layers.length; i++) {
        var L = layers[i], lid = "layer-" + (i + 1), sid = lid + "-pixels";
        if (L.kind !== LayerKind.NORMAL) { rep(report, "info", "layer-rasterised", L.name + ": a " + String(L.kind).replace("LayerKind.", "") + " layer is written as its pixels"); }
        log("export layer " + (i + 1) + "/" + layers.length + " " + L.name);
        var rgba = layerRGBA8(doc, L, opts), sf = werkRaster.surfaceFilesRGBA8(rgba, W, H);
        nTiles += sf.count;
        var lj = layerJson(L, sid);
        var files = [werk.file("surfaces/" + sid + "/surface.wkx", sf.index, "application/octet-stream", sf.tiles ? "payload" : null)];
        if (sf.tiles) { files.push(werk.file("surfaces/" + sid + "/tiles-p0-p0.wkx", sf.tiles, "application/octet-stream", "tiles-p0-p0")); }
        w.addNode(sid, "core.raster.surface", files, { note: "The pixels of layer " + (i + 1) + ": " + sf.count + " stored tile(s) of 256 x 256, u8 RGBA, raw.",
          meta: { usage: "layer-pixels", owner: lid, channels: ["red", "green", "blue", "alpha"], bits_per_sample: 8 },
          payloadFile: "surfaces/" + sid + "/surface.wkx" });
        w.addNode(lid, "core.raster.layer", [werk.file("layers/" + lid + "/layer.json", compact(lj), "application/json")], {
          note: "Layer " + (i + 1) + " of " + layers.length + " as Photoshop " + app.version + " had it (" + TOOL + ").",
          edges: [{ to: sid, kind: "enhances", role: "pixels" }], meta: { kind: "raster" } });
        entries.push({ layer: lid }); layerIds.push(lid); docEdges.push({ to: lid, kind: "enhances", role: "contains" });
        inputs.push("layers/" + lid + "/layer.json"); inputs.push("surfaces/" + sid + "/surface.wkx");
        if (sf.tiles) { inputs.push("surfaces/" + sid + "/tiles-p0-p0.wkx"); }
      }
      var dj = docJson(name, W, H, doc.resolution, entries);
      w.addNode("document", "core.raster.document", [werk.file("document/document.json", compact(dj), "application/json")], {
        note: "The canvas and the layer tree, " + layers.length + " layer(s), " + W + " x " + H + " px, exported by " + TOOL + ".",
        edges: docEdges, meta: { width: W, height: H, color_mode: "Rgb", sample_type: "U8" } });
      var png = compositePNG(doc, sd, true), info = werk.pngInfo(png), ce = [{ to: "document", kind: "requires", role: "rendered-from" }];
      for (i = 0; i < layerIds.length; i++) { ce.push({ to: layerIds[i], kind: "requires", role: "rendered-from" }); ce.push({ to: layerIds[i] + "-pixels", kind: "requires", role: "rendered-from" }); }
      var chs = ["red", "green", "blue", "alpha"].slice(0, info.channels);
      w.addNode("composite", "core.raster.preview", [werk.file("preview/composite.png", png, "image/png")], {
        note: "The document flattened by Photoshop " + app.version + " at full size.", epistemic: "measured", inputFiles: inputs,
        inputParams: { derivation: "flattened-composite", max_side: Math.max(W, H), resample: "area-average" }, edges: ce,
        meta: { alpha_mode: "straight", bits_per_sample: 8, channels: chs, color_space: "srgb", height: info.height, usage: "composite", width: info.width } });
      w.setPrimary("document", "document"); w.setPrimary("image", "composite");
      w.preview("preview/");
      var uses = {}, keys = [];
      for (i = 0; i < w.nodes.length; i++) { keys.push(w.nodes[i].node_id); }
      keys.push("revisions"); keys.sort();
      for (i = 0; i < keys.length; i++) { uses[keys[i]] = 1; }
      var rec = { created: created, kind: "save", nodes: uses, note: "Exported by " + TOOL + ".", producer: producer, revision: 1, schema_version: 1 };
      w.addNode("revisions", "core.revisions", [werk.file("revisions/revision.json", werk.jsonPretty(rec), "application/json")], { note: "The revision record of this save." });
      for (k in tm.schemas) { if (hasOwn(tm.schemas, k)) { for (i = 0; i < w.nodes.length; i++) { if (w.nodes[i].type === k) { w.setSchema(k, tm.schemas[k]); break; } } } }
      for (k in tm.layouts) { if (hasOwn(tm.layouts, k)) { for (i = 0; i < w.nodes.length; i++) { if (w.nodes[i].type === k) { w.setLayout(k, tm.layouts[k]); break; } } } }
      log("writing " + out);
      var msha = w.write(out, null);
      log("written");
      return { manifest_sha256: msha, layers: layers.length, tiles: nTiles, report: report };
    });
  }
  function compact(v) {
    // the profile's payload JSON: written by the werk library's deterministic JSON writer
    return werk.jsonPretty(v);
  }
  function layerJson(L, sid) {
    var fo = 100;
    try { fo = L.fillOpacity; } catch (e) { }
    return { schema_version: 1, name: L.name, visible: L.visible,
      locks: { transparency: false, pixels: false, position: false, artboard: false, all: false },
      blend: fromPSBlend(L.blendMode), opacity: new werk.WFloat(Math.round(L.opacity * 10000) / 1000000), fill_opacity: new werk.WFloat(Math.round(fo * 10000) / 1000000),
      clipped: false, mask: null, vector_mask: null, effects: { enabled: true, items: [], reference: null }, label: "None",
      content: { kind: "raster", pixels: sid }, psd_id: null, psd: null, fill_cache: null, link_group: null, excluded_channels: 0,
      blend_if: { ranges: [] },
      advanced: { knockout: "none", blendInterior: false, blendClipped: true, transparencyShapes: true, layerMaskHidesEffects: false, vectorMaskHidesEffects: false },
      video: null };
  }
  function docJson(name, W, H, dpi, entries) {
    var F = function (x) { return new werk.WFloat(x); };
    return { schema_version: 1, name: name, width: W, height: H, resolution_dpi: F(dpi), color_mode: "Rgb", sample_type: "U8",
      color_space: null, icc_profile: null, layers: entries, channels: [], quick_mask: null, quick_mask_unselected: false, selection: null,
      patterns: [], paths: [], work_path: null, clipping_path: null, layer_comps: [], last_applied_comp: null, last_document_state: null,
      text_styles: null, variables: null, metadata: null, guides: { horizontal: [], vertical: [] },
      global_light: { angle: F(120), altitude: F(30) }, color_table: null, duotone: null,
      measurement: { scale: { pixel_length: F(1), logical_length: F(1), units: "pixels" }, count_groups: [], active_count_group: 0, ruler: null },
      notes: [], slices: { groupName: "", list: [] }, timeline: null, file_encoding: {}, psd: null, fonts: [], app: { document_id: 0 } };
  }

  return { pngFallbacks: function () { return PNG_FALLBACKS; }, rm: rm, openWerk: openWerk, exportImage: exportImage, exportRasterLayers: exportRasterLayers, layerRGBA8: layerRGBA8,
           compositePNG: compositePNG, version: VERSION, setLog: function (p) { LOG = p; }, withPrefs: withPrefs };
})();
