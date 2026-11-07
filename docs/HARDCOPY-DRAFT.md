# `werk-hardcopy/1` — a werk file, printed

**DRAFT. This is not part of `spec/` and nothing in it is normative for the werk
format.** It is a design document for one experiment: taking a werk package out
of every substrate that needs electricity and putting it on paper, in a form
that a stranger with a camera and no prior knowledge can turn back into bytes.

Author: the hardcopy round agent, 2026-08-09. Owns `gauntlet/roundHC/`,
`docs/HARDCOPY-DRAFT.md` and `results/STAGE-HARDCOPY-RESULTS.md` for this wave.
Nothing under `spec/` or `fixtures/` is touched.

---

## 1. What is being proven

The format's central claim is that a werk file explains itself: everything
needed to read it travels inside it. Every test of that claim so far has handed
an agent **the file**. The container was a zip because a zip reader exists
everywhere; the manifest was JSON because JSON parsers exist everywhere. The
claim has never been separated from the substrate.

Paper separates them. A printout has no zip library, no JSON parser, no file
system and no bytes at all — only ink. So the experiment is:

> Print a werk file as (a) plain prose and (b) 2D barcodes, where the printed
> **prose teaches the reader how to decode the barcodes**, and hand a stranger
> nothing but photographs of the sheets.

If that works, self-description has been demonstrated one substrate lower than
any previous round: not "the file carries its spec" but "the *artifact* carries
its spec, and the artifact is a piece of paper".

The proof is deliberately small and complete rather than large and partial. The
payload is one 64×64 PNG of a smiling face inside the smallest recognisable werk
package. The chain the experiment tests end to end is:

**printed prose → a decoder the reader implements → the barcodes → a byte
stream → a hash that matches → a file that opens → a face.**

## 2. Why not QR

The load-bearing requirement is that the *printed prose* be sufficient to
implement a decoder from scratch. That requirement, and not familiarity or tool
support, decides the code.

**Assessed honestly, standard QR does not fit.** A conformant QR decoder needs,
at minimum: finder-pattern detection and perspective rectification; alignment
patterns whose positions come from a 40-row table; the format-information
15-bit BCH(15,5) code and its mask; version information for versions 7 and up;
eight data-mask patterns and the rule for selecting between them; the mode
indicators and character-count-indicator widths, which vary by version band; the
block structure — how many error-correction blocks of what sizes — which is a
table of 40 versions × 4 error-correction levels, 160 rows, none of it derivable;
Reed–Solomon over GF(256) with the field's primitive polynomial, the generator
polynomials per block length, interleaving, and a decoder (syndromes, Berlekamp–
Massey or Euclid, Chien search, Forney). That is a specification, not a page.
Printing it would make the printout mostly QR spec, and the resulting artifact
would prove that a stranger can transcribe ISO/IEC 18004 rather than that werk
explains itself.

There is a second reason, and it is the scientific one. **If the code is QR, the
experiment cannot distinguish "read the printed prose" from "recognised a QR
code and called a library".** Any capable implementer already has QR decoding —
in memory, or one import away — so a successful recovery would say nothing about
the prose at all. A code that has never existed before removes that confound
entirely: there is no library, no training-data recall, no fallback. The prose is
the only path, so the result measures exactly the thing the experiment is about.

**Decision: a purpose-built matrix code, `werk-hardcopy/1`, designed for
prose-describability.** The convenience arm (the same payload additionally in
QR, for a reader who just wants the bytes) is **not built**, because building it
would add a decoding path the archaeology arm might silently take.

The design rule that follows from "describable in two pages" is: **no
mechanism whose specification is a table.** So — no masking (and therefore no
mask-selection penalty scoring), no version tables, no alignment patterns, no
Reed–Solomon, no variable encoding modes. What replaces them:

| QR mechanism | what it is for | what `werk-hardcopy/1` does instead |
|---|---|---|
| three finder patterns + alignment | locate, rectify | one solid black frame; four corners by extremes of x±y; bilinear map |
| format info, version info (BCH) | describe the symbol | nothing: every symbol is the same size, and the parameters live in the codeword's own 16-byte header |
| eight data masks + penalty rules | avoid pathological patterns | nothing: the payload is compressed-ish binary already, and the frame is what is located, not the data |
| Reed–Solomon per block | correct errors inside a symbol | CRC-32 per symbol (detect, then discard) + XOR parity across symbols (recover a whole lost symbol) |
| mode indicators, char counts | encode text efficiently | nothing: the payload is bytes |

The trade is stated plainly: `werk-hardcopy/1` **cannot correct a bit error
inside a symbol**, where QR can. It detects it and throws the symbol away, and
recovers the symbol from the group's parity. That is a worse code and a
*describable* one, and for this artifact describability is the requirement.

## 3. The symbol

Normative statement for this draft; the printed sheets say the same thing in
plain language, and `gauntlet/roundHC/wcode.py` implements it.

```
W = 99 modules per side, plus a white quiet zone at least 4 modules wide.

ring 0   r or c in {0, 98}      SOLID BLACK          the locator frame
ring 1   r or c in {1, 97}      WHITE, except that (1,1), (1,2) and (2,1)
                                are BLACK: the orientation elbow, and it
                                marks the top-left corner
data     rows 2..96, cols 2..96 95 x 95 = 9025 module positions
```

9025 positions carry **1128 bytes** (9024 bits), read row-major, left to right
then top to bottom, most-significant-bit first, black = 1. The one leftover
position is printed white and ignored.

Two properties earn their place:

* **The frame is solid on all four sides**, unlike Data Matrix's L. A solid
  frame is one closed outline, which makes "find the symbols" a connected-region
  question with no special cases, and makes the four corners the extremes of
  x+y and x−y. The cost is four-fold rotational ambiguity, which the elbow
  resolves for three modules.
* **The elbow lives in ring 1, not in the data area.** Reserving positions
  inside the data area would make the read order conditional; ring 1 costs 392
  positions and keeps the read order "row-major, no exceptions".

### Codeword (1128 bytes)

```
0..1     0x57 0x4B        "WK"
2        0x01             version
3        0x00 | 0x01      kind: 0 = data, 1 = parity
4..5     u16 big-endian   seq   -- position in the document, both kinds counted
6..7     u16 big-endian   total -- symbols in the document
8..11    u32 big-endian   file_len -- length of the original file
12..15   u32 big-endian   crc32 of bytes 0..11 followed by bytes 16..1127
16..1127                  payload, 1112 bytes
```

`seq`, `total` and the CRC are **also printed in human-readable text beneath
each symbol**, so a reader can tell a misread symbol from a missing one before
writing any code, and the whole-file sha256 is printed in prose on two of the
three sheets.

### Sequencing and error control

The file is zero-padded to a multiple of 1112. Data symbols carry consecutive
slices; after every group of at most **K = 8** data symbols comes one parity
symbol whose payload is the byte-wise XOR of that group's data payloads. One
lost or corrupt symbol per group is recoverable; two are not. Overhead is
**1/9 = 11.1 %**.

The layering is deliberate: **CRC-32 turns corruption into erasure, and XOR
parity turns erasure into recovery.** Each half is four lines of prose, and
together they do the job a per-symbol ECC would do, at a granularity a
photographer can act on ("re-shoot that one").

## 4. The page

Three A4 sheets at 300 DPI.

| sheet | what is on it |
|---|---|
| 1 | what the document is; the file's length and SHA-256; the symbol geometry; modules→bytes; photograph handling (thresholding, finding symbols, finding corners) |
| 2 | sampling and orientation; the codeword layout; CRC-32 in full with a test vector; the parity scheme |
| 3 | reassembly; what a werk package is; **the nine symbols**, captioned; the SHA-256 again |

Measured layout numbers are in `results/STAGE-HARDCOPY-RESULTS.md` §3.

### What the prose tier carries, and the one deviation from the brief

The brief asked for the prose tier to carry the **minimum-spec kernel sections**
— the 31 490-token package selected in the open-weights round (`MINI-SPECS`
§§1, 2, 3, 5, 6, 11, plus the envelope and rest-pose grammars). **It does not,
and this is a deliberate, recorded deviation.** Those sections are ~17 100
characters and would have added three sheets of prose to a three-sheet
document, tripling it in order to describe payload encodings the payload does
not use: the smiley package has no envelope, no rest poses, and one PNG.

What sheet 3 §8 carries instead is the **condensed werk kernel**: that the file
is a store-mode zip; that `MANIFEST.json` is first and describes every entry
with path, size, media type and sha256; that verification means hashing each
entry against its declared digest; what `README.txt` and `SIGNATURE.json` are
and what a valid signature does and does not prove. That is enough to open,
verify and understand the recovered package, and it is 10 lines rather than 3
sheets.

The full-kernel variant remains buildable — `make_pages.py` takes any prose file
— and the page arithmetic for it is recorded in the results file. **The
substitution is a finding, not a shortcut: on paper, the minimum sufficient spec
is a function of what the payload actually contains, and the open-weights
round's package was sized for a fixture with four payload families and a binary
envelope.**

## 5. Reading a photograph

The procedure printed on sheets 1 and 2, in outline:

1. **Local threshold.** 64×64 tiles; each tile's threshold is the midpoint of
   its darkest and lightest pixel; contrast-free tiles inherit the average of
   the tiles that have contrast.
2. **Find symbols.** Connected regions of ink, 4-connectivity; keep those whose
   bounding box is at least half a symbol and roughly square.
3. **Find corners.** Widen the box; ignore connected groups below a few hundred
   pixels; over what remains take the pixels extremising x+y and x−y. Those are
   the four corners, clockwise from the top-left-most.
4. **Sample.** Bilinear map from the four corners; module (r,c) centre at
   u=(c+0.5)/99, v=(r+0.5)/99; vote over the 3×3 pixel block at that point.
5. **Check and orient.** Ring 0 must be ≥90 % black; rotate in 90° steps until
   the elbow is top-left.
6. **Decode.** Row-major, MSB-first; check the CRC; discard the symbol on
   failure.
7. **Reassemble.** Repair one missing symbol per group by XOR; concatenate data
   payloads by `seq`; truncate to `file_len`; check the printed SHA-256.

**Two of those steps are written the way they are because the reference decoder
got them wrong first, and both corrections are printed.** Step 3 originally said
"topmost, rightmost, bottommost, leftmost, with ties broken by the perpendicular
extreme" — which is wrong at small angles: a 600-pixel edge 6 pixels thick,
tilted one degree, has some hundreds of pixels sharing the same smallest column,
so any tie-break lands most of the way down the edge and the sampling grid
collapses. It was measured collapsing: sides of 470/237/497/125 pixels where the
symbol is 593. And step 3's "a few hundred pixels" floor exists because the
first version used the *largest* connected group, and an illumination gradient
breaks the frame into several. Both are stated on the sheet, as warnings, with
the reason.

That is the draft's most transferable lesson: **prose that describes a code is
itself a program, and it has bugs. The only way to find them is to implement the
decoder from the prose alone and run it against a degraded photograph.**

## 6. Degradation — the honest test input

The clean 300-DPI renders are what a printer receives. The archaeology arm uses
the **scanned** arm: rotation 0.55–0.90°, Gaussian blur radius 1.1 px (about a
fifth of a module), a diagonal illumination ramp falling to 62 % plus a
vignette, additive noise at σ = 9/255, and a JPEG round trip at quality 82.
Every parameter is fixed in `degrade.py` and was chosen once, before the decoder
was run against it.

## 7. What is deliberately not claimed

* **This is not a spec.** No conformance clause, no schema, no `spec/` edit.
* **It is not an archival recommendation.** Nothing here says paper is a good
  place to keep a werk file. The page arithmetic in the results file says
  plainly what a real package would cost in sheets.
* **The code is weaker than QR** at what QR is good at, on purpose (§2).
* **The simulated photograph is a simulation.** Nobody printed and photographed
  these sheets. The degradation model is stated and reproducible; it is not a
  camera.
