"""Package refs and pins - the store's roots, and nothing more.

A ref is a note saying "this manifest hash was ingested, here is what it was
called". It is bookkeeping, not authority: delete every ref and the objects
are still exactly the artifact; delete the objects and no ref can conjure
them back. Refs exist so GC has roots and so a human can find a package by
name instead of by 64 hex characters.

Refs are named by the manifest hash, which names the whole package state
(the manifest hashes every file). Ingesting the same package twice writes
the same ref, which is the correct amount of change: none.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Iterator

from .objects import is_hash

SAFE_NAME = re.compile(r"[^a-z0-9._-]+")


@dataclass
class PackageRef:
    """One ingested package."""

    manifest_hash: str
    entity_uuid: str = ""
    name: str = ""
    signature_hash: "str | None" = None
    signature_state: str = "absent"
    ingested_at: str = ""
    source: str = ""
    container_form: str = ""
    file_count: int = 0
    declared_bytes: int = 0
    werkstore_ref: int = 1

    def to_json(self) -> bytes:
        return (
            json.dumps(asdict(self), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        ).encode("utf-8")

    @classmethod
    def from_json(cls, data: bytes) -> "PackageRef":
        doc = json.loads(data)
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in doc.items() if k in known})


@dataclass
class Pin:
    """An explicit GC root that is not a package ref.

    Pins exist for the cases a ref cannot express: a loose object being
    staged, a blob kept for a bisect, a corpus a benchmark depends on.
    """

    name: str
    hashes: "list[str]" = field(default_factory=list)
    note: str = ""
    created: str = ""

    def to_json(self) -> bytes:
        return (
            json.dumps(asdict(self), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        ).encode("utf-8")


def safe_name(name: str) -> str:
    """A filesystem-safe pin filename."""
    cleaned = SAFE_NAME.sub("-", name.strip().lower()).strip("-")
    return cleaned or "pin"


class RefStore:
    """Refs and pins on disk, one JSON file each. No database (deliberately)."""

    def __init__(self, refs_dir: str, pins_dir: str) -> None:
        self.refs_dir = os.path.abspath(refs_dir)
        self.pins_dir = os.path.abspath(pins_dir)
        os.makedirs(self.refs_dir, exist_ok=True)
        os.makedirs(self.pins_dir, exist_ok=True)

    # -- package refs -------------------------------------------------

    def _ref_path(self, manifest_hash: str) -> str:
        if not is_hash(manifest_hash):
            raise ValueError("manifest hash must be lowercase-hex sha256")
        return os.path.join(self.refs_dir, manifest_hash + ".json")

    def put(self, ref: PackageRef) -> None:
        path = self._ref_path(ref.manifest_hash)
        tmp = path + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(ref.to_json())
        os.replace(tmp, path)

    def get(self, manifest_hash: str) -> "PackageRef | None":
        path = self._ref_path(manifest_hash)
        if not os.path.exists(path):
            return None
        with open(path, "rb") as fh:
            return PackageRef.from_json(fh.read())

    def remove(self, manifest_hash: str) -> bool:
        path = self._ref_path(manifest_hash)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def iter_refs(self) -> "Iterator[PackageRef]":
        for name in sorted(os.listdir(self.refs_dir)):
            if not name.endswith(".json"):
                continue
            with open(os.path.join(self.refs_dir, name), "rb") as fh:
                try:
                    yield PackageRef.from_json(fh.read())
                except Exception:
                    continue

    def resolve(self, spec: str) -> "PackageRef | None":
        """Resolve a full hash, a unique hash prefix, or an entity name.

        Ambiguity is an error, not a coin toss: a prefix matching two
        packages returns None rather than picking one.
        """
        spec = spec.strip()
        if is_hash(spec):
            return self.get(spec)
        refs = list(self.iter_refs())
        by_prefix = [r for r in refs if r.manifest_hash.startswith(spec.lower())]
        if len(by_prefix) == 1:
            return by_prefix[0]
        if len(by_prefix) > 1:
            return None
        by_name = [r for r in refs if r.name == spec]
        if len(by_name) == 1:
            return by_name[0]
        return None

    # -- pins ---------------------------------------------------------

    def put_pin(self, pin: Pin) -> str:
        path = os.path.join(self.pins_dir, safe_name(pin.name) + ".json")
        tmp = path + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(pin.to_json())
        os.replace(tmp, path)
        return path

    def remove_pin(self, name: str) -> bool:
        path = os.path.join(self.pins_dir, safe_name(name) + ".json")
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def iter_pins(self) -> "Iterator[Pin]":
        for name in sorted(os.listdir(self.pins_dir)):
            if not name.endswith(".json"):
                continue
            with open(os.path.join(self.pins_dir, name), "rb") as fh:
                try:
                    doc = json.loads(fh.read())
                except Exception:
                    continue
            yield Pin(
                name=doc.get("name", name[:-5]),
                hashes=[h for h in doc.get("hashes", []) if is_hash(h)],
                note=doc.get("note", ""),
                created=doc.get("created", ""),
            )
