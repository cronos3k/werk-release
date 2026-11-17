"""One-off patch (W5c, release-fixes 26e3e14): bring WerkLink's engine-free reader onto
SPEC 1 / 6 / 12.1 and MINI-SPECS 5.4 of the release-fixes branch. Kept as a record of the
change; run once against WerkLink/Source/WerkLink/Private/Core."""
import os
import sys

CORE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "WerkLink", "Source", "WerkLink",
                    "Private", "Core")


def patch(name, pairs):
    p = os.path.join(CORE, name)
    s = open(p, encoding="utf-8").read()
    for old, new in pairs:
        if s.count(old) != 1:
            sys.exit("%s: anchor found %d times: %r" % (name, s.count(old), old[:70]))
        s = s.replace(old, new)
    open(p, "w", encoding="utf-8", newline="\n").write(s)


# ---------------------------------------------------------------------------- report codes
patch("werk_report.h", [(
    '    inline constexpr const char* ContainerInvalid        = "container-invalid";',
    '    inline constexpr const char* ContainerInvalid        = "container-invalid";\n'
    '    // SPEC 10.1 vocabulary (release-fixes): container-scoped refusals\n'
    '    inline constexpr const char* BadContainer            = "bad-container";\n'
    '    inline constexpr const char* ManifestStructurallyInvalid = "manifest-structurally-invalid";\n'
    '    inline constexpr const char* NodeDead                = "node-dead";'),
])

# ---------------------------------------------------------------------------- zip: MINI-SPECS 5.4
patch("werk_zip.cpp", [
    # rule 1: the EOCD whose comment length accounts for exactly the rest of the file
    ("""    for (size_t Off = N - 22; ; --Off)
    {
        if (Rd32(&Raw[Off]) == kSigEocd)
        {
            EocdOffset = Off;
            break;
        }""",
     """    // MINI-SPECS 5.4 rule 1: the record at the HIGHEST offset whose signature
    // matches AND whose comment length accounts for exactly the rest of the file.
    for (size_t Off = N - 22; ; --Off)
    {
        if (Rd32(&Raw[Off]) == kSigEocd && size_t(Rd16(&Raw[Off + 20])) == N - Off - 22)
        {
            EocdOffset = Off;
            break;
        }"""),
    ("""        Rep.Error(code::ContainerInvalid, "", "no end-of-central-directory record found");""",
     """        Rep.Error(code::BadContainer, "",
                  "no end-of-central-directory record whose comment length matches the end of the file");"""),
    ("""        Rep.Error(code::ContainerInvalid, "", "shorter than an end-of-central-directory record");""",
     """        Rep.Error(code::BadContainer, "", "shorter than an end-of-central-directory record");"""),
    # rule 2: walk exactly `total records`; the byte size is not used to walk
    ("""    if (uint64_t(CdOffset) + uint64_t(CdSize) > uint64_t(N))
    {
        Rep.Error(code::ContainerInvalid, "", "central directory runs past the end of the file");
        return false;
    }

    size_t P = CdOffset;
    const size_t CdEnd = size_t(CdOffset) + size_t(CdSize);""",
     """    // MINI-SPECS 5.4 rule 2: exactly `total records` records, one after another
    // from the central-directory offset; the directory's byte size is NOT used to
    // walk it (it matters only as the zip64 sentinel above).
    size_t P = CdOffset;
    const size_t CdEnd = N;"""),
    ("""            Rep.Error(code::ContainerInvalid, "", "central directory truncated");""",
     """            Rep.Error(code::BadContainer, "", "central directory runs past the end of the file");"""),
    ("""            Rep.Error(code::ContainerInvalid, "", "bad central directory file header signature");""",
     """            Rep.Error(code::BadContainer, "", "bad central directory file header signature");"""),
    ("""            Rep.Error(code::ContainerInvalid, "", "central directory entry truncated");
            return false;
        }
        Ent.name.assign(reinterpret_cast<const char*>(C + 46), NameLen);""",
     """            Rep.Error(code::BadContainer, "", "a central directory name runs past the end of the file");
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
        }"""),
    # rule 5: two records with one name refuse the container
    ("""        EntryList.push_back(std::move(Ent));
        P += 46 + NameLen + ExtraLen + CommLen;
    }

    return true;""",
     """        P += 46 + NameLen + ExtraLen + CommLen;
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

    return true;"""),
    # Read(): bit 3 is now a container refusal (Parse); local header -> zip-entry-invalid
    ("""    if (Found->flags & 0x0008)
    {
        Rep.Error(code::ContainerInvalid, Name,
                  "general purpose flag bit 3 set (sizes in a trailing data descriptor); "
                  "MINI-SPECS 5.4 forbids it in a werk package");
        return false;
    }
""", ""),
    ("""        Rep.Error(code::ContainerInvalid, Name, "local header runs past the end of the file");""",
     """        Rep.Error(code::ZipEntryInvalid, Name, "local header runs past the end of the file");"""),
    ("""        Rep.Error(code::ContainerInvalid, Name, "bad local file header signature");""",
     """        Rep.Error(code::ZipEntryInvalid, Name, "bad local file header signature");"""),
    ("""        Rep.Error(code::ContainerInvalid, Name, "entry data runs past the end of the file");""",
     """        Rep.Error(code::ZipEntryInvalid, Name, "entry data runs past the end of the file");"""),
    # rule 6: method-0 data is checked by the manifest's size + sha256, not by the CRC
    ("""    const uint32_t Actual = Crc32(Out.data(), Out.size());
    if (Actual != Found->crc32)
    {""",
     """    // MINI-SPECS 5.4 rule 6: method-0 data is `compressed size` bytes verbatim,
    // checked by the manifest's size and sha256, not by the directory's CRC-32.
    // Inflated bytes are handed over only after the directory's CRC-32 (SPEC 1).
    const uint32_t Actual = Found->method == 8 ? Crc32(Out.data(), Out.size()) : Found->crc32;
    if (Actual != Found->crc32)
    {"""),
    ("""        Rep.Error(code::HashMismatch, Name, Buf);
        Out.clear();
        return false;
    }
    return true;
}""",
     """        Rep.Error(code::ZipEntryInvalid, Name, Buf);
        Out.clear();
        return false;
    }
    return true;
}"""),
    # the lossy decoder
    ("""bool ZipReader::OpenFile(const std::string& Path, Report& Rep)""",
     """std::string Utf8Lossy(const uint8_t* P, size_t N)
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
            Out.append("\\xEF\\xBF\\xBD");   // U+FFFD, then resynchronise one byte on
            ++i;
        }
    }
    return Out;
}

bool ZipReader::OpenFile(const std::string& Path, Report& Rep)"""),
])
patch("werk_zip.h", [(
    "uint32_t Crc32(const void* Data, size_t Length, uint32_t Seed = 0);",
    "uint32_t Crc32(const void* Data, size_t Length, uint32_t Seed = 0);\n\n"
    "// MINI-SPECS 5.4 rule 3: UTF-8, every invalid sequence replaced by U+FFFD.\n"
    "std::string Utf8Lossy(const uint8_t* P, size_t N);"),
])

# ---------------------------------------------------------------------------- manifest: SPEC 12.1 and 6
patch("werk_manifest.h", [(
    "    int  resolvedIndex = -1;  // index into versions[], -1 when nothing resolved",
    "    // SPEC 12.1 (release-fixes): a node whose own structure is unusable is dead\n"
    "    // under its id, with this reason; empty when the node is well-formed.\n"
    "    std::string malformed;\n\n"
    "    int  resolvedIndex = -1;  // index into versions[], -1 when nothing resolved"),
])
patch("werk_manifest.cpp", [
    ("""    // nodes[]
    if (const JsonValue* A = Root->GetArray("nodes"))
    {
        for (size_t i = 0; i < A->Size(); ++i)
        {
            const JsonValue* O = A->At(i);
            if (!O || !O->IsObject())
            {
                continue;
            }
            Node N;
            N.nodeId = O->GetString("node_id");
            N.type = O->GetString("type");
            N.partId = O->GetString("part_id");
            N.materialId = O->GetString("material_id");
            N.active = int(O->GetNumber("active", 1));""",
     """    // nodes[] -- SPEC 12.1 (release-fixes): `nodes` missing or not an array is
    // the container-scoped structural refusal; a node whose OWN structure is
    // unusable dies under its id and the rest loads (law 3).
    const JsonValue* NodesV = Root->Find("nodes");
    if (!NodesV || !NodesV->IsArray())
    {
        Rep.Error(code::ManifestStructurallyInvalid, "MANIFEST.json",
                  NodesV ? "`nodes` is not an array" : "no `nodes` array");
        return false;
    }
    auto IsInt = [](const JsonValue* V)
    {
        return V && V->IsNumber() && V->number == double(static_cast<long long>(V->number));
    };
    auto IsStr = [](const JsonValue* V) { return V && V->IsString(); };
    if (const JsonValue* A = NodesV)
    {
        for (size_t i = 0; i < A->Size(); ++i)
        {
            const JsonValue* O = A->At(i);
            Node N;
            if (!O || !O->IsObject())
            {
                N.nodeId = "nodes[" + std::to_string(i) + "]";
                N.malformed = "the node is not a JSON object";
                NodeList.push_back(std::move(N));
                continue;
            }
            N.nodeId = O->GetString("node_id");
            N.type = O->GetString("type");
            N.partId = O->GetString("part_id");
            N.materialId = O->GetString("material_id");
            N.active = int(O->GetNumber("active", 0));
            if (!IsStr(O->Find("node_id")))
            {
                N.nodeId = "nodes[" + std::to_string(i) + "]";
                N.malformed = "no string `node_id`";
            }
            else if (!IsStr(O->Find("type")))
            {
                N.malformed = "no string `type`";
            }
            else if (!IsInt(O->Find("active")))
            {
                N.malformed = "no integer `active`";
            }
            else if (!O->GetArray("versions") || O->GetArray("versions")->Size() == 0)
            {
                N.malformed = "no non-empty `versions` array";
            }"""),
    ("""                    if (!VO || !VO->IsObject())
                    {
                        continue;
                    }
                    NodeVersion NV;
                    NV.v = int(VO->GetNumber("v", 1));""",
     """                    if (!VO || !VO->IsObject())
                    {
                        if (N.malformed.empty())
                        {
                            N.malformed = "versions[" + std::to_string(k) + "] is not an object";
                        }
                        continue;
                    }
                    if (N.malformed.empty() && (!IsInt(VO->Find("v")) || !VO->GetArray("files")))
                    {
                        N.malformed = "versions[" + std::to_string(k)
                                      + "] has no integer `v` or no `files` array";
                    }
                    NodeVersion NV;
                    NV.v = int(VO->GetNumber("v", 0));"""),
    ("""                            if (!FO || !FO->IsObject())
                            {
                                continue;
                            }
                            FileRef F;""",
     """                            if (!FO || !FO->IsObject() || !IsStr(FO->Find("path"))
                                || !IsStr(FO->Find("sha256")) || !IsInt(FO->Find("size")))
                            {
                                if (N.malformed.empty())
                                {
                                    N.malformed = "versions[" + std::to_string(k) + "].files["
                                                  + std::to_string(m)
                                                  + "] lacks a string path, a string sha256 or an integer size";
                                }
                                continue;
                            }
                            FileRef F;"""),
    # SPEC 6: check what can be checked without Ed25519
    ("""    if (Reader.Has("SIGNATURE.json"))
    {
        SigState = sig::StateUnverified;
        SigCode = sig::CodeUnverified;
        Rep.Info(sig::CodeUnverified, "SIGNATURE.json",
                 "signature chain present and NOT checked: this adapter does not implement "
                 "Ed25519 and reports the fourth word rather than claiming a verdict");
    }""",
     """    if (Reader.Has("SIGNATURE.json"))
    {
        // SPEC 6 (release-fixes): present-but-unreadable is present-and-invalid,
        // never absent; a reader without Ed25519 still checks that the file is a
        // JSON object whose chain's last entry (and top-level convenience field,
        // when present) names the sha256 of these manifest bytes.
        std::vector<uint8_t> SigBytes;
        Report Local;
        std::string Why;
        JsonPtr Sig;
        if (!Reader.Read("SIGNATURE.json", SigBytes, Local))
        {
            Why = "SIGNATURE.json cannot be read from the container";
        }
        else
        {
            std::string SErr;
            Sig = JsonParse(SigBytes, SErr);
            const JsonValue* Chain = Sig && Sig->IsObject() ? Sig->GetArray("chain") : nullptr;
            const JsonValue* Last = (Chain && Chain->Size() > 0) ? Chain->At(Chain->Size() - 1) : nullptr;
            const JsonValue* Top = Sig && Sig->IsObject() ? Sig->Find("manifest_sha256") : nullptr;
            if (!Sig || !Sig->IsObject())
            {
                Why = "SIGNATURE.json is not a JSON object" + (SErr.empty() ? std::string() : ": " + SErr);
            }
            else if (!Last || !Last->IsObject())
            {
                Why = "SIGNATURE.json has no chain entry";
            }
            else if (Last->GetString("manifest_sha256") != ManifestHash)
            {
                Why = "the last chain entry's manifest_sha256 is not the sha256 of MANIFEST.json";
            }
            else if (Top && (!Top->IsString() || Top->str != ManifestHash))
            {
                Why = "the top-level manifest_sha256 is not the sha256 of MANIFEST.json";
            }
        }
        if (!Why.empty())
        {
            SigState = sig::StateInvalid;
            SigCode = sig::CodeInvalid;
            Rep.Error(sig::CodeInvalid, "SIGNATURE.json", Why);
        }
        else
        {
            SigState = sig::StateUnverified;
            SigCode = sig::CodeUnverified;
            const std::string Alg = Sig->GetString("algorithm");
            if (Alg != "ed25519")
            {
                Rep.Warn(sig::CodeUnverified, "SIGNATURE.json",
                         "chain in algorithm '" + Alg + "', which this adapter does not implement");
            }
            else
            {
                Rep.Info(sig::CodeUnverified, "SIGNATURE.json",
                         "the chain is a JSON object naming this manifest's sha256; its Ed25519 "
                         "signatures are NOT checked: this adapter reports the fourth word");
            }
        }
    }"""),
    # ResolveVersions: a malformed node is dead under its id
    ("""        if (N.versions.empty())
        {
            Rep.Error(code::ManifestInvalid, N.nodeId, "node has no versions");
            continue;
        }""",
     """        if (!N.malformed.empty())
        {
            Rep.Error(code::NodeDead, N.nodeId, "node structure unusable (SPEC 12.1): " + N.malformed);
            continue;
        }
        if (N.versions.empty())
        {
            Rep.Error(code::NodeDead, N.nodeId, "node has no versions");
            continue;
        }"""),
    # sizes are integers now (required); 0 is a real size, so always compare
    ("""                if (F.size != 0 && Bytes.size() != F.size)""",
     """                if (Bytes.size() != F.size)"""),
    ("""                if (!F.sha256.empty() && Actual != F.sha256)""",
     """                if (Actual != F.sha256)"""),
])
print("patched")
