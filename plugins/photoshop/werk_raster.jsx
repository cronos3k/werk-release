// raster-layers/1 for ExtendScript hosts (ES3): decode a layer surface to
// interleaved bytes, and encode u8 RGBA pixels as a surface. A port of the GIMP
// plug-in's werk_raster.py (which is gated against the profile's own test
// vector); the normative text is the capsule's spec/PROFILE-RASTER-LAYERS.md
// and spec/layouts/core.raster.surface.layout.txt. Needs werk.jsx.
var werkRaster = (function () {
  var TILE = 256;
  var ESZ = { u8: 1, u16: 2, f32: 4 };
  var COLOUR = { rgb: "rgb", indexed: "rgb", multichannel: "rgb", grayscale: "gray", bitmap: "gray", duotone: "gray" };

  function resolvedVersion(pkg, id) {
    var n = pkg.node(id), i;
    if (!n) { throw new Error("no node " + id); }
    if (n.status === "dead") { throw new Error("node " + id + " is dead"); }
    for (i = 0; i < n.versions.length; i++) { if (n.versions[i].v === n.resolved) { return n.versions[i]; } }
    throw new Error("node " + id + " has no resolved version");
  }
  function sections(data, header) {
    var out = {}, s = header.sections || [], i;
    for (i = 0; i < s.length; i++) { out[s[i].name] = data.substring(s[i].offset, s[i].offset + s[i].size); }
    return out;
  }
  function inflateZlib(bytes) {
    var cmf = bytes.charCodeAt(0), flg = bytes.charCodeAt(1);
    if ((cmf & 15) !== 8 || ((cmf << 8) | flg) % 31 !== 0 || (flg & 32)) { throw new Error("not a zlib stream"); }
    return werk.inflateRaw(bytes.substring(2), 1 << 30);
  }
  function codesToString(a) {
    var parts = [], i;
    for (i = 0; i < a.length; i += 8192) { parts.push(String.fromCharCode.apply(null, a.slice(i, i + 8192))); }
    return parts.join("");
  }
  // planes-delta DECODE (layout section 5.2) of one tile of C channels, esz bytes per sample
  // ExtendScript arrays slow down badly as they grow, so every loop below works
  // in chunks of at most CHUNK elements and joins strings.
  var CHUNK = 4096;
  function undelta(e, C, esz) {
    var N = TILE * TILE * C, acc = [], parts = [], k, s, s0, s1, tmp, j, c;
    for (k = 0; k < esz * C; k++) { acc.push(0); }
    for (s0 = 0; s0 < N; s0 += CHUNK) {          // CHUNK is a multiple of C for C in 1..4
      s1 = Math.min(N, s0 + CHUNK); tmp = [];
      for (s = s0; s < s1; s++) {
        c = s % C;
        for (k = 0; k < esz; k++) {
          j = k * C + c;
          acc[j] = (acc[j] + e.charCodeAt(k * N + s)) & 255;
          tmp.push(acc[j]);
        }
      }
      parts.push(String.fromCharCode.apply(null, tmp));
    }
    return parts.join("");
  }
  // f32 little-endian samples -> u16 little-endian, clamped to 0..1 (Photoshop has no float layers here)
  function f32ToU16(s) {
    var n = s.length / 4, parts = [], tmp = [], i, b0, b1, b2, b3, sign, ex, man, v, q;
    for (i = 0; i < n; i++) {
      b0 = s.charCodeAt(4 * i); b1 = s.charCodeAt(4 * i + 1); b2 = s.charCodeAt(4 * i + 2); b3 = s.charCodeAt(4 * i + 3);
      sign = b3 >> 7; ex = ((b3 & 127) << 1) | (b2 >> 7); man = ((b2 & 127) << 16) | (b1 << 8) | b0;
      if (ex === 255) { v = man ? 0 : (sign ? 0 : 1); }
      else if (ex === 0) { v = 0; }
      else { v = (1 + man / 8388608) * Math.pow(2, ex - 127); if (sign) { v = -v; } }
      if (v < 0) { v = 0; } if (v > 1) { v = 1; }
      q = Math.round(v * 65535);
      tmp.push(q & 255, q >> 8);
      if (tmp.length >= CHUNK) { parts.push(String.fromCharCode.apply(null, tmp)); tmp = []; }
    }
    if (tmp.length) { parts.push(String.fromCharCode.apply(null, tmp)); }
    return parts.join("");
  }
  function repeatStr(s, n) {
    var out = "", p = s;
    while (n > 0) { if (n & 1) { out += p; } n >>= 1; if (n) { p += p; } }
    return out;
  }

  // -> {mode, colour ('rgb'|'gray'|null), has_alpha, channels, sample_type, C, esz,
  //     rows: [W*C*esz byte strings, top to bottom]}
  function decodeSurface(pkg, id, W, H) {
    var ver = resolvedVersion(pkg, id), files = ver.files, byRole = {}, i;
    for (i = 0; i < files.length; i++) { if (files[i].role) { byRole[files[i].role] = files[i].path; } }
    var idx = pkg.readFile(ver.payload_file || files[0].path), env = werk.readEnvelope(idx), h = env.header;
    if (h.part !== "index") { throw new Error(id + ": not an index envelope"); }
    if (h.tile_size !== TILE) { throw new Error(id + ": tile_size " + h.tile_size); }
    var st = h.sample_type, C = h.channels.length, esz = ESZ[st];
    if (!esz) { throw new Error(id + ": sample_type " + st); }
    var secs = sections(idx, h), def = secs["default-pixel"], tix = secs["tile-index"] || "";
    var px = C * esz, rowLen = W * px, defRow = repeatStr(def, W), rows = [], cache = {}, T = TILE * TILE * px;
    for (i = 0; i < H; i++) { rows.push(defRow); }
    function i32(s, o) { var v = s.charCodeAt(o) | (s.charCodeAt(o + 1) << 8) | (s.charCodeAt(o + 2) << 16) | (s.charCodeAt(o + 3) << 24); return v; }
    for (i = 0; i < (h.tile_count || 0); i++) {
      var tx = i32(tix, i * 16), ty = i32(tix, i * 16 + 4), fi = i32(tix, i * 16 + 8), slot = i32(tix, i * 16 + 12);
      var x0 = tx * TILE, y0 = ty * TILE;
      if (x0 >= W || y0 >= H || x0 + TILE <= 0 || y0 + TILE <= 0) { continue; }
      var role = h.tile_files[fi];
      if (!cache[role]) {
        var raw = pkg.readFile(byRole[role]);
        if (raw.substring(0, 4) !== "WKX0") { raw = inflateZlib(raw); }
        var th = werk.readEnvelope(raw).header, ks = ["pixel_mode", "has_alpha", "sample_type"], k;
        for (k = 0; k < ks.length; k++) { if (th[ks[k]] !== h[ks[k]]) { throw new Error("tile file " + role + ": " + ks[k] + " differs from the index"); } }
        var enc = th.sample_encoding || "raw";
        if (enc !== "raw" && enc !== "planes-delta") { throw new Error("sample_encoding " + enc); }
        cache[role] = { samples: sections(raw, th).samples, enc: enc };
      }
      var tile = cache[role].samples.substring(slot * T, (slot + 1) * T);
      if (tile.length !== T) { throw new Error("slot " + slot + " not in tile file " + role); }
      if (cache[role].enc === "planes-delta") { tile = undelta(tile, C, esz); }
      var qa = Math.max(0, -x0), qb = Math.min(TILE, W - x0), r;
      for (r = Math.max(0, -y0); r < Math.min(TILE, H - y0); r++) {
        var seg = tile.substring((r * TILE + qa) * px, (r * TILE + qb) * px), row = rows[y0 + r], a = (x0 + qa) * px;
        rows[y0 + r] = row.substring(0, a) + seg + row.substring(a + seg.length);
      }
    }
    if (st === "f32") { for (i = 0; i < H; i++) { rows[i] = f32ToU16(rows[i]); } }
    return { mode: h.pixel_mode, colour: COLOUR[h.pixel_mode] || null, has_alpha: !!h.has_alpha, channels: h.channels,
             sample_type: st, out_type: st === "u8" ? "u8" : "u16", C: C, esz: st === "f32" ? 2 : esz, rows: rows };
  }

  // Split decoded rows into an RGB byte string (grey replicated) and an alpha string,
  // both interleaved, little-endian for 16-bit. -> {rgb, alpha|null, bits}
  function toRGBandA(s) {
    var esz = s.esz, C = s.C, gray = s.colour === "gray", nc = gray ? 1 : 3, px = C * esz, rgb = [], al = [], y, x, row, W, rp, ap, g, b;
    for (y = 0; y < s.rows.length; y++) {
      row = s.rows[y]; W = row.length / px;
      if (!gray && !s.has_alpha && C === 3) { rgb.push(row); continue; }
      rp = []; ap = [];
      for (x = 0; x < W; x++) {
        b = x * px;
        if (gray) { g = row.substr(b, esz); rp.push(g + g + g); }
        else { rp.push(row.substr(b, 3 * esz)); }
        if (s.has_alpha) { ap.push(row.substr(b + nc * esz, esz)); }
      }
      rgb.push(rp.join(""));
      if (s.has_alpha) { al.push(ap.join("")); }
    }
    return { rgb: rgb.join(""), alpha: s.has_alpha ? al.join("") : null, bits: esz * 8 };
  }

  // ------------------------------------------------------------------ writing
  function u32le(v) { return String.fromCharCode(v & 255, (v >>> 8) & 255, (v >>> 16) & 255, (v >>> 24) & 255); }
  function i32le(v) { return u32le(v < 0 ? v + 4294967296 : v); }
  function be(v, n) { var s = "", i; for (i = n - 1; i >= 0; i--) { s += String.fromCharCode(Math.floor(v / Math.pow(256, i)) & 255); } return s; }
  function utf8(s) { return werk.utf8Encode(s); }
  // canonical MessagePack (ENVELOPE.layout.txt 4.3): ints, strings, bools, null, arrays, maps (keys sorted by UTF-8)
  function mp(v) {
    var i, n, out;
    if (v === null) { return "\xc0"; }
    if (v === true) { return "\xc3"; }
    if (v === false) { return "\xc2"; }
    if (typeof v === "number") {
      if (Math.floor(v) !== v) { throw new Error("mp: non-integer " + v); }
      if (v >= 0) {
        if (v <= 0x7F) { return String.fromCharCode(v); }
        if (v <= 0xFF) { return "\xcc" + be(v, 1); }
        if (v <= 0xFFFF) { return "\xcd" + be(v, 2); }
        if (v <= 0xFFFFFFFF) { return "\xce" + be(v, 4); }
        return "\xcf" + be(v, 8);
      }
      if (v >= -32) { return String.fromCharCode(256 + v); }
      if (v >= -128) { return "\xd0" + String.fromCharCode(256 + v); }
      if (v >= -32768) { return "\xd1" + be(65536 + v, 2); }
      return "\xd2" + be(4294967296 + v, 4);
    }
    if (typeof v === "string") {
      var raw = utf8(v); n = raw.length;
      if (n <= 31) { return String.fromCharCode(0xA0 | n) + raw; }
      if (n <= 0xFF) { return "\xd9" + be(n, 1) + raw; }
      if (n <= 0xFFFF) { return "\xda" + be(n, 2) + raw; }
      return "\xdb" + be(n, 4) + raw;
    }
    if (v instanceof Array) {
      n = v.length; out = n <= 15 ? String.fromCharCode(0x90 | n) : (n <= 0xFFFF ? "\xdc" + be(n, 2) : "\xdd" + be(n, 4));
      for (i = 0; i < n; i++) { out += mp(v[i]); }
      return out;
    }
    var keys = [], k;
    for (k in v) { if (Object.prototype.hasOwnProperty.call(v, k)) { keys.push(k); } }
    keys.sort(function (a, b) { var x = utf8(a), y = utf8(b); return x < y ? -1 : (x > y ? 1 : 0); });
    n = keys.length; out = n <= 15 ? String.fromCharCode(0x80 | n) : (n <= 0xFFFF ? "\xde" + be(n, 2) : "\xdf" + be(n, 4));
    for (i = 0; i < n; i++) { out += mp(keys[i]) + mp(v[keys[i]]); }
    return out;
  }
  function a16(n) { return Math.ceil(n / 16) * 16; }
  function zeros(n) { return repeatStr("\x00", n); }
  // sections: [{name, dtype, shape, stride, data}]
  function envelope(kind, keys, secs) {
    var hl = 0, enc, origin, i, k;
    while (true) {
      origin = a16(12 + hl);
      var table = [], cur = origin;
      for (i = 0; i < secs.length; i++) {
        table.push({ name: secs[i].name, offset: cur, size: secs[i].data.length, dtype: secs[i].dtype, shape: secs[i].shape, stride: secs[i].stride });
        cur = a16(cur + secs[i].data.length);
      }
      var hd = {};
      for (k in keys) { if (Object.prototype.hasOwnProperty.call(keys, k)) { hd[k] = keys[k]; } }
      hd.kind = kind; hd.endianness = "le"; hd.payload_origin = origin; hd.payload_size = cur - origin; hd.sections = table;
      enc = mp(hd);
      if (enc.length === hl) { break; }
      hl = enc.length;
    }
    var parts = ["WKX0", u32le(1), u32le(hl), enc], len = 12 + hl;
    parts.push(zeros(origin - len)); len = origin;
    for (i = 0; i < secs.length; i++) { parts.push(secs[i].data); len += secs[i].data.length; parts.push(zeros(a16(len) - len)); len = a16(len); }
    return parts.join("");
  }
  // rgba: W*H*4 u8, straight alpha, alpha-0 pixels all zero. -> {index, tiles|null, count}
  function surfaceFilesRGBA8(rgba, w, h) {
    var C = 4, fmt = function (extra) {
      var o = { pixel_mode: "rgb", has_alpha: true, channels: ["red", "green", "blue", "alpha"], sample_type: "u8", tile_size: TILE, nonfinite: false }, k;
      for (k in extra) { if (Object.prototype.hasOwnProperty.call(extra, k)) { o[k] = extra[k]; } }
      return o;
    };
    var tiles = [], rows = [], tx, ty, r, zeroRow = zeros(TILE * C), fullZero = zeros(TILE * TILE * C);
    for (ty = 0; ty < Math.ceil(h / TILE); ty++) {
      for (tx = 0; tx < Math.ceil(w / TILE); tx++) {
        var x0 = tx * TILE, y0 = ty * TILE, qw = Math.min(TILE, w - x0), parts = [], any = false;
        for (r = 0; r < TILE; r++) {
          if (y0 + r < h) {
            var src = ((y0 + r) * w + x0) * C, seg = rgba.substring(src, src + qw * C);
            if (!any && seg !== zeroRow.substring(0, qw * C)) { any = true; }
            parts.push(seg); if (qw < TILE) { parts.push(zeroRow.substring(0, (TILE - qw) * C)); }
          } else { parts.push(zeroRow); }
        }
        if (any) { rows.push(i32le(tx) + i32le(ty) + i32le(0) + i32le(tiles.length)); tiles.push(parts.join("")); }
      }
    }
    var tilesB = tiles.length ? envelope("core.raster.surface", fmt({ part: "tiles", tile_count: tiles.length }),
      [{ name: "samples", dtype: "u8", shape: [tiles.length, TILE, TILE, C], stride: C, data: tiles.join("") }]) : null;
    var indexB = envelope("core.raster.surface", fmt({ part: "index", tile_count: tiles.length, tile_files: tiles.length ? ["tiles-p0-p0"] : [] }), [
      { name: "default-pixel", dtype: "u8", shape: [C], stride: 1, data: zeros(C) },
      { name: "tile-index", dtype: "i32", shape: [tiles.length, 4], stride: 16, data: rows.join("") }]);
    return { index: indexB, tiles: tilesB, count: tiles.length };
  }

  return { undelta: undelta, decodeSurface: decodeSurface, toRGBandA: toRGBandA, surfaceFilesRGBA8: surfaceFilesRGBA8,
           envelope: envelope, mp: mp, resolvedVersion: resolvedVersion, inflateZlib: inflateZlib, TILE: TILE };
})();
