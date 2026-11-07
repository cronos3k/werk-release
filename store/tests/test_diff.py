"""Manifest-aware diff: node versions, not byte ranges; work notes as changelog."""

import json

from werkstore import ingest
from werkstore.diff import diff_stored


def test_diff_reports_versions_files_and_the_changelog(store, werk_v1, werk_v2):
    src1, h1 = werk_v1
    src2, h2 = werk_v2
    ingest(store, src1)
    ingest(store, src2)

    d = diff_stored(store, h1, h2)
    assert d.same_entity, "the pair is two versions of one entity"

    # One node added (the LOD), one node gained a version (the re-bake).
    assert [n.node_id for n in d.nodes_added] == ["geom-lod1"]
    assert d.nodes_removed == []
    added = {(v.node_id, v.v) for v in d.versions_added}
    assert ("tex-base-color", 2) in added
    assert ("geom-lod1", 1) in added

    # Active pointer moved - the author's recommendation changed, and that is
    # a fact a diff must surface (law 6: it is a recommendation, not a command).
    assert d.active_changed == [{"node_id": "tex-base-color", "old": 1, "new": 2}]

    # Files: the new version's payload appears alongside the old one, because
    # versions coexist. The v1 texture is NOT reported as changed or removed.
    kinds = {f.path: f.kind for f in d.files}
    assert kinds["textures/base-color@2.png"] == "added"
    assert kinds["geometry/lod1.glb"] == "added"
    assert "textures/base-color.png" not in kinds

    # The changelog is the work notes, already written, already signed.
    notes = {v.note for v in d.changelog}
    assert any("seam bleed" in n for n in notes)
    assert any("decimation" in n for n in notes)
    assert all(len(n) >= 8 for n in notes), "a work note is mandatory and 'update' is not one"


def test_diff_json_and_text_agree(store, werk_v1, werk_v2):
    src1, h1 = werk_v1
    src2, h2 = werk_v2
    ingest(store, src1)
    ingest(store, src2)
    d = diff_stored(store, h1, h2)

    doc = json.loads(d.to_json())
    assert doc["summary"]["versions_added"] == len(d.versions_added)
    assert doc["summary"]["files_added"] == sum(1 for f in d.files if f.kind == "added")
    assert doc["a"] == h1 and doc["b"] == h2

    text = d.to_text()
    assert "node versions added" in text
    assert "changelog (the work notes" in text
    assert "geom-lod1" in text
    assert "seam bleed" in text


def test_diff_of_a_package_with_itself_is_empty(store, werk_v1):
    src1, h1 = werk_v1
    ingest(store, src1)
    d = diff_stored(store, h1, h1)
    assert d.empty
    assert "no change" in d.to_text()


def test_reverse_diff_reports_removal(store, werk_v1, werk_v2):
    src1, h1 = werk_v1
    src2, h2 = werk_v2
    ingest(store, src1)
    ingest(store, src2)
    d = diff_stored(store, h2, h1)
    assert [n.node_id for n in d.nodes_removed] == ["geom-lod1"]
    assert ("tex-base-color", 2) in {(v.node_id, v.v) for v in d.versions_removed}
    assert d.changelog == []


def test_blob_accounting_predicts_what_a_sync_would_move(store, werk_v1, werk_v2):
    src1, h1 = werk_v1
    src2, h2 = werk_v2
    ingest(store, src1)
    ingest(store, src2)
    d = diff_stored(store, h1, h2)
    assert d.new_blob_bytes > 0
    assert d.shared_blob_bytes > d.new_blob_bytes, (
        "the fixture pair is supposed to share most of its bytes"
    )
