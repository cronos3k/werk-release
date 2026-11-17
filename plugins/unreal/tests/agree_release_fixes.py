#!/usr/bin/env python3
"""agree_release_fixes.py -- WerkLink's reader against the release readers on the
release-fixes rules (SPEC 1, 6, 12.1; MINI-SPECS 5.4).

    py -3.12 tests/agree_release_fixes.py --repo <release-fixes tree> --libs <libs> --out <dir>

Builds damaged variants of two release fixtures (crate-tex-v1, unsigned; crate-cc0-lean-v1,
signed) and asks three readers for a verdict on each: WerkLink's engine-free core
(`tests/.build/werk_gate.exe --verdict`), the release Python library (`python -m werk verify
--json`) and werkc. A clause passes when WerkLink's exit status and dead-node set equal the
library's and werkc's, and its signature word agrees (WerkLink, without Ed25519, says
`unverified` where a full reader says `signed-and-valid`; `absent` and
`present-and-invalid` must be identical). Prints one line per variant; exit 0 when all agree.
"""

import argparse
import json
import os
import struct
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
EXE = os.path.join(HERE, ".build", "werk_gate.exe")


def entries(path):
    z = zipfile.ZipFile(path)
    return [(i.filename, z.read(i.filename)) for i in z.infolist()]


def write_zip(path, items):
    """Store-mode zip; zipfile warns about duplicate names but writes them."""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as z:
            for name, data in items:
                info = zipfile.ZipInfo(name, date_time=(2026, 11, 7, 0, 0, 0))
                z.writestr(info, data)


def with_manifest(items, fn):
    out = []
    for name, data in items:
        if name == "MANIFEST.json":
            m = json.loads(data)
            fn(m)
            data = (json.dumps(m, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        out.append((name, data))
    return out


def replace(items, name, data):
    return [(n, data if n == name else d) for n, d in items]


def variants(fx):
    tex = entries(os.path.join(fx, "crate-tex-v1.werk"))
    sig = entries(os.path.join(fx, "crate-cc0-lean-v1.werk"))
    sigdoc = json.loads(dict(sig)["SIGNATURE.json"])
    victim = "bounds"

    def node(m, nid):
        return [n for n in m["nodes"] if n["node_id"] == nid][0]

    yield "baseline-unsigned", tex
    yield "baseline-signed", sig
    yield "duplicate-entry", tex + [("README.txt", b"a second README.txt\n")]
    yield "signature-not-json", replace(sig, "SIGNATURE.json", b"not json at all\n")
    yield "signature-not-object", replace(sig, "SIGNATURE.json", b"[1, 2, 3]\n")
    bad = json.loads(json.dumps(sigdoc))
    bad["chain"][-1]["manifest_sha256"] = "0" * 64
    yield "signature-wrong-manifest-hash", replace(sig, "SIGNATURE.json", json.dumps(bad).encode())
    foreign = json.loads(json.dumps(sigdoc))
    foreign["algorithm"] = "x-unknown"
    yield "signature-foreign-algorithm", replace(sig, "SIGNATURE.json", json.dumps(foreign).encode())
    yield "file-record-without-size", with_manifest(
        tex, lambda m: node(m, victim)["versions"][0]["files"][0].pop("size"))
    yield "file-record-size-not-integer", with_manifest(
        tex, lambda m: node(m, victim)["versions"][0]["files"][0].__setitem__("size", "12"))
    yield "active-not-integer", with_manifest(tex, lambda m: node(m, victim).__setitem__("active", "one"))
    yield "versions-empty", with_manifest(tex, lambda m: node(m, victim).__setitem__("versions", []))
    yield "node-without-type", with_manifest(tex, lambda m: node(m, victim).pop("type"))
    yield "nodes-not-array", with_manifest(tex, lambda m: m.__setitem__("nodes", {}))
    yield "nodes-missing", with_manifest(tex, lambda m: m.pop("nodes"))
    yield "manifest-not-object", [(n, b"[1, 2]\n" if n == "MANIFEST.json" else d) for n, d in tex]
    yield "manifest-unparseable", [(n, b"{not json\n" if n == "MANIFEST.json" else d) for n, d in tex]
    yield "manifest-absent", [(n, d) for n, d in tex if n != "MANIFEST.json"]

    # MINI-SPECS 5.4 applied to manifest-declared paths, version-scoped (SPEC 10 step 5 [B],
    # 10.1, 12.1): the cross-matrix unsafe-path cases of libs/tests/cross_matrix.py, rebuilt
    # on crate-tex-v1. An unsafe files[] path costs only ITS version: a single-version node
    # dies, a multi-version node falls back to the newest valid earlier version, an unsafe
    # path in a version the walk did not need is still reported; `schema-invalid`, exit 1.
    yield "unsafe-path", unsafe(tex, "README.txt")
    mv = two_versions(tex, MV_NODE)
    yield "multiversion-baseline", mv
    yield "unsafe-path-multiversion", unsafe(mv, MV_V2)
    yield "unsafe-path-payload-file", unsafe(mv, MV_V2, payload_file=True)
    yield "unsafe-path-old-version", unsafe(mv, MV_V1)
    # SPEC 10 step 5 [B]: the walk never goes to a version NEWER than `active` -- it is not
    # tried (an unsafe path in it is reported all the same) and it cannot rescue the node.
    older = with_manifest(mv, lambda m: node(m, MV_NODE).__setitem__("active", 1))
    yield "unsafe-path-newer-version", unsafe(older, MV_V2)
    yield "newer-version-not-tried", [(n, (d[:-1] + bytes([d[-1] ^ 1])) if n == MV_V1 else d)
                                      for n, d in older]


UNSAFE = "../evil.png"
MV_NODE = "tex-crate-tex-albedo"
MV_V1 = "textures/tex-crate-tex-albedo.png"
MV_V2 = "textures/tex-crate-tex-albedo@2.png"


def two_versions(items, nid):
    """crate-tex-v1 with a v2 of `nid` (a copy of v1 under a new path, the same bytes),
    active 2 -- the shape of the cross-matrix `append` step."""
    data = dict(items)[MV_V1]

    def fn(m):
        n = [x for x in m["nodes"] if x["node_id"] == nid][0]
        v2 = json.loads(json.dumps(n["versions"][0]))
        v2["v"] = 2
        v2["files"][0]["path"] = MV_V2
        v2["note"] = "Re-exported the albedo -- v2."
        n["versions"].append(v2)
        n["active"] = 2
    return with_manifest(items, fn) + [(MV_V2, data)]


def unsafe(items, path, payload_file=False):
    """Rename one declared file to ../evil.png in MANIFEST.json and in the zip (same bytes,
    same sha256 and size), as cross_matrix.py's @unsafe-path does."""
    def fn(m):
        hit = 0
        for n in m["nodes"]:
            for v in n["versions"]:
                for f in v["files"]:
                    if f["path"] == path:
                        f["path"] = UNSAFE
                        hit += 1
                        if payload_file:
                            v["payload_file"] = UNSAFE
        assert hit == 1, path
    return [(UNSAFE if n == path else n, d) for n, d in with_manifest(items, fn)]


def patch_bytes(path, kind):
    b = bytearray(open(path, "rb").read())
    eocd = len(b) - 22
    cd = struct.unpack_from("<I", b, eocd + 16)[0]
    if kind == "flag-bit-3":
        b[cd + 8] |= 0x08
    elif kind == "eocd-trailing-byte":
        b += b"\x00"
    elif kind.startswith("name-invalid-utf8"):
        # record k's name, last byte -> 0xFF (local header left alone): k = 0 is
        # MANIFEST.json (-> nothing loads), the -late variant damages the last record
        recs, p = [], cd
        for _ in range(struct.unpack_from("<H", b, eocd + 10)[0]):
            n, e, c = struct.unpack_from("<HHH", b, p + 28)
            recs.append((p, n))
            p += 46 + n + e + c
        rp, n = recs[-1] if kind.endswith("-late") else recs[0]
        b[rp + 46 + n - 1] = 0xFF
    open(path, "wb").write(bytes(b))


def werklink(path):
    p = subprocess.run([EXE, "--verdict", path], capture_output=True, text=True)
    f = dict(kv.split("=", 1) for kv in p.stdout.split())
    return {"exit": int(f["exit"]), "signature": f["signature"],
            "dead": sorted(x for x in f["dead"].split(",") if x), "codes": f["codes"]}


def full(cmd, path, env):
    p = subprocess.run(cmd + ["verify", path, "--json"], capture_output=True, text=True, env=env)
    try:
        v = json.loads(p.stdout)
    except ValueError:
        return {"exit": p.returncode, "signature": "-", "dead": [], "codes": (p.stderr or p.stdout)[-120:]}
    dead = v.get("dead_nodes") or []
    return {"exit": p.returncode, "signature": v.get("signature") or "-",
            "dead": sorted(dead if isinstance(dead, list) else []),
            "codes": ",".join(v.get("error_codes") or [])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--libs", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    env = dict(os.environ, PYTHONPATH=os.path.join(a.libs, "python"), PYTHONIOENCODING="utf-8")
    werkc = os.path.join(a.libs, "_target", "release", "werkc.exe")
    fx = os.path.join(a.repo, "fixtures")
    cases = list(variants(fx))
    for kind in ("flag-bit-3", "eocd-trailing-byte", "name-invalid-utf8", "name-invalid-utf8-late"):
        cases.append((kind, None))
    rows, ok_all = [], True
    for name, items in cases:
        path = os.path.join(a.out, name + ".werk")
        if items is None:
            write_zip(path, entries(os.path.join(fx, "crate-tex-v1.werk")))
            patch_bytes(path, name)
        else:
            write_zip(path, items)
        w = werklink(path)
        py = full([sys.executable, "-m", "werk"], path, env)
        rc = full([werkc], path, env)
        sig_ok = (w["signature"] == py["signature"]
                  or (w["signature"] == "unverified" and py["signature"] in ("signed-and-valid", "unverified"))
                  or (w["exit"] == 2 and py["exit"] == 2))
        ok = w["exit"] == py["exit"] == rc["exit"] and w["dead"] == py["dead"] and sig_ok
        if name.startswith("unsafe-path"):
            # the same report code as the libraries: schema-invalid
            ok = ok and "schema-invalid" in w["codes"].split(",") and "schema-invalid" in py["codes"].split(",")
        ok_all = ok_all and ok
        rows.append({"case": name, "ok": ok, "werklink": w, "python": py, "werkc": rc})
        print("[%s] %-32s werklink exit %d sig %s dead %s | py exit %d sig %s dead %s | werkc exit %d" % (
            "PASS" if ok else "FAIL", name, w["exit"], w["signature"], w["dead"] or "-",
            py["exit"], py["signature"], py["dead"] or "-", rc["exit"]))
    json.dump(rows, open(os.path.join(a.out, "agree.json"), "w"), indent=1)
    print("%d of %d variants agree" % (sum(r["ok"] for r in rows), len(rows)))
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
