#pragma once

// The seam between the engine-free core (Private/Core, std::string) and the
// Unreal layer (FString). Everything that crosses it crosses here, so there is
// exactly one place where a UTF-8 conversion can be wrong.
//
// werk text is UTF-8 without a BOM (MINI-SPECS 2). FString is UTF-16 on
// Windows. TCHAR_TO_UTF8 / UTF8_TO_TCHAR are the correct pair; TCHAR_TO_ANSI
// is not, and would silently mangle every non-ASCII work note in a package.

#include "CoreMinimal.h"

#include <string>
#include <vector>

#include "werk_report.h"
#include "WerkLinkAction.h"

namespace WerkBridge
{
	inline FString ToF(const std::string& S)
	{
		return FString(UTF8_TO_TCHAR(S.c_str()));
	}

	inline std::string ToStd(const FString& S)
	{
		return std::string(TCHAR_TO_UTF8(*S));
	}

	inline TArray<uint8> ToTArray(const std::vector<uint8_t>& V)
	{
		TArray<uint8> Out;
		Out.Append(V.data(), int32(V.size()));
		return Out;
	}

	inline std::vector<uint8_t> ToStdBytes(const TArray<uint8>& V)
	{
		return std::vector<uint8_t>(V.GetData(), V.GetData() + V.Num());
	}

	inline std::vector<uint8_t> ToStdBytes(const TArray64<uint8>& V)
	{
		return std::vector<uint8_t>(V.GetData(), V.GetData() + V.Num());
	}

	/** Mirrors core report entries into the facade result, preserving codes. */
	inline void MirrorReport(const werk::Report& In, TArray<FWerkReportLine>& Out)
	{
		Out.Reset();
		Out.Reserve(int32(In.All().size()));
		for (const werk::ReportEntry& E : In.All())
		{
			FWerkReportLine L;
			L.Code = ToF(E.code);
			L.Severity = FString(ANSI_TO_TCHAR(werk::SeverityName(E.severity)));
			L.Subject = ToF(E.subject);
			L.Detail = ToF(E.detail);
			Out.Add(MoveTemp(L));
		}
	}

	inline void AppendReport(const werk::Report& In, TArray<FWerkReportLine>& Out)
	{
		for (const werk::ReportEntry& E : In.All())
		{
			FWerkReportLine L;
			L.Code = ToF(E.code);
			L.Severity = FString(ANSI_TO_TCHAR(werk::SeverityName(E.severity)));
			L.Subject = ToF(E.subject);
			L.Detail = ToF(E.detail);
			Out.Add(MoveTemp(L));
		}
	}
}

DECLARE_LOG_CATEGORY_EXTERN(LogWerkLink, Log, All);
