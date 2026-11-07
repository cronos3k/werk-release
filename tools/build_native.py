#!/usr/bin/env python3
"""build_native.py — build the two vendored native helpers.

    python tools/build_native.py            # build both, skip what is current
    python tools/build_native.py --force    # rebuild regardless
    python tools/build_native.py vhacd      # just one

Two things get built, into tools/_build/ (git-ignored, reproducible from the
vendored sources in the same tree):

  werk_vhacd.exe        the real V-HACD v4.1 (tools/vhacd/VHACD.h, BSD-3-Clause)
                        behind a binary-in/binary-out CLI.
  werk_mikktspace.dll   the reference MikkTSpace (tools/mikktspace/mikktspace.c,
                        zlib-style licence) behind one flat-array entry point.

Compiler search order, and each one is RECORDED in tools/_build/build.json so
the pipeline can say which toolchain produced the binary it is calling:

  1. MSVC       — located with vswhere, environment taken from vcvarsall.bat.
  2. clang-cl   — if a standalone LLVM is on PATH.
  3. gcc/g++    — mingw-w64, or the system compiler on Linux/macOS.

Nothing is downloaded and nothing is installed. If no compiler is found the
script says so and exits 1; the pipeline then falls back to its pure-Python
paths and records THAT, which is the point of the whole arrangement.
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
BUILD = os.path.join(TOOLS, "_build")

IS_WIN = os.name == "nt"
EXE = ".exe" if IS_WIN else ""
DLL = ".dll" if IS_WIN else (".dylib" if sys.platform == "darwin" else ".so")

VHACD_BIN = os.path.join(BUILD, "werk_vhacd" + EXE)
MIKK_BIN = os.path.join(BUILD, "werk_mikktspace" + DLL)
STAMP = os.path.join(BUILD, "build.json")


# --------------------------------------------------------------------------
# toolchain discovery
# --------------------------------------------------------------------------

def _vswhere():
    # Note: "ProgramFiles(x86)" does not survive every shell (Git Bash drops
    # environment names containing parentheses), so the well-known locations are
    # checked too rather than trusting the variable.
    roots = [os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"),
             r"C:\Program Files (x86)", r"C:\Program Files"]
    exe = None
    for pf in roots:
        if not pf:
            continue
        cand = os.path.join(pf, "Microsoft Visual Studio", "Installer", "vswhere.exe")
        if os.path.exists(cand):
            exe = cand
            break
    if not exe:
        return None
    try:
        out = subprocess.run(
            [exe, "-latest", "-products", "*", "-requires",
             "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
             "-property", "installationPath"],
            capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    path = out.stdout.strip().splitlines()
    return path[0].strip() if path else None


def msvc_env():
    """Return (env, description) for an x64 MSVC command line, or (None, why)."""
    if not IS_WIN:
        return None, "not Windows"
    vs = _vswhere()
    if not vs:
        return None, "vswhere found no Visual Studio with the C++ toolset"
    vcvars = os.path.join(vs, "VC", "Auxiliary", "Build", "vcvarsall.bat")
    if not os.path.exists(vcvars):
        return None, "no vcvarsall.bat under " + vs
    # Ask cmd for the environment vcvarsall leaves behind and diff it in.
    # Via a .bat rather than `cmd /c "..."`: cmd's quote-stripping rules mangle
    # a one-liner whose program path contains spaces AND which continues with
    # `&&`, and the failure looks like "vcvarsall is not recognized".
    marker = "___WERK_ENV___"
    os.makedirs(BUILD, exist_ok=True)
    bat = os.path.join(BUILD, "_vcvars_probe.bat")
    with open(bat, "w") as f:
        f.write('@echo off\r\ncall "%s" x64 >nul\r\necho %s\r\nset\r\n'
                % (vcvars, marker))
    try:
        out = subprocess.run(["cmd", "/d", "/c", bat],
                             capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.SubprocessError) as e:
        return None, "vcvarsall failed: %s" % e
    if marker not in out.stdout:
        return None, "vcvarsall produced no environment (%s)" % out.stderr.strip()[:200]
    # Keys are upper-cased on both sides. Windows environment names are
    # case-insensitive, but a Python dict is not: leaving `PATH` from
    # os.environ next to `Path` from `set` gives CreateProcess two PATHs and it
    # picks one, which shows up as "cannot find cl.exe" with cl.exe right there.
    env = {k.upper(): v for k, v in os.environ.items()}
    for line in out.stdout.split(marker, 1)[1].splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            env[k.strip().upper()] = v.strip()
    return env, "MSVC from " + vs


def _cl_version(env):
    try:
        out = subprocess.run([_resolve("cl", env)], capture_output=True,
                             text=True, env=env, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return "cl (version unknown)"
    line = (out.stderr or out.stdout).splitlines()
    return line[0].strip() if line else "cl (version unknown)"


def _gxx_version(exe):
    try:
        out = subprocess.run([exe, "--version"], capture_output=True, text=True,
                             timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    line = out.stdout.splitlines()
    return line[0].strip() if line else exe


# --------------------------------------------------------------------------
# the builds
# --------------------------------------------------------------------------

def _resolve(exe, env):
    """CreateProcess looks the program up in the CALLING process's PATH, not in
    the environment handed to it, so an MSVC `cl` reached only through
    vcvarsall's PATH must be resolved to a full path here or the build dies
    with 'cannot find the file specified' while cl.exe sits on disk."""
    if os.path.isabs(exe):
        return exe
    return shutil.which(exe, path=(env or os.environ).get("PATH")) or exe


def _run(cmd, cwd, env=None):
    cmd = [_resolve(cmd[0], env)] + list(cmd[1:])
    print("  $", " ".join(cmd[:6]), "..." if len(cmd) > 6 else "")
    # Compiler scratch goes INSIDE the build directory, never a user profile
    # temp: gcc writes its .s through $TMPDIR, and a Temp it cannot write to is
    # a silent cc1plus death with an empty stderr and exit 1, which costs an
    # hour to diagnose. This also keeps every byte the build touches in-tree.
    tmp = os.path.join(BUILD, "tmp")
    os.makedirs(tmp, exist_ok=True)
    env = dict(env or os.environ)
    env["TMP"] = env["TEMP"] = env["TMPDIR"] = tmp
    r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True,
                       timeout=900)
    if r.returncode != 0:
        sys.stderr.write((r.stdout or "")[-4000:])
        sys.stderr.write((r.stderr or "")[-4000:])
    return r.returncode == 0


def build_vhacd(tc):
    src = os.path.join(TOOLS, "vhacd", "werk_vhacd_cli.cpp")
    if tc["kind"] == "msvc":
        ok = _run(["cl", "/nologo", "/O2", "/EHsc", "/std:c++17", "/MT",
                   "/I", os.path.join(TOOLS, "vhacd"), src,
                   "/Fe:" + VHACD_BIN, "/Fo:" + os.path.join(BUILD, "")],
                  BUILD, tc["env"])
    else:
        ok = _run([tc["cxx"], "-O2", "-std=c++17",
                   "-I", os.path.join(TOOLS, "vhacd"), src,
                   "-o", VHACD_BIN, "-lpthread"], BUILD)
    return ok and os.path.exists(VHACD_BIN)


def build_mikk(tc):
    d = os.path.join(TOOLS, "mikktspace")
    srcs = [os.path.join(d, "mikktspace.c"), os.path.join(d, "werk_mikktspace.c")]
    if tc["kind"] == "msvc":
        ok = _run(["cl", "/nologo", "/O2", "/MT", "/LD", "/I", d] + srcs +
                  ["/Fe:" + MIKK_BIN, "/Fo:" + os.path.join(BUILD, "")],
                  BUILD, tc["env"])
    else:
        ok = _run([tc["cc"], "-O2", "-shared", "-fPIC", "-I", d] + srcs +
                  ["-o", MIKK_BIN, "-lm"], BUILD)
    return ok and os.path.exists(MIKK_BIN)


def pick_toolchain():
    env, why = msvc_env()
    if env:
        return {"kind": "msvc", "env": env, "desc": _cl_version(env)}
    reasons = [why]
    for cc, cxx in (("clang-cl", "clang-cl"), ("gcc", "g++"), ("cc", "c++")):
        if shutil.which(cc) and shutil.which(cxx):
            v = _gxx_version(cxx) or cxx
            if cc == "clang-cl":
                # clang-cl takes MSVC flags; treat it as the gcc path only if we
                # also have a POSIX-style driver, which we do not assume.
                continue
            return {"kind": "gcc", "cc": cc, "cxx": cxx, "env": None, "desc": v}
    reasons.append("no gcc/g++ on PATH")
    return {"kind": None, "desc": "; ".join(reasons)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("targets", nargs="*", default=None,
                    help="vhacd and/or mikktspace (default: both)")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    targets = a.targets or ["vhacd", "mikktspace"]

    os.makedirs(BUILD, exist_ok=True)
    tc = pick_toolchain()
    if not tc["kind"]:
        sys.stderr.write("no C/C++ compiler found: %s\n" % tc["desc"])
        return 1
    print("toolchain:", tc["desc"])

    stamp = {}
    if os.path.exists(STAMP):
        try:
            stamp = json.load(open(STAMP))
        except ValueError:
            stamp = {}
    stamp["toolchain"] = tc["desc"]
    stamp["built_on"] = platform.platform()

    rc = 0
    for t in targets:
        out = VHACD_BIN if t == "vhacd" else MIKK_BIN
        if os.path.exists(out) and not a.force:
            print("%s: already built (%s)" % (t, out))
            continue
        print("building", t)
        t0 = time.time()
        ok = build_vhacd(tc) if t == "vhacd" else build_mikk(tc)
        dt = time.time() - t0
        stamp[t] = {"ok": bool(ok), "path": out if ok else None,
                    "seconds": round(dt, 2)}
        print("  ->", "OK" if ok else "FAILED", "in %.1f s" % dt)
        if not ok:
            rc = 1

    with open(STAMP, "w") as f:
        json.dump(stamp, f, indent=2)
    return rc


if __name__ == "__main__":
    sys.exit(main())
