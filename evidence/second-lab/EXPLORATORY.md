# Second-lab evidence — status: EXPLORATORY

Everything under `evidence/second-lab/` is data contributed by an independent
second laboratory (Yuvraj Puyam), from his pull requests #13 (the attempt
ledger) and #8 (the negative-control round against FBX, glTF and USDZ). It is
carried here as **exploratory data**, not as a result of this repository's
gates. His commits are applied with his authorship; the files are as he wrote
them, relocated.

## Where the files came from

| In this repository | In the PR | PR |
|---|---|---|
| `evidence/second-lab/` (README, `ledger/`, `audits/`, `locks/`, …) | `results/second-lab/` | #13 |
| `evidence/second-lab/roundNC/` | `gauntlet/roundNC/` | #8 |

Paths inside these files still name the PR layout (`repo:results/second-lab/…`,
`repo:gauntlet/roundNC/…`, `gauntlet/roundNC/` in `RESULTS-NC.md`). Read them
through the table above. `ledger/check.py --source-repo` therefore resolves
`repo:` pointers against the PR layout, not this one.

147 reproducible run outputs and logs of the negative-control round (8 874 737
bytes: OBJ/RAW/USDC conversions, f32 dumps, WAV and GLB copies, run logs) are
kept out of git. `roundNC/OUT-OF-GIT.txt` lists each with its sha256; they are
in the release asset `evidence/second-lab/roundNC-binaries.tar.gz`
(`RELEASE-ASSETS.md`). Extract it at the repository root.

## How to read it (provisional rulings, pending Gregor's answers)

* **The negative control is exploratory, not pre-registered.** The freeze
  commit (`504a9ac` in the PR history, the first roundNC commit here) is
  unsigned and was first published together with the results (2026-10-11,
  about 70 minutes after the trial batch started). Read "pre-registration" in
  these files as "frozen in a local commit before the trials, published with
  the results".
* **The frozen grader was later edited at its frozen paths**
  (`roundNC/grade_nc.py`, `roundNC/nc_mesh.py`, by the three grader commits
  that follow the results here) while `PREREGISTRATION.md` still says
  "Amendments: None". The frozen bytes are those of the freeze commit.
* **The integrity table overstates one point.** FBX and glTF *declare* no
  integrity values, but their bytes carry incidental non-cryptographic checks
  (zlib Adler-32 on FBX's compressed arrays; PNG CRC-32 in all three
  controls). "Nothing extracted from FBX or glTF can be checked at all" is
  not supported.
* **The arms are not matched** (different asset, mesh structure, extraction
  task, second payload and documentation conditions; n = 3 per arm, one
  model). No PASS-rate gap here is a format-quality result.
* **Ledger counts.** The re-grade of the 39 committed author runs agrees in
  29 and differs in 10 (not 30/9). None of the 31 second-lab rows has its run
  artefacts committed, except the 12 negative-control trials, which are in
  `roundNC/`. The PASS-to-PARTIAL downgrades rest on criteria that are not in
  this repository and cannot be reproduced from it.
* The full-task re-grades are **post-hoc**, stricter than the criteria the
  rounds declared; they stand beside the recorded verdicts and never replace
  them.

The review that produced these points is summarised in `RELEASE-ASSEMBLY.md`.

## Added after the first assembly: PR #13 follow-up (cb0b4b3, 3beea56, 61a873f)

Three more of his commits, replayed with his authorship and relocated the same
way. They change two of the points above:

* `audits/rubric.md` and `audits/criteria-2026-10-05.md` now state the
  criteria behind the changed verdicts, and `audits/rubric_check.py`
  re-derives all 31 round-1 verdicts. It needs his stored re-runs
  (`RERUNS_DIR`), which are not in this repository: they are an author-lab
  asset (`second-lab-reruns-2026-10-12`, pinned by sha256 in
  `RELEASE-ASSETS.md`, not hosted or verified here). Until a reader has that
  file, the 31 verdicts are documented but not reproducible from this
  repository alone.
* `trials/` now holds the programs, reports and small outputs of 11 of the 12
  fresh-agent trials, with `trials/check_trials.py`, which re-runs each
  program on the exact fixture bytes it ran on. Those bytes are historical:
  `crate-v1.werk` `0a7a7341…` and `gsplat-v1.werk` `ede0aee6…` (built from an
  earlier spec revision; listed in `RELEASE-ASSETS.md`, not hosted here) and
  `mini-v1.werk` `f7bdcc85…` (in the repository at
  `gauntlet/roundOW/historical/mini-v1-f7bdcc85.werk`). The checker keeps
  those pins on purpose and refuses this release's rebuilt fixtures. On this
  release tree, with the two historical files supplied: 11 of 11 trials
  reproduce their output bytes (trial `r1-t3`'s program exits 1, its output
  matches; that is the trial as recorded).
* The negative-control scripts (`roundNC/build_expectations.py`,
  `roundNC/run_nc_trials.sh`) now point at the historical mini-v1 file, since
  `gauntlet/roundOW/mini-v1.werk` was rebuilt under the ruling on #11.

