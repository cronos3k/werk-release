#!/usr/bin/env bash
# roundSR second arm -- Moonshot Kimi Code CLI, same task, same isolation.
#   bash gauntlet/roundSR/run_kimi.sh <run-dir> <out-prefix>
set -u
RUNDIR="$1"
OUT="$2"
PROMPT="$(cat "$(dirname "$0")/PROMPT-selfruntask.txt")"

cd "$RUNDIR/workspace" || exit 2
START=$(date +%s.%N)
timeout 2700 kimi -p "$PROMPT" --output-format stream-json \
    > "$OUT.jsonl" 2> "$OUT.stderr"
RC=$?
END=$(date +%s.%N)
echo "exit_code=$RC" > "$OUT.meta"
echo "wall_seconds=$(python -c "print(round($END-$START,1))")" >> "$OUT.meta"
cat "$OUT.meta"
