# tools/blender

Where a Blender binary for the gate goes. The add-on lives in
`plugins/blender/werk_blender/`; its host-side scripts (`vendor_spec.py`,
`build_addon_zip.py`) are in `plugins/blender/tools/`.

| script | what it does |
|---|---|
| `plugins/blender/tools/vendor_spec.py` | copies `spec/`, `loaders/werk_read.py` and `libs/python/werk_single.py` into the add-on, verbatim; `--check` verifies byte-identity and exits 1 on drift |
| `plugins/blender/tools/build_addon_zip.py` | builds the installable add-on zip into `plugins/blender/dist/` |

## Re-run `vendor_spec.py` after editing `spec/` or `loaders/`

The add-on carries a byte-identical copy of both, because a conformant
manifest's `schemas` map points at JSON Schema paths **inside the package**
and an add-on installed from a zip has no path back to this repository. The
copy is therefore structural, not lazy — and the defence against it drifting
is that drift is a **measured gate failure**, not a discovery:

```
python plugins/blender/tools/vendor_spec.py          # refresh
python plugins/blender/tools/vendor_spec.py --check  # verify; exit 1 on any difference
```

`plugins/blender/test_gate.py` runs `--check` as its second clause and
`build_addon_zip.py` refuses to build on drift. This is the same standing
obligation `tests/fixtures/crate.werk` already carries ("editing `spec/` or
`loaders/` changes bytes it embeds, so it must be rebuilt after either").

## Finding a Blender for the gate

`test_gate.py` looks, in order:

1. `--blender <path>`
2. `$WERK_BLENDER`
3. `blender` on `PATH`
4. `C:\Program Files\Blender Foundation\Blender *\blender.exe`, the Steam
   install path, `tools/blender/**`, `/usr/bin/blender`, `/snap/bin/blender`,
   `/Applications/Blender.app/Contents/MacOS/Blender`

If none is found, the Blender clauses report **SKIP with the reason** — never
a pass. The measured run recorded in `HANDOVER.md` used a system install found
by step 4.

### If you need to fetch one

Blender is GPL and its official builds are freely redistributable, so
downloading a portable archive into this directory is allowed:

```
# Linux
curl -LO https://download.blender.org/release/Blender4.2/blender-4.2.1-linux-x64.tar.xz
tar -xf blender-4.2.1-linux-x64.tar.xz -C tools/blender/

# Windows (portable zip, not the installer)
curl -LO https://download.blender.org/release/Blender4.2/blender-4.2.1-windows-x64.zip
```

Unpack it under `tools/blender/` and `test_gate.py` will find it. **The binary
is gitignored**: it is several hundred megabytes and a format repository is
not a place to keep one. Only this README is tracked.

Any Blender 4.x works. The measured run used **4.2.1 LTS**.
