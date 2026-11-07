"""`werkstore` - the command line face of the store.

Store root resolution, in order: --store, $WERKSTORE, ./.werkstore. Never a
user-profile directory: a store holds project data and belongs beside the
project, not in a hidden corner of a home directory that no backup covers.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile

from .diff import diff_stored
from .errors import WerkStoreError
from .gc import collect, scrub
from .ingest import ingest
from .materialize import _load_manifest, materialize
from .refs import Pin
from .store import WerkStore, now_iso
from .sync import missing_refs, plan as sync_plan, push, sync_all

DEFAULT_STORE = ".werkstore"


def resolve_store(arg: "str | None", create: bool = True) -> WerkStore:
    root = arg or os.environ.get("WERKSTORE") or os.path.join(os.getcwd(), DEFAULT_STORE)
    return WerkStore(root, create=create)


def _resolve_ref(store: WerkStore, spec: str) -> str:
    ref = store.refs.resolve(spec)
    if ref is None:
        from .objects import is_hash

        if is_hash(spec) and store.objects.has(spec):
            return spec  # a manifest object with no ref is still materializable
        raise SystemExit(
            "no package matches %r (try `werkstore ls`; a hash prefix must be unique)"
            % spec
        )
    return ref.manifest_hash


# ---------------------------------------------------------------------


def cmd_init(args) -> int:
    store = resolve_store(args.store)
    print("store ready at %s" % store.root)
    return 0


def cmd_ingest(args) -> int:
    store = resolve_store(args.store)
    if args.no_chunking:
        store.chunk_threshold = None
    result = ingest(
        store,
        args.package,
        strict=not args.allow_floating,
        require_valid_signature=args.require_signature,
    )
    print("ingested %s" % (result.name or result.manifest_hash[:12]))
    print("  manifest %s" % result.manifest_hash)
    print("  entity   %s" % result.entity_uuid)
    print("  %s" % result.signature_state)
    print(
        "  %d file(s): %d new object(s) (%d bytes written), %d deduped (%d bytes not written)"
        % (
            result.files_total,
            result.objects_new,
            result.bytes_written,
            result.objects_deduped,
            result.bytes_deduped,
        )
    )
    if result.files_chunked:
        print(
            "  %d large file(s) stored chunked (CDC): %d chunk(s), %d new"
            % (result.files_chunked, result.chunks_total, result.chunks_new)
        )
    for w in result.warnings:
        print("  WARNING: %s" % w)
    return 0


def cmd_ls(args) -> int:
    store = resolve_store(args.store, create=False)
    rows = list(store.refs.iter_refs())
    if not rows:
        print("(no packages)")
        return 0
    for ref in sorted(rows, key=lambda r: r.ingested_at):
        print(
            "%s  %-28s %-20s %10d files  %s"
            % (
                ref.manifest_hash[:12],
                ref.name[:28],
                ref.signature_state,
                ref.file_count,
                ref.ingested_at,
            )
        )
    return 0


def cmd_show(args) -> int:
    store = resolve_store(args.store, create=False)
    h = _resolve_ref(store, args.ref)
    manifest = _load_manifest(store, h)
    ref = store.refs.get(h)
    print("manifest %s" % h)
    print("entity   %s  %s" % (manifest.entity_uuid, manifest.entity_name))
    if ref:
        print("ingested %s from %s (%s)" % (ref.ingested_at, ref.source, ref.container_form))
        print("signature %s" % ref.signature_state)
    print("nodes    %d" % len(manifest.nodes))
    for node in manifest.nodes:
        print("  %-28s %-22s active=%d" % (node.node_id, node.type, node.active))
        for ver in node.versions:
            mark = "*" if ver.v == node.active else " "
            print(
                "   %s v%-3d %6d file(s) %12d B  [%s]  %s"
                % (mark, ver.v, len(ver.files), ver.total_bytes, ver.epistemic or "?", ver.note)
            )
    return 0


def cmd_log(args) -> int:
    """The changelog is the work notes - already written, already signed."""
    store = resolve_store(args.store, create=False)
    h = _resolve_ref(store, args.ref)
    manifest = _load_manifest(store, h)
    rows = []
    for node in manifest.nodes:
        for ver in node.versions:
            rows.append((ver.created, node.node_id, ver.v, ver.note))
    for created, node_id, v, note in sorted(rows):
        print("%s  %s@%d  %s" % (created or "(undated)", node_id, v, note))
    return 0


def cmd_materialize(args) -> int:
    store = resolve_store(args.store, create=False)
    h = _resolve_ref(store, args.ref)
    form = "zip" if args.zip else "directory"
    report = materialize(store, h, args.dest, form=form, keep_failed=args.keep_failed)
    print(report.summary())
    return 0


def cmd_verify(args) -> int:
    """Materialize to a scratch directory purely to prove it can be done."""
    store = resolve_store(args.store, create=False)
    h = _resolve_ref(store, args.ref)
    tmp_parent = os.path.join(store.root, "tmp")
    os.makedirs(tmp_parent, exist_ok=True)
    scratch = tempfile.mkdtemp(prefix="verify-", dir=tmp_parent)
    dest = os.path.join(scratch, "pkg")
    try:
        report = materialize(store, h, dest, form="directory")
        print(report.summary())
        print("VERIFIED: byte-identity proven by rehashing the materialized result")
        return 0
    finally:
        import shutil

        shutil.rmtree(scratch, ignore_errors=True)


def cmd_diff(args) -> int:
    store = resolve_store(args.store, create=False)
    a = _resolve_ref(store, args.a)
    b = _resolve_ref(store, args.b)
    d = diff_stored(store, a, b)
    print(d.to_json() if args.json else d.to_text())
    return 0


def cmd_sync(args) -> int:
    source = resolve_store(args.store, create=False)
    remote = WerkStore(args.remote, create=True)
    if args.pull:
        source, remote = remote, source
    if args.plan:
        targets = [args.ref] if args.ref else [r.manifest_hash for r in source.refs.iter_refs()]
        for spec in targets:
            print(sync_plan(source, remote, _resolve_ref(source, spec)).summary())
        return 0
    if args.ref:
        print(push(source, remote, _resolve_ref(source, args.ref)).summary())
    else:
        pending = missing_refs(source, remote)
        print("%d package(s) not on the far side" % len(pending))
        for result in sync_all(source, remote):
            print(result.summary())
    return 0


def cmd_gc(args) -> int:
    store = resolve_store(args.store, create=False)
    report = collect(store, dry_run=not args.sweep)
    print(report.summary())
    return 1 if report.refused else 0


def cmd_scrub(args) -> int:
    store = resolve_store(args.store, create=False)
    report = scrub(store, quarantine=not args.no_quarantine)
    print(report.summary())
    return 0 if report.ok else 2


def cmd_pin(args) -> int:
    store = resolve_store(args.store)
    if args.action == "ls":
        for pin in store.refs.iter_pins():
            print("%-24s %d hash(es)  %s" % (pin.name, len(pin.hashes), pin.note))
        return 0
    if args.action == "rm":
        print("removed" if store.refs.remove_pin(args.name) else "no such pin")
        return 0
    store.refs.put_pin(
        Pin(name=args.name, hashes=args.hashes or [], note=args.note or "", created=now_iso())
    )
    print("pinned %s (%d hash(es))" % (args.name, len(args.hashes or [])))
    return 0


def cmd_stats(args) -> int:
    store = resolve_store(args.store, create=False)
    print(json.dumps(store.stats(), indent=2))
    return 0


# ---------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="werkstore",
        description=(
            "Format-aware content-addressed store for werk packages. "
            "The materialized werk is truth; this store is a cache."
        ),
    )
    p.add_argument("--store", help="store root (default $WERKSTORE or ./.werkstore)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="create a store")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("ingest", help="ingest a .werk directory or zip")
    s.add_argument("package")
    s.add_argument("--allow-floating", action="store_true",
                   help="ingest even if files are not claimed by any node version")
    s.add_argument("--require-signature", action="store_true",
                   help="refuse unless the signature chain verifies")
    s.add_argument("--no-chunking", action="store_true",
                   help="store every payload whole, even above the CDC threshold")
    s.set_defaults(func=cmd_ingest)

    s = sub.add_parser("ls", help="list packages")
    s.set_defaults(func=cmd_ls)

    s = sub.add_parser("show", help="show a package's node graph")
    s.add_argument("ref")
    s.set_defaults(func=cmd_show)

    s = sub.add_parser("log", help="the work notes, as the changelog")
    s.add_argument("ref")
    s.set_defaults(func=cmd_log)

    s = sub.add_parser("materialize", help="reconstruct a package, byte-exact")
    s.add_argument("ref")
    s.add_argument("dest")
    s.add_argument("--zip", action="store_true", help="write the zip form instead of a directory")
    s.add_argument("--keep-failed", action="store_true",
                   help="keep the output even if verification failed (forensics)")
    s.set_defaults(func=cmd_materialize)

    s = sub.add_parser("verify", help="prove a package can be materialized byte-exact")
    s.add_argument("ref")
    s.set_defaults(func=cmd_verify)

    s = sub.add_parser("diff", help="manifest-aware diff between two packages")
    s.add_argument("a")
    s.add_argument("b")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_diff)

    s = sub.add_parser("sync", help="have/want sync with another store directory")
    s.add_argument("remote")
    s.add_argument("--ref", help="one package (default: all)")
    s.add_argument("--pull", action="store_true", help="copy from the remote instead of to it")
    s.add_argument("--plan", action="store_true", help="show the negotiation, transfer nothing")
    s.set_defaults(func=cmd_sync)

    s = sub.add_parser("gc", help="sweep objects no root reaches")
    s.add_argument("--sweep", action="store_true", help="actually delete (default is a dry run)")
    s.set_defaults(func=cmd_gc)

    s = sub.add_parser("scrub", help="rehash every object; quarantine the corrupt")
    s.add_argument("--no-quarantine", action="store_true")
    s.set_defaults(func=cmd_scrub)

    s = sub.add_parser("pin", help="manage explicit GC roots")
    s.add_argument("action", choices=["add", "rm", "ls"])
    s.add_argument("name", nargs="?", default="")
    s.add_argument("hashes", nargs="*")
    s.add_argument("--note", default="")
    s.set_defaults(func=cmd_pin)

    s = sub.add_parser("stats", help="object count and footprint")
    s.set_defaults(func=cmd_stats)
    return p


def main(argv: "list[str] | None" = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except WerkStoreError as exc:
        print("werkstore: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
