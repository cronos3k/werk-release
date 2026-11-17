"""The one axis conversion, written once, with known vectors.

werk model space (MANIFEST.json `conventions`):
    up +Y, forward -Z, right +X, right-handed, metres, quaternions **wxyz**

Blender:
    up +Z, forward -Y, right +X, right-handed, metres, quaternions **wxyz**

So the ONLY difference is the up axis, and quaternion component order — the
usual source of pain — already agrees. glTF is Y-up too, which is why Blender's
bundled glTF I/O already performs this exact swing for everything that travels
through a GLB.

WHAT CONVERTS WHERE — the whole point of this module being small and explicit:

| data                                     | converted by            |
|------------------------------------------|-------------------------|
| `core.geom.*` positions/normals/tangents | Blender's glTF I/O      |
| `core.geom.*` node transforms            | Blender's glTF I/O      |
| `core.phys.bounds` AABB + sphere centre  | **this module**         |
| `core.phys.colliders` centres/rotations  | **this module**         |
| `core.skeleton` rest translations/rots   | **this module**         |
| `core.anim.clip` root track + bone quats | **this module**         |
| manifest `parts[]` TRS                   | **this module**         |
| UVs, colours, audio, semantics           | nobody — no axes in them|

The matrix, stated so it can be checked rather than believed:

    M = werk -> blender = Rx(+90 degrees) = [[1, 0,  0],
                                             [0, 0, -1],
                                             [0, 1,  0]]

    M * (0,1,0) = (0,0,1)      werk up      -> blender up
    M * (0,0,-1) = (0,1,0)     werk forward -> blender +Y
    M * (1,0,0) = (1,0,0)      right is right

That werk's forward (-Z) lands on Blender's **+Y** and not on Blender's forward
(-Y) is not a mistake and is not fixable: Blender's glTF importer does exactly
this, so a model imported from a GLB faces away from Blender's front view. We
match the bundled importer deliberately. Doing anything else would make the
geometry (converted by glTF I/O) and the skeleton (converted here) disagree,
which is the single worst outcome available.

TWO KINDS OF ROTATION, AND THEY CONVERT DIFFERENTLY
---------------------------------------------------

This is the trap, and it cost this adapter one wrong gate run (45 degrees of
error on every posed bone — exactly the half-angle of a 90-degree swing, which
is what a conjugation applied where a single multiplication belonged looks
like). The question to ask about any quaternion is always:

    **does the frame it maps FROM change its coordinate convention too?**

* **Both frames convert -> CONJUGATE**, `q_b = q_M * q_w * q_M^-1`.
  A rotation from model space to model space. A collider box's orientation is
  this case *because the exporter also relabels the box's own axes*: its
  `half_extents` go through `vec_*` alongside the rotation, so both ends move
  together and the conjugation is the consistent choice.

* **Only the target frame converts -> LEFT-MULTIPLY ONLY**,
  `q_b = q_M * q_w`. A rotation from a frame whose axes are declared
  independently of the up axis, into model space. **Every skeleton bone's
  model-space orientation is this case**, because
  `core.skeleton.schema.json` pins `bone_axis_along: "+y"` and
  `bone_axis_back: "+z"` — Blender's own bone convention — so bone-local
  coordinates are IDENTICAL on both sides and only the model end moves.
  `model_rest_rotation`, a root bone's `rest_rotation` and an animation
  clip's root-track quaternion are all of this kind.

* **Neither frame converts -> UNCHANGED.** A non-root bone's `rest_rotation`
  and every per-bone quaternion in a `core.anim.clip` map one bone's frame to
  its parent bone's frame. Both are bone frames, both are unchanged, so the
  value is invariant. Converting these is the *other* half of the same bug:
  it looks like symmetry and is not.

  Proof, since "invariant" is a strong claim: a bone's model matrix satisfies
  `B_blender = M . B_werk` (only the model end moves). Its local matrix is
  `L = B_parent^-1 . B_child`, so
  `L_werk = (M^-1 B_pb)^-1 (M^-1 B_cb) = B_pb^-1 M M^-1 B_cb = L_blender`.
  The M cancels. That cancellation is why the last two cases differ.

`selftest()` checks every claim above numerically, including the cancellation,
and the gate runs it.
"""

import math

SQRT_HALF = math.sqrt(0.5)

#: Quaternion of M, in werk/Blender wxyz order.
Q_M = (SQRT_HALF, SQRT_HALF, 0.0, 0.0)
Q_M_INV = (SQRT_HALF, -SQRT_HALF, 0.0, 0.0)


# --- vectors ---------------------------------------------------------------

def vec_werk_to_blender(v):
    """(x, y, z) in werk model space -> Blender world space."""
    return (v[0], -v[2], v[1])


def vec_blender_to_werk(v):
    """(x, y, z) in Blender world space -> werk model space."""
    return (v[0], v[2], -v[1])


# --- quaternions (wxyz throughout, both sides) -----------------------------

def quat_mul(a, b):
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    )


def quat_conj(q):
    return (q[0], -q[1], -q[2], -q[3])


def quat_normalize(q):
    n = math.sqrt(sum(c * c for c in q))
    if n < 1e-12:
        return (1.0, 0.0, 0.0, 0.0)
    return tuple(c / n for c in q)


def quat_canonical(q):
    """ENVELOPE.layout.txt section 6: writers MUST emit the w >= 0 representative.

    q and -q are the same rotation, so this loses nothing and makes two
    encoders of the same pose produce the same bytes."""
    q = quat_normalize(q)
    return tuple(-c for c in q) if q[0] < 0.0 else q


def quat_werk_to_blender(q):
    """Rotation expressed in werk space -> the same rotation in Blender space."""
    return quat_canonical(quat_mul(quat_mul(Q_M, q), Q_M_INV))


def quat_blender_to_werk(q):
    return quat_canonical(quat_mul(quat_mul(Q_M_INV, q), Q_M))


def frame_werk_to_blender(q):
    """A rotation whose SOURCE frame does not convert: bone-local -> model.

    Left-multiplication only. Use for `core.skeleton`'s `model_rest_rotation`,
    a root bone's `rest_rotation`, and a `core.anim.clip` root-track
    quaternion. Using `quat_werk_to_blender` here is the 45-degree bug the
    module docstring describes.
    """
    return quat_canonical(quat_mul(Q_M, q))


def frame_blender_to_werk(q):
    return quat_canonical(quat_mul(Q_M_INV, q))


def quat_from_axis_angle(axis, angle):
    n = math.sqrt(sum(c * c for c in axis)) or 1.0
    s = math.sin(angle / 2.0)
    return (math.cos(angle / 2.0),
            axis[0] / n * s, axis[1] / n * s, axis[2] / n * s)


# --- self test -------------------------------------------------------------

def selftest(verbose=False):
    """Every claim in this module's docstring, as an assertion. Returns a list
    of failure strings; empty means everything held."""
    bad = []

    def near(got, want, what, tol=1e-9):
        if any(abs(g - w) > tol for g, w in zip(got, want)):
            bad.append("%s: got %r want %r" % (what, tuple(round(g, 9) for g in got),
                                               want))
        elif verbose:
            print("  OK %s -> %r" % (what, tuple(round(g, 9) for g in got)))

    # the three named vectors
    near(vec_werk_to_blender((0.0, 1.0, 0.0)), (0.0, 0.0, 1.0), "werk up -> blender up")
    near(vec_werk_to_blender((0.0, 0.0, -1.0)), (0.0, 1.0, 0.0),
         "werk forward -> blender +Y")
    near(vec_werk_to_blender((1.0, 0.0, 0.0)), (1.0, 0.0, 0.0), "right stays right")
    near(vec_blender_to_werk((0.0, 0.0, 1.0)), (0.0, 1.0, 0.0), "blender up -> werk up")

    # round trip on an asymmetric vector, so a sign error cannot cancel
    v = (0.25, -1.5, 3.75)
    near(vec_blender_to_werk(vec_werk_to_blender(v)), v, "vector round trip")

    # identity rotation is identity in both frames
    near(quat_werk_to_blender((1.0, 0.0, 0.0, 0.0)), (1.0, 0.0, 0.0, 0.0),
         "identity quaternion")

    # a yaw is a yaw: 90 degrees about werk up (+Y) must become 90 degrees
    # about Blender up (+Z). This is the assertion that catches a conjugation
    # written the wrong way round, which a round-trip test alone cannot.
    yaw_w = quat_from_axis_angle((0.0, 1.0, 0.0), math.radians(90.0))
    near(quat_werk_to_blender(yaw_w),
         quat_from_axis_angle((0.0, 0.0, 1.0), math.radians(90.0)),
         "90 deg yaw about up")

    # pitch about werk +X stays about Blender +X (the shared axis)
    pitch_w = quat_from_axis_angle((1.0, 0.0, 0.0), math.radians(30.0))
    near(quat_werk_to_blender(pitch_w),
         quat_from_axis_angle((1.0, 0.0, 0.0), math.radians(30.0)),
         "30 deg pitch about the shared X")

    # roll about werk -Z (forward) must become roll about Blender +Y
    roll_w = quat_from_axis_angle((0.0, 0.0, -1.0), math.radians(45.0))
    near(quat_werk_to_blender(roll_w),
         quat_from_axis_angle((0.0, 1.0, 0.0), math.radians(45.0)),
         "45 deg roll about forward")

    # quaternion round trip on a rotation with no symmetry to hide behind
    q = quat_canonical(quat_mul(yaw_w, pitch_w))
    near(quat_blender_to_werk(quat_werk_to_blender(q)), q, "quaternion round trip")

    # the conversion must AGREE with rotating vectors: converting a rotation
    # and then a vector must equal rotating then converting. This is the
    # property that makes the skeleton and the glTF geometry line up.
    def rotate(q, v):
        qv = (0.0, v[0], v[1], v[2])
        r = quat_mul(quat_mul(q, qv), quat_conj(q))
        return (r[1], r[2], r[3])

    for name, qq in (("yaw", yaw_w), ("pitch", pitch_w), ("compound", q)):
        lhs = vec_werk_to_blender(rotate(qq, v))
        rhs = rotate(quat_werk_to_blender(qq), vec_werk_to_blender(v))
        near(lhs, rhs, "rotate-then-convert == convert-then-rotate (%s)" % name, 1e-9)

    # canonical sign
    neg = tuple(-c for c in q)
    near(quat_canonical(neg), q, "canonical w >= 0 representative")

    # --- the frame case, which is NOT a conjugation --------------------
    # A bone pointing straight up in werk (its local +Y along werk +Y) has an
    # identity model_rest_rotation. In Blender the same bone points along +Z,
    # so its model rotation must take (0,1,0) to (0,0,1) — which is q_M, not
    # the identity that a conjugation would produce.
    near(frame_werk_to_blender((1.0, 0.0, 0.0, 0.0)), Q_M,
         "identity bone frame -> q_M (left-multiply, not conjugate)")
    near(rotate(frame_werk_to_blender((1.0, 0.0, 0.0, 0.0)), (0.0, 1.0, 0.0)),
         (0.0, 0.0, 1.0), "an up-pointing bone points along Blender +Z")

    # frame round trip
    fq = quat_canonical(quat_mul(yaw_w, roll_w))
    near(frame_blender_to_werk(frame_werk_to_blender(fq)), fq,
         "frame round trip")

    # A frame rotation must move its OWN axes the way vec_* moves them: the
    # bone's local +Y is a model-space direction on both sides.
    for name, qq in (("yaw", yaw_w), ("pitch", pitch_w), ("compound", fq)):
        for local_axis in ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)):
            lhs = vec_werk_to_blender(rotate(qq, local_axis))
            rhs = rotate(frame_werk_to_blender(qq), local_axis)
            near(lhs, rhs, "frame axis agrees with vec_ (%s, %r)" % (name, local_axis))

    # THE CANCELLATION: a local (bone -> parent bone) rotation is invariant.
    # Built from two model-space frames, so a sign error anywhere shows up.
    b_parent = frame_werk_to_blender(yaw_w)
    b_child = frame_werk_to_blender(quat_canonical(quat_mul(yaw_w, pitch_w)))
    local_from_blender = quat_canonical(quat_mul(quat_conj(b_parent), b_child))
    local_from_werk = quat_canonical(
        quat_mul(quat_conj(yaw_w), quat_canonical(quat_mul(yaw_w, pitch_w))))
    near(local_from_blender, local_from_werk,
         "local bone rotation is INVARIANT under the swing")
    near(local_from_werk, quat_canonical(pitch_w),
         "and equals the local rotation it was built from")

    return bad


if __name__ == "__main__":
    import sys

    failures = selftest(verbose=True)
    for f in failures:
        print("FAIL " + f)
    print("axes selftest: %s" % ("OK" if not failures else "FAILED"))
    sys.exit(1 if failures else 0)
