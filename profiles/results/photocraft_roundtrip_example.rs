//! W19 round trip (werk release, profiles/raster-layers): written in a MIRROR of the photocraft
//! werk-native tree whose werk-core is the release core; not part of the ArtCraft sources.
//!
//!   w19_roundtrip <release fixture raster-layers-v1.werk> <out dir>
//!
//! A: release fixture -> photocraft_werk::open -> Document -> save (raster-layers/1, new file)
//!    -> open -> Document: the two Documents must be equal (PartialEq).
//! B: photocraft testgen documents (simple 3-layer, and the every-field `maximal`) -> save ->
//!    open -> equal (the app's own round trip on the release core); the files are left in
//!    <out dir> for the release reference reader to read.
use std::path::Path;

use photocraft_doc::Document;
use photocraft_raster::Rgba8Image;
use photocraft_werk::{Form, SaveOptions, testgen};

fn picture(doc: &Document, side: u32) -> Rgba8Image {
    let (w, h) = (side.min(doc.size.width.max(1)), side.min(doc.size.height.max(1)));
    let mut img = Rgba8Image::new(w, h);
    for (i, px) in img.pixels.chunks_exact_mut(4).enumerate() {
        px.copy_from_slice(&[(i % 251) as u8, 17, (i / 7 % 256) as u8, 255]);
    }
    img
}

fn opts(doc: &Document) -> SaveOptions<'static> {
    SaveOptions {
        form: Form::Zip,
        thumbnail: Some(picture(doc, 64)),
        composite: Some(picture(doc, 256)),
        thumbnail_max_side: 64,
        composite_max_side: 256,
        created: Some("2026-11-20T00:00:00Z".into()),
        uuid: Some("5d6f0c1e-7a2b-4c3d-8e9f-0a1b2c3d4e5f".into()),
        ..Default::default()
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = std::env::args().collect();
    let fixture = Path::new(&args[1]);
    let out = Path::new(&args[2]);
    std::fs::create_dir_all(out)?;
    let mut failures = 0;

    // A
    let a = photocraft_werk::open(fixture)?;
    println!("A open fixture: exit_status {} lost {} skipped {:?} signature {}", a.exit_status, a.lost.len(), a.skipped, a.signature);
    for l in &a.lost {
        println!("A   lost: {l:?}");
    }
    for r in &a.report {
        println!("A   report: {r}");
    }
    println!("A   document: {} x {}, {} top-level layers", a.document.size.width, a.document.size.height, a.document.layers.len());
    let p1 = out.join("A-fixture-resaved-by-photocraft.werk");
    let _ = std::fs::remove_file(&p1);
    let rep = photocraft_werk::save(&a.document, &p1, opts(&a.document))?;
    println!("A save: revision {}", rep.revision);
    let b = photocraft_werk::open(&p1)?;
    println!("A reopen: exit_status {} lost {}", b.exit_status, b.lost.len());
    let eq = b.document == a.document;
    println!("A Document(open(fixture)) == Document(open(save(open(fixture)))): {eq}");
    if !eq || !b.lost.is_empty() {
        failures += 1;
    }

    // B
    for (name, doc) in [("simple", testgen::simple(20_000, 600, 400)), ("maximal", testgen::maximal(1_000_000))] {
        let p = out.join(format!("B-photocraft-{name}.werk"));
        let _ = std::fs::remove_file(&p);
        photocraft_werk::save(&doc, &p, opts(&doc))?;
        let back = photocraft_werk::open(&p)?;
        let eq = back.document == doc;
        println!("B {name}: exit_status {} lost {} equal {eq}", back.exit_status, back.lost.len());
        if !eq || !back.lost.is_empty() {
            failures += 1;
        }
    }
    println!("failures: {failures}");
    std::process::exit(if failures == 0 { 0 } else { 1 });
}
