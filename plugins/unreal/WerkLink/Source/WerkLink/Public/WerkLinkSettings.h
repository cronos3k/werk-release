#pragma once

#include "CoreMinimal.h"
#include "Engine/DeveloperSettings.h"
#include "Engine/EngineTypes.h"

#include "WerkLinkSettings.generated.h"

/**
 * Project settings for WerkLink.
 *
 * Registration follows the content mover (findings A3): GetModulePtr rather
 * than LoadModuleChecked for the Settings module, because settings may
 * legitimately not exist in a commandlet, and any runtime mutation is followed
 * by an explicit SaveConfig().
 *
 * The defaults here are the GUI defaults. The commandlet deliberately uses a
 * DIFFERENT set -- findings B8: fixup defaults OFF headless, because a
 * Blueprint recompile crashes on pre-broken marketplace content, and ON in the
 * editor where a human is watching. That asymmetry is documented in
 * plugins/unreal/README.md rather than left as a surprise.
 */
UCLASS(Config = EditorPerProjectUserSettings, DefaultConfig, meta = (DisplayName = "WerkLink"))
class WERKLINK_API UWerkLinkSettings : public UDeveloperSettings
{
	GENERATED_BODY()

public:
	UWerkLinkSettings();

	/** Content path imported packages are written under, e.g. /Game/Werk. */
	UPROPERTY(EditAnywhere, Config, Category = "Import")
	FString ImportRootPath;

	/**
	 * Parent material for imported core.material nodes. WerkLink ships no
	 * .uasset of its own (it is a source-only plugin), so the master is a
	 * setting. Only parameters that actually exist on the chosen master are
	 * bound; every parameter that could not be bound is reported as a
	 * substituted-fallback rather than silently dropped.
	 */
	UPROPERTY(EditAnywhere, Config, Category = "Import", meta = (AllowedClasses = "/Script/Engine.MaterialInterface"))
	FSoftObjectPath MasterMaterial;

	/** Import core.phys.colliders as simple collision on the static mesh. */
	UPROPERTY(EditAnywhere, Config, Category = "Import")
	bool bImportCollision = true;

	/** Import core.audio.* WAV payloads as USoundWave assets. */
	UPROPERTY(EditAnywhere, Config, Category = "Import")
	bool bImportAudio = true;

	/**
	 * Write core.semantics tags into the asset registry as asset tags, so a
	 * Content Browser filter can find them.
	 */
	UPROPERTY(EditAnywhere, Config, Category = "Import")
	bool bImportSemanticTags = true;

	/**
	 * Fix up referencers after an import relocates anything. GUI default ON,
	 * commandlet default OFF -- see the class comment and findings B8.
	 */
	UPROPERTY(EditAnywhere, Config, Category = "Import")
	bool bFixupReferencers = true;

	/**
	 * Directory holding the spec/ and loaders/ trees to embed in exported
	 * packages. Law 2 says the format travels with the file, so an export
	 * without this is NOT redistributable-conformant and says so in its
	 * report. Point it at the werk repository root.
	 */
	UPROPERTY(EditAnywhere, Config, Category = "Export", meta = (RelativeToGameContentDir))
	FDirectoryPath SpecSourceDirectory;

	/** Producer tool string stamped into every exported node version. */
	UPROPERTY(EditAnywhere, Config, Category = "Export")
	FString ProducerTool;

	/**
	 * Refuse to export when a dependency resolves outside the closure and
	 * cannot be baked -- the hermetic rule. When false the reference is
	 * substituted with a declared fallback and a work note says so. It is
	 * never silently dropped either way.
	 */
	UPROPERTY(EditAnywhere, Config, Category = "Export")
	bool bFailOnUnresolvableExternalReference = false;

	virtual FName GetContainerName() const override { return TEXT("Project"); }
	virtual FName GetCategoryName() const override { return TEXT("Plugins"); }
	virtual FName GetSectionName() const override { return TEXT("WerkLink"); }

#if WITH_EDITOR
	virtual FText GetSectionText() const override
	{
		return NSLOCTEXT("WerkLink", "SettingsSection", "WerkLink");
	}
	virtual FText GetSectionDescription() const override
	{
		return NSLOCTEXT("WerkLink", "SettingsDesc",
			"Import and export werk artifact containers.");
	}
#endif
};
