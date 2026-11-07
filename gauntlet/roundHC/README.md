# `roundHC/` — hardcopy archaeology

A werk file, printed on three sheets of A4, recovered from photographs of those
sheets by an agent that was told nothing except "these are photographs of a
printed document".

Design: **`../../docs/HARDCOPY-DRAFT.md`**. Full record and every measured
number: **`../../results/STAGE-HARDCOPY-RESULTS.md`**. Summary row:
**`../RESULTS.md`**, "hardcopy round".

| file | what it is |
|---|---|
| `make_smiley.py` | the payload's picture: a 64×64 indexed-colour PNG of a smiling face, written out of `zlib` and `struct` so the bytes are identical on every machine. 315 B. |
| `build_smiley_werk.py` | builds `smiley-v1.werk` — profile `image/1`, 8168 B, `signed-and-valid`, every mandatory manifest key present. **Deliberately reduced**: no vendored `spec/`, no `loaders/`, and its own `README.txt` says so and why. |
| `smiley-v1.werk` | the payload. sha256 `b0823016…7617a6`. |
| `wcode.py` | **werk-hardcopy/1**: the matrix code. Encoder, renderer, and the reference decoder — which is written only from what the printed prose says, and is therefore the experiment's control. |
| `prose/PROSE.txt` | the printed text, verbatim. Three sheets, separated by a line holding `\f`. Sheets 1–2 are the complete decoder description; sheet 3 carries reassembly, what a werk package is, and the symbols. |
| `make_pages.py` | renders the three A4 sheets at 300 DPI into `pages/clean/`. |
| `degrade.py` | the **scanned** arm: rotation, blur, illumination ramp, noise, JPEG → `pages/scanned/`. Every parameter fixed in the file. |
| `verify_roundtrip.py` | the control run: decode the pages, reassemble, check the sha256, open the package, re-verify every declared hash, and compare the recovered PNG pixel for pixel against `make_smiley.py`'s output. |
| `PROMPT-archaeology.txt` | the task sentence, verbatim, committed before the run. No format hint. |
| `run_codex.sh` | one Codex run in a neutral directory holding only the page images. 60-minute cap, process wall clock recorded. |
| `runs/` | per attempt: the JSONL transcript, stderr, timing, and everything the agent left on disk. |

## Reproduce

```
python make_smiley.py
python build_smiley_werk.py
python make_pages.py
python degrade.py
python verify_roundtrip.py                    # the degraded arm
python verify_roundtrip.py --pages pages/clean
```

Dependencies: Python 3.12, Pillow, and one monospace TrueType face. No numpy,
no barcode library, and nothing at all beyond the standard library for the
encode/decode of codewords and matrices.
