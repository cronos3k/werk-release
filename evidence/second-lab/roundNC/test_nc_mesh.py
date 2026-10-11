#!/usr/bin/env python3
"""
test_nc_mesh.py -- adversarial cases for nc_mesh.compare_positions.

Grader revision 2026-10-12. The frozen 504a9ac grader graded an all-NaN
position file as 'VALUES' (its test was `abs(a - b) > TOL`, which is False
for NaN) and let a shorter expected array pass by zip truncation. Every
case below must hold for the revised grader; the "frozen" column in the
output shows what the pre-registered grader returned, for the record.

  py -3.13 test_nc_mesh.py            (exit 0 = all cases hold)

Standard library only. No fixture needed; the sub-mesh slice check runs
only when expectations.json and its dump files are present.
"""

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nc_mesh  # noqa: E402

NAN = float("nan")
INF = float("inf")


def frozen_compare(got, exp_rec, exp_positions=None):
    """The 504a9ac predicate, verbatim, for the record."""
    if len(got) != exp_rec["vertex_count"]:
        return None
    if exp_positions is not None:
        ok = True
        for a, b in zip(got, exp_positions):
            if abs(a[0] - b[0]) > nc_mesh.TOL or abs(a[1] - b[1]) > nc_mesh.TOL \
                    or abs(a[2] - b[2]) > nc_mesh.TOL:
                ok = False
                break
        if ok:
            return "VALUES"
    gb = nc_mesh.bbox(got)
    if all(abs(x - y) <= nc_mesh.TOL for x, y in zip(gb, exp_rec["bbox"])):
        return "COUNT+BBOX"
    return None


def main():
    exp = [(float(i), 0.5 * i, -float(i)) for i in range(10)]
    rec = nc_mesh.mesh_record(exp, 4)

    swapped = list(exp)
    swapped[3], swapped[6] = swapped[6], swapped[3]          # same bbox, wrong interior
    cases = [
        # name, got, exp_positions, revised must be, revised must not be
        ("exact values", exp, exp, "VALUES", None),
        ("all NaN", [(NAN, NAN, NAN)] * 10, exp, None, "VALUES"),
        ("one NaN", exp[:9] + [(NAN, 1.0, 2.0)], exp, None, "VALUES"),
        ("inf", exp[:9] + [(INF, 1.0, 2.0)], exp, None, "VALUES"),
        ("short tuple", exp[:9] + [(1.0, 2.0)], exp, None, "VALUES"),
        ("wrong interior, same bbox", swapped, exp, "COUNT+BBOX", "VALUES"),
        ("expected array shorter than got", exp, exp[:5], "COUNT+BBOX", "VALUES"),
        ("wrong count", exp[:9], exp, None, None),
        ("no expected array (bbox only)", exp, None, "COUNT+BBOX", "VALUES"),
    ]
    bad = 0
    print("%-36s %-12s %-12s %s" % ("case", "revised", "frozen", "ok"))
    for name, got, ep, want, forbid in cases:
        try:
            fro = frozen_compare(got, rec, ep)
        except Exception as e:  # the frozen predicate can raise on short tuples
            fro = "raise:%s" % type(e).__name__
        rev = nc_mesh.compare_positions(got, rec, ep)
        ok = (rev == want) and (forbid is None or rev != forbid)
        bad += 0 if ok else 1
        print("%-36s %-12s %-12s %s" % (name, rev, fro, "ok" if ok else "WRONG"))

    # non-finite counter
    assert nc_mesh.nonfinite_count([(NAN, 0, 0), (0, INF, 0), (1, 2), (0, 0, 0)]) == 3

    # sub-mesh slices of the frozen dumps, if the ground truth is here
    ex = os.path.join(HERE, "expectations.json")
    if os.path.exists(ex):
        with open(ex, "r", encoding="utf-8") as f:
            doc = json.load(f)
        for fmt, e in doc["formats"].items():
            t2 = e.get("tier2_mesh") or {}
            if not t2.get("dump_file"):
                continue
            dp = os.path.join(HERE, t2["dump_file"])
            if not os.path.exists(dp):
                print("%-8s dump file missing, slice check skipped" % fmt)
                continue
            with open(dp, "rb") as f:
                dump = nc_mesh.dump_floats(f.read())
            sl = nc_mesh.submesh_slices(t2, dump)
            subs = t2.get("submeshes", [])
            total = sum(s["vertex_count"] for s in subs)
            print("%-8s %d/%d sub-mesh slices verify against their pinned dump_sha256; "
                  "sub-mesh vertices %d of dump %d" % (fmt, len(sl), len(subs), total, len(dump)))
            for s in subs:
                if s["mesh_name"] in sl:
                    got = sl[s["mesh_name"]]
                    assert nc_mesh.compare_positions(got, s, got) == "VALUES"
                    # a NaN'd copy of the slice must not match the sub-mesh either
                    nanned = list(got)
                    nanned[0] = (NAN, NAN, NAN)
                    assert nc_mesh.compare_positions(nanned, s, got) is None
            if len(sl) != len(subs):
                bad += 1
                print("         WRONG: a sub-mesh slice did not verify")
    print("\n%s" % ("ALL CASES HOLD" if bad == 0 else "%d CASE(S) WRONG" % bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
