//! The MessagePack subset werk envelope headers use.
//!
//! Normative source: spec/layouts/ENVELOPE.layout.txt section 4, which
//! specifies the whole subset so that reading a werk binary needs no external
//! knowledge (law 2). The executable statement of the same rules is
//! `mp_encode`/`mp_decode` in spec/examples/make-examples.py; this module is
//! tested for byte-identity against the binary that script emits.
//!
//! Two things bite implementers and are therefore restated here:
//!   * every multi-byte value INSIDE MessagePack is BIG-endian, the opposite
//!     of every payload section;
//!   * ext types (0xc7-0xc9, 0xd4-0xd8) and 0xc1 are BANNED, and a reader must
//!     reject a header containing one rather than skip it.

use std::collections::BTreeMap;

#[derive(Debug, Clone, PartialEq)]
pub enum Mp {
    Nil,
    Bool(bool),
    Int(i64),
    UInt(u64),
    /// Always encoded as float64 (0xcb). Canonical rule 4.3: "encode every
    /// non-integral number as float64, never float32."
    Float(f64),
    Str(String),
    Bin(Vec<u8>),
    Array(Vec<Mp>),
    /// A BTreeMap so that iteration is already in raw-UTF-8 key order, which is
    /// the canonical map ordering rule.
    Map(BTreeMap<String, Mp>),
}

impl Mp {
    pub fn as_u64(&self) -> Option<u64> {
        match self {
            Mp::UInt(v) => Some(*v),
            Mp::Int(v) if *v >= 0 => Some(*v as u64),
            _ => None,
        }
    }
    pub fn as_str(&self) -> Option<&str> {
        match self {
            Mp::Str(s) => Some(s),
            _ => None,
        }
    }
    pub fn as_array(&self) -> Option<&[Mp]> {
        match self {
            Mp::Array(a) => Some(a),
            _ => None,
        }
    }
    pub fn get(&self, key: &str) -> Option<&Mp> {
        match self {
            Mp::Map(m) => m.get(key),
            _ => None,
        }
    }
}

pub fn map(pairs: Vec<(&str, Mp)>) -> Mp {
    Mp::Map(pairs.into_iter().map(|(k, v)| (k.to_string(), v)).collect())
}

// ---------------------------------------------------------------------------
// Encoder (canonical, per ENVELOPE.layout.txt 4.3)
// ---------------------------------------------------------------------------

pub fn encode(v: &Mp) -> Vec<u8> {
    let mut out = Vec::new();
    enc(v, &mut out);
    out
}

fn enc(v: &Mp, out: &mut Vec<u8>) {
    match v {
        Mp::Nil => out.push(0xc0),
        Mp::Bool(false) => out.push(0xc2),
        Mp::Bool(true) => out.push(0xc3),
        Mp::UInt(n) => enc_uint(*n, out),
        Mp::Int(n) => {
            if *n >= 0 {
                enc_uint(*n as u64, out)
            } else if *n >= -32 {
                out.push((*n as i8) as u8)
            } else if *n >= i8::MIN as i64 {
                out.push(0xd0);
                out.push((*n as i8) as u8);
            } else if *n >= i16::MIN as i64 {
                out.push(0xd1);
                out.extend_from_slice(&(*n as i16).to_be_bytes());
            } else if *n >= i32::MIN as i64 {
                out.push(0xd2);
                out.extend_from_slice(&(*n as i32).to_be_bytes());
            } else {
                out.push(0xd3);
                out.extend_from_slice(&n.to_be_bytes());
            }
        }
        Mp::Float(f) => {
            out.push(0xcb);
            out.extend_from_slice(&f.to_be_bytes());
        }
        Mp::Str(s) => {
            let b = s.as_bytes();
            let n = b.len();
            if n <= 31 {
                out.push(0xa0 | n as u8);
            } else if n <= 0xFF {
                out.push(0xd9);
                out.push(n as u8);
            } else if n <= 0xFFFF {
                out.push(0xda);
                out.extend_from_slice(&(n as u16).to_be_bytes());
            } else {
                out.push(0xdb);
                out.extend_from_slice(&(n as u32).to_be_bytes());
            }
            out.extend_from_slice(b);
        }
        Mp::Bin(b) => {
            let n = b.len();
            if n <= 0xFF {
                out.push(0xc4);
                out.push(n as u8);
            } else if n <= 0xFFFF {
                out.push(0xc5);
                out.extend_from_slice(&(n as u16).to_be_bytes());
            } else {
                out.push(0xc6);
                out.extend_from_slice(&(n as u32).to_be_bytes());
            }
            out.extend_from_slice(b);
        }
        Mp::Array(a) => {
            let n = a.len();
            if n <= 15 {
                out.push(0x90 | n as u8);
            } else if n <= 0xFFFF {
                out.push(0xdc);
                out.extend_from_slice(&(n as u16).to_be_bytes());
            } else {
                out.push(0xdd);
                out.extend_from_slice(&(n as u32).to_be_bytes());
            }
            for x in a {
                enc(x, out);
            }
        }
        Mp::Map(m) => {
            let n = m.len();
            if n <= 15 {
                out.push(0x80 | n as u8);
            } else if n <= 0xFFFF {
                out.push(0xde);
                out.extend_from_slice(&(n as u16).to_be_bytes());
            } else {
                out.push(0xdf);
                out.extend_from_slice(&(n as u32).to_be_bytes());
            }
            // BTreeMap iterates in String order, which for Rust is byte order
            // on the UTF-8 encoding — exactly the canonical rule.
            for (k, v) in m {
                enc(&Mp::Str(k.clone()), out);
                enc(v, out);
            }
        }
    }
}

fn enc_uint(n: u64, out: &mut Vec<u8>) {
    if n <= 127 {
        out.push(n as u8);
    } else if n <= 0xFF {
        out.push(0xcc);
        out.push(n as u8);
    } else if n <= 0xFFFF {
        out.push(0xcd);
        out.extend_from_slice(&(n as u16).to_be_bytes());
    } else if n <= 0xFFFF_FFFF {
        out.push(0xce);
        out.extend_from_slice(&(n as u32).to_be_bytes());
    } else {
        out.push(0xcf);
        out.extend_from_slice(&n.to_be_bytes());
    }
}

// ---------------------------------------------------------------------------
// Decoder
// ---------------------------------------------------------------------------

pub fn decode(buf: &[u8]) -> Result<Mp, String> {
    let (v, o) = read(buf, 0)?;
    if o != buf.len() {
        return Err(format!("{} trailing bytes after the MessagePack value", buf.len() - o));
    }
    Ok(v)
}

fn need(b: &[u8], o: usize, n: usize) -> Result<&[u8], String> {
    b.get(o..o + n).ok_or_else(|| format!("header truncated at byte {o}"))
}

fn read(b: &[u8], o: usize) -> Result<(Mp, usize), String> {
    let c = *b.get(o).ok_or("header truncated")?;
    let o = o + 1;
    match c {
        0x00..=0x7f => Ok((Mp::UInt(c as u64), o)),
        0xe0..=0xff => Ok((Mp::Int(c as i8 as i64), o)),
        0xa0..=0xbf => {
            let n = (c & 0x1f) as usize;
            Ok((Mp::Str(utf8(need(b, o, n)?)?), o + n))
        }
        0x90..=0x9f => read_array(b, o, (c & 0x0f) as usize),
        0x80..=0x8f => read_map(b, o, (c & 0x0f) as usize),
        0xc0 => Ok((Mp::Nil, o)),
        0xc2 => Ok((Mp::Bool(false), o)),
        0xc3 => Ok((Mp::Bool(true), o)),
        0xc1 | 0xc7 | 0xc8 | 0xc9 | 0xd4..=0xd8 => Err(format!(
            "format byte 0x{c:02x} is banned in werk headers (ENVELOPE.layout.txt 4.2)"
        )),
        0xcc => Ok((Mp::UInt(need(b, o, 1)?[0] as u64), o + 1)),
        0xcd => Ok((Mp::UInt(u16::from_be_bytes(need(b, o, 2)?.try_into().unwrap()) as u64), o + 2)),
        0xce => Ok((Mp::UInt(u32::from_be_bytes(need(b, o, 4)?.try_into().unwrap()) as u64), o + 4)),
        0xcf => Ok((Mp::UInt(u64::from_be_bytes(need(b, o, 8)?.try_into().unwrap())), o + 8)),
        0xd0 => Ok((Mp::Int(need(b, o, 1)?[0] as i8 as i64), o + 1)),
        0xd1 => Ok((Mp::Int(i16::from_be_bytes(need(b, o, 2)?.try_into().unwrap()) as i64), o + 2)),
        0xd2 => Ok((Mp::Int(i32::from_be_bytes(need(b, o, 4)?.try_into().unwrap()) as i64), o + 4)),
        0xd3 => Ok((Mp::Int(i64::from_be_bytes(need(b, o, 8)?.try_into().unwrap())), o + 8)),
        0xca => Ok((Mp::Float(f32::from_be_bytes(need(b, o, 4)?.try_into().unwrap()) as f64), o + 4)),
        0xcb => Ok((Mp::Float(f64::from_be_bytes(need(b, o, 8)?.try_into().unwrap())), o + 8)),
        0xd9 | 0xda | 0xdb | 0xc4 | 0xc5 | 0xc6 | 0xdc | 0xdd | 0xde | 0xdf => {
            let (len_bytes, kind) = match c {
                0xd9 => (1, 's'),
                0xda => (2, 's'),
                0xdb => (4, 's'),
                0xc4 => (1, 'b'),
                0xc5 => (2, 'b'),
                0xc6 => (4, 'b'),
                0xdc => (2, 'a'),
                0xdd => (4, 'a'),
                0xde => (2, 'm'),
                _ => (4, 'm'),
            };
            let raw = need(b, o, len_bytes)?;
            let n = match len_bytes {
                1 => raw[0] as usize,
                2 => u16::from_be_bytes(raw.try_into().unwrap()) as usize,
                _ => u32::from_be_bytes(raw.try_into().unwrap()) as usize,
            };
            let o = o + len_bytes;
            match kind {
                's' => Ok((Mp::Str(utf8(need(b, o, n)?)?), o + n)),
                'b' => Ok((Mp::Bin(need(b, o, n)?.to_vec()), o + n)),
                'a' => read_array(b, o, n),
                _ => read_map(b, o, n),
            }
        }
    }
}

fn utf8(b: &[u8]) -> Result<String, String> {
    String::from_utf8(b.to_vec()).map_err(|e| format!("header string is not UTF-8: {e}"))
}

fn read_array(b: &[u8], mut o: usize, n: usize) -> Result<(Mp, usize), String> {
    let mut out = Vec::with_capacity(n.min(1024));
    for _ in 0..n {
        let (v, no) = read(b, o)?;
        out.push(v);
        o = no;
    }
    Ok((Mp::Array(out), o))
}

fn read_map(b: &[u8], mut o: usize, n: usize) -> Result<(Mp, usize), String> {
    let mut out = BTreeMap::new();
    for _ in 0..n {
        let (k, no) = read(b, o)?;
        let (v, no2) = read(b, no)?;
        let key = match k {
            Mp::Str(s) => s,
            other => return Err(format!("werk header map keys must be strings, got {other:?}")),
        };
        out.insert(key, v);
        o = no2;
    }
    Ok((Mp::Map(out), o))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The worked example in ENVELOPE.layout.txt section 4.4 — with the
    /// arithmetic corrected.
    ///
    /// SPEC FINDING S-2. That section prints `af` (fixstr length 15) in front
    /// of `core.pose.rest`, which is 14 bytes, and then states header_len = 34
    /// and "pad = 2 bytes". All three numbers are wrong: the correct lead byte
    /// is `ae`, the header is 35 bytes, and the padding is 1. The declared
    /// payload_origin of 48 happens to survive because 46 and 47 round up to
    /// the same boundary, which is why the error is easy to miss by eye.
    /// Nothing generated by make-examples.py is affected — the real WKRP
    /// fixture is written by the encoder, not by hand — so this is a defect in
    /// the illustration only. This test asserts the CORRECT bytes.
    #[test]
    fn worked_example_from_the_layout_file() {
        let h = map(vec![
            ("endianness", Mp::Str("le".into())),
            ("kind", Mp::Str("core.pose.rest".into())),
        ]);
        let bytes = encode(&h);
        let expect: Vec<u8> = {
            let mut v = vec![0x82];
            v.push(0xaa);
            v.extend_from_slice(b"endianness");
            v.push(0xa2);
            v.extend_from_slice(b"le");
            v.push(0xa4);
            v.extend_from_slice(b"kind");
            v.push(0xa0 | 14);
            v.extend_from_slice(b"core.pose.rest");
            v
        };
        assert_eq!(bytes, expect);
        assert_eq!(bytes.len(), 35);
        assert_eq!(super::super::envelope::align16(12 + bytes.len()), 48);
        assert_eq!(decode(&bytes).unwrap(), h);
    }

    #[test]
    fn shortest_integer_encodings() {
        assert_eq!(encode(&Mp::UInt(0)), vec![0x00]);
        assert_eq!(encode(&Mp::UInt(127)), vec![0x7f]);
        assert_eq!(encode(&Mp::UInt(128)), vec![0xcc, 0x80]);
        assert_eq!(encode(&Mp::UInt(256)), vec![0xcd, 0x01, 0x00]);
        assert_eq!(encode(&Mp::Int(-1)), vec![0xff]);
        assert_eq!(encode(&Mp::Int(-32)), vec![0xe0]);
        assert_eq!(encode(&Mp::Int(-33)), vec![0xd0, 0xdf]);
    }

    #[test]
    fn floats_are_always_float64() {
        assert_eq!(encode(&Mp::Float(1.0))[0], 0xcb);
        assert_eq!(encode(&Mp::Float(0.0)).len(), 9);
    }

    #[test]
    fn ext_types_are_rejected() {
        for c in [0xc1u8, 0xc7, 0xc8, 0xc9, 0xd4, 0xd5, 0xd6, 0xd7, 0xd8] {
            assert!(decode(&[c]).is_err(), "0x{c:02x} must be rejected");
        }
    }
}
