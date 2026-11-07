//! The werk binary envelope: 4 ASCII magic, u32 LE version, u32 LE header
//! length, a canonical MessagePack header, zero padding to a 16-byte boundary,
//! then raw payload sections at DECLARED absolute offsets.
//!
//! Normative source: spec/layouts/ENVELOPE.layout.txt. Section 7 of that file
//! gives reference pseudocode and every assertion in it is implemented in
//! `parse` below — a failed assertion means the node is dead, which the caller
//! reports and steps over (law 3).
//!
//! `build` is the writer. It reproduces `build_wkrp` in
//! spec/examples/make-examples.py, including the fixed-point iteration on the
//! header length: the header declares the offsets, the offsets depend on the
//! header's own length, and a shrinking integer can shorten the header and move
//! the payload — so two passes are not enough.

use crate::msgpack::{self, Mp};
use std::collections::BTreeMap;

pub fn align16(n: usize) -> usize {
    (n + 15) / 16 * 16
}

#[derive(Debug, Clone)]
pub struct SectionSpec {
    pub name: String,
    pub dtype: String,
    pub shape: Vec<u64>,
    pub stride: u64,
    pub data: Vec<u8>,
}

#[derive(Debug, Clone)]
pub struct Section {
    pub name: String,
    pub offset: u64,
    pub size: u64,
    pub dtype: String,
    pub shape: Vec<u64>,
    pub stride: u64,
}

#[derive(Debug, Clone)]
pub struct Envelope {
    pub magic: [u8; 4],
    pub version: u32,
    pub header: Mp,
    pub payload_origin: u64,
    pub payload_size: u64,
    pub sections: Vec<Section>,
}

impl Envelope {
    pub fn kind(&self) -> Option<&str> {
        self.header.get("kind").and_then(Mp::as_str)
    }
    pub fn section(&self, name: &str) -> Option<&Section> {
        self.sections.iter().find(|s| s.name == name)
    }
}

/// The seven RESERVED magics of ENVELOPE.layout.txt section 2, and the node
/// type each one binds in its header's `kind`.
///
/// This table is a CONSISTENCY CHECK, not a recogniser. Until ruling 4 of
/// 2026-10-13 it was both: an envelope was "recognised" only if its magic was
/// in this table, the table existed in four files (this one and the three
/// bootstrap loaders), and a magic missing from one of them was silently not
/// parsed there — the reference core missed `WKEM` for three stages and
/// reported nothing, because an unrecognised magic was by rule not damage
/// (finding S12-1). Recognition is now by the frame itself
/// ([`is_envelope_magic`]) and the payload's grammar is found through the
/// header's `kind` and the package's `layouts` map, so a magic this table has
/// never heard of is still validated structurally. `tests/run_gate_magic.py`
/// keeps the four copies of this table equal to the layout file's.
pub const RESERVED_MAGICS: &[(&[u8; 4], &str)] = &[
    (b"WKFF", "core.field.flow"),
    (b"WKRP", "core.pose.rest"),
    (b"WKAC", "core.anim.clip"),
    (b"WKSK", "core.skeleton"),
    (b"WKEM", "core.embedding"),
    (b"WKPC", "core.geom.points"),
    (b"WKGS", "core.geom.gsplat"),
];

/// Is this the start of a werk envelope? `W`, `K`, then two characters each
/// an ASCII capital letter or digit (ENVELOPE.layout.txt section 2). Every
/// reserved magic and every `WKX0`..`WKX9` has this shape, and so does any
/// magic a later revision reserves.
pub fn is_envelope_magic(magic: &[u8; 4]) -> bool {
    magic[0] == b'W'
        && magic[1] == b'K'
        && magic[2..].iter().all(|c| c.is_ascii_uppercase() || c.is_ascii_digit())
}

/// The `kind` a RESERVED magic binds, or `None` for a magic that binds none
/// (`WKX0`..`WKX9`, shared by every profile and extension, and any magic this
/// build does not know).
pub fn reserved_kind(magic: &[u8; 4]) -> Option<&'static str> {
    RESERVED_MAGICS.iter().find(|(m, _)| *m == magic).map(|(_, k)| *k)
}

/// Kept for callers written against the old table: `Some(kind)` for a reserved
/// magic, `Some("*")` for any other envelope magic, `None` for bytes that are
/// not an envelope at all.
pub fn kind_for_magic(magic: &[u8; 4]) -> Option<&'static str> {
    match reserved_kind(magic) {
        Some(k) => Some(k),
        None if is_envelope_magic(magic) => Some("*"),
        None => None,
    }
}

pub fn build(
    magic: &[u8; 4],
    version: u32,
    extra: BTreeMap<String, Mp>,
    kind: &str,
    sections: &[SectionSpec],
) -> Vec<u8> {
    let make_header = |origin: usize, offs: &[usize]| -> Vec<u8> {
        let mut h = extra.clone();
        h.insert("kind".into(), Mp::Str(kind.to_string()));
        h.insert("endianness".into(), Mp::Str("le".into()));
        h.insert("payload_origin".into(), Mp::UInt(origin as u64));
        let end = offs
            .last()
            .zip(sections.last())
            .map(|(o, s)| o + s.data.len())
            .unwrap_or(origin);
        h.insert(
            "payload_size".into(),
            Mp::UInt((align16(end).saturating_sub(origin)) as u64),
        );
        h.insert(
            "sections".into(),
            Mp::Array(
                sections
                    .iter()
                    .zip(offs)
                    .map(|(s, off)| {
                        msgpack::map(vec![
                            ("name", Mp::Str(s.name.clone())),
                            ("offset", Mp::UInt(*off as u64)),
                            ("size", Mp::UInt(s.data.len() as u64)),
                            ("dtype", Mp::Str(s.dtype.clone())),
                            (
                                "shape",
                                Mp::Array(s.shape.iter().map(|d| Mp::UInt(*d)).collect()),
                            ),
                            ("stride", Mp::UInt(s.stride)),
                        ])
                    })
                    .collect(),
            ),
        );
        msgpack::encode(&Mp::Map(h))
    };

    let zeros = vec![0usize; sections.len()];
    let mut header_len = make_header(0, &zeros).len();
    let mut origin;
    let mut offs;
    let mut header;
    let mut round = 0;
    loop {
        origin = align16(12 + header_len);
        offs = Vec::with_capacity(sections.len());
        let mut cur = origin;
        for s in sections {
            offs.push(cur);
            cur = align16(cur + s.data.len());
        }
        header = make_header(origin, &offs);
        if header.len() == header_len {
            break;
        }
        header_len = header.len();
        round += 1;
        assert!(round < 8, "envelope header length did not converge");
    }
    assert_eq!(align16(12 + header.len()), origin);

    let mut out = Vec::new();
    out.extend_from_slice(magic);
    out.extend_from_slice(&version.to_le_bytes());
    out.extend_from_slice(&(header.len() as u32).to_le_bytes());
    out.extend_from_slice(&header);
    out.resize(origin, 0);
    for (s, off) in sections.iter().zip(&offs) {
        out.resize(*off, 0);
        out.extend_from_slice(&s.data);
    }
    let padded = align16(out.len());
    out.resize(padded, 0);
    out
}

/// Every assertion in ENVELOPE.layout.txt section 7. An `Err` here means the
/// node is dead: the caller reports which assertion failed and loads the rest.
pub fn parse(buf: &[u8]) -> Result<Envelope, String> {
    if buf.len() < 12 {
        return Err(format!("file is {} bytes; the minimum legal size is 12", buf.len()));
    }
    let mut magic = [0u8; 4];
    magic.copy_from_slice(&buf[0..4]);
    if !is_envelope_magic(&magic) {
        return Err(format!(
            "{:?} is not an envelope magic (`WK` and two of A-Z or 0-9)",
            String::from_utf8_lossy(&magic)
        ));
    }
    let version = u32::from_le_bytes(buf[4..8].try_into().unwrap());
    let header_len = u32::from_le_bytes(buf[8..12].try_into().unwrap()) as usize;
    if 12 + header_len > buf.len() {
        return Err(format!(
            "header_len {header_len} runs past the end of a {}-byte file",
            buf.len()
        ));
    }
    let header = msgpack::decode(&buf[12..12 + header_len])?;

    match header.get("endianness").and_then(Mp::as_str) {
        Some("le") => {}
        other => {
            return Err(format!(
                "header declares endianness {other:?}; werk payloads are always \"le\""
            ))
        }
    }
    let declared_kind = header
        .get("kind")
        .and_then(Mp::as_str)
        .ok_or("header has no `kind`")?
        .to_string();
    if let Some(expected) = reserved_kind(&magic) {
        if expected != declared_kind {
            return Err(format!(
                "magic {} implies kind `{expected}` but the header says `{declared_kind}`",
                String::from_utf8_lossy(&magic)
            ));
        }
    }

    let computed_origin = align16(12 + header_len) as u64;
    let payload_origin = header
        .get("payload_origin")
        .and_then(Mp::as_u64)
        .ok_or("header has no `payload_origin`")?;
    if payload_origin != computed_origin {
        return Err(format!(
            "declared payload_origin {payload_origin} != computed {computed_origin}"
        ));
    }
    let payload_size = header
        .get("payload_size")
        .and_then(Mp::as_u64)
        .ok_or("header has no `payload_size`")?;
    if payload_origin + payload_size != buf.len() as u64 {
        return Err(format!(
            "payload_origin {payload_origin} + payload_size {payload_size} != file size {}",
            buf.len()
        ));
    }

    let raw = header.get("sections").and_then(Mp::as_array).ok_or("header has no `sections`")?;
    let mut sections = Vec::with_capacity(raw.len());
    let mut seen: Vec<String> = Vec::new();
    let mut prev_end = payload_origin;
    for (i, s) in raw.iter().enumerate() {
        let name = s.get("name").and_then(Mp::as_str).ok_or(format!("section {i} has no name"))?.to_string();
        if seen.contains(&name) {
            return Err(format!("section name `{name}` appears twice"));
        }
        seen.push(name.clone());
        let offset = s.get("offset").and_then(Mp::as_u64).ok_or(format!("section `{name}` has no offset"))?;
        let size = s.get("size").and_then(Mp::as_u64).ok_or(format!("section `{name}` has no size"))?;
        let dtype = s.get("dtype").and_then(Mp::as_str).ok_or(format!("section `{name}` has no dtype"))?.to_string();
        let shape: Vec<u64> = s
            .get("shape")
            .and_then(Mp::as_array)
            .ok_or(format!("section `{name}` has no shape"))?
            .iter()
            .map(|v| v.as_u64().unwrap_or(0))
            .collect();
        let stride = s.get("stride").and_then(Mp::as_u64).ok_or(format!("section `{name}` has no stride"))?;
        if offset % 16 != 0 {
            return Err(format!("section `{name}` offset {offset} is not 16-byte aligned"));
        }
        if offset < prev_end {
            return Err(format!(
                "section `{name}` at {offset} overlaps the previous section, which ended at {prev_end}"
            ));
        }
        if offset - prev_end > 15 {
            return Err(format!(
                "{} bytes of unexplained gap before section `{name}`; only alignment padding is legal",
                offset - prev_end
            ));
        }
        if offset + size > buf.len() as u64 {
            return Err(format!(
                "section `{name}` ({offset}+{size}) runs past the end of a {}-byte file",
                buf.len()
            ));
        }
        check_stride_shape_size(&name, &dtype, &shape, stride, size)?;
        prev_end = offset + size;
        sections.push(Section { name, offset, size, dtype, shape, stride });
    }
    if !sections.is_empty() {
        let last = sections.last().unwrap();
        let expect = align16((last.offset + last.size) as usize) as u64;
        if expect != payload_origin + payload_size {
            return Err(format!(
                "last section ends at {} (aligned {expect}) but payload_origin+payload_size is {}",
                last.offset + last.size,
                payload_origin + payload_size
            ));
        }
    }

    Ok(Envelope { magic, version, header, payload_origin, payload_size, sections })
}

/// ENVELOPE.layout.txt section 6's dtype vocabulary. `None` for "record",
/// which by definition has no fixed element size.
fn dtype_size(dtype: &str) -> Option<u64> {
    Some(match dtype {
        "u8" | "i8" => 1,
        "u16" | "i16" => 2,
        "u32" | "i32" | "f32" => 4,
        "u64" | "i64" | "f64" => 8,
        _ => return None,
    })
}

/// ENVELOPE.layout.txt section 3's consistency rule, as an algorithm rather
/// than a sentence. Which unit `stride` spans — one scalar, or one whole
/// element — is DERIVED from the stride itself against the dtype's size, so a
/// reader never has to guess whether the last entry of `shape` is a component
/// count. The two branches agree whenever `shape[-1] == 1`, so no conformant
/// section is ambiguous. (Stage 2 spec finding S-3, resolved as Stage 1
/// decision 19; the prose version could not be executed and rejected the
/// spec's own fixture.)
fn check_stride_shape_size(
    name: &str,
    dtype: &str,
    shape: &[u64],
    stride: u64,
    size: u64,
) -> Result<(), String> {
    if shape.is_empty() {
        return Err(format!("section `{name}` has an empty shape"));
    }
    // "record" has no fixed element size; the layout file's field table gives
    // the fields and `stride` gives the record size, so esz = stride.
    let esz = dtype_size(dtype).unwrap_or(stride);
    let expect = if stride == esz {
        // The stride spans one scalar: every entry of `shape` is a dimension.
        shape.iter().product::<u64>().saturating_mul(stride)
    } else {
        if stride < esz.saturating_mul(shape[shape.len() - 1]) {
            return Err(format!(
                "section `{name}`: stride {stride} is smaller than {esz} x {} = one element of \
                 dtype `{dtype}` with {} components",
                shape[shape.len() - 1],
                shape[shape.len() - 1]
            ));
        }
        // The stride spans the last dimension: shape[-1] is a component count.
        shape[..shape.len() - 1].iter().product::<u64>().saturating_mul(stride)
    };
    if size != expect {
        return Err(format!(
            "section `{name}`: size {size} but dtype `{dtype}`, shape {shape:?} and stride \
             {stride} require {expect} (ENVELOPE.layout.txt section 3)"
        ));
    }
    Ok(())
}

/// ENVELOPE.layout.txt section 6: "no NaN and no infinity may appear in any
/// core payload. A reader encountering either MUST mark the node dead."
pub fn check_finite(env: &Envelope, buf: &[u8]) -> Result<(), String> {
    for s in &env.sections {
        let data = &buf[s.offset as usize..(s.offset + s.size) as usize];
        let bad = match s.dtype.as_str() {
            "f32" => data
                .chunks_exact(4)
                .any(|c| !f32::from_le_bytes(c.try_into().unwrap()).is_finite()),
            "f64" => data
                .chunks_exact(8)
                .any(|c| !f64::from_le_bytes(c.try_into().unwrap()).is_finite()),
            _ => false,
        };
        if bad {
            return Err(format!("section `{}` contains NaN or infinity", s.name));
        }
    }
    Ok(())
}
