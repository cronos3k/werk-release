#!/usr/bin/env bash
# roundSR -- one Codex run against selfrun-v1.werk in a neutral directory.
#   bash gauntlet/roundSR/run_codex.sh <run-dir> <out-prefix>
# Records process wall clock. 45 min cap, enforced by `timeout`.
set -u
RUNDIR="$1"
OUT="$2"
PROMPT="$(cat "$(dirname "$0")/PROMPT-selfruntask.txt")"

cd "$RUNDIR/workspace" || exit 2
START=$(date +%s.%N)
timeout 2700 codex exec \
    --skip-git-repo-check \
    --sandbox workspace-write \
    -c model_reasoning_effort=high \
    --json \
    "$PROMPT" > "$OUT.jsonl" 2> "$OUT.stderr"
RC=$?
END=$(date +%s.%N)
echo "exit_code=$RC" > "$OUT.meta"
echo "wall_seconds=$(python -c "print(round($END-$START,1))")" >> "$OUT.meta"
cat "$OUT.meta"
