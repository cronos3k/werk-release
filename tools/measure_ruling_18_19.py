#!/usr/bin/env python3
"""measure_ruling_18_19.py — old versus new, on the Stage 3B gate meshes.

Rulings 18 and 19 replaced two producers' internals. This script measures BOTH
implementations of each on the SAME meshes the Stage 3B gate used, in one
process, so the comparison is not two runs of a pipeline with a flag flipped
between them.

    python tools/measure_ruling_18_19.py [--assets crate lantern example]

Prints a table and writes tools/_build/ruling-18-19-measurements.json.

Colliders (18): voxel-hacd-lite/0.1 versus the real V-HACD, both scored by the
same three numbers on the same voxel grid — hausdorff, volume_ratio, and the
ratio taken both ways (coverage / excess).

Tangents (19): Gram-Schmidt versus the reference MikkTSpace, scored by
orthogonality to the normal, unit length, handedness split, and — the one that
matters — how far apart the two bases actually are, in degrees.
"""

import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import glb, meshops as M, mikktspace as MT, vhacd as VH  # noqa: E402
from pipeline import p_collider as PC  # noqa: E402

_LAB = os.environ.get("WERK_LAB", "<WERK_LAB unset>")
ASSETS = {
    "crate": os.path.join(_LAB, "splat-foley", "outputs", "wooden-crate-01", "model.glb"),
    "lantern": os.path.join(_LAB, "splat-foley", "outputs", "lantern", "model.glb"),
    "example": os.path.join(_LAB, "splat-foley", "outputs", "example", "model.glb"),
}


# --------------------------------------------------------------------------

def load(path):
    scene = glb.load_scene(open(path, "rb").read())
    pos, idx, extra, _ = M.weld(scene.pos, scene.idx, [scene.nrm, scene.uv, scene.col])
    nrm, uv, col = extra
    bad = np.linalg.norm(nrm, axis=1) < 1e-9
    if bad.any():
        nrm = np.where(bad[:, None], M.vertex_normals(pos, idx), nrm)
    nrm = nrm / np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-30)
    return scene, pos, idx, nrm, uv, col


def aabb(pos):
    return pos.min(axis=0), pos.max(axis=0)


def mesh_volume(pos, idx, occ=None, cell=None):
    """The SAME denominator p_collider uses, so these ratios sit in the same
    table as the Stage 3B ones: the enclosed volume when the mesh is closed,
    and the solid-voxel volume when it is not — because a divergence-theorem
    volume of an open surface is a fiction, and all three gate assets are open.
    """
    from pipeline import p_bounds as PB
    closed, _hist = PB.watertightness(idx)
    if closed:
        return abs(float(M.mass_properties(pos, idx)["volume"])), True
    return float(occ.sum()) * cell ** 3, False


# --------------------------------------------------------------------------
# colliders
# --------------------------------------------------------------------------

def score_hulls(hulls, pos, idx, origin, cell, occ, mesh_vol, seed=20260808):
    nz, ny, nx = occ.shape
    gx = origin[0] + cell * np.arange(nx)
    gy = origin[1] + cell * np.arange(ny)
    gz = origin[2] + cell * np.arange(nz)
    Z, Y, X = np.meshgrid(gz, gy, gx, indexing="ij")
    P = np.stack([X.ravel(), Y.ravel(), Z.ravel()], axis=1)

    union = np.zeros(len(P), dtype=bool)
    for hp, hf in hulls:
        union |= M.points_in_hull(P, hp, hf, tol=1e-9)
    union_vol = float(union.sum()) * cell ** 3
    solid = occ.ravel()
    n_solid = int(solid.sum())
    coverage = float((union & solid).sum()) / n_solid if n_solid else 0.0
    excess = float((union & ~solid).sum()) / n_solid if n_solid else 0.0

    rng = np.random.RandomState(seed)
    a, b, c = pos[idx[:, 0]], pos[idx[:, 1]], pos[idx[:, 2]]
    ar = np.linalg.norm(np.cross(b - a, c - a), axis=1) * 0.5
    w = ar / ar.sum()
    nsamp = min(4000, max(500, len(idx)))
    pick = rng.choice(len(idx), size=nsamp, p=w)
    r1 = np.sqrt(rng.rand(nsamp))[:, None]
    r2 = rng.rand(nsamp)[:, None]
    S = a[pick] * (1 - r1) + b[pick] * (r1 * (1 - r2)) + c[pick] * (r1 * r2)
    inside = np.zeros(nsamp, dtype=bool)
    dist = np.full(nsamp, np.inf)
    for hp, hf in hulls:
        inside |= M.points_in_hull(S, hp, hf, tol=1e-9)
        d = M.hausdorff_to_mesh(S, hp, hf)
        finite = np.isfinite(d)
        dist = np.where(finite, np.minimum(dist, d), dist)
    dist[inside] = 0.0
    unmeasured = int((~np.isfinite(dist)).sum())
    dist = dist[np.isfinite(dist)]
    if not len(dist):
        dist = np.zeros(1)

    return {"parts": len(hulls),
            "hausdorff_unmeasured_samples": unmeasured,
            "hull_triangles": int(sum(len(hf) for _hp, hf in hulls)),
            "hausdorff_max_m": float(dist.max()),
            "hausdorff_mean_m": float(dist.mean()),
            "volume_ratio": union_vol / mesh_vol if mesh_vol > 0 else 0.0,
            "volume_coverage": coverage,
            "volume_excess": excess}


def collider_compare(name, pos, idx, grid=40, max_parts=12):
    lo, hi = aabb(pos)
    ext = hi - lo
    cell = float(ext.max()) / grid
    pad = cell * 1.5
    origin = lo - pad
    dims = [int(np.ceil((ext[k] + 2 * pad) / cell)) + 1 for k in range(3)]
    occ = M.voxelize(pos, idx, origin, cell, dims)
    if not occ.any():
        return {"error": "solid voxelisation found no interior"}
    kk, jj, ii = np.nonzero(occ)
    vox = np.stack([origin[0] + cell * ii, origin[1] + cell * jj,
                    origin[2] + cell * kk], axis=1)
    mesh_vol, closed = mesh_volume(pos, idx, occ, cell)

    out = {"mesh_volume_m3": mesh_vol, "watertight": closed,
           "volume_denominator": "enclosed" if closed else "solid-voxel",
           "voxel_grid": list(occ.shape[::-1]), "solid_voxels": int(occ.sum())}

    t0 = time.time()
    lite, _e, _p = PC._hulls_lite(vox, cell, max_parts)
    t_lite = time.time() - t0
    s = score_hulls(lite, pos, idx, origin, cell, occ, mesh_vol)
    s["seconds"] = t_lite
    s["engine"] = "voxel-hacd-lite/0.1"
    out["old"] = s

    ok, why = VH.available()
    if not ok:
        out["new"] = {"error": why}
        return out
    t0 = time.time()
    try:
        hulls, engine, params = PC._hulls_vhacd(pos, idx, max_parts)
    except Exception as e:                                   # noqa: BLE001
        out["new"] = {"error": "%s: %s" % (type(e).__name__, e)}
        return out
    t_new = time.time() - t0
    s = score_hulls(hulls, pos, idx, origin, cell, occ, mesh_vol)
    s["seconds"] = t_new
    s["engine"] = engine
    s["params"] = params
    out["new"] = s
    return out


# --------------------------------------------------------------------------
# tangents
# --------------------------------------------------------------------------

def tangent_stats(tan, nrm):
    """tan is (n,4), nrm is (n,3), both on the SAME vertex set."""
    t = tan[:, :3]
    ln = np.linalg.norm(t, axis=1)
    unit = t / np.maximum(ln[:, None], 1e-30)
    signed = np.einsum("ij,ij->i", unit, nrm)
    dot = np.abs(signed)
    # Angle between T and N. Exactly orthogonal is 90 deg; the interesting
    # number is how far from 90 the worst vertex is.
    ang = np.degrees(np.arccos(np.clip(signed, -1.0, 1.0)))
    w = tan[:, 3]
    return {
        "vertices": int(len(tan)),
        "unit_length_max_dev": float(np.abs(ln - 1.0).max()),
        "orthogonality_max_abs_dot": float(dot.max()),
        "orthogonality_mean_abs_dot": float(dot.mean()),
        "orthogonality_max_deviation_deg": float(np.abs(ang - 90.0).max()),
        "orthogonality_mean_deviation_deg": float(np.abs(ang - 90.0).mean()),
        "handedness_plus1": int((w > 0).sum()),
        "handedness_minus1": int((w < 0).sum()),
        "handedness_other": int(((w != 1.0) & (w != -1.0)).sum()),
    }


def tangent_compare(name, scene, pos, idx, nrm, uv, col):
    out = {}
    if not scene.had_uv:
        out["skipped"] = "the GLB has no TEXCOORD_0"
        return out

    t0 = time.time()
    gs_tan, gs_deg = M.tangents(pos, nrm, uv, idx)
    t_gs = time.time() - t0
    out["old"] = tangent_stats(gs_tan, nrm)
    out["old"].update({"engine": "gram-schmidt-accumulated/0.1",
                       "seconds": t_gs, "degenerate": gs_deg, "splits": 0})

    ok, why = MT.available()
    if not ok:
        out["new"] = {"error": why}
        return out
    t0 = time.time()
    split = MT.tangents_split(pos, nrm, uv, idx, extra=(col,))
    t_mt = time.time() - t0
    if split is None:
        out["new"] = {"error": "genTangSpaceDefault refused the mesh"}
        return out
    st = tangent_stats(split["tan"], split["nrm"])
    st.update({"engine": split["engine"], "seconds": t_mt,
               "degenerate": split["degenerate"], "splits": split["splits"]})
    out["new"] = st

    # How far apart are the two bases, on the vertices they share? Compare each
    # split vertex's MikkTSpace tangent against the Gram-Schmidt tangent of the
    # welded vertex it came from.
    src = split["source_vertex"]
    a = split["tan"][:, :3]
    b = gs_tan[src, :3]
    a = a / np.maximum(np.linalg.norm(a, axis=1, keepdims=True), 1e-30)
    b = b / np.maximum(np.linalg.norm(b, axis=1, keepdims=True), 1e-30)
    ang = np.degrees(np.arccos(np.clip(np.einsum("ij,ij->i", a, b), -1.0, 1.0)))
    out["divergence"] = {
        "angle_mean_deg": float(ang.mean()),
        "angle_median_deg": float(np.median(ang)),
        "angle_p95_deg": float(np.percentile(ang, 95)),
        "angle_max_deg": float(ang.max()),
        "over_1deg_fraction": float((ang > 1.0).mean()),
        "over_10deg_fraction": float((ang > 10.0).mean()),
        "handedness_disagreements": int((split["tan"][:, 3] != gs_tan[src, 3]).sum()),
    }
    return out


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", nargs="*", default=list(ASSETS))
    ap.add_argument("--out", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "_build",
        "ruling-18-19-measurements.json"))
    a = ap.parse_args()

    print("V-HACD:     %s" % (VH.available(),))
    print("MikkTSpace: %s" % (MT.available(),))
    print()

    results = {"vhacd": VH.available()[1], "mikktspace": MT.available()[1],
               "assets": {}}
    for name in a.assets:
        path = ASSETS[name]
        if not os.path.exists(path):
            print("%-8s MISSING %s" % (name, path))
            results["assets"][name] = {"error": "missing input " + path}
            continue
        scene, pos, idx, nrm, uv, col = load(path)
        print("== %s: %d welded verts, %d tris" % (name, len(pos), len(idx)))
        r = {"input": path, "welded_vertices": int(len(pos)),
             "triangles": int(len(idx))}
        r["colliders"] = collider_compare(name, pos, idx)
        r["tangents"] = tangent_compare(name, scene, pos, idx, nrm, uv, col)
        results["assets"][name] = r

        c = r["colliders"]
        for k in ("old", "new"):
            v = c.get(k, {})
            if "error" in v:
                print("   colliders %-4s ERROR %s" % (k, v["error"]))
            else:
                print("   colliders %-4s %-20s parts=%-3d haus=%.4f m  "
                      "ratio=%.3f  coverage=%.4f  excess=%.3f  %.1f s"
                      % (k, v["engine"], v["parts"], v["hausdorff_max_m"],
                         v["volume_ratio"], v["volume_coverage"],
                         v["volume_excess"], v["seconds"]))
        t = r["tangents"]
        if "skipped" in t:
            print("   tangents  skipped: %s" % t["skipped"])
        else:
            for k in ("old", "new"):
                v = t.get(k, {})
                if "error" in v:
                    print("   tangents  %-4s ERROR %s" % (k, v["error"]))
                else:
                    print("   tangents  %-4s %-30s verts=%-6d |T.N|max=%.2e  "
                          "|T|dev=%.2e  w+=%d w-=%d  splits=%d  %.3f s"
                          % (k, v["engine"], v["vertices"],
                             v["orthogonality_max_abs_dot"],
                             v["unit_length_max_dev"], v["handedness_plus1"],
                             v["handedness_minus1"], v["splits"], v["seconds"]))
            d = t.get("divergence")
            if d:
                print("   tangents  diff  mean=%.2f deg  median=%.2f  p95=%.2f  "
                      "max=%.2f  >1deg=%.1f%%  handedness flips=%d"
                      % (d["angle_mean_deg"], d["angle_median_deg"],
                         d["angle_p95_deg"], d["angle_max_deg"],
                         100 * d["over_1deg_fraction"],
                         d["handedness_disagreements"]))
        print()

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w") as f:
        json.dump(results, f, indent=2)
    print("wrote", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
