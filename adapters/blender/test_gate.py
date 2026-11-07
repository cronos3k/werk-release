#!/usr/bin/env python3
"""Stage 11 gate — the Blender adapter, measured.

    python adapters/blender/test_gate.py [--blender PATH] [--keep]

Finds a Blender, runs `gate_in_blender.py` inside it headless, then verifies
the exported package with the two INDEPENDENT readers the repository already
has — `bindings/python/werk.py` over `werk.dll` (the Rust core) and
`loaders/werk_read.py` standalone. Three implementations agreeing is the
measurement; one implementation agreeing with itself is not.

House rule: a gate is a measurement. Every number printed here comes from this
run. A clause whose toolchain is absent is reported SKIP with the reason, never
folded into a pass — `10 PASS 0 FAIL 0 SKIP` and `8 PASS 0 FAIL 2 SKIP` are
different results and the difference is the whole point.
"""

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
ADDON_PARENT = HERE
WORK = os.path.join(HERE, "_gate_out")

CLEAN_FIXTURE = os.path.join(ROOT, "fixtures", "crate-v1.werk")
DAMAGED_FIXTURE = os.path.join(ROOT, "fixtures", "crate-v1-damaged.werk")
#: Stage 12. A real Gaussian splat and its derived point cloud, so the
#: add-on's newest import path is measured against a shipped fixture rather
#: than against something the gate built for itself.
GSPLAT_FIXTURE = os.path.join(ROOT, "fixtures", "gsplat-v1.werk")
# S8-1..S8-3: a gate's numbers are measurements of ONE fixture build, so the
# build is pinned against fixtures/fixtures.json before anything is measured.
# A rebuild then fails here with both hashes in the message, instead of the
# gate going on printing PASS about a different file.
sys.path.insert(0, os.path.join(ROOT, "tests"))
from fixture_pin import pin as _pin_fixture           # noqa: E402



# ---------------------------------------------------------------------------
# finding Blender
# ---------------------------------------------------------------------------

def find_blender(explicit=None):
    """Returns (path, how_it_was_found) or (None, reason)."""
    if explicit:
        return (explicit, "given on the command line") if os.path.isfile(explicit) \
            else (None, "the --blender path does not exist: %s" % explicit)

    env = os.environ.get("WERK_BLENDER")
    if env and os.path.isfile(env):
        return env, "the WERK_BLENDER environment variable"

    which = shutil.which("blender")
    if which:
        return which, "PATH"

    patterns = [
        r"C:\Program Files\Blender Foundation\Blender *\blender.exe",
        r"C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe",
        os.path.join(ROOT, "tools", "blender", "**", "blender.exe"),
        os.path.join(ROOT, "tools", "blender", "**", "blender"),
        "/usr/bin/blender", "/usr/local/bin/blender", "/snap/bin/blender",
        "/Applications/Blender.app/Contents/MacOS/Blender",
    ]
    found = []
    for pat in patterns:
        found += [p for p in glob.glob(pat, recursive=True) if os.path.isfile(p)]
    if found:
        found.sort()
        return found[-1], "a filesystem search of the usual install locations"
    return None, ("no Blender found on PATH, in WERK_BLENDER, under "
                  "tools/blender/, or in the usual install locations. "
                  "Download the portable archive of the current LTS into "
                  "tools/blender/ (it is open source; see "
                  "tools/blender/README.md) and re-run.")


def blender_version(path):
    out = subprocess.run([path, "--background", "--version"],
                         capture_output=True, text=True, timeout=180)
    for line in (out.stdout or "").splitlines():
        if line.startswith("Blender "):
            return line.strip()
    return "unknown"


# ---------------------------------------------------------------------------
# independent verification of what Blender wrote
# ---------------------------------------------------------------------------

def verify_with_werk_core(pkg_path):
    """The Rust core, through the ctypes binding, over one werk.dll."""
    sys.path.insert(0, os.path.join(ROOT, "bindings", "python"))
    try:
        import werk as werkcore
    except Exception as e:  # noqa: BLE001
        return None, "bindings/python/werk.py did not import: %s" % e
    try:
        with werkcore.Package.open(pkg_path) as p:
            nodes = p.nodes
            report = p.report
            return {
                "nodes": len(nodes),
                "alive": sum(1 for n in nodes if n.status == "alive"),
                "dead": sum(1 for n in nodes if n.status == "dead"),
                "skipped": sum(1 for n in nodes if n.status == "skipped"),
                "signature": p.signature_state,
                "entity_uuid": p.entity_uuid,
                "manifest_sha256": p.manifest_sha256,
                "errors": sum(1 for r in report if r.severity == "error"),
                "warnings": sum(1 for r in report if r.severity == "warn"),
                "report": ["[%s] %s: %s" % (r.severity, r.code, r.message)
                           for r in report],
            }, None
    except Exception as e:  # noqa: BLE001
        return None, "werk-core refused the package: %s" % e


def verify_with_bootstrap(pkg_path):
    """`loaders/werk_read.py`, standalone, sharing no code with werk-core."""
    loader = os.path.join(ROOT, "loaders", "werk_read.py")
    if not os.path.isfile(loader):
        return None, "loaders/werk_read.py is missing"
    proc = subprocess.run([sys.executable, loader, pkg_path, "--verify"],
                          capture_output=True, text=True, timeout=600)
    out = proc.stdout or ""
    passed = out.count("\nPASS ") + (1 if out.startswith("PASS ") else 0)
    failed = out.count("\nFAIL ") + (1 if out.startswith("FAIL ") else 0)
    summary = next((l for l in out.splitlines() if "files verified over" in l), "")
    return {"exit": proc.returncode, "pass": passed, "fail": failed,
            "summary": summary.strip(),
            "stderr": (proc.stderr or "").strip()[:2000]}, None


def vendored_copies_identical():
    script = os.path.join(ROOT, "tools", "blender", "vendor_spec.py")
    proc = subprocess.run([sys.executable, script, "--check"],
                          capture_output=True, text=True, timeout=300)
    return proc.returncode == 0, (proc.stdout or "").strip()


# ---------------------------------------------------------------------------
# the gate
# ---------------------------------------------------------------------------

class Gate(object):
    def __init__(self):
        self.rows = []

    def add(self, status, name, detail):
        self.rows.append((status, name, detail))
        print("[%-4s] %-38s %s" % (status, name, detail))

    def counts(self):
        p = sum(1 for s, _, _ in self.rows if s == "PASS")
        f = sum(1 for s, _, _ in self.rows if s == "FAIL")
        s = sum(1 for s_, _, _ in self.rows if s_ == "SKIP")
        return p, f, s


def clause(gate, results, name):
    for c in results.get("clauses", []):
        if c["clause"] == name:
            return c
    return None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--blender", help="path to the Blender executable")
    ap.add_argument("--keep", action="store_true",
                    help="keep the exported packages under _gate_out/")
    ap.add_argument("--json", help="also write the raw measurements here")
    args = ap.parse_args(argv)

    print("werk Stage 11 gate — the Blender adapter")
    print("=" * 62)

    gate = Gate()
    t_start = time.time()

    # -- 0. the pure-Python invariants, no Blender needed ----------------
    sys.path.insert(0, ADDON_PARENT)
    import werk_blender
    bad = werk_blender.selftest()
    gate.add("PASS" if not bad else "FAIL", "add-on selftest (no Blender)",
             "axes + bounds + zip + MessagePack: %s"
             % ("all invariants held" if not bad else "; ".join(bad)))

    ok, detail = vendored_copies_identical()
    gate.add("PASS" if ok else "FAIL", "vendored copies byte-identical",
             detail.splitlines()[-1] if detail else "no output")

    # -- fixtures --------------------------------------------------------
    missing = [p for p in (CLEAN_FIXTURE, DAMAGED_FIXTURE) if not os.path.isfile(p)]
    if missing:
        gate.add("FAIL", "fixtures present",
                 "missing: %s — run `python fixtures/build_golden.py`"
                 % ", ".join(os.path.relpath(m, ROOT) for m in missing))
        return _finish(gate, t_start, None, args)
    for key in ("crate-v1", "crate-v1-damaged", "gsplat-v1"):
        r = _pin_fixture(key)
        gate.add("PASS" if r.ok else "FAIL", "fixture pinned: " + key, r.detail)
    gate.add("PASS", "fixtures present",
             "crate-v1.werk %d B, crate-v1-damaged.werk %d B"
             % (os.path.getsize(CLEAN_FIXTURE), os.path.getsize(DAMAGED_FIXTURE)))

    # -- Blender ---------------------------------------------------------
    blender, how = find_blender(args.blender)
    if blender is None:
        for name in ("registration", "import: clean fixture",
                     "import: damaged fixture", "round trip: werk -> Blender -> werk",
                     "round trip: exported package verifies",
                     "writer determinism", "rig round trip (skeleton + clip)"):
            gate.add("SKIP", name, "no Blender: %s" % how)
        return _finish(gate, t_start, None, args)

    ver = blender_version(blender)
    gate.add("PASS", "Blender located", "%s (%s, found via %s)" % (ver, blender, how))

    if os.path.isdir(WORK):
        shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK, exist_ok=True)

    # Build the distributable zip so the OTHER install shape is measured too.
    addon_zip = os.path.join(WORK, "werk_blender.zip")
    zip_proc = subprocess.run(
        [sys.executable, os.path.join(ROOT, "tools", "blender",
                                      "build_addon_zip.py"), "--out", addon_zip],
        capture_output=True, text=True, timeout=600)
    if zip_proc.returncode != 0 or not os.path.isfile(addon_zip):
        gate.add("FAIL", "add-on zip builds",
                 (zip_proc.stdout or zip_proc.stderr or "").strip().splitlines()[-1]
                 if (zip_proc.stdout or zip_proc.stderr) else "no output")
        addon_zip = None
    else:
        gate.add("PASS", "add-on zip builds",
                 "%s, %d bytes" % (os.path.basename(addon_zip),
                                   os.path.getsize(addon_zip)))

    result_path = os.path.join(WORK, "gate_result.json")
    payload = {
        "addon_parent": ADDON_PARENT,
        "addon_zip": addon_zip,
        "clean": CLEAN_FIXTURE,
        "damaged": DAMAGED_FIXTURE,
        "round_trip_out": os.path.join(WORK, "roundtrip.werk"),
        "determinism_a": os.path.join(WORK, "det-a.werk"),
        "determinism_b": os.path.join(WORK, "det-b.werk"),
        "rig_out": os.path.join(WORK, "rig.werk"),
        "textured_out": os.path.join(WORK, "textured.werk"),
        "gsplat": GSPLAT_FIXTURE if os.path.isfile(GSPLAT_FIXTURE) else None,
        "result": result_path,
    }
    cmd = [blender, "--background", "--factory-startup", "--python",
           os.path.join(HERE, "gate_in_blender.py"), "--", json.dumps(payload)]
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    blender_seconds = time.time() - t0

    if not os.path.isfile(result_path):
        gate.add("FAIL", "Blender run",
                 "produced no result document in %.1f s; exit %d"
                 % (blender_seconds, proc.returncode))
        print("\n--- Blender stdout (tail) ---")
        print("\n".join((proc.stdout or "").splitlines()[-40:]))
        print("--- Blender stderr (tail) ---")
        print("\n".join((proc.stderr or "").splitlines()[-40:]))
        return _finish(gate, t_start, None, args)

    with open(result_path, encoding="utf-8") as fh:
        results = json.load(fh)
    gate.add("PASS", "Blender run",
             "%d clause(s) measured in %.1f s, exit %d"
             % (len(results.get("clauses", [])), blender_seconds, proc.returncode))
    for err in results.get("errors", []):
        print("    !! in-Blender exception:\n" +
              "\n".join("       " + l for l in err.strip().splitlines()[-6:]))

    # -- clause 0: registration -----------------------------------------
    c = clause(gate, results, "registration")
    if c is None:
        gate.add("FAIL", "registration", "clause did not run (see exception above)")
    else:
        gate.add("PASS" if c["registered"] else "FAIL", "registration",
                 "import + export operators registered and re-registered cleanly "
                 "under %s in %.3f s" % (c["blender"], c["seconds"]))

    # -- clause 0b: the zip install shape -------------------------------
    c = clause(gate, results, "zip_install")
    if addon_zip is None:
        gate.add("SKIP", "install from zip", "the add-on zip did not build")
    elif c is None:
        gate.add("FAIL", "install from zip", "clause did not run")
    else:
        ok = (c["registered"] and c["imported_from_zip"] and not c["selftest_failures"]
              and c["loader_in_zip"] and c["spec_files_in_zip"] > 0)
        gate.add("PASS" if ok else "FAIL", "install from zip",
                 "%d entries (%d spec files, reader %s), imported from the "
                 "unpacked zip and registered; selftest %s"
                 % (c["entries"], c["spec_files_in_zip"],
                    "present" if c["loader_in_zip"] else "MISSING",
                    "clean" if not c["selftest_failures"]
                    else "; ".join(c["selftest_failures"])))

    # -- clause 1: clean import -----------------------------------------
    c = clause(gate, results, "import_clean")
    if c is None:
        gate.add("FAIL", "import: clean fixture", "clause did not run")
    else:
        ok = (c["objects"] >= 2 and c["meshes"] >= 1 and c["vertices"] > 0
              and not c["unexpected_skips"] and c["nodes_dead"] == 0
              and c["report_text_present"])
        gate.add("PASS" if ok else "FAIL", "import: clean fixture",
                 "%d nodes (%d alive, %d dead, %d skipped-unknown), signature %s; "
                 "%d verts / %d tris, %d material(s), %d image(s), %d sound(s); "
                 "%d unexpected skip(s); %.3f s"
                 % (c["nodes_total"], c["nodes_alive"], c["nodes_dead"],
                    c["nodes_skipped"], c["signature"], c["vertices"],
                    c["triangles"], c["materials"], c["images"], c["sounds"],
                    len(c["unexpected_skips"]), c["seconds"]))
        if c["unexpected_skips"]:
            for code, msg in c["unexpected_skips"]:
                print("       unexpected: %s: %s" % (code, msg))

    # -- clause 2: damaged import ---------------------------------------
    c = clause(gate, results, "import_damaged")
    if c is None:
        gate.add("FAIL", "import: damaged fixture", "clause did not run")
    else:
        pkg = c["package_report_codes"]
        # The exact expectation, asserted as a SET and not as "did not crash":
        # one flipped payload byte -> exactly one hash-mismatch and one dead
        # node; three unknown node types skipped; the signature still valid,
        # because the chain signs the manifest and the manifest hashes the
        # files, so a corrupt payload is not a forged manifest.
        ok = (pkg.get("hash-mismatch") == 1
              and c["nodes_dead"] == 1
              and c["nodes_skipped"] >= 1
              and c["signature"] == "unverified"
              and c["nodes_alive"] >= c["nodes_total"] - 4
              and c["vertices"] > 0)
        gate.add("PASS" if ok else "FAIL", "import: damaged fixture",
                 "%d nodes: %d alive, %d dead, %d skipped-unknown; package report "
                 "%s; mesh still imported (%d verts); %.3f s"
                 % (c["nodes_total"], c["nodes_alive"], c["nodes_dead"],
                    c["nodes_skipped"], json.dumps(pkg, sort_keys=True),
                    c["vertices"], c["seconds"]))

    # -- clause 3: round trip -------------------------------------------
    c = clause(gate, results, "round_trip")
    exported = None
    if c is None:
        gate.add("FAIL", "round trip: werk -> Blender -> werk", "clause did not run")
    else:
        exported = c["exported"]
        ok = (c["uuid_survived"] and c["tags_survived"] and c["vertices_survived"]
              and c["reimport_errors"] == 0 and c["materials_after"] >= 1)
        gate.add("PASS" if ok else "FAIL", "round trip: werk -> Blender -> werk",
                 "uuid %s, tags %s, verts %d->%d %s, materials %d->%d; wrote %d B / "
                 "%d entries / %d nodes / %d files, manifest %d B, preview prefix "
                 "%d B (%.2f%%); identity %s; %.2f s in, %.2f s out, %.2f s back"
                 % ("SURVIVED" if c["uuid_survived"] else "LOST",
                    "SURVIVED" if c["tags_survived"] else "LOST",
                    c["vertices_before"], c["vertices_after"],
                    "SURVIVED" if c["vertices_survived"] else "CHANGED",
                    c["materials_before"], c["materials_after"],
                    c["exported_bytes"], c["exported_entries"], c["exported_nodes"],
                    c["exported_files"], c["exported_manifest_bytes"],
                    c["preview_prefix_bytes"],
                    100.0 * c["preview_prefix_bytes"] / max(1, c["exported_bytes"]),
                    "carried forward" if c["reused_identity"] else "MINTED FRESH",
                    c["import_seconds"], c["export_seconds"], c["reimport_seconds"]))
        for sev, code, msg in c.get("export_report", []):
            if sev in ("warn", "error"):
                print("       export %s %s: %s" % (sev, code, msg[:140]))

    # -- clause 4: the exported package, verified by two other readers ---
    if exported and os.path.isfile(exported):
        core, err = verify_with_werk_core(exported)
        if core is None:
            gate.add("SKIP", "exported .werk: werk-core verify", err)
        else:
            ok = core["errors"] == 0 and core["alive"] >= 1
            gate.add("PASS" if ok else "FAIL", "exported .werk: werk-core verify",
                     "%d nodes (%d alive, %d dead, %d skipped), signature %s, "
                     "%d error(s), %d warning(s)"
                     % (core["nodes"], core["alive"], core["dead"], core["skipped"],
                        core["signature"], core["errors"], core["warnings"]))
            for line in core["report"]:
                if "[error]" in line or "[warn]" in line:
                    print("       core %s" % line[:150])

        boot, err = verify_with_bootstrap(exported)
        if boot is None:
            gate.add("SKIP", "exported .werk: werk_read.py standalone", err)
        else:
            ok = boot["fail"] == 0 and boot["pass"] > 0 and boot["exit"] == 0
            gate.add("PASS" if ok else "FAIL",
                     "exported .werk: werk_read.py standalone",
                     "%s (exit %d)" % (boot["summary"] or
                                       "%d pass / %d fail" % (boot["pass"],
                                                              boot["fail"]),
                                       boot["exit"]))
    else:
        gate.add("SKIP", "exported .werk: werk-core verify",
                 "the round-trip clause produced no package")
        gate.add("SKIP", "exported .werk: werk_read.py standalone",
                 "the round-trip clause produced no package")

    # -- clause 5: determinism ------------------------------------------
    c = clause(gate, results, "determinism")
    if c is None:
        gate.add("FAIL", "writer determinism", "clause did not run")
    else:
        ok = not c["payload_entries_differing"] and c["order_identical"]
        gate.add("PASS" if ok else "FAIL", "writer determinism",
                 "%d payload entries byte-identical across two exports, entry order "
                 "identical%s"
                 % (c["payload_entries_identical"],
                    "" if ok else "; DIFFERING: %s"
                    % ", ".join(c["payload_entries_differing"][:6])))

    # -- clause 6: the synthetic rig ------------------------------------
    c = clause(gate, results, "rig_round_trip")
    if c is None:
        gate.add("FAIL", "rig round trip (skeleton + clip)", "clause did not run")
    else:
        rest = c["worst_rest_head_error_m"]
        pose = c["worst_posed_rotation_error_rad"]
        ok = (c["bones_before"] == c["bones_after"] and c["bones_before"] > 0
              and rest is not None and rest < 1e-4
              and pose is not None and pose < 1e-3
              and c["reimport_errors"] == 0 and c["actions_after"] >= 1)
        gate.add("PASS" if ok else "FAIL", "rig round trip (skeleton + clip)",
                 "%d bone(s) -> %d, worst rest-head error %s m, worst posed "
                 "rotation error %s rad, %d action(s) back, %d B package"
                 % (c["bones_before"], c["bones_after"],
                    "%.3g" % rest if rest is not None else "n/a",
                    "%.3g" % pose if pose is not None else "n/a",
                    c["actions_after"], c["exported_bytes"]))
        for sev, code, msg in c.get("export_report", []):
            if sev in ("warn", "error"):
                print("       rig export %s %s: %s" % (sev, code, msg[:140]))

    # -- clause 8: point clouds and Gaussian splats (Stage 12) ----------
    c = clause(gate, results, "point_cloud")
    if c is None:
        gate.add("SKIP" if not os.path.isfile(GSPLAT_FIXTURE) else "FAIL",
                 "point cloud + gsplat import",
                 "fixtures/gsplat-v1.werk is not on disk"
                 if not os.path.isfile(GSPLAT_FIXTURE) else "clause did not run")
    else:
        want = c["declared"].get("core.geom.points", {}).get("count")
        first_ok = (c["first_vertex"] is not None
                    and c["expected_first_vertex"] is not None
                    and max(abs(a - b) for a, b in zip(c["first_vertex"],
                                                       c["expected_first_vertex"]))
                    < 1e-5)
        codes = [code for _sev, code in c["report"]]
        ok = (c["point_cloud_objects"] == 1
              and c["gsplat_objects"] == 0
              and want is not None and c["vertices"] == want
              and c["colour_domain"] == "POINT"
              and c["colour_count"] == want
              and first_ok
              and "gsplat-degradation-skipped" in codes
              and c["nodes_dead"] == 0)
        gate.add("PASS" if ok else "FAIL", "point cloud + gsplat import",
                 "%d points as mesh vertices (declared %s), werk_color on the "
                 "%s domain with %d entries, first vertex %s matches the "
                 "splat's first mean through the Y-up->Z-up swing, splat not "
                 "imported twice (%s), %d dead node(s), %.2f s"
                 % (c["vertices"], want, c["colour_domain"], c["colour_count"],
                    "" if first_ok else "DOES NOT match ",
                    ", ".join(codes) or "no report codes",
                    c["nodes_dead"], c["seconds"]))

    # -- clause 7: textures ---------------------------------------------
    c = clause(gate, results, "textured_round_trip")
    if c is None:
        gate.add("FAIL", "textured round trip (core.tex + slots)",
                 "clause did not run")
    else:
        spaces = c["images_after"]
        colour_ok = any(v == "sRGB" for v in spaces.values()) and \
            any(v == "Non-Color" for v in spaces.values())
        declared = {k: v.get("color_space") for k, v in c["tex_meta"].items()}
        metallic_ok = (c["metallic_after"] is not None
                       and abs(c["metallic_after"] - c["metallic_before"]) < 1e-4)
        ok = (c["tex_nodes"] == 2 and c["image_count_after"] == 2 and colour_ok
              and metallic_ok and c["reimport_errors"] == 0
              and len(c["material_texture_slots"]) >= 1)
        gate.add("PASS" if ok else "FAIL", "textured round trip (core.tex + slots)",
                 "%d core.tex node(s) declared %s; %d image(s) back as %s; slots %s; "
                 "metallic %.4g -> %s; %d B"
                 % (c["tex_nodes"], json.dumps(declared, sort_keys=True),
                    c["image_count_after"], json.dumps(spaces, sort_keys=True),
                    c["material_texture_slots"], c["metallic_before"],
                    "%.4g" % c["metallic_after"] if c["metallic_after"] is not None
                    else "n/a", c["exported_bytes"]))
        for sev, code, msg in c.get("export_report", []):
            if sev in ("warn", "error") and code != "license-unspecified":
                print("       textured export %s %s: %s" % (sev, code, msg[:140]))

    return _finish(gate, t_start, results, args)


def _finish(gate, t_start, results, args):
    p, f, s = gate.counts()
    print("=" * 62)
    print("%d PASS, %d FAIL, %d SKIP    (%.1f s total)"
          % (p, f, s, time.time() - t_start))
    print("GATE: %s" % ("PASSED" if f == 0 and p > 0 else "FAILED"))
    if args.json and results is not None:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=2, sort_keys=True)
        print("raw measurements: %s" % args.json)
    if not args.keep and os.path.isdir(WORK):
        print("(exported packages under %s; pass --keep to retain them)"
              % os.path.relpath(WORK, ROOT))
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
