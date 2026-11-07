"""Content-defined chunking (CDC) - sub-file dedup for large payloads.

Whole-blob dedup pays nothing when a 43 MB GLB has one vertex moved: the
store writes another 43 MB. CDC cuts a large payload at positions chosen by
the CONTENT (a rolling hash), so an edit disturbs only the chunk(s) it
touches and every other chunk keeps its hash - across versions AND across
unrelated werk files that happen to share bytes.

The algorithm is FastCDC-style Gear chunking with normalized chunk sizes.
It is specified EXACTLY, byte for byte, in store/CHUNKING.md so a foreign
implementation can reproduce identical boundaries; this module is the
reference implementation, and CHUNKING.md carries the test vector the unit
tests assert.

Doctrine unchanged (constraint 1): chunks are an internal representation of
the store, invisible to the format. A chunked object still answers to its
WHOLE-file sha256 - the manifest's hash - and materialization still rehashes
the reassembled result against that hash, so byte-exactness stays proven,
never assumed. No werk file ever contains a chunk boundary.

Stdlib only, like everything else in werkstore.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterator

# ---------------------------------------------------------------------
# Parameters - normative; see store/CHUNKING.md section 2.
# Changing any of these changes every boundary, so they are versioned
# through ALGORITHM and recorded in every recipe.
# ---------------------------------------------------------------------

ALGORITHM = "fastcdc-gear64-v1"

MIN_SIZE = 64 * 1024        # no chunk smaller (except the file's last)
AVG_SIZE = 256 * 1024       # target/normalization point (2**18)
MAX_SIZE = 1024 * 1024      # hard ceiling; forced cut at 1 MiB

# Normalization level 2 around AVG_SIZE = 2**18:
#   before AVG: harder condition, 18+2 = 20 one-bits -> longer chunks
#   after  AVG: easier condition, 18-2 = 16 one-bits -> shorter chunks
# Masks test the TOP bits of the 64-bit fingerprint, where Gear's
# left-shift accumulation concentrates the mixing.
MASK_S = 0xFFFFF00000000000  # 20 one-bits
MASK_L = 0xFFFF000000000000  # 16 one-bits

U64 = 0xFFFFFFFFFFFFFFFF

# Only payloads at or above this size are chunked; smaller objects stay
# whole. Measured (store/tests/measure_gate_cdc.py, "threshold" section):
# below ~2 MiB a file yields so few chunks that edit granularity is not
# meaningfully finer than the whole file, while the recipe + per-chunk
# filesystem overhead is already being paid. See CHUNKING.md section 5.
DEFAULT_THRESHOLD = 2 * 1024 * 1024

GEAR_SEED = b"werk-cdc-gear-v1"


def _gear_table() -> "tuple[int, ...]":
    """The 256-entry Gear table, generated deterministically from SHA-256.

    gear[b] = big-endian u64 of the first 8 bytes of
              SHA-256(b"werk-cdc-gear-v1" + bytes([b]))

    Derived rather than tabulated so a foreign implementation needs one
    sentence, not 256 constants - and cannot mistype entry 173.
    """
    table = []
    for b in range(256):
        digest = hashlib.sha256(GEAR_SEED + bytes([b])).digest()
        table.append(int.from_bytes(digest[:8], "big"))
    return tuple(table)


GEAR = _gear_table()


def cut_point(data: "bytes | bytearray | memoryview", n: "int | None" = None) -> int:
    """Length of the first chunk of *data*, per CHUNKING.md section 3.

    *data* must hold either at least MAX_SIZE bytes or the entire remainder
    of the stream; under that precondition the answer is final - scanning is
    left-to-right and never looks past the returned index.
    """
    if n is None:
        n = len(data)
    if n > MAX_SIZE:
        n = MAX_SIZE
    if n <= MIN_SIZE:
        return n
    center = AVG_SIZE if n > AVG_SIZE else n
    fp = 0
    i = MIN_SIZE  # the first MIN_SIZE bytes are skipped entirely (FastCDC)
    while i < center:
        fp = ((fp << 1) + GEAR[data[i]]) & U64
        if fp & MASK_S == 0:
            return i + 1
        i += 1
    while i < n:
        fp = ((fp << 1) + GEAR[data[i]]) & U64
        if fp & MASK_L == 0:
            return i + 1
        i += 1
    return n


def iter_chunks(stream, read_size: int = 1 << 20) -> "Iterator[bytes]":
    """Yield the CDC chunks of a binary stream, in order.

    Buffers at most MAX_SIZE + read_size bytes, so peak memory is
    independent of payload size. Boundaries depend only on the byte stream,
    never on how it was read.
    """
    buf = bytearray()
    eof = False
    while True:
        while not eof and len(buf) < MAX_SIZE:
            piece = stream.read(read_size)
            if not piece:
                eof = True
                break
            buf += piece
        if not buf:
            return
        if len(buf) >= MAX_SIZE or eof:
            n = cut_point(buf)
            yield bytes(buf[:n])
            del buf[:n]
        if eof and not buf:
            return


def chunk_bytes(data: bytes) -> "list[bytes]":
    """Chunk an in-memory blob (tests and the gate; payloads use streams)."""
    import io

    return list(iter_chunks(io.BytesIO(data)))


# ---------------------------------------------------------------------
# Recipes - how a whole object is put back together
# ---------------------------------------------------------------------

RECIPE_FORMAT = 1


@dataclass(frozen=True)
class Recipe:
    """The reassembly instructions for one chunked object.

    Keyed by (and stored under) the WHOLE-file sha256 - the same digest the
    manifest declares, so nothing above the object layer ever learns that
    chunking happened.
    """

    whole_sha256: str
    whole_size: int
    chunks: "tuple[tuple[str, int], ...]"  # (chunk sha256, chunk size), in order
    algorithm: str = ALGORITHM
    min_size: int = MIN_SIZE
    avg_size: int = AVG_SIZE
    max_size: int = MAX_SIZE

    def to_json(self) -> bytes:
        doc = {
            "werkstore_recipe": RECIPE_FORMAT,
            "algorithm": self.algorithm,
            "min_size": self.min_size,
            "avg_size": self.avg_size,
            "max_size": self.max_size,
            "whole_sha256": self.whole_sha256,
            "whole_size": self.whole_size,
            "chunks": [[h, s] for h, s in self.chunks],
        }
        return (json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n").encode(
            "ascii"
        )

    @classmethod
    def from_json(cls, raw: bytes) -> "Recipe":
        doc = json.loads(raw)
        if doc.get("werkstore_recipe") != RECIPE_FORMAT:
            raise ValueError(
                "unknown recipe format %r" % (doc.get("werkstore_recipe"),)
            )
        chunks = tuple((str(h), int(s)) for h, s in doc["chunks"])
        return cls(
            whole_sha256=str(doc["whole_sha256"]),
            whole_size=int(doc["whole_size"]),
            chunks=chunks,
            algorithm=str(doc.get("algorithm", ALGORITHM)),
            min_size=int(doc.get("min_size", MIN_SIZE)),
            avg_size=int(doc.get("avg_size", AVG_SIZE)),
            max_size=int(doc.get("max_size", MAX_SIZE)),
        )

    def check(self) -> None:
        """Structural sanity - sizes must add up before anyone trusts this."""
        total = sum(s for _h, s in self.chunks)
        if total != self.whole_size:
            raise ValueError(
                "recipe for %s declares whole_size=%d but its chunks sum to %d"
                % (self.whole_sha256, self.whole_size, total)
            )
