//! The 2026-10-13 entries, as tests rather than claims: any profile (SPEC.md
//! 2.2 and 10.3), envelopes recognised by their frame (3.1), format
//! definitions (3.18), `modified_by` (3.20), deflate and zip64 (1, MINI-SPECS
//! 5.5 and 7.1), and the reference's own consistency (the example manifest,
//! canonical JSON).
//!
//! Every package here is the Stage 2 fixture, rebuilt in memory with one
//! thing changed, so each test isolates one rule. The packages of profiles
//! this repository has never seen that were written by OTHER people's code
//! are measured by `tests/run_gate_artcraft.py`; this file is the part that
//! needs no corpus.
//!
//! Everything is written under `core/target/test-tmp/`, inside the project.

use serde_json::{json, Value};
use std::path::{Path, PathBuf};
use werk::envelope::{self, SectionSpec};
use werk::hashing::{from_hex, sha256_hex};
use werk::manifest::{canonical_json, pretty_json};
use werk::package::{ManifestValidation, Package};
use werk::report::{Code, Severity};
use werk::schema::Validator;
use werk::zipstore::{crc32, write_zip, ZipArchive};
use werk::{Error, NodeStatus};

fn repo() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap().to_path_buf()
}

fn tmp(name: &str) -> PathBuf {
    let d = Path::new(env!("CARGO_MANIFEST_DIR")).join("target/test-tmp");
    std::fs::create_dir_all(&d).unwrap();
    d.join(name)
}

type Files = Vec<(String, Vec<u8>)>;

/// The fixture's entries, with its manifest parsed and its signature dropped
/// (every test here changes the manifest, and an invalid chain is a different
/// test's subject).
fn fixture() -> (Value, Files) {
    let z = ZipArchive::parse(std::fs::read(repo().join("tests/fixtures/crate.werk")).unwrap())
        .unwrap();
    let mut manifest = Value::Null;
    let mut files = Vec::new();
    for name in z.names() {
        let data = z.read(&name).unwrap();
        match name.as_str() {
            "MANIFEST.json" => manifest = serde_json::from_slice(&data).unwrap(),
            "SIGNATURE.json" => {}
            _ => files.push((name, data)),
        }
    }
    manifest.as_object_mut().unwrap().remove("signature_file");
    (manifest, files)
}

fn node_mut<'a>(manifest: &'a mut Value, node_id: &str) -> &'a mut Value {
    manifest["nodes"]
        .as_array_mut()
        .unwrap()
        .iter_mut()
        .find(|n| n["node_id"] == node_id)
        .unwrap_or_else(|| panic!("no node {node_id}"))
}

/// Add (or replace) a file and declare it in version 1 of `node_id`.
fn put(manifest: &mut Value, files: &mut Files, node_id: &str, path: &str, data: &[u8]) {
    files.retain(|(p, _)| p != path);
    files.push((path.to_string(), data.to_vec()));
    let list = node_mut(manifest, node_id)["versions"][0]["files"].as_array_mut().unwrap();
    list.retain(|f| f["path"] != path);
    list.push(json!({"path": path, "sha256": sha256_hex(data), "size": data.len()}));
}

fn add_node(manifest: &mut Value, files: &mut Files, node_id: &str, ntype: &str, path: &str, data: &[u8], meta: Option<Value>) {
    files.push((path.to_string(), data.to_vec()));
    let mut node = json!({
        "node_id": node_id, "type": ntype,
        "versions": [{
            "v": 1,
            "files": [{"path": path, "sha256": sha256_hex(data), "size": data.len()}],
            "note": "A node added by a test to isolate one rule.",
            "producer": {"tool": "core/tests/profiles.rs", "version": "1"},
            "epistemic": "authored", "created": "2026-10-13T00:00:00Z"
        }],
        "active": 1, "edges": []
    });
    if let Some(m) = meta {
        node["meta"] = m;
    }
    manifest["nodes"].as_array_mut().unwrap().push(node);
}

/// SPEC.md section 2, recomputed over the manifest's own declarations.
fn respec(manifest: &mut Value) {
    let mut decl = std::collections::BTreeMap::new();
    for n in manifest["nodes"].as_array().unwrap() {
        for v in n["versions"].as_array().unwrap() {
            for f in v["files"].as_array().unwrap() {
                let p = f["path"].as_str().unwrap();
                if p.starts_with("spec/") {
                    decl.insert(p.to_string(), f["sha256"].as_str().unwrap().to_string());
                }
            }
        }
    }
    let mut acc = Vec::new();
    for (p, h) in decl {
        acc.extend_from_slice(p.as_bytes());
        acc.push(b'\n');
        acc.extend_from_slice(&from_hex(&h).unwrap());
        acc.push(b'\n');
    }
    manifest["spec_sha256"] = json!(sha256_hex(&acc));
}

fn write(name: &str, manifest: &Value, files: &Files) -> PathBuf {
    let mut entries = vec![("MANIFEST.json".to_string(), pretty_json(manifest))];
    entries.extend(files.iter().cloned());
    let dest = tmp(name);
    std::fs::write(&dest, write_zip(&entries)).unwrap();
    dest
}

fn count(p: &Package, code: Code, sev: Severity) -> usize {
    p.report.entries.iter().filter(|e| e.code == code && e.severity == sev).count()
}

/// A profile schema for a profile this build has never heard of: the base
/// shape, with `profile` pinned and one node type of its own admitted. It is
/// deliberately tiny — what is under test is where the reader gets it from.
fn toy_schema() -> Value {
    json!({
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "toy/1",
        "type": "object",
        "required": ["werk", "profile", "manifest_schema", "nodes"],
        "properties": {
            "profile": {"const": "toy/1"},
            "conventions": {
                "type": "object",
                "required": ["toy_unit"],
                "properties": {"toy_unit": {"const": "furlong"}}
            }
        }
    })
}

/// The fixture, re-declared as profile `toy/1` carrying its own schema.
fn toy_package() -> (Value, Files) {
    let (mut m, mut files) = fixture();
    m["profile"] = json!("toy/1");
    m["manifest_schema"] = json!("spec/schemas/manifest.toy.schema.json");
    m["conventions"]["toy_unit"] = json!("furlong");
    let schema = pretty_json(&toy_schema());
    put(&mut m, &mut files, "spec", "spec/schemas/manifest.toy.schema.json", &schema);
    add_node(&mut m, &mut files, "thing", "core.toy.thing", "toy/thing.json", b"{\"n\": 1}\n", None);
    respec(&mut m);
    (m, files)
}

// ---------------------------------------------------------------------------
// SPEC 2.2 — any profile
// ---------------------------------------------------------------------------

#[test]
fn a_profile_this_build_has_never_heard_of_opens_with_no_error() {
    let (m, files) = toy_package();
    let p = Package::open(write("toy.werk", &m, &files)).unwrap();
    assert_eq!(p.report.errors(), 0, "{}", p.report);
    assert_eq!(p.manifest_validation, ManifestValidation::PackageOwn);
    // Exactly ONE entry about the profile, a warning, and it says what the
    // validation does not establish.
    assert_eq!(count(&p, Code::UnsupportedProfile, Severity::Warn), 1, "{}", p.report);
    let e = p.report.entries.iter().find(|e| e.code == Code::UnsupportedProfile).unwrap();
    assert!(e.message.contains("PACKAGE'S OWN schema"), "{}", e.message);
    assert!(e.message.contains("does NOT establish"), "{}", e.message);
    // The profile's own node type is skipped and reported — never an error —
    // and every node the reader does know is still alive.
    assert!(matches!(p.node("thing").unwrap().status, NodeStatus::Skipped(_)));
    assert_eq!(p.node("geom-game").unwrap().status, NodeStatus::Alive);
    assert_eq!(p.nodes.iter().filter(|n| n.status.is_dead()).count(), 0);
    // The old behaviour, named so that it cannot come back unnoticed: an
    // `unsupported-convention` error saying the build carries no schema.
    assert_eq!(count(&p, Code::UnsupportedConvention, Severity::Error), 0);
}

#[test]
fn the_package_schema_is_really_applied_not_merely_located() {
    // The toy schema requires conventions.toy_unit == "furlong".
    let (mut m, files) = toy_package();
    m["conventions"]["toy_unit"] = json!("parsec");
    let p = Package::open(write("toy-wrong-unit.werk", &m, &files)).unwrap();
    assert!(p.report.entries.iter().any(|e| e.code == Code::SchemaInvalid
        && e.severity == Severity::Error
        && e.message.contains("/conventions/toy_unit")), "{}", p.report);
}

#[test]
fn a_permissive_schema_cannot_loosen_the_base_shape() {
    // SPEC 10.3: a package can ship any schema, including one that permits
    // everything. The base schema is the reader's own and still applies.
    let (mut m, mut files) = toy_package();
    put(&mut m, &mut files, "spec", "spec/schemas/manifest.toy.schema.json", b"{}\n");
    m.as_object_mut().unwrap().remove("license");
    m["nodes"][0]["versions"][0]["note"] = json!("x");
    respec(&mut m);
    let p = Package::open(write("toy-permissive.werk", &m, &files)).unwrap();
    let base: Vec<_> = p
        .report
        .entries
        .iter()
        .filter(|e| e.code == Code::SchemaInvalid && e.message.starts_with("base shape: "))
        .collect();
    assert!(base.iter().any(|e| e.message.contains("license")), "{}", p.report);
    assert!(base.iter().any(|e| e.message.contains("/nodes/0/versions/0/note")), "{}", p.report);
    // A base-shape error under /nodes/0 quarantines that node, as a profile
    // schema's would.
    assert!(p.nodes[0].status.is_dead());
}

#[test]
fn the_six_base_conventions_are_checked_in_a_profile_the_reader_does_not_know() {
    let (mut m, files) = toy_package();
    m["conventions"]["hash_algorithm"] = json!("md5");
    let p = Package::open(write("toy-md5.werk", &m, &files)).unwrap();
    assert!(p.report.entries.iter().any(|e| e.code == Code::UnsupportedConvention
        && e.severity == Severity::Error
        && e.message.contains("hash_algorithm")), "{}", p.report);
    // ... and the profile's own convention is named, not refused.
    let e = p.report.entries.iter().find(|e| e.code == Code::UnsupportedProfile).unwrap();
    assert!(e.message.contains("toy_unit"), "{}", e.message);
}

#[test]
fn a_schema_that_is_not_part_of_the_specification_is_unusable() {
    // Named, present in the container, and NOT declared by a core.spec node:
    // it is not covered by spec_sha256, so it is not the package's schema.
    let (mut m, mut files) = toy_package();
    let schema = files.iter().find(|(p, _)| p.ends_with("manifest.toy.schema.json")).unwrap().1.clone();
    node_mut(&mut m, "spec")["versions"][0]["files"]
        .as_array_mut()
        .unwrap()
        .retain(|f| f["path"] != "spec/schemas/manifest.toy.schema.json");
    files.retain(|(p, _)| !p.ends_with("manifest.toy.schema.json"));
    add_node(&mut m, &mut files, "sneaky", "x.test.sneaky", "spec/schemas/manifest.toy.schema.json", &schema, None);
    respec(&mut m);
    let p = Package::open(write("toy-sneaky.werk", &m, &files)).unwrap();
    assert_eq!(count(&p, Code::ManifestSchemaUnusable, Severity::Error), 1, "{}", p.report);
    assert_eq!(p.manifest_validation, ManifestValidation::BaseOnly);
}

#[test]
fn a_third_profile_that_names_no_schema_says_so() {
    let (mut m, files) = toy_package();
    m.as_object_mut().unwrap().remove("manifest_schema");
    let p = Package::open(write("toy-nameless.werk", &m, &files)).unwrap();
    assert_eq!(count(&p, Code::ManifestSchemaUnusable, Severity::Error), 1, "{}", p.report);
    assert_eq!(p.manifest_validation, ManifestValidation::BaseOnly);
}

#[test]
fn a_hostile_schema_cannot_recurse_forever_or_flood_the_report() {
    let (mut m, mut files) = toy_package();
    // `$ref` to itself, and a keyword this validator does not implement used
    // where it would be met once per node.
    let hostile = json!({
        "$ref": "#",
        "properties": {"nodes": {"items": {"dependentRequired": {"a": ["b"]}}}}
    });
    put(&mut m, &mut files, "spec", "spec/schemas/manifest.toy.schema.json", &pretty_json(&hostile));
    respec(&mut m);
    let p = Package::open(write("toy-hostile.werk", &m, &files)).unwrap();
    // It returned at all; the recursion is reported, bounded ...
    let recursion = p.report.entries.iter().filter(|e| e.message.contains("recursion")).count();
    assert!(recursion >= 1, "{}", p.report);
    // ... and the unknown keyword is named ONCE, as a constraint not checked.
    let unknown: Vec<_> = p
        .report
        .entries
        .iter()
        .filter(|e| e.code == Code::ManifestSchemaUnusable && e.message.contains("dependentRequired"))
        .collect();
    assert_eq!(unknown.len(), 1, "{}", p.report);
    assert_eq!(unknown[0].severity, Severity::Warn);
}

#[test]
fn a_built_in_profile_carrying_another_schema_revision_is_validated_against_its_own() {
    // The package's copy of manifest.schema.json differs from this build's by
    // one description. The package is the authority for its own contents; the
    // reader says which revision it used, and its own revision's findings are
    // warnings (law 12: on an OLDER package there must be none).
    let (mut m, mut files) = fixture();
    let mut schema: Value = serde_json::from_str(werk::manifest::MANIFEST_SCHEMA).unwrap();
    schema["title"] = json!("an earlier revision, for the test");
    put(&mut m, &mut files, "spec", "spec/schemas/manifest.schema.json", &pretty_json(&schema));
    respec(&mut m);
    let p = Package::open(write("revision.werk", &m, &files)).unwrap();
    assert_eq!(p.manifest_validation, ManifestValidation::PackageRevision);
    assert_eq!(count(&p, Code::ManifestSchemaRevision, Severity::Info), 1, "{}", p.report);
    assert_eq!(p.report.errors(), 0, "{}", p.report);
    assert!(!p.report.entries.iter().any(|e| e.message.contains("by this build's revision")),
            "an identical-in-effect revision must produce no difference:\n{}", p.report);
}

#[test]
fn spec_sha256_is_recomputed_and_a_wrong_one_is_an_error() {
    let (m, files) = fixture();
    let ok = Package::open(write("specsha-ok.werk", &m, &files)).unwrap();
    assert_eq!(count(&ok, Code::SpecSha256Mismatch, Severity::Error), 0, "{}", ok.report);

    let (mut m, files) = fixture();
    m["spec_sha256"] = json!("0".repeat(64));
    let p = Package::open(write("specsha-bad.werk", &m, &files)).unwrap();
    assert_eq!(count(&p, Code::SpecSha256Mismatch, Severity::Error), 1, "{}", p.report);
    // The manifest's claim about itself is wrong; no node is harmed by that.
    assert_eq!(p.nodes.iter().filter(|n| n.status.is_dead()).count(), 0);
}

#[test]
fn a_payload_of_a_type_the_reader_skips_is_still_held_to_the_schema_the_package_ships() {
    let (mut m, mut files) = toy_package();
    let schema = json!({"type": "object", "required": ["n"], "additionalProperties": false,
                        "properties": {"n": {"type": "integer"}}});
    put(&mut m, &mut files, "spec", "spec/schemas/core.toy.thing.schema.json", &pretty_json(&schema));
    m["schemas"]["core.toy.thing"] = json!("spec/schemas/core.toy.thing.schema.json");
    respec(&mut m);
    let good = Package::open(write("toy-payload-ok.werk", &m, &files)).unwrap();
    assert!(matches!(good.node("thing").unwrap().status, NodeStatus::Skipped(_)));

    // Damage the payload AND re-hash it, so that no hash mismatches and only
    // the schema can notice.
    let bad = b"{\"n\": \"one\"}\n";
    put(&mut m, &mut files, "thing", "toy/thing.json", bad);
    let p = Package::open(write("toy-payload-bad.werk", &m, &files)).unwrap();
    assert_eq!(p.report.count(Code::HashMismatch), 0);
    assert!(p.node("thing").unwrap().status.is_dead(), "{}", p.report);
    assert!(p.report.has(Code::PayloadSchemaInvalid));
}

// ---------------------------------------------------------------------------
// SPEC 3.1 — envelopes are recognised by their frame
// ---------------------------------------------------------------------------

fn toy_envelope(magic: &[u8; 4], kind: &str) -> Vec<u8> {
    envelope::build(
        magic,
        1,
        Default::default(),
        kind,
        &[SectionSpec {
            name: "values".into(),
            dtype: "u8".into(),
            shape: vec![4],
            stride: 1,
            data: vec![1, 2, 3, 4],
        }],
    )
}

#[test]
fn an_envelope_with_a_magic_no_table_knows_is_validated_not_passed_over() {
    // `WKZZ` is in no table anywhere. Before ruling 4 this file was not
    // parsed and nothing was reported.
    let (mut m, mut files) = fixture();
    let before = Package::open(write("env-base.werk", &m, &files)).unwrap().envelopes_validated;
    add_node(&mut m, &mut files, "blob", "x.test.blob", "x/test/values.bin",
             &toy_envelope(b"WKZZ", "x.test.blob"), None);
    put(&mut m, &mut files, "spec", "spec/layouts/x.test.blob.layout.txt", b"values: u8[4]\n");
    m["layouts"]["x.test.blob"] = json!("spec/layouts/x.test.blob.layout.txt");
    respec(&mut m);
    let p = Package::open(write("env-unknown-magic.werk", &m, &files)).unwrap();
    assert_eq!(p.envelopes_validated, before + 1);
    assert_eq!(p.report.count(Code::EnvelopeUndeclared), 0, "{}", p.report);
    assert_eq!(p.report.count(Code::EnvelopeInvalid), 0, "{}", p.report);
    assert_eq!(p.report.errors(), 0, "{}", p.report);
}

#[test]
fn an_envelope_whose_kind_has_no_grammar_in_the_package_is_reported() {
    let (mut m, mut files) = fixture();
    add_node(&mut m, &mut files, "blob", "x.test.blob", "x/test/values.bin",
             &toy_envelope(b"WKX7", "x.test.blob"), None);
    let p = Package::open(write("env-undeclared.werk", &m, &files)).unwrap();
    assert_eq!(count(&p, Code::EnvelopeUndeclared, Severity::Warn), 1, "{}", p.report);
    assert_eq!(p.report.errors(), 0, "the frame is sound; this is a warning");
}

#[test]
fn an_envelope_whose_kind_is_not_its_nodes_type_is_reported() {
    let (mut m, mut files) = fixture();
    add_node(&mut m, &mut files, "blob", "x.test.blob", "x/test/values.bin",
             &toy_envelope(b"WKX7", "x.test.other"), None);
    put(&mut m, &mut files, "spec", "spec/layouts/x.test.other.layout.txt", b"values: u8[4]\n");
    m["layouts"]["x.test.other"] = json!("spec/layouts/x.test.other.layout.txt");
    respec(&mut m);
    let p = Package::open(write("env-kind.werk", &m, &files)).unwrap();
    assert!(p.report.entries.iter().any(|e| e.code == Code::EnvelopeInvalid
        && e.severity == Severity::Warn
        && e.message.contains("x.test.other")), "{}", p.report);
}

#[test]
fn a_broken_frame_under_an_unknown_magic_kills_its_node() {
    let (mut m, mut files) = fixture();
    let mut bytes = toy_envelope(b"WKZZ", "x.test.blob");
    bytes.truncate(bytes.len() - 16); // payload_origin + payload_size != file size
    add_node(&mut m, &mut files, "blob", "x.test.blob", "x/test/values.bin", &bytes, None);
    let p = Package::open(write("env-broken.werk", &m, &files)).unwrap();
    assert!(p.node("blob").unwrap().status.is_dead(), "{}", p.report);
    assert_eq!(p.node("geom-game").unwrap().status, NodeStatus::Alive);
}

#[test]
fn a_reserved_magic_still_binds_its_kind() {
    let (mut m, mut files) = fixture();
    add_node(&mut m, &mut files, "blob", "x.test.blob", "x/test/values.bin",
             &toy_envelope(b"WKRP", "x.test.blob"), None);
    let p = Package::open(write("env-reserved.werk", &m, &files)).unwrap();
    assert!(p.node("blob").unwrap().status.is_dead(), "{}", p.report);
}

// ---------------------------------------------------------------------------
// SPEC 3.18 — format definitions
// ---------------------------------------------------------------------------

const TOY_PAYLOAD: &[u8] = b"TOY\x01hello";

fn toy_definition(vector_sha: &str) -> Vec<u8> {
    format!(
        "# toy\n\n```werk-format\n{{\n  \"format_id\": \"toy-format\",\n  \"format_version\": 1,\n  \
         \"title\": \"toy\",\n  \"media_type\": \"application/x-toy\",\n  \
         \"sniff\": [{{\"magic\": [{{\"offset\": 0, \"hex\": \"544f59\"}}]}}],\n  \
         \"defines\": {{\"decode\": true, \"encode\": false}},\n  \"coverage\": \"complete\",\n  \
         \"test_vectors\": [{{\"id\": \"hello\", \"input_bytes\": 9, \"input_sha256\": \"{vector_sha}\",\n    \
         \"output_form\": \"the bytes after the 4-byte header\", \"output_bytes\": 5,\n    \
         \"output_sha256\": \"{}\"}}]\n}}\n```\n\nThe payload is `TOY`, one version byte, then the content.\n\n\
         ```hex hello\n54 4f 59 01 68 65 6c 6c 6f\n```\n",
        sha256_hex(b"hello")
    )
    .into_bytes()
}

fn with_format(vector_sha: &str, payload: &[u8], declared_id: &str) -> (Value, Files) {
    let (mut m, mut files) = fixture();
    put(&mut m, &mut files, "spec", "spec/formats/toy-format.md", &toy_definition(vector_sha));
    m["formats"] = json!({"toy-format": "spec/formats/toy-format.md"});
    add_node(&mut m, &mut files, "original", "x.test.original", "original/file.toy", payload,
             Some(json!({"payload_format": declared_id})));
    respec(&mut m);
    (m, files)
}

#[test]
fn a_foreign_encoded_payload_with_its_definition_in_the_package_is_checked_and_counted() {
    let (m, files) = with_format(&sha256_hex(TOY_PAYLOAD), TOY_PAYLOAD, "toy-format");
    let p = Package::open(write("format-ok.werk", &m, &files)).unwrap();
    assert_eq!(p.formats_read, 1, "{}", p.report);
    assert_eq!(p.format_vectors_checked, 1);
    assert_eq!(p.report.errors(), 0, "{}", p.report);
    for code in [Code::FormatUndeclared, Code::FormatDefinitionInvalid, Code::FormatMismatch] {
        assert_eq!(p.report.count(code), 0, "{}", p.report);
    }
}

#[test]
fn a_definition_whose_printed_vector_does_not_hash_is_invalid() {
    let (m, files) = with_format(&"0".repeat(64), TOY_PAYLOAD, "toy-format");
    let p = Package::open(write("format-badvector.werk", &m, &files)).unwrap();
    assert_eq!(count(&p, Code::FormatDefinitionInvalid, Severity::Warn), 1, "{}", p.report);
    assert_eq!(p.formats_read, 0);
    // The bytes are intact and verified either way (law 3): no error.
    assert_eq!(p.report.errors(), 0);
}

#[test]
fn a_node_naming_a_format_the_package_does_not_define_is_reported() {
    let (m, files) = with_format(&sha256_hex(TOY_PAYLOAD), TOY_PAYLOAD, "some-other-format");
    let p = Package::open(write("format-undeclared.werk", &m, &files)).unwrap();
    assert_eq!(count(&p, Code::FormatUndeclared, Severity::Warn), 1, "{}", p.report);
}

#[test]
fn a_payload_that_is_not_what_its_node_declares_is_reported() {
    let (m, files) = with_format(&sha256_hex(TOY_PAYLOAD), b"NOPE", "toy-format");
    let p = Package::open(write("format-mismatch.werk", &m, &files)).unwrap();
    assert_eq!(count(&p, Code::FormatMismatch, Severity::Warn), 1, "{}", p.report);
}

#[test]
fn a_declared_format_beats_a_sniff() {
    // The payload begins `WKX0` and is NOT an envelope: its node says what it
    // is, so it is not examined as one, and the node is not killed for having
    // a broken envelope frame.
    let (mut m, mut files) = fixture();
    let payload = b"WKX0 but really the toy format";
    let def = String::from_utf8(toy_definition(&sha256_hex(TOY_PAYLOAD)))
        .unwrap()
        .replace("\"sniff\": [{\"magic\": [{\"offset\": 0, \"hex\": \"544f59\"}]}]",
                 "\"sniff\": [{\"rule\": \"none\", \"note\": \"a test format with nothing to recognise it by\"}]");
    put(&mut m, &mut files, "spec", "spec/formats/toy-format.md", def.as_bytes());
    m["formats"] = json!({"toy-format": "spec/formats/toy-format.md"});
    add_node(&mut m, &mut files, "original", "x.test.original", "original/file.toy", payload,
             Some(json!({"payload_format": "toy-format"})));
    respec(&mut m);
    let p = Package::open(write("format-beats-sniff.werk", &m, &files)).unwrap();
    assert!(!p.node("original").unwrap().status.is_dead(), "{}", p.report);
    assert_eq!(p.report.count(Code::EnvelopeInvalid), 0, "{}", p.report);
}

#[test]
fn the_legacy_per_node_map_still_resolves() {
    // Packages written for a reference profile before its schema admitted
    // `formats` carry the same map as meta.format_definitions.
    let (mut m, files) = with_format(&sha256_hex(TOY_PAYLOAD), TOY_PAYLOAD, "toy-format");
    m.as_object_mut().unwrap().remove("formats");
    node_mut(&mut m, "original")["meta"]["format_definitions"] =
        json!({"toy-format": "spec/formats/toy-format.md"});
    let p = Package::open(write("format-legacy.werk", &m, &files)).unwrap();
    assert_eq!(p.formats_read, 1, "{}", p.report);
    assert_eq!(p.report.count(Code::FormatUndeclared), 0, "{}", p.report);
}

// ---------------------------------------------------------------------------
// SPEC 3.20 — an extension that changes how a core payload is shown
// ---------------------------------------------------------------------------

#[test]
fn a_core_node_modified_by_a_skipped_extension_says_so() {
    let (mut m, files) = fixture();
    // The fixture's x-probe node is an extension this reader skips.
    node_mut(&mut m, "geom-game")["meta"] = json!({"modified_by": ["x-probe"]});
    let p = Package::open(write("modified-by.werk", &m, &files)).unwrap();
    let hits: Vec<_> = p.report.entries.iter().filter(|e| e.code == Code::ModifiedBySkippedNode).collect();
    assert_eq!(hits.len(), 1, "{}", p.report);
    assert_eq!(hits[0].node_id.as_deref(), Some("geom-game"));
    assert_eq!(hits[0].severity, Severity::Warn);
    assert_eq!(p.node("geom-game").unwrap().status, NodeStatus::Alive);
}

// ---------------------------------------------------------------------------
// Container — deflate and zip64
// ---------------------------------------------------------------------------

/// A raw DEFLATE stream of stored blocks: valid, and needs no compressor.
fn deflate_stored(data: &[u8]) -> Vec<u8> {
    let mut out = Vec::new();
    let mut chunks = data.chunks(0xFFFF).peekable();
    if data.is_empty() {
        out.extend_from_slice(&[1, 0, 0, 0xFF, 0xFF]);
    }
    while let Some(c) = chunks.next() {
        out.push(u8::from(chunks.peek().is_none()));
        out.extend_from_slice(&(c.len() as u16).to_le_bytes());
        out.extend_from_slice(&(!(c.len() as u16)).to_le_bytes());
        out.extend_from_slice(c);
    }
    out
}

/// Rewrite the fixture as a zip in which `deflated` names are method 8.
fn zip_with_method8(dest: &Path, deflated: &[&str], corrupt_crc: bool) {
    let z = ZipArchive::parse(std::fs::read(repo().join("tests/fixtures/crate.werk")).unwrap()).unwrap();
    let mut body = Vec::new();
    let mut central = Vec::new();
    let mut n = 0u16;
    for name in z.names() {
        let data = z.read(&name).unwrap();
        let m8 = deflated.contains(&name.as_str());
        let stored = if m8 { deflate_stored(&data) } else { data.clone() };
        let mut crc = crc32(&data);
        if m8 && corrupt_crc {
            crc ^= 1;
        }
        let method: u16 = if m8 { 8 } else { 0 };
        let off = body.len() as u32;
        let nb = name.as_bytes();
        body.extend_from_slice(&0x0403_4b50u32.to_le_bytes());
        for v in [20u16, 0x0800, method, 0, 0] {
            body.extend_from_slice(&v.to_le_bytes());
        }
        for v in [crc, stored.len() as u32, data.len() as u32] {
            body.extend_from_slice(&v.to_le_bytes());
        }
        body.extend_from_slice(&(nb.len() as u16).to_le_bytes());
        body.extend_from_slice(&0u16.to_le_bytes());
        body.extend_from_slice(nb);
        body.extend_from_slice(&stored);
        central.extend_from_slice(&0x0201_4b50u32.to_le_bytes());
        for v in [20u16, 20, 0x0800, method, 0, 0] {
            central.extend_from_slice(&v.to_le_bytes());
        }
        for v in [crc, stored.len() as u32, data.len() as u32] {
            central.extend_from_slice(&v.to_le_bytes());
        }
        for v in [nb.len() as u16, 0, 0, 0, 0] {
            central.extend_from_slice(&v.to_le_bytes());
        }
        central.extend_from_slice(&0u32.to_le_bytes());
        central.extend_from_slice(&off.to_le_bytes());
        central.extend_from_slice(nb);
        n += 1;
    }
    let cd_off = body.len() as u32;
    let cd_size = central.len() as u32;
    body.extend_from_slice(&central);
    body.extend_from_slice(&0x0605_4b50u32.to_le_bytes());
    for v in [0u16, 0, n, n] {
        body.extend_from_slice(&v.to_le_bytes());
    }
    body.extend_from_slice(&cd_size.to_le_bytes());
    body.extend_from_slice(&cd_off.to_le_bytes());
    body.extend_from_slice(&0u16.to_le_bytes());
    std::fs::write(dest, body).unwrap();
}

#[test]
fn a_package_whose_every_entry_is_deflated_opens_like_its_stored_twin() {
    let dest = tmp("all-deflated.werk");
    let z = ZipArchive::parse(std::fs::read(repo().join("tests/fixtures/crate.werk")).unwrap()).unwrap();
    let names = z.names();
    let all: Vec<&str> = names.iter().map(String::as_str).collect();
    zip_with_method8(&dest, &all, false);
    let p = Package::open(&dest).unwrap();
    let stored = Package::open(repo().join("tests/fixtures/crate.werk")).unwrap();
    assert_eq!(p.deflated_entries(), names.len());
    assert_eq!(p.report.errors(), 0, "{}", p.report);
    assert_eq!(p.manifest_sha256(), stored.manifest_sha256());
    assert_eq!(p.signature_state, stored.signature_state, "the signature is over the manifest's bytes, not the container's");
    assert_eq!(p.nodes.len(), stored.nodes.len());
}

#[test]
fn a_deflated_entry_that_inflates_to_the_wrong_bytes_is_damage_to_that_entry() {
    let dest = tmp("deflated-badcrc.werk");
    zip_with_method8(&dest, &["LICENSE"], true);
    let p = Package::open(&dest).unwrap();
    assert!(p.node("license").unwrap().status.is_dead(), "{}", p.report);
    assert_eq!(p.report.count(Code::ZipEntryInvalid), 1, "{}", p.report);
    assert_eq!(p.report.count(Code::FileMissing), 0, "the entry is there; it is damaged, and is called that");
    assert_eq!(p.node("spec").unwrap().status, NodeStatus::Alive);
}

#[test]
fn a_method_other_than_store_and_deflate_is_refused_for_that_entry_by_name() {
    let mut bytes = std::fs::read(repo().join("tests/fixtures/crate.werk")).unwrap();
    let mut i = 0;
    let mut patched = false;
    while i + 46 < bytes.len() {
        if &bytes[i..i + 4] == b"PK\x01\x02" {
            let nlen = u16::from_le_bytes([bytes[i + 28], bytes[i + 29]]) as usize;
            if &bytes[i + 46..i + 46 + nlen] == b"LICENSE" {
                bytes[i + 10] = 12; // bzip2
                patched = true;
                break;
            }
        }
        i += 1;
    }
    assert!(patched);
    let dest = tmp("method12.werk");
    std::fs::write(&dest, &bytes).unwrap();
    let p = Package::open(&dest).unwrap();
    assert!(p.node("license").unwrap().status.is_dead());
    assert_eq!(p.report.count(Code::ZipEntryUnsupported), 1, "{}", p.report);
    assert_eq!(p.report.count(Code::FileMissing), 0, "{}", p.report);
}

#[test]
fn zip64_is_refused_whole_by_name_and_is_a_container_refusal() {
    // The zip64 locator immediately before the EOCD, and a count sentinel:
    // synthetic here, and measured against two REAL zip64 archives by
    // tests/run_gate_container.py.
    let good = std::fs::read(repo().join("tests/fixtures/crate.werk")).unwrap();
    let eocd = good.len() - 22;
    for which in ["sentinel", "locator"] {
        let mut bytes = good.clone();
        match which {
            "sentinel" => {
                bytes[eocd + 10] = 0xFF;
                bytes[eocd + 11] = 0xFF;
            }
            _ => {
                let mut loc = vec![0x50, 0x4b, 0x06, 0x07];
                loc.extend_from_slice(&[0u8; 16]);
                bytes.splice(eocd..eocd, loc);
            }
        }
        let dest = tmp(&format!("zip64-{which}.werk"));
        std::fs::write(&dest, &bytes).unwrap();
        match Package::open(&dest) {
            Err(e @ Error::Zip64Unsupported(_)) => {
                assert_eq!(e.tag(), "zip64-unsupported");
                assert!(e.is_container_refusal());
                assert!(e.to_string().contains("DIRECTORY form"), "{e}");
            }
            Err(e) => panic!("{which}: refused under the wrong name: {e}"),
            Ok(_) => panic!("{which}: a zip64 container was opened"),
        }
    }
}

// ---------------------------------------------------------------------------
// The reference's own consistency (ruling 8)
// ---------------------------------------------------------------------------

#[test]
fn the_example_manifest_validates_against_the_schema_it_illustrates() {
    // F-AC-1: spec/README.md called spec/examples/MANIFEST.example.json
    // schema-valid for as long as it lacked the mandatory spec_sha256.
    let text = std::fs::read_to_string(repo().join("spec/examples/MANIFEST.example.json")).unwrap();
    let inst: Value = serde_json::from_str(&text).unwrap();
    for schema in [werk::manifest::MANIFEST_SCHEMA, werk::manifest::MANIFEST_SCHEMA_BASE] {
        let errs = Validator::new(schema).unwrap().validate(&inst);
        assert!(errs.is_empty(), "{:?}", errs.iter().map(|e| e.to_string()).collect::<Vec<_>>());
    }
}

#[test]
fn every_reference_manifest_schema_refines_the_base_shape() {
    // What the base requires, each profile schema requires too.
    let base: Value = serde_json::from_str(werk::manifest::MANIFEST_SCHEMA_BASE).unwrap();
    for (name, text) in [("3d-entity/1", werk::manifest::MANIFEST_SCHEMA),
                         ("image/1", werk::manifest::MANIFEST_SCHEMA_IMAGE)] {
        let s: Value = serde_json::from_str(text).unwrap();
        let req: Vec<&str> = s["required"].as_array().unwrap().iter().filter_map(Value::as_str).collect();
        for r in base["required"].as_array().unwrap() {
            assert!(req.contains(&r.as_str().unwrap()), "{name} does not require `{r}`");
        }
        for (k, pin) in base["properties"]["conventions"]["properties"].as_object().unwrap() {
            assert_eq!(s["properties"]["conventions"]["properties"][k]["const"], pin["const"],
                       "{name} pins base convention `{k}` differently");
        }
        for key in ["formats", "profile_spec", "manifest_schema"] {
            assert!(s["properties"].get(key).is_some(), "{name} does not admit `{key}`");
        }
    }
}

#[test]
fn canonical_json_writes_non_ascii_as_itself() {
    // F-AC-2, the vector of spec/MINI-SPECS.md section 3.
    let v = json!({"n": 1, "name": "Größe", "note": "a→b", "tab": "x\ty"});
    let c = canonical_json(&v);
    assert_eq!(c, "{\"n\":1,\"name\":\"Größe\",\"note\":\"a→b\",\"tab\":\"x\\ty\"}");
    assert_eq!(c.len(), 52);
    assert_eq!(sha256_hex(c.as_bytes()),
               "13a2906649470c284a45bc33763ca934e41edd18e32e764443acfd4aba11baa6");
}
