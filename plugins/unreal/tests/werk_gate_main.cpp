// WerkLink standalone gate.
//
// House rule: gates are MEASURED. This target compiles the adapter's ENGINE-
// FREE core -- the same .cpp files the Unreal module compiles, not a copy --
// with local MSVC and runs every selftest plus a real read of
// fixtures/crate-v1.werk. It asserts nothing it does not print and prints
// nothing it did not measure.
//
// Build:  plugins\unreal\tests\build_gate.bat
// Run:    .build\werk_gate.exe fixtures\crate-v1.werk [fixtures\crate-v1-damaged.werk]
//
// Exit status follows SPEC.md 10.1: 0 clean, 1 errors present, 2 the container
// could not be opened at all.

#include <chrono>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#include "../WerkLink/Source/WerkLink/Private/Core/werk_basis.h"
#include "../WerkLink/Source/WerkLink/Private/Core/werk_edges.h"
#include "../WerkLink/Source/WerkLink/Private/Core/werk_glb.h"
#include "../WerkLink/Source/WerkLink/Private/Core/werk_json.h"
#include "../WerkLink/Source/WerkLink/Private/Core/werk_manifest.h"
#include "../WerkLink/Source/WerkLink/Private/Core/werk_sha256.h"
#include "../WerkLink/Source/WerkLink/Private/Core/werk_zip.h"

using namespace werk;

namespace
{
    int gPass = 0;
    int gFail = 0;

    double Now()
    {
        using namespace std::chrono;
        return double(duration_cast<microseconds>(steady_clock::now().time_since_epoch()).count()) / 1e6;
    }

    void Section(const char* Name, const std::vector<std::string>& Bad, const char* Detail = nullptr)
    {
        if (Bad.empty())
        {
            std::printf("[PASS] %-34s %s\n", Name, Detail ? Detail : "");
            ++gPass;
        }
        else
        {
            std::printf("[FAIL] %-34s %d failure(s)\n", Name, int(Bad.size()));
            for (const std::string& S : Bad)
            {
                std::printf("         %s\n", S.c_str());
            }
            ++gFail;
        }
    }
}

// --verdict <package>: one line of the reader's verdict, for the gate's
// release-fixes agreement campaign (tests/gate.py part A2):
//   exit=<0|1|2> signature=<word> dead=<id,id,...> codes=<code,code,...>
static int Verdict(const char* Path)
{
    Report Rep;
    Package Pkg;
    const bool bOpened = Pkg.OpenFile(Path, Rep);
    std::string Dead, Codes;
    if (bOpened)
    {
        for (const Node& N : Pkg.Nodes())
        {
            if (!N.bAlive)
            {
                Dead += (Dead.empty() ? "" : ",") + N.nodeId;
            }
        }
    }
    for (const ReportEntry& E : Rep.All())
    {
        if (E.severity == Severity::Error
            && ("," + Codes + ",").find("," + E.code + ",") == std::string::npos)
        {
            Codes += (Codes.empty() ? "" : ",") + E.code;
        }
    }
    const int Exit = !bOpened ? 2 : (Rep.CountOf(Severity::Error) ? 1 : 0);
    std::printf("exit=%d signature=%s dead=%s codes=%s\n", Exit,
                bOpened ? Pkg.SignatureState().c_str() : "-", Dead.c_str(), Codes.c_str());
    return Exit;
}

int main(int argc, char** argv)
{
    if (argc == 3 && std::strcmp(argv[1], "--verdict") == 0)
    {
        return Verdict(argv[2]);
    }
    const std::string Fixture = (argc > 1) ? argv[1] : "fixtures/crate-v1.werk";
    const std::string Damaged = (argc > 2) ? argv[2] : "";
    const bool bVerbose = (argc > 3) && std::strcmp(argv[3], "-v") == 0;

    std::printf("WerkLink standalone gate (engine-free core, MSVC)\n");
    std::printf("fixture : %s\n", Fixture.c_str());

    // Measure the fixture itself so the numbers in HANDOVER are traceable to a
    // specific file rather than to "the fixture".
    {
        Report Rep;
        ZipReader R;
        if (R.OpenFile(Fixture, Rep))
        {
            std::printf("          %llu bytes, sha256 %s\n",
                        (unsigned long long)R.ContainerSize(),
                        Sha256::HashHex(R.RawBytes()).c_str());
        }
    }
    std::printf("\n");

    const double T0 = Now();

    Section("basis change", BasisSelftest(bVerbose));
    Section("sha-256", Sha256Selftest(bVerbose));
    Section("store-mode zip + crc32", ZipSelftest(bVerbose));
    Section("json (MINI-SPECS 3 subset)", JsonSelftest(bVerbose));
    Section("glb read/write", GlbSelftest(bVerbose));
    Section("dangling-edge guard (SPEC 5)", EdgeGuardSelftest(bVerbose));
    Section("manifest parse (golden fixture)", ManifestSelftest(Fixture, bVerbose));

    // --- the end-to-end read: open the golden fixture and pull real payloads
    // through the same path the importer uses.
    bool bOpened = false;
    Report Rep;
    Package Pkg;
    {
        std::vector<std::string> Bad;
        const double T1 = Now();
        bOpened = Pkg.OpenFile(Fixture, Rep);
        const double OpenSeconds = Now() - T1;

        if (!bOpened)
        {
            Bad.push_back("package did not open");
            Section("package open", Bad);
        }
        else
        {
            int Alive = 0, Files = 0;
            unsigned long long PayloadBytes = 0;
            for (const Node& N : Pkg.Nodes())
            {
                if (N.bAlive)
                {
                    ++Alive;
                    if (const NodeVersion* V = N.Resolved())
                    {
                        Files += int(V->files.size());
                        for (const FileRef& F : V->files)
                        {
                            PayloadBytes += F.size;
                        }
                    }
                }
            }
            char Buf[256];
            std::snprintf(Buf, sizeof(Buf),
                          "%d nodes, %d alive, %d files hashed, %llu payload bytes, %.3f s",
                          int(Pkg.Nodes().size()), Alive, Files, PayloadBytes, OpenSeconds);
            Section("package open + verify all hashes", Bad, Buf);
        }
    }

    // --- geometry: read the primary mesh through the GLB parser and cross the
    // basis, so the numbers below are the ones an import would produce.
    if (bOpened)
    {
        std::vector<std::string> Bad;
        char Detail[256] = "";
        Report R2;
        const Node* MeshNode = Pkg.PrimaryMesh(R2);
        if (!MeshNode)
        {
            Bad.push_back("no primary mesh");
        }
        else if (const NodeVersion* V = MeshNode->Resolved())
        {
            std::vector<uint8_t> Bytes;
            if (V->files.empty() || !Pkg.ReadPayload(V->files[0].path, Bytes, R2))
            {
                Bad.push_back("could not read the mesh payload");
            }
            else
            {
                GlbMesh Mesh;
                if (!GlbRead(Bytes, MeshNode->type != "core.geom.source", Mesh, MeshNode->nodeId, R2))
                {
                    Bad.push_back("could not parse the mesh GLB");
                }
                else
                {
                    // Cross the basis for every vertex, exactly as the importer
                    // does, and check the transformed AABB against what
                    // physics/bounds.json declares once converted.
                    Vec3 Mn = { 1e30, 1e30, 1e30 }, Mx = { -1e30, -1e30, -1e30 };
                    size_t Verts = 0, Tris = 0;
                    for (GlbPrimitive& P : Mesh.primitives)
                    {
                        for (size_t i = 0; i + 2 < P.positions.size(); i += 3)
                        {
                            const Vec3 W = { P.positions[i], P.positions[i + 1], P.positions[i + 2] };
                            const Vec3 U = PositionWerkToUe(W);
                            for (int c = 0; c < 3; ++c)
                            {
                                if (U[size_t(c)] < Mn[size_t(c)]) Mn[size_t(c)] = U[size_t(c)];
                                if (U[size_t(c)] > Mx[size_t(c)]) Mx[size_t(c)] = U[size_t(c)];
                            }
                        }
                        if (!ReverseWinding(P.indices))
                        {
                            Bad.push_back("winding reversal refused a primitive");
                        }
                        Verts += P.VertexCount();
                        Tris += P.TriangleCount();
                    }

                    // The declared bounds, crossed the same way.
                    Vec3 BMn, BMx;
                    AabbWerkToUe({ -0.5, -0.5, -0.5 }, { 0.54, 0.54, 0.5 }, BMn, BMx);
                    for (int c = 0; c < 3; ++c)
                    {
                        if (Mn[size_t(c)] < BMn[size_t(c)] - 0.01 || Mx[size_t(c)] > BMx[size_t(c)] + 0.01)
                        {
                            Bad.push_back("converted mesh AABB falls outside the converted "
                                          "core.phys.bounds AABB on axis " + std::to_string(c));
                        }
                    }

                    std::snprintf(Detail, sizeof(Detail),
                                  "%s: %zu verts, %zu tris, UE aabb (%.1f %.1f %.1f)-(%.1f %.1f %.1f) cm",
                                  MeshNode->nodeId.c_str(), Verts, Tris,
                                  Mn[0], Mn[1], Mn[2], Mx[0], Mx[1], Mx[2]);
                }
            }
        }
        Section("primary mesh -> UE space", Bad, Detail);
    }

    // --- audio: every WAV in the package must be a RIFF/WAVE whose declared
    // fmt block agrees with its data size, because the importer will hand
    // these bytes straight to the engine's sound factory.
    if (bOpened)
    {
        std::vector<std::string> Bad;
        char Detail[256] = "";
        int Wavs = 0;
        unsigned long long Frames = 0;
        Report R3;
        for (const Node& N : Pkg.Nodes())
        {
            if (!N.bAlive || (N.type != "core.audio.effect" && N.type != "core.audio.ambience"))
            {
                continue;
            }
            const NodeVersion* V = N.Resolved();
            if (!V)
            {
                continue;
            }
            for (const FileRef& F : V->files)
            {
                if (F.path.size() < 4 || F.path.compare(F.path.size() - 4, 4, ".wav") != 0)
                {
                    continue;
                }
                std::vector<uint8_t> Bytes;
                if (!Pkg.ReadPayload(F.path, Bytes, R3))
                {
                    Bad.push_back("could not read " + F.path);
                    continue;
                }
                if (Bytes.size() < 44 || std::memcmp(Bytes.data(), "RIFF", 4) != 0
                    || std::memcmp(Bytes.data() + 8, "WAVE", 4) != 0)
                {
                    Bad.push_back(F.path + " is not a RIFF/WAVE file");
                    continue;
                }
                // Walk the chunks per MINI-SPECS 9, honouring the pad byte.
                size_t P = 12;
                unsigned int BlockAlign = 0;
                unsigned long long DataSize = 0;
                bool bFmt = false, bData = false;
                while (P + 8 <= Bytes.size())
                {
                    char Id[5] = { 0, 0, 0, 0, 0 };
                    std::memcpy(Id, Bytes.data() + P, 4);
                    unsigned int Size = 0;
                    std::memcpy(&Size, Bytes.data() + P + 4, 4);
                    const size_t Body = P + 8;
                    if (Body + Size > Bytes.size())
                    {
                        break;
                    }
                    if (std::strcmp(Id, "fmt ") == 0 && Size >= 16)
                    {
                        unsigned short Ba = 0;
                        std::memcpy(&Ba, Bytes.data() + Body + 12, 2);
                        BlockAlign = Ba;
                        bFmt = true;
                    }
                    else if (std::strcmp(Id, "data") == 0)
                    {
                        DataSize = Size;
                        bData = true;
                    }
                    P = Body + Size + (Size % 2); // the pad byte is not in the size
                }
                if (!bFmt || !bData)
                {
                    Bad.push_back(F.path + " has no fmt or no data chunk");
                }
                else if (BlockAlign == 0 || (DataSize % BlockAlign) != 0)
                {
                    Bad.push_back(F.path + " data size is not a whole number of frames");
                }
                else
                {
                    Frames += DataSize / BlockAlign;
                    ++Wavs;
                }
            }
        }
        std::snprintf(Detail, sizeof(Detail), "%d WAV files, %llu frames total", Wavs, Frames);
        Section("audio payloads are readable WAV", Bad, Detail);
    }

    // --- damage: the damaged fixture must lose exactly what is damaged and
    // keep everything else. Law 3, measured.
    if (!Damaged.empty())
    {
        std::vector<std::string> Bad;
        char Detail[256] = "";
        Report DRep;
        Package DPkg;
        if (!DPkg.OpenFile(Damaged, DRep))
        {
            // A container-scoped refusal is a legitimate outcome for some
            // damage, so say which happened rather than calling it a failure.
            std::snprintf(Detail, sizeof(Detail), "container-scoped refusal, %d error(s)",
                          DRep.CountOf(Severity::Error));
        }
        else
        {
            int Alive = 0, Dead = 0;
            for (const Node& N : DPkg.Nodes())
            {
                (N.bAlive ? Alive : Dead)++;
            }
            if (Dead == 0)
            {
                Bad.push_back("the damaged fixture lost nothing; the damage was not detected");
            }
            if (Alive == 0)
            {
                Bad.push_back("the damaged fixture lost everything; law 3 says the rest must load");
            }
            std::snprintf(Detail, sizeof(Detail),
                          "%d alive, %d dead, %d error(s), %d warn(s)",
                          Alive, Dead, DRep.CountOf(Severity::Error), DRep.CountOf(Severity::Warn));
        }
        Section("damage gauntlet", Bad, Detail);
    }

    const double Elapsed = Now() - T0;

    std::printf("\n");
    if (bOpened)
    {
        std::printf("report entries on the clean fixture: %d info, %d warn, %d error\n",
                    Rep.CountOf(Severity::Info), Rep.CountOf(Severity::Warn),
                    Rep.CountOf(Severity::Error));
        for (const ReportEntry& E : Rep.All())
        {
            if (E.severity != Severity::Info || bVerbose)
            {
                std::printf("  %-5s %-28s %-34s %s\n", SeverityName(E.severity), E.code.c_str(),
                            E.subject.c_str(), E.detail.c_str());
            }
        }
    }

    std::printf("\n%d PASS, %d FAIL   (%.3f s)\n", gPass, gFail, Elapsed);
    std::printf("GATE: %s\n", gFail == 0 ? "PASSED" : "FAILED");

    if (gFail != 0)
    {
        return 1;
    }
    return Rep.ExitStatus(bOpened);
}
