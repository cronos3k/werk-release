#!/usr/bin/env python3
"""cross_matrix.py -- every libs/ writer x every werk reader, on one table.

    python tests/cross_matrix.py [--out DIR] [--fixtures DIR] [--werkc PATH]
                                 [--cc CC] [--rustc RUSTC] [--node NODE]
                                 [--big-mb N] [--keep]

WRITERS (each writes every case from the same inputs, fixed timestamps):
    py        python -m werk                 (libs/python/werk)
    py1       python libs/python/werk_single.py   (the vendorable single file)
    js        node libs/js/bin/werk.js       (dist/werk.js, Uint8Array build)
    es3       node libs/js/bin/werk-es3.js   (dist/werk.jsx, the ExtendScript build)
    rust      werkc (release-cli branch)     pack-image / pack-mesh / append / sign
READERS (each reads every output of every writer, and every fixture):
    py, js, es3      the libs/ readers (full verdict: Ed25519, spec_sha256, ...)
    werkc            werk-core, the reference full reader (JSON Schema too)
    ref-py, ref-c, ref-rs   the bootstrap loaders the packages themselves carry
                     (werk_read.py / .c built with CC / .rs built with rustc)

CHECKS
  bytes   : all writers' outputs of one case are byte-identical (zip: sha256 of
            the file; directory: sha256 over the sorted (path, sha256) list).
  verdict : full readers agree exactly on exit status, signature state and the
            dead-node set; bootstrap loaders agree on the dead-node set and
            refusal, and say `unverified` (never valid/absent) for a present chain.
  extract : every reader extracts, for every live node, the bytes the manifest
            declares (sha256 compared file by file).

Pure standard library; runs on Windows and Linux.
Exit status 0 when every check passed, 1 otherwise.
"""

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LIBS = os.path.dirname(HERE)
UUID_I = "1a6e0000-0000-4000-8000-000000000001"
UUID_M = "1a6e0000-0000-4000-8000-000000000002"
T0, T1, T2, T3 = ("2026-11-07T12:00:00Z", "2026-11-07T13:00:00Z", "2026-11-07T14:00:00Z",
                  "2026-11-07T15:00:00Z")
EXE = ".exe" if os.name == "nt" else ""
FULL = ("py", "js", "es3", "werkc")
BOOT = ("ref-py", "ref-c", "ref-rs")


def sha(b):
    return hashlib.sha256(b).hexdigest()


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_hash(root):
    items = []
    for dp, _dn, fn in os.walk(root):
        for f in fn:
            full = os.path.join(dp, f)
            items.append((os.path.relpath(full, root).replace(os.sep, "/"), sha_file(full)))
    items.sort(key=lambda x: x[0].encode("utf-8"))
    return sha("".join("%s %s\n" % x for x in items).encode("utf-8")), len(items)


def run(cmd, timeout=900):
    t = time.time()
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    return p.returncode, p.stdout, p.stderr, time.time() - t


def which(names):
    for n in names:
        if n and os.path.isfile(n):
            return n
        w = shutil.which(n) if n else None
        if w:
            return w
    return None


# ---------------------------------------------------------------------------
# tools
# ---------------------------------------------------------------------------

def setup_tools(a, work):
    py = sys.executable
    node = which([a.node, "node"])
    werkc = which([a.werkc,
                   os.path.join(LIBS, "_target", "release", "werkc" + EXE),
                   os.path.join(os.path.dirname(LIBS), "core", "target", "release", "werkc" + EXE),
                   "werkc"])
    cc = which([a.cc, "cc", "gcc", "clang", "C:/msys64/mingw64/bin/gcc.exe"])
    rustc = which([a.rustc, "rustc"])
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.join(LIBS, "python") + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    if cc and os.path.dirname(cc):
        env["PATH"] = os.path.dirname(cc) + os.pathsep + env["PATH"]
    os.environ.update(env)
    bindir = os.path.join(work, "bin")
    os.makedirs(bindir, exist_ok=True)
    tools = {"python": py, "node": node, "werkc": werkc}
    loaders = os.path.join(LIBS, "bundle", "loaders")
    if cc:
        out = os.path.join(bindir, "werk_read_c" + EXE)
        rc, _o, e, _t = run([cc, "-std=c99", "-O2", os.path.join(loaders, "werk_read.c"), "-o", out])
        tools["ref-c"] = out if rc == 0 else None
        if rc:
            print("C loader did not build: %s" % e.decode(errors="replace")[:400])
    if rustc:
        out = os.path.join(bindir, "werk_read_rs" + EXE)
        rc, _o, e, _t = run([rustc, "-O", "--edition", "2021", os.path.join(loaders, "werk_read.rs"), "-o", out])
        tools["ref-rs"] = out if rc == 0 else None
        if rc:
            print("Rust loader did not build: %s" % e.decode(errors="replace")[:400])
    tools["cc"], tools["rustc"] = cc, rustc
    return tools


def writer_cmd(w, tools):
    py = tools["python"]
    return {"py": [py, "-m", "werk"],
            "py1": [py, os.path.join(LIBS, "python", "werk_single.py")],
            "js": [tools["node"], os.path.join(LIBS, "js", "bin", "werk.js")] if tools["node"] else None,
            "es3": [tools["node"], os.path.join(LIBS, "js", "bin", "werk-es3.js")] if tools["node"] else None,
            "rust": [tools["werkc"]] if tools["werkc"] else None}[w]


# ---------------------------------------------------------------------------
# cases: a list of steps per case; a step is a CLI call with {in}/{out}
# placeholders. The last step's output is the case's package.
# ---------------------------------------------------------------------------

def cases(I, big_mb):
    k1, k2 = os.path.join(I, "key.hex"), os.path.join(I, "key2.hex")
    img = ["--png", I + "/source.png", "--name", "Test pattern", "--uuid", UUID_I, "--created", T0]
    full_img = ["--png", I + "/source.png", "--thumb", I + "/thumb.png",
                "--name", "Test pattern \u2014 Gr\u00f6\u00dfe \u65e5\u672c \U0001f3a8",
                "--summary", "unicode \u2713, tab\there, quote \" and backslash \\",
                "--uuid", UUID_I, "--created", T0, "--recipe", I + "/recipe.json",
                "--disclosure", I + "/disclosure.json"]
    sign1 = ["--sign-key", k1, "--signer-uri", "urn:werk:test:rfc8032-1", "--signer-kind", "service",
             "--signer-name", "RFC 8032 test key 1"]
    mesh = ["--glb", I + "/triangle.glb", "--name", "Triangle", "--uuid", UUID_M, "--created", T0]
    full_mesh = mesh + ["--texture", "albedo=" + I + "/tex-albedo.png",
                        "--texture", "nrm=" + I + "/tex-normal.png:normal",
                        "--material", "paint:albedo", "--preview", I + "/preview.png"]
    many = []
    for i in range(40):
        many += ["--attach", "note-%02d:x.test.note:notes/note-%02d.txt=%s/attach-%02d.txt" % (i, i, I, i)]
    return [
        ("image-min", "zip", [["pack-image", "{out}"] + img]),
        ("image-full-signed", "zip", [["pack-image", "{out}"] + full_img + sign1]),
        ("image-full-dir", "dir", [["pack-image", "{out}", "--dir"] + full_img + sign1]),
        ("mesh-min", "zip", [["pack-mesh", "{out}"] + mesh]),
        ("mesh-full-signed", "zip", [["pack-mesh", "{out}"] + full_mesh + sign1]),
        ("many-nodes", "zip", [["pack-image", "{out}"] + img + many]),
        ("empty-payload", "zip", [["pack-image", "{out}"] + img +
                                  ["--attach", "empty:x.test.empty:empty/zero.bin=" + I + "/empty.bin",
                                   "--attach", "unicode-text:x.test.text:text/unicode.txt=" + I + "/notes-unicode.txt"]]),
        ("spec-files", "zip", [["pack-image", "{out}"] + img +
                               ["--spec-file", "spec/PROFILE-EXTRA.md=" + I + "/profile-extra.md",
                                "--spec-file", "spec/README.md=" + I + "/spec-readme.md"]]),
        ("profile-extras", "zip", [["pack-image", "{out}"] + img +
                                   ["--spec-file", "spec/conventions-map.extra.json=" + os.path.join(LIBS, "bundle", "spec", "conventions-map.image.json"),
                                    "--conventions-map", "spec/conventions-map.extra.json",
                                    "--readme-file", "HOW-TO-READ.md=" + I + "/profile-extra.md"]]),
        ("large-file-dir", "dir", [["pack-mesh", "{out}", "--dir"] + mesh +
                                   ["--attach", "big:x.test.blob:blob/big.bin=" + I + "/big.bin"]]),
        ("multi-version", "zip", [
            ["pack-mesh", "{out}"] + full_mesh,
            ["append", "{in}", "{out}", "--node", "tex-albedo", "--file", "textures/albedo.png=" + I + "/preview.png",
             "--note", "Re-exported the albedo at 16 px \u2014 v2.", "--created", T1],
            ["append", "{in}", "{out}", "--node", "tex-albedo", "--file", "textures/albedo.png=" + I + "/tex-normal.png",
             "--note", "A third take of the albedo; v1 and v2 stay.", "--created", T2],
            ["append", "{in}", "{out}", "--node", "notes", "--type", "x.test.notes",
             "--file", "notes/unicode.txt=" + I + "/notes-unicode.txt",
             "--note", "Notes in many scripts: Gr\u00f6\u00dfe \u65e5\u672c \U0001f3a8", "--created", T3]]),
        ("signed-append", "zip", [
            ["pack-image", "{out}"] + full_img + sign1,
            ["append", "{in}", "{out}", "--node", "image-thumb", "--file", "image/thumb.png=" + I + "/tex-normal.png",
             "--note", "Thumbnail re-encoded; v1 stays.", "--created", T1,
             "--sign-key", k2, "--signer-uri", "urn:werk:test:rfc8032-2", "--signer-kind", "human"]]),
        ("co-signed", "zip", [
            ["pack-mesh", "{out}"] + mesh,
            ["sign", "{in}", "{out}", "--sign-key", k1, "--signer-uri", "urn:werk:test:k1",
             "--signer-kind", "service", "--signed-at", T1],
            ["sign", "{in}", "{out}", "--sign-key", k2, "--signer-uri", "urn:werk:test:k2",
             "--signer-kind", "agent", "--signed-at", T2]]),
        # Damage applied by the driver to each writer's (identical) output:
        ("tampered-payload", "zip", [["pack-image", "{out}"] + full_img + sign1, ["@tamper-payload", "image/thumb.png"]]),
        ("tampered-signature", "zip", [["pack-image", "{out}"] + full_img + sign1, ["@tamper-signature"]]),
        ("tampered-manifest", "zip", [["pack-image", "{out}"] + full_img + sign1, ["@tamper-manifest"]]),
        ("duplicate-entry", "zip", [["pack-image", "{out}"] + img, ["@duplicate-entry", "README.txt"]]),
        ("truncated", "zip", [["pack-image", "{out}"] + img, ["@truncate", "1000"]]),
        # MINI-SPECS 5.4 path rule, node scope (SPEC 12.1): a files[] path
        # `../evil.txt` (and a zip entry by that name) kills its node; the
        # package loads, nothing is written outside the target folder.
        ("unsafe-path", "zip", [["pack-image", "{out}"] + img, ["@unsafe-path", "README.txt"]]),
    ]


def zip_entry_span(blob, name):
    """(data_offset, size) of a stored entry, from the central directory."""
    import struct
    e = blob.rfind(b"PK\x05\x06")
    count, _cds, cdo = struct.unpack_from("<HII", blob, e + 10)
    p = cdo
    for _ in range(count):
        nlen, mlen, klen = struct.unpack_from("<HHH", blob, p + 28)
        size = struct.unpack_from("<I", blob, p + 24)[0]
        lho = struct.unpack_from("<I", blob, p + 42)[0]
        nm = blob[p + 46:p + 46 + nlen].decode("utf-8")
        if nm == name:
            ln, lm = struct.unpack_from("<HH", blob, lho + 26)
            return lho + 30 + ln + lm, size
        p += 46 + nlen + mlen + klen
    raise KeyError(name)


def damage(path, step):
    with open(path, "rb") as fh:
        blob = bytearray(fh.read())
    kind = step[0]
    if kind == "@tamper-payload":
        off, size = zip_entry_span(blob, step[1])
        blob[off + size // 2] ^= 0x01
    elif kind == "@tamper-signature":
        off, size = zip_entry_span(blob, "SIGNATURE.json")
        text = bytes(blob[off:off + size])
        at = text.index(b'"signature": "') + len(b'"signature": "')
        c = blob[off + at]
        blob[off + at] = ord("0") if c != ord("0") else ord("1")
    elif kind == "@tamper-manifest":
        off, size = zip_entry_span(blob, "MANIFEST.json")
        text = bytes(blob[off:off + size])
        at = text.index(b'"name": "Test pattern') + len(b'"name": "')
        blob[off + at] = ord("B")   # 'T' -> 'B': same length, a changed claim
    elif kind == "@duplicate-entry":
        # a second, different entry under an existing name (store mode, no
        # data descriptor): the stdlib zipfile writes it with a warning.
        import warnings
        import zipfile
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with zipfile.ZipFile(path, "a", compression=zipfile.ZIP_STORED) as z:
                z.writestr(zipfile.ZipInfo(step[1], (2026, 11, 7, 12, 0, 0)), b"a second README.txt\n")
        return
    elif kind == "@unsafe-path":
        # rename one declared file to `../evil.txt` in the manifest and in
        # the container (same bytes, same sha256 and size); every other
        # entry is copied unchanged.
        import zipfile
        bad = "../evil.txt"
        with zipfile.ZipFile(path) as z:
            items = [(i.filename, z.read(i.filename)) for i in z.infolist()]
        man = json.loads(dict(items)["MANIFEST.json"].decode("utf-8"))
        hit = 0
        for n in man["nodes"]:
            for v in n["versions"]:
                for f in v["files"]:
                    if f["path"] == step[1]:
                        f["path"] = bad
                        hit += 1
                if v.get("payload_file") == step[1]:
                    v["payload_file"] = bad
        assert hit == 1, "unsafe-path: %s declared %d times" % (step[1], hit)
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as z:
            for name, data in items:
                if name == "MANIFEST.json":
                    data = json.dumps(man, indent=1).encode("utf-8")
                elif name == step[1]:
                    name = bad
                z.writestr(zipfile.ZipInfo(name, (2026, 11, 17, 12, 0, 0)), data)
        return
    elif kind == "@truncate":
        blob = blob[:int(step[1])]
    with open(path, "wb") as fh:
        fh.write(bytes(blob))


def build(w, tools, case, outdir):
    """Run one writer through one case; return (path, form, ok, error, seconds)."""
    name, form, steps = case
    base = writer_cmd(w, tools)
    if base is None:
        return None, form, False, "writer not available", 0
    prev = None
    total = 0.0
    for i, st in enumerate(steps):
        ext = "" if form == "dir" else ".werk"
        out = os.path.join(outdir, "%s.%s.s%d%s" % (name, w, i, ext))
        if st[0].startswith("@"):
            damage(prev, st)
            continue
        if os.path.isdir(out):
            shutil.rmtree(out)
        elif os.path.exists(out):
            os.remove(out)
        args = [x.replace("{out}", out).replace("{in}", prev or "") for x in st]
        rc, o, e, t = run(base + args)
        total += t
        if rc != 0:
            return None, form, False, (e or o).decode("utf-8", "replace").strip()[-300:], total
        if prev and prev != out and i > 0:
            pass
        prev = out
    return prev, form, True, "", total


# ---------------------------------------------------------------------------
# readers
# ---------------------------------------------------------------------------

def full_reader(r, tools):
    if r == "py":
        return [tools["python"], "-m", "werk"]
    if r == "js" and tools["node"]:
        return [tools["node"], os.path.join(LIBS, "js", "bin", "werk.js")]
    if r == "es3" and tools["node"]:
        return [tools["node"], os.path.join(LIBS, "js", "bin", "werk-es3.js")]
    if r == "werkc" and tools["werkc"]:
        return [tools["werkc"]]
    return None


def boot_reader(r, tools):
    if r == "ref-py":
        return [tools["python"], os.path.join(LIBS, "bundle", "loaders", "werk_read.py")]
    p = tools.get(r)
    return [p] if p else None


SIG_RE = re.compile(r"signature(?:-|:\s*|\s+:\s*)(signed-and-valid|present-and-invalid|unverified|absent|invalid|valid)\b")


def read_full(r, tools, pkg):
    base = full_reader(r, tools)
    if base is None:
        return None
    rc, o, e, t = run(base + ["verify", pkg, "--json"])
    try:
        v = json.loads(o.decode("utf-8"))
    except ValueError:
        return {"exit": rc, "error": (e or o).decode("utf-8", "replace")[-300:], "seconds": t}
    v["exit_status"] = rc
    v["seconds"] = t
    return v


def read_boot(r, tools, pkg, node_ids):
    base = boot_reader(r, tools)
    if base is None:
        return None
    rc, o, e, t = run(base + [pkg, "--list", "--strict"])
    text = o.decode("utf-8", "replace")
    if rc == 2:
        return {"exit_status": 2, "refused": True, "seconds": t}
    dead, skipped = [], []
    for line in text.splitlines():
        toks = line.split()
        if len(toks) >= 3 and toks[0] in node_ids:
            rest = " ".join(toks[2:]).lower()
            if "dead" in rest:
                dead.append(toks[0])
            elif "skip" in rest:
                skipped.append(toks[0])
    rc2, o2, _e2, t2 = run(base + [pkg, "--report"])
    m = SIG_RE.search(o2.decode("utf-8", "replace") + "\n" + text)
    sig = m.group(1) if m else "?"
    sig = {"invalid": "present-and-invalid", "valid": "signed-and-valid"}.get(sig, sig)
    return {"exit_status": rc, "dead_nodes": sorted(dead), "skipped": len(skipped), "signature": sig,
            "seconds": t + t2}


def expected_extraction(pkg_path):
    sys.path.insert(0, os.path.join(LIBS, "python"))
    import werk
    p = werk.open(pkg_path)
    exp = {}
    for n in p.nodes:
        if n.status != "dead":
            for f in n.version()["files"]:
                exp[f["path"]] = f["sha256"]
    return exp, [n.node_id for n in p.nodes if n.status != "dead"], [n.node_id for n in p.nodes]


def extract_compare(r, tools, pkg, exp, live_ids, scratch):
    d = os.path.join(scratch, "x-" + r)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    t0 = time.time()
    if r in FULL:
        rc, _o, e, _t = run(full_reader(r, tools) + ["extract", pkg, d])
    else:
        base = boot_reader(r, tools)
        for nid in live_ids:
            rc, _o, e, _t = run(base + [pkg, "--extract", nid, "--out", d])
    got = {}
    for dp, _dn, fn in os.walk(d):
        for f in fn:
            full = os.path.join(dp, f)
            got[os.path.relpath(full, d).replace(os.sep, "/")] = sha_file(full)
    shutil.rmtree(d)
    missing = sorted(set(exp) - set(got))
    extra = sorted(set(got) - set(exp))
    wrong = sorted(p for p in exp if p in got and got[p] != exp[p])
    ok = not missing and not wrong and not extra
    return ok, {"files": len(got), "missing": missing[:5], "extra": extra[:5], "wrong": wrong[:5],
                "seconds": round(time.time() - t0, 2)}


# Cases where the bootstrap loaders are RECORDED, not held to the full readers:
# their behaviour on duplicate zip entry names is a spec-batch item.
BOOT_FREE = ()   # duplicate-entry was here until the loaders refused it (release-fixes a432b71)


def agree(results, boot_free=False):
    """Verdict agreement over one package. Returns (ok, reason)."""
    fulls = {r: v for r, v in results.items() if r in FULL and v}
    boots = {r: v for r, v in results.items() if r in BOOT and v}
    keys = ("exit_status", "signature", "dead_nodes")
    ref = None
    for r, v in fulls.items():
        if "refusal" in v or v.get("exit_status") == 2:
            sig = ("refused",)
        else:
            sig = tuple(json.dumps(v.get(k), sort_keys=True) for k in keys)
        if ref is None:
            ref = (r, sig, v)
        elif sig != ref[1]:
            return False, "%s disagrees with %s on %s" % (r, ref[0], sig)
    if ref is None:
        return False, "no full reader ran"
    refused = ref[1] == ("refused",)
    if boot_free:
        return True, ""
    for r, v in boots.items():
        if refused:
            if v.get("exit_status") != 2:
                return False, "%s did not refuse" % r
            continue
        if v.get("exit_status") == 2:
            return False, "%s refused a package the full readers opened" % r
        if v["dead_nodes"] != ref[2]["dead_nodes"]:
            return False, "%s dead set %s != %s" % (r, v["dead_nodes"], ref[2]["dead_nodes"])
        fs = ref[2]["signature"]
        ok_sig = (v["signature"] == "absent") if fs == "absent" else (
            v["signature"] in ("unverified", "present-and-invalid") and not (
                fs == "signed-and-valid" and v["signature"] == "present-and-invalid"))
        if not ok_sig:
            return False, "%s says signature %s where the full readers say %s" % (r, v["signature"], fs)
        # SPEC 10.1 (release-fixes): a loader's --strict is "an error entry
        # exists" -- a dead node, or a chain it found present-and-invalid.
        want_exit = 1 if (v["dead_nodes"] or v["signature"] == "present-and-invalid") else 0
        if v["exit_status"] != want_exit:
            return False, "%s --strict exit %s, expected %s" % (r, v["exit_status"], want_exit)
    return True, ""


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(LIBS, "_scratch", "matrix"))
    ap.add_argument("--fixtures", default=None, help="directory of *.werk fixtures to read (reader-only rows)")
    ap.add_argument("--werkc"), ap.add_argument("--cc"), ap.add_argument("--rustc"), ap.add_argument("--node")
    ap.add_argument("--big-mb", type=int, default=24)
    ap.add_argument("--writers", default="py,py1,js,es3,rust")
    ap.add_argument("--readers", default="py,js,es3,werkc,ref-py,ref-c,ref-rs")
    ap.add_argument("--only", default=None, help="comma list of case names")
    ap.add_argument("--keep", action="store_true", help="keep the written packages")
    a = ap.parse_args()
    work = os.path.abspath(a.out)
    if os.path.isdir(work):
        shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work, exist_ok=True)
    tools = setup_tools(a, work)
    inputs = os.path.join(work, "inputs")
    os.environ["WERK_BIG_MB"] = str(a.big_mb)
    run([tools["python"], os.path.join(HERE, "make_inputs.py"), inputs])
    writers = [w for w in a.writers.split(",") if writer_cmd(w, tools)]
    readers = [r for r in a.readers.split(",") if (full_reader(r, tools) if r in FULL else boot_reader(r, tools))]
    env_info = {
        "machine": platform.node(), "os": platform.platform(), "python": platform.python_version(),
        "node": run([tools["node"], "--version"])[1].decode().strip() if tools["node"] else None,
        "werkc": tools["werkc"], "cc": tools["cc"], "rustc": tools["rustc"],
        "writers": writers, "readers": readers, "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    print("writers: %s\nreaders: %s" % (", ".join(writers), ", ".join(readers)))
    rows, failures = [], 0
    wanted = set(a.only.split(",")) if a.only else None
    for case in cases(inputs, a.big_mb):
        name, form = case[0], case[1]
        if wanted and name not in wanted:
            continue
        outs = {}
        for w in writers:
            path, form, ok, err, secs = build(w, tools, case, work)
            if not ok:
                outs[w] = {"ok": False, "error": err}
                continue
            h = tree_hash(path) if form == "dir" else (sha_file(path), 1)
            outs[w] = {"ok": True, "path": path, "sha256": h[0], "seconds": round(secs, 2)}
        hashes = sorted(set(o["sha256"] for o in outs.values() if o.get("ok")))
        identical = len(hashes) == 1 and all(o.get("ok") for o in outs.values())
        row = {"case": name, "form": form, "writers": outs, "identical": identical,
               "sha256": hashes[0] if len(hashes) == 1 else hashes, "reads": {}}
        if not identical:
            failures += 1
        for w, o in outs.items():
            if not o.get("ok"):
                continue
            try:
                exp, live, all_ids = expected_extraction(o["path"])
            except Exception:  # noqa: BLE001 - refused containers
                exp, live, all_ids = None, [], []
            res = {}
            for r in readers:
                res[r] = read_full(r, tools, o["path"]) if r in FULL else read_boot(r, tools, o["path"], set(all_ids))
            ok, why = agree(res, name in BOOT_FREE)
            ext = {}
            if exp is not None and name not in BOOT_FREE:
                for r in readers:
                    eok, info = extract_compare(r, tools, o["path"], exp, live, work)
                    ext[r] = {"ok": eok, **info}
                    if not eok:
                        ok, why = False, why or ("%s extraction differs: %s" % (r, info))
            row["reads"][w] = {"agree": ok, "why": why, "verdicts": res, "extract": ext}
            if not ok:
                failures += 1
        rows.append(row)
        v0 = next(iter(row["reads"].values()), {}).get("verdicts", {}).get("py") or {}
        print("%-20s %-4s identical=%-5s agree=%s  %s" % (
            name, form, identical, all(x["agree"] for x in row["reads"].values()),
            "exit=%s sig=%s dead=%s" % (v0.get("exit_status"), v0.get("signature"), v0.get("dead_nodes"))))
    # fixtures: reader-only rows
    fx_rows = []
    if a.fixtures and os.path.isdir(a.fixtures):
        for fn in sorted(os.listdir(a.fixtures)):
            if not fn.endswith(".werk"):
                continue
            path = os.path.join(a.fixtures, fn)
            exp, live, all_ids = expected_extraction(path)
            res = {r: (read_full(r, tools, path) if r in FULL else read_boot(r, tools, path, set(all_ids)))
                   for r in readers}
            ok, why = agree(res)
            ext = {}
            for r in readers:
                eok, info = extract_compare(r, tools, path, exp, live, work)
                ext[r] = {"ok": eok, **info}
                if not eok:
                    ok, why = False, why or ("%s extraction differs" % r)
            if not ok:
                failures += 1
            fx_rows.append({"fixture": fn, "agree": ok, "why": why, "verdicts": res, "extract": ext})
            v = res.get("py") or {}
            print("%-34s agree=%s  exit=%s sig=%s dead=%s" % (fn, ok, v.get("exit_status"), v.get("signature"),
                                                              v.get("dead_nodes")))
    report = {"env": env_info, "cases": rows, "fixtures": fx_rows, "failures": failures}
    with open(os.path.join(work, "cross_matrix.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, ensure_ascii=False)
    md = render(report)
    with open(os.path.join(work, "CROSS-MATRIX.md"), "w", encoding="utf-8") as fh:
        fh.write(md)
    print("\n" + md)
    if not a.keep:
        for row in rows:
            for o in row["writers"].values():
                p = o.get("path")
                if p and os.path.isdir(p):
                    shutil.rmtree(p, ignore_errors=True)
        for fn in os.listdir(work):
            full = os.path.join(work, fn)
            if fn.endswith(".werk") or (os.path.isdir(full) and ".s" in fn):
                shutil.rmtree(full, ignore_errors=True) if os.path.isdir(full) else os.remove(full)
        shutil.rmtree(inputs, ignore_errors=True)
    print("failures: %d   (report: %s)" % (failures, os.path.join(work, "CROSS-MATRIX.md")))
    return 0 if failures == 0 else 1


def render(rep):
    e = rep["env"]
    readers = e["readers"]
    L = ["# werk libs cross-matrix", "",
         "machine `%s` | %s | python %s | node %s | started %s" % (e["machine"], e["os"], e["python"], e["node"], e["started"]),
         "", "Writers: %s. Readers: %s." % (", ".join(e["writers"]), ", ".join(readers)), "",
         "## Writers x cases (byte identity) and readers x outputs (verdict + extraction)", "",
         "| case | form | byte-identical (%s) | sha256 | full verdict (exit / signature / dead) | %s |"
         % ("/".join(e["writers"]), " | ".join(readers)),
         "|---|---|---|---|---|" + "---|" * len(readers)]
    for row in rep["cases"]:
        writers_ok = "".join("Y" if row["writers"][w].get("ok") else "x" for w in e["writers"])
        ident = ("**yes**" if row["identical"] else "NO") + " (" + writers_ok + ")"
        sha = row["sha256"] if isinstance(row["sha256"], str) else "differs"
        v0 = None
        cells = []
        for r in readers:
            okc = tot = 0
            for w, rd in row["reads"].items():
                tot += 1
                x = rd["verdicts"].get(r)
                ex = rd["extract"].get(r, {"ok": True})
                if x is not None and rd["agree"] and ex.get("ok", True):
                    okc += 1
                if v0 is None and rd["verdicts"].get("py"):
                    v0 = rd["verdicts"]["py"]
            cells.append("%d/%d" % (okc, tot))
        verdict = "-" if not v0 else ("refused (2)" if v0.get("exit_status") == 2 else "%s / %s / %s" % (
            v0.get("exit_status"), v0.get("signature"), ",".join(v0.get("dead_nodes") or []) or "none"))
        L.append("| %s | %s | %s | `%s` | %s | %s |" % (row["case"], row["form"], ident, sha[:16], verdict, " | ".join(cells)))
    L += ["", "A reader cell is `outputs read with an agreeing verdict and byte-exact extraction / outputs`.", ""]
    if rep["fixtures"]:
        L += ["## Fixtures (reader-only)", "", "| fixture | agree | py verdict (exit / signature / dead) | %s |" % " | ".join(readers),
              "|---|---|---|" + "---|" * len(readers)]
        for f in rep["fixtures"]:
            v = f["verdicts"].get("py") or {}
            cells = []
            for r in readers:
                x = f["verdicts"].get(r)
                if x is None:
                    cells.append("-")
                elif r in FULL:
                    cells.append("%s/%s/%s%s" % (x.get("exit_status"), (x.get("signature") or "?")[:7], x.get("dead", "?"),
                                                 "" if f["extract"][r]["ok"] else " EXTRACT-DIFF"))
                else:
                    cells.append("%s/%s/%d%s" % (x.get("exit_status"), (x.get("signature") or "?")[:7], len(x.get("dead_nodes") or []),
                                                 "" if f["extract"][r]["ok"] else " EXTRACT-DIFF"))
            L.append("| %s | %s | %s / %s / %s | %s |" % (f["fixture"], "yes" if f["agree"] else "**NO** " + f["why"],
                                                          v.get("exit_status"), v.get("signature"),
                                                          ",".join(v.get("dead_nodes") or []) or "none", " | ".join(cells)))
        L += ["", "Fixture cells: `exit/signature/dead-count` per reader; bootstrap loaders run with `--strict`.", ""]
    bad = [(r["case"], w, x["why"]) for r in rep["cases"] for w, x in r["reads"].items() if not x["agree"]]
    bad += [(r["case"], "-", "writers differ: %s" % {w: o.get("error") or o.get("sha256", "")[:12] for w, o in r["writers"].items()})
            for r in rep["cases"] if not r["identical"]]
    L += ["## Failures: %d" % rep["failures"], ""] + ["* %s / %s: %s" % b for b in bad]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    sys.exit(main())
