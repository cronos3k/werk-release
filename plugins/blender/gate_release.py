#!/usr/bin/env python3
"""Release gate for the Blender add-on: every release fixture, in real Blender.

    python gate_release.py [--blender PATH] [--json out.json] [--only KEY ...]

1. The vendored release library (`werk_blender/vendor/werk_single.py`) is
   byte-identical to `libs/python/werk_single.py`, and the add-on's writer
   follows the library's determinism contract (conventions, JSON spelling,
   zip layout) -- measured on an export, not asserted.
2. Every fixture recorded in `fixtures/fixtures.json` (3d-entity/1 and
   image/1) is pinned by size + sha256, then, inside
   `blender -b --factory-startup` with the add-on loaded from THIS folder:
     3d-entity/1: import -> export -> fresh scene -> re-import;
                  counts and order-independent geometry hashes compared.
     image/1:     import as a packed image datablock; packed bytes == the
                  primary payload; pixels == the separately extracted primary
                  file loaded directly; export image/1; re-import; pixels
                  compared again.
3. Every exported package is verified OUTSIDE Blender by the release
   readers: `python -m werk verify --json` (libs), `werkc verify --json`
   (schema-validating), and the three bootstrap loaders of the release repo
   (`loaders/werk_read.py`, `.c`, `.rs`, the latter two compiled here).

Blender runs with BLENDER_USER_{CONFIG,SCRIPTS,DATAFILES,EXTENSIONS} pointed
at `_gate_out/blender-profile/`, so nothing is read from or written to a user
profile, and scratch files go to `_gate_out/scratch/` ($WERK_BLENDER_TMP).
"""

import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
import werk_paths                                     # noqa: E402
import release_verify                                 # noqa: E402

REPO = werk_paths.repo_root()
LIBS = werk_paths.libs_root()
WORK = os.path.join(HERE, "_gate_out", "release")
BIN = os.path.join(HERE, "_bin")
sys.path.insert(0, os.path.join(LIBS, "python"))
import werk as werklib                                # noqa: E402
SPEC_SHA = release_verify.bundle_spec_sha256()


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def blender_env():
    env = dict(os.environ)
    prof = os.path.join(HERE, "_gate_out", "blender-profile")
    for k in ("CONFIG", "SCRIPTS", "DATAFILES", "EXTENSIONS"):
        d = os.path.join(prof, k.lower())
        os.makedirs(d, exist_ok=True)
        env["BLENDER_USER_" + k] = d
    scratch = os.path.join(HERE, "_gate_out", "scratch")
    os.makedirs(scratch, exist_ok=True)
    env["WERK_BLENDER_TMP"] = scratch
    return env


def find_blender(explicit):
    sys.path.insert(0, HERE)
    import test_gate
    return test_gate.find_blender(explicit)


class Gate(object):
    def __init__(self):
        self.rows = []

    def add(self, status, name, detail):
        self.rows.append((status, name, detail))
        print("[%-4s] %-44s %s" % (status, name, detail))
        sys.stdout.flush()

    def counts(self):
        return tuple(sum(1 for s, _, _ in self.rows if s == k)
                     for k in ("PASS", "FAIL", "SKIP", "NOTE"))


def zip_layout(path):
    """[(name, method, flags, extra_len)] from the central directory."""
    with open(path, "rb") as fh:
        data = fh.read()
    eocd = data.rfind(b"PK\x05\x06")
    n, cd_size, cd_off = struct.unpack("<HII", data[eocd + 10:eocd + 20])
    out, p = [], cd_off
    for _ in range(n):
        (_sig, _vm, _vn, flags, method, _t, _d, _crc, _cs, _us, nl, xl, cl
         ) = struct.unpack("<IHHHHHHIIIHHH", data[p:p + 34])
        name = data[p + 46:p + 46 + nl].decode("utf-8")
        out.append((name, method, flags, xl))
        p += 46 + nl + xl + cl
    return out


def library_equivalence(gate, export_path):
    """The add-on keeps its own writer (it emits node types the library's
    helpers do not); this measures that it obeys the library's contract."""
    pkg = werklib.open(export_path)
    m = pkg.manifest
    bundle = json.load(open(os.path.join(LIBS, "python", "werk", "bundle", "bundle.json"),
                            encoding="utf-8"))
    prof = bundle["profiles"]["3d-entity/1"]
    conv_ok = list(m["conventions"].items()) == list(prof["conventions"].items())
    gate.add("PASS" if conv_ok else "FAIL", "writer = library: conventions",
             "exported conventions %s the library's 3d-entity/1 table (%d keys, order "
             "included); conventions_map %s"
             % ("==" if conv_ok else "!=", len(m["conventions"]), m.get("conventions_map")))
    mb = pkg.manifest_bytes
    respelled = werklib.json_pretty(werklib.json_loads(mb))
    ok = respelled == mb
    gate.add("PASS" if ok else "FAIL", "writer = library: JSON spelling",
             "MANIFEST.json (%d B) re-emitted by werk.json_pretty is %s"
             % (len(mb), "byte-identical" if ok else "DIFFERENT (%d B)" % len(respelled)))
    lay = zip_layout(export_path)
    names = [x[0] for x in lay]
    stored = all(x[1] == 0 for x in lay)
    utf8 = all(x[2] & 0x0800 for x in lay)
    noextra = all(x[3] == 0 for x in lay)
    order = werklib.physical_order([n for n in names if n != "MANIFEST.json"],
                                   m["container"]["entry_order"])
    order_ok = names[0] == "MANIFEST.json" and \
        [n for n in order if n != "MANIFEST.json"] == names[1:]
    ok = stored and utf8 and noextra and order_ok
    gate.add("PASS" if ok else "FAIL", "writer = library: zip layout",
             "%d entries: store %s, UTF-8 flag %s, no extra fields %s, entry order "
             "== werk.physical_order %s"
             % (len(lay), stored, utf8, noextra, order_ok))


def bundle_drift():
    """Files in which the library's embedded spec differs from the repo's."""
    src = os.path.join(LIBS, "python", "werk", "bundle")
    diff = []
    for sub in ("spec", "loaders"):
        for dp, _dn, fn in os.walk(os.path.join(src, sub)):
            for f in fn:
                a = os.path.join(dp, f)
                rel = os.path.relpath(a, src)
                b = os.path.join(REPO, rel)
                if not os.path.isfile(b) or sha_file(a) != sha_file(b):
                    diff.append(rel.replace(os.sep, "/"))
    rev = json.load(open(os.path.join(src, "bundle.json"), encoding="utf-8"))["source_rev"]
    return rev, sorted(diff)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--blender")
    ap.add_argument("--json")
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args(argv)
    t_start = time.time()
    gate = Gate()
    print("werk Blender add-on -- release gate")
    print("repo %s\nlibs %s" % (REPO, LIBS))
    print("=" * 70)

    # -- 1. the vendored library -------------------------------------------
    a = os.path.join(LIBS, "python", "werk_single.py")
    b = os.path.join(HERE, "werk_blender", "vendor", "werk_single.py")
    ok = os.path.isfile(b) and sha_file(a) == sha_file(b)
    gate.add("PASS" if ok else "FAIL", "release library vendored byte-identical",
             "werk_blender/vendor/werk_single.py %s libs/python/werk_single.py "
             "(sha256 %s, %d B)" % ("==" if ok else "!=", sha_file(a)[:16],
                                    os.path.getsize(a)))
    rev, drift = bundle_drift()
    gate.add("PASS" if not drift else "NOTE", "library bundle vs release repo spec",
             "bundle source_rev %s, lib %s; %d file(s) differ from the repo: %s"
             % (rev[:7], werklib.LIB_VERSION, len(drift), ", ".join(drift) or "none"))
    gate.add("PASS", "library bundle spec_sha256", SPEC_SHA)

    # -- 2. fixtures ----------------------------------------------------------
    rec = json.load(open(os.path.join(REPO, "fixtures", "fixtures.json"),
                         encoding="utf-8"))["fixtures"]
    if os.path.isdir(WORK):
        shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK)
    fixtures = []
    for key, r in rec.items():
        if args.only and key not in args.only:
            continue
        path = os.path.join(REPO, r["path"].replace("/", os.sep))
        if not os.path.isfile(path):
            gate.add("FAIL", "fixture present: " + key, "%s missing -- run "
                     "tools/fetch_fixtures.py --from-dir <assets>" % r["path"])
            continue
        size, digest = os.path.getsize(path), sha_file(path)
        pinned = size == r["size_bytes"] and digest == r["sha256"]
        gate.add("PASS" if pinned else "FAIL", "fixture pinned: " + key,
                 "%s %d B sha256 %s %s" % (r["path"], size, digest[:16],
                                           "matches fixtures.json" if pinned else "DRIFTED"))
        p = werklib.open(path)
        v = p.verdict()
        fx = {"key": key, "path": path, "profile": v["profile"],
              "lib_verdict": dict(v)}
        if v["profile"] == "image/1":
            nid, ppath, data = p.primary_image()
            ext = os.path.splitext(ppath)[1]
            ref = os.path.join(WORK, key + ".primary" + ext)
            with open(ref, "wb") as fh:
                fh.write(data)
            fx["extracted_primary"] = ref
            fx["primary_sha256"] = hashlib.sha256(data).hexdigest()
        elif v["profile"] != "3d-entity/1":
            gate.add("NOTE", "fixture skipped: " + key, "profile %s" % v["profile"])
            continue
        fixtures.append(fx)

    # -- 3. Blender ------------------------------------------------------------
    blender, how = find_blender(args.blender)
    if blender is None:
        gate.add("SKIP", "Blender", how)
        return finish(gate, t_start, None, args)
    ver = subprocess.run([blender, "-b", "--factory-startup", "--version"],
                         capture_output=True, text=True, env=blender_env()).stdout
    ver = next((l.strip() for l in ver.splitlines() if l.startswith("Blender ")), "?")
    gate.add("PASS", "Blender located", "%s (%s)" % (ver, blender))

    payload = {"addon_parent": HERE, "out_dir": WORK,
               "result": os.path.join(WORK, "result.json"), "fixtures": fixtures}
    ppath = os.path.join(WORK, "payload.json")
    with open(ppath, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1)
    cmd = [blender, "-b", "--factory-startup", "--python",
           os.path.join(HERE, "gate_release_in_blender.py"), "--", ppath]
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, env=blender_env(),
                          timeout=7200)
    with open(os.path.join(WORK, "blender-stdout.txt"), "w", encoding="utf-8") as fh:
        fh.write(proc.stdout or "")
        fh.write("\n--- stderr ---\n")
        fh.write(proc.stderr or "")
    if not os.path.isfile(payload["result"]):
        gate.add("FAIL", "Blender run", "no result; exit %d; tail: %s"
                 % (proc.returncode, (proc.stdout or proc.stderr or "")[-800:]))
        return finish(gate, t_start, None, args)
    results = json.load(open(payload["result"], encoding="utf-8"))
    gate.add("PASS" if proc.returncode == 0 else "FAIL", "Blender run",
             "%d fixture(s) measured in %.1f s, exit %d"
             % (len(results["fixtures"]), time.time() - t0, proc.returncode))

    by_key = {f["key"]: f for f in fixtures}
    equivalence_done = False
    for r in results["fixtures"]:
        key = r["fixture"]
        fx = by_key[key]
        lv = fx["lib_verdict"]
        if "exception" in r:
            gate.add("FAIL", "import: " + key, "exception in Blender: %s"
                     % r["exception"].strip().splitlines()[-1])
            continue
        imp = r["import"]
        damaged = lv["exit"] != 0
        census_ok = (imp["nodes_dead"] == lv["dead"]
                     and imp["signature_library"] == lv["signature"])
        if r["profile"] == "image/1":
            im = r["image"]
            ok = (census_ok and im["packed_sha256"] == fx["primary_sha256"]
                  and im["pixels_sha256"] == r["reference"]["pixels_sha256"])
            gate.add("PASS" if ok else "FAIL", "import image/1: " + key,
                     "%dx%d %s; packed bytes %s primary payload (%s, %d B); pixels "
                     "%s the extracted primary loaded directly; %d dead (lib %d), "
                     "signature %s; %.2f s"
                     % (im["size"][0], im["size"][1], im["colorspace"],
                        "==" if im["packed_sha256"] == fx["primary_sha256"] else "!=",
                        im["payload_path"], im["packed_bytes"],
                        "==" if im["pixels_sha256"] == r["reference"]["pixels_sha256"]
                        else "!=", imp["nodes_dead"], lv["dead"],
                        imp["signature_library"], imp["seconds"]))
        else:
            b = r["before"]
            ok = census_ok and (b["vertices"] > 0 or b["bones"] > 0)
            gate.add("PASS" if ok else "FAIL", "import 3d-entity/1: " + key,
                     "%d nodes (%d alive, %d dead [lib %d], %d skipped), signature %s "
                     "(lib %s); %d mesh obj, %d verts, %d tris, %d mat, %d img, "
                     "%d bones, %d actions%s; %.2f s"
                     % (imp["nodes_total"], imp["nodes_alive"], imp["nodes_dead"],
                        lv["dead"], imp["nodes_skipped"], imp["signature_library"],
                        lv["signature"], b["mesh_objects"], b["vertices"],
                        b["triangles"], b["materials"], b["images"], b["bones"],
                        b["actions"], "; DAMAGED twin" if damaged else "",
                        imp["seconds"]))
        exp = r.get("export", {})
        if "refused" in exp or "path" not in exp:
            gate.add("FAIL", "export verified: " + key, "export refused: %s"
                     % exp.get("refused"))
            gate.add("SKIP", "round trip: " + key, "no export")
            continue
        v = release_verify.verify(exp["path"], BIN)
        ok, txt = release_verify.all_ok(v)
        r["release_verify"] = v
        gate.add("PASS" if ok else "FAIL", "export verified: " + key,
                 "%d B; %s" % (exp["bytes"], txt))
        ok = v.get("spec_sha256") == SPEC_SHA
        gate.add("PASS" if ok else "FAIL", "export spec_sha256 = library bundle: " + key,
                 "%s %s %s" % (v.get("spec_sha256"), "==" if ok else "!=", SPEC_SHA[:16]))
        if r["profile"] == "3d-entity/1" and not equivalence_done and not damaged:
            library_equivalence(gate, exp["path"])
            equivalence_done = True

        uuid_ok = r["reimport"].get("entity_uuid") == r.get("source_uuid")
        if r["profile"] == "image/1":
            ok = (r["reimport"]["pixels_sha256"] == r["image"]["pixels_sha256"]
                  and uuid_ok and r["reimport"]["errors"] == 0)
            gate.add("PASS" if ok else "FAIL", "round trip image/1: " + key,
                     "pixels %s after Blender -> image/1 -> Blender (sha256 %s, "
                     "%s); uuid %s; exported PNG %dx%dx%d"
                     % ("identical" if r["reimport"]["pixels_sha256"] ==
                        r["image"]["pixels_sha256"] else "DIFFERENT",
                        r["image"]["pixels_sha256"][:16], r["image"]["pixels_shape"],
                        "kept" if uuid_ok else "CHANGED", *exp["size"]))
        else:
            b, a = r["before"], r["after"]
            # Asserted: triangle count, distinct positions, distinct (position,
            # UV) corners and the three order-independent hashes, bones.
            # NOT asserted: the raw vertex count. Blender's glTF exporter
            # splits a vertex wherever loop normals differ in the last bits,
            # so it is a property of glTF I/O rather than of the geometry
            # (measured on crate-cc0-*: 4686 -> 4737 with the distinct
            # (position, normal to 1e-3, UV) set unchanged at 4686).
            keys = ("triangles", "unique_positions", "distinct_corners",
                    "positions_sha256", "triangles_sha256", "corners_sha256",
                    "bones", "actions", "materials", "images")
            if b["triangles"] == 0:          # a point cloud: every vertex counts
                keys = keys + ("vertices",)
            diff = [k for k in keys if b[k] != a[k]]
            ok = not diff and uuid_ok and r["reimport"]["nodes_dead"] == 0
            gate.add("PASS" if ok else "FAIL", "round trip 3d-entity/1: " + key,
                     "verts %d->%d, tris %d->%d, corners %d->%d, positions %s->%s, "
                     "triangles %s->%s, corners %s->%s, bones %d->%d, uuid %s%s"
                     % (b["vertices"], a["vertices"], b["triangles"], a["triangles"],
                        b["distinct_corners"], a["distinct_corners"],
                        b["positions_sha256"][:12], a["positions_sha256"][:12],
                        b["triangles_sha256"][:12], a["triangles_sha256"][:12],
                        b["corners_sha256"][:12], a["corners_sha256"][:12],
                        b["bones"], a["bones"], "kept" if uuid_ok else "CHANGED",
                        "; DIFFER: " + ", ".join(diff) if diff else ""))
    return finish(gate, t_start, results, args)


def finish(gate, t_start, results, args):
    p, f, s, n = gate.counts()
    print("=" * 70)
    print("%d PASS, %d FAIL, %d SKIP, %d NOTE    (%.1f s total)"
          % (p, f, s, n, time.time() - t_start))
    print("GATE: %s" % ("PASSED" if f == 0 and p > 0 else "FAILED"))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"rows": gate.rows, "results": results}, fh, indent=1)
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
