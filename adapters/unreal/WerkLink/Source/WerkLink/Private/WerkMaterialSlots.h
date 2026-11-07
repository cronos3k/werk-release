#pragma once

#include "CoreMinimal.h"

/**
 * The one table that maps a `core.material` texture slot onto the parameter
 * names WerkLink's master material exposes.
 *
 * It lives in a header shared by the importer and the exporter for exactly the
 * reason spec/SPEC.md gives for every other convention table in this project:
 * two copies of a mapping are two things that can drift, and a drift here is
 * invisible -- a roughness map bound to the wrong parameter still renders, just
 * wrongly.
 *
 * The slot names on the left are NORMATIVE: `core.material.schema.json` pins
 * them with `propertyNames.enum`, so this list is closed and adding to it is a
 * spec change, not an adapter change.
 *
 * The parameter names on the right are this adapter's own, and they are the
 * ones `WerkLink/Content/M_WerkPBR` declares. A DIFFERENT master material is
 * legal and supported: every bind is offered to the configured master and a
 * parameter it does not have is REPORTED as unbound, never silently dropped.
 */
struct FWerkMaterialSlot
{
	const TCHAR* Slot;        // werk slot name, kebab/snake as the schema spells it
	const TCHAR* TextureParam; // texture parameter on M_WerkPBR
	const TCHAR* SwitchParam;  // static switch that turns that sampler on
};

/**
 * Static switches rather than "multiply by a white default": a white default
 * is correct for base colour and WRONG for metallic-roughness (white means
 * metallic 1) and for a normal map. One mechanism that is right for every slot
 * beats six defaults that are each right for one.
 */
inline const TArray<FWerkMaterialSlot>& WerkMaterialSlots()
{
	static const TArray<FWerkMaterialSlot> Slots = {
		{ TEXT("base_color"),         TEXT("BaseColorTexture"),         TEXT("UseBaseColorTexture") },
		{ TEXT("metallic_roughness"), TEXT("MetallicRoughnessTexture"), TEXT("UseMetallicRoughnessTexture") },
		{ TEXT("normal"),             TEXT("NormalTexture"),            TEXT("UseNormalTexture") },
		{ TEXT("occlusion"),          TEXT("OcclusionTexture"),         TEXT("UseOcclusionTexture") },
		{ TEXT("emissive"),           TEXT("EmissiveTexture"),          TEXT("UseEmissiveTexture") },
		{ TEXT("height"),             TEXT("HeightTexture"),            TEXT("UseHeightTexture") },
	};
	return Slots;
}

/** The master material this plugin ships, and the reason CanContainContent is
 *  true in WerkLink.uplugin. A project may override it in the settings. */
#define WERKLINK_DEFAULT_MASTER TEXT("/WerkLink/M_WerkPBR.M_WerkPBR")
