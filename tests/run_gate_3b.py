#!/usr/bin/env python3
"""run_gate_3b.py — Stage 3 Part B gate, MEASURED.

The gate, quoted from ROADMAP.md Stage 3: "bare GLB in -> conformant
fully-enriched .werk out, unattended; every derived node carries input_hash +
epistemic stamps."

So this harness does exactly that and checks exactly that, on more than one
real GLB, and prints what it saw rather than asserting what it hoped:

  1. run pipeline/enrich.py unattended on each input, no human in the loop
  2. verify the result with werk-core through bindings/python/werk.py
     -> 0 errors, 0 dead nodes
  3. verify it standalone with loaders/werk_read.py -> every file, every node
  4. validate MANIFEST.json and every JSON payload against the schemas the
     package itself carries (never the repo's copy: the package is the
     authority for its own contents)
  5. check the law-5 property directly: EVERY node version whose epistemic is
     measured or inferred has input_files, input_params and an input_hash, and
     that hash is RECOMPUTED from the package's own bytes and compared
  6. re-read the binary envelopes (WKRP, WKFF, WKEM) through the bootstrap
     reader's own envelope parser, so the layout grammars are exercised

    python tests/run_gate_3b.py [--keep] [--inputs A.glb B.glb ...]

Exit 0 only when nothing FAILED.
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
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "bindings", "python"))

# Author-lab inputs: WERK_LAB names the directory holding the sibling
# splat-foley project. Unset, the inputs are absent and the gate says so.
LAB = os.environ.get("WERK_LAB", "<WERK_LAB unset>")
DEFAULT_INPUTS = [
    (os.path.join(LAB, "splat-foley", "outputs", "wooden-crate-01", "model.glb"), "Wooden crate 01"),
    (os.path.join(LAB, "splat-foley", "outputs", "lantern", "model.glb"), "Lantern"),
    # The third input is deliberately the awkward one: 408 triangles, vertex
    # colours, NO images and NO material block. The texture cook has nothing to
    # do and fails; the package must come out anyway, one node short, with the
    # failure named. That is the island rule under test rather than described.
    (os.path.join(LAB, "splat-foley", "outputs", "example", "model.glb"), "Example crate"),
]
DETERMINISM_INPUT = 2       # index into the input list, chosen because it is fast

RESULTS = []


def record(name, status, detail=""):
    RESULTS.append((name, status, detail))
    print("[%-4s] %-44s %s" % (status, name, detail))


def canon(v):
    # ensure_ascii=False is NOT cosmetic. MINI-SPECS section 3 rule 3 writes a
    # character outside ASCII as its UTF-8 bytes; json.dumps escapes it to
    # \uXXXX unless told not to, which is valid JSON, parses to the same
    # value, and hashes to something else than werk-core computes. This
    # function had the default for as long as it existed, and nothing caught it
    # because no input_params anywhere held a non-ASCII character AND the gate
    # that recomputes input_hash carried the same line (finding F-AC-2,
    # 2026-10-13; tests/run_gate_reference.py now holds the spec's vector).
    # sort_keys orders by code point, which is the UTF-8 byte order the rule
    # asks for; allow_nan=False because a werk number is always finite.
    return json.dumps(v, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def check_package(path, tag):
    blob = open(path, "rb").read()
    zf = zipfile.ZipFile(path)
    files = {n: zf.read(n) for n in zf.namelist()}
    manifest = json.loads(files["MANIFEST.json"])

    # ---- 2. werk-core --------------------------------------------------
    import werk
    pkg = werk.Package.open(path)
    errors = [e for e in pkg.report if e.severity == "error"]
    dead = [n for n in pkg.nodes if n.status == "dead"]
    record("%s: werk-core loads" % tag,
           "PASS" if not errors and not dead else "FAIL",
           "%d nodes, %d live, %d dead, %d error(s), signature %s"
           % (len(pkg.nodes), sum(1 for n in pkg.nodes if n.status == "alive"),
              len(dead), len(errors), pkg.signature_state))
    for e in errors[:8]:
        print("        %s: %s" % (e.code, e.message))

    # ---- 3. bootstrap reader -------------------------------------------
    p = subprocess.run([sys.executable, os.path.join(ROOT, "loaders", "werk_read.py"),
                        path, "--verify", "--strict"], capture_output=True, text=True)
    out = (p.stdout or "") + (p.stderr or "")
    verified = [l for l in out.splitlines() if "files verified over" in l]
    ok = p.returncode == 0 and "FAIL " not in out and bool(verified)
    if ok:
        head = verified[0].split()[0]          # "<ok>/<total>"
        ok = "/" in head and head.split("/")[0] == head.split("/")[1]
    record("%s: werk_read.py standalone" % tag, "PASS" if ok else "FAIL",
           verified[0] if verified else out.strip().splitlines()[-1:] or "no output")

    # ---- 4. schemas, from the package's own spec/ ------------------------
    import jsonschema
    schema_dir_files = {k: v for k, v in files.items() if k.startswith("spec/schemas/")}
    store = {}
    for k, v in schema_dir_files.items():
        s = json.loads(v)
        store[s.get("$id", k)] = s
        store[k] = s

    def validate(doc, schema_path, label):
        # Every schema in spec/ resolves only "#/$defs/..." refs inside itself
        # (checked: there is no cross-file $ref anywhere in spec/schemas), so
        # the plain validator needs no resolver and no registry.
        s = store.get(schema_path)
        if s is None:
            return "no schema %s in the package" % schema_path
        v = jsonschema.Draft202012Validator(s)
        errs = sorted(v.iter_errors(doc), key=lambda e: list(e.path))
        if errs:
            return "%s: %s at /%s" % (label, errs[0].message,
                                      "/".join(str(x) for x in errs[0].path))
        return None

    problems = []
    m = validate(manifest, manifest.get("manifest_schema",
                                        "spec/schemas/manifest.schema.json"),
                 "MANIFEST.json")
    if m:
        problems.append(m)
    checked = 0
    for node in manifest["nodes"]:
        sp = manifest["schemas"].get(node["type"])
        if not sp:
            continue
        for ver in node["versions"]:
            for f in ver["files"]:
                if not f["path"].endswith(".json"):
                    continue
                e = validate(json.loads(files[f["path"]]), sp, f["path"])
                checked += 1
                if e:
                    problems.append(e)
    record("%s: JSON Schema validation" % tag, "PASS" if not problems else "FAIL",
           "manifest + %d payload documents against the package's own spec/, "
           "%d problem(s)" % (checked, len(problems)))
    for pr in problems[:6]:
        print("        %s" % pr)

    # ---- 5. law 5: input_hash + epistemic on every derived node ---------
    missing, wrong, stamped = [], [], 0
    for node in manifest["nodes"]:
        for ver in node["versions"]:
            ep = ver.get("epistemic")
            if ep is None:
                missing.append("%s v%d has no epistemic stamp" % (node["node_id"], ver["v"]))
                continue
            stamped += 1
            if ep not in ("measured", "inferred"):
                continue
            if "input_files" not in ver or "input_hash" not in ver:
                missing.append("%s v%d is '%s' with no input_hash"
                               % (node["node_id"], ver["v"], ep))
                continue
            h = hashlib.sha256()
            for ip in ver["input_files"]:
                if ip not in files:
                    missing.append("%s v%d names input %s which is not in the "
                                   "package" % (node["node_id"], ver["v"], ip))
                    break
                h.update(hashlib.sha256(files[ip]).digest())
            else:
                h.update(canon(ver.get("input_params", {})))
                if h.hexdigest() != ver["input_hash"]:
                    wrong.append("%s v%d input_hash %s, recomputed %s"
                                 % (node["node_id"], ver["v"],
                                    ver["input_hash"][:12], h.hexdigest()[:12]))
    derived = sum(1 for n in manifest["nodes"] for v in n["versions"]
                  if v.get("epistemic") in ("measured", "inferred"))
    record("%s: every node stamped, every derived hash recomputes" % tag,
           "PASS" if not missing and not wrong else "FAIL",
           "%d versions stamped, %d derived, %d input_hash recomputed and "
           "matched, %d problem(s)"
           % (stamped, derived, derived - len(missing) - len(wrong),
              len(missing) + len(wrong)))
    for pr in (missing + wrong)[:6]:
        print("        %s" % pr)

    # ---- 6. the binary envelopes ---------------------------------------
    sys.path.insert(0, os.path.join(ROOT, "loaders"))
    import werk_read
    envs = []
    for name, data in sorted(files.items()):
        if data[:2] == b"WK" and len(data) > 12:
            magic, ver, hdr = werk_read.read_envelope(data)
            secs = hdr["sections"]
            envs.append("%s %s v%d %d bytes, %d section(s): %s"
                        % (name, magic.decode("ascii"), ver, len(data), len(secs),
                           ", ".join("%s %s[%s] stride %d"
                                     % (s["name"], s["dtype"],
                                        "x".join(str(d) for d in s["shape"]),
                                        s["stride"]) for s in secs)))
    record("%s: binary envelopes parse" % tag, "PASS" if envs else "WARN",
           "%d envelope file(s)" % len(envs))
    for e in envs:
        print("        %s" % e)

    # ---- the numbers for HANDOVER --------------------------------------
    rep = json.loads(files["x/pipeline-report.json"])
    return {
        "path": path, "bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest(),
        "entries": len(files), "nodes": len(manifest["nodes"]),
        "declared_files": sum(len(v["files"]) for n in manifest["nodes"]
                              for v in n["versions"]),
        "manifest_bytes": len(files["MANIFEST.json"]),
        "preview_prefix_bytes": manifest["container"]["preview_prefix_bytes"],
        "derived": derived, "stamped": stamped,
        "stages": rep["stages"], "summary": rep["summary"],
        "core_errors": len(errors), "dead": len(dead),
        "signature": pkg.signature_state,
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", nargs="*", default=None)
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "core", "target", "gate-3b"))
    ap.add_argument("--skip-build", action="store_true")
    args = ap.parse_args(argv)

    os.makedirs(args.out_dir, exist_ok=True)
    inputs = [(p, os.path.basename(os.path.dirname(p))) for p in (args.inputs or [])] \
        or DEFAULT_INPUTS

    results = []
    for src, tag in inputs:
        out = os.path.join(args.out_dir, "%s.werk" %
                           os.path.basename(os.path.dirname(src)))
        if not os.path.isfile(src):
            record("%s: input present" % tag, "FAIL", "%s not found" % src)
            continue
        if not args.skip_build:
            t0 = time.perf_counter()
            p = subprocess.run([sys.executable,
                                os.path.join(ROOT, "pipeline", "enrich.py"),
                                src, out, "--name", tag],
                               capture_output=True, text=True, cwd=ROOT)
            dt = time.perf_counter() - t0
            print(p.stdout)
            if p.returncode != 0:
                record("%s: pipeline runs unattended" % tag, "FAIL",
                       (p.stderr or "")[-400:])
                continue
            record("%s: pipeline runs unattended" % tag, "PASS",
                   "%.1f s, exit 0, no prompts" % dt)
        r = check_package(out, tag)
        r["tag"] = tag
        r["source"] = src
        results.append(r)

    # ---- determinism ----------------------------------------------------
    # Everything derived is arithmetic with declared seeds, so the only thing
    # that can differ between two runs is what the pipeline honestly measures
    # about the run itself: wall times, the clock, the caller's paths.
    # --reproducible drops exactly those, and the rest must then be identical
    # to the byte.
    if not args.skip_build and len(inputs) > DETERMINISM_INPUT:
        src, tag = inputs[DETERMINISM_INPUT]
        digests = []
        for k in (1, 2):
            o = os.path.join(args.out_dir, "determinism-%d.werk" % k)
            p = subprocess.run([sys.executable,
                                os.path.join(ROOT, "pipeline", "enrich.py"), src, o,
                                "--name", tag, "--created", "2026-08-08T12:00:00Z",
                                "--reproducible", "--no-vlm", "--quiet"],
                               capture_output=True, text=True, cwd=ROOT)
            if p.returncode != 0:
                digests = []
                break
            digests.append(hashlib.sha256(open(o, "rb").read()).hexdigest())
        same = len(digests) == 2 and digests[0] == digests[1]
        record("determinism: two --reproducible runs agree", "PASS" if same else "FAIL",
               "%s over %s" % (digests[0][:32] + "..." if digests else "no runs", tag))

    print("")
    print("Stage 3B measurements")
    print("=" * 78)
    for r in results:
        print("%s  (%s)" % (r["tag"], r["source"]))
        print("  %d bytes, sha256 %s" % (r["bytes"], r["sha256"]))
        print("  %d zip entries, %d nodes, %d declared files, manifest %d bytes"
              % (r["entries"], r["nodes"], r["declared_files"], r["manifest_bytes"]))
        print("  preview_prefix_bytes %d (%.2f%%)"
              % (r["preview_prefix_bytes"],
                 100.0 * r["preview_prefix_bytes"] / r["bytes"]))
        print("  %d versions stamped, %d derived with a recomputed input_hash"
              % (r["stamped"], r["derived"]))
        print("  werk-core: %d error(s), %d dead node(s), signature %s"
              % (r["core_errors"], r["dead"], r["signature"]))
        print("  producers: %d ok, %d failed" % (r["summary"]["ok"],
                                                 r["summary"]["failed"]))
        for s in r["stages"]:
            print("    %-14s %-7s %8.2fs  %s"
                  % (s["stage"], s["status"], s["wall_seconds"],
                     (s.get("error") or s.get("detail") or "")[:96]))
        print("")

    npass = sum(1 for _n, s, _d in RESULTS if s == "PASS")
    nfail = sum(1 for _n, s, _d in RESULTS if s == "FAIL")
    nwarn = sum(1 for _n, s, _d in RESULTS if s == "WARN")
    print("%d PASS, %d FAIL, %d WARN" % (npass, nfail, nwarn))
    with open(os.path.join(args.out_dir, "results.json"), "w") as fh:
        json.dump({"checks": RESULTS, "packages": [
            {k: v for k, v in r.items() if k != "stages"} | {"stages": r["stages"]}
            for r in results]}, fh, indent=2)
    return 1 if nfail else 0


if __name__ == "__main__":
    sys.exit(main())
