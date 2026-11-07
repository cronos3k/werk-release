#!/usr/bin/env python3
"""run_gate.py — run the ROADMAP Stage 2 gate and PRINT THE MEASUREMENTS.

House rule: nothing advances on assertion. This harness runs every part of the
gate end to end and prints what it observed, so the numbers in HANDOVER.md are
transcribed from a run rather than asserted from memory.

    python tests/run_gate.py [--rebuild-fixture]

Checks, in order:
  1  cargo test                          the Rust crate's own suite
  2  round-trip byte identity            open -> write -> sha256 compare
  3  damage gauntlet                     covered by the crate suite, re-stated
  4  Rust face                           werkc against the fixture
  5  Python face                         bindings/python/werk.py over werk.dll
  6  C++ face                            tests/cpp/smoke.cpp over the same DLL
  7  bootstrap loader werk_read.py       stdlib only
  8  bootstrap loader werk_read.rs       bare rustc, no cargo
  9  bootstrap loader werk_read.c        C99, cc or cl

A step that cannot run because a toolchain is absent is reported SKIP with the
reason. A SKIP is not a PASS and the summary says so.

Exit 0 only when nothing FAILED.
"""

import hashlib
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(os.path.join(__file__, "..")))
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "crate.werk")
FIXTURE_DIR = os.path.join(ROOT, "tests", "fixtures", "crate")
WORK = os.path.join(ROOT, "core", "target", "gate-tmp")

# S8-1..S8-3: a gate's numbers are measurements of ONE fixture build, so the
# build is pinned against fixtures/fixtures.json before anything is measured.
sys.path.insert(0, os.path.join(ROOT, "tests"))
from fixture_pin import pin as _pin_fixture           # noqa: E402


RESULTS = []


def record(name, status, detail=""):
    RESULTS.append((name, status, detail))
    mark = {"PASS": "PASS", "FAIL": "FAIL", "SKIP": "SKIP"}[status]
    print("[%s] %-34s %s" % (mark, name, detail))


def run(cmd, cwd=None, env=None):
    t0 = time.time()
    p = subprocess.run(cmd, cwd=cwd or ROOT, capture_output=True, text=True,
                       env=env, shell=False)
    return p.returncode, (p.stdout or "") + (p.stderr or ""), time.time() - t0


def which(name):
    return shutil.which(name)


def find_cl():
    """MSVC is not on PATH by default; locate it the way splat-foley does."""
    if which("cl"):
        return which("cl"), None
    base = r"C:\Program Files\Microsoft Visual Studio\2022"
    for edition in ("Community", "Professional", "Enterprise", "BuildTools"):
        vcvars = os.path.join(base, edition, r"VC\Auxiliary\Build\vcvars64.bat")
        if os.path.isfile(vcvars):
            return "cl", vcvars
    return None, None


def run_msvc(command, work):
    """cmd.exe mis-parses `call vcvars.bat >nul 2>&1 && cl ...`: the
    redirection and the `&&` interact, and the whole thing returns 1 with no
    output at all. Writing a three-line batch file instead is boring and works.
    Recorded here because the silent-failure mode cost a debugging round."""
    cl, vcvars = find_cl()
    if not cl:
        return 127, "no cl.exe found"
    bat = os.path.join(work, "_msvc.bat")
    lines = ["@echo off"]
    if vcvars:
        lines.append('call "%s" >nul' % vcvars)
    lines.append(command)
    lines.append("exit /b %ERRORLEVEL%")
    eol = chr(13) + chr(10)
    with open(bat, "wb") as fh:
        fh.write((eol.join(lines) + eol).encode("ascii"))
    rc, out, _ = run(["cmd.exe", "/c", bat], cwd=work)
    return rc, out


def dll_path():
    for profile in ("release", "debug"):
        for name in ("werk.dll", "libwerk.so", "libwerk.dylib"):
            p = os.path.join(ROOT, "core", "target", profile, name)
            if os.path.isfile(p):
                return p
    return None


def sha256_file(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def main(argv):
    os.makedirs(WORK, exist_ok=True)
    print("werk Stage 2 gate")
    print("repo    : %s" % ROOT)
    print("python  : %s" % sys.version.split()[0])
    print()

    # -- 0. fixture ----------------------------------------------------
    if "--rebuild-fixture" in argv or not os.path.isfile(FIXTURE):
        rc, out, _ = run(["cargo", "run", "-q", "--bin", "werkc", "--",
                          "build-fixture", os.path.join(ROOT, "tests", "fixtures")],
                         cwd=os.path.join(ROOT, "core"))
        if rc != 0:
            record("fixture build", "FAIL", out.strip().splitlines()[-1:] or "")
            return 1
    r = _pin_fixture("crate-synthetic")
    record("fixture pinned: crate-synthetic", "PASS" if r.ok else "FAIL", r.detail)
    size = os.path.getsize(FIXTURE)
    digest = sha256_file(FIXTURE)
    print("fixture : %s" % FIXTURE)
    print("          %d bytes, sha256 %s" % (size, digest))
    print()

    # -- 1. cargo test --------------------------------------------------
    if which("cargo"):
        rc, out, secs = run(["cargo", "test", "--quiet"], cwd=os.path.join(ROOT, "core"))
        passed = sum(int(l.split()[3]) for l in out.splitlines()
                     if l.startswith("test result: ok."))
        failed = sum(int(l.split()[5]) for l in out.splitlines()
                     if l.startswith("test result:"))
        record("cargo test", "PASS" if rc == 0 else "FAIL",
               "%d passed, %d failed, %.1fs" % (passed, failed, secs))
        if rc != 0:
            print(out[-3000:])
    else:
        record("cargo test", "SKIP", "cargo not on PATH")

    # -- 2. round-trip byte identity (measured here too, independently) --
    dll = dll_path()
    sys.path.insert(0, os.path.join(ROOT, "bindings", "python"))
    try:
        import werk as werkpy
    except Exception as e:  # noqa: BLE001
        record("python binding import", "FAIL", str(e))
        werkpy = None

    if werkpy and dll:
        try:
            with werkpy.Package.open(FIXTURE) as p:
                out_zip = os.path.join(WORK, "roundtrip.werk")
                p.write_zip(out_zip)
                same = sha256_file(out_zip) == digest
                record("round-trip byte identity", "PASS" if same else "FAIL",
                       "sha256 %s" % ("identical" if same else
                                      "DIFFERS: %s" % sha256_file(out_zip)))
                # and from the directory form
                with werkpy.Package.open(FIXTURE_DIR) as d:
                    out2 = os.path.join(WORK, "fromdir.werk")
                    d.write_zip(out2)
                    same2 = sha256_file(out2) == digest
                    record("round-trip from directory form",
                           "PASS" if same2 else "FAIL",
                           "dir -> zip reproduces the container"
                           if same2 else "DIFFERS")
        except Exception as e:  # noqa: BLE001
            record("round-trip byte identity", "FAIL", repr(e))
    else:
        record("round-trip byte identity", "SKIP", "no shared library built")

    # -- 3. damage gauntlet ---------------------------------------------
    if which("cargo"):
        rc, out, _ = run(["cargo", "test", "--quiet", "--test", "conformance",
                          "gate_damage"], cwd=os.path.join(ROOT, "core"))
        n = sum(int(l.split()[3]) for l in out.splitlines()
                if l.startswith("test result: ok."))
        record("damage gauntlet", "PASS" if rc == 0 else "FAIL",
               "%d damage scenarios" % n)
    else:
        record("damage gauntlet", "SKIP", "cargo not on PATH")

    # -- 4. Rust face ----------------------------------------------------
    if which("cargo"):
        rc, out, _ = run(["cargo", "run", "-q", "--bin", "werkc", "--", "verify", FIXTURE],
                         cwd=os.path.join(ROOT, "core"))
        record("face: Rust (werkc)", "PASS" if rc == 0 else "FAIL",
               out.strip().splitlines()[-1] if out.strip() else "")
    else:
        record("face: Rust (werkc)", "SKIP", "cargo not on PATH")

    # -- 5. Python face --------------------------------------------------
    if werkpy and dll:
        try:
            with werkpy.Package.open(FIXTURE) as p:
                nodes = p.nodes
                alive = sum(1 for n in nodes if n.status == "alive")
                skipped = sum(1 for n in nodes if n.status == "skipped")
                ok = (p.errors == 0 and p.signature_state == "signed-and-valid"
                      and len(nodes) > 10)
                record("face: Python (ctypes)", "PASS" if ok else "FAIL",
                       "%d nodes (%d alive, %d skipped), signature %s, %d error(s)"
                       % (len(nodes), alive, skipped, p.signature_state, p.errors))
        except Exception as e:  # noqa: BLE001
            record("face: Python (ctypes)", "FAIL", repr(e))
    else:
        record("face: Python (ctypes)", "SKIP", "no shared library built")

    # -- 6. C++ face -----------------------------------------------------
    cpp_dir = os.path.join(ROOT, "tests", "cpp")
    lib_import = os.path.join(ROOT, "core", "target", "release", "werk.dll.lib")
    if not dll:
        record("face: C++ (header + DLL)", "SKIP", "no shared library built")
    else:
        cl, vcvars = find_cl()
        built = None
        if cl and os.name == "nt" and os.path.isfile(lib_import):
            exe = os.path.join(WORK, "smoke_msvc.exe")
            # Run from WORK so cl drops its .obj there; /Fo with a trailing
            # backslash inside quotes is a cmd.exe quoting trap.
            cmd = ('cl /nologo /EHsc /std:c++17 /W3 /I"%s" "%s" "%s" /Fe:"%s"'
                   % (os.path.join(ROOT, "core", "include"),
                      os.path.join(cpp_dir, "smoke.cpp"), lib_import, exe))
            rc, out = run_msvc(cmd, WORK)
            if rc == 0:
                built = ("MSVC", exe)
            else:
                record("face: C++ compile (MSVC)", "FAIL", out.strip()[-300:])
        if built is None and which("g++"):
            exe = os.path.join(WORK, "smoke_gcc.exe" if os.name == "nt" else "smoke_gcc")
            rc, out, _ = run(["g++", "-std=c++17",
                              "-I" + os.path.join(ROOT, "core", "include"),
                              os.path.join(cpp_dir, "smoke.cpp"), dll, "-o", exe])
            if rc == 0:
                built = ("g++", exe)
            else:
                record("face: C++ compile (g++)", "FAIL", out.strip()[-300:])
        if built is None:
            record("face: C++ (header + DLL)", "SKIP",
                   "no C++ compiler could produce the smoke test")
        else:
            comp, exe = built
            shutil.copy(dll, os.path.join(WORK, os.path.basename(dll)))
            rc, out, _ = run([exe, FIXTURE], cwd=WORK)
            last = [l for l in out.strip().splitlines() if l.strip()][-1:]
            record("face: C++ (%s)" % comp, "PASS" if rc == 0 else "FAIL",
                   last[0] if last else "")

    # -- 7/8/9. the embedded bootstrap loaders ---------------------------
    loaders = os.path.join(ROOT, "loaders")

    # python
    rc, out, _ = run([sys.executable, os.path.join(loaders, "werk_read.py"), "--selftest"])
    if rc != 0:
        record("bootstrap: werk_read.py", "FAIL", "selftest failed")
    else:
        rc, out, _ = run([sys.executable, os.path.join(loaders, "werk_read.py"),
                          FIXTURE, "--verify", "--strict"])
        line = [l for l in out.splitlines() if "verified over" in l]
        record("bootstrap: werk_read.py", "PASS" if rc == 0 else "FAIL",
               line[0].strip() if line else out.strip()[-160:])

    # rust, bare rustc
    if which("rustc"):
        exe = os.path.join(WORK, "werk_read_rs.exe" if os.name == "nt" else "werk_read_rs")
        rc, out, _ = run(["rustc", "-O", "--edition", "2021", "-o", exe,
                          os.path.join(loaders, "werk_read.rs")])
        if rc != 0:
            record("bootstrap: werk_read.rs", "FAIL", "rustc: " + out.strip()[-200:])
        else:
            rc, out, _ = run([exe, FIXTURE, "--verify", "--strict"])
            line = [l for l in out.splitlines() if "PASS" in l or "verify" in l][-1:]
            record("bootstrap: werk_read.rs", "PASS" if rc == 0 else "FAIL",
                   (line[0].strip() if line else "")[:120])
    else:
        record("bootstrap: werk_read.rs", "SKIP", "rustc not on PATH")

    # c
    cc = which("gcc") or which("clang")
    cl, vcvars = find_cl()
    exe = os.path.join(WORK, "werk_read_c.exe" if os.name == "nt" else "werk_read_c")
    built_c = False
    if cc:
        rc, out, _ = run([cc, "-std=c99", "-O2", "-o", exe,
                          os.path.join(loaders, "werk_read.c")])
        built_c = rc == 0
        if not built_c:
            # A compiler that exits nonzero and says NOTHING has not rejected
            # the source; it has failed to run. (Observed 2026-08-08: this
            # host's mingw gcc cannot compile `int main(void){return 0;}`
            # either — cc1 dies silently.) Reporting that as a source failure
            # would be the harness asserting something it did not measure, so
            # it is a SKIP with the reason and the other compiler is tried.
            if out.strip():
                record("bootstrap: werk_read.c compile", "FAIL", out.strip()[-200:])
            else:
                record("bootstrap: werk_read.c (%s)" % os.path.basename(cc),
                       "SKIP",
                       "%s exited %d with no diagnostics: broken toolchain on "
                       "this host, not a source failure" % (cc, rc))
    if not built_c and cl:
        cmd = 'cl /nologo /O2 /W3 "%s" /Fe:"%s"' % (
            os.path.join(loaders, "werk_read.c"), exe)
        rc, out = run_msvc(cmd, WORK)
        built_c = rc == 0
    if not built_c:
        record("bootstrap: werk_read.c", "SKIP", "no C compiler could build it")
    else:
        rc, out, _ = run([exe, FIXTURE, "--verify", "--strict"])
        line = [l for l in out.splitlines() if "verify:" in l][-1:]
        record("bootstrap: werk_read.c", "PASS" if rc == 0 else "FAIL",
               (line[0].strip() if line else out.strip()[-160:]))

    # -- summary ---------------------------------------------------------
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
    print("GATE: %s" % ("PASSED" if nfail == 0 and nskip == 0 else
                        "PASSED WITH SKIPS" if nfail == 0 else "FAILED"))
    return 1 if nfail else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
