# werk-store

The companion version control system for werk packages (MANIFESTO.md, "The
Companion"; ROADMAP.md Stage 7).

One sentence governs everything here:

> **The materialized werk is truth.** The store dedups, transfers, and
> remembers — it never becomes authoritative.

Python, zero third-party dependencies, including Ed25519 (RFC 8032 on top of
`hashlib`). A Rust port can follow werk-core later; the store is tooling, not
runtime.

## Install / run

```
cd store
python -m werkstore --help          # no install needed
pip install -e .                    # or install the `werkstore` command
python -m pytest tests -q           # 43 tests, no network, no fixtures in git
python tests/measure_gate.py        # the Stage 7 gate numbers, measured
```

Store root resolution: `--store`, else `$WERKSTORE`, else `./.werkstore`.

## Layout

```
<store>/
  werkstore.json     descriptor; the store has no state that is not a file
  objects/ab/cd/<64-hex>    every byte, content-addressed, nothing inlined
  refs/<manifest-hash>.json package refs — GC roots and human-findable names
  pins/<name>.json          explicit GC roots a ref cannot express
  quarantine/<64-hex>       objects that failed a scrub, kept as evidence
  tmp/                      in-flight writes, always renamed into place
```

## Commands

| command | what it does |
|---|---|
| `ingest <pkg>` | store every payload under its manifest hash, verified while streaming; record a ref |
| `materialize <ref> <dest> [--zip]` | rebuild the package, then prove byte-identity by rehashing the result |
| `verify <ref>` | materialize to scratch purely to prove it can be done |
| `diff <a> <b> [--json]` | node-version-granular diff; the changelog is the work notes |
| `log <ref>` | the work notes, in time order |
| `sync <remote> [--ref R] [--plan] [--pull]` | have/want negotiation over a directory transport |
| `gc [--sweep]` | multi-root, pin-aware sweep (dry run by default) |
| `scrub [--no-quarantine]` | rehash every object; quarantine the corrupt |
| `pin add/rm/ls` | explicit roots |
| `ls` / `show` / `stats` | what is in here |

## The six constraints, and where each one lives

1. **The materialized werk is truth** — `materialize.py`. Write and verify
   are separate phases and the verify phase reads the *destination*, never
   the store. If it read the store it would be checking our bookkeeping
   against itself. Materialization that cannot prove byte-identity raises
   and removes its own output.
2. **Content addressing is shared** — `objects.py`. The manifest's per-file
   sha256 *is* the object name. There is no translation layer, no id table,
   no second namespace to drift.
3. **Diff is manifest-aware** — `diff.py`. The unit of change is the node
   version. A 43 MB GLB that changed is one line, because the interesting
   part (*why*) is the work note law 6 already required the author to write.
4. **Sync is node-version-granular** — `sync.py`. have/want over hashes,
   only missing objects move, and resumability is a consequence of content
   addressing rather than a feature with a journal to corrupt.
5. **Cross-package redundancy lives here and only here** — dedup by whole
   blob today; CDC chunking and packing are the next layer and belong here,
   never in the format.
6. **GC is multi-rooted and pin-aware, with integrity scrub** — `gc.py`.
   Roots are every file of *every version* of every node of every ref, plus
   pins. If a root cannot be read, GC sweeps **nothing**: an unknown
   reachable set makes every deletion a guess.

## Deliberate non-inheritances from the donor

Descended from VLocalZ `backend/vcs/content_store.py` and
`backend/data/manifold_content.py` (sha256 keys, ab/cd fanout, tmp+rename,
GC skeleton, envelope discipline). Four of its defects are refused on
purpose:

- **inline tiering** — no size threshold, no second storage path to
  disagree with the first. Everything is content-addressed.
- **UTF-8-only plumbing** — nothing here decodes a payload, ever. Only the
  manifest and the chain are parsed, and their raw bytes stay authoritative.
- **single-root GC** — see constraint 6.
- **DB-is-truth** — there is no database. Truth is the materialized werk;
  the store's own state is files, and `scrub` exists to prove them.
- **lossy materializer** — materialization is byte-exact or it fails.

## Test discipline

No test may pass only because the store was authoritative. Every round-trip
assertion compares the materialized result against the **original package on
disk**, and the signature chain is verified against the manifest bytes that
came back. `test_roundtrip.py` includes the inverse case explicitly: rot one
object inside the store and materialization must fail loudly rather than
hand over plausible bytes.

The Ed25519 implementation is checked against the RFC 8032 §7.1 vectors
before any werk-specific test is allowed to trust it.
