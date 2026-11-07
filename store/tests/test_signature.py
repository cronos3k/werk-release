"""Ed25519 and the custody chain.

The RFC 8032 vectors run FIRST and everything else in the suite depends on
them. An in-house crypto implementation that only ever verifies signatures
it produced itself is a mirror, not a check.
"""

import json

import pytest

from werkstore import ed25519
from werkstore.signature import ABSENT, INVALID, VALID, build_chain, verify_chain

# RFC 8032 section 7.1, TEST 1, TEST 2, TEST 3.
VECTORS = [
    (
        "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
        "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
        "",
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b",
    ),
    (
        "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
        "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
        "72",
        "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00",
    ),
    (
        "c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7",
        "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025",
        "af82",
        "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a",
    ),
]


@pytest.mark.parametrize("secret_hex,public_hex,msg_hex,sig_hex", VECTORS)
def test_rfc8032_vectors(secret_hex, public_hex, msg_hex, sig_hex):
    secret = bytes.fromhex(secret_hex)
    message = bytes.fromhex(msg_hex)
    assert ed25519.public_key(secret).hex() == public_hex
    assert ed25519.sign(secret, message).hex() == sig_hex
    assert ed25519.verify(bytes.fromhex(public_hex), message, bytes.fromhex(sig_hex))


def test_verify_rejects_flipped_bit():
    secret = bytes.fromhex(VECTORS[1][0])
    pub = bytes.fromhex(VECTORS[1][1])
    msg = b"the manifest hash"
    sig = bytearray(ed25519.sign(secret, msg))
    assert ed25519.verify(pub, msg, bytes(sig))
    sig[10] ^= 0x01
    assert not ed25519.verify(pub, msg, bytes(sig))
    assert not ed25519.verify(pub, b"a different manifest hash", ed25519.sign(secret, msg))


def _chain(manifest_hash):
    return build_chain(
        manifest_hash,
        [
            {
                "secret": bytes(range(32)),
                "name": "Author",
                "uri": "mailto:a@example.org",
                "kind": "human",
                "signed_at": "2026-08-08T09:00:00Z",
            },
            {
                "secret": bytes((i * 5 + 1) & 0xFF for i in range(32)),
                "name": "Agent",
                "uri": "https://example.org/agent",
                "kind": "agent",
                "signed_at": "2026-08-08T09:01:00Z",
            },
        ],
    )


def test_three_states_are_distinct():
    manifest_hash = "a" * 64
    doc = _chain(manifest_hash)
    raw = json.dumps(doc).encode("utf-8")

    assert verify_chain(None, manifest_hash).state == ABSENT
    assert verify_chain(raw, manifest_hash).state == VALID

    # Tampering under an existing signature: the manifest changed, the chain
    # did not. This is the state that catches bad actors, and it must NOT
    # look like "absent".
    tampered = verify_chain(raw, "b" * 64)
    assert tampered.state == INVALID
    assert tampered.state != ABSENT


def test_broken_link_is_detected():
    manifest_hash = "c" * 64
    doc = _chain(manifest_hash)
    doc["chain"][1]["prev_entry_sha256"] = "0" * 64  # pretend to be first
    verdict = verify_chain(json.dumps(doc).encode("utf-8"), manifest_hash)
    assert verdict.state == INVALID
    assert any("breaks the chain" in p for p in verdict.problems)


def test_pretty_printing_does_not_break_the_chain():
    """The link is over the previous SIGNATURE, not the previous entry's JSON."""
    manifest_hash = "d" * 64
    doc = _chain(manifest_hash)
    compact = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    pretty = json.dumps(doc, indent=4, sort_keys=True).encode("utf-8")
    assert verify_chain(compact, manifest_hash).state == VALID
    assert verify_chain(pretty, manifest_hash).state == VALID
