#!/usr/bin/env python3
"""run_gate_12.py — Stage 12 gate, MEASURED: point clouds, Gaussian splats and
embedded tools.

The gate, quoted from briefs/STAGE12-BRIEF.md:

    fixture conformant + pinned in fixtures.json; round-trip byte-identical;
    werk-core 0 errors; all three bootstrap readers verify; the gsplat payload
    REPARSES from the layout's declared offsets (independent decoder in the
    gate, not the writer's code); the DC-band point-cloud degradation path
    produces a valid points node; damaged-variant check; mini-gauntlet: 1 fresh
    agent, file only, must write a loader that extracts positions + colors from
    the gsplat node and states what tool made the file and show its embedded
    source.

Everything except the last clause is measured here. The mini-gauntlet is
measured by running a fresh agent against a copy of the fixture in a neutral
directory with no repository access, and its outcome is recorded in
results/STAGE12-RESULTS.md — a program cannot grade it and should not pretend
to. `--prepare-gauntlet DIR` stages the file for that run.

TWO CLAUSES ARE THE ONES THAT EARN THIS GATE'S KEEP.

  * Clause 6 REGENERATES THE PACKAGE FROM ITSELF. It extracts the two embedded
    `core.tool` sources and the embedded source `.splat`, runs them in a
    neutral directory with nothing from this repository on the path, and
    compares the result against the payload the package ships and against the
    intermediate hash the recipe declares. That is the whole Stage 12 claim —
    "the file carries the code that made it" — turned from a sentence into a
    byte comparison.

  * Clause 4 DECODES THE SPLAT WITH A DECODER WRITTEN IN THIS FILE, from the
    offsets, sizes, strides and shapes the payload's own header declares, and
    never from the writer's arithmetic. A gate that called the writer's reader
    would agree with a broken writer.

    python tests/run_gate_12.py [--rebuild] [--json OUT.json]
                                [--prepare-gauntlet DIR]

Exit 0 only when nothing FAILED and nothing was SKIPPED.
"""

import argparse
import hashlib
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))
from fixture_pin import pin as _pin_fixture               # noqa: E402

FIX = os.path.join(ROOT, "fixtures")
GSPLAT_WERK = os.path.join(FIX, "gsplat-v1.werk")
WORK = os.path.join(ROOT, "core", "target", "gate-12")

#: The other real splat available to the lab: a genuine INRIA-convention binary
#: PLY straight out of a 3D-Gaussian-Splatting exporter, 1 920 000 Gaussians,
#: 107 520 363 bytes. It is NOT shipped — it would be a 110 MB fixture — but it
#: is the only real trainer output on this machine and the ingest path is
#: measured against it here rather than only against the fixture's own source.
BIG_PLY = os.path.join(os.environ.get("WERK_LAB", "<WERK_LAB unset>"), "splat-foley", "data", "generated",
                       "marble-cellar.ply")
SOURCE_SPLAT = os.path.join(os.environ.get("WERK_LAB", "<WERK_LAB unset>"), "splat-foley", "data", "samples",
                            "plush.splat")

SH_C0 = 0.28209479177387814

RESULTS = []
MEASURED = {}


def record(name, status, detail=""):
    RESULTS.append((name, status, detail))
    print("[%s] %-44s %s" % (status, name, detail))


def run(cmd, cwd=None, env=None):
    p = subprocess.run(cmd, cwd=cwd or ROOT, capture_output=True, text=True,
                       env=env)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


# ---------------------------------------------------------------------------
# An INDEPENDENT reader: store-mode zip + the werk MessagePack subset + the
# envelope. Written from spec/MINI-SPECS.md section 5 and
# spec/layouts/ENVELOPE.layout.txt, not from the writer.
# ---------------------------------------------------------------------------

def zip_read(path):
    with open(path, "rb") as fh:
        d = fh.read()
    n = len(d)
    eocd = -1
    for i in range(n - 22, max(0, n - 22 - 65535) - 1, -1):
        if d[i:i + 4] == b"PK\x05\x06" and \
                i + 22 + struct.unpack_from("<H", d, i + 20)[0] == n:
            eocd = i
            break
    if eocd < 0:
        raise ValueError("no EOCD")
    count = struct.unpack_from("<H", d, eocd + 10)[0]
    p = struct.unpack_from("<I", d, eocd + 16)[0]
    out = {}
    order = []
    for _ in range(count):
        method = struct.unpack_from("<H", d, p + 10)[0]
        size = struct.unpack_from("<I", d, p + 24)[0]
        nlen = struct.unpack_from("<H", d, p + 28)[0]
        elen = struct.unpack_from("<H", d, p + 30)[0]
        clen = struct.unpack_from("<H", d, p + 32)[0]
        lho = struct.unpack_from("<I", d, p + 42)[0]
        name = d[p + 46:p + 46 + nlen].decode("utf-8")
        if method != 0:
            raise ValueError("%s is deflated; this gate reads store mode only"
                             % name)
        ln = struct.unpack_from("<H", d, lho + 26)[0]
        le = struct.unpack_from("<H", d, lho + 28)[0]
        start = lho + 30 + ln + le
        out[name] = d[start:start + size]
        order.append(name)
        p += 46 + nlen + elen + clen
    return out, order


def mp_decode(buf):
    v, off = _mp(buf, 0)
    if off != len(buf):
        raise ValueError("trailing bytes after the MessagePack value")
    return v


def _mp(b, o):
    t = b[o]
    o += 1
    if t in (0xC1, 0xC7, 0xC8, 0xC9, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8):
        raise ValueError("format byte 0x%02x is banned in a werk header" % t)
    if t <= 0x7F:
        return t, o
    if t >= 0xE0:
        return t - 256, o
    if 0xA0 <= t <= 0xBF:
        n = t & 0x1F
        return b[o:o + n].decode("utf-8"), o + n
    if 0x90 <= t <= 0x9F:
        return _seq(b, o, t & 0x0F, False)
    if 0x80 <= t <= 0x8F:
        return _seq(b, o, t & 0x0F, True)
    if t == 0xC0:
        return None, o
    if t == 0xC2:
        return False, o
    if t == 0xC3:
        return True, o
    fixed = {0xCC: (">B", 1), 0xCD: (">H", 2), 0xCE: (">I", 4), 0xCF: (">Q", 8),
             0xD0: (">b", 1), 0xD1: (">h", 2), 0xD2: (">i", 4), 0xD3: (">q", 8),
             0xCA: (">f", 4), 0xCB: (">d", 8)}
    if t in fixed:
        f, n = fixed[t]
        return struct.unpack_from(f, b, o)[0], o + n
    if t in (0xD9, 0xDA, 0xDB):
        w = {0xD9: (">B", 1), 0xDA: (">H", 2), 0xDB: (">I", 4)}[t]
        n = struct.unpack_from(w[0], b, o)[0]
        o += w[1]
        return b[o:o + n].decode("utf-8"), o + n
    if t in (0xDC, 0xDD):
        w = {0xDC: (">H", 2), 0xDD: (">I", 4)}[t]
        n = struct.unpack_from(w[0], b, o)[0]
        return _seq(b, o + w[1], n, False)
    if t in (0xDE, 0xDF):
        w = {0xDE: (">H", 2), 0xDF: (">I", 4)}[t]
        n = struct.unpack_from(w[0], b, o)[0]
        return _seq(b, o + w[1], n, True)
    raise ValueError("unknown MessagePack format byte 0x%02x" % t)


def _seq(b, o, n, is_map):
    if is_map:
        d = {}
        for _ in range(n):
            k, o = _mp(b, o)
            v, o = _mp(b, o)
            d[k] = v
        return d, o
    a = []
    for _ in range(n):
        v, o = _mp(b, o)
        a.append(v)
    return a, o


DT = {"u8": ("B", 1), "i8": ("b", 1), "u16": ("<H", 2), "i16": ("<h", 2),
      "u32": ("<I", 4), "i32": ("<i", 4), "u64": ("<Q", 8), "i64": ("<q", 8),
      "f32": ("<f", 4), "f64": ("<d", 8)}


def envelope(blob):
    """ENVELOPE.layout.txt section 7's assertions, every one of them."""
    if len(blob) < 12:
        raise ValueError("shorter than the 12-byte minimum")
    magic = blob[0:4]
    version, header_len = struct.unpack_from("<II", blob, 4)
    if 12 + header_len > len(blob):
        raise ValueError("header_len runs past the end")
    header = mp_decode(blob[12:12 + header_len])
    if header.get("endianness") != "le":
        raise ValueError("endianness is not 'le'")
    P = 16 * ((12 + header_len + 15) // 16)
    if header.get("payload_origin") != P:
        raise ValueError("declared payload_origin %r != computed %d"
                         % (header.get("payload_origin"), P))
    if P + header["payload_size"] != len(blob):
        raise ValueError("payload_origin + payload_size != file size")
    prev = P
    for s in header["sections"]:
        if s["offset"] % 16:
            raise ValueError("section %r is not 16-byte aligned" % s["name"])
        if s["offset"] < prev or s["offset"] - prev > 15:
            raise ValueError("section %r is out of order or leaves a gap"
                             % s["name"])
        if s["offset"] + s["size"] > len(blob):
            raise ValueError("section %r runs past the end" % s["name"])
        esz = DT.get(s["dtype"], (None, s["stride"]))[1]
        shape = s["shape"]
        if s["stride"] == esz:
            want = s["stride"]
            for d in shape:
                want *= d
        else:
            if s["stride"] < esz * shape[-1]:
                raise ValueError("section %r: stride < esz * shape[-1]" % s["name"])
            want = s["stride"]
            for d in shape[:-1]:
                want *= d
        if s["size"] != want:
            raise ValueError("section %r: size %d, consistency rule says %d"
                             % (s["name"], s["size"], want))
        prev = s["offset"] + s["size"]
    last = header["sections"][-1]
    if 16 * ((last["offset"] + last["size"] + 15) // 16) != P + header["payload_size"]:
        raise ValueError("the last section does not end where payload_size says")
    return magic, version, header


def section_rows(blob, sec, first=None):
    fmt, esz = DT[sec["dtype"]]
    shape, stride = sec["shape"], sec["stride"]
    comps = 1 if stride == esz else (shape[-1] if shape else 1)
    rows = shape[0] if shape else 0
    if first is not None:
        rows = min(rows, first)
    out = []
    for i in range(rows):
        base = sec["offset"] + i * stride
        v = [struct.unpack_from(fmt, blob, base + c * esz)[0] for c in range(comps)]
        out.append(v[0] if comps == 1 else v)
    return out


def find_section(header, name):
    for s in header["sections"]:
        if s["name"] == name:
            return s
    return None


# ---------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true",
                    help="rebuild the fixture before measuring")
    ap.add_argument("--json")
    ap.add_argument("--prepare-gauntlet", metavar="DIR",
                    help="copy the fixture to DIR and print the mini-gauntlet "
                         "prompt; the agent gets that path and nothing else")
    args = ap.parse_args(argv)
    t_start = time.time()

    if os.path.isdir(WORK):
        shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK, exist_ok=True)

    if args.rebuild:
        rc, out = run([sys.executable,
                       os.path.join(ROOT, "fixtures", "build_gsplat_fixture.py")])
        record("rebuild fixture", "PASS" if rc == 0 else "FAIL",
               out.strip().splitlines()[-1] if out.strip() else "")

    if args.prepare_gauntlet:
        os.makedirs(args.prepare_gauntlet, exist_ok=True)
        dst = os.path.join(args.prepare_gauntlet, "gsplat-v1.werk")
        shutil.copyfile(GSPLAT_WERK, dst)
        print("staged %s (%d bytes, sha256 %s)"
              % (dst, os.path.getsize(dst), sha256_file(dst)))
        print()
        print(GAUNTLET_PROMPT % dst)
        return 0

    # -- 1. the fixture is the build this gate thinks it is -----------------
    r = _pin_fixture("gsplat-v1")
    record("fixture pinned", "PASS" if r.ok else "FAIL", r.detail)
    if not os.path.isfile(GSPLAT_WERK):
        record("fixture present", "FAIL", "fixtures/gsplat-v1.werk is not on disk")
        return _finish(t_start, args)
    entries, order = zip_read(GSPLAT_WERK)
    manifest = json.loads(entries["MANIFEST.json"])
    MEASURED["fixture_bytes"] = os.path.getsize(GSPLAT_WERK)
    MEASURED["fixture_sha256"] = sha256_file(GSPLAT_WERK)
    MEASURED["zip_entries"] = len(order)
    MEASURED["nodes"] = len(manifest["nodes"])
    record("fixture present", "PASS",
           "%d bytes, %d zip entries, %d nodes, profile %s"
           % (MEASURED["fixture_bytes"], len(order), len(manifest["nodes"]),
              manifest["profile"]))

    # -- 2. werk-core -------------------------------------------------------
    rc, out = run(["cargo", "build", "--release"],
                  cwd=os.path.join(ROOT, "core"))
    if rc != 0:
        record("cargo build --release", "FAIL", out.strip()[-300:])
    else:
        record("cargo build --release", "PASS", "werk.dll + werkc.exe")
        werkc = os.path.join(ROOT, "core", "target", "release",
                             "werkc.exe" if os.name == "nt" else "werkc")
        rc, out = run([werkc, "verify", GSPLAT_WERK])
        errs = [l for l in out.splitlines() if l.startswith("[error]")]
        warns = [l for l in out.splitlines() if l.startswith("[warn]")]
        MEASURED["core_errors"] = len(errs)
        MEASURED["core_warnings"] = len(warns)
        record("werk-core verify", "PASS" if rc == 0 and not errs else "FAIL",
               "%d error(s), %d warning(s), exit %d%s"
               % (len(errs), len(warns), rc,
                  "" if not errs else " :: " + errs[0][:160]))

    # -- 3. the three bootstrap loaders -------------------------------------
    loaders = os.path.join(ROOT, "loaders")
    rc, out = run([sys.executable, os.path.join(loaders, "werk_read.py"),
                   GSPLAT_WERK, "--verify"])
    tail = [l for l in out.splitlines() if "files verified" in l]
    record("bootstrap: werk_read.py", "PASS" if rc == 0 and tail else "FAIL",
           tail[0] if tail else out.strip()[-200:])
    if tail:
        MEASURED["python_loader_files"] = tail[0].strip()

    rs_exe = os.path.join(WORK, "werk_read_rs.exe" if os.name == "nt" else "werk_read_rs")
    if shutil.which("rustc"):
        rc, out = run(["rustc", "-O", "--edition", "2021", "-o", rs_exe,
                       os.path.join(loaders, "werk_read.rs")])
        if rc != 0:
            record("bootstrap: werk_read.rs", "FAIL", "rustc: " + out.strip()[-200:])
        else:
            rc, out = run([rs_exe, GSPLAT_WERK, "--verify"])
            tail = [l for l in out.splitlines() if "verified" in l]
            record("bootstrap: werk_read.rs", "PASS" if rc == 0 else "FAIL",
                   tail[-1].strip() if tail else out.strip()[-160:])
    else:
        record("bootstrap: werk_read.rs", "SKIP", "rustc not on PATH")

    sys.path.insert(0, os.path.join(ROOT, "tests"))
    from run_gate_a import build_c_with_msvc            # noqa: E402
    c_exe = os.path.join(WORK, "werk_read_c.exe" if os.name == "nt" else "werk_read_c")
    built = False
    for cc in ("cc", "gcc", "clang"):
        if shutil.which(cc):
            rc, out = run([cc, "-std=c99", "-O2", "-o", c_exe,
                           os.path.join(loaders, "werk_read.c")])
            built = rc == 0
            if built:
                break
    if not built:
        built = build_c_with_msvc(os.path.join(loaders, "werk_read.c"), c_exe)
    if not built:
        record("bootstrap: werk_read.c", "SKIP", "no C compiler could build it")
    else:
        rc, out = run([c_exe, GSPLAT_WERK, "--verify"])
        tail = [l for l in out.splitlines() if "verified" in l]
        record("bootstrap: werk_read.c", "PASS" if rc == 0 else "FAIL",
               tail[-1].strip() if tail else out.strip()[-160:])

    # -- 4. the splat REPARSES from its own declared offsets ----------------
    #      (this file's decoder, never the writer's)
    gs_path = _payload_path(manifest, "core.geom.gsplat")
    pc_path = _payload_path(manifest, "core.geom.points")
    gs = entries[gs_path]
    pc = entries[pc_path]
    try:
        magic, ver, gh = envelope(gs)
        assert magic == b"WKGS", magic
        n = gh["count"]
        k = gh["sh_coeff_count"]
        assert k == (gh["sh_degree"] + 1) ** 2
        names = [s["name"] for s in gh["sections"]]
        assert names == ["means", "scales", "rotations", "opacities",
                         "sh-dc", "sh-rest"], names
        for nm in ("means", "scales", "rotations", "opacities", "sh-dc"):
            assert find_section(gh, nm)["shape"][0] == n, nm
        rest = find_section(gh, "sh-rest")
        assert rest["shape"] == [n, k - 1, 3], rest["shape"]
        assert gh["quat_order"] == "wxyz" and gh["scale_space"] == "linear"
        assert gh["opacity_space"] == "linear" and gh["length_unit"] == "metre"
        assert gh["sh_coeff_order"] == "coefficient-major"
        MEASURED["gsplat"] = {"count": n, "sh_degree": gh["sh_degree"],
                              "bytes": len(gs),
                              "bytes_per_gaussian": round(len(gs) / n, 4)}
        record("gsplat reparses from declared offsets", "PASS",
               "%d Gaussians, sh_degree %d, 6 sections, %d B (%.2f B/Gaussian)"
               % (n, gh["sh_degree"], len(gs), len(gs) / n))
    except Exception as e:  # noqa: BLE001
        record("gsplat reparses from declared offsets", "FAIL", str(e))
        gh = None

    # 4b. the payload's own numbers are sane, measured over EVERY record.
    if gh:
        try:
            sc = find_section(gh, "scales")
            op = find_section(gh, "opacities")
            ro = find_section(gh, "rotations")
            bad_scale = bad_op = 0
            smin, smax = float("inf"), 0.0
            for i in range(n):
                base = sc["offset"] + i * sc["stride"]
                for c in range(3):
                    v = struct.unpack_from("<f", gs, base + c * 4)[0]
                    if not v > 0.0 or not math.isfinite(v):
                        bad_scale += 1
                    smin = min(smin, v)
                    smax = max(smax, v)
            worst_norm = 0.0
            neg_w = 0
            for i in range(n):
                v = struct.unpack_from("<f", gs, op["offset"] + i * op["stride"])[0]
                if not 0.0 <= v <= 1.0:
                    bad_op += 1
                q = struct.unpack_from("<4f", gs, ro["offset"] + i * ro["stride"])
                worst_norm = max(worst_norm, abs(math.sqrt(sum(x * x for x in q)) - 1.0))
                if q[0] < 0.0:
                    neg_w += 1
            ok = bad_scale == 0 and bad_op == 0 and worst_norm < 1e-6 and neg_w == 0
            MEASURED["gsplat_checks"] = {
                "scale_min_m": smin, "scale_max_m": smax,
                "non_positive_scales": bad_scale, "opacities_out_of_range": bad_op,
                "quat_norm_max_dev": worst_norm, "negative_w": neg_w}
            record("gsplat payload values (all %d)" % n, "PASS" if ok else "FAIL",
                   "scales %.3e..%.6f m, %d non-positive; %d opacities outside "
                   "[0,1]; max |q|-1 %.3e; %d with w<0"
                   % (smin, smax, bad_scale, bad_op, worst_norm, neg_w))
        except Exception as e:  # noqa: BLE001
            record("gsplat payload values", "FAIL", str(e))

    # -- 5. the DC-band degradation is EXACT --------------------------------
    try:
        pmagic, _pv, ph = envelope(pc)
        assert pmagic == b"WKPC", pmagic
        assert ph["count"] == gh["count"]
        fields = ph["fields"]
        assert fields[0]["semantic"] == "position"
        assert len(fields) == len(ph["sections"])
        colf = next(f for f in fields if f["semantic"] == "color")
        assert "color_space" in colf
        # Recompute every point from the SPLAT and compare with the shipped
        # point cloud. This is law 5's validate-or-recompute applied to a
        # preview: the node claims `measured` and this is the measurement.
        means = find_section(gh, "means")
        dc = find_section(gh, "sh-dc")
        psec = find_section(ph, "position")
        csec = find_section(ph, "color")
        pos_mismatch = col_mismatch = 0
        for i in range(gh["count"]):
            a = struct.unpack_from("<3f", gs, means["offset"] + i * means["stride"])
            b = struct.unpack_from("<3f", pc, psec["offset"] + i * psec["stride"])
            if a != b:
                pos_mismatch += 1
            d = struct.unpack_from("<3f", gs, dc["offset"] + i * dc["stride"])
            want = tuple(
                int(round(min(1.0, max(0.0, 0.5 + SH_C0 * v)) * 255.0)) for v in d)
            got = struct.unpack_from("<3B", pc, csec["offset"] + i * csec["stride"])
            if want != got:
                col_mismatch += 1
        ok = pos_mismatch == 0 and col_mismatch == 0
        MEASURED["degradation"] = {"points": ph["count"],
                                   "position_mismatches": pos_mismatch,
                                   "colour_mismatches": col_mismatch,
                                   "bytes": len(pc)}
        record("DC-band degradation is exact", "PASS" if ok else "FAIL",
               "%d points recomputed from `means`+`sh-dc`: %d position and %d "
               "colour mismatches, %d B (%.2f B/point)"
               % (ph["count"], pos_mismatch, col_mismatch, len(pc),
                  len(pc) / ph["count"]))
    except Exception as e:  # noqa: BLE001
        record("DC-band degradation is exact", "FAIL", str(e))

    # -- 6. THE PACKAGE REGENERATES ITSELF FROM ITS EMBEDDED TOOLS ----------
    try:
        neutral = os.path.join(WORK, "selfhost")
        os.makedirs(neutral, exist_ok=True)
        recipe = json.loads(entries["recipe/recipe.json"])
        step1, step2 = recipe["steps"][0], recipe["steps"][1]
        src_ref = step1["inputs"][0]
        inter = step1["intermediates"][0]
        # extract the embedded input and the two embedded tools
        with open(os.path.join(neutral, "source.splat"), "wb") as fh:
            fh.write(entries[src_ref["path"]])
        tool1 = json.loads(entries["tools/splat-to-ply/tool.json"])
        tool2 = json.loads(entries["tools/werk-gsplat/tool.json"])
        for t in (tool1, tool2):
            for f in t["files"]:
                dst = os.path.join(neutral, os.path.basename(f["path"]))
                if not os.path.exists(dst):
                    with open(dst, "wb") as fh:
                        fh.write(entries[f["path"]])
        driver = os.path.join(neutral, "regen.py")
        with open(driver, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(REGEN_DRIVER)
        env = dict(os.environ)
        env["PYTHONPATH"] = neutral            # nothing from this repository
        rc, out = run([sys.executable, driver], cwd=neutral, env=env)
        if rc != 0:
            record("package regenerates itself from its own tools", "FAIL",
                   out.strip()[-400:])
        else:
            got = json.loads(out.strip().splitlines()[-1])
            ply_ok = got["ply_sha256"] == inter["sha256"] and \
                got["ply_size"] == inter["size"]
            wkgs_ok = got["wkgs_sha256"] == sha256_bytes(gs)
            MEASURED["self_regeneration"] = {
                "intermediate_declared": inter["sha256"],
                "intermediate_regenerated": got["ply_sha256"],
                "wkgs_shipped": sha256_bytes(gs),
                "wkgs_regenerated": got["wkgs_sha256"],
                "seconds": got["seconds"]}
            record("package regenerates itself from its own tools",
                   "PASS" if ply_ok and wkgs_ok else "FAIL",
                   "intermediate PLY %s (%d B, recipe declared %s); WKGS %s in "
                   "%.1f s, nothing from this repo on the path"
                   % ("MATCHES" if ply_ok else "DIFFERS", got["ply_size"],
                      inter["sha256"][:12],
                      "byte-identical" if wkgs_ok else "DIFFERS", got["seconds"]))
    except Exception as e:  # noqa: BLE001
        record("package regenerates itself from its own tools", "FAIL", repr(e))

    # -- 7. the embedded tools are honest about themselves ------------------
    try:
        problems = []
        tool_nodes = [n for n in manifest["nodes"] if n["type"] == "core.tool"]
        cfg_nodes = [n for n in manifest["nodes"] if n["type"] == "core.tool.config"]
        for node in tool_nodes:
            ver = node["versions"][node["active"] - 1]
            desc = json.loads(entries[[f["path"] for f in ver["files"]
                                       if f["path"].endswith("tool.json")][0]])
            for f in desc["files"]:
                if f["path"] not in entries:
                    problems.append("%s claims %s, which is not in the package"
                                    % (desc["tool_id"], f["path"]))
                elif sha256_bytes(entries[f["path"]]) != f["sha256"]:
                    problems.append("%s: %s hash disagrees with the payload's "
                                    "own claim" % (desc["tool_id"], f["path"]))
            if desc["entrypoint"] not in [f["path"] for f in desc["files"]]:
                problems.append("%s: entrypoint is not one of its files"
                                % desc["tool_id"])
            if desc["form"] != "source":
                problems.append("%s: form is %r; this fixture carries source only"
                                % (desc["tool_id"], desc["form"]))
        cfg_ids = set()
        for node in cfg_nodes:
            ver = node["versions"][node["active"] - 1]
            cfg = json.loads(entries[ver["files"][0]["path"]])
            cfg_ids.add(node["node_id"])
            if cfg["tool_node"] not in [t["node_id"] for t in tool_nodes]:
                problems.append("config %s points at node %r, which is not a "
                                "core.tool here" % (cfg["config_id"], cfg["tool_node"]))
            if cfg["params_provenance"] not in ("recorded", "reconstructed",
                                                "authored-after"):
                problems.append("config %s has no valid params_provenance"
                                % cfg["config_id"])
        # every recipe step's tool_node and config_node resolve INSIDE the file
        ids = {n["node_id"] for n in manifest["nodes"]}
        for st in recipe["steps"]:
            t = st["tool"]
            if "tool_node" in t and t["tool_node"] not in ids:
                problems.append("step %s names tool_node %r, which is not a node "
                                "here" % (st["step_id"], t["tool_node"]))
            if "config_node" in t and t["config_node"] not in cfg_ids:
                problems.append("step %s names config_node %r, which is not a "
                                "core.tool.config here"
                                % (st["step_id"], t["config_node"]))
            if "tool_node" in t and "source_file" in t:
                desc = json.loads(entries["tools/%s/tool.json"
                                          % t["tool_node"].replace("tool-", "", 1)])
                if desc["entrypoint"] != t["source_file"]:
                    problems.append("step %s: tool_node's entrypoint %r and "
                                    "source_file %r disagree"
                                    % (st["step_id"], desc["entrypoint"],
                                       t["source_file"]))
        MEASURED["tools"] = {"tool_nodes": len(tool_nodes),
                             "config_nodes": len(cfg_nodes),
                             "recipe_steps": len(recipe["steps"]),
                             "problems": problems}
        record("embedded tools resolve inside the file",
               "PASS" if not problems else "FAIL",
               "%d core.tool + %d core.tool.config; every recipe step's "
               "tool_node and config_node resolves; every claimed file hash "
               "matches" % (len(tool_nodes), len(cfg_nodes))
               if not problems else "; ".join(problems[:3]))
    except Exception as e:  # noqa: BLE001
        record("embedded tools resolve inside the file", "FAIL", repr(e))

    # -- 8. round trip: rebuild and compare ---------------------------------
    try:
        rebuilt = os.path.join(WORK, "rebuild")
        os.makedirs(rebuilt, exist_ok=True)
        rc, out = run([sys.executable,
                       os.path.join(ROOT, "fixtures", "build_gsplat_fixture.py"),
                       "--out", rebuilt,
                       "--scratch", os.path.join(WORK, "rebuild-scratch")])
        if rc != 0:
            record("round trip: rebuild is byte-identical", "FAIL",
                   out.strip()[-300:])
        else:
            again = sha256_file(os.path.join(rebuilt, "gsplat-v1.werk"))
            ok = again == MEASURED["fixture_sha256"]
            record("round trip: rebuild is byte-identical",
                   "PASS" if ok else "FAIL",
                   "%s vs shipped %s"
                   % (again[:16], MEASURED["fixture_sha256"][:16]))
    except Exception as e:  # noqa: BLE001
        record("round trip: rebuild is byte-identical", "FAIL", repr(e))

    # -- 9. damaged variant: one flipped byte kills one node, not the file --
    try:
        dmg = os.path.join(WORK, "gsplat-v1-damaged.werk")
        with open(GSPLAT_WERK, "rb") as fh:
            raw = bytearray(fh.read())
        # Flip a byte INSIDE the WKGS payload, found through the container's own
        # central directory rather than by an offset this gate hardcoded.
        off = _entry_data_offset(GSPLAT_WERK, gs_path)
        raw[off + 900] ^= 0xFF          # inside `means`, past the header
        with open(dmg, "wb") as fh:
            fh.write(bytes(raw))
        werkc = os.path.join(ROOT, "core", "target", "release",
                             "werkc.exe" if os.name == "nt" else "werkc")
        rc, out = run([werkc, "verify", dmg])
        rc2, out2 = run([sys.executable, os.path.join(loaders, "werk_read.py"),
                         dmg, "--verify"])
        both = out + out2

        # What law 3 actually promises, clause by clause, so a pass here means
        # the island rule EXECUTED rather than that a program printed a word:
        #   * the corrupt payload is caught by its hash, in both readers;
        #   * exactly ONE node dies, and it is the splat;
        #   * the two nodes with an `enhances` edge into it survive, each
        #     losing exactly one feature and SAYING so;
        #   * every other file still verifies, and the loader's own count drops
        #     by exactly the dead node's one file.
        core_mismatch = [l for l in out.splitlines()
                         if "hash-mismatch" in l and gs_path in l]
        core_dead = [l for l in out.splitlines() if "node-dead" in l]
        loader_mismatch = [l for l in out2.splitlines()
                           if "hash-mismatch" in l and gs_path in l]
        enhances = [l for l in both.splitlines() if "enhances-dead-node" in l]
        alive = [l for l in out2.splitlines() if "files verified" in l]
        n_files = n_nodes = -1
        if alive:
            # "74/74 files verified over 16 resolved node(s)"
            parts = alive[0].replace("/", " ").split()
            n_files, n_nodes = int(parts[0]), int(parts[5])
        clean_nodes = MEASURED["nodes"]
        checks = {
            "werk-core exit 1": rc == 1,
            "werk-core names the corrupt path": len(core_mismatch) == 1,
            "exactly one node dead": len(core_dead) == 1 and "gsplat" in core_dead[0],
            "loader names the same mismatch": len(loader_mismatch) == 1,
            "two enhances edges degraded and reported": len(enhances) == 4,
            "loader still verifies every surviving file":
                n_files > 0 and n_nodes == clean_nodes - 1,
        }
        ok = all(checks.values())
        MEASURED["damaged"] = {
            "core_exit": rc, "core_dead_nodes": len(core_dead),
            "enhances_degraded": len(enhances) // 2,
            "loader_files_verified": n_files, "loader_nodes_resolved": n_nodes,
            "checks": {k: bool(v) for k, v in checks.items()}}
        record("damaged variant: one node dies, the rest load",
               "PASS" if ok else "FAIL",
               "werk-core exit %d, 1 hash-mismatch on %s, 1 dead node; both "
               "readers agree; %d enhances edges degraded and reported; "
               "werk_read.py still verifies %d/%d files over %d of %d nodes%s"
               % (rc, gs_path, len(enhances) // 2, n_files, n_files, n_nodes,
                  clean_nodes,
                  "" if ok else " :: FAILED " +
                  ", ".join(k for k, v in checks.items() if not v)))
    except Exception as e:  # noqa: BLE001
        record("damaged variant: one node dies, the rest load", "FAIL", repr(e))

    # -- 10. the INRIA PLY ingest on REAL trainer output --------------------
    if os.path.isfile(BIG_PLY):
        try:
            sys.path.insert(0, ROOT)
            from pipeline import p_gsplat as PG          # noqa: E402
            t0 = time.time()
            blob, st, _arrays = PG.ingest(BIG_PLY)
            dt = time.time() - t0
            envelope(blob)      # this file's decoder, on a 107 MB payload
            MEASURED["big_ply"] = {"path": BIG_PLY, "count": st["count"],
                                   "seconds": round(dt, 2),
                                   "bytes": st["bytes"],
                                   "opacity_exactly_one": st["opacity_exactly_one"],
                                   "quat_order_evidence": st["quat_order_evidence"]}
            record("INRIA PLY ingest, real trainer output", "PASS",
                   "%d Gaussians from a %d B binary PLY in %.1f s -> %d B WKGS "
                   "that reparses; %d opacities are exactly 1.0 (D-GS-5's case, "
                   "measured)"
                   % (st["count"], os.path.getsize(BIG_PLY), dt, st["bytes"],
                      st["opacity_exactly_one"]))
        except Exception as e:  # noqa: BLE001
            record("INRIA PLY ingest, real trainer output", "FAIL", repr(e))
    else:
        record("INRIA PLY ingest, real trainer output", "SKIP",
               "%s is not on this machine" % BIG_PLY)

    # -- 11. ascii PLY, xyzw reorder, and sh_degree 3 -----------------------
    try:
        sys.path.insert(0, ROOT)
        from pipeline import p_gsplat as PG              # noqa: E402
        from pipeline import ply as PLY                  # noqa: E402
        import numpy as np                               # noqa: E402
        rng = np.random.RandomState(20260808)
        m = 32
        k = 16                                            # degree 3
        cols = [("x", rng.randn(m)), ("y", rng.randn(m)), ("z", rng.randn(m)),
                ("nx", np.zeros(m)), ("ny", np.zeros(m)), ("nz", np.zeros(m)),
                ("f_dc_0", rng.randn(m)), ("f_dc_1", rng.randn(m)),
                ("f_dc_2", rng.randn(m))]
        rest = rng.randn(m, 3, k - 1)
        for ch in range(3):
            for c in range(k - 1):
                cols.append(("f_rest_%d" % (ch * (k - 1) + c), rest[:, ch, c]))
        cols += [("opacity", rng.randn(m)),
                 ("scale_0", rng.randn(m)), ("scale_1", rng.randn(m)),
                 ("scale_2", rng.randn(m))]
        q = rng.randn(m, 4)
        q /= np.linalg.norm(q, axis=1)[:, None]
        # write XYZW on purpose: the reorder is the thing under test
        cols += [("rot_0", q[:, 1]), ("rot_1", q[:, 2]),
                 ("rot_2", q[:, 3]), ("rot_3", q[:, 0])]
        ascii_path = os.path.join(WORK, "deg3.ply")
        lines = ["ply", "format ascii 1.0", "element vertex %d" % m]
        lines += ["property float %s" % c[0] for c in cols]
        lines.append("end_header")
        for i in range(m):
            lines.append(" ".join(repr(float(np.float32(c[1][i]))) for c in cols))
        with open(ascii_path, "w", encoding="ascii", newline="\n") as fh:
            fh.write("\n".join(lines) + "\n")
        blob, st, arr = PG.ingest(ascii_path, quat_order="xyzw")
        magic, _v, h = envelope(blob)
        assert magic == b"WKGS" and h["sh_degree"] == 3 and h["sh_coeff_count"] == 16
        restsec = find_section(h, "sh-rest")
        assert restsec["shape"] == [m, 15, 3], restsec["shape"]
        # the transpose: sh-rest[i, c-1, ch] must equal f_rest_[ch*(K-1)+(c-1)]
        bad = 0
        for i in range(m):
            for c in range(1, k):
                base = restsec["offset"] + (i * (k - 1) + (c - 1)) * restsec["stride"]
                got = struct.unpack_from("<3f", blob, base)
                want = tuple(np.float32(rest[i, ch, c - 1]) for ch in range(3))
                if got != want:
                    bad += 1
        # the quaternion reorder: wxyz out of an xyzw source, w >= 0
        rot = find_section(h, "rotations")
        qbad = 0
        for i in range(m):
            got = struct.unpack_from("<4f", blob, rot["offset"] + i * rot["stride"])
            want = q[i] if q[i][0] >= 0 else -q[i]
            if max(abs(float(got[j]) - float(np.float32(want[j]))) for j in range(4)) > 1e-6:
                qbad += 1
        MEASURED["degree3"] = {"gaussians": m, "sh_coeff_count": 16,
                               "transpose_mismatches": bad,
                               "quat_reorder_mismatches": qbad}
        record("ascii PLY, sh_degree 3, xyzw reorder",
               "PASS" if bad == 0 and qbad == 0 else "FAIL",
               "%d Gaussians, 16 coefficients: %d SH transpose and %d "
               "quaternion-reorder mismatches over %d values"
               % (m, bad, qbad, m * 15 * 3 + m * 4))
    except Exception as e:  # noqa: BLE001
        record("ascii PLY, sh_degree 3, xyzw reorder", "FAIL", repr(e))

    # -- 12. every JSON payload validates against its declared schema -------
    try:
        rc, out = run([sys.executable, os.path.join(ROOT, "fixtures",
                                                    "record_fixtures.py"), "--check"])
        line = [l for l in out.splitlines() if "match their record" in l]
        record("fixtures.json record", "PASS" if rc == 0 else "FAIL",
               line[0] if line else out.strip()[-200:])
    except Exception as e:  # noqa: BLE001
        record("fixtures.json record", "FAIL", repr(e))

    # -- 13. the vendored Blender copy is current ---------------------------
    rc, out = run([sys.executable, os.path.join(ROOT, "tools", "blender",
                                                "vendor_spec.py"), "--check"])
    record("Blender vendored spec is current", "PASS" if rc == 0 else "FAIL",
           out.strip().splitlines()[-1] if out.strip() else "")

    return _finish(t_start, args)


def _entry_data_offset(path, want):
    with open(path, "rb") as fh:
        d = fh.read()
    n = len(d)
    for i in range(n - 22, max(0, n - 22 - 65535) - 1, -1):
        if d[i:i + 4] == b"PK\x05\x06" and \
                i + 22 + struct.unpack_from("<H", d, i + 20)[0] == n:
            eocd = i
            break
    count = struct.unpack_from("<H", d, eocd + 10)[0]
    p = struct.unpack_from("<I", d, eocd + 16)[0]
    for _ in range(count):
        nlen = struct.unpack_from("<H", d, p + 28)[0]
        elen = struct.unpack_from("<H", d, p + 30)[0]
        clen = struct.unpack_from("<H", d, p + 32)[0]
        lho = struct.unpack_from("<I", d, p + 42)[0]
        name = d[p + 46:p + 46 + nlen].decode("utf-8")
        if name == want:
            ln = struct.unpack_from("<H", d, lho + 26)[0]
            le = struct.unpack_from("<H", d, lho + 28)[0]
            return lho + 30 + ln + le
        p += 46 + nlen + elen + clen
    raise KeyError(want)


def _payload_path(manifest, ntype):
    for n in manifest["nodes"]:
        if n["type"] == ntype:
            v = n["versions"][n["active"] - 1]
            for f in v["files"]:
                if not f["path"].endswith(".json"):
                    return f["path"]
    raise KeyError(ntype)


def _finish(t_start, args):
    print()
    npass = sum(1 for _, s, _ in RESULTS if s == "PASS")
    nfail = sum(1 for _, s, _ in RESULTS if s == "FAIL")
    nskip = sum(1 for _, s, _ in RESULTS if s == "SKIP")
    print("%d PASS, %d FAIL, %d SKIP    (%.1f s total)"
          % (npass, nfail, nskip, time.time() - t_start))
    if nskip:
        print("A SKIP is not a PASS. Skipped:")
        for n, s, d in RESULTS:
            if s == "SKIP":
                print("  %s — %s" % (n, d))
    print("STAGE 12 GATE (harness clauses): %s"
          % ("PASSED" if nfail == 0 and nskip == 0 else
             "INCOMPLETE (%d SKIPPED; a skip is not a pass)" % nskip
             if nfail == 0 else "FAILED"))
    print("The mini-gauntlet clause is measured by running a fresh agent "
          "against a copy of the fixture and nothing else; see "
          "results/STAGE12-RESULTS.md.")
    if args.json:
        with open(args.json, "w", encoding="utf-8", newline="\n") as fh:
            json.dump({"results": [{"name": n, "status": s, "detail": d}
                                   for n, s, d in RESULTS],
                       "measured": MEASURED,
                       "summary": {"pass": npass, "fail": nfail, "skip": nskip}},
                      fh, indent=2)
            fh.write("\n")
    # Exit non-zero on a skip too, per the docstring's contract.
    return 1 if (nfail or nskip) else 0


#: Runs INSIDE the neutral directory, with only the package's own extracted
#: files on PYTHONPATH. If this script needs anything from this repository, the
#: package did not really carry its tools.
REGEN_DRIVER = '''import hashlib, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
t0 = time.time()
import splat_to_ply
import p_gsplat
splat_to_ply.convert("source.splat", "regen.ply")
with open("regen.ply", "rb") as fh:
    ply = fh.read()
blob, stats, _ = p_gsplat.ingest("regen.ply", quat_order="wxyz")
print(json.dumps({"ply_sha256": hashlib.sha256(ply).hexdigest(),
                  "ply_size": len(ply),
                  "wkgs_sha256": hashlib.sha256(blob).hexdigest(),
                  "wkgs_size": len(blob),
                  "count": stats["count"],
                  "seconds": round(time.time() - t0, 2)}))
'''

GAUNTLET_PROMPT = """MINI-GAUNTLET PROMPT (hand this, and the file, to a fresh agent
with NO access to the werk repository):

----------------------------------------------------------------------
You have been given exactly one file: %s

Nothing else. No documentation outside that file, no repository, no
internet. Work only from the file.

Produce:

  1. A working loader, in a language of your choice, that extracts the
     POSITIONS and the COLOURS of the 3D content in this file, and
     prints the first five of each plus the total count.
  2. A plain statement of WHAT TOOL MADE THIS FILE, and SHOW the
     embedded source of that tool -- name it, say where in the file it
     is, and quote enough of it to prove you read it.
  3. A short note on anything the file told you that surprised you, and
     anything you could not work out.

Do not run any code that came out of the file. Read it.
----------------------------------------------------------------------
"""


if __name__ == "__main__":
    sys.exit(main())
