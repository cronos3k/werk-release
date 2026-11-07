#!/usr/bin/env python3
"""p_collider.py — core.phys.colliders, plus the convex decomposition GLB.

WHAT IS VENDORED, AND WHAT RUNS (the brief asked for this in writing).

TWO engines, in preference order, and the node records WHICH ONE RAN — it is
never assumed from the fact that the code is present:

  vhacd/4.1            the real V-HACD. `tools/vhacd/VHACD.h` is upstream v4.1
                       byte-for-byte (BSD-3-Clause; sha256 and provenance in
                       tools/vhacd/README.md) behind a ~150-line CLI compiled
                       by `python tools/build_native.py`. Ruling 18.

  voxel-hacd-lite/0.1  the fallback, and the only thing that ran before ruling
                       18: V-HACD's three-step shape (solid-voxelise, measure
                       concavity against the hull, recursively split on the
                       best axis-aligned plane) WITHOUT its plane search, hull
                       simplification or volume-conservative merge. Its hulls
                       are built from voxel CORNERS, so the union is a superset
                       of the solid and `volume_ratio` runs 2-4 rather than
                       near 1. It is a worse decomposition and the node says
                       so.

Which one ran is in `fit.method` and, machine-readably, in the node's
`meta.collider_engine` -- `meta` and not `fit` only because
core.phys.colliders.schema.json's `fit` is additionalProperties:false with room
for one method string and two numbers. Filed as S-P-1.

The fit is measured the same way for both, so the two are comparable in one
table: `hausdorff_max_m`, `volume_ratio` (collider volume / mesh volume) and,
new with ruling 18, the ratio taken BOTH WAYS on the same voxel grid,
`volume_coverage` (how much of the solid the colliders actually contain) and
`volume_excess` (how much they add that is not the object). A superset engine
scores coverage 1.0 and excess high; an under-fitting engine does the reverse,
and one number alone cannot tell those apart.

Dependencies: numpy, and scipy for `ConvexHull` only. scipy is a PIPELINE
dependency, never a loader one -- nothing here travels inside a .werk.
"""

import numpy as np

from .common import jbytes
from . import glb, meshops as M, vhacd as VH


def _concavity(vox_pts, hull_pts, hull_faces, cell):
    hv = abs(M.hull_volume(hull_pts, hull_faces))
    vv = len(vox_pts) * cell ** 3
    if hv <= 0:
        return 0.0, hv, vv
    return max(0.0, (hv - vv) / hv), hv, vv


def decompose(vox_pts, cell, max_parts=16, threshold=0.05, depth=0, max_depth=5):
    """Recursive axis-aligned split on the voxel set. Returns list of point
    arrays, each of which is one convex part's voxel centres."""
    if len(vox_pts) < 4:
        return [vox_pts] if len(vox_pts) else []
    try:
        hp, hf = M.convex_hull(vox_pts)
    except Exception:
        return [vox_pts]
    conc, _hv, _vv = _concavity(vox_pts, hp, hf, cell)
    if conc <= threshold or depth >= max_depth or max_parts <= 1:
        return [vox_pts]

    best = None
    for axis in range(3):
        v = vox_pts[:, axis]
        lo, hi = v.min(), v.max()
        if hi - lo < cell * 1.5:
            continue
        for q in (0.3, 0.4, 0.5, 0.6, 0.7):
            plane = lo + (hi - lo) * q
            left = vox_pts[v <= plane]
            right = vox_pts[v > plane]
            if len(left) < 4 or len(right) < 4:
                continue
            score = 0.0
            for part in (left, right):
                try:
                    php, phf = M.convex_hull(part)
                except Exception:
                    score = np.inf
                    break
                c, hv, _ = _concavity(part, php, phf, cell)
                score += c * hv
            if best is None or score < best[0]:
                best = (score, axis, plane, left, right)
    if best is None:
        return [vox_pts]
    _s, _axis, _plane, left, right = best
    budget = max_parts // 2
    return (decompose(left, cell, budget, threshold, depth + 1, max_depth) +
            decompose(right, cell, max_parts - budget, threshold, depth + 1, max_depth))


def _hulls_vhacd(pos, idx, max_parts):
    """The real V-HACD. Returns (hulls, engine, params) or raises."""
    hulls, info = VH.decompose(pos, idx, max_hulls=max_parts)
    out = [(h["points"], h["faces"]) for h in hulls
           if len(h["points"]) >= 4 and len(h["faces"]) >= 4]
    if not out:
        raise RuntimeError("V-HACD returned no usable hull")
    return out, info["engine"], info["params"]


def _hulls_lite(vox, cell, max_parts):
    """The fallback. Voxel-corner hulls, so the union is a superset."""
    parts = [p for p in decompose(vox, cell, max_parts=max_parts) if len(p) >= 4]
    if not parts:
        raise ValueError("decomposition produced no usable part")
    half = cell * 0.5
    box = np.array([[sx * half, sy * half, sz * half]
                    for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)])
    out = []
    for p in parts:
        corners = (p[:, None, :] + box[None, :, :]).reshape(-1, 3)
        out.append(M.convex_hull(corners))
    return out, "voxel-hacd-lite/0.1", {"voxel_grid_cell_m": round(float(cell), 9),
                                        "max_parts": int(max_parts)}


def run(ctx, mesh, bounds, material_ids, grid=40, max_parts=12):
    pos, idx = mesh["pos"], mesh["idx"]
    lo = bounds["aabb_min"]
    hi = bounds["aabb_max"]
    ext = hi - lo
    cell = float(ext.max()) / grid
    if cell <= 0:
        raise ValueError("degenerate bounding box")
    pad = cell * 1.5
    origin = lo - pad
    dims = [int(np.ceil((ext[k] + 2 * pad) / cell)) + 1 for k in range(3)]

    occ = M.voxelize(pos, idx, origin, cell, dims)
    nz, ny, nx = occ.shape
    if not occ.any():
        raise ValueError("solid voxelisation found no interior: the mesh is not "
                         "closed enough for a volume decomposition")
    kk, jj, ii = np.nonzero(occ)
    vox = np.stack([origin[0] + cell * ii, origin[1] + cell * jj,
                    origin[2] + cell * kk], axis=1)

    # -- the decomposition: real V-HACD if it is built, the lite one if not --
    ok, engine_or_why = VH.available()
    fallback_reason = None
    hulls = engine = eparams = None
    if ok:
        try:
            hulls, engine, eparams = _hulls_vhacd(pos, idx, max_parts)
        except Exception as e:                      # noqa: BLE001 - reported
            fallback_reason = "%s: %s" % (type(e).__name__, e)
            hulls = None
    else:
        fallback_reason = engine_or_why
    if hulls is None:
        hulls, engine, eparams = _hulls_lite(vox, cell, max_parts)
    parts = hulls

    # -- the convex parts, as one GLB ------------------------------------
    hp_all, hf_all, base = [], [], 0
    spheres, boxes = [], []
    mid = material_ids[0] if material_ids else None
    for hp, hf in hulls:
        hp_all.append(hp)
        hf_all.append(hf + base)
        base += len(hp)
        c, r = M.welzl(hp)
        sph = {"center": [round(float(v), 6) for v in c], "radius": round(float(r), 6)}
        if mid:
            sph["material_id"] = mid
        spheres.append(sph)
        bc, bh, bq = M.obb_from_points(hp)
        box = {"center": [round(float(v), 6) for v in bc],
               "half_extents": [round(max(float(v), 1e-6), 6) for v in bh],
               "rotation": [round(float(v), 8) for v in bq]}
        if mid:
            box["material_id"] = mid
        boxes.append(box)

    hull_pos = np.vstack(hp_all)
    hull_idx = np.vstack(hf_all)
    hull_glb = glb.build_glb(hull_pos, hull_idx,
                             nrm=M.vertex_normals(hull_pos, hull_idx),
                             name="convex-decomposition")
    hf = ctx.put("physics/convex-hulls.glb", hull_glb)
    ctx.node("collider-hulls", "x.werk-collider.convex-hulls",
             ctx.version([hf],
                         "The convex decomposition itself, %d parts / %d "
                         "triangles, as a GLB. It is 'enhances' only: the "
                         "sphere and box sets in physics/colliders.json make "
                         "the node useful without it."
                         % (len(parts), len(hull_idx)),
                         "measured", inputs=["geometry/game.glb"],
                         params=dict({"voxel_grid": grid, "max_parts": max_parts,
                                      "engine": engine}, **eparams)),
             edges=[{"to": "geom-game", "kind": "enhances", "role": "approximates"}],
             meta={"role": "convex-decomposition", "part_count": len(parts),
                   "triangle_count": int(len(hull_idx)),
                   "engine": engine})

    # -- measured fit ----------------------------------------------------
    # union volume by voxel occupancy of the parts, on the same grid, so the
    # ratio is not inflated by parts that overlap.
    gx = origin[0] + cell * np.arange(nx)
    gy = origin[1] + cell * np.arange(ny)
    gz = origin[2] + cell * np.arange(nz)
    Z, Y, X = np.meshgrid(gz, gy, gx, indexing="ij")
    P = np.stack([X.ravel(), Y.ravel(), Z.ravel()], axis=1)
    union = np.zeros(len(P), dtype=bool)
    off = 0
    for k, p in enumerate(parts):
        n = len(hp_all[k])
        union |= M.points_in_hull(P, hp_all[k], hf_all[k] - off, tol=1e-9)
        off += n
    union_vol = float(union.sum()) * cell ** 3
    mesh_vol = float(bounds["volume"]) or float(occ.sum()) * cell ** 3

    # The ratio taken BOTH WAYS, on that same grid and the same occupancy, so
    # over- and under-fitting are two separate numbers instead of one that
    # cannot distinguish them. `occ` is (nz,ny,nx) and P was built with
    # indexing="ij" over (gz,gy,gx), so occ.ravel() and `union` are the same
    # cells in the same order.
    solid = occ.ravel()
    n_solid = int(solid.sum())
    inter = int((union & solid).sum())
    coverage = inter / n_solid if n_solid else 0.0          # of the object, held
    excess = int((union & ~solid).sum()) / n_solid if n_solid else 0.0  # added

    # Hausdorff: surface samples of the source mesh to the collider union.
    rng = np.random.RandomState(20260808)
    a, b, c = pos[idx[:, 0]], pos[idx[:, 1]], pos[idx[:, 2]]
    ar = np.linalg.norm(np.cross(b - a, c - a), axis=1) * 0.5
    w = ar / ar.sum()
    nsamp = min(4000, max(500, len(idx)))
    pick = rng.choice(len(idx), size=nsamp, p=w)
    r1 = np.sqrt(rng.rand(nsamp))[:, None]
    r2 = rng.rand(nsamp)[:, None]
    S = a[pick] * (1 - r1) + b[pick] * (r1 * (1 - r2)) + c[pick] * (r1 * r2)
    inside_any = np.zeros(nsamp, dtype=bool)
    dist = np.full(nsamp, np.inf)
    off = 0
    for k in range(len(parts)):
        n = len(hp_all[k])
        f = hf_all[k] - off
        inside_any |= M.points_in_hull(S, hp_all[k], f, tol=1e-9)
        d = M.hausdorff_to_mesh(S, hp_all[k], f)
        # A hull with a degenerate face makes hausdorff_to_mesh divide by zero
        # and hand back a NaN, and np.minimum propagates it, which would put a
        # NaN in a package's measured fit. Non-finite distances are dropped —
        # the sample is simply not measured against THAT hull — and counted, so
        # a fit computed against fewer hulls than there are says so. Filed S-P-3.
        finite = np.isfinite(d)
        dist = np.where(finite, np.minimum(dist, d), dist)
        off += n
    dist[inside_any] = 0.0
    unmeasured = int((~np.isfinite(dist)).sum())
    if unmeasured:
        dist = dist[np.isfinite(dist)]
    haus = float(dist.max()) if len(dist) else 0.0

    doc = {
        "schema_version": 1,
        "space": "part-local",
        "groups": [{"part_id": "whole", "spheres": spheres, "boxes": boxes,
                    "convex_hull_node": "collider-hulls"}],
        "fit": {"method": "%s, %d parts (fit measured on a %dx%dx%d voxel grid; "
                          "see pipeline/p_collider.py)"
                          % (engine, len(parts), nx, ny, nz),
                "hausdorff_max_m": round(haus, 6),
                "volume_ratio": round(union_vol / mesh_vol, 6) if mesh_vol > 0 else 0.0},
        "epistemic": "measured",
        "note": "The decomposition was produced by %s%s. One sphere and one "
                "oriented box per convex part, %d of each. hausdorff_max_m is "
                "the largest distance from any of %d area-weighted surface "
                "samples of geometry/game.glb to the collider union. The three "
                "volume numbers are all measured on the same %dx%dx%d voxel "
                "grid, so overlapping parts are counted once: volume_ratio is "
                "collider volume / mesh volume, volume_coverage is the fraction "
                "of the object's own solid the colliders contain, and "
                "volume_excess is the volume they add that is not the object, "
                "as a fraction of the object. One ratio cannot tell an engine "
                "that wraps the object loosely from one that misses parts of "
                "it; these two can."
                % (engine,
                   "" if fallback_reason is None else
                   " (the preferred engine was not used: %s)" % fallback_reason,
                   len(parts), nsamp, nx, ny, nz),
    }
    f = ctx.put("physics/colliders.json", jbytes(doc))
    ctx.node("colliders", "core.phys.colliders",
             ctx.version([f], "Sphere and OBB sets from a %d-part convex "
                              "decomposition by %s, with the fit measured both "
                              "ways." % (len(parts), engine),
                         "measured", inputs=["geometry/game.glb"],
                         params=dict({"voxel_grid": grid, "max_parts": max_parts,
                                      "concavity_threshold": 0.05,
                                      "engine": engine}, **eparams)),
             edges=[{"to": "geom-game", "kind": "requires", "role": "approximates"},
                    {"to": "collider-hulls", "kind": "enhances",
                     "role": "exact-decomposition"}],
             # `fit` in core.phys.colliders.schema.json is
             # additionalProperties:false and has room for exactly one method
             # string and two numbers, so the engine identity and the
             # both-ways ratios live in meta and the schema gap is filed as
             # S-P-1. Non-normative keys, and named as such.
             meta=dict({"collider_engine": engine},
                       **({} if fallback_reason is None else
                          {"collider_engine_fallback_reason": fallback_reason}),
                   **{"volume_coverage": round(coverage, 6),
                      "volume_excess": round(excess, 6),
                      "hausdorff_unmeasured_samples": unmeasured,
                      "volume_measure_grid": [int(nx), int(ny), int(nz)]}),
             part="whole")
    ctx.schemas["core.phys.colliders"] = "spec/schemas/core.phys.colliders.schema.json"
    return {"parts": len(parts), "hausdorff": haus,
            "volume_ratio": union_vol / mesh_vol if mesh_vol > 0 else 0.0,
            "volume_coverage": coverage, "volume_excess": excess,
            "engine": engine, "fallback_reason": fallback_reason,
            "occ": occ, "origin": origin, "cell": cell, "dims": (nx, ny, nz),
            "voxel_volume": float(occ.sum()) * cell ** 3}
