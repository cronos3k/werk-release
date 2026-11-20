#!/usr/bin/env python3
"""cross_readers.py -- the release reference readers against a SECOND implementation of each
profile, on the six fixtures.

    python profiles/tools/cross_readers.py [--fixtures profiles/fixtures] [--out FILE.json]

Second implementations (all written independently of profiles/*/read_*.py, from the profile
documents, by the ArtCraft integration or the release's GIMP plug-in):

  raster-layers  plugins/gimp/plug-ins/file-werk/werk_raster.py read_document()  (release GIMP plug-in)
  vector-art     spec/examples/vector-art/read_document.py                         (travels in the profile)
  motion-comp    spec/examples/motion-comp/read_motion.py `value`                   (travels in the profile)
  rich-document  spec/examples/rich-document/read_document.py --text                (travels in the profile)
  spreadsheet    spec/examples/spreadsheet/read_spreadsheet.py --json               (travels in the profile)
  presentation   spec/examples/presentation/read_presentation.py --json             (travels in the profile)

What is compared, per profile, is listed in each check below; exit 0 when every check agrees.
The second readers are run as scripts from the repository (profiles/<name>/spec/examples/...),
never from inside a package.
"""
import argparse
import hashlib
import importlib
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILES = os.path.dirname(HERE)
REPO = os.path.dirname(PROFILES)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def ours(prof, path):
    d = os.path.join(PROFILES, prof)
    if d not in sys.path:
        sys.path.insert(0, d)
    return importlib.import_module("read_" + prof.replace("-", "_")).read(path)


def example(prof, script):
    return os.path.join(PROFILES, prof, "spec", "examples", prof, script)


def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.returncode, p.stdout, p.stderr


def check_raster(path, tmp):
    gimp = os.path.join(REPO, "plugins", "gimp", "plug-ins", "file-werk")
    sys.path.insert(0, gimp)
    import werk_raster as WR
    doc, tree, _rep = WR.read_document(path)
    theirs = {}

    def walk(items):
        for it in items:
            if it.get("surface"):
                theirs[it["node_id"]] = sha(it["surface"]["data"])
            walk(it.get("children") or [])
    walk(tree)
    mine = {}

    def walk2(ls):
        for L in ls:
            if L.get("pixels"):
                mine[L["id"]] = L["pixels"]["samples_sha256"]
            walk2(L.get("children") or [])
    got = ours("raster-layers", path)
    walk2(got["layers"])
    names_t = [(it["node_id"], it["name"], it["kind"], it["blend"]) for it in tree]
    names_o = [(L["id"], L["name"], L["kind"], L["blend"]) for L in got["layers"]]
    checks = {"canvas": (doc["width"], doc["height"]) == (got["canvas"]["width"], got["canvas"]["height"]),
              "top-level tree (id, name, kind, blend)": names_t == names_o,
              "decoded layer pixels, sha256 per layer": theirs == mine}
    return checks, {"layers_compared": sorted(mine)}


def check_vector(path, tmp):
    rc, o, e = run([sys.executable, example("vector-art", "read_document.py"), path])
    t = json.loads(o.decode("utf-8"))
    got = ours("vector-art", path)
    ids_t = [ob["id"] for L in t["layers"] for ob in L["objects"]]
    ids_o = [ob["id"] for ob in got["objects"]]
    types_t = [ob["type"] for L in t["layers"] for ob in L["objects"]]
    types_o = [ob["kind"] for ob in got["objects"]]
    txt_t = []
    for L in t["layers"]:
        for ob in L["objects"]:
            if ob["type"] == "text":
                txt_t.append(ob.get("text") if isinstance(ob.get("text"), str)
                             else u"".join(r.get("text", u"") for r in ob.get("runs") or []))
    checks = {"exit 0": rc == 0, "title": t["title"] == got["title"],
              "object ids in tree order": ids_t == ids_o, "object types": types_t == types_o,
              "text of text objects": txt_t == got["text"], "nothing lost": t.get("lost") == [] and not got["dead"]}
    return checks, {"objects": len(ids_o)}


def check_motion(path, tmp):
    got = ours("motion-comp", path)
    worst, n, okc = 0.0, 0, True
    for c in got["comps"]:
        tps, rate = 254016000000, c["frame_rate"]
        for L in c["layers"]:
            for prop, series in L["animated"].items():
                ticks = [str(f * tps * rate["den"] // rate["num"]) for f in range(c["frames"])]
                rc, o, e = run([sys.executable, example("motion-comp", "read_motion.py"), path, "value",
                                str(c["id"]), str(L["id"]), prop] + ticks)
                okc = okc and rc == 0
                for line, mine in zip(o.decode("utf-8").splitlines(), series):
                    vals = [float(x) for x in line.split()[1:]] if "[" not in line else \
                        [float(x) for x in line.split(None, 1)[1].strip("[] ").split(",")]
                    mv = mine if isinstance(mine, list) else [mine]
                    for a, b in zip(vals, mv):
                        worst = max(worst, abs(a - b))
                        n += 1
    return {"exit 0 for every property": okc, "values agree within 1e-9 (profile 6.3)": worst <= 1e-9 and n > 0}, \
        {"values_compared": n, "max_abs_difference": worst}


def check_rich(path, tmp):
    rc, o, e = run([sys.executable, example("rich-document", "read_document.py"), path, "--text"])
    got = ours("rich-document", path)
    stored_line_ok = "stored plain text: equals" in e.decode("utf-8", "replace")
    return {"exit 0": rc == 0, "stored plain text equals recomputed (their reader)": stored_line_ok,
            "plain text identical": o.decode("utf-8") == got["plain_text"]}, {"chars": len(got["plain_text"])}


def check_sheet(path, tmp):
    js = os.path.join(tmp, "sheet.json")
    rc, o, e = run([sys.executable, example("spreadsheet", "read_spreadsheet.py"), path, "--json", js])
    t = json.load(open(js, encoding="utf-8"))
    got = ours("spreadsheet", path)
    mine = {(s["name"], k): (v["value"], v["formula"], v["style"]) for s in got["sheets"] for k, v in s["cells"].items()}
    theirs = {(s["name"], c["a1"]): (c["value"], c["formula"], c["style"]) for s in t["sheets"] for c in s["cells"]}
    return {"exit 0": rc == 0, "every cell: value, formula, format index": mine == theirs,
            "nothing lost": t.get("lost") == [] and not got["dead"]}, {"cells_compared": len(mine)}


def check_deck(path, tmp):
    js = os.path.join(tmp, "deck.json")
    rc, o, e = run([sys.executable, example("presentation", "read_presentation.py"), path, "--json", js])
    t = json.load(open(js, encoding="utf-8"))
    got = ours("presentation", path)
    med_t = {m["id"]: m.get("sha256") for m in t["media"]}
    med_o = {m["id"]: m.get("media_sha256") for m in got["media"]}
    return {"exit 0": rc == 0, "slide titles": [s["title"] for s in t["slides"]] == [s["title"] for s in got["slides"]],
            "shape counts per slide": [len(s["shapes"]) for s in t["slides"]] == [len(s["shapes"]) for s in got["slides"]],
            "embedded files: sha256 per media id": med_t == med_o}, {"slides": len(got["slides"])}


CHECKS = [("raster-layers", check_raster), ("vector-art", check_vector), ("motion-comp", check_motion),
          ("rich-document", check_rich), ("spreadsheet", check_sheet), ("presentation", check_deck)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", default=os.path.join(PROFILES, "fixtures"))
    ap.add_argument("--out")
    a = ap.parse_args()
    res, bad = {}, 0
    tmp = tempfile.mkdtemp(dir=os.path.abspath(os.path.dirname(a.out)) if a.out else None)
    for prof, fn in CHECKS:
        path = os.path.join(a.fixtures, "%s-v1.werk" % prof)
        try:
            checks, info = fn(path, tmp)
        except Exception as e:  # noqa: BLE001 - a second reader that cannot read counts as disagreement
            checks, info = {"second reader ran": False}, {"error": repr(e)}
        ok = all(checks.values())
        bad += not ok
        res[prof] = {"agree": ok, "checks": checks, "info": info}
        print("%-14s %s  %s  %s" % (prof, "AGREE" if ok else "DIFFER", json.dumps(checks), json.dumps(info)))
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(res, fh, indent=1, sort_keys=True)
            fh.write("\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
