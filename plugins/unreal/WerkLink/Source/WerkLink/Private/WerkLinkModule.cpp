// The UI layer, and the only place in this plugin allowed to construct a
// widget (findings A4). The facade below it has no Slate at all, which is what
// lets the commandlet drive the same code.

#include "WerkLinkModule.h"

#include "ContentBrowserModule.h"
#include "DesktopPlatformModule.h"
#include "Framework/Application/SlateApplication.h"
#include "Framework/MultiBox/MultiBoxBuilder.h"
#include "IDesktopPlatform.h"
#include "ISettingsModule.h"
#include "Misc/MessageDialog.h"
#include "Misc/Paths.h"
#include "Styling/AppStyle.h"

#include "WerkLinkAction.h"
#include "WerkLinkBridge.h"
#include "WerkLinkSettings.h"

#define LOCTEXT_NAMESPACE "WerkLink"

IMPLEMENT_MODULE(FWerkLinkModule, WerkLink)

void FWerkLinkModule::StartupModule()
{
	RegisterSettings();
	RegisterContextMenus();
}

void FWerkLinkModule::ShutdownModule()
{
	UnregisterContextMenus();
	UnregisterSettings();
}

// --- settings (findings A3) ------------------------------------------------

void FWerkLinkModule::RegisterSettings()
{
	// GetModulePtr, not LoadModuleChecked: settings may legitimately not exist
	// in a commandlet, and this is the difference between degrading and
	// asserting.
	if (ISettingsModule* SettingsModule = FModuleManager::GetModulePtr<ISettingsModule>("Settings"))
	{
		SettingsModule->RegisterSettings(
			"Project", "Plugins", "WerkLink",
			LOCTEXT("SettingsName", "WerkLink"),
			LOCTEXT("SettingsDesc", "Import and export werk artifact containers."),
			GetMutableDefault<UWerkLinkSettings>());
	}
}

void FWerkLinkModule::UnregisterSettings()
{
	if (ISettingsModule* SettingsModule = FModuleManager::GetModulePtr<ISettingsModule>("Settings"))
	{
		SettingsModule->UnregisterSettings("Project", "Plugins", "WerkLink");
	}
}

// --- context menus (findings A2) -------------------------------------------

void FWerkLinkModule::RegisterContextMenus()
{
	FContentBrowserModule& ContentBrowser =
		FModuleManager::LoadModuleChecked<FContentBrowserModule>(TEXT("ContentBrowser"));

	// Folder view: "Import .werk here".
	{
		TArray<FContentBrowserMenuExtender_SelectedPaths>& Extenders =
			ContentBrowser.GetAllPathViewContextMenuExtenders();

		Extenders.Add(FContentBrowserMenuExtender_SelectedPaths::CreateLambda(
			[](const TArray<FString>& SelectedPaths)
			{
				TSharedRef<FExtender> Extender = MakeShared<FExtender>();
				Extender->AddMenuExtension(
					"PathContextBulkOperations", EExtensionHook::After, nullptr,
					FMenuExtensionDelegate::CreateStatic(
						[](FMenuBuilder& MenuBuilder, TArray<FString> Paths)
						{
							MenuBuilder.AddMenuEntry(
								LOCTEXT("ImportLabel", "Import .werk here..."),
								LOCTEXT("ImportTooltip",
									"Import a werk artifact container into this folder. Every node "
									"that cannot be handled is reported; nothing is skipped "
									"silently."),
								FSlateIcon(FAppStyle::GetAppStyleSetName(), "Icons.Import"),
								FUIAction(FExecuteAction::CreateLambda([Paths]()
								{
									FWerkLinkModule& Module =
										FModuleManager::LoadModuleChecked<FWerkLinkModule>("WerkLink");
									Module.ExecuteImportDialog(Paths);
								})));
						},
						// Captured BY VALUE: the caller's array does not
						// outlive the menu.
						SelectedPaths));
				return Extender;
			}));

		PathViewExtenderHandle = Extenders.Last().GetHandle();
	}

	// Asset view: "Export to .werk".
	{
		TArray<FContentBrowserMenuExtender_SelectedAssets>& Extenders =
			ContentBrowser.GetAllAssetViewContextMenuExtenders();

		Extenders.Add(FContentBrowserMenuExtender_SelectedAssets::CreateLambda(
			[](const TArray<FAssetData>& SelectedAssets)
			{
				TArray<FString> Paths;
				for (const FAssetData& Data : SelectedAssets)
				{
					Paths.Add(Data.GetSoftObjectPath().ToString());
				}

				TSharedRef<FExtender> Extender = MakeShared<FExtender>();
				Extender->AddMenuExtension(
					"CommonAssetActions", EExtensionHook::After, nullptr,
					FMenuExtensionDelegate::CreateStatic(
						[](FMenuBuilder& MenuBuilder, TArray<FString> AssetPaths)
						{
							MenuBuilder.AddMenuEntry(
								LOCTEXT("ExportLabel", "Export to .werk..."),
								LOCTEXT("ExportTooltip",
									"Export the selected assets and their dependency closure as a "
									"hermetic werk container. Read from editor source data, never "
									"from an exporter."),
								FSlateIcon(FAppStyle::GetAppStyleSetName(), "Icons.Save"),
								FUIAction(FExecuteAction::CreateLambda([AssetPaths]()
								{
									FWerkLinkModule& Module =
										FModuleManager::LoadModuleChecked<FWerkLinkModule>("WerkLink");
									Module.ExecuteExportDialog(AssetPaths);
								})));
						},
						Paths));
				return Extender;
			}));

		AssetViewExtenderHandle = Extenders.Last().GetHandle();
	}
}

void FWerkLinkModule::UnregisterContextMenus()
{
	// Findings A2: guard with IsModuleLoaded. On editor shutdown the
	// ContentBrowser module may already be gone, and a LoadModuleChecked in a
	// ShutdownModule is a crash.
	if (!FModuleManager::Get().IsModuleLoaded("ContentBrowser"))
	{
		return;
	}
	FContentBrowserModule& ContentBrowser =
		FModuleManager::GetModuleChecked<FContentBrowserModule>(TEXT("ContentBrowser"));

	ContentBrowser.GetAllPathViewContextMenuExtenders().RemoveAll(
		[this](const FContentBrowserMenuExtender_SelectedPaths& Delegate)
		{
			return Delegate.GetHandle() == PathViewExtenderHandle;
		});
	ContentBrowser.GetAllAssetViewContextMenuExtenders().RemoveAll(
		[this](const FContentBrowserMenuExtender_SelectedAssets& Delegate)
		{
			return Delegate.GetHandle() == AssetViewExtenderHandle;
		});
}

// --- the two GUI entry points ----------------------------------------------

namespace
{
	FString FormatOutcomes(const TArray<FWerkNodeOutcome>& Outcomes, int32 Limit = 40)
	{
		FString Text;
		int32 Shown = 0;
		for (const FWerkNodeOutcome& O : Outcomes)
		{
			if (Shown++ >= Limit)
			{
				Text += FString::Printf(TEXT("\n... and %d more"), Outcomes.Num() - Limit);
				break;
			}
			Text += FString::Printf(TEXT("\n  %-11s %-24s %s"),
			                        FWerkNodeOutcome::OutcomeName(O.Outcome), *O.NodeId, *O.Detail);
		}
		return Text;
	}
}

void FWerkLinkModule::ExecuteImportDialog(TArray<FString> SelectedPaths)
{
	if (SelectedPaths.Num() == 0)
	{
		return;
	}

	IDesktopPlatform* Desktop = FDesktopPlatformModule::Get();
	if (!Desktop)
	{
		return;
	}

	TArray<FString> Chosen;
	const bool bPicked = Desktop->OpenFileDialog(
		FSlateApplication::Get().FindBestParentWindowHandleForDialogs(nullptr),
		TEXT("Choose a .werk container"), FPaths::ProjectDir(), TEXT(""),
		TEXT("werk container (*.werk)|*.werk"), EFileDialogFlags::None, Chosen);

	if (!bPicked || Chosen.Num() == 0)
	{
		return;
	}

	const UWerkLinkSettings* Settings = GetDefault<UWerkLinkSettings>();

	FWerkImportRequest Request;
	Request.WerkFilePath = FPaths::ConvertRelativePathToFull(Chosen[0]);
	Request.DestinationPath = SelectedPaths[0];
	Request.bImportAudio = Settings->bImportAudio;
	Request.bImportCollision = Settings->bImportCollision;
	Request.bImportSemanticTags = Settings->bImportSemanticTags;
	Request.MasterMaterial = Settings->MasterMaterial;
	// GUI default: leave the packages dirty so the user can look before saving.
	Request.bSavePackages = false;

	const FWerkImportResult Result = FWerkLinkAction::Import(Request);

	FString Message;
	if (!Result.bSuccess)
	{
		Message = FString::Printf(TEXT("Import failed: %s"), *Result.ErrorMessage);
	}
	else
	{
		Message = FString::Printf(TEXT("%s\n\n%s\n\nPer node:%s"), *Result.EntityName,
		                          *Result.Summary(), *FormatOutcomes(Result.Outcomes));
	}
	FMessageDialog::Open(EAppMsgType::Ok, FText::FromString(Message));
}

void FWerkLinkModule::ExecuteExportDialog(TArray<FString> SelectedAssetPaths)
{
	if (SelectedAssetPaths.Num() == 0)
	{
		return;
	}

	FString EnvError;
	if (!FWerkLinkAction::AssertExportEnvironment(EnvError))
	{
		FMessageDialog::Open(EAppMsgType::Ok, FText::FromString(EnvError));
		return;
	}

	IDesktopPlatform* Desktop = FDesktopPlatformModule::Get();
	if (!Desktop)
	{
		return;
	}

	TArray<FString> Chosen;
	const bool bPicked = Desktop->SaveFileDialog(
		FSlateApplication::Get().FindBestParentWindowHandleForDialogs(nullptr),
		TEXT("Write a .werk container"), FPaths::ProjectDir(), TEXT("entity.werk"),
		TEXT("werk container (*.werk)|*.werk"), EFileDialogFlags::None, Chosen);

	if (!bPicked || Chosen.Num() == 0)
	{
		return;
	}

	const UWerkLinkSettings* Settings = GetDefault<UWerkLinkSettings>();

	FWerkExportRequest Request;
	Request.RootAssetPaths = SelectedAssetPaths;
	Request.OutputFilePath = FPaths::ConvertRelativePathToFull(Chosen[0]);
	Request.SpecSourceDirectory = Settings->SpecSourceDirectory.Path;
	Request.ProducerTool = Settings->ProducerTool;
	Request.bFailOnUnresolvableExternalReference =
		Settings->bFailOnUnresolvableExternalReference;

	const FWerkExportResult Result = FWerkLinkAction::Export(Request);

	FString Message;
	if (!Result.bSuccess)
	{
		Message = FString::Printf(TEXT("Export failed: %s"), *Result.ErrorMessage);
	}
	else
	{
		Message = FString::Printf(TEXT("Wrote %s\n\n%s\n\nPer node:%s"), *Result.OutputFilePath,
		                          *Result.Summary(), *FormatOutcomes(Result.Outcomes));
	}
	FMessageDialog::Open(EAppMsgType::Ok, FText::FromString(Message));
}

#undef LOCTEXT_NAMESPACE
