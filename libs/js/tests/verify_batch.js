// verify_batch.js <werk.js|werk.jsx> <list file>: one verdict JSON line per path
// (a refusal is {"exit": 2, "refusal": code}). Used by tests/damage_agree.py.
var fs = require("fs"), werk = require("../dist/" + process.argv[2]);
var paths = fs.readFileSync(process.argv[3], "utf8").split("\n").filter(Boolean), out = [];
paths.forEach(function (p) {
  var v;
  try { v = werk.open(p).verdict(); }
  catch (e) { v = e.refusal ? { exit: 2, refusal: e.code } : { exit: -1, crash: String(e && e.message) }; }
  out.push(JSON.stringify(v));
});
process.stdout.write(out.join("\n") + "\n");
