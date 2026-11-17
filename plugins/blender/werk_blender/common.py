"""Small shared pieces: scratch directories, JSON spelling, hashes, ids."""

import errno
import hashlib
import json
import os
import re
import shutil
import tempfile

#: Directory name used for the short-lived scratch space beside the package.
SCRATCH_DIRNAME = ".werk-blender-tmp"

#: Override the scratch location entirely. Set this when the package sits on a
#: read-only share or when a pipeline wants every intermediate in one place.
SCRATCH_ENV = "WERK_BLENDER_TMP"


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def jbytes(value):
    """The on-disk JSON spelling werk uses everywhere: two-space indent, one
    trailing newline, UTF-8, non-ASCII kept as itself. Matching
    `fixtures/build_golden.py` exactly is what lets a package written here and
    a package written there be compared byte for byte."""
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def input_hash(paths, blobs):
    """Law 5, per `manifest.schema.json`: sha256 over each input's 32 RAW digest
    bytes in the declared order, then the canonical JSON of `input_params`.

    AN ABSENT `input_params` IS THE EMPTY OBJECT and the two bytes `{}` are
    appended either way — this is S-10, the finding three gauntlet agents in
    three languages each lost the most time to. The exporter also writes
    `"input_params": {}` out explicitly, as the schema says a writer SHOULD, so
    no reader of a package we produce has to rediscover it."""
    h = hashlib.sha256()
    for p in paths:
        h.update(hashlib.sha256(blobs[p]).digest())
    h.update(b"{}")
    return h.hexdigest()


_ID_OK = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def kebab(name, fallback="item"):
    """Coerce a Blender datablock name into `conventions.id_case`: kebab-case,
    matching ^[a-z0-9]+(-[a-z0-9]+)*$, which every id pattern in the schemas
    enforces. Deterministic, so the same object exports to the same id twice."""
    s = re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    return s if _ID_OK.match(s) else fallback


def unique_id(base, taken, fallback="item"):
    """kebab() can collide (Blender's `Cube` and `cube` differ, our ids do not).
    Colliding silently would put two nodes on one id and break the manifest, so
    a numeric suffix is appended and the caller can see it happened."""
    candidate = kebab(base, fallback)
    if candidate not in taken:
        taken.add(candidate)
        return candidate
    n = 2
    while "%s-%d" % (candidate, n) in taken:
        n += 1
    out = "%s-%d" % (candidate, n)
    taken.add(out)
    return out


def is_valid_id(value):
    return isinstance(value, str) and bool(_ID_OK.match(value))


class Scratch(object):
    """A short-lived directory for the GLB/PNG files Blender's own importers
    and exporters insist on reading and writing through the filesystem.

    Placed BESIDE the package by default, never in a user profile directory,
    and removed on exit. Falls back to the system temp directory only when the
    package's own directory cannot be written to (a read-only share, a
    network mount), and records which one it used so the caller can say so.
    """

    def __init__(self, near=None, keep=False):
        self.keep = keep
        self.path = None
        self.fell_back = False
        override = os.environ.get(SCRATCH_ENV)
        candidates = []
        if override:
            candidates.append(os.path.abspath(override))
        if near:
            base = near if os.path.isdir(near) else os.path.dirname(os.path.abspath(near))
            if base:
                candidates.append(os.path.join(base, SCRATCH_DIRNAME))
        self._candidates = candidates

    def __enter__(self):
        for i, cand in enumerate(self._candidates):
            try:
                os.makedirs(cand, exist_ok=True)
                probe = os.path.join(cand, ".probe")
                with open(probe, "wb") as fh:
                    fh.write(b"1")
                os.remove(probe)
                self.path = tempfile.mkdtemp(prefix="werk-", dir=cand)
                self._root = cand
                return self
            except OSError as e:
                if e.errno not in (errno.EACCES, errno.EROFS, errno.EPERM,
                                   errno.ENOENT, errno.EINVAL):
                    raise
        self.path = tempfile.mkdtemp(prefix="werk-blender-")
        self._root = None
        self.fell_back = True
        return self

    def file(self, name):
        return os.path.join(self.path, name)

    def __exit__(self, *_exc):
        if self.keep or not self.path:
            return False
        shutil.rmtree(self.path, ignore_errors=True)
        # Remove the shared parent too, but only while it is empty: a
        # concurrent export in the same directory must not lose its scratch.
        if self._root:
            try:
                os.rmdir(self._root)
            except OSError:
                pass
        return False
