//! A backtracking matcher for the regular-expression subset that appears in
//! werk's JSON Schemas — nothing more.
//!
//! Why not a regex crate: the schemas are part of the format and travel inside
//! every package, so the set of constructs they use is closed and small. It is
//! this:
//!
//!   ^ $ . | ( ) (?: ) (?! ) [abc] [^abc] [a-z] * + ? {n} {n,} {n,m}
//!   \d \w \s \D \W \S and \<punct> escapes
//!
//! The one construct that rules out most toy matchers is the negative
//! lookahead in `$defs/path`:
//!     ^(?!/)(?!.*(^|/)\.\.(/|$))[A-Za-z0-9][A-Za-z0-9._@/-]*$
//! which is what forbids a leading slash and any `..` segment. That check is
//! load-bearing — it is the reason a package cannot name a file outside itself
//! — so it is implemented rather than approximated.
//!
//! Patterns and subjects are treated as bytes. Every pattern in the spec is
//! ASCII; a non-ASCII subject simply will not match an ASCII class, which is
//! the correct answer for id and path patterns.

#[derive(Debug, Clone)]
enum Node {
    Char(u8),
    Any,
    Class { neg: bool, ranges: Vec<(u8, u8)> },
    Start,
    End,
    Group(Alt),
    Look { neg: bool, inner: Alt },
    Repeat { node: Box<Node>, min: u32, max: u32 },
}

#[derive(Debug, Clone)]
struct Alt {
    branches: Vec<Vec<Node>>,
}

#[derive(Debug, Clone)]
pub struct Regex {
    root: Alt,
    src: String,
}

const INF: u32 = u32::MAX;

struct Parser<'a> {
    b: &'a [u8],
    i: usize,
}

impl<'a> Parser<'a> {
    fn peek(&self) -> Option<u8> {
        self.b.get(self.i).copied()
    }
    fn bump(&mut self) -> Option<u8> {
        let c = self.peek();
        if c.is_some() {
            self.i += 1;
        }
        c
    }

    fn alt(&mut self) -> Result<Alt, String> {
        let mut branches = vec![self.concat()?];
        while self.peek() == Some(b'|') {
            self.i += 1;
            branches.push(self.concat()?);
        }
        Ok(Alt { branches })
    }

    fn concat(&mut self) -> Result<Vec<Node>, String> {
        let mut seq = Vec::new();
        loop {
            match self.peek() {
                None | Some(b'|') | Some(b')') => break,
                _ => {}
            }
            let atom = self.atom()?;
            seq.push(self.quantify(atom)?);
        }
        Ok(seq)
    }

    fn quantify(&mut self, atom: Node) -> Result<Node, String> {
        let (min, max) = match self.peek() {
            Some(b'*') => {
                self.i += 1;
                (0, INF)
            }
            Some(b'+') => {
                self.i += 1;
                (1, INF)
            }
            Some(b'?') => {
                self.i += 1;
                (0, 1)
            }
            Some(b'{') => {
                // Only a real {n}/{n,}/{n,m} counts; a stray '{' is a literal.
                let save = self.i;
                self.i += 1;
                let n = self.number();
                match (n, self.peek()) {
                    (Some(n), Some(b'}')) => {
                        self.i += 1;
                        (n, n)
                    }
                    (Some(n), Some(b',')) => {
                        self.i += 1;
                        let m = self.number();
                        if self.peek() != Some(b'}') {
                            self.i = save;
                            return Ok(atom);
                        }
                        self.i += 1;
                        (n, m.unwrap_or(INF))
                    }
                    _ => {
                        self.i = save;
                        return Ok(atom);
                    }
                }
            }
            _ => return Ok(atom),
        };
        // Greedy only. The schemas contain no lazy quantifiers and adding
        // them would be untested code in a validator.
        Ok(Node::Repeat { node: Box::new(atom), min, max })
    }

    fn number(&mut self) -> Option<u32> {
        let start = self.i;
        while matches!(self.peek(), Some(c) if c.is_ascii_digit()) {
            self.i += 1;
        }
        if start == self.i {
            return None;
        }
        std::str::from_utf8(&self.b[start..self.i]).ok()?.parse().ok()
    }

    fn atom(&mut self) -> Result<Node, String> {
        match self.bump().ok_or("unexpected end of pattern")? {
            b'^' => Ok(Node::Start),
            b'$' => Ok(Node::End),
            b'.' => Ok(Node::Any),
            b'(' => {
                let node = if self.peek() == Some(b'?') {
                    self.i += 1;
                    match self.bump() {
                        Some(b':') => Node::Group(self.alt()?),
                        Some(b'!') => Node::Look { neg: true, inner: self.alt()? },
                        Some(b'=') => Node::Look { neg: false, inner: self.alt()? },
                        other => {
                            return Err(format!("unsupported group (?{:?}", other.map(|c| c as char)))
                        }
                    }
                } else {
                    // Capturing groups are parsed but nothing captures: the
                    // validator only ever asks "did it match".
                    Node::Group(self.alt()?)
                };
                if self.bump() != Some(b')') {
                    return Err("unbalanced '('".into());
                }
                Ok(node)
            }
            b'[' => self.class(),
            b'\\' => {
                let c = self.bump().ok_or("trailing backslash")?;
                Ok(escape_node(c))
            }
            c => Ok(Node::Char(c)),
        }
    }

    fn class(&mut self) -> Result<Node, String> {
        let mut neg = false;
        if self.peek() == Some(b'^') {
            neg = true;
            self.i += 1;
        }
        let mut ranges: Vec<(u8, u8)> = Vec::new();
        let mut first = true;
        loop {
            let c = self.bump().ok_or("unterminated character class")?;
            if c == b']' && !first {
                break;
            }
            first = false;
            let lo = if c == b'\\' {
                let e = self.bump().ok_or("trailing backslash in class")?;
                match escape_node(e) {
                    Node::Char(ch) => ch,
                    Node::Class { neg: false, ranges: mut r } => {
                        ranges.append(&mut r);
                        continue;
                    }
                    Node::Class { neg: true, ranges: r } => {
                        // \D \W \S inside a class: expand the complement.
                        ranges.append(&mut complement(&r));
                        continue;
                    }
                    _ => return Err("unsupported escape in class".into()),
                }
            } else {
                c
            };
            // A '-' that is not between two members is a literal '-'.
            if self.peek() == Some(b'-')
                && self.b.get(self.i + 1).copied().map_or(false, |n| n != b']')
            {
                self.i += 1;
                let hi = self.bump().ok_or("unterminated range")?;
                let hi = if hi == b'\\' {
                    match escape_node(self.bump().ok_or("trailing backslash")?) {
                        Node::Char(ch) => ch,
                        _ => return Err("range end must be a literal".into()),
                    }
                } else {
                    hi
                };
                ranges.push((lo, hi));
            } else {
                ranges.push((lo, lo));
            }
        }
        Ok(Node::Class { neg, ranges })
    }
}

fn complement(ranges: &[(u8, u8)]) -> Vec<(u8, u8)> {
    let mut sorted = ranges.to_vec();
    sorted.sort_unstable();
    let mut out = Vec::new();
    let mut next = 0u32;
    for (lo, hi) in sorted {
        if (lo as u32) > next {
            out.push((next as u8, (lo - 1) as u8));
        }
        next = next.max(hi as u32 + 1);
    }
    if next <= 255 {
        out.push((next as u8, 255));
    }
    out
}

fn escape_node(c: u8) -> Node {
    match c {
        b'd' => Node::Class { neg: false, ranges: vec![(b'0', b'9')] },
        b'D' => Node::Class { neg: true, ranges: vec![(b'0', b'9')] },
        b'w' => Node::Class {
            neg: false,
            ranges: vec![(b'a', b'z'), (b'A', b'Z'), (b'0', b'9'), (b'_', b'_')],
        },
        b'W' => Node::Class {
            neg: true,
            ranges: vec![(b'a', b'z'), (b'A', b'Z'), (b'0', b'9'), (b'_', b'_')],
        },
        b's' => Node::Class {
            neg: false,
            ranges: vec![(b' ', b' '), (0x09, 0x0d)],
        },
        b'S' => Node::Class {
            neg: true,
            ranges: vec![(b' ', b' '), (0x09, 0x0d)],
        },
        b'n' => Node::Char(b'\n'),
        b'r' => Node::Char(b'\r'),
        b't' => Node::Char(b'\t'),
        other => Node::Char(other),
    }
}

impl Regex {
    pub fn new(pattern: &str) -> Result<Regex, String> {
        let mut p = Parser { b: pattern.as_bytes(), i: 0 };
        let root = p.alt()?;
        if p.i != p.b.len() {
            return Err(format!("unparsed tail at byte {} of /{}/", p.i, pattern));
        }
        Ok(Regex { root, src: pattern.to_string() })
    }

    pub fn as_str(&self) -> &str {
        &self.src
    }

    /// JSON Schema `pattern` is an unanchored search, so try every start.
    pub fn is_match(&self, subject: &str) -> bool {
        let s = subject.as_bytes();
        for start in 0..=s.len() {
            if m_alt(&self.root, s, start, &|_| true) {
                return true;
            }
        }
        false
    }
}

fn m_alt(a: &Alt, s: &[u8], pos: usize, k: &dyn Fn(usize) -> bool) -> bool {
    a.branches.iter().any(|b| m_seq(b, s, pos, k))
}

fn m_seq(seq: &[Node], s: &[u8], pos: usize, k: &dyn Fn(usize) -> bool) -> bool {
    match seq.split_first() {
        None => k(pos),
        Some((n, rest)) => m_node(n, s, pos, &|p| m_seq(rest, s, p, k)),
    }
}

fn m_node(n: &Node, s: &[u8], pos: usize, k: &dyn Fn(usize) -> bool) -> bool {
    match n {
        Node::Char(c) => pos < s.len() && s[pos] == *c && k(pos + 1),
        Node::Any => pos < s.len() && s[pos] != b'\n' && k(pos + 1),
        Node::Class { neg, ranges } => {
            if pos >= s.len() {
                return false;
            }
            let c = s[pos];
            let inside = ranges.iter().any(|(lo, hi)| c >= *lo && c <= *hi);
            inside != *neg && k(pos + 1)
        }
        Node::Start => pos == 0 && k(pos),
        Node::End => pos == s.len() && k(pos),
        Node::Group(a) => m_alt(a, s, pos, k),
        Node::Look { neg, inner } => {
            // Zero-width: the lookahead consumes nothing whether it matched or
            // not; it only decides whether we continue from `pos`.
            let hit = m_alt(inner, s, pos, &|_| true);
            if hit != *neg {
                k(pos)
            } else {
                false
            }
        }
        Node::Repeat { node, min, max } => m_repeat(node, s, pos, *min, *max, k),
    }
}

fn m_repeat(n: &Node, s: &[u8], pos: usize, min: u32, max: u32, k: &dyn Fn(usize) -> bool) -> bool {
    if min > 0 {
        return m_node(n, s, pos, &|p| {
            // Guard against an empty match satisfying an unbounded minimum,
            // which would loop forever on e.g. (a?)+.
            if p == pos {
                return false;
            }
            m_repeat(n, s, p, min - 1, max.saturating_sub(1), k)
        });
    }
    if max > 0
        && m_node(n, s, pos, &|p| {
            p != pos && m_repeat(n, s, p, 0, if max == INF { INF } else { max - 1 }, k)
        })
    {
        return true;
    }
    k(pos)
}

#[cfg(test)]
mod tests {
    use super::Regex;

    fn m(p: &str, s: &str) -> bool {
        Regex::new(p).expect(p).is_match(s)
    }

    #[test]
    fn kebab_ids() {
        let p = r"^[a-z0-9]+(-[a-z0-9]+)*$";
        assert!(m(p, "crate"));
        assert!(m(p, "crate-lid"));
        assert!(m(p, "a1-b2-c3"));
        assert!(!m(p, "Crate"));
        assert!(!m(p, "crate-"));
        assert!(!m(p, "-crate"));
        assert!(!m(p, "crate_lid"));
    }

    #[test]
    fn hex_digests() {
        let p = r"^[0-9a-f]{64}$";
        assert!(m(p, &"a".repeat(64)));
        assert!(!m(p, &"a".repeat(63)));
        assert!(!m(p, &"a".repeat(65)));
        assert!(!m(p, &"A".repeat(64)));
    }

    #[test]
    fn node_types() {
        let p = r"^(core|x)\.[a-z0-9-]+(\.[a-z0-9-]+)*$";
        assert!(m(p, "core.geom.game"));
        assert!(m(p, "x.cub.v1"));
        assert!(m(p, "core.tex"));
        assert!(!m(p, "core"));
        assert!(!m(p, "y.thing"));
        assert!(!m(p, "core.Geom"));
    }

    #[test]
    fn uuid() {
        let p = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$";
        assert!(m(p, "6f1c2b7a-9d3e-4a10-8c55-2b8e41d0a7c3"));
        assert!(!m(p, "6f1c2b7a-9d3e-4a10-8c55-2b8e41d0a7c"));
    }

    #[test]
    fn schema_paths() {
        let p = r"^spec/schemas/[A-Za-z0-9._-]+\.schema\.json$";
        assert!(m(p, "spec/schemas/core.material.schema.json"));
        assert!(!m(p, "spec/schemas/core.material.json"));
        assert!(!m(p, "../spec/schemas/x.schema.json"));
    }

    /// The one that matters: no leading slash, no `..` segment anywhere.
    #[test]
    fn package_paths_with_lookahead() {
        let p = r"^(?!/)(?!.*(^|/)\.\.(/|$))[A-Za-z0-9][A-Za-z0-9._@/-]*$";
        assert!(m(p, "geometry/game.glb"));
        assert!(m(p, "MANIFEST.json"));
        assert!(m(p, "audio/crate/crate-impact.wav"));
        assert!(m(p, "poses/rest@2.wkrp"));
        assert!(!m(p, "/etc/passwd"));
        assert!(!m(p, "../escape.txt"));
        assert!(!m(p, "geometry/../../escape.txt"));
        assert!(!m(p, "geometry/.."));
        assert!(!m(p, "C:/windows/system32"));
        assert!(!m(p, "geometry\\game.glb"));
        // A file literally named "..x" is fine; only the `..` SEGMENT is banned.
        assert!(m(p, "geometry/a..b"));
    }
}
