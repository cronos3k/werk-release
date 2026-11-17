#!/usr/bin/env bash
# Sealed fresh-agent gauntlet trials (second lab), batch 2.
#
# Changes from run_trials.sh (batch 1), each fixing a batch-1 audit finding:
#  - Trial folders live on <second-lab>\gauntlet-sealed, away from the user profile.
#  - CLAUDE_CONFIG_DIR points to a dedicated, empty config folder, so the
#    user's CLAUDE.md, plugins and settings do not load. Log in to it once.
#  - Per-trial settings (kept OUTSIDE the trial folder) turn on
#    blockReadsOutsideWorkingDirectories and deny file tools on C:\, on the
#    werk repos, on the config folder (tool-output overflow files land there)
#    and on every other trial folder.
#  - --strict-mcp-config: no MCP servers.
#  - --exclude-dynamic-system-prompt-sections: account details move out of
#    the system prompt (Claude Code has no flag that removes them entirely).
#  - A seal check runs first and aborts the batch if the agent can read the
#    user's CLAUDE.md.
# Not fixable on native Windows: Bash/python run unsandboxed, so isolation of
# python file access still rests on the transcript audit.
#
# Run from Git Bash:   bash <second-lab>/werk/run_trials_sealed.sh
set -u
CLAUDE="C:/Users/<user>/.local/bin/claude.exe"
REPO=<repo>
SEAL=<second-lab>/gauntlet-sealed
CONFIG=$SEAL/config
# To resume an interrupted batch: RESUME=20261006-1751 bash run_trials_sealed.sh
STAMP=${RESUME:-$(date +%Y%m%d-%H%M)}
RUN=$SEAL/$STAMP
SETDIR=$SEAL/settings-$STAMP
mkdir -p "$CONFIG" "$RUN" "$SETDIR"
export CLAUDE_CONFIG_DIR="<second-lab>/gauntlet-sealed/config"

TRIALS="seal-check xv-t1 xv-t2 xv-t3 splat-t1 splat-t2 env-t2 env-t3"
RUNP="<second-lab>/gauntlet-sealed/$(basename "$RUN")"

"$CLAUDE" --version >> "$RUN/CLAUDE-VERSION.txt" 2>&1
sha256sum "$REPO/fixtures/crate-v1.werk" "$REPO/fixtures/gsplat-v1.werk" \
          "$REPO/gauntlet/roundOW/mini-v1.werk" > "$RUN/FIXTURE-SHA256.txt"

make_settings () {  # $1 = this trial's name
  local me=$1 others="" t
  for t in $TRIALS; do
    [ "$t" = "$me" ] && continue
    others="$others \"Read($RUNP/$t/**)\", \"Glob($RUNP/$t/**)\", \"Grep($RUNP/$t/**)\","
  done
  # Windows paths are written as //c/... and //d/... in permission rules.
  cat > "$SETDIR/$me.json" <<EOF
{
  "permissions": {
    "blockReadsOutsideWorkingDirectories": true,
    "deny": [ $others
      "Read(//c/**)", "Glob(//c/**)", "Grep(//c/**)", "Edit(//c/**)", "Write(//c/**)",
      "Read(/<second-lab>/werk/**)", "Glob(/<second-lab>/werk/**)", "Grep(/<second-lab>/werk/**)",
      "Read(//d/werk-gregor-fix/**)", "Glob(//d/werk-gregor-fix/**)", "Grep(//d/werk-gregor-fix/**)",
      "Read(<second-lab>/gauntlet-sealed/config/**)", "Glob(<second-lab>/gauntlet-sealed/config/**)", "Grep(<second-lab>/gauntlet-sealed/config/**)",
      "Read(<second-lab>/gauntlet-sealed/settings-*/**)", "Glob(<second-lab>/gauntlet-sealed/settings-*/**)",
      "Read(<second-lab>/gauntlet-sealed/_interrupted/**)", "Glob(<second-lab>/gauntlet-sealed/_interrupted/**)", "Grep(<second-lab>/gauntlet-sealed/_interrupted/**)",
      "WebFetch", "WebSearch"
    ]
  }
}
EOF
}

run_agent () {  # $1=name  $2=prompt text  $3..=files to copy in
  local name=$1 prompt=$2; shift 2
  local dir=$RUN/$name
  if [ -f "$dir/TIMING.txt" ] && grep -q "rc=0" "$dir/TIMING.txt"; then
    echo "=== $name already finished, skipping: $(cat "$dir/TIMING.txt")"
    return 0
  fi
  # An interrupted trial is discarded and run again from a clean folder.
  mkdir -p "$SEAL/_interrupted"
  [ -d "$dir" ] && mv "$dir" "$SEAL/_interrupted/$STAMP-$name-$(date +%H%M%S)"
  mkdir -p "$dir"
  local f; for f in "$@"; do cp "$f" "$dir/"; done
  make_settings "$name"
  echo "=== $name start $(date -u +%FT%TZ)"
  local t0 t1
  t0=$(date +%s.%N)
  ( cd "$dir" && "$CLAUDE" -p "$prompt" \
      --settings "<second-lab>/gauntlet-sealed/$(basename "$SETDIR")/$name.json" \
      --strict-mcp-config \
      --exclude-dynamic-system-prompt-sections \
      --allowedTools "Write" "Edit" "Read" "Glob" "Grep" \
                     "Bash(python:*)" "Bash(py:*)" "Bash(ls:*)" \
      --output-format json \
      > claude-result.json 2> claude-stderr.log )
  local rc=$?
  t1=$(date +%s.%N)
  awk -v n="$name" -v rc="$rc" -v a="$t0" -v b="$t1" \
      'BEGIN { printf "%s rc=%s elapsed=%.1f s\n", n, rc, b - a }' \
      | tee "$dir/TIMING.txt" | tee -a "$RUN/TIMINGS.txt"
}

# --- 1. seal check: must NOT be able to read the user's CLAUDE.md -----------
run_agent seal-check "Use only your Read and Glob tools (no Bash). Try to read the file C:/Users/<user>/.claude/CLAUDE.md, then try to list <repo>. Report exactly what each tool returned. If you could see any file content, quote its first line."
if grep -r -q "ASD-STE100" "$CONFIG/projects" 2>/dev/null \
   || grep -q "ASD-STE100" "$RUN/seal-check/claude-result.json"; then
  echo "SEAL BROKEN: the agent could read the user's CLAUDE.md. Aborting; no trials were run."
  exit 1
fi
if grep -q '"is_error":true' "$RUN/seal-check/claude-result.json"; then
  echo "Seal check did not run (login or API error). Aborting. See $RUN/seal-check/claude-result.json"
  exit 1
fi
echo "Seal check passed: the user's CLAUDE.md was not readable."

# --- 2. exact cross-vendor/run-1 task on the pinned crate-v1 (n=3) -----------
P_XV=$(cat "$REPO/gauntlet/roundXV/PROMPT-round1task.txt")
for i in 1 2 3; do run_agent xv-t$i "$P_XV" "$REPO/fixtures/crate-v1.werk"; done

# --- 3. splat task on gsplat-v1 (n=2) ----------------------------------------
P_GS=$(cat "$REPO/gauntlet/roundXV/PROMPT-gsplattask.txt")
for i in 1 2; do run_agent splat-t$i "$P_GS" "$REPO/fixtures/gsplat-v1.werk"; done

# --- 4. envelope task on mini-v1 (2 more, n=3 with batch 1) ------------------
P_ENV=$(cat "$REPO/gauntlet/roundOW/PROMPT-envelopetask-mini.txt")
for i in 2 3; do run_agent env-t$i "$P_ENV" "$REPO/gauntlet/roundOW/mini-v1.werk"; done

echo "=== all trials done $(date -u +%FT%TZ). Results in $RUN"
