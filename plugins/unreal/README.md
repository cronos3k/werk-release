# WerkLink for Unreal Engine 5.8 (werk release plug-in)

`.werk` packages (profile `3d-entity/1`, and the textures of `image/1`) to real UAssets, and
selected UAssets back to a werk package. It replaces the repository's earlier
adapter (`adapters/unreal/` in `fa32df8`), updated to and gated against
branch `release-fixes` @ `26e3e14` (library bundle `26e3e14`), built and gated on
**Unreal Engine 5.8.2** (the source tree was written against 5.7; 5.7 is untested: it is not
installed on the gate machine). The adapter's design document is `DESIGN.md` in this
folder; this file says what this copy changes, how to install it and what
it does not do.

## What this copy changes (all in `WerkLink/`)

| change | where | why |
|---|---|---|
| **Python / Blueprint entry point** `unreal.WerkLinkScripting.import_werk(file, dest, save, master)` and `export_werk(out, assets, spec_dir, name, hermetic)`, each returning the result struct as JSON | `Public/WerkLinkScripting.h`, `Private/WerkLinkScripting.cpp` | the repository's WerkLink had no Python entry point (TESTBED.md limitation 5); the gate drives it from `-run=pythonscript` |
| **dangling-edge guard** (SPEC §5 "Edge targets", PR #11 change 2): the exporter refuses to write a package in which any `edges[].to` names a node that is not in `nodes[]`, `requires` or `enhances` alike | `Private/Core/werk_edges.{h,cpp}`, the end of `FWerkLinkAction::Export` | W1 noted the C++ exporter lacked it; it compiles here on 5.8 |
| **exported `core.material` carries its edges**: one `requires` / `samples` edge per bound texture slot (the fixtures' shape); before, every exported node had `edges: []`, so the guard had nothing to guard | `Private/WerkLinkExport.cpp` | the guard now checks real edges, and the material's dependency is declared |
| **one container path per node**: the second and later meshes are written to `geometry/<node-id>.glb` (the first keeps `geometry/game.glb`), and a second writer guard refuses any path listed by two nodes | `WerkLinkExport.cpp`, `werk_edges.cpp` | **bug found by this gate**: every crate fixture has two meshes (`geom-game`, `geom-source`); both were written to `geometry/game.glb`, i.e. two zip entries with one name. The Python / JS readers then hashed one entry and killed both nodes; werkc and the C / Rust loaders hashed the other and passed |
| **a constant UV channel is not exported** | `MeshDescriptionToGlb` | **bug found by this gate**: a GLB imported without `TEXCOORD_0` (crate-v1) got Unreal's default all-zero channel, the exporter wrote it, and WerkLink's own importer then refused the re-import (collapsed UVs, exit 1) |
| **deflate (zip method 8) is read** (RFC 1951 inflater; size + CRC-32 checked; `zip-entry-invalid` / `zip-entry-unsupported` per SPEC §1 ruling 9) | `Private/Core/werk_zip.cpp`, `werk_report.h` | the reader was store-only and refused `fixtures/crate-cc0-lean-v1-deflated.werk` as a container (exit 2) |
| `FVertexInstanceID::Invalid` -> `FVertexInstanceID(INDEX_NONE)` | `WerkLinkImport.cpp` | the two C4996 deprecation warnings of 5.8 |
| plug-in version 0.1 -> 0.2 | `WerkLink.uplugin` | |
| **release-fixes reader rules** (26e3e14): MINI-SPECS 5.4's six zip rules (duplicate names and flag bit 3 refuse the container, lossy UTF-8 names, CD is the authority, method-0 data checked by the manifest hash); SPEC 12.1 (malformed node dead under its id; `nodes` missing / manifest not an object refuse); SPEC 6 (SIGNATURE.json must be an object naming this manifest's sha256, else `present-and-invalid`; foreign algorithm warns) | `Private/Core/werk_zip.cpp`, `werk_manifest.{h,cpp}`, `werk_report.h` | WerkLink reads with its own C++, not werk-core; measured against the release readers on 21 damaged variants (`tests/agree_release_fixes.py`, gate part A2) |

`tests/roundtrip_gate.py` (the repository's commandlet gate) is **rebaselined from the fixture
manifests**: the "files verified" count and the node count are derived from each fixture by the
release Python reader instead of being typed in (see GATE-RESULTS.md for why the old numbers
were +8 off).

## Install

1. Build for your engine (Windows, MSVC 2022, UE 5.8):

       "C:\Program Files\Epic Games\UE_5.8\Engine\Build\BatchFiles\RunUAT.bat" BuildPlugin ^
           -Plugin=<this folder>\WerkLink\WerkLink.uplugin -Package=<out>\WerkLink -TargetPlatforms=Win64 -Rocket

2. Copy `<out>\WerkLink` (without its `HostProject` folder) into `<YourProject>\Plugins\WerkLink`.
   Copy, do not link.
3. Enable the plug-ins `WerkLink`, `PythonScriptPlugin` (only for the Python route) and open the
   project. Project Settings > Plugins > WerkLink: set **Spec Source Directory** to a werk
   repository checkout (its `spec/` and `loaders/` are embedded in every export; without it the
   export says it is not redistributable-conformant).

WerkLink is editor-only, has no network code and opens no port.

## Use

Content Browser: right-click a folder > *Import .werk here...*; right-click assets > *Export to
.werk...*. Commandlet: `UnrealEditor-Cmd.exe <project> -run=WerkLink -Import=<file> [-Dest=/Game/Werk]`
or `-Export=<out.werk> -Assets=/Game/A.A,... [-Spec=<werk repo>]` (repository README). Python
(Output Log, editor scripts, `-run=pythonscript`):

```python
import json, unreal
r = json.loads(unreal.WerkLinkScripting.import_werk("C:/assets/crate.werk", "/Game/Werk", True, ""))
e = json.loads(unreal.WerkLinkScripting.export_werk("C:/out/crate.werk", r["created_assets"],
                                                   "C:/werk", r["entity_name"], False))
print(r["exit"], r["summary"], e["exit"], e["summary"])
```

`exit` is the SPEC §10.1 status (0 clean, 1 errors in the report, 2 nothing loaded / refused).

## Gate

    py -3.12 tests/gate.py --repo <werk release repo> --libs <werk libs dir>
          # the gate's repo here: _repo/ = `git archive 26e3e14` of stage/werk + stage/assets-fixes
    sh tests/rebuild_and_gate.sh            # build with RunUAT, install into the gate project, gate

Part A builds the engine-free core with MSVC (`tests/build_gate.bat`) and runs its selftests
(the edge guard and the zip rules included) on crate-v1, its damaged twin and the deflated
fixture; part A2 checks WerkLink's reader verdicts against `python -m werk` and werkc on 21
damaged variants. Part B runs the
rebaselined commandlet round trip. Part C runs `UnrealEditor-Cmd -run=pythonscript` with
`tests/ue_python_gate.py`: every `3d-entity/1` fixture of the release is imported, everything the
import created is exported, every export is re-imported, and every export is verified by every
release reader (`tests/readers.py`). The gate project is `project/WerkGate` (content-only).
Results: `GATE-RESULTS.md`, raw output `_gate_out/`.

## Limits

* Import does not turn `core.skeleton`, `core.anim.clip`, `core.geom.points`, `core.geom.gsplat`
  or `core.retarget.bind` into assets (reported as skipped), so the four gsplat / retarget
  fixtures produce no assets and have nothing to export.
* Export writes entities, not levels; static meshes, simple collision, materials, textures and
  sound waves. A re-exported `core.geom.source` mesh is written as `core.geom.game` (the type is
  not stored in the asset); its node id is kept.
* No Ed25519: a signed package reports `unverified` (after checking the chain names this
  manifest's sha256); exports are unsigned.
* Built and run on Windows / UE 5.8.2 only. Not compiled against 5.7 after these changes.
