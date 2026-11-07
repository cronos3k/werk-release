#!/usr/bin/env python3
"""p_gsplat.py — core.geom.gsplat, the WKGS binary: ingest a 3D-Gaussian-
Splatting PLY into werk's six declared streams.

    python pipeline/p_gsplat.py IN.ply OUT.wkgs [--quat-order wxyz|xyzw]
                                                [--json PLAN.json]

Normative source: spec/layouts/gsplat.layout.txt. Every transform this module
applies is named there together with its exact inverse, so nothing here is
knowledge a foreign reader needs to have — which is the whole test of whether a
converter belongs in a format's repository or in somebody's private notebook.

WHAT IT DOES, IN ONE PARAGRAPH. It reads the INRIA field convention
(`x y z`, the always-zero `nx ny nz`, `f_dc_*`, `f_rest_*`, `opacity`,
`scale_*`, `rot_*`), applies `exp` to the log scales, `sigmoid` to the logit
opacity, reorders and sign-canonicalises the quaternions, TRANSPOSES the
spherical-harmonic coefficients from the source's channel-major layout to
werk's coefficient-major one, and writes six sections whose offsets and sizes
are declared in the header. It does not resample, decimate, sort, recentre or
rescale — an ingester that quietly improved its input would make `input_hash`
a hash of something nobody has.

THE ONE JUDGEMENT CALL is the quaternion order, which the source does not
declare and half the ecosystem disagrees about. `--quat-order` settles it; with
no flag the order is inferred and BOTH the inference and the statistic it was
based on go into the node's `input_params`, so a weak inference is visible as
one. See gsplat.layout.txt section 6 and finding S12-3.

This module is embedded into the packages it writes as a `core.tool` node
(SPEC.md section 3.17), so a package produced by it carries the code that made
it and a consumer can read the transforms rather than trust this docstring.
"""

import argparse
import json
import os
import sys

import numpy as np

if __package__ in (None, ""):
    # Standalone, in either of two shapes -- from the repository, and from a
    # werk package that carried this file as a `core.tool` node and extracted
    # it flat beside common.py and ply.py. The second is what makes the
    # embedded-tool claim checkable instead of decorative: tests/run_gate_12.py
    # extracts these three files into an empty directory, runs them with
    # nothing from this repository on the path, and compares the result against
    # the payload the package ships.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        sys.path.insert(
            1, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from pipeline.common import write_envelope
        from pipeline.ply import (read_ply, detect_gsplat, gsplat_arrays,
                                  dc_to_linear_rgb)
    except ImportError:
        from common import write_envelope
        from ply import read_ply, detect_gsplat, gsplat_arrays, dc_to_linear_rgb
else:
    from .common import write_envelope
    from .ply import read_ply, detect_gsplat, gsplat_arrays, dc_to_linear_rgb

TOOL = "pipeline/p_gsplat.py"
TOOL_VERSION = "1.0"

MAGIC = "WKGS"
KIND = "core.geom.gsplat"
LAYOUT = "spec/layouts/gsplat.layout.txt"


def build_wkgs(means, scales, rotations, opacities, sh, extra_header=None):
    """The writer. `sh` is [N, K, 3] COEFFICIENT-MAJOR (gsplat.layout.txt §4).

    Every check the layout's section 8 asks a READER to make is made here on
    the way out too, because a writer that emits what its own reader would
    reject is the cheapest bug in the world to prevent and the most expensive
    to find in someone else's renderer.
    """
    means = np.ascontiguousarray(means, dtype="<f4")
    scales = np.ascontiguousarray(scales, dtype="<f4")
    rot = np.ascontiguousarray(rotations, dtype="<f4")
    opac = np.ascontiguousarray(opacities, dtype="<f4").reshape(-1)
    sh = np.ascontiguousarray(sh, dtype="<f4")

    n = len(means)
    k = sh.shape[1] if sh.size or sh.ndim == 3 else 1
    degree = int(round(k ** 0.5)) - 1
    if (degree + 1) ** 2 != k or not 0 <= degree <= 3:
        raise ValueError("sh has %d coefficients, which is not (degree+1)**2 for "
                         "an sh_degree in 0..3" % k)
    for name, arr, want in (("means", means, (n, 3)), ("scales", scales, (n, 3)),
                            ("rotations", rot, (n, 4)), ("sh", sh, (n, k, 3))):
        if arr.shape != want:
            raise ValueError("%s has shape %s, expected %s" % (name, arr.shape, want))
    if opac.shape != (n,):
        raise ValueError("opacities has shape %s, expected (%d,)" % (opac.shape, n))
    for name, arr in (("means", means), ("scales", scales), ("rotations", rot),
                      ("opacities", opac), ("sh", sh)):
        if n and not np.isfinite(arr).all():
            raise ValueError("%s contains NaN or infinity; ENVELOPE.layout.txt "
                             "section 6 forbids either in a core payload" % name)

    header = {
        "count": int(n),
        "sh_degree": int(degree),
        "sh_coeff_count": int(k),
        "sh_coeff_order": "coefficient-major",
        "quat_order": "wxyz",
        "scale_space": "linear",
        "opacity_space": "linear",
        "length_unit": "metre",
    }
    if n:
        header["bounds"] = {
            "min": [float(v) for v in means.min(axis=0)],
            "max": [float(v) for v in means.max(axis=0)],
        }
    header.update(extra_header or {})

    dc = np.ascontiguousarray(sh[:, 0, :], dtype="<f4")
    rest = np.ascontiguousarray(sh[:, 1:, :], dtype="<f4")

    return write_envelope(MAGIC, KIND, header, [
        ("means", "f32", [n, 3], 12, means.tobytes()),
        ("scales", "f32", [n, 3], 12, scales.tobytes()),
        ("rotations", "f32", [n, 4], 16, rot.tobytes()),
        ("opacities", "f32", [n], 4, opac.tobytes()),
        ("sh-dc", "f32", [n, 3], 12, dc.tobytes()),
        ("sh-rest", "f32", [n, k - 1, 3], 12, rest.tobytes()),
    ])


def ingest(ply_path, quat_order=None):
    """PLY -> (blob, stats). `stats` is everything a node's input_params and
    work note need, and it is deliberately a plain dict so a caller can put it
    in a package without this module knowing what a package is."""
    ply = read_ply(ply_path)
    el = ply.element("vertex")
    if el is None:
        raise ValueError("%s has no `vertex` element" % ply_path)
    plan = detect_gsplat(el, quat_order=quat_order)
    means, scales, rot, opac, sh = gsplat_arrays(el, plan)

    dropped_normals = int(all(p in el.names() for p in ("nx", "ny", "nz")))
    zero_normals = None
    if dropped_normals:
        nn = np.stack([np.asarray(el.data[p], dtype=np.float64)
                       for p in ("nx", "ny", "nz")], 1)
        zero_normals = bool(np.all(nn == 0.0))

    extra = {
        "source_convention": "inria-3dgs/1",
        "activation": {"scale": "exp", "opacity": "sigmoid", "sh": "identity"},
        "producer": {"tool": TOOL, "version": TOOL_VERSION},
        "epistemic": "measured",
    }
    n_zero_opacity = int(np.count_nonzero(opac == 0.0))
    n_one_opacity = int(np.count_nonzero(opac == 1.0))
    if n_zero_opacity or n_one_opacity:
        extra["opacity_note"] = (
            "%d of %d opacities are exactly 0.0 and %d exactly 1.0. Those are "
            "LEGAL (gsplat.layout.txt D-GS-5) and they have no logit, so a "
            "consumer converting back into a trainer's parameterisation must "
            "clamp and say so." % (n_zero_opacity, len(opac), n_one_opacity))

    blob = build_wkgs(means, scales, rot, opac, sh, extra)

    rgb = dc_to_linear_rgb(sh[:, 0, :]) if len(means) else np.zeros((0, 3))
    stats = {
        "count": int(len(means)),
        "sh_degree": int(plan.sh_degree),
        "sh_coeff_count": int(plan.sh_coeff_count),
        "quat_order": plan.quat_order,
        "quat_order_evidence": plan.quat_order_evidence,
        # The statistic is recorded whether or not the order was declared, so
        # the field gsplat.layout.txt section 6 asks for is never empty.
        "quat_order_statistic": plan.quat_order_statistic,
        "quat_order_inferred": plan.quat_order_inferred,
        "quat_order_declared": quat_order is not None,
        "source_scale_space": plan.scale_space,
        "source_opacity_space": plan.opacity_space,
        "ply_format": ply.format,
        "ply_properties": len(el.properties),
        "ignored_ply_properties": list(plan.extra_names),
        "normals_present": bool(dropped_normals),
        "normals_all_zero": zero_normals,
        "bytes": len(blob),
        "bytes_per_gaussian": (len(blob) / len(means)) if len(means) else 0.0,
        "opacity_exactly_zero": n_zero_opacity,
        "opacity_exactly_one": n_one_opacity,
        "scale_min_m": float(scales.min()) if len(means) else 0.0,
        "scale_max_m": float(scales.max()) if len(means) else 0.0,
        "scale_median_m": float(np.median(scales)) if len(means) else 0.0,
        "opacity_mean": float(opac.mean()) if len(means) else 0.0,
        "quat_norm_max_dev": (float(np.abs(np.linalg.norm(rot, axis=1) - 1.0).max())
                              if len(means) else 0.0),
        "bounds_min_m": [float(v) for v in means.min(axis=0)] if len(means) else [0, 0, 0],
        "bounds_max_m": [float(v) for v in means.max(axis=0)] if len(means) else [0, 0, 0],
        "dc_rgb_mean": [float(v) for v in rgb.mean(axis=0)] if len(means) else [0, 0, 0],
    }
    return blob, stats, (means, scales, rot, opac, sh)


def run(ctx, ply_path, node_id="gsplat", path="splats/gsplat.wkgs",
        quat_order=None, epistemic="measured", inputs=None, params=None,
        note=None, edges=(), part=None):
    """Producer entry point: ingest and put the node into `ctx`."""
    blob, stats, arrays = ingest(ply_path, quat_order=quat_order)
    f = ctx.put(path, blob)
    p = dict(params or {})
    p.update({
        "source_convention": "inria-3dgs/1",
        "quat_order": stats["quat_order"],
        "quat_order_source": ("declared by the caller" if stats["quat_order_declared"]
                              else stats["quat_order_evidence"]),
        "activation_scale": "exp",
        "activation_opacity": "sigmoid",
        "sh_coeff_order": "coefficient-major (transposed from the source's "
                          "channel-major f_rest_*)",
        "resampled": False,
        "recentred": False,
        "rescaled": False,
    })
    if note is None:
        note = (
            "%d Gaussians ingested from a %s Gaussian-splatting PLY at SH degree "
            "%d. Scales are LINEAR metres (exp of the source's log scales, "
            "%.6f..%.6f m, median %.6f) and opacity is LINEAR alpha (sigmoid of "
            "the source's logit, mean %.4f) — gsplat.layout.txt section 0 argues "
            "why, and section 6 gives the exact inverses. Quaternions are wxyz, "
            "unit to %.2e, w>=0; the source PLY does not declare its component "
            "order and this one was %s. SH is stored coefficient-major, "
            "transposed from the source's channel-major f_rest_*. Nothing was "
            "resampled, recentred or rescaled."
            % (stats["count"], stats["ply_format"], stats["sh_degree"],
               stats["scale_min_m"], stats["scale_max_m"], stats["scale_median_m"],
               stats["opacity_mean"], stats["quat_norm_max_dev"],
               ("declared by the caller as %r" % stats["quat_order"])
               if stats["quat_order_declared"] else stats["quat_order_evidence"]))
        if stats["normals_all_zero"]:
            note += (" The source's nx/ny/nz are all exactly zero — the INRIA "
                     "writer reusing a point-cloud writer — and were DROPPED "
                     "rather than carried as normals a consumer would light with.")
    ctx.node(node_id, KIND,
             ctx.version([f], note, epistemic, inputs=inputs, params=p,
                         tool=TOOL, tver=TOOL_VERSION),
             edges=[dict(e) for e in edges], part=part,
             meta={"gaussian_count": stats["count"],
                   "sh_degree": stats["sh_degree"],
                   "bytes_per_gaussian": round(stats["bytes_per_gaussian"], 3)})
    ctx.layouts[KIND] = LAYOUT
    return stats, arrays


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--quat-order", choices=("wxyz", "xyzw"), default=None)
    ap.add_argument("--json")
    args = ap.parse_args(argv)
    blob, stats, _ = ingest(args.input, quat_order=args.quat_order)
    with open(args.output, "wb") as fh:
        fh.write(blob)
    if args.json:
        with open(args.json, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(stats, fh, indent=2)
            fh.write("\n")
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
