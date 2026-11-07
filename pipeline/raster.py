#!/usr/bin/env python3
"""raster.py — a headless software rasterizer, numpy only.

The imposter baker and the LOD silhouette metric both need pictures of a mesh
from a known camera, and both need them on a machine with no display, no GPU
and no driver. A GPU path would be faster and would make the pipeline's most
load-bearing measurement depend on which card ran it; this one is arithmetic,
so the same mesh gives the same pixels on every machine, which is what lets an
imposter node claim `epistemic: "measured"` and a screen-space error be a
number rather than a hint.

Orthographic only. Perspective is representable in the imposter descriptor and
deliberately not implemented: `projection: "orthographic"` is the only choice
that composites correctly across tile blends (imposter.layout.txt).
"""

import numpy as np


def look_at_basis(dir_to_eye, up_hint=(0.0, 1.0, 0.0)):
    """Right-handed camera basis looking along -dir_to_eye at the origin.

    Returns (right, up, forward) with forward = dir_to_eye (the direction from
    the subject towards the eye), so camera space is x=right, y=up, z=forward.
    """
    f = np.asarray(dir_to_eye, dtype=np.float64)
    f = f / np.linalg.norm(f)
    up = np.asarray(up_hint, dtype=np.float64)
    if abs(float(np.dot(f, up))) > 0.999:
        up = np.array([0.0, 0.0, 1.0])
    r = np.cross(up, f)
    r /= np.linalg.norm(r)
    u = np.cross(f, r)
    return r, u, f


def render(pos, idx, direction, half_height, size, attrs=None, pivot=(0, 0, 0),
           backface_cull=True):
    """Rasterize an orthographic view.

    pos          (nv,3) model space
    idx          (nt,3)
    direction    unit vector from the subject towards the eye, model space
    half_height  half the vertical extent of the view volume, metres
    size         output edge length in pixels (square)
    attrs        dict name -> (nv,k) per-vertex attributes to interpolate
    returns      dict with 'mask' (bool), 'depth' (f64, camera-space distance
                 from the eye plane, +inf where empty), and one entry per attr

    Depth increases away from the eye. The camera plane is at camera-space
    z = +camera_distance; a pixel's depth is that distance minus the vertex's
    z, so it is a metric distance and can be written into a 16-bit map with a
    declared range.
    """
    pos = np.asarray(pos, dtype=np.float64)
    idx = np.asarray(idx, dtype=np.int64)
    r, u, f = look_at_basis(direction)
    p = pos - np.asarray(pivot, dtype=np.float64)
    cam = np.stack([p @ r, p @ u, p @ f], axis=1)          # (nv,3)

    s = size / (2.0 * half_height)
    sx = cam[:, 0] * s + size * 0.5
    sy = size * 0.5 - cam[:, 1] * s                        # y down in raster space
    z = -cam[:, 2]                                         # increases away from eye

    depth = np.full((size, size), np.inf, dtype=np.float64)
    tri_id = np.full((size, size), -1, dtype=np.int64)
    # The barycentric buffer is only needed when an attribute is interpolated.
    # Silhouette work is the hot path (the LOD metric renders 1080px masks by
    # the dozen) and it wants none of it.
    need_bary = bool(attrs)
    bary = np.zeros((size, size, 3), dtype=np.float64) if need_bary else None

    ax, ay = sx[idx[:, 0]], sy[idx[:, 0]]
    bx, by = sx[idx[:, 1]], sy[idx[:, 1]]
    cx, cy = sx[idx[:, 2]], sy[idx[:, 2]]
    area = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
    keep = np.abs(area) > 1e-12
    if backface_cull:
        # raster-space y is flipped, so a CCW model-space front face has
        # NEGATIVE signed area here. Cull the other sign.
        keep &= area < 0.0
    tsel = np.nonzero(keep)[0]

    x0 = np.floor(np.minimum(np.minimum(ax, bx), cx)).astype(np.int64)
    x1 = np.ceil(np.maximum(np.maximum(ax, bx), cx)).astype(np.int64)
    y0 = np.floor(np.minimum(np.minimum(ay, by), cy)).astype(np.int64)
    y1 = np.ceil(np.maximum(np.maximum(ay, by), cy)).astype(np.int64)
    np.clip(x0, 0, size - 1, out=x0); np.clip(x1, 0, size, out=x1)
    np.clip(y0, 0, size - 1, out=y0); np.clip(y1, 0, size, out=y1)

    za, zb, zc = z[idx[:, 0]], z[idx[:, 1]], z[idx[:, 2]]

    for t in tsel:
        if x1[t] <= x0[t] or y1[t] <= y0[t]:
            continue
        xs = np.arange(x0[t], x1[t]) + 0.5
        ys = np.arange(y0[t], y1[t]) + 0.5
        px = xs[None, :]
        py = ys[:, None]
        inv = 1.0 / area[t]
        w0 = ((bx[t] - px) * (cy[t] - py) - (by[t] - py) * (cx[t] - px)) * inv
        w1 = ((cx[t] - px) * (ay[t] - py) - (cy[t] - py) * (ax[t] - px)) * inv
        w2 = 1.0 - w0 - w1
        inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not inside.any():
            continue
        zz = w0 * za[t] + w1 * zb[t] + w2 * zc[t]
        sub = depth[y0[t]:y1[t], x0[t]:x1[t]]
        win = inside & (zz < sub)
        if not win.any():
            continue
        sub[win] = zz[win]
        tri_id[y0[t]:y1[t], x0[t]:x1[t]][win] = t
        if need_bary:
            bw = bary[y0[t]:y1[t], x0[t]:x1[t]]
            bw[win, 0] = w0[win]
            bw[win, 1] = w1[win]
            bw[win, 2] = w2[win]

    out = {"mask": tri_id >= 0, "depth": depth, "tri": tri_id}
    if attrs:
        m = out["mask"]
        ti = tri_id[m]
        w = bary[m]
        for name, a in attrs.items():
            a = np.asarray(a, dtype=np.float64)
            va = a[idx[ti, 0]]
            vb = a[idx[ti, 1]]
            vc = a[idx[ti, 2]]
            buf = np.zeros((size, size, a.shape[1]), dtype=np.float64)
            buf[m] = va * w[:, 0:1] + vb * w[:, 1:2] + vc * w[:, 2:3]
            out[name] = buf
    return out


def silhouette(pos, idx, direction, half_height, size, pivot=(0, 0, 0)):
    """Coverage mask only — no attribute interpolation, both faces kept.

    Backfaces are NOT culled here: a silhouette is the union of what the mesh
    covers, and an open or inconsistently wound mesh (which real assets are)
    would otherwise report holes that a viewer never sees.
    """
    return render(pos, idx, direction, half_height, size, pivot=pivot,
                  backface_cull=False)["mask"]
