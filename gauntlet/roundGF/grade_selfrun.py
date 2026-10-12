#!/usr/bin/env python3
"""
grade_selfrun.py -- artifact grading for the GAP-COMPLETION round's adapted
self-run arm.

roundSR's grade was: does the built runtime's stdout, CRLF-normalised to LF,
hash to the vector the package carries? That is decided here from the bytes the
run left behind, not from the model's claims, and the vectors are read out of
the pinned fixture rather than hard-coded.

Two independent grades, both reported:

  A. AN ECHO CHECK, WHICH IS NOT EVIDENCE, AND IS LABELLED AS SUCH. Every text
     file the run wrote is scanned for each vector's exact generated text.
     BEWARE: `testvectors/generate-*.stdout.txt` and `vectors.json` are INSIDE
     the package and are therefore INLINED in this arm's prompt, so a model can
     print the expected text and the expected digest without building anything.
     The first version of this grader called that PASS. It is reported and it
     never decides.
  B. THE ONLY GRADE THAT DECIDES. If the run left an
     executable behind, this grader invokes it itself with the vector's own
     `argv` and hashes the result. That is the harness re-running the artifact
     in the grader's hands rather than the model's, which is `grade.py`'s
     clean-directory re-run adapted to a compiled tool.

  python grade_selfrun.py --fixture gauntlet/roundSR/selfrun-v1.werk \
                          --rundir <dir> [--json-out f.json]
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rerun_support import run_command


def lf(b):
    return b.replace(b"\r\n", b"\n")


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", required=True)
    ap.add_argument("--rundir", required=True)
    ap.add_argument("--json-out", default="")
    ap.add_argument("--no-exec", action="store_true",
                    help="skip grade B (do not invoke a binary the run built)")
    args = ap.parse_args()

    with zipfile.ZipFile(args.fixture) as z:
        vec = json.loads(z.read("testvectors/vectors.json"))
    vectors = vec["vectors"]
    print("fixture  : %s" % args.fixture)
    print("vectors  : %d" % len(vectors))
    for v in vectors:
        print("  %-20s steps=%d t=%s  sha256_lf=%s"
              % (v["vector_id"], v["steps"], v["temperature"], v["stdout_sha256_lf"][:16]))

    root = os.path.realpath(args.rundir)
    texts, exes = [], []
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d != "__pycache__"]
        for f in sorted(fn):
            fp = os.path.join(dp, f)
            rel = os.path.relpath(fp, root).replace("\\", "/")
            if rel.endswith(".werk"):
                continue
            if f.lower().endswith(".exe"):
                exes.append(rel)
                continue
            if os.path.getsize(fp) > 64 << 20:
                continue
            try:
                texts.append((rel, open(fp, "rb").read()))
            except Exception:
                pass
    blob = lf(b"\n".join(b for _, b in texts))
    print("\nscanned %d text artifacts (%d B), %d executables: %s"
          % (len(texts), len(blob), len(exes), exes or "none"))

    # ---- grade A: is the vector's exact text present in what the run produced?
    A = {}
    for v in vectors:
        with zipfile.ZipFile(args.fixture) as z:
            want = lf(z.read("testvectors/" + v["stdout_file"]))
        A[v["vector_id"]] = {
            "text_present": want.strip() in blob,
            "sha_lf_quoted": v["stdout_sha256_lf"] in blob.decode("utf-8", "replace"),
            "want_sha256_lf": v["stdout_sha256_lf"],
            "want_bytes_lf": len(want),
        }

    # ---- grade B: the grader runs the binary the run built
    B = {}
    if exes and not args.no_exec:
        # Use a separate directory for each vector. Keep the original run read-only.
        for v in vectors:
            with tempfile.TemporaryDirectory(prefix="werk-selfrun-") as scratch:
                exe = os.path.join(scratch, os.path.basename(exes[0]))
                shutil.copy2(os.path.join(root, exes[0]), exe)
                shutil.copy2(args.fixture, os.path.join(scratch, os.path.basename(args.fixture)))
                # Supply runtime data without exposing the stored expected outputs.
                with zipfile.ZipFile(args.fixture) as package:
                    for member in ("model/stories15M.bin", "model/tokenizer.bin"):
                        if member not in v["argv"][1:]:
                            continue
                        destination = os.path.join(scratch, *member.split("/"))
                        os.makedirs(os.path.dirname(destination), exist_ok=True)
                        with open(destination, "wb") as output:
                            output.write(package.read(member))
                result = run_command([exe] + list(v["argv"][1:]), scratch)
                B[v["vector_id"]] = {
                    "exe": exes[0], "exit": result["exit"], "status": result["status"],
                    "error": result["error"], "sha256_lf": result["stdout_sha256_lf"],
                    "bytes_lf": result["stdout_bytes_lf"],
                    "match": result["status"] == "completed" and result["exit"] == 0
                             and result["stdout_sha256_lf"] == v["stdout_sha256_lf"],
                }

    print("\n=== GRADE A -- ECHO CHECK ONLY, NOT EVIDENCE (the expected text is "
          "inside the package and is inlined in this arm's prompt) ===")
    for k, r in A.items():
        print("  %-20s text_present=%-5s sha256_lf_quoted=%s" %
              (k, r["text_present"], r["sha_lf_quoted"]))
    print("\n=== GRADE B -- DECIDES: the GRADER invoked the binary the run built ===")
    if not B:
        print("  (no executable left behind, or --no-exec)")
    for k, r in B.items():
        print("  %-20s %s" % (k, json.dumps(r)))

    nA = sum(1 for r in A.values() if r["text_present"])
    nB = sum(1 for r in B.values() if r.get("match"))
    # GRADE A IS NOT EVIDENCE -- see the module docstring. Only grade B decides:
    # the grader itself invoking a binary the run actually built. Same rule as
    # "an agent's report is evidence about the agent", applied to a grader that
    # was accepting the package's own answer key.
    host_error = any(r.get("status") == "host-error" for r in B.values())
    verdict = "HOST-ERROR" if host_error else ("PASS" if nB == len(vectors) else "FAIL")
    print("\nvectors reproduced: A %d/%d   B %d/%d   ->  %s"
          % (nA, len(vectors), nB, len(vectors), verdict))

    row = {"fixture": args.fixture, "rundir": root, "executables": exes,
           "grade_A": A, "grade_B": B, "A_matched": nA, "B_matched": nB,
           "vectors": len(vectors), "verdict": verdict}
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(row, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
