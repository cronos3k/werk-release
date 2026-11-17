// Byte adapter: binary strings (one char per byte, 0-255). ExtendScript has no
// typed arrays; File objects opened with encoding "BINARY" read and write
// exactly this. Same interface as adapter-u8.js.
var B = {
  kind: "binary-string",
  empty: function () { return ""; },
  isBytes: function (x) { return typeof x === "string"; },
  len: function (b) { return b.length; },
  at: function (b, i) { return b.charCodeAt(i); },
  slice: function (b, s, e) { return b.substring(s, e === undefined ? b.length : e); },
  fromArray: function (a) {
    var parts = [], i;
    for (i = 0; i < a.length; i += 4096) {
      parts.push(String.fromCharCode.apply(null, a.slice(i, i + 4096)));
    }
    return parts.join("");
  },
  concat: function (list) { return list.join(""); },
  eq: function (a, b) { return a === b; },
  builder: function () {
    var parts = [], cur = [], n = 0;
    function flush() {
      if (cur.length) { parts.push(String.fromCharCode.apply(null, cur)); cur = []; }
    }
    return {
      put8: function (x) { cur.push(x & 255); n++; if (cur.length >= 4096) { flush(); } },
      bytes: function (b) { flush(); parts.push(b); n += b.length; },
      length: function () { return n; },
      done: function () { flush(); return parts.join(""); }
    };
  },
  // the DEFLATE decoder's output (core.js inflateRaw), linear in this representation
  // ExtendScript copies substrings natively but interprets every array store,
  // V8 the reverse (string windows get flattened on every slice): the window
  // sink in ExtendScript, the ring elsewhere. Same bytes either way.
  inflateSinkKind: (typeof $ !== "undefined" && $ && typeof $.version === "string") ? "window" : "ring",
  inflateSink: function (limit) { return this.inflateSinkKind === "window" ? new StrInflateSink(limit) : new RingInflateSink(limit); }
};

// The DEFLATE output sink: see core.js inflateRaw.
function StrInflateSink(limit) {
  this.parts = []; this.total = 0; this.tail = ""; this.lit = []; this.limit = limit;
}
StrInflateSink.prototype.flush = function () {
  if (this.lit.length) { var s = String.fromCharCode.apply(null, this.lit); this.lit = []; this.put(s); }
};
StrInflateSink.prototype.put = function (s) {
  this.parts.push(s); this.total += s.length; this.tail += s;
  if (this.parts.length >= 512) { this.parts = [this.parts.join("")]; }
  if (this.total > this.limit) { throw new Error("deflate stream inflates past the declared size"); }
  if (this.tail.length > 131072) { this.tail = this.tail.substring(this.tail.length - 65536); }
};
StrInflateSink.prototype.lit8 = function (x) { this.lit.push(x); if (this.lit.length >= 4096) { this.flush(); } };
StrInflateSink.prototype.copy = function (dist, len) {
  this.flush();
  if (dist > this.tail.length) { throw new Error("deflate: distance too far back"); }
  var src = this.tail.substring(this.tail.length - dist), out;
  if (len <= dist) { out = src.substring(0, len); }
  else { out = src; while (out.length < len) { out += out; } out = out.substring(0, len); }
  this.put(out);
};
StrInflateSink.prototype.stored = function (data, s, e) { this.flush(); this.put(data.substring(s, e)); };
StrInflateSink.prototype.done = function () { this.flush(); return this.parts.join(""); };


// Alternative sink with no string window: a preallocated 64 KiB ring of byte
// values and a preallocated 4 KiB chunk, both written by index (never grown),
// the chunk turned into a string with one String.fromCharCode.apply. Chosen
// per host by measurement (js/tests/extendscript_bench.jsx): in Illustrator
// 2020 the window sink measured 0.41 MB/s, this one 0.016 MB/s, so "window" is
// the default; this one is kept selectable (B.inflateSinkKind = "ring").
function RingInflateSink(limit) {
  var i;
  this.ring = []; this.ch = []; this.k = 0; this.p = 0; this.limit = limit; this.parts = []; this.total = 0;
  for (i = 0; i < 65536; i++) { this.ring[i] = 0; }
  for (i = 0; i < 4096; i++) { this.ch[i] = 0; }
}
RingInflateSink.prototype.emit = function () {
  var s = String.fromCharCode.apply(null, this.k === 4096 ? this.ch : this.ch.slice(0, this.k));
  this.k = 0; this.parts.push(s); this.total += s.length;
  if (this.parts.length >= 512) { this.parts = [this.parts.join("")]; }
  if (this.total > this.limit) { throw new Error("deflate stream inflates past the declared size"); }
};
RingInflateSink.prototype.lit8 = function (x) {
  this.ring[this.p & 65535] = x; this.p++; this.ch[this.k++] = x;
  if (this.k === 4096) { this.emit(); }
};
RingInflateSink.prototype.copy = function (dist, len) {
  if (dist > this.p) { throw new Error("deflate: distance too far back"); }
  var r = this.ring, c = this.ch, p = this.p, k = this.k, i, x;
  for (i = 0; i < len; i++) {
    x = r[(p - dist) & 65535]; r[p & 65535] = x; p++; c[k++] = x;
    if (k === 4096) { this.k = k; this.emit(); k = 0; }
  }
  this.p = p; this.k = k;
};
RingInflateSink.prototype.stored = function (data, s, e) {
  for (var i = s; i < e; i++) { this.lit8(data.charCodeAt(i)); }
};
RingInflateSink.prototype.done = function () { if (this.k) { this.emit(); } return this.parts.join(""); };
