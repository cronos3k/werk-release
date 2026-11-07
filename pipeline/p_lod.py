#!/usr/bin/env python3
"""p_lod.py — the LOD chain, core.geom.lod, with a MEASURED screen-space error.

SPEC.md section 4 defines `screen_space_error_px` as "the maximum silhouette
deviation from core.geom.game, in pixels, when the entity's bounding sphere is
rendered at 1080 vertical pixels with a 60 degree vertical field of view". That
is a rendering, so this producer renders it: both silhouettes, at 1080, from
every tile-centre direction of the imposter preview tier, and the number
written into the node is the largest symmetric boundary distance any of those
views produced.

The orthographic limit is used, with the view volume's half height set to the
bounding sphere radius, so the sphere spans exactly 1080 pixels. That is the
configuration the spec sentence describes and it removes the one free
parameter a perspective camera would leave (how far away).
"""

import numpy as np

from . import glb, meshops as M, raster
from .p_imposter import tile_directions

REFERENCE_PX = 1080
FOV_Y_RAD = 60.0 * np.pi / 180.0


def _edt(mask):
    from scipy.ndimage import distance_transform_edt
    return distance_transform_edt(~mask)


def silhouette_error_px(a_pos, a_idx, b_pos, b_idx, dirs, radius, centre,
                        size=REFERENCE_PX):
    """Symmetric silhouette Hausdorff distance in pixels, max over `dirs`."""
    worst = 0.0
    per_view = []
    for d in dirs:
        A = raster.silhouette(a_pos, a_idx, d, radius, size, pivot=centre)
        B = raster.silhouette(b_pos, b_idx, d, radius, size, pivot=centre)
        if not A.any() and not B.any():
            per_view.append(0.0)
            continue
        da = _edt(A)
        db = _edt(B)
        e1 = float(da[B & ~A].max()) if (B & ~A).any() else 0.0
        e2 = float(db[A & ~B].max()) if (A & ~B).any() else 0.0
        e = max(e1, e2)
        per_view.append(e)
        worst = max(worst, e)
    return worst, per_view


def run(ctx, mesh, bounds, levels=(0.5, 0.25, 0.12, 0.06), views=16,
        min_tris=48, size=REFERENCE_PX):
    pos, idx = mesh["pos"], mesh["idx"]
    nrm, uv, col = mesh["nrm"], mesh["uv"], mesh["col"]
    dirs = tile_directions(int(round(views ** 0.5)), "octahedral-full")
    made = []
    cur_pos, cur_idx = pos, idx
    for lvl, frac in enumerate(levels, start=1):
        target = max(min_tris, int(len(idx) * frac))
        if target >= len(cur_idx):
            break
        dp, di, st = M.decimate(cur_pos, cur_idx, target)
        if len(di) < 4:
            break
        sse, per_view = silhouette_error_px(pos, idx, dp, di, dirs,
                                            bounds["radius"], bounds["centre"], size)
        # carry the attributes of the nearest surviving source vertex
        vn = M.vertex_normals(dp, di)
        blob = glb.build_glb(dp, di, nrm=vn, name="lod%d" % lvl)
        f = ctx.put("geometry/lod%d.glb" % lvl, blob)
        node_id = "geom-lod%d" % lvl
        ctx.node(node_id, "core.geom.lod",
                 ctx.version([f],
                             "Quadric-error decimation of geometry/game.glb to "
                             "%d triangles (%.1f%%), %d edge collapses. The "
                             "screen-space error is a MEASUREMENT: both "
                             "silhouettes rendered at %d px over %d directions, "
                             "largest symmetric boundary distance %.2f px."
                             % (len(di), 100.0 * len(di) / len(idx),
                                st["collapses"], size, len(dirs), sse),
                             "measured", inputs=["geometry/game.glb"],
                             params={"target_triangles": target,
                                     "collapse_to": "endpoint",
                                     "protect_boundary": True}),
                 edges=[{"to": "geom-game", "kind": "enhances",
                         "role": "simplification"}],
                 meta={"lod_level": lvl,
                       "triangle_count": int(len(di)),
                       "vertex_count": int(len(dp)),
                       "reference_resolution_px": REFERENCE_PX,
                       "screen_space_error_px": round(float(sse), 4),
                       "sse_method": "rendered-silhouette-hausdorff",
                       "sse_views": len(dirs),
                       "sse_projection": "orthographic-half-height-equals-"
                                         "bounding-sphere-radius",
                       "sse_per_view_px": [round(float(v), 4) for v in per_view],
                       "decimator": "quadric-error-endpoint-collapse/0.1"},
                 part="whole")
        made.append({"node": node_id, "level": lvl, "tris": int(len(di)),
                     "sse_px": float(sse), "pos": dp, "idx": di})
        cur_pos, cur_idx = dp, di
    if not made:
        raise ValueError("mesh has %d triangles: nothing to decimate above the "
                         "%d-triangle floor" % (len(idx), min_tris))
    return made
