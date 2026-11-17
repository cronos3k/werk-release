import hashlib, json, sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
m = json.loads(z.read("MANIFEST.json"))
n = [x for x in m["nodes"] if x["node_id"] == "rest-poses"][0]["versions"][0]
want = n["input_hash"]
ins = n["input_files"]
raw = {p: hashlib.sha256(z.read(p)).digest() for p in ins}
decl = {}
for node in m["nodes"]:
    for v in node["versions"]:
        for f in v["files"]:
            decl[f["path"]] = f["sha256"]
print("declared vs actual input sha256 agree:", all(raw[p].hex() == decl[p] for p in ins))
variants = {
    "raw, declared order, {}": b"".join(raw[p] for p in ins) + b"{}",
    "raw, reversed order, {}": b"".join(raw[p] for p in reversed(ins)) + b"{}",
    "raw, declared order, nothing": b"".join(raw[p] for p in ins),
    "hex, declared order, {}": b"".join(raw[p].hex().encode() for p in ins) + b"{}",
    "hex, reversed order, {}": b"".join(raw[p].hex().encode() for p in reversed(ins)) + b"{}",
    "raw game.glb only, {}": raw["geometry/game.glb"] + b"{}",
}
for k, b in variants.items():
    h = hashlib.sha256(b).hexdigest()
    print("%-32s %s %s" % (k, h, "MATCH" if h == want else ""))
print("declared                         ", want)
