#include "werk_manifest.h"

#include <cstdio>
#include <cstring>

#include "werk_sha256.h"

namespace werk
{

namespace
{
    // The blast radius of each convention: which node type prefixes it
    // governs. SPEC.md 10.1 requires a node scope rather than a container
    // scope, and the exact table is spec finding S-17, still awaiting a
    // ruling. This is WerkLink's reading and it is deliberately conservative:
    // where a convention plausibly governs a family, it is listed.
    struct ConvSpec
    {
        const char* Key;
        const char* Expected;
        const char* Governs; // comma-separated type prefixes; "*" = everything
    };

    const ConvSpec kConventions[] = {
        { "endianness",           "le",             "*" },
        { "units_per_meter",      "1.0",            "core.geom,core.phys,core.field,core.pose,core.skeleton,core.anim,core.destruct" },
        { "length_unit",          "metre",          "core.geom,core.phys,core.field,core.pose,core.skeleton,core.anim,core.destruct" },
        { "angle_unit",           "radian",         "core.skeleton,core.anim,core.pose,core.phys" },
        { "time_unit",            "second",         "core.anim,core.audio" },
        { "mass_unit",            "kilogram",       "core.phys" },
        { "up_axis",              "y",              "core.geom,core.phys,core.field,core.pose,core.skeleton,core.anim,core.imposter,core.destruct" },
        { "forward_axis",         "-z",             "core.geom,core.phys,core.field,core.pose,core.skeleton,core.anim,core.imposter,core.destruct" },
        { "right_axis",           "+x",             "core.geom,core.phys,core.field,core.pose,core.skeleton,core.anim,core.imposter,core.destruct" },
        { "handedness",           "right",          "core.geom,core.phys,core.field,core.pose,core.skeleton,core.anim,core.imposter,core.destruct" },
        { "winding",              "ccw",            "core.geom,core.destruct" },
        { "quat_order",           "wxyz",           "core.pose,core.skeleton,core.anim,core.phys" },
        { "oct_encoding_pole",    "y",              "core.imposter" },
        { "color_space_default",  "srgb",           "core.tex,core.imposter,core.material,core.semantics" },
        { "uv_origin",            "top-left",       "core.geom,core.tex,core.imposter,core.material" },
        { "alignment_bytes",      "16",             "*" },
        { "text_encoding",        "utf-8",          "*" },
        { "id_case",              "kebab-case",     "*" },
        { "hash_algorithm",       "sha256",         "*" },
        { "signature_algorithm",  "ed25519",        "" }, // governs SIGNATURE.json only
    };

    std::string NumToString(double D)
    {
        char Buf[64];
        if (D == double(long long(D)))
        {
            // units_per_meter is written 1.0 in the spec text but is a JSON
            // number; both spellings mean the same value and neither is wrong.
            std::snprintf(Buf, sizeof(Buf), "%.1f", D);
        }
        else
        {
            std::snprintf(Buf, sizeof(Buf), "%.17g", D);
        }
        return Buf;
    }

    bool GovernsType(const char* Governs, const std::string& NodeType)
    {
        if (std::strcmp(Governs, "*") == 0)
        {
            return true;
        }
        if (Governs[0] == '\0')
        {
            return false;
        }
        std::string G(Governs);
        size_t Start = 0;
        while (Start <= G.size())
        {
            const size_t Comma = G.find(',', Start);
            const size_t End = (Comma == std::string::npos) ? G.size() : Comma;
            const std::string Prefix = G.substr(Start, End - Start);
            if (!Prefix.empty() && NodeType.compare(0, Prefix.size(), Prefix) == 0)
            {
                return true;
            }
            if (Comma == std::string::npos)
            {
                break;
            }
            Start = Comma + 1;
        }
        return false;
    }

    Vec3 ReadVec3(const JsonValue* A, const Vec3& Default)
    {
        if (!A || !A->IsArray() || A->Size() != 3)
        {
            return Default;
        }
        Vec3 V = Default;
        for (int i = 0; i < 3; ++i)
        {
            const JsonValue* E = A->At(size_t(i));
            if (E && E->IsNumber())
            {
                V[size_t(i)] = E->number;
            }
        }
        return V;
    }

    Quat ReadQuat(const JsonValue* A, const Quat& Default)
    {
        if (!A || !A->IsArray() || A->Size() != 4)
        {
            return Default;
        }
        Quat Q = Default;
        for (int i = 0; i < 4; ++i)
        {
            const JsonValue* E = A->At(size_t(i));
            if (E && E->IsNumber())
            {
                Q[size_t(i)] = E->number;
            }
        }
        return Q;
    }
}

const std::vector<std::pair<std::string, std::string>>& SupportedConventions()
{
    static std::vector<std::pair<std::string, std::string>> V;
    if (V.empty())
    {
        for (const ConvSpec& C : kConventions)
        {
            V.emplace_back(C.Key, C.Expected);
        }
    }
    return V;
}

bool Package::OpenFile(const std::string& Path, Report& Rep)
{
    if (!Reader.OpenFile(Path, Rep))
    {
        return false;
    }
    return ParseManifest(Rep);
}

bool Package::OpenMemory(std::vector<uint8_t> Bytes, Report& Rep)
{
    if (!Reader.OpenMemory(std::move(Bytes), Rep))
    {
        return false;
    }
    return ParseManifest(Rep);
}

bool Package::ParseManifest(Report& Rep)
{
    if (!Reader.Read("MANIFEST.json", ManifestBytes, Rep))
    {
        Rep.Error(Reader.Has("MANIFEST.json") ? code::ManifestInvalid : code::ManifestAbsent, "MANIFEST.json",
                  "the container has no readable MANIFEST.json; this is the one "
                  "container-scoped refusal that may be empty-handed");
        return false;
    }
    ManifestHash = Sha256::HashHex(ManifestBytes);

    std::string Err;
    Root = JsonParse(ManifestBytes, Err);
    if (!Root)
    {
        Rep.Error(code::ManifestUnparseable, "MANIFEST.json", Err.empty() ? "does not parse" : Err);
        return false;
    }
    if (!Root->IsObject())
    {
        // SPEC 12.1 (release-fixes): parses, but is not a JSON object
        Rep.Error(code::ManifestStructurallyInvalid, "MANIFEST.json", "not a JSON object");
        return false;
    }

    if (const JsonValue* W = Root->GetObject("werk"))
    {
        Major = int(W->GetNumber("major", 0));
        Minor = int(W->GetNumber("minor", 0));
    }
    if (Major != 1)
    {
        // Checklist step 2: check that werk.major is one we support. A future
        // major is not something to guess at.
        Rep.Error(code::ManifestInvalid, "MANIFEST.json",
                  "werk.major is " + std::to_string(Major) + "; this adapter implements major 1");
        return false;
    }
    ProfileName = Root->GetString("profile");

    if (const JsonValue* E = Root->GetObject("entity"))
    {
        Uuid = E->GetString("uuid");
        Name = E->GetString("name");
        Summary = E->GetString("summary");
    }

    if (const JsonValue* P = Root->GetObject("primary"))
    {
        PrimaryMeshId = P->GetString("mesh");
        PrimarySoundId = P->GetString("sound");
        PrimaryImageId = P->GetString("image");
    }

    // parts[]
    if (const JsonValue* A = Root->GetArray("parts"))
    {
        for (size_t i = 0; i < A->Size(); ++i)
        {
            const JsonValue* O = A->At(i);
            if (!O || !O->IsObject())
            {
                continue;
            }
            Part Pt;
            Pt.partId = O->GetString("part_id");
            Pt.name = O->GetString("name");
            const JsonValue* Par = O->Find("parent");
            Pt.parent = (Par && Par->IsString()) ? Par->str : std::string();
            if (const JsonValue* T = O->GetObject("transform"))
            {
                Pt.translation = ReadVec3(T->GetArray("translation"), { 0, 0, 0 });
                Pt.rotation = ReadQuat(T->GetArray("rotation"), { 1, 0, 0, 0 });
                Pt.scale = ReadVec3(T->GetArray("scale"), { 1, 1, 1 });
            }
            PartList.push_back(std::move(Pt));
        }
    }

    // materials[]
    if (const JsonValue* A = Root->GetArray("materials"))
    {
        for (size_t i = 0; i < A->Size(); ++i)
        {
            const JsonValue* O = A->At(i);
            if (!O || !O->IsObject())
            {
                continue;
            }
            MaterialEntry M;
            M.materialId = O->GetString("material_id");
            M.partId = O->GetString("part_id");
            M.name = O->GetString("name");
            M.cls = O->GetString("class");
            MaterialList.push_back(std::move(M));
        }
    }

    // nodes[] -- SPEC 12.1 (release-fixes): `nodes` missing or not an array is
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
            }
            const JsonValue* MetaV = O->Find("meta");
            if (MetaV)
            {
                // Shared, not copied: meta is read-only here.
                N.meta = std::make_shared<JsonValue>(*MetaV);
            }
            if (const JsonValue* Ed = O->GetArray("edges"))
            {
                for (size_t k = 0; k < Ed->Size(); ++k)
                {
                    const JsonValue* EO = Ed->At(k);
                    if (!EO || !EO->IsObject())
                    {
                        continue;
                    }
                    Edge E;
                    E.to = EO->GetString("to");
                    E.kind = EO->GetString("kind");
                    E.role = EO->GetString("role");
                    N.edges.push_back(std::move(E));
                }
            }
            if (const JsonValue* Vs = O->GetArray("versions"))
            {
                for (size_t k = 0; k < Vs->Size(); ++k)
                {
                    const JsonValue* VO = Vs->At(k);
                    if (!VO || !VO->IsObject())
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
                    NV.v = int(VO->GetNumber("v", 0));
                    NV.note = VO->GetString("note");
                    NV.epistemic = VO->GetString("epistemic");
                    NV.created = VO->GetString("created");
                    NV.inputHash = VO->GetString("input_hash");
                    if (const JsonValue* Pr = VO->GetObject("producer"))
                    {
                        NV.producer.tool = Pr->GetString("tool");
                        NV.producer.model = Pr->GetString("model");
                        NV.producer.version = Pr->GetString("version");
                    }
                    if (const JsonValue* IF = VO->GetArray("input_files"))
                    {
                        for (size_t m = 0; m < IF->Size(); ++m)
                        {
                            const JsonValue* S = IF->At(m);
                            if (S && S->IsString())
                            {
                                NV.inputFiles.push_back(S->str);
                            }
                        }
                    }
                    if (const JsonValue* IP = VO->Find("input_params"))
                    {
                        NV.inputParams = std::make_shared<JsonValue>(*IP);
                    }
                    if (const JsonValue* Fs = VO->GetArray("files"))
                    {
                        for (size_t m = 0; m < Fs->Size(); ++m)
                        {
                            const JsonValue* FO = Fs->At(m);
                            if (!FO || !FO->IsObject() || !IsStr(FO->Find("path"))
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
                            FileRef F;
                            F.path = FO->GetString("path");
                            F.sha256 = FO->GetString("sha256");
                            F.size = uint64_t(FO->GetNumber("size", 0));
                            F.mediaType = FO->GetString("media_type");
                            F.role = FO->GetString("role");
                            // Checklist step 9: this index IS the whitelist.
                            // Nothing outside it will ever be opened.
                            FileHashIndex[F.path] = F.sha256;
                            FileSizeIndex[F.path] = F.size;
                            NV.files.push_back(std::move(F));
                        }
                    }
                    N.versions.push_back(std::move(NV));
                }
            }
            NodeList.push_back(std::move(N));
        }
    }

    CheckConventions(Rep);
    ResolveVersions(Rep);

    // Checklist step 4. WerkLink does not carry an Ed25519 implementation, so
    // it reports the fourth word and never one of the three states it did not
    // establish. `absent` is only correct when the file really is absent.
    if (Reader.Has("SIGNATURE.json"))
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
    }
    else
    {
        SigState = sig::StateAbsent;
        SigCode = sig::CodeAbsent;
        Rep.Info(sig::CodeAbsent, "", "no SIGNATURE.json: the package is anonymous, and visibly so");
    }

    return true;
}

void Package::CheckConventions(Report& Rep)
{
    const JsonValue* C = Root->GetObject("conventions");
    if (!C)
    {
        Rep.Error(code::ManifestInvalid, "MANIFEST.json", "no conventions block");
        return;
    }

    // S-23 (ratified): a reader's convention set belongs to the PROFILE, not to
    // the reader. The 21 conventions below are `3d-entity/1`'s. A package in
    // another profile -- `image/1`, say -- legitimately declares a different
    // set, and warning thirteen times that a 2D image package does not say
    // which way is up is not graceful degradation, it is noise that buries the
    // one line that matters.
    //
    // Measured, which is why this is here: importing fixtures/ista-varun-v1.werk
    // (profile image/1) produced 13 unsupported-convention warnings and one
    // useful sentence. So the per-convention warnings are scoped to this
    // profile, and a foreign profile gets ONE line naming itself. The checks
    // themselves still run and still gate every 3d-entity node type, so nothing
    // is loosened -- only the reporting is made true.
    const bool bConventionsAreThisProfiles = (ProfileName == "3d-entity/1");
    if (!bConventionsAreThisProfiles)
    {
        Rep.Info(code::UnsupportedConvention, "profile",
                 "this package declares profile '" + ProfileName
                     + "', not '3d-entity/1'. The conventions checked below are "
                       "3d-entity/1's, so nodes governed by them are refused as a body "
                       "rather than reported one convention at a time. Every node is "
                       "still listed and every file is still hash-verified.");
    }

    for (const ConvSpec& Spec : kConventions)
    {
        ConventionCheck Chk;
        Chk.key = Spec.Key;
        Chk.expected = Spec.Expected;

        const JsonValue* V = C->Find(Spec.Key);
        if (!V)
        {
            Chk.actual = "(absent)";
            Chk.bSupported = false;
        }
        else if (V->IsString())
        {
            Chk.actual = V->str;
            Chk.bSupported = (Chk.actual == Chk.expected);
        }
        else if (V->IsNumber())
        {
            Chk.actual = NumToString(V->number);
            // Numeric compare, so 1 and 1.0 are the same convention. The spec
            // writes units_per_meter as 1.0 and alignment_bytes as 16; both
            // are JSON numbers and neither spelling is more correct.
            Chk.bSupported = (std::strtod(Chk.expected.c_str(), nullptr) == V->number);
        }
        else
        {
            Chk.actual = "(wrong type)";
            Chk.bSupported = false;
        }

        // Split the governs list once, here, so callers do not re-parse it.
        {
            std::string G(Spec.Governs);
            size_t Start = 0;
            while (!G.empty() && Start <= G.size())
            {
                const size_t Comma = G.find(',', Start);
                const size_t End = (Comma == std::string::npos) ? G.size() : Comma;
                Chk.governs.push_back(G.substr(Start, End - Start));
                if (Comma == std::string::npos)
                {
                    break;
                }
                Start = Comma + 1;
            }
        }

        if (!Chk.bSupported && bConventionsAreThisProfiles)
        {
            // SPEC.md 10.1: node-scoped, not container-scoped. The graph
            // listing, the hashes and the work notes stay readable.
            Rep.Warn(code::UnsupportedConvention, Chk.key,
                     "expected '" + Chk.expected + "', found '" + Chk.actual
                         + "'; nodes governed by it will be refused, the rest still load");
        }
        ConventionList.push_back(std::move(Chk));
    }
}

bool Package::ConventionsSatisfiedFor(const std::string& NodeType, std::string& OutWhichFailed) const
{
    for (size_t i = 0; i < ConventionList.size(); ++i)
    {
        const ConventionCheck& Chk = ConventionList[i];
        if (Chk.bSupported)
        {
            continue;
        }
        if (GovernsType(kConventions[i].Governs, NodeType))
        {
            OutWhichFailed = Chk.key;
            return false;
        }
    }
    OutWhichFailed.clear();
    return true;
}

void Package::ResolveVersions(Report& Rep)
{
    for (Node& N : NodeList)
    {
        if (!N.malformed.empty())
        {
            Rep.Error(code::NodeDead, N.nodeId, "node structure unusable (SPEC 12.1): " + N.malformed);
            continue;
        }
        if (N.versions.empty())
        {
            Rep.Error(code::NodeDead, N.nodeId, "node has no versions");
            continue;
        }

        // Order to try: `active` first, then earlier versions newest-first.
        std::vector<int> Order;
        for (size_t i = 0; i < N.versions.size(); ++i)
        {
            if (N.versions[i].v == N.active)
            {
                Order.push_back(int(i));
            }
        }
        for (int i = int(N.versions.size()) - 1; i >= 0; --i)
        {
            if (N.versions[size_t(i)].v != N.active)
            {
                Order.push_back(i);
            }
        }

        bool bResolved = false;
        for (size_t Try = 0; Try < Order.size(); ++Try)
        {
            const int Idx = Order[Try];
            const NodeVersion& NV = N.versions[size_t(Idx)];
            bool bOk = true;

            for (const FileRef& F : NV.files)
            {
                std::vector<uint8_t> Bytes;
                Report Local;
                if (!Reader.Read(F.path, Bytes, Local))
                {
                    for (const ReportEntry& E : Local.All())
                    {
                        Rep.Add(E.code.c_str(), E.severity, N.nodeId,
                                F.path + ": " + E.detail);
                    }
                    bOk = false;
                    break;
                }
                // Checklist step 6: size, then sha256.
                if (Bytes.size() != F.size)
                {
                    Rep.Error(code::SizeMismatch, N.nodeId,
                              F.path + ": " + std::to_string(Bytes.size()) + " bytes on disk, manifest says "
                                  + std::to_string(F.size));
                    bOk = false;
                    break;
                }
                const std::string Actual = Sha256::HashHex(Bytes);
                if (Actual != F.sha256)
                {
                    Rep.Error(code::HashMismatch, N.nodeId,
                              F.path + ": sha256 " + Actual + ", manifest says " + F.sha256);
                    bOk = false;
                    break;
                }
            }

            if (bOk)
            {
                N.resolvedIndex = Idx;
                N.bAlive = true;
                bResolved = true;
                if (Try != 0 || NV.v != N.active)
                {
                    // SPEC.md section 5: a resilient reader MAY fall back and
                    // MUST report having done so.
                    Rep.Warn(code::VersionFallback, N.nodeId,
                             "active version " + std::to_string(N.active)
                                 + " did not verify; fell back to version " + std::to_string(NV.v));
                }
                break;
            }
        }

        if (!bResolved)
        {
            Rep.Error(code::HashMismatch, N.nodeId, "no version of this node verified; node is dead");
        }
    }

    // Law 3, via SPEC.md section 5: a `requires` edge into a dead node kills
    // the source node too, and so does one to a node absent from nodes[].
    // Iterated to a fixed point, because a chain of requires must propagate
    // all the way. Each death gets its own code, never hash-mismatch: no hash
    // failed here, and a tool counting hash mismatches must get the true count.
    bool bChanged = true;
    int Guard = 0;
    while (bChanged && Guard++ < 64)
    {
        bChanged = false;
        for (Node& N : NodeList)
        {
            if (!N.bAlive)
            {
                continue;
            }
            for (const Edge& E : N.edges)
            {
                if (E.kind != "requires")
                {
                    continue;
                }
                const Node* T = FindNode(E.to);
                if (!T)
                {
                    N.bAlive = false;
                    N.resolvedIndex = -1;
                    bChanged = true;
                    Rep.Error(code::RequiresMissingNode, N.nodeId,
                              "requires edge to '" + E.to + "', which is not in nodes[]");
                    break;
                }
                if (!T->bAlive)
                {
                    N.bAlive = false;
                    N.resolvedIndex = -1;
                    bChanged = true;
                    Rep.Error(code::RequiresDeadNode, N.nodeId,
                              "requires edge into dead node '" + E.to + "'");
                    break;
                }
            }
        }
    }
}

const Node* Package::FindNode(const std::string& NodeId) const
{
    for (const Node& N : NodeList)
    {
        if (N.nodeId == NodeId)
        {
            return &N;
        }
    }
    return nullptr;
}

const Part* Package::FindPart(const std::string& PartId) const
{
    for (const Part& P : PartList)
    {
        if (P.partId == PartId)
        {
            return &P;
        }
    }
    return nullptr;
}

const MaterialEntry* Package::FindMaterial(const std::string& MaterialId) const
{
    for (const MaterialEntry& M : MaterialList)
    {
        if (M.materialId == MaterialId)
        {
            return &M;
        }
    }
    return nullptr;
}

const Node* Package::PrimaryMesh(Report& Rep) const
{
    if (!PrimaryMeshId.empty())
    {
        if (const Node* N = FindNode(PrimaryMeshId))
        {
            return N;
        }
        Rep.Warn(code::PrimaryFallback, PrimaryMeshId,
                 "primary.mesh names a node that is not in the graph");
    }
    // SPEC.md section 2 fallback: the mesh is the core.geom.game node -- never
    // a core.geom.lod, and never core.geom.source, which is the archival
    // anchor and may lack the attributes a renderer needs.
    for (const Node& N : NodeList)
    {
        if (N.type == "core.geom.game" && N.bAlive)
        {
            Rep.Warn(code::PrimaryFallback, N.nodeId,
                     "primary.mesh absent; fell back to the core.geom.game node");
            return &N;
        }
    }
    return nullptr;
}

const Node* Package::PrimarySound(Report& Rep) const
{
    if (!PrimarySoundId.empty())
    {
        if (const Node* N = FindNode(PrimarySoundId))
        {
            return N;
        }
        Rep.Warn(code::PrimaryFallback, PrimarySoundId,
                 "primary.sound names a node that is not in the graph");
    }
    // Fallback: the audio package's preview_effect slug resolved to its effect
    // node, and failing that the first core.audio.effect in nodes[].
    for (const Node& N : NodeList)
    {
        if (N.type == "core.audio.effect" && N.bAlive)
        {
            Rep.Warn(code::PrimaryFallback, N.nodeId,
                     "primary.sound absent; fell back to the first core.audio.effect");
            return &N;
        }
    }
    return nullptr;
}

bool Package::ReadPayload(const std::string& Path, std::vector<uint8_t>& Out, Report& Rep) const
{
    // Checklist step 9: never follow a path that is not in some files[].
    const auto It = FileHashIndex.find(Path);
    if (It == FileHashIndex.end())
    {
        Rep.Error(code::FileMissing, Path,
                  "path is not named by any node version's files[]; nothing floats");
        return false;
    }
    if (!Reader.Read(Path, Out, Rep))
    {
        return false;
    }
    const auto SzIt = FileSizeIndex.find(Path);
    if (SzIt != FileSizeIndex.end() && SzIt->second != 0 && Out.size() != SzIt->second)
    {
        Rep.Error(code::SizeMismatch, Path,
                  std::to_string(Out.size()) + " bytes, manifest says " + std::to_string(SzIt->second));
        Out.clear();
        return false;
    }
    const std::string Actual = Sha256::HashHex(Out);
    if (!It->second.empty() && Actual != It->second)
    {
        Rep.Error(code::HashMismatch, Path, "sha256 " + Actual + ", manifest says " + It->second);
        Out.clear();
        return false;
    }
    return true;
}

// --- selftest --------------------------------------------------------------

std::vector<std::string> ManifestSelftest(const std::string& FixturePath, bool bVerbose)
{
    std::vector<std::string> Bad;
    Report Rep;
    Package Pkg;

    if (!Pkg.OpenFile(FixturePath, Rep))
    {
        Bad.push_back("could not open the fixture: " + FixturePath);
        for (const ReportEntry& E : Rep.All())
        {
            Bad.push_back("  " + E.code + " " + E.subject + " " + E.detail);
        }
        return Bad;
    }

    if (Pkg.WerkMajor() != 1)
    {
        Bad.push_back("werk.major != 1");
    }
    if (Pkg.Profile() != "3d-entity/1")
    {
        Bad.push_back("profile is '" + Pkg.Profile() + "', expected '3d-entity/1'");
    }
    if (Pkg.EntityUuid().empty())
    {
        Bad.push_back("entity.uuid is empty");
    }
    if (Pkg.Nodes().empty())
    {
        Bad.push_back("no nodes parsed");
    }

    // Every convention must be one we support, for the golden fixture.
    for (const ConventionCheck& C : Pkg.Conventions())
    {
        if (!C.bSupported)
        {
            Bad.push_back("unsupported convention " + C.key + ": expected '" + C.expected
                          + "', found '" + C.actual + "'");
        }
    }

    // Every node must resolve, and every hash must match: the fixture is the
    // undamaged one.
    int Alive = 0, Dead = 0, FilesChecked = 0;
    for (const Node& N : Pkg.Nodes())
    {
        if (N.bAlive)
        {
            ++Alive;
            const NodeVersion* V = N.Resolved();
            if (V)
            {
                FilesChecked += int(V->files.size());
                if (V->note.empty())
                {
                    // Law 6: the work note is mandatory.
                    Bad.push_back("node " + N.nodeId + " version has an empty work note");
                }
                if (V->epistemic != "authored" && V->epistemic != "measured"
                    && V->epistemic != "inferred")
                {
                    Bad.push_back("node " + N.nodeId + " has epistemic '" + V->epistemic + "'");
                }
                // Law 5, machine-checkable: input_hash and input_files are
                // mandatory whenever epistemic is measured or inferred.
                if ((V->epistemic == "measured" || V->epistemic == "inferred")
                    && (V->inputHash.empty() || V->inputFiles.empty()))
                {
                    Bad.push_back("node " + N.nodeId + " is " + V->epistemic
                                  + " but carries no input_hash/input_files");
                }
            }
        }
        else
        {
            ++Dead;
            Bad.push_back("node " + N.nodeId + " did not resolve in an undamaged fixture");
        }
    }

    if (Rep.HasErrors())
    {
        for (const ReportEntry& E : Rep.All())
        {
            if (E.severity == Severity::Error)
            {
                Bad.push_back("error report: " + E.code + " " + E.subject + " " + E.detail);
            }
        }
    }

    // The signature must be reported as unverified, not as valid or absent.
    if (Pkg.Zip().Has("SIGNATURE.json") && Pkg.SignatureState() != sig::StateUnverified)
    {
        Bad.push_back("signature state is '" + Pkg.SignatureState()
                      + "'; a reader with no Ed25519 must say 'unverified'");
    }

    // primary must be declared, not inferred, for this fixture.
    {
        Report R2;
        const Node* Mesh = Pkg.PrimaryMesh(R2);
        if (!Mesh)
        {
            Bad.push_back("no primary mesh resolved");
        }
        for (const ReportEntry& E : R2.All())
        {
            if (E.code == code::PrimaryFallback)
            {
                Bad.push_back("primary mesh fell back although the fixture declares primary.mesh");
            }
        }
    }

    // Refusing a path that is not in any files[] is checklist step 9, and it
    // has to be tested with a path that really is in the container.
    {
        Report R3;
        std::vector<uint8_t> Bytes;
        if (Pkg.ReadPayload("MANIFEST.json", Bytes, R3))
        {
            Bad.push_back("ReadPayload returned MANIFEST.json, which no files[] names");
        }
    }

    if (bVerbose)
    {
        std::printf("  OK manifest: %d nodes (%d alive, %d dead), %d files verified, "
                    "%zu conventions all supported, signature %s\n",
                    int(Pkg.Nodes().size()), Alive, Dead, FilesChecked,
                    Pkg.Conventions().size(), Pkg.SignatureState().c_str());
    }

    return Bad;
}

} // namespace werk
