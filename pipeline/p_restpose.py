#!/usr/bin/env python3
"""p_restpose.py — core.pose.rest, the WKRP binary: where this thing lands.

WHAT THE SIMULATION ACTUALLY IS, stated plainly because the layout file says
"measured, not guessed" and a reader deserves to know what was measured.

This is a QUASI-STATIC rigid-body settle, not a time-stepped dynamics run. For
each trial the entity is given a uniformly random orientation, dropped onto a
level rigid floor, and allowed to tip: the face of its convex hull that first
touches the floor is found, and while the centre of mass does not project
inside that face's polygon the body rotates over the support edge nearest the
projection and lands on the neighbouring face. That loop is the physics -- it
is what a dynamics engine converges to once the kinetic energy is gone, and it
reaches the answer without a timestep, a restitution coefficient or a friction
model to get wrong.

What it therefore does NOT model: bouncing, sliding, a body that comes to rest
on a non-hull feature (a bowl landing inside its own rim), and any pose that
depends on deformation. Those are named in the node's note rather than left for
someone to discover. `trials` is the real number of random drops and
`probability` is the real fraction that settled on each face, so a consumer can
tell a 3 %% pose from a 40 %% one.
"""

import math

import numpy as np

from .common import write_envelope
from . import meshops as M

TARGET_POSES = 32


def _merge_faces(pts, simplices, tol=1e-6):
    """Group coplanar hull triangles into polygon faces."""
    n = M.face_normals(pts, simplices)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    keep = ln[:, 0] > 1e-14
    n = n / np.maximum(ln, 1e-30)
    d = np.sum(n * pts[simplices[:, 0]], axis=1)
    faces = []
    used = np.zeros(len(simplices), dtype=bool)
    for i in range(len(simplices)):
        if used[i] or not keep[i]:
            continue
        same = (~used) & keep & (np.abs(np.sum(n * n[i], axis=1) - 1.0) < tol) & \
               (np.abs(d - d[i]) < 1e-6 * max(1.0, abs(d[i])))
        used |= same
        verts = np.unique(simplices[same].reshape(-1))
        faces.append({"normal": n[i], "offset": float(d[i]), "verts": verts,
                      "tris": np.nonzero(same)[0]})
    return faces


def _polygon_order(pts, verts, normal):
    c = pts[verts].mean(axis=0)
    u = pts[verts[0]] - c
    if np.linalg.norm(u) < 1e-12:
        u = np.array([1.0, 0.0, 0.0])
    u = u - normal * float(u @ normal)
    u /= max(np.linalg.norm(u), 1e-30)
    v = np.cross(normal, u)
    rel = pts[verts] - c
    ang = np.arctan2(rel @ v, rel @ u)
    return verts[np.argsort(ang)]


def _inside_polygon(p, poly, normal):
    """2D point-in-convex-polygon in the face's own plane."""
    u = poly[1] - poly[0]
    u = u - normal * float(u @ normal)
    nu = np.linalg.norm(u)
    if nu < 1e-14:
        return False, None
    u /= nu
    v = np.cross(normal, u)
    P = np.array([float((p - poly[0]) @ u), float((p - poly[0]) @ v)])
    Q = np.stack([(poly - poly[0]) @ u, (poly - poly[0]) @ v], axis=1)
    n = len(Q)
    inside = True
    worst_edge, worst_d = None, -np.inf
    for i in range(n):
        a, b = Q[i], Q[(i + 1) % n]
        e = b - a
        # outward normal of this edge in the face plane (polygon is CCW about
        # `normal`, so the outward side is +90 degrees from the edge)
        no = np.array([e[1], -e[0]])
        ln = np.linalg.norm(no)
        if ln < 1e-14:
            continue
        no /= ln
        dist = float((P - a) @ no)
        if dist > 1e-12:
            inside = False
        if dist > worst_d:
            worst_d, worst_edge = dist, i
    return inside, worst_edge


def _quat_align(a, b):
    """Unit quaternion (w,x,y,z) rotating unit vector a onto unit vector b."""
    a = a / max(np.linalg.norm(a), 1e-30)
    b = b / max(np.linalg.norm(b), 1e-30)
    d = float(a @ b)
    if d > 1 - 1e-12:
        return np.array([1.0, 0.0, 0.0, 0.0])
    if d < -1 + 1e-12:
        axis = np.cross(a, np.array([1.0, 0.0, 0.0]))
        if np.linalg.norm(axis) < 1e-8:
            axis = np.cross(a, np.array([0.0, 1.0, 0.0]))
        axis /= np.linalg.norm(axis)
        return np.array([0.0, axis[0], axis[1], axis[2]])
    axis = np.cross(a, b)
    q = np.array([1.0 + d, axis[0], axis[1], axis[2]])
    q /= np.linalg.norm(q)
    if q[0] < 0:
        q = -q
    return q


def _rotate(q, v):
    w, x, y, z = q
    R = np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    return v @ R.T


def run(ctx, mesh, bounds, body, trials=512, up=(0.0, 1.0, 0.0), seed=20260808):
    pos, idx = mesh["pos"], mesh["idx"]
    hp, hs = M.convex_hull(pos)
    faces = _merge_faces(hp, hs)
    if not faces:
        raise ValueError("the convex hull produced no faces")
    com = np.asarray(body["com"], dtype=np.float64)
    up = np.asarray(up, dtype=np.float64)

    polys = []
    for f in faces:
        order = _polygon_order(hp, f["verts"], f["normal"])
        polys.append({"normal": f["normal"], "poly": hp[order], "verts": order})

    # adjacency: which face shares each edge
    edge_face = {}
    for fi, f in enumerate(faces):
        order = polys[fi]["verts"]
        n = len(order)
        for i in range(n):
            a, b = int(order[i]), int(order[(i + 1) % n])
            edge_face.setdefault((min(a, b), max(a, b)), []).append(fi)

    def stable(fi):
        p = polys[fi]
        # project the CoM onto the face plane along the face normal
        d = float((com - p["poly"][0]) @ p["normal"])
        proj = com - p["normal"] * d
        ins, edge = _inside_polygon(proj, p["poly"], p["normal"])
        return ins, edge

    def settle(fi, guard=64):
        seen = set()
        for _ in range(guard):
            ins, edge = stable(fi)
            if ins:
                return fi
            if fi in seen:
                return fi              # limit cycle: this face is the answer
            seen.add(fi)
            order = polys[fi]["verts"]
            n = len(order)
            a, b = int(order[edge]), int(order[(edge + 1) % n])
            nb = [g for g in edge_face.get((min(a, b), max(a, b)), []) if g != fi]
            if not nb:
                return fi
            fi = nb[0]
        return fi

    rng = np.random.RandomState(seed)
    hits = np.zeros(len(faces), dtype=np.int64)
    for _ in range(trials):
        # uniform random rotation (Shoemake), applied to the DOWN direction:
        # the face that touches the floor is the hull's support face in the
        # rotated down direction, so only the direction needs rotating.
        u1, u2, u3 = rng.rand(3)
        q = np.array([math.sqrt(u1) * math.cos(2 * math.pi * u3),
                      math.sqrt(1 - u1) * math.sin(2 * math.pi * u2),
                      math.sqrt(1 - u1) * math.cos(2 * math.pi * u2),
                      math.sqrt(u1) * math.sin(2 * math.pi * u3)])
        down = _rotate(np.array([q[0], -q[1], -q[2], -q[3]]), -up)
        dots = np.array([float(p["normal"] @ down) for p in polys])
        hits[settle(int(np.argmax(dots)))] += 1

    order = np.argsort(-hits)
    order = [int(i) for i in order if hits[i] > 0][:TARGET_POSES]
    if not order:
        raise ValueError("no trial settled")

    pose_bytes = bytearray()
    contact_bytes = bytearray()
    contact_first = 0
    summary = []
    for fi in order:
        p = polys[fi]
        q = _quat_align(p["normal"], -up)
        pts = p["poly"]
        # support area: the polygon's own area, which IS the convex hull of the
        # contact points projected onto the floor plane (the face is planar and
        # the rotation puts it in the floor plane exactly).
        area = 0.0
        if len(pts) >= 3:
            c = pts.mean(axis=0)
            for i in range(len(pts)):
                a2 = pts[i] - c
                b2 = pts[(i + 1) % len(pts)] - c
                area += 0.5 * float(np.linalg.norm(np.cross(a2, b2)))
        prob = float(hits[fi]) / float(trials)
        pose_bytes += np.array(q, dtype="<f4").tobytes()
        pose_bytes += np.array([contact_first, len(pts)], dtype="<u4").tobytes()
        pose_bytes += np.array([prob, area], dtype="<f4").tobytes()
        contact_bytes += np.ascontiguousarray(pts, dtype="<f4").tobytes()
        contact_first += len(pts)
        summary.append({"face": fi, "probability": prob, "contacts": len(pts),
                        "support_area_m2": area})

    total_prob = sum(s["probability"] for s in summary)
    header = {
        "pose_count": len(order),
        "contact_count": contact_first,
        "trials": int(trials),
        "floor_normal": [float(v) for v in up],
        "settle_epsilon_m": 1e-9,
        "merge_angle_deg": 0.0,
        "note": "Quasi-static settle over the convex hull; see the node's work "
                "note. probability sums to %.6f because %d of %d trials settled "
                "onto a face outside the top %d."
                % (total_prob, trials - int(round(total_prob * trials)), trials,
                   TARGET_POSES),
        "producer": {"tool": "pipeline/p_restpose.py", "version": "0.1"},
        "epistemic": "measured",
    }
    blob = write_envelope("WKRP", "core.pose.rest", header, [
        ("poses", "record", [len(order)], 32, bytes(pose_bytes)),
        ("contacts", "f32", [contact_first, 3], 12, bytes(contact_bytes)),
    ])
    f = ctx.put("physics/restposes.wkrp", blob)
    ctx.node("restposes", "core.pose.rest",
             ctx.version([f],
                         "%d settled orientations from %d random drops, "
                         "quasi-static over the convex hull (%d faces). The most "
                         "likely pose takes %.1f%% of trials. NOT modelled: "
                         "bouncing, sliding, resting on a non-hull feature such "
                         "as the inside of a bowl, and anything deformable - "
                         "each of those would need a time-stepped solver and "
                         "this is not one."
                         % (len(order), trials, len(faces),
                            100.0 * summary[0]["probability"]),
                         "measured", inputs=["geometry/game.glb", "physics/body.json"],
                         params={"trials": int(trials), "seed": int(seed),
                                 "method": "quasi-static-hull-settle/0.1"}),
             edges=[{"to": "geom-game", "kind": "requires", "role": "settles"},
                    {"to": "body", "kind": "requires", "role": "centre-of-mass"}],
             part="whole")
    ctx.layouts["core.pose.rest"] = "spec/layouts/restposes.layout.txt"
    return {"poses": len(order), "trials": trials, "top": summary[0],
            "hull_faces": len(faces), "coverage": total_prob}
