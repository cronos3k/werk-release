//! SIGNATURE.json — the Ed25519 custody chain.
//!
//! Normative: SPEC.md section 6 and spec/schemas/signature.schema.json's
//! `$comment`. The bytes an entry signs are exactly
//!
//!   werk-sig/1 LF manifest_sha256 LF prev_entry_sha256 LF signed_at LF
//!   signer.uri LF signer.kind
//!
//! UTF-8, LF line endings, NO trailing newline. `manifest_sha256` is THE
//! ENTRY'S OWN: every chain entry records the manifest state its signer signed,
//! so enrichment can append a link without invalidating every earlier one
//! (law 7). The top-level `manifest_sha256` is the CURRENT anchor and must equal
//! both the last entry's value and the sha256 of the MANIFEST.json bytes on
//! disk. Earlier entries name states that are gone; they verify
//! cryptographically and are not re-checkable against bytes, which is what a
//! history is. (Stage 2 spec finding S-1, resolved as Stage 1 decision 17.)
//!
//! THREE states, never two (a tool that collapses `absent` and `invalid` into
//! one warning has defeated the doctrine):
//!   * signed-and-valid
//!   * absent — anonymous, and visibly so
//!   * present-and-invalid — tampering under an existing signature

use crate::error::{Error, Result};
use crate::hashing::{from_hex, sha256_hex, to_hex};
use ed25519_dalek::{Signature, Signer, SigningKey, Verifier, VerifyingKey};
use serde_json::{json, Value};

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SignatureState {
    Absent,
    Valid,
    Invalid(String),
}

impl SignatureState {
    pub fn code(&self) -> i32 {
        match self {
            SignatureState::Absent => 0,
            SignatureState::Valid => 1,
            SignatureState::Invalid(_) => 2,
        }
    }
    pub fn as_str(&self) -> &str {
        match self {
            SignatureState::Absent => "absent",
            SignatureState::Valid => "signed-and-valid",
            SignatureState::Invalid(r) => r,
        }
    }
}

pub fn signed_message(
    manifest_sha256: &str,
    prev_entry_sha256: &str,
    signed_at: &str,
    uri: &str,
    kind: &str,
) -> Vec<u8> {
    format!("werk-sig/1\n{manifest_sha256}\n{prev_entry_sha256}\n{signed_at}\n{uri}\n{kind}")
        .into_bytes()
}

pub const ZERO_PREV: &str =
    "0000000000000000000000000000000000000000000000000000000000000000";

/// Verify the whole chain against the manifest bytes as they sit on disk.
pub fn verify_chain(sig: &Value, manifest_bytes: &[u8]) -> SignatureState {
    let declared = match sig.get("manifest_sha256").and_then(Value::as_str) {
        Some(s) => s,
        None => return SignatureState::Invalid("SIGNATURE.json has no manifest_sha256".into()),
    };
    let actual = sha256_hex(manifest_bytes);
    if declared != actual {
        return SignatureState::Invalid(format!(
            "manifest_sha256 is {declared} but MANIFEST.json hashes to {actual}: \
             the manifest changed under an existing signature"
        ));
    }
    let chain = match sig.get("chain").and_then(Value::as_array) {
        Some(c) if !c.is_empty() => c,
        _ => return SignatureState::Invalid("SIGNATURE.json has an empty chain".into()),
    };
    let last = chain.len() - 1;
    let mut prev_expected = ZERO_PREV.to_string();
    for (i, e) in chain.iter().enumerate() {
        let idx = e.get("index").and_then(Value::as_i64).unwrap_or(-1);
        if idx != i as i64 {
            return SignatureState::Invalid(format!(
                "chain entry {i} declares index {idx}; index MUST equal the array position"
            ));
        }
        let prev = e.get("prev_entry_sha256").and_then(Value::as_str).unwrap_or("");
        if prev != prev_expected {
            return SignatureState::Invalid(format!(
                "chain entry {i}: prev_entry_sha256 {prev} does not chain to {prev_expected}"
            ));
        }
        // Each entry signs the manifest state IT saw, not a shared anchor.
        let entry_manifest = match e.get("manifest_sha256").and_then(Value::as_str) {
            Some(s) => s,
            None => {
                return SignatureState::Invalid(format!(
                    "chain entry {i} has no manifest_sha256; every entry records the \
                     manifest state its signer signed (SPEC section 6)"
                ))
            }
        };
        // Only the newest link is checkable against bytes we hold. The earlier
        // ones name states that enrichment has superseded, and reporting those
        // as failures would be reporting a history as damage.
        if i == last && entry_manifest != actual {
            return SignatureState::Invalid(format!(
                "the last chain entry signs manifest {entry_manifest} but MANIFEST.json \
                 hashes to {actual}: the manifest changed under an existing signature"
            ));
        }
        let sig_hex = e.get("signature").and_then(Value::as_str).unwrap_or("");
        let pk_hex = e.get("public_key").and_then(Value::as_str).unwrap_or("");
        let signed_at = e.get("signed_at").and_then(Value::as_str).unwrap_or("");
        let uri = e.pointer("/signer/uri").and_then(Value::as_str).unwrap_or("");
        let kind = e.pointer("/signer/kind").and_then(Value::as_str).unwrap_or("");

        let pk_bytes = match from_hex(pk_hex).and_then(|v| <[u8; 32]>::try_from(v).ok()) {
            Some(b) => b,
            None => {
                return SignatureState::Invalid(format!(
                    "chain entry {i}: public_key is not 32 lowercase-hex bytes"
                ))
            }
        };
        let sig_bytes = match from_hex(sig_hex).and_then(|v| <[u8; 64]>::try_from(v).ok()) {
            Some(b) => b,
            None => {
                return SignatureState::Invalid(format!(
                    "chain entry {i}: signature is not 64 lowercase-hex bytes"
                ))
            }
        };
        let vk = match VerifyingKey::from_bytes(&pk_bytes) {
            Ok(k) => k,
            Err(e) => {
                return SignatureState::Invalid(format!(
                    "chain entry {i}: public_key is not a valid Ed25519 point: {e}"
                ))
            }
        };
        let msg = signed_message(entry_manifest, prev, signed_at, uri, kind);
        if vk.verify(&msg, &Signature::from_bytes(&sig_bytes)).is_err() {
            return SignatureState::Invalid(format!(
                "chain entry {i} ({}): Ed25519 verification failed",
                e.pointer("/signer/name").and_then(Value::as_str).unwrap_or("unnamed")
            ));
        }
        prev_expected = sha256_hex(sig_hex.as_bytes());
    }
    SignatureState::Valid
}

pub struct Signer_ {
    pub name: String,
    pub uri: String,
    pub kind: String,
    pub role: Option<String>,
    pub note: Option<String>,
    pub signed_at: String,
}

/// Append an entry, or start a chain if there is none.
///
/// Appending across a manifest change is the NORMAL case, not an error:
/// enrichment adds a node, the manifest is rehashed, and the new signer signs
/// the new state while every earlier entry keeps signing the state it saw. That
/// is what per-entry `manifest_sha256` buys, and it is why law 7's "enrichment
/// appends; it never overwrites earlier custody" is now literally true rather
/// than aspirational. (Stage 2 spec finding S-1, resolved as Stage 1
/// decision 17; werk-core used to refuse here.)
pub fn append_entry(
    existing: Option<&Value>,
    manifest_bytes: &[u8],
    secret_key_hex: &str,
    who: &Signer_,
) -> Result<Value> {
    let sk_bytes = from_hex(secret_key_hex)
        .and_then(|v| <[u8; 32]>::try_from(v).ok())
        .ok_or_else(|| Error::BadKey("secret key must be 64 lowercase hex characters".into()))?;
    let sk = SigningKey::from_bytes(&sk_bytes);
    let pk_hex = to_hex(sk.verifying_key().as_bytes());
    let manifest_hash = sha256_hex(manifest_bytes);

    let (mut chain, extra) = match existing {
        None => (Vec::new(), None),
        Some(v) => (
            v.get("chain").and_then(Value::as_array).cloned().unwrap_or_default(),
            v.get("compaction_log").cloned(),
        ),
    };

    let prev = match chain.last() {
        None => ZERO_PREV.to_string(),
        Some(e) => sha256_hex(
            e.get("signature").and_then(Value::as_str).unwrap_or("").as_bytes(),
        ),
    };
    let msg = signed_message(&manifest_hash, &prev, &who.signed_at, &who.uri, &who.kind);
    let sig = sk.sign(&msg);

    let mut signer = json!({"name": who.name, "uri": who.uri, "kind": who.kind});
    if let Some(r) = &who.role {
        signer["role"] = json!(r);
    }
    let mut entry = json!({
        "index": chain.len(),
        "signer": signer,
        "public_key": pk_hex,
        "signed_at": who.signed_at,
        "manifest_sha256": manifest_hash,
        "prev_entry_sha256": prev,
        "signature": to_hex(&sig.to_bytes()),
    });
    if let Some(n) = &who.note {
        entry["note"] = json!(n);
    }
    chain.push(entry);

    let mut out = json!({
        "werk_signature": 1,
        "algorithm": "ed25519",
        "encoding": "hex-lowercase",
        "manifest_sha256": manifest_hash,
        "chain": chain,
    });
    if let Some(c) = extra {
        out["compaction_log"] = c;
    }
    Ok(out)
}

pub fn public_key_hex(secret_key_hex: &str) -> Result<String> {
    let sk_bytes = from_hex(secret_key_hex)
        .and_then(|v| <[u8; 32]>::try_from(v).ok())
        .ok_or_else(|| Error::BadKey("secret key must be 64 lowercase hex characters".into()))?;
    Ok(to_hex(SigningKey::from_bytes(&sk_bytes).verifying_key().as_bytes()))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// RFC 8032 test vector 1, quoted in spec/MINI-SPECS.md section 12. The
    /// spec says: prove the library before trusting it. This is that proof.
    #[test]
    fn rfc8032_vector_one() {
        let sk_hex = "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60";
        let pk_hex = "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a";
        let expect = "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b";
        assert_eq!(public_key_hex(sk_hex).unwrap(), pk_hex);
        let sk = SigningKey::from_bytes(&<[u8; 32]>::try_from(from_hex(sk_hex).unwrap()).unwrap());
        assert_eq!(to_hex(&sk.sign(b"").to_bytes()), expect);
    }

    #[test]
    fn sha256_vectors_from_mini_specs() {
        assert_eq!(
            sha256_hex(b""),
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        );
        assert_eq!(
            sha256_hex(b"abc"),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        );
        assert_eq!(
            sha256_hex(b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"),
            "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1"
        );
    }
}
