#!/usr/bin/env python3
"""damage_profiles.py -- one-bit / one-byte damage on the six profile fixtures: do all readers agree?

    python profiles/tools/damage_profiles.py [--fixtures profiles/fixtures] [--out DIR]
                                             [--werkc PATH] [--cc CC] [--rustc RUSTC] [--node NODE]

Built on the release's own tooling (libs/tests/cross_matrix.py and damage_agree.py: the same
readers, the same verdict normalisation, the same agreement rules). Two families of variants per
fixture:

  container  one bit flipped at: every byte of the EOCD; every byte of the first three
             central-directory records and every 41st byte of the rest; every byte of the first
             two local headers; every 997th byte of MANIFEST.json.
  payload    for EVERY file of every profile node (not spec/, loaders/, tools/, LICENSE, README,
             HOW-TO-READ, revisions/): one byte in the middle of the stored data XOR 0x01, the
             entry's zip CRC-32 patched (in the local header and the central directory) so that
             only the werk hash can catch it.

For every variant: py, js, es3 must give the same (exit, signature, dead set); werkc must agree
on refusal, signature and dead set; the bundled loaders (ref-py, ref-c, ref-rs) on refusal and
dead set; nobody may crash. For payload variants additionally the profile's REFERENCE READER
(profiles/<name>/read_<name>.py, imported) must exit 1 and name the damaged file's node in its
`dead` list or its `file_failures`. Writes <out>/damage_profiles.json; exit 0 when no
disagreement.
"""
import argparse
import importlib
import json
import os
import shutil
import struct
import subprocess
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILES = os.path.dirname(HERE)
LIBS = os.path.join(os.path.dirname(PROFILES), "libs")
sys.path.insert(0, os.path.join(LIBS, "python"))
sys.path.insert(0, os.path.join(LIBS, "tests"))
import werk  # noqa: E402
import cross_matrix as cm  # noqa: E402
import damage_agree as da  # noqa: E402

BASE_PREFIXES = ("spec/", "loaders/", "tools/", "revisions/")
BASE_FILES = ("LICENSE", "README.txt", "HOW-TO-READ.md", "MANIFEST.json")


def central(blob):
    e = blob.rfind(b"PK\x05\x06")
    count, _s, cdo = struct.unpack_from("<HII", blob, e + 10)
    recs, p = [], cdo
    for _ in range(count):
        nlen, mlen, klen = struct.unpack_from("<HHH", blob, p + 28)
        lho = struct.unpack_from("<I", blob, p + 42)[0]
        recs.append((p, 46 + nlen + mlen + klen, lho, blob[p + 46:p + 46 + nlen].decode("utf-8")))
        p += 46 + nlen + mlen + klen
    return e, recs


def container_offsets(blob):
    eocd, recs = central(blob)
    picks = set(range(eocd, len(blob)))
    for j, (p, ln, _lho, _n) in enumerate(recs):
        rng = range(p, p + ln)
        picks.update(rng if j < 3 else list(rng)[::41])
    for (_p, _ln, lho, _n) in recs[:2]:
        nlen, mlen = struct.unpack_from("<HH", blob, lho + 26)
        picks.update(range(lho, lho + 30 + nlen))
    off, size = cm.zip_entry_span(bytes(blob), "MANIFEST.json")
    picks.update(range(off, off + size, 997))
    return sorted(picks)


def payload_variants(blob, owner):
    """(name, bytes, node, path) per profile file: one byte flipped, CRC patched."""
    _e, recs = central(blob)
    out = []
    for (p, _ln, lho, name) in recs:
        if name.startswith(BASE_PREFIXES) or name in BASE_FILES or name not in owner:
            continue
        off, size = cm.zip_entry_span(bytes(blob), name)
        if size == 0:
            continue
        b = bytearray(blob)
        b[off + size // 2] ^= 0x01
        crc = zlib.crc32(bytes(b[off:off + size])) & 0xFFFFFFFF
        struct.pack_into("<I", b, lho + 14, crc)
        struct.pack_into("<I", b, p + 16, crc)
        out.append((name, bytes(b), owner[name], name))
    return out


def verdicts(paths, tools, all_ids):
    res = {p: {} for p in paths}
    for p in paths:
        res[p]["py"] = da.py_verdict(p)
    lst = os.path.join(os.path.dirname(paths[0]), "list.txt")
    with open(lst, "w", newline="") as fh:
        fh.write("\n".join(paths) + "\n")
    for build, key in (("werk.js", "js"), ("werk.jsx", "es3")):
        if not tools.get("node"):
            continue
        o = subprocess.run([tools["node"], os.path.join(LIBS, "js", "tests", "verify_batch.js"), build, lst],
                           stdout=subprocess.PIPE).stdout.decode().splitlines()
        for p, line in zip(paths, o):
            v = json.loads(line)
            res[p][key] = {"exit": v["exit"], "signature": v.get("signature"), "dead": v.get("dead_nodes", []),
                           "crash": v.get("crash")}
    for p in paths:
        w = cm.read_full("werkc", tools, p)
        res[p]["werkc"] = {"exit": w.get("exit_status"), "signature": w.get("signature"),
                           "dead": w.get("dead_nodes", []), "error": w.get("error")}
        for r in cm.BOOT:
            b = cm.read_boot(r, tools, p, all_ids)
            if b:
                res[p][r] = {"exit": b["exit_status"], "signature": b.get("signature"), "dead": b.get("dead_nodes", [])}
    return res


def judge(r):
    """[] when the readers agree on this variant, else the disagreements (damage_agree rules)."""
    bad = []
    libs = [da.norm(r[k]) for k in ("py", "js", "es3") if k in r]
    if any(x[0] == "crash" for x in libs) or r["werkc"]["exit"] not in (0, 1, 2):
        bad.append(("crash", libs, r["werkc"]))
    if len(set(libs)) != 1:
        bad.append(("libs", libs))
    ref = libs[0]
    w = da.norm(r["werkc"])
    wcmp = w if w[0] in ("refused", "crash") else w[1:]
    rcmp = ref if ref[0] in ("refused", "crash") else ref[1:]
    if wcmp != rcmp:
        bad.append(("werkc", w, ref))
    for k in cm.BOOT:
        if k not in r:
            continue
        bv = r[k]
        if ref == ("refused",):
            ok = bv["exit"] == 2
        elif bv["exit"] == 2:
            ok = False
        else:
            ok = (bv["signature"] == "absent") and tuple(bv["dead"]) == ref[2]
        if not ok:
            bad.append((k, (bv["exit"], bv["signature"], bv["dead"]), ref))
    return bad


def reader_module(prof):
    d = os.path.join(PROFILES, prof)
    if d not in sys.path:
        sys.path.insert(0, d)
    return importlib.import_module("read_" + prof.replace("-", "_"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", default=os.path.join(PROFILES, "fixtures"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--werkc"), ap.add_argument("--cc"), ap.add_argument("--rustc"), ap.add_argument("--node")
    a = ap.parse_args()
    work = os.path.abspath(a.out)
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    tools = cm.setup_tools(a, work)
    report = {"tools": {k: v for k, v in tools.items() if isinstance(v, str) or v is None}, "fixtures": {}}
    total_bad = 0
    for fn in sorted(os.listdir(a.fixtures)):
        if not fn.endswith("-v1.werk"):
            continue
        prof = fn[:-len("-v1.werk")]
        R = reader_module(prof)
        src = os.path.join(a.fixtures, fn)
        blob = bytearray(open(src, "rb").read())
        pkg = werk.open(src)
        owner = {}
        for n in pkg.nodes:
            for v in n.versions:
                for f in v["files"]:
                    owner[f["path"]] = n.node_id
        all_ids = set(n.node_id for n in pkg.nodes)
        vdir = os.path.join(work, prof)
        os.makedirs(vdir)
        cpaths = []
        for o in container_offsets(bytes(blob)):
            b = bytearray(blob)
            b[o] ^= 0x01
            p = os.path.join(vdir, "c%07d.werk" % o)
            open(p, "wb").write(bytes(b))
            cpaths.append(p)
        ppaths, pmeta = [], {}
        for i, (name, data, nid, path) in enumerate(payload_variants(bytes(blob), owner)):
            p = os.path.join(vdir, "p%04d.werk" % i)
            open(p, "wb").write(data)
            ppaths.append(p)
            pmeta[p] = (nid, path)
        res = verdicts(cpaths + ppaths, tools, all_ids)
        tally = {"container_variants": len(cpaths), "payload_variants": len(ppaths), "agree": 0,
                 "reader_named_damage": 0, "refused_by_all": 0}
        bad = []
        for p in cpaths + ppaths:
            d = judge(res[p])
            if not d:
                tally["agree"] += 1
                if da.norm(res[p]["py"]) == ("refused",):
                    tally["refused_by_all"] += 1
            else:
                bad.append((os.path.basename(p), d))
        for p in ppaths:
            nid, path = pmeta[p]
            try:
                got = R.read(p)
                named = any(d["node"] == nid for d in got["dead"]) or any(f.startswith(nid + ":") for f in got["file_failures"])
                rc = 1 if (got["dead"] or got["file_failures"]) else 0
            except R.Refusal:
                named, rc = True, 2   # the structure node itself was damaged: the reader refuses, and says why
            ok = named and rc in (1, 2)
            if ok:
                tally["reader_named_damage"] += 1
            else:
                bad.append((os.path.basename(p), ("reference-reader", nid, path, rc)))
        total_bad += len(bad)
        report["fixtures"][fn] = {"tally": tally, "disagreements": bad[:50], "disagreement_count": len(bad),
                                  "payload_cases": {os.path.basename(p): {"node": pmeta[p][0], "path": pmeta[p][1],
                                                                          "full_dead": res[p]["py"].get("dead"),
                                                                          "werkc_dead": res[p]["werkc"].get("dead")}
                                                    for p in ppaths}}
        print("%-26s %s  disagreements %d" % (fn, json.dumps(tally), len(bad)))
        shutil.rmtree(vdir, ignore_errors=True)
    report["disagreements_total"] = total_bad
    with open(os.path.join(work, "damage_profiles.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, default=str)
    print("disagreements: %d" % total_bad)
    return 0 if total_bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
