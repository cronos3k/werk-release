#!/usr/bin/env node
// The ES3 / ExtendScript build (dist/werk.jsx) driven from Node, so the exact
// file Photoshop & co. #include is exercised by the cross-matrix: binary-string
// bytes, Node file IO in place of File/Folder.
var werk = require("../dist/werk.jsx");
process.exitCode = werk.cli(process.argv.slice(2));
