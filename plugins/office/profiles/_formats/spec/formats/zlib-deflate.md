# zlib, DEFLATE and gzip — werk format definition `zlib-deflate`

```werk-format
{
  "format_id": "zlib-deflate",
  "format_version": 1,
  "title": "zlib, DEFLATE and gzip",
  "media_type": "application/zlib",
  "extensions": [
    "zz",
    "zlib",
    "gz"
  ],
  "sniff": [
    {
      "rule": "zlib-header"
    },
    {
      "magic": [
        {
          "offset": 0,
          "hex": "1f8b08"
        }
      ]
    }
  ],
  "defines": {
    "decode": true,
    "encode": true
  },
  "coverage": "partial",
  "coverage_note": "Decoding of DEFLATE (all three block types), the zlib framing and the gzip framing (multi-member, all header flags) is defined completely. NOT defined: zlib streams that use a preset dictionary (FDICT) - the dictionary is not in the stream and such a stream is refused. Encoding is defined only as far as producing a VALID stream (stored blocks and fixed-Huffman blocks, section 9); how to choose matches and build dynamic Huffman codes for good compression is not defined.",
  "lossy": false,
  "normative_sources": [
    "RFC 1950 (zlib)",
    "RFC 1951 (DEFLATE)",
    "RFC 1952 (gzip)"
  ],
  "reference_tools": [
    {
      "tool_id": "format-zlib-deflate-reference",
      "language": "python",
      "entrypoint": "tools/format-zlib-deflate-reference/inflate.py"
    }
  ],
  "test_vectors": [
    {
      "id": "stored",
      "description": "zlib framing, one STORED block (BTYPE 00).",
      "input_bytes": 30,
      "input_sha256": "c1b81b71aa3243ff5ecfd8ebb6009fed3339cec6e3ca8e97b2c1221e60d21827",
      "output_form": "the decompressed bytes",
      "output_bytes": 19,
      "output_sha256": "dfcaccbb870affa50b8b0a4de89b665dffb22f2eb7bf4537456b49c4b1a31992"
    },
    {
      "id": "fixed",
      "description": "zlib framing, one FIXED-Huffman block (BTYPE 01) with a length/distance match that overlaps its own output.",
      "input_bytes": 17,
      "input_sha256": "c5af43cfa489275bf4b3bf65b995ee5c131607710df3903cf73c070431790af4",
      "output_form": "the decompressed bytes",
      "output_bytes": 24,
      "output_sha256": "66dafcbddf1265a536c7cd4dc458b50de3c109cedc0896cdb77041616c98a003"
    },
    {
      "id": "dynamic",
      "description": "zlib framing, one DYNAMIC-Huffman block (BTYPE 10): 2136 bytes of text.",
      "input_bytes": 156,
      "input_sha256": "398c1412f754b2fceb01b350bb95a66b70061401c9c02d09ba69142ed352e755",
      "output_form": "the decompressed bytes",
      "output_bytes": 2136,
      "output_sha256": "db7ff35ae3f9c11c0c45dba5dcb5d3ada7f41850f4f95b579db6ade28e1c273f"
    },
    {
      "id": "gzip-two-members",
      "description": "gzip framing, two members; the first carries FNAME (`a.txt`). The output is the concatenation of both members' data.",
      "input_bytes": 73,
      "input_sha256": "2f6e985b6d29b51b17f07c938a188d78adf5e19cf2ca0105e1e1ddeef96b12f9",
      "output_form": "the decompressed bytes",
      "output_bytes": 27,
      "output_sha256": "9384585afb38dbcfe6feb29c21798ed481d2a244404f51ec19450162fa61b024"
    },
    {
      "id": "empty",
      "description": "zlib framing around zero bytes of data (the Adler-32 of nothing is 1).",
      "input_bytes": 8,
      "input_sha256": "b171e283c6145acf2b923098dbbc40ffc39b4f1db0212928f9869747376c4ac8",
      "output_form": "the decompressed bytes",
      "output_bytes": 0,
      "output_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    }
  ]
}
```

This document is normative and self-contained: with it and nothing else you can write a
decoder for DEFLATE-compressed data in its two common framings, and an encoder that emits
valid (if not well-compressed) streams. It restates RFC 1950, RFC 1951 and RFC 1952 in full for
the parts it covers; you do not need those documents.

## 1. Scope and coverage

Three things, nested:

* **DEFLATE** — the compressed data format itself: a sequence of blocks (§5–§9).
* **zlib** — a 2-byte header, a DEFLATE stream, a 4-byte Adler-32 of the uncompressed data (§3).
* **gzip** — a ≥10-byte header, a DEFLATE stream, CRC-32 and length; possibly repeated (§4).

A payload of this format is a zlib stream or a gzip file. Which one is decided by its first
bytes: `1f 8b 08` is gzip; otherwise the first two bytes must be a valid zlib header (§3).

Defined completely: decoding of all three block types, both framings, all gzip header flags,
multi-member gzip. **Not defined:** a zlib stream with a preset dictionary (the `FDICT` flag) —
the dictionary is by definition not in the stream; a decoder refuses such a stream. Encoding is
defined only as far as producing a valid stream (§10).

## 2. Conventions

* A byte is 8 bits. Multi-byte integers in the zlib trailer are **big-endian**; in the gzip
  header/trailer and in a stored block's length fields they are **little-endian**.
* **Bit order inside DEFLATE.** The compressed data is read as a stream of bits. Bits are taken
  from each byte starting with the **least significant bit** (bit 0, value 1) and ending with
  the most significant (bit 7, value 128); then the next byte.
* A fixed-width field of *n* bits (a block header field, an "extra bits" value) is read with its
  **least significant bit first**: the first bit read is bit 0 of the value.
* A **Huffman code** is read **most significant bit first**: the first bit read is the top bit
  of the code. (This is the one asymmetry of the format; getting it wrong decodes garbage.)

`bits(n)` below means: read *n* bits as a fixed-width field, value 0 .. 2ⁿ−1; `bits(0)` is 0.

## 3. The zlib framing

```
offset  size  field
0       1     CMF   bits 0-3: CM, compression method, MUST be 8 (deflate)
                    bits 4-7: CINFO, log2(window size) - 8, MUST be <= 7 (window <= 32768)
1       1     FLG   bits 0-4: FCHECK, chosen so that (CMF*256 + FLG) is a multiple of 31
                    bit  5:   FDICT, a 4-byte dictionary id follows the header
                    bits 6-7: FLEVEL, informational, ignored by a decoder
2       ...   the DEFLATE stream (section 5)
end-4   4     ADLER32 of the UNCOMPRESSED data, big-endian (section 11)
```

A decoder checks: `CM == 8`, `CINFO <= 7`, `(CMF*256 + FLG) % 31 == 0`; if `FDICT` is set it
refuses the stream; after the last DEFLATE block the next 4 bytes (starting at the next byte
boundary) must equal the Adler-32 of everything it produced.

The most common header is `78 9c` (also `78 01`, `78 5e`, `78 da`).

## 4. The gzip framing

A gzip file is one or more **members**, concatenated; the decoded data is the concatenation of
the members' data. Each member:

```
offset  size  field
0       2     ID1 ID2 = 1f 8b
2       1     CM = 8 (deflate)
3       1     FLG   bit 0 FTEXT (ignore)   bit 1 FHCRC   bit 2 FEXTRA   bit 3 FNAME
                    bit 4 FCOMMENT         bits 5-7 reserved, must be 0
4       4     MTIME, little-endian Unix time, 0 = not set (ignore)
8       1     XFL (ignore)
9       1     OS  (ignore)
then, in THIS order, each present only if its flag is set:
  FEXTRA    2 bytes XLEN (little-endian), then XLEN bytes
  FNAME     bytes up to and including a terminating 00  (ISO 8859-1 file name)
  FCOMMENT  bytes up to and including a terminating 00
  FHCRC     2 bytes (low 16 bits of the CRC-32 of the header so far; may be ignored)
then  the DEFLATE stream
then  4 bytes CRC32 of this member's uncompressed data, little-endian (section 11)
      4 bytes ISIZE = uncompressed length modulo 2^32, little-endian
```

After a member, if any bytes remain, another member starts.

## 5. The DEFLATE stream

A stream is a sequence of **blocks**. Each block starts with a 3-bit header:

```
BFINAL = bits(1)     1 = this is the last block of the stream
BTYPE  = bits(2)     0 = stored, 1 = fixed Huffman codes, 2 = dynamic Huffman codes, 3 = ERROR
```

The decoder produces one continuous output; a block may copy from output produced by earlier
blocks. Blocks are of any size and are not aligned to byte boundaries (except as §6 says).

## 6. Stored blocks (BTYPE = 0)

1. Discard the remaining bits of the current byte (move to the next byte boundary).
2. Read `LEN` (2 bytes, little-endian) and `NLEN` (2 bytes, little-endian). `NLEN` must equal
   the one's complement of `LEN` (`LEN ^ 0xFFFF == NLEN`), else the stream is corrupt.
3. Copy the next `LEN` bytes to the output unchanged. `LEN` may be 0.

## 7. Compressed blocks: the two alphabets

A compressed block is a sequence of symbols from the **literal/length alphabet** (values 0–285):

* 0–255: output that byte.
* 256: end of block.
* 257–285: a **match length** follows (table A); then a symbol from the **distance alphabet**
  (values 0–29) is read with the distance code, and a **distance** follows (table B). The
  decoder then copies `length` bytes starting `distance` bytes back in the output.

Table A — length symbol → (extra bits to read, base length); length = base + bits(extra):

```
sym ext base | sym ext base | sym ext base | sym ext base
257  0    3  | 265  1   11  | 273  3   35  | 281  5  131
258  0    4  | 266  1   13  | 274  3   43  | 282  5  163
259  0    5  | 267  1   15  | 275  3   51  | 283  5  195
260  0    6  | 268  1   17  | 276  3   59  | 284  5  227
261  0    7  | 269  2   19  | 277  4   67  | 285  0  258
262  0    8  | 270  2   23  | 278  4   83  |
263  0    9  | 271  2   27  | 279  4   99  |
264  0   10  | 272  2   31  | 280  4  115  |
```

Symbols 286 and 287 never occur in valid data. Lengths range 3..258.

Table B — distance symbol → (extra bits, base distance); distance = base + bits(extra):

```
sym ext base | sym ext  base | sym ext   base
 0   0     1 | 10   4     33 | 20   9   1025
 1   0     2 | 11   4     49 | 21   9   1537
 2   0     3 | 12   5     65 | 22  10   2049
 3   0     4 | 13   5     97 | 23  10   3073
 4   1     5 | 14   6    129 | 24  11   4097
 5   1     7 | 15   6    193 | 25  11   6145
 6   2     9 | 16   7    257 | 26  12   8193
 7   2    13 | 17   7    385 | 27  12  12289
 8   3    17 | 18   8    513 | 28  13  16385
 9   3    25 | 19   8    769 | 29  13  24577
```

Distance symbols 30 and 31 never occur. Distances range 1..32768. A distance larger than the
number of bytes output so far is an error.

**The copy may overlap its own output**: `length` may exceed `distance`. Copy one byte at a
time, from oldest to newest: with distance 1 and length 5 the last output byte is repeated five
times. (Test vector `fixed` exercises this.)

## 8. Huffman codes

Every code in DEFLATE is a **canonical** prefix code, fully determined by the code LENGTH of
each symbol (0 = the symbol does not occur). Given `lengths[0..n-1]`, the codes are:

```
bl_count[L] = number of symbols with length L          (for L >= 1)
code = 0
next_code[1] = 0
for L = 2 .. max_length:
    code = (code + bl_count[L-1]) << 1
    next_code[L] = code
for symbol = 0 .. n-1 in increasing order:
    L = lengths[symbol]
    if L != 0:
        codes[symbol] = next_code[L], written as exactly L bits
        next_code[L] += 1
```

Example: lengths (A..H) = 3,3,3,3,3,2,4,4 give codes A=010, B=011, C=100, D=101, E=110, F=00,
G=1110, H=1111.

To decode one symbol: start with `code = 0`, `L = 0`; repeat `code = (code << 1) | bits(1)`,
`L += 1`, until `(L, code)` is the code of some symbol. No code is longer than 15 bits.

### 8.1 Fixed codes (BTYPE = 1)

No table is transmitted. The literal/length code lengths are:

```
symbols   0-143: 8 bits      144-255: 9 bits      256-279: 7 bits      280-287: 8 bits
```

and all 30 distance symbols have length 5 (so a distance symbol is simply 5 bits, read most
significant bit first).

### 8.2 Dynamic codes (BTYPE = 2)

The block begins with a description of its two codes:

```
HLIT  = bits(5) + 257     number of literal/length code lengths transmitted (257..286)
HDIST = bits(5) + 1       number of distance code lengths transmitted (1..32)
HCLEN = bits(4) + 4       number of code-length-code lengths transmitted (4..19)
```

Then `HCLEN` values of `bits(3)` each: the code lengths of the **code length alphabet**
(symbols 0–18), given in this fixed order, the rest being 0:

```
16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15
```

Build the canonical code for those 19 symbols (§8). Then read `HLIT + HDIST` code lengths as
ONE sequence (the literal/length lengths followed by the distance lengths; a repeat may run
across the boundary), each obtained by decoding a code-length symbol:

```
0..15   the length itself
16      copy the PREVIOUS length 3 + bits(2) times   (3..6); an error if there is no previous
17      a run of zeros, 3 + bits(3) long             (3..10)
18      a run of zeros, 11 + bits(7) long            (11..138)
```

A run that would exceed `HLIT + HDIST` entries is an error. The first `HLIT` lengths define the
literal/length code, the next `HDIST` the distance code. Symbol 256 must have a non-zero length.
A distance code with a single symbol of length 1 is valid (the code is the single bit 0).

## 9. The decoding procedure

```
out = empty
repeat:
    BFINAL = bits(1); BTYPE = bits(2)
    if BTYPE == 0:  stored block (section 6)
    elif BTYPE == 3: error
    else:
        (litlen, dist) = fixed codes (8.1) if BTYPE == 1 else codes read as in 8.2
        loop:
            s = decode(litlen)
            if s < 256:   out.append(s)
            elif s == 256: break
            else:
                length   = baseA[s] + bits(extraA[s])            # table A; s > 285 is an error
                d        = decode(dist)                          # d > 29 is an error
                distance = baseB[d] + bits(extraB[d])            # table B
                if distance > len(out): error
                for i in 0 .. length-1: out.append(out[len(out) - distance])
until BFINAL == 1
```

After the final block, any remaining bits of the current byte are discarded; the framing's
trailer starts at the next byte boundary.

## 10. Encoding: the minimum that is valid

Two ways to write a valid stream without designing a compressor:

* **Stored only.** Split the data into chunks of at most 65535 bytes. For each chunk write the
  byte `01` for the last chunk or `00` otherwise (BFINAL, BTYPE = 0, and five padding bits),
  then `LEN` and `NLEN` (little-endian), then the chunk. Empty data is one final stored block
  with `LEN = 0`.
* **Fixed Huffman, literals only.** Write the 3 header bits `1`, then `1`, `0` (BFINAL = 1,
  BTYPE = 1, least significant bit first), then for each byte its fixed code (§8.1) most
  significant bit first, then the code of symbol 256 (seven 0 bits), then pad with 0 bits to a
  byte boundary. The fixed codes: bytes 0–143 are the 8-bit codes `00110000` + value; bytes
  144–255 the 9-bit codes `110010000` + (value − 144); symbol 256 is `0000000`.

zlib framing around either: `78 01`, the DEFLATE stream, Adler-32 big-endian. Using matches
(§7) and dynamic codes (§8.2) is permitted to any encoder; how to choose them is not defined
here.

## 11. The two checksums

**Adler-32** (zlib), over the uncompressed data:

```
a = 1; b = 0
for each byte x:  a = (a + x) mod 65521;  b = (b + a) mod 65521
adler32 = b * 65536 + a
```

The Adler-32 of no data is 1; of the single byte `61` it is `00620062`; of ASCII `abc` it is
`024d0127`.

**CRC-32** (gzip): the reflected CRC with polynomial `0xEDB88320`, initial value `0xFFFFFFFF`,
final XOR `0xFFFFFFFF`:

```
crc = 0xFFFFFFFF
for each byte x:
    crc = crc XOR x
    repeat 8 times:  crc = (crc >> 1) XOR 0xEDB88320  if (crc AND 1) else  crc >> 1
crc32 = crc XOR 0xFFFFFFFF
```

The CRC-32 of ASCII `123456789` is `cbf43926`; of no data, `00000000`.

## 12. Errors a decoder must report rather than guess through

A zlib header that fails §3; `FDICT`; a gzip member with `CM != 8`; block type 3; a stored
block whose `NLEN` is not the complement of `LEN`; a code that matches no symbol; a
literal/length symbol above 285 or a distance symbol above 29; a distance beyond the start of
the output; a code-length repeat with no previous length or running past the table; data that
ends before the final block ends; a checksum or `ISIZE` that does not match.

## 13. Test vectors

Every input below is given in full as a `hex <id>` block; its sha256 and the sha256 of the decoded output (in the stated output form) are in the header at the top of this document. An implementation is checked by decoding each input and comparing the hash of its output.

### Vector `stored`

zlib framing, one STORED block (BTYPE 00).

* input: 30 bytes, sha256 `c1b81b71aa3243ff5ecfd8ebb6009fed3339cec6e3ca8e97b2c1221e60d21827`
* output form: the decompressed bytes
* output: 19 bytes, sha256 `dfcaccbb870affa50b8b0a4de89b665dffb22f2eb7bf4537456b49c4b1a31992`
* checked when this document was built: the reference decoder's output equals the bytes the input was encoded from

The output, for orientation:

```
werk: stored block
```

```hex stored
7801011300ecff7765726b3a2073746f72656420626c6f636b0a47a406da
```

### Vector `fixed`

zlib framing, one FIXED-Huffman block (BTYPE 01) with a length/distance match that overlaps its own output.

* input: 17 bytes, sha256 `c5af43cfa489275bf4b3bf65b995ee5c131607710df3903cf73c070431790af4`
* output form: the decompressed bytes
* output: 24 bytes, sha256 `66dafcbddf1265a536c7cd4dc458b50de3c109cedc0896cdb77041616c98a003`
* checked when this document was built: the reference decoder's output equals the bytes the input was encoded from

The output, for orientation:

```
hello hello hello hello
```

```hex fixed
78dacb48cdc9c957c84027b90070be08bb
```

### Vector `dynamic`

zlib framing, one DYNAMIC-Huffman block (BTYPE 10): 2136 bytes of text.

* input: 156 bytes, sha256 `398c1412f754b2fceb01b350bb95a66b70061401c9c02d09ba69142ed352e755`
* output form: the decompressed bytes
* output: 2136 bytes, sha256 `db7ff35ae3f9c11c0c45dba5dcb5d3ada7f41850f4f95b579db6ade28e1c273f`
* checked when this document was built: the reference decoder's output equals the bytes the input was encoded from

The output, for orientation:

```
000 the quick brown fox jumps over the lazy dog; pack my box with five dozen liquor jugs
001 the quick brown fox jumps o...
```

```hex dynamic
78dab5d3cb1582301046e1bd554c0999f83e56031a200a040201a17a73ece1ae
e79fbbfb8c3132374ec6e49f1f2963587ba9c257dea91b26098b8bff735bec9b
bc42fd90a1c8bb6e93328f563f3752f9c5e5d3ee7a69fd9842ccbff5743046a9
b0a5c2472a7ca2c2672a7ca1c2572a7ca3c27728ac943ca5e429254f29794ac9
534a9e52f29492a7943ca5e4594a9ea5e4594a9e85e4fd00baeff6b9
```

### Vector `gzip-two-members`

gzip framing, two members; the first carries FNAME (`a.txt`). The output is the concatenation of both members' data.

* input: 73 bytes, sha256 `2f6e985b6d29b51b17f07c938a188d78adf5e19cf2ca0105e1e1ddeef96b12f9`
* output form: the decompressed bytes
* output: 27 bytes, sha256 `9384585afb38dbcfe6feb29c21798ed481d2a244404f51ec19450162fa61b024`
* checked when this document was built: the reference decoder's output equals the bytes the input was encoded from

The output, for orientation:

```
first member
second member
```

```hex gzip-two-members
1f8b08080000000002ff612e747874004bcb2c2a2e51c84dcd4d4a2de20200a7
f4850a0d0000001f8b08000000000002ff2b4e4dcecf4b51c84dcd4d4a2de202
0036184b0e0e000000
```

### Vector `empty`

zlib framing around zero bytes of data (the Adler-32 of nothing is 1).

* input: 8 bytes, sha256 `b171e283c6145acf2b923098dbbc40ffc39b4f1db0212928f9869747376c4ac8`
* output form: the decompressed bytes
* output: 0 bytes, sha256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
* checked when this document was built: the reference decoder's output equals the bytes the input was encoded from

The output in full (hex):

```

```

```hex empty
78da030000000001
```


## 14. What this definition does not cover

Preset dictionaries (`FDICT`). Compression strategy. The "deflate64" variant (64 KiB window,
length symbol 285 with 16 extra bits), which is not DEFLATE and does not occur in zlib or gzip.
