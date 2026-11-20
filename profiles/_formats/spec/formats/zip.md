# ZIP archive: central directory, local headers, stored and deflated entries, ZIP64 — werk format definition `zip`

```werk-format
{
  "format_id": "zip",
  "format_version": 1,
  "title": "ZIP archive: central directory, local headers, stored and deflated entries, ZIP64",
  "media_type": "application/zip",
  "extensions": [
    "zip"
  ],
  "sniff": [
    {
      "magic": [
        {
          "offset": 0,
          "hex": "504b0304"
        }
      ]
    },
    {
      "magic": [
        {
          "offset": 0,
          "hex": "504b0506"
        }
      ]
    }
  ],
  "defines": {
    "decode": true,
    "encode": true
  },
  "coverage": "partial",
  "coverage_note": "Defined completely: finding the end-of-central-directory record; the central directory and local file headers; general-purpose flags (data descriptor, UTF-8 names); stored (method 0) and deflated (method 8) entries - DEFLATE by reference to format `zlib-deflate`; CRC-32; MS-DOS date and time; names in UTF-8 or code page 437 and the Unicode-path extra field; the ZIP64 end records and extra field; writing a store-mode or deflated archive. NOT defined: encryption (traditional or AES) - an encrypted entry is refused by name; compression methods other than 0 and 8 (Deflate64, BZIP2, LZMA, Zstandard, ...); multi-disk (spanned or split) archives; the central-directory digital signature and archive extra data records; other extra fields (timestamps, Unix and NTFS attributes), which are skipped; the meaning of external file attributes. A reader built from this document reads the CENTRAL DIRECTORY and does not recover entries that only a local header describes.",
  "lossy": false,
  "requires": [
    "zlib-deflate"
  ],
  "normative_sources": [
    "PKWARE APPNOTE.TXT, .ZIP File Format Specification (6.3.10); ISO/IEC 21320-1",
    "RFC 1951 (via format definition zlib-deflate)"
  ],
  "reference_tools": [
    {
      "tool_id": "format-zip-reference",
      "language": "python",
      "entrypoint": "tools/format-zip-reference/zip_dump.py"
    }
  ],
  "test_vectors": [
    {
      "id": "python-zipfile",
      "description": "Written by Python's zipfile module: five entries - a stored file, a directory entry (name ending in `/`, no data), a deflated text, a deflated file whose name is not ASCII (general-purpose bit 11: the name is UTF-8), a deflated EMPTY file (2 bytes of DEFLATE for 0 bytes) - and an archive comment.",
      "input_bytes": 621,
      "input_sha256": "8fc28780585ea41bac6c94a4f376412f868ffe2f17bba6021266526cffc28ef0",
      "output_form": "the text listing of section 9: `zip entries <n> zip64 <0|1> comment <text>`, then one `entry` line per central directory header in directory order, with the size and SHA-256 of the entry's uncompressed bytes; UTF-8, LF line ends",
      "output_bytes": 911,
      "output_sha256": "6eece337362fa3f5bd5a8a6e1cc150bf07ff8491220c09aa18f18e8654d42a82"
    },
    {
      "id": "python-streamed-data-descriptor",
      "description": "Written by Python's zipfile to a stream that cannot seek: general-purpose bit 3 is set, the local headers hold ZERO for CRC and sizes, and a data descriptor follows each entry's data. The central directory has the true values - which is why a reader goes by the central directory.",
      "input_bytes": 324,
      "input_sha256": "56a131f35b9be82c281aa247860099e736c11b45e396811709812174962be1cf",
      "output_form": "the text listing of section 9: `zip entries <n> zip64 <0|1> comment <text>`, then one `entry` line per central directory header in directory order, with the size and SHA-256 of the entry's uncompressed bytes; UTF-8, LF line ends",
      "output_bytes": 365,
      "output_sha256": "71ccd69e9d3cbe84c3673a058797bc5e41c0d829e2bee70010a906e4b7302d5c"
    },
    {
      "id": "python-zip64-local-header",
      "description": "Written by Python's zipfile with force_zip64: the LOCAL header carries a ZIP64 extra field and FFFFFFFF sizes, while the central directory - small numbers - does not. The local header is used only to find where the data starts.",
      "input_bytes": 195,
      "input_sha256": "9fec1380d7aaaa0acc18335370f442af296a223e1a532aaf547b4965c4fcad4b",
      "output_form": "the text listing of section 9: `zip entries <n> zip64 <0|1> comment <text>`, then one `entry` line per central directory header in directory order, with the size and SHA-256 of the entry's uncompressed bytes; UTF-8, LF line ends",
      "output_bytes": 202,
      "output_sha256": "76a2d0c595fdf24dad1f846a1dfc0a782b91529190fecee326d4e9cea79415e4"
    },
    {
      "id": "dotnet",
      "description": "Written by .NET System.IO.Compression.ZipArchive: `docs/readme.txt` at CompressionLevel.Optimal, and `stored.bin` (the 256 byte values) at NoCompression - which .NET writes as method 8 with a STORED DEFLATE block, 5 bytes longer than the data.",
      "input_bytes": 536,
      "input_sha256": "9ef7f0f0c7de40fb25c02219b2041c953394a87f13d95884653d0e111ba69880",
      "output_form": "the text listing of section 9: `zip entries <n> zip64 <0|1> comment <text>`, then one `entry` line per central directory header in directory order, with the size and SHA-256 of the entry's uncompressed bytes; UTF-8, LF line ends",
      "output_bytes": 370,
      "output_sha256": "45196211879b104c9deee1c850f2b9604912951d811c34e6b1afc87b89537587"
    },
    {
      "id": "zip64-end-records",
      "description": "Assembled by hand: every size and offset that has a 64-bit form uses it. The end-of-central-directory record holds FFFF / FFFFFFFF; a ZIP64 locator in front of it points at the ZIP64 end record, which has the real entry count, directory size and directory offset; each central header has FFFFFFFF for sizes and offset and a ZIP64 extra field with uncompressed size, compressed size and offset, in that order. (Real archives use these forms only above 4 GiB or 65535 entries.)",
      "input_bytes": 478,
      "input_sha256": "0de4fbf15aa3a333426cc4d8e0f1987abc6abe446687801421a69c72bcb778a8",
      "output_form": "the text listing of section 9: `zip entries <n> zip64 <0|1> comment <text>`, then one `entry` line per central directory header in directory order, with the size and SHA-256 of the entry's uncompressed bytes; UTF-8, LF line ends",
      "output_bytes": 366,
      "output_sha256": "33a861ab985d747891b0e1209ed5afc30934512ef0f8137a84a42f8fab691364"
    },
    {
      "id": "names-cp437-and-unicode-path",
      "description": "Assembled by hand: (1) a name whose bytes are code page 437 because bit 11 is clear (`81` = u-umlaut, `84` = a-umlaut, `9C` = pound sign); (2) an entry with the Info-ZIP Unicode Path extra field (7075), whose UTF-8 name replaces the header's name because its CRC-32 matches the header name's bytes, followed by a timestamp extra field (5455), which is skipped; (3) an entry whose Unicode Path field is STALE (its CRC does not match) and is therefore ignored. The archive comment is code page 437 as well.",
      "input_bytes": 461,
      "input_sha256": "46d1b56677d0bef50fa56cc8bc3da2a8625ac5155e9aab3b361ea123007d2e57",
      "output_form": "the text listing of section 9: `zip entries <n> zip64 <0|1> comment <text>`, then one `entry` line per central directory header in directory order, with the size and SHA-256 of the entry's uncompressed bytes; UTF-8, LF line ends",
      "output_bytes": 571,
      "output_sha256": "67fa64ae54e417164777522ecd604a54b3bc135c9c71744189233480f18748ce"
    }
  ]
}
```

This document is normative and self-contained — with format definition `zlib-deflate` for the
DEFLATE compression (a package that carries this document carries that one too; it is named in
the header's `requires`): with the two you can list a ZIP archive, extract and verify every
entry, and write an archive every unzip program reads.

## 1. Scope and coverage

ZIP is the container of office documents (OOXML, OpenDocument), EPUB, IDML, Java archives and
of the single-file form of a werk package itself. An archive is a sequence of **entries**
(files; directories are entries whose name ends in `/`), each stored or compressed on its own,
followed by a **central directory** that lists them, followed by an end record.

Defined: the end-of-central-directory record and how to find it (§3); the central directory
(§4); local headers and data descriptors (§5); methods 0 (stored) and 8 (deflated), CRC-32
(§6); names and their encodings (§7); ZIP64 (§8); writing (§10).

Not defined — refuse by name: encrypted entries (general-purpose bit 0, or bit 6, or method
99); compression methods other than 0 and 8; archives spanning several disks or files. Extra
fields other than ZIP64 and Unicode Path are skipped. (A werk package in single-file form is a
ZIP restricted to method 0 without data descriptors; its rules are in `spec/SPEC.md`, not
here.)

## 2. Conventions

All integers are **little-endian**. Records are recognised by 4-byte signatures beginning
`50 4B` ("PK"). **Read an archive from its END**: the central directory is the authority;
local headers are used only to find where an entry's data begins. (Bytes may precede the first
entry — a self-extractor — and offsets still count from the start of the file.)

## 3. The end-of-central-directory record (EOCD)

```
0   4   signature 50 4B 05 06
4   2   number of this disk                          (0)
6   2   disk where the central directory starts      (0)
8   2   entries in the central directory on this disk
10  2   entries in the central directory, total
12  4   size of the central directory in bytes
16  4   offset of the central directory from the start of the file
20  2   comment length n
22  n   comment
```

It is the last record of the file. To find it, search backwards from offset `file size − 22`
for the signature, down to `file size − 22 − 65535`, and take the first position `p` (the one
nearest the end) for which `p + 22 + comment length <= file size`. If the 20 bytes before it
begin with the ZIP64 locator signature, see §8.

## 4. The central directory

`total entries` headers, one after another, starting at the directory offset:

```
0   4   signature 50 4B 01 02
4   2   version made by (low byte: specification version * 10; high byte: host system)
6   2   version needed to extract (20 = deflate/directories, 45 = ZIP64)
8   2   general-purpose flags (section 5)
10  2   compression method: 0 stored, 8 deflated
12  2   modification time, MS-DOS format
14  2   modification date, MS-DOS format
16  4   CRC-32 of the uncompressed data
20  4   compressed size
24  4   uncompressed size
28  2   name length n
30  2   extra field length m
32  2   comment length k
34  2   disk number where the entry starts (0)
36  2   internal attributes
38  4   external attributes (host-dependent: high 16 bits are Unix mode bits when made on Unix)
42  4   offset of the entry's local header from the start of the file
46  n   name
    m   extra field
    k   entry comment
```

The next header follows at `46 + n + m + k`.

**MS-DOS date and time** (local time, no zone, 2-second resolution):

```
date: bits 15-9 year - 1980,  bits 8-5 month 1-12,  bits 4-0 day 1-31
time: bits 15-11 hour,        bits 10-5 minute,     bits 4-0 seconds / 2
```

**The extra field** is a sequence of blocks: 2 bytes id, 2 bytes size `s`, `s` bytes. Blocks
with ids this document does not name are skipped. Two matter: `0001` ZIP64 (§8) and `7075`
Unicode Path (§7).

## 5. Local headers, flags and data descriptors

At each entry's offset:

```
0   4   signature 50 4B 03 04
4   2   version needed
6   2   general-purpose flags
8   2   compression method
10  2   modification time
12  2   modification date
14  4   CRC-32                 }
18  4   compressed size        }  zero when flag bit 3 is set
22  4   uncompressed size      }
26  2   name length n
28  2   extra field length m
30  n   name
    m   extra field            (need NOT equal the central header's extra field or its length)
then the entry's data: `compressed size` bytes
```

**The data starts at `offset + 30 + n + m` using the LOCAL header's `n` and `m`.** Everything
else about the entry is taken from the central header.

General-purpose flags:

| bit | meaning |
|---|---|
| 0 | the entry is encrypted — not defined here |
| 1, 2 | compression options (informative) |
| 3 | **data descriptor**: the local header's CRC and sizes are zero; after the data come the real values — optionally the signature `50 4B 07 08`, then CRC-32, compressed size, uncompressed size (4 bytes each; 8 bytes each for a ZIP64 entry). A reader that uses the central directory does not need it |
| 6 | strong encryption — not defined here |
| 11 | **the name and comment are UTF-8** |

## 6. Entry data

* **Method 0, stored:** the data is the file's bytes; compressed size = uncompressed size.
* **Method 8, deflated:** the data is one **raw DEFLATE stream** — the block format of format
  definition `zlib-deflate` §5–§9 WITHOUT the 2-byte zlib header and WITHOUT the Adler-32
  trailer. It inflates to exactly `uncompressed size` bytes.

After decoding, the **CRC-32** of the bytes must equal the central header's value. CRC-32 is
the reflected CRC with polynomial `EDB88320`:

```
crc = FFFFFFFF
for each byte x:  crc = crc XOR x ;  repeat 8 times:  crc = (crc >> 1) XOR EDB88320 if (crc AND 1) else crc >> 1
result = crc XOR FFFFFFFF          (of ASCII "123456789": CBF43926; of no bytes: 00000000)
```

A directory entry has a name ending in `/`, no data, CRC 0.

## 7. Names

Names use `/` as the separator, are relative (no leading `/`, no drive letter), and the same
name may not be assumed unique. A reader that extracts to a file system must refuse names
containing `..` components or absolute paths.

The bytes of a name (and of comments) are:

1. **UTF-8**, if general-purpose bit 11 is set;
2. otherwise, if the central header's extra field has a **Unicode Path block** (id `7075`):
   1 byte version (1), 4 bytes CRC-32 of the header's name bytes, then the name in UTF-8 —
   that UTF-8 name is used **if the CRC matches the header's name bytes** (if it does not, the
   block is stale and ignored);
3. otherwise **code page 437**: bytes `00`–`7F` are ASCII; bytes `80`–`FF` are, in order,

```
80  Ç ü é â ä à å ç ê ë è ï î ì Ä Å      90  É æ Æ ô ö ò û ù ÿ Ö Ü ¢ £ ¥ ₧ ƒ
A0  á í ó ú ñ Ñ ª º ¿ ⌐ ¬ ½ ¼ ¡ « »      B0  ░ ▒ ▓ │ ┤ ╡ ╢ ╖ ╕ ╣ ║ ╗ ╝ ╜ ╛ ┐
C0  └ ┴ ┬ ├ ─ ┼ ╞ ╟ ╚ ╔ ╩ ╦ ╠ ═ ╬ ╧      D0  ╨ ╤ ╥ ╙ ╘ ╒ ╓ ╫ ╪ ┘ ┌ █ ▄ ▌ ▐ ▀
E0  α ß Γ π Σ σ µ τ Φ Θ Ω δ ∞ φ ε ∩      F0  ≡ ± ≥ ≤ ⌠ ⌡ ÷ ≈ ° ∙ · √ ⁿ ² ■ (FF = U+00A0, no-break space)
```

(In practice many writers put the local system's code page there without saying so; a reader
cannot know. Writers: set bit 11 and write UTF-8.) The archive comment has no flag and is read
as code page 437.

## 8. ZIP64

For archives beyond 4 GiB or 65535 entries, 32-bit and 16-bit fields that overflow hold
`FFFFFFFF` / `FFFF` and the real value is elsewhere.

**End records.** If the 20 bytes immediately before the EOCD are a **ZIP64 locator**

```
0   4   signature 50 4B 06 07
4   4   disk with the ZIP64 end record (0)
8   8   offset of the ZIP64 end record
16  4   total number of disks (0 or 1)
```

then at that offset is the **ZIP64 end record**, whose values replace the EOCD's:

```
0   4   signature 50 4B 06 06
4   8   size of the rest of this record
12  2   version made by
14  2   version needed
16  4   number of this disk
20  4   disk where the central directory starts
24  8   entries on this disk
32  8   entries in the central directory, total
40  8   size of the central directory
48  8   offset of the central directory
```

**Entries.** A central header whose uncompressed size, compressed size or offset is
`FFFFFFFF` (or whose disk number is `FFFF`) has a **ZIP64 extra block** (id `0001`) holding
ONLY the overflowed fields, in this fixed order: uncompressed size (8 bytes), compressed size
(8), local header offset (8), disk number (4). A field that did not overflow is absent from
the block. (A local header may have its own ZIP64 block with the two sizes; a reader that goes
by the central directory skips it.)

## 9. The canonical decoded form

A reader built from this document is checked on this exact text: UTF-8, each line ended by one
`0A` byte, items separated by single spaces.

```
zip entries <number of central headers> zip64 <1 if a ZIP64 locator was found, else 0> comment <ESC(archive comment)>
entry <ESC(name)> method <m> flags <4 lowercase hex digits> time <YYYY-MM-DDThh:mm:ss> crc <8 lowercase hex digits> packed <compressed size> size <uncompressed size> sha256 <SHA-256 of the uncompressed bytes, lowercase hex>
```

One `entry` line per central header, in directory order. `<name>` is the name of §7 as text;
`time` is the MS-DOS date and time decoded (seconds are even; a month or day of 0 is printed
as it is, two digits). `ESC(text)`: encode as UTF-8 and write each byte `21`–`7E` except `25`
as that ASCII character, every other byte as `%` and two uppercase hexadecimal digits; empty
text is a single `%`.

## 10. Writing a ZIP archive

For each file: a local header (version needed 20, flags `0800` when the name is not ASCII and
therefore written in UTF-8, else 0; method 0 or 8; time, date; CRC-32; sizes; name length;
extra length 0), the name, the data (the bytes, or a raw DEFLATE stream — the simplest is one
stored block per 65535 bytes, `zlib-deflate` §6). Then the central directory: one header per
file repeating those values, version made by 20, the local header's offset, attributes 0 (or
`10` hex in the low byte of the external attributes for a directory). Then the EOCD with the
entry count twice, the directory's size and offset, comment length 0. Compute the CRC before
writing the header, or set bit 3 and append a data descriptor. Do not write ZIP64 records
unless a value overflows. Container formats add rules of their own (EPUB and OpenDocument: the
first entry is `mimetype`, stored, without extra field — see their definitions).

## 11. Errors a reader must report rather than guess through

No EOCD; a multi-disk archive (any disk number other than 0, more than one disk in the ZIP64
locator); a ZIP64 locator that does not point at a ZIP64 end record; a central directory
outside the file or a header without its signature; an entry that is encrypted, uses a method
other than 0 or 8, has no local header signature at its offset, runs past the end of the
file, inflates to a size other than stated, or fails its CRC-32; a malformed DEFLATE stream.

## 12. Test vectors

Four inputs were written by encoders that share no code with the reference reader — Python's
zipfile module (three archives) and .NET's System.IO.Compression — and for each the name,
size, CRC-32 and SHA-256 of every entry were computed from the content that was put in and
compared with the listing. Two inputs were assembled byte by byte, with the complete expected
listing.

**Independent check (measured).** Every vector and six real archives were also read with
Python's zipfile module (its own directory reader; inflation by the C zlib library), and the
entry names in order, the sizes and the SHA-256 of every entry's bytes were compared
(`formats/tools/compare_zipfile.py`): identical on all 6 vectors — including the ZIP64 end
records, the code page 437 names and the Unicode Path extra field — and on five real archives
(two Office add-ins with 60 and 73 entries, three werk capsules with 79 to 141 entries, up to
23.7 MB). A sixth real file, a werk capsule deliberately damaged for a test, is refused by the
reference reader for a CRC-32 mismatch in one entry; zipfile's own integrity test names the
same entry.

**Second implementation.** The ZIP layer was implemented a second time, in JavaScript, as
part of the second implementation of format `opc` (`formats/tools/second/opc.js`): it reads
the three OPC vectors and five real Office packages identically. There is no separate second
implementation that runs the six vectors of THIS document.

Every input below is given in full as a `hex <id>` block; its sha256 and the sha256 of the decoded output (in the stated output form) are in the header at the top of this document. An implementation is checked by decoding each input and comparing the hash of its output.

### Vector `python-zipfile`

Written by Python's zipfile module: five entries - a stored file, a directory entry (name ending in `/`, no data), a deflated text, a deflated file whose name is not ASCII (general-purpose bit 11: the name is UTF-8), a deflated EMPTY file (2 bytes of DEFLATE for 0 bytes) - and an archive comment.

* input: 621 bytes, sha256 `8fc28780585ea41bac6c94a4f376412f868ffe2f17bba6021266526cffc28ef0`
* output form: the text listing of section 9: `zip entries <n> zip64 <0|1> comment <text>`, then one `entry` line per central directory header in directory order, with the size and SHA-256 of the entry's uncompressed bytes; UTF-8, LF line ends
* output: 911 bytes, sha256 `6eece337362fa3f5bd5a8a6e1cc150bf07ff8491220c09aa18f18e8654d42a82`
* checked when this document was built: the reference decoder's output has 5 entries whose names, sizes, CRC-32 and SHA-256 equal those of the content the archive was made from (the flags, packed sizes and times are what the encoder chose)

The output, for orientation:

```
zip entries 5 zip64 0 comment written%20by%20Python%20zipfile
entry mimetype method 0 flags 0000 time 2026-10-13T09:15:30 crc ca82b844 packed 18 size 18 sha256 a834041d0c0f570ed35fa4a86aebd4af855451cd73081a100fc89bf075ba91da
entry folder/ method 0 flags 0000 time 2026-10-13T09:15:30 crc 00000000 packed 0 size 0 sha256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
entry folder/text.txt method 8 flags 0000 time 2026-10-13T09:15:30 crc 72aadfdc packed 51 size 540 sha256 c9024b19dbefca3dbe16012afdd756ad11136bce00e0ea196d82cb4f46a5f4aa
entry Gr%C3%BC%C3%9Fe%20%E4%B8%96%E7%95%8C.txt method 8 flags 0800 time 2026-10-13T09:15:30 crc fbd37071 packed 9 size 7 sha256 f83e039796c6453a10f5519e39fd113901572316a1a8ea07cb525d2801dfd074
entry empty.bin method 8 flags 0000 time 2026-10-13T09:15:30 crc 00000000 packed 2 size 0 sha256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

```hex python-zipfile
504b0304140000000000ef494d5d44b882ca1200000012000000080000006d69
6d65747970656170706c69636174696f6e2f782d74657374504b030414000000
0000ef494d5d00000000000000000000000007000000666f6c6465722f504b03
04140000000800ef494d5ddcdfaa72330000001c0200000f000000666f6c6465
722f746578742e7478740bc94855282ccd4cce56482aca2fcf5348cbaf50c82a
cd2d2856c82f4b2d5228014ae72456552aa4e4a7eb29848c2a1e498a01504b03
04140000080800ef494d5d7170d3fb0900000007000000120000004772c3bcc3
9f6520e4b896e7958c2e747874732f3abce7f0fc5400504b0304140000000800
ef494d5d00000000020000000000000009000000656d7074792e62696e030050
4b01021400140000000000ef494d5d44b882ca12000000120000000800000000
00000000000000a401000000006d696d6574797065504b010214001400000000
00ef494d5d000000000000000000000000070000000000000000000000a40138
000000666f6c6465722f504b01021400140000000800ef494d5ddcdfaa723300
00001c0200000f0000000000000000000000a4015d000000666f6c6465722f74
6578742e747874504b01021400140000080800ef494d5d7170d3fb0900000007
000000120000000000000000000000a401bd0000004772c3bcc39f6520e4b896
e7958c2e747874504b01021400140000000800ef494d5d000000000200000000
000000090000000000000000000000a401f6000000656d7074792e62696e504b
050600000000050005001f0100001f01000019007772697474656e2062792050
7974686f6e207a697066696c65
```

### Vector `python-streamed-data-descriptor`

Written by Python's zipfile to a stream that cannot seek: general-purpose bit 3 is set, the local headers hold ZERO for CRC and sizes, and a data descriptor follows each entry's data. The central directory has the true values - which is why a reader goes by the central directory.

* input: 324 bytes, sha256 `56a131f35b9be82c281aa247860099e736c11b45e396811709812174962be1cf`
* output form: the text listing of section 9: `zip entries <n> zip64 <0|1> comment <text>`, then one `entry` line per central directory header in directory order, with the size and SHA-256 of the entry's uncompressed bytes; UTF-8, LF line ends
* output: 365 bytes, sha256 `71ccd69e9d3cbe84c3673a058797bc5e41c0d829e2bee70010a906e4b7302d5c`
* checked when this document was built: the reference decoder's output has 2 entries whose names, sizes, CRC-32 and SHA-256 equal those of the content the archive was made from (the flags, packed sizes and times are what the encoder chose)

The output, for orientation:

```
zip entries 2 zip64 0 comment %
entry streamed.txt method 8 flags 0008 time 2026-10-13T09:15:30 crc 72aadfdc packed 51 size 540 sha256 c9024b19dbefca3dbe16012afdd756ad11136bce00e0ea196d82cb4f46a5f4aa
entry second.txt method 0 flags 0008 time 2026-10-13T09:15:30 crc 24887f0e packed 23 size 23 sha256 c6fa426226025b38e6d875625761d8bef2343b26958674bf6155ac9eaf715d62
```

```hex python-streamed-data-descriptor
504b0304140008000800ef494d5d0000000000000000000000000c0000007374
7265616d65642e7478740bc94855282ccd4cce56482aca2fcf5348cbaf50c82a
cd2d2856c82f4b2d5228014ae72456552aa4e4a7eb29848c2a1e498a01504b07
08dcdfaa72330000001c020000504b0304140008000000ef494d5d0000000000
000000000000000a0000007365636f6e642e7478746166746572206120646174
612064657363726970746f72504b07080e7f88241700000017000000504b0102
1400140008000800ef494d5ddcdfaa72330000001c0200000c00000000000000
00000000a4010000000073747265616d65642e747874504b0102140014000800
0000ef494d5d0e7f882417000000170000000a0000000000000000000000a401
6d0000007365636f6e642e747874504b0506000000000200020072000000bc00
00000000
```

### Vector `python-zip64-local-header`

Written by Python's zipfile with force_zip64: the LOCAL header carries a ZIP64 extra field and FFFFFFFF sizes, while the central directory - small numbers - does not. The local header is used only to find where the data starts.

* input: 195 bytes, sha256 `9fec1380d7aaaa0acc18335370f442af296a223e1a532aaf547b4965c4fcad4b`
* output form: the text listing of section 9: `zip entries <n> zip64 <0|1> comment <text>`, then one `entry` line per central directory header in directory order, with the size and SHA-256 of the entry's uncompressed bytes; UTF-8, LF line ends
* output: 202 bytes, sha256 `76a2d0c595fdf24dad1f846a1dfc0a782b91529190fecee326d4e9cea79415e4`
* checked when this document was built: the reference decoder's output has 1 entries whose names, sizes, CRC-32 and SHA-256 equal those of the content the archive was made from (the flags, packed sizes and times are what the encoder chose)

The output, for orientation:

```
zip entries 1 zip64 0 comment %
entry big-header.txt method 8 flags 0000 time 2026-10-13T09:15:30 crc 4acce2f2 packed 49 size 100 sha256 5d1479550cf382e5b8c8d6c698b8a06ad71b85860eae39b207576eee84765306
```

```hex python-zip64-local-header
504b03042d0000000800ef494d5df2e2cc4affffffffffffffff0e0014006269
672d6865616465722e7478740100100064000000000000003100000000000000
0bc94855282ccd4cce56482aca2fcf5348cbaf50c82acd2d2856c82f4b2d5228
014ae72456552aa4e4a7eb298490a71800504b01022d002d0000000800ef494d
5df2e2cc4a31000000640000000e0000000000000000000000a4010000000062
69672d6865616465722e747874504b050600000000010001003c000000710000
000000
```

### Vector `dotnet`

Written by .NET System.IO.Compression.ZipArchive: `docs/readme.txt` at CompressionLevel.Optimal, and `stored.bin` (the 256 byte values) at NoCompression - which .NET writes as method 8 with a STORED DEFLATE block, 5 bytes longer than the data.

* input: 536 bytes, sha256 `9ef7f0f0c7de40fb25c02219b2041c953394a87f13d95884653d0e111ba69880`
* output form: the text listing of section 9: `zip entries <n> zip64 <0|1> comment <text>`, then one `entry` line per central directory header in directory order, with the size and SHA-256 of the entry's uncompressed bytes; UTF-8, LF line ends
* output: 370 bytes, sha256 `45196211879b104c9deee1c850f2b9604912951d811c34e6b1afc87b89537587`
* checked when this document was built: the reference decoder's output has 2 entries whose names, sizes, CRC-32 and SHA-256 equal those of the content the archive was made from (the flags, packed sizes and times are what the encoder chose)

The output, for orientation:

```
zip entries 2 zip64 0 comment %
entry docs/readme.txt method 8 flags 0000 time 2026-10-13T09:15:30 crc 72aadfdc packed 51 size 540 sha256 c9024b19dbefca3dbe16012afdd756ad11136bce00e0ea196d82cb4f46a5f4aa
entry stored.bin method 8 flags 0000 time 2026-10-13T09:15:30 crc 29058c73 packed 261 size 256 sha256 40aff2e9d2d8922e47afd4648e6967497158785fbd1da870e7110266bf944880
```

```hex dotnet
504b0304140000000800ef494d5ddcdfaa72330000001c0200000f000000646f
63732f726561646d652e7478740bc94855282ccd4cce56482aca2fcf5348cbaf
50c82acd2d2856c82f4b2d5228014ae72456552aa4e4a7eb29848c2a1e498a01
504b0304140000000800ef494d5d738c052905010000000100000a0000007374
6f7265642e62696e010001fffe000102030405060708090a0b0c0d0e0f101112
131415161718191a1b1c1d1e1f202122232425262728292a2b2c2d2e2f303132
333435363738393a3b3c3d3e3f404142434445464748494a4b4c4d4e4f505152
535455565758595a5b5c5d5e5f606162636465666768696a6b6c6d6e6f707172
737475767778797a7b7c7d7e7f808182838485868788898a8b8c8d8e8f909192
939495969798999a9b9c9d9e9fa0a1a2a3a4a5a6a7a8a9aaabacadaeafb0b1b2
b3b4b5b6b7b8b9babbbcbdbebfc0c1c2c3c4c5c6c7c8c9cacbcccdcecfd0d1d2
d3d4d5d6d7d8d9dadbdcdddedfe0e1e2e3e4e5e6e7e8e9eaebecedeeeff0f1f2
f3f4f5f6f7f8f9fafbfcfdfeff504b01021400140000000800ef494d5ddcdfaa
72330000001c0200000f0000000000000000000000000000000000646f63732f
726561646d652e747874504b01021400140000000800ef494d5d738c05290501
0000000100000a000000000000000000000000006000000073746f7265642e62
696e504b05060000000002000200750000008d0100000000
```

### Vector `zip64-end-records`

Assembled by hand: every size and offset that has a 64-bit form uses it. The end-of-central-directory record holds FFFF / FFFFFFFF; a ZIP64 locator in front of it points at the ZIP64 end record, which has the real entry count, directory size and directory offset; each central header has FFFFFFFF for sizes and offset and a ZIP64 extra field with uncompressed size, compressed size and offset, in that order. (Real archives use these forms only above 4 GiB or 65535 entries.)

* input: 478 bytes, sha256 `0de4fbf15aa3a333426cc4d8e0f1987abc6abe446687801421a69c72bcb778a8`
* output form: the text listing of section 9: `zip entries <n> zip64 <0|1> comment <text>`, then one `entry` line per central directory header in directory order, with the size and SHA-256 of the entry's uncompressed bytes; UTF-8, LF line ends
* output: 366 bytes, sha256 `33a861ab985d747891b0e1209ed5afc30934512ef0f8137a84a42f8fab691364`
* checked when this document was built: the reference decoder's output equals the bytes the input was encoded from

The output, for orientation:

```
zip entries 2 zip64 1 comment zip64
entry first.txt method 8 flags 0000 time 2026-10-13T09:15:30 crc 480c994a packed 49 size 200 sha256 3271f5cd2dac066cb860eab460cc718626e93068c4aa1a15044720de48859e58
entry second.bin method 0 flags 0000 time 2026-10-13T09:15:30 crc 0da62e3c packed 40 size 40 sha256 5faa4eec3611556812c2d74b437c8c49add3f910f10063d801441f7d75cd5e3b
```

```hex zip64-end-records
504b03042d0000000800ef494d5d4a990c48ffffffffffffffff090014006669
7273742e74787401001000c80000000000000031000000000000000bc9485528
2ccd4cce56482aca2fcf5348cbaf50c82acd2d2856c82f4b2d5228014ae72456
552aa4e4a7eb29840c5ec500504b03042d0000000000ef494d5d3c2ea60dffff
ffffffffffff0a0014007365636f6e642e62696e010010002800000000000000
2800000000000000000102030405060708090a0b0c0d0e0f1011121314151617
18191a1b1c1d1e1f2021222324252627504b01022d002d0000000800ef494d5d
4a990c48ffffffffffffffff09001c0000000000000000000000ffffffff6669
7273742e74787401001800c80000000000000031000000000000000000000000
000000504b01022d002d0000000000ef494d5d3c2ea60dffffffffffffffff0a
001c0000000000000000000000ffffffff7365636f6e642e62696e0100180028
0000000000000028000000000000006c00000000000000504b06062c00000000
0000002d002d00000000000000000002000000000000000200000000000000a7
00000000000000d000000000000000504b060700000000770100000000000001
000000504b050600000000ffffffffffffffffffffffff05007a69703634
```

### Vector `names-cp437-and-unicode-path`

Assembled by hand: (1) a name whose bytes are code page 437 because bit 11 is clear (`81` = u-umlaut, `84` = a-umlaut, `9C` = pound sign); (2) an entry with the Info-ZIP Unicode Path extra field (7075), whose UTF-8 name replaces the header's name because its CRC-32 matches the header name's bytes, followed by a timestamp extra field (5455), which is skipped; (3) an entry whose Unicode Path field is STALE (its CRC does not match) and is therefore ignored. The archive comment is code page 437 as well.

* input: 461 bytes, sha256 `46d1b56677d0bef50fa56cc8bc3da2a8625ac5155e9aab3b361ea123007d2e57`
* output form: the text listing of section 9: `zip entries <n> zip64 <0|1> comment <text>`, then one `entry` line per central directory header in directory order, with the size and SHA-256 of the entry's uncompressed bytes; UTF-8, LF line ends
* output: 571 bytes, sha256 `67fa64ae54e417164777522ecd604a54b3bc135c9c71744189233480f18748ce`
* checked when this document was built: the reference decoder's output equals the bytes the input was encoded from

The output, for orientation:

```
zip entries 3 zip64 0 comment Gr%C3%BC%C3%9Fe
entry %C3%BCber%20%C3%A4/%C2%A3.txt method 0 flags 0000 time 2026-10-13T09:15:30 crc 162c4f93 packed 10 size 10 sha256 781ecd9f1804324fe79a44e738327b0a21a0377b4cb63ba4b1caf890da11183f
entry %E4%B8%96%E7%95%8C.txt method 8 flags 0000 time 2026-10-13T09:15:30 crc a5833378 packed 26 size 24 sha256 e14d77d7ec3b97583656ad9718825e668058c75c1ca26869df849efd14a41e17
entry plain.txt method 0 flags 0000 time 2026-10-13T09:15:30 crc 4b26d365 packed 18 size 18 sha256 17f34eed739ca4897510d19ebd0362983843bb7f0c6b2ef0cf05b7f6a422f982
```

```hex names-cp437-and-unicode-path
504b0304140000000000ef494d5d934f2c160a0000000a0000000c0000008162
657220842f9c2e7478746370343337206e616d65504b0304140000000800ef49
4d5d783383a51a0000001800000009001c0073656b61692e74787475700f0001
e7ca8ccae4b896e7958c2e74787455540500010af9cd6a2bcdcb4cce4f495528
482cc95048ad28294a5448cb4ccd490100504b0304140000000000ef494d5d65
d3264b120000001200000009001200706c61696e2e74787475700e0001393000
0077726f6e672e7478747374616c6520756e69636f64652070617468504b0102
1400140000000000ef494d5d934f2c160a0000000a0000000c00000000000000
000000000000000000008162657220842f9c2e747874504b0102140014000000
0800ef494d5d783383a51a0000001800000009001c0000000000000000000000
3400000073656b61692e74787475700f0001e7ca8ccae4b896e7958c2e747874
55540500010af9cd6a504b01021400140000000000ef494d5d65d3264b120000
0012000000090012000000000000000000000091000000706c61696e2e747874
75700e00013930000077726f6e672e747874504b05060000000003000300d600
0000dc0000000500477281e165
```


## 13. What this definition does not cover

Encryption; Deflate64, BZIP2, LZMA, Zstandard, PPMd and other methods; spanned and split
archives; recovering entries from local headers when the central directory is damaged;
timestamps, Unix and NTFS extra fields; file attributes; the digital-signature records.

## 14. Change notes

* Version 1 (2026-10-13). No change was forced by the second implementation of the ZIP layer
  inside `opc.js`.
