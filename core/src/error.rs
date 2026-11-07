//! Errors that stop a package being opened at all.
//!
//! The island rule (manifesto law 3, SPEC.md section 5) says a damaged NODE
//! never fails a load — it is quarantined and reported. So this enum is
//! deliberately short: it only covers the cases where there is no package to
//! speak of, or where a caller asked for something that does not exist.

use std::fmt;

#[derive(Debug)]
pub enum Error {
    /// The path does not exist, or is neither a directory nor a readable file.
    NotFound(String),
    /// An I/O failure while reading the container.
    Io(String),
    /// The container is not a zip and not a directory.
    BadContainer(String),
    /// The container is a zip64 archive. Refused WHOLE and by name
    /// (`zip64-unsupported`, spec/MINI-SPECS.md section 5.5): the offsets a
    /// zip32 reader would follow are sentinels, so nothing is read from it.
    /// Ruled 2026-10: werk does not adopt zip64; a package past the zip32
    /// ceiling is carried in directory form, which is the same format.
    Zip64Unsupported(String),
    /// One zip entry uses a compression method this reader does not implement
    /// (anything but 0 = store and 8 = deflate), or is encrypted. The ENTRY is
    /// unreadable; the container and every other entry are not.
    UnsupportedEntry(String),
    /// One zip entry is damaged at the container level: a deflate stream that
    /// does not decode, a size or CRC-32 that disagrees with the directory.
    BadEntry(String),
    /// MANIFEST.json is not parseable JSON, or is not an object. Everything
    /// else about a manifest — invalid against the schema, unsupported
    /// conventions, dead nodes — is a REPORT, not an error. Report code
    /// `manifest-unparseable` (SPEC.md section 12.1).
    BadManifest(String),
    /// MANIFEST.json is not in the container at all. Report code
    /// `manifest-absent`. Same numeric code as `BadManifest` on the C ABI,
    /// whose header has always said "absent or not JSON" for it.
    ManifestAbsent(String),
    /// A caller asked for a node/version/file that is not in the manifest.
    NoSuchItem(String),
    /// A signing or verification input was malformed (bad hex, wrong length).
    BadKey(String),
    /// A write target could not be produced.
    Write(String),
    /// A mutation was rejected because it would violate a law (e.g. an empty
    /// work note, which law 6 forbids).
    Rejected(String),
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let msg = match self {
            Error::NotFound(m)
            | Error::Io(m)
            | Error::BadContainer(m)
            | Error::Zip64Unsupported(m)
            | Error::UnsupportedEntry(m)
            | Error::BadEntry(m)
            | Error::BadManifest(m)
            | Error::ManifestAbsent(m)
            | Error::NoSuchItem(m)
            | Error::BadKey(m)
            | Error::Write(m)
            | Error::Rejected(m) => m,
        };
        write!(f, "{}: {msg}", self.tag())
    }
}

impl std::error::Error for Error {}

impl From<std::io::Error> for Error {
    fn from(e: std::io::Error) -> Self {
        Error::Io(e.to_string())
    }
}

/// Stable numeric codes for the C ABI. 0 is success.
impl Error {
    pub fn code(&self) -> i32 {
        match self {
            Error::NotFound(_) => -1,
            Error::Io(_) => -2,
            Error::BadContainer(_) => -3,
            Error::BadManifest(_) | Error::ManifestAbsent(_) => -4,
            Error::NoSuchItem(_) => -5,
            Error::BadKey(_) => -6,
            Error::Write(_) => -7,
            Error::Rejected(_) => -8,
            // -9 is WERK_ERR_ARGUMENT in werk.h, raised by the FFI layer itself.
            Error::Zip64Unsupported(_) => -10,
            Error::UnsupportedEntry(_) => -11,
            Error::BadEntry(_) => -12,
        }
    }
}

impl Error {
    /// The stable report code of this refusal — the same spelling
    /// spec/SPEC.md section 10.1 uses, so a tool comparing strings sees one
    /// vocabulary whether the refusal was a report entry or a failed open.
    pub fn tag(&self) -> &'static str {
        match self {
            Error::NotFound(_) => "not-found",
            Error::Io(_) => "io",
            Error::BadContainer(_) => "bad-container",
            Error::BadManifest(_) => "manifest-unparseable",
            Error::ManifestAbsent(_) => "manifest-absent",
            Error::NoSuchItem(_) => "no-such-item",
            Error::BadKey(_) => "bad-key",
            Error::Write(_) => "write",
            Error::Rejected(_) => "rejected",
            Error::Zip64Unsupported(_) => "zip64-unsupported",
            Error::UnsupportedEntry(_) => "zip-entry-unsupported",
            Error::BadEntry(_) => "zip-entry-invalid",
        }
    }

    /// SPEC.md section 10.1: is this a CONTAINER-scoped refusal — the one
    /// scope that may come back empty-handed, exit status 2?
    pub fn is_container_refusal(&self) -> bool {
        matches!(
            self,
            Error::NotFound(_)
                | Error::Io(_)
                | Error::BadContainer(_)
                | Error::BadManifest(_)
                | Error::ManifestAbsent(_)
                | Error::Zip64Unsupported(_)
        )
    }
}

pub type Result<T> = std::result::Result<T, Error>;
