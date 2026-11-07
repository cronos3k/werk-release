#!/usr/bin/env python3
"""run_gate_cc0_public.py — the PUBLIC-DOMAIN crate gate, MEASURED.

Modelled on tests/run_gate_a.py, but for the two CC0 fixtures and their damaged
siblings — the ones anyone can rebuild from this repository alone, with no
private splat-foley assets, no Blender and no network:

    fixtures/crate-cc0-lean-v1.werk        fixtures/crate-cc0-lean-v1-damaged.werk
    fixtures/crate-cc0-full-v1.werk        fixtures/crate-cc0-full-v1-damaged.werk

For each CLEAN fixture: it opens with the Python binding (0 errors, signature
'signed-and-valid', the EXACT node/alive/skipped counts it was built with, 0
dead), round-trips it byte-for-byte, runs the bootstrap reader
loaders/werk_read.py --verify --strict and requires exit 0, extracts the mesh
blob and checks its glTF magic, and resolves primary.mesh to geometry/game.glb.

For each DAMAGED fixture: it asserts the EXACT dead and skipped node lists it was
designed to produce, the exact report codes on the exact nodes, that the
signature is STILL 'signed-and-valid' (corrupting a payload must NOT invalidate
the chain — this is the key property), and that the bootstrap reader also SEES
the damage (non-zero exit, the corrupt file named).

    python tests/run_gate_cc0_public.py [--rebuild]

Exit 0 only when nothing FAILED and nothing was SKIPPED (a SKIP here would mean
the pure-Python reader/verify path did not run, which is itself a failure).
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
BUILDER = os.path.join(FIX, "build_crate_cc0.py")

sys.path.insert(0, os.path.join(ROOT, "tools"))
from payload_file import payload_file_for, check_payload_files      # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fixture_pin import pin as _pin_fixture                           # noqa: E402

RESULTS = []

# The exact shape each fixture was built with. If build_crate_cc0.py changes a
# node set, these numbers change with it — that coupling is the point of a gate.
SPEC = {
    "lean": {
        "clean": "crate-cc0-lean-v1.werk",
        "damaged": "crate-cc0-lean-v1-damaged.werk",
        "nodes": 13, "alive": 13, "skipped": [],
        "dnodes": 14, "dalive": 12,
        "dead": ["disclosure-cc0"],
        "dskipped": ["mystery"],
        "hash_mismatch": ["disclosure-cc0"],
        "corrupt_file": "disclosure/disclosure.json",
    },
    "full": {
        "clean": "crate-cc0-full-v1.werk",
        "damaged": "crate-cc0-full-v1-damaged.werk",
        "nodes": 18, "alive": 16,
        "skipped": ["evidence-view-1", "evidence-view-2"],
        "dnodes": 19, "dalive": 15,
        "dead": ["audio-cc0-click"],
        "dskipped": ["evidence-view-1", "evidence-view-2", "mystery"],
        "hash_mismatch": ["audio-cc0-click"],
        "corrupt_file": "audio/sfx/crate-cc0-click.wav",
    },
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


def primary_mesh_path(werk_path):
    with zipfile.ZipFile(werk_path) as z:
        man = json.loads(z.read("MANIFEST.json"))
    by_id = {n["node_id"]: n for n in man["nodes"]}
    node = by_id.get((man.get("primary") or {}).get("mesh"))
    if node is None:
        return None, man
    ver = [v for v in node["versions"] if v["v"] == node["active"]][0]
    return (ver.get("payload_file") or payload_file_for(node["type"], ver["files"])), man


def gate_clean(werk, spec, variant):
    import werk as werkpy
    path = os.path.join(FIX, werk)

    with werkpy.Package.open(path) as p:
        nodes = p.nodes
        alive = [n for n in nodes if n.status == "alive"]
        dead = [n for n in nodes if n.status == "dead"]
        skipped = sorted(n.node_id for n in nodes if n.status == "skipped")
        ok = (p.errors == 0 and p.signature_state == "signed-and-valid"
              and len(nodes) == spec["nodes"] and len(alive) == spec["alive"]
              and not dead and skipped == spec["skipped"])
        record("%s clean: binding load" % variant, "PASS" if ok else "FAIL",
               "%d nodes (%d alive, %d skipped, %d dead), sig %s, %d error(s)"
               % (len(nodes), len(alive), len(skipped), len(dead),
                  p.signature_state, p.errors)
               + ("" if ok else " EXPECTED %d/%d/skip=%s"
                  % (spec["nodes"], spec["alive"], spec["skipped"])))

    with werkpy.Package.open(path) as p:
        out_zip = os.path.join(WORK, werk.replace(".werk", "-rt.werk"))
        t0 = time.time()
        p.write_zip(out_zip)
        secs = time.time() - t0
        same = sha256_file(out_zip) == sha256_file(path)
        record("%s clean: round-trip byte identity" % variant,
               "PASS" if same else "FAIL",
               "%s (%.2f s)" % ("sha256 identical" if same else "DIFFERS", secs))

    rc, out = run([sys.executable, os.path.join(ROOT, "loaders", "werk_read.py"),
                   path, "--verify", "--strict"])
    line = [l for l in out.splitlines() if "verified over" in l]
    record("%s clean: werk_read.py --verify --strict" % variant,
           "PASS" if rc == 0 else "FAIL",
           (line[-1].strip() if line else out.strip()[-160:]))

    with werkpy.Package.open(path) as p:
        mesh = p.blob("geometry/game.glb")
        ok = mesh[:4] == b"glTF"
        record("%s clean: extract mesh blob (glTF magic)" % variant,
               "PASS" if ok else "FAIL",
               "game.glb %d bytes, magic %r" % (len(mesh), mesh[:4]))

    pm, man = primary_mesh_path(path)
    problems = []
    if pm != "geometry/game.glb":
        problems.append("primary.mesh -> %r" % pm)
    problems += check_payload_files(man)
    record("%s clean: primary.mesh resolves to game.glb" % variant,
           "PASS" if not problems else "FAIL",
           "primary.mesh -> geometry/game.glb" if not problems
           else "; ".join(problems))


def gate_damaged(werk, spec, variant):
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
        # THE key property: corrupting a PAYLOAD must NOT invalidate the SIGNATURE.
        if p.signature_state != "signed-and-valid":
            problems.append("signature is %s; a corrupt payload must NOT "
                            "invalidate the chain" % p.signature_state)
        record("%s damaged: exact dead/skip report" % variant,
               "PASS" if not problems else "FAIL",
               ("dead=%s, skipped=%s, %d alive, signature still %s"
                % (dead, skipped, len(alive), p.signature_state))
               if not problems else "; ".join(problems))

    # The bootstrap reader must also SEE the damage: non-zero exit, corrupt file
    # named, and the rest still parsed.
    rc, out = run([sys.executable, os.path.join(ROOT, "loaders", "werk_read.py"),
                   path, "--verify", "--strict"])
    saw = spec["corrupt_file"] in out and rc != 0
    record("%s damaged: werk_read.py reports the corruption" % variant,
           "PASS" if saw else "FAIL",
           "exit %d, names %s" % (rc, spec["corrupt_file"]) if saw
           else "exit %d, corrupt file %s in output: %s"
           % (rc, spec["corrupt_file"], spec["corrupt_file"] in out))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true")
    args = ap.parse_args(argv)

    os.makedirs(WORK, exist_ok=True)
    print("werk public-domain crate gate — the CC0 samples")
    print("repo   : %s" % ROOT)

    for variant in ("lean", "full"):
        spec = SPEC[variant]
        need = (args.rebuild
                or not os.path.isfile(os.path.join(FIX, spec["clean"]))
                or not os.path.isfile(os.path.join(FIX, spec["damaged"])))
        if need:
            rc, out = run([sys.executable, BUILDER, "--variant", variant])
            record("build: %s" % variant, "PASS" if rc == 0 else "FAIL",
                   out.strip().splitlines()[-1] if out.strip() else "")
            if rc != 0:
                return 1

    for label, path in [(v + " " + k, os.path.join(FIX, SPEC[v][k]))
                        for v in ("lean", "full") for k in ("clean", "damaged")]:
        print("%-14s: %d bytes, sha256 %s"
              % (label, os.path.getsize(path), sha256_file(path)))
    print()

    # Pin BEFORE measuring (the S8 lesson, tests/fixture_pin.py). These CC0
    # fixtures were the only shipped fixtures recorded nowhere but in a
    # hand-typed table, so a rebuild silently changed what this gate measured
    # (finding F-AC-5, 2026-10-13). They are in fixtures/fixtures.json now.
    for key in ("crate-cc0-lean-v1", "crate-cc0-lean-v1-damaged",
                "crate-cc0-full-v1", "crate-cc0-full-v1-damaged"):
        r = _pin_fixture(key)
        record("fixture pinned: %s" % key, "PASS" if r.ok else "FAIL", r.detail)

    sys.path.insert(0, os.path.join(ROOT, "bindings", "python"))
    try:
        import werk  # noqa: F401
    except Exception as e:  # noqa: BLE001
        record("python binding import", "FAIL", repr(e))
        return 1

    for variant in ("lean", "full"):
        spec = SPEC[variant]
        gate_clean(spec["clean"], spec, variant)
        gate_damaged(spec["damaged"], spec, variant)

    print()
    npass = sum(1 for _, s, _ in RESULTS if s == "PASS")
    nfail = sum(1 for _, s, _ in RESULTS if s == "FAIL")
    nskip = sum(1 for _, s, _ in RESULTS if s == "SKIP")
    print("%d PASS, %d FAIL, %d SKIP" % (npass, nfail, nskip))
    print("GATE CC0-PUBLIC: %s"
          % ("PASSED" if nfail == 0 and nskip == 0 else
             "INCOMPLETE (%d SKIPPED; a skip is not a pass)" % nskip
             if nfail == 0 else "FAILED"))
    return 1 if (nfail or nskip) else 0


if __name__ == "__main__":
    sys.exit(main())
