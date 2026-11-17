// werk for Photoshop 2022+ (UXP, manifest v5): open an image/1 package (or any
// package's primary.image) and export the active document as image/1.
// The werk release library (werk.js, Uint8Array build) does all byte work; PNG /
// JPEG decode and encode are Photoshop's own (open / saveAs.png of a temporary file).
const werk = require("./werk.js");
const uxp = require("uxp");
const { app, core } = require("photoshop");
const fs = uxp.storage.localFileSystem;
const BIN = { format: uxp.storage.formats.binary };
const UTF8 = { format: uxp.storage.formats.utf8 };
const TOOL = { tool: "werk-photoshop-uxp", version: "1.0.0" };

async function readBytes(entry) { return new Uint8Array(await entry.read(BIN)); }
async function writeBytes(entry, u8) {
  await entry.write(u8.buffer.slice(u8.byteOffset, u8.byteOffset + u8.length), BIN);
}
function url(path) { return "file:" + path.replace(/\\/g, "/"); }
async function fileAt(path, create) {
  return create ? fs.createEntryWithUrl(url(path), { overwrite: true }) : fs.getEntryWithUrl(url(path));
}

// -> {doc, verdict, report, primaryPath}
async function openPackageBytes(bytes, name, scratchFolder) {
  const pkg = werk.openBytes(bytes, name);
  const verdict = pkg.verdict();
  const { path, bytes: img } = pkg.primaryImage();
  const ext = (/\.(\w+)$/.exec(path) || [0, "png"])[1].toLowerCase();
  const tmp = await scratchFolder.createFile("werk-primary-" + Date.now() + "." + ext, { overwrite: true });
  await writeBytes(tmp, img);
  const doc = await core.executeAsModal(async () => app.open(tmp), { commandName: "Open werk package" });
  try { await tmp.delete(); } catch (e) { /* keep going */ }
  return { doc, verdict, report: pkg.report, primaryPath: path, profile: pkg.manifest.profile };
}

// the document's composite as PNG (Photoshop's encoder), packed as image/1
async function exportImageBytes(doc, scratchFolder, opts) {
  const tmp = await scratchFolder.createFile("werk-composite-" + Date.now() + ".png", { overwrite: true });
  await core.executeAsModal(async () => doc.saveAs.png(tmp, { compression: 6 }, true), { commandName: "Export werk image/1" });
  const png = await readBytes(tmp);
  try { await tmp.delete(); } catch (e) { /* keep going */ }
  const w = werk.buildImagePackage(png, Object.assign({ name: (doc.title || "Untitled").replace(/\.[^.]*$/, "") || "Untitled",
    generator: TOOL, producer: TOOL }, opts || {}));
  return { zip: w.toBytes(), png };
}

// ------------------------------------------------------------ gate hook
// When SELFTEST is set to an absolute folder (this plug-in's _selftest/, as gate_uxp.py
// writes it) and <SELFTEST>/request.json exists at load,
// run its tasks and write result.json beside it (the gate's only way in: UXP
// plug-ins cannot be driven from COM / ExtendScript). Without that file: nothing.
const SELFTEST = "";  // e.g. "C:/path/to/contrib/experimental/photoshop-uxp/_selftest"; empty: hook off
async function selftest() {
  let req;
  try { req = JSON.parse(await (await fileAt(SELFTEST + "/request.json")).read(UTF8)); } catch (e) { return; }
  const out = { started: new Date().toISOString(), host: { app: "Photoshop", version: app.version }, lib: werk.version, tasks: [] };
  const scratch = await fs.getEntryWithUrl(url(SELFTEST));
  for (const t of req.tasks) {
    const r = { task: t.task, input: t.in, ok: false };
    const t0 = Date.now();
    try {
      const bytes = await readBytes(await fileAt(t.in));
      const o = await openPackageBytes(bytes, t.in, scratch);
      r.verdict = o.verdict; r.primary_path = o.primaryPath; r.profile = o.profile;
      r.width = o.doc.width; r.height = o.doc.height;
      const ex = await exportImageBytes(o.doc, scratch, { name: t.task, created: "2026-11-07T00:00:00Z" });
      await writeBytes(await fileAt(t.out, true), ex.zip);
      await writeBytes(await fileAt(t.out_png, true), ex.png);
      await core.executeAsModal(async () => o.doc.closeWithoutSaving(), { commandName: "close" });
      // re-open the export through the plug-in
      const o2 = await openPackageBytes(await readBytes(await fileAt(t.out)), t.out, scratch);
      r.reopen_verdict = o2.verdict;
      const ex2 = await exportImageBytes(o2.doc, scratch, {});
      await writeBytes(await fileAt(t.reopen_png, true), ex2.png);
      await core.executeAsModal(async () => o2.doc.closeWithoutSaving(), { commandName: "close" });
      r.ok = true;
    } catch (e) { r.error = String(e && e.message || e); }
    r.seconds = (Date.now() - t0) / 1000;
    out.tasks.push(r);
  }
  out.finished = new Date().toISOString();
  await (await fileAt(SELFTEST + "/result.json", true)).write(JSON.stringify(out, null, 1), UTF8);
}

uxp.entrypoints.setup({
  plugin: { create() { setTimeout(() => { selftest().catch(() => {}); }, 3000); } },
  commands: {
    async openWerk() {
      const f = await fs.getFileForOpening({ types: ["werk"] });
      if (!f) { return; }
      const scratch = await fs.getTemporaryFolder();
      const o = await openPackageBytes(await readBytes(f), f.name, scratch);
      if (o.verdict.exit !== 0) {
        await app.showAlert("werk: " + f.name + " opened with verification errors: " + o.verdict.error_codes.join(", "));
      }
    },
    async exportWerkImage() {
      if (!app.activeDocument) { await app.showAlert("werk: no document is open"); return; }
      const f = await fs.getFileForSaving((app.activeDocument.title || "image").replace(/\.[^.]*$/, "") + ".werk", { types: ["werk"] });
      if (!f) { return; }
      const ex = await exportImageBytes(app.activeDocument, await fs.getTemporaryFolder(), {});
      await writeBytes(f, ex.zip);
    }
  }
});
