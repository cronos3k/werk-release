# werk mini-specs — the boring encodings, in full

Law 2 says: *where a ubiquitous, boring encoding exists, use it — and still
include its one-page mini-spec, so the guarantee holds literally.*

This is that file. Everything a werk 3D entity contains is either

* a custom binary described by `spec/layouts/*.layout.txt`, or
* one of the encodings below.

An isolated intelligence with `spec/` and nothing else can therefore write a
complete reader. That is the claim, and the point of this document is to
make it true rather than aspirational.

Each section gives the byte-level structure, the constants, and a test
vector where one exists. None of them is a substitute for the original
standard's edge cases; each is a complete description of **the subset werk
uses**, and werk writers MUST stay inside that subset.

**Contents**

1. Bit and byte conventions
2. UTF-8
3. JSON
4. MessagePack (pointer)
5. zip
6. CRC-32
7. DEFLATE / zlib — what needs it and what does not
8. PNG
9. WAV (RIFF)
10. GLB (glTF 2.0 binary)
11. SHA-256
12. Ed25519
13. What werk deliberately does not use

---

## 1. Bit and byte conventions

* **Little-endian** for every werk custom binary payload. The least
  significant byte comes first: the u32 `0x12345678` is stored `78 56 34 12`.
* **Big-endian** appears only inside imported formats, and each place is
  called out where it occurs: MessagePack's integers and floats (§4), PNG's
  chunk lengths, CRCs, `IHDR` fields and 16-bit samples (§8), the zlib
  wrapper's Adler-32 (§7), and SHA-256/SHA-512's words and length field
  (§11). Zip is little-endian throughout, and so is every werk binary. If you
  find yourself byte-swapping anywhere else, you have a bug.
* IEEE-754 binary32 ("f32", 4 bytes) and binary64 ("f64", 8 bytes) are the
  only float encodings. No NaN and no infinity may appear in a core payload.
* Signed integers are two's complement.
* Sizes are in bytes unless a field name says otherwise.

---

## 2. UTF-8

Every string in every werk file is UTF-8, without a byte-order mark. A
werk reader MUST reject a BOM rather than silently strip it, because a
stripped BOM changes a file's sha256 and sha256 is the store key.

Encoding, complete:

| code point range | bytes |
|---|---|
| `U+0000`–`U+007F` | `0xxxxxxx` |
| `U+0080`–`U+07FF` | `110xxxxx 10xxxxxx` |
| `U+0800`–`U+FFFF` | `1110xxxx 10xxxxxx 10xxxxxx` |
| `U+10000`–`U+10FFFF` | `11110xxx 10xxxxxx 10xxxxxx 10xxxxxx` |

The `x` bits are the code point's bits, most significant first. Rules a
conformant reader enforces: no overlong encodings (a code point must use the
shortest form), no surrogate code points (`U+D800`–`U+DFFF`), nothing above
`U+10FFFF`.

werk ids (`entity.uuid`, `part_id`, `material_id`, `node_id`, `bone_id`,
effect `slug`, facet tags) are ASCII kebab-case, matching
`^[a-z0-9]+(-[a-z0-9]+)*$`. Human-facing text (names, notes, descriptions)
is full UTF-8.

---

## 3. JSON

werk uses RFC 8259 JSON, restricted:

* UTF-8, no BOM.
* No comments. No trailing commas. No single quotes.
* No `NaN`, `Infinity`, `-Infinity` — a JSON number in werk is always finite.
* Integers that must round-trip exactly stay within ±2^53.
* Duplicate object keys are illegal; a reader encountering one MUST reject
  the file rather than pick a winner.

Grammar, complete:

```
value   = object | array | string | number | "true" | "false" | "null"
object  = '{' [ member *( ',' member ) ] '}'
member  = string ':' value
array   = '[' [ value *( ',' value ) ] ']'
string  = '"' *char '"'
char    = any Unicode scalar except '"' and '\' and U+0000-U+001F
        | '\' ( '"' | '\' | '/' | 'b' | 'f' | 'n' | 'r' | 't'
                | 'u' 4HEXDIG )
number  = [ '-' ] int [ frac ] [ exp ]
int     = '0' | digit1-9 *digit
frac    = '.' 1*digit
exp     = ('e'|'E') [ '+' | '-' ] 1*digit
ws      = *( ' ' | '\t' | '\n' | '\r' )   ; allowed between any two tokens
```

`\uXXXX` escapes: a code point above `U+FFFF` is written as a surrogate
pair of two `\uXXXX` escapes, high surrogate first.

### Canonical JSON (for hashing only)

Where werk hashes a JSON *value* rather than a file's bytes — only
`version.input_params` in the manifest does this — the canonical form is:

1. Object keys sorted ascending by their UTF-8 byte sequence.
2. No whitespace at all between tokens.
3. Strings escaped minimally: only `"`, `\` and `U+0000`–`U+001F` escaped,
   the last as `\u00XX` except for the short forms `\b \f \n \r \t`.
4. Integers written without a decimal point or exponent. Non-integers
   written in the shortest form that round-trips through binary64.
5. UTF-8, no BOM, no trailing newline.

**Rule 3 is the one a standard library gets wrong for you.** A character
outside ASCII is written as **its UTF-8 bytes**, not as a `\uXXXX` escape —
and several serialisers escape everything outside ASCII unless told not to
(Python's `json.dumps` does, by default; `ensure_ascii=False` turns it off).
The escaped string is valid JSON, parses to the same value, and hashes to
something else. This repository's own Python `canon()` had that default for
as long as it existed while the Rust core did not, and nothing caught it
because no fixture's `input_params` contained a character outside ASCII
(finding F-AC-2, fixed 2026-10-13). The vector, so that it is caught the next
time:

```
value      {"n": 1, "name": "Größe", "note": "a→b", "tab": "x<TAB>y"}
canonical  {"n":1,"name":"Größe","note":"a→b","tab":"x\ty"}
bytes      7b226e223a312c226e616d65223a224772c3b6c39f65222c226e6f7465223a2261
           e2869262222c22746162223a22785c7479227d                    (52 bytes)
sha256     13a2906649470c284a45bc33763ca934e41edd18e32e764443acfd4aba11baa6
WRONG      88236f7462a04075483b9eaa769cb1a7fa8f4977f3f92e70c4f8df36ecd40d49
           (63 bytes: the same value with ö, ß and → written as ö ß →)
```

The control character keeps its short form (`\t`), which rule 3 does ask for.

**Rule 4 is not yet a complete rule, and this is said rather than hidden.**
"The shortest form that round-trips" fixes the digits and not the spelling,
and serialisers spell the same digits differently:

| value | Python `json` | Rust `serde_json` | JavaScript `JSON.stringify` |
|---|---|---|---|
| `1e-05` | `1e-05` | `0.00001` | `0.00001` |
| `1e-07` | `1e-07` | `1e-7` | `1e-7` |
| `1.0` | `1.0` | `1.0` | `1` |
| `1e16` | `1e+16` | `1e+16` | `10000000000000000` |
| `0.1`, `1.5e300`, `5e-324` | agree | agree | agree |

So an `input_hash` over a parameter like `1e-05` is recomputed differently by
readers in different languages, today, including by this repository's own
two. Until it is ruled (finding F-AC-3, open), **a writer keeps every number
in `input_params` to an integer, or to a non-integer whose shortest decimal
form has a digit on both sides of the point and no exponent** (`0.5`, `12.25`,
`0.28209479177387814`) — the forms on which all three agree — and puts
anything else in a string. Every fixture in this repository already does.

Everywhere else — including the manifest hash that signatures cover — werk
hashes **the bytes of the file as they are**, never a reserialisation.

---

## 4. MessagePack

Used only for envelope headers in custom binaries. The full byte-level
specification of the subset werk permits — every format byte, the banned
extension types, and the canonical-encoding rules — is section 4 of
`spec/layouts/ENVELOPE.layout.txt`. It is written there rather than here
because it is inseparable from the envelope's other rules.

The one thing worth repeating: **MessagePack integers and floats are
big-endian**, unlike everything else in a werk binary.

---

## 5. zip

The interchange form of a werk is its directory tree zipped. werk uses
**store mode (method 0) by default**; see `SPEC.md` §1 for why.

> **FIRST, THE CHEAP PATH: if your language has a zip library, use it.**
> A `.werk` is an ordinary, standards-conformant zip — `import zipfile` in
> Python, `java.util.zip`, `System.IO.Compression.ZipArchive`, `unzip(1)` —
> and every one of them opens it correctly with no werk-specific knowledge at
> all. **Nothing in this format asks you to write a zip parser.** The
> byte-level description below is here for the reader that has no such library
> (the embedded Rust and C loaders may use no third-party crates), for the
> reader doing ranged reads over the preview prefix, and for the reader that
> wants to verify what a library told it. It is a fallback, not the intended
> route, and it is the graded-effort doctrine applied to your first five
> minutes with the file.
>
> Recorded as spec finding **S-OW-4**: both sub-9B models in the open-weights
> gauntlet died at the container — one hand-rolled an EOCD scan that never
> found the EOCD, in sixteen attempts, with this section and a complete entry
> listing *with offsets* in front of it — and neither had ever been told that
> the library route existed.

A zip file is read **from the end**. Three record types matter.

### 5.1 End of central directory record (EOCD)

Signature `50 4B 05 06` (`PK\x05\x06`), little-endian throughout:

| offset | size | field |
|---|---|---|
| 0 | 4 | signature `0x06054b50` |
| 4 | 2 | number of this disk (0) |
| 6 | 2 | disk where central directory starts (0) |
| 8 | 2 | central directory records on this disk |
| 10 | 2 | total central directory records |
| 12 | 4 | size of central directory in bytes |
| 16 | 4 | offset of central directory from start of file |
| 20 | 2 | comment length *n* |
| 22 | *n* | comment |

To find it, in these exact terms — a reader transcribing as it goes should be
able to stop at the end of this list:

```
first offset tested   = filesize - 22
lowest offset tested  = max(0, filesize - 22 - 65535)
bytes you need to read = min(filesize, 65535 + 22) from the end
```

The comment is the only thing that can follow the record and its length field
is 16 bits, so 65535 is the whole of the slack and the read window is that
plus the 22-byte record itself.

### 5.2 Central directory file header

Signature `50 4B 01 02` (`0x02014b50`):

| offset | size | field |
|---|---|---|
| 0 | 4 | signature |
| 4 | 2 | version made by |
| 6 | 2 | version needed |
| 8 | 2 | general purpose flags |
| 10 | 2 | compression method — **0 = store, 8 = deflate** |
| 12 | 2 | last mod time (MS-DOS) |
| 14 | 2 | last mod date (MS-DOS) |
| 16 | 4 | CRC-32 of the uncompressed data |
| 20 | 4 | compressed size |
| 24 | 4 | uncompressed size |
| 28 | 2 | file name length *n* |
| 30 | 2 | extra field length *m* |
| 32 | 2 | comment length *k* |
| 34 | 2 | disk number start |
| 36 | 2 | internal attributes |
| 38 | 4 | external attributes |
| 42 | 4 | **offset of the local file header** |
| 46 | *n* | file name, UTF-8 (flag bit 11: see §5.4) |
| 46+*n* | *m* | extra field |
| 46+*n*+*m* | *k* | comment |

Records follow one another with no padding. The central directory is the
authority on names, sizes and offsets; a reader uses it and does not scan
for local headers.

### 5.3 Local file header

Signature `50 4B 03 04` (`0x04034b50`), at the offset the central directory
gave:

| offset | size | field |
|---|---|---|
| 0 | 4 | signature |
| 4 | 2 | version needed |
| 6 | 2 | general purpose flags |
| 8 | 2 | compression method |
| 10 | 2 | last mod time |
| 12 | 2 | last mod date |
| 14 | 4 | CRC-32 |
| 18 | 4 | compressed size |
| 22 | 4 | uncompressed size |
| 26 | 2 | file name length *n* |
| 28 | 2 | extra field length *m* |
| 30 | *n* | file name |
| 30+*n* | *m* | extra field |

**File data begins at `local_header_offset + 30 + n + m`.** Note that the
local header's *n* and *m* can differ from the central directory's; always
re-read them from the local header. With method 0 the data is `compressed
size` bytes verbatim.

With method 8 the data is `compressed size` bytes of one raw DEFLATE stream,
§7.1, which inflates to `uncompressed size` bytes whose CRC-32 (§6) is the
directory's. A reader checks both before it hands the bytes over: a stream
that does not decode, or decodes to something else, is damage to **that
entry** — report code `zip-entry-invalid`, the node is dead, the container is
not.

A werk reader that supports only method 0 is conformant for store-mode
packages, which is what every fixture but one uses. It MUST report a method-8
entry as unsupported rather than returning wrong bytes. All four reference
readers support methods 0 and 8 (ruling 9 of 2026-10-13, PROPOSED). **Any
other method** (9 Deflate64, 12 bzip2, 14 LZMA, 93 Zstandard, …) **and an
encrypted entry** (general purpose flag bit 0) is refused for that entry, by
name — `zip-entry-unsupported` — and its bytes are never returned.

### 5.4 Rules werk imposes

* Names use forward slashes, are relative, contain no `..` segment, no drive
  letter and no leading slash.
* Directory entries (names ending in `/`, size 0) are optional; a reader
  MUST NOT depend on them.
* General purpose flag bit 3 (sizes in a trailing data descriptor) MUST NOT
  be set by a werk writer, because it makes a ranged read of the preview
  prefix impossible.
* Names are UTF-8. General purpose flag bit 11 ("the name is UTF-8") MUST be
  set on an entry whose name holds a byte above 0x7F. For an all-ASCII name
  the bit changes nothing — ASCII is UTF-8 — and MAY be clear: the zip
  library route above is conformant as it stands (Python's `zipfile` leaves
  the bit clear for ASCII names; werk's own writers always set it). A reader
  decodes every name as UTF-8 whatever the bit says and MUST NOT reject an
  entry for a clear bit 11.
* No two entries have the same name.
* Entry order SHOULD be the preview-first order declared in
  `MANIFEST.json` → `container.entry_order` (`SPEC.md` §1; a reader never
  depends on it). An element of `entry_order` that matches no entry —
  `SIGNATURE.json` in an unsigned package, say — matches nothing and is
  skipped; it is not an error.

**Reader rules for a damaged container — so that independent readers agree.**
The four reference readers apply exactly these, and a damage campaign holds
them to one verdict per damaged byte:

1. The EOCD is the record at the **highest** offset of the §5.1 window whose
   signature matches **and** whose comment length accounts for exactly the
   rest of the file. None → `bad-container`.
2. Exactly *total central directory records* (EOCD offset 10) records are
   read, one after another from the central-directory offset. The
   directory's byte size (EOCD offset 12) and the per-disk count (offset 8)
   are not used to walk it; they matter only as the zip64 sentinels of §5.5.
   A record whose signature is not `50 4B 01 02`, or whose name runs past the
   end of the file, → `bad-container`. Each record's extra field and comment
   are skipped by their lengths, not read.
3. A name is decoded as UTF-8 with every invalid sequence replaced (U+FFFD).
   A damaged name is then a name no manifest path matches — that file is
   missing, its node is dead (`file-missing`) — never a malformed directory.
4. Flag bit 3 set → `bad-container`. Flag bit 0 set → that entry is
   `zip-entry-unsupported`. No other flag bit is consulted.
5. Two records with one name (after step 3) → `bad-container`.
6. The central directory is the authority on method, sizes, CRC-32 and
   offset. Of the local header only its signature and its name and extra
   lengths are read; a bad local signature, or data that runs past the end of
   the file, is `zip-entry-invalid` for that entry. Method 0 data is
   `compressed size` bytes verbatim, checked by the manifest's `size` and
   `sha256`, not by the directory's CRC-32.

### 5.5 Zip64 — how to RECOGNISE it, and what to do

**werk does not use zip64** (ruling 9 of 2026-10-13, PROPOSED; `SPEC.md`
§1). A single-file package is a 32-bit zip — every entry and the whole file
below 4 GiB, at most 65 534 entries — and a package past that is carried in
directory form, which is the same format and has no ceiling. No werk writer
emits zip64 and no reference reader implements it. *This paragraph used to
say zip64 was permitted and that a full reader SHOULD support it; no reader
ever did, and no fixture ever was one.*

Recognising it is not optional for anybody, though, because a zip32-only
reader that does not recognise it will read the sentinel values as real
numbers and return wrong bytes — which §5.3's rule ("report unsupported
rather than return wrong bytes") forbids — and because a file somebody else
zipped with a general tool may well be zip64. So the detection procedure is
normative:

1. Find the 22-byte EOCD as in §5.1.
2. **Sentinels.** In that EOCD, the value `0xFFFF` in either 16-bit count
   field, or `0xFFFFFFFF` in the central-directory size or offset field,
   means "the real value is in the zip64 record". Any one of them present ⇒
   the container is zip64.
3. **Zip64 EOCD locator**, signature `50 4B 06 07` (`0x07064b50`), 20 bytes,
   sits immediately before the EOCD — i.e. at `eocd_offset - 20`. Its
   presence is the second, independent signal; a reader MAY test for it
   directly instead of relying on the sentinels.

   | offset | size | field |
   |---|---|---|
   | 0 | 4 | signature `0x07064b50` |
   | 4 | 4 | disk with the zip64 EOCD (0) |
   | 8 | 8 | **offset of the zip64 EOCD record** |
   | 16 | 4 | total number of disks (1) |

4. **Zip64 EOCD record**, signature `50 4B 06 06` (`0x06064b50`), at the
   offset the locator gave. The fields a reader needs are the 64-bit
   widenings of the EOCD's:

   | offset | size | field |
   |---|---|---|
   | 0 | 4 | signature `0x06064b50` |
   | 4 | 8 | size of this record minus 12 |
   | 12 | 2 | version made by |
   | 14 | 2 | version needed |
   | 16 | 4 | number of this disk (0) |
   | 20 | 4 | disk with the central directory (0) |
   | 24 | 8 | central directory records on this disk |
   | 32 | 8 | total central directory records |
   | 40 | 8 | size of the central directory |
   | 48 | 8 | offset of the central directory |

5. Per-entry, the same sentinel convention applies inside the central
   directory: an uncompressed size, compressed size or local-header offset
   of `0xFFFFFFFF` means the true 64-bit value is in that entry's extra
   field, in the record tagged `0x0001` (2-byte tag, 2-byte size, then the
   present values in the order uncompressed size, compressed size,
   local-header offset, disk number — **only the ones whose fixed field held
   the sentinel are present**, which is why the extra field's size is what
   tells you how many were written).

**What a reader MUST do:** refuse the container — not a node — with the
named report `zip64-unsupported` and exit status 2, and read nothing from
it. This is the one refusal in §10's checklist that is whole-container
rather than per-node, because the offsets it would otherwise follow are
sentinels rather than data. It MUST NOT fall back to reading the 32-bit
fields. The directory form of the same package is unaffected and remains a
complete, readable werk, and the refusal says so.

**Do it from the tail, before reading anything else.** Steps 1–3 need only
the last `22 + 65535 + 20` bytes of the file. A zip64 container is by
definition the kind that may not fit in memory — passing 4 GiB is what it is
for — so a reader that loads the file and *then* refuses it has already paid,
in RAM, for the thing it is refusing; and a reader whose file offsets are 32
bits wide cannot even ask such a file its size. Seek relative to the end,
read the tail, decide. (Step 5's per-entry sentinel is checked when the
central directory is walked, for the rare zip64 entry inside an otherwise
32-bit archive.)

**What is NOT zip64: a zip64 extra field in a LOCAL header only.** A writer
that starts an entry before it knows the entry's size may reserve room for
64-bit sizes: it writes `0xFFFFFFFF` into the two size fields of the *local*
header, a `0x0001` record into the local extra field and 45 into "version
needed", and then, the entry having turned out small, writes ordinary 32-bit
values into the central directory and an ordinary EOCD (the Python standard
library does exactly this for `ZipFile.open(name, "w", force_zip64=True)`).
Steps 1–5 find nothing in such a file, and that is the right answer: the
central directory is where a reader takes sizes and offsets from, the local
header is used for *n* and *m* only (§5.3), and every byte the reader follows
is a real number. Such a container is read. Measured 2026-10-13 on the CC0
lean crate rewritten that way: all four reference readers read it and report
what they report for the original (`tests/run_gate_container.py`).

All four reference readers do exactly this and print the same code, and it
is measured rather than claimed: `tests/run_gate_container.py` builds two
**real** zip64 archives with an unrelated tool — one of 70 001 entries, which
trips the count sentinel, and with `--big` one of 4.06 GiB, which trips the
offset sentinel — and requires status 2 and `zip64-unsupported` from each
reader on each. Before 2026-10-13 the four readers printed four different
things for that file — one a stack trace, one the code behind another code's
prefix, two a sentence with no code at all — and all four returned status 1.
The preview prefix never needs zip64.

---

## 6. CRC-32

Needed twice: zip entry checksums, and PNG chunk checksums. It is the same
function in both — the reflected IEEE 802.3 CRC-32 with polynomial
`0xEDB88320`, initial value `0xFFFFFFFF`, final XOR `0xFFFFFFFF`.

```
crc32(bytes):
    crc = 0xFFFFFFFF
    for b in bytes:
        crc ^= b
        repeat 8 times:
            crc = (crc >> 1) ^ (0xEDB88320 if (crc & 1) else 0)
    return crc ^ 0xFFFFFFFF
```

**Test vector:** `crc32("123456789")` (the nine ASCII bytes `31 32 33 34 35
36 37 38 39`) = `0xCBF43926`.

---

## 7. DEFLATE / zlib — what needs it and what does not

Honest accounting, because this is the one place a reader needs an algorithm
of real size — about a hundred and fifty lines, defined in §7.1 and carried by
all four reference readers since 2026-10-13:

| you want to read | do you need inflate? |
|---|---|
| the zip container, store mode | **no** |
| `MANIFEST.json`, every schema, every layout, `facets.json`, the skeleton | **no** |
| any `WKFF`/`WKRP`/`WKAC`/`WKSK` envelope binary | **no** |
| WAV audio takes | **no** |
| GLB geometry (uncompressed accessors) | **no** |
| **PNG pixel data** | **yes** |
| the zip container, deflate mode | **yes** |

So a zero-dependency bootstrap loader can read the entire graph, all
geometry, all audio and all metadata, and will need an inflate
implementation only to turn a texture into pixels. That is a deliberate
line: it is why store mode is the container default (`SPEC.md` §1), and it
is why a `core.loader` that declares `read-textures` is doing meaningfully
more work than one that declares `read-geometry`.

~~DEFLATE itself (RFC 1951) is not reproduced here~~ — it was not, until
2026-10-13, on the argument that every standard library ships it. That
argument is about the present tense, and this document's whole premise is
that ubiquity is a property of the present tense (it is why PNG and WAV get
mini-specs at all); and under the principle `SPEC.md` §3.18 states — the file
carries a definition a codec can be built from — a PNG whose pixels need an
algorithm the file does not describe was the one hole in the base set. §7.1
closes it. A zlib *stream* (RFC 1950), which is what PNG's IDAT contains, is:
1 byte CMF, 1 byte FLG, the raw DEFLATE stream of §7.1, then a 4-byte
big-endian Adler-32 of the uncompressed data. `CMF & 0x0F` must be 8. If
`FLG & 0x20` is set a 4-byte dictionary id follows the header; PNG never sets
it, and a werk reader refuses a stream that does.

Adler-32, for completeness: `a = 1, b = 0; for each byte: a = (a+byte) %
65521, b = (b+a) % 65521; return (b << 16) | a`.

### 7.1 DEFLATE, decoding (RFC 1951, restated)

Enough to write an inflater from this section alone. Decoding only: a werk
writer never needs to compress (a store-mode zip and a PNG whose IDAT uses
stored blocks, below, are both legal and need no compressor).

**Bits.** The stream is read as a sequence of bits, **least significant bit
of each byte first**. A fixed-width field of *n* bits is read
least-significant bit first: the first bit read is bit 0 of the value. **A
Huffman code is the one exception: it is read one bit at a time and each new
bit is appended at the least significant end of the code** (so codes are, in
effect, packed most-significant bit first). Getting this pair the wrong way
round is the classic inflate bug.

**Blocks.** The stream is a sequence of blocks. Each begins with a 3-bit
header:

```
BFINAL  1 bit    1 = this is the last block
BTYPE   2 bits   0 = stored, 1 = fixed Huffman, 2 = dynamic Huffman, 3 = INVALID
```

**BTYPE 0, stored.** Discard the remaining bits of the current byte. Then:
`LEN` (u16 little-endian), `NLEN` (u16 little-endian, MUST equal `LEN` with
every bit inverted), then `LEN` bytes copied to the output verbatim.

**BTYPE 1 and 2, compressed.** The block is a sequence of symbols from two
alphabets, each with its own Huffman code:

* the **literal/length** alphabet, symbols 0..285: 0..255 is a literal byte;
  256 is end-of-block; 257..285 is a match length (table below);
* the **distance** alphabet, symbols 0..29 (table below).

```
loop:
    sym = decode(literal/length code)
    if sym < 256:   output byte sym
    elif sym == 256: end of this block
    else:
        length   = LBASE[sym-257] + read_bits(LEXTRA[sym-257])
        dsym     = decode(distance code)               ; 30 and 31 are invalid
        distance = DBASE[dsym] + read_bits(DEXTRA[dsym])
        ; distance > bytes output so far (in the whole stream) is invalid
        copy `length` bytes, ONE AT A TIME, from `distance` bytes back
```

The copy is byte by byte **because a match may overlap its own output**:
length 15 at distance 3 after "abc" yields "abcabcabcabcabcabc". A block copy
reads bytes that have not been written yet. Matches may reach back into
earlier blocks, up to 32 768 bytes.

```
sym    257 258 259 260 261 262 263 264 265 266 267 268 269 270 271
LBASE    3   4   5   6   7   8   9  10  11  13  15  17  19  23  27
LEXTRA   0   0   0   0   0   0   0   0   1   1   1   1   2   2   2
sym    272 273 274 275 276 277 278 279 280 281 282 283 284 285
LBASE   31  35  43  51  59  67  83  99 115 131 163 195 227 258
LEXTRA   2   3   3   3   3   4   4   4   4   5   5   5   5   0

dsym     0  1  2  3  4  5  6   7   8   9  10  11  12  13   14
DBASE    1  2  3  4  5  7  9  13  17  25  33  49  65  97  129
DEXTRA   0  0  0  0  1  1  2   2   3   3   4   4   5   5    6
dsym    15   16   17   18   19    20    21    22    23    24    25    26     27     28     29
DBASE  193  257  385  513  769  1025  1537  2049  3073  4097  6145  8193  12289  16385  24577
DEXTRA   6    7    7    8    8     9     9    10    10    11    11    12     12     13     13
```

**A Huffman code is given by one number per symbol: its code length in bits,
0 meaning "this symbol does not occur".** The codes follow from the lengths
(they are *canonical*): shorter codes come first, and within one length the
codes are consecutive in order of symbol value.

```
count[L] = number of symbols with length L          (L = 1..15; ignore length 0)
code = 0
for L in 1..15:
    code = (code + count[L-1]) << 1                 (count[0] taken as 0)
    next[L] = code
for each symbol s in increasing order, with length L != 0:
    s is assigned the L-bit code next[L];  next[L] += 1
```

Decoding without building a table: read one bit at a time, keeping `code`
(the bits so far), and for each length *L* compare against the first code of
that length and the number of codes of that length —

```
code = first = index = 0
for L in 1..15:
    code |= read_bits(1)
    if code - count[L] < first:  return symbols_sorted_by_(length, value)[index + (code - first)]
    index += count[L];  first = (first + count[L]) << 1;  code <<= 1
fail: no code matches
```

A set of lengths is **over-subscribed** (invalid) if, running `left = 1; for
L in 1..15: left = 2*left - count[L]`, `left` ever goes negative. It is
**incomplete** if `left` ends above 0; an incomplete code is valid only when
it consists of a single code of length 1 (a block that uses one distance, or
none).

**BTYPE 1, the fixed codes.** No lengths are transmitted. Literal/length
lengths: symbols 0..143 → 8, 144..255 → 9, 256..279 → 7, 280..287 → 8
(286 and 287 never occur in data but take part in the construction).
Distance lengths: all 30 symbols → 5.

**BTYPE 2, the dynamic codes.** The two codes' lengths are transmitted,
themselves Huffman-coded:

```
HLIT   5 bits   number of literal/length lengths  = HLIT + 257   (257..286)
HDIST  5 bits   number of distance lengths        = HDIST + 1    (1..30)
HCLEN  4 bits   number of code-length-code lengths = HCLEN + 4   (4..19)
then (HCLEN + 4) x 3 bits: the lengths of the CODE-LENGTH alphabet's 19
symbols, in this fixed order; those not transmitted are 0:
    16 17 18 0 8 7 9 6 10 5 11 4 12 3 13 2 14 1 15
then HLIT+257 + HDIST+1 code lengths, as ONE sequence (the literal/length
lengths first, the distance lengths straight after), each decoded with the
code-length code:
    0..15   that length
    16      repeat the PREVIOUS length 3 + read_bits(2) times (3..6);
            invalid as the very first symbol
    17      a run of 3 + read_bits(3) zeros (3..10)
    18      a run of 11 + read_bits(7) zeros (11..138)
```

A run may cross from the literal/length lengths into the distance lengths; it
may not run past the end of the sequence. The literal/length code MUST give
symbol 256 a non-zero length. Then build both codes and decode as above.

**Errors a decoder reports rather than guesses through:** BTYPE 3; `NLEN`
not the complement of `LEN`; the stream ending inside a block; a bit sequence
that is no code; a length symbol above 285 or a distance symbol above 29; a
distance reaching before the start of the output; over-subscribed lengths; an
incomplete code other than the single-code case; no end-of-block code; and —
for a zip entry — output exceeding the directory's uncompressed size, which
a decoder treats as its limit rather than as a number to check afterwards.

**Test vectors.** One per block type. The inputs were produced by an
unrelated encoder (zlib 1.3.1, through Python's `zlib.compressobj(level, 8,
-15)`); the outputs are the bytes that were handed to it. All three are run
by `--selftest` of the Rust and C loaders and by the reference core's tests.

```
stored    in  01 0b 00 f4 ff 77 65 72 6b 20 73 74 6f 72 65 64                (16 bytes)
          out "werk stored"                                                  (11 bytes)
          sha256(out) ce0a40dc0a2c99da888b60c8a20a5dfbd5aae7dd238f8d15fc15eeedf940a8e5

fixed     in  4b 4c 4a 4e 44 45 00                                           (7 bytes)
          out "abcabcabcabcabcabc"   - four literals (a b c a), then ONE     (18 bytes)
              match of length 14 at distance 3, which overlaps its own output
          sha256(out) 916f4626f2d02e07085873c17f8115790840519094e94114b706573c9749331f

dynamic   in  8d 89 bb 0d 80 30 0c 05 57 f1 00 c0 00 6c 63 39 4e f2 44 3e
              92 63 88 d8 9e 82 92 86 e6 74 ba 9b 6a 07 cd 9f 18 5a e2 2a
              6c 76 a3 25 0a 48 70 2e c4 e6 88 2c 3e 76 f2 ac 14 51 94 30
              5e ef 56 d9 97 4f 0f 5d ce aa cd d9 d1 db 77 b3 49 c6 a5 1b
              3d                                                             (81 bytes)
          out "werk " nine times, then "self-carrying digital artifacts: the
              file is the format, the file is the documentation, the file is
              the archive. "   (one space after the full stop)               (158 bytes)
          sha256(out) 09b86fc31af218f9bae56da09eb8a03c49ba5b22acae373d69613d5a793eb26e
```

Walking the first bytes of the `fixed` vector, because one worked header is
worth the paragraph above: `4b` is `01001011`; read LSB first that is
BFINAL = 1, then BTYPE = `1,0` → 1 (fixed). The next bits, taken one at a time
into a code, are `1,0,0,1,0,0,0,1` = `10010001` = 0x91, an 8-bit code;
the fixed 8-bit literal codes start at `00110000` (0x30) for symbol 0, so
this is symbol 0x91 − 0x30 = 0x61, the literal `a`.

---

## 8. PNG

Every texture and every imposter atlas is a PNG.

### 8.1 File structure

8-byte signature, then a sequence of chunks:

```
89 50 4E 47 0D 0A 1A 0A     the signature, exactly these bytes
```

Each chunk:

| size | field |
|---|---|
| 4 | length of the data field, **big-endian u32** (does not include type or CRC) |
| 4 | chunk type, 4 ASCII letters |
| *length* | data |
| 4 | CRC-32, big-endian, computed over **type + data** (not the length) |

Chunk type case carries meaning: bit 5 of byte 0 set = ancillary
(skippable), of byte 1 = private, of byte 3 = safe to copy.

### 8.2 Chunks werk cares about

**`IHDR`** — first chunk, 13 bytes:

| offset | size | field |
|---|---|---|
| 0 | 4 | width, big-endian u32, > 0 |
| 4 | 4 | height, big-endian u32, > 0 |
| 8 | 1 | bit depth: 1, 2, 4, 8 or 16 |
| 9 | 1 | colour type: 0 grey, 2 RGB, 3 palette, 4 grey+alpha, 6 RGBA |
| 10 | 1 | compression method, always 0 (DEFLATE) |
| 11 | 1 | filter method, always 0 |
| 12 | 1 | interlace: 0 none, 1 Adam7 |

werk restricts textures to bit depth 8 or 16, colour type 0, 2, 4 or 6, and
**interlace 0**. A palette PNG or an interlaced PNG in a werk package is
non-conformant; a reader MUST report it rather than guess.

**`PLTE`** — palette; not used by conformant werk textures.

**`IDAT`** — the pixel data. One or more IDAT chunks, whose data
concatenated in order form a single zlib stream (§7). Decompressed, it is
the scanlines.

**`IEND`** — zero-length terminator.

**`sRGB` / `gAMA` / `iCCP`** — colour space chunks. werk reads them if
present but they are **not** authoritative: the colour space of a texture is
`meta.color_space` in `MANIFEST.json`, because law 8 says a convention is a
declared value and not something recovered from an optional chunk that half
the tools drop.

### 8.3 Scanlines and filters

Let `bpp` = bytes per complete pixel, rounded up to at least 1
(e.g. 8-bit RGBA → 4; 16-bit grey → 2; 8-bit RGB → 3). Each scanline in the
decompressed stream is:

```
1 byte filter type, then width*bpp bytes of filtered data
```

Reconstruction, per byte, where `x` is the current filtered byte, `a` is the
already-reconstructed byte `bpp` positions to the left (0 at the start of
the line), `b` is the reconstructed byte directly above (0 on the first
line), `c` is the reconstructed byte above-left (0 likewise). All arithmetic
is modulo 256.

| filter | reconstruction |
|---|---|
| 0 None | `out = x` |
| 1 Sub | `out = x + a` |
| 2 Up | `out = x + b` |
| 3 Average | `out = x + floor((a + b) / 2)` |
| 4 Paeth | `out = x + Paeth(a, b, c)` |

```
Paeth(a, b, c):
    p  = a + b - c
    pa = |p - a| ; pb = |p - b| ; pc = |p - c|
    if pa <= pb and pa <= pc: return a
    if pb <= pc:              return b
    return c
```

16-bit samples are big-endian within the scanline. The filter operates on
bytes, not on samples — do not byte-swap before filtering.

---

## 9. WAV (RIFF)

Every audio take is a WAV. RIFF is little-endian throughout.

```
offset 0  : "RIFF"                      4 ASCII
offset 4  : u32  size of everything after this field
offset 8  : "WAVE"                      4 ASCII
offset 12 : a sequence of chunks
```

Each chunk:

| size | field |
|---|---|
| 4 | chunk id, 4 ASCII |
| 4 | u32 chunk data size |
| *size* | data |
| 0 or 1 | pad byte `0x00` when *size* is odd |

The pad byte is **not** counted in the size field and is the single most
commonly missed rule in RIFF parsing.

**`fmt `** (note the trailing space), 16 bytes minimum:

| offset | size | field |
|---|---|---|
| 0 | 2 | audio format: **1 = PCM integer, 3 = IEEE float**, `0xFFFE` = extensible |
| 2 | 2 | channels |
| 4 | 4 | sample rate, Hz |
| 8 | 4 | byte rate = sample_rate × block_align |
| 12 | 2 | block align = channels × bits_per_sample / 8 |
| 14 | 2 | bits per sample |
| 16 | 2 | (if size ≥ 18) size of the extension, often 0 |
| 18 | 22 | (if extensible) valid bits, channel mask, 16-byte sub-format GUID |

**`data`** — the samples, interleaved by frame: all channels of frame 0,
then all channels of frame 1, and so on. Frame count =
`data_size / block_align`.

Sample encodings:

| bits | format | encoding |
|---|---|---|
| 8 | PCM | **unsigned** 0..255, silence at 128 |
| 16 | PCM | signed little-endian, silence at 0 |
| 24 | PCM | signed little-endian, 3 bytes per sample |
| 32 | PCM | signed little-endian |
| 32 | IEEE float | binary32 little-endian, nominal range −1.0..+1.0 |

Chunks a reader must skip gracefully: `LIST`, `fact`, `cue `, `bext`, `id3 `
and anything else. Read the size, skip that many bytes plus the pad.

werk declares the format it used in the effect sidecar's `audio_format`
block, so a consumer can check rather than discover.

---

## 10. GLB (glTF 2.0 binary)

All geometry — source, game mesh, LOD chain, fracture pieces — is GLB.

### 10.1 Container

```
offset 0  : "glTF"   4 ASCII (47 6C 54 46)
offset 4  : u32 LE   version, must be 2
offset 8  : u32 LE   total file length in bytes
offset 12 : chunks
```

Each chunk:

| size | field |
|---|---|
| 4 | u32 LE chunk length (of the data, excluding this header) |
| 4 | u32 LE chunk type |
| *length* | data, padded so that *length* is a multiple of 4 |

Chunk types: `0x4E4F534A` = `JSON`, `0x004E4942` = `BIN`. The JSON chunk
comes first and is padded with spaces (`0x20`); the BIN chunk is padded with
zeros. There is at most one of each.

### 10.2 The JSON chunk

A glTF 2.0 document. The parts werk uses:

* `asset` — `{version:"2.0", generator}`.
* `buffers[]` — for GLB, exactly one buffer with no `uri`, meaning "the BIN
  chunk", and `byteLength`.
* `bufferViews[]` — `{buffer, byteOffset, byteLength, byteStride?, target?}`.
  A view is a slice of the buffer. `byteStride` is required when the view is
  used by more than one interleaved vertex attribute.
* `accessors[]` — `{bufferView, byteOffset, componentType, count, type,
  normalized?, min?, max?}`. The element at index *i* starts at
  `bufferView.byteOffset + accessor.byteOffset + i * stride`, where *stride*
  is `bufferView.byteStride` when present and otherwise the tightly packed
  element size.
* `meshes[].primitives[]` — `{attributes:{POSITION, NORMAL, TANGENT,
  TEXCOORD_0, COLOR_0, JOINTS_0, WEIGHTS_0}, indices, material, mode}`.
  `mode` 4 is triangles and is the only mode werk core uses.
* `nodes[]`, `scenes[]`, `scene` — the hierarchy. A node has either `matrix`
  or any of `translation`/`rotation`/`scale`. glTF's `rotation` is a
  quaternion in **`[x, y, z, w]`** order — the opposite of werk's `wxyz`.
  This is the single most dangerous mismatch in the whole format and it is
  why `conventions.quat_order` exists. Convert on import and on export.
* `materials[]`, `textures[]`, `images[]`, `samplers[]` — present in a GLB
  but **not** authoritative inside a werk: the werk `core.material` node is.
  A reader that takes material parameters from the GLB instead of from
  `materials/` is non-conformant.
* `skins[]`, `animations[]` — likewise not authoritative; `core.skeleton`
  and `core.anim.clip` are.

`componentType` codes:

| code | type | bytes |
|---|---|---|
| 5120 | signed byte | 1 |
| 5121 | unsigned byte | 1 |
| 5122 | signed short | 2 |
| 5123 | unsigned short | 2 |
| 5125 | unsigned int | 4 |
| 5126 | float (binary32) | 4 |

`type` strings and their component counts: `SCALAR` 1, `VEC2` 2, `VEC3` 3,
`VEC4` 4, `MAT2` 4, `MAT3` 9, `MAT4` 16. All numeric data in the BIN chunk
is **little-endian**. Accessor byte offsets are aligned to the component
size.

### 10.3 werk's coordinate rule for GLB

glTF's own text says an asset's front faces `+Z`. werk declares
`forward_axis: "-z"`. **Inside a werk package the manifest's conventions
govern**: geometry in a werk GLB is authored in werk model space (+Y up, −Z
forward, +X right, metres, counter-clockwise front faces). A tool exchanging
with a pipeline that honours glTF's stated facing applies a 180° rotation
about Y on the way in or out, and says so in the node's work note. Nothing
in werk reads the facing from the GLB, because the GLB does not carry it as
a number.

---

## 11. SHA-256

`conventions.hash_algorithm` is `sha256`; every content hash in werk is the
lowercase hex encoding of a SHA-256 digest, 64 characters.

SHA-256 is FIPS 180-4. It is not reproduced byte-for-byte here — it is
present in every standard library werk cares about (`hashlib` in Python,
`sha2` in a hundred lines of C, `ring`/`sha2` in Rust) — but the following
test vectors let an implementer prove theirs before trusting it. All are
hex, lowercase.

| input | digest |
|---|---|
| *(empty)* | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `abc` | `ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad` |
| `abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq` | `248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1` |

Structural facts, in case you must implement it: 32-bit words, big-endian,
message padded with a `0x80` byte then zeros then the 64-bit big-endian bit
length, block size 64 bytes, 64 rounds, eight initial state words being the
first 32 bits of the fractional parts of the **square roots** of the first
eight primes, and the 64 round constants being the first 32 bits of the
fractional parts of the **cube roots** of the first 64 primes. Both
constant tables are therefore *derivable*, not data you must be given —
which is the point of stating the rule instead of printing 72 numbers.

### 11.1 SHA-512

You need this only if you verify signatures: Ed25519 (§12) is defined in
terms of SHA-512 and cannot be implemented without it. No werk content hash
uses SHA-512, so a reader that does not verify signatures can skip this
section entirely.

SHA-512 is the same construction as SHA-256 with every dimension widened,
and the same derivation rules for both constant tables:

| | SHA-256 | SHA-512 |
|---|---|---|
| word size | 32 bits | **64 bits** |
| block size | 64 bytes | **128 bytes** |
| rounds | 64 | **80** |
| length field in the padding | 64-bit big-endian | **128-bit big-endian** |
| digest | 32 bytes | **64 bytes** |
| initial state | first **32** bits of frac(√pₙ), n = 1..8 | first **64** bits of frac(√pₙ), n = 1..8 |
| round constants | first **32** bits of frac(∛pₙ), n = 1..64 | first **64** bits of frac(∛pₙ), n = 1..**80** |

The rotation amounts differ too, and they are the one thing not derivable
from a rule, so here they are. With `ROTR` a 64-bit rotate right and `SHR` a
64-bit shift right:

```
Σ0(a) = ROTR(a,28) ^ ROTR(a,34) ^ ROTR(a,39)
Σ1(e) = ROTR(e,14) ^ ROTR(e,18) ^ ROTR(e,41)
σ0(x) = ROTR(x, 1) ^ ROTR(x, 8) ^ SHR(x, 7)
σ1(x) = ROTR(x,19) ^ ROTR(x,61) ^ SHR(x, 6)
```

Everything else — the message schedule, `Ch`, `Maj`, the compression loop,
the final addition into the state — is identical to SHA-256 with 64-bit
arithmetic.

**Test vectors**, so you can prove it before Ed25519 depends on it:

| input | digest |
|---|---|
| *(empty)* | `cf83e1357eefb8bdf1542850d66d8007d620e4050b5715dc83f4a921d36ce9ce47d0d13c5d85f2b0ff8318d2877eec2f63b931bd47417a81a538327af927da3e` |
| `abc` | `ddaf35a193617abacc417349ae20413112e6fa4e89a97ea20a9eeee64b55d39a2192992a274fc1a836ba3c23a3feebbd454d4423643ce80e2a9ac94fa54ca49f` |
| `abcdefghbcdefghicdefghijdefghijkefghijklfghijklmghijklmnhijklmnoijklmnopjklmnopqklmnopqrlmnopqrsmnopqrstnopqrstu` | `8e959b75dae313da8cf4f72814fc143f8f7779c6eb9f7fa17299aeadb6889018501d289e4900f7e4331b99dec4b5433ac7d329eeb6dd26545e96e55b874be909` |

### What gets hashed

* `files[].sha256` — the exact bytes of that file in the container.
* `manifest_sha256` in `SIGNATURE.json` — the exact bytes of
  `MANIFEST.json`.
* `input_hash` — the concatenation, in `input_files` order, of each input's
  32 **raw** digest bytes, followed by the UTF-8 bytes of the canonical JSON
  (§3) of `input_params`. Raw bytes, not hex: hashing hex strings would work
  too, but there would then be two conventions and one of them would be
  wrong somewhere.

  **An absent `input_params` is the empty object.** Its canonical JSON is the
  two bytes `{}` and those two bytes are appended, exactly as they would be
  if the key were written out. "Absent" and `{}` are the same input to this
  hash and always were; nothing is ever appended as *nothing*. A writer
  SHOULD emit `"input_params": {}` explicitly so the two spellings never have
  to be reconciled by a reader at all.

  Three independently-written readers each lost time to this — it was the
  single longest detour in the gauntlet, for all three — so here it is as an
  executable statement rather than a sentence:

  ```
  input_hash(input_files, input_params):
      h = sha256_new()
      for path in input_files:                 # ORDER MATTERS
          h.update(sha256_raw_32_bytes_of(file_at(path)))
      h.update(utf8(canonical_json(input_params or {})))   # "{}" when absent
      return hex(h.digest())
  ```

  Worked example from this package, checkable by hand: node `bounds`,
  version 1, has `input_files: ["geometry/game.glb"]` and no `input_params`.
  Take `geometry/game.glb`'s declared `sha256`, decode those 64 hex
  characters to 32 bytes, append the two ASCII bytes `{}`, and SHA-256 the
  34-byte result. That is the node's declared `input_hash`.

---

## 12. Ed25519

`conventions.signature_algorithm` is `ed25519`: RFC 8032 Ed25519, pure
(neither `ph` nor `ctx` variants). Keys are 32 bytes, signatures 64 bytes,
both carried as lowercase hex in `SIGNATURE.json`.

**Use a library if you have one.** Ed25519 is easy to implement and hard to
implement *safely*, and a signature check that is subtly wrong is worse than
one that is absent. That advice stands.

But "use a library" is not an answer for a reader that is not allowed one —
the embedded Rust and C loaders may use no crates and no third-party
libraries at all — and law 2 says this file must be sufficient on its own.
So the parameters are here. Every one of them is *derivable* from the two
definitions below; none of it has to be taken on trust, and all of it is
proved by the test vector at the end.

**The curve.** Edwards curve `-x² + y² = 1 + d·x²·y²` over the prime field
`GF(p)`:

```
p  = 2^255 - 19
d  = -121665 * inverse(121666) mod p
L  = 2^252 + 27742317777372353535851937790883648493      (group order)
I  = sqrt(-1) mod p = 2^((p-1)/4) mod p                   (used in decoding)
B  = the base point: the point with y = 4/5 mod p and even x
```

`inverse(a)` is `a^(p-2) mod p` by Fermat. `B`'s x is recovered from its y by
the point-decompression rule below, choosing the root whose lowest bit is 0.

**Point encoding**, 32 bytes: y as a 255-bit little-endian integer, with the
**most significant bit of the last byte** set to the lowest bit of x. So a
public key is the compressed y of the point, sign bit in bit 255.

**Point decompression**, given 32 bytes: let `y` be the low 255 bits and
`sign` the top bit. Then

```
u = y² - 1
v = d·y² + 1
x = u·v³ · (u·v⁷)^((p-5)/8)  mod p
if v·x² == -u  then x = x·I
if v·x² != u   then the point is not on the curve — reject
if x == 0 and sign == 1 then reject
if lowest bit of x != sign then x = p - x
```

**Group law**, extended twisted-Edwards coordinates `(X, Y, Z, T)` with
`x = X/Z`, `y = Y/Z`, `T = X·Y/Z`. Addition:

```
A = (Y1-X1)·(Y2-X2)   B = (Y1+X1)·(Y2+X2)
C = T1·2d·T2          D = Z1·2·Z2
E = B-A   F = D-C   G = D+C   H = B+A
X3 = E·F   Y3 = G·H   T3 = E·H   Z3 = F·G
```

Doubling is this with the two operands equal. Scalar multiplication is
double-and-add; **a verifier's inputs are all public**, so a non-constant-time
ladder is acceptable here and only here. Never reuse that code for signing.

**Verification** of signature `(R, S)` over message `M` with public key `A`,
where `R` is the first 32 bytes and `S` the last 32 read as a little-endian
integer:

```
reject if S >= L                       (canonical S; this check is not optional)
decompress A and R to points, rejecting on failure
k = SHA-512(R || A || M) as a little-endian integer, reduced mod L
accept iff  [8]·(S·B)  ==  [8]·(R + k·A)
```

The cofactor-8 form above is the check RFC 8032 §5.1.7 describes; the
cofactorless form `S·B == R + k·A` is what most libraries do and is stricter.
Either is acceptable to werk; a verifier MUST NOT accept a signature that
fails both.

**Signing is deliberately not specified here.** A reader verifies; a writer
that signs is doing key handling, and key handling belongs in a library that
has been audited for it.

**Prove it before you trust it** — RFC 8032's own first test vector, which
is also the key the Stage 2 conformance fixture is signed with, and is
therefore public by construction:

```
secret key : 9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60
public key : d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a
message    : (empty, zero bytes)
signature  : e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b
```

**If you are using a library**, the one thing it will not tell you is how to
hand it the 32 raw key bytes this file carries, because most high-level APIs
want a structured key object. The SubjectPublicKeyInfo DER wrapper for an
Ed25519 public key is a fixed 12-byte prefix followed by the 32 raw bytes:

```
30 2a 30 05 06 03 2b 65 70 03 21 00  || <32 raw public key bytes>
```

(`2b 65 70` is the OID 1.3.101.112, "Ed25519".) That is the whole of it; the
44-byte result is what a `createPublicKey`-style call accepts as DER. A
gauntlet reader had to supply those twelve bytes from memory and prove them
against the vector above, which is precisely the outside knowledge law 2
promises you will never need.

### 12.1 What werk actually signs — the message construction

**This subsection is the one that was missing, and its absence produced a
false tampering alarm on an intact package.** Everything above tells you how
to run Ed25519; none of it tells you *what to run it over*, and a verifier
that guesses the message gets `present-and-invalid` — "somebody tampered with
this file" — on a package that is perfectly sound. Measured, on six models,
2026-08-08 (spec finding **S-OW-1**).

An entry in `SIGNATURE.json`'s `chain` signs the UTF-8 encoding of **exactly
this string**:

```
werk-sig/1 LF manifest_sha256 LF prev_entry_sha256 LF signed_at LF signer.uri LF signer.kind
```

Six fields, one `LF` (`0x0A`) between them, **no trailing newline**, UTF-8, no
BOM. Nothing is JSON-encoded, nothing is length-prefixed, nothing is
whitespace-padded, and no field may itself contain an `LF`. All six values are
read from **that entry**, not from the top-level object:

| field | where it comes from |
|---|---|
| `manifest_sha256` | `chain[i].manifest_sha256` — **the entry's own**, the manifest state as it stood when *that* signer signed. Not the top-level copy, which is only the current anchor. |
| `prev_entry_sha256` | 64 `0` characters for `index 0`; otherwise the sha256 of the **UTF-8 bytes of entry `i-1`'s `signature` string** — the 128 hex characters as text, not the 64 raw bytes they denote. |
| `signed_at` | `chain[i].signed_at`, verbatim, including the `Z`. |
| `signer.uri` | `chain[i].signer.uri`, verbatim. |
| `signer.kind` | `chain[i].signer.kind`, verbatim. |

Per-entry rather than one shared anchor because enrichment appends (law 7);
`SPEC.md` §6 argues that and gives the whole-chain verification procedure.

**A complete worked example, on real bytes.** `spec/examples/` in this same
package carries `MANIFEST.example.json`, a one-link `SIGNATURE.example.json`
over its exact bytes signed with the published RFC 8032 test key above, and
**`spec/examples/signature.example.txt`**, which shows all of it end to end.
The whole example is reproduced below so that **this section is sufficient on
its own**, even for a reader whose documentation budget did not stretch to
`spec/examples/`. Everything between the markers is generated by
`spec/examples/make-examples.py`, never hand-transcribed, so it cannot drift
from the files beside it.

<!-- BEGIN GENERATED: signature-example (spec/examples/make-examples.py) -->

```
the six fields, from chain[0] of spec/examples/SIGNATURE.example.json
  manifest_sha256    7601951bcb139307309a76006a74c589fce3450ea3a9c64ec8a2ca2da6ded14d
                     (= sha256 of the 20223 bytes of MANIFEST.example.json)
  prev_entry_sha256  0000000000000000000000000000000000000000000000000000000000000000
  signed_at          2026-08-08T09:00:00Z
  signer.uri         urn:werk:fixture:rfc8032-vector-1
  signer.kind        service

the message, as text -- the LAST field has NO newline after it
  werk-sig/1\n
  7601951bcb139307309a76006a74c589fce3450ea3a9c64ec8a2ca2da6ded14d\n
  0000000000000000000000000000000000000000000000000000000000000000\n
  2026-08-08T09:00:00Z\n
  urn:werk:fixture:rfc8032-vector-1\n
  service        <- no trailing LF

the message, as all 203 of its bytes
    00000000  77 65 72 6b 2d 73 69 67 2f 31 0a 37 36 30 31 39 35 31 62 63 62 31 33 39 33 30 37 33 30 39 61 37
    00000020  36 30 30 36 61 37 34 63 35 38 39 66 63 65 33 34 35 30 65 61 33 61 39 63 36 34 65 63 38 61 32 63
    00000040  61 32 64 61 36 64 65 64 31 34 64 0a 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30
    00000060  30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30
    00000080  30 30 30 30 30 30 30 30 30 30 30 30 0a 32 30 32 36 2d 30 38 2d 30 38 54 30 39 3a 30 30 3a 30 30
    000000a0  5a 0a 75 72 6e 3a 77 65 72 6b 3a 66 69 78 74 75 72 65 3a 72 66 63 38 30 33 32 2d 76 65 63 74 6f
    000000c0  72 2d 31 0a 73 65 72 76 69 63 65

CHECKPOINT -- compare these before you compare a signature
  len(message)     203
  sha256(message)  98461c457717453a49e8302fd850b505ee58ed1a4df0037e78c658aa64816553

verify
  public_key  d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a
  signature   99b9cb20098d0a82fa08dda98ed49c1ce3532bb4e14064403dc28da1f2b3437e
              f94a4c56d4a8e239427359d2e31189e1733733a3cb84d8b9312f350633c93f0f
  ed25519_verify(public_key, message, signature)  ->  TRUE
```

<!-- END GENERATED: signature-example -->

That `sha256(message)` is a checkpoint **for you**. Ed25519 hashes the message
itself with SHA-512 internally; you do **not** pre-hash before calling
`verify`. If your bytes do not match it, you have a construction bug and the
package in front of you is almost certainly fine.

### 12.2 The fourth token — say `unverified`, never guess

A conformant tool reports one of four words, and `SPEC.md` §10 step 4 fixes
them: **`signed-and-valid`**, **`absent`**, **`present-and-invalid`**,
**`unverified`**. A package is in one of the three states of `SPEC.md` §6;
`unverified` is the fourth word because it describes the reader ("I did not
check"), not the package.

`unverified` is the correct verdict whenever you did not perform the check —
no Ed25519 available, no time budget for it, or a deliberate decision to scope
it out. It is a legitimate, expected answer and costs nothing.

`present-and-invalid` means **a link failed**: tampering under an existing
signature. Reporting it because you could not build the message, or because
you built it wrongly, is a **false tampering alarm**, and it is the most
damaging wrong answer this format makes available — a damage report that is
wrong in the alarming direction is worse than no report at all. If §12.1's
checkpoint does not match, you have a construction bug, not a tampered
package; say `unverified` and move on.

The same bytes are given in `spec/schemas/signature.schema.json` under
`$comment` and in `SPEC.md` §6. Three copies of one construction is
deliberate: it is the fact a reader most needs and is least able to derive.

---

## 13. What werk deliberately does not use

Named so that a reader knows an absence is a decision and not an oversight:

* **No XML, no YAML, no TOML.** One structured text encoding is enough and
  JSON is the one every language already has.
* **No protobuf, no flatbuffers, no CBOR in core.** They need a schema
  compiler or a second header dialect; MessagePack's tiny subset (§4) does
  the one job werk needs.
* **No BC/DXT/ASTC/KTX2 textures in core.** They are GPU-vendor-shaped, they
  cannot be inspected without a decoder, and they belong in an `x.*` cooked
  tier — which is exactly what law 12 is for.
* **No Draco or meshopt geometry compression in core.** Same argument.
* **No 7z, no tar, no zstd container.** Store-mode zip is readable in a
  hundred lines everywhere.
* **No MP3, no Ogg, no FLAC in core.** WAV is the only audio encoding whose
  decoder is a struct read.
* **No floating-point text formats with locale-dependent separators.** JSON
  numbers use `.` and nothing else, always.
