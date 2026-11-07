#!/usr/bin/env python3
"""meshops.py — the geometry arithmetic several producers share.

Welding, normals, tangents, quadric-error decimation, Welzl's exact minimal
enclosing sphere, the divergence-theorem mass integrals, an exact
point-to-triangle distance field, and convex hulls.

Everything here is deterministic and dependency-light: numpy always, scipy
only for `ConvexHull` and `distance_transform_edt`, and every caller of those
two has a declared fallback so an install without scipy degrades a stage
instead of killing the run.
"""

import math

import numpy as np

try:
    from scipy.spatial import ConvexHull            # noqa: F401
    HAVE_SCIPY = True
except Exception:                                    # pragma: no cover
    HAVE_SCIPY = False


# ---------------------------------------------------------------------------
# welding and normals
# ---------------------------------------------------------------------------

def weld(pos, idx, extra=(), decimals=6):
    """Merge vertices that share a position to `decimals` places.

    Real GLBs carry one vertex per corner far more often than they carry one
    vertex per point, and every topological operation below (edge collapse,
    boundary detection, watertightness) is meaningless on a mesh whose
    triangles do not share vertices.
    """
    key = np.round(np.asarray(pos, dtype=np.float64), decimals)
    _u, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inv = inv.reshape(-1)
    order = np.argsort(first)
    remap = np.empty(len(first), dtype=np.int64)
    remap[order] = np.arange(len(first))
    new_idx = remap[inv][np.asarray(idx, dtype=np.int64)]
    keep = first[order]
    out_extra = [None if e is None else np.asarray(e)[keep] for e in extra]
    # drop degenerate triangles created by the merge
    good = ((new_idx[:, 0] != new_idx[:, 1]) & (new_idx[:, 1] != new_idx[:, 2]) &
            (new_idx[:, 0] != new_idx[:, 2]))
    return np.asarray(pos)[keep], new_idx[good], out_extra, good


def face_normals(pos, idx):
    a = pos[idx[:, 0]]
    e1 = pos[idx[:, 1]] - a
    e2 = pos[idx[:, 2]] - a
    n = np.cross(e1, e2)
    return n


def vertex_normals(pos, idx):
    """Area-weighted, which is the accumulation glTF viewers agree on."""
    n = np.zeros_like(pos)
    fn = face_normals(pos, idx)
    for k in range(3):
        np.add.at(n, idx[:, k], fn)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1.0
    return n / ln


# ---------------------------------------------------------------------------
# tangents
# ---------------------------------------------------------------------------

def tangents(pos, nrm, uv, idx):
    """A per-vertex tangent basis in the glTF VEC4 (xyz, w=sign) convention.

    THIS IS NOT MikkTSpace and the node that carries it says so. MikkTSpace
    splits vertices where the basis is discontinuous and weights by the
    triangle's angle at the vertex after an exact area normalisation; this is
    the ordinary accumulate-then-Gram-Schmidt basis, which agrees with
    MikkTSpace wherever the UV chart is continuous and diverges at chart
    seams. Filed as S3-4. Emitting it labelled honestly is better than
    emitting nothing, because glTF's own fallback ("compute with MikkTSpace")
    is a dependency the consumer has to find.
    """
    tan = np.zeros((len(pos), 3), dtype=np.float64)
    bit = np.zeros((len(pos), 3), dtype=np.float64)
    p0, p1, p2 = pos[idx[:, 0]], pos[idx[:, 1]], pos[idx[:, 2]]
    w0, w1, w2 = uv[idx[:, 0]], uv[idx[:, 1]], uv[idx[:, 2]]
    e1, e2 = p1 - p0, p2 - p0
    du1, du2 = w1 - w0, w2 - w0
    det = du1[:, 0] * du2[:, 1] - du2[:, 0] * du1[:, 1]
    ok = np.abs(det) > 1e-20
    r = np.zeros_like(det)
    r[ok] = 1.0 / det[ok]
    t = (e1 * du2[:, 1:2] - e2 * du1[:, 1:2]) * r[:, None]
    b = (e2 * du1[:, 0:1] - e1 * du2[:, 0:1]) * r[:, None]
    t[~ok] = 0.0
    b[~ok] = 0.0
    for k in range(3):
        np.add.at(tan, idx[:, k], t)
        np.add.at(bit, idx[:, k], b)
    # Gram-Schmidt against the normal
    d = np.sum(tan * nrm, axis=1, keepdims=True)
    t = tan - nrm * d
    ln = np.linalg.norm(t, axis=1, keepdims=True)
    bad = (ln[:, 0] < 1e-12)
    if bad.any():
        # degenerate chart: any vector orthogonal to the normal will do, and a
        # declared arbitrary basis beats a NaN.
        alt = np.tile(np.array([1.0, 0.0, 0.0]), (bad.sum(), 1))
        flip = np.abs(nrm[bad, 0]) > 0.9
        alt[flip] = np.array([0.0, 0.0, 1.0])
        alt = alt - nrm[bad] * np.sum(alt * nrm[bad], axis=1, keepdims=True)
        t[bad] = alt
        ln[bad] = np.linalg.norm(alt, axis=1, keepdims=True)
    t = t / np.maximum(ln, 1e-30)
    sign = np.where(np.sum(np.cross(nrm, t) * bit, axis=1) < 0.0, -1.0, 1.0)
    return np.hstack([t, sign[:, None]]), int(bad.sum())


# ---------------------------------------------------------------------------
# quadric-error decimation
# ---------------------------------------------------------------------------

def decimate(pos, idx, target_tris, protect_boundary=True):
    """Garland-Heckbert quadric error metric, half-edge collapse to a vertex
    of the pair (never to the optimal point).

    Collapsing to one of the two endpoints rather than to the quadric's
    minimiser keeps every LOD vertex ON the original surface, which is what
    makes the measured Hausdorff distance an upper bound a consumer can trust
    and stops thin features from being pulled into space. It costs a little
    error at equal triangle count and buys a property worth more than that.
    """
    pos = np.array(pos, dtype=np.float64)
    idx = np.array(idx, dtype=np.int64)
    nv = len(pos)

    Q = np.zeros((nv, 4, 4), dtype=np.float64)
    fn = face_normals(pos, idx)
    ln = np.linalg.norm(fn, axis=1, keepdims=True)
    area = ln[:, 0] * 0.5
    unit = fn / np.maximum(ln, 1e-30)
    d = -np.sum(unit * pos[idx[:, 0]], axis=1)
    planes = np.hstack([unit, d[:, None]])
    for k in range(3):
        outer = planes[:, :, None] * planes[:, None, :] * area[:, None, None]
        np.add.at(Q, idx[:, k], outer)

    alive_v = np.ones(nv, dtype=bool)
    alive_f = np.ones(len(idx), dtype=bool)
    faces_of = [[] for _ in range(nv)]
    for fi, tri in enumerate(idx):
        for v in tri:
            faces_of[v].append(fi)

    # edge set, and which faces each edge borders (for boundary protection)
    from collections import defaultdict
    edge_faces = defaultdict(list)
    for fi, tri in enumerate(idx):
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            edge_faces[(min(a, b), max(a, b))].append(fi)
    boundary_v = np.zeros(nv, dtype=bool)
    for (a, b), fl in edge_faces.items():
        if len(fl) == 1:
            boundary_v[a] = True
            boundary_v[b] = True

    def cost(v_from, v_to):
        q = Q[v_from] + Q[v_to]
        p = np.array([pos[v_to, 0], pos[v_to, 1], pos[v_to, 2], 1.0])
        return float(p @ q @ p)

    import heapq
    heap = []
    for (a, b) in edge_faces:
        ca, cb = cost(a, b), cost(b, a)
        if ca <= cb:
            heapq.heappush(heap, (ca, int(a), int(b)))
        else:
            heapq.heappush(heap, (cb, int(b), int(a)))

    parent = np.arange(nv)

    def find(v):
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v

    live_tris = int(alive_f.sum())
    collapses = 0
    max_err = 0.0
    while live_tris > target_tris and heap:
        c, a, b = heapq.heappop(heap)
        a, b = find(a), find(b)
        if a == b or not alive_v[a] or not alive_v[b]:
            continue
        if protect_boundary and boundary_v[a] and not boundary_v[b]:
            continue
        cur = cost(a, b)
        if cur > c + 1e-12:
            heapq.heappush(heap, (cur, a, b))
            continue
        # collapse a into b
        removed = 0
        touched = set(faces_of[a])
        for fi in touched:
            if not alive_f[fi]:
                continue
            tri = idx[fi]
            t = [find(v) for v in tri]
            t = [b if v == a else v for v in t]
            if t[0] == t[1] or t[1] == t[2] or t[0] == t[2]:
                alive_f[fi] = False
                removed += 1
            else:
                idx[fi] = t
                faces_of[b].append(fi)
        alive_v[a] = False
        parent[a] = b
        Q[b] = Q[a] + Q[b]
        boundary_v[b] = boundary_v[b] or boundary_v[a]
        live_tris -= removed
        collapses += 1
        max_err = max(max_err, cur)
        # re-push the neighbourhood of b
        for fi in faces_of[b]:
            if not alive_f[fi]:
                continue
            tri = [find(v) for v in idx[fi]]
            for x, y in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
                if x == y:
                    continue
                cx, cy = cost(x, y), cost(y, x)
                if cx <= cy:
                    heapq.heappush(heap, (cx, int(x), int(y)))
                else:
                    heapq.heappush(heap, (cy, int(y), int(x)))

    tri = np.array([[find(v) for v in t] for t in idx[alive_f]], dtype=np.int64)
    used = np.unique(tri)
    remap = np.full(nv, -1, dtype=np.int64)
    remap[used] = np.arange(len(used))
    return pos[used], remap[tri], {"collapses": collapses,
                                   "max_quadric_error": max_err}


# ---------------------------------------------------------------------------
# Welzl's exact minimal enclosing sphere
# ---------------------------------------------------------------------------

def _sphere_from(pts):
    if not pts:
        return ((0.0, 0.0, 0.0), 0.0)
    if len(pts) == 1:
        return (tuple(pts[0]), 0.0)
    if len(pts) == 2:
        a, b = np.array(pts[0]), np.array(pts[1])
        c = (a + b) / 2.0
        return (tuple(c), float(np.linalg.norm(a - c)))
    if len(pts) == 3:
        a, b, c = [np.array(p) for p in pts]
        ab, ac = b - a, c - a
        n = np.cross(ab, ac)
        d = 2.0 * float(n @ n)
        if abs(d) < 1e-30:
            best = ((0, 0, 0), 0.0)
            for pair in ((a, b), (a, c), (b, c)):
                s = _sphere_from([tuple(pair[0]), tuple(pair[1])])
                if s[1] > best[1]:
                    best = s
            return best
        centre = a + (np.cross(n, ab) * float(ac @ ac) +
                      np.cross(ac, n) * float(ab @ ab)) / d
        return (tuple(centre), float(np.linalg.norm(a - centre)))
    a, b, c, d = [np.array(p) for p in pts[:4]]
    A = np.vstack([b - a, c - a, d - a]) * 2.0
    rhs = np.array([float(b @ b - a @ a), float(c @ c - a @ a), float(d @ d - a @ a)])
    try:
        centre = np.linalg.solve(A, rhs)
    except np.linalg.LinAlgError:
        best = ((0, 0, 0), 0.0)
        for tri in ((a, b, c), (a, b, d), (a, c, d), (b, c, d)):
            s = _sphere_from([tuple(x) for x in tri])
            if s[1] > best[1]:
                best = s
        return best
    return (tuple(centre), float(np.linalg.norm(a - centre)))


def welzl(points):
    """Exact minimal enclosing sphere, iterative Welzl with a random shuffle
    seeded from a constant so two runs agree."""
    pts = [tuple(map(float, p)) for p in points]
    rng = np.random.RandomState(0x5745524B & 0x7FFFFFFF)
    rng.shuffle(pts)
    centre, radius = _sphere_from(pts[:1])
    eps = 1e-12
    for i in range(len(pts)):
        if np.linalg.norm(np.array(pts[i]) - centre) <= radius + eps:
            continue
        centre, radius = _sphere_from([pts[i]])
        for j in range(i):
            if np.linalg.norm(np.array(pts[j]) - centre) <= radius + eps:
                continue
            centre, radius = _sphere_from([pts[i], pts[j]])
            for k in range(j):
                if np.linalg.norm(np.array(pts[k]) - centre) <= radius + eps:
                    continue
                centre, radius = _sphere_from([pts[i], pts[j], pts[k]])
                for l in range(k):
                    if np.linalg.norm(np.array(pts[l]) - centre) <= radius + eps:
                        continue
                    centre, radius = _sphere_from([pts[i], pts[j], pts[k], pts[l]])
    return tuple(float(x) for x in centre), float(radius)


# ---------------------------------------------------------------------------
# mass properties by the divergence theorem
# ---------------------------------------------------------------------------

def mass_properties(pos, idx):
    """Volume, centroid and the inertia integrals of a closed triangle mesh.

    Signed tetrahedron sum against the origin — exact for a closed, correctly
    wound surface, and its sign tells you when the winding is inverted. The
    six returned products are the POSITIVE integrals (ixy = integral of x*y
    dV), which is the convention core.phys.body.schema.json declares and
    negates on assembly.
    """
    a = pos[idx[:, 0]]
    b = pos[idx[:, 1]]
    c = pos[idx[:, 2]]
    cross = np.cross(b - a, c - a)
    vol6 = np.sum(a * cross, axis=1)                # 6 * signed tet volume
    volume = float(vol6.sum()) / 6.0

    # first moments
    centroid_num = np.sum(vol6[:, None] * (a + b + c) / 4.0, axis=0) / 6.0
    centroid = centroid_num / volume if abs(volume) > 1e-30 else np.zeros(3)

    # second moments about the origin, per Mirtich's tetrahedron formulae
    def sq(u, v, w):
        return u * u + u * v + v * v + w * (u + v + w)

    ixx = iyy = izz = ixy = ixz = iyz = 0.0
    for k in range(3):
        pass
    ax, ay, az = a[:, 0], a[:, 1], a[:, 2]
    bx, by, bz = b[:, 0], b[:, 1], b[:, 2]
    cx, cy, cz = c[:, 0], c[:, 1], c[:, 2]
    d = vol6 / 6.0                                   # signed tet volume

    def second(p, q):
        return np.sum(d * (
            (p[0] * q[0] + p[1] * q[1] + p[2] * q[2]) / 10.0 +
            (p[0] * (q[1] + q[2]) + p[1] * (q[0] + q[2]) + p[2] * (q[0] + q[1])) / 20.0))

    P = (ax, bx, cx)
    Qy = (ay, by, cy)
    Rz = (az, bz, cz)
    Ixx = second(P, P)
    Iyy = second(Qy, Qy)
    Izz = second(Rz, Rz)
    Ixy = second(P, Qy)
    Ixz = second(P, Rz)
    Iyz = second(Qy, Rz)
    return {"volume": volume, "centroid": centroid,
            "second_moments_origin": (Ixx, Iyy, Izz, Ixy, Ixz, Iyz)}


def inertia_about(second_origin, volume, centroid, density):
    """Turn origin-frame second moments into the mass inertia tensor about
    the centre of mass, still in model axes."""
    Ixx, Iyy, Izz, Ixy, Ixz, Iyz = second_origin
    m = density * volume
    cx, cy, cz = centroid
    # products of inertia (POSITIVE integrals), mass-weighted, shifted
    pxy = density * Ixy - m * cx * cy
    pxz = density * Ixz - m * cx * cz
    pyz = density * Iyz - m * cy * cz
    mxx = density * Ixx - m * cx * cx
    myy = density * Iyy - m * cy * cy
    mzz = density * Izz - m * cz * cz
    ixx = myy + mzz
    iyy = mxx + mzz
    izz = mxx + myy
    return m, (ixx, iyy, izz, pxy, pxz, pyz)


def principal(components):
    ixx, iyy, izz, ixy, ixz, iyz = components
    M = np.array([[ixx, -ixy, -ixz], [-ixy, iyy, -iyz], [-ixz, -iyz, izz]])
    w, V = np.linalg.eigh(M)
    if np.linalg.det(V) < 0:
        V[:, 0] = -V[:, 0]
    return w, quat_from_matrix(V)


def quat_from_matrix(R):
    t = R[0, 0] + R[1, 1] + R[2, 2]
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        w = 0.25 * s
        x = (R[2, 1] - R[1, 2]) / s
        y = (R[0, 2] - R[2, 0]) / s
        z = (R[1, 0] - R[0, 1]) / s
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = math.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
        w = (R[2, 1] - R[1, 2]) / s
        x = 0.25 * s
        y = (R[0, 1] + R[1, 0]) / s
        z = (R[0, 2] + R[2, 0]) / s
    elif R[1, 1] > R[2, 2]:
        s = math.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
        w = (R[0, 2] - R[2, 0]) / s
        x = (R[0, 1] + R[1, 0]) / s
        y = 0.25 * s
        z = (R[1, 2] + R[2, 1]) / s
    else:
        s = math.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
        w = (R[1, 0] - R[0, 1]) / s
        x = (R[0, 2] + R[2, 0]) / s
        y = (R[1, 2] + R[2, 1]) / s
        z = 0.25 * s
    q = np.array([w, x, y, z], dtype=np.float64)
    q /= np.linalg.norm(q)
    if q[0] < 0:
        q = -q                       # ENVELOPE.layout.txt section 6: w >= 0
    return q


# ---------------------------------------------------------------------------
# distance field
# ---------------------------------------------------------------------------

def point_triangle_distance2(P, a, b, c):
    """Squared distance from each point in P (n,3) to ONE triangle. Exact —
    the full seven-region Ericson test, not a plane projection."""
    ab = b - a
    ac = c - a
    ap = P - a
    d1 = ap @ ab
    d2 = ap @ ac
    bp = P - b
    d3 = bp @ ab
    d4 = bp @ ac
    cp = P - c
    d5 = cp @ ab
    d6 = cp @ ac
    va = d3 * d6 - d5 * d4
    vb = d5 * d2 - d1 * d6
    vc = d1 * d4 - d3 * d2
    denom = va + vb + vc

    Q = np.empty_like(P)
    done = np.zeros(len(P), dtype=bool)

    m = (d1 <= 0) & (d2 <= 0)
    Q[m] = a; done |= m
    m = (~done) & (d3 >= 0) & (d4 <= d3)
    Q[m] = b; done |= m
    m = (~done) & (d6 >= 0) & (d5 <= d6)
    Q[m] = c; done |= m
    m = (~done) & (vc <= 0) & (d1 >= 0) & (d3 <= 0)
    if m.any():
        t = (d1[m] / (d1[m] - d3[m]))[:, None]
        Q[m] = a + t * ab
    done |= m
    m = (~done) & (vb <= 0) & (d2 >= 0) & (d6 <= 0)
    if m.any():
        t = (d2[m] / (d2[m] - d6[m]))[:, None]
        Q[m] = a + t * ac
    done |= m
    m = (~done) & (va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0)
    if m.any():
        t = ((d4[m] - d3[m]) / ((d4[m] - d3[m]) + (d5[m] - d6[m])))[:, None]
        Q[m] = b + t * (c - b)
    done |= m
    m = ~done
    if m.any():
        dd = np.where(np.abs(denom[m]) < 1e-30, 1.0, denom[m])
        v = (vb[m] / dd)[:, None]
        w = (vc[m] / dd)[:, None]
        Q[m] = a + ab * v + ac * w
    diff = P - Q
    return np.sum(diff * diff, axis=1)


def hausdorff_to_mesh(points, pos, idx, chunk=64):
    """Max/mean distance from `points` to the surface of (pos, idx).

    One-sided; the caller takes the max of both directions when it needs the
    symmetric figure. Brute force over triangles, chunked so a 300k-triangle
    mesh does not need a 300k x n array.
    """
    P = np.asarray(points, dtype=np.float64)
    best = np.full(len(P), np.inf)
    a = pos[idx[:, 0]]
    b = pos[idx[:, 1]]
    c = pos[idx[:, 2]]
    # coarse rejection with the triangle's bounding sphere
    cen = (a + b + c) / 3.0
    rad = np.max(np.stack([np.linalg.norm(a - cen, axis=1),
                           np.linalg.norm(b - cen, axis=1),
                           np.linalg.norm(c - cen, axis=1)]), axis=0)
    for t in range(len(idx)):
        d_cen = np.linalg.norm(P - cen[t], axis=1)
        cand = (d_cen - rad[t]) ** 2 < best
        if not cand.any():
            continue
        d2 = point_triangle_distance2(P[cand], a[t], b[t], c[t])
        cur = best[cand]
        best[cand] = np.minimum(cur, d2)
    return np.sqrt(best)


def sdf_grid(pos, idx, origin, cell, dims):
    """Signed distance on a regular grid: exact unsigned distance, sign by
    even-odd ray parity along +X.

    Ray parity rather than normal-lookup because real assets are not reliably
    wound, and a sign that flips per triangle produces a field that is worse
    than none. Parity is wrong only for a non-watertight mesh, and the caller
    reports watertightness alongside.
    """
    nx, ny, nz = dims
    gx = origin[0] + cell * np.arange(nx)
    gy = origin[1] + cell * np.arange(ny)
    gz = origin[2] + cell * np.arange(nz)
    Z, Y, X = np.meshgrid(gz, gy, gx, indexing="ij")
    P = np.stack([X.ravel(), Y.ravel(), Z.ravel()], axis=1)

    dist = hausdorff_to_mesh(P, pos, idx)

    # even-odd along +X, in the YZ plane of each grid point
    a, b, c = pos[idx[:, 0]], pos[idx[:, 1]], pos[idx[:, 2]]
    inside = np.zeros(len(P), dtype=np.int64)
    for t in range(len(idx)):
        ta, tb, tc = a[t], b[t], c[t]
        ymin = min(ta[1], tb[1], tc[1]); ymax = max(ta[1], tb[1], tc[1])
        zmin = min(ta[2], tb[2], tc[2]); zmax = max(ta[2], tb[2], tc[2])
        m = ((P[:, 1] >= ymin) & (P[:, 1] <= ymax) &
             (P[:, 2] >= zmin) & (P[:, 2] <= zmax))
        if not m.any():
            continue
        Q = P[m]
        # barycentric in the YZ projection
        d = ((tb[1] - ta[1]) * (tc[2] - ta[2]) - (tc[1] - ta[1]) * (tb[2] - ta[2]))
        if abs(d) < 1e-30:
            continue
        w1 = ((Q[:, 1] - ta[1]) * (tc[2] - ta[2]) -
              (tc[1] - ta[1]) * (Q[:, 2] - ta[2])) / d
        w2 = ((tb[1] - ta[1]) * (Q[:, 2] - ta[2]) -
              (Q[:, 1] - ta[1]) * (tb[2] - ta[2])) / d
        w0 = 1.0 - w1 - w2
        hit = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not hit.any():
            continue
        xh = w0[hit] * ta[0] + w1[hit] * tb[0] + w2[hit] * tc[0]
        fwd = xh > Q[hit, 0]
        sel = np.nonzero(m)[0][np.nonzero(hit)[0][fwd]]
        np.add.at(inside, sel, 1)
    sign = np.where(inside % 2 == 1, -1.0, 1.0)
    return (dist * sign).reshape(nz, ny, nx)


def voxelize(pos, idx, origin, cell, dims):
    """Solid voxelization by even-odd ray parity along +X. Returns a bool
    array of shape (nz, ny, nx), True inside."""
    nx, ny, nz = dims
    gx = origin[0] + cell * np.arange(nx)
    gy = origin[1] + cell * np.arange(ny)
    gz = origin[2] + cell * np.arange(nz)
    Z, Y, X = np.meshgrid(gz, gy, gx, indexing="ij")
    P = np.stack([X.ravel(), Y.ravel(), Z.ravel()], axis=1)
    a, b, c = pos[idx[:, 0]], pos[idx[:, 1]], pos[idx[:, 2]]
    inside = np.zeros(len(P), dtype=np.int64)
    for t in range(len(idx)):
        ta, tb, tc = a[t], b[t], c[t]
        m = ((P[:, 1] >= min(ta[1], tb[1], tc[1])) &
             (P[:, 1] <= max(ta[1], tb[1], tc[1])) &
             (P[:, 2] >= min(ta[2], tb[2], tc[2])) &
             (P[:, 2] <= max(ta[2], tb[2], tc[2])))
        if not m.any():
            continue
        Q = P[m]
        d = ((tb[1] - ta[1]) * (tc[2] - ta[2]) - (tc[1] - ta[1]) * (tb[2] - ta[2]))
        if abs(d) < 1e-30:
            continue
        w1 = ((Q[:, 1] - ta[1]) * (tc[2] - ta[2]) -
              (tc[1] - ta[1]) * (Q[:, 2] - ta[2])) / d
        w2 = ((tb[1] - ta[1]) * (Q[:, 2] - ta[2]) -
              (Q[:, 1] - ta[1]) * (tb[2] - ta[2])) / d
        w0 = 1.0 - w1 - w2
        hit = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not hit.any():
            continue
        xh = w0[hit] * ta[0] + w1[hit] * tb[0] + w2[hit] * tc[0]
        fwd = xh > Q[hit, 0]
        sel = np.nonzero(m)[0][np.nonzero(hit)[0][fwd]]
        np.add.at(inside, sel, 1)
    return (inside % 2 == 1).reshape(nz, ny, nx)


def hull_volume(points, faces):
    a = points[faces[:, 0]]
    b = points[faces[:, 1]]
    c = points[faces[:, 2]]
    return float(np.sum(np.sum(a * np.cross(b - a, c - a), axis=1)) / 6.0)


def points_in_hull(P, hull_pts, hull_faces, tol=1e-9):
    """True where P is inside the (outward-oriented) convex hull."""
    a = hull_pts[hull_faces[:, 0]]
    n = face_normals(hull_pts, hull_faces)
    n = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-30)
    d = np.einsum("ij,kj->ik", P, n) - np.einsum("ij,ij->i", a, n)[None, :]
    return np.all(d <= tol, axis=1)


def convex_hull(points):
    """Return (hull_points, hull_faces) or raise if scipy is unavailable."""
    if not HAVE_SCIPY:
        raise RuntimeError("scipy is not installed; convex hulls unavailable")
    from scipy.spatial import ConvexHull as CH
    h = CH(np.asarray(points, dtype=np.float64))
    verts = h.points[h.vertices]
    remap = {int(v): i for i, v in enumerate(h.vertices)}
    faces = np.array([[remap[int(v)] for v in s] for s in h.simplices], dtype=np.int64)
    # orient outward
    cen = verts.mean(axis=0)
    fn = face_normals(verts, faces)
    flip = np.sum(fn * (verts[faces[:, 0]] - cen), axis=1) < 0
    faces[flip] = faces[flip][:, ::-1]
    return verts, faces


def obb_from_points(points):
    """Oriented box from the covariance eigenbasis, tightened to the extremes.

    A PCA box is not the minimum-volume box and does not claim to be; it is
    deterministic, cheap, and within a few percent of optimal on the shapes
    props actually are.
    """
    P = np.asarray(points, dtype=np.float64)
    mu = P.mean(axis=0)
    cov = np.cov((P - mu).T)
    if not np.all(np.isfinite(cov)):
        cov = np.eye(3)
    _w, V = np.linalg.eigh(cov)
    V = V[:, ::-1]
    if np.linalg.det(V) < 0:
        V[:, 2] = -V[:, 2]
    local = (P - mu) @ V
    lo, hi = local.min(axis=0), local.max(axis=0)
    half = (hi - lo) / 2.0
    centre = mu + V @ ((hi + lo) / 2.0)
    return centre, half, quat_from_matrix(V)
