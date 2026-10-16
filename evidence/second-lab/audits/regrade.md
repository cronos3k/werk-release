# Re-grade of retained attempts

All 68 retained attempts have a recorded grading decision.
Sixty-two have a revised result. Six lack retained executable programs and remain UNAVAILABLE.
UNAVAILABLE means the evidence cannot support an independent rerun. It is not an agent failure.
The original verdict remains unchanged in every ledger row. Current substitutes never establish historical-input equality.

The revised mesh scorer verifies resolved primary bytes. Full-task decisions also require listing and declared-hash verification.
PARTIAL preserves a correct mesh or missing non-extraction clauses. The source criteria are in `<second-lab>/blind-regrade/CRITERIA.md`.
Envelope decisions compare the two stored records, rather than counts alone. Seven splat decisions reuse the existing full-task report.
Hardcopy decisions use actual recovered bytes. Six diagnostic checks remain separate from the recovery verdict.
The self-run scorer now supplies only model data and tokenizer data. It does not supply expected output files.

| Attempt | Original | Revised | Input basis | Reason |
|---|---|---|---|---|
| author/roundDS/dsv4__envel | "decoded", explicitly not a clean spec-forcing pass (S-DS-8) | PASS | original recorded bytes | Both pose records match. The embedded answer key still prevents a clean specification-forcing inference. |
| author/roundDS/dsv4__selfrun | FAIL (grade B 0/2, no binary) | PASS | Retained MSVC command on the current host | Reconstructed retained compile command and invoked the binary for both stored vectors. |
| author/roundOW/glm46vflash__mini__retry | PASS | PARTIAL | labelled current-fixture substitute | The node listing is absent. |
| author/roundOW/glm47flash__mini__retry | PASS* (cap raised 16k->32k) | PARTIAL | labelled current-fixture substitute | The node listing and full hash verification are absent. |
| author/roundOW/postfix-glm46vflash__mini | PASS | PARTIAL | original recorded bytes | Only two entries are listed and verified. |
| author/roundOW/postfix-llama31-8b__mini | FAIL (descriptor JSON as sound) | PARTIAL | original recorded bytes | The sound output contains its descriptor, rather than the payload. |
| author/roundOW/qwen3coder30b__mini | PASS | PARTIAL | labelled current-fixture substitute | The program checks ZIP CRC rather than every declared SHA-256 digest. |
| author/round1/python | SUCCESS | UNAVAILABLE | not rerun | No retained standalone program for an independent rerun. Historical input recovery does not supply the missing program. |
| author/round1/javascript | SUCCESS | UNAVAILABLE | not rerun | No retained standalone program for an independent rerun. Historical input recovery does not supply the missing program. |
| author/round1/rust | SUCCESS | UNAVAILABLE | not rerun | No retained standalone program for an independent rerun. Historical input recovery does not supply the missing program. |
| author/round1/c | SUCCESS | UNAVAILABLE | not rerun | No retained standalone program for an independent rerun. Historical input recovery does not supply the missing program. |
| author/round3/splat | SUCCESS | UNAVAILABLE | not rerun | No retained standalone program for an independent rerun. Historical input recovery does not supply the missing program. |
| author/roundXV/openai-gsplat | SUCCESS | FAIL | labelled current-fixture substitute | Complete point table absent. Reused existing full-task report. Original scoring scope differs. |
| author/roundXV/moonshot-gsplat | SUCCESS | FAIL | labelled current-fixture substitute | Complete point table absent. Reused existing full-task report. Original scoring scope differs. |
| author/roundSR/kimi | SUCCESS | HOST-ERROR | MSVC substitute for the original MinGW recipe | Windows application control blocked the reconstructed binary after one retry. |
| second/august/mesh-image | PASS | UNAVAILABLE | not rerun | No retained standalone program for an independent rerun. Historical input recovery does not supply the missing program. |

The table includes changed scope and unavailable results. SUCCESS is normalized to PASS for this comparison.
Qualified historical labels keep their original wording. Do not pool original, substitute and unavailable results.

| Revised decision | Attempts |
|---|---|
| FAIL | 21 |
| HOST-ERROR | 1 |
| PARTIAL | 14 |
| PASS | 26 |
| UNAVAILABLE | 6 |

Evidence: `<scratch>/reruns-20261012/results.json` and `<scratch>/special-20261012c/`.
