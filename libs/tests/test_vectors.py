#!/usr/bin/env python3
"""test_vectors.py -- the spec's own test vectors, run against every libs/ library.

    python tests/test_vectors.py

Python lib, JS (dist/werk.js) and ES3 (dist/werk.jsx under Node):
  * SHA-256 vectors (MINI-SPECS section 11)
  * canonical JSON vector of MINI-SPECS section 3 (sha256 13a29066...)
  * the worked signature of spec/examples (MANIFEST.example.json +
    SIGNATURE.example.json) verifies; RFC 8032 test 1 signs to its published
    signature; one flipped bit fails
  * WRITING-IMAGE.md: the 8x8 source PNG and the thumbnail input_hash
  * float spelling: 20 000 doubles across magnitudes, JS pyFloat == Python repr
Rust: `cargo test --bin werkc` runs the same float table (json.rs).
"""

import hashlib
import json
import os
import random
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIBS = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(LIBS, "python"))
import werk  # noqa: E402

RFC_SK = "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"
RFC_PK = "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
RFC_SIG = ("e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46b"
           "d25bf5f0595bbe24655141438e7a100b")


def check(name, ok, detail=""):
    print("%s %s %s" % ("PASS" if ok else "FAIL", name, ascii(detail)))
    return 0 if ok else 1


def py_checks():
    bad = 0
    bad += check("py sha256('abc')", werk._core.sha256_hex(b"abc") ==
                 "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
    v = werk._core.OrderedDict([("n", 1), ("name", "Größe"), ("note", "a→b"), ("tab", "x\ty")])
    c = werk.json_canonical(v)
    bad += check("py canonical JSON vector", hashlib.sha256(c).hexdigest() ==
                 "13a2906649470c284a45bc33763ca934e41edd18e32e764443acfd4aba11baa6", c.decode("utf-8"))
    sk = bytes.fromhex(RFC_SK)
    bad += check("py ed25519 RFC 8032 test 1 public key", werk.ed25519_public_key(sk).hex() == RFC_PK)
    bad += check("py ed25519 RFC 8032 test 1 signature", werk.ed25519_sign(sk, b"").hex() == RFC_SIG)
    b = werk.default_bundle()
    man, sig = b.data("spec/examples/MANIFEST.example.json"), b.data("spec/examples/SIGNATURE.example.json")
    problems, signers = werk.verify_chain(sig, hashlib.sha256(man).hexdigest())
    bad += check("py spec/examples signature verifies", problems == [], str(signers))
    tampered = bytearray(man)
    tampered[100] ^= 1
    problems, _ = werk.verify_chain(sig, hashlib.sha256(bytes(tampered)).hexdigest())
    bad += check("py spec/examples signature fails on a changed manifest", bool(problems))
    sys.path.insert(0, HERE)
    import make_inputs
    src = make_inputs.png(make_inputs.pattern(8, 0))
    bad += check("py WRITING-IMAGE source.png", hashlib.sha256(src).hexdigest() ==
                 "564ee5f1f8ff4190b4683e3de4ec8775966988ae8be4de3a5aee61d643090b7d")
    params = werk._core.OrderedDict([("resample", "box"), ("width", 4), ("height", 4),
                                     ("on", "stored-values"), ("rounding", "half-up")])
    ih = werk.input_hash_of([hashlib.sha256(src).digest()], params)
    bad += check("py WRITING-IMAGE thumbnail input_hash",
                 ih == "9208123a577abd68619a99ac332ccb84c3063f57e0853fc69fae090ba376edaf", ih)
    return bad


JS_PROBE = r"""
var werk = require(process.argv[2]), fs = require("fs"), B = werk.B;
function bytes(s) { return werk.utf8Encode(s); }
var out = {};
out.sha = werk.sha256Hex(bytes("abc"));
var v = {n: 1, name: "Größe", note: "a→b", tab: "x\ty"};
out.canon = werk.sha256Hex(werk.jsonCanonical(v));
var sk = werk.fromHex(process.argv[3]);
out.pk = werk.toHex(werk.ed25519PublicKey(sk));
out.sig = werk.toHex(werk.ed25519Sign(sk, B.empty()));
var bd = werk.defaultBundle();
var man = bd.bytes("spec/examples/MANIFEST.example.json"), sg = bd.bytes("spec/examples/SIGNATURE.example.json");
out.chain = werk.verifyChain(sg, werk.sha256Hex(man)).problems;
var lines = fs.readFileSync(process.argv[4], "utf8").trim().split("\n"), bad = [], i;
for (i = 0; i < lines.length; i++) {
  var p = lines[i].split(" "), buf = Buffer.from(p[0], "hex"), x = buf.readDoubleBE(0);
  var got = werk.pyFloat(x);
  if (got !== p[1]) { bad.push(p[0] + " " + p[1] + " got " + got); }
}
out.floats = lines.length; out.float_bad = bad.slice(0, 5); out.float_bad_n = bad.length;
process.stdout.write(JSON.stringify(out));
"""


def js_checks(build):
    rnd = random.Random(20261107)
    lines = []
    for i in range(20000):
        k = i % 4
        if k == 0:
            x = rnd.uniform(-1, 1) * 10 ** rnd.randint(-30, 30)
        elif k == 1:
            x = struct.unpack(">d", struct.pack(">Q", rnd.getrandbits(64)))[0]
            if x != x or x in (float("inf"), float("-inf")):
                x = 1.5
        elif k == 2:
            x = round(rnd.uniform(-1000, 1000), rnd.randint(0, 6))
        else:
            x = float(rnd.randint(-10 ** 17, 10 ** 17)) / 10 ** rnd.randint(0, 20)
        lines.append("%s %s" % (struct.pack(">d", x).hex(), repr(x)))
    for x in (0.0, -0.0, 1.0, 1e16, 1e-5, 1e-4, 1e15, 0.1, 5e-324, 1.7976931348623157e308, 123456789012345.6):
        lines.append("%s %s" % (struct.pack(">d", x).hex(), repr(x)))
    fl = os.path.join(LIBS, "_scratch", "floats.txt")
    os.makedirs(os.path.dirname(fl), exist_ok=True)
    with open(fl, "w", newline="") as fh:
        fh.write("\n".join(lines) + "\n")
    probe = os.path.join(LIBS, "_scratch", "probe.js")
    with open(probe, "w", encoding="utf-8") as fh:
        fh.write(JS_PROBE)
    path = os.path.join(LIBS, "js", "dist", build)
    o = subprocess.check_output(["node", probe, path, RFC_SK, fl])
    r = json.loads(o)
    bad = 0
    t = build
    bad += check("%s sha256('abc')" % t, r["sha"] == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
    bad += check("%s canonical JSON vector" % t, r["canon"] == "13a2906649470c284a45bc33763ca934e41edd18e32e764443acfd4aba11baa6")
    bad += check("%s ed25519 RFC 8032 test 1 public key" % t, r["pk"] == RFC_PK)
    bad += check("%s ed25519 RFC 8032 test 1 signature" % t, r["sig"] == RFC_SIG)
    bad += check("%s spec/examples signature verifies" % t, r["chain"] == [])
    bad += check("%s float spelling == Python repr" % t, r["float_bad_n"] == 0,
                 "%d doubles, %d differ %s" % (r["floats"], r["float_bad_n"], r["float_bad"]))
    return bad


def main():
    bad = py_checks()
    for b in ("werk.js", "werk.jsx"):
        bad += js_checks(b)
    print("%d failure(s)" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
