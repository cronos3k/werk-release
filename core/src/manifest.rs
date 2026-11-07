//! MANIFEST.json — parsing, the typed view, and the conventions check.
//!
//! The raw `serde_json::Value` is kept alongside the typed view because the
//! manifest is the thing signatures are anchored to: it is hashed as the exact
//! bytes it arrived as, never as a reserialisation (SPEC.md section 6).

use crate::error::{Error, Result};
use crate::schema::json_equal;
use serde_json::Value;

/// The schemas are EMBEDDED at build time straight out of `spec/`, not copied
/// into this crate. A copy would be a second authority and would drift; this
/// way a spec edit is a compile-time change to the reference implementation,
/// which is the relationship the manifesto asks for.
pub const MANIFEST_SCHEMA: &str = include_str!("../../spec/schemas/manifest.schema.json");
pub const MANIFEST_SCHEMA_IMAGE: &str =
    include_str!("../../spec/schemas/manifest.image.schema.json");
pub const SIGNATURE_SCHEMA: &str = include_str!("../../spec/schemas/signature.schema.json");
/// The shape EVERY manifest of major version 1 has, whatever its profile
/// (SPEC.md section 2.2). It is the part of manifest validation a reader holds
/// itself: a package can ship a permissive profile schema, and cannot loosen
/// this one.
pub const MANIFEST_SCHEMA_BASE: &str =
    include_str!("../../spec/schemas/manifest.base.schema.json");

/// The six conventions every reader depends on to read ANY werk — the
/// container, the manifest and the envelope frame — and therefore checks
/// against itself in every profile, including one it has never heard of
/// (SPEC.md section 10.3). Their values are read out of the base schema's
/// `const` pins, not restated here.
pub const BASE_CONVENTIONS: &[&str] = &[
    "endianness",
    "alignment_bytes",
    "text_encoding",
    "id_case",
    "hash_algorithm",
    "signature_algorithm",
];

/// The path a reference profile's manifest schema has when the manifest does
/// not name one. Only the two reference profiles have a default; every other
/// profile MUST name its schema, because nothing else says where it is.
pub fn default_manifest_schema_path(profile: &str) -> Option<&'static str> {
    match profile {
        "3d-entity/1" | "" => Some("spec/schemas/manifest.schema.json"),
        "image/1" => Some("spec/schemas/manifest.image.schema.json"),
        _ => None,
    }
}

/// Which embedded manifest schema validates a package, given its declared
/// profile and its optional `manifest_schema` path.
///
/// The path wins when this build carries the schema it names, because a
/// declared value beats a derived one (law 8's corollary) — and mapping a
/// profile string to a filename by convention is deriving. `None` means this
/// build has no schema for that package: the caller reports it and validates
/// nothing rather than validating against the wrong document, which would
/// produce a page of confident, meaningless errors.
pub fn manifest_schema_for(profile: &str, declared_path: Option<&str>) -> Option<&'static str> {
    if let Some(p) = declared_path {
        return match p {
            "spec/schemas/manifest.schema.json" => Some(MANIFEST_SCHEMA),
            "spec/schemas/manifest.image.schema.json" => Some(MANIFEST_SCHEMA_IMAGE),
            _ => None,
        };
    }
    match profile {
        // The documented fallback: a package written before `manifest_schema`
        // existed is a profile-1 package.
        "3d-entity/1" | "" => Some(MANIFEST_SCHEMA),
        "image/1" => Some(MANIFEST_SCHEMA_IMAGE),
        _ => None,
    }
}

/// Node types this build knows how to interpret. Anything else — an `x.*`
/// extension, or a `core.*` type from a later profile — is skipped and
/// reported, never guessed at (law 12).
///
/// The list spans every profile this build knows, deliberately: whether a type
/// is legal *here* is the manifest schema's question, and this list answers a
/// different one — whether this reader can interpret the payload at all.
pub const KNOWN_TYPES: &[&str] = &[
    "core.spec", "core.loader", "core.license", "core.readme",
    "core.geom.source", "core.geom.game", "core.geom.lod", "core.tex",
    "core.material", "core.imposter", "core.phys.colliders", "core.phys.bounds",
    "core.phys.body", "core.field.flow", "core.pose.rest", "core.skeleton",
    "core.anim.clip", "core.audio.package", "core.audio.effect",
    "core.audio.ambience", "core.destruct", "core.props", "core.semantics",
    "core.provenance",
    // Base doctrine, every profile (SPEC.md 3.11-3.13, 3.17).
    "core.recipe", "core.disclosure", "core.embedding",
    "core.tool", "core.tool.config",
    // Stage 12 geometry (SPEC.md 3.15-3.16).
    "core.geom.points", "core.geom.gsplat",
    // Ruled 2026-08-08 (ruling 12) and shipped with a schema; this list did
    // not know about it, so the one package that carries a solved bind had it
    // skipped as an unknown type. Added in Stage 12 with the four above.
    "core.retarget.bind",
    // Profile image/1.
    "core.image.source", "core.image.derived",
    // PROPOSED 2026-10-13: the document revision log (base doctrine, SPEC.md
    // 3.19) and the versioned scene record of profile 1 (SPEC.md 3.20).
    "core.revisions", "core.scene",
];

#[derive(Debug, Clone)]
pub struct FileRef {
    pub path: String,
    pub sha256: String,
    pub size: u64,
    pub media_type: Option<String>,
    pub role: Option<String>,
}

#[derive(Debug, Clone)]
pub struct VersionView {
    pub v: i64,
    pub note: String,
    pub epistemic: String,
    pub created: String,
    pub files: Vec<FileRef>,
    pub input_hash: Option<String>,
    pub input_files: Vec<String>,
    pub compacted: bool,
    /// SPEC.md section 2.1: the declared path of THE payload file, when the
    /// version declares one.
    pub payload_file: Option<String>,
}

#[derive(Debug, Clone)]
pub struct Edge {
    pub to: String,
    pub kind: String,
    pub role: Option<String>,
}

#[derive(Debug, Clone)]
pub struct NodeView {
    pub index: usize,
    pub node_id: String,
    pub ntype: String,
    pub active: i64,
    pub versions: Vec<VersionView>,
    pub edges: Vec<Edge>,
    pub meta: Option<Value>,
}

impl NodeView {
    pub fn version(&self, v: i64) -> Option<&VersionView> {
        self.versions.iter().find(|x| x.v == v)
    }
}

pub struct Manifest {
    pub bytes: Vec<u8>,
    pub raw: Value,
}

impl Manifest {
    pub fn parse(bytes: Vec<u8>) -> Result<Manifest> {
        let raw: Value = serde_json::from_slice(&bytes)
            .map_err(|e| Error::BadManifest(format!("MANIFEST.json is not valid JSON: {e}")))?;
        if !raw.is_object() {
            return Err(Error::BadManifest("MANIFEST.json is not a JSON object".into()));
        }
        Ok(Manifest { bytes, raw })
    }

    pub fn entity_name(&self) -> &str {
        self.raw.pointer("/entity/name").and_then(Value::as_str).unwrap_or("")
    }
    pub fn entity_uuid(&self) -> &str {
        self.raw.pointer("/entity/uuid").and_then(Value::as_str).unwrap_or("")
    }
    pub fn profile(&self) -> &str {
        self.raw.get("profile").and_then(Value::as_str).unwrap_or("")
    }

    /// The path this manifest declares for its own schema, if it declares one.
    pub fn declared_manifest_schema(&self) -> Option<&str> {
        self.raw.get("manifest_schema").and_then(Value::as_str)
    }

    /// The embedded schema text that validates THIS manifest, or `None` when
    /// this build has none for its profile.
    pub fn schema_source(&self) -> Option<&'static str> {
        manifest_schema_for(self.profile(), self.declared_manifest_schema())
    }
    pub fn schemas_map(&self) -> Vec<(String, String)> {
        pairs(self.raw.get("schemas"))
    }
    /// Format id -> path of the definition document (SPEC.md section 3.18).
    pub fn formats_map(&self) -> Vec<(String, String)> {
        pairs(self.raw.get("formats"))
    }
    /// The path of the manifest schema this manifest names, or its profile's
    /// default. `None` for a non-reference profile that names none.
    pub fn manifest_schema_path(&self) -> Option<String> {
        self.declared_manifest_schema()
            .map(str::to_string)
            .or_else(|| default_manifest_schema_path(self.profile()).map(str::to_string))
    }
    pub fn spec_sha256(&self) -> Option<&str> {
        self.raw.get("spec_sha256").and_then(Value::as_str)
    }
    pub fn layouts_map(&self) -> Vec<(String, String)> {
        pairs(self.raw.get("layouts"))
    }
    pub fn entry_order(&self) -> Vec<String> {
        self.raw
            .pointer("/container/entry_order")
            .and_then(Value::as_array)
            .map(|a| a.iter().filter_map(Value::as_str).map(str::to_string).collect())
            .unwrap_or_default()
    }
    pub fn has_signature_file(&self) -> bool {
        self.raw.get("signature_file").is_some()
    }

    /// Build the typed view. A node the view cannot be built from (missing
    /// node_id, no versions) is returned as `Err` for that index only — the
    /// caller quarantines it and keeps going.
    pub fn nodes(&self) -> Vec<std::result::Result<NodeView, (usize, String)>> {
        let arr = match self.raw.get("nodes").and_then(Value::as_array) {
            Some(a) => a,
            None => return Vec::new(),
        };
        arr.iter().enumerate().map(|(i, n)| node_view(i, n)).collect()
    }

    /// SPEC.md section 10 step 3: check every declared convention against what
    /// this reader supports, and refuse rather than guess. The values are not
    /// restated here in prose — they are read out of the built-in schema's
    /// `const` pins, so the schema stays the single authority (law 8).
    ///
    /// For a profile this build has a schema for, that is the profile's whole
    /// convention set. For any other profile it is the six BASE conventions,
    /// which is all a reader that does not implement the profile depends on
    /// (SPEC.md section 10.3); the profile's own conventions govern payload
    /// meaning this reader does not claim, and are reported as such by the
    /// caller in its one `unsupported-profile` entry.
    pub fn unsupported_conventions(&self) -> Vec<String> {
        match self.schema_source() {
            Some(src) => self.conventions_against(src, None),
            None => self.conventions_against(MANIFEST_SCHEMA_BASE, Some(BASE_CONVENTIONS)),
        }
    }

    /// The conventions this manifest declares beyond the base six — the
    /// profile's own.
    pub fn profile_convention_keys(&self) -> Vec<String> {
        self.raw
            .get("conventions")
            .and_then(Value::as_object)
            .map(|c| {
                c.keys()
                    .filter(|k| !BASE_CONVENTIONS.contains(&k.as_str()))
                    .cloned()
                    .collect()
            })
            .unwrap_or_default()
    }

    fn conventions_against(&self, src: &str, only: Option<&[&str]>) -> Vec<String> {
        let schema: Value = match serde_json::from_str(src) {
            Ok(v) => v,
            Err(_) => return vec!["embedded manifest schema is unreadable".into()],
        };
        let pins = match schema.pointer("/properties/conventions/properties").and_then(Value::as_object) {
            Some(p) => p,
            None => return vec!["embedded schema declares no conventions".into()],
        };
        let mine = match self.raw.get("conventions").and_then(Value::as_object) {
            Some(c) => c,
            None => return vec!["manifest declares no `conventions` block".into()],
        };
        // Which conventions are MANDATORY is the schema's `required` list, not
        // "every key that has a const". Stage 12 added two OPTIONAL conventions
        // with const pins — sh_coeff_order and sh_degree — and the old rule
        // reported the first as a missing convention on every package written
        // before it existed, which is exactly the retroactive
        // non-conformance an optional key exists to avoid. A key that is
        // PRESENT is still checked against its pin; a key that is absent is
        // only an error when the schema says it must be there.
        let required: Vec<&str> = schema
            .pointer("/properties/conventions/required")
            .and_then(Value::as_array)
            .map(|a| a.iter().filter_map(Value::as_str).collect())
            .unwrap_or_default();
        let mut out = Vec::new();
        for (key, spec) in pins {
            if let Some(only) = only {
                if !only.contains(&key.as_str()) {
                    continue;
                }
            }
            let expected = match spec.get("const") {
                Some(c) => c,
                None => continue,
            };
            match mine.get(key) {
                None => {
                    if required.iter().any(|r| r == key) {
                        out.push(format!(
                            "`{key}` is missing; this reader requires it to be {expected}"
                        ));
                    }
                }
                Some(v) if !json_equal(expected, v) => out.push(format!(
                    "`{key}` is {v}; this reader implements only {expected}"
                )),
                _ => {}
            }
        }
        out
    }
}

fn pairs(v: Option<&Value>) -> Vec<(String, String)> {
    v.and_then(Value::as_object)
        .map(|m| {
            m.iter()
                .filter_map(|(k, v)| v.as_str().map(|s| (k.clone(), s.to_string())))
                .collect()
        })
        .unwrap_or_default()
}

fn node_view(i: usize, n: &Value) -> std::result::Result<NodeView, (usize, String)> {
    let err = |m: &str| (i, format!("nodes[{i}]: {m}"));
    let node_id = n
        .get("node_id")
        .and_then(Value::as_str)
        .ok_or_else(|| err("no node_id"))?
        .to_string();
    let ntype = n
        .get("type")
        .and_then(Value::as_str)
        .ok_or_else(|| err("no type"))?
        .to_string();
    let active = n.get("active").and_then(Value::as_i64).ok_or_else(|| err("no active"))?;
    let versions_raw = n
        .get("versions")
        .and_then(Value::as_array)
        .ok_or_else(|| err("no versions array"))?;
    if versions_raw.is_empty() {
        return Err(err("versions[] is empty"));
    }
    let mut versions = Vec::with_capacity(versions_raw.len());
    for ver in versions_raw {
        let v = ver.get("v").and_then(Value::as_i64).ok_or_else(|| err("a version has no v"))?;
        let files = ver
            .get("files")
            .and_then(Value::as_array)
            .ok_or_else(|| err("a version has no files[]"))?
            .iter()
            .map(|f| FileRef {
                path: f.get("path").and_then(Value::as_str).unwrap_or("").to_string(),
                sha256: f.get("sha256").and_then(Value::as_str).unwrap_or("").to_string(),
                size: f.get("size").and_then(Value::as_u64).unwrap_or(0),
                media_type: f.get("media_type").and_then(Value::as_str).map(str::to_string),
                role: f.get("role").and_then(Value::as_str).map(str::to_string),
            })
            .collect();
        versions.push(VersionView {
            v,
            note: ver.get("note").and_then(Value::as_str).unwrap_or("").to_string(),
            epistemic: ver.get("epistemic").and_then(Value::as_str).unwrap_or("").to_string(),
            created: ver.get("created").and_then(Value::as_str).unwrap_or("").to_string(),
            files,
            input_hash: ver.get("input_hash").and_then(Value::as_str).map(str::to_string),
            input_files: ver
                .get("input_files")
                .and_then(Value::as_array)
                .map(|a| a.iter().filter_map(Value::as_str).map(str::to_string).collect())
                .unwrap_or_default(),
            compacted: ver.get("compacted").is_some(),
            payload_file: ver.get("payload_file").and_then(Value::as_str).map(str::to_string),
        });
    }
    let edges = n
        .get("edges")
        .and_then(Value::as_array)
        .map(|a| {
            a.iter()
                .map(|e| Edge {
                    to: e.get("to").and_then(Value::as_str).unwrap_or("").to_string(),
                    kind: e.get("kind").and_then(Value::as_str).unwrap_or("enhances").to_string(),
                    role: e.get("role").and_then(Value::as_str).map(str::to_string),
                })
                .collect()
        })
        .unwrap_or_default();
    Ok(NodeView {
        index: i,
        node_id,
        ntype,
        active,
        versions,
        edges,
        meta: n.get("meta").cloned(),
    })
}

/// Canonical JSON (spec/MINI-SPECS.md section 3): object keys sorted by UTF-8
/// byte order, no insignificant whitespace, numbers in shortest round-tripping
/// form. serde_json's default map is a BTreeMap and its float writer is
/// shortest-round-trip, so `to_string` already IS canonical — stated here so
/// nobody has to rediscover it.
pub fn canonical_json(v: &Value) -> String {
    serde_json::to_string(v).unwrap_or_else(|_| "null".into())
}

/// The on-disk spelling werk uses for a manifest it wrote itself: two-space
/// indent and a trailing newline, matching `spec/examples/make-examples.py`.
pub fn pretty_json(v: &Value) -> Vec<u8> {
    let mut s = serde_json::to_string_pretty(v).unwrap_or_else(|_| "null".into());
    s.push('\n');
    s.into_bytes()
}
