"""Dedup: two versions sharing blobs are stored once. Measured, not asserted."""

import os

import pytest

import mkwerk
from werkstore import ingest, materialize
from werkstore.manifest import Manifest


def _logical_bytes(pkg_dir):
    total = 0
    for dirpath, _dirs, names in os.walk(pkg_dir):
        for name in names:
            total += os.path.getsize(os.path.join(dirpath, name))
    return total


def test_shared_blobs_are_stored_once(store, werk_v1, werk_v2):
    src1, h1 = werk_v1
    src2, h2 = werk_v2

    first = ingest(store, src1)
    after_first = store.objects.count_and_bytes()
    second = ingest(store, src2)
    after_second = store.objects.count_and_bytes()

    assert h1 != h2, "the pair must actually differ"

    m1 = Manifest(open(os.path.join(src1, "MANIFEST.json"), "rb").read())
    m2 = Manifest(open(os.path.join(src2, "MANIFEST.json"), "rb").read())
    shared = m1.payload_hashes() & m2.payload_hashes()
    only_in_v2 = m2.payload_hashes() - m1.payload_hashes()
    assert shared, "the fixture pair must share blobs or this measures nothing"
    assert only_in_v2, "the fixture pair must differ or this measures nothing"

    # The second ingest wrote only the genuinely new blobs.
    assert second.objects_deduped >= len(shared)
    expected_new_bytes = sum(
        e.size
        for _n, _v, e in m2.iter_files()
        if e.sha256 in only_in_v2
    )
    # (dedup by hash: a blob appearing twice in v2 is still counted once)
    seen = set()
    expected_new_bytes = 0
    for _n, _v, e in m2.iter_files():
        if e.sha256 in only_in_v2 and e.sha256 not in seen:
            seen.add(e.sha256)
            expected_new_bytes += e.size
    assert second.bytes_written == expected_new_bytes

    # Every shared blob has exactly one copy on disk.
    for digest in shared:
        assert store.objects.has(digest)
    # +2: v2's own manifest object and its own signature object. Those two
    # differ by construction (the manifest hashes every file; the chain signs
    # the manifest), so they are the irreducible per-package overhead.
    assert after_second[0] == after_first[0] + len(only_in_v2) + 2

    logical = _logical_bytes(src1) + _logical_bytes(src2)
    physical = after_second[1]
    assert physical < logical
    print(
        "\ndedup (synthetic pair): logical %d B, physical %d B, ratio %.3fx, saved %.1f%%"
        % (logical, physical, logical / physical, 100.0 * (1 - physical / logical))
    )


def test_both_versions_still_materialize_after_dedup(store, werk_v1, werk_v2, tmp_path):
    """Dedup must not cost either package its byte-identity.

    This is the failure mode a clever store dies of: it deduplicates, and
    then one of the two packages cannot be reconstructed exactly. Working
    copies are whole; the store is clever. Never the reverse.
    """
    src1, h1 = werk_v1
    src2, h2 = werk_v2
    ingest(store, src1)
    ingest(store, src2)

    for name, digest, src in (("out1", h1, src1), ("out2", h2, src2)):
        out = str(tmp_path / name)
        report = materialize(store, digest, out, form="directory")
        assert report.ok
        for dirpath, _dirs, names in os.walk(src):
            for fname in names:
                rel = os.path.relpath(os.path.join(dirpath, fname), src)
                with open(os.path.join(src, rel), "rb") as a, open(
                    os.path.join(out, rel), "rb"
                ) as b:
                    assert a.read() == b.read(), "%s differs in %s" % (rel, name)


# The real corpus is private to the author's machine. WERK_STORE_CORPUS points
# this test at another corpus with the same layout (model/model.glb,
# model/textures/, views/*.png, audio/<group>/*.wav, properties.json).
# Unset, the test uses mkwerk.DEFAULT_CORPUS, as before.
REAL_CORPUS = os.environ.get("WERK_STORE_CORPUS") or mkwerk.DEFAULT_CORPUS


@pytest.mark.skipif(
    not mkwerk.corpus_available(REAL_CORPUS),
    reason="real asset corpus not present on this machine (set WERK_STORE_CORPUS to use another)",
)
def test_dedup_on_the_real_corpus(store, tmp_path):
    """The gate measurement, on production assets rather than generated noise."""
    src1 = str(tmp_path / "bell-v1")
    src2 = str(tmp_path / "bell-v2")
    h1 = mkwerk.make_from_corpus(src1, REAL_CORPUS, variant="v1")
    h2 = mkwerk.make_from_corpus(src2, REAL_CORPUS, variant="v2")

    ingest(store, src1)
    ingest(store, src2)
    _count, physical = store.objects.count_and_bytes()
    logical = _logical_bytes(src1) + _logical_bytes(src2)

    assert h1 != h2
    assert physical < logical
    print(
        "\ndedup (real corpus pair): logical %d B, physical %d B, ratio %.3fx, saved %.2f%%"
        % (logical, physical, logical / physical, 100.0 * (1 - physical / logical))
    )

    for name, digest, src in (("bell-out1", h1, src1), ("bell-out2", h2, src2)):
        report = materialize(store, digest, str(tmp_path / name), form="directory")
        assert report.ok
