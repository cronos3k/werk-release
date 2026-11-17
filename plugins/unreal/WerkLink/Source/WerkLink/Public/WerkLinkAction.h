#pragma once

#include "CoreMinimal.h"
#include "UObject/SoftObjectPath.h"

class UObject;

/**
 * The static facade, copied wholesale from the content mover's shape
 * (findings A1): a plain class with only static methods, a POD request in and
 * a POD result out, no state, no delegates, and NO SLATE.
 *
 * That last part is not stylistic. Findings A4: every headless hang in the
 * production plugin -- the modal window, the OS folder browser, the message
 * dialog -- lived in the module layer, and the facade being clean of them is
 * the only reason it could later be driven from a commandlet at all. The
 * Content Browser menu and the commandlet are two callers of this file and
 * neither knows about the other.
 *
 * Outcomes are DATA, not log lines. Graceful degradation is only expressible
 * if a skipped node is a struct field that a commandlet can inspect and print;
 * a UE_LOG is not an outcome, it is a side effect.
 */

/** What happened to one node. */
enum class EWerkOutcome : uint8
{
	Imported,       // an asset exists that did not before
	Exported,       // bytes were written into the package
	Skipped,        // recognised, deliberately not handled in v1
	Unknown,        // an unknown node type -- newer, or an x.* extension
	Refused,        // hashes, envelope, schema or a requires edge failed
	Substituted,    // handled, but with a declared fallback; see Detail
};

struct FWerkNodeOutcome
{
	FString       NodeId;
	FString       NodeType;
	EWerkOutcome  Outcome = EWerkOutcome::Skipped;
	/** The stable machine code from SPEC.md 10.1, e.g. "hash-mismatch". */
	FString       Code;
	/** Free prose. Never the only place a reason is recorded. */
	FString       Detail;
	/** Object path of the asset produced, when one was. */
	FString       AssetPath;

	WERKLINK_API static const TCHAR* OutcomeName(EWerkOutcome In);
};

/** One report entry, mirrored out of the engine-free core. */
struct FWerkReportLine
{
	FString Code;
	FString Severity; // info | warn | error
	FString Subject;
	FString Detail;
};

struct FWerkImportRequest
{
	/** Absolute path to a .werk file. */
	FString WerkFilePath;

	/** Content path to import under, e.g. /Game/Werk. A subfolder named for
	 *  the entity is created inside it. */
	FString DestinationPath;

	bool bImportAudio = true;
	bool bImportCollision = true;
	bool bImportSemanticTags = true;

	/** Parent for imported core.material nodes. May be null; then materials
	 *  are reported as skipped rather than invented. */
	FSoftObjectPath MasterMaterial;

	/** Save the created packages to disk. The commandlet needs this; the GUI
	 *  can leave the packages dirty for the user to review. */
	bool bSavePackages = true;

	/** Report every node without creating anything. */
	bool bDryRun = false;
};

struct FWerkImportResult
{
	bool    bSuccess = false;
	FString ErrorMessage;

	FString EntityUuid;
	FString EntityName;
	/** One of the four fixed strings of SPEC.md 10 step 4. */
	FString SignatureState;

	int32 NodesTotal = 0;
	int32 NodesImported = 0;
	int32 NodesSkipped = 0;
	int32 NodesRefused = 0;
	int32 AssetsCreated = 0;
	int32 PackagesSaved = 0;
	int32 FilesVerified = 0;

	TArray<FWerkNodeOutcome> Outcomes;
	TArray<FWerkReportLine>  Report;
	TArray<FString>          CreatedAssetPaths;

	/** SPEC.md 10.1 exit status: 0 clean, 1 errors present, 2 nothing loaded. */
	WERKLINK_API int32 ExitStatus() const;
	WERKLINK_API FString Summary() const;
};

struct FWerkExportRequest
{
	/** Object paths of the assets the user selected. The closure is walked
	 *  from these; they are the roots, not the whole set. */
	TArray<FString> RootAssetPaths;

	/** Absolute path of the .werk to write. */
	FString OutputFilePath;

	/** entity.name. When empty, taken from the first root asset. */
	FString EntityName;

	/** Directory holding spec/ and loaders/ to embed. When empty the package
	 *  is written WITHOUT them and the report says it is not
	 *  redistributable-conformant, because law 2 says the format travels with
	 *  the file. */
	FString SpecSourceDirectory;

	FString ProducerTool;

	/** Hermetic rule: refuse rather than substitute when a dependency cannot
	 *  be resolved into the package. */
	bool bFailOnUnresolvableExternalReference = false;

	bool bDryRun = false;
};

struct FWerkExportResult
{
	bool    bSuccess = false;
	FString ErrorMessage;

	FString OutputFilePath;
	FString EntityUuid;
	FString ManifestSha256;

	int32    AssetsInClosure = 0;
	int32    NodesWritten = 0;
	int32    FilesWritten = 0;
	int32    ExternalReferencesResolved = 0;
	int32    ExternalReferencesSubstituted = 0;
	uint64   ContainerBytes = 0;
	uint64   PreviewPrefixBytes = 0;
	bool     bSpecEmbedded = false;

	TArray<FWerkNodeOutcome> Outcomes;
	TArray<FWerkReportLine>  Report;

	WERKLINK_API int32 ExitStatus() const;
	WERKLINK_API FString Summary() const;
};

class WERKLINK_API FWerkLinkAction
{
public:
	/** .werk -> UAssets. Never fails the whole file for one bad node. */
	static FWerkImportResult Import(const FWerkImportRequest& Request);

	/** UAssets -> a conformant unsigned .werk. */
	static FWerkExportResult Export(const FWerkExportRequest& Request);

	/**
	 * The dependency closure of a set of roots (findings A2/B2/B3):
	 * EDependencyCategory::Package, redirectors resolved first, /Script/
	 * filtered out, deduped by PackageName, cycle-guarded. /Engine/ packages
	 * are returned in OutEngineReferences rather than in the closure, because
	 * they are the resolve-or-substitute path and not ours to copy.
	 */
	static void WalkClosure(const TArray<FString>& RootAssetPaths,
	                        TArray<FString>& OutClosureAssetPaths,
	                        TArray<FString>& OutEngineReferences,
	                        TArray<FWerkReportLine>& OutReport);

	/**
	 * Findings B1: assert editor build, uncooked, source data present, up
	 * front and loudly. Called at the top of Export. Returns false and fills
	 * OutError when the environment cannot produce a truthful package.
	 */
	static bool AssertExportEnvironment(FString& OutError);

	/** kebab-case werk id -> a legal Unreal object name. NOT reversible; the
	 *  reverse direction is a lookup in UWerkAssetUserData, never a
	 *  computation. */
	static FString WerkIdToObjectName(const FString& WerkId);

	/** A legal kebab-case werk id derived from an Unreal name, for export of
	 *  assets that were never imported and so carry no stored id. */
	static FString ObjectNameToWerkId(const FString& ObjectName);
};
