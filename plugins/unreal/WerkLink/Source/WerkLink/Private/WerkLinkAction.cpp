#include "WerkLinkAction.h"

#include "AssetRegistry/ARFilter.h"
#include "AssetRegistry/AssetData.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "AssetRegistry/IAssetRegistry.h"
#include "Misc/AssetRegistryInterface.h"
#include "Misc/PackageName.h"
#include "Modules/ModuleManager.h"
#include "UObject/ObjectRedirector.h"

#include "WerkLinkBridge.h"

DEFINE_LOG_CATEGORY(LogWerkLink);

const TCHAR* FWerkNodeOutcome::OutcomeName(EWerkOutcome In)
{
	switch (In)
	{
	case EWerkOutcome::Imported:    return TEXT("imported");
	case EWerkOutcome::Exported:    return TEXT("exported");
	case EWerkOutcome::Skipped:     return TEXT("skipped");
	case EWerkOutcome::Unknown:     return TEXT("unknown");
	case EWerkOutcome::Refused:     return TEXT("refused");
	case EWerkOutcome::Substituted: return TEXT("substituted");
	}
	return TEXT("skipped");
}

namespace
{
	int32 ExitStatusFrom(bool bOpened, const TArray<FWerkReportLine>& Report)
	{
		if (!bOpened)
		{
			return 2;
		}
		for (const FWerkReportLine& L : Report)
		{
			if (L.Severity == TEXT("error"))
			{
				return 1;
			}
		}
		return 0;
	}
}

int32 FWerkImportResult::ExitStatus() const
{
	return ExitStatusFrom(bSuccess || NodesTotal > 0, Report);
}

FString FWerkImportResult::Summary() const
{
	return FString::Printf(
		TEXT("%d nodes: %d imported, %d skipped, %d refused; %d assets, %d packages saved, "
		     "%d files verified; signature %s"),
		NodesTotal, NodesImported, NodesSkipped, NodesRefused, AssetsCreated, PackagesSaved,
		FilesVerified, *SignatureState);
}

int32 FWerkExportResult::ExitStatus() const
{
	return ExitStatusFrom(bSuccess, Report);
}

FString FWerkExportResult::Summary() const
{
	return FString::Printf(
		TEXT("%d assets in closure -> %d nodes, %d files, %llu bytes (preview prefix %llu); "
		     "%d engine refs resolved, %d substituted; spec embedded: %s"),
		AssetsInClosure, NodesWritten, FilesWritten,
		(unsigned long long)ContainerBytes, (unsigned long long)PreviewPrefixBytes,
		ExternalReferencesResolved, ExternalReferencesSubstituted,
		bSpecEmbedded ? TEXT("yes") : TEXT("NO - not redistributable-conformant"));
}

// --- identity mapping ------------------------------------------------------

FString FWerkLinkAction::WerkIdToObjectName(const FString& WerkId)
{
	// kebab-case -> PascalCase. Lossy on purpose: two different werk ids can
	// land on the same name, which is exactly why the reverse direction is a
	// lookup in UWerkAssetUserData and never a computation.
	FString Out;
	Out.Reserve(WerkId.Len());
	bool bUpper = true;
	for (TCHAR C : WerkId)
	{
		if (C == TEXT('-') || C == TEXT('.') || C == TEXT('_') || C == TEXT(' '))
		{
			bUpper = true;
			continue;
		}
		if (!FChar::IsAlnum(C))
		{
			continue;
		}
		Out.AppendChar(bUpper ? FChar::ToUpper(C) : C);
		bUpper = false;
	}
	if (Out.IsEmpty())
	{
		Out = TEXT("WerkNode");
	}
	if (FChar::IsDigit(Out[0]))
	{
		// An Unreal object name may not begin with a digit; a werk id may.
		Out.InsertAt(0, TEXT('N'));
	}
	return Out;
}

FString FWerkLinkAction::ObjectNameToWerkId(const FString& ObjectName)
{
	// MINI-SPECS 2 pins werk ids to ^[a-z0-9]+(-[a-z0-9]+)*$, so this must
	// produce something that matches or the manifest is invalid on emission.
	FString Out;
	Out.Reserve(ObjectName.Len() + 8);
	bool bPrevLower = false;
	for (int32 i = 0; i < ObjectName.Len(); ++i)
	{
		const TCHAR C = ObjectName[i];
		if (!FChar::IsAlnum(C))
		{
			if (!Out.IsEmpty() && Out[Out.Len() - 1] != TEXT('-'))
			{
				Out.AppendChar(TEXT('-'));
			}
			bPrevLower = false;
			continue;
		}
		if (FChar::IsUpper(C) && bPrevLower && !Out.IsEmpty() && Out[Out.Len() - 1] != TEXT('-'))
		{
			Out.AppendChar(TEXT('-'));
		}
		Out.AppendChar(FChar::ToLower(C));
		bPrevLower = FChar::IsLower(C) || FChar::IsDigit(C);
	}
	while (Out.StartsWith(TEXT("-")))
	{
		Out.RemoveAt(0);
	}
	while (Out.EndsWith(TEXT("-")))
	{
		Out.RemoveAt(Out.Len() - 1);
	}
	if (Out.IsEmpty())
	{
		Out = TEXT("node");
	}
	return Out;
}

// --- environment assertion (findings B1) -----------------------------------

bool FWerkLinkAction::AssertExportEnvironment(FString& OutError)
{
	OutError.Reset();

#if !WITH_EDITOR
	OutError = TEXT("WerkLink export requires an editor build: the exporter reads UStaticMesh "
	                "source data (GetMeshDescription) and FTextureSource, neither of which "
	                "exists outside the editor.");
	return false;
#else
	if (FPlatformProperties::RequiresCookedData())
	{
		OutError = TEXT("WerkLink export requires uncooked data. Cooked packages have no mesh "
		                "description and no texture source; an export from them would produce a "
		                "package that does not contain what it says it contains.");
		return false;
	}
	// Findings B1: the FBX and mesh exporters assert headless. WerkLink never
	// calls one, and this comment is here so that a later change that adds one
	// has to delete a sentence that says not to.
	return true;
#endif
}

// --- closure walk (findings A6, B2, B3, B4) --------------------------------

void FWerkLinkAction::WalkClosure(const TArray<FString>& RootAssetPaths,
                                  TArray<FString>& OutClosureAssetPaths,
                                  TArray<FString>& OutEngineReferences,
                                  TArray<FWerkReportLine>& OutReport)
{
	OutClosureAssetPaths.Reset();
	OutEngineReferences.Reset();

	IAssetRegistry& Registry =
		FModuleManager::LoadModuleChecked<FAssetRegistryModule>("AssetRegistry").Get();

	auto AddReport = [&OutReport](const TCHAR* Code, const TCHAR* Severity,
	                              const FString& Subject, const FString& Detail)
	{
		FWerkReportLine L;
		L.Code = Code;
		L.Severity = Severity;
		L.Subject = Subject;
		L.Detail = Detail;
		OutReport.Add(MoveTemp(L));
	};

	// Findings B3: dedupe by PackageName. A Blueprint and its generated class
	// share a package and the registry returns both, so a set keyed on the
	// asset path double-counts. The visited guard and the output key are the
	// same FName for the same reason -- one key, one meaning.
	TSet<FName> Visited;
	TArray<FName> Frontier;

	auto ResolveRedirector = [&Registry](FName PackageName) -> FName
	{
		// Findings A6 + B4: resolve THROUGH redirectors before walking, so the
		// closure never records a redirector's package as a dependency. The
		// query is the production one, GetClassPathName() and all.
		FARFilter Filter;
		Filter.PackageNames.Add(PackageName);
		Filter.ClassPaths.Add(UObjectRedirector::StaticClass()->GetClassPathName());
		TArray<FAssetData> Found;
		Registry.GetAssets(Filter, Found);
		if (Found.Num() == 0)
		{
			return PackageName;
		}
		// A redirector's destination is recorded as its one hard dependency.
		TArray<FName> Deps;
		Registry.GetDependencies(PackageName, Deps, UE::AssetRegistry::EDependencyCategory::Package);
		for (FName D : Deps)
		{
			if (D != PackageName)
			{
				return D;
			}
		}
		return PackageName;
	};

	for (const FString& RootPath : RootAssetPaths)
	{
		const FString PackagePath = FPackageName::ObjectPathToPackageName(RootPath);
		FName PackageName(*PackagePath);
		PackageName = ResolveRedirector(PackageName);
		if (!Visited.Contains(PackageName))
		{
			Visited.Add(PackageName);
			Frontier.Add(PackageName);
		}
	}

	while (Frontier.Num() > 0)
	{
		const FName Current = Frontier.Pop();
		const FString CurrentStr = Current.ToString();

		// /Script/ packages are code, not content, and are never in a package.
		if (CurrentStr.StartsWith(TEXT("/Script/")))
		{
			continue;
		}

		// /Engine/ is the resolve-or-substitute path: an engine asset is not
		// ours to copy into a hermetic package, and it is not allowed to
		// remain as a dangling reference either. The exporter decides which;
		// the walker only separates them.
		if (CurrentStr.StartsWith(TEXT("/Engine/")))
		{
			OutEngineReferences.AddUnique(CurrentStr);
			AddReport(TEXT("external-reference"), TEXT("warn"), CurrentStr,
			          TEXT("engine package reached from the closure; must be baked or "
			               "substituted with a declared fallback, never left dangling"));
			continue;
		}

		// /WerkLink/ is this plugin's own content -- today, exactly the master
		// material every imported UMaterialInstanceConstant parents to. It is
		// tooling, not entity, and exporting it produced a phantom
		// `core.material` node describing the MASTER's defaults next to the
		// real one describing the instance's values. Measured: a five-asset
		// export produced 12 nodes including `material-m-werk-pbr`.
		//
		// The hermetic rule is satisfied without it, and this is the reason it
		// is a drop rather than a hole: `core.material` carries the FLATTENED
		// parameters, so the package never references a parent in the first
		// place. Nothing dangles because nothing pointed at it.
		if (CurrentStr.StartsWith(TEXT("/WerkLink/")))
		{
			AddReport(TEXT("substituted-fallback"), TEXT("info"), CurrentStr,
			          TEXT("WerkLink's own master material, reached as a material instance's "
			               "parent. NOT exported: core.material carries flattened parameters, "
			               "so the package does not reference a parent and nothing is left "
			               "dangling by leaving it out."));
			continue;
		}

		OutClosureAssetPaths.AddUnique(CurrentStr);

		// Hard and soft in one query: EDependencyProperty has a `Hard` bit and
		// the DOCUMENTED meaning of its absence is "soft" -- there is no
		// `Soft` enumerator to ask for (AssetRegistryInterface.h:93). Asking
		// unfiltered returns both, which is what "Hard then Soft" means in
		// practice.
		TArray<FName> Deps;
		Registry.GetDependencies(Current, Deps,
		                         UE::AssetRegistry::EDependencyCategory::Package
		                             | UE::AssetRegistry::EDependencyCategory::SearchableName);

		for (FName Dep : Deps)
		{
			const FName Resolved = ResolveRedirector(Dep);
			if (Visited.Contains(Resolved))
			{
				continue; // the cycle guard, and the dedupe, at once
			}
			Visited.Add(Resolved);
			Frontier.Add(Resolved);
		}
	}

	AddReport(TEXT("imported"), TEXT("info"), FString(),
	          FString::Printf(TEXT("closure: %d packages, %d engine references, from %d root(s)"),
	                          OutClosureAssetPaths.Num(), OutEngineReferences.Num(),
	                          RootAssetPaths.Num()));
}
