"""Sync: node-version-granular have/want, transferring only what is missing."""

import os

import pytest

from werkstore import WerkStore, ingest, materialize
from werkstore.errors import HashMismatch
from werkstore.sync import missing_refs, plan, pull, push, sync_all


@pytest.fixture
def remote(tmp_path):
    return WerkStore(str(tmp_path / "remote"))


def test_first_push_moves_everything_then_nothing(store, remote, werk_v1):
    src, h1 = werk_v1
    ingest(store, src)

    p = plan(store, remote, h1)
    assert p.have_objects == 0
    assert p.want_bytes > 0
    assert len(p.want()) == len(set(p.want())), "the plan must not ask for a blob twice"

    first = push(store, remote, h1)
    assert first.objects_copied == len(p.want())
    assert first.bytes_copied > 0
    assert first.ref_written

    second = push(store, remote, h1)
    assert second.objects_copied == 0
    assert second.bytes_copied == 0


def test_second_package_moves_only_the_new_node_versions(store, remote, werk_v1, werk_v2):
    src1, h1 = werk_v1
    src2, h2 = werk_v2
    ingest(store, src1)
    ingest(store, src2)
    push(store, remote, h1)

    p = plan(store, remote, h2)
    needing = [n for n in p.versions if n.needed]
    ids = {(n.node_id, n.v) for n in needing}
    assert ids == {("tex-base-color", 2), ("geom-lod1", 1)}, (
        "only the node versions that actually changed should need bytes"
    )
    assert all(n.note for n in needing), "the plan carries the work note, so a human knows why"
    assert p.have_objects > len(p.want())

    result = push(store, remote, h2)
    assert result.objects_copied == len(p.want())
    assert result.bytes_skipped > result.bytes_copied


def test_the_far_side_can_materialize_byte_exact(store, remote, werk_v1, werk_v2, tmp_path):
    """The real test of a sync: the receiver can rebuild the truth."""
    src1, h1 = werk_v1
    src2, h2 = werk_v2
    ingest(store, src1)
    ingest(store, src2)
    sync_all(store, remote)

    for name, digest, src in (("r1", h1, src1), ("r2", h2, src2)):
        out = str(tmp_path / name)
        report = materialize(remote, digest, out, form="directory")
        assert report.ok
        assert report.signature.state == "signed-and-valid"
        for dirpath, _dirs, names in os.walk(src):
            for fname in names:
                rel = os.path.relpath(os.path.join(dirpath, fname), src)
                with open(os.path.join(src, rel), "rb") as a, open(
                    os.path.join(out, rel), "rb"
                ) as b:
                    assert a.read() == b.read()


def test_sync_is_resumable_by_construction(store, remote, werk_v1, tmp_path):
    """Interrupt a transfer; the rerun moves exactly the remainder."""
    src, h1 = werk_v1
    ingest(store, src)
    wanted = plan(store, remote, h1).want()

    # Simulate an interruption after the first two objects landed.
    for digest in wanted[:2]:
        with store.objects.open(digest) as fh:
            remote.objects.put_stream(fh, expect=digest)

    p = plan(store, remote, h1)
    assert len(p.want()) == len(wanted) - 2
    result = push(store, remote, h1)
    assert result.objects_copied == len(wanted) - 2
    assert all(remote.objects.has(d) for d in wanted)


def test_receiver_verifies_rather_than_trusting_the_sender(store, remote, werk_v1):
    """A transport that flips a byte is caught by the receiver."""
    src, h1 = werk_v1
    ingest(store, src)
    digest = plan(store, remote, h1).want()[0]

    import io

    class Corrupting(io.RawIOBase):
        def __init__(self, inner):
            self.inner = inner

        def readable(self):
            return True

        def read(self, size=-1):
            chunk = self.inner.read(size)
            if chunk:
                return bytes([chunk[0] ^ 0xFF]) + chunk[1:]
            return chunk

    with store.objects.open(digest) as fh:
        with pytest.raises(HashMismatch):
            remote.objects.put_stream(Corrupting(fh), expect=digest, source="sync")
    assert not remote.objects.has(digest)


def test_pull_is_push_with_the_ends_swapped(store, remote, werk_v1):
    src, h1 = werk_v1
    ingest(remote, src)
    assert missing_refs(remote, store) == [h1]
    pull(store, remote, h1)
    assert store.refs.get(h1) is not None
    assert missing_refs(remote, store) == []
