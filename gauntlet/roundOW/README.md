# roundOW/ — the open-weights gauntlet

Six small local models, no agentic CLI, one RTX 4090, and a test that fits in
**31 490 tokens** of inlined self-description.

Read **`../../results/STAGE-OPENWEIGHTS-RESULTS.md`** for the whole record and
**`../RESULTS.md`** ("open-weights round") for the summary table.

| file | what it is |
|---|---|
| `driver.py` | the harness. No tools: the package's self-description is inlined, the model emits one complete Python program, the harness runs it in the isolated run directory and feeds back stdout/stderr/traceback. 8 iterations or 45 minutes. Measures its own wall clock. |
| `driver_toolloop.py` | the FIRST harness — a four-tool agentic loop — **discarded before anything was graded** (LM Studio models are not CLI agents). Kept because a discarded protocol is part of the experimental record. Its one partial run is in `_discarded/`. |
| `prefill_probe.py` | times a prefill of known size against whatever model is loaded. This is how the loaded context length was *measured* rather than assumed: a 30B-A3B Q4 model loads at its nominal 262144 and prefills at 293 tok/s, and at 65536 does 1881 tok/s. |
| `build_mini_fixture.py` | deterministic builder for `mini-v1.werk`, from bytes that already live inside `fixtures/crate-v1.werk` and `tests/fixtures/crate.werk`. Touches neither. Re-signs, re-converges `preview_prefix_bytes`, recomputes `spec_sha256`. |
| `mini-v1.werk` | the small-context fixture, `signed-and-valid`. One mesh, one sound family, one image, one WKRP envelope, and its own spec/ and loaders/. Rebuilt for the release under the ruling on #11 (no edge to an absent node, so it verifies clean; size and hash in `fixtures/fixtures.json`, key `mini-v1`). Every trial recorded in this round ran on the earlier post-fix build: 960 061 B, sha256 `f7bdcc85…`, 36 entries, 14 nodes, 34 declared files, kept byte for byte as `historical/mini-v1-f7bdcc85.werk` (key `mini-v1-historical`). The pre-fix round ran on the first build: 938 756 B, sha256 `86dec8c0…6db75713`, 34 entries, 14 nodes, 32 declared files. That first build is not committed. See the post-fix arm in `../RESULTS.md`. |
| `grade.py` | artifact grading. Hashes what a run left on disk against the fixture's own `MANIFEST.json`, and re-runs the final program in a clean directory containing only the fixture. Matches by digest, not by filename. |
| `run_one.sh` | one run: unload everything, load the model cold at the recorded context with `--parallel 1`, wait until the server answers, hand a fresh directory containing only the fixture to `driver.py`. |
| `PROMPT-round1task.txt` | round 1's task sentence, verbatim, as used in the cross-vendor round. |
| `PROMPT-round1task-mini.txt` | the same, with the filename changed and nothing else. |
| `PROMPT-envelopetask-mini.txt` | the spec-forcing second task. **Adapted** from `PROMPT-gsplattask.txt`, not verbatim. |
| `context_package.mini.txt` | the exact 31 490-token package every model received, committed once. |
| `runs/<tag>/` | per run: `run.json` (the machine-readable row), `stdout.log`, the final `solution.py`, any `REPORT.md`, and `transcript.json` with the context package elided (it is identical across runs and committed above). |

Run directories were outside every werk repository, contained only the pinned
fixture, and the harness refused absolute paths outside them and any networking
import in a generated program.
