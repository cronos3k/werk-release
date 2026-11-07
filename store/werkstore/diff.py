"""Manifest-aware diff.

Constraint 3: "Diff is manifest-aware. The unit of change is the node
version, not the byte range; the changelog is the work notes, already
written, already signed."

So this module never looks inside a payload. A 43 MB GLB that changed is one
line - path, old hash, new hash, size delta - because that is the entire
truth a byte-range diff of a compressed binary could honestly tell you, and
the interesting part (WHY) is the work note the author was required to write
(law 6). The changelog is not generated here; it is *collected* here.

Both faces are produced from one computation: human text and JSON.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

from .manifest import Manifest
from .store import WerkStore


@dataclass
class FileChange:
    path: str
    kind: str  # added | removed | changed
    old_sha256: "str | None" = None
    new_sha256: "str | None" = None
    old_size: "int | None" = None
    new_size: "int | None" = None

    @property
    def size_delta(self) -> int:
        return (self.new_size or 0) - (self.old_size or 0)


@dataclass
class VersionChange:
    node_id: str
    node_type: str
    v: int
    note: str
    epistemic: str = ""
    created: str = ""
    producer: str = ""
    bytes: int = 0


@dataclass
class NodeChange:
    node_id: str
    node_type: str
    versions: int
    active: int
    bytes: int


@dataclass
class Diff:
    a: str
    b: str
    entity_a: str = ""
    entity_b: str = ""
    same_entity: bool = True
    nodes_added: "list[NodeChange]" = field(default_factory=list)
    nodes_removed: "list[NodeChange]" = field(default_factory=list)
    versions_added: "list[VersionChange]" = field(default_factory=list)
    versions_removed: "list[VersionChange]" = field(default_factory=list)
    active_changed: "list[dict]" = field(default_factory=list)
    files: "list[FileChange]" = field(default_factory=list)
    changelog: "list[VersionChange]" = field(default_factory=list)
    new_blob_bytes: int = 0
    shared_blob_bytes: int = 0

    @property
    def empty(self) -> bool:
        return not (
            self.nodes_added
            or self.nodes_removed
            or self.versions_added
            or self.versions_removed
            or self.active_changed
            or self.files
        )

    def to_json(self) -> str:
        doc = asdict(self)
        doc["summary"] = {
            "nodes_added": len(self.nodes_added),
            "nodes_removed": len(self.nodes_removed),
            "versions_added": len(self.versions_added),
            "versions_removed": len(self.versions_removed),
            "files_added": sum(1 for f in self.files if f.kind == "added"),
            "files_removed": sum(1 for f in self.files if f.kind == "removed"),
            "files_changed": sum(1 for f in self.files if f.kind == "changed"),
            "net_size_delta": sum(f.size_delta for f in self.files),
            "new_blob_bytes": self.new_blob_bytes,
            "shared_blob_bytes": self.shared_blob_bytes,
        }
        return json.dumps(doc, indent=2, sort_keys=False, ensure_ascii=False)

    def to_text(self) -> str:
        out: "list[str]" = []
        out.append("werk diff")
        out.append("  from %s  %s" % (self.a[:12], self.entity_a))
        out.append("  to   %s  %s" % (self.b[:12], self.entity_b))
        if not self.same_entity:
            out.append(
                "  NOTE: different entity uuids - these are not two versions of "
                "one entity, they are two entities."
            )
        if self.empty:
            out.append("  no change (identical manifests)")
            return "\n".join(out)

        if self.nodes_added:
            out.append("")
            out.append("nodes added (%d):" % len(self.nodes_added))
            for n in self.nodes_added:
                out.append(
                    "  + %-28s %-22s %d version(s), %s"
                    % (n.node_id, n.node_type, n.versions, _human(n.bytes))
                )
        if self.nodes_removed:
            out.append("")
            out.append("nodes removed (%d):" % len(self.nodes_removed))
            for n in self.nodes_removed:
                out.append(
                    "  - %-28s %-22s %d version(s), %s"
                    % (n.node_id, n.node_type, n.versions, _human(n.bytes))
                )
        if self.versions_added:
            out.append("")
            out.append("node versions added (%d):" % len(self.versions_added))
            for v in self.versions_added:
                out.append(
                    "  + %s@%d  %s  [%s]  %s"
                    % (v.node_id, v.v, _human(v.bytes), v.epistemic or "?", v.producer)
                )
        if self.versions_removed:
            out.append("")
            out.append("node versions removed (%d):" % len(self.versions_removed))
            for v in self.versions_removed:
                out.append("  - %s@%d  %s" % (v.node_id, v.v, _human(v.bytes)))
        if self.active_changed:
            out.append("")
            out.append("active version changed:")
            for c in self.active_changed:
                out.append("  ~ %s  %d -> %d" % (c["node_id"], c["old"], c["new"]))

        if self.files:
            out.append("")
            out.append("files (%d):" % len(self.files))
            for f in sorted(self.files, key=lambda x: (x.kind, x.path)):
                if f.kind == "added":
                    out.append(
                        "  + %-52s %s  %s" % (f.path, (f.new_sha256 or "")[:12], _human(f.new_size or 0))
                    )
                elif f.kind == "removed":
                    out.append(
                        "  - %-52s %s  %s" % (f.path, (f.old_sha256 or "")[:12], _human(f.old_size or 0))
                    )
                else:
                    out.append(
                        "  ~ %-52s %s -> %s  %+d bytes"
                        % (
                            f.path,
                            (f.old_sha256 or "")[:12],
                            (f.new_sha256 or "")[:12],
                            f.size_delta,
                        )
                    )

        out.append("")
        out.append("changelog (the work notes, as written and signed):")
        if self.changelog:
            for v in self.changelog:
                out.append("  %s@%d  %s" % (v.node_id, v.v, v.note))
        else:
            out.append("  (no new node versions)")

        out.append("")
        out.append(
            "blobs: %s new, %s already shared with the other side"
            % (_human(self.new_blob_bytes), _human(self.shared_blob_bytes))
        )
        return "\n".join(out)


def _human(n: int) -> str:
    step = 1024.0
    value = float(n)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(value) < step or unit == "TiB":
            return "%.0f %s" % (value, unit) if unit == "B" else "%.2f %s" % (value, unit)
        value /= step
    return "%d B" % n


def _producer(version) -> str:
    p = version.producer or {}
    bits = [str(p.get("tool", "")), str(p.get("version", ""))]
    if p.get("model"):
        bits.append(str(p["model"]))
    return " ".join(b for b in bits if b)


def _node_change(node) -> NodeChange:
    return NodeChange(
        node_id=node.node_id,
        node_type=node.type,
        versions=len(node.versions),
        active=node.active,
        bytes=sum(v.total_bytes for v in node.versions),
    )


def _version_change(node, version) -> VersionChange:
    return VersionChange(
        node_id=node.node_id,
        node_type=node.type,
        v=version.v,
        note=version.note,
        epistemic=version.epistemic,
        created=version.created,
        producer=_producer(version),
        bytes=version.total_bytes,
    )


def diff_manifests(a: Manifest, b: Manifest) -> Diff:
    """Diff two parsed manifests. Pure - touches no store, no filesystem."""
    d = Diff(
        a=a.digest,
        b=b.digest,
        entity_a=a.entity_name,
        entity_b=b.entity_name,
        same_entity=(a.entity_uuid == b.entity_uuid),
    )

    nodes_a = {n.node_id: n for n in a.nodes}
    nodes_b = {n.node_id: n for n in b.nodes}

    for node_id in sorted(set(nodes_b) - set(nodes_a)):
        node = nodes_b[node_id]
        d.nodes_added.append(_node_change(node))
        for ver in node.versions:
            vc = _version_change(node, ver)
            d.versions_added.append(vc)
            d.changelog.append(vc)
    for node_id in sorted(set(nodes_a) - set(nodes_b)):
        node = nodes_a[node_id]
        d.nodes_removed.append(_node_change(node))
        for ver in node.versions:
            d.versions_removed.append(_version_change(node, ver))

    for node_id in sorted(set(nodes_a) & set(nodes_b)):
        na, nb = nodes_a[node_id], nodes_b[node_id]
        va = {v.v for v in na.versions}
        vb = {v.v for v in nb.versions}
        for v in sorted(vb - va):
            ver = nb.version(v)
            vc = _version_change(nb, ver)
            d.versions_added.append(vc)
            d.changelog.append(vc)
        for v in sorted(va - vb):
            d.versions_removed.append(_version_change(na, na.version(v)))
        if na.active != nb.active:
            d.active_changed.append(
                {"node_id": node_id, "old": na.active, "new": nb.active}
            )

    # File-level truth, deduped by path across versions.
    fa = {f.path: f for _n, _v, f in a.iter_files()}
    fb = {f.path: f for _n, _v, f in b.iter_files()}
    for path in sorted(set(fb) - set(fa)):
        f = fb[path]
        d.files.append(FileChange(path, "added", None, f.sha256, None, f.size))
    for path in sorted(set(fa) - set(fb)):
        f = fa[path]
        d.files.append(FileChange(path, "removed", f.sha256, None, f.size, None))
    for path in sorted(set(fa) & set(fb)):
        x, y = fa[path], fb[path]
        if x.sha256 != y.sha256:
            d.files.append(FileChange(path, "changed", x.sha256, y.sha256, x.size, y.size))

    # Blob-level: what a sync from a to b would actually have to move.
    blobs_a = {f.sha256: f.size for _n, _v, f in a.iter_files()}
    blobs_b = {f.sha256: f.size for _n, _v, f in b.iter_files()}
    d.new_blob_bytes = sum(size for h, size in blobs_b.items() if h not in blobs_a)
    d.shared_blob_bytes = sum(size for h, size in blobs_b.items() if h in blobs_a)
    return d


def diff_stored(store: WerkStore, hash_a: str, hash_b: str) -> Diff:
    """Diff two manifests already in the store, by manifest hash."""
    from .materialize import _load_manifest

    return diff_manifests(_load_manifest(store, hash_a), _load_manifest(store, hash_b))
