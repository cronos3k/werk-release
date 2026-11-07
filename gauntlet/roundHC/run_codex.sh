#!/usr/bin/env bash
# roundHC -- one Codex run against a directory of page photographs.
#   bash gauntlet/roundHC/run_codex.sh <run-dir> <out-prefix>
# The run directory's workspace/ holds ONLY the page images. No format hint is
# given: the prompt is PROMPT-archaeology.txt, verbatim, committed before the run.
# Records process wall clock. 60 min cap, enforced by `timeout`.
set -u
RUNDIR="$1"
OUT="$2"
PROMPT="$(cat "$(dirname "$0")/PROMPT-archaeology.txt")"

cd "$RUNDIR/workspace" || exit 2
START=$(date +%s.%N)
# The two `sandbox_workspace_write.exclude_*` settings are a HARNESS FIX, not a
# loosening: without them Codex asks for the workspace AND a temp directory as
# writable roots, and an unelevated Windows restricted-token sandbox refuses a
# split writable root set outright -- which broke the IMAGE VIEWER and nothing
# else. With them the sandbox has ONE writable root, the workspace, so the run
# is strictly more isolated than the default. A first run died on this before
# anything was graded and is kept as runs/_discarded-sandboxbug/.
timeout 3600 codex exec \
    --skip-git-repo-check \
    --sandbox workspace-write \
    -c sandbox_workspace_write.exclude_tmpdir_env_var=true \
    -c sandbox_workspace_write.exclude_slash_tmp=true \
    -c model_reasoning_effort=high \
    --json \
    "$PROMPT" > "$OUT.jsonl" 2> "$OUT.stderr"
RC=$?
END=$(date +%s.%N)
echo "exit_code=$RC" > "$OUT.meta"
echo "wall_seconds=$(python -c "print(round($END-$START,1))")" >> "$OUT.meta"
cat "$OUT.meta"
