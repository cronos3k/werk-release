//! werk-core — the reference implementation of the werk artifact container
//! format, profile `3d-entity/1`.
//!
//! Built as one `cdylib` (`werk.dll` / `libwerk.so` / `libwerk.dylib`) behind
//! the C ABI in `include/werk.h`, plus an `rlib` for Rust callers. C++ consumes
//! the header and the shared library; Python binds the SAME shared library
//! through `ctypes` with no pip dependencies. One implementation, three faces.
//!
//! The spec travels with the format: everything this crate does is written down
//! in `spec/`, and the JSON Schemas are `include_str!`-ed straight out of
//! `spec/schemas/` so the code cannot drift from the document.
//!
//! Entry point: [`Package::open`].

pub mod envelope;
pub mod error;
pub mod ffi;
pub mod formats;
pub mod geom;
pub mod hashing;
pub mod inflate;
pub mod manifest;
pub mod msgpack;
pub mod package;
pub mod regexlite;
pub mod report;
pub mod schema;
pub mod signature;
pub mod zipstore;

pub use error::{Error, Result};
pub use manifest::{Manifest, NodeView, VersionView};
pub use package::{
    ManifestValidation, NewFile, NewNode, NewVersion, NodeStatus, OpenOptions, Package,
};
pub use report::{Code, LoadReport, ReportEntry, Severity};
pub use signature::SignatureState;

/// Version of this implementation, not of the format. The format version a
/// package declares is `MANIFEST.json` → `werk: {major, minor}`.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// The profile this build implements.
pub const PROFILE: &str = "3d-entity/1";
