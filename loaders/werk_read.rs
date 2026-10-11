// werk_read.rs — bootstrap reader for the werk artifact container.
// ---------------------------------------------------------------------------
// This file ships INSIDE werk packages. It is both a working reader and a
// worked example of how to read one. Read it top to bottom; nothing is hidden
// behind a crate.
//
// SPEC FILES THIS IMPLEMENTS (all of them travel in the package, in spec/):
//   spec/SPEC.md
//       §1  container: directory tree, or that tree zipped, store mode.
//       §2  MANIFEST.json: the graph, conventions, versions, files, hashes.
//       §5  versioning and degradation: nodes[].active, fallback to the
//           newest valid earlier version, and report that you did.
//       §7  embedded loaders: single file, zero dependencies, read-only.
//       §10 the reader checklist, which this file follows step by step.
//   spec/MINI-SPECS.md
//       §1  little-endian everywhere except MessagePack (big-endian).
//       §2  UTF-8, no BOM — a BOM is rejected, never silently stripped.
//       §3  JSON, restricted: no comments, no duplicate keys, finite numbers.
//       §5  zip: EOCD, central directory, local file header byte tables.
//       §11 SHA-256, with the three test vectors wired into --selftest.
//   spec/schemas/manifest.schema.json
//       the shape of MANIFEST.json, including $defs/loaderMeta which is what
//       this loader's own core.loader node declares.
//   spec/layouts/ENVELOPE.layout.txt
//       §1 fixed prefix, §2 magic values, §3 header map, §4 the MessagePack
//       subset, §5 payload sections, §6 dtype vocabulary, §7 reference reader.
//
// CAPABILITIES DECLARED (manifest.schema.json → $defs/loaderMeta.capabilities).
// Honest and narrow beats aspirational; each of these is exercised by a CLI
// command in this file and was run against a real package before shipping.
// The next line is the machine-readable statement of the list, and it is what
// a writer that embeds this file reads to fill `meta.capabilities`:
//
// WERK-LOADER-CAPABILITIES: read-manifest verify-hashes read-envelope materialize
//
//     "read-manifest"    parse MANIFEST.json, walk nodes[], resolve versions
//     "verify-hashes"    SHA-256 + declared size of every file of every
//                        resolved version
//     "read-envelope"    parse the 4-byte magic / u32 LE version / u32 LE
//                        header_len / MessagePack header / declared sections
//                        of ANY envelope binary — recognised by its frame
//                        (`WK` and two of A-Z / 0-9), not by a table of the
//                        magics this file happens to know
//     "materialize"      `--extract <node_id> --out <dir>` writes a resolved
//                        version's files, verified, under a directory the
//                        caller names — never over the package
//
// NOT declared, and therefore not attempted: read-geometry, read-textures,
// read-audio, read-skeleton, read-animation, verify-signature.
// Signature state is *reported* (SPEC §6's three states) but never verified —
// this file contains no Ed25519 and does not pretend to.
//
// LIMITS, stated rather than discovered:
//   * Zip method 8 (deflate) entries ARE read (ruling 9 of 2026-10-13), by the
//     inflate in section 4a, written from MINI-SPECS §7.1; the result is
//     checked against the directory's size and CRC-32 before it is returned.
//     Any other method, and an encrypted entry, is refused by name for that
//     entry only (`zip-entry-unsupported`) and is never returned as bytes.
//   * Zip64 is not implemented and by ruling will not be: a zip64 container
//     is refused WHOLE and by name (`zip64-unsupported`, exit status 2) and
//     nothing is read from it. A package past the zip32 ceiling is carried in
//     directory form, which is the same format.
//   * No JSON Schema validation. For a profile this file does not have built
//     in it says so in ONE `unsupported-profile` line, checks the six base
//     conventions it itself depends on, and still lists, hash-verifies and
//     extracts every file (SPEC §10.3).
//   * The whole container is read into memory. A bootstrap loader is allowed
//     to be simple; it is not expected to be fast (SPEC §7).
//
// SAFETY: read-only. This program never writes into a package, never executes
// anything, and never opens a path that is not listed in some version's
// files[] (SPEC §10 step 9). --extract writes only under the directory the
// caller named. Prebuilt binaries in a package are inert data here: they are
// hashed and listed, never loaded (SPEC §7.1).
//
// BUILD (no cargo, no crates, std only):
//     rustc -O --edition 2021 -o werk_read.exe werk_read.rs
//
// EXIT CODES (SPEC §10.1's table, which this file did not follow until ruling
// 9 of 2026-10-13 — it returned 1 for an unreadable container and 3 for
// --strict, and two readers of one format disagreeing about an exit status
// is the S-20 class of bug):
//     0  the container and manifest were read. Dead nodes do not change this:
//        the island rule (SPEC §5, §10 step 8) says a corrupt file, a missing
//        file or an unknown node type must never abort the load.
//     1  the container opened and there is an error: the conventions block
//        declares something this reader does not support (SPEC §10 step 3:
//        refuse, do not guess), --strict was given and at least one node
//        ended up dead, or --selftest failed.
//     2  CONTAINER-SCOPED REFUSAL, nothing was loaded: not a zip, a zip64
//        container, no or unparseable MANIFEST.json. Also a command line this
//        program cannot act on — no package was loaded then either.
// ---------------------------------------------------------------------------

#![forbid(unsafe_code)]

use std::collections::BTreeMap;
use std::fmt;
use std::io::Write;
use std::path::{Path, PathBuf};

// ===========================================================================
// 1. SHA-256 — FIPS 180-4, from scratch. MINI-SPECS.md §11.
//    32-bit words, big-endian, message padded with 0x80 then zeros then the
//    64-bit big-endian bit length, 64-byte blocks, 64 rounds.
// ===========================================================================

const SHA256_H0: [u32; 8] = [
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
];

const SHA256_K: [u32; 64] = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
];

struct Sha256 {
    h: [u32; 8],
    block: [u8; 64],
    used: usize,
    total_bytes: u64,
}

impl Sha256 {
    fn new() -> Self {
        Sha256 { h: SHA256_H0, block: [0u8; 64], used: 0, total_bytes: 0 }
    }

    fn compress(&mut self) {
        let mut w = [0u32; 64];
        for i in 0..16 {
            let b = &self.block[i * 4..i * 4 + 4];
            w[i] = u32::from_be_bytes([b[0], b[1], b[2], b[3]]);
        }
        for i in 16..64 {
            let s0 = w[i - 15].rotate_right(7) ^ w[i - 15].rotate_right(18) ^ (w[i - 15] >> 3);
            let s1 = w[i - 2].rotate_right(17) ^ w[i - 2].rotate_right(19) ^ (w[i - 2] >> 10);
            w[i] = w[i - 16]
                .wrapping_add(s0)
                .wrapping_add(w[i - 7])
                .wrapping_add(s1);
        }
        let (mut a, mut b, mut c, mut d) = (self.h[0], self.h[1], self.h[2], self.h[3]);
        let (mut e, mut f, mut g, mut hh) = (self.h[4], self.h[5], self.h[6], self.h[7]);
        for i in 0..64 {
            let s1 = e.rotate_right(6) ^ e.rotate_right(11) ^ e.rotate_right(25);
            let ch = (e & f) ^ ((!e) & g);
            let t1 = hh
                .wrapping_add(s1)
                .wrapping_add(ch)
                .wrapping_add(SHA256_K[i])
                .wrapping_add(w[i]);
            let s0 = a.rotate_right(2) ^ a.rotate_right(13) ^ a.rotate_right(22);
            let maj = (a & b) ^ (a & c) ^ (b & c);
            let t2 = s0.wrapping_add(maj);
            hh = g;
            g = f;
            f = e;
            e = d.wrapping_add(t1);
            d = c;
            c = b;
            b = a;
            a = t1.wrapping_add(t2);
        }
        self.h[0] = self.h[0].wrapping_add(a);
        self.h[1] = self.h[1].wrapping_add(b);
        self.h[2] = self.h[2].wrapping_add(c);
        self.h[3] = self.h[3].wrapping_add(d);
        self.h[4] = self.h[4].wrapping_add(e);
        self.h[5] = self.h[5].wrapping_add(f);
        self.h[6] = self.h[6].wrapping_add(g);
        self.h[7] = self.h[7].wrapping_add(hh);
    }

    fn update(&mut self, mut data: &[u8]) {
        self.total_bytes = self.total_bytes.wrapping_add(data.len() as u64);
        while !data.is_empty() {
            let room = 64 - self.used;
            let n = room.min(data.len());
            self.block[self.used..self.used + n].copy_from_slice(&data[..n]);
            self.used += n;
            data = &data[n..];
            if self.used == 64 {
                self.compress();
                self.used = 0;
            }
        }
    }

    fn finish(mut self) -> [u8; 32] {
        let bit_len = self.total_bytes.wrapping_mul(8);
        self.update(&[0x80]);
        // update() advanced total_bytes; that is fine, bit_len was captured first.
        while self.used != 56 {
            self.update(&[0x00]);
        }
        let lb = bit_len.to_be_bytes();
        self.update(&lb);
        debug_assert_eq!(self.used, 0);
        let mut out = [0u8; 32];
        for i in 0..8 {
            out[i * 4..i * 4 + 4].copy_from_slice(&self.h[i].to_be_bytes());
        }
        out
    }
}

fn sha256_hex(data: &[u8]) -> String {
    let mut s = Sha256::new();
    s.update(data);
    hex_lower(&s.finish())
}

fn hex_lower(bytes: &[u8]) -> String {
    let mut out = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        out.push_str(&format!("{:02x}", b));
    }
    out
}

/// MINI-SPECS.md §11 test vectors. Proving the primitive before trusting it is
/// the whole point of the table being in the spec.
fn selftest() -> bool {
    let vectors: [(&str, &str); 3] = [
        ("", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
        ("abc", "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"),
        (
            "abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq",
            "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1",
        ),
    ];
    let mut all_ok = true;
    for (input, want) in vectors.iter() {
        let got = sha256_hex(input.as_bytes());
        let ok = got == *want;
        all_ok &= ok;
        let label = if input.is_empty() { "(empty)".to_string() } else { format!("\"{}\"", input) };
        println!("{} sha256 {} -> {}", if ok { "OK  " } else { "FAIL" }, label, got);
        if !ok {
            println!("       expected {}", want);
        }
    }
    // A multi-block case, so the streaming path is covered too: 1,000,000 'a'
    // is the classic FIPS long vector.
    let mut s = Sha256::new();
    let chunk = vec![b'a'; 1000];
    for _ in 0..1000 {
        s.update(&chunk);
    }
    let got = hex_lower(&s.finish());
    let want = "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0";
    let ok = got == want;
    all_ok &= ok;
    println!("{} sha256 1e6 x 'a' (streaming) -> {}", if ok { "OK  " } else { "FAIL" }, got);

    // MINI-SPECS.md §7.1: the three DEFLATE vectors, one per block type. The
    // inputs were produced by an unrelated encoder (zlib); the expected
    // outputs are the bytes that were handed to it.
    let inflate_vectors: [(&str, &[u8], &str); 3] = [
        (
            "stored",
            &[0x01, 0x0b, 0x00, 0xf4, 0xff, 0x77, 0x65, 0x72, 0x6b, 0x20, 0x73, 0x74, 0x6f, 0x72,
              0x65, 0x64],
            "ce0a40dc0a2c99da888b60c8a20a5dfbd5aae7dd238f8d15fc15eeedf940a8e5",
        ),
        (
            "fixed",
            &[0x4b, 0x4c, 0x4a, 0x4e, 0x44, 0x45, 0x00],
            "916f4626f2d02e07085873c17f8115790840519094e94114b706573c9749331f",
        ),
        (
            "dynamic",
            &[0x8d, 0x89, 0xbb, 0x0d, 0x80, 0x30, 0x0c, 0x05, 0x57, 0xf1, 0x00, 0xc0, 0x00, 0x6c,
              0x63, 0x39, 0x4e, 0xf2, 0x44, 0x3e, 0x92, 0x63, 0x88, 0xd8, 0x9e, 0x82, 0x92, 0x86,
              0xe6, 0x74, 0xba, 0x9b, 0x6a, 0x07, 0xcd, 0x9f, 0x18, 0x5a, 0xe2, 0x2a, 0x6c, 0x76,
              0xa3, 0x25, 0x0a, 0x48, 0x70, 0x2e, 0xc4, 0xe6, 0x88, 0x2c, 0x3e, 0x76, 0xf2, 0xac,
              0x14, 0x51, 0x94, 0x30, 0x5e, 0xef, 0x56, 0xd9, 0x97, 0x4f, 0x0f, 0x5d, 0xce, 0xaa,
              0xcd, 0xd9, 0xd1, 0xdb, 0x77, 0xb3, 0x49, 0xc6, 0xa5, 0x1b, 0x3d],
            "09b86fc31af218f9bae56da09eb8a03c49ba5b22acae373d69613d5a793eb26e",
        ),
    ];
    for (name, input, want) in inflate_vectors.iter() {
        let ok = match inflate(input, 1 << 16) {
            Ok(out) => sha256_hex(&out) == *want,
            Err(_) => false,
        };
        all_ok &= ok;
        println!("{} inflate {} block ({} bytes in)", if ok { "OK  " } else { "FAIL" }, name, input.len());
    }
    all_ok
}

// ===========================================================================
// 2. JSON — MINI-SPECS.md §3. Enough to walk MANIFEST.json, not a validator.
//    The restrictions the spec imposes and this parser enforces:
//      * UTF-8 without a BOM (a BOM changes the file's sha256, so it is an
//        error, never something to strip — MINI-SPECS.md §2)
//      * no duplicate object keys (a reader MUST reject rather than pick)
//      * no comments, no trailing commas, no single quotes
//      * numbers are finite; NaN/Infinity are not JSON here
// ===========================================================================

#[derive(Debug, Clone)]
enum Json {
    Null,
    Bool(bool),
    Num(f64),
    Str(String),
    Arr(Vec<Json>),
    Obj(Vec<(String, Json)>),
}

impl Json {
    fn get(&self, key: &str) -> Option<&Json> {
        match self {
            Json::Obj(pairs) => pairs.iter().find(|(k, _)| k == key).map(|(_, v)| v),
            _ => None,
        }
    }
    fn as_str(&self) -> Option<&str> {
        match self {
            Json::Str(s) => Some(s.as_str()),
            _ => None,
        }
    }
    fn as_f64(&self) -> Option<f64> {
        match self {
            Json::Num(n) => Some(*n),
            _ => None,
        }
    }
    fn as_i64(&self) -> Option<i64> {
        match self {
            Json::Num(n) if n.fract() == 0.0 && n.abs() <= 9.007_199_254_740_992e15 => Some(*n as i64),
            _ => None,
        }
    }
    fn as_arr(&self) -> Option<&Vec<Json>> {
        match self {
            Json::Arr(a) => Some(a),
            _ => None,
        }
    }
    /// One-line rendering, used only for reporting a mismatched conventions
    /// value back to the operator.
    fn render(&self) -> String {
        match self {
            Json::Null => "null".to_string(),
            Json::Bool(b) => b.to_string(),
            Json::Num(n) => {
                if n.fract() == 0.0 && n.abs() < 1e15 {
                    format!("{}", *n as i64)
                } else {
                    format!("{}", n)
                }
            }
            Json::Str(s) => format!("\"{}\"", s),
            Json::Arr(a) => {
                let parts: Vec<String> = a.iter().map(|v| v.render()).collect();
                format!("[{}]", parts.join(","))
            }
            Json::Obj(o) => {
                let parts: Vec<String> =
                    o.iter().map(|(k, v)| format!("\"{}\":{}", k, v.render())).collect();
                format!("{{{}}}", parts.join(","))
            }
        }
    }
}

const JSON_MAX_DEPTH: usize = 64;

struct JsonParser<'a> {
    b: &'a [u8],
    p: usize,
}

fn json_parse(bytes: &[u8]) -> Result<Json, String> {
    if bytes.starts_with(&[0xEF, 0xBB, 0xBF]) {
        // MINI-SPECS.md §2: reject, do not strip. A stripped BOM changes the
        // file's sha256 and sha256 is the store key.
        return Err("UTF-8 BOM present; werk JSON is UTF-8 without a BOM".to_string());
    }
    if std::str::from_utf8(bytes).is_err() {
        return Err("not valid UTF-8".to_string());
    }
    let mut p = JsonParser { b: bytes, p: 0 };
    p.ws();
    let v = p.value(0)?;
    p.ws();
    if p.p != p.b.len() {
        return Err(format!("trailing bytes after top-level JSON value at offset {}", p.p));
    }
    Ok(v)
}

impl<'a> JsonParser<'a> {
    fn peek(&self) -> Option<u8> {
        self.b.get(self.p).copied()
    }
    fn ws(&mut self) {
        while let Some(c) = self.peek() {
            match c {
                b' ' | b'\t' | b'\n' | b'\r' => self.p += 1,
                _ => break,
            }
        }
    }
    fn expect(&mut self, c: u8) -> Result<(), String> {
        if self.peek() == Some(c) {
            self.p += 1;
            Ok(())
        } else {
            Err(format!(
                "expected '{}' at offset {}, found {}",
                c as char,
                self.p,
                match self.peek() {
                    Some(x) => format!("'{}'", x as char),
                    None => "end of input".to_string(),
                }
            ))
        }
    }

    fn value(&mut self, depth: usize) -> Result<Json, String> {
        if depth > JSON_MAX_DEPTH {
            return Err("JSON nesting too deep".to_string());
        }
        match self.peek() {
            None => Err("unexpected end of input".to_string()),
            Some(b'{') => self.object(depth),
            Some(b'[') => self.array(depth),
            Some(b'"') => Ok(Json::Str(self.string()?)),
            Some(b't') => self.literal("true", Json::Bool(true)),
            Some(b'f') => self.literal("false", Json::Bool(false)),
            Some(b'n') => self.literal("null", Json::Null),
            Some(c) if c == b'-' || c.is_ascii_digit() => self.number(),
            Some(c) => Err(format!("unexpected byte 0x{:02x} at offset {}", c, self.p)),
        }
    }

    fn literal(&mut self, word: &str, val: Json) -> Result<Json, String> {
        if self.b[self.p..].starts_with(word.as_bytes()) {
            self.p += word.len();
            Ok(val)
        } else {
            Err(format!("bad literal at offset {}, expected {}", self.p, word))
        }
    }

    fn object(&mut self, depth: usize) -> Result<Json, String> {
        self.expect(b'{')?;
        let mut out: Vec<(String, Json)> = Vec::new();
        self.ws();
        if self.peek() == Some(b'}') {
            self.p += 1;
            return Ok(Json::Obj(out));
        }
        loop {
            self.ws();
            let key = self.string()?;
            if out.iter().any(|(k, _)| *k == key) {
                // MINI-SPECS.md §3: duplicate keys are illegal and a reader
                // MUST reject the file rather than pick a winner.
                return Err(format!("duplicate object key \"{}\"", key));
            }
            self.ws();
            self.expect(b':')?;
            self.ws();
            let val = self.value(depth + 1)?;
            out.push((key, val));
            self.ws();
            match self.peek() {
                Some(b',') => {
                    self.p += 1;
                }
                Some(b'}') => {
                    self.p += 1;
                    return Ok(Json::Obj(out));
                }
                _ => return Err(format!("expected ',' or '}}' at offset {}", self.p)),
            }
        }
    }

    fn array(&mut self, depth: usize) -> Result<Json, String> {
        self.expect(b'[')?;
        let mut out: Vec<Json> = Vec::new();
        self.ws();
        if self.peek() == Some(b']') {
            self.p += 1;
            return Ok(Json::Arr(out));
        }
        loop {
            self.ws();
            out.push(self.value(depth + 1)?);
            self.ws();
            match self.peek() {
                Some(b',') => {
                    self.p += 1;
                }
                Some(b']') => {
                    self.p += 1;
                    return Ok(Json::Arr(out));
                }
                _ => return Err(format!("expected ',' or ']' at offset {}", self.p)),
            }
        }
    }

    fn hex4(&mut self) -> Result<u16, String> {
        if self.p + 4 > self.b.len() {
            return Err("truncated \\u escape".to_string());
        }
        let mut v: u16 = 0;
        for i in 0..4 {
            let c = self.b[self.p + i];
            let d = match c {
                b'0'..=b'9' => c - b'0',
                b'a'..=b'f' => c - b'a' + 10,
                b'A'..=b'F' => c - b'A' + 10,
                _ => return Err(format!("bad hex digit in \\u escape at offset {}", self.p + i)),
            };
            v = (v << 4) | d as u16;
        }
        self.p += 4;
        Ok(v)
    }

    fn string(&mut self) -> Result<String, String> {
        self.expect(b'"')?;
        let mut out: Vec<u8> = Vec::new();
        loop {
            let c = match self.peek() {
                Some(c) => c,
                None => return Err("unterminated string".to_string()),
            };
            match c {
                b'"' => {
                    self.p += 1;
                    return String::from_utf8(out).map_err(|e| e.to_string());
                }
                b'\\' => {
                    self.p += 1;
                    let e = match self.peek() {
                        Some(e) => e,
                        None => return Err("unterminated escape".to_string()),
                    };
                    self.p += 1;
                    let push_char = |ch: char, out: &mut Vec<u8>| {
                        let mut tmp = [0u8; 4];
                        out.extend_from_slice(ch.encode_utf8(&mut tmp).as_bytes());
                    };
                    match e {
                        b'"' => out.push(b'"'),
                        b'\\' => out.push(b'\\'),
                        b'/' => out.push(b'/'),
                        b'b' => out.push(0x08),
                        b'f' => out.push(0x0c),
                        b'n' => out.push(b'\n'),
                        b'r' => out.push(b'\r'),
                        b't' => out.push(b'\t'),
                        b'u' => {
                            let hi = self.hex4()?;
                            if (0xD800..0xDC00).contains(&hi) {
                                // High surrogate: a code point above U+FFFF is
                                // written as a surrogate pair, high first
                                // (MINI-SPECS.md §3).
                                if self.peek() != Some(b'\\') {
                                    return Err("high surrogate not followed by \\u".to_string());
                                }
                                self.p += 1;
                                if self.peek() != Some(b'u') {
                                    return Err("high surrogate not followed by \\u".to_string());
                                }
                                self.p += 1;
                                let lo = self.hex4()?;
                                if !(0xDC00..0xE000).contains(&lo) {
                                    return Err("high surrogate not followed by a low surrogate"
                                        .to_string());
                                }
                                let cp = 0x1_0000u32
                                    + ((hi as u32 - 0xD800) << 10)
                                    + (lo as u32 - 0xDC00);
                                match char::from_u32(cp) {
                                    Some(ch) => push_char(ch, &mut out),
                                    None => return Err("surrogate pair is not a scalar".to_string()),
                                }
                            } else if (0xDC00..0xE000).contains(&hi) {
                                return Err("lone low surrogate in \\u escape".to_string());
                            } else {
                                match char::from_u32(hi as u32) {
                                    Some(ch) => push_char(ch, &mut out),
                                    None => return Err("bad \\u escape".to_string()),
                                }
                            }
                        }
                        _ => return Err(format!("unknown escape \\{}", e as char)),
                    }
                }
                0x00..=0x1f => {
                    return Err(format!("raw control byte 0x{:02x} inside string", c));
                }
                _ => {
                    // The whole document was checked as UTF-8 at entry, so
                    // copying raw bytes through cannot produce invalid UTF-8.
                    out.push(c);
                    self.p += 1;
                }
            }
        }
    }

    fn number(&mut self) -> Result<Json, String> {
        let start = self.p;
        if self.peek() == Some(b'-') {
            self.p += 1;
        }
        // int = '0' | digit1-9 *digit
        match self.peek() {
            Some(b'0') => self.p += 1,
            Some(c) if c.is_ascii_digit() => {
                while matches!(self.peek(), Some(d) if d.is_ascii_digit()) {
                    self.p += 1;
                }
            }
            _ => return Err(format!("bad number at offset {}", start)),
        }
        if self.peek() == Some(b'.') {
            self.p += 1;
            if !matches!(self.peek(), Some(d) if d.is_ascii_digit()) {
                return Err(format!("bad fraction at offset {}", self.p));
            }
            while matches!(self.peek(), Some(d) if d.is_ascii_digit()) {
                self.p += 1;
            }
        }
        if matches!(self.peek(), Some(b'e') | Some(b'E')) {
            self.p += 1;
            if matches!(self.peek(), Some(b'+') | Some(b'-')) {
                self.p += 1;
            }
            if !matches!(self.peek(), Some(d) if d.is_ascii_digit()) {
                return Err(format!("bad exponent at offset {}", self.p));
            }
            while matches!(self.peek(), Some(d) if d.is_ascii_digit()) {
                self.p += 1;
            }
        }
        let text = std::str::from_utf8(&self.b[start..self.p]).map_err(|e| e.to_string())?;
        let n: f64 = text.parse().map_err(|_| format!("unparseable number \"{}\"", text))?;
        if !n.is_finite() {
            return Err(format!("non-finite number \"{}\"; werk JSON numbers are finite", text));
        }
        Ok(Json::Num(n))
    }
}

// ===========================================================================
// 3. MessagePack — ENVELOPE.layout.txt §4. The subset werk permits, complete.
//    Every multi-byte integer and float inside MessagePack is BIG-ENDIAN,
//    which is the opposite of every werk payload. That is the single most
//    common implementation bug and the layout file says so twice.
// ===========================================================================

#[derive(Debug, Clone)]
enum Mp {
    Nil,
    Bool(bool),
    Int(i64),
    Uint(u64),
    F32(f32),
    F64(f64),
    Str(String),
    Bin(Vec<u8>),
    Arr(Vec<Mp>),
    Map(Vec<(Mp, Mp)>),
}

impl Mp {
    fn get(&self, key: &str) -> Option<&Mp> {
        match self {
            Mp::Map(pairs) => pairs
                .iter()
                .find(|(k, _)| matches!(k, Mp::Str(s) if s == key))
                .map(|(_, v)| v),
            _ => None,
        }
    }
    fn as_str(&self) -> Option<&str> {
        match self {
            Mp::Str(s) => Some(s.as_str()),
            _ => None,
        }
    }
    fn as_u64(&self) -> Option<u64> {
        match self {
            Mp::Uint(u) => Some(*u),
            Mp::Int(i) if *i >= 0 => Some(*i as u64),
            _ => None,
        }
    }
    fn as_arr(&self) -> Option<&Vec<Mp>> {
        match self {
            Mp::Arr(a) => Some(a),
            _ => None,
        }
    }
    /// Compact JSON-ish rendering of a decoded header, for --envelope output.
    /// Map keys are printed in file order, which for a conformant writer is
    /// already sorted by raw UTF-8 bytes (ENVELOPE.layout.txt §4.3).
    fn render(&self) -> String {
        match self {
            Mp::Nil => "null".to_string(),
            Mp::Bool(b) => b.to_string(),
            Mp::Int(i) => i.to_string(),
            Mp::Uint(u) => u.to_string(),
            Mp::F32(f) => format!("{}", f),
            Mp::F64(f) => format!("{}", f),
            Mp::Str(s) => format!("\"{}\"", s),
            Mp::Bin(b) => format!("<{} bytes>", b.len()),
            Mp::Arr(a) => {
                let parts: Vec<String> = a.iter().map(|v| v.render()).collect();
                format!("[{}]", parts.join(","))
            }
            Mp::Map(m) => {
                let parts: Vec<String> =
                    m.iter().map(|(k, v)| format!("{}:{}", k.render(), v.render())).collect();
                format!("{{{}}}", parts.join(","))
            }
        }
    }
}

const MP_MAX_DEPTH: usize = 32;

struct MpReader<'a> {
    b: &'a [u8],
    p: usize,
}

impl<'a> MpReader<'a> {
    fn byte(&mut self) -> Result<u8, String> {
        let v = *self.b.get(self.p).ok_or_else(|| "MessagePack: truncated".to_string())?;
        self.p += 1;
        Ok(v)
    }
    fn take(&mut self, n: usize) -> Result<&'a [u8], String> {
        if self.p + n > self.b.len() {
            return Err("MessagePack: truncated".to_string());
        }
        let s = &self.b[self.p..self.p + n];
        self.p += n;
        Ok(s)
    }
    fn be_uint(&mut self, n: usize) -> Result<u64, String> {
        let s = self.take(n)?;
        let mut v: u64 = 0;
        for b in s {
            v = (v << 8) | *b as u64;
        }
        Ok(v)
    }
    fn be_int(&mut self, n: usize) -> Result<i64, String> {
        let u = self.be_uint(n)?;
        Ok(match n {
            1 => u as u8 as i8 as i64,
            2 => u as u16 as i16 as i64,
            4 => u as u32 as i32 as i64,
            8 => u as i64,
            _ => return Err("MessagePack: bad integer width".to_string()),
        })
    }
    fn utf8(&mut self, n: usize) -> Result<String, String> {
        let s = self.take(n)?;
        String::from_utf8(s.to_vec()).map_err(|_| "MessagePack: str is not UTF-8".to_string())
    }

    fn value(&mut self, depth: usize) -> Result<Mp, String> {
        if depth > MP_MAX_DEPTH {
            return Err("MessagePack: nesting too deep".to_string());
        }
        let t = self.byte()?;
        match t {
            0x00..=0x7f => Ok(Mp::Uint(t as u64)),
            0xe0..=0xff => Ok(Mp::Int(t as i8 as i64)),
            0xa0..=0xbf => {
                let n = (t & 0x1f) as usize;
                Ok(Mp::Str(self.utf8(n)?))
            }
            0x90..=0x9f => {
                let n = (t & 0x0f) as usize;
                self.array(n, depth)
            }
            0x80..=0x8f => {
                let n = (t & 0x0f) as usize;
                self.map(n, depth)
            }
            0xc0 => Ok(Mp::Nil),
            0xc2 => Ok(Mp::Bool(false)),
            0xc3 => Ok(Mp::Bool(true)),
            0xcc => Ok(Mp::Uint(self.be_uint(1)?)),
            0xcd => Ok(Mp::Uint(self.be_uint(2)?)),
            0xce => Ok(Mp::Uint(self.be_uint(4)?)),
            0xcf => Ok(Mp::Uint(self.be_uint(8)?)),
            0xd0 => Ok(Mp::Int(self.be_int(1)?)),
            0xd1 => Ok(Mp::Int(self.be_int(2)?)),
            0xd2 => Ok(Mp::Int(self.be_int(4)?)),
            0xd3 => Ok(Mp::Int(self.be_int(8)?)),
            0xca => {
                let bits = self.be_uint(4)? as u32;
                Ok(Mp::F32(f32::from_bits(bits)))
            }
            0xcb => {
                let bits = self.be_uint(8)?;
                Ok(Mp::F64(f64::from_bits(bits)))
            }
            0xd9 => {
                let n = self.be_uint(1)? as usize;
                Ok(Mp::Str(self.utf8(n)?))
            }
            0xda => {
                let n = self.be_uint(2)? as usize;
                Ok(Mp::Str(self.utf8(n)?))
            }
            0xdb => {
                let n = self.be_uint(4)? as usize;
                Ok(Mp::Str(self.utf8(n)?))
            }
            0xc4 => {
                let n = self.be_uint(1)? as usize;
                Ok(Mp::Bin(self.take(n)?.to_vec()))
            }
            0xc5 => {
                let n = self.be_uint(2)? as usize;
                Ok(Mp::Bin(self.take(n)?.to_vec()))
            }
            0xc6 => {
                let n = self.be_uint(4)? as usize;
                Ok(Mp::Bin(self.take(n)?.to_vec()))
            }
            0xdc => {
                let n = self.be_uint(2)? as usize;
                self.array(n, depth)
            }
            0xdd => {
                let n = self.be_uint(4)? as usize;
                self.array(n, depth)
            }
            0xde => {
                let n = self.be_uint(2)? as usize;
                self.map(n, depth)
            }
            0xdf => {
                let n = self.be_uint(4)? as usize;
                self.map(n, depth)
            }
            // ENVELOPE.layout.txt §4.2: banned. Extension types smuggle
            // application knowledge into the payload, which law 1 forbids.
            0xc1 => Err("MessagePack: 0xc1 (never-used byte) is banned in werk headers".to_string()),
            0xc7 | 0xc8 | 0xc9 => {
                Err(format!("MessagePack: ext type 0x{:02x} is banned in werk headers", t))
            }
            0xd4..=0xd8 => {
                Err(format!("MessagePack: fixext 0x{:02x} is banned in werk headers", t))
            }
        }
    }

    fn array(&mut self, n: usize, depth: usize) -> Result<Mp, String> {
        let mut out = Vec::with_capacity(n.min(1024));
        for _ in 0..n {
            out.push(self.value(depth + 1)?);
        }
        Ok(Mp::Arr(out))
    }

    fn map(&mut self, n: usize, depth: usize) -> Result<Mp, String> {
        let mut out = Vec::with_capacity(n.min(1024));
        for _ in 0..n {
            let k = self.value(depth + 1)?;
            let v = self.value(depth + 1)?;
            out.push((k, v));
        }
        Ok(Mp::Map(out))
    }
}

fn mp_decode(bytes: &[u8]) -> Result<(Mp, usize), String> {
    let mut r = MpReader { b: bytes, p: 0 };
    let v = r.value(0)?;
    Ok((v, r.p))
}

// ===========================================================================
// 4. The container — MINI-SPECS.md §5 (zip) and SPEC.md §1 (directory).
//    "Directory and zip layouts are identical. Both are the format."
// ===========================================================================

#[derive(Debug)]
enum PkgErr {
    NotFound,
    Unsupported(String),
    Bad(String),
}

impl fmt::Display for PkgErr {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            PkgErr::NotFound => write!(f, "missing from package"),
            PkgErr::Unsupported(s) => write!(f, "unsupported: {}", s),
            PkgErr::Bad(s) => write!(f, "unreadable: {}", s),
        }
    }
}

struct ZipEntry {
    method: u16,
    flags: u16,
    crc32: u32,
    comp_size: u64,
    uncomp_size: u64,
    local_header_offset: u64,
}

struct ZipArchive {
    data: Vec<u8>,
    entries: BTreeMap<String, ZipEntry>,
    /// Names in physical central-directory order, which is the writer's
    /// preview-first order (SPEC §1, law 9). Reported, never depended on.
    order: Vec<String>,
    notes: Vec<String>,
}

fn le_u16(b: &[u8], off: usize) -> Option<u16> {
    b.get(off..off + 2).map(|s| u16::from_le_bytes([s[0], s[1]]))
}
fn le_u32(b: &[u8], off: usize) -> Option<u32> {
    b.get(off..off + 4).map(|s| u32::from_le_bytes([s[0], s[1], s[2], s[3]]))
}

impl ZipArchive {
    fn open(data: Vec<u8>) -> Result<ZipArchive, String> {
        let mut notes: Vec<String> = Vec::new();
        let n = data.len();
        if n < 22 {
            return Err("bad-container: file is too short to be a zip".to_string());
        }
        // MINI-SPECS.md §5.1: scan backwards from filesize-22 for PK\x05\x06,
        // going back at most 65535+22 bytes (the comment is the only thing
        // that can follow the record).
        let scan_floor = n.saturating_sub(22 + 65535);
        let mut eocd: Option<usize> = None;
        let mut i = n - 22;
        loop {
            if data[i] == 0x50 && data[i + 1] == 0x4b && data[i + 2] == 0x05 && data[i + 3] == 0x06 {
                let clen = le_u16(&data, i + 20).unwrap_or(0) as usize;
                if i + 22 + clen == n {
                    eocd = Some(i);
                    break;
                }
            }
            if i == scan_floor {
                break;
            }
            i -= 1;
        }
        let eocd = eocd.ok_or_else(|| {
            "bad-container: end of central directory record not found: not a zip".to_string()
        })?;

        let disk_records = le_u16(&data, eocd + 8).unwrap() as usize;
        let total_records = le_u16(&data, eocd + 10).unwrap() as usize;
        let cd_size = le_u32(&data, eocd + 12).unwrap() as u64;
        let cd_offset = le_u32(&data, eocd + 16).unwrap() as u64;

        // MINI-SPECS.md §5.5, BOTH signals, either one is enough: a sentinel
        // in the EOCD, or the zip64 locator sitting immediately before it.
        // Refused whole and by name: the offsets a zip32 reader would follow
        // are sentinels.
        let sentinel = cd_offset == 0xFFFF_FFFF
            || cd_size == 0xFFFF_FFFF
            || total_records == 0xFFFF
            || disk_records == 0xFFFF;
        let locator = eocd >= 20 && le_u32(&data, eocd - 20) == Some(0x0706_4b50);
        if sentinel || locator {
            return Err(format!(
                "zip64-unsupported: zip64 container (EOCD sentinel: {}; zip64 locator before \
                 the EOCD: {}). {}",
                sentinel, locator, ZIP64_REMEDY
            ));
        }

        let mut entries: BTreeMap<String, ZipEntry> = BTreeMap::new();
        let mut order: Vec<String> = Vec::new();
        let mut p = cd_offset as usize;
        let cd_end = (cd_offset + cd_size) as usize;
        if cd_end > n {
            return Err("central directory runs past the end of the file".to_string());
        }
        let mut seen = 0usize;
        while p + 46 <= cd_end {
            let sig = le_u32(&data, p)
                .ok_or_else(|| "bad-container: truncated central directory".to_string())?;
            if sig != 0x0201_4b50 {
                return Err(format!(
                    "bad-container: bad central directory signature 0x{:08x} at {}",
                    sig, p
                ));
            }
            let flags = le_u16(&data, p + 8).unwrap();
            let method = le_u16(&data, p + 10).unwrap();
            let crc32 = le_u32(&data, p + 16).unwrap();
            let comp_size = le_u32(&data, p + 20).unwrap() as u64;
            let uncomp_size = le_u32(&data, p + 24).unwrap() as u64;
            let nlen = le_u16(&data, p + 28).unwrap() as usize;
            let mlen = le_u16(&data, p + 30).unwrap() as usize;
            let klen = le_u16(&data, p + 32).unwrap() as usize;
            let lho = le_u32(&data, p + 42).unwrap() as u64;
            let name_bytes = data
                .get(p + 46..p + 46 + nlen)
                .ok_or_else(|| "truncated central directory name".to_string())?;
            let name = String::from_utf8(name_bytes.to_vec())
                .map_err(|_| "central directory entry name is not UTF-8".to_string())?;
            p += 46 + nlen + mlen + klen;
            seen += 1;
            if comp_size == 0xFFFF_FFFF || uncomp_size == 0xFFFF_FFFF || lho == 0xFFFF_FFFF {
                // MINI-SPECS.md §5.5 step 5: the per-entry sentinel.
                return Err(format!(
                    "zip64-unsupported: entry {:?} carries a 0xFFFFFFFF size or offset sentinel \
                     (a zip64 entry). {}",
                    name, ZIP64_REMEDY
                ));
            }

            if name.ends_with('/') {
                // MINI-SPECS.md §5.4: directory entries are optional and a
                // reader MUST NOT depend on them. Ignored entirely.
                continue;
            }
            if !is_safe_package_path(&name) {
                notes.push(format!(
                    "zip: entry name rejected as unsafe (MINI-SPECS §5.4): {:?}",
                    name
                ));
                continue;
            }
            if flags & 0x0008 != 0 {
                notes.push(format!(
                    "zip: entry {} sets general purpose flag bit 3 (data descriptor), \
                     which a werk writer MUST NOT do (MINI-SPECS §5.4); \
                     using the central directory sizes",
                    name
                ));
            }
            if flags & 0x0001 != 0 {
                notes.push(format!("zip: entry {} is encrypted; unreadable", name));
            }
            if entries.contains_key(&name) {
                notes.push(format!("zip: duplicate entry name {}; keeping the first", name));
                continue;
            }
            order.push(name.clone());
            entries.insert(
                name,
                ZipEntry { method, flags, crc32, comp_size, uncomp_size, local_header_offset: lho },
            );
        }
        if seen != total_records {
            notes.push(format!(
                "zip: EOCD declares {} central directory records, {} were parsed",
                total_records, seen
            ));
        }
        Ok(ZipArchive { data, entries, order, notes })
    }

    fn read(&self, path: &str) -> Result<Vec<u8>, PkgErr> {
        let e = match self.entries.get(path) {
            Some(e) => e,
            None => return Err(PkgErr::NotFound),
        };
        if e.flags & 0x0001 != 0 {
            return Err(PkgErr::Unsupported("encrypted entry".to_string()));
        }
        if e.method != 0 && e.method != 8 {
            // MINI-SPECS §5.3: say so rather than return wrong bytes.
            return Err(PkgErr::Unsupported(format!(
                "zip-entry-unsupported: zip compression method {}; this loader implements 0 \
                 (store) and 8 (deflate)",
                e.method
            )));
        }
        // MINI-SPECS.md §5.3: the local header's n and m can differ from the
        // central directory's; always re-read them from the local header.
        // File data begins at local_header_offset + 30 + n + m.
        let lho = e.local_header_offset as usize;
        if lho + 30 > self.data.len() {
            return Err(PkgErr::Bad("local header runs past end of file".to_string()));
        }
        let sig = le_u32(&self.data, lho).unwrap();
        if sig != 0x0403_4b50 {
            return Err(PkgErr::Bad(format!("bad local header signature 0x{:08x}", sig)));
        }
        let lmethod = le_u16(&self.data, lho + 8).unwrap();
        if lmethod != e.method {
            return Err(PkgErr::Bad(format!(
                "local header method {} disagrees with central directory method {}",
                lmethod, e.method
            )));
        }
        let nlen = le_u16(&self.data, lho + 26).unwrap() as usize;
        let mlen = le_u16(&self.data, lho + 28).unwrap() as usize;
        let start = lho + 30 + nlen + mlen;
        let len = e.comp_size as usize;
        if start + len > self.data.len() {
            return Err(PkgErr::Bad("entry data runs past end of file".to_string()));
        }
        if e.method == 8 {
            // A raw DEFLATE stream (MINI-SPECS §7.1). The directory's
            // uncompressed size bounds the output, and size and CRC-32 are
            // checked before a byte is handed over: a stream that decodes to
            // the wrong thing is damage to this entry, never a wrong payload.
            let out = inflate(&self.data[start..start + len], e.uncomp_size as usize)
                .map_err(|m| PkgErr::Bad(format!("zip-entry-invalid: deflate stream does not decode: {}", m)))?;
            if out.len() as u64 != e.uncomp_size {
                return Err(PkgErr::Bad(format!(
                    "zip-entry-invalid: inflates to {} bytes, the directory declares {}",
                    out.len(),
                    e.uncomp_size
                )));
            }
            let crc = crc32(&out);
            if crc != e.crc32 {
                return Err(PkgErr::Bad(format!(
                    "zip-entry-invalid: inflates to bytes whose CRC-32 is {:08x}, the directory \
                     declares {:08x}",
                    crc, e.crc32
                )));
            }
            return Ok(out);
        }
        if e.comp_size != e.uncomp_size {
            return Err(PkgErr::Bad(format!(
                "store-mode entry declares compressed {} != uncompressed {}",
                e.comp_size, e.uncomp_size
            )));
        }
        Ok(self.data[start..start + len].to_vec())
    }
}

/// The remedy every zip64 refusal prints. One sentence, in one place, because
/// "refused by name" is only true if the name and the way out are the same
/// wherever the refusal happens.
const ZIP64_REMEDY: &str = "This reader implements 32-bit zip only and reads nothing from a \
    zip64 container, because the offsets it would follow are sentinels. werk does not use \
    zip64: a package past the zip32 ceiling (4 GiB, 65534 entries) is carried in DIRECTORY \
    form, which is the same format and has no ceiling.";

// ===========================================================================
// 4a. Inflate — raw DEFLATE (RFC 1951), from MINI-SPECS.md §7.1.
//     Decoding only, for zip method 8. The bit-at-a-time canonical-Huffman
//     walk: the slowest correct way to do it and the easiest to check against
//     the prose, which is the right trade for a file that is also a worked
//     example.
// ===========================================================================

/// CRC-32, reflected, polynomial 0xEDB88320 — MINI-SPECS.md §6.
fn crc32(data: &[u8]) -> u32 {
    let mut crc = 0xFFFF_FFFFu32;
    for &b in data {
        crc ^= b as u32;
        for _ in 0..8 {
            crc = if crc & 1 != 0 { (crc >> 1) ^ 0xEDB8_8320 } else { crc >> 1 };
        }
    }
    !crc
}

struct BitReader<'a> {
    src: &'a [u8],
    pos: usize,
    buf: u32,
    cnt: u32,
}

impl<'a> BitReader<'a> {
    /// `n` bits (n <= 16), least significant bit first within each byte.
    fn take(&mut self, n: u32) -> Result<u32, String> {
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
}

/// A canonical Huffman code: how many codes there are of each length, and the
/// symbols in order of (length, symbol value), which is the order of the codes.
struct Huffman {
    count: [u16; 16],
    symbol: Vec<u16>,
}

/// `Ok((code, left))`; `left` is the number of unused codes of the longest
/// length (0 = complete). `Err` = over-subscribed.
fn huffman(lengths: &[u8]) -> Result<(Huffman, i32), String> {
    let mut count = [0u16; 16];
    for &l in lengths {
        count[l as usize] += 1;
    }
    let mut left: i32 = 1;
    for len in 1..16 {
        left <<= 1;
        left -= count[len] as i32;
        if left < 0 {
            return Err("over-subscribed Huffman code lengths".to_string());
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

fn huffman_decode(bits: &mut BitReader, h: &Huffman) -> Result<u16, String> {
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
    Err("a bit sequence matches no Huffman code".to_string())
}

const INF_LEN_BASE: [u16; 29] = [
    3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99, 115, 131,
    163, 195, 227, 258,
];
const INF_LEN_EXTRA: [u8; 29] = [
    0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0,
];
const INF_DIST_BASE: [u16; 30] = [
    1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025, 1537,
    2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577,
];
const INF_DIST_EXTRA: [u8; 30] = [
    0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13,
    13,
];
const INF_CLEN_ORDER: [usize; 19] =
    [16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15];

fn inflate_codes(
    bits: &mut BitReader,
    out: &mut Vec<u8>,
    lit: &Huffman,
    dist: &Huffman,
    limit: usize,
) -> Result<(), String> {
    loop {
        let sym = huffman_decode(bits, lit)? as usize;
        if sym < 256 {
            if out.len() >= limit {
                return Err(format!("output exceeds the declared {} bytes", limit));
            }
            out.push(sym as u8);
        } else if sym == 256 {
            return Ok(());
        } else {
            let i = sym - 257;
            if i >= 29 {
                return Err(format!("invalid length symbol {}", sym));
            }
            let len = INF_LEN_BASE[i] as usize + bits.take(INF_LEN_EXTRA[i] as u32)? as usize;
            let d = huffman_decode(bits, dist)? as usize;
            if d >= 30 {
                return Err(format!("invalid distance symbol {}", d));
            }
            let distance = INF_DIST_BASE[d] as usize + bits.take(INF_DIST_EXTRA[d] as u32)? as usize;
            if distance > out.len() {
                return Err(format!("distance {} reaches before the start of the output", distance));
            }
            if out.len() + len > limit {
                return Err(format!("output exceeds the declared {} bytes", limit));
            }
            // Byte by byte on purpose: a match may overlap its own output.
            let start = out.len() - distance;
            for k in 0..len {
                let b = out[start + k];
                out.push(b);
            }
        }
    }
}

/// Inflate one complete raw DEFLATE stream to at most `limit` bytes.
fn inflate(src: &[u8], limit: usize) -> Result<Vec<u8>, String> {
    let mut bits = BitReader { src, pos: 0, buf: 0, cnt: 0 };
    let mut out: Vec<u8> = Vec::with_capacity(limit.min(1 << 24));
    loop {
        let last = bits.take(1)?;
        match bits.take(2)? {
            0 => {
                // Stored: discard the rest of the current byte, then LEN, NLEN.
                bits.buf = 0;
                bits.cnt = 0;
                let hdr = src
                    .get(bits.pos..bits.pos + 4)
                    .ok_or_else(|| "stored block header runs past the end".to_string())?;
                let len = u16::from_le_bytes([hdr[0], hdr[1]]);
                let nlen = u16::from_le_bytes([hdr[2], hdr[3]]);
                if len != !nlen {
                    return Err("stored block: LEN and NLEN are not complements".to_string());
                }
                bits.pos += 4;
                let data = src
                    .get(bits.pos..bits.pos + len as usize)
                    .ok_or_else(|| "stored block data runs past the end".to_string())?;
                if out.len() + data.len() > limit {
                    return Err(format!("output exceeds the declared {} bytes", limit));
                }
                out.extend_from_slice(data);
                bits.pos += len as usize;
            }
            1 => {
                let mut l = [0u8; 288];
                for (i, v) in l.iter_mut().enumerate() {
                    *v = if i < 144 { 8 } else if i < 256 { 9 } else if i < 280 { 7 } else { 8 };
                }
                let (lit, _) = huffman(&l)?;
                let (dist, _) = huffman(&[5u8; 30])?;
                inflate_codes(&mut bits, &mut out, &lit, &dist, limit)?;
            }
            2 => {
                let nlen = bits.take(5)? as usize + 257;
                let ndist = bits.take(5)? as usize + 1;
                let ncode = bits.take(4)? as usize + 4;
                if nlen > 286 || ndist > 30 {
                    return Err("dynamic block declares too many codes".to_string());
                }
                let mut cl = [0u8; 19];
                for &slot in INF_CLEN_ORDER.iter().take(ncode) {
                    cl[slot] = bits.take(3)? as u8;
                }
                let (clcode, left) = huffman(&cl)?;
                if left != 0 {
                    return Err("the code-length code is incomplete".to_string());
                }
                let mut lengths = vec![0u8; nlen + ndist];
                let mut i = 0;
                while i < nlen + ndist {
                    let sym = huffman_decode(&mut bits, &clcode)?;
                    if sym < 16 {
                        lengths[i] = sym as u8;
                        i += 1;
                        continue;
                    }
                    let (value, repeat) = if sym == 16 {
                        if i == 0 {
                            return Err("repeat-previous code with no previous length".to_string());
                        }
                        (lengths[i - 1], 3 + bits.take(2)? as usize)
                    } else if sym == 17 {
                        (0, 3 + bits.take(3)? as usize)
                    } else {
                        (0, 11 + bits.take(7)? as usize)
                    };
                    if i + repeat > nlen + ndist {
                        return Err("a repeat code runs past the declared code lengths".to_string());
                    }
                    for _ in 0..repeat {
                        lengths[i] = value;
                        i += 1;
                    }
                }
                if lengths[256] == 0 {
                    return Err("dynamic block has no end-of-block code".to_string());
                }
                let (lit, left) = huffman(&lengths[..nlen])?;
                if left != 0 && nlen as u16 != lit.count[0] + lit.count[1] {
                    return Err("incomplete literal/length code".to_string());
                }
                let (dist, left) = huffman(&lengths[nlen..])?;
                if left != 0 && ndist as u16 != dist.count[0] + dist.count[1] {
                    return Err("incomplete distance code".to_string());
                }
                inflate_codes(&mut bits, &mut out, &lit, &dist, limit)?;
            }
            _ => return Err("block type 3 is reserved and never valid".to_string()),
        }
        if last == 1 {
            return Ok(out);
        }
    }
}

/// MINI-SPECS.md §5.4 and manifest.schema.json $defs/path: forward slashes,
/// relative, no `..` segment, no drive letter, no leading slash, no backslash.
/// Applied to every path this reader will ever open, from either direction.
fn is_safe_package_path(p: &str) -> bool {
    if p.is_empty() || p.len() > 1024 {
        return false;
    }
    if p.starts_with('/') || p.contains('\\') || p.contains('\0') {
        return false;
    }
    if p.len() >= 2 && p.as_bytes()[1] == b':' {
        return false;
    }
    for seg in p.split('/') {
        if seg.is_empty() || seg == "." || seg == ".." {
            return false;
        }
    }
    true
}

enum Package {
    Dir(PathBuf),
    Zip(ZipArchive),
}

/// Refuse a zip64 container from its TAIL, before the file — which may be
/// larger than memory, that being what zip64 is for — is read at all. The EOCD
/// and the zip64 locator are in the last 22 + 65535 + 20 bytes. `Ok(())` means
/// "not recognisably zip64 from the tail"; `ZipArchive::open` then makes every
/// other check.
fn refuse_zip64_from_tail(path: &Path) -> Result<(), String> {
    use std::io::{Read, Seek, SeekFrom};
    let mut f = std::fs::File::open(path)
        .map_err(|e| format!("cannot read {}: {}", path.display(), e))?;
    let len = f.metadata().map_err(|e| e.to_string())?.len();
    let want = (22u64 + 65_535 + 20).min(len);
    f.seek(SeekFrom::Start(len - want)).map_err(|e| e.to_string())?;
    let mut tail = vec![0u8; want as usize];
    f.read_exact(&mut tail).map_err(|e| e.to_string())?;
    if tail.len() < 22 {
        return Ok(());
    }
    let mut i = tail.len() - 22;
    loop {
        if le_u32(&tail, i) == Some(0x0605_4b50) {
            let sentinel = le_u16(&tail, i + 8) == Some(0xFFFF)
                || le_u16(&tail, i + 10) == Some(0xFFFF)
                || le_u32(&tail, i + 12) == Some(0xFFFF_FFFF)
                || le_u32(&tail, i + 16) == Some(0xFFFF_FFFF);
            let locator = i >= 20 && le_u32(&tail, i - 20) == Some(0x0706_4b50);
            if sentinel || locator {
                return Err(format!(
                    "zip64-unsupported: zip64 container (EOCD sentinel: {}; zip64 locator \
                     before the EOCD: {}). {}",
                    sentinel, locator, ZIP64_REMEDY
                ));
            }
            return Ok(());
        }
        if i == 0 {
            return Ok(());
        }
        i -= 1;
    }
}

impl Package {
    fn open(path: &Path) -> Result<Package, String> {
        let md = std::fs::metadata(path)
            .map_err(|e| format!("cannot stat {}: {}", path.display(), e))?;
        if md.is_dir() {
            Ok(Package::Dir(path.to_path_buf()))
        } else {
            refuse_zip64_from_tail(path)?;
            let data = std::fs::read(path)
                .map_err(|e| format!("cannot read {}: {}", path.display(), e))?;
            Ok(Package::Zip(ZipArchive::open(data)?))
        }
    }

    fn form(&self) -> &'static str {
        match self {
            Package::Dir(_) => "directory",
            Package::Zip(_) => "zip",
        }
    }

    fn read(&self, rel: &str) -> Result<Vec<u8>, PkgErr> {
        if !is_safe_package_path(rel) {
            return Err(PkgErr::Bad(format!("unsafe package path {:?}", rel)));
        }
        match self {
            Package::Zip(z) => z.read(rel),
            Package::Dir(root) => {
                let mut p = root.clone();
                for seg in rel.split('/') {
                    p.push(seg);
                }
                match std::fs::metadata(&p) {
                    Err(_) => Err(PkgErr::NotFound),
                    Ok(m) if !m.is_file() => Err(PkgErr::NotFound),
                    Ok(_) => std::fs::read(&p).map_err(|e| PkgErr::Bad(e.to_string())),
                }
            }
        }
    }

    /// Every path the container physically holds. Used to check SPEC §2's
    /// "nothing floats": every byte except MANIFEST.json and SIGNATURE.json is
    /// reachable from exactly one node version's files[].
    fn all_paths(&self) -> Vec<String> {
        match self {
            Package::Zip(z) => z.order.clone(),
            Package::Dir(root) => {
                let mut out = Vec::new();
                walk_dir(root, "", 0, &mut out);
                out.sort();
                out
            }
        }
    }

    fn container_notes(&self) -> Vec<String> {
        match self {
            Package::Zip(z) => z.notes.clone(),
            Package::Dir(_) => Vec::new(),
        }
    }

    /// Entries this reader cannot return bytes for at all (deflate, encrypted).
    /// Reported by --report so an operator sees the limit, not a mystery.
    fn unsupported_entries(&self) -> Vec<String> {
        match self {
            Package::Zip(z) => z
                .order
                .iter()
                .filter_map(|name| {
                    let e = z.entries.get(name)?;
                    if e.method != 0 && e.method != 8 {
                        Some(format!("{} (zip method {})", name, e.method))
                    } else if e.flags & 0x0001 != 0 {
                        Some(format!("{} (encrypted)", name))
                    } else {
                        None
                    }
                })
                .collect(),
            Package::Dir(_) => Vec::new(),
        }
    }
}

fn walk_dir(root: &Path, prefix: &str, depth: usize, out: &mut Vec<String>) {
    if depth > 32 {
        return;
    }
    let rd = match std::fs::read_dir(root) {
        Ok(rd) => rd,
        Err(_) => return,
    };
    for entry in rd.flatten() {
        let name = entry.file_name().to_string_lossy().to_string();
        let rel = if prefix.is_empty() { name.clone() } else { format!("{}/{}", prefix, name) };
        match entry.file_type() {
            Ok(ft) if ft.is_dir() => walk_dir(&entry.path(), &rel, depth + 1, out),
            Ok(ft) if ft.is_file() => out.push(rel),
            _ => {}
        }
    }
}

// ===========================================================================
// 5. The binary envelope — ENVELOPE.layout.txt §1-§7.
// ===========================================================================

struct Section {
    name: String,
    offset: u64,
    size: u64,
    dtype: String,
    shape: Vec<u64>,
    stride: u64,
}

struct Envelope {
    magic: String,
    version: u32,
    header_len: u32,
    kind: String,
    payload_origin: u64,
    payload_size: u64,
    header: Mp,
    sections: Vec<Section>,
    /// Non-fatal observations: things the layout file leaves ambiguous, or
    /// checks that passed via the looser of two readings.
    notes: Vec<String>,
}

/// ENVELOPE.layout.txt §2: is this the start of an envelope? `W`, `K`, then two
/// characters each an ASCII capital letter or digit. An envelope is recognised
/// by its FRAME, never by a table of the magics this file happens to know, so
/// a profile-defined or newer envelope is validated structurally instead of
/// being passed over in silence (ruling 4 of 2026-10-13).
fn is_envelope_magic(magic: &[u8]) -> bool {
    magic.len() == 4
        && magic[0] == b'W'
        && magic[1] == b'K'
        && magic[2..].iter().all(|c| c.is_ascii_uppercase() || c.is_ascii_digit())
}

/// The seven RESERVED magics of ENVELOPE.layout.txt §2 and the kind each binds
/// — a consistency check, not a recogniser. `Some("")` is an envelope magic
/// that binds no kind: `WKX0`..`WKX9`, shared by every profile and extension
/// (the header's `kind` says what it is), and any magic reserved after this
/// file was written. tests/run_gate_magic.py keeps this table equal to the
/// layout file's and to the other three readers'.
fn magic_kind(magic: &str) -> Option<&'static str> {
    match magic {
        "WKFF" => Some("core.field.flow"),
        "WKRP" => Some("core.pose.rest"),
        "WKAC" => Some("core.anim.clip"),
        "WKSK" => Some("core.skeleton"),
        "WKEM" => Some("core.embedding"),
        "WKPC" => Some("core.geom.points"),
        "WKGS" => Some("core.geom.gsplat"),
        m if is_envelope_magic(m.as_bytes()) => Some(""),
        _ => None,
    }
}

fn read_envelope(buf: &[u8]) -> Result<Envelope, String> {
    // §1: minimum legal file size is 12 bytes, and the header map has
    // mandatory keys so header_len >= 1 always.
    if buf.len() < 12 {
        return Err(format!("file is {} bytes; an envelope is at least 12", buf.len()));
    }
    let magic_bytes = &buf[0..4];
    if !magic_bytes.iter().all(|b| b.is_ascii_graphic()) {
        return Err("magic is not 4 printable ASCII bytes".to_string());
    }
    let magic = String::from_utf8(magic_bytes.to_vec()).map_err(|e| e.to_string())?;
    let expect_kind = magic_kind(&magic).ok_or_else(|| {
        format!("{:?} is not an envelope magic (`WK` and two of A-Z or 0-9)", magic)
    })?;
    let version = le_u32(buf, 4).unwrap();
    let header_len = le_u32(buf, 8).unwrap();
    if header_len == 0 {
        return Err("header_len is 0; the header map has mandatory keys".to_string());
    }
    let hend = 12usize
        .checked_add(header_len as usize)
        .ok_or_else(|| "header_len overflows".to_string())?;
    if hend > buf.len() {
        return Err(format!(
            "header_len {} runs past the end of a {}-byte file",
            header_len,
            buf.len()
        ));
    }
    let (header, consumed) = mp_decode(&buf[12..hend])?;
    if consumed != header_len as usize {
        return Err(format!(
            "MessagePack header decoded {} bytes but header_len declares {}",
            consumed, header_len
        ));
    }
    if !matches!(header, Mp::Map(_)) {
        return Err("header is not a MessagePack map".to_string());
    }

    let mut notes: Vec<String> = Vec::new();

    // §3 mandatory keys.
    let endianness = header
        .get("endianness")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "header has no \"endianness\" string".to_string())?;
    if endianness != "le" {
        return Err(format!("header declares endianness {:?}; werk payloads are \"le\"", endianness));
    }
    let kind = header
        .get("kind")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "header has no \"kind\" string".to_string())?
        .to_string();
    if !expect_kind.is_empty() && kind != expect_kind {
        return Err(format!(
            "header kind {:?} does not match magic {:?} (§2 expects {:?})",
            kind, magic, expect_kind
        ));
    }
    let payload_origin = header
        .get("payload_origin")
        .and_then(|v| v.as_u64())
        .ok_or_else(|| "header has no \"payload_origin\" uint".to_string())?;
    let payload_size = header
        .get("payload_size")
        .and_then(|v| v.as_u64())
        .ok_or_else(|| "header has no \"payload_size\" uint".to_string())?;

    // §1: P = 16 * ceil((12 + header_len) / 16), and the header also declares
    // it. Two independent statements of the same fact is how a truncated or
    // hand-edited file is caught. A reader MUST reject a disagreement.
    let computed_p = {
        let x = 12u64 + header_len as u64;
        16 * x.div_ceil(16)
    };
    if payload_origin != computed_p {
        return Err(format!(
            "payload_origin declares {} but 16*ceil((12+{})/16) is {}",
            payload_origin, header_len, computed_p
        ));
    }
    if payload_origin + payload_size != buf.len() as u64 {
        return Err(format!(
            "payload_origin {} + payload_size {} = {} but the file is {} bytes",
            payload_origin,
            payload_size,
            payload_origin + payload_size,
            buf.len()
        ));
    }

    // §5 payload sections.
    let sec_arr = header
        .get("sections")
        .and_then(|v| v.as_arr())
        .ok_or_else(|| "header has no \"sections\" array".to_string())?;
    let mut sections: Vec<Section> = Vec::new();
    for (i, s) in sec_arr.iter().enumerate() {
        let name = s
            .get("name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| format!("section {}: no \"name\"", i))?
            .to_string();
        let offset = s
            .get("offset")
            .and_then(|v| v.as_u64())
            .ok_or_else(|| format!("section {}: no \"offset\"", i))?;
        let size = s
            .get("size")
            .and_then(|v| v.as_u64())
            .ok_or_else(|| format!("section {}: no \"size\"", i))?;
        let dtype = s
            .get("dtype")
            .and_then(|v| v.as_str())
            .ok_or_else(|| format!("section {}: no \"dtype\"", i))?
            .to_string();
        let stride = s
            .get("stride")
            .and_then(|v| v.as_u64())
            .ok_or_else(|| format!("section {}: no \"stride\"", i))?;
        let shape_arr = s
            .get("shape")
            .and_then(|v| v.as_arr())
            .ok_or_else(|| format!("section {}: no \"shape\" array", i))?;
        let mut shape: Vec<u64> = Vec::new();
        for d in shape_arr {
            shape.push(d.as_u64().ok_or_else(|| format!("section {}: shape entry is not a uint", i))?);
        }
        if !DTYPES.iter().any(|(d, _)| *d == dtype) {
            return Err(format!("section {} ({}): dtype {:?} is not in §6", i, name, dtype));
        }
        if offset % 16 != 0 {
            return Err(format!("section {} ({}): offset {} is not 16-byte aligned", i, name, offset));
        }
        if offset + size > buf.len() as u64 {
            return Err(format!(
                "section {} ({}): offset {} + size {} runs past the {}-byte file",
                i,
                name,
                offset,
                size,
                buf.len()
            ));
        }
        if sections.iter().any(|p| p.name == name) {
            return Err(format!("section name {:?} appears twice; names are unique per file", name));
        }
        if i == 0 && offset != payload_origin {
            return Err(format!(
                "section 0 ({}) starts at {} but payload_origin is {}",
                name, offset, payload_origin
            ));
        }
        if let Some(prev) = sections.last() {
            let prev_end = prev.offset + prev.size;
            if offset < prev_end {
                return Err(format!("section {} ({}) overlaps the previous section", i, name));
            }
            if offset - prev_end > 15 {
                return Err(format!(
                    "section {} ({}): {} bytes of gap after {}; §5 permits 0..15",
                    i,
                    name,
                    offset - prev_end,
                    prev.name
                ));
            }
        }

        // §3's consistency rule, which the layout file itself admits is "easy
        // to get wrong" and states in two spellings. Both spellings occur in
        // real werk files (see the note pushed below), so this reader accepts
        // either and records which one held rather than rejecting a valid file.
        let prod_all = shape.iter().try_fold(1u64, |a, b| a.checked_mul(*b));
        let prod_but_last = if shape.len() > 1 {
            shape[..shape.len() - 1].iter().try_fold(1u64, |a, b| a.checked_mul(*b))
        } else {
            Some(1)
        };
        let by_all = prod_all.and_then(|p| stride.checked_mul(p)) == Some(size);
        let by_but_last = prod_but_last.and_then(|p| stride.checked_mul(p)) == Some(size);
        if !by_all && !by_but_last {
            return Err(format!(
                "section {} ({}): size {} matches neither stride*prod(shape) nor \
                 stride*prod(shape[..-1]) with stride {} shape {:?}",
                i, name, size, stride, shape
            ));
        }
        if by_all && !by_but_last {
            notes.push(format!(
                "section {:?}: size == stride * prod(shape) (stride spans one element)",
                name
            ));
        } else if by_but_last && !by_all {
            notes.push(format!(
                "section {:?}: size == stride * prod(shape[..-1]) (stride spans the last dimension)",
                name
            ));
        }
        sections.push(Section { name, offset, size, dtype, shape, stride });
    }

    // §5: the last section's offset+size, rounded UP to a multiple of 16, MUST
    // equal payload_origin + payload_size. Trailing padding is legal; trailing
    // data is not.
    if let Some(last) = sections.last() {
        let end = last.offset + last.size;
        let rounded = 16 * end.div_ceil(16);
        if rounded != payload_origin + payload_size {
            return Err(format!(
                "last section ends at {} (rounded up: {}) but payload_origin+payload_size is {}",
                end,
                rounded,
                payload_origin + payload_size
            ));
        }
    } else if payload_size != 0 {
        return Err("no sections declared but payload_size is nonzero".to_string());
    }

    Ok(Envelope {
        magic,
        version,
        header_len,
        kind,
        payload_origin,
        payload_size,
        header,
        sections,
        notes,
    })
}

/// ENVELOPE.layout.txt §6 dtype vocabulary, with element sizes.
const DTYPES: &[(&str, u64)] = &[
    ("u8", 1),
    ("i8", 1),
    ("u16", 2),
    ("i16", 2),
    ("u32", 4),
    ("i32", 4),
    ("u64", 8),
    ("i64", 8),
    ("f32", 4),
    ("f64", 8),
    ("record", 0), // heterogeneous; "stride" gives the record size
];

fn print_envelope(label: &str, env: &Envelope) {
    println!("envelope: {}", label);
    println!("  magic          : {:?}", env.magic);
    println!("  version        : {}", env.version);
    println!("  header_len     : {}", env.header_len);
    println!("  kind           : {:?}", env.kind);
    println!("  payload_origin : {}", env.payload_origin);
    println!("  payload_size   : {}", env.payload_size);
    println!("  sections       : {}", env.sections.len());
    for s in &env.sections {
        println!(
            "    {:<12} offset {:>8}  size {:>8}  dtype {:<7} stride {:>5}  shape {:?}",
            s.name, s.offset, s.size, s.dtype, s.stride, s.shape
        );
    }
    for n in &env.notes {
        println!("  note: {}", n);
    }
    println!("  header (decoded): {}", env.header.render());
}

// ===========================================================================
// 6. MANIFEST.json model — SPEC.md §2, schemas/manifest.schema.json.
// ===========================================================================

struct FileEnt {
    path: String,
    sha256: String,
    size: u64,
    role: Option<String>,
    /// The node DECLARES this file to be in a defined foreign format (SPEC
    /// §3.18: `meta.payload_format` for the payload file, `meta.file_formats`
    /// by role). A declaration beats a sniff: such a file is not an envelope,
    /// whatever its first bytes are.
    foreign: bool,
}

struct VersionEnt {
    v: i64,
    files: Vec<FileEnt>,
    note: String,
    compacted: bool,
}

struct EdgeEnt {
    to: String,
    kind: String,
    role: Option<String>,
}

struct NodeEnt {
    node_id: String,
    ntype: String,
    active: i64,
    versions: Vec<VersionEnt>,
    edges: Vec<EdgeEnt>,
}

/// Which node types are "not a surprise" to this reader. A bootstrap loader
/// interprets no payload, so there is nothing for a table of types to gate:
/// every `core.*` type is its profile's constitution, whichever profile that
/// is, and is never skipped; an `x.*` type is the open frontier and is skipped
/// and said so (SPEC §10 step 8, law 12). All three bootstrap loaders apply
/// this one rule. This file used to carry a table of the core types it had
/// been told about; it had drifted five types behind the manifest schema
/// (`core.tool`, `core.tool.config`, `core.geom.points`, `core.geom.gsplat`,
/// `core.retarget.bind` were all reported as unknown), which is the same
/// failure as the magic table and has the same cure: no table (ruling 2 of
/// 2026-10-13).
fn type_is_known(t: &str) -> bool {
    t.starts_with("core.")
}

/// SPEC.md §10 step 3 / manifest.schema.json → conventions. Every one of these
/// is pinned to a `const` by the schema, so "does this reader support it" is a
/// comparison, not a judgement call. A mismatch is a refusal, never a guess.
/// The tables are PER PROFILE, because a convention list is a property of the
/// profile and not of the reader: profile image/1 has no handedness, no up axis
/// and no quaternions, and a reader checking profile 1's twenty-one against it
/// would report fourteen missing conventions about a well-formed package.
/// (Found the first time a second profile existed; spec finding S-25.)
const CONV_STR: &[(&str, &str)] = &[
    ("endianness", "le"),
    ("length_unit", "metre"),
    ("angle_unit", "radian"),
    ("time_unit", "second"),
    ("mass_unit", "kilogram"),
    ("up_axis", "y"),
    ("forward_axis", "-z"),
    ("right_axis", "+x"),
    ("handedness", "right"),
    ("winding", "ccw"),
    ("quat_order", "wxyz"),
    ("oct_encoding_pole", "y"),
    ("color_space_default", "srgb"),
    ("uv_origin", "top-left"),
    ("text_encoding", "utf-8"),
    ("id_case", "kebab-case"),
    ("hash_algorithm", "sha256"),
    ("signature_algorithm", "ed25519"),
];
const CONV_NUM: &[(&str, f64)] = &[("units_per_meter", 1.0), ("alignment_bytes", 16.0)];
const CONV_SH_L1: [&str; 4] = ["dc", "y", "z", "x"];

/// Profile image/1 — spec/PROFILE-IMAGE.md §6. Nine, not twenty-one.
const CONV_STR_IMAGE: &[(&str, &str)] = &[
    ("endianness", "le"),
    ("color_space_default", "srgb"),
    ("pixel_origin", "top-left"),
    ("alpha_mode", "straight"),
    ("text_encoding", "utf-8"),
    ("id_case", "kebab-case"),
    ("hash_algorithm", "sha256"),
    ("signature_algorithm", "ed25519"),
];
const CONV_NUM_IMAGE: &[(&str, f64)] = &[("alignment_bytes", 16.0)];

const PROFILE_3D: &str = "3d-entity/1";
const PROFILE_IMAGE: &str = "image/1";

/// The six conventions EVERY reader depends on to read any werk at all — the
/// container, the manifest and the envelope frame — whatever the profile. A
/// reader that does not have a package's profile built in still checks these
/// (SPEC §10.3); the profile's own conventions govern payload meaning it does
/// not claim.
const CONV_STR_BASE: &[(&str, &str)] = &[
    ("endianness", "le"),
    ("text_encoding", "utf-8"),
    ("id_case", "kebab-case"),
    ("hash_algorithm", "sha256"),
    ("signature_algorithm", "ed25519"),
];
const CONV_NUM_BASE: &[(&str, f64)] = &[("alignment_bytes", 16.0)];

/// `Ok(None)` — checked and supported. `Ok(Some(note))` — the profile is one
/// this reader does not know, so nothing was checked and the note says so;
/// listing, hashing and extraction all still happen (law 3: the smallest
/// refusal scope that contains the problem). `Err(bad)` — declared values this
/// reader does not implement.
fn check_conventions(manifest: &Json) -> Result<Option<String>, Vec<String>> {
    let mut bad: Vec<String> = Vec::new();
    let conv = match manifest.get("conventions") {
        Some(c @ Json::Obj(_)) => c,
        _ => {
            return Err(vec!["MANIFEST.json has no \"conventions\" object; \
                             law 8 makes it mandatory"
                .to_string()])
        }
    };
    let profile = manifest.get("profile").and_then(|v| v.as_str()).unwrap_or("");
    let mut note: Option<String> = None;
    let (conv_str, conv_num, want_sh) = match profile {
        PROFILE_3D => (CONV_STR, CONV_NUM, true),
        PROFILE_IMAGE => (CONV_STR_IMAGE, CONV_NUM_IMAGE, false),
        _ => {
            // Not a complaint about the package: an admission about this
            // reader (S-25). One `unsupported-profile` line, and the six base
            // conventions are still checked below.
            let mut own: Vec<String> = Vec::new();
            if let Json::Obj(pairs) = conv {
                for (k, _) in pairs {
                    let base = CONV_STR_BASE.iter().any(|(n, _)| n == k)
                        || CONV_NUM_BASE.iter().any(|(n, _)| n == k);
                    if !base {
                        own.push(k.clone());
                    }
                }
            }
            own.sort();
            let schema = match manifest.get("manifest_schema").and_then(|v| v.as_str()) {
                Some(s) => format!("`{}`", s),
                None => "NO manifest_schema".to_string(),
            };
            note = Some(format!(
                "unsupported-profile: profile \"{}\" is not built into this reader (it has \
                 \"{}\" and \"{}\"). The manifest names {} as the schema that validates \
                 it; this bootstrap loader carries no JSON Schema validator and did NOT \
                 validate the manifest against it. The six base conventions were checked \
                 against this reader; the profile's own {} ({}) govern payload meaning and \
                 were NOT interpreted. Every file is still listed, hash-verified and \
                 extractable",
                profile,
                PROFILE_3D,
                PROFILE_IMAGE,
                schema,
                own.len(),
                own.join(", ")
            ));
            (CONV_STR_BASE, CONV_NUM_BASE, false)
        }
    };
    for (k, want) in conv_str {
        match conv.get(k) {
            None => bad.push(format!("conventions.{}: missing (mandatory)", k)),
            Some(v) => match v.as_str() {
                Some(got) if got == *want => {}
                _ => bad.push(format!(
                    "conventions.{}: declares {}, supported \"{}\"",
                    k,
                    v.render(),
                    want
                )),
            },
        }
    }
    for (k, want) in conv_num {
        match conv.get(k) {
            None => bad.push(format!("conventions.{}: missing (mandatory)", k)),
            Some(v) => match v.as_f64() {
                Some(got) if (got - *want).abs() < 1e-12 => {}
                _ => bad.push(format!(
                    "conventions.{}: declares {}, supported {}",
                    k,
                    v.render(),
                    want
                )),
            },
        }
    }
    if want_sh {
        // Stage 12's two OPTIONAL conventions: absent is fine, present is
        // checked. This file used to refuse any package that declared them
        // ("unknown convention key"), which no reference fixture does and
        // every package of one third-party writer does.
        if let Some(v) = conv.get("sh_coeff_order") {
            if v.as_str() != Some("coefficient-major") {
                bad.push(format!(
                    "conventions.sh_coeff_order: declares {}, supported \"coefficient-major\"",
                    v.render()
                ));
            }
        }
        if let Some(v) = conv.get("sh_degree") {
            match v.as_f64() {
                Some(d) if (0.0..=3.0).contains(&d) && d.fract() == 0.0 => {}
                _ => bad.push(format!(
                    "conventions.sh_degree: declares {}, supported 0..3",
                    v.render()
                )),
            }
        }
        match conv.get("sh_l1_order") {
            None => bad.push("conventions.sh_l1_order: missing (mandatory)".to_string()),
            Some(v) => {
                let got: Vec<&str> = v
                    .as_arr()
                    .map(|a| a.iter().filter_map(|x| x.as_str()).collect())
                    .unwrap_or_default();
                if got.len() != 4 || got != CONV_SH_L1 {
                    bad.push(format!(
                        "conventions.sh_l1_order: declares {}, supported {:?}",
                        v.render(),
                        CONV_SH_L1
                    ));
                }
            }
        }
    }
    // additionalProperties:false in the schema — an unknown key here means the
    // package speaks a convention vocabulary this reader has never heard of,
    // which is exactly the case law 8 exists to catch.
    //
    // Only for a profile this reader has built in: for any other, the keys
    // beyond the base six are the PROFILE's, were named in the note above, and
    // are not this reader's to refuse.
    if note.is_none() {
        if let Json::Obj(pairs) = conv {
            for (k, _) in pairs {
                let known = conv_str.iter().any(|(n, _)| n == k)
                    || conv_num.iter().any(|(n, _)| n == k)
                    || (want_sh && k == "sh_l1_order")
                    // Stage 12's two OPTIONAL conventions of profile 1.
                    || (want_sh && (k == "sh_coeff_order" || k == "sh_degree"));
                if !known {
                    bad.push(format!("conventions.{}: unknown convention key", k));
                }
            }
        }
    }
    if bad.is_empty() {
        Ok(note)
    } else {
        Err(bad)
    }
}

fn parse_nodes(manifest: &Json) -> Result<Vec<NodeEnt>, String> {
    let arr = manifest
        .get("nodes")
        .and_then(|v| v.as_arr())
        .ok_or_else(|| "MANIFEST.json has no \"nodes\" array".to_string())?;
    let mut out = Vec::new();
    for (i, n) in arr.iter().enumerate() {
        let node_id = n
            .get("node_id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| format!("nodes[{}]: no node_id", i))?
            .to_string();
        let ntype = n
            .get("type")
            .and_then(|v| v.as_str())
            .ok_or_else(|| format!("nodes[{}] ({}): no type", i, node_id))?
            .to_string();
        let active = n
            .get("active")
            .and_then(|v| v.as_i64())
            .ok_or_else(|| format!("node {}: no integer \"active\"", node_id))?;
        let vs = n
            .get("versions")
            .and_then(|v| v.as_arr())
            .ok_or_else(|| format!("node {}: no \"versions\" array", node_id))?;
        let mut versions = Vec::new();
        for (j, ver) in vs.iter().enumerate() {
            let v = ver
                .get("v")
                .and_then(|x| x.as_i64())
                .ok_or_else(|| format!("node {} versions[{}]: no integer \"v\"", node_id, j))?;
            let note = ver.get("note").and_then(|x| x.as_str()).unwrap_or("").to_string();
            let compacted = ver.get("compacted").is_some();
            let fs = ver
                .get("files")
                .and_then(|x| x.as_arr())
                .ok_or_else(|| format!("node {} v{}: no \"files\" array", node_id, v))?;
            // SPEC §3.18: the node's own declaration of foreign-encoded files.
            let meta = n.get("meta");
            let payload_format = meta
                .and_then(|m| m.get("payload_format"))
                .and_then(|x| x.as_str())
                .is_some();
            let file_formats = meta.and_then(|m| m.get("file_formats"));
            let declared_payload: Option<String> = if payload_format {
                let named =
                    ver.get("payload_file").and_then(|x| x.as_str()).map(|s| s.to_string());
                let single = if fs.len() == 1 {
                    fs[0].get("path").and_then(|x| x.as_str()).map(|s| s.to_string())
                } else {
                    None
                };
                let roled: Vec<String> = fs
                    .iter()
                    .filter(|f| f.get("role").and_then(|x| x.as_str()) == Some("payload"))
                    .filter_map(|f| f.get("path").and_then(|x| x.as_str()).map(|s| s.to_string()))
                    .collect();
                named.or(single).or(if roled.len() == 1 { Some(roled[0].clone()) } else { None })
            } else {
                None
            };
            let mut files = Vec::new();
            for (k, f) in fs.iter().enumerate() {
                let path = f
                    .get("path")
                    .and_then(|x| x.as_str())
                    .ok_or_else(|| format!("node {} v{} files[{}]: no path", node_id, v, k))?
                    .to_string();
                let sha = f
                    .get("sha256")
                    .and_then(|x| x.as_str())
                    .ok_or_else(|| format!("node {} v{} files[{}]: no sha256", node_id, v, k))?
                    .to_string();
                let size = f
                    .get("size")
                    .and_then(|x| x.as_i64())
                    .ok_or_else(|| format!("node {} v{} files[{}]: no size", node_id, v, k))?;
                if size < 0 {
                    return Err(format!("node {} v{}: negative size for {}", node_id, v, path));
                }
                let role = f.get("role").and_then(|x| x.as_str()).map(|s| s.to_string());
                let by_role = match (&role, file_formats) {
                    (Some(r), Some(ff)) => ff.get(r).is_some(),
                    _ => false,
                };
                let foreign = by_role || declared_payload.as_deref() == Some(path.as_str());
                files.push(FileEnt { path, sha256: sha, size: size as u64, role, foreign });
            }
            versions.push(VersionEnt { v, files, note, compacted });
        }
        let mut edges = Vec::new();
        if let Some(es) = n.get("edges").and_then(|v| v.as_arr()) {
            for e in es {
                let to = match e.get("to").and_then(|x| x.as_str()) {
                    Some(t) => t.to_string(),
                    None => continue,
                };
                let kind = e.get("kind").and_then(|x| x.as_str()).unwrap_or("enhances").to_string();
                let role = e.get("role").and_then(|x| x.as_str()).map(|s| s.to_string());
                edges.push(EdgeEnt { to, kind, role });
            }
        }
        out.push(NodeEnt { node_id, ntype, active, versions, edges });
    }
    Ok(out)
}

// ===========================================================================
// 7. The load — SPEC.md §10 steps 5 to 8, plus §5's island rule.
//    Nothing in here aborts. A corrupt file, a missing file or an unknown type
//    marks one node and the walk continues.
// ===========================================================================

#[derive(Clone, Copy, PartialEq)]
enum Health {
    Ok,
    Fallback,
    Dead,
}

struct FileResult {
    path: String,
    ok: bool,
    detail: String,
}

struct Attempt {
    v: i64,
    /// The version's work note. Law 6 makes it mandatory and law 9 makes it
    /// the changelog, so a reader that never shows it is throwing away half of
    /// what the version record is for.
    note: String,
    files: Vec<FileResult>,
    ok: bool,
}

struct LoadedNode {
    node_id: String,
    ntype: String,
    active: i64,
    resolved: Option<i64>,
    health: Health,
    unknown_type: bool,
    dead_reason: String,
    attempts: Vec<Attempt>,
    edges: Vec<EdgeEnt>,
}

impl LoadedNode {
    fn status(&self) -> String {
        let mut parts: Vec<String> = Vec::new();
        match self.health {
            Health::Ok => parts.push("ok".to_string()),
            Health::Fallback => parts.push(format!("ok-fallback(active v{} unusable)", self.active)),
            Health::Dead => parts.push("dead".to_string()),
        }
        if self.unknown_type {
            parts.push("skipped:unknown-type".to_string());
        }
        parts.join(",")
    }
}

struct Load {
    nodes: Vec<LoadedNode>,
    report: Vec<String>,
    manifest_sha256: String,
    manifest: Json,
}

fn verify_version(pkg: &Package, ver: &VersionEnt) -> Attempt {
    let mut files = Vec::new();
    let mut ok = true;
    if ver.compacted {
        // SPEC §2 / schema: a compacted version keeps its record and lost its
        // bytes, by an explicit signed choice. It is not selectable.
        return Attempt {
            v: ver.v,
            note: ver.note.clone(),
            files: vec![FileResult {
                path: "(all)".to_string(),
                ok: false,
                detail: "version was compacted; its bytes were deliberately removed".to_string(),
            }],
            ok: false,
        };
    }
    for f in &ver.files {
        match pkg.read(&f.path) {
            Err(e) => {
                ok = false;
                files.push(FileResult { path: f.path.clone(), ok: false, detail: e.to_string() });
            }
            Ok(bytes) => {
                if bytes.len() as u64 != f.size {
                    ok = false;
                    files.push(FileResult {
                        path: f.path.clone(),
                        ok: false,
                        detail: format!(
                            "size mismatch: manifest declares {}, container holds {}",
                            f.size,
                            bytes.len()
                        ),
                    });
                    continue;
                }
                let got = sha256_hex(&bytes);
                if got != f.sha256 {
                    ok = false;
                    files.push(FileResult {
                        path: f.path.clone(),
                        ok: false,
                        detail: format!(
                            "sha256 mismatch: manifest declares {}, bytes hash to {}",
                            f.sha256, got
                        ),
                    });
                } else {
                    files.push(FileResult {
                        path: f.path.clone(),
                        ok: true,
                        detail: format!(
                            "{} bytes, sha256 ok{}",
                            f.size,
                            match &f.role {
                                Some(r) => format!(", role={}", r),
                                None => String::new(),
                            }
                        ),
                    });
                }
            }
        }
    }
    Attempt { v: ver.v, note: ver.note.clone(), files, ok }
}

fn load(pkg: &Package) -> Result<Load, String> {
    // SPEC §10 step 1-2: open the container, read MANIFEST.json.
    let manifest_bytes = pkg
        .read("MANIFEST.json")
        .map_err(|e| format!("MANIFEST.json: {}", e))?;
    let manifest_sha256 = sha256_hex(&manifest_bytes);
    let manifest = json_parse(&manifest_bytes).map_err(|e| format!("MANIFEST.json: {}", e))?;

    let mut report: Vec<String> = Vec::new();
    for n in pkg.container_notes() {
        report.push(n);
    }

    // SPEC §10 step 3: check conventions. Refuse, do not guess.
    match check_conventions(&manifest) {
        Err(bad) => {
            let mut msg = String::from(
                "conventions this reader does not support (SPEC §10 step 3: refuse, do not guess):",
            );
            for b in bad {
                msg.push_str("\n  ");
                msg.push_str(&b);
            }
            return Err(msg);
        }
        Ok(Some(note)) => report.push(note),
        Ok(None) => report
            .push("conventions: every declared value is one this reader supports".to_string()),
    }

    // Advisory container cross-checks. SPEC §1 says directory and zip layouts
    // are identical and both are the format, so a form mismatch is a note and
    // never an error.
    if let Some(c) = manifest.get("container") {
        if let Some(form) = c.get("form").and_then(|v| v.as_str()) {
            if form != pkg.form() {
                report.push(format!(
                    "container.form declares {:?} but this copy was opened as a {} \
                     (SPEC §1: both are the format, so this is a note, not an error)",
                    form,
                    pkg.form()
                ));
            }
        }
        if let Some(z) = c.get("zip_compression").and_then(|v| v.as_str()) {
            if z != "store" {
                report.push(format!(
                    "container.zip_compression is {:?}; this loader implements store mode only, \
                     so deflate entries will be reported unsupported rather than decoded",
                    z
                ));
            }
        }
    }

    // SPEC §10 step 4: four fixed state words, surfaced distinctly. This loader
    // does not declare verify-signature, so it reports and loads on. The word is
    // exactly `unverified`; a near-synonym would defeat the doctrine as surely
    // as collapsing two states would.
    match pkg.read("SIGNATURE.json") {
        Ok(_) => report.push(
            "signature: unverified — SIGNATURE.json is present, but this loader carries \
             no ed25519 and has NOT checked the mathematics. `unverified` is not \
             `signed-and-valid`, and it is not `absent` (SPEC §6, §10 step 4)"
                .to_string(),
        ),
        Err(PkgErr::NotFound) => report
            .push("signature: absent — this package is anonymous, and visibly so (SPEC §6)".to_string()),
        Err(e) => report.push(format!("signature: SIGNATURE.json {}", e)),
    }

    let nodes_src = parse_nodes(&manifest)?;

    // SPEC §10 steps 5-8, per node.
    let mut envelopes_validated = 0usize;
    let mut loaded: Vec<LoadedNode> = Vec::new();
    for n in &nodes_src {
        let unknown_type = !type_is_known(&n.ntype);
        if unknown_type {
            report.push(format!(
                "node {}: type {:?} is not one this reader implements — skipped and reported \
                 (SPEC §10 step 8). Its bytes are still verified below.",
                n.node_id, n.ntype
            ));
        }

        // Order of attempts: the author's recommended version first, then the
        // newest valid EARLIER version. SPEC §5: never glob the filesystem for
        // versions; resolve through nodes[].versions[].
        let mut order: Vec<&VersionEnt> = Vec::new();
        if let Some(a) = n.versions.iter().find(|v| v.v == n.active) {
            order.push(a);
        } else {
            report.push(format!(
                "node {}: active v{} is not present in versions[]",
                n.node_id, n.active
            ));
        }
        let mut earlier: Vec<&VersionEnt> =
            n.versions.iter().filter(|v| v.v < n.active).collect();
        earlier.sort_by(|a, b| b.v.cmp(&a.v));
        order.extend(earlier);

        let mut attempts: Vec<Attempt> = Vec::new();
        let mut resolved: Option<i64> = None;
        for ver in order {
            let a = verify_version(pkg, ver);
            let ok = a.ok;
            let v = a.v;
            attempts.push(a);
            if ok {
                resolved = Some(v);
                break;
            }
        }

        // read-envelope, exercised on every file of the resolved version that
        // starts like an envelope and is not DECLARED to be something else. A
        // broken frame kills the node, like any other damage; a sound one is
        // counted, so "no envelope complaints" and "no envelopes looked at"
        // stop printing the same nothing.
        let mut envelope_failure: Option<String> = None;
        if let Some(rv) = resolved {
            if let Some(ver) = n.versions.iter().find(|x| x.v == rv) {
                for f in ver.files.iter().filter(|f| !f.foreign) {
                    let bytes = match pkg.read(&f.path) {
                        Ok(b) => b,
                        Err(_) => continue,
                    };
                    if bytes.len() < 4 || !is_envelope_magic(&bytes[0..4]) {
                        continue;
                    }
                    match read_envelope(&bytes) {
                        Ok(_) => envelopes_validated += 1,
                        Err(e) => {
                            envelope_failure =
                                Some(format!("envelope-invalid: {}: {}", f.path, e));
                            break;
                        }
                    }
                }
            }
        }
        if envelope_failure.is_some() {
            resolved = None;
        }

        let mut health = Health::Dead;
        let mut dead_reason = String::new();
        match resolved {
            None if envelope_failure.is_some() => {
                dead_reason = envelope_failure.clone().unwrap_or_default();
                report.push(format!("node {}: DEAD — {}", n.node_id, dead_reason));
            }
            Some(v) if v == n.active => health = Health::Ok,
            Some(v) => {
                health = Health::Fallback;
                report.push(format!(
                    "node {}: FELL BACK to v{} because active v{} could not be verified \
                     (SPEC §5 requires reporting this)",
                    n.node_id, v, n.active
                ));
                for a in attempts.iter().filter(|a| a.v == n.active) {
                    for f in a.files.iter().filter(|f| !f.ok) {
                        report.push(format!("  node {} v{}: {} — {}", n.node_id, a.v, f.path, f.detail));
                    }
                }
            }
            None => {
                dead_reason = "no version of this node verified".to_string();
                report.push(format!("node {}: DEAD — {}", n.node_id, dead_reason));
                for a in &attempts {
                    for f in a.files.iter().filter(|f| !f.ok) {
                        report.push(format!("  node {} v{}: {} — {}", n.node_id, a.v, f.path, f.detail));
                    }
                }
            }
        }

        loaded.push(LoadedNode {
            node_id: n.node_id.clone(),
            ntype: n.ntype.clone(),
            active: n.active,
            resolved,
            health,
            unknown_type,
            dead_reason,
            attempts,
            edges: n.edges.iter().map(|e| EdgeEnt {
                to: e.to.clone(),
                kind: e.kind.clone(),
                role: e.role.clone(),
            }).collect(),
        });
    }

    // SPEC §5: "A requires edge into a dead node kills the source node too; an
    // enhances edge into a dead node costs exactly one feature." A requires
    // edge to a node absent from nodes[] kills exactly as a dead target does
    // (report code requires-missing-node). Run to a fixpoint so a chain of
    // requires propagates.
    //
    // Note a deliberate distinction: a node whose TYPE this reader skipped is
    // not dead. Its bytes are intact and another reader will use them, so a
    // requires edge into it is not fatal here. Only verification failure kills.
    loop {
        let mut changed = false;
        for i in 0..loaded.len() {
            if loaded[i].health == Health::Dead {
                continue;
            }
            let mut kill: Option<String> = None;
            for e in loaded[i].edges.iter().filter(|e| e.kind == "requires") {
                match loaded.iter().find(|t| t.node_id == e.to) {
                    None => {
                        kill = Some(format!(
                            "requires-missing-node: requires edge to {:?}, which is not in nodes[]",
                            e.to
                        ));
                        break;
                    }
                    Some(t) if t.health == Health::Dead => {
                        kill = Some(format!("requires-dead-node: requires edge into dead node {:?}", e.to));
                        break;
                    }
                    Some(_) => {}
                }
            }
            if let Some(reason) = kill {
                loaded[i].health = Health::Dead;
                loaded[i].resolved = None;
                loaded[i].dead_reason = reason.clone();
                let id = loaded[i].node_id.clone();
                report.push(format!("node {}: DEAD — {} (SPEC §5)", id, reason));
                changed = true;
            }
        }
        if !changed {
            break;
        }
    }
    // Feature losses are counted once, after the kill cascade has settled, so
    // a node is not reported twice for the same edge.
    for i in 0..loaded.len() {
        if loaded[i].health == Health::Dead {
            continue;
        }
        for e in loaded[i].edges.iter().filter(|e| e.kind == "enhances") {
            match loaded.iter().find(|t| t.node_id == e.to) {
                None => report.push(format!(
                    "node {}: edge-dangling: enhances edge to {:?}, which is not in nodes[]; one feature lost{}",
                    loaded[i].node_id,
                    e.to,
                    match &e.role {
                        Some(r) => format!(" (role {})", r),
                        None => String::new(),
                    }
                )),
                Some(t) if t.health == Health::Dead => report.push(format!(
                    "node {}: enhances edge into dead node {:?} — one feature lost{}",
                    loaded[i].node_id,
                    e.to,
                    match &e.role {
                        Some(r) => format!(" (role {})", r),
                        None => String::new(),
                    }
                )),
                Some(_) => {}
            }
        }
    }

    report.push(format!("envelopes: {} frame(s) validated", envelopes_validated));

    Ok(Load { nodes: loaded, report, manifest_sha256, manifest })
}

// ===========================================================================
// 8. Commands
// ===========================================================================

fn cmd_list(load: &Load) {
    println!(
        "{:<24} {:<22} {:>6} {:>8}  {}",
        "node_id", "type", "active", "resolved", "status"
    );
    for n in &load.nodes {
        println!(
            "{:<24} {:<22} {:>6} {:>8}  {}",
            n.node_id,
            n.ntype,
            n.active,
            match n.resolved {
                Some(v) => format!("v{}", v),
                None => "-".to_string(),
            },
            n.status()
        );
    }
    let dead = load.nodes.iter().filter(|n| n.health == Health::Dead).count();
    let fell = load.nodes.iter().filter(|n| n.health == Health::Fallback).count();
    let skipped = load.nodes.iter().filter(|n| n.unknown_type).count();
    println!(
        "\n{} nodes: {} live, {} dead, {} resolved by fallback, {} skipped for unknown type",
        load.nodes.len(),
        load.nodes.len() - dead,
        dead,
        fell,
        skipped
    );
}

fn cmd_verify(load: &Load) {
    let mut pass = 0usize;
    let mut fail = 0usize;
    for n in &load.nodes {
        for a in &n.attempts {
            // Law 6: the work note travels with the version, so show it.
            println!("-- {} v{}: {}", n.node_id, a.v, a.note);
            for f in &a.files {
                if f.ok {
                    pass += 1;
                } else {
                    fail += 1;
                }
                println!(
                    "{} {}  v{}  {}  {}",
                    if f.ok { "PASS" } else { "FAIL" },
                    n.node_id,
                    a.v,
                    f.path,
                    f.detail
                );
            }
        }
    }
    // A node can be dead although every one of its bytes verified: an
    // envelope whose FRAME is broken (ENVELOPE.layout.txt section 7). This
    // command used to count such a node dead and never say why.
    for n in &load.nodes {
        if n.health == Health::Dead && n.dead_reason.starts_with("envelope-invalid") {
            println!("FAIL {}  {}", n.node_id, n.dead_reason);
        }
    }
    let dead = load.nodes.iter().filter(|n| n.health == Health::Dead).count();
    println!(
        "\nsummary: {} file checks passed, {} failed; {} of {} nodes dead",
        pass,
        fail,
        dead,
        load.nodes.len()
    );
}

fn cmd_report(pkg: &Package, load: &Load) {
    println!("werk package report");
    println!("  container form   : {}", pkg.form());
    println!("  MANIFEST.json    : sha256 {}", load.manifest_sha256);
    if let Some(w) = load.manifest.get("werk") {
        println!(
            "  werk             : {}.{}",
            w.get("major").and_then(|v| v.as_i64()).unwrap_or(-1),
            w.get("minor").and_then(|v| v.as_i64()).unwrap_or(-1)
        );
    }
    if let Some(p) = load.manifest.get("profile").and_then(|v| v.as_str()) {
        println!("  profile          : {}", p);
    }
    if let Some(e) = load.manifest.get("entity") {
        println!(
            "  entity           : {} ({})",
            e.get("name").and_then(|v| v.as_str()).unwrap_or("?"),
            e.get("uuid").and_then(|v| v.as_str()).unwrap_or("?")
        );
    }
    println!();

    println!("load report ({} lines)", load.report.len());
    for line in &load.report {
        println!("  {}", line);
    }
    println!();

    let unsupported = pkg.unsupported_entries();
    if unsupported.is_empty() {
        println!("unsupported container entries: none");
    } else {
        println!("unsupported container entries ({}):", unsupported.len());
        for u in &unsupported {
            println!("  {}", u);
        }
    }
    println!();

    // SPEC §2: every byte except MANIFEST.json and SIGNATURE.json is reachable
    // from exactly one node version's files[]. Nothing floats.
    let mut owned: BTreeMap<String, Vec<String>> = BTreeMap::new();
    if let Some(nodes) = load.manifest.get("nodes").and_then(|v| v.as_arr()) {
        for n in nodes {
            let id = n.get("node_id").and_then(|v| v.as_str()).unwrap_or("?").to_string();
            if let Some(vs) = n.get("versions").and_then(|v| v.as_arr()) {
                for ver in vs {
                    let vn = ver.get("v").and_then(|v| v.as_i64()).unwrap_or(0);
                    if let Some(fs) = ver.get("files").and_then(|v| v.as_arr()) {
                        for f in fs {
                            if let Some(p) = f.get("path").and_then(|v| v.as_str()) {
                                owned
                                    .entry(p.to_string())
                                    .or_default()
                                    .push(format!("{}@v{}", id, vn));
                            }
                        }
                    }
                }
            }
        }
    }
    let physical = pkg.all_paths();
    let mut floating: Vec<&String> = physical
        .iter()
        .filter(|p| {
            p.as_str() != "MANIFEST.json" && p.as_str() != "SIGNATURE.json" && !owned.contains_key(*p)
        })
        .collect();
    floating.sort();
    if floating.is_empty() {
        println!("nothing floats: every container byte is owned by a node version (SPEC §2)");
    } else {
        println!("FLOATING files, present in the container but owned by no node version:");
        for f in &floating {
            println!("  {}", f);
        }
    }
    let multi: Vec<(&String, &Vec<String>)> =
        owned.iter().filter(|(_, o)| o.len() > 1).collect();
    for (p, o) in multi {
        println!("  double-owned: {} claimed by {}", p, o.join(", "));
    }
    let missing: Vec<&String> = owned
        .keys()
        .filter(|p| !physical.iter().any(|q| q == *p))
        .collect();
    for m in missing {
        println!("  declared but absent from the container: {}", m);
    }
    println!();

    // read-envelope, exercised on every live node whose type has a layouts
    // entry. A failure here marks the node's payload unreadable and is
    // reported; it never stops the walk.
    let layouts = load.manifest.get("layouts");
    let mut any = false;
    for n in &load.nodes {
        if n.health == Health::Dead {
            continue;
        }
        let has_layout = layouts.and_then(|l| l.get(&n.ntype)).is_some();
        let v = match n.resolved {
            Some(v) => v,
            None => continue,
        };
        let paths: Vec<String> = load
            .manifest
            .get("nodes")
            .and_then(|x| x.as_arr())
            .map(|arr| {
                arr.iter()
                    .filter(|m| m.get("node_id").and_then(|x| x.as_str()) == Some(&n.node_id))
                    .flat_map(|m| m.get("versions").and_then(|x| x.as_arr()).cloned().unwrap_or_default())
                    .filter(|ver| ver.get("v").and_then(|x| x.as_i64()) == Some(v))
                    .flat_map(|ver| ver.get("files").and_then(|x| x.as_arr()).cloned().unwrap_or_default())
                    .filter_map(|f| f.get("path").and_then(|x| x.as_str()).map(|s| s.to_string()))
                    .collect()
            })
            .unwrap_or_default();
        for p in paths {
            let bytes = match pkg.read(&p) {
                Ok(b) => b,
                Err(_) => continue,
            };
            if bytes.len() < 4 || !is_envelope_magic(&bytes[0..4]) {
                continue; // not an envelope binary (a JSON or GLB sidecar)
            }
            any = true;
            match read_envelope(&bytes) {
                Ok(env) => {
                    print_envelope(&format!("{} ({})", p, n.node_id), &env);
                    if !has_layout && n.ntype != "core.spec" {
                        println!(
                            "  envelope-undeclared: the frame is valid, but the `layouts` map \
                             of this package names no grammar for node type {:?}",
                            n.ntype
                        );
                    }
                }
                Err(e) => println!(
                    "envelope: {} ({}) UNREADABLE — {} (node payload skipped, load continues)",
                    p, n.node_id, e
                ),
            }
        }
    }
    if !any {
        println!("no envelope binaries in this package's live nodes");
    }
    println!();
    cmd_list(load);
}

fn cmd_extract(pkg: &Package, load: &Load, node_id: &str, out_dir: &str) -> i32 {
    let node = match load.nodes.iter().find(|n| n.node_id == node_id) {
        Some(n) => n,
        None => {
            eprintln!("no node with node_id {:?}", node_id);
            return 2;
        }
    };
    let v = match node.resolved {
        Some(v) => v,
        None => {
            eprintln!(
                "node {} has no resolvable version ({}); nothing extracted",
                node_id, node.dead_reason
            );
            return 2;
        }
    };
    // Paths come from the resolved version's files[] only. SPEC §10 step 9:
    // never follow a path that is not in some files[].
    let attempt = match node.attempts.iter().find(|a| a.v == v) {
        Some(a) => a,
        None => {
            eprintln!("internal: no attempt record for v{}", v);
            return 1;
        }
    };
    let root = Path::new(out_dir);
    if let Err(e) = std::fs::create_dir_all(root) {
        eprintln!("cannot create {}: {}", out_dir, e);
        return 1;
    }
    let mut n_written = 0usize;
    for f in &attempt.files {
        if !is_safe_package_path(&f.path) {
            eprintln!("refusing unsafe path {:?}", f.path);
            return 1;
        }
        let bytes = match pkg.read(&f.path) {
            Ok(b) => b,
            Err(e) => {
                eprintln!("skip {}: {}", f.path, e);
                continue;
            }
        };
        let mut dst = root.to_path_buf();
        for seg in f.path.split('/') {
            dst.push(seg);
        }
        if let Some(parent) = dst.parent() {
            if let Err(e) = std::fs::create_dir_all(parent) {
                eprintln!("cannot create {}: {}", parent.display(), e);
                return 1;
            }
        }
        if let Err(e) = std::fs::write(&dst, &bytes) {
            eprintln!("cannot write {}: {}", dst.display(), e);
            return 1;
        }
        println!("wrote {} ({} bytes)", dst.display(), bytes.len());
        n_written += 1;
    }
    println!("extracted node {} v{}: {} file(s) under {}", node_id, v, n_written, out_dir);
    0
}

fn cmd_cat(pkg: &Package, path: &str) -> i32 {
    match pkg.read(path) {
        Ok(bytes) => {
            let stdout = std::io::stdout();
            let mut h = stdout.lock();
            if let Err(e) = h.write_all(&bytes) {
                eprintln!("write failed: {}", e);
                return 1;
            }
            let _ = h.flush();
            0
        }
        Err(e) => {
            eprintln!("{}: {}", path, e);
            1
        }
    }
}

fn print_usage() {
    println!(
"werk_read — zero-dependency bootstrap reader for werk packages (profile 3d-entity/1)
capabilities: read-manifest, verify-hashes, read-envelope, materialize   (read-only; never executes anything)

usage:
  werk_read <package.werk|dir> --list                     nodes: id, type, active, resolved, status
  werk_read <package.werk|dir> --verify                   PASS/FAIL per file, plus a summary
  werk_read <package.werk|dir> --report                   the full load report
  werk_read <package.werk|dir> --extract <node_id> --out <dir>
  werk_read <package.werk|dir> --cat <package-path>       raw bytes to stdout (binary safe)
  werk_read <package.werk|dir> --envelope <package-path>  parse one envelope binary
  werk_read --envelope <file>                             ... or one lying loose on disk
  werk_read --selftest                                    SHA-256 test vectors (MINI-SPECS §11)

options:
  --strict    exit 1 if any node ended up dead (for test harnesses)

exit codes (SPEC section 10.1): 0 loaded (dead nodes included); 1 loaded with
an error (unsupported conventions, or --strict with a dead node); 2 nothing
was loaded (not a zip, zip64, no or unparseable MANIFEST.json, or a command
line this program cannot act on)."
    );
}

enum Cmd {
    SelfTest,
    List,
    Verify,
    Report,
    Extract(String),
    Cat(String),
    Envelope(String),
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.is_empty() {
        print_usage();
        std::process::exit(2);
    }
    std::process::exit(run(&args));
}

fn run(args: &[String]) -> i32 {
    let mut pkg_arg: Option<String> = None;
    let mut cmd: Option<Cmd> = None;
    let mut out_dir: Option<String> = None;
    let mut strict = false;

    let mut i = 0usize;
    let need = |i: &mut usize, args: &[String], flag: &str| -> Option<String> {
        *i += 1;
        match args.get(*i) {
            Some(v) => Some(v.clone()),
            None => {
                eprintln!("{} needs an argument", flag);
                None
            }
        }
    };
    while i < args.len() {
        let a = args[i].as_str();
        match a {
            "--selftest" => cmd = Some(Cmd::SelfTest),
            "--list" => cmd = Some(Cmd::List),
            "--verify" => cmd = Some(Cmd::Verify),
            "--report" => cmd = Some(Cmd::Report),
            "--strict" => strict = true,
            "-h" | "--help" => {
                print_usage();
                return 0;
            }
            "--extract" => match need(&mut i, args, "--extract") {
                Some(v) => cmd = Some(Cmd::Extract(v)),
                None => return 2,
            },
            "--cat" => match need(&mut i, args, "--cat") {
                Some(v) => cmd = Some(Cmd::Cat(v)),
                None => return 2,
            },
            "--envelope" => match need(&mut i, args, "--envelope") {
                Some(v) => cmd = Some(Cmd::Envelope(v)),
                None => return 2,
            },
            "--out" => match need(&mut i, args, "--out") {
                Some(v) => out_dir = Some(v),
                None => return 2,
            },
            _ if a.starts_with("--") => {
                eprintln!("unknown option {}", a);
                return 2;
            }
            _ => {
                if pkg_arg.is_some() {
                    eprintln!("more than one package argument: {}", a);
                    return 2;
                }
                pkg_arg = Some(a.to_string());
            }
        }
        i += 1;
    }

    let cmd = match cmd {
        Some(c) => c,
        None => {
            eprintln!("no command given");
            print_usage();
            return 2;
        }
    };

    if let Cmd::SelfTest = cmd {
        return if selftest() {
            println!("selftest: OK");
            0
        } else {
            println!("selftest: FAIL");
            1
        };
    }

    // --envelope with no package argument reads a bare envelope binary from
    // the filesystem, which is how a worked example in spec/examples/ is
    // inspected. With a package argument the path is package-relative.
    if let Cmd::Envelope(ref p) = cmd {
        if pkg_arg.is_none() {
            let bytes = match std::fs::read(p) {
                Ok(b) => b,
                Err(e) => {
                    eprintln!("cannot read {}: {}", p, e);
                    return 1;
                }
            };
            println!("sha256           : {}", sha256_hex(&bytes));
            println!("file size        : {}", bytes.len());
            return match read_envelope(&bytes) {
                Ok(env) => {
                    print_envelope(p, &env);
                    0
                }
                Err(e) => {
                    eprintln!("envelope: {} UNREADABLE — {}", p, e);
                    1
                }
            };
        }
    }

    let pkg_path = match pkg_arg {
        Some(p) => p,
        None => {
            eprintln!("this command needs a package (a .werk file or a directory)");
            return 2;
        }
    };
    let pkg = match Package::open(Path::new(&pkg_path)) {
        Ok(p) => p,
        Err(e) => {
            // SPEC §10.1: a container-scoped refusal, printed under its stable
            // code (the message begins with it) and exit status 2.
            let coded = e.starts_with("zip64-unsupported:") || e.starts_with("bad-container:");
            if coded {
                eprintln!("[error] {}", e);
            } else {
                eprintln!("[error] not-found: cannot open package {}: {}", pkg_path, e);
            }
            eprintln!("container-scoped refusal: nothing was loaded; exit status 2");
            return 2;
        }
    };

    // --cat and --envelope-in-package do not need a parsed manifest; they are
    // deliberately usable on a package whose manifest is broken.
    match &cmd {
        Cmd::Cat(p) => return cmd_cat(&pkg, p),
        Cmd::Envelope(p) => {
            let bytes = match pkg.read(p) {
                Ok(b) => b,
                Err(e) => {
                    eprintln!("{}: {}", p, e);
                    return 1;
                }
            };
            println!("sha256           : {}", sha256_hex(&bytes));
            println!("file size        : {}", bytes.len());
            return match read_envelope(&bytes) {
                Ok(env) => {
                    print_envelope(p, &env);
                    0
                }
                Err(e) => {
                    eprintln!("envelope: {} UNREADABLE — {}", p, e);
                    1
                }
            };
        }
        _ => {}
    }

    let load = match load(&pkg) {
        Ok(l) => l,
        Err(e) => {
            if e.starts_with("conventions") {
                // The container opened; the refusal is this reader's (§10 step 3).
                eprintln!("[error] unsupported-convention: {}", e);
                return 1;
            }
            eprintln!("[error] manifest-unparseable: cannot load package: {}", e);
            eprintln!("container-scoped refusal: nothing was loaded; exit status 2");
            return 2;
        }
    };

    let rc = match &cmd {
        Cmd::List => {
            cmd_list(&load);
            0
        }
        Cmd::Verify => {
            cmd_verify(&load);
            0
        }
        Cmd::Report => {
            cmd_report(&pkg, &load);
            0
        }
        Cmd::Extract(node_id) => match &out_dir {
            Some(d) => cmd_extract(&pkg, &load, node_id, d),
            None => {
                eprintln!("--extract needs --out <dir>");
                2
            }
        },
        Cmd::SelfTest | Cmd::Cat(_) | Cmd::Envelope(_) => 0,
    };
    if rc != 0 {
        return rc;
    }
    if strict && load.nodes.iter().any(|n| n.health == Health::Dead) {
        eprintln!("--strict: at least one node is dead");
        return 1;
    }
    0
}
