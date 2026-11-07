# Post-hoc rerun convention

This revision changes reruns. It does not replace historical results.

| Grader | Program arguments | Scratch directory | Host failure |
|---|---|---|---|
| roundOW/grade.py | `--prog-args` then repeated `--prog-arg` | `--out` | TASK HOST-ERROR |
| roundGF/grade_gsplat.py | Same arguments | `--out`, then a separate damaged copy | JSON verdict HOST-ERROR |
| roundNC/grade_nc.py | Same arguments | `--out` | JSON verdict HOST-ERROR |
| roundGF/grade_selfrun.py | The fixture's vector argument array | A fresh directory per vector | JSON verdict HOST-ERROR |
| roundGF/grade_hardcopy.py | No program execution | Reads existing artifacts | Not applicable |

`--prog-arg` passes one value without shell parsing. Use `--prog-arg=--flag` for values that start with a dash.

`--prog-args` retains shell-string compatibility. The grader appends each `--prog-arg` value after that string.

The output directory must be new or empty. It must be outside any Git checkout.
The grader never removes an existing output directory. Use a fresh path for each rerun.

Inspect each program before execution. Check network calls, child processes, deletion, and paths outside the scratch directory.
Copy only the fixture and the reviewed program into that directory.
Python reruns use isolated mode and UTF-8 text output (`python -I -X utf8`).
That changes some exit codes against the historical reruns: a program that
crashed on its own non-ASCII output on a cp1252 console now completes (for
example `roundDS/runs/dsv4__envel`, exit 1 before, 0 now). It removes a host
artefact; it is still a change, and a rerun record says which mode it used.

The full-task verdicts of `roundGF/grade_gsplat.py` and `roundOW/grade.py
--require-primary` are post-hoc re-grades, stricter than the criteria the
rounds declared before they ran. They are reported beside the recorded
verdicts and never replace them.

A launch failure is a host error. A timeout is a program failure.
A completed program with a nonzero exit cannot receive PASS.
Keep the original verdict beside every post-hoc verdict.

The frozen negative-control grader at `504a9ac` keeps its original interface.
The revised grader is in `evidence/second-lab/roundNC/` (PR #8), after the freeze.
