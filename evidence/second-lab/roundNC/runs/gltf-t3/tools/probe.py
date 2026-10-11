"""Read-only probe of the referenced files: hex heads/tails, printable runs, sha256."""
import hashlib, re, sys, os

base = sys.argv[1]
for name in ("crate-nc-v1.gltf", "crate-nc-v1.bin", "crate_diffuse.png"):
    data = open(os.path.join(base, name), "rb").read()
    print("==", name, len(data), "bytes sha256", hashlib.sha256(data).hexdigest())
    print(" head:", data[:64].hex(" "))
    print(" tail:", data[-48:].hex(" "))
    runs = re.findall(rb"[\x20-\x7e]{6,}", data)
    print(" printable runs (>=6):", len(runs))
    for r in runs[:40]:
        print("   ", r[:120])
