// motion-comp/1 -> After Effects 2020: a PARTIAL import (ExtendScript, ES3).
// Needs werk.jsx and werk_ae_lib.jsx first.
//
//   werkAEMotion.importProject(path, opts) -> {comps: {id: CompItem}, report[], verdict, counts}
//
// What is built (PROFILE-MOTION-COMP.md sections 3.2-3.5, 6.1-6.3):
//   folders; solid and footage items (a footage item's medium is extracted to the
//   media folder, content-addressed, as werkAE.importImage does); every composition
//   (size, pixel aspect, frame rate, duration, background colour); every layer of
//   source type Solid, Footage, Comp, Null, Camera, Light, Text (its static source
//   text) - Shape layers are created EMPTY (their contents are not built) and Model /
//   Primitive layers as nulls; name, timing (start, in, out, stretch), blend mode,
//   the video / 3D / shy / locked switches, parenting; the transform group (anchor,
//   position, scale, orientation, rotation X/Y/Z, opacity): static values and
//   keyframes (inline `keys` or the WKX3 tracks node) with their Linear / Bezier /
//   Hold interpolation.
// What is NOT built, and reported: shape contents, masks, effects, layer styles,
// text animators and styling, expressions, temporal / spatial eases and tangents
// (Bezier keys keep AE's default ease), markers, track mattes, time remapping,
// audio levels, camera / light options, render queue.
var werkAEMotion = (function () {
  var TPS = 254016000000;
  function num(v) { return (v instanceof werk.WFloat) ? v.value : v; }
  function rep(list, sev, code, msg) { list.push({ severity: sev, code: code, message: msg }); }
  function fastJson(bytes) {
    // U+2028 / U+2029 are legal inside JSON strings but end a line in an ES3 string literal
    var text = werk.utf8Decode(bytes).replace(/\u2028/g, "\\u2028").replace(/\u2029/g, "\\u2029");
    var t = text.replace(/\\(?:["\\\/bfnrt]|u[0-9a-fA-F]{4})/g, "@")
      .replace(/"[^"\\\n\r]*"|true|false|null|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?/g, "]")
      .replace(/(?:^|:|,)(?:\s*\[)+/g, "");
    if (!/^[\],:{}\s]*$/.test(t)) { return werk.jsonParse(text); }
    return eval("(" + text + ")");
  }
  function f64(s, o) {
    var lo = (s.charCodeAt(o) | (s.charCodeAt(o + 1) << 8) | (s.charCodeAt(o + 2) << 16)) + s.charCodeAt(o + 3) * 16777216;
    var b4 = s.charCodeAt(o + 4), b5 = s.charCodeAt(o + 5), b6 = s.charCodeAt(o + 6), b7 = s.charCodeAt(o + 7);
    var sign = b7 >> 7, ex = ((b7 & 127) << 4) | (b6 >> 4), hi = ((b6 & 15) * 65536) + (b5 << 8) + b4;
    var man = hi * 4294967296 + lo;
    if (ex === 0) { return (sign ? -1 : 1) * man * Math.pow(2, -1074); }
    if (ex === 2047) { return NaN; }
    return (sign ? -1 : 1) * (1 + man / 4503599627370496) * Math.pow(2, ex - 1023);
  }
  function i64(s, o) {
    var lo = (s.charCodeAt(o) | (s.charCodeAt(o + 1) << 8) | (s.charCodeAt(o + 2) << 16)) + s.charCodeAt(o + 3) * 16777216;
    var hi = (s.charCodeAt(o + 4) | (s.charCodeAt(o + 5) << 8) | (s.charCodeAt(o + 6) << 16)) + s.charCodeAt(o + 7) * 16777216;
    if (hi >= 2147483648) { return (hi - 4294967296) * 4294967296 + lo; }
    return hi * 4294967296 + lo;
  }
  // WKX3 -> tracks[i] = [{time (ticks), value [..], inI, outI}]
  function readTracks(bytes) {
    var env = werk.readEnvelope(bytes), h = env.header, sec = {}, i, j;
    for (i = 0; i < h.sections.length; i++) { sec[h.sections[i].name] = h.sections[i].offset; }
    var out = [], interps = h.interpolations;
    for (i = 0; i < h.tracks.length; i++) {
      var t = h.tracks[i], c = t.components, keys = [];
      for (j = 0; j < t.keys; j++) {
        var k = t.first_key + j, v = [], q;
        for (q = 0; q < c; q++) { v.push(f64(bytes, sec.value + 8 * (t.first_value + j * c + q))); }
        keys.push({ time: i64(bytes, sec.at + 8 * k), value: v,
                    inI: interps[bytes.charCodeAt(sec.interp + 2 * k)], outI: interps[bytes.charCodeAt(sec.interp + 2 * k + 1)] });
      }
      out.push({ uid: t.uid, kind: t.kind, keys: keys });
    }
    return out;
  }
  function child(group, match) {
    var ch = (group && group.children) || [], i;
    for (i = 0; i < ch.length; i++) { if (ch[i].match === match) { return ch[i]; } }
    return null;
  }
  function val(p) {
    var v = p.value ? p.value.v : null, i, o;
    if (v instanceof Array) { o = []; for (i = 0; i < v.length; i++) { o.push(num(v[i])); } return o; }
    return num(v);
  }
  var BLEND = null;
  function blend(name) {
    if (!BLEND) {
      BLEND = { Normal: BlendingMode.NORMAL, Dissolve: BlendingMode.DISSOLVE, Darken: BlendingMode.DARKEN, Multiply: BlendingMode.MULTIPLY,
        ColorBurn: BlendingMode.COLOR_BURN, LinearBurn: BlendingMode.LINEAR_BURN, DarkerColor: BlendingMode.DARKER_COLOR, Add: BlendingMode.ADD,
        Lighten: BlendingMode.LIGHTEN, Screen: BlendingMode.SCREEN, ColorDodge: BlendingMode.COLOR_DODGE, LinearDodge: BlendingMode.LINEAR_DODGE,
        LighterColor: BlendingMode.LIGHTER_COLOR, Overlay: BlendingMode.OVERLAY, SoftLight: BlendingMode.SOFT_LIGHT, HardLight: BlendingMode.HARD_LIGHT,
        LinearLight: BlendingMode.LINEAR_LIGHT, VividLight: BlendingMode.VIVID_LIGHT, PinLight: BlendingMode.PIN_LIGHT, HardMix: BlendingMode.HARD_MIX,
        Difference: BlendingMode.DIFFERENCE, Exclusion: BlendingMode.EXCLUSION, Subtract: BlendingMode.SUBTRACT, Divide: BlendingMode.DIVIDE,
        Hue: BlendingMode.HUE, Saturation: BlendingMode.SATURATION, Color: BlendingMode.COLOR, Luminosity: BlendingMode.LUMINOSITY };
    }
    return BLEND[name] || null;
  }
  var XF = [["anchor", "ADBE Anchor Point"], ["position", "ADBE Position"], ["scale", "ADBE Scale"], ["orientation", "ADBE Orientation"],
            ["rotationX", "ADBE Rotate X"], ["rotationY", "ADBE Rotate Y"], ["rotation", "ADBE Rotate Z"], ["opacity", "ADBE Opacity"],
            ["poi", "ADBE Point of Interest"]];
  function fit(v, prop) {
    // AE wants 2 numbers for a 2D layer's anchor/position/scale, 3 for 3D; a scalar for rotation/opacity
    var vt = prop.propertyValueType;
    if (!(v instanceof Array)) { return v; }
    if (vt === PropertyValueType.TwoD || vt === PropertyValueType.TwoD_SPATIAL) { return [v[0], v[1]]; }
    if (vt === PropertyValueType.ThreeD || vt === PropertyValueType.ThreeD_SPATIAL) { return [v[0], v[1], v.length > 2 ? v[2] : 0]; }
    if (vt === PropertyValueType.OneD) { return v[0]; }
    return v;
  }
  var KI = null;
  function kit(name) {
    if (!KI) { KI = { Linear: KeyframeInterpolationType.LINEAR, Bezier: KeyframeInterpolationType.BEZIER, Hold: KeyframeInterpolationType.HOLD }; }
    return KI[name] || KeyframeInterpolationType.LINEAR;
  }
  function applyTransform(layer, lj, tracks, report, counts) {
    var tg = child(lj.layer.props, "transform"), i, j, sep = child(tg, "positionX") !== null;
    if (!tg) { return; }
    var group = layer.property("ADBE Transform Group");
    if (sep) {
      try { group.property("ADBE Position").dimensionsSeparated = true; } catch (e0) { rep(report, "info", "separate-dimensions-not-set", lj.layer.name); }
    }
    var list = XF.slice(0);
    if (sep) { list.push(["positionX", "ADBE Position_0"], ["positionY", "ADBE Position_1"], ["positionZ", "ADBE Position_2"]); }
    for (i = 0; i < list.length; i++) {
      var p = child(tg, list[i][0]);
      if (!p || (sep && list[i][0] === "position")) { continue; }
      var only3D = list[i][0] === "orientation" || list[i][0] === "rotationX" || list[i][0] === "rotationY";
      if (only3D && !layer.threeDLayer && (p.track === undefined || p.track === null) && !(p.keys && p.keys.length)) { continue; }   // hidden on a 2D layer
      var ap = group.property(list[i][1]);
      if (!ap) { continue; }
      var keys = null;
      if (p.track !== undefined && p.track !== null) {
        var tr = tracks ? tracks[p.track] : null;
        if (!tr || tr.uid !== p.uid) { rep(report, "warn", "track-binding-lost", lj.layer.name + "." + p.match + ": keeps its static value"); }
        else { keys = tr.keys; }
      } else if (p.keys && p.keys.length) {
        keys = [];
        for (j = 0; j < p.keys.length; j++) {
          var kk = p.keys[j];
          keys.push({ time: num(kk.time), value: kk.value && kk.value.v !== undefined ? (kk.value.v instanceof Array ? kk.value.v : [kk.value.v]) : [], inI: kk.in_interp || "Linear", outI: kk.out_interp || "Linear" });
          for (var q = 0; q < keys[j].value.length; q++) { keys[j].value[q] = num(keys[j].value[q]); }
        }
      }
      try {
        if (keys && keys.length) {
          var st = layer.startTime;
          for (j = 0; j < keys.length; j++) {
            var v = keys[j].value.length === 1 ? keys[j].value[0] : keys[j].value;
            ap.setValueAtTime(st + keys[j].time / TPS, fit(v, ap));
          }
          for (j = 0; j < keys.length; j++) { ap.setInterpolationTypeAtKey(j + 1, kit(keys[j].inI), kit(keys[j].outI)); }
          counts.keys += keys.length;
          if (keys.length > 1) { counts.animated++; }
        } else if (ap.canSetExpression !== undefined) {
          ap.setValue(fit(val(p), ap));
        }
      } catch (e1) { rep(report, "warn", "transform-not-set", lj.layer.name + "." + p.match + ": " + e1.message); }
      if (p.expr && p.expr.text) { rep(report, "info", "expression-not-applied", lj.layer.name + "." + p.match); }
    }
  }
  function importProject(path, opts) {
    opts = opts || {};
    var report = [], pkg = werk.open(path), v = pkg.verdict(), i, j;
    for (i = 0; i < pkg.report.length; i++) { var e = pkg.report[i]; report.push({ severity: e.severity, code: e.code, message: (e.node ? e.node + ": " : "") + e.message }); }
    if (pkg.manifest.profile !== "motion-comp/1") { throw new Error("profile " + pkg.manifest.profile + " is not motion-comp/1"); }
    var proj = fastJson(pkg.readPayload(pkg.manifest.primary.document)), P = app.project, counts = { comps: 0, layers: 0, solids: 0, footage: 0, folders: 0, keys: 0, animated: 0, shape_empty: 0, placeholders: 0 };
    var folders = {}, items = {}, solids = {}, comps = {}, compJson = {};
    var root = P.items.addFolder(opts.folderName || ((pkg.manifest.entity || {}).name || "werk") + " (werk)");
    for (i = 0; i < (proj.folders || []).length; i++) { var fd = proj.folders[i]; folders[fd.id] = P.items.addFolder(fd.name); counts.folders++; }
    for (i = 0; i < (proj.folders || []).length; i++) { var f2 = proj.folders[i]; folders[f2.id].parentFolder = f2.parent !== null && folders[f2.parent] ? folders[f2.parent] : root; }
    function parentOf(id) { return id !== null && id !== undefined && folders[id] ? folders[id] : root; }
    var mediaDir = opts.mediaDir;
    for (i = 0; i < proj.items.length; i++) {
      var it = proj.items[i];
      try {
        if (it.kind === "comp") {
          var cj = fastJson(pkg.readPayload(it.node)), c = cj.comp, fr = num(c.frame_rate.num) / num(c.frame_rate.den);
          var comp = P.items.addComp(cj.name, num(c.width), num(c.height), num(c.pixel_aspect) || 1, Math.max(1 / fr, num(c.duration) / TPS), fr);
          comp.parentFolder = parentOf(cj.parent);
          if (c.background) { var bg = c.background; comp.bgColor = [num(bg[0]), num(bg[1]), num(bg[2])]; }
          if (c.display_start) { comp.displayStartTime = num(c.display_start) / TPS; }
          comps[it.id] = comp; compJson[it.id] = cj; counts.comps++;
        } else {
          var ij = fastJson(pkg.readPayload(it.node));
          if (ij.kind.Solid) { solids[it.id] = ij; }
          else if (ij.kind.Footage) {
            var F = ij.kind.Footage, mn = F.media && F.media.node;
            if (!mn) { rep(report, "warn", "footage-without-media", ij.name); continue; }
            var tmp = werkAE.extractMedia(pkg, mn, mediaDir);
            var io = new ImportOptions(new File(tmp));
            var fi = P.importFile(io); fi.name = ij.name; fi.parentFolder = parentOf(ij.parent);
            if (F.alpha === "Ignore") { try { fi.mainSource.alphaMode = AlphaMode.IGNORE; } catch (e3) { } }
            items[it.id] = fi; counts.footage++;
          }
        }
      } catch (e2) { rep(report, "error", "item-not-built", it.node + ": " + e2.message); }
    }
    // layers, back to front (After Effects adds each new layer on top)
    for (var cid in comps) {
      if (!Object.prototype.hasOwnProperty.call(comps, cid)) { continue; }
      var C = comps[cid], CJ = compJson[cid], built = {}, ljs = {}, pending = [];
      for (j = CJ.layers.length - 1; j >= 0; j--) {
        var lref = CJ.layers[j], lj, L = null;
        try { lj = fastJson(pkg.readPayload(lref.node)); } catch (e4) { rep(report, "error", "layer-dead", lref.node + ": " + e4.message); continue; }
        var Ld = lj.layer, src = Ld.source || {}, tracks = null;
        if (lj.tracks) { try { tracks = readTracks(pkg.readPayload(lj.tracks)); } catch (e5) { rep(report, "error", "tracks-dead", lj.tracks + ": " + e5.message); } }
        try {
          if (src.type === "Solid") {
            var sj = solids[src.item], S = sj.kind.Solid;
            if (items[src.item]) { L = C.layers.add(items[src.item]); }
            else { L = C.layers.addSolid([num(S.color[0]), num(S.color[1]), num(S.color[2])], sj.name, num(S.width), num(S.height), num(S.pixel_aspect) || 1); items[src.item] = L.source; counts.solids++; }
          } else if (src.type === "Footage" || src.type === "Comp") {
            var srcItem = src.type === "Comp" ? comps[src.item] : items[src.item];
            if (!srcItem) { throw new Error("source item " + src.item + " was not built"); }
            L = C.layers.add(srcItem);
          } else if (src.type === "Null") { L = C.layers.addNull(); }
          else if (src.type === "Camera") { L = C.layers.addCamera(Ld.name, [C.width / 2, C.height / 2]); }
          else if (src.type === "Light") {
            L = C.layers.addLight(Ld.name, [C.width / 2, C.height / 2]);
            var LT = { Parallel: LightType.PARALLEL, Spot: LightType.SPOT, Point: LightType.POINT, Ambient: LightType.AMBIENT };
            if (LT[src.kind]) { L.lightType = LT[src.kind]; }
          } else if (src.type === "Text") {
            var tg = child(Ld.props, "text"), stp = child(tg, "sourceText"), txt = "";
            if (stp && stp.value && stp.value.v) { txt = stp.value.v.text || ""; }
            L = C.layers.addText(txt);
            try {
              var sv = stp.value.v, tdp = L.property("ADBE Text Properties").property("ADBE Text Document"), td = tdp.value;
              if (sv.size !== undefined) { td.fontSize = num(sv.size); }
              if (sv.fill) { td.applyFill = true; td.fillColor = [num(sv.fill[0]), num(sv.fill[1]), num(sv.fill[2])]; }
              if (sv.tracking !== undefined) { td.tracking = num(sv.tracking); }
              tdp.setValue(td);
            } catch (eT) { rep(report, "info", "text-style-not-set", Ld.name + ": " + eT.message); }
            rep(report, "info", "text-font-and-animators-not-applied", Ld.name + ": text, size, fill colour and tracking are set; font face, animators and paragraph settings are not");
          } else if (src.type === "Shape") {
            L = C.layers.addShape(); counts.shape_empty++;
            rep(report, "info", "shape-contents-not-built", Ld.name + ": an empty shape layer");
          } else {
            L = C.layers.addNull(); counts.placeholders++;
            rep(report, "info", "layer-kind-as-null", Ld.name + ": source " + src.type + " opens as a null");
          }
          L.name = Ld.name;
          var sw = Ld.switches || {};
          if (sw.three_d && L.threeDLayer !== undefined && src.type !== "Camera" && src.type !== "Light") { try { L.threeDLayer = true; } catch (e6) { } }
          L.startTime = num(Ld.start_time || 0) / TPS;
          if (Ld.stretch !== undefined && num(Ld.stretch) !== 100) { L.stretch = num(Ld.stretch); }
          L.inPoint = num(Ld.in_point) / TPS; L.outPoint = num(Ld.out_point) / TPS;
          var bm = blend(Ld.blend_mode || "Normal");
          if (bm) { try { L.blendingMode = bm; } catch (e7) { } } else { rep(report, "info", "blend-not-mapped", Ld.name + ": " + Ld.blend_mode); }
          pending.push({ L: L, lj: lj, tracks: tracks, audioOnly: src.type === "Footage" && L.hasAudio === true && L.hasVideo === false });
          if (sw.video === false) { L.enabled = false; }
          if (sw.shy) { L.shy = true; }
          var others = ["masks", "effects", "layerStyles"];
          for (var oi = 0; oi < others.length; oi++) { var g = child(Ld.props, others[oi]); if (g && g.children && g.children.length) { rep(report, "info", others[oi] + "-not-built", Ld.name + ": " + g.children.length); } }
          if (Ld.track_matte) { rep(report, "info", "track-matte-not-set", Ld.name); }
          built[Ld.id] = L; ljs[Ld.id] = Ld; counts.layers++;
          var srcDur = null;
          if (src.type === "Comp" && compJson[src.item]) { srcDur = num(compJson[src.item].comp.duration) / TPS; }
          else if (src.type === "Footage" && items[src.item] && items[src.item].mainSource && !items[src.item].mainSource.isStill) { srcDur = items[src.item].duration; }
          if (srcDur !== null && num(Ld.out_point) / TPS > L.startTime + srcDur + 1e-9) {
            rep(report, "info", "out-point-clamped", Ld.name + ": out point " + (num(Ld.out_point) / TPS) + " s is past the end of its source (" + srcDur + " s); After Effects ends the layer there (time remapping, which would extend it, is not built)");
          }
        } catch (e8) { rep(report, "error", "layer-not-built", lref.node + " (" + Ld.name + "): " + e8.message); }
      }
      // parents BEFORE transforms: assigning .parent makes After Effects re-express the
      // child's transform so that it keeps its place in the world
      for (var lid in built) {
        if (!Object.prototype.hasOwnProperty.call(built, lid)) { continue; }
        var par = ljs[lid].parent;
        if (par !== null && par !== undefined && built[par]) { try { built[lid].parent = built[par]; } catch (e9) { rep(report, "warn", "parent-not-set", ljs[lid].name); } }
      }
      for (j = 0; j < pending.length; j++) {
        if (pending[j].audioOnly) { rep(report, "info", "audio-layer-transform-hidden", pending[j].lj.layer.name + ": an audio-only layer has no visible transform in After Effects"); continue; }
        applyTransform(pending[j].L, pending[j].lj, pending[j].tracks, report, counts);
      }
      for (lid in built) {
        if (!Object.prototype.hasOwnProperty.call(built, lid)) { continue; }
        if ((ljs[lid].switches || {}).locked) { built[lid].locked = true; }
      }
    }
    return { comps: comps, report: report, verdict: v, counts: counts, root: root };
  }
  return { importProject: importProject, readTracks: readTracks, TPS: TPS };
})();
