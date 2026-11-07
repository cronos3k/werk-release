#!/usr/bin/env python3
"""
grade.py -- artifact grading for the open-weights round.

The rule, unchanged from the cross-vendor round: an agent's own report is
evidence about the agent, not about the artifact. Success is decided here, by
hashing the bytes the run left on disk against what MANIFEST.json inside the
pinned fixture declares -- and, separately, by re-running the agent's program
in a clean directory containing only the fixture.

  python grade.py --rundir <dir> --fixture <path to .werk>
  python grade.py --rerun  --rundir <dir> --fixture <path> --prog <script> --out <cleandir>

Standard library only.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def declared(fixture):
    """path -> declared sha256, from the fixture's own MANIFEST.json."""
    out = {}
    with zipfile.ZipFile(fixture) as z:
        man = json.loads(z.read("MANIFEST.json"))
    # A werk manifest has no flat file list: every declared file hangs off
    # nodes[].versions[].files[]. Walking it is the point -- the grader must
    # read the manifest the same way a reader does.
    for n in man.get("nodes", []):
        for v in n.get("versions", []):
            for f in v.get("files", []):
                out[f["path"]] = f.get("sha256")
    return out, man


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rundir", required=True)
    ap.add_argument("--fixture", required=True)
    ap.add_argument("--rerun", action="store_true")
    ap.add_argument("--prog", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    dec, man = declared(args.fixture)
    print("fixture      : %s" % args.fixture)
    print("fixture sha256: %s" % sha256_file(args.fixture))
    print("declared files: %d" % len(dec))

    if args.rerun:
        out = os.path.realpath(args.out)
        if os.path.exists(out):
            shutil.rmtree(out)
        os.makedirs(out)
        shutil.copy2(args.fixture, os.path.join(out, os.path.basename(args.fixture)))
        src = os.path.join(args.rundir, args.prog)
        shutil.copy2(src, os.path.join(out, os.path.basename(args.prog)))
        t0 = time.monotonic()
        p = subprocess.run([sys.executable, os.path.basename(args.prog)], cwd=out,
                           capture_output=True, timeout=1800)
        dt = time.monotonic() - t0
        print("\n=== RE-RUN in clean dir %s ===" % out)
        print("argv: python %s" % os.path.basename(args.prog))
        print("exit: %d  in %.1fs" % (p.returncode, dt))
        so = p.stdout.decode("utf-8", "replace")
        se = p.stderr.decode("utf-8", "replace")
        enc = sys.stdout.encoding or "utf-8"
        sys.stdout.write(so.encode(enc, "replace").decode(enc, "replace"))
        sys.stderr.write(se.encode(enc, "replace").decode(enc, "replace"))
        scan = out
    else:
        scan = args.rundir

    print("\n=== ARTIFACT HASHES (graded here, not self-reported) ===")
    base = {os.path.basename(k): (k, v) for k, v in dec.items()}
    n_ok = n_bad = n_unknown = 0
    for root, dirs, files in os.walk(scan):
        dirs[:] = [d for d in dirs if d != "_harness"]
        for name in sorted(files):
            fp = os.path.join(root, name)
            rel = os.path.relpath(fp, scan).replace("\\", "/")
            if rel.endswith(".werk"):
                continue
            if os.path.getsize(fp) == 0:
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext not in (".glb", ".wav", ".png", ".ply", ".gltf", ".bin", ".jpg"):
                continue
            got = sha256_file(fp)
            key = None
            if rel in dec:
                key = rel
            elif name in base:
                key = base[name][0]
            else:
                # An agent may name its output whatever it likes. What is being
                # graded is the BYTES, so a digest that equals a declared digest
                # is a match no matter what the file is called.
                for k, v in dec.items():
                    if v == got:
                        key = k
                        break
            if key is None:
                print("  ?  %-52s %s  (no declared match by name)" % (rel, got[:16]))
                n_unknown += 1
            elif dec[key] == got:
                print("  OK %-52s %s == declared %s  [%s]" % (rel, got[:16], dec[key][:16], key))
                n_ok += 1
            else:
                print("  XX %-52s %s != declared %s  [%s]" % (rel, got[:16], dec[key][:16], key))
                n_bad += 1
    print("\nmatched=%d mismatched=%d unmatched=%d" % (n_ok, n_bad, n_unknown))


if __name__ == "__main__":
    main()
