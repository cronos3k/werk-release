# run_extendscript.ps1 -- launch an Adobe host through COM, run
# extendscript_smoke.jsx inside it, print the result line, quit the host.
#   powershell -File js/tests/run_extendscript.ps1 -ProgId Photoshop.Application.180 -Expect <sha256>
# Photoshop.Application.180 is Photoshop 2024 on this machine (the bare
# Photoshop.Application ProgID is registered to Photoshop 2020).
param([string]$ProgId = "Photoshop.Application.180", [string]$Expect = "", [switch]$KeepOpen)
$libs = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path -replace '\\', '/'
$smoke = (Join-Path $PSScriptRoot "extendscript_smoke.jsx") -replace '\\', '/'
$before = @(Get-Process | Where-Object { $_.ProcessName -eq "Photoshop" } | ForEach-Object { $_.Id })
$app = New-Object -ComObject $ProgId
$code = "var WERK_T = '$libs'; var WERK_EXPECT = '$Expect'; `$.evalFile(new File('$smoke'));"
$sw = [Diagnostics.Stopwatch]::StartNew()
$result = $app.DoJavaScript($code)
$sw.Stop()
Write-Output "host=$ProgId total_ms=$($sw.ElapsedMilliseconds) $result"
if (-not $KeepOpen) {
  $after = @(Get-Process | Where-Object { $_.ProcessName -eq "Photoshop" } | ForEach-Object { $_.Id })
  $mine = @($after | Where-Object { $before -notcontains $_ })
  if ($mine.Count -gt 0) { $app.Quit(); Write-Output "quit the host this script started (pid $($mine -join ','))" }
  else { Write-Output "the host was already running before this script; left it open" }
}
