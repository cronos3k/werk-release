# `roundGF/` — the gap-completion round

Three holes in the gauntlet's coverage matrix, filled or attempted, in one
round. Read **`../../results/STAGE-GAPFILL-RESULTS.md`** for the whole record
and **`../RESULTS.md`** ("gap-completion round") for the summary.

The three gaps, each named by a previous round's own verdict:

| gap | who named it | this round's arm |
|---|---|---|
| **no local model has ever passed the spec-forcing task** — the open-weights round's envelope arm was 0/2 and the post-fix arm never re-ran it | `STAGE-OPENWEIGHTS-RESULTS.md`, "Spec-forcing envelope task **0 / 2**" | the **splat arm**: round 3's splat task on `fixtures/gsplat-v1.werk`, run against the five models that have passed anything, under roundOW's protocol |
| **the hardcopy round is N = 1, one vendor** | `STAGE-HARDCOPY-RESULTS.md`, "What it does not establish: N = 1, one vendor" | the **hardcopy replication arm**: Kimi Code CLI 0.15.0, the same three degraded page JPEGs, the same task sentence, the same 60-minute cap |
| **the self-run round is two frontier agentic CLIs; no non-agentic implementer has built anything** | `STAGE-SELFRUN-RESULTS.md` §5 | the **adapted self-run arm**: the strongest local model, no shell, writing a build script a supervised harness executes — an ADAPTED protocol, labelled as such everywhere |

| file | what it is |
|---|---|
| `driver.py` | the splat arm's harness. `roundOW/driver.py` plus exactly three changes, all documented in its own docstring as GF-1/GF-2/GF-3: a third context packer for the splat task, and **S-SFX-4 applied** (generated programs now run with `PYTHONIOENCODING=utf-8`). |
| `context_package.gsplat.txt` | the exact package every model in the splat arm received, committed once. **154 963 characters; 69 485 tokens** on qwen3-coder-30b's tokenizer. Over the 35k budget of the previous rounds, deliberately and by ruling — the splat task needs two complete layout grammars and a 36 KB manifest. |
| `PROMPT-gsplattask.txt` | round 3's splat task sentence, **verbatim**, byte-identical to `roundOW/PROMPT-gsplattask.txt` and to the one the cross-vendor round used. |
| `grade_gsplat.py` | artifact grading for the splat arm. Derives ground truth from the pinned fixture by the normative path (its own MessagePack + envelope reader), then checks the run's own output against it: the point count, the first points' position and colour triples, the three embedded tools by id, path and a verbatim source line. A model that fabricates values fails here. |
| `run_one.sh` | one splat run: unload everything, load the model cold at the **largest context in a ladder that actually loads and answers**, hand a fresh directory containing only the pinned fixture to `driver.py`. `--parallel 1`, one model resident, one request in flight. |
| `run_kimi_hardcopy.sh` | the hardcopy replication. `roundHC/run_codex.sh` with the CLI swapped, the same prompt file, the same degraded pages, the same cap. |
| `grade_hardcopy.py` | the hardcopy round's five-step ladder, graded from artifacts: byte-identical `.werk`, byte-identical PNG, the decoder the agent wrote, the CRC and prose evidence. |
| `driver_selfrun.py` | the adapted self-run harness. The model writes one bash script; **the harness executes it**. Its docstring states the "never auto-execute" distinction rather than assuming it. |
| `grade_selfrun.py` | two independent grades: is the package's own temperature-0 vector text in what the run produced, and does the binary the run built still reproduce the vector when *the grader* invokes it? |
| `runs/<tag>/` | per run: `run.json`, `stdout.log`, the final program, any report, the grader's json, and `transcript.json`. |

Run directories are `<lab>\gf-gauntlet\...`, outside every werk repository, and
contained only the pinned fixture (or, for the hardcopy arm, only the three
JPEGs). The harness refuses networking imports and absolute paths outside the
run directory in any generated program.
