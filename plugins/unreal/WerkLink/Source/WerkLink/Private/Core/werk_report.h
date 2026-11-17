// werk report entries — SPEC.md 10.1.
//
// "Silence is not a refusal; an unreported skip is a bug." Every refusal in
// this adapter becomes one entry here, with a STABLE MACHINE CODE, a severity
// and the node id or path it concerns.
//
// Engine-free on purpose: this header is compiled into the UE module AND into
// the standalone MSVC gate target, so the code the gate measures is the code
// that ships. Nothing in Core/ may include an Unreal header or use FString.

#pragma once

#include <string>
#include <vector>

namespace werk
{

enum class Severity
{
    Info,
    Warn,
    Error,
};

// SPEC.md 10.1: "Every refusal is one report entry with a stable machine code".
// These are the fixed strings. Prose around them is free; the token is not.
namespace code
{
    inline constexpr const char* UnsupportedConvention   = "unsupported-convention";
    inline constexpr const char* HashMismatch            = "hash-mismatch";
    inline constexpr const char* SizeMismatch            = "size-mismatch";
    inline constexpr const char* EnvelopeInvalid         = "envelope-invalid";
    inline constexpr const char* PayloadSchemaInvalid    = "payload-schema-invalid";
    inline constexpr const char* NodeSkippedUnknownType  = "node-skipped-unknown-type";
    inline constexpr const char* NodeSkippedNotImplement = "node-skipped-not-implemented";
    inline constexpr const char* Zip64Unsupported        = "zip64-unsupported";
    inline constexpr const char* ContainerInvalid        = "container-invalid";
    // SPEC 10.1 vocabulary (release-fixes): container-scoped refusals
    inline constexpr const char* BadContainer            = "bad-container";
    inline constexpr const char* ManifestStructurallyInvalid = "manifest-structurally-invalid";
    inline constexpr const char* NodeDead                = "node-dead";
    inline constexpr const char* ManifestUnparseable     = "manifest-unparseable";
    inline constexpr const char* ManifestAbsent          = "manifest-absent";
    inline constexpr const char* ManifestInvalid         = "manifest-invalid";
    inline constexpr const char* CompressionUnsupported  = "compression-unsupported";
    inline constexpr const char* ZipEntryUnsupported     = "zip-entry-unsupported";
    inline constexpr const char* ZipEntryInvalid         = "zip-entry-invalid";
    inline constexpr const char* PrimaryFallback         = "primary-fallback";
    inline constexpr const char* VersionFallback         = "version-fallback";
    inline constexpr const char* FileMissing             = "file-missing";
    inline constexpr const char* RequiresDeadNode        = "requires-dead-node";
    inline constexpr const char* RequiresMissingNode     = "requires-missing-node";
    inline constexpr const char* ExternalReference       = "external-reference";
    inline constexpr const char* SubstitutedFallback     = "substituted-fallback";
    inline constexpr const char* SourceDataMissing       = "source-data-missing";
    inline constexpr const char* Imported                = "imported";
    inline constexpr const char* Exported                = "exported";
}

// SPEC.md 10 step 4: the four words are FIXED STRINGS, and so are the four
// matching report codes. A tool comparing them is a normal thing to write.
namespace sig
{
    inline constexpr const char* StateValid       = "signed-and-valid";
    inline constexpr const char* StateAbsent      = "absent";
    inline constexpr const char* StateInvalid     = "present-and-invalid";
    inline constexpr const char* StateUnverified  = "unverified";

    inline constexpr const char* CodeValid        = "signature-valid";
    inline constexpr const char* CodeAbsent       = "signature-absent";
    inline constexpr const char* CodeInvalid      = "signature-invalid";
    inline constexpr const char* CodeUnverified   = "signature-unverified";
}

struct ReportEntry
{
    std::string code;      // one of code:: above
    Severity    severity = Severity::Info;
    std::string subject;   // node id, or path, or "" when container-scoped
    std::string detail;    // free prose

    ReportEntry() = default;
    ReportEntry(const char* InCode, Severity InSeverity, std::string InSubject, std::string InDetail)
        : code(InCode), severity(InSeverity), subject(std::move(InSubject)), detail(std::move(InDetail))
    {
    }
};

class Report
{
public:
    void Add(const char* InCode, Severity InSeverity, std::string InSubject, std::string InDetail)
    {
        Entries.emplace_back(InCode, InSeverity, std::move(InSubject), std::move(InDetail));
    }

    void Info(const char* InCode, std::string Subject, std::string Detail)
    {
        Add(InCode, Severity::Info, std::move(Subject), std::move(Detail));
    }
    void Warn(const char* InCode, std::string Subject, std::string Detail)
    {
        Add(InCode, Severity::Warn, std::move(Subject), std::move(Detail));
    }
    void Error(const char* InCode, std::string Subject, std::string Detail)
    {
        Add(InCode, Severity::Error, std::move(Subject), std::move(Detail));
    }

    int CountOf(Severity S) const
    {
        int N = 0;
        for (const ReportEntry& E : Entries)
        {
            if (E.severity == S)
            {
                ++N;
            }
        }
        return N;
    }

    bool HasErrors() const { return CountOf(Severity::Error) > 0; }

    // SPEC.md 10.1 exit status: 0 = opened, no error entry; 1 = opened, at
    // least one error; 2 = container-scoped refusal, nothing loaded.
    int ExitStatus(bool bContainerOpened) const
    {
        if (!bContainerOpened)
        {
            return 2;
        }
        return HasErrors() ? 1 : 0;
    }

    const std::vector<ReportEntry>& All() const { return Entries; }
    void Clear() { Entries.clear(); }

private:
    std::vector<ReportEntry> Entries;
};

inline const char* SeverityName(Severity S)
{
    switch (S)
    {
    case Severity::Info:  return "info";
    case Severity::Warn:  return "warn";
    case Severity::Error: return "error";
    }
    return "info";
}

} // namespace werk
