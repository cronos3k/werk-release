#!/usr/bin/env python3
"""
grade_nc.py -- artifact grading for roundNC (negative-control round).

A variant of gauntlet/roundOW/grade.py. Same rule: an agent's report is
evidence about the agent; success is decided by hashing bytes on disk. The
difference: ground truth comes from expectations.json (built at fixture time,
kept outside every agent workspace), not from a MANIFEST inside the fixture,
so the werk baseline and the controls go through ONE code path.

  py -3.13 grade_nc.py --rundir <dir> --format {werk,gltf,fbx,usdz} [--payload {sound,texture}]
  py -3.13 grade_nc.py --rerun --rundir <dir> --format F --prog <script> --out <cleandir>
  py -3.13 grade_nc.py --echo-check <workspace> --format F

Clauses (plan section 3, pre-registered):
  C1 open        program exits 0 (needs --rerun) and enumerates the structure
  C2 meanings    NEEDS-HUMAN-REVIEW (evidence excerpted)
  C3 integrity   NEEDS-HUMAN-REVIEW (evidence + what the file declares)
  C4 extract     the named payloads exist on disk in the run dir
  C5 hash match  Tier 1 sha256 match, or Tier 2 mesh match for the mesh class
Human rulings are supplied back with --human C2=PASS --human C3=PASS-honest.

Verdicts:
  PASS     C1..C5 all pass (C3 = PASS-honest allowed)
  PARTIAL  at least one Tier 1 or Tier 2 artifact exact, but not all clauses
  FAIL     program does not run clean, or no graded artifact matches
  PENDING  every auto-graded clause passes, but a human ruling (C2/C3) or the
           clean re-run (C1) is still missing. Not a final verdict.

Standard library only.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nc_mesh  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rerun_support import prepare_output, program_args, run_python


HARNESS_FILES = {"PROMPT.txt", "REPORT.md", "_agent-stdout.txt", "_agent-stderr.txt"}
CLASS_EXT = {
    "mesh": (".glb", ".gltf", ".obj", ".ply", ".fbx", ".usd", ".usdc", ".usda",
             ".stl", ".bin", ".f32", ".raw"),
    "sound": (".wav", ".ogg", ".mp3", ".flac", ".aif", ".aiff"),
    "texture": (".png", ".jpg", ".jpeg", ".tga", ".bmp", ".ktx2", ".dds",
                ".webp", ".tif", ".tiff"),
}
C2_KW = re.compile(r"mesh|texture|sound|audio|image|material|scene|node|buffer|"
                   r"accessor|geometry|meaning|semantic|primitive|wav|png|glb", re.I)
C3_KW = re.compile(r"integrit|verif|hash|sha-?256|crc|checksum|signature|"
                   r"declar|could not|cannot|unverif|no .*check", re.I)


def default_repo():
    for c in (os.path.join(HERE, "..", ".."), os.path.join(HERE, "..", "werk")):
        if os.path.exists(os.path.join(c, "gauntlet", "roundOW", "mini-v1.werk")):
            return os.path.normpath(c)
    return None


def load_exp(path, fmt, allow_prov):
    with open(path, "r", encoding="utf-8") as f:
        doc = json.load(f)
    e = doc["formats"][fmt]
    if e["status"] == "STUB":
        raise SystemExit("ABORT: format %s is a STUB in %s (fixture not built)" % (fmt, path))
    if e["status"] != "COMPLETE" and not allow_prov:
        raise SystemExit("ABORT: format %s ground truth is %s; pass --allow-provisional "
                         "to grade anyway (dry-run only)" % (fmt, e["status"]))
    t2 = e.get("tier2_mesh")
    dump = None
    if t2 and t2.get("dump_file"):
        p = os.path.join(os.path.dirname(os.path.abspath(path)), t2["dump_file"])
        if nc_mesh.sha256_file(p) != t2["dump_file_sha256"]:
            raise SystemExit("ABORT: %s does not match its pinned sha256" % p)
        with open(p, "rb") as f:
            dump = nc_mesh.dump_floats(f.read())
    return doc, e, dump


# ------------------------------------------------------------------ re-run

def do_rerun(args, e):
    out = prepare_output(args.out, [args.rundir, args.repo])
    for ff in e["fixture_files"]:
        src = os.path.join(args.repo, ff["path"])
        if nc_mesh.sha256_file(src) != ff["sha256"]:
            raise ValueError("fixture hash differs from frozen expectation: " + ff["name"])
        dst = os.path.realpath(os.path.join(out, ff["name"]))
        if os.path.commonpath([out, dst]) != out:
            raise ValueError("fixture name leaves the scratch directory")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
    src = os.path.join(args.rundir, args.prog)
    shutil.copy2(src, os.path.join(out, os.path.basename(args.prog)))
    result = run_python(os.path.basename(args.prog), program_args(args), out)
    print("\n=== RE-RUN in clean dir %s ===" % out)
    print("run status: %s; exit: %s; seconds: %s" %
          (result["status"], result["exit"], result["secs"]))
    print(result["stdout"])
    if result["stderr"]:
        print(result["stderr"], file=sys.stderr)
    return out, result


# --------------------------------------------------------------- the walk

def walk(scan, e, dump):
    pays = e.get("payloads", [])
    by_sha = {}
    for p in pays:
        by_sha.setdefault(p["sha256"], []).append(p)
    by_base = {}
    for p in pays:
        by_base.setdefault(os.path.basename(p["path"]), []).append(p)
    declared_all = e.get("tier1_declared_all", {})
    inputs = {ff["name"].replace("\\", "/"): ff["sha256"] for ff in e["fixture_files"]}
    t2 = e.get("tier2_mesh")
    sub_slices = nc_mesh.submesh_slices(t2, dump)

    rows = []
    notes = []
    for root, dirs, files in os.walk(scan):
        dirs[:] = sorted(d for d in dirs if d != "_harness")
        for name in sorted(files):
            fp = os.path.join(root, name)
            rel = os.path.relpath(fp, scan).replace("\\", "/")
            if rel in HARNESS_FILES:
                continue
            size = os.path.getsize(fp)
            if size == 0:
                continue
            got = nc_mesh.sha256_file(fp)
            if rel in inputs:
                if got == inputs[rel]:
                    continue  # the input itself, not an extraction
                notes.append("INPUT MODIFIED: %s (sha256 %s != pinned %s); constraint 5"
                             % (rel, got[:16], inputs[rel][:16]))
                continue
            r = {"rel": rel, "sha256": got, "size": size, "status": "?", "class": None,
                 "payload": None, "tier": None, "detail": ""}
            ext = os.path.splitext(name)[1].lower()
            if got in by_sha:
                p = by_sha[got][0]
                r.update(status="OK", tier="T1")
                r["class"], r["payload"] = p["class"], p["id"]
            elif t2 and got == t2["dump_sha256"]:
                r.update(status="OK", tier="T2-EXACT", detail="canonical dump bytes")
                r["class"] = "mesh"
            elif got in declared_all.values():
                k = [k for k, v in declared_all.items() if v == got][0]
                r.update(status="OK-DECLARED", tier="T1", detail="non-payload declared file " + k)
            else:
                named = by_base.get(name)
                if named:
                    p = named[0]
                    r.update(status="XX", tier="T1",
                             detail="name matches payload %s but sha256 != %s"
                             % (p["id"], p["sha256"][:16]))
                    r["class"], r["payload"] = p["class"], p["id"]
                if t2:
                    res = nc_mesh.positions_from_file(fp)
                    if res:
                        kind, pos, tri = res
                        bad = nc_mesh.nonfinite_count(pos)
                        m = nc_mesh.compare_positions(pos, t2, dump)
                        if m == "COUNT+BBOX" and kind != "text":
                            m = None  # plan 1.3: count+bbox only for a text dump
                        sub = []
                        if not m and len(t2.get("submeshes", [])) > 1:
                            # grader revision 2026-10-12: a sub-mesh match is
                            # decided on its VALUES (the verified slice of the
                            # frozen dump), not on count+bbox alone. Where no
                            # verified slice exists the frozen count+bbox test
                            # is kept and the detail says so.
                            for s in t2["submeshes"]:
                                exp = sub_slices.get(s["mesh_name"])
                                sm = nc_mesh.compare_positions(pos, s, exp)
                                if sm == "COUNT+BBOX" and (exp is not None or kind != "text"):
                                    sm = None
                                if sm:
                                    sub.append("%s(%s%s)" % (s["mesh_name"], sm,
                                                             "" if exp is not None else ",unverified-slice"))
                        info = "parsed %d positions (%s)" % (len(pos), kind)
                        if bad:
                            info += "; %d non-finite or short positions (never a match)" % bad
                        if r["status"] == "XX":
                            r["detail"] += "; tier2 (not counted, file is XX): %s %s" % (info, m or "no match")
                        elif m:
                            r.update(status="OK", tier="T2-" + m, detail=info)
                            r["class"] = "mesh"
                        elif sub and t2.get("accept_submesh_as_c5"):
                            r.update(status="OK", tier="T2-SUBMESH", detail=info + " = " + ",".join(sub))
                            r["class"] = "mesh"
                        elif sub:
                            r.update(status="SUBMESH", tier="T2-SUBMESH",
                                     detail=info + " equals submesh " + ",".join(sub) +
                                     " only (counts for PARTIAL, not C5)")
                            r["class"] = "mesh"
                        elif r["status"] == "?":
                            r["detail"] = info + "; no tier2 match"
            if r["class"] is None:
                for c, exts in CLASS_EXT.items():
                    if ext in exts:
                        r["ext_class"] = c
            rows.append(r)
    return rows, notes


# ---------------------------------------------------------------- evidence

def excerpt(text, rx, limit=40):
    out = []
    for i, ln in enumerate(text.splitlines(), 1):
        if rx.search(ln):
            out.append("%4d: %s" % (i, ln.rstrip()[:200]))
            if len(out) >= limit:
                out.append("      ... (truncated)")
                break
    return out


def read_text(p):
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


# ------------------------------------------------------------------- grade

def grade(args, doc, e, dump, scan, exit_code, prog_stdout):
    rows, notes = walk(scan, e, dump)
    second = args.payload
    absent = second in e.get("absent_classes", [])
    have_truth = any(p["class"] == second for p in e.get("payloads", []))
    req = ["mesh"] + ([] if absent else [second])

    print("\n=== ARTIFACT HASHES (graded here, not self-reported) ===")
    for r in rows:
        tag = {"OK": "OK", "OK-DECLARED": "ok", "XX": "XX", "SUBMESH": "~~"}.get(r["status"], " ?")
        print("  %s %-52s %s  %-14s %s %s" % (tag, r["rel"], r["sha256"][:16], r["tier"] or "",
                                           r["payload"] or r["class"] or r.get("ext_class") or "",
                                           r["detail"]))
    for n in notes:
        print("  !! " + n)

    clauses = {}
    # C1
    run_status = getattr(args, "run_status", "not-run")
    if run_status == "host-error":
        clauses["C1"] = {"result": "HOST-ERROR", "why": "host could not launch the program"}
    elif run_status == "program-timeout":
        clauses["C1"] = {"result": "FAIL", "why": "program exceeded the timeout"}
    elif exit_code is None:
        clauses["C1"] = {"result": "NOT-RUN", "why": "exit code needs --rerun"}
    elif exit_code != 0:
        clauses["C1"] = {"result": "FAIL", "why": "exit %d in clean dir" % exit_code}
    else:
        names = set()
        for p in e.get("payloads", []):
            names.add(os.path.basename(p["path"]))
        for ff in e["fixture_files"]:
            names.add(os.path.basename(ff["name"]))
        for k in e.get("tier1_declared_all", {}):
            names.add(os.path.basename(k))
        for s in (e.get("tier2_mesh") or {}).get("submeshes", []):
            if s.get("mesh_name"):
                names.add(s["mesh_name"])
        seen = sorted(n for n in names if n and n in (prog_stdout or ""))
        if len(seen) >= 2:
            clauses["C1"] = {"result": "PASS", "why": "exit 0; stdout names %d structure "
                             "entries (%s)" % (len(seen), ", ".join(seen[:6]))}
        else:
            clauses["C1"] = {"result": "NEEDS-HUMAN-REVIEW",
                             "why": "exit 0 but stdout names <2 known entries; check enumeration",
                             "evidence": (prog_stdout or "").splitlines()[:40]}
    # evidence sources for C2/C3
    report = read_text(os.path.join(args.rundir, "REPORT.md")) or ""
    agent_out = prog_stdout if prog_stdout is not None else (
        read_text(os.path.join(args.rundir, "_agent-stdout.txt")) or "")
    for c, rx, what in (("C2", C2_KW, "listing names the payloads and states what they are"),
                        ("C3", C3_KW, "verifies what the file declares AND reports what "
                                      "could not be verified; invented verification = FAIL")):
        ev = {"REPORT.md": excerpt(report, rx), "program stdout": excerpt(agent_out, rx)}
        clauses[c] = {"result": "NEEDS-HUMAN-REVIEW", "criterion": what, "evidence": ev}
        if c == "C3":
            clauses[c]["file_declares"] = e["integrity_declared_by_file"]["declares"]
    # C4
    c4 = {}
    for cls in req:
        hits = [r["rel"] for r in rows if r["class"] == cls or r.get("ext_class") == cls]
        c4[cls] = hits
    clauses["C4"] = {"result": "PASS" if all(c4.values()) else "FAIL",
                     "candidates": c4}
    # C5
    c5 = {}
    for cls in req:
        ok = [r for r in rows if r["class"] == cls and r["status"] == "OK"]
        bad = [r for r in rows if r["class"] == cls and r["status"] == "XX"]
        if cls != "mesh" and not have_truth:
            c5[cls] = "UNAVAILABLE (no ground truth for this class: inputs missing)"
        elif ok and not bad:
            c5[cls] = "PASS via " + ", ".join("%s[%s]" % (r["rel"], r["tier"]) for r in ok)
        elif bad:
            c5[cls] = "FAIL: mismatch " + ", ".join(r["rel"] for r in bad)
        else:
            c5[cls] = "FAIL: no matching artifact"
    clauses["C5"] = {"result": "PASS" if all(v.startswith("PASS") for v in c5.values()) else "FAIL",
                     "per_class": c5}
    if absent:
        clauses["C5"]["note"] = "%s is N/A for %s (absent_classes); graded on mesh only" % (second, args.format)
        clauses["C4"]["note"] = clauses["C5"]["note"]

    # human rulings
    for h in args.human:
        k, _, v = h.partition("=")
        if k in clauses:
            clauses[k]["result"] = v
            clauses[k]["ruled_by_human"] = True

    # verdict
    graded_match = any(r["status"] in ("OK", "SUBMESH") and r["class"] for r in rows)
    res = {k: v["result"] for k, v in clauses.items()}
    passing = lambda v: v in ("PASS", "PASS-honest")
    if run_status == "host-error":
        verdict, why = "HOST-ERROR", "host could not launch the program"
    elif run_status == "program-timeout":
        verdict, why = "FAIL", "program exceeded the timeout"
    elif exit_code not in (None, 0):
        verdict = "FAIL"
        why = "program does not run clean"
    elif not graded_match:
        verdict = "FAIL"
        why = "no graded artifact matches"
    elif all(passing(v) for v in res.values()):
        verdict = "PASS"
        why = "C1..C5 all pass"
    elif any(v == "FAIL" for v in res.values()):
        verdict = "PARTIAL"
        why = "graded artifact(s) exact, failing: " + ",".join(k for k, v in res.items() if v == "FAIL")
    else:
        verdict = "PENDING"
        why = "auto clauses pass; awaiting: " + ",".join(
            k for k, v in res.items() if not passing(v))

    # verifiable-integrity fraction (plan 3): over the payloads extracted
    # (matched), weighted by stored payload bytes.
    pays = {p["id"]: p for p in e.get("payloads", [])}
    mesh_primary = [p for p in e.get("payloads", []) if p["class"] == "mesh" and p.get("primary")]
    t2 = e.get("tier2_mesh") or {}
    def vif_over(classes):
        got = {}
        for r in rows:
            if r["status"] != "OK" or not r["class"] or r["class"] not in classes:
                continue
            if r["payload"]:
                p = pays[r["payload"]]
                got[p["id"]] = (p["size"], p["integrity"])
            elif r["class"] == "mesh":
                if mesh_primary:
                    p = mesh_primary[0]
                    got[p["id"]] = (p["size"], p["integrity"])
                else:
                    # Tier 2 mesh: integrity = what covers the stored mesh bytes
                    # (USDZ: the zip CRC-32 of the usdc entry; FBX: nothing).
                    got["mesh:tier2"] = (t2.get("dump_size", 0), t2.get("integrity", []))
        tot = sum(s for s, _ in got.values())
        return {
            "payloads_counted": sorted(got),
            "bytes": tot,
            "any_declared": round(sum(s for s, i in got.values() if i) / tot, 6) if tot else None,
            "cryptographic": round(sum(s for s, i in got.values() if "sha256" in i) / tot, 6) if tot else None,
            "kinds": sorted({k for _, i in got.values() for k in i}),
        }
    # Headline: the required payload classes only (mesh + second payload), so
    # extra extractions do not move the number. 'all_extracted' sits beside it.
    vif = vif_over(set(req))
    vif["all_extracted"] = vif_over({"mesh", "sound", "texture"})

    print("\n=== CLAUSES (format=%s, second payload=%s%s) ===" % (
        args.format, second, " N/A" if absent else ""))
    for k in ("C1", "C2", "C3", "C4", "C5"):
        v = clauses[k]
        print("  %s %-20s %s" % (k, v["result"], v.get("why", "") or v.get("criterion", "")))
        if k == "C3":
            print("       file declares: %s" % v["file_declares"])
        if "per_class" in v:
            for c, s in v["per_class"].items():
                print("       %-8s %s" % (c, s))
        if "candidates" in v:
            for c, s in v["candidates"].items():
                print("       %-8s %s" % (c, ", ".join(s) or "(none)"))
        if v.get("note"):
            print("       note: " + v["note"])
        ev = v.get("evidence")
        if v["result"] == "NEEDS-HUMAN-REVIEW" and ev:
            if isinstance(ev, dict):
                for src, lines in ev.items():
                    print("       evidence from %s:" % src)
                    for ln in lines or ["(nothing matched)"]:
                        print("         " + ln)
            else:
                for ln in ev:
                    print("         " + ln)
    print("\n=== VERIFIABLE-INTEGRITY FRACTION ===")
    for lab, v in (("required", vif), ("all extracted", vif["all_extracted"])):
        print("  %-13s any declared: %s   cryptographic: %s   kinds: %s   over %s" % (
            lab, v["any_declared"], v["cryptographic"], v["kinds"] or "none", v["payloads_counted"]))
    print("\n=== VERDICT: %s  (%s) ===" % (verdict, why))
    if e["status"] != "COMPLETE":
        print("  WARNING: ground truth for %s is %s; this verdict is NOT reportable."
              % (args.format, e["status"]))
    return {"format": args.format, "payload": second, "second_payload_na": absent,
            "score_version": "post-hoc-rerun-2026-10-11",
            "rerun": getattr(args, "run_result", None),
            "ground_truth_status": e["status"], "scan_dir": scan, "exit_code": exit_code,
            "rows": rows, "notes": notes, "clauses": clauses, "verdict": verdict,
            "verdict_reason": why, "verifiable_integrity_fraction": vif}


# --------------------------------------------------------------- echo check

def echo_check(ws, doc, e, fmt):
    """Plan 5.7 / roundGF: no expected hash value may appear in any file of an
    agent workspace. Values the fixture legitimately declares about itself
    (werk MANIFEST sha256) are its integrity data, not a leak, and are
    reported separately. Anything else found is a LEAK."""
    vals = {}
    for p in e.get("payloads", []):
        vals[p["sha256"]] = "payload " + p["id"]
    for k, v in e.get("tier1_declared_all", {}).items():
        vals.setdefault(v, "declared " + k)
    t2 = e.get("tier2_mesh") or {}
    if t2:
        vals[t2["dump_sha256"]] = "tier2 canonical dump"
        vals[t2["dump_file_sha256"]] = "tier2 dump file"
        for s in t2.get("submeshes", []):
            vals.setdefault(s["dump_sha256"], "tier2 submesh " + str(s["mesh_name"]))
    self_declared = set(e.get("tier1_declared_all", {}).values())

    blobs = []
    for root, dirs, files in os.walk(ws):
        for n in files:
            fp = os.path.join(root, n)
            rel = os.path.relpath(fp, ws).replace("\\", "/")
            with open(fp, "rb") as f:
                b = f.read()
            blobs.append((rel, b))
            if n.lower().endswith((".werk", ".usdz", ".zip")):
                try:
                    with zipfile.ZipFile(fp) as z:
                        for i in z.infolist():
                            blobs.append((rel + "!" + i.filename, z.read(i.filename)))
                except zipfile.BadZipFile:
                    pass
    leaks, allowed = [], []
    for rel, b in blobs:
        low = b.lower()
        if b"expectations" in low and rel.endswith(".json"):
            leaks.append((rel, "file looks like an expectations file"))
        for h, what in vals.items():
            hit = h.encode() in low or bytes.fromhex(h) in b
            if not hit:
                continue
            in_fixture = rel.split("!")[0] in {ff["name"] for ff in e["fixture_files"]}
            if in_fixture and h in self_declared:
                allowed.append((rel, h[:16], what))
            else:
                leaks.append((rel, "%s (%s)" % (h[:16], what)))
    print("=== ECHO CHECK %s (format=%s) ===" % (ws, fmt))
    print("  files scanned: %d (incl. zip members)   hash values checked: %d" % (len(blobs), len(vals)))
    print("  self-declared by fixture (allowed, the format's own integrity data): %d" % len(allowed))
    for a in allowed[:5]:
        print("     %s  %s  %s" % a)
    if len(allowed) > 5:
        print("     ... %d more" % (len(allowed) - 5))
    print("  LEAKS: %d" % len(leaks))
    for l in leaks:
        print("     LEAK %s  %s" % l)
    print("  ECHO CHECK: %s" % ("PASS" if not leaks else "FAIL"))
    return {"workspace": ws, "format": fmt, "files_scanned": len(blobs),
            "values_checked": len(vals), "allowed_self_declared": len(allowed),
            "leaks": leaks, "result": "PASS" if not leaks else "FAIL"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rundir")
    ap.add_argument("--format", required=True, choices=["werk", "gltf", "fbx", "usdz"])
    ap.add_argument("--payload", choices=["sound", "texture"], default="sound",
                    help="second payload class (decision D2). werk baseline: sound.")
    ap.add_argument("--expectations", default=os.path.join(HERE, "expectations.json"))
    ap.add_argument("--repo", default=default_repo())
    ap.add_argument("--rerun", action="store_true")
    ap.add_argument("--prog", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--prog-args", default=None, help="shell-style argument string")
    ap.add_argument("--prog-arg", action="append", default=[], help="one verbatim argument; repeatable")
    ap.add_argument("--human", action="append", default=[],
                    help="human ruling, e.g. C2=PASS or C3=PASS-honest or C3=FAIL")
    ap.add_argument("--allow-provisional", action="store_true")
    ap.add_argument("--echo-check", metavar="WORKSPACE")
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    doc, e, dump = load_exp(args.expectations, args.format, args.allow_provisional)
    if args.echo_check:
        res = echo_check(args.echo_check, doc, e, args.format)
    else:
        if not args.rundir:
            raise SystemExit("--rundir is required")
        print("format        : %s (%s)" % (args.format, e["status"]))
        for ff in e["fixture_files"]:
            print("fixture file  : %s  %s" % (ff["path"], ff["sha256"]))
        print("expectations  : %s" % args.expectations)
        exit_code = prog_stdout = None
        if args.rerun:
            if not (args.prog and args.out):
                raise SystemExit("--rerun needs --prog and --out")
            scan, args.run_result = do_rerun(args, e)
            args.run_status = args.run_result["status"]
            exit_code, prog_stdout = args.run_result["exit"], args.run_result["stdout"]
        else:
            scan = args.rundir
        res = grade(args, doc, e, dump, scan, exit_code, prog_stdout)
    if args.json:
        with open(args.json, "w", encoding="utf-8", newline="\n") as f:
            json.dump(res, f, indent=2)
            f.write("\n")


if __name__ == "__main__":
    main()
