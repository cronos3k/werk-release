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
