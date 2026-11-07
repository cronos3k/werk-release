# Incoming paper changes — parked, not applied

Two pull requests by Yuvraj Puyam change the paper. The paper is owned by a
separate edit (workstream W7), so they are **parked here as his patch series,
unapplied**. Each `.patch` is `git format-patch` output and carries his
authorship, dates and messages.

| Folder | PR | What | Review (summary) |
|---|---|---|---|
| `pr9/` | #9 | `results/SECOND-LAB-REPLICATION.md` (new) and a proposed §7 paragraph in `paper/v2/PAPER.md` | report: merge after changes ("rounds 4 to 9" → 4 to 7; the controls were not "the same CC0 crate"; Gate 12 FAIL/SKIP counts; ~40 numbers without `NUMBERS.md` rows; "end to end" overreaches); the §7 paragraph needs Gregor's wording |
| `pr10/` | #10 | corrections M1, M2, M4, M7, M8, M9, M10, M11 to `paper/v2/PAPER.md` and `NUMBERS.md` | merge after changes (M9 incomplete: abstract and three lines still say printed and photographed; M10 count vs source; M1/M2/M10 need §12 ledger rows; Q6 second error) |

The patches were written against the earlier public snapshot's paper text,
which differs in wording from `paper/v2/PAPER.md` here (the private
lineage's original). They will not apply as they are; port them by hand.
