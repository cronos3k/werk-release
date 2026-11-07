#!/usr/bin/env bash
# run_selfrun.sh <quant> <tag> [retry]
#
# The adapted self-run arm, run against the resident DeepSeek-V4-Flash endpoint.
#
# This uses roundGF's `driver_selfrun.py` — NOT roundDS's own `--task-kind
# selfrun` packer (DS-2). DS-2 was written before roundGF landed; roundGF had
# already established an adapted self-run protocol for exactly this population
# (the model emits ONE BASH SCRIPT — extract, compile, invoke, verify — and the
# harness executes it, because the interesting steps of a BUILDING task are
# `gcc` and an `argv` line, not Python). Using roundGF's harness makes this row
# directly comparable to its local-model attempt instead of being a third
# protocol nobody can line up. DS-2 stays in the driver, unused, and the
# results file says so.
#
# The only change to roundGF's driver is an --api flag for a non-localhost
# endpoint. The model is resident (155 GB), so nothing is loaded or unloaded
# here; serial discipline comes from this being the only client.
set -u
QUANT="$1"; TAG="$2"; RETRY="${3:-}"
WERK=/f/werk
ROOT="${GAUNTLET_ROOT:?set GAUNTLET_ROOT to an empty run directory outside any checkout}"
API="${API:-http://localhost:8123/v1}"
MODEL="${MODEL:-DeepSeek-V4-Flash-0731}"
CTX="${CTX:-1048576}"
FIX=$WERK/gauntlet/roundSR/selfrun-v1.werk

DIR=$ROOT/${TAG}__selfrun${RETRY:+__retry}
rm -rf "$DIR"; mkdir -p "$DIR"
cp "$FIX" "$DIR/"

python - "$MODEL" "$API" <<'PY' || { echo "endpoint not ready"; exit 1; }
import json,sys,urllib.request
model,api=sys.argv[1],sys.argv[2]
b=json.dumps({"model":model,"messages":[{"role":"user","content":"hi"}],"max_tokens":1}).encode()
r=urllib.request.Request(api.rstrip("/")+"/chat/completions",data=b,
                         headers={"Content-Type":"application/json"})
urllib.request.urlopen(r,timeout=900).read()
print("server ready")
PY

cd "$DIR" || exit 1
python "$WERK/gauntlet/roundDS/driver_selfrun.py" \
  --api "$API" --model "$MODEL" --quant "$QUANT" --context "$CTX" \
  --max-iters "${ITERS:-8}" --max-wall "${WALL:-2700}" --max-tokens "${MAXTOK:-16384}" \
  --fixture "$DIR/$(basename "$FIX")" --rundir "$DIR" \
  --label "${TAG}-selfrun${RETRY:+-retry}" \
  > "$ROOT/log-${TAG}-selfrun${RETRY:+-retry}.txt" 2>&1
echo "driver exit $?"
tail -3 "$ROOT/log-${TAG}-selfrun${RETRY:+-retry}.txt"
