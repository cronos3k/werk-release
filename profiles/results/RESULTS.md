# Profile fixtures — what was run (W19, 2026-11-20)

Machine `<lab-workstation>`, Windows 10, Python 3.12.8 (zlib 1.3.1), node v24.10.0, gcc 15.2.0
(MSYS2), rustc 1.94.0 (loaders) and 1.95.0 (ArtCraft mirror builds). `werkc` built from release
`fdc388b` `core/` (sha256 `52b5c2c71139bf16680bc74b9cc294397e588f83d0dc1032c93c275ec8431cbb`,
the binary W18 built; used read-only). Release spec digest `55882f4b…` before and after
(`../PINS.md`). Fixture hashes: `../PINS.md`.

| check | command | result |
|---|---|---|
| fixtures reproduce | `python profiles/tools/build_fixtures.py --check` | all six byte-identical to the pins (each builder also asserts its own ground truth: its reference reader gives back what it wrote) |
| every reader | `python profiles/tools/verify_fixtures.py --werkc <werkc>` ([verify_fixtures.json](verify_fixtures.json)) | 6/6: `werkc verify` exit 0, 0 errors, manifest validated against the package's own schema, every JSON payload validated against its schema (7–13 per fixture), envelopes validated, format definitions' test-vector inputs re-hashed; `python -m werk verify`, `werk.js`, `werk-es3.js` exit 0; `--strict` of the libs exits 1 (it promotes the one `unsupported-profile` warning, by design); `loaders/werk_read.py --verify --strict` exit 0, all files verified (116–143); reference readers exit 0, nothing dead |
| format definitions | `python tools/format_def.py --check-package` | exit 0 on all six (zlib-deflate, zip: printed test-vector inputs re-hashed; two packages declare none) |
| 7-reader agreement + extraction | `python libs/tests/cross_matrix.py --fixtures profiles/fixtures --only none --werkc <werkc>` ([CROSS-MATRIX.md](CROSS-MATRIX.md)) | 6/6 agree: py, js, es3, werkc, ref-py, ref-c, ref-rs all `0 / absent / 0 dead`; every reader extracts every live node's files byte-exact; failures 0 |
| one-bit damage | `python profiles/tools/damage_profiles.py --out <scratch> --werkc <werkc>` ([damage_profiles.json](damage_profiles.json)) | 3 867 variants (3 808 container bit flips, 59 payload byte flips with CRC patched); no crash; 3 852 agree; 15 disagree, all one class (below); the reference reader of the profile named the damaged node in 59/59 payload variants |
| second implementation | `python profiles/tools/cross_readers.py` ([cross_readers.json](cross_readers.json)) | 6/6 agree (below) |
| blocks array schema | `python profiles/tools/probe_blocklist.py --werkc <werkc>` | the rich-document fixture's inflated blocks array validates against `$defs/BlockList`; the negative control (one run length a string) is rejected |
| reader self-containment | `python profiles/tools/check_readers.py` | 6/6 carry the shared container block verbatim and import only the standard library |
| PhotoCraft round trip | mirror build, [photocraft_roundtrip_example.rs](photocraft_roundtrip_example.rs), log [photocraft_roundtrip.log](photocraft_roundtrip.log) | see below |

**The 15 damage disagreements** (all flips inside `MANIFEST.json`): 14 break one node record's
manifest schema (a key renamed: `media_type`, `producer`, `epistemic`, `payload_file`,
`input_files`, `role`, `version`; `"v": 0`; a type `core.sheeu.styles`; an `input_files` path
with a backtick). werkc validates the manifest with JSON Schema and kills that node; the libs
readers and loaders do not validate JSON Schema (documented in `libs/README.md`) and keep it. One
(vector-art) removes a node's `node_id`: the libs kill it as `<node 4>`, the bootstrap loaders
name no node without an id. The same class as the release's own known gaps
(`libs/tests/results/damage_agree.json`: werkc agrees on 1 524 of 1 532). None is in a profile
payload; none involves the profile definitions.

**Second implementations** (written independently of the reference readers):
raster-layers — the release GIMP plug-in's `werk_raster.read_document`: canvas, top-level tree
and the decoded pixels of both raster layers (sha256 per layer) equal. vector-art — the
profile's `read_document.py`: title, 12 object ids in tree order, types, the text of the text
object equal, nothing lost. motion-comp — the profile's `read_motion.py value`: 250 property
values (every frame of every animated property) within 2.5e-10 of the reference reader (§6.3
asks 1e-9). rich-document — the profile's `read_document.py --text`: plain text identical, and
it reports the stored plain text equal to its recomputation. spreadsheet — the profile's
`read_spreadsheet.py --json`: all 33 cells (value, formula, format index) equal. presentation —
the profile's `read_presentation.py --json`: slide titles, shape counts, embedded files' sha256
equal.

**PhotoCraft round trip.** The PhotoCraft `werk-native` tree (`photocraft-werk`, profile
raster-layers/1) and craft-libs, copied into a mirror whose werk-core is the release core
(edits: [MIRROR-EDITS.txt](MIRROR-EDITS.txt); one source edit in craft-werk to map the release
core's `SignatureState::Unverified`), built with rustc 1.95.0:
* A: `raster-layers-v1.werk` → `photocraft_werk::open` (exit 0, nothing lost) → Document → `save`
  → `open` → Document: equal (`PartialEq`). The reference reader's extraction of the fixture and
  of PhotoCraft's re-save is identical for canvas, name and the whole layer tree including every
  surface's decoded samples (previews differ: the example passes its own preview pictures). The
  document and layer JSON payloads PhotoCraft wrote are byte-identical to the builder's; tile
  files differ in compression only (PhotoCraft compresses the raw tiles too).
* B: PhotoCraft's own `simple` (3 layers) and every-field `maximal` documents → save → open:
  equal; the reference reader reads both with exit 0, nothing dead (the maximal one: 13
  top-level layers, 755 files verified; `x.photocraft.*` reported as skipped); `werkc verify`
  exit 0 on all three PhotoCraft-written packages.
* Observed: PhotoCraft's re-save does not carry the fixture's `reader-raster-layers` `core.tool`
  node (it writes the `core.tool` nodes of format definitions only).
* Not run: the same for the other five apps (no adapter in this task; W6: the apps are not
  rebased on the release core). The standalone `photocraft-werk-adapter` crate writes profile
  `photocraft/1`, not raster-layers/1; it was not used.

**EffectCraft schemas.** In a mirror of EffectCraft `werk-native` on the release core,
[effectcraft_schemas_example.rs](effectcraft_schemas_example.rs) wrote all 11 schemas of
`effectcraft_werk::schema`; the 7 the sample carries are byte-identical to the sample's copies;
the other 4 were added to `profiles/motion-comp/spec/schemas/`.
