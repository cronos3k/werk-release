#include "WerkLinkScripting.h"

#include "Misc/Paths.h"

#include "WerkLinkAction.h"
#include "WerkLinkBridge.h"
#include "WerkLinkSettings.h"

#include "werk_json.h"

using namespace WerkBridge;

namespace
{
	werk::JsonPtr OutcomesJson(const TArray<FWerkNodeOutcome>& Outcomes)
	{
		werk::JsonPtr A = werk::JsonValue::MakeArray();
		for (const FWerkNodeOutcome& O : Outcomes)
		{
			werk::JsonPtr J = werk::JsonValue::MakeObject();
			J->SetString("node_id", ToStd(O.NodeId));
			J->SetString("type", ToStd(O.NodeType));
			J->SetString("outcome", ToStd(FString(FWerkNodeOutcome::OutcomeName(O.Outcome))));
			J->SetString("code", ToStd(O.Code));
			J->SetString("detail", ToStd(O.Detail));
			J->SetString("asset", ToStd(O.AssetPath));
			A->Push(J);
		}
		return A;
	}

	werk::JsonPtr ReportJson(const TArray<FWerkReportLine>& Report)
	{
		werk::JsonPtr A = werk::JsonValue::MakeArray();
		for (const FWerkReportLine& L : Report)
		{
			werk::JsonPtr J = werk::JsonValue::MakeObject();
			J->SetString("severity", ToStd(L.Severity));
			J->SetString("code", ToStd(L.Code));
			J->SetString("subject", ToStd(L.Subject));
			J->SetString("detail", ToStd(L.Detail));
			A->Push(J);
		}
		return A;
	}

	werk::JsonPtr StringsJson(const TArray<FString>& In)
	{
		werk::JsonPtr A = werk::JsonValue::MakeArray();
		for (const FString& S : In)
		{
			A->Push(werk::JsonValue::MakeString(ToStd(S)));
		}
		return A;
	}
}

FString UWerkLinkScripting::ImportWerk(const FString& WerkFile, const FString& DestinationPath,
                                       bool bSavePackages, const FString& MasterMaterial)
{
	const UWerkLinkSettings* Settings = GetDefault<UWerkLinkSettings>();
	FWerkImportRequest R;
	R.WerkFilePath = FPaths::ConvertRelativePathToFull(WerkFile);
	R.DestinationPath = DestinationPath.IsEmpty()
		? (Settings->ImportRootPath.IsEmpty() ? FString(TEXT("/Game/Werk")) : Settings->ImportRootPath)
		: DestinationPath;
	R.MasterMaterial = MasterMaterial.IsEmpty() ? Settings->MasterMaterial
	                                            : FSoftObjectPath(MasterMaterial);
	R.bSavePackages = bSavePackages;
	R.bImportAudio = Settings->bImportAudio;
	R.bImportCollision = Settings->bImportCollision;
	R.bImportSemanticTags = Settings->bImportSemanticTags;

	const FWerkImportResult Res = FWerkLinkAction::Import(R);

	werk::JsonPtr J = werk::JsonValue::MakeObject();
	J->SetString("op", "import");
	J->SetString("file", ToStd(R.WerkFilePath));
	J->SetInt("exit", Res.ExitStatus());
	J->SetBool("success", Res.bSuccess);
	J->SetString("error", ToStd(Res.ErrorMessage));
	J->SetString("summary", ToStd(Res.Summary()));
	J->SetString("entity_uuid", ToStd(Res.EntityUuid));
	J->SetString("entity_name", ToStd(Res.EntityName));
	J->SetString("signature", ToStd(Res.SignatureState));
	J->SetInt("nodes", Res.NodesTotal);
	J->SetInt("imported", Res.NodesImported);
	J->SetInt("skipped", Res.NodesSkipped);
	J->SetInt("refused", Res.NodesRefused);
	J->SetInt("assets", Res.AssetsCreated);
	J->SetInt("packages_saved", Res.PackagesSaved);
	J->SetInt("files_verified", Res.FilesVerified);
	J->Set("created_assets", StringsJson(Res.CreatedAssetPaths));
	J->Set("outcomes", OutcomesJson(Res.Outcomes));
	J->Set("report", ReportJson(Res.Report));
	return ToF(werk::JsonWritePretty(*J));
}

FString UWerkLinkScripting::ExportWerk(const FString& OutputFile, const TArray<FString>& RootAssetPaths,
                                       const FString& SpecSourceDirectory, const FString& EntityName,
                                       bool bHermetic)
{
	const UWerkLinkSettings* Settings = GetDefault<UWerkLinkSettings>();
	FWerkExportRequest R;
	R.OutputFilePath = FPaths::ConvertRelativePathToFull(OutputFile);
	R.RootAssetPaths = RootAssetPaths;
	R.SpecSourceDirectory = SpecSourceDirectory.IsEmpty() ? Settings->SpecSourceDirectory.Path
	                                                      : SpecSourceDirectory;
	R.EntityName = EntityName;
	R.ProducerTool = Settings->ProducerTool;
	R.bFailOnUnresolvableExternalReference = bHermetic;

	const FWerkExportResult Res = FWerkLinkAction::Export(R);

	werk::JsonPtr J = werk::JsonValue::MakeObject();
	J->SetString("op", "export");
	J->SetString("file", ToStd(R.OutputFilePath));
	J->SetInt("exit", Res.ExitStatus());
	J->SetBool("success", Res.bSuccess);
	J->SetString("error", ToStd(Res.ErrorMessage));
	J->SetString("summary", ToStd(Res.Summary()));
	J->SetString("manifest_sha256", ToStd(Res.ManifestSha256));
	J->SetInt("assets_in_closure", Res.AssetsInClosure);
	J->SetInt("nodes_written", Res.NodesWritten);
	J->SetInt("files_written", Res.FilesWritten);
	J->SetBool("spec_embedded", Res.bSpecEmbedded);
	J->Set("outcomes", OutcomesJson(Res.Outcomes));
	J->Set("report", ReportJson(Res.Report));
	return ToF(werk::JsonWritePretty(*J));
}
