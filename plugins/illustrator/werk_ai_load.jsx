// Loads the plug-in's modules from the folder this file is in, at GLOBAL scope
// ($.evalFile evaluates in the caller's scope, so this file must not wrap it in a function).
// Safe to evaluate more than once.
var WERK_PLUGIN_DIR = File($.fileName).parent.fsName.replace(/\\/g, "/");
if (typeof werk === "undefined") { $.evalFile(new File(WERK_PLUGIN_DIR + "/werk.jsx")); }
if (typeof werkAI === "undefined") { $.evalFile(new File(WERK_PLUGIN_DIR + "/werk_ai_lib.jsx")); }
