#!/usr/bin/env python3
"""Measure prompt-prefill throughput of the currently loaded LM Studio model.

Sends a prompt of a known size and asks for 8 tokens back, so the measured time
is dominated by prefill. Prints tokens, seconds and tokens/s. Used to choose an
honest loaded-context value per model: a context length whose KV cache does not
fit in VRAM makes prefill collapse, and that must be measured, not assumed.
"""
import json, sys, time, urllib.request

API = "http://127.0.0.1:1234/v1/chat/completions"

def probe(model, chars):
    filler = ("The quick brown fox jumps over the lazy dog. " * ((chars // 45) + 1))[:chars]
    body = {"model": model, "max_tokens": 8, "temperature": 0,
            "messages": [{"role": "user", "content": filler + "\n\nReply with the word OK."}]}
    t0 = time.monotonic()
    req = urllib.request.Request(API, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=3600) as r:
        d = json.loads(r.read().decode())
    dt = time.monotonic() - t0
    u = d.get("usage") or {}
    pt = u.get("prompt_tokens")
    print("chars=%d prompt_tokens=%s secs=%.1f prefill=%.0f tok/s chars_per_token=%.2f"
          % (chars, pt, dt, (pt or 0) / dt, chars / (pt or 1)))
    return pt, dt

if __name__ == "__main__":
    m = sys.argv[1]
    for c in [int(x) for x in sys.argv[2:]] or [40000]:
        probe(m, c)
