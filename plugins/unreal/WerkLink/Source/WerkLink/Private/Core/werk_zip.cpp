#include "werk_zip.h"

#include <cstdio>
#include <cstring>

namespace werk
{

namespace
{
    uint16_t Rd16(const uint8_t* P) { return uint16_t(P[0]) | (uint16_t(P[1]) << 8); }
    uint32_t Rd32(const uint8_t* P)
    {
        return uint32_t(P[0]) | (uint32_t(P[1]) << 8) | (uint32_t(P[2]) << 16) | (uint32_t(P[3]) << 24);
    }

    void Wr16(std::vector<uint8_t>& V, uint16_t X)
    {
        V.push_back(uint8_t(X & 0xFF));
        V.push_back(uint8_t((X >> 8) & 0xFF));
    }
    void Wr32(std::vector<uint8_t>& V, uint32_t X)
    {
        V.push_back(uint8_t(X & 0xFF));
        V.push_back(uint8_t((X >> 8) & 0xFF));
        V.push_back(uint8_t((X >> 16) & 0xFF));
        V.push_back(uint8_t((X >> 24) & 0xFF));
    }

    constexpr uint32_t kSigEocd    = 0x06054b50;
    constexpr uint32_t kSigCentral = 0x02014b50;
    constexpr uint32_t kSigLocal   = 0x04034b50;
    constexpr uint32_t kSigZip64Locator = 0x07064b50;
}

uint32_t Crc32(const void* Data, size_t Length, uint32_t Seed)
{
    // Reflected IEEE 802.3, polynomial 0xEDB88320, init 0xFFFFFFFF, final xor
    // 0xFFFFFFFF -- MINI-SPECS section 6. The table is built once on first use
    // rather than written out, because the polynomial is the specification and
    // 256 constants are not.
    static uint32_t Table[256];
    static bool bBuilt = false;
    if (!bBuilt)
    {
        for (uint32_t i = 0; i < 256; ++i)
        {
            uint32_t C = i;
            for (int k = 0; k < 8; ++k)
            {
                C = (C & 1) ? (0xEDB88320u ^ (C >> 1)) : (C >> 1);
            }
            Table[i] = C;
        }
        bBuilt = true;
    }

    uint32_t Crc = Seed ^ 0xFFFFFFFFu;
    const uint8_t* P = static_cast<const uint8_t*>(Data);
    for (size_t i = 0; i < Length; ++i)
    {
        Crc = Table[(Crc ^ P[i]) & 0xFF] ^ (Crc >> 8);
    }
    return Crc ^ 0xFFFFFFFFu;
}

bool IsSafeZipName(const std::string& Name)
{
    if (Name.empty() || Name.size() > 4096)
    {
        return false;
    }
    if (Name[0] == '/' || Name[0] == '\\')
    {
        return false;
    }
    if (Name.find('\\') != std::string::npos)
    {
        return false;
    }
    if (Name.size() >= 2 && Name[1] == ':')
    {
        return false;
    }
    // No ".." segment, checked as a segment and not as a substring, so that a
    // legitimate name like "a..b/c" is not rejected.
    size_t Start = 0;
    while (Start <= Name.size())
    {
        const size_t Slash = Name.find('/', Start);
        const size_t End = (Slash == std::string::npos) ? Name.size() : Slash;
        if (Name.compare(Start, End - Start, "..") == 0)
        {
            return false;
        }
        if (Slash == std::string::npos)
        {
            break;
        }
        Start = Slash + 1;
    }
    return true;
}

// --- reader ----------------------------------------------------------------

std::string Utf8Lossy(const uint8_t* P, size_t N)
{
    std::string Out;
    Out.reserve(N);
    size_t i = 0;
    while (i < N)
    {
        const uint8_t B = P[i];
        size_t Len = 0;
        uint32_t Cp = 0, Min = 0;
        if (B < 0x80) { Out.push_back(char(B)); ++i; continue; }
        else if ((B & 0xE0) == 0xC0) { Len = 2; Cp = B & 0x1F; Min = 0x80; }
        else if ((B & 0xF0) == 0xE0) { Len = 3; Cp = B & 0x0F; Min = 0x800; }
        else if ((B & 0xF8) == 0xF0) { Len = 4; Cp = B & 0x07; Min = 0x10000; }
        bool bOk = Len != 0 && i + Len <= N;
        for (size_t k = 1; bOk && k < Len; ++k)
        {
            if ((P[i + k] & 0xC0) != 0x80) { bOk = false; break; }
            Cp = (Cp << 6) | (P[i + k] & 0x3F);
        }
        bOk = bOk && Cp >= Min && Cp <= 0x10FFFF && !(Cp >= 0xD800 && Cp <= 0xDFFF);
        if (bOk)
        {
            Out.append(reinterpret_cast<const char*>(P + i), Len);
            i += Len;
        }
        else
        {
            Out.append("\xEF\xBF\xBD");   // U+FFFD, then resynchronise one byte on
            ++i;
        }
    }
    return Out;
}

bool ZipReader::OpenFile(const std::string& Path, Report& Rep)
{
    std::FILE* F = nullptr;
#if defined(_MSC_VER)
    if (fopen_s(&F, Path.c_str(), "rb") != 0)
    {
        F = nullptr;
    }
#else
    F = std::fopen(Path.c_str(), "rb");
#endif
    if (!F)
    {
        Rep.Error(code::ContainerInvalid, Path, "cannot open file for reading");
        return false;
    }
    std::fseek(F, 0, SEEK_END);
    const long Size = std::ftell(F);
    std::fseek(F, 0, SEEK_SET);
    if (Size < 0)
    {
        std::fclose(F);
        Rep.Error(code::ContainerInvalid, Path, "cannot determine file size");
        return false;
    }
    // static_cast, not a functional cast: `std::vector<uint8_t> Bytes(size_t(Size))`
    // is a function declaration to a C++ compiler, not a variable.
    std::vector<uint8_t> Bytes(static_cast<size_t>(Size));
    if (Size > 0 && std::fread(Bytes.data(), 1, size_t(Size), F) != size_t(Size))
    {
        std::fclose(F);
        Rep.Error(code::ContainerInvalid, Path, "short read");
        return false;
    }
    std::fclose(F);
    return OpenMemory(std::move(Bytes), Rep);
}

bool ZipReader::OpenMemory(std::vector<uint8_t> Bytes, Report& Rep)
{
    Raw = std::move(Bytes);
    EntryList.clear();
    return Parse(Rep);
}

bool ZipReader::Parse(Report& Rep)
{
    const size_t N = Raw.size();
    if (N < 22)
    {
        Rep.Error(code::BadContainer, "", "shorter than an end-of-central-directory record");
        return false;
    }

    // MINI-SPECS 5.1: search backwards from filesize - 22, no lower than
    // filesize - 22 - 65535, because the comment is the only thing that can
    // follow and its length field is 16 bits.
    const size_t Lowest = (N >= size_t(22) + 65535) ? (N - 22 - 65535) : 0;
    size_t EocdOffset = size_t(-1);
    // MINI-SPECS 5.4 rule 1: the record at the HIGHEST offset whose signature
    // matches AND whose comment length accounts for exactly the rest of the file.
    for (size_t Off = N - 22; ; --Off)
    {
        if (Rd32(&Raw[Off]) == kSigEocd && size_t(Rd16(&Raw[Off + 20])) == N - Off - 22)
        {
            EocdOffset = Off;
            break;
        }
        if (Off == Lowest)
        {
            break;
        }
    }
    if (EocdOffset == size_t(-1))
    {
        Rep.Error(code::BadContainer, "",
                  "no end-of-central-directory record whose comment length matches the end of the file");
        return false;
    }

    const uint8_t* E = &Raw[EocdOffset];
    const uint16_t RecordsHere = Rd16(E + 8);
    const uint16_t RecordsTotal = Rd16(E + 10);
    const uint32_t CdSize = Rd32(E + 12);
    const uint32_t CdOffset = Rd32(E + 16);

    // MINI-SPECS 5.5: two independent zip64 signals. Either is enough, and a
    // zip32-only reader MUST refuse the CONTAINER -- not a node -- and read
    // nothing, rather than following sentinels as if they were offsets.
    const bool bSentinel = (RecordsHere == 0xFFFF) || (RecordsTotal == 0xFFFF)
                        || (CdSize == 0xFFFFFFFFu) || (CdOffset == 0xFFFFFFFFu);
    bool bLocator = false;
    if (EocdOffset >= 20)
    {
        bLocator = (Rd32(&Raw[EocdOffset - 20]) == kSigZip64Locator);
    }
    if (bSentinel || bLocator)
    {
        Rep.Error(code::Zip64Unsupported, "",
                  bSentinel ? "zip64 sentinel present in the end-of-central-directory record"
                            : "zip64 end-of-central-directory locator present");
        return false;
    }

    // MINI-SPECS 5.4 rule 2: exactly `total records` records, one after another
    // from the central-directory offset; the directory's byte size is NOT used to
    // walk it (it matters only as the zip64 sentinel above).
    size_t P = CdOffset;
    const size_t CdEnd = N;
    EntryList.reserve(RecordsTotal);
    for (uint16_t i = 0; i < RecordsTotal; ++i)
    {
        if (P + 46 > CdEnd)
        {
            Rep.Error(code::BadContainer, "", "central directory runs past the end of the file");
            return false;
        }
        const uint8_t* C = &Raw[P];
        if (Rd32(C) != kSigCentral)
        {
            Rep.Error(code::BadContainer, "", "bad central directory file header signature");
            return false;
        }
        ZipEntry Ent;
        Ent.flags            = Rd16(C + 8);
        Ent.method           = Rd16(C + 10);
        Ent.crc32            = Rd32(C + 16);
        Ent.compressedSize   = Rd32(C + 20);
        Ent.uncompressedSize = Rd32(C + 24);
        const uint16_t NameLen  = Rd16(C + 28);
        const uint16_t ExtraLen = Rd16(C + 30);
        const uint16_t CommLen  = Rd16(C + 32);
        Ent.localHeaderOffset = Rd32(C + 42);

        if (P + 46 + NameLen + ExtraLen + CommLen > CdEnd)
        {
            Rep.Error(code::BadContainer, "", "a central directory name runs past the end of the file");
            return false;
        }
        // rule 3: UTF-8 with every invalid sequence replaced by U+FFFD; a damaged
        // name is then a name no manifest path matches (file-missing), never a
        // malformed directory. Bit 11 is not consulted.
        Ent.name = Utf8Lossy(C + 46, NameLen);
        // rule 4: bit 3 refuses the container; bit 0 is per entry (Read).
        if (Ent.flags & 0x0008)
        {
            Rep.Error(code::BadContainer, Ent.name,
                      "general purpose flag bit 3 set (sizes in a trailing data descriptor)");
            return false;
        }

        // Per-entry zip64 sentinels (MINI-SPECS 5.5 step 5) are just as fatal
        // as the container-level ones, for the same reason.
        if (Ent.compressedSize == 0xFFFFFFFFu || Ent.uncompressedSize == 0xFFFFFFFFu
            || Ent.localHeaderOffset == 0xFFFFFFFFu)
        {
            Rep.Error(code::Zip64Unsupported, Ent.name, "zip64 sentinel in a central directory entry");
            return false;
        }

        P += 46 + NameLen + ExtraLen + CommLen;
        // rule 5 / SPEC 1 "one name, one entry": refused whole.
        for (const ZipEntry& Seen : EntryList)
        {
            if (Seen.name == Ent.name)
            {
                Rep.Error(code::BadContainer, Ent.name,
                          "the central directory names this entry twice; which bytes are the file "
                          "cannot be decided (SPEC 1)");
                return false;
            }
        }
        EntryList.push_back(std::move(Ent));
    }

    return true;
}

bool ZipReader::Has(const std::string& Name) const
{
    for (const ZipEntry& E : EntryList)
    {
        if (E.name == Name)
        {
            return true;
        }
    }
    return false;
}


// --- inflate (RFC 1951), for method-8 entries ------------------------------
//
// Added for the werk release (W5c): SPEC.md section 1, ruling 9 -- every
// reference reader reads deflate, and fixtures/crate-cc0-lean-v1-deflated.werk
// exercises it. The bitstream is MINI-SPECS 7.1. A stream that does not
// decode, or that inflates to a size or CRC-32 other than the central
// directory's, is damage to that entry (zip-entry-invalid).
namespace
{
    struct BitIn
    {
        const uint8_t* P;
        size_t N;
        size_t Pos = 0;
        uint32_t Bit = 0;
        uint32_t Cnt = 0;
        bool Bad = false;
        BitIn(const uint8_t* InP, size_t InN) : P(InP), N(InN) {}
        uint32_t Get(uint32_t Need)
        {
            if (Need == 0)
            {
                return 0;
            }
            while (Cnt < Need)
            {
                if (Pos >= N)
                {
                    Bad = true;
                    return 0;
                }
                Bit |= uint32_t(P[Pos++]) << Cnt;
                Cnt += 8;
            }
            const uint32_t V = Bit & ((1u << Need) - 1u);
            Bit >>= Need;
            Cnt -= Need;
            return V;
        }
    };

    struct Huff
    {
        uint16_t Count[16] = {};
        uint16_t Symbol[320] = {};
    };

    // Canonical Huffman table from code lengths (RFC 1951 3.2.2). False for an
    // over-subscribed set; an incomplete set is legal.
    bool Build(Huff& H, const uint8_t* Lengths, int N)
    {
        for (int i = 0; i < 16; ++i) { H.Count[i] = 0; }
        for (int i = 0; i < N; ++i) { H.Count[Lengths[i]]++; }
        H.Count[0] = 0;
        int Left = 1;
        for (int Len = 1; Len < 16; ++Len)
        {
            Left <<= 1;
            Left -= H.Count[Len];
            if (Left < 0) { return false; }
        }
        uint16_t Offs[16] = {};
        for (int Len = 1; Len < 15; ++Len) { Offs[Len + 1] = uint16_t(Offs[Len] + H.Count[Len]); }
        for (int i = 0; i < N; ++i)
        {
            if (Lengths[i]) { H.Symbol[Offs[Lengths[i]]++] = uint16_t(i); }
        }
        return true;
    }

    int Decode(BitIn& B, const Huff& H)
    {
        int Code = 0, First = 0, Index = 0;
        for (int Len = 1; Len < 16; ++Len)
        {
            Code |= int(B.Get(1));
            if (B.Bad) { return -1; }
            const int Count = H.Count[Len];
            if (Code - Count < First) { return H.Symbol[Index + (Code - First)]; }
            Index += Count;
            First += Count;
            First <<= 1;
            Code <<= 1;
        }
        return -1;
    }

    const uint16_t kLenBase[29] = { 3,4,5,6,7,8,9,10,11,13,15,17,19,23,27,31,35,43,51,59,
                                    67,83,99,115,131,163,195,227,258 };
    const uint16_t kLenExtra[29] = { 0,0,0,0,0,0,0,0,1,1,1,1,2,2,2,2,3,3,3,3,4,4,4,4,5,5,5,5,0 };
    const uint16_t kDistBase[30] = { 1,2,3,4,5,7,9,13,17,25,33,49,65,97,129,193,257,385,513,769,
                                     1025,1537,2049,3073,4097,6145,8193,12289,16385,24577 };
    const uint16_t kDistExtra[30] = { 0,0,0,0,1,1,2,2,3,3,4,4,5,5,6,6,7,7,8,8,9,9,10,10,11,11,
                                      12,12,13,13 };

    bool Codes(BitIn& B, std::vector<uint8_t>& Out, const Huff& Lit, const Huff& Dist,
               size_t Limit, std::string& Err)
    {
        for (;;)
        {
            const int Sym = Decode(B, Lit);
            if (Sym < 0) { Err = "bad literal/length code"; return false; }
            if (Sym < 256)
            {
                if (Out.size() >= Limit) { Err = "inflates past the declared size"; return false; }
                Out.push_back(uint8_t(Sym));
            }
            else if (Sym == 256)
            {
                return true;
            }
            else
            {
                const int L = Sym - 257;
                if (L >= 29) { Err = "invalid length symbol"; return false; }
                const size_t Len = kLenBase[L] + B.Get(kLenExtra[L]);
                const int D = Decode(B, Dist);
                if (D < 0 || D >= 30) { Err = "bad distance code"; return false; }
                const size_t Dst = kDistBase[D] + B.Get(kDistExtra[D]);
                if (B.Bad) { Err = "stream ends inside a match"; return false; }
                if (Dst > Out.size()) { Err = "distance reaches before the start"; return false; }
                if (Out.size() + Len > Limit) { Err = "inflates past the declared size"; return false; }
                const size_t From = Out.size() - Dst;
                for (size_t k = 0; k < Len; ++k) { Out.push_back(Out[From + k]); }
            }
        }
    }

    bool InflateRaw(const uint8_t* In, size_t N, size_t Limit, std::vector<uint8_t>& Out,
                    std::string& Err)
    {
        BitIn B(In, N);
        Out.clear();
        Out.reserve(Limit);
        static const uint8_t kOrder[19] = { 16,17,18,0,8,7,9,6,10,5,11,4,12,3,13,2,14,1,15 };
        uint32_t Final = 0;
        do
        {
            Final = B.Get(1);
            const uint32_t Type = B.Get(2);
            if (B.Bad) { Err = "stream ends inside a block header"; return false; }
            if (Type == 0)
            {
                B.Bit = 0;
                B.Cnt = 0;   // drop to a byte boundary
                if (B.Pos + 4 > N) { Err = "stored block header truncated"; return false; }
                const uint32_t Len = uint32_t(In[B.Pos]) | (uint32_t(In[B.Pos + 1]) << 8);
                const uint32_t NLen = uint32_t(In[B.Pos + 2]) | (uint32_t(In[B.Pos + 3]) << 8);
                B.Pos += 4;
                if ((Len ^ 0xFFFFu) != NLen) { Err = "stored block LEN/NLEN mismatch"; return false; }
                if (B.Pos + Len > N) { Err = "stored block truncated"; return false; }
                if (Out.size() + Len > Limit) { Err = "inflates past the declared size"; return false; }
                Out.insert(Out.end(), In + B.Pos, In + B.Pos + Len);
                B.Pos += Len;
            }
            else if (Type == 1 || Type == 2)
            {
                Huff Lit, Dist;
                uint8_t Lengths[320] = {};
                if (Type == 1)
                {
                    int i = 0;
                    for (; i < 144; ++i) { Lengths[i] = 8; }
                    for (; i < 256; ++i) { Lengths[i] = 9; }
                    for (; i < 280; ++i) { Lengths[i] = 7; }
                    for (; i < 288; ++i) { Lengths[i] = 8; }
                    Build(Lit, Lengths, 288);
                    for (i = 0; i < 30; ++i) { Lengths[i] = 5; }
                    Build(Dist, Lengths, 30);
                }
                else
                {
                    const int HLit = int(B.Get(5)) + 257;
                    const int HDist = int(B.Get(5)) + 1;
                    const int HCLen = int(B.Get(4)) + 4;
                    if (B.Bad || HLit > 286 || HDist > 30) { Err = "bad dynamic block header"; return false; }
                    uint8_t CL[19] = {};
                    for (int i = 0; i < HCLen; ++i) { CL[kOrder[i]] = uint8_t(B.Get(3)); }
                    Huff LenH;
                    if (!Build(LenH, CL, 19)) { Err = "bad code-length code"; return false; }
                    int i = 0;
                    while (i < HLit + HDist)
                    {
                        const int Sym = Decode(B, LenH);
                        if (Sym < 0) { Err = "bad code-length symbol"; return false; }
                        if (Sym < 16) { Lengths[i++] = uint8_t(Sym); continue; }
                        int Rep = 0;
                        uint8_t Val = 0;
                        if (Sym == 16)
                        {
                            if (i == 0) { Err = "repeat with no previous length"; return false; }
                            Val = Lengths[i - 1];
                            Rep = 3 + int(B.Get(2));
                        }
                        else if (Sym == 17) { Rep = 3 + int(B.Get(3)); }
                        else { Rep = 11 + int(B.Get(7)); }
                        if (i + Rep > HLit + HDist) { Err = "code lengths overrun"; return false; }
                        while (Rep--) { Lengths[i++] = Val; }
                    }
                    if (Lengths[256] == 0) { Err = "no end-of-block code"; return false; }
                    if (!Build(Lit, Lengths, HLit) || !Build(Dist, Lengths + HLit, HDist))
                    {
                        Err = "over-subscribed Huffman code";
                        return false;
                    }
                }
                if (!Codes(B, Out, Lit, Dist, Limit, Err)) { return false; }
            }
            else
            {
                Err = "reserved block type 3";
                return false;
            }
        } while (!Final);
        return true;
    }
}

bool ZipReader::Read(const std::string& Name, std::vector<uint8_t>& Out, Report& Rep) const
{
    Out.clear();
    const ZipEntry* Found = nullptr;
    for (const ZipEntry& E : EntryList)
    {
        if (E.name == Name)
        {
            Found = &E;
            break;
        }
    }
    if (!Found)
    {
        Rep.Error(code::FileMissing, Name, "no such entry in the container");
        return false;
    }
    if (Found->method != 0 && Found->method != 8)
    {
        // SPEC.md section 1, ruling 9: any method other than 0 and 8 is
        // refused for that entry, by name.
        Rep.Error(code::ZipEntryUnsupported, Name,
                  "compression method " + std::to_string(Found->method)
                      + "; this reader implements store (0) and deflate (8)");
        return false;
    }
    if (Found->flags & 0x0001)
    {
        Rep.Error(code::ZipEntryUnsupported, Name, "encrypted entry");
        return false;
    }

    const size_t Lho = size_t(Found->localHeaderOffset);
    if (Lho + 30 > Raw.size())
    {
        Rep.Error(code::ZipEntryInvalid, Name, "local header runs past the end of the file");
        return false;
    }
    const uint8_t* L = &Raw[Lho];
    if (Rd32(L) != kSigLocal)
    {
        Rep.Error(code::ZipEntryInvalid, Name, "bad local file header signature");
        return false;
    }
    // MINI-SPECS 5.3: the local n and m can differ from the central
    // directory's; always re-read them here.
    const uint16_t NameLen = Rd16(L + 26);
    const uint16_t ExtraLen = Rd16(L + 28);
    const size_t DataOffset = Lho + 30 + NameLen + ExtraLen;
    if (DataOffset + size_t(Found->compressedSize) > Raw.size())
    {
        Rep.Error(code::ZipEntryInvalid, Name, "entry data runs past the end of the file");
        return false;
    }

    if (Found->method == 8)
    {
        std::string Err;
        if (!InflateRaw(&Raw[DataOffset], size_t(Found->compressedSize),
                        size_t(Found->uncompressedSize), Out, Err)
            || Out.size() != size_t(Found->uncompressedSize))
        {
            Rep.Error(code::ZipEntryInvalid, Name,
                      "deflate stream does not decode to the directory's size: "
                          + (Err.empty() ? std::string("short output") : Err));
            Out.clear();
            return false;
        }
    }
    else
    {
        Out.assign(Raw.begin() + DataOffset, Raw.begin() + DataOffset + size_t(Found->compressedSize));
    }

    // MINI-SPECS 5.4 rule 6: method-0 data is `compressed size` bytes verbatim,
    // checked by the manifest's size and sha256, not by the directory's CRC-32.
    // Inflated bytes are handed over only after the directory's CRC-32 (SPEC 1).
    const uint32_t Actual = Found->method == 8 ? Crc32(Out.data(), Out.size()) : Found->crc32;
    if (Actual != Found->crc32)
    {
        char Buf[128];
        std::snprintf(Buf, sizeof(Buf), "crc32 %08x, central directory says %08x",
                      Actual, Found->crc32);
        Rep.Error(code::ZipEntryInvalid, Name, Buf);
        Out.clear();
        return false;
    }
    return true;
}

// --- writer ----------------------------------------------------------------

void ZipWriter::Add(const std::string& Name, std::vector<uint8_t> Bytes)
{
    Items.emplace_back(Name, std::move(Bytes));
}

bool ZipWriter::Has(const std::string& Name) const
{
    for (const auto& It : Items)
    {
        if (It.first == Name)
        {
            return true;
        }
    }
    return false;
}

std::vector<uint8_t> ZipWriter::Build(const std::string& PrefixThroughName,
                                      uint64_t& OutPrefixBytes) const
{
    std::vector<uint8_t> Out;
    struct Rec { uint32_t Crc; uint32_t Size; uint32_t Offset; };
    std::vector<Rec> Recs;
    Recs.reserve(Items.size());

    OutPrefixBytes = 0;

    for (const auto& It : Items)
    {
        Rec R;
        R.Offset = uint32_t(Out.size());
        R.Size = uint32_t(It.second.size());
        R.Crc = Crc32(It.second.data(), It.second.size());

        Wr32(Out, kSigLocal);
        Wr16(Out, 20);      // version needed: 2.0, which is what store requires
        Wr16(Out, 0x0800);  // flag bit 11: names are UTF-8. Bit 3 stays clear.
        Wr16(Out, 0);       // method 0, store
        Wr16(Out, 0);       // mod time  -- fixed, see the comment below
        Wr16(Out, 0x0021);  // mod date  -- 1980-01-01
        Wr32(Out, R.Crc);
        Wr32(Out, R.Size);
        Wr32(Out, R.Size);
        Wr16(Out, uint16_t(It.first.size()));
        Wr16(Out, 0);       // no extra field
        Out.insert(Out.end(), It.first.begin(), It.first.end());
        Out.insert(Out.end(), It.second.begin(), It.second.end());

        Recs.push_back(R);

        if (!PrefixThroughName.empty() && It.first == PrefixThroughName)
        {
            OutPrefixBytes = uint64_t(Out.size());
        }
    }

    const uint32_t CdOffset = uint32_t(Out.size());
    for (size_t i = 0; i < Items.size(); ++i)
    {
        const auto& It = Items[i];
        const Rec& R = Recs[i];
        Wr32(Out, kSigCentral);
        Wr16(Out, 20);      // version made by
        Wr16(Out, 20);      // version needed
        Wr16(Out, 0x0800);
        Wr16(Out, 0);
        Wr16(Out, 0);
        Wr16(Out, 0x0021);
        Wr32(Out, R.Crc);
        Wr32(Out, R.Size);
        Wr32(Out, R.Size);
        Wr16(Out, uint16_t(It.first.size()));
        Wr16(Out, 0);       // extra
        Wr16(Out, 0);       // comment
        Wr16(Out, 0);       // disk number start
        Wr16(Out, 0);       // internal attributes
        Wr32(Out, 0);       // external attributes
        Wr32(Out, R.Offset);
        Out.insert(Out.end(), It.first.begin(), It.first.end());
    }
    const uint32_t CdSize = uint32_t(Out.size()) - CdOffset;

    Wr32(Out, kSigEocd);
    Wr16(Out, 0);
    Wr16(Out, 0);
    Wr16(Out, uint16_t(Items.size()));
    Wr16(Out, uint16_t(Items.size()));
    Wr32(Out, CdSize);
    Wr32(Out, CdOffset);
    Wr16(Out, 0); // no comment

    return Out;
}

bool ZipWriter::WriteFile(const std::string& Path, const std::string& PrefixThroughName,
                          uint64_t& OutPrefixBytes, Report& Rep) const
{
    for (const auto& It : Items)
    {
        if (!IsSafeZipName(It.first))
        {
            Rep.Error(code::ContainerInvalid, It.first, "unsafe entry name refused by the writer");
            return false;
        }
    }
    const std::vector<uint8_t> Bytes = Build(PrefixThroughName, OutPrefixBytes);

    std::FILE* F = nullptr;
#if defined(_MSC_VER)
    if (fopen_s(&F, Path.c_str(), "wb") != 0)
    {
        F = nullptr;
    }
#else
    F = std::fopen(Path.c_str(), "wb");
#endif
    if (!F)
    {
        Rep.Error(code::ContainerInvalid, Path, "cannot open file for writing");
        return false;
    }
    const bool bOk = Bytes.empty() || std::fwrite(Bytes.data(), 1, Bytes.size(), F) == Bytes.size();
    std::fclose(F);
    if (!bOk)
    {
        Rep.Error(code::ContainerInvalid, Path, "short write");
        return false;
    }
    return true;
}

// --- selftest --------------------------------------------------------------

std::vector<std::string> ZipSelftest(bool bVerbose)
{
    std::vector<std::string> Bad;

    // MINI-SPECS section 6 test vector.
    {
        const char* In = "123456789";
        const uint32_t Got = Crc32(In, 9);
        if (Got != 0xCBF43926u)
        {
            char Buf[128];
            std::snprintf(Buf, sizeof(Buf), "crc32(\"123456789\"): got %08x want cbf43926", Got);
            Bad.push_back(Buf);
        }
        else if (bVerbose)
        {
            std::printf("  OK crc32(\"123456789\") == 0xcbf43926\n");
        }
    }

    // Round trip: write three entries in a deliberate order, read them back,
    // and check both the bytes and that the physical order survived -- law 9
    // depends on the order being what the writer chose.
    {
        ZipWriter W;
        W.Add("MANIFEST.json", std::vector<uint8_t>{ '{', '}' });
        std::vector<uint8_t> Big(5000);
        for (size_t i = 0; i < Big.size(); ++i)
        {
            Big[i] = uint8_t(i * 7 + 3);
        }
        W.Add("loaders/werk_read.py", Big);
        W.Add("geometry/game.glb", std::vector<uint8_t>{ 'g', 'l', 'T', 'F' });

        uint64_t PrefixBytes = 0;
        const std::vector<uint8_t> Bytes = W.Build("loaders/werk_read.py", PrefixBytes);

        Report Rep;
        ZipReader R;
        if (!R.OpenMemory(Bytes, Rep))
        {
            Bad.push_back("store round trip: reader refused its own writer's output");
        }
        else
        {
            if (R.Entries().size() != 3)
            {
                Bad.push_back("store round trip: entry count "
                              + std::to_string(R.Entries().size()) + " != 3");
            }
            else if (R.Entries()[0].name != "MANIFEST.json"
                     || R.Entries()[1].name != "loaders/werk_read.py"
                     || R.Entries()[2].name != "geometry/game.glb")
            {
                Bad.push_back("store round trip: physical entry order not preserved");
            }
            std::vector<uint8_t> Got;
            if (!R.Read("loaders/werk_read.py", Got, Rep) || Got != Big)
            {
                Bad.push_back("store round trip: payload bytes differ");
            }
            else if (bVerbose)
            {
                std::printf("  OK store round trip, 3 entries, order preserved\n");
            }
            // The measured prefix must end exactly where the named entry's
            // data ends, so it is checkable rather than advisory.
            if (PrefixBytes == 0 || PrefixBytes > Bytes.size())
            {
                Bad.push_back("prefix measurement out of range");
            }
        }
    }

    // MINI-SPECS 5.4 (release-fixes) rule 6: a flipped byte of METHOD-0 data is
    // returned verbatim -- the manifest's size + sha256 catch it (the damage
    // gauntlet of the gate measures that end to end), not the directory CRC.
    {
        ZipWriter W;
        W.Add("a.bin", std::vector<uint8_t>{ 1, 2, 3, 4, 5, 6, 7, 8 });
        uint64_t Px = 0;
        std::vector<uint8_t> Bytes = W.Build("", Px);
        Bytes[35] ^= 0xFF;   // entry data starts at 30 + strlen("a.bin")
        Report Rep;
        ZipReader R;
        std::vector<uint8_t> Got;
        if (!R.OpenMemory(Bytes, Rep) || !R.Read("a.bin", Got, Rep) || Got.size() != 8 || Got[0] != 0xFE)
        {
            Bad.push_back("rule 6: method-0 bytes were not handed over verbatim");
        }
    }
    auto Refused = [&](const char* What, std::vector<uint8_t> Bytes)
    {
        Report Rep;
        ZipReader R;
        if (R.OpenMemory(std::move(Bytes), Rep))
        {
            Bad.push_back(std::string(What) + ": container was NOT refused");
            return;
        }
        bool bBad = false;
        for (const ReportEntry& E : Rep.All())
        {
            bBad = bBad || E.code == code::BadContainer;
        }
        if (!bBad)
        {
            Bad.push_back(std::string(What) + ": refused, but not as bad-container");
        }
        else if (bVerbose)
        {
            std::printf("  OK %s -> bad-container\n", What);
        }
    };
    // rule 5 / SPEC 1: one name, two entries
    {
        ZipWriter W;
        W.Add("a.bin", std::vector<uint8_t>{ 1 });
        W.Add("a.bin", std::vector<uint8_t>{ 2 });
        uint64_t Px = 0;
        Refused("duplicate entry name", W.Build("", Px));
    }
    // rule 4: flag bit 3 in the central directory
    {
        ZipWriter W;
        W.Add("a.bin", std::vector<uint8_t>{ 1, 2 });
        uint64_t Px = 0;
        std::vector<uint8_t> Bytes = W.Build("", Px);
        const size_t Cd = size_t(Rd32(&Bytes[Bytes.size() - 22 + 16]));
        Bytes[Cd + 8] |= 0x08;
        Refused("flag bit 3", Bytes);
    }
    // rule 1: an EOCD whose comment length does not reach the end of the file
    {
        ZipWriter W;
        W.Add("a.bin", std::vector<uint8_t>{ 1, 2 });
        uint64_t Px = 0;
        std::vector<uint8_t> Bytes = W.Build("", Px);
        Bytes.push_back(0x00);   // one trailing byte the comment length does not cover
        Refused("EOCD comment length", Bytes);
    }
    // rule 3: an invalid UTF-8 name decodes lossily, it does not refuse
    {
        const uint8_t Raw[] = { 'a', 0xFF, 'b' };
        if (Utf8Lossy(Raw, 3) != std::string("a\xEF\xBF\xBD" "b"))
        {
            Bad.push_back("rule 3: invalid UTF-8 not replaced by U+FFFD");
        }
    }

    // Zip64 detection: plant the locator signature immediately before the
    // EOCD and require a container-scoped refusal.
    {
        ZipWriter W;
        W.Add("a.bin", std::vector<uint8_t>{ 9, 9, 9 });
        uint64_t Px = 0;
        std::vector<uint8_t> Bytes = W.Build("", Px);
        const size_t EocdAt = Bytes.size() - 22;
        std::vector<uint8_t> Locator(20, 0);
        Locator[0] = 0x50; Locator[1] = 0x4B; Locator[2] = 0x06; Locator[3] = 0x07;
        Bytes.insert(Bytes.begin() + EocdAt, Locator.begin(), Locator.end());
        Report Rep;
        ZipReader R;
        if (R.OpenMemory(Bytes, Rep))
        {
            Bad.push_back("zip64 locator was not detected");
        }
        else
        {
            bool bNamed = false;
            for (const ReportEntry& E : Rep.All())
            {
                if (E.code == code::Zip64Unsupported)
                {
                    bNamed = true;
                }
            }
            if (!bNamed)
            {
                Bad.push_back("zip64 refusal was not reported as zip64-unsupported");
            }
            else if (bVerbose)
            {
                std::printf("  OK zip64 locator -> container-scoped zip64-unsupported\n");
            }
        }
    }

    // Name safety.
    {
        const char* GoodNames[] = { "MANIFEST.json", "spec/schemas/a.json", "a..b/c.bin" };
        const char* BadNames[]  = { "/abs.json", "../escape", "a/../../x", "C:/x", "a\\b" };
        for (const char* N : GoodNames)
        {
            if (!IsSafeZipName(N))
            {
                Bad.push_back(std::string("IsSafeZipName rejected a good name: ") + N);
            }
        }
        for (const char* N : BadNames)
        {
            if (IsSafeZipName(N))
            {
                Bad.push_back(std::string("IsSafeZipName accepted a bad name: ") + N);
            }
        }
        if (bVerbose)
        {
            std::printf("  OK zip name safety, 3 good and 5 bad\n");
        }
    }

    return Bad;
}

} // namespace werk
