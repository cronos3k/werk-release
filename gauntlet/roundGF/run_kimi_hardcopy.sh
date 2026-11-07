#!/usr/bin/env bash
# roundGF job 2 -- the hardcopy round's REPLICATION arm.
#
# The hardcopy round is N=1, one vendor (Codex CLI on gpt-5.6-sol). Its own
# verdict names that as the first thing it does not establish. This script is
# `gauntlet/roundHC/run_codex.sh` with the CLI swapped and nothing else:
#
#   * the SAME task sentence, `gauntlet/roundHC/PROMPT-archaeology.txt`,
#     verbatim, committed before the run and unchanged since;
#   * the SAME input, a fresh directory containing ONLY the three DEGRADED
#     page JPEGs from `gauntlet/roundHC/pages/scanned/` (rotation 0.55-0.90
#     degrees, 1.1 px blur, illumination ramp to 62 %, sigma = 9 noise,
#     JPEG q82) -- the degraded arm, which is the arm Codex was graded on;
#   * the SAME 60-minute cap, enforced by `timeout`;
#   * process wall clock, never self-reported.
#
# Codex's `sandbox_workspace_write.exclude_*` settings have no Kimi
# equivalent; they were a fix for a Windows restricted-token sandbox bug in
# Codex specifically (documented in run_codex.sh) and there is nothing to
# port. Kimi's isolation is audited from the transcript afterwards, exactly as
# the cross-vendor round audited it.
#
#   bash gauntlet/roundGF/run_kimi_hardcopy.sh <run-dir> <out-prefix>
set -u
RUNDIR="$1"
OUT="$2"
PROMPT="$(cat "$(dirname "$0")/../roundHC/PROMPT-archaeology.txt")"

cd "$RUNDIR/workspace" || exit 2
START=$(date +%s.%N)
timeout 3600 kimi -p "$PROMPT" --output-format stream-json \
    > "$OUT.jsonl" 2> "$OUT.stderr"
RC=$?
END=$(date +%s.%N)
echo "exit_code=$RC" > "$OUT.meta"
echo "wall_seconds=$(python -c "print(round($END-$START,1))")" >> "$OUT.meta"
cat "$OUT.meta"
