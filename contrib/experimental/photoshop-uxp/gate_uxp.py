#!/usr/bin/env python3
"""Gate for the werk UXP plug-in in Photoshop 2024 (25.x).

    py -3.12 uxp/gate_uxp.py [--json uxp/_logs/gate.json]

UXP plug-ins cannot be driven through COM or ExtendScript, and the UXP
Developer Tool is not installed, so the gate:
 1. packs this folder (manifest.json, index.js, werk.js) as werk-uxp.ccx in
    _gate_out/ and records `UnifiedPluginInstallerAgent /list all`;
 2. installs it with `UnifiedPluginInstallerAgent /install` (Adobe's own
    side-load path; recorded, and removed again in step 6);
 3. writes _selftest/request.json (the image/1 release fixtures);
 4. starts Photoshop 2024 through COM .180 (refuses if any Photoshop runs);
    the plug-in's load hook sees request.json, opens every fixture through the
    plug-in, exports image/1, re-opens it, and writes _selftest/result.json;
 5. ends the Photoshop instance it started;
 6. `UnifiedPluginInstallerAgent /remove`, and checks /list again;
 7. outside: the exports through the release readers, pixels vs the primary.
"""
import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile

UXP = os.path.dirname(os.path.abspath(__file__))
PS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(UXP))), "plugins", "photoshop")
sys.path.insert(0, os.path.join(PS, "tools"))
import werk_paths                                    # noqa: E402
import release_verify                                # noqa: E402
import adobe_com                                     # noqa: E402

REPO = werk_paths.repo_root()
LIBS = werk_paths.libs_root()
sys.path.insert(0, os.path.join(LIBS, "python"))
import werk as werklib                               # noqa: E402

UPIA = r"C:\Program Files\Common Files\Adobe\Adobe Desktop Common\RemoteComponents\UPI\UnifiedPluginInstallerAgent\UnifiedPluginInstallerAgent.exe"
WORK = os.path.join(UXP, "_gate_out")
ST = os.path.join(UXP, "_selftest")
BIN = os.path.join(UXP, "_bin")


def upia(*args, timeout=600):
    p = subprocess.run([UPIA] + list(args), capture_output=True, timeout=timeout)
    return p.returncode, (p.stdout + p.stderr).decode("utf-8", "replace")


def rgba(x):
    from PIL import Image
    return Image.open(io.BytesIO(x) if isinstance(x, bytes) else x).convert("RGBA")


def same(a, b):
    from PIL import ImageChops
    if a.size != b.size:
        return False, {"a": a.size, "b": b.size}
    ext = ImageChops.difference(a, b).getextrema()
    return max(e[1] for e in ext) == 0, {"max": [e[1] for e in ext], "size": a.size}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=os.path.join(UXP, "_logs", "gate.json"))
    ap.add_argument("--wait", type=int, default=2400)
    a = ap.parse_args()
    rows, t0 = [], time.time()

    def add(st, name, det):
        rows.append((st, name, det))
        print("[%-4s] %-48s %s" % (st, name, det))
        sys.stdout.flush()
    for d in (WORK, ST):
        if os.path.isdir(d):
            shutil.rmtree(d)
        os.makedirs(d)
    os.makedirs(os.path.dirname(a.json), exist_ok=True)
    lib = os.path.join(LIBS, "js", "dist", "werk.js")
    add("PASS" if open(lib, "rb").read() == open(os.path.join(UXP, "werk.js"), "rb").read() else "FAIL",
        "werk.js vendored byte-identical", hashlib.sha256(open(lib, "rb").read()).hexdigest()[:16])
    ccx = os.path.join(WORK, "werk-uxp.ccx")
    with zipfile.ZipFile(ccx, "w", zipfile.ZIP_DEFLATED) as z:
        for n in ("manifest.json", "index.js", "werk.js"):
            z.write(os.path.join(UXP, n), n)
    fx = json.load(open(os.path.join(REPO, "fixtures", "fixtures.json"), encoding="utf-8"))
    tasks = []
    for _n, r in fx["fixtures"].items():
        if r.get("profile") != "image/1":
            continue
        p = os.path.join(REPO, r["path"].replace("/", os.sep))
        t = os.path.basename(p).replace(".werk", "")
        tasks.append({"task": t, "in": p.replace("\\", "/"),
                      "out": os.path.join(WORK, t + "-out.werk").replace("\\", "/"),
                      "out_png": os.path.join(WORK, t + "-export.png").replace("\\", "/"),
                      "reopen_png": os.path.join(WORK, t + "-reopen.png").replace("\\", "/")})
    if adobe_com.pids(adobe_com.HOSTS["photoshop2024"][0]) or adobe_com.pids(adobe_com.HOSTS["photoshop"][0]):
        add("SKIP", "UXP run", "a Photoshop is running (not ours) - nothing installed, nothing touched")
        return finish(rows, a, t0, {})
    rc, before = upia("/list", "all")
    add("NOTE", "UPIA list before", " ".join(l.strip() for l in before.splitlines() if "Photoshop 2024" in l))
    rc, out = upia("/install", ccx)
    installed = rc == 0 and "fail" not in out.lower()
    add("PASS" if installed else "FAIL", "UPIA /install werk-uxp.ccx", "exit %s: %s" % (rc, out.strip().replace("\n", " | ")[-300:]))
    rc, mid = upia("/list", "all")
    seg = mid[mid.find("Photoshop 2024"):][:600]
    add("NOTE", "UPIA list after install", seg.strip().replace("\n", " | "))
    extra = {"upia_install": out, "upia_list_after_install": mid}
    if installed:
        json.dump({"tasks": tasks}, open(os.path.join(ST, "request.json"), "w"))
        res_p = os.path.join(ST, "result.json")
        try:
            with adobe_com.Host("photoshop2024") as h:
                add("NOTE", "Photoshop 2024", "version %s; %s" % (h.version, h.events[0]))
                ts = time.time()
                while time.time() - ts < a.wait and not os.path.exists(res_p):
                    time.sleep(5)
                time.sleep(3)
                extra["host_events"] = h.events
        except Exception as e:  # noqa: BLE001
            add("FAIL", "Photoshop 2024 start", repr(e))
        if os.path.exists(res_p):
            res = json.load(open(res_p, encoding="utf-8"))
            extra["result"] = res
            add("PASS", "plug-in loaded and ran in Photoshop", "host %s, lib %s, %d task(s)" % (res["host"], res["lib"], len(res["tasks"])))
            for r in res["tasks"]:
                add("PASS" if r.get("ok") else "FAIL", "UXP task " + r["task"], r.get("error") or "%.0f s, verdict exit %s sig %s, %sx%s" % (
                    r["seconds"], r["verdict"]["exit"], r["verdict"]["signature"], r.get("width"), r.get("height")))
                if not r.get("ok"):
                    continue
                t = [x for x in tasks if x["task"] == r["task"]][0]
                v = release_verify.verify(t["out"], BIN)
                ok, txt = release_verify.all_ok(v)
                add("PASS" if ok else "FAIL", r["task"] + ": export image/1 verified", "%d B; %s" % (os.path.getsize(t["out"]), txt))
                _n, _p, png = werklib.open(t["out"]).primary_image()
                add("PASS" if png == open(t["out_png"], "rb").read() else "FAIL", r["task"] + ": payload == Photoshop's PNG", "")
                _n, pp, pb = werklib.open(t["in"]).primary_image()
                ok1, d1 = same(rgba(pb), rgba(png))
                add("PASS" if ok1 else "NOTE", r["task"] + ": exported pixels vs the primary (Pillow)", json.dumps(d1))
                ok2, d2 = same(rgba(png), rgba(t["reopen_png"]))
                add("PASS" if ok2 else "FAIL", r["task"] + ": re-open through the plug-in == export", json.dumps(d2))
        else:
            add("FAIL", "plug-in loaded and ran in Photoshop", "no result.json within %d s" % a.wait)
        rc, out = upia("/remove", "werk")
        add("PASS" if rc == 0 else "FAIL", "UPIA /remove werk", "exit %s: %s" % (rc, out.strip().replace("\n", " | ")[-200:]))
        rc, after = upia("/list", "all")
        seg = after[after.find("Photoshop 2024"):][:300]
        add("PASS" if "werk" not in seg.split("Prelude")[0] else "FAIL", "UPIA list after remove", seg.strip().replace("\n", " | "))
    return finish(rows, a, t0, extra)


def finish(rows, a, t0, extra):
    c = {k: sum(1 for s, _, _ in rows if s == k) for k in ("PASS", "FAIL", "SKIP", "NOTE")}
    print("\n%d PASS, %d FAIL, %d SKIP, %d NOTE   (%.0f s)" % (c["PASS"], c["FAIL"], c["SKIP"], c["NOTE"], time.time() - t0))
    d = {"rows": rows, "seconds": time.time() - t0}
    d.update(extra)
    json.dump(d, open(a.json, "w", encoding="utf-8"), indent=1, default=str)
    return 1 if c["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
