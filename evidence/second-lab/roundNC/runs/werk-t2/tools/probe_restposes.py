import hashlib, json, sys, zipfile, itertools
z = zipfile.ZipFile(sys.argv[1])
m = json.loads(z.read("MANIFEST.json"))
node = [n for n in m["nodes"] if n["node_id"] == "rest-poses"][0]
v = node["versions"][0]
target = v["input_hash"]
print("declared", target)
files = v["input_files"]
raw = {p: hashlib.sha256(z.read(p)).digest() for p in files}
cands = {}
for perm in itertools.permutations(files):
    for tail_name, tail in (("{}", b"{}"), ("none", b"")):
        for enc_name, enc in (("raw", lambda d: d), ("hex", lambda d: d.hex().encode())):
            h = hashlib.sha256()
            for p in perm:
                h.update(enc(raw[p]))
            h.update(tail)
            cands["%s %s %s" % (list(perm), tail_name, enc_name)] = h.hexdigest()
for k, val in cands.items():
    print(("MATCH " if val == target else "      ") + val + "  " + k)
print("bounds.json:", z.read("physics/bounds.json").decode())
