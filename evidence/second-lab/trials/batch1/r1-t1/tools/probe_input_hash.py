"""Try plausible input_hash constructions for node rest-poses."""
import hashlib, itertools, sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
want = "60e08ed15118810abfeeee57aa45a4bbbbc3e21d90c887debaff8bd585d496c8"
files = ["geometry/game.glb", "physics/bounds.json"]
raw = {f: hashlib.sha256(z.read(f)).digest() for f in files}
tails = {"{}": b"{}", "none": b"", "null": b"null"}
for order in itertools.permutations(files):
    for enc in ("raw", "hex"):
        for tn, t in tails.items():
            h = hashlib.sha256()
            for f in order:
                h.update(raw[f] if enc == "raw" else raw[f].hex().encode())
            h.update(t)
            r = h.hexdigest()
            print(("MATCH " if r == want else "      ") + f"{order} {enc} tail={tn} {r}")
# single-input variants
for f in files:
    for tn, t in tails.items():
        r = hashlib.sha256(raw[f] + t).hexdigest()
        print(("MATCH " if r == want else "      ") + f"only {f} tail={tn} {r}")
