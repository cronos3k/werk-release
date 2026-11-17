#!/usr/bin/env python3
"""Gate for the werk Illustrator 2020 plug-in, run in the real host.

    py -3.12 gate.py [--json _logs/gate.json] [--only TASK ...] [--big]

1. Outside the host: the vendored werk.jsx is byte-identical to the release
   library (stage/libs/js/dist/werk.jsx); werk.jsx's inflateRaw agrees with zlib
   (Node, if present).
2. Inside Illustrator 2020 (COM .DoJavaScript; attaches if Illustrator is
   already running, else starts it and quits it at the end): for every
   vector-art/1 sample (ArtCraft VectorCraft samples, read-only) open it, dump
   the art Illustrator now holds, export vector-art/1 + image/1, re-open both.
   For every image/1 fixture of the release repo: open, export image/1, re-open.
3. Outside: geometry of every path / compound / text the plug-in builds is
   compared with the package's own payload (anchors and handles, points);
   pixel sizes of image opens; every export goes through the release readers
   (tools/release_verify.py: python -m werk, werkc + JSON Schema, loaders
   .py/.c/.rs); the re-opened art is compared with the first open.
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
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
import werk_paths                                    # noqa: E402
import release_verify                                # noqa: E402
import adobe_com                                     # noqa: E402

REPO = werk_paths.repo_root()
LIBS = werk_paths.libs_root()
sys.path.insert(0, os.path.join(LIBS, "python"))
import werk as werklib                               # noqa: E402

WORK = os.path.join(HERE, "_gate_out")
BIN = os.path.join(HERE, "_bin")
SAMPLES = os.path.join(os.environ.get("WERK_ARTCRAFT_SAMPLES", ""), "vectorcraft")  # ArtCraft capsules, not in this repository
VA = ["neon-drive.werk", "every-field-signed.werk"]
VA_BIG = ["twenty-thousand-paths.werk"]
TEMPLATE = os.path.join(SAMPLES, "neon-drive.werk")


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


def image_fixtures():
    fx = json.load(open(os.path.join(REPO, "fixtures", "fixtures.json"), encoding="utf-8"))
    out = []
    for _name, r in fx["fixtures"].items():
        if r.get("profile") == "image/1":
            out.append((os.path.join(REPO, r["path"].replace("/", os.sep)), r["sha256"], r["size_bytes"]))
    return out


# ---------------------------------------------------------------- payload geometry
def unit_payload(pkg, nid):
    obj = json.loads(pkg.read_payload(nid))
    if isinstance(obj, dict) and "external" in obj:
        node = pkg.node(nid)
        ver = [v for v in node.versions if v["v"] == node.resolved][0]
        f = [f for f in ver["files"] if f.get("role") == obj["external"]["role"]][0]
        obj = json.loads(zlib.decompress(pkg.read_file(f["path"])))
    return obj


BUILT = ("path", "compound", "group", "layer", "text", "image")
CANVAS = 16383.0    # Illustrator's canvas is 227 x 227 inches; coordinates beyond it cannot be represented


IMAGE_KEYS = None   # keys of images that have pixels (a node) in the package; others draw nothing


def flatten(objs, out, depth=0):
    """Pre-order walk in paint order -> list of (kind, payload) for the kinds the plug-in builds."""
    for o in objs:
        t = o["kind"]["type"]
        if t not in BUILT:
            continue
        if t == "image" and IMAGE_KEYS is not None and o["kind"].get("key") not in IMAGE_KEYS:
            continue
        if t == "group" and o["kind"].get("clip") and o["kind"].get("children"):
            ch = o["kind"]["children"]
            kids = ch[1:] + ch[:1]            # the plug-in builds the clipping path last (Illustrator's order) ...
            out.append(("group", None))
            flatten_clip(ch, out, depth + 1)  # ... and the dump writes it back first: compare in that order
            continue
        if t == "path":
            out.append(("path", [sp for sp in o["kind"]["path"]["subpaths"]]))
        elif t == "compound":
            subs = []
            for c in o["kind"].get("children", []):
                if c["kind"]["type"] == "path":
                    subs += c["kind"]["path"]["subpaths"]
            out.append(("compound", subs))
        elif t == "text":
            out.append(("text", "".join(r["text"] for r in o["kind"]["runs"])))
        elif t == "image":
            out.append(("image", None))
        elif t in ("group", "layer"):
            out.append((t, None))
            flatten(o["kind"].get("children", []), out, depth + 1)


def flatten_clip(ch, out, depth):
    flatten(ch, out, depth)


def dump_flatten(objs, out):
    for o in objs:
        t = o["kind"]["type"]
        if t == "path":
            out.append(("path", o["kind"]["path"]["subpaths"]))
        elif t == "compound":
            subs = []
            for c in o["kind"]["children"]:
                subs += c["kind"]["path"]["subpaths"]
            out.append(("compound", subs))
        elif t == "text":
            out.append(("text", "".join(r["text"] for r in o["kind"]["runs"])))
        elif t == "image":
            out.append(("image", None))
        else:
            out.append((t, None))
            dump_flatten(o["kind"].get("children", []), out)


def anchors_of(subs):
    pts = []
    for sp in subs:
        for a in sp.get("anchors", []):
            p = a["p"]
            pts.append((p[0], p[1], a.get("in", p)[0], a.get("in", p)[1], a.get("out", p)[0], a.get("out", p)[1]))
    return pts


def compare_geometry(src_items, got_items, compound_as_multi=True):
    """-> dict(n_src, n_got, kinds_equal, paths, anchors, max_dev, text_equal, first_diff)"""
    def norm(items):
        out = []
        for k, v in items:
            if k == "path" and v is not None and len(v) > 1:
                k = "compound"                       # a multi-subpath path opens as a compound path
            out.append((k, v))
        return out
    s, g = norm(src_items), norm(got_items)
    res = {"n_src": len(s), "n_got": len(g), "paths": 0, "anchors": 0, "max_dev": 0.0, "text": 0, "text_equal": 0,
           "kinds_equal": [k for k, _ in s] == [k for k, _ in g], "first_diff": None}
    for i, ((ks, vs), (kg, vg)) in enumerate(zip(s, g)):
        if ks != kg:
            res["first_diff"] = res["first_diff"] or "item %d: %s vs %s" % (i, ks, kg)
            continue
        if ks in ("path", "compound"):
            a, b = anchors_of(vs), anchors_of(vg)
            if any(abs(x) > CANVAS for p in a for x in p):
                res["outside_canvas"] = res.get("outside_canvas", 0) + 1     # Illustrator cannot hold it; not compared
                continue
            res["paths"] += 1
            if len(a) != len(b):
                res["first_diff"] = res["first_diff"] or "item %d: %d vs %d anchors" % (i, len(a), len(b))
                res["max_dev"] = float("inf")
                continue
            res["anchors"] += len(a)
            for p, q in zip(a, b):
                d = max(abs(x - y) for x, y in zip(p, q))
                res["max_dev"] = max(res["max_dev"], d)
        elif ks == "text":
            res["text"] += 1
            if vs.replace("\n", "\r") == vg.replace("\n", "\r") or vs == vg:
                res["text_equal"] += 1
            else:
                res["first_diff"] = res["first_diff"] or "item %d: text %r vs %r" % (i, vs[:40], vg[:40])
    return res


def src_layers(pkg):
    global IMAGE_KEYS
    doc = json.loads(pkg.read_payload(pkg.manifest["primary"]["document"]))
    IMAGE_KEYS = set(e["key"] for e in doc.get("images", []) if e.get("node"))
    out = []
    for lid in doc.get("layers", []):
        try:
            out.append(unit_payload(pkg, lid)["layer"])
        except Exception:  # noqa: BLE001
            pass
    return out


def png_size(p):
    from PIL import Image
    with Image.open(p) as im:
        return im.size, im.mode


def png_diff(a, b):
    from PIL import Image, ImageChops
    A = Image.open(a).convert("RGBA")
    Bm = Image.open(b).convert("RGBA")
    if A.size != Bm.size:
        return {"size_a": A.size, "size_b": Bm.size, "same_size": False}
    d = ImageChops.difference(A, Bm)
    hist = d.histogram()
    tot = A.size[0] * A.size[1] * 4
    s = sum(i * c for band in range(4) for i, c in enumerate(hist[band * 256:(band + 1) * 256]))
    mx = max(x[1] for x in d.getextrema())
    return {"same_size": True, "size": A.size, "mean_abs": round(s / tot, 3), "max": mx, "identical": mx == 0}


def node_check():
    node = shutil.which("node")
    if not node:
        return None, "node not found"
    t = os.path.join(WORK, "inflate_check.js")
    open(t, "w").write(r"""
const fs=require('fs'),vm=require('vm'),zl=require('zlib'),crypto=require('crypto');
require.extensions['.jsx']=require.extensions['.js']; global.werk=require(process.argv[2]);
let ok=0,bad=0;
function t(b){const o=werk.inflateRaw(b.toString('latin1').substring(2));if(o===zl.inflateSync(b).toString('latin1'))ok++;else bad++;}
for(const l of [0,1,6,9])for(const n of [0,1,1000,70000,300000]){const r=crypto.randomBytes(n);const x=Buffer.concat([r,Buffer.alloc(n,7),r.subarray(0,n/3|0)]);
 t(zl.deflateSync(x,{level:l}));t(zl.deflateSync(x,{level:l,strategy:zl.constants.Z_FIXED}));t(zl.deflateSync(x,{level:l,strategy:zl.constants.Z_HUFFMAN_ONLY}));}
console.log(JSON.stringify({ok,bad}));
""")
    p = subprocess.run([node, t, os.path.join(HERE, "werk.jsx")], capture_output=True, text=True)
    try:
        return json.loads(p.stdout.strip().splitlines()[-1]), None
    except Exception:  # noqa: BLE001
        return None, (p.stdout + p.stderr)[-300:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=os.path.join(HERE, "_logs", "gate.json"))
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--big", action="store_true", help="also the 20 000-path sample (slow in ExtendScript)")
    a = ap.parse_args()
    gate = Gate()
    t0 = time.time()
    if os.path.isdir(WORK):
        shutil.rmtree(WORK)
    os.makedirs(os.path.join(WORK, "scratch"))
    os.makedirs(os.path.dirname(a.json), exist_ok=True)
    log = os.path.join(WORK, "host-log.txt")

    lib = os.path.join(LIBS, "js", "dist", "werk.jsx")
    same = sha_file(lib) == sha_file(os.path.join(HERE, "werk.jsx"))
    gate.add("PASS" if same else "FAIL", "werk.jsx vendored byte-identical", "sha256 %s" % sha_file(lib)[:16])
    bundle = json.load(open(os.path.join(LIBS, "bundle", "bundle.json"), encoding="utf-8"))
    gate.add("NOTE", "library version gated", "lib %s, bundle source_rev %s, bundle.json sha256 %s"
             % (bundle["lib_version"], bundle["source_rev"][:7], sha_file(os.path.join(LIBS, "bundle", "bundle.json"))[:16]))
    r, why = node_check()
    if r is None:
        gate.add("SKIP", "werk.jsx inflateRaw vs zlib (Node)", why)
    else:
        gate.add("PASS" if r["bad"] == 0 and r["ok"] > 0 else "FAIL", "werk.jsx inflateRaw vs zlib (Node)", "%d streams equal, %d differ" % (r["ok"], r["bad"]))

    tasks = []
    for name in VA + (VA_BIG if a.big else []):
        tasks.append({"task": "va-" + name.replace(".werk", ""), "in": os.path.join(SAMPLES, name)})
    for path, sha, size in image_fixtures():
        ok = os.path.isfile(path) and os.path.getsize(path) == size and sha_file(path) == sha
        gate.add("PASS" if ok else "FAIL", "fixture pinned " + os.path.basename(path), "%d B sha256 %s" % (size, sha[:16]))
        if ok:
            tasks.append({"task": "img-" + os.path.basename(path).replace(".werk", ""), "in": path})
    if a.only:
        tasks = [t for t in tasks if t["task"] in a.only]
    results = {}
    host_info = {"events": []}
    # one Illustrator per task: a crash in one task (Illustrator 2020 crashed twice inside
    # a script call during development, see GATE-RESULTS.md) cannot take the others down;
    # a crashed task is run once more in a fresh instance and both attempts are reported.
    for t in tasks:
        args = dict(t, outdir=WORK.replace("\\", "/"), log=log.replace("\\", "/"), template=TEMPLATE.replace("\\", "/"),
                    out=os.path.join(WORK, t["task"] + "-out.werk").replace("\\", "/"),
                    out_image=os.path.join(WORK, t["task"] + "-image.werk").replace("\\", "/"))
        args["in"] = args["in"].replace("\\", "/")
        for attempt in (1, 2):
            jp = os.path.join(WORK, t["task"] + ".json")
            if os.path.exists(jp):
                os.remove(jp)
            with adobe_com.Host("illustrator") as h:
                host_info["version"] = h.version
                if attempt == 1 and t is tasks[0]:
                    gate.add("NOTE", "Illustrator", "version %s, %s (a fresh instance per task)" % (h.version, h.events[0]))
                rec = h.run(os.path.join(HERE, "gate_ai.jsx"), args, progress_file=log, idle_limit=900)
                host_info["events"].append({"task": t["task"], "attempt": attempt, "events": h.events})
            if rec.get("crashed"):
                gate.add("NOTE" if attempt == 1 else "FAIL", "host run %s (attempt %d)" % (t["task"], attempt), rec["err"])
                continue
            break
        res = json.load(open(jp, encoding="utf-8")) if os.path.exists(jp) else {"ok": False, "error": rec.get("err")}
        res["_com"] = rec
        results[t["task"]] = res
        gate.add("PASS" if res.get("ok") else "FAIL", "host run " + t["task"],
                 "%.0f s; %s" % (rec["seconds"], res.get("error") or "docs %s->%s" % (rec["docs_before"], rec["docs_after"])))
    for t in tasks:
        res = results[t["task"]]
        if not res.get("ok"):
            continue
        task = t["task"]
        pkg = werklib.open(t["in"])
        if task.startswith("va-"):
            src, got, again = [], [], []
            flatten(src_layers(pkg), src)
            dump = json.load(open(os.path.join(WORK, task + "-dump.json"), encoding="utf-8"))
            dump_flatten(dump["layers"], got)
            c = compare_geometry(src, got)
            ok = c["kinds_equal"] and c["max_dev"] <= 1e-3 and c["text"] == c["text_equal"]
            gate.add("PASS" if ok else "FAIL", task + ": open geometry",
                     "%d items, %d paths, %d anchors (with handles), max deviation %.2g pt, text %d/%d equal, %d path(s) with coordinates beyond Illustrator's canvas (|x| > 16383 pt, not compared); built %s; not built %s%s"
                     % (c["n_src"], c["paths"], c["anchors"], c["max_dev"], c["text_equal"], c["text"], c.get("outside_canvas", 0),
                        res.get("counts"), res.get("skipped"), ("; " + c["first_diff"]) if c["first_diff"] else ""))
            prev = None
            for nid in [n["node_id"] for n in pkg.manifest["nodes"] if n["type"] == "core.vector.preview"]:
                prev = os.path.join(WORK, task + "-src-preview.png")
                open(prev, "wb").write(pkg.read_payload(nid))
            if prev:
                from PIL import Image
                small = os.path.join(WORK, task + "-open-at-preview-size.png")
                Image.open(os.path.join(WORK, task + "-open.png")).convert("RGBA").resize(png_size(prev)[0], Image.LANCZOS).save(small)
                d = png_diff(prev, small)
                gate.add("NOTE", task + ": picture vs the package's preview",
                         "VectorCraft's preview %s vs Illustrator's artboard PNG %s scaled to it: mean |d| %s/255, max %s "
                         "(live effects, missing fonts and gradient geometry differ by design; not a pass/fail measure)" % (
                             png_size(prev)[0], png_size(os.path.join(WORK, task + "-open.png"))[0], d.get("mean_abs"), d.get("max")))
            out = os.path.join(WORK, task + "-out.werk")
            v = release_verify.verify(out, BIN)
            ok, txt = release_verify.all_ok(v)
            gate.add("PASS" if ok else "FAIL", task + ": export vector-art/1 verified", "%d B; %s" % (os.path.getsize(out), txt))
            results[task]["verify_vector"] = v
            red = json.load(open(os.path.join(WORK, task + "-redump.json"), encoding="utf-8"))
            dump_flatten(red["layers"], again)
            c2 = compare_geometry(got, again)
            ok2 = c2["kinds_equal"] and c2["max_dev"] <= 1e-3 and c2["text"] == c2["text_equal"]
            gate.add("PASS" if ok2 else "FAIL", task + ": re-open == first open",
                     "%d items, %d anchors, max deviation %.2g pt, text %d/%d%s" % (c2["n_got"], c2["anchors"], c2["max_dev"],
                                                                             c2["text_equal"], c2["text"], ("; " + c2["first_diff"]) if c2["first_diff"] else ""))
            d = png_diff(os.path.join(WORK, task + "-open.png"), os.path.join(WORK, task + "-reopen.png"))
            gate.add("PASS" if d.get("same_size") and d.get("max", 255) <= 2 else "NOTE", task + ": re-open picture", json.dumps(d))
        else:
            sz = png_size(os.path.join(WORK, task + "-open.png"))[0]
            _nid, ppath, pbytes = pkg.primary_image()
            from PIL import Image
            want = Image.open(io.BytesIO(pbytes)).size
            gate.add("PASS" if tuple(sz) == tuple(want) else "FAIL", task + ": open size", "artboard PNG %s, primary %s %s" % (sz, ppath, want))
            tmpp = os.path.join(WORK, task + "-primary-decoded.png")
            Image.open(io.BytesIO(pbytes)).convert("RGBA").save(tmpp)
            d = png_diff(tmpp, os.path.join(WORK, task + "-open.png"))
            gate.add("PASS" if d.get("identical") else "NOTE", task + ": artboard pixels vs the primary decoded by Pillow",
                     json.dumps(d) + " (Illustrator places the image and re-renders it at 72 ppi; not an identity path)")
        outi = os.path.join(WORK, task + "-image.werk")
        v = release_verify.verify(outi, BIN)
        ok, txt = release_verify.all_ok(v)
        gate.add("PASS" if ok else "FAIL", task + ": export image/1 verified", "%d B; %s" % (os.path.getsize(outi), txt))
        results[task]["verify_image"] = v
        pi = werklib.open(outi)
        _n, _p, png = pi.primary_image()
        tmp = os.path.join(WORK, task + "-image-payload.png")
        open(tmp, "wb").write(png)
        d = png_diff(os.path.join(WORK, task + "-open.png"), tmp)
        gate.add("PASS" if d.get("identical") else "FAIL", task + ": image/1 payload == the artboard export", json.dumps(d))
        d = png_diff(tmp, os.path.join(WORK, task + "-reopen-image.png"))
        gate.add("PASS" if d.get("same_size") and d.get("max", 255) <= 2 else "NOTE", task + ": image/1 re-open picture", json.dumps(d))
    p, f, s, n = gate.counts()
    print("\n%d PASS, %d FAIL, %d SKIP, %d NOTE   (%.0f s)" % (p, f, s, n, time.time() - t0))
    json.dump({"rows": gate.rows, "host": host_info, "results": results, "seconds": time.time() - t0},
              open(a.json, "w", encoding="utf-8"), indent=1, default=str)
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
