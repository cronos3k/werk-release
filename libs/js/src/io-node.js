// File-system adapter for Node (both byte adapters). Not loaded in UXP or a
// browser: there, use werk.openBytes(bytes) and writer.toBytes().
function makeNodeIO(B) {
  var fs = require("fs"), pathm = require("path");
  function toB(buf) {
    if (B.kind === "uint8array") { return new Uint8Array(buf.buffer, buf.byteOffset, buf.length); }
    return buf.toString("latin1");
  }
  function fromB(b) {
    if (B.kind === "uint8array") { return Buffer.from(b.buffer, b.byteOffset, b.length); }
    return Buffer.from(b, "latin1");
  }
  return {
    name: "node",
    isDir: function (p) { try { return fs.statSync(p).isDirectory(); } catch (e) { return false; } },
    isFile: function (p) { try { return fs.statSync(p).isFile(); } catch (e) { return false; } },
    exists: function (p) { return fs.existsSync(p); },
    size: function (p) { return fs.statSync(p).size; },
    read: function (p) { return toB(fs.readFileSync(p)); },
    readHead: function (p, n) {
      var fd = fs.openSync(p, "r"), buf = Buffer.alloc(n);
      var got = fs.readSync(fd, buf, 0, n, 0);
      fs.closeSync(fd);
      return toB(buf.subarray(0, got));
    },
    write: function (p, b) { fs.writeFileSync(p, fromB(b)); },
    openWriter: function (p) {
      var fd = fs.openSync(p, "w");
      return { write: function (b) { var x = fromB(b); fs.writeSync(fd, x, 0, x.length); },
               close: function () { fs.closeSync(fd); } };
    },
    mkdirs: function (p) { fs.mkdirSync(p, { recursive: true }); },
    remove: function (p) { if (fs.existsSync(p)) { fs.unlinkSync(p); } },
    rename: function (a, b) { fs.renameSync(a, b); },
    isEmptyDir: function (p) { return fs.readdirSync(p).length === 0; },
    join: function (a, rel) { return pathm.join.apply(null, [a].concat(rel.split("/"))); },
    dirname: function (p) { return pathm.dirname(p); },
    listFiles: function (root) {
      var out = [];
      function walk(d, pre) {
        var names = fs.readdirSync(d), i;
        for (i = 0; i < names.length; i++) {
          var full = pathm.join(d, names[i]);
          if (fs.statSync(full).isDirectory()) { walk(full, pre + names[i] + "/"); }
          else { out.push(pre + names[i]); }
        }
      }
      walk(root, "");
      return out;
    },
    stdout: function (t) { process.stdout.write(t); },
    stdoutBytes: function (b) { process.stdout.write(fromB(b)); },
    stderr: function (t) { process.stderr.write(t); }
  };
}
