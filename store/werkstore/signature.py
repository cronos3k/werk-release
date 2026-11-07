"""The Ed25519 custody chain - verification, and signing for fixtures.

Law 7 and spec/schemas/signature.schema.json. The signed message is exactly:

    b"werk-sig/1" LF manifest_sha256 LF prev_entry_sha256 LF signed_at
    LF signer.uri LF signer.kind

UTF-8, LF line endings, no trailing newline. Nothing else is covered
directly and nothing else needs to be: manifest_sha256 covers every byte of
every node through the manifest's per-file hashes, and prev_entry_sha256
covers every earlier link.

The three states are surfaced distinctly, because a tool that collapses
"absent" and "invalid" into one warning has defeated the doctrine:

    ABSENT  - no SIGNATURE.json. Anonymous, by choice or by stripping.
              Nothing breaks; the absence is visible.
    VALID   - chain present, every link verifies against the manifest bytes
              the store actually holds.
    INVALID - a link fails. Tampering under an existing signature: the state
              that catches bad actors.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from . import ed25519

ABSENT = "absent"
VALID = "signed-and-valid"
INVALID = "present-and-invalid"

ZERO64 = "0" * 64


@dataclass
class ChainVerdict:
    state: str
    signers: "list[str]" = field(default_factory=list)
    problems: "list[str]" = field(default_factory=list)
    manifest_sha256: str = ""

    @property
    def ok(self) -> bool:
        return self.state == VALID

    def summary(self) -> str:
        if self.state == ABSENT:
            return "signature: absent (anonymous - legitimate, and visible)"
        if self.state == VALID:
            return "signature: signed-and-valid (%d link%s: %s)" % (
                len(self.signers),
                "" if len(self.signers) == 1 else "s",
                ", ".join(self.signers),
            )
        return "signature: PRESENT-AND-INVALID - %s" % "; ".join(self.problems)


def message_for(
    manifest_sha256: str, prev_entry_sha256: str, signed_at: str, uri: str, kind: str
) -> bytes:
    """The exact bytes an entry signs."""
    return "\n".join(
        ["werk-sig/1", manifest_sha256, prev_entry_sha256, signed_at, uri, kind]
    ).encode("utf-8")


def link_hash(previous_signature_hex: str) -> str:
    """sha256 of the UTF-8 bytes of the previous entry's signature field.

    Chaining on the previous signature rather than the previous entry's whole
    JSON means the link survives a pretty-printer.
    """
    return hashlib.sha256(previous_signature_hex.encode("utf-8")).hexdigest()


def verify_chain(signature_bytes: "bytes | None", manifest_sha256: str) -> ChainVerdict:
    """Verify a chain against the sha256 of the manifest bytes actually held."""
    if signature_bytes is None:
        return ChainVerdict(state=ABSENT, manifest_sha256=manifest_sha256)

    problems: "list[str]" = []
    try:
        doc: "dict[str, Any]" = json.loads(signature_bytes)
    except Exception as exc:
        return ChainVerdict(
            state=INVALID,
            problems=["SIGNATURE.json is not parseable JSON: %s" % (exc,)],
            manifest_sha256=manifest_sha256,
        )

    declared = doc.get("manifest_sha256")
    if declared != manifest_sha256:
        problems.append(
            "chain anchors manifest_sha256=%s but the manifest present hashes to %s"
            % (declared, manifest_sha256)
        )

    if doc.get("algorithm") not in (None, "ed25519"):
        problems.append("unsupported algorithm %r" % (doc.get("algorithm"),))
    if doc.get("encoding") not in (None, "hex-lowercase"):
        problems.append("unsupported encoding %r" % (doc.get("encoding"),))

    chain = doc.get("chain")
    if not isinstance(chain, list) or not chain:
        problems.append("chain is empty or not an array")
        return ChainVerdict(state=INVALID, problems=problems, manifest_sha256=manifest_sha256)

    signers: "list[str]" = []
    prev_sig: "str | None" = None
    for i, entry in enumerate(chain):
        where = "chain[%d]" % i
        if not isinstance(entry, dict):
            problems.append("%s is not an object" % where)
            break
        if entry.get("index") != i:
            problems.append(
                "%s declares index=%r but sits at %d" % (where, entry.get("index"), i)
            )
        signer = entry.get("signer") or {}
        uri = str(signer.get("uri", ""))
        kind = str(signer.get("kind", ""))
        name = str(signer.get("name", uri or "?"))
        signed_at = str(entry.get("signed_at", ""))
        prev = str(entry.get("prev_entry_sha256", ""))
        # Each entry signs the manifest state IT saw (SPEC section 6). Only the
        # newest link is checkable against the bytes we hold; the earlier ones
        # name states enrichment has superseded, and calling a history a fault
        # is what the single shared anchor used to force.
        entry_manifest = entry.get("manifest_sha256")
        if not isinstance(entry_manifest, str):
            problems.append(
                "%s has no manifest_sha256; every entry records the manifest state "
                "its signer signed" % where
            )
            entry_manifest = ""
        elif i == len(chain) - 1 and entry_manifest != manifest_sha256:
            problems.append(
                "%s is the newest link and signs manifest %s, but the manifest present "
                "hashes to %s" % (where, entry_manifest, manifest_sha256)
            )
        sig_hex = str(entry.get("signature", ""))
        pub_hex = str(entry.get("public_key", ""))

        expected_prev = ZERO64 if i == 0 else link_hash(prev_sig or "")
        if prev != expected_prev:
            problems.append(
                "%s prev_entry_sha256=%s breaks the chain (expected %s)"
                % (where, prev or "<missing>", expected_prev)
            )

        try:
            pub = bytes.fromhex(pub_hex)
            sig = bytes.fromhex(sig_hex)
        except ValueError:
            problems.append("%s public_key or signature is not hex" % where)
            prev_sig = sig_hex
            continue

        msg = message_for(entry_manifest, prev, signed_at, uri, kind)
        if not ed25519.verify(pub, msg, sig):
            problems.append("%s Ed25519 signature does not verify (signer %s)" % (where, name))
        else:
            signers.append("%s <%s>" % (name, uri) if uri else name)
        prev_sig = sig_hex

    state = INVALID if problems else VALID
    return ChainVerdict(
        state=state, signers=signers, problems=problems, manifest_sha256=manifest_sha256
    )


def build_chain(
    manifest_sha256: str, entries: "list[dict[str, Any]]"
) -> "dict[str, Any]":
    """Build a signed SIGNATURE.json document.

    Each item of *entries* is ``{secret: bytes, name, uri, kind, signed_at,
    role?, note?, manifest_sha256?}``. Used by the fixture builder so tests
    verify a real chain, not a stub. An entry may name its own
    ``manifest_sha256`` (the state that signer saw); entries that do not
    default to *manifest_sha256*, which is the co-signing case where every
    signer signed one state.
    """
    chain = []
    prev_sig = None
    for i, spec in enumerate(entries):
        prev = ZERO64 if i == 0 else link_hash(prev_sig or "")
        secret = spec["secret"]
        pub = ed25519.public_key(secret)
        entry_manifest = spec.get("manifest_sha256") or manifest_sha256
        msg = message_for(
            entry_manifest, prev, spec["signed_at"], spec["uri"], spec["kind"]
        )
        sig = ed25519.sign(secret, msg)
        entry = {
            "index": i,
            "signer": {
                "name": spec["name"],
                "uri": spec["uri"],
                "kind": spec["kind"],
            },
            "public_key": pub.hex(),
            "signed_at": spec["signed_at"],
            "manifest_sha256": entry_manifest,
            "prev_entry_sha256": prev,
            "signature": sig.hex(),
        }
        if spec.get("role"):
            entry["signer"]["role"] = spec["role"]
        if spec.get("note"):
            entry["note"] = spec["note"]
        chain.append(entry)
        prev_sig = sig.hex()
    return {
        "werk_signature": 1,
        "algorithm": "ed25519",
        "encoding": "hex-lowercase",
        "manifest_sha256": manifest_sha256,
        "chain": chain,
    }
