# The 32-byte-record Gaussian splat file (`.splat`) — werk format definition `splat-32`

This document is a **format definition** in the sense of `spec/SPEC.md`
§3.18: it is normative, it is self-contained, and a decoder and an encoder for
the format can be written from it and from nothing else. It is also this
specification's worked example of what a definition document looks like —
read its header against the key table in §3.18.

```werk-format
{
  "format_id": "splat-32",
  "format_version": 1,
  "title": "Gaussian splat, 32 bytes per Gaussian (.splat)",
  "media_type": "application/octet-stream",
  "extensions": ["splat"],
  "sniff": [
    {
      "rule": "none",
      "size_multiple_of": 32,
      "note": "The file is an array of 32-byte records from byte 0, with no magic and no header, so nothing in its first bytes identifies it. A node that carries one NAMES the format; the one check the bytes allow is that the size is a whole number of records."
    }
  ],
  "defines": {"decode": true, "encode": true},
  "coverage": "complete",
  "lossy": false,
  "normative_sources": [
    "The record layout written by the `convert.py` tool of the antimatter15/splat WebGL viewer (2023); this document restates it and does not depend on it"
  ],
  "test_vectors": [
    {
      "id": "four-records",
      "description": "Four records: the identity rotation, a rotation about each of two axes, a negative scalar part, colour and opacity bytes at both ends of their range, and positions and scales that are exact in binary32.",
      "input_bytes": 128,
      "input_sha256": "28be3bc42381f662d114eca78d4afffe1ec360ecc86a020989ca6f35fb3304b8",
      "output_form": "Section 6: 14 little-endian binary32 values per record, 56 bytes per record, records in file order.",
      "output_bytes": 224,
      "output_sha256": "d43afa67aeef311c64f645b8e5e8673b31df74dd2c6f713419f9831ea7210b54"
    },
    {
      "id": "no-records",
      "description": "The empty file: zero Gaussians. Legal, and decodes to the empty output.",
      "input_bytes": 0,
      "input_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "output_form": "Section 6.",
      "output_bytes": 0,
      "output_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    }
  ]
}
```

## 1. Scope and coverage

A `.splat` file is one 3D Gaussian splat — a set of anisotropic Gaussians,
each with a position, three scales, a rotation, an opacity and one colour —
as web viewers exchange it. **Coverage is complete**: every byte of every
conformant file is defined here, for reading and for writing.

What the format itself does not have, so that an absence reads as a fact
about the format and not as a gap in this document: no header, no count
field, no spherical-harmonic coefficients above degree 0 (one colour per
Gaussian, no view dependence), no units, no coordinate-system declaration,
and no version number.

## 2. Conventions

* All multi-byte values are **little-endian**.
* `f32` is IEEE 754 binary32. `u8` is an unsigned byte.
* The file is `N` records of exactly 32 bytes, with nothing before, between
  or after them. `N = file size / 32`. A file whose size is not a multiple of
  32 is not a file of this format.

## 3. The record

| offset | size | type | field |
|---|---|---|---|
| 0 | 4 | f32 | position x |
| 4 | 4 | f32 | position y |
| 8 | 4 | f32 | position z |
| 12 | 4 | f32 | scale x |
| 16 | 4 | f32 | scale y |
| 20 | 4 | f32 | scale z |
| 24 | 1 | u8 | colour red |
| 25 | 1 | u8 | colour green |
| 26 | 1 | u8 | colour blue |
| 27 | 1 | u8 | opacity |
| 28 | 1 | u8 | rotation w |
| 29 | 1 | u8 | rotation x |
| 30 | 1 | u8 | rotation y |
| 31 | 1 | u8 | rotation z |

## 4. What the fields mean

Four of these are places where a wrong reading produces a file that parses,
renders, and is wrong.

* **Position** is the Gaussian's centre, in the capture's own units and axes.
  The file declares neither; whoever carries it records them elsewhere (in a
  werk package: the recipe that names this file).
* **Scale is LINEAR.** The three numbers are the standard deviations of the
  Gaussian along its own axes, already activated. The representation a
  trainer writes stores `log(scale)`; this file does not. A reader that
  applies `exp` to these has squared the problem.
* **Opacity is LINEAR**, straight (not premultiplied): `opacity = byte / 255`,
  from 0.0 (invisible) to 1.0 (opaque). A trainer writes the logit; this file
  does not. Because the byte 255 means exactly 1.0 and `logit(1.0)` is
  infinite, converting *to* the logit form needs a clamp, which the converter
  must state and count.
* **Colour** is the Gaussian's degree-0 colour, already evaluated:
  `component = byte / 255`, and the byte was produced from a trainer's
  degree-0 spherical-harmonic coefficient `f_dc` as
  `byte = round(255 * clamp(0.5 + C0 * f_dc, 0, 1))` with
  `C0 = 0.28209479177387814`. So the inverse is
  `f_dc = (byte / 255 - 0.5) / C0`, exact up to the byte's quantisation. The
  colour space is the capture's; nothing in the file says sRGB or linear.
* **Rotation** is a quaternion in the order **w, x, y, z — the scalar part
  first** — with each component stored as `byte = clamp(round(128 + 128 * q),
  0, 255)`, so `q = (byte - 128) / 128`, between −1.0 and +0.9921875. The
  stored quaternion is close to unit length and not exactly: **normalise it**
  before building a rotation matrix. A quaternion and its negation are the
  same rotation. Because +1.0 does not fit (it would be byte 256), the
  identity rotation is stored as `255, 128, 128, 128`, which decodes to
  `(0.9921875, 0, 0, 0)` and normalises to the identity.

Records are conventionally sorted so that the most significant Gaussians
(largest, most opaque) come first, so that a viewer can show a truncated
download. The order carries no other meaning and a reader must not depend on
it.

## 5. Decoding

```
if size(file) mod 32 != 0:  refuse  ("not a whole number of 32-byte records")
N = size(file) / 32
for i in 0 .. N-1, with p = 32*i:
    position = ( f32le(p+0),  f32le(p+4),  f32le(p+8)  )
    scale    = ( f32le(p+12), f32le(p+16), f32le(p+20) )      linear
    colour   = ( u8(p+24)/255, u8(p+25)/255, u8(p+26)/255 )
    opacity  =   u8(p+27)/255                                 linear
    rotation = ( (u8(p+28)-128)/128, (u8(p+29)-128)/128,
                 (u8(p+30)-128)/128, (u8(p+31)-128)/128 )     w, x, y, z; NOT normalised
```

A decoder that hands the Gaussians to a renderer then normalises each
rotation, and — if all four components are zero, which a damaged or
hand-made file can contain — treats it as the identity and says how many
there were.

## 6. The canonical decoded form

For checking an implementation against the test vectors: for each record, in
file order, **14 values, each rounded to binary32 and written little-endian**
— 56 bytes per record —

```
position x, y, z        as stored
scale x, y, z           as stored
colour r, g, b          byte / 255      (computed in binary64, rounded to binary32)
opacity                 byte / 255      (the same)
rotation w, x, y, z     (byte - 128) / 128    exact in binary32; NOT normalised
```

## 7. Encoding

```
for each Gaussian:
    write position x, y, z as f32le
    write scale x, y, z as f32le                       LINEAR; each > 0
    write clamp(round(255 * c), 0, 255) for c in colour r, g, b
    write clamp(round(255 * opacity), 0, 255)
    q = rotation normalised to unit length, order w, x, y, z
    write clamp(round(128 + 128 * qi), 0, 255) for qi in q
```

`round` is round-half-away-from-zero. A writer converting from a trainer's
representation applies `exp` to the scales, the sigmoid to the opacity and
the colour formula of §4 to the degree-0 coefficients, and drops every
coefficient above degree 0 — which loses the view dependence, and a writer
says so.

## 8. Errors a decoder reports rather than guesses through

* A size that is not a multiple of 32: refuse the file.
* A position or scale that is not finite (NaN, ±infinity): the record is
  invalid. A converter into a werk payload refuses the file, because a werk
  payload may not hold a non-finite number.
* A scale component that is zero or negative: the record is degenerate. It
  cannot be converted to a logarithmic representation; a converter refuses
  rather than invents.

## 9. Test vectors

The inputs are printed in full below; each hashes to the `input_sha256` in
the header, and decoding it to the form of §6 gives bytes that hash to
`output_sha256`. The expected outputs were written down from the values in
the table, not produced by a decoder.

`four-records`:

| record | position | scale | colour bytes | opacity byte | rotation bytes w,x,y,z | decoded rotation |
|---|---|---|---|---|---|---|
| 0 | 0, 0, 0 | 1, 1, 1 | 255, 255, 255 | 255 | 255, 128, 128, 128 | 0.9921875, 0, 0, 0 |
| 1 | 0.5, −0.25, 2 | 0.125, 0.25, 0.5 | 0, 128, 255 | 1 | 128, 255, 128, 128 | 0, 0.9921875, 0, 0 |
| 2 | −1.5, 3, −0.75 | 0.0625, 1.5, 2 | 17, 34, 51 | 128 | 0, 128, 128, 128 | −1, 0, 0, 0 |
| 3 | 100, −200, 0.001953125 | 4, 0.5, 0.03125 | 64, 64, 64 | 0 | 192, 64, 192, 64 | 0.5, −0.5, 0.5, −0.5 |

```hex four-records
00000000 00000000 00000000 0000803f 0000803f 0000803f ffffffff ff808080
0000003f 000080be 00000040 0000003e 0000803e 0000003f 0080ff01 80ff8080
0000c0bf 00004040 000040bf 0000803d 0000c03f 00000040 11223380 00808080
0000c842 000048c3 0000003b 00008040 0000003f 0000003d 40404000 c040c040
```

Three things in it are there to be got wrong: record 0's rotation decodes to
0.9921875 and not to 1; record 2's scalar part is negative, which is the same
rotation as its negation and must survive a round trip as stored; and record
1's opacity byte of 1 decodes to 1/255, which is not zero.

`no-records`:

```hex no-records
```

## 10. In a werk package

A `.splat` file in a werk package is what it is anywhere else: these bytes,
verbatim. This repository's Gaussian-splat fixture carries one as the input
medium of its recipe, converts it with a tool whose source travels in the
same package, and stores the result as a `core.geom.gsplat` payload
(`spec/layouts/gsplat.layout.txt`), which keeps the same activated values at
full float precision: `means` = position, `scales` = scale, `sh-dc` =
`(colour − 0.5) / C0`, `rotations` = the normalised quaternion with its
scalar part made non-negative, and `opacities` = opacity **except at the two
ends**: that converter goes through the trainer's logit form, where 0 and 1
do not exist, so it clamps opacity half a quantisation step inside the range
(to 0.5/255 and 254.5/255), says so, and records how many Gaussians it
clamped. The `.splat` therefore cannot be recovered byte for byte from the
payload, which is one reason the original is carried and the other is that
it is the thing the recipe says it started from.

## 11. Change notes

* `format_version` 1 — 2026-10-13. First text.
