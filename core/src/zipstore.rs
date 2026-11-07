//! Zip, read (store and deflate) and write (store only), implemented natively.
//!
//! Normative source: spec/MINI-SPECS.md section 5 (EOCD, central directory,
//! local file header — the byte tables) and section 5.4 (the rules werk
//! imposes). SPEC.md section 1 explains why store (method 0) is the default:
//! a zero-dependency reader is about a hundred lines WITHOUT an inflate
//! implementation, and PNG/WAV/GLB are already compressed.
//!
//! READING method 8 (deflate) is implemented since ruling 9 of 2026-10-13
//! (`inflate.rs`, from MINI-SPECS section 7.1); the inflated bytes are checked
//! against the directory's size and CRC-32 before they are returned. Any other
//! method, and an encrypted entry, is refused BY NAME for that entry only
//! (`zip-entry-unsupported`) and its bytes are never returned — MINI-SPECS
//! section 5.3. WRITING is store mode only, always.
//!
//! Zip64 is detected and refused whole, by name (`zip64-unsupported`); it is
//! not implemented and by ruling will not be (directory form instead).

use crate::error::{Error, Result};

const SIG_LOCAL: u32 = 0x0403_4b50;
const SIG_CENTRAL: u32 = 0x0201_4b50;
const SIG_EOCD: u32 = 0x0605_4b50;
const SIG_EOCD64: u32 = 0x0606_4b50;
const SIG_EOCD64_LOC: u32 = 0x0706_4b50;

/// Flag bit 11: the file name is UTF-8. werk always sets it (MINI-SPECS 5.2).
const FLAG_UTF8: u16 = 0x0800;
/// Flag bit 0: the entry is encrypted. werk has no encryption.
const FLAG_ENCRYPTED: u16 = 0x0001;
/// Flag bit 3: sizes live in a trailing data descriptor. werk writers MUST NOT
/// set it, because it makes a ranged read of the preview prefix impossible.
const FLAG_DATA_DESCRIPTOR: u16 = 0x0008;

/// A fixed timestamp, so that writing the same content twice produces the same
/// bytes. Byte-identity is a gate (ROADMAP Stage 2); a wall clock in the
/// header would destroy it for no benefit. 2026-08-08 09:00:00, MS-DOS format.
pub const DOS_TIME: u16 = (9 << 11) | (0 << 5); // 09:00:00
pub const DOS_DATE: u16 = ((2026 - 1980) << 9) | (8 << 5) | 8; // 2026-08-08

#[derive(Debug, Clone)]
pub struct ZipEntry {
    pub name: String,
    pub flags: u16,
    pub method: u16,
    pub crc32: u32,
    pub comp_size: u64,
    pub uncomp_size: u64,
    pub local_header_offset: u64,
}

pub struct ZipArchive {
    bytes: Vec<u8>,
    pub entries: Vec<ZipEntry>,
}

fn u16le(b: &[u8], o: usize) -> Option<u16> {
    Some(u16::from_le_bytes(b.get(o..o + 2)?.try_into().ok()?))
}
fn u32le(b: &[u8], o: usize) -> Option<u32> {
    Some(u32::from_le_bytes(b.get(o..o + 4)?.try_into().ok()?))
}

/// The one message every whole-container zip64 refusal in this crate prints.
/// Kept in one place because "refused by name" is only true if the name and
/// the remedy are the same sentence wherever the refusal happens.
fn zip64_message(sentinel: bool, locator: bool, record: bool) -> String {
    format!(
        "zip64 container (EOCD sentinel: {sentinel}; zip64 locator before the EOCD: \
         {locator}; zip64 EOCD record where the locator points: {record}). This reader \
         implements 32-bit zip only and reads nothing from a zip64 container, because \
         the offsets it would follow are sentinels. werk does not use zip64: a package \
         past the zip32 ceiling (4 GiB, 65534 entries) is carried in DIRECTORY form, \
         which is the same format and has no ceiling."
    )
}

/// Refuse a zip64 container from its TAIL, before anything else is read.
///
/// A zip64 container is by definition the kind that may not fit in memory —
/// its whole reason to exist is to pass 4 GiB — so a reader that slurps the
/// file and then refuses it has already paid, in RAM, for the thing it is
/// refusing. The end-of-central-directory record and the zip64 locator are in
/// the last 65 577 bytes (22 + 65 535 of comment + 20 of locator); that is all
/// this reads. `Ok(())` means "not recognisably zip64 from the tail": the
/// caller then reads the file and `parse` makes every other check.
pub fn refuse_zip64_from_tail(path: &std::path::Path) -> Result<()> {
    use std::io::{Read, Seek, SeekFrom};
    let mut f = std::fs::File::open(path)?;
    let len = f.metadata()?.len();
    let want = (22 + 65_535 + 20).min(len);
    f.seek(SeekFrom::Start(len - want))?;
    let mut tail = vec![0u8; want as usize];
    f.read_exact(&mut tail)?;
    if tail.len() < 22 {
        return Ok(());
    }
    let mut i = tail.len() - 22;
    loop {
        if u32le(&tail, i) == Some(SIG_EOCD) {
            let disk_count = u16le(&tail, i + 8).unwrap_or(0);
            let count = u16le(&tail, i + 10).unwrap_or(0);
            let cd_size = u32le(&tail, i + 12).unwrap_or(0);
            let cd_off = u32le(&tail, i + 16).unwrap_or(0);
            let sentinel = cd_off == 0xFFFF_FFFF
                || cd_size == 0xFFFF_FFFF
                || count == 0xFFFF
                || disk_count == 0xFFFF;
            let locator = i >= 20 && u32le(&tail, i - 20) == Some(SIG_EOCD64_LOC);
            if sentinel || locator {
                // Whether the zip64 record is where the locator says is not
                // checked here: it may be 4 GiB away, and the refusal does
                // not depend on it.
                return Err(Error::Zip64Unsupported(zip64_message(sentinel, locator, locator)));
            }
            return Ok(());
        }
        if i == 0 {
            return Ok(());
        }
        i -= 1;
    }
}

impl ZipArchive {
    pub fn parse(bytes: Vec<u8>) -> Result<ZipArchive> {
        let n = bytes.len();
        if n < 22 {
            return Err(Error::BadContainer("file is too short to be a zip".into()));
        }
        // Scan backwards for the EOCD signature. The comment is the only thing
        // that may follow it, and it is at most 65535 bytes.
        let start = n.saturating_sub(22 + 65535);
        let mut eocd = None;
        let mut i = n - 22;
        loop {
            if u32le(&bytes, i) == Some(SIG_EOCD) {
                eocd = Some(i);
                break;
            }
            if i == start {
                break;
            }
            i -= 1;
        }
        let eocd = eocd.ok_or_else(|| {
            Error::BadContainer("no end-of-central-directory record: not a zip".into())
        })?;

        let count = u16le(&bytes, eocd + 10).unwrap_or(0) as usize;
        let cd_size = u32le(&bytes, eocd + 12).unwrap_or(0) as u64;
        let cd_off = u32le(&bytes, eocd + 16).unwrap_or(0) as u64;

        // spec/MINI-SPECS.md section 5.5, both signals. Either one is enough:
        // a sentinel in the EOCD, or the zip64 locator sitting immediately
        // before it. The refusal is whole-container and named, because the
        // offsets a zip32 reader would otherwise follow are sentinels.
        let disk_count = u16le(&bytes, eocd + 8).unwrap_or(0);
        let sentinel = cd_off == 0xFFFF_FFFF
            || cd_size == 0xFFFF_FFFF
            || count == 0xFFFF
            || disk_count == 0xFFFF;
        let locator = eocd >= 20 && u32le(&bytes, eocd - 20) == Some(SIG_EOCD64_LOC);
        if sentinel || locator {
            let record = locator
                && bytes
                    .get(eocd - 12..eocd - 4)
                    .and_then(|b| <[u8; 8]>::try_from(b).ok())
                    .map(u64::from_le_bytes)
                    .and_then(|off| usize::try_from(off).ok())
                    .map_or(false, |off| u32le(&bytes, off) == Some(SIG_EOCD64));
            return Err(Error::Zip64Unsupported(zip64_message(sentinel, locator, record)));
        }

        let mut entries = Vec::with_capacity(count);
        let mut p = cd_off as usize;
        for _ in 0..count {
            if u32le(&bytes, p) != Some(SIG_CENTRAL) {
                return Err(Error::BadContainer(format!(
                    "central directory record at {p} has a bad signature"
                )));
            }
            let flags = u16le(&bytes, p + 8).unwrap_or(0);
            let method = u16le(&bytes, p + 10).unwrap_or(0);
            let crc32 = u32le(&bytes, p + 16).unwrap_or(0);
            let comp = u32le(&bytes, p + 20).unwrap_or(0) as u64;
            let uncomp = u32le(&bytes, p + 24).unwrap_or(0) as u64;
            let nlen = u16le(&bytes, p + 28).unwrap_or(0) as usize;
            let mlen = u16le(&bytes, p + 30).unwrap_or(0) as usize;
            let klen = u16le(&bytes, p + 32).unwrap_or(0) as usize;
            let lho = u32le(&bytes, p + 42).unwrap_or(0) as u64;
            let name = String::from_utf8_lossy(
                bytes.get(p + 46..p + 46 + nlen).ok_or_else(|| {
                    Error::BadContainer("central directory name runs past end of file".into())
                })?,
            )
            .into_owned();
            if comp == 0xFFFF_FFFF || uncomp == 0xFFFF_FFFF || lho == 0xFFFF_FFFF {
                // MINI-SPECS 5.5 step 5: the per-entry sentinel. The true
                // value is in a zip64 extra field this reader does not read.
                return Err(Error::Zip64Unsupported(format!(
                    "entry `{name}` carries a 0xFFFFFFFF size or offset sentinel (a zip64 \
                     entry). This reader implements 32-bit zip only and reads nothing from \
                     a zip64 container. werk does not use zip64: a package past the zip32 \
                     ceiling is carried in DIRECTORY form, which is the same format."
                )));
            }
            if flags & FLAG_DATA_DESCRIPTOR != 0 {
                return Err(Error::BadContainer(format!(
                    "entry `{name}` sets general-purpose flag bit 3 (data descriptor), \
                     which a werk writer MUST NOT set"
                )));
            }
            entries.push(ZipEntry {
                name,
                flags,
                method,
                crc32,
                comp_size: comp,
                uncomp_size: uncomp,
                local_header_offset: lho,
            });
            p += 46 + nlen + mlen + klen;
        }
        Ok(ZipArchive { bytes, entries })
    }

    pub fn total_bytes(&self) -> usize {
        self.bytes.len()
    }

    pub fn names(&self) -> Vec<String> {
        self.entries.iter().map(|e| e.name.clone()).collect()
    }

    pub fn find(&self, name: &str) -> Option<&ZipEntry> {
        self.entries.iter().find(|e| e.name == name)
    }

    /// Byte offset of an entry's DATA, resolved through the LOCAL header —
    /// never the central directory's name/extra lengths, which are allowed to
    /// differ (MINI-SPECS 5.3).
    pub fn data_offset(&self, e: &ZipEntry) -> Result<usize> {
        let lho = e.local_header_offset as usize;
        if u32le(&self.bytes, lho) != Some(SIG_LOCAL) {
            return Err(Error::BadContainer(format!(
                "local header for `{}` at {lho} has a bad signature",
                e.name
            )));
        }
        let nlen = u16le(&self.bytes, lho + 26).unwrap_or(0) as usize;
        let mlen = u16le(&self.bytes, lho + 28).unwrap_or(0) as usize;
        Ok(lho + 30 + nlen + mlen)
    }

    pub fn read(&self, name: &str) -> Result<Vec<u8>> {
        let e = self
            .find(name)
            .ok_or_else(|| Error::NoSuchItem(format!("no zip entry `{name}`")))?;
        if e.flags & FLAG_ENCRYPTED != 0 {
            return Err(Error::UnsupportedEntry(format!(
                "entry `{name}` is encrypted; werk has no encryption and this reader \
                 returns no bytes for it"
            )));
        }
        if e.method != 0 && e.method != 8 {
            return Err(Error::UnsupportedEntry(format!(
                "entry `{name}` uses compression method {}; this reader implements 0 \
                 (store) and 8 (deflate) and refuses to return wrong bytes",
                e.method
            )));
        }
        let off = self
            .data_offset(e)
            .map_err(|err| Error::BadEntry(format!("entry `{name}`: {err}")))?;
        let end = off + e.comp_size as usize;
        let data = self
            .bytes
            .get(off..end)
            .ok_or_else(|| Error::BadEntry(format!("entry `{name}` runs past end of file")))?;
        if e.method == 0 {
            return Ok(data.to_vec());
        }
        // Method 8. The directory's uncompressed size is the output limit —
        // a deflate stream is the one place a small file can ask for a large
        // allocation — and the size and CRC-32 are checked before a byte is
        // handed over, so a stream that decodes to the wrong thing is damage
        // to this entry and never a silently wrong payload.
        let out = crate::inflate::inflate(data, e.uncomp_size as usize).map_err(|m| {
            Error::BadEntry(format!("entry `{name}`: deflate stream does not decode: {m}"))
        })?;
        if out.len() as u64 != e.uncomp_size {
            return Err(Error::BadEntry(format!(
                "entry `{name}` inflates to {} bytes but the directory declares {}",
                out.len(),
                e.uncomp_size
            )));
        }
        let crc = crc32(&out);
        if crc != e.crc32 {
            return Err(Error::BadEntry(format!(
                "entry `{name}` inflates to bytes whose CRC-32 is {crc:08x}; the directory \
                 declares {:08x}",
                e.crc32
            )));
        }
        Ok(out)
    }

    /// Names of the entries stored with method 8, so a caller can say that it
    /// inflated something rather than leave it implicit.
    pub fn deflated_names(&self) -> Vec<String> {
        self.entries.iter().filter(|e| e.method == 8).map(|e| e.name.clone()).collect()
    }
}

// ---------------------------------------------------------------------------
// Writer
// ---------------------------------------------------------------------------

/// Writes a store-mode zip. The entry ORDER given is the physical order
/// written, which is the whole point: law 9's preview-first layout means the
/// first N bytes of the file are a browsable record.
pub fn write_zip(entries: &[(String, Vec<u8>)]) -> Vec<u8> {
    let mut out: Vec<u8> = Vec::new();
    let mut central: Vec<u8> = Vec::new();
    let mut count: u16 = 0;

    for (name, data) in entries {
        let lho = out.len() as u32;
        let crc = crc32(data);
        let nb = name.as_bytes();

        out.extend_from_slice(&SIG_LOCAL.to_le_bytes());
        out.extend_from_slice(&20u16.to_le_bytes()); // version needed: 2.0
        out.extend_from_slice(&FLAG_UTF8.to_le_bytes());
        out.extend_from_slice(&0u16.to_le_bytes()); // method 0 = store
        out.extend_from_slice(&DOS_TIME.to_le_bytes());
        out.extend_from_slice(&DOS_DATE.to_le_bytes());
        out.extend_from_slice(&crc.to_le_bytes());
        out.extend_from_slice(&(data.len() as u32).to_le_bytes());
        out.extend_from_slice(&(data.len() as u32).to_le_bytes());
        out.extend_from_slice(&(nb.len() as u16).to_le_bytes());
        out.extend_from_slice(&0u16.to_le_bytes()); // no extra field
        out.extend_from_slice(nb);
        out.extend_from_slice(data);

        central.extend_from_slice(&SIG_CENTRAL.to_le_bytes());
        central.extend_from_slice(&20u16.to_le_bytes()); // version made by
        central.extend_from_slice(&20u16.to_le_bytes()); // version needed
        central.extend_from_slice(&FLAG_UTF8.to_le_bytes());
        central.extend_from_slice(&0u16.to_le_bytes());
        central.extend_from_slice(&DOS_TIME.to_le_bytes());
        central.extend_from_slice(&DOS_DATE.to_le_bytes());
        central.extend_from_slice(&crc.to_le_bytes());
        central.extend_from_slice(&(data.len() as u32).to_le_bytes());
        central.extend_from_slice(&(data.len() as u32).to_le_bytes());
        central.extend_from_slice(&(nb.len() as u16).to_le_bytes());
        central.extend_from_slice(&0u16.to_le_bytes()); // extra
        central.extend_from_slice(&0u16.to_le_bytes()); // comment
        central.extend_from_slice(&0u16.to_le_bytes()); // disk number
        central.extend_from_slice(&0u16.to_le_bytes()); // internal attrs
        central.extend_from_slice(&0u32.to_le_bytes()); // external attrs
        central.extend_from_slice(&lho.to_le_bytes());
        central.extend_from_slice(nb);

        count += 1;
    }

    let cd_off = out.len() as u32;
    let cd_size = central.len() as u32;
    out.extend_from_slice(&central);
    out.extend_from_slice(&SIG_EOCD.to_le_bytes());
    out.extend_from_slice(&0u16.to_le_bytes()); // this disk
    out.extend_from_slice(&0u16.to_le_bytes()); // disk with central dir
    out.extend_from_slice(&count.to_le_bytes());
    out.extend_from_slice(&count.to_le_bytes());
    out.extend_from_slice(&cd_size.to_le_bytes());
    out.extend_from_slice(&cd_off.to_le_bytes());
    out.extend_from_slice(&0u16.to_le_bytes()); // no comment
    out
}

/// CRC-32, IEEE 802.3 polynomial 0xEDB88320 reflected — spec/MINI-SPECS.md
/// section 6. Implemented here so the writer needs nothing outside std.
pub fn crc32(data: &[u8]) -> u32 {
    let mut crc = 0xFFFF_FFFFu32;
    for &b in data {
        let mut c = (crc ^ b as u32) & 0xFF;
        for _ in 0..8 {
            c = if c & 1 != 0 { (c >> 1) ^ 0xEDB8_8320 } else { c >> 1 };
        }
        crc = (crc >> 8) ^ c;
    }
    !crc
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn crc32_known_vector() {
        // The canonical check value: CRC-32 of "123456789" is 0xCBF43926.
        assert_eq!(crc32(b"123456789"), 0xCBF4_3926);
        assert_eq!(crc32(b""), 0);
    }

    #[test]
    fn round_trip_and_determinism() {
        let entries = vec![
            ("MANIFEST.json".to_string(), b"{\"a\":1}".to_vec()),
            ("spec/SPEC.md".to_string(), b"# spec\n".to_vec()),
            ("empty.bin".to_string(), Vec::new()),
        ];
        let a = write_zip(&entries);
        let b = write_zip(&entries);
        assert_eq!(a, b, "the writer must be deterministic");

        let z = ZipArchive::parse(a).unwrap();
        assert_eq!(z.names(), vec!["MANIFEST.json", "spec/SPEC.md", "empty.bin"]);
        assert_eq!(z.read("spec/SPEC.md").unwrap(), b"# spec\n");
        assert_eq!(z.read("empty.bin").unwrap(), Vec::<u8>::new());
        assert!(z.read("nope").is_err());
    }
}
