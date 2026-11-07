#include "WerkLinkCommandlet.h"

#include "HAL/PlatformFileManager.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

#include "WerkLinkAction.h"
#include "WerkLinkBridge.h"
#include "WerkLinkSettings.h"

#include "werk_json.h"

using namespace WerkBridge;

UWerkLinkCommandlet::UWerkLinkCommandlet()
{
	IsClient = false;
	IsServer = false;
	IsEditor = true;
	LogToConsole = true;
	// The report is the product. A commandlet that only logs cannot be graded.
	ShowErrorCount = false;
}

namespace
{
	void PrintReport(const TArray<FWerkReportLine>& Report)
	{
		for (const FWerkReportLine& L : Report)
		{
			UE_LOG(LogWerkLink, Display, TEXT("  %-5s %-28s %-34s %s"),
			       *L.Severity, *L.Code, *L.Subject, *L.Detail);
		}
	}

	void PrintOutcomes(const TArray<FWerkNodeOutcome>& Outcomes)
	{
		for (const FWerkNodeOutcome& O : Outcomes)
		{
			UE_LOG(LogWerkLink, Display, TEXT("  %-11s %-28s %-30s %s"),
			       FWerkNodeOutcome::OutcomeName(O.Outcome), *O.NodeId, *O.NodeType, *O.Detail);
		}
	}

	int32 RunImport(const FWerkImportRequest& Request)
	{
		UE_LOG(LogWerkLink, Display, TEXT("WerkLink import: %s -> %s"),
		       *Request.WerkFilePath, *Request.DestinationPath);

		const double Start = FPlatformTime::Seconds();
		const FWerkImportResult Result = FWerkLinkAction::Import(Request);
		const double Elapsed = FPlatformTime::Seconds() - Start;

		if (!Result.bSuccess)
		{
			UE_LOG(LogWerkLink, Error, TEXT("import failed: %s"), *Result.ErrorMessage);
			PrintReport(Result.Report);
			return Result.ExitStatus();
		}

		UE_LOG(LogWerkLink, Display, TEXT("entity   : %s (%s)"), *Result.EntityName, *Result.EntityUuid);
		UE_LOG(LogWerkLink, Display, TEXT("signature: %s"), *Result.SignatureState);
		UE_LOG(LogWerkLink, Display, TEXT("result   : %s"), *Result.Summary());
		UE_LOG(LogWerkLink, Display, TEXT("elapsed  : %.3f s"), Elapsed);
		UE_LOG(LogWerkLink, Display, TEXT("per node:"));
		PrintOutcomes(Result.Outcomes);
		UE_LOG(LogWerkLink, Display, TEXT("report:"));
		PrintReport(Result.Report);
		return Result.ExitStatus();
	}

	int32 RunExport(const FWerkExportRequest& Request)
	{
		UE_LOG(LogWerkLink, Display, TEXT("WerkLink export: %d root(s) -> %s"),
		       Request.RootAssetPaths.Num(), *Request.OutputFilePath);

		const double Start = FPlatformTime::Seconds();
		const FWerkExportResult Result = FWerkLinkAction::Export(Request);
		const double Elapsed = FPlatformTime::Seconds() - Start;

		if (!Result.bSuccess)
		{
			UE_LOG(LogWerkLink, Error, TEXT("export failed: %s"), *Result.ErrorMessage);
			PrintReport(Result.Report);
			return Result.ExitStatus();
		}

		UE_LOG(LogWerkLink, Display, TEXT("result   : %s"), *Result.Summary());
		UE_LOG(LogWerkLink, Display, TEXT("manifest : sha256 %s"), *Result.ManifestSha256);
		UE_LOG(LogWerkLink, Display, TEXT("elapsed  : %.3f s"), Elapsed);
		UE_LOG(LogWerkLink, Display, TEXT("per node:"));
		PrintOutcomes(Result.Outcomes);
		UE_LOG(LogWerkLink, Display, TEXT("report:"));
		PrintReport(Result.Report);
		return Result.ExitStatus();
	}
}

int32 UWerkLinkCommandlet::Main(const FString& Params)
{
	TArray<FString> Tokens;
	TArray<FString> Switches;
	TMap<FString, FString> Args;
	UCommandlet::ParseCommandLine(*Params, Tokens, Switches, Args);

	const UWerkLinkSettings* Settings = GetDefault<UWerkLinkSettings>();

	auto Arg = [&Args](const TCHAR* Key, const FString& Default = FString()) -> FString
	{
		if (const FString* Found = Args.Find(Key))
		{
			return *Found;
		}
		return Default;
	};
	const bool bDryRun = Switches.Contains(TEXT("DryRun"));
	const bool bNoSave = Switches.Contains(TEXT("NoSave"));

	// --- batch mode ---------------------------------------------------------
	const FString ManifestPath = Arg(TEXT("Manifest"));
	if (!ManifestPath.IsEmpty())
	{
		TArray<uint8> Bytes;
		if (!FFileHelper::LoadFileToArray(Bytes, *ManifestPath))
		{
			UE_LOG(LogWerkLink, Error, TEXT("cannot read batch manifest: %s"), *ManifestPath);
			return 2;
		}
		std::string Err;
		// The same JSON parser the format uses, so the batch file gets the
		// same duplicate-key and BOM rules as a manifest does. A batch file
		// with two "op" keys is a mistake worth refusing.
		werk::JsonPtr Doc = werk::JsonParse(ToStdBytes(Bytes), Err);
		if (!Doc || !Doc->IsArray())
		{
			UE_LOG(LogWerkLink, Error, TEXT("batch manifest is not a JSON array: %s"), *ToF(Err));
			return 2;
		}

		int32 Worst = 0;
		for (size_t i = 0; i < Doc->Size(); ++i)
		{
			const werk::JsonValue* Op = Doc->At(i);
			if (!Op || !Op->IsObject())
			{
				continue;
			}
			const FString Kind = ToF(Op->GetString("op"));
			int32 Status = 0;
			if (Kind == TEXT("import"))
			{
				FWerkImportRequest R;
				R.WerkFilePath = ToF(Op->GetString("file"));
				R.DestinationPath = ToF(Op->GetString("dest", "/Game/Werk"));
				R.MasterMaterial = FSoftObjectPath(ToF(Op->GetString("master")));
				R.bSavePackages = !bNoSave;
				R.bDryRun = bDryRun;
				R.bImportAudio = Settings->bImportAudio;
				R.bImportCollision = Settings->bImportCollision;
				R.bImportSemanticTags = Settings->bImportSemanticTags;
				Status = RunImport(R);
			}
			else if (Kind == TEXT("export"))
			{
				FWerkExportRequest R;
				R.OutputFilePath = ToF(Op->GetString("file"));
				R.SpecSourceDirectory = ToF(Op->GetString("spec"));
				R.EntityName = ToF(Op->GetString("name"));
				R.ProducerTool = Settings->ProducerTool;
				R.bDryRun = bDryRun;
				if (const werk::JsonValue* AssetsArr = Op->GetArray("assets"))
				{
					for (size_t k = 0; k < AssetsArr->Size(); ++k)
					{
						if (const werk::JsonValue* S = AssetsArr->At(k))
						{
							if (S->IsString())
							{
								R.RootAssetPaths.Add(ToF(S->str));
							}
						}
					}
				}
				Status = RunExport(R);
			}
			else
			{
				UE_LOG(LogWerkLink, Warning, TEXT("batch entry %d: unknown op '%s'"),
				       int32(i), *Kind);
				continue;
			}
			Worst = FMath::Max(Worst, Status);
		}
		UE_LOG(LogWerkLink, Display, TEXT("batch complete, worst exit status %d"), Worst);
		return Worst;
	}

	// --- single import ------------------------------------------------------
	const FString ImportPath = Arg(TEXT("Import"));
	if (!ImportPath.IsEmpty())
	{
		FWerkImportRequest R;
		R.WerkFilePath = FPaths::ConvertRelativePathToFull(ImportPath);
		R.DestinationPath = Arg(TEXT("Dest"),
			Settings->ImportRootPath.IsEmpty() ? FString(TEXT("/Game/Werk")) : Settings->ImportRootPath);
		const FString Master = Arg(TEXT("Master"));
		R.MasterMaterial = Master.IsEmpty() ? Settings->MasterMaterial : FSoftObjectPath(Master);
		R.bSavePackages = !bNoSave;
		R.bDryRun = bDryRun;
		R.bImportAudio = !Switches.Contains(TEXT("NoAudio")) && Settings->bImportAudio;
		R.bImportCollision = !Switches.Contains(TEXT("NoCollision")) && Settings->bImportCollision;
		R.bImportSemanticTags = Settings->bImportSemanticTags;
		return RunImport(R);
	}

	// --- single export ------------------------------------------------------
	const FString ExportPath = Arg(TEXT("Export"));
	if (!ExportPath.IsEmpty())
	{
		FWerkExportRequest R;
		R.OutputFilePath = FPaths::ConvertRelativePathToFull(ExportPath);
		Arg(TEXT("Assets")).ParseIntoArray(R.RootAssetPaths, TEXT(","), true);
		R.SpecSourceDirectory = Arg(TEXT("Spec"), Settings->SpecSourceDirectory.Path);
		R.EntityName = Arg(TEXT("Name"));
		R.ProducerTool = Settings->ProducerTool;
		R.bDryRun = bDryRun;
		// Findings B8: hermetic refusal is opt-IN headless, so a batch does not
		// die on its first engine reference.
		R.bFailOnUnresolvableExternalReference = Switches.Contains(TEXT("Hermetic"));
		if (R.RootAssetPaths.Num() == 0)
		{
			UE_LOG(LogWerkLink, Error, TEXT("-Export needs -Assets=/Game/A.A[,/Game/B.B]"));
			return 2;
		}
		return RunExport(R);
	}

	UE_LOG(LogWerkLink, Display,
	       TEXT("usage: -run=WerkLink -Import=<file.werk> [-Dest=/Game/Werk] [-Master=...] "
	            "[-DryRun] [-NoSave] [-NoAudio] [-NoCollision]"));
	UE_LOG(LogWerkLink, Display,
	       TEXT("       -run=WerkLink -Export=<out.werk> -Assets=<a,b> [-Spec=<dir>] [-Name=...] "
	            "[-Hermetic] [-DryRun]"));
	UE_LOG(LogWerkLink, Display, TEXT("       -run=WerkLink -Manifest=<batch.json>"));
	return 2;
}
