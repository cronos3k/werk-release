#!/usr/bin/env python3
"""Build the installable add-on zip.

    python tools/blender/build_addon_zip.py [--out PATH]

Produces `werk_blender-<version>.zip` containing a single top-level
`werk_blender/` directory, which is the shape Blender's
`Preferences > Add-ons > Install...` expects.

The vendored copies are verified byte-identical first and the build REFUSES
rather than shipping a stale schema: a zip is the form most likely to end up
on someone else's machine, so it is the worst place for a copy that drifted.

Deterministic: fixed timestamps and sorted entries, so two builds of the same
tree are the same bytes.
"""

import argparse
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
ADDON = os.path.join(ROOT, "adapters", "blender", "werk_blender")

SKIP_DIRS = {"__pycache__", ".git"}
SKIP_SUFFIXES = (".pyc", ".pyo")

# 1980-01-01 00:00:00, the earliest a zip timestamp can express.
FIXED_DATE = (1980, 1, 1, 0, 0, 0)


def addon_version():
    with open(os.path.join(ADDON, "__init__.py"), encoding="utf-8") as fh:
        for line in fh:
            if line.strip().startswith('"version"'):
                nums = [int(t) for t in line.split("(")[1].split(")")[0].split(",")]
                return ".".join(str(n) for n in nums)
    return "0"


def build(out_path):
    files = []
    for dirpath, dirnames, filenames in os.walk(ADDON):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            if name.endswith(SKIP_SUFFIXES):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, os.path.dirname(ADDON)).replace(os.sep, "/")
            files.append((full, rel))
    files.sort(key=lambda p: p[1])

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        for full, rel in files:
            info = zipfile.ZipInfo(rel, date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with open(full, "rb") as fh:
                z.writestr(info, fh.read())
    return out_path, len(files)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--skip-vendor-check", action="store_true",
                    help="build even if the vendored copies have drifted "
                         "(for diagnosing that drift, never for shipping)")
    args = ap.parse_args(argv)

    if not args.skip_vendor_check:
        sys.path.insert(0, HERE)
        import vendor_spec
        ok, problems = vendor_spec.check()
        if problems:
            print("REFUSING to build: the vendored copies have drifted.")
            for p in problems:
                print("  " + p)
            print("Run `python tools/blender/vendor_spec.py` and rebuild.")
            return 1
        print("vendored copies: %d/%d byte-identical" % (ok, ok))

    out = args.out or os.path.join(ROOT, "adapters", "blender", "dist",
                                   "werk_blender-%s.zip" % addon_version())
    path, n = build(out)
    print("wrote %s" % path)
    print("  %d file(s), %d bytes" % (n, os.path.getsize(path)))
    print("Install in Blender: Edit > Preferences > Add-ons > Install... "
          "and pick this zip.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
