"""Content-addressable object store.

Descends from VLocalZ backend/vcs/content_store.py (sha256 keys, ab/cd
fanout, tmp+rename atomicity, existence dedup). Deliberately does NOT
inherit its defects:

  * no inline tiering - EVERYTHING is content-addressed, no size threshold,
    no second storage path to disagree with the first;
  * no whole-file-in-RAM - store and read are streaming, because a werk
    payload is a 43 MB GLB, not a source file;
  * bytes-clean - nothing here decodes text, ever;
  * no database - the object store's truth is the filesystem, and a store
    that cannot rehash a blob to its own name is broken (constraint 6).

Key discipline: the object name IS the manifest's per-file sha256, lowercase
hex, no prefix, no translation layer (constraint 2).
"""

from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from typing import BinaryIO, Iterator

from .chunking import Recipe, iter_chunks
from .errors import HashMismatch, MissingObject

CHUNK = 1 << 20  # 1 MiB: big enough to keep syscalls cheap, small enough
# that peak RSS is independent of payload size.

HEX = "0123456789abcdef"


def is_hash(value: object) -> bool:
    """True if *value* is a well-formed lowercase-hex sha256 digest."""
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(c in HEX for c in value)


def hash_bytes(data: bytes) -> str:
    """sha256 of *data*, lowercase hex."""
    return hashlib.sha256(data).hexdigest()


def hash_stream(src: BinaryIO) -> "tuple[str, int]":
    """Stream *src* to the end, returning (sha256_hex, byte_count)."""
    h = hashlib.sha256()
    size = 0
    while True:
        chunk = src.read(CHUNK)
        if not chunk:
            break
        h.update(chunk)
        size += len(chunk)
    return h.hexdigest(), size


def hash_file(path: str) -> "tuple[str, int]":
    """sha256 and byte length of the file at *path*, streamed."""
    with open(path, "rb") as fh:
        return hash_stream(fh)


@dataclass(frozen=True)
class PutResult:
    """Outcome of storing one object."""

    digest: str
    size: int
    deduped: bool  # True when the object was already present and no bytes were written

    @property
    def bytes_written(self) -> int:
        return 0 if self.deduped else self.size

    chunked = False
    chunks_total = 0
    chunks_new = 0


@dataclass(frozen=True)
class ChunkedPutResult:
    """Outcome of storing one object in chunked form.

    Field-compatible with PutResult where it matters (digest, size, deduped,
    bytes_written), plus the chunk-level accounting the gate reports.
    """

    digest: str
    size: int
    chunks_total: int
    chunks_new: int
    new_bytes: int
    recipe_existed: bool
    chunked = True

    @property
    def deduped(self) -> bool:
        return self.chunks_new == 0 and self.recipe_existed

    @property
    def bytes_written(self) -> int:
        return self.new_bytes


class _ChunkReader:
    """A read-only binary stream over the chunks of one recipe, in order.

    Presents the WHOLE object: read() returns the reassembled bytes exactly
    as they were ingested. Callers (copy_to, the zip writer) rehash what
    they read, so a wrong chunk cannot slip through as the whole.
    """

    def __init__(self, store: "ObjectStore", recipe: Recipe) -> None:
        self._store = store
        self._recipe = recipe
        self._index = 0
        self._current: "BinaryIO | None" = None
        self.closed = False

    def read(self, n: int = -1) -> bytes:
        if self.closed:
            raise ValueError("read on a closed chunk reader")
        if n is None or n < 0:
            parts = []
            while True:
                piece = self.read(CHUNK)
                if not piece:
                    return b"".join(parts)
                parts.append(piece)
        while True:
            if self._current is None:
                if self._index >= len(self._recipe.chunks):
                    return b""
                digest, _size = self._recipe.chunks[self._index]
                self._current = self._store.open_whole(digest)
                self._index += 1
            piece = self._current.read(n)
            if piece:
                return piece
            self._current.close()
            self._current = None

    def close(self) -> None:
        if self._current is not None:
            self._current.close()
            self._current = None
        self.closed = True

    def __enter__(self) -> "_ChunkReader":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class ObjectStore:
    """Streaming content-addressed blob store rooted at *objects_dir*.

    Layout: ``<objects_dir>/ab/cd/<64-hex>``. Two levels of fanout keep
    directory sizes sane on every filesystem worth supporting; the full
    digest is still the filename so a blob is self-identifying even if it is
    copied out of the tree by hand.
    """

    def __init__(
        self, objects_dir: str, tmp_dir: str, chunks_dir: "str | None" = None
    ) -> None:
        self.objects_dir = os.path.abspath(objects_dir)
        self.tmp_dir = os.path.abspath(tmp_dir)
        self.chunks_dir = os.path.abspath(chunks_dir) if chunks_dir else None
        os.makedirs(self.objects_dir, exist_ok=True)
        os.makedirs(self.tmp_dir, exist_ok=True)
        # chunks_dir is created lazily on first recipe write, so a store
        # that never chunks (and every store from before CDC) has no
        # chunks/ directory at all - migration is the absence of change.

    # -- addressing ---------------------------------------------------

    def path_for(self, digest: str) -> str:
        """Filesystem path an object with *digest* would occupy."""
        if not is_hash(digest):
            raise ValueError("not a lowercase-hex sha256: %r" % (digest,))
        return os.path.join(self.objects_dir, digest[:2], digest[2:4], digest)

    def recipe_path(self, digest: str) -> str:
        """Filesystem path the chunk recipe for whole-hash *digest* would occupy."""
        if self.chunks_dir is None:
            raise ValueError("this ObjectStore has no chunks directory")
        if not is_hash(digest):
            raise ValueError("not a lowercase-hex sha256: %r" % (digest,))
        return os.path.join(self.chunks_dir, digest[:2], digest[2:4], digest + ".json")

    def has_whole(self, digest: str) -> bool:
        """True only if the object is present as a single whole blob."""
        return os.path.exists(self.path_for(digest))

    def chunk_recipe(self, digest: str) -> "Recipe | None":
        """The recipe for *digest* if it is stored chunked and readable.

        An unreadable or mis-filed recipe answers None - the store then
        simply cannot produce the object that way, which surfaces as a loud
        MissingObject at use and as a named report in `werkstore scrub`
        (which re-reads recipes directly and quarantines the bad ones).
        """
        if self.chunks_dir is None:
            return None
        path = self.recipe_path(digest)
        try:
            with open(path, "rb") as fh:
                raw = fh.read()
        except OSError:
            return None
        try:
            recipe = Recipe.from_json(raw)
            recipe.check()
        except Exception:
            return None
        if recipe.whole_sha256 != digest:
            return None
        return recipe

    def has(self, digest: str) -> bool:
        """True if the store can produce this object - whole or chunked.

        The chunked answer is only yes when EVERY chunk is present: a recipe
        whose chunks are missing is a promise the store cannot keep, and
        has() must never say yes to that.
        """
        if self.has_whole(digest):
            return True
        recipe = self.chunk_recipe(digest)
        if recipe is None:
            return False
        return all(self.has_whole(h) for h, _s in recipe.chunks)

    def size(self, digest: str) -> int:
        try:
            return os.path.getsize(self.path_for(digest))
        except OSError:
            pass
        recipe = self.chunk_recipe(digest)
        if recipe is not None:
            return recipe.whole_size
        raise MissingObject(digest)

    # -- writing ------------------------------------------------------

    def _tmp(self, tag: str) -> str:
        return os.path.join(
            self.tmp_dir, "put-%d-%s.tmp" % (os.getpid(), tag)
        )

    def put_stream(
        self, src: BinaryIO, expect: "str | None" = None, source: str = "<stream>"
    ) -> PutResult:
        """Store everything readable from *src*.

        Hashes while writing - the bytes are never held whole in memory and
        never read twice. If *expect* is given and the content hashes to
        anything else, the temp file is destroyed and HashMismatch is raised
        with the exact report; nothing enters the store.
        """
        h = hashlib.sha256()
        size = 0
        tmp = self._tmp("%x" % (id(src) & 0xFFFFFFFF))
        try:
            with open(tmp, "wb") as out:
                while True:
                    chunk = src.read(CHUNK)
                    if not chunk:
                        break
                    h.update(chunk)
                    out.write(chunk)
                    size += len(chunk)
                out.flush()
                os.fsync(out.fileno())
            digest = h.hexdigest()
            if expect is not None and digest != expect:
                raise HashMismatch(expect, digest, size, source)
            final = self.path_for(digest)
            if os.path.exists(final):
                os.remove(tmp)
                return PutResult(digest, size, deduped=True)
            os.makedirs(os.path.dirname(final), exist_ok=True)
            os.replace(tmp, final)  # atomic within a filesystem
            return PutResult(digest, size, deduped=False)
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    def put_path(self, path: str, expect: "str | None" = None) -> PutResult:
        """Store the file at *path* by streaming it."""
        with open(path, "rb") as fh:
            return self.put_stream(fh, expect=expect, source=path)

    def put_bytes(
        self, data: bytes, expect: "str | None" = None, source: str = "<bytes>"
    ) -> PutResult:
        """Store an in-memory blob. For small structured payloads only."""
        import io

        return self.put_stream(io.BytesIO(data), expect=expect, source=source)

    # -- chunked writing ----------------------------------------------

    def put_stream_chunked(
        self, src: BinaryIO, expect: "str | None" = None, source: str = "<stream>"
    ) -> ChunkedPutResult:
        """Store *src* chunked: each CDC chunk becomes an ordinary object,
        and a recipe under the WHOLE-file hash lists them in order.

        The whole-file sha256 is computed over the same pass, and the same
        refusal applies as for put_stream: if *expect* is given and the
        content hashes to anything else, HashMismatch is raised, no recipe
        is written, and every chunk THIS call added is removed - nothing of
        a refused ingest enters the store.
        """
        if self.chunks_dir is None:
            raise ValueError("this ObjectStore has no chunks directory")
        whole = hashlib.sha256()
        size = 0
        chunks: "list[tuple[str, int]]" = []
        added: "list[str]" = []
        new_bytes = 0
        try:
            for chunk in iter_chunks(src):
                whole.update(chunk)
                size += len(chunk)
                put = self.put_bytes(chunk, source="%s [chunk %d]" % (source, len(chunks)))
                chunks.append((put.digest, put.size))
                if not put.deduped:
                    added.append(put.digest)
                    new_bytes += put.size
            digest = whole.hexdigest()
            if expect is not None and digest != expect:
                raise HashMismatch(expect, digest, size, source)
            recipe = Recipe(
                whole_sha256=digest, whole_size=size, chunks=tuple(chunks)
            )
            recipe_existed = os.path.exists(self.recipe_path(digest))
            if not recipe_existed:
                self.put_recipe(recipe)
            return ChunkedPutResult(
                digest=digest,
                size=size,
                chunks_total=len(chunks),
                chunks_new=len(added),
                new_bytes=new_bytes,
                recipe_existed=recipe_existed,
            )
        except BaseException:
            # Undo this call's additions; chunks that already existed (or
            # that another package also owns, which dedup makes identical
            # to "already existed") are left alone.
            for h in added:
                try:
                    self.remove(h)
                except OSError:
                    pass
            raise

    def put_recipe(self, recipe: Recipe) -> str:
        """Write a recipe atomically. Returns its path."""
        recipe.check()
        path = self.recipe_path(recipe.whole_sha256)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(recipe.to_json())
        os.replace(tmp, path)
        return path

    def remove_recipe(self, digest: str) -> int:
        """Delete a recipe (never its chunks - GC owns that decision)."""
        if self.chunks_dir is None:
            return 0
        path = self.recipe_path(digest)
        if not os.path.exists(path):
            return 0
        n = os.path.getsize(path)
        os.remove(path)
        self._prune_chunk_dirs(os.path.dirname(path))
        return n

    def iter_recipe_hashes(self) -> Iterator[str]:
        """Yield the whole-file hash of every recipe present."""
        if self.chunks_dir is None or not os.path.isdir(self.chunks_dir):
            return
        for d1 in sorted(os.listdir(self.chunks_dir)):
            p1 = os.path.join(self.chunks_dir, d1)
            if not os.path.isdir(p1) or len(d1) != 2:
                continue
            for d2 in sorted(os.listdir(p1)):
                p2 = os.path.join(p1, d2)
                if not os.path.isdir(p2) or len(d2) != 2:
                    continue
                for name in sorted(os.listdir(p2)):
                    if name.endswith(".json") and is_hash(name[:-5]):
                        yield name[:-5]

    def recipes_count_and_bytes(self) -> "tuple[int, int]":
        """(recipe count, recipe bytes on disk) - the chunking overhead."""
        n = 0
        total = 0
        for digest in self.iter_recipe_hashes():
            n += 1
            total += os.path.getsize(self.recipe_path(digest))
        return n, total

    def _prune_chunk_dirs(self, leaf: str) -> None:
        cur = leaf
        for _ in range(2):
            if self.chunks_dir is None or os.path.abspath(cur) == self.chunks_dir:
                return
            try:
                if not os.listdir(cur):
                    os.rmdir(cur)
                else:
                    return
            except OSError:
                return
            cur = os.path.dirname(cur)

    # -- reading ------------------------------------------------------

    def open_whole(self, digest: str) -> BinaryIO:
        """Open a whole blob; never consults recipes (chunks use this)."""
        try:
            return open(self.path_for(digest), "rb")
        except FileNotFoundError:
            raise MissingObject(digest)

    def open(self, digest: str):
        """Open an object for streaming reads. Caller closes.

        Transparent over representation: a whole blob streams from its file,
        a chunked object streams reassembled through its recipe. Either way
        the caller sees the manifest's bytes.
        """
        if self.has_whole(digest):
            return self.open_whole(digest)
        recipe = self.chunk_recipe(digest)
        if recipe is not None:
            return _ChunkReader(self, recipe)
        raise MissingObject(digest)

    def read_bytes(self, digest: str, max_bytes: int = 64 << 20) -> bytes:
        """Read a whole object into memory.

        Bounded on purpose: this is for manifests and signature chains, the
        only objects the store itself must parse. Payloads are streamed.
        """
        parts = []
        got = 0
        with self.open(digest) as fh:
            while got <= max_bytes:
                piece = fh.read(CHUNK)
                if not piece:
                    break
                parts.append(piece)
                got += len(piece)
        data = b"".join(parts)
        if len(data) > max_bytes:
            raise ValueError(
                "object %s exceeds %d bytes; stream it instead" % (digest, max_bytes)
            )
        return data

    def copy_to(self, digest: str, dest: str, verify: bool = True) -> int:
        """Stream an object out to *dest*, atomically. Returns byte count.

        With *verify* (the default) the bytes are rehashed on the way out,
        so a materialized file is proven, not assumed - the store may have
        rotted since ingest and that is exactly the case this catches.
        """
        os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
        tmp = dest + ".werktmp"
        h = hashlib.sha256()
        size = 0
        try:
            with self.open(digest) as src, open(tmp, "wb") as out:
                while True:
                    chunk = src.read(CHUNK)
                    if not chunk:
                        break
                    if verify:
                        h.update(chunk)
                    out.write(chunk)
                    size += len(chunk)
            if verify and h.hexdigest() != digest:
                raise HashMismatch(
                    digest, h.hexdigest(), size, "store object %s" % digest
                )
            os.replace(tmp, dest)
            return size
        except BaseException:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
            raise

    # -- enumeration and removal -------------------------------------

    def iter_hashes(self) -> Iterator[str]:
        """Yield every object name present, in filesystem order."""
        for d1 in sorted(os.listdir(self.objects_dir)):
            p1 = os.path.join(self.objects_dir, d1)
            if not os.path.isdir(p1) or len(d1) != 2:
                continue
            for d2 in sorted(os.listdir(p1)):
                p2 = os.path.join(p1, d2)
                if not os.path.isdir(p2) or len(d2) != 2:
                    continue
                for name in sorted(os.listdir(p2)):
                    if is_hash(name):
                        yield name

    def count_and_bytes(self) -> "tuple[int, int]":
        """(object count, total bytes on disk) - the physical footprint."""
        n = 0
        total = 0
        for digest in self.iter_hashes():
            n += 1
            total += os.path.getsize(self.path_for(digest))
        return n, total

    def remove(self, digest: str) -> int:
        """Delete an object. Returns the bytes reclaimed (0 if absent)."""
        path = self.path_for(digest)
        if not os.path.exists(path):
            return 0
        n = os.path.getsize(path)
        os.remove(path)
        self._prune_dirs(os.path.dirname(path))
        return n

    def quarantine(self, digest: str, quarantine_dir: str) -> str:
        """Move a suspect object out of the addressed tree, keeping the bytes.

        Corrupt data is evidence. Deleting it would destroy the only copy of
        what went wrong, so scrub quarantines instead.
        """
        src = self.path_for(digest)
        os.makedirs(quarantine_dir, exist_ok=True)
        dest = os.path.join(quarantine_dir, digest)
        if os.path.exists(dest):
            dest = dest + ".%d" % os.getpid()
        shutil.move(src, dest)
        self._prune_dirs(os.path.dirname(src))
        return dest

    def _prune_dirs(self, leaf: str) -> None:
        """Remove now-empty fanout directories, never the objects root."""
        cur = leaf
        for _ in range(2):
            if os.path.abspath(cur) == self.objects_dir:
                return
            try:
                if not os.listdir(cur):
                    os.rmdir(cur)
                else:
                    return
            except OSError:
                return
            cur = os.path.dirname(cur)
