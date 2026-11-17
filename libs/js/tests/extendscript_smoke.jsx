// extendscript_smoke.jsx -- the ES3 build inside a real ExtendScript engine.
// Driven by js/tests/run_extendscript.ps1, which sets WERK_T (the libs/ root,
// forward slashes) and WERK_EXPECT (sha256 the Python writer produced for the
// same input) before evaluating this file. Returns one line of key=value pairs.
(function () {
  var out = [], t0 = new Date().getTime();
  function lap() { var t = new Date().getTime(); var d = t - t0; t0 = t; return d; }
  function put(k, v) { out.push(k + "=" + v); }
  try {
    $.evalFile(new File(WERK_T + "/js/dist/werk.jsx"));
    put("engine", "ExtendScript " + $.version + " build " + $.build);
    put("app", app.name + " " + app.version);
    put("load_ms", lap());
    put("io", werk.io().name);
    var pkg = werk.open(WERK_T + "/_scratch/es-in.werk");
    var v = pkg.verdict();
    put("read_ms", lap());
    put("verify_exit", v.exit); put("signature", v.signature);
    put("census", v.alive + "/" + v.skipped + "/" + v.dead); put("spec_sha256_ok", v.spec_sha256_ok);
    var img = pkg.primaryImage();
    put("primary_image", img.path + ":" + werk.sha256Hex(img.bytes));
    put("payload_ms", lap());
    var io = werk.io(), I = WERK_T + "/_scratch/inputs/";
    var w = werk.writeImagePackage(WERK_T + "/_scratch/es-out.werk", io.read(I + "source.png"), {
      name: "Test-Größe", summary: "uni✓", uuid: "1a6e0000-0000-4000-8000-000000000001",
      created: "2026-11-07T12:00:00Z", thumbnailPng: io.read(I + "thumb.png"),
      recipe: werk.jsonParseBytes(io.read(I + "recipe.json")),
      disclosure: werk.jsonParseBytes(io.read(I + "disclosure.json")),
      signKey: werk.utf8Decode(io.read(I + "key.hex")), signer: { uri: "urn:x", kind: "service" } });
    put("write_ms", lap());
    var got = werk.sha256Hex(io.read(WERK_T + "/_scratch/es-out.werk"));
    put("written_sha256", got);
    put("byte_identical_to_python", got === WERK_EXPECT);
    put("hash_ms", lap());
    var back = werk.open(WERK_T + "/_scratch/es-out.werk").verdict();
    put("reread_exit", back.exit); put("reread_signature", back.signature);
    put("reread_ms", lap());
    // Float spelling in THIS engine against Python repr (tests/test_vectors.py
    // writes _scratch/floats.txt: IEEE-754 bits in hex, then repr).
    var ff = new File(WERK_T + "/_scratch/floats.txt");
    if (ff.exists) {
      ff.encoding = "UTF-8"; ff.open("r");
      var lines = ff.read().split("\n"), nf = 0, badf = 0, firstBad = "";
      ff.close();
      for (var li = 0; li < lines.length; li++) {
        if (li >= 2500 && li < lines.length - 13) { continue; }
        var parts = lines[li].split(" ");
        if (parts.length !== 2) { continue; }
        var hi = parseInt(parts[0].substring(0, 8), 16), lo = parseInt(parts[0].substring(8), 16);
        var sgn = hi >= 0x80000000 ? -1 : 1, ex = Math.floor(hi / 1048576) & 2047, mant = (hi % 1048576) * 4294967296 + lo;
        var x = ex === 0 ? sgn * mant * Math.pow(2, -1074) : sgn * (1 + mant / 4503599627370496) * Math.pow(2, ex - 1023);
        if (x === 0 && sgn < 0) { x = -0; }
        if (ex === 2047) { continue; }
        nf++;
        if (werk.pyFloat(x) !== parts[1]) { badf++; if (!firstBad) { firstBad = parts[1] + "->" + werk.pyFloat(x); } }
      }
      put("floats_checked", nf); put("floats_differ", badf);
      if (firstBad) { put("first_float_diff", firstBad); }
      put("float_ms", lap());
    }
  } catch (e) {
    put("ERROR", (e && e.message) ? e.message : String(e));
    if (e && e.line) { put("line", e.line); }
  }
  return out.join(" ");
})();
