# Attempt ledger schema

One JSON object describes one attempt. The attempt identifier is unique.
A resumed session stays in its original attempt. A replacement run gets a separate row.
An internal feedback iteration stays within its attempt. `retry_index` identifies a replacement attempt.

| Field | Meaning |
|---|---|
| attempt_id, lab, date, round, task | Identity and task group |
| date_precision | A day or the documented round date |
| fixture_name, fixture_sha256, fixture_size | Original fixture identity, when recorded |
| fixture_hash_prefix | A published shortened hash when the full hash is unavailable |
| fixture_location, fixture_status | A matching local file, or a missing or unknown input |
| fixture_inputs | All files supplied for a multi-file task |
| agent_created_files | Files an agent made during its trial, kept apart from the supplied inputs |
| prompt_file, prompt_sha256, prompt_hash_basis | Retained prompt or current source copy, with its hash basis |
| model, model_version, cli, cli_version, settings | Recorded model and harness configuration |
| retry_index, wall_clock_seconds, cost_usd | Attempt timing and cost |
| isolation_class | The original audit classification |
| original_verdict, original_verdict_source | The historical verdict and its evidence |
| corrected_verdict, score_version, correction_reason | A separate post-hoc result |
| excluded, exclusion_reason | Whether the attempt contributes to task denominators |
| artifact_location | Retained artifact or source record |
| damage_payload, damage_spec | Independent damage results, when measured |
| missing_metadata | Fields the source does not establish |
| corrected_verdict_source, corrected_input_basis, rerun_evidence | Evidence for the post-hoc result, when a re-run exists |
| contamination_limit | A limit on what a PASS can show, when one applies |
| fixture_reference_correction | A note on a corrected fixture record |

`null` means unknown or not yet measured. It does not mean zero or FAIL.
The original verdict is never replaced by a correction.
The source's original wording is retained where it gives a qualified verdict.

Path prefixes:

| Prefix | Resolves to | Checker option |
|---|---|---|
| `repo:` | This repository | `--source-repo` (default: the repository that holds this file) |
| `<second-lab>/` | The second lab's local working folder | `--workspace` |
| `<second-lab>/gauntlet-sealed/` | The second lab's sealed trial folders | `--sealed` |
| `<scratch>/` | The second lab's local re-run folders | `--scratch` |
| `C:/Users/<user>/` | The home folder of the current user | none |

Paths outside `repo:` identify local files. They are not in this repository.
`<user>` replaces the local user name.
The checker puts the current home folder in place of `C:/Users/<user>`.
No transcript or injected account context is stored in this ledger.

Run the checker from the repository root:

```
python results/second-lab/ledger/check.py --workspace <your copy of the second-lab folder> --output check.json
```

The checker verifies every available fixture and prompt hash.
It reports missing files and checks mapped aggregate counts.
It also lists count statements that still need an explicit mapping.
The checker scans the paper and second-lab report for unmatched count statements.
A scope mapping does not establish a numerator. Each unreproduced ratio has a separate reason.
UNAVAILABLE is a grading decision when no executable program remains. HOST-ERROR identifies a host execution block.
Damage records distinguish exit status, named damage, intact extraction and explicit false verification claims.
Current substitutes have their own input hashes. They never replace original fixture identities.
