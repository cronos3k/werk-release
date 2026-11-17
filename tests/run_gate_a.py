#!/usr/bin/env python3
"""run_gate_a.py — Stage 3 Gate A, MEASURED.

Gate A, quoted from briefs/STAGE3-BRIEF.md: "werk-core loads both; damaged
loads with exact skip report; bootstrap readers parse the intact one
standalone."

Nothing here asserts a number it did not observe. Every check prints what it
saw, and the damaged-fixture check asserts the EXACT report — the precise
codes, on the precise nodes, with the precise survivors — because "it did not
crash" is not a measurement of graceful degradation.

Clause 6b builds one more damaged package in-test (a `requires` edge to an
absent node, its cascade, and an `enhances` edge to an absent node) and runs
werk-core and all three bootstrap loaders on it. They must report the same
dead nodes under the same codes (SPEC section 5, "Edge targets").

    python tests/run_gate_a.py [--rebuild]

--rebuild adds the rebuild clauses: crate-v1 and crate-v1-damaged rebuilt
from the inputs crate-v1.werk carries, reported at three levels (archive
reassembly, computed payloads, original inputs). It writes only to the
gate's work dir.

Exit 0 only when nothing FAILED and nothing was SKIPPED.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, "fixtures")
CLEAN = os.path.join(FIX, "crate-v1.werk")
DAMAGED = os.path.join(FIX, "crate-v1-damaged.werk")
WORK = os.path.join(ROOT, "core", "target", "gate-a")
# S8-1..S8-3: a gate's numbers are measurements of ONE fixture build, so the
# build is pinned against fixtures/fixtures.json before anything is measured.
# A rebuild then fails here with both hashes in the message, instead of the
# gate going on printing PASS about a different file.
sys.path.insert(0, os.path.join(ROOT, "tests"))
from fixture_pin import pin as _pin_fixture           # noqa: E402


RESULTS = []


def record(name, status, detail=""):
    RESULTS.append((name, status, detail))
    print("[%s] %-38s %s" % (status, name, detail))


def compiler_env(cc):
    """The compiler's own bin directory first on PATH, so a MinGW gcc loads
    its own DLLs rather than another MinGW's (finding N2; see
    tests/gate_common.py)."""
    env = dict(os.environ)
    if cc:
        env["PATH"] = os.path.dirname(os.path.abspath(cc)) + os.pathsep + env.get("PATH", "")
    return env


def run(cmd, cwd=None, env=None):
    # A host that refuses to start a freshly built executable (Windows
    # Smart App Control: OSError WinError 4551) must be recorded as a
    # FAIL with the reason, not crash the gate with a traceback.
    try:
        p = subprocess.run(cmd, cwd=cwd or ROOT, capture_output=True, text=True,
                           env=env)
    except OSError as e:
        return 1, "could not start %s (host refused or missing): %r" % (cmd[0], e)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def sha256_file(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def build_c_with_msvc(src, exe):
    """cl.exe is not on PATH by default; find vcvars64 and go through a batch
    file. Writing the batch file rather than chaining `call ... && cl ...` is
    boring and works — the chained form returns 1 with no output at all, which
    cost a debugging round in the Stage 2 harness and is recorded there too."""
    if os.name != "nt":
        return False
    base = r"C:\Program Files\Microsoft Visual Studio\2022"
    vcvars = None
    for edition in ("Community", "Professional", "Enterprise", "BuildTools"):
        cand = os.path.join(base, edition, r"VC\Auxiliary\Build\vcvars64.bat")
        if os.path.isfile(cand):
            vcvars = cand
            break
    if not vcvars:
        return False
    bat = os.path.join(WORK, "_msvc_c.bat")
    os.makedirs(os.path.dirname(bat), exist_ok=True)
    with open(bat, "w") as fh:
        fh.write("@echo off\r\n")
        fh.write('call "%s"\r\n' % vcvars)
        # cd into the work dir rather than passing /Fo: a trailing backslash
        # inside a quoted argument escapes the quote, and cl then tries to
        # write to a path with a stray '"' in it.
        fh.write('cd /d "%s"\r\n' % WORK)
        fh.write('cl /nologo /O2 /W3 "%s" /Fe:"%s"\r\n' % (src, exe))
    rc, _out = run(["cmd", "/c", bat])
    return rc == 0 and os.path.isfile(exe)


def build_dangling(dest):
    """crate-v1.werk with three manifest edits, built in-test (nothing is
    committed): `semantics` gets a `requires` edge to `ghost-node`, which is
    in no node; `props` gets a `requires` edge to `semantics` (the cascade);
    `material-wood` gets an `enhances` edge to `ghost-tex` (the control for
    the edge kind). `evidence-segments --requires--> evidence-views` is
    already in the fixture and is the control for a skipped target.
    SIGNATURE.json is dropped, so the edit does not add a signature-invalid
    error; every entry stays stored and in the source order."""
    import zipfile
    with zipfile.ZipFile(CLEAN) as zin:
        man = json.loads(zin.read("MANIFEST.json"))
        by_id = {n["node_id"]: n for n in man["nodes"]}
        by_id["semantics"]["edges"].append(
            {"to": "ghost-node", "kind": "requires", "role": "describes"})
        by_id["props"]["edges"].append(
            {"to": "semantics", "kind": "requires", "role": "test-chain"})
        by_id["material-wood"]["edges"].append(
            {"to": "ghost-tex", "kind": "enhances", "role": "sampled-by"})
        mbytes = (json.dumps(man, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_STORED) as zout:
            for info in zin.infolist():
                if info.filename == "SIGNATURE.json":
                    continue
                data = mbytes if info.filename == "MANIFEST.json" else zin.read(info.filename)
                zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                zi.compress_type = zipfile.ZIP_STORED
                zout.writestr(zi, data)


# Each reader's spelling of the same three facts. The CODE token is shared;
# the line format is each reader's own. A tuple means: all of these on one line.
DANGLING_EXPECT = {
    "werk_read.py": [
        ("semantics requires-missing-node", "requires-missing-node: semantics:"),
        ("props requires-dead-node", "requires-dead-node: props:"),
        ("material-wood edge-dangling", "edge-dangling: material-wood:"),
    ],
    "werk_read.rs": [
        ("semantics requires-missing-node", ("node semantics: DEAD", "requires-missing-node:")),
        ("props requires-dead-node", ("node props: DEAD", "requires-dead-node:")),
        ("material-wood edge-dangling", "node material-wood: edge-dangling:"),
    ],
    "werk_read.c": [
        ("semantics requires-missing-node", "node=semantics reason=requires-missing-node"),
        ("props requires-dead-node", "node=props reason=requires-dead-node"),
        ("material-wood edge-dangling", "node=material-wood reason=edge-dangling"),
    ],
}
# Each loader's exit convention: 0 with dead nodes; with --strict, 1. Ruling 9
# of 2026-10-13 (docs/RULINGS-2026-10-13.md) unified the bootstrap loaders'
# exit statuses, so the Rust loader's --strict exit is 1 on this lineage, not
# the 3 it was when PR #11 was written against the public snapshot.
DANGLING_EXIT = {"werk_read.py": (0, 1), "werk_read.rs": (0, 1), "werk_read.c": (0, 1)}


def dangling_edges_clause(werkpy, loaders, rs_exe, c_exe):
    dest = os.path.join(WORK, "dangling-edges.werk")
    build_dangling(dest)

    # werk-core, through the shared library
    with werkpy.Package.open(dest) as p:
        st = {n.node_id: n.status for n in p.nodes}
        codes = {}
        for e in p.report:
            codes.setdefault(e.code, []).append(e.node_id or "")
        problems = []
        dead = sorted(k for k, v in st.items() if v == "dead")
        if dead != ["props", "semantics"]:
            problems.append("dead=%s expected ['props', 'semantics']" % dead)
        if codes.get("requires-missing-node") != ["semantics"]:
            problems.append("requires-missing-node on %s" % codes.get("requires-missing-node"))
        if codes.get("requires-dead-node") != ["props"]:
            problems.append("requires-dead-node on %s" % codes.get("requires-dead-node"))
        if codes.get("edge-dangling") != ["material-wood"]:
            problems.append("edge-dangling on %s" % codes.get("edge-dangling"))
        if st.get("material-wood") != "alive":
            problems.append("material-wood is %s" % st.get("material-wood"))
        if st.get("evidence-segments") != "skipped":
            problems.append("evidence-segments is %s; a requires edge into a "
                            "SKIPPED node must not kill" % st.get("evidence-segments"))
        if codes.get("hash-mismatch"):
            problems.append("hash-mismatch on %s" % codes.get("hash-mismatch"))
        if p.errors == 0:
            problems.append("no error entry, so a CLI would exit 0")
        record("dangling edges: werk-core", "PASS" if not problems else "FAIL",
               "semantics dead (requires-missing-node), props dead (cascade), "
               "material-wood alive (edge-dangling), evidence-segments skipped"
               if not problems else "; ".join(problems))

    py = [sys.executable, os.path.join(loaders, "werk_read.py")]
    for name, cmd in (("werk_read.py", py),
                      ("werk_read.rs", [rs_exe] if rs_exe else None),
                      ("werk_read.c", [c_exe] if c_exe else None)):
        label = "dangling edges: " + name
        if cmd is None:
            record(label, "SKIP", "not built in this run")
            continue
        rc, out = run(cmd + [dest, "--report"])
        rcs, _ = run(cmd + [dest, "--report", "--strict"])
        lines = out.splitlines()
        missing = [what for what, needle in DANGLING_EXPECT[name]
                   if not any(all(k in l for k in ((needle,) if isinstance(needle, str)
                                                   else needle)) for l in lines)]
        problems = []
        if missing:
            problems.append("report lacks: " + ", ".join(missing))
        want = DANGLING_EXIT[name]
        if (rc, rcs) != want:
            problems.append("exit %d / --strict %d, documented %d / %d"
                            % (rc, rcs, want[0], want[1]))
        # A dangling requires edge is one fact: it must not ALSO be reported
        # as edge-dangling.
        for l in lines:
            if "edge-dangling" in l and "ghost-node" in l:
                problems.append("ghost-node reported twice: " + l.strip()[:80])
        record(label, "PASS" if not problems else "FAIL",
               ("same three facts; exit %d, --strict %d (its documented convention)"
                % (rc, rcs)) if not problems else "; ".join(problems))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true",
                    help="also rebuild the golden pair from the inputs the "
                    "package carries, into the work dir")
    args = ap.parse_args(argv)

    os.makedirs(WORK, exist_ok=True)
    print("werk Stage 3 Gate A — the golden sample")
    print("repo   : %s" % ROOT)

    # --rebuild no longer builds into fixtures/: it adds the rebuild clauses
    # (section 9), which build into the work dir. A missing fixture is still
    # built in place from the author's source tree, as before.
    if not os.path.isfile(CLEAN):
        rc, out = run([sys.executable, os.path.join(FIX, "build_golden.py")])
        if rc != 0:
            record("build", "FAIL", out.strip()[-300:])
            return 1

    for key in ("crate-v1", "crate-v1-damaged"):
        r = _pin_fixture(key)
        record("fixture pinned: " + key, "PASS" if r.ok else "FAIL", r.detail)
    for label, path in (("clean", CLEAN), ("damaged", DAMAGED)):
        print("%-8s: %s" % (label, path))
        print("          %d bytes, sha256 %s" % (os.path.getsize(path),
                                                 sha256_file(path)))
    print()

    sys.path.insert(0, os.path.join(ROOT, "bindings", "python"))
    try:
        import werk as werkpy
    except Exception as e:  # noqa: BLE001
        record("python binding import", "FAIL", repr(e))
        return 1

    # -- 1. werk-core loads the clean fixture, no errors -----------------
    with werkpy.Package.open(CLEAN) as p:
        nodes = p.nodes
        alive = [n for n in nodes if n.status == "alive"]
        skipped = [n for n in nodes if n.status == "skipped"]
        ok = (p.errors == 0 and p.signature_state == "signed-and-valid"
              and len(nodes) == 36 and len(skipped) == 2 and not
              [n for n in nodes if n.status == "dead"])
        record("werk-core loads the clean fixture", "PASS" if ok else "FAIL",
               "%d nodes (%d alive, %d skipped, 0 dead), signature %s, %d error(s)"
               % (len(nodes), len(alive), len(skipped), p.signature_state, p.errors))
        clean_manifest = p.manifest_sha256

    # -- 2. round-trip byte identity ------------------------------------
    with werkpy.Package.open(CLEAN) as p:
        out_zip = os.path.join(WORK, "roundtrip.werk")
        t0 = time.time()
        p.write_zip(out_zip)
        secs = time.time() - t0
        same = sha256_file(out_zip) == sha256_file(CLEAN)
        record("round-trip byte identity", "PASS" if same else "FAIL",
               "%s (%.2f s for %.1f MiB)"
               % ("sha256 identical" if same else "DIFFERS",
                  secs, os.path.getsize(CLEAN) / 1048576.0))

    # -- 3. the damaged fixture: the EXACT report ------------------------
    with werkpy.Package.open(DAMAGED) as p:
        codes = {}
        for e in p.report:
            codes.setdefault(e.code, []).append(e.node_id or "")
        dead = sorted(n.node_id for n in p.nodes if n.status == "dead")
        skipped = sorted(n.node_id for n in p.nodes if n.status == "skipped")
        alive = [n for n in p.nodes if n.status == "alive"]
        expect_dead = ["audio-crate-impact-hard-surface"]
        expect_skipped = ["evidence-segments", "evidence-views", "mystery"]
        problems = []
        if dead != expect_dead:
            problems.append("dead=%s expected %s" % (dead, expect_dead))
        if skipped != expect_skipped:
            problems.append("skipped=%s expected %s" % (skipped, expect_skipped))
        if codes.get("hash-mismatch") != ["audio-crate-impact-hard-surface"]:
            problems.append("hash-mismatch on %s" % codes.get("hash-mismatch"))
        if sorted(codes.get("node-skipped-unknown-type", [])) != expect_skipped:
            problems.append("unknown-type on %s"
                            % codes.get("node-skipped-unknown-type"))
        # The finding that is easiest to get backwards: corrupting a PAYLOAD
        # does not invalidate the SIGNATURE. The chain signs the manifest and
        # the manifest hashes the files, so detection belongs to the per-file
        # hash. A reader reporting "signature invalid" here names the wrong fact.
        if p.signature_state != "signed-and-valid":
            problems.append("signature is %s; a corrupt payload must NOT "
                            "invalidate the chain" % p.signature_state)
        if len(alive) != 33:
            problems.append("%d alive, expected 33" % len(alive))
        record("damaged: exact skip report", "PASS" if not problems else "FAIL",
               ("1 hash-mismatch (dead), 3 unknown-type (skipped), %d alive, "
                "signature still %s" % (len(alive), p.signature_state))
               if not problems else "; ".join(problems))

    # -- 4/5/6. the three bootstrap readers, standalone ------------------
    loaders = os.path.join(ROOT, "loaders")
    rs_exe = c_exe = None     # set only when built in THIS run (clause 6b)

    rc, out = run([sys.executable, os.path.join(loaders, "werk_read.py"),
                   CLEAN, "--verify", "--strict"])
    line = [l for l in out.splitlines() if "verified over" in l]
    record("bootstrap: werk_read.py", "PASS" if rc == 0 else "FAIL",
           line[0].strip() if line else out.strip()[-160:])

    if shutil.which("rustc"):
        exe = os.path.join(WORK, "werk_read_rs.exe" if os.name == "nt" else "werk_read_rs")
        rc, out = run(["rustc", "-O", "--edition", "2021", "-o", exe,
                       os.path.join(loaders, "werk_read.rs")])
        if rc != 0:
            record("bootstrap: werk_read.rs", "FAIL", "rustc: " + out.strip()[-200:])
        else:
            rs_exe = exe
            rc, out = run([exe, CLEAN, "--verify", "--strict"])
            line = [l for l in out.splitlines() if "verify" in l or "PASS" in l][-1:]
            record("bootstrap: werk_read.rs", "PASS" if rc == 0 else "FAIL",
                   (line[0].strip() if line else out.strip()[-160:])[:120])
    else:
        record("bootstrap: werk_read.rs", "SKIP", "rustc not on PATH")

    cc = shutil.which("gcc") or shutil.which("clang")
    exe = os.path.join(WORK, "werk_read_c.exe" if os.name == "nt" else "werk_read_c")
    built = False
    if cc:
        rc, out = run([cc, "-std=c99", "-O2", "-o", exe,
                       os.path.join(loaders, "werk_read.c")], env=compiler_env(cc))
        built = rc == 0
    if not built:
        # Same fallback the Stage 2 harness has always had: MSVC is not on PATH
        # by default, and a gate that reports SKIP because it did not look is a
        # gate that measured nothing.
        built = build_c_with_msvc(os.path.join(loaders, "werk_read.c"), exe)
    if not built:
        record("bootstrap: werk_read.c", "SKIP", "no C compiler could build it")
    else:
        c_exe = exe
        rc, out = run([exe, CLEAN, "--verify", "--strict"])
        line = [l for l in out.splitlines() if "verify:" in l][-1:]
        record("bootstrap: werk_read.c", "PASS" if rc == 0 else "FAIL",
               (line[0].strip() if line else out.strip()[-160:]))

    # -- 6b. dangling edges: every reader gives the same answer -----------
    # SPEC section 5, "Edge targets". Before this clause no shared test held
    # a `requires` edge to an absent node, and the readers split two ways on
    # it while each one passed its own gate. werk-core's exact report for the
    # same shape is core/tests/conformance.rs
    # gate_damage_requires_edge_into_absent_node.
    dangling_edges_clause(werkpy, loaders, rs_exe, c_exe)

    # -- 7. extraction actually works ------------------------------------
    with werkpy.Package.open(CLEAN) as p:
        mesh = p.blob("geometry/game.glb")
        snd = p.blob("audio/sfx/crate-impact-hard-surface.wav")
        ok = mesh[:4] == b"glTF" and snd[:4] == b"RIFF" and snd[8:12] == b"WAVE"
        record("extract mesh + one sound", "PASS" if ok else "FAIL",
               "game.glb %d bytes (glTF magic ok), one-shot %d bytes (RIFF/WAVE ok)"
               % (len(mesh), len(snd)))

    # -- 8. primary.sound resolves to the WAV, not the descriptor --------
    # S-OW-2, measured: an 8B implementer followed primary.sound to its node,
    # took files[0], and wrote out the DESCRIPTOR JSON where a WAV was asked
    # for -- while reporting success. SPEC 2.1 answers it with `payload_file`
    # and an ordered fallback. This clause is that failure, executed.
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from payload_file import payload_file_for, check_payload_files   # noqa: E402
    import zipfile as _zip
    with _zip.ZipFile(CLEAN) as z:
        man = json.loads(z.read("MANIFEST.json"))
    problems = []
    by_id = {n["node_id"]: n for n in man["nodes"]}
    resolved = {}
    for key, node_id in (man.get("primary") or {}).items():
        node = by_id.get(node_id)
        if node is None:
            problems.append("primary.%s names %r, which is not a node"
                            % (key, node_id))
            continue
        ver = [v for v in node["versions"] if v["v"] == node["active"]][0]
        path = ver.get("payload_file") or payload_file_for(node["type"],
                                                           ver["files"])
        if path is None:
            problems.append("primary.%s: payload not determinable" % key)
            continue
        resolved[key] = path
        if path.endswith(".json"):
            problems.append("primary.%s resolves to %s, a descriptor" % (key, path))
    if resolved.get("sound") != "audio/sfx/crate-impact-hard-surface.wav":
        problems.append("primary.sound -> %r" % resolved.get("sound"))
    if resolved.get("mesh") != "geometry/game.glb":
        problems.append("primary.mesh -> %r" % resolved.get("mesh"))
    problems += check_payload_files(man)
    record("primary.* resolves to a payload file (S-OW-2)",
           "PASS" if not problems else "FAIL",
           ("%d primary key(s) resolved: %s; every payload_file names a file "
            "in its own version" % (len(resolved),
                                    ", ".join("%s -> %s" % kv for kv in
                                              sorted(resolved.items()))))
           if not problems else "; ".join(problems))

    # -- 9. --rebuild: rebuild the golden pair, at three levels -----------
    # "Rebuild" means three different things, and each is reported on its
    # own (Codex review rows G16, G17):
    #   L1 archive reassembly: the whole .werk is byte-identical to the pin,
    #      rebuilt from the inputs crate-v1.werk carries
    #   L2 computed payloads: every entry the builder computes (not copies,
    #      and not the records its JSON inputs were reconstructed from)
    #   L3 original inputs: the builder on the author's source tree
    # L1 and L2 run on any machine. Every input comes out of crate-v1.werk
    # and is checked against its manifest sha256. The rebuild goes into the
    # work dir, never into fixtures/.
    if args.rebuild:
        import package_rebuild as pr
        try:
            shipped = {}
            for key, path in (("crate-v1", CLEAN),
                              ("crate-v1-damaged", DAMAGED)):
                shipped[key], _o = pr.read_zip(path)
            rb = os.path.join(WORK, "rebuild")
            root = os.path.join(rb, "root")
            src = os.path.join(rb, "src")
            out = os.path.join(rb, "out")
            shutil.rmtree(out, ignore_errors=True)
            os.makedirs(out)
            spec_loaders = pr.make_overlay(ROOT, shipped["crate-v1"], root)
            copied, records = pr.golden_source_tree(shipped["crate-v1"], src)
            bad = pr.check_declared(shipped["crate-v1"],
                                    spec_loaders + copied + records)
            if bad:
                raise ValueError("packaged inputs do not match the manifest: "
                                 + "; ".join(bad[:5]))
            rc, log = run([sys.executable,
                           os.path.join(root, "fixtures", "build_golden.py"),
                           "--src", src, "--out", out])
            if rc != 0:
                raise ValueError("builder exit %d: %s"
                                 % (rc, log.strip()[-200:]))
            not_computed = set(spec_loaders) | set(copied) | set(records)
            for key, path in (("crate-v1", CLEAN),
                              ("crate-v1-damaged", DAMAGED)):
                rebuilt_path = os.path.join(out, key + ".werk")
                again, _o = pr.read_zip(rebuilt_path)
                c = pr.compare(shipped[key], again, not_computed)
                whole, pin = sha256_file(rebuilt_path), sha256_file(path)
                d1 = ("%s vs pin %s; %d/%d entries identical; substitution: %s"
                      % (whole[:16], pin[:16], c["identical"], c["total"],
                         " | ".join(pr.GOLDEN_SUBSTITUTIONS)))
                if whole != pin:
                    d1 = "differ: %s; %s" % (", ".join(c["differ"]), d1)
                record("rebuild L1: %s archive" % key,
                       "PASS" if whole == pin else "FAIL", d1)
                ok_computed = len(c["computed"]) - len(c["computed_bad"])
                d2 = ("%d/%d computed entries identical; not counted: %d "
                      "binaries copied in (model, views, segments, sound "
                      "takes), %d JSON records the JSON inputs were "
                      "reconstructed from (circular), %d spec/ and loaders/ "
                      "files"
                      % (ok_computed, len(c["computed"]), len(copied),
                         len(records), len(spec_loaders)))
                if c["computed_bad"] or c["inputs_bad"]:
                    d2 = "differ: %s; %s" % (
                        ", ".join(c["computed_bad"] + c["inputs_bad"]), d2)
                record("rebuild L2: %s computed payloads" % key,
                       "FAIL" if (c["computed_bad"] or c["inputs_bad"])
                       else "PASS", d2)
        except Exception as e:  # noqa: BLE001
            record("rebuild L1/L2 from the packaged inputs", "FAIL", repr(e))

        # L3: the original inputs, the path --rebuild used to take (it built
        # into fixtures/; now it builds into the work dir).
        n3 = "rebuild L3: original inputs (author-lab)"
        orig = os.path.join(WORK, "rebuild-original")
        os.makedirs(orig, exist_ok=True)
        rc, log = run([sys.executable, os.path.join(FIX, "build_golden.py"),
                       "--out", orig])
        if rc != 0:
            record(n3, "SKIP",
                   "needs the author's splat-foley output tree "
                   "(<WERK_LAB>/splat-foley/outputs/example): the original JSON "
                   "inputs. The model, views, segments and sound takes are "
                   "outputs of the splat-foley pipeline; regenerating them is "
                   "outside any rebuild. " + log.strip()[-120:])
        else:
            same = all(sha256_file(os.path.join(orig, os.path.basename(p)))
                       == sha256_file(p) for p in (CLEAN, DAMAGED))
            if same:
                record(n3, "PASS", "both fixtures rebuilt from the original "
                       "tree, identical sha256")
            else:
                import package_rebuild as pr
                parts = []
                for p in (CLEAN, DAMAGED):
                    a, _o = pr.read_zip(p)
                    b, _o = pr.read_zip(os.path.join(orig, os.path.basename(p)))
                    d = sorted(n for n in set(a) | set(b) if a.get(n) != b.get(n))
                    parts.append("%s: %d/%d entries differ%s"
                                 % (os.path.basename(p), len(d), len(set(a) | set(b)),
                                    (" (" + ", ".join(d[:12]) + ")") if d else ""))
                record(n3, "FAIL", "a rebuild from the original tree produced "
                       "different bytes; " + "; ".join(parts))

    print()
    print("manifest sha256 %s" % clean_manifest)
    npass = sum(1 for _, s, _ in RESULTS if s == "PASS")
    nfail = sum(1 for _, s, _ in RESULTS if s == "FAIL")
    nskip = sum(1 for _, s, _ in RESULTS if s == "SKIP")
    print("%d PASS, %d FAIL, %d SKIP" % (npass, nfail, nskip))
    print("GATE A: %s" % ("PASSED" if nfail == 0 and nskip == 0 else
                          "INCOMPLETE (%d SKIPPED; a skip is not a pass)" % nskip
                          if nfail == 0 else "FAILED"))
    # Exit non-zero on a skip too: the docstring promises exit 0 only when
    # nothing FAILED and nothing was SKIPPED, and "a SKIP is not a PASS".
    return 1 if (nfail or nskip) else 0


if __name__ == "__main__":
    sys.exit(main())
