# Vendored readers: the bootstrap loader and the werk release library

`werk_single.py` here is a **byte-identical** copy of the werk release
library's single-file build, `libs/python/werk_single.py` (reader +
PackageWriter + its embedded spec/loaders bundle, standard library only).
`libwerk.py` imports it; it verifies signatures (Ed25519) on import, re-reads
every export, and does all of image/1. Copied, never symlinked; refreshed by
`python tools/vendor_spec.py`, and both gates hash it against its source.
Current copy: sha256 `082420506e949d100ba05daf40d513e0dd9689507dc7e1653c1e18d4db62864e`, 663120 bytes (lib 0.1.0, bundle source_rev 26e3e14 = release-fixes, spec_sha256 55882f4b05e7...).


`werk_read.py` here is a **byte-identical** copy of `loaders/werk_read.py` at
the repository root.

- Do not edit it. Edit the original and re-copy.
- `plugins/blender/test_gate.py` hashes both files and fails the gate on any
  difference, so drift is a measured failure rather than a discovery.
- The copy exists because a Blender add-on installed from a zip has no access
  to the werk repository, and `werk_blender` declares zero dependencies
  beyond the Python standard library and `bpy`.

Current copy: sha256
`71b793b03c43556bc09521c84f234979c225d80f68962884b21f4ca8744315c5`, 62021 bytes (release-fixes 26e3e14) (was stale in the source README: it said 64de154c..., 31997 bytes).

The add-on uses it as a library, not as a CLI. Two consequences worth knowing:

1. `Package.__init__` raises `SystemExit` when `MANIFEST.json` is missing or
   unparseable — a container-scoped refusal in CLI terms (SPEC §10.1). The
   importer catches `SystemExit` and converts it to a Blender operator error,
   because a script that kills Blender's process is not a refusal, it is a
   crash.
2. `Package` verifies every declared file's size and sha256 during
   construction and records the outcome in `Package.report`. The importer
   never re-hashes; it reads that report.
