// Run by a host launched with this file as its argument (Illustrator, or any
// ExtendScript host without COM): run the smoke test, write the result line to
// _scratch/es-result.txt, quit the host.
// libs/ root: this file is libs/js/tests/extendscript_host_wrapper.jsx
var WERK_T = new File($.fileName).parent.parent.parent.fsName.replace(/\\/g, "/");
var WERK_EXPECT = "9c9681fa50bc6530a8ed73a833870848c6aa86a3cd49f8922fe8d14d89e7cc25";
var __r = $.evalFile(new File(WERK_T + "/js/tests/extendscript_smoke.jsx"));
var __f = new File(WERK_T + "/_scratch/es-result.txt");
__f.encoding = "UTF-8"; __f.open("w"); __f.write("host=" + app.name + " " + __r); __f.close();
app.quit();
