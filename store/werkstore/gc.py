"""Multi-root, pin-aware garbage collection, and integrity scrub.

Constraint 6: "GC is multi-rooted and pin-aware, with integrity scrub; a
store that cannot verify every blob rehashes to its name is broken."

Multi-rooted matters more than it sounds. The donor store had a single root
(one table column) and would happily delete a blob that a second kind of
reference still needed. Here the root set is the union of:

  * every package ref - and for each, the manifest object, the signature
    object, and EVERY file of EVERY version of EVERY node. Not just the
    active version: law 6 says a regression is fixed by pointing back in
    seconds, and a GC that swept inactive versions would turn that into a
    restore-from-backup.
  * every explicit pin.

The safety rule that makes this trustworthy: **if a root cannot be read, GC
sweeps nothing.** An unreadable manifest means an unknown reachable set, and
an unknown reachable set means every deletion is a guess. Refusing is the
only honest option.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from .manifest import Manifest
from .objects import hash_stream
from .store import WerkStore


@dataclass
class Roots:
    hashes: "set[str]" = field(default_factory=set)
    live_recipes: "set[str]" = field(default_factory=set)  # whole-hashes whose recipe is rooted
    from_refs: int = 0
    from_pins: int = 0
    broken_refs: "list[str]" = field(default_factory=list)
    missing: "list[str]" = field(default_factory=list)  # rooted but not in the store


def compute_roots(store: WerkStore) -> Roots:
    """Every object reachable from every ref and every pin."""
    roots = Roots()
    for ref in store.refs.iter_refs():
        try:
            raw = store.objects.read_bytes(ref.manifest_hash)
            manifest = Manifest(raw)
        except Exception as exc:
            roots.broken_refs.append("%s: %s" % (ref.manifest_hash, exc))
            continue
        roots.hashes.add(ref.manifest_hash)
        if ref.signature_hash:
            roots.hashes.add(ref.signature_hash)
        for _node, _ver, entry in manifest.iter_files():
            roots.hashes.add(entry.sha256)
        roots.from_refs += 1

    for pin in store.refs.iter_pins():
        for h in pin.hashes:
            roots.hashes.add(h)
        roots.from_pins += 1

    # Chunk expansion: a rooted hash stored chunked reaches its recipe and
    # every chunk. The recipe is part of how the store keeps its promise for
    # that hash, so its chunks are as rooted as the whole would be.
    for h in list(roots.hashes):
        recipe = store.objects.chunk_recipe(h)
        if recipe is not None:
            roots.live_recipes.add(h)
            for chunk_hash, _size in recipe.chunks:
                roots.hashes.add(chunk_hash)

    roots.missing = sorted(h for h in roots.hashes if not store.objects.has(h))
    return roots


@dataclass
class GCReport:
    live: int = 0
    live_bytes: int = 0
    swept: int = 0
    swept_bytes: int = 0
    live_recipes: int = 0
    swept_recipes: int = 0
    dry_run: bool = False
    refused: "str | None" = None
    broken_refs: "list[str]" = field(default_factory=list)
    missing_rooted: "list[str]" = field(default_factory=list)
    swept_hashes: "list[str]" = field(default_factory=list)

    def summary(self) -> str:
        if self.refused:
            return "gc REFUSED: %s" % self.refused
        verb = "would sweep" if self.dry_run else "swept"
        lines = [
            "gc: %d live object(s), %d bytes; %s %d object(s), %d bytes"
            % (self.live, self.live_bytes, verb, self.swept, self.swept_bytes)
        ]
        if self.live_recipes or self.swept_recipes:
            lines.append(
                "  chunk recipes: %d live, %s %d"
                % (self.live_recipes, verb, self.swept_recipes)
            )
        for m in self.missing_rooted:
            lines.append("  MISSING (rooted but absent): %s" % m)
        return "\n".join(lines)


def collect(store: WerkStore, dry_run: bool = True) -> GCReport:
    """Sweep every object no root reaches."""
    roots = compute_roots(store)
    report = GCReport(dry_run=dry_run, broken_refs=roots.broken_refs, missing_rooted=roots.missing)

    if roots.broken_refs:
        report.refused = (
            "%d package ref(s) could not be read, so their reachable sets are "
            "unknown and no deletion can be proven safe:\n  %s"
            % (len(roots.broken_refs), "\n  ".join(roots.broken_refs))
        )
        return report

    for digest in list(store.objects.iter_hashes()):
        size = os.path.getsize(store.objects.path_for(digest))
        if digest in roots.hashes:
            report.live += 1
            report.live_bytes += size
            continue
        report.swept += 1
        report.swept_bytes += size
        report.swept_hashes.append(digest)
        if not dry_run:
            store.objects.remove(digest)

    # Recipes are reachable exactly when their whole-hash is: an orphan
    # recipe describes an object no root wants, and its chunks (unless a
    # live recipe or a root also claims them) were swept above.
    for digest in list(store.objects.iter_recipe_hashes()):
        size = os.path.getsize(store.objects.recipe_path(digest))
        if digest in roots.hashes:
            report.live_recipes += 1
            report.live_bytes += size
            continue
        report.swept_recipes += 1
        report.swept_bytes += size
        if not dry_run:
            store.objects.remove_recipe(digest)
    return report


@dataclass
class ScrubReport:
    checked: int = 0
    bytes_checked: int = 0
    recipes_checked: int = 0
    recipe_bytes_checked: int = 0  # reassembled bytes rehashed against whole hashes
    corrupt: "list[dict]" = field(default_factory=list)
    bad_recipes: "list[str]" = field(default_factory=list)
    quarantined: "list[str]" = field(default_factory=list)
    missing_rooted: "list[str]" = field(default_factory=list)
    unreadable: "list[str]" = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return (
            not self.corrupt
            and not self.bad_recipes
            and not self.missing_rooted
            and not self.unreadable
        )

    def summary(self) -> str:
        lines = [
            "scrub: %d object(s), %d bytes rehashed" % (self.checked, self.bytes_checked)
        ]
        if self.corrupt:
            lines.append("  CORRUPT (%d):" % len(self.corrupt))
            for c in self.corrupt:
                lines.append(
                    "    filed as %s but hashes to %s (%d bytes)%s"
                    % (
                        c["expected"],
                        c["actual"],
                        c["size"],
                        " -> quarantined at " + c["quarantined"] if c.get("quarantined") else "",
                    )
                )
        if self.recipes_checked:
            lines.append(
                "  chunk recipes: %d reassembled and rehashed (%d bytes)"
                % (self.recipes_checked, self.recipe_bytes_checked)
            )
        for b in self.bad_recipes:
            lines.append("  BAD RECIPE: %s" % b)
        for m in self.missing_rooted:
            lines.append("  MISSING (a package ref needs it and it is not here): %s" % m)
        for u in self.unreadable:
            lines.append("  UNREADABLE: %s" % u)
        if self.ok:
            lines.append("  every object rehashes to its own name")
        return "\n".join(lines)


def scrub(store: WerkStore, quarantine: bool = True) -> ScrubReport:
    """Rehash every object; quarantine anything that does not match its name.

    This is the check that makes the store's promise falsifiable. It reads
    the bytes on disk and recomputes - it consults no index, no cached size,
    no database, because every one of those would be a way for the store to
    agree with itself while being wrong.
    """
    report = ScrubReport()
    for digest in list(store.objects.iter_hashes()):
        path = store.objects.path_for(digest)
        try:
            size = os.path.getsize(path)
            with open(path, "rb") as fh:
                actual, streamed = hash_stream(fh)
        except OSError as exc:
            report.unreadable.append("%s (%s)" % (digest, exc))
            continue
        report.checked += 1
        report.bytes_checked += size
        if actual != digest:
            record = {"expected": digest, "actual": actual, "size": streamed}
            if quarantine:
                dest = store.objects.quarantine(digest, store.quarantine_dir)
                record["quarantined"] = dest
                report.quarantined.append(dest)
            report.corrupt.append(record)

    # Recipes get the same falsifiability: reassemble every chunked object
    # through its recipe and rehash against the WHOLE-file name. A corrupt
    # chunk was already caught above (it is an object); this catches the
    # recipe itself lying - wrong order, wrong chunk, wrong count. A bad
    # recipe is quarantined like any other corrupt evidence; its chunks are
    # left alone because each still rehashes to its own name.
    import hashlib as _hashlib

    for digest in list(store.objects.iter_recipe_hashes()):
        path = store.objects.recipe_path(digest)
        try:
            with open(path, "rb") as fh:
                raw = fh.read()
            from .chunking import Recipe

            recipe = Recipe.from_json(raw)
            recipe.check()
            if recipe.whole_sha256 != digest:
                raise ValueError(
                    "filed under %s but declares whole_sha256=%s"
                    % (digest, recipe.whole_sha256)
                )
        except Exception as exc:
            report.bad_recipes.append("%s: %s" % (digest, exc))
            if quarantine:
                dest = os.path.join(store.quarantine_dir, digest + ".recipe.json")
                os.makedirs(store.quarantine_dir, exist_ok=True)
                try:
                    os.replace(path, dest)
                    report.quarantined.append(dest)
                except OSError:
                    pass
            continue
        h = _hashlib.sha256()
        streamed = 0
        problem = None
        for chunk_hash, _size in recipe.chunks:
            try:
                with store.objects.open_whole(chunk_hash) as fh:
                    while True:
                        piece = fh.read(1 << 20)
                        if not piece:
                            break
                        h.update(piece)
                        streamed += len(piece)
            except Exception as exc:
                problem = "chunk %s unreadable (%s)" % (chunk_hash, exc)
                break
        report.recipes_checked += 1
        report.recipe_bytes_checked += streamed
        if problem is None and h.hexdigest() != digest:
            problem = "chunks reassemble to %s, recipe promises %s" % (
                h.hexdigest(),
                digest,
            )
        if problem is not None:
            report.bad_recipes.append("%s: %s" % (digest, problem))
            if quarantine:
                dest = os.path.join(store.quarantine_dir, digest + ".recipe.json")
                os.makedirs(store.quarantine_dir, exist_ok=True)
                try:
                    os.replace(path, dest)
                    report.quarantined.append(dest)
                except OSError:
                    pass

    roots = compute_roots(store)
    report.missing_rooted = roots.missing
    return report
