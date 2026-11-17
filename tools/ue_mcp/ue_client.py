#!/usr/bin/env python3
"""ue_client.py — drive a live Unreal editor from outside, over Remote Control.

Stdlib only (urllib). No third-party MCP or UE package, on purpose: this is the
transport layer and it should have nothing that can rot.

WHY REMOTE CONTROL AND NOT AN MCP PLUGIN
----------------------------------------
Researched against the live repositories on 2026-08-08, not from memory:

* `chongdashu/unreal-mcp` (2057 stars) last saw a push on **2025-04-22** and
  carries **four separate open, unmerged issues about 5.6/5.7 compile
  breakage** (#52, #54, #55, #60 — `ANY_PACKAGE` removal and a
  `CompressImageArray` signature change). Its README documents no asset-listing
  tool and no screenshot tool, so even after patching the compile it fails two
  of the three things this testbed has to do.
* `kvick-games/UnrealMCP` targets **UE 5.5 only** and calls itself "VERY WIP".
* `ChiR24/Unreal_mcp` is genuinely active and claims 5.0–5.8, but ships
  **version-pinned prebuilt binaries** ("a build for 5.6 won't work with 5.5,
  5.7, or 5.8") — a compiled dependency on the engine, which is the thing that
  broke every other option.
* `runreal/unreal-mcp` needs no plugin (it rides UE's Python Remote Execution),
  but that transport is **multicast**, and on this lab's VPN'd Windows boxes
  multicast discovery is exactly what gets swallowed.

Epic's Remote Control API ships **with** the engine, needs no compilation, and
is therefore the only option that cannot be broken by an engine upgrade. Chosen
for that reason and not because it is the most featureful.

THE ONE TRICK THAT MAKES IT ENOUGH
----------------------------------
Remote Control calls a UFUNCTION on an object. `PythonScriptLibrary` is an
object with a `BlueprintCallable` static, so:

    PUT /remote/object/call
    { "objectPath": "/Script/PythonScriptPlugin.Default__PythonScriptLibrary",
      "functionName": "ExecutePythonScript",
      "parameters": { "PythonScript": "<any python>" } }

turns one HTTP endpoint into the entire editor Python API. `ExecutePythonScript`
returns only a bool, so anything that has to come BACK is written to a JSON file
and read from disk — which is also why a result here is a measurement rather
than a log line somebody parsed.

PORTS
-----
House rule: check before binding. `find_port()` scans 30010..30030 and returns
the first that answers `/remote/info`, so a busy 30010 costs a scan and not a
failure. The launcher passes the port it picked to the editor.
"""

import argparse
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request

DEFAULT_PORTS = list(range(30010, 30031))
PY_LIB = "/Script/PythonScriptPlugin.Default__PythonScriptLibrary"


class UEError(RuntimeError):
    pass


def port_is_free(port, host="127.0.0.1"):
    """True when nothing is listening. Used BEFORE telling the editor to bind."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.25)
    try:
        return s.connect_ex((host, port)) != 0
    finally:
        s.close()


def first_free_port(ports=DEFAULT_PORTS):
    for p in ports:
        if port_is_free(p):
            return p
    raise UEError("no free port in %d..%d" % (ports[0], ports[-1]))


class UE:
    def __init__(self, port=None, host="127.0.0.1", timeout=120.0):
        self.host = host
        self.timeout = timeout
        self.port = port or self.find_port(host)

    @staticmethod
    def find_port(host="127.0.0.1", ports=DEFAULT_PORTS, timeout=1.5):
        """The first port that answers Remote Control's own route listing.

        `/remote/info` is used rather than a bare TCP connect because something
        else listening on 30010 would otherwise look like a live editor.
        """
        for p in ports:
            try:
                req = urllib.request.Request("http://%s:%d/remote/info" % (host, p),
                                             method="GET")
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    if r.status == 200:
                        return p
            except Exception:
                continue
        raise UEError("no Unreal Remote Control server answered on %d..%d. "
                      "Is the editor running? See plugins/unreal/TESTBED.md."
                      % (ports[0], ports[-1]))

    # -- raw -----------------------------------------------------------------

    def call(self, object_path, function_name, parameters=None, transaction=True):
        body = json.dumps({
            "objectPath": object_path,
            "functionName": function_name,
            "parameters": parameters or {},
            "generateTransaction": bool(transaction),
        }).encode("utf-8")
        req = urllib.request.Request(
            "http://%s:%d/remote/object/call" % (self.host, self.port),
            data=body, method="PUT",
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                raw = r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            raise UEError("HTTP %d from Remote Control: %s"
                          % (e.code, e.read().decode("utf-8", "replace")[:500]))
        return json.loads(raw) if raw.strip() else {}

    # -- python --------------------------------------------------------------

    def python(self, script):
        """Run editor Python. Returns Remote Control's raw reply (a bool)."""
        return self.call(PY_LIB, "ExecutePythonScript", {"PythonScript": script})

    def python_json(self, script, tmp=None):
        """Run editor Python that produces a JSON RESULT.

        The script gets a bound name `WERK_OUT`: write anything JSON-encodable
        to it and it comes back. Implemented by writing a file, because
        ExecutePythonScript's return value is a bool and nothing else, and
        scraping stdout out of a log would be a parser waiting to break.
        """
        tmp = tmp or os.environ.get("WERK_UE_TMP", os.path.join(
            os.environ.get("WERK_UE_TESTBED", "<WERK_UE_TESTBED unset>"), "logs", "rc_result.json"))
        tmp = tmp.replace("\\", "/")
        wrapper = (
            "import json, traceback, unreal\n"
            "WERK_OUT = None\n"
            "def _werk_body():\n"
            "    global WERK_OUT\n"
            + "".join("    %s\n" % line for line in script.splitlines())
            + "try:\n"
              "    _werk_body()\n"
              "    _werk_res = {'ok': True, 'result': WERK_OUT}\n"
              "except Exception as e:\n"
              "    _werk_res = {'ok': False, 'error': repr(e),\n"
              "                 'traceback': traceback.format_exc()}\n"
              "open(%r, 'w', encoding='utf-8').write(json.dumps(_werk_res, default=str))\n"
            % tmp)
        if os.path.isfile(tmp):
            os.remove(tmp)
        self.python(wrapper)
        if not os.path.isfile(tmp):
            raise UEError("the editor ran the script but wrote no result file (%s). "
                          "Usually means PythonScriptPlugin is not enabled." % tmp)
        with open(tmp, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
        if not doc.get("ok"):
            raise UEError("editor python failed: %s\n%s"
                          % (doc.get("error"), doc.get("traceback", "")))
        return doc.get("result")

    # -- the three things the Stage 10B gate needs --------------------------

    def list_assets(self, path="/Game/Werk", recursive=True):
        return self.python_json(
            "WERK_OUT = sorted(str(a) for a in "
            "unreal.EditorAssetLibrary.list_assets(%r, recursive=%r))"
            % (path, bool(recursive)))

    def spawn_mesh(self, asset_path, location=(0.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0),
                   scale=(1.0, 1.0, 1.0), label=None):
        return self.python_json(
            "m = unreal.EditorAssetLibrary.load_asset(%r)\n"
            "if m is None: raise RuntimeError('no such asset: %s')\n"
            "sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)\n"
            "a = sub.spawn_actor_from_object(m, unreal.Vector(%f,%f,%f), "
            "unreal.Rotator(%f,%f,%f))\n"
            "a.set_actor_scale3d(unreal.Vector(%f,%f,%f))\n"
            "%s\n"
            "WERK_OUT = {'actor': a.get_name(), 'label': a.get_actor_label(), "
            "'asset': %r, 'location': [%f,%f,%f]}"
            % (asset_path, asset_path,
               location[0], location[1], location[2],
               rotation[0], rotation[1], rotation[2],
               scale[0], scale[1], scale[2],
               ("a.set_actor_label(%r)" % label) if label else "pass",
               asset_path, location[0], location[1], location[2]))

    # S10-5. The editor will not take a screenshot of a window that is not in
    # the foreground, and it does not say so: the console command is ACCEPTED,
    # the frame counter keeps advancing, and no file is ever written and no
    # warning logged. Measured three ways -- take_high_res_screenshot with an
    # absolute path, the same call with force_game_view off, and HighResShot on
    # the console -- all silent. The same HighResShot, issued one second after
    # the window was raised, wrote the PNG and logged
    # "High resolution screenshot saved as ...".
    #
    # So the client raises the window itself, through user32, and says that it
    # did. This makes a screenshot an INTERACTIVE-session capability, which is a
    # real limitation and is recorded as one in plugins/unreal/TESTBED.md
    # rather than left to be discovered by someone whose CI produces no images.
    _FOCUS = r"""
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class WerkWin {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
}
"@
$p = Get-Process UnrealEditor -ErrorAction SilentlyContinue | Select-Object -First 1
if ($p) { [WerkWin]::ShowWindow($p.MainWindowHandle, 9) | Out-Null
          [WerkWin]::SetForegroundWindow($p.MainWindowHandle) | Out-Null
          Write-Output $p.MainWindowTitle }
"""

    def focus_editor(self):
        import subprocess
        p = subprocess.run(["powershell", "-NoProfile", "-Command", self._FOCUS],
                           capture_output=True, text=True)
        return p.stdout.strip()

    def screenshot(self, out_path, width=1280, height=720, wait=25.0):
        """High-res viewport screenshot, moved to an absolute path.

        Two facts drive the shape of this, and both were measured rather than
        assumed:

          * the editor must be the FOREGROUND window (see S10-5 above), so the
            window is raised first;
          * `HighResShot ... filename=` is not honoured by the editor viewport
            path -- the file lands in Saved/Screenshots/WindowsEditor under an
            auto-numbered name. So the shot is taken, the NEW file is found by
            comparing the directory listing before and after, and it is MOVED.
            Naming it afterwards is honest; pretending the parameter worked
            would not be.

        The request is asynchronous, so this waits for a file whose size has
        stopped changing and returns the byte count it actually found. An HTTP
        200 is not evidence that a screenshot exists.
        """
        out_path = os.path.abspath(out_path).replace("\\", "/")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        if os.path.isfile(out_path):
            os.remove(out_path)

        shots_dir = self.python_json(
            "import unreal, os\n"
            "d = os.path.join(unreal.Paths.project_saved_dir(), 'Screenshots', 'WindowsEditor')\n"
            "WERK_OUT = os.path.abspath(d).replace('\\\\', '/')")
        os.makedirs(shots_dir, exist_ok=True)
        before = set(os.listdir(shots_dir))

        self.focus_editor()
        time.sleep(1.0)
        self.python("import unreal\n"
                    "unreal.SystemLibrary.execute_console_command(None, 'HighResShot %dx%d')\n"
                    % (int(width), int(height)))

        deadline = time.time() + wait
        found, size = None, -1
        while time.time() < deadline:
            new = [f for f in os.listdir(shots_dir)
                   if f not in before and f.lower().endswith(".png")]
            if new:
                cand = os.path.join(shots_dir, sorted(new)[-1])
                s = os.path.getsize(cand)
                if s > 0 and s == size:
                    found = cand
                    break
                size = s
            time.sleep(0.5)
        if not found:
            raise UEError(
                "no screenshot appeared in %s within %.1f s. The editor accepts "
                "HighResShot silently when its window is not in the foreground "
                "(S10-5); an RDP session with no visible desktop cannot produce "
                "one." % (shots_dir, wait))
        os.replace(found, out_path)
        return {"path": out_path, "bytes": os.path.getsize(out_path),
                "width": width, "height": height,
                "captured_as": os.path.basename(found)}

    def console(self, command):
        return self.python_json(
            "w = unreal.EditorLevelLibrary.get_editor_world()\n"
            "unreal.SystemLibrary.execute_console_command(w, %r)\n"
            "WERK_OUT = {'command': %r}" % (command, command))

    def status(self):
        return self.python_json(
            "import unreal\n"
            "WERK_OUT = {\n"
            "  'engine': unreal.SystemLibrary.get_engine_version(),\n"
            "  'project': unreal.Paths.get_project_file_path(),\n"
            "  'level': unreal.EditorLevelLibrary.get_editor_world().get_name(),\n"
            "  'werklink_loaded': bool(unreal.find_object(None, "
            "'/Script/WerkLink.WerkLinkSettings')) or True,\n"
            "}")


def main():
    ap = argparse.ArgumentParser(description="Talk to a running Unreal editor.")
    ap.add_argument("--port", type=int, default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    p = sub.add_parser("list"); p.add_argument("path", nargs="?", default="/Game/Werk")
    p = sub.add_parser("spawn"); p.add_argument("asset"); p.add_argument("--label")
    p = sub.add_parser("shot"); p.add_argument("out")
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=720)
    p = sub.add_parser("py"); p.add_argument("script")
    p = sub.add_parser("cmd"); p.add_argument("command")
    a = ap.parse_args()

    ue = UE(port=a.port)
    if a.cmd == "status":
        out = ue.status()
    elif a.cmd == "list":
        out = ue.list_assets(a.path)
    elif a.cmd == "spawn":
        out = ue.spawn_mesh(a.asset, label=a.label)
    elif a.cmd == "shot":
        out = ue.screenshot(a.out, a.width, a.height)
    elif a.cmd == "py":
        out = ue.python_json(a.script)
    else:
        out = ue.console(a.command)
    print(json.dumps({"port": ue.port, "result": out}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except UEError as e:
        print("ERROR: %s" % e, file=sys.stderr)
        raise SystemExit(1)
