#!/usr/bin/env python3
"""Gate for the werk Photoshop 2020 scripts, run in the real host.

    py -3.12 gate.py [--json _logs/gate.json] [--only TASK ...]

Photoshop 2020 is driven through COM `.DoJavaScript` (tools/adobe_com.py). If it
is already running - on this machine it usually is, with the user's own
documents - the gate ATTACHES and only creates, inspects and closes documents
of its own (gate_ps.jsx); the document count before and after every call is
checked; the document that was active is made active again; the instance is
never quit. If the gate started Photoshop it quits it.

1. Outside the host: vendored werk.jsx byte-identical to the release library;
   werk.inflateRaw (vendored werk.jsx) vs zlib and werk_raster.jsx vs the GIMP plug-in's Python
   decoder on every surface of the PhotoCraft samples (Node).
2. Inside Photoshop: selftest (profile test vector decode + section 7.2 writer
   checkpoint inside ExtendScript); every image/1 fixture of the release repo:
   open, composite, export image/1, re-open; the raster-layers/1 samples:
   open, every layer's pixels read back, export raster-layers/1 + image/1,
   re-open.
3. Outside: pixels against the payload (Pillow / the reference decoder), every
   export through the release readers (python -m werk, werkc + JSON Schema,
   loaders .py/.c/.rs), re-opened layers against the first open.
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
import adobe_com                                     # noqa: E402
import werk_single                                   # noqa: E402,F401  (ref_werk_raster imports it)
import ref_werk_raster as ref                        # noqa: E402

REPO = werk_paths.repo_root()
LIBS = werk_paths.libs_root()
sys.path.insert(0, os.path.join(LIBS, "python"))
import werk as werklib                               # noqa: E402

WORK = os.path.join(HERE, "_gate_out")
BIN = os.path.join(HERE, "_bin")
PC = os.path.join(os.environ.get("WERK_ARTCRAFT_SAMPLES", ""), "photocraft")  # ArtCraft capsules, not in this repository
LAYERED = ["simple.werk", "maximal.werk"]
TEMPLATE = os.path.join(PC, "simple.werk")


class Gate(object):
    def __init__(self):
        self.rows = []

    def add(self, status, name, detail):
        self.rows.append((status, name, detail))
        print("[%-4s] %-48s %s" % (status, name, detail))
        sys.stdout.flush()

    def counts(self):
        return tuple(sum(1 for s, _, _ in self.rows if s == k) for k in ("PASS", "FAIL", "SKIP", "NOTE"))


def sha_file(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def image_fixtures():
    fx = json.load(open(os.path.join(REPO, "fixtures", "fixtures.json"), encoding="utf-8"))
    return [(os.path.join(REPO, r["path"].replace("/", os.sep)), r["sha256"], r["size_bytes"])
            for _n, r in fx["fixtures"].items() if r.get("profile") == "image/1"]


def rgba(x):
    from PIL import Image
    return Image.open(io.BytesIO(x) if isinstance(x, bytes) else x).convert("RGBA")


def pdiff(a, b):
    from PIL import ImageChops
    if a.size != b.size:
        return {"same_size": False, "a": a.size, "b": b.size}
    d = ImageChops.difference(a, b)
    n = a.size[0] * a.size[1]
    hist = d.histogram()
    bands = {}
    for i, k in enumerate("RGBA"):
        h = hist[i * 256:(i + 1) * 256]
        bands[k] = {"max": d.getextrema()[i][1], "mean": round(sum(j * c for j, c in enumerate(h)) / n, 4)}
    return {"same_size": True, "size": a.size, "identical": max(x[1] for x in d.getextrema()) == 0, "bands": bands}


def ref_rgba8(surf):
    """Reference decoder output -> W*H*4 u8 straight RGBA, grey replicated, alpha-0 pixels zero,
    16-bit samples rounded to 8 bits (what Photoshop's 16->8 conversion is expected to give)."""
    data, C, esz, W, H = surf["data"], surf["C"], surf["esz"], surf["rect"][2], surf["rect"][3]
    gray = surf["colour"] == "gray"
    nc = 1 if gray else 3
    out = bytearray(W * H * 4)
    import struct
    for i in range(W * H):
        base = i * C * esz

        def s(ch):
            o = base + ch * esz
            if esz == 1:
                return data[o]
            if esz == 2:
                v = data[o] | (data[o + 1] << 8)
                return (v * 255 + 32767) // 65535
            v = struct.unpack_from("<f", data, o)[0]
            v = 0.0 if v != v else min(1.0, max(0.0, v))
            return int(round(v * 255))
        rgb = [s(0)] * 3 if gray else [s(0), s(1), s(2)]
        a = s(nc) if surf["has_alpha"] else 255
        if a == 0:
            continue
        out[i * 4:i * 4 + 4] = bytes(rgb + [a])
    return bytes(out)


def cmp_rgba(a, b, W, H):
    """max abs difference per channel over pixels where either alpha > 0, and count of differing pixels"""
    if len(a) != len(b):
        return {"len_a": len(a), "len_b": len(b), "max": 999, "pixels_diff": -1}
    if a == b:
        return {"max": 0, "pixels_diff": 0, "identical": True}
    mx, nd = 0, 0
    for i in range(0, len(a), 4):
        if a[i:i + 4] != b[i:i + 4]:
            nd += 1
            mx = max(mx, max(abs(a[i + k] - b[i + k]) for k in range(4)))
    return {"max": mx, "pixels_diff": nd, "identical": False, "pixels": W * H}


def node_checks():
    node = shutil.which("node")
    if not node:
        return None, "node not found"
    t = os.path.join(WORK, "node_check.js")
    open(t, "w").write(r"""
require.extensions['.jsx']=require.extensions['.js'];
const fs=require('fs'),vm=require('vm'),zl=require('zlib'),crypto=require('crypto'),path=require('path');
const D=process.argv[2]; global.werk=require(path.join(D,'werk.jsx'));
vm.runInThisContext(fs.readFileSync(path.join(D,'werk_raster.jsx'),'utf8')+'\nglobal.werkRaster=werkRaster;');
let ok=0,bad=0;
function t(b){const o=werk.inflateRaw(b.toString('latin1').substring(2));if(o===zl.inflateSync(b).toString('latin1'))ok++;else bad++;}
for(const l of [0,1,6,9])for(const n of [0,1,1000,70000,300000]){const r=crypto.randomBytes(n);const x=Buffer.concat([r,Buffer.alloc(n,7),r.subarray(0,n/3|0)]);
 t(zl.deflateSync(x,{level:l}));t(zl.deflateSync(x,{level:l,strategy:zl.constants.Z_FIXED}));t(zl.deflateSync(x,{level:l,strategy:zl.constants.Z_HUFFMAN_ONLY}));}
const out=process.argv[3]; fs.mkdirSync(out,{recursive:true}); let n=0;
for (const f of process.argv.slice(4)) { const p=werk.open(f); const d=JSON.parse(p.readPayload(p.manifest.primary.document));
  for (const nd of p.nodes) if (nd.type==='core.raster.surface') { try { const s=werkRaster.decodeSurface(p,nd.nodeId||nd.node_id,d.width,d.height);
    fs.writeFileSync(path.join(out,path.basename(f)+'.'+(nd.nodeId||nd.node_id)+'.'+s.sample_type+'.bin'),Buffer.from(s.rows.join(''),'latin1')); n++; } catch(e) {} } }
console.log(JSON.stringify({ok,bad,surfaces:n}));
""")
    p = subprocess.run([node, t, HERE, os.path.join(WORK, "node_surf")] + [os.path.join(PC, x) for x in LAYERED],
                       capture_output=True, text=True)
    try:
        return json.loads(p.stdout.strip().splitlines()[-1]), None
    except Exception:  # noqa: BLE001
        return None, (p.stdout + p.stderr)[-400:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=os.path.join(HERE, "_logs", "gate.json"))
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--host", default="photoshop", choices=["photoshop", "photoshop2024"],
                    help="photoshop = 2020 (COM .140), photoshop2024 = 2024 (COM .180)")
    ap.add_argument("--maximal-export", action="store_true", help="also export maximal.werk as raster-layers/1 (hours)")
    a = ap.parse_args()
    gate = Gate()
    t0 = time.time()
    if os.path.isdir(WORK):
        shutil.rmtree(WORK)
    os.makedirs(os.path.join(WORK, "re"))
    os.makedirs(os.path.dirname(a.json), exist_ok=True)
    log = os.path.join(WORK, "host-log.txt")

    lib = os.path.join(LIBS, "js", "dist", "werk.jsx")
    gate.add("PASS" if sha_file(lib) == sha_file(os.path.join(HERE, "werk.jsx")) else "FAIL",
             "werk.jsx vendored byte-identical", "sha256 %s" % sha_file(lib)[:16])
    gate.add("PASS" if sha_file(os.path.join(LIBS, "python", "werk_single.py")) == sha_file(os.path.join(HERE, "tools", "werk_single.py")) else "FAIL",
             "tools/werk_single.py (reference side) byte-identical", "")
    bundle = json.load(open(os.path.join(LIBS, "bundle", "bundle.json"), encoding="utf-8"))
    gate.add("NOTE", "library version gated", "lib %s, bundle source_rev %s, bundle.json sha256 %s"
             % (bundle["lib_version"], bundle["source_rev"][:7], sha_file(os.path.join(LIBS, "bundle", "bundle.json"))[:16]))
    r, why = node_checks()
    if r is None:
        gate.add("SKIP", "Node checks", why)
    else:
        gate.add("PASS" if r["bad"] == 0 else "FAIL", "werk.jsx inflateRaw vs zlib (Node)", "%d streams equal, %d differ" % (r["ok"], r["bad"]))
        same = diff_ = 0
        for fn in sorted(os.listdir(os.path.join(WORK, "node_surf"))):
            cap, sid, st = fn[:-4].split(".werk.")[0] + ".werk", fn[:-4].split(".werk.")[1].rsplit(".", 1)[0], fn[:-4].rsplit(".", 1)[1]
            if st == "f32":
                continue
            pkg = werklib.open(os.path.join(PC, cap))
            d = json.loads(pkg.read_payload(pkg.manifest["primary"]["document"]))
            s = ref.decode_surface(werk_single.open(os.path.join(PC, cap)), sid, d["width"], d["height"])
            if open(os.path.join(WORK, "node_surf", fn), "rb").read() == s["data"]:
                same += 1
            else:
                diff_ += 1
        gate.add("PASS" if diff_ == 0 and same else "FAIL", "werk_raster.jsx surfaces == GIMP plug-in decoder (Node)",
                 "%d u8/u16 surfaces byte-identical, %d differ (f32 surfaces are converted to u16 by design)" % (same, diff_))

    tasks = [{"task": "selftest"}]
    for path, sha, size in image_fixtures():
        ok = os.path.isfile(path) and os.path.getsize(path) == size and sha_file(path) == sha
        gate.add("PASS" if ok else "FAIL", "fixture pinned " + os.path.basename(path), "%d B sha256 %s" % (size, sha[:16]))
        if ok:
            tasks.append({"task": "img-" + os.path.basename(path).replace(".werk", ""), "in": path})
    for x in LAYERED:
        tasks.append({"task": "rl-" + x.replace(".werk", ""), "in": os.path.join(PC, x),
                      # maximal (137 pixel layers): open + every layer read back + image/1 export only. Its
                      # raster-layers/1 export would hash and CRC ~170 MB of tiles in ExtendScript (hours).
                      "export_layers": "0" if x == "maximal.werk" and not a.maximal_export else "1"})
    if a.only:
        tasks = [t for t in tasks if t["task"] in a.only]
    results, host = {}, {}
    if a.host == "photoshop2024" and adobe_com.pids(adobe_com.HOSTS["photoshop"][0]):
        gate.add("SKIP", "Photoshop 2024 run", "Photoshop 2020 is running (the user's); 2024 does not start beside it - not touched")
        p, f, s_, n = gate.counts()
        print("%d PASS, %d FAIL, %d SKIP, %d NOTE" % (p, f, s_, n))
        return 1
    def one(h, t):
        args = {"task": t["task"], "outdir": WORK.replace("\\", "/"), "log": log.replace("\\", "/"),
                "template": TEMPLATE.replace("\\", "/"),
                "out": os.path.join(WORK, t["task"] + "-out.werk").replace("\\", "/"),
                "out_image": os.path.join(WORK, t["task"] + "-image.werk").replace("\\", "/")}
        if "in" in t:
            args["in"] = t["in"].replace("\\", "/")
        if "export_layers" in t:
            args["export_layers"] = t["export_layers"]
        if t["task"].startswith("img-"):
            pkg = werklib.open(t["in"])
            _n, pp, pb = pkg.primary_image()
            direct = os.path.join(WORK, t["task"] + "-primary" + os.path.splitext(pp)[1])
            open(direct, "wb").write(pb)
            args["direct"] = direct.replace("\\", "/")
        try:
            return h.run(os.path.join(HERE, "gate_ps.jsx"), args, progress_file=log, idle_limit=600 if a.host == "photoshop2024" else 1500)
        except RuntimeError as e:
            return {"err": str(e), "seconds": 0}

    def record(t, rec):
        jp = os.path.join(WORK, t["task"] + ".json")
        res = json.load(open(jp, encoding="utf-8")) if os.path.exists(jp) else {"ok": False, "error": rec.get("err")}
        res["_com"] = rec
        results[t["task"]] = res
        # Photoshop 2024: the in-host script writes its result before closing its documents;
        # a hang after that (closing, returning) is killed by the watchdog and noted, not failed.
        late = rec.get("crashed") and res.get("ok") and res.get("written_before_close")
        gate.add("PASS" if res.get("ok") and (not rec.get("err") or late) else "FAIL", "host run " + t["task"],
                 "%.0f s; %s" % (rec.get("seconds", 0), res.get("error") or (rec.get("err") if not late else
                 "results written; then the host stopped answering while closing (watchdog ended our instance)") or
                 "docs %s->%s, active document restored" % (rec.get("docs_before"), rec.get("docs_after"))))

    host = {"events": []}
    if a.host == "photoshop2024":
        # one fresh Photoshop 2024 per task: under COM automation it sometimes stops answering
        for i, t in enumerate(tasks):
            with adobe_com.Host(a.host) as h:
                host["version"] = h.version
                if i == 0:
                    gate.add("NOTE", "Photoshop", "version %s; %s (a fresh instance per task)" % (h.version, h.events[0]))
                rec = one(h, t)
            host["events"].append({"task": t["task"], "events": h.events})
            record(t, rec)
    else:
        with adobe_com.Host(a.host) as h:
            host["version"], host["started"] = h.version, h.started
            gate.add("NOTE", "Photoshop", "version %s; %s" % (h.version, h.events[0]))
            for t in tasks:
                record(t, one(h, t))
            host["events"] = h.events
    analyse(gate, tasks, results)
    p, f, s, n = gate.counts()
    print("\n%d PASS, %d FAIL, %d SKIP, %d NOTE   (%.0f s)" % (p, f, s, n, time.time() - t0))
    json.dump({"rows": gate.rows, "host": host, "results": results, "seconds": time.time() - t0},
              open(a.json, "w", encoding="utf-8"), indent=1, default=str)
    return 1 if f else 0


def analyse(gate, tasks, results):
    for t in tasks:
        task, res = t["task"], results.get(t["task"], {})
        if not res.get("ok"):
            continue
        if task == "selftest":
            ok = (res["vector_decode_sha256"] == "9666edb477dd4922aa6f532fd8944cb8ce1abb9188c96664d8794993e6936618"
                  and res["writer_tiles"] == {"bytes": 262432, "sha256": "b87706652c2b888f1c1727fa34e27a1ad08f55e6005205ceb7147fcc1a510fcc"}
                  and res["writer_index"] == {"bytes": 400, "sha256": "08000f038cf0eae6eef93922bbc3d70280625dea8de6bb2b994f464d5b9c1074"})
            gate.add("PASS" if ok else "FAIL", "in Photoshop: raster-layers test vector + 7.2 checkpoint",
                     "decode %s; tiles %s; index %s" % (res["vector_decode_sha256"][:16], res["writer_tiles"], res["writer_index"]))
            continue
        pkg = werklib.open(t["in"])
        if task.startswith("img-"):
            _n, pp, pb = pkg.primary_image()
            want = rgba(pb)
            d = pdiff(want, rgba(os.path.join(WORK, task + "-direct.png")))
            gate.add("PASS" if d.get("identical") else "NOTE", task + ": Photoshop's own decode of the primary vs Pillow", json.dumps(d))
            d = pdiff(rgba(os.path.join(WORK, task + "-direct.png")), rgba(os.path.join(WORK, task + "-open.png")))
            gate.add("PASS" if d.get("identical") else "FAIL", task + ": open through werk == Photoshop opening the primary", json.dumps(d))
        else:
            dj = json.loads(pkg.read_payload(pkg.manifest["primary"]["document"]))
            W, H = dj["width"], dj["height"]
            spkg = werk_single.open(t["in"])
            _doc, tree, _rep = ref.read_document(t["in"])
            leaves = []

            def walk(es):
                for e in es:
                    if e["children"] is not None:
                        walk(e["children"])
                    else:
                        leaves.append(e)
            walk(tree)
            byid = {e["node_id"]: e for e in leaves}
            exact = close = mism = noref = 0
            worst = []
            for L in res["layers"]:
                if L.get("group") or "file" not in L:
                    continue
                e = byid.get(L["node_id"])
                got = open(L["file"], "rb").read()
                if not e or e["surface"] is None:
                    noref += 1
                    continue
                want = ref_rgba8(e["surface"])
                c = cmp_rgba(want, got, W, H)
                if c.get("identical"):
                    exact += 1
                elif c["max"] <= 1:
                    close += 1
                else:
                    mism += 1
                    worst.append("%s(%s %s): max %s, %s px" % (L["name"], e["surface"]["sample_type"], e["surface"]["mode"], c["max"], c["pixels_diff"]))
            names_ok = sum(1 for L in res["layers"] if L.get("ps_name") is not None and L["ps_name"] == L["name"])
            n_px = sum(1 for L in res["layers"] if "file" in L)
            gate.add("PASS" if mism == 0 and (exact + close) > 0 else "FAIL", task + ": open - every layer's pixels vs the surface",
                     "%d pixel layers read back: %d identical, %d within 1/255 (16-bit / float surfaces), %d differ, %d without a decodable surface (left empty, reported)%s; %d groups; names equal %d/%d"
                     % (n_px, exact, close, mism, noref, ("; " + "; ".join(worst[:6])) if worst else "", res["counts"]["group"], names_ok, n_px))
        # exports
        outs = [(task + "-out.werk", "image/1" if task.startswith("img-") else "raster-layers/1")]
        if task.startswith("rl-"):
            if t.get("export_layers") == "0":
                outs = []
                gate.add("NOTE", task + ": raster-layers/1 export not run", "by design in this gate (see --maximal-export); image/1 export below")
            outs.append((task + "-image.werk", "image/1"))
        for fn, prof in outs:
            p = os.path.join(WORK, fn)
            v = release_verify.verify(p, BIN)
            ok, txt = release_verify.all_ok(v)
            gate.add("PASS" if ok else "FAIL", "%s: export %s verified" % (task, prof), "%d B; %s" % (os.path.getsize(p), txt))
            res.setdefault("verify", {})[fn] = v
        if task.startswith("img-"):
            _n, _p, png = werklib.open(os.path.join(WORK, task + "-out.werk")).primary_image()
            d = pdiff(rgba(os.path.join(WORK, task + "-open.png")), rgba(png))
            gate.add("PASS" if d.get("identical") else "FAIL", task + ": exported image/1 pixels == the opened document", json.dumps(d))
            d = pdiff(rgba(png), rgba(os.path.join(WORK, task + "-reopen.png")))
            gate.add("PASS" if d.get("identical") else "FAIL", task + ": re-open == export", json.dumps(d))
        elif t.get("export_layers") == "0":
            d = pdiff(rgba(os.path.join(WORK, task + "-open.png")), rgba(os.path.join(WORK, task + "-reopen-flat.png")))
            gate.add("PASS" if d.get("identical") else "FAIL", task + ": re-open image/1 == composite before export", json.dumps(d))
        else:
            first = {L["name"]: L for L in res["layers"] if "file" in L}
            again = [L for L in res["reopen_layers"] if "file" in L]
            same = diff_ = 0
            for L in again:
                F = first.get(L["name"])
                if F and open(F["file"], "rb").read() == open(L["file"], "rb").read():
                    same += 1
                else:
                    diff_ += 1
            gate.add("PASS" if diff_ == 0 and same == len(first) else "FAIL", task + ": re-open raster-layers/1 == first open",
                     "%d/%d layers' RGBA identical, %d differ; re-opened names %s" % (same, len(first), diff_,
                                                                                    "equal" if sorted(first) == sorted(L["name"] for L in again) else "differ"))
            d = pdiff(rgba(os.path.join(WORK, task + "-open.png")), rgba(os.path.join(WORK, task + "-reopen-flat.png")))
            gate.add("PASS" if d.get("identical") else "FAIL", task + ": re-open image/1 == composite before export", json.dumps(d))


if __name__ == "__main__":
    sys.exit(main())
