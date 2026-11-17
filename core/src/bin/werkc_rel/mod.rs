//! The release commands of werkc: pack-image, pack-mesh, extract, cat,
//! append, sign, and `verify --json`. They mirror libs/python/werk/_core.py
//! and libs/js/src/core.js exactly -- same options, same exit statuses, and
//! for identical input the SAME BYTES (libs/tests/cross_matrix.py checks it).
//! Reading and verification are werk-core's (`Package::open`), the reference
//! full reader; writing is done here with an order-preserving JSON so the
//! output matches the other writers byte for byte.

pub mod bundle_files;
pub mod json;

use ed25519_dalek::{Signer, SigningKey};
use json::{obj, J};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;
use werk::package::Package;

pub const LIB_VERSION: &str = "0.1.0";
const MANIFEST: &str = "MANIFEST.json";
const SIGNATURE: &str = "SIGNATURE.json";

type R<T> = Result<T, String>;

fn sha_hex(b: &[u8]) -> String {
    hex(&Sha256::digest(b))
}
fn hex(b: &[u8]) -> String {
    b.iter().map(|x| format!("{x:02x}")).collect()
}
fn unhex(s: &str) -> R<Vec<u8>> {
    if s.len() % 2 != 0 || !s.chars().all(|c| c.is_ascii_hexdigit()) {
        return Err("not hex".into());
    }
    Ok((0..s.len()).step_by(2).map(|i| u8::from_str_radix(&s[i..i + 2], 16).unwrap()).collect())
}

fn crc32(data: &[u8]) -> u32 {
    let mut table = [0u32; 256];
    for n in 0..256u32 {
        let mut c = n;
        for _ in 0..8 {
            c = if c & 1 != 0 { 0xEDB8_8320 ^ (c >> 1) } else { c >> 1 };
        }
        table[n as usize] = c;
    }
    let mut c = 0xFFFF_FFFFu32;
    for b in data {
        c = table[((c ^ *b as u32) & 0xFF) as usize] ^ (c >> 8);
    }
    c ^ 0xFFFF_FFFF
}

// ------------------------------------------------------------------ bundle

pub struct Bundle {
    pub info: J,
    files: BTreeMap<String, &'static [u8]>,
}

impl Bundle {
    pub fn load() -> R<Bundle> {
        let info = json::parse(bundle_files::BUNDLE_JSON)?;
        let mut files = BTreeMap::new();
        for (p, b) in bundle_files::FILES {
            files.insert(p.to_string(), *b);
        }
        let bnd = Bundle { info, files };
        for rec in bnd.records() {
            let p = rec.get("path").and_then(J::as_str).unwrap();
            let b = bnd.files.get(p).ok_or(format!("bundle file {p} is not compiled in"))?;
            if sha_hex(b) != rec.get("sha256").and_then(J::as_str).unwrap_or("") {
                return Err(format!(
                    "this repository's {p} is not the bytes bundle.json declares; rebuild the \
                     bundle (libs/tools/make_bundle.py + build_rust_bundle.py) or check out the \
                     matching spec/"
                ));
            }
        }
        Ok(bnd)
    }
    pub fn records(&self) -> &Vec<J> {
        self.info.get("files").and_then(J::as_arr).unwrap()
    }
    pub fn rec(&self, p: &str) -> Option<&J> {
        self.records().iter().find(|r| r.get("path").and_then(J::as_str) == Some(p))
    }
    pub fn bytes(&self, p: &str) -> &'static [u8] {
        self.files[p]
    }
    fn s(&self, path: &[&str]) -> String {
        let mut v = &self.info;
        for k in path {
            v = v.get(k).unwrap();
        }
        v.as_str().unwrap().to_string()
    }
}

// ------------------------------------------------------------------ hashes, signatures

pub fn spec_sha256_of(nodes: &[J]) -> String {
    let mut declared: BTreeMap<Vec<u8>, String> = BTreeMap::new();
    for n in nodes {
        for v in n.get("versions").and_then(J::as_arr).map(|a| a.as_slice()).unwrap_or(&[]) {
            for f in v.get("files").and_then(J::as_arr).map(|a| a.as_slice()).unwrap_or(&[]) {
                if let Some(p) = f.get("path").and_then(J::as_str) {
                    if p.starts_with("spec/") {
                        declared.insert(p.as_bytes().to_vec(), f.get("sha256").and_then(J::as_str).unwrap_or("").into());
                    }
                }
            }
        }
    }
    let mut h = Sha256::new();
    for (p, s) in &declared {
        h.update(p);
        h.update(b"\n");
        h.update(unhex(s).unwrap_or_default());
        h.update(b"\n");
    }
    hex(&h.finalize())
}

pub fn input_hash_of(raw: &[Vec<u8>], params: &J) -> String {
    let mut h = Sha256::new();
    for d in raw {
        h.update(d);
    }
    h.update(json::canonical(params));
    hex(&h.finalize())
}

fn sig_message(m: &str, prev: &str, at: &str, uri: &str, kind: &str) -> Vec<u8> {
    ["werk-sig/1", m, prev, at, uri, kind].join("\n").into_bytes()
}

pub fn parse_secret(text: &str) -> R<[u8; 32]> {
    let t = text.trim().to_lowercase();
    if t.len() != 64 {
        return Err("an Ed25519 secret key is given as 64 hex digits (the 32-byte seed)".into());
    }
    let v = unhex(&t)?;
    let mut k = [0u8; 32];
    k.copy_from_slice(&v);
    Ok(k)
}

#[derive(Clone)]
pub struct SignerOpt {
    pub key: [u8; 32],
    pub uri: String,
    pub kind: String,
    pub name: Option<String>,
    pub role: Option<String>,
    pub note: Option<String>,
    pub signed_at: Option<String>,
}

pub fn chain_append(existing: Option<J>, msha: &str, s: &SignerOpt, default_at: &str) -> R<J> {
    let mut doc = match existing {
        None => obj(vec![
            ("werk_signature", J::Int(1)),
            ("algorithm", J::s("ed25519")),
            ("encoding", J::s("hex-lowercase")),
            ("manifest_sha256", J::s(msha)),
            ("chain", J::Arr(vec![])),
        ]),
        Some(mut d) => {
            d.set("manifest_sha256", J::s(msha));
            d
        }
    };
    if !["human", "agent", "service"].contains(&s.kind.as_str()) {
        return Err("signer kind is human, agent or service (signature.schema.json)".into());
    }
    let at = s.signed_at.clone().unwrap_or_else(|| default_at.to_string());
    if s.uri.contains('\n') || at.contains('\n') {
        return Err("a signed field may not contain a line feed".into());
    }
    let chain = doc.get_mut("chain").and_then(J::as_arr_mut).ok_or("SIGNATURE.json has no chain")?;
    let prev = match chain.last() {
        None => "0".repeat(64),
        Some(e) => sha_hex(e.get("signature").and_then(J::as_str).unwrap_or("").as_bytes()),
    };
    let sk = SigningKey::from_bytes(&s.key);
    let sig = sk.sign(&sig_message(msha, &prev, &at, &s.uri, &s.kind));
    let mut signer = obj(vec![
        ("name", J::s(s.name.as_deref().unwrap_or(&s.uri))),
        ("uri", J::s(&s.uri)),
        ("kind", J::s(&s.kind)),
    ]);
    if let Some(r) = s.role.as_deref().filter(|r| !r.is_empty()) {
        signer.set("role", J::s(r));
    }
    let mut e = obj(vec![
        ("index", J::Int(chain.len() as i64)),
        ("signer", signer),
        ("public_key", J::s(&hex(&sk.verifying_key().to_bytes()))),
        ("signed_at", J::s(&at)),
        ("manifest_sha256", J::s(msha)),
        ("prev_entry_sha256", J::s(&prev)),
        ("signature", J::s(&hex(&sig.to_bytes()))),
    ]);
    if let Some(n) = s.note.as_deref() {
        e.set("note", J::s(n));
    }
    chain.push(e);
    Ok(doc)
}

// ------------------------------------------------------------------ container

fn dos_datetime(created: &str) -> R<(u16, u16)> {
    let b = created.as_bytes();
    let num = |a: usize, z: usize| -> R<u32> {
        created.get(a..z).and_then(|s| s.parse().ok()).ok_or("created must be RFC 3339 UTC, e.g. 2026-11-07T12:00:00Z".to_string())
    };
    if b.len() < 19 {
        return Err("created must be RFC 3339 UTC, e.g. 2026-11-07T12:00:00Z".into());
    }
    let (mut y, mut mo, mut d, mut h, mut mi, mut s) = (num(0, 4)?, num(5, 7)?, num(8, 10)?, num(11, 13)?, num(14, 16)?, num(17, 19)?);
    if y < 1980 {
        (y, mo, d, h, mi, s) = (1980, 1, 1, 0, 0, 0);
    }
    Ok((((h << 11) | (mi << 5) | (s / 2)) as u16, (((y - 1980) << 9) | (mo << 5) | d) as u16))
}

pub fn physical_order(paths: &[String], entry_order: &[String]) -> Vec<String> {
    let mut left: Vec<String> = paths.to_vec();
    left.sort_by(|a, b| a.as_bytes().cmp(b.as_bytes()));
    left.dedup();
    let mut placed: BTreeMap<String, usize> = BTreeMap::new();
    for (i, pat) in entry_order.iter().enumerate() {
        if !pat.ends_with('/') && left.contains(pat) && !placed.contains_key(pat) {
            placed.insert(pat.clone(), i);
        }
    }
    for (i, pat) in entry_order.iter().enumerate() {
        if pat.ends_with('/') {
            for p in &left {
                if !placed.contains_key(p) && p.starts_with(pat.as_str()) {
                    placed.insert(p.clone(), i);
                }
            }
        }
    }
    let mut listed: Vec<String> = left.iter().filter(|p| placed.contains_key(*p)).cloned().collect();
    listed.sort_by(|a, b| placed[a].cmp(&placed[b]).then(a.as_bytes().cmp(b.as_bytes())));
    let mut order: Vec<String> = listed;
    order.extend(left.iter().filter(|p| !placed.contains_key(*p)).cloned());
    if let Some(i) = order.iter().position(|p| p == MANIFEST) {
        let m = order.remove(i);
        order.insert(0, m);
    }
    order
}

/// A file of the package being written: owned bytes, or a vendored bundle file.
#[derive(Clone)]
pub enum Blob {
    Data(Vec<u8>),
    Bundle(&'static [u8], u32),
}
impl Blob {
    fn bytes(&self) -> &[u8] {
        match self {
            Blob::Data(d) => d,
            Blob::Bundle(b, _) => b,
        }
    }
}

fn zip_bytes(blobs: &BTreeMap<String, Blob>, mb: &[u8], sb: Option<&[u8]>, entry_order: &[String], created: &str) -> R<Vec<u8>> {
    let (t, d) = dos_datetime(created)?;
    let mut all: Vec<String> = blobs.keys().cloned().collect();
    all.push(MANIFEST.into());
    if sb.is_some() {
        all.push(SIGNATURE.into());
    }
    let order = physical_order(&all, entry_order);
    if order.len() > 65534 {
        return Err("more than 65534 entries; write this package in directory form".into());
    }
    let mut body: Vec<u8> = Vec::new();
    let mut central: Vec<u8> = Vec::new();
    for name in &order {
        let (data, crc): (&[u8], u32) = if name == MANIFEST {
            (mb, crc32(mb))
        } else if name == SIGNATURE {
            (sb.unwrap(), crc32(sb.unwrap()))
        } else {
            match &blobs[name] {
                Blob::Data(x) => (x.as_slice(), crc32(x)),
                Blob::Bundle(x, c) => (*x, *c),
            }
        };
        let nb = name.as_bytes();
        let off = body.len();
        if off + 30 + nb.len() + data.len() >= 0xFFFF_FFFF {
            return Err("the zip form ends below 4 GiB; write this package in directory form".into());
        }
        let n = data.len() as u32;
        for v in [0x0403_4B50u32] { body.extend(v.to_le_bytes()); }
        for v in [20u16, 0x0800, 0, t, d] { body.extend(v.to_le_bytes()); }
        for v in [crc, n, n] { body.extend(v.to_le_bytes()); }
        for v in [nb.len() as u16, 0] { body.extend(v.to_le_bytes()); }
        body.extend(nb);
        body.extend(data);
        central.extend(0x0201_4B50u32.to_le_bytes());
        for v in [20u16, 20, 0x0800, 0, t, d] { central.extend(v.to_le_bytes()); }
        for v in [crc, n, n] { central.extend(v.to_le_bytes()); }
        for v in [nb.len() as u16, 0, 0, 0, 0] { central.extend(v.to_le_bytes()); }
        central.extend(0u32.to_le_bytes());
        central.extend((off as u32).to_le_bytes());
        central.extend(nb);
    }
    let cd_off = body.len() as u32;
    let cd_len = central.len() as u32;
    body.extend(central);
    body.extend(0x0605_4B50u32.to_le_bytes());
    for v in [0u16, 0, order.len() as u16, order.len() as u16] { body.extend(v.to_le_bytes()); }
    body.extend(cd_len.to_le_bytes());
    body.extend(cd_off.to_le_bytes());
    body.extend(0u16.to_le_bytes());
    Ok(body)
}

pub fn write_container(out: &str, form: &str, blobs: &BTreeMap<String, Blob>, mb: &[u8], sb: Option<&[u8]>, entry_order: &[String], created: &str) -> R<()> {
    if form == "zip" {
        let z = zip_bytes(blobs, mb, sb, entry_order, created)?;
        let tmp = format!("{out}.partial");
        std::fs::write(&tmp, z).map_err(|e| e.to_string())?;
        let _ = std::fs::remove_file(out);
        std::fs::rename(&tmp, out).map_err(|e| e.to_string())?;
        return Ok(());
    }
    if form != "directory" {
        return Err("form is zip or directory".into());
    }
    let root = Path::new(out);
    if root.exists() && std::fs::read_dir(root).map_err(|e| e.to_string())?.next().is_some() {
        return Err(format!("{out} exists and is not empty; a directory package is written fresh"));
    }
    let mut items: Vec<(String, &[u8])> = blobs.iter().map(|(k, v)| (k.clone(), v.bytes())).collect();
    items.push((MANIFEST.into(), mb));
    if let Some(s) = sb {
        items.push((SIGNATURE.into(), s));
    }
    for (p, b) in items {
        let full = p.split('/').fold(root.to_path_buf(), |acc, seg| acc.join(seg));
        if let Some(d) = full.parent() {
            std::fs::create_dir_all(d).map_err(|e| e.to_string())?;
        }
        std::fs::write(&full, b).map_err(|e| e.to_string())?;
    }
    Ok(())
}

pub fn form_of(out: &str, explicit: Option<&str>) -> String {
    if let Some(f) = explicit {
        return f.to_string();
    }
    let l = out.to_lowercase();
    if l.ends_with(".werk") || l.ends_with(".zip") { "zip".into() } else { "directory".into() }
}

// ------------------------------------------------------------------ writer

fn is_id(s: &str) -> bool {
    !s.is_empty()
        && s.split('-').all(|p| !p.is_empty() && p.bytes().all(|c| c.is_ascii_lowercase() || c.is_ascii_digit()))
}
fn check_id(s: &str, what: &str) -> R<()> {
    if is_id(s) { Ok(()) } else { Err(format!("{what} {s} is not kebab-case")) }
}
fn check_path(p: &str) -> R<()> {
    let first_ok = p.bytes().next().map_or(false, |c| c.is_ascii_alphanumeric());
    let rest_ok = p.bytes().all(|c| c.is_ascii_alphanumeric() || b"._@/-".contains(&c));
    if !first_ok || !rest_ok || p.len() > 1024 || p.split('/').any(|s| s == "..") || p.ends_with('/') || p.contains("//") {
        return Err(format!("package path {p} is not legal: relative POSIX, ASCII letters, digits and . _ @ / - only, first character a letter or digit, no '..' (manifest.schema.json $defs/path)"));
    }
    if p == MANIFEST || p == SIGNATURE {
        return Err(format!("{p} is written by the writer itself"));
    }
    Ok(())
}
fn is_type(t: &str) -> bool {
    let rest = if let Some(r) = t.strip_prefix("core.") { r } else if let Some(r) = t.strip_prefix("x.") { r } else { return false };
    !rest.is_empty() && rest.split('.').all(|s| !s.is_empty() && s.bytes().all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == b'-'))
}
fn check_note(n: &str) -> R<()> {
    let c = n.chars().count();
    if (8..=2000).contains(&c) { Ok(()) } else { Err("every version carries a work note of 8-2000 characters saying why it exists (law 6)".into()) }
}

pub struct NewFile {
    pub path: String,
    pub data: Vec<u8>,
    pub media_type: Option<String>,
    pub role: Option<String>,
}
pub fn nf(path: &str, data: Vec<u8>, mt: Option<&str>, role: Option<&str>) -> R<NewFile> {
    check_path(path)?;
    if let Some(r) = role {
        check_id(r, "role")?;
    }
    Ok(NewFile { path: path.into(), data, media_type: mt.map(String::from), role: role.map(String::from) })
}

#[derive(Default)]
pub struct NodeOpts {
    pub epistemic: Option<String>,
    pub producer: Option<J>,
    pub meta: Option<J>,
    pub edges: Vec<(String, String, Option<String>)>,
    pub input_files: Option<Vec<String>>,
    pub input_params: Option<J>,
    pub payload_file: Option<String>,
    pub part_id: Option<String>,
    pub material_id: Option<String>,
}

#[allow(clippy::too_many_arguments)]
fn version_record(v: i64, files: Vec<J>, payload_file: Option<String>, note: &str, producer: J, epistemic: &str,
                  created: &str, inputs: Option<(Vec<String>, J, String)>) -> J {
    let mut r = obj(vec![("v", J::Int(v)), ("files", J::Arr(files))]);
    if let Some(p) = payload_file {
        r.set("payload_file", J::Str(p));
    }
    r.set("note", J::s(note));
    r.set("producer", producer);
    r.set("epistemic", J::s(epistemic));
    r.set("created", J::s(created));
    if let Some((f, p, h)) = inputs {
        r.set("input_files", J::Arr(f.iter().map(|s| J::s(s)).collect()));
        r.set("input_params", p);
        r.set("input_hash", J::Str(h));
    }
    r
}

fn file_rec(f: &NewFile) -> J {
    let mut r = obj(vec![("path", J::s(&f.path)), ("sha256", J::Str(sha_hex(&f.data))), ("size", J::Int(f.data.len() as i64))]);
    if let Some(m) = &f.media_type {
        r.set("media_type", J::s(m));
    }
    if let Some(ro) = &f.role {
        r.set("role", J::s(ro));
    }
    r
}

fn edge(to: &str, kind: &str, role: Option<&str>) -> R<J> {
    check_id(to, "edge target")?;
    if kind != "requires" && kind != "enhances" {
        return Err("edge kind is requires or enhances".into());
    }
    let mut e = obj(vec![("to", J::s(to)), ("kind", J::s(kind))]);
    if let Some(r) = role.filter(|r| !r.is_empty()) {
        check_id(r, "edge role")?;
        e.set("role", J::s(r));
    }
    Ok(e)
}

pub struct Writer {
    pub bundle: Bundle,
    pub profile: String,
    ptab: J,
    pub created: String,
    uuid: String,
    name: String,
    summary: Option<String>,
    producer: J,
    generator: J,
    spdx_id: Option<String>,
    pub nodes: Vec<J>,
    pub blobs: BTreeMap<String, Blob>,
    owner: BTreeMap<String, String>,
    primary: Vec<(String, String)>,
    parts: Vec<J>,
    materials: Vec<J>,
    schemas: Vec<(String, String)>,
    layouts: Vec<(String, String)>,
    preview_exact: Vec<String>,
    pub signers: Vec<SignerOpt>,
    pub conventions_map: Option<String>,
}

pub struct WriterOpts {
    pub name: String,
    pub summary: Option<String>,
    pub uuid: Option<String>,
    pub created: Option<String>,
    pub license_text: Option<Vec<u8>>,
    pub spdx_id: Option<String>,
}

fn utc_now() -> String {
    let secs = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map(|d| d.as_secs()).unwrap_or(0) as i64;
    let (days, rem) = (secs.div_euclid(86400), secs.rem_euclid(86400));
    // civil_from_days (Howard Hinnant)
    let z = days + 719468;
    let era = z.div_euclid(146097);
    let doe = z - era * 146097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if m <= 2 { y + 1 } else { y };
    format!("{y:04}-{m:02}-{d:02}T{:02}:{:02}:{:02}Z", rem / 3600, rem % 3600 / 60, rem % 60)
}

fn uuid4() -> String {
    // Not cryptographic: an entity id must be unique, not secret. Seeded from
    // time and address entropy; callers wanting reproducible output pass --uuid.
    let mut h = Sha256::new();
    h.update(format!("{:?}{:p}", std::time::SystemTime::now(), &h as *const _).as_bytes());
    let mut b = h.finalize().to_vec();
    b[6] = (b[6] & 0x0f) | 0x40;
    b[8] = (b[8] & 0x3f) | 0x80;
    let x = hex(&b[..16]);
    format!("{}-{}-{}-{}-{}", &x[0..8], &x[8..12], &x[12..16], &x[16..20], &x[20..32])
}

impl Writer {
    pub fn new(profile: &str, o: WriterOpts) -> R<Writer> {
        let bundle = Bundle::load()?;
        let ptab = bundle.info.get("profiles").and_then(|p| p.get(profile)).cloned()
            .ok_or(format!("profile {profile} is not built into werkc's writer"))?;
        if o.name.is_empty() || o.name.chars().count() > 200 {
            return Err("entity name must be 1-200 characters".into());
        }
        let created = o.created.unwrap_or_else(utc_now);
        dos_datetime(&created)?;
        let uuid = o.uuid.unwrap_or_else(uuid4).to_lowercase();
        let ok = uuid.len() == 36 && uuid.chars().enumerate().all(|(i, c)| if [8, 13, 18, 23].contains(&i) { c == '-' } else { c.is_ascii_hexdigit() });
        if !ok {
            return Err("uuid must be an RFC 4122 uuid in lower case".into());
        }
        let lv = bundle.s(&["lib_version"]);
        let mut w = Writer {
            producer: obj(vec![("tool", J::s("werk")), ("version", J::s(&lv))]),
            generator: obj(vec![("tool", J::s("werk")), ("version", J::s(&lv))]),
            bundle, profile: profile.into(), ptab, created, uuid, name: o.name, summary: o.summary,
            spdx_id: o.spdx_id, nodes: vec![], blobs: BTreeMap::new(), owner: BTreeMap::new(), primary: vec![],
            parts: vec![], materials: vec![], schemas: vec![], layouts: vec![], preview_exact: vec![], signers: vec![],
            conventions_map: None,
        };
        w.carry(o.license_text)?;
        Ok(w)
    }

    fn carry(&mut self, license: Option<Vec<u8>>) -> R<()> {
        let texts = |k: &str| self.bundle.s(&["texts", k]);
        let (spec_note, loader_note, lic_note, rd_note) = (texts("spec_note"), texts("loader_note"), texts("license_note"), texts("readme_note"));
        let (lic_default, readme) = (texts("license_unestablished"), texts("readme"));
        let mut spec_files = vec![];
        for rec in self.bundle.records().clone() {
            let p = rec.get("path").and_then(J::as_str).unwrap().to_string();
            if p.starts_with("spec/") {
                let crc = rec.get("crc32").and_then(J::as_i64).unwrap() as u32;
                self.blobs.insert(p.clone(), Blob::Bundle(self.bundle.bytes(&p), crc));
                self.owner.insert(p.clone(), "spec".into());
                spec_files.push(obj(vec![("path", J::s(&p)), ("sha256", rec.get("sha256").cloned().unwrap()), ("size", rec.get("size").cloned().unwrap())]));
            }
        }
        self.node_raw("spec", "core.spec", spec_files, &spec_note, None);
        let loaders = self.bundle.info.get("loaders").and_then(J::as_arr).unwrap().clone();
        for ld in loaders {
            let id = ld.get("node_id").and_then(J::as_str).unwrap().to_string();
            let p = ld.get("path").and_then(J::as_str).unwrap().to_string();
            let rec = self.bundle.rec(&p).unwrap().clone();
            let crc = rec.get("crc32").and_then(J::as_i64).unwrap() as u32;
            self.blobs.insert(p.clone(), Blob::Bundle(self.bundle.bytes(&p), crc));
            self.owner.insert(p.clone(), id.clone());
            let f = obj(vec![("path", J::s(&p)), ("sha256", rec.get("sha256").cloned().unwrap()), ("size", rec.get("size").cloned().unwrap())]);
            self.node_raw(&id, "core.loader", vec![f], &loader_note, ld.get("meta").cloned());
        }
        let lic = license.unwrap_or_else(|| lic_default.into_bytes());
        self.add_node("license", "core.license", vec![nf("LICENSE", lic, Some("text/plain"), None)?], &lic_note, NodeOpts::default())?;
        self.add_node("readme", "core.readme", vec![nf("README.txt", readme.into_bytes(), Some("text/plain"), None)?], &rd_note, NodeOpts::default())?;
        Ok(())
    }

    fn node_raw(&mut self, id: &str, t: &str, files: Vec<J>, note: &str, meta: Option<J>) {
        let mut n = obj(vec![
            ("node_id", J::s(id)),
            ("type", J::s(t)),
            ("versions", J::Arr(vec![version_record(1, files, None, note, self.producer.clone(), "authored", &self.created, None)])),
            ("active", J::Int(1)),
            ("edges", J::Arr(vec![])),
        ]);
        if let Some(m) = meta {
            n.set("meta", m);
        }
        self.nodes.push(n);
    }

    fn sha_of(&self, p: &str) -> R<String> {
        match self.blobs.get(p) {
            None => Err(format!("input file {p} is not in the package (law 1: inputs are carried)")),
            Some(b) => Ok(sha_hex(b.bytes())),
        }
    }

    pub fn add_node(&mut self, id: &str, t: &str, files: Vec<NewFile>, note: &str, o: NodeOpts) -> R<()> {
        check_id(id, "node_id")?;
        if self.nodes.iter().any(|n| n.get("node_id").and_then(J::as_str) == Some(id)) {
            return Err(format!("node {id} already exists"));
        }
        if !is_type(t) {
            return Err(format!("node type {t} is not core.* or x.* kebab-case"));
        }
        let ep = o.epistemic.clone().unwrap_or_else(|| "authored".into());
        if !["authored", "measured", "inferred"].contains(&ep.as_str()) {
            return Err("epistemic is authored, measured or inferred".into());
        }
        if ep != "authored" && o.input_files.as_ref().map_or(true, |v| v.is_empty()) {
            return Err(format!("a {ep} version names its inputs (law 5): pass input files"));
        }
        check_note(note)?;
        if files.is_empty() {
            return Err("a version owns at least one file".into());
        }
        let mut recs = vec![];
        for f in &files {
            if let Some(ow) = self.owner.get(&f.path) {
                return Err(format!("{} is already listed by node {ow}", f.path));
            }
            recs.push(file_rec(f));
        }
        for f in files {
            self.owner.insert(f.path.clone(), id.into());
            self.blobs.insert(f.path, Blob::Data(f.data));
        }
        let mut pf = o.payload_file.clone();
        if pf.is_none() && recs.len() > 1 {
            let roled: Vec<&J> = recs.iter().filter(|r| r.get("role").and_then(J::as_str) == Some("payload")).collect();
            if roled.len() == 1 {
                pf = roled[0].get("path").and_then(J::as_str).map(String::from);
            }
        }
        if let Some(p) = &pf {
            if !recs.iter().any(|r| r.get("path").and_then(J::as_str) == Some(p)) {
                return Err(format!("payload_file {p} is not one of the version's files"));
            }
        }
        let inputs = match &o.input_files {
            None => None,
            Some(fs) => {
                let params = o.input_params.clone().unwrap_or_else(J::obj);
                let mut raw = vec![];
                for p in fs {
                    raw.push(unhex(&self.sha_of(p)?)?);
                }
                let h = input_hash_of(&raw, &params);
                Some((fs.clone(), params, h))
            }
        };
        let mut n = obj(vec![("node_id", J::s(id)), ("type", J::s(t))]);
        if let Some(p) = &o.part_id {
            check_id(p, "part_id")?;
            n.set("part_id", J::s(p));
        }
        if let Some(m) = &o.material_id {
            check_id(m, "material_id")?;
            n.set("material_id", J::s(m));
        }
        let prod = o.producer.clone().unwrap_or_else(|| self.producer.clone());
        n.set("versions", J::Arr(vec![version_record(1, recs, pf, note, prod, &ep, &self.created, inputs)]));
        n.set("active", J::Int(1));
        let mut es = vec![];
        for (to, kind, role) in &o.edges {
            es.push(edge(to, kind, role.as_deref())?);
        }
        n.set("edges", J::Arr(es));
        if let Some(m) = o.meta {
            n.set("meta", m);
        }
        self.nodes.push(n);
        if let Some(sp) = self.bundle.info.get("schemas_by_type").and_then(|m| m.get(t)).and_then(J::as_str) {
            if !self.schemas.iter().any(|(k, _)| k == t) {
                self.schemas.push((t.into(), sp.into()));
            }
        }
        if let Some(lp) = self.bundle.info.get("layouts_by_type").and_then(|m| m.get(t)).and_then(J::as_str) {
            if !self.layouts.iter().any(|(k, _)| k == t) {
                self.layouts.push((t.into(), lp.into()));
            }
        }
        Ok(())
    }

    /// Carry one more file in spec/, or replace a vendored one (a profile's
    /// own narrative and schema, a format definition). Joins the core.spec
    /// node, files kept sorted by UTF-8 path; twin of Python add_spec_file.
    pub fn add_spec_file(&mut self, path: &str, data: Vec<u8>) -> R<bool> {
        check_path(path)?;
        if !path.starts_with("spec/") {
            return Err(format!("a specification file lives under spec/: {path}"));
        }
        if let Some(ow) = self.owner.get(path) {
            if ow != "spec" {
                return Err(format!("{path} is already listed by node {ow}"));
            }
        }
        let replaced = self.blobs.contains_key(path);
        let rec = obj(vec![("path", J::s(path)), ("sha256", J::Str(sha_hex(&data))), ("size", J::Int(data.len() as i64))]);
        self.blobs.insert(path.into(), Blob::Data(data));
        self.owner.insert(path.into(), "spec".into());
        let node = self.nodes.iter_mut().find(|n| n.get("node_id").and_then(J::as_str) == Some("spec")).ok_or("no spec node")?;
        let v0 = &mut node.get_mut("versions").and_then(J::as_arr_mut).unwrap()[0];
        let files = v0.get_mut("files").and_then(J::as_arr_mut).unwrap();
        files.retain(|f| f.get("path").and_then(J::as_str) != Some(path));
        files.push(rec);
        files.sort_by(|a, b| a.get("path").and_then(J::as_str).unwrap().as_bytes().cmp(b.get("path").and_then(J::as_str).unwrap().as_bytes()));
        Ok(replaced)
    }

    /// Add a file to the core.readme node beside README.txt; the version then
    /// declares payload_file "README.txt". Twin of Python add_readme_file.
    pub fn add_readme_file(&mut self, path: &str, data: Vec<u8>) -> R<()> {
        check_path(path)?;
        if let Some(ow) = self.owner.get(path) {
            return Err(format!("{path} is already listed by node {ow}"));
        }
        let rec = obj(vec![("path", J::s(path)), ("sha256", J::Str(sha_hex(&data))), ("size", J::Int(data.len() as i64))]);
        self.blobs.insert(path.into(), Blob::Data(data));
        self.owner.insert(path.into(), "readme".into());
        let node = self.nodes.iter_mut().find(|n| n.get("node_id").and_then(J::as_str) == Some("readme")).ok_or("no readme node")?;
        let v0 = &mut node.get_mut("versions").and_then(J::as_arr_mut).unwrap()[0];
        let mut files = v0.get("files").and_then(J::as_arr).unwrap().clone();
        files.push(rec);
        let mut nv: Vec<(String, J)> = vec![];
        if let J::Obj(pairs) = v0 {
            for (k, v) in pairs.iter() {
                if k == "payload_file" {
                    continue;
                }
                if k == "files" {
                    nv.push((k.clone(), J::Arr(files.clone())));
                    nv.push(("payload_file".into(), J::s("README.txt")));
                } else {
                    nv.push((k.clone(), v.clone()));
                }
            }
        }
        *v0 = J::Obj(nv);
        Ok(())
    }

    pub fn set_primary(&mut self, k: &str, id: &str) {
        if let Some(slot) = self.primary.iter_mut().find(|(kk, _)| kk == k) {
            slot.1 = id.into();
        } else {
            self.primary.push((k.into(), id.into()));
        }
    }
    pub fn preview(&mut self, p: &str) {
        if !self.preview_exact.iter().any(|x| x == p) {
            self.preview_exact.push(p.into());
        }
    }

    fn entry_order(&self) -> (Vec<String>, Vec<String>) {
        let head: Vec<String> = self.bundle.info.get("head_order").and_then(J::as_arr).unwrap().iter().map(|s| s.as_str().unwrap().to_string()).collect();
        let dirs: BTreeSet<Vec<u8>> = self.blobs.keys().filter(|p| p.contains('/')).map(|p| format!("{}/", p.split('/').next().unwrap()).into_bytes()).collect();
        let dirs: Vec<String> = dirs.into_iter().map(|b| String::from_utf8(b).unwrap()).collect();
        let pp: Vec<String> = self.ptab.get("preview_prefixes").and_then(J::as_arr).unwrap().iter().map(|s| s.as_str().unwrap().to_string()).collect();
        let mut order = head.clone();
        let mut tier = head.clone();
        for p in &pp {
            if dirs.contains(p) && !order.contains(p) {
                order.push(p.clone());
            }
            if dirs.contains(p) {
                tier.push(p.clone());
            }
        }
        for p in &self.preview_exact {
            if !order.contains(p) {
                order.push(p.clone());
            }
            tier.push(p.clone());
        }
        for d in &dirs {
            if !order.contains(d) {
                order.push(d.clone());
            }
        }
        (order, tier)
    }

    pub fn manifest(&self, form: &str) -> R<J> {
        let (order, tier) = self.entry_order();
        let mut m = J::obj();
        m.set("werk", obj(vec![("major", J::Int(1)), ("minor", J::Int(0))]));
        m.set("profile", J::s(&self.profile));
        m.set("manifest_schema", self.ptab.get("manifest_schema").cloned().unwrap());
        m.set("spec_sha256", J::Str(spec_sha256_of(&self.nodes)));
        let mut ent = obj(vec![("uuid", J::s(&self.uuid)), ("name", J::s(&self.name))]);
        if let Some(s) = &self.summary {
            ent.set("summary", J::s(s));
        }
        ent.set("created", J::s(&self.created));
        m.set("entity", ent);
        m.set("conventions", self.ptab.get("conventions").cloned().unwrap());
        if let Some(cm) = &self.conventions_map {
            if !self.blobs.contains_key(cm) || self.owner.get(cm).map(String::as_str) != Some("spec") {
                return Err(format!("conventions_map names {cm}, which is not a spec/ file of this package (carry it with --spec-file)"));
            }
            m.set("conventions_map", J::s(cm));
        } else if let Some(cm) = self.ptab.get("conventions_map").and_then(J::as_str) {
            if self.blobs.contains_key(cm) {
                m.set("conventions_map", J::s(cm));
            }
        }
        m.set("container", obj(vec![
            ("form", J::s(form)),
            ("zip_compression", J::s("store")),
            ("entry_order", J::Arr(order.iter().map(|s| J::s(s)).collect())),
            ("preview_tier", J::Arr(tier.iter().map(|s| J::s(s)).collect())),
        ]));
        if !self.primary.is_empty() {
            m.set("primary", J::Obj(self.primary.iter().map(|(k, v)| (k.clone(), J::s(v))).collect()));
        }
        let mut lic = J::obj();
        if let Some(s) = &self.spdx_id {
            lic.set("spdx_id", J::s(s));
        }
        lic.set("file", J::s("LICENSE"));
        lic.set("sha256", J::Str(self.sha_of("LICENSE")?));
        m.set("license", lic);
        m.set("schemas", J::Obj(self.schemas.iter().map(|(k, v)| (k.clone(), J::s(v))).collect()));
        m.set("layouts", J::Obj(self.layouts.iter().map(|(k, v)| (k.clone(), J::s(v))).collect()));
        if self.ptab.get("has_parts") == Some(&J::Bool(true)) {
            m.set("parts", J::Arr(self.parts.clone()));
            m.set("materials", J::Arr(self.materials.clone()));
        }
        m.set("nodes", J::Arr(self.nodes.clone()));
        m.set("generator", self.generator.clone());
        let ids: Vec<&str> = self.nodes.iter().filter_map(|n| n.get("node_id").and_then(J::as_str)).collect();
        for (_, v) in &self.primary {
            if !ids.contains(&v.as_str()) {
                return Err(format!("primary names {v}, which is not a node"));
            }
        }
        Ok(m)
    }

    pub fn write(&self, out: &str, form: &str) -> R<String> {
        let mb = json::pretty(&self.manifest(form)?);
        let msha = sha_hex(&mb);
        let mut doc: Option<J> = None;
        for s in &self.signers {
            doc = Some(chain_append(doc, &msha, s, &self.created)?);
        }
        let sb = doc.map(|d| json::pretty(&d));
        let order: Vec<String> = self.entry_order().0;
        write_container(out, form, &self.blobs, &mb, sb.as_deref(), &order, &self.created)?;
        Ok(msha)
    }
}

// ------------------------------------------------------------------ profile helpers

pub struct PngInfo {
    pub w: i64,
    pub h: i64,
    pub ch: i64,
    pub depth: i64,
    pub alpha: bool,
}
pub fn png_info(d: &[u8]) -> R<PngInfo> {
    if d.len() < 26 || &d[..8] != b"\x89PNG\r\n\x1a\n" || &d[12..16] != b"IHDR" {
        return Err("not a PNG (MINI-SPECS section 8)".into());
    }
    let be = |o: usize| u32::from_be_bytes([d[o], d[o + 1], d[o + 2], d[o + 3]]) as i64;
    let (mut depth, ct) = (d[24] as i64, d[25]);
    let ch = match ct { 0 => 1, 2 => 3, 3 => 3, 4 => 2, 6 => 4, _ => return Err(format!("PNG colour type {ct} is not defined")) };
    if ct == 3 {
        depth = 8;
    }
    Ok(PngInfo { w: be(16), h: be(20), ch, depth, alpha: ct == 4 || ct == 6 })
}
pub fn glb_check(d: &[u8]) -> R<()> {
    if d.len() < 20 || &d[..4] != b"glTF" {
        return Err("not a GLB (magic glTF)".into());
    }
    let u = |o: usize| u32::from_le_bytes([d[o], d[o + 1], d[o + 2], d[o + 3]]) as usize;
    if u(4) != 2 || u(8) != d.len() || u(16) != 0x4E4F_534A {
        return Err("GLB version / length / first chunk does not match the file".into());
    }
    Ok(())
}

pub struct Attachment {
    pub node_id: String,
    pub ntype: String,
    pub files: Vec<NewFile>,
}

fn attach(w: &mut Writer, atts: Vec<Attachment>) -> R<()> {
    for a in atts {
        w.add_node(&a.node_id, &a.ntype, a.files, "A file attached by the writing application.", NodeOpts::default())?;
    }
    Ok(())
}

pub struct ImageOpts {
    pub thumb: Option<Vec<u8>>,
    pub recipe: Option<J>,
    pub disclosure: Option<J>,
    pub model: Option<String>,
    pub epistemic: Option<String>,
    pub inputs: Option<Vec<String>>,
}

pub fn image_package(w: &mut Writer, png: Vec<u8>, o: ImageOpts, atts: Vec<Attachment>) -> R<()> {
    let i = png_info(&png)?;
    let cs = "srgb";
    let src = "image/source.png";
    let meta = obj(vec![("width", J::Int(i.w)), ("height", J::Int(i.h)), ("channels", J::Int(i.ch)), ("bit_depth", J::Int(i.depth)),
                        ("color_space", J::s(cs)), ("encoding", J::s("png")), ("has_alpha", J::Bool(i.alpha))]);
    let ep = o.epistemic.clone().unwrap_or_else(|| "authored".into());
    if ep != "authored" && o.inputs.as_ref().map_or(true, |v| v.is_empty()) {
        return Err("an inferred image names its inputs: pass input files".into());
    }
    if let Some(r) = o.recipe {
        w.add_node("recipe", "core.recipe", vec![nf("recipe/recipe.json", json::pretty(&r), Some("application/json"), Some("record"))?],
                   "The reproduction record of the generation (SPEC section 3.11).", NodeOpts::default())?;
        w.preview("recipe/recipe.json");
    }
    let producer = o.model.as_ref().map(|m| {
        let mut p = w.producer.clone();
        p.set("model", J::s(m));
        p
    });
    w.add_node("image-source", "core.image.source", vec![nf(src, png, Some("image/png"), None)?],
               "The image as the process that made it delivered it.",
               NodeOpts { epistemic: Some(ep), producer, meta: Some(meta), input_files: o.inputs.clone(), ..Default::default() })?;
    w.set_primary("image", "image-source");
    if let Some(t) = o.thumb {
        let ti = png_info(&t)?;
        let tmeta = obj(vec![("width", J::Int(ti.w)), ("height", J::Int(ti.h)), ("channels", J::Int(ti.ch)), ("bit_depth", J::Int(ti.depth)),
                             ("color_space", J::s(cs)), ("encoding", J::s("png")), ("has_alpha", J::Bool(ti.alpha)),
                             ("derived_role", J::s("thumbnail")), ("resample", J::s("box"))]);
        let params = obj(vec![("resample", J::s("box")), ("width", J::Int(ti.w)), ("height", J::Int(ti.h))]);
        w.add_node("image-thumb", "core.image.derived", vec![nf("image/thumb.png", t, Some("image/png"), None)?],
                   "The listing thumbnail, a downscale of the source image.",
                   NodeOpts { epistemic: Some("measured".into()), meta: Some(tmeta), input_files: Some(vec![src.into()]), input_params: Some(params),
                              edges: vec![("image-source".into(), "requires".into(), Some("derived-from".into()))], ..Default::default() })?;
        w.set_primary("thumbnail", "image-thumb");
        w.preview("image/thumb.png");
    }
    if let Some(d) = o.disclosure {
        w.add_node("disclosure", "core.disclosure", vec![nf("disclosure/disclosure.json", json::pretty(&d), Some("application/json"), None)?],
                   "The machine-readable synthetic-content facts (SPEC section 3.12).", NodeOpts::default())?;
    }
    attach(w, atts)
}

pub struct Tex {
    pub id: String,
    pub png: Vec<u8>,
    pub usage: String,
}
pub struct Mat {
    pub id: String,
    pub base_color: Option<String>,
}

pub fn mesh_package(w: &mut Writer, glb: Vec<u8>, texs: Vec<Tex>, mats: Vec<Mat>, preview: Option<Vec<u8>>, atts: Vec<Attachment>) -> R<()> {
    glb_check(&glb)?;
    w.parts.push(obj(vec![("part_id", J::s("body")), ("name", J::s("Body")), ("parent", J::Null),
        ("transform", obj(vec![("translation", J::Arr(vec![J::Int(0), J::Int(0), J::Int(0)])),
                               ("rotation", J::Arr(vec![J::Int(1), J::Int(0), J::Int(0), J::Int(0)])),
                               ("scale", J::Arr(vec![J::Int(1), J::Int(1), J::Int(1)]))]))]));
    w.add_node("geom-game", "core.geom.game", vec![nf("geometry/game.glb", glb, Some("model/gltf-binary"), None)?],
               "The mesh to render, as the authoring application exported it.", NodeOpts { part_id: Some("body".into()), ..Default::default() })?;
    w.set_primary("mesh", "geom-game");
    w.set_primary("geometry", "geom-game");
    let mut tex_ids: BTreeMap<String, (String, String)> = BTreeMap::new();
    for t in texs {
        check_id(&t.id, "texture id")?;
        let i = png_info(&t.png)?;
        let cs = if t.usage == "base-color" || t.usage == "emissive" { "srgb" } else { "linear" };
        let mut meta = obj(vec![("color_space", J::s(cs)), ("usage", J::s(&t.usage)), ("width", J::Int(i.w)), ("height", J::Int(i.h)),
                                ("channels", J::Int(i.ch)), ("bit_depth", J::Int(i.depth))]);
        if t.usage == "normal" {
            meta.set("normal_convention", J::s("opengl-y-up"));
        }
        let path = format!("textures/{}.png", t.id);
        w.add_node(&format!("tex-{}", t.id), "core.tex", vec![nf(&path, t.png, Some("image/png"), None)?],
                   "A texture of the mesh, as exported.", NodeOpts { meta: Some(meta), part_id: Some("body".into()), ..Default::default() })?;
        tex_ids.insert(t.id.clone(), (format!("tex-{}", t.id), path));
    }
    for m in mats {
        check_id(&m.id, "material id")?;
        w.materials.push(obj(vec![("material_id", J::s(&m.id)), ("name", J::s(&m.id)), ("part_id", J::s("body"))]));
        let mut payload = obj(vec![("material_id", J::s(&m.id)), ("name", J::s(&m.id)), ("model", J::s("metallic-roughness")),
            ("base_color_factor", J::Arr(vec![J::Int(1), J::Int(1), J::Int(1), J::Int(1)])), ("metallic_factor", J::Int(0)),
            ("roughness_factor", J::Int(1)), ("alpha_mode", J::s("opaque")), ("double_sided", J::Bool(false))]);
        let mut edges = vec![];
        if let Some(bc) = &m.base_color {
            let (nid, p) = tex_ids.get(bc).cloned().ok_or(format!("material {} names texture {bc}, which was not given", m.id))?;
            payload.set("textures", obj(vec![("base_color", obj(vec![("node", J::s(&nid)), ("path", J::s(&p)), ("uv_set", J::Int(0))]))]));
            edges.push((nid, "enhances".to_string(), Some("base-color".to_string())));
        }
        payload.set("epistemic", J::s("authored"));
        w.add_node(&format!("mat-{}", m.id), "core.material", vec![nf(&format!("materials/{}.json", m.id), json::pretty(&payload), Some("application/json"), None)?],
                   "Material parameters of the mesh, as exported.",
                   NodeOpts { material_id: Some(m.id.clone()), part_id: Some("body".into()), edges, ..Default::default() })?;
    }
    if let Some(pv) = preview {
        let i = png_info(&pv)?;
        let meta = obj(vec![("color_space", J::s("srgb")), ("usage", J::s("other")), ("width", J::Int(i.w)), ("height", J::Int(i.h)),
                            ("channels", J::Int(i.ch)), ("bit_depth", J::Int(i.depth))]);
        w.add_node("preview", "core.tex", vec![nf("preview/preview.png", pv, Some("image/png"), None)?],
                   "A still of the entity for listings, rendered by the authoring application.", NodeOpts { meta: Some(meta), ..Default::default() })?;
        w.set_primary("image", "preview");
        w.preview("preview/preview.png");
    }
    attach(w, atts)
}

// ------------------------------------------------------------------ reading through werk-core

pub struct Opened {
    pub pkg: Package,
    pub manifest: J,
    pub manifest_bytes: Vec<u8>,
}

pub fn open(path: &str) -> Result<Opened, werk::Error> {
    let pkg = Package::open(path)?;
    let mb = pkg.blob(MANIFEST)?.as_ref().clone();
    let manifest = json::parse_bytes(&mb).map_err(werk::Error::BadManifest)?;
    Ok(Opened { pkg, manifest, manifest_bytes: mb })
}

fn errors(o: &Opened) -> Vec<String> {
    o.pkg.report.entries.iter().filter(|e| e.severity == werk::Severity::Error).map(|e| e.code.as_str().to_string()).collect()
}

fn all_blobs(o: &Opened) -> R<BTreeMap<String, Blob>> {
    let mut out = BTreeMap::new();
    for n in o.manifest.get("nodes").and_then(J::as_arr).unwrap() {
        for v in n.get("versions").and_then(J::as_arr).unwrap() {
            for f in v.get("files").and_then(J::as_arr).unwrap() {
                let p = f.get("path").and_then(J::as_str).unwrap().to_string();
                if !out.contains_key(&p) {
                    let b = o.pkg.blob(&p).map_err(|e| e.to_string())?;
                    out.insert(p, Blob::Data(b.as_ref().clone()));
                }
            }
        }
    }
    Ok(out)
}

pub fn verdict(o: &Opened) -> J {
    let (mut alive, mut skipped, mut dead) = (0, 0, 0);
    let mut dead_nodes = vec![];
    for n in &o.pkg.nodes {
        match n.status {
            werk::NodeStatus::Alive => alive += 1,
            werk::NodeStatus::Skipped(_) => skipped += 1,
            werk::NodeStatus::Dead(_) => {
                dead += 1;
                dead_nodes.push(n.view.node_id.clone());
            }
        }
    }
    dead_nodes.sort();
    let mut codes: Vec<String> = errors(o);
    codes.sort();
    codes.dedup();
    let nodes = o.manifest.get("nodes").and_then(J::as_arr).cloned().unwrap_or_default();
    let spec_ok = o.manifest.get("spec_sha256").and_then(J::as_str) == Some(spec_sha256_of(&nodes).as_str());
    let form = if Path::new(&o.pkg.origin).is_dir() { "directory" } else { "zip" };
    obj(vec![
        ("exit", J::Int(if codes.is_empty() { 0 } else { 1 })),
        ("profile", J::s(o.pkg.manifest.profile())),
        ("form", J::s(form)),
        ("signature", J::s(o.pkg.signature_state.word())),
        ("nodes", J::Int(o.pkg.nodes.len() as i64)),
        ("alive", J::Int(alive)),
        ("skipped", J::Int(skipped)),
        ("dead", J::Int(dead)),
        ("dead_nodes", J::Arr(dead_nodes.iter().map(|s| J::s(s)).collect())),
        ("error_codes", J::Arr(codes.iter().map(|s| J::s(s)).collect())),
        ("envelopes", J::Int(o.pkg.envelopes_validated as i64)),
        ("manifest_sha256", J::Str(sha_hex(&o.manifest_bytes))),
        ("spec_sha256_ok", J::Bool(spec_ok)),
        ("schema_validated", J::Bool(true)),
    ])
}

const PAYLOAD_ROLE: &[(&str, &str)] = &[("core.audio.effect", "best"), ("core.audio.ambience", "best"), ("core.imposter", "atlas"), ("core.recipe", "record")];

/// SPEC section 2.1's ordered rules; never files[0] by default.
pub fn payload_path(ntype: &str, ver: &J) -> R<String> {
    let files = ver.get("files").and_then(J::as_arr).cloned().unwrap_or_default();
    let paths: Vec<String> = files.iter().filter_map(|f| f.get("path").and_then(J::as_str).map(String::from)).collect();
    if let Some(pf) = ver.get("payload_file").and_then(J::as_str) {
        if paths.iter().filter(|p| *p == pf).count() == 1 {
            return Ok(pf.into());
        }
        return Err(format!("payload-file-ambiguous: payload_file {pf} is not exactly one of files[]"));
    }
    if files.len() == 1 {
        return Ok(paths[0].clone());
    }
    let with_role = |r: &str| -> Vec<String> { files.iter().filter(|f| f.get("role").and_then(J::as_str) == Some(r)).filter_map(|f| f.get("path").and_then(J::as_str).map(String::from)).collect() };
    let r = with_role("payload");
    if r.len() == 1 {
        return Ok(r[0].clone());
    }
    if let Some((_, role)) = PAYLOAD_ROLE.iter().find(|(t, _)| *t == ntype) {
        let r = with_role(role);
        if r.len() == 1 {
            return Ok(r[0].clone());
        }
    }
    if ntype == "core.anim.clip" {
        let r: Vec<&String> = paths.iter().filter(|p| p.ends_with(".wkac")).collect();
        if r.len() == 1 {
            return Ok(r[0].clone());
        }
    }
    Err(format!("payload-file-ambiguous: {} candidate files; none is declared the payload", paths.len()))
}

fn node_raw<'a>(o: &'a Opened, id: &str) -> R<&'a J> {
    o.manifest.get("nodes").and_then(J::as_arr).unwrap().iter().find(|n| n.get("node_id").and_then(J::as_str) == Some(id)).ok_or(format!("no node {id}"))
}

fn version_of(n: &J, v: i64) -> Option<&J> {
    n.get("versions").and_then(J::as_arr).and_then(|vs| vs.iter().find(|x| x.get("v").and_then(J::as_i64) == Some(v)))
}

pub fn read_payload(o: &Opened, id: &str, version: Option<i64>) -> R<Vec<u8>> {
    let state = o.pkg.node(id).ok_or(format!("no node {id}"))?;
    let v = match version {
        Some(v) => v,
        None => {
            if state.status.is_dead() {
                return Err(format!("node {id} is dead: {}", state.status.reason()));
            }
            state.resolved.ok_or(format!("node {id} has no usable version"))?
        }
    };
    let raw = node_raw(o, id)?;
    let ver = version_of(raw, v).ok_or(format!("node {id} has no v{v}"))?;
    let p = payload_path(raw.get("type").and_then(J::as_str).unwrap_or(""), ver)?;
    o.pkg.blob(&p).map(|b| b.as_ref().clone()).map_err(|e| e.to_string())
}

pub fn read_declared(o: &Opened, path: &str) -> R<Vec<u8>> {
    let declared = path == MANIFEST || path == SIGNATURE || o.manifest.get("nodes").and_then(J::as_arr).unwrap().iter().any(|n| {
        n.get("versions").and_then(J::as_arr).unwrap().iter().any(|v| v.get("files").and_then(J::as_arr).unwrap().iter().any(|f| f.get("path").and_then(J::as_str) == Some(path)))
    });
    if !declared {
        return Err(format!("{path} is not declared by any node; refusing to read it"));
    }
    o.pkg.blob(path).map(|b| b.as_ref().clone()).map_err(|e| e.to_string())
}

pub fn extract(o: &Opened, out: &str, ids: Option<&[String]>, all_versions: bool) -> R<usize> {
    let mut seen: BTreeSet<String> = BTreeSet::new();
    for n in o.manifest.get("nodes").and_then(J::as_arr).unwrap() {
        let id = n.get("node_id").and_then(J::as_str).unwrap_or("");
        if let Some(ids) = ids {
            if !ids.iter().any(|x| x == id) {
                continue;
            }
        }
        let st = match o.pkg.node(id) {
            Some(s) => s,
            None => continue,
        };
        if st.status.is_dead() && !all_versions {
            continue;
        }
        let vers: Vec<&J> = if all_versions {
            n.get("versions").and_then(J::as_arr).unwrap().iter().collect()
        } else {
            st.resolved.and_then(|v| version_of(n, v)).into_iter().collect()
        };
        for v in vers {
            for f in v.get("files").and_then(J::as_arr).unwrap() {
                let p = f.get("path").and_then(J::as_str).unwrap().to_string();
                if seen.contains(&p) {
                    continue;
                }
                if p.starts_with('/') || p.contains('\\') || p.split('/').any(|s| s == "..") {
                    return Err(format!("refusing an unsafe package path: {p}"));
                }
                let full = p.split('/').fold(Path::new(out).to_path_buf(), |a, s| a.join(s));
                if let Some(d) = full.parent() {
                    std::fs::create_dir_all(d).map_err(|e| e.to_string())?;
                }
                std::fs::write(&full, o.pkg.blob(&p).map_err(|e| e.to_string())?.as_ref()).map_err(|e| e.to_string())?;
                seen.insert(p);
            }
        }
    }
    Ok(seen.len())
}

// ------------------------------------------------------------------ rewriting

fn at_marker(path: &str, n: i64) -> String {
    let (d, name) = match path.rfind('/') { Some(i) => (&path[..i], &path[i + 1..]), None => ("", path) };
    let name = match name.rfind('.') { Some(i) if i > 0 => format!("{}@{n}{}", &name[..i], &name[i..]), _ => format!("{name}@{n}") };
    if d.is_empty() { name } else { format!("{d}/{name}") }
}

fn strip_marker(path: &str) -> String {
    let (d, name) = match path.rfind('/') { Some(i) => (&path[..i], &path[i + 1..]), None => ("", path) };
    // remove the first "@<digits>" that sits before the last extension or at the end
    let ext_at = name.rfind('.').filter(|i| *i > 0).unwrap_or(name.len());
    let stem = &name[..ext_at];
    let new_stem = match stem.rfind('@') {
        Some(i) if i + 1 < stem.len() && stem[i + 1..].bytes().all(|c| c.is_ascii_digit()) => stem[..i].to_string(),
        _ => stem.to_string(),
    };
    let name = format!("{new_stem}{}", &name[ext_at..]);
    if d.is_empty() { name } else { format!("{d}/{name}") }
}

pub struct AppendOpts {
    pub epistemic: Option<String>,
    pub created: Option<String>,
    pub node_type: Option<String>,
    pub signer: Option<SignerOpt>,
    pub drop_signature: bool,
    pub form: Option<String>,
}

fn paths_of(v: &J) -> Vec<String> {
    v.get("files").and_then(J::as_arr).unwrap().iter().filter_map(|f| f.get("path").and_then(J::as_str).map(String::from)).collect()
}

pub fn append_version(src: &str, out: &str, node_id: &str, files: Vec<NewFile>, note: &str, o: AppendOpts) -> R<()> {
    let op = open(src).map_err(|e| e.to_string())?;
    let errs = errors(&op);
    if !errs.is_empty() {
        return Err(format!("refusing to append to a package that does not verify clean: {}", errs.join("; ")));
    }
    let created = o.created.clone().unwrap_or_else(utc_now);
    dos_datetime(&created)?;
    check_note(note)?;
    let mut m = op.manifest.clone();
    let mut blobs = all_blobs(&op)?;
    let mut owners: BTreeMap<String, String> = BTreeMap::new();
    for n in m.get("nodes").and_then(J::as_arr).unwrap() {
        for v in n.get("versions").and_then(J::as_arr).unwrap() {
            for p in paths_of(v) {
                owners.insert(p, n.get("node_id").and_then(J::as_str).unwrap().to_string());
            }
        }
    }
    let prod = obj(vec![("tool", J::s("werk")), ("version", J::s(LIB_VERSION))]);
    let ep = o.epistemic.clone().unwrap_or_else(|| "authored".into());
    let new_recs: Vec<(J, Vec<u8>)> = files.into_iter().map(|f| (file_rec(&f), f.data)).collect();
    let path_of = |r: &J| r.get("path").and_then(J::as_str).unwrap().to_string();
    let nodes = m.get_mut("nodes").and_then(J::as_arr_mut).unwrap();
    let idx = nodes.iter().position(|n| n.get("node_id").and_then(J::as_str) == Some(node_id));
    match idx {
        None => {
            let t = o.node_type.clone().ok_or(format!("no node {node_id}; pass --type to add it"))?;
            check_id(node_id, "node_id")?;
            if !is_type(&t) {
                return Err(format!("bad node type {t}"));
            }
            let mut recs = vec![];
            for (r, d) in new_recs {
                let p = path_of(&r);
                if let Some(ow) = owners.get(&p) {
                    return Err(format!("{p} already belongs to node {ow}"));
                }
                blobs.insert(p, Blob::Data(d));
                recs.push(r);
            }
            let mut pf = None;
            if recs.len() > 1 {
                let roled: Vec<&J> = recs.iter().filter(|r| r.get("role").and_then(J::as_str) == Some("payload")).collect();
                if roled.len() == 1 {
                    pf = Some(path_of(roled[0]));
                }
            }
            nodes.push(obj(vec![
                ("node_id", J::s(node_id)),
                ("type", J::s(&t)),
                ("versions", J::Arr(vec![version_record(1, recs, pf, note, prod, &ep, &created, None)])),
                ("active", J::Int(1)),
                ("edges", J::Arr(vec![])),
            ]));
            let b = Bundle::load()?;
            if let Some(sp) = b.info.get("schemas_by_type").and_then(|x| x.get(&t)).and_then(J::as_str) {
                if let Some(s @ J::Obj(_)) = m.get_mut("schemas") {
                    if !s.has(&t) {
                        s.set(&t, J::s(sp));
                    }
                }
            }
            if let Some(lp) = b.info.get("layouts_by_type").and_then(|x| x.get(&t)).and_then(J::as_str) {
                if let Some(s @ J::Obj(_)) = m.get_mut("layouts") {
                    if !s.has(&t) {
                        s.set(&t, J::s(lp));
                    }
                }
            }
        }
        Some(i) => {
            let raw = &mut nodes[i];
            let active = raw.get("active").and_then(J::as_i64).unwrap();
            let newv = raw.get("versions").and_then(J::as_arr).unwrap().iter().filter_map(|v| v.get("v").and_then(J::as_i64)).max().unwrap() + 1;
            let cur = raw.get("versions").and_then(J::as_arr).unwrap().iter().find(|v| v.get("v").and_then(J::as_i64) == Some(active)).cloned().unwrap();
            let given: Vec<(String, J, Vec<u8>)> = new_recs.into_iter().map(|(r, d)| (path_of(&r), r, d)).collect();
            let mut seen: BTreeSet<String> = BTreeSet::new();
            let mut out_files: Vec<J> = vec![];
            for f in cur.get("files").and_then(J::as_arr).unwrap() {
                let fp = f.get("path").and_then(J::as_str).unwrap().to_string();
                let logical = strip_marker(&fp);
                if let Some((_, r, data)) = given.iter().find(|(p, _, _)| *p == logical) {
                    seen.insert(logical.clone());
                    if r.get("sha256") == f.get("sha256") && r.get("size") == f.get("size") && fp == logical {
                        out_files.push(f.clone());
                        continue;
                    }
                    if fp == logical {
                        let fsha = f.get("sha256").cloned();
                        let intro = raw.get("versions").and_then(J::as_arr).unwrap().iter()
                            .filter(|v| v.get("files").and_then(J::as_arr).unwrap().iter().any(|x| x.get("path").and_then(J::as_str) == Some(&logical) && x.get("sha256").cloned() == fsha))
                            .filter_map(|v| v.get("v").and_then(J::as_i64)).min().unwrap();
                        let moved = at_marker(&logical, intro);
                        if owners.contains_key(&moved) {
                            return Err(format!("{moved} already exists; cannot supersede {logical}"));
                        }
                        for v in raw.get_mut("versions").and_then(J::as_arr_mut).unwrap() {
                            for x in v.get_mut("files").and_then(J::as_arr_mut).unwrap() {
                                if x.get("path").and_then(J::as_str) == Some(&logical) {
                                    x.set("path", J::s(&moved));
                                }
                            }
                            if v.get("payload_file").and_then(J::as_str) == Some(&logical) {
                                v.set("payload_file", J::s(&moved));
                            }
                        }
                        let b = blobs.remove(&logical).unwrap();
                        blobs.insert(moved.clone(), b);
                        owners.insert(moved, node_id.into());
                    }
                    blobs.insert(logical.clone(), Blob::Data(data.clone()));
                    owners.insert(logical, node_id.into());
                    out_files.push(r.clone());
                } else {
                    out_files.push(f.clone());
                }
            }
            for (p, r, data) in &given {
                if seen.contains(p) {
                    continue;
                }
                if let Some(ow) = owners.get(p) {
                    if ow != node_id {
                        return Err(format!("{p} belongs to node {ow}"));
                    }
                }
                if blobs.contains_key(p) {
                    return Err(format!("{p} is a file of an earlier version; give it a new path"));
                }
                blobs.insert(p.clone(), Blob::Data(data.clone()));
                owners.insert(p.clone(), node_id.into());
                out_files.push(r.clone());
            }
            let mut pf = None;
            if out_files.len() > 1 {
                let cpf = cur.get("payload_file").and_then(J::as_str).map(strip_marker);
                if let Some(c) = cpf.filter(|c| out_files.iter().any(|f| f.get("path").and_then(J::as_str) == Some(c))) {
                    pf = Some(c);
                } else {
                    let roled: Vec<&J> = out_files.iter().filter(|r| r.get("role").and_then(J::as_str) == Some("payload")).collect();
                    if roled.len() == 1 {
                        pf = Some(path_of(roled[0]));
                    }
                }
            }
            let rec = version_record(newv, out_files, pf, note, prod, &ep, &created, None);
            raw.get_mut("versions").and_then(J::as_arr_mut).unwrap().push(rec);
            raw.set("active", J::Int(newv));
        }
    }
    let form = form_of(out, o.form.as_deref());
    finish_rewrite(&op, m, blobs, out, &form, &created, o.signer, o.drop_signature)
}

fn finish_rewrite(op: &Opened, mut m: J, blobs: BTreeMap<String, Blob>, out: &str, form: &str, created: &str, signer: Option<SignerOpt>, drop_sig: bool) -> R<()> {
    let nodes = m.get("nodes").and_then(J::as_arr).cloned().unwrap();
    m.set("spec_sha256", J::Str(spec_sha256_of(&nodes)));
    if let Some(c @ J::Obj(_)) = m.get_mut("container") {
        c.set("form", J::s(form));
        if c.has("total_size_bytes") {
            let mut sizes: BTreeMap<String, i64> = BTreeMap::new();
            for n in &nodes {
                for v in n.get("versions").and_then(J::as_arr).unwrap() {
                    for f in v.get("files").and_then(J::as_arr).unwrap() {
                        sizes.insert(f.get("path").and_then(J::as_str).unwrap().into(), f.get("size").and_then(J::as_i64).unwrap_or(0));
                    }
                }
            }
            c.set("total_size_bytes", J::Int(sizes.values().sum()));
        }
    }
    let mb = json::pretty(&m);
    let had_sig = op.pkg.signature_state != werk::SignatureState::Absent;
    let sb = match signer {
        Some(s) => {
            let existing = if had_sig { Some(json::parse_bytes(&op.pkg.blob(SIGNATURE).map_err(|e| e.to_string())?)?) } else { None };
            Some(json::pretty(&chain_append(existing, &sha_hex(&mb), &s, created)?))
        }
        None if had_sig && !drop_sig => {
            return Err("the package is signed; a changed manifest needs a new chain entry (pass a signing key) or --drop-signature. Leaving the old chain in place would make the package present-and-invalid".into());
        }
        None => None,
    };
    let order: Vec<String> = m.get("container").and_then(|c| c.get("entry_order")).and_then(J::as_arr)
        .map(|a| a.iter().filter_map(|s| s.as_str().map(String::from)).collect()).unwrap_or_default();
    write_container(out, form, &blobs, &mb, sb.as_deref(), &order, created)
}

pub fn sign_package(src: &str, out: &str, s: SignerOpt, form: Option<&str>) -> R<()> {
    let op = open(src).map_err(|e| e.to_string())?;
    if matches!(op.pkg.signature_state, werk::SignatureState::Invalid(_)) {
        return Err("the existing chain is present-and-invalid; refusing to extend it".into());
    }
    let at = s.signed_at.clone().unwrap_or_else(utc_now);
    let existing = if op.pkg.signature_state != werk::SignatureState::Absent {
        Some(json::parse_bytes(&op.pkg.blob(SIGNATURE).map_err(|e| e.to_string())?)?)
    } else {
        None
    };
    let mut s2 = s.clone();
    s2.signed_at = Some(at.clone());
    let doc = chain_append(existing, &sha_hex(&op.manifest_bytes), &s2, &at)?;
    let blobs = all_blobs(&op)?;
    let order: Vec<String> = op.manifest.get("container").and_then(|c| c.get("entry_order")).and_then(J::as_arr)
        .map(|a| a.iter().filter_map(|s| s.as_str().map(String::from)).collect()).unwrap_or_default();
    write_container(out, &form_of(out, form), &blobs, &op.manifest_bytes, Some(&json::pretty(&doc)), &order, &at)
}

// ------------------------------------------------------------------ CLI

struct Args {
    pos: Vec<String>,
    opt: BTreeMap<String, Vec<String>>,
}
impl Args {
    fn one(&self, k: &str) -> Option<String> {
        self.opt.get(k).and_then(|v| v.last().cloned())
    }
    fn flag(&self, k: &str) -> bool {
        self.opt.contains_key(k)
    }
    fn many(&self, k: &str) -> Vec<String> {
        self.opt.get(k).cloned().unwrap_or_default()
    }
}

fn parse_args(argv: &[String]) -> R<Args> {
    const FLAGS: &[&str] = &["json", "strict", "dir", "all-versions", "drop-signature"];
    let mut a = Args { pos: vec![], opt: BTreeMap::new() };
    let mut i = 0;
    while i < argv.len() {
        if let Some(k) = argv[i].strip_prefix("--") {
            if FLAGS.contains(&k) {
                a.opt.entry(k.into()).or_default().push(String::new());
                i += 1;
                continue;
            }
            let v = argv.get(i + 1).ok_or(format!("option --{k} needs a value"))?;
            a.opt.entry(k.into()).or_default().push(v.clone());
            i += 2;
        } else {
            a.pos.push(argv[i].clone());
            i += 1;
        }
    }
    Ok(a)
}

fn readf(p: &str) -> R<Vec<u8>> {
    std::fs::read(p).map_err(|e| format!("{p}: {e}"))
}

fn signer_of(a: &Args) -> R<Option<SignerOpt>> {
    let key = match a.one("sign-key") {
        None => return Ok(None),
        Some(k) => k,
    };
    let text = if Path::new(&key).is_file() { String::from_utf8_lossy(&readf(&key)?).to_string() } else { key };
    Ok(Some(SignerOpt {
        key: parse_secret(&text)?,
        uri: a.one("signer-uri").unwrap_or_else(|| "urn:werk:anonymous".into()),
        kind: a.one("signer-kind").unwrap_or_else(|| "human".into()),
        name: a.one("signer-name"),
        role: Some(a.one("signer-role").unwrap_or_else(|| "author".into())),
        note: None,
        signed_at: a.one("signed-at"),
    }))
}

fn attachments(a: &Args) -> R<Vec<Attachment>> {
    let mut out = vec![];
    for spec in a.many("attach") {
        let (head, local) = spec.split_once('=').ok_or("--attach is ID:TYPE:PKGPATH=FILE")?;
        let parts: Vec<&str> = head.split(':').collect();
        if parts.len() != 3 || local.is_empty() {
            return Err("--attach is ID:TYPE:PKGPATH=FILE".into());
        }
        out.push(Attachment { node_id: parts[0].into(), ntype: parts[1].into(), files: vec![nf(parts[2], readf(local)?, None, None)?] });
    }
    Ok(out)
}

/// Returns Some(exit status) when the command is one of the release commands.
pub fn run(cmd: &str, argv: &[String]) -> Option<i32> {
    let known = ["pack-image", "pack-mesh", "extract", "cat", "append", "sign"];
    let json_verify = cmd == "verify" && argv.iter().any(|a| a == "--json");
    if !known.contains(&cmd) && !json_verify {
        return None;
    }
    let a = match parse_args(argv) {
        Ok(a) => a,
        Err(e) => {
            eprintln!("werkc: {e}");
            return Some(2);
        }
    };
    Some(match dispatch(cmd, &a) {
        Ok(code) => code,
        Err(Fail::Usage(m)) => {
            eprintln!("werkc: {m}");
            2
        }
        Err(Fail::Refused(code, m)) => {
            if json_verify {
                print!("{}", String::from_utf8(json::pretty(&obj(vec![("exit", J::Int(2)), ("refusal", J::s(&code))]))).unwrap());
            }
            eprintln!("[error] {code}: {m}\ncontainer-scoped refusal: nothing was loaded; exit status 2");
            2
        }
        Err(Fail::Other(m)) => {
            eprintln!("werkc: {m}");
            1
        }
    })
}

enum Fail {
    Usage(String),
    Refused(String, String),
    Other(String),
}
impl From<String> for Fail {
    fn from(s: String) -> Fail {
        Fail::Other(s)
    }
}

fn opened(p: &str) -> Result<Opened, Fail> {
    open(p).map_err(|e| if e.is_container_refusal() || matches!(e, werk::Error::NotFound(_)) {
        Fail::Refused(e.tag().into(), e.to_string())
    } else {
        Fail::Other(e.to_string())
    })
}

fn dispatch(cmd: &str, a: &Args) -> Result<i32, Fail> {
    let need = |n: usize, m: &str| -> Result<(), Fail> { if a.pos.len() < n { Err(Fail::Usage(m.into())) } else { Ok(()) } };
    match cmd {
        "verify" => {
            need(1, "verify needs a package")?;
            let o = opened(&a.pos[0])?;
            let mut v = verdict(&o);
            if a.flag("strict") && o.pkg.report.entries.iter().any(|e| e.severity == werk::Severity::Warn) {
                v.set("exit", J::Int(1));
                v.set("strict_promoted_warnings", J::Bool(true));
            }
            print!("{}", String::from_utf8(json::pretty(&v)).unwrap());
            Ok(v.get("exit").and_then(J::as_i64).unwrap() as i32)
        }
        "extract" => {
            need(2, "extract needs <pkg> <out-dir>")?;
            let o = opened(&a.pos[0])?;
            let ids = a.opt.get("node").cloned();
            let n = extract(&o, &a.pos[1], ids.as_deref(), a.flag("all-versions"))?;
            println!("{n} file(s) written under {}", a.pos[1]);
            Ok(if errors(&o).is_empty() { 0 } else { 1 })
        }
        "cat" => {
            need(1, "cat needs a package")?;
            let o = opened(&a.pos[0])?;
            let bytes = if let Some(id) = a.one("payload") {
                let ver = a.one("version").map(|v| v.parse::<i64>()).transpose().map_err(|_| Fail::Usage("--version is an integer".into()))?;
                read_payload(&o, &id, ver)?
            } else if a.pos.len() >= 2 {
                read_declared(&o, &a.pos[1])?
            } else {
                return Err(Fail::Usage("cat needs a path or --payload NODE".into()));
            };
            use std::io::Write;
            std::io::stdout().write_all(&bytes).map_err(|e| e.to_string())?;
            Ok(0)
        }
        "pack-image" | "pack-mesh" => {
            need(1, "needs <out>")?;
            let name = a.one("name").ok_or(Fail::Usage(format!("{cmd} needs --name")))?;
            let out = &a.pos[0];
            let form = if a.flag("dir") { "directory".to_string() } else { form_of(out, None) };
            let lic = a.one("license").map(|p| readf(&p)).transpose()?;
            let wo = WriterOpts { name, summary: a.one("summary"), uuid: a.one("uuid"), created: a.one("created"), license_text: lic, spdx_id: a.one("spdx") };
            let profile = if cmd == "pack-image" { "image/1" } else { "3d-entity/1" };
            let mut w = Writer::new(profile, wo)?;
            let mut spec_files: Vec<(String, Vec<u8>)> = vec![];
            for spec in a.many("spec-file") {
                let (p, local) = spec.split_once('=').ok_or(Fail::Usage("--spec-file is PKGPATH=FILE (PKGPATH under spec/)".into()))?;
                spec_files.push((p.to_string(), readf(local)?));
            }
            spec_files.sort_by(|x, y| x.0.as_bytes().cmp(y.0.as_bytes()));
            for (p, d) in spec_files {
                w.add_spec_file(&p, d)?;
            }
            if let Some(cm) = a.one("conventions-map") {
                check_path(&cm)?;
                w.conventions_map = Some(cm);
            }
            for spec in a.many("readme-file") {
                let (p, local) = spec.split_once('=').ok_or(Fail::Usage("--readme-file is PKGPATH=FILE".into()))?;
                w.add_readme_file(p, readf(local)?)?;
            }
            let atts = attachments(a)?;
            if cmd == "pack-image" {
                let png = readf(&a.one("png").ok_or(Fail::Usage("pack-image needs --png".into()))?)?;
                let jf = |k: &str| -> Result<Option<J>, Fail> { match a.one(k) { None => Ok(None), Some(p) => Ok(Some(json::parse_bytes(&readf(&p)?)?)) } };
                let io = ImageOpts { thumb: a.one("thumb").map(|p| readf(&p)).transpose()?, recipe: jf("recipe")?, disclosure: jf("disclosure")?,
                                     model: a.one("model"), epistemic: a.one("epistemic"), inputs: a.opt.get("input").cloned() };
                image_package(&mut w, png, io, atts)?;
            } else {
                let glb = readf(&a.one("glb").ok_or(Fail::Usage("pack-mesh needs --glb".into()))?)?;
                let mut texs = vec![];
                for spec in a.many("texture") {
                    let (id, rest) = spec.split_once('=').ok_or(Fail::Usage("--texture is ID=FILE[:usage]".into()))?;
                    let (fpath, usage) = match rest.rfind(':') {
                        Some(i) if !Path::new(rest).exists() => (&rest[..i], &rest[i + 1..]),
                        _ => (rest, "base-color"),
                    };
                    texs.push(Tex { id: id.into(), png: readf(fpath)?, usage: usage.into() });
                }
                let mats = a.many("material").iter().map(|s| match s.split_once(':') {
                    Some((m, t)) => Mat { id: m.into(), base_color: if t.is_empty() { None } else { Some(t.into()) } },
                    None => Mat { id: s.clone(), base_color: None },
                }).collect();
                let pv = a.one("preview").map(|p| readf(&p)).transpose()?;
                mesh_package(&mut w, glb, texs, mats, pv, atts)?;
            }
            if let Some(s) = signer_of(a)? {
                w.signers.push(s);
            }
            w.write(out, &form)?;
            println!("wrote {out}");
            Ok(0)
        }
        "append" => {
            need(2, "append needs <pkg> <out> --node ID --file PKGPATH=FILE --note TEXT")?;
            let node = a.one("node").ok_or(Fail::Usage("append needs --node".into()))?;
            let note = a.one("note").ok_or(Fail::Usage("append needs --note".into()))?;
            let mut files = vec![];
            for spec in a.many("file") {
                let (p, local) = spec.split_once('=').ok_or(Fail::Usage("--file is PKGPATH=FILE".into()))?;
                files.push(nf(p, readf(local)?, None, None)?);
            }
            if files.is_empty() {
                return Err(Fail::Usage("append needs --file".into()));
            }
            let ao = AppendOpts { epistemic: a.one("epistemic"), created: a.one("created"), node_type: a.one("type"), signer: signer_of(a)?,
                                  drop_signature: a.flag("drop-signature"), form: if a.flag("dir") { Some("directory".into()) } else { None } };
            append_version(&a.pos[0], &a.pos[1], &node, files, &note, ao)?;
            println!("wrote {}", a.pos[1]);
            Ok(0)
        }
        "sign" => {
            need(2, "sign needs <pkg> <out> --sign-key HEX")?;
            let s = signer_of(a)?.ok_or(Fail::Usage("sign needs --sign-key".into()))?;
            sign_package(&a.pos[0], &a.pos[1], s, if a.flag("dir") { Some("directory") } else { None })?;
            println!("wrote {}", a.pos[1]);
            Ok(0)
        }
        _ => Err(Fail::Usage(format!("unknown command {cmd}"))),
    }
}
