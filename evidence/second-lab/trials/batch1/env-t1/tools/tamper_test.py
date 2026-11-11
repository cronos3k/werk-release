"""Make damaged COPIES of the package and check werk_inspect flags each one."""
import os
import subprocess
import sys

src = sys.argv[1]
here = os.path.dirname(os.path.abspath(__file__))
out = os.path.join(here, "tamper")
os.makedirs(out, exist_ok=True)
buf = open(src, "rb").read()

cases = {
    # one byte inside the WKRP pose 0 probability (poses/rest.wkrp data at 956780+30+15)
    "wkrp-byte": (buf.index(b"WKRP", 956780) + 400 + 24, None),
    # one byte inside MANIFEST.json text (the entity name)
    "manifest-byte": (buf.index(b"Wooden crate (small"), None),
}
for name, (off, _) in cases.items():
    b = bytearray(buf)
    b[off] ^= 0x01
    p = os.path.join(out, name + ".werk")
    open(p, "wb").write(bytes(b))
    r = subprocess.run([sys.executable, "-I", os.path.join(here, "werk_inspect.py"), p],
                       capture_output=True, text=True, encoding="utf-8")
    lines = [l for l in (r.stdout + r.stderr).splitlines() if "FAIL" in l or "SUMMARY" in l or "Error" in l]
    print("== %s (byte %d flipped), exit %d" % (name, off, r.returncode))
    for l in lines:
        print("   " + l.strip())
