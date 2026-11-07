#!/usr/bin/env python3
"""p_bounds.py — core.phys.bounds.

AABB, the TRUE minimal enclosing sphere (Welzl, exact, checked against every
vertex before it is written), surface area, enclosed volume and whether the
mesh is actually closed. The watertight flag is what makes the volume readable:
a volume computed from an open surface is a fiction, and the flag is how a
consumer tells the two apart.
"""

import numpy as np

from .common import jbytes
from . import meshops as M


def watertightness(idx):
    from collections import Counter
    c = Counter()
    for tri in idx:
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            c[(min(int(a), int(b)), max(int(a), int(b)))] += 1
    counts = Counter(c.values())
    closed = all(v == 2 for v in c.values())
    return closed, dict(counts)


def run(ctx, mesh):
    pos, idx = mesh["pos"], mesh["idx"]
    lo = pos.min(axis=0)
    hi = pos.max(axis=0)
    centre, radius = M.welzl(pos)
    d = np.linalg.norm(pos - np.array(centre), axis=1)
    worst = float(d.max() - radius)
    assert worst <= 1e-9, "Welzl sphere misses a vertex by %.3e m" % worst

    fn = M.face_normals(pos, idx)
    area = float(np.linalg.norm(fn, axis=1).sum() * 0.5)
    closed, edge_hist = watertightness(idx)
    mp = M.mass_properties(pos, idx)
    volume = abs(mp["volume"]) if closed else 0.0

    rec = {
        "aabb_min": [float(v) for v in lo],
        "aabb_max": [float(v) for v in hi],
        "sphere_center": [float(v) for v in centre],
        "sphere_radius": float(radius),
        "sphere_method": "welzl-exact",
        "surface_area_m2": area,
        "volume_m3": float(volume),
        "watertight": bool(closed),
        "longest_axis_m": float((hi - lo).max()),
    }
    doc = {"schema_version": 1, "space": "model", "entity": rec,
           "epistemic": "measured",
           "note": "Sphere is Welzl-exact and was checked against every one of "
                   "the %d vertices before it was written; the worst overshoot "
                   "was %.3e m. The mesh is %s, so volume_m3 is %s."
                   % (len(pos), worst,
                      "closed" if closed else "NOT closed",
                      "the real enclosed volume" if closed
                      else "0 rather than a fiction")}
    longest = float((hi - lo).max())
    if longest > 10.0 or longest < 0.02:
        # glTF declares its units to be metres and the manifest pins
        # units_per_meter to 1.0, so this pipeline does NOT rescale: silently
        # "fixing" a source's scale would make every downstream number a
        # different lie. It says so instead, once, loudly, here and in the
        # README, because mass, inertia, cell size and every switch distance
        # inherit it.
        note = ("The source declares a longest axis of %.4f m. glTF units are "
                "metres and the manifest pins units_per_meter to 1.0, so this "
                "is taken at face value and NOTHING is rescaled. If the author "
                "modelled in centimetres, every metric number in this package - "
                "mass, inertia, flow cell size, imposter switch distance - is "
                "off by that same factor, and the fix is to rescale the source, "
                "not to reinterpret this file." % longest)
        doc["note"] += " " + note
        ctx.notes.append("scale: " + note)

    f = ctx.put("physics/bounds.json", jbytes(doc))
    ctx.node("bounds", "core.phys.bounds",
             ctx.version([f], "Axis-aligned box and true minimal sphere, both "
                              "measured from geometry/game.glb.",
                         "measured", inputs=["geometry/game.glb"]),
             edges=[{"to": "geom-game", "kind": "requires", "role": "measures"}],
             part="whole")
    ctx.schemas["core.phys.bounds"] = "spec/schemas/core.phys.bounds.schema.json"
    return {"aabb_min": lo, "aabb_max": hi, "centre": np.array(centre),
            "radius": radius, "area": area, "watertight": closed,
            "volume": volume, "mass_props": mp, "edge_hist": edge_hist}
