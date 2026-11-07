"""Node-version-granular sync over a dumb transport.

Constraint 4: "Sync is node-version-granular: have/want negotiation over
hashes, transferring only missing objects, resumable."

The transport here is a filesystem path - a local directory, a network
share, an SSH-mounted remote store. That is deliberate. There is no wire
protocol yet because a wire protocol is an optimisation, and correctness
comes first; anything that can present a directory can be a werk remote
today, and the negotiation below is the same negotiation a socket would
carry tomorrow.

Resumability is not a feature here, it is a consequence: objects are
content-addressed and written tmp+rename, so an interrupted transfer leaves
either a complete correct object or nothing. Running the same sync again
transfers exactly what is still missing. There is no journal to corrupt.

The unit of the plan is the NODE VERSION, not the file and not the package:
that is the unit an author actually changed, the unit the work note explains,
and therefore the unit a human should be told about.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import MissingObject
from .manifest import MANIFEST_NAME, SIGNATURE_NAME, Manifest
from .store import WerkStore


@dataclass
class VersionNeed:
    """What one node version still needs on the receiving side."""

    node_id: str
    node_type: str
    v: int
    note: str
    objects: "list[str]" = field(default_factory=list)
    bytes: int = 0

    @property
    def needed(self) -> bool:
        return bool(self.objects)


@dataclass
class SyncPlan:
    manifest_hash: str
    name: str = ""
    versions: "list[VersionNeed]" = field(default_factory=list)
    extra_objects: "list[str]" = field(default_factory=list)  # manifest, signature
    recipes: "list[str]" = field(default_factory=list)  # whole-hashes to install chunked
    have_objects: int = 0
    have_bytes: int = 0
    chunk_bytes_reused: int = 0  # bytes of chunked files already on the far side
    chunks_reused: int = 0

    def want(self) -> "list[str]":
        """Every object hash the receiver is missing, deduped, in plan order."""
        seen: "set[str]" = set()
        out: "list[str]" = []
        for need in self.versions:
            for h in need.objects:
                if h not in seen:
                    seen.add(h)
                    out.append(h)
        for h in self.extra_objects:
            if h not in seen:
                seen.add(h)
                out.append(h)
        return out

    @property
    def want_bytes(self) -> int:
        return sum(n.bytes for n in self.versions)

    def summary(self) -> str:
        needed = [n for n in self.versions if n.needed]
        lines = [
            "sync plan for %s (%s)" % (self.manifest_hash[:12], self.name or "unnamed"),
            "  receiver already has %d object(s), %d bytes"
            % (self.have_objects, self.have_bytes),
            "  %d node version(s) need bytes:" % len(needed),
        ]
        for n in needed:
            lines.append(
                "    %s@%d  %d object(s), %d bytes  - %s"
                % (n.node_id, n.v, len(n.objects), n.bytes, n.note)
            )
        if not needed:
            lines.append("    (none - the receiver is already up to date)")
        return "\n".join(lines)


@dataclass
class SyncResult:
    manifest_hash: str
    objects_copied: int = 0
    bytes_copied: int = 0
    objects_skipped: int = 0
    bytes_skipped: int = 0
    recipes_written: int = 0
    chunks_reused: int = 0
    chunk_bytes_reused: int = 0
    ref_written: bool = False

    def summary(self) -> str:
        text = (
            "synced %s: %d object(s)/%d bytes copied, %d object(s)/%d bytes "
            "already present"
            % (
                self.manifest_hash[:12],
                self.objects_copied,
                self.bytes_copied,
                self.objects_skipped,
                self.bytes_skipped,
            )
        )
        if self.recipes_written:
            text += "; %d chunk recipe(s) installed (%d chunk(s)/%d bytes reused in place)" % (
                self.recipes_written,
                self.chunks_reused,
                self.chunk_bytes_reused,
            )
        if self.ref_written:
            text += "; ref written"
        return text


def plan(source: WerkStore, dest: WerkStore, manifest_hash: str) -> SyncPlan:
    """Compute the have/want negotiation for one package, node version by node version."""
    from .materialize import _load_manifest

    manifest: Manifest = _load_manifest(source, manifest_hash)
    ref = source.refs.get(manifest_hash)

    out = SyncPlan(manifest_hash=manifest_hash, name=manifest.entity_name)
    seen_in_plan: "set[str]" = set()

    for node in manifest.nodes:
        for version in node.versions:
            need = VersionNeed(
                node_id=node.node_id, node_type=node.type, v=version.v, note=version.note
            )
            for entry in version.files:
                if dest.objects.has(entry.sha256):
                    out.have_objects += 1
                    out.have_bytes += entry.size
                    continue
                if entry.sha256 in seen_in_plan:
                    continue  # a blob shared between versions travels once
                seen_in_plan.add(entry.sha256)
                # If the source holds this file CHUNKED, negotiate at chunk
                # granularity: only the chunks the far side lacks travel,
                # plus the recipe. An edited 5 MB payload whose neighbour
                # version is already over there costs its changed chunks.
                recipe = source.objects.chunk_recipe(entry.sha256)
                if recipe is not None:
                    if entry.sha256 not in out.recipes:
                        out.recipes.append(entry.sha256)
                    for chunk_hash, chunk_size in recipe.chunks:
                        if dest.objects.has_whole(chunk_hash):
                            out.chunks_reused += 1
                            out.chunk_bytes_reused += chunk_size
                            continue
                        if chunk_hash in seen_in_plan:
                            continue
                        seen_in_plan.add(chunk_hash)
                        need.objects.append(chunk_hash)
                        need.bytes += chunk_size
                    continue
                need.objects.append(entry.sha256)
                need.bytes += entry.size
            out.versions.append(need)

    # The manifest and the chain are objects too, and the package is not
    # transferable without them.
    for extra, label in ((manifest_hash, MANIFEST_NAME), (ref.signature_hash if ref else None, SIGNATURE_NAME)):
        if extra and not dest.objects.has(extra):
            out.extra_objects.append(extra)
        elif extra:
            out.have_objects += 1
            out.have_bytes += source.objects.size(extra)
    return out


def push(source: WerkStore, dest: WerkStore, manifest_hash: str) -> SyncResult:
    """Copy one package from *source* into *dest*, transferring only what is missing.

    Every object is re-verified on arrival: put_stream is given the hash it
    must produce, so a transport that corrupts a byte is caught by the
    receiver rather than trusted because the sender said so.
    """
    p = plan(source, dest, manifest_hash)
    result = SyncResult(manifest_hash=manifest_hash)
    result.objects_skipped = p.have_objects
    result.bytes_skipped = p.have_bytes

    for digest in p.want():
        if dest.objects.has(digest):  # another process may have raced us there
            result.objects_skipped += 1
            result.bytes_skipped += dest.objects.size(digest)
            continue
        if not source.objects.has(digest):
            raise MissingObject(digest, "sync of %s" % manifest_hash)
        with source.objects.open(digest) as fh:
            put = dest.objects.put_stream(fh, expect=digest, source="sync:%s" % digest)
        if put.deduped:
            result.objects_skipped += 1
            result.bytes_skipped += put.size
        else:
            result.objects_copied += 1
            result.bytes_copied += put.size

    # Install the recipes for files that travelled chunked, so the receiver
    # can answer for the WHOLE-file hash. Each chunk was verified against
    # its own name on arrival (put_stream with expect); the reassembly is
    # proven whole-file at materialize time, which fails loudly - and
    # `werkstore scrub` on the receiver reproves it any day of the week.
    for whole_hash in p.recipes:
        recipe = source.objects.chunk_recipe(whole_hash)
        if recipe is None:  # raced away on the source; the object must exist whole
            if not dest.objects.has(whole_hash):
                raise MissingObject(whole_hash, "sync of %s" % manifest_hash)
            continue
        missing_chunks = [h for h, _s in recipe.chunks if not dest.objects.has_whole(h)]
        if missing_chunks:
            raise MissingObject(missing_chunks[0], "sync of %s (chunk of %s)" % (manifest_hash, whole_hash))
        dest.objects.put_recipe(recipe)
        result.recipes_written += 1
    result.chunks_reused = p.chunks_reused
    result.chunk_bytes_reused = p.chunk_bytes_reused

    ref = source.refs.get(manifest_hash)
    if ref is not None:
        dest.refs.put(ref)
        result.ref_written = True
    return result


def pull(local: WerkStore, remote: WerkStore, manifest_hash: str) -> SyncResult:
    """Copy one package from *remote* into *local*. Same negotiation, reversed."""
    return push(remote, local, manifest_hash)


def sync_all(source: WerkStore, dest: WerkStore) -> "list[SyncResult]":
    """Push every package ref the source has. Idempotent; safe to re-run."""
    results = []
    for ref in source.refs.iter_refs():
        results.append(push(source, dest, ref.manifest_hash))
    return results


def missing_refs(source: WerkStore, dest: WerkStore) -> "list[str]":
    """Manifest hashes the source has and the destination does not."""
    have = {r.manifest_hash for r in dest.refs.iter_refs()}
    return [r.manifest_hash for r in source.refs.iter_refs() if r.manifest_hash not in have]
