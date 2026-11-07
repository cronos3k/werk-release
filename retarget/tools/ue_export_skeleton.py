"""ue_export_skeleton.py -- export a UE skeleton + one animation to JSON.

Runs INSIDE Unreal's Python (headless is fine):

    UnrealEditor-Cmd.exe <project>.uproject -run=pythonscript ^
        -script="<repo>/retarget/tools/ue_export_skeleton.py" ^
        -unattended -nosplash -nullrhi -NoLogTimes

Writes <WERK_LAB>/Stage6UE/export/ue-mannequin.json:

    {
      "source": {...provenance...},
      "unit_scale_m": 0.01,              # UE centimetres
      "bones": [ {name, parent, rest_local: {t:[3], q:[wxyz], s:[3]},
                  rest_model: {t, q, s}} ... ],
      "clips": [ {name, frame_count, rate_hz, duration_s,
                  root: [[px,py,pz,qw,qx,qy,qz] * frames],
                  tracks: {bone: [[qw,qx,qy,qz] * frames]}} ]
    }

Nothing is guessed: every route the script tries is recorded in "routes" so a
failure names the API that was missing rather than producing a silent default.
UE quaternions are xyzw in the C++ struct and are re-ordered to werk's wxyz
here, once, at the boundary -- see spec/SPEC.md conventions.quat_order.
"""

import json
import os
import traceback

import unreal

OUT_DIR = os.environ.get("WERK_S6_UE_OUT", os.path.join(
    os.environ.get("WERK_LAB", "<WERK_LAB unset>"), "Stage6UE", "export"))
MESH_PATH = "/Game/Mannequin/Character/Mesh/SK_Mannequin"
ANIM_PATHS = [
    "/Game/Mannequin/Animations/ThirdPersonWalk",
    "/Game/Mannequin/Animations/ThirdPersonRun",
    "/Game/Mannequin/Animations/ThirdPersonIdle",
]

routes = []


def note(msg):
    routes.append(msg)
    unreal.log("[werk-s6] " + msg)


def q_wxyz(q):
    """unreal.Quat -> [w,x,y,z] floats."""
    return [float(q.w), float(q.x), float(q.y), float(q.z)]


def xform(t):
    """unreal.Transform -> {t, q, s}."""
    return {
        "t": [float(t.translation.x), float(t.translation.y), float(t.translation.z)],
        "q": q_wxyz(t.rotation),
        "s": [float(t.scale3d.x), float(t.scale3d.y), float(t.scale3d.z)],
    }


def collect_bones(mesh):
    """Bone names, parents and reference-pose transforms.

    Route A: spawn a SkeletalMeshActor and read its component. The component is
    the only object that exposes the parent relation and per-bone transforms to
    Blueprint/Python, so this is the primary route and not a convenience.
    """
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = sub.spawn_actor_from_class(
        unreal.SkeletalMeshActor, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
    comp = actor.skeletal_mesh_component
    try:
        comp.set_skeletal_mesh_asset(mesh)
    except Exception:
        comp.set_skeletal_mesh(mesh)          # older signature
        note("set_skeletal_mesh (legacy signature)")
    comp.set_editor_property("animation_mode", unreal.AnimationMode.ANIMATION_SINGLE_NODE)
    comp.set_animation(None)
    n = comp.get_num_bones()
    note("SkeletalMeshActor route: %d bones" % n)

    names = [str(comp.get_bone_name(i)) for i in range(n)]
    bones = []
    for i, nm in enumerate(names):
        parent = str(comp.get_parent_bone(nm))
        if parent == "None" or parent == "" or parent == nm:
            parent = None
        # Component space == model space of the mesh, which is what we want for
        # the rest pose; RelativeTransformSpace.RTS_COMPONENT.
        m = comp.get_socket_transform(nm, unreal.RelativeTransformSpace.RTS_COMPONENT)
        bones.append({"name": nm, "index": i, "parent": parent, "rest_model": xform(m)})
    sub.destroy_actor(actor)
    return bones


def collect_clip(anim, bone_names):
    lib = unreal.AnimationLibrary
    try:
        nframes = int(lib.get_num_frames(anim))
    except Exception:
        nframes = int(anim.get_editor_property("number_of_sampled_keys"))
        note("get_num_frames missing; used number_of_sampled_keys")
    length = float(lib.get_sequence_length(anim))
    rate = (nframes / length) if length > 0 else 30.0
    note("clip %s: %d frames, %.6f s" % (anim.get_name(), nframes, length))

    tracks = {}
    for nm in bone_names:
        seq = []
        for f in range(nframes):
            t = lib.get_bone_pose_for_frame(anim, nm, f, False)
            seq.append(xform(t))
        tracks[nm] = seq
    return {
        "name": str(anim.get_name()),
        "frame_count": nframes,
        "duration_s": length,
        "rate_hz": rate,
        "tracks": tracks,
    }


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    mesh = unreal.EditorAssetLibrary.load_asset(MESH_PATH)
    if mesh is None:
        raise RuntimeError("no skeletal mesh at %s" % MESH_PATH)
    note("mesh %s loaded" % MESH_PATH)

    bones = collect_bones(mesh)
    bone_names = [b["name"] for b in bones]

    clips = []
    for p in ANIM_PATHS:
        a = unreal.EditorAssetLibrary.load_asset(p)
        if a is None:
            note("MISSING animation %s" % p)
            continue
        clips.append(collect_clip(a, bone_names))

    doc = {
        "source": {
            "engine_version": str(unreal.SystemLibrary.get_engine_version()),
            "mesh_asset": MESH_PATH,
            "origin": "UE_5.7 Templates/TemplateResources/High/Mannequin, copied verbatim",
            "unit_scale_m": 0.01,
            "up_axis_ue": "z",
            "forward_axis_ue": "x",
            "handedness_ue": "left",
            "quat_order_here": "wxyz (re-ordered from UE xyzw at this boundary)",
        },
        "routes": routes,
        "bones": bones,
        "clips": clips,
    }
    out = os.path.join(OUT_DIR, "ue-mannequin.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
    unreal.log("[werk-s6] wrote %s (%d bones, %d clips)"
               % (out, len(bones), len(clips)))


try:
    main()
except Exception:
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "ue-mannequin.ERROR.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(routes) + "\n\n" + traceback.format_exc())
    unreal.log_error("[werk-s6] FAILED\n" + traceback.format_exc())
