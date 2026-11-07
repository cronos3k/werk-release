# Vendored bootstrap reader

`werk_read.py` here is a **byte-identical** copy of `loaders/werk_read.py` at
the repository root.

- Do not edit it. Edit the original and re-copy.
- `adapters/blender/test_gate.py` hashes both files and fails the gate on any
  difference, so drift is a measured failure rather than a discovery.
- The copy exists because a Blender add-on installed from a zip has no access
  to the werk repository, and `werk_blender` declares zero dependencies
  beyond the Python standard library and `bpy`.

Current copy: sha256
`64de154c170334dbb08f1ddeafcbd5cb12ec62639d8d8742c475fb35a8869eb5`, 31997 bytes.

The add-on uses it as a library, not as a CLI. Two consequences worth knowing:

1. `Package.__init__` raises `SystemExit` when `MANIFEST.json` is missing or
   unparseable — a container-scoped refusal in CLI terms (SPEC §10.1). The
   importer catches `SystemExit` and converts it to a Blender operator error,
   because a script that kills Blender's process is not a refusal, it is a
   crash.
2. `Package` verifies every declared file's size and sha256 during
   construction and records the outcome in `Package.report`. The importer
   never re-hashes; it reads that report.
