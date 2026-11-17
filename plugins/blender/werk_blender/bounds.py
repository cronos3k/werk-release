"""AABB, exact minimal sphere, surface area, volume, watertightness.

Ported from `fixtures/build_golden.py` — the same Welzl implementation that
produced `fixtures/crate-v1.werk`'s `physics/bounds.json`, so an entity
round-tripped through Blender is measured by the same code that measured it
the first time. The port is deliberate duplication rather than an import: this
add-on ships alone, and law 1 bans a promise about another file.

`sphere_method` is written into the payload as `welzl-exact` and this module
EARNS that word: `minimal_sphere` checks the result against every input point
before returning it, and raises if the sphere misses one. An approximate
sphere labelled exact is precisely the quiet lie the format exists to remove.
"""

import math
import random
import sys


def aabb(points):
    """Component-wise min/max over every point. Returns (min3, max3)."""
    if not points:
        raise ValueError("an AABB over zero points is not a number")
    lo = [min(p[i] for p in points) for i in range(3)]
    hi = [max(p[i] for p in points) for i in range(3)]
    return lo, hi


# --- Welzl's exact minimal enclosing sphere ---------------------------------

def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _dist(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def _sphere_from(pts):
    """The trivial cases of Welzl: the sphere through 0..4 boundary points."""
    if not pts:
        return ((0.0, 0.0, 0.0), -1.0)
    if len(pts) == 1:
        return (tuple(pts[0]), 0.0)
    if len(pts) == 2:
        a, b = pts
        c = tuple((a[i] + b[i]) / 2.0 for i in range(3))
        return (c, _dist(c, a))
    if len(pts) == 3:
        a, b, c = pts
        u, v = _sub(b, a), _sub(c, a)
        w = _cross(u, v)
        d = 2.0 * _dot(w, w)
        if d < 1e-24:
            return max((_sphere_from([x, y]) for x, y in
                        ((a, b), (a, c), (b, c))), key=lambda s: s[1])
        t = _cross(_sub([_dot(u, u) * v[i] for i in range(3)],
                        [_dot(v, v) * u[i] for i in range(3)]), w)
        cen = tuple(a[i] + t[i] / d for i in range(3))
        return (cen, max(_dist(cen, p) for p in pts))
    a, b, c, d = pts[:4]
    m = [[2.0 * (p[i] - a[i]) for i in range(3)] for p in (b, c, d)]
    rhs = [sum(p[i] ** 2 - a[i] ** 2 for i in range(3)) for p in (b, c, d)]

    def det3(m3):
        return (m3[0][0] * (m3[1][1] * m3[2][2] - m3[1][2] * m3[2][1])
                - m3[0][1] * (m3[1][0] * m3[2][2] - m3[1][2] * m3[2][0])
                + m3[0][2] * (m3[1][0] * m3[2][1] - m3[1][1] * m3[2][0]))

    det = det3(m)
    if abs(det) < 1e-24:  # coplanar: the best 3-point sphere that holds all four
        best = None
        for tri in ((a, b, c), (a, b, d), (a, c, d), (b, c, d)):
            s = _sphere_from(list(tri))
            if all(_dist(s[0], p) <= s[1] + 1e-9 for p in pts[:4]):
                if best is None or s[1] < best[1]:
                    best = s
        return best or _sphere_from(pts[:3])
    cen = []
    for col in range(3):
        mm = [row[:] for row in m]
        for r in range(3):
            mm[r][col] = rhs[r]
        cen.append(det3(mm) / det)
    cen = tuple(cen)
    return (cen, max(_dist(cen, p) for p in pts[:4]))


def _in_ball(sphere, p, eps=1e-9):
    return sphere[1] >= 0.0 and _dist(sphere[0], p) <= sphere[1] + eps


def minimal_sphere(points, seed=20260808):
    """Welzl's exact minimal enclosing sphere, as (centre, radius).

    The point order is randomised with a FIXED seed: randomisation is what makes
    the expected running time linear, and the fixed seed is what makes an export
    reproducible. Every input point is checked against the result before it is
    allowed out of here.

    Welzl is recursive and Blender's Python has the usual CPython recursion
    limit, so the limit is raised for the call and restored afterwards; an
    export of a 200k-vertex mesh must not leave Blender's interpreter altered.
    """
    pts = [tuple(float(c) for c in p) for p in points]
    if not pts:
        raise ValueError("a minimal sphere over zero points is not a number")
    random.Random(seed).shuffle(pts)

    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old_limit, 3000, len(pts) * 8))
    try:
        def rec(n, bound):
            if n == 0 or len(bound) == 4:
                return _sphere_from(bound)
            p = pts[n - 1]
            s = rec(n - 1, bound)
            if _in_ball(s, p):
                return s
            return rec(n - 1, bound + [p])

        centre, radius = rec(len(pts), [])
    finally:
        sys.setrecursionlimit(old_limit)

    # The word `welzl-exact` is a claim, so it gets checked, not asserted.
    worst = max(_dist(centre, p) for p in pts)
    if worst > radius + 1e-6:
        raise ValueError(
            "minimal sphere r=%.9f misses a vertex at distance %.9f; refusing to "
            "write `welzl-exact` over a sphere that is not" % (radius, worst))
    return centre, radius


def mesh_stats(points, triangles):
    """Surface area (m^2), enclosed volume (m^3) and watertightness.

    Volume is the divergence-theorem sum of signed tetrahedron volumes to the
    origin. It is only a volume when the surface is closed, which is exactly
    what `watertight` is for — `core.phys.bounds.schema.json` says a volume
    from a non-watertight mesh is a fiction and the flag is how a consumer
    knows.
    """
    area = 0.0
    vol = 0.0
    edges = {}
    for a, b, c in triangles:
        pa, pb, pc = points[a], points[b], points[c]
        u = (pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2])
        v = (pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2])
        n = _cross(u, v)
        area += 0.5 * math.sqrt(_dot(n, n))
        vol += _dot(pa, n) / 6.0
        for e in ((a, b), (b, c), (c, a)):
            k = (e[0], e[1]) if e[0] < e[1] else (e[1], e[0])
            edges[k] = edges.get(k, 0) + 1
    watertight = bool(edges) and all(v == 2 for v in edges.values())
    return area, abs(vol), watertight


def bounds_record(points, triangles=None):
    """The `entity` block of a core.phys.bounds payload, in werk model space."""
    lo, hi = aabb(points)
    centre, radius = minimal_sphere(points)
    rec = {
        "aabb_min": [round(v, 7) for v in lo],
        "aabb_max": [round(v, 7) for v in hi],
        "sphere_center": [round(v, 7) for v in centre],
        "sphere_radius": round(radius, 7),
        "sphere_method": "welzl-exact",
        "longest_axis_m": round(max(hi[i] - lo[i] for i in range(3)), 7),
    }
    if triangles:
        area, volume, watertight = mesh_stats(points, triangles)
        rec["surface_area_m2"] = round(area, 7)
        rec["volume_m3"] = round(volume, 7)
        rec["watertight"] = watertight
    return rec


def selftest(verbose=False):
    """Cases with a hand-checkable answer, plus the case that matters: a box,
    where the minimal sphere is strictly smaller than the AABB's circumsphere
    only when the box is not a cube, and exactly equal when it is."""
    bad = []

    def near(got, want, what, tol=1e-6):
        if abs(got - want) > tol:
            bad.append("%s: got %.9f want %.9f" % (what, got, want))
        elif verbose:
            print("  OK %s = %.9f" % (what, got))

    # one point
    c, r = minimal_sphere([(1.0, 2.0, 3.0)])
    near(r, 0.0, "single point radius")
    near(_dist(c, (1.0, 2.0, 3.0)), 0.0, "single point centre")

    # two points: centre is the midpoint, radius is half the separation
    c, r = minimal_sphere([(-1.0, 0.0, 0.0), (1.0, 0.0, 0.0)])
    near(r, 1.0, "two point radius")
    near(_dist(c, (0.0, 0.0, 0.0)), 0.0, "two point centre")

    # unit cube corners: the sphere is the circumsphere, r = sqrt(3)/2
    cube = [(x, y, z) for x in (-0.5, 0.5) for y in (-0.5, 0.5) for z in (-0.5, 0.5)]
    c, r = minimal_sphere(cube)
    near(r, math.sqrt(3.0) / 2.0, "unit cube radius")

    # a flat 2x2 square in the XZ plane: r = sqrt(2), NOT the box circumsphere
    square = [(x, 0.0, z) for x in (-1.0, 1.0) for z in (-1.0, 1.0)]
    c, r = minimal_sphere(square)
    near(r, math.sqrt(2.0), "coplanar square radius")

    # a long thin rod plus a dense cloud near the origin: the exact sphere is
    # driven by the two ends and Ritter would overshoot. Checks that adding
    # interior points changes nothing.
    rod = [(-5.0, 0.0, 0.0), (5.0, 0.0, 0.0)]
    cloud = rod + [(random.Random(7 + i).uniform(-0.4, 0.4),
                    random.Random(70 + i).uniform(-0.4, 0.4),
                    random.Random(700 + i).uniform(-0.4, 0.4)) for i in range(200)]
    c, r = minimal_sphere(cloud)
    near(r, 5.0, "rod with interior cloud radius")

    # closed tetrahedron: watertight, positive volume
    tp = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
    tt = [(0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3)]
    area, vol, wt = mesh_stats(tp, tt)
    near(vol, 1.0 / 6.0, "tetrahedron volume")
    if not wt:
        bad.append("tetrahedron should be watertight")
    elif verbose:
        print("  OK tetrahedron watertight")

    # one face removed: not watertight
    _a, _v, wt2 = mesh_stats(tp, tt[:3])
    if wt2:
        bad.append("open tetrahedron should NOT be watertight")
    elif verbose:
        print("  OK open tetrahedron is not watertight")

    # the recursion limit is restored
    before = sys.getrecursionlimit()
    minimal_sphere(cube)
    if sys.getrecursionlimit() != before:
        bad.append("minimal_sphere left the recursion limit at %d, was %d"
                   % (sys.getrecursionlimit(), before))
    elif verbose:
        print("  OK recursion limit restored")

    return bad


if __name__ == "__main__":
    failures = selftest(verbose=True)
    for f in failures:
        print("FAIL " + f)
    print("bounds selftest: %s" % ("OK" if not failures else "FAILED"))
    sys.exit(1 if failures else 0)
