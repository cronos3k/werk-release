//! Format definitions — SPEC.md section 3.18 (ruling 1 of 2026-10-13).
//!
//! "The self-describing part of each node is a format declaration and
//! definition from which an LLM / AI agent can build a working codec."
//! A foreign-encoded payload (a JPEG, a font, a camera raw file) is therefore
//! a legitimate core payload exactly when its DEFINITION DOCUMENT travels in
//! the package: `MANIFEST.json` → `formats` maps a format id to the document's
//! path, and a node names the id in `meta.payload_format`,
//! `meta.file_formats` or `meta.contained_formats`.
//!
//! This module does the part of that a reader can check without implementing
//! any codec: read the document's machine header, check that it is the
//! document the id names, check that every PRINTED test vector hashes to what
//! the header declares, and check a file's leading bytes against the ways the
//! definition says a file of that format is recognised. It builds no codec and
//! runs nothing — a reference implementation in a package is a `core.tool`
//! node, inert data (SPEC.md sections 3.17 and 7.1).

use crate::hashing::sha256_hex;
use serde_json::Value;
use std::collections::BTreeMap;

/// One alternative of a definition's `sniff` list.
#[derive(Debug, Clone, PartialEq)]
pub enum Sniff {
    /// Every listed byte string present at its offset.
    Magic(Vec<(usize, Vec<u8>)>),
    /// A zlib stream header: CMF & 15 == 8, CMF >> 4 <= 7,
    /// (CMF * 256 + FLG) % 31 == 0.
    ZlibHeader,
    /// The format has nothing to recognise it by. It is always NAMED by the
    /// node; the size rule is the one check the bytes allow.
    None { size_multiple_of: Option<u64> },
    /// A rule this reader does not know. Unknown-because-newer: it neither
    /// matches nor mismatches, and the caller says so.
    Unknown(String),
}

#[derive(Debug, Clone)]
pub struct TestVector {
    pub id: String,
    pub input_sha256: String,
    /// `Some(path)` when the input is a declared vector file instead of a
    /// printed hex block.
    pub input_file: Option<String>,
}

#[derive(Debug, Clone)]
pub struct VectorFile {
    pub path: String,
    pub sha256: String,
}

#[derive(Debug, Clone)]
pub struct Definition {
    pub format_id: String,
    pub coverage: String,
    pub coverage_note: Option<String>,
    pub sniff: Vec<Sniff>,
    pub requires: Vec<String>,
    pub vectors: Vec<TestVector>,
    pub vector_files: Vec<VectorFile>,
    /// Fenced blocks whose info string is `hex <id>`, decoded.
    pub hex_blocks: BTreeMap<String, Vec<u8>>,
}

/// Every fenced code block of a markdown document as `(info string, body)`.
/// A fence is a line that starts with three backticks; the info string is the
/// rest of the opening line, trimmed.
fn fenced_blocks(doc: &str) -> Vec<(String, String)> {
    let mut out = Vec::new();
    let mut open: Option<(String, String)> = None;
    for line in doc.lines() {
        let line = line.strip_suffix('\r').unwrap_or(line);
        if let Some(rest) = line.strip_prefix("```") {
            match open.take() {
                Some(block) => out.push(block),
                None => open = Some((rest.trim().to_string(), String::new())),
            }
        } else if let Some((_, body)) = open.as_mut() {
            body.push_str(line);
            body.push('\n');
        }
    }
    out
}

fn decode_hex(text: &str) -> Result<Vec<u8>, String> {
    let digits: Vec<u8> = text.bytes().filter(|b| !b.is_ascii_whitespace()).collect();
    if digits.len() % 2 != 0 {
        return Err("an odd number of hex digits".into());
    }
    digits
        .chunks(2)
        .map(|p| {
            let s = std::str::from_utf8(p).map_err(|_| "non-ASCII in a hex block".to_string())?;
            u8::from_str_radix(s, 16).map_err(|_| format!("`{s}` is not two hex digits"))
        })
        .collect()
}

fn parse_sniff(v: &Value) -> Sniff {
    if let Some(list) = v.get("magic").and_then(Value::as_array) {
        let mut parts = Vec::new();
        for m in list {
            let off = m.get("offset").and_then(Value::as_u64).unwrap_or(0) as usize;
            match m.get("hex").and_then(Value::as_str).map(decode_hex) {
                Some(Ok(bytes)) if !bytes.is_empty() => parts.push((off, bytes)),
                _ => return Sniff::Unknown("a magic entry without usable hex".into()),
            }
        }
        if parts.is_empty() {
            return Sniff::Unknown("an empty magic list".into());
        }
        return Sniff::Magic(parts);
    }
    match v.get("rule").and_then(Value::as_str) {
        Some("zlib-header") => Sniff::ZlibHeader,
        Some("none") => Sniff::None {
            size_multiple_of: v.get("size_multiple_of").and_then(Value::as_u64),
        },
        Some(other) => Sniff::Unknown(format!("rule `{other}`")),
        None => Sniff::Unknown("neither `magic` nor `rule`".into()),
    }
}

/// Read a definition document. `Err` says exactly what makes it unusable as
/// the definition of `expected_id`.
pub fn parse(doc: &[u8], expected_id: &str) -> Result<Definition, String> {
    let text = std::str::from_utf8(doc).map_err(|_| "the document is not UTF-8".to_string())?;
    let blocks = fenced_blocks(text);
    let header_text = blocks
        .iter()
        .find(|(info, _)| info == "werk-format")
        .map(|(_, body)| body)
        .ok_or("no machine header: a fenced block whose info string is `werk-format`")?;
    let header: Value = serde_json::from_str(header_text)
        .map_err(|e| format!("the `werk-format` header is not JSON: {e}"))?;
    let format_id = header
        .get("format_id")
        .and_then(Value::as_str)
        .ok_or("the header has no `format_id`")?
        .to_string();
    if format_id != expected_id {
        return Err(format!(
            "the document defines format `{format_id}`, not `{expected_id}`: one id names exactly \
             one document"
        ));
    }
    let coverage = header.get("coverage").and_then(Value::as_str).unwrap_or("").to_string();
    if coverage != "complete" && coverage != "partial" {
        return Err(format!("`coverage` is {coverage:?}; it is `complete` or `partial`"));
    }
    let coverage_note =
        header.get("coverage_note").and_then(Value::as_str).map(str::to_string);
    if coverage == "partial" && coverage_note.as_deref().map_or(true, |n| n.trim().is_empty()) {
        return Err("`coverage` is `partial` and there is no `coverage_note` saying what is \
                    and is not defined"
            .into());
    }
    let sniff: Vec<Sniff> = header
        .get("sniff")
        .and_then(Value::as_array)
        .map(|a| a.iter().map(parse_sniff).collect())
        .unwrap_or_default();
    if sniff.is_empty() {
        return Err("`sniff` is absent or empty: an empty list is an omission, not a \
                    declaration (a format with nothing to recognise says `{\"rule\": \"none\"}`)"
            .into());
    }
    let requires = header
        .get("requires")
        .and_then(Value::as_array)
        .map(|a| a.iter().filter_map(Value::as_str).map(str::to_string).collect())
        .unwrap_or_default();
    let vectors: Vec<TestVector> = header
        .get("test_vectors")
        .and_then(Value::as_array)
        .map(|a| {
            a.iter()
                .map(|v| TestVector {
                    id: v.get("id").and_then(Value::as_str).unwrap_or("").to_string(),
                    input_sha256: v
                        .get("input_sha256")
                        .and_then(Value::as_str)
                        .unwrap_or("")
                        .to_string(),
                    input_file: v.get("input_file").and_then(Value::as_str).map(str::to_string),
                })
                .collect()
        })
        .unwrap_or_default();
    if vectors.is_empty() {
        return Err("no `test_vectors`: a definition nobody can check an implementation \
                    against is a description, not a definition"
            .into());
    }
    let vector_files = header
        .get("vector_files")
        .and_then(Value::as_array)
        .map(|a| {
            a.iter()
                .map(|v| VectorFile {
                    path: v.get("path").and_then(Value::as_str).unwrap_or("").to_string(),
                    sha256: v.get("sha256").and_then(Value::as_str).unwrap_or("").to_string(),
                })
                .collect()
        })
        .unwrap_or_default();

    let mut hex_blocks = BTreeMap::new();
    for (info, body) in &blocks {
        if let Some(id) = info.strip_prefix("hex ") {
            let bytes = decode_hex(body).map_err(|e| format!("hex block `{}`: {e}", id.trim()))?;
            hex_blocks.insert(id.trim().to_string(), bytes);
        }
    }

    // The self-check a reader CAN do without a codec: every printed input is
    // the input the header hashed. A vector whose input is a declared file is
    // checked by the caller, which knows the manifest.
    for v in &vectors {
        if v.input_file.is_some() {
            continue;
        }
        match hex_blocks.get(&v.id) {
            None => {
                return Err(format!(
                    "test vector `{}` has neither a `hex {}` block nor an `input_file`",
                    v.id, v.id
                ))
            }
            Some(bytes) => {
                let got = sha256_hex(bytes);
                if got != v.input_sha256 {
                    return Err(format!(
                        "test vector `{}`: the printed input hashes to {got}, the header \
                         declares {}",
                        v.id, v.input_sha256
                    ));
                }
            }
        }
    }

    Ok(Definition {
        format_id,
        coverage,
        coverage_note,
        sniff,
        requires,
        vectors,
        vector_files,
        hex_blocks,
    })
}

/// What a file's bytes say against a definition's `sniff` list.
#[derive(Debug, Clone, PartialEq)]
pub enum SniffVerdict {
    /// At least one alternative matches.
    Match,
    /// The format declares nothing to recognise it by; nothing was checked.
    NotSniffable,
    /// No alternative matches.
    Mismatch(String),
    /// Every alternative that did not match is one this reader does not know.
    Unknown(String),
}

pub fn sniff(def: &Definition, bytes: &[u8]) -> SniffVerdict {
    let mut unknown = Vec::new();
    let mut none_rule = false;
    for alt in &def.sniff {
        match alt {
            Sniff::Magic(parts) => {
                if parts.iter().all(|(off, m)| bytes.get(*off..*off + m.len()) == Some(&m[..])) {
                    return SniffVerdict::Match;
                }
            }
            Sniff::ZlibHeader => {
                if bytes.len() >= 2 {
                    let (cmf, flg) = (bytes[0] as u32, bytes[1] as u32);
                    if cmf & 15 == 8 && cmf >> 4 <= 7 && (cmf * 256 + flg) % 31 == 0 {
                        return SniffVerdict::Match;
                    }
                }
            }
            Sniff::None { size_multiple_of } => {
                none_rule = true;
                if let Some(n) = size_multiple_of {
                    if *n > 0 && bytes.len() as u64 % n != 0 {
                        return SniffVerdict::Mismatch(format!(
                            "{} bytes is not a multiple of the record size {n}",
                            bytes.len()
                        ));
                    }
                }
            }
            Sniff::Unknown(what) => unknown.push(what.clone()),
        }
    }
    if none_rule {
        SniffVerdict::NotSniffable
    } else if !unknown.is_empty() {
        SniffVerdict::Unknown(unknown.join("; "))
    } else {
        SniffVerdict::Mismatch(format!(
            "the leading bytes match none of the {} way(s) the definition gives to recognise \
             format `{}`",
            def.sniff.len(),
            def.format_id
        ))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const DOC: &str = "# toy\n\n```werk-format\n{\"format_id\": \"toy\", \"format_version\": 1,\n \"sniff\": [{\"magic\": [{\"offset\": 0, \"hex\": \"544f59\"}]}],\n \"coverage\": \"complete\",\n \"test_vectors\": [{\"id\": \"one\", \"input_sha256\": \"4e4d1f9b2f0e7ec6f0f4f2a4b2a0f0d1c7a2d3f9f6d0d4b9d3b2f8f1c9e9d6a1\"}]}\n```\n\n```hex one\n54 4f 59 01\n```\n";

    #[test]
    fn a_vector_that_does_not_hash_is_refused_by_name() {
        let err = parse(DOC.as_bytes(), "toy").unwrap_err();
        assert!(err.contains("test vector `one`"), "{err}");
    }

    #[test]
    fn a_good_document_parses_and_sniffs() {
        let input = [0x54u8, 0x4f, 0x59, 0x01];
        let doc = DOC.replace(
            "4e4d1f9b2f0e7ec6f0f4f2a4b2a0f0d1c7a2d3f9f6d0d4b9d3b2f8f1c9e9d6a1",
            &sha256_hex(&input),
        );
        let def = parse(doc.as_bytes(), "toy").unwrap();
        assert_eq!(def.hex_blocks["one"], input);
        assert_eq!(sniff(&def, b"TOY..."), SniffVerdict::Match);
        assert!(matches!(sniff(&def, b"NOPE"), SniffVerdict::Mismatch(_)));
        // One id, one document.
        assert!(parse(doc.as_bytes(), "other").unwrap_err().contains("not `other`"));
    }

    #[test]
    fn an_empty_sniff_list_is_an_omission() {
        let doc = DOC.replace("[{\"magic\": [{\"offset\": 0, \"hex\": \"544f59\"}]}]", "[]");
        assert!(parse(doc.as_bytes(), "toy").unwrap_err().contains("sniff"));
    }
}
