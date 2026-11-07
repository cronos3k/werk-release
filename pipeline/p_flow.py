#!/usr/bin/env python3
"""p_flow.py — core.field.flow, the WKFF binary: an SDF plus a flow response.

The SDF is exact: unsigned distance from each cell centre to the nearest point
of the nearest triangle (the full seven-region point-triangle test, not a plane
projection), signed by even-odd ray parity along +X. Parity rather than a
normal lookup because real assets are not reliably wound, and a sign that flips
per triangle is worse than no field at all. When the mesh is not closed the
parity sign is meaningless and the node says so instead of shipping a
plausible-looking field.

The FLOW half is a steady incompressible POTENTIAL-FLOW solve: Laplace's
equation for a velocity potential on the cells outside the solid, with the free
stream imposed at the grid boundary and a no-penetration condition at the
obstacle, relaxed by Gauss-Seidel until the residual stops moving; the stored
vector is the gradient of that potential, divided by the free-stream speed, so
1.0 is undisturbed and 0.0 is stagnant. That model has no viscosity, so it has
no wake and no separation: it is right in front of a body and optimistic
behind one. That limitation is in the node's work note, because a flow field
that quietly pretends to have a wake is the kind of derived data law 5 exists
to distrust.
"""

import numpy as np

from .common import write_envelope
from . import meshops as M


def solve_potential(solid, cell, iters=400, tol=1e-6):
    """Gauss-Seidel (red-black Jacobi) relaxation of Laplace's equation.

    phi is stored on the same grid as the SDF, shape (nz,ny,nx). The free
    stream runs along +X, so the analytic undisturbed solution is phi = x and
    the boundary condition at the grid's x faces is exactly that. On the solid
    the potential is mirrored from its fluid neighbours, which is the discrete
    form of dphi/dn = 0.
    """
    nz, ny, nx = solid.shape
    x = (np.arange(nx) * cell)[None, None, :]
    phi = np.broadcast_to(x, solid.shape).astype(np.float64).copy()
    fluid = ~solid
    residual = None
    for it in range(iters):
        nb = np.zeros_like(phi)
        cnt = np.zeros_like(phi)
        for axis, shift in ((2, 1), (2, -1), (1, 1), (1, -1), (0, 1), (0, -1)):
            r = np.roll(phi, shift, axis=axis)
            m = np.roll(fluid, shift, axis=axis)
            if axis == 2:
                # x neighbours off the edge take the free-stream value
                if shift == 1:
                    r[:, :, 0] = phi[:, :, 0] - cell
                    m[:, :, 0] = True
                else:
                    r[:, :, -1] = phi[:, :, -1] + cell
                    m[:, :, -1] = True
            else:
                sl = [slice(None)] * 3
                sl[axis] = 0 if shift == 1 else -1
                r[tuple(sl)] = phi[tuple(sl)]
                m[tuple(sl)] = True
            nb += np.where(m, r, 0.0)
            cnt += m.astype(np.float64)
        new = np.where(cnt > 0, nb / np.maximum(cnt, 1.0), phi)
        new = np.where(fluid, new, phi)
        # hold the inflow/outflow faces at the analytic free stream
        new[:, :, 0] = x[0, 0, 0]
        new[:, :, -1] = x[0, 0, -1]
        residual = float(np.abs(new - phi).max())
        phi = new
        if residual < tol * cell:
            break
    return phi, it + 1, residual


def run(ctx, mesh, bounds, grid=32, margin=0.35, iters=400):
    pos, idx = mesh["pos"], mesh["idx"]
    lo = bounds["aabb_min"]
    hi = bounds["aabb_max"]
    ext = hi - lo
    longest = float(ext.max())
    cell = longest * (1.0 + 2 * margin) / (grid - 1)
    origin = lo - ext.max() * margin
    dims = [max(2, int(np.ceil((ext[k] + 2 * margin * longest) / cell)) + 1)
            for k in range(3)]
    nx, ny, nz = dims
    if nx * ny * nz > 1 << 26:
        raise ValueError("grid %s exceeds the profile's 2^26 cell ceiling" % dims)

    sdf = M.sdf_grid(pos, idx, origin, cell, dims)          # (nz,ny,nx)
    watertight = bool(bounds["watertight"])
    solid = sdf < 0
    if solid.any():
        phi, its, res = solve_potential(solid, cell, iters=iters)
        gz, gy, gx = np.gradient(phi, cell)
        flow = np.stack([gx, gy, gz], axis=-1)
        flow[solid] = 0.0
        speed = np.linalg.norm(flow, axis=-1)
        flow_note = ("potential-flow Gauss-Seidel, %d iterations, final residual "
                     "%.3e m; peak speed ratio %.3f" % (its, res, float(speed.max())))
    else:
        flow = np.zeros(sdf.shape + (3,), dtype=np.float64)
        flow[..., 0] = 1.0
        flow_note = ("no cell fell inside the surface at this resolution, so the "
                     "field is the undisturbed free stream everywhere")

    assert np.isfinite(sdf).all() and np.isfinite(flow).all()

    header = {
        "dims": [int(nx), int(ny), int(nz)],
        "cell_size_m": float(cell),
        "origin_m": [float(v) for v in origin],
        "sdf_sign": "negative-inside",
        "flow_free_stream": [1.0, 0.0, 0.0],
        "flow_reynolds": 0.0,
        "sdf_range_m": [float(sdf.min()), float(sdf.max())],
        "note": flow_note,
        "producer": {"tool": "pipeline/p_flow.py", "version": "0.1"},
        "epistemic": "measured",
    }
    blob = write_envelope("WKFF", "core.field.flow", header, [
        ("sdf", "f32", [nz, ny, nx], 4,
         np.ascontiguousarray(sdf, dtype="<f4").tobytes()),
        ("flow", "f32", [nz, ny, nx, 3], 12,
         np.ascontiguousarray(flow, dtype="<f4").tobytes()),
    ])
    f = ctx.put("fields/flow.wkff", blob)
    ctx.node("flow", "core.field.flow",
             ctx.version([f],
                         "%dx%dx%d cubic cells of %.5f m. SDF exact "
                         "point-to-triangle, signed by +X ray parity%s. %d of "
                         "%d cells came out inside. Flow is "
                         "an inviscid potential-flow solve: %s. It therefore has "
                         "NO wake and NO separation - it is right upstream of "
                         "the body and optimistic downstream, and a consumer "
                         "using it for drag will underestimate."
                         % (nx, ny, nz, cell,
                            "" if watertight else
                            " (the mesh is NOT closed, so parity is the best "
                            "available sign and not a guaranteed one: a cell "
                            "behind an open boundary can come out on the wrong "
                            "side, and a consumer that needs a certified sign "
                            "must not use this field)",
                            int(solid.sum()), solid.size,
                            flow_note),
                         "measured", inputs=["geometry/game.glb"],
                         params={"grid": int(grid), "margin": margin,
                                 "iterations": int(iters)}),
             edges=[{"to": "geom-game", "kind": "enhances", "role": "samples"}],
             part="whole")
    ctx.layouts["core.field.flow"] = "spec/layouts/flowfield.layout.txt"
    return {"dims": (nx, ny, nz), "cell": cell, "bytes": len(blob),
            "inside_cells": int(solid.sum()), "note": flow_note}
