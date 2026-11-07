"""Content-defined chunking - the algorithm, the store integration, and the
invariant that must survive it all: materialization stays byte-exact,
proven against the manifest's whole-file hashes.

The algorithm tests assert the published vector from store/CHUNKING.md, so
this file is also the compatibility gate for any foreign implementation.
"""

import hashlib
import io
import json
import os

import pytest

from werkstore import WerkStore, collect, ingest, materialize, scrub
from werkstore.chunking import (
    ALGORITHM,
    AVG_SIZE,
    DEFAULT_THRESHOLD,
    GEAR,
    MAX_SIZE,
    MIN_SIZE,
    Recipe,
    chunk_bytes,
    iter_chunks,
)
from werkstore.errors import HashMismatch, MaterializeError
from werkstore.sync import plan as sync_plan, push


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def keystream(seed: bytes, n: int) -> bytes:
    parts = []
    total = 0
    i = 0
    while total < n:
        b = hashlib.sha256(seed + i.to_bytes(8, "big")).digest()
        parts.append(b)
        total += len(b)
        i += 1
    return b"".join(parts)[:n]


# ---------------------------------------------------------------------
# the algorithm
# ---------------------------------------------------------------------


def test_gear_table_spot_values():
    """CHUNKING.md section 3. A mistyped table would move every boundary."""
    assert GEAR[0] == 0xE845C0CAAECA9317
    assert GEAR[1] == 0xD690296A6C7CAC90
    assert GEAR[255] == 0xE2469BEE8245A8F2
    assert len(GEAR) == 256
    assert len(set(GEAR)) == 256  # SHA-256 had better not collide on 1 byte


def test_chunking_matches_the_published_vector():
    """The test vector from CHUNKING.md section 8, asserted verbatim."""
    data = keystream(b"werk-cdc-test-vector-v1", 4 * 1024 * 1024)
    assert sha(data) == "8adb1ba530a42022b67f5a8a7eec17a134694a7bd33107fcbcf25a9a6ed77a6b"
    chunks = chunk_bytes(data)
    expected = [
        (302199, "ae072e57601b04b202a94e61b72b0a8664302c3a2ba89e24fb8e2f9012086a7a"),
        (353580, "bfeed62493bb916ed4ea2a560ce95c821dc875b01dd053e7d4e97a04290dfcae"),
        (211227, "6d097ccff8f3992f7b800ad155da7267e87cbfeecc0185ee94bba1b75f30497f"),
        (370589, "f44d6fdb0801c1ee65fac38bcdba0d696f21bdbe3fa7ef414f2d619dc99e2dd1"),
        (275527, "36d2364eee6ea411d7e0272332fa01128343698a8bc8c283565bb9efb490b26e"),
        (449179, "057f402f51f5436c7dd6520a702c8e0bd3c849c8c548ffda235a195413eb9ff3"),
        (321334, "6e360c0dc9b000edfa9e63633dfe1cf01a92fa1aa9db49cfddccb91a12279892"),
        (323021, "2129fcb4f925ca49c27ce929c1a42f5f4733effce3b22bbc3f3c305ede1c837b"),
        (332888, "78e645da7f161d96b5f835480644586165195a7257d416c2fb46ce2b2bfd01f7"),
        (362134, "4f140c7493f0d42cf99f30f75f78198bf6526b4ba6edbd2b18a97b7097478a5f"),
        (320605, "3bb6228e16a199c7fbaa0a3ccbfb59f4d4010c28fea04d79a967a37924532a65"),
        (269656, "2980cc09c2ae378906d2f28cb980ffefff61b795fd5e263c654eced452f179d9"),
        (268089, "1294e43fc8208f7eb841d49fffcf84c8a1cd1de06ae5392a884e55ef44a2bbe2"),
        (34276, "82093726d1519f31b1009ebfadf881c208319cec3883818cba5deb8722329f80"),
    ]
    assert [(len(c), sha(c)) for c in chunks] == expected


def test_reassembly_identity_and_size_bounds():
    for size in (0, 1, MIN_SIZE - 1, MIN_SIZE, MIN_SIZE + 1, AVG_SIZE,
                 MAX_SIZE, MAX_SIZE + 1, 3 * MAX_SIZE + 12345):
        data = keystream(b"bounds-%d" % size, size)
        chunks = chunk_bytes(data)
        assert b"".join(chunks) == data
        for c in chunks[:-1]:
            assert MIN_SIZE <= len(c) <= MAX_SIZE
        if chunks:
            assert len(chunks[-1]) <= MAX_SIZE


def test_boundaries_do_not_depend_on_read_size():
    """CHUNKING.md section 4: boundaries are a function of the byte stream."""
    data = keystream(b"read-size-independence", 3 * 1024 * 1024)
    baseline = [sha(c) for c in chunk_bytes(data)]
    for read_size in (1, 7, 4096, 65537, 1 << 20):
        got = [sha(c) for c in iter_chunks(io.BytesIO(data), read_size=read_size)]
        assert got == baseline, "read_size=%d moved a boundary" % read_size


def test_small_edit_disturbs_few_chunks():
    """The property the whole layer exists for."""
    data = keystream(b"edit-stability", 4 * 1024 * 1024)
    edited = bytearray(data)
    edited[2 * 1024 * 1024 : 2 * 1024 * 1024 + 4096] = b"\xAA" * 4096
    before = [sha(c) for c in chunk_bytes(data)]
    after = [sha(c) for c in chunk_bytes(bytes(edited))]
    changed = [h for h in after if h not in set(before)]
    # An edit inside one chunk can at most invalidate that chunk plus, if it
    # moves the boundary, its successor. More than 2 means boundaries are
    # not content-defined at all.
    assert 1 <= len(changed) <= 2
    assert len(before) >= 10  # otherwise the assertion above proves nothing


def test_recipe_round_trips_and_checks():
    r = Recipe(whole_sha256="ab" * 32, whole_size=10, chunks=(("cd" * 32, 4), ("ef" * 32, 6)))
    r2 = Recipe.from_json(r.to_json())
    assert r2 == r
    assert r2.algorithm == ALGORITHM
    bad = Recipe(whole_sha256="ab" * 32, whole_size=11, chunks=(("cd" * 32, 4),))
    with pytest.raises(ValueError):
        bad.check()


# ---------------------------------------------------------------------
# store integration
# ---------------------------------------------------------------------


BIG = 6 * 1024 * 1024  # comfortably above DEFAULT_THRESHOLD


def make_blob_werk(dest: str, payload: bytes, extra: "dict[str, bytes] | None" = None) -> str:
    """A minimal conformant package directory around arbitrary payloads."""
    files = {"data/big.bin": payload}
    files.update(extra or {})
    nodes = []
    for i, (path, data) in enumerate(sorted(files.items())):
        full = os.path.join(dest, *path.split("/"))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as fh:
            fh.write(data)
        nodes.append(
            {
                "node_id": "n%d" % i,
                "type": "x.test.blob",
                "active": 1,
                "versions": [
                    {
                        "v": 1,
                        "note": "test payload",
                        "files": [{"path": path, "sha256": sha(data), "size": len(data)}],
                    }
                ],
            }
        )
    manifest = {
        "entity": {"uuid": "0d5b7a9e-1111-4222-8333-444455556666", "name": "chunk-test"},
        "nodes": nodes,
    }
    raw = (json.dumps(manifest, indent=1, sort_keys=True) + "\n").encode("utf-8")
    with open(os.path.join(dest, "MANIFEST.json"), "wb") as fh:
        fh.write(raw)
    return sha(raw)


def test_ingest_chunks_large_payloads_and_materializes_byte_exact(tmp_path):
    payload = keystream(b"store-big", BIG)
    src = str(tmp_path / "pkg")
    h = make_blob_werk(src, payload)
    store = WerkStore(str(tmp_path / "store"))
    assert store.chunk_threshold == DEFAULT_THRESHOLD

    r = ingest(store, src)
    assert r.files_chunked == 1
    assert r.chunks_total >= 10
    # the whole blob is NOT stored whole - only its chunks and the recipe
    assert not store.objects.has_whole(sha(payload))
    assert store.objects.chunk_recipe(sha(payload)) is not None
    assert store.objects.has(sha(payload))
    assert store.objects.size(sha(payload)) == BIG

    out = str(tmp_path / "out")
    report = materialize(store, h, out, form="directory")
    assert report.ok
    with open(os.path.join(out, "data", "big.bin"), "rb") as fh:
        assert fh.read() == payload

    # zip form reassembles through the same reader
    zpath = str(tmp_path / "out.werk")
    zreport = materialize(store, h, zpath, form="zip")
    assert zreport.ok


def test_small_payloads_stay_whole(tmp_path):
    small = keystream(b"small", 100 * 1024)
    src = str(tmp_path / "pkg")
    make_blob_werk(src, small)
    store = WerkStore(str(tmp_path / "store"))
    r = ingest(store, src)
    assert r.files_chunked == 0
    assert store.objects.has_whole(sha(small))
    assert store.objects.chunk_recipe(sha(small)) is None


def test_edit_costs_chunks_not_the_file(tmp_path):
    payload = keystream(b"editable", BIG)
    edited = bytearray(payload)
    edited[3 * 1024 * 1024 : 3 * 1024 * 1024 + 2048] = b"\x55" * 2048
    edited = bytes(edited)

    src1, src2 = str(tmp_path / "v1"), str(tmp_path / "v2")
    make_blob_werk(src1, payload)
    h2 = make_blob_werk(src2, edited)
    store = WerkStore(str(tmp_path / "store"))
    ingest(store, src1)
    r2 = ingest(store, src2)

    # v2's marginal cost: its manifest plus the changed chunk(s), nowhere
    # near the 6 MiB the whole blob weighs.
    assert r2.bytes_written < 3 * MAX_SIZE
    assert r2.chunks_new <= 2

    out = str(tmp_path / "out-v2")
    assert materialize(store, h2, out, form="directory").ok
    with open(os.path.join(out, "data", "big.bin"), "rb") as fh:
        assert fh.read() == edited


def test_put_stream_chunked_refuses_mismatch_and_adds_nothing(tmp_path):
    store = WerkStore(str(tmp_path / "store"))
    data = keystream(b"refusal", BIG)
    wrong = "0" * 64
    before = set(store.objects.iter_hashes())
    with pytest.raises(HashMismatch):
        store.objects.put_stream_chunked(io.BytesIO(data), expect=wrong, source="x")
    assert set(store.objects.iter_hashes()) == before
    assert list(store.objects.iter_recipe_hashes()) == []


def test_gc_keeps_shared_chunks_and_sweeps_orphans(tmp_path):
    payload = keystream(b"gc-big", BIG)
    edited = payload[: 4 * 1024 * 1024] + b"\xEE" * 1024 + payload[4 * 1024 * 1024 + 1024 :]

    src1, src2 = str(tmp_path / "v1"), str(tmp_path / "v2")
    h1 = make_blob_werk(src1, payload)
    make_blob_werk(src2, edited)
    store = WerkStore(str(tmp_path / "store"))
    ingest(store, src1)
    r2 = ingest(store, src2)
    h2_manifest = [r.manifest_hash for r in store.refs.iter_refs() if r.manifest_hash != h1][0]

    # Drop v2's ref; its unique chunks and its recipe become garbage, the
    # chunks it shares with v1 do not.
    store.refs.remove(h2_manifest)
    report = collect(store, dry_run=False)
    assert report.swept >= 1  # at least v2's manifest and its unique chunk(s)
    assert report.swept_recipes == 1
    assert store.objects.chunk_recipe(sha(payload)) is not None
    assert store.objects.chunk_recipe(sha(edited)) is None

    # v1 must still materialize byte-exact after the sweep.
    out = str(tmp_path / "out")
    assert materialize(store, h1, out, form="directory").ok
    with open(os.path.join(out, "data", "big.bin"), "rb") as fh:
        assert fh.read() == payload
    assert r2.chunks_total > 0  # the test exercised what it claims


def test_scrub_catches_a_corrupt_chunk_and_materialization_fails_loudly(tmp_path):
    payload = keystream(b"scrub-big", BIG)
    src = str(tmp_path / "pkg")
    h = make_blob_werk(src, payload)
    store = WerkStore(str(tmp_path / "store"))
    ingest(store, src)

    recipe = store.objects.chunk_recipe(sha(payload))
    victim = recipe.chunks[3][0]
    path = store.objects.path_for(victim)
    with open(path, "r+b") as fh:
        fh.seek(100)
        b = fh.read(1)
        fh.seek(100)
        fh.write(bytes([b[0] ^ 0xFF]))

    report = scrub(store)
    assert not report.ok
    assert any(c["expected"] == victim for c in report.corrupt)
    # the recipe is now unfulfillable and scrub says so by name
    assert any(sha(payload) in b for b in report.bad_recipes)

    with pytest.raises((MaterializeError, Exception)):
        materialize(store, h, str(tmp_path / "out"), form="directory")
    assert not os.path.exists(str(tmp_path / "out"))


def test_scrub_quarantines_a_lying_recipe(tmp_path):
    payload = keystream(b"lying-recipe", BIG)
    src = str(tmp_path / "pkg")
    make_blob_werk(src, payload)
    store = WerkStore(str(tmp_path / "store"))
    ingest(store, src)

    # Swap two chunks in the recipe: every chunk still rehashes to its own
    # name, but the reassembly no longer hashes to the whole. Only the
    # end-to-end reproof can catch this.
    rpath = store.objects.recipe_path(sha(payload))
    doc = json.loads(open(rpath, "rb").read())
    doc["chunks"][0], doc["chunks"][1] = doc["chunks"][1], doc["chunks"][0]
    with open(rpath, "wb") as fh:
        fh.write(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("ascii"))

    report = scrub(store)
    assert any(sha(payload) in b for b in report.bad_recipes)
    assert any(q.endswith(".recipe.json") for q in report.quarantined)
    # objects themselves are all fine - the chunks were never the problem
    assert not report.corrupt


def test_sync_transfers_only_the_changed_chunks(tmp_path):
    payload = keystream(b"sync-big", BIG)
    edited = bytearray(payload)
    edited[1024 * 1024 : 1024 * 1024 + 512] = b"\x11" * 512
    edited = bytes(edited)

    src1, src2 = str(tmp_path / "v1"), str(tmp_path / "v2")
    h1 = make_blob_werk(src1, payload)
    h2 = make_blob_werk(src2, edited)
    store = WerkStore(str(tmp_path / "store"))
    ingest(store, src1)
    ingest(store, src2)

    remote = WerkStore(str(tmp_path / "remote"))
    push(store, remote, h1)

    p = sync_plan(store, remote, h2)
    assert p.want_bytes < 3 * MAX_SIZE  # not the 6 MiB blob
    result = push(store, remote, h2)
    assert result.bytes_copied < 3 * MAX_SIZE
    assert result.recipes_written >= 1
    assert result.chunk_bytes_reused > 4 * 1024 * 1024

    out = str(tmp_path / "remote-out")
    assert materialize(remote, h2, out, form="directory").ok
    with open(os.path.join(out, "data", "big.bin"), "rb") as fh:
        assert fh.read() == edited


def test_chunking_can_be_disabled(tmp_path):
    payload = keystream(b"disabled", BIG)
    src = str(tmp_path / "pkg")
    make_blob_werk(src, payload)
    store = WerkStore(str(tmp_path / "store"), chunk_threshold=None)
    r = ingest(store, src)
    assert r.files_chunked == 0
    assert store.objects.has_whole(sha(payload))


def test_pre_cdc_store_layout_keeps_working(tmp_path):
    """Migration: a store with no chunks/ directory is simply a store."""
    root = str(tmp_path / "store")
    payload = keystream(b"legacy", BIG)
    src = str(tmp_path / "pkg")
    h = make_blob_werk(src, payload)

    legacy = WerkStore(root, chunk_threshold=None)  # everything whole, as before CDC
    ingest(legacy, src)
    import shutil

    chunks_dir = os.path.join(root, "chunks")
    if os.path.isdir(chunks_dir):
        shutil.rmtree(chunks_dir)

    # Reopen with chunking on: old whole objects answer as ever, and the
    # next large ingest of something NEW chunks without touching them.
    store = WerkStore(root)
    assert store.objects.has_whole(sha(payload))
    out = str(tmp_path / "out")
    assert materialize(store, h, out, form="directory").ok

    other = keystream(b"legacy-2", BIG)
    src2 = str(tmp_path / "pkg2")
    h2 = make_blob_werk(src2, other)
    r = ingest(store, src2)
    assert r.files_chunked == 1
    assert store.objects.has_whole(sha(payload))  # untouched
    assert materialize(store, h2, str(tmp_path / "out2"), form="directory").ok
