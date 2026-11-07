//! The load report.
//!
//! Manifesto law 3 and SPEC.md section 10 step 8: a damaged node, an unknown
//! node type and a node that is simply newer than this reader all degrade
//! through the SAME path — quarantine the node, say precisely what happened,
//! load everything else. So `open()` returns a package plus a report; it does
//! not return an error for damage. A reader that fails a load because one
//! texture is corrupt has thrown away the other ninety nodes.

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum Severity {
    /// Something worth stating, nothing lost.
    Info,
    /// A feature was lost but the package is usable.
    Warn,
    /// A node is unusable, or the package's own claims do not hold.
    Error,
}

impl Severity {
    pub fn as_str(&self) -> &'static str {
        match self {
            Severity::Info => "info",
            Severity::Warn => "warn",
            Severity::Error => "error",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Code {
    /// MANIFEST.json failed the embedded schema at some pointer.
    SchemaInvalid,
    /// A `conventions` value this reader does not implement. Refuse, not guess.
    UnsupportedConvention,
    /// A file listed in `files[]` is not in the container.
    FileMissing,
    /// A file's bytes do not match its declared sha256.
    HashMismatch,
    /// A file's length does not match its declared `size`.
    SizeMismatch,
    /// No version of this node could be resolved; the node is unusable.
    NodeDead,
    /// The node's `type` is one this reader does not interpret (law 12). Its
    /// bytes are still verified, listed and extractable.
    NodeSkippedUnknownType,
    /// `active` was unusable and an earlier version was used instead (SPEC 5).
    VersionFallback,
    /// A `requires` edge points into a dead node, which kills this node too.
    RequiresDeadNode,
    /// An `enhances` edge points into a dead node: one feature lost, no more.
    EnhancesDeadNode,
    /// An edge names a node_id that is not in the manifest.
    EdgeDangling,
    /// A file is in the container but reachable from no node version. "Nothing
    /// floats" (SPEC section 2) is a claim the package makes; this is it failing.
    FloatingFile,
    /// A JSON payload failed the schema the manifest's `schemas` map points at.
    PayloadSchemaInvalid,
    /// A custom binary failed an assertion in ENVELOPE.layout.txt section 7.
    EnvelopeInvalid,
    /// A zip entry uses a compression method this reader does not implement
    /// (anything but store and deflate), or is encrypted.
    ZipEntryUnsupported,
    /// A zip entry is damaged at the container level: its deflate stream does
    /// not decode, or its bytes disagree with the directory's size or CRC-32.
    ZipEntryInvalid,
    /// The package's profile is not one this reader has built in. One entry,
    /// severity warn: an admission about the reader, not a complaint about the
    /// package (S-25). It says exactly what was and was not established.
    UnsupportedProfile,
    /// The schema the manifest names for itself cannot be used: not named, not
    /// declared by a `core.spec` node, not in the container, not the bytes the
    /// manifest hashes, or not a schema.
    ManifestSchemaUnusable,
    /// The package carries another revision of its profile's manifest schema
    /// than the one this build has. Informational: the package's own copy is
    /// the authority for its own contents.
    ManifestSchemaRevision,
    /// The manifest's `spec_sha256` is not the digest of the spec files the
    /// manifest itself declares (SPEC.md section 2).
    SpecSha256Mismatch,
    /// A well-formed envelope whose `kind` has no layout grammar in this
    /// package's `layouts` map: structurally valid, not self-described.
    EnvelopeUndeclared,
    /// A node names a format id (`meta.payload_format`, `meta.file_formats`,
    /// `meta.contained_formats`) that the package's `formats` map does not
    /// resolve to a definition document.
    FormatUndeclared,
    /// A format definition document the package points at is unusable: absent,
    /// not a file of a `core.spec` node, no machine header, a header naming
    /// another id, or a printed test vector that does not hash as declared.
    FormatDefinitionInvalid,
    /// A file's leading bytes match none of the alternatives its declared
    /// format's definition gives for recognising it.
    FormatMismatch,
    /// A core node declares (`meta.modified_by`) that a node this reader
    /// skipped or lost changes how its payload is shown.
    ModifiedBySkippedNode,
    /// Three-state doctrine (SPEC section 6). These are never collapsed.
    SignatureAbsent,
    SignatureValid,
    SignatureInvalid,
    /// A prebuilt loader binary was found. It is inert data and was NOT run.
    PrebuiltNotExecuted,
    /// A derived version's declared input_hash does not match its inputs.
    StaleDerivedData,
}

impl Code {
    pub fn as_str(&self) -> &'static str {
        match self {
            Code::SchemaInvalid => "schema-invalid",
            Code::UnsupportedConvention => "unsupported-convention",
            Code::FileMissing => "file-missing",
            Code::HashMismatch => "hash-mismatch",
            Code::SizeMismatch => "size-mismatch",
            Code::NodeDead => "node-dead",
            Code::NodeSkippedUnknownType => "node-skipped-unknown-type",
            Code::VersionFallback => "version-fallback",
            Code::RequiresDeadNode => "requires-dead-node",
            Code::EnhancesDeadNode => "enhances-dead-node",
            Code::EdgeDangling => "edge-dangling",
            Code::FloatingFile => "floating-file",
            Code::PayloadSchemaInvalid => "payload-schema-invalid",
            Code::EnvelopeInvalid => "envelope-invalid",
            Code::ZipEntryUnsupported => "zip-entry-unsupported",
            Code::ZipEntryInvalid => "zip-entry-invalid",
            Code::UnsupportedProfile => "unsupported-profile",
            Code::ManifestSchemaUnusable => "manifest-schema-unusable",
            Code::ManifestSchemaRevision => "manifest-schema-revision",
            Code::SpecSha256Mismatch => "spec-sha256-mismatch",
            Code::EnvelopeUndeclared => "envelope-undeclared",
            Code::FormatUndeclared => "format-undeclared",
            Code::FormatDefinitionInvalid => "format-definition-invalid",
            Code::FormatMismatch => "format-mismatch",
            Code::ModifiedBySkippedNode => "modified-by-skipped-node",
            Code::SignatureAbsent => "signature-absent",
            Code::SignatureValid => "signature-valid",
            Code::SignatureInvalid => "signature-invalid",
            Code::PrebuiltNotExecuted => "prebuilt-not-executed",
            Code::StaleDerivedData => "stale-derived-data",
        }
    }
}

#[derive(Debug, Clone)]
pub struct ReportEntry {
    pub severity: Severity,
    pub code: Code,
    pub node_id: Option<String>,
    pub version: Option<i64>,
    pub path: Option<String>,
    pub message: String,
}

impl std::fmt::Display for ReportEntry {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "[{}] {}", self.severity.as_str(), self.code.as_str())?;
        if let Some(n) = &self.node_id {
            write!(f, " node={n}")?;
        }
        if let Some(v) = self.version {
            write!(f, " v={v}")?;
        }
        if let Some(p) = &self.path {
            write!(f, " path={p}")?;
        }
        write!(f, ": {}", self.message)
    }
}

#[derive(Debug, Clone, Default)]
pub struct LoadReport {
    pub entries: Vec<ReportEntry>,
}

impl LoadReport {
    pub fn push(
        &mut self,
        severity: Severity,
        code: Code,
        node_id: Option<&str>,
        version: Option<i64>,
        path: Option<&str>,
        message: impl Into<String>,
    ) {
        self.entries.push(ReportEntry {
            severity,
            code,
            node_id: node_id.map(str::to_string),
            version,
            path: path.map(str::to_string),
            message: message.into(),
        });
    }

    pub fn count(&self, code: Code) -> usize {
        self.entries.iter().filter(|e| e.code == code).count()
    }

    pub fn errors(&self) -> usize {
        self.entries.iter().filter(|e| e.severity == Severity::Error).count()
    }

    pub fn has(&self, code: Code) -> bool {
        self.count(code) > 0
    }
}

impl std::fmt::Display for LoadReport {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        for e in &self.entries {
            writeln!(f, "{e}")?;
        }
        Ok(())
    }
}
