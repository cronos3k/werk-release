# `_discarded-ctx262144/` — the run that was killed, kept because it is evidence

`qwen/qwen3-coder-30b`, Q4_K_M, 18.63 GB of weights, loaded at its nominal
maximum **262144** on a 24 GB RTX 4090, given the splat package.

Gregor's order for this round was MAX context, and `lms load` reported success
in 25.4 s, so the run started there. Its preflight is the only line it ever
produced:

```
model=qwen/qwen3-coder-30b ctx=262144 package_ctx=131072 budget=243793 chars package=154963 chars included=20 omitted=0
preflight: prompt_tokens=69485 cold prefill=253.4s (274 tok/s), chars/token=2.26
```

**Killed after 75 minutes without iteration 1 returning.** Nothing was graded
and nothing is scored from it. It is kept for two reasons.

1. It is the measurement that set the round's context policy. 274 tok/s against
   the same model's **3 751 tok/s at ctx 65536** is a 13.7× collapse, and the
   cause is KV residency: at 65536 the cache fits in the 5.9 GB the weights
   leave and above that it does not. "The largest context that does not
   collapse is what gets loaded" is roundOW's own rule; taking MAX literally
   violated it, and this directory is the cost of finding that out.
2. A discarded protocol is part of the experimental record —
   `roundOW/driver_toolloop.py`'s precedent.

Note the `package=154963 chars` in that header: this run predates the **GF-4**
fix, so its package is the one that was still missing every layout grammar
(S-GF-1). The package the graded runs received is 166 642 characters and is
committed as `../../context_package.gsplat.txt`.
