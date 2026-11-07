"""Ingest a .werk into the store.

Contract, in the order the brief states it:

  * parse the manifest;
  * store every payload blob under ITS MANIFEST HASH, verifying while
    streaming - a mismatch is a refusal with an exact report, never a
    silent re-key under the hash we actually computed;
  * store the manifest and the signature as objects too (they are bytes the
    package owns, and materialization needs them back verbatim);
  * record a package ref {entity_uuid, name, manifest_hash, time}.

Two refusals that are not optional:

  1. A file whose bytes do not hash to the manifest's declared sha256. The
     store would otherwise become a place where a corrupt package looks
     fine, which is the exact opposite of its job.
  2. A file present in the container that no node version claims. SPEC
     section 2: "Every byte in the container except MANIFEST.json is
     reachable from exactly one node version's files[]. Nothing floats."
     Ingesting a floating file would mean materialization silently produces
     a DIFFERENT package - byte-identity we could not prove.

Both can be waived explicitly (`--allow-floating`, `strict=False`) because a
tool that cannot examine a broken package is useless for diagnosing one, and
both waivers are recorded, never assumed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from .errors import HashMismatch, SizeMismatch, WerkStoreError
from .manifest import MANIFEST_NAME, SIGNATURE_NAME, Manifest
from .refs import PackageRef
from .signature import verify_chain
from .store import WerkStore, now_iso
from .werkpkg import ZipSource, open_werk


class IngestRefused(WerkStoreError):
    """Ingest found problems it will not paper over. Carries every one."""

    def __init__(self, problems: "list[str]", source: str) -> None:
        self.problems = problems
        self.source = source
        super().__init__(
            "refusing to ingest %s - %d problem%s:\n  %s"
            % (
                source,
                len(problems),
                "" if len(problems) == 1 else "s",
                "\n  ".join(problems),
            )
        )


@dataclass
class IngestResult:
    manifest_hash: str
    entity_uuid: str
    name: str
    signature_state: str
    files_total: int = 0
    objects_new: int = 0
    objects_deduped: int = 0
    bytes_logical: int = 0  # what the package weighs
    bytes_written: int = 0  # what this ingest actually added to the store
    bytes_deduped: int = 0  # what it did not have to add
    files_chunked: int = 0  # payloads stored via CDC (see store/CHUNKING.md)
    chunks_total: int = 0
    chunks_new: int = 0
    warnings: "list[str]" = field(default_factory=list)

    @property
    def dedup_ratio(self) -> float:
        """logical bytes / bytes written by this ingest (inf if nothing new)."""
        if self.bytes_written == 0:
            return float("inf")
        return self.bytes_logical / self.bytes_written


def ingest(
    store: WerkStore,
    package_path: str,
    strict: bool = True,
    require_valid_signature: bool = False,
) -> IngestResult:
    """Ingest the .werk at *package_path* (directory or zip) into *store*."""
    src = open_werk(package_path)
    try:
        manifest = Manifest(src.manifest_bytes())
        sig_bytes = src.signature_bytes()
        verdict = verify_chain(sig_bytes, manifest.digest)

        problems: "list[str]" = []
        warnings: "list[str]" = []

        if require_valid_signature and not verdict.ok:
            problems.append(verdict.summary())
        elif verdict.state == "present-and-invalid":
            # Recorded, loudly, and still ingested: an invalid signature is a
            # trust verdict, not a parse failure, and refusing to store the
            # evidence would help the forger.
            warnings.append(verdict.summary())

        # Everything the manifest claims, deduped by (path, hash) - a path
        # may appear in several versions with identical bytes.
        claimed: "dict[str, str]" = manifest.file_map()

        present = set(src.paths())
        unclaimed = sorted(
            p for p in present if p not in claimed and p not in (MANIFEST_NAME, SIGNATURE_NAME)
        )
        for p in unclaimed:
            msg = "floating file not claimed by any node version: %s" % p
            (problems if strict else warnings).append(msg)

        missing = sorted(p for p in claimed if p not in present)
        for p in missing:
            problems.append("manifest claims %s but the container does not contain it" % p)

        result = IngestResult(
            manifest_hash=manifest.digest,
            entity_uuid=manifest.entity_uuid,
            name=manifest.entity_name,
            signature_state=verdict.state,
        )

        # Stream every claimed file into the store, verifying as we go.
        # Large payloads (declared size at or above the store's chunk
        # threshold) are stored chunked - CDC, store/CHUNKING.md - so an
        # edited multi-MB GLB costs its changed chunks, not its whole self.
        # The decision reads the manifest's DECLARED size; if that lies, the
        # existing size check below reports it either way.
        declared_size: "dict[str, int]" = {}
        for _node, _ver, entry in manifest.iter_files():
            declared_size[entry.path] = entry.size
        threshold = getattr(store, "chunk_threshold", None)

        for path in sorted(claimed):
            if path in missing:
                continue
            expected = claimed[path]
            chunk_this = (
                threshold is not None and declared_size.get(path, 0) >= threshold
            )
            try:
                with src.open(path) as fh:
                    if chunk_this:
                        put = store.objects.put_stream_chunked(
                            fh, expect=expected, source=path
                        )
                    else:
                        put = store.objects.put_stream(fh, expect=expected, source=path)
            except HashMismatch as exc:
                problems.append(str(exc))
                continue
            result.files_total += 1
            result.bytes_logical += put.size
            result.bytes_written += put.bytes_written
            result.bytes_deduped += put.size - put.bytes_written
            if put.chunked:
                result.files_chunked += 1
                result.chunks_total += put.chunks_total
                result.chunks_new += put.chunks_new
            if put.deduped:
                result.objects_deduped += 1
            else:
                result.objects_new += 1

        # Declared sizes are part of the manifest's promise; check them.
        for _node, _ver, entry in manifest.iter_files():
            if entry.path in missing:
                continue
            try:
                actual = store.objects.size(entry.sha256)
            except Exception:
                continue
            if actual != entry.size:
                problems.append(str(SizeMismatch(entry.path, entry.size, actual)))

        if problems:
            raise IngestRefused(problems, package_path)

        # The manifest and the chain are bytes too. Store them by their own
        # hashes; the manifest's hash is the package's name.
        store.objects.put_bytes(manifest.raw, expect=manifest.digest, source=MANIFEST_NAME)
        sig_hash = None
        if sig_bytes is not None:
            sig_hash = store.objects.put_bytes(sig_bytes, source=SIGNATURE_NAME).digest

        ref = PackageRef(
            manifest_hash=manifest.digest,
            entity_uuid=manifest.entity_uuid,
            name=manifest.entity_name,
            signature_hash=sig_hash,
            signature_state=verdict.state,
            ingested_at=now_iso(),
            source=os.path.abspath(package_path),
            container_form="zip" if isinstance(src, ZipSource) else "directory",
            file_count=result.files_total,
            declared_bytes=manifest.total_declared_bytes(),
        )
        store.refs.put(ref)
        result.warnings = warnings
        return result
    finally:
        src.close()
