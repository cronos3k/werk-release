// werk core -- ES3 syntax on purpose (it is also the ExtendScript build).
// Bytes go through B (adapter-u8.js or adapter-str.js); files through an IO
// object (io-node.js, io-jsx.js) or not at all (openBytes / toBytes).
// Normative ground truth: the spec/ tree in the bundle. Behaviour mirrors
// libs/python/werk/_core.py exactly; the cross-matrix holds them equal.

var LIB_VERSION = "0.1.0";
var MANIFEST = "MANIFEST.json", SIGNATURE = "SIGNATURE.json";
var SIG_VALID = "signed-and-valid", SIG_ABSENT = "absent",
    SIG_INVALID = "present-and-invalid", SIG_UNVERIFIED = "unverified";

// ---------------------------------------------------------------- errors
function WerkError(message, code) {
  this.name = "WerkError";
  this.message = message;
  this.code = code || null;
  var e = new Error(message);
  if (e.stack) { this.stack = "WerkError: " + message + "\n" + String(e.stack).split("\n").slice(1).join("\n"); }
}
WerkError.prototype = new Error();
WerkError.prototype.constructor = WerkError;
WerkError.prototype.toString = function () { return "WerkError: " + this.message; };

function refusal(code, message) {
  var e = new WerkError(code + ": " + message, code);
  e.refusal = true;
  e.detail = message;
  return e;
}

// ---------------------------------------------------------------- utilities
function hasOwn(o, k) { return Object.prototype.hasOwnProperty.call(o, k); }
function isArray(x) { return Object.prototype.toString.call(x) === "[object Array]"; }
function isObj(x) { return x !== null && typeof x === "object" && !isArray(x) && !(x instanceof WFloat) && !(x instanceof WInt) && !B.isBytes(x); }
function keysOf(o) { var out = [], k; for (k in o) { if (hasOwn(o, k)) { out.push(k); } } return out; }
function indexOf(a, x) { for (var i = 0; i < a.length; i++) { if (a[i] === x) { return i; } } return -1; }
function contains(a, x) { return indexOf(a, x) >= 0; }
function startsWith(s, p) { return s.substring(0, p.length) === p; }
function endsWith(s, p) { return s.length >= p.length && s.substring(s.length - p.length) === p; }
function repeat(s, n) { var o = []; for (var i = 0; i < n; i++) { o.push(s); } return o.join(""); }
function isInt(v) { return typeof v === "number" && isFinite(v) && Math.floor(v) === v; }

// A JSON number that is a float in its source or by the writer's intent:
// `1.0` stays `1.0` (a JavaScript number cannot tell 1 from 1.0).
function WFloat(v) { this.value = v; }
// An integer outside +-2^53, kept as its lexeme.
function WInt(lexeme) { this.lexeme = lexeme; }
function numValue(v) {
  if (v instanceof WFloat) { return v.value; }
  if (v instanceof WInt) { return parseFloat(v.lexeme); }
  return v;
}

// UTF-8 (MINI-SPECS section 2)
function utf8Encode(s) {
  var b = B.builder(), i, c, d;
  for (i = 0; i < s.length; i++) {
    c = s.charCodeAt(i);
    if (c >= 0xD800 && c <= 0xDBFF) {
      d = i + 1 < s.length ? s.charCodeAt(i + 1) : 0;
      if (d < 0xDC00 || d > 0xDFFF) { throw new WerkError("lone surrogate in a string"); }
      c = 0x10000 + ((c - 0xD800) << 10) + (d - 0xDC00);
      i++;
    } else if (c >= 0xDC00 && c <= 0xDFFF) {
      throw new WerkError("lone surrogate in a string");
    }
    if (c < 0x80) { b.put8(c); }
    else if (c < 0x800) { b.put8(0xC0 | (c >> 6)); b.put8(0x80 | (c & 63)); }
    else if (c < 0x10000) { b.put8(0xE0 | (c >> 12)); b.put8(0x80 | ((c >> 6) & 63)); b.put8(0x80 | (c & 63)); }
    else { b.put8(0xF0 | (c >> 18)); b.put8(0x80 | ((c >> 12) & 63)); b.put8(0x80 | ((c >> 6) & 63)); b.put8(0x80 | (c & 63)); }
  }
  return b.done();
}

function utf8Decode(bytes) {
  var out = [], parts = [], n = B.len(bytes), i = 0, c, c2, c3, c4, cp;
  while (i < n) {
    c = B.at(bytes, i);
    if (c < 0x80) { cp = c; i += 1; }
    else if (c >= 0xC2 && c <= 0xDF && i + 1 < n) {
      c2 = B.at(bytes, i + 1);
      if ((c2 & 0xC0) !== 0x80) { throw new WerkError("invalid UTF-8"); }
      cp = ((c & 31) << 6) | (c2 & 63); i += 2;
    } else if (c >= 0xE0 && c <= 0xEF && i + 2 < n) {
      c2 = B.at(bytes, i + 1); c3 = B.at(bytes, i + 2);
      if ((c2 & 0xC0) !== 0x80 || (c3 & 0xC0) !== 0x80) { throw new WerkError("invalid UTF-8"); }
      cp = ((c & 15) << 12) | ((c2 & 63) << 6) | (c3 & 63);
      if (cp < 0x800 || (cp >= 0xD800 && cp <= 0xDFFF)) { throw new WerkError("invalid UTF-8"); }
      i += 3;
    } else if (c >= 0xF0 && c <= 0xF4 && i + 3 < n) {
      c2 = B.at(bytes, i + 1); c3 = B.at(bytes, i + 2); c4 = B.at(bytes, i + 3);
      if ((c2 & 0xC0) !== 0x80 || (c3 & 0xC0) !== 0x80 || (c4 & 0xC0) !== 0x80) { throw new WerkError("invalid UTF-8"); }
      cp = ((c & 7) << 18) | ((c2 & 63) << 12) | ((c3 & 63) << 6) | (c4 & 63);
      if (cp < 0x10000 || cp > 0x10FFFF) { throw new WerkError("invalid UTF-8"); }
      i += 4;
    } else { throw new WerkError("invalid UTF-8 at byte " + i); }
    if (cp >= 0x10000) { cp -= 0x10000; out.push(0xD800 + (cp >> 10), 0xDC00 + (cp & 1023)); }
    else { out.push(cp); }
    if (out.length >= 4096) { parts.push(String.fromCharCode.apply(null, out)); out = []; }
  }
  if (out.length) { parts.push(String.fromCharCode.apply(null, out)); }
  return parts.join("");
}

// UTF-8 with every invalid sequence replaced by U+FFFD, the maximal-subpart
// policy (Unicode 6.2+; what Python's "replace" error handler does).
function utf8DecodeLossy(bytes) {
  var out = [], n = B.len(bytes), i = 0, c, need, cp, lo, hi, k, b;
  while (i < n) {
    c = B.at(bytes, i);
    if (c < 0x80) { out.push(c); i++; continue; }
    if (c >= 0xC2 && c <= 0xDF) { need = 1; cp = c & 31; lo = 0x80; hi = 0xBF; }
    else if (c >= 0xE0 && c <= 0xEF) { need = 2; cp = c & 15; lo = c === 0xE0 ? 0xA0 : 0x80; hi = c === 0xED ? 0x9F : 0xBF; }
    else if (c >= 0xF0 && c <= 0xF4) { need = 3; cp = c & 7; lo = c === 0xF0 ? 0x90 : 0x80; hi = c === 0xF4 ? 0x8F : 0xBF; }
    else { out.push(0xFFFD); i++; continue; }
    i++;
    for (k = 0; k < need; k++) {
      b = i < n ? B.at(bytes, i) : -1;
      if (b < lo || b > hi) { break; }
      cp = (cp << 6) | (b & 63); i++; lo = 0x80; hi = 0xBF;
    }
    if (k < need) { out.push(0xFFFD); continue; }
    if (cp >= 0x10000) { cp -= 0x10000; out.push(0xD800 + (cp >> 10), 0xDC00 + (cp & 1023)); } else { out.push(cp); }
  }
  var parts = [];
  for (k = 0; k < out.length; k += 4096) { parts.push(String.fromCharCode.apply(null, out.slice(k, k + 4096))); }
  return parts.join("");
}

function asciiBytes(s) {
  var a = [];
  for (var i = 0; i < s.length; i++) { a.push(s.charCodeAt(i) & 255); }
  return B.fromArray(a);
}

// Compare two strings by their UTF-8 bytes == by code points.
function codePointAt(s, i) {
  var c = s.charCodeAt(i);
  if (c >= 0xD800 && c <= 0xDBFF && i + 1 < s.length) {
    var d = s.charCodeAt(i + 1);
    if (d >= 0xDC00 && d <= 0xDFFF) { return 0x10000 + ((c - 0xD800) << 10) + (d - 0xDC00); }
  }
  return c;
}
function compareUtf8(a, b) {
  var i = 0, j = 0, ca, cb;
  while (i < a.length && j < b.length) {
    ca = codePointAt(a, i); cb = codePointAt(b, j);
    if (ca !== cb) { return ca < cb ? -1 : 1; }
    i += ca >= 0x10000 ? 2 : 1; j += cb >= 0x10000 ? 2 : 1;
  }
  if (i < a.length) { return 1; }
  if (j < b.length) { return -1; }
  return 0;
}
function sortUtf8(arr) { var a = arr.slice(0); a.sort(compareUtf8); return a; }

var HEXC = "0123456789abcdef";
function toHex(b) {
  var o = [], n = B.len(b), x;
  for (var i = 0; i < n; i++) { x = B.at(b, i); o.push(HEXC.charAt(x >> 4) + HEXC.charAt(x & 15)); }
  return o.join("");
}
function fromHex(s) {
  if (typeof s !== "string" || s.length % 2 || !/^[0-9a-fA-F]*$/.test(s)) { throw new WerkError("not hex"); }
  var a = [];
  for (var i = 0; i < s.length; i += 2) { a.push(parseInt(s.substring(i, i + 2), 16)); }
  return B.fromArray(a);
}

var B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
var B64_REV = null;
function b64decode(s) {
  // Four characters -> three bytes into a small array, turned into bytes every
  // 3 KiB: no per-byte call, no unbounded array (ExtendScript pays for both).
  var i, j, n = s.length, chunk = [], parts = [], acc = 0, bits = 0, v, R;
  if (!B64_REV) { B64_REV = []; for (i = 0; i < 256; i++) { B64_REV.push(-1); } for (i = 0; i < 64; i++) { B64_REV[B64.charCodeAt(i)] = i; } }
  R = B64_REV;
  for (i = 0; i < n; i++) {
    j = s.charCodeAt(i);
    if (j === 61) { break; }
    v = j < 256 ? R[j] : -1;
    if (v < 0) { continue; }
    acc = ((acc << 6) | v) & 0xFFFFFF; bits += 6;
    if (bits >= 8) {
      bits -= 8; chunk.push((acc >> bits) & 255);
      if (chunk.length >= 3072) { parts.push(B.fromArray(chunk)); chunk = []; }
    }
  }
  if (chunk.length) { parts.push(B.fromArray(chunk)); }
  return parts.length === 1 ? parts[0] : B.concat(parts);
}

// ---------------------------------------------------------------- JSON
// Strict parse (MINI-SPECS section 3): no duplicate keys, no BOM, finite
// numbers; a number spelled with a fraction or exponent becomes a WFloat.
function jsonParse(text) {
  var pos = 0, n = text.length;
  if (text.charCodeAt(0) === 0xFEFF) { throw new WerkError("JSON starts with a byte-order mark"); }
  function fail(m) { throw new WerkError("JSON: " + m + " at offset " + pos); }
  function ws() { var c; while (pos < n) { c = text.charAt(pos); if (c === " " || c === "\t" || c === "\n" || c === "\r") { pos++; } else { break; } } }
  function str() {
    var out = [], c, h;
    pos++;
    while (true) {
      if (pos >= n) { fail("unterminated string"); }
      c = text.charAt(pos);
      if (c === "\"") { pos++; break; }
      if (c === "\\") {
        c = text.charAt(pos + 1);
        if (c === "u") {
          h = text.substring(pos + 2, pos + 6);
          if (!/^[0-9a-fA-F]{4}$/.test(h)) { fail("bad \\u escape"); }
          out.push(String.fromCharCode(parseInt(h, 16))); pos += 6;
        } else {
          var m = { "\"": "\"", "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t" };
          if (!hasOwn(m, c)) { fail("bad escape"); }
          out.push(m[c]); pos += 2;
        }
      } else {
        if (c.charCodeAt(0) < 0x20) { fail("control character in string"); }
        out.push(c); pos++;
      }
    }
    return out.join("");
  }
  function num() {
    var start = pos;
    if (text.charAt(pos) === "-") { pos++; }
    if (text.charAt(pos) === "0") { pos++; }
    else if (/[1-9]/.test(text.charAt(pos))) { while (/[0-9]/.test(text.charAt(pos))) { pos++; } }
    else { fail("bad number"); }
    var isF = false;
    if (text.charAt(pos) === ".") {
      isF = true; pos++;
      if (!/[0-9]/.test(text.charAt(pos))) { fail("bad fraction"); }
      while (/[0-9]/.test(text.charAt(pos))) { pos++; }
    }
    if (text.charAt(pos) === "e" || text.charAt(pos) === "E") {
      isF = true; pos++;
      if (text.charAt(pos) === "+" || text.charAt(pos) === "-") { pos++; }
      if (!/[0-9]/.test(text.charAt(pos))) { fail("bad exponent"); }
      while (/[0-9]/.test(text.charAt(pos))) { pos++; }
    }
    var lex = text.substring(start, pos), v = parseFloat(lex);
    if (!isFinite(v)) { fail("number does not fit binary64"); }
    if (isF) { return new WFloat(v); }
    if (Math.abs(v) > 9007199254740991) { return new WInt(lex.charAt(0) === "-" && /^-0+$/.test(lex) ? "0" : lex); }
    return v === 0 ? 0 : v;
  }
  function val(depth) {
    if (depth > 512) { fail("nesting deeper than 512"); }
    ws();
    var c = text.charAt(pos);
    if (c === "{") {
      var o = {}, k;
      pos++; ws();
      if (text.charAt(pos) === "}") { pos++; return o; }
      while (true) {
        ws();
        if (text.charAt(pos) !== "\"") { fail("expected a string key"); }
        k = str();
        if (k === "__proto__") { fail("the key __proto__ is not accepted"); }
        if (hasOwn(o, k)) { fail("duplicate object key " + k); }
        ws();
        if (text.charAt(pos) !== ":") { fail("expected ':'"); }
        pos++;
        o[k] = val(depth + 1);
        ws();
        c = text.charAt(pos);
        if (c === ",") { pos++; continue; }
        if (c === "}") { pos++; return o; }
        fail("expected ',' or '}'");
      }
    }
    if (c === "[") {
      var a = [];
      pos++; ws();
      if (text.charAt(pos) === "]") { pos++; return a; }
      while (true) {
        a.push(val(depth + 1));
        ws();
        c = text.charAt(pos);
        if (c === ",") { pos++; continue; }
        if (c === "]") { pos++; return a; }
        fail("expected ',' or ']'");
      }
    }
    if (c === "\"") { return str(); }
    if (text.substring(pos, pos + 4) === "true") { pos += 4; return true; }
    if (text.substring(pos, pos + 5) === "false") { pos += 5; return false; }
    if (text.substring(pos, pos + 4) === "null") { pos += 4; return null; }
    if (c === "-" || /[0-9]/.test(c)) { return num(); }
    fail("unexpected character");
  }
  var v = val(0);
  ws();
  if (pos !== n) { fail("trailing content"); }
  return v;
}

function jsonParseBytes(b) {
  if (B.len(b) >= 3 && B.at(b, 0) === 0xEF && B.at(b, 1) === 0xBB && B.at(b, 2) === 0xBF) {
    throw new WerkError("JSON starts with a byte-order mark");
  }
  return jsonParse(utf8Decode(b));
}

// Python's repr() of a float: THE spelling of a non-integer in every libs/
// writer. Shortest digits that round-trip, fixed notation for decimal
// exponents -4..15, else d.ddde+XX with at least two exponent digits.
// Exact shortest digits (Steele & White / Burger & Dybvig free-format, with
// IEEE round-half-even boundaries and ties to the even digit -- the rule of
// Python's repr and of ECMAScript Number::toString). Done with integer
// bignums so the spelling never depends on the engine's own float printing
// or parsing: ExtendScript's parseFloat is not correctly rounded, which a
// String()/toPrecision approach silently trusts (measured in Illustrator
// 2020, ExtendScript 4.5.6: 1713 of 2512 doubles misspelled).
var BN = 10000000;
function bnSmall(n) { var r = []; do { r.push(n % BN); n = Math.floor(n / BN); } while (n > 0); return r; }
function bnMul(x, m) {
  var r = [], c = 0, i, t;
  for (i = 0; i < x.length; i++) { t = x[i] * m + c; c = Math.floor(t / BN); r.push(t - c * BN); }
  while (c > 0) { r.push(c % BN); c = Math.floor(c / BN); }
  return r;
}
function bnAdd(x, y) {
  var r = [], c = 0, i, t, n = Math.max(x.length, y.length);
  for (i = 0; i < n; i++) { t = (x[i] || 0) + (y[i] || 0) + c; c = t >= BN ? 1 : 0; r.push(t - c * BN); }
  if (c) { r.push(c); }
  return r;
}
function bnSub(x, y) {
  var r = [], b = 0, i, t;
  for (i = 0; i < x.length; i++) { t = x[i] - (y[i] || 0) - b; b = t < 0 ? 1 : 0; r.push(t + b * BN); }
  while (r.length > 1 && r[r.length - 1] === 0) { r.pop(); }
  return r;
}
function bnCmp(x, y) {
  var i, n = Math.max(x.length, y.length);
  for (i = n - 1; i >= 0; i--) { var a = x[i] || 0, b = y[i] || 0; if (a !== b) { return a < b ? -1 : 1; } }
  return 0;
}
function bnPow2(x, n) { while (n >= 20) { x = bnMul(x, 1048576); n -= 20; } return n > 0 ? bnMul(x, pow2f(n)) : x; }
function bnPow10(x, n) { while (n >= 6) { x = bnMul(x, 1000000); n -= 6; } while (n > 0) { x = bnMul(x, 10); n--; } return x; }
function pow2f(n) { var r = 1; while (n > 0) { r *= 2; n--; } while (n < 0) { r /= 2; n++; } return r; }

function shortestDigits(a) {
  // a = f * 2^e exactly, f integer
  var f, e, E;
  if (a < pow2f(-1022)) { f = a * pow2f(537) * pow2f(537); e = -1074; }
  else {
    E = Math.floor(Math.log(a) / Math.LN2);
    while (pow2f(E) > a) { E--; }
    while (pow2f(E + 1) <= a) { E++; }
    f = a / pow2f(E - 52); e = E - 52;
  }
  var even = f % 2 === 0, p52 = 4503599627370496, r, s, mp, mm;
  if (e >= 0) {
    var be = bnPow2([1], e);
    if (f !== p52) { r = bnPow2(bnMulBig(bnSmall(f), be), 1); s = [2]; mp = be; mm = be; }
    else { r = bnPow2(bnMulBig(bnSmall(f), be), 2); s = [4]; mp = bnPow2(be, 1); mm = be; }
  } else if (e === -1074 || f !== p52) { r = bnPow2(bnSmall(f), 1); s = bnPow2([1], 1 - e); mp = [1]; mm = [1]; }
  else { r = bnPow2(bnSmall(f), 2); s = bnPow2([1], 2 - e); mp = [2]; mm = [1]; }
  var k = Math.ceil(Math.log(a) / Math.LN10 - 1e-10);
  if (k >= 0) { s = bnPow10(s, k); } else { r = bnPow10(r, -k); mp = bnPow10(mp, -k); mm = bnPow10(mm, -k); }
  function high(rr, mpp, ss) { var c = bnCmp(bnAdd(rr, mpp), ss); return even ? c >= 0 : c > 0; }
  while (high(r, mp, s)) { s = bnMul(s, 10); k++; }
  while (!high(bnMul(r, 10), bnMul(mp, 10), s)) { r = bnMul(r, 10); mp = bnMul(mp, 10); mm = bnMul(mm, 10); k--; }
  var digits = [];
  while (true) {
    r = bnMul(r, 10); mp = bnMul(mp, 10); mm = bnMul(mm, 10);
    var d = 0;
    while (bnCmp(r, s) >= 0) { r = bnSub(r, s); d++; }
    var cl = bnCmp(r, mm), low = even ? cl <= 0 : cl < 0, hi = high(r, mp, s);
    if (!low && !hi) { digits.push(d); continue; }
    if (low && !hi) { digits.push(d); }
    else if (hi && !low) { digits.push(d + 1); }
    else { var c2 = bnCmp(bnMul(r, 2), s); digits.push(c2 < 0 ? d : (c2 > 0 ? d + 1 : (d % 2 === 0 ? d : d + 1))); }
    break;
  }
  return { digits: digits.join(""), k: k };
}
function bnMulBig(x, y) {
  var r = [], i, j, t, c;
  for (i = 0; i < x.length + y.length; i++) { r.push(0); }
  for (i = 0; i < x.length; i++) {
    c = 0;
    for (j = 0; j < y.length; j++) { t = r[i + j] + x[i] * y[j] + c; c = Math.floor(t / BN); r[i + j] = t - c * BN; }
    j = i + y.length;
    while (c > 0) { t = r[j] + c; c = Math.floor(t / BN); r[j] = t - c * BN; j++; }
  }
  while (r.length > 1 && r[r.length - 1] === 0) { r.pop(); }
  return r;
}

// Python's repr() of a float: THE spelling of a non-integer in every libs/
// writer. Shortest digits that round-trip, fixed notation for decimal
// exponents -4..15, else d.ddde+XX with at least two exponent digits.
function pyFloat(x) {
  if (!isFinite(x)) { throw new WerkError("werk JSON numbers are finite"); }
  if (x === 0) { return (1 / x < 0) ? "-0.0" : "0.0"; }
  var neg = x < 0, sd = shortestDigits(neg ? -x : x), digits = sd.digits, sci = sd.k - 1, out;
  while (digits.length > 1 && digits.charAt(digits.length - 1) === "0") { digits = digits.substring(0, digits.length - 1); }
  if (sci >= -4 && sci <= 15) {
    if (sci >= 0) {
      var intd = digits.substring(0, sci + 1);
      while (intd.length < sci + 1) { intd += "0"; }
      var frac = digits.substring(sci + 1);
      out = intd + "." + (frac.length ? frac : "0");
    } else {
      out = "0." + repeat("0", -sci - 1) + digits;
    }
  } else {
    var ex = Math.abs(sci);
    out = digits.charAt(0) + (digits.length > 1 ? "." + digits.substring(1) : "") +
          "e" + (sci < 0 ? "-" : "+") + (ex < 10 ? "0" + ex : String(ex));
  }
  return (neg ? "-" : "") + out;
}

function jsonNum(v) {
  if (v instanceof WFloat) { return pyFloat(v.value); }
  if (v instanceof WInt) { return v.lexeme; }
  if (!isFinite(v)) { throw new WerkError("werk JSON numbers are finite"); }
  if (isInt(v)) {
    if (Math.abs(v) > 9007199254740991) { throw new WerkError("integer outside +-2^53; pass a WInt"); }
    return String(v === 0 ? 0 : v);
  }
  return pyFloat(v);
}

function jsonStr(s) {
  var out = ["\""], i, c, ch;
  for (i = 0; i < s.length; i++) {
    c = s.charCodeAt(i); ch = s.charAt(i);
    if (ch === "\"") { out.push("\\\""); }
    else if (ch === "\\") { out.push("\\\\"); }
    else if (ch === "\n") { out.push("\\n"); }
    else if (ch === "\r") { out.push("\\r"); }
    else if (ch === "\t") { out.push("\\t"); }
    else if (ch === "\b") { out.push("\\b"); }
    else if (ch === "\f") { out.push("\\f"); }
    else if (c < 0x20) { out.push("\\u00" + HEXC.charAt(c >> 4) + HEXC.charAt(c & 15)); }
    else if (c >= 0xD800 && c <= 0xDBFF) {
      var d = i + 1 < s.length ? s.charCodeAt(i + 1) : 0;
      if (d < 0xDC00 || d > 0xDFFF) { throw new WerkError("lone surrogate in a string"); }
      out.push(ch + s.charAt(i + 1)); i++;
    } else if (c >= 0xDC00 && c <= 0xDFFF) { throw new WerkError("lone surrogate in a string"); }
    else { out.push(ch); }
  }
  out.push("\"");
  return out.join("");
}

function jsonEmit(v, indent, level, out, sortKeys) {
  var i, ks, pad, close;
  if (v === null || v === undefined) { out.push("null"); return; }
  if (v === true) { out.push("true"); return; }
  if (v === false) { out.push("false"); return; }
  if (typeof v === "string") { out.push(jsonStr(v)); return; }
  if (typeof v === "number" || v instanceof WFloat || v instanceof WInt) { out.push(jsonNum(v)); return; }
  pad = indent ? "\n" + repeat(" ", indent * (level + 1)) : "";
  close = indent ? "\n" + repeat(" ", indent * level) : "";
  if (isArray(v)) {
    if (!v.length) { out.push("[]"); return; }
    out.push("[");
    for (i = 0; i < v.length; i++) {
      if (i) { out.push(","); }
      out.push(pad);
      jsonEmit(v[i], indent, level + 1, out, sortKeys);
    }
    out.push(close + "]");
    return;
  }
  if (typeof v === "object") {
    ks = keysOf(v);
    if (sortKeys) { ks = sortUtf8(ks); }
    var live = [];
    for (i = 0; i < ks.length; i++) { if (v[ks[i]] !== undefined) { live.push(ks[i]); } }
    if (!live.length) { out.push("{}"); return; }
    out.push("{");
    for (i = 0; i < live.length; i++) {
      if (i) { out.push(","); }
      out.push(pad + jsonStr(live[i]) + (indent ? ": " : ":"));
      jsonEmit(v[live[i]], indent, level + 1, out, sortKeys);
    }
    out.push(close + "}");
    return;
  }
  throw new WerkError("cannot write a " + typeof v + " as JSON");
}

// The bytes every libs/ writer emits for a JSON file (see the Python twin).
function jsonPretty(v) { var o = []; jsonEmit(v, 2, 0, o, false); return utf8Encode(o.join("") + "\n"); }
// MINI-SPECS section 3 canonical JSON.
function jsonCanonical(v) { var o = []; jsonEmit(v, 0, 0, o, true); return utf8Encode(o.join("")); }

// ---------------------------------------------------------------- SHA-256
var K256 = [0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2];

function Sha256() {
  this.h = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19];
  this.buf = []; this.total = 0; this.w = [];
  for (var i = 0; i < 64; i++) { this.w.push(0); }
}
// One 64-byte block from `src` at `o`. `isStr`: src is a binary string
// (charCodeAt), else an indexable byte array (Uint8Array or Array). Locals
// only, preallocated schedule, no calls and no allocation in the rounds.
function sha256Block(H, w, src, o, isStr) {
  // Rounds unrolled with the round constants inlined (generated; see
  // libs/js/README section "speed"): no loop counter, no K[] lookup and no
  // eight-way variable rotation per round -- in ExtendScript every one of
  // those is interpreted work.
  var i, a, b, c, d, e, f, g, h, t, x, y;
  if (isStr) {
    for (i = 0; i < 16; i++) { w[i] = (src.charCodeAt(o) << 24) | (src.charCodeAt(o + 1) << 16) | (src.charCodeAt(o + 2) << 8) | src.charCodeAt(o + 3); o += 4; }
  } else {
    for (i = 0; i < 16; i++) { w[i] = (src[o] << 24) | (src[o + 1] << 16) | (src[o + 2] << 8) | src[o + 3]; o += 4; }
  }
  for (i = 16; i < 64; i++) {
    x = w[i - 15]; y = w[i - 2];
    w[i] = (w[i - 16] + (((x >>> 7) | (x << 25)) ^ ((x >>> 18) | (x << 14)) ^ (x >>> 3)) + w[i - 7] +
            (((y >>> 17) | (y << 15)) ^ ((y >>> 19) | (y << 13)) ^ (y >>> 10))) | 0;
  }
  a = H[0]; b = H[1]; c = H[2]; d = H[3]; e = H[4]; f = H[5]; g = H[6]; h = H[7];
  t = (h + (((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7))) + ((e & f) ^ (~e & g)) + 1116352408 + w[0]) | 0; d = (d + t) | 0; h = (t + ((((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10))) + ((a & b) ^ (a & c) ^ (b & c)))) | 0;
  t = (g + (((d >>> 6) | (d << 26)) ^ ((d >>> 11) | (d << 21)) ^ ((d >>> 25) | (d << 7))) + ((d & e) ^ (~d & f)) + 1899447441 + w[1]) | 0; c = (c + t) | 0; g = (t + ((((h >>> 2) | (h << 30)) ^ ((h >>> 13) | (h << 19)) ^ ((h >>> 22) | (h << 10))) + ((h & a) ^ (h & b) ^ (a & b)))) | 0;
  t = (f + (((c >>> 6) | (c << 26)) ^ ((c >>> 11) | (c << 21)) ^ ((c >>> 25) | (c << 7))) + ((c & d) ^ (~c & e)) + -1245643825 + w[2]) | 0; b = (b + t) | 0; f = (t + ((((g >>> 2) | (g << 30)) ^ ((g >>> 13) | (g << 19)) ^ ((g >>> 22) | (g << 10))) + ((g & h) ^ (g & a) ^ (h & a)))) | 0;
  t = (e + (((b >>> 6) | (b << 26)) ^ ((b >>> 11) | (b << 21)) ^ ((b >>> 25) | (b << 7))) + ((b & c) ^ (~b & d)) + -373957723 + w[3]) | 0; a = (a + t) | 0; e = (t + ((((f >>> 2) | (f << 30)) ^ ((f >>> 13) | (f << 19)) ^ ((f >>> 22) | (f << 10))) + ((f & g) ^ (f & h) ^ (g & h)))) | 0;
  t = (d + (((a >>> 6) | (a << 26)) ^ ((a >>> 11) | (a << 21)) ^ ((a >>> 25) | (a << 7))) + ((a & b) ^ (~a & c)) + 961987163 + w[4]) | 0; h = (h + t) | 0; d = (t + ((((e >>> 2) | (e << 30)) ^ ((e >>> 13) | (e << 19)) ^ ((e >>> 22) | (e << 10))) + ((e & f) ^ (e & g) ^ (f & g)))) | 0;
  t = (c + (((h >>> 6) | (h << 26)) ^ ((h >>> 11) | (h << 21)) ^ ((h >>> 25) | (h << 7))) + ((h & a) ^ (~h & b)) + 1508970993 + w[5]) | 0; g = (g + t) | 0; c = (t + ((((d >>> 2) | (d << 30)) ^ ((d >>> 13) | (d << 19)) ^ ((d >>> 22) | (d << 10))) + ((d & e) ^ (d & f) ^ (e & f)))) | 0;
  t = (b + (((g >>> 6) | (g << 26)) ^ ((g >>> 11) | (g << 21)) ^ ((g >>> 25) | (g << 7))) + ((g & h) ^ (~g & a)) + -1841331548 + w[6]) | 0; f = (f + t) | 0; b = (t + ((((c >>> 2) | (c << 30)) ^ ((c >>> 13) | (c << 19)) ^ ((c >>> 22) | (c << 10))) + ((c & d) ^ (c & e) ^ (d & e)))) | 0;
  t = (a + (((f >>> 6) | (f << 26)) ^ ((f >>> 11) | (f << 21)) ^ ((f >>> 25) | (f << 7))) + ((f & g) ^ (~f & h)) + -1424204075 + w[7]) | 0; e = (e + t) | 0; a = (t + ((((b >>> 2) | (b << 30)) ^ ((b >>> 13) | (b << 19)) ^ ((b >>> 22) | (b << 10))) + ((b & c) ^ (b & d) ^ (c & d)))) | 0;
  t = (h + (((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7))) + ((e & f) ^ (~e & g)) + -670586216 + w[8]) | 0; d = (d + t) | 0; h = (t + ((((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10))) + ((a & b) ^ (a & c) ^ (b & c)))) | 0;
  t = (g + (((d >>> 6) | (d << 26)) ^ ((d >>> 11) | (d << 21)) ^ ((d >>> 25) | (d << 7))) + ((d & e) ^ (~d & f)) + 310598401 + w[9]) | 0; c = (c + t) | 0; g = (t + ((((h >>> 2) | (h << 30)) ^ ((h >>> 13) | (h << 19)) ^ ((h >>> 22) | (h << 10))) + ((h & a) ^ (h & b) ^ (a & b)))) | 0;
  t = (f + (((c >>> 6) | (c << 26)) ^ ((c >>> 11) | (c << 21)) ^ ((c >>> 25) | (c << 7))) + ((c & d) ^ (~c & e)) + 607225278 + w[10]) | 0; b = (b + t) | 0; f = (t + ((((g >>> 2) | (g << 30)) ^ ((g >>> 13) | (g << 19)) ^ ((g >>> 22) | (g << 10))) + ((g & h) ^ (g & a) ^ (h & a)))) | 0;
  t = (e + (((b >>> 6) | (b << 26)) ^ ((b >>> 11) | (b << 21)) ^ ((b >>> 25) | (b << 7))) + ((b & c) ^ (~b & d)) + 1426881987 + w[11]) | 0; a = (a + t) | 0; e = (t + ((((f >>> 2) | (f << 30)) ^ ((f >>> 13) | (f << 19)) ^ ((f >>> 22) | (f << 10))) + ((f & g) ^ (f & h) ^ (g & h)))) | 0;
  t = (d + (((a >>> 6) | (a << 26)) ^ ((a >>> 11) | (a << 21)) ^ ((a >>> 25) | (a << 7))) + ((a & b) ^ (~a & c)) + 1925078388 + w[12]) | 0; h = (h + t) | 0; d = (t + ((((e >>> 2) | (e << 30)) ^ ((e >>> 13) | (e << 19)) ^ ((e >>> 22) | (e << 10))) + ((e & f) ^ (e & g) ^ (f & g)))) | 0;
  t = (c + (((h >>> 6) | (h << 26)) ^ ((h >>> 11) | (h << 21)) ^ ((h >>> 25) | (h << 7))) + ((h & a) ^ (~h & b)) + -2132889090 + w[13]) | 0; g = (g + t) | 0; c = (t + ((((d >>> 2) | (d << 30)) ^ ((d >>> 13) | (d << 19)) ^ ((d >>> 22) | (d << 10))) + ((d & e) ^ (d & f) ^ (e & f)))) | 0;
  t = (b + (((g >>> 6) | (g << 26)) ^ ((g >>> 11) | (g << 21)) ^ ((g >>> 25) | (g << 7))) + ((g & h) ^ (~g & a)) + -1680079193 + w[14]) | 0; f = (f + t) | 0; b = (t + ((((c >>> 2) | (c << 30)) ^ ((c >>> 13) | (c << 19)) ^ ((c >>> 22) | (c << 10))) + ((c & d) ^ (c & e) ^ (d & e)))) | 0;
  t = (a + (((f >>> 6) | (f << 26)) ^ ((f >>> 11) | (f << 21)) ^ ((f >>> 25) | (f << 7))) + ((f & g) ^ (~f & h)) + -1046744716 + w[15]) | 0; e = (e + t) | 0; a = (t + ((((b >>> 2) | (b << 30)) ^ ((b >>> 13) | (b << 19)) ^ ((b >>> 22) | (b << 10))) + ((b & c) ^ (b & d) ^ (c & d)))) | 0;
  t = (h + (((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7))) + ((e & f) ^ (~e & g)) + -459576895 + w[16]) | 0; d = (d + t) | 0; h = (t + ((((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10))) + ((a & b) ^ (a & c) ^ (b & c)))) | 0;
  t = (g + (((d >>> 6) | (d << 26)) ^ ((d >>> 11) | (d << 21)) ^ ((d >>> 25) | (d << 7))) + ((d & e) ^ (~d & f)) + -272742522 + w[17]) | 0; c = (c + t) | 0; g = (t + ((((h >>> 2) | (h << 30)) ^ ((h >>> 13) | (h << 19)) ^ ((h >>> 22) | (h << 10))) + ((h & a) ^ (h & b) ^ (a & b)))) | 0;
  t = (f + (((c >>> 6) | (c << 26)) ^ ((c >>> 11) | (c << 21)) ^ ((c >>> 25) | (c << 7))) + ((c & d) ^ (~c & e)) + 264347078 + w[18]) | 0; b = (b + t) | 0; f = (t + ((((g >>> 2) | (g << 30)) ^ ((g >>> 13) | (g << 19)) ^ ((g >>> 22) | (g << 10))) + ((g & h) ^ (g & a) ^ (h & a)))) | 0;
  t = (e + (((b >>> 6) | (b << 26)) ^ ((b >>> 11) | (b << 21)) ^ ((b >>> 25) | (b << 7))) + ((b & c) ^ (~b & d)) + 604807628 + w[19]) | 0; a = (a + t) | 0; e = (t + ((((f >>> 2) | (f << 30)) ^ ((f >>> 13) | (f << 19)) ^ ((f >>> 22) | (f << 10))) + ((f & g) ^ (f & h) ^ (g & h)))) | 0;
  t = (d + (((a >>> 6) | (a << 26)) ^ ((a >>> 11) | (a << 21)) ^ ((a >>> 25) | (a << 7))) + ((a & b) ^ (~a & c)) + 770255983 + w[20]) | 0; h = (h + t) | 0; d = (t + ((((e >>> 2) | (e << 30)) ^ ((e >>> 13) | (e << 19)) ^ ((e >>> 22) | (e << 10))) + ((e & f) ^ (e & g) ^ (f & g)))) | 0;
  t = (c + (((h >>> 6) | (h << 26)) ^ ((h >>> 11) | (h << 21)) ^ ((h >>> 25) | (h << 7))) + ((h & a) ^ (~h & b)) + 1249150122 + w[21]) | 0; g = (g + t) | 0; c = (t + ((((d >>> 2) | (d << 30)) ^ ((d >>> 13) | (d << 19)) ^ ((d >>> 22) | (d << 10))) + ((d & e) ^ (d & f) ^ (e & f)))) | 0;
  t = (b + (((g >>> 6) | (g << 26)) ^ ((g >>> 11) | (g << 21)) ^ ((g >>> 25) | (g << 7))) + ((g & h) ^ (~g & a)) + 1555081692 + w[22]) | 0; f = (f + t) | 0; b = (t + ((((c >>> 2) | (c << 30)) ^ ((c >>> 13) | (c << 19)) ^ ((c >>> 22) | (c << 10))) + ((c & d) ^ (c & e) ^ (d & e)))) | 0;
  t = (a + (((f >>> 6) | (f << 26)) ^ ((f >>> 11) | (f << 21)) ^ ((f >>> 25) | (f << 7))) + ((f & g) ^ (~f & h)) + 1996064986 + w[23]) | 0; e = (e + t) | 0; a = (t + ((((b >>> 2) | (b << 30)) ^ ((b >>> 13) | (b << 19)) ^ ((b >>> 22) | (b << 10))) + ((b & c) ^ (b & d) ^ (c & d)))) | 0;
  t = (h + (((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7))) + ((e & f) ^ (~e & g)) + -1740746414 + w[24]) | 0; d = (d + t) | 0; h = (t + ((((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10))) + ((a & b) ^ (a & c) ^ (b & c)))) | 0;
  t = (g + (((d >>> 6) | (d << 26)) ^ ((d >>> 11) | (d << 21)) ^ ((d >>> 25) | (d << 7))) + ((d & e) ^ (~d & f)) + -1473132947 + w[25]) | 0; c = (c + t) | 0; g = (t + ((((h >>> 2) | (h << 30)) ^ ((h >>> 13) | (h << 19)) ^ ((h >>> 22) | (h << 10))) + ((h & a) ^ (h & b) ^ (a & b)))) | 0;
  t = (f + (((c >>> 6) | (c << 26)) ^ ((c >>> 11) | (c << 21)) ^ ((c >>> 25) | (c << 7))) + ((c & d) ^ (~c & e)) + -1341970488 + w[26]) | 0; b = (b + t) | 0; f = (t + ((((g >>> 2) | (g << 30)) ^ ((g >>> 13) | (g << 19)) ^ ((g >>> 22) | (g << 10))) + ((g & h) ^ (g & a) ^ (h & a)))) | 0;
  t = (e + (((b >>> 6) | (b << 26)) ^ ((b >>> 11) | (b << 21)) ^ ((b >>> 25) | (b << 7))) + ((b & c) ^ (~b & d)) + -1084653625 + w[27]) | 0; a = (a + t) | 0; e = (t + ((((f >>> 2) | (f << 30)) ^ ((f >>> 13) | (f << 19)) ^ ((f >>> 22) | (f << 10))) + ((f & g) ^ (f & h) ^ (g & h)))) | 0;
  t = (d + (((a >>> 6) | (a << 26)) ^ ((a >>> 11) | (a << 21)) ^ ((a >>> 25) | (a << 7))) + ((a & b) ^ (~a & c)) + -958395405 + w[28]) | 0; h = (h + t) | 0; d = (t + ((((e >>> 2) | (e << 30)) ^ ((e >>> 13) | (e << 19)) ^ ((e >>> 22) | (e << 10))) + ((e & f) ^ (e & g) ^ (f & g)))) | 0;
  t = (c + (((h >>> 6) | (h << 26)) ^ ((h >>> 11) | (h << 21)) ^ ((h >>> 25) | (h << 7))) + ((h & a) ^ (~h & b)) + -710438585 + w[29]) | 0; g = (g + t) | 0; c = (t + ((((d >>> 2) | (d << 30)) ^ ((d >>> 13) | (d << 19)) ^ ((d >>> 22) | (d << 10))) + ((d & e) ^ (d & f) ^ (e & f)))) | 0;
  t = (b + (((g >>> 6) | (g << 26)) ^ ((g >>> 11) | (g << 21)) ^ ((g >>> 25) | (g << 7))) + ((g & h) ^ (~g & a)) + 113926993 + w[30]) | 0; f = (f + t) | 0; b = (t + ((((c >>> 2) | (c << 30)) ^ ((c >>> 13) | (c << 19)) ^ ((c >>> 22) | (c << 10))) + ((c & d) ^ (c & e) ^ (d & e)))) | 0;
  t = (a + (((f >>> 6) | (f << 26)) ^ ((f >>> 11) | (f << 21)) ^ ((f >>> 25) | (f << 7))) + ((f & g) ^ (~f & h)) + 338241895 + w[31]) | 0; e = (e + t) | 0; a = (t + ((((b >>> 2) | (b << 30)) ^ ((b >>> 13) | (b << 19)) ^ ((b >>> 22) | (b << 10))) + ((b & c) ^ (b & d) ^ (c & d)))) | 0;
  t = (h + (((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7))) + ((e & f) ^ (~e & g)) + 666307205 + w[32]) | 0; d = (d + t) | 0; h = (t + ((((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10))) + ((a & b) ^ (a & c) ^ (b & c)))) | 0;
  t = (g + (((d >>> 6) | (d << 26)) ^ ((d >>> 11) | (d << 21)) ^ ((d >>> 25) | (d << 7))) + ((d & e) ^ (~d & f)) + 773529912 + w[33]) | 0; c = (c + t) | 0; g = (t + ((((h >>> 2) | (h << 30)) ^ ((h >>> 13) | (h << 19)) ^ ((h >>> 22) | (h << 10))) + ((h & a) ^ (h & b) ^ (a & b)))) | 0;
  t = (f + (((c >>> 6) | (c << 26)) ^ ((c >>> 11) | (c << 21)) ^ ((c >>> 25) | (c << 7))) + ((c & d) ^ (~c & e)) + 1294757372 + w[34]) | 0; b = (b + t) | 0; f = (t + ((((g >>> 2) | (g << 30)) ^ ((g >>> 13) | (g << 19)) ^ ((g >>> 22) | (g << 10))) + ((g & h) ^ (g & a) ^ (h & a)))) | 0;
  t = (e + (((b >>> 6) | (b << 26)) ^ ((b >>> 11) | (b << 21)) ^ ((b >>> 25) | (b << 7))) + ((b & c) ^ (~b & d)) + 1396182291 + w[35]) | 0; a = (a + t) | 0; e = (t + ((((f >>> 2) | (f << 30)) ^ ((f >>> 13) | (f << 19)) ^ ((f >>> 22) | (f << 10))) + ((f & g) ^ (f & h) ^ (g & h)))) | 0;
  t = (d + (((a >>> 6) | (a << 26)) ^ ((a >>> 11) | (a << 21)) ^ ((a >>> 25) | (a << 7))) + ((a & b) ^ (~a & c)) + 1695183700 + w[36]) | 0; h = (h + t) | 0; d = (t + ((((e >>> 2) | (e << 30)) ^ ((e >>> 13) | (e << 19)) ^ ((e >>> 22) | (e << 10))) + ((e & f) ^ (e & g) ^ (f & g)))) | 0;
  t = (c + (((h >>> 6) | (h << 26)) ^ ((h >>> 11) | (h << 21)) ^ ((h >>> 25) | (h << 7))) + ((h & a) ^ (~h & b)) + 1986661051 + w[37]) | 0; g = (g + t) | 0; c = (t + ((((d >>> 2) | (d << 30)) ^ ((d >>> 13) | (d << 19)) ^ ((d >>> 22) | (d << 10))) + ((d & e) ^ (d & f) ^ (e & f)))) | 0;
  t = (b + (((g >>> 6) | (g << 26)) ^ ((g >>> 11) | (g << 21)) ^ ((g >>> 25) | (g << 7))) + ((g & h) ^ (~g & a)) + -2117940946 + w[38]) | 0; f = (f + t) | 0; b = (t + ((((c >>> 2) | (c << 30)) ^ ((c >>> 13) | (c << 19)) ^ ((c >>> 22) | (c << 10))) + ((c & d) ^ (c & e) ^ (d & e)))) | 0;
  t = (a + (((f >>> 6) | (f << 26)) ^ ((f >>> 11) | (f << 21)) ^ ((f >>> 25) | (f << 7))) + ((f & g) ^ (~f & h)) + -1838011259 + w[39]) | 0; e = (e + t) | 0; a = (t + ((((b >>> 2) | (b << 30)) ^ ((b >>> 13) | (b << 19)) ^ ((b >>> 22) | (b << 10))) + ((b & c) ^ (b & d) ^ (c & d)))) | 0;
  t = (h + (((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7))) + ((e & f) ^ (~e & g)) + -1564481375 + w[40]) | 0; d = (d + t) | 0; h = (t + ((((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10))) + ((a & b) ^ (a & c) ^ (b & c)))) | 0;
  t = (g + (((d >>> 6) | (d << 26)) ^ ((d >>> 11) | (d << 21)) ^ ((d >>> 25) | (d << 7))) + ((d & e) ^ (~d & f)) + -1474664885 + w[41]) | 0; c = (c + t) | 0; g = (t + ((((h >>> 2) | (h << 30)) ^ ((h >>> 13) | (h << 19)) ^ ((h >>> 22) | (h << 10))) + ((h & a) ^ (h & b) ^ (a & b)))) | 0;
  t = (f + (((c >>> 6) | (c << 26)) ^ ((c >>> 11) | (c << 21)) ^ ((c >>> 25) | (c << 7))) + ((c & d) ^ (~c & e)) + -1035236496 + w[42]) | 0; b = (b + t) | 0; f = (t + ((((g >>> 2) | (g << 30)) ^ ((g >>> 13) | (g << 19)) ^ ((g >>> 22) | (g << 10))) + ((g & h) ^ (g & a) ^ (h & a)))) | 0;
  t = (e + (((b >>> 6) | (b << 26)) ^ ((b >>> 11) | (b << 21)) ^ ((b >>> 25) | (b << 7))) + ((b & c) ^ (~b & d)) + -949202525 + w[43]) | 0; a = (a + t) | 0; e = (t + ((((f >>> 2) | (f << 30)) ^ ((f >>> 13) | (f << 19)) ^ ((f >>> 22) | (f << 10))) + ((f & g) ^ (f & h) ^ (g & h)))) | 0;
  t = (d + (((a >>> 6) | (a << 26)) ^ ((a >>> 11) | (a << 21)) ^ ((a >>> 25) | (a << 7))) + ((a & b) ^ (~a & c)) + -778901479 + w[44]) | 0; h = (h + t) | 0; d = (t + ((((e >>> 2) | (e << 30)) ^ ((e >>> 13) | (e << 19)) ^ ((e >>> 22) | (e << 10))) + ((e & f) ^ (e & g) ^ (f & g)))) | 0;
  t = (c + (((h >>> 6) | (h << 26)) ^ ((h >>> 11) | (h << 21)) ^ ((h >>> 25) | (h << 7))) + ((h & a) ^ (~h & b)) + -694614492 + w[45]) | 0; g = (g + t) | 0; c = (t + ((((d >>> 2) | (d << 30)) ^ ((d >>> 13) | (d << 19)) ^ ((d >>> 22) | (d << 10))) + ((d & e) ^ (d & f) ^ (e & f)))) | 0;
  t = (b + (((g >>> 6) | (g << 26)) ^ ((g >>> 11) | (g << 21)) ^ ((g >>> 25) | (g << 7))) + ((g & h) ^ (~g & a)) + -200395387 + w[46]) | 0; f = (f + t) | 0; b = (t + ((((c >>> 2) | (c << 30)) ^ ((c >>> 13) | (c << 19)) ^ ((c >>> 22) | (c << 10))) + ((c & d) ^ (c & e) ^ (d & e)))) | 0;
  t = (a + (((f >>> 6) | (f << 26)) ^ ((f >>> 11) | (f << 21)) ^ ((f >>> 25) | (f << 7))) + ((f & g) ^ (~f & h)) + 275423344 + w[47]) | 0; e = (e + t) | 0; a = (t + ((((b >>> 2) | (b << 30)) ^ ((b >>> 13) | (b << 19)) ^ ((b >>> 22) | (b << 10))) + ((b & c) ^ (b & d) ^ (c & d)))) | 0;
  t = (h + (((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7))) + ((e & f) ^ (~e & g)) + 430227734 + w[48]) | 0; d = (d + t) | 0; h = (t + ((((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10))) + ((a & b) ^ (a & c) ^ (b & c)))) | 0;
  t = (g + (((d >>> 6) | (d << 26)) ^ ((d >>> 11) | (d << 21)) ^ ((d >>> 25) | (d << 7))) + ((d & e) ^ (~d & f)) + 506948616 + w[49]) | 0; c = (c + t) | 0; g = (t + ((((h >>> 2) | (h << 30)) ^ ((h >>> 13) | (h << 19)) ^ ((h >>> 22) | (h << 10))) + ((h & a) ^ (h & b) ^ (a & b)))) | 0;
  t = (f + (((c >>> 6) | (c << 26)) ^ ((c >>> 11) | (c << 21)) ^ ((c >>> 25) | (c << 7))) + ((c & d) ^ (~c & e)) + 659060556 + w[50]) | 0; b = (b + t) | 0; f = (t + ((((g >>> 2) | (g << 30)) ^ ((g >>> 13) | (g << 19)) ^ ((g >>> 22) | (g << 10))) + ((g & h) ^ (g & a) ^ (h & a)))) | 0;
  t = (e + (((b >>> 6) | (b << 26)) ^ ((b >>> 11) | (b << 21)) ^ ((b >>> 25) | (b << 7))) + ((b & c) ^ (~b & d)) + 883997877 + w[51]) | 0; a = (a + t) | 0; e = (t + ((((f >>> 2) | (f << 30)) ^ ((f >>> 13) | (f << 19)) ^ ((f >>> 22) | (f << 10))) + ((f & g) ^ (f & h) ^ (g & h)))) | 0;
  t = (d + (((a >>> 6) | (a << 26)) ^ ((a >>> 11) | (a << 21)) ^ ((a >>> 25) | (a << 7))) + ((a & b) ^ (~a & c)) + 958139571 + w[52]) | 0; h = (h + t) | 0; d = (t + ((((e >>> 2) | (e << 30)) ^ ((e >>> 13) | (e << 19)) ^ ((e >>> 22) | (e << 10))) + ((e & f) ^ (e & g) ^ (f & g)))) | 0;
  t = (c + (((h >>> 6) | (h << 26)) ^ ((h >>> 11) | (h << 21)) ^ ((h >>> 25) | (h << 7))) + ((h & a) ^ (~h & b)) + 1322822218 + w[53]) | 0; g = (g + t) | 0; c = (t + ((((d >>> 2) | (d << 30)) ^ ((d >>> 13) | (d << 19)) ^ ((d >>> 22) | (d << 10))) + ((d & e) ^ (d & f) ^ (e & f)))) | 0;
  t = (b + (((g >>> 6) | (g << 26)) ^ ((g >>> 11) | (g << 21)) ^ ((g >>> 25) | (g << 7))) + ((g & h) ^ (~g & a)) + 1537002063 + w[54]) | 0; f = (f + t) | 0; b = (t + ((((c >>> 2) | (c << 30)) ^ ((c >>> 13) | (c << 19)) ^ ((c >>> 22) | (c << 10))) + ((c & d) ^ (c & e) ^ (d & e)))) | 0;
  t = (a + (((f >>> 6) | (f << 26)) ^ ((f >>> 11) | (f << 21)) ^ ((f >>> 25) | (f << 7))) + ((f & g) ^ (~f & h)) + 1747873779 + w[55]) | 0; e = (e + t) | 0; a = (t + ((((b >>> 2) | (b << 30)) ^ ((b >>> 13) | (b << 19)) ^ ((b >>> 22) | (b << 10))) + ((b & c) ^ (b & d) ^ (c & d)))) | 0;
  t = (h + (((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7))) + ((e & f) ^ (~e & g)) + 1955562222 + w[56]) | 0; d = (d + t) | 0; h = (t + ((((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10))) + ((a & b) ^ (a & c) ^ (b & c)))) | 0;
  t = (g + (((d >>> 6) | (d << 26)) ^ ((d >>> 11) | (d << 21)) ^ ((d >>> 25) | (d << 7))) + ((d & e) ^ (~d & f)) + 2024104815 + w[57]) | 0; c = (c + t) | 0; g = (t + ((((h >>> 2) | (h << 30)) ^ ((h >>> 13) | (h << 19)) ^ ((h >>> 22) | (h << 10))) + ((h & a) ^ (h & b) ^ (a & b)))) | 0;
  t = (f + (((c >>> 6) | (c << 26)) ^ ((c >>> 11) | (c << 21)) ^ ((c >>> 25) | (c << 7))) + ((c & d) ^ (~c & e)) + -2067236844 + w[58]) | 0; b = (b + t) | 0; f = (t + ((((g >>> 2) | (g << 30)) ^ ((g >>> 13) | (g << 19)) ^ ((g >>> 22) | (g << 10))) + ((g & h) ^ (g & a) ^ (h & a)))) | 0;
  t = (e + (((b >>> 6) | (b << 26)) ^ ((b >>> 11) | (b << 21)) ^ ((b >>> 25) | (b << 7))) + ((b & c) ^ (~b & d)) + -1933114872 + w[59]) | 0; a = (a + t) | 0; e = (t + ((((f >>> 2) | (f << 30)) ^ ((f >>> 13) | (f << 19)) ^ ((f >>> 22) | (f << 10))) + ((f & g) ^ (f & h) ^ (g & h)))) | 0;
  t = (d + (((a >>> 6) | (a << 26)) ^ ((a >>> 11) | (a << 21)) ^ ((a >>> 25) | (a << 7))) + ((a & b) ^ (~a & c)) + -1866530822 + w[60]) | 0; h = (h + t) | 0; d = (t + ((((e >>> 2) | (e << 30)) ^ ((e >>> 13) | (e << 19)) ^ ((e >>> 22) | (e << 10))) + ((e & f) ^ (e & g) ^ (f & g)))) | 0;
  t = (c + (((h >>> 6) | (h << 26)) ^ ((h >>> 11) | (h << 21)) ^ ((h >>> 25) | (h << 7))) + ((h & a) ^ (~h & b)) + -1538233109 + w[61]) | 0; g = (g + t) | 0; c = (t + ((((d >>> 2) | (d << 30)) ^ ((d >>> 13) | (d << 19)) ^ ((d >>> 22) | (d << 10))) + ((d & e) ^ (d & f) ^ (e & f)))) | 0;
  t = (b + (((g >>> 6) | (g << 26)) ^ ((g >>> 11) | (g << 21)) ^ ((g >>> 25) | (g << 7))) + ((g & h) ^ (~g & a)) + -1090935817 + w[62]) | 0; f = (f + t) | 0; b = (t + ((((c >>> 2) | (c << 30)) ^ ((c >>> 13) | (c << 19)) ^ ((c >>> 22) | (c << 10))) + ((c & d) ^ (c & e) ^ (d & e)))) | 0;
  t = (a + (((f >>> 6) | (f << 26)) ^ ((f >>> 11) | (f << 21)) ^ ((f >>> 25) | (f << 7))) + ((f & g) ^ (~f & h)) + -965641998 + w[63]) | 0; e = (e + t) | 0; a = (t + ((((b >>> 2) | (b << 30)) ^ ((b >>> 13) | (b << 19)) ^ ((b >>> 22) | (b << 10))) + ((b & c) ^ (b & d) ^ (c & d)))) | 0;
  H[0] = (H[0] + a) | 0; H[1] = (H[1] + b) | 0; H[2] = (H[2] + c) | 0; H[3] = (H[3] + d) | 0;
  H[4] = (H[4] + e) | 0; H[5] = (H[5] + f) | 0; H[6] = (H[6] + g) | 0; H[7] = (H[7] + h) | 0;
}
Sha256.prototype.update = function (data) {
  var n = B.len(data), i = 0, buf = this.buf, isStr = typeof data === "string";
  this.total += n;
  if (buf.length) {
    while (buf.length < 64 && i < n) { buf.push(isStr ? data.charCodeAt(i) : data[i]); i++; }
    if (buf.length === 64) { sha256Block(this.h, this.w, buf, 0, false); this.buf = buf = []; }
  }
  while (i + 64 <= n) { sha256Block(this.h, this.w, data, i, isStr); i += 64; }
  while (i < n) { buf.push(isStr ? data.charCodeAt(i) : data[i]); i++; }
  return this;
};
Sha256.prototype.digestArray = function () {
  var buf = this.buf.slice(0), bits = this.total * 8, i, out = [];
  buf.push(0x80);
  while (buf.length % 64 !== 56) { buf.push(0); }
  var hi = Math.floor(bits / 4294967296), lo = bits >>> 0;
  buf.push((hi >>> 24) & 255, (hi >>> 16) & 255, (hi >>> 8) & 255, hi & 255, (lo >>> 24) & 255, (lo >>> 16) & 255, (lo >>> 8) & 255, lo & 255);
  for (i = 0; i < buf.length; i += 64) { sha256Block(this.h, this.w, buf, i, false); }
  for (i = 0; i < 8; i++) { out.push((this.h[i] >>> 24) & 255, (this.h[i] >>> 16) & 255, (this.h[i] >>> 8) & 255, this.h[i] & 255); }
  return out;
};
Sha256.prototype.digest = function () { return B.fromArray(this.digestArray()); };
function sha256(data) { return new Sha256().update(data).digest(); }
function sha256Hex(data) { return toHex(sha256(data)); }

// ---------------------------------------------------------------- SHA-512 (for Ed25519), 32-bit halves
var K512 = [0x428a2f98, 0xd728ae22, 0x71374491, 0x23ef65cd, 0xb5c0fbcf, 0xec4d3b2f, 0xe9b5dba5, 0x8189dbbc,
  0x3956c25b, 0xf348b538, 0x59f111f1, 0xb605d019, 0x923f82a4, 0xaf194f9b, 0xab1c5ed5, 0xda6d8118,
  0xd807aa98, 0xa3030242, 0x12835b01, 0x45706fbe, 0x243185be, 0x4ee4b28c, 0x550c7dc3, 0xd5ffb4e2,
  0x72be5d74, 0xf27b896f, 0x80deb1fe, 0x3b1696b1, 0x9bdc06a7, 0x25c71235, 0xc19bf174, 0xcf692694,
  0xe49b69c1, 0x9ef14ad2, 0xefbe4786, 0x384f25e3, 0x0fc19dc6, 0x8b8cd5b5, 0x240ca1cc, 0x77ac9c65,
  0x2de92c6f, 0x592b0275, 0x4a7484aa, 0x6ea6e483, 0x5cb0a9dc, 0xbd41fbd4, 0x76f988da, 0x831153b5,
  0x983e5152, 0xee66dfab, 0xa831c66d, 0x2db43210, 0xb00327c8, 0x98fb213f, 0xbf597fc7, 0xbeef0ee4,
  0xc6e00bf3, 0x3da88fc2, 0xd5a79147, 0x930aa725, 0x06ca6351, 0xe003826f, 0x14292967, 0x0a0e6e70,
  0x27b70a85, 0x46d22ffc, 0x2e1b2138, 0x5c26c926, 0x4d2c6dfc, 0x5ac42aed, 0x53380d13, 0x9d95b3df,
  0x650a7354, 0x8baf63de, 0x766a0abb, 0x3c77b2a8, 0x81c2c92e, 0x47edaee6, 0x92722c85, 0x1482353b,
  0xa2bfe8a1, 0x4cf10364, 0xa81a664b, 0xbc423001, 0xc24b8b70, 0xd0f89791, 0xc76c51a3, 0x0654be30,
  0xd192e819, 0xd6ef5218, 0xd6990624, 0x5565a910, 0xf40e3585, 0x5771202a, 0x106aa070, 0x32bbd1b8,
  0x19a4c116, 0xb8d2d0c8, 0x1e376c08, 0x5141ab53, 0x2748774c, 0xdf8eeb99, 0x34b0bcb5, 0xe19b48a8,
  0x391c0cb3, 0xc5c95a63, 0x4ed8aa4a, 0xe3418acb, 0x5b9cca4f, 0x7763e373, 0x682e6ff3, 0xd6b2b8a3,
  0x748f82ee, 0x5defb2fc, 0x78a5636f, 0x43172f60, 0x84c87814, 0xa1f0ab72, 0x8cc70208, 0x1a6439ec,
  0x90befffa, 0x23631e28, 0xa4506ceb, 0xde82bde9, 0xbef9a3f7, 0xb2c67915, 0xc67178f2, 0xe372532b,
  0xca273ece, 0xea26619c, 0xd186b8c7, 0x21c0c207, 0xeada7dd6, 0xcde0eb1e, 0xf57d4f7f, 0xee6ed178,
  0x06f067aa, 0x72176fba, 0x0a637dc5, 0xa2c898a6, 0x113f9804, 0xbef90dae, 0x1b710b35, 0x131c471b,
  0x28db77f5, 0x23047d84, 0x32caab7b, 0x40c72493, 0x3c9ebe0a, 0x15c9bebc, 0x431d67c4, 0x9c100d4c,
  0x4cc5d4be, 0xcb3e42b6, 0x597f299c, 0xfc657e2a, 0x5fcb6fab, 0x3ad6faec, 0x6c44198c, 0x4a475817];

// sha512 over a plain array of byte values; returns a plain array of 64.
function sha512Array(msg) {
  var H = [0x6a09e667, 0xf3bcc908, 0xbb67ae85, 0x84caa73b, 0x3c6ef372, 0xfe94f82b, 0xa54ff53a, 0x5f1d36f1,
    0x510e527f, 0xade682d1, 0x9b05688c, 0x2b3e6c1f, 0x1f83d9ab, 0xfb41bd6b, 0x5be0cd19, 0x137e2179];
  var m = msg.slice(0), len = msg.length, i, j, t, W = [];
  m.push(0x80);
  while (m.length % 128 !== 112) { m.push(0); }
  for (i = 0; i < 8; i++) { m.push(0); }
  var bits = len * 8, hi = Math.floor(bits / 4294967296), lo = bits >>> 0;
  m.push((hi >>> 24) & 255, (hi >>> 16) & 255, (hi >>> 8) & 255, hi & 255, (lo >>> 24) & 255, (lo >>> 16) & 255, (lo >>> 8) & 255, lo & 255);
  function add(ah, al, bh, bl) { var l = (al >>> 0) + (bl >>> 0); return [(ah + bh + Math.floor(l / 4294967296)) | 0, l | 0]; }
  function rotr(h, l, n) {
    if (n < 32) { return [(h >>> n) | (l << (32 - n)), (l >>> n) | (h << (32 - n))]; }
    n -= 32; return n === 0 ? [l, h] : [(l >>> n) | (h << (32 - n)), (h >>> n) | (l << (32 - n))];
  }
  function shr(h, l, n) { return n < 32 ? [h >>> n, (l >>> n) | (h << (32 - n))] : [0, h >>> (n - 32)]; }
  function x3(a, b, c) { return [a[0] ^ b[0] ^ c[0], a[1] ^ b[1] ^ c[1]]; }
  for (i = 0; i < m.length; i += 128) {
    for (j = 0; j < 16; j++) {
      var o = i + j * 8;
      W[j] = [(m[o] << 24) | (m[o + 1] << 16) | (m[o + 2] << 8) | m[o + 3], (m[o + 4] << 24) | (m[o + 5] << 16) | (m[o + 6] << 8) | m[o + 7]];
    }
    for (j = 16; j < 80; j++) {
      var a15 = W[j - 15], a2 = W[j - 2];
      var s0 = x3(rotr(a15[0], a15[1], 1), rotr(a15[0], a15[1], 8), shr(a15[0], a15[1], 7));
      var s1 = x3(rotr(a2[0], a2[1], 19), rotr(a2[0], a2[1], 61), shr(a2[0], a2[1], 6));
      t = add(W[j - 16][0], W[j - 16][1], s0[0], s0[1]);
      t = add(t[0], t[1], W[j - 7][0], W[j - 7][1]);
      W[j] = add(t[0], t[1], s1[0], s1[1]);
    }
    var v = [];
    for (j = 0; j < 8; j++) { v.push([H[2 * j], H[2 * j + 1]]); }
    for (j = 0; j < 80; j++) {
      var a = v[0], b = v[1], c = v[2], d = v[3], e = v[4], f = v[5], g = v[6], h = v[7];
      var S1 = x3(rotr(e[0], e[1], 14), rotr(e[0], e[1], 18), rotr(e[0], e[1], 41));
      var ch = [(e[0] & f[0]) ^ (~e[0] & g[0]), (e[1] & f[1]) ^ (~e[1] & g[1])];
      t = add(h[0], h[1], S1[0], S1[1]);
      t = add(t[0], t[1], ch[0], ch[1]);
      t = add(t[0], t[1], K512[2 * j], K512[2 * j + 1]);
      var t1 = add(t[0], t[1], W[j][0], W[j][1]);
      var S0 = x3(rotr(a[0], a[1], 28), rotr(a[0], a[1], 34), rotr(a[0], a[1], 39));
      var mj = [(a[0] & b[0]) ^ (a[0] & c[0]) ^ (b[0] & c[0]), (a[1] & b[1]) ^ (a[1] & c[1]) ^ (b[1] & c[1])];
      var t2 = add(S0[0], S0[1], mj[0], mj[1]);
      v = [add(t1[0], t1[1], t2[0], t2[1]), a, b, c, add(d[0], d[1], t1[0], t1[1]), e, f, g];
    }
    for (j = 0; j < 8; j++) { t = add(H[2 * j], H[2 * j + 1], v[j][0], v[j][1]); H[2 * j] = t[0]; H[2 * j + 1] = t[1]; }
  }
  var out = [];
  for (i = 0; i < 16; i++) { out.push((H[i] >>> 24) & 255, (H[i] >>> 16) & 255, (H[i] >>> 8) & 255, H[i] & 255); }
  return out;
}

function bytesToArray(b) { var a = [], n = B.len(b); for (var i = 0; i < n; i++) { a.push(B.at(b, i)); } return a; }

// ---------------------------------------------------------------- Ed25519 (TweetNaCl arithmetic, plain arrays)
function gf(init) { var r = [], i; for (i = 0; i < 16; i++) { r.push(init && i < init.length ? init[i] : 0); } return r; }
var gf0 = gf(), gf1 = gf([1]);
var ED_D = gf([0x78a3, 0x1359, 0x4dca, 0x75eb, 0xd8ab, 0x4141, 0x0a4d, 0x0070, 0xe898, 0x7779, 0x4079, 0x8cc7, 0xfe73, 0x2b6f, 0x6cee, 0x5203]);
var ED_D2 = gf([0xf159, 0x26b2, 0x9b94, 0xebd6, 0xb156, 0x8283, 0x149a, 0x00e0, 0xd130, 0xeef3, 0x80f2, 0x198e, 0xfce7, 0x56df, 0xd9dc, 0x2406]);
var ED_X = gf([0xd51a, 0x8f25, 0x2d60, 0xc956, 0xa7b2, 0x9525, 0xc760, 0x692c, 0xdc5c, 0xfdd6, 0xe231, 0xc0a4, 0x53fe, 0xcd6e, 0x36d3, 0x2169]);
var ED_Y = gf([0x6658, 0x6666, 0x6666, 0x6666, 0x6666, 0x6666, 0x6666, 0x6666, 0x6666, 0x6666, 0x6666, 0x6666, 0x6666, 0x6666, 0x6666, 0x6666]);
var ED_I = gf([0xa0b0, 0x4a0e, 0x1b27, 0xc4ee, 0xe478, 0xad2f, 0x1806, 0x2f43, 0xd7a7, 0x3dfb, 0x0099, 0x2b4d, 0xdf0b, 0x4fc1, 0x2480, 0x2b83]);
var ED_L = [0xed, 0xd3, 0xf5, 0x5c, 0x1a, 0x63, 0x12, 0x58, 0xd6, 0x9c, 0xf7, 0xa2, 0xde, 0xf9, 0xde, 0x14, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0x10];

function set25519(r, a) { for (var i = 0; i < 16; i++) { r[i] = a[i] | 0; } }
function car25519(o) {
  var i, v, c = 1;
  for (i = 0; i < 16; i++) { v = o[i] + c + 65535; c = Math.floor(v / 65536); o[i] = v - c * 65536; }
  o[0] += c - 1 + 37 * (c - 1);
}
function sel25519(p, q, b) {
  var t, c = ~(b - 1);
  for (var i = 0; i < 16; i++) { t = c & (p[i] ^ q[i]); p[i] ^= t; q[i] ^= t; }
}
function pack25519(o, n) {
  var i, j, b, m = gf(), t = gf();
  for (i = 0; i < 16; i++) { t[i] = n[i]; }
  car25519(t); car25519(t); car25519(t);
  for (j = 0; j < 2; j++) {
    m[0] = t[0] - 0xffed;
    for (i = 1; i < 15; i++) { m[i] = t[i] - 0xffff - ((m[i - 1] >> 16) & 1); m[i - 1] &= 0xffff; }
    m[15] = t[15] - 0x7fff - ((m[14] >> 16) & 1);
    b = (m[15] >> 16) & 1;
    m[14] &= 0xffff;
    sel25519(t, m, 1 - b);
  }
  for (i = 0; i < 16; i++) { o[2 * i] = t[i] & 0xff; o[2 * i + 1] = t[i] >> 8; }
}
function vn(x, xi, y, yi, n) { var i, d = 0; for (i = 0; i < n; i++) { d |= x[xi + i] ^ y[yi + i]; } return (1 & ((d - 1) >>> 8)) - 1; }
function neq25519(a, b) { var c = [], d = []; pack25519(c, a); pack25519(d, b); return vn(c, 0, d, 0, 32); }
function par25519(a) { var d = []; pack25519(d, a); return d[0] & 1; }
function unpack25519(o, n) { for (var i = 0; i < 16; i++) { o[i] = n[2 * i] + (n[2 * i + 1] << 8); } o[15] &= 0x7fff; }
function A(o, a, b) { for (var i = 0; i < 16; i++) { o[i] = a[i] + b[i]; } }
function Z(o, a, b) { for (var i = 0; i < 16; i++) { o[i] = a[i] - b[i]; } }
function M(o, a, b) {
  var t = [], i, j;
  for (i = 0; i < 31; i++) { t[i] = 0; }
  for (i = 0; i < 16; i++) { for (j = 0; j < 16; j++) { t[i + j] += a[i] * b[j]; } }
  for (i = 0; i < 15; i++) { t[i] += 38 * t[i + 16]; }
  for (i = 0; i < 16; i++) { o[i] = t[i]; }
  car25519(o); car25519(o);
}
function S(o, a) { M(o, a, a); }
function inv25519(o, i) {
  var c = gf(), a;
  for (a = 0; a < 16; a++) { c[a] = i[a]; }
  for (a = 253; a >= 0; a--) { S(c, c); if (a !== 2 && a !== 4) { M(c, c, i); } }
  for (a = 0; a < 16; a++) { o[a] = c[a]; }
}
function pow2523(o, i) {
  var c = gf(), a;
  for (a = 0; a < 16; a++) { c[a] = i[a]; }
  for (a = 250; a >= 0; a--) { S(c, c); if (a !== 1) { M(c, c, i); } }
  for (a = 0; a < 16; a++) { o[a] = c[a]; }
}
function edAdd(p, q) {
  var a = gf(), b = gf(), c = gf(), d = gf(), e = gf(), f = gf(), g = gf(), h = gf(), t = gf();
  Z(a, p[1], p[0]); Z(t, q[1], q[0]); M(a, a, t);
  A(b, p[0], p[1]); A(t, q[0], q[1]); M(b, b, t);
  M(c, p[3], q[3]); M(c, c, ED_D2);
  M(d, p[2], q[2]); A(d, d, d);
  Z(e, b, a); Z(f, d, c); A(g, d, c); A(h, b, a);
  M(p[0], e, f); M(p[1], h, g); M(p[2], g, f); M(p[3], e, h);
}
function cswap(p, q, b) { for (var i = 0; i < 4; i++) { sel25519(p[i], q[i], b); } }
function edPack(r, p) {
  var tx = gf(), ty = gf(), zi = gf();
  inv25519(zi, p[2]); M(tx, p[0], zi); M(ty, p[1], zi);
  pack25519(r, ty);
  r[31] ^= par25519(tx) << 7;
}
function scalarmult(p, q, s) {
  var b, i;
  set25519(p[0], gf0); set25519(p[1], gf1); set25519(p[2], gf1); set25519(p[3], gf0);
  for (i = 255; i >= 0; --i) {
    b = (s[(i / 8) | 0] >> (i & 7)) & 1;
    cswap(p, q, b); edAdd(q, p); edAdd(p, p); cswap(p, q, b);
  }
}
function scalarbase(p, s) {
  var q = [gf(), gf(), gf(), gf()];
  set25519(q[0], ED_X); set25519(q[1], ED_Y); set25519(q[2], gf1); M(q[3], ED_X, ED_Y);
  scalarmult(p, q, s);
}
function modL(r, x) {
  var carry, i, j, k;
  for (i = 63; i >= 32; --i) {
    carry = 0;
    for (j = i - 32, k = i - 12; j < k; ++j) {
      x[j] += carry - 16 * x[i] * ED_L[j - (i - 32)];
      carry = Math.floor((x[j] + 128) / 256);
      x[j] -= carry * 256;
    }
    x[j] += carry; x[i] = 0;
  }
  carry = 0;
  for (j = 0; j < 32; j++) { x[j] += carry - (x[31] >> 4) * ED_L[j]; carry = x[j] >> 8; x[j] &= 255; }
  for (j = 0; j < 32; j++) { x[j] -= carry * ED_L[j]; }
  for (i = 0; i < 32; i++) { x[i + 1] += x[i] >> 8; r[i] = x[i] & 255; }
}
function reduce(r) { var x = [], i; for (i = 0; i < 64; i++) { x[i] = r[i]; } for (i = 0; i < 64; i++) { r[i] = 0; } modL(r, x); }
function unpackneg(r, p) {
  var t = gf(), chk = gf(), num = gf(), den = gf(), den2 = gf(), den4 = gf(), den6 = gf();
  set25519(r[2], gf1);
  unpack25519(r[1], p);
  S(num, r[1]); M(den, num, ED_D); Z(num, num, r[2]); A(den, r[2], den);
  S(den2, den); S(den4, den2); M(den6, den4, den2); M(t, den6, num); M(t, t, den);
  pow2523(t, t); M(t, t, num); M(t, t, den); M(t, t, den); M(r[0], t, den);
  S(chk, r[0]); M(chk, chk, den);
  if (neq25519(chk, num)) { M(r[0], r[0], ED_I); }
  S(chk, r[0]); M(chk, chk, den);
  if (neq25519(chk, num)) { return -1; }
  if (par25519(r[0]) === (p[31] >> 7)) { Z(r[0], gf0, r[0]); }
  M(r[3], r[0], r[1]);
  return 0;
}
function edExpand(seed) {
  var d = sha512Array(seed);
  d[0] &= 248; d[31] &= 127; d[31] |= 64;
  return d;
}
function ed25519PublicKey(seedB) {
  var seed = bytesToArray(seedB);
  if (seed.length !== 32) { throw new WerkError("an Ed25519 secret key is 32 bytes (64 hex digits)"); }
  var d = edExpand(seed), p = [gf(), gf(), gf(), gf()], pk = [];
  scalarbase(p, d.slice(0, 32)); edPack(pk, p);
  return B.fromArray(pk);
}
function ed25519Sign(seedB, msgB) {
  var seed = bytesToArray(seedB), msg = bytesToArray(msgB), i, j;
  var d = edExpand(seed), p = [gf(), gf(), gf(), gf()], pk = [];
  scalarbase(p, d.slice(0, 32)); edPack(pk, p);
  var r = sha512Array(d.slice(32, 64).concat(msg));
  reduce(r);
  var R = [];
  p = [gf(), gf(), gf(), gf()];
  scalarbase(p, r); edPack(R, p);
  var h = sha512Array(R.concat(pk).concat(msg));
  reduce(h);
  var x = [];
  for (i = 0; i < 64; i++) { x[i] = 0; }
  for (i = 0; i < 32; i++) { x[i] = r[i]; }
  for (i = 0; i < 32; i++) { for (j = 0; j < 32; j++) { x[i + j] += h[i] * d[j]; } }
  var s = [];
  modL(s, x);
  return B.fromArray(R.concat(s.slice(0, 32)));
}
function ed25519Verify(pubB, msgB, sigB) {
  var pub = bytesToArray(pubB), sig = bytesToArray(sigB), msg = bytesToArray(msgB), i;
  if (pub.length !== 32 || sig.length !== 64) { return false; }
  // s must be < L (RFC 8032 section 5.1.7): compare little-endian.
  for (i = 31; i >= 0; i--) {
    if (sig[32 + i] < ED_L[i]) { break; }
    if (sig[32 + i] > ED_L[i]) { return false; }
    if (i === 0) { return false; }
  }
  var q = [gf(), gf(), gf(), gf()], p = [gf(), gf(), gf(), gf()];
  if (unpackneg(q, pub)) { return false; }
  var h = sha512Array(sig.slice(0, 32).concat(pub).concat(msg));
  reduce(h);
  scalarmult(p, q, h);
  scalarbase(q, sig.slice(32, 64));
  edAdd(p, q);
  var t = [];
  edPack(t, p);
  return vn(sig, 0, t, 0, 32) === 0;
}

// ---------------------------------------------------------------- CRC-32
var CRC_TABLE = null, CRC_T1 = null, CRC_T2 = null, CRC_T3 = null;
// CRC-32 (MINI-SPECS section 6), slicing-by-4: four bytes per step through
// four tables, a quarter of the loop iterations a byte-wise table needs.
function crc32(data, start) {
  var c, n, k, i, len, T, T1, T2, T3, end;
  if (!CRC_TABLE) {
    CRC_TABLE = []; CRC_T1 = []; CRC_T2 = []; CRC_T3 = [];
    for (n = 0; n < 256; n++) { c = n; for (k = 0; k < 8; k++) { c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1); } CRC_TABLE[n] = c >>> 0; }
    for (n = 0; n < 256; n++) {
      c = CRC_TABLE[n];
      c = CRC_TABLE[c & 255] ^ (c >>> 8); CRC_T1[n] = c >>> 0;
      c = CRC_TABLE[c & 255] ^ (c >>> 8); CRC_T2[n] = c >>> 0;
      c = CRC_TABLE[c & 255] ^ (c >>> 8); CRC_T3[n] = c >>> 0;
    }
  }
  T = CRC_TABLE; T1 = CRC_T1; T2 = CRC_T2; T3 = CRC_T3;
  c = ((start === undefined ? 0 : start) ^ 0xFFFFFFFF) | 0;
  len = B.len(data); end = len - (len % 4); i = 0;
  if (typeof data === "string") {
    for (; i < end; i += 4) {
      c ^= data.charCodeAt(i) | (data.charCodeAt(i + 1) << 8) | (data.charCodeAt(i + 2) << 16) | (data.charCodeAt(i + 3) << 24);
      c = T3[c & 255] ^ T2[(c >>> 8) & 255] ^ T1[(c >>> 16) & 255] ^ T[c >>> 24];
    }
    for (; i < len; i++) { c = T[(c ^ data.charCodeAt(i)) & 255] ^ (c >>> 8); }
  } else {
    for (; i < end; i += 4) {
      c ^= data[i] | (data[i + 1] << 8) | (data[i + 2] << 16) | (data[i + 3] << 24);
      c = T3[c & 255] ^ T2[(c >>> 8) & 255] ^ T1[(c >>> 16) & 255] ^ T[c >>> 24];
    }
    for (; i < len; i++) { c = T[(c ^ data[i]) & 255] ^ (c >>> 8); }
  }
  return (c ^ 0xFFFFFFFF) >>> 0;
}

// ---------------------------------------------------------------- DEFLATE decode (MINI-SPECS section 7.1)
// Output is linear in both builds. Binary strings (ES3): literals collect in a
// small array flushed through String.fromCharCode, back-references are copied
// as SUBSTRINGS of a string window, and the parts are joined in bounded
// batches -- ExtendScript's array push and per-byte string growth are
// super-linear, its substring and join are native. (The approach of the Adobe
// plug-ins' werk_inflate.jsx, folded in.) Uint8Array: one growing buffer,
// doubled when full, back-references copied byte by byte.
function inflateRaw(data, limit) {
  if (limit === undefined || limit === null) { limit = 2147483647; }
  var isStr = typeof data === "string", out = B.inflateSink(limit);
  var pos = 0, bitbuf = 0, bitcnt = 0, n = B.len(data);
  function next() {
    if (pos >= n) { throw new WerkError("deflate stream ends early"); }
    return isStr ? data.charCodeAt(pos++) : data[pos++];
  }
  function bits(need) {
    if (need === 0) { return 0; }
    while (bitcnt < need) { bitbuf |= next() << bitcnt; bitcnt += 8; }
    var v = bitbuf & ((1 << need) - 1);
    bitbuf >>>= need; bitcnt -= need;
    return v;
  }
  function construct(lengths, num) {
    var count = [], offs = [], symbol = [], i, len;
    for (len = 0; len <= 15; len++) { count.push(0); }
    for (i = 0; i < num; i++) { count[lengths[i] || 0]++; }
    count[0] = 0;
    offs[1] = 0;
    for (len = 1; len < 15; len++) { offs[len + 1] = offs[len] + count[len]; }
    for (i = 0; i < num; i++) { symbol.push(0); }
    for (i = 0; i < num; i++) { if (lengths[i]) { symbol[offs[lengths[i]]++] = i; } }
    return { count: count, symbol: symbol };
  }
  function decode(h) {
    var code = 0, first = 0, index = 0, len, count, cnt = h.count;
    for (len = 1; len <= 15; len++) {
      if (bitcnt === 0) { bitbuf = next(); bitcnt = 8; }
      code |= bitbuf & 1; bitbuf >>>= 1; bitcnt--;
      count = cnt[len];
      if (code - count < first) { return h.symbol[index + (code - first)]; }
      index += count; first += count; first <<= 1; code <<= 1;
    }
    throw new WerkError("deflate: bad Huffman code");
  }
  var LBASE = [3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258];
  var LEXT = [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0];
  var DBASE = [1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025, 1537, 2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577];
  var DEXT = [0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13];
  function codes(lc, dc) {
    var sym, len, dist;
    while (true) {
      sym = decode(lc);
      if (sym < 256) { out.lit8(sym); }
      else if (sym === 256) { return; }
      else {
        sym -= 257;
        if (sym >= 29) { throw new WerkError("deflate: bad length symbol"); }
        len = LBASE[sym] + bits(LEXT[sym]);
        sym = decode(dc);
        if (sym >= 30) { throw new WerkError("deflate: bad distance symbol"); }
        dist = DBASE[sym] + bits(DEXT[sym]);
        out.copy(dist, len);
      }
    }
  }
  var fixedL = null, fixedD = null, last, type, i;
  do {
    last = bits(1); type = bits(2);
    if (type === 0) {
      bitbuf = 0; bitcnt = 0;
      if (pos + 4 > n) { throw new WerkError("deflate: stored block header truncated"); }
      var len = B.at(data, pos) | (B.at(data, pos + 1) << 8), nlen = B.at(data, pos + 2) | (B.at(data, pos + 3) << 8);
      pos += 4;
      if (len !== (~nlen & 0xffff)) { throw new WerkError("deflate: stored block length check fails"); }
      if (pos + len > n) { throw new WerkError("deflate: stored block truncated"); }
      out.stored(data, pos, pos + len);
      pos += len;
    } else if (type === 1) {
      if (!fixedL) {
        var l = [];
        for (i = 0; i < 144; i++) { l[i] = 8; }
        for (; i < 256; i++) { l[i] = 9; }
        for (; i < 280; i++) { l[i] = 7; }
        for (; i < 288; i++) { l[i] = 8; }
        fixedL = construct(l, 288);
        l = [];
        for (i = 0; i < 30; i++) { l[i] = 5; }
        fixedD = construct(l, 30);
      }
      codes(fixedL, fixedD);
    } else if (type === 2) {
      var nlenc = bits(5) + 257, ndist = bits(5) + 1, ncode = bits(4) + 4;
      var ORDER = [16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15];
      var lengths = [], idx;
      for (i = 0; i < 19; i++) { lengths[i] = 0; }
      for (i = 0; i < ncode; i++) { lengths[ORDER[i]] = bits(3); }
      var lencode = construct(lengths, 19);
      lengths = [];
      idx = 0;
      while (idx < nlenc + ndist) {
        var sym = decode(lencode), rep, val;
        if (sym < 16) { lengths[idx++] = sym; }
        else {
          if (sym === 16) { if (idx === 0) { throw new WerkError("deflate: repeat with no length"); } val = lengths[idx - 1]; rep = 3 + bits(2); }
          else if (sym === 17) { val = 0; rep = 3 + bits(3); }
          else { val = 0; rep = 11 + bits(7); }
          if (idx + rep > nlenc + ndist) { throw new WerkError("deflate: too many lengths"); }
          while (rep--) { lengths[idx++] = val; }
        }
      }
      codes(construct(lengths.slice(0, nlenc), nlenc), construct(lengths.slice(nlenc), ndist));
    } else { throw new WerkError("deflate: invalid block type 3"); }
  } while (!last);
  return out.done();
}
// ---------------------------------------------------------------- integers in bytes
function u16(b, o) { return B.at(b, o) | (B.at(b, o + 1) << 8); }
function u32(b, o) { return (B.at(b, o) | (B.at(b, o + 1) << 8) | (B.at(b, o + 2) << 16)) + B.at(b, o + 3) * 16777216; }
function put16(bl, v) { bl.put8(v & 255); bl.put8((v >>> 8) & 255); }
function put32(bl, v) { bl.put8(v & 255); bl.put8((v >>> 8) & 255); bl.put8((v >>> 16) & 255); bl.put8((v >>> 24) & 255); }
function bytesEqAscii(b, o, s) { for (var i = 0; i < s.length; i++) { if (B.at(b, o + i) !== s.charCodeAt(i)) { return false; } } return true; }

// ---------------------------------------------------------------- containers
var ZIP64_REMEDY = "werk does not use zip64: a package past the zip32 ceiling (4 GiB, 65534 entries) is carried in DIRECTORY form, which is the same format";

// MINI-SPECS 5.4: relative, forward slashes, no `..` segment, no drive letter,
// no leading slash (and no NUL).
function isUnsafePath(p) {
  return !p || p.charAt(0) === "/" || p.indexOf("\\") >= 0 || p.indexOf("\u0000") >= 0 || contains(p.split("/"), "..") || (p.length > 1 && p.charAt(1) === ":");
}
function unsafeMsg(tag, p) {
  return tag + ": files[] path " + p + " is not a package path (MINI-SPECS 5.4: relative, forward slashes, no `..` segment, no drive letter); this version is unusable";
}
function rejectUnsafe(p) {
  if (isUnsafePath(p)) {
    throw new WerkError("refusing an unsafe package path: " + p, "unsafe-path");
  }
}

function ZipContainer(data) {
  this.form = "zip";
  this.data = data;
  this.entries = {};
  this.order = [];
  var d = data, n = B.len(d), i, eocd = -1;
  if (n < 22) { throw refusal("bad-container", "file is too short to be a zip"); }
  for (i = n - 22; i >= Math.max(0, n - 22 - 65535); i--) {
    if (B.at(d, i) === 0x50 && B.at(d, i + 1) === 0x4B && B.at(d, i + 2) === 5 && B.at(d, i + 3) === 6) {
      if (i + 22 + u16(d, i + 20) === n) { eocd = i; break; }
    }
  }
  if (eocd < 0) { throw refusal("bad-container", "no end-of-central-directory record: not a zip"); }
  var disks = u16(d, eocd + 8), count = u16(d, eocd + 10), cdSize = u32(d, eocd + 12), cdOff = u32(d, eocd + 16);
  var locator = eocd >= 20 && B.at(d, eocd - 20) === 0x50 && B.at(d, eocd - 19) === 0x4B && B.at(d, eocd - 18) === 6 && B.at(d, eocd - 17) === 7;
  if (cdSize === 0xFFFFFFFF || cdOff === 0xFFFFFFFF || count === 0xFFFF || disks === 0xFFFF || locator) {
    throw refusal("zip64-unsupported", "zip64 container. " + ZIP64_REMEDY);
  }
  var p = cdOff;
  for (i = 0; i < count; i++) {
    if (p + 46 > n || !(B.at(d, p) === 0x50 && B.at(d, p + 1) === 0x4B && B.at(d, p + 2) === 1 && B.at(d, p + 3) === 2)) {
      throw refusal("bad-container", "bad central directory signature at " + p);
    }
    var flags = u16(d, p + 8), method = u16(d, p + 10), crc = u32(d, p + 16), comp = u32(d, p + 20), uncomp = u32(d, p + 24);
    var nlen = u16(d, p + 28), mlen = u16(d, p + 30), klen = u16(d, p + 32), lho = u32(d, p + 42);
    var name;
    if (p + 46 + nlen > n) { throw refusal("bad-container", "a central directory name runs past the end of the file"); }
    // MINI-SPECS 5.4 rule 3: lossy UTF-8 -- a damaged name matches no
    // manifest path (file-missing), it never makes the directory malformed.
    name = utf8DecodeLossy(B.slice(d, p + 46, p + 46 + nlen));
    if (comp === 0xFFFFFFFF || uncomp === 0xFFFFFFFF || lho === 0xFFFFFFFF) {
      throw refusal("zip64-unsupported", "entry " + name + " carries a zip64 sentinel. " + ZIP64_REMEDY);
    }
    if (flags & 8) { throw refusal("bad-container", "entry " + name + " sets flag bit 3 (data descriptor)"); }
    // Two records, one name: which bytes ARE that file cannot be decided, and
    // readers that pick different ones disagree. Refused whole (exit 2).
    if (hasOwn(this.entries, "/" + name)) { throw refusal("bad-container", "the zip holds two entries named " + name + "; which bytes are that file cannot be decided, so the container is refused"); }
    this.entries["/" + name] = { method: method, comp: comp, uncomp: uncomp, lho: lho, flags: flags, crc: crc };
    this.order.push(name);
    p += 46 + nlen + mlen + klen;
  }
}
ZipContainer.prototype.names = function () {
  var o = [], i;
  for (i = 0; i < this.order.length; i++) { if (!endsWith(this.order[i], "/")) { o.push(this.order[i]); } }
  return o;
};
ZipContainer.prototype.has = function (path) { return hasOwn(this.entries, "/" + path); };
ZipContainer.prototype.read = function (path) {
  if (!hasOwn(this.entries, "/" + path)) { var e0 = new WerkError(path + " is not in the container", "file-missing"); e0.missing = true; throw e0; }
  var e = this.entries["/" + path], d = this.data;
  if (e.flags & 1) { throw new WerkError("entry " + path + " is encrypted", "zip-entry-unsupported"); }
  if (e.method !== 0 && e.method !== 8) { throw new WerkError("entry " + path + " uses compression method " + e.method, "zip-entry-unsupported"); }
  if (!bytesEqAscii(d, e.lho, "PK\u0003\u0004")) { throw new WerkError("bad local header signature for " + path, "zip-entry-invalid"); }
  var start = e.lho + 30 + u16(d, e.lho + 26) + u16(d, e.lho + 28);
  if (start + e.comp > B.len(d)) { throw new WerkError("entry " + path + " runs past the end of the file", "zip-entry-invalid"); }
  var raw = B.slice(d, start, start + e.comp);
  if (e.method === 0) { return raw; }
  var out;
  try { out = inflateRaw(raw, e.uncomp); } catch (x) { throw new WerkError("entry " + path + ": deflate stream does not decode: " + x.message, "zip-entry-invalid"); }
  if (B.len(out) !== e.uncomp) { throw new WerkError("entry " + path + " does not inflate to the declared size", "zip-entry-invalid"); }
  if (crc32(out) !== e.crc) { throw new WerkError("entry " + path + " inflates to bytes whose CRC-32 disagrees", "zip-entry-invalid"); }
  return out;
};
ZipContainer.prototype.head = function (path, k) { return B.slice(this.read(path), 0, k); };

function DirContainer(io, root) { this.form = "directory"; this.io = io; this.root = root; }
DirContainer.prototype.full = function (path) { rejectUnsafe(path); return this.io.join(this.root, path); };
DirContainer.prototype.names = function () { return sortUtf8(this.io.listFiles(this.root)); };
DirContainer.prototype.has = function (path) { return this.io.isFile(this.full(path)); };
DirContainer.prototype.read = function (path) {
  var f = this.full(path);
  if (!this.io.isFile(f)) { var e = new WerkError(path + " is not in the container", "file-missing"); e.missing = true; throw e; }
  return this.io.read(f);
};
DirContainer.prototype.head = function (path, k) { return this.io.readHead(this.full(path), k); };

function openContainer(io, path) {
  if (io.isDir(path)) { return new DirContainer(io, path); }
  if (!io.isFile(path)) { throw refusal("bad-container", path + " is neither a file nor a directory"); }
  return new ZipContainer(io.read(path));
}

function dosDateTime(created) {
  var m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})/.exec(created || "");
  if (!m) { throw new WerkError("created must be RFC 3339 UTC, e.g. 2026-11-07T12:00:00Z"); }
  var y = parseInt(m[1], 10), mo = parseInt(m[2], 10), d = parseInt(m[3], 10);
  var h = parseInt(m[4], 10), mi = parseInt(m[5], 10), s = parseInt(m[6], 10);
  if (y < 1980) { y = 1980; mo = 1; d = 1; h = 0; mi = 0; s = 0; }
  return [(h << 11) | (mi << 5) | Math.floor(s / 2), ((y - 1980) << 9) | (mo << 5) | d];
}

// The exact zip every libs/ writer emits (see the Python twin, ZipWriter).
function ZipWriter(sink, created) {
  var td = dosDateTime(created);
  this.t = td[0]; this.d = td[1]; this.sink = sink; this.central = []; this.pos = 0; this.count = 0;
}
ZipWriter.prototype.add = function (name, data, crc) {
  var nb = utf8Encode(name), n = B.len(data), h = B.builder(), c = B.builder();
  if (crc === undefined || crc === null) { crc = crc32(data); }
  if (n >= 0xFFFFFFFF || this.pos + 30 + B.len(nb) + n >= 0xFFFFFFFF) { throw new WerkError("the zip form ends below 4 GiB; write this package in directory form"); }
  put32(h, 0x04034B50); put16(h, 20); put16(h, 0x0800); put16(h, 0); put16(h, this.t); put16(h, this.d);
  put32(h, crc); put32(h, n); put32(h, n); put16(h, B.len(nb)); put16(h, 0); h.bytes(nb);
  put32(c, 0x02014B50); put16(c, 20); put16(c, 20); put16(c, 0x0800); put16(c, 0); put16(c, this.t); put16(c, this.d);
  put32(c, crc); put32(c, n); put32(c, n); put16(c, B.len(nb)); put16(c, 0); put16(c, 0); put16(c, 0); put16(c, 0);
  put32(c, 0); put32(c, this.pos); c.bytes(nb);
  this.central.push(c.done());
  var hb = h.done();
  this.sink.write(hb); this.sink.write(data);
  this.pos += B.len(hb) + n; this.count++;
};
ZipWriter.prototype.close = function () {
  if (this.count > 65534) { throw new WerkError("more than 65534 entries; write this package in directory form"); }
  var cd = B.concat(this.central), e = B.builder();
  this.sink.write(cd);
  put32(e, 0x06054B50); put16(e, 0); put16(e, 0); put16(e, this.count); put16(e, this.count);
  put32(e, B.len(cd)); put32(e, this.pos); put16(e, 0);
  this.sink.write(e.done());
};

function physicalOrder(paths, entryOrder) {
  var left = sortUtf8(paths), placed = {}, i, j, pat;
  for (i = 0; i < entryOrder.length; i++) {
    pat = entryOrder[i];
    if (!endsWith(pat, "/") && contains(left, pat) && !hasOwn(placed, "/" + pat)) { placed["/" + pat] = i; }
  }
  for (i = 0; i < entryOrder.length; i++) {
    pat = entryOrder[i];
    if (endsWith(pat, "/")) {
      for (j = 0; j < left.length; j++) { if (!hasOwn(placed, "/" + left[j]) && startsWith(left[j], pat)) { placed["/" + left[j]] = i; } }
    }
  }
  var listed = [], rest = [];
  for (i = 0; i < left.length; i++) { if (hasOwn(placed, "/" + left[i])) { listed.push(left[i]); } else { rest.push(left[i]); } }
  listed.sort(function (a, b) { var d = placed["/" + a] - placed["/" + b]; return d !== 0 ? d : compareUtf8(a, b); });
  var order = listed.concat(rest), k = indexOf(order, MANIFEST);
  if (k >= 0) { order.splice(k, 1); order.unshift(MANIFEST); }
  return order;
}

// ---------------------------------------------------------------- envelopes (ENVELOPE.layout.txt section 7)
var MAGIC_KIND = { WKFF: "core.field.flow", WKRP: "core.pose.rest", WKAC: "core.anim.clip", WKSK: "core.skeleton",
  WKEM: "core.embedding", WKPC: "core.geom.points", WKGS: "core.geom.gsplat" };
function isMagicTail(c) { return (c >= 65 && c <= 90) || (c >= 48 && c <= 57); }
function isEnvelopeMagic(b) { return B.len(b) >= 4 && B.at(b, 0) === 0x57 && B.at(b, 1) === 0x4B && isMagicTail(B.at(b, 2)) && isMagicTail(B.at(b, 3)); }

function mpDecode(b, start, end) {
  var o = start;
  function be(n) { var v = 0; for (var i = 0; i < n; i++) { v = v * 256 + B.at(b, o + i); } o += n; return v; }
  function sbe(n) { var v = be(n), lim = Math.pow(2, 8 * n); return v >= lim / 2 ? v - lim : v; }
  function f32() { var x = be(4), s = x >>> 31 ? -1 : 1, e = (x >>> 23) & 255, m = x & 0x7FFFFF; if (e === 255) { return m ? NaN : s * Infinity; } return e === 0 ? s * m * Math.pow(2, -149) : s * (1 + m / 8388608) * Math.pow(2, e - 127); }
  function f64() { var hi = be(4), lo = be(4), s = hi >>> 31 ? -1 : 1, e = (hi >>> 20) & 2047, m = (hi & 0xFFFFF) * 4294967296 + lo; if (e === 2047) { return m ? NaN : s * Infinity; } return e === 0 ? s * m * Math.pow(2, -1074) : s * (1 + m / 4503599627370496) * Math.pow(2, e - 1023); }
  function rs(n) { var s = utf8Decode(B.slice(b, o, o + n)); o += n; return s; }
  function seq(n, isMap) {
    var out = isMap ? {} : [], i, k;
    for (i = 0; i < n; i++) {
      if (isMap) { k = read(); if (typeof k !== "string") { throw new WerkError("werk header map keys must be strings"); } out[k] = read(); }
      else { out.push(read()); }
    }
    return out;
  }
  function read() {
    if (o >= end) { throw new WerkError("MessagePack header runs past its length"); }
    var c = B.at(b, o++);
    if (c === 0xC1 || c === 0xC7 || c === 0xC8 || c === 0xC9 || (c >= 0xD4 && c <= 0xD8)) { throw new WerkError("format byte banned in werk headers"); }
    if (c <= 0x7F) { return c; }
    if (c >= 0xE0) { return c - 256; }
    if (c >= 0xA0 && c <= 0xBF) { return rs(c & 31); }
    if (c >= 0x90 && c <= 0x9F) { return seq(c & 15, false); }
    if (c >= 0x80 && c <= 0x8F) { return seq(c & 15, true); }
    switch (c) {
      case 0xC0: return null;
      case 0xC2: return false;
      case 0xC3: return true;
      case 0xCC: return be(1);
      case 0xCD: return be(2);
      case 0xCE: return be(4);
      case 0xCF: return be(8);
      case 0xD0: return sbe(1);
      case 0xD1: return sbe(2);
      case 0xD2: return sbe(4);
      case 0xD3: return sbe(8);
      case 0xCA: return f32();
      case 0xCB: return f64();
      case 0xD9: return rs(be(1));
      case 0xDA: return rs(be(2));
      case 0xDB: return rs(be(4));
      case 0xC4: var n1 = be(1); o += n1; return null;
      case 0xC5: var n2 = be(2); o += n2; return null;
      case 0xC6: var n4 = be(4); o += n4; return null;
      case 0xDC: return seq(be(2), false);
      case 0xDD: return seq(be(4), false);
      case 0xDE: return seq(be(2), true);
      case 0xDF: return seq(be(4), true);
    }
    throw new WerkError("unknown MessagePack format byte");
  }
  var v = read();
  if (o !== end) { throw new WerkError("trailing bytes after the MessagePack header"); }
  return v;
}

function a16(n) { return Math.floor((n + 15) / 16) * 16; }

function readEnvelope(data) {
  var n = B.len(data);
  if (n < 16) { throw new WerkError("file is " + n + " bytes; the smallest legal envelope is 16"); }
  if (!isEnvelopeMagic(data)) { throw new WerkError("not an envelope magic"); }
  var magic = String.fromCharCode(B.at(data, 0), B.at(data, 1), B.at(data, 2), B.at(data, 3));
  var version = u32(data, 4), hlen = u32(data, 8);
  if (12 + hlen > n) { throw new WerkError("header_len runs past the end of the file"); }
  var header = mpDecode(data, 12, 12 + hlen);
  if (!isObj(header)) { throw new WerkError("the header is not a map"); }
  if (header.endianness !== "le") { throw new WerkError("header endianness is not 'le'"); }
  if (hasOwn(MAGIC_KIND, magic) && header.kind !== MAGIC_KIND[magic]) { throw new WerkError("magic " + magic + " implies kind " + MAGIC_KIND[magic]); }
  var origin = a16(12 + hlen);
  if (header.payload_origin !== origin) { throw new WerkError("payload_origin does not equal the computed origin"); }
  if (!isInt(header.payload_size) || origin + header.payload_size !== n) { throw new WerkError("payload_origin + payload_size != file size"); }
  var prev = origin, secs = header.sections || [], i;
  for (i = 0; i < secs.length; i++) {
    var off = secs[i].offset, size = secs[i].size;
    if (off % 16 || off < prev || off - prev > 15 || off + size > n) { throw new WerkError("section " + secs[i].name + " is misplaced"); }
    prev = off + size;
  }
  if (secs.length && a16(secs[secs.length - 1].offset + secs[secs.length - 1].size) !== origin + header.payload_size) {
    throw new WerkError("the last section does not end where payload_size says");
  }
  return { magic: magic, version: version, header: header };
}

// ---------------------------------------------------------------- the bundle
var BUNDLE = null;
function Bundle(info, files) { this.info = info; this.files = {}; this.order = []; this.data = files; var i;
  for (i = 0; i < info.files.length; i++) { this.files["/" + info.files[i].path] = info.files[i]; this.order.push(info.files[i].path); } }
Bundle.prototype.rec = function (p) { return this.files["/" + p]; };
Bundle.prototype.bytes = function (p) {
  var b = this.data(p), r = this.rec(p);
  if (B.len(b) !== r.size) { throw new WerkError("the vendored bundle file " + p + " is not the bytes bundle.json declares"); }
  return b;
};
function defaultBundle() {
  if (!BUNDLE) {
    var info = jsonParse(WERK_BUNDLE_JSON), cache = {};
    BUNDLE = new Bundle(info, function (p) {
      if (!hasOwn(cache, "/" + p)) { cache["/" + p] = b64decode(WERK_BUNDLE_FILES[p]); }
      return cache["/" + p];
    });
  }
  return BUNDLE;
}

// ---------------------------------------------------------------- reading
var SUPPORTED_CONVENTIONS = null, BASE_CONVENTIONS = null;
function conventionTables() {
  if (!SUPPORTED_CONVENTIONS) {
    var info = defaultBundle().info, ps = keysOf(info.profiles), i;
    SUPPORTED_CONVENTIONS = {};
    for (i = 0; i < ps.length; i++) { SUPPORTED_CONVENTIONS[ps[i]] = info.profiles[ps[i]].conventions; }
    BASE_CONVENTIONS = info.base_conventions;
  }
}
var PAYLOAD_ROLE = { "core.audio.effect": "best", "core.audio.ambience": "best", "core.imposter": "atlas", "core.recipe": "record" };
var MESH_TYPES = ["core.geom.game", "core.geom.source", "core.geom.lod"];

function jsonEqual(a, b) {
  var i, ka, kb;
  if ((typeof a === "number" || a instanceof WFloat || a instanceof WInt) && (typeof b === "number" || b instanceof WFloat || b instanceof WInt)) { return numValue(a) === numValue(b); }
  if (isArray(a)) { if (!isArray(b) || a.length !== b.length) { return false; } for (i = 0; i < a.length; i++) { if (!jsonEqual(a[i], b[i])) { return false; } } return true; }
  if (a !== null && typeof a === "object") {
    if (b === null || typeof b !== "object" || isArray(b)) { return false; }
    ka = keysOf(a); kb = keysOf(b);
    if (ka.length !== kb.length) { return false; }
    for (i = 0; i < ka.length; i++) { if (!hasOwn(b, ka[i]) || !jsonEqual(a[ka[i]], b[ka[i]])) { return false; } }
    return true;
  }
  return a === b;
}

function Node(raw, index) {
  this.raw = raw;
  this.index = index;
  this.nodeId = typeof raw.node_id === "string" ? raw.node_id : "<node " + index + ">";
  this.type = typeof raw.type === "string" ? raw.type : "<untyped>";
  this.active = raw.active;
  this.versions = isArray(raw.versions) ? raw.versions : [];
  this.edges = isArray(raw.edges) ? raw.edges : [];
  this.meta = isObj(raw.meta) ? raw.meta : {};
  this.resolved = null;
  this.status = "alive";
  this.reason = "";
}
Node.prototype.version = function (v) {
  if (v === undefined || v === null) { v = this.resolved; }
  for (var i = 0; i < this.versions.length; i++) { if (isObj(this.versions[i]) && this.versions[i].v === v) { return this.versions[i]; } }
  return null;
};

// SPEC 12.1: what a node needs to be walked at all -- the reference core's and
// the bootstrap loaders' rule (twin of the Python node_shape_error).
function nodeShapeError(n) {
  var i, j, vs, fs;
  if (!isObj(n)) { return "is not a JSON object"; }
  if (typeof n.node_id !== "string") { return "no node_id"; }
  if (typeof n.type !== "string") { return "no type"; }
  if (!isInt(n.active)) { return "no active"; }
  vs = n.versions;
  if (!isArray(vs) || !vs.length) { return "no versions array"; }
  for (i = 0; i < vs.length; i++) {
    if (!isObj(vs[i]) || !isInt(vs[i].v)) { return "a version has no v"; }
    fs = vs[i].files;
    if (!isArray(fs)) { return "a version has no files[]"; }
    for (j = 0; j < fs.length; j++) {
      if (!isObj(fs[j])) { return "a files[] entry is not an object"; }
      // SPEC 12.1: path, sha256 and an integer size, or the node is dead.
      if (typeof fs[j].path !== "string") { return "a files[] entry has no path"; }
      if (typeof fs[j].sha256 !== "string") { return "a files[] entry has no sha256"; }
      if (!isInt(fs[j].size) || fs[j].size < 0) { return "a files[] entry has no integer size"; }
    }
  }
  return null;
}

function payloadPathOf(node, ver) {
  if (!ver) { throw new WerkError("node " + node.nodeId + " has no usable version"); }
  var files = ver.files || [], paths = [], i, roled = [];
  for (i = 0; i < files.length; i++) { paths.push(files[i].path); }
  if (typeof ver.payload_file === "string") {
    var cnt = 0;
    for (i = 0; i < paths.length; i++) { if (paths[i] === ver.payload_file) { cnt++; } }
    if (cnt === 1) { return ver.payload_file; }
    throw new WerkError("payload-file-ambiguous: payload_file " + ver.payload_file + " is not exactly one of files[]", "payload-file-ambiguous");
  }
  if (files.length === 1) { return paths[0]; }
  for (i = 0; i < files.length; i++) { if (files[i].role === "payload") { roled.push(files[i].path); } }
  if (roled.length === 1) { return roled[0]; }
  var role = PAYLOAD_ROLE[node.type];
  if (role) {
    roled = [];
    for (i = 0; i < files.length; i++) { if (files[i].role === role) { roled.push(files[i].path); } }
    if (roled.length === 1) { return roled[0]; }
  }
  if (node.type === "core.anim.clip") {
    roled = [];
    for (i = 0; i < files.length; i++) { if (endsWith(String(files[i].path), ".wkac")) { roled.push(files[i].path); } }
    if (roled.length === 1) { return roled[0]; }
  }
  throw new WerkError("payload-file-ambiguous: node " + node.nodeId + " has " + paths.length + " candidate files; none is declared the payload", "payload-file-ambiguous");
}

function specSha256Of(nodes) {
  var declared = {}, keys = [], i, j, k, n, v, f;
  for (i = 0; i < nodes.length; i++) {
    n = nodes[i];
    if (!isObj(n) || !isArray(n.versions)) { continue; }
    for (j = 0; j < n.versions.length; j++) {
      v = n.versions[j];
      if (!isObj(v) || !isArray(v.files)) { continue; }
      for (k = 0; k < v.files.length; k++) {
        f = v.files[k];
        if (isObj(f) && typeof f.path === "string" && startsWith(f.path, "spec/")) {
          if (!hasOwn(declared, "/" + f.path)) { keys.push(f.path); }
          declared["/" + f.path] = f.sha256;
        }
      }
    }
  }
  keys = sortUtf8(keys);
  var h = new Sha256(), lf = B.fromArray([10]);
  for (i = 0; i < keys.length; i++) {
    var raw;
    try { raw = fromHex(declared["/" + keys[i]]); } catch (e) { raw = B.empty(); }
    h.update(utf8Encode(keys[i])); h.update(lf); h.update(raw); h.update(lf);
  }
  return toHex(h.digest());
}

function inputHashOf(rawDigests, params) {
  var h = new Sha256(), i;
  for (i = 0; i < rawDigests.length; i++) { h.update(rawDigests[i]); }
  h.update(jsonCanonical(params === undefined || params === null ? {} : params));
  return toHex(h.digest());
}

function signatureMessage(msha, prev, at, uri, kind) { return utf8Encode(["werk-sig/1", msha, prev, at, uri, kind].join("\n")); }

function verifyChain(raw, manifestSha) {
  var doc, problems = [], signers = [], i;
  try { doc = jsonParseBytes(raw); } catch (e) { return { problems: ["SIGNATURE.json is not valid JSON: " + e.message], signers: [] }; }
  if (!isObj(doc)) { return { problems: ["SIGNATURE.json is not an object"], signers: [] }; }
  // SPEC 6 / 10.1: a foreign algorithm is `unverified`; no algorithm, or not a
  // string, is a chain that cannot be read (present-and-invalid). werk-core's rule.
  if (doc.algorithm === undefined) { return { problems: ["SIGNATURE.json has no `algorithm`"], signers: [] }; }
  if (typeof doc.algorithm !== "string") { return { problems: ["SIGNATURE.json `algorithm` is not a string"], signers: [] }; }
  if (doc.algorithm !== "ed25519") { return { problems: null, signers: [] }; }
  if (doc.manifest_sha256 !== manifestSha) { problems.push("top-level manifest_sha256 is not the manifest present"); }
  var chain = doc.chain;
  if (!isArray(chain) || !chain.length) { problems.push("chain is empty or not an array"); return { problems: problems, signers: [] }; }
  var prevSig = null;
  for (i = 0; i < chain.length; i++) {
    var e = chain[i], where = "chain[" + i + "]";
    if (!isObj(e)) { problems.push(where + " is not an object"); break; }
    if (e.index !== i) { problems.push(where + " declares the wrong index"); }
    var signer = isObj(e.signer) ? e.signer : {}, em = e.manifest_sha256;
    if (typeof em !== "string") { problems.push(where + " has no manifest_sha256"); em = ""; }
    else if (i === chain.length - 1 && em !== manifestSha) { problems.push(where + " is the newest link and signs another manifest"); }
    var expected = i === 0 ? repeat("0", 64) : sha256Hex(utf8Encode(prevSig || ""));
    var prev = e.prev_entry_sha256;
    if (prev !== expected) { problems.push(where + " prev_entry_sha256 breaks the chain"); }
    var sig, pub;
    try { sig = fromHex(e.signature); pub = fromHex(e.public_key); } catch (x) { problems.push(where + " public_key or signature is not hex"); prevSig = e.signature; continue; }
    var fields = [em, typeof prev === "string" ? prev : "", e.signed_at, signer.uri, signer.kind], ok = true, j;
    for (j = 0; j < fields.length; j++) { if (typeof fields[j] !== "string") { ok = false; } }
    if (!ok) { problems.push(where + " has a non-string field"); }
    else if (!ed25519Verify(pub, signatureMessage(fields[0], fields[1], fields[2], fields[3], fields[4]), sig)) { problems.push(where + " Ed25519 signature does not verify"); }
    else { signers.push((signer.name || "?") + " <" + (signer.uri || "") + ">"); }
    prevSig = typeof e.signature === "string" ? e.signature : "";
  }
  return { problems: problems, signers: signers };
}

function Package(container, path) {
  conventionTables();
  this.path = path;
  this.container = container;
  this.form = container.form;
  this.report = [];
  this.hashCache = {};
  var raw;
  try { raw = container.read(MANIFEST); }
  catch (e) { if (e.missing) { throw refusal("manifest-absent", MANIFEST + " is not in " + path); } throw refusal("manifest-unparseable", MANIFEST + " cannot be read: " + e.message); }
  this.manifestBytes = raw;
  try { this.manifest = jsonParseBytes(raw); } catch (e2) { throw refusal("manifest-unparseable", MANIFEST + " is not valid JSON: " + e2.message); }
  var m = this.manifest;
  if (!isObj(m)) { throw refusal("manifest-structurally-invalid", "MANIFEST.json is not an object"); }
  if (!isArray(m.nodes)) { throw refusal("manifest-structurally-invalid", "nodes is not an array"); }
  this.manifestSha256 = sha256Hex(raw);
  this.profile = typeof m.profile === "string" ? m.profile : "";
  this.envelopesValidated = 0;
  this.signatureState = SIG_ABSENT;
  this.signers = [];
  var major = isObj(m.werk) ? m.werk.major : null;
  // Not a container trigger (SPEC 12.1 lists only the graph); the base shape
  // pins werk.major to 1, so this is that check failing.
  if (major !== 1) { this.add("error", "schema-invalid", null, "werk.major is " + major + "; this reader implements major version 1"); }
  this.checkConventions();
  this.checkSignature();
  this.nodes = [];
  this.byId = {};
  var i;
  for (i = 0; i < m.nodes.length; i++) {
    var nd = new Node(isObj(m.nodes[i]) ? m.nodes[i] : {}, i);
    this.nodes.push(nd);
    if (!hasOwn(this.byId, "/" + nd.nodeId)) { this.byId["/" + nd.nodeId] = nd; }
  }
  this.walk();
  this.propagateEdges();
  this.checkFloating();
  this.specSha256Computed = specSha256Of(m.nodes);
  if (m.spec_sha256 !== undefined && m.spec_sha256 !== this.specSha256Computed) {
    this.add("error", "spec-sha256-mismatch", null, "spec_sha256 declares " + m.spec_sha256 + "; the spec/ files the manifest lists digest to " + this.specSha256Computed);
  }
  this.checkInputHashes();
}
Package.prototype.add = function (sev, code, node, msg) { this.report.push({ severity: sev, code: code, node: node, message: msg }); };
Package.prototype.errors = function () { var o = [], i; for (i = 0; i < this.report.length; i++) { if (this.report[i].severity === "error") { o.push(this.report[i]); } } return o; };
Package.prototype.checkConventions = function () {
  var conv = this.manifest.conventions, table = SUPPORTED_CONVENTIONS[this.profile], ks, i;
  if (!isObj(conv)) { this.add("error", "unsupported-convention", null, "no conventions block"); return; }
  if (!table || !hasOwn(SUPPORTED_CONVENTIONS, this.profile)) {
    var own = [], ck = keysOf(conv);
    for (i = 0; i < ck.length; i++) { if (!hasOwn(BASE_CONVENTIONS, ck[i])) { own.push(ck[i]); } }
    this.add("warn", "unsupported-profile", null, "profile " + this.profile + " is not built into this reader; the six base conventions were checked, the profile's own (" + sortUtf8(own).join(", ") + ") were not interpreted, and the manifest was NOT validated against the schema it names. Every file is still listed, hash-verified and extractable");
    table = BASE_CONVENTIONS;
  }
  ks = keysOf(table);
  for (i = 0; i < ks.length; i++) {
    if (!hasOwn(conv, ks[i])) { this.add("error", "unsupported-convention", null, "`" + ks[i] + "` is missing"); }
    else if (!jsonEqual(conv[ks[i]], table[ks[i]]) || (typeof conv[ks[i]] === "boolean") !== (typeof table[ks[i]] === "boolean")) {
      this.add("error", "unsupported-convention", null, "`" + ks[i] + "` has a value this reader does not implement");
    }
  }
};
Package.prototype.checkSignature = function () {
  var raw;
  try { raw = this.container.read(SIGNATURE); } catch (e) {
    if (!e.missing) {
      // SPEC section 6: present but its entry cannot be read is
      // present-and-invalid, never absent.
      this.signatureState = SIG_INVALID;
      this.add("error", "signature-invalid", null, "SIGNATURE.json is present but cannot be read: " + e.message);
      return;
    }
    this.signatureState = SIG_ABSENT;
    this.add("info", "signature-absent", null, "no SIGNATURE.json: anonymous, which is legitimate and visible");
    return;
  }
  var r = verifyChain(raw, this.manifestSha256);
  if (r.problems === null) { this.signatureState = SIG_UNVERIFIED; this.add("warn", "signature-unverified", null, "signature algorithm not supported"); }
  else if (r.problems.length) { this.signatureState = SIG_INVALID; this.add("error", "signature-invalid", null, r.problems.join("; ")); }
  else { this.signatureState = SIG_VALID; this.signers = r.signers; this.add("info", "signature-valid", null, r.signers.length + " link(s) verify: " + r.signers.join(", ")); }
};
Package.prototype.fileHash = function (path) {
  if (!hasOwn(this.hashCache, "/" + path)) {
    var b = this.container.read(path);
    this.hashCache["/" + path] = { sha: sha256Hex(b), size: B.len(b) };
  }
  return this.hashCache["/" + path];
};
Package.prototype.verifyVersion = function (node, ver) {
  var problems = [], files = isArray(ver.files) ? ver.files : [], i, tag = node.nodeId + " v" + ver.v;
  for (i = 0; i < files.length; i++) {
    var f = files[i], path = isObj(f) ? f.path : null, h;
    if (typeof path !== "string") { problems.push(["error", "file-missing", tag + ": a file record has no path"]); continue; }
    if (isUnsafePath(path)) { problems.push(["error", "schema-invalid", unsafeMsg(tag, path)]); continue; }
    try { h = this.fileHash(path); }
    catch (e) {
      if (e.missing) { problems.push(["error", "file-missing", tag + ": " + path + " is not in the container"]); }
      else if (e.code === "zip-entry-invalid") { problems.push(["error", "zip-entry-invalid", tag + ": " + e.message]); }
      else { problems.push(["error", "zip-entry-unsupported", tag + ": " + e.message]); }
      continue;
    }
    // A record without a usable size declares 0 bytes (werk-core's and the C/Rust loaders' reading).
    var dsize = isInt(f.size) && f.size >= 0 ? f.size : 0;
    if (h.size !== dsize) { problems.push(["error", "size-mismatch", tag + ": " + path + " declares " + f.size + " bytes, holds " + h.size]); }
    if (h.sha !== f.sha256) { problems.push(["error", "hash-mismatch", tag + ": " + path + " declares sha256 " + f.sha256 + ", bytes hash to " + h.sha]); }
  }
  return problems;
};
Package.prototype.declaredFormats = function (node, ver) {
  var out = {}, files = ver.files || [], i;
  if (typeof node.meta.payload_format === "string") { try { out["/" + payloadPathOf(node, ver)] = true; } catch (e) { /* ambiguous: nothing declared */ } }
  if (isObj(node.meta.file_formats)) {
    for (i = 0; i < files.length; i++) { if (typeof files[i].role === "string" && hasOwn(node.meta.file_formats, files[i].role)) { out["/" + files[i].path] = true; } }
  }
  return out;
};
Package.prototype.walk = function () {
  var i, j, node, cands, active, problems;
  for (i = 0; i < this.nodes.length; i++) {
    node = this.nodes[i];
    var bad = nodeShapeError(this.manifest.nodes[node.index]);
    if (bad !== null) {
      node.status = "dead"; node.reason = "malformed node: " + bad; node.type = "<malformed>"; node.versions = []; node.edges = [];
      this.add("error", "node-dead", node.nodeId, node.nodeId + ": nodes[" + node.index + "]: " + bad + "; the node is dead, the package is not");
      continue;
    }
    if (!node.versions.length) { node.status = "dead"; node.reason = "no versions[]"; this.add("error", "node-dead", node.nodeId, node.nodeId + " has no versions[]"); continue; }
    active = node.active;
    var found = false;
    for (j = 0; j < node.versions.length; j++) { if (isObj(node.versions[j]) && node.versions[j].v === active) { found = true; } }
    if (!found) { this.add("warn", "version-fallback", node.nodeId, node.nodeId + ": active names v" + active + ", which does not exist"); }
    cands = [];
    for (j = 0; j < node.versions.length; j++) {
      var v = node.versions[j];
      if (isObj(v) && isInt(v.v) && (!isInt(active) || v.v <= active)) { cands.push(v); }
    }
    cands.sort(function (a, b) { return b.v - a.v; });
    var tried = [];
    for (j = 0; j < cands.length; j++) {
      tried.push(cands[j]);
      if (hasOwn(cands[j], "compacted")) { this.add("info", "version-compacted", node.nodeId, node.nodeId + " v" + cands[j].v + " was compacted"); continue; }
      problems = this.verifyVersion(node, cands[j]);
      if (!problems.length) {
        node.resolved = cands[j].v;
        if (cands[j].v !== active) { this.add("warn", "version-fallback", node.nodeId, node.nodeId + ": active v" + active + " is unusable, fell back to v" + cands[j].v); }
        break;
      }
      for (var k = 0; k < problems.length; k++) { this.add(problems[k][0], problems[k][1], node.nodeId, problems[k][2]); }
    }
    // MINI-SPECS 5.4 / SPEC 10 step 5: an unsafe path makes its VERSION unusable,
    // never the node; one in a version the walk did not need (newer than
    // `active`, older than the resolved one) is still an error, reported -- as
    // werk-core reports it.
    for (j = 0; j < node.versions.length; j++) {
      var uv = node.versions[j];
      if (!isObj(uv) || contains(tried, uv) || !isArray(uv.files)) { continue; }
      for (var q = 0; q < uv.files.length; q++) {
        var up = isObj(uv.files[q]) ? uv.files[q].path : null;
        if (typeof up === "string" && isUnsafePath(up)) { this.add("error", "schema-invalid", node.nodeId, unsafeMsg(node.nodeId + " v" + uv.v, up)); }
      }
    }
    if (node.resolved === null) { node.status = "dead"; node.reason = "no usable version"; this.add("error", "node-dead", node.nodeId, node.nodeId + ": no usable version"); continue; }
    var ver = node.version(), declared = this.declaredFormats(node, ver), files = ver.files;
    for (j = 0; j < files.length; j++) {
      var p = files[j].path, head;
      if (hasOwn(declared, "/" + p)) { continue; }
      try { head = this.container.head(p, 4); } catch (e) { continue; }
      if (!isEnvelopeMagic(head)) { continue; }
      try { readEnvelope(this.container.read(p)); this.envelopesValidated++; }
      catch (e2) { node.status = "dead"; node.reason = "envelope-invalid"; this.add("error", "envelope-invalid", node.nodeId, node.nodeId + ": " + p + ": " + e2.message); }
    }
    if (node.status === "dead") { continue; }
    if (!startsWith(node.type, "core.")) {
      node.status = "skipped"; node.reason = "unknown node type `" + node.type + "`";
      this.add("warn", "node-skipped-unknown-type", node.nodeId, node.nodeId + ": type `" + node.type + "` is not interpreted; its bytes are verified and extractable");
    }
    if (node.type === "core.loader" && node.meta.form === "prebuilt") {
      this.add("info", "prebuilt-not-executed", node.nodeId, node.nodeId + " carries a prebuilt binary; it was NOT executed (SPEC 7.1)");
    }
  }
};
Package.prototype.propagateEdges = function () {
  var changed = true, i, j, n, e, t;
  while (changed) {
    changed = false;
    for (i = 0; i < this.nodes.length; i++) {
      n = this.nodes[i];
      if (n.status === "dead") { continue; }
      for (j = 0; j < n.edges.length; j++) {
        e = n.edges[j];
        t = isObj(e) && typeof e.to === "string" && hasOwn(this.byId, "/" + e.to) ? this.byId["/" + e.to] : null;
        if (!t && isObj(e) && typeof e.to === "string" && e.kind === "requires") {
          // SPEC 5 "Edge targets": a requires edge to a node absent from nodes[] kills the source, skipped or not.
          n.status = "dead"; n.reason = "requires `" + e.to + "`, which is not a node";
          this.add("error", "requires-missing-node", n.nodeId, n.nodeId + ": a `requires` edge to `" + e.to + "`, which is not a node in this manifest");
          changed = true;
          break;
        }
        if (t && t.status === "dead" && e.kind === "requires") {
          n.status = "dead"; n.reason = "requires dead node `" + e.to + "`";
          this.add("error", "requires-dead-node", n.nodeId, n.nodeId + ": a `requires` edge into dead node `" + e.to + "`");
          changed = true;
          break;
        }
      }
    }
  }
  for (i = 0; i < this.nodes.length; i++) {
    n = this.nodes[i];
    for (j = 0; j < n.edges.length; j++) {
      e = n.edges[j];
      if (!isObj(e) || typeof e.to !== "string") { continue; }
      t = hasOwn(this.byId, "/" + e.to) ? this.byId["/" + e.to] : null;
      if (!t && e.kind === "requires") { continue; }
      if (!t) { this.add("warn", "edge-dangling", n.nodeId, n.nodeId + ": edge points at `" + e.to + "`, which is not a node"); }
      else if (t.status === "dead" && e.kind === "enhances") { this.add("warn", "enhances-dead-node", n.nodeId, n.nodeId + ": `enhances` dead node `" + e.to + "` (one feature lost)"); }
    }
  }
};
Package.prototype.checkFloating = function () {
  var declared = {}, i, j, k, names = this.container.names();
  for (i = 0; i < this.nodes.length; i++) {
    for (j = 0; j < this.nodes[i].versions.length; j++) {
      var v = this.nodes[i].versions[j];
      if (!isObj(v) || !isArray(v.files)) { continue; }
      for (k = 0; k < v.files.length; k++) { if (isObj(v.files[k]) && typeof v.files[k].path === "string") { declared["/" + v.files[k].path] = true; } }
    }
  }
  for (i = 0; i < names.length; i++) {
    if (names[i] !== MANIFEST && names[i] !== SIGNATURE && !hasOwn(declared, "/" + names[i])) {
      this.add("warn", "floating-file", null, names[i] + " is in the container but no node declares it");
    }
  }
};
Package.prototype.checkInputHashes = function () {
  var i, j;
  for (i = 0; i < this.nodes.length; i++) {
    var n = this.nodes[i], ver = n.version();
    if (!ver || !hasOwn(ver, "input_hash")) { continue; }
    var paths = isArray(ver.input_files) ? ver.input_files : [], digests = [], ok = true;
    for (j = 0; j < paths.length; j++) { try { digests.push(fromHex(this.fileHash(paths[j]).sha)); } catch (e) { ok = false; } }
    if (!ok) { continue; }
    var got = inputHashOf(digests, ver.input_params || {});
    if (got !== ver.input_hash) { this.add("warn", "stale-derived-data", n.nodeId, n.nodeId + " v" + ver.v + ": input_hash " + ver.input_hash + ", the declared inputs hash to " + got); }
  }
};
Package.prototype.node = function (id) {
  if (!hasOwn(this.byId, "/" + id)) { throw new WerkError("no node " + id); }
  return this.byId["/" + id];
};
Package.prototype.readFile = function (path) {
  var i, j, k, ok = path === MANIFEST || path === SIGNATURE;
  for (i = 0; i < this.nodes.length && !ok; i++) {
    for (j = 0; j < this.nodes[i].versions.length && !ok; j++) {
      var fs = this.nodes[i].versions[j].files || [];
      for (k = 0; k < fs.length; k++) { if (fs[k].path === path) { ok = true; } }
    }
  }
  if (!ok) { throw new WerkError(path + " is not declared by any node; refusing to read it"); }
  return this.container.read(path);
};
Package.prototype.payloadPath = function (id, version) {
  var n = this.node(id);
  if ((version === undefined || version === null) && n.resolved === null) { throw new WerkError("node " + id + " is dead: " + n.reason); }
  return payloadPathOf(n, n.version(version));
};
Package.prototype.readPayload = function (id, version) {
  var n = this.node(id);
  if ((version === undefined || version === null) && n.status === "dead") { throw new WerkError("node " + id + " is dead: " + n.reason); }
  return this.container.read(payloadPathOf(n, n.version(version)));
};
Package.prototype.primary = function (key) {
  var prim = this.manifest.primary, i, alive = [], pick = null;
  if (isObj(prim) && typeof prim[key] === "string") { return { nodeId: prim[key], fellBack: false }; }
  for (i = 0; i < this.nodes.length; i++) { if (this.nodes[i].status !== "dead") { alive.push(this.nodes[i]); } }
  function first(test) { for (var j = 0; j < alive.length; j++) { if (test(alive[j])) { return alive[j]; } } return null; }
  if (key === "image") {
    if (this.profile === "image/1") { pick = first(function (n) { return n.type === "core.image.source"; }); }
    else { pick = first(function (n) { return n.type === "core.imposter"; }) || first(function (n) { return n.type === "core.tex" && n.meta.usage === "base-color"; }); }
  } else if (key === "mesh") {
    pick = first(function (n) { return n.type === "core.geom.game"; });
  } else if (key === "thumbnail") {
    var th = [];
    for (i = 0; i < alive.length; i++) { if (alive[i].type === "core.image.derived" && alive[i].meta.derived_role === "thumbnail") { th.push(alive[i]); } }
    th.sort(function (a, b) { return (a.meta.width || 0) - (b.meta.width || 0); });
    pick = th.length ? th[0] : null;
  }
  if (!pick) { throw new WerkError("no primary " + key + " declared and the documented fallback finds none"); }
  return { nodeId: pick.nodeId, fellBack: true };
};
Package.prototype.primaryImage = function () {
  var id = this.primary("image").nodeId;
  return { nodeId: id, path: this.payloadPath(id), bytes: this.readPayload(id) };
};
Package.prototype.primaryMesh = function () {
  var prim = isObj(this.manifest.primary) ? this.manifest.primary : {}, id = prim.mesh || null;
  if (!id && typeof prim.geometry === "string" && contains(MESH_TYPES, this.node(prim.geometry).type)) { id = prim.geometry; }
  if (!id) { id = this.primary("mesh").nodeId; }
  return { nodeId: id, path: this.payloadPath(id), bytes: this.readPayload(id) };
};
Package.prototype.extract = function (outDir, nodeIds, allVersions, io) {
  io = io || IO;
  var written = [], seen = {}, i, j, k;
  for (i = 0; i < this.nodes.length; i++) {
    var n = this.nodes[i];
    if (nodeIds && !contains(nodeIds, n.nodeId)) { continue; }
    if (n.status === "dead" && !allVersions) { continue; }
    var vers = allVersions ? n.versions : [n.version()];
    for (j = 0; j < vers.length; j++) {
      var fs = (vers[j] && vers[j].files) || [];
      for (k = 0; k < fs.length; k++) {
        var p = fs[k].path;
        if (hasOwn(seen, "/" + p)) { continue; }
        rejectUnsafe(p);
        var target = io.join(outDir, p);
        io.mkdirs(io.dirname(target));
        io.write(target, this.container.read(p));
        seen["/" + p] = true;
        written.push(p);
      }
    }
  }
  return written;
};
Package.prototype.census = function () {
  var c = { alive: 0, skipped: 0, dead: 0 }, i;
  for (i = 0; i < this.nodes.length; i++) { c[this.nodes[i].status]++; }
  return c;
};
Package.prototype.verdict = function () {
  var c = this.census(), errs = {}, codes = [], dead = [], i;
  for (i = 0; i < this.report.length; i++) { if (this.report[i].severity === "error" && !hasOwn(errs, this.report[i].code)) { errs[this.report[i].code] = true; codes.push(this.report[i].code); } }
  for (i = 0; i < this.nodes.length; i++) { if (this.nodes[i].status === "dead") { dead.push(this.nodes[i].nodeId); } }
  return {
    exit: codes.length ? 1 : 0, profile: this.profile, form: this.form, signature: this.signatureState,
    nodes: this.nodes.length, alive: c.alive, skipped: c.skipped, dead: c.dead,
    dead_nodes: sortUtf8(dead), error_codes: sortUtf8(codes), envelopes: this.envelopesValidated,
    manifest_sha256: this.manifestSha256, spec_sha256_ok: this.manifest.spec_sha256 === this.specSha256Computed,
    schema_validated: false
  };
};

// ---------------------------------------------------------------- writing
var ID_RE = /^[a-z0-9]+(-[a-z0-9]+)*$/;
var PATH_RE = /^[A-Za-z0-9][A-Za-z0-9._@\/-]*$/;
var TYPE_RE = /^(core|x)\.[a-z0-9-]+(\.[a-z0-9-]+)*$/;
var UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

function checkId(s, what) { if (typeof s !== "string" || !ID_RE.test(s)) { throw new WerkError((what || "id") + " " + s + " is not kebab-case"); } }
function checkPath(p) {
  if (typeof p !== "string" || !PATH_RE.test(p) || p.length > 1024 || contains(p.split("/"), "..") || endsWith(p, "/") || p.indexOf("//") >= 0) {
    throw new WerkError("package path " + p + " is not legal: relative POSIX, ASCII letters, digits and . _ @ / - only, first character a letter or digit, no '..' (manifest.schema.json $defs/path)");
  }
  if (p === MANIFEST || p === SIGNATURE) { throw new WerkError(p + " is written by the writer itself"); }
}
function checkNote(note) {
  if (typeof note !== "string" || note.length < 8 || note.length > 2000) { throw new WerkError("every version carries a work note of 8-2000 characters saying why it exists (law 6)"); }
}
function pad2(n) { return n < 10 ? "0" + n : String(n); }
function utcNow() {
  var d = new Date();
  return d.getUTCFullYear() + "-" + pad2(d.getUTCMonth() + 1) + "-" + pad2(d.getUTCDate()) + "T" + pad2(d.getUTCHours()) + ":" + pad2(d.getUTCMinutes()) + ":" + pad2(d.getUTCSeconds()) + "Z";
}
function uuid4() {
  var h = [], i;
  for (i = 0; i < 32; i++) { h.push(HEXC.charAt(Math.floor(Math.random() * 16))); }
  h[12] = "4"; h[16] = HEXC.charAt(8 + Math.floor(Math.random() * 4));
  var s = h.join("");
  return s.substring(0, 8) + "-" + s.substring(8, 12) + "-" + s.substring(12, 16) + "-" + s.substring(16, 20) + "-" + s.substring(20);
}

function versionRecord(v, files, note, producer, epistemic, created, payloadFile, confidence, inputFiles, inputParams, inputHash) {
  var r = { v: v, files: files };
  if (payloadFile !== undefined && payloadFile !== null) { r.payload_file = payloadFile; }
  r.note = note; r.producer = producer; r.epistemic = epistemic;
  if (confidence !== undefined && confidence !== null) { r.confidence = confidence; }
  r.created = created;
  if (inputFiles !== undefined && inputFiles !== null) {
    r.input_files = inputFiles.slice(0);
    r.input_params = inputParams === undefined || inputParams === null ? {} : inputParams;
    r.input_hash = inputHash;
  }
  return r;
}

function makeEdge(e) {
  if (isArray(e)) { e = { to: e[0], kind: e[1], role: e[2] }; }
  var out = { to: e.to, kind: e.kind };
  checkId(out.to, "edge target");
  if (out.kind !== "requires" && out.kind !== "enhances") { throw new WerkError("edge kind is requires or enhances"); }
  if (e.role) { checkId(e.role, "edge role"); out.role = e.role; }
  return out;
}

function chainAppend(existing, msha, seed, uri, kind, name, signedAt, role, note) {
  var doc = existing;
  if (!doc) { doc = { werk_signature: 1, algorithm: "ed25519", encoding: "hex-lowercase", manifest_sha256: msha, chain: [] }; }
  else { doc.manifest_sha256 = msha; }
  if (kind !== "human" && kind !== "agent" && kind !== "service") { throw new WerkError("signer kind is human, agent or service (signature.schema.json)"); }
  if (uri.indexOf("\n") >= 0 || signedAt.indexOf("\n") >= 0) { throw new WerkError("a signed field may not contain a line feed"); }
  var chain = doc.chain, prev = chain.length ? sha256Hex(utf8Encode(chain[chain.length - 1].signature)) : repeat("0", 64);
  var sig = ed25519Sign(seed, signatureMessage(msha, prev, signedAt, uri, kind));
  var signer = { name: name, uri: uri, kind: kind };
  if (role) { signer.role = role; }
  var e = { index: chain.length, signer: signer, public_key: toHex(ed25519PublicKey(seed)), signed_at: signedAt,
            manifest_sha256: msha, prev_entry_sha256: prev, signature: toHex(sig) };
  if (note) { e.note = note; }
  chain.push(e);
  return doc;
}

function parseSecretKey(k) {
  if (B.isBytes(k) && B.len(k) === 32) { return k; }
  var t = String(k).replace(/^\s+|\s+$/g, "").toLowerCase();
  if (t.length !== 64) { throw new WerkError("an Ed25519 secret key is given as 64 hex digits (the 32-byte seed)"); }
  return fromHex(t);
}

function file(path, data, mediaType, role) {
  checkPath(path);
  if (role !== undefined && role !== null) { checkId(role, "role"); }
  if (!B.isBytes(data)) { throw new WerkError("file data must be bytes (" + B.kind + ")"); }
  return { path: path, data: data, mediaType: mediaType || null, role: role || null };
}

function PackageWriter(profile, opts) {
  opts = opts || {};
  this.bundle = opts.bundle || defaultBundle();
  var info = this.bundle.info, ptab = hasOwn(info.profiles, profile) ? info.profiles[profile] : null;
  if (!ptab) {
    if (!opts.conventions || !opts.manifestSchema) { throw new WerkError("profile " + profile + " is not built in: pass conventions and manifestSchema (SPEC section 2.2)"); }
    ptab = { conventions: opts.conventions, manifest_schema: opts.manifestSchema, conventions_map: null, has_parts: false, preview_prefixes: ["semantics/"] };
  }
  if (typeof opts.name !== "string" || opts.name.length < 1 || opts.name.length > 200) { throw new WerkError("entity name must be 1-200 characters"); }
  this.profile = profile;
  this.ptab = ptab;
  this.created = opts.created || utcNow();
  dosDateTime(this.created);
  this.uuid = (opts.uuid || uuid4()).toLowerCase();
  if (!UUID_RE.test(this.uuid)) { throw new WerkError("uuid must be an RFC 4122 uuid in lower case"); }
  this.name = opts.name;
  this.summary = opts.summary === undefined ? null : opts.summary;
  this.conventions = opts.conventions || ptab.conventions;
  this.manifestSchema = opts.manifestSchema || ptab.manifest_schema;
  this.profileSpec = opts.profileSpec || null;
  if (opts.conventionsMap !== undefined && opts.conventionsMap !== null) { checkPath(opts.conventionsMap); }
  this.conventionsMap = opts.conventionsMap === undefined ? null : opts.conventionsMap;
  this.generator = opts.generator || { tool: "werk", version: info.lib_version };
  this.producer = opts.producer || { tool: "werk", version: info.lib_version };
  this.spdxId = opts.spdxId || null;
  this.nodes = []; this.nodeIndex = {};
  this.blobs = {}; this.blobOrder = []; this.owner = {};
  this.primaryMap = {}; this.primaryKeys = [];
  this.parts = []; this.materials = [];
  this.schemas = {}; this.layouts = {}; this.formats = {}; this.formatKeys = [];
  this.previewExact = [];
  this.signers = [];
  this.carry(opts);
  if (opts.specFiles) {
    var sk = sortUtf8(keysOf(opts.specFiles));
    for (var si = 0; si < sk.length; si++) { this.addSpecFile(sk[si], opts.specFiles[sk[si]]); }
  }
}
PackageWriter.file = file;
PackageWriter.prototype.file = file;
PackageWriter.prototype.putBlob = function (path, blob, owner) {
  this.blobs["/" + path] = blob; this.blobOrder.push(path); this.owner["/" + path] = owner;
};
PackageWriter.prototype.carry = function (opts) {
  var info = this.bundle.info, texts = info.texts, specFiles = [], i, p, r;
  for (i = 0; i < this.bundle.order.length; i++) {
    p = this.bundle.order[i];
    if (startsWith(p, "spec/")) {
      r = this.bundle.rec(p);
      this.putBlob(p, { bundlePath: p }, "spec");
      specFiles.push({ path: p, sha256: r.sha256, size: r.size });
    }
  }
  this.nodeRaw("spec", "core.spec", specFiles, texts.spec_note, null);
  for (i = 0; i < info.loaders.length; i++) {
    var ld = info.loaders[i];
    r = this.bundle.rec(ld.path);
    this.putBlob(ld.path, { bundlePath: ld.path }, ld.node_id);
    this.nodeRaw(ld.node_id, "core.loader", [{ path: ld.path, sha256: r.sha256, size: r.size }], texts.loader_note, ld.meta);
  }
  var lic = opts.licenseText !== undefined && opts.licenseText !== null ? (B.isBytes(opts.licenseText) ? opts.licenseText : utf8Encode(opts.licenseText)) : utf8Encode(texts.license_unestablished);
  this.addNode("license", "core.license", [file("LICENSE", lic, "text/plain")], { note: texts.license_note });
  var rd = opts.readmeText !== undefined && opts.readmeText !== null ? (B.isBytes(opts.readmeText) ? opts.readmeText : utf8Encode(opts.readmeText)) : utf8Encode(texts.readme);
  this.addNode("readme", "core.readme", [file("README.txt", rd, "text/plain")], { note: texts.readme_note });
};
PackageWriter.prototype.nodeRaw = function (id, type, files, note, meta) {
  var n = { node_id: id, type: type, versions: [versionRecord(1, files, note, this.producer, "authored", this.created)], active: 1, edges: [] };
  if (meta) { n.meta = meta; }
  this.nodes.push(n); this.nodeIndex["/" + id] = n;
};
PackageWriter.prototype.shaOf = function (path) {
  if (!hasOwn(this.blobs, "/" + path)) { throw new WerkError("input file " + path + " is not in the package (law 1: inputs are carried)"); }
  var b = this.blobs["/" + path];
  if (b.bundlePath) { return this.bundle.rec(path).sha256; }
  return sha256Hex(b.data);
};
// opts: note (required), epistemic, producer, meta, edges, inputFiles, inputParams,
//       payloadFile, partId, materialId, confidence, created
PackageWriter.prototype.addNode = function (id, type, files, opts) {
  opts = opts || {};
  checkId(id, "node_id");
  if (hasOwn(this.nodeIndex, "/" + id)) { throw new WerkError("node " + id + " already exists"); }
  if (typeof type !== "string" || !TYPE_RE.test(type)) { throw new WerkError("node type " + type + " is not core.* or x.* kebab-case"); }
  var ep = opts.epistemic || "authored", i;
  if (ep !== "authored" && ep !== "measured" && ep !== "inferred") { throw new WerkError("epistemic is authored, measured or inferred"); }
  if (ep !== "authored" && !(opts.inputFiles && opts.inputFiles.length)) { throw new WerkError("a " + ep + " version names its inputs (law 5): pass inputFiles"); }
  checkNote(opts.note);
  if (!files || !files.length) { throw new WerkError("a version owns at least one file"); }
  var recs = [];
  for (i = 0; i < files.length; i++) {
    var f = files[i];
    if (hasOwn(this.owner, "/" + f.path)) { throw new WerkError(f.path + " is already listed by node " + this.owner["/" + f.path]); }
    var r = { path: f.path, sha256: sha256Hex(f.data), size: B.len(f.data) };
    if (f.mediaType) { r.media_type = f.mediaType; }
    if (f.role) { r.role = f.role; }
    recs.push(r);
    this.putBlob(f.path, { data: f.data }, id);
  }
  var pf = opts.payloadFile === undefined ? null : opts.payloadFile;
  if (pf === null && recs.length > 1) {
    var roled = [];
    for (i = 0; i < recs.length; i++) { if (recs[i].role === "payload") { roled.push(recs[i].path); } }
    if (roled.length === 1) { pf = roled[0]; }
  }
  if (pf !== null) { var okp = false; for (i = 0; i < recs.length; i++) { if (recs[i].path === pf) { okp = true; } } if (!okp) { throw new WerkError("payloadFile " + pf + " is not one of the version's files"); } }
  var ih = null, ip = null;
  if (opts.inputFiles) {
    ip = opts.inputParams === undefined || opts.inputParams === null ? {} : opts.inputParams;
    var ds = [];
    for (i = 0; i < opts.inputFiles.length; i++) { ds.push(fromHex(this.shaOf(opts.inputFiles[i]))); }
    ih = inputHashOf(ds, ip);
  }
  var n = { node_id: id, type: type };
  if (opts.partId !== undefined && opts.partId !== null) { checkId(opts.partId, "part_id"); n.part_id = opts.partId; }
  if (opts.materialId !== undefined && opts.materialId !== null) { checkId(opts.materialId, "material_id"); n.material_id = opts.materialId; }
  n.versions = [versionRecord(1, recs, opts.note, opts.producer || this.producer, ep, opts.created || this.created, pf, opts.confidence, opts.inputFiles || null, ip, ih)];
  n.active = 1;
  n.edges = [];
  var es = opts.edges || [];
  for (i = 0; i < es.length; i++) { n.edges.push(makeEdge(es[i])); }
  if (opts.meta !== undefined && opts.meta !== null) { n.meta = opts.meta; }
  this.nodes.push(n); this.nodeIndex["/" + id] = n;
  var sp = this.bundle.info.schemas_by_type[type];
  if (sp && hasOwn(this.bundle.info.schemas_by_type, type) && !hasOwn(this.schemas, type)) { this.schemas[type] = sp; }
  var lp = this.bundle.info.layouts_by_type[type];
  if (lp && hasOwn(this.bundle.info.layouts_by_type, type) && !hasOwn(this.layouts, type)) { this.layouts[type] = lp; }
  return n;
};
PackageWriter.prototype.setPrimary = function (key, id) { checkId(id, "primary node"); if (!hasOwn(this.primaryMap, key)) { this.primaryKeys.push(key); } this.primaryMap[key] = id; };
PackageWriter.prototype.addPart = function (partId, name, parent, translation, rotation, scale) {
  checkId(partId, "part_id");
  this.parts.push({ part_id: partId, name: name, parent: parent === undefined ? null : parent,
    transform: { translation: translation || [0, 0, 0], rotation: rotation || [1, 0, 0, 0], scale: scale || [1, 1, 1] } });
};
PackageWriter.prototype.addMaterial = function (materialId, name, partId, klass) {
  checkId(materialId, "material_id");
  var m = { material_id: materialId, name: name };
  if (partId !== undefined && partId !== null) { m.part_id = partId; }
  if (klass !== undefined && klass !== null) { m["class"] = klass; }
  this.materials.push(m);
};
// Carry one more file in spec/, or replace a vendored one (a profile's own
// narrative and schema, a format definition). It joins the core.spec node,
// whose files stay sorted by UTF-8 path, so spec_sha256 covers it. Returns
// true when it replaced a bundled file. Twin of the Python add_spec_file.
PackageWriter.prototype.addSpecFile = function (path, data, mediaType) {
  checkPath(path);
  if (!startsWith(path, "spec/")) { throw new WerkError("a specification file lives under spec/: " + path); }
  if (!B.isBytes(data)) { throw new WerkError("spec file data must be bytes (" + B.kind + ")"); }
  if (hasOwn(this.owner, "/" + path) && this.owner["/" + path] !== "spec") { throw new WerkError(path + " is already listed by node " + this.owner["/" + path]); }
  var replaced = hasOwn(this.blobs, "/" + path);
  if (replaced) { this.blobs["/" + path] = { data: data }; } else { this.putBlob(path, { data: data }, "spec"); }
  var rec = { path: path, sha256: sha256Hex(data), size: B.len(data) };
  if (mediaType) { rec.media_type = mediaType; }
  var node = this.nodeIndex["/spec"], old = node.versions[0].files, files = [], i;
  for (i = 0; i < old.length; i++) { if (old[i].path !== path) { files.push(old[i]); } }
  files.push(rec);
  files.sort(function (a, b) { return compareUtf8(a.path, b.path); });
  node.versions[0].files = files;
  return replaced;
};
// Add a file to the core.readme node (a HOW-TO-READ.md beside README.txt).
// The version then declares payload_file "README.txt". Twin of the Python
// add_readme_file; files keep the order they were added in.
PackageWriter.prototype.addReadmeFile = function (path, data, mediaType) {
  checkPath(path);
  if (!B.isBytes(data)) { throw new WerkError("readme file data must be bytes (" + B.kind + ")"); }
  if (hasOwn(this.owner, "/" + path)) { throw new WerkError(path + " is already listed by node " + this.owner["/" + path]); }
  this.putBlob(path, { data: data }, "readme");
  var rec = { path: path, sha256: sha256Hex(data), size: B.len(data) };
  if (mediaType) { rec.media_type = mediaType; }
  var node = this.nodeIndex["/readme"], ver = node.versions[0], ks = keysOf(ver), nv = {}, i;
  var files = ver.files.slice(0);
  files.push(rec);
  for (i = 0; i < ks.length; i++) {
    if (ks[i] === "payload_file") { continue; }
    nv[ks[i]] = ks[i] === "files" ? files : ver[ks[i]];
    if (ks[i] === "files") { nv.payload_file = "README.txt"; }
  }
  node.versions[0] = nv;
};
PackageWriter.prototype.setSchema = function (t, p) { this.schemas[t] = p; };
PackageWriter.prototype.setLayout = function (t, p) { this.layouts[t] = p; };
PackageWriter.prototype.setFormat = function (id, p) { if (!hasOwn(this.formats, id)) { this.formatKeys.push(id); } this.formats[id] = p; };
PackageWriter.prototype.preview = function (p) { if (!contains(this.previewExact, p)) { this.previewExact.push(p); } };
PackageWriter.prototype.sign = function (key, uri, opts) {
  opts = opts || {};
  this.signers.push({ seed: parseSecretKey(key), uri: uri, kind: opts.kind || "human", name: opts.name || uri, role: opts.role === undefined ? "author" : opts.role, note: opts.note || null, signedAt: opts.signedAt || this.created });
};
PackageWriter.prototype.entryOrder = function () {
  var head = this.bundle.info.head_order.slice(0), dirsSeen = {}, dirs = [], i, order, tier, p;
  for (i = 0; i < this.blobOrder.length; i++) {
    p = this.blobOrder[i];
    if (p.indexOf("/") >= 0) { var d = p.substring(0, p.indexOf("/")) + "/"; if (!hasOwn(dirsSeen, d)) { dirsSeen[d] = true; dirs.push(d); } }
  }
  dirs = sortUtf8(dirs);
  order = head.slice(0); tier = head.slice(0);
  var pp = this.ptab.preview_prefixes;
  for (i = 0; i < pp.length; i++) { if (contains(dirs, pp[i]) && !contains(order, pp[i])) { order.push(pp[i]); } if (contains(dirs, pp[i])) { tier.push(pp[i]); } }
  for (i = 0; i < this.previewExact.length; i++) { if (!contains(order, this.previewExact[i])) { order.push(this.previewExact[i]); } tier.push(this.previewExact[i]); }
  for (i = 0; i < dirs.length; i++) { if (!contains(order, dirs[i])) { order.push(dirs[i]); } }
  return { order: order, tier: tier };
};
PackageWriter.prototype.manifest = function (form) {
  var eo = this.entryOrder(), m = {}, i, j;
  m.werk = { major: 1, minor: 0 };
  m.profile = this.profile;
  m.manifest_schema = this.manifestSchema;
  if (this.profileSpec) { m.profile_spec = this.profileSpec; }
  m.spec_sha256 = specSha256Of(this.nodes);
  var ent = { uuid: this.uuid, name: this.name };
  if (this.summary !== null) { ent.summary = this.summary; }
  ent.created = this.created;
  m.entity = ent;
  m.conventions = this.conventions;
  if (this.conventionsMap !== null) {
    if (!hasOwn(this.blobs, "/" + this.conventionsMap) || this.owner["/" + this.conventionsMap] !== "spec") { throw new WerkError("conventionsMap names " + this.conventionsMap + ", which is not a spec/ file of this package (carry it with addSpecFile)"); }
    m.conventions_map = this.conventionsMap;
  } else if (this.ptab.conventions_map && hasOwn(this.blobs, "/" + this.ptab.conventions_map)) { m.conventions_map = this.ptab.conventions_map; }
  m.container = { form: form, zip_compression: "store", entry_order: eo.order, preview_tier: eo.tier };
  if (this.primaryKeys.length) { var pr = {}; for (i = 0; i < this.primaryKeys.length; i++) { pr[this.primaryKeys[i]] = this.primaryMap[this.primaryKeys[i]]; } m.primary = pr; }
  var lic = {};
  if (this.spdxId) { lic.spdx_id = this.spdxId; }
  lic.file = "LICENSE"; lic.sha256 = this.shaOf("LICENSE");
  m.license = lic;
  m.schemas = this.schemas;
  m.layouts = this.layouts;
  if (this.formatKeys.length) { m.formats = this.formats; }
  if (this.ptab.has_parts) { m.parts = this.parts; m.materials = this.materials; }
  m.nodes = this.nodes;
  m.generator = this.generator;
  for (i = 0; i < this.primaryKeys.length; i++) { if (!hasOwn(this.nodeIndex, "/" + this.primaryMap[this.primaryKeys[i]])) { throw new WerkError("primary names " + this.primaryMap[this.primaryKeys[i]] + ", which is not a node"); } }
  for (i = 0; i < this.nodes.length; i++) { for (j = 0; j < this.nodes[i].edges.length; j++) { if (!hasOwn(this.nodeIndex, "/" + this.nodes[i].edges[j].to)) { throw new WerkError(this.nodes[i].node_id + " has an edge to " + this.nodes[i].edges[j].to + ", which is not a node"); } } }
  return m;
};
PackageWriter.prototype.build = function (form) {
  var m = this.manifest(form), mb = jsonPretty(m), sb = null, i;
  if (this.signers.length) {
    var msha = sha256Hex(mb), doc = null;
    for (i = 0; i < this.signers.length; i++) { var s = this.signers[i]; doc = chainAppend(doc, msha, s.seed, s.uri, s.kind, s.name, s.signedAt, s.role, s.note); }
    sb = jsonPretty(doc);
  }
  return { manifest: m, manifestBytes: mb, signatureBytes: sb };
};
PackageWriter.prototype.blobBytes = function (b) { return b.bundlePath ? this.bundle.bytes(b.bundlePath) : b.data; };
PackageWriter.prototype.blobCrc = function (b) { return b.bundlePath ? this.bundle.rec(b.bundlePath).crc32 : null; };
PackageWriter.prototype.toBytes = function () {
  var parts = [], built = this.build("zip");
  writeZipTo({ write: function (b) { parts.push(b); } }, this, built);
  return B.concat(parts);
};
PackageWriter.prototype.write = function (out, form, io) {
  io = io || IO;
  if (!form) { form = /\.(werk|zip)$/i.test(out) ? "zip" : "directory"; }
  var built = this.build(form);
  writeContainer(io, out, form, this, built);
  return sha256Hex(built.manifestBytes);
};

// A "source" is anything with blobOrder/blobs/blobBytes/blobCrc (a writer or a rewrite).
function writeZipTo(sink, src, built) {
  var all = src.blobOrder.slice(0), i, p;
  all.push(MANIFEST);
  if (built.signatureBytes) { all.push(SIGNATURE); }
  var order = physicalOrder(all, built.manifest.container && built.manifest.container.entry_order ? built.manifest.container.entry_order : []);
  var zw = new ZipWriter(sink, built.created || src.created);
  for (i = 0; i < order.length; i++) {
    p = order[i];
    if (p === MANIFEST) { zw.add(p, built.manifestBytes); }
    else if (p === SIGNATURE) { zw.add(p, built.signatureBytes); }
    else { var b = src.blobs["/" + p]; zw.add(p, src.blobBytes(b), src.blobCrc(b)); }
  }
  zw.close();
}

function writeContainer(io, out, form, src, built) {
  var i;
  if (form === "zip") {
    var tmp = out + ".partial", w = io.openWriter(tmp);
    try { writeZipTo(w, src, built); } finally { w.close(); }
    io.remove(out);
    io.rename(tmp, out);
    return;
  }
  if (form !== "directory") { throw new WerkError("form is zip or directory"); }
  if (io.exists(out) && !io.isEmptyDir(out)) { throw new WerkError(out + " exists and is not empty; a directory package is written fresh"); }
  var items = src.blobOrder.slice(0);
  for (i = 0; i < items.length; i++) {
    var full = io.join(out, items[i]);
    io.mkdirs(io.dirname(full));
    io.write(full, src.blobBytes(src.blobs["/" + items[i]]));
  }
  io.mkdirs(out);
  io.write(io.join(out, MANIFEST), built.manifestBytes);
  if (built.signatureBytes) { io.write(io.join(out, SIGNATURE), built.signatureBytes); }
}

// ---------------------------------------------------------------- rewriting: append, sign
function atMarker(path, n) {
  var slash = path.lastIndexOf("/"), d = slash >= 0 ? path.substring(0, slash) : "", name = slash >= 0 ? path.substring(slash + 1) : path;
  var dot = name.lastIndexOf(".");
  name = dot > 0 ? name.substring(0, dot) + "@" + n + name.substring(dot) : name + "@" + n;
  return d ? d + "/" + name : name;
}
function stripMarker(path) {
  var slash = path.lastIndexOf("/"), d = slash >= 0 ? path.substring(0, slash) : "", name = slash >= 0 ? path.substring(slash + 1) : path;
  name = name.replace(/@[0-9]+(?=\.[^.]*$|$)/, "");
  return d ? d + "/" + name : name;
}

function Rewrite(pkg) {
  this.pkg = pkg; this.blobs = {}; this.blobOrder = [];
  var i, j, k, n, fs;
  for (i = 0; i < pkg.nodes.length; i++) {
    n = pkg.nodes[i];
    for (j = 0; j < n.versions.length; j++) {
      fs = n.versions[j].files || [];
      for (k = 0; k < fs.length; k++) { if (!hasOwn(this.blobs, "/" + fs[k].path)) { this.blobs["/" + fs[k].path] = { data: pkg.container.read(fs[k].path) }; this.blobOrder.push(fs[k].path); } }
    }
  }
}
Rewrite.prototype.blobBytes = function (b) { return b.data; };
Rewrite.prototype.blobCrc = function () { return null; };
Rewrite.prototype.put = function (p, data) { if (!hasOwn(this.blobs, "/" + p)) { this.blobOrder.push(p); } this.blobs["/" + p] = { data: data }; };
Rewrite.prototype.move = function (from, to) {
  this.blobs["/" + to] = this.blobs["/" + from]; delete this.blobs["/" + from];
  this.blobOrder[indexOf(this.blobOrder, from)] = to;
};

function containerForm(out, form) { return form ? form : (/\.(werk|zip)$/i.test(out) ? "zip" : "directory"); }

// opts: epistemic, producer, created, nodeType, meta, edges, inputFiles, inputParams,
//       payloadFile, form, signKey, signer {uri, kind, name, role, note, signedAt}, dropSignature
function appendVersion(src, out, nodeId, files, note, opts) {
  opts = opts || {};
  var io = opts.io || IO;
  var pkg = new Package(openContainer(io, src), src), i, j, k;
  if (pkg.errors().length) { var cs = []; for (i = 0; i < pkg.errors().length; i++) { cs.push(pkg.errors()[i].code); } throw new WerkError("refusing to append to a package that does not verify clean: " + cs.join("; ")); }
  var created = opts.created || utcNow();
  dosDateTime(created);
  checkNote(note);
  var m = pkg.manifest, rw = new Rewrite(pkg), owners = {};
  for (i = 0; i < m.nodes.length; i++) { for (j = 0; j < m.nodes[i].versions.length; j++) { var fs0 = m.nodes[i].versions[j].files; for (k = 0; k < fs0.length; k++) { owners["/" + fs0[k].path] = m.nodes[i].node_id; } } }
  var prod = opts.producer || { tool: "werk", version: LIB_VERSION };
  var ep = opts.epistemic || "authored";
  var raw = null;
  for (i = 0; i < m.nodes.length; i++) { if (m.nodes[i].node_id === nodeId) { raw = m.nodes[i]; } }
  var newRecs = [];
  for (i = 0; i < files.length; i++) {
    var r = { path: files[i].path, sha256: sha256Hex(files[i].data), size: B.len(files[i].data) };
    if (files[i].mediaType) { r.media_type = files[i].mediaType; }
    if (files[i].role) { r.role = files[i].role; }
    newRecs.push({ rec: r, data: files[i].data });
  }
  function ihash(inputs, params) {
    var ds = [];
    for (var q = 0; q < inputs.length; q++) { ds.push(sha256(rw.blobs["/" + inputs[q]].data)); }
    return inputHashOf(ds, params);
  }
  var ip = opts.inputFiles ? (opts.inputParams === undefined || opts.inputParams === null ? {} : opts.inputParams) : null;
  var pf = opts.payloadFile === undefined ? null : opts.payloadFile, roled;
  if (raw === null) {
    if (!opts.nodeType) { throw new WerkError("no node " + nodeId + "; pass nodeType to add it"); }
    checkId(nodeId, "node_id");
    if (!TYPE_RE.test(opts.nodeType)) { throw new WerkError("bad node type " + opts.nodeType); }
    var recs = [];
    for (i = 0; i < newRecs.length; i++) {
      if (hasOwn(owners, "/" + newRecs[i].rec.path)) { throw new WerkError(newRecs[i].rec.path + " already belongs to node " + owners["/" + newRecs[i].rec.path]); }
      rw.put(newRecs[i].rec.path, newRecs[i].data);
      recs.push(newRecs[i].rec);
    }
    if (pf === null && recs.length > 1) { roled = []; for (i = 0; i < recs.length; i++) { if (recs[i].role === "payload") { roled.push(recs[i].path); } } if (roled.length === 1) { pf = roled[0]; } }
    var node = { node_id: nodeId, type: opts.nodeType,
      versions: [versionRecord(1, recs, note, prod, ep, created, pf, null, opts.inputFiles || null, ip, opts.inputFiles ? ihash(opts.inputFiles, ip) : null)],
      active: 1, edges: [] };
    var es = opts.edges || [];
    for (i = 0; i < es.length; i++) { node.edges.push(makeEdge(es[i])); }
    if (opts.meta !== undefined && opts.meta !== null) { node.meta = opts.meta; }
    m.nodes.push(node);
    var bi = defaultBundle().info;
    if (hasOwn(bi.schemas_by_type, opts.nodeType) && isObj(m.schemas) && !hasOwn(m.schemas, opts.nodeType)) { m.schemas[opts.nodeType] = bi.schemas_by_type[opts.nodeType]; }
    if (hasOwn(bi.layouts_by_type, opts.nodeType) && isObj(m.layouts) && !hasOwn(m.layouts, opts.nodeType)) { m.layouts[opts.nodeType] = bi.layouts_by_type[opts.nodeType]; }
  } else {
    var vs = raw.versions, cur = null, newv = 0;
    for (i = 0; i < vs.length; i++) { if (vs[i].v === raw.active) { cur = vs[i]; } if (vs[i].v > newv) { newv = vs[i].v; } }
    newv += 1;
    var given = {}, givenOrder = [], seen = {}, outFiles = [];
    for (i = 0; i < newRecs.length; i++) { given["/" + newRecs[i].rec.path] = newRecs[i]; givenOrder.push(newRecs[i].rec.path); }
    for (i = 0; i < cur.files.length; i++) {
      var f = cur.files[i], logical = stripMarker(f.path);
      if (hasOwn(given, "/" + logical)) {
        var g = given["/" + logical];
        seen["/" + logical] = true;
        if (g.rec.sha256 === f.sha256 && g.rec.size === f.size && f.path === logical) { outFiles.push(f); continue; }
        if (f.path === logical) {
          var intro = null;
          for (j = 0; j < vs.length; j++) { for (k = 0; k < vs[j].files.length; k++) { if (vs[j].files[k].path === logical && vs[j].files[k].sha256 === f.sha256 && (intro === null || vs[j].v < intro)) { intro = vs[j].v; } } }
          var moved = atMarker(logical, intro);
          if (hasOwn(owners, "/" + moved)) { throw new WerkError(moved + " already exists; cannot supersede " + logical); }
          for (j = 0; j < vs.length; j++) {
            for (k = 0; k < vs[j].files.length; k++) { if (vs[j].files[k].path === logical) { vs[j].files[k].path = moved; } }
          }
          rw.move(logical, moved);
          owners["/" + moved] = nodeId;
          for (j = 0; j < vs.length; j++) { if (vs[j].payload_file === logical) { vs[j].payload_file = moved; } }
        }
        rw.put(logical, g.data);
        owners["/" + logical] = nodeId;
        outFiles.push(g.rec);
      } else { outFiles.push(f); }
    }
    for (i = 0; i < givenOrder.length; i++) {
      var lg = givenOrder[i];
      if (hasOwn(seen, "/" + lg)) { continue; }
      if (hasOwn(owners, "/" + lg) && owners["/" + lg] !== nodeId) { throw new WerkError(lg + " belongs to node " + owners["/" + lg]); }
      if (hasOwn(rw.blobs, "/" + lg)) { throw new WerkError(lg + " is a file of an earlier version; give it a new path"); }
      rw.put(lg, given["/" + lg].data);
      owners["/" + lg] = nodeId;
      outFiles.push(given["/" + lg].rec);
    }
    if (pf === null && outFiles.length > 1) {
      var cpf = typeof cur.payload_file === "string" ? stripMarker(cur.payload_file) : null, has = false;
      for (i = 0; i < outFiles.length; i++) { if (outFiles[i].path === cpf) { has = true; } }
      if (has) { pf = cpf; }
      else { roled = []; for (i = 0; i < outFiles.length; i++) { if (outFiles[i].role === "payload") { roled.push(outFiles[i].path); } } if (roled.length === 1) { pf = roled[0]; } }
    }
    vs.push(versionRecord(newv, outFiles, note, prod, ep, created, pf, null, opts.inputFiles || null, ip, opts.inputFiles ? ihash(opts.inputFiles, ip) : null));
    raw.active = newv;
    if (opts.meta !== undefined && opts.meta !== null) { raw.meta = opts.meta; }
  }
  finishRewrite(io, pkg, m, rw, out, containerForm(out, opts.form), created, opts, opts.preview && newRecs.length ? newRecs[0].rec.path : null);
  return out;
}

function finishRewrite(io, pkg, m, rw, out, form, created, opts, previewPath) {
  var i, j, k;
  m.spec_sha256 = specSha256Of(m.nodes);
  var cont = m.container;
  if (isObj(cont)) {
    cont.form = form;
    if (hasOwn(cont, "total_size_bytes")) {
      var sizes = {}, keys = [], tot = 0;
      for (i = 0; i < m.nodes.length; i++) { for (j = 0; j < m.nodes[i].versions.length; j++) { var fs = m.nodes[i].versions[j].files; for (k = 0; k < fs.length; k++) { if (!hasOwn(sizes, "/" + fs[k].path)) { keys.push(fs[k].path); } sizes["/" + fs[k].path] = fs[k].size; } } }
      for (i = 0; i < keys.length; i++) { tot += sizes["/" + keys[i]]; }
      cont.total_size_bytes = tot;
    }
    if (previewPath && isArray(cont.entry_order) && !contains(cont.entry_order, previewPath)) { cont.entry_order.push(previewPath); }
  }
  var mb = jsonPretty(m), sb = null, hadSig = pkg.signatureState !== SIG_ABSENT;
  if (opts.signKey) {
    var existing = hadSig ? jsonParseBytes(pkg.container.read(SIGNATURE)) : null, sg = opts.signer || {};
    var doc = chainAppend(existing, sha256Hex(mb), parseSecretKey(opts.signKey), sg.uri || "urn:werk:anonymous", sg.kind || "human",
                          sg.name || sg.uri || "urn:werk:anonymous", sg.signedAt || created, sg.role === undefined ? "author" : sg.role, sg.note || null);
    sb = jsonPretty(doc);
  } else if (hadSig && !opts.dropSignature) {
    throw new WerkError("the package is signed; a changed manifest needs a new chain entry (pass a signing key) or dropSignature. Leaving the old chain in place would make the package present-and-invalid");
  }
  writeContainer(io, out, form, rw, { manifest: m, manifestBytes: mb, signatureBytes: sb, created: created });
}

function signPackage(src, out, key, uri, opts) {
  opts = opts || {};
  var io = opts.io || IO;
  var pkg = new Package(openContainer(io, src), src);
  if (pkg.signatureState === SIG_INVALID) { throw new WerkError("the existing chain is present-and-invalid; refusing to extend it"); }
  var at = opts.signedAt || utcNow();
  var existing = pkg.signatureState !== SIG_ABSENT ? jsonParseBytes(pkg.container.read(SIGNATURE)) : null;
  var doc = chainAppend(existing, pkg.manifestSha256, parseSecretKey(key), uri, opts.kind || "human", opts.name || uri, at, opts.role === undefined ? "author" : opts.role, opts.note || null);
  var rw = new Rewrite(pkg);
  writeContainer(io, out, containerForm(out, opts.form), rw, { manifest: pkg.manifest, manifestBytes: pkg.manifestBytes, signatureBytes: jsonPretty(doc), created: at });
  return out;
}

// ---------------------------------------------------------------- profile helpers
function pngInfo(d) {
  var sig = [0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A], i;
  for (i = 0; i < 8; i++) { if (B.len(d) < 26 || B.at(d, i) !== sig[i]) { throw new WerkError("not a PNG (MINI-SPECS section 8)"); } }
  if (!bytesEqAscii(d, 12, "IHDR")) { throw new WerkError("not a PNG (no IHDR)"); }
  function be32(o) { return B.at(d, o) * 16777216 + (B.at(d, o + 1) << 16) + (B.at(d, o + 2) << 8) + B.at(d, o + 3); }
  var w = be32(16), h = be32(20), depth = B.at(d, 24), ct = B.at(d, 25);
  var ch = { 0: 1, 2: 3, 3: 3, 4: 2, 6: 4 }[ct];
  if (ch === undefined) { throw new WerkError("PNG colour type " + ct + " is not defined"); }
  if (ct === 3) { depth = 8; }
  return { width: w, height: h, channels: ch, bitDepth: depth, hasAlpha: ct === 4 || ct === 6 };
}
function glbInfo(d) {
  if (B.len(d) < 20 || !bytesEqAscii(d, 0, "glTF")) { throw new WerkError("not a GLB (magic glTF)"); }
  if (u32(d, 4) !== 2 || u32(d, 8) !== B.len(d)) { throw new WerkError("GLB version or length does not match the file"); }
  if (u32(d, 16) !== 0x4E4F534A) { throw new WerkError("the first GLB chunk is not JSON"); }
  var j = B.slice(d, 20, 20 + u32(d, 12)), n = B.len(j);
  while (n > 0 && (B.at(j, n - 1) === 0x20 || B.at(j, n - 1) === 0)) { n--; }
  return jsonParseBytes(B.slice(j, 0, n));
}
function signerFromOpts(w, opts) {
  if (opts.signKey) { var sg = opts.signer || {}; w.sign(opts.signKey, sg.uri || "urn:werk:anonymous", { kind: sg.kind || "human", name: sg.name, role: sg.role, note: sg.note, signedAt: sg.signedAt }); }
}
function attach(w, atts) {
  var i, j;
  for (i = 0; i < (atts || []).length; i++) {
    var a = atts[i], fs = [];
    for (j = 0; j < a.files.length; j++) { var f = a.files[j]; fs.push(file(f[0], f[1], f[2], f[3])); }
    w.addNode(a.nodeId, a.type, fs, { note: a.note || "A file attached by the writing application.", meta: a.meta });
  }
}
function addReadmeFiles(w, rfs) {
  for (var q = 0; q < (rfs || []).length; q++) { w.addReadmeFile(rfs[q][0], rfs[q][1], rfs[q][2]); }
}
function commonWriterOpts(opts) {
  return { name: opts.name, summary: opts.summary, uuid: opts.uuid, created: opts.created, licenseText: opts.licenseText,
           spdxId: opts.spdxId, producer: opts.producer, generator: opts.generator, specFiles: opts.specFiles, conventionsMap: opts.conventionsMap };
}
// opts: name (req), summary, uuid, created, thumbnailPng, thumbnailParams, recipe, disclosure,
//       epistemic, model, inputFiles, licenseText, spdxId, producer, generator, signKey, signer,
//       form, attachments, sourcePath, colorSpace
function buildImagePackage(png, opts) {
  opts = opts || {};
  var w = new PackageWriter("image/1", commonWriterOpts(opts)), info = pngInfo(png), cs = opts.colorSpace || "srgb";
  addReadmeFiles(w, opts.readmeFiles);
  var sp = opts.sourcePath || "image/source.png";
  var meta = { width: info.width, height: info.height, channels: info.channels, bit_depth: info.bitDepth, color_space: cs, encoding: "png", has_alpha: info.hasAlpha };
  var prod = null, ep = opts.epistemic || "authored";
  if (opts.model) { var base = opts.producer || w.producer; prod = { tool: base.tool, version: base.version, model: opts.model }; }
  if (ep !== "authored" && !(opts.inputFiles && opts.inputFiles.length)) { throw new WerkError("an inferred image names its inputs: pass inputFiles"); }
  if (opts.recipe) {
    w.addNode("recipe", "core.recipe", [file("recipe/recipe.json", jsonPretty(opts.recipe), "application/json", "record")], { note: "The reproduction record of the generation (SPEC section 3.11)." });
    w.preview("recipe/recipe.json");
  }
  w.addNode("image-source", "core.image.source", [file(sp, png, "image/png")], { note: "The image as the process that made it delivered it.", epistemic: ep, producer: prod, meta: meta, inputFiles: opts.inputFiles || null });
  w.setPrimary("image", "image-source");
  if (opts.thumbnailPng) {
    var t = pngInfo(opts.thumbnailPng), tp = opts.thumbnailParams;
    var tmeta = { width: t.width, height: t.height, channels: t.channels, bit_depth: t.bitDepth, color_space: cs, encoding: "png", has_alpha: t.hasAlpha, derived_role: "thumbnail", resample: (tp && tp.resample) || "box" };
    w.addNode("image-thumb", "core.image.derived", [file("image/thumb.png", opts.thumbnailPng, "image/png")],
      { note: "The listing thumbnail, a downscale of the source image.", epistemic: "measured", meta: tmeta, inputFiles: [sp],
        inputParams: tp || { resample: "box", width: t.width, height: t.height },
        edges: [{ to: "image-source", kind: "requires", role: "derived-from" }] });
    w.setPrimary("thumbnail", "image-thumb");
    w.preview("image/thumb.png");
  }
  if (opts.disclosure) {
    w.addNode("disclosure", "core.disclosure", [file("disclosure/disclosure.json", jsonPretty(opts.disclosure), "application/json")], { note: "The machine-readable synthetic-content facts (SPEC section 3.12)." });
  }
  attach(w, opts.attachments);
  signerFromOpts(w, opts);
  return w;
}
function defaultMaterial(id, name, tex) {
  var m = { material_id: id, name: name, model: "metallic-roughness", base_color_factor: [1, 1, 1, 1], metallic_factor: 0, roughness_factor: 1, alpha_mode: "opaque", double_sided: false };
  if (tex) { m.textures = { base_color: { node: tex[0], path: tex[1], uv_set: 0 } }; }
  m.epistemic = "authored";
  return m;
}
// opts: name (req) ..., textures: [{id, png, usage, colorSpace, normalConvention, note}],
//       materials: [{id, name, baseColor, klass, payload, note}], previewPng, partName
function buildMeshPackage(glb, opts) {
  opts = opts || {};
  var w = new PackageWriter("3d-entity/1", commonWriterOpts(opts)), i, texIds = {};
  addReadmeFiles(w, opts.readmeFiles);
  glbInfo(glb);
  w.addPart("body", opts.partName || "Body");
  w.addNode("geom-game", "core.geom.game", [file("geometry/game.glb", glb, "model/gltf-binary")], { note: "The mesh to render, as the authoring application exported it.", partId: "body" });
  w.setPrimary("mesh", "geom-game");
  w.setPrimary("geometry", "geom-game");
  var texs = opts.textures || [];
  for (i = 0; i < texs.length; i++) {
    var t = texs[i], inf = pngInfo(t.png), usage = t.usage || "base-color";
    checkId(t.id, "texture id");
    var meta = { color_space: t.colorSpace || (usage === "base-color" || usage === "emissive" ? "srgb" : "linear"), usage: usage, width: inf.width, height: inf.height, channels: inf.channels, bit_depth: inf.bitDepth };
    if (usage === "normal") { meta.normal_convention = t.normalConvention || "opengl-y-up"; }
    var path = "textures/" + t.id + ".png";
    w.addNode("tex-" + t.id, "core.tex", [file(path, t.png, "image/png")], { note: t.note || "A texture of the mesh, as exported.", meta: meta, partId: "body" });
    texIds["/" + t.id] = ["tex-" + t.id, path];
  }
  var mats = opts.materials || [];
  for (i = 0; i < mats.length; i++) {
    var mt = mats[i];
    checkId(mt.id, "material id");
    w.addMaterial(mt.id, mt.name || mt.id, "body", mt.klass);
    var payload = mt.payload || defaultMaterial(mt.id, mt.name || mt.id, mt.baseColor ? texIds["/" + mt.baseColor] : null);
    var edges = mt.baseColor ? [{ to: texIds["/" + mt.baseColor][0], kind: "enhances", role: "base-color" }] : [];
    w.addNode("mat-" + mt.id, "core.material", [file("materials/" + mt.id + ".json", jsonPretty(payload), "application/json")],
      { note: mt.note || "Material parameters of the mesh, as exported.", materialId: mt.id, partId: "body", edges: edges });
  }
  if (opts.previewPng) {
    var pi = pngInfo(opts.previewPng);
    w.addNode("preview", "core.tex", [file("preview/preview.png", opts.previewPng, "image/png")],
      { note: "A still of the entity for listings, rendered by the authoring application.",
        meta: { color_space: "srgb", usage: "other", width: pi.width, height: pi.height, channels: pi.channels, bit_depth: pi.bitDepth } });
    w.setPrimary("image", "preview");
    w.preview("preview/preview.png");
  }
  attach(w, opts.attachments);
  signerFromOpts(w, opts);
  return w;
}

// ---------------------------------------------------------------- CLI (shared by the Node and the ES3 builds)
var USAGE = "werk " + LIB_VERSION + " -- read and write werk packages (JavaScript, no dependencies)\n\n" +
  "  werk info    <pkg>\n  werk verify  <pkg> [--json] [--strict]\n  werk extract <pkg> <out-dir> [--node ID ...] [--all-versions]\n" +
  "  werk cat     <pkg> <path> | --payload NODE [--version N]\n" +
  "  werk pack-image <out> --png F --name N [--thumb F] [--recipe F] [--disclosure F] [...]\n" +
  "  werk pack-mesh  <out> --glb F --name N [--texture ID=F[:usage]] [--material ID[:tex]] [--preview F]\n" +
  "  werk append  <pkg> <out> --node ID --file PKGPATH=FILE ... --note TEXT [--type T]\n" +
  "  werk sign    <pkg> <out> --sign-key HEX --signer-uri U [--signer-kind K]\n\n" +
  "Options and exit statuses are those of the Python CLI (libs/README.md).\n";

function cliArgs(argv, multi, flags) {
  var pos = [], opt = {}, i = 0;
  while (i < argv.length) {
    var a = argv[i];
    if (a.substring(0, 2) === "--") {
      var k = a.substring(2);
      if (contains(flags, k)) { opt[k] = true; i++; continue; }
      if (i + 1 >= argv.length) { throw new WerkError("option " + a + " needs a value", "usage"); }
      if (contains(multi, k)) { if (!hasOwn(opt, k)) { opt[k] = []; } opt[k].push(argv[i + 1]); } else { opt[k] = argv[i + 1]; }
      i += 2;
    } else { pos.push(a); i++; }
  }
  return { pos: pos, opt: opt };
}

function cli(argv, io) {
  io = io || IO;
  if (!argv.length || argv[0] === "-h" || argv[0] === "--help" || argv[0] === "help") { io.stdout(USAGE); return argv.length ? 0 : 2; }
  var cmd = argv[0], a, pos, opt, pkg, i;
  function readText(p) { return utf8Decode(io.read(p)); }
  function signer() {
    if (!hasOwn(opt, "sign-key")) { return null; }
    var key = opt["sign-key"];
    if (io.isFile(key)) { key = readText(key); }
    var s = { uri: opt["signer-uri"] || "urn:werk:anonymous", kind: opt["signer-kind"] || "human", role: opt["signer-role"] || "author" };
    if (opt["signer-name"]) { s.name = opt["signer-name"]; }
    if (opt["signed-at"]) { s.signedAt = opt["signed-at"]; }
    return { key: key, signer: s };
  }
  function attachments() {
    var out = [], specs = opt.attach || [], j;
    for (j = 0; j < specs.length; j++) {
      var eq = specs[j].indexOf("="), head = specs[j].substring(0, eq), local = specs[j].substring(eq + 1), parts = head.split(":");
      if (eq < 0 || parts.length !== 3 || !local) { throw new WerkError("--attach is ID:TYPE:PKGPATH=FILE", "usage"); }
      out.push({ nodeId: parts[0], type: parts[1], files: [[parts[2], io.read(local)]] });
    }
    return out;
  }
  try {
    a = cliArgs(argv.slice(1), ["attach", "texture", "material", "file", "node", "input", "spec-file", "readme-file"], ["json", "strict", "dir", "all-versions", "drop-signature"]);
    pos = a.pos; opt = a.opt;
    if (cmd === "info" || cmd === "verify" || cmd === "extract" || cmd === "cat") {
      if (!pos.length) { throw new WerkError(cmd + " needs a package", "usage"); }
      try { pkg = new Package(openContainer(io, pos[0]), pos[0]); }
      catch (e) {
        if (e.refusal) {
          if (cmd === "verify" && opt.json) { io.stdout(utf8Decode(jsonPretty({ exit: 2, refusal: e.code }))); }
          io.stderr("[error] " + e.code + ": " + e.detail + "\ncontainer-scoped refusal: nothing was loaded; exit status 2\n");
          return 2;
        }
        throw e;
      }
      if (cmd === "verify") {
        var v = pkg.verdict();
        if (opt.strict) { for (i = 0; i < pkg.report.length; i++) { if (pkg.report[i].severity === "warn") { v.exit = 1; v.strict_promoted_warnings = true; } } }
        if (opt.json) { io.stdout(utf8Decode(jsonPretty(v))); }
        else {
          for (i = 0; i < pkg.report.length; i++) { io.stdout("[" + pkg.report[i].severity + "] " + pkg.report[i].code + ": " + pkg.report[i].message + "\n"); }
          var c = pkg.census();
          io.stdout("profile    : " + pkg.profile + "\nsignature  : " + pkg.signatureState + "\ncensus     : " + pkg.nodes.length + " nodes: " + c.alive + " alive, " + c.skipped + " skipped, " + c.dead + " dead\nspec_sha256: " + (v.spec_sha256_ok ? "ok" : "MISMATCH") + "\n" + pkg.errors().length + " error(s), " + pkg.report.length + " report entries\n");
        }
        return v.exit;
      }
      if (cmd === "info") {
        var mm = pkg.manifest, ent = isObj(mm.entity) ? mm.entity : {};
        io.stdout("entity     : " + ent.name + " (" + ent.uuid + ")\nprofile    : " + pkg.profile + "   form: " + pkg.form + "   signature: " + pkg.signatureState + "\n");
        for (i = 0; i < pkg.nodes.length; i++) {
          var n = pkg.nodes[i], pp = "";
          if (n.resolved !== null) { try { pp = payloadPathOf(n, n.version()); } catch (e3) { pp = "(payload ambiguous)"; } }
          io.stdout("  " + n.nodeId + "  " + n.type + "  v" + (n.resolved === null ? "-" : n.resolved) + "  " + n.status + "  " + pp + "\n");
        }
        for (i = 0; i < pkg.report.length; i++) { io.stdout("[" + pkg.report[i].severity + "] " + pkg.report[i].code + ": " + pkg.report[i].message + "\n"); }
        return pkg.errors().length ? 1 : 0;
      }
      if (cmd === "extract") {
        if (pos.length < 2) { throw new WerkError("extract needs <pkg> <out-dir>", "usage"); }
        var wr = pkg.extract(pos[1], opt.node || null, !!opt["all-versions"], io);
        io.stdout(wr.length + " file(s) written under " + pos[1] + "\n");
        return pkg.errors().length ? 1 : 0;
      }
      if (opt.payload) { io.stdoutBytes(pkg.readPayload(opt.payload, opt.version ? parseInt(opt.version, 10) : null)); }
      else if (pos.length >= 2) { io.stdoutBytes(pkg.readFile(pos[1])); }
      else { throw new WerkError("cat needs a path or --payload NODE", "usage"); }
      return 0;
    }
    if (cmd === "pack-image" || cmd === "pack-mesh") {
      if (!pos.length || !opt.name) { throw new WerkError(cmd + " needs <out> and --name", "usage"); }
      var out = pos[0], form = opt.dir ? "directory" : containerForm(out, null), sg = signer(), w;
      var common = { name: opt.name, summary: opt.summary, uuid: opt.uuid, created: opt.created,
        licenseText: opt.license ? readText(opt.license) : null, spdxId: opt.spdx, attachments: attachments() };
      var sfs = opt["spec-file"] || [], sfo = null;
      for (i = 0; i < sfs.length; i++) {
        var e3 = sfs[i].indexOf("=");
        if (e3 < 0) { throw new WerkError("--spec-file is PKGPATH=FILE (PKGPATH under spec/)", "usage"); }
        if (!sfo) { sfo = {}; }
        sfo[sfs[i].substring(0, e3)] = io.read(sfs[i].substring(e3 + 1));
      }
      common.specFiles = sfo;
      if (opt["conventions-map"]) { common.conventionsMap = opt["conventions-map"]; }
      var rfs = opt["readme-file"] || [];
      common.readmeFiles = [];
      for (i = 0; i < rfs.length; i++) {
        var e4 = rfs[i].indexOf("=");
        if (e4 < 0) { throw new WerkError("--readme-file is PKGPATH=FILE", "usage"); }
        common.readmeFiles.push([rfs[i].substring(0, e4), io.read(rfs[i].substring(e4 + 1))]);
      }
      if (sg) { common.signKey = sg.key; common.signer = sg.signer; }
      if (cmd === "pack-image") {
        if (!opt.png) { throw new WerkError("pack-image needs --png", "usage"); }
        common.thumbnailPng = opt.thumb ? io.read(opt.thumb) : null;
        common.recipe = opt.recipe ? jsonParseBytes(io.read(opt.recipe)) : null;
        common.disclosure = opt.disclosure ? jsonParseBytes(io.read(opt.disclosure)) : null;
        common.model = opt.model; common.epistemic = opt.epistemic; common.inputFiles = opt.input || null;
        w = buildImagePackage(io.read(opt.png), common);
      } else {
        if (!opt.glb) { throw new WerkError("pack-mesh needs --glb", "usage"); }
        var tx = [], mats = [], specs = opt.texture || [];
        for (i = 0; i < specs.length; i++) {
          var e1 = specs[i].indexOf("="), tid = specs[i].substring(0, e1), rest = specs[i].substring(e1 + 1), fpath = rest, usage = "base-color";
          if (rest.indexOf(":") >= 0 && !io.exists(rest)) { var c1 = rest.lastIndexOf(":"); fpath = rest.substring(0, c1); usage = rest.substring(c1 + 1); }
          tx.push({ id: tid, png: io.read(fpath), usage: usage });
        }
        specs = opt.material || [];
        for (i = 0; i < specs.length; i++) { var c2 = specs[i].indexOf(":"), mid = c2 >= 0 ? specs[i].substring(0, c2) : specs[i], tex = c2 >= 0 ? specs[i].substring(c2 + 1) : ""; mats.push({ id: mid, name: mid, baseColor: tex || null }); }
        common.textures = tx; common.materials = mats; common.previewPng = opt.preview ? io.read(opt.preview) : null;
        w = buildMeshPackage(io.read(opt.glb), common);
      }
      w.write(out, form, io);
      io.stdout("wrote " + out + "\n");
      return 0;
    }
    if (cmd === "append") {
      if (pos.length < 2 || !opt.node || !opt.note || !opt.file) { throw new WerkError("append needs <pkg> <out> --node ID --file PKGPATH=FILE --note TEXT", "usage"); }
      var files = [];
      for (i = 0; i < opt.file.length; i++) { var e2 = opt.file[i].indexOf("="); files.push(file(opt.file[i].substring(0, e2), io.read(opt.file[i].substring(e2 + 1)))); }
      var s2 = signer(), ao = { epistemic: opt.epistemic, created: opt.created, nodeType: opt.type, dropSignature: !!opt["drop-signature"], form: opt.dir ? "directory" : null };
      if (s2) { ao.signKey = s2.key; ao.signer = s2.signer; }
      ao.io = io;
      appendVersion(pos[0], pos[1], opt.node[0], files, opt.note, ao);
      io.stdout("wrote " + pos[1] + "\n");
      return 0;
    }
    if (cmd === "sign") {
      var s3 = signer();
      if (pos.length < 2 || !s3) { throw new WerkError("sign needs <pkg> <out> --sign-key HEX", "usage"); }
      signPackage(pos[0], pos[1], s3.key, s3.signer.uri, { kind: s3.signer.kind, name: s3.signer.name, role: s3.signer.role, signedAt: opt["signed-at"], form: opt.dir ? "directory" : null, io: io });
      io.stdout("wrote " + pos[1] + "\n");
      return 0;
    }
    throw new WerkError("unknown command " + cmd, "usage");
  } catch (err) {
    if (err instanceof WerkError) {
      if (err.code === "usage") { io.stderr("werk: " + err.message + "\n\n" + USAGE); return 2; }
      if (err.refusal) { io.stderr("[error] " + err.code + ": " + err.detail + "\n"); return 2; }
      io.stderr("werk: " + err.message + "\n");
      return 1;
    }
    throw err;
  }
}
