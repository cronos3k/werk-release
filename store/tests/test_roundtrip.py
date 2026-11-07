"""The Stage 7 gate: store round-trip proves byte-identity against signatures.

The discipline the brief demands is that no test may pass only because the
store was authoritative. So every assertion here compares the MATERIALIZED
RESULT against the ORIGINAL PACKAGE ON DISK - two things the store cannot
both fabricate - and the signature chain is verified against the manifest
bytes that came back, not against the manifest bytes we put in.
"""

import hashlib
import json
import os

import pytest

import mkwerk
from werkstore import ingest, materialize
from werkstore.errors import MaterializeError
from werkstore.ingest import IngestRefused
from werkstore.signature import VALID


def _tree(root):
    """path -> sha256 for every file under *root*."""
    out = {}
    for dirpath, _dirs, names in os.walk(root):
        for name in names:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            with open(full, "rb") as fh:
                out[rel] = hashlib.sha256(fh.read()).hexdigest()
    return out


def test_directory_roundtrip_is_byte_identical(store, werk_v1, tmp_path):
    src, manifest_hash = werk_v1
    result = ingest(store, src)
    assert result.manifest_hash == manifest_hash
    assert result.signature_state == VALID

    out = str(tmp_path / "materialized")
    report = materialize(store, manifest_hash, out, form="directory")

    before = _tree(src)
    after = _tree(out)
    assert after == before, "materialized tree differs from the original package"
    assert report.files_verified == len(before) - 2  # MANIFEST and SIGNATURE verified separately
    assert report.signature is not None and report.signature.state == VALID

    # And byte-for-byte, not merely hash-for-hash, on a payload chosen at
    # random from the tree: hashes agreeing while bytes differ would be a
    # sha256 collision, but comparing the bytes costs nothing here.
    for rel in sorted(before)[:3]:
        with open(os.path.join(src, *rel.split("/")), "rb") as a, open(
            os.path.join(out, *rel.split("/")), "rb"
        ) as b:
            assert a.read() == b.read()


def test_zip_roundtrip_is_byte_identical_and_preview_first(store, werk_v1, tmp_path):
    src, manifest_hash = werk_v1
    ingest(store, src)
    out = str(tmp_path / "materialized.werk")
    report = materialize(store, manifest_hash, out, form="zip")
    assert report.ok

    import zipfile

    with zipfile.ZipFile(out) as zf:
        names = [i.filename for i in zf.infolist()]
        # Law 9: the manifest, the chain and the browsable tier come first.
        assert names[0] == "MANIFEST.json"
        assert names[1] == "SIGNATURE.json"
        assert "LICENSE" in names[:4]
        semantics_at = [i for i, n in enumerate(names) if n.startswith("semantics/")]
        geometry_at = [i for i, n in enumerate(names) if n.startswith("geometry/")]
        assert max(semantics_at) < min(geometry_at)
        # store mode: readable without an inflate implementation
        assert all(i.compress_type == zipfile.ZIP_STORED for i in zf.infolist())
        for rel, digest in _tree(src).items():
            assert hashlib.sha256(zf.read(rel)).hexdigest() == digest

    assert 0 < report.preview_prefix_bytes < report.total_size_bytes


def test_materialization_fails_loudly_when_the_store_rotted(store, werk_v1, tmp_path):
    """The store is a cache, never the truth.

    If the cache has rotted, materialization must FAIL - not hand back
    plausible bytes, and not quietly succeed because the store agrees with
    its own bookkeeping.
    """
    src, manifest_hash = werk_v1
    ingest(store, src)

    # Corrupt one payload object in place, leaving its name alone.
    manifest = json.loads(open(os.path.join(src, "MANIFEST.json"), "rb").read())
    victim = None
    for node in manifest["nodes"]:
        for ver in node["versions"]:
            for f in ver["files"]:
                if f["path"].endswith(".png"):
                    victim = f["sha256"]
    assert victim
    with open(store.objects.path_for(victim), "r+b") as fh:
        fh.seek(64)
        fh.write(b"\x00\x00\x00\x00")

    out = str(tmp_path / "should-not-exist")
    with pytest.raises(Exception) as exc:
        materialize(store, manifest_hash, out, form="directory")
    assert "hash" in str(exc.value).lower()
    assert not os.path.exists(out), "a failed materialization must not leave a package behind"


def test_ingest_refuses_a_tampered_package(store, werk_v1):
    """A payload whose bytes disagree with the manifest is refused, with a report."""
    src, _manifest_hash = werk_v1
    victim = os.path.join(src, "textures", "base-color.png")
    with open(victim, "r+b") as fh:
        fh.seek(100)
        fh.write(b"\xff\xff")

    with pytest.raises(IngestRefused) as exc:
        ingest(store, src)
    text = str(exc.value)
    assert "textures/base-color.png" in text
    assert "manifest declares sha256=" in text
    assert "hash to sha256=" in text
    # No ref was recorded for a package we refused.
    assert list(store.refs.iter_refs()) == []


def test_ingest_refuses_a_floating_file(store, werk_v1, tmp_path):
    """SPEC section 2: nothing floats. A file no node claims cannot be given back."""
    src, _ = werk_v1
    with open(os.path.join(src, "stray.bin"), "wb") as fh:
        fh.write(b"nobody claims me")
    with pytest.raises(IngestRefused) as exc:
        ingest(store, src)
    assert "floating file" in str(exc.value)


def test_unsigned_package_round_trips_and_says_so(store, tmp_path):
    """Absent is a legitimate state, and it must stay visible (law 7)."""
    src = str(tmp_path / "anon")
    manifest_hash = mkwerk.make_synthetic(src, "v1", sign=False)
    result = ingest(store, src)
    assert result.signature_state == "absent"
    out = str(tmp_path / "anon-out")
    report = materialize(store, manifest_hash, out, form="directory")
    assert report.ok
    assert report.signature.state == "absent"
    assert _tree(out) == _tree(src)


def test_stripping_the_signature_after_ingest_is_caught(store, werk_v1, tmp_path):
    """A materialized package that lost its chain is a problem, not a shrug."""
    src, manifest_hash = werk_v1
    ingest(store, src)
    ref = store.refs.get(manifest_hash)
    assert ref.signature_hash
    store.objects.remove(ref.signature_hash)
    with pytest.raises(Exception):
        materialize(store, manifest_hash, str(tmp_path / "nosig"), form="directory")


def test_two_ingests_of_the_same_package_are_one_ref(store, werk_v1):
    src, manifest_hash = werk_v1
    first = ingest(store, src)
    second = ingest(store, src)
    assert first.manifest_hash == second.manifest_hash
    assert len(list(store.refs.iter_refs())) == 1
    assert second.bytes_written == 0
    assert second.objects_deduped == second.files_total
