//! Opening, verifying, degrading, writing and extending a werk package.
//!
//! The shape of this module is dictated by SPEC.md section 10, the reader
//! checklist, in order: open the container, read and validate the manifest,
//! check the conventions, verify the signature chain and report which of the
//! THREE states you are in, walk the nodes resolving `active` with fallback,
//! verify every file, dispatch by type, skip what you do not know and SAY SO,
//! and never follow a path that is not in some `files[]`.

use crate::envelope;
use crate::error::{Error, Result};
use crate::hashing::{sha256, sha256_hex, to_hex};
use crate::formats;
use crate::manifest::{
    canonical_json, pretty_json, Manifest, NodeView, VersionView, KNOWN_TYPES,
    MANIFEST_SCHEMA_BASE, SIGNATURE_SCHEMA,
};
use crate::report::{Code, LoadReport, Severity};
use crate::schema::Validator;
use crate::signature::{self, SignatureState};
use crate::zipstore::{self, ZipArchive};
use serde_json::{json, Map, Value};
use std::cell::RefCell;
use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};
use std::rc::Rc;

pub const MANIFEST_NAME: &str = "MANIFEST.json";
pub const SIGNATURE_NAME: &str = "SIGNATURE.json";

#[derive(Debug, Clone, Copy)]
pub struct OpenOptions {
    /// Hash every file of every resolvable version. Off makes `open` a listing
    /// operation; on makes it a verification. Default on — a reader that says
    /// "loaded" without checking has told you nothing.
    pub verify: bool,
    /// Dispatch by node type: validate JSON payloads against the schemas the
    /// manifest points at, and parse custom binaries against the envelope
    /// grammar.
    pub interpret: bool,
    /// Recompute `input_hash` from the declared `input_files` and report drift
    /// (law 5's validate-or-recompute).
    pub check_derived: bool,
}

impl Default for OpenOptions {
    fn default() -> Self {
        OpenOptions { verify: true, interpret: true, check_derived: true }
    }
}

impl OpenOptions {
    pub fn from_flags(flags: u32) -> OpenOptions {
        // Bit 0 skip verify, bit 1 skip interpret, bit 2 skip derived checks.
        OpenOptions {
            verify: flags & 1 == 0,
            interpret: flags & 2 == 0,
            check_derived: flags & 4 == 0,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum NodeStatus {
    /// Resolved, verified, and of a type this reader interprets.
    Alive,
    /// Bytes are fine; the type is one this reader does not interpret. Listed,
    /// hashed and extractable — law 12's "loses nothing but that feature".
    Skipped(String),
    /// Unusable. The reason is exact, never "load failed".
    Dead(String),
}

impl NodeStatus {
    pub fn code(&self) -> i32 {
        match self {
            NodeStatus::Alive => 0,
            NodeStatus::Skipped(_) => 1,
            NodeStatus::Dead(_) => 2,
        }
    }
    pub fn reason(&self) -> &str {
        match self {
            NodeStatus::Alive => "",
            NodeStatus::Skipped(r) | NodeStatus::Dead(r) => r,
        }
    }
    pub fn is_dead(&self) -> bool {
        matches!(self, NodeStatus::Dead(_))
    }
}

#[derive(Debug, Clone)]
pub struct NodeState {
    pub view: NodeView,
    pub status: NodeStatus,
    /// The version actually usable — `active`, or an earlier one after a
    /// reported fallback, or none if the node is dead.
    pub resolved: Option<i64>,
}

enum Source {
    Dir(PathBuf),
    Zip(Box<ZipArchive>),
}

pub struct Package {
    pub origin: PathBuf,
    source: Source,
    pub manifest: Manifest,
    pub signature_raw: Option<Value>,
    pub signature_state: SignatureState,
    pub nodes: Vec<NodeState>,
    pub report: LoadReport,
    opts: OpenOptions,
    /// Bytes staged by add_node/append_version that are not yet on disk.
    overlay: BTreeMap<String, Vec<u8>>,
    /// The chain was deliberately removed in memory; the copy still sitting in
    /// the source container must not shine through.
    signature_stripped: bool,
    cache: RefCell<BTreeMap<String, Rc<Vec<u8>>>>,
    /// How many files were recognised as envelopes and passed the frame check
    /// of ENVELOPE.layout.txt section 7. Stated, because "no envelope
    /// complaints" and "no envelopes looked at" used to print the same nothing
    /// (finding S12-1).
    pub envelopes_validated: usize,
    /// Format definition documents read and found usable, and how many printed
    /// test-vector inputs in them were re-hashed (SPEC.md section 3.18).
    pub formats_read: usize,
    pub format_vectors_checked: usize,
    /// JSON payloads validated against the schema the package's `schemas` map
    /// names for their node type.
    pub payloads_validated: usize,
    /// Every path any version of any node declares -> (sha256, node_id, node
    /// type). Rebuilt by every analysis; the last declaration of a path wins,
    /// and S-18 makes every declaration of one path identical.
    file_index: BTreeMap<String, (String, String, String)>,
    /// How the manifest was validated, in one fixed word — see
    /// [`ManifestValidation`].
    pub manifest_validation: ManifestValidation,
}

/// Which schema(s) the manifest was held against (SPEC.md section 2.2). The
/// built-in BASE schema is applied in every case and is not listed.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ManifestValidation {
    /// A profile this build has built in, and the package carries the same
    /// revision of its schema (or none): validated against this build's copy.
    BuiltIn,
    /// A profile this build has built in, but the package carries another
    /// revision of its schema: validated against the PACKAGE's copy, and
    /// against this build's copy at warning severity.
    PackageRevision,
    /// A profile this build does not have: validated against the schema the
    /// package names and carries. Establishes self-consistency, not meaning.
    PackageOwn,
    /// No profile schema could be used; only the base shape was checked.
    BaseOnly,
}

impl ManifestValidation {
    pub fn as_str(&self) -> &'static str {
        match self {
            ManifestValidation::BuiltIn => "built-in-schema",
            ManifestValidation::PackageRevision => "package-schema-revision",
            ManifestValidation::PackageOwn => "package-own-schema",
            ManifestValidation::BaseOnly => "base-schema-only",
        }
    }
}

impl Package {
    pub fn open(path: impl AsRef<Path>) -> Result<Package> {
        Package::open_with(path, OpenOptions::default())
    }

    pub fn open_with(path: impl AsRef<Path>, opts: OpenOptions) -> Result<Package> {
        let path = path.as_ref().to_path_buf();
        let source = if path.is_dir() {
            Source::Dir(path.clone())
        } else if path.is_file() {
            // A zip64 container is refused from its last 64 KiB, before the
            // file — which may be larger than memory — is read at all.
            zipstore::refuse_zip64_from_tail(&path)?;
            let bytes = std::fs::read(&path)?;
            Source::Zip(Box::new(ZipArchive::parse(bytes)?))
        } else {
            return Err(Error::NotFound(format!("{} does not exist", path.display())));
        };

        let manifest_bytes = read_source(&source, MANIFEST_NAME).map_err(|e| match e {
            Error::NoSuchItem(_) => {
                Error::ManifestAbsent(format!("{MANIFEST_NAME} is not in {}", path.display()))
            }
            other => Error::BadManifest(format!("{MANIFEST_NAME} cannot be read: {other}")),
        })?;
        let manifest = Manifest::parse(manifest_bytes)?;

        let signature_raw = read_source(&source, SIGNATURE_NAME)
            .ok()
            .and_then(|b| serde_json::from_slice::<Value>(&b).ok());

        let mut pkg = Package {
            origin: path,
            source,
            manifest,
            signature_raw,
            signature_state: SignatureState::Absent,
            nodes: Vec::new(),
            report: LoadReport::default(),
            opts,
            overlay: BTreeMap::new(),
            signature_stripped: false,
            cache: RefCell::new(BTreeMap::new()),
            envelopes_validated: 0,
            formats_read: 0,
            format_vectors_checked: 0,
            payloads_validated: 0,
            file_index: BTreeMap::new(),
            manifest_validation: ManifestValidation::BaseOnly,
        };
        pkg.analyse();
        Ok(pkg)
    }

    // -----------------------------------------------------------------
    // Reading
    // -----------------------------------------------------------------

    /// Package-relative read. A path not declared in any node's `files[]` is
    /// still readable through here — the "never follow an undeclared path" rule
    /// (checklist step 9) is enforced where paths COME FROM, and every caller
    /// inside this crate takes its paths from the manifest.
    pub fn blob(&self, path: &str) -> Result<Rc<Vec<u8>>> {
        if let Some(v) = self.cache.borrow().get(path) {
            return Ok(v.clone());
        }
        let bytes = self.raw_read(path)?;
        let rc = Rc::new(bytes);
        self.cache.borrow_mut().insert(path.to_string(), rc.clone());
        Ok(rc)
    }

    fn raw_read(&self, path: &str) -> Result<Vec<u8>> {
        if let Some(b) = self.overlay.get(path) {
            return Ok(b.clone());
        }
        if self.signature_stripped && path == SIGNATURE_NAME {
            return Err(Error::NoSuchItem(format!("no file `{path}` in this package")));
        }
        read_source(&self.source, path)
    }

    /// How many zip entries of this container are stored deflated (method 8).
    /// 0 for a directory and for every store-mode package.
    pub fn deflated_entries(&self) -> usize {
        match &self.source {
            Source::Zip(z) => z.deflated_names().len(),
            Source::Dir(_) => 0,
        }
    }

    pub fn container_files(&self) -> Vec<String> {
        let mut out: BTreeSet<String> = match &self.source {
            Source::Dir(d) => walk_dir(d),
            Source::Zip(z) => z.names().into_iter().filter(|n| !n.ends_with('/')).collect(),
        };
        if self.signature_stripped {
            out.remove(SIGNATURE_NAME);
        }
        for k in self.overlay.keys() {
            out.insert(k.clone());
        }
        out.into_iter().collect()
    }

    pub fn node(&self, node_id: &str) -> Option<&NodeState> {
        self.nodes.iter().find(|n| n.view.node_id == node_id)
    }

    /// Every path declared by any version of any node, mapped to its sha256.
    fn declared_paths(&self) -> BTreeMap<String, String> {
        let mut m = BTreeMap::new();
        for n in &self.nodes {
            for v in &n.view.versions {
                for f in &v.files {
                    m.insert(f.path.clone(), f.sha256.clone());
                }
            }
        }
        m
    }

    // -----------------------------------------------------------------
    // The load
    // -----------------------------------------------------------------

    fn analyse(&mut self) {
        self.nodes.clear();
        self.report = LoadReport::default();
        self.cache.borrow_mut().clear();

        self.envelopes_validated = 0;
        self.formats_read = 0;
        self.format_vectors_checked = 0;
        self.payloads_validated = 0;
        self.file_index.clear();
        for view in self.manifest.nodes().into_iter().flatten() {
            for ver in &view.versions {
                for f in &ver.files {
                    self.file_index.insert(
                        f.path.clone(),
                        (f.sha256.clone(), view.node_id.clone(), view.ntype.clone()),
                    );
                }
            }
        }

        // 1. Schema. Errors under /nodes/<i> kill only that node; everything
        //    else is a package-level complaint that does not stop the load.
        let mut node_schema_errors: BTreeMap<usize, Vec<String>> = BTreeMap::new();

        // 1a. The BASE shape (SPEC.md section 2.2). Built in, applied to every
        //     manifest of every profile, and not something a package can
        //     loosen by shipping a permissive schema of its own.
        if let Err(e) = self.run_schema(
            MANIFEST_SCHEMA_BASE,
            false,
            Severity::Error,
            "base shape: ",
            Some(&mut node_schema_errors),
        ) {
            self.report.push(
                Severity::Error,
                Code::SchemaInvalid,
                None,
                None,
                None,
                format!("the built-in base manifest schema is unusable: {e}"),
            );
        }

        // 1b. The PROFILE's schema — this build's, or the one the package
        //     names and carries.
        self.manifest_validation = self.validate_against_profile_schema(&mut node_schema_errors);

        // 1c. `spec_sha256` is a claim the manifest makes about itself, and it
        //     is checkable from the manifest alone.
        self.check_spec_sha256();

        // 2. Conventions: refuse, do not guess. For a profile this build has
        //    built in, the profile's whole set; for any other, the six base
        //    conventions this reader itself depends on (SPEC.md section 10.3).
        for c in self.manifest.unsupported_conventions() {
            self.report.push(Severity::Error, Code::UnsupportedConvention, None, None, None, c);
        }

        // 3. Signature — three states, always stated.
        self.signature_state = match &self.signature_raw {
            None => {
                self.report.push(
                    Severity::Info,
                    Code::SignatureAbsent,
                    None,
                    None,
                    None,
                    "no SIGNATURE.json: this package is anonymous, which is a legitimate state",
                );
                SignatureState::Absent
            }
            Some(sig) => {
                if let Ok(v) = Validator::new(SIGNATURE_SCHEMA) {
                    for e in v.validate(sig) {
                        self.report.push(
                            Severity::Error,
                            Code::SchemaInvalid,
                            None,
                            None,
                            Some(SIGNATURE_NAME),
                            e.to_string(),
                        );
                    }
                }
                let st = signature::verify_chain(sig, &self.manifest.bytes);
                match &st {
                    SignatureState::Valid => self.report.push(
                        Severity::Info,
                        Code::SignatureValid,
                        None,
                        None,
                        None,
                        format!(
                            "signature chain verifies: {} link(s)",
                            sig.get("chain").and_then(Value::as_array).map_or(0, Vec::len)
                        ),
                    ),
                    SignatureState::Invalid(r) => self.report.push(
                        Severity::Error,
                        Code::SignatureInvalid,
                        None,
                        None,
                        None,
                        r.clone(),
                    ),
                    SignatureState::Absent => {}
                }
                st
            }
        };

        // 4. Node views.
        let mut states = Vec::new();
        for r in self.manifest.nodes() {
            match r {
                Err((i, msg)) => {
                    self.report.push(Severity::Error, Code::NodeDead, None, None, None, msg.clone());
                    let _ = i;
                }
                Ok(view) => {
                    let mut status = NodeStatus::Alive;
                    if let Some(errs) = node_schema_errors.get(&view.index) {
                        status = NodeStatus::Dead(format!(
                            "fails the manifest schema: {}",
                            errs.join("; ")
                        ));
                    } else if !KNOWN_TYPES.contains(&view.ntype.as_str()) {
                        status = NodeStatus::Skipped(format!(
                            "node type `{}` is not one this reader interprets",
                            view.ntype
                        ));
                    }
                    states.push(NodeState { view, status, resolved: None });
                }
            }
        }
        self.nodes = states;

        // 5. Resolve + verify each node's version.
        let n = self.nodes.len();
        for i in 0..n {
            let (resolved, entries, dead) = self.resolve_node(i);
            for e in entries {
                self.report.entries.push(e);
            }
            self.nodes[i].resolved = resolved;
            if let Some(reason) = dead {
                self.nodes[i].status = NodeStatus::Dead(reason);
            }
        }

        // 6. Dispatch by type (JSON schema / envelope), and the loader safety rule.
        if self.opts.interpret {
            self.interpret_payloads();
        }

        // 7. Law 5: is the derived data stale?
        if self.opts.check_derived {
            self.check_derived();
        }

        // 8. Edges (SPEC section 10 step 10). `requires` into a dead node, or
        //    to a node absent from nodes[], kills the source, transitively;
        //    `enhances` into a dead or absent node costs exactly one feature.
        self.propagate_edges();

        // 8a. A core node that says an extension changes how it is shown, and
        //     an extension this reader skipped or lost (SPEC.md section 3.20).
        self.check_modified_by();

        // 9. "Nothing floats."
        self.check_floating();

        for i in 0..self.nodes.len() {
            let st = self.nodes[i].status.clone();
            let id = self.nodes[i].view.node_id.clone();
            match st {
                NodeStatus::Dead(r) => self.report.push(
                    Severity::Error,
                    Code::NodeDead,
                    Some(&id),
                    None,
                    None,
                    r,
                ),
                NodeStatus::Skipped(r) => self.report.push(
                    Severity::Warn,
                    Code::NodeSkippedUnknownType,
                    Some(&id),
                    None,
                    None,
                    r,
                ),
                NodeStatus::Alive => {}
            }
        }
    }

    #[allow(clippy::type_complexity)]
    fn resolve_node(
        &self,
        i: usize,
    ) -> (Option<i64>, Vec<crate::report::ReportEntry>, Option<String>) {
        let node = &self.nodes[i];
        let id = node.view.node_id.clone();
        let mut out = Vec::new();
        if node.status.is_dead() {
            return (None, out, None);
        }

        let mut candidates: Vec<&crate::manifest::VersionView> = node
            .view
            .versions
            .iter()
            .filter(|v| v.v <= node.view.active)
            .collect();
        candidates.sort_by_key(|v| -v.v);

        if node.view.version(node.view.active).is_none() {
            out.push(entry(
                Severity::Warn,
                Code::VersionFallback,
                Some(&id),
                Some(node.view.active),
                None,
                format!("`active` names version {} which does not exist", node.view.active),
            ));
        }

        let mut failures = Vec::new();
        for cand in candidates {
            if cand.compacted {
                failures.push(format!("v{} was compacted: the record stays, the bytes went", cand.v));
                continue;
            }
            let mut problems = Vec::new();
            for f in &cand.files {
                match self.blob(&f.path) {
                    // A refusal is reported under ITS name. Before ruling 9 of
                    // 2026-10-13 every one of these was `file-missing`, so a
                    // deflated entry was "refused by name" under the wrong
                    // name and `zip-entry-unsupported` was a code this crate
                    // defined and never emitted.
                    Err(Error::UnsupportedEntry(m)) => problems.push(entry(
                        Severity::Error,
                        Code::ZipEntryUnsupported,
                        Some(&id),
                        Some(cand.v),
                        Some(&f.path),
                        m,
                    )),
                    Err(Error::BadEntry(m)) => problems.push(entry(
                        Severity::Error,
                        Code::ZipEntryInvalid,
                        Some(&id),
                        Some(cand.v),
                        Some(&f.path),
                        m,
                    )),
                    Err(_) => problems.push(entry(
                        Severity::Error,
                        Code::FileMissing,
                        Some(&id),
                        Some(cand.v),
                        Some(&f.path),
                        "declared in files[] but not in the container",
                    )),
                    Ok(bytes) => {
                        if bytes.len() as u64 != f.size {
                            problems.push(entry(
                                Severity::Error,
                                Code::SizeMismatch,
                                Some(&id),
                                Some(cand.v),
                                Some(&f.path),
                                format!("declared {} bytes, found {}", f.size, bytes.len()),
                            ));
                        }
                        if self.opts.verify {
                            let got = sha256_hex(&bytes);
                            if got != f.sha256 {
                                problems.push(entry(
                                    Severity::Error,
                                    Code::HashMismatch,
                                    Some(&id),
                                    Some(cand.v),
                                    Some(&f.path),
                                    format!("declared sha256 {} but the bytes hash to {got}", f.sha256),
                                ));
                            }
                        }
                    }
                }
            }
            if problems.is_empty() {
                if cand.v != node.view.active {
                    out.push(entry(
                        Severity::Warn,
                        Code::VersionFallback,
                        Some(&id),
                        Some(cand.v),
                        None,
                        format!(
                            "active v{} is unusable; fell back to v{} — {}",
                            node.view.active, cand.v, cand.note
                        ),
                    ));
                }
                out.extend(failures_to_entries(&id, &failures));
                return (Some(cand.v), out, None);
            }
            out.extend(problems);
            failures.push(format!("v{} failed verification", cand.v));
        }
        out.extend(failures_to_entries(&id, &failures));
        (
            None,
            out,
            Some(format!(
                "no usable version: {}",
                if failures.is_empty() { "no version at or below `active`".into() } else { failures.join("; ") }
            )),
        )
    }

    // -----------------------------------------------------------------
    // The manifest's own schema, and the package's own specification
    // -----------------------------------------------------------------

    /// Validate the manifest against one schema text and report every finding
    /// at `severity`. `kills` collects the findings under `/nodes/<i>`, which
    /// quarantine that node. `lenient` is for a schema this crate did not ship:
    /// the keywords it uses that this validator does not implement are
    /// returned (once) instead of being reported at every instance.
    fn run_schema(
        &mut self,
        text: &str,
        lenient: bool,
        severity: Severity,
        prefix: &str,
        mut kills: Option<&mut BTreeMap<usize, Vec<String>>>,
    ) -> std::result::Result<Vec<String>, String> {
        let v = Validator::new(text)?;
        let v = if lenient { v.lenient() } else { v };
        let unknown = if lenient { v.unknown_keywords() } else { Vec::new() };
        for e in v.validate(&self.manifest.raw) {
            if let Some(k) = kills.as_deref_mut() {
                if let Some(i) = node_index_of(&e.instance_path) {
                    k.entry(i).or_default().push(e.to_string());
                }
            }
            self.report.push(severity, Code::SchemaInvalid, None, None, None, format!("{prefix}{e}"));
        }
        Ok(unknown)
    }

    /// One file of the package's own specification, by path. It must be
    /// declared by a node of type `core.spec` — which is what puts it under
    /// `spec_sha256` — be in the container, and be the bytes the manifest
    /// hashes. `Err` says which of those failed. Returns the bytes, the
    /// declared sha256 and the declaring node's id.
    fn spec_file(&self, path: &str) -> std::result::Result<(Rc<Vec<u8>>, String, String), String> {
        match self.file_index.get(path) {
            None => Err("no node of this manifest declares that path".into()),
            Some((_, node, ntype)) if ntype != "core.spec" => Err(format!(
                "it is declared by node `{node}` of type `{ntype}`, not by a `core.spec` node, \
                 so it is not part of the specification `spec_sha256` covers"
            )),
            Some((sha, node, _)) => {
                let bytes = self.blob(path).map_err(|_| {
                    format!("node `{node}` declares it, but it is not in the container")
                })?;
                if self.opts.verify && sha256_hex(&bytes) != *sha {
                    return Err(format!(
                        "its bytes do not hash to the sha256 node `{node}` declares for it"
                    ));
                }
                Ok((bytes, sha.clone(), node.clone()))
            }
        }
    }

    fn note_unknown_keywords(&mut self, path: &str, unknown: Vec<String>) {
        if unknown.is_empty() {
            return;
        }
        self.report.push(
            Severity::Warn,
            Code::ManifestSchemaUnusable,
            None,
            None,
            Some(path),
            format!(
                "the package's manifest schema uses {} keyword(s) this validator does not \
                 implement ({}); the constraints they express were NOT checked, everything \
                 else in the schema was",
                unknown.len(),
                unknown.join(", ")
            ),
        );
    }

    /// SPEC.md section 2.2. Which schema validates this manifest is decided by
    /// the package (`manifest_schema`, a path INSIDE the package), not by a
    /// table in this build — the PROFILE-IMAGE precedent, made the general
    /// rule by ruling 2 of 2026-10-13. What that does and does not establish
    /// is section 10.3 and is said in the report, not left to be assumed.
    fn validate_against_profile_schema(
        &mut self,
        kills: &mut BTreeMap<usize, Vec<String>>,
    ) -> ManifestValidation {
        let profile = self.manifest.profile().to_string();
        let builtin = self.manifest.schema_source();
        let path = self.manifest.manifest_schema_path();
        let embedded = path.as_deref().map(|p| self.spec_file(p));

        // ---- a profile this build has built in --------------------------
        if let Some(own) = builtin {
            let path = path.unwrap_or_default();
            match embedded {
                Some(Ok((bytes, sha, _))) if bytes.as_slice() != own.as_bytes() => {
                    let text = String::from_utf8_lossy(&bytes).into_owned();
                    match self.run_schema(&text, true, Severity::Error, "", Some(kills)) {
                        Ok(unknown) => {
                            self.note_unknown_keywords(&path, unknown);
                            self.report.push(
                                Severity::Info,
                                Code::ManifestSchemaRevision,
                                None,
                                None,
                                Some(&path),
                                format!(
                                    "this package carries another revision of the `{profile}` \
                                     manifest schema (sha256 {sha}) than this build (sha256 {}). \
                                     The manifest was validated against the PACKAGE'S copy, which \
                                     is the authority for its own contents; anything this build's \
                                     revision would say differently follows as a warning",
                                    sha256_hex(own.as_bytes())
                                ),
                            );
                            // The proof of additive evolution, run on every
                            // open: a package written under an EARLIER revision
                            // must also satisfy this one (law 12), so on such a
                            // package this pass is silent. On a package written
                            // under a LATER revision it names what this build
                            // does not know yet — as warnings, never as errors.
                            let _ = self.run_schema(
                                own,
                                false,
                                Severity::Warn,
                                "by this build's revision of the schema (the package's own \
                                 revision is the authority): ",
                                None,
                            );
                            return ManifestValidation::PackageRevision;
                        }
                        Err(e) => self.report.push(
                            Severity::Warn,
                            Code::ManifestSchemaUnusable,
                            None,
                            None,
                            Some(&path),
                            format!(
                                "the package's copy of its manifest schema is not usable ({e}); \
                                 the manifest was validated against this build's copy instead"
                            ),
                        ),
                    }
                }
                Some(Err(why)) => self.report.push(
                    Severity::Warn,
                    Code::ManifestSchemaUnusable,
                    None,
                    None,
                    Some(&path),
                    format!(
                        "the manifest's schema is `{path}`, but {why}. The manifest was \
                         validated against this build's copy; the package does not carry the \
                         schema it is written against (law 2)"
                    ),
                ),
                _ => {}
            }
            if let Err(e) = self.run_schema(own, false, Severity::Error, "", Some(kills)) {
                self.report.push(
                    Severity::Error,
                    Code::SchemaInvalid,
                    None,
                    None,
                    None,
                    format!("the embedded manifest schema itself is unusable: {e}"),
                );
            }
            return ManifestValidation::BuiltIn;
        }

        // ---- any other profile -----------------------------------------
        let mut validated: Option<(String, String, String)> = None;
        match (path, embedded) {
            (Some(p), Some(Ok((bytes, sha, node)))) => {
                let text = String::from_utf8_lossy(&bytes).into_owned();
                match self.run_schema(&text, true, Severity::Error, "", Some(kills)) {
                    Ok(unknown) => {
                        self.note_unknown_keywords(&p, unknown);
                        validated = Some((p, sha, node));
                    }
                    Err(e) => self.report.push(
                        Severity::Error,
                        Code::ManifestSchemaUnusable,
                        None,
                        None,
                        Some(&p),
                        format!(
                            "the manifest names `{p}` as the schema that validates it, and that \
                             file is not a usable schema ({e}). Only the base shape was checked"
                        ),
                    ),
                }
            }
            (Some(p), Some(Err(why))) => self.report.push(
                Severity::Error,
                Code::ManifestSchemaUnusable,
                None,
                None,
                Some(&p),
                format!(
                    "the manifest names `{p}` as the schema that validates it, but {why}. Only \
                     the base shape was checked"
                ),
            ),
            _ => self.report.push(
                Severity::Error,
                Code::ManifestSchemaUnusable,
                None,
                None,
                None,
                format!(
                    "profile `{profile}` is not built into this reader and the manifest names \
                     no `manifest_schema`. A profile other than the two reference profiles MUST \
                     name the schema that validates it, inside the package (SPEC.md section \
                     2.2). Only the base shape was checked"
                ),
            ),
        }

        // One entry, severity warn: an admission about this reader, not a
        // complaint about the package (S-25).
        let own_conventions = self.manifest.profile_convention_keys();
        let conventions = if own_conventions.is_empty() {
            "the profile declares none of its own".to_string()
        } else {
            format!(
                "the profile's own {} ({}) govern payload meaning and were NOT interpreted",
                own_conventions.len(),
                own_conventions.join(", ")
            )
        };
        let (validation, what) = match &validated {
            Some((p, sha, node)) => (
                ManifestValidation::PackageOwn,
                format!(
                    "Its manifest was validated against the PACKAGE'S OWN schema `{p}` (sha256 \
                     {sha}; a file of node `{node}`, bytes verified, covered by spec_sha256) and \
                     against this reader's built-in base schema. That establishes that this is a \
                     well-formed werk manifest and that it is consistent with the schema the \
                     package ships. It does NOT establish that the schema is the one the \
                     profile's author published — a package can ship any schema — and it says \
                     nothing about what the payloads mean"
                ),
            ),
            None => (
                ManifestValidation::BaseOnly,
                "Its manifest was validated against this reader's built-in base schema ONLY, \
                 because no profile schema could be used (see the manifest-schema-unusable entry)"
                    .to_string(),
            ),
        };
        self.report.push(
            Severity::Warn,
            Code::UnsupportedProfile,
            None,
            None,
            None,
            format!(
                "profile `{profile}` is not built into this reader. {what}. Conventions: the six \
                 base conventions were checked against this reader; {conventions}. Node types \
                 this reader does not know are skipped and reported; every file is still \
                 listed, hash-verified and extractable"
            ),
        );
        validation
    }

    /// SPEC.md section 2: `spec_sha256` is one sha256 over every file under
    /// `spec/` that the manifest declares — path, 0x0A, the file's sha256 as 32
    /// raw bytes, 0x0A, in ascending byte order of the path. Recomputed here
    /// from the manifest's own declarations: whether the BYTES match those
    /// declarations is the per-file hash's job, and this answers the other
    /// half — whether the manifest's summary of its specification is the
    /// summary of the specification it lists.
    fn check_spec_sha256(&mut self) {
        let declared = match self.manifest.spec_sha256() {
            Some(d) => d.to_string(),
            None => return, // the schema has already said it is missing
        };
        let mut acc: Vec<u8> = Vec::new();
        let mut count = 0usize;
        // BTreeMap<String, _> iterates in byte order of the UTF-8 key, which
        // is exactly the order the algorithm asks for.
        for (path, (sha, _, _)) in &self.file_index {
            if !path.starts_with("spec/") {
                continue;
            }
            match crate::hashing::from_hex(sha) {
                Some(raw) if raw.len() == 32 => {
                    acc.extend_from_slice(path.as_bytes());
                    acc.push(b'\n');
                    acc.extend_from_slice(&raw);
                    acc.push(b'\n');
                    count += 1;
                }
                _ => return, // a malformed sha256 is the schema's finding
            }
        }
        let got = sha256_hex(&acc);
        if got != declared {
            self.report.push(
                Severity::Error,
                Code::SpecSha256Mismatch,
                None,
                None,
                None,
                format!(
                    "the manifest declares spec_sha256 {declared}, but the {count} file(s) under \
                     spec/ that it lists digest to {got}: the manifest's statement of which \
                     specification it carries is not true of the specification it lists"
                ),
            );
        }
    }

    // -----------------------------------------------------------------
    // Format definitions (SPEC.md section 3.18)
    // -----------------------------------------------------------------

    /// Where each format id's definition document is, and the documents that
    /// could be read. The manifest's `formats` map is the authority; a package
    /// written for a reference profile before its schema admitted that key
    /// carries the same map on a node, as `meta.format_definitions`, and a
    /// reader looks there second.
    fn load_format_definitions(
        &self,
        pending: &mut Vec<Pending>,
    ) -> (BTreeMap<String, String>, BTreeMap<String, formats::Definition>) {
        let mut paths: BTreeMap<String, String> = BTreeMap::new();
        for n in &self.nodes {
            let legacy = n
                .view
                .meta
                .as_ref()
                .and_then(|m| m.get("format_definitions"))
                .and_then(Value::as_object);
            if let Some(map) = legacy {
                for (id, p) in map {
                    if let Some(p) = p.as_str() {
                        paths.insert(id.clone(), p.to_string());
                    }
                }
            }
        }
        for (id, p) in self.manifest.formats_map() {
            paths.insert(id, p);
        }

        let mut defs = BTreeMap::new();
        for (id, path) in &paths {
            let parsed = self
                .spec_file(path)
                .and_then(|(bytes, _, _)| formats::parse(&bytes, id));
            let def = match parsed {
                Ok(d) => d,
                Err(why) => {
                    pending.push((
                        None,
                        Severity::Warn,
                        Code::FormatDefinitionInvalid,
                        Some(path.clone()),
                        format!("format `{id}`: {why}"),
                        false,
                    ));
                    continue;
                }
            };
            // The two ways a test vector's input is carried (SPEC 3.18): a
            // printed hex block, checked by `formats::parse`, or a DECLARED
            // vector file, checked here because only the manifest knows it.
            for vf in &def.vector_files {
                let ok = matches!(
                    self.file_index.get(&vf.path),
                    Some((sha, _, ntype)) if *sha == vf.sha256 && ntype == "core.spec"
                );
                if !ok {
                    pending.push((
                        None,
                        Severity::Warn,
                        Code::FormatDefinitionInvalid,
                        Some(path.clone()),
                        format!(
                            "format `{id}`: its definition declares the vector file `{}` \
                             (sha256 {}), which is not a file of a `core.spec` node of this \
                             package with that sha256",
                            vf.path, vf.sha256
                        ),
                        false,
                    ));
                }
            }
            for v in &def.vectors {
                if let Some(f) = &v.input_file {
                    let ok =
                        matches!(self.file_index.get(f), Some((sha, _, _)) if *sha == v.input_sha256);
                    if !ok {
                        pending.push((
                            None,
                            Severity::Warn,
                            Code::FormatDefinitionInvalid,
                            Some(path.clone()),
                            format!(
                                "format `{id}`: test vector `{}` takes its input from `{f}`, \
                                 which this package does not declare with sha256 {}",
                                v.id, v.input_sha256
                            ),
                            false,
                        ));
                    }
                }
            }
            defs.insert(id.clone(), def);
        }
        for def in defs.values() {
            for r in &def.requires {
                if !paths.contains_key(r) {
                    pending.push((
                        None,
                        Severity::Warn,
                        Code::FormatUndeclared,
                        None,
                        format!(
                            "format `{}` builds on format `{r}` (`requires`), and this package's \
                             `formats` map does not list `{r}`: a definition that points at \
                             another must find it inside the package",
                            def.format_id
                        ),
                        false,
                    ));
                }
            }
        }
        (paths, defs)
    }

    fn interpret_payloads(&mut self) {
        let schemas: BTreeMap<String, String> = self.manifest.schemas_map().into_iter().collect();
        let layouts: BTreeMap<String, String> = self.manifest.layouts_map().into_iter().collect();
        let mut pending: Vec<Pending> = Vec::new();
        let mut envelopes_ok = 0usize;
        let mut payloads_ok = 0usize;

        let (format_paths, definitions) = self.load_format_definitions(&mut pending);
        self.formats_read = definitions.len();
        self.format_vectors_checked = definitions
            .values()
            .map(|d| d.vectors.iter().filter(|v| v.input_file.is_none()).count())
            .sum();

        for (i, node) in self.nodes.iter().enumerate() {
            let v = match node.resolved.and_then(|v| node.view.version(v)) {
                Some(v) => v,
                None => continue,
            };
            if node.status.is_dead() {
                continue;
            }
            // SPEC 7.1: a prebuilt loader is inert data. Say that we did not run it.
            if node.view.ntype == "core.loader"
                && node.view.meta.as_ref().and_then(|m| m.get("form")).and_then(Value::as_str)
                    == Some("prebuilt")
            {
                pending.push((
                    Some(i),
                    Severity::Info,
                    Code::PrebuiltNotExecuted,
                    None,
                    "prebuilt loader binary treated as inert data; it was not executed, loaded or linked"
                        .into(),
                    false,
                ));
            }
            let unknown_type = matches!(node.status, NodeStatus::Skipped(_));
            let payload_path = payload_path_of(&node.view.ntype, v);

            // Which of this node's files are DECLARED to be in a defined
            // foreign format (SPEC.md section 3.18). A declaration beats a
            // sniff: such a file is neither an envelope nor a JSON payload,
            // whatever its first bytes happen to be.
            let meta = node.view.meta.as_ref();
            let mut declared: BTreeMap<String, String> = BTreeMap::new();
            let mut named: Vec<String> = Vec::new();
            if let Some(id) = meta.and_then(|m| m.get("payload_format")).and_then(Value::as_str) {
                named.push(id.to_string());
                if let Some(p) = &payload_path {
                    declared.insert(p.clone(), id.to_string());
                }
            }
            if let Some(map) = meta.and_then(|m| m.get("file_formats")).and_then(Value::as_object) {
                for (role, id) in map {
                    if let Some(id) = id.as_str() {
                        named.push(id.to_string());
                        for f in v.files.iter().filter(|f| f.role.as_deref() == Some(role.as_str())) {
                            declared.insert(f.path.clone(), id.to_string());
                        }
                    }
                }
            }
            if let Some(list) = meta.and_then(|m| m.get("contained_formats")).and_then(Value::as_array) {
                named.extend(list.iter().filter_map(Value::as_str).map(str::to_string));
            }
            named.sort();
            named.dedup();
            for id in &named {
                if !format_paths.contains_key(id) {
                    pending.push((
                        Some(i),
                        Severity::Warn,
                        Code::FormatUndeclared,
                        None,
                        format!(
                            "this node names format `{id}`, and the package's `formats` map has \
                             no definition for it: the bytes are carried and verified, but the \
                             package does not say how to decode them (law 2)"
                        ),
                        false,
                    ));
                }
            }

            for f in &v.files {
                let bytes = match self.blob(&f.path) {
                    Ok(b) => b,
                    Err(_) => continue,
                };
                if let Some(id) = declared.get(&f.path) {
                    if let Some(def) = definitions.get(id) {
                        if let formats::SniffVerdict::Mismatch(why) = formats::sniff(def, &bytes) {
                            pending.push((
                                Some(i),
                                Severity::Warn,
                                Code::FormatMismatch,
                                Some(f.path.clone()),
                                format!("declared as format `{id}`: {why}"),
                                false,
                            ));
                        }
                    }
                    continue;
                }
                // Custom binary? An envelope is recognised by its FRAME — `WK`
                // and two of A-Z / 0-9 — never by a table of the magics this
                // build happens to know, so a profile-defined or newer
                // envelope is validated structurally instead of being silently
                // passed over (ruling 4 of 2026-10-13).
                if bytes.len() >= 4 && envelope::is_envelope_magic(&[bytes[0], bytes[1], bytes[2], bytes[3]])
                {
                    match envelope::parse(&bytes).and_then(|e| envelope::check_finite(&e, &bytes).map(|_| e)) {
                        Ok(env) => {
                            // The universal grammar passed. Now the per-magic
                            // layout file's own rules, which the envelope
                            // cannot know: section names and counts for a
                            // WKGS, the fields/sections pairing for a WKPC.
                            // Kept in two severities on purpose — a structural
                            // failure kills the node, a producer's slip is a
                            // warning and the payload still loads (law 3).
                            let structural = match &env.magic {
                                b"WKGS" => crate::geom::check_gsplat(&env).err(),
                                b"WKPC" => crate::geom::check_points(&env).err(),
                                _ => None,
                            };
                            if let Some(msg) = structural {
                                pending.push((
                                    Some(i),
                                    Severity::Error,
                                    Code::EnvelopeInvalid,
                                    Some(f.path.clone()),
                                    msg,
                                    true,
                                ));
                            } else {
                                envelopes_ok += 1;
                                let warns = match &env.magic {
                                    b"WKGS" => crate::geom::warnings_gsplat(&env, &bytes),
                                    b"WKPC" => crate::geom::warnings_points(&env),
                                    _ => Vec::new(),
                                };
                                for w in warns {
                                    pending.push((
                                        Some(i),
                                        Severity::Warn,
                                        Code::EnvelopeInvalid,
                                        Some(f.path.clone()),
                                        w,
                                        false,
                                    ));
                                }
                                // Which grammar describes it: the header's
                                // `kind`, through the package's `layouts` map.
                                // A worked example inside `core.spec` is
                                // exempt — it illustrates another node type
                                // and its grammar is the layout file beside it.
                                if node.view.ntype != "core.spec" {
                                    let kind = env.kind().unwrap_or("").to_string();
                                    let magic = String::from_utf8_lossy(&env.magic).into_owned();
                                    if kind != node.view.ntype {
                                        pending.push((
                                            Some(i),
                                            Severity::Warn,
                                            Code::EnvelopeInvalid,
                                            Some(f.path.clone()),
                                            format!(
                                                "the {magic} envelope's header `kind` is `{kind}` but \
                                                 its node's type is `{}`: outside a core.spec node an \
                                                 envelope's kind is its node's type \
                                                 (ENVELOPE.layout.txt section 2)",
                                                node.view.ntype
                                            ),
                                            false,
                                        ));
                                    }
                                    let grammar = layouts.get(&kind);
                                    let carried = grammar.map_or(false, |p| {
                                        matches!(self.file_index.get(p), Some((_, _, t)) if t == "core.spec")
                                    });
                                    if !carried {
                                        pending.push((
                                            Some(i),
                                            Severity::Warn,
                                            Code::EnvelopeUndeclared,
                                            Some(f.path.clone()),
                                            match grammar {
                                                None => format!(
                                                    "a well-formed {magic} envelope of kind `{kind}` \
                                                     ({} section(s)), but this package's `layouts` map \
                                                     names no grammar for `{kind}`: the frame was \
                                                     validated, the contents are not described by the \
                                                     package (law 2)",
                                                    env.sections.len()
                                                ),
                                                Some(p) => format!(
                                                    "a well-formed {magic} envelope of kind `{kind}`; \
                                                     `layouts` names `{p}` as its grammar, and no \
                                                     core.spec node of this package declares that file"
                                                ),
                                            },
                                            false,
                                        ));
                                    }
                                }
                            }
                        }
                        Err(msg) => pending.push((
                            Some(i),
                            Severity::Error,
                            Code::EnvelopeInvalid,
                            Some(f.path.clone()),
                            msg,
                            true,
                        )),
                    }
                    continue;
                }
                // JSON payload with a schema the manifest points at. For a type
                // this build interprets, every .json file of the version, as
                // before. For a type it does NOT interpret (a profile-defined
                // or extension type) only THE payload file, resolved by SPEC
                // 2.1 — validating a payload against the schema its own
                // package ships is structure, not meaning, and it is what
                // catches a payload that was damaged and re-hashed.
                let candidate = if unknown_type {
                    payload_path.as_deref() == Some(f.path.as_str()) && f.path.ends_with(".json")
                } else {
                    f.path.ends_with(".json")
                };
                if !candidate {
                    continue;
                }
                if let Some(sp) = schemas.get(&node.view.ntype) {
                    match self.blob(sp) {
                        Err(_) => pending.push((
                            Some(i),
                            Severity::Warn,
                            Code::PayloadSchemaInvalid,
                            Some(f.path.clone()),
                            format!("the manifest points at schema `{sp}`, which is not in the package"),
                            false,
                        )),
                        Ok(schema_bytes) => {
                            let text = String::from_utf8_lossy(&schema_bytes).into_owned();
                            let validator = Validator::new(&text).map(|v| if unknown_type { v.lenient() } else { v });
                            match (validator, serde_json::from_slice::<Value>(&bytes)) {
                                (Ok(val), Ok(inst)) => {
                                    payloads_ok += 1;
                                    for e in val.validate(&inst) {
                                        pending.push((
                                            Some(i),
                                            Severity::Error,
                                            Code::PayloadSchemaInvalid,
                                            Some(f.path.clone()),
                                            e.to_string(),
                                            true,
                                        ));
                                    }
                                }
                                (_, Err(e)) => pending.push((
                                    Some(i),
                                    Severity::Error,
                                    Code::PayloadSchemaInvalid,
                                    Some(f.path.clone()),
                                    format!("payload is not valid JSON: {e}"),
                                    true,
                                )),
                                (Err(e), _) => pending.push((
                                    Some(i),
                                    Severity::Warn,
                                    Code::PayloadSchemaInvalid,
                                    Some(f.path.clone()),
                                    format!("schema `{sp}` is unusable: {e}"),
                                    false,
                                )),
                            }
                        }
                    }
                }
            }
        }

        self.envelopes_validated = envelopes_ok;
        self.payloads_validated = payloads_ok;
        for (i, sev, code, path, msg, kills) in pending {
            match i {
                Some(i) => {
                    let id = self.nodes[i].view.node_id.clone();
                    self.report.push(sev, code, Some(&id), self.nodes[i].resolved, path.as_deref(), msg.clone());
                    if kills && !self.nodes[i].status.is_dead() {
                        self.nodes[i].status = NodeStatus::Dead(msg);
                    }
                }
                None => self.report.push(sev, code, None, None, path.as_deref(), msg),
            }
        }
    }

    /// SPEC.md section 3.20: a core node may declare, in `meta.modified_by`,
    /// the nodes whose state changes how ITS payload is shown by the
    /// application that wrote it — an edit layer, a recolouring, a deformer
    /// kept in an extension. A reader that skips or loses one of those nodes
    /// is then showing something its author did not see, and says so; before
    /// this rule it lost the content silently, which is the one thing law 3's
    /// "loses one feature" never meant.
    fn check_modified_by(&mut self) {
        let status: BTreeMap<String, NodeStatus> =
            self.nodes.iter().map(|n| (n.view.node_id.clone(), n.status.clone())).collect();
        let mut out = Vec::new();
        for n in &self.nodes {
            let list = match n.view.meta.as_ref().and_then(|m| m.get("modified_by")).and_then(Value::as_array) {
                Some(l) => l,
                None => continue,
            };
            for target in list.iter().filter_map(Value::as_str) {
                match status.get(target) {
                    None => out.push((
                        Code::EdgeDangling,
                        n.view.node_id.clone(),
                        format!("meta.modified_by names `{target}`, which is not a node in this manifest"),
                    )),
                    Some(NodeStatus::Alive) => {}
                    Some(other) => out.push((
                        Code::ModifiedBySkippedNode,
                        n.view.node_id.clone(),
                        format!(
                            "this node declares that node `{target}` changes how its payload is \
                             shown, and this reader {} `{target}`: what is read from this node is \
                             its unmodified payload, not what its author saw",
                            if other.is_dead() { "lost" } else { "skipped" }
                        ),
                    )),
                }
            }
        }
        for (code, id, msg) in out {
            self.report.push(Severity::Warn, code, Some(&id), None, None, msg);
        }
    }

    fn check_derived(&mut self) {
        let paths = self.declared_paths();
        let mut pending = Vec::new();
        for node in &self.nodes {
            for ver in &node.view.versions {
                let declared = match &ver.input_hash {
                    Some(h) => h,
                    None => continue,
                };
                if ver.input_files.is_empty() {
                    continue;
                }
                let mut digests = Vec::new();
                let mut missing = None;
                for p in &ver.input_files {
                    match paths.get(p).and_then(|h| crate::hashing::from_hex(h)) {
                        Some(d) if d.len() == 32 => {
                            let mut a = [0u8; 32];
                            a.copy_from_slice(&d);
                            digests.push(a);
                        }
                        _ => {
                            missing = Some(p.clone());
                            break;
                        }
                    }
                }
                if let Some(p) = missing {
                    pending.push((
                        node.view.node_id.clone(),
                        ver.v,
                        format!("input_files names `{p}`, which no node version declares"),
                    ));
                    continue;
                }
                let params = self
                    .manifest
                    .raw
                    .pointer(&format!("/nodes/{}/versions", node.view.index))
                    .and_then(Value::as_array)
                    .and_then(|a| a.iter().find(|x| x.get("v").and_then(Value::as_i64) == Some(ver.v)))
                    .and_then(|x| x.get("input_params"))
                    .cloned()
                    .unwrap_or_else(|| json!({}));
                let got = crate::hashing::input_hash(&digests, &canonical_json(&params));
                if &got != declared {
                    pending.push((
                        node.view.node_id.clone(),
                        ver.v,
                        format!("declared input_hash {declared} but the declared inputs hash to {got}"),
                    ));
                }
            }
        }
        for (id, v, msg) in pending {
            self.report.push(Severity::Warn, Code::StaleDerivedData, Some(&id), Some(v), None, msg);
        }
    }

    fn propagate_edges(&mut self) {
        let index: BTreeMap<String, usize> = self
            .nodes
            .iter()
            .enumerate()
            .map(|(i, n)| (n.view.node_id.clone(), i))
            .collect();
        // SPEC section 5: a `requires` edge to a node that is not in nodes[]
        // kills the source exactly as one into a dead node does. One entry per
        // such edge, also on a node that is already dead for another reason,
        // so the manifest defect is never hidden behind a hash mismatch. The
        // node's files were already verified (step 6); only its status moves.
        let mut missing = Vec::new();
        for (i, n) in self.nodes.iter().enumerate() {
            for e in &n.view.edges {
                if e.kind == "requires" && !index.contains_key(&e.to) {
                    missing.push((i, e.to.clone()));
                }
            }
        }
        for (i, target) in missing {
            let id = self.nodes[i].view.node_id.clone();
            if !self.nodes[i].status.is_dead() {
                self.nodes[i].status = NodeStatus::Dead(format!(
                    "requires `{target}`, which is not a node in this manifest"
                ));
            }
            self.report.push(
                Severity::Error,
                Code::RequiresMissingNode,
                Some(&id),
                None,
                None,
                format!(
                    "a `requires` edge to `{target}`, which is not a node in this manifest, \
                     kills this node as a dead target would"
                ),
            );
        }
        loop {
            let mut changed = false;
            let mut kills = Vec::new();
            for (i, n) in self.nodes.iter().enumerate() {
                if n.status.is_dead() {
                    continue;
                }
                for e in &n.view.edges {
                    if e.kind != "requires" {
                        continue;
                    }
                    if let Some(&j) = index.get(&e.to) {
                        if self.nodes[j].status.is_dead() {
                            kills.push((i, e.to.clone()));
                        }
                    }
                }
            }
            for (i, target) in kills {
                if !self.nodes[i].status.is_dead() {
                    let id = self.nodes[i].view.node_id.clone();
                    self.nodes[i].status = NodeStatus::Dead(format!(
                        "requires `{target}`, which is dead"
                    ));
                    self.report.push(
                        Severity::Error,
                        Code::RequiresDeadNode,
                        Some(&id),
                        None,
                        None,
                        format!("a `requires` edge into dead node `{target}` kills this node too"),
                    );
                    changed = true;
                }
            }
            if !changed {
                break;
            }
        }
        let mut warns = Vec::new();
        for n in &self.nodes {
            for e in &n.view.edges {
                match index.get(&e.to) {
                    // A dangling `requires` edge was reported above as
                    // `requires-missing-node`; only `enhances` is a warning.
                    None if e.kind == "requires" => {}
                    None => warns.push((
                        Severity::Warn,
                        Code::EdgeDangling,
                        n.view.node_id.clone(),
                        format!("edge points at `{}`, which is not a node in this manifest", e.to),
                    )),
                    Some(&j) if self.nodes[j].status.is_dead() && e.kind == "enhances" => warns.push((
                        Severity::Warn,
                        Code::EnhancesDeadNode,
                        n.view.node_id.clone(),
                        format!(
                            "an `enhances` edge into dead node `{}` costs one feature and nothing else",
                            e.to
                        ),
                    )),
                    _ => {}
                }
            }
        }
        for (sev, code, id, msg) in warns {
            self.report.push(sev, code, Some(&id), None, None, msg);
        }
    }

    fn check_floating(&mut self) {
        let declared = self.declared_paths();
        let mut floating = Vec::new();
        for f in self.container_files() {
            if f == MANIFEST_NAME || f == SIGNATURE_NAME {
                continue;
            }
            if !declared.contains_key(&f) {
                floating.push(f);
            }
        }
        for f in floating {
            self.report.push(
                Severity::Warn,
                Code::FloatingFile,
                None,
                None,
                Some(&f),
                "in the container but reachable from no node version; \"nothing floats\" is broken",
            );
        }
    }

    // -----------------------------------------------------------------
    // Writing
    // -----------------------------------------------------------------

    /// The physical entry order: `container.entry_order` expanded against the
    /// declared file set, then anything left over in lexicographic order. It is
    /// a pure function of the manifest, which is what makes a rewrite
    /// byte-identical (ROADMAP Stage 2's gate).
    pub fn file_order(&self) -> Vec<String> {
        let mut remaining: BTreeSet<String> = self.declared_paths().keys().cloned().collect();
        remaining.insert(MANIFEST_NAME.to_string());
        if self.signature_raw.is_some() {
            remaining.insert(SIGNATURE_NAME.to_string());
        }
        let mut out = Vec::with_capacity(remaining.len());
        for pat in self.manifest.entry_order() {
            let picked: Vec<String> = if pat.ends_with('/') {
                remaining.iter().filter(|p| p.starts_with(&pat)).cloned().collect()
            } else {
                remaining.iter().filter(|p| **p == pat).cloned().collect()
            };
            for p in picked {
                remaining.remove(&p);
                out.push(p);
            }
        }
        out.extend(remaining);
        out
    }

    pub fn write_zip(&self, dest: impl AsRef<Path>) -> Result<Vec<u8>> {
        let mut entries = Vec::new();
        for p in self.file_order() {
            let bytes = if p == MANIFEST_NAME {
                self.manifest.bytes.clone()
            } else if p == SIGNATURE_NAME {
                match &self.signature_raw {
                    Some(_) => (*self.blob(SIGNATURE_NAME)?).clone(),
                    None => continue,
                }
            } else {
                (*self.blob(&p)?).clone()
            };
            entries.push((p, bytes));
        }
        let bytes = zipstore::write_zip(&entries);
        if let Some(parent) = dest.as_ref().parent() {
            std::fs::create_dir_all(parent)?;
        }
        std::fs::write(dest.as_ref(), &bytes)?;
        Ok(bytes)
    }

    pub fn materialize_dir(&self, dest: impl AsRef<Path>) -> Result<usize> {
        let dest = dest.as_ref();
        let mut n = 0;
        for p in self.file_order() {
            let bytes = if p == MANIFEST_NAME {
                self.manifest.bytes.clone()
            } else {
                match self.blob(&p) {
                    Ok(b) => (*b).clone(),
                    Err(_) => continue,
                }
            };
            let target = dest.join(&p);
            if let Some(parent) = target.parent() {
                std::fs::create_dir_all(parent)?;
            }
            std::fs::write(&target, &bytes)?;
            n += 1;
        }
        Ok(n)
    }

    // -----------------------------------------------------------------
    // Mutation — every one carries a mandatory work note (law 6)
    // -----------------------------------------------------------------

    pub fn add_node(&mut self, spec: NewNode) -> Result<()> {
        if self.nodes.iter().any(|n| n.view.node_id == spec.node_id) {
            return Err(Error::Rejected(format!("node `{}` already exists", spec.node_id)));
        }
        let version = self.build_version(1, &spec.version)?;
        let mut node = Map::new();
        node.insert("node_id".into(), json!(spec.node_id));
        node.insert("type".into(), json!(spec.ntype));
        if let Some(p) = &spec.part_id {
            node.insert("part_id".into(), json!(p));
        }
        if let Some(m) = &spec.material_id {
            node.insert("material_id".into(), json!(m));
        }
        node.insert("versions".into(), Value::Array(vec![version]));
        node.insert("active".into(), json!(1));
        node.insert("edges".into(), spec.edges.clone());
        if let Some(m) = &spec.meta {
            node.insert("meta".into(), m.clone());
        }
        self.stage(&spec.version);
        self.manifest
            .raw
            .get_mut("nodes")
            .and_then(Value::as_array_mut)
            .ok_or_else(|| Error::BadManifest("manifest has no nodes array".into()))?
            .push(Value::Object(node));
        self.reserialise();
        Ok(())
    }

    pub fn append_version(&mut self, node_id: &str, spec: NewVersion) -> Result<i64> {
        let idx = self
            .nodes
            .iter()
            .find(|n| n.view.node_id == node_id)
            .map(|n| n.view.index)
            .ok_or_else(|| Error::NoSuchItem(format!("no node `{node_id}`")))?;
        let next = {
            let arr = self
                .manifest
                .raw
                .pointer(&format!("/nodes/{idx}/versions"))
                .and_then(Value::as_array)
                .ok_or_else(|| Error::BadManifest("node has no versions array".into()))?;
            arr.iter().filter_map(|v| v.get("v").and_then(Value::as_i64)).max().unwrap_or(0) + 1
        };
        let version = self.build_version(next, &spec)?;
        self.stage(&spec);
        let node = self
            .manifest
            .raw
            .pointer_mut(&format!("/nodes/{idx}"))
            .ok_or_else(|| Error::BadManifest("node vanished".into()))?;
        node.get_mut("versions")
            .and_then(Value::as_array_mut)
            .ok_or_else(|| Error::BadManifest("node has no versions array".into()))?
            .push(version);
        node["active"] = json!(next);
        self.reserialise();
        Ok(next)
    }

    /// Put bytes into the package without declaring them yet. Used by the C
    /// ABI, where the payload arrives before the node description does.
    pub fn stage_blob(&mut self, path: &str, bytes: Vec<u8>) {
        self.overlay.insert(path.to_string(), bytes);
        self.cache.borrow_mut().remove(path);
    }

    /// Bytes for a path, staged or stored. `None` when the package has neither.
    pub fn peek(&self, path: &str) -> Option<Vec<u8>> {
        self.raw_read(path).ok()
    }

    fn stage(&mut self, spec: &NewVersion) {
        for f in &spec.files {
            self.overlay.insert(f.path.clone(), f.bytes.clone());
        }
    }

    fn build_version(&self, v: i64, spec: &NewVersion) -> Result<Value> {
        // Law 6: the note is not optional and "update" is not a note. The schema
        // says minLength 8; enforce it here so a bad write never reaches disk.
        if spec.note.trim().chars().count() < 8 {
            return Err(Error::Rejected(
                "a version needs a work note of at least 8 characters saying why it exists (law 6)"
                    .into(),
            ));
        }
        if spec.files.is_empty() {
            return Err(Error::Rejected("a version must own at least one file".into()));
        }
        let mut files = Vec::new();
        for f in &spec.files {
            let mut o = Map::new();
            o.insert("path".into(), json!(f.path));
            o.insert("sha256".into(), json!(sha256_hex(&f.bytes)));
            o.insert("size".into(), json!(f.bytes.len()));
            if let Some(m) = &f.media_type {
                o.insert("media_type".into(), json!(m));
            }
            if let Some(r) = &f.role {
                o.insert("role".into(), json!(r));
            }
            files.push(Value::Object(o));
        }
        let mut ver = Map::new();
        ver.insert("v".into(), json!(v));
        ver.insert("files".into(), Value::Array(files));
        ver.insert("note".into(), json!(spec.note));
        let mut producer = Map::new();
        producer.insert("tool".into(), json!(spec.producer_tool));
        producer.insert("version".into(), json!(spec.producer_version));
        if let Some(m) = &spec.producer_model {
            producer.insert("model".into(), json!(m));
        }
        ver.insert("producer".into(), Value::Object(producer));
        ver.insert("epistemic".into(), json!(spec.epistemic));
        ver.insert("created".into(), json!(spec.created));
        if v > 1 {
            ver.insert("supersedes".into(), json!(v - 1));
        }

        // Law 5, machine-enforced: derived data must say what it was derived
        // from, in order, and carry the hash of those inputs.
        if spec.epistemic == "measured" || spec.epistemic == "inferred" {
            if spec.input_files.is_empty() {
                return Err(Error::Rejected(format!(
                    "epistemic `{}` requires an ordered input_files list (law 5)",
                    spec.epistemic
                )));
            }
            let known = self.declared_paths();
            let mut digests = Vec::new();
            for p in &spec.input_files {
                let hex = match known.get(p) {
                    Some(h) => h.clone(),
                    None => match self.blob(p) {
                        Ok(b) => sha256_hex(&b),
                        Err(_) => {
                            return Err(Error::Rejected(format!(
                                "input file `{p}` is neither declared by a node nor in the package"
                            )))
                        }
                    },
                };
                let d = crate::hashing::from_hex(&hex)
                    .ok_or_else(|| Error::Rejected(format!("bad sha256 for input `{p}`")))?;
                let mut a = [0u8; 32];
                a.copy_from_slice(&d);
                digests.push(a);
            }
            let params = spec.input_params.clone().unwrap_or_else(|| json!({}));
            ver.insert("input_files".into(), json!(spec.input_files));
            ver.insert(
                "input_hash".into(),
                json!(crate::hashing::input_hash(&digests, &canonical_json(&params))),
            );
            ver.insert("input_params".into(), params);
        }
        Ok(Value::Object(ver))
    }

    fn reserialise(&mut self) {
        self.manifest.bytes = pretty_json(&self.manifest.raw);
        self.cache.borrow_mut().remove(MANIFEST_NAME);
        self.analyse();
    }

    // -----------------------------------------------------------------
    // Signing
    // -----------------------------------------------------------------

    pub fn sign(&mut self, secret_key_hex: &str, who: signature::Signer_) -> Result<()> {
        let sig = signature::append_entry(
            self.signature_raw.as_ref(),
            &self.manifest.bytes,
            secret_key_hex,
            &who,
        )?;
        self.set_signature(Some(sig));
        Ok(())
    }

    /// Deliberate, not a fallback: throw away the existing custody chain and
    /// anchor a new one to the current manifest.
    pub fn sign_new_chain(&mut self, secret_key_hex: &str, who: signature::Signer_) -> Result<()> {
        let sig = signature::append_entry(None, &self.manifest.bytes, secret_key_hex, &who)?;
        self.set_signature(Some(sig));
        Ok(())
    }

    /// Strip the chain. The package becomes anonymous — a legitimate state, and
    /// a visibly different one from "present and invalid".
    pub fn strip_signature(&mut self) {
        self.set_signature(None);
    }

    fn set_signature(&mut self, sig: Option<Value>) {
        match &sig {
            Some(v) => {
                self.signature_stripped = false;
                self.overlay.insert(SIGNATURE_NAME.into(), pretty_json(v));
            }
            None => {
                self.overlay.remove(SIGNATURE_NAME);
                self.signature_stripped = true;
            }
        }
        self.signature_raw = sig;
        self.cache.borrow_mut().remove(SIGNATURE_NAME);
        self.analyse();
    }

    /// Hash of MANIFEST.json exactly as it sits — never a reserialisation.
    pub fn manifest_sha256(&self) -> String {
        to_hex(&sha256(&self.manifest.bytes))
    }
}

// ---------------------------------------------------------------------------
// Mutation inputs
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
pub struct NewFile {
    pub path: String,
    pub bytes: Vec<u8>,
    pub media_type: Option<String>,
    pub role: Option<String>,
}

#[derive(Debug, Clone)]
pub struct NewVersion {
    pub files: Vec<NewFile>,
    pub note: String,
    pub producer_tool: String,
    pub producer_version: String,
    pub producer_model: Option<String>,
    pub epistemic: String,
    pub created: String,
    pub input_files: Vec<String>,
    pub input_params: Option<Value>,
}

#[derive(Debug, Clone)]
pub struct NewNode {
    pub node_id: String,
    pub ntype: String,
    pub part_id: Option<String>,
    pub material_id: Option<String>,
    pub meta: Option<Value>,
    pub edges: Value,
    pub version: NewVersion,
}

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

fn entry(
    severity: Severity,
    code: Code,
    node_id: Option<&str>,
    version: Option<i64>,
    path: Option<&str>,
    message: impl Into<String>,
) -> crate::report::ReportEntry {
    crate::report::ReportEntry {
        severity,
        code,
        node_id: node_id.map(str::to_string),
        version,
        path: path.map(str::to_string),
        message: message.into(),
    }
}

/// One finding queued while the nodes are borrowed: node index (None for a
/// package-level finding), severity, code, path, message, and whether it kills
/// the node.
type Pending = (Option<usize>, Severity, Code, Option<String>, String, bool);

/// SPEC.md section 2.1: the ONE payload file of a node version, by the ordered
/// rules — `payload_file`, a single file, the reserved role `payload`, the
/// type's documented payload role — or `None` when it is not
/// machine-determinable. Never `files[0]`.
fn payload_path_of(ntype: &str, v: &VersionView) -> Option<String> {
    if let Some(p) = &v.payload_file {
        if v.files.iter().any(|f| &f.path == p) {
            return Some(p.clone());
        }
    }
    if v.files.len() == 1 {
        return Some(v.files[0].path.clone());
    }
    let with_role = |role: &str| -> Option<String> {
        let mut hits = v.files.iter().filter(|f| f.role.as_deref() == Some(role));
        match (hits.next(), hits.next()) {
            (Some(f), None) => Some(f.path.clone()),
            _ => None,
        }
    };
    if let Some(p) = with_role("payload") {
        return Some(p);
    }
    let role = match ntype {
        "core.audio.effect" | "core.audio.ambience" => Some("best"),
        "core.imposter" => Some("atlas"),
        "core.recipe" => Some("record"),
        _ => None,
    };
    role.and_then(with_role)
}

fn failures_to_entries(_id: &str, _f: &[String]) -> Vec<crate::report::ReportEntry> {
    Vec::new()
}

fn node_index_of(pointer: &str) -> Option<usize> {
    let rest = pointer.strip_prefix("/nodes/")?;
    let head = rest.split('/').next()?;
    head.parse().ok()
}

fn read_source(source: &Source, path: &str) -> Result<Vec<u8>> {
    match source {
        Source::Dir(d) => {
            // Package-relative POSIX paths only; refuse anything that could
            // leave the package (the same rule the manifest schema's path
            // pattern enforces).
            if path.starts_with('/') || path.contains("..") || path.contains('\\') {
                return Err(Error::NoSuchItem(format!(
                    "`{path}` is not a package-relative path"
                )));
            }
            std::fs::read(d.join(path))
                .map_err(|_| Error::NoSuchItem(format!("no file `{path}` in this package")))
        }
        Source::Zip(z) => z.read(path),
    }
}

fn walk_dir(root: &Path) -> BTreeSet<String> {
    let mut out = BTreeSet::new();
    let mut stack = vec![root.to_path_buf()];
    while let Some(dir) = stack.pop() {
        let rd = match std::fs::read_dir(&dir) {
            Ok(r) => r,
            Err(_) => continue,
        };
        for e in rd.flatten() {
            let p = e.path();
            if p.is_dir() {
                stack.push(p);
            } else if let Ok(rel) = p.strip_prefix(root) {
                out.insert(rel.to_string_lossy().replace('\\', "/"));
            }
        }
    }
    out
}
