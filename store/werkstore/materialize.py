"""Materialize a package out of the store - byte-exact, or fail loudly.

This is the module the whole doctrine rests on. Constraint 1: "The
materialized werk is truth. The store dedups, transfers, and remembers - it
never becomes authoritative. Materialization from the store is byte-exact
and verified against the signed manifest, or it failed."

So materialization is two phases that share no state:

  WRITE   - stream every object out of the store into the destination.
  VERIFY  - forget everything we believe and read the RESULT back from
            disk: rehash every file, compare against the manifest's declared
            sha256 and size, rehash MANIFEST.json itself, and re-verify the
            signature chain against the manifest bytes now on disk.

The verify phase deliberately reads the destination, not the store. If it
read the store it would be checking our own bookkeeping against itself - the
tautology the brief warns about ("if any test would pass only because the
store was authoritative, the test is wrong").

A materialization that cannot prove byte-identity raises MaterializeError
and removes the output, because a half-package that looks like a package is
worse than no package.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field

from .errors import MaterializeError, MissingObject
from .manifest import MANIFEST_NAME, SIGNATURE_NAME, Manifest
from .objects import hash_stream
from .signature import ABSENT, INVALID, ChainVerdict, verify_chain
from .store import WerkStore
from .werkpkg import ZipSource, order_entries, preview_prefix_bytes, write_zip


@dataclass
class MaterializeReport:
    manifest_hash: str
    dest: str
    form: str
    files_written: int = 0
    bytes_written: int = 0
    files_verified: int = 0
    signature: "ChainVerdict | None" = None
    preview_prefix_bytes: int = 0
    total_size_bytes: int = 0
    problems: "list[str]" = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    def summary(self) -> str:
        lines = [
            "materialized %s -> %s (%s)" % (self.manifest_hash[:12], self.dest, self.form),
            "  %d files, %d bytes written; %d files rehashed from the RESULT and matched"
            % (self.files_written, self.bytes_written, self.files_verified),
        ]
        if self.signature is not None:
            lines.append("  " + self.signature.summary())
        if self.form == "zip" and self.preview_prefix_bytes:
            lines.append(
                "  preview prefix: %d of %d bytes (%.2f%%) carry the browsable tier"
                % (
                    self.preview_prefix_bytes,
                    self.total_size_bytes,
                    100.0 * self.preview_prefix_bytes / max(1, self.total_size_bytes),
                )
            )
        for p in self.problems:
            lines.append("  PROBLEM: " + p)
        return "\n".join(lines)


def _load_manifest(store: WerkStore, manifest_hash: str) -> Manifest:
    if not store.objects.has(manifest_hash):
        raise MissingObject(manifest_hash, "MANIFEST.json")
    raw = store.objects.read_bytes(manifest_hash)
    manifest = Manifest(raw)
    if manifest.digest != manifest_hash:
        raise MaterializeError(
            "store object %s does not hash to its own name (%s) - the store is "
            "corrupt; run `werkstore scrub`" % (manifest_hash, manifest.digest)
        )
    return manifest


def _missing_objects(store: WerkStore, manifest: Manifest) -> "list[str]":
    missing = []
    for _node, _ver, entry in manifest.iter_files():
        if not store.objects.has(entry.sha256):
            missing.append("%s (%s)" % (entry.path, entry.sha256))
    return sorted(set(missing))


def materialize(
    store: WerkStore,
    manifest_hash: str,
    dest: str,
    form: str = "directory",
    keep_failed: bool = False,
) -> MaterializeReport:
    """Reconstruct the package named by *manifest_hash* at *dest*.

    *form* is "directory" or "zip". Both are the format (SPEC section 1);
    the zip is written store-mode with preview-first entry order.
    """
    if form not in ("directory", "zip"):
        raise ValueError("form must be 'directory' or 'zip'")

    manifest = _load_manifest(store, manifest_hash)
    ref = store.refs.get(manifest_hash)
    sig_hash = ref.signature_hash if ref else None
    sig_bytes = store.objects.read_bytes(sig_hash) if sig_hash else None

    missing = _missing_objects(store, manifest)
    if missing:
        raise MaterializeError(
            "cannot materialize %s: %d object%s missing from the store:\n  %s"
            % (
                manifest_hash,
                len(missing),
                "" if len(missing) == 1 else "s",
                "\n  ".join(missing),
            )
        )

    report = MaterializeReport(manifest_hash=manifest_hash, dest=os.path.abspath(dest), form=form)
    created_root = not os.path.exists(dest)
    try:
        if form == "directory":
            _write_dir(store, manifest, sig_bytes, dest, report)
            _verify_dir(manifest, sig_bytes, dest, report)
        else:
            _write_zip(store, manifest, sig_bytes, dest, report)
            _verify_zip(manifest, dest, report)
    except BaseException:
        if not keep_failed:
            _remove(dest, created_root)
        raise

    if report.problems:
        if not keep_failed:
            _remove(dest, created_root)
        raise MaterializeError(
            "materialization of %s could not prove byte-identity:\n  %s"
            % (manifest_hash, "\n  ".join(report.problems))
        )
    return report


def _remove(dest: str, created_root: bool) -> None:
    if not created_root:
        return
    try:
        if os.path.isdir(dest):
            shutil.rmtree(dest)
        elif os.path.exists(dest):
            os.remove(dest)
    except OSError:
        pass


# ---------------------------------------------------------------------
# directory form
# ---------------------------------------------------------------------


def _write_dir(store, manifest, sig_bytes, dest, report) -> None:
    os.makedirs(dest, exist_ok=True)
    manifest_path = os.path.join(dest, MANIFEST_NAME)
    with open(manifest_path + ".werktmp", "wb") as fh:
        fh.write(manifest.raw)
    os.replace(manifest_path + ".werktmp", manifest_path)
    report.files_written += 1
    report.bytes_written += len(manifest.raw)

    if sig_bytes is not None:
        sig_path = os.path.join(dest, SIGNATURE_NAME)
        with open(sig_path + ".werktmp", "wb") as fh:
            fh.write(sig_bytes)
        os.replace(sig_path + ".werktmp", sig_path)
        report.files_written += 1
        report.bytes_written += len(sig_bytes)

    for path, digest in sorted(manifest.file_map().items()):
        out = os.path.join(dest, *path.split("/"))
        n = store.objects.copy_to(digest, out, verify=True)
        report.files_written += 1
        report.bytes_written += n


def _verify_dir(manifest, sig_bytes, dest, report) -> None:
    """Read the RESULT back and prove it. Nothing here consults the store."""
    for path, digest in sorted(manifest.file_map().items()):
        full = os.path.join(dest, *path.split("/"))
        if not os.path.isfile(full):
            report.problems.append("materialized package is missing %s" % path)
            continue
        with open(full, "rb") as fh:
            actual, size = hash_stream(fh)
        if actual != digest:
            report.problems.append(
                "%s rehashes to %s, manifest declares %s" % (path, actual, digest)
            )
            continue
        report.files_verified += 1

    for _node, _ver, entry in manifest.iter_files():
        full = os.path.join(dest, *entry.path.split("/"))
        if os.path.isfile(full):
            actual = os.path.getsize(full)
            if actual != entry.size:
                report.problems.append(
                    "%s is %d bytes, manifest declares %d" % (entry.path, actual, entry.size)
                )

    manifest_path = os.path.join(dest, MANIFEST_NAME)
    with open(manifest_path, "rb") as fh:
        raw_on_disk = fh.read()
    from .objects import hash_bytes

    if hash_bytes(raw_on_disk) != manifest.digest:
        report.problems.append(
            "MANIFEST.json on disk hashes to %s, expected %s"
            % (hash_bytes(raw_on_disk), manifest.digest)
        )

    sig_path = os.path.join(dest, SIGNATURE_NAME)
    on_disk_sig = None
    if os.path.isfile(sig_path):
        with open(sig_path, "rb") as fh:
            on_disk_sig = fh.read()
    verdict = verify_chain(on_disk_sig, hash_bytes(raw_on_disk))
    report.signature = verdict
    if verdict.state == INVALID:
        report.problems.append(
            "signature chain does not stand on the materialized result: %s"
            % "; ".join(verdict.problems)
        )
    if sig_bytes is not None and verdict.state == ABSENT:
        report.problems.append("package was ingested signed but materialized unsigned")

    # Nothing may float in the result either: a file we wrote that no node
    # claims would mean we produced a different package.
    claimed = set(manifest.file_map())
    claimed.update([MANIFEST_NAME, SIGNATURE_NAME])
    for dirpath, _dirs, names in os.walk(dest):
        for name in names:
            rel = os.path.relpath(os.path.join(dirpath, name), dest).replace(os.sep, "/")
            if rel not in claimed:
                report.problems.append("materialized package contains unclaimed file %s" % rel)


# ---------------------------------------------------------------------
# zip form
# ---------------------------------------------------------------------


def _write_zip(store, manifest, sig_bytes, dest, report) -> None:
    import io

    file_map = manifest.file_map()
    all_paths = list(file_map) + [MANIFEST_NAME]
    if sig_bytes is not None:
        all_paths.append(SIGNATURE_NAME)

    declared_order = manifest.entry_order or [
        MANIFEST_NAME,
        SIGNATURE_NAME,
        "LICENSE",
        "semantics/",
        "imposters/",
    ]
    ordered = order_entries(all_paths, declared_order)

    def opener(path: str):
        if path == MANIFEST_NAME:
            return io.BytesIO(manifest.raw)
        if path == SIGNATURE_NAME and sig_bytes is not None:
            return io.BytesIO(sig_bytes)
        return store.objects.open(file_map[path])

    total = write_zip(dest, ordered, opener, compression=manifest.zip_compression)
    report.files_written = len(ordered)
    report.bytes_written = total
    report.total_size_bytes = total

    # Where the browsable tier actually ends, measured from the archive's own
    # local headers rather than computed from declared sizes. The preview
    # tier is exactly the set named by container.entry_order, and
    # order_entries() guarantees those sit in a contiguous leading run.
    preview_set: "set[str]" = set()
    path_set = set(all_paths)
    for item in declared_order:
        if item in path_set:
            preview_set.add(item)
            continue
        prefix = item if item.endswith("/") else item + "/"
        preview_set.update(p for p in path_set if p.startswith(prefix))
    preview_through = [p for p in ordered if p in preview_set]
    if preview_through:
        report.preview_prefix_bytes = preview_prefix_bytes(dest, preview_through)


def _verify_zip(manifest, dest, report) -> None:
    """Read the RESULT back out of the archive and prove it."""
    from .objects import hash_bytes

    src = ZipSource(dest)
    try:
        present = set(src.paths())
        for path, digest in sorted(manifest.file_map().items()):
            if path not in present:
                report.problems.append("materialized zip is missing %s" % path)
                continue
            with src.open(path) as fh:
                actual, size = hash_stream(fh)
            if actual != digest:
                report.problems.append(
                    "%s rehashes to %s, manifest declares %s" % (path, actual, digest)
                )
                continue
            report.files_verified += 1

        raw_on_disk = src.manifest_bytes()
        if hash_bytes(raw_on_disk) != manifest.digest:
            report.problems.append(
                "MANIFEST.json in zip hashes to %s, expected %s"
                % (hash_bytes(raw_on_disk), manifest.digest)
            )
        verdict = verify_chain(src.signature_bytes(), hash_bytes(raw_on_disk))
        report.signature = verdict
        if verdict.state == INVALID:
            report.problems.append(
                "signature chain does not stand on the materialized zip: %s"
                % "; ".join(verdict.problems)
            )

        claimed = set(manifest.file_map())
        claimed.update([MANIFEST_NAME, SIGNATURE_NAME])
        for path in present:
            if path not in claimed:
                report.problems.append("materialized zip contains unclaimed entry %s" % path)
    finally:
        src.close()
