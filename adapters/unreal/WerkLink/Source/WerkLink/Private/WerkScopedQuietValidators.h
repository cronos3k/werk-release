#pragma once

// Findings B5 -- and read that entry before trusting this file.
//
// An internal note describes `FScopedDisableNoisyValidators` in an earlier
// private plugin: an RAII CDO-flipper
// that silences validators during batch saves, because the Localization
// validator opens a MODAL in UE 5.7 and a modal in a commandlet is a hang with
// no timeout.
//
// That revision is not on this machine. What follows is a reconstruction from
// a one-line description, not a transcription, and the exact validator set is
// a guess. It is written so that being wrong is cheap: it finds nothing, and
// does nothing, rather than misfiring.
//
// TWO THINGS WERE CHECKED IN THE 5.7 HEADERS AND SHAPED THIS FILE:
//
//  1. `UEditorValidatorBase` lives in the DataValidation PLUGIN
//     (Engine/Plugins/Editor/DataValidation), not in the engine proper. A
//     compile-time dependency on it would make WerkLink refuse to build in a
//     project where that plugin is off.
//  2. `bIsEnabled` is `protected` and there is no `SetIsEnabled`
//     (EditorValidatorBase.h:96 and :138). `IsEnabled()` is a getter and a
//     virtual, not a switch.
//
// So this uses reflection: it looks the class up by name at runtime, finds the
// `bIsEnabled` FBoolProperty on the CDO, flips it, and restores it. No plugin
// dependency, no access to a protected member, and a clean no-op when the
// DataValidation plugin is not loaded -- which is the common case and must not
// be an error.

#include "CoreMinimal.h"
#include "UObject/UnrealType.h"
#include "UObject/UObjectIterator.h"

/**
 * Disables editor validators whose class name contains the given substring,
 * for the lifetime of the scope, and restores exactly the ones it disabled.
 *
 * Deliberately NOT a blanket "disable all validation": the call site names the
 * noise it is silencing, so a reader can see the answer is "the localization
 * one" rather than "all of them".
 */
class FWerkScopedQuietValidators
{
public:
	explicit FWerkScopedQuietValidators(const TCHAR* ClassNameSubstring = TEXT("Localization"))
	{
#if WITH_EDITOR
		UClass* ValidatorBase = FindObject<UClass>(nullptr, TEXT("/Script/DataValidation.EditorValidatorBase"));
		if (!ValidatorBase)
		{
			// The DataValidation plugin is not loaded. Nothing to silence,
			// and that is not a failure.
			return;
		}

		for (TObjectIterator<UClass> It; It; ++It)
		{
			UClass* Class = *It;
			if (!Class || Class == ValidatorBase || !Class->IsChildOf(ValidatorBase))
			{
				continue;
			}
			if (Class->HasAnyClassFlags(CLASS_Abstract | CLASS_Deprecated | CLASS_NewerVersionExists))
			{
				continue;
			}
			if (ClassNameSubstring && *ClassNameSubstring
				&& !Class->GetName().Contains(ClassNameSubstring))
			{
				continue;
			}

			UObject* Cdo = Class->GetDefaultObject();
			if (!Cdo)
			{
				continue;
			}
			FBoolProperty* Prop = FindFProperty<FBoolProperty>(Class, TEXT("bIsEnabled"));
			if (!Prop)
			{
				continue;
			}
			void* Addr = Prop->ContainerPtrToValuePtr<void>(Cdo);
			if (!Prop->GetPropertyValue(Addr))
			{
				continue; // already off; leave it that way on the way out
			}
			Prop->SetPropertyValue(Addr, false);
			Restore.Add({ Cdo, Prop });
		}
#else
		(void)ClassNameSubstring;
#endif
	}

	~FWerkScopedQuietValidators()
	{
#if WITH_EDITOR
		for (FEntry& E : Restore)
		{
			if (UObject* Cdo = E.Cdo.Get())
			{
				E.Prop->SetPropertyValue(E.Prop->ContainerPtrToValuePtr<void>(Cdo), true);
			}
		}
#endif
		Restore.Reset();
	}

	FWerkScopedQuietValidators(const FWerkScopedQuietValidators&) = delete;
	FWerkScopedQuietValidators& operator=(const FWerkScopedQuietValidators&) = delete;

	/** How many validators this scope actually silenced. Zero is normal. */
	int32 Num() const { return Restore.Num(); }

private:
	struct FEntry
	{
		TWeakObjectPtr<UObject> Cdo;
		FBoolProperty*          Prop = nullptr;
	};
	TArray<FEntry> Restore;
};
