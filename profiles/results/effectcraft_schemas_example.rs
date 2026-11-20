//! W19 (werk release, mirror only): write every motion-comp/1 JSON schema the application
//! generates, `spec/schemas/<type>.schema.json`, into <out dir>.
fn main() {
    let out = std::path::PathBuf::from(std::env::args().nth(1).expect("usage: w19_schemas <out dir>"));
    std::fs::create_dir_all(&out).unwrap();
    for t in effectcraft_werk::schema::JSON_TYPES {
        let b = effectcraft_werk::schema::of(t).expect("schema");
        std::fs::write(out.join(format!("{t}.schema.json")), b).unwrap();
        println!("{t} {}", b.len());
    }
}
