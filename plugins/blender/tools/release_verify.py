"""Verify one package with every release reader, outside the host.

    python tools/release_verify.py <pkg.werk> [--bin DIR]   # prints JSON

Readers (each shares no code with a host plug-in's writer):
  lib     `python -m werk verify --json`  from the release libraries (libs/python)
  werkc   `werkc verify <pkg> --json`     the Rust reference reader, JSON Schema validated
  py      `loaders/werk_read.py --verify` the bootstrap loaders of the release repo
  c       `loaders/werk_read.c`           built here with cc/gcc into --bin
  rs      `loaders/werk_read.rs`          built here with rustc into --bin

A reader whose toolchain is missing is reported {"skip": reason}, never
folded into a pass.
"""

import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import werk_paths  # noqa: E402

REPO = werk_paths.repo_root()
LIBS = werk_paths.libs_root()


def _run(cmd, cwd=None, env=None, timeout=900):
    p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, timeout=timeout)
    return p.returncode, p.stdout.decode("utf-8", "replace"), \
        p.stderr.decode("utf-8", "replace")


def find_werkc():
    env = os.environ.get("WERKC")
    cands = [env] if env else []
    cands += [os.path.join(LIBS, "_target", "release", "werkc.exe"),
              os.path.join(LIBS, "_target", "release", "werkc"),
              shutil.which("werkc")]
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return None


def _cc_env():
    env = dict(os.environ)
    cc = shutil.which("gcc") or shutil.which("cc")
    if cc:   # MinGW gcc needs its own bin dir on PATH to find cc1/as
        env["PATH"] = os.path.dirname(cc) + os.pathsep + env.get("PATH", "")
    return cc, env


def build_loaders(bin_dir):
    """{name: exe path or None, name+'_why': reason}"""
    bin_dir = os.path.abspath(bin_dir)
    os.makedirs(bin_dir, exist_ok=True)
    out = {}
    exe = ".exe" if os.name == "nt" else ""
    c_exe = os.path.join(bin_dir, "werk_read_c" + exe)
    if not os.path.isfile(c_exe):
        cc, env = _cc_env()
        if cc:
            rc, so, se = _run([cc, "-std=c99", "-O2",
                               os.path.join(REPO, "loaders", "werk_read.c"),
                               "-o", c_exe], env=env)
            if rc != 0:
                out["c_why"] = "cc failed: %s" % (se or so)[-300:]
        else:
            out["c_why"] = "no gcc/cc on PATH"
    out["c"] = c_exe if os.path.isfile(c_exe) else None
    rs_exe = os.path.join(bin_dir, "werk_read_rs" + exe)
    if not os.path.isfile(rs_exe):
        rustc = shutil.which("rustc")
        if rustc:
            rc, so, se = _run([rustc, "-O", "--edition", "2021",
                               os.path.join(REPO, "loaders", "werk_read.rs"),
                               "-o", rs_exe], cwd=bin_dir)
            if rc != 0:
                out["rs_why"] = "rustc failed: %s" % (se or so)[-300:]
        else:
            out["rs_why"] = "no rustc on PATH"
    out["rs"] = rs_exe if os.path.isfile(rs_exe) else None
    return out


def _loader_summary(rc, so):
    """Parse the three loaders' summary lines into pass/fail counts."""
    m = re.search(r"(\d+)/(\d+) files verified", so)            # werk_read.py
    if m:
        return {"exit": rc, "pass": int(m.group(1)),
                "fail": int(m.group(2)) - int(m.group(1)), "line": m.group(0)}
    m = re.search(r"summary: (\d+) file checks passed, (\d+) failed", so)  # rs
    if m:
        return {"exit": rc, "pass": int(m.group(1)), "fail": int(m.group(2)),
                "line": m.group(0)}
    m = re.search(r"verify: (\d+) file\(s\) PASS, (\d+) FAIL", so)          # c
    if m:
        return {"exit": rc, "pass": int(m.group(1)), "fail": int(m.group(2)),
                "line": m.group(0)}
    return {"exit": rc, "pass": None, "fail": None,
            "line": (so.strip().splitlines() or [""])[-1][:200]}


def verify(pkg, bin_dir):
    pkg = os.path.abspath(pkg)
    res = {"package": pkg, "bytes": os.path.getsize(pkg)}
    try:
        sys.path.insert(0, os.path.join(LIBS, "python"))
        import werk as _w
        res["spec_sha256"] = _w.open(pkg).manifest.get("spec_sha256")
    except Exception as e:  # noqa: BLE001
        res["spec_sha256"] = None
        res["spec_sha256_error"] = str(e)
    rc, so, se = _run([sys.executable, "-m", "werk", "verify", pkg, "--json"],
                      cwd=os.path.join(LIBS, "python"))
    try:
        res["lib"] = dict(json.loads(so), exit_status=rc)
    except ValueError:
        res["lib"] = {"exit_status": rc, "unparsed": (so + se)[-400:]}
    wc = find_werkc()
    if wc:
        rc, so, se = _run([wc, "verify", pkg, "--json"])
        try:
            res["werkc"] = dict(json.loads(so), exit_status=rc)
        except ValueError:
            res["werkc"] = {"exit_status": rc, "unparsed": (so + se)[-400:]}
    else:
        res["werkc"] = {"skip": "werkc not found (set WERKC)"}
    rc, so, se = _run([sys.executable, os.path.join(REPO, "loaders", "werk_read.py"),
                       pkg, "--verify"])
    res["py"] = _loader_summary(rc, so)
    exes = build_loaders(bin_dir)
    for k in ("c", "rs"):
        if exes.get(k):
            rc, so, se = _run([exes[k], pkg, "--verify"])
            res[k] = _loader_summary(rc, so)
        else:
            res[k] = {"skip": exes.get(k + "_why", "not built")}
    return res


def bundle_spec_sha256():
    """spec_sha256 of the release library's bundled spec/ (what every package
    the library writes for a built-in profile carries)."""
    sys.path.insert(0, os.path.join(LIBS, "python"))
    import werk as _w
    pw = _w.PackageWriter("image/1", "probe")
    return _w.spec_sha256_of(list(pw.nodes.values()))


def all_ok(v, expect_exit=0):
    """(ok, short text) -- every reader that ran accepted the package."""
    bits, ok = [], True
    lib = v["lib"]
    ok &= lib.get("exit_status") == expect_exit
    bits.append("lib exit %s sig %s" % (lib.get("exit_status"), lib.get("signature")))
    wc = v["werkc"]
    if "skip" in wc:
        bits.append("werkc SKIP")
    else:
        ok &= wc.get("exit_status") == expect_exit and wc.get("schema_validated") is True
        bits.append("werkc exit %s schema %s" % (wc.get("exit_status"),
                                                 wc.get("schema_validated")))
    for k in ("py", "c", "rs"):
        r = v[k]
        if "skip" in r:
            bits.append("%s SKIP" % k)
            continue
        ok &= r["exit"] == expect_exit and (expect_exit != 0 or r.get("fail") == 0) \
            and r.get("pass") is not None
        bits.append("%s %s/%s" % (k, r.get("pass"), (r.get("pass") or 0) + (r.get("fail") or 0)))
    return bool(ok), "; ".join(bits)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("pkg")
    ap.add_argument("--bin", default=os.path.join(os.path.dirname(HERE), "_bin"))
    a = ap.parse_args()
    v = verify(a.pkg, a.bin)
    print(json.dumps(v, indent=1))
    print(all_ok(v))
