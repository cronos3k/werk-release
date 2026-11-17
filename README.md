# werk

**Self-carrying digital artifacts.** A werk file is hermetic (contains
everything it needs), self-describing (contains the knowledge required to
read it), self-historied (contains its own versions and the reasons for
them), and self-attributed (contains its authorship, cryptographically).

> A digital artifact should bring all its logic along for a consumer to
> use, rather than to set up painfully after the fact.

This repository is the first public release candidate: the specification,
the reference implementation, the single-file readers, the fixtures and their
builders, every gate harness, and the recorded evidence. It was assembled from
the author's private lineage; `RELEASE-ASSEMBLY.md` says from what and how.

## What is where

| Path | What |
|---|---|
| [MANIFESTO.md](MANIFESTO.md) | The twelve laws. Read this first. |
| [spec/](spec/) | The specification: `SPEC.md`, `MINI-SPECS.md`, the JSON schemas, the byte layouts, format definitions, writing walkthroughs. Every package carries a copy. |
| [SPEC-3D-ENTITY.md](SPEC-3D-ENTITY.md), [WHITEPAPER.md](WHITEPAPER.md) | Profile overview and the short argument. |
| [loaders/](loaders/) | Single-file, dependency-free readers: `werk_read.py`, `werk_read.rs`, `werk_read.c`. |
| [core/](core/) | The reference core (Rust, `werk-core`): a C ABI (`include/werk.h`), the `werkc` CLI, conformance tests. |
| [bindings/python/](bindings/python/) | Python over the core's C ABI (ctypes, no pip dependencies). |
| [store/](store/), [pipeline/](pipeline/), [retarget/](retarget/), [tools/](tools/) | The content store, the enrichment pipeline, the retargeter, helper tools. |
| [plugins/](plugins/) | Host plug-ins, each gated in the real host: Blender 4.2, GIMP 3, Unreal Engine 5.8.2 (WerkLink; 5.7 untested), Photoshop 2020 (21.0.3; 2024 self-test only), Illustrator 2020, After Effects 2020, Office 2016 (`werk-office` CLI). Results in each folder's `GATE-RESULTS.md`; overview in [plugins/README.md](plugins/README.md). |
| [libs/](libs/) | Read/write libraries: Python (package + single file, stdlib only), JavaScript (ES2017 + ES3 for ExtendScript); `werkc` release commands live in `core/`. |
| [contrib/experimental/](contrib/experimental/) | Untested contributions (Photoshop UXP plug-in). |
| [fixtures/](fixtures/) | Conformance fixtures, their builders, and their pinned hashes (`fixtures.json`, `FIXTURES.md`, `CC0-FIXTURES.md`). |
| [tests/](tests/) | The gate harnesses (`run_gate*.py`). |
| [gauntlet/](gauntlet/) | The agent-implementability protocol and the committed run records. |
| [evidence/second-lab/](evidence/second-lab/) | The independent second-laboratory data (exploratory). |
| [results/](results/), [docs/](docs/) | Per-stage result ledgers and the rulings. |
| [paper/](paper/) | The paper drafts. |
| [RELEASE-ASSETS.md](RELEASE-ASSETS.md) | Files kept out of git (large fixtures, scans), hash-pinned. |

## Build and test

```
cd core
cargo test --release            # the reference core
cargo build --release           # werk.dll / libwerk.so, used by the gates
cd ..
python tools/fetch_fixtures.py  # the large fixtures listed in RELEASE-ASSETS.md
python tests/run_gate.py        # and every other tests/run_gate*.py
```

The public-domain (CC0) fixtures and their gates (`tests/run_gate_cc0_*.py`)
need nothing outside this repository. Some clauses of other gates rebuild a
fixture from the author's own inputs; those clauses look under the directory
named by the `WERK_LAB` environment variable and report SKIP when it is unset.

The gates assume the host grants the privileges a normal developer box has:
executing freshly built binaries and filesystem access. A missing toolchain
(rustc, a C compiler, Blender, an engine) is reported **SKIP**, and a SKIP is
not a PASS. On Windows 11, Smart App Control blocks freshly compiled unsigned
binaries (`os error 4551`); those failures are the host, not the format.

## Licence

Not decided yet. See [LICENSE-PENDING.md](LICENSE-PENDING.md).

Gregor Hubert Max Koch · Ken Gamble — 2026
