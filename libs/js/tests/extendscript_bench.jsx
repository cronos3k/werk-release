// extendscript_bench.jsx -- sha256 / crc32 / inflateRaw throughput of werk.jsx
// inside a real ExtendScript host. WERK_ARGS = {dir: <libs>/_scratch, builds:
// [{name, path, sizes: {sha: "256k", crc: "256k", inflate: "64k"}, sinks: [...]}]}.
// Returns one line per measurement: build op size bytes ms MB/s check.
(function () {
  var out = [], A = WERK_ARGS;
  function rd(name) { var f = new File(A.dir + "/" + name); f.encoding = "BINARY"; f.open("r"); var s = f.read(); f.close(); return s; }
  function ms(f) { var t = new Date().getTime(); var r = f(); return [r, new Date().getTime() - t]; }
  function line(b, op, size, bytes, t, check) {
    var pf = new File(A.dir + "/es-bench-progress.txt"); pf.encoding = "UTF-8"; pf.open("a");
    pf.writeln(b + " " + op + " " + size + " " + t + " ms " + check); pf.close();
    out.push(b + " " + op + " " + size + " " + bytes + " bytes " + t + " ms " + (t > 0 ? (bytes / 1048576 / (t / 1000)).toFixed(3) : "inf") + " MB/s " + check);
  }
  for (var i = 0; i < A.builds.length; i++) {
    var b = A.builds[i];
    try {
      $.evalFile(new File(b.path));
      var raw = rd("bench-raw-" + b.sizes.sha + ".bin");
      var r = ms(function () { return werk.sha256Hex(raw); });
      line(b.name, "sha256", b.sizes.sha, raw.length, r[1], r[0].substring(0, 16));
      raw = rd("bench-raw-" + b.sizes.crc + ".bin");
      r = ms(function () { return werk.crc32(raw); });
      line(b.name, "crc32", b.sizes.crc, raw.length, r[1], String(r[0]));
      var want = rd("bench-raw-" + b.sizes.inflate + ".bin"), def = rd("bench-def-" + b.sizes.inflate + ".bin");
      var sinks = b.sinks || [null];
      for (var k = 0; k < sinks.length; k++) {
        if (sinks[k]) { werk.B.inflateSinkKind = sinks[k]; }
        r = ms(function () { return werk.inflateRaw(def, want.length); });
        line(b.name, "inflate" + (sinks[k] ? "-" + sinks[k] : ""), b.sizes.inflate, want.length, r[1], r[0] === want ? "ok" : "WRONG");
      }
      if (b.nolimit) {
        try { r = ms(function () { return werk.inflateRaw(def); }); line(b.name, "inflate-no-limit", b.sizes.inflate, want.length, r[1], r[0] === want ? "ok" : "WRONG"); }
        catch (e1) { out.push(b.name + " inflate-no-limit THROWS: " + e1.message); }
      }
    } catch (e) { out.push(b.name + " ERROR " + e.message + " line " + e.line); }
  }
  return out.join("\n");
})();
