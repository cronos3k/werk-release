# `roundDS/` — the frontier-open-weights round

**DeepSeek-V4-Flash-0731, 284B total / 13B active, served by us, on our own
hardware, under `roundOW`'s protocol unchanged.**

Read **`../../results/STAGE-DSV4-RESULTS.md`** for the whole record — bring-up,
costs, timings, per-task outcomes and the `S-DS-n` findings — and **`../RESULTS.md`**
for the summary row in the open-weights table.

This round exists because the open-weights round tested *small* open weights
(4B–30B) and the cross-vendor round tested *frontier commercial* models behind
someone else's API. The cell in between — **frontier open weights, self-hosted**
— was empty, and it is the cell that matters for the format's premise: a
reader that is both as capable as the commercial agents and as inspectable as a
file on a disk.

| file | what it is |
|---|---|
| `driver.py` | `roundOW/driver.py` with **one** change: an `--api` flag (and `$WERK_API`) so the harness can drive an OpenAI-compatible endpoint that is not LM Studio on localhost. The protocol — inlined self-description, one complete program per turn, harness runs it and feeds back stdout/stderr/traceback, 8 iterations or 45 minutes, artifact grading — is byte-identical otherwise. |
| `run_one.sh` | one run. Unlike `roundOW/run_one.sh` it does **not** cold-load the model per run: 155 GB across eight V100s costs minutes to load, so the server comes up once and stays resident. Serialisation (one request in flight) is enforced by this being the only client. |
| `runs/<tag>/` | per run: `run.json`, `stdout.log`, the final `solution.py`, any `REPORT.md`, and `transcript.json`. |

Grading is `roundOW/grade.py`, unchanged — hashes what a run left on disk
against the fixture's own `MANIFEST.json` and re-runs the final program in a
clean directory containing only the fixture. Matches by digest, not filename.

Fixtures are the pinned ones, not rebuilt for this round:
`gauntlet/roundOW/mini-v1.werk` (`f7bdcc85…`, the post-fix build) and
`fixtures/gsplat-v1.werk` (`ede0aee6…`).
