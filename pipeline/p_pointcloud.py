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
