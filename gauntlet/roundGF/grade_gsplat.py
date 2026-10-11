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
          must appear in the run's output or report. Any such line counts if
          it is unique to that tool; the count per tool is reported.

EVIDENCE ALLOWLIST (grader revision 2026-10-12). Only the run's outputs are
evidence: the harness stdout log, the clean re-run's stdout, and the data or
report files the program wrote. Not scanned: every program source file
(.py, .sh, .ps1, .bat, .cmd; not only --prog and its iterations), any file
whose name starts with prompt, task, transcript or context_package, and the
fixture. The model's code and a copy of the prompt name the tools and the
count whether or not anything was decoded (--include-source restores the
pre-revision scan).

TWO VERDICTS. `verdict` is the FULL-TASK verdict: clause 1 needs at least
one of the package's declared sha256 digests printed beside a verification
verdict; clause 2 needs the count and ALL of the first --sample-rows
(default 32) positions and colours; clause 3 needs each tool named, its
path given and at least one unique source line quoted. `verdict_numeric`
is the pre-revision rule (count, point[0], tool names only). An
89-character report satisfies the numeric rule without decoding anything;
it cannot satisfy the full-task rule, which is why the numeric rule is now
reported as a partial check and not as the verdict.

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
    digests = set()
    for n in man.get("nodes", []):
        for v0 in n.get("versions", []):
            for f in v0.get("files", []):
                if f.get("sha256"):
                    digests.add(f["sha256"].lower())

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
    # Every line of >= 40 chars counts as a candidate quote, not only the
    # longest one: a run that quotes ten real lines of a tool has quoted it.
    # A line that also occurs in another tool's source is dropped, so that
    # quoting shared boilerplate cannot credit a tool that was not quoted.
    quotes = {}
    cand = {}
    for prefix, tid in TOOLS.items():
        best = None
        lines = set()
        for n in z.namelist():
            if n.startswith(prefix + "/") and n.endswith(".py"):
                for line in z.read(n).decode("utf-8", "replace").splitlines():
                    ls = line.strip()
                    if len(ls) >= 40 and not ls.startswith("#"):
                        lines.add(ls)
                        if best is None or len(ls) > len(best[1]):
                            best = (n, ls)
        quotes[tid] = best
        cand[tid] = lines
    tool_lines = {}
    for tid, lines in cand.items():
        others = set().union(*(v for k, v in cand.items() if k != tid))
        tool_lines[tid] = sorted(lines - others)

    return {
        "count": count,
        "positions": pos,
        "colors": col,
        "colors_derived": derived,
        "means_equal_positions": means_eq,
        "colors_recomputed_matching": ncol_ok,
        "declared_files": sum(len(v0.get("files", []))
                              for n in man.get("nodes", []) for v0 in n.get("versions", [])),
        "declared_digests": sorted(digests),
        "tool_quotes": quotes,
        "tool_lines": tool_lines,
        "fixture_sha256": sha256_file(fixture),
    }


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


# ---------------------------------------------------------------- run scanning

def source_names(prog):
    """Paths (relative to the scan dir) that hold the program's own source:
    the --prog file and its saved iterations (solution.iter1.py, ...). The
    source is the model's code, not its output: it names the tools and the
    point count whether or not the program runs."""
    rel = prog.replace("\\", "/")
    if rel.startswith("./"):
        rel = rel[2:]
    base = os.path.basename(rel)
    stem, ext = os.path.splitext(base)
    pat = re.compile(r"(?:.*/)?%s\.iter\d+%s$" % (re.escape(stem), re.escape(ext)))
    return {rel, base}, pat


SOURCE_EXT = (".py", ".pyc", ".sh", ".ps1", ".bat", ".cmd")
NOT_EVIDENCE = re.compile(r"(?i)^(prompt|task|transcript|context_package)")


def harvest(scan, prog=None):
    """Everything textual the run produced: stdout log + every text file it
    wrote, excluding the fixture, the harness's own copies of the prompt,
    and (when prog is given) every program source file and every file named
    like a prompt, task or transcript copy. prog=None scans everything (the
    pre-revision behaviour, --include-source). Returns the texts and the
    list of skipped files."""
    texts = []
    skipped = []
    names, pat = source_names(prog) if prog else (set(), None)
    for root, dirs, files in os.walk(scan):
        for name in sorted(files):
            fp = os.path.join(root, name)
            rel = os.path.relpath(fp, scan).replace("\\", "/")
            if rel.endswith(".werk"):
                continue
            if prog and (rel in names or pat.match(rel)):
                skipped.append(rel)
                continue
            if prog and (rel.lower().endswith(SOURCE_EXT) or NOT_EVIDENCE.search(name)):
                skipped.append(rel)
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
    return texts, skipped


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
    ap.add_argument("--include-source", action="store_true",
                    help="also scan the program's own source (the pre-fix behaviour)")
    ap.add_argument("--sample-rows", type=int, default=32,
                    help="how many leading points must ALL be present for a full-task PASS")
    args = ap.parse_args()

    gt = ground_truth(args.fixture, max(1, args.sample_rows))
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

    texts, skipped = harvest(scan, None if args.include_source else args.prog)
    blob = "\n".join(t for _, t in texts)
    print("\nscanned %d text artifacts under %s (%d chars)" % (len(texts), scan, len(blob)))
    if skipped:
        print("not scanned (program source, prompt/task/transcript copies): %s"
              % ", ".join(skipped))

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
    tool_quote_lines = {t: sum(1 for ls in lines if ls in blob)
                        for t, lines in gt["tool_lines"].items()}
    tool_quoted = {t: n > 0 for t, n in tool_quote_lines.items()}

    # ---- clause 1: integrity
    integ_words = bool(re.search(r"sha-?256", blob, re.I)) and \
        bool(re.search(r"(verif|match|\bOK\b|\bPASS\b)", blob, re.I))
    lblob = blob.lower()
    digests_seen = [d for d in gt["declared_digests"] if d in lblob]
    integ_ok = integ_words and len(digests_seen) > 0

    print("\n=== CLAUSE GRADES (from artifacts, not from the model's claims) ===")
    print(" 1  integrity: sha-256 named and a verification verdict : %s" % integ_words)
    print("    declared digests printed (of %d)                : %d  -> clause 1 %s"
          % (len(gt["declared_digests"]), len(digests_seen), integ_ok))
    print(" 2  point count %d present                       : %s" % (gt["count"], count_ok))
    print("    point[0] position triple present               : %s" % pos_ok)
    print("    point[0] colour triple present                 : %s%s"
          % (col_ok, "  (form: %s)" % col_form if col_ok else ""))
    print("    of the first %d points: %d positions, %d colours present"
          % (len(gt["positions"]), posN, colN))
    print(" 3  tools named   : %s" % tool_named)
    print("    tool paths    : %s" % tool_path)
    print("    source quoted : %s" % tool_quoted)
    print("    quoted lines  : %s  (of %s candidate lines)"
          % (tool_quote_lines, {t: len(v) for t, v in gt["tool_lines"].items()}))

    nrows = len(gt["positions"])
    numeric = count_ok and pos_ok and col_ok and all(tool_named.values())
    full_checks = [
        ("1 integrity: declared digest + verdict", integ_ok),
        ("2 count", count_ok),
        ("2 all %d sample positions" % nrows, posN == nrows),
        ("2 all %d sample colours" % nrows, colN == nrows),
        ("3 tools named", all(tool_named.values())),
        ("3 tool paths", all(tool_path.values())),
        ("3 source quoted", all(tool_quoted.values())),
    ]
    failing = [name for name, ok in full_checks if not ok]
    passed = not failing
    print("\nVERDICT (full task, clauses 1-3): %s%s"
          % ("PASS" if passed else "FAIL",
             "" if passed else "   failing: " + "; ".join(failing)))
    print("numeric sub-check (count, point[0], tool names; the pre-2026-10-12 verdict rule): %s"
          % ("PASS" if numeric else "FAIL"))

    row = {"fixture": args.fixture, "fixture_sha256": gt["fixture_sha256"],
           "rundir": args.rundir, "scanned": scan, "rerun": rerun,
           "count_ok": count_ok, "pos0_ok": pos_ok, "col0_ok": col_ok,
           "col0_form": col_form,
           "positions_present": posN, "colors_present": colN,
           "sample_rows": nrows,
           "integrity_ok": integ_ok, "integrity_words": integ_words,
           "declared_digests_printed": len(digests_seen),
           "tool_named": tool_named, "tool_path": tool_path, "tool_quoted": tool_quoted,
           "tool_quote_lines": tool_quote_lines, "source_excluded": skipped,
           "verdict": "PASS" if passed else "FAIL",
           "verdict_rule": "full-task-2026-10-12",
           "full_task_failing": failing,
           "verdict_numeric": "PASS" if numeric else "FAIL",
           "artifacts": [n for n, _ in texts]}
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(row, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
