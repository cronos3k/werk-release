// SHA-256, FIPS 180-4, per MINI-SPECS.md section 11.
//
// Written here rather than taken from the engine because Unreal Core ships
// SHA-1 (FSHAHash), Blake3, CityHash, BuzHash, FNV and xxhash -- and no
// SHA-256. Checked, not assumed: there is no Sha256 header in
// Engine/Source/Runtime/Core/Public/Hash/ or in Misc/SecureHash.h on UE 5.7.
//
// conventions.hash_algorithm is "sha256" and every content hash in werk is the
// lowercase hex of a SHA-256 digest, 64 characters. Getting this wrong means
// every file in an exported package carries a wrong hash, which no later stage
// can detect for us -- so the three MINI-SPECS test vectors are asserted by
// Selftest() and the gate runs it.

#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace werk
{

class Sha256
{
public:
    Sha256() { Reset(); }

    void Reset();
    void Update(const void* Data, size_t Length);
    // Writes 32 raw bytes. The object must not be reused afterwards.
    void Final(uint8_t OutDigest[32]);

    static void Hash(const void* Data, size_t Length, uint8_t OutDigest[32]);
    static std::string HashHex(const void* Data, size_t Length);
    static std::string HashHex(const std::vector<uint8_t>& Data);

private:
    void Transform(const uint8_t Block[64]);

    uint32_t State[8];
    uint64_t BitLength;
    uint8_t  Buffer[64];
    size_t   BufferLength;
};

// Lowercase hex, 64 characters, as conventions.hash_algorithm requires.
std::string ToHex(const uint8_t* Bytes, size_t Length);
// Returns false if the string is not exactly 64 lowercase-or-uppercase hex
// characters. Case is accepted on the way in and normalised on the way out,
// because a reader that rejects a valid file over letter case is a bad reader;
// a WRITER must always emit lowercase.
bool FromHex64(const std::string& Hex, uint8_t OutBytes[32]);

// MINI-SPECS.md section 11 "What gets hashed": input_hash is the concatenation,
// in input_files order, of each input's 32 RAW digest bytes, followed by the
// UTF-8 bytes of the canonical JSON of input_params. An absent input_params is
// the empty object and its canonical JSON is the two bytes "{}" -- S-10, the
// single longest detour in the agent gauntlet, for three readers in three
// languages. Passing CanonicalParamsJson = "{}" is therefore correct and is
// the default rather than a special case.
std::string InputHashHex(const std::vector<std::string>& InputFileSha256Hex,
                         const std::string& CanonicalParamsJson = "{}");

// Every vector in MINI-SPECS.md section 11, plus the S-10 worked example shape.
// Empty result means all held.
std::vector<std::string> Sha256Selftest(bool bVerbose = false);

} // namespace werk
