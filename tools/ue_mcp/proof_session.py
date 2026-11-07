#!/usr/bin/env python3
"""proof_session.py — the Stage 10B editor-control gate, run against a LIVE editor.

    python tools/ue_mcp/proof_session.py [--proof <testbed>/proof]

Requires an editor already up (tools/ue_mcp/launch_testbed.py). It connects over
Remote Control, does the three things the brief names -- list /Game/Werk assets,
spawn the imported crate into a level, screenshot the viewport -- and writes the
screenshots plus a JSON transcript into the proof directory.

Every clause is decided on a MEASUREMENT: a screenshot clause passes on the byte
count of a file that appeared on disk, never on an HTTP 200.
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ue_client import UE, UEError  # noqa: E402

RESULTS = []


def clause(name, ok, detail):
    RESULTS.append({"clause": name, "pass": bool(ok), "detail": detail})
    print("[%s] %-34s %s" % ("PASS" if ok else "FAIL", name, detail))
    return ok


SETUP_LEVEL = """
aes = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

# Idempotent, because this script is run more than once and a level that
# accumulates a second crate on every run makes every later screenshot a lie
# about what one import produced.
removed = []
for a in list(aes.get_all_level_actors()):
    if a.get_actor_label() in ('Key', 'Fill', 'Floor', 'Sky',
                               'WerkCrateTextured', 'WerkCratePlain'):
        removed.append(a.get_actor_label())
        aes.destroy_actor(a)

# A real sun plus a real sky, not a dim directional light on its own. The first
# run of this used intensity 6 lux with a SkyLight that had a black sky to
# capture, and produced a screenshot in which the crate was technically present
# and visually absent -- which proves a screenshot happened and nothing about
# whether the import worked.
sky = aes.spawn_actor_from_class(unreal.SkyAtmosphere, unreal.Vector(0, 0, 0))
sky.set_actor_label('Sky')

# The sun points roughly the way the camera looks (yaw 35, pitch -35), so the
# faces in frame are the LIT ones. The first version aimed it at yaw 150 -- away
# from the camera -- and the textured crate, whose albedo is mid-brown, read as
# near-black in its own shadow while the untextured white one still looked
# bright. That is a lighting artefact that looks exactly like a texture failure,
# and it cost an hour of chasing a bug that was not there.
L = aes.spawn_actor_from_class(unreal.DirectionalLight,
                               unreal.Vector(0, 0, 600), unreal.Rotator(0, -35, 35))
L.set_actor_label('Key')
LC = L.get_component_by_class(unreal.DirectionalLightComponent)
LC.set_intensity(12.0)
LC.set_editor_property('atmosphere_sun_light', True)

S = aes.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 400))
S.set_actor_label('Fill')
SC = S.get_component_by_class(unreal.SkyLightComponent)
SC.set_editor_property('real_time_capture', True)
SC.set_intensity(1.5)

P = aes.spawn_actor_from_object(unreal.load_asset('/Engine/BasicShapes/Plane'),
                                unreal.Vector(0, 0, -1))
P.set_actor_label('Floor')
P.set_actor_scale3d(unreal.Vector(16, 16, 1))

WERK_OUT = {'removed': sorted(set(removed)),
            'actors': sorted(a.get_actor_label() for a in aes.get_all_level_actors())}
"""

SHADING = """
m = unreal.EditorAssetLibrary.load_asset(%r)
if m is None:
    raise RuntimeError('mesh not found')
slots = m.static_materials
out = []
for i, s in enumerate(slots):
    mi = m.get_material(i)
    row = {'slot': str(s.material_slot_name), 'material': mi.get_name() if mi else None}
    if isinstance(mi, unreal.MaterialInstanceConstant):
        row['parent'] = mi.parent.get_name() if mi.parent else None
        row['textures'] = {}
        for p in ('BaseColorTexture', 'MetallicRoughnessTexture', 'NormalTexture'):
            t = unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(mi, p)
            row['textures'][p] = t.get_name() if t else None
        row['switches'] = {}
        for p in ('UseBaseColorTexture', 'UseMetallicRoughnessTexture', 'UseNormalTexture'):
            row['switches'][p] = bool(
                unreal.MaterialEditingLibrary.get_material_instance_static_switch_parameter_value(mi, p))
    out.append(row)
WERK_OUT = {'uvs': unreal.EditorStaticMeshLibrary.get_num_uv_channels(m, 0),
            'lods': unreal.EditorStaticMeshLibrary.get_lod_count(m),
            'slots': out}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--proof", default=os.path.join(
        os.environ.get("WERK_UE_TESTBED", "<WERK_UE_TESTBED unset>"), "proof"))
    ap.add_argument("--port", type=int, default=None)
    a = ap.parse_args()
    proof = os.path.abspath(a.proof)
    os.makedirs(proof, exist_ok=True)

    try:
        ue = UE(port=a.port)
    except UEError as e:
        print("SKIP: %s" % e)
        return 3

    print("werk Stage 10B -- editor control, measured against a live UE 5.7 editor")
    st = ue.status()
    print("engine  : %s" % st["engine"])
    print("project : %s" % st["project"])
    print("port    : %d (Remote Control HTTP)\n" % ue.port)

    # (a) list the imported assets
    assets = ue.list_assets("/Game/Werk", True)
    tex = [x for x in assets if "/T_" in x]
    clause("MCP: list /Game/Werk assets", len(assets) >= 50,
           "%d assets, %d textures, e.g. %s" % (len(assets), len(tex), assets[0] if assets else "-"))

    # the level furniture, so a screenshot shows a LIT object and not a black frame
    setup = ue.python_json(SETUP_LEVEL)
    clause("level: sun, sky and floor", len(setup["actors"]) == 4,
           "rebuilt from scratch (removed %s); actors now: %s"
           % (setup["removed"] or "nothing", ", ".join(setup["actors"])))

    mesh = "/Game/Werk/crate-tex-v1/WoodenCrateTextured/SM_GeomGame"
    shading = ue.python_json(SHADING % mesh)
    slot0 = shading["slots"][0] if shading["slots"] else {}
    textures_bound = [k for k, v in (slot0.get("textures") or {}).items() if v]
    switches_on = [k for k, v in (slot0.get("switches") or {}).items() if v]
    clause("in-editor: the mesh IS shaded by the imported textures",
           slot0.get("parent") == "M_WerkPBR" and len(textures_bound) == 3
           and len(switches_on) == 3 and shading["uvs"] >= 1,
           "slot '%s' -> %s (parent %s), %d UV channel(s), textures %s, switches %s"
           % (slot0.get("slot"), slot0.get("material"), slot0.get("parent"),
              shading["uvs"], textures_bound, switches_on))

    # (b) spawn it
    spawned = []
    for label, asset, loc in (
        ("WerkCrateTextured", mesh, (0.0, 0.0, 55.0)),
        ("WerkCratePlain", "/Game/Werk/crate-v1/WoodenCrate/SM_GeomGame", (220.0, 0.0, 55.0)),
    ):
        try:
            spawned.append(ue.spawn_mesh(asset, loc, label=label))
        except UEError as e:
            spawned.append({"error": str(e), "asset": asset})
    clause("MCP: spawn the imported meshes",
           all("actor" in s for s in spawned),
           "; ".join("%s @ %s" % (s.get("label", "?"), s.get("location")) for s in spawned))

    # (c) screenshots
    # unreal.Rotator's PYTHON constructor is (roll, pitch, yaw) -- not the
    # (pitch, yaw, roll) the editor's details panel shows. The first run of this
    # script passed Rotator(-18, 40, 0) meaning "pitch down 18, yaw 40" and got
    # roll -18, pitch 40: a camera looking at the sky, and a proof screenshot
    # that proved only that a screenshot had happened. Named here because the
    # mistake is silent and the fix is not obvious from the argument list.
    #
    # The angles are COMPUTED from the two positions rather than typed, so the
    # camera cannot drift away from what it is supposed to be framing.
    ue.python_json(
        "import math\n"
        "eye = unreal.Vector(-360.0, -330.0, 260.0)\n"
        "target = unreal.Vector(110.0, 0.0, 60.0)\n"
        "dx, dy, dz = target.x-eye.x, target.y-eye.y, target.z-eye.z\n"
        "yaw = math.degrees(math.atan2(dy, dx))\n"
        "pitch = math.degrees(math.atan2(dz, math.hypot(dx, dy)))\n"
        "sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)\n"
        "sub.set_level_viewport_camera_info(eye, unreal.Rotator(0.0, pitch, yaw))\n"
        "loc, rot = sub.get_level_viewport_camera_info()\n"
        "WERK_OUT = {'eye': [loc.x, loc.y, loc.z],\n"
        "            'rotator_read_back': [rot.roll, rot.pitch, rot.yaw]}")
    time.sleep(1.5)

    # Two framings: the wide shot that shows both crates side by side, and a
    # close-up of the textured one where the plank grain and the normal map are
    # large enough to judge.
    #
    # NOT two view modes. `viewmode unlit` over this channel is ACCEPTED by the
    # console -- it appears in the log as `Cmd: viewmode unlit` -- and does not
    # change the level viewport, which produced two "lit" and "unlit" images
    # that were the same picture. Rather than ship a pair of screenshots whose
    # labels are wrong, the view-mode idea is dropped and the limitation is
    # written down in adapters/unreal/TESTBED.md.
    shots = []
    for name, eye, target in (
        ("01-viewport-wide.png", (-360.0, -330.0, 260.0), (110.0, 0.0, 60.0)),
        ("02-viewport-closeup.png", (-150.0, -140.0, 110.0), (0.0, 0.0, 55.0)),
    ):
        ue.python_json(
            "import math\n"
            "eye = unreal.Vector(%f, %f, %f)\n"
            "target = unreal.Vector(%f, %f, %f)\n"
            "dx, dy, dz = target.x-eye.x, target.y-eye.y, target.z-eye.z\n"
            "yaw = math.degrees(math.atan2(dy, dx))\n"
            "pitch = math.degrees(math.atan2(dz, math.hypot(dx, dy)))\n"
            "sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)\n"
            "sub.set_level_viewport_camera_info(eye, unreal.Rotator(0.0, pitch, yaw))\n"
            "WERK_OUT = 'framed'"
            % (eye[0], eye[1], eye[2], target[0], target[1], target[2]))
        time.sleep(1.5)
        try:
            s = ue.screenshot(os.path.join(proof, name), 1280, 720)
            s["framing"] = {"eye": list(eye), "target": list(target)}
            shots.append(s)
        except UEError as e:
            shots.append({"path": name, "error": str(e), "bytes": 0})

    if len(shots) == 2 and all(s.get("bytes", 0) > 0 for s in shots):
        a_bytes = open(shots[0]["path"], "rb").read()
        b_bytes = open(shots[1]["path"], "rb").read()
        clause("screenshots: the two framings really differ", a_bytes != b_bytes,
               "%d B vs %d B, %s"
               % (len(a_bytes), len(b_bytes),
                  "different images" if a_bytes != b_bytes
                  else "IDENTICAL -- the camera command did not take"))

    clause("MCP: viewport screenshots on disk",
           all(s.get("bytes", 0) > 10000 for s in shots),
           "; ".join("%s %d B" % (os.path.basename(s["path"]), s.get("bytes", 0))
                     for s in shots))

    transcript = {
        "engine": st["engine"], "project": st["project"], "port": ue.port,
        "asset_count": len(assets), "assets": assets,
        "shading": shading, "spawned": spawned, "screenshots": shots,
        "clauses": RESULTS,
    }
    tpath = os.path.join(proof, "session.json")
    with open(tpath, "w", encoding="utf-8") as fh:
        json.dump(transcript, fh, indent=2, default=str)
    print("\ntranscript: %s" % tpath)

    npass = sum(1 for r in RESULTS if r["pass"])
    print("%d PASS, %d FAIL" % (npass, len(RESULTS) - npass))
    print("EDITOR CONTROL: %s" % ("PROVEN" if npass == len(RESULTS) else "NOT PROVEN"))
    return 0 if npass == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
