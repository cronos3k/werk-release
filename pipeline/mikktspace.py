#!/usr/bin/env python3
"""mikktspace.py — the pipeline's bridge to the vendored reference MikkTSpace.

The C is in `tools/mikktspace/` (upstream, unmodified, provenance and licence
in the README there) behind one flat-array entry point; this module loads the
built shared library through ctypes and turns its per-face-corner answer into
a mesh the pipeline can write.

Two functions matter:

  available()            -> (bool, str)   is the library loadable, and why not
  tangents_split(...)    -> the real thing: per-corner MikkTSpace tangents,
                            with vertices SPLIT where the corners disagree.

Splitting is what makes this MikkTSpace rather than MikkTSpace-flavoured. The
basis is genuinely discontinuous across a UV chart seam; a mesh with one shared
vertex there cannot carry both answers, so the vertex becomes two. That is what
every engine's MikkTSpace path does and it is why a normal map baked against
MikkTSpace lines up.

Nothing in here is required: if the library is missing, `p_geom` falls back to
the Gram-Schmidt basis and RECORDS that it did.
"""

import ctypes
import os

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BUILD = os.path.join(_ROOT, "tools", "_build")

_lib = None
_why = None


def _candidates():
    env = os.environ.get("WERK_MIKKTSPACE_LIB")
    if env:
        yield env
    for name in ("werk_mikktspace.dll", "libwerk_mikktspace.so",
                 "werk_mikktspace.so", "werk_mikktspace.dylib",
                 "libwerk_mikktspace.dylib"):
        yield os.path.join(_BUILD, name)


def _load():
    global _lib, _why
    if _lib is not None or _why is not None:
        return _lib
    tried = []
    for path in _candidates():
        if not os.path.exists(path):
            tried.append(path)
            continue
        try:
            lib = ctypes.CDLL(path)
        except OSError as e:
            tried.append("%s (%s)" % (path, e))
            continue
        lib.werk_mikktspace.restype = ctypes.c_int
        lib.werk_mikktspace.argtypes = [
            ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float),
            ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_uint32),
            ctypes.c_int, ctypes.POINTER(ctypes.c_float)]
        lib.werk_mikktspace_version.restype = ctypes.c_char_p
        _lib = lib
        return _lib
    _why = ("no MikkTSpace library was loadable; build it with "
            "`python tools/build_native.py mikktspace`. Tried: " +
            ", ".join(tried))
    return None


def available():
    lib = _load()
    return (True, version()) if lib else (False, _why)


def version():
    lib = _load()
    if not lib:
        return None
    return lib.werk_mikktspace_version().decode("ascii")


def corner_tangents(pos, nrm, uv, idx):
    """Per-face-corner tangents from the reference implementation.

    Returns an (ntri, 3, 4) float64 array, or None if the library refused the
    mesh (which genTangSpaceDefault does for a mesh it cannot handle at all).
    """
    lib = _load()
    if lib is None:
        return None
    ntri = int(len(idx))
    p = np.ascontiguousarray(pos, dtype=np.float32)
    n = np.ascontiguousarray(nrm, dtype=np.float32)
    t = np.ascontiguousarray(uv, dtype=np.float32)
    i = np.ascontiguousarray(idx, dtype=np.uint32).reshape(-1)
    out = np.zeros(ntri * 12, dtype=np.float32)
    ok = lib.werk_mikktspace(
        p.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        n.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        t.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        i.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32)),
        ctypes.c_int(ntri),
        out.ctypes.data_as(ctypes.POINTER(ctypes.c_float)))
    if not ok:
        return None
    return out.astype(np.float64).reshape(ntri, 3, 4)


def tangents_split(pos, nrm, uv, idx, extra=(), tol=1e-4):
    """Run MikkTSpace and split vertices whose corners disagree.

    `extra` is a tuple of per-vertex arrays (colour, whatever) carried along.

    Returns a dict, or None if the library was unavailable/refused:
      pos, nrm, uv, idx, tan (n,4), extra (list), splits, degenerate, source

    The RETURNED index buffer addresses the split vertex set. Positions are
    duplicated, never moved, so the surface is bit-identical to the input —
    only the vertex count changes.
    """
    corners = corner_tangents(pos, nrm, uv, idx)
    if corners is None:
        return None

    nv = len(pos)
    ntri = len(idx)
    flat_v = np.asarray(idx, dtype=np.int64).reshape(-1)          # 3*ntri
    flat_t = corners.reshape(-1, 4)                                # 3*ntri x 4

    # Group corners by the vertex they address and give each DISTINCT tangent
    # its own copy of that vertex. Quantising to `tol` before grouping means
    # two corners that agree to float precision do not split a vertex over a
    # last-bit difference.
    q = np.round(flat_t / tol).astype(np.int64)
    order = np.lexsort((q[:, 3], q[:, 2], q[:, 1], q[:, 0], flat_v))
    sv = flat_v[order]
    sq = q[order]
    new = np.empty(len(order), dtype=np.int64)

    boundary = np.ones(len(order), dtype=bool)
    boundary[1:] = (sv[1:] != sv[:-1]) | np.any(sq[1:] != sq[:-1], axis=1)
    group = np.cumsum(boundary) - 1
    new[order] = group
    ngroups = int(group[-1]) + 1 if len(group) else 0

    # representative corner (and source vertex) for each group
    rep = np.zeros(ngroups, dtype=np.int64)
    rep[group] = order            # last wins; any member is equivalent by
    src = flat_v[rep]             # construction, they are the same vertex+tan

    out_tan = np.array(flat_t[rep])
    nrm_out = np.asarray(nrm)[src]

    # MikkTSpace's degenerate epilogue hands back a small number of EXACTLY
    # zero tangents (measured: 12 corners of 19 728 on the crate, 18 of 16 182
    # on the lantern) and, very rarely, one that is not orthogonal to the
    # normal it was given. A zero tangent is a NaN waiting to happen in a
    # shader, so those specific vertices get the same declared-arbitrary basis
    # the Gram-Schmidt path uses — any vector orthogonal to the normal. Every
    # other vertex keeps MikkTSpace's answer bit for bit, and the count of
    # repaired ones is reported rather than swept up.
    ln = np.linalg.norm(out_tan[:, :3], axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        unit = out_tan[:, :3] / np.maximum(ln[:, None], 1e-30)
    off_normal = np.abs(np.einsum("ij,ij->i", unit, nrm_out))
    broken = (ln < 1e-12) | ~np.isfinite(ln) | (off_normal > 1e-3)
    degenerate = int(broken.sum())
    if degenerate:
        n_b = nrm_out[broken]
        alt = np.tile(np.array([1.0, 0.0, 0.0]), (degenerate, 1))
        alt[np.abs(n_b[:, 0]) > 0.9] = np.array([0.0, 0.0, 1.0])
        alt = alt - n_b * np.sum(alt * n_b, axis=1, keepdims=True)
        alt = alt / np.maximum(np.linalg.norm(alt, axis=1, keepdims=True), 1e-30)
        unit[broken] = alt
        w = out_tan[broken, 3]
        out_tan[broken, 3] = np.where(w == 0.0, 1.0, w)
    out_tan[:, :3] = unit

    res = {
        "pos": np.asarray(pos)[src],
        "nrm": nrm_out,
        "uv": np.asarray(uv)[src],
        "idx": new.reshape(ntri, 3).astype(np.int64),
        "tan": out_tan,
        "extra": [np.asarray(a)[src] for a in extra],
        "splits": int(ngroups - nv),
        "vertex_count": int(ngroups),
        "degenerate": degenerate,
        "source_vertex": src,
        "engine": version() or "mikktspace/1.0",
    }
    return res
