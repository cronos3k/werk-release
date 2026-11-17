#include "werk_sha256.h"

#include <cstdio>
#include <cstring>

namespace werk
{

namespace
{
    // The first 32 bits of the fractional parts of the cube roots of the first
    // 64 primes. MINI-SPECS.md section 11 points out these are derivable
    // rather than data; they are written out here because a table is cheaper
    // to verify by eye than a derivation, and the test vectors prove it either
    // way.
    const uint32_t K[64] = {
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
        0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
        0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
        0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
        0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
        0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
        0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
    };

    inline uint32_t Rotr(uint32_t X, int N) { return (X >> N) | (X << (32 - N)); }
}

void Sha256::Reset()
{
    // The first 32 bits of the fractional parts of the square roots of the
    // first eight primes.
    State[0] = 0x6a09e667; State[1] = 0xbb67ae85;
    State[2] = 0x3c6ef372; State[3] = 0xa54ff53a;
    State[4] = 0x510e527f; State[5] = 0x9b05688c;
    State[6] = 0x1f83d9ab; State[7] = 0x5be0cd19;
    BitLength = 0;
    BufferLength = 0;
}

void Sha256::Transform(const uint8_t Block[64])
{
    uint32_t W[64];
    for (int i = 0; i < 16; ++i)
    {
        // 32-bit words, big-endian.
        W[i] = (uint32_t(Block[i * 4 + 0]) << 24) | (uint32_t(Block[i * 4 + 1]) << 16)
             | (uint32_t(Block[i * 4 + 2]) << 8)  | (uint32_t(Block[i * 4 + 3]));
    }
    for (int i = 16; i < 64; ++i)
    {
        const uint32_t S0 = Rotr(W[i - 15], 7) ^ Rotr(W[i - 15], 18) ^ (W[i - 15] >> 3);
        const uint32_t S1 = Rotr(W[i - 2], 17) ^ Rotr(W[i - 2], 19) ^ (W[i - 2] >> 10);
        W[i] = W[i - 16] + S0 + W[i - 7] + S1;
    }

    uint32_t a = State[0], b = State[1], c = State[2], d = State[3];
    uint32_t e = State[4], f = State[5], g = State[6], h = State[7];

    for (int i = 0; i < 64; ++i)
    {
        const uint32_t S1 = Rotr(e, 6) ^ Rotr(e, 11) ^ Rotr(e, 25);
        const uint32_t Ch = (e & f) ^ ((~e) & g);
        const uint32_t T1 = h + S1 + Ch + K[i] + W[i];
        const uint32_t S0 = Rotr(a, 2) ^ Rotr(a, 13) ^ Rotr(a, 22);
        const uint32_t Maj = (a & b) ^ (a & c) ^ (b & c);
        const uint32_t T2 = S0 + Maj;

        h = g; g = f; f = e; e = d + T1;
        d = c; c = b; b = a; a = T1 + T2;
    }

    State[0] += a; State[1] += b; State[2] += c; State[3] += d;
    State[4] += e; State[5] += f; State[6] += g; State[7] += h;
}

void Sha256::Update(const void* Data, size_t Length)
{
    const uint8_t* P = static_cast<const uint8_t*>(Data);
    BitLength += uint64_t(Length) * 8;

    while (Length > 0)
    {
        const size_t Take = (64 - BufferLength) < Length ? (64 - BufferLength) : Length;
        std::memcpy(Buffer + BufferLength, P, Take);
        BufferLength += Take;
        P += Take;
        Length -= Take;

        if (BufferLength == 64)
        {
            Transform(Buffer);
            BufferLength = 0;
        }
    }
}

void Sha256::Final(uint8_t OutDigest[32])
{
    // 0x80, then zeros, then the 64-bit big-endian bit length. Written into
    // the buffer directly rather than through Update(), because Update()
    // counts what it is given as message data and the padding is not message
    // data -- juggling BitLength around three Update() calls is exactly the
    // kind of cleverness that produces a hash that is wrong only for messages
    // of certain lengths.
    const uint64_t Bits = BitLength;

    Buffer[BufferLength++] = 0x80;
    if (BufferLength > 56)
    {
        std::memset(Buffer + BufferLength, 0, 64 - BufferLength);
        Transform(Buffer);
        BufferLength = 0;
    }
    std::memset(Buffer + BufferLength, 0, 56 - BufferLength);

    for (int i = 0; i < 8; ++i)
    {
        Buffer[56 + i] = uint8_t((Bits >> ((7 - i) * 8)) & 0xFF);
    }
    Transform(Buffer);
    BufferLength = 0;

    for (int i = 0; i < 8; ++i)
    {
        OutDigest[i * 4 + 0] = uint8_t((State[i] >> 24) & 0xFF);
        OutDigest[i * 4 + 1] = uint8_t((State[i] >> 16) & 0xFF);
        OutDigest[i * 4 + 2] = uint8_t((State[i] >> 8) & 0xFF);
        OutDigest[i * 4 + 3] = uint8_t(State[i] & 0xFF);
    }
}

void Sha256::Hash(const void* Data, size_t Length, uint8_t OutDigest[32])
{
    Sha256 H;
    H.Update(Data, Length);
    H.Final(OutDigest);
}

std::string Sha256::HashHex(const void* Data, size_t Length)
{
    uint8_t D[32];
    Hash(Data, Length, D);
    return ToHex(D, 32);
}

std::string Sha256::HashHex(const std::vector<uint8_t>& Data)
{
    return HashHex(Data.empty() ? nullptr : Data.data(), Data.size());
}

std::string ToHex(const uint8_t* Bytes, size_t Length)
{
    static const char* Digits = "0123456789abcdef";
    std::string S;
    S.reserve(Length * 2);
    for (size_t i = 0; i < Length; ++i)
    {
        S.push_back(Digits[(Bytes[i] >> 4) & 0xF]);
        S.push_back(Digits[Bytes[i] & 0xF]);
    }
    return S;
}

bool FromHex64(const std::string& Hex, uint8_t OutBytes[32])
{
    if (Hex.size() != 64)
    {
        return false;
    }
    auto Nib = [](char C, int& Out) -> bool
    {
        if (C >= '0' && C <= '9') { Out = C - '0'; return true; }
        if (C >= 'a' && C <= 'f') { Out = C - 'a' + 10; return true; }
        if (C >= 'A' && C <= 'F') { Out = C - 'A' + 10; return true; }
        return false;
    };
    for (int i = 0; i < 32; ++i)
    {
        int Hi = 0, Lo = 0;
        if (!Nib(Hex[i * 2], Hi) || !Nib(Hex[i * 2 + 1], Lo))
        {
            return false;
        }
        OutBytes[i] = uint8_t((Hi << 4) | Lo);
    }
    return true;
}

std::string InputHashHex(const std::vector<std::string>& InputFileSha256Hex,
                         const std::string& CanonicalParamsJson)
{
    Sha256 H;
    for (const std::string& Hex : InputFileSha256Hex)
    {
        uint8_t Raw[32];
        if (!FromHex64(Hex, Raw))
        {
            return std::string();
        }
        H.Update(Raw, 32); // RAW bytes, not the hex string.
    }
    H.Update(CanonicalParamsJson.data(), CanonicalParamsJson.size());
    uint8_t D[32];
    H.Final(D);
    return ToHex(D, 32);
}

std::vector<std::string> Sha256Selftest(bool bVerbose)
{
    std::vector<std::string> Bad;

    struct Case { const char* In; const char* Want; const char* Name; };
    const Case Cases[] = {
        { "", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
          "sha256(empty)" },
        { "abc", "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
          "sha256(abc)" },
        { "abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq",
          "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1",
          "sha256(56-byte NIST string)" },
    };

    for (const Case& Cs : Cases)
    {
        const std::string Got = Sha256::HashHex(Cs.In, std::strlen(Cs.In));
        if (Got != Cs.Want)
        {
            Bad.push_back(std::string(Cs.Name) + ": got " + Got + " want " + Cs.Want);
        }
        else if (bVerbose)
        {
            std::printf("  OK %s\n", Cs.Name);
        }
    }

    // A multi-block message exercising the buffered Update path: 1000 'a's,
    // which crosses the 64-byte block boundary fifteen times and lands the
    // padding in the awkward place (length % 64 == 40, so the length field
    // fits without an extra block).
    {
        std::string A(1000, 'a');
        Sha256 H;
        for (size_t i = 0; i < A.size(); i += 7) // deliberately ragged chunks
        {
            const size_t N = (i + 7 <= A.size()) ? 7 : (A.size() - i);
            H.Update(A.data() + i, N);
        }
        uint8_t D[32];
        H.Final(D);
        const std::string Chunked = ToHex(D, 32);
        const std::string OneShot = Sha256::HashHex(A.data(), A.size());
        if (Chunked != OneShot)
        {
            Bad.push_back("chunked Update disagrees with one-shot: " + Chunked + " vs " + OneShot);
        }
        else if (bVerbose)
        {
            std::printf("  OK ragged-chunk Update == one-shot (%s)\n", OneShot.c_str());
        }
    }

    // Padding edge cases: exactly 55, 56 and 64 bytes. 56 is the one that
    // forces a second block for the length field and is where a hand-written
    // implementation usually breaks.
    {
        const size_t Lengths[3] = { 55, 56, 64 };
        for (size_t L : Lengths)
        {
            std::string S(L, 'x');
            Sha256 H1;
            H1.Update(S.data(), S.size());
            uint8_t D1[32];
            H1.Final(D1);

            Sha256 H2;
            for (size_t i = 0; i < L; ++i)
            {
                H2.Update(S.data() + i, 1);
            }
            uint8_t D2[32];
            H2.Final(D2);

            if (ToHex(D1, 32) != ToHex(D2, 32))
            {
                Bad.push_back("padding edge case at length " + std::to_string(L));
            }
            else if (bVerbose)
            {
                std::printf("  OK padding edge case length %zu\n", L);
            }
        }
    }

    // Hex round trip.
    {
        uint8_t Raw[32];
        const std::string Hex = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";
        if (!FromHex64(Hex, Raw) || ToHex(Raw, 32) != Hex)
        {
            Bad.push_back("hex round trip");
        }
        if (FromHex64("tooshort", Raw))
        {
            Bad.push_back("FromHex64 accepted a short string");
        }
        if (FromHex64("zzb0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", Raw))
        {
            Bad.push_back("FromHex64 accepted a non-hex character");
        }
    }

    // S-10: an absent input_params IS the empty object. Hashing one input file
    // with no params must equal sha256(raw32 || "{}"), and the default argument
    // must produce exactly that.
    {
        const std::string FileHex = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";
        uint8_t Raw[32];
        FromHex64(FileHex, Raw);
        std::vector<uint8_t> Buf(Raw, Raw + 32);
        Buf.push_back('{');
        Buf.push_back('}');
        const std::string Want = Sha256::HashHex(Buf);
        const std::string Got = InputHashHex({ FileHex });
        if (Got != Want)
        {
            Bad.push_back("input_hash with absent params: got " + Got + " want " + Want);
        }
        else if (bVerbose)
        {
            std::printf("  OK input_hash appends \"{}\" for absent params\n");
        }
        if (InputHashHex({ FileHex }, "{}") != Want)
        {
            Bad.push_back("input_hash: explicit {} disagrees with absent");
        }
    }

    return Bad;
}

} // namespace werk
