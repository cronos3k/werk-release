"""Run one ExtendScript file inside Photoshop 2020 through COM `.DoJavaScript`.

    py -3.12 tools/ps_run.py <script.jsx> [--timeout S] [--arg NAME=VALUE ...]

The script is evaluated with `$.evalFile` so that `$.fileName` inside it is its
own path (it finds its siblings from there). `--arg` values are put into a
global object `WERK_ARGS` before it runs. The script's last expression is
printed (it should be a JSON string).

Desktop safety: if Photoshop 2020 is already running (it usually is, with the
user's own documents), this ATTACHES and never quits it. It quits only an
instance it started itself. The script is responsible for touching only
documents it created; ps_run.py records the document count before/after and
the active document's name, and fails loudly if the count changed.
"""
import json
import os
import subprocess
import sys
import threading
import time

import psutil
import pythoncom
import win32com.client as wc

PS_EXE = r"C:\Program Files\Adobe\Adobe Photoshop 2020\Photoshop.exe"
PROGID = "Photoshop.Application.140"


def ps_pids():
    out = set()
    for p in psutil.process_iter(["exe"]):
        try:
            if p.info["exe"] and os.path.normcase(p.info["exe"]) == os.path.normcase(PS_EXE):
                out.add(p.pid)
        except Exception:
            pass
    return out


def js_str(s):
    return json.dumps(s)


def run(script, args=None, timeout=1800):
    script = os.path.abspath(script).replace("\\", "/")
    pre = "var WERK_ARGS = %s;\n" % json.dumps(args or {})
    src = pre + "$.evalFile(new File(%s));" % js_str(script)
    before = ps_pids()
    box = {}

    def work():
        pythoncom.CoInitialize()
        try:
            app = wc.DispatchEx(PROGID) if not before else wc.Dispatch(PROGID)
            box["attached"] = bool(before)
            n0 = app.Documents.Count
            try:
                a0 = app.ActiveDocument.Name if n0 else None
            except Exception:
                a0 = None
            box["docs_before"] = n0
            box["active_before"] = a0
            t = time.time()
            box["ret"] = app.DoJavaScript(src)
            box["seconds"] = round(time.time() - t, 1)
            box["docs_after"] = app.Documents.Count
            try:
                box["active_after"] = app.ActiveDocument.Name if box["docs_after"] else None
            except Exception:
                box["active_after"] = None
            box["version"] = app.Version
            if not before:
                try:
                    app.Quit()
                except Exception as e:
                    box["quit"] = repr(e)
        except Exception as e:
            box["err"] = repr(e)
    th = threading.Thread(target=work, daemon=True)
    th.start()
    th.join(timeout)
    if th.is_alive():
        box["err"] = "HUNG: DoJavaScript did not return in %ds" % timeout
    new = ps_pids() - before
    if new:
        time.sleep(5)
        new = ps_pids() - before
        for p in new:
            subprocess.run(["taskkill", "/PID", str(p), "/T", "/F"], capture_output=True)
        box["killed_own_instance"] = sorted(new)
    box["pids_before"] = sorted(before)
    return box


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--arg", action="append", default=[])
    a = ap.parse_args()
    args = dict(x.split("=", 1) for x in a.arg)
    r = run(a.script, args, a.timeout)
    print(json.dumps(r, indent=1))
    sys.exit(0 if "err" not in r and r.get("docs_before") == r.get("docs_after") else 1)
