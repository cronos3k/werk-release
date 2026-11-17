#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleInterface.h"
#include "Modules/ModuleManager.h"

class FWerkLinkModule : public IModuleInterface
{
public:
	virtual void StartupModule() override;
	virtual void ShutdownModule() override;

	/** Import dialog entry point, called from the folder context menu. */
	void ExecuteImportDialog(TArray<FString> SelectedPaths);
	/** Export entry point, called from the asset context menu. */
	void ExecuteExportDialog(TArray<FString> SelectedAssetPaths);

private:
	void RegisterSettings();
	void UnregisterSettings();
	void RegisterContextMenus();
	void UnregisterContextMenus();

	// Findings A2: the handle must be taken from the extender array's Last()
	// straight after adding, because there is no other way to find your own
	// extender again at shutdown.
	FDelegateHandle PathViewExtenderHandle;
	FDelegateHandle AssetViewExtenderHandle;
};
