"""make_testbed_level.py — create /Game/Maps/WerkTestbed, the standing level.

    UnrealEditor-Cmd.exe <Project>.uproject -run=pythonscript \
        -script="<repo>/adapters/unreal/tools/make_testbed_level.py"

It creates the map EMPTY. `tools/ue_mcp/proof_session.py` furnishes it (sun,
sky, floor) over Remote Control every time it runs, and does so idempotently,
because a level that accumulates a second crate on every run makes every later
screenshot a lie about what one import produced. Furnishing it here as well
would be a second authority for the same three actors.

One measured caveat behind that split: an actor's light component is reached
with `get_component_by_class(unreal.DirectionalLightComponent)`, NOT
`actor.directional_light_component` -- the latter does not exist on
`unreal.DirectionalLight` and the attribute error inside a commandlet surfaces
as an access violation with no Python frame, which is a very long way from
"wrong attribute name".
"""

import unreal

MAP = "/Game/Maps/WerkTestbed"

les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)

# Idempotent. `new_level` refuses when the map already exists and then
# `save_current_level` fails too, because there is no current level to save --
# two errors and a non-zero exit for a map that was already fine.
unreal.AssetRegistryHelpers.get_asset_registry().scan_paths_synchronous(
    ["/Game/Maps"], force_rescan=True)
if unreal.EditorAssetLibrary.does_asset_exist(MAP):
    unreal.log("WERKLEVEL %s already exists; nothing to do" % MAP)
else:
    les.new_level(MAP)
    les.save_current_level()
    unreal.log("WERKLEVEL created %s (empty; proof_session.py furnishes it)" % MAP)
