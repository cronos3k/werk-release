# Scoring rubric for the re-grade

This page gives the rules behind every changed verdict in [regrade.md](regrade.md).
The ledger keeps each original verdict. The rubric decides only `corrected_verdict`.

## 1. General rules

1. The program decides, not the agent's report. The final program is run again in a clean folder that holds only the fixture and the program.
2. Bytes decide. An extracted file counts only if its SHA-256 equals the digest that the package declares.
3. Text clauses (the listing, the damage messages) are read from the program output and from the text files that the program writes. The agent transcript is not read for this, because it contains the inlined spec.
4. Verification is tested by behaviour, not by printed words. One byte is changed in a payload file, and in a second copy one byte is changed in a spec file. The program must name the changed file next to an error signal.
5. An attempt without a retained program is UNAVAILABLE. This is not an agent failure.

The criteria were written before grading, on 2026-10-05 (tasks T1 to T6, [criteria-2026-10-05.md](criteria-2026-10-05.md)). Two amendments were made during grading, before any verdict was read. The rules below are those criteria, made mechanical.

## 2. Round-1 task (open, list, verify, extract the primary mesh and one sound)

| Measurement | How it is measured |
|---|---|
| Mesh | A fresh output file has the declared digest of the primary mesh (`geometry/game.glb`). |
| Sound | A fresh output file has the declared digest of a `.wav` of the sound node. |
| Listing | Number of manifest node ids that occur in the output, against the number of nodes. |
| Payload damage named | With one payload byte changed, an output line names that file and has an error signal (`mismatch`, `fail`, `error`, `computed`, `expected`, `corrupt`, `invalid`, `bad`, `differ`, `!=`). |
| Spec damage named | The same test, with one byte changed in `spec/MINI-SPECS.md`. |

| Verdict | Rule |
|---|---|
| PASS | Mesh and sound match, every node is listed, and both damage tests name the changed file. |
| PARTIAL | Mesh and sound match, but the listing is incomplete or a damage test fails. Or only one of mesh and sound matches. |
| FAIL | Neither mesh nor sound matches. |

[rubric_check.py](rubric_check.py) applies these rules to the stored re-runs. Result: 31 round-1 attempts, 0 differ from the ledger. Per-attempt values are in [rubric-check.json](rubric-check.json).

## 3. The four PASS to PARTIAL downgrades

| Attempt | Mesh, sound | Nodes listed | Payload damage named | Spec damage named | Rule that fails |
|---|---|---|---|---|---|
| author/roundOW/glm46vflash__mini__retry | match, match | 0 of 14 | yes | yes | listing |
| author/roundOW/glm47flash__mini__retry | match, match | 3 of 14 | no | no | listing, verification |
| author/roundOW/postfix-glm46vflash__mini | match, match | 2 of 14 | yes | no | listing, spec verification |
| author/roundOW/qwen3coder30b__mini | match, match | 14 of 14 | no, and it reports the damaged sound as verified | no | verification (it checks ZIP CRC, not the declared SHA-256) |

For comparison, all 9 second-lab round-1 trials (batch 1, batch 2 and the werk arm of the negative control) list every node and name both damaged files.

## 4. Other changed verdicts

| Attempts | Change | Rule |
|---|---|---|
| author/roundXV/openai-gsplat, author/roundXV/moonshot-gsplat | SUCCESS to FAIL | Full splat task: the complete point table (all 281,498 points) must be on disk, and the flipped-byte damage test must pass. No complete point table exists. The original prompt asked for "a sample", so the original scope differs. Numeric sub-checks are unchanged. |
| author/round1 (python, javascript, rust, c), author/round3/splat, second/august/mesh-image | SUCCESS or PASS to UNAVAILABLE | No retained standalone program. |
| author/roundSR/kimi | SUCCESS to HOST-ERROR | Windows application control blocked the rebuilt binary. |
| author/roundOW/postfix-llama31-8b__mini | FAIL to PARTIAL | The mesh matches. The sound output is the descriptor JSON, not the payload. |
| author/roundDS/dsv4__selfrun | FAIL to PASS | The retained compile command was run, and the binary reproduced both stored vectors. |
| author/roundDS/dsv4__envel | "decoded" to PASS | Both pose records match an independent decode. The worked example in the spec still holds the same answer (S-DS-8). |

## 5. Limits

- One person wrote the criteria, collected the second-lab evidence and graded it. The criteria predate the grading, but the grading is not blind.
- Re-runs of 18 author attempts use the current fixture, not the historical one. The ledger labels these inputs "labelled current-fixture substitute".
- Correction on 2026-11-11: the damage flags of author/roundXV/openai were wrong. The earlier keyword rule missed its "declared ..., computed ..." messages. Both flags are now "yes". Its verdict stays PASS.
- Three author envelope rows carry task `mini` (the fixture name) in the ledger. The rubric check selects round-1 rows by prompt file.
