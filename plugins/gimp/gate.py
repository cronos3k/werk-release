#!/usr/bin/env python3
"""Gate for the GIMP 3 werk plug-in, run in the real host (gimp-console, batch).

    python gate.py [--gimp PATH] [--template CAPSULE] [--json out.json]

1. Pure-Python checks (no GIMP): the vendored release library is
   byte-identical to libs/python/werk_single.py; the raster-layers/1 decoder
   reproduces the profile's own test vector (spec/examples/raster-layers/
   tiles.example.wkxz -> decoded samples sha256) and the writer reproduces the
   section 7.2 checkpoint (tiles-p0-p0.wkx and surface.wkx sizes + sha256).
2. GIMP runs with GIMP3_DIRECTORY = _gate_out/gimp-profile/ (a fresh profile
   inside this folder; its gimprc puts ./plug-ins on plug-in-path), so the
   plug-in is loaded from THIS folder and nothing touches the user profile.
   For every image/1 fixture of the release repo (fixtures/fixtures.json):
   File>Open through file-werk-load, pixels compared with the primary file
   extracted by the release library and opened by GIMP directly; export
   image/1; re-open; pixels compared again. For each raster-layers/1 capsule
   (--layers, default: the PhotoCraft samples): open, every layer's pixels
   compared with the surface decoded outside GIMP; export raster-layers/1 and
   image/1; re-open; layers compared.
3. Every export is verified OUTSIDE GIMP by the release readers
   (tools/release_verify.py: python -m werk, werkc, loaders .py/.c/.rs).
"""

import argparse
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
import werk_paths                                    # noqa: E402
import release_verify                                # noqa: E402

REPO = werk_paths.repo_root()
LIBS = werk_paths.libs_root()
PLUGIN = os.path.join(HERE, "plug-ins", "file-werk")
WORK = os.path.join(HERE, "_gate_out")
OUT = os.path.join(WORK, "out")
BIN = os.path.join(HERE, "_bin")
sys.path.insert(0, PLUGIN)
import werk_single as werklib                        # noqa: E402
import werk_raster                                   # noqa: E402
SPEC_SHA = release_verify.bundle_spec_sha256()

# ArtCraft raster-layers capsules (not in this repository): $WERK_ARTCRAFT_SAMPLES
DEFAULT_LAYERS = [os.path.join(os.environ.get("WERK_ARTCRAFT_SAMPLES", ""), "photocraft", "simple.werk"),
                  os.path.join(os.environ.get("WERK_ARTCRAFT_SAMPLES", ""), "photocraft", "maximal.werk")]


def sha_file(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


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


def find_gimp(explicit):
    cands = [explicit] if explicit else []
    cands += [os.environ.get("WERK_GIMP_CONSOLE")]
    cands += sorted(glob.glob(r"C:\Program Files\GIMP 3*\bin\gimp-console-3*.exe"))[::-1]
    cands += [shutil.which("gimp-console-3.2"), shutil.which("gimp-console-3.0"),
              shutil.which("gimp-console")]
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return None


def gimp_env(profile):
    env = dict(os.environ)
    env["GIMP3_DIRECTORY"] = profile
    env["WERK_GIMP_TMP"] = os.path.join(WORK, "scratch")
    os.makedirs(env["WERK_GIMP_TMP"], exist_ok=True)
    return env


def pure_checks(gate, template):
    a = os.path.join(LIBS, "python", "werk_single.py")
    b = os.path.join(PLUGIN, "werk_single.py")
    ok = sha_file(a) == sha_file(b)
    gate.add("PASS", "library bundle", "lib %s, bundle source_rev %s, spec_sha256 %s"
             % (werklib.LIB_VERSION, werklib.default_bundle().info["source_rev"][:7], SPEC_SHA))
    gate.add("PASS" if ok else "FAIL", "release library vendored byte-identical",
             "plug-ins/file-werk/werk_single.py %s libs/python/werk_single.py (%s, %d B)"
             % ("==" if ok else "!=", sha_file(a)[:16], os.path.getsize(a)))
    if not template or not os.path.exists(template):
        gate.add("SKIP", "raster-layers decoder: spec test vector", "no template capsule")
        gate.add("SKIP", "raster-layers writer: section 7.2 checkpoint", "no template capsule")
        return
    t = werklib.open(template)
    raw = t.read_file("spec/examples/raster-layers/tiles.example.wkxz")
    env = zlib.decompress(raw)
    _m, _v, h = werklib.read_envelope(env)
    samples = werk_raster._sections(env, h)["samples"]
    dec = werk_raster._undelta(bytes(samples), len(h["channels"]), werk_raster.ESZ[h["sample_type"]])
    want = "9666edb477dd4922aa6f532fd8944cb8ce1abb9188c96664d8794993e6936618"
    got = hashlib.sha256(dec).hexdigest()
    gate.add("PASS" if got == want else "FAIL", "raster-layers decoder: spec test vector",
             "tiles.example.wkxz (planes-delta, zlib) decoded to sha256 %s (%s the value "
             "printed in tiles.example.hex.txt)" % (got[:16], "==" if got == want else "!="))
    px = bytearray()
    for y in range(256):
        for x in range(256):
            px += bytes([x, y, (x + y) % 256, 255])
    idx, tiles, _n = werk_raster.surface_files_rgba8(bytes(px), 256, 256)
    ok = (len(tiles) == 262432 and hashlib.sha256(tiles).hexdigest() ==
          "b87706652c2b888f1c1727fa34e27a1ad08f55e6005205ceb7147fcc1a510fcc"
          and len(idx) == 400 and hashlib.sha256(idx).hexdigest() ==
          "08000f038cf0eae6eef93922bbc3d70280625dea8de6bb2b994f464d5b9c1074")
    gate.add("PASS" if ok else "FAIL", "raster-layers writer: section 7.2 checkpoint",
             "tiles-p0-p0.wkx %d B, surface.wkx %d B, both sha256 %s PROFILE-RASTER-LAYERS.md 7.2"
             % (len(tiles), len(idx), "==" if ok else "!="))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--gimp")
    ap.add_argument("--template", default=os.environ.get("WERK_RASTER_LAYERS_TEMPLATE",
                                                         DEFAULT_LAYERS[0]))
    ap.add_argument("--layers", nargs="*", default=DEFAULT_LAYERS)
    ap.add_argument("--json")
    args = ap.parse_args(argv)
    t_start = time.time()
    gate = Gate()
    print("werk GIMP plug-in -- gate\nrepo %s\nlibs %s" % (REPO, LIBS))
    print("=" * 70)
    pure_checks(gate, args.template)

    if os.path.isdir(WORK):
        shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(OUT)
    profile = os.path.join(WORK, "gimp-profile")
    os.makedirs(profile)
    with open(os.path.join(profile, "gimprc"), "w", encoding="utf-8") as fh:
        fh.write('(plug-in-path "${gimp_dir}/plug-ins;${gimp_plug_in_dir}/plug-ins;%s")\n'
                 % os.path.join(HERE, "plug-ins").replace("\\", "/"))

    # fixtures
    rec = json.load(open(os.path.join(REPO, "fixtures", "fixtures.json"),
                         encoding="utf-8"))["fixtures"]
    fixtures = []
    for key, r in rec.items():
        path = os.path.join(REPO, r["path"].replace("/", os.sep))
        if not os.path.isfile(path):
            continue
        p = werklib.open(path)
        if p.verdict()["profile"] != "image/1":
            continue
        pinned = os.path.getsize(path) == r["size_bytes"] and sha_file(path) == r["sha256"]
        gate.add("PASS" if pinned else "FAIL", "fixture pinned: " + key,
                 "%s %d B %s" % (r["path"], os.path.getsize(path),
                                 "matches fixtures.json" if pinned else "DRIFTED"))
        nid, ppath, data = p.primary_image()
        ref = os.path.join(OUT, key + ".primary" + os.path.splitext(ppath)[1])
        with open(ref, "wb") as fh:
            fh.write(data)
        fixtures.append({"key": key, "path": path, "profile": "image/1",
                         "extracted_primary": ref, "lib_verdict": dict(p.verdict())})
    for lp in args.layers:
        if not os.path.exists(lp):
            gate.add("SKIP", "raster-layers capsule", "%s not on disk" % lp)
            continue
        key = "photocraft-" + os.path.splitext(os.path.basename(lp))[0]
        fixtures.append({"key": key, "path": lp, "profile": "raster-layers/1",
                         "lib_verdict": dict(werklib.open(lp).verdict())})

    gimp = find_gimp(args.gimp)
    if gimp is None:
        gate.add("SKIP", "GIMP", "no gimp-console found (set WERK_GIMP_CONSOLE)")
        return finish(gate, t_start, None, args)
    ver = subprocess.run([gimp, "--version"], capture_output=True, text=True,
                         env=gimp_env(profile)).stdout.strip()
    gate.add("PASS", "GIMP located", "%s (%s)" % (ver, gimp))

    payload = {"plugin_dir": PLUGIN, "out_dir": OUT, "template": args.template or "",
               "result": os.path.join(OUT, "result.json"), "fixtures": fixtures}
    ppath = os.path.join(WORK, "payload.json")
    with open(ppath, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1)
    env = gimp_env(profile)
    env["WERK_GIMP_GATE_PAYLOAD"] = ppath
    script = os.path.join(HERE, "gate_in_gimp.py").replace("\\", "/")
    cmd = [gimp, "-i", "-n", "-d", "-f", "-c", "--batch-interpreter", "python-fu-eval",
           "-b", "exec(open(r'%s').read())" % script, "--quit"]
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=7200)
    with open(os.path.join(WORK, "gimp-console.txt"), "w", encoding="utf-8") as fh:
        fh.write(" ".join(cmd) + "\n\n" + (proc.stdout or "") + "\n--- stderr ---\n"
                 + (proc.stderr or ""))
    if not os.path.isfile(payload["result"]):
        gate.add("FAIL", "GIMP run", "no result; exit %d; tail: %s"
                 % (proc.returncode, (proc.stderr or proc.stdout or "")[-1200:]))
        return finish(gate, t_start, None, args)
    res = json.load(open(payload["result"], encoding="utf-8"))
    plugdef = open(os.path.join(profile, "pluginrc"), encoding="utf-8", errors="replace").read()
    reg = "file-werk.py" in plugdef and HERE.replace("\\", "\\\\") in plugdef
    gate.add("PASS" if reg else "FAIL", "plug-in registered from this folder",
             "pluginrc lists %s\\file-werk.py: %s" % (PLUGIN, reg))
    done = "batch command executed successfully" in (proc.stdout + proc.stderr)
    gate.add("PASS" if done and proc.returncode == 0 else "FAIL", "GIMP run",
             "%s; %d fixture(s) measured in %.1f s, exit %d, batch %s"
             % (res.get("gimp"), len(res["fixtures"]), time.time() - t0, proc.returncode,
                "executed successfully" if done else "DID NOT REPORT SUCCESS"))

    by = {f["key"]: f for f in fixtures}
    for r in res["fixtures"]:
        key = r["key"]
        if "exception" in r:
            gate.add("FAIL", "open: " + key, "exception in GIMP: %s"
                     % r["exception"].strip().splitlines()[-1])
            continue
        if r["profile"] == "image/1":
            o, ref = r["open"], r["reference"]
            ok = o["pixels_sha256"] == ref["pixels_sha256"] and o["size"] == ref["size"]
            gate.add("PASS" if ok else "FAIL", "open image/1: " + key,
                     "%dx%d, %d layer; pixels %s the extracted primary opened directly "
                     "(sha256 %s)" % (o["size"][0], o["size"][1], o["layers"],
                                      "==" if ok else "!=", o["pixels_sha256"][:16]))
            exp = r["export"]
            if not os.path.isfile(exp["path"]):
                gate.add("FAIL", "export verified: " + key, "status %s, no file" % exp["status"])
                continue
            v = release_verify.verify(exp["path"], BIN)
            ok, txt = release_verify.all_ok(v)
            gate.add("PASS" if ok else "FAIL", "export verified: " + key,
                     "%d B; %s" % (v["bytes"], txt))
            ok = v.get("spec_sha256") == SPEC_SHA
            gate.add("PASS" if ok else "FAIL", "export spec_sha256 = library bundle: " + key,
                     "%s %s %s" % (v.get("spec_sha256"), "==" if ok else "!=", SPEC_SHA[:16]))
            ok = r["reopen"]["pixels_sha256"] == o["pixels_sha256"]
            gate.add("PASS" if ok else "FAIL", "re-open image/1: " + key,
                     "pixels %s after GIMP -> image/1 -> GIMP" % ("identical" if ok else "DIFFERENT"))
        else:
            o = r["open"]
            # GIMP makes layer names unique by appending " #N"; that is the
            # only renaming allowed, and each one is listed.
            ok = (o["leaf_layers"] == o["tree_leaves"] and o["names_match_modulo_gimp_suffix"]
                  and o["surfaces_exact"] == o["surfaces_compared"] and o["surfaces_compared"] > 0)
            gate.add("PASS" if ok else "FAIL", "open raster-layers/1: " + key,
                     "%dx%d; %d GIMP layers (%d leaf = %d in the tree), names %s; %d/%d "
                     "decoded surfaces byte-identical in GIMP (native format), %d converted "
                     "to the document precision and not compared; report: %s"
                     % (o["size"][0], o["size"][1], o["layers_total"], o["leaf_layers"],
                        o["tree_leaves"], "match" if o["names_match"] else
                        ("match except GIMP's uniqueness suffix on %d: %s"
                         % (len(o["name_diffs"]), "; ".join("%r->%r" % tuple(d) for d in o["name_diffs"]))
                         if o["names_match_modulo_gimp_suffix"] else "DIFFER: %s" % o["name_diffs"][:8]),
                        o["surfaces_exact"], o["surfaces_compared"],
                        o["surfaces_converted_precision"], ", ".join(o["report_codes"])))
            for tag, ek in (("raster-layers/1", "export_layers"), ("image/1", "export_flat")):
                exp = r.get(ek) or {}
                if not exp.get("path") or not os.path.isfile(exp["path"]):
                    gate.add("FAIL", "export %s verified: %s" % (tag, key),
                             "status %s %s" % (exp.get("status"), exp.get("error")))
                    continue
                v = release_verify.verify(exp["path"], BIN)
                ok, txt = release_verify.all_ok(v)
                gate.add("PASS" if ok else "FAIL", "export %s verified: %s" % (tag, key),
                         "%d B; %s" % (v["bytes"], txt))
                if tag == "image/1":
                    ok = v.get("spec_sha256") == SPEC_SHA
                    gate.add("PASS" if ok else "FAIL",
                             "export spec_sha256 = library bundle: %s (flat)" % key,
                             "%s %s %s" % (v.get("spec_sha256"), "==" if ok else "!=",
                                           SPEC_SHA[:16]))
                else:
                    # the bundle's spec/ plus the profile's own files
                    # (add_spec_file), so by construction not the bundle value
                    gate.add("NOTE", "export spec_sha256: %s (layers)" % key,
                             "%s (bundle spec/ + raster-layers/1 profile files; the "
                             "library verdict's spec_sha256_ok is %s)"
                             % (v.get("spec_sha256"), v["lib"].get("spec_sha256_ok")))
            rl = r.get("reopen_layers")
            if rl:
                # The writer flattens groups to their leaves and writes u8, so
                # the merged picture is asserted only for a group-free u8
                # document; otherwise its difference is reported as a NOTE.
                flat_same = rl["flat_sha256"] == rl["flat_before_sha256"]
                simple = o.get("groups", 0) == 0 and o.get("precision") == "u8-non-linear"
                ok = (rl["leaf_layers"] == o["leaf_layers"] and rl["names_identical"]
                      and rl["layers_identical"] == o["leaf_layers"]
                      and (flat_same or not simple))
                gate.add("PASS" if ok else "FAIL", "re-open raster-layers/1: " + key,
                         "%d/%d layers' RGBA u8 pixels identical, names %s, merged picture %s"
                         % (rl["layers_identical"], rl["leaf_layers"],
                            "identical" if rl["names_identical"] else "DIFFER",
                            "identical" if flat_same else
                            "DIFFERENT (%s)" % ("asserted" if simple else
                                                "not asserted: %d group(s) flattened, "
                                                "precision %s -> u8" % (o.get("groups", 0),
                                                                        o.get("precision")))))
                if not flat_same and not simple:
                    gate.add("NOTE", "merged picture after layers round trip: " + key,
                             "differs, as the stated limits predict (groups not written, "
                             "u8 only)")
            rf = r.get("reopen_flat")
            if rf:
                ok = rf["pixels_sha256"] == rf["flat_before_sha256"]
                gate.add("PASS" if ok else "FAIL", "re-open image/1 (flattened): " + key,
                         "%d layer; pixels %s the merged visible layers before export"
                         % (rf["layers"], "==" if ok else "!="))
    return finish(gate, t_start, res, args)


def finish(gate, t_start, res, args):
    p, f, s, n = gate.counts()
    print("=" * 70)
    print("%d PASS, %d FAIL, %d SKIP, %d NOTE    (%.1f s total)"
          % (p, f, s, n, time.time() - t_start))
    print("GATE: %s" % ("PASSED" if f == 0 and p > 0 else "FAILED"))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"rows": gate.rows, "results": res}, fh, indent=1)
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
