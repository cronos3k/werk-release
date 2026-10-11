#!/usr/bin/env python3
"""
test_grade_gsplat_adversarial.py -- can grade_gsplat.py be passed without
decoding the splat?

Grader revision 2026-10-12. Each case builds a run directory in a temp
folder, runs grade_gsplat.py on it, and checks both verdicts:

  verdict          the full-task rule (clauses 1-3, all sample rows)
  verdict_numeric  the pre-revision rule (count, point[0], tool names)

The point of the table is the pairs where numeric says PASS and full says
FAIL: those are runs the old rule would have credited without a decoded
artifact. The last case is a correct synthetic run, so the suite also shows
the full-task rule CAN be passed.

  py -3.13 test_grade_gsplat_adversarial.py [--fixture ../../fixtures/gsplat-v1.werk]

Needs the pinned fixture (tools/fetch_fixtures.py). Standard library only.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
GRADER = os.path.join(HERE, "grade_gsplat.py")
sys.path.insert(0, HERE)
import grade_gsplat  # noqa: E402

ROWS = 32


def evidence(gt, rows=None, colour_bump_row=None, nan_rows=False, first_row_only=False,
             positions_only=False, index_column=False):
    """A report and a CSV that a correct, complete run would have left.
    rows=None writes every point (gt must hold the full set)."""
    if rows is None:
        rows = len(gt["positions"])
    rep = ["# REPORT", "",
           "Integrity: every declared file re-hashed with SHA-256; all match the manifest: OK.",
           "digests checked: " + " ".join(gt["declared_digests"][:3]), "",
           "Point count: %d" % gt["count"], ""]
    for path, tid in grade_gsplat.TOOLS.items():
        q = gt["tool_lines"][tid][0]
        rep += ["Tool %s at %s/ converts the capture; source:" % (tid, path), "    " + q, ""]
    n = 1 if first_row_only else rows
    csv = [("i," if index_column else "") + ("x,y,z" if positions_only else "x,y,z,r,g,b")]
    for k in range(n):
        p = gt["positions"][k]
        c = list(gt["colors"][k])
        if colour_bump_row is not None and k == colour_bump_row:
            c[0] = c[0] + 1 if c[0] < 255 else c[0] - 1
        pre = ("%d," % k) if index_column else ""
        if nan_rows:
            csv.append(pre + "nan,nan,nan,%d,%d,%d" % tuple(c))
        elif positions_only:
            csv.append(pre + "%.8f,%.8f,%.8f" % (p[0], p[1], p[2]))
        else:
            csv.append(pre + "%.8f,%.8f,%.8f,%d,%d,%d" % (p[0], p[1], p[2], c[0], c[1], c[2]))
    return "\n".join(rep) + "\n", "\n".join(csv) + "\n"


def probe89(gt):
    p = gt["positions"][0]
    c = gt["colors"][0]
    return ("%d points; point[0] %.8f %.8f %.8f col %d %d %d; werk-gsplat werk-pointcloud splat-to-ply"
            % ((gt["count"],) + tuple(p) + tuple(c)))


def run(fixture, d, extra=()):
    js = os.path.join(d, "_grade.json")
    p = subprocess.run([sys.executable, GRADER, "--fixture", fixture, "--rundir", d,
                        "--prog", "solution.py", "--json-out", js] + list(extra),
                       capture_output=True, timeout=600)
    if p.returncode != 0 or not os.path.exists(js):
        raise SystemExit("grader failed on %s:\n%s" % (d, p.stderr.decode("utf-8", "replace")))
    with open(js, "r", encoding="utf-8") as f:
        return json.load(f)


def write(d, files):
    for name, text in files.items():
        fp = os.path.join(d, name)
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        with open(fp, "w", encoding="utf-8") as f:
            f.write(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", default=os.path.join(HERE, "..", "..", "fixtures", "gsplat-v1.werk"))
    ap.add_argument("--keep", action="store_true", help="keep the temp run dirs")
    args = ap.parse_args()
    fixture = os.path.abspath(args.fixture)
    if not os.path.exists(fixture):
        print("fixture missing: %s (run tools/fetch_fixtures.py); nothing tested" % fixture)
        return 2

    gt = grade_gsplat.ground_truth(fixture, None)        # every point
    rep, csv = evidence(gt)                               # the complete table
    rep32, csv32 = evidence(gt, rows=ROWS)                # 32 rows only
    prompt = open(os.path.join(HERE, "PROMPT-gsplattask.txt"), encoding="utf-8").read()
    pkg_copy = ""
    with zipfile.ZipFile(fixture) as z:
        pkg_copy = z.read("MANIFEST.json").decode("utf-8")

    # name -> (files, extra grader flags, expected full, expected numeric)
    cases = [
        ("89-char report only",
         {"REPORT.md": probe89(gt)}, (), "FAIL", "PASS"),
        ("prompt copy holding full evidence",
         {"PROMPT-copy.txt": prompt + rep + csv, "REPORT.md": "see prompt"}, (), "FAIL", "FAIL"),
        ("helper source holding full evidence",
         {"helper.py": '"""\n' + rep + csv + '\n"""', "REPORT.md": "done"}, (), "FAIL", "FAIL"),
        ("program source holding full evidence",
         {"solution.py": '"""\n' + rep + csv + '\n"""'}, (), "FAIL", "FAIL"),
        ("program source with --include-source (pre-revision scan; source is never a point table)",
         {"solution.py": '"""\n' + rep + csv + '\n"""'}, ("--include-source",), "FAIL", "PASS"),
        ("first row only, everything else right",
         {"REPORT.md": rep, "points.csv": evidence(gt, first_row_only=True)[1]}, (), "FAIL", "PASS"),
        ("first 32 rows only, everything else right",
         {"REPORT.md": rep32, "points.csv": csv32}, (), "FAIL", "PASS"),
        ("complete table, row 2 colour off by one u8 step",
         {"REPORT.md": rep, "points.csv": evidence(gt, colour_bump_row=1)[1]}, (), "FAIL", "PASS"),
        ("complete table, interior row 1000 colour off by one",
         {"REPORT.md": rep, "points.csv": evidence(gt, colour_bump_row=1000)[1]}, (), "FAIL", "PASS"),
        ("complete table, positions only",
         {"REPORT.md": rep, "points.csv": evidence(gt, positions_only=True)[1]}, (), "FAIL", "FAIL"),
        ("complete table, last row missing",
         {"REPORT.md": rep, "points.csv": "\n".join(csv.splitlines()[:-1]) + "\n"}, (), "FAIL", "PASS"),
        ("NaN positions, right colours",
         {"REPORT.md": rep, "points.csv": evidence(gt, nan_rows=True)[1]}, (), "FAIL", "FAIL"),
        ("unpacked package copy beside a thin report",
         {"REPORT.md": probe89(gt), "x/MANIFEST.json": pkg_copy, "x/spec.md.txt": pkg_copy},
         (), "FAIL", "PASS"),
        ("no digest printed (integrity by words only)",
         {"REPORT.md": rep.replace("digests checked: ", "digests checked: none "
                                   ).replace(gt["declared_digests"][0], "")
                       .replace(gt["declared_digests"][1], "").replace(gt["declared_digests"][2], ""),
          "points.csv": csv}, (), "FAIL", "PASS"),
        ("no artifact at all",
         {"solution.py": "print('hi')\n"}, (), "FAIL", "FAIL"),
        ("correct complete run (committed mode: clause 1 cannot be established)",
         {"REPORT.md": rep, "points.csv": csv}, (), "FAIL", "PASS"),
        ("same, header with digits (r_u8,g_u8,b_u8)",
         {"REPORT.md": rep,
          "points.csv": csv.replace("x,y,z,r,g,b", "x,y,z,r_lin,g_lin,b_lin,r_u8,g_u8,b_u8", 1)},
         (), "FAIL", "PASS"),
        ("same, index column",
         {"REPORT.md": rep, "points.csv": evidence(gt, index_column=True)[1]}, (), "FAIL", "PASS"),
    ]

    # Without --rerun, clause 1 is never established, so the committed-mode
    # cases can at best fail on clause 1 alone. The two cases below exercise
    # the damage check itself with --rerun.
    root = tempfile.mkdtemp(prefix="gsplat-adv-")
    bad = 0
    print("%-48s %-6s %-8s %-6s %-8s %s" % ("case", "full", "(want)", "num", "(want)", "ok"))
    for i, (name, files, extra, want_full, want_num) in enumerate(cases):
        d = os.path.join(root, "case%02d" % i)
        os.makedirs(d)
        if "solution.py" not in files:
            files = dict(files, **{"solution.py": "# placeholder program\n"})
        write(d, files)
        r = run(fixture, d, extra)
        ok = r["verdict"] == want_full and r["verdict_numeric"] == want_num
        if name.startswith("correct complete run") or name.startswith("same, "):
            # the only failing clause may be clause 1
            ok = ok and r["full_task_failing"] == [x for x in r["full_task_failing"] if x.startswith("1 ")]
        bad += 0 if ok else 1
        print("%-48s %-6s %-8s %-6s %-8s %s%s" % (
            name, r["verdict"], "(" + want_full + ")", r["verdict_numeric"], "(" + want_num + ")",
            "ok" if ok else "WRONG",
            "" if r["verdict"] == "PASS" else "   failing: " + "; ".join(r["full_task_failing"])))
    # ---- the damage check, with --rerun: an honest verifier and a liar
    HONEST = (
        "import hashlib, json, sys, zipfile\n"
        "z = zipfile.ZipFile(sys.argv[1]); man = json.loads(z.read('MANIFEST.json')); bad = 0\n"
        "for n in man['nodes']:\n"
        "    for v in n['versions']:\n"
        "        for f in v['files']:\n"
        "            if hashlib.sha256(z.read(f['path'])).hexdigest() != f['sha256']:\n"
        "                bad += 1; print('MISMATCH', f['path'])\n"
        "print('sha-256 of every declared file verified:', 'OK' if bad == 0 else 'FAIL (%d)' % bad)\n"
        "sys.exit(1 if bad else 0)\n")
    LIAR = "print('sha-256 of every declared file verified: OK')\nprint('281498 points')\n"
    print("\n%-48s %-10s %-10s %s" % ("damage check (--rerun)", "integrity", "(want)", "ok"))
    for i, (name, prog, want) in enumerate([("honest verifier", HONEST, True), ("liar", LIAR, False)]):
        d = os.path.join(root, "damage%02d" % i)
        os.makedirs(d)
        write(d, {"solution.py": prog})
        r = run(fixture, d, ("--rerun", "--out", os.path.join(d, "_clean"), "--prog-arg",
                             os.path.basename(fixture), "--no-report"))
        ok = r["integrity_ok"] == want and bool(r["damage_check"]) and r["damage_check"]["detected"] == want
        bad += 0 if ok else 1
        print("%-48s %-10s %-10s %s   %s" % (name, r["integrity_ok"], want, "ok" if ok else "WRONG",
                                              r.get("integrity_how")))
    if not args.keep:
        shutil.rmtree(root, ignore_errors=True)
    else:
        print("run dirs kept under", root)
    print("\n%s" % ("ALL CASES HOLD" if bad == 0 else "%d CASE(S) WRONG" % bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
