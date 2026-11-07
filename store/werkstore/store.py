"""The store itself: objects + refs + pins under one root.

    <root>/
      werkstore.json      store descriptor (format version; nothing else -
                          the store has no state that is not a file)
      objects/ab/cd/<64-hex>
      refs/<manifest-hash>.json
      pins/<name>.json
      quarantine/<64-hex>  objects that failed a scrub, kept as evidence
      tmp/                 in-flight writes, always renamed into place

Every one of those is regenerable from materialized werk files except the
objects, and the objects are only ever a copy of bytes that exist, verified,
somewhere else. The store is a cache, never the truth.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from .chunking import DEFAULT_THRESHOLD as CHUNK_THRESHOLD
from .objects import ObjectStore
from .refs import RefStore

STORE_DESCRIPTOR = "werkstore.json"
STORE_FORMAT = 1


def now_iso() -> str:
    """RFC 3339 UTC, second precision - the format the signature chain uses."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


class WerkStore:
    """A werk object store rooted at *root*."""

    def __init__(
        self,
        root: str,
        create: bool = True,
        chunk_threshold: "int | None" = CHUNK_THRESHOLD,
    ) -> None:
        self.root = os.path.abspath(root)
        if create:
            os.makedirs(self.root, exist_ok=True)
        elif not os.path.isdir(self.root):
            raise FileNotFoundError("no store at %s" % self.root)
        # Payloads at or above this size are stored chunked (CDC, see
        # store/CHUNKING.md); None disables chunking entirely. Applies to
        # NEW ingests only - whatever is already in the store stays as it
        # is, which is what makes an old store forward-compatible for free.
        self.chunk_threshold = chunk_threshold
        self.objects = ObjectStore(
            os.path.join(self.root, "objects"),
            os.path.join(self.root, "tmp"),
            chunks_dir=os.path.join(self.root, "chunks"),
        )
        self.refs = RefStore(
            os.path.join(self.root, "refs"), os.path.join(self.root, "pins")
        )
        self.quarantine_dir = os.path.join(self.root, "quarantine")
        if create:
            self._write_descriptor()

    def _write_descriptor(self) -> None:
        path = os.path.join(self.root, STORE_DESCRIPTOR)
        if os.path.exists(path):
            return
        doc = {
            "werkstore": STORE_FORMAT,
            "hash_algorithm": "sha256",
            "object_layout": "objects/<h[0:2]>/<h[2:4]>/<h>",
            "chunking": "fastcdc-gear64-v1 (see store/CHUNKING.md); recipes at "
            "chunks/<h[0:2]>/<h[2:4]>/<h>.json keyed by the WHOLE-file sha256",
            "note": (
                "Content-addressed cache of werk packages. The manifest's "
                "per-file sha256 IS the object name; there is no translation "
                "layer. Materialized werk files are the truth; this directory "
                "is a cache and may be deleted."
            ),
            "created": now_iso(),
        }
        tmp = path + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write((json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        os.replace(tmp, path)

    # -- convenience --------------------------------------------------

    def stats(self) -> "dict[str, int]":
        count, total = self.objects.count_and_bytes()
        recipes, recipe_bytes = self.objects.recipes_count_and_bytes()
        return {
            "objects": count,
            "bytes": total,
            "chunk_recipes": recipes,
            "chunk_recipe_bytes": recipe_bytes,
            "packages": sum(1 for _ in self.refs.iter_refs()),
            "pins": sum(1 for _ in self.refs.iter_pins()),
        }

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "<WerkStore %s>" % self.root
