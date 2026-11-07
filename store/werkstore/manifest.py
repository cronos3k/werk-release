"""Manifest reading - structure only, never authority.

The store parses a manifest for exactly two reasons: to learn which blobs a
package owns, and to learn how to put them back. It does not validate the
profile (that is werk-core's job), it does not rewrite manifests, and it
never treats its parsed copy as the artifact. The RAW BYTES are the truth;
everything here is a view over them.

Shape source: spec/schemas/manifest.schema.json when present, otherwise the
manifest section of SPEC-3D-ENTITY.md. The fields this module depends on are
identical in both:

    entity.uuid, entity.name
    container.entry_order         (optional; preview-first zip ordering)
    license.file                  (optional convenience)
    nodes[].node_id
    nodes[].type
    nodes[].active
    nodes[].versions[].v
    nodes[].versions[].note
    nodes[].versions[].files[].path
    nodes[].versions[].files[].sha256
    nodes[].versions[].files[].size

Everything else in the manifest is carried through untouched, because the
store's job is to give back the same bytes, not a tidier version of them.
"""

from __future__ import annotations

import json
import posixpath
from dataclasses import dataclass, field
from typing import Any, Iterator

from .errors import ManifestError, UnsafePath

MANIFEST_NAME = "MANIFEST.json"
SIGNATURE_NAME = "SIGNATURE.json"


def check_path(path: object) -> str:
    """Validate a package-relative path and return it normalised to POSIX.

    Rejects absolute paths, drive letters, backslashes, '.' and '..'
    segments, and empty components. A manifest path is data from an
    untrusted package; materialization writes to disk from it, so this is
    the boundary that stops a package escaping its own directory.
    """
    if not isinstance(path, str) or not path:
        raise UnsafePath("path is not a non-empty string: %r" % (path,))
    if "\\" in path:
        raise UnsafePath("backslash in package path: %r" % (path,))
    if path.startswith("/") or (len(path) > 1 and path[1] == ":"):
        raise UnsafePath("absolute path in manifest: %r" % (path,))
    parts = path.split("/")
    for part in parts:
        if part in ("", ".", ".."):
            raise UnsafePath("unsafe path component in %r" % (path,))
    normalised = posixpath.normpath(path)
    if normalised != path:
        raise UnsafePath("non-canonical path in manifest: %r" % (path,))
    return path


@dataclass(frozen=True)
class FileEntry:
    """One file owned by one node version."""

    path: str
    sha256: str
    size: int
    role: "str | None" = None
    media_type: "str | None" = None

    @property
    def key(self) -> "tuple[str, str]":
        return (self.path, self.sha256)


@dataclass(frozen=True)
class Version:
    """One append-only version of a node."""

    v: int
    files: "tuple[FileEntry, ...]"
    note: str
    producer: "dict[str, Any]" = field(default_factory=dict)
    epistemic: str = ""
    created: str = ""
    input_hash: "str | None" = None

    @property
    def total_bytes(self) -> int:
        return sum(f.size for f in self.files)


@dataclass(frozen=True)
class Node:
    """One node of the graph."""

    node_id: str
    type: str
    active: int
    versions: "tuple[Version, ...]"
    part_id: "str | None" = None

    def version(self, v: int) -> "Version | None":
        for ver in self.versions:
            if ver.v == v:
                return ver
        return None


class Manifest:
    """A parsed view over the exact manifest bytes.

    ``raw`` is authoritative. ``digest`` is the sha256 of ``raw`` and is the
    store key for the whole package: the manifest hashes every file, so the
    manifest hash names the entire package state (and is what a signature
    signs).
    """

    def __init__(self, raw: bytes) -> None:
        from .objects import hash_bytes

        self.raw = raw
        self.digest = hash_bytes(raw)
        try:
            doc = json.loads(raw)
        except Exception as exc:  # json raises several unrelated types
            raise ManifestError("MANIFEST.json is not parseable JSON: %s" % (exc,))
        if not isinstance(doc, dict):
            raise ManifestError("MANIFEST.json is not a JSON object")
        self.doc: "dict[str, Any]" = doc
        self.nodes: "tuple[Node, ...]" = tuple(self._parse_nodes())
        self._by_id = {n.node_id: n for n in self.nodes}

    # -- construction -------------------------------------------------

    @classmethod
    def from_file(cls, path: str) -> "Manifest":
        with open(path, "rb") as fh:
            return cls(fh.read())

    def _parse_nodes(self) -> "Iterator[Node]":
        raw_nodes = self.doc.get("nodes")
        if not isinstance(raw_nodes, list) or not raw_nodes:
            raise ManifestError("manifest has no nodes[]")
        for i, rn in enumerate(raw_nodes):
            if not isinstance(rn, dict):
                raise ManifestError("nodes[%d] is not an object" % i)
            node_id = rn.get("node_id")
            if not isinstance(node_id, str) or not node_id:
                raise ManifestError("nodes[%d] has no node_id" % i)
            raw_versions = rn.get("versions")
            if not isinstance(raw_versions, list) or not raw_versions:
                raise ManifestError("node %s has no versions[]" % node_id)
            versions = []
            for j, rv in enumerate(raw_versions):
                if not isinstance(rv, dict):
                    raise ManifestError("node %s versions[%d] not an object" % (node_id, j))
                files = []
                raw_files = rv.get("files")
                if not isinstance(raw_files, list):
                    raise ManifestError(
                        "node %s v%s has no files[]" % (node_id, rv.get("v"))
                    )
                for rf in raw_files:
                    if not isinstance(rf, dict):
                        raise ManifestError("node %s has a non-object file entry" % node_id)
                    from .objects import is_hash

                    digest = rf.get("sha256")
                    if not is_hash(digest):
                        raise ManifestError(
                            "node %s file %r has no lowercase-hex sha256"
                            % (node_id, rf.get("path"))
                        )
                    size = rf.get("size")
                    if not isinstance(size, int) or size < 0:
                        raise ManifestError(
                            "node %s file %r has no declared size"
                            % (node_id, rf.get("path"))
                        )
                    files.append(
                        FileEntry(
                            path=check_path(rf.get("path")),
                            sha256=digest,
                            size=size,
                            role=rf.get("role"),
                            media_type=rf.get("media_type"),
                        )
                    )
                versions.append(
                    Version(
                        v=int(rv.get("v", j + 1)),
                        files=tuple(files),
                        note=str(rv.get("note", "")),
                        producer=rv.get("producer") or {},
                        epistemic=str(rv.get("epistemic", "")),
                        created=str(rv.get("created", "")),
                        input_hash=rv.get("input_hash"),
                    )
                )
            yield Node(
                node_id=node_id,
                type=str(rn.get("type", "")),
                active=int(rn.get("active", versions[-1].v)),
                versions=tuple(versions),
                part_id=rn.get("part_id"),
            )

    # -- identity -----------------------------------------------------

    @property
    def entity_uuid(self) -> str:
        entity = self.doc.get("entity") or {}
        return str(entity.get("uuid", ""))

    @property
    def entity_name(self) -> str:
        entity = self.doc.get("entity") or {}
        return str(entity.get("name", ""))

    @property
    def entry_order(self) -> "list[str]":
        container = self.doc.get("container") or {}
        order = container.get("entry_order")
        return list(order) if isinstance(order, list) else []

    @property
    def zip_compression(self) -> str:
        container = self.doc.get("container") or {}
        return str(container.get("zip_compression", "store"))

    # -- the file set -------------------------------------------------

    def node(self, node_id: str) -> "Node | None":
        return self._by_id.get(node_id)

    def iter_files(self) -> "Iterator[tuple[Node, Version, FileEntry]]":
        """Every file of every version - all of them, not just active ones.

        Law 6: old versions are never rewritten and never silently dropped.
        A store that only kept the active version would make pointing back
        to a previous version impossible, which is the whole feature.
        """
        for node in self.nodes:
            for ver in node.versions:
                for f in ver.files:
                    yield node, ver, f

    def file_map(self) -> "dict[str, str]":
        """path -> sha256, over every version.

        A path may legitimately appear once per version directory (`@N`
        suffixes); two different hashes claiming the SAME path is a broken
        manifest and is reported here rather than silently resolved.
        """
        out: "dict[str, str]" = {}
        for _node, _ver, f in self.iter_files():
            prev = out.get(f.path)
            if prev is not None and prev != f.sha256:
                raise ManifestError(
                    "path %s is claimed by two different hashes (%s, %s)"
                    % (f.path, prev, f.sha256)
                )
            out[f.path] = f.sha256
        return out

    def payload_hashes(self) -> "set[str]":
        return {f.sha256 for _n, _v, f in self.iter_files()}

    def total_declared_bytes(self) -> int:
        """Sum of declared sizes over DISTINCT paths (the materialized size)."""
        seen: "dict[str, int]" = {}
        for _n, _v, f in self.iter_files():
            seen[f.path] = f.size
        return sum(seen.values())
