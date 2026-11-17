"""Drive an Adobe host (Photoshop 2020 / Illustrator 2020) through COM `.DoJavaScript`.

    with Host("illustrator") as h:          # attaches if running, else starts it
        h.run(script_path, {"task": ...})   # evaluates the script with WERK_ARGS set

Desktop safety (W5b rules):
  * If the host is already running (the user's own instance) we ATTACH and never
    quit it; scripts must only touch documents they create. The document count
    before/after every call is recorded and a change is an error.
  * If we started it, we quit it at the end and kill the process if Quit leaves it
    alive (Illustrator 2020 does, see plugins/_recon/HOSTS.md).
  * One COM call at a time, on one thread; a call has no timeout (ExtendScript
    cannot be interrupted from outside, so a timeout would only orphan it). The
    in-host scripts write a progress log instead.
"""
import json
import os
import subprocess
import time

import psutil
import pythoncom
import win32com.client as wc

HOSTS = {
    "photoshop": (r"C:\Program Files\Adobe\Adobe Photoshop 2020\Photoshop.exe", "Photoshop.Application.140"),
    "photoshop2024": (r"C:\Program Files\Adobe\Adobe Photoshop 2024\Photoshop.exe", "Photoshop.Application.180"),
    "illustrator": (r"C:\Program Files\Adobe\Adobe Illustrator 2020\Support Files\Contents\Windows\Illustrator.exe",
                    "Illustrator.Application.24"),
}


def pids(exe):
    out = set()
    for p in psutil.process_iter(["exe"]):
        try:
            if p.info["exe"] and os.path.normcase(p.info["exe"]) == os.path.normcase(exe):
                # a crashed instance's crash-dump child lingers with no handles and cannot be
                # opened or killed (seen after Illustrator 2020 crashed): not a running host
                if p.num_handles() == 0:
                    continue
                out.add(p.pid)
        except Exception:
            pass
    return out


def window_titles(pid):
    """Titles of the visible top-level windows of one process (Win32)."""
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    out = []
    proto = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(h, _l):
        p = wintypes.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid and u.IsWindowVisible(h):
            buf = ctypes.create_unicode_buffer(512)
            u.GetWindowTextW(h, buf, 512)
            out.append(buf.value)
        return True
    u.EnumWindows(proto(cb), 0)
    return out


class Host(object):
    def __init__(self, name):
        self.name = name
        self.exe, self.progid = HOSTS[name]
        self.app = None
        self.started = False
        self.before = set()
        self.events = []
        self.crashed = False

    def __enter__(self):
        pythoncom.CoInitialize()
        self.before = pids(self.exe)
        t = time.time()
        if self.before:
            self.app = wc.Dispatch(self.progid)
            self.events.append("attached to running %s pid %s" % (self.name, sorted(self.before)))
        elif self.name.startswith("photoshop"):
            # Start Photoshop as a normal (visible) application and attach to it: an
            # instance COM starts itself ("/Automation -Embedding", no window) refused
            # saves and stopped answering in this work, in 2024 and in 2020 alike, while
            # the same scripts ran cleanly in a normally started Photoshop.
            subprocess.Popen([self.exe], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.started = True
            deadline, last = time.time() + 600, None
            while time.time() < deadline:
                time.sleep(10)
                try:
                    self.app = wc.Dispatch(self.progid)
                    int(self.app.Documents.Count)
                    break
                except Exception as e:  # noqa: BLE001
                    last = e
                    self.app = None
            if self.app is None:
                raise RuntimeError("Photoshop did not answer COM within 600 s: %r" % last)
            self.events.append("started %s as a normal application (%.0f s)" % (self.name, time.time() - t))
        else:
            try:
                self.app = wc.DispatchEx(self.progid)
            except Exception as e:  # noqa: BLE001  (Photoshop 2024 sometimes: 'Server execution failed')
                self.events.append("first start failed: %r; retrying once in 30 s" % e)
                for p in pids(self.exe) - self.before:
                    subprocess.run(["taskkill", "/PID", str(p), "/T", "/F"], capture_output=True)
                time.sleep(30)
                self.app = wc.DispatchEx(self.progid)
            self.started = True
            self.events.append("started %s (%.0f s)" % (self.name, time.time() - t))
        try:
            self.version = str(self.app.Version)
        except Exception as e:  # noqa: BLE001
            self.version = "?(%r)" % e
        return self

    def docs(self):
        try:
            return int(self.app.Documents.Count)
        except Exception:
            return -1

    def _watch(self, stop, box, progress_file, idle_limit):
        """Watchdog for an instance WE started: Illustrator 2020 sometimes crashes inside a
        script call (it spawns a crash-dump child Illustrator.exe and the COM call never
        returns). On such a child, or when the in-host progress log has not moved for
        idle_limit seconds, kill our own instance so the call returns with an error."""
        mine = pids(self.exe) - self.before
        while not stop.wait(5):
            try:
                kids = [c.pid for p in mine for c in psutil.Process(p).children() if c.name().lower() == os.path.basename(self.exe).lower()]
            except Exception:  # noqa: BLE001
                kids = []
            idle = None
            if progress_file and os.path.exists(progress_file):
                idle = time.time() - os.path.getmtime(progress_file)
            dialogs = [t for p in mine for t in window_titles(p) if t in ("Save As", "Save a Copy")]
            if kids or dialogs or (idle is not None and idle > idle_limit):
                box["killed"] = ("child %s" % kids if kids else
                                 "the host opened its '%s' dialog (nobody can answer it in a gate)" % dialogs[0] if dialogs else
                                 "no progress for %.0f s" % idle)
                for p in mine:
                    subprocess.run(["taskkill", "/PID", str(p), "/T", "/F"], capture_output=True)
                return

    def run(self, script, args, progress_file=None, idle_limit=1200):
        import threading
        script = os.path.abspath(script).replace("\\", "/")
        src = "var WERK_ARGS = %s;\n$.evalFile(new File(%s));" % (json.dumps(args), json.dumps(script))
        n0 = self.docs()
        t = time.time()
        stop, box = threading.Event(), {}
        wd = None
        if self.started:
            wd = threading.Thread(target=self._watch, args=(stop, box, progress_file, idle_limit), daemon=True)
            wd.start()
        try:
            ret = self.app.DoJavaScript(src)
            err = None
        except Exception as e:  # noqa: BLE001
            ret, err = None, repr(e)
        stop.set()
        if "killed" in box:
            self.crashed = True
            err = "HOST CRASHED / HUNG (%s); our own instance was killed by the watchdog. COM: %s" % (box["killed"], err)
            rec = {"task": args.get("task"), "seconds": round(time.time() - t, 1), "ret": None, "err": err,
                   "docs_before": n0, "docs_after": None, "crashed": True}
            self.events.append(rec)
            return rec
        n1 = self.docs()
        rec = {"task": args.get("task"), "seconds": round(time.time() - t, 1), "ret": ret, "err": err,
               "docs_before": n0, "docs_after": n1}
        self.events.append(rec)
        if n0 != n1:
            raise RuntimeError("document count changed %d -> %d during %s" % (n0, n1, args.get("task")))
        return rec

    def __exit__(self, *exc):
        if self.started and not self.crashed:
            # Photoshop 2024's COM Quit() can block forever: call it on a helper thread
            # (marshalled), wait at most 60 s, then end our own instance below.
            import threading
            box = {}
            try:
                stream = pythoncom.CreateStreamOnHGlobal()
                pythoncom.CoMarshalInterface(stream, pythoncom.IID_IDispatch, self.app._oleobj_, pythoncom.MSHCTX_LOCAL, pythoncom.MSHLFLAGS_NORMAL)
                stream.Seek(0, 0)
            except Exception as e:  # noqa: BLE001
                stream = None
                box["marshal"] = repr(e)

            def _quit():
                pythoncom.CoInitialize()
                try:
                    disp = pythoncom.CoUnmarshalInterface(stream, pythoncom.IID_IDispatch)
                    wc.Dispatch(disp).Quit()
                    box["ok"] = True
                except Exception as e:  # noqa: BLE001
                    box["err"] = repr(e)
            if stream is not None:
                th = threading.Thread(target=_quit, daemon=True)
                th.start()
                th.join(60)
                self.events.append("Quit(): %s" % ("returned" if box.get("ok") else box.get("err", "no return in 60 s")))
            else:
                self.events.append("Quit() not called: %s" % box.get("marshal"))
        self.app = None
        if self.started:
            time.sleep(8)
            left = pids(self.exe) - self.before
            for p in left:
                subprocess.run(["taskkill", "/PID", str(p), "/T", "/F"], capture_output=True)
            if left:
                self.events.append("killed own instance %s after Quit" % sorted(left))
        # no CoUninitialize: with a killed server it can block; the process ends anyway
        return False
