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
        Rep.Error(code::ContainerInvalid, "", "shorter than an end-of-central-directory record");
        return false;
    }

    // MINI-SPECS 5.1: search backwards from filesize - 22, no lower than
    // filesize - 22 - 65535, because the comment is the only thing that can
    // follow and its length field is 16 bits.
    const size_t Lowest = (N >= size_t(22) + 65535) ? (N - 22 - 65535) : 0;
    size_t EocdOffset = size_t(-1);
    for (size_t Off = N - 22; ; --Off)
    {
        if (Rd32(&Raw[Off]) == kSigEocd)
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
        Rep.Error(code::ContainerInvalid, "", "no end-of-central-directory record found");
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

    if (uint64_t(CdOffset) + uint64_t(CdSize) > uint64_t(N))
    {
        Rep.Error(code::ContainerInvalid, "", "central directory runs past the end of the file");
        return false;
    }

    size_t P = CdOffset;
    const size_t CdEnd = size_t(CdOffset) + size_t(CdSize);
    EntryList.reserve(RecordsTotal);
    for (uint16_t i = 0; i < RecordsTotal; ++i)
    {
        if (P + 46 > CdEnd)
        {
            Rep.Error(code::ContainerInvalid, "", "central directory truncated");
            return false;
        }
        const uint8_t* C = &Raw[P];
        if (Rd32(C) != kSigCentral)
        {
            Rep.Error(code::ContainerInvalid, "", "bad central directory file header signature");
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
            Rep.Error(code::ContainerInvalid, "", "central directory entry truncated");
            return false;
        }
        Ent.name.assign(reinterpret_cast<const char*>(C + 46), NameLen);

        // Per-entry zip64 sentinels (MINI-SPECS 5.5 step 5) are just as fatal
        // as the container-level ones, for the same reason.
        if (Ent.compressedSize == 0xFFFFFFFFu || Ent.uncompressedSize == 0xFFFFFFFFu
            || Ent.localHeaderOffset == 0xFFFFFFFFu)
        {
            Rep.Error(code::Zip64Unsupported, Ent.name, "zip64 sentinel in a central directory entry");
            return false;
        }

        EntryList.push_back(std::move(Ent));
        P += 46 + NameLen + ExtraLen + CommLen;
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
    if (Found->method != 0)
    {
        // SPEC.md section 1: a store-only reader "must say so rather than
        // return wrong bytes".
        Rep.Error(code::CompressionUnsupported, Name,
                  "compression method " + std::to_string(Found->method)
                      + "; this reader implements store (method 0) only");
        return false;
    }
    if (Found->flags & 0x0008)
    {
        Rep.Error(code::ContainerInvalid, Name,
                  "general purpose flag bit 3 set (sizes in a trailing data descriptor); "
                  "MINI-SPECS 5.4 forbids it in a werk package");
        return false;
    }

    const size_t Lho = size_t(Found->localHeaderOffset);
    if (Lho + 30 > Raw.size())
    {
        Rep.Error(code::ContainerInvalid, Name, "local header runs past the end of the file");
        return false;
    }
    const uint8_t* L = &Raw[Lho];
    if (Rd32(L) != kSigLocal)
    {
        Rep.Error(code::ContainerInvalid, Name, "bad local file header signature");
        return false;
    }
    // MINI-SPECS 5.3: the local n and m can differ from the central
    // directory's; always re-read them here.
    const uint16_t NameLen = Rd16(L + 26);
    const uint16_t ExtraLen = Rd16(L + 28);
    const size_t DataOffset = Lho + 30 + NameLen + ExtraLen;
    if (DataOffset + size_t(Found->compressedSize) > Raw.size())
    {
        Rep.Error(code::ContainerInvalid, Name, "entry data runs past the end of the file");
        return false;
    }

    Out.assign(Raw.begin() + DataOffset, Raw.begin() + DataOffset + size_t(Found->compressedSize));

    const uint32_t Actual = Crc32(Out.data(), Out.size());
    if (Actual != Found->crc32)
    {
        char Buf[128];
        std::snprintf(Buf, sizeof(Buf), "crc32 %08x, central directory says %08x",
                      Actual, Found->crc32);
        Rep.Error(code::HashMismatch, Name, Buf);
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

    // A corrupted payload byte must be caught by CRC, not returned.
    {
        ZipWriter W;
        W.Add("a.bin", std::vector<uint8_t>{ 1, 2, 3, 4, 5, 6, 7, 8 });
        uint64_t Px = 0;
        std::vector<uint8_t> Bytes = W.Build("", Px);
        // Entry data starts at 30 + strlen("a.bin") = 35.
        Bytes[35] ^= 0xFF;
        Report Rep;
        ZipReader R;
        std::vector<uint8_t> Got;
        if (!R.OpenMemory(Bytes, Rep))
        {
            Bad.push_back("damaged-payload case: container failed to open at all");
        }
        else if (R.Read("a.bin", Got, Rep))
        {
            Bad.push_back("damaged payload was returned instead of refused");
        }
        else if (bVerbose)
        {
            std::printf("  OK a flipped payload byte is caught by crc32\n");
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
