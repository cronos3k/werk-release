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
