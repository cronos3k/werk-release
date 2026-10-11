//! The Stage 2 gate, as tests rather than claims.
//!
//! ROADMAP Stage 2: "round-trip byte-identity on untouched nodes; damage
//! gauntlet passes; the same .werk opens from Rust, C++ and Python through the
//! one DLL; each embedded bootstrap reader parses the golden sample
//! standalone." The first two and the version/signature behaviour are measured
//! here. The C++ and Python faces are measured by `tests/cpp/smoke.cpp` and
//! `tests/run_gate.py`, which drive the same shared library.
//!
//! Everything is written under `core/target/test-tmp/`, inside the project.

use std::path::{Path, PathBuf};
use werk::hashing::sha256_hex;
use werk::package::{NewFile, NewVersion, OpenOptions, Package};
use werk::report::Code;
use werk::signature::{SignatureState, Signer_};
use werk::zipstore::{write_zip, ZipArchive};
use werk::NodeStatus;

const FIXTURE_SK: &str = "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60";

fn repo() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap().to_path_buf()
}

fn fixture_zip() -> PathBuf {
    repo().join("tests/fixtures/crate.werk")
}

fn fixture_dir() -> PathBuf {
    repo().join("tests/fixtures/crate")
}

fn tmp(name: &str) -> PathBuf {
    let d = Path::new(env!("CARGO_MANIFEST_DIR")).join("target/test-tmp");
    std::fs::create_dir_all(&d).unwrap();
    d.join(name)
}

/// Rebuild the fixture zip with surgical damage applied, preserving entry order.
fn rebuild<F>(dest: &Path, mutate: F) -> PathBuf
where
    F: Fn(&str, Vec<u8>) -> Option<Vec<u8>>,
{
    let z = ZipArchive::parse(std::fs::read(fixture_zip()).unwrap()).unwrap();
    let mut entries = Vec::new();
    for name in z.names() {
        let data = z.read(&name).unwrap();
        if let Some(d) = mutate(&name, data) {
            entries.push((name, d));
        }
    }
    let bytes = write_zip(&entries);
    std::fs::write(dest, bytes).unwrap();
    dest.to_path_buf()
}

fn flip_last_byte(mut v: Vec<u8>) -> Vec<u8> {
    let n = v.len();
    v[n - 1] ^= 0xFF;
    v
}

// ---------------------------------------------------------------------------
// The fixture itself
// ---------------------------------------------------------------------------

#[test]
fn fixture_opens_clean() {
    let p = Package::open(fixture_zip()).expect("fixture opens");
    assert_eq!(p.report.errors(), 0, "clean fixture must produce zero errors:\n{}", p.report);
    assert_eq!(p.signature_state, SignatureState::Valid);
    assert_eq!(p.manifest.profile(), "3d-entity/1");
    assert!(p.nodes.len() >= 12, "fixture should exercise a real graph");
    // Every node except the deliberate x.* probe is alive.
    for n in &p.nodes {
        match n.view.ntype.starts_with("x.") {
            true => assert!(matches!(n.status, NodeStatus::Skipped(_)),
                            "{} should be skipped", n.view.node_id),
            false => assert_eq!(n.status, NodeStatus::Alive, "{} should be alive", n.view.node_id),
        }
    }
    // "Nothing floats."
    assert_eq!(p.report.count(Code::FloatingFile), 0);
}

/// The envelope writer must agree with spec/examples/make-examples.py BYTE FOR
/// BYTE. That script is the executable statement of the envelope rules, so this
/// is the one test that proves the Rust implementation and the spec agree
/// rather than merely both being plausible.
#[test]
fn envelope_writer_matches_the_spec_example_byte_for_byte() {
    let expected = std::fs::read(repo().join("spec/examples/restposes.example.wkrp")).unwrap();
    let p = Package::open(fixture_zip()).unwrap();
    let ours = p.blob("poses/rest.wkrp").unwrap();
    assert_eq!(
        ours.len(),
        expected.len(),
        "length differs: ours {} vs spec {}",
        ours.len(),
        expected.len()
    );
    assert_eq!(*ours, expected, "the WKRP bytes differ from the spec's worked example");
    assert_eq!(
        sha256_hex(&expected),
        "6c2c44d5492a4e4f1dbcf5b4c30beb5ada4825ffba7ab7e5010040494ee15f95",
        "the spec example itself changed; re-derive before trusting this test"
    );
}

#[test]
fn envelope_parses_and_declares_what_it_contains() {
    let p = Package::open(fixture_zip()).unwrap();
    let bytes = p.blob("poses/rest.wkrp").unwrap();
    let env = werk::envelope::parse(&bytes).expect("envelope parses");
    assert_eq!(&env.magic, b"WKRP");
    assert_eq!(env.kind(), Some("core.pose.rest"));
    assert_eq!(env.payload_origin, 400);
    assert_eq!(env.payload_origin + env.payload_size, bytes.len() as u64);
    let poses = env.section("poses").unwrap();
    assert_eq!((poses.offset, poses.size, poses.stride), (400, 64, 32));
    let contacts = env.section("contacts").unwrap();
    assert_eq!((contacts.offset, contacts.size, contacts.stride), (464, 84, 12));
    werk::envelope::check_finite(&env, &bytes).expect("no NaN or infinity in a core payload");
}

// ---------------------------------------------------------------------------
// GATE 1 — round-trip byte identity
// ---------------------------------------------------------------------------

#[test]
fn gate_round_trip_zip_is_byte_identical() {
    let original = std::fs::read(fixture_zip()).unwrap();
    let p = Package::open(fixture_zip()).unwrap();
    let out = tmp("roundtrip.werk");
    let written = p.write_zip(&out).unwrap();
    assert_eq!(
        sha256_hex(&written),
        sha256_hex(&original),
        "read -> write must reproduce the container byte for byte"
    );
    assert_eq!(written.len(), original.len());
}

#[test]
fn gate_round_trip_survives_the_directory_form() {
    // SPEC section 1: "Directory and zip layouts are identical. Both are the
    // format." So dir -> zip must land on the same bytes as zip -> zip.
    let original = std::fs::read(fixture_zip()).unwrap();
    let p = Package::open(fixture_dir()).expect("directory form opens");
    assert_eq!(p.report.errors(), 0, "{}", p.report);
    let out = tmp("from-dir.werk");
    let written = p.write_zip(&out).unwrap();
    assert_eq!(
        sha256_hex(&written),
        sha256_hex(&original),
        "the directory form must re-emit the identical container"
    );
}

#[test]
fn gate_round_trip_through_a_materialised_directory() {
    let original = std::fs::read(fixture_zip()).unwrap();
    let dir = tmp("materialised");
    let _ = std::fs::remove_dir_all(&dir);
    let p = Package::open(fixture_zip()).unwrap();
    let n = p.materialize_dir(&dir).unwrap();
    assert!(n > 10);
    let again = Package::open(&dir).unwrap();
    assert_eq!(again.report.errors(), 0, "{}", again.report);
    let out = tmp("from-materialised.werk");
    assert_eq!(sha256_hex(&again.write_zip(&out).unwrap()), sha256_hex(&original));
}

// ---------------------------------------------------------------------------
// GATE 2 — the damage gauntlet
// ---------------------------------------------------------------------------

/// One corrupt payload, one missing payload, and an unknown node type. The
/// package must still load, the damage must be exact, and everything not
/// downstream of the damage must be untouched.
#[test]
fn gate_damage_gauntlet() {
    let dest = tmp("damaged.werk");
    rebuild(&dest, |name, data| match name {
        // A corrupt texture: one flipped byte, still the right length.
        "textures/crate-basecolor.png" => Some(flip_last_byte(data)),
        // A missing payload: the manifest still declares it.
        "semantics/semantics.json" => None,
        _ => Some(data),
    });

    let p = Package::open(&dest).expect("a damaged package still opens");

    let status = |id: &str| p.node(id).unwrap_or_else(|| panic!("no node {id}")).status.clone();

    // -- the damage, exactly ------------------------------------------
    assert!(status("tex-basecolor").is_dead(), "a corrupt file kills its node");
    assert!(status("semantics").is_dead(), "a missing file kills its node");
    assert_eq!(p.report.count(Code::HashMismatch), 1, "exactly one hash mismatch");
    assert_eq!(p.report.count(Code::FileMissing), 1, "exactly one missing file");

    // -- the island rule ----------------------------------------------
    for id in ["spec", "license", "readme", "geom-game", "geom-lod1", "bounds",
               "rest-poses", "provenance", "loader-python", "loader-rust", "loader-c"] {
        assert_eq!(status(id), NodeStatus::Alive, "{id} is not downstream of the damage");
    }

    // -- edges: enhances costs one feature, requires kills -------------
    // mat-oak ENHANCES the dead texture, so it survives and reports the loss.
    assert_eq!(status("mat-oak"), NodeStatus::Alive, "an enhances edge must not kill");
    assert_eq!(p.report.count(Code::EnhancesDeadNode), 1);

    // -- law 12: an unknown type degrades through the same path ---------
    assert!(matches!(status("x-probe"), NodeStatus::Skipped(_)));
    assert_eq!(p.report.count(Code::NodeSkippedUnknownType), 1);
    assert_eq!(
        p.node("x-probe").unwrap().resolved,
        Some(1),
        "a skipped node's bytes are still verified and reachable"
    );
    assert!(p.blob("x/test/blob.bin").is_ok());

    // -- the signature is a SEPARATE question from the damage -----------
    // The manifest did not change, so the chain still verifies. Detecting the
    // corrupt payload is the per-file hash's job, not the signature's, and a
    // reader that conflated the two would report the wrong thing.
    assert_eq!(p.signature_state, SignatureState::Valid);

    // -- and the load did not fail --------------------------------------
    assert!(p.nodes.len() >= 12);
    assert!(p.report.errors() >= 2);
}

/// A `requires` edge into a dead node kills the source, transitively.
#[test]
fn gate_damage_requires_edge_cascades() {
    let dest = tmp("damaged-geom.werk");
    rebuild(&dest, |name, data| {
        if name == "geometry/game.glb" {
            Some(flip_last_byte(data))
        } else {
            Some(data)
        }
    });
    let p = Package::open(&dest).unwrap();
    assert!(p.node("geom-game").unwrap().status.is_dead());
    // geom-lod1 and bounds both `require` geom-game.
    assert!(p.node("geom-lod1").unwrap().status.is_dead(), "requires must cascade");
    assert!(p.node("bounds").unwrap().status.is_dead(), "requires must cascade");
    assert_eq!(p.report.count(Code::RequiresDeadNode), 2);
    // rest-poses only ENHANCES it: one feature lost, node alive.
    assert_eq!(p.node("rest-poses").unwrap().status, NodeStatus::Alive);
    assert_eq!(p.report.count(Code::EnhancesDeadNode), 1);
    // Untouched islands are untouched.
    assert_eq!(p.node("spec").unwrap().status, NodeStatus::Alive);
    assert_eq!(p.node("semantics").unwrap().status, NodeStatus::Alive);
}

/// A `requires` edge to a node that is ABSENT from nodes[] kills the source
/// exactly as a dead target would, and the death cascades. An `enhances` edge
/// to an absent node costs one feature. A `requires` edge into a SKIPPED node
/// kills nothing. The victim's files are still hash-checked. (SPEC section 5,
/// section 10 step 10.) Gate A runs the three bootstrap loaders on the same
/// shape of package (tests/run_gate_a.py).
#[test]
fn gate_damage_requires_edge_into_absent_node() {
    let dest = tmp("damaged-dangling.werk");
    let z = ZipArchive::parse(std::fs::read(fixture_zip()).unwrap()).unwrap();
    let mut manifest: serde_json::Value =
        serde_json::from_slice(&z.read("MANIFEST.json").unwrap()).unwrap();
    for node in manifest["nodes"].as_array_mut().unwrap() {
        let id = node["node_id"].as_str().unwrap().to_string();
        let edges = node["edges"].as_array_mut().unwrap();
        match id.as_str() {
            // the damage: a requires edge to an id that is in no node
            "semantics" => edges.push(serde_json::json!(
                {"to": "ghost-node", "kind": "requires", "role": "describes"})),
            // the cascade: a live node that requires the victim
            "provenance" => edges.push(serde_json::json!(
                {"to": "semantics", "kind": "requires", "role": "test-chain"})),
            // the control for kind: enhances to an absent node
            "mat-oak" => edges.push(serde_json::json!(
                {"to": "ghost-tex", "kind": "enhances", "role": "sampled-by"})),
            // the control for skipped: requires into a node of unknown type
            "rest-poses" => edges.push(serde_json::json!(
                {"to": "x-probe", "kind": "requires", "role": "test-skipped"})),
            // a node that is ALSO hash-dead: both facts are reported
            "bounds" => edges.push(serde_json::json!(
                {"to": "ghost-bounds", "kind": "requires", "role": "test-both"})),
            _ => {}
        }
    }
    let mut mtext = serde_json::to_string_pretty(&manifest).unwrap();
    mtext.push('\n');
    rebuild(&dest, |name, data| match name {
        "MANIFEST.json" => Some(mtext.clone().into_bytes()),
        "physics/bounds.json" => Some(flip_last_byte(data)),
        _ => Some(data),
    });

    let p = Package::open(&dest).expect("a dangling edge never fails the load");
    let status = |id: &str| p.node(id).unwrap_or_else(|| panic!("no node {id}")).status.clone();
    let on = |code: Code| -> Vec<String> {
        let mut v: Vec<String> = p
            .report
            .entries
            .iter()
            .filter(|e| e.code == code)
            .map(|e| e.node_id.clone().unwrap_or_default())
            .collect();
        v.sort();
        v
    };

    // absent == dead for `requires`, and it cascades
    assert!(status("semantics").is_dead(), "requires to an absent node kills");
    assert!(status("provenance").is_dead(), "and the kill cascades");
    assert_eq!(on(Code::RequiresMissingNode), ["bounds", "semantics"],
               "one requires-missing-node entry per dangling requires edge");
    assert_eq!(on(Code::RequiresDeadNode), ["provenance"]);

    // the victim's bytes were still verified, and are still reachable
    assert_eq!(on(Code::HashMismatch), ["bounds"], "hash check still runs on the victims");
    assert!(status("bounds").is_dead());
    assert!(p.blob("semantics/semantics.json").is_ok());

    // enhances to an absent node: one feature, node alive, and the dangling
    // requires edges are NOT also reported as edge-dangling
    assert_eq!(status("mat-oak"), NodeStatus::Alive);
    assert_eq!(on(Code::EdgeDangling), ["mat-oak"], "one entry, enhances only");

    // requires into a SKIPPED node is not fatal
    assert!(matches!(status("x-probe"), NodeStatus::Skipped(_)));
    assert_eq!(status("rest-poses"), NodeStatus::Alive);

    // island rule: nothing else is touched
    for id in ["spec", "license", "readme", "geom-game", "geom-lod1", "tex-basecolor",
               "loader-python", "loader-rust", "loader-c"] {
        assert_eq!(status(id), NodeStatus::Alive, "{id} is not downstream");
    }
    // SPEC 10.1 exit status: error entries exist, so a CLI exits 1
    assert!(p.report.errors() >= 4);
    // the manifest changed under the chain: a separate fact
    assert!(matches!(p.signature_state, SignatureState::Invalid(_)));
}

/// A payload whose bytes are intact but whose CONTENT violates the schema the
/// manifest points at. The node dies; nothing else does.
#[test]
fn gate_damage_invalid_payload_against_its_own_schema() {
    let dest = tmp("damaged-payload.werk");
    // Re-hash so the file passes verification and only the SCHEMA can catch it.
    let bad = br#"{"material_id":"oak-slats","name":"Oak slats","model":"phong",
                   "base_color_factor":[9,9,9,9],"metallic_factor":0.0,
                   "roughness_factor":0.68,"alpha_mode":"opaque","double_sided":false}"#
        .to_vec();
    let z = ZipArchive::parse(std::fs::read(fixture_zip()).unwrap()).unwrap();
    let mut manifest: serde_json::Value =
        serde_json::from_slice(&z.read("MANIFEST.json").unwrap()).unwrap();
    for node in manifest["nodes"].as_array_mut().unwrap() {
        if node["node_id"] == "mat-oak" {
            let f = &mut node["versions"][0]["files"][0];
            f["sha256"] = serde_json::json!(sha256_hex(&bad));
            f["size"] = serde_json::json!(bad.len());
        }
    }
    let mut mtext = serde_json::to_string_pretty(&manifest).unwrap();
    mtext.push('\n');
    rebuild(&dest, |name, data| match name {
        "materials/oak-slats.json" => Some(bad.clone()),
        "MANIFEST.json" => Some(mtext.clone().into_bytes()),
        _ => Some(data),
    });

    let p = Package::open(&dest).unwrap();
    assert_eq!(p.report.count(Code::HashMismatch), 0, "the bytes themselves are consistent");
    assert!(p.node("mat-oak").unwrap().status.is_dead(), "an invalid payload kills its node");
    assert!(p.report.count(Code::PayloadSchemaInvalid) >= 1);
    assert_eq!(p.node("tex-basecolor").unwrap().status, NodeStatus::Alive);
    // The manifest changed, so the existing chain must now read as INVALID —
    // and that is a different fact from the payload being wrong.
    assert!(matches!(p.signature_state, SignatureState::Invalid(_)));
}

/// A corrupt custom binary must fail the envelope assertions, not be guessed at.
#[test]
fn gate_damage_broken_envelope() {
    let dest = tmp("damaged-envelope.werk");
    let z = ZipArchive::parse(std::fs::read(fixture_zip()).unwrap()).unwrap();
    let mut wkrp = z.read("poses/rest.wkrp").unwrap();
    wkrp[8] = 0xFF; // header_len now runs past the end of the file
    let mut manifest: serde_json::Value =
        serde_json::from_slice(&z.read("MANIFEST.json").unwrap()).unwrap();
    for node in manifest["nodes"].as_array_mut().unwrap() {
        if node["node_id"] == "rest-poses" {
            node["versions"][0]["files"][0]["sha256"] = serde_json::json!(sha256_hex(&wkrp));
        }
    }
    let mut mtext = serde_json::to_string_pretty(&manifest).unwrap();
    mtext.push('\n');
    rebuild(&dest, |name, data| match name {
        "poses/rest.wkrp" => Some(wkrp.clone()),
        "MANIFEST.json" => Some(mtext.clone().into_bytes()),
        _ => Some(data),
    });
    let p = Package::open(&dest).unwrap();
    assert!(p.node("rest-poses").unwrap().status.is_dead());
    assert_eq!(p.report.count(Code::EnvelopeInvalid), 1);
    assert_eq!(p.node("geom-game").unwrap().status, NodeStatus::Alive);
}

// ---------------------------------------------------------------------------
// Signatures — three states, never two
// ---------------------------------------------------------------------------

#[test]
fn signature_three_states() {
    // 1. signed-and-valid
    let p = Package::open(fixture_zip()).unwrap();
    assert_eq!(p.signature_state, SignatureState::Valid);
    assert!(p.report.has(Code::SignatureValid));

    // 2. present-and-invalid: the manifest changed under the signature.
    let dest = tmp("tampered-manifest.werk");
    rebuild(&dest, |name, data| {
        if name == "MANIFEST.json" {
            let mut s = String::from_utf8(data).unwrap();
            s = s.replace("Wooden crate", "Wooden CRATE");
            Some(s.into_bytes())
        } else {
            Some(data)
        }
    });
    let bad = Package::open(&dest).unwrap();
    assert!(matches!(bad.signature_state, SignatureState::Invalid(_)));
    assert!(bad.report.has(Code::SignatureInvalid));
    assert!(!bad.report.has(Code::SignatureAbsent), "invalid must never read as absent");

    // 3. absent, and visibly so
    let dest = tmp("anonymous.werk");
    rebuild(&dest, |name, data| {
        if name == "SIGNATURE.json" {
            None
        } else {
            Some(data)
        }
    });
    let anon = Package::open(&dest).unwrap();
    assert_eq!(anon.signature_state, SignatureState::Absent);
    assert!(anon.report.has(Code::SignatureAbsent));
    assert_eq!(anon.report.errors(), 0, "anonymous is legitimate, not an error:\n{}", anon.report);
}

#[test]
fn signature_tampering_with_one_signature_byte_is_caught() {
    let dest = tmp("tampered-signature.werk");
    rebuild(&dest, |name, data| {
        if name == "SIGNATURE.json" {
            let s = String::from_utf8(data).unwrap();
            // Flip one hex digit of the signature itself.
            let i = s.find("\"signature\"").unwrap() + 16;
            let mut b = s.into_bytes();
            b[i] = if b[i] == b'a' { b'b' } else { b'a' };
            Some(b)
        } else {
            Some(data)
        }
    });
    let p = Package::open(&dest).unwrap();
    match &p.signature_state {
        SignatureState::Invalid(r) => assert!(
            r.contains("verification failed") || r.contains("hex"),
            "unexpected reason: {r}"
        ),
        other => panic!("a flipped signature byte must be caught, got {other:?}"),
    }
}

#[test]
fn signing_strips_and_resigns() {
    let mut p = Package::open(fixture_zip()).unwrap();
    p.strip_signature();
    assert_eq!(p.signature_state, SignatureState::Absent);

    p.sign_new_chain(
        FIXTURE_SK,
        Signer_ {
            name: "test".into(),
            uri: "urn:werk:test".into(),
            kind: "agent".into(),
            role: Some("review".into()),
            note: None,
            signed_at: "2026-08-08T12:00:00Z".into(),
        },
    )
    .unwrap();
    assert_eq!(p.signature_state, SignatureState::Valid);

    // A second signer appends to the same chain while the manifest is unchanged.
    p.sign(
        FIXTURE_SK,
        Signer_ {
            name: "second".into(),
            uri: "urn:werk:test-2".into(),
            kind: "human".into(),
            role: None,
            note: None,
            signed_at: "2026-08-08T12:01:00Z".into(),
        },
    )
    .unwrap();
    assert_eq!(p.signature_state, SignatureState::Valid);
    assert_eq!(
        p.signature_raw.as_ref().unwrap()["chain"].as_array().unwrap().len(),
        2
    );

    // Written out and reopened, it still verifies.
    let out = tmp("resigned.werk");
    p.write_zip(&out).unwrap();
    let again = Package::open(&out).unwrap();
    assert_eq!(again.signature_state, SignatureState::Valid);
}

/// SPEC FINDING S-1, RESOLVED, made executable: every chain entry carries its
/// own `manifest_sha256`, so enrichment can append a link and the earlier links
/// keep verifying — law 7's "enrichment appends; it never overwrites earlier
/// custody", now literally true. This test does the thing werk-core used to
/// refuse: change the manifest, append, and require the whole chain valid.
#[test]
fn signing_appends_across_a_manifest_change() {
    let mut p = Package::open(fixture_zip()).unwrap();
    p.append_version(
        "readme",
        NewVersion {
            files: vec![NewFile {
                path: "README.txt".into(),
                bytes: b"a second edition of the readme\n".to_vec(),
                media_type: Some("text/plain".into()),
                role: None,
            }],
            note: "Rewrote the readme so the append path has something to do.".into(),
            producer_tool: "conformance-test".into(),
            producer_version: "1".into(),
            producer_model: None,
            epistemic: "authored".into(),
            created: "2026-08-08T12:00:00Z".into(),
            input_files: vec![],
            input_params: None,
        },
    )
    .unwrap();
    // The manifest changed under the existing signature, so before re-signing
    // the package is present-and-invalid. That much is unchanged.
    assert!(matches!(p.signature_state, SignatureState::Invalid(_)));
    let manifest_before = p.manifest_sha256();

    // Appending is now the normal enrichment path, not a refusal.
    p.sign(
        FIXTURE_SK,
        Signer_ {
            name: "enricher".into(),
            uri: "urn:werk:test".into(),
            kind: "agent".into(),
            role: None,
            note: None,
            signed_at: "2026-08-08T12:05:00Z".into(),
        },
    )
    .unwrap();
    assert_eq!(p.signature_state, SignatureState::Valid);

    let sig = p.signature_raw.as_ref().unwrap();
    let chain = sig["chain"].as_array().unwrap();
    assert_eq!(chain.len(), 2, "the original author's link must survive");

    // The two entries sign two DIFFERENT manifest states, and only the newest
    // one is the state on disk. That is the whole point of the fix.
    let m0 = chain[0]["manifest_sha256"].as_str().unwrap();
    let m1 = chain[1]["manifest_sha256"].as_str().unwrap();
    assert_ne!(m0, m1, "entry 0 signs the state before the readme was rewritten");
    assert_eq!(m1, manifest_before);
    assert_eq!(m1, p.manifest_sha256());
    assert_eq!(sig["manifest_sha256"].as_str().unwrap(), m1,
               "the top-level anchor is a copy of the newest entry's, never a second authority");

    // Written out and reopened, the two-state chain still verifies.
    let out = tmp("enriched-then-signed.werk");
    p.write_zip(&out).unwrap();
    assert_eq!(Package::open(&out).unwrap().signature_state, SignatureState::Valid);
}

/// The other half of S-1's resolution: a chain whose LAST entry does not sign
/// the manifest on disk is still invalid. Per-entry hashes made the chain
/// survive enrichment; they must not have made tampering survive detection.
#[test]
fn a_chain_whose_newest_link_does_not_match_the_manifest_is_invalid() {
    let mut p = Package::open(fixture_zip()).unwrap();
    p.append_version("readme", authored("README.txt", b"tampered\n", "Tampered readme, unsigned."))
        .unwrap();
    match &p.signature_state {
        SignatureState::Invalid(_) => {}
        s => panic!("expected present-and-invalid, got {s:?}"),
    }
}

// ---------------------------------------------------------------------------
// Version operations
// ---------------------------------------------------------------------------

fn authored(path: &str, bytes: &[u8], note: &str) -> NewVersion {
    NewVersion {
        files: vec![NewFile {
            path: path.into(),
            bytes: bytes.to_vec(),
            media_type: Some("text/plain".into()),
            role: None,
        }],
        note: note.into(),
        producer_tool: "conformance-test".into(),
        producer_version: "1".into(),
        producer_model: None,
        epistemic: "authored".into(),
        created: "2026-08-08T12:00:00Z".into(),
        input_files: vec![],
        input_params: None,
    }
}

#[test]
fn append_version_is_append_only_and_moves_active() {
    let mut p = Package::open(fixture_zip()).unwrap();
    let v = p
        .append_version("readme", authored("README.txt", b"second edition\n",
                        "Rewrote the readme after the fixture grew a third loader."))
        .unwrap();
    assert_eq!(v, 2);
    let n = p.node("readme").unwrap();
    assert_eq!(n.view.active, 2);
    assert_eq!(n.view.versions.len(), 2, "law 6: the old version is never rewritten");
    assert_eq!(n.view.versions[0].v, 1);
    assert_eq!(n.resolved, Some(2));
    assert_eq!(p.blob("README.txt").unwrap().as_slice(), b"second edition\n");

    // It survives a write/reopen.
    let out = tmp("versioned.werk");
    p.write_zip(&out).unwrap();
    let again = Package::open(&out).unwrap();
    assert_eq!(again.node("readme").unwrap().resolved, Some(2));
    assert_eq!(again.node("readme").unwrap().view.versions.len(), 2);
}

/// SPEC section 5: if `active` is unusable, a resilient reader MAY fall back to
/// the newest valid earlier version and MUST report having done so.
#[test]
fn version_fallback_is_reported_not_silent() {
    let mut p = Package::open(fixture_zip()).unwrap();
    p.append_version(
        "readme",
        authored("README@2.txt", b"second edition\n",
                 "A second version whose bytes we are about to destroy."),
    )
    .unwrap();
    let out = tmp("fallback-src.werk");
    p.write_zip(&out).unwrap();

    // Now break v2's payload only.
    let dest = tmp("fallback.werk");
    let z = ZipArchive::parse(std::fs::read(&out).unwrap()).unwrap();
    let mut entries = Vec::new();
    for name in z.names() {
        let data = z.read(&name).unwrap();
        entries.push((name.clone(), if name == "README@2.txt" { flip_last_byte(data) } else { data }));
    }
    std::fs::write(&dest, write_zip(&entries)).unwrap();

    let p = Package::open(&dest).unwrap();
    let n = p.node("readme").unwrap();
    assert_eq!(n.view.active, 2);
    assert_eq!(n.resolved, Some(1), "must fall back to the newest valid earlier version");
    assert_eq!(n.status, NodeStatus::Alive, "a fallback is not a death");
    assert_eq!(p.report.count(Code::VersionFallback), 1, "the fallback MUST be reported");
    assert_eq!(p.blob("README.txt").unwrap().as_slice(),
               std::fs::read(fixture_dir().join("README.txt")).unwrap().as_slice());
}

#[test]
fn a_version_without_a_work_note_is_refused() {
    // Law 6 is not advisory. "update" is not a note.
    let mut p = Package::open(fixture_zip()).unwrap();
    let err = p.append_version("readme", authored("README.txt", b"x\n", "update")).unwrap_err();
    assert!(err.to_string().contains("work note"), "{err}");
}

#[test]
fn a_requires_edge_to_an_absent_node_is_refused_by_the_writer() {
    // SPEC section 5: a writer MUST NOT emit a dangling `requires` edge.
    let mut p = Package::open(fixture_zip()).unwrap();
    let node = |id: &str, edges: serde_json::Value| werk::NewNode {
        node_id: id.into(),
        ntype: "core.readme".into(),
        part_id: None,
        material_id: None,
        meta: None,
        edges,
        version: authored(&format!("{id}.txt"), b"x\n", "A node added to test the edge rule."),
    };
    let err = p
        .add_node(node("notes", serde_json::json!([{"to": "ghost-node", "kind": "requires"}])))
        .unwrap_err();
    assert!(err.to_string().contains("ghost-node"), "{err}");
    assert!(p.node("notes").is_none(), "a refused node is not half-added");
    // The same edge into a node that exists is fine.
    p.add_node(node("notes", serde_json::json!([{"to": "readme", "kind": "requires"}])))
        .unwrap();
    // The shared check werkc build-fixture uses.
    let m = serde_json::json!({"nodes": [
        {"node_id": "a", "edges": [{"to": "b", "kind": "requires"}]},
        {"node_id": "c", "edges": [{"to": "d", "kind": "enhances"}]}
    ]});
    assert_eq!(werk::manifest::dangling_edges(&m).len(), 2);
    let err = werk::manifest::refuse_dangling_requires(&m).unwrap_err();
    assert!(err.to_string().contains("`a` requires `b`"), "{err}");
    assert!(!err.to_string().contains("`d`"), "enhances is listed, not refused");
}

#[test]
fn derived_data_without_declared_inputs_is_refused() {
    // Law 5, machine-enforced.
    let mut p = Package::open(fixture_zip()).unwrap();
    let mut v = authored("README.txt", b"x\n", "A measured version with nothing to measure from.");
    v.epistemic = "measured".into();
    let err = p.append_version("readme", v).unwrap_err();
    assert!(err.to_string().contains("input_files"), "{err}");
}

#[test]
fn derived_input_hash_is_computed_and_then_checked() {
    let mut p = Package::open(fixture_zip()).unwrap();
    let mut v = authored("README.txt", b"derived\n",
                         "A derived version, so the input hash has something to cover.");
    v.epistemic = "measured".into();
    v.input_files = vec!["geometry/game.glb".into()];
    p.append_version("readme", v).unwrap();
    let node = p.node("readme").unwrap();
    let hash = node.view.versions[1].input_hash.clone().unwrap();
    assert_eq!(hash.len(), 64);
    // The reader recomputes it on load, so no staleness is reported.
    assert_eq!(p.report.count(Code::StaleDerivedData), 0, "{}", p.report);
}

#[test]
fn a_forged_input_hash_is_detected() {
    let dest = tmp("stale-derived.werk");
    let z = ZipArchive::parse(std::fs::read(fixture_zip()).unwrap()).unwrap();
    let mut manifest: serde_json::Value =
        serde_json::from_slice(&z.read("MANIFEST.json").unwrap()).unwrap();
    for node in manifest["nodes"].as_array_mut().unwrap() {
        if node["node_id"] == "bounds" {
            node["versions"][0]["input_hash"] = serde_json::json!("0".repeat(64));
        }
    }
    let mut mtext = serde_json::to_string_pretty(&manifest).unwrap();
    mtext.push('\n');
    rebuild(&dest, |name, data| {
        if name == "MANIFEST.json" {
            Some(mtext.clone().into_bytes())
        } else {
            Some(data)
        }
    });
    let p = Package::open(&dest).unwrap();
    assert_eq!(p.report.count(Code::StaleDerivedData), 1,
               "law 5 is validate-or-recompute, not trust:\n{}", p.report);
}

// ---------------------------------------------------------------------------
// Container and reader behaviour
// ---------------------------------------------------------------------------

#[test]
fn deflate_is_reported_unsupported_and_never_guessed() {
    // A method-8 entry must be refused, not decoded wrong (MINI-SPECS 5.3).
    let mut bytes = std::fs::read(fixture_zip()).unwrap();
    // Find the central-directory record for LICENSE and claim it is deflated.
    let needle = b"PK\x01\x02";
    let mut i = 0;
    let mut patched = false;
    while i + 46 < bytes.len() {
        if &bytes[i..i + 4] == needle {
            let nlen = u16::from_le_bytes([bytes[i + 28], bytes[i + 29]]) as usize;
            let name = String::from_utf8_lossy(&bytes[i + 46..i + 46 + nlen]).into_owned();
            if name == "LICENSE" {
                bytes[i + 10] = 8;
                patched = true;
                break;
            }
        }
        i += 1;
    }
    assert!(patched, "test could not find the LICENSE central directory record");
    let dest = tmp("deflated-claim.werk");
    std::fs::write(&dest, &bytes).unwrap();
    let p = Package::open(&dest).unwrap();
    assert!(p.node("license").unwrap().status.is_dead());
    assert_eq!(p.node("spec").unwrap().status, NodeStatus::Alive, "one bad entry is not a bad zip");
}

#[test]
fn skip_verify_is_faster_and_says_so_by_finding_nothing() {
    let dest = tmp("unverified.werk");
    rebuild(&dest, |name, data| {
        if name == "textures/crate-basecolor.png" {
            Some(flip_last_byte(data))
        } else {
            Some(data)
        }
    });
    let strict = Package::open(&dest).unwrap();
    assert!(strict.node("tex-basecolor").unwrap().status.is_dead());

    let lax = Package::open_with(
        &dest,
        OpenOptions { verify: false, interpret: false, check_derived: false },
    )
    .unwrap();
    // The size still matches, so without hashing there is nothing to see —
    // which is exactly why hashing is the default.
    assert_eq!(lax.node("tex-basecolor").unwrap().status, NodeStatus::Alive);
    assert_eq!(lax.report.count(Code::HashMismatch), 0);
}

#[test]
fn a_package_path_can_never_leave_the_package() {
    let p = Package::open(fixture_dir()).unwrap();
    for evil in ["../HANDOVER.md", "/etc/passwd", "spec/../../HANDOVER.md",
                 "..\\HANDOVER.md"] {
        assert!(p.blob(evil).is_err(), "{evil} must not resolve");
    }
}

#[test]
fn a_floating_file_is_reported() {
    let dest = tmp("floating.werk");
    let z = ZipArchive::parse(std::fs::read(fixture_zip()).unwrap()).unwrap();
    let mut entries: Vec<(String, Vec<u8>)> =
        z.names().into_iter().map(|n| (n.clone(), z.read(&n).unwrap())).collect();
    entries.push(("stowaway.txt".into(), b"nothing declares me\n".to_vec()));
    std::fs::write(&dest, write_zip(&entries)).unwrap();
    let p = Package::open(&dest).unwrap();
    assert_eq!(p.report.count(Code::FloatingFile), 1, "\"nothing floats\" must be checked");
}
