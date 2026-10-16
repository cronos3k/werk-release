# Second-lab evidence

This folder holds the evidence from an independent second lab.
The core is an attempt ledger: one row per agent attempt, across both labs.
"Author" rows are the original rounds. "Second" rows are the second-lab trials.

| Count | Value |
|---|---|
| Rows in the ledger | 81 |
| Retained attempts | 68 |
| Excluded records (discarded or interrupted runs, one model that did not load, expired logins, seal checks) | 13 |

## How to read a row

Each line of [ledger/attempts.jsonl](ledger/attempts.jsonl) is one JSON object.
[ledger/SCHEMA.md](ledger/SCHEMA.md) explains every field.

- `original_verdict` is the historical verdict. A correction never replaces it.
- `corrected_verdict` is a separate post-hoc result, with its reason and evidence.
- `null` means unknown or not measured. It does not mean zero or FAIL.
- `excluded: true` means the record does not count in task denominators.

## What each folder holds

| Path | Contents |
|---|---|
| [ledger/](ledger/) | The attempt ledger, its schema, the fixture inventory, the count mappings and the checker |
| [audits/](audits/) | Short notes and data for each audit step (see below) |
| [locks/](locks/) | Environment pins: installed packages, interpreters, the Cargo lock and per-builder sources |
| [clause-coverage.md](clause-coverage.md) | One row per gate clause, with its input basis and evidence |
| [reproducibility.md](reproducibility.md) | Which environment each exact-byte claim needs |
| [log-policy.md](log-policy.md) | How the trial logs were redacted, and how to request them |

| Audit note | Topic |
|---|---|
| [audits/attempt-inventory.md](audits/attempt-inventory.md) | Ledger size, hash checks and count checks |
| [audits/hash-and-count-check.json](audits/hash-and-count-check.json) | Checker output from the original host |
| [audits/regrade.md](audits/regrade.md) | The re-grade of all 68 retained attempts |
| [audits/damage-probes.md](audits/damage-probes.md) | One-byte damage probes on each retained program |
| [audits/damage-evidence.json](audits/damage-evidence.json) | Per-attempt damage probe data |
| [audits/gate-coverage.md](audits/gate-coverage.md) | Summary of the clause coverage table |
| [audits/environment-pins.md](audits/environment-pins.md) | Summary of the environment pins |
| [audits/sanitised-logs.md](audits/sanitised-logs.md) | Summary of the redacted trial logs |
| [audits/redaction-check.json](audits/redaction-check.json) | Redaction counts and checks |
| [audits/audit-summary.json](audits/audit-summary.json) | Totals across all audit steps |

## How to run the checker

Run it from the repository root. It needs Python 3 and no extra packages.

```
python results/second-lab/ledger/check.py
```

The checker does these steps:

1. It confirms that each attempt identifier is unique.
2. It hashes every fixture and prompt file that it can find.
3. It checks 20 aggregate attempt counts against the ledger.
4. It checks count statements in the paper and results files against their mappings.

Files that are not on your machine show as unavailable. They are not errors.
Some large fixtures are not in Git. [fixtures/DOWNLOADS.md](../../fixtures/DOWNLOADS.md) lists them.
Until you download them, they also show as unavailable.
Use `--output check.json` to save the full result.

## Path placeholders

Paths that start with `repo:` point into this repository.
Other paths point to local files on the second-lab machine.

| Placeholder | Meaning | Checker option |
|---|---|---|
| `<second-lab>/` | The second lab's local working folder | `--workspace` |
| `<second-lab>/gauntlet-sealed/` | The sealed trial folders | `--sealed` |
| `<scratch>/` | The local re-run folders | `--scratch` |
| `C:/Users/<user>/` | The local home folder | none |

## What stays local

These items are not in this repository. They are available on request from the second lab.

- The redacted trial logs (26 sessions). [log-policy.md](log-policy.md) explains the redaction.
- The sealed trial folders, with each agent's program and output.
- The re-run and damage-probe scratch folders.
- The grading reports that the ledger cites under `<second-lab>/`.
