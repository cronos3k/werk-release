#!/usr/bin/env bash
# run_one.sh <quant> <task: mini|envel|gsplat|round1> <tag> [retry]
#
# One DeepSeek-V4-Flash gauntlet run. Unlike roundOW/run_one.sh this does NOT
# load or unload the model: DeepSeek-V4-Flash is 155 GB of weights spread over
# eight V100s and a cold load costs minutes, so the server is brought up ONCE
# (see results/STAGE-DSV4-RESULTS.md for the exact systemd-run command) and
# stays resident for the whole round. Requests are strictly serial — one in
# flight at any moment, Gregor's standing order — which this script enforces by
# being the only thing that talks to the endpoint.
#
# The driver runs on the Windows box and talks to llama-server on v100 over the
# LAN. Everything else is roundOW's protocol, unchanged.
set -u
QUANT="$1"; TASK="$2"; TAG="$3"; RETRY="${4:-}"
WERK=/f/werk
ROOT="${GAUNTLET_ROOT:?set GAUNTLET_ROOT to an empty run directory outside any checkout}"
API="${API:-http://localhost:8123/v1}"
MODEL="${MODEL:-DeepSeek-V4-Flash-0731}"
CTX="${CTX:-131072}"
PKGCTX="${PKGCTX:-131072}"

KIND=""
case "$TASK" in
  round1) FIX=$WERK/fixtures/crate-v1.werk;  PROMPT=$WERK/gauntlet/roundOW/PROMPT-round1task.txt ;;
  gsplat) FIX=$WERK/fixtures/gsplat-v1.werk; PROMPT=$WERK/gauntlet/roundOW/PROMPT-gsplattask.txt ;;
  mini)   FIX=$WERK/gauntlet/roundOW/mini-v1.werk
          PROMPT=$WERK/gauntlet/roundOW/PROMPT-round1task-mini.txt; KIND="--task-kind mini" ;;
  envel)  FIX=$WERK/gauntlet/roundOW/mini-v1.werk
          PROMPT=$WERK/gauntlet/roundOW/PROMPT-envelopetask-mini.txt; KIND="--task-kind mini" ;;
  selfrun) FIX=$WERK/gauntlet/roundSR/selfrun-v1.werk
          PROMPT=$WERK/gauntlet/roundDS/PROMPT-selfruntask-inline.txt; KIND="--task-kind selfrun" ;;
  splat)  FIX=$WERK/fixtures/gsplat-v1.werk
          PROMPT=$WERK/gauntlet/roundGF/PROMPT-gsplattask.txt; KIND="--task-kind gsplatmini" ;;
  *) echo "unknown task $TASK"; exit 2 ;;
esac

DIR=$ROOT/${TAG}__${TASK}${RETRY:+__retry}
rm -rf "$DIR"; mkdir -p "$DIR"
cp "$FIX" "$DIR/"

# The server is already up and resident. Confirm it answers for this model id
# before starting the clock, so a serving hiccup is never scored as a model
# failure (S-OW-5).
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
python "$WERK/gauntlet/roundDS/driver.py" \
  --api "$API" --model "$MODEL" --quant "$QUANT" --context "$CTX" --package-ctx "$PKGCTX" $KIND \
  --max-tokens "${MAXTOK:-16384}" --max-iters "${ITERS:-8}" --max-wall "${WALL:-2700}" \
  --fixture "$DIR/$(basename "$FIX")" --task "$PROMPT" --rundir "$DIR" \
  --label "${TAG}-${TASK}${RETRY:+-retry}" \
  > "$ROOT/log-${TAG}-${TASK}${RETRY:+-retry}.txt" 2>&1
echo "driver exit $?"
tail -1 "$ROOT/log-${TAG}-${TASK}${RETRY:+-retry}.txt"
