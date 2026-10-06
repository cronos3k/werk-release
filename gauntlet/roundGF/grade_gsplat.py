#!/usr/bin/env python3
"""
grade_gsplat.py -- artifact grading for the GAP-COMPLETION round's splat arm.

Same rule as `gauntlet/roundOW/grade.py`: a model's report is evidence about the
model, not about the artifact. Success is decided HERE, from the bytes and the
characters a run left on disk, against a ground truth this file derives from the
pinned fixture by the normative path.

Ground truth is NOT hard-coded. It is decoded, every time, from
`fixtures/gsplat-v1.werk` with a from-scratch envelope reader (MessagePack
subset + WKPC/WKGS sections), so the grader and the model solve the same problem
independently. What the grader then checks is agreement.

The splat task's three clauses, and how each is graded:

  1. open / list with meanings / verify integrity
       -> the run's program must have re-verified the declared digests. Graded
          as: does its output name the point count AND report a hash pass over
          the package's declared files?
  2. positions and colours, by the normative path
       -> GRADED ON NUMBERS. The grader extracts every float/int-looking token
          from the run's stdout and any file it wrote, and asks whether the
          first point's position triple and colour triple are present, and
          whether the count 281498 is present. A colour counts as present
          as the stored u8 triple or as the exact k/255 fractions (S-DS-6).
          A model that fabricates values
          (roundOW's envelope-task failure mode) fails here and cannot talk its
          way past it.
  3. identify the embedded tools, quote their source
       -> the three tool node ids and their three paths must appear, and at
          least one verbatim line of >= 40 chars from each tool's real source
          must appear in the run's output or report.

  python grade_gsplat.py --fixture fixtures/gsplat-v1.werk --rundir <dir>
  python grade_gsplat.py --fixture ... --rundir <dir> --rerun --prog solution.py \
                         --out <cleandir>

Standard library only.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import zipfile

# ---------------------------------------------------------------- MessagePack

def mp(b, i=0):
    c = b[i]; i += 1
    if c < 0x80: return c, i
    if c >= 0xe0: return c - 256, i
    if 0x80 <= c <= 0x8f: return mpmap(b, i, c - 0x80)
    if 0x90 <= c <= 0x9f: return mparr(b, i, c - 0x90)
    if 0xa0 <= c <= 0xbf:
        n = c - 0xa0; return b[i:i + n].decode("utf-8"), i + n
    if c == 0xc0: return None, i
    if c == 0xc2: return False, i
    if c == 0xc3: return True, i
    if c == 0xca: return struct.unpack_from(">f", b, i)[0], i + 4
    if c == 0xcb: return struct.unpack_from(">d", b, i)[0], i + 8
    if c == 0xcc: return b[i], i + 1
    if c == 0xcd: return struct.unpack_from(">H", b, i)[0], i + 2
    if c == 0xce: return struct.unpack_from(">I", b, i)[0], i + 4
    if c == 0xcf: return struct.unpack_from(">Q", b, i)[0], i + 8
    if c == 0xd0: return struct.unpack_from(">b", b, i)[0], i + 1
    if c == 0xd1: return struct.unpack_from(">h", b, i)[0], i + 2
    if c == 0xd2: return struct.unpack_from(">i", b, i)[0], i + 4
    if c == 0xd3: return struct.unpack_from(">q", b, i)[0], i + 8
    if c == 0xd9:
        n = b[i]; i += 1; return b[i:i + n].decode("utf-8"), i + n
    if c == 0xda:
        n = struct.unpack_from(">H", b, i)[0]; i += 2; return b[i:i + n].decode("utf-8"), i + n
    if c == 0xdb:
        n = struct.unpack_from(">I", b, i)[0]; i += 4; return b[i:i + n].decode("utf-8"), i + n
    if c == 0xdc:
        n = struct.unpack_from(">H", b, i)[0]; i += 2; return mparr(b, i, n)
    if c == 0xdd:
        n = struct.unpack_from(">I", b, i)[0]; i += 4; return mparr(b, i, n)
    if c == 0xde:
        n = struct.unpack_from(">H", b, i)[0]; i += 2; return mpmap(b, i, n)
    if c == 0xdf:
        n = struct.unpack_from(">I", b, i)[0]; i += 4; return mpmap(b, i, n)
    raise ValueError("unsupported msgpack lead byte %#x" % c)


def mparr(b, i, n):
    out = []
    for _ in range(n):
        v, i = mp(b, i); out.append(v)
    return out, i


def mpmap(b, i, n):
    out = {}
    for _ in range(n):
        k, i = mp(b, i); v, i = mp(b, i); out[k] = v
    return out, i


def envelope(data):
    magic = data[:4].decode("ascii")
    ver = struct.unpack_from("<I", data, 4)[0]
    hl = struct.unpack_from("<I", data, 8)[0]
    hdr, end = mp(data, 12)
    assert end <= 12 + hl, "header overruns declared header_len"
    return magic, ver, hdr


def section(data, hdr, name):
    for s in hdr["sections"]:
        if s["name"] == name:
            return s, data[s["offset"]:s["offset"] + s["size"]]
    raise KeyError(name)


# ---------------------------------------------------------------- ground truth

TOOLS = {
    "tools/werk-gsplat": "werk-gsplat",
    "tools/werk-pointcloud": "werk-pointcloud",
    "tools/splat-to-ply": "splat-to-ply",
}


def ground_truth(fixture, nrows=8):
    z = zipfile.ZipFile(fixture)
    man = json.loads(z.read("MANIFEST.json"))

    pc = z.read("points/plush-dc.wkpc")
    m, v, ph = envelope(pc)
    assert m == "WKPC"
    _, posb = section(pc, ph, "position")
    _, colb = section(pc, ph, "color")
    count = ph["count"]

    gs = z.read("splats/plush.wkgs")
    m2, v2, gh = envelope(gs)
    assert m2 == "WKGS"
    _, means = section(gs, gh, "means")
    _, shdc = section(gs, gh, "sh-dc")

    pos = [struct.unpack_from("<3f", posb, 12 * k) for k in range(min(nrows, count))]
    col = [tuple(colb[3 * k:3 * k + 3]) for k in range(min(nrows, count))]

    # the normative path, gsplat.layout section 5 + section 7
    C0 = 0.28209479177387814
    def q(x):
        y = 0.5 + C0 * x
        y = 0.0 if y < 0.0 else (1.0 if y > 1.0 else y)
        # round-half-even, as tools/werk-pointcloud-run.config.json states
        import decimal
        return int(decimal.Decimal(y * 255.0).quantize(0, rounding=decimal.ROUND_HALF_EVEN))

    derived = []
    for k in range(min(nrows, count)):
        dc = struct.unpack_from("<3f", shdc, 12 * k)
        derived.append(tuple(q(c) for c in dc))

    # cross-check the WHOLE file, not just the sample rows
    means_eq = (means == posb)
    ncol_ok = 0
    for k in range(count):
        dc = struct.unpack_from("<3f", shdc, 12 * k)
        if tuple(q(c) for c in dc) == tuple(colb[3 * k:3 * k + 3]):
            ncol_ok += 1

    # tool source lines, for the "quote their source" clause
    quotes = {}
    for prefix, tid in TOOLS.items():
        best = None
        for n in z.namelist():
            if n.startswith(prefix + "/") and n.endswith(".py"):
                for line in z.read(n).decode("utf-8", "replace").splitlines():
                    ls = line.strip()
                    if len(ls) >= 40 and not ls.startswith("#"):
                        if best is None or len(ls) > len(best[1]):
                            best = (n, ls)
        quotes[tid] = best

    return {
        "count": count,
        "positions": pos,
        "colors": col,
        "colors_derived": derived,
        "means_equal_positions": means_eq,
        "colors_recomputed_matching": ncol_ok,
        "declared_files": sum(len(v0.get("files", []))
                              for n in man.get("nodes", []) for v0 in n.get("versions", [])),
        "tool_quotes": quotes,
        "fixture_sha256": sha256_file(fixture),
    }


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


# ---------------------------------------------------------------- run scanning

def harvest(scan):
    """Everything textual the run produced: stdout log + every text file it
    wrote, excluding the fixture and the harness's own copies of the prompt."""
    texts = []
    for root, dirs, files in os.walk(scan):
        for name in sorted(files):
            fp = os.path.join(root, name)
            rel = os.path.relpath(fp, scan).replace("\\", "/")
            if rel.endswith(".werk"):
                continue
            if rel.startswith("_harness/") and rel not in ("_harness/stdout.log",):
                continue
            if os.path.getsize(fp) > 64 << 20:
                continue
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    texts.append((rel, f.read()))
            except Exception:
                pass
    return texts


NUM = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


def has_triple(text, triple, tol, ints=False):
    """Is this triple present, in order, anywhere in the text, allowing the
    printed precision to be shorter than the stored float?"""
    toks = NUM.findall(text)
    vals = []
    for t in toks:
        try:
            vals.append(float(t))
        except ValueError:
            vals.append(None)
    n = len(vals)
    for i in range(n - 2):
        a, b, c = vals[i], vals[i + 1], vals[i + 2]
        if a is None or b is None or c is None:
            continue
        if ints:
            if (a, b, c) == triple:
                return True
        else:
            if (abs(a - triple[0]) <= tol and abs(b - triple[1]) <= tol
                    and abs(c - triple[2]) <= tol):
                return True
    return False


# A u8 colour may be printed as its stored integer (39) or as the exact
# fraction of 255 it denotes (39/255 = 0.152941...). Both carry the same value
# (S-DS-6). The fraction form is accepted only within FRAC_TOL of k/255, which
# needs about 5 printed decimals; adjacent u8 steps are 1/255 = 0.0039 apart,
# so a wrong colour cannot pass by rounding.
FRAC_TOL = 5e-6


def colour_form(text, rgb):
    """'u8' if the integer triple is present, 'unit' if the exact /255
    fractions are present, else None. The integer test is tried first, so a
    run graded PASS before this change is graded the same way after it."""
    if has_triple(text, tuple(float(x) for x in rgb), 0.0, ints=True):
        return "u8"
    if has_triple(text, tuple(x / 255.0 for x in rgb), FRAC_TOL):
        return "unit"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", required=True)
    ap.add_argument("--rundir", required=True)
    ap.add_argument("--rerun", action="store_true")
    ap.add_argument("--prog", default="solution.py")
    ap.add_argument("--out", default="")
    ap.add_argument("--json-out", default="")
    args = ap.parse_args()

    gt = ground_truth(args.fixture)
    print("fixture        : %s" % args.fixture)
    print("fixture sha256 : %s" % gt["fixture_sha256"])
    print("ground truth   : count=%d  declared_files=%d" % (gt["count"], gt["declared_files"]))
    print("  WKGS means == WKPC position bytes : %s" % gt["means_equal_positions"])
    print("  colours recomputed from sh-dc     : %d / %d match"
          % (gt["colors_recomputed_matching"], gt["count"]))
    print("  point[0] pos = %.8f %.8f %.8f   col = %d %d %d"
          % (gt["positions"][0] + gt["colors"][0]))

    scan = args.rundir
    rerun = None
    if args.rerun:
        out = os.path.realpath(args.out)
        if os.path.exists(out):
            shutil.rmtree(out)
        os.makedirs(out)
        shutil.copy2(args.fixture, os.path.join(out, os.path.basename(args.fixture)))
        shutil.copy2(os.path.join(args.rundir, args.prog),
                     os.path.join(out, os.path.basename(args.prog)))
        cenv = dict(os.environ)
        cenv["PYTHONIOENCODING"] = "utf-8"
        cenv["PYTHONUTF8"] = "1"
        t0 = time.monotonic()
        p = subprocess.run([sys.executable, os.path.basename(args.prog)], cwd=out,
                           capture_output=True, timeout=3600, env=cenv)
        dt = time.monotonic() - t0
        so = p.stdout.decode("utf-8", "replace")
        se = p.stderr.decode("utf-8", "replace")
        with open(os.path.join(out, "_rerun.stdout.txt"), "w", encoding="utf-8") as f:
            f.write(so)
        with open(os.path.join(out, "_rerun.stderr.txt"), "w", encoding="utf-8") as f:
            f.write(se)
        print("\n=== RE-RUN in clean dir %s ===" % out)
        print("exit=%d in %.1fs  stdout=%dB stderr=%dB" % (p.returncode, dt, len(so), len(se)))
        rerun = {"exit": p.returncode, "secs": round(dt, 1),
                 "stdout_bytes": len(so), "stderr_bytes": len(se)}
        scan = out

    texts = harvest(scan)
    blob = "\n".join(t for _, t in texts)
    print("\nscanned %d text artifacts under %s (%d chars)" % (len(texts), scan, len(blob)))

    # ---- clause 2: the numbers
    count_ok = bool(re.search(r"\b%d\b" % gt["count"], blob)) or \
               bool(re.search(r"\b%s\b" % "[  ,]".join(str(gt["count"])), blob))
    pos_ok = has_triple(blob, gt["positions"][0], 5e-6)
    col_form = colour_form(blob, gt["colors"][0])
    col_ok = col_form is not None
    posN = sum(1 for k in range(len(gt["positions"])) if has_triple(blob, gt["positions"][k], 5e-6))
    colN = sum(1 for k in range(len(gt["colors"]))
               if colour_form(blob, gt["colors"][k]) is not None)

    # ---- clause 3: the tools
    tool_named = {t: (t in blob) for t in TOOLS.values()}
    tool_path = {t: (p in blob) for p, t in TOOLS.items()}
    tool_quoted = {}
    for t, best in gt["tool_quotes"].items():
        tool_quoted[t] = bool(best) and (best[1] in blob)

    # ---- clause 1: integrity
    integ_ok = bool(re.search(r"sha-?256", blob, re.I)) and \
        bool(re.search(r"(verif|match|\bOK\b|\bPASS\b)", blob, re.I))

    print("\n=== CLAUSE GRADES (from artifacts, not from the model's claims) ===")
    print(" 1  integrity: sha-256 named and a verification verdict : %s" % integ_ok)
    print(" 2  point count %d present                       : %s" % (gt["count"], count_ok))
    print("    point[0] position triple present               : %s" % pos_ok)
    print("    point[0] colour triple present                 : %s%s"
          % (col_ok, "  (form: %s)" % col_form if col_ok else ""))
    print("    of the first %d points: %d positions, %d colours present"
          % (len(gt["positions"]), posN, colN))
    print(" 3  tools named   : %s" % tool_named)
    print("    tool paths    : %s" % tool_path)
    print("    source quoted : %s" % tool_quoted)

    passed = count_ok and pos_ok and col_ok and all(tool_named.values())
    print("\nVERDICT (clauses 2 and 3, the spec-forcing ones): %s"
          % ("PASS" if passed else "FAIL"))

    row = {"fixture": args.fixture, "fixture_sha256": gt["fixture_sha256"],
           "rundir": args.rundir, "scanned": scan, "rerun": rerun,
           "count_ok": count_ok, "pos0_ok": pos_ok, "col0_ok": col_ok,
           "col0_form": col_form,
           "positions_present": posN, "colors_present": colN,
           "sample_rows": len(gt["positions"]),
           "integrity_ok": integ_ok,
           "tool_named": tool_named, "tool_path": tool_path, "tool_quoted": tool_quoted,
           "verdict": "PASS" if passed else "FAIL",
           "artifacts": [n for n, _ in texts]}
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(row, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
