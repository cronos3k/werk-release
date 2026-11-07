//! Raw DEFLATE (RFC 1951) decoding, implemented natively.
//!
//! Normative source: spec/MINI-SPECS.md section 7.1, which defines the
//! bitstream completely and carries the test vectors the tests below check.
//! It exists for one caller: a zip entry stored with method 8. A werk writer
//! emits store mode by default (SPEC.md section 1) and every conformance
//! fixture is store mode; method 8 "remains legal and a reader SHOULD support
//! it", and until ruling 9 of 2026-10-13 nothing in this repository did.
//!
//! Decoding only. This crate never deflates: the payloads that dominate a
//! package are already compressed, and a writer that wants a smaller container
//! is the companion store's customer, not this one's.
//!
//! The decoder is the bit-at-a-time canonical-Huffman walk (count per length,
//! symbols in code order). It is the slowest correct way to do it and the
//! easiest to check against the prose, which is the right trade for a
//! reference implementation.

/// Hard ceiling on what one entry may inflate to when the caller does not know
/// better. A caller that knows the declared uncompressed size passes it and
/// the decoder refuses to produce a single byte more: a deflate stream is the
/// one place in the container where a small file can ask for a large
/// allocation.
/// On 32-bit targets (wasm32) `1 << 32` does not fit a `usize`; the ceiling is
/// then the largest representable size, which no allocation can reach anyway.
#[cfg(target_pointer_width = "64")]
pub const DEFAULT_LIMIT: usize = 1 << 32;
#[cfg(not(target_pointer_width = "64"))]
pub const DEFAULT_LIMIT: usize = usize::MAX;

struct Bits<'a> {
    src: &'a [u8],
    pos: usize,
    buf: u32,
    cnt: u32,
}

impl<'a> Bits<'a> {
    /// `n` bits, least significant bit first within each byte (RFC 1951 3.1.1).
    fn take(&mut self, n: u32) -> Result<u32, String> {
        debug_assert!(n <= 16);
        while self.cnt < n {
            let b = *self
                .src
                .get(self.pos)
                .ok_or_else(|| "deflate stream ends inside a block".to_string())?;
            self.pos += 1;
            self.buf |= (b as u32) << self.cnt;
            self.cnt += 8;
        }
        let v = self.buf & ((1u32 << n) - 1);
        self.buf >>= n;
        self.cnt -= n;
        Ok(v)
    }

    /// Discard the bits left in the current byte (stored blocks start on a
    /// byte boundary).
    fn align(&mut self) {
        self.buf = 0;
        self.cnt = 0;
    }
}

/// A canonical Huffman code: how many codes there are of each length, and the
/// symbols in order of (length, symbol value) — which IS the order of the
/// codes, by the construction of RFC 1951 3.2.2.
struct Huffman {
    count: [u16; 16],
    symbol: Vec<u16>,
}

/// `Ok((code, left))`: `left` is how many codes of the longest length remain
/// unused (0 = complete). `Err` = over-subscribed, which no decoder can read.
fn construct(lengths: &[u8]) -> Result<(Huffman, i32), String> {
    let mut count = [0u16; 16];
    for &l in lengths {
        count[l as usize] += 1;
    }
    let mut left: i32 = 1;
    for len in 1..16 {
        left <<= 1;
        left -= count[len] as i32;
        if left < 0 {
            return Err("over-subscribed Huffman code lengths".into());
        }
    }
    let mut offs = [0u16; 16];
    for len in 1..15 {
        offs[len + 1] = offs[len] + count[len];
    }
    let mut symbol = vec![0u16; lengths.len()];
    for (sym, &l) in lengths.iter().enumerate() {
        if l != 0 {
            symbol[offs[l as usize] as usize] = sym as u16;
            offs[l as usize] += 1;
        }
    }
    Ok((Huffman { count, symbol }, left))
}

fn decode(bits: &mut Bits, h: &Huffman) -> Result<u16, String> {
    let mut code: i32 = 0;
    let mut first: i32 = 0;
    let mut index: i32 = 0;
    for len in 1..16 {
        code |= bits.take(1)? as i32;
        let count = h.count[len] as i32;
        if code - count < first {
            return Ok(h.symbol[(index + (code - first)) as usize]);
        }
        index += count;
        first += count;
        first <<= 1;
        code <<= 1;
    }
    Err("a bit sequence matches no Huffman code".into())
}

const LEN_BASE: [u16; 29] = [
    3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99, 115, 131,
    163, 195, 227, 258,
];
const LEN_EXTRA: [u8; 29] = [
    0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0,
];
const DIST_BASE: [u16; 30] = [
    1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025, 1537,
    2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577,
];
const DIST_EXTRA: [u8; 30] = [
    0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13,
    13,
];
/// The order in which the code-length code's own lengths are transmitted.
const CLEN_ORDER: [usize; 19] = [16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15];

fn codes(
    bits: &mut Bits,
    out: &mut Vec<u8>,
    lit: &Huffman,
    dist: &Huffman,
    limit: usize,
) -> Result<(), String> {
    loop {
        let sym = decode(bits, lit)? as usize;
        if sym < 256 {
            if out.len() >= limit {
                return Err(format!("output exceeds the declared {limit} bytes"));
            }
            out.push(sym as u8);
        } else if sym == 256 {
            return Ok(());
        } else {
            let i = sym - 257;
            if i >= 29 {
                return Err(format!("invalid length symbol {sym}"));
            }
            let len = LEN_BASE[i] as usize + bits.take(LEN_EXTRA[i] as u32)? as usize;
            let d = decode(bits, dist)? as usize;
            if d >= 30 {
                return Err(format!("invalid distance symbol {d}"));
            }
            let distance = DIST_BASE[d] as usize + bits.take(DIST_EXTRA[d] as u32)? as usize;
            if distance > out.len() {
                return Err(format!(
                    "distance {distance} reaches before the start of the output ({} bytes so far)",
                    out.len()
                ));
            }
            if out.len() + len > limit {
                return Err(format!("output exceeds the declared {limit} bytes"));
            }
            // Byte by byte ON PURPOSE: a match may overlap its own output
            // (distance 1, length 100 is a run), and a block copy would read
            // bytes that are not written yet.
            let start = out.len() - distance;
            for k in 0..len {
                let b = out[start + k];
                out.push(b);
            }
        }
    }
}

fn fixed_tables() -> (Huffman, Huffman) {
    let mut l = [0u8; 288];
    for (i, v) in l.iter_mut().enumerate() {
        *v = match i {
            0..=143 => 8,
            144..=255 => 9,
            256..=279 => 7,
            _ => 8,
        };
    }
    let d = [5u8; 30];
    // Both are complete or deliberately incomplete by definition; the errors
    // cannot happen for these constants.
    (construct(&l).expect("fixed literal code").0, construct(&d).expect("fixed distance code").0)
}

fn dynamic_tables(bits: &mut Bits) -> Result<(Huffman, Huffman), String> {
    let nlen = bits.take(5)? as usize + 257;
    let ndist = bits.take(5)? as usize + 1;
    let ncode = bits.take(4)? as usize + 4;
    if nlen > 286 || ndist > 30 {
        return Err(format!("dynamic block declares {nlen} literal/length and {ndist} distance codes"));
    }
    let mut cl = [0u8; 19];
    for &slot in CLEN_ORDER.iter().take(ncode) {
        cl[slot] = bits.take(3)? as u8;
    }
    let (clcode, left) = construct(&cl)?;
    if left != 0 {
        return Err("the code-length code is incomplete".into());
    }
    let mut lengths = vec![0u8; nlen + ndist];
    let mut i = 0;
    while i < nlen + ndist {
        let sym = decode(bits, &clcode)?;
        if sym < 16 {
            lengths[i] = sym as u8;
            i += 1;
            continue;
        }
        let (value, repeat) = match sym {
            16 => {
                if i == 0 {
                    return Err("repeat-previous code with no previous length".into());
                }
                (lengths[i - 1], 3 + bits.take(2)? as usize)
            }
            17 => (0, 3 + bits.take(3)? as usize),
            _ => (0, 11 + bits.take(7)? as usize),
        };
        if i + repeat > nlen + ndist {
            return Err("a repeat code runs past the declared number of code lengths".into());
        }
        for _ in 0..repeat {
            lengths[i] = value;
            i += 1;
        }
    }
    if lengths[256] == 0 {
        return Err("dynamic block has no end-of-block code".into());
    }
    let (lit, left) = construct(&lengths[..nlen])?;
    if left != 0 && nlen as u16 != lit.count[0] + lit.count[1] {
        return Err("incomplete literal/length code".into());
    }
    let (dist, left) = construct(&lengths[nlen..])?;
    if left != 0 && ndist as u16 != dist.count[0] + dist.count[1] {
        return Err("incomplete distance code".into());
    }
    Ok((lit, dist))
}

/// Inflate one complete raw DEFLATE stream. `limit` is the largest output the
/// caller will accept; pass the declared uncompressed size where one exists.
pub fn inflate(src: &[u8], limit: usize) -> Result<Vec<u8>, String> {
    let mut bits = Bits { src, pos: 0, buf: 0, cnt: 0 };
    let mut out: Vec<u8> = Vec::with_capacity(limit.min(1 << 24));
    loop {
        let last = bits.take(1)?;
        match bits.take(2)? {
            0 => {
                bits.align();
                let hdr = src
                    .get(bits.pos..bits.pos + 4)
                    .ok_or_else(|| "stored block header runs past the end".to_string())?;
                let len = u16::from_le_bytes([hdr[0], hdr[1]]);
                let nlen = u16::from_le_bytes([hdr[2], hdr[3]]);
                if len != !nlen {
                    return Err("stored block: LEN and NLEN are not complements".into());
                }
                bits.pos += 4;
                let data = src
                    .get(bits.pos..bits.pos + len as usize)
                    .ok_or_else(|| "stored block data runs past the end".to_string())?;
                if out.len() + data.len() > limit {
                    return Err(format!("output exceeds the declared {limit} bytes"));
                }
                out.extend_from_slice(data);
                bits.pos += len as usize;
            }
            1 => {
                let (lit, dist) = fixed_tables();
                codes(&mut bits, &mut out, &lit, &dist, limit)?;
            }
            2 => {
                let (lit, dist) = dynamic_tables(&mut bits)?;
                codes(&mut bits, &mut out, &lit, &dist, limit)?;
            }
            _ => return Err("block type 3 is reserved and never valid".into()),
        }
        if last == 1 {
            return Ok(out);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn hex(s: &str) -> Vec<u8> {
        let clean: String = s.chars().filter(|c| !c.is_whitespace()).collect();
        (0..clean.len()).step_by(2).map(|i| u8::from_str_radix(&clean[i..i + 2], 16).unwrap()).collect()
    }

    // The three vectors of spec/MINI-SPECS.md section 7.1, one per block type.
    // The inputs were produced by an unrelated encoder (zlib, through Python);
    // the expected outputs are the bytes that were handed to it.

    #[test]
    fn stored_block() {
        let out = inflate(&hex("010b00f4ff7765726b2073746f726564"), 64).unwrap();
        assert_eq!(out, b"werk stored");
    }

    #[test]
    fn fixed_huffman_block_with_an_overlapping_match() {
        // "abcabcabcabcabcabc": four literals (a b c a), then one match of
        // length 14 at distance 3 — a match that reads bytes it is itself
        // writing.
        let out = inflate(&hex("4b4c4a4e444500"), 64).unwrap();
        assert_eq!(out, b"abcabcabcabcabcabc");
    }

    #[test]
    fn dynamic_huffman_block() {
        let mut want = Vec::new();
        for _ in 0..9 {
            want.extend_from_slice(b"werk ");
        }
        want.extend_from_slice(
            b"self-carrying digital artifacts: the file is the format, the file is the \
              documentation, the file is the archive. ",
        );
        assert_eq!(want.len(), 158);
        let out = inflate(
            &hex(
                "8d89bb0d80300c0557f100c0006c63394ef2443e926388d89e829286e674ba9b6a07cd9f185ae22a
                 6c76a3250a48702ec4e6882c3e76f2ac145194305eef56d9974f0f5dceaacdd9d1db77b349c6a51b
                 3d",
            ),
            158,
        )
        .unwrap();
        assert_eq!(out, want);
    }

    #[test]
    fn refusals_are_named_not_guessed() {
        // Reserved block type.
        assert!(inflate(&[0x07], 16).is_err());
        // Truncated.
        assert!(inflate(&hex("4b4c4a4e44"), 64).is_err());
        // A stream that would exceed what the container declared.
        assert!(inflate(&hex("4b4c4a4e444500"), 17).is_err());
        // LEN / NLEN disagree.
        assert!(inflate(&hex("010b00f4fe7765726b2073746f726564"), 64).is_err());
    }
}
