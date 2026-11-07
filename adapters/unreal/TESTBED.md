# The werk Unreal testbed

A standing UE 5.7 project that hosts WerkLink and can be driven from outside —
from a shell, from a Python script, or from a Claude Code session over MCP.

It lives at **`<lab>\UnrealWerkTest\WerkTest\`** and is deliberately **not** in
this git repository. A UE project is a few gigabytes of `Intermediate/`,
`DerivedDataCache/` and `Saved/`, none of which is the format; what belongs to
werk is the plugin source, the fixtures, and the scripts in this document,
which are all committed.

```
<lab>\UnrealWerkTest\
  WerkTest\            the project
    Config\            DefaultEngine.ini, DefaultEditorPerProjectUserSettings.ini,
                       DefaultRemoteControl.ini   <- read this one
    Plugins\WerkLink   a JUNCTION to <repo>\adapters\unreal\WerkLink
    Content\Werk\      where fixtures import to
    Content\Maps\WerkTestbed.umap
  proof\               gate screenshots + session.json
  logs\                commandlet logs, editor log, testbed_port.txt
  roundtrip\           packages the export gate writes
```

---

## The plugin is a junction, not a copy

```
mklink /J <lab>\UnrealWerkTest\WerkTest\Plugins\WerkLink <repo>\adapters\unreal\WerkLink
```

(PowerShell: `New-Item -ItemType Junction -Path ... -Target ...`)

**Why a junction.** Editing `adapters/unreal/WerkLink/**` and rebuilding is the
whole development loop; a copy means every edit needs a sync step and one
forgotten sync means measuring the wrong binary. The junction makes that
impossible.

**What it costs, stated so it is not a surprise.** UE writes
`WerkLink/Binaries/` and `WerkLink/Intermediate/` *inside the repository*.
Both are already in `adapters/unreal/.gitignore`. `WerkLink/Content/` is NOT
ignored, and must not be: `M_WerkPBR.uasset` is a shipped part of the plugin.

**To refresh after editing plugin source:** nothing. Just rebuild:

```
"C:\Program Files\Epic Games\UE_5.7\Engine\Build\BatchFiles\Build.bat" ^
    WerkTestEditor Win64 Development -Project=<lab>\UnrealWerkTest\WerkTest\WerkTest.uproject
```

The editor holds `UnrealEditor-WerkLink.dll` open, so **close the editor before
building** or the link step fails.

---

## The master material

`WerkLink/Content/M_WerkPBR.uasset` ships with the plugin (`CanContainContent`
is `true` in the `.uplugin`) and is the default `MasterMaterial` setting, so
`core.material` import produces working material instances out of the box.

It is a **build product**. The graph is authored in
`adapters/unreal/tools/make_master_material.py`, and the parameter names come
from the same table the C++ reads (`Private/WerkMaterialSlots.h`). Regenerate:

```
UnrealEditor-Cmd.exe <lab>\UnrealWerkTest\WerkTest\WerkTest.uproject -run=pythonscript ^
    -script="<repo>/adapters/unreal/tools/make_master_material.py" -unattended -nopause -nosplash
```

It writes `<lab>\UnrealWerkTest\logs\master_material.json` listing every parameter
the finished asset actually exposes plus any connection that failed, and sets
`"ok": false` if the material does not match `WerkMaterialSlots.h`. Read the
file; do not read the exit code alone.

| werk slot | texture parameter | static switch |
|---|---|---|
| `base_color` | `BaseColorTexture` | `UseBaseColorTexture` |
| `metallic_roughness` | `MetallicRoughnessTexture` | `UseMetallicRoughnessTexture` |
| `normal` | `NormalTexture` | `UseNormalTexture` |
| `occlusion` | `OcclusionTexture` | `UseOcclusionTexture` |
| `emissive` | `EmissiveTexture` | `UseEmissiveTexture` |
| `height` | — | — |

Scalars: `Metallic`, `Roughness`, `NormalScale`, `OcclusionStrength`,
`EmissiveStrength`. Vectors: `BaseColor`, `EmissiveColor`.

There is **no height slot**: a base pass cannot shade one without parallax
occlusion mapping, and a parameter wired to nothing would make the exporter
write a slot claiming a shading the engine never performs. The importer reports
`height` as unbound, which is true.

---

## Running the gates

**The import/export/round-trip gate** (needs no running editor; it starts
commandlets itself):

```
python adapters\unreal\tests\roundtrip_gate.py
```

**The editor-control gate** (needs a running editor):

```
python tools\ue_mcp\launch_testbed.py          # starts it, waits, prints the port
python tools\ue_mcp\proof_session.py           # writes <lab>\UnrealWerkTest\proof\
```

---

## Driving the editor

### Which route, and why

Epic's **Remote Control API** (HTTP, ships with the engine) with
`PythonScriptLibrary.ExecutePythonScript` as the payload. Researched against
the live repositories on 2026-08-08 rather than from memory:

| option | verdict |
|---|---|
| `chongdashu/unreal-mcp` (2057★) | last push **2025-04-22**; **four open unmerged issues** about 5.6/5.7 compile breakage (#52, #54, #55, #60). No asset-listing tool, no screenshot tool. **Rejected.** |
| `kvick-games/UnrealMCP` (604★) | UE **5.5 only**, self-described "VERY WIP". **Rejected.** |
| `ChiR24/Unreal_mcp` (821★) | genuinely active, claims 5.0–5.8, but ships **version-pinned prebuilt binaries** and needs a C++ project. A compiled dependency on the engine is the thing that broke every other option. **Rejected.** |
| `runreal/unreal-mcp` (114★) | no plugin to compile — but rides UE's **multicast** Python Remote Execution, and multicast is what a VPN'd Windows box eats. **Rejected here, reasonable elsewhere.** |
| **Epic Remote Control API** | ships with 5.7, nothing to compile, cannot be broken by an engine upgrade. **Chosen.** |

The trick that makes it sufficient: Remote Control calls a `UFUNCTION` on an
object, and `PythonScriptLibrary.ExecutePythonScript` is one — so a single HTTP
endpoint is the whole editor Python API.

### Setup, already done in this project

`Config/DefaultRemoteControl.ini` (**not** `DefaultEngine.ini` —
`URemoteControlSettings` is `UCLASS(config = RemoteControl)`, and the same keys
in `DefaultEngine.ini` are silently read by nobody):

```ini
[/Script/RemoteControlCommon.RemoteControlSettings]
bAutoStartWebServer=True
RemoteControlHttpServerPort=30010
RemoteControlWebsocketServerBindAddress=127.0.0.1
bEnableRemotePythonExecution=True
```

**`bEnableRemotePythonExecution` is a real security decision.**
`FRemoteControlModule::CanBeAccessedRemotely` refuses every call to
`PythonScriptLibrary` unless it is true, and Epic's own comment says enabling it
"could open you up to vulnerabilities if an outside actor has access to your
server." It is defensible here *only* because both servers bind `127.0.0.1` and
this project holds nothing. Do not copy that file into a project that listens on
a network interface.

**Ports.** `launch_testbed.py` scans **30010–30030**, checks each is free before
telling the editor to bind, and writes the one it used to
`<lab>\UnrealWerkTest\logs\testbed_port.txt`. `ue_client.py` finds a live server by
asking each port for `/remote/info` rather than assuming.

### From a shell

```
python tools\ue_mcp\ue_client.py status
python tools\ue_mcp\ue_client.py list /Game/Werk
python tools\ue_mcp\ue_client.py spawn /Game/Werk/crate-tex-v1/WoodenCrateTextured/SM_GeomGame --label Crate
python tools\ue_mcp\ue_client.py shot <lab>/UnrealWerkTest/proof/mine.png
python tools\ue_mcp\ue_client.py py "WERK_OUT = unreal.EditorAssetLibrary.list_assets('/Game')"
```

### From Claude Code (MCP)

Registered project-scoped in `<repo>\.mcp.json` and `<lab>\SFNovels\.mcp.json` as
the server **`werk-unreal`**. Tools: `ue_status`, `ue_list_assets`,
`ue_spawn_mesh`, `ue_screenshot`, `ue_camera`, `ue_werk_import`,
`ue_save_level`, `ue_python`. Start the editor first
(`launch_testbed.py`); the server connects lazily and reports a dead editor as
an error rather than hanging.

The server is hand-rolled JSON-RPC over stdio, stdlib only, for the same reason
`werk_json.cpp` exists rather than `FJsonObject`: a repository arguing that its
format needs no ecosystem should not need one to test itself.

---

## Limitations, measured rather than assumed

1. **A screenshot needs the editor window in the FOREGROUND.** (S10-5.) The
   editor accepts `HighResShot` and `AutomationLibrary.take_high_res_screenshot`
   silently when it is not: the command appears in the log, the frame counter
   advances, no file is written and no warning is logged. `ue_client.screenshot`
   raises the window through `user32` first and says so. **An RDP session with
   no visible desktop, or a truly headless box, cannot produce one this way.**
2. **`HighResShot ... filename=` is not honoured** by the editor viewport path.
   The file lands in `Saved/Screenshots/WindowsEditor/` under an auto-numbered
   name; the client finds the new file by diffing the directory and moves it.
3. **`viewmode unlit` over this channel does not change the level viewport.**
   The console accepts it (`Cmd: viewmode unlit` appears in the log) and the
   picture does not change. The proof session therefore ships two *framings*
   rather than two claimed view modes.
4. **`ExecutePythonScript` returns a bool and nothing else.** Anything that has
   to come back is written to a JSON file by the wrapper in
   `ue_client.python_json` and read from disk. Log scraping was rejected: a log
   format change would silently turn a measurement into a guess.
5. **`ue_werk_import` refuses.** WerkLink exposes no Python entry point, and
   running the commandlet against a project the editor already has open would
   fight over the same packages. Import through the commandlet with the editor
   closed, or through the Content Browser menu.
6. **Two editors on one project is not supported** and `launch_testbed.py`
   refuses to start a second one when Remote Control already answers.

---

## Reproducing the testbed from scratch

1. `mkdir <lab>\UnrealWerkTest\WerkTest` and copy `Config/`, `Source/` and
   `WerkTest.uproject` from this document's tree (they are ~60 lines total).
2. Junction the plugin (above).
3. `Build.bat WerkTestEditor Win64 Development -Project=...`.
4. Run `make_master_material.py`, then `make_testbed_level.py`, both as
   `-run=pythonscript` commandlets.
5. `python adapters\unreal\tests\roundtrip_gate.py` — it imports every fixture
   itself.
6. `python tools\ue_mcp\launch_testbed.py` then `proof_session.py`.
