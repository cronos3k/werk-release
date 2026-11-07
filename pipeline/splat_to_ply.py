#!/usr/bin/env python3
"""splat_to_ply.py — turn an antimatter15 `.splat` file into an INRIA-convention
Gaussian-splatting PLY.

    python pipeline/splat_to_ply.py IN.splat OUT.ply [--json PLAN.json]

WHY THIS TOOL EXISTS, AND WHY IT TRAVELS INSIDE THE PACKAGES IT MAKES.

werk's splat ingester (`pipeline/p_gsplat.py`) reads PLY, because PLY is what
every 3D-Gaussian-Splatting trainer writes. The web viewers write something
else: a flat 32-byte-per-gaussian record with everything ALREADY ACTIVATED and
the colour and rotation quantised to bytes. A file in that shape is a perfectly
good splat and a completely different set of numbers, and the difference is
four transforms, each of which is invisible when you get it wrong.

    offset  bytes  field                          state in the .splat
    ------  -----  -----------------------------  --------------------------
    0       12     position x,y,z   f32 LE         as-is
    12      12     scale    sx,sy,sz f32 LE        LINEAR (already exp'd)
    24      4      colour   r,g,b,a  u8            r,g,b are 0.5 + C0*f_dc,
                                                   scaled to 0..255 and
                                                   clipped; a is sigmoid
                                                   (opacity) scaled to 0..255
    28      4      rotation q        u8            (128 + 128*q), WXYZ order

The INRIA PLY wants the pre-activation values: `log` scales, `logit` opacity,
raw degree-0 SH coefficients, f32 quaternions. This tool computes those exact
inverses and writes them, so the ingester downstream sees a real splat PLY and
not a special case.

THE ONE PLACE THE INVERSE IS NOT EXACT, stated here rather than discovered
later: `logit(1.0)` is +infinity, and a byte alpha of 255 means exactly 1.0.
ENVELOPE.layout.txt section 6 forbids an infinity anywhere in a core payload,
so alpha is clamped into [0.5/255, 254.5/255] before the logit — half a
quantisation step in from each end, which is where the true value was known to
lie anyway. The clamp is COUNTED and reported, and the count travels into the
package as part of this tool's recorded configuration. A conversion that
silently produced infinities and a conversion that silently clamped them are
both wrong; a conversion that clamps and says how often is right.

Dependencies: numpy, and `pipeline/ply.py` for the writer. Both are pipeline
dependencies and neither travels inside a package as executable code — what
travels is THIS SOURCE, as a `core.tool` node, because a package that carries
the code that made it can be checked instead of believed (SPEC.md section 3.17).
"""

import argparse
import hashlib
import json
import os
import sys

import numpy as np

if __package__ in (None, ""):
    # Standalone. TWO shapes have to work, and the second is the one that
    # matters: this file also travels INSIDE a werk package as a `core.tool`
    # node, extracted flat beside its siblings with no `pipeline` package
    # around it. A tool that could only be imported from the repository it was
    # written in would be a tool node making a promise about another file,
    # which is the exact thing SPEC.md section 3.17 exists to prevent.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        sys.path.insert(
            1, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from pipeline.ply import SH_C0, write_ply_binary
    except ImportError:
        from ply import SH_C0, write_ply_binary
else:
    from .ply import SH_C0, write_ply_binary

TOOL_NAME = "pipeline/splat_to_ply.py"
TOOL_VERSION = "1.0"

#: Half a quantisation step in from each end of the u8 alpha range. See the
#: module docstring: this is the only inexact inverse in the file.
ALPHA_LO = 0.5 / 255.0
ALPHA_HI = 254.5 / 255.0

RECORD_BYTES = 32


def read_splat(path):
    """Decode a .splat into (positions, scales_linear, rgba_u8, quat_wxyz)."""
    raw = np.fromfile(path, dtype=np.uint8)
    if raw.size % RECORD_BYTES != 0:
        raise SystemExit(
            "%s is %d bytes, which is not a whole number of %d-byte records"
            % (path, raw.size, RECORD_BYTES))
    n = raw.size // RECORD_BYTES
    rec = raw.reshape(n, RECORD_BYTES)
    pos = rec[:, 0:12].copy().view("<f4").reshape(n, 3)
    scl = rec[:, 12:24].copy().view("<f4").reshape(n, 3)
    col = rec[:, 24:28].astype(np.float64)
    rot = rec[:, 28:32].astype(np.float64)
    return n, pos, scl, col, rot


def convert(in_path, out_path):
    n, pos, scl, col, rot = read_splat(in_path)

    if not np.isfinite(pos).all() or not np.isfinite(scl).all():
        raise SystemExit("source .splat contains a non-finite position or scale")
    if (scl <= 0).any():
        raise SystemExit("source .splat contains a non-positive scale; log() of "
                         "it is not a number this tool is willing to invent")

    # colour -> the degree-0 SH coefficient. The forward transform the viewer
    # applied was  byte = round(255 * clip(0.5 + C0*f_dc, 0, 1)).
    f_dc = ((col[:, :3] / 255.0) - 0.5) / SH_C0

    # alpha -> logit opacity, with the clamp this file's docstring argues for.
    alpha = col[:, 3] / 255.0
    clamped = int(np.count_nonzero((alpha < ALPHA_LO) | (alpha > ALPHA_HI)))
    alpha = np.clip(alpha, ALPHA_LO, ALPHA_HI)
    opacity = np.log(alpha / (1.0 - alpha))

    # linear scale -> log scale.
    log_scale = np.log(scl.astype(np.float64))

    # byte quaternion -> f32, WXYZ, renormalised, canonical w >= 0 sign
    # (ENVELOPE.layout.txt section 6).
    q = (rot - 128.0) / 128.0
    nrm = np.linalg.norm(q, axis=1)
    degenerate = int(np.count_nonzero(nrm == 0))
    nrm[nrm == 0] = 1.0
    q = q / nrm[:, None]
    q = np.where(q[:, :1] < 0, -q, q)

    cols = [("x", pos[:, 0]), ("y", pos[:, 1]), ("z", pos[:, 2]),
            ("f_dc_0", f_dc[:, 0]), ("f_dc_1", f_dc[:, 1]), ("f_dc_2", f_dc[:, 2]),
            ("opacity", opacity),
            ("scale_0", log_scale[:, 0]), ("scale_1", log_scale[:, 1]),
            ("scale_2", log_scale[:, 2]),
            ("rot_0", q[:, 0]), ("rot_1", q[:, 1]), ("rot_2", q[:, 2]),
            ("rot_3", q[:, 3])]

    comments = [
        "produced by %s %s from a 32-byte-record .splat" % (TOOL_NAME, TOOL_VERSION),
        "scales are natural-log, opacity is logit, rot_* is WXYZ, SH degree 0",
        "alpha was clamped into [%.8f, %.8f] on %d of %d gaussians before the "
        "logit; see the tool source" % (ALPHA_LO, ALPHA_HI, clamped, n),
    ]
    size = write_ply_binary(out_path, n, cols, comments)

    with open(in_path, "rb") as fh:
        in_sha = hashlib.sha256(fh.read()).hexdigest()
    with open(out_path, "rb") as fh:
        out_sha = hashlib.sha256(fh.read()).hexdigest()

    return {
        "tool": TOOL_NAME,
        "tool_version": TOOL_VERSION,
        "input": {"path": os.path.basename(in_path), "sha256": in_sha,
                  "size": os.path.getsize(in_path)},
        "output": {"path": os.path.basename(out_path), "sha256": out_sha,
                   "size": size},
        "count": int(n),
        "sh_degree": 0,
        "quat_order_in": "wxyz",
        "quat_order_out": "wxyz",
        "alpha_clamp": [ALPHA_LO, ALPHA_HI],
        "alpha_clamped_count": clamped,
        "degenerate_quaternions": degenerate,
        "transforms": {
            "scale": "log(linear)",
            "opacity": "logit(clamp(alpha_u8/255))",
            "sh_dc": "((rgb_u8/255) - 0.5) / %.17g" % SH_C0,
            "rotation": "(u8 - 128)/128, renormalised, w>=0",
        },
        "note": ("Every transform here is the exact inverse of what the .splat "
                 "writer applied, except the alpha clamp, which is inexact by "
                 "at most half a quantisation step and is counted above."),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--json", help="write the conversion record here")
    args = ap.parse_args(argv)
    rec = convert(args.input, args.output)
    if args.json:
        with open(args.json, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(rec, fh, indent=2)
            fh.write("\n")
    print(json.dumps(rec, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
