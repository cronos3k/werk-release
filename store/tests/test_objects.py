"""The CAS itself: streaming, dedup, atomicity, and refusal."""

import hashlib
import io
import os

import pytest

from werkstore.errors import HashMismatch, MissingObject
from werkstore.objects import ObjectStore, hash_bytes, is_hash


@pytest.fixture
def objects(tmp_path):
    return ObjectStore(str(tmp_path / "objects"), str(tmp_path / "tmp"))


def test_key_is_the_manifest_hash_with_no_translation(objects):
    """Constraint 2: the manifest's per-file sha256 IS the store key."""
    data = b"the bytes a manifest would declare"
    digest = hashlib.sha256(data).hexdigest()
    put = objects.put_bytes(data)
    assert put.digest == digest
    assert os.path.basename(objects.path_for(digest)) == digest
    # two-level fanout, full digest still the filename
    rel = os.path.relpath(objects.path_for(digest), objects.objects_dir).replace(os.sep, "/")
    assert rel == "%s/%s/%s" % (digest[:2], digest[2:4], digest)


def test_dedup_writes_nothing_the_second_time(objects):
    data = os.urandom(4096)
    first = objects.put_bytes(data)
    second = objects.put_bytes(data)
    assert first.deduped is False and first.bytes_written == len(data)
    assert second.deduped is True and second.bytes_written == 0
    count, total = objects.count_and_bytes()
    assert count == 1 and total == len(data)


def test_mismatch_refuses_and_stores_nothing(objects):
    data = b"honest bytes"
    lie = "f" * 64
    with pytest.raises(HashMismatch) as exc:
        objects.put_bytes(data, expect=lie, source="textures/base-color.png")
    assert exc.value.expected == lie
    assert exc.value.actual == hash_bytes(data)
    assert exc.value.size == len(data)
    assert "textures/base-color.png" in str(exc.value)
    # Nothing entered the store under either name.
    assert not objects.has(lie)
    assert not objects.has(hash_bytes(data))
    assert objects.count_and_bytes()[0] == 0
    # And no temp file was left behind.
    assert os.listdir(objects.tmp_dir) == []


def test_streaming_never_holds_the_payload_whole(objects, monkeypatch):
    """put_stream must read in chunks, not slurp.

    Enforced by a reader that refuses an unbounded read - the way a
    whole-file implementation would call it.
    """

    class ChunkOnly(io.RawIOBase):
        def __init__(self, total):
            self.remaining = total

        def readable(self):
            return True

        def read(self, size=-1):
            if size is None or size < 0:
                raise AssertionError("put_stream asked for the whole file at once")
            n = min(size, self.remaining)
            self.remaining -= n
            return b"\x5a" * n

    total = 5 << 20
    put = objects.put_stream(ChunkOnly(total), source="<big>")
    assert put.size == total
    assert put.digest == hashlib.sha256(b"\x5a" * total).hexdigest()


def test_copy_to_verifies_on_the_way_out(objects, tmp_path):
    data = b"payload that must come back identical"
    digest = objects.put_bytes(data).digest
    dest = str(tmp_path / "out" / "file.bin")
    n = objects.copy_to(digest, dest)
    assert n == len(data)
    with open(dest, "rb") as fh:
        assert fh.read() == data

    # Rot the object in place; copy_to must catch it rather than hand over
    # bytes that no longer match their own name.
    with open(objects.path_for(digest), "r+b") as fh:
        fh.seek(0)
        fh.write(b"X")
    with pytest.raises(HashMismatch):
        objects.copy_to(digest, str(tmp_path / "out" / "file2.bin"))
    assert not os.path.exists(str(tmp_path / "out" / "file2.bin"))


def test_missing_object_is_named(objects):
    with pytest.raises(MissingObject):
        objects.open("0" * 64)


def test_remove_prunes_empty_fanout_dirs_but_not_the_root(objects):
    digest = objects.put_bytes(b"transient").digest
    fanout = os.path.dirname(objects.path_for(digest))
    assert os.path.isdir(fanout)
    objects.remove(digest)
    assert not os.path.exists(fanout)
    assert os.path.isdir(objects.objects_dir)


def test_is_hash_rejects_uppercase_and_short():
    assert is_hash("a" * 64)
    assert not is_hash("A" * 64)
    assert not is_hash("a" * 63)
    assert not is_hash(None)
