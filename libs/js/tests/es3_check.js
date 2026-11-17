// es3_check.js -- prove dist/werk.jsx is ES3, so ExtendScript can load it.
//   node --expose-internals js/tests/es3_check.js [file]
// 1. Parse with acorn at ecmaVersion 3 (the acorn bundled inside Node).
// 2. Walk the AST: no ES3-reserved word used as a property name or key
//    (legal in ES5, a syntax error in ExtendScript).
// 3. Outside the node-only IO block, no call to an API ES3 does not have.
var fs = require("fs"), path = require("path");
var acorn = require("internal/deps/acorn/acorn/dist/acorn");
var file = process.argv[2] || path.join(__dirname, "..", "dist", "werk.jsx");
var src = fs.readFileSync(file, "utf8"), bad = 0;
var ast = acorn.parse(src, { ecmaVersion: 3, locations: true });
var RESERVED = ("break case catch continue debugger default delete do else finally for function if in instanceof new return switch this throw try typeof var void while with " +
  "abstract boolean byte char class const double enum export extends final float goto implements import int interface long native package private protected public short static super synchronized throws transient volatile null true false").split(" ");
function walk(n) {
  if (!n || typeof n.type !== "string") { return; }
  if (n.type === "MemberExpression" && !n.computed && RESERVED.indexOf(n.property.name) >= 0) { bad++; console.log("reserved word as property: ." + n.property.name + " at line " + n.loc.start.line); }
  if (n.type === "Property" && n.key.type === "Identifier" && RESERVED.indexOf(n.key.name) >= 0) { bad++; console.log("reserved word as key: " + n.key.name + " at line " + n.loc.start.line); }
  for (var k in n) { var v = n[k]; if (Array.isArray(v)) { v.forEach(walk); } else if (v && typeof v.type === "string") { walk(v); } }
}
walk(ast);
var lint = src.replace(/\/\*@node-only-begin\*\/[\s\S]*?\/\*@node-only-end\*\//g, "");
var FORBIDDEN = [/\bObject\.(keys|create|defineProperty|freeze|assign|entries|values)\b/, /\bJSON\./,
  /\.(forEach|map|filter|reduce|some|every|trim|startsWith|endsWith|includes|padStart|repeat)\(/,
  /\bArray\.(isArray|from)\b/, /\b(Uint8Array|Uint32Array|Float64Array|ArrayBuffer|DataView|Map|Set|Symbol|Promise|BigInt)\b/,
  /\bDate\.now\b/, /=>/, /`/, /\b(let|const|class)\s/];
var STRING_RE = new RegExp('"(?:[^"\\\\]|\\\\.)*"', "g");
var lines = lint.split("\n"), checked = 0;
for (var i = 0; i < lines.length; i++) {
  if (/^WERK_BUNDLE_FILES\[/.test(lines[i]) || /^var WERK_BUNDLE_JSON/.test(lines[i])) { continue; }
  checked++;
  var code = lines[i].replace(STRING_RE, '""').replace(/\/\/.*$/, "");
  for (var j = 0; j < FORBIDDEN.length; j++) {
    if (FORBIDDEN[j].test(code)) { bad++; console.log("non-ES3 API at line " + (i + 1) + ": " + lines[i].trim().slice(0, 120)); }
  }
}
console.log((bad ? "FAIL" : "OK") + ": " + file + " parses as ECMAScript 3 (acorn " + acorn.version +
  "), " + checked + " code lines linted for non-ES3 APIs, " + bad + " problem(s)");
process.exitCode = bad ? 1 : 0;
