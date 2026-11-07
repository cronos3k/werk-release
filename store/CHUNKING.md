# werkstore content-defined chunking (CDC) — `fastcdc-gear64-v1`

This document is normative for the werkstore chunk layer. It specifies the
algorithm exactly — table generation, fingerprint update, masks, the cut
rule, the storage layout and the recipe format — so that a foreign
implementation, given the same bytes, produces the same chunk boundaries,
the same chunk hashes and the same recipe. A test vector at the end makes
that claim checkable rather than believable.

Reference implementation: `store/werkstore/chunking.py` (stdlib-only
Python, like all of werkstore).

## 0. What chunking is, and what it is not

Chunking is an **internal representation of the store**. It is invisible to
the werk format:

* No `.werk` file ever contains a chunk boundary, a chunk hash or a recipe.
* A chunked object still answers to its **whole-file sha256** — the same
  digest the manifest declares. There is no second naming scheme.
* Materialization reassembles the chunks and then **rehashes the result
  against the manifest's sha256**, exactly as it does for whole objects.
  The byte-exactness invariant is proven on every materialization, never
  assumed from bookkeeping. A store whose chunks cannot reassemble to the
  declared hash fails loudly and leaves nothing behind.

The point: whole-blob dedup pays nothing when a 43 MB GLB has one vertex
moved. Content-defined boundaries make an edit cost the chunk(s) it
touched, across versions and across unrelated packages that share bytes.

## 1. Layout

```
<store>/
  objects/<h[0:2]>/<h[2:4]>/<h>          objects — whole payloads AND chunks
  chunks/<H[0:2]>/<H[2:4]>/<H>.json      recipe for the object whose
                                         WHOLE-file sha256 is H
```

Chunks are ordinary CAS objects named by their own sha256; nothing about a
chunk marks it as one. A recipe is a small JSON file, fanned out by the
whole-file hash it reconstructs, `.json` suffix so the two trees cannot be
confused.

An object may legally exist in **both** forms at once (stored whole before
chunking existed, chunked by a later ingest elsewhere and synced in). Both
answer to the same hash; readers prefer the whole form when present.

**Migration is the absence of change**: a store from before this document
simply has no `chunks/` directory. Every operation on it behaves exactly as
before; chunking applies to new ingests only, and a mixed store (whole old
objects, chunked new ones) is the normal steady state, handled by ingest,
materialize, sync, gc and scrub alike.

## 2. Parameters (normative)

| name | value | meaning |
|---|---|---|
| `ALGORITHM` | `fastcdc-gear64-v1` | names everything in this document |
| `MIN_SIZE` | 65536 (64 KiB) | no cut before this many bytes; also: the first `MIN_SIZE` bytes of each chunk are never hashed into the fingerprint |
| `AVG_SIZE` | 262144 (256 KiB) | the normalization point (2^18) |
| `MAX_SIZE` | 1048576 (1 MiB) | forced cut; no chunk is ever larger |
| `MASK_S` | `0xFFFFF00000000000` | 20 one-bits, tested **before** `AVG_SIZE` |
| `MASK_L` | `0xFFFF000000000000` | 16 one-bits, tested **from** `AVG_SIZE` on |
| threshold | 2097152 (2 MiB) | only objects at or above this size are chunked (section 5) |

All fingerprint arithmetic is unsigned 64-bit, modulo 2^64. The masks test
the **top** bits of the fingerprint because Gear's left-shift update pushes
its mixing toward the high bits; testing low bits would test mostly the
newest byte.

Changing any parameter changes every boundary. A change is a new
`ALGORITHM` string, and every recipe records the algorithm and sizes it was
cut with, so a store can carry recipes from two algorithm generations
without ambiguity.

## 3. The gear table (normative)

256 entries, one per byte value, generated — not tabulated — from SHA-256:

```
gear[b] = uint64_be( SHA256( b"werk-cdc-gear-v1" || byte(b) )[0:8] )
```

that is: hash the 17-byte string consisting of the ASCII seed
`werk-cdc-gear-v1` followed by the single byte `b`; take the first 8 bytes
of the digest; interpret them as a big-endian unsigned 64-bit integer.

Spot values a foreign implementation must reproduce:

```
gear[0]   = 0xe845c0caaeca9317
gear[1]   = 0xd690296a6c7cac90
gear[255] = 0xe2469bee8245a8f2
```

## 4. The cut rule (normative)

Given a window `data` that holds either at least `MAX_SIZE` bytes or the
entire remainder of the stream, the length of the next chunk is:

```
cut(data):
    n = min(len(data), MAX_SIZE)
    if n <= MIN_SIZE:            # remainder smaller than a minimum chunk
        return n
    center = AVG_SIZE if n > AVG_SIZE else n
    fp = 0
    i = MIN_SIZE                 # bytes [0, MIN_SIZE) are skipped entirely
    while i < center:            # the "hard" phase: longer chunks favoured
        fp = ((fp << 1) + gear[data[i]]) mod 2^64
        if fp AND MASK_S == 0:
            return i + 1
        i += 1
    while i < n:                 # the "easy" phase: catch up quickly
        fp = ((fp << 1) + gear[data[i]]) mod 2^64
        if fp AND MASK_L == 0:
            return i + 1
        i += 1
    return n                     # forced cut at MAX_SIZE (or EOF)
```

Notes that matter for byte-compatibility:

* `fp` starts at 0 for **every chunk** and is **not** reset between the two
  phases.
* The byte at index `i` is consumed **before** the test; a hit at index `i`
  makes the chunk `i + 1` bytes long.
* `center` is the position where the mask switches, clamped to `n` when the
  window is short; when `n <= AVG_SIZE` only the hard phase runs.
* The whole file is chunked by applying `cut` repeatedly to the remaining
  stream. Boundaries depend only on the byte stream, never on read sizes or
  buffering. Scanning is strictly left-to-right, so a boundary found inside
  a full window is final.
* A file of `MIN_SIZE` or fewer remaining bytes yields one final chunk of
  that size; the **last chunk of a file is the only chunk allowed to be
  smaller than `MIN_SIZE`**.

Expected chunk size under these parameters is roughly 300 KiB on
incompressible data (measured 14 chunks over the 4 MiB test vector below).

## 5. The threshold (measured, then fixed)

Only objects of **2 MiB or more** (by the manifest's declared size) are
chunked; smaller objects are stored whole, exactly as before.

Why 2 MiB — measured with `store/tests/measure_gate_cdc.py` (threshold
section), not asserted: a chunked file pays a recipe (~80 bytes per chunk)
plus per-chunk object overhead, and buys edit granularity of one average
chunk. Below ~1 MiB a file yields only 2–4 chunks, so the finest thing an
edit can cost is a large fraction of the file — nearly the whole-blob
price, while the overhead and the extra objects are already being paid. At
2 MiB (8× `AVG_SIZE`) a file yields ~7+ chunks and a small edit reliably
costs a small fraction. The gate prints the measured table (chunks and
overhead per size) on every run.

The threshold is a store-side policy knob (`WerkStore(chunk_threshold=…)`,
`werkstore ingest --no-chunking`), not part of the algorithm: two stores
with different thresholds still agree on every boundary of every object
they both chunked. Changing it never breaks an existing store — recipes
already written keep working, whole objects stay whole.

## 6. The recipe (normative)

One JSON document per chunked object, stored at
`chunks/<H[0:2]>/<H[2:4]>/<H>.json` where `H` is the whole-file sha256,
lowercase hex. Serialized with sorted keys, minimal separators
(`,` and `:`), ASCII, one trailing LF:

```json
{"algorithm":"fastcdc-gear64-v1",
 "avg_size":262144,
 "chunks":[["<chunk sha256>",<chunk size>], ...],
 "max_size":1048576,
 "min_size":65536,
 "werkstore_recipe":1,
 "whole_sha256":"<H>",
 "whole_size":<total bytes>}
```

`chunks` lists `[sha256, size]` pairs **in stream order**; concatenating
the named objects in that order MUST reproduce exactly `whole_size` bytes
hashing to `whole_sha256`. `sum(sizes) == whole_size` is a structural
requirement checked on read and write. The recipe is bookkeeping, not
truth: it is not content-addressed, and everything it promises is reproved
by rehashing the reassembled bytes at materialization and by
`werkstore scrub`.

## 7. How each operation treats chunked objects

* **ingest** — payloads with declared size ≥ threshold stream through the
  chunker; each chunk is stored (and deduped) as an ordinary object; the
  whole-file sha256 is computed over the same pass and checked against the
  manifest's declared hash **before** the recipe is written. A mismatch is
  the same refusal as ever, and the chunks this ingest added are removed —
  nothing of a refused ingest enters the store.
* **materialize** — `open`/`copy_to` are representation-transparent: a
  chunked object streams reassembled. The verify phase rereads the
  destination and rehashes every file against the manifest, so chunking
  cannot weaken the byte-exactness proof even in principle.
* **sync** — negotiation drops to chunk granularity: for a wanted file held
  chunked by the sender, only the chunks the receiver lacks travel (each
  verified against its own hash on arrival), then the recipe is installed.
  An edited file whose previous version the receiver already has costs its
  changed chunks.
* **gc** — a rooted whole-file hash roots its recipe and every chunk the
  recipe names. Orphan recipes are swept with their unshared chunks; shared
  chunks survive on the strength of whichever recipe or root still needs
  them. The refuse-if-a-root-is-unreadable rule is unchanged.
* **scrub** — chunks are objects and are rehashed like any object. Recipes
  are additionally reproved end to end: chunks are streamed in order and
  the concatenation is rehashed against the whole-file name; a lying recipe
  is quarantined (never deleted — evidence), its chunks left alone because
  each still answers to its own name.

## 8. Test vector

Input: 4 MiB (4194304 bytes) of deterministic keystream

```
data = concat( SHA256( b"werk-cdc-test-vector-v1" || uint64_be(i) )  for i = 0,1,2,... )
```

truncated to 4194304 bytes (i.e. 131072 whole 32-byte blocks).

```
sha256(data) = 8adb1ba530a42022b67f5a8a7eec17a134694a7bd33107fcbcf25a9a6ed77a6b
```

Chunking `data` with the parameters above MUST produce exactly these 14
chunks, in this order:

| # | size | sha256 |
|---|---|---|
| 0 | 302199 | `ae072e57601b04b202a94e61b72b0a8664302c3a2ba89e24fb8e2f9012086a7a` |
| 1 | 353580 | `bfeed62493bb916ed4ea2a560ce95c821dc875b01dd053e7d4e97a04290dfcae` |
| 2 | 211227 | `6d097ccff8f3992f7b800ad155da7267e87cbfeecc0185ee94bba1b75f30497f` |
| 3 | 370589 | `f44d6fdb0801c1ee65fac38bcdba0d696f21bdbe3fa7ef414f2d619dc99e2dd1` |
| 4 | 275527 | `36d2364eee6ea411d7e0272332fa01128343698a8bc8c283565bb9efb490b26e` |
| 5 | 449179 | `057f402f51f5436c7dd6520a702c8e0bd3c849c8c548ffda235a195413eb9ff3` |
| 6 | 321334 | `6e360c0dc9b000edfa9e63633dfe1cf01a92fa1aa9db49cfddccb91a12279892` |
| 7 | 323021 | `2129fcb4f925ca49c27ce929c1a42f5f4733effce3b22bbc3f3c305ede1c837b` |
| 8 | 332888 | `78e645da7f161d96b5f835480644586165195a7257d416c2fb46ce2b2bfd01f7` |
| 9 | 362134 | `4f140c7493f0d42cf99f30f75f78198bf6526b4ba6edbd2b18a97b7097478a5f` |
| 10 | 320605 | `3bb6228e16a199c7fbaa0a3ccbfb59f4d4010c28fea04d79a967a37924532a65` |
| 11 | 269656 | `2980cc09c2ae378906d2f28cb980ffefff61b795fd5e263c654eced452f179d9` |
| 12 | 268089 | `1294e43fc8208f7eb841d49fffcf84c8a1cd1de06ae5392a884e55ef44a2bbe2` |
| 13 | 34276 | `82093726d1519f31b1009ebfadf881c208319cec3883818cba5deb8722329f80` |

Sizes sum to 4194304. Every chunk except the last is within
`[MIN_SIZE, MAX_SIZE]`; the last is 34276 bytes (the tail rule).

Edit-stability property the tests assert on the same data: overwriting
bytes `[2097152, 2101248)` (4096 bytes) with `0xAA` changes **1 of 14**
chunks; the other 13 keep their hashes.

`store/tests/test_chunking.py::test_chunking_matches_the_published_vector`
asserts this table verbatim; an implementation in any language that
reproduces it is boundary-compatible.
