#pragma once

#include "CoreMinimal.h"
#include "Commandlets/Commandlet.h"

#include "WerkLinkCommandlet.generated.h"

/**
 * Headless WerkLink.
 *
 *   UnrealEditor-Cmd.exe <Project.uproject> -run=WerkLink -Import=<file.werk>
 *       [-Dest=/Game/Werk] [-Master=/Game/M_Werk.M_Werk] [-DryRun] [-NoSave]
 *
 *   UnrealEditor-Cmd.exe <Project.uproject> -run=WerkLink -Export=<out.werk>
 *       -Assets=/Game/A.A,/Game/B.B [-Spec=<repo>] [-Hermetic]
 *
 *   UnrealEditor-Cmd.exe <Project.uproject> -run=WerkLink -Manifest=batch.json
 *
 * The batch manifest is a JSON array of operation objects, each with an "op"
 * of "import" or "export" and the same fields as the switches above:
 *
 *   [ { "op": "import", "file": "<repo>/fixtures/crate-v1.werk",
 *       "dest": "/Game/Werk" },
 *     { "op": "export", "file": "<out>/crate.werk",
 *       "assets": ["/Game/Werk/WoodenCrate/SM_GeomGame.SM_GeomGame"],
 *       "spec": "<repo>" } ]
 *
 * Findings A4: this class NEVER constructs a widget. Every dialog in the
 * production content mover lived in the module layer and every one of them
 * hangs a commandlet with no timeout.
 *
 * Findings B8: the destructive defaults are INVERTED here relative to the GUI.
 * Referencer fixup is off unless -Fixup is passed, because a Blueprint
 * recompile crashes on pre-broken marketplace content and a crash in a batch
 * of 261 packs costs the whole batch.
 *
 * Exit status follows SPEC.md 10.1: 0 clean, 1 at least one error entry,
 * 2 a container-scoped refusal.
 */
UCLASS()
class WERKLINK_API UWerkLinkCommandlet : public UCommandlet
{
	GENERATED_BODY()

public:
	UWerkLinkCommandlet();

	virtual int32 Main(const FString& Params) override;
};
