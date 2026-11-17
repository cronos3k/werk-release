import os
p=os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","WerkLink","Source","WerkLink","Private","Core","werk_zip.cpp")
s=open(p,encoding="utf-8").read()
a=s.index("    // A corrupted payload byte must be caught by CRC, not returned.")
b=s.index("    // Zip64 detection: plant the locator signature")
new=r'''    // MINI-SPECS 5.4 (release-fixes) rule 6: a flipped byte of METHOD-0 data is
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

'''
s=s[:a]+new+s[b:]
open(p,"w",encoding="utf-8",newline="\n").write(s)
print("ok")
