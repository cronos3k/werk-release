# Open Packaging Conventions (OPC) package: parts, content types, relationships — werk format definition `opc`

```werk-format
{
  "format_id": "opc",
  "format_version": 1,
  "title": "Open Packaging Conventions (OPC) package: parts, content types, relationships",
  "media_type": "application/vnd.openxmlformats-package",
  "extensions": [
    "docx",
    "docm",
    "dotx",
    "xlsx",
    "xlsm",
    "xlam",
    "pptx",
    "pptm",
    "xps",
    "vsdx"
  ],
  "sniff": [
    {
      "magic": [
        {
          "offset": 0,
          "hex": "504b0304"
        }
      ]
    }
  ],
  "defines": {
    "decode": true,
    "encode": true
  },
  "coverage": "partial",
  "coverage_note": "Defined completely: how a package maps onto a ZIP archive (format `zip`, which this definition requires); part names and their comparison; the content-type table `[Content_Types].xml` (Default and Override); relationship parts, package-level and part-level, internal and external targets and how a target resolves to a part; the handful of XML rules needed to read those two kinds of file; where the main document, the core properties and a thumbnail are found; writing a package. NOT defined: what the parts CONTAIN - WordprocessingML, SpreadsheetML, PresentationML, DrawingML, VML, the core-properties XML beyond its location - this document delivers every part's bytes, type and relationships; interleaved parts (`[n].piece` items), refused by name; package digital signatures; XML features outside section 5 (DTDs, entity declarations) in the package-level files. This definition has the magic of `zip`: a node NAMES it.",
  "lossy": false,
  "requires": [
    "zip"
  ],
  "normative_sources": [
    "ECMA-376 Part 2 / ISO/IEC 29500-2: Open Packaging Conventions (5th edition, 2021)",
    "RFC 3986 (URI syntax, for part names and targets)"
  ],
  "reference_tools": [
    {
      "tool_id": "format-opc-reference",
      "language": "python",
      "entrypoint": "tools/format-opc-reference/opc_dump.py"
    }
  ],
  "test_vectors": [
    {
      "id": "system-io-packaging",
      "description": "Written by Microsoft's System.IO.Packaging: four parts (one stored, three deflated; one whose name contains a percent-encoded space), a package relationship to the main document, four relationships of that document - relative, absolute, external with `&` in the URL, and one that climbs out of its folder with `..` - and core properties, which the library stores in a part with a generated name and its own package relationship. Note what a part name with `%20` looks like after the listing's own escaping: `%2520`.",
      "input_bytes": 3216,
      "input_sha256": "168a983a6efff4e0b28395981146b71dfe33cfbf857cef1e86e9370e5faf569a",
      "output_form": "the text listing of section 8: `opc parts <n> relationships <n>`, one `part` line per part in archive order with content type, size and SHA-256, then one `rel` line per relationship; UTF-8, LF line ends",
      "output_bytes": 2217,
      "output_sha256": "62fed8a5c56f2a0196f65acced71c950b8a4ed16d20c2f2c87863040ebbd3519"
    },
    {
      "id": "rules",
      "description": "Typed by hand and zipped with Python's zipfile. Content types: a UTF-8 byte order mark, an XML declaration and a comment before the root; a Default whose extension is written in upper case and one whose attributes are in single quotes and in the other order; an Override whose part name differs from the archive's in case; a part with NO content type (`notes.bin`: listed with an empty type). Relationships: element names with a namespace prefix; attributes in any order; a target that leaves its folder with `..`; one with `.`, `..`, an unencoded space and a fragment, which names the part stored as `a%20b.xml`; an absolute target in the wrong case; an external target with `&amp;` and a character reference; a target that names no part (`!missing`); and one that climbs above the root (it stays at the root). The folder entry `media/` is not a part.",
      "input_bytes": 1755,
      "input_sha256": "f9b2063ebf4be20995e4fd3a66fbbb9fc513129ed30c23806647af719744569e",
      "output_form": "the text listing of section 8: `opc parts <n> relationships <n>`, one `part` line per part in archive order with content type, size and SHA-256, then one `rel` line per relationship; UTF-8, LF line ends",
      "output_bytes": 1811,
      "output_sha256": "a6f50664887111dd0cb7655839cc4da3f7d57295e1ef285ba21f2dbea86e97ab"
    },
    {
      "id": "minimal",
      "description": "The smallest package: a content-type table and one part; no relationships at all (a package need not have any).",
      "input_bytes": 370,
      "input_sha256": "47cf8ff4676431e79da8d12c39b9286c56bd87e35b1c35387f0f83c1f82384b5",
      "output_form": "the text listing of section 8: `opc parts <n> relationships <n>`, one `part` line per part in archive order with content type, size and SHA-256, then one `rel` line per relationship; UTF-8, LF line ends",
      "output_bytes": 139,
      "output_sha256": "8eb9162d639d0688834889847b6a4a744100f1a4bab8848c4f53222a2a091b69"
    }
  ]
}
```

This document is normative and self-contained — together with format definition `zip` for the
archive it lives in (a package that carries this document carries that one too; it is named
in the header's `requires`): with the two you can open an OOXML document or any other Open
Packaging Conventions package, list its parts with their content types, follow its
relationships from the package root to every part, extract any part, and write a package.

## 1. Scope and coverage

`.docx`, `.xlsx`, `.pptx` and their macro-enabled and template variants, `.xps`, `.vsdx` and
many other formats are **OPC packages**: a ZIP archive holding **parts** (the files), a
**content-type table** that says what each part is, and **relationships** that say how parts
refer to each other. Applications never find a part by a fixed path; they start at the
package's relationships and follow them.

Defined: the mapping onto ZIP (§3); part names (§4); the two kinds of XML file a package
reader must parse, and how little XML that takes (§5); content types (§6); relationships and
how a target resolves (§7); writing (§9).

Not defined: the contents of parts — the markup languages of Office documents are formats of
their own. This document delivers each part's bytes, its type, and what it is related to.
Also not defined: interleaved parts (a part split over several ZIP items named
`…/[0].piece`, `…/[1].last.piece`) — refuse by name; package digital signatures.

## 2. Conventions

"The archive" is the ZIP file, read as format `zip` says (central directory; methods 0 and
8). All package-level XML is UTF-8 (or UTF-16 with a byte order mark).

## 3. A package as a ZIP archive

* Every ZIP item whose name does not end in `/` is a part, **except** the item named
  `[Content_Types].xml`, which is the content-type table. (ZIP folder items are ignored.)
* **A part's name is `/` followed by the ZIP item name**, unchanged: item
  `word/document.xml` is part `/word/document.xml`. Item names use `/`, are ASCII, and carry
  characters outside the URI character set percent-encoded (a space is `%20`) — the encoding
  is PART OF the name; it is never decoded.
* A package has exactly one `[Content_Types].xml`.

## 4. Part names

A part name is an absolute path: `/` followed by one or more segments separated by `/`; no
empty segment, no segment ending in a dot. **Part names are compared without regard to ASCII
case** (`/Word/Document.XML` and `/word/document.xml` are the same part), after bringing both
to URI form (§7.2). Two parts whose names are equal under that comparison make a package
invalid.

The **extension** of a part is the text after the last `.` of its last segment (empty if
there is none).

## 5. The XML a package reader needs

The content-type table and the relationship parts are small XML documents. To read them you
need only this:

* skip a byte order mark, the XML declaration `<?xml … ?>` and other processing instructions,
  comments `<!-- … -->`, CDATA sections and end tags `</…>`;
* for every **start tag** `<name attr="value" …>` or `<name … />`: the element name, with a
  namespace prefix (`prefix:`) removed, and its attributes — `name="value"` or `name='value'`,
  separated by white space, in any order, prefix removed;
* in attribute values replace `&amp;` `&lt;` `&gt;` `&quot;` `&apos;` and numeric references
  `&#N;` (decimal) and `&#xN;` (hexadecimal) by their characters;
* a document type declaration (`<!DOCTYPE`) is not allowed in these files: refuse it.

Element nesting, text content and namespace declarations do not matter for these two files.

## 6. Content types: `[Content_Types].xml`

```
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml"  ContentType="application/xml"/>
  <Override PartName="/word/document.xml"
            ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
```

The content type (a media type) of a part is:

1. the `ContentType` of the `Override` element whose `PartName` equals the part's name
   (compared as §4 says); else
2. the `ContentType` of the `Default` element whose `Extension` equals the part's extension,
   compared without regard to ASCII case; else
3. none. (A conformant package gives every part a type; a reader reports a part without one
   and still delivers it.)

The content type, not the file name, says what a part is. The main ones of Office documents:

| content type ends with | the part is |
|---|---|
| `wordprocessingml.document.main+xml` | the body of a `.docx` |
| `spreadsheetml.sheet.main+xml` | the workbook of an `.xlsx` |
| `presentationml.presentation.main+xml` | the presentation of a `.pptx` |
| `vnd.ms-word.document.macroEnabled.main+xml`, `vnd.ms-excel.sheet.macroEnabled.main+xml`, `…addin.macroEnabled.main+xml` | the same with macros |
| `vnd.ms-office.vbaProject` | a VBA project (format `ovba`) |
| `vnd.openxmlformats-package.core-properties+xml` | title, author, dates |
| `vnd.openxmlformats-package.relationships+xml` | a relationship part (§7) |

## 7. Relationships

### 7.1 Relationship parts

Relationships are stored in parts with the extension `.rels`, in a folder named `_rels`:

| relationship part | holds the relationships of |
|---|---|
| `/_rels/.rels` | the **package** itself (source `/`) |
| `/<folder>/_rels/<name>.rels` | the part `/<folder>/<name>` (e.g. `/word/_rels/document.xml.rels` → `/word/document.xml`) |

(Only `/_rels/.rels` belongs to the package. An item named exactly `.rels` in a `_rels` folder
below the root follows the second row with an empty `<name>`: its source is `/<folder>/`.)

```
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
      Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
      Target="word/document.xml"/>
  <Relationship Id="rId2" Type="…/hyperlink" Target="https://example.org/" TargetMode="External"/>
</Relationships>
```

Each `Relationship` has:

* `Id` — unique within its relationship part; the source part's own markup refers to the
  relationship by this id (`r:id="rId5"`);
* `Type` — a URI naming what the relationship means; compare it as an exact string;
* `Target` — where it points;
* `TargetMode` — `External`: the target is a resource outside the package (a URL, a file
  path) and is not resolved; `Internal` or absent: the target names a part.

### 7.2 Resolving an internal target

```
1. cut the target at the first `#` or `?` (a fragment or query is not part of the part name)
2. if it starts with `/`:  the base is the root, and the rest is the path
   else:                   the base is the SOURCE PART's folder (for source /word/document.xml: /word/;
                           for the package, source /: the root), and the target is the path
3. go through the path's segments (split at `/`):
     empty or `.`   skip
     `..`           remove the last segment of what has been built (at the root: nothing happens)
     anything else  append
4. the part name is `/` + the segments joined by `/`
5. the part it names is the part whose name equals it, compared as section 4 says
```

**URI form** (used in every comparison of part names): each character that a URI may not
contain literally — space, control characters, non-ASCII characters (as their UTF-8 bytes),
and `"` `<` `>` `\` `^` `` ` `` `{` `|` `}` — is replaced by `%` and two uppercase
hexadecimal digits; nothing is ever decoded. So the target `a b.xml` names the part stored as
`a%20b.xml`.

A target that names no part is reported; the rest of the package is unaffected.

### 7.3 Where things are

Start at the package relationships (`/_rels/.rels`) and select by `Type`:

| Type | target |
|---|---|
| `http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument` (strict packages: `http://purl.oclc.org/ooxml/officeDocument/relationships/officeDocument`) | the main part |
| `http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties` | core properties |
| `http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties` | application properties |
| `http://schemas.openxmlformats.org/package/2006/relationships/metadata/thumbnail` | a preview picture |

Then follow the main part's relationships (styles, images, worksheets, slides, the VBA project
`…/office/2006/relationships/vbaProject`, …), and theirs. A part no relationship reaches is
still in the package; an application that preserves a document keeps it.

## 8. The canonical decoded form

A reader built from this document is checked on this exact text: UTF-8, each line ended by one
`0A` byte, items separated by single spaces.

```
opc parts <number of parts> relationships <number of relationships>
part <ESC(part name)> type <ESC(content type)> size <bytes> sha256 <SHA-256 of the part's bytes, lowercase hex>
rel <ESC(source)> <ESC(Id)> <ESC(Type)> <internal|external> <ESC(Target as written, after entity replacement)> <resolved>
```

* `part` lines: one per part, in the order of the ZIP central directory. Relationship parts
  are parts and are listed. A part without content type has the type `%`.
* `rel` lines: after all `part` lines; for each relationship part in that same order, its
  `Relationship` elements in document order. `<source>` is `/` for the package, else the
  source part's name as derived in §7.1. `<resolved>` is `-` for an external relationship;
  for an internal one, `ESC` of the NAME OF THE PART FOUND (as stored, not as written in the
  target), or `!missing` if §7.2 finds none.
* `ESC(text)`: encode as UTF-8 and write each byte `21`–`7E` except `25` (`%`) as that ASCII
  character, every other byte as `%` and two uppercase hexadecimal digits; empty text is a
  single `%`. (A part name containing `%20` is therefore printed with `%2520`.)

## 9. Writing a package

1. Choose part names (ASCII; percent-encode anything else) and give every part a content
   type: a `Default` per extension, an `Override` where a part differs.
2. Always include `<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>`.
3. Write `/_rels/.rels` with at least the relationship to the main part, and a `.rels` part
   beside every part that refers to others. Use relative targets; ids `rId1`, `rId2`, ….
4. ZIP it (format `zip` §10): `[Content_Types].xml` first by convention, items stored or
   deflated, no encryption, no data descriptors if avoidable, names without a leading `/`.

## 10. Errors a reader must report rather than guess through

Everything format `zip` reports; no `[Content_Types].xml`, or more than one; an interleaved
part (`.piece` item under a folder whose name starts with `[`); two parts with the same name
under the comparison of §4; XML that breaks the rules of §5 (an unclosed tag, comment or
value; an undefined entity; a document type declaration); a `Relationship` without `Id`,
`Type` or `Target`. (A part without content type and a target that names no part are
reported in the listing and are not errors.)

## 11. Test vectors

One input was written by Microsoft's own OPC implementation (System.IO.Packaging); the lines
for the parts and relationships it was asked to write are required in the output. Two were
typed by hand and zipped with Python's zipfile module; their complete expected listing was
written out by hand.

**Independent check (measured).** Every vector and five real packages were also opened with
System.IO.Packaging, which shares no code with the reference reader, and the parts (name,
content type, size) and relationships (source, id, type, mode, target) were compared as sets
(`formats/tools/compare_opc_packaging.py`): identical on `system-io-packaging`, on `minimal`,
and on the five Excel add-ins shipped with Microsoft Office 2016 (20 to 124 parts and
relationships each). On `rules` everything is identical — the case-insensitive Override, the
upper-case Default, the unencoded space in a target, the `..` above the root, the
entity-encoded external target — except one thing: System.IO.Packaging does not list the part
that has no content type, which this document lists with an empty type (§6, §8).

A first draft of this document percent-DECODED part names. System.IO.Packaging showed that to
be wrong (it names the part `/custom/My%20Data.xml`, as stored); §3 and §7.2 now say that a
name is never decoded.

**Second implementation (measured).** The reader — ZIP layer included — was written a second
time, in JavaScript, from this document and `zip.md` alone (`formats/tools/second/opc.js` in
the craft-werk source tree; inflation by Node's zlib): it reproduces the stated output hash of
all 3 vectors, and its output is byte-identical to the reference reader's on the five real
Office packages (listings of 3.8 to 28.8 KB, which include the SHA-256 of every part).

Every input below is given in full as a `hex <id>` block; its sha256 and the sha256 of the decoded output (in the stated output form) are in the header at the top of this document. An implementation is checked by decoding each input and comparing the hash of its output.

### Vector `system-io-packaging`

Written by Microsoft's System.IO.Packaging: four parts (one stored, three deflated; one whose name contains a percent-encoded space), a package relationship to the main document, four relationships of that document - relative, absolute, external with `&` in the URL, and one that climbs out of its folder with `..` - and core properties, which the library stores in a part with a generated name and its own package relationship. Note what a part name with `%20` looks like after the listing's own escaping: `%2520`.

* input: 3216 bytes, sha256 `168a983a6efff4e0b28395981146b71dfe33cfbf857cef1e86e9370e5faf569a`
* output form: the text listing of section 8: `opc parts <n> relationships <n>`, one `part` line per part in archive order with content type, size and SHA-256, then one `rel` line per relationship; UTF-8, LF line ends
* output: 2217 bytes, sha256 `62fed8a5c56f2a0196f65acced71c950b8a4ed16d20c2f2c87863040ebbd3519`
* checked when this document was built: the reference decoder's output contains the 9 lines assembled from the values the input was encoded from (the other lines - offsets the encoder chose - are what the reference computes)

The output, for orientation:

```
opc parts 7 relationships 6
part /word/document.xml type application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml size 50 sha256 f2ec97c4ece2e5ef47ead00f26deec44b9b6104a24195878769f165e5438bf20
part /word/media/image1.png type image/png size 8 sha256 cc1cdcbcf0bdb70801a2f0777e9f9c85571461df7f96d1d3f1476f420df37e38
part /word/styles.xml type application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml size 27 sha256 def9b03be9515473b53b9945abaa8b0f820fc138be6cdc7c05ef35a67fe1367e
part /custom/My%2520Data.xml type application/xml size 7 sha256 03ee9d54665eba6fffaf320018f2543f589ed601bf03b3088ee1e0e3f5a2e2f8
part /_rels/.rels type application/vnd.openxmlformats-package.relationships+xml size 509 sha256 83671d4d712e34536ce52f42ecf8ddcd690a4a56e9ef6dc1fa603d2040a06f9d
part /word/_rels/document.xml.rels type application/vnd.openxmlformats-package.relationships+xml size 688 sha256 0b76fef824b9a1db29f3b8dd6d99ca2fdd81a02a8561374a08fd3d547a62f13f
part /package/services/metadata/core-properties/26c7858a5a194913a47fb85475bf19ae.psmdcp type application/vnd.openxmlformats-package.core-properties+xml size 367 sha256 99 ...
rel / rId1 http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument internal /word/document.xml /word/document.xml
rel / R13dee429e2a6496f http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties internal /package/services/metadata/core-properties/26c7858a ...
rel /word/document.xml rId1 http://schemas.openxmlformats.org/officeDocument/2006/relationships/image internal media/image1.png /word/media/image1.png
rel /word/document.xml rId2 http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles internal /word/styles.xml /word/styles.xml
rel /word/document.xml rId3 http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink external https://example.org/a?b=1&c=2 -
rel /word/document.xml rId4 http://example.org/relationships/data internal ../custom/My%2520Data.xml /custom/My%2520Data.xml
```

```hex system-io-packaging
504b03041400000008006c0d4d5dec70cb442c0000003200000011001c00776f
72642f646f63756d656e742e786d6c20a2180028a01400000000000000000000
0000000000000000000000b329b74ac94f2ecd4dcd2b51a8c8cdc92bb62ab755
2f2dcab3aa50b7b329b74aca4fa9d4b7b3d147a8b20300504b03040a00000000
006c0d4d5dbb637a42080000000800000015001c00776f72642f6d656469612f
696d616765312e706e6720a2180028a014000000000000000000000000000000
00000000000089504e4701020304504b03041400000008006c0d4d5d7dc0f5fd
1d0000001b0000000f001c00776f72642f7374796c65732e786d6c20a2180028
a014000000000000000000000000000000000000000000b329b72a2ea9cc492d
56a8c8cdc92bb62ab7552f2dcab3aa50d7b70300504b03041400000008006c0d
4d5df3b0adbb090000000700000014001c00637573746f6d2f4d792532304461
74612e786d6c20a2180028a01400000000000000000000000000000000000000
0000b349492c49d4b70300504b03040a00000000006c0d4d5dbbfa7383fd0100
00fd0100000b001c005f72656c732f2e72656c7320a2180028a0140000000000
00000000000000000000000000000000efbbbf3c3f786d6c2076657273696f6e
3d22312e302220656e636f64696e673d227574662d38223f3e3c52656c617469
6f6e736869707320786d6c6e733d22687474703a2f2f736368656d61732e6f70
656e786d6c666f726d6174732e6f72672f7061636b6167652f323030362f7265
6c6174696f6e7368697073223e3c52656c6174696f6e7368697020547970653d
22687474703a2f2f736368656d61732e6f70656e786d6c666f726d6174732e6f
72672f6f6666696365446f63756d656e742f323030362f72656c6174696f6e73
686970732f6f6666696365446f63756d656e7422205461726765743d222f776f
72642f646f63756d656e742e786d6c222049643d227249643122202f3e3c5265
6c6174696f6e7368697020547970653d22687474703a2f2f736368656d61732e
6f70656e786d6c666f726d6174732e6f72672f7061636b6167652f323030362f
72656c6174696f6e73686970732f6d657461646174612f636f72652d70726f70
65727469657322205461726765743d222f7061636b6167652f73657276696365
732f6d657461646174612f636f72652d70726f706572746965732f3236633738
3538613561313934393133613437666238353437356266313961652e70736d64
6370222049643d22523133646565343239653261363439366622202f3e3c2f52
656c6174696f6e73686970733e504b03041400000008006c0d4d5d348244e40d
010000b00200001c001c00776f72642f5f72656c732f646f63756d656e742e78
6d6c2e72656c7320a2180028a014000000000000000000000000000000000000
000000b5924b4ec3301040af6259821d7612104250379bb2e8a21bd40b0cf624
b11a7f643bd09c8d0547e20a98f2492321c1a6cbf9bd791acddbcbeba2de9b9e
3c6188da59414b565082563aa56d2be8909a8b1b5a2f170fd843ca1db1d33e92
3c62a3a05d4afe96f3283b341099f36873a571c140ca6168b907b98316795514
d73c1c33e89c49b6a3c7ff105dd368892b27078336fd02e6dae48d946c21b498
0435a8347c264be66d4bc95a091ad6aaa4849f4c22a6b1c73859f06717d45796
65da8f45754a8b2e9342afed6e12f9c0c6ccc53d18dfe30104f5a328cf737c27
45f5ddba712a5bdcef13060b93efe51fbec7dcb98c82049307635c0e3139c337
e35955ac72717697abc31e3efbbbe53b504b03040a00000000006c0d4d5d9ce8
af916f0100006f01000051001c007061636b6167652f73657276696365732f6d
657461646174612f636f72652d70726f706572746965732f3236633738353861
3561313934393133613437666238353437356266313961652e70736d64637020
a2180028a014000000000000000000000000000000000000000000efbbbf3c3f
786d6c2076657273696f6e3d22312e302220656e636f64696e673d227574662d
38223f3e3c636f726550726f7065727469657320786d6c6e733a64633d226874
74703a2f2f7075726c2e6f72672f64632f656c656d656e74732f312e312f2220
786d6c6e733a64637465726d733d22687474703a2f2f7075726c2e6f72672f64
632f7465726d732f2220786d6c6e733a7873693d22687474703a2f2f7777772e
77332e6f72672f323030312f584d4c536368656d612d696e7374616e63652220
786d6c6e733d22687474703a2f2f736368656d61732e6f70656e786d6c666f72
6d6174732e6f72672f7061636b6167652f323030362f6d657461646174612f63
6f72652d70726f70657274696573223e3c64633a7469746c653e7765726b2074
657374207061636b6167653c2f64633a7469746c653e3c64633a63726561746f
723e63726166742d7765726b3c2f64633a63726561746f723e3c2f636f726550
726f706572746965733e504b03040a00000000006c0d4d5d7356cb60bf020000
bf02000013001c005b436f6e74656e745f54797065735d2e786d6c20a2180028
a014000000000000000000000000000000000000000000efbbbf3c3f786d6c20
76657273696f6e3d22312e302220656e636f64696e673d227574662d38223f3e
3c547970657320786d6c6e733d22687474703a2f2f736368656d61732e6f7065
6e786d6c666f726d6174732e6f72672f7061636b6167652f323030362f636f6e
74656e742d7479706573223e3c44656661756c7420457874656e73696f6e3d22
786d6c2220436f6e74656e74547970653d226170706c69636174696f6e2f766e
642e6f70656e786d6c666f726d6174732d6f6666696365646f63756d656e742e
776f726470726f63657373696e676d6c2e646f63756d656e742e6d61696e2b78
6d6c22202f3e3c44656661756c7420457874656e73696f6e3d22706e67222043
6f6e74656e74547970653d22696d6167652f706e6722202f3e3c44656661756c
7420457874656e73696f6e3d2272656c732220436f6e74656e74547970653d22
6170706c69636174696f6e2f766e642e6f70656e786d6c666f726d6174732d70
61636b6167652e72656c6174696f6e73686970732b786d6c22202f3e3c446566
61756c7420457874656e73696f6e3d2270736d6463702220436f6e74656e7454
7970653d226170706c69636174696f6e2f766e642e6f70656e786d6c666f726d
6174732d7061636b6167652e636f72652d70726f706572746965732b786d6c22
202f3e3c4f7665727269646520506172744e616d653d222f776f72642f737479
6c65732e786d6c2220436f6e74656e74547970653d226170706c69636174696f
6e2f766e642e6f70656e786d6c666f726d6174732d6f6666696365646f63756d
656e742e776f726470726f63657373696e676d6c2e7374796c65732b786d6c22
202f3e3c4f7665727269646520506172744e616d653d222f637573746f6d2f4d
79253230446174612e786d6c2220436f6e74656e74547970653d226170706c69
636174696f6e2f786d6c22202f3e3c2f54797065733e504b01022d0014000000
08006c0d4d5dec70cb442c000000320000001100000000000000000000000000
00000000776f72642f646f63756d656e742e786d6c504b01022d000a00000000
006c0d4d5dbb637a420800000008000000150000000000000000000000000077
000000776f72642f6d656469612f696d616765312e706e67504b01022d001400
000008006c0d4d5d7dc0f5fd1d0000001b0000000f0000000000000000000000
0000ce000000776f72642f7374796c65732e786d6c504b01022d001400000008
006c0d4d5df3b0adbb0900000007000000140000000000000000000000000034
010000637573746f6d2f4d79253230446174612e786d6c504b01022d000a0000
0000006c0d4d5dbbfa7383fd010000fd0100000b000000000000000000000000
008b0100005f72656c732f2e72656c73504b01022d001400000008006c0d4d5d
348244e40d010000b00200001c00000000000000000000000000cd030000776f
72642f5f72656c732f646f63756d656e742e786d6c2e72656c73504b01022d00
0a00000000006c0d4d5d9ce8af916f0100006f01000051000000000000000000
00000000300500007061636b6167652f73657276696365732f6d657461646174
612f636f72652d70726f706572746965732f3236633738353861356131393439
3133613437666238353437356266313961652e70736d646370504b01022d000a
00000000006c0d4d5d7356cb60bf020000bf0200001300000000000000000000
0000002a0700005b436f6e74656e745f54797065735d2e786d6c504b05060000
00000800080044020000360a00000000
```

### Vector `rules`

Typed by hand and zipped with Python's zipfile. Content types: a UTF-8 byte order mark, an XML declaration and a comment before the root; a Default whose extension is written in upper case and one whose attributes are in single quotes and in the other order; an Override whose part name differs from the archive's in case; a part with NO content type (`notes.bin`: listed with an empty type). Relationships: element names with a namespace prefix; attributes in any order; a target that leaves its folder with `..`; one with `.`, `..`, an unencoded space and a fragment, which names the part stored as `a%20b.xml`; an absolute target in the wrong case; an external target with `&amp;` and a character reference; a target that names no part (`!missing`); and one that climbs above the root (it stays at the root). The folder entry `media/` is not a part.

* input: 1755 bytes, sha256 `f9b2063ebf4be20995e4fd3a66fbbb9fc513129ed30c23806647af719744569e`
* output form: the text listing of section 8: `opc parts <n> relationships <n>`, one `part` line per part in archive order with content type, size and SHA-256, then one `rel` line per relationship; UTF-8, LF line ends
* output: 1811 bytes, sha256 `a6f50664887111dd0cb7655839cc4da3f7d57295e1ef285ba21f2dbea86e97ab`
* checked when this document was built: the reference decoder's output equals the bytes the input was encoded from

The output, for orientation:

```
opc parts 7 relationships 8
part /_rels/.rels type application/vnd.openxmlformats-package.relationships+xml size 362 sha256 e28e6c9e6cada81f5033acae4db49edcefbefb7604b31e87259c8f686db6eca8
part /word/document.xml type application/vnd.test.main+xml size 6 sha256 630890f1ac4752b019e13c1f559d9f8f8e4be89e9f74f43dde4da95843030219
part /word/_rels/document.xml.rels type application/vnd.openxmlformats-package.relationships+xml size 657 sha256 76f25627d84b8d2bdfb1203b63b1b9a02aef0b89b855380bf06af5035d622ad4
part /word/a%2520b.xml type application/vnd.test.spaced+xml size 5 sha256 35a2e14755e2ae72f72318d5ace6b1323b7392dadd7280c063f789ec08e419cd
part /word/notes.bin type % size 3 sha256 ae4b3280e56e2faf83f414a6e3dabe9d5fbe18976544c05fed121accb85b53fc
part /media/picture.png type image/png size 8 sha256 0eeb93c105541e8910effe271bf99ecfe4fd4f02c031241f7be1c66c648414f5
part /docProps/thumbnail.PNG type image/png size 4 sha256 0f4636c78f65d3639ece5a064b5ae753e3408614a14fb18ab4d7540d2c248543
rel / rId1 http://example.org/rel/main internal word/document.xml /word/document.xml
rel / rId2 http://schemas.openxmlformats.org/package/2006/relationships/metadata/thumbnail internal docProps/thumbnail.PNG /docProps/thumbnail.PNG
rel /word/document.xml a http://example.org/rel/image internal ../media/picture.png /media/picture.png
rel /word/document.xml b http://example.org/rel/part internal ./sub/../a%20b.xml#anchor /word/a%2520b.xml
rel /word/document.xml c http://example.org/rel/part internal /WORD/NOTES.BIN /word/notes.bin
rel /word/document.xml d http://example.org/rel/link external https://example.org/?x=1&y=A -
rel /word/document.xml e http://example.org/rel/part internal missing.xml !missing
rel /word/document.xml f http://example.org/rel/part internal ../../../media/picture.png /media/picture.png
```

```hex rules
504b0304140000000800ef494d5d02238d5b250100001d020000130000005b43
6f6e74656e745f54797065735d2e786d6c8d914b4ec3301086f748dcc158425d
20c7a10b8450922e68599587a008b643324d2ce2876cb7b46763c191b80276da
8aa8aa043bcfcc3fdf3f33fefefcca462bd992255a27b4cae979925282aad495
50754e9f6737ec9212e74155d06a85395da3a3a3e2f8283b618c945a79549ef8
b54147188bf959f70e54e572da786fae38776583125ca20daa50996b2bc187d0
d6dc40f90e35f2619a5ef02d8f753c5a64639cc3a2f564b20ae9cd848f93e913
25d71b61f4ca2918d38a127ca8f3a5aaf65cd8d621b1d8761ad708e3ce8280f2
5f873e70d00706dda0e73f88313f389951f5de6042c6cd623e74dc87235b5121
7900ebef40863a7fd1b6e2635d2e64e8495e6fa77f6ce6d1f9448250bbf10f41
3f22144e87e95b1255ff20ba7022ac764cdefd60f103504b0304140000000800
ef494d5d12887069bb0000006a0100000b0000005f72656c732f2e72656c739d
90390ec2400c45af12f90071a0a0880894880645880b988c4922328b3c66bb3d
03128b424769fbe97ddbf3e5d50ed99925f6de5530c90b582ee6526e79204dad
d8f521668971b1940a3ad55022c6a6634b31f7815d9a1dbc58d2544a8b819a23
b58cd3a298a17c5b60eccdd6a602599b0964bb5be0b79daf64c3c04f5d32a0a5
de2584a465ade0e2c5a0f1cdc9b2d33ca503fe885f6cc26af121a27627bb77d4
0f79bd59c12b783a0afeeb2cb4ac6448e913f2d808473f5cdc01504b03041400
00000800ef494d5d12006154080000000600000011000000776f72642f646f63
756d656e742e786d6cb349c94fd6b70300504b0304140000000800ef494d5d46
9e8e9cf5000000910200001c000000776f72642f5f72656c732f646f63756d65
6e742e786d6c2e72656c7395d24d6b02311006e0bfb244f098d1527aa8ae8552
0f1eaa60859e6777c76c305f2411e2bf6f6c69bb2d0159c865c89b27cc24cb3d
298cd29ad04b17aaa4950935eb63748f00a1ed4963e0d691c93b47eb35c65c7a
010edb130a82bbd9ec01fcd060abe5d0ac365dcd9055878ba31f98126aa7e853
ca8741ea6ce50c7a41b1669c83a64e2238d9c6b327ee8c6050709b1bae431f07
2c84730319c7aae1b99f099ab6b7be28b7a36478dfed5f60bb3bacdff8f3665b
14bb1ba292e6f42b5e43e15fea29d5f3692e17977a3a49f7f3c577fcd576d95d
a748dea02ade4ea3fad1320469c4754845ed386eee1cbe56f151e1cf0f5c7d00
504b0304140000000000ef494d5d740847b905000000050000000e000000776f
72642f61253230622e786d6c3c61622f3e504b0304140000000000ef494d5d7f
89540803000000030000000e000000776f72642f6e6f7465732e62696e000102
504b0304140000000000ef494d5d000000000000000000000000060000006d65
6469612f504b0304140000000000ef494d5d6ef0ed7008000000080000001100
00006d656469612f706963747572652e706e6789504e472e2e2e2e504b030414
0000000000ef494d5da5beeb5b040000000400000016000000646f6350726f70
732f7468756d626e61696c2e504e4789504e47504b01021400140000000800ef
494d5d02238d5b250100001d0200001300000000000000000000008001000000
005b436f6e74656e745f54797065735d2e786d6c504b01021400140000000800
ef494d5d12887069bb0000006a0100000b000000000000000000000080015601
00005f72656c732f2e72656c73504b01021400140000000800ef494d5d120061
54080000000600000011000000000000000000000080013a020000776f72642f
646f63756d656e742e786d6c504b01021400140000000800ef494d5d469e8e9c
f5000000910200001c0000000000000000000000800171020000776f72642f5f
72656c732f646f63756d656e742e786d6c2e72656c73504b0102140014000000
0000ef494d5d740847b905000000050000000e00000000000000000000008001
a0030000776f72642f61253230622e786d6c504b01021400140000000000ef49
4d5d7f89540803000000030000000e00000000000000000000008001d1030000
776f72642f6e6f7465732e62696e504b01021400140000000000ef494d5d0000
000000000000000000000600000000000000000000008001000400006d656469
612f504b01021400140000000000ef494d5d6ef0ed7008000000080000001100
000000000000000000008001240400006d656469612f706963747572652e706e
67504b01021400140000000000ef494d5da5beeb5b0400000004000000160000
00000000000000000080015b040000646f6350726f70732f7468756d626e6169
6c2e504e47504b0506000000000900090032020000930400000000
```

### Vector `minimal`

The smallest package: a content-type table and one part; no relationships at all (a package need not have any).

* input: 370 bytes, sha256 `47cf8ff4676431e79da8d12c39b9286c56bd87e35b1c35387f0f83c1f82384b5`
* output form: the text listing of section 8: `opc parts <n> relationships <n>`, one `part` line per part in archive order with content type, size and SHA-256, then one `rel` line per relationship; UTF-8, LF line ends
* output: 139 bytes, sha256 `8eb9162d639d0688834889847b6a4a744100f1a4bab8848c4f53222a2a091b69`
* checked when this document was built: the reference decoder's output equals the bytes the input was encoded from

The output, for orientation:

```
opc parts 1 relationships 0
part /hello.txt type text/plain size 5 sha256 2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824
```

```hex minimal
504b0304140000000000ef494d5d0dddad2d8700000087000000130000005b43
6f6e74656e745f54797065735d2e786d6c3c547970657320786d6c6e733d2268
7474703a2f2f736368656d61732e6f70656e786d6c666f726d6174732e6f7267
2f7061636b6167652f323030362f636f6e74656e742d7479706573223e3c4465
6661756c7420457874656e73696f6e3d227478742220436f6e74656e74547970
653d22746578742f706c61696e222f3e3c2f54797065733e504b030414000000
0000ef494d5d86a6103605000000050000000900000068656c6c6f2e74787468
656c6c6f504b01021400140000000000ef494d5d0dddad2d8700000087000000
1300000000000000000000008001000000005b436f6e74656e745f5479706573
5d2e786d6c504b01021400140000000000ef494d5d86a6103605000000050000
000900000000000000000000008001b800000068656c6c6f2e747874504b0506
000000000200020078000000e40000000000
```


## 12. What this definition does not cover

The markup inside parts (WordprocessingML, SpreadsheetML, PresentationML, DrawingML, VML,
custom XML, core and extended properties); interleaved parts; digital signatures
(`/_xmlsignatures`); the physical growth-hint and ZIP-level rules beyond what `zip` defines;
ODF packages (a different convention: see `odf`), EPUB (`epub`) and IDML (`idml`), which are
ZIP archives but not OPC packages.

## 13. Change notes

* Version 1 (2026-10-13). Fixed before release: (1) found by comparing with
  System.IO.Packaging — part names are not percent-decoded (the draft decoded them, which
  also broke the Override lookup for such a part); the URI form of §7.2 replaces decoding;
  (2) found by writing the second implementation — §7.1 did not say what the source of a
  `.rels` item named exactly `.rels` in a folder below the root is; it now does.
