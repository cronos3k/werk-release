#!/usr/bin/env bash
# run_selfrun.sh <model-key> <quant> <ctx-ladder> <tag>
#
# The adapted self-run arm. Same serial discipline as run_one.sh: unload
# everything, load cold at the largest context in the ladder that loads AND
# answers, `--parallel 1`, one model resident and one request in flight.
#
# The run directory contains ONLY the pinned selfrun fixture. The model writes
# a bash script; driver_selfrun.py screens it and executes it. See that file's
# docstring for why a supervised harness compiling reviewed source is not the
# act the "never auto-execute" doctrine forbids.
set -u
MODEL="$1"; QUANT="$2"; LADDER="$3"; TAG="$4"
WERK=/f/werk
ROOT="${GAUNTLET_ROOT:?set GAUNTLET_ROOT to an empty run directory outside any checkout}"
FIX=$WERK/gauntlet/roundSR/selfrun-v1.werk

DIR=$ROOT/${TAG}__selfrun
rm -rf "$DIR"; mkdir -p "$DIR"
cp "$FIX" "$DIR/"

lms unload --all >/dev/null 2>&1
CTX=""
for C in $LADDER; do
  echo "trying context $C ..."
  if lms load "$MODEL" -c "$C" --parallel 1 --gpu max -y >/dev/null 2>&1; then
    for _ in $(seq 1 60); do
      if python - "$MODEL" <<'PY'
import json,sys,urllib.request
b=json.dumps({"model":sys.argv[1],"messages":[{"role":"user","content":"hi"}],"max_tokens":1}).encode()
r=urllib.request.Request("http://127.0.0.1:1234/v1/chat/completions",data=b,
                         headers={"Content-Type":"application/json"})
urllib.request.urlopen(r,timeout=900).read()
PY
      then CTX="$C"; break; fi
      sleep 5
    done
  fi
  [ -n "$CTX" ] && break
  lms unload --all >/dev/null 2>&1
done
[ -z "$CTX" ] && { echo "LOAD FAILED at every context: $LADDER"; exit 3; }
echo "loaded at context $CTX"; lms ps 2>&1 | tail -2

cd "$DIR" || exit 1
python "$WERK/gauntlet/roundGF/driver_selfrun.py" \
  --model "$MODEL" --quant "$QUANT" --context "$CTX" \
  --max-iters "${ITERS:-8}" --max-wall "${WALL:-2700}" --max-tokens "${MAXTOK:-16384}" \
  --fixture "$DIR/$(basename "$FIX")" --rundir "$DIR" --label "${TAG}-selfrun" \
  > "$ROOT/log-${TAG}-selfrun.txt" 2>&1
echo "driver exit $?"
tail -3 "$ROOT/log-${TAG}-selfrun.txt"
