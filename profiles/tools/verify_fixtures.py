#!/usr/bin/env python3
"""verify_fixtures.py -- every reader of the release on the six profile fixtures, one table.

    python profiles/tools/verify_fixtures.py --werkc PATH [--node NODE] [--out FILE.json]

Per fixture: the pin (fixtures.json), `werkc verify` (exit, validated, census, payloads,
formats lines), `python -m werk verify` and `--strict`, `node libs/js/bin/werk.js verify`,
`node libs/js/bin/werk-es3.js verify`, `python loaders/werk_read.py --verify --strict`, and the
profile's reference reader (profiles/<name>/read_<name>.py, exit and dead count). Exit 0 when
every fixture matches its pin, werkc / libs / loader exit 0 (the libs' --strict is expected to
exit 1: it promotes the one `unsupported-profile` warning every non-built-in profile gets), and
every reference reader exits 0.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILES = os.path.dirname(HERE)
REPO = os.path.dirname(PROFILES)


def run(cmd, env=None):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--werkc", required=True); ap.add_argument("--node", default="node"); ap.add_argument("--out")
    ap.add_argument("--fixtures", default=os.path.join(PROFILES, "fixtures"))
    a = ap.parse_args()
    pins = json.load(open(os.path.join(a.fixtures, "fixtures.json"), encoding="utf-8"))["fixtures"]
    env = dict(os.environ, PYTHONPATH=os.path.join(REPO, "libs", "python"), PYTHONIOENCODING="utf-8")
    rows, bad = {}, 0
    for prof, pin in sorted(pins.items()):
        path = os.path.join(a.fixtures, pin["file"])
        data = open(path, "rb").read()
        r = {"pin": hashlib.sha256(data).hexdigest() == pin["sha256"] and len(data) == pin["bytes"]}
        rc, o, _e = run([a.werkc, "verify", path])
        lines = {k: (re.search(r"^%s\s*:\s*(.*)$" % k, o, re.M) or [None, None])[1]
                 for k in ("validated", "census", "envelopes", "payloads", "formats")}
        r["werkc"] = {"exit": rc, **lines, "errors": len(re.findall(r"^\[error\]", o, re.M))}
        r["py"] = run([sys.executable, "-m", "werk", "verify", path], env)[0]
        r["py_strict"] = run([sys.executable, "-m", "werk", "verify", path, "--strict"], env)[0]
        r["js"] = run([a.node, os.path.join(REPO, "libs", "js", "bin", "werk.js"), "verify", path])[0]
        r["es3"] = run([a.node, os.path.join(REPO, "libs", "js", "bin", "werk-es3.js"), "verify", path])[0]
        rc, o, _e = run([sys.executable, os.path.join(REPO, "loaders", "werk_read.py"), path, "--verify", "--strict"])
        m = re.search(r"(\d+)/(\d+) files verified", o)
        r["loader_py_strict"] = {"exit": rc, "verified": m.group(0) if m else None}
        reader = os.path.join(PROFILES, prof, "read_%s.py" % prof.replace("-", "_"))
        rc, o, _e = run([sys.executable, reader, path])
        try:
            d = json.loads(o)
            r["reference_reader"] = {"exit": rc, "dead": len(d["dead"]), "files_verified": d["files_verified"]}
        except ValueError:
            r["reference_reader"] = {"exit": rc, "output": o[-300:]}
        ok = (r["pin"] and r["werkc"]["exit"] == 0 and r["py"] == 0 and r["py_strict"] == 1 and r["js"] == 0
              and r["es3"] == 0 and r["loader_py_strict"]["exit"] == 0 and r["reference_reader"]["exit"] == 0)
        r["ok"] = ok
        bad += not ok
        rows[prof] = r
        print("%-14s %s %s" % (prof, "OK  " if ok else "FAIL", json.dumps(r)))
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(rows, fh, indent=1, sort_keys=True)
            fh.write("\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
