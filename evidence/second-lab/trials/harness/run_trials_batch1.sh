#!/usr/bin/env bash
# Fresh-agent gauntlet trials on mini-v1.werk (second lab).
# Protocol (gauntlet/roundOW): one fresh directory per trial, outside every
# werk repo, holding ONLY the fixture; the prompt is the committed task text,
# unchanged; wall clock is measured here, never self-reported.
# Agents get file tools and python only. They do not get web access.
#
# Run from Git Bash:   bash <second-lab>/werk/run_trials.sh
set -u
CLAUDE="C:/Users/<user>/.local/bin/claude.exe"
REPO=<repo>
FIX=$REPO/gauntlet/roundOW/mini-v1.werk
BASE=/c/Users/<user>/AppData/Local/Temp/gauntlet-trials-$(date +%Y%m%d)
mkdir -p "$BASE"
"$CLAUDE" --version > "$BASE/CLAUDE-VERSION.txt" 2>&1
sha256sum "$FIX" > "$BASE/FIXTURE-SHA256.txt"

run_trial () {
  local name=$1 promptfile=$2
  local dir=$BASE/$name
  rm -rf "$dir"; mkdir -p "$dir"
  cp "$FIX" "$dir/mini-v1.werk"
  local prompt; prompt=$(cat "$promptfile")
  echo "=== $name start $(date -u +%FT%TZ)"
  local t0 t1
  t0=$(date +%s.%N)
  ( cd "$dir" && "$CLAUDE" -p "$prompt" \
      --allowedTools "Write" "Edit" "Read" "Glob" "Grep" \
                     "Bash(python:*)" "Bash(py:*)" "Bash(ls:*)" \
      --output-format json \
      > claude-result.json 2> claude-stderr.log )
  local rc=$?
  t1=$(date +%s.%N)
  awk -v n="$name" -v rc="$rc" -v a="$t0" -v b="$t1" \
      'BEGIN { printf "%s rc=%s elapsed=%.1f s\n", n, rc, b - a }' \
      | tee "$dir/TIMING.txt" | tee -a "$BASE/TIMINGS.txt"
}

run_trial r1-t1  "$REPO/gauntlet/roundOW/PROMPT-round1task-mini.txt"
run_trial r1-t2  "$REPO/gauntlet/roundOW/PROMPT-round1task-mini.txt"
run_trial r1-t3  "$REPO/gauntlet/roundOW/PROMPT-round1task-mini.txt"
run_trial env-t1 "$REPO/gauntlet/roundOW/PROMPT-envelopetask-mini.txt"
echo "=== all trials done $(date -u +%FT%TZ). Results in $BASE"
