#!/usr/bin/env bash
# roundNC (negative control) sealed trial runner.
#
# Modeled on D:\werk\run_trials_sealed.sh (batch 2 of the sealed lab). Same seal:
#  - CLAUDE_CONFIG_DIR is the dedicated, already logged-in config folder
#    D:/gauntlet-sealed/config, so the user's CLAUDE.md, plugins and settings
#    do not load.
#  - Per-trial settings (kept OUTSIDE the trial folder) turn on
#    blockReadsOutsideWorkingDirectories and deny file tools on C:\, on the
#    werk repos, on the config folder, on the settings folders, on
#    _interrupted, on every sibling trial and every other batch folder, on
#    D:/build (the fixture build folder) and on the repo's gauntlet/roundNC
#    (expectations.json lives there).
#  - --strict-mcp-config (no MCP servers) and
#    --exclude-dynamic-system-prompt-sections.
#  - A seal check runs first and aborts the batch if the agent can read the
#    user's CLAUDE.md, the roundNC expectations or D:/build.
#  - Before each agent starts, grade_nc.py --echo-check scans its workspace.
#    Any leak aborts THAT trial (it is not launched).
# Not fixable on native Windows: Bash/python run unsandboxed, so isolation of
# python file access still rests on the transcript audit.
#
# Trial matrix (pre-registered, PREREGISTRATION.md): 12 trials, interleaved
#   werk-t1 fbx-t1 gltf-t1 usdz-t1  werk-t2 ...  usdz-t3
# Prompts: prompts/texture/PROMPT-<format>.txt (PROMPT-werk.txt is the verbatim
# roundOW mini prompt, "one sound"). Workspace = fixture file(s) + PROMPT.txt.
#
# Run from PowerShell:
#   & "C:\Program Files\Git\bin\bash.exe" /d/werk/werk/gauntlet/roundNC/run_nc_trials.sh
# Resume an interrupted batch (same stamp; finished trials are skipped,
# an unfinished trial folder is moved to _interrupted and run again):
#   & "C:\Program Files\Git\bin\bash.exe" -c "RESUME=20261007-1500 /d/werk/werk/gauntlet/roundNC/run_nc_trials.sh"
#
# Test hooks (dry test only): CLAUDE=<stub> SEAL=<temp dir> TRIALS_ONLY="werk-t1 fbx-t1"
set -u

CLAUDE=${CLAUDE:-C:/Users/yuvra/.local/bin/claude.exe}
REPO=$(cygpath -u "${REPO:-/d/werk/werk}")
NC=$REPO/gauntlet/roundNC
SEAL=$(cygpath -u "${SEAL:-/d/gauntlet-sealed}")
CONFIG=$SEAL/config
PY=${PY:-py -3.13}
STAMP=${RESUME:-$(date +%Y%m%d-%H%M)}
RUNNAME=nc-$STAMP
RUN=$SEAL/$RUNNAME
SETDIR=$SEAL/settings-$RUNNAME
mkdir -p "$CONFIG" "$RUN" "$SETDIR" "$RUN/_echo" "$SEAL/_interrupted"
export CLAUDE_CONFIG_DIR="$(cygpath -m "$CONFIG")"

# Windows paths are written as //c/... and //d/... in permission rules.
rule () { local m; m=$(cygpath -m "$1"); m=${m%/}; local d=${m:0:1}; echo "//${d,,}${m:2}"; }  # /d/x or D:/x -> //d/x
winp () { cygpath -m "$1"; }       # /d/x -> D:/x
R_SEAL=$(rule "$SEAL")
R_RUN=$(rule "$RUN")

ALL_TRIALS="werk-t1 fbx-t1 gltf-t1 usdz-t1 werk-t2 fbx-t2 gltf-t2 usdz-t2 werk-t3 fbx-t3 gltf-t3 usdz-t3"
TRIALS=${TRIALS_ONLY:-$ALL_TRIALS}
NAMES="seal-check $ALL_TRIALS"

# ---- pinned bytes (PREREGISTRATION.md). Any mismatch aborts the batch. -------
PIN_WERK=f7bdcc853009504b1d31b2934a7a8294cbf0e6f227c95f7de1e81af0947e9837
PIN_FBX=ca28bbe959e14dc54ed40f29e1ce2f12530fc46f15976681e7bece9d626816ef
PIN_GLTF=3f9a6a472de5a08573b4fa1cf4c3de53fffa03ec2c3fdb5b8a2d89c5bb919f69
PIN_BIN=02148a5ba343d0d1eba4664be44416db5594c8a2147f61067c0ef5af010630ab
PIN_PNG=af85a84d80b8fee7bf413a5edc2e722f4442df09a5d2d064d8b16dfb0a51ec1f
PIN_USDZ=14cd873a32574a7fd30f9b3599b64ca128ff105ef992329a74794ecdedd806b7
PIN_P_WERK=397aba804e83938068eb2967b32f961253a031cdecb694e8b8aa4129760119d4
PIN_P_FBX=c82c5ff6cf7a8f545b91b48aee6d83f11afbb71e5b6a51f7f8d5424c93297988
PIN_P_GLTF=3bfec5fe499f3db6b6bc1c9fc6841dd303148f924bfe934e2620a24230d244a9
PIN_P_USDZ=b68cbea04eb7d52ddd23f20949b6ff10dcc26383f4b83a9d02e1f4cc8984ec93

# the bytes the round ran on (mini-v1.werk was rebuilt under the ruling on #11)
F_WERK=$REPO/gauntlet/roundOW/historical/mini-v1-f7bdcc85.werk
F_FBX=$NC/crate-nc-v1.fbx
F_GLTF=$NC/crate-nc-v1.gltf
F_BIN=$NC/crate-nc-v1.bin
F_PNG=$NC/crate_diffuse.png
F_USDZ=$NC/crate-nc-v1.usdz

pin_ok=1
check_pin () {  # $1=file $2=sha256
  local got; got=$(sha256sum "$1" | cut -d' ' -f1)
  echo "$got  $1" >> "$RUN/FIXTURE-SHA256.txt"
  if [ "$got" != "$2" ]; then echo "PIN MISMATCH: $1 is $got, pinned $2"; pin_ok=0; fi
}
: > "$RUN/FIXTURE-SHA256.txt"
check_pin "$F_WERK" $PIN_WERK
check_pin "$F_FBX" $PIN_FBX
check_pin "$F_GLTF" $PIN_GLTF
check_pin "$F_BIN" $PIN_BIN
check_pin "$F_PNG" $PIN_PNG
check_pin "$F_USDZ" $PIN_USDZ
check_pin "$NC/prompts/texture/PROMPT-werk.txt" $PIN_P_WERK
check_pin "$NC/prompts/texture/PROMPT-fbx.txt" $PIN_P_FBX
check_pin "$NC/prompts/texture/PROMPT-gltf.txt" $PIN_P_GLTF
check_pin "$NC/prompts/texture/PROMPT-usdz.txt" $PIN_P_USDZ
if [ $pin_ok -ne 1 ]; then
  echo "Fixture or prompt bytes differ from the pre-registration. Aborting; no trials were run."
  exit 1
fi
cmp -s "$NC/prompts/texture/PROMPT-werk.txt" "$REPO/gauntlet/roundOW/PROMPT-round1task-mini.txt" \
  || { echo "werk prompt is not byte-identical to roundOW/PROMPT-round1task-mini.txt. Aborting."; exit 1; }
"$CLAUDE" --version >> "$RUN/CLAUDE-VERSION.txt" 2>&1
( cd "$REPO" && git rev-parse HEAD && git status --porcelain --untracked-files=no ) > "$RUN/REPO-STATE.txt" 2>&1

make_settings () {  # $1 = this trial's name
  local me=$1 others="" t d
  for t in $NAMES; do
    [ "$t" = "$me" ] && continue
    others="$others \"Read($R_RUN/$t/**)\", \"Glob($R_RUN/$t/**)\", \"Grep($R_RUN/$t/**)\","
  done
  # every other batch folder on the seal drive (earlier rounds' agent output)
  for d in "$SEAL"/*/; do
    d=${d%/}
    case "$(basename "$d")" in
      "$RUNNAME"|config|_interrupted|settings-*) continue ;;
    esac
    others="$others \"Read($(rule "$d")/**)\", \"Glob($(rule "$d")/**)\", \"Grep($(rule "$d")/**)\","
  done
  cat > "$SETDIR/$me.json" <<EOF
{
  "permissions": {
    "blockReadsOutsideWorkingDirectories": true,
    "deny": [ $others
      "Read($R_RUN/_echo/**)", "Glob($R_RUN/_echo/**)", "Grep($R_RUN/_echo/**)",
      "Read(//c/**)", "Glob(//c/**)", "Grep(//c/**)", "Edit(//c/**)", "Write(//c/**)",
      "Read(//d/werk/**)", "Glob(//d/werk/**)", "Grep(//d/werk/**)", "Edit(//d/werk/**)", "Write(//d/werk/**)",
      "Read(//d/werk/werk/gauntlet/roundNC/**)", "Glob(//d/werk/werk/gauntlet/roundNC/**)", "Grep(//d/werk/werk/gauntlet/roundNC/**)",
      "Read(//d/werk-gregor-fix/**)", "Glob(//d/werk-gregor-fix/**)", "Grep(//d/werk-gregor-fix/**)",
      "Read(//d/build/**)", "Glob(//d/build/**)", "Grep(//d/build/**)", "Edit(//d/build/**)", "Write(//d/build/**)",
      "Read($R_SEAL/config/**)", "Glob($R_SEAL/config/**)", "Grep($R_SEAL/config/**)",
      "Read($R_SEAL/settings-*/**)", "Glob($R_SEAL/settings-*/**)", "Grep($R_SEAL/settings-*/**)",
      "Read($R_SEAL/_interrupted/**)", "Glob($R_SEAL/_interrupted/**)", "Grep($R_SEAL/_interrupted/**)",
      "WebFetch", "WebSearch"
    ]
  }
}
EOF
}

# $1=name $2=format (werk|fbx|gltf|usdz|-) $3=prompt file ("-" = inline text in $4) $4.. = files to copy in
FAILED=""
run_agent () {
  local name=$1 fmt=$2 pfile=$3; shift 3
  local dir=$RUN/$name prompt
  if [ -f "$dir/_harness/TIMING.txt" ] && grep -q "rc=0" "$dir/_harness/TIMING.txt"; then
    echo "=== $name already finished, skipping: $(cat "$dir/_harness/TIMING.txt")"
    return 0
  fi
  # An interrupted trial is discarded and run again from a clean folder.
  [ -d "$dir" ] && mv "$dir" "$SEAL/_interrupted/$RUNNAME-$name-$(date +%H%M%S)"
  mkdir -p "$dir"
  if [ "$pfile" = "-" ]; then
    prompt=$1; shift
  else
    cp "$pfile" "$dir/PROMPT.txt"
    prompt=$(cat "$dir/PROMPT.txt")
    local f; for f in "$@"; do case "$f" in *mini-v1-f7bdcc85.werk) cp "$f" "$dir/mini-v1.werk" ;; *) cp "$f" "$dir/" ;; esac; done
    # echo rule: no expected hash value may sit in the workspace
    $PY "$NC/grade_nc.py" --format "$fmt" --echo-check "$(winp "$dir")" \
        --json "$(winp "$RUN/_echo/$name.json")" > "$RUN/_echo/$name.log" 2>&1
    if ! grep -q '"result": "PASS"' "$RUN/_echo/$name.json" 2>/dev/null; then
      echo "ECHO CHECK FAILED for $name (see $RUN/_echo/$name.log). Trial NOT launched."
      echo "$name ECHO-FAIL" >> "$RUN/TIMINGS.txt"
      FAILED="$FAILED $name"
      return 1
    fi
    echo "--- $name echo check PASS: $(ls "$dir" | tr '\n' ' ')"
  fi
  make_settings "$name"
  echo "=== $name start $(date -u +%FT%TZ)"
  local t0 t1 rc
  t0=$(date +%s.%N)
  ( cd "$dir" && "$CLAUDE" -p "$prompt" \
      --settings "$(winp "$SETDIR")/$name.json" \
      --strict-mcp-config \
      --exclude-dynamic-system-prompt-sections \
      --allowedTools "Write" "Edit" "Read" "Glob" "Grep" \
                     "Bash(python:*)" "Bash(py:*)" "Bash(ls:*)" \
      --output-format json \
      > _agent-stdout.txt 2> _agent-stderr.txt )
  rc=$?
  t1=$(date +%s.%N)
  mkdir -p "$dir/_harness"
  awk -v n="$name" -v rc="$rc" -v a="$t0" -v b="$t1" \
      'BEGIN { printf "%s rc=%s elapsed=%.1f s\n", n, rc, b - a }' \
      | tee "$dir/_harness/TIMING.txt" | tee -a "$RUN/TIMINGS.txt"
  [ "$rc" = 0 ] || FAILED="$FAILED $name"
}

# --- 1. seal check: must NOT read CLAUDE.md, the expectations, or D:/build ---
run_agent seal-check - - "Use only your Read and Glob tools (no Bash). Try to read the file C:/Users/yuvra/.claude/CLAUDE.md, then try to read D:/werk/werk/gauntlet/roundNC/expectations.json, then try to list D:/build and D:/gauntlet-sealed. Report exactly what each tool returned. If you could see any file content, quote its first line."
SR=$RUN/seal-check/_agent-stdout.txt
if grep -r -q "ASD-STE100" "$CONFIG/projects" 2>/dev/null \
   || grep -q -e "ASD-STE100" -e "ground truth for grade_nc" -e "blender-args" -e "usdz-build-record" "$SR"; then
  echo "SEAL BROKEN: the agent could read CLAUDE.md, the roundNC expectations or D:/build. Aborting; no trials were run."
  exit 1
fi
if ! grep -q '"is_error":false' "$SR" && ! grep -q '"is_error": false' "$SR"; then
  echo "Seal check did not run (login or API error). Aborting. See $SR"
  exit 1
fi
echo "Seal check passed."

# --- 2. the 12 trials, interleaved so time-of-day effects are spread ---------
for t in $TRIALS; do
  case $t in
    werk-*) run_agent "$t" werk "$NC/prompts/texture/PROMPT-werk.txt" "$F_WERK" ;;
    fbx-*)  run_agent "$t" fbx  "$NC/prompts/texture/PROMPT-fbx.txt"  "$F_FBX" ;;
    gltf-*) run_agent "$t" gltf "$NC/prompts/texture/PROMPT-gltf.txt" "$F_GLTF" "$F_BIN" "$F_PNG" ;;
    usdz-*) run_agent "$t" usdz "$NC/prompts/texture/PROMPT-usdz.txt" "$F_USDZ" ;;
    *) echo "unknown trial $t"; FAILED="$FAILED $t" ;;
  esac
done

echo "=== all trials done $(date -u +%FT%TZ). Results in $RUN"
if [ -n "$FAILED" ]; then
  echo "NOT CLEAN:$FAILED (rerun with RESUME=$STAMP to retry these)"
  exit 1
fi
