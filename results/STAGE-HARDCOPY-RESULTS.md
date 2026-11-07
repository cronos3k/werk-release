# Stage HARDCOPY results — a werk file printed on paper, and recovered from photographs of it

**Author:** the hardcopy round agent. **Owns for this wave:**
`gauntlet/roundHC/`, `docs/HARDCOPY-DRAFT.md`,
`results/STAGE-HARDCOPY-RESULTS.md`, and the hardcopy rows in
`paper/v2/NUMBERS.md` and `paper/v2/CHANGES.md`. **Nothing under `spec/` or
`fixtures/` was read-modify-written by this wave, and no existing fixture was
touched.**

**Date:** 2026-08-09.

---

## 0. What this round exists to test

Every previous round handed an agent **the file**. The container was a zip
because zip readers exist everywhere; the manifest was JSON because JSON parsers
exist everywhere. So "the file explains itself" has never been separated from
"the substrate already knows how to open it".

Paper separates them. A printout has no zip library, no JSON parser and no
bytes — only ink. The round therefore prints a werk package as two tiers on
three sheets of A4: a **prose tier** in plain text, and a **payload tier** of 2D
barcodes, where the **printed prose is the only specification of the barcode**.
Then it hands a fresh agent photographs of the sheets and one sentence that
names no format.

The chain under test, end to end:

> **printed prose → a decoder the reader implements → the barcodes → a byte
> stream → a hash that matches → a file that opens → a smiling face.**

Design document: **`docs/HARDCOPY-DRAFT.md`** (a DRAFT; it is not a `spec/`
edit and nothing in it is normative). Everything below is measured.

---

## 1. Headline

| | |
|---|---|
| Serialization | **`werk-hardcopy/1`** — a purpose-built matrix code, **not QR**, designed to be describable in two printed pages (§2) |
| Payload | **`gauntlet/roundHC/smiley-v1.werk`**, 8168 B, profile `image/1`, `signed-and-valid`, carrying one 64×64 PNG of a smiling face |
| The whole artifact | **3 sheets of A4** — 2 sheets of prose, 1 sheet carrying the last of the prose plus all nine symbols |
| Test input | the **degraded** arm: rotation 0.55–0.90°, 1.1 px blur, illumination ramp to 62 %, σ=9 noise, JPEG q82 |
| Control (reference decoder, written only from the printed prose) | **PASS** on the degraded pages: 8/9 symbols read, **seq 7 repaired by the parity symbol**, sha256 exact, smiley pixel-identical over 4096 pixels |
| Archaeology run | **Codex CLI 0.144.1 / `gpt-5.6-sol`**, effort `high`, one fresh neutral directory holding **only the three JPEGs**, no format hint, 60-minute cap |
| **Success ladder** | **5 / 5** — see §5 |
| Prior barcode knowledge available to the agent | **none exists**: `werk-hardcopy/1` was invented for this round, so the printed prose is the only possible source |
| Density | **1112 file bytes per symbol**, **12 symbols on a symbols-only A4 sheet**, **11 861 file bytes per sheet** = **88.4 sheets per MiB** |
| New findings | **S-HC-1 … S-HC-6** |

---

## 2. The serialization, and why it is not QR

The load-bearing requirement in the brief is that the **printed prose be
sufficient to implement a decoder from scratch**. That, and not ubiquity or tool
support, decides the code.

**Assessed honestly, standard QR does not fit.** A conformant decoder needs
finder-pattern detection and perspective rectification; alignment patterns whose
centres come from a 40-row table; the 15-bit BCH(15,5) format information and its
mask; version information for versions ≥ 7; eight data masks plus the
penalty-scoring rule that selects among them; mode indicators and
character-count-indicator widths that vary by version band; a block-structure
table of 40 versions × 4 error-correction levels — **160 rows, none of it
derivable**; and Reed–Solomon over GF(256) with per-length generator polynomials
and a decoder (syndromes, Berlekamp–Massey, Chien, Forney). That is a
specification, not a page. Printing it would have made the artifact mostly a
transcription of ISO/IEC 18004.

**The second reason is the scientific one, and it is decisive.** If the code
were QR, the experiment could not distinguish *"read the printed prose"* from
*"recognised a QR code and called a library"*. Every capable implementer already
has QR decoding, so a success would have said nothing about the prose. A code
that has never existed removes the confound completely: **there is no library to
call and nothing to recall, so the prose is the only path.** That makes the
custom code the *clean* arm rather than the eccentric one, and it is why the
optional QR convenience arm was **deliberately not built** — building it would
have added a decoding path the archaeology arm might silently have taken.

The design rule that follows from "describable in two pages" is **no mechanism
whose specification is a table**. What replaced each QR mechanism is tabulated in
`docs/HARDCOPY-DRAFT.md` §2. The summary:

```
W = 99 modules per side, plus a white quiet zone at least 4 modules wide

ring 0   r or c in {0, 98}      SOLID BLACK -- the locator frame
ring 1   r or c in {1, 97}      WHITE, except (1,1), (1,2), (2,1) BLACK:
                                the orientation elbow, marking top-left
data     rows 2..96, cols 2..96 95 x 95 = 9025 module positions
                                -> 1128 bytes, row-major, MSB first, black = 1

codeword: "WK" | version | kind | seq u16 | total u16 | file_len u32 |
          crc32 u32 | 1112 payload bytes                     (big-endian)

error control: CRC-32 per symbol turns corruption into ERASURE;
               XOR parity over each group of 8 data symbols turns
               erasure into RECOVERY.  Overhead 1/9 = 11.1 %.
```

**The trade is stated plainly: `werk-hardcopy/1` cannot correct a bit error
inside a symbol, where QR can.** It detects it, discards the symbol, and rebuilds
that symbol from the group's parity. That is a *worse* code and a *describable*
one, and describability is the requirement here.

One measured surprise: the describable code is **not** less dense.

| code | modules | payload bytes | bytes per module |
|---|---:|---:|---:|
| QR version 40, EC level L | 177×177 = 31 329 | 2 953 | **0.09426** |
| `werk-hardcopy/1`, raw | 99×99 = 9 801 | 1 112 | **0.11346** |
| `werk-hardcopy/1`, net of the 1-in-9 parity symbol | 9 801 | 988.4 | **0.10085** |

So it is **1.07× denser than QR-L even after paying for parity** — because it
spends nothing on in-symbol error correction. Density was bought with fragility,
not with cleverness, and that is the honest reading.

---

## 3. The artifact: three sheets, and the page arithmetic

### 3.1 The payload

`gauntlet/roundHC/smiley-v1.werk`, built by `build_smiley_werk.py` from
`make_smiley.py`'s output and nothing else.

| | |
|---|---|
| bytes | **8168** |
| sha256 | `b0823016712e4770e01870f709b10a0fd3d4aaf08753d714092038d84d7617a6` |
| profile | `image/1`; validates against `spec/schemas/manifest.image.schema.json` |
| entries | 5 — `MANIFEST.json` (4000 B), `SIGNATURE.json` (1002 B), `LICENSE` (1073 B), `README.txt` (1256 B), `image/smiley.png` (315 B) |
| signature | **`signed-and-valid`**, verified with `store/werkstore/signature.py` |
| the picture | 64×64, indexed colour, 3-entry palette, 315 B, generated from integer arithmetic in `zlib` + `struct` so the bytes are identical on every machine |

**It is a deliberately REDUCED package and says so in its own `README.txt`.** It
vendors no `spec/` tree and no `loaders/`, so `schemas` is `{}` and `spec_sha256`
is `e3b0c442…b855` — the declared algorithm's correct value over the empty file
set, not a placeholder. The reason is arithmetic: the smallest `spec/` tree in
this repository (`mini-v1.werk`'s) is 252 KB, which is **22 sheets of paper**, to
restate on ink what sheet 1 is already saying in plain language. The package's
`README.txt` tells whoever recovers it exactly this, including that "the
specification travels on that paper", so the reduction is declared to the reader
and not merely to the repository.

### 3.2 The sheets

Three A4 sheets at 300 DPI, 2480 × 3508 px each.

| sheet | contents |
|---|---|
| 1 | what the document is; **file length and SHA-256 in prose**; symbol geometry; modules→bytes; photograph handling — thresholding, finding symbols, finding corners |
| 2 | the two corner warnings; sampling and orientation; the codeword layout; **CRC-32 in full with a test vector**; the parity scheme |
| 3 | reassembly; what a werk package is; **the nine symbols with captions**; the SHA-256 again |

Measured layout: **Consolas at 7.8 pt (32 px), 39 px leading, widest line 96
characters**; symbol module **6 px = 0.508 mm**, symbol block **642 px =
54.4 mm** square including its quiet zone; nine symbols in a 3×3 grid, each
captioned `SEQ n/9  DATA|PARITY  CRC xxxxxxxx`.

### 3.3 Density — "how many sheets is a werk file"

A sheet given over entirely to symbols (60 px margins, 28 px gap, 44 px caption)
holds **3 columns × 4 rows = 12 symbols**.

| quantity | value |
|---|---|
| payload bytes per symbol | **1112** (codeword 1128 B; 16 B header = 1.42 % overhead) |
| parity overhead | **11.11 %** (1 parity symbol per 8 data symbols) |
| symbols per symbols-only A4 sheet | **12** |
| **file bytes per symbols-only A4 sheet** | **11 861** (11.58 KiB) |
| **sheets per MiB** | **88.4** |

Applied to the fixtures this repository actually ships:

| package | bytes | data + parity symbols | symbols-only sheets |
|---|---:|---:|---:|
| `gauntlet/roundHC/smiley-v1.werk` | 8 168 | 8 + 1 = **9** | **1** |
| `gauntlet/roundOW/mini-v1.werk` | 960 061 | 864 + 108 = 972 | **81** |
| `fixtures/crate-v1.werk` | 13 684 477 | 12 307 + 1 539 = 13 846 | **1 154** |
| `fixtures/gsplat-v1.werk` | 30 235 611 | 27 191 + 3 399 = 30 590 | **2 550** |

**That is the number to quote and it is not flattering: a real werk package is a
ream of paper.** The 3D-entity fixture is 1 154 sheets; the splat fixture is
five reams. Paper is a proof of self-description, not an archival
recommendation, and §7 says so.

---

## 4. The control — the reference decoder, written only from the printed prose

`gauntlet/roundHC/wcode.py`'s decoder is the experiment's control. It was
written against the printed text and nothing else, and run against the
**degraded** pages before any agent saw them, so that a failure by the agent
would be a statement about the prose rather than about the paper.

```
$ python verify_roundtrip.py                       # pages/scanned, the degraded arm
page-01.jpg      regions=0   sampled=0   frame_reject=0   crc_fail=0   decoded=0
page-02.jpg      regions=0   sampled=0   frame_reject=0   crc_fail=0   decoded=0
page-03.jpg      regions=9   sampled=9   frame_reject=0   crc_fail=1   decoded=8
assemble: {"seen": 8, "recovered_by_parity": [7], "missing": [], "total": 9, "file_len": 8168}
recovered 8168 bytes, sha256 b0823016712e4770e01870f709b10a0fd3d4aaf08753d714092038d84d7617a6
sha256 matches payload: True
opens as a werk package: profile=image/1 entity='Smiley' entries=5
  README.txt           1256   hash OK
  LICENSE              1073   hash OK
  image/smiley.png     315    hash OK
smiley bytes identical to make_smiley.py: True
pixel differences over 4096 pixels: 0
decode wall clock: 6.9 s
RESULT: PASS
```

The clean arm decodes 9/9 with no CRC failure and needs no parity.

**The parity symbol did real work on the very first honest run, and the symbol
it saved is the interesting one.** `seq 7` is the last data symbol, so most of
its 1112 bytes are the zero padding — which prints as a nearly blank data area.
A nearly blank area gives the local thresholder tiles with no contrast in them,
the fallback threshold then admits noise as ink, and the CRC fails. **The
symbol whose content is emptiest is the one hardest to read**, which is the
opposite of the intuition, and it is why the parity tier is in the design rather
than an afterthought (**S-HC-3**).

### 4.1 Two decoder facts the control discovered, and both are now printed

This is the round's most transferable result, so it is recorded as method rather
than as an anecdote. **Prose that describes a code is itself a program, and it
has bugs; the only way to find them is to implement the decoder from the prose
alone and run it against a degraded photograph.** Two bugs were found that way,
and the fix in each case was to the *printed sheet*.

1. **"Topmost, rightmost, bottommost, leftmost, ties broken by the
   perpendicular extreme" is wrong at small angles.** A 600-pixel edge six
   pixels thick, tilted one degree, has some hundreds of pixels sharing the same
   smallest column, so any tie-break among them lands most of the way down the
   edge. Measured: the four "corners" gave side lengths **470 / 237 / 497 / 125**
   pixels for a symbol whose side is **593**, and the sampled ring-0 score
   collapsed from 1.000 to **0.390**. The printed prose now says to take the
   extremes of **x+y and x−y**, and prints the warning and the reason.
2. **The frame must not be assumed to be one connected piece.** Under the
   illumination ramp, binarisation breaks it into several. Using only the
   *largest* connected group put 4 of 9 symbols out of geometry. The printed
   prose now says to gather every connected group above a few-hundred-pixel
   floor inside the widened box — which in one rule also discards noise specks
   (a single speck in the quiet zone had moved a corner by tens of pixels) and
   any caption text that strayed into the box.

Both corrections are on sheet 1 with the word "WARNING" and the measurement that
motivated them. **A reader who is told only the happy path writes the decoder
that fails** (**S-HC-1**).

---

## 5. The archaeology run

**Setup.** Codex CLI **0.144.1** on **`gpt-5.6-sol`**, `model_reasoning_effort=high`,
`--sandbox workspace-write`. A fresh directory outside every werk repository
containing **only the three degraded JPEGs** — `page-01.jpg`, `page-02.jpg`,
`page-03.jpg` — and nothing else. The task sentence, committed before the run in
`gauntlet/roundHC/PROMPT-archaeology.txt`, verbatim and in full:

> These images are photographs of a printed document. Recover whatever the
> document contains and report what you find. Verify your recovery against any
> correctness information the document provides.

**No format hint.** The words "werk", "barcode", "zip", "PNG" and "decode" do
not appear in it.

**Measured wall clock: 206.7 s (3 min 27 s), process clock, `exit_code=0`.**
Token usage from the harness's own accounting: 681 627 input, 9 286 output, of
which 3 143 reasoning. One attempt; the permitted retry was not needed.

**Isolation, audited from the transcript rather than assumed.** The agent tried
`python -m pip install --target .\.deps numpy` and got
`ERROR: Could not find a version that satisfies the requirement numpy (from
versions: none)` — **there was no network**, and it proceeded with the standard
library plus Pillow. `grep -oic "http://|https://|qrcode|ISO/IEC|18004|reed.solomon"`
over the whole 45 654-byte JSONL transcript returns **0**. Nothing came from
outside the run directory.

### 5.1 The success ladder, graded by the orchestrator from the artifacts

Every row below was re-verified by this agent against the files the run left on
disk, not accepted from the report.

| # | step | verdict | evidence |
|---|---|---|---|
| 1 | **read the prose** | **PASS** | its second message, before writing any code, states "the embedded file is 8,168 bytes, split across eight data symbols plus one parity symbol, with per-symbol CRC-32 values and an overall SHA-256 `b0823016…7617a6`" — every one of those facts is printed prose |
| 2 | **implemented a decoder** | **PASS** | `decode_werk.py`, 6 414 B, written from scratch: connected components, corner extremes, the bilinear map with `u=(c+0.5)/99`, the 3×3 ≥5 vote, elbow orientation, rows 2..96 MSB-first, and the leftover-module-must-be-white check |
| 2b | **prose or prior knowledge?** | **PROSE, and it cannot be otherwise** | `werk-hardcopy/1` was invented for this round, so no library and no training data contains it. The agent cites it: "The printed pages themselves specify the complete recovery format: framing and orientation, 95×95 data layout, byte packing, codeword headers, CRC-32 algorithm, XOR parity repair, and final assembly." |
| 3 | **reassembled the byte stream, CRCs pass** | **PASS, 9/9** | every symbol's recomputed CRC equals both the CRC inside its codeword and the caption printed beneath it: `F616796C A64016D6 AC510CD2 9C35923F AE804266 3A153C58 63604E4D E20A2CD2` and parity `0E184BA8` |
| 4 | **whole-file sha256 matches the printed one** | **PASS** | orchestrator's own hash of `recovered.werk`: `b0823016712e4770e01870f709b10a0fd3d4aaf08753d714092038d84d7617a6`, and `recovered.werk` is **byte-identical** to `gauntlet/roundHC/smiley-v1.werk` |
| 5 | **recognised and opened the .werk** | **PASS** | reported it as "an 8,168-byte ZIP-compatible WERK 1.0 package named *Smiley*", listed all five entries, gave the entity uuid, profile and creation time from the manifest |
| 5b | **the recovered image IS the smiley** | **PASS** | it extracted `image/smiley.png`; orchestrator's check: identical to `make_smiley.py`'s reference bytes, **0 pixel differences over all 4096 pixels** |
| bonus | **verified every declared hash** | **PASS** | it hashed all three payload files against the manifest and checked `SIGNATURE.json`'s `manifest_sha256` against the recovered manifest; orchestrator re-ran the same check independently: all match |
| bonus | **the signature** | **CORRECTLY DECLINED** | see S-HC-4 |

**5 / 5, plus both bonuses, first attempt, 207 seconds.**

### 5.2 What it did that the printed prose did not say — and what that means

The honest version of "the prose was sufficient" is *which parts of it were
load-bearing*. Two of the seven printed steps were **not** implemented as
described, and the run is a cleaner result for saying so.

* **Step (a), the 64×64-tile local threshold, was not used.** The agent swept a
  single global threshold from 90 to 190 and found 90 worked for every symbol on
  the page. This is a property of the degradation model rather than a defect in
  the prose: the illumination ramp is multiplicative, so paper darkens from 255
  toward 158 while ink stays near 0, and one global threshold still separates
  them. The local recipe is belt-and-braces at this level of degradation and
  would start to matter under a shadow that darkens ink as well.
* **Step (b), finding symbols by connected regions across the whole page, was
  not used.** The agent looked at the image, wrote nine hard-coded crop
  rectangles, and ran the corner search inside each. That is a legitimate move
  for an implementer with eyes, and it means the round did **not** test the
  page-scan half of the prose. The reference decoder does implement it, and does
  so on all three sheets, correctly finding **0** symbols on sheets 1 and 2.

So the parts of the printed prose that were **measured to be load-bearing** are:
the symbol geometry, the orientation elbow, the module-to-bit rule and its bit
order, the codeword layout, the CRC-32 algorithm with its test vector, and the
reassembly-and-truncate rule. Those are precisely the parts that no amount of
looking at the picture would supply.

**And it improved on one printed rule.** Where the prose says to take *the*
pixel extremising x+y, the agent averaged all pixels within 1 of the extreme,
producing sub-pixel corners — which is why it read **9/9** symbols where the
reference decoder read 8/9 and needed the parity symbol. The printed rule is the
simplest correct thing; the agent found the obvious refinement unprompted. That
is what a specification is supposed to permit.

### 5.3 The discarded first run

A first run died before anything was graded and is kept as
`gauntlet/roundHC/runs/_discarded-sandboxbug/`. Codex's image viewer failed with
`failed to prepare windows sandbox wrapper: windows unelevated restricted-token
sandbox cannot enforce split writable root sets directly; refusing to run
unsandboxed` — the harness wanted the workspace *and* a temp directory as
writable roots. The agent, unable to see the pages, spent its time trying to
start a browser to view them. **This is an S-OW-5-class serving-stack failure and
scoring it as a format result would have measured the wrong thing.** The fix is
in `run_codex.sh`: `sandbox_workspace_write.exclude_tmpdir_env_var=true` and
`exclude_slash_tmp=true`, which leave **one** writable root and are therefore
*more* isolating than the default. It is recorded because a discarded protocol is
part of the experimental record.

---

## 6. Findings

**S-HC-1 — prose that describes a code is a program, and it has bugs; the only
way to find them is to implement the decoder from the prose alone and run it on
a degraded photograph.** Measured twice in this round, both times against the
first draft of the printed sheet. (a) "Topmost, rightmost, bottommost, leftmost,
ties broken by the perpendicular extreme" is *wrong* at small rotations: a
600-pixel edge six pixels thick tilted one degree has hundreds of pixels sharing
the smallest column, and the tie-break lands most of the way down the edge —
measured side lengths **470 / 237 / 497 / 125** for a symbol whose side is 593,
ring-0 score **0.390**. (b) Using only the *largest* connected group as the frame
fails under an illumination gradient that breaks the frame into pieces — 4 of 9
symbols out of geometry. Both are now printed as WARNINGs with their reasons.
**This generalises past the barcode:** every prose specification in `spec/` is in
the same position, and the only rounds that have found bugs in them are the ones
where somebody implemented from the prose and ran the result.
*Severity: method, and high value.*

**S-HC-2 — a self-describing printed artifact cannot use QR, and the reason that
matters is not size.** The size argument is real (§2: 160 rows of block-structure
table, eight masks with penalty scoring, BCH format information, Reed–Solomon
over GF(256) — not two pages). The *decisive* argument is experimental: a code
that already exists cannot distinguish "read the printed prose" from "called a
library", so a QR-based artifact could not have measured self-description at all.
**A format that wants to prove it explains itself must sometimes invent the thing
it is explaining.** Recorded as a design finding; the price is stated in §2 (no
in-symbol error correction) and paid in §4 (one symbol needed the parity tier).

**S-HC-3 — the emptiest symbol is the hardest to read.** `seq 7` is the last data
symbol, so most of its payload is the zero padding, so its data area is nearly
blank, so its 64×64 tiles have no contrast, so the local thresholder falls back
and admits noise as ink, so its CRC fails. It was the **only** symbol the
reference decoder lost, on both the first and the final degraded run.
*Proposed fix:* pad with a per-symbol pseudo-random byte pattern derived from
`seq` rather than with zeros, so no symbol can be low-contrast. That costs one
extra printed paragraph and removes a systematic failure mode.
*Severity: medium*, and it is a genuine surprise — the intuition is that a
sparse symbol is easier.

**S-HC-4 — S-OW-1 reproduced, at the paper tier, by a frontier agent.** The
signed-message construction (`werk-sig/1 LF manifest_sha256 LF
prev_entry_sha256 LF signed_at LF signer.uri LF signer.kind`) lives only in
`spec/SPEC.md` and `spec/schemas/signature.schema.json`. The reduced package
vendors neither, and the printed prose does not state it. The agent tried
**three** candidate messages — the raw manifest bytes, the digest as 32 raw
bytes, and the digest as ASCII hex — and reported `signature not over manifest
raw`, `signature not over digest bytes`, `signature not over digest ascii`. It
then **correctly declined to render a verdict**, reporting instead that the
signature record's `manifest_sha256` matches the recovered manifest and quoting
the package's own warning that the key is a published development key. That is
better behaviour than the open-weights round's models, which reported
`present-and-invalid` — a false tampering alarm — on the same construction gap.
**But the gap is now measured in two independent rounds, across three model
families and five weight classes, and it is still open.** S-OW-1's proposed fix
stands and gains a second, stronger piece of evidence: put the six-line
construction into `MINI-SPECS` §12, and say there that `unverified` is the right
answer when it is unavailable. *Severity: high.*

**S-HC-5 — "the prose was sufficient" is not the same claim as "the prose was
used", and only the second is measurable.** Two of the seven printed steps were
not implemented as written (§5.2): the local threshold was replaced by a global
sweep, and the page-wide symbol search was replaced by nine hand-written crops
read off the image by eye. The parts that *were* load-bearing are the ones no
amount of looking supplies — geometry, bit order, codeword layout, CRC-32,
reassembly. **Any future round that claims a document is self-describing should
report which of its sections the implementer actually needed**, because a
document can be sufficient and half-unread at the same time, and the unread half
is untested. *Severity: method.*

**S-HC-6 — on paper, the minimum sufficient specification is a function of the
payload, not a fixed package.** The brief asked the prose tier to carry the
open-weights round's 31 490-token kernel (`MINI-SPECS` §§1, 2, 3, 5, 6, 11 plus
the envelope and rest-pose grammars). It does not, and the deviation is recorded
in `docs/HARDCOPY-DRAFT.md` §4: those sections are ~17 100 characters, three more
sheets, describing payload encodings this payload does not contain — the smiley
package has no envelope, no rest poses, and one PNG. What sheet 3 §8 carries
instead is **ten lines**: store-mode zip, `MANIFEST.json` first and describing
every entry with path/size/media-type/sha256, verify each against its declared
digest, what `README.txt` and `SIGNATURE.json` are, and what a valid signature
does and does not prove. **The archaeology agent opened, verified and explained
the package from those ten lines.** The open-weights round's package was sized
for a fixture with four payload families and a binary envelope, and treating its
31 490 tokens as *the* minimum spec would overstate the requirement by a factor
of roughly a hundred for a package this simple. *Severity: medium*, and it
refines rather than contradicts S-OW's headline number.

---

## 7. What is and is not claimed

**Claimed, and measured:** a werk package can be printed on three sheets of A4
such that a stranger given nothing but degraded photographs of those sheets
recovers it byte-exactly, verifies it against a digest printed in prose, opens
it, and gets the picture out — in 207 seconds, with a decoder written from the
printed text for a code that did not exist before the sheets were printed. That
is self-description one substrate below anything previously tested here: not
"the file carries its spec" but "the artifact carries its spec, and the artifact
is paper".

**Not claimed:**

* **This is not a spec.** `docs/HARDCOPY-DRAFT.md` is a draft; no conformance
  clause turns on it and no file under `spec/` was edited by this wave.
* **This is not an archival recommendation.** §3.3 gives the arithmetic: 88.4
  sheets per MiB, so `fixtures/crate-v1.werk` is **1 154 sheets** and
  `fixtures/gsplat-v1.werk` is **2 550**. Paper proves the property; it does not
  store the corpus.
* **Nobody printed and photographed anything.** The degradation is a stated,
  reproducible model in `degrade.py` — rotation, blur, a multiplicative
  illumination ramp, noise, JPEG — and it is not a camera. In particular the
  ramp does not darken ink, which is why one global threshold sufficed (§5.2). A
  real print-and-shoot run is the obvious next step and would test the half of
  the prose this round left unexercised.
* **One agent, one vendor, one run.** N = 1. The cross-vendor and open-weights
  rounds' caveats apply unchanged.
* **The code is weaker than QR** at what QR is good at, deliberately (§2, S-HC-2).

---

## 8. Where everything lives

| what | path |
|---|---|
| design draft | `docs/HARDCOPY-DRAFT.md` |
| the code, encoder + reference decoder | `gauntlet/roundHC/wcode.py` |
| the printed text, verbatim | `gauntlet/roundHC/prose/PROSE.txt` |
| the payload and its builders | `gauntlet/roundHC/smiley-v1.werk`, `build_smiley_werk.py`, `make_smiley.py` |
| page renderer / degradation | `gauntlet/roundHC/make_pages.py`, `degrade.py` |
| the sheets | `gauntlet/roundHC/pages/clean/`, `gauntlet/roundHC/pages/scanned/` |
| the control | `gauntlet/roundHC/verify_roundtrip.py` |
| the task sentence, verbatim | `gauntlet/roundHC/PROMPT-archaeology.txt` |
| the runner | `gauntlet/roundHC/run_codex.sh` |
| the run: transcript, timing, the agent's decoder, its recovered file and image | `gauntlet/roundHC/runs/attempt1/` |
| the discarded first run | `gauntlet/roundHC/runs/_discarded-sandboxbug/` |
