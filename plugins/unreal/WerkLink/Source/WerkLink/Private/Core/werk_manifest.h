// MANIFEST.json, modelled -- SPEC.md section 2 -- plus the package open path
// of the section 10 reader checklist.
//
// This is engine-free so the standalone gate can measure it. The UE importer
// consumes this model; it never re-parses the manifest itself.
//
// The checklist steps implemented here, in order:
//   1  open the container (werk_zip)
//   2  read MANIFEST.json and check structurally what we use, and that
//      werk.major is one we support. We do NOT carry a JSON Schema validator,
//      so we declare `read-manifest` and not a validation we did not do.
//   3  check every value in `conventions` against what we support; refuse,
//      do not guess -- node-scoped, per section 10.1
//   4  report the signature state. WerkLink does not implement Ed25519, so it
//      reports the fourth word, `unverified`, and never `absent` for a file
//      that is present or `signed-and-valid` for a signature it never checked
//   5  walk nodes[], taking `active` or the newest valid earlier version, and
//      reporting when it fell back
//   6  per file: check size, check sha256; mismatch marks the node dead and
//      the walk continues
//   9  never follow a path that is not in some files[]

#pragma once

#include <cstdint>
#include <map>
#include <string>
#include <vector>

#include "werk_basis.h"
#include "werk_json.h"
#include "werk_report.h"
#include "werk_zip.h"

namespace werk
{

struct FileRef
{
    std::string path;
    std::string sha256;
    uint64_t    size = 0;
    std::string mediaType;
    std::string role;
};

struct Producer
{
    std::string tool;
    std::string model;
    std::string version;
};

struct NodeVersion
{
    int                     v = 1;
    std::vector<FileRef>    files;
    std::string             note;       // law 6: mandatory
    Producer                producer;
    std::string             epistemic;  // authored | measured | inferred
    std::string             created;
    std::string             inputHash;
    std::vector<std::string> inputFiles;
    JsonPtr                 inputParams;
};

struct Edge
{
    std::string to;
    std::string kind; // requires | enhances
    std::string role;
};

struct Node
{
    std::string              nodeId;
    std::string              type;
    std::string              partId;
    std::string              materialId;
    std::vector<NodeVersion> versions;
    int                      active = 1;
    std::vector<Edge>        edges;
    JsonPtr                  meta;

    // Filled by Package::Open.
    // SPEC 12.1 (release-fixes): a node whose own structure is unusable is dead
    // under its id, with this reason; empty when the node is well-formed.
    std::string malformed;

    int  resolvedIndex = -1;  // index into versions[], -1 when nothing resolved
    bool bAlive = false;

    const NodeVersion* Resolved() const
    {
        return (resolvedIndex >= 0 && size_t(resolvedIndex) < versions.size())
                   ? &versions[size_t(resolvedIndex)]
                   : nullptr;
    }
};

struct Part
{
    std::string partId;
    std::string name;
    std::string parent;      // empty when null
    Vec3        translation = { 0, 0, 0 };
    Quat        rotation    = { 1, 0, 0, 0 }; // werk wxyz
    Vec3        scale       = { 1, 1, 1 };
};

struct MaterialEntry
{
    std::string materialId;
    std::string partId;
    std::string name;
    std::string cls;
};

// The 21 pinned conventions of SPEC.md section 2, and which node types each
// one governs. SPEC.md section 10.1 makes an unsupported convention
// NODE-scoped rather than container-scoped, so a reader that cannot do
// quaternions still lists the graph and still verifies every hash. The exact
// convention -> node-type table is spec finding S-17 and is still awaiting
// Gregor's ruling; the mapping below is this adapter's reading of it and is
// marked as such wherever it is used.
struct ConventionCheck
{
    std::string key;
    std::string expected;
    std::string actual;
    bool        bSupported = false;
    // Node type prefixes this convention governs. Empty means "the whole
    // package", which is only used for the ones that govern text and ids.
    std::vector<std::string> governs;
};

class Package
{
public:
    // Opens a .werk zip. Returns false only on a CONTAINER-scoped refusal
    // (SPEC.md 10.1): not a zip, no EOCD, zip64 in a zip32-only reader, or
    // MANIFEST.json missing or unparseable. Everything else degrades to a
    // node-scoped or value-scoped report and still returns true.
    bool OpenFile(const std::string& Path, Report& Rep);
    bool OpenMemory(std::vector<uint8_t> Bytes, Report& Rep);

    // --- manifest surface ---
    int         WerkMajor() const { return Major; }
    int         WerkMinor() const { return Minor; }
    const std::string& Profile() const { return ProfileName; }
    const std::string& EntityUuid() const { return Uuid; }
    const std::string& EntityName() const { return Name; }
    const std::string& EntitySummary() const { return Summary; }
    const std::string& ManifestSha256() const { return ManifestHash; }
    uint64_t    ManifestSize() const { return ManifestBytes.size(); }

    const std::vector<Part>&          Parts() const { return PartList; }
    const std::vector<MaterialEntry>& Materials() const { return MaterialList; }
    const std::vector<Node>&          Nodes() const { return NodeList; }
    const std::vector<ConventionCheck>& Conventions() const { return ConventionList; }

    const Node* FindNode(const std::string& NodeId) const;
    const Part* FindPart(const std::string& PartId) const;
    const MaterialEntry* FindMaterial(const std::string& MaterialId) const;

    // SPEC.md section 2 `primary`: a declared value beats an inference every
    // time, and a reader MUST report that it fell back. bOutFellBack says
    // which happened; the report gets a `primary-fallback` entry when it did.
    const Node* PrimaryMesh(Report& Rep) const;
    const Node* PrimarySound(Report& Rep) const;

    // The four fixed strings of SPEC.md 10 step 4. WerkLink returns
    // `unverified` whenever SIGNATURE.json is present, because it does not
    // implement Ed25519 and must not claim a check it did not make.
    const std::string& SignatureState() const { return SigState; }
    const std::string& SignatureCode() const { return SigCode; }

    // Payload access. Refuses any path not named in some version's files[]
    // (checklist step 9). Hash and size are verified on the way out.
    bool ReadPayload(const std::string& Path, std::vector<uint8_t>& Out, Report& Rep) const;

    const ZipReader& Zip() const { return Reader; }
    const std::vector<uint8_t>& RawManifest() const { return ManifestBytes; }
    const JsonValue* ManifestJson() const { return Root.get(); }

    // Is a given convention supported, for the blast radius of a node type?
    bool ConventionsSatisfiedFor(const std::string& NodeType, std::string& OutWhichFailed) const;

private:
    bool ParseManifest(Report& Rep);
    void CheckConventions(Report& Rep);
    void ResolveVersions(Report& Rep);

    ZipReader   Reader;
    JsonPtr     Root;
    std::vector<uint8_t> ManifestBytes;
    std::string ManifestHash;

    int         Major = 0;
    int         Minor = 0;
    std::string ProfileName;
    std::string Uuid, Name, Summary;
    std::string PrimaryMeshId, PrimarySoundId, PrimaryImageId;

    std::vector<Part>          PartList;
    std::vector<MaterialEntry> MaterialList;
    std::vector<Node>          NodeList;
    std::vector<ConventionCheck> ConventionList;
    std::map<std::string, std::string> FileHashIndex; // path -> sha256, from files[]
    std::map<std::string, uint64_t>    FileSizeIndex;

    std::string SigState = sig::StateAbsent;
    std::string SigCode  = sig::CodeAbsent;
};

// Every conventions key SPEC.md section 2 pins, with the value this adapter
// supports. Exposed so the README and the gate can print it rather than
// paraphrase it.
const std::vector<std::pair<std::string, std::string>>& SupportedConventions();

std::vector<std::string> ManifestSelftest(const std::string& FixturePath, bool bVerbose = false);

} // namespace werk
