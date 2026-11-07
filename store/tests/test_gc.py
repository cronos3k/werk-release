"""GC and scrub: pinned survives, garbage goes, corruption is found."""

import os

from werkstore import collect, ingest, scrub
from werkstore.gc import compute_roots
from werkstore.refs import Pin
from werkstore.store import now_iso


def test_garbage_goes_and_referenced_survives(store, werk_v1):
    src, manifest_hash = werk_v1
    result = ingest(store, src)

    garbage = store.objects.put_bytes(b"nothing points at me").digest
    assert store.objects.has(garbage)

    dry = collect(store, dry_run=True)
    assert garbage in dry.swept_hashes
    assert dry.swept == 1
    assert store.objects.has(garbage), "a dry run must delete nothing"

    real = collect(store, dry_run=False)
    assert real.swept == 1
    assert not store.objects.has(garbage)
    assert real.live == result.files_total + 2  # payloads + manifest + signature

    # Everything the package needs is still there.
    roots = compute_roots(store)
    assert roots.missing == []


def test_inactive_versions_are_roots_too(store, werk_v2):
    """Law 6: pointing back to an earlier version must stay a seconds-long act.

    A GC that swept non-active versions would silently turn that into a
    restore-from-backup, so the v1 texture blob must survive even though the
    node's active pointer is v2.
    """
    src, _h = werk_v2
    ingest(store, src)
    import json

    manifest = json.loads(open(os.path.join(src, "MANIFEST.json"), "rb").read())
    tex = next(n for n in manifest["nodes"] if n["node_id"] == "tex-base-color")
    assert tex["active"] == 2
    inactive_blob = tex["versions"][0]["files"][0]["sha256"]

    collect(store, dry_run=False)
    assert store.objects.has(inactive_blob)


def test_a_pin_keeps_an_otherwise_unreachable_object(store):
    kept = store.objects.put_bytes(b"a blob a benchmark depends on").digest
    dropped = store.objects.put_bytes(b"a blob nobody needs").digest
    store.refs.put_pin(
        Pin(name="bench-corpus", hashes=[kept], note="held for the perf run", created=now_iso())
    )

    report = collect(store, dry_run=False)
    assert store.objects.has(kept)
    assert not store.objects.has(dropped)
    assert report.swept == 1

    store.refs.remove_pin("bench-corpus")
    collect(store, dry_run=False)
    assert not store.objects.has(kept)


def test_gc_refuses_when_a_root_cannot_be_read(store, werk_v1):
    """An unknown reachable set makes every deletion a guess. Refuse instead."""
    src, manifest_hash = werk_v1
    ingest(store, src)
    payload = store.objects.put_bytes(b"garbage").digest

    # Lose the manifest object while keeping the ref that points at it.
    store.objects.remove(manifest_hash)

    report = collect(store, dry_run=False)
    assert report.refused
    assert "unknown" in report.refused
    assert report.swept == 0
    assert store.objects.has(payload), "a refused gc must not delete anything"


def test_scrub_finds_a_deliberately_corrupted_object(store, werk_v1):
    src, _h = werk_v1
    ingest(store, src)

    clean = scrub(store)
    assert clean.ok
    assert clean.checked > 0
    assert clean.bytes_checked > 0

    victim = sorted(store.objects.iter_hashes())[0]
    with open(store.objects.path_for(victim), "r+b") as fh:
        fh.seek(0)
        fh.write(b"\x00")

    dirty = scrub(store)
    assert not dirty.ok
    assert len(dirty.corrupt) == 1
    record = dirty.corrupt[0]
    assert record["expected"] == victim
    assert record["actual"] != victim
    assert os.path.isfile(record["quarantined"])
    # Quarantined, not deleted: corrupt data is evidence.
    assert not store.objects.has(victim)
    # And the package that needed it is now reported as incomplete.
    assert victim in dirty.missing_rooted


def test_scrub_can_report_without_quarantining(store, werk_v1):
    src, _h = werk_v1
    ingest(store, src)
    victim = sorted(store.objects.iter_hashes())[0]
    with open(store.objects.path_for(victim), "r+b") as fh:
        fh.seek(0)
        fh.write(b"\x01")
    report = scrub(store, quarantine=False)
    assert len(report.corrupt) == 1
    assert report.quarantined == []
    assert store.objects.has(victim)
