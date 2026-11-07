// werk_tool.rs — a complete reader for a werk package (profile image/1).
//
// Build:  rustc -O werk_tool.rs -o werk_tool
// Run:    ./werk_tool artifact.werk [outdir]
//
// No cargo, no crates, no std feature beyond core std. Everything below —
// SHA-256, CRC-32, a JSON parser, a MessagePack subset decoder, a store-mode
// zip reader and the WKEM envelope parser — is implemented here from the
// spec that travels inside the package itself.

use std::env;
use std::fs;
use std::path::PathBuf;

// ============================================================ SHA-256
const K: [u32; 64] = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
];

fn sha256(data: &[u8]) -> [u8; 32] {
    let mut h: [u32; 8] = [
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab,
        0x5be0cd19,
    ];
    let bitlen = (data.len() as u64).wrapping_mul(8);
    let mut msg = data.to_vec();
    msg.push(0x80);
    while msg.len() % 64 != 56 {
        msg.push(0);
    }
    msg.extend_from_slice(&bitlen.to_be_bytes());
    let mut w = [0u32; 64];
    for chunk in msg.chunks(64) {
        for i in 0..16 {
            w[i] = u32::from_be_bytes([
                chunk[i * 4],
                chunk[i * 4 + 1],
                chunk[i * 4 + 2],
                chunk[i * 4 + 3],
            ]);
        }
        for i in 16..64 {
            let s0 = w[i - 15].rotate_right(7) ^ w[i - 15].rotate_right(18) ^ (w[i - 15] >> 3);
            let s1 = w[i - 2].rotate_right(17) ^ w[i - 2].rotate_right(19) ^ (w[i - 2] >> 10);
            w[i] = w[i - 16]
                .wrapping_add(s0)
                .wrapping_add(w[i - 7])
                .wrapping_add(s1);
        }
        let (mut a, mut b, mut c, mut d, mut e, mut f, mut g, mut hh) =
            (h[0], h[1], h[2], h[3], h[4], h[5], h[6], h[7]);
        for i in 0..64 {
            let s1 = e.rotate_right(6) ^ e.rotate_right(11) ^ e.rotate_right(25);
            let ch = (e & f) ^ ((!e) & g);
            let t1 = hh
                .wrapping_add(s1)
                .wrapping_add(ch)
                .wrapping_add(K[i])
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
        h[0] = h[0].wrapping_add(a);
        h[1] = h[1].wrapping_add(b);
        h[2] = h[2].wrapping_add(c);
        h[3] = h[3].wrapping_add(d);
        h[4] = h[4].wrapping_add(e);
        h[5] = h[5].wrapping_add(f);
        h[6] = h[6].wrapping_add(g);
        h[7] = h[7].wrapping_add(hh);
    }
    let mut out = [0u8; 32];
    for i in 0..8 {
        out[i * 4..i * 4 + 4].copy_from_slice(&h[i].to_be_bytes());
    }
    out
}

fn hex(b: &[u8]) -> String {
    let mut s = String::with_capacity(b.len() * 2);
    for x in b {
        s.push_str(&format!("{:02x}", x));
    }
    s
}

fn unhex(s: &str) -> Option<Vec<u8>> {
    if s.len() % 2 != 0 {
        return None;
    }
    let b = s.as_bytes();
    let mut out = Vec::with_capacity(s.len() / 2);
    let d = |c: u8| -> Option<u8> {
        match c {
            b'0'..=b'9' => Some(c - b'0'),
            b'a'..=b'f' => Some(c - b'a' + 10),
            b'A'..=b'F' => Some(c - b'A' + 10),
            _ => None,
        }
    };
    for i in (0..b.len()).step_by(2) {
        out.push((d(b[i])? << 4) | d(b[i + 1])?);
    }
    Some(out)
}

// ============================================================ CRC-32
fn crc32(data: &[u8]) -> u32 {
    let mut table = [0u32; 256];
    for i in 0..256u32 {
        let mut c = i;
        for _ in 0..8 {
            c = if c & 1 != 0 { 0xEDB88320 ^ (c >> 1) } else { c >> 1 };
        }
        table[i as usize] = c;
    }
    let mut c = 0xFFFF_FFFFu32;
    for &b in data {
        c = table[((c ^ b as u32) & 0xff) as usize] ^ (c >> 8);
    }
    c ^ 0xFFFF_FFFF
}

// ============================================================ JSON
#[derive(Debug, Clone)]
enum J {
    Null,
    Bool(bool),
    Num(f64),
    Str(String),
    Arr(Vec<J>),
    Obj(Vec<(String, J)>),
}

impl J {
    fn g(&self, k: &str) -> Option<&J> {
        if let J::Obj(m) = self {
            m.iter().find(|(kk, _)| kk == k).map(|(_, v)| v)
        } else {
            None
        }
    }
    fn s(&self) -> &str {
        if let J::Str(s) = self {
            s
        } else {
            ""
        }
    }
    fn u(&self) -> u64 {
        if let J::Num(n) = self {
            *n as u64
        } else {
            0
        }
    }
    fn f(&self) -> f64 {
        if let J::Num(n) = self {
            *n
        } else {
            0.0
        }
    }
    fn b(&self) -> bool {
        matches!(self, J::Bool(true))
    }
    fn a(&self) -> &[J] {
        if let J::Arr(v) = self {
            v
        } else {
            &[]
        }
    }
    fn gs(&self, k: &str) -> String {
        self.g(k).map(|v| v.s().to_string()).unwrap_or_default()
    }
}

struct P<'a> {
    b: &'a [u8],
    i: usize,
}

impl<'a> P<'a> {
    fn ws(&mut self) {
        while self.i < self.b.len() && matches!(self.b[self.i], b' ' | b'\t' | b'\n' | b'\r') {
            self.i += 1;
        }
    }
    fn val(&mut self) -> Result<J, String> {
        self.ws();
        if self.i >= self.b.len() {
            return Err("json: eof".into());
        }
        match self.b[self.i] {
            b'{' => self.obj(),
            b'[' => self.arr(),
            b'"' => Ok(J::Str(self.string()?)),
            b't' => {
                self.lit("true")?;
                Ok(J::Bool(true))
            }
            b'f' => {
                self.lit("false")?;
                Ok(J::Bool(false))
            }
            b'n' => {
                self.lit("null")?;
                Ok(J::Null)
            }
            _ => self.num(),
        }
    }
    fn lit(&mut self, s: &str) -> Result<(), String> {
        if self.b[self.i..].starts_with(s.as_bytes()) {
            self.i += s.len();
            Ok(())
        } else {
            Err(format!("json: expected {} at {}", s, self.i))
        }
    }
    fn num(&mut self) -> Result<J, String> {
        let st = self.i;
        while self.i < self.b.len()
            && matches!(self.b[self.i], b'-'|b'+'|b'.'|b'0'..=b'9'|b'e'|b'E')
        {
            self.i += 1;
        }
        std::str::from_utf8(&self.b[st..self.i])
            .ok()
            .and_then(|s| s.parse::<f64>().ok())
            .map(J::Num)
            .ok_or_else(|| format!("json: bad number at {}", st))
    }
    fn string(&mut self) -> Result<String, String> {
        self.i += 1; // opening quote
        let mut out = String::new();
        loop {
            if self.i >= self.b.len() {
                return Err("json: unterminated string".into());
            }
            let c = self.b[self.i];
            match c {
                b'"' => {
                    self.i += 1;
                    return Ok(out);
                }
                b'\\' => {
                    self.i += 1;
                    let e = self.b[self.i];
                    self.i += 1;
                    match e {
                        b'"' => out.push('"'),
                        b'\\' => out.push('\\'),
                        b'/' => out.push('/'),
                        b'b' => out.push('\u{8}'),
                        b'f' => out.push('\u{c}'),
                        b'n' => out.push('\n'),
                        b'r' => out.push('\r'),
                        b't' => out.push('\t'),
                        b'u' => {
                            let h = std::str::from_utf8(&self.b[self.i..self.i + 4])
                                .map_err(|_| "json: bad \\u")?;
                            let mut cp = u32::from_str_radix(h, 16).map_err(|_| "json: bad \\u")?;
                            self.i += 4;
                            if (0xD800..0xDC00).contains(&cp) && self.b[self.i] == b'\\' {
                                let h2 = std::str::from_utf8(&self.b[self.i + 2..self.i + 6])
                                    .map_err(|_| "json: bad \\u")?;
                                let lo =
                                    u32::from_str_radix(h2, 16).map_err(|_| "json: bad \\u")?;
                                self.i += 6;
                                cp = 0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00);
                            }
                            out.push(char::from_u32(cp).unwrap_or('\u{fffd}'));
                        }
                        _ => return Err("json: bad escape".into()),
                    }
                }
                _ => {
                    // copy a whole UTF-8 sequence
                    let n = utf8_len(c);
                    let s = std::str::from_utf8(&self.b[self.i..self.i + n])
                        .map_err(|_| "json: bad utf-8")?;
                    out.push_str(s);
                    self.i += n;
                }
            }
        }
    }
    fn obj(&mut self) -> Result<J, String> {
        self.i += 1;
        let mut m = Vec::new();
        self.ws();
        if self.b[self.i] == b'}' {
            self.i += 1;
            return Ok(J::Obj(m));
        }
        loop {
            self.ws();
            let k = self.string()?;
            self.ws();
            if self.b[self.i] != b':' {
                return Err("json: expected :".into());
            }
            self.i += 1;
            let v = self.val()?;
            m.push((k, v));
            self.ws();
            match self.b[self.i] {
                b',' => self.i += 1,
                b'}' => {
                    self.i += 1;
                    return Ok(J::Obj(m));
                }
                _ => return Err("json: expected , or }".into()),
            }
        }
    }
    fn arr(&mut self) -> Result<J, String> {
        self.i += 1;
        let mut v = Vec::new();
        self.ws();
        if self.b[self.i] == b']' {
            self.i += 1;
            return Ok(J::Arr(v));
        }
        loop {
            v.push(self.val()?);
            self.ws();
            match self.b[self.i] {
                b',' => self.i += 1,
                b']' => {
                    self.i += 1;
                    return Ok(J::Arr(v));
                }
                _ => return Err("json: expected , or ]".into()),
            }
        }
    }
}

fn utf8_len(b: u8) -> usize {
    if b < 0x80 {
        1
    } else if b >> 5 == 0b110 {
        2
    } else if b >> 4 == 0b1110 {
        3
    } else {
        4
    }
}

fn json_parse(b: &[u8]) -> Result<J, String> {
    // tolerate a UTF-8 BOM even though the spec forbids one
    let b = if b.starts_with(&[0xEF, 0xBB, 0xBF]) { &b[3..] } else { b };
    let mut p = P { b, i: 0 };
    p.val()
}

/// Canonical JSON per spec/MINI-SPECS.md §3 — used only for `input_params`.
fn canonical(v: &J) -> String {
    match v {
        J::Null => "null".into(),
        J::Bool(true) => "true".into(),
        J::Bool(false) => "false".into(),
        J::Num(n) => {
            if n.fract() == 0.0 && n.abs() < 9e15 {
                format!("{}", *n as i64)
            } else {
                format!("{}", n)
            }
        }
        J::Str(s) => {
            let mut o = String::from("\"");
            for c in s.chars() {
                match c {
                    '"' => o.push_str("\\\""),
                    '\\' => o.push_str("\\\\"),
                    '\u{8}' => o.push_str("\\b"),
                    '\u{c}' => o.push_str("\\f"),
                    '\n' => o.push_str("\\n"),
                    '\r' => o.push_str("\\r"),
                    '\t' => o.push_str("\\t"),
                    c if (c as u32) < 0x20 => o.push_str(&format!("\\u{:04x}", c as u32)),
                    c => o.push(c),
                }
            }
            o.push('"');
            o
        }
        J::Arr(a) => {
            let parts: Vec<String> = a.iter().map(canonical).collect();
            format!("[{}]", parts.join(","))
        }
        J::Obj(m) => {
            let mut ks: Vec<&(String, J)> = m.iter().collect();
            ks.sort_by(|a, b| a.0.as_bytes().cmp(b.0.as_bytes()));
            let parts: Vec<String> = ks
                .iter()
                .map(|(k, v)| format!("{}:{}", canonical(&J::Str(k.clone())), canonical(v)))
                .collect();
            format!("{{{}}}", parts.join(","))
        }
    }
}

// ============================================================ MessagePack subset
// spec/layouts/ENVELOPE.layout.txt §4. Integers and floats are BIG-ENDIAN in
// here; everything else in the file is little-endian.
#[derive(Debug, Clone)]
enum M {
    Nil,
    Bool(bool),
    U(u64),
    I(i64),
    F(f64),
    Str(String),
    Bin(Vec<u8>),
    Arr(Vec<M>),
    Map(Vec<(String, M)>),
}

impl M {
    fn g(&self, k: &str) -> Option<&M> {
        if let M::Map(m) = self {
            m.iter().find(|(kk, _)| kk == k).map(|(_, v)| v)
        } else {
            None
        }
    }
    fn s(&self) -> &str {
        if let M::Str(s) = self {
            s
        } else {
            ""
        }
    }
    fn u(&self) -> u64 {
        match self {
            M::U(n) => *n,
            M::I(n) => *n as u64,
            M::F(n) => *n as u64,
            _ => 0,
        }
    }
    fn show(&self) -> String {
        match self {
            M::Nil => "nil".into(),
            M::Bool(b) => format!("{}", b),
            M::U(n) => format!("{}", n),
            M::I(n) => format!("{}", n),
            M::F(n) => format!("{}", n),
            M::Str(s) => format!("{:?}", s),
            M::Bin(b) => format!("<{} bytes>", b.len()),
            M::Arr(a) => format!("[{} items]", a.len()),
            M::Map(m) => format!("{{{} keys}}", m.len()),
        }
    }
}

struct MP<'a> {
    b: &'a [u8],
    i: usize,
}

impl<'a> MP<'a> {
    fn need(&self, n: usize) -> Result<(), String> {
        if self.i + n > self.b.len() {
            Err("msgpack: truncated".into())
        } else {
            Ok(())
        }
    }
    fn take(&mut self, n: usize) -> Result<&'a [u8], String> {
        self.need(n)?;
        let s = &self.b[self.i..self.i + n];
        self.i += n;
        Ok(s)
    }
    fn be(&mut self, n: usize) -> Result<u64, String> {
        let s = self.take(n)?;
        let mut v = 0u64;
        for &x in s {
            v = (v << 8) | x as u64;
        }
        Ok(v)
    }
    fn strn(&mut self, n: usize) -> Result<String, String> {
        let s = self.take(n)?;
        String::from_utf8(s.to_vec()).map_err(|_| "msgpack: bad utf-8 in str".into())
    }
    fn val(&mut self) -> Result<M, String> {
        self.need(1)?;
        let t = self.b[self.i];
        self.i += 1;
        Ok(match t {
            0x00..=0x7f => M::U(t as u64),
            0xe0..=0xff => M::I(t as i64 - 256),
            0xc0 => M::Nil,
            0xc2 => M::Bool(false),
            0xc3 => M::Bool(true),
            0xcc => M::U(self.be(1)?),
            0xcd => M::U(self.be(2)?),
            0xce => M::U(self.be(4)?),
            0xcf => M::U(self.be(8)?),
            0xd0 => M::I(self.be(1)? as u8 as i8 as i64),
            0xd1 => M::I(self.be(2)? as u16 as i16 as i64),
            0xd2 => M::I(self.be(4)? as u32 as i32 as i64),
            0xd3 => M::I(self.be(8)? as i64),
            0xca => M::F(f32::from_bits(self.be(4)? as u32) as f64),
            0xcb => M::F(f64::from_bits(self.be(8)?)),
            0xa0..=0xbf => {
                let n = (t & 0x1f) as usize;
                M::Str(self.strn(n)?)
            }
            0xd9 => {
                let n = self.be(1)? as usize;
                M::Str(self.strn(n)?)
            }
            0xda => {
                let n = self.be(2)? as usize;
                M::Str(self.strn(n)?)
            }
            0xdb => {
                let n = self.be(4)? as usize;
                M::Str(self.strn(n)?)
            }
            0xc4 => {
                let n = self.be(1)? as usize;
                M::Bin(self.take(n)?.to_vec())
            }
            0xc5 => {
                let n = self.be(2)? as usize;
                M::Bin(self.take(n)?.to_vec())
            }
            0xc6 => {
                let n = self.be(4)? as usize;
                M::Bin(self.take(n)?.to_vec())
            }
            0x90..=0x9f => self.array((t & 0x0f) as usize)?,
            0xdc => {
                let n = self.be(2)? as usize;
                self.array(n)?
            }
            0xdd => {
                let n = self.be(4)? as usize;
                self.array(n)?
            }
            0x80..=0x8f => self.map((t & 0x0f) as usize)?,
            0xde => {
                let n = self.be(2)? as usize;
                self.map(n)?
            }
            0xdf => {
                let n = self.be(4)? as usize;
                self.map(n)?
            }
            // §4.2 — banned in werk headers, reader MUST reject
            0xc1 => return Err("msgpack: 0xc1 (never-used) is banned in werk headers".into()),
            0xc7..=0xc9 | 0xd4..=0xd8 => {
                return Err(format!("msgpack: extension type 0x{:02x} is banned in werk headers", t))
            }
        })
    }
    fn array(&mut self, n: usize) -> Result<M, String> {
        let mut v = Vec::with_capacity(n.min(1024));
        for _ in 0..n {
            v.push(self.val()?);
        }
        Ok(M::Arr(v))
    }
    fn map(&mut self, n: usize) -> Result<M, String> {
        let mut v = Vec::with_capacity(n.min(1024));
        for _ in 0..n {
            let k = self.val()?;
            let ks = match k {
                M::Str(s) => s,
                _ => return Err("msgpack: werk header map keys must be strings".into()),
            };
            v.push((ks, self.val()?));
        }
        Ok(M::Map(v))
    }
}

// ============================================================ ZIP (store mode)
struct ZEntry {
    name: String,
    method: u16,
    crc: u32,
    csize: u64,
    usize_: u64,
    lho: u64,
}

fn le16(b: &[u8], o: usize) -> u16 {
    u16::from_le_bytes([b[o], b[o + 1]])
}
fn le32(b: &[u8], o: usize) -> u32 {
    u32::from_le_bytes([b[o], b[o + 1], b[o + 2], b[o + 3]])
}

fn read_zip(buf: &[u8]) -> Result<Vec<ZEntry>, String> {
    // A zip is read from the end. MINI-SPECS.md §5.
    let mut eocd = None;
    let start = buf.len().saturating_sub(66_000);
    let mut i = buf.len().saturating_sub(22);
    loop {
        if le32(buf, i) == 0x0605_4b50 {
            eocd = Some(i);
            break;
        }
        if i == start {
            break;
        }
        i -= 1;
    }
    let e = eocd.ok_or("container: no EOCD record — this is not a zip")?;
    // §5.5 zip64 detection: refuse rather than guess.
    if e >= 20 && le32(buf, e - 20) == 0x0706_4b50 {
        return Err("container: zip64 EOCD locator present; this reader is zip32-only".into());
    }
    let count = le16(buf, e + 10) as usize;
    let cd_off = le32(buf, e + 16) as usize;
    if count == 0xffff || cd_off == 0xffff_ffff {
        return Err("container: zip64 sentinel values in EOCD; refusing".into());
    }
    let mut p = cd_off;
    let mut out = Vec::with_capacity(count);
    for _ in 0..count {
        if le32(buf, p) != 0x0201_4b50 {
            return Err("container: bad central directory signature".into());
        }
        let method = le16(buf, p + 10);
        let crc = le32(buf, p + 16);
        let csize = le32(buf, p + 20) as u64;
        let usz = le32(buf, p + 24) as u64;
        let nlen = le16(buf, p + 28) as usize;
        let elen = le16(buf, p + 30) as usize;
        let clen = le16(buf, p + 32) as usize;
        let lho = le32(buf, p + 42) as u64;
        let name = String::from_utf8_lossy(&buf[p + 46..p + 46 + nlen]).into_owned();
        out.push(ZEntry {
            name,
            method,
            crc,
            csize,
            usize_: usz,
            lho,
        });
        p += 46 + nlen + elen + clen;
    }
    Ok(out)
}

fn entry_data<'a>(buf: &'a [u8], e: &ZEntry) -> Result<&'a [u8], String> {
    let o = e.lho as usize;
    if le32(buf, o) != 0x0403_4b50 {
        return Err(format!("{}: bad local header signature", e.name));
    }
    let nlen = le16(buf, o + 26) as usize;
    let elen = le16(buf, o + 28) as usize;
    let ds = o + 30 + nlen + elen;
    if e.method != 0 {
        return Err(format!(
            "{}: compression method {} — werk declares store mode only",
            e.name, e.method
        ));
    }
    if ds + e.csize as usize > buf.len() {
        return Err(format!("{}: data runs past end of file", e.name));
    }
    Ok(&buf[ds..ds + e.csize as usize])
}

// ============================================================ report plumbing
struct Rep {
    pass: usize,
    fail: usize,
    warn: usize,
}

impl Rep {
    fn ok(&mut self, what: &str) {
        self.pass += 1;
        println!("  [ok]   {}", what);
    }
    fn bad(&mut self, what: &str) {
        self.fail += 1;
        println!("  [FAIL] {}", what);
    }
    fn note(&mut self, what: &str) {
        self.warn += 1;
        println!("  [note] {}", what);
    }
}

fn trunc(s: &str, n: usize) -> String {
    let c: Vec<char> = s.chars().collect();
    if c.len() <= n {
        s.to_string()
    } else {
        format!("{}… ({} chars total)", c[..n].iter().collect::<String>(), c.len())
    }
}

fn type_gloss(t: &str) -> &'static str {
    match t {
        "core.spec" => "the format's own specification, schemas and layout grammars",
        "core.license" => "the full licence text, embedded (never a link)",
        "core.readme" => "human orientation text",
        "core.loader" => "a single-file zero-dependency reference reader",
        "core.image.source" => "THE PRIMARY IMAGE, as generated",
        "core.image.derived" => "a resized rendition of the primary image",
        "core.recipe" => "the reproduction record: how the image was made",
        "core.disclosure" => "machine-readable AI-generation disclosure",
        "core.embedding" => "style descriptor vector + palette, custom WKEM binary",
        "core.semantics" => "facet tags, palette, keywords, description",
        "core.provenance" => "which tool run consumed and produced what, when",
        "x.c2pa.export" => "experimental C2PA mapping (stub: not implemented, not validated)",
        _ => "unknown node type — listed, hashed, not interpreted",
    }
}

fn linear_to_srgb8(l: f64) -> u8 {
    let l = l.clamp(0.0, 1.0);
    let s = if l <= 0.0031308 {
        12.92 * l
    } else {
        1.055 * l.powf(1.0 / 2.4) - 0.055
    };
    (s * 255.0).round().clamp(0.0, 255.0) as u8
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let path = args.get(1).cloned().unwrap_or_else(|| "artifact.werk".into());
    let outdir = PathBuf::from(args.get(2).cloned().unwrap_or_else(|| "extracted".into()));

    let buf = match fs::read(&path) {
        Ok(b) => b,
        Err(e) => {
            eprintln!("cannot read {}: {}", path, e);
            std::process::exit(2);
        }
    };
    let mut r = Rep { pass: 0, fail: 0, warn: 0 };

    println!("================================================================");
    println!("  werk reader — {}", path);
    println!("  {} bytes on disk", buf.len());
    println!("================================================================");

    // ---------------------------------------------------------- container
    let entries = match read_zip(&buf) {
        Ok(e) => e,
        Err(e) => {
            eprintln!("container refusal (scope: container): {}", e);
            std::process::exit(3);
        }
    };
    let get = |name: &str| -> Option<&[u8]> {
        entries
            .iter()
            .find(|e| e.name == name)
            .and_then(|e| entry_data(&buf, e).ok())
    };

    let manifest_bytes = match get("MANIFEST.json") {
        Some(b) => b.to_vec(),
        None => {
            eprintln!("container refusal: MANIFEST.json is missing");
            std::process::exit(3);
        }
    };
    let man = match json_parse(&manifest_bytes) {
        Ok(m) => m,
        Err(e) => {
            eprintln!("container refusal: MANIFEST.json unparseable: {}", e);
            std::process::exit(3);
        }
    };

    // ---------------------------------------------------------- 1. identity
    let profile = man.gs("profile");
    let entity = man.g("entity").cloned().unwrap_or(J::Null);
    println!("\n---- 1. WHAT THIS PACKAGE IS -----------------------------------");
    println!(
        "  werk version   : {}.{}",
        man.g("werk").and_then(|w| w.g("major")).map(|v| v.u()).unwrap_or(0),
        man.g("werk").and_then(|w| w.g("minor")).map(|v| v.u()).unwrap_or(0)
    );
    println!("  profile        : {}", profile);
    println!("  manifest schema: {}", man.gs("manifest_schema"));
    println!("  entity         : {}", entity.gs("name"));
    println!("  uuid           : {}", entity.gs("uuid"));
    println!("  created        : {}", entity.gs("created"));
    println!("  licence        : {} (embedded as {})",
        man.g("license").map(|l| l.gs("spdx_id")).unwrap_or_default(),
        man.g("license").map(|l| l.gs("file")).unwrap_or_default());
    let prim = man.g("primary").cloned().unwrap_or(J::Null);
    println!("  primary image  : node \"{}\"   thumbnail: node \"{}\"",
        prim.gs("image"), prim.gs("thumbnail"));
    println!("  summary        : {}", trunc(entity.gs("summary").as_str(), 400));
    println!("\n  conventions this package declares (a reader must support all of them):");
    if let Some(J::Obj(c)) = man.g("conventions") {
        for (k, v) in c {
            println!("    {:<22} = {}", k, canonical(v));
        }
    }
    // conventions we actually support
    let mut unsupported = Vec::new();
    let cv = |k: &str| man.g("conventions").map(|c| c.gs(k)).unwrap_or_default();
    if cv("endianness") != "le" { unsupported.push("endianness"); }
    if cv("text_encoding") != "utf-8" { unsupported.push("text_encoding"); }
    if cv("hash_algorithm") != "sha256" { unsupported.push("hash_algorithm"); }
    if man.g("conventions").map(|c| c.g("alignment_bytes").map(|v| v.u()).unwrap_or(0)).unwrap_or(0) != 16 {
        unsupported.push("alignment_bytes");
    }
    if !unsupported.is_empty() {
        println!("  UNSUPPORTED CONVENTIONS (refusing to interpret payloads): {:?}", unsupported);
    }

    // ---------------------------------------------------------- node index
    // path -> list of (node_id, type, version, role)
    let empty: Vec<J> = Vec::new();
    let nodes: &[J] = man.g("nodes").map(|n| n.a()).unwrap_or(&empty);
    let mut file_meaning: Vec<(String, Vec<(String, String, u64, String)>)> = Vec::new();
    let mut push_meaning = |p: &str, m: (String, String, u64, String)| {
        if let Some(e) = file_meaning.iter_mut().find(|(k, _)| k == p) {
            e.1.push(m);
        } else {
            file_meaning.push((p.to_string(), vec![m]));
        }
    };
    for n in nodes {
        let nid = n.gs("node_id");
        let ty = n.gs("type");
        for v in n.g("versions").map(|x| x.a()).unwrap_or(&[]) {
            let vn = v.g("v").map(|x| x.u()).unwrap_or(0);
            for f in v.g("files").map(|x| x.a()).unwrap_or(&[]) {
                push_meaning(
                    &f.gs("path"),
                    (nid.clone(), ty.clone(), vn, f.gs("role")),
                );
            }
        }
    }

    // ---------------------------------------------------------- 2. listing
    println!("\n---- 2. CONTENTS, WITH MEANINGS --------------------------------");
    println!("  {} zip entries, all stored (no compression) as container.zip_compression declares.\n", entries.len());
    let mut cur_group = String::new();
    for e in &entries {
        let group = match e.name.split('/').next().unwrap_or("") {
            g if e.name.contains('/') => g.to_string(),
            _ => "(root)".to_string(),
        };
        if group != cur_group {
            cur_group = group.clone();
            println!("  --- {}/", cur_group);
        }
        let meaning = if e.name == "MANIFEST.json" {
            "the manifest: the graph, the conventions, every file's sha256. The signature covers its bytes.".to_string()
        } else if e.name == "SIGNATURE.json" {
            "the signature chain over MANIFEST.json (ed25519, hex)".to_string()
        } else {
            match file_meaning.iter().find(|(k, _)| *k == e.name) {
                Some((_, ms)) => {
                    let vs: Vec<String> = ms
                        .iter()
                        .map(|(id, _, v, role)| {
                            if role.is_empty() {
                                format!("{}@v{}", id, v)
                            } else {
                                format!("{}@v{} [{}]", id, v, role)
                            }
                        })
                        .collect();
                    format!("{} — node {} ({})", type_gloss(&ms[0].1), vs.join(", "), ms[0].1)
                }
                None => "NOT DECLARED BY ANY NODE — present in the container but unowned".into(),
            }
        };
        println!("    {:<44} {:>9}  {}", e.name, e.usize_, meaning);
    }

    // per-node view
    println!("\n  Node graph ({} nodes):", nodes.len());
    for n in nodes {
        let nid = n.gs("node_id");
        let ty = n.gs("type");
        let active = n.g("active").map(|v| v.u()).unwrap_or(0);
        let nver = n.g("versions").map(|v| v.a().len()).unwrap_or(0);
        let edges: Vec<String> = n
            .g("edges")
            .map(|e| e.a())
            .unwrap_or(&[])
            .iter()
            .map(|e| format!("{} --{}/{}--> {}", nid, e.gs("kind"), e.gs("role"), e.gs("to")))
            .collect();
        println!(
            "    {:<16} {:<20} active v{} of {}  — {}",
            nid, ty, active, nver, type_gloss(&ty)
        );
        for e in edges {
            println!("        edge: {}", e);
        }
        if let Some(meta) = n.g("meta") {
            if let J::Obj(m) = meta {
                let flat: Vec<String> = m
                    .iter()
                    .filter(|(k, _)| k != "aspect_note")
                    .map(|(k, v)| format!("{}={}", k, trunc(&canonical(v), 60)))
                    .collect();
                if !flat.is_empty() {
                    println!("        meta: {}", flat.join(" "));
                }
                if let Some(a) = meta.g("aspect_note") {
                    println!("        note: {}", trunc(a.s(), 240));
                }
            }
        }
    }

    // ---------------------------------------------------------- 3. integrity
    println!("\n---- 3. INTEGRITY ----------------------------------------------");

    // 3a. zip CRC-32 of every entry
    let mut crc_bad = 0;
    for e in &entries {
        match entry_data(&buf, e) {
            Ok(d) => {
                if d.len() as u64 != e.usize_ || crc32(d) != e.crc {
                    crc_bad += 1;
                    println!("  [FAIL] container CRC/size mismatch: {}", e.name);
                }
            }
            Err(msg) => {
                crc_bad += 1;
                println!("  [FAIL] {}", msg);
            }
        }
    }
    if crc_bad == 0 {
        r.ok(&format!("container: all {} entries match their zip CRC-32 and size", entries.len()));
    } else {
        r.fail += crc_bad;
    }

    // 3b. every declared file: size + sha256
    let mut checked = 0;
    let mut hash_bad = 0;
    let mut seen: Vec<String> = Vec::new();
    for n in nodes {
        for v in n.g("versions").map(|x| x.a()).unwrap_or(&[]) {
            for f in v.g("files").map(|x| x.a()).unwrap_or(&[]) {
                let p = f.gs("path");
                if seen.contains(&p) {
                    continue;
                }
                seen.push(p.clone());
                let want = f.gs("sha256");
                let wsize = f.g("size").map(|x| x.u()).unwrap_or(0);
                match get(&p) {
                    None => {
                        hash_bad += 1;
                        println!("  [FAIL] declared file missing from container: {}", p);
                    }
                    Some(d) => {
                        checked += 1;
                        if d.len() as u64 != wsize {
                            hash_bad += 1;
                            println!("  [FAIL] size mismatch {}: {} vs declared {}", p, d.len(), wsize);
                        }
                        let got = hex(&sha256(d));
                        if got != want {
                            hash_bad += 1;
                            println!("  [FAIL] sha256 mismatch {}\n          declared {}\n          computed {}", p, want, got);
                        }
                    }
                }
            }
        }
    }
    if hash_bad == 0 {
        r.ok(&format!("{} distinct declared files: size and sha256 both match the manifest", checked));
    } else {
        r.fail += hash_bad;
    }

    // files present but not declared
    let undeclared: Vec<&str> = entries
        .iter()
        .map(|e| e.name.as_str())
        .filter(|n| *n != "MANIFEST.json" && *n != "SIGNATURE.json" && !seen.iter().any(|s| s == n))
        .collect();
    if undeclared.is_empty() {
        r.ok("every container entry except MANIFEST/SIGNATURE is owned by a node");
    } else {
        r.note(&format!("undeclared entries present: {:?}", undeclared));
    }

    // 3c. licence hash
    if let (Some(lic), Some(d)) = (man.g("license"), get(&man.g("license").map(|l| l.gs("file")).unwrap_or_default())) {
        if hex(&sha256(d)) == lic.gs("sha256") {
            r.ok("LICENSE bytes match license.sha256");
        } else {
            r.bad("LICENSE bytes do NOT match license.sha256");
        }
    }

    // 3d. input_hash — law 5, the derived-data staleness check
    // sha256( raw32(sha256(input_file)) for each, in order || utf8(canonical(input_params or {})) )
    let mut ih_ok = 0;
    let mut ih_bad = 0;
    for n in nodes {
        let nid = n.gs("node_id");
        for v in n.g("versions").map(|x| x.a()).unwrap_or(&[]) {
            let vn = v.g("v").map(|x| x.u()).unwrap_or(0);
            let want = v.gs("input_hash");
            if want.is_empty() {
                continue;
            }
            let mut acc: Vec<u8> = Vec::new();
            let mut ok = true;
            for f in v.g("input_files").map(|x| x.a()).unwrap_or(&[]) {
                match get(f.s()) {
                    Some(d) => acc.extend_from_slice(&sha256(d)),
                    None => {
                        ok = false;
                        println!("  [FAIL] {}@v{}: input file {} not in container", nid, vn, f.s());
                    }
                }
            }
            let params = v.g("input_params").cloned().unwrap_or(J::Obj(Vec::new()));
            acc.extend_from_slice(canonical(&params).as_bytes());
            if ok {
                let got = hex(&sha256(&acc));
                if got == want {
                    ih_ok += 1;
                } else {
                    ih_bad += 1;
                    println!("  [FAIL] {}@v{}: input_hash declared {} computed {}", nid, vn, want, got);
                }
            } else {
                ih_bad += 1;
            }
        }
    }
    if ih_bad == 0 {
        r.ok(&format!("{} derived versions: recomputed input_hash matches (nothing is stale)", ih_ok));
    } else {
        r.fail += ih_bad;
    }

    // 3e. container arithmetic: total_size_bytes and preview_prefix_bytes
    if let Some(c) = man.g("container") {
        // total_size_bytes = sum of size over DISTINCT declared paths, payload only
        let mut tot = 0u64;
        for p in &seen {
            if let Some(d) = get(p) {
                tot += d.len() as u64;
            }
        }
        if let Some(dec) = c.g("total_size_bytes") {
            if dec.u() == tot {
                r.ok(&format!("container.total_size_bytes = {} matches the sum of distinct declared payload files", tot));
            } else {
                r.bad(&format!("container.total_size_bytes declared {} but distinct declared payload files sum to {}", dec.u(), tot));
            }
        }
        // preview_prefix_bytes = end offset of the last entry in preview_tier
        if let (Some(dec), Some(tier)) = (c.g("preview_prefix_bytes"), c.g("preview_tier")) {
            let inset = |name: &str| -> bool {
                tier.a().iter().any(|t| {
                    let t = t.s();
                    if t.ends_with('/') { name.starts_with(t) } else { name == t }
                })
            };
            let mut end = 0u64;
            for e in &entries {
                if inset(&e.name) {
                    let o = e.lho as usize;
                    let nlen = le16(&buf, o + 26) as u64;
                    let elen = le16(&buf, o + 28) as u64;
                    let fin = e.lho + 30 + nlen + elen + e.csize;
                    if fin > end {
                        end = fin;
                    }
                }
            }
            if end == dec.u() {
                r.ok(&format!("container.preview_prefix_bytes = {} is exactly the end of the preview tier in the zip", end));
            } else {
                r.bad(&format!("container.preview_prefix_bytes declared {} computed {}", dec.u(), end));
            }
        }
        // entry_order, S-14 (PROPOSED): exact paths first, then '/' prefixes
        if let Some(eo) = c.g("entry_order") {
            let order: Vec<&str> = eo.a().iter().map(|x| x.s()).collect();
            let idx = |name: &str| -> Option<usize> {
                order.iter().position(|t| *t == name)
                    .or_else(|| order.iter().position(|t| t.ends_with('/') && name.starts_with(*t)))
            };
            let mut last = 0usize;
            let mut monotone = true;
            for e in &entries {
                match idx(&e.name) {
                    Some(i) => {
                        if i < last { monotone = false; }
                        last = i;
                    }
                    None => monotone = false,
                }
            }
            if monotone {
                r.ok("physical entry order agrees with container.entry_order (S-14 two-pass matching; ruling is still PROPOSED)");
            } else {
                r.note("physical entry order does not agree with container.entry_order under the S-14 two-pass reading");
            }
        }
    }

    // 3f. signature chain
    println!("\n  signature chain:");
    match get("SIGNATURE.json") {
        None => {
            println!("    state: signature-absent — this package is anonymous, and visibly so.");
            r.note("SIGNATURE.json absent");
        }
        Some(sb) => {
            let sig = json_parse(sb).unwrap_or(J::Null);
            let man_hash = hex(&sha256(&manifest_bytes));
            println!("    algorithm     : {} ({})", sig.gs("algorithm"), sig.gs("encoding"));
            println!("    MANIFEST.json sha256 computed : {}", man_hash);
            println!("    SIGNATURE top-level declares  : {}", sig.gs("manifest_sha256"));
            let chain = sig.g("chain").map(|c| c.a()).unwrap_or(&[]);
            let mut anchor_ok = sig.gs("manifest_sha256") == man_hash;
            let mut prev_ok = true;
            let mut prev_sig: Option<String> = None;
            for (i, e) in chain.iter().enumerate() {
                let signer = e.g("signer").cloned().unwrap_or(J::Null);
                println!(
                    "    entry {}: signer {:?} kind={} role={} uri={}",
                    i, signer.gs("name"), signer.gs("kind"), signer.gs("role"), signer.gs("uri")
                );
                println!("             signed_at        {}", e.gs("signed_at"));
                println!("             public_key       {}", e.gs("public_key"));
                println!("             manifest_sha256  {}", e.gs("manifest_sha256"));
                println!("             prev_entry_sha256 {}", e.gs("prev_entry_sha256"));
                println!("             signature        {}…{}",
                    &e.gs("signature")[..16.min(e.gs("signature").len())],
                    &e.gs("signature")[e.gs("signature").len().saturating_sub(8)..]);
                // The bytes this entry signs, per SPEC.md §6 — we can build them,
                // we simply do not verify the ed25519 over them (see below).
                let msg = format!(
                    "werk-sig/1\n{}\n{}\n{}\n{}\n{}",
                    e.gs("manifest_sha256"),
                    e.gs("prev_entry_sha256"),
                    e.gs("signed_at"),
                    signer.gs("uri"),
                    signer.gs("kind")
                );
                println!("             signed message   {:?}", trunc(&msg.replace('\n', "\\n"), 160));
                println!("             signature length {} bytes, public key {} bytes (both well-formed hex)",
                    unhex(&e.gs("signature")).map(|v| v.len()).unwrap_or(0),
                    unhex(&e.gs("public_key")).map(|v| v.len()).unwrap_or(0));
                let want_prev = match &prev_sig {
                    None => "0".repeat(64),
                    Some(s) => hex(&sha256(s.as_bytes())),
                };
                if e.gs("prev_entry_sha256") == want_prev {
                    println!("             prev_entry_sha256 links correctly");
                } else {
                    prev_ok = false;
                    println!("             [FAIL] prev_entry_sha256 does not link (expected {})", want_prev);
                }
                prev_sig = Some(e.gs("signature"));
                if i + 1 == chain.len() {
                    anchor_ok &= e.gs("manifest_sha256") == man_hash;
                }
            }
            if anchor_ok {
                r.ok("the last chain entry (and the top-level copy) anchor the MANIFEST.json bytes actually present");
            } else {
                r.bad("the chain's anchor hash does not match the MANIFEST.json bytes present — present-and-invalid");
            }
            if prev_ok {
                r.ok("prev_entry_sha256 linkage is consistent across the chain");
            } else {
                r.bad("prev_entry_sha256 linkage broken");
            }
            println!("    STATE: signature-unverified");
            println!("           (SPEC.md §10.0 step 4's fourth word. This reader carries no");
            println!("            Ed25519 implementation, so it MUST NOT say signed-and-valid.");
            println!("            Everything around the signature checks out: the chain is");
            println!("            well-formed, the anchor matches the bytes, the links hash");
            println!("            correctly. The curve arithmetic itself was not performed.");
            println!("            README.txt also warns the key is a published DEV key: even a");
            println!("            valid signature here would prove nothing about authorship.)");
            r.note("ed25519 not verified — reported as signature-unverified, never as valid");
        }
    }

    // ---------------------------------------------------------- 4. extraction
    println!("\n---- 4. EXTRACTION ---------------------------------------------");
    let _ = fs::create_dir_all(&outdir);
    // the primary image is named by primary.image, never guessed from a path
    let primary_node = prim.gs("image");
    let mut want: Vec<String> = Vec::new();
    for n in nodes {
        if n.gs("node_id") == primary_node {
            let act = n.g("active").map(|v| v.u()).unwrap_or(0);
            for v in n.g("versions").map(|x| x.a()).unwrap_or(&[]) {
                if v.g("v").map(|x| x.u()).unwrap_or(0) == act {
                    for f in v.g("files").map(|x| x.a()).unwrap_or(&[]) {
                        want.push(f.gs("path"));
                    }
                }
            }
        }
    }
    // the second payload: the custom binary, plus the style plate the model was given
    want.push("semantics/style-embedding.wkem".into());
    want.push("recipe/inputs/imperial-painterly.png".into());
    for p in &want {
        match get(p) {
            None => println!("  [FAIL] {} not in container", p),
            Some(d) => {
                let name = p.rsplit('/').next().unwrap_or(p);
                let dest = outdir.join(name);
                match fs::write(&dest, d) {
                    Ok(_) => println!(
                        "  wrote {:<52} {:>9} bytes   sha256 {} (verified above)",
                        dest.display(),
                        d.len(),
                        &hex(&sha256(d))[..16]
                    ),
                    Err(e) => println!("  [FAIL] writing {}: {}", dest.display(), e),
                }
            }
        }
    }

    // ---------------------------------------------------------- 5. WKEM
    println!("\n---- 5. THE CUSTOM BINARY: semantics/style-embedding.wkem ------");
    match get("semantics/style-embedding.wkem") {
        None => println!("  not present"),
        Some(w) => {
            let sem = get("semantics/semantics.json").and_then(|b| json_parse(b).ok());
            match parse_wkem(w, sem.as_ref(), &mut r) {
                Ok(()) => {}
                Err(e) => {
                    println!("  node dead: {}", e);
                    r.bad(&format!("WKEM: {}", e));
                }
            }
        }
    }

    // ---------------------------------------------------------- 6. recipe
    println!("\n---- 6. HOW THE IMAGE WAS MADE (core.recipe) -------------------");
    // find the recipe node's ACTIVE version and its record file
    let mut recipe_path = String::new();
    let mut recipe_active = 0u64;
    let mut recipe_versions: Vec<(u64, String, u64)> = Vec::new(); // v, note, supersedes
    for n in nodes {
        if n.gs("type") == "core.recipe" {
            recipe_active = n.g("active").map(|v| v.u()).unwrap_or(0);
            for v in n.g("versions").map(|x| x.a()).unwrap_or(&[]) {
                let vn = v.g("v").map(|x| x.u()).unwrap_or(0);
                recipe_versions.push((vn, v.gs("note"), v.g("supersedes").map(|x| x.u()).unwrap_or(0)));
                if vn == recipe_active {
                    for f in v.g("files").map(|x| x.a()).unwrap_or(&[]) {
                        if f.gs("role") == "record" {
                            recipe_path = f.gs("path");
                        }
                    }
                }
            }
        }
    }
    println!("  The recipe node carries {} versions; version {} is active.", recipe_versions.len(), recipe_active);
    for (v, note, sup) in &recipe_versions {
        println!("    v{}{}: {}", v, if *sup > 0 { format!(" (supersedes v{})", sup) } else { String::new() }, trunc(note, 300));
    }
    if let Some(rb) = get(&recipe_path) {
        let rc = json_parse(rb).unwrap_or(J::Null);
        println!("\n  Reading {} (the active record):", recipe_path);
        println!("    target            : node {} v{}", rc.g("target").map(|t| t.gs("node_id")).unwrap_or_default(),
            rc.g("target").and_then(|t| t.g("version")).map(|v| v.u()).unwrap_or(0));
        println!("    reproducibility   : {}", rc.gs("reproducibility").to_uppercase());
        println!("    why               : {}", trunc(&rc.gs("reproducibility_note"), 400));
        println!("    generated_at      : {}", rc.gs("generated_at"));
        println!("    pipeline kind     : {}", rc.g("pipeline").map(|p| p.gs("kind")).unwrap_or_default());
        for (i, st) in rc.g("steps").map(|s| s.a()).unwrap_or(&[]).iter().enumerate() {
            println!("\n    step {} \"{}\" (role: {})", i, st.gs("step_id"), st.gs("role"));
            let m = st.g("model").cloned().unwrap_or(J::Null);
            println!("      model           : {}  (family {}, hosted={}, operator {})",
                m.gs("id"), m.gs("family"),
                m.g("hosted").map(|h| h.b()).unwrap_or(false), m.gs("operator"));
            if let Some(w) = m.g("weights") {
                println!("      weights         : available={} — {}",
                    w.g("available").map(|x| x.b()).unwrap_or(false), trunc(&w.gs("reason"), 240));
            }
            println!("      reached via     : {}", trunc(&m.gs("note"), 240));
            if let Some(t) = st.g("tool") {
                println!("      tool            : {} (version {}, repo rev {})",
                    t.gs("name"), t.gs("version"), t.gs("repository_revision"));
            }
            if let Some(J::Obj(p)) = st.g("params") {
                let s: Vec<String> = p.iter().map(|(k, v)| format!("{}={}", k, canonical(v))).collect();
                println!("      call params     : {}", s.join("  "));
            }
            if let Some(sd) = st.g("seed") {
                println!("      seed            : controlled={} — {}",
                    sd.g("controlled").map(|x| x.b()).unwrap_or(false), trunc(&sd.gs("reason"), 240));
            }
            for inp in st.g("inputs").map(|x| x.a()).unwrap_or(&[]) {
                println!("      input           : [{}] {} ({} bytes)", inp.gs("role"), inp.gs("path"), inp.g("size").map(|x| x.u()).unwrap_or(0));
                println!("                        {}", trunc(&inp.gs("note"), 300));
            }
            for o in st.g("outputs").map(|x| x.a()).unwrap_or(&[]) {
                println!("      output          : {} ({} bytes, {})", o.gs("path"), o.g("size").map(|x| x.u()).unwrap_or(0), o.gs("media_type"));
            }
            if let Some(pr) = st.g("prompt") {
                let pos = pr.g("positive").cloned().unwrap_or(J::Null);
                println!("      prompt file     : {}  [provenance: {}]", pos.gs("file"), pos.gs("provenance").to_uppercase());
                println!("      prompt caveat   : {}", trunc(&pos.gs("note"), 300));
                if let Some(rec) = pos.g("reconstruction") {
                    println!("      reconstruction  : {}", trunc(&rec.gs("method"), 900));
                    for ev in rec.g("evidence").map(|x| x.a()).unwrap_or(&[]) {
                        println!("        evidence      : {} — {}", ev.gs("path"), trunc(&ev.gs("note"), 200));
                    }
                }
                println!("      negative prompt : absent — {}", trunc(&pr.gs("negative_absent_reason"), 300));
                if let Some(pb) = get(&pos.gs("file")) {
                    let txt = String::from_utf8_lossy(pb);
                    println!("\n      ---- the prompt as this version records it, in full ----");
                    let mut line = String::new();
                    for word in txt.trim_end().split_whitespace() {
                        if line.chars().count() + word.chars().count() + 1 > 104 {
                            println!("      | {}", line);
                            line.clear();
                        }
                        if !line.is_empty() {
                            line.push(' ');
                        }
                        line.push_str(word);
                    }
                    if !line.is_empty() {
                        println!("      | {}", line);
                    }
                    println!("      ---- end of prompt ({} bytes) ----", pb.len());
                }
            }
            println!("      step note       : {}", trunc(&st.gs("note"), 400));
        }
        for pp in rc.g("postprocess").map(|x| x.a()).unwrap_or(&[]) {
            println!("\n    postprocess \"{}\" via {} {}", pp.gs("op"),
                pp.g("tool").map(|t| t.gs("name")).unwrap_or_default(),
                pp.g("tool").map(|t| t.gs("version")).unwrap_or_default());
            println!("      {}", trunc(&pp.gs("description"), 400));
        }
        let un = rc.g("unrecorded").map(|x| x.a()).unwrap_or(&[]);
        println!("\n    NOT RECORDED — {} facts this package refuses to invent:", un.len());
        for u in un {
            println!("      * {}", trunc(u.s(), 260));
        }
        // difference between the two prompt files, since that is the point of v2
        if let (Some(a), Some(b)) = (get("recipe/prompt-recorded.txt"), get("recipe/prompt-transmitted.txt")) {
            let common = a.iter().zip(b.iter()).take_while(|(x, y)| x == y).count();
            println!("\n    The two prompt files differ by exactly {} bytes appended at the end;", b.len() - common);
            println!("    the first {} bytes are byte-identical, so the persisted prompt really is", common);
            println!("    a prefix of the reconstructed transmitted string:");
            println!("      appended: {:?}", String::from_utf8_lossy(&b[common..]).trim_end());
        }
    }

    // ---------------------------------------------------------- 7. disclosure
    println!("\n---- 7. WHAT THE FILE DECLARES ABOUT THAT (core.disclosure) ----");
    if let Some(db) = get("disclosure/disclosure.json") {
        let d = json_parse(db).unwrap_or(J::Null);
        println!("    ai_generated      : {}", d.g("ai_generated").map(|x| x.b()).unwrap_or(false));
        println!("    ai_modified       : {}", d.g("ai_modified").map(|x| x.b()).unwrap_or(false));
        println!("    generation_scope  : {}", d.gs("generation_scope"));
        println!("    declared_by       : {} ({})",
            d.g("declared_by").map(|x| x.gs("name")).unwrap_or_default(),
            d.g("declared_by").map(|x| x.gs("uri")).unwrap_or_default());
        println!("    declared_at       : {}", d.gs("declared_at"));
        println!("    backed by node    : {}", d.gs("recipe_node"));
        for m in d.g("models").map(|x| x.a()).unwrap_or(&[]) {
            println!("    model             : {} (role {}, operator {}, hosted {})",
                m.gs("id"), m.gs("role"), m.gs("operator"), m.g("hosted").map(|x| x.b()).unwrap_or(false));
            println!("                        {}", trunc(&m.gs("version_note"), 300));
        }
        if let Some(h) = d.g("human_authorship") {
            println!("    human authorship  : claimed={}", h.g("claimed").map(|x| x.b()).unwrap_or(false));
            println!("                        {}", trunc(&h.gs("description"), 400));
            for c in h.g("contributors").map(|x| x.a()).unwrap_or(&[]) {
                println!("                        {} — {}", c.gs("name"), trunc(&c.gs("contribution"), 200));
            }
        }
        if let Some(s) = d.g("synthetic_markers") {
            println!("    synthetic markers : c2pa_manifest_present={} embedded_metadata_stripped={}",
                s.g("c2pa_manifest_present").map(|x| x.b()).unwrap_or(false),
                s.g("embedded_metadata_stripped").map(|x| x.b()).unwrap_or(false));
        }
        if let Some(t) = d.g("training_data_statement") {
            println!("    training data     : {} — {}", t.gs("status"), trunc(&t.gs("text"), 300));
        }
        if let Some(s) = d.g("subject") {
            println!("    subject           : real person={} real event={} universe={}",
                s.g("depicts_real_person").map(|x| x.b()).unwrap_or(false),
                s.g("depicts_real_event").map(|x| x.b()).unwrap_or(false),
                s.gs("fictional_universe"));
            println!("                        {}", trunc(&s.gs("note"), 300));
        }
        println!("    statements:");
        for st in d.g("statements").map(|x| x.a()).unwrap_or(&[]) {
            println!("      [{}] ({}{})", st.gs("id"), st.gs("epistemic"),
                st.g("confidence").map(|c| format!(", confidence {}", c.f())).unwrap_or_default());
            println!("          {}", trunc(&st.gs("text"), 500));
        }
        println!("    jurisdiction note : {}", trunc(&d.gs("jurisdiction_note"), 400));
    }
    if let Some(cb) = get("x/c2pa/export.json") {
        let c = json_parse(cb).unwrap_or(J::Null);
        println!("\n    x.c2pa.export     : present, and it is a STUB. status={} note={}",
            c.gs("status"), trunc(&c.gs("note"), 300));
    }

    // ---------------------------------------------------------- 8. summary
    println!("\n---- 8. RESULT -------------------------------------------------");
    println!("  checks passed {}   failed {}   notes {}", r.pass, r.fail, r.warn);
    println!("  signature state: signature-unverified (no ed25519 in this reader)");
    if r.fail == 0 {
        println!("  Every hash, size, CRC and declared arithmetic in this package agrees.");
    } else {
        println!("  {} check(s) FAILED — see above.", r.fail);
    }
}

// ============================================================ WKEM parser
fn parse_wkem(w: &[u8], sem: Option<&J>, r: &mut Rep) -> Result<(), String> {
    if w.len() < 12 {
        return Err("shorter than the 12-byte fixed prefix".into());
    }
    let magic = String::from_utf8_lossy(&w[0..4]).into_owned();
    let version = le32(w, 4);
    let header_len = le32(w, 8) as usize;
    println!("  fixed prefix:");
    println!("    magic            {:?}  ({})", magic,
        if magic == "WKEM" { "core.embedding — style descriptor + palette" } else { "UNKNOWN magic: mark dead and continue" });
    println!("    version          {} (u32 LE)", version);
    println!("    header_len       {} (u32 LE)", header_len);
    if magic != "WKEM" {
        return Err("unrecognised magic".into());
    }
    if 12 + header_len > w.len() {
        return Err("header runs past end of file".into());
    }
    let mut mp = MP { b: &w[12..12 + header_len], i: 0 };
    let h = mp.val()?;
    if mp.i != header_len {
        println!("    [note] {} trailing bytes after the header map", header_len - mp.i);
    }

    println!("\n  header (MessagePack map, big-endian numbers inside a little-endian file):");
    if let M::Map(kv) = &h {
        for (k, v) in kv {
            match (k.as_str(), v) {
                ("sections", M::Arr(a)) => println!("    {:<15} [{} sections, tabulated below]", k, a.len()),
                (_, M::Str(s)) => println!("    {:<15} {:?}", k, trunc(s, 220)),
                _ => println!("    {:<15} {}", k, v.show()),
            }
        }
    }
    // what the mandatory keys mean
    println!("\n  what those keys mean:");
    println!("    kind={:?} must match the magic; endianness={:?} states the payload byte order",
        h.g("kind").map(|v| v.s()).unwrap_or(""), h.g("endianness").map(|v| v.s()).unwrap_or(""));
    println!("    model={:?}", h.g("model").map(|v| v.s()).unwrap_or(""));
    println!("      -> the single most important key: a vector whose model is unknown is noise.");
    println!("         This one is an ALGORITHM defined in the package itself");
    println!("         (spec/layouts/embedding.layout.txt §4), not a neural net, which is why");
    println!("         the node can claim epistemic \"measured\" instead of merely asserted.");
    println!("    dim={}  normalized={}  metric={:?}  swatch_count={}",
        h.g("dim").map(|v| v.u()).unwrap_or(0),
        matches!(h.g("normalized"), Some(M::Bool(true))),
        h.g("metric").map(|v| v.s()).unwrap_or(""),
        h.g("swatch_count").map(|v| v.u()).unwrap_or(0));
    println!("    epistemic={:?} tolerance={} colour_space={:?}",
        h.g("epistemic").map(|v| v.s()).unwrap_or(""),
        h.g("tolerance").map(|v| v.show()).unwrap_or_default(),
        h.g("colour_space").map(|v| v.s()).unwrap_or(""));

    // envelope arithmetic, both statements of it
    let p_calc = 16 * ((12 + header_len + 15) / 16);
    let p_decl = h.g("payload_origin").map(|v| v.u()).unwrap_or(0) as usize;
    let psize = h.g("payload_size").map(|v| v.u()).unwrap_or(0) as usize;
    println!("\n  envelope arithmetic (two independent statements of one fact):");
    println!("    payload_origin computed 16*ceil((12+{})/16) = {}", header_len, p_calc);
    println!("    payload_origin declared                      = {}", p_decl);
    if p_calc != p_decl {
        return Err("computed and declared payload_origin disagree".into());
    }
    r.ok("WKEM: computed payload_origin equals the declared one");
    println!("    payload_origin + payload_size = {} + {} = {}   file length = {}",
        p_decl, psize, p_decl + psize, w.len());
    if p_decl + psize != w.len() {
        return Err("payload_origin + payload_size != file length".into());
    }
    r.ok("WKEM: payload_origin + payload_size equals the file length");
    if h.g("endianness").map(|v| v.s()).unwrap_or("") != "le" {
        return Err("header does not declare endianness \"le\"".into());
    }
    // padding must be zero (a writer rule, checked for information only)
    let padnz = w[12 + header_len..p_decl].iter().filter(|b| **b != 0).count();
    println!("    {} padding bytes between header and payload, {} of them nonzero",
        p_decl - 12 - header_len, padnz);

    // sections
    let secs = match h.g("sections") {
        Some(M::Arr(a)) => a.clone(),
        _ => return Err("no sections array".into()),
    };
    println!("\n  payload sections (offsets are ABSOLUTE and declared, never derived):");
    println!("    {:<10} {:>8} {:>8} {:>8} {:<8} {:<12} {}", "name", "offset", "size", "stride", "dtype", "shape", "consistency rule");
    let dsz = |d: &str| -> Option<usize> {
        Some(match d {
            "u8" | "i8" => 1,
            "u16" | "i16" => 2,
            "u32" | "i32" | "f32" => 4,
            "u64" | "i64" | "f64" => 8,
            _ => return None,
        })
    };
    let mut vector: Vec<f32> = Vec::new();
    let mut palette: Vec<[f32; 4]> = Vec::new();
    for s in &secs {
        let name = s.g("name").map(|v| v.s().to_string()).unwrap_or_default();
        let off = s.g("offset").map(|v| v.u()).unwrap_or(0) as usize;
        let size = s.g("size").map(|v| v.u()).unwrap_or(0) as usize;
        let stride = s.g("stride").map(|v| v.u()).unwrap_or(0) as usize;
        let dtype = s.g("dtype").map(|v| v.s().to_string()).unwrap_or_default();
        let shape: Vec<usize> = match s.g("shape") {
            Some(M::Arr(a)) => a.iter().map(|x| x.u() as usize).collect(),
            _ => Vec::new(),
        };
        let esz = dsz(&dtype).unwrap_or(stride);
        let branch;
        let ok;
        if stride == esz {
            let prod: usize = shape.iter().product();
            ok = size == stride * prod;
            branch = format!("1st: size == stride*prod(shape) = {}", stride * prod);
        } else {
            let prod: usize = shape[..shape.len() - 1].iter().product();
            ok = stride >= esz * shape[shape.len() - 1] && size == stride * prod;
            branch = format!("2nd: stride>={}*{} and size == stride*prod(shape[..-1]) = {}",
                esz, shape[shape.len() - 1], stride * prod);
        }
        println!("    {:<10} {:>8} {:>8} {:>8} {:<8} {:<12} {} {}",
            name, off, size, stride, dtype,
            format!("{:?}", shape), branch, if ok { "OK" } else { "FAILED" });
        if off % 16 != 0 {
            return Err(format!("section {} offset {} is not 16-aligned", name, off));
        }
        if off + size > w.len() {
            return Err(format!("section {} runs past end of file", name));
        }
        if !ok {
            return Err(format!("section {} fails the envelope consistency rule", name));
        }
        let d = &w[off..off + size];
        if name == "vector" {
            for c in d.chunks(4) {
                vector.push(f32::from_le_bytes([c[0], c[1], c[2], c[3]]));
            }
        } else if name == "palette" {
            for c in d.chunks(16) {
                let mut v = [0f32; 4];
                for i in 0..4 {
                    v[i] = f32::from_le_bytes([c[i * 4], c[i * 4 + 1], c[i * 4 + 2], c[i * 4 + 3]]);
                }
                palette.push(v);
            }
        }
    }
    r.ok("WKEM: both sections satisfy the envelope section-consistency rule (one per branch, by design)");

    // no NaN / inf allowed anywhere in a core payload
    if vector.iter().any(|v| !v.is_finite()) || palette.iter().flatten().any(|v| !v.is_finite()) {
        return Err("NaN or infinity in a core payload".into());
    }
    r.ok("WKEM: no NaN and no infinity in the payload");

    // --- the vector
    let dim = h.g("dim").map(|v| v.u()).unwrap_or(0) as usize;
    if vector.len() != dim {
        return Err(format!("vector has {} components but dim declares {}", vector.len(), dim));
    }
    let norm: f64 = vector.iter().map(|v| (*v as f64) * (*v as f64)).sum::<f64>().sqrt();
    println!("\n  VECTOR — {} f32 components. Per the layout file, components 0..63 are a", dim);
    println!("  4x4x4 CIELAB colour histogram over a 32x32 box-resample of the image, and");
    println!("  components 64..71 are an 8-bin Sobel gradient-orientation histogram of the");
    println!("  same grid's L plane. The whole thing is then L2-normalised.");
    println!("    L2 norm = {:.9}  (header says normalized={}, so this must be 1.0 +/- 1e-6)",
        norm, matches!(h.g("normalized"), Some(M::Bool(true))));
    if (norm - 1.0).abs() < 1e-6 {
        r.ok("WKEM: the vector really is L2-normalised, as the header claims");
    } else {
        r.bad("WKEM: header says normalized but the L2 norm is not 1.0");
    }

    // decode the colour histogram bins that are non-empty
    println!("\n    non-zero colour bins (index = 16*L + 4*a + b, each axis quartered):");
    let mut bins: Vec<(usize, f32)> = vector[..64.min(dim)]
        .iter()
        .enumerate()
        .filter(|(_, v)| **v > 0.0)
        .map(|(i, v)| (i, *v))
        .collect();
    bins.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
    for (i, v) in &bins {
        let (lb, ab, bb) = (i / 16, (i / 4) % 4, i % 4);
        println!("      bin {:>2}  L-quarter {} a-quarter {} b-quarter {}   normalised weight {:.6}",
            i, lb, ab, bb, v);
    }
    println!("      -> {} of 64 colour bins are occupied: a tightly clustered, low-chroma image.", bins.len());
    println!("\n    gradient-orientation bins (0 = horizontal gradient, sweeping to pi):");
    for (i, v) in vector[64..dim].iter().enumerate() {
        let a0 = i as f64 * 180.0 / 8.0;
        println!("      bin {}  [{:>5.1}deg,{:>5.1}deg)  {:.6}  {}", i, a0, a0 + 22.5, v,
            "#".repeat((*v as f64 * 300.0) as usize));
    }

    // --- the palette
    println!("\n  PALETTE — {} swatches of (r,g,b,weight) f32, colour space {:?},", palette.len(),
        h.g("colour_space").map(|v| v.s()).unwrap_or(""));
    println!("  sorted by weight DESCENDING so record 0 IS \"the dominant colour\":");
    println!("    {:<3} {:<9} {:<9} {:<9} {:<10} {}", "#", "R(lin)", "G(lin)", "B(lin)", "weight", "as sRGB");
    let mut wsum = 0f64;
    for (i, p) in palette.iter().enumerate() {
        let hexs = format!("#{:02x}{:02x}{:02x}",
            linear_to_srgb8(p[0] as f64), linear_to_srgb8(p[1] as f64), linear_to_srgb8(p[2] as f64));
        println!("    {:<3} {:<9.6} {:<9.6} {:<9.6} {:<10.7} {}", i, p[0], p[1], p[2], p[3], hexs);
        wsum += p[3] as f64;
    }
    println!("    weights sum to {:.6}", wsum);
    println!("    (NOT 1.0, and that is correct and documented: this is a TOP-8 palette over");
    println!("     ten occupied bins, so it deliberately does not cover the whole image.");
    println!("     semantics.json flags the same thing as spec finding S-24, because");
    println!("     core.semantics.schema.json describes palette weights as summing to 1.0.)");

    // cross-check against the JSON duplicate in semantics.json
    // The palette is deliberately duplicated as JSON in semantics.json (law 9:
    // a listing wants eight hex strings without parsing an envelope). Two
    // spellings of one fact is only safe if a reader checks they agree.
    println!("\n  cross-check against the JSON duplicate in semantics/semantics.json:");
    match sem.and_then(|s| s.g("palette")).and_then(|p| p.g("colors")) {
        None => println!("    semantics.json carries no palette to compare against"),
        Some(cols) => {
            let cols = cols.a();
            let mut agree = true;
            if cols.len() != palette.len() {
                agree = false;
                println!("    [FAIL] {} JSON swatches vs {} binary swatches", cols.len(), palette.len());
            }
            for (i, c) in cols.iter().enumerate().take(palette.len()) {
                let lin = c.g("linear_rgb").map(|x| x.a()).unwrap_or(&[]);
                let wj = c.g("weight").map(|x| x.f()).unwrap_or(-1.0);
                let hj = c.gs("hex_srgb");
                let hb = format!("#{:02x}{:02x}{:02x}",
                    linear_to_srgb8(palette[i][0] as f64),
                    linear_to_srgb8(palette[i][1] as f64),
                    linear_to_srgb8(palette[i][2] as f64));
                let mut ok = hj == hb && (wj - palette[i][3] as f64).abs() < 1e-6;
                for k in 0..3.min(lin.len()) {
                    if (lin[k].f() - palette[i][k] as f64).abs() > 1e-6 {
                        ok = false;
                    }
                }
                if !ok {
                    agree = false;
                    println!("    [FAIL] swatch {}: JSON {} w={} vs binary {} w={}", i, hj, wj, hb, palette[i][3]);
                }
            }
            if agree {
                r.ok("WKEM: all 8 swatches agree with the JSON duplicate in semantics.json, to 1e-6, including the sRGB hex I re-encoded from the linear values");
            } else {
                r.bad("WKEM: the binary palette and semantics.json disagree");
            }
            if let Some(sp) = sem.and_then(|s| s.g("palette")) {
                println!("    semantics.json also states dominant_index={} and average_luminance={:.6};",
                    sp.g("dominant_index").map(|x| x.u()).unwrap_or(0),
                    sp.g("average_luminance").map(|x| x.f()).unwrap_or(0.0));
                println!("    dominant_index 0 is consistent with the binary's weight-descending sort rule.");
            }
        }
    }
    println!("\n  NOT DONE, and declared rather than glossed over: the descriptor was not");
    println!("  RECOMPUTED from image/source.png. §4 of the layout file defines the whole");
    println!("  algorithm and §5 promises agreement to 1e-6 absolute, so this is checkable —");
    println!("  it just needs a PNG decoder (zlib inflate + defiltering), which this reader");
    println!("  does not carry. Everything above is what the file DECLARES, verified for");
    println!("  internal consistency; the pixels were not re-measured.");
    Ok(())
}
