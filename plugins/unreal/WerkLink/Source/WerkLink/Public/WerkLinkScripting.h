#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"

#include "WerkLinkScripting.generated.h"

/**
 * The Python (and Blueprint) entry point to the same static facade the
 * commandlet and the Content Browser menu call. Added for the werk release
 * (W5c) so an editor Python script -- `UnrealEditor-Cmd -run=pythonscript`, or
 * the Output Log -- can import and export without spawning a commandlet:
 *
 *     import unreal, json
 *     r = json.loads(unreal.WerkLinkScripting.import_werk("C:/x/crate.werk", "/Game/Werk", True))
 *     e = json.loads(unreal.WerkLinkScripting.export_werk("C:/x/out.werk", r["created_assets"],
 *                                                       "C:/werk", "Crate", False))
 *
 * Both return one JSON object (the result struct, outcomes and report as
 * data). `exit` is the SPEC 10.1 status the commandlet would have returned.
 */
UCLASS()
class WERKLINK_API UWerkLinkScripting : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** .werk -> UAssets under DestinationPath (a long package path such as
	 *  /Game/Werk). MasterMaterial empty = the project setting. */
	UFUNCTION(BlueprintCallable, Category = "WerkLink")
	static FString ImportWerk(const FString& WerkFile, const FString& DestinationPath,
	                          bool bSavePackages, const FString& MasterMaterial);

	/** UAssets (object paths, the closure roots) -> one unsigned .werk.
	 *  SpecSourceDirectory empty = the project setting. */
	UFUNCTION(BlueprintCallable, Category = "WerkLink")
	static FString ExportWerk(const FString& OutputFile, const TArray<FString>& RootAssetPaths,
	                          const FString& SpecSourceDirectory, const FString& EntityName,
	                          bool bHermetic);
};
