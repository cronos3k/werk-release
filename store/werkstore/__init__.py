"""werk-store - the format-aware version control system for werk packages.

The one sentence that governs every module here:

    The materialized werk is truth. The store dedups, transfers, and
    remembers - it never becomes authoritative.

Consequences, all of them load-bearing:

  * the manifest's per-file sha256 IS the object name - no translation layer;
  * materialization is verified by rehashing the RESULT, never by trusting
    the store's own bookkeeping;
  * the unit of diff and of sync is the node version, not the byte range;
  * GC is multi-rooted and pin-aware, and refuses to sweep when a root
    cannot be read;
  * scrub rehashes every object, because a store that cannot prove every
    blob hashes to its own name is broken.

Zero third-party dependencies, by construction (including Ed25519).
"""

from .chunking import (
    ALGORITHM as CDC_ALGORITHM,
    AVG_SIZE as CDC_AVG_SIZE,
    DEFAULT_THRESHOLD as CDC_THRESHOLD,
    MAX_SIZE as CDC_MAX_SIZE,
    MIN_SIZE as CDC_MIN_SIZE,
    Recipe,
    chunk_bytes,
    cut_point,
    iter_chunks,
)
from .diff import Diff, diff_manifests, diff_stored
from .gc import GCReport, ScrubReport, collect, compute_roots, scrub
from .ingest import IngestRefused, IngestResult, ingest
from .manifest import Manifest, Node, Version
from .materialize import MaterializeReport, materialize
from .objects import ObjectStore, hash_bytes, hash_file, hash_stream, is_hash
from .refs import PackageRef, Pin
from .signature import ABSENT, INVALID, VALID, verify_chain
from .store import WerkStore
from .sync import SyncPlan, SyncResult, plan, pull, push, sync_all

__version__ = "0.1.0"

__all__ = [
    "WerkStore",
    "ObjectStore",
    "Manifest",
    "Node",
    "Version",
    "PackageRef",
    "Pin",
    "ingest",
    "IngestResult",
    "IngestRefused",
    "materialize",
    "MaterializeReport",
    "diff_manifests",
    "diff_stored",
    "Diff",
    "plan",
    "push",
    "pull",
    "sync_all",
    "SyncPlan",
    "SyncResult",
    "collect",
    "scrub",
    "compute_roots",
    "GCReport",
    "ScrubReport",
    "verify_chain",
    "ABSENT",
    "VALID",
    "INVALID",
    "hash_bytes",
    "hash_file",
    "hash_stream",
    "is_hash",
    "Recipe",
    "chunk_bytes",
    "cut_point",
    "iter_chunks",
    "CDC_ALGORITHM",
    "CDC_MIN_SIZE",
    "CDC_AVG_SIZE",
    "CDC_MAX_SIZE",
    "CDC_THRESHOLD",
    "__version__",
]
