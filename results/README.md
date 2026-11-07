# `results/` — the shared-doc serialization protocol

Ruling 20 of `docs/RULINGS-2026-08-08.md`:

> **Shared-doc serialization: YES, write the protocol.** Per-stage result
> files (e.g. `results/STAGE<id>-RESULTS.md`); `HANDOVER.md` and `ROADMAP.md`
> are merged serially by the orchestrator only, never edited by two
> concurrent agents.

## The protocol, normative for every agent working in this tree

1. **Two files are serialized: `HANDOVER.md` and `ROADMAP.md`.** They are the
   project's shared narrative and its shared work queue. Concurrent agents
   editing either of them produce merge conflicts in prose, which git resolves
   by picking a side — i.e. by silently losing one agent's measured results.
   That has already happened once in this repository (see the "stage by
   explicit path, never `git add -A`" lesson in HANDOVER).

2. **While a wave is running, no agent writes to those two files.** An agent
   writes its results to **`results/STAGE<id>-RESULTS.md`**, a file only it
   touches. `<id>` is the stage number or, for a cross-cutting wave, a short
   slug (`RULINGS`, `PAPER`, `VLM`). One file, one author, no conflicts.

3. **At most one agent per wave is authorized to merge.** That agent — the
   orchestrator, or the single agent the orchestrator names — folds the
   per-stage result files into `HANDOVER.md` and `ROADMAP.md` **in one commit,
   at the end of its work**, and says in the commit message which result files
   it merged. Every other agent's contribution to the shared narrative is its
   result file, and it is complete without the merge.

4. **Commit by explicit path, always.** `git add <path> …`, never `git add -A`
   and never `git commit -a`. Agents share a working tree; a wildcard add
   commits somebody else's half-finished work under your commit message.

5. **A result file is not a draft.** It carries the same standard the shared
   docs do: measured numbers only, every gate named with its command and its
   fresh output, and findings filed with an id. If the merge never happens the
   result file is still the record.

6. **Ownership is declared, not assumed.** An agent that owns a subtree for a
   wave (the Stage 8 paper agent owns `paper/`, the rulings agent owns
   `spec/`, `retarget/`, `fixtures/`) says so in its result file's header, and
   no other agent writes there during the wave.

## Naming

| file | wave | author |
|---|---|---|
| `results/STAGE-RULINGS-RESULTS.md` | the 2026-08-08 rulings implementation (rulings 1–6, 8–15, 20) | the rulings agent |
| `results/STAGE-PIPELINE-QUALITY-RESULTS.md` | the 2026-08-08 pipeline-quality wave (rulings 16, 18, 19) | the pipeline-quality agent |
| `results/STAGE12-RESULTS.md` | Stage 12: point clouds, Gaussian splats, embedded tools | the Stage 12 agent |
| `results/STAGE12B-RESULTS.md` | Stage 12B: rulings 21 + 22 (S12-9, S12-7) and the fixture/gate re-drill | the Stage 12B agent |
| `results/STAGE-CROSSVENDOR-RESULTS.md` | the 2026-08-08 cross-vendor gauntlet round (OpenAI + Moonshot, four runs, S-XV-1 … S-XV-5) | the cross-vendor gauntlet agent |
| `results/STAGE-OPENWEIGHTS-RESULTS.md` | the 2026-08-08 open-weights round (six small local models, the 31 490-token package, S-OW-1 … S-OW-6) | the open-weights gauntlet agent |
| `results/STAGE-SPECFIX-OW-RESULTS.md` | the 2026-08-09 open-weights spec-fix wave (S-OW-1 … S-OW-4 turned into spec, all fixtures rebuilt, the post-fix model arm, S-SFX-1 … S-SFX-5) | the open-weights spec-fix agent |
| `results/STAGE-OPENWEIGHTS-RESULTS.md` | the 2026-08-09 open-weights gauntlet round (six small local models, S-OW-1 … S-OW-6) | the open-weights gauntlet agent |
| `results/STAGE-SELFRUN-RESULTS.md` | the 2026-08-09 self-run round: a package carrying a language model AND its runtime as source; `gauntlet/roundSR/`, `docs/PROFILE-MODEL-DRAFT.md`, S-SR-1 … S-SR-11 | the self-run agent |
| `results/STAGE-HARDCOPY-RESULTS.md` | the 2026-08-09 hardcopy round: a werk package printed on three sheets as prose + 2D barcodes, recovered from photographs (S-HC-1 … S-HC-6) | the hardcopy round agent |

| `results/STAGE-GAPFILL-RESULTS.md` | the 2026-08-09 gap-completion round: the splat task on local models, the hardcopy round replicated on a second vendor, and an adapted self-run arm; `gauntlet/roundGF/`, S-GF-1 … S-GF-5 | the gap-completion agent |

New waves append a row.
