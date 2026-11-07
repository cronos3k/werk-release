#!/usr/bin/env python3
"""Copy `spec/` and `loaders/werk_read.py` into the Blender add-on, verbatim.

    python tools/blender/vendor_spec.py [--check]

Why the add-on carries a copy at all, since duplication is normally the bug:

A conformant werk manifest's `schemas` map points at JSON Schema paths **inside
the package** (SPEC section 2), and werk-core reports
`payload-schema-invalid` — "the manifest points at schema X, which is not in
the package" — for every JSON payload whose schema is absent. So a writer
cannot emit a fully self-validating werk without shipping the schemas it
references. A Blender add-on installed from a zip has no path back to this
repository, so it must carry them.

The duplication is therefore structural, not lazy, and the only defence is to
make drift a MEASURED failure rather than a discovery: `--check` compares every
vendored byte against the original and the Stage 11 gate runs it. Same argument
werk-core makes for `include_str!`-ing the schemas instead of copying them —
a second authority that is allowed to differ is worse than no second copy.

Filed as a spec finding in HANDOVER (S-29): every conformant writer in every
language inherits this copy, and the format has nothing to say about how it is
kept fresh.
"""

import argparse
import hashlib
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
ADDON = os.path.join(ROOT, "adapters", "blender", "werk_blender")

#: (source path relative to the repo root, destination relative to the add-on)
TREES = [("spec", "spec")]
FILES = [(os.path.join("loaders", "werk_read.py"),
          os.path.join("vendor", "werk_read.py"))]

SKIP_DIRS = {"__pycache__"}
SKIP_SUFFIXES = (".pyc",)


def _walk(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            if name.endswith(SKIP_SUFFIXES):
                continue
            full = os.path.join(dirpath, name)
            yield full, os.path.relpath(full, root).replace(os.sep, "/")


def _sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def plan():
    """[(source_abs, dest_abs, package_relative_label)] for everything vendored."""
    out = []
    for src_rel, dst_rel in TREES:
        src_root = os.path.join(ROOT, src_rel)
        for full, rel in _walk(src_root):
            out.append((full, os.path.join(ADDON, dst_rel, *rel.split("/")),
                        "%s/%s" % (dst_rel, rel)))
    for src_rel, dst_rel in FILES:
        out.append((os.path.join(ROOT, src_rel), os.path.join(ADDON, dst_rel),
                    dst_rel.replace(os.sep, "/")))
    return out


def check():
    """Returns (ok_count, [problem strings]). Extra files count as problems:
    a stale schema left behind after a rename would otherwise ship forever."""
    problems = []
    ok = 0
    expected = set()
    for src, dst, label in plan():
        expected.add(os.path.normcase(os.path.abspath(dst)))
        if not os.path.isfile(dst):
            problems.append("MISSING  %s" % label)
            continue
        if _sha(src) != _sha(dst):
            problems.append("DIFFERS  %s" % label)
            continue
        ok += 1
    vendored_root = os.path.join(ADDON, "spec")
    if os.path.isdir(vendored_root):
        for full, rel in _walk(vendored_root):
            if os.path.normcase(os.path.abspath(full)) not in expected:
                problems.append("EXTRA    spec/%s" % rel)
    return ok, problems


def vendor():
    n = 0
    for src, dst, _label in plan():
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
        n += 1
    # Remove anything the source tree no longer has.
    expected = {os.path.normcase(os.path.abspath(d)) for _s, d, _l in plan()}
    vendored_root = os.path.join(ADDON, "spec")
    if os.path.isdir(vendored_root):
        for full, rel in list(_walk(vendored_root)):
            if os.path.normcase(os.path.abspath(full)) not in expected:
                os.remove(full)
                print("removed stale %s" % rel)
    return n


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="verify the vendored copy is byte-identical; exit 1 if not")
    args = ap.parse_args(argv)

    if args.check:
        ok, problems = check()
        for p in problems:
            print(p)
        total = ok + len(problems)
        print("vendored spec check: %d/%d byte-identical" % (ok, total))
        return 1 if problems else 0

    n = vendor()
    ok, problems = check()
    print("vendored %d file(s) into %s" % (n, os.path.relpath(ADDON, ROOT)))
    print("verified %d/%d byte-identical" % (ok, ok + len(problems)))
    for p in problems:
        print(p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
