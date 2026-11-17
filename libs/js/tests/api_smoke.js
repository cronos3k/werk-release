// api_smoke.js -- the JavaScript API as libs/README.md shows it, on both builds.
//   node js/tests/api_smoke.js <libs/_scratch/inputs dir>
var fs = require("fs"), path = require("path");
var I = process.argv[2], OUT = path.join(__dirname, "..", "..", "_scratch", "api-js"), fails = 0;
fs.rmSync(OUT, { recursive: true, force: true }); fs.mkdirSync(OUT, { recursive: true });
function check(n, ok, d) { console.log((ok ? "PASS " : "FAIL ") + n + (d ? " " + d : "")); if (!ok) { fails++; } }
["werk.js", "werk.jsx"].forEach(function (build) {
  var werk = require("../dist/" + build), io = werk.io();
  var png = io.read(path.join(I, "source.png")), glb = io.read(path.join(I, "triangle.glb"));
  // read, 3 lines
  var pkg = werk.open(path.join(I, "..", "img2.werk"));
  var v = pkg.verdict();
  check(build + " open + verdict", v.exit === 0 && v.signature === "signed-and-valid", JSON.stringify([v.alive, v.dead]));
  var img = pkg.primaryImage();
  check(build + " primaryImage", img.nodeId === "image-source" && werk.sha256Hex(img.bytes) === "564ee5f1f8ff4190b4683e3de4ec8775966988ae8be4de3a5aee61d643090b7d");
  // write
  var out = path.join(OUT, build + "-sunset.werk");
  werk.writeImagePackage(out, png, { name: "Sunset", created: "2026-11-07T12:00:00Z", uuid: "1a6e0000-0000-4000-8000-0000000000aa" });
  check(build + " writeImagePackage verifies", werk.open(out).verdict().exit === 0);
  var w = werk.buildMeshPackage(glb, { name: "Crate", created: "2026-11-07T12:00:00Z", uuid: "1a6e0000-0000-4000-8000-0000000000bb",
    textures: [{ id: "albedo", png: png }], materials: [{ id: "wood", baseColor: "albedo" }],
    signKey: "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60", signer: { uri: "urn:werk:test:k1", kind: "service" } });
  var zb = w.toBytes();                    // UXP / browser path: no file system needed
  var p2 = werk.openBytes(zb);
  check(build + " toBytes + openBytes (no IO)", p2.verdict().exit === 0 && p2.signatureState === "signed-and-valid");
  check(build + " primaryMesh", werk.B.eq(p2.primaryMesh().bytes, glb));
  var out3 = path.join(OUT, build + "-sunset-v2.werk");
  werk.appendVersion(out, out3, "image-source", [werk.file("image/source.png", io.read(path.join(I, "preview.png")))], "A larger source, for the test.", { created: "2026-11-07T13:00:00Z" });
  var n = werk.open(out3).node("image-source");
  check(build + " appendVersion @N move", n.versions[0].files[0].path === "image/source@1.png" && n.resolved === 2);
  var bd = werk.defaultBundle();
  var w6 = werk.buildImagePackage(png, { name: "Extras", created: "2026-11-07T12:00:00Z", uuid: "1a6e0000-0000-4000-8000-0000000000ee",
    conventionsMap: "spec/conventions-map.extra.json", specFiles: { "spec/conventions-map.extra.json": bd.bytes("spec/conventions-map.image.json") },
    readmeFiles: [["HOW-TO-READ.md", werk.utf8Encode("# How to read this package\n")]] });
  var p6 = werk.openBytes(w6.toBytes()), rv = p6.node("readme").version();
  check(build + " conventionsMap + addReadmeFile", p6.manifest.conventions_map === "spec/conventions-map.extra.json" &&
    rv.files.length === 2 && p6.payloadPath("readme") === "README.txt" && p6.verdict().exit === 0);
  var dupOk = false;
  try { werk.openBytes(fs.readFileSync(path.join(I, "..", "dup.werk"))); } catch (e) { dupOk = e.code === "bad-container"; }
  if (build === "werk.js") { check(build + " duplicate entry names refused", dupOk); }
});
console.log(fails + " failure(s)");
process.exitCode = fails ? 1 : 0;
