#!/usr/bin/env python3
"""run_gate_cc0_image.py — the PUBLIC-DOMAIN image gate, MEASURED.

Modelled on tests/run_gate_cc0_public.py, but for the CC0 image fixture and its
damaged sibling — the ones anyone can rebuild from this repository alone, with
no private tree, no database and no network:

    fixtures/image-cc0-v1.werk        fixtures/image-cc0-v1-damaged.werk

For the CLEAN fixture: it opens with the Python binding (0 errors, signature
'signed-and-valid', the EXACT node/alive/skipped counts it was built with, 0
dead), round-trips it byte-for-byte, runs loaders/werk_read.py --verify --strict
and requires exit 0, extracts the source image blob and checks its JPEG magic,
extracts the WKEM descriptor and checks its magic, and resolves primary.image to
image/source.jpg and primary.thumbnail to image/thumb-256.png.

For the DAMAGED fixture: it asserts the EXACT dead and skipped node lists, the
exact report codes on the exact nodes, that the signature is STILL
'signed-and-valid' (corrupting a payload must NOT invalidate the chain — the key
property), and that the bootstrap reader also SEES the damage.

    python tests/run_gate_cc0_image.py [--rebuild]

Exit 0 only when nothing FAILED and nothing was SKIPPED.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, "fixtures")
WORK = os.path.join(ROOT, "core", "target", "gate-cc0")
BUILDER = os.path.join(FIX, "build_image_cc0.py")

sys.path.insert(0, os.path.join(ROOT, "tools"))
from payload_file import payload_file_for, check_payload_files      # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fixture_pin import pin as _pin_fixture                           # noqa: E402

RESULTS = []

# The exact shape the fixture was built with. If build_image_cc0.py changes a
# node set, these numbers change with it — that coupling is the point of a gate.
SPEC = {
    "clean": "image-cc0-v1.werk",
    "damaged": "image-cc0-v1-damaged.werk",
    "nodes": 11, "alive": 11, "skipped": [],
    "dnodes": 12, "dalive": 10,
    "dead": ["disclosure"],
    "dskipped": ["mystery"],
    "hash_mismatch": ["disclosure"],
    "corrupt_file": "disclosure/disclosure.json",
    "primary_image": "image/source.jpg",
    "primary_thumb": "image/thumb-256.png",
}


def record(name, status, detail=""):
    RESULTS.append((name, status, detail))
    print("[%s] %-46s %s" % (status, name, detail))


def run(cmd, cwd=None):
    p = subprocess.run(cmd, cwd=cwd or ROOT, capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def sha256_file(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def primary_payloads(werk_path):
    with zipfile.ZipFile(werk_path) as z:
        man = json.loads(z.read("MANIFEST.json"))
    by_id = {n["node_id"]: n for n in man["nodes"]}

    def resolve(slot):
        node = by_id.get((man.get("primary") or {}).get(slot))
        if node is None:
            return None
        ver = [v for v in node["versions"] if v["v"] == node["active"]][0]
        return ver.get("payload_file") or payload_file_for(node["type"], ver["files"])

    return resolve("image"), resolve("thumbnail"), man


def gate_clean(werk, spec):
    import werk as werkpy
    path = os.path.join(FIX, werk)

    with werkpy.Package.open(path) as p:
        nodes = p.nodes
        alive = [n for n in nodes if n.status == "alive"]
        dead = [n for n in nodes if n.status == "dead"]
        skipped = sorted(n.node_id for n in nodes if n.status == "skipped")
        ok = (p.errors == 0 and p.signature_state == "signed-and-valid"
              and len(nodes) == spec["nodes"] and len(alive) == spec["alive"]
              and not dead and skipped == spec["skipped"]
              and p.profile == "image/1")
        record("image clean: binding load", "PASS" if ok else "FAIL",
               "%d nodes (%d alive, %d skipped, %d dead), profile %s, sig %s, "
               "%d error(s)" % (len(nodes), len(alive), len(skipped), len(dead),
                                p.profile, p.signature_state, p.errors)
               + ("" if ok else " EXPECTED %d/%d/skip=%s"
                  % (spec["nodes"], spec["alive"], spec["skipped"])))

    with werkpy.Package.open(path) as p:
        out_zip = os.path.join(WORK, werk.replace(".werk", "-rt.werk"))
        t0 = time.time()
        p.write_zip(out_zip)
        secs = time.time() - t0
        same = sha256_file(out_zip) == sha256_file(path)
        record("image clean: round-trip byte identity",
               "PASS" if same else "FAIL",
               "%s (%.2f s)" % ("sha256 identical" if same else "DIFFERS", secs))

    rc, out = run([sys.executable, os.path.join(ROOT, "loaders", "werk_read.py"),
                   path, "--verify", "--strict"])
    line = [l for l in out.splitlines() if "verified over" in l]
    record("image clean: werk_read.py --verify --strict",
           "PASS" if rc == 0 else "FAIL",
           (line[-1].strip() if line else out.strip()[-160:]))

    with werkpy.Package.open(path) as p:
        img = p.blob("image/source.jpg")
        ok = img[:2] == b"\xff\xd8"
        record("image clean: extract source blob (JPEG magic)",
               "PASS" if ok else "FAIL",
               "source.jpg %d bytes, magic %r" % (len(img), img[:2]))

    with werkpy.Package.open(path) as p:
        wkem = p.blob("semantics/style-embedding.wkem")
        ok = wkem[:4] == b"WKEM"
        record("image clean: extract descriptor blob (WKEM magic)",
               "PASS" if ok else "FAIL",
               "style-embedding.wkem %d bytes, magic %r" % (len(wkem), wkem[:4]))

    pi, pt, man = primary_payloads(path)
    problems = []
    if pi != spec["primary_image"]:
        problems.append("primary.image -> %r" % pi)
    if pt != spec["primary_thumb"]:
        problems.append("primary.thumbnail -> %r" % pt)
    problems += check_payload_files(man)
    record("image clean: primary.image / thumbnail resolve",
           "PASS" if not problems else "FAIL",
           "primary.image -> %s, primary.thumbnail -> %s"
           % (spec["primary_image"], spec["primary_thumb"])
           if not problems else "; ".join(problems))


def gate_damaged(werk, spec):
    import werk as werkpy
    path = os.path.join(FIX, werk)

    with werkpy.Package.open(path) as p:
        codes = {}
        for e in p.report:
            codes.setdefault(e.code, []).append(e.node_id or "")
        dead = sorted(n.node_id for n in p.nodes if n.status == "dead")
        skipped = sorted(n.node_id for n in p.nodes if n.status == "skipped")
        alive = [n for n in p.nodes if n.status == "alive"]
        problems = []
        if dead != sorted(spec["dead"]):
            problems.append("dead=%s expected %s" % (dead, sorted(spec["dead"])))
        if skipped != sorted(spec["dskipped"]):
            problems.append("skipped=%s expected %s"
                            % (skipped, sorted(spec["dskipped"])))
        if sorted(codes.get("hash-mismatch", [])) != sorted(spec["hash_mismatch"]):
            problems.append("hash-mismatch=%s expected %s"
                            % (codes.get("hash-mismatch"), spec["hash_mismatch"]))
        if sorted(codes.get("node-skipped-unknown-type", [])) != sorted(spec["dskipped"]):
            problems.append("unknown-type=%s expected %s"
                            % (codes.get("node-skipped-unknown-type"),
                               spec["dskipped"]))
        if len(p.nodes) != spec["dnodes"]:
            problems.append("%d nodes, expected %d" % (len(p.nodes), spec["dnodes"]))
        if len(alive) != spec["dalive"]:
            problems.append("%d alive, expected %d" % (len(alive), spec["dalive"]))
        if p.signature_state != "signed-and-valid":
            problems.append("signature is %s; a corrupt payload must NOT "
                            "invalidate the chain" % p.signature_state)
        record("image damaged: exact dead/skip report",
               "PASS" if not problems else "FAIL",
               ("dead=%s, skipped=%s, %d alive, signature still %s"
                % (dead, skipped, len(alive), p.signature_state))
               if not problems else "; ".join(problems))

    rc, out = run([sys.executable, os.path.join(ROOT, "loaders", "werk_read.py"),
                   path, "--verify", "--strict"])
    saw = spec["corrupt_file"] in out and rc != 0
    record("image damaged: werk_read.py reports the corruption",
           "PASS" if saw else "FAIL",
           "exit %d, names %s" % (rc, spec["corrupt_file"]) if saw
           else "exit %d, corrupt file in output: %s"
           % (rc, spec["corrupt_file"] in out))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true")
    args = ap.parse_args(argv)

    os.makedirs(WORK, exist_ok=True)
    print("werk public-domain image gate — the CC0 sample")
    print("repo   : %s" % ROOT)

    need = (args.rebuild
            or not os.path.isfile(os.path.join(FIX, SPEC["clean"]))
            or not os.path.isfile(os.path.join(FIX, SPEC["damaged"])))
    if need:
        rc, out = run([sys.executable, BUILDER])
        record("build: image", "PASS" if rc == 0 else "FAIL",
               out.strip().splitlines()[-1] if out.strip() else "")
        if rc != 0:
            return 1

    for label, key in [("image clean", "clean"), ("image damaged", "damaged")]:
        path = os.path.join(FIX, SPEC[key])
        print("%-14s: %d bytes, sha256 %s"
              % (label, os.path.getsize(path), sha256_file(path)))
    print()

    # Pin BEFORE measuring (the S8 lesson, tests/fixture_pin.py). These CC0
    # fixtures were the only shipped fixtures recorded nowhere but in a
    # hand-typed table, so a rebuild silently changed what this gate measured
    # (finding F-AC-5, 2026-10-13). They are in fixtures/fixtures.json now.
    for key in ("image-cc0-v1", "image-cc0-v1-damaged"):
        r = _pin_fixture(key)
        record("fixture pinned: %s" % key, "PASS" if r.ok else "FAIL", r.detail)

    sys.path.insert(0, os.path.join(ROOT, "bindings", "python"))
    try:
        import werk  # noqa: F401
    except Exception as e:  # noqa: BLE001
        record("python binding import", "FAIL", repr(e))
        return 1

    gate_clean(SPEC["clean"], SPEC)
    gate_damaged(SPEC["damaged"], SPEC)

    # -- builder is deterministic (the public counterpart to Gate 9 clause 3:
    # rebuild from the in-repo CC0 source and require byte-identity) ----------
    #
    # Built into the gate's own scratch directory, NOT into fixtures/. This
    # clause used to run the builder with its default output directory, which
    # is fixtures/ -- so every run of this gate OVERWROTE the two shipped
    # fixtures with a fresh build, and after any spec change the gate had
    # replaced the files it was about to be asked about (finding F-AC-5). The
    # rebuild is now compared with the shipped, pinned bytes, which is the
    # claim "the builder reproduces the fixture" rather than the weaker "two
    # runs of the builder agree with each other".
    rc, out = run([sys.executable, BUILDER, "--check-determinism", "--out", WORK])
    ok = rc == 0 and "determinism: PASS" in out
    same = []
    for key in ("clean", "damaged"):
        fresh = os.path.join(WORK, SPEC[key])
        same.append(os.path.isfile(fresh)
                    and sha256_file(fresh) == sha256_file(os.path.join(FIX, SPEC[key])))
    record("image: builder is deterministic (rebuild identical)",
           "PASS" if ok and all(same) else "FAIL",
           "two builds byte-identical, and identical to the shipped pinned fixtures"
           if ok and all(same) else
           ("two builds agree but DIFFER from the shipped fixtures: the fixtures "
            "predate the spec they would be rebuilt with" if ok else
            (out.strip()[-160:] or "no output")))

    print()
    npass = sum(1 for _, s, _ in RESULTS if s == "PASS")
    nfail = sum(1 for _, s, _ in RESULTS if s == "FAIL")
    nskip = sum(1 for _, s, _ in RESULTS if s == "SKIP")
    print("%d PASS, %d FAIL, %d SKIP" % (npass, nfail, nskip))
    print("GATE CC0-IMAGE: %s"
          % ("PASSED" if nfail == 0 and nskip == 0 else
             "INCOMPLETE (%d SKIPPED; a skip is not a pass)" % nskip
             if nfail == 0 else "FAILED"))
    return 1 if (nfail or nskip) else 0


if __name__ == "__main__":
    sys.exit(main())
