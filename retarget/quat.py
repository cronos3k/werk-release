"""quat.py -- quaternion and similarity-transform maths for werk retargeting.

werk convention, pinned by every manifest that carries a rig
(spec/schemas/manifest.schema.json, conventions.quat_order):

    quaternions are [w, x, y, z]
    the coordinate frame is RIGHT handed, +Y up, -Z forward, +X right

glTF, Unreal and most DCC tools disagree with at least one of those, so every
importer converts ONCE, at its own boundary, and everything downstream of
`retarget.sources` is already in werk convention. That is a deliberate choice:
a conversion that happens in one named place can be tested, and a conversion
that happens wherever it is needed cannot.

numpy only. Arrays are float64 throughout; f32 appears exactly once, when a
clip is written to a `core.anim.clip` payload, and that quantisation is a
measured line in the Stage 6 gate rather than an assumption.
"""

import numpy as np


# --- basic quaternion algebra ----------------------------------------------

def qnorm(q):
    q = np.asarray(q, dtype=np.float64)
    n = np.linalg.norm(q, axis=-1, keepdims=True)
    n = np.where(n == 0.0, 1.0, n)
    return q / n


def qmul(a, b):
    """Hamilton product, broadcasting over leading axes. wxyz in, wxyz out."""
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    aw, ax, ay, az = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    bw, bx, by, bz = b[..., 0], b[..., 1], b[..., 2], b[..., 3]
    return np.stack([
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    ], axis=-1)


def qconj(q):
    q = np.asarray(q, dtype=np.float64)
    return np.stack([q[..., 0], -q[..., 1], -q[..., 2], -q[..., 3]], axis=-1)


def qinv(q):
    """Inverse of a UNIT quaternion (== conjugate). Normalised first, because
    a rig read off disk is only unit to the precision it was stored at."""
    return qconj(qnorm(q))


def qrot(q, v):
    """Rotate vector(s) v by unit quaternion(s) q."""
    q = np.asarray(q, dtype=np.float64)
    v = np.asarray(v, dtype=np.float64)
    w = q[..., 0:1]
    u = q[..., 1:4]
    uv = np.cross(u, v)
    return v + 2.0 * (w * uv + np.cross(u, uv))


def qangle(a, b):
    """Geodesic angle in radians between two rotations, sign-insensitive.

    Uses 2*atan2(|a-b|, |a+b|) rather than 2*acos(|dot|). The acos form loses
    all its precision exactly where a retarget test spends its time -- near
    zero error -- and Stage 11 recorded a gate that manufactured 8e-3 rad of
    fictitious error that way. This form is stable to the last bit.
    """
    a = qnorm(a)
    b = qnorm(b)
    d = np.sum(a * b, axis=-1, keepdims=True)
    b = np.where(d < 0.0, -b, b)
    n1 = np.linalg.norm(a - b, axis=-1)
    n2 = np.linalg.norm(a + b, axis=-1)
    return 2.0 * np.arctan2(n1, n2)


def qslerp(a, b, t):
    a = qnorm(a)
    b = qnorm(b)
    d = float(np.dot(a, b))
    if d < 0.0:
        b = -b
        d = -d
    if d > 0.9995:
        return qnorm(a + t * (b - a))
    th0 = np.arccos(np.clip(d, -1.0, 1.0))
    th = th0 * t
    b2 = qnorm(b - a * d)
    return a * np.cos(th) + b2 * np.sin(th)


def mat_to_quat(m):
    """3x3 rotation matrix -> wxyz. Shepperd's branch, for conditioning."""
    m = np.asarray(m, dtype=np.float64)
    tr = m[0, 0] + m[1, 1] + m[2, 2]
    if tr > 0.0:
        s = np.sqrt(tr + 1.0) * 2.0
        q = [0.25 * s, (m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s,
             (m[1, 0] - m[0, 1]) / s]
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = np.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2.0
        q = [(m[2, 1] - m[1, 2]) / s, 0.25 * s, (m[0, 1] + m[1, 0]) / s,
             (m[0, 2] + m[2, 0]) / s]
    elif m[1, 1] > m[2, 2]:
        s = np.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2.0
        q = [(m[0, 2] - m[2, 0]) / s, (m[0, 1] + m[1, 0]) / s, 0.25 * s,
             (m[1, 2] + m[2, 1]) / s]
    else:
        s = np.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2.0
        q = [(m[1, 0] - m[0, 1]) / s, (m[0, 2] + m[2, 0]) / s,
             (m[1, 2] + m[2, 1]) / s, 0.25 * s]
    return qnorm(np.array(q, dtype=np.float64))


def quat_to_mat(q):
    q = qnorm(q)
    w, x, y, z = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
    ], dtype=np.float64)


def euler_zyx_to_quat(rz, ry, rx):
    """BVH's usual channel order: the local rotation is Rz * Ry * Rx.

    Angles in radians. Written as an explicit product of three quaternions so
    the order is visible in the source instead of hidden in a trig identity --
    a wrong Euler order is the single most common silent retarget bug and it
    must be readable.
    """
    qz = np.array([np.cos(rz / 2), 0.0, 0.0, np.sin(rz / 2)])
    qy = np.array([np.cos(ry / 2), 0.0, np.sin(ry / 2), 0.0])
    qx = np.array([np.cos(rx / 2), np.sin(rx / 2), 0.0, 0.0])
    return qmul(qmul(qz, qy), qx)


def euler_to_quat(order, angles):
    """Generic intrinsic Euler product for a channel order like "ZYX".

    `order` is the order the channels appear in the file, and the local
    rotation is the product in that same left-to-right order, which is what
    the BVH format specifies.
    """
    axis_q = {
        "X": lambda a: np.array([np.cos(a / 2), np.sin(a / 2), 0.0, 0.0]),
        "Y": lambda a: np.array([np.cos(a / 2), 0.0, np.sin(a / 2), 0.0]),
        "Z": lambda a: np.array([np.cos(a / 2), 0.0, 0.0, np.sin(a / 2)]),
    }
    q = np.array([1.0, 0.0, 0.0, 0.0])
    for ax, a in zip(order, angles):
        q = qmul(q, axis_q[ax](a))
    return q


# --- similarity fit ---------------------------------------------------------

def umeyama_similarity(src, dst, weights=None):
    """Least-squares similarity (scale, rotation, translation) src -> dst.

    Returns (scale, R3x3, t3, rms) with dst ~= scale * R @ src + t.

    ROTATION ONLY, never a reflection: if the SVD lands on det < 0 the smallest
    singular direction is flipped back. A reflection would fit some point sets
    better and is *always* wrong here -- it turns a left hand into a right hand,
    and it cannot be carried by a quaternion, so a solver that silently allowed
    one would produce a bind that works on positions and mirrors every rotation.
    Handedness is converted once, in the importer, and never here.

    Umeyama 1991, "Least-squares estimation of transformation parameters
    between two point patterns", IEEE PAMI 13(4). Implemented from the paper's
    equations 34-42, not from a library, because it is thirty lines and the
    reflection clause above is the whole reason this function exists.
    """
    src = np.asarray(src, dtype=np.float64)
    dst = np.asarray(dst, dtype=np.float64)
    n = src.shape[0]
    if n < 3:
        raise ValueError("similarity fit needs at least 3 correspondences, got %d" % n)
    if weights is None:
        w = np.ones(n, dtype=np.float64)
    else:
        w = np.asarray(weights, dtype=np.float64)
    w = w / w.sum()

    mu_s = (w[:, None] * src).sum(axis=0)
    mu_d = (w[:, None] * dst).sum(axis=0)
    s0 = src - mu_s
    d0 = dst - mu_d
    var_s = float((w[:, None] * (s0 ** 2)).sum())
    cov = (w[:, None] * d0).T @ s0

    U, D, Vt = np.linalg.svd(cov)
    S = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0.0:
        S[2, 2] = -1.0
    R = U @ S @ Vt
    scale = float((D * np.diag(S)).sum() / var_s) if var_s > 0 else 1.0
    t = mu_d - scale * (R @ mu_s)

    fit = (scale * (R @ src.T).T) + t
    rms = float(np.sqrt((w * ((fit - dst) ** 2).sum(axis=1)).sum()))
    return scale, R, t, rms
