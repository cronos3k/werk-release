#!/bin/sh
# Rebuild WerkLink for UE 5.8 (RunUAT BuildPlugin), install the build into the gate project
# (a copy, never a junction), and run tests/gate.py. Log: _gate_out/build.log, stdout = the gate.
set -e
P=$(cd "$(dirname "$0")/.." && pwd)
W=$(cygpath -w "$P" 2>/dev/null || echo "$P")
REPO=${WERK_REPO:-$(cd "$P/../.." && pwd)}
LIBS=${WERK_LIBS:-$REPO/libs}
rm -rf "$P/_build/pkg"
powershell -NoProfile -Command "& 'C:\Program Files\Epic Games\UE_5.8\Engine\Build\BatchFiles\RunUAT.bat' BuildPlugin '-Plugin=$W\WerkLink\WerkLink.uplugin' '-Package=$W\_build\pkg' -TargetPlatforms=Win64 -Rocket *> '$W\_build\build.log'; exit \$LASTEXITCODE"
rm -rf "$P/project/WerkGate/Plugins/WerkLink"
mkdir -p "$P/project/WerkGate/Plugins"
cp -r "$P/_build/pkg" "$P/project/WerkGate/Plugins/WerkLink"
rm -rf "$P/project/WerkGate/Plugins/WerkLink/HostProject"
cd "$P" && py -3.12 -u tests/gate.py --repo "$REPO" --libs "$LIBS"
