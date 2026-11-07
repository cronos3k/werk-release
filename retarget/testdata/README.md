# Stage 6 test corpus

Three real, foreign, freely obtainable rigs, so `tests/run_gate_6.py` can be
re-run from a clone rather than believed. Two of the three are here; the third
cannot be, and this file says why.

`tests/run_gate_6.py` re-hashes the two committed files on every run and fails
if either has moved, so the numbers in HANDOVER.md are attached to these exact
bytes and not to a URL that may have been re-tagged since.

| file | bytes | sha256 | where it came from |
|---|---|---|---|
| `CesiumMan.glb` | 438044 | `b7001eaeea8254bd44773bcd247e78696d94169388fbb2a1800fc69434e777d9` | `https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models/CesiumMan/glTF-Binary/CesiumMan.glb` |
| `CesiumMan-README.md` | 1096 | `688a1acc5ee702d98d317ba18117fb294f3b52750062d0bc9f70f7ad71391fcb` | the same directory; it carries Khronos's own licence statement, unedited |
| `02_01.bvh` | 260091 | `cf56db43157acc3d200b3d4215523f54d354a8926bea67e1f6c8031bd335ba7e` | `https://raw.githubusercontent.com/una-dinosauria/cmu-mocap/master/data/002/02_01.bvh` — Bruce Hahne's BVH conversion of the CMU Graphics Lab Motion Capture Database |
| `cmu-READMEFIRST.txt` | 13248 | `8e6fe2e640b3728ef2e43e722cb5ae9cdf0010028c0517c4226ed165f9037930` | the same repository's root; CMU's own terms, unedited. The database is free for all uses. |

## The third rig is not here, on purpose

The Unreal Engine mannequin (`SK_Mannequin` + `ThirdPersonWalk`, UE 5.7.4) is
Epic engine content. Skeleton and animation data derived from it must not be
redistributed, so it is **regenerated, never cloned**:

1. copy `C:\Program Files\Epic Games\UE_5.7\Templates\TemplateResources\High\Mannequin\Content`
   to `<lab>\Stage6UE\S6\Content\Mannequin`;
2. write `<lab>\Stage6UE\S6\S6.uproject` — a JSON file with `"EngineAssociation":
   "5.7"`, no modules, and `PythonScriptPlugin` enabled;
3. run, headless:

       UnrealEditor-Cmd.exe <lab>/Stage6UE/S6/S6.uproject -run=pythonscript ^
           -script="<repo>/retarget/tools/ue_export_skeleton.py" ^
           -unattended -nosplash -nullrhi

It writes `<lab>/Stage6UE/export/ue-mannequin.json`. Point the gate somewhere else
with `WERK_S6_UE_EXPORT`. A gate run that cannot find it **SKIPs that rig with
the reason printed**, and never folds the absence into a pass.

## Why these three and not others

Between them they break every assumption a retargeter can make, which is the
only reason a corpus of three is worth more than a corpus of one:

* **CesiumMan** — a COLLADA export. 19 joints, no naming convention a heuristic
  could use, and the left and right arm chains are numbered in OPPOSITE
  directions (`L__4_ → L__3_ → L__2_` against `R → R__2_ → R__3_`), so
  mirroring one side's map by string substitution silently swaps the shoulder
  and the wrist. No clavicles, no second spine joint, a `Z_UP` node above the
  armature, and per-joint translation keyed on every frame.
* **UE mannequin** — Z-up **and left handed**, in centimetres, with 68 bones
  including twist and IK bones that map to nothing. Its neutral is an A-pose,
  not the canonical T-pose.
* **CMU 02_01** — raw capture. 31 joints, no declared unit and no declared axis
  anywhere in the file, two zero-length hip artefacts, a two-segment neck, and
  no bind pose at all: a BVH's rest is just its OFFSETs. The calibration scan
  has to find a usable pose among 344 frames of walking.
