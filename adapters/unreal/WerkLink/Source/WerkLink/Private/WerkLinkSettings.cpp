#include "WerkLinkSettings.h"

#include "WerkMaterialSlots.h"

UWerkLinkSettings::UWerkLinkSettings()
{
	ImportRootPath = TEXT("/Game/Werk");
	ProducerTool = TEXT("werklink");

	// Stage 10 shipped with NO default master, on the ground that pointing at
	// an /Engine/ material would produce instances that look right and are not:
	// the werk core.material node is the authority (SPEC.md 10.2), and binding
	// its parameters to a master that has none of them discards every one.
	//
	// That argument is still correct, and Stage 10B answers it rather than
	// working around it: the plugin now SHIPS a master whose parameter names
	// are the ones WerkMaterialSlots.h declares, so the default binds
	// everything the schema can express. `CanContainContent` is true in the
	// .uplugin for exactly this one asset.
	//
	// A project may still point this at its own master. Every parameter is
	// offered and every unbound one is reported, so a foreign master degrades
	// visibly rather than silently.
	MasterMaterial = FSoftObjectPath(WERKLINK_DEFAULT_MASTER);
}
