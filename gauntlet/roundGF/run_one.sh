#!/usr/bin/env bash
# run_one.sh <model-key> <quant> <ctx-ladder> <tag> [retry]
#
# One GAP-COMPLETION splat run. Derived from `gauntlet/roundOW/run_one.sh`.
# Two differences, both because the splat package is ~50k tokens rather than
# ~33k:
#
#   * CTX LADDER. Gregor's order for this round is MAX context. `lms load`
#     is tried at each context in the ladder, largest first, and the first one
#     that loads AND answers is the one used and recorded. What actually
#     loaded is in run.json, never assumed.
#   * PKGCTX is 131072 so that the whole 20-item package fits with nothing
#     omitted regardless of which rung the model landed on. Every model
#     therefore receives the IDENTICAL package, which is roundOW's rule.
#
# STRICTLY SERIAL: `lms unload --all` first, `--parallel 1`, one model
# resident and one request in flight. Gregor's standing order.
set -u
MODEL="$1"; QUANT="$2"; LADDER="$3"; TAG="$4"; RETRY="${5:-}"
WERK=/f/werk
ROOT="${GAUNTLET_ROOT:?set GAUNTLET_ROOT to an empty run directory outside any checkout}"

FIX=$WERK/fixtures/gsplat-v1.werk
PROMPT=$WERK/gauntlet/roundGF/PROMPT-gsplattask.txt
PKGCTX="${PKGCTX:-131072}"

DIR=$ROOT/${TAG}__gsplat${RETRY:+__retry}
rm -rf "$DIR"; mkdir -p "$DIR"
cp "$FIX" "$DIR/"

lms unload --all >/dev/null 2>&1

CTX=""
for C in $LADDER; do
  echo "trying context $C ..."
  if lms load "$MODEL" -c "$C" --parallel 1 --gpu max -y >/dev/null 2>&1; then
    # `lms load` returns before the server is servable; a 400 here would be
    # recorded as a model failure when it is a harness race.
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

if [ -z "$CTX" ]; then
  echo "LOAD FAILED at every context in the ladder: $LADDER" | tee "$ROOT/log-${TAG}-gsplat${RETRY:+-retry}.txt"
  exit 3
fi
echo "loaded at context $CTX"
lms ps 2>&1 | tail -2

cd "$DIR" || exit 1
python "$WERK/gauntlet/roundGF/driver.py" \
  --model "$MODEL" --quant "$QUANT" --context "$CTX" --package-ctx "$PKGCTX" \
  --task-kind gsplatmini \
  --max-tokens "${MAXTOK:-16384}" --max-iters "${ITERS:-8}" --max-wall "${WALL:-2700}" \
  --fixture "$DIR/$(basename "$FIX")" --task "$PROMPT" --rundir "$DIR" \
  --label "${TAG}-gsplat${RETRY:+-retry}" \
  > "$ROOT/log-${TAG}-gsplat${RETRY:+-retry}.txt" 2>&1
echo "driver exit $?"
tail -3 "$ROOT/log-${TAG}-gsplat${RETRY:+-retry}.txt"
