# REPORT: gsplat-v1.werk analysis

## Task 1: List contents, meanings, verify integrity

**Succeeded:** yes

Container: werk v1.0, profile 3d-entity/1
Entity: plush (5b052490-f871-4336-9d9c-19a3fb076796)
Summary: A real 3D Gaussian splat, its exact point-cloud degradation, and the source code of the three tools that made them.

### Nodes and their files

- **spec** [core.spec]: The format specification, its schemas and its binary layout grammars, travelling inside the file they describe (law 2).
  - `spec/MINI-SPECS.md` (40147 B)
  - `spec/PROFILE-IMAGE.md` (13274 B)
  - `spec/README.md` (10855 B)
  - `spec/SPEC.md` (104388 B)
  - `spec/X-C2PA-EXPORT.md` (7461 B)
  - `spec/conventions-map.image.json` (2416 B)
  - `spec/conventions-map.json` (9269 B)
  - `spec/examples/MANIFEST.example.json` (20080 B)
  - `spec/examples/SIGNATURE.example.json` (1084 B)
  - `spec/examples/embedding.example.hex.txt` (4444 B)
  - `spec/examples/embedding.example.wkem` (512 B)
  - `spec/examples/gsplat.example.hex.txt` (9796 B)
  - `spec/examples/gsplat.example.wkgs` (1120 B)
  - `spec/examples/make-examples.py` (57655 B)
  - `spec/examples/restposes.example.hex.txt` (4308 B)
  - `spec/examples/restposes.example.wkrp` (560 B)
  - `spec/examples/signature.example.txt` (4544 B)
  - `spec/extensions/x.cub.v1.baked.layout.txt` (9359 B)
  - `spec/extensions/x.cub.v1.md` (8783 B)
  - `spec/facets.json` (11978 B)
  - `spec/layouts/ENVELOPE.layout.txt` (26372 B)
  - `spec/layouts/animclip.layout.txt` (16800 B)
  - `spec/layouts/embedding.layout.txt` (14361 B)
  - `spec/layouts/flowfield.layout.txt` (6263 B)
  - `spec/layouts/gsplat.layout.txt` (23918 B)
  - `spec/layouts/imposter.layout.txt` (10446 B)
  - `spec/layouts/points.layout.txt` (16663 B)
  - `spec/layouts/restposes.layout.txt` (5958 B)
  - `spec/layouts/skeleton.layout.txt` (5964 B)
  - `spec/schemas/conventions-map.schema.json` (4614 B)
  - `spec/schemas/core.anim.clip.schema.json` (9585 B)
  - `spec/schemas/core.audio.effect.schema.json` (8628 B)
  - `spec/schemas/core.audio.package.schema.json` (7320 B)
  - `spec/schemas/core.destruct.schema.json` (6319 B)
  - `spec/schemas/core.disclosure.schema.json` (11515 B)
  - `spec/schemas/core.imposter.schema.json` (6708 B)
  - `spec/schemas/core.material.schema.json` (4823 B)
  - `spec/schemas/core.phys.body.schema.json` (6157 B)
  - `spec/schemas/core.phys.bounds.schema.json` (3164 B)
  - `spec/schemas/core.phys.colliders.schema.json` (4116 B)
  - `spec/schemas/core.props.schema.json` (11666 B)
  - `spec/schemas/core.provenance.schema.json` (6140 B)
  - `spec/schemas/core.recipe.schema.json` (26485 B)
  - `spec/schemas/core.retarget.bind.schema.json` (13337 B)
  - `spec/schemas/core.semantics.schema.json` (6917 B)
  - `spec/schemas/core.skeleton.schema.json` (11464 B)
  - `spec/schemas/core.tool.config.schema.json` (7321 B)
  - `spec/schemas/core.tool.schema.json` (10894 B)
  - `spec/schemas/facets.schema.json` (3593 B)
  - `spec/schemas/manifest.image.schema.json` (28278 B)
  - `spec/schemas/manifest.schema.json` (46174 B)
  - `spec/schemas/signature.schema.json` (11209 B)
  - `spec/schemas/x.c2pa.export.schema.json` (4935 B)
  - `spec/skeleton/canonical-humanoid-v1.json` (22429 B)
  - `spec/skeleton/core.hands.v1.json` (26112 B)
  - `spec/skeleton/derive-canonical-humanoid.py` (19852 B)
- **loader-python** [core.loader]: A single-file, dependency-free reader for this package, carried as payload so the file brings its own reader (law 1).
  - `loaders/werk_read.py` (42226 B)
- **loader-rust** [core.loader]: A single-file, dependency-free reader for this package, carried as payload so the file brings its own reader (law 1).
  - `loaders/werk_read.rs` (98761 B)
- **loader-c** [core.loader]: A single-file, dependency-free reader for this package, carried as payload so the file brings its own reader (law 1).
  - `loaders/werk_read.c` (111051 B)
- **license** [core.license]: The full licence text, embedded, never a link (law 7) -- including the part where the splat's own terms are NOT established and the package says so instead of guessing.
  - `LICENSE` (2859 B)
- **tool-splat-to-ply** [core.tool]: The converter that changed this content's representation, carried as SOURCE so a reader can check what it did instead of believing a producer string (SPEC.md section 3.17). 2 file(s), entrypoint tools/splat-to-ply/splat_to_ply.py. Reading it is the point; nothing in this package is ever executed automatically.
  - `tools/splat-to-ply/tool.json` (1818 B)
  - `tools/splat-to-ply/splat_to_ply.py` (8353 B)
  - `tools/splat-to-ply/ply.py` (21847 B)
- **tool-werk-gsplat** [core.tool]: The converter that changed this content's representation, carried as SOURCE so a reader can check what it did instead of believing a producer string (SPEC.md section 3.17). 3 file(s), entrypoint tools/werk-gsplat/p_gsplat.py. Reading it is the point; nothing in this package is ever executed automatically.
  - `tools/werk-gsplat/tool.json` (1936 B)
  - `tools/werk-gsplat/p_gsplat.py` (12942 B)
  - `tools/werk-gsplat/ply.py` (21847 B)
  - `tools/werk-gsplat/common.py` (16849 B)
- **tool-werk-pointcloud** [core.tool]: The processor that derived something in this package, carried as SOURCE so a reader can check what it did instead of believing a producer string (SPEC.md section 3.17). 3 file(s), entrypoint tools/werk-pointcloud/p_pointcloud.py. Reading it is the point; nothing in this package is ever executed automatically.
  - `tools/werk-pointcloud/tool.json` (1692 B)
  - `tools/werk-pointcloud/p_pointcloud.py` (13791 B)
  - `tools/werk-pointcloud/ply.py` (21847 B)
  - `tools/werk-pointcloud/common.py` (16849 B)
- **tool-config-splat-to-ply-run** [core.tool.config]: The exact settings tool-splat-to-ply ran with for this package: 8 parameter(s), provenance 'recorded'. The keys are the tool's own and werk does not rename them.
  - `tools/splat-to-ply-run.config.json` (2007 B)
- **tool-config-werk-gsplat-run** [core.tool.config]: The exact settings tool-werk-gsplat ran with for this package: 10 parameter(s), provenance 'recorded'. The keys are the tool's own and werk does not rename them.
  - `tools/werk-gsplat-run.config.json` (1824 B)
- **tool-config-werk-pointcloud-run** [core.tool.config]: The exact settings tool-werk-pointcloud ran with for this package: 8 parameter(s), provenance 'recorded'. The keys are the tool's own and werk does not rename them.
  - `tools/werk-pointcloud-run.config.json` (1547 B)
- **gsplat** [core.geom.gsplat]: 281498 Gaussians ingested from a binary_little_endian Gaussian-splatting PLY at SH degree 0. Scales are LINEAR metres (exp of the source's log scales, 0.000000..0.244545 m, median 0.001623) and opacity is LINEAR alpha (sigmoid of the source's logit, mean 0.4647) — gsplat.layout.txt section 0 argues why, and section 6 gives the exact inverses. Quaternions are wxyz, unit to 1.19e-07, w>=0; the source PLY does not declare its component order and this one was declared by the caller as 'wxyz'. SH is stored coefficient-major, transposed from the source's channel-major f_rest_*. Nothing was resampled, recentred or rescaled.
  - `splats/plush.wkgs` (15764784 B)
- **points-dc** [core.geom.points]: 281498 points: the splat's means EXACTLY, and its degree-0 SH band through clamp(0.5 + 0.28209479177387814*dc, 0, 1) quantised to 8 bits per channel, in LINEAR sRGB. Nothing was resampled and nothing was decimated -- this is the whole splat seen by a consumer that does not implement Gaussian splatting, which spec/layouts/gsplat.layout.txt section 7 makes a NORMATIVE path rather than a courtesy. A reader holding the WKGS can recompute every byte of this node and check it (law 5).
  - `points/plush-dc.wkpc` (4223440 B)
- **recipe** [core.recipe]: How this package's payloads were made, step by step, naming the embedded tools by node id. The source .splat travels in this node's files[] because SPEC.md section 3.11 says a recipe that names an input it does not carry is a promise about another file. The one intermediate is recorded rather than carried, by section 3.17's rule, with the exact invocation that regenerates it.
  - `recipe/recipe.json` (6171 B)
  - `recipe/inputs/plush.splat` (9007936 B)
- **semantics** [core.semantics]: Facet tags and a palette measured from the splat's own DC band. The two style/mood tags are x.-prefixed because spec/facets.json v1 has no tag for 'this is a capture rather than an authored asset', and inventing one in a fixture would be extending the registry by the back door.
  - `semantics/semantics.json` (2381 B)
- **provenance** [core.provenance]: Where the source came from and what this build did with it, including the splat that was considered and rejected for size.
  - `provenance/provenance.json` (1047 B)
- **readme** [core.readme]: One page for a human who opened this file and wants to know what it is -- including the two-section shortcut for a reader that does not implement Gaussian splatting.
  - `README.txt` (2682 B)

### Integrity

CRC-32: all entries OK
SHA-256: all declared files OK
Manifest SHA-256 matches SIGNATURE.json: True

## Task 2: Extract point positions and colours

**Succeeded:** yes

Point count: 281498 (from WKGS), 281498 (from WKPC)
First 100 points match between WKGS-derived and WKPC: True

### Sample positions and colours (linear sRGB, from WKGS DC band)

| index | position (x,y,z) | rgb_linear |
|---|---|---|
| 0 | (-0.060075, 1.625257, 0.935071) | (0.152941, 0.074510, 0.023529) |
| 1 | (-0.035026, 1.578063, 1.032170) | (0.235294, 0.117647, 0.113725) |
| 2 | (-0.109434, 1.615720, 1.005387) | (0.427451, 0.278431, 0.101961) |
| 3 | (-0.025732, 1.576227, 1.033759) | (0.254902, 0.168627, 0.180392) |
| 4 | (-0.011812, 1.612853, 0.940788) | (0.200000, 0.070588, 0.035294) |
| 281493 | (0.847431, 1.671588, 1.028747) | (0.894118, 0.831373, 0.709804) |
| 281494 | (0.477563, 1.650874, 1.203664) | (0.745098, 0.647059, 0.607843) |
| 281495 | (0.477869, 1.652458, 1.200677) | (0.541176, 0.454902, 0.333333) |
| 281496 | (0.470707, 1.649350, 1.213920) | (0.482353, 0.360784, 0.290196) |
| 281497 | (0.461299, 1.664856, 1.180542) | (0.643137, 0.552941, 0.470588) |

Colour formula used (from spec/layouts/gsplat.layout.txt §5):
```
C0 = 0.28209479177387814
rgb_linear = clamp(0.5 + C0 * sh_dc, 0, 1)
```

## Task 3: Identify tools, roles, source

**Succeeded:** yes

Three tools are embedded as `core.tool` nodes. Their source was read from the package and is quoted below. **No bundled reader was opened, run, or ported**; all decoding was implemented from the in-package specifications.

### tool-splat-to-ply (`splat-to-ply`, role: converter)
Location: `tools/splat-to-ply/tool.json` and sibling files
Entrypoint: `tools/splat-to-ply/splat_to_ply.py`
Description: The converter that turned the embedded source into the PLY the next tool read. That PLY is NOT in this package and does not need to be: this tool plus recipe/inputs/ regenerates it, and the recipe records its sha256 so the regeneration is checkable (SPEC.md section 3.17).
Files: tools/splat-to-ply/tool.json, tools/splat-to-ply/splat_to_ply.py, tools/splat-to-ply/ply.py

#### Source

##### `tools/splat-to-ply/splat_to_ply.py`

```python
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

```

##### `tools/splat-to-ply/ply.py`

```python
#!/usr/bin/env python3
"""ply.py — a PLY reader with no dependencies beyond numpy, and the INRIA
3D-Gaussian-Splatting field convention it has to recognise.

Two formats are in scope and both are mandatory (Stage 12 brief): `ascii 1.0`
and `binary_little_endian 1.0`. `binary_big_endian 1.0` is read too, because
refusing it would cost four lines and returning wrong numbers costs a user a
day — but nothing in werk ever WRITES one.

WHY A READER LIVES HERE AT ALL. A point cloud or a Gaussian splat arrives as a
PLY, always: it is what every splat trainer emits and what every scanner
exports. `plyfile` and `open3d` both read one, and both are a pip install —
which is fine for a pipeline (law 1 governs what travels inside a package, not
what built it) but bad for a file that wants to be its own converter's home.
This module is 300 lines and is embedded into the packages it produces as a
`core.tool` node, so the package carries the code that read its own input.

WHAT A GAUSSIAN SPLAT PLY LOOKS LIKE. The reference implementation
(graphdeco-inria/gaussian-splatting, `GaussianModel.save_ply`) writes one
`vertex` element with these properties, all f32, in this order:

    x y z                        the mean, in the scene's own units
    nx ny nz                     ALWAYS ZERO. Written because the original
                                 code reuses a point-cloud writer; a reader
                                 that trusts them gets a black render.
    f_dc_0 f_dc_1 f_dc_2         the degree-0 SH coefficient, per RGB channel
    f_rest_0 .. f_rest_{3K-4}    the remaining K-1 coefficients, CHANNEL-MAJOR:
                                 all K-1 of red, then all of green, then blue.
                                 K = (sh_degree+1)**2.
    opacity                      LOGIT space: alpha = sigmoid(opacity)
    scale_0 scale_1 scale_2      LOG space, natural log: metres = exp(scale)
    rot_0 rot_1 rot_2 rot_3      a quaternion, and its component order is the
                                 one field of the whole convention that is not
                                 stable — see `detect_gsplat`.

Every one of those facts is a decode step, not a copy, and getting one wrong
produces a file that looks plausible and renders wrong. `detect_gsplat` returns
them as a declared plan so the caller can print it and a human can check it.
"""

import re
import struct

import numpy as np

__all__ = ["PlyData", "PlyElement", "read_ply", "detect_gsplat", "GsplatPlan",
           "gsplat_arrays", "dc_to_linear_rgb", "write_ply_binary", "SH_C0"]

#: The degree-0 spherical-harmonic basis constant, 1/(2*sqrt(pi)). The DC
#: coefficient is turned into linear colour by `0.5 + SH_C0 * f_dc`, which is
#: the reference renderer's own arithmetic and is reproduced in
#: spec/layouts/gsplat.layout.txt section 6 so a foreign reader needs nothing
#: but the file.
SH_C0 = 0.28209479177387814

_SCALAR = {
    "char": "i1", "int8": "i1",
    "uchar": "u1", "uint8": "u1",
    "short": "i2", "int16": "i2",
    "ushort": "u2", "uint16": "u2",
    "int": "i4", "int32": "i4",
    "uint": "u4", "uint32": "u4",
    "float": "f4", "float32": "f4",
    "double": "f8", "float64": "f8",
}


class PlyElement(object):
    __slots__ = ("name", "count", "properties", "data")

    def __init__(self, name, count):
        self.name = name
        self.count = count
        #: list of (prop_name, scalar_type) or (prop_name, "list", count_type,
        #: item_type). A list property in an element werk reads is an error
        #: rather than a silently dropped column — see read_ply.
        self.properties = []
        self.data = None

    def names(self):
        return [p[0] for p in self.properties]

    def __repr__(self):
        return "<PlyElement %s count=%d props=%d>" % (
            self.name, self.count, len(self.properties))


class PlyData(object):
    __slots__ = ("format", "version", "elements", "comments", "header_bytes")

    def __init__(self):
        self.format = None
        self.version = None
        self.elements = []
        self.comments = []
        self.header_bytes = 0

    def element(self, name):
        for e in self.elements:
            if e.name == name:
                return e
        return None


def _parse_header(buf):
    """Split the header off the front. Returns (PlyData, offset_of_body).

    The header is ASCII and line-oriented and ends with a line `end_header`.
    Line endings are not specified by the PLY 'spec' (there is no normative
    one), so both LF and CRLF are accepted; this is the single most common
    reason a hand-written PLY reader rejects a real file.
    """
    end = buf.find(b"end_header")
    if end < 0:
        raise ValueError("not a PLY: no end_header in the file")
    nl = buf.find(b"\n", end)
    if nl < 0:
        raise ValueError("PLY header's end_header line is unterminated")
    head = buf[:nl + 1]
    text = head.decode("ascii", "replace")
    lines = [ln.strip() for ln in re.split(r"\r\n|\n|\r", text) if ln.strip()]
    if not lines or lines[0] != "ply":
        raise ValueError("not a PLY: the file does not begin with 'ply'")

    ply = PlyData()
    ply.header_bytes = nl + 1
    cur = None
    for ln in lines[1:]:
        parts = ln.split()
        key = parts[0]
        if key == "format":
            if len(parts) < 3:
                raise ValueError("malformed format line: %r" % ln)
            ply.format, ply.version = parts[1], parts[2]
        elif key == "comment" or key == "obj_info":
            ply.comments.append(ln)
        elif key == "element":
            if len(parts) < 3:
                raise ValueError("malformed element line: %r" % ln)
            cur = PlyElement(parts[1], int(parts[2]))
            ply.elements.append(cur)
        elif key == "property":
            if cur is None:
                raise ValueError("property outside any element: %r" % ln)
            if parts[1] == "list":
                cur.properties.append((parts[4], "list", parts[2], parts[3]))
            else:
                cur.properties.append((parts[2], parts[1]))
        elif key == "end_header":
            break
        else:
            # Law 12 in miniature: an unknown header line is skipped, not fatal.
            ply.comments.append("unknown-header-line " + ln)
    if ply.format not in ("ascii", "binary_little_endian", "binary_big_endian"):
        raise ValueError("unsupported PLY format %r" % ply.format)
    return ply


def read_ply(path, want=("vertex",)):
    """Read `path`. Returns a PlyData whose named elements carry numpy arrays.

    `want` names the elements whose data is materialised; every other element
    is still parsed structurally (so its bytes can be stepped over) but its
    data is left None. A splat PLY has exactly one element and a mesh PLY has
    two, and reading a 100 MB face list nobody asked for is the difference
    between a 2-second ingest and a 40-second one.
    """
    with open(path, "rb") as fh:
        buf = fh.read()
    ply = _parse_header(buf)
    off = ply.header_bytes

    if ply.format == "ascii":
        body = buf[off:].decode("ascii", "replace").split()
        cursor = 0
        for el in ply.elements:
            if any(p[1] == "list" for p in el.properties):
                raise ValueError(
                    "element %r has a list property; werk's PLY ingesters read "
                    "fixed per-vertex fields only" % el.name)
            ncol = len(el.properties)
            take = el.count * ncol
            chunk = body[cursor:cursor + take]
            if len(chunk) != take:
                raise ValueError(
                    "element %r declares %d rows x %d columns = %d values, the "
                    "file has %d" % (el.name, el.count, ncol, take, len(chunk)))
            cursor += take
            if el.name in want:
                dt = np.dtype([(p[0], _dtype_of(p[1], "<")) for p in el.properties])
                arr = np.empty(el.count, dtype=dt)
                flat = np.array(chunk)
                for i, p in enumerate(el.properties):
                    arr[p[0]] = flat[i::ncol].astype(dt[i])
                el.data = arr
        return ply

    endian = "<" if ply.format == "binary_little_endian" else ">"
    for el in ply.elements:
        if any(p[1] == "list" for p in el.properties):
            raise ValueError(
                "element %r has a list property; werk's PLY ingesters read "
                "fixed per-vertex fields only" % el.name)
        dt = np.dtype([(p[0], _dtype_of(p[1], endian)) for p in el.properties])
        need = dt.itemsize * el.count
        if off + need > len(buf):
            raise ValueError(
                "element %r declares %d rows of %d bytes = %d, but only %d bytes "
                "follow the header" % (el.name, el.count, dt.itemsize, need,
                                       len(buf) - off))
        if el.name in want:
            el.data = np.frombuffer(buf, dtype=dt, count=el.count, offset=off)
        off += need
    return ply


def _dtype_of(kind, endian):
    try:
        code = _SCALAR[kind]
    except KeyError:
        raise ValueError("unknown PLY scalar type %r" % kind)
    return endian + code if code[0] in "iuf" and code != "i1" and code != "u1" else code


# ---------------------------------------------------------------------------
# the INRIA Gaussian-splat convention
# ---------------------------------------------------------------------------

class GsplatPlan(object):
    """The decode plan for one splat PLY, DECLARED rather than applied.

    Every attribute is a decision that a wrong answer to produces a file that
    parses, renders, and is wrong. Printing this object is how a human checks
    an ingest before 100 MB of it is written into a package.
    """

    __slots__ = ("count", "sh_degree", "sh_coeff_count", "quat_order",
                 "scale_space", "opacity_space", "dc_names", "rest_names",
                 "scale_names", "rot_names", "opacity_name", "extra_names",
                 "quat_order_evidence", "quat_order_statistic",
                 "quat_order_inferred")

    def as_json(self):
        return {
            "count": int(self.count),
            "sh_degree": int(self.sh_degree),
            "sh_coeff_count": int(self.sh_coeff_count),
            "quat_order": self.quat_order,
            "quat_order_evidence": self.quat_order_evidence,
            "quat_order_statistic": self.quat_order_statistic,
            "quat_order_inferred": self.quat_order_inferred,
            "scale_space": self.scale_space,
            "opacity_space": self.opacity_space,
            "ignored_properties": list(self.extra_names),
        }

    def __repr__(self):
        return ("<GsplatPlan %d gaussians, sh_degree %d (%d coeffs), quat %s "
                "(%s), scales %s, opacity %s>"
                % (self.count, self.sh_degree, self.sh_coeff_count,
                   self.quat_order, self.quat_order_evidence, self.scale_space,
                   self.opacity_space))


def detect_gsplat(el, quat_order=None):
    """Decide whether a PLY `vertex` element is an INRIA Gaussian splat, and
    how to decode it. Raises ValueError when it is not one.

    The one genuinely ambiguous field is the quaternion order, and this is the
    honest state of the world: the reference implementation stores WXYZ, and
    several widely used exporters store XYZW under the same property names.
    Nothing in the file declares it. So:

      * an explicit `quat_order` argument always wins, and the plan records
        that a human said so;
      * otherwise the order is INFERRED from the data, by the one statistic
        that separates them: in a trained splat the great majority of
        rotations are near-identity-ish only in the sense that no component
        dominates, but the WXYZ convention's first component is the scalar
        part, whose ABSOLUTE MEAN is markedly higher than the three vector
        components' when the writer emitted w first. The plan records the two
        means and the word 'inferred', so the guess is visible and a consumer
        can override it.

    A guess that is recorded and a guess that is silent are different things;
    this returns the first. Spec finding S12-3.
    """
    names = el.names()
    have = set(names)
    for req in ("x", "y", "z", "opacity"):
        if req not in have:
            raise ValueError("not a Gaussian-splat PLY: no %r property" % req)
    dc = [n for n in ("f_dc_0", "f_dc_1", "f_dc_2") if n in have]
    if len(dc) != 3:
        raise ValueError("not a Gaussian-splat PLY: f_dc_0/1/2 are not all present")
    scale = sorted([n for n in names if re.fullmatch(r"scale_\d+", n)],
                   key=lambda n: int(n.split("_")[1]))
    rot = sorted([n for n in names if re.fullmatch(r"rot_\d+", n)],
                 key=lambda n: int(n.split("_")[1]))
    if len(scale) != 3:
        raise ValueError("expected scale_0..2, found %r" % (scale,))
    if len(rot) != 4:
        raise ValueError("expected rot_0..3, found %r" % (rot,))
    rest = sorted([n for n in names if re.fullmatch(r"f_rest_\d+", n)],
                  key=lambda n: int(n.split("_")[2]))

    if len(rest) % 3 != 0:
        raise ValueError(
            "f_rest_* count %d is not a multiple of 3; the INRIA layout stores "
            "(K-1) coefficients per RGB channel" % len(rest))
    k_minus_1 = len(rest) // 3
    k = k_minus_1 + 1
    degree = int(round(k ** 0.5)) - 1
    if (degree + 1) ** 2 != k:
        raise ValueError(
            "f_rest_* implies %d SH coefficients, which is not (degree+1)**2 "
            "for any integer degree" % k)

    plan = GsplatPlan()
    plan.count = int(el.count)
    plan.sh_degree = degree
    plan.sh_coeff_count = k
    plan.dc_names = ["f_dc_0", "f_dc_1", "f_dc_2"]
    plan.rest_names = rest
    plan.scale_names = scale
    plan.rot_names = rot
    plan.opacity_name = "opacity"
    plan.scale_space = "log"
    plan.opacity_space = "logit"
    known = set(plan.dc_names) | set(rest) | set(scale) | set(rot) | {
        "x", "y", "z", "opacity", "nx", "ny", "nz"}
    plan.extra_names = [n for n in names if n not in known]

    # The statistic is computed ALWAYS, even when the caller declares the
    # order. It costs one pass and it is the number spec/layouts/
    # gsplat.layout.txt section 6 demands be recorded -- and a declared order
    # whose supporting measurement is absent is exactly the empty spot a cold
    # reader found in the first gsplat package (Stage 12 mini-gauntlet, note 3).
    # Declared still WINS; the measurement is evidence beside it, never over it.
    q = np.stack([np.asarray(el.data[n], dtype=np.float64) for n in rot], 1)
    nq = np.linalg.norm(q, axis=1)
    nq[nq == 0] = 1.0
    q = q / nq[:, None]
    m = np.abs(q).mean(axis=0)
    first, rest_mean = float(m[0]), float(m[1:].mean())
    last, head_mean = float(m[3]), float(m[:3].mean())
    if first >= rest_mean and first >= last:
        inferred = "wxyz"
        stat = ("mean|q0| %.4f vs mean of the other three %.4f"
                % (first, rest_mean))
        strength = "inferred"
    elif last > head_mean:
        inferred = "xyzw"
        stat = ("mean|q3| %.4f vs mean of the other three %.4f"
                % (last, head_mean))
        strength = "inferred"
    else:
        inferred = "wxyz"
        stat = ("no component dominates (mean absolute components %s)"
                % " ".join("%.4f" % v for v in m))
        strength = "inferred WEAKLY"
    plan.quat_order_statistic = stat
    plan.quat_order_inferred = inferred

    if quat_order is not None:
        if quat_order not in ("wxyz", "xyzw"):
            raise ValueError("quat_order must be 'wxyz' or 'xyzw'")
        plan.quat_order = quat_order
        plan.quat_order_evidence = (
            "declared by the caller as %r; the same pass measured %s, which "
            "would have %s %r"
            % (quat_order, stat,
               "agreed" if inferred == quat_order else "DISAGREED and chosen",
               inferred))
    else:
        plan.quat_order = inferred
        plan.quat_order_evidence = "%s: %s" % (strength, stat)
    return plan


def gsplat_arrays(el, plan):
    """Apply `plan` to `el.data`. Returns werk-space arrays, all float32:

        means      [N,3]   as they are in the file, no unit change
        scales     [N,3]   LINEAR metres, exp() of the stored log scales
        rotations  [N,4]   wxyz, unit length, w >= 0 (the werk canonical sign)
        opacities  [N]     LINEAR alpha in [0,1], sigmoid() of the stored logit
        sh         [N,K,3] COEFFICIENT-MAJOR: sh[i,c] is coefficient c's RGB

    Every transform here is named in spec/layouts/gsplat.layout.txt section 6
    together with its exact inverse, so nothing in this function is knowledge a
    foreign reader has to have.
    """
    d = el.data
    f = lambda n: np.asarray(d[n], dtype=np.float64)  # noqa: E731

    means = np.stack([f("x"), f("y"), f("z")], 1)
    scales = np.exp(np.stack([f(n) for n in plan.scale_names], 1))
    op = f(plan.opacity_name)
    opac = 1.0 / (1.0 + np.exp(-op))

    q = np.stack([f(n) for n in plan.rot_names], 1)
    if plan.quat_order == "xyzw":
        q = q[:, [3, 0, 1, 2]]
    nrm = np.linalg.norm(q, axis=1)
    nrm[nrm == 0] = 1.0
    q = q / nrm[:, None]
    # ENVELOPE.layout.txt section 6: "w >= 0 is the canonical sign; writers
    # MUST emit the w >= 0 representative". q and -q are the same rotation, so
    # this changes no geometry and makes two writers agree byte for byte.
    q = np.where(q[:, :1] < 0, -q, q)

    k = plan.sh_coeff_count
    sh = np.empty((len(means), k, 3), dtype=np.float64)
    sh[:, 0, 0] = f("f_dc_0")
    sh[:, 0, 1] = f("f_dc_1")
    sh[:, 0, 2] = f("f_dc_2")
    if k > 1:
        # f_rest_* is CHANNEL-MAJOR in the source: (K-1) reds, then greens,
        # then blues. werk stores COEFFICIENT-MAJOR. This transpose is the
        # whole difference and it is the second-easiest thing to get wrong
        # after the quaternion order.
        km1 = k - 1
        rest = np.stack([f(n) for n in plan.rest_names], 1)      # [N, 3*(K-1)]
        rest = rest.reshape(len(means), 3, km1)                   # [N,3,K-1]
        sh[:, 1:, :] = np.transpose(rest, (0, 2, 1))              # [N,K-1,3]

    return (means.astype(np.float32), scales.astype(np.float32),
            q.astype(np.float32), opac.astype(np.float32), sh.astype(np.float32))


def dc_to_linear_rgb(sh_dc):
    """The degree-0 band evaluated in the direction-independent way every
    renderer uses for a first approximation, and the ONLY thing a
    means-and-colour reader needs (spec/SPEC.md section 3.16, law 9)."""
    return np.clip(0.5 + SH_C0 * np.asarray(sh_dc, dtype=np.float64), 0.0, 1.0)


def write_ply_binary(path, count, columns, comments=()):
    """Write a binary_little_endian PLY. `columns` is an ordered list of
    (property_name, numpy array of shape [count]) — all float32 here, because
    every INRIA splat property is.

    This exists so the ingest path has a WRITER to test itself against, and so
    that a source that is not a PLY can be turned into one by a tool the
    package carries rather than by something a reader has to trust.
    """
    head = ["ply", "format binary_little_endian 1.0"]
    head += ["comment " + c for c in comments]
    head.append("element vertex %d" % count)
    for name, _arr in columns:
        head.append("property float %s" % name)
    head.append("end_header")
    blob = ("\n".join(head) + "\n").encode("ascii")
    dt = np.dtype([(name, "<f4") for name, _ in columns])
    rec = np.empty(count, dtype=dt)
    for name, arr in columns:
        rec[name] = np.asarray(arr, dtype=np.float32)
    with open(path, "wb") as fh:
        fh.write(blob)
        fh.write(rec.tobytes())
    return len(blob) + rec.nbytes


def _selftest():
    """Round-trip the writer through the reader, in both encodings."""
    import io
    import os
    import tempfile
    n = 7
    rng = np.random.RandomState(12345)
    cols = [("x", rng.randn(n)), ("y", rng.randn(n)), ("z", rng.randn(n)),
            ("f_dc_0", rng.randn(n)), ("f_dc_1", rng.randn(n)),
            ("f_dc_2", rng.randn(n)), ("opacity", rng.randn(n)),
            ("scale_0", rng.randn(n)), ("scale_1", rng.randn(n)),
            ("scale_2", rng.randn(n)),
            ("rot_0", np.abs(rng.randn(n)) + 1.0), ("rot_1", rng.randn(n)),
            ("rot_2", rng.randn(n)), ("rot_3", rng.randn(n))]
    tmp = os.path.join(tempfile.gettempdir(), "werk-ply-selftest.ply")
    write_ply_binary(tmp, n, cols)
    ply = read_ply(tmp)
    el = ply.element("vertex")
    plan = detect_gsplat(el)
    assert plan.count == n and plan.sh_degree == 0, plan
    m, s, q, o, sh = gsplat_arrays(el, plan)
    assert m.shape == (n, 3) and sh.shape == (n, 1, 3)
    assert np.allclose(np.linalg.norm(q, axis=1), 1.0, atol=1e-6)
    assert (q[:, 0] >= 0).all()
    os.remove(tmp)

    # ascii, same numbers
    lines = ["ply", "format ascii 1.0", "element vertex %d" % n]
    lines += ["property float %s" % c[0] for c in cols]
    lines.append("end_header")
    for i in range(n):
        lines.append(" ".join(repr(float(np.float32(c[1][i]))) for c in cols))
    tmp2 = os.path.join(tempfile.gettempdir(), "werk-ply-selftest-ascii.ply")
    with open(tmp2, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    ply2 = read_ply(tmp2)
    m2, s2, q2, o2, sh2 = gsplat_arrays(ply2.element("vertex"),
                                        detect_gsplat(ply2.element("vertex")))
    assert np.allclose(m, m2, atol=1e-6) and np.allclose(sh, sh2, atol=1e-6)
    os.remove(tmp2)
    print("ply.py selftest OK (binary + ascii round trip, %d vertices)" % n)
    return True


if __name__ == "__main__":
    _selftest()

```

### tool-werk-gsplat (`werk-gsplat`, role: converter)
Location: `tools/werk-gsplat/tool.json` and sibling files
Entrypoint: `tools/werk-gsplat/p_gsplat.py`
Description: This is the file that wrote splats/plush.wkgs. If you want to know exactly what `exp`, `sigmoid` and the SH transpose did to your numbers, read it -- that is why it is here.
Files: tools/werk-gsplat/tool.json, tools/werk-gsplat/p_gsplat.py, tools/werk-gsplat/ply.py, tools/werk-gsplat/common.py

#### Source

##### `tools/werk-gsplat/p_gsplat.py`

```python
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

```

##### `tools/werk-gsplat/ply.py`

```python
#!/usr/bin/env python3
"""ply.py — a PLY reader with no dependencies beyond numpy, and the INRIA
3D-Gaussian-Splatting field convention it has to recognise.

Two formats are in scope and both are mandatory (Stage 12 brief): `ascii 1.0`
and `binary_little_endian 1.0`. `binary_big_endian 1.0` is read too, because
refusing it would cost four lines and returning wrong numbers costs a user a
day — but nothing in werk ever WRITES one.

WHY A READER LIVES HERE AT ALL. A point cloud or a Gaussian splat arrives as a
PLY, always: it is what every splat trainer emits and what every scanner
exports. `plyfile` and `open3d` both read one, and both are a pip install —
which is fine for a pipeline (law 1 governs what travels inside a package, not
what built it) but bad for a file that wants to be its own converter's home.
This module is 300 lines and is embedded into the packages it produces as a
`core.tool` node, so the package carries the code that read its own input.

WHAT A GAUSSIAN SPLAT PLY LOOKS LIKE. The reference implementation
(graphdeco-inria/gaussian-splatting, `GaussianModel.save_ply`) writes one
`vertex` element with these properties, all f32, in this order:

    x y z                        the mean, in the scene's own units
    nx ny nz                     ALWAYS ZERO. Written because the original
                                 code reuses a point-cloud writer; a reader
                                 that trusts them gets a black render.
    f_dc_0 f_dc_1 f_dc_2         the degree-0 SH coefficient, per RGB channel
    f_rest_0 .. f_rest_{3K-4}    the remaining K-1 coefficients, CHANNEL-MAJOR:
                                 all K-1 of red, then all of green, then blue.
                                 K = (sh_degree+1)**2.
    opacity                      LOGIT space: alpha = sigmoid(opacity)
    scale_0 scale_1 scale_2      LOG space, natural log: metres = exp(scale)
    rot_0 rot_1 rot_2 rot_3      a quaternion, and its component order is the
                                 one field of the whole convention that is not
                                 stable — see `detect_gsplat`.

Every one of those facts is a decode step, not a copy, and getting one wrong
produces a file that looks plausible and renders wrong. `detect_gsplat` returns
them as a declared plan so the caller can print it and a human can check it.
"""

import re
import struct

import numpy as np

__all__ = ["PlyData", "PlyElement", "read_ply", "detect_gsplat", "GsplatPlan",
           "gsplat_arrays", "dc_to_linear_rgb", "write_ply_binary", "SH_C0"]

#: The degree-0 spherical-harmonic basis constant, 1/(2*sqrt(pi)). The DC
#: coefficient is turned into linear colour by `0.5 + SH_C0 * f_dc`, which is
#: the reference renderer's own arithmetic and is reproduced in
#: spec/layouts/gsplat.layout.txt section 6 so a foreign reader needs nothing
#: but the file.
SH_C0 = 0.28209479177387814

_SCALAR = {
    "char": "i1", "int8": "i1",
    "uchar": "u1", "uint8": "u1",
    "short": "i2", "int16": "i2",
    "ushort": "u2", "uint16": "u2",
    "int": "i4", "int32": "i4",
    "uint": "u4", "uint32": "u4",
    "float": "f4", "float32": "f4",
    "double": "f8", "float64": "f8",
}


class PlyElement(object):
    __slots__ = ("name", "count", "properties", "data")

    def __init__(self, name, count):
        self.name = name
        self.count = count
        #: list of (prop_name, scalar_type) or (prop_name, "list", count_type,
        #: item_type). A list property in an element werk reads is an error
        #: rather than a silently dropped column — see read_ply.
        self.properties = []
        self.data = None

    def names(self):
        return [p[0] for p in self.properties]

    def __repr__(self):
        return "<PlyElement %s count=%d props=%d>" % (
            self.name, self.count, len(self.properties))


class PlyData(object):
    __slots__ = ("format", "version", "elements", "comments", "header_bytes")

    def __init__(self):
        self.format = None
        self.version = None
        self.elements = []
        self.comments = []
        self.header_bytes = 0

    def element(self, name):
        for e in self.elements:
            if e.name == name:
                return e
        return None


def _parse_header(buf):
    """Split the header off the front. Returns (PlyData, offset_of_body).

    The header is ASCII and line-oriented and ends with a line `end_header`.
    Line endings are not specified by the PLY 'spec' (there is no normative
    one), so both LF and CRLF are accepted; this is the single most common
    reason a hand-written PLY reader rejects a real file.
    """
    end = buf.find(b"end_header")
    if end < 0:
        raise ValueError("not a PLY: no end_header in the file")
    nl = buf.find(b"\n", end)
    if nl < 0:
        raise ValueError("PLY header's end_header line is unterminated")
    head = buf[:nl + 1]
    text = head.decode("ascii", "replace")
    lines = [ln.strip() for ln in re.split(r"\r\n|\n|\r", text) if ln.strip()]
    if not lines or lines[0] != "ply":
        raise ValueError("not a PLY: the file does not begin with 'ply'")

    ply = PlyData()
    ply.header_bytes = nl + 1
    cur = None
    for ln in lines[1:]:
        parts = ln.split()
        key = parts[0]
        if key == "format":
            if len(parts) < 3:
                raise ValueError("malformed format line: %r" % ln)
            ply.format, ply.version = parts[1], parts[2]
        elif key == "comment" or key == "obj_info":
            ply.comments.append(ln)
        elif key == "element":
            if len(parts) < 3:
                raise ValueError("malformed element line: %r" % ln)
            cur = PlyElement(parts[1], int(parts[2]))
            ply.elements.append(cur)
        elif key == "property":
            if cur is None:
                raise ValueError("property outside any element: %r" % ln)
            if parts[1] == "list":
                cur.properties.append((parts[4], "list", parts[2], parts[3]))
            else:
                cur.properties.append((parts[2], parts[1]))
        elif key == "end_header":
            break
        else:
            # Law 12 in miniature: an unknown header line is skipped, not fatal.
            ply.comments.append("unknown-header-line " + ln)
    if ply.format not in ("ascii", "binary_little_endian", "binary_big_endian"):
        raise ValueError("unsupported PLY format %r" % ply.format)
    return ply


def read_ply(path, want=("vertex",)):
    """Read `path`. Returns a PlyData whose named elements carry numpy arrays.

    `want` names the elements whose data is materialised; every other element
    is still parsed structurally (so its bytes can be stepped over) but its
    data is left None. A splat PLY has exactly one element and a mesh PLY has
    two, and reading a 100 MB face list nobody asked for is the difference
    between a 2-second ingest and a 40-second one.
    """
    with open(path, "rb") as fh:
        buf = fh.read()
    ply = _parse_header(buf)
    off = ply.header_bytes

    if ply.format == "ascii":
        body = buf[off:].decode("ascii", "replace").split()
        cursor = 0
        for el in ply.elements:
            if any(p[1] == "list" for p in el.properties):
                raise ValueError(
                    "element %r has a list property; werk's PLY ingesters read "
                    "fixed per-vertex fields only" % el.name)
            ncol = len(el.properties)
            take = el.count * ncol
            chunk = body[cursor:cursor + take]
            if len(chunk) != take:
                raise ValueError(
                    "element %r declares %d rows x %d columns = %d values, the "
                    "file has %d" % (el.name, el.count, ncol, take, len(chunk)))
            cursor += take
            if el.name in want:
                dt = np.dtype([(p[0], _dtype_of(p[1], "<")) for p in el.properties])
                arr = np.empty(el.count, dtype=dt)
                flat = np.array(chunk)
                for i, p in enumerate(el.properties):
                    arr[p[0]] = flat[i::ncol].astype(dt[i])
                el.data = arr
        return ply

    endian = "<" if ply.format == "binary_little_endian" else ">"
    for el in ply.elements:
        if any(p[1] == "list" for p in el.properties):
            raise ValueError(
                "element %r has a list property; werk's PLY ingesters read "
                "fixed per-vertex fields only" % el.name)
        dt = np.dtype([(p[0], _dtype_of(p[1], endian)) for p in el.properties])
        need = dt.itemsize * el.count
        if off + need > len(buf):
            raise ValueError(
                "element %r declares %d rows of %d bytes = %d, but only %d bytes "
                "follow the header" % (el.name, el.count, dt.itemsize, need,
                                       len(buf) - off))
        if el.name in want:
            el.data = np.frombuffer(buf, dtype=dt, count=el.count, offset=off)
        off += need
    return ply


def _dtype_of(kind, endian):
    try:
        code = _SCALAR[kind]
    except KeyError:
        raise ValueError("unknown PLY scalar type %r" % kind)
    return endian + code if code[0] in "iuf" and code != "i1" and code != "u1" else code


# ---------------------------------------------------------------------------
# the INRIA Gaussian-splat convention
# ---------------------------------------------------------------------------

class GsplatPlan(object):
    """The decode plan for one splat PLY, DECLARED rather than applied.

    Every attribute is a decision that a wrong answer to produces a file that
    parses, renders, and is wrong. Printing this object is how a human checks
    an ingest before 100 MB of it is written into a package.
    """

    __slots__ = ("count", "sh_degree", "sh_coeff_count", "quat_order",
                 "scale_space", "opacity_space", "dc_names", "rest_names",
                 "scale_names", "rot_names", "opacity_name", "extra_names",
                 "quat_order_evidence", "quat_order_statistic",
                 "quat_order_inferred")

    def as_json(self):
        return {
            "count": int(self.count),
            "sh_degree": int(self.sh_degree),
            "sh_coeff_count": int(self.sh_coeff_count),
            "quat_order": self.quat_order,
            "quat_order_evidence": self.quat_order_evidence,
            "quat_order_statistic": self.quat_order_statistic,
            "quat_order_inferred": self.quat_order_inferred,
            "scale_space": self.scale_space,
            "opacity_space": self.opacity_space,
            "ignored_properties": list(self.extra_names),
        }

    def __repr__(self):
        return ("<GsplatPlan %d gaussians, sh_degree %d (%d coeffs), quat %s "
                "(%s), scales %s, opacity %s>"
                % (self.count, self.sh_degree, self.sh_coeff_count,
                   self.quat_order, self.quat_order_evidence, self.scale_space,
                   self.opacity_space))


def detect_gsplat(el, quat_order=None):
    """Decide whether a PLY `vertex` element is an INRIA Gaussian splat, and
    how to decode it. Raises ValueError when it is not one.

    The one genuinely ambiguous field is the quaternion order, and this is the
    honest state of the world: the reference implementation stores WXYZ, and
    several widely used exporters store XYZW under the same property names.
    Nothing in the file declares it. So:

      * an explicit `quat_order` argument always wins, and the plan records
        that a human said so;
      * otherwise the order is INFERRED from the data, by the one statistic
        that separates them: in a trained splat the great majority of
        rotations are near-identity-ish only in the sense that no component
        dominates, but the WXYZ convention's first component is the scalar
        part, whose ABSOLUTE MEAN is markedly higher than the three vector
        components' when the writer emitted w first. The plan records the two
        means and the word 'inferred', so the guess is visible and a consumer
        can override it.

    A guess that is recorded and a guess that is silent are different things;
    this returns the first. Spec finding S12-3.
    """
    names = el.names()
    have = set(names)
    for req in ("x", "y", "z", "opacity"):
        if req not in have:
            raise ValueError("not a Gaussian-splat PLY: no %r property" % req)
    dc = [n for n in ("f_dc_0", "f_dc_1", "f_dc_2") if n in have]
    if len(dc) != 3:
        raise ValueError("not a Gaussian-splat PLY: f_dc_0/1/2 are not all present")
    scale = sorted([n for n in names if re.fullmatch(r"scale_\d+", n)],
                   key=lambda n: int(n.split("_")[1]))
    rot = sorted([n for n in names if re.fullmatch(r"rot_\d+", n)],
                 key=lambda n: int(n.split("_")[1]))
    if len(scale) != 3:
        raise ValueError("expected scale_0..2, found %r" % (scale,))
    if len(rot) != 4:
        raise ValueError("expected rot_0..3, found %r" % (rot,))
    rest = sorted([n for n in names if re.fullmatch(r"f_rest_\d+", n)],
                  key=lambda n: int(n.split("_")[2]))

    if len(rest) % 3 != 0:
        raise ValueError(
            "f_rest_* count %d is not a multiple of 3; the INRIA layout stores "
            "(K-1) coefficients per RGB channel" % len(rest))
    k_minus_1 = len(rest) // 3
    k = k_minus_1 + 1
    degree = int(round(k ** 0.5)) - 1
    if (degree + 1) ** 2 != k:
        raise ValueError(
            "f_rest_* implies %d SH coefficients, which is not (degree+1)**2 "
            "for any integer degree" % k)

    plan = GsplatPlan()
    plan.count = int(el.count)
    plan.sh_degree = degree
    plan.sh_coeff_count = k
    plan.dc_names = ["f_dc_0", "f_dc_1", "f_dc_2"]
    plan.rest_names = rest
    plan.scale_names = scale
    plan.rot_names = rot
    plan.opacity_name = "opacity"
    plan.scale_space = "log"
    plan.opacity_space = "logit"
    known = set(plan.dc_names) | set(rest) | set(scale) | set(rot) | {
        "x", "y", "z", "opacity", "nx", "ny", "nz"}
    plan.extra_names = [n for n in names if n not in known]

    # The statistic is computed ALWAYS, even when the caller declares the
    # order. It costs one pass and it is the number spec/layouts/
    # gsplat.layout.txt section 6 demands be recorded -- and a declared order
    # whose supporting measurement is absent is exactly the empty spot a cold
    # reader found in the first gsplat package (Stage 12 mini-gauntlet, note 3).
    # Declared still WINS; the measurement is evidence beside it, never over it.
    q = np.stack([np.asarray(el.data[n], dtype=np.float64) for n in rot], 1)
    nq = np.linalg.norm(q, axis=1)
    nq[nq == 0] = 1.0
    q = q / nq[:, None]
    m = np.abs(q).mean(axis=0)
    first, rest_mean = float(m[0]), float(m[1:].mean())
    last, head_mean = float(m[3]), float(m[:3].mean())
    if first >= rest_mean and first >= last:
        inferred = "wxyz"
        stat = ("mean|q0| %.4f vs mean of the other three %.4f"
                % (first, rest_mean))
        strength = "inferred"
    elif last > head_mean:
        inferred = "xyzw"
        stat = ("mean|q3| %.4f vs mean of the other three %.4f"
                % (last, head_mean))
        strength = "inferred"
    else:
        inferred = "wxyz"
        stat = ("no component dominates (mean absolute components %s)"
                % " ".join("%.4f" % v for v in m))
        strength = "inferred WEAKLY"
    plan.quat_order_statistic = stat
    plan.quat_order_inferred = inferred

    if quat_order is not None:
        if quat_order not in ("wxyz", "xyzw"):
            raise ValueError("quat_order must be 'wxyz' or 'xyzw'")
        plan.quat_order = quat_order
        plan.quat_order_evidence = (
            "declared by the caller as %r; the same pass measured %s, which "
            "would have %s %r"
            % (quat_order, stat,
               "agreed" if inferred == quat_order else "DISAGREED and chosen",
               inferred))
    else:
        plan.quat_order = inferred
        plan.quat_order_evidence = "%s: %s" % (strength, stat)
    return plan


def gsplat_arrays(el, plan):
    """Apply `plan` to `el.data`. Returns werk-space arrays, all float32:

        means      [N,3]   as they are in the file, no unit change
        scales     [N,3]   LINEAR metres, exp() of the stored log scales
        rotations  [N,4]   wxyz, unit length, w >= 0 (the werk canonical sign)
        opacities  [N]     LINEAR alpha in [0,1], sigmoid() of the stored logit
        sh         [N,K,3] COEFFICIENT-MAJOR: sh[i,c] is coefficient c's RGB

    Every transform here is named in spec/layouts/gsplat.layout.txt section 6
    together with its exact inverse, so nothing in this function is knowledge a
    foreign reader has to have.
    """
    d = el.data
    f = lambda n: np.asarray(d[n], dtype=np.float64)  # noqa: E731

    means = np.stack([f("x"), f("y"), f("z")], 1)
    scales = np.exp(np.stack([f(n) for n in plan.scale_names], 1))
    op = f(plan.opacity_name)
    opac = 1.0 / (1.0 + np.exp(-op))

    q = np.stack([f(n) for n in plan.rot_names], 1)
    if plan.quat_order == "xyzw":
        q = q[:, [3, 0, 1, 2]]
    nrm = np.linalg.norm(q, axis=1)
    nrm[nrm == 0] = 1.0
    q = q / nrm[:, None]
    # ENVELOPE.layout.txt section 6: "w >= 0 is the canonical sign; writers
    # MUST emit the w >= 0 representative". q and -q are the same rotation, so
    # this changes no geometry and makes two writers agree byte for byte.
    q = np.where(q[:, :1] < 0, -q, q)

    k = plan.sh_coeff_count
    sh = np.empty((len(means), k, 3), dtype=np.float64)
    sh[:, 0, 0] = f("f_dc_0")
    sh[:, 0, 1] = f("f_dc_1")
    sh[:, 0, 2] = f("f_dc_2")
    if k > 1:
        # f_rest_* is CHANNEL-MAJOR in the source: (K-1) reds, then greens,
        # then blues. werk stores COEFFICIENT-MAJOR. This transpose is the
        # whole difference and it is the second-easiest thing to get wrong
        # after the quaternion order.
        km1 = k - 1
        rest = np.stack([f(n) for n in plan.rest_names], 1)      # [N, 3*(K-1)]
        rest = rest.reshape(len(means), 3, km1)                   # [N,3,K-1]
        sh[:, 1:, :] = np.transpose(rest, (0, 2, 1))              # [N,K-1,3]

    return (means.astype(np.float32), scales.astype(np.float32),
            q.astype(np.float32), opac.astype(np.float32), sh.astype(np.float32))


def dc_to_linear_rgb(sh_dc):
    """The degree-0 band evaluated in the direction-independent way every
    renderer uses for a first approximation, and the ONLY thing a
    means-and-colour reader needs (spec/SPEC.md section 3.16, law 9)."""
    return np.clip(0.5 + SH_C0 * np.asarray(sh_dc, dtype=np.float64), 0.0, 1.0)


def write_ply_binary(path, count, columns, comments=()):
    """Write a binary_little_endian PLY. `columns` is an ordered list of
    (property_name, numpy array of shape [count]) — all float32 here, because
    every INRIA splat property is.

    This exists so the ingest path has a WRITER to test itself against, and so
    that a source that is not a PLY can be turned into one by a tool the
    package carries rather than by something a reader has to trust.
    """
    head = ["ply", "format binary_little_endian 1.0"]
    head += ["comment " + c for c in comments]
    head.append("element vertex %d" % count)
    for name, _arr in columns:
        head.append("property float %s" % name)
    head.append("end_header")
    blob = ("\n".join(head) + "\n").encode("ascii")
    dt = np.dtype([(name, "<f4") for name, _ in columns])
    rec = np.empty(count, dtype=dt)
    for name, arr in columns:
        rec[name] = np.asarray(arr, dtype=np.float32)
    with open(path, "wb") as fh:
        fh.write(blob)
        fh.write(rec.tobytes())
    return len(blob) + rec.nbytes


def _selftest():
    """Round-trip the writer through the reader, in both encodings."""
    import io
    import os
    import tempfile
    n = 7
    rng = np.random.RandomState(12345)
    cols = [("x", rng.randn(n)), ("y", rng.randn(n)), ("z", rng.randn(n)),
            ("f_dc_0", rng.randn(n)), ("f_dc_1", rng.randn(n)),
            ("f_dc_2", rng.randn(n)), ("opacity", rng.randn(n)),
            ("scale_0", rng.randn(n)), ("scale_1", rng.randn(n)),
            ("scale_2", rng.randn(n)),
            ("rot_0", np.abs(rng.randn(n)) + 1.0), ("rot_1", rng.randn(n)),
            ("rot_2", rng.randn(n)), ("rot_3", rng.randn(n))]
    tmp = os.path.join(tempfile.gettempdir(), "werk-ply-selftest.ply")
    write_ply_binary(tmp, n, cols)
    ply = read_ply(tmp)
    el = ply.element("vertex")
    plan = detect_gsplat(el)
    assert plan.count == n and plan.sh_degree == 0, plan
    m, s, q, o, sh = gsplat_arrays(el, plan)
    assert m.shape == (n, 3) and sh.shape == (n, 1, 3)
    assert np.allclose(np.linalg.norm(q, axis=1), 1.0, atol=1e-6)
    assert (q[:, 0] >= 0).all()
    os.remove(tmp)

    # ascii, same numbers
    lines = ["ply", "format ascii 1.0", "element vertex %d" % n]
    lines += ["property float %s" % c[0] for c in cols]
    lines.append("end_header")
    for i in range(n):
        lines.append(" ".join(repr(float(np.float32(c[1][i]))) for c in cols))
    tmp2 = os.path.join(tempfile.gettempdir(), "werk-ply-selftest-ascii.ply")
    with open(tmp2, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    ply2 = read_ply(tmp2)
    m2, s2, q2, o2, sh2 = gsplat_arrays(ply2.element("vertex"),
                                        detect_gsplat(ply2.element("vertex")))
    assert np.allclose(m, m2, atol=1e-6) and np.allclose(sh, sh2, atol=1e-6)
    os.remove(tmp2)
    print("ply.py selftest OK (binary + ascii round trip, %d vertices)" % n)
    return True


if __name__ == "__main__":
    _selftest()

```

##### `tools/werk-gsplat/common.py`

```python
#!/usr/bin/env python3
"""common.py — the parts every producer in the enrichment pipeline shares.

Hashing, the on-disk JSON spelling, the node/version builders, the canonical
MessagePack encoder and the binary-envelope writer, and the zip writer that is
byte-for-byte what `core/src/zipstore.rs` emits.

Nothing here is werk-specific policy; the policy lives in `spec/` and in the
producer modules. This file is the plumbing, and it is deliberately the only
place in the pipeline that knows how to turn bytes into a container.

Stdlib only, except `werkstore.ed25519` (itself stdlib-only) for signing.
"""

import hashlib
import json
import math
import os
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if os.path.join(ROOT, "store") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "store"))

TOOL = "pipeline/enrich.py"
TOOL_VERSION = "0.1"


# ---------------------------------------------------------------------------
# hashing, JSON, ids
# ---------------------------------------------------------------------------

def sha256(b):
    return hashlib.sha256(b).hexdigest()


def jbytes(v):
    """The on-disk spelling werk uses: two-space indent, trailing newline."""
    return (json.dumps(v, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def canon(v):
    """Canonical JSON, as `input_params` is hashed (MINI-SPECS section 11)."""
    return json.dumps(v, sort_keys=True, separators=(",", ":")).encode("utf-8")


def uuid_from(seed_bytes):
    """A deterministic RFC-4122 v4-shaped uuid derived from content.

    A pipeline that stamped a random uuid would make two runs over one GLB
    two different entities, which is a lie about identity (law 4). Derived
    from the source bytes, the uuid says 'this entity is that GLB enriched'
    and says it the same way on every machine.
    """
    d = hashlib.sha256(b"werk-entity-uuid/1\x00" + seed_bytes).digest()
    b = bytearray(d[:16])
    b[6] = (b[6] & 0x0F) | 0x40
    b[8] = (b[8] & 0x3F) | 0x80
    h = b.hex()
    return "%s-%s-%s-%s-%s" % (h[0:8], h[8:12], h[12:16], h[16:20], h[20:32])


def kebab(s):
    out = []
    prev_dash = True
    for ch in s.lower():
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        elif not prev_dash:
            out.append("-")
            prev_dash = True
    while out and out[-1] == "-":
        out.pop()
    return "".join(out) or "entity"


# ---------------------------------------------------------------------------
# canonical MessagePack (writer subset of ENVELOPE.layout.txt section 4)
# ---------------------------------------------------------------------------

def mp_encode(v):
    if v is True:
        return b"\xc3"
    if v is False:
        return b"\xc2"
    if v is None:
        raise ValueError("werk headers never carry nil; omit the key instead")
    if isinstance(v, int):
        if 0 <= v <= 127:
            return struct.pack("B", v)
        if -32 <= v < 0:
            return struct.pack("b", v)
        if 0 <= v <= 0xFF:
            return b"\xcc" + struct.pack(">B", v)
        if 0 <= v <= 0xFFFF:
            return b"\xcd" + struct.pack(">H", v)
        if 0 <= v <= 0xFFFFFFFF:
            return b"\xce" + struct.pack(">I", v)
        if 0 <= v <= 0xFFFFFFFFFFFFFFFF:
            return b"\xcf" + struct.pack(">Q", v)
        if -0x80 <= v < 0:
            return b"\xd0" + struct.pack(">b", v)
        if -0x8000 <= v < 0:
            return b"\xd1" + struct.pack(">h", v)
        if -0x80000000 <= v < 0:
            return b"\xd2" + struct.pack(">i", v)
        return b"\xd3" + struct.pack(">q", v)
    if isinstance(v, float):
        # section 4.3: every non-integral number is float64, never float32.
        if math.isnan(v) or math.isinf(v):
            raise ValueError("no NaN and no infinity in a werk payload")
        return b"\xcb" + struct.pack(">d", v)
    if isinstance(v, str):
        b = v.encode("utf-8")
        n = len(b)
        if n <= 31:
            return struct.pack("B", 0xA0 | n) + b
        if n <= 0xFF:
            return b"\xd9" + struct.pack(">B", n) + b
        if n <= 0xFFFF:
            return b"\xda" + struct.pack(">H", n) + b
        return b"\xdb" + struct.pack(">I", n) + b
    if isinstance(v, (list, tuple)):
        n = len(v)
        if n <= 15:
            head = struct.pack("B", 0x90 | n)
        elif n <= 0xFFFF:
            head = b"\xdc" + struct.pack(">H", n)
        else:
            head = b"\xdd" + struct.pack(">I", n)
        return head + b"".join(mp_encode(x) for x in v)
    if isinstance(v, dict):
        items = sorted(v.items(), key=lambda kv: kv[0].encode("utf-8"))
        n = len(items)
        if n <= 15:
            head = struct.pack("B", 0x80 | n)
        elif n <= 0xFFFF:
            head = b"\xde" + struct.pack(">H", n)
        else:
            head = b"\xdf" + struct.pack(">I", n)
        return head + b"".join(mp_encode(k) + mp_encode(x) for k, x in items)
    raise TypeError("not encodable in the werk MessagePack subset: %r" % type(v))


DTYPE_SIZE = {"u8": 1, "i8": 1, "u16": 2, "i16": 2, "u32": 4, "i32": 4,
              "u64": 8, "i64": 8, "f32": 4, "f64": 8}


def write_envelope(magic, kind, header_extra, sections):
    """Build a conformant werk binary envelope.

    `sections` is a list of (name, dtype, shape, stride, payload_bytes) in file
    order. Offsets, sizes, payload_origin and payload_size are computed here
    and DECLARED in the header — never left for a reader to derive (law 8).
    The section consistency rule of ENVELOPE.layout.txt section 3 is asserted
    on the way out, so a malformed writer fails here and not in someone else's
    reader.
    """
    assert len(magic) == 4
    # payload_origin depends on header_len, which depends on the offsets, which
    # depend on payload_origin. Iterate to the fixed point; it converges in two
    # rounds because only the digit count of the offsets can move.
    origin = 16
    for _ in range(8):
        secs, cursor = [], origin
        for name, dtype, shape, stride, data in sections:
            esz = DTYPE_SIZE.get(dtype, stride)
            prod_all = 1
            for d in shape:
                prod_all *= d
            if stride == esz:
                expect = stride * prod_all
            else:
                assert shape and stride >= esz * shape[-1], \
                    "%s: stride %d < esz %d * shape[-1] %d" % (name, stride, esz,
                                                               shape[-1] if shape else 0)
                prod_head = 1
                for d in shape[:-1]:
                    prod_head *= d
                expect = stride * prod_head
            assert len(data) == expect, \
                "%s: %d payload bytes, consistency rule says %d" % (name, len(data), expect)
            secs.append({"name": name, "offset": cursor, "size": len(data),
                         "dtype": dtype, "shape": [int(d) for d in shape],
                         "stride": int(stride)})
            cursor += len(data)
            cursor = (cursor + 15) // 16 * 16
        header = dict(header_extra)
        header.update({"kind": kind, "endianness": "le",
                       "payload_origin": origin, "payload_size": cursor - origin,
                       "sections": secs})
        hb = mp_encode(header)
        new_origin = 16 * ((12 + len(hb) + 15) // 16)
        if new_origin == origin:
            break
        origin = new_origin
    else:
        raise RuntimeError("envelope header size did not converge")

    out = bytearray()
    out += magic.encode("ascii") + struct.pack("<II", 1, len(hb)) + hb
    out += b"\x00" * (origin - len(out))
    for sec, (_n, _d, _s, _st, data) in zip(secs, sections):
        assert len(out) == sec["offset"]
        out += data
        pad = (16 - (len(out) % 16)) % 16
        out += b"\x00" * pad
    assert len(out) == origin + header["payload_size"]
    return bytes(out)


# ---------------------------------------------------------------------------
# zip writer — byte-for-byte what core/src/zipstore.rs::write_zip emits
# ---------------------------------------------------------------------------

CRC_TABLE = []
for _n in range(256):
    _c = _n
    for _ in range(8):
        _c = (_c >> 1) ^ (0xEDB88320 if _c & 1 else 0)
    CRC_TABLE.append(_c)


def crc32(data):
    c = 0xFFFFFFFF
    for b in data:
        c = (c >> 8) ^ CRC_TABLE[(c ^ b) & 0xFF]
    return c ^ 0xFFFFFFFF


DOS_TIME = (9 << 11) | (0 << 5)
DOS_DATE = ((2026 - 1980) << 9) | (8 << 5) | 8
FLAG_UTF8 = 0x0800


def write_zip(entries):
    out, central, count = bytearray(), bytearray(), 0
    for name, data in entries:
        lho = len(out)
        crc = crc32(data)
        nb = name.encode("utf-8")
        out += struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, FLAG_UTF8, 0, DOS_TIME,
                           DOS_DATE, crc, len(data), len(data), len(nb), 0)
        out += nb + data
        central += struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, 20, 20, FLAG_UTF8, 0,
                               DOS_TIME, DOS_DATE, crc, len(data), len(data), len(nb),
                               0, 0, 0, 0, 0, lho)
        central += nb
        count += 1
    cd_off, cd_size = len(out), len(central)
    out += central
    out += struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, count, count, cd_size, cd_off, 0)
    return bytes(out)


# ---------------------------------------------------------------------------
# the build context every producer writes into
# ---------------------------------------------------------------------------

class Report(object):
    """One line of the pipeline's own honesty. A producer that fails writes
    one of these and the run continues (the island rule): a failed producer
    yields a MISSING NODE plus a report, never a dead pipeline."""

    def __init__(self, stage, status, seconds, detail="", nodes=(), error=None):
        self.stage = stage
        self.status = status          # "ok" | "skipped" | "failed"
        self.seconds = seconds
        self.detail = detail
        self.nodes = list(nodes)
        self.error = error

    record_timings = True

    def as_json(self):
        d = {"stage": self.stage, "status": self.status, "nodes": self.nodes}
        if self.record_timings:
            d["wall_seconds"] = round(self.seconds, 4)
        if self.detail:
            d["detail"] = self.detail
        if self.error:
            d["error"] = self.error
        return d


class Ctx(object):
    def __init__(self, created, entity_uuid, name, record_timings=True):
        # Wall times are honest measurements of ONE run and therefore the one
        # thing in the package that cannot be byte-identical across runs.
        # `record_timings=False` drops them so that byte-identity becomes a
        # checkable property; it does not make the pipeline more deterministic,
        # it stops the package from recording the one thing that isn't.
        self.record_timings = record_timings
        self.files = {}
        self.nodes = []
        self.reports = []
        self.created = created
        self.entity_uuid = entity_uuid
        self.name = name
        self.parts = []
        self.materials = []
        self.schemas = {}
        self.layouts = {}
        self.primary = {}
        self.stats = {}
        self.notes = []

    # -- files ----------------------------------------------------------
    def put(self, path, data):
        if path in self.files:
            raise AssertionError("two nodes claim %s" % path)
        self.files[path] = data
        return {"path": path, "sha256": sha256(data), "size": len(data)}

    def input_hash(self, paths, params=None):
        """sha256 over each input's 32 RAW digest bytes in order, then the
        canonical JSON of input_params. The executable copy is werk-core's
        hashing.rs; this must agree with it byte for byte."""
        h = hashlib.sha256()
        for p in paths:
            h.update(hashlib.sha256(self.files[p]).digest())
        h.update(canon(params if params is not None else {}))
        return h.hexdigest()

    # -- nodes ----------------------------------------------------------
    def node(self, node_id, ntype, ver, edges=(), meta=None, part=None,
             material=None):
        n = {"node_id": node_id, "type": ntype, "versions": [ver], "active": 1,
             "edges": [dict(e) for e in edges]}
        if part:
            n["part_id"] = part
        if material:
            n["material_id"] = material
        if meta:
            n["meta"] = meta
        self.nodes.append(n)
        return n

    def version(self, fs, note, epistemic, inputs=None, params=None,
                confidence=None, tool=TOOL, tver=TOOL_VERSION, model=None):
        v = {"v": 1, "files": list(fs), "note": note,
             "producer": {"tool": tool, "version": tver},
             "epistemic": epistemic, "created": self.created}
        if model:
            v["producer"]["model"] = model
        if epistemic in ("measured", "inferred"):
            assert inputs, "%s node without input_files: law 5 forbids it" % epistemic
        if inputs:
            v["input_files"] = list(inputs)
            v["input_params"] = dict(params or {})
            v["input_hash"] = self.input_hash(inputs, v["input_params"])
        if confidence is not None:
            v["confidence"] = confidence
        return v

    # -- reports --------------------------------------------------------
    def report(self, r):
        r.record_timings = self.record_timings
        self.reports.append(r)
        return r


class Stage(object):
    """Context manager implementing the island rule.

        with Stage(ctx, "lod") as st:
            ...
            st.produced("geom-lod1")

    An exception inside the block is caught, timed, recorded as a failed
    stage, and swallowed. The pipeline continues and the package simply lacks
    that node — which the format says is legal and which is exactly the
    behaviour under test.
    """

    def __init__(self, ctx, name, verbose=True):
        self.ctx = ctx
        self.name = name
        self.verbose = verbose
        self.nodes = []
        self.detail = ""
        self.t0 = None
        self.ok = False

    def produced(self, *node_ids):
        self.nodes.extend(node_ids)

    def says(self, text):
        self.detail = text

    def __enter__(self):
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        dt = time.perf_counter() - self.t0
        if exc_type is None:
            self.ok = True
            r = Report(self.name, "ok", dt, self.detail, self.nodes)
        else:
            import traceback
            err = "".join(traceback.format_exception_only(exc_type, exc)).strip()
            r = Report(self.name, "failed", dt, self.detail, [], err)
            r.traceback = "".join(traceback.format_exception(exc_type, exc, tb))
        self.ctx.report(r)
        if self.verbose:
            print("  [%-7s] %-14s %7.2fs  %s" % (r.status, self.name, dt,
                                                 r.error or r.detail))
        return exc_type is not None       # swallow: the island rule


# ---------------------------------------------------------------------------
# PNG (writer only; Pillow is a PIPELINE dependency and never ships inside a
# package — law 1 governs what travels in the file, not what built it)
# ---------------------------------------------------------------------------

def png_bytes(arr, mode):
    """arr: numpy array. mode in {'RGBA','RGB','L16'}. Deterministic PNG."""
    import io
    import numpy as np
    from PIL import Image
    if mode == "L16":
        img = Image.fromarray(np.ascontiguousarray(arr.astype("<u2")), mode="I;16")
    else:
        img = Image.fromarray(np.ascontiguousarray(arr.astype("u1")), mode=mode)
    buf = io.BytesIO()
    # optimize=False + fixed compress_level keeps two runs byte-identical.
    img.save(buf, format="PNG", optimize=False, compress_level=6)
    return buf.getvalue()


def png_info(b):
    assert b[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    ln, tag = struct.unpack(">I4s", b[8:16])
    assert tag == b"IHDR" and ln == 13
    w, h, depth, ctype = struct.unpack(">IIBB", b[16:26])
    return {"width": w, "height": h, "bit_depth": depth, "color_type": ctype}


def srgb_to_linear_f(u8):
    s = u8 / 255.0
    return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4


def linear_to_srgb_f(x):
    x = max(0.0, min(1.0, x))
    return x * 12.92 if x <= 0.0031308 else 1.055 * (x ** (1.0 / 2.4)) - 0.055


def hexcolor(rgb_lin):
    return "#" + "".join("%02x" % int(round(linear_to_srgb_f(c) * 255.0))
                         for c in rgb_lin)

```

### tool-werk-pointcloud (`werk-pointcloud`, role: processor)
Location: `tools/werk-pointcloud/tool.json` and sibling files
Entrypoint: `tools/werk-pointcloud/p_pointcloud.py`
Description: The processor that derived points/plush-dc.wkpc from the splat. Its `from_gsplat` is nine lines and they are the whole of gsplat.layout.txt section 7.
Files: tools/werk-pointcloud/tool.json, tools/werk-pointcloud/p_pointcloud.py, tools/werk-pointcloud/ply.py, tools/werk-pointcloud/common.py

#### Source

##### `tools/werk-pointcloud/p_pointcloud.py`

```python
#!/usr/bin/env python3
"""p_pointcloud.py — core.geom.points, the WKPC binary: a point cloud with
DECLARED fields.

    python pipeline/p_pointcloud.py IN.ply OUT.wkpc [--json STATS.json]

Normative source: spec/layouts/points.layout.txt. Two producers live here and
they are different jobs that share a writer:

  * `ingest_ply` — a PLY point cloud (ascii or binary, either endianness) into
    a WKPC. Property names map to SEMANTICS by the table in points.layout.txt
    section 7; anything unrecognised is carried as a `custom` field named
    `x-<property>` rather than dropped, because a field a producer did not
    anticipate is exactly what the declared-fields design exists for.

  * `from_gsplat` — the normative degradation of a Gaussian splat into its
    point cloud (gsplat.layout.txt section 7, SPEC.md section 3.16, law 9):
    positions are the means EXACTLY, colours are the DC band through
    `clamp(0.5 + C0*sh_dc, 0, 1)`. No resampling, no decimation, no
    approximation — which is what makes the resulting node `epistemic:
    "measured"` over a derivation a consumer can recompute and check.

TWO THINGS ARE DROPPED ON PLY INGEST AND BOTH ARE REPORTED. A `face` element
(a PLY with faces is a mesh and belongs in core.geom.source; discarding its
faces silently would turn a mesh into a point cloud without telling anyone),
and `nx/ny/nz` that are exactly zero for every point — the signature of the
INRIA splat writer reusing a point-cloud writer, where carrying three million
zeros as "normals" is worse than carrying nothing because a consumer would
light with them.

This module is embedded into the packages it writes as a `core.tool` node
(SPEC.md section 3.17).
"""

import argparse
import json
import os
import sys

import numpy as np

if __package__ in (None, ""):
    # Standalone, in either of two shapes: from the repository, and from a werk
    # package that extracted this file flat beside common.py and ply.py as a
    # `core.tool` node. See p_gsplat.py's note on why the second one matters.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        sys.path.insert(
            1, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from pipeline.common import write_envelope
        from pipeline.ply import read_ply, dc_to_linear_rgb
    except ImportError:
        from common import write_envelope
        from ply import read_ply, dc_to_linear_rgb
else:
    from .common import write_envelope
    from .ply import read_ply, dc_to_linear_rgb

TOOL = "pipeline/p_pointcloud.py"
TOOL_VERSION = "1.0"

MAGIC = "WKPC"
KIND = "core.geom.points"
LAYOUT = "spec/layouts/points.layout.txt"

DTYPE_SIZE = {"u8": 1, "i8": 1, "u16": 2, "i16": 2, "u32": 4, "i32": 4,
              "u64": 8, "i64": 8, "f32": 4, "f64": 8}

NP_OF = {"u8": "u1", "i8": "i1", "u16": "<u2", "i16": "<i2", "u32": "<u4",
         "i32": "<i4", "u64": "<u8", "i64": "<i8", "f32": "<f4", "f64": "<f8"}


class Field(object):
    """One declared field: the header entry and the column, together, so the
    two cannot drift apart between construction and writing."""

    __slots__ = ("name", "semantic", "dtype", "components", "data", "extra")

    def __init__(self, name, semantic, dtype, components, data, **extra):
        self.name = name
        self.semantic = semantic
        self.dtype = dtype
        self.components = int(components)
        self.data = np.ascontiguousarray(data, dtype=NP_OF[dtype])
        self.extra = extra

    def header_entry(self):
        e = {"name": self.name, "section": self.name, "semantic": self.semantic,
             "dtype": self.dtype, "components": self.components}
        e.update(self.extra)
        return e

    def section(self, count):
        stride = DTYPE_SIZE[self.dtype] * self.components
        shape = [count] if self.components == 1 else [count, self.components]
        want = (count,) if self.components == 1 else (count, self.components)
        if self.data.shape != want:
            raise ValueError("field %r has shape %s, expected %s"
                             % (self.name, self.data.shape, want))
        return (self.name, self.dtype, shape, stride, self.data.tobytes())


def build_wkpc(fields, extra_header=None):
    """The writer. `fields` is an ordered list of Field; fields[0] MUST be the
    position field, which is what points.layout.txt section 6 check 2 requires
    a reader to verify — so the writer verifies it first."""
    if not fields:
        raise ValueError("a WKPC needs at least the position field")
    if fields[0].semantic != "position":
        raise ValueError("the first field must be the position, not %r"
                         % fields[0].semantic)
    if sum(1 for f in fields if f.semantic == "position") != 1:
        raise ValueError("exactly one field may have semantic 'position'")
    if fields[0].dtype not in ("f32", "f64") or fields[0].components != 3:
        raise ValueError("position must be f32 or f64 with 3 components")
    seen = set()
    for f in fields:
        if f.name in seen:
            raise ValueError("two fields named %r" % f.name)
        seen.add(f.name)
        if f.semantic == "color" and "color_space" not in f.extra:
            raise ValueError("field %r has semantic 'color' and no color_space; "
                             "points.layout.txt section 4 makes it mandatory"
                             % f.name)
        if f.semantic == "custom" and not f.name.startswith("x-"):
            raise ValueError("custom field %r must be named x-<something>" % f.name)
        if f.dtype in ("f32", "f64") and f.data.size and not np.isfinite(f.data).all():
            raise ValueError("field %r contains NaN or infinity" % f.name)

    count = len(fields[0].data)
    pos = fields[0].data
    header = {
        "count": int(count),
        "length_unit": "metre",
        "fields": [f.header_entry() for f in fields],
    }
    if count:
        header["bounds"] = {"min": [float(v) for v in pos.min(axis=0)],
                            "max": [float(v) for v in pos.max(axis=0)]}
    header.update(extra_header or {})
    return write_envelope(MAGIC, KIND, header,
                          [f.section(count) for f in fields])


# ---------------------------------------------------------------------------
# ingest: PLY -> WKPC
# ---------------------------------------------------------------------------

_COLOR_TRIPLES = [("red", "green", "blue", "alpha"), ("r", "g", "b", "a")]


def ingest_ply(path):
    ply = read_ply(path, want=("vertex",))
    el = ply.element("vertex")
    if el is None:
        raise ValueError("%s has no `vertex` element" % path)
    names = el.names()
    have = set(names)
    for req in ("x", "y", "z"):
        if req not in have:
            raise ValueError("%s has no %r property; a point cloud needs a "
                             "position" % (path, req))
    used = {"x", "y", "z"}
    reports = []

    faces = [e.name for e in ply.elements if e.name != "vertex"]
    if faces:
        reports.append("dropped non-vertex element(s) %s: a PLY with faces is a "
                       "mesh and belongs in core.geom.source, and discarding "
                       "them silently would turn a mesh into a point cloud "
                       "without telling anyone" % ", ".join(sorted(faces)))

    col = lambda n: np.asarray(el.data[n])  # noqa: E731
    fields = [Field("position", "position", "f32", 3,
                    np.stack([col("x"), col("y"), col("z")], 1).astype("<f4"),
                    unit="metre")]

    for triple in _COLOR_TRIPLES:
        r, g, b, a = triple
        if r in have and g in have and b in have:
            comps = [r, g, b] + ([a] if a in have else [])
            used.update(comps)
            src = np.stack([col(c) for c in comps], 1)
            if src.dtype.kind == "f":
                dtype, arr = "f32", src.astype("<f4")
            else:
                dtype, arr = "u8", src.astype("u1")
            fields.append(Field("color", "color", dtype, len(comps), arr,
                                color_space="srgb"))
            reports.append(
                "PLY does not declare a colour space for %s/%s/%s; ingested as "
                "'srgb' because every tool that writes those properties writes "
                "display-referred values, and the assumption is on the record "
                "here rather than being a fact nobody chose (D-PC-2)"
                % (r, g, b))
            break

    if {"nx", "ny", "nz"} <= have:
        used.update(("nx", "ny", "nz"))
        nn = np.stack([col("nx"), col("ny"), col("nz")], 1).astype("<f4")
        if np.all(nn == 0.0):
            reports.append(
                "dropped nx/ny/nz: all %d are exactly zero, which is the INRIA "
                "splat writer reusing a point-cloud writer. Carrying them as "
                "normals would be worse than carrying nothing, because a "
                "consumer would light with them" % (len(nn),))
        else:
            fields.append(Field("normal", "normal", "f32", 3, nn))

    for src_name, fname in (("intensity", "intensity"),
                            ("scalar_Intensity", "intensity")):
        if src_name in have and not any(f.name == "intensity" for f in fields):
            used.add(src_name)
            a = col(src_name)
            dt = "f32" if a.dtype.kind == "f" else "u16"
            fields.append(Field("intensity", "intensity", dt, 1,
                                a.astype(NP_OF[dt])))

    for src_name in ("classification", "class"):
        if src_name in have and not any(f.name == "classification" for f in fields):
            used.add(src_name)
            fields.append(Field("classification", "classification", "u8", 1,
                                col(src_name).astype("u1")))

    for n in names:
        if n in used:
            continue
        a = col(n)
        dt = {"f": "f32", "u": "u32", "i": "i32"}.get(a.dtype.kind)
        if dt is None:
            reports.append("skipped property %r: dtype %s has no werk equivalent"
                           % (n, a.dtype))
            continue
        if a.dtype.itemsize == 1 and a.dtype.kind == "u":
            dt = "u8"
        safe = "x-" + "".join(c if (c.isalnum()) else "-" for c in n.lower()).strip("-")
        fields.append(Field(safe, "custom", dt, 1, a.astype(NP_OF[dt]),
                            note="carried verbatim from PLY property %r" % n))

    extra = {
        "source": "ply",
        "producer": {"tool": TOOL, "version": TOOL_VERSION},
        "epistemic": "measured",
    }
    blob = build_wkpc(fields, extra)
    return blob, _stats(fields, blob, reports, ply.format)


def from_gsplat(means, sh_dc, extra_header=None):
    """The normative splat -> point-cloud degradation. See the module docstring
    and gsplat.layout.txt section 7."""
    rgb = dc_to_linear_rgb(sh_dc)
    u8 = np.clip(np.rint(rgb * 255.0), 0, 255).astype("u1")
    fields = [
        Field("position", "position", "f32", 3,
              np.ascontiguousarray(means, dtype="<f4"), unit="metre"),
        Field("color", "color", "u8", 3, u8, color_space="linear-srgb",
              note="the Gaussian splat's degree-0 SH band through "
                   "clamp(0.5 + 0.28209479177387814*dc, 0, 1), quantised to 8 "
                   "bits per channel. LINEAR, not sRGB-encoded: apply the "
                   "transfer function before display."),
    ]
    extra = {"source": "gsplat-dc-band",
             "producer": {"tool": TOOL, "version": TOOL_VERSION},
             "epistemic": "measured"}
    extra.update(extra_header or {})
    blob = build_wkpc(fields, extra)
    return blob, _stats(fields, blob, [], "n/a (derived from a WKGS payload)")


def _stats(fields, blob, reports, source_format):
    pos = fields[0].data
    return {
        "count": int(len(pos)),
        "fields": [f.header_entry() for f in fields],
        "field_names": [f.name for f in fields],
        "bytes": len(blob),
        "bytes_per_point": (len(blob) / len(pos)) if len(pos) else 0.0,
        "bounds_min_m": [float(v) for v in pos.min(axis=0)] if len(pos) else [0, 0, 0],
        "bounds_max_m": [float(v) for v in pos.max(axis=0)] if len(pos) else [0, 0, 0],
        "source_format": source_format,
        "reports": reports,
    }


def run(ctx, node_id, path, blob, stats, note, epistemic="measured",
        inputs=None, params=None, edges=(), part=None):
    """Put an already-built WKPC into `ctx`. The blob is built by `ingest_ply`
    or `from_gsplat`; keeping the two apart is what lets the gate build one
    without a package and the fixture build one inside a package."""
    f = ctx.put(path, blob)
    ctx.node(node_id, KIND,
             ctx.version([f], note, epistemic, inputs=inputs,
                         params=dict(params or {}), tool=TOOL, tver=TOOL_VERSION),
             edges=[dict(e) for e in edges], part=part,
             meta={"point_count": stats["count"],
                   "fields": [f2["name"] for f2 in stats["fields"]],
                   "bytes_per_point": round(stats["bytes_per_point"], 3)})
    ctx.layouts[KIND] = LAYOUT
    return stats


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--json")
    args = ap.parse_args(argv)
    blob, stats = ingest_ply(args.input)
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

```

##### `tools/werk-pointcloud/ply.py`

```python
#!/usr/bin/env python3
"""ply.py — a PLY reader with no dependencies beyond numpy, and the INRIA
3D-Gaussian-Splatting field convention it has to recognise.

Two formats are in scope and both are mandatory (Stage 12 brief): `ascii 1.0`
and `binary_little_endian 1.0`. `binary_big_endian 1.0` is read too, because
refusing it would cost four lines and returning wrong numbers costs a user a
day — but nothing in werk ever WRITES one.

WHY A READER LIVES HERE AT ALL. A point cloud or a Gaussian splat arrives as a
PLY, always: it is what every splat trainer emits and what every scanner
exports. `plyfile` and `open3d` both read one, and both are a pip install —
which is fine for a pipeline (law 1 governs what travels inside a package, not
what built it) but bad for a file that wants to be its own converter's home.
This module is 300 lines and is embedded into the packages it produces as a
`core.tool` node, so the package carries the code that read its own input.

WHAT A GAUSSIAN SPLAT PLY LOOKS LIKE. The reference implementation
(graphdeco-inria/gaussian-splatting, `GaussianModel.save_ply`) writes one
`vertex` element with these properties, all f32, in this order:

    x y z                        the mean, in the scene's own units
    nx ny nz                     ALWAYS ZERO. Written because the original
                                 code reuses a point-cloud writer; a reader
                                 that trusts them gets a black render.
    f_dc_0 f_dc_1 f_dc_2         the degree-0 SH coefficient, per RGB channel
    f_rest_0 .. f_rest_{3K-4}    the remaining K-1 coefficients, CHANNEL-MAJOR:
                                 all K-1 of red, then all of green, then blue.
                                 K = (sh_degree+1)**2.
    opacity                      LOGIT space: alpha = sigmoid(opacity)
    scale_0 scale_1 scale_2      LOG space, natural log: metres = exp(scale)
    rot_0 rot_1 rot_2 rot_3      a quaternion, and its component order is the
                                 one field of the whole convention that is not
                                 stable — see `detect_gsplat`.

Every one of those facts is a decode step, not a copy, and getting one wrong
produces a file that looks plausible and renders wrong. `detect_gsplat` returns
them as a declared plan so the caller can print it and a human can check it.
"""

import re
import struct

import numpy as np

__all__ = ["PlyData", "PlyElement", "read_ply", "detect_gsplat", "GsplatPlan",
           "gsplat_arrays", "dc_to_linear_rgb", "write_ply_binary", "SH_C0"]

#: The degree-0 spherical-harmonic basis constant, 1/(2*sqrt(pi)). The DC
#: coefficient is turned into linear colour by `0.5 + SH_C0 * f_dc`, which is
#: the reference renderer's own arithmetic and is reproduced in
#: spec/layouts/gsplat.layout.txt section 6 so a foreign reader needs nothing
#: but the file.
SH_C0 = 0.28209479177387814

_SCALAR = {
    "char": "i1", "int8": "i1",
    "uchar": "u1", "uint8": "u1",
    "short": "i2", "int16": "i2",
    "ushort": "u2", "uint16": "u2",
    "int": "i4", "int32": "i4",
    "uint": "u4", "uint32": "u4",
    "float": "f4", "float32": "f4",
    "double": "f8", "float64": "f8",
}


class PlyElement(object):
    __slots__ = ("name", "count", "properties", "data")

    def __init__(self, name, count):
        self.name = name
        self.count = count
        #: list of (prop_name, scalar_type) or (prop_name, "list", count_type,
        #: item_type). A list property in an element werk reads is an error
        #: rather than a silently dropped column — see read_ply.
        self.properties = []
        self.data = None

    def names(self):
        return [p[0] for p in self.properties]

    def __repr__(self):
        return "<PlyElement %s count=%d props=%d>" % (
            self.name, self.count, len(self.properties))


class PlyData(object):
    __slots__ = ("format", "version", "elements", "comments", "header_bytes")

    def __init__(self):
        self.format = None
        self.version = None
        self.elements = []
        self.comments = []
        self.header_bytes = 0

    def element(self, name):
        for e in self.elements:
            if e.name == name:
                return e
        return None


def _parse_header(buf):
    """Split the header off the front. Returns (PlyData, offset_of_body).

    The header is ASCII and line-oriented and ends with a line `end_header`.
    Line endings are not specified by the PLY 'spec' (there is no normative
    one), so both LF and CRLF are accepted; this is the single most common
    reason a hand-written PLY reader rejects a real file.
    """
    end = buf.find(b"end_header")
    if end < 0:
        raise ValueError("not a PLY: no end_header in the file")
    nl = buf.find(b"\n", end)
    if nl < 0:
        raise ValueError("PLY header's end_header line is unterminated")
    head = buf[:nl + 1]
    text = head.decode("ascii", "replace")
    lines = [ln.strip() for ln in re.split(r"\r\n|\n|\r", text) if ln.strip()]
    if not lines or lines[0] != "ply":
        raise ValueError("not a PLY: the file does not begin with 'ply'")

    ply = PlyData()
    ply.header_bytes = nl + 1
    cur = None
    for ln in lines[1:]:
        parts = ln.split()
        key = parts[0]
        if key == "format":
            if len(parts) < 3:
                raise ValueError("malformed format line: %r" % ln)
            ply.format, ply.version = parts[1], parts[2]
        elif key == "comment" or key == "obj_info":
            ply.comments.append(ln)
        elif key == "element":
            if len(parts) < 3:
                raise ValueError("malformed element line: %r" % ln)
            cur = PlyElement(parts[1], int(parts[2]))
            ply.elements.append(cur)
        elif key == "property":
            if cur is None:
                raise ValueError("property outside any element: %r" % ln)
            if parts[1] == "list":
                cur.properties.append((parts[4], "list", parts[2], parts[3]))
            else:
                cur.properties.append((parts[2], parts[1]))
        elif key == "end_header":
            break
        else:
            # Law 12 in miniature: an unknown header line is skipped, not fatal.
            ply.comments.append("unknown-header-line " + ln)
    if ply.format not in ("ascii", "binary_little_endian", "binary_big_endian"):
        raise ValueError("unsupported PLY format %r" % ply.format)
    return ply


def read_ply(path, want=("vertex",)):
    """Read `path`. Returns a PlyData whose named elements carry numpy arrays.

    `want` names the elements whose data is materialised; every other element
    is still parsed structurally (so its bytes can be stepped over) but its
    data is left None. A splat PLY has exactly one element and a mesh PLY has
    two, and reading a 100 MB face list nobody asked for is the difference
    between a 2-second ingest and a 40-second one.
    """
    with open(path, "rb") as fh:
        buf = fh.read()
    ply = _parse_header(buf)
    off = ply.header_bytes

    if ply.format == "ascii":
        body = buf[off:].decode("ascii", "replace").split()
        cursor = 0
        for el in ply.elements:
            if any(p[1] == "list" for p in el.properties):
                raise ValueError(
                    "element %r has a list property; werk's PLY ingesters read "
                    "fixed per-vertex fields only" % el.name)
            ncol = len(el.properties)
            take = el.count * ncol
            chunk = body[cursor:cursor + take]
            if len(chunk) != take:
                raise ValueError(
                    "element %r declares %d rows x %d columns = %d values, the "
                    "file has %d" % (el.name, el.count, ncol, take, len(chunk)))
            cursor += take
            if el.name in want:
                dt = np.dtype([(p[0], _dtype_of(p[1], "<")) for p in el.properties])
                arr = np.empty(el.count, dtype=dt)
                flat = np.array(chunk)
                for i, p in enumerate(el.properties):
                    arr[p[0]] = flat[i::ncol].astype(dt[i])
                el.data = arr
        return ply

    endian = "<" if ply.format == "binary_little_endian" else ">"
    for el in ply.elements:
        if any(p[1] == "list" for p in el.properties):
            raise ValueError(
                "element %r has a list property; werk's PLY ingesters read "
                "fixed per-vertex fields only" % el.name)
        dt = np.dtype([(p[0], _dtype_of(p[1], endian)) for p in el.properties])
        need = dt.itemsize * el.count
        if off + need > len(buf):
            raise ValueError(
                "element %r declares %d rows of %d bytes = %d, but only %d bytes "
                "follow the header" % (el.name, el.count, dt.itemsize, need,
                                       len(buf) - off))
        if el.name in want:
            el.data = np.frombuffer(buf, dtype=dt, count=el.count, offset=off)
        off += need
    return ply


def _dtype_of(kind, endian):
    try:
        code = _SCALAR[kind]
    except KeyError:
        raise ValueError("unknown PLY scalar type %r" % kind)
    return endian + code if code[0] in "iuf" and code != "i1" and code != "u1" else code


# ---------------------------------------------------------------------------
# the INRIA Gaussian-splat convention
# ---------------------------------------------------------------------------

class GsplatPlan(object):
    """The decode plan for one splat PLY, DECLARED rather than applied.

    Every attribute is a decision that a wrong answer to produces a file that
    parses, renders, and is wrong. Printing this object is how a human checks
    an ingest before 100 MB of it is written into a package.
    """

    __slots__ = ("count", "sh_degree", "sh_coeff_count", "quat_order",
                 "scale_space", "opacity_space", "dc_names", "rest_names",
                 "scale_names", "rot_names", "opacity_name", "extra_names",
                 "quat_order_evidence", "quat_order_statistic",
                 "quat_order_inferred")

    def as_json(self):
        return {
            "count": int(self.count),
            "sh_degree": int(self.sh_degree),
            "sh_coeff_count": int(self.sh_coeff_count),
            "quat_order": self.quat_order,
            "quat_order_evidence": self.quat_order_evidence,
            "quat_order_statistic": self.quat_order_statistic,
            "quat_order_inferred": self.quat_order_inferred,
            "scale_space": self.scale_space,
            "opacity_space": self.opacity_space,
            "ignored_properties": list(self.extra_names),
        }

    def __repr__(self):
        return ("<GsplatPlan %d gaussians, sh_degree %d (%d coeffs), quat %s "
                "(%s), scales %s, opacity %s>"
                % (self.count, self.sh_degree, self.sh_coeff_count,
                   self.quat_order, self.quat_order_evidence, self.scale_space,
                   self.opacity_space))


def detect_gsplat(el, quat_order=None):
    """Decide whether a PLY `vertex` element is an INRIA Gaussian splat, and
    how to decode it. Raises ValueError when it is not one.

    The one genuinely ambiguous field is the quaternion order, and this is the
    honest state of the world: the reference implementation stores WXYZ, and
    several widely used exporters store XYZW under the same property names.
    Nothing in the file declares it. So:

      * an explicit `quat_order` argument always wins, and the plan records
        that a human said so;
      * otherwise the order is INFERRED from the data, by the one statistic
        that separates them: in a trained splat the great majority of
        rotations are near-identity-ish only in the sense that no component
        dominates, but the WXYZ convention's first component is the scalar
        part, whose ABSOLUTE MEAN is markedly higher than the three vector
        components' when the writer emitted w first. The plan records the two
        means and the word 'inferred', so the guess is visible and a consumer
        can override it.

    A guess that is recorded and a guess that is silent are different things;
    this returns the first. Spec finding S12-3.
    """
    names = el.names()
    have = set(names)
    for req in ("x", "y", "z", "opacity"):
        if req not in have:
            raise ValueError("not a Gaussian-splat PLY: no %r property" % req)
    dc = [n for n in ("f_dc_0", "f_dc_1", "f_dc_2") if n in have]
    if len(dc) != 3:
        raise ValueError("not a Gaussian-splat PLY: f_dc_0/1/2 are not all present")
    scale = sorted([n for n in names if re.fullmatch(r"scale_\d+", n)],
                   key=lambda n: int(n.split("_")[1]))
    rot = sorted([n for n in names if re.fullmatch(r"rot_\d+", n)],
                 key=lambda n: int(n.split("_")[1]))
    if len(scale) != 3:
        raise ValueError("expected scale_0..2, found %r" % (scale,))
    if len(rot) != 4:
        raise ValueError("expected rot_0..3, found %r" % (rot,))
    rest = sorted([n for n in names if re.fullmatch(r"f_rest_\d+", n)],
                  key=lambda n: int(n.split("_")[2]))

    if len(rest) % 3 != 0:
        raise ValueError(
            "f_rest_* count %d is not a multiple of 3; the INRIA layout stores "
            "(K-1) coefficients per RGB channel" % len(rest))
    k_minus_1 = len(rest) // 3
    k = k_minus_1 + 1
    degree = int(round(k ** 0.5)) - 1
    if (degree + 1) ** 2 != k:
        raise ValueError(
            "f_rest_* implies %d SH coefficients, which is not (degree+1)**2 "
            "for any integer degree" % k)

    plan = GsplatPlan()
    plan.count = int(el.count)
    plan.sh_degree = degree
    plan.sh_coeff_count = k
    plan.dc_names = ["f_dc_0", "f_dc_1", "f_dc_2"]
    plan.rest_names = rest
    plan.scale_names = scale
    plan.rot_names = rot
    plan.opacity_name = "opacity"
    plan.scale_space = "log"
    plan.opacity_space = "logit"
    known = set(plan.dc_names) | set(rest) | set(scale) | set(rot) | {
        "x", "y", "z", "opacity", "nx", "ny", "nz"}
    plan.extra_names = [n for n in names if n not in known]

    # The statistic is computed ALWAYS, even when the caller declares the
    # order. It costs one pass and it is the number spec/layouts/
    # gsplat.layout.txt section 6 demands be recorded -- and a declared order
    # whose supporting measurement is absent is exactly the empty spot a cold
    # reader found in the first gsplat package (Stage 12 mini-gauntlet, note 3).
    # Declared still WINS; the measurement is evidence beside it, never over it.
    q = np.stack([np.asarray(el.data[n], dtype=np.float64) for n in rot], 1)
    nq = np.linalg.norm(q, axis=1)
    nq[nq == 0] = 1.0
    q = q / nq[:, None]
    m = np.abs(q).mean(axis=0)
    first, rest_mean = float(m[0]), float(m[1:].mean())
    last, head_mean = float(m[3]), float(m[:3].mean())
    if first >= rest_mean and first >= last:
        inferred = "wxyz"
        stat = ("mean|q0| %.4f vs mean of the other three %.4f"
                % (first, rest_mean))
        strength = "inferred"
    elif last > head_mean:
        inferred = "xyzw"
        stat = ("mean|q3| %.4f vs mean of the other three %.4f"
                % (last, head_mean))
        strength = "inferred"
    else:
        inferred = "wxyz"
        stat = ("no component dominates (mean absolute components %s)"
                % " ".join("%.4f" % v for v in m))
        strength = "inferred WEAKLY"
    plan.quat_order_statistic = stat
    plan.quat_order_inferred = inferred

    if quat_order is not None:
        if quat_order not in ("wxyz", "xyzw"):
            raise ValueError("quat_order must be 'wxyz' or 'xyzw'")
        plan.quat_order = quat_order
        plan.quat_order_evidence = (
            "declared by the caller as %r; the same pass measured %s, which "
            "would have %s %r"
            % (quat_order, stat,
               "agreed" if inferred == quat_order else "DISAGREED and chosen",
               inferred))
    else:
        plan.quat_order = inferred
        plan.quat_order_evidence = "%s: %s" % (strength, stat)
    return plan


def gsplat_arrays(el, plan):
    """Apply `plan` to `el.data`. Returns werk-space arrays, all float32:

        means      [N,3]   as they are in the file, no unit change
        scales     [N,3]   LINEAR metres, exp() of the stored log scales
        rotations  [N,4]   wxyz, unit length, w >= 0 (the werk canonical sign)
        opacities  [N]     LINEAR alpha in [0,1], sigmoid() of the stored logit
        sh         [N,K,3] COEFFICIENT-MAJOR: sh[i,c] is coefficient c's RGB

    Every transform here is named in spec/layouts/gsplat.layout.txt section 6
    together with its exact inverse, so nothing in this function is knowledge a
    foreign reader has to have.
    """
    d = el.data
    f = lambda n: np.asarray(d[n], dtype=np.float64)  # noqa: E731

    means = np.stack([f("x"), f("y"), f("z")], 1)
    scales = np.exp(np.stack([f(n) for n in plan.scale_names], 1))
    op = f(plan.opacity_name)
    opac = 1.0 / (1.0 + np.exp(-op))

    q = np.stack([f(n) for n in plan.rot_names], 1)
    if plan.quat_order == "xyzw":
        q = q[:, [3, 0, 1, 2]]
    nrm = np.linalg.norm(q, axis=1)
    nrm[nrm == 0] = 1.0
    q = q / nrm[:, None]
    # ENVELOPE.layout.txt section 6: "w >= 0 is the canonical sign; writers
    # MUST emit the w >= 0 representative". q and -q are the same rotation, so
    # this changes no geometry and makes two writers agree byte for byte.
    q = np.where(q[:, :1] < 0, -q, q)

    k = plan.sh_coeff_count
    sh = np.empty((len(means), k, 3), dtype=np.float64)
    sh[:, 0, 0] = f("f_dc_0")
    sh[:, 0, 1] = f("f_dc_1")
    sh[:, 0, 2] = f("f_dc_2")
    if k > 1:
        # f_rest_* is CHANNEL-MAJOR in the source: (K-1) reds, then greens,
        # then blues. werk stores COEFFICIENT-MAJOR. This transpose is the
        # whole difference and it is the second-easiest thing to get wrong
        # after the quaternion order.
        km1 = k - 1
        rest = np.stack([f(n) for n in plan.rest_names], 1)      # [N, 3*(K-1)]
        rest = rest.reshape(len(means), 3, km1)                   # [N,3,K-1]
        sh[:, 1:, :] = np.transpose(rest, (0, 2, 1))              # [N,K-1,3]

    return (means.astype(np.float32), scales.astype(np.float32),
            q.astype(np.float32), opac.astype(np.float32), sh.astype(np.float32))


def dc_to_linear_rgb(sh_dc):
    """The degree-0 band evaluated in the direction-independent way every
    renderer uses for a first approximation, and the ONLY thing a
    means-and-colour reader needs (spec/SPEC.md section 3.16, law 9)."""
    return np.clip(0.5 + SH_C0 * np.asarray(sh_dc, dtype=np.float64), 0.0, 1.0)


def write_ply_binary(path, count, columns, comments=()):
    """Write a binary_little_endian PLY. `columns` is an ordered list of
    (property_name, numpy array of shape [count]) — all float32 here, because
    every INRIA splat property is.

    This exists so the ingest path has a WRITER to test itself against, and so
    that a source that is not a PLY can be turned into one by a tool the
    package carries rather than by something a reader has to trust.
    """
    head = ["ply", "format binary_little_endian 1.0"]
    head += ["comment " + c for c in comments]
    head.append("element vertex %d" % count)
    for name, _arr in columns:
        head.append("property float %s" % name)
    head.append("end_header")
    blob = ("\n".join(head) + "\n").encode("ascii")
    dt = np.dtype([(name, "<f4") for name, _ in columns])
    rec = np.empty(count, dtype=dt)
    for name, arr in columns:
        rec[name] = np.asarray(arr, dtype=np.float32)
    with open(path, "wb") as fh:
        fh.write(blob)
        fh.write(rec.tobytes())
    return len(blob) + rec.nbytes


def _selftest():
    """Round-trip the writer through the reader, in both encodings."""
    import io
    import os
    import tempfile
    n = 7
    rng = np.random.RandomState(12345)
    cols = [("x", rng.randn(n)), ("y", rng.randn(n)), ("z", rng.randn(n)),
            ("f_dc_0", rng.randn(n)), ("f_dc_1", rng.randn(n)),
            ("f_dc_2", rng.randn(n)), ("opacity", rng.randn(n)),
            ("scale_0", rng.randn(n)), ("scale_1", rng.randn(n)),
            ("scale_2", rng.randn(n)),
            ("rot_0", np.abs(rng.randn(n)) + 1.0), ("rot_1", rng.randn(n)),
            ("rot_2", rng.randn(n)), ("rot_3", rng.randn(n))]
    tmp = os.path.join(tempfile.gettempdir(), "werk-ply-selftest.ply")
    write_ply_binary(tmp, n, cols)
    ply = read_ply(tmp)
    el = ply.element("vertex")
    plan = detect_gsplat(el)
    assert plan.count == n and plan.sh_degree == 0, plan
    m, s, q, o, sh = gsplat_arrays(el, plan)
    assert m.shape == (n, 3) and sh.shape == (n, 1, 3)
    assert np.allclose(np.linalg.norm(q, axis=1), 1.0, atol=1e-6)
    assert (q[:, 0] >= 0).all()
    os.remove(tmp)

    # ascii, same numbers
    lines = ["ply", "format ascii 1.0", "element vertex %d" % n]
    lines += ["property float %s" % c[0] for c in cols]
    lines.append("end_header")
    for i in range(n):
        lines.append(" ".join(repr(float(np.float32(c[1][i]))) for c in cols))
    tmp2 = os.path.join(tempfile.gettempdir(), "werk-ply-selftest-ascii.ply")
    with open(tmp2, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    ply2 = read_ply(tmp2)
    m2, s2, q2, o2, sh2 = gsplat_arrays(ply2.element("vertex"),
                                        detect_gsplat(ply2.element("vertex")))
    assert np.allclose(m, m2, atol=1e-6) and np.allclose(sh, sh2, atol=1e-6)
    os.remove(tmp2)
    print("ply.py selftest OK (binary + ascii round trip, %d vertices)" % n)
    return True


if __name__ == "__main__":
    _selftest()

```

##### `tools/werk-pointcloud/common.py`

```python
#!/usr/bin/env python3
"""common.py — the parts every producer in the enrichment pipeline shares.

Hashing, the on-disk JSON spelling, the node/version builders, the canonical
MessagePack encoder and the binary-envelope writer, and the zip writer that is
byte-for-byte what `core/src/zipstore.rs` emits.

Nothing here is werk-specific policy; the policy lives in `spec/` and in the
producer modules. This file is the plumbing, and it is deliberately the only
place in the pipeline that knows how to turn bytes into a container.

Stdlib only, except `werkstore.ed25519` (itself stdlib-only) for signing.
"""

import hashlib
import json
import math
import os
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if os.path.join(ROOT, "store") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "store"))

TOOL = "pipeline/enrich.py"
TOOL_VERSION = "0.1"


# ---------------------------------------------------------------------------
# hashing, JSON, ids
# ---------------------------------------------------------------------------

def sha256(b):
    return hashlib.sha256(b).hexdigest()


def jbytes(v):
    """The on-disk spelling werk uses: two-space indent, trailing newline."""
    return (json.dumps(v, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def canon(v):
    """Canonical JSON, as `input_params` is hashed (MINI-SPECS section 11)."""
    return json.dumps(v, sort_keys=True, separators=(",", ":")).encode("utf-8")


def uuid_from(seed_bytes):
    """A deterministic RFC-4122 v4-shaped uuid derived from content.

    A pipeline that stamped a random uuid would make two runs over one GLB
    two different entities, which is a lie about identity (law 4). Derived
    from the source bytes, the uuid says 'this entity is that GLB enriched'
    and says it the same way on every machine.
    """
    d = hashlib.sha256(b"werk-entity-uuid/1\x00" + seed_bytes).digest()
    b = bytearray(d[:16])
    b[6] = (b[6] & 0x0F) | 0x40
    b[8] = (b[8] & 0x3F) | 0x80
    h = b.hex()
    return "%s-%s-%s-%s-%s" % (h[0:8], h[8:12], h[12:16], h[16:20], h[20:32])


def kebab(s):
    out = []
    prev_dash = True
    for ch in s.lower():
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        elif not prev_dash:
            out.append("-")
            prev_dash = True
    while out and out[-1] == "-":
        out.pop()
    return "".join(out) or "entity"


# ---------------------------------------------------------------------------
# canonical MessagePack (writer subset of ENVELOPE.layout.txt section 4)
# ---------------------------------------------------------------------------

def mp_encode(v):
    if v is True:
        return b"\xc3"
    if v is False:
        return b"\xc2"
    if v is None:
        raise ValueError("werk headers never carry nil; omit the key instead")
    if isinstance(v, int):
        if 0 <= v <= 127:
            return struct.pack("B", v)
        if -32 <= v < 0:
            return struct.pack("b", v)
        if 0 <= v <= 0xFF:
            return b"\xcc" + struct.pack(">B", v)
        if 0 <= v <= 0xFFFF:
            return b"\xcd" + struct.pack(">H", v)
        if 0 <= v <= 0xFFFFFFFF:
            return b"\xce" + struct.pack(">I", v)
        if 0 <= v <= 0xFFFFFFFFFFFFFFFF:
            return b"\xcf" + struct.pack(">Q", v)
        if -0x80 <= v < 0:
            return b"\xd0" + struct.pack(">b", v)
        if -0x8000 <= v < 0:
            return b"\xd1" + struct.pack(">h", v)
        if -0x80000000 <= v < 0:
            return b"\xd2" + struct.pack(">i", v)
        return b"\xd3" + struct.pack(">q", v)
    if isinstance(v, float):
        # section 4.3: every non-integral number is float64, never float32.
        if math.isnan(v) or math.isinf(v):
            raise ValueError("no NaN and no infinity in a werk payload")
        return b"\xcb" + struct.pack(">d", v)
    if isinstance(v, str):
        b = v.encode("utf-8")
        n = len(b)
        if n <= 31:
            return struct.pack("B", 0xA0 | n) + b
        if n <= 0xFF:
            return b"\xd9" + struct.pack(">B", n) + b
        if n <= 0xFFFF:
            return b"\xda" + struct.pack(">H", n) + b
        return b"\xdb" + struct.pack(">I", n) + b
    if isinstance(v, (list, tuple)):
        n = len(v)
        if n <= 15:
            head = struct.pack("B", 0x90 | n)
        elif n <= 0xFFFF:
            head = b"\xdc" + struct.pack(">H", n)
        else:
            head = b"\xdd" + struct.pack(">I", n)
        return head + b"".join(mp_encode(x) for x in v)
    if isinstance(v, dict):
        items = sorted(v.items(), key=lambda kv: kv[0].encode("utf-8"))
        n = len(items)
        if n <= 15:
            head = struct.pack("B", 0x80 | n)
        elif n <= 0xFFFF:
            head = b"\xde" + struct.pack(">H", n)
        else:
            head = b"\xdf" + struct.pack(">I", n)
        return head + b"".join(mp_encode(k) + mp_encode(x) for k, x in items)
    raise TypeError("not encodable in the werk MessagePack subset: %r" % type(v))


DTYPE_SIZE = {"u8": 1, "i8": 1, "u16": 2, "i16": 2, "u32": 4, "i32": 4,
              "u64": 8, "i64": 8, "f32": 4, "f64": 8}


def write_envelope(magic, kind, header_extra, sections):
    """Build a conformant werk binary envelope.

    `sections` is a list of (name, dtype, shape, stride, payload_bytes) in file
    order. Offsets, sizes, payload_origin and payload_size are computed here
    and DECLARED in the header — never left for a reader to derive (law 8).
    The section consistency rule of ENVELOPE.layout.txt section 3 is asserted
    on the way out, so a malformed writer fails here and not in someone else's
    reader.
    """
    assert len(magic) == 4
    # payload_origin depends on header_len, which depends on the offsets, which
    # depend on payload_origin. Iterate to the fixed point; it converges in two
    # rounds because only the digit count of the offsets can move.
    origin = 16
    for _ in range(8):
        secs, cursor = [], origin
        for name, dtype, shape, stride, data in sections:
            esz = DTYPE_SIZE.get(dtype, stride)
            prod_all = 1
            for d in shape:
                prod_all *= d
            if stride == esz:
                expect = stride * prod_all
            else:
                assert shape and stride >= esz * shape[-1], \
                    "%s: stride %d < esz %d * shape[-1] %d" % (name, stride, esz,
                                                               shape[-1] if shape else 0)
                prod_head = 1
                for d in shape[:-1]:
                    prod_head *= d
                expect = stride * prod_head
            assert len(data) == expect, \
                "%s: %d payload bytes, consistency rule says %d" % (name, len(data), expect)
            secs.append({"name": name, "offset": cursor, "size": len(data),
                         "dtype": dtype, "shape": [int(d) for d in shape],
                         "stride": int(stride)})
            cursor += len(data)
            cursor = (cursor + 15) // 16 * 16
        header = dict(header_extra)
        header.update({"kind": kind, "endianness": "le",
                       "payload_origin": origin, "payload_size": cursor - origin,
                       "sections": secs})
        hb = mp_encode(header)
        new_origin = 16 * ((12 + len(hb) + 15) // 16)
        if new_origin == origin:
            break
        origin = new_origin
    else:
        raise RuntimeError("envelope header size did not converge")

    out = bytearray()
    out += magic.encode("ascii") + struct.pack("<II", 1, len(hb)) + hb
    out += b"\x00" * (origin - len(out))
    for sec, (_n, _d, _s, _st, data) in zip(secs, sections):
        assert len(out) == sec["offset"]
        out += data
        pad = (16 - (len(out) % 16)) % 16
        out += b"\x00" * pad
    assert len(out) == origin + header["payload_size"]
    return bytes(out)


# ---------------------------------------------------------------------------
# zip writer — byte-for-byte what core/src/zipstore.rs::write_zip emits
# ---------------------------------------------------------------------------

CRC_TABLE = []
for _n in range(256):
    _c = _n
    for _ in range(8):
        _c = (_c >> 1) ^ (0xEDB88320 if _c & 1 else 0)
    CRC_TABLE.append(_c)


def crc32(data):
    c = 0xFFFFFFFF
    for b in data:
        c = (c >> 8) ^ CRC_TABLE[(c ^ b) & 0xFF]
    return c ^ 0xFFFFFFFF


DOS_TIME = (9 << 11) | (0 << 5)
DOS_DATE = ((2026 - 1980) << 9) | (8 << 5) | 8
FLAG_UTF8 = 0x0800


def write_zip(entries):
    out, central, count = bytearray(), bytearray(), 0
    for name, data in entries:
        lho = len(out)
        crc = crc32(data)
        nb = name.encode("utf-8")
        out += struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, FLAG_UTF8, 0, DOS_TIME,
                           DOS_DATE, crc, len(data), len(data), len(nb), 0)
        out += nb + data
        central += struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, 20, 20, FLAG_UTF8, 0,
                               DOS_TIME, DOS_DATE, crc, len(data), len(data), len(nb),
                               0, 0, 0, 0, 0, lho)
        central += nb
        count += 1
    cd_off, cd_size = len(out), len(central)
    out += central
    out += struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, count, count, cd_size, cd_off, 0)
    return bytes(out)


# ---------------------------------------------------------------------------
# the build context every producer writes into
# ---------------------------------------------------------------------------

class Report(object):
    """One line of the pipeline's own honesty. A producer that fails writes
    one of these and the run continues (the island rule): a failed producer
    yields a MISSING NODE plus a report, never a dead pipeline."""

    def __init__(self, stage, status, seconds, detail="", nodes=(), error=None):
        self.stage = stage
        self.status = status          # "ok" | "skipped" | "failed"
        self.seconds = seconds
        self.detail = detail
        self.nodes = list(nodes)
        self.error = error

    record_timings = True

    def as_json(self):
        d = {"stage": self.stage, "status": self.status, "nodes": self.nodes}
        if self.record_timings:
            d["wall_seconds"] = round(self.seconds, 4)
        if self.detail:
            d["detail"] = self.detail
        if self.error:
            d["error"] = self.error
        return d


class Ctx(object):
    def __init__(self, created, entity_uuid, name, record_timings=True):
        # Wall times are honest measurements of ONE run and therefore the one
        # thing in the package that cannot be byte-identical across runs.
        # `record_timings=False` drops them so that byte-identity becomes a
        # checkable property; it does not make the pipeline more deterministic,
        # it stops the package from recording the one thing that isn't.
        self.record_timings = record_timings
        self.files = {}
        self.nodes = []
        self.reports = []
        self.created = created
        self.entity_uuid = entity_uuid
        self.name = name
        self.parts = []
        self.materials = []
        self.schemas = {}
        self.layouts = {}
        self.primary = {}
        self.stats = {}
        self.notes = []

    # -- files ----------------------------------------------------------
    def put(self, path, data):
        if path in self.files:
            raise AssertionError("two nodes claim %s" % path)
        self.files[path] = data
        return {"path": path, "sha256": sha256(data), "size": len(data)}

    def input_hash(self, paths, params=None):
        """sha256 over each input's 32 RAW digest bytes in order, then the
        canonical JSON of input_params. The executable copy is werk-core's
        hashing.rs; this must agree with it byte for byte."""
        h = hashlib.sha256()
        for p in paths:
            h.update(hashlib.sha256(self.files[p]).digest())
        h.update(canon(params if params is not None else {}))
        return h.hexdigest()

    # -- nodes ----------------------------------------------------------
    def node(self, node_id, ntype, ver, edges=(), meta=None, part=None,
             material=None):
        n = {"node_id": node_id, "type": ntype, "versions": [ver], "active": 1,
             "edges": [dict(e) for e in edges]}
        if part:
            n["part_id"] = part
        if material:
            n["material_id"] = material
        if meta:
            n["meta"] = meta
        self.nodes.append(n)
        return n

    def version(self, fs, note, epistemic, inputs=None, params=None,
                confidence=None, tool=TOOL, tver=TOOL_VERSION, model=None):
        v = {"v": 1, "files": list(fs), "note": note,
             "producer": {"tool": tool, "version": tver},
             "epistemic": epistemic, "created": self.created}
        if model:
            v["producer"]["model"] = model
        if epistemic in ("measured", "inferred"):
            assert inputs, "%s node without input_files: law 5 forbids it" % epistemic
        if inputs:
            v["input_files"] = list(inputs)
            v["input_params"] = dict(params or {})
            v["input_hash"] = self.input_hash(inputs, v["input_params"])
        if confidence is not None:
            v["confidence"] = confidence
        return v

    # -- reports --------------------------------------------------------
    def report(self, r):
        r.record_timings = self.record_timings
        self.reports.append(r)
        return r


class Stage(object):
    """Context manager implementing the island rule.

        with Stage(ctx, "lod") as st:
            ...
            st.produced("geom-lod1")

    An exception inside the block is caught, timed, recorded as a failed
    stage, and swallowed. The pipeline continues and the package simply lacks
    that node — which the format says is legal and which is exactly the
    behaviour under test.
    """

    def __init__(self, ctx, name, verbose=True):
        self.ctx = ctx
        self.name = name
        self.verbose = verbose
        self.nodes = []
        self.detail = ""
        self.t0 = None
        self.ok = False

    def produced(self, *node_ids):
        self.nodes.extend(node_ids)

    def says(self, text):
        self.detail = text

    def __enter__(self):
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        dt = time.perf_counter() - self.t0
        if exc_type is None:
            self.ok = True
            r = Report(self.name, "ok", dt, self.detail, self.nodes)
        else:
            import traceback
            err = "".join(traceback.format_exception_only(exc_type, exc)).strip()
            r = Report(self.name, "failed", dt, self.detail, [], err)
            r.traceback = "".join(traceback.format_exception(exc_type, exc, tb))
        self.ctx.report(r)
        if self.verbose:
            print("  [%-7s] %-14s %7.2fs  %s" % (r.status, self.name, dt,
                                                 r.error or r.detail))
        return exc_type is not None       # swallow: the island rule


# ---------------------------------------------------------------------------
# PNG (writer only; Pillow is a PIPELINE dependency and never ships inside a
# package — law 1 governs what travels in the file, not what built it)
# ---------------------------------------------------------------------------

def png_bytes(arr, mode):
    """arr: numpy array. mode in {'RGBA','RGB','L16'}. Deterministic PNG."""
    import io
    import numpy as np
    from PIL import Image
    if mode == "L16":
        img = Image.fromarray(np.ascontiguousarray(arr.astype("<u2")), mode="I;16")
    else:
        img = Image.fromarray(np.ascontiguousarray(arr.astype("u1")), mode=mode)
    buf = io.BytesIO()
    # optimize=False + fixed compress_level keeps two runs byte-identical.
    img.save(buf, format="PNG", optimize=False, compress_level=6)
    return buf.getvalue()


def png_info(b):
    assert b[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    ln, tag = struct.unpack(">I4s", b[8:16])
    assert tag == b"IHDR" and ln == 13
    w, h, depth, ctype = struct.unpack(">IIBB", b[16:26])
    return {"width": w, "height": h, "bit_depth": depth, "color_type": ctype}


def srgb_to_linear_f(u8):
    s = u8 / 255.0
    return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4


def linear_to_srgb_f(x):
    x = max(0.0, min(1.0, x))
    return x * 12.92 if x <= 0.0031308 else 1.055 * (x ** (1.0 / 2.4)) - 0.055


def hexcolor(rgb_lin):
    return "#" + "".join("%02x" % int(round(linear_to_srgb_f(c) * 255.0))
                         for c in rgb_lin)

```

### Tool configurations

#### `tools/splat-to-ply-run.config.json`

```json
{
  "schema_version": 1,
  "config_id": "splat-to-ply-run",
  "tool_node": "tool-splat-to-ply",
  "params": {
    "input": "recipe/inputs/plush.splat",
    "output": "plush.ply",
    "alpha_clamp": [
      0.00196078431372549,
      0.9980392156862745
    ],
    "alpha_clamped_count": 33401,
    "degenerate_quaternions": 0,
    "quat_order_in": "wxyz",
    "quat_order_out": "wxyz",
    "transforms": {
      "scale": "log(linear)",
      "opacity": "logit(clamp(alpha_u8/255))",
      "sh_dc": "((rgb_u8/255) - 0.5) / 0.28209479177387814",
      "rotation": "(u8 - 128)/128, renormalised, w>=0"
    }
  },
  "params_provenance": "recorded",
  "environment": {
    "platform": "win32",
    "runtime_version": "CPython 3.10.0",
    "library_versions": {
      "numpy": "1.26.4"
    },
    "device": "cpu",
    "note": "The arithmetic is numpy float64 throughout with a float32 store; exp, log and the logistic function are the only libm calls, and they are the reason this run is reproducible to the bit on this machine and to ~1 ulp across machines."
  },
  "determinism": "deterministic",
  "determinism_note": "Every operation is a fixed-point arithmetic transform of the input bytes with no random source and no wall-clock input, so two runs on this machine produce the same 15764528-byte PLY; the recipe carries that file's sha256 and the gate re-runs the conversion and compares.",
  "unrecorded": [
    "the exact libm build that evaluated log(); its last-bit result is the only thing that could differ across machines, and only in the final float32 rounding"
  ],
  "ran_at": "2026-08-08T00:00:00Z",
  "note": "33401 of 281498 alpha values were at a byte endpoint and were clamped half a quantisation step inwards before the logit, because logit(0) and logit(1) are infinities and ENVELOPE.layout.txt section 6 forbids one in a core payload. The count is here rather than in a comment because a conversion that silently clamped and a conversion that silently produced infinities are both wrong."
}

```

#### `tools/werk-gsplat-run.config.json`

```json
{
  "schema_version": 1,
  "config_id": "werk-gsplat-run",
  "tool_node": "tool-werk-gsplat",
  "params": {
    "input": "plush.ply",
    "output": "splats/plush.wkgs",
    "quat_order": "wxyz",
    "quat_order_source": "declared by the caller",
    "source_convention": "inria-3dgs/1",
    "activation": {
      "scale": "exp",
      "opacity": "sigmoid",
      "sh": "identity"
    },
    "sh_coeff_order": "coefficient-major",
    "resample": false,
    "recentre": false,
    "rescale": false
  },
  "params_provenance": "recorded",
  "environment": {
    "platform": "win32",
    "runtime_version": "CPython 3.10.0",
    "library_versions": {
      "numpy": "1.26.4"
    },
    "device": "cpu",
    "note": "The arithmetic is numpy float64 throughout with a float32 store; exp, log and the logistic function are the only libm calls, and they are the reason this run is reproducible to the bit on this machine and to ~1 ulp across machines."
  },
  "determinism": "deterministic",
  "determinism_note": "exp() and the logistic function are the only inexact operations and both are applied elementwise to declared inputs; the writer emits a canonical MessagePack header, so the 15764784-byte payload is byte-identical across runs on this machine.",
  "unrecorded": [],
  "ran_at": "2026-08-08T00:00:00Z",
  "note": "quat_order was DECLARED rather than inferred, and the same pass measured the statistic anyway: mean|q0| 0.8647 vs mean of the other three 0.2188. A declared value and an inferred one are different claims, so the package records which this is AND what the measurement would have said (S12-3). The first cold reader of this fixture found this exact sentence empty, because the writer interpolated an evidence string that said only 'declared by the caller'; the statistic is computed unconditionally now."
}

```

#### `tools/werk-pointcloud-run.config.json`

```json
{
  "schema_version": 1,
  "config_id": "werk-pointcloud-run",
  "tool_node": "tool-werk-pointcloud",
  "params": {
    "producer": "from_gsplat",
    "input_sections": [
      "means",
      "sh-dc"
    ],
    "color_dtype": "u8",
    "color_space": "linear-srgb",
    "sh_c0": 0.28209479177387814,
    "formula": "clamp(0.5 + sh_c0 * dc, 0, 1) * 255, rounded half to even",
    "decimate": false,
    "resample": false
  },
  "params_provenance": "recorded",
  "environment": {
    "platform": "win32",
    "runtime_version": "CPython 3.10.0",
    "library_versions": {
      "numpy": "1.26.4"
    },
    "device": "cpu",
    "note": "The arithmetic is numpy float64 throughout with a float32 store; exp, log and the logistic function are the only libm calls, and they are the reason this run is reproducible to the bit on this machine and to ~1 ulp across machines."
  },
  "determinism": "deterministic",
  "determinism_note": "Three multiplies, a clamp and a round-to-nearest-even on declared inputs. No libm call at all.",
  "unrecorded": [],
  "ran_at": "2026-08-08T00:00:00Z",
  "note": "The colour is quantised to 8 bits per channel, which is the one lossy step in this package. It is lossy against the DC band, not against the splat: the splat keeps its f32 sh-dc section and a consumer that wants full precision reads that. Measured on this asset it is lossless in practice: the source's colours were 8-bit to begin with and never left the 1/255 lattice, which the first cold reader of this fixture verified over all 281 498 points."
}

```

## Files read, in order

1. `MANIFEST.json` (t=0.0s)
2. `SIGNATURE.json` (t=0.0s)
3. `splats/plush.wkgs` (t=0.1s)
4. `points/plush-dc.wkpc` (t=0.4s)
5. `tools/splat-to-ply/tool.json` (t=0.6s)
6. `tools/splat-to-ply/splat_to_ply.py` (t=0.6s)
7. `tools/splat-to-ply/ply.py` (t=0.6s)
8. `tools/werk-gsplat/tool.json` (t=0.6s)
9. `tools/werk-gsplat/p_gsplat.py` (t=0.6s)
10. `tools/werk-gsplat/ply.py` (t=0.6s)
11. `tools/werk-gsplat/common.py` (t=0.6s)
12. `tools/werk-pointcloud/tool.json` (t=0.6s)
13. `tools/werk-pointcloud/p_pointcloud.py` (t=0.6s)
14. `tools/werk-pointcloud/ply.py` (t=0.6s)
15. `tools/werk-pointcloud/common.py` (t=0.6s)
16. `tools/splat-to-ply-run.config.json` (t=0.6s)
17. `tools/werk-gsplat-run.config.json` (t=0.6s)
18. `tools/werk-pointcloud-run.config.json` (t=0.6s)

**Which file unblocked the decode:** `spec/layouts/gsplat.layout.txt` together with `spec/examples/gsplat.example.hex.txt` — the layout gave the section table and the colour formula, and the worked hex dump confirmed the MessagePack header structure and section offsets.

## Anything wanted from outside the file

Nothing. Every rule (zip, MessagePack subset, envelope layout, WKGS/WKPC layout, colour formula) was derived from files inside the package. No web, no external libraries beyond the Python standard library.

## Stumbles (honest)

- Initially I considered using the bundled `loaders/werk_read.py` as a shortcut, but the task forbids executing anything from the file and also asks to derive rules from the file itself, so I did not open it. (I did not even read it, to avoid any temptation to port it.)

- The MessagePack header is big-endian while the payload is little-endian; I had to be careful to implement the decoder exactly per ENVELOPE.layout.txt §4. The worked example in `spec/examples/gsplat.example.hex.txt` was essential to confirm the header structure.

- The `sh-rest` section is size 0 for SH degree 0; I initially expected it to be absent, but the spec says it must be present with size 0. The envelope consistency rule handles this correctly.

- The WKPC colour is u8 quantised, so comparing WKGS-derived float colours to WKPC bytes required a tolerance of 1/255.

- I had to implement a small MessagePack decoder from scratch; the spec's table was complete but I still double-checked against the hex dump.


## Wall-clock sense

- Reading manifest and understanding package structure: ~2 min
- Implementing MessagePack and envelope parsing: ~10 min
- Extracting points and colours: ~3 min
- Reading tool sources and writing report: ~5 min
- Total wall-clock: ~20 min (program runtime: 0.6s)
