@echo off
rem WerkLink standalone gate: compile the engine-free core with local MSVC.
rem
rem Locates the C++ toolchain through vswhere rather than assuming a path, so
rem this runs on any box with Build Tools or a full Visual Studio.
rem
rem Usage (from anywhere; the script finds the repository root itself):
rem   adapters\unreal\tests\build_gate.bat
rem   adapters\unreal\tests\.build\werk_gate.exe fixtures\crate-v1.werk fixtures\crate-v1-damaged.werk

setlocal enabledelayedexpansion

set "REPO=%~dp0..\..\.."
pushd "%REPO%"

set "OUT=adapters\unreal\tests\.build"
if not exist "%OUT%" mkdir "%OUT%"

set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE%" (
    echo ERROR: vswhere.exe not found; no Visual Studio installation to locate.
    popd & exit /b 2
)

rem Via a file rather than `for /f`: both the vswhere path and the value it
rem prints contain spaces AND parentheses ("Program Files (x86)"), and every
rem quoting form that survives one of those breaks on the other.
"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath > "%OUT%\vspath.txt"
set /p VSPATH=<"%OUT%\vspath.txt"
if "%VSPATH%"=="" (
    echo ERROR: no Visual Studio installation with the x64 C++ toolchain.
    popd & exit /b 2
)

call "%VSPATH%\VC\Auxiliary\Build\vcvars64.bat" >nul 2>nul
if errorlevel 1 (
    echo ERROR: vcvars64.bat failed.
    popd & exit /b 2
)

set "SRC=adapters\unreal\WerkLink\Source\WerkLink\Private\Core"

cl /nologo /std:c++17 /EHsc /W4 /WX /O2 /MD ^
   /Fo"%OUT%\\" /Fe"%OUT%\werk_gate.exe" ^
   adapters\unreal\tests\werk_gate_main.cpp ^
   "%SRC%\werk_basis.cpp" ^
   "%SRC%\werk_sha256.cpp" ^
   "%SRC%\werk_zip.cpp" ^
   "%SRC%\werk_json.cpp" ^
   "%SRC%\werk_glb.cpp" ^
   "%SRC%\werk_manifest.cpp"

if errorlevel 1 (
    echo BUILD FAILED
    popd & exit /b 1
)

echo Built %OUT%\werk_gate.exe
popd
endlocal
