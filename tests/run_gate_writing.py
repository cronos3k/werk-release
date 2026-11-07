#!/usr/bin/env python3
"""run_gate_writing.py -- GATE WRITING: the two "writing a minimal valid
package" walkthroughs are true.

    python tests/run_gate_writing.py

Ruling 3 of 2026-10-13 (docs/RULINGS-2026-10-13.md; SPEC.md section 14).
spec/WRITING-3D-ENTITY.md and spec/WRITING-IMAGE.md are NORMATIVE, and each
has an executable half in spec/examples/ that uses the Python standard library
and nothing else. A walkthrough that is not run is a walkthrough that drifts,
so for each of the two this gate holds that

  * the script runs from a package alone (the donor is a pinned fixture: the
    script takes `spec/` and `loaders/` out of it and authors the rest);
  * what it writes is read by all four reference readers with exit status 0
    and no report entry of severity error -- in the zip form and in the
    directory form;
  * running it twice writes the same bytes;
  * the package it wrote is itself a sufficient donor: written again FROM ITS
    OWN OUTPUT, the script produces the same bytes (law 1, literally);
  * every SHA-256 the document quotes is printed by the script, and is the
    hash of the file the package actually carries.
"""

import os
import re
import shutil
import sys
import zipfile
import hashlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate_common as G                                        # noqa: E402
from fixture_pin import pin                                    # noqa: E402

WORK = os.path.join(G.ROOT, "core", "target", "gate-writing")
CASES = [
    ("3d-entity/1", "WRITING-3D-ENTITY.md", "write_minimal_3d_entity.py", "crate-cc0-lean-v1"),
    ("image/1", "WRITING-IMAGE.md", "write_minimal_image.py", "image-cc0-v1"),
]
HEX = re.compile(r"\b[0-9a-f]{64}\b")


def main():
    gate = G.Gate("WRITING")
    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK)
    readers = G.readers(gate)
    for profile, doc, script, donor_key in CASES:
        r = pin(donor_key)
        gate.record("fixture pinned: %s" % donor_key, "PASS" if r.ok else "FAIL", r.detail)
        if not r.ok:
            continue
        tag = profile.split("/")[0]
        exe = [sys.executable, "-I", os.path.join(G.ROOT, "spec", "examples", script)]
        a = os.path.join(WORK, tag + "-a.werk")
        b = os.path.join(WORK, tag + "-b.werk")
        c = os.path.join(WORK, tag + "-from-own-output.werk")
        d = os.path.join(WORK, tag + "-directory")
        rc, out = G.run(exe + [r.path, a])
        if not gate.check("%s: the script runs from a package alone" % profile,
                          rc == 0 and os.path.isfile(a),
                          "%s, donor %s, %d bytes written"
                          % (script, donor_key, os.path.getsize(a) if os.path.isfile(a) else 0),
                          out.strip()[-300:]):
            continue
        G.run(exe + [r.path, b])
        G.run(exe + [a, c])
        rc_d, _ = G.run(exe + [r.path, d, "--dir"])
        sa = G.sha256_file(a)
        gate.check("%s: twice the same bytes" % profile, sa == G.sha256_file(b),
                   "sha256 %s both times" % sa[:16])
        gate.check("%s: its own output is a sufficient donor" % profile,
                   os.path.isfile(c) and sa == G.sha256_file(c),
                   "written again from the package it wrote: the same %d bytes"
                   % os.path.getsize(a))
        for form, path in (("zip", a), ("directory", d)):
            for reader in readers:
                rc, vout = G.verify(reader, path)
                errors = sorted(c2 for s, c2 in G.codes(vout) if s == "error")
                gate.check("%s %s form: %s reads it" % (profile, form, reader[0]),
                           rc == 0 and not errors, "exit 0, no error",
                           "exit %d, errors %s: %s"
                           % (rc, errors, vout.strip().splitlines()[-1][:140]
                              if vout.strip() else ""))
        text = open(os.path.join(G.ROOT, "spec", doc), encoding="utf-8").read()
        quoted = sorted(set(HEX.findall(text)))
        with zipfile.ZipFile(a) as z:
            carried = {hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()}
            manifest = z.read("MANIFEST.json").decode("utf-8")
        missing = [h for h in quoted if h not in out]
        unbacked = [h for h in quoted if h not in carried and h not in manifest]
        gate.check("%s: every hash the document quotes is real" % profile,
                   bool(quoted) and not missing and not unbacked,
                   "%d hashes quoted in %s: each printed by the script, and each the "
                   "hash of a carried file or a value in the manifest" % (len(quoted), doc),
                   "not printed: %s; in neither a file nor the manifest: %s"
                   % ([h[:12] for h in missing], [h[:12] for h in unbacked]))
    return gate.finish()


if __name__ == "__main__":
    sys.exit(main())
