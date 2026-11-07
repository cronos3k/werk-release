#!/usr/bin/env python3
"""verify_selfrun.py -- check gauntlet/roundSR/selfrun-v1.werk from the outside.

Does what a cold reader would do, and nothing this repository knows that the
package does not: reads the container as a zip, validates the manifest against
the schema the package itself names, recomputes every declared hash, verifies
the signature chain, checks the two layout grammars' arithmetic against the
actual payloads, and checks that every file in the container is reachable from
exactly one node version.

    python gauntlet/roundSR/verify_selfrun.py [path.werk]
"""
import hashlib
import io
import json
import os
import struct
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "store"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print("  [%s] %-52s %s" % ("PASS" if ok else "FAIL", name, detail))


def main(path):
    z = zipfile.ZipFile(path)
    names = z.namelist()
    blobs = {n: z.read(n) for n in names}
    man = json.loads(blobs["MANIFEST.json"].decode("utf-8"))
    sig = json.loads(blobs["SIGNATURE.json"].decode("utf-8"))

    check("container is a zip, %d entries" % len(names), True)
    check("every entry is STORED (no deflate)",
          all(i.compress_type == zipfile.ZIP_STORED for i in z.infolist()))
    check("profile is model/1-draft", man["profile"] == man["profile"] and
          man["profile"] == "model/1-draft", man["profile"])

    # -- manifest validates against the schema the package names -----------
    import jsonschema
    schema_path = man["manifest_schema"]
    check("manifest_schema is present in the package", schema_path in blobs,
          schema_path)
    schema = json.loads(blobs[schema_path].decode("utf-8"))
    errs = sorted(jsonschema.Draft202012Validator(schema).iter_errors(man),
                  key=lambda e: e.path)
    check("manifest validates against its declared schema", not errs,
          "" if not errs else errs[0].message[:160])

    # every other schema the manifest names must also be in the package
    missing = [p for p in man["schemas"].values() if p not in blobs]
    check("every schemas[] path is in the package", not missing, str(missing))
    missing = [p for p in man["layouts"].values() if p not in blobs]
    check("every layouts[] path is in the package", not missing, str(missing))

    # -- payload nodes validate against their own schemas ------------------
    for ntype, spath in sorted(man["schemas"].items()):
        node = next((n for n in man["nodes"] if n["type"] == ntype), None)
        if node is None:
            continue
        s = json.loads(blobs[spath].decode("utf-8"))
        f = node["versions"][0].get("payload_file") or \
            node["versions"][0]["files"][0]["path"]
        doc = json.loads(blobs[f].decode("utf-8"))
        e = sorted(jsonschema.Draft202012Validator(s).iter_errors(doc),
                   key=lambda x: x.path)
        check("%s payload validates" % ntype, not e,
              "" if not e else e[0].message[:160])

    # core.tool / core.tool.config are many-per-package
    for ntype in ("core.tool", "core.tool.config"):
        spath = man["schemas"].get(ntype)
        if not spath:
            continue
        s = json.loads(blobs[spath].decode("utf-8"))
        for node in [n for n in man["nodes"] if n["type"] == ntype]:
            f = node["versions"][0].get("payload_file") or \
                node["versions"][0]["files"][0]["path"]
            doc = json.loads(blobs[f].decode("utf-8"))
            e = list(jsonschema.Draft202012Validator(s).iter_errors(doc))
            check("%s %s payload validates" % (ntype, node["node_id"]), not e,
                  "" if not e else e[0].message[:160])

    # -- every declared hash ------------------------------------------------
    bad = []
    declared = 0
    for n in man["nodes"]:
        for v in n["versions"]:
            for f in v["files"]:
                declared += 1
                b = blobs.get(f["path"])
                if b is None or hashlib.sha256(b).hexdigest() != f["sha256"] \
                        or len(b) != f["size"]:
                    bad.append(f["path"])
    check("manifest file sha256+size: %d/%d" % (declared - len(bad), declared),
          not bad, str(bad[:3]))

    # the core.tool payloads restate their own hashes -- two independent
    # statements of one fact, which is the point of the construction
    restated, restated_bad = 0, []
    for n in [x for x in man["nodes"] if x["type"] == "core.tool"]:
        doc = json.loads(blobs[n["versions"][0]["files"][0]["path"]].decode("utf-8"))
        for f in doc["files"]:
            restated += 1
            if hashlib.sha256(blobs[f["path"]]).hexdigest() != f["sha256"]:
                restated_bad.append(f["path"])
    check("core.tool payload restates %d hashes, all agree" % restated,
          not restated_bad, str(restated_bad))

    # -- reachability: every file in exactly one node version --------------
    reach = {}
    for n in man["nodes"]:
        for v in n["versions"]:
            for f in v["files"]:
                reach.setdefault(f["path"], []).append(n["node_id"])
    unreachable = [p for p in names
                   if p not in ("MANIFEST.json", "SIGNATURE.json")
                   and p not in reach]
    multi = {p: v for p, v in reach.items() if len(v) > 1}
    check("every container file is reachable from a node", not unreachable,
          str(unreachable[:4]))
    check("no file is claimed by two nodes", not multi, str(list(multi)[:3]))

    # -- signature ---------------------------------------------------------
    from werkstore.signature import verify_chain
    mh = hashlib.sha256(blobs["MANIFEST.json"]).hexdigest()
    try:
        ok, why = verify_chain(sig, mh), ""
    except Exception as exc:                                   # noqa: BLE001
        ok, why = False, str(exc)
    check("Ed25519 signature chain verifies", bool(ok), why or "")
    check("SIGNATURE.json top-level manifest_sha256 == sha256(MANIFEST.json)",
          sig["manifest_sha256"] == mh)

    # -- spec_sha256 -------------------------------------------------------
    from spec_sha256 import spec_sha256_of_files
    files = {p: blobs[p] for p in names
             if p not in ("MANIFEST.json", "SIGNATURE.json")}
    check("spec_sha256 recomputes",
          spec_sha256_of_files(files) == man["spec_sha256"], man["spec_sha256"])

    # -- the layout grammars' arithmetic, against the real payloads --------
    ck = blobs["model/stories15M.bin"]
    dim, hidden, nl, nh, nkv, vs, sl = struct.unpack("<7i", ck[:28])
    hs = dim // nh
    off = 28
    for shape in [(vs, dim), (nl, dim), (nl, dim, nh * hs), (nl, dim, nkv * hs),
                  (nl, dim, nkv * hs), (nl, nh * hs, dim), (nl, dim),
                  (nl, hidden, dim), (nl, dim, hidden), (nl, hidden, dim),
                  (dim,), (sl, hs // 2), (sl, hs // 2)]:
        c = 1
        for d in shape:
            c *= d
        off += c * 4
    check("checkpoint layout accounts for every byte (%d)" % off,
          off == len(ck), "file is %d" % len(ck))

    tk = blobs["model/tokenizer.bin"]
    mtl, = struct.unpack("<i", tk[:4])
    p, n, mx = 4, 0, 0
    while p < len(tk) and n < vs:
        _sc, ln = struct.unpack("<fi", tk[p:p + 8])
        p += 8 + ln
        mx = max(mx, ln)
        n += 1
    check("tokenizer walk lands exactly on EOF (%d entries)" % n,
          p == len(tk) and n == vs, "consumed %d of %d" % (p, len(tk)))
    check("tokenizer max_token_length declared == measured",
          mtl == mx, "%d vs %d" % (mtl, mx))

    # -- the test vectors are internally consistent ------------------------
    tv = json.loads(blobs["testvectors/vectors.json"].decode("utf-8"))
    okv = True
    for v in tv["vectors"]:
        b = blobs["testvectors/" + v["stdout_file"]]
        okv &= (hashlib.sha256(b).hexdigest() == v["stdout_sha256_lf"]
                and len(b) == v["stdout_bytes_lf"]
                and b.decode("utf-8") == v["stdout_text"]
                and b"\r" not in b
                and len(v["token_ids"]) == v["token_count"]
                and v["token_ids"][0] == 1
                and v["temperature"] == 0.0)
    check("test vectors: %d, each self-consistent, LF, BOS-first, t=0"
          % len(tv["vectors"]), okv)
    check("test-vector config matches the checkpoint header",
          tv["model"]["config"]["dim"] == dim
          and tv["model"]["config"]["vocab_size"] == vs
          and tv["model"]["checkpoint_sha256"] == hashlib.sha256(ck).hexdigest())

    # -- doctrine ----------------------------------------------------------
    tools = [n for n in man["nodes"] if n["type"] == "core.tool"]
    forms = {n["meta"]["form"] for n in tools}
    check("every core.tool is form=source (no prebuilt anywhere)",
          forms == {"source"}, str(forms))
    check("primary names all four parts",
          set(man["primary"]) == {"weights", "tokenizer", "runtime",
                                  "testvectors"}, str(man["primary"]))
    check("preview prefix precedes the weights",
          man["container"]["preview_prefix_bytes"] < len(ck),
          "%d < %d" % (man["container"]["preview_prefix_bytes"], len(ck)))

    print("\n%d PASS, %d FAIL" % (len(PASS), len(FAIL)))
    if FAIL:
        print("FAILED: " + ", ".join(FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1
                          else os.path.join(HERE, "selfrun-v1.werk")))
