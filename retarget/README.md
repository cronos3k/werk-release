# `retarget/` — the one-calibration-pose retargeter

Stage 6's implementation and the proof that goes with it. Python, stdlib +
numpy. Nothing here is on a `core.loader`'s path; the bootstrap readers stay
dependency-free.

    python tests/run_gate_6.py            # the gate: 33 PASS, 0 FAIL, 0 SKIP
    python fixtures/build_retarget_fixture.py

## The claim

Given a foreign rig — different bone names, different bone count, different
proportions, different rest pose — **one** pose is enough to bind it to the werk
canonical humanoid. After that, clips convert in both directions.

A bind is three things and nothing else:

| | |
|---|---|
| `scale` | the rig's stature relative to the canonical 1.75 m. **Recovered, never declared.** |
| `qA` | the rig's whole-body frame relative to werk model space — this is what absorbs Z-up, an armature node's own matrix, and a capture stage that faced the other way. **Recovered, never hard-coded.** |
| `O[b]` | one constant rotation per mapped bone. |

Retargeting bone *b* at frame *f* is then `Q_canon[b](f) = qA · Q_foreign[b](f)
· O[b]`.

## Why one pose is enough

The per-bone direction error is the angle between the same rotation applied to
two FIXED vectors, so it does not depend on *f*: **a single calibration
measurement bounds every frame of every clip.** The argument is written out in
`calibrate.py`, and `frame_invariance_residual` measures it rather than
asserting it — 3.03e-14 rad of spread across 29 frames on the Unreal mannequin.

The proof needs the two foreign bones to be parent and child of each other. Where
a rig interposes an animated joint between two mapped bones — CMU's zero-length
`LHipJoint` — the error becomes frame-dependent by exactly that joint's motion,
which is real motion the canonical 23-bone rig has nowhere to put. Measured
separately, reported separately, never averaged in. That is finding S6-3.

## What this does NOT do

**Bone correspondence.** Which foreign bone is the left forearm is a naming
question, not a geometry question, and it is answered by DATA: the `retarget`
maps that travel with the canonical skeleton, and the ones in `maps/`. The
calibration pose fixes the geometry of an already-stated correspondence. Keeping
the two problems apart is deliberate — a solver that guessed names would make its
geometric residual unattributable.

## Layout

| file | |
|---|---|
| `quat.py` | quaternion algebra; `qangle` via the stable `2·atan2(\|p−q\|,\|p+q\|)`; Umeyama similarity with **reflections refused** |
| `skeleton.py` | `Rig` — canonical and foreign alike — the FK evaluator, and `Clip` |
| `calibrate.py` | the solver, the clip auto-scan, and the frame-invariance measurement |
| `retarget.py` | foreign → canonical → any other bound rig, both directions from one bind |
| `writers.py` | `core.skeleton` and `core.anim.clip` (WKAC) writers, plus a decoder written from the layout rather than from the writer |
| `sources/gltf.py` | GLB/glTF, no glTF library |
| `sources/bvh.py` | BVH, Euler channel order read per joint from the file |
| `sources/ue.py` | the Unreal export, including the left→right handedness flip |
| `tools/ue_export_skeleton.py` | runs inside Unreal, headless |
| `maps/*.json` | bone correspondence as data |
| `testdata/` | the corpus, with provenance and hashes — see its README |

Every axis, handedness and unit conversion happens **once**, in the importer for
that format, and everything downstream of `sources/` is already in werk
convention. A conversion that happens in one named place can be tested; one that
happens wherever it is needed cannot.
