"""calibrate.py -- bind a foreign rig to the canonical humanoid from ONE pose.

THE CLAIM THIS FILE IMPLEMENTS
------------------------------
Given a foreign rig -- different bone names, different bone count, different
proportions, different rest pose -- ONE pose in which that rig is holding the
canonical calibration pose is enough to bind it. After the bind, any clip on
that rig converts to a canonical clip, and any canonical clip converts back.

WHAT A BIND IS
--------------
Three things, and nothing else:

  1. `scale`   one number: the foreign rig's stature relative to the canonical
               1.75 m. Recovered, never declared.
  2. `qA`      one rotation: the foreign rig's whole-body frame relative to
               werk model space. This is what absorbs Z-up vs Y-up, an armature
               node's own matrix, and a capture stage that faced the other way.
               Recovered, never hard-coded -- hard-coding it would delete the
               only interesting part of the test.
  3. `O[b]`    one constant rotation per mapped bone: the difference between
               how the foreign rig holds that bone in the calibration pose and
               how the canonical rig holds it.

WHY ONE POSE IS ENOUGH, STATED SO IT CAN BE CHECKED
---------------------------------------------------
Retargeting bone b at frame f is `Q_canon[b](f) = qA * Q_foreign[b](f) * O[b]`.
Both sides are model-space rotations, so the per-bone direction error at frame f
is the angle between

    qA * Q_f[b](f) * (O[b] applied to the canonical bone axis)   and
    qA * Q_f[b](f) * (the foreign bone's own axis)

which is the SAME rotation applied to two FIXED vectors. The angle between two
fixed vectors does not depend on f. So the per-bone pose error of the whole clip
is exactly the per-bone pose error of the calibration pose -- a single
measurement bounds every frame, and that is the precise sense in which one pose
is enough. `Bind.frame_invariance_residual_rad` measures it instead of asserting
it, over every frame, because a proof in a docstring is not a gate.

WHAT THIS FILE DOES NOT DO
--------------------------
Bone CORRESPONDENCE. Which foreign bone is the left forearm is a naming
question, not a geometry question, and it is answered by data -- the retarget
maps that travel with the canonical skeleton (`retarget` in
spec/skeleton/canonical-humanoid-v1.json) and the ones in `retarget/maps/`. The
calibration pose fixes the GEOMETRY of an already-stated correspondence. Keeping
those two problems apart is deliberate: a solver that guessed names would make
its geometric residual unattributable.
"""

import numpy as np

from .quat import (mat_to_quat, qangle, qinv, qmul, qnorm, qrot,
                   umeyama_similarity)


class Bind:
    def __init__(self, rig, canon, pairs, scale, R, t, O, calibration, residuals):
        self.rig = rig
        self.canon = canon
        self.pairs = pairs                 # [(foreign_index, canonical_index)]
        self.scale = float(scale)
        self.R = np.asarray(R, dtype=np.float64)
        self.qA = mat_to_quat(self.R)
        self.t = np.asarray(t, dtype=np.float64)
        self.O = O                         # {canonical_index: quat}
        self.calibration = calibration     # provenance of the chosen pose
        self.residuals = residuals

    # foreign model space -> canonical model space, for POSITIONS
    def to_canon_pos(self, p):
        return (self.scale * (self.R @ np.atleast_2d(p).T).T) + self.t

    def from_canon_pos(self, p):
        return (self.R.T @ (np.atleast_2d(p) - self.t).T).T / self.scale

    @property
    def mapped_canonical(self):
        return sorted(ci for _, ci in self.pairs)

    def summary(self):
        d = dict(self.residuals)
        d.update({
            "rig": self.rig.rig_id,
            "scale": self.scale,
            "qA_wxyz": [float(x) for x in self.qA],
            "pairs": len(self.pairs),
            "calibration": self.calibration,
        })
        return d


def direction_pairs(rig, canon, name_map):
    """Bone-direction correspondences: (foreign_parent, foreign_child,
    canonical_parent, canonical_child).

    A bone's DIRECTION is proportion-free, which is the whole reason the scan
    scores on directions and not on positions. Two rigs with a 30 % limb-length
    difference holding the same pose have a large position residual and a zero
    direction residual, and only one of those two numbers is about the pose.
    """
    out = []
    fwd = {}
    for fname, cname in name_map.items():
        if fname in rig.index and cname in canon.index:
            if cname == "root":
                # The canonical root is never driven by a mapped foreign bone
                # (retarget.py decision 1): it carries WHERE the character is,
                # derived from the hips. Letting it into the bind would put a
                # rotation on it that the retargeter then ignores, and the
                # difference would surface as unattributable residual.
                continue
            fwd[canon.index[cname]] = rig.index[fname]
    for ci, fi in fwd.items():
        for cj in range(canon.n):
            if int(canon.parent[cj]) == ci and cj in fwd:
                out.append((fi, fwd[cj], ci, cj))
    return out, fwd


def _kabsch(src, dst, weights=None):
    """Rotation-only fit of unit vectors src -> dst. Reflections refused, for
    the reason `umeyama_similarity` gives at length."""
    src = np.asarray(src, dtype=np.float64)
    dst = np.asarray(dst, dtype=np.float64)
    w = np.ones(len(src)) if weights is None else np.asarray(weights, dtype=np.float64)
    H = (w[:, None] * dst).T @ src
    U, D, Vt = np.linalg.svd(H)
    S = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        S[2, 2] = -1.0
    return U @ S @ Vt


def score_pose(rig, canon, name_map, Qf, Pf, dirs=None, fwd=None):
    """How well does this foreign pose hold the canonical calibration pose?

    Returns (rms_rad, max_rad, R, scale, t, position_rms_m, per_bone).
    """
    if dirs is None:
        dirs, fwd = direction_pairs(rig, canon, name_map)
    Qc, Pc = canon.rest_fk()

    src = []
    dst = []
    used = []
    for fi, fj, ci, cj in dirs:
        a = Pf[fj] - Pf[fi]
        b = Pc[cj] - Pc[ci]
        na = np.linalg.norm(a)
        nb = np.linalg.norm(b)
        if na < 1e-9 or nb < 1e-9:
            continue        # a zero-length joint (CMU's LHipJoint) says nothing
        src.append(a / na)
        dst.append(b / nb)
        used.append((fi, fj, ci, cj))
    if len(src) < 3:
        raise ValueError("only %d usable direction pairs; a bind needs at least 3"
                         % len(src))
    src = np.array(src)
    dst = np.array(dst)
    R = _kabsch(src, dst)
    ang = np.arccos(np.clip(np.sum((R @ src.T).T * dst, axis=1), -1.0, 1.0))
    rms = float(np.sqrt(np.mean(ang ** 2)))
    mx = float(ang.max())

    # scale + translation from the mapped joint POSITIONS, with R held fixed
    fs = np.array([Pf[fi] for fi in fwd.values()])
    cs = np.array([Pc[ci] for ci in fwd.keys()])
    rf = (R @ fs.T).T
    mf = rf.mean(axis=0)
    mc = cs.mean(axis=0)
    var = float(((rf - mf) ** 2).sum())
    scale = float(((rf - mf) * (cs - mc)).sum() / var) if var > 0 else 1.0
    t = mc - scale * mf
    pos_rms = float(np.sqrt(np.mean(((scale * rf + t) - cs) ** 2 * 3.0)))
    return rms, mx, R, scale, t, pos_rms, (used, ang)


def solve(rig, canon, name_map, local_q=None, local_t=None, root_offset=None,
          calibration=None):
    """Bind `rig` to `canon` from ONE pose (default: the rig's own rest pose)."""
    Qf, Pf = rig.fk(local_q=local_q, local_t=local_t, root_offset=root_offset)
    dirs, fwd = direction_pairs(rig, canon, name_map)
    rms, mx, R, scale, t, pos_rms, (used, ang) = score_pose(
        rig, canon, name_map, Qf, Pf, dirs, fwd)

    qA = mat_to_quat(R)
    Qc, _ = canon.rest_fk()
    O = {}
    for ci, fi in fwd.items():
        O[ci] = qnorm(qmul(qinv(qmul(qA, Qf[fi])), Qc[ci]))

    per_bone = {}
    for k, (fi, fj, ci, cj) in enumerate(used):
        per_bone[canon.names[ci] + "->" + canon.names[cj]] = float(ang[k])

    residuals = {
        "direction_rms_rad": rms,
        "direction_max_rad": mx,
        "position_rms_m": pos_rms,
        "per_bone_direction_rad": per_bone,
    }
    pairs = [(fi, ci) for ci, fi in fwd.items()]
    return Bind(rig, canon, pairs, scale, R, t, O,
                calibration or {"source": "rest-pose"}, residuals)


def scan_clip(clip, canon, name_map, stride=1, include_rest=True):
    """Auto-scan a clip for the frame that best holds the calibration pose.

    Returns (bind, scores) where `scores` is the per-candidate direction RMS in
    radians. The whole distribution is returned, not just its minimum, because
    "one calibration pose is enough" only means something if the landscape has a
    minimum: if every frame binds as well as every other, the pose is doing no
    work and the claim is empty. The gate checks the margin.
    """
    rig = clip.rig
    dirs, fwd = direction_pairs(rig, canon, name_map)
    candidates = []
    if include_rest:
        candidates.append(("rest", None))
    for f in range(0, clip.frames, stride):
        candidates.append(("frame", f))

    scores = []
    best = None
    for kind, f in candidates:
        if kind == "rest":
            Qf, Pf = rig.rest_fk()
        else:
            Qf, Pf = clip.fk_frame(f)
        rms = score_pose(rig, canon, name_map, Qf, Pf, dirs, fwd)[0]
        scores.append({"kind": kind, "frame": f, "direction_rms_rad": rms})
        if best is None or rms < best[0]:
            best = (rms, kind, f)

    rms, kind, f = best
    if kind == "rest":
        bind = solve(rig, canon, name_map,
                     calibration={"source": "rest-pose", "scanned": len(candidates),
                                  "direction_rms_rad": rms})
    else:
        lt = None if clip.bone_t is None else clip.bone_t[f]
        ro = None if clip.bone_t is not None else clip.root_t[f]
        bind = solve(rig, canon, name_map, local_q=clip.local_q[f], local_t=lt,
                     root_offset=ro,
                     calibration={"source": "clip-frame", "clip": clip.clip_id,
                                  "frame": f, "t_s": f / clip.rate_hz,
                                  "scanned": len(candidates),
                                  "direction_rms_rad": rms})
    arr = np.array([s["direction_rms_rad"] for s in scores])
    bind.residuals["scan_best_rad"] = float(arr.min())
    bind.residuals["scan_median_rad"] = float(np.median(arr))
    bind.residuals["scan_worst_rad"] = float(arr.max())
    bind.residuals["scan_margin"] = float(arr.min() / np.median(arr)) if np.median(arr) > 0 else 0.0
    bind.scan_scores = scores
    return bind, scores


def frame_invariance_residual(bind, clip):
    """Measure the frame-invariance argued in this module's docstring.

    For every frame and every mapped bone with a mapped child, the angle between
    the canonical bone direction produced by the retarget and the source rig's
    own bone direction carried through `qA`.

    THE MEASUREMENT CORRECTED THE ARGUMENT, so the argument is restated here
    with the condition it was missing. The proof needs the source bone
    direction to be a FIXED vector in the source bone's own frame. It is fixed
    when the corresponding foreign bones are parent and child of each other,
    because then the direction is the child's constant rest offset. It is NOT
    fixed when the foreign rig interposes an animated joint between them --
    CMU's zero-length `LHipJoint` sits between `Hips` and `LeftUpLeg`, and the
    canonical rig has nowhere to put its rotation. So:

      * ADJACENT pairs   -- frame-invariant, and this function proves it to
                            ~1e-15 rather than asserting it.
      * INTERPOSED pairs -- frame-DEPENDENT, and the spread is exactly the
                            motion of the interposed joints, which is real
                            motion the canonical 23-bone rig cannot carry.
                            Reported as a number, never averaged into the
                            invariant set. See finding S6-3.
    """
    from .retarget import to_canonical
    rig = bind.rig
    canon = bind.canon
    dirs, fwd = direction_pairs(rig, canon, bind_name_map(bind))
    cclip = to_canonical(bind, clip)
    Qc, Pc = cclip.fk_all()

    keep = []
    for fi, fj, ci, cj in dirs:
        adjacent = int(rig.parent[fj]) == fi
        keep.append((fi, fj, ci, cj, adjacent))

    per_frame = []
    for f in range(clip.frames):
        Qf, Pf = clip.fk_frame(f)
        row = []
        for fi, fj, ci, cj, _adj in keep:
            a = Pf[fj] - Pf[fi]
            b = Pc[f][cj] - Pc[f][ci]
            na = np.linalg.norm(a)
            nb = np.linalg.norm(b)
            if na < 1e-9 or nb < 1e-9:
                row.append(np.nan)
                continue
            a = bind.R @ (a / na)
            row.append(np.arccos(np.clip(float(np.dot(a, b / nb)), -1.0, 1.0)))
        per_frame.append(row)
    A = np.array(per_frame)                      # (F, pairs)
    adj = np.array([k[4] for k in keep])
    usable = ~np.isnan(A).all(axis=0)
    spread = np.zeros(A.shape[1])
    if usable.any():
        spread[usable] = (np.nanmax(A[:, usable], axis=0)
                          - np.nanmin(A[:, usable], axis=0))
    a_mask = adj & usable
    i_mask = (~adj) & usable

    def stat(mask):
        if not mask.any():
            return None
        sub = A[:, mask]
        return {
            "pairs": int(mask.sum()),
            "rms_rad": float(np.sqrt(np.nanmean(sub ** 2))),
            "max_rad": float(np.nanmax(sub)),
            "spread_rad": float(np.nanmax(spread[mask])),
        }

    return {
        "frames": int(A.shape[0]),
        "adjacent": stat(a_mask),
        "interposed": stat(i_mask),
        "interposed_bones": [canon.names[k[2]] + "->" + canon.names[k[3]]
                             for k, mm in zip(keep, i_mask) if mm],
    }


def bind_name_map(bind):
    return {bind.rig.names[fi]: bind.canon.names[ci] for fi, ci in bind.pairs}
