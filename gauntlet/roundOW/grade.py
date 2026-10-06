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
                   [--prog-args "mini-v1.werk out"]

--prog-args is split like a POSIX shell line (shlex) and passed to the
program after its name. Paths in it are relative to the clean dir, which
holds the fixture under its own basename. Without --prog-args the program
runs with no arguments, as before. Write --prog-args="..." when the
string starts with a dash.

--check-role adds a role column to each matched file and a 'role check:'
line after the counts: does the matched file's declared kind (media_type,
role, extension) fit the kind the run's file name asks for, and were the
manifest's primary payloads found with the right kind. The matched count
is not changed by it.

Standard library only.
"""

import argparse
import hashlib
import json
import os
import shlex
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


# ---------------------------------------------------------------- role check
# Optional (--check-role). The hash match above says the bytes equal SOME
# declared file. It does not say the file is the kind the task asked for: a
# JSON descriptor saved as a .wav matches by digest and counts as a match.
# The role check compares the class the run's file name asks for (by its
# extension) with the class the manifest declares for the matched file. It is
# reported in its own column and line; the matched count is not changed.

EXT_CLASS = {".glb": "mesh", ".gltf": "mesh", ".ply": "mesh", ".obj": "mesh",
             ".wav": "sound", ".ogg": "sound", ".flac": "sound", ".mp3": "sound",
             ".png": "image", ".jpg": "image", ".jpeg": "image",
             ".json": "data", ".txt": "data", ".md": "data"}


def media_class(media_type):
    mt = (media_type or "").lower()
    if mt.startswith("audio/"):
        return "sound"
    if mt.startswith("model/"):
        return "mesh"
    if mt.startswith("image/"):
        return "image"
    if mt.startswith("text/") or mt.endswith("json"):
        return "data"
    return None


def declared_roles(man):
    """path -> what the manifest says the file is: its class (from
    media_type, else from its extension; a 'descriptor' role is data),
    role, node, and which primary payload it is, if any."""
    info = {}
    for n in man.get("nodes", []):
        for v in n.get("versions", []):
            for f in v.get("files", []):
                cls = media_class(f.get("media_type")) or \
                    EXT_CLASS.get(os.path.splitext(f["path"])[1].lower())
                if f.get("role") == "descriptor":
                    cls = "data"
                info[f["path"]] = {"class": cls, "role": f.get("role"),
                                   "media_type": f.get("media_type"),
                                   "node": n.get("node_id"), "primary": None}
    nodes = {n.get("node_id"): n for n in man.get("nodes", [])}
    for slot, nid in (man.get("primary") or {}).items():
        n = nodes.get(nid)
        if not n:
            continue
        act = [v for v in n.get("versions", []) if v.get("v") == n.get("active")]
        if not act:
            continue
        files = act[0].get("files", [])
        path = act[0].get("payload_file") or (files[0]["path"] if len(files) == 1 else None)
        if path in info:
            info[path]["primary"] = slot
    return info


def role_verdict(name, key, roles):
    """('ok' | 'WRONG' | 'n/a', text) for one matched file."""
    want = EXT_CLASS.get(os.path.splitext(name)[1].lower())
    d = roles.get(key, {})
    have = d.get("class")
    desc = "declared %s" % (have or "unknown")
    if d.get("media_type"):
        desc += ", %s" % d["media_type"]
    if d.get("role"):
        desc += ", role=%s" % d["role"]
    if d.get("primary"):
        desc += ", primary.%s payload" % d["primary"]
    if want is None or have is None:
        return "n/a", "role n/a (%s)" % desc
    if want == have:
        return "ok", "role ok (%s)" % desc
    return "WRONG", "role WRONG: file asks for %s, %s" % (want, desc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rundir", required=True)
    ap.add_argument("--fixture", required=True)
    ap.add_argument("--rerun", action="store_true")
    ap.add_argument("--prog", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--prog-args", default=None,
                    help="arguments for the re-run program, one shell-style string")
    ap.add_argument("--check-role", action="store_true",
                    help="also check that each matched file is the kind of file its name "
                         "asks for (reported separately; the matched count is unchanged)")
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
        pargs = shlex.split(args.prog_args) if args.prog_args is not None else []
        p = subprocess.run([sys.executable, os.path.basename(args.prog)] + pargs, cwd=out,
                           capture_output=True, timeout=1800)
        dt = time.monotonic() - t0
        print("\n=== RE-RUN in clean dir %s ===" % out)
        print("argv: python %s" % " ".join([os.path.basename(args.prog)] +
                                           [shlex.quote(a) for a in pargs]))
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
    roles = declared_roles(man) if args.check_role else None
    role_n = {"ok": 0, "WRONG": 0, "n/a": 0}
    primary_ok = set()
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
                line = "  OK %-52s %s == declared %s  [%s]" % (rel, got[:16], dec[key][:16], key)
                if roles is not None:
                    rv, rtext = role_verdict(name, key, roles)
                    role_n[rv] += 1
                    if rv == "ok" and roles.get(key, {}).get("primary"):
                        primary_ok.add(roles[key]["primary"])
                    line += "  %s" % rtext
                print(line)
                n_ok += 1
            else:
                print("  XX %-52s %s != declared %s  [%s]" % (rel, got[:16], dec[key][:16], key))
                n_bad += 1
    print("\nmatched=%d mismatched=%d unmatched=%d" % (n_ok, n_bad, n_unknown))
    if roles is not None:
        slots = sorted((man.get("primary") or {}).keys())
        print("role check: matched_role_ok=%d matched_role_wrong=%d matched_role_na=%d | %s"
              % (role_n["ok"], role_n["WRONG"], role_n["n/a"],
                 " ".join("primary.%s=%s" % (s, "found" if s in primary_ok else "missing")
                          for s in slots)))


if __name__ == "__main__":
    main()
