#!/usr/bin/env python3
"""Fetch the files this repository keeps out of git, and verify them.

The list is RELEASE-ASSETS.md at the repository root: one table row per file,
with its repository-relative path, its size in bytes and its sha256. Nothing is
trusted until its sha256 matches the row. Stdlib only. Run from anywhere:

    python tools/fetch_fixtures.py --base-url URL   # download what is missing
    python tools/fetch_fixtures.py --from-dir DIR   # copy from a local mirror
    python tools/fetch_fixtures.py --check          # verify only, fetch nothing
    python tools/fetch_fixtures.py --only fixtures/gsplat-v1.werk ...

The base URL can also come from the environment variable
WERK_RELEASE_BASE_URL. A file is fetched from <base-url>/<path>; a local
mirror holds the same <path> layout under DIR. Files already present with the
right hash are left alone (use --force to replace them). Archives (rows whose
path ends in .tar.gz) are verified but not unpacked.

Exit 0: every requested file is present and matches. Exit 1: something is
missing or does not match (the reason is printed per file).
"""
import argparse
import hashlib
import os
import re
import shutil
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIST = os.path.join(ROOT, "RELEASE-ASSETS.md")
PLACEHOLDER = "{RELEASE_BASE_URL}"

# | `path` | bytes | `sha256` | where |
ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*([0-9 ]+)\s*\|\s*`([0-9a-f]{64})`\s*\|", re.M)


def entries():
    text = open(LIST, encoding="utf-8").read()
    for path, size, sha in ROW.findall(text):
        yield path.strip(), int(size.replace(" ", "")), sha


def sha256_of(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ok(p, size, sha):
    return os.path.isfile(p) and os.path.getsize(p) == size and sha256_of(p) == sha


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base-url", default=os.environ.get("WERK_RELEASE_BASE_URL", ""))
    ap.add_argument("--from-dir", default="")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", nargs="*", default=None)
    a = ap.parse_args(argv)
    if a.base_url and PLACEHOLDER in a.base_url:
        a.base_url = ""
    bad = 0
    for rel, size, sha in entries():
        if a.only is not None and rel not in a.only:
            continue
        dst = os.path.join(ROOT, *rel.split("/"))
        if ok(dst, size, sha) and not a.force:
            print("ok        %s" % rel)
            continue
        if a.check:
            print("%s %s" % ("MISMATCH " if os.path.exists(dst) else "MISSING  ", rel))
            bad += 1
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        part = dst + ".part"
        try:
            if a.from_dir:
                src = os.path.join(a.from_dir, *rel.split("/"))
                print("copy      %s  <- %s" % (rel, src))
                shutil.copyfile(src, part)
            elif a.base_url:
                url = a.base_url.rstrip("/") + "/" + rel
                print("fetch     %s  <- %s" % (rel, url))
                urllib.request.urlretrieve(url, part)
            else:
                print("MISSING   %s  (no --base-url / WERK_RELEASE_BASE_URL and no "
                      "--from-dir given)" % rel)
                bad += 1
                continue
        except Exception as e:                                     # noqa: BLE001
            print("  ERROR   %s: %s" % (rel, e))
            if os.path.exists(part):
                os.remove(part)
            bad += 1
            continue
        if not ok(part, size, sha):
            got = sha256_of(part)
            print("  HASH MISMATCH %s: expected %s (%d B), got %s (%d B)"
                  % (rel, sha, size, got, os.path.getsize(part)))
            os.remove(part)
            bad += 1
            continue
        os.replace(part, dst)
        print("  verified %s" % rel)
    if bad:
        print("\n%d file(s) missing or invalid." % bad)
        return 1
    print("\nAll requested files present and verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
