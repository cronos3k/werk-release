#!/usr/bin/env python3
"""damage_agree.py -- do the libs/ readers and werkc agree on damaged containers?

    python tests/damage_agree.py [--werkc PATH] [--cc CC] [--rustc RUSTC] [--out DIR]

One signed package (written by the Python library from make_inputs.py) is
damaged one bit at a time at chosen offsets: every byte of the EOCD, of the
first three central-directory records and of five local headers, every 7th
byte of the rest of the central directory, and a sample of MANIFEST.json and
SIGNATURE.json bytes. For each variant:

  * py, js, es3 (the libs/ readers) must give the SAME (exit, signature, dead
    set) -- MINI-SPECS 5.4's six reader rules, SPEC 6, 10.1 and 12.1;
  * werkc (werk-core) must agree with them on refusal, signature and the
    dead set (its exit may additionally be 1 for a JSON Schema finding the
    libs/ readers do not look for);
  * the bundled loaders (ref-py, ref-c, ref-rs) must agree on refusal and
    the dead set and say `unverified` (or present-and-invalid) for a chain
    they cannot check.
No reader may crash (exit other than 0/1/2, or a traceback).
"""

import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIBS = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(LIBS, "python"))
sys.path.insert(0, HERE)
import werk  # noqa: E402
import cross_matrix as cm  # noqa: E402


def py_verdict(p):
    try:
        v = werk.open(p).verdict()
        return {"exit": v["exit"], "signature": v["signature"], "dead": v["dead_nodes"]}
    except werk.ContainerRefusal as e:
        return {"exit": 2, "refusal": e.code}
    except Exception as e:  # noqa: BLE001
        return {"exit": -1, "crash": repr(e)}


def norm(v):
    if v.get("exit") == 2:
        return ("refused",)
    if v.get("exit") not in (0, 1):
        return ("crash", v.get("crash") or v.get("error"))
    return (v.get("exit"), v.get("signature"), tuple(v.get("dead") if "dead" in v else v.get("dead_nodes") or []))


def offsets(blob):
    e = cm.zip_entry_span  # noqa: F841
    eocd = blob.rfind(b"PK\x05\x06")
    count, _size, cdo = struct.unpack_from("<HII", blob, eocd + 10)
    picks = set(range(eocd, len(blob)))
    p = cdo
    recs = []
    for i in range(count):
        nlen, mlen, klen = struct.unpack_from("<HHH", blob, p + 28)
        lho = struct.unpack_from("<I", blob, p + 42)[0]
        recs.append((p, 46 + nlen + mlen + klen, lho, blob[p + 46:p + 46 + nlen].decode()))
        p += 46 + nlen + mlen + klen
    for j, (p, ln, lho, name) in enumerate(recs):
        rng = range(p, p + ln)
        picks.update(rng if j < 3 else list(rng)[::7])
    for (p, ln, lho, name) in recs[:5]:
        nlen, mlen = struct.unpack_from("<HH", blob, lho + 26)
        picks.update(range(lho, lho + 30 + nlen))
    for name, step in (("MANIFEST.json", 97), ("SIGNATURE.json", 11)):
        off, size = cm.zip_entry_span(bytes(blob), name)
        picks.update(range(off, off + size, step))
    return sorted(picks)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(LIBS, "_scratch", "damage"))
    ap.add_argument("--werkc"), ap.add_argument("--cc"), ap.add_argument("--rustc"), ap.add_argument("--node")
    a = ap.parse_args()
    work = os.path.abspath(a.out)
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work, exist_ok=True)
    tools = cm.setup_tools(a, work)
    inputs = os.path.join(work, "inputs")
    os.environ["WERK_BIG_MB"] = "1"
    subprocess.run([tools["python"], os.path.join(HERE, "make_inputs.py"), inputs], stdout=subprocess.PIPE)
    src = os.path.join(work, "base.werk")
    with open(os.path.join(inputs, "source.png"), "rb") as fh:
        png = fh.read()
    with open(os.path.join(inputs, "thumb.png"), "rb") as fh:
        thumb = fh.read()
    werk.write_image_package(src, png, name="Damage base", thumbnail_png=thumb, created="2026-11-07T12:00:00Z",
                             uuid="1a6e0000-0000-4000-8000-0000000000ff",
                             sign_key=open(os.path.join(inputs, "key.hex")).read().strip(),
                             signer={"uri": "urn:werk:test:k1", "kind": "service"})
    with open(src, "rb") as fh:
        blob = bytearray(fh.read())
    offs = offsets(bytes(blob))
    vdir = os.path.join(work, "v")
    os.makedirs(vdir)
    paths = []
    for o in offs:
        b = bytearray(blob)
        b[o] ^= 0x01
        p = os.path.join(vdir, "o%07d.werk" % o)
        with open(p, "wb") as fh:
            fh.write(bytes(b))
        paths.append(p)
    lst = os.path.join(work, "list.txt")
    with open(lst, "w", newline="") as fh:
        fh.write("\n".join(paths) + "\n")
    res = {p: {} for p in paths}
    for p in paths:
        res[p]["py"] = py_verdict(p)
    for build, key in (("werk.js", "js"), ("werk.jsx", "es3")):
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
        ids = set()
        try:
            ids = set(n.node_id for n in werk.open(p).nodes)
        except Exception:  # noqa: BLE001
            pass
        for r in cm.BOOT:
            b = cm.read_boot(r, tools, p, ids or {"spec", "license", "readme", "image-source", "image-thumb",
                                                    "loader-python", "loader-rust", "loader-c"})
            if b:
                res[p][r] = {"exit": b["exit_status"], "signature": b.get("signature"), "dead": b.get("dead_nodes", [])}
    tally = {"variants": len(paths), "libs_agree": 0, "werkc_agree": 0, "boot_agree": {r: 0 for r in cm.BOOT},
             "crashes": 0}
    bad = []
    for p in paths:
        r = res[p]
        libs = [norm(r[k]) for k in ("py", "js", "es3")]
        if any(x[0] == "crash" for x in libs) or r["werkc"]["exit"] not in (0, 1, 2):
            tally["crashes"] += 1
        if libs[0] == libs[1] == libs[2]:
            tally["libs_agree"] += 1
        else:
            bad.append((os.path.basename(p), "libs", libs))
        ref = libs[0]
        w = norm(r["werkc"])
        wcmp = w if w[0] in ("refused", "crash") else w[1:]
        rcmp = ref if ref[0] in ("refused", "crash") else ref[1:]
        if wcmp == rcmp:
            tally["werkc_agree"] += 1
        else:
            bad.append((os.path.basename(p), "werkc", w, ref))
        for k in cm.BOOT:
            if k not in r:
                continue
            bv = r[k]
            if ref == ("refused",):
                ok = bv["exit"] == 2
            elif bv["exit"] == 2:
                ok = False
            else:
                fs = ref[1]
                sig_ok = (bv["signature"] == "absent") if fs == "absent" else bv["signature"] in ("unverified", "present-and-invalid")
                ok = sig_ok and tuple(bv["dead"]) == ref[2]
            if ok:
                tally["boot_agree"][k] += 1
            else:
                bad.append((os.path.basename(p), k, (bv["exit"], bv["signature"], bv["dead"]), ref))
    with open(os.path.join(work, "damage_agree.json"), "w") as fh:
        json.dump({"tally": tally, "disagreements": bad}, fh, indent=1, default=str)
    print(json.dumps(tally, indent=1))
    for b in bad[:25]:
        print("DISAGREE", b)
    print("disagreements: %d" % len(bad))
    shutil.rmtree(vdir, ignore_errors=True)
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
