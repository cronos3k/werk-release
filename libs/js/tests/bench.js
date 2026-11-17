// bench.js -- MB/s of sha256, crc32 and inflateRaw in both builds, under Node.
//   node js/tests/bench.js [MB]
// The ES3 build (werk.jsx) is run on binary strings exactly as ExtendScript
// would run it; the numbers are V8's, not ExtendScript's (see
// extendscript_bench.jsx for the in-host measurement).
var zlib = require("zlib"), path = require("path");
var MB = parseFloat(process.argv[2] || "8");
var n = Math.floor(MB * 1048576), raw = Buffer.alloc(n), x = 12345, i;
for (i = 0; i < n; i++) { x = (x * 1103515245 + 12345) & 0x7fffffff; raw[i] = (i % 97 < 60) ? 65 + (i % 26) : (x >>> 16) & 255; }
var deflated = zlib.deflateRawSync(raw, { level: 6 });
var refSha = require("crypto").createHash("sha256").update(raw).digest("hex");
var refCrc = zlib.crc32 ? zlib.crc32(raw) >>> 0 : null;
function time(f) { var t = process.hrtime.bigint(); var r = f(); return [r, Number(process.hrtime.bigint() - t) / 1e9]; }
["werk.js", "werk.jsx"].forEach(function (build) {
  var werk = require(path.join(__dirname, "..", "dist", build));
  var data = werk.B.kind === "uint8array" ? new Uint8Array(raw) : raw.toString("latin1");
  var def = werk.B.kind === "uint8array" ? new Uint8Array(deflated) : deflated.toString("latin1");
  var s = time(function () { return werk.sha256Hex(data); });
  var c = time(function () { return werk.crc32(data); });
  var f = time(function () { return werk.inflateRaw(def, n); });
  var g = time(function () { return werk.inflateRaw(def); });
  var same = werk.B.kind === "uint8array" ? Buffer.from(f[0]).equals(raw) : f[0] === raw.toString("latin1");
  console.log(build + ": sha256 " + (MB / s[1]).toFixed(1) + " MB/s (" + (s[0] === refSha ? "ok" : "WRONG") + "), crc32 " +
    (MB / c[1]).toFixed(1) + " MB/s (" + (refCrc === null || c[0] === refCrc ? "ok" : "WRONG") + "), inflate " +
    (MB / f[1]).toFixed(1) + " MB/s out (" + (same ? "ok" : "WRONG") + "; " + deflated.length + " -> " + n + " bytes), no-limit call " +
    (B_len(g[0], werk) === n ? "ok" : "WRONG"));
});
function B_len(b, werk) { return werk.B.len(b); }
