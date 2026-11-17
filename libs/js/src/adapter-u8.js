// Byte adapter: Uint8Array (Node 18+, Adobe UXP, browsers). Same interface as
// adapter-str.js; the core never touches bytes except through B.
var B = {
  kind: "uint8array",
  empty: function () { return new Uint8Array(0); },
  isBytes: function (x) { return x instanceof Uint8Array; },
  len: function (b) { return b.length; },
  at: function (b, i) { return b[i]; },
  slice: function (b, s, e) { return b.subarray(s, e === undefined ? b.length : e); },
  fromArray: function (a) { return new Uint8Array(a); },
  concat: function (list) {
    var n = 0, i, o = 0;
    for (i = 0; i < list.length; i++) { n += list[i].length; }
    var out = new Uint8Array(n);
    for (i = 0; i < list.length; i++) { out.set(list[i], o); o += list[i].length; }
    return out;
  },
  eq: function (a, b) {
    if (a.length !== b.length) { return false; }
    for (var i = 0; i < a.length; i++) { if (a[i] !== b[i]) { return false; } }
    return true;
  },
  builder: function () {
    var buf = new Uint8Array(256), n = 0;
    function grow(k) {
      if (n + k <= buf.length) { return; }
      var c = buf.length * 2;
      while (c < n + k) { c *= 2; }
      var nb = new Uint8Array(c);
      nb.set(buf.subarray(0, n));
      buf = nb;
    }
    return {
      put8: function (x) { grow(1); buf[n++] = x & 255; },
      bytes: function (b) { grow(b.length); buf.set(b, n); n += b.length; },
      length: function () { return n; },
      done: function () { return buf.slice(0, n); }
    };
  },
  // the DEFLATE decoder's output (core.js inflateRaw), linear in this representation
  inflateSink: function (limit) { return new U8InflateSink(limit); }
};

// The DEFLATE output sink: see core.js inflateRaw.
function U8InflateSink(limit) {
  this.buf = new Uint8Array(limit > 0 && limit < 268435456 ? limit : 65536); this.n = 0; this.limit = limit;
}
U8InflateSink.prototype.room = function (k) {
  if (this.n + k > this.limit) { throw new Error("deflate stream inflates past the declared size"); }
  if (this.n + k <= this.buf.length) { return; }
  var c = this.buf.length * 2;
  while (c < this.n + k) { c *= 2; }
  var nb = new Uint8Array(c);
  nb.set(this.buf.subarray(0, this.n));
  this.buf = nb;
};
U8InflateSink.prototype.lit8 = function (x) { if (this.n >= this.buf.length || this.n >= this.limit) { this.room(1); } this.buf[this.n++] = x; };
U8InflateSink.prototype.copy = function (dist, len) {
  if (dist > this.n) { throw new Error("deflate: distance too far back"); }
  this.room(len);
  var b = this.buf, p = this.n, q = p - dist, i;
  for (i = 0; i < len; i++) { b[p + i] = b[q + i]; }
  this.n = p + len;
};
U8InflateSink.prototype.stored = function (data, s, e) { this.room(e - s); this.buf.set(data.subarray(s, e), this.n); this.n += e - s; };
U8InflateSink.prototype.done = function () { return this.buf.slice(0, this.n); };

