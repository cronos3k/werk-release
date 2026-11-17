"""readers.py -- run every werk release reader over one package.

Stdlib only. Used by the W5c gates (plugins/unreal, plugins/office); the same
file is copied into each folder.

Readers (all from the release tree, never from the package under test):
  py-lib     python -m werk verify --json         (stage/libs/python, the release library)
  py-single  python werk_single.py verify --json  (the vendored single file)
  js         node js/bin/werk.js verify --json    (when node is on PATH)
  werkc      werkc verify --json                  (reference full reader, JSON Schema validation)
  ref-py     loaders/werk_read.py <pkg> --verify --strict  (bootstrap loader;
             judged on the --strict exit, as the release loader gate is)
  ref-c      loaders/werk_read.c built with MSYS2 gcc -std=c99 -O2
  ref-rs     loaders/werk_read.rs built with rustc -O --edition 2021

`check(pkg, want_exit)` returns a list of (reader, ok, detail). A reader that
is not available is returned as (reader, None, "not run: ...") -- never as a
pass.
"""

import json
import os
import shutil
import subprocess
import sys

EXE = ".exe" if os.name == "nt" else ""


class Readers(object):
    def __init__(self, libs, loaders, work, vendor_single=None, python=None):
        self.libs = libs                 # stage/libs
        self.loaders = loaders           # <repo>/loaders (release)
        self.work = work                 # build dir for the C / Rust loaders
        self.single = vendor_single or os.path.join(libs, "python", "werk_single.py")
        self.py = python or sys.executable
        self.node = shutil.which("node")
        self.werkc = os.path.join(libs, "_target", "release", "werkc" + EXE)
        if not os.path.isfile(self.werkc):
            self.werkc = shutil.which("werkc")
        self.env = dict(os.environ)
        self.env["PYTHONPATH"] = os.path.join(libs, "python")
        self.env["PYTHONIOENCODING"] = "utf-8"
        self.ref_c = None
        self.ref_rs = None
        self.build_notes = []
        os.makedirs(work, exist_ok=True)
        self._build_loaders()

    # -- building the two compiled bootstrap loaders -------------------------
    def _build_loaders(self):
        cc = None
        for c in (os.environ.get("WERK_CC"), "C:/msys64/mingw64/bin/gcc.exe",
                  shutil.which("gcc"), shutil.which("cc"), shutil.which("clang")):
            if c and os.path.isfile(c):
                cc = c
                break
        if cc:
            env = dict(self.env)
            # this host's MinGW gcc exits 1 silently unless its bin dir is first
            env["PATH"] = os.path.dirname(cc) + os.pathsep + env.get("PATH", "")
            out = os.path.join(self.work, "werk_read_c" + EXE)
            p = subprocess.run([cc, "-std=c99", "-O2", os.path.join(self.loaders, "werk_read.c"),
                                "-o", out], capture_output=True, env=env)
            if p.returncode == 0:
                self.ref_c = out
                self.build_notes.append("ref-c: built with %s" % cc)
            else:
                self.build_notes.append("ref-c: build FAILED (%s): %s" % (
                    cc, (p.stderr or p.stdout).decode("utf-8", "replace")[:300]))
        else:
            self.build_notes.append("ref-c: no C compiler found")
        rustc = shutil.which("rustc")
        if rustc:
            out = os.path.join(self.work, "werk_read_rs" + EXE)
            p = subprocess.run([rustc, "-O", "--edition", "2021",
                                os.path.join(self.loaders, "werk_read.rs"), "-o", out],
                               capture_output=True, env=self.env)
            if p.returncode == 0:
                self.ref_rs = out
                self.build_notes.append("ref-rs: built with %s" % rustc)
            else:
                self.build_notes.append("ref-rs: build FAILED: %s" % (
                    (p.stderr or p.stdout).decode("utf-8", "replace")[:300]))
        else:
            self.build_notes.append("ref-rs: no rustc found")

    # -- running -------------------------------------------------------------
    def _run(self, cmd):
        p = subprocess.run(cmd, capture_output=True, env=self.env)
        return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")

    def _full(self, name, base, pkg, want_exit):
        rc, out, err = self._run(base + ["verify", pkg, "--json"])
        try:
            v = json.loads(out)
        except ValueError:
            return (name, False, "exit %d, no JSON: %s" % (rc, (err or out).strip()[-200:]))
        dead = v.get("dead_nodes") or v.get("dead") or []
        ndead = len(dead) if isinstance(dead, list) else dead
        sv = v.get("schema_validated")
        detail = "exit %d (want %d), profile %s, signature %s, nodes %s, dead %s%s" % (
            rc, want_exit, v.get("profile"), v.get("signature"), v.get("nodes"), ndead,
            "" if sv is None else ", schema_validated %s" % sv)
        errs = v.get("error_codes")
        if errs:
            detail += ", error codes %s" % errs
        return (name, rc == want_exit, detail)

    def _boot(self, name, base, pkg, want_exit):
        rc, out, err = self._run(base + [pkg, "--verify"])
        tail = [l for l in out.strip().splitlines() if l.strip()]
        rc2, out2, _ = self._run(base + [pkg, "--verify", "--strict"])
        # judged on --verify --strict, as the release's loader gate does
        # (RELEASE-ASSEMBLY.md: 0 for the clean fixtures, 1 for the damaged)
        detail = "--verify --strict exit %d (want %d); --verify exit %d; %s" % (
            rc2, want_exit, rc, (tail[-1] if tail else err.strip()[-160:]))
        return (name, rc2 == want_exit, detail)

    def check(self, pkg, want_exit=0):
        rows = []
        rows.append(self._full("py-lib", [self.py, "-m", "werk"], pkg, want_exit))
        rows.append(self._full("py-single", [self.py, self.single], pkg, want_exit))
        if self.node:
            rows.append(self._full("js", [self.node, os.path.join(self.libs, "js", "bin", "werk.js")],
                                   pkg, want_exit))
        else:
            rows.append(("js", None, "not run: node not on PATH"))
        if self.werkc:
            rows.append(self._full("werkc", [self.werkc], pkg, want_exit))
        else:
            rows.append(("werkc", None, "not run: werkc not built"))
        rows.append(self._boot("ref-py", [self.py, os.path.join(self.loaders, "werk_read.py")],
                               pkg, want_exit))
        rows.append(self._boot("ref-c", [self.ref_c], pkg, want_exit) if self.ref_c
                    else ("ref-c", None, "not run: loader not built"))
        rows.append(self._boot("ref-rs", [self.ref_rs], pkg, want_exit) if self.ref_rs
                    else ("ref-rs", None, "not run: loader not built"))
        return rows
