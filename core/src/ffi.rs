//! The C ABI. One shared library, three faces.
//!
//! `include/werk.h` is the header this module implements; read it for the
//! contract as a C programmer sees it. The rules that matter:
//!
//!   * Every returned `const char*` and every blob pointer is owned by the
//!     package handle and is valid until that handle is closed OR mutated.
//!     Any call that changes the package (sign, strip, add_node,
//!     append_version, stage_file) invalidates every pointer previously handed
//!     out for it.
//!   * Functions returning `int32_t` return 0 on success and a negative
//!     `werk_status` on failure; `werk_last_error()` then has the detail.
//!   * A handle is NOT thread-safe. Use one per thread.
//!   * Damage never fails a call: a package with dead nodes opens fine and the
//!     report says what died. Check `werk_report_*`, not the return code, to
//!     find out what was lost.

#![allow(clippy::missing_safety_doc)]

use crate::package::{NewFile, NewNode, NewVersion, OpenOptions, Package};
use crate::signature::Signer_;
use serde_json::Value;
use std::cell::RefCell;
use std::ffi::{c_char, CStr, CString};
use std::ptr;

thread_local! {
    static LAST_ERROR: RefCell<CString> = RefCell::new(CString::new("").unwrap());
}

fn set_error(msg: impl Into<String>) {
    let s = CString::new(msg.into().replace('\0', " ")).unwrap_or_default();
    LAST_ERROR.with(|e| *e.borrow_mut() = s);
}

/// Opaque handle. The arena keeps every `CString` this handle has handed out
/// alive, so the pointers stay valid without the caller owning anything.
pub struct WerkPackage {
    pkg: Package,
    arena: RefCell<Vec<CString>>,
}

impl WerkPackage {
    fn cstr(&self, s: &str) -> *const c_char {
        let c = CString::new(s.replace('\0', " ")).unwrap_or_default();
        let p = c.as_ptr();
        self.arena.borrow_mut().push(c);
        p
    }
    fn invalidate(&self) {
        self.arena.borrow_mut().clear();
    }
}

const EMPTY: &[u8] = b"\0";
fn empty() -> *const c_char {
    EMPTY.as_ptr() as *const c_char
}

unsafe fn as_str<'a>(p: *const c_char) -> Option<&'a str> {
    if p.is_null() {
        return None;
    }
    CStr::from_ptr(p).to_str().ok()
}

unsafe fn pkg<'a>(h: *mut WerkPackage) -> Option<&'a WerkPackage> {
    if h.is_null() {
        set_error("null package handle");
        return None;
    }
    Some(&*h)
}

// ---------------------------------------------------------------------------
// Library
// ---------------------------------------------------------------------------

#[no_mangle]
pub extern "C" fn werk_version() -> *const c_char {
    concat!(env!("CARGO_PKG_VERSION"), "\0").as_ptr() as *const c_char
}

#[no_mangle]
pub extern "C" fn werk_profile() -> *const c_char {
    concat!("3d-entity/1", "\0").as_ptr() as *const c_char
}

#[no_mangle]
pub extern "C" fn werk_last_error() -> *const c_char {
    LAST_ERROR.with(|e| e.borrow().as_ptr())
}

// ---------------------------------------------------------------------------
// Open / close
// ---------------------------------------------------------------------------

#[no_mangle]
pub unsafe extern "C" fn werk_open(
    path: *const c_char,
    flags: u32,
    out: *mut *mut WerkPackage,
) -> i32 {
    if out.is_null() {
        set_error("werk_open: out pointer is null");
        return -9;
    }
    *out = ptr::null_mut();
    let path = match as_str(path) {
        Some(p) => p,
        None => {
            set_error("werk_open: path is null or not UTF-8");
            return -9;
        }
    };
    match Package::open_with(path, OpenOptions::from_flags(flags)) {
        Ok(p) => {
            let boxed = Box::new(WerkPackage { pkg: p, arena: RefCell::new(Vec::new()) });
            *out = Box::into_raw(boxed);
            0
        }
        Err(e) => {
            let code = e.code();
            set_error(e.to_string());
            code
        }
    }
}

#[no_mangle]
pub unsafe extern "C" fn werk_close(h: *mut WerkPackage) {
    if !h.is_null() {
        drop(Box::from_raw(h));
    }
}

// ---------------------------------------------------------------------------
// Package facts
// ---------------------------------------------------------------------------

macro_rules! str_getter {
    ($name:ident, $body:expr) => {
        #[no_mangle]
        pub unsafe extern "C" fn $name(h: *mut WerkPackage) -> *const c_char {
            match pkg(h) {
                None => empty(),
                Some(w) => {
                    let f: fn(&Package) -> String = $body;
                    let s = f(&w.pkg);
                    w.cstr(&s)
                }
            }
        }
    };
}

str_getter!(werk_entity_name, |p| p.manifest.entity_name().to_string());
str_getter!(werk_entity_uuid, |p| p.manifest.entity_uuid().to_string());
str_getter!(werk_package_profile, |p| p.manifest.profile().to_string());
str_getter!(werk_manifest_sha256, |p| p.manifest_sha256());

#[no_mangle]
pub unsafe extern "C" fn werk_manifest_bytes(
    h: *mut WerkPackage,
    len: *mut usize,
) -> *const u8 {
    match pkg(h) {
        None => ptr::null(),
        Some(w) => {
            if !len.is_null() {
                *len = w.pkg.manifest.bytes.len();
            }
            w.pkg.manifest.bytes.as_ptr()
        }
    }
}

/// 0 = absent, 1 = signed-and-valid, 2 = present-and-invalid, 3 = unverified
/// (the chain names an algorithm this library does not implement; SPEC.md
/// section 10.1). Three states, never two: SPEC.md section 6 is explicit that
/// collapsing absent and invalid into one warning defeats the doctrine, so the
/// ABI cannot express the collapse.
#[no_mangle]
pub unsafe extern "C" fn werk_signature_state(h: *mut WerkPackage) -> i32 {
    match pkg(h) {
        None => -9,
        Some(w) => w.pkg.signature_state.code(),
    }
}

str_getter!(werk_signature_detail, |p| p.signature_state.as_str().to_string());

// ---------------------------------------------------------------------------
// Load report
// ---------------------------------------------------------------------------

#[no_mangle]
pub unsafe extern "C" fn werk_report_count(h: *mut WerkPackage) -> i32 {
    pkg(h).map_or(-9, |w| w.pkg.report.entries.len() as i32)
}

#[no_mangle]
pub unsafe extern "C" fn werk_report_errors(h: *mut WerkPackage) -> i32 {
    pkg(h).map_or(-9, |w| w.pkg.report.errors() as i32)
}

macro_rules! report_getter {
    ($name:ident, $f:expr) => {
        #[no_mangle]
        pub unsafe extern "C" fn $name(h: *mut WerkPackage, i: i32) -> *const c_char {
            match pkg(h) {
                None => empty(),
                Some(w) => match w.pkg.report.entries.get(i.max(0) as usize) {
                    None => empty(),
                    Some(e) => {
                        let f: fn(&crate::report::ReportEntry) -> String = $f;
                        let s = f(e);
                        w.cstr(&s)
                    }
                },
            }
        }
    };
}

report_getter!(werk_report_code, |e| e.code.as_str().to_string());
report_getter!(werk_report_severity, |e| e.severity.as_str().to_string());
report_getter!(werk_report_node, |e| e.node_id.clone().unwrap_or_default());
report_getter!(werk_report_path, |e| e.path.clone().unwrap_or_default());
report_getter!(werk_report_message, |e| e.message.clone());

#[no_mangle]
pub unsafe extern "C" fn werk_report_version(h: *mut WerkPackage, i: i32) -> i32 {
    match pkg(h) {
        None => -9,
        Some(w) => w
            .pkg
            .report
            .entries
            .get(i.max(0) as usize)
            .and_then(|e| e.version)
            .map_or(-1, |v| v as i32),
    }
}

// ---------------------------------------------------------------------------
// Nodes, versions, files
// ---------------------------------------------------------------------------

#[no_mangle]
pub unsafe extern "C" fn werk_node_count(h: *mut WerkPackage) -> i32 {
    pkg(h).map_or(-9, |w| w.pkg.nodes.len() as i32)
}

#[no_mangle]
pub unsafe extern "C" fn werk_node_index(h: *mut WerkPackage, node_id: *const c_char) -> i32 {
    let w = match pkg(h) {
        Some(w) => w,
        None => return -9,
    };
    let id = match as_str(node_id) {
        Some(s) => s,
        None => return -5,
    };
    w.pkg
        .nodes
        .iter()
        .position(|n| n.view.node_id == id)
        .map_or(-5, |i| i as i32)
}

macro_rules! node_getter {
    ($name:ident, $f:expr) => {
        #[no_mangle]
        pub unsafe extern "C" fn $name(h: *mut WerkPackage, n: i32) -> *const c_char {
            match pkg(h) {
                None => empty(),
                Some(w) => match w.pkg.nodes.get(n.max(0) as usize) {
                    None => empty(),
                    Some(node) => {
                        let f: fn(&crate::package::NodeState) -> String = $f;
                        let s = f(node);
                        w.cstr(&s)
                    }
                },
            }
        }
    };
}

node_getter!(werk_node_id, |n| n.view.node_id.clone());
node_getter!(werk_node_type, |n| n.view.ntype.clone());
node_getter!(werk_node_status_reason, |n| n.status.reason().to_string());

/// 0 = alive, 1 = skipped (unknown type, bytes still good), 2 = dead.
#[no_mangle]
pub unsafe extern "C" fn werk_node_status(h: *mut WerkPackage, n: i32) -> i32 {
    match pkg(h) {
        None => -9,
        Some(w) => w.pkg.nodes.get(n.max(0) as usize).map_or(-5, |x| x.status.code()),
    }
}

#[no_mangle]
pub unsafe extern "C" fn werk_node_active(h: *mut WerkPackage, n: i32) -> i32 {
    match pkg(h) {
        None => -9,
        Some(w) => w.pkg.nodes.get(n.max(0) as usize).map_or(-5, |x| x.view.active as i32),
    }
}

/// The version actually usable after fallback, or -1 when the node is dead.
#[no_mangle]
pub unsafe extern "C" fn werk_node_resolved(h: *mut WerkPackage, n: i32) -> i32 {
    match pkg(h) {
        None => -9,
        Some(w) => w
            .pkg
            .nodes
            .get(n.max(0) as usize)
            .map_or(-5, |x| x.resolved.map_or(-1, |v| v as i32)),
    }
}

#[no_mangle]
pub unsafe extern "C" fn werk_version_count(h: *mut WerkPackage, n: i32) -> i32 {
    match pkg(h) {
        None => -9,
        Some(w) => w.pkg.nodes.get(n.max(0) as usize).map_or(-5, |x| x.view.versions.len() as i32),
    }
}

fn version_at(w: &WerkPackage, n: i32, v: i32) -> Option<&crate::manifest::VersionView> {
    w.pkg.nodes.get(n.max(0) as usize)?.view.versions.get(v.max(0) as usize)
}

#[no_mangle]
pub unsafe extern "C" fn werk_version_number(h: *mut WerkPackage, n: i32, v: i32) -> i32 {
    match pkg(h) {
        None => -9,
        Some(w) => version_at(w, n, v).map_or(-5, |x| x.v as i32),
    }
}

macro_rules! version_getter {
    ($name:ident, $f:expr) => {
        #[no_mangle]
        pub unsafe extern "C" fn $name(h: *mut WerkPackage, n: i32, v: i32) -> *const c_char {
            match pkg(h) {
                None => empty(),
                Some(w) => match version_at(w, n, v) {
                    None => empty(),
                    Some(ver) => {
                        let f: fn(&crate::manifest::VersionView) -> String = $f;
                        let s = f(ver);
                        w.cstr(&s)
                    }
                },
            }
        }
    };
}

version_getter!(werk_version_note, |v| v.note.clone());
version_getter!(werk_version_epistemic, |v| v.epistemic.clone());
version_getter!(werk_version_created, |v| v.created.clone());
version_getter!(werk_version_input_hash, |v| v.input_hash.clone().unwrap_or_default());

#[no_mangle]
pub unsafe extern "C" fn werk_file_count(h: *mut WerkPackage, n: i32, v: i32) -> i32 {
    match pkg(h) {
        None => -9,
        Some(w) => version_at(w, n, v).map_or(-5, |x| x.files.len() as i32),
    }
}

macro_rules! file_getter {
    ($name:ident, $f:expr) => {
        #[no_mangle]
        pub unsafe extern "C" fn $name(
            h: *mut WerkPackage,
            n: i32,
            v: i32,
            f: i32,
        ) -> *const c_char {
            match pkg(h) {
                None => empty(),
                Some(w) => match version_at(w, n, v).and_then(|x| x.files.get(f.max(0) as usize)) {
                    None => empty(),
                    Some(fr) => {
                        let g: fn(&crate::manifest::FileRef) -> String = $f;
                        let s = g(fr);
                        w.cstr(&s)
                    }
                },
            }
        }
    };
}

file_getter!(werk_file_path, |f| f.path.clone());
file_getter!(werk_file_sha256, |f| f.sha256.clone());
file_getter!(werk_file_role, |f| f.role.clone().unwrap_or_default());
file_getter!(werk_file_media_type, |f| f.media_type.clone().unwrap_or_default());

#[no_mangle]
pub unsafe extern "C" fn werk_file_size(h: *mut WerkPackage, n: i32, v: i32, f: i32) -> u64 {
    match pkg(h) {
        None => 0,
        Some(w) => version_at(w, n, v)
            .and_then(|x| x.files.get(f.max(0) as usize))
            .map_or(0, |fr| fr.size),
    }
}

// ---------------------------------------------------------------------------
// Blobs
// ---------------------------------------------------------------------------

/// Borrowed pointer into bytes the package holds. Valid until the handle is
/// closed or mutated. Never free it.
#[no_mangle]
pub unsafe extern "C" fn werk_blob(
    h: *mut WerkPackage,
    path: *const c_char,
    data: *mut *const u8,
    len: *mut usize,
) -> i32 {
    let w = match pkg(h) {
        Some(w) => w,
        None => return -9,
    };
    let p = match as_str(path) {
        Some(p) => p,
        None => {
            set_error("werk_blob: path is null or not UTF-8");
            return -9;
        }
    };
    match w.pkg.blob(p) {
        Ok(rc) => {
            if !data.is_null() {
                *data = rc.as_ptr();
            }
            if !len.is_null() {
                *len = rc.len();
            }
            0
        }
        Err(e) => {
            let c = e.code();
            set_error(e.to_string());
            c
        }
    }
}

// ---------------------------------------------------------------------------
// Verification, writing
// ---------------------------------------------------------------------------

/// Re-run the load with full verification. Returns the number of ERROR-severity
/// report entries — 0 means every declared hash matched.
#[no_mangle]
pub unsafe extern "C" fn werk_verify(h: *mut WerkPackage) -> i32 {
    match pkg(h) {
        None => -9,
        Some(w) => w.pkg.report.errors() as i32,
    }
}

#[no_mangle]
pub unsafe extern "C" fn werk_write_zip(h: *mut WerkPackage, dest: *const c_char) -> i32 {
    let w = match pkg(h) {
        Some(w) => w,
        None => return -9,
    };
    let d = match as_str(dest) {
        Some(d) => d,
        None => return -9,
    };
    match w.pkg.write_zip(d) {
        Ok(_) => 0,
        Err(e) => {
            let c = e.code();
            set_error(e.to_string());
            c
        }
    }
}

#[no_mangle]
pub unsafe extern "C" fn werk_materialize_dir(h: *mut WerkPackage, dest: *const c_char) -> i32 {
    let w = match pkg(h) {
        Some(w) => w,
        None => return -9,
    };
    let d = match as_str(dest) {
        Some(d) => d,
        None => return -9,
    };
    match w.pkg.materialize_dir(d) {
        Ok(n) => n as i32,
        Err(e) => {
            let c = e.code();
            set_error(e.to_string());
            c
        }
    }
}

// ---------------------------------------------------------------------------
// Signing
// ---------------------------------------------------------------------------

#[no_mangle]
pub unsafe extern "C" fn werk_sign(
    h: *mut WerkPackage,
    secret_key_hex: *const c_char,
    name: *const c_char,
    uri: *const c_char,
    kind: *const c_char,
    role: *const c_char,
    note: *const c_char,
    signed_at: *const c_char,
) -> i32 {
    if h.is_null() {
        set_error("werk_sign: null package handle");
        return -9;
    }
    let who = Signer_ {
        name: as_str(name).unwrap_or("").to_string(),
        uri: as_str(uri).unwrap_or("").to_string(),
        kind: as_str(kind).unwrap_or("human").to_string(),
        role: as_str(role).filter(|s| !s.is_empty()).map(str::to_string),
        note: as_str(note).filter(|s| !s.is_empty()).map(str::to_string),
        signed_at: as_str(signed_at).unwrap_or("").to_string(),
    };
    let sk = match as_str(secret_key_hex) {
        Some(s) => s,
        None => return -6,
    };
    let me = &mut *h;
    me.invalidate();
    match me.pkg.sign(sk, who) {
        Ok(()) => 0,
        Err(e) => {
            let c = e.code();
            set_error(e.to_string());
            c
        }
    }
}

#[no_mangle]
pub unsafe extern "C" fn werk_strip_signature(h: *mut WerkPackage) -> i32 {
    if h.is_null() {
        set_error("werk_strip_signature: null package handle");
        return -9;
    }
    let me = &mut *h;
    me.invalidate();
    me.pkg.strip_signature();
    0
}

// ---------------------------------------------------------------------------
// Mutation
// ---------------------------------------------------------------------------

/// Put payload bytes into the package before declaring them. The node
/// description passed to `werk_add_node`/`werk_append_version` refers to them
/// by path.
#[no_mangle]
pub unsafe extern "C" fn werk_stage_file(
    h: *mut WerkPackage,
    path: *const c_char,
    data: *const u8,
    len: usize,
) -> i32 {
    if h.is_null() {
        return -9;
    }
    let p = match as_str(path) {
        Some(p) => p.to_string(),
        None => return -9,
    };
    let bytes = if data.is_null() || len == 0 {
        Vec::new()
    } else {
        std::slice::from_raw_parts(data, len).to_vec()
    };
    let me = &mut *h;
    me.invalidate();
    me.pkg.stage_blob(&p, bytes);
    0
}

fn version_from_json(w: &Package, v: &Value) -> Result<NewVersion, String> {
    let mut files = Vec::new();
    for f in v.get("files").and_then(Value::as_array).ok_or("version has no files[]")? {
        let path = f.get("path").and_then(Value::as_str).ok_or("a file has no path")?;
        let bytes = w
            .peek(path)
            .ok_or_else(|| format!("no bytes for `{path}`: stage it with werk_stage_file first"))?;
        files.push(NewFile {
            path: path.to_string(),
            bytes,
            media_type: f.get("media_type").and_then(Value::as_str).map(str::to_string),
            role: f.get("role").and_then(Value::as_str).map(str::to_string),
        });
    }
    Ok(NewVersion {
        files,
        note: v.get("note").and_then(Value::as_str).unwrap_or("").to_string(),
        producer_tool: v
            .pointer("/producer/tool")
            .and_then(Value::as_str)
            .unwrap_or("unknown")
            .to_string(),
        producer_version: v
            .pointer("/producer/version")
            .and_then(Value::as_str)
            .unwrap_or("0")
            .to_string(),
        producer_model: v.pointer("/producer/model").and_then(Value::as_str).map(str::to_string),
        epistemic: v.get("epistemic").and_then(Value::as_str).unwrap_or("authored").to_string(),
        created: v.get("created").and_then(Value::as_str).unwrap_or("").to_string(),
        input_files: v
            .get("input_files")
            .and_then(Value::as_array)
            .map(|a| a.iter().filter_map(Value::as_str).map(str::to_string).collect())
            .unwrap_or_default(),
        input_params: v.get("input_params").cloned(),
    })
}

#[no_mangle]
pub unsafe extern "C" fn werk_add_node(h: *mut WerkPackage, spec_json: *const c_char) -> i32 {
    if h.is_null() {
        return -9;
    }
    let text = match as_str(spec_json) {
        Some(t) => t,
        None => return -9,
    };
    let spec: Value = match serde_json::from_str(text) {
        Ok(v) => v,
        Err(e) => {
            set_error(format!("werk_add_node: spec is not JSON: {e}"));
            return -8;
        }
    };
    let me = &mut *h;
    me.invalidate();
    let ver = match spec.get("version").ok_or("spec has no `version` object".to_string())
        .and_then(|v| version_from_json(&me.pkg, v))
    {
        Ok(v) => v,
        Err(e) => {
            set_error(e);
            return -8;
        }
    };
    let node = NewNode {
        node_id: spec.get("node_id").and_then(Value::as_str).unwrap_or("").to_string(),
        ntype: spec.get("type").and_then(Value::as_str).unwrap_or("").to_string(),
        part_id: spec.get("part_id").and_then(Value::as_str).map(str::to_string),
        material_id: spec.get("material_id").and_then(Value::as_str).map(str::to_string),
        meta: spec.get("meta").cloned(),
        edges: spec.get("edges").cloned().unwrap_or_else(|| Value::Array(Vec::new())),
        version: ver,
    };
    match me.pkg.add_node(node) {
        Ok(()) => 0,
        Err(e) => {
            let c = e.code();
            set_error(e.to_string());
            c
        }
    }
}

/// Returns the new version number, or a negative status.
#[no_mangle]
pub unsafe extern "C" fn werk_append_version(
    h: *mut WerkPackage,
    node_id: *const c_char,
    spec_json: *const c_char,
) -> i32 {
    if h.is_null() {
        return -9;
    }
    let id = match as_str(node_id) {
        Some(t) => t.to_string(),
        None => return -9,
    };
    let text = match as_str(spec_json) {
        Some(t) => t,
        None => return -9,
    };
    let spec: Value = match serde_json::from_str(text) {
        Ok(v) => v,
        Err(e) => {
            set_error(format!("werk_append_version: spec is not JSON: {e}"));
            return -8;
        }
    };
    let me = &mut *h;
    me.invalidate();
    let ver = match version_from_json(&me.pkg, &spec) {
        Ok(v) => v,
        Err(e) => {
            set_error(e);
            return -8;
        }
    };
    match me.pkg.append_version(&id, ver) {
        Ok(v) => v as i32,
        Err(e) => {
            let c = e.code();
            set_error(e.to_string());
            c
        }
    }
}
