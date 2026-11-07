"""skeleton.py -- the rig model and the FK evaluator.

One class, `Rig`, serves both the canonical humanoid and every foreign rig, so
the retargeter has exactly one thing to reason about. A foreign importer's only
job is to fill a `Rig` in werk convention; everything after that is shared code
and is tested once.

Composition, quoted from spec/skeleton/canonical-humanoid-v1.json:

    M_bone = M_parent * T(rest_translation) * R(rest_rotation)

so the local matrix is T then R: the head offset is expressed in the PARENT's
frame, and the bone's own rotation does not move its own head. Written out:

    model_rot(b)  = model_rot(parent)  * local_rot(b)
    model_head(b) = model_head(parent) + model_rot(parent) * local_trans(b)

An animated pose replaces `rest_rotation` with the clip's local rotation and
leaves `rest_translation` alone -- bone lengths belong to the rig, never to a
clip (animclip.layout.txt, D-AC-4).
"""

import json

import numpy as np

from .quat import qmul, qnorm, qrot

IDENT = np.array([1.0, 0.0, 0.0, 0.0])


class Rig:
    """A bone hierarchy in werk convention (Y up, -Z forward, right handed).

    Bones are stored in topological order: a bone's parent always has a lower
    index, which is what lets FK be a single forward loop with no recursion and
    no visited set. `add` enforces it rather than assuming it.
    """

    def __init__(self, rig_id, source=None, unit_scale_m=1.0):
        self.rig_id = rig_id
        self.source = source or {}
        self.unit_scale_m = float(unit_scale_m)
        self.names = []
        self.index = {}
        self.parent = []          # index of parent, -1 for a root
        self.local_t = []         # (3,) rest translation, parent frame
        self.local_q = []         # (4,) rest rotation, wxyz, parent frame
        self._cache = None

    # -- construction --------------------------------------------------------

    def add(self, name, parent, local_t, local_q):
        if name in self.index:
            raise ValueError("duplicate bone id %r in rig %r" % (name, self.rig_id))
        if parent is None:
            pi = -1
        else:
            if parent not in self.index:
                raise ValueError(
                    "bone %r names parent %r, which has not been added yet. "
                    "Rig bones must arrive in topological order." % (name, parent))
            pi = self.index[parent]
        self.index[name] = len(self.names)
        self.names.append(name)
        self.parent.append(pi)
        self.local_t.append(np.asarray(local_t, dtype=np.float64).reshape(3))
        self.local_q.append(qnorm(np.asarray(local_q, dtype=np.float64).reshape(4)))
        self._cache = None
        return self

    def finish(self):
        self.parent = np.asarray(self.parent, dtype=np.int64)
        self.local_t = np.asarray(self.local_t, dtype=np.float64)
        self.local_q = np.asarray(self.local_q, dtype=np.float64)
        return self

    @property
    def n(self):
        return len(self.names)

    def roots(self):
        return [i for i in range(self.n) if self.parent[i] < 0]

    # -- forward kinematics --------------------------------------------------

    def fk(self, local_q=None, root_offset=None, local_t=None):
        """Model-space (rotation, head) for every bone.

        local_q: (n,4) local rotations replacing the rest rotations. None means
                 the rest pose.
        local_t: (n,3) local translations replacing the rest translations. None
                 means the rig's own. Foreign source rigs really do animate bone
                 translation (Unreal keys the pelvis that way as a matter of
                 course), and evaluating the SOURCE pose wrongly would poison
                 the calibration before the retargeter ever ran. Core clips
                 still cannot carry it -- see D-AC-4 and finding S6-4 -- but
                 that is a statement about the output, not a licence to
                 misread the input.
        root_offset: (3,) added to every root bone's head, in model units.

        Returns (Q, P) with Q (n,4) and P (n,3).
        """
        n = self.n
        lq = self.local_q if local_q is None else qnorm(np.asarray(local_q, dtype=np.float64))
        lt = self.local_t if local_t is None else np.asarray(local_t, dtype=np.float64)
        if lq.shape != (n, 4):
            raise ValueError("local_q must be (%d,4), got %s" % (n, lq.shape))
        if lt.shape != (n, 3):
            raise ValueError("local_t must be (%d,3), got %s" % (n, lt.shape))
        Q = np.empty((n, 4), dtype=np.float64)
        P = np.empty((n, 3), dtype=np.float64)
        off = np.zeros(3) if root_offset is None else np.asarray(root_offset, dtype=np.float64)
        for i in range(n):
            p = int(self.parent[i])
            if p < 0:
                Q[i] = lq[i]
                P[i] = lt[i] + off
            else:
                Q[i] = qmul(Q[p], lq[i])
                P[i] = P[p] + qrot(Q[p], lt[i])
        return Q, P

    def rest_fk(self):
        if self._cache is None:
            self._cache = self.fk()
        return self._cache

    def localise(self, Q_model):
        """Model-space rotations -> parent-local rotations. Exact inverse of the
        rotation half of `fk`, which is what makes the round-trip gate clause a
        measurement of the format and not of this function."""
        n = self.n
        lq = np.empty((n, 4), dtype=np.float64)
        for i in range(n):
            p = int(self.parent[i])
            if p < 0:
                lq[i] = Q_model[i]
            else:
                inv = np.array([Q_model[p][0], -Q_model[p][1], -Q_model[p][2], -Q_model[p][3]])
                lq[i] = qmul(inv, Q_model[i])
        return qnorm(lq)

    def descendants_of(self, name):
        i0 = self.index[name]
        out = [i0]
        for i in range(i0 + 1, self.n):
            if int(self.parent[i]) in out:
                out.append(i)
        return out

    # -- canonical loader ----------------------------------------------------

    @classmethod
    def from_canonical(cls, path):
        """Load spec/skeleton/canonical-humanoid-v1.json.

        The file declares BOTH local and model-space rest values (Stage 1
        decision 8: redundant on purpose so the local numbers are checkable).
        This loader reads the LOCAL numbers and VERIFIES the model ones, so a
        drifted canon is a raised error and not a silently different rig.
        """
        with open(path, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
        conv = doc["conventions"]
        for key, want in (("up_axis", "y"), ("forward_axis", "-z"),
                          ("right_axis", "+x"), ("handedness", "right"),
                          ("quat_order", "wxyz"), ("bone_axis_along", "+y")):
            if conv.get(key) != want:
                raise ValueError("canonical skeleton convention %s is %r, this code "
                                 "is written for %r" % (key, conv.get(key), want))
        rig = cls(doc["skeleton_id"],
                  source={"path": path, "status": doc.get("status"),
                          "reference_height_m": doc.get("reference_height_m"),
                          "pose_name": doc.get("pose_name")},
                  unit_scale_m=1.0)
        for b in doc["bones"]:
            rig.add(b["bone_id"], b["parent"], b["rest_translation"], b["rest_rotation"])
        rig.finish()

        Q, P = rig.rest_fk()
        worst_p = 0.0
        worst_q = 0.0
        for i, b in enumerate(doc["bones"]):
            worst_p = max(worst_p, float(np.abs(P[i] - np.array(b["model_rest_head_m"])).max()))
            dq = np.abs(np.abs(np.dot(Q[i], np.array(b["model_rest_rotation"]))) - 1.0)
            worst_q = max(worst_q, float(dq))
        rig.source["recompose_residual_position_m"] = worst_p
        rig.source["recompose_residual_rotation"] = worst_q
        if worst_p > 1e-5 or worst_q > 1e-5:
            raise ValueError(
                "canonical skeleton fails its own recomposition check "
                "(pos %.3e m, rot %.3e); the schema tells readers to verify "
                "within 1e-5 and this file does not" % (worst_p, worst_q))
        rig.canonical_doc = doc
        rig.bone_length = np.array([b["length_m"] for b in doc["bones"]])
        rig.reference_height_m = float(doc["reference_height_m"])
        return rig


class Clip:
    """A uniformly sampled clip on one rig: local rotations per bone per frame,
    plus a root translation track. Exactly the shape core.anim.clip stores."""

    def __init__(self, clip_id, rig, rate_hz, local_q, root_t, root_bone=None,
                 source=None, bone_t=None):
        self.clip_id = clip_id
        self.rig = rig
        self.rate_hz = float(rate_hz)
        self.local_q = qnorm(np.asarray(local_q, dtype=np.float64))   # (F, n, 4)
        self.root_t = np.asarray(root_t, dtype=np.float64)            # (F, 3)
        self.root_bone = root_bone if root_bone is not None else rig.names[rig.roots()[0]]
        self.source = source or {}
        # (F,n,3) per-bone local translation, or None for "the rig's rest".
        # Present only on SOURCE clips read from foreign formats.
        self.bone_t = None if bone_t is None else np.asarray(bone_t, dtype=np.float64)
        if self.local_q.shape[1:] != (rig.n, 4):
            raise ValueError("clip %r: local_q must be (F,%d,4), got %s"
                             % (clip_id, rig.n, self.local_q.shape))
        if self.root_t.shape != (self.frames, 3):
            raise ValueError("clip %r: root_t must be (%d,3), got %s"
                             % (clip_id, self.frames, self.root_t.shape))

    @property
    def frames(self):
        return int(self.local_q.shape[0])

    @property
    def duration_s(self):
        return self.frames / self.rate_hz

    def fk_frame(self, f):
        if self.bone_t is None:
            return self.rig.fk(self.local_q[f], root_offset=self.root_t[f])
        # bone_t already carries the root bone's own animated translation, so
        # adding root_t on top would count the root's motion twice.
        return self.rig.fk(self.local_q[f], local_t=self.bone_t[f])

    def fk_all(self):
        """(F,n,4) model rotations and (F,n,3) model heads."""
        F = self.frames
        Q = np.empty((F, self.rig.n, 4))
        P = np.empty((F, self.rig.n, 3))
        for f in range(F):
            Q[f], P[f] = self.fk_frame(f)
        return Q, P
