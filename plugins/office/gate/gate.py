#!/usr/bin/env python3
"""gate.py -- the werk-office gate: Office 2016 documents -> werk -> Office, in the real hosts.

    py -3.12 gate/gate.py --libs <werk libs dir> --repo <werk release repo>
          [--samples <artcraft-samples>] [--reuse-inputs]

 A. inputs: three test documents written by Word, Excel and PowerPoint themselves
    (gate/make_inputs.py; skipped with --reuse-inputs when they exist)
 B. export each with werk_office.py (PDF made by the Office application)
 C. every package through every release reader (gate/readers.py: python -m werk, the
    vendored werk_single.py, the JS library, werkc with JSON Schema validation, and the
    three bootstrap loaders built from the release tree), plus python jsonschema over the
    manifest (the package's own profile schema), every JSON payload its manifest maps to a
    schema, and the inflated text blocks (rich-document $defs/BlockList); plus the profile's
    own reader script that travels in the package (spec/examples/<profile>/read_*.py)
 D. the carried original: byte-identical to the input; the PDF starts with %PDF
 E. import (original route) -> the bytes of the input; reopened in Office
 F. import --rebuild (from the structured nodes only) -> reopened in Office; the text,
    cells and slides that werk-office maps are checked against the input's
 G. import --rebuild of the ArtCraft samples of the three profiles (no original inside)
    -> reopened in Office

Every clause prints PASS / FAIL / NOT-RUN. Results: _gate_out/gate.json.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import zipfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
import readers                         # noqa: E402
import werk_office as wo               # noqa: E402

RESULTS = []
PY = sys.executable


def clause(part, name, ok, detail):
    word = "NOT-RUN" if ok is None else ("PASS" if ok else "FAIL")
    RESULTS.append({"part": part, "clause": name, "result": word, "detail": detail})
    print("[%s] %-48s %s" % (word, name, str(detail)[:300]))
    sys.stdout.flush()


def sha_file(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def run_tool(args):
    p = subprocess.run([PY, os.path.join(ROOT, "werk_office.py")] + args, capture_output=True, text=True,
                       encoding="utf-8")
    try:
        return p.returncode, json.loads(p.stdout), p.stderr
    except ValueError:
        return p.returncode, None, (p.stderr or p.stdout)[-400:]


def schema_checks(pkg_path):
    """jsonschema over the manifest, every JSON payload with a schema, inflated blocks."""
    try:
        import jsonschema
    except ImportError:
        return None, "python jsonschema not installed"
    z = zipfile.ZipFile(pkg_path)
    m = json.loads(z.read("MANIFEST.json"))
    errs, n = [], 0

    def check(schema_path, doc, what, sub=None):
        nonlocal n
        s = json.loads(z.read(schema_path))
        if sub:
            s = dict(s, **{"$ref": "#/$defs/" + sub})
            s.pop("properties", None), s.pop("required", None), s.pop("type", None)
            s.pop("additionalProperties", None)
        v = jsonschema.Draft202012Validator(s)
        for e in v.iter_errors(doc):
            errs.append("%s: %s at %s" % (what, e.message[:160], "/".join(str(x) for x in e.path)))
        n += 1

    check(m["manifest_schema"], m, "MANIFEST.json")
    for node in m["nodes"]:
        sp = m.get("schemas", {}).get(node["type"])
        if not sp:
            continue
        ver = [v for v in node["versions"] if v["v"] == node["active"]][0]
        pf = ver.get("payload_file") or (ver["files"][0]["path"] if len(ver["files"]) == 1 else None)
        if not pf or not pf.endswith(".json"):
            continue
        doc = json.loads(z.read(pf))
        check(sp, doc, pf)
        if node["type"] == "core.text.blocks":
            bf = [f["path"] for f in ver["files"] if f.get("role") == "blocks"][0]
            check(sp, json.loads(zlib.decompress(z.read(bf))), bf + " (inflated)", sub="BlockList")
    return not errs, "%d document(s) validated, %d error(s)%s" % (n, len(errs),
                                                                ": " + "; ".join(errs[:3]) if errs else "")


def profile_reader(pkg_path, profile, outdir):
    """Run the reader script the package itself carries, with python -I, on the package."""
    name = {"rich-document/1": ("rich-document", "read_document.py", ["--text"]),
            "spreadsheet/1": ("spreadsheet", "read_spreadsheet.py", []),
            "presentation/1": ("presentation", "read_presentation.py", ["--text"])}[profile]
    d = os.path.join(outdir, "carried-reader")
    os.makedirs(d, exist_ok=True)
    rel = "spec/examples/%s/%s" % (name[0], name[1])
    script = os.path.join(d, name[1])
    with open(script, "wb") as fh:
        fh.write(zipfile.ZipFile(pkg_path).read(rel))
    p = subprocess.run([PY, "-I", script, pkg_path] + name[2], capture_output=True)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


EXPECT_TEXT = {
    ".docx": ["werk-office gate document", "Plain text, bold, italic", "Grüße – ünïcødé 日本語",
              "Apples", "Pears", "After the table", "The last paragraph, on page two."],
    ".pptx": ["werk-office gate deck", "Slide one subtitle", "First point", "Second point", "Grüße – 日本語"],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--libs", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--samples", default=os.environ.get("WERK_ARTCRAFT_SAMPLES", ""))
    ap.add_argument("--out", default=os.path.join(ROOT, "_gate_out"))
    ap.add_argument("--reuse-inputs", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    bundle = json.load(open(os.path.join(a.libs, "bundle", "bundle.json"), encoding="utf-8"))
    print("werk-office gate  werk-office %s" % wo.VERSION)
    print("libs: lib_version %s, bundle source_rev %s; vendored werk_single.py sha256 %s"
          % (bundle["lib_version"], bundle["source_rev"], sha_file(os.path.join(ROOT, "vendor", "werk_single.py"))))
    inputs = os.path.join(a.out, "inputs")
    pk = os.path.join(a.out, "packages")
    back = os.path.join(a.out, "imported")
    for d in (inputs, pk, back):
        os.makedirs(d, exist_ok=True)

    # A
    print("\n== A. inputs ==")
    if not (a.reuse_inputs and all(os.path.isfile(os.path.join(inputs, "test" + e)) for e in wo.KIND)):
        p = subprocess.run([PY, os.path.join(HERE, "make_inputs.py"), inputs], capture_output=True, text=True)
        clause("A", "make_inputs.py (Word, Excel, PowerPoint)", p.returncode == 0, (p.stdout + p.stderr).strip()[-300:])
    rec = json.load(open(os.path.join(inputs, "inputs.json"), encoding="utf-8"))
    for e in wo.KIND:
        f = os.path.join(inputs, "test" + e)
        clause("A", "input test%s" % e, os.path.isfile(f) and sha_file(f) == rec["test" + e]["sha256"],
               "%d bytes, sha256 %s, Office %s" % (os.path.getsize(f), sha_file(f)[:16], rec["test" + e]["office"]))

    R = readers.Readers(a.libs, os.path.join(a.repo, "loaders"), os.path.join(a.out, "bin"),
                        os.path.join(ROOT, "vendor", "werk_single.py"))
    for n in R.build_notes:
        print("  " + n)

    def verify_all(tag, path, profile):
        for rname, ok, detail in R.check(path, 0):
            clause("C", "%s: verify %s" % (tag, rname), ok, detail)
        ok, detail = schema_checks(path)
        clause("C", "%s: jsonschema (manifest, payloads, blocks)" % tag, ok, detail)
        rc, out, err = profile_reader(path, profile, a.out)
        clause("C", "%s: the package's own profile reader" % tag, rc == 0,
               "exit %d; %s" % (rc, (out.strip().splitlines() or [err.strip()[-200:]])[-1][:200]))
        return out

    for e in wo.KIND:
        src = os.path.join(inputs, "test" + e)
        dst = os.path.join(pk, "test-%s.werk" % e[1:])
        print("\n== %s ==" % e)
        if os.path.isfile(dst):
            os.remove(dst)
        rc, r, err = run_tool(["export", src, dst, "--created", "2026-11-07T12:00:00Z"])
        clause("B", "export test%s" % e, rc == 0 and os.path.isfile(dst),
               "exit %d; %s" % (rc, json.dumps({k: r[k] for k in ("profile", "nodes", "files", "host", "notes",
                                                                    "office_instances")}, ensure_ascii=False)
                                if r else err))
        if not os.path.isfile(dst):
            continue
        import werk_single as werk
        pkg = werk.open(dst)
        profile = pkg.profile
        out = verify_all("test%s" % e, dst, profile)
        if e in EXPECT_TEXT:
            miss = [t for t in EXPECT_TEXT[e] if t not in out]
            clause("C", "test%s: profile reader shows the text" % e, not miss,
                   "missing %s" % miss if miss else "all %d expected strings present" % len(EXPECT_TEXT[e]))
        nid, orig = wo.find_original(pkg)
        clause("D", "test%s: original carried byte for byte" % e,
               orig is not None and hashlib.sha256(orig).hexdigest() == sha_file(src),
               "node %s, %s bytes" % (nid, len(orig) if orig else None))
        pdfs = [n for n in pkg.nodes if n.type == wo.X_RENDITION]
        if pdfs:
            pdf = pkg.read_payload(pdfs[0].node_id)
        else:
            d = json.loads(pkg.read_payload("document"))
            pdf = None
            for m in d.get("media", []):
                desc = json.loads(pkg.read_payload(m["node"]))
                if desc["encoding"] == "pdf":
                    node = pkg.node(m["node"])
                    ver = [v for v in node.versions if v["v"] == node.resolved][0]
                    pdf = pkg.read_file([f["path"] for f in ver["files"] if f.get("role") == "media"][0])
        clause("D", "test%s: PDF rendition by the Office host" % e, bool(pdf) and pdf[:5] == b"%PDF-",
               "%s bytes, header %r" % (len(pdf) if pdf else None, pdf[:8] if pdf else None))

        # E: original route
        o1 = os.path.join(back, "from-original-test" + e)
        rc, r, err = run_tool(["import", dst, o1])
        clause("E", "test%s: import (original route)" % e,
               rc == 0 and r and r["route"] == "original" and sha_file(o1) == sha_file(src),
               "exit %d; %s" % (rc, json.dumps(r) if r else err))
        try:
            ro = wo.reopen(o1)
            clause("E", "test%s: reopened in Office" % e, True, json.dumps(ro, ensure_ascii=False)[:250])
        except Exception as exc:
            clause("E", "test%s: reopened in Office" % e, False, repr(exc))

        # F: rebuild route
        o2 = os.path.join(back, "rebuilt-test" + e)
        rc, r, err = run_tool(["import", dst, o2, "--rebuild"])
        clause("F", "test%s: import --rebuild" % e, rc == 0 and r and r["route"] == "rebuilt" and os.path.isfile(o2),
               "exit %d; %s" % (rc, json.dumps(r) if r else err))
        if not os.path.isfile(o2):
            continue
        try:
            ro = wo.reopen(o2)
        except Exception as exc:
            clause("F", "test%s: rebuilt file reopened in Office" % e, False, repr(exc))
            continue
        if e == ".docx":
            miss = [t for t in EXPECT_TEXT[e] if t not in ro["text"].replace("\x07", " ")]
            clause("F", "test.docx: rebuilt text matches", not miss and ro["tables"] == 1,
                   "%d paragraphs, %d table(s), %d page(s); missing %s" % (ro["paragraphs"], ro["tables"],
                                                                          ro["pages"], miss or "none"))
        elif e == ".pptx":
            flat = " ".join(" ".join(t) for t in ro["texts"])
            miss = [t for t in EXPECT_TEXT[e] if t not in flat]
            clause("F", "test.pptx: rebuilt slides match", ro["slides"] == 2 and not miss,
                   "%d slides, size %s; missing %s" % (ro["slides"], ro["size"], miss or "none"))
        else:
            sheets = {s["name"]: s["cells"] for s in ro["sheets"]}
            # values compared as Value2 (locale-free: this machine's Excel shows 8.5 as "8,5")
            want = {("Prices", "B5"): ("=SUM(B2:B4)", 8.5), ("Prices", "C2"): ("=B2*2", 9.0),
                    ("Prices", "A2"): ("Tea", "Tea"), ("Prices", "D1"): ("TRUE", True),
                    ("Prices", "A5000"): ("far down", "far down"), ("Notes", "B2"): ("1234567.25", 1234567.25),
                    ("Notes", "A1"): ("Grüße – 日本語", "Grüße – 日本語")}
            bad = []
            for (sh, ref), (f, v) in want.items():
                got = sheets.get(sh, {}).get(ref)
                if not got or got["formula"] != f or got.get("value2") != v:
                    bad.append("%s!%s=%r" % (sh, ref, got))
            d2 = sheets.get("Prices", {}).get("D2")
            if not d2 or d2["value"] != "#DIV/0!":
                bad.append("Prices!D2=%r (want #DIV/0!)" % d2)
            clause("F", "test.xlsx: rebuilt cells match", list(sheets) == ["Prices", "Notes"] and not bad,
                   "sheets %s; mismatches %s" % (list(sheets), bad or "none"))

    # G: ArtCraft samples (no original carried)
    print("\n== G. ArtCraft samples, rebuilt ==")
    for rel, ext in (("wordcraft/report.werk", ".docx"), ("gridcraft/sales.werk", ".xlsx"),
                     ("deckcraft/sample-deck.werk", ".pptx")):
        src = os.path.join(a.samples, rel)
        o3 = os.path.join(back, os.path.basename(rel)[:-5] + ext)
        rc, r, err = run_tool(["import", src, o3])
        clause("G", "%s -> %s" % (rel, ext), rc == 0 and r and r["route"] == "rebuilt",
               "exit %d; %s" % (rc, json.dumps(r) if r else err))
        if rc == 0:
            try:
                ro = wo.reopen(o3)
                clause("G", "%s: reopened in Office" % rel, True, json.dumps(ro, ensure_ascii=False)[:250])
            except Exception as exc:
                clause("G", "%s: reopened in Office" % rel, False, repr(exc))

    left = {img: wo._pids(img) for img in ("WINWORD.EXE", "EXCEL.EXE", "POWERPNT.EXE")}
    counts = {w: sum(1 for r in RESULTS if r["result"] == w) for w in ("PASS", "FAIL", "NOT-RUN")}
    print("\nOffice processes running at the end (not started by this gate unless listed in the "
          "instance log): %s" % left)
    print("%d PASS, %d FAIL, %d NOT-RUN  (%.0f s)" % (counts["PASS"], counts["FAIL"], counts["NOT-RUN"],
                                                     time.time() - t0))
    json.dump({"bundle_source_rev": bundle["source_rev"], "counts": counts, "clauses": RESULTS,
               "office_processes_at_end": {k: sorted(v) for k, v in left.items()}},
              open(os.path.join(a.out, "gate.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("GATE: %s" % ("PASSED" if counts["FAIL"] == 0 else "FAILED"))
    return 0 if counts["FAIL"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
