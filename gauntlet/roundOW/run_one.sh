#!/usr/bin/env bash
# run_one.sh <model-key> <quant> <ctx> <task: round1|gsplat> <tag> [retry]
#
# One gauntlet run. Loads the model COLD (unload everything first, then load
# with --parallel 1 at the recorded context) so that every run pays its own
# prefill and the per-run wall clocks are comparable, then hands a fresh
# directory containing ONLY the pinned fixture to driver.py.
set -u
MODEL="$1"; QUANT="$2"; CTX="$3"; TASK="$4"; TAG="$5"; RETRY="${6:-}"
WERK=/f/werk
ROOT="${GAUNTLET_ROOT:?set GAUNTLET_ROOT to an empty run directory outside any checkout}"

KIND=""
PKGCTX="${PKGCTX:-131072}"
case "$TASK" in
  round1) FIX=$WERK/fixtures/crate-v1.werk;  PROMPT=$WERK/gauntlet/roundOW/PROMPT-round1task.txt ;;
  gsplat) FIX=$WERK/fixtures/gsplat-v1.werk; PROMPT=$WERK/gauntlet/roundOW/PROMPT-gsplattask.txt ;;
  mini)   FIX=$WERK/gauntlet/roundOW/mini-v1.werk
          PROMPT=$WERK/gauntlet/roundOW/PROMPT-round1task-mini.txt; KIND="--task-kind mini" ;;
  envel)  FIX=$WERK/gauntlet/roundOW/mini-v1.werk
          PROMPT=$WERK/gauntlet/roundOW/PROMPT-envelopetask-mini.txt; KIND="--task-kind mini" ;;
  *) echo "unknown task $TASK"; exit 2 ;;
esac

DIR=$ROOT/${TAG}__${TASK}${RETRY:+__retry}
rm -rf "$DIR"; mkdir -p "$DIR"
cp "$FIX" "$DIR/"

lms unload --all >/dev/null 2>&1
lms load "$MODEL" -c "$CTX" --parallel 1 --gpu max -y >/dev/null 2>&1
lms ps 2>&1 | tail -2

# Wait until the server actually answers for this model. `lms load` returns
# before the model is servable and the first request then 400s, which would be
# recorded as a model failure when it is a harness race.
for _ in $(seq 1 60); do
  if python - "$MODEL" <<'PY'
import json,sys,urllib.request
b=json.dumps({"model":sys.argv[1],"messages":[{"role":"user","content":"hi"}],"max_tokens":1}).encode()
r=urllib.request.Request("http://127.0.0.1:1234/v1/chat/completions",data=b,
                         headers={"Content-Type":"application/json"})
urllib.request.urlopen(r,timeout=600).read()
PY
  then echo "server ready"; break; fi
  sleep 5
done

cd "$DIR" || exit 1
python "$WERK/gauntlet/roundOW/driver.py" \
  --model "$MODEL" --quant "$QUANT" --context "$CTX" --package-ctx "$PKGCTX" $KIND \
  --max-tokens "${MAXTOK:-16384}" \
  --fixture "$DIR/$(basename "$FIX")" --task "$PROMPT" --rundir "$DIR" \
  --label "${TAG}-${TASK}${RETRY:+-retry}" \
  > "$ROOT/log-${TAG}-${TASK}${RETRY:+-retry}.txt" 2>&1
echo "driver exit $?"
tail -1 "$ROOT/log-${TAG}-${TASK}${RETRY:+-retry}.txt"
