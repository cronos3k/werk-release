"""Cross-check werk_reader's Ed25519 + message construction on spec/examples (MINI-SPECS 12.1)."""
import sys, json, hashlib
sys.path.insert(0, sys.argv[1])          # directory holding werk_reader.py (my own code)
import werk_reader as w
mb = open(sys.argv[2], "rb").read()      # copy of spec/examples/MANIFEST.example.json
sig = json.load(open(sys.argv[3], encoding="utf-8"))
e = sig["chain"][0]
msg = w.sig_message(e)
print("manifest sha256", hashlib.sha256(mb).hexdigest(), "(expect c421d2e8...)")
print("len(message)", len(msg), "(expect 203)")
print("sha256(message)", hashlib.sha256(msg).hexdigest(), "(expect 11e260cc...)")
print("verify", w.ed25519_verify(bytes.fromhex(e["public_key"]), msg, bytes.fromhex(e["signature"])))
print("chain state", w.verify_chain(sig, mb))
