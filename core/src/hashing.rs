//! SHA-256 helpers and the two derived hashes werk defines.
//!
//! spec/MINI-SPECS.md section 11 ("What gets hashed") is normative:
//!   * `files[].sha256`   — the exact bytes of that file in the container.
//!   * `manifest_sha256`  — the exact bytes of MANIFEST.json, never a
//!                          reserialisation.
//!   * `input_hash`       — the concatenation, in `input_files` order, of each
//!                          input's 32 RAW digest bytes, followed by the UTF-8
//!                          bytes of the canonical JSON of `input_params`.

use sha2::{Digest, Sha256};

pub fn sha256(bytes: &[u8]) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(bytes);
    let out = h.finalize();
    let mut a = [0u8; 32];
    a.copy_from_slice(&out);
    a
}

pub fn sha256_hex(bytes: &[u8]) -> String {
    to_hex(&sha256(bytes))
}

pub fn to_hex(bytes: &[u8]) -> String {
    let mut s = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        s.push(char::from_digit((b >> 4) as u32, 16).unwrap());
        s.push(char::from_digit((b & 0xf) as u32, 16).unwrap());
    }
    s
}

pub fn from_hex(s: &str) -> Option<Vec<u8>> {
    if s.len() % 2 != 0 {
        return None;
    }
    let b = s.as_bytes();
    let mut out = Vec::with_capacity(s.len() / 2);
    let mut i = 0;
    while i < b.len() {
        let hi = (b[i] as char).to_digit(16)?;
        let lo = (b[i + 1] as char).to_digit(16)?;
        // Lowercase only: conventions.encoding is hex-lowercase and two
        // spellings of one value is how a comparison silently fails.
        if b[i].is_ascii_uppercase() || b[i + 1].is_ascii_uppercase() {
            return None;
        }
        out.push(((hi << 4) | lo) as u8);
        i += 2;
    }
    Some(out)
}

/// Law 5's derived-data hash. `inputs` is the ORDERED list of (path, sha256hex)
/// pairs — ordered, because a hash over an unordered set is not reproducible —
/// and `params_canonical_json` is the canonical JSON text of `input_params`
/// (`{}` when there are none).
pub fn input_hash(inputs: &[[u8; 32]], params_canonical_json: &str) -> String {
    let mut h = Sha256::new();
    for d in inputs {
        h.update(d);
    }
    h.update(params_canonical_json.as_bytes());
    to_hex(&h.finalize())
}
