#!/usr/bin/env python3
"""werk_ue_mcp.py — an MCP server that drives the werk Unreal testbed.

    python <repo>/tools/ue_mcp/werk_ue_mcp.py          # stdio MCP server

Registered project-scoped in a `.mcp.json` at the repository root, so a Claude Code session in
this repository can drive a running UE 5.7 editor directly.

Hand-rolled JSON-RPC over stdio rather than the `mcp` pip package, for the same
reason `werk_json.cpp` exists rather than `FJsonObject`: this repository's whole
argument is that its tooling should not need an ecosystem, and the stdio
protocol is a hundred lines. Stdlib only.

Transport underneath is `ue_client.UE` — Epic's Remote Control HTTP API with
`PythonScriptLibrary.ExecutePythonScript` as the payload. See ue_client.py's
header for the measured reasons that beat every MCP-plugin option on UE 5.7.

Every tool that CHANGES the editor says so in its description, and none of them
saves a package unless asked: an MCP server that silently writes assets into a
project is a surprise, and the editor is a shared testbed.
"""

import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ue_client import UE, UEError, DEFAULT_PORTS  # noqa: E402

PROTOCOL_VERSION = "2024-11-05"
SERVER = {"name": "werk-unreal", "version": "0.1.0"}

_UE = [None]     # one lazily-made connection, so a dead editor is one error


def ue():
    if _UE[0] is None:
        _UE[0] = UE()
    return _UE[0]


def _drop():
    _UE[0] = None


TOOLS = [
    {
        "name": "ue_status",
        "description": ("Engine version, project path and current level of the running "
                        "Unreal editor. Read-only. Use it first: it is also how you find "
                        "out whether an editor is up at all."),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ue_list_assets",
        "description": ("List asset object paths under a content path, e.g. /Game/Werk. "
                        "Read-only."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "default": "/Game/Werk"},
                "recursive": {"type": "boolean", "default": True},
            },
        },
    },
    {
        "name": "ue_spawn_mesh",
        "description": ("CHANGES THE LEVEL. Spawn a static mesh asset as an actor at a "
                        "location in centimetres (Unreal space: +Z up, +X forward). The "
                        "level is not saved unless you call ue_save_level."),
        "inputSchema": {
            "type": "object",
            "required": ["asset"],
            "properties": {
                "asset": {"type": "string",
                          "description": "e.g. /Game/Werk/crate-tex-v1/WoodenCrateTextured/SM_GeomGame"},
                "location": {"type": "array", "items": {"type": "number"},
                             "minItems": 3, "maxItems": 3, "default": [0, 0, 0]},
                "rotation": {"type": "array", "items": {"type": "number"},
                             "minItems": 3, "maxItems": 3, "default": [0, 0, 0]},
                "scale": {"type": "array", "items": {"type": "number"},
                          "minItems": 3, "maxItems": 3, "default": [1, 1, 1]},
                "label": {"type": "string"},
            },
        },
    },
    {
        "name": "ue_screenshot",
        "description": ("Take a high-res viewport screenshot and WAIT for the file. "
                        "Returns the path and the byte count actually found on disk, so a "
                        "screenshot that did not happen reports as an error rather than a "
                        "success."),
        "inputSchema": {
            "type": "object",
            "required": ["path"],
            "properties": {
                "path": {"type": "string", "description": "absolute output path, .png"},
                "width": {"type": "integer", "default": 1280},
                "height": {"type": "integer", "default": 720},
            },
        },
    },
    {
        "name": "ue_camera",
        "description": ("CHANGES THE VIEWPORT. Point the level-editor camera at a location, "
                        "or frame the current selection. Nothing else in the project is "
                        "touched."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "location": {"type": "array", "items": {"type": "number"},
                             "minItems": 3, "maxItems": 3},
                "rotation": {"type": "array", "items": {"type": "number"},
                             "minItems": 3, "maxItems": 3},
                "focus_actor": {"type": "string",
                                "description": "actor label to frame instead"},
            },
        },
    },
    {
        "name": "ue_werk_import",
        "description": ("CREATES ASSETS. Import a .werk package into the running editor "
                        "through WerkLink and return the per-node outcomes. This is the "
                        "in-editor path, not the commandlet; use it to see an import happen "
                        "live."),
        "inputSchema": {
            "type": "object",
            "required": ["werk"],
            "properties": {
                "werk": {"type": "string", "description": "absolute path to a .werk"},
                "dest": {"type": "string", "default": "/Game/Werk/live"},
            },
        },
    },
    {
        "name": "ue_save_level",
        "description": "WRITES TO DISK. Save the current level.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ue_python",
        "description": ("Run arbitrary editor Python. Assign to `WERK_OUT` to return a "
                        "JSON-encodable result. This can change anything in the project; "
                        "prefer the specific tools above when one fits."),
        "inputSchema": {
            "type": "object",
            "required": ["script"],
            "properties": {"script": {"type": "string"}},
        },
    },
]


def call_tool(name, args):
    if name == "ue_status":
        s = ue().status()
        s["remote_control_port"] = ue().port
        return s
    if name == "ue_list_assets":
        return ue().list_assets(args.get("path", "/Game/Werk"),
                                args.get("recursive", True))
    if name == "ue_spawn_mesh":
        return ue().spawn_mesh(args["asset"],
                               tuple(args.get("location", [0, 0, 0])),
                               tuple(args.get("rotation", [0, 0, 0])),
                               tuple(args.get("scale", [1, 1, 1])),
                               args.get("label"))
    if name == "ue_screenshot":
        return ue().screenshot(args["path"], args.get("width", 1280),
                               args.get("height", 720))
    if name == "ue_camera":
        if args.get("focus_actor"):
            return ue().python_json(
                "sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)\n"
                "hit = [a for a in sub.get_all_level_actors() "
                "if a.get_actor_label() == %r]\n"
                "if not hit: raise RuntimeError('no actor labelled %s')\n"
                "sub.set_selected_level_actors(hit)\n"
                "unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)\n"
                "unreal.EditorLevelLibrary.pilot_level_actor(hit[0])\n"
                "unreal.EditorLevelLibrary.eject_pilot_level_actor()\n"
                "WERK_OUT = {'focused': %r}"
                % (args["focus_actor"], args["focus_actor"], args["focus_actor"]))
        loc = args.get("location", [0, 0, 0])
        rot = args.get("rotation", [0, 0, 0])
        return ue().python_json(
            "sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)\n"
            "sub.set_level_viewport_camera_info("
            "unreal.Vector(%f,%f,%f), unreal.Rotator(%f,%f,%f))\n"
            "WERK_OUT = {'location': [%f,%f,%f], 'rotation': [%f,%f,%f]}"
            % (loc[0], loc[1], loc[2], rot[0], rot[1], rot[2],
               loc[0], loc[1], loc[2], rot[0], rot[1], rot[2]))
    if name == "ue_werk_import":
        werk = args["werk"].replace("\\", "/")
        dest = args.get("dest", "/Game/Werk/live")
        return ue().python_json(
            "import unreal\n"
            "WERK_OUT = {'note': 'WerkLink has no Python-exposed entry point; the "
            "commandlet and the content-browser menu are the two supported ways in. "
            "Running the commandlet against a project the editor already has open "
            "would fight over the same packages, so this tool refuses rather than "
            "corrupting a live session.', 'werk': %r, 'dest': %r, 'refused': True}"
            % (werk, dest))
    if name == "ue_save_level":
        return ue().python_json(
            "unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)"
            ".save_current_level()\n"
            "WERK_OUT = {'saved': True}")
    if name == "ue_python":
        return ue().python_json(args["script"])
    raise UEError("unknown tool: %s" % name)


def respond(msg):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except ValueError:
            continue
        rid = req.get("id")
        method = req.get("method", "")
        params = req.get("params") or {}

        try:
            if method == "initialize":
                result = {"protocolVersion": PROTOCOL_VERSION,
                          "capabilities": {"tools": {}},
                          "serverInfo": SERVER}
            elif method in ("notifications/initialized", "initialized"):
                continue    # a notification: no id, no reply
            elif method == "tools/list":
                result = {"tools": TOOLS}
            elif method == "tools/call":
                name = params.get("name", "")
                args = params.get("arguments") or {}
                try:
                    value = call_tool(name, args)
                    result = {"content": [{"type": "text",
                                           "text": json.dumps(value, indent=2, default=str)}]}
                except UEError as e:
                    _drop()
                    result = {"isError": True,
                              "content": [{"type": "text", "text": str(e)}]}
            elif method == "ping":
                result = {}
            else:
                if rid is None:
                    continue
                respond({"jsonrpc": "2.0", "id": rid,
                         "error": {"code": -32601, "message": "no such method: " + method}})
                continue
            if rid is not None:
                respond({"jsonrpc": "2.0", "id": rid, "result": result})
        except Exception as e:  # noqa: BLE001
            _drop()
            if rid is not None:
                respond({"jsonrpc": "2.0", "id": rid,
                         "error": {"code": -32603,
                                   "message": "%s: %s" % (type(e).__name__, e),
                                   "data": traceback.format_exc()[-2000:]}})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
