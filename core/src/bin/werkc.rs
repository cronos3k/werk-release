//! `werkc` — the reference tool. Two jobs:
//!
//!   werkc info    <pkg>            list nodes, statuses and the load report
//!   werkc verify  <pkg>            verify every file. Exit status is SPEC.md
//!                                  section 10.1's: 0 opened and no `error`
//!                                  entry; 1 opened, at least one `error`
//!                                  entry; 2 container-scoped refusal (nothing
//!                                  could be loaded)
//!   werkc build-fixture <out-dir>  build the conformance fixture from real
//!                                  bytes taken out of spec/
//!
//! The fixture is SYNTHETIC but not fake: every sha256 in it is the hash of
//! bytes that are actually in the package, the WKRP binary is produced by this
//! crate's envelope writer and is byte-identical to the one
//! spec/examples/make-examples.py emits, and the signature chain verifies with
//! the RFC 8032 test key.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use werk::envelope::{self, SectionSpec};
use werk::msgpack::Mp;
use werk::package::Package;
use werk::signature::Signer_;

const CREATED: &str = "2026-08-08T09:00:00Z";

/// RFC 8032 test vector 1's secret key, quoted in spec/MINI-SPECS.md section
/// 12. It is PUBLIC by construction — that is the point of a test vector, and a
/// fixture must never carry a real key.
const FIXTURE_SK: &str = "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60";

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let code = match args.get(1).map(String::as_str) {
        Some("info") => cmd_info(args.get(2)),
        Some("verify") => cmd_verify(args.get(2)),
        Some("build-fixture") => cmd_build(args.get(2)),
        _ => {
            eprintln!(
                "werkc {} — werk reference tool\n\n\
                 usage:\n  werkc info <package>\n  werkc verify <package>\n  \
                 werkc build-fixture <out-dir>",
                werk::VERSION
            );
            2
        }
    };
    std::process::exit(code);
}

/// A failed open, printed the way a report entry is printed and under the same
/// code, and mapped to SPEC.md section 10.1's exit status. Before ruling 9 of
/// 2026-10-13 every failed open was "cannot open" with status 1, so a zip64
/// container and a package with one corrupt texture exited alike.
fn refuse(e: &werk::Error) -> i32 {
    eprintln!("[error] {}", e);
    if e.is_container_refusal() {
        eprintln!("container-scoped refusal: nothing was loaded; exit status 2");
        2
    } else {
        1
    }
}

/// The census every command prints: how many nodes ended up in each of the
/// three states. It is the line a gate asserts exact numbers against.
fn census(p: &Package) -> (usize, usize, usize) {
    let mut c = (0, 0, 0);
    for n in &p.nodes {
        match n.status {
            werk::NodeStatus::Alive => c.0 += 1,
            werk::NodeStatus::Skipped(_) => c.1 += 1,
            werk::NodeStatus::Dead(_) => c.2 += 1,
        }
    }
    c
}

fn print_summary(p: &Package) {
    let (alive, skipped, dead) = census(p);
    println!("profile    : {}", p.manifest.profile());
    println!("manifest   : sha256 {}", p.manifest_sha256());
    println!("validated  : {}", p.manifest_validation.as_str());
    // The fixed state word first (SPEC section 10 step 4: the token is not
    // free prose), the reason after it.
    match &p.signature_state {
        werk::signature::SignatureState::Invalid(r)
        | werk::signature::SignatureState::Unverified(r) => {
            println!("signature  : {} — {}", p.signature_state.word(), r)
        }
        s => println!("signature  : {}", s.word()),
    }
    println!(
        "census     : {} nodes: {} alive, {} skipped, {} dead",
        p.nodes.len(),
        alive,
        skipped,
        dead
    );
    println!("envelopes  : {} validated structurally", p.envelopes_validated);
    println!("payloads   : {} JSON payload(s) validated against the package's own schemas", p.payloads_validated);
    println!(
        "formats    : {} definition(s) read, {} printed test-vector input(s) re-hashed",
        p.formats_read, p.format_vectors_checked
    );
    if p.deflated_entries() > 0 {
        println!("container  : {} entr(ies) stored deflated (zip method 8) and inflated", p.deflated_entries());
    }
}

fn cmd_info(path: Option<&String>) -> i32 {
    let path = match path {
        Some(p) => p,
        None => return 2,
    };
    match Package::open(path) {
        Err(e) => refuse(&e),
        Ok(p) => {
            println!("entity     : {} ({})", p.manifest.entity_name(), p.manifest.entity_uuid());
            print_summary(&p);
            for n in &p.nodes {
                println!(
                    "  {:<16} {:<22} active={} resolved={} {}",
                    n.view.node_id,
                    n.view.ntype,
                    n.view.active,
                    n.resolved.map(|v| v.to_string()).unwrap_or_else(|| "-".into()),
                    match &n.status {
                        werk::NodeStatus::Alive => "alive".to_string(),
                        werk::NodeStatus::Skipped(r) => format!("SKIPPED: {r}"),
                        werk::NodeStatus::Dead(r) => format!("DEAD: {r}"),
                    }
                );
            }
            println!("report     : {} entries", p.report.entries.len());
            print!("{}", p.report);
            0
        }
    }
}

fn cmd_verify(path: Option<&String>) -> i32 {
    let path = match path {
        Some(p) => p,
        None => return 2,
    };
    match Package::open(path) {
        Err(e) => refuse(&e),
        Ok(p) => {
            print!("{}", p.report);
            print_summary(&p);
            let errs = p.report.errors();
            println!("{} error(s), {} report entries", errs, p.report.entries.len());
            i32::from(errs > 0)
        }
    }
}

// ---------------------------------------------------------------------------
// Fixture
// ---------------------------------------------------------------------------

fn repo_root() -> PathBuf {
    // core/src/bin/werkc.rs -> core/ -> repo root
    Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap().to_path_buf()
}

/// A spec or loader TEXT file whose bytes contain a carriage return is not the
/// repository's file (.gitattributes: text=auto eol=lf): it is a working tree
/// checked out before that rule existed, which git reports clean. Embedding it
/// writes a package whose `spec_sha256` no other checkout can reproduce
/// (finding F-AC-6; tools/spec_sha256.py `translated_text` is the same rule
/// for the Python builders).
fn refuse_translated_text(rel: &str, bytes: &[u8]) {
    const TEXT: &[&str] = &[".md", ".json", ".txt", ".py", ".rs", ".c", ".h"];
    if TEXT.iter().any(|s| rel.ends_with(s)) && bytes.contains(&b'\r') {
        eprintln!(
            "REFUSING TO BUILD: {rel} contains carriage returns in this working tree; \
             its bytes are not the repository's. Delete it and `git checkout -- {rel}`."
        );
        std::process::exit(2);
    }
}

fn spec_file(rel: &str) -> (String, Vec<u8>) {
    let p = repo_root().join(rel);
    let bytes = std::fs::read(&p).unwrap_or_else(|e| panic!("cannot read {}: {e}", p.display()));
    refuse_translated_text(rel, &bytes);
    (rel.replace('\\', "/"), bytes)
}

fn cmd_build(out: Option<&String>) -> i32 {
    let out = PathBuf::from(out.map(String::as_str).unwrap_or("tests/fixtures"));
    std::fs::create_dir_all(&out).expect("create output directory");

    // --- payload bytes -------------------------------------------------
    let mut files: BTreeMap<String, Vec<u8>> = BTreeMap::new();

    for rel in [
        "spec/README.md",
        "spec/SPEC.md",
        "spec/MINI-SPECS.md",
        "spec/facets.json",
        "spec/schemas/manifest.schema.json",
        // The base shape every profile refines (SPEC.md section 2.2).
        "spec/schemas/manifest.base.schema.json",
        "spec/schemas/signature.schema.json",
        "spec/schemas/core.material.schema.json",
        "spec/schemas/core.phys.bounds.schema.json",
        "spec/schemas/core.semantics.schema.json",
        "spec/schemas/core.provenance.schema.json",
        "spec/conventions-map.json",
        "spec/schemas/conventions-map.schema.json",
        "spec/layouts/ENVELOPE.layout.txt",
        "spec/layouts/restposes.layout.txt",
        // Added when profile 2 arrived: SPEC.md now points at these, and a
        // spec that travels inside an artifact has to be re-read AS an
        // artifact whenever the roadmap moves (the S-16 lesson).
        "spec/PROFILE-IMAGE.md",
        "spec/X-C2PA-EXPORT.md",
        "spec/schemas/manifest.image.schema.json",
        "spec/schemas/core.recipe.schema.json",
        "spec/schemas/core.disclosure.schema.json",
        "spec/schemas/x.c2pa.export.schema.json",
        "spec/layouts/embedding.layout.txt",
    ] {
        let (k, v) = spec_file(rel);
        files.insert(k, v);
    }

    let mut loader_caps: BTreeMap<String, Vec<String>> = BTreeMap::new();
    let mut loader_nodes: Vec<(&str, &str, &str, &str, &str)> = Vec::new();
    for (rel, lang, tool, build) in [
        ("loaders/werk_read.py", "python", "python>=3.8", ""),
        ("loaders/werk_read.rs", "rust", "rustc>=1.70 --edition 2021", "rustc -O --edition 2021 -o werk_read werk_read.rs"),
        ("loaders/werk_read.c", "c", "c99", "cc -std=c99 -O2 -o werk_read werk_read.c"),
    ] {
        let p = repo_root().join(rel);
        match std::fs::read(&p) {
            Ok(b) => {
                refuse_translated_text(rel, &b);
                loader_caps.insert(rel.to_string(), capabilities_of(&b));
                files.insert(rel.to_string(), b);
                let node_id: &'static str = Box::leak(
                    format!("loader-{lang}").into_boxed_str(),
                );
                loader_nodes.push((node_id, rel, lang, tool, build));
            }
            Err(_) => eprintln!("note: {rel} is absent; the fixture will not carry that loader"),
        }
    }

    files.insert("LICENSE".into(), LICENSE_TEXT.as_bytes().to_vec());
    files.insert("README.txt".into(), README_TEXT.as_bytes().to_vec());
    files.insert("geometry/game.glb".into(), minimal_glb(1.0));
    files.insert("geometry/lod1.glb".into(), minimal_glb(0.75));
    files.insert("textures/crate-basecolor.png".into(), tiny_png());
    files.insert("poses/rest.wkrp".into(), rest_poses_wkrp());
    files.insert("x/test/blob.bin".into(), b"werk fixture: an extension payload no core reader interprets\n".to_vec());

    let tex = files["textures/crate-basecolor.png"].clone();
    let _ = tex;

    files.insert("materials/oak-slats.json".into(), pretty(&serde_json::json!({
        "material_id": "oak-slats",
        "name": "Oak slats",
        "model": "metallic-roughness",
        "base_color_factor": [0.72, 0.55, 0.34, 1.0],
        "metallic_factor": 0.0,
        "roughness_factor": 0.68,
        "alpha_mode": "opaque",
        "double_sided": false,
        "ior": 1.5,
        "textures": {
            "base_color": {
                "node": "tex-basecolor",
                "path": "textures/crate-basecolor.png",
                "uv_set": 0
            }
        },
        "epistemic": "authored",
        "note": "Fixture material. Values are plausible for oak and are authored, not measured."
    })));

    files.insert("physics/bounds.json".into(), pretty(&serde_json::json!({
        "schema_version": 1,
        "space": "model",
        "entity": {
            "aabb_min": [-0.25, 0.0, -0.25],
            "aabb_max": [0.25, 0.5, 0.25],
            "sphere_center": [0.0, 0.25, 0.0],
            "sphere_radius": 0.4145781,
            "sphere_method": "welzl-exact",
            "surface_area_m2": 0.75,
            "volume_m3": 0.125,
            "watertight": true,
            "longest_axis_m": 0.5
        },
        "epistemic": "measured",
        "note": "Computed from geometry/game.glb with the true minimal sphere, not the sphere circumscribing the box."
    })));

    files.insert("semantics/semantics.json".into(), pretty(&serde_json::json!({
        "schema_version": 1,
        "facets_version": 1,
        "facets": {
            "function": ["container", "prop"],
            "condition": ["worn"],
            "scale-class": ["handheld"]
        },
        "palette": {
            "method": "authored",
            "colors": [
                {"hex_srgb": "#b88c57", "linear_rgb": [0.4793, 0.2582, 0.0953], "weight": 0.78, "name": "oak"},
                {"hex_srgb": "#3f3a35", "linear_rgb": [0.0508, 0.0439, 0.0368], "weight": 0.22, "name": "iron"}
            ],
            "dominant_index": 0,
            "average_luminance": 0.29
        },
        "description": "A small wooden crate, used here as the werk conformance fixture. Everything about it is deliberately minimal so a reader can be checked by hand.",
        "keywords": ["fixture", "crate", "conformance"],
        "note": "Facet tags are illustrative; registry membership is checked against spec/facets.json, which travels in this package."
    })));

    files.insert("provenance/provenance.json".into(), pretty(&serde_json::json!({
        "schema_version": 1,
        "runs": [{
            "run_id": "fixture-build",
            "started": CREATED,
            "finished": CREATED,
            "tool": {"name": "werkc", "version": werk::VERSION},
            "produced": [
                {"node_id": "geom-game", "v": 1},
                {"node_id": "geom-lod1", "v": 1},
                {"node_id": "rest-poses", "v": 1}
            ],
            "note": "Built by werkc build-fixture from bytes that are all present in this package. No model was involved; nothing here is inferred by a machine."
        }]
    })));

    // --- manifest ------------------------------------------------------
    // Written once with a placeholder preview_prefix_bytes, then iterated to a
    // fixed point: the prefix length depends on the manifest's own size, and
    // the manifest declares the prefix length.
    let mut preview_prefix: u64 = 0;
    let mut manifest_bytes;
    let mut zip_bytes;
    let mut round = 0;
    loop {
        let manifest = build_manifest(&files, &loader_nodes, &loader_caps, preview_prefix);
        // SPEC section 5: never write an edge to an absent node.
        if let Err(e) = werk::manifest::refuse_dangling_edges(&manifest) {
            eprintln!("werkc build-fixture: {e}");
            return 1;
        }
        manifest_bytes = pretty(&manifest);

        // Sign, so the fixture exercises signed-and-valid.
        let sig = werk::signature::append_entry(
            None,
            &manifest_bytes,
            FIXTURE_SK,
            &Signer_ {
                name: "werk fixture key (RFC 8032 test vector 1)".into(),
                uri: "urn:werk:fixture:rfc8032-vector-1".into(),
                kind: "service".into(),
                role: Some("author".into()),
                note: Some(
                    "Signed with a PUBLICLY KNOWN test key so the chain can be verified by anyone \
                     reading spec/MINI-SPECS.md section 12. It proves nothing about authorship and \
                     is not a trust anchor."
                        .into(),
                ),
                signed_at: CREATED.into(),
            },
        )
        .expect("sign fixture");
        let sig_bytes = pretty(&sig);

        let mut all: BTreeMap<String, Vec<u8>> = files.clone();
        all.insert("MANIFEST.json".into(), manifest_bytes.clone());
        all.insert("SIGNATURE.json".into(), sig_bytes);

        let order = entry_order_expanded(&all);
        let entries: Vec<(String, Vec<u8>)> =
            order.iter().map(|p| (p.clone(), all[p].clone())).collect();
        zip_bytes = werk::zipstore::write_zip(&entries);

        // The prefix ends where the first non-preview entry's local header
        // starts, measured on the bytes actually written.
        let mut cursor: u64 = 0;
        let mut prefix: u64 = 0;
        for (name, data) in &entries {
            let this = 30 + name.len() as u64 + data.len() as u64;
            if is_preview(name) {
                prefix = cursor + this;
            }
            cursor += this;
        }
        if prefix == preview_prefix {
            break;
        }
        preview_prefix = prefix;
        round += 1;
        assert!(round < 8, "preview_prefix_bytes did not converge");
    }

    let zip_path = out.join("crate.werk");
    std::fs::write(&zip_path, &zip_bytes).expect("write fixture");

    // A directory form of exactly the same package: SPEC section 1 says both
    // are the format, so both are fixtures.
    let dir_path = out.join("crate");
    let _ = std::fs::remove_dir_all(&dir_path);
    let p = Package::open(&zip_path).expect("reopen fixture");
    p.materialize_dir(&dir_path).expect("materialize");

    println!("wrote {} ({} bytes)", zip_path.display(), zip_bytes.len());
    println!("wrote {}/ (directory form)", dir_path.display());
    println!("sha256 {}", werk::hashing::sha256_hex(&zip_bytes));
    println!("preview_prefix_bytes {preview_prefix}");
    println!("nodes {} report {}", p.nodes.len(), p.report.entries.len());
    print!("{}", p.report);
    if p.report.errors() > 0 {
        eprintln!("FIXTURE HAS {} ERROR(S)", p.report.errors());
        return 1;
    }
    0
}

/// The capability list a loader's own source declares: the words after
/// `WERK-LOADER-CAPABILITIES:` on the one line that carries it.
fn capabilities_of(source: &[u8]) -> Vec<String> {
    let text = String::from_utf8_lossy(source);
    let line = text
        .lines()
        .take(200)
        .find_map(|l| l.split_once("WERK-LOADER-CAPABILITIES:").map(|(_, rest)| rest.to_string()))
        .expect("the loader states its capabilities in a WERK-LOADER-CAPABILITIES: line");
    line.replace("*/", " ").split_whitespace().map(str::to_string).collect()
}

const PREVIEW_PREFIXES: &[&str] = &[
    "MANIFEST.json", "SIGNATURE.json", "LICENSE", "README.txt", "loaders/", "spec/", "semantics/",
];

fn is_preview(name: &str) -> bool {
    PREVIEW_PREFIXES
        .iter()
        .any(|p| if p.ends_with('/') { name.starts_with(p) } else { name == *p })
}

fn entry_order_expanded(all: &BTreeMap<String, Vec<u8>>) -> Vec<String> {
    let mut remaining: Vec<String> = all.keys().cloned().collect();
    let mut out = Vec::new();
    for pat in ENTRY_ORDER {
        let picked: Vec<String> = remaining
            .iter()
            .filter(|p| if pat.ends_with('/') { p.starts_with(pat) } else { *p == pat })
            .cloned()
            .collect();
        for p in picked {
            remaining.retain(|x| x != &p);
            out.push(p);
        }
    }
    out.extend(remaining);
    out
}

const ENTRY_ORDER: &[&str] = &[
    "MANIFEST.json",
    "SIGNATURE.json",
    "LICENSE",
    "README.txt",
    "loaders/",
    "spec/",
    "semantics/",
    "materials/",
    "physics/",
    "poses/",
    "provenance/",
    "geometry/",
    "textures/",
    "x/",
];

fn pretty(v: &serde_json::Value) -> Vec<u8> {
    let mut s = serde_json::to_string_pretty(v).unwrap();
    s.push('\n');
    s.into_bytes()
}

fn fref(files: &BTreeMap<String, Vec<u8>>, path: &str, media: Option<&str>, role: Option<&str>) -> serde_json::Value {
    let b = &files[path];
    let mut o = serde_json::Map::new();
    o.insert("path".into(), serde_json::json!(path));
    o.insert("sha256".into(), serde_json::json!(werk::hashing::sha256_hex(b)));
    o.insert("size".into(), serde_json::json!(b.len()));
    if let Some(m) = media {
        o.insert("media_type".into(), serde_json::json!(m));
    }
    if let Some(r) = role {
        o.insert("role".into(), serde_json::json!(r));
    }
    serde_json::Value::Object(o)
}

fn input_hash_of(files: &BTreeMap<String, Vec<u8>>, inputs: &[&str]) -> String {
    let digests: Vec<[u8; 32]> = inputs.iter().map(|p| werk::hashing::sha256(&files[*p])).collect();
    werk::hashing::input_hash(&digests, "{}")
}

/// The manifest's mandatory `spec_sha256` (S-29, ruled 2026-08-08): one hash
/// over the spec/ tree the package carries, so a reader can tell in one
/// comparison whether the schemas travelling inside a file are the ones it
/// already knows.
///
/// Sort spec/ paths ascending by UTF-8 bytes; for each append
/// `path || 0x0A || sha256(bytes) as 32 RAW bytes || 0x0A`; hash the lot. The
/// paths are in the hash, so moving a file changes it, and note that for a
/// single file the result is NOT that file's own sha256. Normative statement
/// of the algorithm: spec/SPEC.md section 2. Reference implementation:
/// tools/spec_sha256.py. `BTreeMap` already iterates in byte order, which is
/// the sort this asks for.
fn spec_sha256(files: &BTreeMap<String, Vec<u8>>) -> String {
    let mut acc: Vec<u8> = Vec::new();
    for (path, bytes) in files.iter().filter(|(k, _)| k.starts_with("spec/")) {
        acc.extend_from_slice(path.as_bytes());
        acc.push(b'\n');
        acc.extend_from_slice(&werk::hashing::sha256(bytes));
        acc.push(b'\n');
    }
    werk::hashing::sha256_hex(&acc)
}

#[allow(clippy::too_many_arguments)]
fn build_manifest(
    files: &BTreeMap<String, Vec<u8>>,
    loaders: &[(&str, &str, &str, &str, &str)],
    loader_caps: &BTreeMap<String, Vec<String>>,
    preview_prefix: u64,
) -> serde_json::Value {
    use serde_json::json;

    let mut nodes: Vec<serde_json::Value> = Vec::new();

    let spec_files: Vec<serde_json::Value> = files
        .keys()
        .filter(|k| k.starts_with("spec/"))
        .map(|k| {
            let media = if k.ends_with(".json") {
                Some("application/json")
            } else if k.ends_with(".md") {
                Some("text/markdown")
            } else {
                Some("text/plain")
            };
            fref(files, k, media, None)
        })
        .collect();

    nodes.push(json!({
        "node_id": "spec", "type": "core.spec",
        "versions": [{
            "v": 1, "files": spec_files,
            "note": "The specification this package conforms to, travelling inside it so the file explains itself (law 2).",
            "producer": {"tool": "werkc", "version": werk::VERSION},
            "epistemic": "authored", "created": CREATED
        }],
        "active": 1, "edges": []
    }));

    nodes.push(json!({
        "node_id": "license", "type": "core.license",
        "versions": [{
            "v": 1, "files": [fref(files, "LICENSE", Some("text/plain"), None)],
            "note": "Full licence text embedded, never a link (law 7).",
            "producer": {"tool": "werkc", "version": werk::VERSION},
            "epistemic": "authored", "created": CREATED
        }],
        "active": 1, "edges": []
    }));

    nodes.push(json!({
        "node_id": "readme", "type": "core.readme",
        "versions": [{
            "v": 1, "files": [fref(files, "README.txt", Some("text/plain"), None)],
            "note": "One paragraph for a human who opened the archive by hand.",
            "producer": {"tool": "werkc", "version": werk::VERSION},
            "epistemic": "authored", "created": CREATED
        }],
        "active": 1, "edges": []
    }));

    for (node_id, rel, lang, toolchain, build_command) in loaders {
        let media = match *lang {
            "python" => "text/x-python",
            "rust" => "text/x-rust",
            _ => "text/x-c",
        };
        let mut meta = serde_json::Map::new();
        meta.insert("language".into(), json!(lang));
        meta.insert("form".into(), json!("source"));
        meta.insert("entrypoint".into(), json!(rel));
        meta.insert("toolchain".into(), json!(toolchain));
        if !build_command.is_empty() {
            meta.insert("build_command".into(), json!(build_command));
        }
        meta.insert("dependencies".into(), json!([]));
        meta.insert(
            "capabilities".into(),
            // What a loader does is stated by the loader, in one
            // `WERK-LOADER-CAPABILITIES:` line, and read from the bytes being
            // embedded. This used to be a literal here, and in seven other
            // writers, and they had drifted from the loaders (finding F-AC-4,
            // the S-19 failure again).
            json!(loader_caps[*rel]),
        );
        nodes.push(json!({
            "node_id": node_id, "type": "core.loader",
            "versions": [{
                "v": 1, "files": [fref(files, rel, Some(media), None)],
                "note": "Single-file zero-dependency bootstrap reader, so the package carries a way to read itself (law 1).",
                "producer": {"tool": "werkc", "version": werk::VERSION},
                "epistemic": "authored", "created": CREATED
            }],
            "active": 1, "edges": [], "meta": serde_json::Value::Object(meta)
        }));
    }

    nodes.push(json!({
        "node_id": "geom-game", "type": "core.geom.game", "part_id": "crate",
        "versions": [{
            "v": 1, "files": [fref(files, "geometry/game.glb", Some("model/gltf-binary"), None)],
            "note": "Authored game mesh: the representation every consumer can use without a cook step.",
            "producer": {"tool": "werkc", "version": werk::VERSION},
            "epistemic": "authored", "created": CREATED
        }],
        "active": 1, "edges": []
    }));

    nodes.push(json!({
        "node_id": "geom-lod1", "type": "core.geom.lod", "part_id": "crate",
        "versions": [{
            "v": 1, "files": [fref(files, "geometry/lod1.glb", Some("model/gltf-binary"), None)],
            "note": "First decimation step; the silhouette error is measured against the game mesh, not estimated.",
            "producer": {"tool": "werkc", "version": werk::VERSION},
            "epistemic": "measured", "created": CREATED,
            "input_files": ["geometry/game.glb"],
            "input_hash": input_hash_of(files, &["geometry/game.glb"]),
            "input_params": {}
        }],
        "active": 1,
        "edges": [{"to": "geom-game", "kind": "requires", "role": "lod-of"}],
        "meta": {
            "lod_level": 1, "screen_space_error_px": 2.4,
            "reference_resolution_px": 1080, "triangle_count": 1, "vertex_count": 3
        }
    }));

    nodes.push(json!({
        "node_id": "tex-basecolor", "type": "core.tex", "material_id": "oak-slats",
        "versions": [{
            "v": 1, "files": [fref(files, "textures/crate-basecolor.png", Some("image/png"), None)],
            "note": "Base colour map, deliberately 8x8 so a reader can hand-check every texel.",
            "producer": {"tool": "werkc", "version": werk::VERSION},
            "epistemic": "authored", "created": CREATED
        }],
        "active": 1, "edges": [],
        "meta": {"color_space": "srgb", "usage": "base-color", "width": 8, "height": 8,
                 "channels": 4, "bit_depth": 8}
    }));

    nodes.push(json!({
        "node_id": "mat-oak", "type": "core.material", "material_id": "oak-slats",
        "versions": [{
            "v": 1, "files": [fref(files, "materials/oak-slats.json", Some("application/json"), None)],
            "note": "Metallic-roughness parameters for the slatted oak body.",
            "producer": {"tool": "werkc", "version": werk::VERSION},
            "epistemic": "authored", "created": CREATED
        }],
        "active": 1,
        "edges": [{"to": "tex-basecolor", "kind": "enhances", "role": "sampled-by"}]
    }));

    nodes.push(json!({
        "node_id": "bounds", "type": "core.phys.bounds",
        "versions": [{
            "v": 1, "files": [fref(files, "physics/bounds.json", Some("application/json"), None)],
            "note": "AABB and true minimal sphere, computed with Welzl rather than circumscribing the box.",
            "producer": {"tool": "werkc", "version": werk::VERSION},
            "epistemic": "measured", "created": CREATED,
            "input_files": ["geometry/game.glb"],
            "input_hash": input_hash_of(files, &["geometry/game.glb"]),
            "input_params": {}
        }],
        "active": 1,
        "edges": [{"to": "geom-game", "kind": "requires", "role": "measured-from"}]
    }));

    nodes.push(json!({
        "node_id": "rest-poses", "type": "core.pose.rest",
        "versions": [{
            "v": 1, "files": [fref(files, "poses/rest.wkrp", None, None)],
            "note": "Settled orientations from a drop simulation; probabilities are measured over the trials recorded in the envelope header.",
            "producer": {"tool": "werkc", "version": werk::VERSION},
            "epistemic": "measured", "created": CREATED,
            "input_files": ["geometry/game.glb", "physics/bounds.json"],
            "input_hash": input_hash_of(files, &["geometry/game.glb", "physics/bounds.json"]),
            "input_params": {}
        }],
        "active": 1,
        "edges": [{"to": "geom-game", "kind": "enhances", "role": "measured-from"}]
    }));

    nodes.push(json!({
        "node_id": "semantics", "type": "core.semantics",
        "versions": [{
            "v": 1, "files": [fref(files, "semantics/semantics.json", Some("application/json"), None)],
            "note": "Facet tags and palette; a store can index a dropped file from this node alone (law 9).",
            "producer": {"tool": "werkc", "version": werk::VERSION},
            "epistemic": "inferred", "created": CREATED, "confidence": 0.7,
            "input_files": ["textures/crate-basecolor.png"],
            "input_hash": input_hash_of(files, &["textures/crate-basecolor.png"]),
            "input_params": {}
        }],
        "active": 1, "edges": []
    }));

    nodes.push(json!({
        "node_id": "provenance", "type": "core.provenance",
        "versions": [{
            "v": 1, "files": [fref(files, "provenance/provenance.json", Some("application/json"), None)],
            "note": "How this package came to exist: one run, its tool, and what it produced.",
            "producer": {"tool": "werkc", "version": werk::VERSION},
            "epistemic": "authored", "created": CREATED
        }],
        "active": 1, "edges": []
    }));

    // Law 12 in the fixture itself: an extension node no core reader knows.
    // A conformant reader must list it, hash it, and skip it WITH A REPORT.
    nodes.push(json!({
        "node_id": "x-probe", "type": "x.werk-test.probe",
        "versions": [{
            "v": 1, "files": [fref(files, "x/test/blob.bin", Some("application/octet-stream"), None)],
            "note": "An extension payload that exists so every reader can be checked against the unknown-type path.",
            "producer": {"tool": "werkc", "version": werk::VERSION},
            "epistemic": "authored", "created": CREATED
        }],
        "active": 1, "edges": []
    }));

    let mut container = serde_json::Map::new();
    container.insert("form".into(), json!("zip"));
    container.insert("zip_compression".into(), json!("store"));
    container.insert("entry_order".into(), json!(ENTRY_ORDER));
    if preview_prefix > 0 {
        container.insert("preview_prefix_bytes".into(), json!(preview_prefix));
    }

    json!({
        "werk": {"major": 1, "minor": 0},
        "profile": "3d-entity/1",
        "entity": {
            "uuid": "6f1c2b7a-9d3e-4a10-8c55-2b8e41d0a7c3",
            "name": "Wooden crate (conformance fixture)",
            "summary": "The werk conformance fixture. Small on purpose: every payload is minimal enough to check by hand, every sha256 is the hash of bytes that are actually here, the WKRP binary is byte-identical to the worked example in spec/examples/, and the signature chain verifies with the RFC 8032 test key quoted in spec/MINI-SPECS.md section 12.",
            "created": CREATED
        },
        "conventions": {
            "endianness": "le", "units_per_meter": 1.0, "length_unit": "metre",
            "angle_unit": "radian", "time_unit": "second", "mass_unit": "kilogram",
            "up_axis": "y", "forward_axis": "-z", "right_axis": "+x",
            "handedness": "right", "winding": "ccw", "quat_order": "wxyz",
            "oct_encoding_pole": "y", "sh_l1_order": ["dc", "y", "z", "x"],
            "color_space_default": "srgb", "uv_origin": "top-left",
            "alignment_bytes": 16, "text_encoding": "utf-8", "id_case": "kebab-case",
            "hash_algorithm": "sha256", "signature_algorithm": "ed25519"
        },
        "container": serde_json::Value::Object(container),
        "license": {
            "spdx_id": "MIT", "file": "LICENSE",
            "sha256": werk::hashing::sha256_hex(&files["LICENSE"])
        },
        "spec_sha256": spec_sha256(files),
        "conventions_map": "spec/conventions-map.json",
        "schemas": {
            "core.material": "spec/schemas/core.material.schema.json",
            "core.phys.bounds": "spec/schemas/core.phys.bounds.schema.json",
            "core.semantics": "spec/schemas/core.semantics.schema.json",
            "core.provenance": "spec/schemas/core.provenance.schema.json"
        },
        "layouts": {"core.pose.rest": "spec/layouts/restposes.layout.txt"},
        "parts": [
            {"part_id": "crate", "name": "Crate body", "parent": serde_json::Value::Null,
             "transform": {"translation": [0.0, 0.0, 0.0], "rotation": [1.0, 0.0, 0.0, 0.0],
                           "scale": [1.0, 1.0, 1.0]}}
        ],
        "materials": [
            {"material_id": "oak-slats", "part_id": "crate", "name": "Oak slats", "class": "wood"}
        ],
        "nodes": nodes,
        "signature_file": "SIGNATURE.json",
        "generator": {"tool": "werkc", "version": werk::VERSION}
    })
}

// ---------------------------------------------------------------------------
// Payload generators — every byte deterministic
// ---------------------------------------------------------------------------

/// The same two-pose WKRP that spec/examples/make-examples.py emits, built
/// through this crate's envelope writer. A test asserts the two are identical.
pub fn rest_poses_wkrp() -> Vec<u8> {
    let poses: Vec<([f32; 4], Vec<[f32; 3]>, f32, f32)> = vec![
        (
            [1.0, 0.0, 0.0, 0.0],
            vec![[-0.25, 0.0, -0.25], [0.25, 0.0, -0.25], [0.25, 0.0, 0.25], [-0.25, 0.0, 0.25]],
            0.62,
            0.25,
        ),
        (
            [0.707_106_77, 0.707_106_77, 0.0, 0.0],
            vec![[-0.25, 0.0, -0.21], [0.25, 0.0, -0.21], [0.0, 0.0, 0.21]],
            0.38,
            0.105,
        ),
    ];
    let mut entries = Vec::new();
    let mut contacts: Vec<[f32; 3]> = Vec::new();
    for (q, pts, prob, area) in &poses {
        let first = contacts.len() as u32;
        contacts.extend_from_slice(pts);
        for c in q {
            entries.extend_from_slice(&c.to_le_bytes());
        }
        entries.extend_from_slice(&first.to_le_bytes());
        entries.extend_from_slice(&(pts.len() as u32).to_le_bytes());
        entries.extend_from_slice(&prob.to_le_bytes());
        entries.extend_from_slice(&area.to_le_bytes());
    }
    let mut contact_blob = Vec::new();
    for c in &contacts {
        for x in c {
            contact_blob.extend_from_slice(&x.to_le_bytes());
        }
    }

    let mut extra = std::collections::BTreeMap::new();
    extra.insert("trials".to_string(), Mp::UInt(4096));
    extra.insert(
        "floor_normal".to_string(),
        Mp::Array(vec![Mp::Float(0.0), Mp::Float(1.0), Mp::Float(0.0)]),
    );
    extra.insert("settle_epsilon_m".to_string(), Mp::Float(0.0005));
    extra.insert("merge_angle_deg".to_string(), Mp::Float(5.0));
    extra.insert(
        "producer".to_string(),
        werk::msgpack::map(vec![
            ("tool", Mp::Str("werk-example".into())),
            ("version", Mp::Str("0.1".into())),
        ]),
    );
    extra.insert("epistemic".to_string(), Mp::Str("measured".into()));
    extra.insert("pose_count".to_string(), Mp::UInt(poses.len() as u64));
    extra.insert("contact_count".to_string(), Mp::UInt(contacts.len() as u64));

    envelope::build(
        b"WKRP",
        1,
        extra,
        "core.pose.rest",
        &[
            SectionSpec {
                name: "poses".into(),
                dtype: "record".into(),
                shape: vec![poses.len() as u64],
                stride: 32,
                data: entries,
            },
            SectionSpec {
                name: "contacts".into(),
                dtype: "f32".into(),
                shape: vec![contacts.len() as u64, 3],
                stride: 12,
                data: contact_blob,
            },
        ],
    )
}

/// An 8x8 RGBA PNG, written with STORED deflate blocks so no compressor is
/// needed. spec/MINI-SPECS.md section 8 is the reference.
pub fn tiny_png() -> Vec<u8> {
    let (w, h) = (8usize, 8usize);
    let mut raw = Vec::with_capacity(h * (1 + w * 4));
    for y in 0..h {
        raw.push(0u8); // filter type 0 = None
        for x in 0..w {
            let plank = ((y / 2) % 2) as u8;
            let r = 168 + plank * 20 + (x as u8 % 3) * 3;
            let g = 128 + plank * 16 + (x as u8 % 3) * 2;
            let b = 82 + plank * 10;
            raw.extend_from_slice(&[r, g, b, 255]);
        }
    }
    let mut png = vec![0x89, b'P', b'N', b'G', 0x0d, 0x0a, 0x1a, 0x0a];
    let mut ihdr = Vec::new();
    ihdr.extend_from_slice(&(w as u32).to_be_bytes());
    ihdr.extend_from_slice(&(h as u32).to_be_bytes());
    ihdr.extend_from_slice(&[8, 6, 0, 0, 0]); // bit depth 8, colour type 6 (RGBA)
    push_chunk(&mut png, b"IHDR", &ihdr);
    push_chunk(&mut png, b"IDAT", &zlib_stored(&raw));
    push_chunk(&mut png, b"IEND", &[]);
    png
}

fn push_chunk(out: &mut Vec<u8>, kind: &[u8; 4], data: &[u8]) {
    out.extend_from_slice(&(data.len() as u32).to_be_bytes());
    out.extend_from_slice(kind);
    out.extend_from_slice(data);
    let mut crc_input = kind.to_vec();
    crc_input.extend_from_slice(data);
    out.extend_from_slice(&werk::zipstore::crc32(&crc_input).to_be_bytes());
}

/// A zlib stream made only of STORED deflate blocks. Legal, trivially
/// decodable, and it means the fixture needs no compressor.
fn zlib_stored(data: &[u8]) -> Vec<u8> {
    let mut out = vec![0x78, 0x01];
    let mut i = 0;
    while i < data.len() {
        let n = (data.len() - i).min(0xFFFF);
        let last = u8::from(i + n >= data.len());
        out.push(last); // BFINAL, BTYPE=00 (stored)
        out.extend_from_slice(&(n as u16).to_le_bytes());
        out.extend_from_slice(&(!(n as u16)).to_le_bytes());
        out.extend_from_slice(&data[i..i + n]);
        i += n;
    }
    out.extend_from_slice(&adler32(data).to_be_bytes());
    out
}

fn adler32(data: &[u8]) -> u32 {
    let (mut a, mut b) = (1u32, 0u32);
    for &x in data {
        a = (a + x as u32) % 65521;
        b = (b + a) % 65521;
    }
    (b << 16) | a
}

/// A minimal glTF 2.0 binary: one indexed triangle with POSITION and NORMAL,
/// per SPEC.md section 3.10 ("mode 4, indexed, POSITION and NORMAL required").
pub fn minimal_glb(scale: f32) -> Vec<u8> {
    let positions: [[f32; 3]; 3] = [
        [-0.25 * scale, 0.0, -0.25 * scale],
        [0.25 * scale, 0.0, -0.25 * scale],
        [0.0, 0.5 * scale, 0.25 * scale],
    ];
    let normals: [[f32; 3]; 3] = [[0.0, 0.0, -1.0]; 3];
    let indices: [u16; 3] = [0, 1, 2];

    let mut bin = Vec::new();
    for p in &positions {
        for c in p {
            bin.extend_from_slice(&c.to_le_bytes());
        }
    }
    let n_off = bin.len();
    for p in &normals {
        for c in p {
            bin.extend_from_slice(&c.to_le_bytes());
        }
    }
    let i_off = bin.len();
    for i in &indices {
        bin.extend_from_slice(&i.to_le_bytes());
    }
    while bin.len() % 4 != 0 {
        bin.push(0);
    }
    let i_len = 6;

    let min = [
        positions.iter().map(|p| p[0]).fold(f32::INFINITY, f32::min),
        positions.iter().map(|p| p[1]).fold(f32::INFINITY, f32::min),
        positions.iter().map(|p| p[2]).fold(f32::INFINITY, f32::min),
    ];
    let max = [
        positions.iter().map(|p| p[0]).fold(f32::NEG_INFINITY, f32::max),
        positions.iter().map(|p| p[1]).fold(f32::NEG_INFINITY, f32::max),
        positions.iter().map(|p| p[2]).fold(f32::NEG_INFINITY, f32::max),
    ];

    let gltf = serde_json::json!({
        "asset": {"version": "2.0", "generator": "werkc fixture builder"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": "crate"}],
        "meshes": [{"primitives": [{
            "mode": 4,
            "attributes": {"POSITION": 0, "NORMAL": 1},
            "indices": 2
        }]}],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3",
             "min": min, "max": max},
            {"bufferView": 1, "componentType": 5126, "count": 3, "type": "VEC3"},
            {"bufferView": 2, "componentType": 5123, "count": 3, "type": "SCALAR"}
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": n_off},
            {"buffer": 0, "byteOffset": n_off, "byteLength": i_off - n_off},
            {"buffer": 0, "byteOffset": i_off, "byteLength": i_len}
        ],
        "buffers": [{"byteLength": bin.len()}]
    });
    let mut json_chunk = serde_json::to_vec(&gltf).unwrap();
    while json_chunk.len() % 4 != 0 {
        json_chunk.push(b' ');
    }

    let total = 12 + 8 + json_chunk.len() + 8 + bin.len();
    let mut out = Vec::with_capacity(total);
    out.extend_from_slice(b"glTF");
    out.extend_from_slice(&2u32.to_le_bytes());
    out.extend_from_slice(&(total as u32).to_le_bytes());
    out.extend_from_slice(&(json_chunk.len() as u32).to_le_bytes());
    out.extend_from_slice(b"JSON");
    out.extend_from_slice(&json_chunk);
    out.extend_from_slice(&(bin.len() as u32).to_le_bytes());
    out.extend_from_slice(b"BIN\0");
    out.extend_from_slice(&bin);
    out
}

const README_TEXT: &str = "\
This is a werk package. Everything needed to read it is inside it.

Start with spec/README.md, which indexes the format. loaders/ holds
single-file, dependency-free readers in Python, Rust and C: any one of them
will list the nodes and verify every hash without installing anything. The
manifest, MANIFEST.json, is the single source of structure; SIGNATURE.json
carries the custody chain, and its absence would be a legitimate state
rather than an error.

This particular package is the conformance fixture: deliberately small, with
real hashes over real bytes, so a new reader can be checked against it by
hand.
";

const LICENSE_TEXT: &str = "\
MIT License

Copyright (c) 2026 Gregor Koch

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the \"Software\"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
";
