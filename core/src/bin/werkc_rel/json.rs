//! Ordered JSON for the release writer: a strict parser that keeps key order
//! and whether a number was spelled as a float, and the one emitter every
//! libs/ writer shares (Python `json.dumps(v, indent=2, ensure_ascii=False)`
//! byte for byte, floats in Python `repr` spelling). `serde_json` without
//! `preserve_order` sorts keys and spells floats differently, so the writer
//! cannot use it and stay byte-identical with the Python and JavaScript ones.

#[derive(Debug, Clone, PartialEq)]
pub enum J {
    Null,
    Bool(bool),
    Int(i64),
    /// An integer outside i64, kept as its (normalised) lexeme.
    BigInt(String),
    Float(f64),
    Str(String),
    Arr(Vec<J>),
    Obj(Vec<(String, J)>),
}

impl J {
    pub fn obj() -> J {
        J::Obj(Vec::new())
    }
    pub fn s(v: &str) -> J {
        J::Str(v.to_string())
    }
    pub fn get(&self, k: &str) -> Option<&J> {
        match self {
            J::Obj(m) => m.iter().find(|(kk, _)| kk == k).map(|(_, v)| v),
            _ => None,
        }
    }
    pub fn get_mut(&mut self, k: &str) -> Option<&mut J> {
        match self {
            J::Obj(m) => m.iter_mut().find(|(kk, _)| kk == k).map(|(_, v)| v),
            _ => None,
        }
    }
    pub fn has(&self, k: &str) -> bool {
        self.get(k).is_some()
    }
    /// Insert or replace, keeping the position of an existing key.
    pub fn set(&mut self, k: &str, v: J) {
        if let J::Obj(m) = self {
            if let Some(slot) = m.iter_mut().find(|(kk, _)| kk == k) {
                slot.1 = v;
            } else {
                m.push((k.to_string(), v));
            }
        }
    }
    pub fn as_str(&self) -> Option<&str> {
        match self {
            J::Str(s) => Some(s),
            _ => None,
        }
    }
    pub fn as_i64(&self) -> Option<i64> {
        match self {
            J::Int(i) => Some(*i),
            _ => None,
        }
    }
    pub fn as_arr(&self) -> Option<&Vec<J>> {
        match self {
            J::Arr(a) => Some(a),
            _ => None,
        }
    }
    pub fn as_arr_mut(&mut self) -> Option<&mut Vec<J>> {
        match self {
            J::Arr(a) => Some(a),
            _ => None,
        }
    }
}

/// Builder: `obj(vec![("k", v), ...])`.
pub fn obj(pairs: Vec<(&str, J)>) -> J {
    J::Obj(pairs.into_iter().map(|(k, v)| (k.to_string(), v)).collect())
}

// ------------------------------------------------------------------ parse

pub fn parse_bytes(b: &[u8]) -> Result<J, String> {
    if b.starts_with(&[0xEF, 0xBB, 0xBF]) {
        return Err("JSON starts with a byte-order mark".into());
    }
    let s = std::str::from_utf8(b).map_err(|e| format!("JSON is not UTF-8: {e}"))?;
    parse(s)
}

pub fn parse(s: &str) -> Result<J, String> {
    let mut p = P { b: s.as_bytes(), s, i: 0 };
    let v = p.val(0)?;
    p.ws();
    if p.i != p.b.len() {
        return Err(format!("JSON: trailing content at offset {}", p.i));
    }
    Ok(v)
}

struct P<'a> {
    b: &'a [u8],
    s: &'a str,
    i: usize,
}

impl<'a> P<'a> {
    fn err<T>(&self, m: &str) -> Result<T, String> {
        Err(format!("JSON: {m} at offset {}", self.i))
    }
    fn ws(&mut self) {
        while self.i < self.b.len() && matches!(self.b[self.i], b' ' | b'\t' | b'\n' | b'\r') {
            self.i += 1;
        }
    }
    fn val(&mut self, depth: usize) -> Result<J, String> {
        if depth > 512 {
            return self.err("nesting deeper than 512");
        }
        self.ws();
        match self.b.get(self.i) {
            Some(b'{') => {
                self.i += 1;
                let mut m: Vec<(String, J)> = Vec::new();
                self.ws();
                if self.b.get(self.i) == Some(&b'}') {
                    self.i += 1;
                    return Ok(J::Obj(m));
                }
                loop {
                    self.ws();
                    if self.b.get(self.i) != Some(&b'"') {
                        return self.err("expected a string key");
                    }
                    let k = self.string()?;
                    if m.iter().any(|(kk, _)| *kk == k) {
                        return self.err(&format!("duplicate object key {k:?}"));
                    }
                    self.ws();
                    if self.b.get(self.i) != Some(&b':') {
                        return self.err("expected ':'");
                    }
                    self.i += 1;
                    let v = self.val(depth + 1)?;
                    m.push((k, v));
                    self.ws();
                    match self.b.get(self.i) {
                        Some(b',') => self.i += 1,
                        Some(b'}') => {
                            self.i += 1;
                            return Ok(J::Obj(m));
                        }
                        _ => return self.err("expected ',' or '}'"),
                    }
                }
            }
            Some(b'[') => {
                self.i += 1;
                let mut a = Vec::new();
                self.ws();
                if self.b.get(self.i) == Some(&b']') {
                    self.i += 1;
                    return Ok(J::Arr(a));
                }
                loop {
                    a.push(self.val(depth + 1)?);
                    self.ws();
                    match self.b.get(self.i) {
                        Some(b',') => self.i += 1,
                        Some(b']') => {
                            self.i += 1;
                            return Ok(J::Arr(a));
                        }
                        _ => return self.err("expected ',' or ']'"),
                    }
                }
            }
            Some(b'"') => Ok(J::Str(self.string()?)),
            Some(b't') if self.s[self.i..].starts_with("true") => {
                self.i += 4;
                Ok(J::Bool(true))
            }
            Some(b'f') if self.s[self.i..].starts_with("false") => {
                self.i += 5;
                Ok(J::Bool(false))
            }
            Some(b'n') if self.s[self.i..].starts_with("null") => {
                self.i += 4;
                Ok(J::Null)
            }
            Some(c) if *c == b'-' || c.is_ascii_digit() => self.number(),
            _ => self.err("unexpected character"),
        }
    }
    fn string(&mut self) -> Result<String, String> {
        self.i += 1;
        let mut out: Vec<u16> = Vec::new();
        let mut s = String::new();
        loop {
            let c = match self.b.get(self.i) {
                Some(c) => *c,
                None => return self.err("unterminated string"),
            };
            if c == b'"' {
                self.i += 1;
                break;
            }
            if c == b'\\' {
                let e = *self.b.get(self.i + 1).unwrap_or(&0);
                if e == b'u' {
                    let h = self.s.get(self.i + 2..self.i + 6).unwrap_or("");
                    let v = u16::from_str_radix(h, 16).map_err(|_| "JSON: bad \\u escape".to_string())?;
                    out.push(v);
                    self.i += 6;
                    continue;
                }
                flush(&mut out, &mut s)?;
                s.push(match e {
                    b'"' => '"',
                    b'\\' => '\\',
                    b'/' => '/',
                    b'b' => '\u{8}',
                    b'f' => '\u{c}',
                    b'n' => '\n',
                    b'r' => '\r',
                    b't' => '\t',
                    _ => return self.err("bad escape"),
                });
                self.i += 2;
                continue;
            }
            if c < 0x20 {
                return self.err("control character in string");
            }
            flush(&mut out, &mut s)?;
            let ch = self.s[self.i..].chars().next().unwrap();
            s.push(ch);
            self.i += ch.len_utf8();
        }
        flush(&mut out, &mut s)?;
        Ok(s)
    }
    fn number(&mut self) -> Result<J, String> {
        let start = self.i;
        let b = self.b;
        if b.get(self.i) == Some(&b'-') {
            self.i += 1;
        }
        match b.get(self.i) {
            Some(b'0') => self.i += 1,
            Some(c) if (b'1'..=b'9').contains(c) => {
                while b.get(self.i).map_or(false, |c| c.is_ascii_digit()) {
                    self.i += 1;
                }
            }
            _ => return self.err("bad number"),
        }
        let mut is_f = false;
        if b.get(self.i) == Some(&b'.') {
            is_f = true;
            self.i += 1;
            if !b.get(self.i).map_or(false, |c| c.is_ascii_digit()) {
                return self.err("bad fraction");
            }
            while b.get(self.i).map_or(false, |c| c.is_ascii_digit()) {
                self.i += 1;
            }
        }
        if matches!(b.get(self.i), Some(b'e') | Some(b'E')) {
            is_f = true;
            self.i += 1;
            if matches!(b.get(self.i), Some(b'+') | Some(b'-')) {
                self.i += 1;
            }
            if !b.get(self.i).map_or(false, |c| c.is_ascii_digit()) {
                return self.err("bad exponent");
            }
            while b.get(self.i).map_or(false, |c| c.is_ascii_digit()) {
                self.i += 1;
            }
        }
        let lex = &self.s[start..self.i];
        if is_f {
            let v: f64 = lex.parse().map_err(|_| "JSON: bad number".to_string())?;
            if !v.is_finite() {
                return self.err("number does not fit binary64");
            }
            return Ok(J::Float(v));
        }
        match lex.parse::<i64>() {
            Ok(v) => Ok(J::Int(v)),
            Err(_) => {
                let t = lex.trim_start_matches('-');
                Ok(J::BigInt(if lex.starts_with('-') { format!("-{t}") } else { t.to_string() }))
            }
        }
    }
}

fn flush(units: &mut Vec<u16>, s: &mut String) -> Result<(), String> {
    if units.is_empty() {
        return Ok(());
    }
    let t = String::from_utf16(units).map_err(|_| "JSON: lone surrogate escape".to_string())?;
    s.push_str(&t);
    units.clear();
    Ok(())
}

// ------------------------------------------------------------------ emit

/// Python's `repr()` of a float (shortest round-trip digits; fixed notation
/// for decimal exponents -4..=15, else `d.ddde+XX`).
pub fn py_float(x: f64) -> String {
    if x == 0.0 {
        return if x.is_sign_negative() { "-0.0".into() } else { "0.0".into() };
    }
    let neg = x < 0.0;
    let ax = x.abs();
    let mut e = format!("{:e}", ax); // shortest digits, e.g. "1.5e16", "1e-5"
    // Rust's shortest search breaks an exact tie between two shortest
    // candidates away from zero; Python (and ECMAScript) take the even one.
    // The correctly rounded k-digit value (exact mode, ties to even) is that
    // one whenever it round-trips.
    let k = e.split_once('e').unwrap().0.chars().filter(|c| c.is_ascii_digit()).count();
    let exact = format!("{:.*e}", k - 1, ax);
    if exact.parse::<f64>() == Ok(ax) {
        e = exact;
    }
    let (mant, exp) = e.split_once('e').unwrap();
    let exp: i32 = exp.parse().unwrap();
    let mut digits: String = mant.chars().filter(|c| *c != '.').collect();
    while digits.len() > 1 && digits.ends_with('0') {
        digits.pop();
    }
    let out = if (-4..=15).contains(&exp) {
        if exp >= 0 {
            let k = exp as usize + 1;
            let mut int_d: String = digits.chars().take(k).collect();
            while int_d.len() < k {
                int_d.push('0');
            }
            let frac: String = digits.chars().skip(k).collect();
            format!("{int_d}.{}", if frac.is_empty() { "0".to_string() } else { frac })
        } else {
            format!("0.{}{digits}", "0".repeat((-exp - 1) as usize))
        }
    } else {
        let m = if digits.len() > 1 { format!("{}.{}", &digits[..1], &digits[1..]) } else { digits.clone() };
        format!("{m}e{}{:02}", if exp < 0 { '-' } else { '+' }, exp.abs())
    };
    if neg {
        format!("-{out}")
    } else {
        out
    }
}

fn esc(s: &str, out: &mut String) {
    out.push('"');
    for ch in s.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\u{8}' => out.push_str("\\b"),
            '\u{c}' => out.push_str("\\f"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
}

fn emit(v: &J, indent: usize, level: usize, sort: bool, out: &mut String) {
    match v {
        J::Null => out.push_str("null"),
        J::Bool(b) => out.push_str(if *b { "true" } else { "false" }),
        J::Int(i) => out.push_str(&i.to_string()),
        J::BigInt(s) => out.push_str(s),
        J::Float(f) => out.push_str(&py_float(*f)),
        J::Str(s) => esc(s, out),
        J::Arr(a) => {
            if a.is_empty() {
                out.push_str("[]");
                return;
            }
            out.push('[');
            for (i, x) in a.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                if indent > 0 {
                    out.push('\n');
                    out.push_str(&" ".repeat(indent * (level + 1)));
                }
                emit(x, indent, level + 1, sort, out);
            }
            if indent > 0 {
                out.push('\n');
                out.push_str(&" ".repeat(indent * level));
            }
            out.push(']');
        }
        J::Obj(m) => {
            if m.is_empty() {
                out.push_str("{}");
                return;
            }
            let mut items: Vec<&(String, J)> = m.iter().collect();
            if sort {
                items.sort_by(|a, b| a.0.as_bytes().cmp(b.0.as_bytes()));
            }
            out.push('{');
            for (i, (k, x)) in items.iter().map(|p| (&p.0, &p.1)).enumerate() {
                if i > 0 {
                    out.push(',');
                }
                if indent > 0 {
                    out.push('\n');
                    out.push_str(&" ".repeat(indent * (level + 1)));
                }
                esc(k, out);
                out.push_str(if indent > 0 { ": " } else { ":" });
                emit(x, indent, level + 1, sort, out);
            }
            if indent > 0 {
                out.push('\n');
                out.push_str(&" ".repeat(indent * level));
            }
            out.push('}');
        }
    }
}

/// The bytes of a JSON file as every libs/ writer emits it.
pub fn pretty(v: &J) -> Vec<u8> {
    let mut s = String::new();
    emit(v, 2, 0, false, &mut s);
    s.push('\n');
    s.into_bytes()
}

/// MINI-SPECS section 3 canonical JSON.
pub fn canonical(v: &J) -> Vec<u8> {
    let mut s = String::new();
    emit(v, 0, 0, true, &mut s);
    s.into_bytes()
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn floats_spell_like_python() {
        for (x, want) in [(1.0, "1.0"), (0.5, "0.5"), (1e16, "1e+16"), (1e-5, "1e-05"), (1.5e300, "1.5e+300"),
                          (0.0001, "0.0001"), (123456789012345.6, "123456789012345.6"), (5e-324, "5e-324"),
                          (-2.5, "-2.5"), (1e15, "1000000000000000.0"), (0.1, "0.1")] {
            assert_eq!(py_float(x), want, "{x}");
        }
    }

    /// libs/tests/test_vectors.py writes 20 011 doubles with Python's repr of
    /// each; `WERK_FLOATS=<that file> cargo test` checks this emitter on all.
    #[test]
    fn floats_file_matches_python() {
        let Ok(path) = std::env::var("WERK_FLOATS") else { return };
        let text = std::fs::read_to_string(path).unwrap();
        let mut bad = 0;
        let mut n = 0;
        for line in text.lines() {
            let (h, want) = line.split_once(' ').unwrap();
            let x = f64::from_bits(u64::from_str_radix(h, 16).unwrap());
            n += 1;
            if py_float(x) != want {
                bad += 1;
                if bad < 5 {
                    eprintln!("{h}: python {want} rust {}", py_float(x));
                }
            }
        }
        eprintln!("{n} doubles, {bad} differ");
        assert_eq!(bad, 0);
    }
}
