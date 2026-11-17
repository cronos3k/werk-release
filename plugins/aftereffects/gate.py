#!/usr/bin/env python3
"""Gate for the werk After Effects 2020 scripts, run in the real host.

    py -3.12 gate.py [--json _logs/gate.json]

Runs `AfterFX.exe -noui -r <runner>` once (refuses if After Effects is already
running: that instance would not be ours). Inside: every image/1 fixture of
the release repo is imported as footage through werk_ae_lib.jsx, a comp of its
size renders frame 0 (comp.saveFrameToPng), the frame is exported as image/1,
and that export is imported again; a synthetic comp (two solids) is exported.
Outside: the footage's size and the rendered frame's pixels are compared with
the primary image the release library extracts (decoded by Pillow), every
export goes through the release readers (python -m werk, werkc + schema,
loaders .py/.c/.rs), the exported PNG is compared with the frame, and the
synthetic frame's pixels are checked against the solids' colours.
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

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
import werk_paths                                    # noqa: E402
import release_verify                                # noqa: E402
import psutil                                        # noqa: E402

REPO = werk_paths.repo_root()
LIBS = werk_paths.libs_root()
sys.path.insert(0, os.path.join(LIBS, "python"))
import werk as werklib                               # noqa: E402

EXE = r"C:\Program Files\Adobe\Adobe After Effects 2020\Support Files\AfterFX.exe"
WORK = os.path.join(HERE, "_gate_out")
BIN = os.path.join(HERE, "_bin")
MOTION = os.path.join(os.environ.get("WERK_ARTCRAFT_SAMPLES", ""), "effectcraft", "intro.werk")   # read-only ArtCraft sample
TPS = 254016000000


class Gate(object):
    def __init__(self):
        self.rows = []

    def add(self, status, name, detail):
        self.rows.append((status, name, detail))
        print("[%-4s] %-46s %s" % (status, name, detail))
        sys.stdout.flush()

    def counts(self):
        return tuple(sum(1 for s, _, _ in self.rows if s == k) for k in ("PASS", "FAIL", "SKIP", "NOTE"))


def sha_file(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def ae_pids():
    out = set()
    for p in psutil.process_iter(["name"]):
        try:
            if (p.info["name"] or "").lower() in ("afterfx.exe", "afterfx.com", "aerender.exe"):
                out.add(p.pid)
        except Exception:
            pass
    return out


def image_fixtures():
    fx = json.load(open(os.path.join(REPO, "fixtures", "fixtures.json"), encoding="utf-8"))
    return [(os.path.join(REPO, r["path"].replace("/", os.sep)), r["sha256"], r["size_bytes"])
            for _n, r in fx["fixtures"].items() if r.get("profile") == "image/1"]


def rgba(p_or_bytes):
    from PIL import Image
    im = Image.open(io.BytesIO(p_or_bytes) if isinstance(p_or_bytes, bytes) else p_or_bytes)
    return im.convert("RGBA")


def diff(a, b):
    from PIL import ImageChops
    if a.size != b.size:
        return {"same_size": False, "a": a.size, "b": b.size}
    d = ImageChops.difference(a, b)
    ext = d.getextrema()
    hist = d.histogram()
    n = a.size[0] * a.size[1]
    per = {}
    for i, band in enumerate("RGBA"):
        h = hist[i * 256:(i + 1) * 256]
        per[band] = {"max": ext[i][1], "mean": round(sum(k * c for k, c in enumerate(h)) / n, 4), "nonzero": n - h[0]}
    return {"same_size": True, "size": a.size, "identical": max(x[1] for x in d.getextrema()) == 0, "bands": per}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=os.path.join(HERE, "_logs", "gate.json"))
    ap.add_argument("--wait", type=int, default=7200)
    a = ap.parse_args()
    gate = Gate()
    t0 = time.time()
    if os.path.isdir(WORK):
        shutil.rmtree(WORK)
    os.makedirs(os.path.join(WORK, "scratch"))
    os.makedirs(os.path.dirname(a.json), exist_ok=True)
    lib = os.path.join(LIBS, "js", "dist", "werk.jsx")
    gate.add("PASS" if sha_file(lib) == sha_file(os.path.join(HERE, "werk.jsx")) else "FAIL",
             "werk.jsx vendored byte-identical", "sha256 %s" % sha_file(lib)[:16])
    bundle = json.load(open(os.path.join(LIBS, "bundle", "bundle.json"), encoding="utf-8"))
    gate.add("NOTE", "library version gated", "lib %s, bundle source_rev %s, bundle.json sha256 %s"
             % (bundle["lib_version"], bundle["source_rev"][:7], sha_file(os.path.join(LIBS, "bundle", "bundle.json"))[:16]))
    tasks = []
    for path, sha, size in image_fixtures():
        ok = os.path.isfile(path) and os.path.getsize(path) == size and sha_file(path) == sha
        gate.add("PASS" if ok else "FAIL", "fixture pinned " + os.path.basename(path), "%d B sha256 %s" % (size, sha[:16]))
        if ok:
            tasks.append({"task": "img-" + os.path.basename(path).replace(".werk", ""), "in": path.replace("\\", "/")})
    if ae_pids():
        gate.add("SKIP", "After Effects run", "After Effects is already running (pid %s) - not ours, not touched" % sorted(ae_pids()))
        return finish(gate, a, t0, {})
    log = os.path.join(WORK, "host-log.txt")
    args = {"outdir": WORK.replace("\\", "/"), "log": log.replace("\\", "/"), "tasks": tasks, "synthetic": True}
    if os.path.isfile(MOTION):
        mp = werklib.open(MOTION)
        poster = [n for n in mp.manifest["nodes"] if n["type"] == "core.preview.poster"]
        ip = poster[0]["versions"][-1]["input_params"] if poster else {}
        args.update(motion=MOTION.replace("\\", "/"), poster_comp=ip.get("comp"), poster_tick=ip.get("tick"))
    runner = os.path.join(WORK, "runner.jsx")
    open(runner, "w", encoding="utf-8").write("var WERK_ARGS = %s;\n$.evalFile(new File(%s));\n"
                                              % (json.dumps(args), json.dumps(os.path.join(HERE, "gate_ae.jsx").replace("\\", "/"))))
    cmd = [EXE, "-noui", "-r", runner]
    ts = time.time()
    p = subprocess.Popen(cmd)
    state = "TIMEOUT"
    while time.time() - ts < a.wait:
        if p.poll() is not None:
            state = "exit %s" % p.returncode
            break
        if os.path.exists(log) and "ALL DONE" in open(log, encoding="utf-8", errors="replace").read():
            dd = time.time()
            while time.time() - dd < 30 and p.poll() is None:
                time.sleep(1)
            state = "script done; " + ("exit %s" % p.returncode if p.poll() is not None else "app.quit() did not exit in 30 s")
            break
        time.sleep(3)
    killed = []
    if p.poll() is None:
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
        killed.append(p.pid)
    time.sleep(3)
    for pid in ae_pids():           # children After Effects spawned for this run (none existed before)
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        killed.append(pid)
    host = {"command": " ".join(cmd), "state": state, "seconds": round(time.time() - ts, 1), "killed": killed,
            "log": open(log, encoding="utf-8", errors="replace").read() if os.path.exists(log) else None}
    gate.add("PASS" if "script done" in state else "FAIL", "After Effects run", "%s, %.0f s%s" % (state, host["seconds"], ", killed %s" % killed if killed else ""))
    results = {}
    if args.get("motion"):
        analyse_motion(gate, results)
    for t in tasks + [{"task": "synthetic"}]:
        jp = os.path.join(WORK, t["task"] + ".json")
        res = json.load(open(jp, encoding="utf-8")) if os.path.exists(jp) else {"ok": False, "error": "no result file"}
        results[t["task"]] = res
        gate.add("PASS" if res.get("ok") else "FAIL", "host run " + t["task"], res.get("error") or "%.0f s" % res.get("seconds", 0))
        if not res.get("ok"):
            continue
        if t["task"] != "synthetic":
            pkg = werklib.open(t["in"])
            _n, ppath, pbytes = pkg.primary_image()
            want = rgba(pbytes)
            ok = res["media_sha256"] == hashlib.sha256(pbytes).hexdigest() and (res["footage"]["width"], res["footage"]["height"]) == want.size
            gate.add("PASS" if ok else "FAIL", t["task"] + ": imported footage", "%s %dx%d, media file sha256 %s the primary %s"
                     % (res["footage"]["typename"], res["footage"]["width"], res["footage"]["height"],
                        "==" if res["media_sha256"] == hashlib.sha256(pbytes).hexdigest() else "!=", ppath))
            d = diff(want, rgba(os.path.join(WORK, t["task"] + "-open.png")))
            gate.add("PASS" if d.get("identical") else ("NOTE" if d.get("same_size") else "FAIL"), t["task"] + ": rendered frame vs primary pixels", json.dumps(d))
            frame = os.path.join(WORK, t["task"] + "-open.png")
        else:
            frame = None
        out = os.path.join(WORK, t["task"] + "-out.werk")
        v = release_verify.verify(out, BIN)
        ok, txt = release_verify.all_ok(v)
        gate.add("PASS" if ok else "FAIL", t["task"] + ": export image/1 verified", "%d B; %s" % (os.path.getsize(out), txt))
        res["verify"] = v
        _n, _p, png = werklib.open(out).primary_image()
        if frame:
            gate.add("PASS" if open(frame, "rb").read() == png else "FAIL", t["task"] + ": exported PNG == the frame After Effects wrote",
                     "sha256 %s" % hashlib.sha256(png).hexdigest()[:16])
            d = diff(rgba(png), rgba(os.path.join(WORK, t["task"] + "-reopen.png")))
            gate.add("PASS" if d.get("identical") else "NOTE", t["task"] + ": re-import frame == exported frame", json.dumps(d))
        else:
            im = rgba(png)
            px = {"(10,10)": im.getpixel((10, 10)), "(300,170)": im.getpixel((300, 170)), "size": im.size}
            ok = im.size == (320, 180) and im.getpixel((10, 10))[:3] == (0, 0, 255) and im.getpixel((300, 170))[:3] == (255, 0, 0)
            gate.add("PASS" if ok else "FAIL", "synthetic: frame pixels", "blue solid left, red right: %s" % px)
    return finish(gate, a, t0, {"host": host, "results": results})


def read_tracks(b):
    import struct
    _m, _v, h = werklib.read_envelope(b)
    sec = {x["name"]: x["offset"] for x in h["sections"]}
    out = []
    for t in h["tracks"]:
        c, keys = t["components"], []
        for j in range(t["keys"]):
            k = t["first_key"] + j
            v = [struct.unpack_from("<d", b, sec["value"] + 8 * (t["first_value"] + j * c + q))[0] for q in range(c)]
            keys.append((struct.unpack_from("<q", b, sec["at"] + 8 * k)[0], v, h["interpolations"][b[sec["interp"] + 2 * k]],
                         h["interpolations"][b[sec["interp"] + 2 * k + 1]]))
        out.append({"uid": t["uid"], "keys": keys})
    return out


AE_OF = {"anchor": "ADBE Anchor Point", "position": "ADBE Position", "scale": "ADBE Scale", "orientation": "ADBE Orientation",
         "rotationX": "ADBE Rotate X", "rotationY": "ADBE Rotate Y", "rotation": "ADBE Rotate Z", "opacity": "ADBE Opacity"}


def analyse_motion(gate, results):
    jp = os.path.join(WORK, "motion.json")
    res = json.load(open(jp, encoding="utf-8")) if os.path.exists(jp) else {"ok": False, "error": "no result file"}
    results["motion"] = res
    gate.add("PASS" if res.get("ok") else "FAIL", "host run motion-comp/1 import (partial)", res.get("error") or "%.0f s; built %s" % (res.get("seconds", 0), res.get("counts")))
    if not res.get("ok"):
        return
    pkg = werklib.open(MOTION)
    proj = json.loads(pkg.read_payload(pkg.manifest["primary"]["document"]))
    want_comps = {it["id"]: json.loads(pkg.read_payload(it["node"])) for it in proj["items"] if it["kind"] == "comp"}
    got = {c["id"]: c for c in res["comps"]}
    ok = sorted(got) == sorted(want_comps)
    bad = []
    for cid, cj in want_comps.items():
        c, g = cj["comp"], got.get(cid)
        if not g:
            continue
        fr = c["frame_rate"]["num"] / c["frame_rate"]["den"]
        if (g["width"], g["height"]) != (c["width"], c["height"]) or abs(g["frameRate"] - fr) > 1e-4 or abs(g["duration"] - c["duration"] / TPS) > 0.5 / fr:
            bad.append("comp %s settings" % cid)
        if len(g["layers"]) != len(cj["layers"]):
            bad.append("comp %s: %d layers vs %d" % (cid, len(g["layers"]), len(cj["layers"])))
    gate.add("PASS" if ok and not bad else "FAIL", "motion: compositions (size, rate, duration, layer count)",
             "%d comps; %s" % (len(want_comps), "; ".join(bad) or "all equal"))
    nkeys = nprops = nstatic = nclamp = naudio = 0
    worst, timing_bad, kbad = 0.0, [], []
    items = {it["id"]: json.loads(pkg.read_payload(it["node"])) for it in proj["items"] if it["kind"] != "comp"}
    for cid, cj in want_comps.items():
        g = got.get(cid)
        if not g:
            continue
        half = 0.5 * cj["comp"]["frame_rate"]["den"] / cj["comp"]["frame_rate"]["num"]   # After Effects puts times on frames
        for idx, lref in enumerate(cj["layers"]):
            lj = json.loads(pkg.read_payload(lref["node"]))
            L = lj["layer"]
            gl = g["layers"][idx] if idx < len(g["layers"]) else None
            if not gl or gl["name"] != L["name"]:
                timing_bad.append("%s: order/name" % L["name"])
                continue
            src = L.get("source", {})
            sdur = None
            if src.get("type") == "Comp" and src.get("item") in want_comps:
                sdur = want_comps[src["item"]]["comp"]["duration"] / TPS
            elif src.get("type") == "Footage" and src.get("item") in items:
                fd = items[src["item"]]["kind"].get("Footage", {}).get("duration") or 0
                sdur = fd / TPS if fd else None
            want_out = L["out_point"] / TPS
            if sdur is not None and want_out > L.get("start_time", 0) / TPS + sdur:
                want_out = L.get("start_time", 0) / TPS + sdur      # After Effects ends a layer with its source
                nclamp += 1
            for k, want in (("inPoint", L["in_point"] / TPS), ("outPoint", want_out), ("startTime", L.get("start_time", 0) / TPS)):
                if abs(gl[k] - want) > half:
                    timing_bad.append("%s.%s %.6f vs %.6f" % (L["name"], k, gl[k], want))
            if src.get("type") == "Footage" and items.get(src.get("item"), {}).get("kind", {}).get("Footage", {}).get("has_video") is False:
                naudio += 1
                continue                                              # an audio layer has no visible transform
            tracks = read_tracks(pkg.read_payload(lj["tracks"])) if lj.get("tracks") else []
            tg = [x for x in L["props"]["children"] if x.get("match") == "transform"]
            for p in (tg[0]["children"] if tg else []):
                if p["match"] not in AE_OF or AE_OF[p["match"]] not in gl["props"]:
                    continue
                gp = gl["props"][AE_OF[p["match"]]]
                nprops += 1
                if p.get("track") is not None:
                    keys = tracks[p["track"]]["keys"]
                    if gp["numKeys"] != len(keys):
                        kbad.append("%s.%s: %d keys vs %d" % (L["name"], p["match"], gp["numKeys"], len(keys)))
                        continue
                    for (at, v, ii, oi), gk in zip(keys, gp["keys"]):
                        nkeys += 1
                        if abs(gk["t"] - (L.get("start_time", 0) + at) / TPS) > half:
                            kbad.append("%s.%s key time" % (L["name"], p["match"]))
                        gv = gk["v"] if isinstance(gk["v"], list) else [gk["v"]]
                        worst = max([worst] + [abs(a - b) for a, b in zip(v, gv)])
                elif p.get("value") and p["value"]["t"] in ("Scalar", "Vec2", "Vec3") and "value0" in gp:
                    nstatic += 1
                    v = p["value"]["v"] if isinstance(p["value"]["v"], list) else [p["value"]["v"]]
                    gv = gp["value0"] if isinstance(gp["value0"], list) else [gp["value0"]]
                    worst = max([worst] + [abs(a - b) for a, b in zip(v, gv)])
    gate.add("PASS" if not timing_bad else "FAIL", "motion: layer order, names, in / out / start times",
             "%s; times compared to half a frame (After Effects puts them on frames); %d out point(s) past the end of the "
             "layer's source are expected at the source's end (After Effects ends the layer there)"
             % ("; ".join(timing_bad[:8]) or "all equal (%d comps)" % len(want_comps), nclamp))
    gate.add("PASS" if not kbad and worst <= 1e-4 else "FAIL", "motion: transform values and keyframes",
             "%d transform properties, %d static values, %d keyframes (time to half a frame + value); max |value difference| %.3g; %d audio-only layer(s) skipped (no transform in After Effects)%s"
             % (nprops, nstatic, nkeys, worst, naudio, ("; " + "; ".join(kbad[:6])) if kbad else ""))
    fr = os.path.join(WORK, "motion-poster-frame.png")
    pn = [n for n in pkg.manifest["nodes"] if n["type"] == "core.preview.poster"]
    if os.path.exists(fr) and pn:
        from PIL import Image
        want = rgba(pkg.read_payload(pn[0]["node_id"]))
        gotim = rgba(fr).resize(want.size, Image.BILINEAR)
        d = diff(want, gotim)
        gate.add("NOTE", "motion: poster frame vs EffectCraft's poster", "After Effects frame scaled to %s; %s (shape contents, effects, text styling not built: a large difference is expected)"
                 % (want.size, json.dumps(d.get("bands"))))


def finish(gate, a, t0, extra):
    p, f, s, n = gate.counts()
    print("\n%d PASS, %d FAIL, %d SKIP, %d NOTE   (%.0f s)" % (p, f, s, n, time.time() - t0))
    d = {"rows": gate.rows, "seconds": time.time() - t0}
    d.update(extra)
    json.dump(d, open(a.json, "w", encoding="utf-8"), indent=1, default=str)
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
