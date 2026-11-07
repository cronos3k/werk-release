"""Reading and writing .werk containers - directory form and zip form.

SPEC section 1: "A werk 3D entity is a directory tree; the interchange form
is that tree zipped (store or deflate). Directory and zip layouts are
identical. Both are the format." So the store reads either and can write
either, and neither is privileged.

Nothing in this module decodes text. Paths are the manifest's own POSIX
strings; bytes are bytes.
"""

from __future__ import annotations

import os
import posixpath
import zipfile
from typing import BinaryIO, Iterable

from .errors import PackageError
from .manifest import MANIFEST_NAME, SIGNATURE_NAME, check_path

# Deterministic zip stamp. A werk's timestamps live in the manifest
# (versions carry `created`); the container's own mtimes carry no
# information and would only make two identical packages differ.
FIXED_STAMP = (1980, 1, 1, 0, 0, 0)


class WerkSource:
    """Read-only access to a .werk, whichever form it is in."""

    def paths(self) -> "list[str]":
        raise NotImplementedError

    def exists(self, path: str) -> bool:
        raise NotImplementedError

    def open(self, path: str) -> BinaryIO:
        raise NotImplementedError

    def read(self, path: str, max_bytes: int = 64 << 20) -> bytes:
        with self.open(path) as fh:
            data = fh.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise PackageError("%s exceeds %d bytes" % (path, max_bytes))
        return data

    def close(self) -> None:
        pass

    def __enter__(self) -> "WerkSource":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- the two files that are not in any node's files[] --------------

    def manifest_bytes(self) -> bytes:
        if not self.exists(MANIFEST_NAME):
            raise PackageError("no %s in package" % MANIFEST_NAME)
        return self.read(MANIFEST_NAME)

    def signature_bytes(self) -> "bytes | None":
        """None means the anonymous state, which is legitimate (law 7)."""
        if not self.exists(SIGNATURE_NAME):
            return None
        return self.read(SIGNATURE_NAME, max_bytes=8 << 20)


class DirSource(WerkSource):
    def __init__(self, root: str) -> None:
        self.root = os.path.abspath(root)
        if not os.path.isdir(self.root):
            raise PackageError("not a directory: %s" % root)

    def _abs(self, path: str) -> str:
        check_path(path)
        return os.path.join(self.root, *path.split("/"))

    def paths(self) -> "list[str]":
        out = []
        for dirpath, _dirnames, filenames in os.walk(self.root):
            for name in filenames:
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, self.root).replace(os.sep, "/")
                out.append(rel)
        return sorted(out)

    def exists(self, path: str) -> bool:
        return os.path.isfile(self._abs(path))

    def open(self, path: str) -> BinaryIO:
        try:
            return open(self._abs(path), "rb")
        except FileNotFoundError:
            raise PackageError("%s not present in package" % path)


class ZipSource(WerkSource):
    def __init__(self, path: str) -> None:
        try:
            self.zf = zipfile.ZipFile(path, "r")
        except Exception as exc:
            raise PackageError("not a readable zip: %s (%s)" % (path, exc))
        self._names = [i.filename for i in self.zf.infolist() if not i.is_dir()]
        self._set = set(self._names)

    def paths(self) -> "list[str]":
        return sorted(self._names)

    def entry_order(self) -> "list[str]":
        """Physical entry order as actually written - law 9's preview-first."""
        return list(self._names)

    def exists(self, path: str) -> bool:
        return path in self._set

    def open(self, path: str) -> BinaryIO:
        if path not in self._set:
            raise PackageError("%s not present in package" % path)
        return self.zf.open(path, "r")

    def close(self) -> None:
        self.zf.close()


def open_werk(path: str) -> WerkSource:
    """Open a .werk directory or zip, whichever *path* is."""
    if os.path.isdir(path):
        return DirSource(path)
    if os.path.isfile(path):
        return ZipSource(path)
    raise PackageError("no such package: %s" % path)


# ---------------------------------------------------------------------
# Preview-first ordering (law 9)
# ---------------------------------------------------------------------


def order_entries(all_paths: "Iterable[str]", entry_order: "Iterable[str]") -> "list[str]":
    """Order package paths preview-first.

    ``entry_order`` comes from the manifest's container block. Its schema
    types it as an array of strings without saying whether an item is a full
    path or a directory prefix, and the SPEC's own example mixes both
    ("MANIFEST.json", "semantics/"). So each item is matched as:

      1. an exact path, else
      2. a directory prefix (item ending in '/', or item + '/'),

    with prefix groups internally sorted for determinism. Everything not
    named by any item follows, sorted. Every path appears exactly once.

    A reader MUST NOT depend on this order for correctness (the schema says
    so); it exists so a store can fetch a prefix and show a real listing.
    """
    remaining = sorted(set(all_paths))
    placed: "list[str]" = []
    taken: "set[str]" = set()
    for item in entry_order:
        if item in remaining and item not in taken:
            placed.append(item)
            taken.add(item)
            continue
        prefix = item if item.endswith("/") else item + "/"
        group = [p for p in remaining if p.startswith(prefix) and p not in taken]
        for p in group:
            placed.append(p)
            taken.add(p)
    placed.extend(p for p in remaining if p not in taken)
    return placed


def write_zip(
    dest: str,
    ordered_paths: "list[str]",
    opener,
    compression: str = "store",
) -> int:
    """Write a .werk zip, entries in the given physical order.

    *opener* is a callable ``path -> binary stream`` (the caller decides
    whether that stream comes from the object store or from disk); the
    stream is copied through in 1 MiB chunks so a 43 MB GLB never lands in
    RAM. Returns the total byte size of the written archive.

    Store mode is the default per SPEC: a zero-dependency zip reader is
    about a hundred lines in any language WITHOUT an inflate implementation,
    and werk payloads (PNG, GLB, WAV) are already internally compressed.
    """
    method = zipfile.ZIP_STORED if compression == "store" else zipfile.ZIP_DEFLATED
    tmp = dest + ".werktmp"
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    try:
        with zipfile.ZipFile(tmp, "w", compression=method, allowZip64=True) as zf:
            for path in ordered_paths:
                info = zipfile.ZipInfo(filename=path, date_time=FIXED_STAMP)
                info.compress_type = method
                info.external_attr = 0o644 << 16
                info.create_system = 3  # unix, so the archive is stamp-identical
                with opener(path) as src, zf.open(info, "w") as out:
                    while True:
                        chunk = src.read(1 << 20)
                        if not chunk:
                            break
                        out.write(chunk)
        os.replace(tmp, dest)
        return os.path.getsize(dest)
    except BaseException:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise


def preview_prefix_bytes(zip_path: str, through: "Iterable[str]") -> int:
    """Bytes of *zip_path* that contain every entry in *through*.

    Measured from the archive's own local headers, not computed from
    declared sizes - the manifest's preview_prefix_bytes is a hint a reader
    must verify, and this is the verification.
    """
    import struct

    want = set(through)
    end = 0
    with zipfile.ZipFile(zip_path, "r") as zf:
        infos = [i for i in zf.infolist() if i.filename in want]
    with open(zip_path, "rb") as fh:
        for info in infos:
            fh.seek(info.header_offset)
            local = fh.read(30)
            if len(local) < 30 or local[:4] != b"PK\x03\x04":
                raise PackageError(
                    "no local file header for %s at %d" % (info.filename, info.header_offset)
                )
            name_len, extra_len = struct.unpack("<HH", local[26:30])
            data_start = info.header_offset + 30 + name_len + extra_len
            end = max(end, data_start + info.compress_size)
    return end


def strip_suffix(path: str) -> str:
    """Drop a trailing '@N' version suffix from the last path component."""
    head, tail = posixpath.split(path)
    if "@" in tail:
        tail = tail.rsplit("@", 1)[0]
    return posixpath.join(head, tail) if head else tail
