// werk for Illustrator 2020 (ExtendScript, ES3). Read and write profile
// vector-art/1 and image/1 packages. Needs werk.jsx (the werk release library,
// vendored byte for byte beside this file) to be evaluated first.
//
//   werkAI.openWerk(path, opts)            -> {doc, report[], verdict, profile}
//   werkAI.exportVectorArt(doc, out, opts) -> {manifest_sha256, report[]}
//   werkAI.exportImage(doc, out, opts)     -> {manifest_sha256}
//   werkAI.dumpDocument(doc)               -> the document's art as vector-art/1 objects
//
// Coordinates: vector-art/1 is y DOWN in points; Illustrator's document
// coordinate system is y UP. Every point maps (x, y) <-> (x, -y). The script
// sets app.coordinateSystem to DOCUMENTCOORDINATESYSTEM while it works and
// restores it afterwards.
var werkAI = (function () {
  var TOOL = "werk-illustrator", VERSION = "1.0.0";

  // ------------------------------------------------------------------ helpers
  function num(v) { return (v instanceof werk.WFloat) ? v.value : v; }
  function hasOwn(o, k) { return Object.prototype.hasOwnProperty.call(o, k); }
  function rep(list, sev, code, msg) { list.push({ severity: sev, code: code, message: msg }); }
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
  // JSON payloads can be megabytes; werk.jsonParse is exact but slow in
  // ExtendScript. json2's validation (the ES3 standard way) + eval is fast and
  // refuses anything that is not JSON text before it is evaluated.
  function fastJson(bytes) {
    // U+2028 / U+2029 are legal inside JSON strings but end a line in an ES3 string literal
    var text = werk.utf8Decode(bytes).replace(/\u2028/g, "\\u2028").replace(/\u2029/g, "\\u2029");
    var t = text.replace(/\\(?:["\\\/bfnrt]|u[0-9a-fA-F]{4})/g, "@")
      .replace(/"[^"\\\n\r]*"|true|false|null|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?/g, "]")
      .replace(/(?:^|:|,)(?:\s*\[)+/g, "");
    if (!/^[\],:{}\s]*$/.test(t)) { return werk.jsonParse(text); }
    return eval("(" + text + ")");
  }
  function inflateZlib(bytes, size) {
    var cmf = bytes.charCodeAt(0), flg = bytes.charCodeAt(1);
    if ((cmf & 15) !== 8 || ((cmf << 8) | flg) % 31 !== 0 || (flg & 32)) { throw new Error("not a zlib stream (RFC 1950)"); }
    return werk.inflateRaw(bytes.substring(2), size || (1 << 30));
  }
  function resolvedVersion(pkg, id) {
    var n = pkg.node(id), i; if (!n) { return null; }
    for (i = 0; i < n.versions.length; i++) { if (n.versions[i].v === n.resolved) { return n.versions[i]; } }
    return null;
  }
  // A layer / symbol / pattern payload, also when it is "stored apart" (PROFILE-VECTOR-ART 3.1).
  function readUnitPayload(pkg, id) {
    var obj = fastJson(pkg.readPayload(id));
    if (obj && obj.external) {
      var ver = resolvedVersion(pkg, id), cf = null, i;
      for (i = 0; i < ver.files.length; i++) { if (ver.files[i].role === obj.external.role) { cf = ver.files[i].path; } }
      if (!cf) { throw new Error(id + ": no file of role " + obj.external.role); }
      var raw = pkg.readFile(cf), inf = inflateZlib(raw, num(obj.external.bytes));
      if (inf.length !== num(obj.external.bytes)) { throw new Error(id + ": inflated size differs from external.bytes"); }
      if (werk.sha256Hex(inf) !== obj.external.sha256) { throw new Error(id + ": inflated sha256 differs from external.sha256"); }
      obj = fastJson(inf);
    }
    return obj;
  }

  // ------------------------------------------------------------------ colour
  function toAIColor(c, report) {
    if (!c) { return new NoColor(); }
    var m = c.model, out;
    if (m === "rgb") { out = new RGBColor(); out.red = num(c.r) * 255; out.green = num(c.g) * 255; out.blue = num(c.b) * 255; return out; }
    if (m === "cmyk") { out = new CMYKColor(); out.cyan = num(c.c) * 100; out.magenta = num(c.m) * 100; out.yellow = num(c.y) * 100; out.black = num(c.k) * 100; return out; }
    if (m === "gray") { out = new GrayColor(); out.gray = num(c.k) * 100; return out; }
    if (m === "lab") { out = new LabColor(); out.l = num(c.l); out.a = num(c.a); out.b = num(c.b); return out; }
    rep(report, "warn", "colour-model-unknown", "colour model " + m + " drawn as none");
    return new NoColor();
  }
  function round6(x) { return Math.round(x * 1e6) / 1e6; }
  function fromAIColor(col) {
    var t = col.typename;
    if (t === "RGBColor") { return { model: "rgb", r: round6(col.red / 255), g: round6(col.green / 255), b: round6(col.blue / 255) }; }
    if (t === "CMYKColor") { return { model: "cmyk", c: round6(col.cyan / 100), m: round6(col.magenta / 100), y: round6(col.yellow / 100), k: round6(col.black / 100) }; }
    if (t === "GrayColor") { return { model: "gray", k: round6(col.gray / 100) }; }
    if (t === "LabColor") { return { model: "lab", l: col.l, a: col.a, b: col.b }; }
    if (t === "SpotColor") { return fromAIColor(col.spot.color); }
    return null;
  }
  var BLEND_TO_AI = null, AI_TO_BLEND = null;
  function blendTables() {
    if (BLEND_TO_AI) { return; }
    var pairs = [["Normal", BlendModes.NORMAL], ["Multiply", BlendModes.MULTIPLY], ["Screen", BlendModes.SCREEN],
      ["Overlay", BlendModes.OVERLAY], ["SoftLight", BlendModes.SOFTLIGHT], ["HardLight", BlendModes.HARDLIGHT],
      ["ColorDodge", BlendModes.COLORDODGE], ["ColorBurn", BlendModes.COLORBURN], ["Darken", BlendModes.DARKEN],
      ["Lighten", BlendModes.LIGHTEN], ["Difference", BlendModes.DIFFERENCE], ["Exclusion", BlendModes.EXCLUSION],
      ["Hue", BlendModes.HUE], ["Saturation", BlendModes.SATURATIONBLEND], ["Color", BlendModes.COLORBLEND],
      ["Luminosity", BlendModes.LUMINOSITY]];
    BLEND_TO_AI = {}; AI_TO_BLEND = {};
    for (var i = 0; i < pairs.length; i++) { BLEND_TO_AI[pairs[i][0]] = pairs[i][1]; AI_TO_BLEND[String(pairs[i][1])] = pairs[i][0]; }
  }

  // ------------------------------------------------------------------ READ
  function applyCommon(item, o, report) {
    blendTables();
    if (o.name) { try { item.name = o.name; } catch (e0) { } }
    if (o.opacity !== undefined) { item.opacity = num(o.opacity) * 100; }
    if (o.blend && o.blend !== "Normal") {
      if (hasOwn(BLEND_TO_AI, o.blend)) { item.blendingMode = BLEND_TO_AI[o.blend]; }
      else { rep(report, "info", "blend-not-mapped", "object " + o.id + ": blend " + o.blend + " opens as Normal"); }
    }
    if (o.visible === false) { item.hidden = true; }
    if (o.appearance && o.appearance.effects && o.appearance.effects.length) {
      rep(report, "info", "effects-not-applied", "object " + o.id + ": " + o.appearance.effects.length + " live effect(s) not applied");
    }
    if (o.mask) { rep(report, "info", "opacity-mask-not-applied", "object " + o.id); }
  }
  function lastItem(o, kind) {
    var items = (o.appearance && o.appearance.items) || [], i, found = null, n = 0;
    for (i = 0; i < items.length; i++) { if (items[i].kind === kind && items[i].visible !== false) { found = items[i]; n++; } }
    return { item: found, count: n };
  }
  function gradientColor(doc, p, report, oid) {
    var g = p.gradient, gr = doc.gradients.add(), i, st = g.stops || [];
    gr.type = (g.kind === "Radial") ? GradientType.RADIAL : GradientType.LINEAR;
    while (gr.gradientStops.length < st.length) { gr.gradientStops.add(); }
    for (i = 0; i < st.length; i++) {
      var gs = gr.gradientStops[i];
      gs.rampPoint = Math.max(0, Math.min(100, num(st[i].offset) * 100));
      gs.color = toAIColor(st[i].color, report);
      if (st[i].opacity !== undefined) { gs.opacity = num(st[i].opacity) * 100; }
      if (st[i].midpoint !== undefined) { gs.midPoint = Math.max(13, Math.min(87, num(st[i].midpoint) * 100)); }
    }
    var gc = new GradientColor(); gc.gradient = gr;
    if (p.angle !== undefined) { gc.angle = num(p.angle); }
    rep(report, "info", "gradient-geometry-approximate", "object " + oid + ": gradient placed by angle only");
    return gc;
  }
  function paintTo(doc, p, report, oid) {
    if (!p || p.type === "none") { return null; }
    if (p.type === "solid") { return toAIColor(p.color, report); }
    if (p.type === "gradient") { return gradientColor(doc, p, report, oid); }
    rep(report, "info", "paint-not-mapped", "object " + oid + ": " + p.type + " paint drawn as none");
    return null;
  }
  function applyPaint(doc, item, o, report) {
    var f = lastItem(o, "fill"), s = lastItem(o, "stroke"), c;
    if (f.count > 1 || s.count > 1) { rep(report, "info", "appearance-stack-reduced", "object " + o.id + ": " + f.count + " fills / " + s.count + " strokes, the top one of each kept"); }
    c = f.item ? paintTo(doc, f.item.paint, report, o.id) : null;
    if (c) { item.filled = true; item.fillColor = c; } else { item.filled = false; }
    // Illustrator ignores GradientColor.angle on assignment: turn the fill's gradient alone
    // (angles are counter-clockwise on screen in both models, 0 = left to right)
    if (c && c.typename === "GradientColor" && f.item.paint.angle !== undefined && num(f.item.paint.angle) !== 0) {
      try { item.rotate(num(f.item.paint.angle), false, false, true, false, Transformation.CENTER); } catch (eR) { }
    }
    c = s.item ? paintTo(doc, s.item.paint, report, o.id) : null;
    if (c && num(s.item.width) > 0) {
      item.stroked = true; item.strokeColor = c; item.strokeWidth = num(s.item.width);
      var si = s.item;
      if (si.cap) { item.strokeCap = si.cap === "Round" ? StrokeCap.ROUNDENDCAP : (si.cap === "Square" ? StrokeCap.PROJECTINGENDCAP : StrokeCap.BUTTENDCAP); }
      if (si.join) { item.strokeJoin = si.join === "Round" ? StrokeJoin.ROUNDENDJOIN : (si.join === "Bevel" ? StrokeJoin.BEVELENDJOIN : StrokeJoin.MITERENDJOIN); }
      if (si.miter_limit !== undefined) { item.strokeMiterLimit = Math.max(1, num(si.miter_limit)); }
      if (si.dash && si.dash.array && si.dash.array.length) {
        var d = [], k; for (k = 0; k < si.dash.array.length; k++) { d.push(num(si.dash.array[k])); }
        item.strokeDashes = d; if (si.dash.offset !== undefined) { item.strokeDashOffset = num(si.dash.offset); }
      }
    } else { item.stroked = false; }
  }
  function pt(a) { return [num(a[0]), -num(a[1])]; }
  function buildSubpath(container, sub) {
    var pi = container.pathItems.add(), i, an = sub.anchors || [];
    for (i = 0; i < an.length; i++) {
      var a = an[i], pp = pi.pathPoints.add();
      pp.anchor = pt(a.p);
      pp.leftDirection = pt(a["in"] || a.p);
      pp.rightDirection = pt(a.out || a.p);
      pp.pointType = a.kind === "Smooth" ? PointType.SMOOTH : PointType.CORNER;
    }
    pi.closed = !!sub.closed;
    return pi;
  }
  function buildPath(doc, container, o, report) {
    var subs = o.kind.path.subpaths || [], item, i;
    if (subs.length === 1) {
      item = buildSubpath(container, subs[0]);
      if (o.kind.rule === "EvenOdd") { item.evenodd = true; }
      applyPaint(doc, item, o, report);
    } else {
      item = container.compoundPathItems.add();
      for (i = 0; i < subs.length; i++) { buildSubpath(item, subs[i]); }
      if (item.pathItems.length) {
        if (o.kind.rule === "EvenOdd") { item.pathItems[0].evenodd = true; }
        applyPaint(doc, item.pathItems[0], o, report);
      }
      rep(report, "info", "multi-subpath-as-compound", "object " + o.id + ": " + subs.length + " subpaths opened as one compound path");
    }
    if (o.kind.guide) { try { item.guides = true; } catch (e1) { } }
    applyCommon(item, o, report);
    return item;
  }
  function buildCompound(doc, container, o, report) {
    var item = container.compoundPathItems.add(), ch = o.kind.children || [], i, j;
    for (i = 0; i < ch.length; i++) {
      if (ch[i].kind.type !== "path") { rep(report, "warn", "compound-member-skipped", "object " + ch[i].id + " (" + ch[i].kind.type + ") in compound " + o.id); continue; }
      var subs = ch[i].kind.path.subpaths || [];
      for (j = 0; j < subs.length; j++) { buildSubpath(item, subs[j]); }
    }
    if (item.pathItems.length) {
      if (o.kind.rule === "EvenOdd") { item.pathItems[0].evenodd = true; }
      applyPaint(doc, item.pathItems[0], o, report);
    }
    applyCommon(item, o, report);
    return item;
  }
  function findFont(family, style) {
    var fonts = app.textFonts, i, best = null;
    for (i = 0; i < fonts.length; i++) {
      var f = fonts[i];
      if (f.family === family) { if (!style || f.style === style) { return f; } if (!best) { best = f; } }
    }
    return best;
  }
  function buildText(doc, container, o, report) {
    var k = o.kind, xf = k.xf, tf, i, kind = k.kind ? k.kind.kind : "point";
    var text = "", runs = k.runs || [];
    for (i = 0; i < runs.length; i++) { text += runs[i].text; }
    text = text.replace(/\n/g, "\r");
    if (kind === "area" && k.kind.frame) {
      var fp = container.pathItems.add(), subs = k.kind.frame.subpaths || [];
      if (subs.length) {
        var an = subs[0].anchors || [];
        for (i = 0; i < an.length; i++) {
          var x = num(an[i].p[0]), y = num(an[i].p[1]);
          var pp = fp.pathPoints.add();
          pp.anchor = [num(xf[0]) * x + num(xf[2]) * y + num(xf[4]), -(num(xf[1]) * x + num(xf[3]) * y + num(xf[5]))];
          pp.leftDirection = pp.anchor; pp.rightDirection = pp.anchor;
        }
        fp.closed = true;
      }
      tf = container.textFrames.areaText(fp);
    } else {
      if (kind !== "point") { rep(report, "info", "text-kind-as-point", "object " + o.id + ": " + kind + " type opened as point type"); }
      tf = container.textFrames.pointText([num(xf[4]), -num(xf[5])]);
    }
    tf.contents = text.length ? text : " ";
    // character attributes run by run
    var pos = 0, missing = {};
    for (i = 0; i < runs.length; i++) {
      var n = runs[i].text.length, st = runs[i].style || {}, j;
      if (n === 0) { continue; }
      var ca = [];
      for (j = pos; j < pos + n && j < tf.characters.length; j++) { ca.push(tf.characters[j]); }
      for (j = 0; j < ca.length; j++) {
        var a = ca[j].characterAttributes;
        if (st.size !== undefined) { a.size = num(st.size); }
        var f = findFont(st.font_family, st.font_style);
        if (f) { a.textFont = f; } else { missing[st.font_family + " " + (st.font_style || "")] = true; }
        if (st.tracking !== undefined) { a.tracking = num(st.tracking); }
        if (st.fill) { var c = paintTo(doc, st.fill, report, o.id); if (c) { a.fillColor = c; } }
      }
      pos += n;
    }
    for (var mf in missing) { if (hasOwn(missing, mf)) { rep(report, "info", "font-substituted", "object " + o.id + ": font " + mf + " not installed"); } }
    var a0 = num(xf[0]), b0 = num(xf[1]), c0 = num(xf[2]), d0 = num(xf[3]);
    if (kind !== "area" && (Math.abs(a0 - 1) > 1e-9 || Math.abs(b0) > 1e-9 || Math.abs(c0) > 1e-9 || Math.abs(d0 - 1) > 1e-9)) {
      var m = app.getIdentityMatrix(); m.mValueA = a0; m.mValueB = -b0; m.mValueC = -c0; m.mValueD = d0; m.mValueTX = 0; m.mValueTY = 0;
      tf.transform(m, true, true, true, true, 1, Transformation.DOCUMENTORIGIN);
      tf.position = tf.position; // keep
      rep(report, "info", "text-transform-approximate", "object " + o.id + ": text matrix applied about the document origin");
    }
    applyCommon(tf, o, report);
    return tf;
  }
  function buildImage(doc, container, o, ctx, report) {
    var k = o.kind, key = k.key, ent = ctx.images[key];
    if (!ent || !ent.node) { rep(report, "warn", "image-missing", "object " + o.id + ": image key has no node; skipped"); return null; }
    var png;
    try { png = ctx.pkg.readPayload(ent.node); } catch (e) { rep(report, "warn", "image-dead", "object " + o.id + ": " + e.message); return null; }
    var p = ctx.scratch + "/img-" + o.id + ".png";
    writeBin(p, png);
    ctx.temp.push(p);
    var pi = container.placedItems.add(); pi.file = new File(p);
    var xf = k.xf, w = num(k.width), h = num(k.height);
    var a = num(xf[0]), b = num(xf[1]), c = num(xf[2]), d = num(xf[3]), e = num(xf[4]), f = num(xf[5]);
    if (Math.abs(b) < 1e-9 && Math.abs(c) < 1e-9 && a > 0 && d > 0) {
      pi.width = a * w; pi.height = d * h; pi.position = [e, -f];
    } else {
      pi.width = w; pi.height = h; pi.position = [0, 0];
      var m = app.getIdentityMatrix(); m.mValueA = a; m.mValueB = -b; m.mValueC = -c; m.mValueD = d; m.mValueTX = e; m.mValueTY = -f;
      pi.transform(m, true, true, true, true, 1, Transformation.DOCUMENTORIGIN);
      rep(report, "info", "image-transform-approximate", "object " + o.id);
    }
    try { pi.embed(); } catch (e2) { rep(report, "info", "image-not-embedded", "object " + o.id + ": " + e2.message); }
    // embed() replaces the placed item; the new raster is the top item of the container
    var item = container.pageItems[0];
    applyCommon(item, o, report);
    return item;
  }
  function buildChildren(doc, container, list, ctx, report) {
    var i;
    for (i = 0; i < list.length; i++) { buildObject(doc, container, list[i], ctx, report); }
  }
  function buildObject(doc, container, o, ctx, report) {
    var t = o.kind.type, item = null;
    ctx.counts[t] = (ctx.counts[t] || 0) + 1;
    if (t === "path") { item = buildPath(doc, container, o, report); }
    else if (t === "compound") { item = buildCompound(doc, container, o, report); }
    else if (t === "group") {
      item = container.groupItems.add();
      var ch = o.kind.children || [];
      if (o.kind.clip && ch.length) {
        buildChildren(doc, item, ch.slice(1), ctx, report);
        var cp = buildObject(doc, item, ch[0], ctx, report);   // created last = topmost, as Illustrator wants
        try { if (cp && cp.typename === "PathItem") { cp.clipping = true; } else if (cp && cp.typename === "CompoundPathItem") { cp.pathItems[0].clipping = true; } item.clipped = true; }
        catch (e3) { rep(report, "warn", "clip-not-applied", "group " + o.id + ": " + e3.message); }
      } else { buildChildren(doc, item, ch, ctx, report); }
      applyCommon(item, o, report);
    }
    else if (t === "layer") {
      item = container.layers.add();
      buildChildren(doc, item, o.kind.children || [], ctx, report);
      applyLayer(item, o, report);
    }
    else if (t === "text") { item = buildText(doc, container, o, report); }
    else if (t === "image") { item = buildImage(doc, container, o, ctx, report); }
    else {
      ctx.skipped[t] = (ctx.skipped[t] || 0) + 1;
      rep(report, "info", "object-kind-not-mapped", "object " + o.id + ": kind " + t + " is not built in Illustrator by this plug-in");
      return null;
    }
    if (item && o.kind.type === "path" && o.kind.clipping && item.typename === "PathItem") { try { item.clipping = true; } catch (e4) { } }
    if (item && o.locked) { ctx.lock.push(item); }
    return item;
  }
  function applyLayer(layer, o, report) {
    blendTables();
    if (o.name) { layer.name = o.name; }
    if (o.opacity !== undefined) { layer.opacity = num(o.opacity) * 100; }
    if (o.blend && hasOwn(BLEND_TO_AI, o.blend)) { layer.blendingMode = BLEND_TO_AI[o.blend]; }
    if (o.kind.printable === false) { layer.printable = false; }
    if (o.kind.template === true) { layer.isTemplate = true; }
    if (o.visible === false) { layer.visible = false; }
    if (o.locked) { layer.locked = true; }
  }

  function openWerk(path, opts) {
    opts = opts || {};
    var report = [], pkg = werk.open(path), v = pkg.verdict(), i;
    for (i = 0; i < pkg.report.length; i++) { var e = pkg.report[i]; report.push({ severity: e.severity, code: e.code, message: (e.node ? e.node + ": " : "") + e.message }); }
    var profile = pkg.manifest.profile;
    if (profile === "vector-art/1") { return openVectorArt(pkg, v, report, opts); }
    if (profile === "image/1" || (pkg.manifest.primary && pkg.manifest.primary.image)) { return openImage(pkg, v, report, opts, profile); }
    throw new Error("profile " + profile + " is not one Illustrator opens (vector-art/1, image/1)");
  }
  // pixel size from the file header: PNG IHDR, JPEG SOFn; null when unknown
  function imageSize(b) {
    if (b.substring(0, 8) === "\x89PNG\r\n\x1a\n") { var i = werk.pngInfo(b); return [i.width, i.height]; }
    if (b.charCodeAt(0) === 0xFF && b.charCodeAt(1) === 0xD8) {
      var o = 2, n = b.length, m, len;
      while (o + 4 < n) {
        if (b.charCodeAt(o) !== 0xFF) { o++; continue; }
        m = b.charCodeAt(o + 1); len = (b.charCodeAt(o + 2) << 8) | b.charCodeAt(o + 3);
        if (m >= 0xC0 && m <= 0xCF && m !== 0xC4 && m !== 0xC8 && m !== 0xCC) {
          return [(b.charCodeAt(o + 7) << 8) | b.charCodeAt(o + 8), (b.charCodeAt(o + 5) << 8) | b.charCodeAt(o + 6)];
        }
        if (m === 0xD8 || m === 0x01 || (m >= 0xD0 && m <= 0xD7)) { o += 2; } else { o += 2 + len; }
      }
    }
    return null;
  }
  // The primary image in a new document whose artboard is the image, one point per pixel,
  // so that a 72 ppi export gives the image's own pixel size back.
  function openImage(pkg, v, report, opts, profile) {
    var pi = pkg.primaryImage(), ext = /\.(\w+)$/.exec(pi.path), sd = scratchDir(opts);
    var p = sd + "/primary-" + new Date().getTime() + "." + (ext ? ext[1].toLowerCase() : "png");
    writeBin(p, pi.bytes);
    var wh = imageSize(pi.bytes), doc;
    if (!wh) {
      doc = app.open(new File(p));
      rep(report, "info", "image-size-unknown", pi.path + ": opened by Illustrator as it chooses");
    } else {
      doc = app.documents.add(DocumentColorSpace.RGB, wh[0], wh[1]);
      var prevCS = app.coordinateSystem;
      app.coordinateSystem = CoordinateSystem.DOCUMENTCOORDINATESYSTEM;
      try {
        doc.artboards[0].artboardRect = [0, 0, wh[0], -wh[1]];
        var it = doc.layers[0].placedItems.add(); it.file = new File(p);
        it.width = wh[0]; it.height = wh[1]; it.position = [0, 0];
        try { it.embed(); } catch (eE) { rep(report, "info", "image-not-embedded", eE.message); }
        var top = doc.layers[0].pageItems[0];
        top.width = wh[0]; top.height = wh[1]; top.position = [0, 0];
      } finally { app.coordinateSystem = prevCS; }
    }
    try { new File(p).remove(); } catch (eR) { }
    if (profile !== "image/1") { rep(report, "info", "opened-primary-image", "profile " + profile + ": only primary.image (" + pi.path + ") was opened"); }
    return { doc: doc, report: report, verdict: v, profile: profile, primary_path: pi.path, size: wh };
  }
  function openVectorArt(pkg, v, report, opts) {
    var m = pkg.manifest, docId = (m.primary || {}).document, ctx = { pkg: pkg, images: {}, counts: {}, skipped: {}, lock: [], temp: [], scratch: scratchDir(opts) };
    var dj = fastJson(pkg.readPayload(docId)), i;
    var abs = [];
    for (i = 0; i < (dj.artboards || []).length; i++) {
      try { abs.push(fastJson(pkg.readPayload(dj.artboards[i]))); }
      catch (e) { rep(report, "error", "artboard-dead", dj.artboards[i] + ": " + e.message); }
    }
    for (i = 0; i < (dj.images || []).length; i++) { ctx.images[dj.images[i].key] = dj.images[i]; }
    var r0 = abs.length ? abs[0].rect : { x0: 0, y0: 0, x1: 612, y1: 792 };
    var doc = app.documents.add(dj.color_mode === "Cmyk" ? DocumentColorSpace.CMYK : DocumentColorSpace.RGB,
                                num(r0.x1) - num(r0.x0), num(r0.y1) - num(r0.y0));
    var prevCS = app.coordinateSystem;
    app.coordinateSystem = CoordinateSystem.DOCUMENTCOORDINATESYSTEM;
    try {
      for (i = 0; i < abs.length; i++) {
        var r = abs[i].rect, rect = [num(r.x0), -num(r.y0), num(r.x1), -num(r.y1)];
        var ab = i === 0 ? doc.artboards[0] : doc.artboards.add(rect);
        ab.artboardRect = rect;
        if (abs[i].name) { ab.name = abs[i].name; }
      }
      var placeholder = doc.layers[0];
      for (i = 0; i < (dj.layers || []).length; i++) {
        var lid = dj.layers[i], lp;
        try { lp = readUnitPayload(pkg, lid); }
        catch (e2) { rep(report, "error", "layer-dead", lid + ": " + e2.message + "; the document opens without it"); continue; }
        var lo = lp.layer, L = doc.layers.add();
        ctx.counts.layer = (ctx.counts.layer || 0) + 1;
        buildChildren(doc, L, lo.kind.children || [], ctx, report);
        applyLayer(L, lo, report);
      }
      if (doc.layers.length > 1 && placeholder.pageItems.length === 0 && placeholder.layers.length === 0) { placeholder.remove(); }
      for (i = 0; i < ctx.lock.length; i++) { try { ctx.lock[i].locked = true; } catch (e5) { } }
      if ((dj.symbols || []).length) { rep(report, "info", "symbols-not-mapped", dj.symbols.length + " symbol(s): instances are not built"); }
      if ((dj.patterns || []).length) { rep(report, "info", "patterns-not-mapped", dj.patterns.length + " pattern(s)"); }
    } finally { app.coordinateSystem = prevCS; }
    for (i = 0; i < ctx.temp.length; i++) { try { new File(ctx.temp[i]).remove(); } catch (e6) { } }
    return { doc: doc, report: report, verdict: v, profile: "vector-art/1", counts: ctx.counts, skipped: ctx.skipped, entity: m.entity };
  }

  // ------------------------------------------------------------------ WRITE (dump)
  function aiPt(p) { return [round6(p[0]), round6(-p[1])]; }
  function samePt(a, b) { return Math.abs(a[0] - b[0]) < 1e-9 && Math.abs(a[1] - b[1]) < 1e-9; }
  function dumpSubpath(pi) {
    var an = [], i, pts = pi.pathPoints;
    for (i = 0; i < pts.length; i++) {
      var q = pts[i], a = { p: aiPt(q.anchor) }, li = aiPt(q.leftDirection), ro = aiPt(q.rightDirection);
      if (!samePt(li, a.p)) { a["in"] = li; }
      if (!samePt(ro, a.p)) { a.out = ro; }
      if (q.pointType === PointType.SMOOTH) { a.kind = "Smooth"; }
      an.push(a);
    }
    return { anchors: an, closed: !!pi.closed };
  }
  function dumpPaint(col, ctx) {
    if (!col) { return { type: "none" }; }
    var t = col.typename;
    if (t === "NoColor") { return { type: "none" }; }
    if (t === "GradientColor") {
      var g = col.gradient, stops = [], i;
      for (i = 0; i < g.gradientStops.length; i++) {
        var gs = g.gradientStops[i], c = fromAIColor(gs.color) || { model: "rgb", r: 0, g: 0, b: 0 };
        stops.push({ offset: round6(gs.rampPoint / 100), color: c, opacity: round6(gs.opacity / 100), midpoint: round6(gs.midPoint / 100) });
      }
      // the direction lives in the gradient's matrix once the fill has been turned (col.angle stays 0)
      var ang = col.angle;
      try { var gm = col.matrix; if (gm && (Math.abs(gm.mValueB) > 1e-12 || gm.mValueA < 0)) { ang = Math.atan2(gm.mValueB, gm.mValueA) * 180 / Math.PI + col.angle; } } catch (eA) { }
      while (ang > 180) { ang -= 360; } while (ang <= -180) { ang += 360; }
      return { type: "gradient", gradient: { kind: g.type === GradientType.RADIAL ? "Radial" : "Linear", stops: stops }, angle: round6(ang) };
    }
    if (t === "PatternColor") { ctx.notes["pattern-paint-as-none"] = (ctx.notes["pattern-paint-as-none"] || 0) + 1; return { type: "none" }; }
    var cc = fromAIColor(col);
    return cc ? { type: "solid", color: cc } : { type: "none" };
  }
  function dumpAppearance(pi, ctx) {
    var items = [];
    items.push({ kind: "fill", paint: pi.filled ? dumpPaint(pi.fillColor, ctx) : { type: "none" } });
    var st = { kind: "stroke", paint: pi.stroked ? dumpPaint(pi.strokeColor, ctx) : { type: "none" }, width: pi.stroked ? round6(pi.strokeWidth) : 0 };
    if (pi.stroked) {
      st.cap = pi.strokeCap === StrokeCap.ROUNDENDCAP ? "Round" : (pi.strokeCap === StrokeCap.PROJECTINGENDCAP ? "Square" : "Butt");
      st.join = pi.strokeJoin === StrokeJoin.ROUNDENDJOIN ? "Round" : (pi.strokeJoin === StrokeJoin.BEVELENDJOIN ? "Bevel" : "Miter");
      st.miter_limit = round6(pi.strokeMiterLimit);
      if (pi.strokeDashes && pi.strokeDashes.length) {
        var d = [], k; for (k = 0; k < pi.strokeDashes.length; k++) { d.push(round6(pi.strokeDashes[k])); }
        st.dash = { array: d, offset: round6(pi.strokeDashOffset) };
      }
    }
    items.push(st);
    return { items: items };
  }
  function commonOut(o, item) {
    blendTables();
    if (item.name) { o.name = item.name; }
    if (item.opacity !== undefined && Math.abs(item.opacity - 100) > 1e-9) { o.opacity = round6(item.opacity / 100); }
    var bm = AI_TO_BLEND[String(item.blendingMode)];
    if (bm && bm !== "Normal") { o.blend = bm; }
    if (item.hidden) { o.visible = false; }
    if (item.locked) { o.locked = true; }
  }
  function dumpItem(item, ctx) {
    var t = item.typename, o = { id: ctx.nextId++ }, i;
    if (t === "PathItem") {
      o.kind = { type: "path", path: { subpaths: [dumpSubpath(item)] } };
      if (item.evenodd) { o.kind.rule = "EvenOdd"; }
      if (item.clipping) { o.kind.clipping = true; }
      if (item.guides) { o.kind.guide = true; }
      if (!item.clipping && !item.guides) { o.appearance = dumpAppearance(item, ctx); }
      commonOut(o, item);
      ctx.counts.path = (ctx.counts.path || 0) + 1;
      return o;
    }
    if (t === "CompoundPathItem") {
      var ch = [], pis = item.pathItems;
      for (i = pis.length - 1; i >= 0; i--) { ch.push({ id: ctx.nextId++, kind: { type: "path", path: { subpaths: [dumpSubpath(pis[i])] } } }); }
      o.kind = { type: "compound", children: ch };
      if (pis.length && pis[0].evenodd) { o.kind.rule = "EvenOdd"; }
      if (pis.length) { o.appearance = dumpAppearance(pis[0], ctx); }
      commonOut(o, item);
      ctx.counts.compound = (ctx.counts.compound || 0) + 1;
      return o;
    }
    if (t === "GroupItem") {
      var kids = dumpChildren(item.pageItems, ctx);
      o.kind = { type: "group", children: kids };
      if (item.clipped) {
        // Illustrator keeps the clipping path on top; vector-art/1 wants it FIRST
        var ci = -1;
        for (i = 0; i < kids.length; i++) { if (kids[i].kind.clipping) { ci = i; } }
        if (ci > 0) { var cpo = kids.splice(ci, 1)[0]; kids.unshift(cpo); }
        o.kind.clip = true;
      }
      commonOut(o, item);
      ctx.counts.group = (ctx.counts.group || 0) + 1;
      return o;
    }
    if (t === "TextFrame") { return dumpText(item, o, ctx); }
    if (t === "RasterItem" || t === "PlacedItem") { return dumpImage(item, o, ctx); }
    ctx.skipped[t] = (ctx.skipped[t] || 0) + 1;
    ctx.nextId--;
    return null;
  }
  function dumpText(tf, o, ctx) {
    var runs = [], i, paras = tf.paragraphs;
    for (i = 0; i < paras.length; i++) {
      var p = paras[i], txt = p.contents.replace(/\r/g, "\n") + (i < paras.length - 1 ? "\n" : "");
      if (!txt.length) { continue; }
      var a = p.characters.length ? p.characters[0].characterAttributes : tf.textRange.characterAttributes;
      var fill = { type: "none" };
      try { fill = dumpPaint(a.fillColor, ctx); } catch (e) { }
      var st = { font_family: a.textFont.family, font_style: a.textFont.style, size: round6(a.size), fill: fill, tracking: a.tracking };
      runs.push({ text: txt, style: st });
    }
    if (!runs.length) { runs.push({ text: "", style: { font_family: "", size: 12, fill: { type: "none" } } }); }
    if (tf.kind === TextType.AREATEXT) {
      // area type: the frame's own path in document space, text space = document space
      var fr = dumpSubpath(tf.textPath);
      for (i = 0; i < fr.anchors.length; i++) { delete fr.anchors[i]["in"]; delete fr.anchors[i].out; delete fr.anchors[i].kind; }
      fr.closed = true;
      o.kind = { type: "text", kind: { kind: "area", frame: { subpaths: [fr] } }, xf: [1, 0, 0, 1, 0, 0], runs: runs };
    } else {
      var xf = [1, 0, 0, 1, 0, 0];
      try { var m = tf.matrix, ax = tf.anchor; xf = [round6(m.mValueA), round6(-m.mValueB), round6(-m.mValueC), round6(m.mValueD), round6(ax[0]), round6(-ax[1])]; }
      catch (eM) { var gb = tf.geometricBounds; xf = [1, 0, 0, 1, round6(gb[0]), round6(-gb[1])]; ctx.notes["text-origin-from-bounds"] = (ctx.notes["text-origin-from-bounds"] || 0) + 1; }
      o.kind = { type: "text", kind: { kind: "point" }, xf: xf, runs: runs };
      if (tf.kind === TextType.PATHTEXT) { ctx.notes["path-type-as-point"] = (ctx.notes["path-type-as-point"] || 0) + 1; }
    }
    commonOut(o, tf);
    ctx.counts.text = (ctx.counts.text || 0) + 1;
    return o;
  }
  function dumpImage(item, o, ctx) {
    // Pixels of a raster are not readable through the DOM: the plug-in renders
    // the item alone to PNG at its own size (export of a temporary document).
    var b = item.geometricBounds; // [l, t, r, b] y up
    var w = Math.max(1, Math.round(b[2] - b[0])), h = Math.max(1, Math.round(b[1] - b[3]));
    var key = "werk-ai-image-" + o.id, png = ctx.renderImages ? ctx.renderItem(item, w, h) : null;
    if (png) { ctx.images.push({ key: key, png: png, id: o.id }); }
    else { ctx.notes["image-without-pixels"] = (ctx.notes["image-without-pixels"] || 0) + 1; }
    o.kind = { type: "image", key: key, width: w, height: h, xf: [round6((b[2] - b[0]) / w), 0, 0, round6((b[1] - b[3]) / h), round6(b[0]), round6(-b[1])] };
    commonOut(o, item);
    ctx.counts.image = (ctx.counts.image || 0) + 1;
    return o;
  }
  function dumpChildren(items, ctx) {
    var out = [], i;
    for (i = items.length - 1; i >= 0; i--) {      // pageItems[0] is the front; vector-art lists bottom first
      var it = items[i];
      if (it.parent && it.parent.typename === "CompoundPathItem") { continue; }
      var o = dumpItem(it, ctx);
      if (o) { out.push(o); }
    }
    return out;
  }
  function firstZ(L) {
    var i;
    try { if (L.pageItems.length) { return L.pageItems[0].absoluteZOrderPosition; } } catch (e) { return null; }
    for (i = 0; i < L.layers.length; i++) { var z = firstZ(L.layers[i]); if (z !== null) { return z; } }
    return null;
  }
  function dumpLayer(L, ctx) {
    blendTables();
    var o = { id: ctx.nextId++, name: L.name }, kids = [], i;
    if (!L.layers.length) { kids = dumpChildren(L.pageItems, ctx); }
    else {
      // items and sublayers share one stacking order that the DOM exposes only through
      // absoluteZOrderPosition: order both by it (a sublayer by any item inside it)
      var ent = [], items = L.pageItems, k, okZ = true;
      for (i = 0; i < items.length; i++) {
        if (items[i].parent && items[i].parent.typename === "CompoundPathItem") { continue; }
        try { ent.push({ z: items[i].absoluteZOrderPosition, item: items[i] }); } catch (eZ) { okZ = false; ent.push({ z: -i, item: items[i] }); }
      }
      for (i = 0; i < L.layers.length; i++) {
        var z = firstZ(L.layers[i]);
        if (z === null) { okZ = false; z = 1e15 - i; }
        ent.push({ z: z, layer: L.layers[i] });
      }
      ent.sort(function (a, b) { return a.z - b.z; });     // larger absoluteZOrderPosition = nearer the front
      for (k = 0; k < ent.length; k++) {
        if (ent[k].layer) { kids.push(dumpLayer(ent[k].layer, ctx)); }
        else { var oo = dumpItem(ent[k].item, ctx); if (oo) { kids.push(oo); } }
      }
      if (!okZ) { ctx.notes["sublayer-order-approximate"] = (ctx.notes["sublayer-order-approximate"] || 0) + 1; }
    }
    o.kind = { type: "layer", color: { Custom: [Math.round(L.color.red), Math.round(L.color.green), Math.round(L.color.blue)] }, children: kids, printable: L.printable, template: L.isTemplate };
    if (!L.visible) { o.visible = false; }
    if (L.locked) { o.locked = true; }
    if (Math.abs(L.opacity - 100) > 1e-9) { o.opacity = round6(L.opacity / 100); }
    var bm = AI_TO_BLEND[String(L.blendingMode)];
    if (bm && bm !== "Normal") { o.blend = bm; }
    ctx.counts.layer = (ctx.counts.layer || 0) + 1;
    return o;
  }
  function fixNum(x, path, bad) {
    if (!isFinite(x)) { bad.push(path + "=" + x); return 0; }
    if (Math.floor(x) === x && Math.abs(x) > 9007199254740991) { bad.push(path + "=" + x); return new werk.WFloat(x); }
    return x;
  }
  // The document's art in vector-art/1 form: {artboards: [...], layers: [layer objects, bottom first]}
  function dumpDocument(doc, opts) {
    var prevCS = app.coordinateSystem, out = { artboards: [], layers: [] }, i;
    app.coordinateSystem = CoordinateSystem.DOCUMENTCOORDINATESYSTEM;
    var ctx = { nextId: 1, counts: {}, skipped: {}, notes: {}, images: [], renderImages: !!(opts && opts.renderItem), renderItem: opts && opts.renderItem };
    try {
      for (i = 0; i < doc.artboards.length; i++) {
        var r = doc.artboards[i].artboardRect;
        out.artboards.push({ schema_version: 1, id: i + 1, name: doc.artboards[i].name, rect: { x0: round6(r[0]), y0: round6(-r[1]), x1: round6(r[2]), y1: round6(-r[3]) } });
      }
      for (i = doc.layers.length - 1; i >= 0; i--) { out.layers.push(dumpLayer(doc.layers[i], ctx)); }
    } finally { app.coordinateSystem = prevCS; }
    // Illustrator reports some values (an unset attribute of a text range, the matrix of
    // a degenerate object) as huge numbers; the JSON writer refuses integers past 2^53.
    // Such a number is written as a binary64 (WFloat) and counted.
    var bad = [];
    (function san(v, path) {
      var k, i;
      if (v instanceof Array) { for (i = 0; i < v.length; i++) { if (typeof v[i] === "number") { v[i] = fixNum(v[i], path + "/" + i, bad); } else { san(v[i], path + "/" + i); } } return; }
      if (v && typeof v === "object" && !(v instanceof werk.WFloat)) {
        for (k in v) { if (hasOwn(v, k)) { if (typeof v[k] === "number") { v[k] = fixNum(v[k], path + "/" + k, bad); } else { san(v[k], path + "/" + k); } } }
      }
    })(out.layers, "");
    if (bad.length) { ctx.notes["number-out-of-range"] = bad.length; out.bad_numbers = bad.slice(0, 20); }
    out.counts = ctx.counts; out.skipped = ctx.skipped; out.notes = ctx.notes; out.images = ctx.images; out.next_id = ctx.nextId;
    return out;
  }

  // ------------------------------------------------------------------ WRITE (package)
  function utcNow() {
    var d = new Date();
    function p2(n) { return (n < 10 ? "0" : "") + n; }
    return d.getUTCFullYear() + "-" + p2(d.getUTCMonth() + 1) + "-" + p2(d.getUTCDate()) + "T" + p2(d.getUTCHours()) + ":" + p2(d.getUTCMinutes()) + ":" + p2(d.getUTCSeconds()) + "Z";
  }
  function exportPNG(doc, path, abIndex) {
    var o = new ExportOptionsPNG24(); o.artBoardClipping = true; o.transparency = true; o.antiAliasing = true;
    o.horizontalScale = 100; o.verticalScale = 100;
    doc.artboards.setActiveArtboardIndex(abIndex || 0);
    doc.exportFile(new File(path), ExportType.PNG24, o);
  }
  function exportSVG(doc, path) {
    var o = new ExportOptionsSVG(); o.embedRasterImages = true; o.fontType = SVGFontType.OUTLINEFONT;
    o.DTD = SVGDTDVersion.SVG1_1; o.documentEncoding = SVGDocumentEncoding.UTF8; o.saveMultipleArtboards = false;
    doc.exportFile(new File(path), ExportType.SVG, o);
  }
  function findExported(path) {
    // Illustrator may append the artboard name to an exported file name
    var f = new File(path); if (f.exists) { return f.fsName; }
    var dir = f.parent, base = f.name.replace(/\.[^.]*$/, ""), ext = f.name.replace(/^.*\./, ""), list = dir.getFiles(base + "*." + ext);
    return list.length ? list[0].fsName : null;
  }
  // Templates carry the vector-art/1 specification (spec/), which is not part of
  // the werk release's own spec tree (the GIMP plug-in does the same for raster-layers/1).
  function templateSpec(templatePath) {
    var tpl = werk.open(templatePath), tm = tpl.manifest;
    if (tm.profile !== "vector-art/1") { throw new Error("template " + templatePath + " is profile " + tm.profile + ", not vector-art/1"); }
    var ver = resolvedVersion(tpl, "spec"), files = {}, i;
    for (i = 0; i < ver.files.length; i++) {
      var p = ver.files[i].path, nm = p.replace(/^.*\//, "");
      if (/@\d+(\.|$)/.test(nm)) { continue; }
      files[p] = tpl.readFile(p);
    }
    return { manifest: tm, files: files, howto: tpl.readFile("HOW-TO-READ.md") };
  }
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
  function exportVectorArt(doc, out, opts) {
    opts = opts || {};
    var created = opts.created || utcNow(), sd = scratchDir(opts), stamp = new Date().getTime(), report = [];
    var tpl = templateSpec(opts.template);
    var tm = tpl.manifest, producer = { tool: TOOL, version: VERSION };
    var w = new werk.PackageWriter("vector-art/1", {
      name: opts.name || doc.name.replace(/\.[^.]*$/, "") || "Untitled", summary: null, uuid: opts.uuid, created: created,
      conventions: tm.conventions, manifestSchema: tm.manifest_schema, profileSpec: tm.profile_spec || null,
      specFiles: tpl.files, generator: producer, producer: producer, conventionsMap: tm.conventions_map
    });
    // The vector-art/1 manifest schema requires conventions_map; werk.jsx takes it as
    // `conventionsMap` (added after the first W5b report). An older werk.jsx ignores the
    // option: then set it the only way that build allows.
    if (w.conventionsMap === undefined) { w.ptab.conventions_map = tm.conventions_map; }
    // the profile's reading guide beside README.txt, as the template carries it
    if (typeof w.addReadmeFile === "function" && tpl.howto) { w.addReadmeFile("HOW-TO-READ.md", tpl.howto, "text/markdown"); }
    // LIBRARY GAP (reported): the release loaders' meta lists capabilities
    // ("summarize-points", "summarize-gsplat") that this profile's manifest schema
    // does not permit; keep the ones it permits (a subset is still true).
    restrictLoaderCaps(w, tpl.files[tm.manifest_schema]);
    var renderItem = function (item, wpx, hpx) {
      var tmp = app.documents.add(DocumentColorSpace.RGB, wpx, hpx), png = null;
      try {
        var dup = item.duplicate(tmp.layers[0], ElementPlacement.PLACEATBEGINNING);
        var b = dup.geometricBounds;
        tmp.artboards[0].artboardRect = [b[0], b[1], b[2], b[3]];
        var p = sd + "/img-" + stamp + "-" + Math.round(Math.random() * 1e9) + ".png";
        exportPNG(tmp, p, 0); var fp = findExported(p);
        if (fp) { png = readBin(fp); new File(fp).remove(); }
      } finally { tmp.close(SaveOptions.DONOTSAVECHANGES); }
      return png;
    };
    var dump = dumpDocument(doc, { renderItem: opts.withImages === false ? null : renderItem });
    var i, k;
    for (k in dump.skipped) { if (hasOwn(dump.skipped, k)) { rep(report, "info", "item-not-written", dump.skipped[k] + " " + k + "(s) not written"); } }
    for (k in dump.notes) { if (hasOwn(dump.notes, k)) { rep(report, "info", k, dump.notes[k] + " time(s)"); } }
    var J = function (v) { return werk.jsonPretty(v); }, docEdges = [], layerIds = [], abIds = [], inputs = [];
    for (i = 0; i < dump.artboards.length; i++) {
      var ab = dump.artboards[i], aid = "artboard-" + ab.id, ap = "vector/artboards/" + aid + ".json";
      w.addNode(aid, "core.vector.artboard", [werk.file(ap, J(ab), "application/json")], { note: "Artboard " + ab.id + " as Illustrator had it (" + TOOL + ")." });
      abIds.push(aid); docEdges.push({ to: aid, kind: "enhances", role: "contains" });
    }
    var imgTable = [];
    for (i = 0; i < dump.images.length; i++) {
      var im = dump.images[i], iid = "image-" + (i + 1), ip = "vector/images/" + iid + ".png";
      w.addNode(iid, "core.vector.image", [werk.file(ip, im.png, "image/png")], {
        note: "The pixels of an Illustrator raster, rendered alone at 72 ppi by " + TOOL + ".", meta: { key: im.key } });
      imgTable.push({ key: im.key, node: iid });
      docEdges.push({ to: iid, kind: "enhances", role: "contains" });
    }
    var layerFiles = [];
    for (i = 0; i < dump.layers.length; i++) {
      var lo = dump.layers[i], lid = "layer-" + lo.id, lp = "vector/layers/" + lid + ".json";
      var ledges = [];
      for (k = 0; k < imgTable.length; k++) { ledges.push({ to: imgTable[k].node, kind: "enhances", role: "uses" }); }
      w.addNode(lid, "core.vector.layer", [werk.file(lp, J({ schema_version: 1, layer: lo }), "application/json")],
                { note: "Top-level layer " + (i + 1) + " of " + dump.layers.length + " as Illustrator had it (" + TOOL + ").", edges: ledges });
      layerIds.push(lid); layerFiles.push(lp); docEdges.push({ to: lid, kind: "enhances", role: "contains" });
    }
    var dj = { schema_version: 1, title: opts.name || doc.name.replace(/\.[^.]*$/, ""), color_mode: doc.documentColorSpace === DocumentColorSpace.CMYK ? "Cmyk" : "Rgb",
               units: "Points", artboards: abIds, layers: layerIds, images: imgTable, next_object_id: dump.next_id };
    w.addNode("document", "core.vector.document", [werk.file("vector/document.json", J(dj), "application/json")],
              { note: "The structure of an Illustrator document: " + abIds.length + " artboard(s), " + layerIds.length + " layer(s), exported by " + TOOL + ".", edges: docEdges });
    inputs = ["vector/document.json"];
    if (abIds.length) { inputs.push("vector/artboards/" + abIds[0] + ".json"); }
    for (i = 0; i < layerFiles.length; i++) { inputs.push(layerFiles[i]); }
    for (i = 0; i < imgTable.length; i++) { inputs.push("vector/images/" + imgTable[i].node + ".png"); }
    var derivedEdges = [{ to: "document", kind: "requires", role: "derived-from" }];
    if (abIds.length) { derivedEdges.push({ to: abIds[0], kind: "requires", role: "derived-from" }); }
    for (i = 0; i < layerIds.length; i++) { derivedEdges.push({ to: layerIds[i], kind: "requires", role: "derived-from" }); }
    var a0 = dump.artboards[0].rect;
    var pngPath = sd + "/preview-" + stamp + ".png"; exportPNG(doc, pngPath, 0);
    var pf = findExported(pngPath), png = readBin(pf); new File(pf).remove();
    var info = werk.pngInfo(png);
    var region = [String(a0.x0), String(a0.y0), String(a0.x1), String(a0.y1)];
    w.addNode("preview", "core.vector.preview", [werk.file("preview/artboard.png", png, "image/png")], {
      note: "The first artboard rendered by Illustrator " + app.version + " (PNG-24 export, 72 ppi).", epistemic: "measured",
      inputFiles: inputs, inputParams: { background: "transparent", height: info.height, pixels_per_point: "1", region: region, renderer: "adobe-illustrator", renderer_version: app.version, width: info.width },
      edges: derivedEdges });
    w.preview("preview/");
    w.setPrimary("document", "document"); w.setPrimary("image", "preview");
    if (opts.svg !== false) {
      var svgPath = sd + "/preview-" + stamp + ".svg"; exportSVG(doc, svgPath);
      var sf = findExported(svgPath);
      if (sf) {
        var svg = readBin(sf); new File(sf).remove();
        w.addNode("preview-svg", "core.vector.svg", [werk.file("preview/artboard.svg", svg, "image/svg+xml")], {
          note: "The document as SVG 1.1 written by Illustrator " + app.version + " (type as outlines, images embedded).", epistemic: "measured",
          inputFiles: inputs, inputParams: { region: region, renderer: "adobe-illustrator", renderer_version: app.version }, edges: derivedEdges });
      } else { rep(report, "warn", "svg-not-written", "Illustrator wrote no SVG file"); }
    }
    // the revision record (CRAFT-BASE section 3)
    var uses = {};
    for (i = 0; i < w.nodes.length; i++) { uses[w.nodes[i].node_id] = 1; }
    var keys = [], ordered = {};
    for (k in uses) { if (hasOwn(uses, k)) { keys.push(k); } }
    keys.sort();
    for (i = 0; i < keys.length; i++) { ordered[keys[i]] = 1; }
    var rec = { created: created, kind: "save", nodes: ordered, note: "Exported by " + TOOL + " " + VERSION + " from Illustrator " + app.version + ".", producer: producer, revision: 1, schema_version: 1 };
    w.addNode("revisions", "core.revisions", [werk.file("revisions/revision.json", J(rec), "application/json")], { note: "The revision record of this save." });
    for (k in tm.schemas) { if (hasOwn(tm.schemas, k)) { for (i = 0; i < w.nodes.length; i++) { if (w.nodes[i].type === k) { w.setSchema(k, tm.schemas[k]); break; } } } }
    var msha = w.write(out, null);
    return { manifest_sha256: msha, report: report, counts: dump.counts, skipped: dump.skipped };
  }
  function exportImage(doc, out, opts) {
    opts = opts || {};
    var sd = scratchDir(opts), p = sd + "/image-" + new Date().getTime() + ".png";
    exportPNG(doc, p, opts.artboard || 0);
    var fp = findExported(p), png = readBin(fp); new File(fp).remove();
    var producer = { tool: TOOL, version: VERSION };
    var w = werk.writeImagePackage(out, png, { name: opts.name || doc.name.replace(/\.[^.]*$/, "") || "Untitled", created: opts.created, uuid: opts.uuid, generator: producer, producer: producer });
    return { manifest_sha256: werk.sha256Hex(w.build("zip").manifestBytes), png_sha256: werk.sha256Hex(png) };
  }

  return { openWerk: openWerk, exportVectorArt: exportVectorArt, exportImage: exportImage, dumpDocument: dumpDocument,
           fastJson: fastJson, readUnitPayload: readUnitPayload, version: VERSION };
})();
