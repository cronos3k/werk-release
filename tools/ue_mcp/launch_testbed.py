#!/usr/bin/env python3
"""launch_testbed.py — start the werk UE 5.7 testbed editor and wait for it.

    python tools/ue_mcp/launch_testbed.py [--wait 300] [--kill-first]

House rule, honoured literally: the port is CHECKED FREE before the editor is
told to bind it, and the check scans a range rather than assuming one number.
The port actually used is written to <testbed>/logs/testbed_port.txt so
a client does not have to guess either.

The editor is launched detached. It is a GUI process: a viewport that renders
is what makes `take_high_res_screenshot` produce an image rather than an error,
so this is deliberately NOT a headless launch and the difference is stated.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ue_client import DEFAULT_PORTS, port_is_free  # noqa: E402

DEFAULT_ENGINE = r"C:\Program Files\Epic Games\UE_5.7"
# <testbed> is WERK_UE_TESTBED: the Unreal test project folder (plugins/unreal/TESTBED.md).
TESTBED = os.environ.get("WERK_UE_TESTBED", "<WERK_UE_TESTBED unset>")
DEFAULT_PROJECT = os.path.join(TESTBED, "WerkTest", "WerkTest.uproject")
LOG_DIR = os.path.join(TESTBED, "logs")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default=os.environ.get("WERK_UE_ENGINE", DEFAULT_ENGINE))
    ap.add_argument("--project", default=os.environ.get("WERK_UE_PROJECT", DEFAULT_PROJECT))
    ap.add_argument("--wait", type=float, default=300.0)
    ap.add_argument("--kill-first", action="store_true")
    a = ap.parse_args()

    exe = os.path.join(a.engine, "Engine", "Binaries", "Win64", "UnrealEditor.exe")
    if not os.path.isfile(exe):
        print("FAIL: no editor at %s" % exe)
        return 1
    os.makedirs(LOG_DIR, exist_ok=True)

    if a.kill_first:
        subprocess.run(["taskkill", "/IM", "UnrealEditor.exe", "/F"],
                       capture_output=True)
        time.sleep(4)

    # Already up? Then say so and do not start a second editor on the same
    # project -- two editors sharing one Content tree is how a testbed gets
    # corrupted.
    for p in DEFAULT_PORTS:
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/remote/info" % p, timeout=1.0) as r:
                if r.status == 200:
                    print("already running: Remote Control on port %d" % p)
                    open(os.path.join(LOG_DIR, "testbed_port.txt"), "w").write(str(p))
                    return 0
        except Exception:
            pass

    free = [p for p in DEFAULT_PORTS if port_is_free(p)]
    if not free:
        print("FAIL: every port in %d..%d is taken" % (DEFAULT_PORTS[0], DEFAULT_PORTS[-1]))
        return 1
    port = free[0]
    print("ports checked: %d of %d free in %d..%d; taking %d"
          % (len(free), len(DEFAULT_PORTS), DEFAULT_PORTS[0], DEFAULT_PORTS[-1], port))

    log = os.path.join(LOG_DIR, "editor.log")
    cmd = [exe, a.project, "-RCWebControlEnable", "-RCWebInterfaceEnable",
           "-RCWebControlPort=%d" % port]
    with open(log, "wb") as fh:
        subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT,
                         creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
    print("launched: %s" % " ".join(cmd))

    deadline = time.time() + a.wait
    while time.time() < deadline:
        for p in (port,) + tuple(DEFAULT_PORTS):
            try:
                with urllib.request.urlopen("http://127.0.0.1:%d/remote/info" % p,
                                            timeout=1.0) as r:
                    if r.status == 200:
                        open(os.path.join(LOG_DIR, "testbed_port.txt"), "w").write(str(p))
                        print("READY: Remote Control answering on %d after %.0f s"
                              % (p, a.wait - (deadline - time.time())))
                        return 0
            except Exception:
                pass
        time.sleep(2)
    print("FAIL: no Remote Control answer within %.0f s. See %s" % (a.wait, log))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
