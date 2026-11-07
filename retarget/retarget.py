"""retarget.py -- foreign clip -> canonical clip -> any other bound rig.

Both directions use the SAME bind and nothing else, so a round trip is a real
test of the bind rather than of a second, differently-tuned code path.

    to_canonical(bind_A, clip_on_A)      -> canonical clip
    to_rig(bind_B, canonical_clip)       -> clip on rig B

and therefore

    to_rig(bind_A, to_canonical(bind_A, c))   must return c (mapped bones)
    to_rig(bind_B, to_canonical(bind_A, c))   is A's motion on B

DECISIONS A LATER READER WILL ASK ABOUT
---------------------------------------
1. **The canonical `root` bone is never driven by a mapped foreign bone, even
   when the name map offers one** (the shipped `ue-mannequin` map does: UE's
   `root` -> canonical `root`). The root track exists to carry where the
   character IS; a foreign rig's root bone is sometimes the pelvis, sometimes a
   floor-locked locomotion node keyed at identity for the whole clip (Unreal's
   is), and sometimes absent. Deriving the root from the HIPS is the only rule
   that behaves the same for all three. Root rotation is identity and all
   orientation lives on `hips`, which is exactly what `flags` bit 2
   (ROOT_YAW_ONLY) in animclip.layout.txt anticipates -- a stricter case of it.

   RULING 9 (2026-08-08) MADE THIS NORMATIVE RATHER THAN A SOLVER CHOICE. The
   canonical `root` is a BASE BONE at the origin and the pelvis is parented to
   it, precisely so that a clip which is not in-place carries its locomotion on
   the root while the pelvis stays a body bone. What this module already did by
   argument, the skeleton canon now requires: locomotion on `root`, orientation
   and the pelvis's own bob on `hips`. Nothing in the code changed; the reason
   it is right stopped being this docstring's opinion. See spec/SPEC.md 3.5.
2. **Unmapped canonical bones hold their rest rotation relative to their nearest
   mapped ancestor.** They do not interpolate, and they do not stay at model
   identity. A rig with no `spine2` should carry the whole spine bend on
   `spine1` and `spine3` and leave `spine2` straight *in the torso's frame*,
   which is what this rule produces and what the alternative does not.
3. **Bone lengths are never touched.** Only rotations cross. That is what makes
   a retarget preserve a pose rather than a silhouette, and it is why the
   position residuals reported by the gate are large where proportions differ
   and the rotation residuals are not.
"""

import numpy as np

from .quat import qinv, qmul, qnorm
from .skeleton import Clip

HIPS = "hips"
ROOT = "root"


def _canonical_pose(bind, Qf):
    """Model-space canonical rotations for one frame, given the source rig's
    model-space rotations."""
    canon = bind.canon
    qA = bind.qA
    Qc = np.empty((canon.n, 4))
    mapped = {ci: fi for fi, ci in bind.pairs}
    root_i = canon.index[ROOT]
    for i in range(canon.n):
        if i == root_i:
            Qc[i] = np.array([1.0, 0.0, 0.0, 0.0])          # decision 1
            continue
        if i in mapped:
            Qc[i] = qnorm(qmul(qmul(qA, Qf[mapped[i]]), bind.O[i]))
        else:
            p = int(canon.parent[i])
            Qc[i] = qnorm(qmul(Qc[p], canon.local_q[i]))     # decision 2
    return Qc


def to_canonical(bind, clip, clip_id=None):
    canon = bind.canon
    hips_c = canon.index[HIPS]
    root_c = canon.index[ROOT]
    mapped = {ci: fi for fi, ci in bind.pairs}
    if hips_c not in mapped:
        raise ValueError("rig %r has no bone mapped to canonical 'hips'; the root "
                         "track cannot be derived" % bind.rig.rig_id)
    hips_f = mapped[hips_c]
    hips_rest = canon.local_t[hips_c] + canon.local_t[root_c]

    F = clip.frames
    local_q = np.empty((F, canon.n, 4))
    root_t = np.empty((F, 3))
    for f in range(F):
        Qf, Pf = clip.fk_frame(f)
        Qc = _canonical_pose(bind, Qf)
        local_q[f] = canon.localise(Qc)
        target_hips = bind.to_canon_pos(Pf[hips_f])[0]
        root_t[f] = target_hips - hips_rest
    return Clip(clip_id or (clip.clip_id + "-canonical"), canon, clip.rate_hz,
                local_q, root_t, root_bone=ROOT,
                source={"retargeted_from": bind.rig.rig_id,
                        "source_clip": clip.clip_id,
                        "bind": bind.summary()})


def to_rig(bind, cclip, clip_id=None):
    """Canonical clip -> a clip on the bound foreign rig."""
    rig = bind.rig
    canon = bind.canon
    if cclip.rig is not canon and cclip.rig.rig_id != canon.rig_id:
        raise ValueError("clip is on rig %r, not on the canonical rig %r"
                         % (cclip.rig.rig_id, canon.rig_id))
    qAi = qinv(bind.qA)
    mapped = {ci: fi for fi, ci in bind.pairs}
    inv_map = {fi: ci for ci, fi in mapped.items()}
    hips_c = canon.index[HIPS]
    hips_f = mapped[hips_c]

    F = cclip.frames
    local_q = np.empty((F, rig.n, 4))
    root_t = np.empty((F, 3))
    for f in range(F):
        Qc, Pc = cclip.fk_frame(f)
        Qf = np.empty((rig.n, 4))
        for i in range(rig.n):
            if i in inv_map:
                ci = inv_map[i]
                Qf[i] = qnorm(qmul(qmul(qAi, Qc[ci]), qinv(bind.O[ci])))
            else:
                p = int(rig.parent[i])
                Qf[i] = rig.local_q[i] if p < 0 else qnorm(qmul(Qf[p], rig.local_q[i]))
        local_q[f] = rig.localise(Qf)
        _, P0 = rig.fk(local_q=local_q[f])
        want = bind.from_canon_pos(Pc[hips_c])[0]
        root_t[f] = want - P0[hips_f]
    return Clip(clip_id or (cclip.clip_id + "-on-" + rig.rig_id), rig, cclip.rate_hz,
                local_q, root_t, root_bone=rig.names[rig.roots()[0]],
                source={"retargeted_to": rig.rig_id, "source_clip": cclip.clip_id,
                        "bind": bind.summary()})


# --- measurement ------------------------------------------------------------

def compare_local(a, b, bones=None):
    """Per-bone local rotation disagreement between two clips on the same rig."""
    from .quat import qangle
    if a.rig.names != b.rig.names:
        raise ValueError("clips are on different rigs")
    if a.frames != b.frames:
        raise ValueError("clips have different frame counts (%d vs %d)"
                         % (a.frames, b.frames))
    idx = list(range(a.rig.n)) if bones is None else [a.rig.index[n] for n in bones]
    ang = qangle(a.local_q[:, idx, :], b.local_q[:, idx, :])
    worst = int(np.unravel_index(np.argmax(ang), ang.shape)[1])
    return {
        "bones": len(idx),
        "frames": a.frames,
        "max_rad": float(ang.max()),
        "rms_rad": float(np.sqrt(np.mean(ang ** 2))),
        "worst_bone": a.rig.names[idx[worst]],
    }


def compare_model(a, b, bones=None):
    """Per-bone MODEL-space rotation disagreement, plus head positions.

    Model space is the honest place to compare two clips that went round
    different hierarchies: a local rotation is only meaningful next to its
    parent, and two decompositions of the same pose can disagree locally while
    describing the same character.
    """
    from .quat import qangle
    idx = list(range(a.rig.n)) if bones is None else [a.rig.index[n] for n in bones]
    Qa, Pa = a.fk_all()
    Qb, Pb = b.fk_all()
    ang = qangle(Qa[:, idx, :], Qb[:, idx, :])
    dp = np.linalg.norm(Pa[:, idx, :] - Pb[:, idx, :], axis=-1)
    worst = int(np.unravel_index(np.argmax(ang), ang.shape)[1])
    return {
        "bones": len(idx),
        "frames": a.frames,
        "max_rad": float(ang.max()),
        "rms_rad": float(np.sqrt(np.mean(ang ** 2))),
        "worst_bone": a.rig.names[idx[worst]],
        "max_position_m": float(dp.max()),
        "rms_position_m": float(np.sqrt(np.mean(dp ** 2))),
    }
