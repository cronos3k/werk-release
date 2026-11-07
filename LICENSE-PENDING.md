# Licence — not decided

This repository has **no LICENSE file yet**, on purpose. Gregor Hubert Max Koch
has not chosen the licence for the specification, the code and the loaders.
Until he does, no licence is granted by this repository beyond what copyright
law allows, and no file's own licence header was changed while it was assembled.

## The candidates on record

| Where it was stated | Licence |
|---|---|
| The private lineage's `README.md` (§ License) | Documents CC BY-SA 4.0; specification "open"; reference implementation **PolyForm Noncommercial 1.0.0** (commercial licensing via the authors). |
| The earlier public snapshot (`cronos3k/werk` `main` `6d547d0`), `LICENSE` | **Mozilla Public License 2.0** for code and specification, with a separate `TRADEMARK.md` naming policy for "werk" and `.werk`. |

## Inconsistencies a decision has to resolve

* `core/Cargo.toml` declares `license = "MIT"` for `werk-core` (unchanged here).
  It matches neither candidate.
* Third-party material keeps its own terms regardless of the decision: the
  vendored `tools/vhacd/VHACD.h` and `tools/mikktspace/`, the Khronos and CMU
  test data under `retarget/testdata/` (see the READMEs beside them), and the
  CC0 sources under `fixtures/sources/`.
* Each fixture carries a `core.license` node for its *content*; those are
  content licences inside the packages and are not affected by this file.
* `TRADEMARK.md` from the public snapshot was written for MPL-2.0 and was not
  carried over; it returns with the decision if MPL-2.0 is chosen.
