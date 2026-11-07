#!/usr/bin/env python3
"""vhacd.py — the pipeline's bridge to the real V-HACD.

`tools/vhacd/` carries upstream V-HACD v4.1 (one header, unmodified, licence
and sha256 in the README there) behind a binary-in / binary-out CLI. This
module writes the mesh, runs the child process and parses the hulls back.

It is deliberately a subprocess, not a DLL: a decomposition that asserts on a
hostile mesh takes the child down and returns an exit code, instead of taking
the pipeline down with it.

Nothing here is required. `available()` says whether the binary is there, and
`p_collider` falls back to `voxel-hacd-lite/0.1` when it is not — recording in
`fit.engine` which one actually ran, never assuming.
"""

import os
import struct
import subprocess
import tempfile

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BUILD = os.path.join(_ROOT, "tools", "_build")

FILL_FLOOD, FILL_SURFACE, FILL_RAYCAST = 0, 1, 2

# The version the vendored header declares. Read from the header rather than
# typed in, so bumping the vendored copy cannot leave a stale string in a
# package's provenance.
def _header_version():
    h = os.path.join(_ROOT, "tools", "vhacd", "VHACD.h")
    major = minor = None
    try:
        with open(h, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if "VHACD_VERSION_MAJOR" in line and "define" in line:
                    major = line.split()[-1]
                elif "VHACD_VERSION_MINOR" in line and "define" in line:
                    minor = line.split()[-1]
                if major and minor:
                    break
    except OSError:
        return None
    if major and minor:
        return "%s.%s" % (major, minor)
    return None


def binary_path():
    env = os.environ.get("WERK_VHACD_BIN")
    if env and os.path.exists(env):
        return env
    for name in ("werk_vhacd.exe", "werk_vhacd"):
        p = os.path.join(_BUILD, name)
        if os.path.exists(p):
            return p
    return None


def available():
    p = binary_path()
    if not p:
        return False, ("no V-HACD binary; build it with "
                       "`python tools/build_native.py vhacd`")
    v = _header_version()
    return True, "vhacd/%s" % (v or "4.x")


def engine_id():
    ok, s = available()
    return s if ok else None


def decompose(pos, idx, max_hulls=16, resolution=400000, max_verts_per_hull=64,
              fill_mode=FILL_FLOOD, max_recursion_depth=10,
              min_volume_percent_error=1.0, find_best_plane=False, timeout=900,
              workdir=None):
    """Run V-HACD. Returns (hulls, info) or raises RuntimeError.

    hulls: list of dicts {points (n,3) float64, faces (m,3) int64,
                          volume float, center (3,)}
    info:  {"engine", "returncode", "stdout", "params"}
    """
    exe = binary_path()
    if not exe:
        raise RuntimeError("V-HACD binary not built")

    pos = np.ascontiguousarray(pos, dtype=np.float64)
    idx = np.ascontiguousarray(idx, dtype=np.uint32)
    params = {"max_hulls": int(max_hulls), "resolution": int(resolution),
              "max_verts_per_hull": int(max_verts_per_hull),
              "fill_mode": int(fill_mode),
              "max_recursion_depth": int(max_recursion_depth),
              "min_volume_percent_error": float(min_volume_percent_error),
              "find_best_plane": bool(find_best_plane)}

    # Scratch stays in the build tree, never a user-profile temp.
    workdir = workdir or os.path.join(_BUILD, "tmp")
    os.makedirs(workdir, exist_ok=True)
    fd_in, p_in = tempfile.mkstemp(suffix=".vhacd-in", dir=workdir)
    os.close(fd_in)
    fd_out, p_out = tempfile.mkstemp(suffix=".vhacd-out", dir=workdir)
    os.close(fd_out)
    try:
        with open(p_in, "wb") as f:
            f.write(b"WKVH")
            f.write(struct.pack("<8I", len(pos), len(idx), params["max_hulls"],
                                params["resolution"],
                                params["max_verts_per_hull"],
                                params["fill_mode"],
                                params["max_recursion_depth"],
                                1 if params["find_best_plane"] else 0))
            f.write(struct.pack("<d", params["min_volume_percent_error"]))
            f.write(pos.tobytes())
            f.write(idx.tobytes())

        r = subprocess.run([exe, p_in, p_out], capture_output=True, text=True,
                           timeout=timeout)
        if r.returncode != 0:
            raise RuntimeError("V-HACD exited %d: %s" %
                               (r.returncode, (r.stderr or r.stdout).strip()[:400]))

        with open(p_out, "rb") as f:
            blob = f.read()
    finally:
        for p in (p_in, p_out):
            try:
                os.remove(p)
            except OSError:
                pass

    if len(blob) < 8 or blob[:4] != b"WKVO":
        raise RuntimeError("V-HACD wrote no usable output")
    off = 4
    (n,) = struct.unpack_from("<I", blob, off)
    off += 4
    hulls = []
    for _ in range(n):
        np_, nt = struct.unpack_from("<II", blob, off)
        off += 8
        pts = np.frombuffer(blob, dtype="<f8", count=np_ * 3, offset=off).reshape(np_, 3)
        off += np_ * 3 * 8
        tri = np.frombuffer(blob, dtype="<u4", count=nt * 3, offset=off).reshape(nt, 3)
        off += nt * 3 * 4
        vol, cx, cy, cz = struct.unpack_from("<4d", blob, off)
        off += 32
        hulls.append({"points": np.array(pts, dtype=np.float64),
                      "faces": np.array(tri, dtype=np.int64),
                      "volume": float(vol),
                      "center": np.array([cx, cy, cz], dtype=np.float64)})
    if not hulls:
        raise RuntimeError("V-HACD produced zero hulls")
    return hulls, {"engine": engine_id(), "returncode": r.returncode,
                   "stdout": (r.stdout or "").strip(), "params": params}
