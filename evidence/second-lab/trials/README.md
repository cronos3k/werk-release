# Second-lab trial evidence

This folder lets a reader check the second-lab claim "12 of 12 fresh-agent trials passed" from the repository.

| Trials | Count | Evidence here |
|---|---|---|
| Batch 1, 2026-10-05 | 4 | Programs and reports, rebuilt from the session logs (see below) |
| Batch 2, 2026-10-07, sealed | 7 | Programs, reports, run results and small outputs, copied from the trial folders |
| August trial, 2026-08-25 | 1 | None. The program was not retained. Only the written account in the August verification report exists. The ledger marks it UNAVAILABLE. |

So 11 of the 12 trials can be checked from these files. The August trial cannot.

## In this release (read this first)

These trials are historical. They ran on fixture bytes built from an earlier
spec revision, not on this release's fixtures, so the checker keeps its
original pins in [batch2/FIXTURE-SHA256.txt](batch2/FIXTURE-SHA256.txt) and
refuses the release's own `fixtures/crate-v1.werk` and `fixtures/gsplat-v1.werk`
(their hashes differ). What it needs:

| file | sha256 | where |
|---|---|---|
| `crate-v1.werk` | `0a7a7341d5d508c75925a8c3be0b6c8ccdcced607d9bdd0b26f04e264f029106` | not hosted with this release; see "External and historical files" in `RELEASE-ASSETS.md` |
| `gsplat-v1.werk` | `ede0aee6cc5659af741059b747dc3f3459db220234e7ffb95c4437c02337090a` | same |
| `mini-v1.werk` | `f7bdcc853009504b1d31b2934a7a8294cbf0e6f227c95f7de1e81af0947e9837` | in the repository at `gauntlet/roundOW/historical/mini-v1-f7bdcc85.werk`; the checker picks it up by itself |

Put the two historical `.werk` files in one folder and run, from the repository root:

```
python evidence/second-lab/trials/check_trials.py --fixtures DIR
```

Paths below that start with `results/second-lab/` are this folder's paths in
the second lab's own tree; here they start with `evidence/second-lab/`.

## Check the trials yourself

You need Python 3.10 or later, standard library only. You also need `fixtures/crate-v1.werk` and `fixtures/gsplat-v1.werk` from `tools/fetch_fixtures.py` or the `fixtures-v1` release. The trials ran on `gauntlet/roundOW/mini-v1.werk` as it was before the ruling on #11 (`f7bdcc85...`). Once #11 rebuilds that file, the old bytes are at `gauntlet/roundOW/historical/mini-v1-f7bdcc85.werk`, and the checker uses them.

```
python results/second-lab/trials/check_trials.py
```

The checker does these steps for each trial:

1. It confirms that each fixture hashes to its pin in [batch2/FIXTURE-SHA256.txt](batch2/FIXTURE-SHA256.txt).
2. It copies the program and its sibling files into an empty temporary folder with only the fixture.
3. It runs the program with the command that the agent's own report gives.
4. It checks the output bytes:
   - round 1: one output file has the declared digest of the primary mesh, and one has a declared digest of a primary sound `.wav`;
   - envelope: the output gives the decoded values of both pose records;
   - gsplat: `points.csv` has all 281,498 points, and every row equals the package's float32 position and 8-bit colour.

Result on 2026-11-11 (Windows 11, Python 3.14): **11 of 11 trials reproduce their output bytes.**
The listing and damage-detection clauses are scored separately, in [../audits/rubric.md](../audits/rubric.md).

## The trials

| Trial | Task | Fixture (sha256 prefix) | Program | Wall clock | Cost (USD) | Verdict | Isolation (ledger) |
|---|---|---|---|---:|---:|---|---|
| batch1/r1-t1 | round 1 | `mini-v1` (`f7bdcc85`) | `tools/werk_reader.py` | 398.7 s | 2.740 | PASS | clean |
| batch1/r1-t2 | round 1 | `mini-v1` (`f7bdcc85`) | `werk_open.py` | 389.2 s | 2.660 | PASS | clean |
| batch1/r1-t3 | round 1 | `mini-v1` (`f7bdcc85`) | `werk_reader.py` | 338.5 s | 2.464 | PASS | technical violation: 2 reads of its own spilled tool output outside the folder |
| batch1/env-t1 | envelope | `mini-v1` (`f7bdcc85`) | `tools/werk_inspect.py` | 338.5 s | 2.564 | PASS | clean |
| batch2/xv-t1 | round 1 | `crate-v1` (`0a7a7341`) | `werk_open.py` | 386.0 s | 2.740 | PASS | 1 read of its own spilled tool output, blocked by the seal |
| batch2/xv-t2 | round 1 | `crate-v1` (`0a7a7341`) | `werk_reader.py` | 337.7 s | 2.863 | PASS | 1 read of its own spilled tool output, blocked by the seal |
| batch2/xv-t3 | round 1 | `crate-v1` (`0a7a7341`) | `werk_reader.py` | 305.5 s | 2.463 | PASS | clean |
| batch2/splat-t1 | gsplat | `gsplat-v1` (`ede0aee6`) | `scripts/werk_inspect.py` | 378.5 s | 2.765 | PASS | clean |
| batch2/splat-t2 | gsplat | `gsplat-v1` (`ede0aee6`) | `mytools/werk_inspect.py` | 626.2 s | 3.255 | PASS | 1 read of its own spilled tool output, blocked by the seal |
| batch2/env-t2 | envelope | `mini-v1` (`f7bdcc85`) | `tools/werk_inspect.py` | 254.6 s | 1.647 | PASS | clean |
| batch2/env-t3 | envelope | `mini-v1` (`f7bdcc85`) | `tools/werkread.py` | 355.1 s | 2.600 | PASS | clean |

All 11 trials used `claude-opus-5-5` (Claude Code 2.1.290 for batch 1, 2.1.292 for batch 2).
The prompts are the committed files `gauntlet/roundOW/PROMPT-round1task-mini.txt`, `gauntlet/roundXV/PROMPT-round1task.txt`, `gauntlet/roundXV/PROMPT-gsplattask.txt` and `gauntlet/roundOW/PROMPT-envelopetask-mini.txt`. The ledger row of each trial gives its prompt file and digest.

## What each trial folder holds

Each folder has a `FILES.tsv` that lists every file the trial left, with its size and SHA-256. The status column says what happened to it:

| Status | Meaning |
|---|---|
| copied | The file is here, byte for byte. |
| copied, local paths replaced | The local user name and folder paths are replaced with `<user>`, `<second-lab>` or `<repo>`. Both digests are listed. No program file needed this. |
| not copied: identical to fixture or package entry | The bytes equal a pinned fixture or a file inside it. The listed digest proves this. |
| not copied: larger than 1 MB | A large output, such as `points.csv` (20 MB). The checker regenerates it. |
| skipped: Python bytecode | `__pycache__` files. |

`claude-result.json` is the run summary from Claude Code (model, cost, turns, blocked tool calls).

## How batch 1 was rebuilt

The batch 1 trial folders were in a temporary folder that the system later deleted. The session logs remained. The agent wrote every file with the Write and Edit tools, so each file was rebuilt by replaying those calls in order. Each rebuilt final program has the same SHA-256 as the program that was graded on 2026-10-05 and recorded in the ledger (`rerun_evidence.program_sha256`). [pack-summary.json](pack-summary.json) records this check. Batch 1 has no `claude-result.json`. Its cost and time come from the grading record.

## Harness

[harness/](harness/) holds the two trial scripts and the per-trial seal settings of batch 2 (deny rules, no web, no other trial folder). Local paths are replaced with placeholders.

## What is not here

- Session transcripts. They stay outside Git ([../log-policy.md](../log-policy.md)). A reviewer can ask for the redacted logs.
- The August trial program (not retained).

## Limits

- One person ran, collected and graded these trials. The grading criteria were written before grading.
- One model family across all 12 trials.
- The envelope prompt's answer also appears as the worked example in the spec (S-DS-8). The pose count can be copied. The per-entry values cannot.
- Batch 1 was not sealed. Batch 2 was sealed with Claude Code permission rules. Python run by the agent was not sandboxed on Windows, so the transcript audit covers that part.
