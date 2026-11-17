#!/usr/bin/env python3
"""spec_sha256.py -- the reference implementation of the manifest's `spec_sha256`.

    python tools/spec_sha256.py spec/                  # over a directory tree
    python tools/spec_sha256.py package.werk           # over a package's spec/

S-29, ruled 2026-08-08. Vendoring `spec/` is structural for every werk writer
in every language -- the manifest's `schemas` map names paths INSIDE the
package, so a writer that wants its output to validate must ship the bytes --
and until this field existed nothing said WHICH revision those bytes were. Two
tools could emit mutually contradictory schemas while both claiming
`profile: "3d-entity/1"`, and a reader had no way to notice.

THE ALGORITHM, stated completely, because a hash whose input order is a
convention is not a hash:

    take every file under spec/ that the manifest declares in some node's
    files[]; sort by package-relative path, ascending, comparing UTF-8 BYTES;
    for each, append
        path UTF-8 bytes || 0x0A || that file's own sha256 as 32 RAW bytes || 0x0A
    spec_sha256 = sha256(that concatenation)

Paths are included, so moving a file changes the hash. Raw hash bytes rather
than hex, deliberately the same shape as `input_hash` (SPEC section 2), so a
writer implements one construction and uses it twice.

NOTE THE CONSEQUENCE, because it catches people: for a set of exactly ONE file
the result is NOT that file's own sha256. It is the hash of the path-plus-hash
record. That is intentional -- a one-file spec tree and a one-file payload are
different claims and must not collide.

The SAME construction computes the OPTIONAL per-node-version `spec_sha256`,
over exactly the spec files that version's payload conforms to (its entry in
`schemas`, its entry in `layouts`, or both). One function, two uses:
`spec_sha256_over()` takes whatever set you hand it.
"""

import hashlib
import os
import sys
import zipfile


def spec_sha256_over(path_to_bytes_or_hash):
    """{package-relative path: bytes | 64-char hex sha256} -> hex digest.

    Accepts either the file's bytes or its already-computed hex sha256, so a
    writer that has hashed everything once does not hash it twice.
    """
    acc = hashlib.sha256()
    for path in sorted(path_to_bytes_or_hash, key=lambda p: p.encode("utf-8")):
        v = path_to_bytes_or_hash[path]
        if isinstance(v, (bytes, bytearray)):
            digest = hashlib.sha256(bytes(v)).digest()
        else:
            s = str(v).strip().lower()
            if len(s) != 64:
                raise ValueError("%s: expected bytes or a 64-char hex sha256, "
                                 "got %r" % (path, v))
            digest = bytes.fromhex(s)
        acc.update(path.encode("utf-8"))
        acc.update(b"\n")
        acc.update(digest)
        acc.update(b"\n")
    return acc.hexdigest()


TEXT_SUFFIXES = (".md", ".json", ".txt", ".py", ".rs", ".c", ".h", ".toml")


def translated_text(files, prefixes=("spec/", "loaders/")):
    """The spec and loader TEXT files in `files` whose bytes contain a carriage
    return: paths, sorted. An empty list is the only healthy answer.

    WHY (finding F-AC-6, measured 2026-10-13). .gitattributes makes every text
    file of this repository LF, in the index and in the working tree. A working
    tree checked out BEFORE that rule existed keeps the CRLF it was given: git
    reports such a file clean, because it is clean under the rule, and its
    bytes on disk are not the repository's. A builder run from that tree embeds
    the CRLF bytes; the package it writes is internally consistent, verifies,
    and carries a `spec_sha256` no other checkout can reproduce. Three spec
    files were in that state in the working tree the shipped fixtures had been
    built from, and that -- not a defect in any builder -- is why two
    "rebuild is byte-identical" clauses failed on a fresh checkout of the same
    commit. The binary examples under spec/examples may contain 0D legitimately
    and are not text; they are not looked at.
    """
    return sorted(p for p, v in files.items()
                  if p.startswith(prefixes) and p.endswith(TEXT_SUFFIXES)
                  and isinstance(v, (bytes, bytearray)) and b"\r" in v)


def spec_sha256_of_files(files, prefix="spec/"):
    """{path: bytes|hex} for a WHOLE package -> the global spec_sha256.

    Filters to the spec/ subtree, which is what the global field is over.
    This is the WRITER's entry point (every builder calls it on the bytes it
    is about to embed), so it is also where a working tree whose text files
    were translated is refused: see `translated_text`.
    """
    bad = translated_text(files)
    if bad:
        raise SystemExit(
            "REFUSING TO BUILD: %d spec/loader text file(s) in this working tree "
            "contain carriage returns, so their bytes are not the repository's "
            "(.gitattributes: text=auto eol=lf) and the package would carry a "
            "spec_sha256 no other checkout can reproduce:\n  %s\nRe-checkout "
            "them:  git rm --cached -r -q spec loaders && git reset -q --hard HEAD "
            "-- is the blunt form; for single files, delete the file and "
            "`git checkout -- <path>`." % (len(bad), "\n  ".join(bad)))
    return spec_sha256_over({p: v for p, v in files.items()
                             if p.startswith(prefix)})


def spec_sha256_of_dir(root, prefix="spec/"):
    """A directory holding a spec/ tree (or being one) -> the digest."""
    root = os.path.abspath(root)
    base = root if os.path.basename(root) == "spec" else os.path.join(root, "spec")
    out = {}
    for dirpath, _dirs, names in os.walk(base):
        _dirs.sort()  # else the filesystem's order (ext4: hash order)
        for nm in sorted(names):
            if nm.endswith(".pyc"):
                continue
            full = os.path.join(dirpath, nm)
            rel = prefix + os.path.relpath(full, base).replace(os.sep, "/")
            with open(full, "rb") as fh:
                out[rel] = fh.read()
    if not out:
        raise SystemExit("no spec/ tree under %s" % root)
    return spec_sha256_over(out)


def spec_sha256_of_werk(path, prefix="spec/"):
    """A .werk zip -> the digest over the spec/ entries it actually carries."""
    with zipfile.ZipFile(path) as z:
        out = {n: z.read(n) for n in z.namelist() if n.startswith(prefix)}
    if not out:
        raise SystemExit("%s carries no spec/ tree" % path)
    return spec_sha256_over(out)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        argv = ["spec"]
    for target in argv:
        if os.path.isdir(target):
            print("%s  %s" % (spec_sha256_of_dir(target), target))
        elif zipfile.is_zipfile(target):
            print("%s  %s" % (spec_sha256_of_werk(target), target))
        else:
            raise SystemExit("%s is neither a directory nor a zip" % target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
