// File-system adapter for Adobe ExtendScript: File / Folder objects, binary
// strings through encoding "BINARY". Paths are given in the platform's form
// or as URIs; the adapter uses "/" internally and lets File resolve them.
function makeJsxIO(B) {
  function f(p) { return new File(p); }
  function readAll(p) {
    var fh = f(p);
    fh.encoding = "BINARY";
    if (!fh.open("r")) { throw new Error("cannot open " + p + " for reading"); }
    var parts = [], s;
    // read() in chunks: one huge read() is slow in some ExtendScript builds.
    while (!fh.eof) { s = fh.read(1048576); if (s === "" && fh.eof) { break; } parts.push(s); }
    fh.close();
    return parts.join("");
  }
  function mk(p) {
    var d = new Folder(p);
    if (d.exists) { return; }
    var parent = d.parent;
    if (parent && !parent.exists) { mk(parent.fsName); }
    d.create();
  }
  return {
    name: "extendscript",
    // File(path) returns a Folder object when the path is an existing folder.
    isDir: function (p) { var x = File(p); return x.exists && (x instanceof Folder); },
    isFile: function (p) { var x = File(p); return x.exists && !(x instanceof Folder); },
    exists: function (p) { return File(p).exists || Folder(p).exists; },
    size: function (p) { return f(p).length; },
    read: readAll,
    readHead: function (p, n) {
      var fh = f(p);
      fh.encoding = "BINARY";
      if (!fh.open("r")) { throw new Error("cannot open " + p); }
      var s = fh.read(n);
      fh.close();
      return s;
    },
    write: function (p, b) {
      var fh = f(p);
      fh.encoding = "BINARY";
      fh.lineFeed = "Unix";
      if (!fh.open("w")) { throw new Error("cannot open " + p + " for writing"); }
      fh.write(b);
      fh.close();
    },
    openWriter: function (p) {
      var fh = f(p);
      fh.encoding = "BINARY";
      fh.lineFeed = "Unix";
      if (!fh.open("w")) { throw new Error("cannot open " + p + " for writing"); }
      return { write: function (b) { fh.write(b); }, close: function () { fh.close(); } };
    },
    mkdirs: mk,
    remove: function (p) { var x = f(p); if (x.exists) { x.remove(); } },
    rename: function (a, b) {
      var x = f(a), target = f(b);
      if (target.exists) { target.remove(); }
      // File.rename takes a NAME in the same folder.
      if (!x.rename(target.name)) { throw new Error("cannot rename " + a); }
    },
    isEmptyDir: function (p) { return new Folder(p).getFiles().length === 0; },
    join: function (a, rel) { return a.replace(/[\\\/]+$/, "") + "/" + rel; },
    dirname: function (p) { return f(p).parent.fsName; },
    listFiles: function (root) {
      var out = [];
      function walk(d, pre) {
        var items = d.getFiles(), i;
        for (i = 0; i < items.length; i++) {
          var it = items[i], nm = decodeURI(it.name);
          if (it instanceof Folder) { walk(it, pre + nm + "/"); } else { out.push(pre + nm); }
        }
      }
      walk(new Folder(root), "");
      return out;
    },
    stdout: function (t) { $.write(t); },
    stdoutBytes: function (b) { $.write(b); },
    stderr: function (t) { $.write(t); }
  };
}
