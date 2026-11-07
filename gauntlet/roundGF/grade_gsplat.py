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

Files whose bytes equal any entry of the package (an unpacked copy of the
fixture, with any name or suffix, MANIFEST.json and SIGNATURE.json
included) are not evidence either: they are the input, not an output.

TWO VERDICTS. `verdict` is the FULL-TASK verdict. It is a POST-HOC,
STRICTER re-grade (criteria of 2026-10-12, written after the runs): it is
reported BESIDE each round's recorded verdict and never replaces it. For a
committed run whose record dropped outputs, a clause-2 failure means "not
established by the committed artefacts", not that the run failed it.
`verdict_numeric` is the rule the rounds were graded by. clause 1 needs a
verification verdict in the clean run AND, under --rerun, the DAMAGE CHECK:
the same program is run on a copy of the fixture in which one byte of one
declared file is flipped (the zip is rewritten self-consistent, so only
the manifest digest disagrees), and it must report the damage (non-zero
exit where the clean run exited 0, or more failure words than the clean
run). Words such as "all hashes verified" are the model's claim, not
evidence; the damage check is. Without --rerun clause 1 is NOT
ESTABLISHED and the full-task verdict is FAIL. Clause 2 needs the count
AND the complete point set on disk: a
text table (csv/txt/xyz/tsv, one point per line, optional index column)
whose every row k equals ground-truth point k, positions within 5e-6 and
colours as the stored u8 triple or exact k/255; clause 3 needs each tool
named, its path given and at least one unique source line quoted.
--sample-rows (default 32) only reports how many leading points also
appear in the free text. `verdict_numeric` is the pre-revision rule
(count, point[0], tool names only). An 89-character report satisfies the
numeric rule without decoding anything; it cannot satisfy the full-task
rule, which is why the numeric rule is now reported as a partial check and
not as the verdict.

  --rerun --prog-arg gsplat-v1.werk --prog-arg=--out --prog-arg out
       passes arguments verbatim to the re-run program (repeatable; write
       --prog-arg=--flag for an argument that starts with a dash).

In --rerun mode the evidence is the clean re-run's stdout and the files the
program wrote there, plus the run's own REPORT.md (--report NAME, default
REPORT.md; --no-report excludes it). The report is a declared output of the
task (the prompt asks for it) and is where a run quotes tool source and
lists the digests it verified; the re-run establishes that the program
reproduces the point set without the model present.

  python grade_gsplat.py --fixture fixtures/gsplat-v1.werk --rundir <dir>
  python grade_gsplat.py --fixture ... --rundir <dir> --rerun --prog solution.py \
                         --out <cleandir>

Standard library only.
"""

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rerun_support import prepare_output, program_args, run_python

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
    """nrows=None decodes every point (for the full point-set check)."""
    z = zipfile.ZipFile(fixture)
    man = json.loads(z.read("MANIFEST.json"))
    digests = set()
    for n in man.get("nodes", []):
        for v0 in n.get("versions", []):
            for f in v0.get("files", []):
                if f.get("sha256"):
                    digests.add(f["sha256"].lower())
    entry_digests = set(hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()
                        if not n.endswith("/"))

    pc = z.read("points/plush-dc.wkpc")
    m, v, ph = envelope(pc)
    assert m == "WKPC"
    _, posb = section(pc, ph, "position")
    _, colb = section(pc, ph, "color")
    count = ph["count"]
    if nrows is None:
        nrows = count

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
        "entry_digests": sorted(entry_digests),
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


# ---------------------------------------------------------------- damage check

FAIL_WORDS = re.compile(r"(mismatch|corrupt|tamper|invalid|fail|damaged|does not match|bad )", re.I)


def make_damaged(fixture, out_path):
    """Write a copy of the fixture with one byte of one declared file
    flipped. The zip is rewritten entry by entry with the same names and
    compression, so every CRC is right and only the manifest's sha256 of
    that file disagrees. The file is the first declared path under spec/
    larger than 1000 bytes (sorted), else the largest declared file.
    -> (path, byte offset)."""
    z = zipfile.ZipFile(fixture)
    man = json.loads(z.read("MANIFEST.json"))
    declared = []
    for n in man.get("nodes", []):
        for v0 in n.get("versions", []):
            for f in v0.get("files", []):
                declared.append(f["path"])
    sizes = {i.filename: i.file_size for i in z.infolist()}
    cands = sorted(pth for pth in declared if pth.startswith("spec/") and sizes.get(pth, 0) > 1000)
    target = cands[0] if cands else max(declared, key=lambda pth: sizes.get(pth, 0))
    data = bytearray(z.read(target))
    off = len(data) // 2
    data[off] ^= 0x01
    with zipfile.ZipFile(out_path, "w") as w:
        for info in z.infolist():
            payload = bytes(data) if info.filename == target else z.read(info.filename)
            ni = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            ni.compress_type = info.compress_type
            ni.external_attr = info.external_attr
            w.writestr(ni, payload)
    return target, off


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
# A committed run folder also holds the earlier grader's own output
# (grade*.json) and the harness's metadata (run.json). Neither is the
# agent's work (review B finding 2).
NOT_EVIDENCE_FILE = re.compile(r"(?i)^(grade[^/]*\.json|run\.json)$")


def harvest(scan, prog=None, package_digests=()):
    """Everything textual the run produced: stdout log + every text file it
    wrote, excluding the fixture, the harness's own copies of the prompt,
    every file whose bytes equal a declared package entry (an unpacked
    copy), and (when prog is given) every program source file and every
    file named like a prompt, task or transcript copy. prog=None scans
    everything else (the pre-revision behaviour, --include-source).
    Returns the texts and the list of skipped files."""
    texts = []
    skipped = []
    names, pat = source_names(prog) if prog else (set(), None)
    pkg = set(package_digests)
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
            if NOT_EVIDENCE_FILE.match(name):
                skipped.append(rel + " (grader/harness output)")
                continue
            if pkg and os.path.getsize(fp) <= 64 << 20 and sha256_file(fp) in pkg:
                skipped.append(rel + " (package copy)")
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


def numbers(text):
    """Every finite number in the text. A sha256 hex string contains runs
    such as 3e999 that parse as infinity; those are not numbers here."""
    vals = []
    for t in NUM.findall(text):
        try:
            v = float(t)
        except ValueError:
            continue
        if math.isfinite(v):
            vals.append(v)
    return vals


class TripleIndex(object):
    """All numeric tokens of a text, indexed by the bucket of each token, so
    that 'is this triple present, in order, within tol' is answered without
    rescanning the text per triple. A triple is present when three
    consecutive tokens match it; the printed precision may be shorter than
    the stored float."""

    def __init__(self, text, tol):
        self.vals = numbers(text)
        self.tol = tol
        self.w = max(tol, 1e-9) * 2.0
        self.idx = {}
        for i, v in enumerate(self.vals):
            self.idx.setdefault(int(math.floor(v / self.w)), []).append(i)

    def has(self, triple, tol=None, ints=False):
        tol = self.tol if tol is None else tol
        b = int(math.floor(triple[0] / self.w))
        n = len(self.vals)
        for bb in (b - 1, b, b + 1):
            for i in self.idx.get(bb, ()):
                if i + 2 >= n:
                    continue
                a, c, d = self.vals[i], self.vals[i + 1], self.vals[i + 2]
                if ints:
                    if (a, c, d) == triple:
                        return True
                elif (abs(a - triple[0]) <= tol and abs(c - triple[1]) <= tol
                      and abs(d - triple[2]) <= tol):
                    return True
        return False


def has_triple(text, triple, tol, ints=False):
    """Kept for callers that hold a text; builds a one-off index."""
    return TripleIndex(text, tol).has(triple, tol, ints)


# A u8 colour may be printed as its stored integer (39) or as the exact
# fraction of 255 it denotes (39/255 = 0.152941...). Both carry the same value
# (S-DS-6). The fraction form is accepted only within FRAC_TOL of k/255, which
# needs about 5 printed decimals; adjacent u8 steps are 1/255 = 0.0039 apart,
# so a wrong colour cannot pass by rounding.
FRAC_TOL = 5e-6


def colour_form(ix, rgb):
    """'u8' if the integer triple is present, 'unit' if the exact /255
    fractions are present, else None. The integer test is tried first, so a
    run graded PASS before this change is graded the same way after it.
    `ix` is a TripleIndex built with FRAC_TOL."""
    if ix.has(tuple(float(x) for x in rgb), 0.0, ints=True):
        return "u8"
    if ix.has(tuple(x / 255.0 for x in rgb), FRAC_TOL):
        return "unit"
    return None


# ------------------------------------------------------------ full point set

POINT_TABLE_EXT = (".csv", ".txt", ".xyz", ".tsv", ".dat")
NOT_ROW = re.compile(r"[A-DF-Za-df-z_#]")
FIELD_SEP = re.compile(r"[,;\t |]+")
IS_NUMBER = re.compile(r"^[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?$")


def row_numbers(line):
    """The numeric fields of one table line, or None if the line is not a
    data row. Text fields are tolerated only at the ends of the row: a
    constant label column such as `linear-srgb` after the numbers (the
    cross-vendor openai run, review B finding 1) or a name before them. A
    line whose fields are all text, such as a header `x,y,z,r_u8,g_u8,b_u8`,
    or with text between numbers, is not a row."""
    fields = [f for f in FIELD_SEP.split(line.strip()) if f]
    num = [bool(IS_NUMBER.match(f)) for f in fields]
    if not any(num):
        return None
    lo = num.index(True)
    hi = len(num) - 1 - num[::-1].index(True)
    if not all(num[lo:hi + 1]):
        return None
    vals = []
    for f in fields[lo:hi + 1]:
        v = float(f)
        if not math.isfinite(v):
            return None
        vals.append(v)
    return vals


def colour_at(nums, rgb):
    """Does the number list hold rgb as a u8 triple or an exact k/255 triple,
    in order, anywhere? -> 'u8', 'unit' or None."""
    n = len(nums)
    want_u8 = tuple(float(x) for x in rgb)
    want_unit = tuple(x / 255.0 for x in rgb)
    for i in range(n - 2):
        t = (nums[i], nums[i + 1], nums[i + 2])
        if t == want_u8:
            return "u8"
        if all(abs(t[k] - want_unit[k]) <= FRAC_TOL for k in range(3)):
            return "unit"
    return None


def check_point_table(text, positions, colors, tol):
    """Grade one text table against the complete ground truth.
    Row k (after an optional header; an optional leading index column) must
    hold position k within tol, and colour k as u8 or exact k/255 anywhere
    after the position. -> dict(rows, pos_ok, col_ok, first_bad_row)."""
    count = len(positions)
    rows = 0
    pos_ok = col_ok = 0
    first_bad = None
    for line in text.splitlines():
        # A data row holds numeric fields, optionally with text fields at its
        # ends (row_numbers). A header such as "x,y,z,r_u8,g_u8,b_u8" contains
        # digits but no numeric field, so it is not a row.
        nums = row_numbers(line)
        if nums is None or len(nums) < 3:
            continue
        if rows >= count:
            rows += 1
            continue
        p = positions[rows]
        off = None
        for o in (0, 1):
            if len(nums) >= o + 3 and all(abs(nums[o + k] - p[k]) <= tol for k in range(3)):
                off = o
                break
        if off is None:
            if first_bad is None:
                first_bad = rows
            rows += 1
            continue
        pos_ok += 1
        if colour_at(nums[off + 3:], colors[rows]) or colour_at(nums[:off], colors[rows]):
            col_ok += 1
        elif first_bad is None:
            first_bad = rows
        rows += 1
    return {"rows": rows, "pos_ok": pos_ok, "col_ok": col_ok, "first_bad_row": first_bad}


def full_point_set(texts, gt, tol):
    """The best point table among the run's text artifacts: the one with the
    most rows equal to ground truth. -> (rel, result) or (None, None)."""
    best = (None, None)
    for rel, text in texts:
        if not rel.lower().endswith(POINT_TABLE_EXT) and not rel.endswith("stdout.log") \
                and not rel.endswith("_rerun.stdout.txt"):
            continue
        if text.count("\n") < gt["count"] // 2:
            continue
        r = check_point_table(text, gt["positions"], gt["colors"], tol)
        if best[1] is None or (r["pos_ok"], r["col_ok"]) > (best[1]["pos_ok"], best[1]["col_ok"]):
            best = (rel, r)
    return best


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
                    help="how many leading points are looked for in the free text (reported only)")
    ap.add_argument("--prog-args", default=None, help="shell-style argument string")
    ap.add_argument("--prog-arg", action="append", default=[],
                    help="one argument for the re-run program, verbatim (repeatable)")
    ap.add_argument("--report", default="REPORT.md",
                    help="the run's report file (relative to --rundir) that --rerun also scans")
    ap.add_argument("--no-report", action="store_true",
                    help="with --rerun, scan the clean re-run directory only")
    ap.add_argument("--no-damage-check", action="store_true",
                    help="with --rerun, skip the flipped-byte run (clause 1 then stays not established)")
    args = ap.parse_args()

    gt = ground_truth(args.fixture, max(1, args.sample_rows))
    gt_all = ground_truth(args.fixture, None)
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
        out = prepare_output(args.out, [args.rundir, args.fixture])
        shutil.copy2(args.fixture, os.path.join(out, os.path.basename(args.fixture)))
        shutil.copy2(os.path.join(args.rundir, args.prog), os.path.join(out, os.path.basename(args.prog)))
        pargs = program_args(args)
        rerun = run_python(os.path.basename(args.prog), pargs, out, 3600)
        so, se = rerun["stdout"], rerun["stderr"]
        for name, text in (("stdout", so), ("stderr", se)):
            with open(os.path.join(out, "_rerun.%s.txt" % name), "w", encoding="utf-8") as f:
                f.write(text)
        print("\n=== RE-RUN: %s; exit=%s ===" % (rerun["status"], rerun["exit"]))
        scan = out
        if not args.no_damage_check and rerun["status"] == "completed" and rerun["exit"] == 0:
            dout = prepare_output(out + "-damaged", [args.rundir, args.fixture])
            target, off = make_damaged(args.fixture, os.path.join(dout, os.path.basename(args.fixture)))
            shutil.copy2(os.path.join(args.rundir, args.prog), os.path.join(dout, os.path.basename(args.prog)))
            damaged = run_python(os.path.basename(args.prog), pargs, dout, 3600)
            sod = damaged["stdout"] + damaged["stderr"]
            with open(os.path.join(dout, "_rerun.stdout.txt"), "w", encoding="utf-8") as f:
                f.write(sod)
            clean_words = len(FAIL_WORDS.findall(so + se))
            dam_words = len(FAIL_WORDS.findall(sod))
            detected = damaged["status"] == "completed" and (
                damaged["exit"] != 0 or dam_words > clean_words)
            print("=== DAMAGE CHECK: %s; status=%s; detected=%s ===" %
                  (target, damaged["status"], detected))
            rerun["damage"] = {"file": target, "offset": off, "exit": damaged["exit"],
                               "status": damaged["status"], "error": damaged["error"],
                               "clean_exit": rerun["exit"], "fail_words_clean": clean_words,
                               "fail_words_damaged": dam_words, "detected": detected, "dir": dout}

    texts, skipped = harvest(scan, None if args.include_source else args.prog,
                             gt["entry_digests"])
    if args.rerun and not args.no_report:
        rp = os.path.join(args.rundir, args.report)
        if os.path.isfile(rp):
            with open(rp, "r", encoding="utf-8", errors="replace") as f:
                texts.append(("(rundir)/" + args.report.replace(chr(92), "/"), f.read()))
            print("plus the run's report: %s" % rp)
    blob = "\n".join(t for _, t in texts)
    print("\nscanned %d text artifacts under %s (%d chars)" % (len(texts), scan, len(blob)))
    if skipped:
        print("not scanned (program source, prompt/task/transcript copies, package copies): %s"
              % ", ".join(skipped))

    # ---- clause 2: the numbers
    count_ok = bool(re.search(r"\b%d\b" % gt["count"], blob)) or \
               bool(re.search(r"\b%s\b" % "[  ,]".join(str(gt["count"])), blob))
    ix = TripleIndex(blob, FRAC_TOL)
    pos_ok = ix.has(gt["positions"][0], 5e-6)
    col_form = colour_form(ix, gt["colors"][0])
    col_ok = col_form is not None
    posN = sum(1 for k in range(len(gt["positions"])) if ix.has(gt["positions"][k], 5e-6))
    colN = sum(1 for k in range(len(gt["colors"]))
               if colour_form(ix, gt["colors"][k]) is not None)
    full_rel, full = full_point_set(texts, gt_all, 5e-6)
    full_pos_ok = bool(full) and full["pos_ok"] == gt_all["count"]
    full_col_ok = bool(full) and full["col_ok"] == gt_all["count"]

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
    damage = (rerun or {}).get("damage")
    if damage is None:
        integ_ok = False
        integ_how = "NOT ESTABLISHED (needs --rerun with the damage check)"
    else:
        integ_ok = integ_words and damage["detected"]
        integ_how = "damage %s" % ("reported" if damage["detected"] else "NOT reported")

    print("\n=== CLAUSE GRADES (from artifacts, not from the model's claims) ===")
    print(" 1  integrity: sha-256 named and a verification verdict : %s" % integ_words)
    print("    declared digests printed (of %d)                : %d  (reported only)"
          % (len(gt["declared_digests"]), len(digests_seen)))
    print("    flipped-byte copy                              : %s  -> clause 1 %s"
          % (integ_how, integ_ok))
    print(" 2  point count %d present                       : %s" % (gt["count"], count_ok))
    print("    point[0] position triple present               : %s" % pos_ok)
    print("    point[0] colour triple present                 : %s%s"
          % (col_ok, "  (form: %s)" % col_form if col_ok else ""))
    print("    of the first %d points: %d positions, %d colours present in the free text"
          % (len(gt["positions"]), posN, colN))
    if full:
        print("    complete point set on disk (%s): %d rows; %d / %d positions, %d / %d colours "
              "equal ground truth%s"
              % (full_rel, full["rows"], full["pos_ok"], gt_all["count"], full["col_ok"],
                 gt_all["count"],
                 "" if full["first_bad_row"] is None else
                 "; first row not equal: %d" % full["first_bad_row"]))
    else:
        print("    complete point set on disk                     : no table with >= %d rows"
              % (gt_all["count"] // 2))
    print(" 3  tools named   : %s" % tool_named)
    print("    tool paths    : %s" % tool_path)
    print("    source quoted : %s" % tool_quoted)
    print("    quoted lines  : %s  (of %s candidate lines)"
          % (tool_quote_lines, {t: len(v) for t, v in gt["tool_lines"].items()}))

    nrows = len(gt["positions"])
    numeric = count_ok and pos_ok and col_ok and all(tool_named.values())
    full_checks = [
        ("1 integrity: verdict + damage reported on a flipped-byte copy", integ_ok),
        ("2 count", count_ok),
        ("2 complete point set on disk, positions", full_pos_ok),
        ("2 complete point set on disk, colours", full_col_ok),
        ("3 tools named", all(tool_named.values())),
        ("3 tool paths", all(tool_path.values())),
        ("3 source quoted", all(tool_quoted.values())),
    ]
    failing = [name for name, ok in full_checks if not ok]
    if rerun and (rerun["status"] != "completed" or rerun["exit"] != 0):
        failing.append("program did not complete with exit 0")
    host_error = bool(rerun) and (rerun["status"] == "host-error" or
                                 (damage or {}).get("status") == "host-error")
    passed = not failing and not host_error
    verdict = "HOST-ERROR" if host_error else ("PASS" if passed else "FAIL")
    print("\nVERDICT (full task, clauses 1-3): %s%s"
          % (verdict,
             "" if passed else "   failing: " + "; ".join(failing)))
    print("numeric sub-check (count, point[0], tool names; the pre-2026-10-12 verdict rule): %s"
          % ("PASS" if numeric else "FAIL"))

    row = {"fixture": args.fixture, "fixture_sha256": gt["fixture_sha256"],
           "rundir": args.rundir, "scanned": scan, "rerun": rerun,
           "count_ok": count_ok, "pos0_ok": pos_ok, "col0_ok": col_ok,
           "col0_form": col_form,
           "positions_present": posN, "colors_present": colN,
           "sample_rows": nrows,
           "full_set_file": full_rel,
           "full_set": full,
           "full_set_positions_ok": full_pos_ok, "full_set_colors_ok": full_col_ok,
           "integrity_ok": integ_ok, "integrity_words": integ_words,
           "integrity_how": integ_how, "damage_check": damage,
           "declared_digests_printed": len(digests_seen),
           "tool_named": tool_named, "tool_path": tool_path, "tool_quoted": tool_quoted,
           "tool_quote_lines": tool_quote_lines, "source_excluded": skipped,
           "verdict": verdict,
           "verdict_rule": "full-task-2026-10-12",
           "full_task_failing": failing,
           "verdict_kind": "full-task verdict is a post-hoc re-grade (criteria of 2026-10-12); verdict_numeric is the recorded rule",
           "verdict_numeric": "PASS" if numeric else "FAIL",
           "artifacts": [n for n, _ in texts]}
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(row, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
