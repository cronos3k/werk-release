# The half of gate.py that runs INSIDE GIMP (python-fu-eval). Measures only.
#   gimp-console -i -n -d -f -c --batch-interpreter python-fu-eval \
#       -b "exec(open(r'<this file>').read())" --quit
# Reads $WERK_GIMP_GATE_PAYLOAD (JSON), writes payload["result"].
import hashlib
import json
import os
import sys
import traceback

import gi
gi.require_version("Gimp", "3.0")
gi.require_version("Gegl", "0.4")
from gi.repository import Gimp, Gegl, Gio  # noqa: E402

P = json.load(open(os.environ["WERK_GIMP_GATE_PAYLOAD"], encoding="utf-8"))
sys.path.insert(0, P["plugin_dir"])
import werk_raster  # noqa: E402  (the plug-in's own decoder, for the layer check)

PDB = Gimp.get_pdb()


def sha(b):
    return hashlib.sha256(b).hexdigest()


def drawable_bytes(d, W, H, fmt="R'G'B'A u8"):
    ok, ox, oy = d.get_offsets()
    return bytes(d.get_buffer().get(Gegl.Rectangle.new(-ox, -oy, W, H), 1.0, fmt,
                                    Gegl.AbyssPolicy.NONE))


def merged(img):
    W, H = img.get_width(), img.get_height()
    dup = img.duplicate()
    try:
        L = dup.merge_visible_layers(Gimp.MergeType.CLIP_TO_IMAGE)
        return drawable_bytes(L, W, H), W, H
    finally:
        dup.delete()


def leaves(layers):
    out = []
    for L in reversed(list(layers)):
        out += leaves(L.get_children()) if L.is_group() else [L]
    return out


def count_all(layers):
    n = 0
    for L in layers:
        n += 1
        if L.is_group():
            n += count_all(L.get_children())
    return n


def load(path):
    return Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(path))


def export(img, path, profile="image/1", template=""):
    proc = PDB.lookup_procedure("file-werk-export")
    cfg = proc.create_config()
    cfg.set_property("run-mode", Gimp.RunMode.NONINTERACTIVE)
    cfg.set_property("image", img)
    cfg.set_property("file", Gio.File.new_for_path(path))
    cfg.set_property("profile", profile)
    cfg.set_property("template", template)
    res = proc.run(cfg)
    return str(res.index(0)), (res.index(1) if res.length() > 1 else None)


def run_image(fx):
    r = {"key": fx["key"], "profile": "image/1"}
    img = load(fx["path"])
    px, W, H = merged(img)
    r["open"] = {"size": [W, H], "layers": len(img.get_layers()),
                 "pixels_sha256": sha(px), "precision": img.get_precision().value_nick}
    ref = load(fx["extracted_primary"])
    rpx, rW, rH = merged(ref)
    r["reference"] = {"size": [rW, rH], "pixels_sha256": sha(rpx)}
    ref.delete()
    out = os.path.join(P["out_dir"], fx["key"] + ".gimp-export.werk")
    r["export"] = {"path": out, "status": export(img, out)[0]}
    img.delete()
    back = load(out)
    bpx, bW, bH = merged(back)
    r["reopen"] = {"size": [bW, bH], "pixels_sha256": sha(bpx)}
    back.delete()
    return r


def run_layers(fx):
    r = {"key": fx["key"], "profile": "raster-layers/1"}
    img = load(fx["path"])
    W, H = img.get_width(), img.get_height()
    doc, tree, rep = werk_raster.read_document(fx["path"])
    want = []

    def walk(items):
        for it in items:
            if it["children"] is not None:
                walk(it["children"])
            else:
                want.append(it)
    walk(tree)
    got = leaves(img.get_layers())
    exact, compared, converted = 0, 0, 0
    mism = []
    for it, L in zip(want, got):
        s = it["surface"]
        if s is None:
            continue
        # the plug-in opens at the deepest precision present, so every surface
        # must read back byte-identical in its own format
        native = True
        if not native:
            converted += 1
            continue
        compared += 1
        if s["colour"] == "gray":
            # read back as RGB(A) and take R (+A): GIMP stores gray as R=G=B,
            # and re-deriving Y' from RGB rounds in the last bit for floats
            t = werk_raster.BABL_TYPE[s["sample_type"]]
            fmt = "R'G'B'%s %s" % ("A" if s["has_alpha"] else "", t)
            raw = drawable_bytes(L, W, H, fmt)
            k = s["esz"]
            n = 4 if s["has_alpha"] else 3
            px = [raw[i:i + k] for i in range(0, len(raw), k)]
            b = b"".join(px[j] + (px[j + 3] if s["has_alpha"] else b"")
                         for j in range(0, len(px), n))
        else:
            b = drawable_bytes(L, W, H, werk_raster.babl_format(s))
        if b == s["data"]:
            exact += 1
        else:
            mism.append(it["name"])
    r["open"] = {"size": [W, H], "layers_total": count_all(img.get_layers()),
                 "precision": img.get_precision().value_nick,
                 "leaf_layers": len(got), "tree_leaves": len(want),
                 "surfaces_compared": compared, "surfaces_exact": exact,
                 "surfaces_converted_precision": converted, "mismatch": mism[:20],
                 "names_match": [L.get_name() for L in got] == [i["name"] for i in want],
                 "name_diffs": [[i["name"], L.get_name()] for i, L in zip(want, got)
                                if i["name"] != L.get_name()],
                 "names_match_modulo_gimp_suffix": [
                     __import__("re").sub(r" #\d+$", "", L.get_name()) for L in got]
                     == [i["name"] for i in want],
                 "report_codes": sorted({c for _s, c, _m in rep.entries})}
    groups = count_all(img.get_layers()) - len(got)
    r["open"]["groups"] = groups
    rgba_before = [sha(drawable_bytes(L, W, H)) for L in got]
    names_before = [L.get_name() for L in got]
    flat_before = sha(merged(img)[0])
    out = os.path.join(P["out_dir"], fx["key"] + ".gimp-export-layers.werk")
    st, err = export(img, out, "raster-layers/1", P["template"])
    r["export_layers"] = {"path": out, "status": st, "error": str(err) if err else None}
    out1 = os.path.join(P["out_dir"], fx["key"] + ".gimp-export-flat.werk")
    r["export_flat"] = {"path": out1, "status": export(img, out1)[0]}
    img.delete()
    if os.path.isfile(out):
        back = load(out)
        bl = leaves(back.get_layers())
        rgba_after = [sha(drawable_bytes(L, W, H)) for L in bl]
        r["reopen_layers"] = {"leaf_layers": len(bl),
                              "layers_identical": sum(1 for a, b in zip(rgba_before, rgba_after) if a == b),
                              "names_identical": [L.get_name() for L in bl] == names_before,
                              "flat_sha256": sha(merged(back)[0]),
                              "flat_before_sha256": flat_before}
        back.delete()
    if os.path.isfile(out1):
        b1 = load(out1)
        r["reopen_flat"] = {"pixels_sha256": sha(merged(b1)[0]),
                            "flat_before_sha256": flat_before, "layers": len(b1.get_layers())}
        b1.delete()
    return r


results = {"gimp": Gimp.version(), "fixtures": [], "errors": []}
for fx in P["fixtures"]:
    try:
        rr = run_layers(fx) if fx["profile"] == "raster-layers/1" else run_image(fx)
    except Exception:  # noqa: BLE001
        rr = {"key": fx["key"], "profile": fx["profile"], "exception": traceback.format_exc()}
    results["fixtures"].append(rr)
    with open(P["result"], "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=1)
print("GATE-IN-GIMP done: %d fixture(s)" % len(results["fixtures"]))
