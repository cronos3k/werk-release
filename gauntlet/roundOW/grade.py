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
is not changed by it. The primary payload of a node is resolved by the
full SPEC section 2.1 rule order (payload_file, single file, role
'payload', the type's payload role, else ambiguous), never files[0].

--require-primary mesh,sound adds a 'TASK' verdict line: PASS only when,
for every named primary slot, some file on disk has the sha256 of that
slot's resolved payload file. Identity of bytes decides it; the output's
name and extension do not. A JSON descriptor saved as .wav therefore
leaves primary.sound missing and the task FAILs, while the matched count
still credits the descriptor as a declared file.

--prog-arg VALUE (repeatable) passes one argument verbatim, with no shell
splitting; use it for Windows paths with backslashes or spaces. It is
appended after --prog-args.

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


# SPEC section 2.1, "Resolution, NORMATIVE, in this order". The writer-side
# helper tools/payload_file.py computes the same answer when it emits the
# field; this is the reader side, kept inline so the grader stays one file.
PAYLOAD_ROLE_BY_TYPE = {
    "core.audio.effect": "best",
    "core.audio.ambience": "best",
    "core.imposter": "atlas",
    "core.recipe": "record",
}
PAYLOAD_EXT_BY_TYPE = {"core.anim.clip": ".wkac"}


def resolve_payload(node_type, version):
    """-> (path or None, rule). The one payload file of a node version by
    SPEC 2.1 rules 1-4, or (None, '5:ambiguous') for rule 5. Never files[0]."""
    files = version.get("files") or []
    paths = [f["path"] for f in files]
    pf = version.get("payload_file")
    if pf and pf in paths:
        return pf, "1:payload_file"
    if len(files) == 1:
        return files[0]["path"], "2:single-file"
    hit = [f for f in files if f.get("role") == "payload"]
    if len(hit) == 1:
        return hit[0]["path"], "3:role=payload"
    role = PAYLOAD_ROLE_BY_TYPE.get(node_type)
    if role:
        hit = [f for f in files if f.get("role") == role]
        if len(hit) == 1:
            return hit[0]["path"], "4:role=" + role
    ext = PAYLOAD_EXT_BY_TYPE.get(node_type)
    if ext:
        hit = [f for f in files if f["path"].endswith(ext) and f.get("role") != "descriptor"]
        if len(hit) == 1:
            return hit[0]["path"], "4:single-" + ext
    return None, "5:ambiguous"


def primary_payloads(man):
    """slot -> {'node', 'path', 'sha256', 'rule'} for every primary.* slot,
    resolved by SPEC 2.1. A slot whose payload is not machine-determinable
    gets path None and rule '5:ambiguous'."""
    nodes = {n.get("node_id"): n for n in man.get("nodes", [])}
    out = {}
    for slot, nid in (man.get("primary") or {}).items():
        n = nodes.get(nid)
        if not n:
            out[slot] = {"node": nid, "path": None, "sha256": None, "rule": "no-such-node"}
            continue
        act = [v for v in n.get("versions", []) if v.get("v") == n.get("active")]
        if not act:
            out[slot] = {"node": nid, "path": None, "sha256": None, "rule": "no-active-version"}
            continue
        path, rule = resolve_payload(n.get("type", ""), act[0])
        sha = None
        for f in act[0].get("files", []):
            if f["path"] == path:
                sha = f.get("sha256")
        out[slot] = {"node": nid, "path": path, "sha256": sha, "rule": rule}
    return out


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
    for slot, pp in primary_payloads(man).items():
        if pp["path"] in info:
            info[pp["path"]]["primary"] = slot
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
    ap.add_argument("--prog-arg", action="append", default=[],
                    help="one argument for the re-run program, verbatim (repeatable)")
    ap.add_argument("--check-role", action="store_true",
                    help="also check that each matched file is the kind of file its name "
                         "asks for (reported separately; the matched count is unchanged)")
    ap.add_argument("--require-primary", default="",
                    help="comma-separated primary slots (e.g. mesh,sound) whose resolved "
                         "payload bytes must be on disk for a TASK PASS")
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
        pargs = (shlex.split(args.prog_args) if args.prog_args is not None else []) + \
            list(args.prog_arg)
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
    on_disk = {}  # sha256 -> first rel path with those bytes (every graded file)
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
            on_disk.setdefault(got, rel)
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
    if args.require_primary:
        want = [w.strip() for w in args.require_primary.split(",") if w.strip()]
        pp = primary_payloads(man)
        ok_all = True
        parts = []
        for slot in want:
            p = pp.get(slot)
            if p is None:
                parts.append("primary.%s=NOT-DECLARED" % slot)
                ok_all = False
            elif p["path"] is None:
                parts.append("primary.%s=AMBIGUOUS(%s)" % (slot, p["rule"]))
                ok_all = False
            elif p["sha256"] in on_disk:
                parts.append("primary.%s=FOUND(%s as %s)" % (slot, p["path"], on_disk[p["sha256"]]))
            else:
                parts.append("primary.%s=MISSING(%s, rule %s)" % (slot, p["path"], p["rule"]))
                ok_all = False
        print("TASK (required primary payloads present by sha256): %s | %s"
              % ("PASS" if ok_all else "FAIL", " ".join(parts)))


if __name__ == "__main__":
    main()
