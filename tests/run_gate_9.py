#!/usr/bin/env python3
"""run_gate_9.py — Stage 9 gate, MEASURED.

The gate, quoted from briefs/STAGE9-BRIEF.md: "fixture #2 conformant (all
existing gates still green after any spec touches); 2/2 gauntlet agents parse
the envelope payload and can state the image's recipe and disclosure correctly
from the file alone."

This harness measures the first clause. The second is measured by running the
agents, and is recorded in gauntlet/RESULTS.md round 2 — a program cannot
grade it and should not pretend to.

Nothing here asserts a number it did not observe. Every check prints what it
saw. The two that matter most are 5 and 6: the envelope is not merely parsed,
its declared arithmetic is checked and its vector is RECOMPUTED from the source
image, because `epistemic: "measured"` is a claim and this is the measurement.

    python tests/run_gate_9.py [--rebuild]

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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# S8-1..S8-3: a gate's numbers are measurements of ONE fixture build, so the
# build is pinned against fixtures/fixtures.json before anything is measured.
# A rebuild then fails here with both hashes in the message, instead of the
# gate going on printing PASS about a different file.
sys.path.insert(0, os.path.join(ROOT, "tests"))
from fixture_pin import pin as _pin_fixture           # noqa: E402

FIX = os.path.join(ROOT, "fixtures")
IMAGE_WERK = os.path.join(FIX, "ista-varun-v1.werk")
WORK = os.path.join(ROOT, "core", "target", "gate-9")

RESULTS = []


def record(name, status, detail=""):
    RESULTS.append((name, status, detail))
    print("[%s] %-40s %s" % (status, name, detail))


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


# --- a store-mode zip reader, so the container checks measure the CONTAINER --
def zip_entries(path):
    """(name, local_header_offset, data_offset, size) in physical order."""
    with open(path, "rb") as fh:
        d = fh.read()
    n = len(d)
    eocd = -1
    for i in range(n - 22, max(0, n - 22 - 65535) - 1, -1):
        if d[i:i + 4] == b"PK\x05\x06":
            if i + 22 + struct.unpack_from("<H", d, i + 20)[0] == n:
                eocd = i
                break
    if eocd < 0:
        raise ValueError("no EOCD")
    count = struct.unpack_from("<H", d, eocd + 10)[0]
    p = struct.unpack_from("<I", d, eocd + 16)[0]
    out = []
    for _ in range(count):
        nlen = struct.unpack_from("<H", d, p + 28)[0]
        elen = struct.unpack_from("<H", d, p + 30)[0]
        clen = struct.unpack_from("<H", d, p + 32)[0]
        size = struct.unpack_from("<I", d, p + 24)[0]
        lho = struct.unpack_from("<I", d, p + 42)[0]
        name = d[p + 46:p + 46 + nlen].decode("utf-8")
        ln = struct.unpack_from("<H", d, lho + 26)[0]
        le = struct.unpack_from("<H", d, lho + 28)[0]
        out.append((name, lho, lho + 30 + ln + le, size))
        p += 46 + nlen + elen + clen
    out.sort(key=lambda e: e[1])
    return d, out


def mp_decode(buf):
    """The werk MessagePack subset, ENVELOPE.layout.txt section 4."""
    v, off = _mp(buf, 0)
    if off != len(buf):
        raise ValueError("trailing bytes in header")
    return v


def _mp(b, o):
    t = b[o]
    o += 1
    if t <= 0x7F:
        return t, o
    if t >= 0xE0:
        return t - 256, o
    if 0xA0 <= t <= 0xBF:
        n = t & 0x1F
        return b[o:o + n].decode("utf-8"), o + n
    if 0x90 <= t <= 0x9F:
        return _mp_arr(b, o, t & 0x0F)
    if 0x80 <= t <= 0x8F:
        return _mp_map(b, o, t & 0x0F)
    if t == 0xC0:
        return None, o
    if t == 0xC2:
        return False, o
    if t == 0xC3:
        return True, o
    for code, fmt, ln in ((0xCC, ">B", 1), (0xCD, ">H", 2), (0xCE, ">I", 4),
                          (0xCF, ">Q", 8), (0xD0, ">b", 1), (0xD1, ">h", 2),
                          (0xD2, ">i", 4), (0xD3, ">q", 8), (0xCA, ">f", 4),
                          (0xCB, ">d", 8)):
        if t == code:
            return struct.unpack_from(fmt, b, o)[0], o + ln
    if t in (0xD9, 0xDA, 0xDB):
        ln = {0xD9: 1, 0xDA: 2, 0xDB: 4}[t]
        n = int.from_bytes(b[o:o + ln], "big")
        o += ln
        return b[o:o + n].decode("utf-8"), o + n
    if t in (0xDC, 0xDD):
        ln = 2 if t == 0xDC else 4
        n = int.from_bytes(b[o:o + ln], "big")
        return _mp_arr(b, o + ln, n)
    if t in (0xDE, 0xDF):
        ln = 2 if t == 0xDE else 4
        n = int.from_bytes(b[o:o + ln], "big")
        return _mp_map(b, o + ln, n)
    raise ValueError("byte 0x%02x is not in the werk subset" % t)


def _mp_arr(b, o, n):
    out = []
    for _ in range(n):
        v, o = _mp(b, o)
        out.append(v)
    return out, o


def _mp_map(b, o, n):
    out = {}
    for _ in range(n):
        k, o = _mp(b, o)
        v, o = _mp(b, o)
        out[k] = v
    return out, o


DTYPE_SIZE = {"u8": 1, "i8": 1, "u16": 2, "i16": 2, "u32": 4, "i32": 4,
              "u64": 8, "i64": 8, "f32": 4, "f64": 8}


def prod(xs):
    r = 1
    for x in xs:
        r *= x
    return r


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true")
    args = ap.parse_args(argv)

    os.makedirs(WORK, exist_ok=True)
    print("werk Stage 9 gate — conformance fixture #2 (profile image/1)")
    print("repo    : %s" % ROOT)

    # Build werk-core FIRST. bindings/python/werk.py prefers
    # core/target/release/werk.dll, so a stale release build silently tests
    # yesterday's reader against today's fixture — which is exactly how this
    # harness first "found" six dead nodes in a package three other readers
    # called clean.
    rc, out = run(["cargo", "build", "--release"], cwd=os.path.join(ROOT, "core"))
    if rc != 0:
        record("cargo build --release", "FAIL", out.strip()[-300:])
        return 1

    if args.rebuild or not os.path.isfile(IMAGE_WERK):
        rc, out = run([sys.executable,
                       os.path.join(FIX, "build_image_fixture.py")])
        if rc != 0:
            record("build", "FAIL", out.strip()[-400:])
            return 1

    r = _pin_fixture("ista-varun-v1")
    record("fixture pinned: ista-varun-v1", "PASS" if r.ok else "FAIL", r.detail)
    print("fixture : %s" % IMAGE_WERK)
    print("          %d bytes, sha256 %s"
          % (os.path.getsize(IMAGE_WERK), sha256_file(IMAGE_WERK)))
    print()

    sys.path.insert(0, os.path.join(ROOT, "bindings", "python"))
    try:
        import werk as werkpy
    except Exception as e:  # noqa: BLE001
        record("python binding import", "FAIL", repr(e))
        return 1

    # -- 1. werk-core loads it, no errors --------------------------------
    with werkpy.Package.open(IMAGE_WERK) as p:
        nodes = p.nodes
        alive = [n for n in nodes if n.status == "alive"]
        skipped = [n for n in nodes if n.status == "skipped"]
        dead = [n for n in nodes if n.status == "dead"]
        ok = (p.errors == 0 and p.signature_state == "signed-and-valid"
              and len(nodes) == 15 and len(alive) == 14 and not dead
              and [n.node_id for n in skipped] == ["c2pa-export"]
              and p.profile == "image/1")
        record("werk-core loads fixture #2", "PASS" if ok else "FAIL",
               "profile %s, %d nodes (%d alive, %d skipped, %d dead), "
               "signature %s, %d error(s)"
               % (p.profile, len(nodes), len(alive), len(skipped), len(dead),
                  p.signature_state, p.errors))
        manifest = json.loads(p.blob("MANIFEST.json"))

    # -- 2. round-trip byte identity --------------------------------------
    with werkpy.Package.open(IMAGE_WERK) as p:
        out_zip = os.path.join(WORK, "roundtrip.werk")
        p.write_zip(out_zip)
        same = sha256_file(out_zip) == sha256_file(IMAGE_WERK)
        record("round-trip byte identity", "PASS" if same else "FAIL",
               "sha256 identical" if same else "DIFFERS")

    # -- 3. rebuild, at three levels ----------------------------------------
    # "Rebuild" means three different things, and each is reported on its
    # own (Codex review rows G16, G17):
    #   L1 archive reassembly: the whole .werk is byte-identical to the pin,
    #      rebuilt from the inputs the package carries plus named substitutions
    #   L2 computed payloads: every entry the builder computes (not copies)
    #      reproduces from those inputs
    #   L3 original inputs: the builder on the author's <WERK_LAB>/SFNovels tree
    # L1 and L2 run on any machine. The rebuild goes into the work dir, never
    # into fixtures/. The substitutions are named in tests/package_rebuild.py
    # and in the clause detail. L3 SKIPs where the author tree is absent; the
    # public image determinism proof without substitutions is
    # tests/run_gate_cc0_image.py (ruling R3, docs/RULINGS-2026-09-09.md).
    import package_rebuild as pr
    n1 = "rebuild L1: archive reassembly"
    n2 = "rebuild L2: computed payloads reproduce"
    try:
        shipped, _order = pr.read_zip(IMAGE_WERK)
        inputs = set(pr.IMAGE_INPUTS) | set(
            nm for nm in shipped
            if nm.startswith("spec/") or nm.startswith("loaders/"))
        bad = pr.check_declared(shipped, inputs)
        if bad:
            for nm in (n1, n2):
                record(nm, "FAIL", "packaged inputs do not match the manifest: "
                       + "; ".join(bad[:5]))
        else:
            rb = os.path.join(WORK, "rebuild")
            root = os.path.join(rb, "root")
            src = os.path.join(rb, "src")
            out = os.path.join(rb, "out")
            shutil.rmtree(out, ignore_errors=True)
            pr.make_overlay(ROOT, shipped, root)
            pr.image_source_tree(shipped, src)
            ev_path = os.path.join(rb, "pipeline-source.txt")
            with open(ev_path, "wb") as fh:
                fh.write(shipped[pr.IMAGE_EVIDENCE])
            # The preview PNGs are encoded by the builder's own deterministic
            # encoder (pipeline/det_png.py), not by whichever zlib Pillow's
            # wheel links, so one attempt is the whole question (release
            # finding N3: the pinned streams used to be Pillow's, zlib-ng on
            # Windows and stock zlib on Linux, and this clause failed on Linux).
            zdesc = "PNG streams by pipeline/det_png.py (no zlib deflate)"
            pin_sha = sha256_file(IMAGE_WERK)
            attempts = [("builder", [])]
            matched = False
            for label, extra in attempts:
                out_a = out + "-" + label
                shutil.rmtree(out_a, ignore_errors=True)
                rc, log = run([sys.executable,
                               os.path.join(ROOT, "tests", "package_rebuild.py"),
                               "image", root, src, out_a, ev_path] + extra)
                rebuilt_path = os.path.join(out_a, "ista-varun-v1.werk")
                matched = (rc == 0 and os.path.isfile(rebuilt_path)
                           and sha256_file(rebuilt_path) == pin_sha)
                if matched:
                    break
            if not matched:
                zdesc += "; the rebuild does not reproduce the pin"
            if rc != 0 or not os.path.isfile(rebuilt_path):
                for nm in (n1, n2):
                    record(nm, "FAIL", "builder exit %d: %s"
                           % (rc, log.strip()[-200:]))
            else:
                again, _o = pr.read_zip(rebuilt_path)
                pngs = [nm for nm in shipped if nm.startswith("image/")
                        and nm.endswith(".png") and nm not in inputs]
                c = pr.compare(shipped, again, inputs, png_by_pixels=pngs)
                subs = pr.IMAGE_SUBSTITUTIONS
                measured = {
                    "entries_total": c["total"],
                    "entries_identical": c["identical"],
                    "entries_differ": c["differ"],
                    "computed": len(c["computed"]),
                    "png_scanline_only": c["png_scanline_only"],
                    "zlib": zdesc}
                print("          rebuild: %s" % json.dumps(measured))
                whole = sha256_file(rebuilt_path)
                pin = sha256_file(IMAGE_WERK)
                d1 = ("%s vs pin %s; %d/%d entries identical; %s; "
                      "substitutions: %s"
                      % (whole[:16], pin[:16], c["identical"], c["total"],
                         zdesc, " | ".join(subs)))
                if whole == pin:
                    record(n1, "PASS", d1)
                elif c["json_float_only"] and set(c["differ"]) <= (
                        {"MANIFEST.json", "SIGNATURE.json"}
                        | set(c["json_float_only"])):
                    record(n1, "SKIP", "byte identity depends on this host's "
                           "maths library: %s differ only in the last digits "
                           "of floats (largest relative difference %.1e), "
                           "plus the manifest and signature that hash them; "
                           "%s" % (", ".join(c["json_float_only"]),
                                   c["json_max_rel_diff"], d1))
                else:
                    record(n1, "FAIL", "differ: %s; %s"
                           % (", ".join(c["differ"]), d1))
                d2 = ("%d computed entries: %d byte-identical, %d with "
                      "identical chunks and scanlines but a different deflate "
                      "stream (%s); %d input entries taken from the package "
                      "(%d spec/ and loaders/ files, %s); %d JSON entries "
                      "equal within a relative %.0e (%s)"
                      % (len(c["computed"]),
                         len(c["computed"]) - len(c["computed_bad"])
                         - len(c["png_scanline_only"])
                         - len(c["json_float_only"]),
                         len(c["png_scanline_only"]),
                         ", ".join(c["png_scanline_only"]) or "none",
                         len(inputs), len(inputs) - len(pr.IMAGE_INPUTS),
                         ", ".join(pr.IMAGE_INPUTS),
                         len(c["json_float_only"]), pr.JSON_REL_TOL,
                         ", ".join(c["json_float_only"]) or "none"))
                if c["computed_bad"] or c["inputs_bad"]:
                    record(n2, "FAIL", "differ: %s; %s"
                           % (", ".join(c["computed_bad"] + c["inputs_bad"]),
                              d2))
                else:
                    record(n2, "PASS", d2 + "; recipe/recipe.json and "
                           "MANIFEST.json carry the copied evidence's hash, "
                           "so they confirm the copy, not its generation")
    except Exception as e:  # noqa: BLE001
        for nm in (n1, n2):
            record(nm, "FAIL", repr(e))

    # L3: the original inputs. Before this change the clause was named
    # "builder is deterministic (author-lab)".
    n3 = "rebuild L3: original inputs (author-lab)"
    rc, out = run([sys.executable, os.path.join(FIX, "build_image_fixture.py"),
                   "--out", WORK])
    rebuilt = os.path.join(WORK, "ista-varun-v1.werk")
    if rc != 0 or not os.path.isfile(rebuilt):
        record(n3, "SKIP",
               "needs the author's <WERK_LAB>/SFNovels tree: the artifacts.db row and "
               "the four whole producer source files the package carries only "
               "as excerpts plus sha256 (so pipeline-source.txt cannot be "
               "regenerated here). Generating the source image itself (model "
               "output) is outside any rebuild. " + out.strip()[-120:])
    else:
        same = sha256_file(rebuilt) == sha256_file(IMAGE_WERK)
        if same:
            record(n3, "PASS", "rebuilt from the original tree, identical sha256")
        else:
            import package_rebuild as pr
            a, _o = pr.read_zip(IMAGE_WERK)
            b, _o = pr.read_zip(rebuilt)
            differ = sorted(n for n in set(a) | set(b) if a.get(n) != b.get(n))
            record(n3, "FAIL",
                   "a rebuild from the original tree produced different "
                   "bytes; %d/%d entries differ: %s"
                   % (len(differ), len(set(a) | set(b)), ", ".join(differ)))

    # -- 4. the three bootstrap loaders, standalone -----------------------
    loaders = os.path.join(ROOT, "loaders")
    rc, out = run([sys.executable, os.path.join(loaders, "werk_read.py"),
                   IMAGE_WERK, "--verify", "--strict"])
    line = [l for l in out.splitlines() if "verified over" in l]
    record("bootstrap: werk_read.py", "PASS" if rc == 0 else "FAIL",
           line[0].strip() if line else out.strip()[-200:])

    rs_exe = os.path.join(WORK, "werk_read_rs.exe" if os.name == "nt" else "werk_read_rs")
    if shutil.which("rustc"):
        rc, out = run(["rustc", "-O", "--edition", "2021", "-o", rs_exe,
                       os.path.join(loaders, "werk_read.rs")])
        if rc != 0:
            record("bootstrap: werk_read.rs", "FAIL", "rustc: " + out.strip()[-200:])
        else:
            rc, out = run([rs_exe, IMAGE_WERK, "--verify", "--strict"])
            line = [l for l in out.splitlines() if "summary:" in l]
            record("bootstrap: werk_read.rs", "PASS" if rc == 0 else "FAIL",
                   line[0].strip() if line else out.strip()[-160:])
    else:
        record("bootstrap: werk_read.rs", "SKIP", "rustc not on PATH")

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from run_gate_a import build_c_with_msvc  # noqa: E402  (same repo, same job)
    c_exe = os.path.join(WORK, "werk_read_c.exe" if os.name == "nt" else "werk_read_c")
    cc = shutil.which("gcc") or shutil.which("clang")
    built = False
    if cc:
        rc, out = run([cc, "-std=c99", "-O2", "-o", c_exe,
                       os.path.join(loaders, "werk_read.c")], env=compiler_env(cc))
        built = rc == 0
    if not built:
        built = build_c_with_msvc(os.path.join(loaders, "werk_read.c"), c_exe)
    if not built:
        record("bootstrap: werk_read.c", "SKIP", "no C compiler could build it")
    else:
        rc, out = run([c_exe, IMAGE_WERK, "--verify", "--strict"])
        line = [l for l in out.splitlines() if "verify:" in l]
        record("bootstrap: werk_read.c", "PASS" if rc == 0 else "FAIL",
               line[0].strip() if line else out.strip()[-160:])

    # -- 5. the WKEM envelope: every assertion in ENVELOPE §7 --------------
    with werkpy.Package.open(IMAGE_WERK) as p:
        wk = bytes(p.blob("semantics/style-embedding.wkem"))
    problems = []
    magic = wk[0:4]
    version, header_len = struct.unpack_from("<II", wk, 4)
    if magic != b"WKEM":
        problems.append("magic %r" % magic)
    header = mp_decode(wk[12:12 + header_len])
    P = 16 * ((12 + header_len + 15) // 16)
    if header.get("payload_origin") != P:
        problems.append("payload_origin declared %s computed %d"
                        % (header.get("payload_origin"), P))
    if P + header.get("payload_size", -1) != len(wk):
        problems.append("payload_origin + payload_size != file size")
    if header.get("endianness") != "le":
        problems.append("endianness %r" % header.get("endianness"))
    if header.get("kind") != "core.embedding":
        problems.append("kind %r" % header.get("kind"))
    if not header.get("model"):
        problems.append("no model key — a vector whose model is unknown is noise")
    branches = []
    for s in header.get("sections", []):
        esz = DTYPE_SIZE.get(s["dtype"], s["stride"])
        if s["offset"] % 16:
            problems.append("%s: offset not 16-aligned" % s["name"])
        if s["offset"] + s["size"] > len(wk):
            problems.append("%s: runs past the end" % s["name"])
        if s["stride"] == esz:
            branches.append("first")
            if s["size"] != s["stride"] * prod(s["shape"]):
                problems.append("%s: first-branch size arithmetic" % s["name"])
        else:
            branches.append("second")
            if s["stride"] < esz * s["shape"][-1]:
                problems.append("%s: stride < esz*shape[-1]" % s["name"])
            if s["size"] != s["stride"] * prod(s["shape"][:-1]):
                problems.append("%s: second-branch size arithmetic" % s["name"])
    if sorted(branches) != ["first", "second"]:
        problems.append("both consistency-rule branches must be exercised; got %s"
                        % branches)
    record("WKEM envelope: every §7 assertion", "PASS" if not problems else "FAIL",
           ("magic WKEM v%d, header %d B, payload_origin %d, 2 sections "
            "(%s branch each), model %s"
            % (version, header_len, P, "/".join(branches), header.get("model")))
           if not problems else "; ".join(problems))

    # -- 6. the descriptor really is MEASURED ------------------------------
    #    Recompute it from image/source.png and compare against the stored
    #    vector at the tolerance the header itself declares.
    try:
        import io
        from PIL import Image
        sys.path.insert(0, FIX)
        import labhog
        with werkpy.Package.open(IMAGE_WERK) as p:
            src = bytes(p.blob("image/source.png"))
        vec, pal, _ = labhog.descriptor(Image.open(io.BytesIO(src)))
        secs = {s["name"]: s for s in header["sections"]}
        sv = secs["vector"]
        stored = struct.unpack_from("<%df" % sv["shape"][0], wk, sv["offset"])
        tol = header.get("tolerance", 1e-6)
        worst = max(abs(a - b) for a, b in zip(stored, vec))
        sp = secs["palette"]
        stored_pal = struct.unpack_from("<%df" % (sp["shape"][0] * 4), wk, sp["offset"])
        worst_pal = max(abs(a - b) for a, b
                        in zip(stored_pal, [float(x) for x in pal.reshape(-1)]))
        ok = worst <= tol and worst_pal <= tol
        record("descriptor recomputes (epistemic: measured)",
               "PASS" if ok else "FAIL",
               "worst component drift %.3e (vector) / %.3e (palette), declared "
               "tolerance %.0e" % (worst, worst_pal, tol))
    except Exception as e:  # noqa: BLE001
        record("descriptor recomputes (epistemic: measured)", "SKIP", repr(e))

    # -- 7. preview_prefix_bytes recomputes exactly (S-15) -----------------
    raw, entries = zip_entries(IMAGE_WERK)
    tier = manifest["container"]["preview_tier"]

    def in_tier(name):
        return any(name.startswith(t) if t.endswith("/") else name == t
                   for t in tier)

    cursor, prefix = 0, 0
    for name, _lho, _doff, size in entries:
        this = 30 + len(name.encode("utf-8")) + size
        if in_tier(name):
            prefix = cursor + this
        cursor += this
    declared = manifest["container"]["preview_prefix_bytes"]
    record("preview_prefix_bytes recomputes (S-15)",
           "PASS" if prefix == declared else "FAIL",
           "declared %d, recomputed %d (%.2f%% of the archive)"
           % (declared, prefix, 100.0 * declared / os.path.getsize(IMAGE_WERK)))

    # -- 8. entry_order matches physical order under the S-14 rule ---------
    order = manifest["container"]["entry_order"]
    names = [e[0] for e in entries]
    remaining = sorted(names)
    expected = []
    for pat in order:
        picked = [n for n in remaining
                  if (n.startswith(pat) if pat.endswith("/") else n == pat)]
        for n in picked:
            remaining.remove(n)
            expected.append(n)
    leftovers = list(remaining)
    expected += remaining
    exacts_between = [p for p in order
                      if not p.endswith("/") and p.count("/") >= 1]
    # SPEC.md section 1 describes entry_order as listing every bucket in the
    # package. A leftover is an entry no declared element matches: legal,
    # because the order is advisory, and still an inconsistency between the
    # array and the package it describes. A gauntlet reader found exactly one
    # (S-28); this check is why there will not be a second.
    order_ok = expected == names and not leftovers
    record("entry_order two-pass matching (S-14)",
           "PASS" if order_ok else "FAIL",
           "%d entries in the declared order, 0 unlisted; %d exact paths "
           "interleaved between prefixes" % (len(names), len(exacts_between))
           if order_ok else
           ("unlisted by entry_order: %s" % leftovers if leftovers
            else "physical order differs from the rule"))

    # -- 9. the S-18 case is really present --------------------------------
    rec = [n for n in manifest["nodes"] if n["node_id"] == "recipe"][0]
    v1 = {f["path"]: (f["sha256"], f["size"]) for f in rec["versions"][0]["files"]}
    v2 = {f["path"]: (f["sha256"], f["size"]) for f in rec["versions"][1]["files"]}
    shared = sorted(set(v1) & set(v2))
    consistent = all(v1[p] == v2[p] for p in shared)
    record("S-18: one node, two versions, shared file",
           "PASS" if shared and consistent else "FAIL",
           "%d file(s) listed by both versions with identical hash and size: %s"
           % (len(shared), ", ".join(shared)))

    # -- 10. recipe hermeticity: every input medium is IN the package -------
    with werkpy.Package.open(IMAGE_WERK) as p:
        recipe = json.loads(p.blob("recipe/recipe.json"))
    container = {e[0] for e in entries}
    node_paths = {f["path"] for v in rec["versions"] for f in v["files"]}
    missing = []
    checked = 0
    for step in recipe["steps"]:
        for inp in step.get("inputs", []):
            if "path" not in inp:
                continue
            checked += 1
            if inp["path"] not in container:
                missing.append("%s not in container" % inp["path"])
            elif inp["path"] not in node_paths:
                missing.append("%s not in the recipe node's files[]" % inp["path"])
            else:
                with werkpy.Package.open(IMAGE_WERK) as p2:
                    got = hashlib.sha256(bytes(p2.blob(inp["path"]))).hexdigest()
                if got != inp["sha256"]:
                    missing.append("%s hash disagrees with the recipe" % inp["path"])
    for pt in ("positive", "negative"):
        pr = recipe["steps"][0].get("prompt", {}).get(pt)
        if pr:
            checked += 1
            with werkpy.Package.open(IMAGE_WERK) as p2:
                got = hashlib.sha256(bytes(p2.blob(pr["file"]))).hexdigest()
            if got != pr["sha256"]:
                missing.append("%s hash disagrees with the recipe" % pr["file"])
    record("recipe hermeticity (law 1, D-REC-1)",
           "PASS" if not missing else "FAIL",
           "%d referenced file(s): all embedded, all in the node's files[], all "
           "hashes agree; grade %s; %d unrecorded fact(s) named"
           % (checked, recipe["reproducibility"], len(recipe["unrecorded"]))
           if not missing else "; ".join(missing))

    # -- 11. the palette agrees in both spellings (law 9) -------------------
    with werkpy.Package.open(IMAGE_WERK) as p:
        sem = json.loads(p.blob("semantics/semantics.json"))
    sp = {s["name"]: s for s in header["sections"]}["palette"]
    binpal = struct.unpack_from("<%df" % (sp["shape"][0] * 4), wk, sp["offset"])
    diffs = []
    for i, col in enumerate(sem["palette"]["colors"]):
        base = i * 4
        for j in range(3):
            if abs(col["linear_rgb"][j] - binpal[base + j]) > 1e-6:
                diffs.append("colour %d channel %d" % (i, j))
        if abs(col["weight"] - binpal[base + 3]) > 1e-6:
            diffs.append("colour %d weight" % i)
    wsum = sum(c["weight"] for c in sem["palette"]["colors"])
    record("palette: JSON and WKEM agree (law 9)",
           "PASS" if not diffs else "FAIL",
           "%d swatches identical to 1e-6 in both spellings; weights sum to "
           "%.6f (a top-N palette, S-24)" % (len(sem["palette"]["colors"]), wsum)
           if not diffs else "; ".join(diffs))

    # -- 12. the disclosure says what the doctrine requires -----------------
    with werkpy.Package.open(IMAGE_WERK) as p:
        disc = json.loads(p.blob("disclosure/disclosure.json"))
    bad = []
    if disc.get("ai_generated") is not True:
        bad.append("ai_generated is not true")
    if not disc.get("declared_by", {}).get("name"):
        bad.append("no declared_by")
    if disc.get("recipe_node") != "recipe":
        bad.append("recipe_node does not name the recipe")
    ids = {s["id"] for s in disc.get("statements", [])}
    if "no-enforcement" not in ids:
        bad.append("no statement recording that the format enforces nothing")
    dm = {m["id"] for m in disc.get("models", [])}
    rm = {s["model"]["id"] for s in recipe["steps"]}
    if dm != rm:
        bad.append("disclosure models %s != recipe models %s" % (dm, rm))
    record("disclosure agrees with the recipe",
           "PASS" if not bad else "FAIL",
           "ai_generated=%s, scope=%s, models %s, %d statement(s), "
           "training-data status %s"
           % (disc["ai_generated"], disc["generation_scope"], sorted(dm),
              len(disc.get("statements", [])),
              disc["training_data_statement"]["status"])
           if not bad else "; ".join(bad))

    print()
    npass = sum(1 for _, s, _ in RESULTS if s == "PASS")
    nfail = sum(1 for _, s, _ in RESULTS if s == "FAIL")
    nskip = sum(1 for _, s, _ in RESULTS if s == "SKIP")
    print("%d PASS, %d FAIL, %d SKIP" % (npass, nfail, nskip))
    if nskip:
        print("A SKIP is not a PASS. Skipped:")
        for n, s, d in RESULTS:
            if s == "SKIP":
                print("  %s — %s" % (n, d))
    print("STAGE 9 GATE (fixture clause): %s"
          % ("PASSED" if nfail == 0 and nskip == 0 else
             "INCOMPLETE (%d SKIPPED; a skip is not a pass)" % nskip
             if nfail == 0 else "FAILED"))
    print("The gauntlet clause is measured by running the agents; see "
          "gauntlet/RESULTS.md round 2.")
    # Exit non-zero on a skip too, per the docstring's contract.
    return 1 if (nfail or nskip) else 0


if __name__ == "__main__":
    sys.exit(main())
