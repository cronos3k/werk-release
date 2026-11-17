#!/usr/bin/env python3
"""opc_dump.py - reference reader for werk format definition `opc`.

Implements spec/formats/opc.md from scratch: an Open Packaging Conventions package - the
container of OOXML documents (.docx, .xlsx, .pptx and their macro-enabled and template
variants), XPS and others - as a ZIP archive (format definition `zip`; its reader is repeated
in this file) holding PARTS, a content-type table ([Content_Types].xml) and RELATIONSHIPS
(.rels parts). It lists every part with its content type and every relationship with its
resolved target.

    python opc_dump.py <package>  >  <listing>
    python opc_dump.py <package> --part </part/name>  >  <that part's bytes>

Output (the definition's canonical form, section 8): UTF-8 text, each line ended by LF.

NOT implemented, as the definition states: what the parts contain (WordprocessingML,
SpreadsheetML, ...); interleaved parts ([n].piece entries), which are refused by name;
digital signatures; the XML of the two package-level files is read with the small scanner of
section 5, not with a general XML parser (no DTD, no entity declarations).

Python >= 3.8, standard library only (hashlib for SHA-256). Source only; never run
automatically by any werk tool.
"""

import hashlib
import sys


# ---------------------------------------------------------------------------------------------
# the ZIP layer (format definition `zip`)

class FormatError(Exception):
    pass


LENGTH_BASE = [3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31,
               35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258]
LENGTH_EXTRA = [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2,
                3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0]
DIST_BASE = [1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769,
             1025, 1537, 2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577]
DIST_EXTRA = [0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8,
              9, 9, 10, 10, 11, 11, 12, 12, 13, 13]
CODE_LENGTH_ORDER = [16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15]


class Bits:
    def __init__(self, data):
        self.data, self.pos, self.buf, self.cnt = data, 0, 0, 0

    def get(self, n):
        while self.cnt < n:
            if self.pos >= len(self.data):
                raise FormatError("the DEFLATE stream ends early")
            self.buf |= self.data[self.pos] << self.cnt
            self.pos += 1
            self.cnt += 8
        v = self.buf & ((1 << n) - 1)
        self.buf >>= n
        self.cnt -= n
        return v


def huffman(lengths):
    count = [0] * 16
    for n in lengths:
        count[n] += 1
    count[0] = 0
    code = 0
    next_code = [0] * 16
    for n in range(1, 16):
        code = (code + count[n - 1]) << 1
        next_code[n] = code
    table = {}
    for symbol, n in enumerate(lengths):
        if n:
            table[(n, next_code[n])] = symbol
            next_code[n] += 1
    return table


def symbol(bits, table):
    code = 0
    for n in range(1, 16):
        code = (code << 1) | bits.get(1)
        if (n, code) in table:
            return table[(n, code)]
    raise FormatError("a Huffman code in the DEFLATE stream matches no symbol")


def inflate_raw(data):
    """A raw DEFLATE stream (RFC 1951): no zlib header, no checksum."""
    bits = Bits(data)
    out = bytearray()
    while True:
        final, kind = bits.get(1), bits.get(2)
        if kind == 0:
            bits.buf = bits.cnt = 0
            if bits.pos + 4 > len(data):
                raise FormatError("the DEFLATE stream ends early")
            n = data[bits.pos] | (data[bits.pos + 1] << 8)
            if n ^ 0xFFFF != data[bits.pos + 2] | (data[bits.pos + 3] << 8):
                raise FormatError("stored block: LEN and NLEN disagree")
            if bits.pos + 4 + n > len(data):
                raise FormatError("the DEFLATE stream ends early")
            out += data[bits.pos + 4:bits.pos + 4 + n]
            bits.pos += 4 + n
        elif kind in (1, 2):
            if kind == 1:
                lit = huffman([8] * 144 + [9] * 112 + [7] * 24 + [8] * 8)
                dist = huffman([5] * 30)
            else:
                hlit, hdist, hclen = bits.get(5) + 257, bits.get(5) + 1, bits.get(4) + 4
                cl = [0] * 19
                for i in range(hclen):
                    cl[CODE_LENGTH_ORDER[i]] = bits.get(3)
                cl_table = huffman(cl)
                lengths = []
                while len(lengths) < hlit + hdist:
                    s = symbol(bits, cl_table)
                    if s < 16:
                        lengths.append(s)
                    elif s == 16:
                        if not lengths:
                            raise FormatError("code length repeat with nothing to repeat")
                        lengths += [lengths[-1]] * (3 + bits.get(2))
                    elif s == 17:
                        lengths += [0] * (3 + bits.get(3))
                    else:
                        lengths += [0] * (11 + bits.get(7))
                if len(lengths) != hlit + hdist:
                    raise FormatError("code lengths overrun")
                lit, dist = huffman(lengths[:hlit]), huffman(lengths[hlit:])
            while True:
                s = symbol(bits, lit)
                if s < 256:
                    out.append(s)
                elif s == 256:
                    break
                elif s > 285:
                    raise FormatError("invalid length symbol")
                else:
                    length = LENGTH_BASE[s - 257] + bits.get(LENGTH_EXTRA[s - 257])
                    d = symbol(bits, dist)
                    if d > 29:
                        raise FormatError("invalid distance symbol")
                    distance = DIST_BASE[d] + bits.get(DIST_EXTRA[d])
                    if distance > len(out):
                        raise FormatError("distance reaches before the start of the data")
                    for _ in range(length):
                        out.append(out[-distance])
        else:
            raise FormatError("reserved DEFLATE block type 3")
        if final:
            return bytes(out)


def crc32(data):
    crc = 0xFFFFFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xEDB88320 if crc & 1 else crc >> 1
    return crc ^ 0xFFFFFFFF


CP437 = ("ÇüéâäàåçêëèïîìÄÅ"
         "ÉæÆôöòûùÿÖÜ¢£¥₧ƒ"
         "áíóúñÑªº¿⌐¬½¼¡«»"
         "░▒▓│┤╡╢╖╕╣║╗╝╜╛┐"
         "└┴┬├─┼╞╟╚╔╩╦╠═╬╧"
         "╨╤╥╙╘╒╓╫╪┘┌█▄▌▐▀"
         "αßΓπΣσµτΦΘΩδ∞φε∩"
         "≡±≥≤⌠⌡÷≈°∙·√ⁿ²■ ")


def text_of(raw, utf8):
    """A name or comment as text: UTF-8 if the flag says so, else code page 437."""
    if utf8:
        return raw.decode("utf-8", "replace")
    return "".join(chr(b) if b < 128 else CP437[b - 128] for b in raw)


def esc(text):
    data = text.encode("utf-8")
    if not data:
        return "%"
    return "".join(chr(b) if 0x21 <= b <= 0x7E and b != 0x25 else "%%%02X" % b for b in data)


def u16(d, p):
    return d[p] | (d[p + 1] << 8)


def u32(d, p):
    return int.from_bytes(d[p:p + 4], "little")


def u64(d, p):
    return int.from_bytes(d[p:p + 8], "little")


def read_directory(data):
    """Returns (entries, zip64 flag, comment bytes). An entry is a dict."""
    # the end-of-central-directory record: the LAST occurrence of its signature that fits
    eocd = -1
    p = len(data) - 22
    while p >= 0 and p >= len(data) - 22 - 65535:
        if data[p:p + 4] == b"PK\x05\x06" and p + 22 + u16(data, p + 20) <= len(data):
            eocd = p
            break
        p -= 1
    if eocd < 0:
        raise FormatError("not a ZIP file: no end-of-central-directory record")
    if u16(data, eocd + 4) != 0 or u16(data, eocd + 6) != 0:
        raise FormatError("a multi-disk archive is not defined")
    count, cd_size, cd_offset = u16(data, eocd + 10), u32(data, eocd + 12), u32(data, eocd + 16)
    comment = data[eocd + 22:eocd + 22 + u16(data, eocd + 20)]
    zip64 = 0
    loc = eocd - 20
    if loc >= 0 and data[loc:loc + 4] == b"PK\x06\x07":
        rec = u64(data, loc + 8)
        if data[rec:rec + 4] != b"PK\x06\x06":
            raise FormatError("the ZIP64 locator does not point at a ZIP64 end-of-central-directory record")
        if u32(data, loc + 4) != 0 or u32(data, loc + 16) > 1:
            raise FormatError("a multi-disk archive is not defined")
        zip64 = 1
        count, cd_size, cd_offset = u64(data, rec + 32), u64(data, rec + 40), u64(data, rec + 48)
    if cd_offset + cd_size > len(data):
        raise FormatError("the central directory lies outside the file")
    entries = []
    p = cd_offset
    for _ in range(count):
        if data[p:p + 4] != b"PK\x01\x02" or p + 46 > len(data):
            raise FormatError("a central directory header is missing its signature")
        flags, method, mtime, mdate = u16(data, p + 8), u16(data, p + 10), u16(data, p + 12), u16(data, p + 14)
        crc, packed, size = u32(data, p + 16), u32(data, p + 20), u32(data, p + 24)
        n, m, k = u16(data, p + 28), u16(data, p + 30), u16(data, p + 32)
        disk, offset = u16(data, p + 34), u32(data, p + 42)
        name = data[p + 46:p + 46 + n]
        extra = data[p + 46 + n:p + 46 + n + m]
        if len(name) != n or len(extra) != m:
            raise FormatError("a central directory header runs past the end of the file")
        # extra field blocks
        q = 0
        unicode_name = None
        while q + 4 <= len(extra):
            hid, hsize = u16(extra, q), u16(extra, q + 2)
            block = extra[q + 4:q + 4 + hsize]
            if hid == 0x0001:                                # ZIP64: only the fields whose 32-bit form is FFFFFFFF / FFFF
                r = 0
                if size == 0xFFFFFFFF:
                    size = u64(block, r)
                    r += 8
                if packed == 0xFFFFFFFF:
                    packed = u64(block, r)
                    r += 8
                if offset == 0xFFFFFFFF:
                    offset = u64(block, r)
                    r += 8
                if disk == 0xFFFF:
                    disk = u32(block, r)
            elif hid == 0x7075 and len(block) >= 5 and block[0] == 1 and u32(block, 1) == crc32(name):
                unicode_name = block[5:].decode("utf-8", "replace")
            q += 4 + hsize
        if disk != 0:
            raise FormatError("a multi-disk archive is not defined")
        text = unicode_name if unicode_name is not None else text_of(name, flags & 0x0800)
        entries.append({"name": text, "flags": flags, "method": method, "time": mtime, "date": mdate, "crc": crc,
                        "packed": packed, "size": size, "offset": offset})
        p += 46 + n + m + k
    return entries, zip64, comment


def entry_bytes(data, e):
    """The uncompressed bytes of one entry, CRC-checked."""
    if e["flags"] & 0x0001:
        raise FormatError("entry `%s` is encrypted; encryption is not defined" % e["name"])
    if e["method"] not in (0, 8):
        raise FormatError("entry `%s` uses compression method %d, which is not defined" % (e["name"], e["method"]))
    p = e["offset"]
    if data[p:p + 4] != b"PK\x03\x04" or p + 30 > len(data):
        raise FormatError("entry `%s`: no local file header at its offset" % e["name"])
    start = p + 30 + u16(data, p + 26) + u16(data, p + 28)
    packed = data[start:start + e["packed"]]
    if len(packed) != e["packed"]:
        raise FormatError("entry `%s` runs past the end of the file" % e["name"])
    out = packed if e["method"] == 0 else inflate_raw(packed)
    if len(out) != e["size"]:
        raise FormatError("entry `%s`: %d bytes after decompression, the directory says %d" % (e["name"], len(out), e["size"]))
    if crc32(out) != e["crc"]:
        raise FormatError("entry `%s`: CRC-32 mismatch" % e["name"])
    return out


# ---------------------------------------------------------------------------------------------
# a small XML scanner (section 5): start tags with their attributes, in document order

ENTITIES = {"lt": "<", "gt": ">", "amp": "&", "quot": '"', "apos": "'"}


def unescape(text):
    out = []
    i = 0
    while i < len(text):
        c = text[i]
        if c != "&":
            out.append(c)
            i += 1
            continue
        j = text.find(";", i)
        if j < 0:
            raise FormatError("XML: an entity reference is not terminated")
        name = text[i + 1:j]
        if name.startswith("#x"):
            out.append(chr(int(name[2:], 16)))
        elif name.startswith("#"):
            out.append(chr(int(name[1:])))
        elif name in ENTITIES:
            out.append(ENTITIES[name])
        else:
            raise FormatError("XML: entity &%s; is not predefined (a DTD is not allowed here)" % name)
        i = j + 1
    return "".join(out)


def start_tags(data):
    """Yields (local name, {attribute local name: value}) for every start or empty-element tag."""
    if data[:3] == b"\xef\xbb\xbf":
        data = data[3:]
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        text = data.decode("utf-16")
    else:
        text = data.decode("utf-8")
    i = 0
    while True:
        i = text.find("<", i)
        if i < 0:
            return
        if text.startswith("<!--", i):
            j = text.find("-->", i + 4)
            if j < 0:
                raise FormatError("XML: a comment is not closed")
            i = j + 3
        elif text.startswith("<![CDATA[", i):
            j = text.find("]]>", i + 9)
            if j < 0:
                raise FormatError("XML: a CDATA section is not closed")
            i = j + 3
        elif text.startswith("<?", i):
            j = text.find("?>", i + 2)
            if j < 0:
                raise FormatError("XML: a processing instruction is not closed")
            i = j + 2
        elif text.startswith("<!", i):
            raise FormatError("XML: a document type declaration is not allowed in a package file")
        elif text.startswith("</", i):
            j = text.find(">", i)
            if j < 0:
                raise FormatError("XML: an end tag is not closed")
            i = j + 1
        else:
            # a start tag: name, then attributes name="value" or name='value'
            j = i + 1
            while j < len(text) and text[j] not in " \t\r\n/>":
                j += 1
            name = text[i + 1:j]
            attrs = {}
            while True:
                while j < len(text) and text[j] in " \t\r\n":
                    j += 1
                if j >= len(text):
                    raise FormatError("XML: a start tag is not closed")
                if text[j] == ">":
                    j += 1
                    break
                if text.startswith("/>", j):
                    j += 2
                    break
                k = j
                while k < len(text) and text[k] not in " \t\r\n=":
                    k += 1
                aname = text[j:k]
                while k < len(text) and text[k] in " \t\r\n":
                    k += 1
                if k >= len(text) or text[k] != "=":
                    raise FormatError("XML: attribute `%s` has no value" % aname)
                k += 1
                while k < len(text) and text[k] in " \t\r\n":
                    k += 1
                if k >= len(text) or text[k] not in "\"'":
                    raise FormatError("XML: the value of attribute `%s` is not quoted" % aname)
                end = text.find(text[k], k + 1)
                if end < 0:
                    raise FormatError("XML: the value of attribute `%s` is not closed" % aname)
                attrs[aname.split(":")[-1]] = unescape(text[k + 1:end])
                j = end + 1
            yield name.split(":")[-1], attrs
            i = j


# ---------------------------------------------------------------------------------------------
# the package (sections 3-7)

def to_uri(text):
    """Percent-encode what a URI may not contain literally: space, controls, non-ASCII (as UTF-8), and the
    characters " < > backslash ^ ` { | }."""
    out = []
    for byte in text.encode("utf-8"):
        if byte <= 0x20 or byte >= 0x7F or byte in (0x22, 0x3C, 0x3E, 0x5C, 0x5E, 0x60, 0x7B, 0x7C, 0x7D):
            out.append("%%%02X" % byte)
        else:
            out.append(chr(byte))
    return "".join(out)


def key(part_name):
    """Part names are compared as URIs, without regard to ASCII case."""
    return "".join(chr(ord(c) + 32) if "A" <= c <= "Z" else c for c in to_uri(part_name))


def resolve(source, target):
    """The part name a relationship target names, relative to the part `source` ('/' for the package)."""
    target = target.split("#")[0].split("?")[0]
    if target.startswith("/"):
        segments = []
        rest = target[1:]
    else:
        segments = source.split("/")[1:-1]                    # the source part's folder
        rest = target
    for seg in rest.split("/"):
        if seg == "." or seg == "":
            continue
        if seg == "..":
            if segments:
                segments.pop()
            continue
        segments.append(seg)
    return "/" + "/".join(segments)


def read_package(data):
    """Returns (parts, relationships). parts: list of (name, content type, entry);
    relationships: list of (source, id, type, mode, target, resolved or None)."""
    entries, _, _ = read_directory(data)
    files = []
    for e in entries:
        if e["name"].endswith("/"):
            continue                                          # a folder entry is not a part
        if "/[" in "/" + e["name"] and e["name"].endswith(".piece"):
            raise FormatError("interleaved part `%s`: interleaving is not defined" % e["name"])
        files.append(e)
    types = [e for e in files if e["name"] == "[Content_Types].xml"]
    if len(types) != 1:
        raise FormatError("not an OPC package: there is no (single) [Content_Types].xml")
    defaults, overrides = {}, {}
    for (tag, attrs) in start_tags(entry_bytes(data, types[0])):
        if tag == "Default" and "Extension" in attrs and "ContentType" in attrs:
            defaults[key(attrs["Extension"])] = attrs["ContentType"]
        elif tag == "Override" and "PartName" in attrs and "ContentType" in attrs:
            overrides[key(attrs["PartName"])] = attrs["ContentType"]
    parts = []
    by_key = {}
    for e in files:
        if e["name"] == "[Content_Types].xml":
            continue
        name = "/" + e["name"]
        last = name.rsplit("/", 1)[-1]
        ext = last.rsplit(".", 1)[-1] if "." in last else ""
        ctype = overrides.get(key(name), defaults.get(key(ext), ""))
        parts.append((name, ctype, e))
        if key(name) in by_key:
            raise FormatError("two parts are named `%s` (part names are compared without regard to case)" % name)
        by_key[key(name)] = name
    rels = []
    for (name, _, e) in parts:
        folder, _, last = name.rpartition("/")
        if not (folder.endswith("/_rels") or folder == "/_rels") or not last.endswith(".rels"):
            continue
        owner_folder = folder[:-len("/_rels")]
        source = "/" if last == ".rels" and owner_folder == "" else owner_folder + "/" + last[:-len(".rels")]
        for (tag, attrs) in start_tags(entry_bytes(data, e)):
            if tag != "Relationship":
                continue
            if "Id" not in attrs or "Type" not in attrs or "Target" not in attrs:
                raise FormatError("a Relationship of `%s` lacks Id, Type or Target" % name)
            mode = "external" if attrs.get("TargetMode") == "External" else "internal"
            resolved = None
            if mode == "internal":
                resolved = by_key.get(key(resolve(source, attrs["Target"])))
            rels.append((source, attrs["Id"], attrs["Type"], mode, attrs["Target"], resolved))
    return parts, rels


def listing(data):
    parts, rels = read_package(data)
    lines = ["opc parts %d relationships %d" % (len(parts), len(rels))]
    for (name, ctype, e) in parts:
        lines.append("part %s type %s size %d sha256 %s" % (esc(name), esc(ctype), e["size"], hashlib.sha256(entry_bytes(data, e)).hexdigest()))
    for (source, rid, rtype, mode, target, resolved) in rels:
        lines.append("rel %s %s %s %s %s %s" % (esc(source), esc(rid), esc(rtype), mode, esc(target),
                                                 esc(resolved) if resolved is not None else ("-" if mode == "external" else "!missing")))
    return ("\n".join(lines) + "\n").encode("utf-8")


def main(argv):
    args = argv[1:]
    want = None
    if "--part" in args:
        i = args.index("--part")
        want = args[i + 1]
        args = args[:i] + args[i + 2:]
    if len(args) != 1:
        sys.stderr.write(__doc__)
        return 2
    with open(args[0], "rb") as fh:
        data = fh.read()
    try:
        if want is None:
            sys.stdout.buffer.write(listing(data))
            return 0
        parts, _ = read_package(data)
        for (name, _, e) in parts:
            if key(name) == key(want):
                sys.stdout.buffer.write(entry_bytes(data, e))
                return 0
        raise FormatError("no part `%s`" % want)
    except (FormatError, IndexError, UnicodeDecodeError, ValueError) as e:
        sys.stderr.write("opc_dump: %s\n" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
