#pragma once

#include "CoreMinimal.h"
#include "Engine/AssetUserData.h"

#include "WerkAssetUserData.generated.h"

/**
 * The identity bridge, both directions.
 *
 * werk ids are kebab-case (`conventions.id_case`, and MINI-SPECS 2 pins the
 * regex `^[a-z0-9]+(-[a-z0-9]+)*$`). Unreal object names are not: they are
 * PascalCase by convention and, more importantly, they are not allowed to
 * contain every character a kebab-case id can, and two different werk ids can
 * sanitise to the same Unreal name.
 *
 * So the mapping is NOT computed on the way back. The original node id, the
 * entity uuid, the part and material ids and the source package path are
 * stored here at import time and read at export time. Export round-trips
 * identity because it looks the answer up rather than deriving it.
 *
 * Attached through IInterface_AssetUserData::AddAssetUserData, which
 * UStaticMesh, UTexture2D, USoundWave and UMaterialInstanceConstant all
 * implement.
 */
UCLASS()
class WERKLINK_API UWerkAssetUserData : public UAssetUserData
{
	GENERATED_BODY()

public:
	/** The werk node this asset came from, verbatim, kebab-case and all. */
	UPROPERTY(VisibleAnywhere, Category = "werk")
	FString NodeId;

	/** The werk node type, e.g. core.geom.game. */
	UPROPERTY(VisibleAnywhere, Category = "werk")
	FString NodeType;

	/** entity.uuid of the package this came from. */
	UPROPERTY(VisibleAnywhere, Category = "werk")
	FString EntityUuid;

	/** entity.name, for humans reading the details panel. */
	UPROPERTY(VisibleAnywhere, Category = "werk")
	FString EntityName;

	/** parts[].part_id this node belongs to, if any. */
	UPROPERTY(VisibleAnywhere, Category = "werk")
	FString PartId;

	/** materials[].material_id this node belongs to, if any. */
	UPROPERTY(VisibleAnywhere, Category = "werk")
	FString MaterialId;

	/** The path inside the container this asset's bytes came from. */
	UPROPERTY(VisibleAnywhere, Category = "werk")
	FString SourceFilePath;

	/** sha256 of those bytes, as the manifest declared it. */
	UPROPERTY(VisibleAnywhere, Category = "werk")
	FString SourceSha256;

	/** The node version that was resolved -- not necessarily `active`. */
	UPROPERTY(VisibleAnywhere, Category = "werk")
	int32 SourceVersion = 0;

	/** The work note of that version (law 6), carried so it is never lost. */
	UPROPERTY(VisibleAnywhere, Category = "werk")
	FString WorkNote;

	/** authored | measured | inferred, as the version declared it. */
	UPROPERTY(VisibleAnywhere, Category = "werk")
	FString Epistemic;

	/** Absolute path of the .werk this was imported from, for provenance. */
	UPROPERTY(VisibleAnywhere, Category = "werk")
	FString ImportedFrom;

	/**
	 * core.tex only: meta.usage as the manifest declared it (base-color,
	 * normal, metallic-roughness, ...). Stored for the same reason NodeId is:
	 * Unreal's own CompressionSettings can only tell a normal map from
	 * everything else, so recomputing usage on export would flatten five
	 * declared values into two guessed ones.
	 */
	UPROPERTY(VisibleAnywhere, Category = "werk")
	FString TextureUsage;

	/**
	 * core.material only: the slot -> texture node bindings this instance was
	 * built from, keyed by werk slot name (base_color, normal, ...) with the
	 * texture NODE id as the value. Export reads it back so a round trip
	 * reproduces the same bindings even for a slot whose master parameter is
	 * named something this adapter would not have guessed.
	 */
	UPROPERTY(VisibleAnywhere, Category = "werk")
	TMap<FString, FString> TextureSlotNodes;

	/** Same map, slot -> the uv_set the material JSON declared. */
	UPROPERTY(VisibleAnywhere, Category = "werk")
	TMap<FString, int32> TextureSlotUvSets;
};
