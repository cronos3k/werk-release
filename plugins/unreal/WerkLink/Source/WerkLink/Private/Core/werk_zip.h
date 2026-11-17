// Store-mode zip, reader and writer, per MINI-SPECS.md section 5.
//
// Unreal ships no zip library, and SPEC.md section 1 blesses store-only
// conformance explicitly: "a reader that supports only store mode is
// conformant against the fixtures and must say so rather than return wrong
// bytes". So this is the whole dependency story for the container -- about a
// hundred lines of reader, a hundred of writer, and CRC-32.
//
// What is implemented, stated plainly so the README can copy it:
//   * method 0 (store), read and write
//   * the central directory as the authority on names, sizes and offsets
//   * local header re-read for the data offset, because MINI-SPECS 5.3 warns
//     that the local n and m can differ from the central directory's
//   * general purpose flag bit 11 (UTF-8 names) set on write
//   * flag bit 3 (trailing data descriptor) refused on read and never set on
//     write, per MINI-SPECS 5.4 -- it makes a ranged preview read impossible
//   * zip64 DETECTION and refusal, container-scoped, per MINI-SPECS 5.5
//   * CRC-32 verified on every entry read
//   * method 8 (deflate) READ (werk release, W5c: SPEC 1 ruling 9); a stream
//     that does not decode to the directory's size is `zip-entry-invalid`,
//     any other method or an encrypted entry `zip-entry-unsupported`, both
//     entry-scoped. Never written: the writer is store-only.
//
// What is not:
//   * zip64 reading. Reported as `zip64-unsupported`, container-scoped, and
//     nothing is read from the container -- MINI-SPECS 5.5 requires exactly
//     this and forbids falling back to the 32-bit fields.

#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include "werk_report.h"

namespace werk
{

uint32_t Crc32(const void* Data, size_t Length, uint32_t Seed = 0);

// MINI-SPECS 5.4 rule 3: UTF-8, every invalid sequence replaced by U+FFFD.
std::string Utf8Lossy(const uint8_t* P, size_t N);

struct ZipEntry
{
    std::string name;
    uint32_t    crc32 = 0;
    uint64_t    compressedSize = 0;
    uint64_t    uncompressedSize = 0;
    uint64_t    localHeaderOffset = 0;
    uint16_t    method = 0;
    uint16_t    flags = 0;
};

class ZipReader
{
public:
    // Reads the whole container into memory. A werk package is a handful of
    // megabytes and every consumer here needs random access; streaming would
    // buy nothing and cost the ranged-read simplicity.
    bool OpenFile(const std::string& Path, Report& Rep);
    bool OpenMemory(std::vector<uint8_t> Bytes, Report& Rep);

    const std::vector<ZipEntry>& Entries() const { return EntryList; }
    bool Has(const std::string& Name) const;
    // Returns false and reports on: missing name, unsupported method, CRC
    // mismatch, or a truncated local header.
    bool Read(const std::string& Name, std::vector<uint8_t>& Out, Report& Rep) const;

    uint64_t ContainerSize() const { return Raw.size(); }
    const std::vector<uint8_t>& RawBytes() const { return Raw; }

private:
    bool Parse(Report& Rep);

    std::vector<uint8_t> Raw;
    std::vector<ZipEntry> EntryList;
};

class ZipWriter
{
public:
    // Entries are written in the order added. SPEC.md section 1 makes that
    // order load-bearing (preview-first, law 9), so this class deliberately
    // does not sort, dedupe or reorder anything.
    void Add(const std::string& Name, std::vector<uint8_t> Bytes);
    bool Has(const std::string& Name) const;
    size_t Count() const { return Items.size(); }

    // Serialises into memory. Returns the bytes; the offset of the end of the
    // last entry named in PrefixThrough is written to OutPrefixBytes so a
    // caller can fill container.preview_prefix_bytes with a measured number
    // rather than an estimate. Pass an empty string for no prefix measurement.
    std::vector<uint8_t> Build(const std::string& PrefixThroughName,
                               uint64_t& OutPrefixBytes) const;

    bool WriteFile(const std::string& Path, const std::string& PrefixThroughName,
                   uint64_t& OutPrefixBytes, Report& Rep) const;

    const std::vector<std::pair<std::string, std::vector<uint8_t>>>& All() const { return Items; }

private:
    std::vector<std::pair<std::string, std::vector<uint8_t>>> Items;
};

// MINI-SPECS 5.4 name rules: forward slashes, relative, no "..", no drive
// letter, no leading slash. A writer must not emit a name that fails this and
// a reader must not follow one.
bool IsSafeZipName(const std::string& Name);

// CRC-32 test vector from MINI-SPECS section 6, plus a store round trip.
std::vector<std::string> ZipSelftest(bool bVerbose = false);

} // namespace werk
