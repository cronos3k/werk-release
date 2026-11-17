#!/usr/bin/env node
// werk CLI on the Uint8Array build (dist/werk.js). Same commands, options and
// exit statuses as `python -m werk`.
var werk = require("../dist/werk.js");
process.exitCode = werk.cli(process.argv.slice(2));
