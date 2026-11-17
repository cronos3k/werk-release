#!/usr/bin/env python3
"""gate_common.py -- what the gates added on 2026-10-13 share.

The four readers of this repository (the reference core's `werkc`, and the
three bootstrap loaders in Python, Rust and C) are compared with one another
by several gates. Building the two native loaders, running a reader and
reading its report were about to be written a fifth time; they are written
once here instead.

Nothing here decides a verdict. A gate records PASS, FAIL or SKIP itself, and
a SKIP is not a pass: every gate that uses this file exits non-zero when
anything was skipped.
"""

import hashlib
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, "fixtures")
LOADERS = os.path.join(ROOT, "loaders")
NATIVE = os.path.join(ROOT, "core", "target", "gate-loaders")
EXE = ".exe" if os.name == "nt" else ""

REPORT_LINE = re.compile(r"^\[(info|warn|error)\]\s+([a-z0-9]+(?:-[a-z0-9]+)*)")


class Gate(object):
    def __init__(self, title):
        self.title = title
        self.results = []

    def record(self, name, status, detail=""):
        assert status in ("PASS", "FAIL", "SKIP")
        self.results.append((name, status, detail))
        print("[%s] %-46s %s" % (status, name, detail))

    def check(self, name, ok, detail="", fail_detail=None):
        self.record(name, "PASS" if ok else "FAIL",
                    detail if ok or fail_detail is None else fail_detail)
        return ok

    def finish(self):
        npass = sum(1 for _, s, _ in self.results if s == "PASS")
        nfail = sum(1 for _, s, _ in self.results if s == "FAIL")
        nskip = sum(1 for _, s, _ in self.results if s == "SKIP")
        print()
        print("%d PASS, %d FAIL, %d SKIP" % (npass, nfail, nskip))
        print("GATE %s: %s" % (
            self.title,
            "FAILED" if nfail else
            "INCOMPLETE (%d SKIPPED; a skip is not a pass)" % nskip if nskip
            else "PASSED"))
        return 1 if (nfail or nskip) else 0


def compiler_env(cc):
    """The environment to run a C/C++ compiler in: its OWN bin directory first
    on PATH. A MinGW gcc loads its DLLs (libgmp, zlib1, libzstd, ...) through
    PATH; when another MinGW's bin precedes it -- Git for Windows puts its
    /mingw64/bin there -- cc1 fails to load (exit 127, nothing printed) and gcc
    exits 1 with no diagnostics. Measured on the author's host (finding N2 of
    the release evidence); the toolchain was never broken, the PATH was."""
    env = dict(os.environ)
    d = os.path.dirname(os.path.abspath(cc)) if cc else ""
    if d:
        env["PATH"] = d + os.pathsep + env.get("PATH", "")
    return env


def run(cmd, cwd=None, timeout=1800, env=None):
    p = subprocess.run(cmd, cwd=cwd or ROOT, capture_output=True, timeout=timeout,
                       env=env)
    out = (p.stdout or b"").decode("utf-8", "replace") + \
          (p.stderr or b"").decode("utf-8", "replace")
    return p.returncode, out


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def werkc():
    for profile in ("release", "debug"):
        p = os.path.join(ROOT, "core", "target", profile, "werkc" + EXE)
        if os.path.isfile(p):
            return p
    return None


def _msvc(command, work):
    base = r"C:\Program Files\Microsoft Visual Studio\2022"
    vcvars = None
    for edition in ("Community", "Professional", "Enterprise", "BuildTools"):
        v = os.path.join(base, edition, r"VC\Auxiliary\Build\vcvars64.bat")
        if os.path.isfile(v):
            vcvars = v
            break
    if not vcvars and not shutil.which("cl"):
        return 127, "no cl.exe found"
    bat = os.path.join(work, "_msvc.bat")
    lines = ["@echo off"]
    if vcvars:
        lines.append('call "%s" >nul' % vcvars)
    lines += [command, "exit /b %ERRORLEVEL%"]
    with open(bat, "wb") as fh:
        fh.write(("\r\n".join(lines) + "\r\n").encode("ascii"))
    return run(["cmd.exe", "/c", bat], cwd=work)


def native_loaders():
    """Build the Rust and the C loader from loaders/ as they are NOW.

    Returns {"rs": path-or-None, "c": path-or-None, "why": {...}}. A binary is
    rebuilt whenever its source's SHA-256 is not the one it was built from, so
    a gate never measures a stale loader (the S8 lesson, applied to tools).
    """
    os.makedirs(NATIVE, exist_ok=True)
    out = {"rs": None, "c": None, "why": {}}

    def current(exe, src):
        stamp = exe + ".src-sha256"
        return (os.path.isfile(exe) and os.path.isfile(stamp)
                and open(stamp).read().strip() == sha256_file(src))

    def stamp(exe, src):
        with open(exe + ".src-sha256", "w") as fh:
            fh.write(sha256_file(src))

    src = os.path.join(LOADERS, "werk_read.rs")
    exe = os.path.join(NATIVE, "werk_read_rs" + EXE)
    if current(exe, src):
        out["rs"] = exe
    elif shutil.which("rustc"):
        rc, text = run(["rustc", "-O", "--edition", "2021", "-o", exe, src])
        if rc == 0:
            stamp(exe, src)
            out["rs"] = exe
        else:
            out["why"]["rs"] = "rustc: " + text.strip()[-200:]
    else:
        out["why"]["rs"] = "rustc not on PATH"

    src = os.path.join(LOADERS, "werk_read.c")
    exe = os.path.join(NATIVE, "werk_read_c" + EXE)
    if current(exe, src):
        out["c"] = exe
    else:
        built, why = False, "no C compiler found"
        cc = shutil.which("gcc") or shutil.which("clang")
        if cc:
            rc, text = run([cc, "-std=c99", "-O2", "-o", exe, src],
                           env=compiler_env(cc))
            built = rc == 0
            why = ("%s exited %d: %s" % (os.path.basename(cc), rc,
                                         text.strip()[-160:] or "no diagnostics, "
                                         "with its own bin first on PATH (the compiler "
                                         "did not run; not a source failure)"))
        if not built and os.name == "nt":
            rc, text = _msvc('cl /nologo /O2 /W3 "%s" /Fe:"%s" /Fo:"%s.obj"'
                             % (src, exe, exe), NATIVE)
            built = rc == 0
            if not built:
                why += "; MSVC: " + text.strip()[-160:]
        if built:
            stamp(exe, src)
            out["c"] = exe
        else:
            out["why"]["c"] = why
    return out


def readers(gate):
    """[(name, argv-prefix)] for the four readers; records a SKIP for each one
    that could not be built, so its absence is in the gate's count."""
    found = []
    w = werkc()
    if w:
        found.append(("core", [w, "verify"], []))
    else:
        gate.record("reader available: core", "SKIP",
                    "no werkc; run `cargo build --release` in core/")
    found.append(("py", [sys.executable, os.path.join(LOADERS, "werk_read.py")],
                  ["--verify", "--strict"]))
    nat = native_loaders()
    for key in ("rs", "c"):
        if nat[key]:
            found.append((key, [nat[key]], ["--verify", "--strict"]))
        else:
            gate.record("reader available: %s" % key, "SKIP", nat["why"].get(key, ""))
    return found


def verify(reader, package, extra=()):
    """Run one reader's verify over one package -> (exit status, output)."""
    _name, head, tail = reader
    return run(list(head) + [package] + list(tail) + list(extra))


def codes(output):
    """The set of (severity, code) pairs a reader printed."""
    found = set()
    for line in output.splitlines():
        m = REPORT_LINE.match(line.strip())
        if m:
            found.add((m.group(1), m.group(2)))
    return found


def dead_nodes(output):
    """node ids a reader reported dead, from `[error] node-dead node=<id>`."""
    return sorted(set(re.findall(r"node-dead node=([a-z0-9-]+)", output)))
