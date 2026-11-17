# PDF (Portable Document Format): objects, file structure, filters, pages, content-stream grammar — werk format definition `pdf`

```werk-format
{
  "format_id": "pdf",
  "format_version": 1,
  "title": "PDF (Portable Document Format): objects, file structure, filters, pages, content-stream grammar",
  "media_type": "application/pdf",
  "extensions": [
    "pdf"
  ],
  "sniff": [
    {
      "magic": [
        {
          "offset": 0,
          "hex": "255044462d"
        }
      ]
    }
  ],
  "defines": {
    "decode": true,
    "encode": true
  },
  "coverage": "partial",
  "coverage_note": "Defined completely: the object syntax; the file structure - header, cross-reference tables and cross-reference streams, hybrid files, object streams, incremental updates; a stream whose /Length is wrong; the filters FlateDecode (through format `zlib-deflate`, which this definition requires), LZWDecode, ASCII85Decode, ASCIIHexDecode, RunLengthDecode and the TIFF (8-bit) and PNG predictors; the page tree with inherited attributes; page content as a sequence of operators with operands, inline images included, with a one-line meaning for each operator; text strings and the information dictionary; which fonts a page names and where each embedded font program is; writing a simple PDF. NOT defined: encrypted documents (refused by name); rebuilding a damaged cross-reference by scanning; the image filters DCTDecode (the data is format `jpeg`), JPXDecode, CCITTFaxDecode, JBIG2Decode and Crypt (such a stream is delivered still encoded); everything about what content operators DO - the graphics state, painting, colour, text positioning, turning character codes into Unicode, transparency; font programs themselves (TrueType/OpenType data is format `sfnt`); annotations, forms, signatures, structure trees, embedded files. With this document a reader reaches every object and every decoded page content stream of an unencrypted PDF; it does not render or extract text.",
  "lossy": false,
  "requires": [
    "zlib-deflate"
  ],
  "normative_sources": [
    "ISO 32000-1:2008 (PDF 1.7), clauses 7.2-7.5, 7.7, 7.8, 7.9.2, 8.2, 9.6-9.9 and annexes A, D",
    "ISO 32000-2:2020 (PDF 2.0), for the UTF-8 text string"
  ],
  "reference_tools": [
    {
      "tool_id": "format-pdf-reference",
      "language": "python",
      "entrypoint": "tools/format-pdf-reference/pdf_dump.py"
    }
  ],
  "test_vectors": [
    {
      "id": "hello",
      "description": "The file of section 15, exactly as printed there: five objects, a cross-reference table, one page with one line of text in a standard font. The operator listing whose hash the `page` line carries is:\n\n```\nBT\n/F1 24 Tf\n72 720 Td\n<48656c6c6f2c20776f726c64> Tj\nET\n```\n\n",
      "input_bytes": 598,
      "input_sha256": "6274e34710885b0942af3f98caa13699391d000f386eed84d643f2ed444e6027",
      "output_form": "the text listing of section 14: `pdf <version> revisions <n> objects <n>`, a `trailer` line, `info` lines, one `object` line per in-use object, then for each page a `page` line and its `font` lines; UTF-8, LF line ends",
      "output_bytes": 743,
      "output_sha256": "eebce4486291d2417fd20f713c7ccae40a36c403714f39d600f8bf1a4c1201fd"
    },
    {
      "id": "syntax",
      "description": "The object syntax, one rule per object. Line ends are CR LF in the header and the table. Object 3: every way of writing a number. Object 4: literal strings with nested parentheses, the escapes, octal escapes of one, two and three digits (`\\0053` is the byte 05 and the character `3`; `\\500` is taken modulo 256), a backslash at the end of a line, raw CR LF and CR inside a string (each one byte 0A), a backslash before an ordinary character; hexadecimal strings with an odd number of digits and with white space; empty strings of both kinds. Object 5: names with `#xx`, an encoded `/` and `%`, the empty name, raw bytes above 7F. Object 6: a key given twice (the last value, the first position), a comment that contains delimiters, a `null` value, a reference to an object that does not exist. Object 7: no white space at all between tokens. Object 9: `R` binds the two integers before it and nothing else. Object 10 has generation 3. Object 11 is empty (null). Object 14 is separated by NUL, TAB, FF and CR. The information dictionary (object 12) has a PDFDocEncoding title with a bullet, an accented letter and curly quotes, a UTF-16BE author with a character outside the basic plane, a UTF-8 subject, a value that is not a string (not listed), an empty string, and a value reached through a reference. The page tree is empty: no `page` lines.",
      "input_bytes": 1310,
      "input_sha256": "ce48e98a02074cab9fab79e4749a832da8ba65276d8cbba1433203e817971883",
      "output_form": "the text listing of section 14: `pdf <version> revisions <n> objects <n>`, a `trailer` line, `info` lines, one `object` line per in-use object, then for each page a `page` line and its `font` lines; UTF-8, LF line ends",
      "output_bytes": 1087,
      "output_sha256": "5443026b7c4ab6545c14e7eff69a0e344fce786476d6974f3dc45aa2439a41df"
    },
    {
      "id": "filters",
      "description": "One stream per filter rule; no pages. 3 Flate. 4 LZW with the default EarlyChange over 2.5 KB of noise, so that codes grow from 9 to 12 bits. 5 LZW with `/EarlyChange 0` and a clear code in the middle of the data. 6 ASCII85 with a leading `<~`, `z` groups, white space inside groups and a final group of four characters; 7 a final group of two characters, the filter named `/A85`; 8 a final group of three, ended by a lone `~`, the filter in a one-element array. 9 ASCIIHex with white space, both letter cases, an odd last digit and bytes after `>`. 10 RunLength: literal and repeat runs including the longest of each (128 bytes), the end-of-data byte, bytes after it. 11 a chain of two filters with a parallel `/DecodeParms` array whose first element is null, and a PNG predictor whose six rows use the filter types 0, 1, 2, 3, 4, 4 with three bytes per pixel. 12 PNG predictor at 1 bit per component (the left neighbour is one byte back) under LZW, row types 1 to 4. 13 PNG predictor at 16 bits per component (two bytes back). 14 TIFF predictor 2 with three components. 15 `/DCTDecode`: delivered as stored, `partial`. 16 `[/AHx /DCT]`: the hexadecimal layer is removed, the JPEG layer stays. 17 a filter that is not decoded in the MIDDLE of a chain: everything from it on stays. 18 an undefined filter name, 19 data that is not a zlib stream, 20 a character outside the ASCII85 alphabet: `undecodable`. 21 `/Length` and `/Filter` given as references to later objects. 24 an empty stream. 25 a correct `/Length` whose data contains the word `endstream`.",
      "input_bytes": 7375,
      "input_sha256": "51f18332c398bc835ab8e3a10a538c7c56196bdc829eb3d15ce9afc7f28e3fb8",
      "output_form": "the text listing of section 14: `pdf <version> revisions <n> objects <n>`, a `trailer` line, `info` lines, one `object` line per in-use object, then for each page a `page` line and its `font` lines; UTF-8, LF line ends",
      "output_bytes": 3443,
      "output_sha256": "e27737b701b4b2116093bcd5e7c555aa7d153b491527824d310ac9a798b0c057"
    },
    {
      "id": "xref-stream",
      "description": "Two revisions, both indexed by cross-reference STREAMS. The older one (object 5) has `/W [0 2 0]` - no type field, so every entry is type 1, and no generation field - and `/Index [1 5]`, and is ASCIIHex-encoded. The newer one (object 10) has `/W [1 2 1]`, three `/Index` ranges, Flate with PNG predictor 12, a `/Prev`, and replaces object 2 by a compressed object: object stream 6 holds the new page tree node, a second page and its font. The cross-reference entry of object 8 gives the WRONG index within the object stream (0, where the object is third): the pair that names 8 is used. The entry of object 11 has the undefined type 3 and is ignored. Object 5, the old cross-reference stream, is still an object of the file and is listed.",
      "input_bytes": 1103,
      "input_sha256": "0a69cce2c5c1423406c66d18ec2ca57dc32293d32ef1cd74386e54ac79cf9654",
      "output_form": "the text listing of section 14: `pdf <version> revisions <n> objects <n>`, a `trailer` line, `info` lines, one `object` line per in-use object, then for each page a `page` line and its `font` lines; UTF-8, LF line ends",
      "output_bytes": 1862,
      "output_sha256": "e242470aec0855ddf7595fd4ce39745192cac09cc7638dbc159e880565e6f55c"
    },
    {
      "id": "hybrid",
      "description": "A hybrid file with an incremental update: three cross-reference TABLES linked by `/Prev`. In the oldest, objects 4 and 5 are free - that is what a reader which knows only tables sees. The middle one lists only object 8 and its trailer has `/XRefStm`, naming cross-reference stream 8, which says where 4 and 5 really are: in object stream 6 (which is not compressed). The newest table has one entry: object 5 is free. Reading newest first: object 5 is free (found first in the newest table); object 4 is found in the `/XRefStm` stream, which is read BEFORE following `/Prev`, so the free entry of the oldest table never counts. `revisions` is 3: the `/XRefStm` stream is not a revision.",
      "input_bytes": 1037,
      "input_sha256": "a84c5e90f4bd3b048bdb0eb49d91a9aaa49607836a6ddc872f527ef5cab95ea2",
      "output_form": "the text listing of section 14: `pdf <version> revisions <n> objects <n>`, a `trailer` line, `info` lines, one `object` line per in-use object, then for each page a `page` line and its `font` lines; UTF-8, LF line ends",
      "output_bytes": 1083,
      "output_sha256": "912ea3b23fb01b813ef15f2ec6a2b7b56d06b7b84afc444cac776b8de045ba2c"
    },
    {
      "id": "incremental",
      "description": "Three revisions, each appended to the one before, all with cross-reference tables. Revision 2 replaces the content stream (object 4) and the information dictionary (object 5); its table has one subsection of two entries. Revision 3 replaces the page tree node, adds a page (objects 7, 8) and deletes object 6 with a free entry; its table has three subsections. The newest definition of each object wins; the old bytes are still in the file.",
      "input_bytes": 1309,
      "input_sha256": "ccddb9090eb070bb57c2d736312e52d41b74db6e0b2c463a9e429a49e71b2c97",
      "output_form": "the text listing of section 14: `pdf <version> revisions <n> objects <n>`, a `trailer` line, `info` lines, one `object` line per in-use object, then for each page a `page` line and its `font` lines; UTF-8, LF line ends",
      "output_bytes": 1103,
      "output_sha256": "d825d51785bb03ac2ef82bc9e50f062e9212afc77f9912de0e111db973579388"
    },
    {
      "id": "pages",
      "description": "The page tree and fonts. The root node gives `/MediaBox` (through a reference), `/Rotate 90` and `/Resources` for all pages. Its first child (object 3) overrides `/Rotate`. Page 1 (object 4) inherits everything; its `/Contents` is an array of two streams - split between `12` and `Tf`, joined with one line feed. Page 2 (object 5) has its own box (written `100.0 +50`), rotation and resources and no content at all. Page 3 (object 7), under the second child, inherits the root's values. Fonts: a standard font (no program), a TrueType font with `/FontFile2`, a Type 1 font with `/FontFile`, a composite font whose program is found through `/DescendantFonts`, a Type 3 font (no `/BaseFont`, no program), a font with `/FontFile3` and a space in its name; the entry `/Bad 5` is not a font dictionary and is skipped.",
      "input_bytes": 3267,
      "input_sha256": "40dbc0b932f8178ad193abc7c5b92515a60b3c57199d30a197681827d203f8f9",
      "output_form": "the text listing of section 14: `pdf <version> revisions <n> objects <n>`, a `trailer` line, `info` lines, one `object` line per in-use object, then for each page a `page` line and its `font` lines; UTF-8, LF line ends",
      "output_bytes": 3861,
      "output_sha256": "ba0dbcdbb219add6b44b69bb0eb5ba960519473c4d318d380f904861001ef9ea"
    },
    {
      "id": "content",
      "description": "The content-stream grammar. One page whose (Flate-compressed) content has: numbers in several spellings; an array and a dictionary as operands; strings with escapes; the operators `'`, `\"`, `T*`, `W*`, `f*`, `B*`, `b*`; an inline image whose data is text (the white space inside it is data; the two operands left before `BI` are dropped); a second inline image written without spaces after `BI`, whose BINARY data contains `EI` twice - once not preceded by white space, once not followed by a delimiter - before the real end; `true false null` as operands of an unknown operator; stray closing delimiters and a `{`, which are skipped; a comment; tokens with no white space between them; and three operands after the last operator, which are dropped. The decoded content is 0x209 bytes; its operator listing, whose hash the `page` line carries, is:\n\n```\nq\n1 0 0 1 72.5 0 cm\n/GS1 gs\n[ 3 1.5 ] 0 d\nBI << /W 2 /H 2 /BPC 8 /CS /G /F [ /AHx ] >> ID 10 2e9b0a9f178541c29ab5549ff06a56a417386996406d28f8b831aaba8699fc61 EI\nBT\n/F1 12 Tf\n1 0 0 1 72 720 Tm\n<48656c6c6f2028776f726c6429> Tj\n[ <41> -120 <42> 15.5 <43> ] TJ\nT*\n<69742773> '\n1 2 <71> \"\nET\n0 0 m\n10 10 l\n20 0 30 10 40 0 c\nh\nS\n0 0 10 10 re\nW*\nn\nf*\nB*\nb*\n/P << /MCID 0 /Lang <656e> >> BDC\nEMC\n/Span BMC\nEMC\n/Im1 Do\n1 0.5 0.25 rg\n0 g\n<61> Tj\n[ 1 ] TJ\n<41> Tj\n/N gs\nBI << /W 1 /H 1 /IM true >> ID 9 c24f9943370780c6ed8db0af34b3510127d82a4c856966b31dda4e0fe69289f7 EI\nQ\n0 0 m\n1 1 l\nS\n0 g\n1 G\n2 w\n0 J\n0 j\ntrue false null 1 unknownOp\n5 w\n```\n\n",
      "input_bytes": 828,
      "input_sha256": "0769876f50317e89f78f242a9f892eb49f473e15a9a518e99a9e23d91c1b01dd",
      "output_form": "the text listing of section 14: `pdf <version> revisions <n> objects <n>`, a `trailer` line, `info` lines, one `object` line per in-use object, then for each page a `page` line and its `font` lines; UTF-8, LF line ends",
      "output_bytes": 623,
      "output_sha256": "c673d5d263613ce43b35cf191f47e2ec844a231a44bf20c303f488c788ae1f17"
    },
    {
      "id": "lenient",
      "description": "A file that breaks the rules of PDF in ways this document nevertheless defines an outcome for (other readers repair such files differently - see the measured comparison above). The cross-reference table lists object 13 as FREE and its own trailer's `/XRefStm` stream says it is in object stream 16: the stream's entry replaces the free entry of its table (section 6.3). The root page tree node has a wrong `/Count`. Its first child (object 3) has no `/Type` but has `/Kids`: an intermediate node. Page 1 (object 4) has a `/Contents` array with a reference to a missing object, which is not counted, a font resource named `/F#31` (the name F1) and an entry `/Bad 5` that is not a font. Page 2 (object 5) has no `/Type` and no `/Kids`: a page. The second child's `/Kids` holds a page dictionary written directly, not as a reference: it is skipped. Page 3 (object 7) has `/Rotate null`, which counts as absent, so 90 is inherited. Stream 10 has a `/Length` that is too small, 11 one that is too large (and CR LF line ends), 12 none at all - there the data itself ends in a line feed and the end of line before `endstream` is a CR: exactly one end of line is removed. Stream 14 has a TIFF predictor and five bytes after the last complete row, stream 15 a PNG predictor and a final row of two bytes: the partial row is decoded as far as it goes. The font's `/BaseFont` is written `/A#zz#41`: a `#` not followed by two hexadecimal digits is an ordinary character.",
      "input_bytes": 1696,
      "input_sha256": "990da279560ba987dabfae639beb566bbec318df35872bfd2aa57679d4f5f423",
      "output_form": "the text listing of section 14: `pdf <version> revisions <n> objects <n>`, a `trailer` line, `info` lines, one `object` line per in-use object, then for each page a `page` line and its `font` lines; UTF-8, LF line ends",
      "output_bytes": 2435,
      "output_sha256": "e0592324e02517dca57c59344b700da5036c530bd3b06498324f22aa82ef00a6"
    },
    {
      "id": "reportlab-flate-a85",
      "description": "Written by reportlab: two pages, content streams with `/Filter [/ASCII85Decode /FlateDecode]`, a classic cross-reference table, an information dictionary whose title is a UTF-16BE text string.",
      "input_bytes": 2104,
      "input_sha256": "b3f24986f6ce2d75aa27c7605f15e3ec0fe4b79c9a7d84ce1f38d5be1d751874",
      "output_form": "the text listing of section 14: `pdf <version> revisions <n> objects <n>`, a `trailer` line, `info` lines, one `object` line per in-use object, then for each page a `page` line and its `font` lines; UTF-8, LF line ends",
      "output_bytes": 2435,
      "output_sha256": "12e5ae4b02d33fad6be5d79540471b5f642255edb4f0564acc83ed080f8504bd"
    },
    {
      "id": "qpdf-objstm-xrefstream",
      "description": "The same document rewritten by qpdf with every non-stream object in an object stream and a cross-reference stream (Flate, PNG predictor 12, `/W [1 2 1]`) instead of a table.",
      "input_bytes": 1315,
      "input_sha256": "aeec50375948aded217076a6cb77aca3ae2e0ecbd5117d67f9b29b99ce9a70cc",
      "output_form": "the text listing of section 14: `pdf <version> revisions <n> objects <n>`, a `trailer` line, `info` lines, one `object` line per in-use object, then for each page a `page` line and its `font` lines; UTF-8, LF line ends",
      "output_bytes": 2904,
      "output_sha256": "81959a5601da139f0c5eb59178218bf89ec7772e7f56669000c821145f1adaac"
    },
    {
      "id": "qpdf-linearized",
      "description": "The same document written by qpdf as a LINEARIZED file: the first page's objects come first and the file has two cross-reference sections linked by `/Prev`, although it was written in one pass. It is read from its end like any other file.",
      "input_bytes": 2395,
      "input_sha256": "2664afe6bc4e3c751efd606c3fe2cd85bb0f5f49ecb045662dde5c8b7ba4fe2f",
      "output_form": "the text listing of section 14: `pdf <version> revisions <n> objects <n>`, a `trailer` line, `info` lines, one `object` line per in-use object, then for each page a `page` line and its `font` lines; UTF-8, LF line ends",
      "output_bytes": 2634,
      "output_sha256": "22b8de7e799e64443674e7dd4e594f0c6e1ac09b5bd73776ad092d758061259a"
    },
    {
      "id": "mupdf-incremental",
      "description": "The same document after MuPDF added a line of text to page 1 and saved INCREMENTALLY: the original bytes, then new objects and a second cross-reference table. Page 1 now has four content streams (MuPDF wraps the old one in `q` / `Q` and appends its own) and a third font resource; page 2 is untouched.",
      "input_bytes": 2971,
      "input_sha256": "a27665eb1a7fb33c5da4f5ae1f90d82f16202b5a0ae835a3453fb87ddd684d4b",
      "output_form": "the text listing of section 14: `pdf <version> revisions <n> objects <n>`, a `trailer` line, `info` lines, one `object` line per in-use object, then for each page a `page` line and its `font` lines; UTF-8, LF line ends",
      "output_bytes": 2945,
      "output_sha256": "8b2ba8d7889620154679ee80464d35c9a77acf3184c5e74187dc9c71282b9702"
    },
    {
      "id": "pypdf-compressed",
      "description": "The same document rewritten by pypdf with Flate-compressed content streams; pypdf writes its dictionaries with other spacing and line ends than the writers above.",
      "input_bytes": 1908,
      "input_sha256": "8ec43007d3cee4589e18df3fdb481ddf5030bb22b97304f2b8af0a6528a42612",
      "output_form": "the text listing of section 14: `pdf <version> revisions <n> objects <n>`, a `trailer` line, `info` lines, one `object` line per in-use object, then for each page a `page` line and its `font` lines; UTF-8, LF line ends",
      "output_bytes": 2397,
      "output_sha256": "0f6550fb91b0eb97d3f2a86f296b7cd95d3995cdb18c3f6c2a16bf066f814632"
    },
    {
      "id": "pillow-dct",
      "description": "A 16 x 16 pixel RGB image saved as a PDF by Pillow: the page paints one image XObject whose data is a JPEG file (`/Filter /DCTDecode`). The stream is listed `partial DCTDecode`: its data is delivered as stored and is decoded with format `jpeg`.",
      "input_bytes": 1516,
      "input_sha256": "0fb7cd6e2d52677b51a0f55d1d2d91ec15d0ac09ed3b9ac616a318757c1dffce",
      "output_form": "the text listing of section 14: `pdf <version> revisions <n> objects <n>`, a `trailer` line, `info` lines, one `object` line per in-use object, then for each page a `page` line and its `font` lines; UTF-8, LF line ends",
      "output_bytes": 1099,
      "output_sha256": "b0ab9d09193975dab55a35380d9272b858ee0e88dcfd2cb6b02bef8c8b4796f1"
    }
  ]
}
```

This document is normative and self-contained — with format definition `zlib-deflate` for the
Flate compression (a package that carries this document carries that one too; it is named in
the header's `requires`): with the two you can open a PDF file, find and parse every object in
it, decode its streams, walk its pages, and read each page's content as a sequence of
operators with their operands, and you can find the fonts each page uses and where their
font programs are. You can also write a simple PDF.

It does **not** make you a PDF viewer: what the operators paint, how text is shaped from
fonts, colour, transparency are not defined here. §1 says exactly where the line is.

## 1. Scope and coverage

A PDF file is a collection of numbered **objects** (dictionaries, arrays, numbers, strings,
streams of bytes …), an index that says where each object is (the **cross-reference**), and a
**trailer** that names the root object. Everything else — pages, fonts, pictures, forms — is
built from those objects.

Defined here:

* the syntax of objects (§3, §4);
* the file: header, cross-reference **tables** and cross-reference **streams**, hybrid files,
  **object streams**, the chain of **incremental updates** (§5–§7);
* stream filters **FlateDecode, LZWDecode, ASCII85Decode, ASCIIHexDecode, RunLengthDecode**
  and the **predictors** (§8);
* the document structure down to pages: catalog, page tree, inherited attributes, content
  streams (§9);
* the **content stream** grammar — operands, operators, inline images — and the table of
  operators with what they mean in one line each (§10);
* text strings (§11) and the document information dictionary;
* **fonts by reference**: which fonts a page names and where the embedded font program is
  (§12);
* writing a simple PDF (§15).

Not defined — a reader says so by name rather than guessing:

* **encrypted documents** (the trailer has `/Encrypt`): refused. Nothing can be decoded
  without the security handler, which this document does not define;
* **repair**: rebuilding the cross-reference of a damaged file by scanning for objects. One
  repair IS defined because real files need it: a stream whose `/Length` is wrong (§5.3);
* the **image filters** `DCTDecode` (the data is a JPEG file: format `jpeg`), `JPXDecode`
  (JPEG 2000), `CCITTFaxDecode`, `JBIG2Decode`: such a stream is delivered with those filters
  still applied; and `Crypt`;
* **interpreting** content: the graphics state, painting, colour spaces, shading, text
  positioning, turning character codes into Unicode (encodings, CMaps, `ToUnicode`),
  transparency, annotations' appearance, forms (AcroForm, XFA), structure trees, digital
  signatures, JavaScript, embedded files, optional content — all of these are OBJECTS you can
  read with this document, whose meaning it does not define;
* **font programs**: TrueType / OpenType data is format `sfnt`; Type 1 and CFF programs are
  delivered as bytes;
* linearization hints (a linearized file is read like any other: from its end).

## 2. Conventions

* Bytes are written in hexadecimal; text in `code` is ASCII.
* "Offset" always means a byte offset **from the `%` of `%PDF-`** (§5.1), which is normally
  the first byte of the file.
* Object numbers are positive integers; generation numbers are 0 in nearly every file.

## 3. Lexical rules

**White space** is any of the six bytes `00` (NUL), `09` (TAB), `0A` (LF), `0C` (FF),
`0D` (CR), `20` (space). An **end of line** is CR, LF, or CR LF.

**Delimiters** are `(` `)` `<` `>` `[` `]` `{` `}` `/` `%`. Every other byte is a **regular
character**. A **token** is either a delimiter construct (string, name, array or dictionary
bracket) or a maximal run of regular characters (a number, a keyword such as `obj`, `true`,
`R`, an operator).

A **comment** begins with `%` outside a string or stream and runs to the end of the line; it
counts as white space. (`%PDF-1.7` and `%%EOF` are comments with a meaning.)

## 4. Objects

There are eight kinds of object, plus the indirect reference.

**null** — `null`. **Booleans** — `true`, `false`.

**Numbers.** An optional `+` or `-`, then digits with at most one `.`: `0`, `+17`, `-98`,
`34.5`, `-.002`, `4.`, `007`. With a `.` it is a real, without it an integer. There is no
exponent notation. There must be at least one digit. A token that is not exactly of this form
is not a number: `1e5`, `--1`, `.`, `+`, `1.2.3` are keywords.

**Literal strings** — bytes between `(` and `)`:

* parentheses nest: a balanced `(` … `)` pair inside is part of the string;
* `\` introduces an escape: `\n` (0A) `\r` (0D) `\t` (09) `\b` (08) `\f` (0C) `\(` `\)` `\\`;
  `\ddd` — one to three OCTAL digits — is the byte with that value (taken modulo 256); a `\`
  followed by an end of line means "no byte, the string continues on the next line"; a `\`
  before any other character is dropped and the character kept;
* an unescaped end of line inside the string (CR, LF or CR LF) is ONE byte `0A`.

**Hexadecimal strings** — `<` hex digits `>`; white space between digits is ignored; if the
number of digits is odd, a final `0` is assumed (`<901FA>` is the three bytes 90 1F A0). Any
other character between `<` and `>` is an error.

A string is a sequence of BYTES. What characters they mean depends on where it is used (§11).

**Names** — `/` followed by regular characters: `/Type`, `/A;Name_With-Various***Characters?`.
`#` followed by two hex digits stands for that byte (`/Adobe#20Green` is "Adobe Green";
`/#` followed by anything else is a literal `#`). `/` alone is the empty name. Names are
case-sensitive byte strings.

**Arrays** — `[` objects `]`, any kinds, nested freely.

**Dictionaries** — `<<` key value key value … `>>`: each key a name, each value any object
(a value `null` is the same as an absent key). If a key occurs twice, the last value counts.
A key that is not a name, or a key without a value, is an error.

**Indirect references** — `12 0 R`: "the object numbered 12, generation 0". Wherever an
array element or dictionary value may be an object, it may be a reference instead. In an array
or dictionary, the keyword `R` turns the two non-negative integers immediately before it into
one reference (`[1 2 3 R]` is the integer 1 and the reference `2 3 R`); any other keyword
inside an array or dictionary is an error. A reference to an object that does not exist — no
cross-reference entry, or a free one — is `null`, and so is a reference that leads back to
the object being read.

**Streams** — a dictionary followed by the keyword `stream`, an end of line (CR LF or LF — a
lone CR is tolerated), the data bytes, an end of line, and `endstream`. Only an indirect
object can be a stream. Its dictionary describes the data:

| key | meaning |
|---|---|
| `/Length` | the number of data bytes, as stored (may be an indirect reference to an integer) |
| `/Filter` | a name, or an array of names: the filters to apply IN ORDER to decode the data (§8) |
| `/DecodeParms` | a dictionary, or an array of dictionaries (or null) parallel to `/Filter` |

## 5. File structure

### 5.1 Header

The file begins `%PDF-M.m` (`%PDF-1.4`, `%PDF-2.0`). If other bytes precede it, find `%PDF-`
within the first 1024 bytes; **all offsets in the file then count from that `%`** (drop the
bytes before it and read the rest as the file). The version is the text from after `-` to
the next white-space byte, at most 11 bytes of it.

(No test vector has bytes before the header, because a vector must match this format's sniff
rule, which wants `%PDF-` at offset 0; a node whose PDF has such a prefix NAMES the format.
The rule was checked when this document was written by putting 32 bytes in front of vector
`syntax`: the reference reader and the second implementation gave the listing of the
unprefixed file, and qpdf and pdfcraft read the same objects.)

### 5.2 Indirect objects

```
12 0 obj
<object>
endobj
```

— object number, generation number, `obj`, the object, `endobj`. The cross-reference says at
which offset each one begins. If the number found at the offset is not the one looked up, the
object is unreadable. `n g obj endobj` with nothing between is the null object.

### 5.3 Stream data and a wrong /Length

The data starts after the end of line that follows `stream`. If `/Length` is present, is a
non-negative integer, and — skipping white space after `/Length` bytes of data — the keyword
`endstream` follows, the data is those `/Length` bytes. **Otherwise** (missing, wrong, or
unresolvable length) the data runs up to the first occurrence of `endstream` after its start,
with ONE end of line (CR LF, LF or CR) immediately before `endstream` removed.

### 5.4 Reading a file: start at the end

```
1. find the last `startxref` in the final 2048 bytes; the integer after it is the offset of
   the NEWEST cross-reference section
2. read that section (section 6): it gives object locations and a trailer dictionary
3. if the trailer has /XRefStm (an integer), read the cross-reference stream at that offset too
4. if the trailer has /Prev (an integer), read the older section at that offset, and so on
5. the FIRST information found for an object number wins (newest section first)
6. the trailer dictionary of the newest section is THE trailer
```

A section offset visited twice is an error (a loop).

## 6. Cross-reference sections

At a section's offset there is either the keyword `xref` (a table) or an indirect object
that is a stream with `/Type /XRef`.

### 6.1 Cross-reference table

```
xref
0 3                     <- a subsection: first object number, number of entries
0000000000 65535 f      <- object 0: free
0000000017 00000 n      <- object 1: in use, at offset 17, generation 0
0000000081 00000 n      <- object 2
5 1                     <- another subsection: object 5
0000000331 00000 n
trailer
<< /Size 6 /Root 1 0 R /Info 4 0 R /Prev 1234 >>
startxref
492
%%EOF
```

Each entry is nominally 20 bytes — a 10-digit offset, a space, a 5-digit generation, a space,
`n` or `f`, and a 2-byte end of line — but read it as three tokens: writers get the end of
line wrong. `n` = in use at that offset; `f` = free (no object). Subsections repeat until the
keyword `trailer`, which is followed by the trailer dictionary.

### 6.2 Cross-reference stream

A stream object whose dictionary is ALSO the trailer dictionary, with:

| key | meaning |
|---|---|
| `/Type /XRef` | |
| `/Size` | one more than the highest object number |
| `/W [a b c]` | the byte widths of the three fields of an entry |
| `/Index [first count …]` | pairs of first object number and count; default `[0 Size]` |
| `/Prev`, `/Root`, `/Info`, `/ID`, `/Encrypt` | as in a trailer |

Decode the stream (§8; it is usually Flate with a PNG predictor). The result is rows of
`a + b + c` bytes, one per object in the `/Index` ranges in order (if the data ends early,
the remaining objects have no entry). Each field is a big-endian
unsigned integer of its width; **a field of width 0 has the default value**: 1 for the first
field, 0 for the others.

| field 1 (type) | field 2 | field 3 | meaning |
|---|---|---|---|
| 0 | next free object | generation | free |
| 1 | offset | generation | in use, at that offset |
| 2 | number of an OBJECT STREAM | index within it | in use, compressed (§7); generation 0 |

Other types: ignore the entry (the object is null).

### 6.3 Hybrid files

A table's trailer may have `/XRefStm`: the offset of a cross-reference stream whose entries
ADD the compressed objects that a table cannot express (a reader that knows only tables sees
them as free in an OLDER table). The order of lookup is: the table, then its `/XRefStm`
stream, then the section at `/Prev` — and the first information found wins. So read the
`/XRefStm` stream right after its table, before following `/Prev`. `/Prev` and `/XRefStm`
inside that stream's own dictionary are not followed.

One leniency: if the SAME table lists an object as free and its `/XRefStm` stream has an
entry for it, the stream's entry replaces that free entry. (A free entry from a NEWER section
is never replaced.) Readers differ on this non-conforming case; this is the rule here.

### 6.4 The trailer dictionary

| key | meaning |
|---|---|
| `/Size` | one more than the highest object number |
| `/Root` | reference to the document catalog (§9) — required |
| `/Info` | reference to the information dictionary (§11) |
| `/ID` | array of two byte strings identifying the file |
| `/Prev` | offset of the previous cross-reference section |
| `/Encrypt` | the document is encrypted — NOT defined here: refuse the document |

### 6.5 Incremental updates

A PDF is changed by APPENDING: new and changed objects, a new cross-reference section whose
trailer has `/Prev` pointing at the previous one, a new `startxref`. The newest definition of
an object number replaces older ones; an object is deleted by a newer `f` entry. Reading as
§5.4 says gives the current state. Each `/Prev` step back is an earlier state of the
document — the bytes of every earlier revision are still in the file.

## 7. Object streams

An object stream (`/Type /ObjStm`) holds several objects in one compressed stream:

| key | meaning |
|---|---|
| `/N` | the number of objects in it |
| `/First` | the offset, within the DECODED data, of the first object |

The decoded data begins with `N` pairs of integers — object number, offset relative to
`/First` — and then the objects themselves, written WITHOUT `obj`/`endobj`. Object `i` (from
0, the index of a type-2 cross-reference entry) is parsed at decoded offset
`First + offset_i`. If the pair at that index names a different object number, use the pair
that names the wanted number. Streams cannot be inside object streams, and their generation
is 0.

## 8. Filters

Apply the filters of `/Filter` in order, each with the corresponding `/DecodeParms`
dictionary (if any).

| filter | abbreviation in inline images | |
|---|---|---|
| `FlateDecode` | `Fl` | §8.1 |
| `LZWDecode` | `LZW` | §8.2 |
| `ASCII85Decode` | `A85` | §8.3 |
| `ASCIIHexDecode` | `AHx` | §8.4 |
| `RunLengthDecode` | `RL` | §8.5 |
| `DCTDecode` | `DCT` | JPEG — not decoded here |
| `CCITTFaxDecode` | `CCF` | not decoded here |
| `JPXDecode`, `JBIG2Decode`, `Crypt` | | not decoded here |

When the chain reaches a filter that is not decoded here, stop: the result is the data so
far, with that filter and the ones after it still to apply. Any other filter name is an
error for that stream.

### 8.1 FlateDecode

The data is a zlib stream (format `zlib-deflate`: 2-byte header, DEFLATE blocks, Adler-32).
Inflate it; then undo the predictor (§8.6). A reader may ignore a missing or wrong Adler-32.

### 8.2 LZWDecode

Codes are packed most significant bit first, starting 9 bits wide. Codes 0–255 are bytes,
256 is "clear table", 257 is "end of data", new entries start at 258.

```
table = the 258 initial entries ; width = 9 ; prev = none
loop:
    code = next `width` bits (if the data runs out: stop)
    if code == 256: reset the table and width = 9 ; prev = none ; continue
    if code == 257: stop
    if prev is none:            entry = table[code]
    elif code < len(table):     entry = table[code] ;  append table[prev] + first byte of entry
    elif code == len(table):    entry = table[prev] + first byte of table[prev] ;  append it
    else: error
    output entry ; prev = code
    n = len(table) + EarlyChange          (EarlyChange: /DecodeParms, default 1)
    if n >= 2048: width = 12   elif n >= 1024: width = 11   elif n >= 512: width = 10
```

With the default `EarlyChange 1` the width grows one code EARLIER than in GIF (at 511, 1023,
2047 entries). Data that does not begin with a clear code is read as if it did. A writer
sends a clear code before the table would exceed 4096 entries. Then undo the predictor (§8.6).

### 8.3 ASCII85Decode

Ignore white space. An optional leading `<~` is skipped. `~` (normally `~>`) ends the data.
`z`, outside a group, is four zero bytes. Otherwise characters `!`…`u` (21–75) have the
values 0–84; each group of five is a base-85 number, most significant digit first, giving 4
bytes big-endian (a value above 2^32−1 is an error). A final group of `n` = 2, 3 or 4
characters is padded with `u` (84) to five and yields the first `n − 1` bytes of its value
taken modulo 2^32; a final group of one character is an error. Any other character is an
error.

### 8.4 ASCIIHexDecode

Pairs of hexadecimal digits, white space ignored, ended by `>` (or by the end of the data);
an odd final digit is followed by an assumed `0`. Any other character is an error.

### 8.5 RunLengthDecode

A length byte `n`: 0–127 → copy the next `n + 1` bytes; 129–255 → repeat the next byte
`257 − n` times; 128 → end of data. Data that ends without a 128, or inside a run, ends the
output there (a literal run gives the bytes that are present).

### 8.6 Predictors

`/DecodeParms` of a Flate or LZW stream may have `/Predictor` (default 1 = none), with
`/Colors` (default 1), `/BitsPerComponent` (default 8) and `/Columns` (default 1). Let

```
row_bytes = ceil(Colors * BitsPerComponent * Columns / 8)
bpp       = max(1, Colors * BitsPerComponent div 8)
```

* **Predictor 2 (TIFF), 8 bits per component:** the data is rows of `row_bytes`; in each row,
  for `i >= Colors`: `row[i] = (row[i] + row[i - Colors]) mod 256`. (Other bit depths are not
  defined here.)
* **Predictor 10–15 (PNG):** the data is rows of `1 + row_bytes` bytes: a filter-type byte,
  then the row. The value 10–15 in the dictionary is only a hint; the filter-type byte of EACH
  ROW decides. With `a` = the reconstructed byte `bpp` to the left (0 if none), `b` = the
  byte above in the previous reconstructed row (0 for the first row), `c` = the byte above-left:

  | type | reconstructed byte = (x + …) mod 256 |
  |---|---|
  | 0 | 0 |
  | 1 | a |
  | 2 | b |
  | 3 | (a + b) div 2 |
  | 4 | Paeth: with p = a + b − c, whichever of a, b, c is closest to p — ties in the order a, b, c |

  Any other filter-type byte is an error.

Data that ends inside a row (non-conforming): the partial final row is decoded as far as it
goes — for PNG its filter-type byte and however many bytes follow. A `/Predictor` value other
than 1, 2 and 10–15 is an error.

## 9. Document structure

```
trailer /Root  ->  catalog  << /Type /Catalog  /Pages -> page tree root  ... >>
page tree node     << /Type /Pages  /Kids [ refs to nodes or pages ]  /Count n >>
page               << /Type /Page  /Parent ref  /MediaBox [x0 y0 x1 y1]  /Resources <<...>>  /Contents ref or [refs] ... >>
```

**The pages of the document** are the leaves of the page tree in the order of a depth-first
walk of `/Kids`. A node is an intermediate node if its `/Type` is `/Pages` (or it has no
`/Type /Page` but has a `/Kids` array); otherwise it is a page. `/Pages` in the catalog and
every element of `/Kids` must be a REFERENCE: an element that is anything else (or refers to
something that is not a dictionary) is skipped, and a catalog whose `/Pages` is not a
reference has no pages. A node reached twice is an error. Do not trust `/Count`.

**Inherited attributes.** `/Resources`, `/MediaBox`, `/CropBox` and `/Rotate` may be given on
an ancestor node instead of the page: a page's value is its own if present, else the nearest
ancestor's (an entry whose value is written `null` counts as absent).

* `/MediaBox` — the page's size: `[x0 y0 x1 y1]` in units of 1/72 inch, origin bottom-left.
* `/Rotate` — 0, 90, 180 or 270 degrees clockwise when displayed; default 0.
* `/Resources` — the names the page's content uses: `/Font`, `/XObject` (images and reusable
  content: "forms"), `/ExtGState`, `/ColorSpace`, `/Pattern`, `/Shading`, `/Properties`.
* `/Contents` — one stream, or an array of streams. **The page's content is the decoded data
  of those streams joined with one `0A` byte between consecutive streams** (the division into
  several streams has no meaning and may fall between any two tokens). Absent: empty content.

## 10. Content streams

A content stream is a sequence of **operands followed by an operator**, in the object syntax
of §3–§4 (no indirect references, no streams):

```
BT /F1 12 Tf 72 720 Td (Hello) Tj ET
0.5 g 100 100 200 50 re f
```

Read tokens: every object is an operand; a keyword (a run of regular characters that is not a
number, `true`, `false` or `null`) is an **operator**, and takes all operands collected since
the previous operator (operands after the last operator of the stream are dropped). `'` and `"` are operators; so are `T*`, `b*`, `B*`, `f*`, `W*`. A stray
closing delimiter (`)`, `>`, `]`, `}`) or `{` is skipped.

**Inline images** are the one exception to the token grammar:

```
BI  /W 16 /H 16 /BPC 8 /CS /G /F /AHx     <- key value pairs (abbreviated keys and names)
ID <one white-space byte><the image data, raw bytes><white space>EI
```

After the operator `BI` read key–value pairs until the keyword `ID`. **One** white-space
byte follows `ID`; the image data starts after it and ends before the first `EI` that is
preceded by a white-space byte and followed by white space, a delimiter, or the end of the
stream (the white-space byte before `EI` is not data). If there is no such `EI`, the data
runs to the end of the stream. `BI … EI` counts as ONE operator; operands left over before
`BI` are dropped. The keyword `ID` is recognised only when a white-space byte (or the end of
the stream) follows it.

The operators (the number of operands is a guide; a reader passes on whatever it finds):

| operator | operands | meaning |
|---|---|---|
| `q` / `Q` | — | save / restore the graphics state |
| `cm` | a b c d e f | concatenate a matrix to the current transformation |
| `w` `J` `j` `M` | number | line width, cap, join, miter limit |
| `d` | array phase | dash pattern |
| `ri` `gs` | name | rendering intent; set parameters from `/ExtGState` |
| `i` | number | flatness |
| `m` `l` | x y | begin a subpath at; line to |
| `c` | x1 y1 x2 y2 x3 y3 | Bézier curve to |
| `v` `y` | 4 numbers | Bézier with the first / last control point on the curve |
| `h` | — | close the subpath |
| `re` | x y w h | rectangle |
| `S` `s` `f` `F` `f*` `B` `B*` `b` `b*` `n` | — | stroke / close+stroke / fill / fill even-odd / fill+stroke … / end path without painting |
| `W` `W*` | — | intersect the clipping path (non-zero / even-odd) |
| `BT` / `ET` | — | begin / end a text object |
| `Tc` `Tw` `Tz` `TL` `Tr` `Ts` | number | character spacing, word spacing, horizontal scale, leading, render mode, rise |
| `Tf` | name size | font (a key of `/Resources /Font`) and size |
| `Td` `TD` | tx ty | move to the next line (TD also sets the leading) |
| `Tm` | a b c d e f | set the text matrix |
| `T*` | — | next line |
| `Tj` | string | show text (the string holds character codes of the current font) |
| `TJ` | array | show text with adjustments: strings and numbers (thousandths of an em, subtracted) |
| `'` | string | next line, show text |
| `"` | aw ac string | set word and character spacing, next line, show text |
| `d0` `d1` | 2 / 6 numbers | glyph metrics in a Type 3 font's glyph procedure |
| `CS` `cs` | name | colour space for stroking / non-stroking |
| `SC` `SCN` `sc` `scn` | numbers [name] | colour |
| `G` `g` | gray | grey level (stroking / non-stroking) |
| `RG` `rg` | r g b | RGB colour |
| `K` `k` | c m y k | CMYK colour |
| `sh` | name | paint a shading |
| `Do` | name | paint an XObject (an image or a form) of `/Resources /XObject` |
| `BI` … `ID` … `EI` | | inline image |
| `MP` `DP` | tag [properties] | marked-content point |
| `BMC` `BDC` / `EMC` | tag [properties] | begin / end a marked-content sequence |
| `BX` / `EX` | — | begin / end a section in which unknown operators are ignored |

## 11. Text strings and the information dictionary

Strings that hold human-readable text OUTSIDE content streams (titles, names, annotation
contents) are **text strings**:

* beginning with the bytes `FE FF`: the rest is UTF-16BE;
* beginning with `EF BB BF` (PDF 2.0): the rest is UTF-8;
* otherwise **PDFDocEncoding**: each byte is the Unicode character of the same number
  (Latin-1), EXCEPT:

```
18 ˘  19 ˇ  1A ˆ  1B ˙  1C ˝  1D ˛  1E ˚  1F ˜
80 •  81 †  82 ‡  83 …  84 —  85 –  86 ƒ  87 ⁄  88 ‹  89 ›  8A −  8B ‰  8C „  8D “  8E ”  8F ‘
90 ’  91 ‚  92 ™  93 ﬁ  94 ﬂ  95 Ł  96 Œ  97 Š  98 Ÿ  99 Ž  9A ı  9B ł  9C œ  9D š  9E ž
9F (undefined: U+FFFD)   A0 €
```

The **information dictionary** (`/Info`) has text-string values under `/Title`, `/Author`,
`/Subject`, `/Keywords`, `/Creator`, `/Producer`, and dates `/CreationDate`, `/ModDate` of the
form `D:YYYYMMDDHHmmSS+HH'mm'` (everything after the year optional).

Strings INSIDE content streams (operands of `Tj`, `TJ`, `'`, `"`) are character codes of the
current font, not text strings; turning them into Unicode needs the font's encoding and is
not defined here.

## 12. Fonts by reference

A page's fonts are the entries of its `/Resources /Font` dictionary: resource name → font
dictionary.

| font `/Subtype` | the font program's place |
|---|---|
| `/Type1`, `/MMType1`, `/TrueType` | font dictionary → `/FontDescriptor` → program key |
| `/Type0` (composite) | font dictionary → `/DescendantFonts` [0] (a CID font: `/CIDFontType0` or `/CIDFontType2`) → `/FontDescriptor` → program key |
| `/Type3` | no font program: glyphs are content streams in `/CharProcs` |

The **program key** in the font descriptor is one of:

| key | the stream holds |
|---|---|
| `/FontFile` | a Type 1 font program (with `/Length1`, `/Length2`, `/Length3`: clear text, encrypted part, trailer) |
| `/FontFile2` | a TrueType font — format `sfnt` (often a subset, lacking tables a font file on disk has) |
| `/FontFile3` | per its `/Subtype`: `/Type1C` or `/CIDFontType0C` a bare CFF font; `/OpenType` an OpenType font (format `sfnt`) |

A font without any of these is not embedded: `/BaseFont` names it (one of the 14 standard
fonts — Helvetica, Times-Roman, Courier with their styles, Symbol, ZapfDingbats — or a font
the viewer must find). `/BaseFont` of an embedded subset has a six-letter tag and `+` in
front (`ABCDEF+Arial`). Other entries a text extractor needs — `/Encoding`, `/ToUnicode`,
`/Widths`, `/W` — are ordinary objects reachable from the font dictionary.

## 13. Reading procedure, in one place

```
find the header (5.1) ;  read the cross-reference chain from the end (5.4, 6)
if the trailer has a non-null /Encrypt: refuse the document
an object number -> its cross-reference entry -> parse at an offset (5.2), or out of an object stream (7)
catalog = trailer /Root ;  pages = leaves of catalog /Pages (9), with inherited attributes
for a page: content = joined decoded /Contents (9) ;  operators = tokens of the content (10)
fonts of a page = its /Resources /Font (12)
```

Circular structures occur in hostile files: guard every walk (reference chains, page tree,
`/Prev` chain) against visiting the same thing twice.

## 14. The canonical decoded form

A reader built from this document is checked on this exact text: UTF-8, each line ended by one
`0A` byte, items separated by single spaces.

```
pdf <version> revisions <number of cross-reference sections in the /Prev chain> objects <number of in-use objects>
trailer root <n g> info <n g, or -> id <first /ID string in lowercase hex, or ->
info <ESC(key)> <ESC(value as text)>          one per string-valued entry of the information dictionary, in its order
object <n> <g> <canonical object>             one per in-use object, ascending object number
page <i> object <n> <g> mediabox <canonical array, or -> rotate <canonical number, or 0> contents <number of content streams> bytes <length of the content> sha256 <of the content> operators <count> tokens <sha256 of the operator listing>
font <i> <ESC(resource name)> <ESC(subtype) or -> <ESC(BaseFont) or -> program <FontFile|FontFile2|FontFile3> <n g>      or:  program none -
```

* The **in-use objects** are the object numbers whose winning cross-reference entry is type
  `n`/1 or type 2, except object 0. Cross-reference streams and object streams are objects
  and are listed. `<g>` is the entry's generation (0 for a compressed object). `revisions`
  counts the sections followed through `/Prev`, starting with the newest (an `/XRefStm`
  stream is not counted).
* `info` lines come only if `/Info` is, or refers to, a dictionary: one for each entry whose
  value is (or refers to) a string, converted as §11 says. The `trailer` line shows `root` and
  `info` only when they are references, and `id` only when `/ID` is an array whose first
  element is a non-empty string.
* A dictionary entry whose value is `null` IS written (`/Key null`).
* **Canonical object:**

  | object | written as |
  |---|---|
  | null, booleans | `null`, `true`, `false` |
  | number | remove a leading `+`; remove leading zeros of the integer part (keep one digit: `.5` is `0.5`); remove trailing zeros of the fraction, and the `.` if nothing remains (`4.` and `4.0` are `4`); keep `-` unless the value is zero |
  | string | `<` + the bytes in lowercase hex + `>` |
  | name | `/` + `ESC` of its bytes |
  | reference | `<n> <g> R` |
  | array | `[ ` + each element followed by a space + `]`  (the empty array is `[ ]`) |
  | dictionary | `<< ` + for each entry `/` + `ESC(key)` + space + value + space, in the order the keys FIRST appear + `>>` |
  | stream | the dictionary, then ` stream raw <stored length> decoded <length> sha256 <hash of the fully decoded data>`; or, when the filter chain stops at a filter not decoded here, ` stream raw <n> partial <the remaining filter names, ESC'd, joined by commas> <length> sha256 <hash of the data so far>`; or ` stream raw <n> undecodable` when a filter fails. Filter names are written in full (`DCTDecode`, not `DCT`); the abbreviations of §8 are accepted in any stream |

  An object the reader cannot parse at all is `object <n> <g> !unreadable`.
* `page` lines, in page order; then after each page line its `font` lines in the order of the
  `/Font` dictionary (of the page's inherited `/Resources`; an entry that is not a font
  dictionary is skipped). `object` is the page's number and generation. `mediabox` and `rotate` are the inherited values, with
  references inside the array left as references. `contents` counts the elements of
  `/Contents` that are streams. The program key is the first of `FontFile`, `FontFile2`,
  `FontFile3` whose value is a reference. The **operator
  listing** is one line per operator, each ended by `0A`: the operands in canonical form,
  each followed by a space, then `ESC` of the operator; an inline image is the line
  `BI <canonical dictionary of its parameters as written> ID <data length> <SHA-256 of the data> EI`.
  If the content cannot be decoded or parsed the page line ends `contents !unreadable` instead.
* For a `/Type0` font the `program` is the descendant font's.
* `ESC(bytes)`: each byte `21`–`7E` except `25` (`%`) and `2F` (`/`) as that ASCII character,
  every other byte as `%` and two uppercase hexadecimal digits; no bytes at all give `%`.
  Text is UTF-8 encoded first. SHA-256 values are lowercase hexadecimal.

## 15. Writing a simple PDF

```
%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842]
           /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >> endobj
4 0 obj << /Length 43 >> stream
BT /F1 24 Tf 72 720 Td (Hello, world) Tj ET
endstream endobj
5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
xref
0 6
0000000000 65535 f 
<one line per object 1..5: its 10-digit offset, " 00000 n", a space and LF (20 bytes)>
trailer << /Size 6 /Root 1 0 R >>
startxref
<the offset of the word xref>
%%EOF
```

Rules that matter: offsets are exact byte offsets from the `%` of the header; `/Length` is
the exact number of bytes between the end of line after `stream` and the end of line before
`endstream`; each cross-reference entry is exactly 20 bytes; in strings escape `(`, `)` and
`\`; to compress a stream, Flate it (a zlib stream) and add `/Filter /FlateDecode`. A second
line of four bytes above 127 after the header (`%âãÏÓ`) tells transfer programs the file is
binary. To change a file without rewriting it, append (§6.5).

## 16. Errors a reader must report rather than guess through

For the whole document: no `%PDF-` in the first 1024 bytes; no `startxref` in the last 2048
bytes or no integer after it; a cross-reference section that is neither a table nor an
`/XRef` stream, is malformed, has `/W` that is not three integers or rows of width 0, or uses
a filter not decoded here; a `/Prev` chain that loops; a trailer without a `/Root` catalog; a
non-null `/Encrypt`. For one object (reported as `!unreadable`, the rest of the document is
read): an offset that does not hold `n g obj` for the right number; unterminated strings,
arrays, dictionaries; a dictionary key that is not a name; a stream without `endstream`; an
object stream that is not one, has a malformed index or lacks the object. For one stream
(`undecodable`): an undefined filter name, malformed Flate, LZW, ASCII85 or ASCIIHex data, an
undefined predictor. For a page: a page tree that loops or is deeper than 200 levels (whole
document); content that cannot be decoded or tokenised (`contents !unreadable`).

## 17. Test vectors

Nine inputs were assembled byte by byte by a small writer in `formats/tools/vectors_pdf.py`
that shares nothing with the reference reader (it concatenates text and counts offsets; its
LZW, ASCII85, run-length and predictor ENCODERS are written there; Flate through Python's
zlib). For each, the complete expected listing was typed out — the canonical form of every
object as a literal, the hashes computed from the bytes that were put in — and the reference
reader's output must equal it. Six inputs were written by other programs (reportlab 4.4,
qpdf 12.3 through pikepdf, MuPDF 1.27, pypdf 6.7, Pillow); for those the build checks what
is known independently: the title, author, page size and fonts that reportlab was asked for,
and the length and SHA-256 of each page's content, computed from the UNCOMPRESSED content
streams of the reportlab original that the four rewrites descend from.

**Independent check with qpdf (measured).** Every vector and 99 further files were also read
with qpdf 12.3.2 (through pikepdf 10.7), which shares no code with the reference reader
(`formats/tools/compare_pikepdf.py`). Compared per file: every in-use object except
cross-reference and object streams, which qpdf does not expose (non-stream objects in the
canonical form of §14 with dictionary keys sorted — qpdf does not keep their order — and with
references to objects not in use read as null and null entries left out, as qpdf presents
them; for streams the SHA-256 of the decoded data wherever qpdf decodes it); the text strings
of the information dictionary converted to Unicode; the list of pages by object number; each
page's decoded content; the number of operators in it.

* **14 of the 15 vectors agree in everything** (hello, syntax, filters, xref-stream, hybrid,
  incremental, pages, content and the six written by other programs): 156 objects, 42 decoded
  streams — every filter and predictor case of `filters` among them, LZW included —, 48 text
  strings, 21 pages, their content and operator counts.
* On `lenient`, the vector of rule-breaking input, qpdf repairs differently, as expected: it
  keeps the end of line before `endstream` when `/Length` is wrong (three streams one or two
  bytes longer); it pads a partial final predictor row to full length instead of ending the
  output where the data ends (two streams); it treats the object that the table calls free as free, although the
  same section's `/XRefStm` locates it; it makes the page written directly in `/Kids` a page
  (4 pages, where this document counts 3); and it stops at the `null` in a `/Contents` array.
* The 99 further files: 78 PDFs shipped with software on the build machine (MiKTeX package
  documentation, Adobe and Autodesk product documents, an Intel guide: 62.7 MB, PDF 1.3 to
  1.6, 21 of them with cross-reference streams and object streams, 9 with more than one
  revision, 2,167 pages), 18 written for this purpose by reportlab, qpdf (object streams,
  QDF, linearized), MuPDF (incremental, ASCII), pypdf, Pillow, matplotlib (Type 3 and Type 42
  fonts), pdfLaTeX and Chrome, and 3 test files of pdfcraft. **98 agree in everything**:
  62,469 objects, 8,538 decoded streams, 549 text strings, 2,198 pages with their content and
  operator counts. The one difference is a stream whose `/Length` is wrong in a pdfcraft test
  file (`openssl-signed.pdf`): the same end-of-line difference as above.

**Check against the suite's own reader (measured).** The same 15 vectors and the 78 shipped
files were read with pdfcraft's reader (crates `pdfcraft-cos`, `-model`, `-content` 0.7.1,
through a scratch program) and compared: version, number of revisions, number of in-use
objects; for every stream both decode, the stored length, decoded length and SHA-256; the
pages by object number, their rotation, number of content streams, content SHA-256 and
operator count. **All 78 files agree in everything** (8,945 streams, 2,167 pages). On the
vectors everything agrees — including every stream of `lenient`, its page count and its
same-section `/XRefStm` rule, which were taken from pdfcraft — except three things, where
this document follows ISO 32000 (and qpdf agrees with it): pdfcraft reports the empty object
of `syntax` (`11 0 obj endobj`) as unreadable; it does not follow a `/Filter` given as an
indirect reference (stream 21 of `filters` stays encoded); and it lets `/Rotate null` on a
page hide the inherited value (page 3 of `lenient`: 0, here 90).

**Second implementation (measured).** The reader was written a second time, in JavaScript
(`formats/tools/second/pdf.js` in the craft-werk source tree; the zlib layer by Node's
zlib), following this text section by section: it reproduces the stated output hash of all
15 vectors, and its listing is byte-identical to the reference reader's on the 99 further
files named above (11.5 MB of listings, which carry the SHA-256 of every decoded stream and
of every page's operator listing). It was written by the author of the reference reader with
that reader's source at hand, so it shows that the text is sufficient, less strongly that
nothing is missing from it; what it did show to be missing is in the change notes.

Not checked by any independent tool: the operator LISTING itself beyond its count (qpdf and
pdfcraft tokenise, but their operand values were not compared); LZW on real files (none of
the 99 uses it; the vectors' LZW streams agree with qpdf and pdfcraft); a file produced by
following §15 was not opened in a viewer — the `hello` vector IS that file, and qpdf and
pdfcraft read it.

Every input below is given in full as a `hex <id>` block; its sha256 and the sha256 of the decoded output (in the stated output form) are in the header at the top of this document. An implementation is checked by decoding each input and comparing the hash of its output.

### Vector `hello`

The file of section 15, exactly as printed there: five objects, a cross-reference table, one page with one line of text in a standard font. The operator listing whose hash the `page` line carries is:

```
BT
/F1 24 Tf
72 720 Td
<48656c6c6f2c20776f726c64> Tj
ET
```



* input: 598 bytes, sha256 `6274e34710885b0942af3f98caa13699391d000f386eed84d643f2ed444e6027`
* output form: the text listing of section 14: `pdf <version> revisions <n> objects <n>`, a `trailer` line, `info` lines, one `object` line per in-use object, then for each page a `page` line and its `font` lines; UTF-8, LF line ends
* output: 743 bytes, sha256 `eebce4486291d2417fd20f713c7ccae40a36c403714f39d600f8bf1a4c1201fd`
* checked when this document was built: the reference decoder's output equals the bytes the input was encoded from

The output, for orientation:

```
pdf 1.4 revisions 1 objects 5
trailer root 1 0 info - id -
object 1 0 << /Type /Catalog /Pages 2 0 R >>
object 2 0 << /Type /Pages /Kids [ 3 0 R ] /Count 1 >>
object 3 0 << /Type /Page /Parent 2 0 R /MediaBox [ 0 0 595 842 ] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>
object 4 0 << /Length 43 >> stream raw 43 decoded 43 sha256 1ad21fbc00a0b653a5760dd80ac3abcde75e8afd451dd093aa66afde6e19b0e9
object 5 0 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
page 1 object 3 0 mediabox [ 0 0 595 842 ] rotate 0 contents 1 bytes 43 sha256 1ad21fbc00a0b653a5760dd80ac3abcde75e8afd451dd093aa66afde6e19b0e9 operators 5 tokens e36a320854bae9ece26faa1e94cd6901d1d424e174578ddbf27911a4075681f3
font 1 F1 Type1 Helvetica program none -
```

```hex hello
255044462d312e340a312030206f626a203c3c202f54797065202f436174616c
6f67202f5061676573203220302052203e3e20656e646f626a0a322030206f62
6a203c3c202f54797065202f5061676573202f4b696473205b33203020525d20
2f436f756e742031203e3e20656e646f626a0a332030206f626a203c3c202f54
797065202f50616765202f506172656e74203220302052202f4d65646961426f
78205b30203020353935203834325d0a20202020202020202020202f5265736f
7572636573203c3c202f466f6e74203c3c202f4631203520302052203e3e203e
3e202f436f6e74656e7473203420302052203e3e20656e646f626a0a34203020
6f626a203c3c202f4c656e677468203433203e3e2073747265616d0a4254202f
463120323420546620373220373230205464202848656c6c6f2c20776f726c64
2920546a2045540a656e6473747265616d20656e646f626a0a352030206f626a
203c3c202f54797065202f466f6e74202f53756274797065202f547970653120
2f42617365466f6e74202f48656c766574696361203e3e20656e646f626a0a78
7265660a3020360a303030303030303030302036353533352066200a30303030
303030303039203030303030206e200a30303030303030303538203030303030
206e200a30303030303030313135203030303030206e200a3030303030303032
3532203030303030206e200a30303030303030333435203030303030206e200a
747261696c6572203c3c202f53697a652036202f526f6f74203120302052203e
3e0a7374617274787265660a3431350a2525454f460a
```

### Vector `syntax`

The object syntax, one rule per object. Line ends are CR LF in the header and the table. Object 3: every way of writing a number. Object 4: literal strings with nested parentheses, the escapes, octal escapes of one, two and three digits (`\0053` is the byte 05 and the character `3`; `\500` is taken modulo 256), a backslash at the end of a line, raw CR LF and CR inside a string (each one byte 0A), a backslash before an ordinary character; hexadecimal strings with an odd number of digits and with white space; empty strings of both kinds. Object 5: names with `#xx`, an encoded `/` and `%`, the empty name, raw bytes above 7F. Object 6: a key given twice (the last value, the first position), a comment that contains delimiters, a `null` value, a reference to an object that does not exist. Object 7: no white space at all between tokens. Object 9: `R` binds the two integers before it and nothing else. Object 10 has generation 3. Object 11 is empty (null). Object 14 is separated by NUL, TAB, FF and CR. The information dictionary (object 12) has a PDFDocEncoding title with a bullet, an accented letter and curly quotes, a UTF-16BE author with a character outside the basic plane, a UTF-8 subject, a value that is not a string (not listed), an empty string, and a value reached through a reference. The page tree is empty: no `page` lines.

* input: 1310 bytes, sha256 `ce48e98a02074cab9fab79e4749a832da8ba65276d8cbba1433203e817971883`
* output form: the text listing of section 14: `pdf <version> revisions <n> objects <n>`, a `trailer` line, `info` lines, one `object` line per in-use object, then for each page a `page` line and its `font` lines; UTF-8, LF line ends
* output: 1087 bytes, sha256 `5443026b7c4ab6545c14e7eff69a0e344fce786476d6974f3dc45aa2439a41df`
* checked when this document was built: the reference decoder's output equals the bytes the input was encoded from

The output, for orientation:

```
pdf 1.7 revisions 1 objects 14
trailer root 1 0 info 12 0 id 00ff61
info Title %E2%80%A2%20caf%C3%A9%20%E2%80%9Cq%E2%80%9D
info Author W%C3%A9%F0%9F%98%80
info Subject UTF-8%20%C3%BC
info Empty %
info Keywords two%20words
object 1 0 << /Type /Catalog /Pages 2 0 R >>
object 2 0 << /Type /Pages /Kids [ ] /Count 0 >>
object 3 0 [ 0 17 -98 34.5 -0.002 4 7 0 0 0.5 123456789012 -7.25 ]
object 4 0 [ <6128622963> <6c696e65310a6c696e6532> <413007053340> <7879> <7261770a656f6c0a6372> <7129285c> <> <901fa0> <48656c6c6f> <> ]
object 5 0 [ /Name /A%20B /AB /a%2Fb /% /50%25 /%C3%9C /A;Name_With-Various***Characters? ]
object 6 0 << /A 2 /B [ 1 0 R 2 0 R ] /C null /D << /E true /F false >> /G 99 0 R >>
object 7 0 << /K [ /N <73> <41> 1 0 R ] /L /M >>
object 8 0 -12.5
object 9 0 [ 1 2 3 R 4 5 R [ 6 7 ] null true ]
object 10 3 <67656e65726174696f6e207468726565>
object 11 0 null
object 12 0 << /Title <8020636166e9208d718e> /Author <feff005700e9d83dde00> /Subject <efbbbf5554462d3820c3bc> /Count 5 /Empty <> /Keywords 13 0 R >>
object 13 0 <74776f20776f726473>
object 14 0 << /Tab 1 /Cr 2 >>
```

```hex syntax
255044462d312e370d0a25e2e3cfd30d0a312030206f626a0a3c3c2f54797065
2f436174616c6f672f50616765732032203020523e3e0a656e646f626a0a3220
30206f626a0a3c3c202f54797065202f5061676573202f4b696473205b205d20
2f436f756e742030203e3e0a656e646f626a0a332030206f626a0a5b2030202b
3137202d39382033342e35202d2e30303220342e20303037202d30202b302e30
202e3520313233343536373839303132202d3030372e32353030205d0a656e64
6f626a0a342030206f626a0a5b2861286229632920286c696e65315c6e6c696e
65322920285c3130315c36305c375c303035335c353030292028785c0d0a7929
20287261770d0a656f6c0d63722920285c715c295c285c5c29202829203c3930
3146413e203c2034382036352036430a3663203646203e203c3e5d0a656e646f
626a0a352030206f626a0a5b2f4e616d65202f4123323042202f41233432202f
6123324662202f202f3530233235202fc39c202f413b4e616d655f576974682d
566172696f75732a2a2a436861726163746572733f5d0a656e646f626a0a3620
30206f626a0a3c3c202f412031202f42205b31203020522032203020525d202f
4120322025206120636f6d6d656e742029202820776974682064656c696d6974
6572730a202f43206e756c6c202f44203c3c202f452074727565202f46206661
6c7365203e3e202f4720393920302052203e3e0a656e646f626a0a372030206f
626a0a3c3c2f4b5b2f4e2873293c34313e31203020525d2f4c2f4d3e3e0a656e
646f626a0a382030206f626a0a2d31322e35300a656e646f626a0a392030206f
626a0a5b31203220332052203420352052205b3620375d206e756c6c20747275
655d0a656e646f626a0a31302033206f626a0a2867656e65726174696f6e2074
68726565290a656e646f626a0a31312030206f626a20656e646f626a0a313220
30206f626a0a3c3c202f5469746c6520285c323030206361665c333531205c32
3135715c32313629202f417574686f72203c4645464620303035372030304539
204438334420444530303e202f5375626a6563742028efbbbf5554462d3820c3
bc29202f436f756e742035202f456d707479202829202f4b6579776f72647320
313320302052203e3e0a656e646f626a0a31332030206f626a0a2874776f2077
6f726473290a656e646f626a0a31342030206f626a0a3c3c002f54616209310c
2f43720d32203e3e0a656e646f626a0a787265660a302031350a303030303030
3030303020363535333520660d0a30303030303030303137203030303030206e
0d0a30303030303030303632203030303030206e0d0a30303030303030313135
203030303030206e0d0a30303030303030313936203030303030206e0d0a3030
3030303030333233203030303030206e0d0a3030303030303034313420303030
3030206e0d0a30303030303030353339203030303030206e0d0a303030303030
30353831203030303030206e0d0a30303030303030363033203030303030206e
0d0a30303030303030363530203030303033206e0d0a30303030303030363835
203030303030206e0d0a30303030303030373031203030303030206e0d0a3030
3030303030383439203030303030206e0d0a3030303030303038373720303030
3030206e0d0a747261696c65720a3c3c202f53697a65203135202f526f6f7420
3120302052202f496e666f20313220302052202f4944205b3c3030464636313e
203c30313e5d203e3e0a7374617274787265660a3931320a2525454f460a
```

### Vector `filters`

One stream per filter rule; no pages. 3 Flate. 4 LZW with the default EarlyChange over 2.5 KB of noise, so that codes grow from 9 to 12 bits. 5 LZW with `/EarlyChange 0` and a clear code in the middle of the data. 6 ASCII85 with a leading `<~`, `z` groups, white space inside groups and a final group of four characters; 7 a final group of two characters, the filter named `/A85`; 8 a final group of three, ended by a lone `~`, the filter in a one-element array. 9 ASCIIHex with white space, both letter cases, an odd last digit and bytes after `>`. 10 RunLength: literal and repeat runs including the longest of each (128 bytes), the end-of-data byte, bytes after it. 11 a chain of two filters with a parallel `/DecodeParms` array whose first element is null, and a PNG predictor whose six rows use the filter types 0, 1, 2, 3, 4, 4 with three bytes per pixel. 12 PNG predictor at 1 bit per component (the left neighbour is one byte back) under LZW, row types 1 to 4. 13 PNG predictor at 16 bits per component (two bytes back). 14 TIFF predictor 2 with three components. 15 `/DCTDecode`: delivered as stored, `partial`. 16 `[/AHx /DCT]`: the hexadecimal layer is removed, the JPEG layer stays. 17 a filter that is not decoded in the MIDDLE of a chain: everything from it on stays. 18 an undefined filter name, 19 data that is not a zlib stream, 20 a character outside the ASCII85 alphabet: `undecodable`. 21 `/Length` and `/Filter` given as references to later objects. 24 an empty stream. 25 a correct `/Length` whose data contains the word `endstream`.

* input: 7375 bytes, sha256 `51f18332c398bc835ab8e3a10a538c7c56196bdc829eb3d15ce9afc7f28e3fb8`
* output form: the text listing of section 14: `pdf <version> revisions <n> objects <n>`, a `trailer` line, `info` lines, one `object` line per in-use object, then for each page a `page` line and its `font` lines; UTF-8, LF line ends
* output: 3443 bytes, sha256 `e27737b701b4b2116093bcd5e7c555aa7d153b491527824d310ac9a798b0c057`
* checked when this document was built: the reference decoder's output equals the bytes the input was encoded from

The output, for orientation:

```
pdf 1.5 revisions 1 objects 25
trailer root 1 0 info - id -
object 1 0 << /Type /Catalog /Pages 2 0 R >>
object 2 0 << /Type /Pages /Kids [ ] /Count 0 >>
object 3 0 << /Length 68 /Filter /FlateDecode >> stream raw 68 decoded 240 sha256 6c2fed0cb7ad1d8b1bd836c738632f15d38d4d41da10cadf4679383489ac8ff3
object 4 0 << /Length 3226 /Filter /LZWDecode >> stream raw 3226 decoded 2540 sha256 f6f9f0d971c892e2474995c61695ed5e2d026939758381fd62f0612683085490
object 5 0 << /Length 975 /Filter /LZWDecode /DecodeParms << /EarlyChange 0 >> >> stream raw 975 decoded 940 sha256 5223b79dc936c6e8d0da0e2e1c40547aa43d375c455e5652ac69f566218c38dd
object 6 0 << /Length 39 /Filter /ASCII85Decode >> stream raw 39 decoded 30 sha256 794284dfe14b2b392b3cdafdb8369d799040305ea6a7e49fed55c3ae7f8e0c7b
object 7 0 << /Length 9 /Filter /A85 >> stream raw 9 decoded 5 sha256 5994471abb01112afcc18159f6cc74b4f511b99806da59b3caf5a9c173cacfc5
object 8 0 << /Length 9 /Filter [ /ASCII85Decode ] >> stream raw 9 decoded 6 sha256 8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92
object 9 0 << /Length 23 /Filter /ASCIIHexDecode >> stream raw 23 decoded 6 sha256 be84a32467c54987b1c804331816cab250aeb3850254d404a2ba2ad4e6364099
object 10 0 << /Length 147 /Filter /RunLengthDecode >> stream raw 147 decoded 266 sha256 6c9a7d4dcff361ba4aad516a57fef2bc6e69446873cc4f9f2ef8eaffc74c2ac2
object 11 0 << /Length 66 /Filter [ /ASCII85Decode /FlateDecode ] /DecodeParms [ null << /Predictor 15 /Colors 3 /BitsPerComponent 8 /Columns 4 >> ] >> stream raw 66 decoded 72 sha256 e066ed5c691e7548 ...
object 12 0 << /Length 16 /Filter /LZW /DecodeParms << /Predictor 12 /BitsPerComponent 1 /Columns 10 >> >> stream raw 16 decoded 8 sha256 4311fa557d02ac25267a6c7d313c21a7497f4fa1a034ee417ac7dc1e5d48db11
object 13 0 << /Length 22 /Filter /Fl /DecodeParms << /Predictor 10 /BitsPerComponent 16 /Columns 3 >> >> stream raw 22 decoded 18 sha256 6594470eaad128efbc662076bf193da9ccd8c1578b8c8a3dd18b574051a19c60
object 14 0 << /Length 18 /Filter /FlateDecode /DecodeParms << /Predictor 2 /Colors 3 /Columns 5 >> >> stream raw 18 decoded 30 sha256 945f38ee11ecac36ce1a4595b7a947bc9be480c6017a2efde3a857ad280ae49a
object 15 0 << /Type /XObject /Subtype /Image /Width 1 /Height 1 /Length 25 /Filter /DCTDecode >> stream raw 25 partial DCTDecode 25 sha256 e049d9dab7db79815e112f6c00b0f33f565fd7e66e565b5e762a2f750be1bb41
object 16 0 << /Length 51 /Filter [ /AHx /DCT ] >> stream raw 51 partial DCTDecode 25 sha256 e049d9dab7db79815e112f6c00b0f33f565fd7e66e565b5e762a2f750be1bb41
object 17 0 << /Length 27 /Filter [ /FlateDecode /JPXDecode /ASCII85Decode ] >> stream raw 27 partial JPXDecode,ASCII85Decode 19 sha256 5498ab80725c35f4fc0b7b54cd10bea5909215a028c7ac7e5cc68055f73d1998
object 18 0 << /Length 4 /Filter /FooDecode >> stream raw 4 undecodable
object 19 0 << /Length 9 /Filter /FlateDecode >> stream raw 9 undecodable
object 20 0 << /Length 5 /Filter /ASCII85Decode >> stream raw 5 undecodable
object 21 0 << /Length 22 0 R /Filter 23 0 R >> stream raw 10 decoded 4 sha256 ba31188f8190c477b5442e99b71d96347f24fa9f72f67bc8c96a30f2a207c060
object 22 0 10
object 23 0 /ASCIIHexDecode
object 24 0 << /Length 0 >> stream raw 0 decoded 0 sha256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
object 25 0 << /Length 46 >> stream raw 46 decoded 46 sha256 8d47bd6ef9b9b2647c365f084510093f89fbad39553440ed9330a503b2b9289d
```

```hex filters
255044462d312e350a312030206f626a0a3c3c202f54797065202f436174616c
6f67202f5061676573203220302052203e3e0a656e646f626a0a322030206f62
6a0a3c3c202f54797065202f5061676573202f4b696473205b5d202f436f756e
742030203e3e0a656e646f626a0a332030206f626a0a3c3c202f4c656e677468
203638202f46696c746572202f466c6174654465636f6465203e3e0a73747265
616d0a78da2b4f2dca5648cb2fca4d2c5148494dcbcccb2cc9cccf2b5628294a
2c4bcd5128cf2cc95028c9485548492c4904312a81aa8a938b329352f514ca87
a05e004a8a59310a656e6473747265616d0a656e646f626a0a342030206f626a
0a3c3c202f4c656e6774682033323236202f46696c746572202f4c5a57446563
6f6465203e3e0a73747265616d0a8037008655507d5a1d2d369caac0d878be13
381e4d8fd083fc32af3007408ac5a074042b231e0e63a7937cbeae5b820b2d17
70e420cb242556acc448a422ff032d8c42e6f8f1f2357e92d282865024f84459
808bc962facdd46d563505a81371a55ee07321c989c0239da4362e8b0c0c9753
d0f2f643281d69313390c4126a83596b33b854d46a1d1a1748e6d9d010464f3c
d9cb3053e1a0dd342edf05f7d091e4d27e0610efb2e21d74b41c0c94a9b0d8f4
207c7b9e1ac7f711b5f011488a4fc934ab2c24c52bb38b4f16a05830d70caf00
85b3f264caf151250e2c4152b0d4a91c310eac7568c870020f814762c4c869f8
eb0ab799f7a701f178d60f25c369a05a757c9731b4d24fc57b7d448c4b88c8a6
275b740e65383fcb0893533dee651dc1f838749c8050d0729bc4991a1c1383e9
7a6b8b6049a8739c4198881f89446188509206b1705c1b8308be6891c1417c2c
81c550a00d8a0450d41b052730e06f8aa3b9746e088368865d9520402e6b1807
b0f6040c2381b216992090e42d8483f184711b4589640213c101003a06e4d0de
480186e85c2f0e47a8122416c2c1a24b9d261918588dc699ba09088310640602
85395e1f9f4061bc6b02667026431962b940239c82d97c6888a5a06c6a9107f1
a4000827910e5881e418be3a0ca5d0502302c291be44144099b25f8847796e08
96a6f00e3f9923c974719502c094549d016950268a04e9cc4c0d6711524d19e1
089833054461aa480221b930339125d95a798a246826569ea0e1420092856160
420d87a9147a8543d1227a9e65585e430645d102228401e98633828440f43a92
0640c66380e7003c610e001934689160b07e121ec619bc159de2e8b4689cc3b0
263c9942102c5c8205500a6c9061818e0519e429e033196761de56112261f45b
83e0c174618686f96c30094591001919a1c942371be4a0880a1c27994c761827
a0722180c601363113a71874698c277986298d66809e4b03e7709a5e9e60285a
4b9fc621a24d88a13968511884a1b03207c5c0e25c9880f8a6458104a8384f0b
e200427f92e3d034268fe38119730f87d1000d884651ea6d9187c8585c1cc3f0
827b1f23f802721501b0da521d8511da5d0e0768a82b9d6503d0209122689a2c
8d0731245e0b85581c798203c80c4e94a1e9e2290ba170121d81a6712c368824
f1ea05058520d60b0ac4e9580d008010523d8cc5e83a4b906540ac529ca65186
24808281847d0e6268500a1981881a5e0ba058b83c11e3f03c4503442902079d
6731566e1a03b8820a1d20a16a2246785c0a63604082e01610c098e61f81300a
85718a05c620881141f47982f190a98778d9022354280460243b0410d019a188
6883d142040740e30222b4630f60343ec400910b02cc5d8851ae0c4740e51743
801f04e11c18c3c8f70d62242a07c1a03b86386a0781c000089118160118ed03
0114610bb1183600d8bc10c0840a0a31e83307b81e05602c7689f19010c1e0e7
08e1d8200570ca1cc158f606a2fc3e041008108200b61dc2c40601f07a2fc5b0
9f10a00c6b07d10029c7f8b41543585e83613838c270040520e8108ef07401c0
802b0d22a02e0990c034c360d11e021c228f11e02d0640271b82a45780005210
42306f0d23347489d046300208740e00741e8e90ac2846900c1c82c0398d0022
0002789b0aa01c2708c00a094648900de24805824172014460e70f40a4738e70
2a304508a81b42544c0f31b60902606511c020688b304e09c480be1662786085
a1e81b8548de0003904986b130328478fd09214076a1616e1dc6f0fe1861c825
8881bc14c288ab0181080c8cb12413c580790cc1dc270d50aa154320a91ee2a0
338470a62202f81e0a219c1701f1c632a600f218a0e01b00a0702d42e8c61981
9c620fa1560cc398a200419c6c88d06e0f832964066390668ad00c2783488411
e0b83701b08c0940e8ca11c178280496da1a81900b1e80001e0d509811018832
1a00d85a0d910e2245a8f7156158580b90902085409b1343c07386e04819c390
2c1201082707c0943683b0031b42d04b87000a1a4488461461645706807e03c5
00660e21c81e88a1f42c47c8a073009c448d71463bc3f8fb1be0381289104414
42b01101e33c550811b43a4640da0dc0083701a0be3fc2082812c1f42a86c16c
3543e02a0a0344278a31980ac7f0ea0243246b99317625c6687b1e01d07d88a1
783980a8d70140e4401621a81804f89808e2c83f05802c0a07c05608e3204584
d15a10c190be1e6058250670ce188240841182300e8c80bc2503201a0c60d828
8100ec30c2d02c0a62f0510d91c20cc150230863885b83a13a020408a514c01c
500451e42fc1b0111fa2a02e88b1ee2c8678050a23702c0950182587e0d91783
5c7406b0bc3f80c8231be1a86700f0d0360578330d61fc5d0010de3b47889713
6280628bb00818c2009716c1b87a8341080f4548b71200b05f85e13235c32497
0681fc550b80da1584d8880fc000408a31262380a08a03e3e0658e61783240c8
1018c8b82e0b51e03701483e1882f85482912c324388f10420805f81d0fa0244
786100e1a42e0730200045b0ae09110c350e91a409c0b0a30e80680d04a1b22b
0370421a20c87d0a605e0745603b08c2fc2d81895417c088991f03b0740d50b6
0cc190061c80dc050831261bd880d40422841e08c0f22b04d8e50d81d8218da0
9e3f01588106a210ce00d1142ac6e8780dc1fc3e06c1be1103d88a00a3a41a03
f0e22785409c18a034030f604616c7e83d0ac3746081d1862686f8d601a21460
8dc1161dc0082e0d63b8370761462206f8e61360f45d0cd13617c210fb1ec14c
528da1e8034608491021345d03712c26c1e0040d600c488970b22443103f1222
2c2604b0fe1c4150681f82d40ec8d07416c6405f11e2f47b0181d00180289c1c
03d00d0ad1e20245083e15e05a1c8c71181ec7f8bb1040f45005b10c12c21002
0482434703705025c1e8f20ec2d4700ac0080f0304bbe341001609803a0b4698
4c14c060658c00c01143f0e01ba294330f41a43801188912a0902f8210b02c03
109a04607c3a05e1261d47b0500a83ac1f8720be1e81b8561e80a45b04a0ae05
c4d0430941205508509a0bc170181303fc250eb1aa2c80f0c413c3584f8ef172
0681a0a302a270080321063c0290f906c3c06f0021f21187c8795d229c6a89a0
78310610ba1623946824d1d83783b8d50da110080c218830c480f41e40b80904
caca0a413882168270360600c01c20a800c15a0b41f81ae0400a215818803016
a1ca0ce1761240581be1420a41320dc08616a03c1a80441241300d216e096130
1f803c022e281021ba1f201c08a0521621661ee0e40e21381ea0de10a0101b80
1c0f012816a0660340ae1bc0600a617c1740041560520300a212a0840c804c0f
e0421200d41340441800440d21021700d801617400c0720921441dce9208a034
1cc1160fe1fc1ce0ac0b201a0c414a05213a1600fe0d0f341380a21dc00e1620
7e1580b40fa188f781261101aa0e61cc1d00961aabf81ae12e0fa08406e0fa1f
00cc03a0540eaca202e08203408009e01e0640521e018e10010a0c402a1b802c
0a815801c0b60f60bc1c80ec0141ba02a1be1e009c1b21961a81260886160aa0
cc10636804817e0d60dc1aa0f01381e21386341401100e411a00e0d80f20540f
e0fe1420ea0fe16812212c1521b004c1081200da03c08c0960901121ca1761d8
1e006613614a08407e0980c81041260bc0bc0660681bc0c60fe0ae0c41fc0521
c61aa0a407015600615e0c20ce1c81ee0620ee1501663f410c1e81281c408a1d
612c08e10e0901721981b00a614c08a0f419614f0e610402e0b4084168116096
8c418002011802a08819e1141421ca1d00a20b61b415a0c809a1641c20ae1a20
001e40c806e1881ec15e0385960aa10a13e13e06e17c05a02410e1ea06c09a02
e12a0f01640b80c80d01e008a0b61bc08a17c0920fe0e600404c1dc10614a070
16407a0ba8720c41280c214416015c1dc0581260340201bc1560340c41ae0020
a605a0c201202819604c0ae0cc1780220421b0de40f200e0ba08208e1de0b89d
61ea19405a0901601ba1081c114c1041e01760041ae1361e21141ac10a0fc138
04a01c0720be0540961661b406a19008a0140da0001bc18a0f813211c0a21f40
c01a2e0e00e13803202e14005202e1b81b01061c40ec1e81a20ba17411a0c408
e16c0160f80220b01c60ee0ca0e40d60400cc0de0e40da0c20e80400c80ca0cc
0d22aa0e80d20de0dc0e60400e80e40c20ec0ca0d80400ee0d20e80d13d20d00
cb3bd3b80c33ea0ca0f33bc8de0c60e40d20c40ca05d3e13a93ad3b13b53b93f
d3c33c73cb3cf3d33d73db3df3e33e73f73f00e93f53e73f93fc0e7401405409
40d3ab3af3b33b73bb3bf41b3e541f3d13d53d93dd3e13e53e94374314353ed3
fb3bf43d40340740b3a744741344d4193c54553cd45942545f42b4653ed4693f
746f3ff4754422020a656e6473747265616d0a656e646f626a0a352030206f62
6a0a3c3c202f4c656e67746820393735202f46696c746572202f4c5a57446563
6f6465202f4465636f64655061726d73203c3c202f4561726c794368616e6765
2030203e3e203e3e0a73747265616d0a802c17aa474024aa4c75839a66c3c1a0
e0aa10a757e8a7b104c6784fb7122941e268923f7ead4a6694028df899773fd1
cb96a0dd20a760bed847c52985ae9a72361e0781eb4dba2d2f0c424bd219b8d6
27292313e2a1c2fd0cdb40b6c16e87d1f9deaa633f484ec2103d447d4d0f0647
81400cb44e4833880984e258129e6c159a0a6768c4c6fe5f18980c92239ca489
153b5d670143e900660fb7550d97c955a6491f20c948f3b845d4f02188140e51
d3cd48a842974ea7e1d3a92ec83c3401ec723a513632161f1627947ae07cd767
13c361a0eb2c9e321228c0e7b2b1b4acca0930158393e3a830b30d15c7c3e172
f02c0b6a818d23f72018187f3f365b63e3a860eac633315720749bc006233f0b
04eb525ad452e569979842d438f528e802c150a09f238862ac133acf61b40a20
43e054da34c15294b63783d0c4bc0f86f178ba3fc07274c41106f094762684d2
c8090686c3fc181006b01030238283c01a380ea394e7238501d4c0110fd3806a
2800102c9c24006100011a83f2a40b320102247e0a47d100b7124553f0c00f01
b0fc16134b705835260e104ce71a44903c5114c86284ba040c51701a0702e330
67040150bc9f2fce53d094048cd3d47a28c281cc31070ad354531385b080fd04
4210d85e37851338010b4c30dcda23cc93301222cd60d8920e8ed19051288cb1
2c5e349f92b4c12f8cd284e73fc7d174993dcca32c25374ff1a0b21ac91358d4
1241f07cf20e82a32858024942801b0c4da0ecb013c1014c4b120a1320f90e8c
41bc7c090be274ea150da1d0042523215c133e0b005415050852c05a304bc0f0
501d02b208f8154fe38c981d43f3cc25338263446f3f8261200a30cb429c000d
4d51803831c6f18ca43ec4b0e02e3a0ed37c601b41419cd60cc0f14064190c62
88060b4843248b3d0850dc01164432e0df3b881250f52dc1419814180742fc7c
104061e80a048273741e1b8f81d44e024ec2b8cc2c0120d0970142303500323e
09673258157072190c1c6467d301427235af5d0a0700acc43c5901568cf32be1
161b4ab90d6fb4f04c6ef9070dcfead6609918d8029505a446d050805965239f
e7f709fc20384f2d094f95291090cb14a4160a60bbf08288019a93c58699edb8
7e172119a3f5114814d94ba7984623b9962220331bce46d309d0406432998d26
e349d0d26f371cc407439184ec6536080ef76345f0d065b85b8c387329e6e065
3998ce469311945d83b39aed36bb6dbee373baddef37bbedff0383c2e371474c
61d3118fb8e4b2996cc59ad16ab65bb21a1bb5e2f57cbf6030584d7eacc98bc6
ec72393cae5f33b8ceeef4174df69383a7e26ab5f89e46b79590d9f3b310100a
656e6473747265616d0a656e646f626a0a362030206f626a0a3c3c202f4c656e
677468203339202f46696c746572202f415343494938354465636f6465203e3e
0a73747265616d0a3c7e7a3575552d42380a204e38524d7338572d217a21210d
0a092121222b4556252b43623e7e3e0a656e6473747265616d0a656e646f626a
0a372030206f626a0a3c3c202f4c656e6774682039202f46696c746572202f41
3835203e3e0a73747265616d0a3065744f4132237e3e0a656e6473747265616d
0a656e646f626a0a382030206f626a0a3c3c202f4c656e6774682039202f4669
6c746572205b2f415343494938354465636f64655d203e3e0a73747265616d0a
3065744f413229597e0a656e6473747265616d0a656e646f626a0a392030206f
626a0a3c3c202f4c656e677468203233202f46696c746572202f415343494948
65784465636f6465203e3e0a73747265616d0a34382036350a36633643203666
20373e69676e6f7265640a656e6473747265616d0a656e646f626a0a31302030
206f626a0a3c3c202f4c656e67746820313437202f46696c746572202f52756e
4c656e6774684465636f6465203e3e0a73747265616d0a02616263fd5a7f0001
02030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f2021
22232425262728292a2b2c2d2e2f303132333435363738393a3b3c3d3e3f4041
42434445464748494a4b4c4d4e4f505152535455565758595a5b5c5d5e5f6061
62636465666768696a6b6c6d6e6f707172737475767778797a7b7c7d7e7f8151
0021ff788061667465720a656e6473747265616d0a656e646f626a0a31312030
206f626a0a3c3c202f4c656e677468203636202f46696c746572205b2f415343
494938354465636f6465202f466c6174654465636f64655d202f4465636f6465
5061726d73205b6e756c6c203c3c202f507265646963746f72203135202f436f
6c6f72732033202f42697473506572436f6d706f6e656e742038202f436f6c75
6d6e732034203e3e5d203e3e0a73747265616d0a476172384f4c752749624642
35553a4d3c66634e4e305b45214d6f2c4f592c6e61543c3e325a48643633446c
743167233830452b4d695536695b336d6a7137677e3e0a656e6473747265616d
0a656e646f626a0a31322030206f626a0a3c3c202f4c656e677468203136202f
46696c746572202f4c5a57202f4465636f64655061726d73203c3c202f507265
646963746f72203132202f42697473506572436f6d706f6e656e742031202f43
6f6c756d6e73203130203e3e203e3e0a73747265616d0a800054a9b011690003
41080087d404040a656e6473747265616d0a656e646f626a0a31332030206f62
6a0a3c3c202f4c656e677468203232202f46696c746572202f466c202f446563
6f64655061726d73203c3c202f507265646963746f72203130202f4269747350
6572436f6d706f6e656e74203136202f436f6c756d6e732033203e3e203e3e0a
73747265616d0a789c636450f50202166e30601654d60602001bc202780a656e
6473747265616d0a656e646f626a0a31342030206f626a0a3c3c202f4c656e67
7468203138202f46696c746572202f466c6174654465636f6465202f4465636f
64655061726d73203c3c202f507265646963746f722032202f436f6c6f727320
33202f436f6c756d6e732035203e3e203e3e0a73747265616d0a789c6360e7d3
4402bc22d2c85c003b7b042a0a656e6473747265616d0a656e646f626a0a3135
2030206f626a0a3c3c202f54797065202f584f626a656374202f537562747970
65202f496d616765202f57696474682031202f4865696768742031202f4c656e
677468203235202f46696c746572202f4443544465636f6465203e3e0a737472
65616d0affd8ffe0206e6f74207265616c6c792061204a50454720ffd90a656e
6473747265616d0a656e646f626a0a31362030206f626a0a3c3c202f4c656e67
7468203531202f46696c746572205b2f414878202f4443545d203e3e0a737472
65616d0a46464438464645303230364536463734323037323635363136433643
373932303631323034413530343534373230464644393e0a656e647374726561
6d0a656e646f626a0a31372030206f626a0a3c3c202f4c656e67746820323720
2f46696c746572205b2f466c6174654465636f6465202f4a50584465636f6465
202f415343494938354465636f64655d203e3e0a73747265616d0a789cb3a9b3
304f0e0d7289cdd451724dcab730a8b303003a1105c60a656e6473747265616d
0a656e646f626a0a31382030206f626a0a3c3c202f4c656e6774682034202f46
696c746572202f466f6f4465636f6465203e3e0a73747265616d0a646174610a
656e6473747265616d0a656e646f626a0a31392030206f626a0a3c3c202f4c65
6e6774682039202f46696c746572202f466c6174654465636f6465203e3e0a73
747265616d0a6e6f74207a6c6962210a656e6473747265616d0a656e646f626a
0a32302030206f626a0a3c3c202f4c656e6774682035202f46696c746572202f
415343494938354465636f6465203e3e0a73747265616d0a6162637b7e0a656e
6473747265616d0a656e646f626a0a32312030206f626a0a3c3c202f4c656e67
746820323220302052202f46696c74657220323320302052203e3e0a73747265
616d0a3737363537322036623e0a656e6473747265616d0a656e646f626a0a32
322030206f626a0a31300a656e646f626a0a32332030206f626a0a2f41534349
494865784465636f64650a656e646f626a0a32342030206f626a0a3c3c202f4c
656e6774682030203e3e0a73747265616d0a0a656e6473747265616d0a656e64
6f626a0a32352030206f626a0a3c3c202f4c656e677468203436203e3e0a7374
7265616d0a746869732064617461207361797320656e6473747265616d0a656e
646f626a0a6265666f726520697420656e64730a656e6473747265616d0a656e
646f626a0a787265660a302032360a3030303030303030303020363535333520
66200a30303030303030303039203030303030206e200a303030303030303035
38203030303030206e200a30303030303030313130203030303030206e200a30
303030303030323439203030303030206e200a30303030303033353436203030
303030206e200a30303030303034363235203030303030206e200a3030303030
3034373337203030303030206e200a3030303030303438303820303030303020
6e200a30303030303034383931203030303030206e200a303030303030343938
38203030303030206e200a30303030303035323132203030303030206e200a30
303030303035343438203030303030206e200a30303030303035353933203030
303030206e200a30303030303035373433203030303030206e200a3030303030
3035383836203030303030206e200a3030303030303630333120303030303020
6e200a30303030303036313533203030303030206e200a303030303030363238
30203030303030206e200a30303030303036333533203030303030206e200a30
303030303036343333203030303030206e200a30303030303036353131203030
303030206e200a30303030303036353931203030303030206e200a3030303030
3036363130203030303030206e200a3030303030303636343220303030303020
6e200a30303030303036363932203030303030206e200a747261696c65720a3c
3c202f53697a65203236202f526f6f74203120302052203e3e0a737461727478
7265660a363738390a2525454f460a
```

### Vector `xref-stream`

Two revisions, both indexed by cross-reference STREAMS. The older one (object 5) has `/W [0 2 0]` - no type field, so every entry is type 1, and no generation field - and `/Index [1 5]`, and is ASCIIHex-encoded. The newer one (object 10) has `/W [1 2 1]`, three `/Index` ranges, Flate with PNG predictor 12, a `/Prev`, and replaces object 2 by a compressed object: object stream 6 holds the new page tree node, a second page and its font. The cross-reference entry of object 8 gives the WRONG index within the object stream (0, where the object is third): the pair that names 8 is used. The entry of object 11 has the undefined type 3 and is ignored. Object 5, the old cross-reference stream, is still an object of the file and is listed.

* input: 1103 bytes, sha256 `0a69cce2c5c1423406c66d18ec2ca57dc32293d32ef1cd74386e54ac79cf9654`
* output form: the text listing of section 14: `pdf <version> revisions <n> objects <n>`, a `trailer` line, `info` lines, one `object` line per in-use object, then for each page a `page` line and its `font` lines; UTF-8, LF line ends
* output: 1862 bytes, sha256 `e242470aec0855ddf7595fd4ce39745192cac09cc7638dbc159e880565e6f55c`
* checked when this document was built: the reference decoder's output equals the bytes the input was encoded from

The output, for orientation:

```
pdf 1.5 revisions 2 objects 10
trailer root 1 0 info - id -
object 1 0 << /Type /Catalog /Pages 2 0 R >>
object 2 0 << /Type /Pages /Kids [ 3 0 R 7 0 R ] /Count 2 >>
object 3 0 << /Type /Page /Parent 2 0 R /MediaBox [ 0 0 100 100 ] /Contents 4 0 R >>
object 4 0 << /Length 43 >> stream raw 43 decoded 43 sha256 f9320318993c56cf1d313ec7e48392811a6c75d820f8fc1babcce197136e7c81
object 5 0 << /Type /XRef /Size 6 /W [ 0 2 0 ] /Index [ 1 5 ] /Root 1 0 R /Filter /ASCIIHexDecode /Length 21 >> stream raw 21 decoded 10 sha256 fffc7a5d8c84e1f6a8ab5cd24e908beed3c27fb0cab3b9fc56a4964bd3d395a9
object 6 0 << /Type /ObjStm /N 3 /First 15 /Filter /FlateDecode /Length 158 >> stream raw 158 decoded 226 sha256 44e036403b1722640ce0c994a5778c8ac622ce02d6a2ffb3e441c9825ff023b1
object 7 0 << /Type /Page /Parent 2 0 R /MediaBox [ 0 0 100 100 ] /Resources << /Font << /F1 8 0 R >> >> /Contents 9 0 R >>
object 8 0 << /Type /Font /Subtype /Type1 /BaseFont /Courier >>
object 9 0 << /Length 45 /Filter /FlateDecode >> stream raw 45 decoded 40 sha256 da2460ec593b210f212413851338c35eb37be29e78ee51248af833101c177917
object 10 0 << /Type /XRef /Size 12 /W [ 1 2 1 ] /Index [ 0 1 2 1 6 6 ] /Root 1 0 R /Prev 301 /Filter /FlateDecode /DecodeParms << /Predictor 12 /Columns 4 >> /Length 45 >> stream raw 45 decoded 32 sh ...
page 1 object 3 0 mediabox [ 0 0 100 100 ] rotate 0 contents 1 bytes 43 sha256 f9320318993c56cf1d313ec7e48392811a6c75d820f8fc1babcce197136e7c81 operators 5 tokens 08bc79104f466aa2a475cf40dd7602e8a182a667d7e4b3f40555e8c119abfc8b
page 2 object 7 0 mediabox [ 0 0 100 100 ] rotate 0 contents 1 bytes 40 sha256 da2460ec593b210f212413851338c35eb37be29e78ee51248af833101c177917 operators 5 tokens a2552cd088349b4f8e2ab59b82a3885c1519f83f54aa38e347fb16aa8b3e02ec
font 2 F1 Type1 Courier program none -
```

```hex xref-stream
255044462d312e350a25e2e3cfd30a312030206f626a0a3c3c202f5479706520
2f436174616c6f67202f5061676573203220302052203e3e0a656e646f626a0a
322030206f626a0a3c3c202f54797065202f5061676573202f4b696473205b33
203020525d202f436f756e742031203e3e0a656e646f626a0a332030206f626a
0a3c3c202f54797065202f50616765202f506172656e74203220302052202f4d
65646961426f78205b30203020313030203130305d202f436f6e74656e747320
3420302052203e3e0a656e646f626a0a342030206f626a0a3c3c202f4c656e67
7468203433203e3e0a73747265616d0a4254202f463120392054662031302031
3020546420286669727374207265766973696f6e2920546a2045540a656e6473
747265616d0a656e646f626a0a352030206f626a0a3c3c202f54797065202f58
526566202f53697a652036202f57205b30203220305d202f496e646578205b31
20355d202f526f6f74203120302052202f46696c746572202f41534349494865
784465636f6465202f4c656e677468203231203e3e0a73747265616d0a303030
66303034303030373930306430303132643e0a656e6473747265616d0a656e64
6f626a0a7374617274787265660a3330310a2525454f460a362030206f626a0a
3c3c202f54797065202f4f626a53746d202f4e2033202f466972737420313520
2f46696c746572202f466c6174654465636f6465202f4c656e67746820313538
203e3e0a73747265616d0a789c558ec10ac2301044ef7ec5fcc12655b1859243
052f2248f5563c44bb482e8d2429e8dfbb891e149225999d37bb15143658d5a8
a1d70dda16747e3d1874b4778ea0bd1b2386a5b87af149bd80b67e9e122a18b3
f8f7e71ab8f4b29f0e3c3adbf92706258256e54a40cfd1cfe126f999df7921ca
43cb161934261f993325498b68beeacfb802d169bea6f2cda2067536f2a7233b
06c741a0370d463dd00a656e6473747265616d0a656e646f626a0a392030206f
626a0a3c3c202f4c656e677468203435202f46696c746572202f466c61746544
65636f6465203e3e0a73747265616d0a789c730a51d0773354b0540849533034
00a19014058de2d4e4fcbc148582c4f4544d85902c05d71000c94a0aab0a656e
6473747265616d0a656e646f626a0a31302030206f626a0a3c3c202f54797065
202f58526566202f53697a65203132202f57205b31203220315d202f496e6465
78205b30203120322031203620365d202f526f6f74203120302052202f507265
7620333031202f46696c746572202f466c6174654465636f6465202f4465636f
64655061726d73203c3c202f507265646963746f72203132202f436f6c756d6e
732034203e3e202f4c656e677468203435203e3e0a73747265616d0a789c1dc8
410900201405c17d7bd036a6339c3904e3c8179ce30894d26265636ac47fe541
32d1bbfa03a46009220a656e6473747265616d0a656e646f626a0a7374617274
787265660a3834370a2525454f460a
```

### Vector `hybrid`

A hybrid file with an incremental update: three cross-reference TABLES linked by `/Prev`. In the oldest, objects 4 and 5 are free - that is what a reader which knows only tables sees. The middle one lists only object 8 and its trailer has `/XRefStm`, naming cross-reference stream 8, which says where 4 and 5 really are: in object stream 6 (which is not compressed). The newest table has one entry: object 5 is free. Reading newest first: object 5 is free (found first in the newest table); object 4 is found in the `/XRefStm` stream, which is read BEFORE following `/Prev`, so the free entry of the oldest table never counts. `revisions` is 3: the `/XRefStm` stream is not a revision.

* input: 1037 bytes, sha256 `a84c5e90f4bd3b048bdb0eb49d91a9aaa49607836a6ddc872f527ef5cab95ea2`
* output form: the text listing of section 14: `pdf <version> revisions <n> objects <n>`, a `trailer` line, `info` lines, one `object` line per in-use object, then for each page a `page` line and its `font` lines; UTF-8, LF line ends
* output: 1083 bytes, sha256 `912ea3b23fb01b813ef15f2ec6a2b7b56d06b7b84afc444cac776b8de045ba2c`
* checked when this document was built: the reference decoder's output equals the bytes the input was encoded from

The output, for orientation:

```
pdf 1.5 revisions 3 objects 7
trailer root 1 0 info - id -
object 1 0 << /Type /Catalog /Pages 2 0 R >>
object 2 0 << /Type /Pages /Kids [ 3 0 R ] /Count 1 >>
object 3 0 << /Type /Page /Parent 2 0 R /MediaBox [ 0 0 50 50 ] /Resources << /Font << /F1 4 0 R >> /ExtGState << /GS 5 0 R >> >> /Contents 7 0 R >>
object 4 0 << /Type /Font /Subtype /Type1 /BaseFont /Symbol >>
object 6 0 << /Type /ObjStm /N 2 /First 9 /Length 89 >> stream raw 89 decoded 89 sha256 6402c08e63ed2b99ff308eb06b5bb6a0e1fa837a0fe6045a9754d757bdcf3de3
object 7 0 << /Length 33 >> stream raw 33 decoded 33 sha256 2bb3a42d28429002287171e7d9fd01703f55f7739a8dc50300a9b9db5f3f4b12
object 8 0 << /Type /XRef /Size 9 /W [ 1 1 1 ] /Index [ 4 2 ] /Length 6 >> stream raw 6 decoded 6 sha256 a527469cf28445bf9f88342c06f1ee512731f5b1450932f45d53f29cdcfcb482
page 1 object 3 0 mediabox [ 0 0 50 50 ] rotate 0 contents 1 bytes 33 sha256 2bb3a42d28429002287171e7d9fd01703f55f7739a8dc50300a9b9db5f3f4b12 operators 5 tokens 255e7e9ddee2563bb50aaee937bd0a0cbd4b9142f9a47d05dcd413489f6f40a7
font 1 F1 Type1 Symbol program none -
```

```hex hybrid
255044462d312e350a312030206f626a0a3c3c202f54797065202f436174616c
6f67202f5061676573203220302052203e3e0a656e646f626a0a322030206f62
6a0a3c3c202f54797065202f5061676573202f4b696473205b33203020525d20
2f436f756e742031203e3e0a656e646f626a0a332030206f626a0a3c3c202f54
797065202f50616765202f506172656e74203220302052202f4d65646961426f
78205b3020302035302035305d202f5265736f7572636573203c3c202f466f6e
74203c3c202f4631203420302052203e3e202f457874475374617465203c3c20
2f4753203520302052203e3e203e3e202f436f6e74656e747320372030205220
3e3e0a656e646f626a0a362030206f626a0a3c3c202f54797065202f4f626a53
746d202f4e2032202f46697273742039202f4c656e677468203839203e3e0a73
747265616d0a34203020352035320a3c3c202f54797065202f466f6e74202f53
756274797065202f5479706531202f42617365466f6e74202f53796d626f6c20
3e3e203c3c202f54797065202f457874475374617465202f4c572032203e3e0a
656e6473747265616d0a656e646f626a0a372030206f626a0a3c3c202f4c656e
677468203333203e3e0a73747265616d0a2f4753206773204254202f46312039
20546620286879627269642920546a2045540a656e6473747265616d0a656e64
6f626a0a382030206f626a0a3c3c202f54797065202f58526566202f53697a65
2039202f57205b31203120315d202f496e646578205b3420325d202f4c656e67
74682036203e3e0a73747265616d0a0206000206010a656e6473747265616d0a
656e646f626a0a787265660a3020380a30303030303030303030203635353335
2066200a30303030303030303039203030303030206e200a3030303030303030
3538203030303030206e200a30303030303030313135203030303030206e200a
303030303030303030302030303030302066200a303030303030303030302030
303030302066200a30303030303030323636203030303030206e200a30303030
303030343333203030303030206e200a747261696c65720a3c3c202f53697a65
2038202f526f6f74203120302052203e3e0a7374617274787265660a3631350a
2525454f460a787265660a3820310a3030303030303035313620303030303020
6e200a747261696c65720a3c3c202f53697a652039202f526f6f742031203020
52202f5852656653746d20353136202f5072657620363135203e3e0a73746172
74787265660a3833380a2525454f460a787265660a3520310a30303030303030
3030302030303030312066200a747261696c65720a3c3c202f53697a65203920
2f526f6f74203120302052202f5072657620383338203e3e0a73746172747872
65660a3934340a2525454f460a
```

### Vector `incremental`

Three revisions, each appended to the one before, all with cross-reference tables. Revision 2 replaces the content stream (object 4) and the information dictionary (object 5); its table has one subsection of two entries. Revision 3 replaces the page tree node, adds a page (objects 7, 8) and deletes object 6 with a free entry; its table has three subsections. The newest definition of each object wins; the old bytes are still in the file.

* input: 1309 bytes, sha256 `ccddb9090eb070bb57c2d736312e52d41b74db6e0b2c463a9e429a49e71b2c97`
* output form: the text listing of section 14: `pdf <version> revisions <n> objects <n>`, a `trailer` line, `info` lines, one `object` line per in-use object, then for each page a `page` line and its `font` lines; UTF-8, LF line ends
* output: 1103 bytes, sha256 `d825d51785bb03ac2ef82bc9e50f062e9212afc77f9912de0e111db973579388`
* checked when this document was built: the reference decoder's output equals the bytes the input was encoded from

The output, for orientation:

```
pdf 1.4 revisions 3 objects 7
trailer root 1 0 info 5 0 id a1b2
info Title Final
object 1 0 << /Type /Catalog /Pages 2 0 R >>
object 2 0 << /Type /Pages /Kids [ 3 0 R 7 0 R ] /Count 2 /MediaBox [ 0 0 10 10 ] >>
object 3 0 << /Type /Page /Parent 2 0 R /Contents 4 0 R >>
object 4 0 << /Length 27 /Filter /FlateDecode >> stream raw 27 decoded 19 sha256 355f5fab16dbacc2e239d096fbd591dfed6e55df179b0bc86a08d7f5e1cffdb8
object 5 0 << /Title <46696e616c> >>
object 7 0 << /Type /Page /Parent 2 0 R /Contents 8 0 R /Rotate 270 >>
object 8 0 << /Length 12 >> stream raw 12 decoded 12 sha256 cf322faf8d2f8086dfb93c8b39477af6aaa0155ab1318df2ff8ff43ae76787e9
page 1 object 3 0 mediabox [ 0 0 10 10 ] rotate 0 contents 1 bytes 19 sha256 355f5fab16dbacc2e239d096fbd591dfed6e55df179b0bc86a08d7f5e1cffdb8 operators 3 tokens 4e9766518b8639bbc01db13e79735b6f2e9fd0aece6e752b19d9878367ecf01b
page 2 object 7 0 mediabox [ 0 0 10 10 ] rotate 270 contents 1 bytes 12 sha256 cf322faf8d2f8086dfb93c8b39477af6aaa0155ab1318df2ff8ff43ae76787e9 operators 2 tokens f2aa773899a7156aef39b198fbc86cef846798598cc6da898e73247c5a8aaabb
```

```hex incremental
255044462d312e340a312030206f626a0a3c3c202f54797065202f436174616c
6f67202f5061676573203220302052203e3e0a656e646f626a0a322030206f62
6a0a3c3c202f54797065202f5061676573202f4b696473205b33203020525d20
2f436f756e742031202f4d65646961426f78205b3020302031302031305d203e
3e0a656e646f626a0a332030206f626a0a3c3c202f54797065202f5061676520
2f506172656e74203220302052202f436f6e74656e7473203420302052203e3e
0a656e646f626a0a342030206f626a0a3c3c202f4c656e677468203139203e3e
0a73747265616d0a425420286f6c6420746578742920546a2045540a656e6473
747265616d0a656e646f626a0a352030206f626a0a3c3c202f5469746c652028
447261667429203e3e0a656e646f626a0a362030206f626a0a2874686973206f
626a6563742069732064656c6574656420696e207265766973696f6e2033290a
656e646f626a0a787265660a3020370a30303030303030303030203635353335
2066200a30303030303030303039203030303030206e200a3030303030303030
3538203030303030206e200a30303030303030313337203030303030206e200a
30303030303030323030203030303030206e200a303030303030303236392030
30303030206e200a30303030303030333035203030303030206e200a74726169
6c65720a3c3c202f53697a652037202f526f6f74203120302052202f496e666f
203520302052202f4944205b3c613162323e203c613162323e5d203e3e0a7374
617274787265660a3335390a2525454f460a342030206f626a0a3c3c202f4c65
6e677468203237202f46696c746572202f466c6174654465636f6465203e3e0a
73747265616d0a789c730a51d0c84b2d572849ad28d15408c952700d01003a33
05ce0a656e6473747265616d0a656e646f626a0a352030206f626a0a3c3c202f
5469746c65202846696e616c29203e3e0a656e646f626a0a787265660a342032
0a30303030303030353934203030303030206e200a3030303030303036393220
3030303030206e200a747261696c65720a3c3c202f53697a652037202f526f6f
74203120302052202f496e666f203520302052202f4944205b3c613162323e20
3c633364343e5d202f5072657620333539203e3e0a7374617274787265660a37
32380a2525454f460a322030206f626a0a3c3c202f54797065202f5061676573
202f4b696473205b33203020522037203020525d202f436f756e742032202f4d
65646961426f78205b3020302031302031305d203e3e0a656e646f626a0a3720
30206f626a0a3c3c202f54797065202f50616765202f506172656e7420322030
2052202f436f6e74656e7473203820302052202f526f7461746520323730203e
3e0a656e646f626a0a382030206f626a0a3c3c202f4c656e677468203132203e
3e0a73747265616d0a3020302035203520726520660a656e6473747265616d0a
656e646f626a0a787265660a3020310a30303030303030303036203635353335
2066200a3220310a30303030303030383733203030303030206e200a3620330a
303030303030303030302030303030312066200a303030303030303935382030
30303030206e200a30303030303031303333203030303030206e200a74726169
6c65720a3c3c202f53697a652039202f526f6f74203120302052202f496e666f
203520302052202f4944205b3c613162323e203c653566363e5d202f50726576
20373238203e3e0a7374617274787265660a313039350a2525454f460a
```

### Vector `pages`

The page tree and fonts. The root node gives `/MediaBox` (through a reference), `/Rotate 90` and `/Resources` for all pages. Its first child (object 3) overrides `/Rotate`. Page 1 (object 4) inherits everything; its `/Contents` is an array of two streams - split between `12` and `Tf`, joined with one line feed. Page 2 (object 5) has its own box (written `100.0 +50`), rotation and resources and no content at all. Page 3 (object 7), under the second child, inherits the root's values. Fonts: a standard font (no program), a TrueType font with `/FontFile2`, a Type 1 font with `/FontFile`, a composite font whose program is found through `/DescendantFonts`, a Type 3 font (no `/BaseFont`, no program), a font with `/FontFile3` and a space in its name; the entry `/Bad 5` is not a font dictionary and is skipped.

* input: 3267 bytes, sha256 `40dbc0b932f8178ad193abc7c5b92515a60b3c57199d30a197681827d203f8f9`
* output form: the text listing of section 14: `pdf <version> revisions <n> objects <n>`, a `trailer` line, `info` lines, one `object` line per in-use object, then for each page a `page` line and its `font` lines; UTF-8, LF line ends
* output: 3861 bytes, sha256 `ba0dbcdbb219add6b44b69bb0eb5ba960519473c4d318d380f904861001ef9ea`
* checked when this document was built: the reference decoder's output equals the bytes the input was encoded from

The output, for orientation:

```
pdf 1.6 revisions 1 objects 27
trailer root 1 0 info - id -
object 1 0 << /Type /Catalog /Pages 2 0 R >>
object 2 0 << /Type /Pages /Kids [ 3 0 R 6 0 R ] /Count 3 /MediaBox 20 0 R /Rotate 90 /Resources 21 0 R >>
object 3 0 << /Type /Pages /Parent 2 0 R /Kids [ 4 0 R 5 0 R ] /Count 2 /Rotate 180 >>
object 4 0 << /Type /Page /Parent 3 0 R /Contents [ 10 0 R 11 0 R ] >>
object 5 0 << /Type /Page /Parent 3 0 R /MediaBox [ 0 0 100 50 ] /Rotate 0 /Resources << /Font << /T0 25 0 R /T3 26 0 R /CFF 27 0 R >> >> >>
object 6 0 << /Type /Pages /Parent 2 0 R /Kids [ 7 0 R ] /Count 1 >>
object 7 0 << /Type /Page /Parent 6 0 R /Contents 12 0 R >>
object 10 0 << /Length 28 >> stream raw 28 decoded 28 sha256 8738dde2e3028409f5f28245cd57bcdc905254adfaaf03ab7cb75e3918fec11a
object 11 0 << /Length 22 /Filter /FlateDecode >> stream raw 22 decoded 14 sha256 61ce6cb4af9274ac69bed5d945df8b874c19fd3e01fe9ceb702879cf5e8e1ed9
object 12 0 << /Length 14 >> stream raw 14 decoded 14 sha256 596ce83fdfa544a0f29f4baacba5300846a11cde7c2e0baf7c3aa3c6a6174a40
object 20 0 [ 0 0 300 400 ]
object 21 0 << /Font << /F1 22 0 R /F2 23 0 R /Bad 5 /F3 24 0 R >> >>
object 22 0 << /Type /Font /Subtype /Type1 /BaseFont /Times-Roman >>
object 23 0 << /Type /Font /Subtype /TrueType /BaseFont /ABCDEF+Arial /FontDescriptor 30 0 R >>
object 24 0 << /Type /Font /Subtype /Type1 /BaseFont /MyType1 /FontDescriptor 32 0 R >>
object 25 0 << /Type /Font /Subtype /Type0 /BaseFont /GHIJKL+Noto-Identity-H /Encoding /Identity-H /DescendantFonts [ 34 0 R ] >>
object 26 0 << /Type /Font /Subtype /Type3 /FontBBox [ 0 0 1 1 ] /FontMatrix [ 1 0 0 1 0 0 ] /CharProcs << >> /Encoding << /Differences [ ] >> >>
object 27 0 << /Type /Font /Subtype /Type1 /BaseFont /Cff%20Font /FontDescriptor 37 0 R >>
object 30 0 << /Type /FontDescriptor /FontName /ABCDEF+Arial /FontFile2 31 0 R >>
object 31 0 << /Length 37 /Length1 37 >> stream raw 37 decoded 37 sha256 4b940a97d1baed64064837cab487b7fba6d6b96c2a8bfff8923b95f31d5c0602
object 32 0 << /Type /FontDescriptor /FontName /MyType1 /FontFile 33 0 R >>
object 33 0 << /Length 35 /Length1 35 /Length2 0 /Length3 0 >> stream raw 35 decoded 35 sha256 470dbfbca16d127caf89435c1ef2bad747077ce2e96b726df075eb0b55f0f395
object 34 0 << /Type /Font /Subtype /CIDFontType2 /BaseFont /GHIJKL+Noto /FontDescriptor 35 0 R >>
object 35 0 << /Type /FontDescriptor /FontName /GHIJKL+Noto /FontFile2 36 0 R >>
object 36 0 << /Length 37 >> stream raw 37 decoded 37 sha256 4b940a97d1baed64064837cab487b7fba6d6b96c2a8bfff8923b95f31d5c0602
object 37 0 << /Type /FontDescriptor /FontName /Cff%20Font /FontFile3 38 0 R >>
object 38 0 << /Length 18 /Subtype /Type1C >> stream raw 18 decoded 18 sha256 d7373102eccd14da426667aed1119f7caa71fe322df0f8a63d96a4938ca11fef
page 1 object 4 0 mediabox [ 0 0 300 400 ] rotate 180 contents 2 bytes 43 sha256 50a07d4b090b3b3352926f34a735c499293cd1f3152095b9cc95f0d8bcbec633 operators 7 tokens 3fd858fc8742c5914faf0e72c26fe853124709bf07cfd77cdbea982a5f1a5765
font 1 F1 Type1 Times-Roman program none -
font 1 F2 TrueType ABCDEF+Arial program FontFile2 31 0
font 1 F3 Type1 MyType1 program FontFile 33 0
page 2 object 5 0 mediabox [ 0 0 100 50 ] rotate 0 contents 0 bytes 0 sha256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 operators 0 tokens e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
font 2 T0 Type0 GHIJKL+Noto-Identity-H program FontFile2 36 0
font 2 T3 Type3 - program none -
font 2 CFF Type1 Cff%20Font program FontFile3 38 0
page 3 object 7 0 mediabox [ 0 0 300 400 ] rotate 90 contents 1 bytes 14 sha256 596ce83fdfa544a0f29f4baacba5300846a11cde7c2e0baf7c3aa3c6a6174a40 operators 2 tokens 7f1ca5695251f932e88bad381d111cbb3ad9b8a2947c980b6ce8e87bb6e3d210
font 3 F1 Type1 Times-Roman program none -
font 3 F2 TrueType ABCDEF+Arial program FontFile2 31 0
font 3 F3 Type1 MyType1 program FontFile 33 0
```

```hex pages
255044462d312e360a312030206f626a0a3c3c202f54797065202f436174616c
6f67202f5061676573203220302052203e3e0a656e646f626a0a322030206f62
6a0a3c3c202f54797065202f5061676573202f4b696473205b33203020522036
203020525d202f436f756e742033202f4d65646961426f782032302030205220
2f526f74617465203930202f5265736f757263657320323120302052203e3e0a
656e646f626a0a332030206f626a0a3c3c202f54797065202f5061676573202f
506172656e74203220302052202f4b696473205b34203020522035203020525d
202f436f756e742032202f526f7461746520313830203e3e0a656e646f626a0a
342030206f626a0a3c3c202f54797065202f50616765202f506172656e742033
20302052202f436f6e74656e7473205b313020302052203131203020525d203e
3e0a656e646f626a0a352030206f626a0a3c3c202f54797065202f5061676520
2f506172656e74203320302052202f4d65646961426f78205b30203020313030
2e30202b35305d202f526f746174652030202f5265736f7572636573203c3c20
2f466f6e74203c3c202f543020323520302052202f543320323620302052202f
43464620323720302052203e3e203e3e203e3e0a656e646f626a0a362030206f
626a0a3c3c202f54797065202f5061676573202f506172656e74203220302052
202f4b696473205b37203020525d202f436f756e742031203e3e0a656e646f62
6a0a372030206f626a0a3c3c202f54797065202f50616765202f506172656e74
203620302052202f436f6e74656e747320313220302052203e3e0a656e646f62
6a0a31302030206f626a0a3c3c202f4c656e677468203238203e3e0a73747265
616d0a71203120302030203120313020313020636d204254202f46312031320a
656e6473747265616d0a656e646f626a0a31312030206f626a0a3c3c202f4c65
6e677468203232202f46696c746572202f466c6174654465636f6465203e3e0a
73747265616d0a789c0b4953d0a8d05408c952700d510804001c3603ac0a656e
6473747265616d0a656e646f626a0a31322030206f626a0a3c3c202f4c656e67
7468203134203e3e0a73747265616d0a30203020313020313020726520660a65
6e6473747265616d0a656e646f626a0a32302030206f626a0a5b302030203330
30203430305d0a656e646f626a0a32312030206f626a0a3c3c202f466f6e7420
3c3c202f463120323220302052202f463220323320302052202f426164203520
2f463320323420302052203e3e203e3e0a656e646f626a0a32322030206f626a
0a3c3c202f54797065202f466f6e74202f53756274797065202f547970653120
2f42617365466f6e74202f54696d65732d526f6d616e203e3e0a656e646f626a
0a32332030206f626a0a3c3c202f54797065202f466f6e74202f537562747970
65202f5472756554797065202f42617365466f6e74202f4142434445462b4172
69616c202f466f6e7444657363726970746f7220333020302052203e3e0a656e
646f626a0a32342030206f626a0a3c3c202f54797065202f466f6e74202f5375
6274797065202f5479706531202f42617365466f6e74202f4d79547970653120
2f466f6e7444657363726970746f7220333220302052203e3e0a656e646f626a
0a32352030206f626a0a3c3c202f54797065202f466f6e74202f537562747970
65202f5479706530202f42617365466f6e74202f4748494a4b4c2b4e6f746f2d
4964656e746974792d48202f456e636f64696e67202f4964656e746974792d48
202f44657363656e64616e74466f6e7473205b3334203020525d203e3e0a656e
646f626a0a32362030206f626a0a3c3c202f54797065202f466f6e74202f5375
6274797065202f5479706533202f466f6e7442426f78205b302030203120315d
202f466f6e744d6174726978205b31203020302031203020305d202f43686172
50726f6373203c3c203e3e202f456e636f64696e67203c3c202f446966666572
656e636573205b5d203e3e203e3e0a656e646f626a0a32372030206f626a0a3c
3c202f54797065202f466f6e74202f53756274797065202f5479706531202f42
617365466f6e74202f436666233230466f6e74202f466f6e7444657363726970
746f7220333720302052203e3e0a656e646f626a0a33302030206f626a0a3c3c
202f54797065202f466f6e7444657363726970746f72202f466f6e744e616d65
202f4142434445462b417269616c202f466f6e7446696c653220333120302052
203e3e0a656e646f626a0a33312030206f626a0a3c3c202f4c656e6774682033
37202f4c656e67746831203337203e3e0a73747265616d0a0001000020612054
727565547970652070726f6772616d20776f756c6420626520686572650a656e
6473747265616d0a656e646f626a0a33322030206f626a0a3c3c202f54797065
202f466f6e7444657363726970746f72202f466f6e744e616d65202f4d795479
706531202f466f6e7446696c6520333320302052203e3e0a656e646f626a0a33
332030206f626a0a3c3c202f4c656e677468203335202f4c656e677468312033
35202f4c656e677468322030202f4c656e677468332030203e3e0a7374726561
6d0a252150532d41646f6265466f6e742d312e30206120547970652031207072
6f6772616d0a656e6473747265616d0a656e646f626a0a33342030206f626a0a
3c3c202f54797065202f466f6e74202f53756274797065202f434944466f6e74
5479706532202f42617365466f6e74202f4748494a4b4c2b4e6f746f202f466f
6e7444657363726970746f7220333520302052203e3e0a656e646f626a0a3335
2030206f626a0a3c3c202f54797065202f466f6e7444657363726970746f7220
2f466f6e744e616d65202f4748494a4b4c2b4e6f746f202f466f6e7446696c65
3220333620302052203e3e0a656e646f626a0a33362030206f626a0a3c3c202f
4c656e677468203337203e3e0a73747265616d0a000100002061205472756554
7970652070726f6772616d20776f756c6420626520686572650a656e64737472
65616d0a656e646f626a0a33372030206f626a0a3c3c202f54797065202f466f
6e7444657363726970746f72202f466f6e744e616d65202f436666233230466f
6e74202f466f6e7446696c653320333820302052203e3e0a656e646f626a0a33
382030206f626a0a3c3c202f4c656e677468203138202f53756274797065202f
547970653143203e3e0a73747265616d0a010004012061204346462070726f67
72616d0a656e6473747265616d0a656e646f626a0a787265660a302033390a30
3030303030303030302036353533352066200a30303030303030303039203030
303030206e200a30303030303030303538203030303030206e200a3030303030
3030313637203030303030206e200a3030303030303032353620303030303020
6e200a30303030303030333239203030303030206e200a303030303030303437
35203030303030206e200a30303030303030353436203030303030206e200a30
3030303030303030302030303030302066200a30303030303030303030203030
3030302066200a30303030303030363130203030303030206e200a3030303030
3030363839203030303030206e200a3030303030303037383320303030303020
6e200a303030303030303030302030303030302066200a303030303030303030
302030303030302066200a303030303030303030302030303030302066200a30
3030303030303030302030303030302066200a30303030303030303030203030
3030302066200a303030303030303030302030303030302066200a3030303030
30303030302030303030302066200a3030303030303038343820303030303020
6e200a30303030303030383738203030303030206e200a303030303030303935
32203030303030206e200a30303030303031303235203030303030206e200a30
303030303031313235203030303030206e200a30303030303031323137203030
303030206e200a30303030303031333439203030303030206e200a3030303030
3031343934203030303030206e200a3030303030303030303020303030303020
66200a303030303030303030302030303030302066200a303030303030313538
39203030303030206e200a30303030303031363735203030303030206e200a30
303030303031373735203030303030206e200a30303030303031383535203030
303030206e200a30303030303031393735203030303030206e200a3030303030
3032303738203030303030206e200a3030303030303231363320303030303020
6e200a30303030303032323531203030303030206e200a303030303030323333
35203030303030206e200a747261696c65720a3c3c202f53697a65203339202f
526f6f74203120302052203e3e0a7374617274787265660a323432310a252545
4f460a
```

### Vector `content`

The content-stream grammar. One page whose (Flate-compressed) content has: numbers in several spellings; an array and a dictionary as operands; strings with escapes; the operators `'`, `"`, `T*`, `W*`, `f*`, `B*`, `b*`; an inline image whose data is text (the white space inside it is data; the two operands left before `BI` are dropped); a second inline image written without spaces after `BI`, whose BINARY data contains `EI` twice - once not preceded by white space, once not followed by a delimiter - before the real end; `true false null` as operands of an unknown operator; stray closing delimiters and a `{`, which are skipped; a comment; tokens with no white space between them; and three operands after the last operator, which are dropped. The decoded content is 0x209 bytes; its operator listing, whose hash the `page` line carries, is:

```
q
1 0 0 1 72.5 0 cm
/GS1 gs
[ 3 1.5 ] 0 d
BI << /W 2 /H 2 /BPC 8 /CS /G /F [ /AHx ] >> ID 10 2e9b0a9f178541c29ab5549ff06a56a417386996406d28f8b831aaba8699fc61 EI
BT
/F1 12 Tf
1 0 0 1 72 720 Tm
<48656c6c6f2028776f726c6429> Tj
[ <41> -120 <42> 15.5 <43> ] TJ
T*
<69742773> '
1 2 <71> "
ET
0 0 m
10 10 l
20 0 30 10 40 0 c
h
S
0 0 10 10 re
W*
n
f*
B*
b*
/P << /MCID 0 /Lang <656e> >> BDC
EMC
/Span BMC
EMC
/Im1 Do
1 0.5 0.25 rg
0 g
<61> Tj
[ 1 ] TJ
<41> Tj
/N gs
BI << /W 1 /H 1 /IM true >> ID 9 c24f9943370780c6ed8db0af34b3510127d82a4c856966b31dda4e0fe69289f7 EI
Q
0 0 m
1 1 l
S
0 g
1 G
2 w
0 J
0 j
true false null 1 unknownOp
5 w
```



* input: 828 bytes, sha256 `0769876f50317e89f78f242a9f892eb49f473e15a9a518e99a9e23d91c1b01dd`
* output form: the text listing of section 14: `pdf <version> revisions <n> objects <n>`, a `trailer` line, `info` lines, one `object` line per in-use object, then for each page a `page` line and its `font` lines; UTF-8, LF line ends
* output: 623 bytes, sha256 `c673d5d263613ce43b35cf191f47e2ec844a231a44bf20c303f488c788ae1f17`
* checked when this document was built: the reference decoder's output equals the bytes the input was encoded from

The output, for orientation:

```
pdf 1.4 revisions 1 objects 4
trailer root 1 0 info - id -
object 1 0 << /Type /Catalog /Pages 2 0 R >>
object 2 0 << /Type /Pages /Kids [ 3 0 R ] /Count 1 >>
object 3 0 << /Type /Page /Parent 2 0 R /MediaBox [ 0 0 612 792 ] /Contents 4 0 R >>
object 4 0 << /Length 391 /Filter /FlateDecode >> stream raw 391 decoded 521 sha256 55fc2af6efed3baa7754547217c7c732eeacd1ab4b8ccf257e8d2054fb737f7a
page 1 object 3 0 mediabox [ 0 0 612 792 ] rotate 0 contents 1 bytes 521 sha256 55fc2af6efed3baa7754547217c7c732eeacd1ab4b8ccf257e8d2054fb737f7a operators 48 tokens 839185abc992a0be493c3afafa29dc2af929a339d69e5ea9c4f9653e746d7528
```

```hex content
255044462d312e340a312030206f626a0a3c3c202f54797065202f436174616c
6f67202f5061676573203220302052203e3e0a656e646f626a0a322030206f62
6a0a3c3c202f54797065202f5061676573202f4b696473205b33203020525d20
2f436f756e742031203e3e0a656e646f626a0a332030206f626a0a3c3c202f54
797065202f50616765202f506172656e74203220302052202f4d65646961426f
78205b30203020363132203739325d202f436f6e74656e747320342030205220
3e3e0a656e646f626a0a342030206f626a0a3c3c202f4c656e67746820333931
202f46696c746572202f466c6174654465636f6465203e3e0a73747265616d0a
789c4d50616bdb3010ddf6ad82fd87c7a0d432d4929c986e100cb563270ecbd6
61413fa4fee0258ee34cb65bc7c185b1ffbe73c6a0dce978a77bbad3bd172848
32853bd7f1246ea523b1ad3f32b14815ca13361328c7cb88b26377f88c208178
840bb11c43f010d29d08538805448c8db85fbe6648e690328eafe2584a9f4509
0b345515940bbd7f33915c42d7b09685312d9eaca1edccee8973e823db58f71c
b78a1856c0a13cc7c36c3af133e815b40dabea6f4e1c37d4c885f5c2f1099166
63e71a4a8e6ee08ee9e4924c47b8c501e985f38fd11578b4d1606f23b0f1d366
e201b3995887e302105ff3a6845534dcf711cc4344eb10227dce1b04eb4bc644
522bcc5ba64835491f745c0f5d79dd57e5a1a739a595737ddca84caf6653e5eb
a3f8469ab26be4d8b6755d343daca1ea0f1cbbc25475d517dd89050909ac485f
259235faee5c909eec7d947c4094bcbe1be5fcf17f4f32839470496841420c84
57748eecf2709f9b5381e66c0cd5cfcdafa61d9aefcf8cc347863ff80d0f03fb
02b2bfbd0f7ade0a656e6473747265616d0a656e646f626a0a787265660a3020
350a303030303030303030302036353533352066200a30303030303030303039
203030303030206e200a30303030303030303538203030303030206e200a3030
3030303030313135203030303030206e200a3030303030303032303220303030
3030206e200a747261696c65720a3c3c202f53697a652035202f526f6f742031
20302052203e3e0a7374617274787265660a3636350a2525454f460a
```

### Vector `lenient`

A file that breaks the rules of PDF in ways this document nevertheless defines an outcome for (other readers repair such files differently - see the measured comparison above). The cross-reference table lists object 13 as FREE and its own trailer's `/XRefStm` stream says it is in object stream 16: the stream's entry replaces the free entry of its table (section 6.3). The root page tree node has a wrong `/Count`. Its first child (object 3) has no `/Type` but has `/Kids`: an intermediate node. Page 1 (object 4) has a `/Contents` array with a reference to a missing object, which is not counted, a font resource named `/F#31` (the name F1) and an entry `/Bad 5` that is not a font. Page 2 (object 5) has no `/Type` and no `/Kids`: a page. The second child's `/Kids` holds a page dictionary written directly, not as a reference: it is skipped. Page 3 (object 7) has `/Rotate null`, which counts as absent, so 90 is inherited. Stream 10 has a `/Length` that is too small, 11 one that is too large (and CR LF line ends), 12 none at all - there the data itself ends in a line feed and the end of line before `endstream` is a CR: exactly one end of line is removed. Stream 14 has a TIFF predictor and five bytes after the last complete row, stream 15 a PNG predictor and a final row of two bytes: the partial row is decoded as far as it goes. The font's `/BaseFont` is written `/A#zz#41`: a `#` not followed by two hexadecimal digits is an ordinary character.

* input: 1696 bytes, sha256 `990da279560ba987dabfae639beb566bbec318df35872bfd2aa57679d4f5f423`
* output form: the text listing of section 14: `pdf <version> revisions <n> objects <n>`, a `trailer` line, `info` lines, one `object` line per in-use object, then for each page a `page` line and its `font` lines; UTF-8, LF line ends
* output: 2435 bytes, sha256 `e0592324e02517dca57c59344b700da5036c530bd3b06498324f22aa82ef00a6`
* checked when this document was built: the reference decoder's output equals the bytes the input was encoded from

The output, for orientation:

```
pdf 1.5 revisions 1 objects 15
trailer root 1 0 info - id -
object 1 0 << /Type /Catalog /Pages 2 0 R >>
object 2 0 << /Type /Pages /Kids [ 3 0 R 6 0 R ] /Count 99 /MediaBox [ 0 0 30 40 ] /Rotate 90 >>
object 3 0 << /Kids [ 4 0 R 5 0 R ] /Rotate 180 >>
object 4 0 << /Type /Page /Parent 3 0 R /Contents [ 10 0 R 99 0 R ] /Resources << /Font << /F1 13 0 R /Bad 5 >> >> >>
object 5 0 << /Parent 3 0 R /Rotate 0 >>
object 6 0 << /Type /Pages /Kids [ << /Type /Page /Contents 12 0 R >> 7 0 R ] >>
object 7 0 << /Type /Page /Contents 11 0 R /Rotate null >>
object 10 0 << /Length 6 >> stream raw 13 decoded 13 sha256 67dd03cf19f0bcb54ca9dfc1b63ca1d8145c5162640b4e3ee6e6d331f9f94bc3
object 11 0 << /Length 4000000 >> stream raw 32 decoded 32 sha256 7732ee9bb1572b1423c72e3b7df7339fd50ca5d389e5d5e1a451290789ddbaa5
object 12 0 << /Kind /NoLength >> stream raw 4 decoded 4 sha256 27add8fa7e1bfd6c65fc9025962ba0bb49fba5bc58842fe726f95c5a6cf393bd
object 13 0 << /Type /Font /Subtype /Type1 /BaseFont /A#zzA >>
object 14 0 << /Length 23 /Filter /FlateDecode /DecodeParms << /Predictor 2 /Colors 3 /Columns 5 >> >> stream raw 23 decoded 35 sha256 82821a923424084d192374df9bed565311c308ac68c97972d08d76fbb59e512f
object 15 0 << /Length 21 /Filter /FlateDecode /DecodeParms << /Predictor 12 /Columns 4 >> >> stream raw 21 decoded 10 sha256 80c2adede092b59abcc2310d000a027dd7a803a1a9a783ccd3b9acc8a6f4ee7c
object 16 0 << /Type /ObjStm /N 1 /First 5 /Length 57 >> stream raw 57 decoded 57 sha256 555ad7546b9e45ce5b524f037de99c297954fe48419a7b736629bc6d213e0c35
object 17 0 << /Type /XRef /Size 18 /W [ 1 1 1 ] /Index [ 13 1 ] /Length 3 >> stream raw 3 decoded 3 sha256 cdbb8b46a6361990c5d82cf4ae1cbff9763089950bf5ba23b21f1bcd8c56b1bc
page 1 object 4 0 mediabox [ 0 0 30 40 ] rotate 180 contents 1 bytes 13 sha256 67dd03cf19f0bcb54ca9dfc1b63ca1d8145c5162640b4e3ee6e6d331f9f94bc3 operators 3 tokens 6b44fe49ff7a0e60e17ed7cdd21270470861424228272a4ca4ad2cf2f8576d29
font 1 F1 Type1 A#zzA program none -
page 2 object 5 0 mediabox [ 0 0 30 40 ] rotate 0 contents 0 bytes 0 sha256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 operators 0 tokens e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
page 3 object 7 0 mediabox [ 0 0 30 40 ] rotate 90 contents 1 bytes 32 sha256 7732ee9bb1572b1423c72e3b7df7339fd50ca5d389e5d5e1a451290789ddbaa5 operators 4 tokens 52c8a73f78ff750bf35e1ef4704d0b68d0919b1cd8e1929b2f3e3c7be8fc17ef
```

```hex lenient
255044462d312e350a312030206f626a0a3c3c202f54797065202f436174616c
6f67202f5061676573203220302052203e3e0a656e646f626a0a322030206f62
6a0a3c3c202f54797065202f5061676573202f4b696473205b33203020522036
203020525d202f436f756e74203939202f4d65646961426f78205b3020302033
302034305d202f526f74617465203930203e3e0a656e646f626a0a332030206f
626a0a3c3c202f4b696473205b34203020522035203020525d202f526f746174
6520313830203e3e0a656e646f626a0a342030206f626a0a3c3c202f54797065
202f50616765202f506172656e74203320302052202f436f6e74656e7473205b
313020302052203939203020525d202f5265736f7572636573203c3c202f466f
6e74203c3c202f4623333120313320302052202f4261642035203e3e203e3e20
3e3e0a656e646f626a0a352030206f626a0a3c3c202f506172656e7420332030
2052202f526f746174652030203e3e0a656e646f626a0a362030206f626a0a3c
3c202f54797065202f5061676573202f4b696473205b203c3c202f5479706520
2f50616765202f436f6e74656e747320313220302052203e3e20372030205220
5d203e3e0a656e646f626a0a372030206f626a0a3c3c202f54797065202f5061
6765202f436f6e74656e747320313120302052202f526f74617465206e756c6c
203e3e0a656e646f626a0a31302030206f626a0a3c3c202f4c656e6774682036
203e3e0a73747265616d0a302030206d20392039206c20530a656e6473747265
616d0a656e646f626a0a31312030206f626a0a3c3c202f4c656e677468203430
3030303030203e3e0a73747265616d0d0a4254202f4623333120382054662028
746869726420706167652920546a2045540d0a656e6473747265616d0a656e64
6f626a0a31322030206f626a0a3c3c202f4b696e64202f4e6f4c656e67746820
3e3e0a73747265616d0a3120670a0d656e6473747265616d0a656e646f626a0a
31342030206f626a0a3c3c202f4c656e677468203233202f46696c746572202f
466c6174654465636f6465202f4465636f64655061726d73203c3c202f507265
646963746f722032202f436f6c6f72732033202f436f6c756d6e732035203e3e
203e3e0a73747265616d0a789c6360e7d34402bc22d2c85c4626661656005070
04390a656e6473747265616d0a656e646f626a0a31352030206f626a0a3c3c20
2f4c656e677468203231202f46696c746572202f466c6174654465636f646520
2f4465636f64655061726d73203c3c202f507265646963746f72203132202f43
6f6c756d6e732034203e3e203e3e0a73747265616d0a789c63e01291d3606264
626661646506000447007a0a656e6473747265616d0a656e646f626a0a313620
30206f626a0a3c3c202f54797065202f4f626a53746d202f4e2031202f466972
73742035202f4c656e677468203537203e3e0a73747265616d0a31332030203c
3c202f54797065202f466f6e74202f53756274797065202f5479706531202f42
617365466f6e74202f41237a7a233431203e3e0a656e6473747265616d0a656e
646f626a0a31372030206f626a0a3c3c202f54797065202f58526566202f5369
7a65203138202f57205b31203120315d202f496e646578205b313320315d202f
4c656e6774682033203e3e0a73747265616d0a0210000a656e6473747265616d
0a656e646f626a0a787265660a302031380a3030303030303030303020363535
33352066200a30303030303030303039203030303030206e200a303030303030
30303538203030303030206e200a30303030303030313535203030303030206e
200a30303030303030323038203030303030206e200a30303030303030333330
203030303030206e200a30303030303030333735203030303030206e200a3030
3030303030343630203030303030206e200a3030303030303030303020303030
30302066200a303030303030303030302030303030302066200a303030303030
30353233203030303030206e200a30303030303030353836203030303030206e
200a30303030303030363736203030303030206e200a30303030303030303030
2030303030302066200a30303030303030373336203030303030206e200a3030
3030303030383834203030303030206e200a3030303030303130323120303030
3030206e200a30303030303031313537203030303030206e200a747261696c65
720a3c3c202f53697a65203138202f526f6f74203120302052202f5852656653
746d2031313537203e3e0a7374617274787265660a313235360a2525454f460a
```

### Vector `reportlab-flate-a85`

Written by reportlab: two pages, content streams with `/Filter [/ASCII85Decode /FlateDecode]`, a classic cross-reference table, an information dictionary whose title is a UTF-16BE text string.

* input: 2104 bytes, sha256 `b3f24986f6ce2d75aa27c7605f15e3ec0fe4b79c9a7d84ce1f38d5be1d751874`
* output form: the text listing of section 14: `pdf <version> revisions <n> objects <n>`, a `trailer` line, `info` lines, one `object` line per in-use object, then for each page a `page` line and its `font` lines; UTF-8, LF line ends
* output: 2435 bytes, sha256 `12e5ae4b02d33fad6be5d79540471b5f642255edb4f0564acc83ed080f8504bd`
* checked when this document was built: the reference decoder's output has the 2 page(s) the writer was asked for and contains the title and author, the page size, both standard fonts and the length and SHA-256 of the content streams, which were computed from the UNCOMPRESSED content streams of the reportlab original (the object numbers and offsets the writer chose are what the reference computes)

The output, for orientation:

```
pdf 1.3 revisions 1 objects 10
trailer root 6 0 info 7 0 id 33c4ff8082649f4a30ed8e21d6c0143f
info Author craft-werk
info CreationDate D:20000101000000+00'00'
info Creator anonymous
info Keywords %
info ModDate D:20000101000000+00'00'
info Producer ReportLab%20PDF%20Library%20-%20(opensource)
info Subject unspecified
info Title werk%20test%20%C3%BC
object 1 0 << /F1 2 0 R /F2 3 0 R >>
object 2 0 << /BaseFont /Helvetica /Encoding /WinAnsiEncoding /Name /F1 /Subtype /Type1 /Type /Font >>
object 3 0 << /BaseFont /Times-Roman /Encoding /WinAnsiEncoding /Name /F2 /Subtype /Type1 /Type /Font >>
object 4 0 << /Contents 9 0 R /MediaBox [ 0 0 200 120 ] /Parent 8 0 R /Resources << /Font 1 0 R /ProcSet [ /PDF /Text /ImageB /ImageC /ImageI ] >> /Rotate 0 /Trans << >> /Type /Page >>
object 5 0 << /Contents 10 0 R /MediaBox [ 0 0 200 120 ] /Parent 8 0 R /Resources << /Font 1 0 R /ProcSet [ /PDF /Text /ImageB /ImageC /ImageI ] >> /Rotate 0 /Trans << >> /Type /Page >>
object 6 0 << /PageMode /UseNone /Pages 8 0 R /Type /Catalog >>
object 7 0 << /Author <63726166742d7765726b> /CreationDate <443a32303030303130313030303030302b303027303027> /Creator <616e6f6e796d6f7573> /Keywords <> /ModDate <443a32303030303130313030303030302b30302 ...
object 8 0 << /Count 2 /Kids [ 4 0 R 5 0 R ] /Type /Pages >>
object 9 0 << /Filter [ /ASCII85Decode /FlateDecode ] /Length 192 >> stream raw 192 decoded 234 sha256 d04394d93acecdc792c6b1c9b97575b267a9b900277f2dda6e2d5a2728975677
object 10 0 << /Filter [ /ASCII85Decode /FlateDecode ] /Length 192 >> stream raw 192 decoded 234 sha256 46226d3b01ea2bc580cd41612118416a6ebd5f7498d7bbe6897a762a03e41ee2
page 1 object 4 0 mediabox [ 0 0 200 120 ] rotate 0 contents 1 bytes 234 sha256 d04394d93acecdc792c6b1c9b97575b267a9b900277f2dda6e2d5a2728975677 operators 27 tokens d12cdee6f1121ee702bc8dae603d4c43ae9084b7ba0968c946e2530b64adb869
font 1 F1 Type1 Helvetica program none -
font 1 F2 Type1 Times-Roman program none -
page 2 object 5 0 mediabox [ 0 0 200 120 ] rotate 0 contents 1 bytes 234 sha256 46226d3b01ea2bc580cd41612118416a6ebd5f7498d7bbe6897a762a03e41ee2 operators 27 tokens 4df05a4dbd50fa66a8ebd0caf972d21680dfe7b5c7fc41981448934fc5bca5df
font 2 F1 Type1 Helvetica program none -
font 2 F2 Type1 Times-Roman program none -
```

```hex reportlab-flate-a85
255044462d312e330a25938c8b9e205265706f72744c61622047656e65726174
65642050444620646f63756d656e7420286f70656e736f75726365290a312030
206f626a0a3c3c0a2f4631203220302052202f46322033203020520a3e3e0a65
6e646f626a0a322030206f626a0a3c3c0a2f42617365466f6e74202f48656c76
6574696361202f456e636f64696e67202f57696e416e7369456e636f64696e67
202f4e616d65202f4631202f53756274797065202f5479706531202f54797065
202f466f6e740a3e3e0a656e646f626a0a332030206f626a0a3c3c0a2f426173
65466f6e74202f54696d65732d526f6d616e202f456e636f64696e67202f5769
6e416e7369456e636f64696e67202f4e616d65202f4632202f53756274797065
202f5479706531202f54797065202f466f6e740a3e3e0a656e646f626a0a3420
30206f626a0a3c3c0a2f436f6e74656e7473203920302052202f4d6564696142
6f78205b203020302032303020313230205d202f506172656e74203820302052
202f5265736f7572636573203c3c0a2f466f6e74203120302052202f50726f63
536574205b202f504446202f54657874202f496d61676542202f496d61676543
202f496d61676549205d0a3e3e202f526f746174652030202f5472616e73203c
3c0a0a3e3e200a20202f54797065202f506167650a3e3e0a656e646f626a0a35
2030206f626a0a3c3c0a2f436f6e74656e747320313020302052202f4d656469
61426f78205b203020302032303020313230205d202f506172656e7420382030
2052202f5265736f7572636573203c3c0a2f466f6e74203120302052202f5072
6f63536574205b202f504446202f54657874202f496d61676542202f496d6167
6543202f496d61676549205d0a3e3e202f526f746174652030202f5472616e73
203c3c0a0a3e3e200a20202f54797065202f506167650a3e3e0a656e646f626a
0a362030206f626a0a3c3c0a2f506167654d6f6465202f5573654e6f6e65202f
5061676573203820302052202f54797065202f436174616c6f670a3e3e0a656e
646f626a0a372030206f626a0a3c3c0a2f417574686f72202863726166742d77
65726b29202f4372656174696f6e446174652028443a32303030303130313030
303030302b30302730302729202f43726561746f722028616e6f6e796d6f7573
29202f4b6579776f726473202829202f4d6f64446174652028443a3230303030
3130313030303030302b30302730302729202f50726f64756365722028526570
6f72744c616220504446204c696272617279202d205c286f70656e736f757263
655c2929200a20202f5375626a6563742028756e73706563696669656429202f
5469746c6520287765726b2074657374205c33373429202f5472617070656420
2f46616c73650a3e3e0a656e646f626a0a382030206f626a0a3c3c0a2f436f75
6e742032202f4b696473205b203420302052203520302052205d202f54797065
202f50616765730a3e3e0a656e646f626a0a392030206f626a0a3c3c0a2f4669
6c746572205b202f415343494938354465636f6465202f466c6174654465636f
6465205d202f4c656e677468203139320a3e3e0a73747265616d0a476173332d
30616b6950262d5e75545e5a2836545f6a53484f672f557263234c4f4b736030
6023683b65633130286f724946613b6d33252a5a713a2665233b363a2837366e
74392a4d302e25392c557347603b6c6235496c28523e2c253e40283e365c4b49
3072596b5a62366d736a4b52534341244548312721463362457073722f715427
544a212926645a4b5670495f48496a49426c2c2a426c2b483f22283c53344842
476463282550224a436e6b6e3a5c4d3a2d5e6f415a475352407e3e656e647374
7265616d0a656e646f626a0a31302030206f626a0a3c3c0a2f46696c74657220
5b202f415343494938354465636f6465202f466c6174654465636f6465205d20
2f4c656e677468203139320a3e3e0a73747265616d0a476173332d30616b6950
262d5e75545e5a2836543656506536672f557263234c4f4b7360306023683b65
633130286f724946613f4143212a243b295064636442312464394c4b5631703d
39222772744c5d5a2c5142543d6f5b65556569525c4d656c6d612a58255c5f44
21735f4a33475e5b6a29216e423a6032656c712a2e2e734f34752f66513f6d54
474d6954556031684b3b44295c6f405a5e2c552a2b322e72383932344b685b35
2c74677072555f3a415d3a2d5e6f415a567262277e3e656e6473747265616d0a
656e646f626a0a787265660a302031310a303030303030303030302036353533
352066200a30303030303030303631203030303030206e200a30303030303030
313032203030303030206e200a30303030303030323039203030303030206e20
0a30303030303030333138203030303030206e200a3030303030303035313120
3030303030206e200a30303030303030373035203030303030206e200a303030
30303030373733203030303030206e200a303030303030313034312030303030
30206e200a30303030303031313036203030303030206e200a30303030303031
333838203030303030206e200a747261696c65720a3c3c0a2f4944200a5b3c33
336334666638303832363439663461333065643865323164366330313433663e
3c33336334666638303832363439663461333065643865323164366330313433
663e5d0a25205265706f72744c61622067656e6572617465642050444620646f
63756d656e74202d2d2064696765737420286f70656e736f75726365290a0a2f
496e666f2037203020520a2f526f6f742036203020520a2f53697a652031310a
3e3e0a7374617274787265660a313637310a2525454f460a
```

### Vector `qpdf-objstm-xrefstream`

The same document rewritten by qpdf with every non-stream object in an object stream and a cross-reference stream (Flate, PNG predictor 12, `/W [1 2 1]`) instead of a table.

* input: 1315 bytes, sha256 `aeec50375948aded217076a6cb77aca3ae2e0ecbd5117d67f9b29b99ce9a70cc`
* output form: the text listing of section 14: `pdf <version> revisions <n> objects <n>`, a `trailer` line, `info` lines, one `object` line per in-use object, then for each page a `page` line and its `font` lines; UTF-8, LF line ends
* output: 2904 bytes, sha256 `81959a5601da139f0c5eb59178218bf89ec7772e7f56669000c821145f1adaac`
* checked when this document was built: the reference decoder's output has the 2 page(s) the writer was asked for and contains the title and author, the page size, both standard fonts and the length and SHA-256 of the content streams, which were computed from the UNCOMPRESSED content streams of the reportlab original (the object numbers and offsets the writer chose are what the reference computes)

The output, for orientation:

```
pdf 1.5 revisions 1 objects 12
trailer root 7 0 info 8 0 id 33c4ff8082649f4a30ed8e21d6c0143f
info Author craft-werk
info CreationDate D:20000101000000+00'00'
info Creator anonymous
info Keywords %
info ModDate D:20000101000000+00'00'
info Producer ReportLab%20PDF%20Library%20-%20(opensource)
info Subject unspecified
info Title werk%20test%20%C3%BC
object 1 0 << /Type /ObjStm /Length 442 /Filter /FlateDecode /N 8 /First 45 >> stream raw 442 decoded 957 sha256 3b7f771aca54097883b39ec7172f597e72cc02e58214e408c641717bfd9d85b5
object 2 0 << /F1 3 0 R /F2 4 0 R >>
object 3 0 << /BaseFont /Helvetica /Encoding /WinAnsiEncoding /Name /F1 /Subtype /Type1 /Type /Font >>
object 4 0 << /BaseFont /Times-Roman /Encoding /WinAnsiEncoding /Name /F2 /Subtype /Type1 /Type /Font >>
object 5 0 << /Contents 10 0 R /MediaBox [ 0 0 200 120 ] /Parent 9 0 R /Resources << /Font 2 0 R /ProcSet [ /PDF /Text /ImageB /ImageC /ImageI ] >> /Rotate 0 /Trans << >> /Type /Page >>
object 6 0 << /Contents 11 0 R /MediaBox [ 0 0 200 120 ] /Parent 9 0 R /Resources << /Font 2 0 R /ProcSet [ /PDF /Text /ImageB /ImageC /ImageI ] >> /Rotate 0 /Trans << >> /Type /Page >>
object 7 0 << /PageMode /UseNone /Pages 9 0 R /Type /Catalog >>
object 8 0 << /Author <63726166742d7765726b> /CreationDate <443a32303030303130313030303030302b303027303027> /Creator <616e6f6e796d6f7573> /Keywords <> /ModDate <443a32303030303130313030303030302b30302 ...
object 9 0 << /Count 2 /Kids [ 5 0 R 6 0 R ] /Type /Pages >>
object 10 0 << /Length 152 /Filter /FlateDecode >> stream raw 152 decoded 234 sha256 d04394d93acecdc792c6b1c9b97575b267a9b900277f2dda6e2d5a2728975677
object 11 0 << /Length 152 /Filter /FlateDecode >> stream raw 152 decoded 234 sha256 46226d3b01ea2bc580cd41612118416a6ebd5f7498d7bbe6897a762a03e41ee2
object 12 0 << /Type /XRef /Length 37 /Filter /FlateDecode /DecodeParms << /Columns 4 /Predictor 12 >> /W [ 1 2 1 ] /Info 8 0 R /Root 7 0 R /Size 13 /ID [ <33c4ff8082649f4a30ed8e21d6c0143f> <21d18bbe5 ...
page 1 object 5 0 mediabox [ 0 0 200 120 ] rotate 0 contents 1 bytes 234 sha256 d04394d93acecdc792c6b1c9b97575b267a9b900277f2dda6e2d5a2728975677 operators 27 tokens d12cdee6f1121ee702bc8dae603d4c43ae9084b7ba0968c946e2530b64adb869
font 1 F1 Type1 Helvetica program none -
font 1 F2 Type1 Times-Roman program none -
page 2 object 6 0 mediabox [ 0 0 200 120 ] rotate 0 contents 1 bytes 234 sha256 46226d3b01ea2bc580cd41612118416a6ebd5f7498d7bbe6897a762a03e41ee2 operators 27 tokens 4df05a4dbd50fa66a8ebd0caf972d21680dfe7b5c7fc41981448934fc5bca5df
font 2 F1 Type1 Helvetica program none -
font 2 F2 Type1 Times-Roman program none -
```

```hex qpdf-objstm-xrefstream
255044462d312e350a25bff7a2fe0a312030206f626a0a3c3c202f5479706520
2f4f626a53746d202f4c656e67746820343432202f46696c746572202f466c61
74654465636f6465202f4e2038202f4669727374203435203e3e0a7374726561
6d0a789cd5534b4fe33010bef32be6462254f9010d05a14ab4dd6a110f55a568
0fc0c14d8662b6b123db59e87fe7b063a7d5227158ae24913d9ec7e7cfdf3812
381c822ce0088418401fa49050c0e1e0188ea15f48184021fa70028342ee9d9d
019b0acae730274b5251b486c31419298f536b02b09fb8fe8341970ad80f53da
4a9b15b05fda9c1bafff396e548d098fddb6cbb06968b1a05174134522d627ec
85aed1f7e6b656e62be8f22be863b2d1040f827747bbc64aab917d837b881ec9
3908c9e111d84c39ca243d52de1cbd6d5d891e92341152769199b3e52d060260
b3c99436c537227f51ab158eb6f3783b5f10ee70486036a88054ce164e990419
dd1ddd19257ea62bbe03dd685fdb8abc771e6facd986fd8e5557315641aded6a
5774de8667eb202b9d7a0abd5774bf73ca71a882b6661237ce26a77450ce05bd
e939e07c9fbe5d5eac56c69a4d6d5b4fce4bdcbc5a5779c868417cfe07429254
6d898432c7c6ba70a59610b5b9d24ba7dc067af090d9064d27e9439ea79bf682
6580ac35bec1523f69acf27865c39ab68a8780803ec07b9e446b1aaca80d6aed
3fb4b64d4d61979a98ded3ff18252ad2f8f8515c1f2bfe0210ba13c30a656e64
73747265616d0a656e646f626a0a31302030206f626a0a3c3c202f4c656e6774
6820313532202f46696c746572202f466c6174654465636f6465203e3e0a7374
7265616d0a789c7dce310bc2301005e03dbfe28dadc399c4b6da55501707d11b
b3c4982a6a5369fcff18ab8883c81d373c1e1fa720d3a8e1ba169833c64b05a5
c10d544105788d058b3fb97a135aa296e016d9c61e7d0a4c76b3bd0fd1e4b0e1
0063b0b7ee12af369e72f0193cfac81af5004b9afd84a72f387ad725a9e9c2fd
4b208df40f55d8ae4478b6d356924a4c24e912bdc74e403c00b2c3361d0a656e
6473747265616d0a656e646f626a0a31312030206f626a0a3c3c202f4c656e67
746820313532202f46696c746572202f466c6174654465636f6465203e3e0a73
747265616d0a789c7dce310bc2301005e03dbfe28dad434cceb6da55501707d1
1bb3c4982a6a5369fcff18ab8883c83dde701c1fa7a1d2e8a15d0bcc19e3a586
2670035dc802bcc682c59fbd7e13a4502b708b6c638f1e0493dd6cef4334396c
38c018ecadbbc4ab8da71c7c068f3e32a11e6025673fe1e90b8ede75496aba70
ff122421fd232b6c57223caf532a254b4c94a412bdc74e403c00b353361e0a65
6e6473747265616d0a656e646f626a0a31322030206f626a0a3c3c202f547970
65202f58526566202f4c656e677468203337202f46696c746572202f466c6174
654465636f6465202f4465636f64655061726d73203c3c202f436f6c756d6e73
2034202f507265646963746f72203132203e3e202f57205b203120322031205d
202f496e666f203820302052202f526f6f74203720302052202f53697a652031
33202f4944205b3c333363346666383038323634396634613330656438653231
64366330313433663e3c32316431386262653530623264313363353764303861
623433323431313062313e5d203e3e0a73747265616d0a789c63620002264606
7e10f1898109c8632440fc67d2fdc9c4c0f810a4f82103005c64050f0a656e64
73747265616d0a656e646f626a0a7374617274787265660a313030380a252545
4f460a
```

### Vector `qpdf-linearized`

The same document written by qpdf as a LINEARIZED file: the first page's objects come first and the file has two cross-reference sections linked by `/Prev`, although it was written in one pass. It is read from its end like any other file.

* input: 2395 bytes, sha256 `2664afe6bc4e3c751efd606c3fe2cd85bb0f5f49ecb045662dde5c8b7ba4fe2f`
* output form: the text listing of section 14: `pdf <version> revisions <n> objects <n>`, a `trailer` line, `info` lines, one `object` line per in-use object, then for each page a `page` line and its `font` lines; UTF-8, LF line ends
* output: 2634 bytes, sha256 `22b8de7e799e64443674e7dd4e594f0c6e1ac09b5bd73776ad092d758061259a`
* checked when this document was built: the reference decoder's output has the 2 page(s) the writer was asked for and contains the title and author, the page size, both standard fonts and the length and SHA-256 of the content streams, which were computed from the UNCOMPRESSED content streams of the reportlab original (the object numbers and offsets the writer chose are what the reference computes)

The output, for orientation:

```
pdf 1.3 revisions 2 objects 12
trailer root 6 0 info 4 0 id 33c4ff8082649f4a30ed8e21d6c0143f
info Author craft-werk
info CreationDate D:20000101000000+00'00'
info Creator anonymous
info Keywords %
info ModDate D:20000101000000+00'00'
info Producer ReportLab%20PDF%20Library%20-%20(opensource)
info Subject unspecified
info Title werk%20test%20%C3%BC
object 1 0 << /Contents 2 0 R /MediaBox [ 0 0 200 120 ] /Parent 3 0 R /Resources << /Font 10 0 R /ProcSet [ /PDF /Text /ImageB /ImageC /ImageI ] >> /Rotate 0 /Trans << >> /Type /Page >>
object 2 0 << /Length 152 /Filter /FlateDecode >> stream raw 152 decoded 234 sha256 46226d3b01ea2bc580cd41612118416a6ebd5f7498d7bbe6897a762a03e41ee2
object 3 0 << /Count 2 /Kids [ 8 0 R 1 0 R ] /Type /Pages >>
object 4 0 << /Author <63726166742d7765726b> /CreationDate <443a32303030303130313030303030302b303027303027> /Creator <616e6f6e796d6f7573> /Keywords <> /ModDate <443a32303030303130313030303030302b30302 ...
object 5 0 << /Linearized 1 /L 2395 /H [ 621 131 ] /O 8 /E 1428 /N 2 /T 2177 >>
object 6 0 << /PageMode /UseNone /Pages 3 0 R /Type /Catalog >>
object 7 0 << /Filter /FlateDecode /S 46 /Length 54 >> stream raw 54 decoded 76 sha256 ce9f1de06d030aac036fa668821f7d7f60b408b904734719556a475321b63a45
object 8 0 << /Contents 9 0 R /MediaBox [ 0 0 200 120 ] /Parent 3 0 R /Resources << /Font 10 0 R /ProcSet [ /PDF /Text /ImageB /ImageC /ImageI ] >> /Rotate 0 /Trans << >> /Type /Page >>
object 9 0 << /Length 152 /Filter /FlateDecode >> stream raw 152 decoded 234 sha256 d04394d93acecdc792c6b1c9b97575b267a9b900277f2dda6e2d5a2728975677
object 10 0 << /F1 11 0 R /F2 12 0 R >>
object 11 0 << /BaseFont /Helvetica /Encoding /WinAnsiEncoding /Name /F1 /Subtype /Type1 /Type /Font >>
object 12 0 << /BaseFont /Times-Roman /Encoding /WinAnsiEncoding /Name /F2 /Subtype /Type1 /Type /Font >>
page 1 object 8 0 mediabox [ 0 0 200 120 ] rotate 0 contents 1 bytes 234 sha256 d04394d93acecdc792c6b1c9b97575b267a9b900277f2dda6e2d5a2728975677 operators 27 tokens d12cdee6f1121ee702bc8dae603d4c43ae9084b7ba0968c946e2530b64adb869
font 1 F1 Type1 Helvetica program none -
font 1 F2 Type1 Times-Roman program none -
page 2 object 1 0 mediabox [ 0 0 200 120 ] rotate 0 contents 1 bytes 234 sha256 46226d3b01ea2bc580cd41612118416a6ebd5f7498d7bbe6897a762a03e41ee2 operators 27 tokens 4df05a4dbd50fa66a8ebd0caf972d21680dfe7b5c7fc41981448934fc5bca5df
font 2 F1 Type1 Helvetica program none -
font 2 F2 Type1 Times-Roman program none -
```

```hex qpdf-linearized
255044462d312e330a25bff7a2fe0a352030206f626a0a3c3c202f4c696e6561
72697a65642031202f4c2032333935202f48205b2036323120313331205d202f
4f2038202f452031343238202f4e2032202f542032313737203e3e0a656e646f
626a0a2020202020202020202020202020202020202020202020202020202020
2020202020202020202020202020202020202020202020202020202020202020
2020202020202020202020202020202020202020202020202020202020202020
20202020202020202020202020202020202020202020200a787265660a352038
0a30303030303030303135203030303030206e200a3030303030303035353320
3030303030206e200a30303030303030363231203030303030206e200a303030
30303030373532203030303030206e200a303030303030303934322030303030
30206e200a30303030303031313636203030303030206e200a30303030303031
323130203030303030206e200a30303030303031333138203030303030206e20
0a747261696c6572203c3c202f496e666f203420302052202f526f6f74203620
302052202f53697a65203133202f507265762032313639202020202020202020
2020202020202020202f4944205b3c3333633466663830383236343966346133
3065643865323164366330313433663e3c666632333965393832383630623365
65393266366336386539316233346433383e5d203e3e0a737461727478726566
0a300a2525454f460a362030206f626a0a3c3c202f506167654d6f6465202f55
73654e6f6e65202f5061676573203320302052202f54797065202f436174616c
6f67203e3e0a656e646f626a0a372030206f626a0a3c3c202f46696c74657220
2f466c6174654465636f6465202f53203436202f4c656e677468203534203e3e
0a73747265616d0a789c6360606002a25c10c9388f8193010ac06c2606662093
e540330383811f4333033260856206061d068e495b181c9c1800ca6c06170a65
6e6473747265616d0a656e646f626a0a382030206f626a0a3c3c202f436f6e74
656e7473203920302052202f4d65646961426f78205b20302030203230302031
3230205d202f506172656e74203320302052202f5265736f7572636573203c3c
202f466f6e7420313020302052202f50726f63536574205b202f504446202f54
657874202f496d61676542202f496d61676543202f496d61676549205d203e3e
202f526f746174652030202f5472616e73203c3c203e3e202f54797065202f50
616765203e3e0a656e646f626a0a392030206f626a0a3c3c202f4c656e677468
20313532202f46696c746572202f466c6174654465636f6465203e3e0a737472
65616d0a789c7dce310bc2301005e03dbfe28dadc399c4b6da55501707d11bb3
c4982a6a5369fcff18ab8883c81d373c1e1fa720d3a8e1ba169833c64b05a5c1
0d544105788d058b3fb97a135aa296e016d9c61e7d0a4c76b3bd0fd1e4b0e100
63b0b7ee12af369e72f0193cfac81af5004b9afd84a72f387ad725a9e9c2fd4b
208df40f55d8ae4478b6d356924a4c24e912bdc74e403c00b2c3361d0a656e64
73747265616d0a656e646f626a0a31302030206f626a0a3c3c202f4631203131
20302052202f463220313220302052203e3e0a656e646f626a0a31312030206f
626a0a3c3c202f42617365466f6e74202f48656c766574696361202f456e636f
64696e67202f57696e416e7369456e636f64696e67202f4e616d65202f463120
2f53756274797065202f5479706531202f54797065202f466f6e74203e3e0a65
6e646f626a0a31322030206f626a0a3c3c202f42617365466f6e74202f54696d
65732d526f6d616e202f456e636f64696e67202f57696e416e7369456e636f64
696e67202f4e616d65202f4632202f53756274797065202f5479706531202f54
797065202f466f6e74203e3e0a656e646f626a0a312030206f626a0a3c3c202f
436f6e74656e7473203220302052202f4d65646961426f78205b203020302032
303020313230205d202f506172656e74203320302052202f5265736f75726365
73203c3c202f466f6e7420313020302052202f50726f63536574205b202f5044
46202f54657874202f496d61676542202f496d61676543202f496d6167654920
5d203e3e202f526f746174652030202f5472616e73203c3c203e3e202f547970
65202f50616765203e3e0a656e646f626a0a322030206f626a0a3c3c202f4c65
6e67746820313532202f46696c746572202f466c6174654465636f6465203e3e
0a73747265616d0a789c7dce310bc2301005e03dbfe28dad434cceb6da555017
07d11bb3c4982a6a5369fcff18ab8883c83dde701c1fa7a1d2e8a15d0bcc19e3
a5862670035dc802bcc682c59fbd7e13a4502b708b6c638f1e0493dd6cef4334
396c38c018ecadbbc4ab8da71c7c068f3e32a11e6025673fe1e90b8ede75496a
ba70ff122421fd232b6c57223caf532a254b4c94a412bdc74e403c00b353361e
0a656e6473747265616d0a656e646f626a0a332030206f626a0a3c3c202f436f
756e742032202f4b696473205b203820302052203120302052205d202f547970
65202f5061676573203e3e0a656e646f626a0a342030206f626a0a3c3c202f41
7574686f72202863726166742d7765726b29202f4372656174696f6e44617465
2028443a32303030303130313030303030302b30302730302729202f43726561
746f722028616e6f6e796d6f757329202f4b6579776f726473202829202f4d6f
64446174652028443a32303030303130313030303030302b3030273030272920
2f50726f647563657220285265706f72744c616220504446204c696272617279
202d205c286f70656e736f757263655c2929202f5375626a6563742028756e73
706563696669656429202f5469746c6520287765726b207465737420fc29202f
54726170706564202f46616c7365203e3e0a656e646f626a0a787265660a3020
350a303030303030303030302036353533352066200a30303030303031343238
203030303030206e200a30303030303031363138203030303030206e200a3030
3030303031383432203030303030206e200a3030303030303139303720303030
3030206e200a747261696c6572203c3c202f53697a652035202f4944205b3c33
336334666638303832363439663461333065643865323164366330313433663e
3c66663233396539383238363062336565393266366336386539316233346433
383e5d203e3e0a7374617274787265660a3231360a2525454f460a
```

### Vector `mupdf-incremental`

The same document after MuPDF added a line of text to page 1 and saved INCREMENTALLY: the original bytes, then new objects and a second cross-reference table. Page 1 now has four content streams (MuPDF wraps the old one in `q` / `Q` and appends its own) and a third font resource; page 2 is untouched.

* input: 2971 bytes, sha256 `a27665eb1a7fb33c5da4f5ae1f90d82f16202b5a0ae835a3453fb87ddd684d4b`
* output form: the text listing of section 14: `pdf <version> revisions <n> objects <n>`, a `trailer` line, `info` lines, one `object` line per in-use object, then for each page a `page` line and its `font` lines; UTF-8, LF line ends
* output: 2945 bytes, sha256 `8b2ba8d7889620154679ee80464d35c9a77acf3184c5e74187dc9c71282b9702`
* checked when this document was built: the reference decoder's output has the 2 page(s) the writer was asked for and contains the title and author, the page size, both standard fonts and the length and SHA-256 of the content streams, which were computed from the UNCOMPRESSED content streams of the reportlab original (the object numbers and offsets the writer chose are what the reference computes)

The output, for orientation:

```
pdf 1.3 revisions 2 objects 14
trailer root 6 0 info 7 0 id 33c4ff8082649f4a30ed8e21d6c0143f
info Author craft-werk
info CreationDate D:20000101000000+00'00'
info Creator anonymous
info Keywords %
info ModDate D:20000101000000+00'00'
info Producer ReportLab%20PDF%20Library%20-%20(opensource)
info Subject unspecified
info Title werk%20test%20%C3%BC
object 1 0 << /F1 2 0 R /F2 3 0 R /helv 11 0 R >>
object 2 0 << /BaseFont /Helvetica /Encoding /WinAnsiEncoding /Name /F1 /Subtype /Type1 /Type /Font >>
object 3 0 << /BaseFont /Times-Roman /Encoding /WinAnsiEncoding /Name /F2 /Subtype /Type1 /Type /Font >>
object 4 0 << /Type /Page /Contents [ 12 0 R 9 0 R 13 0 R 14 0 R ] /MediaBox [ 0 0 200 120 ] /Parent 8 0 R /Resources << /Font 1 0 R /ProcSet [ /PDF /Text /ImageB /ImageC /ImageI ] >> /Rotate 0 /Trans << >> >>
object 5 0 << /Contents 10 0 R /MediaBox [ 0 0 200 120 ] /Parent 8 0 R /Resources << /Font 1 0 R /ProcSet [ /PDF /Text /ImageB /ImageC /ImageI ] >> /Rotate 0 /Trans << >> /Type /Page >>
object 6 0 << /PageMode /UseNone /Pages 8 0 R /Type /Catalog >>
object 7 0 << /Author <63726166742d7765726b> /CreationDate <443a32303030303130313030303030302b303027303027> /Creator <616e6f6e796d6f7573> /Keywords <> /ModDate <443a32303030303130313030303030302b30302 ...
object 8 0 << /Count 2 /Kids [ 4 0 R 5 0 R ] /Type /Pages >>
object 9 0 << /Length 234 >> stream raw 234 decoded 234 sha256 d04394d93acecdc792c6b1c9b97575b267a9b900277f2dda6e2d5a2728975677
object 10 0 << /Length 234 >> stream raw 234 decoded 234 sha256 46226d3b01ea2bc580cd41612118416a6ebd5f7498d7bbe6897a762a03e41ee2
object 11 0 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>
object 12 0 << /Length 2 >> stream raw 2 decoded 2 sha256 4adc33bd9fe74303c344be46e5916d65182fb218e248fe80452ab3f025b06c64
object 13 0 << /Length 3 >> stream raw 3 decoded 3 sha256 4ecc2a57848dc2b3163d07c6aa64c5b305c8cf77037fef8bc29a6ea7e58311aa
object 14 0 << /Length 68 >> stream raw 68 decoded 68 sha256 7dd1d8ec053ef7e5aa4bcb739314b6e1d96ba376a7ceb6d6ec0953a7866a03cd
page 1 object 4 0 mediabox [ 0 0 200 120 ] rotate 0 contents 4 bytes 310 sha256 6a4da1061baf75ba06bc09f04602ec8dbbdd2be3e08d840d4893da4ae5a467d1 operators 36 tokens 561de7b6ab68add09430d33268ab7f1f12403d81d466eca06b4d995c189acf11
font 1 F1 Type1 Helvetica program none -
font 1 F2 Type1 Times-Roman program none -
font 1 helv Type1 Helvetica program none -
page 2 object 5 0 mediabox [ 0 0 200 120 ] rotate 0 contents 1 bytes 234 sha256 46226d3b01ea2bc580cd41612118416a6ebd5f7498d7bbe6897a762a03e41ee2 operators 27 tokens 4df05a4dbd50fa66a8ebd0caf972d21680dfe7b5c7fc41981448934fc5bca5df
font 2 F1 Type1 Helvetica program none -
font 2 F2 Type1 Times-Roman program none -
font 2 helv Type1 Helvetica program none -
```

```hex mupdf-incremental
255044462d312e330a25938c8b9e205265706f72744c61622047656e65726174
65642050444620646f63756d656e7420286f70656e736f75726365290a312030
206f626a0a3c3c0a2f4631203220302052202f46322033203020520a3e3e0a65
6e646f626a0a322030206f626a0a3c3c0a2f42617365466f6e74202f48656c76
6574696361202f456e636f64696e67202f57696e416e7369456e636f64696e67
202f4e616d65202f4631202f53756274797065202f5479706531202f54797065
202f466f6e740a3e3e0a656e646f626a0a332030206f626a0a3c3c0a2f426173
65466f6e74202f54696d65732d526f6d616e202f456e636f64696e67202f5769
6e416e7369456e636f64696e67202f4e616d65202f4632202f53756274797065
202f5479706531202f54797065202f466f6e740a3e3e0a656e646f626a0a3420
30206f626a0a3c3c0a2f436f6e74656e7473203920302052202f4d6564696142
6f78205b203020302032303020313230205d202f506172656e74203820302052
202f5265736f7572636573203c3c0a2f466f6e74203120302052202f50726f63
536574205b202f504446202f54657874202f496d61676542202f496d61676543
202f496d61676549205d0a3e3e202f526f746174652030202f5472616e73203c
3c0a0a3e3e200a20202f54797065202f506167650a3e3e0a656e646f626a0a35
2030206f626a0a3c3c0a2f436f6e74656e747320313020302052202f4d656469
61426f78205b203020302032303020313230205d202f506172656e7420382030
2052202f5265736f7572636573203c3c0a2f466f6e74203120302052202f5072
6f63536574205b202f504446202f54657874202f496d61676542202f496d6167
6543202f496d61676549205d0a3e3e202f526f746174652030202f5472616e73
203c3c0a0a3e3e200a20202f54797065202f506167650a3e3e0a656e646f626a
0a362030206f626a0a3c3c0a2f506167654d6f6465202f5573654e6f6e65202f
5061676573203820302052202f54797065202f436174616c6f670a3e3e0a656e
646f626a0a372030206f626a0a3c3c0a2f417574686f72202863726166742d77
65726b29202f4372656174696f6e446174652028443a32303030303130313030
303030302b30302730302729202f43726561746f722028616e6f6e796d6f7573
29202f4b6579776f726473202829202f4d6f64446174652028443a3230303030
3130313030303030302b30302730302729202f50726f64756365722028526570
6f72744c616220504446204c696272617279202d205c286f70656e736f757263
655c2929200a20202f5375626a6563742028756e73706563696669656429202f
5469746c6520287765726b2074657374205c33373429202f5472617070656420
2f46616c73650a3e3e0a656e646f626a0a382030206f626a0a3c3c0a2f436f75
6e742032202f4b696473205b203420302052203520302052205d202f54797065
202f50616765730a3e3e0a656e646f626a0a392030206f626a0a3c3c0a2f4c65
6e677468203233340a3e3e0a73747265616d0a31203020302031203020302063
6d20204254202f46312031322054662031342e3420544c2045540a4254202f46
312031322054662031342e3420544c2045540a42542031203020302031203230
20393020546d2028506167652031205c28706172656e735c2920616e64205c5c
206261636b736c6173682920546a20542a2045540a4254202f46322039205466
2031302e3820544c2045540a4254203120302030203120323020373020546d20
287365636f6e6420666f6e742920546a20542a2045540a2e32202e34202e3620
52470a6e2032302032302036302e352033302e323520726520530a200a656e64
73747265616d0a656e646f626a0a31302030206f626a0a3c3c0a2f4c656e6774
68203233340a3e3e0a73747265616d0a312030203020312030203020636d2020
4254202f46312031322054662031342e3420544c2045540a4254202f46312031
322054662031342e3420544c2045540a42542031203020302031203230203930
20546d2028506167652032205c28706172656e735c2920616e64205c5c206261
636b736c6173682920546a20542a2045540a4254202f46322039205466203130
2e3820544c2045540a4254203120302030203120323020373020546d20287365
636f6e6420666f6e742920546a20542a2045540a2e32202e34202e362052470a
6e2032302032302036302e352033302e323520726520530a200a656e64737472
65616d0a656e646f626a0a787265660a302031310a3030303030303030303020
36353533352066200a30303030303030303631203030303030206e200a303030
30303030313032203030303030206e200a303030303030303230392030303030
30206e200a30303030303030333138203030303030206e200a30303030303030
353131203030303030206e200a30303030303030373035203030303030206e20
0a30303030303030373733203030303030206e200a3030303030303130343120
3030303030206e200a30303030303031313036203030303030206e200a303030
30303031333930203030303030206e200a747261696c65720a3c3c0a2f494420
0a5b3c3333633466663830383236343966346133306564386532316436633031
3433663e3c333363346666383038323634396634613330656438653231643663
30313433663e5d0a25205265706f72744c61622067656e657261746564205044
4620646f63756d656e74202d2d2064696765737420286f70656e736f75726365
290a0a2f496e666f2037203020520a2f526f6f742036203020520a2f53697a65
2031310a3e3e0a7374617274787265660a313637350a2525454f460a0a252057
72697474656e206279204d7550444620312e32372e320a0a312030206f626a0a
3c3c2f46312032203020522f46322033203020522f68656c7620313120302052
3e3e0a656e646f626a0a0a342030206f626a0a3c3c2f547970652f506167652f
436f6e74656e74735b3132203020522039203020522031332030205220313420
3020525d2f4d65646961426f785b30203020323030203132305d2f506172656e
742038203020522f5265736f75726365733c3c2f466f6e742031203020522f50
726f635365745b2f5044462f546578742f496d616765422f496d616765432f49
6d616765495d3e3e2f526f7461746520302f5472616e733c3c3e3e3e3e0a656e
646f626a0a0a31312030206f626a0a3c3c2f547970652f466f6e742f53756274
7970652f54797065312f42617365466f6e742f48656c7665746963612f456e63
6f64696e672f57696e416e7369456e636f64696e673e3e0a656e646f626a0a0a
31322030206f626a0a3c3c2f4c656e67746820323e3e0a73747265616d0a710a
0a656e6473747265616d0a656e646f626a0a0a31332030206f626a0a3c3c2f4c
656e67746820333e3e0a73747265616d0a0a510a0a656e6473747265616d0a65
6e646f626a0a0a31342030206f626a0a3c3c2f4c656e6774682036383e3e0a73
747265616d0a0a710a42540a3120302030203120323020313020546d0a2f6865
6c762038205466205b3c36313634363436353634323036633631373436353732
3e5d544a0a45540a510a0a656e6473747265616d0a656e646f626a0a0a787265
660a3120310a30303030303032313336203030303030206e200a3420310a3030
3030303032313837203030303030206e200a313120340a303030303030323337
34203030303030206e200a30303030303032343634203030303030206e200a30
303030303032353135203030303030206e200a30303030303032353637203030
303030206e200a0a747261696c65720a3c3c2f49445b3c333343344646383038
32363439463441333045443845323144364330313433463e3c43394236393234
323634433045394638303644393346394438463539443935463e5d2f496e666f
2037203020522f526f6f742036203020522f53697a652031352f507265762031
3637353e3e0a7374617274787265660a323638350a2525454f460a
```

### Vector `pypdf-compressed`

The same document rewritten by pypdf with Flate-compressed content streams; pypdf writes its dictionaries with other spacing and line ends than the writers above.

* input: 1908 bytes, sha256 `8ec43007d3cee4589e18df3fdb481ddf5030bb22b97304f2b8af0a6528a42612`
* output form: the text listing of section 14: `pdf <version> revisions <n> objects <n>`, a `trailer` line, `info` lines, one `object` line per in-use object, then for each page a `page` line and its `font` lines; UTF-8, LF line ends
* output: 2397 bytes, sha256 `0f6550fb91b0eb97d3f2a86f296b7cd95d3995cdb18c3f6c2a16bf066f814632`
* checked when this document was built: the reference decoder's output has the 2 page(s) the writer was asked for and contains the title and author, the page size, both standard fonts and the length and SHA-256 of the content streams, which were computed from the UNCOMPRESSED content streams of the reportlab original (the object numbers and offsets the writer chose are what the reference computes)

The output, for orientation:

```
pdf 1.3 revisions 1 objects 10
trailer root 1 0 info 10 0 id 33c4ff8082649f4a30ed8e21d6c0143f
info Author craft-werk
info CreationDate D:20000101000000+00'00'
info Creator anonymous
info Keywords %
info ModDate D:20000101000000+00'00'
info Producer ReportLab%20PDF%20Library%20-%20(opensource)
info Subject unspecified
info Title werk%20test%20%C3%BC
object 1 0 << /PageMode /UseNone /Pages 2 0 R /Type /Catalog >>
object 2 0 << /Count 2 /Kids [ 3 0 R 8 0 R ] /Type /Pages >>
object 3 0 << /Contents 4 0 R /MediaBox [ 0 0 200 120 ] /Parent 2 0 R /Resources << /Font 5 0 R /ProcSet [ /PDF /Text /ImageB /ImageC /ImageI ] >> /Rotate 0 /Trans << >> /Type /Page >>
object 4 0 << /Filter /FlateDecode /Length 152 >> stream raw 152 decoded 234 sha256 d04394d93acecdc792c6b1c9b97575b267a9b900277f2dda6e2d5a2728975677
object 5 0 << /F1 6 0 R /F2 7 0 R >>
object 6 0 << /BaseFont /Helvetica /Encoding /WinAnsiEncoding /Name /F1 /Subtype /Type1 /Type /Font >>
object 7 0 << /BaseFont /Times-Roman /Encoding /WinAnsiEncoding /Name /F2 /Subtype /Type1 /Type /Font >>
object 8 0 << /Contents 9 0 R /MediaBox [ 0 0 200 120 ] /Parent 2 0 R /Resources << /Font 5 0 R /ProcSet [ /PDF /Text /ImageB /ImageC /ImageI ] >> /Rotate 0 /Trans << >> /Type /Page >>
object 9 0 << /Filter /FlateDecode /Length 152 >> stream raw 152 decoded 234 sha256 46226d3b01ea2bc580cd41612118416a6ebd5f7498d7bbe6897a762a03e41ee2
object 10 0 << /Author <63726166742d7765726b> /CreationDate <443a32303030303130313030303030302b303027303027> /Creator <616e6f6e796d6f7573> /Keywords <> /ModDate <443a32303030303130313030303030302b3030 ...
page 1 object 3 0 mediabox [ 0 0 200 120 ] rotate 0 contents 1 bytes 234 sha256 d04394d93acecdc792c6b1c9b97575b267a9b900277f2dda6e2d5a2728975677 operators 27 tokens d12cdee6f1121ee702bc8dae603d4c43ae9084b7ba0968c946e2530b64adb869
font 1 F1 Type1 Helvetica program none -
font 1 F2 Type1 Times-Roman program none -
page 2 object 8 0 mediabox [ 0 0 200 120 ] rotate 0 contents 1 bytes 234 sha256 46226d3b01ea2bc580cd41612118416a6ebd5f7498d7bbe6897a762a03e41ee2 operators 27 tokens 4df05a4dbd50fa66a8ebd0caf972d21680dfe7b5c7fc41981448934fc5bca5df
font 2 F1 Type1 Helvetica program none -
font 2 F2 Type1 Times-Roman program none -
```

```hex pypdf-compressed
255044462d312e330a25e2e3cfd30a312030206f626a0a3c3c0a2f506167654d
6f6465202f5573654e6f6e650a2f50616765732032203020520a2f5479706520
2f436174616c6f670a3e3e0a656e646f626a0a322030206f626a0a3c3c0a2f43
6f756e7420320a2f4b696473205b203320302052203820302052205d0a2f5479
7065202f50616765730a3e3e0a656e646f626a0a332030206f626a0a3c3c0a2f
436f6e74656e74732034203020520a2f4d65646961426f78205b203020302032
303020313230205d0a2f506172656e742032203020520a2f5265736f75726365
73203c3c0a2f466f6e742035203020520a2f50726f63536574205b202f504446
202f54657874202f496d61676542202f496d61676543202f496d61676549205d
0a3e3e0a2f526f7461746520300a2f5472616e73203c3c0a3e3e0a2f54797065
202f506167650a3e3e0a656e646f626a0a342030206f626a0a3c3c0a2f46696c
746572202f466c6174654465636f64650a2f4c656e677468203135320a3e3e0a
73747265616d0a789c7dce310bc2301005e03dbfe28dadc399c4b6da55501707
d11bb3c4982a6a5369fcff18ab8883c81d373c1e1fa720d3a8e1ba169833c64b
05a5c10d544105788d058b3fb97a135aa296e016d9c61e7d0a4c76b3bd0fd1e4
b0e10063b0b7ee12af369e72f0193cfac81af5004b9afd84a72f387ad725a9e9
c2fd4b208df40f55d8ae4478b6d356924a4c24e912bdc74e403c00b2c3361d0a
656e6473747265616d0a656e646f626a0a352030206f626a0a3c3c0a2f463120
36203020520a2f46322037203020520a3e3e0a656e646f626a0a362030206f62
6a0a3c3c0a2f42617365466f6e74202f48656c7665746963610a2f456e636f64
696e67202f57696e416e7369456e636f64696e670a2f4e616d65202f46310a2f
53756274797065202f54797065310a2f54797065202f466f6e740a3e3e0a656e
646f626a0a372030206f626a0a3c3c0a2f42617365466f6e74202f54696d6573
2d526f6d616e0a2f456e636f64696e67202f57696e416e7369456e636f64696e
670a2f4e616d65202f46320a2f53756274797065202f54797065310a2f547970
65202f466f6e740a3e3e0a656e646f626a0a382030206f626a0a3c3c0a2f436f
6e74656e74732039203020520a2f4d65646961426f78205b2030203020323030
20313230205d0a2f506172656e742032203020520a2f5265736f757263657320
3c3c0a2f466f6e742035203020520a2f50726f63536574205b202f504446202f
54657874202f496d61676542202f496d61676543202f496d61676549205d0a3e
3e0a2f526f7461746520300a2f5472616e73203c3c0a3e3e0a2f54797065202f
506167650a3e3e0a656e646f626a0a392030206f626a0a3c3c0a2f46696c7465
72202f466c6174654465636f64650a2f4c656e677468203135320a3e3e0a7374
7265616d0a789c7dce310bc2301005e03dbfe28dad434cceb6da55501707d11b
b3c4982a6a5369fcff18ab8883c83dde701c1fa7a1d2e8a15d0bcc19e3a58626
70035dc802bcc682c59fbd7e13a4502b708b6c638f1e0493dd6cef4334396c38
c018ecadbbc4ab8da71c7c068f3e32a11e6025673fe1e90b8ede75496aba70ff
122421fd232b6c57223caf532a254b4c94a412bdc74e403c00b353361e0a656e
6473747265616d0a656e646f626a0a31302030206f626a0a3c3c0a2f41757468
6f72202863726166745c3035357765726b290a2f4372656174696f6e44617465
2028445c30373232303030303130313030303030305c30353330305c30343730
305c303437290a2f43726561746f722028616e6f6e796d6f7573290a2f4b6579
776f7264732028290a2f4d6f64446174652028445c3037323230303030313031
3030303030305c30353330305c30343730305c303437290a2f50726f64756365
7220285265706f72744c616220504446204c696272617279205c303535205c30
35306f70656e736f757263655c303531290a2f5375626a6563742028756e7370
65636966696564290a2f5469746c6520287765726b2074657374205c33373429
0a2f54726170706564202f46616c73650a3e3e0a656e646f626a0a787265660a
302031310a303030303030303030302036353533352066200a30303030303030
303135203030303030206e200a30303030303030303833203030303030206e20
0a30303030303030313438203030303030206e200a3030303030303033333720
3030303030206e200a30303030303030353631203030303030206e200a303030
30303030363032203030303030206e200a303030303030303730392030303030
30206e200a30303030303030383138203030303030206e200a30303030303031
303037203030303030206e200a30303030303031323331203030303030206e20
0a747261696c65720a3c3c0a2f53697a652031310a2f526f6f74203120302052
0a2f496e666f203130203020520a2f4944205b203c3333633466663830383236
3439663461333065643865323164366330313433663e203c3333633466663830
3832363439663461333065643865323164366330313433663e205d0a3e3e0a73
74617274787265660a313533310a2525454f460a
```

### Vector `pillow-dct`

A 16 x 16 pixel RGB image saved as a PDF by Pillow: the page paints one image XObject whose data is a JPEG file (`/Filter /DCTDecode`). The stream is listed `partial DCTDecode`: its data is delivered as stored and is decoded with format `jpeg`.

* input: 1516 bytes, sha256 `0fb7cd6e2d52677b51a0f55d1d2d91ec15d0ac09ed3b9ac616a318757c1dffce`
* output form: the text listing of section 14: `pdf <version> revisions <n> objects <n>`, a `trailer` line, `info` lines, one `object` line per in-use object, then for each page a `page` line and its `font` lines; UTF-8, LF line ends
* output: 1099 bytes, sha256 `b0ab9d09193975dab55a35380d9272b858ee0e88dcfd2cb6b02bef8c8b4796f1`
* checked when this document was built: the reference decoder's output has the 1 page(s) the writer was asked for and contains the image dictionary with the size that was asked for, its stream left `partial DCTDecode`, and a page of 16 x 16 points (the object numbers and offsets the writer chose are what the reference computes)

The output, for orientation:

```
pdf 1.4 revisions 1 objects 6
trailer root 4 0 info 6 0 id -
info CreationDate D:20261012235428Z
info ModDate D:20261012235428Z
object 1 0 << /Type /XObject /Subtype /Image /Width 16 /Height 16 /Filter /DCTDecode /BitsPerComponent 8 /ColorSpace /DeviceRGB /Length 659 >> stream raw 659 partial DCTDecode 659 sha256 696dabe7db7d7 ...
object 2 0 << /Resources << /ProcSet [ /PDF /ImageC ] /XObject << /image 1 0 R >> >> /MediaBox [ 0 0 16 16 ] /Contents 3 0 R /Type /Page /Parent 5 0 R >>
object 3 0 << /Length 45 >> stream raw 45 decoded 45 sha256 d2932738365ba8491061ed04452b9843768806f5e0aeec6db933aaabc7ba38c9
object 4 0 << /Type /Catalog /Pages 5 0 R >>
object 5 0 << /Type /Pages /Count 1 /Kids [ 2 0 R ] >>
object 6 0 << /CreationDate <443a32303236313031323233353432385a> /ModDate <443a32303236313031323233353432385a> >>
page 1 object 2 0 mediabox [ 0 0 16 16 ] rotate 0 contents 1 bytes 45 sha256 d2932738365ba8491061ed04452b9843768806f5e0aeec6db933aaabc7ba38c9 operators 4 tokens 66a20299d0538089ab7baf73ca0e24fb07e63025a29f7ac65cf323a4987155c9
```

```hex pillow-dct
255044462d312e340a2520637265617465642062792050696c6c6f7720504446
206472697665720a342030206f626a3c3c0a2f54797065202f436174616c6f67
0a2f50616765732035203020520a3e3e656e646f626a0a352030206f626a3c3c
0a2f54797065202f50616765730a2f436f756e7420310a2f4b696473205b2032
20302052205d0a3e3e656e646f626a0a312030206f626a3c3c0a2f5479706520
2f584f626a6563740a2f53756274797065202f496d6167650a2f576964746820
31360a2f4865696768742031360a2f46696c746572202f4443544465636f6465
0a2f42697473506572436f6d706f6e656e7420380a2f436f6c6f725370616365
202f4465766963655247420a2f4c656e677468203635390a3e3e73747265616d
0affd8ffe000104a46494600010100000100010000ffdb004300080606070605
080707070909080a0c140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20242e27
20222c231c1c2837292c30313434341f27393d38323c2e333432ffdb00430109
09090c0b0c180d0d1832211c2132323232323232323232323232323232323232
32323232323232323232323232323232323232323232323232323232323232ff
c00011080010001003012200021101031101ffc4001f00000105010101010101
00000000000000000102030405060708090a0bffc400b5100002010303020403
050504040000017d01020300041105122131410613516107227114328191a108
2342b1c11552d1f02433627282090a161718191a25262728292a343536373839
3a434445464748494a535455565758595a636465666768696a73747576777879
7a838485868788898a92939495969798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6
b7b8b9bac2c3c4c5c6c7c8c9cad2d3d4d5d6d7d8d9dae1e2e3e4e5e6e7e8e9ea
f1f2f3f4f5f6f7f8f9faffc4001f010003010101010101010101000000000000
0102030405060708090a0bffc400b51100020102040403040705040400010277
000102031104052131061241510761711322328108144291a1b1c109233352f0
156272d10a162434e125f11718191a262728292a35363738393a434445464748
494a535455565758595a636465666768696a737475767778797a828384858687
88898a92939495969798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9bac2c3
c4c5c6c7c8c9cad2d3d4d5d6d7d8d9dae2e3e4e5e6e7e8e9eaf2f3f4f5f6f7f8
f9faffda000c03010002110311003f00f3fb1d0ba7c95d358685d3e4ae96c342
e9f2574f63a174f92b4c5e6be62e1fcef6d4ffd90a656e6473747265616d0a65
6e646f626a0a322030206f626a3c3c0a2f5265736f7572636573203c3c0a2f50
726f63536574205b202f504446202f496d61676543205d0a2f584f626a656374
203c3c0a2f696d6167652031203020520a3e3e0a3e3e0a2f4d65646961426f78
205b203020302031362e302031362e30205d0a2f436f6e74656e747320332030
20520a2f54797065202f506167650a2f506172656e742035203020520a3e3e65
6e646f626a0a332030206f626a3c3c0a2f4c656e6774682034350a3e3e737472
65616d0a712031362e303030303030203020302031362e303030303030203020
3020636d202f696d61676520446f20510a0a656e6473747265616d0a656e646f
626a0a362030206f626a3c3c0a2f4372656174696f6e446174652028443a3230
3236313031323233353432385a290a2f4d6f64446174652028443a3230323631
3031323233353432385a290a3e3e656e646f626a0a787265660a3020370a3030
30303030303030302036353533362066200a3030303030303031343420303030
3030206e200a30303030303030393636203030303030206e200a303030303030
31313236203030303030206e200a30303030303030303430203030303030206e
200a30303030303030303837203030303030206e200a30303030303031323139
203030303030206e200a747261696c65720a3c3c0a2f526f6f74203420302052
0a2f53697a6520370a2f496e666f2036203020520a3e3e0a7374617274787265
660a313330310a2525454f46
```


## 18. What this definition does not cover

Encryption and permissions; repair of damaged cross-references; DCT, JPX, CCITT and JBIG2
image data; everything about what content operators DO (graphics state, paths, colour,
shading, patterns, images, transparency, text rendering); character encodings, CMaps,
`ToUnicode` and text extraction; font programs; annotations, forms, XFA, JavaScript, actions;
structure trees and accessibility; digital signatures; embedded files, multimedia, 3D;
optional content; linearization hints; PDF/A, PDF/X, PDF/UA conformance.

## 19. Change notes

* Version 1 (2026-10-13). Fixed before release:
  1. found by comparing with qpdf — the draft let an `/XRefStm` entry replace ANY free
     entry, also one from a newer section; §6.3 now gives the order of lookup of ISO 32000
     (table, its `/XRefStm`, then `/Prev`) and confines the leniency to the same section;
  2. found by comparing with qpdf — the expected title of vector `syntax` was typed with the
     Windows-1252 positions of the curly quotes; PDFDocEncoding has them at 8D and 8E (the
     table of §11 and the reference reader were right; the expectation was wrong);
  3. found by comparing with pdfcraft — the draft DROPPED a partial final predictor row and
     accepted a page dictionary written directly in `/Kids`; pdfcraft decodes the partial row
     as far as it goes and skips a kid that is not a reference, and §8.6 and §9 now say that;
  4. found by writing the second implementation — the text did not say: that a number needs
     at least one digit; that a character other than a hex digit in a hexadecimal string, a
     dictionary key without a value, and a keyword other than `R` inside an array or
     dictionary are errors; that `n g obj endobj` is the null object and a reference back to
     the object being read is null; what a cross-reference stream shorter than its `/Index`
     means; what the final short ASCII85 group yields when its value exceeds 32 bits; how
     RunLength and ASCIIHex data without an end marker end; that operands before `BI` and
     after the last operator are dropped; that filter names are listed in full; that the
     section 15 example's `/Length` was one too large (44; the content is 43 bytes).
