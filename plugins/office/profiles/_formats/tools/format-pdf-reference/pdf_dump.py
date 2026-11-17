#!/usr/bin/env python3
"""pdf_dump.py - reference reader for werk format definition `pdf`.

Implements spec/formats/pdf.md from scratch: the PDF object syntax; the file structure -
header, cross-reference tables AND cross-reference streams, hybrid files, object streams, the
chain of incremental updates; the stream filters FlateDecode (inflated by the code in this
file, the algorithm of format definition `zlib-deflate`), LZWDecode, ASCII85Decode,
ASCIIHexDecode, RunLengthDecode and the PNG / TIFF predictors; the page tree with inherited
attributes; page content streams and their operator grammar including inline images; and the
fonts each page names, down to where the embedded font program is.

    python pdf_dump.py <input.pdf>  >  <listing>
    python pdf_dump.py <input.pdf> --content <page number>  >  <that page's decoded content stream>
    python pdf_dump.py <input.pdf> --tokens <page number>   >  <its canonical operator listing>
    python pdf_dump.py <input.pdf> --stream <object number> >  <that stream's decoded data>

Output (the definition's canonical form, section 14): UTF-8 text, each line ended by LF.

NOT implemented, as the definition states: encrypted documents (refused by name); rebuilding a
damaged cross-reference by scanning; the image filters DCTDecode, JPXDecode, CCITTFaxDecode and
JBIG2Decode (the data is delivered still encoded); interpreting content - no text extraction,
no rendering; font programs themselves (formats `sfnt`, `cff`).

Python >= 3.8, standard library only (hashlib for SHA-256). Source only; never run
automatically by any werk tool.
"""

import hashlib
import sys

sys.setrecursionlimit(10000)


class FormatError(Exception):
    pass


# ---------------------------------------------------------------------------------------------
# DEFLATE (format definition `zlib-deflate`)

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


def inflate_zlib(data):
    if len(data) < 2 or data[0] & 15 != 8 or ((data[0] << 8) | data[1]) % 31:
        raise FormatError("FlateDecode data is not a zlib stream")
    return inflate_raw(data[2:])


# ---------------------------------------------------------------------------------------------
# section 3: lexical conventions and objects

WHITESPACE = b"\x00\t\n\x0c\r "
DELIMITERS = b"()<>[]{}/%"


class Ref:
    def __init__(self, num, gen):
        self.num, self.gen = num, gen


class Name:
    def __init__(self, value):
        self.value = value                                    # bytes, after #xx decoding

    def __eq__(self, other):
        return isinstance(other, Name) and other.value == self.value

    def __hash__(self):
        return hash(self.value)


class Number:
    def __init__(self, lexeme):
        self.lexeme = lexeme                                  # str, as written

    def is_int(self):
        return "." not in self.lexeme

    def int(self):
        return int(self.lexeme) if self.is_int() else int(float(self.lexeme))


class String:
    def __init__(self, value):
        self.value = value                                    # bytes, decoded


class Stream:
    def __init__(self, dictionary, raw):
        self.dict, self.raw = dictionary, raw


class Keyword:
    def __init__(self, word):
        self.word = word


class Dict:
    """A dictionary that keeps the order of its entries; a repeated key keeps its first position, last value."""

    def __init__(self):
        self.keys, self.map = [], {}

    def set(self, key, value):
        if key not in self.map:
            self.keys.append(key)
        self.map[key] = value

    def get(self, key, default=None):
        return self.map.get(key if isinstance(key, bytes) else key.encode("latin-1"), default)

    def items(self):
        return [(k, self.map[k]) for k in self.keys]


class Lexer:
    def __init__(self, data, pos=0):
        self.data, self.pos = data, pos

    def skip_ws(self):
        d = self.data
        while self.pos < len(d):
            c = d[self.pos]
            if c in WHITESPACE:
                self.pos += 1
            elif c == 0x25:                                   # % comment to the end of the line
                while self.pos < len(d) and d[self.pos] not in b"\r\n":
                    self.pos += 1
            else:
                break

    def regular(self):
        """A run of regular characters starting at pos."""
        d = self.data
        start = self.pos
        while self.pos < len(d) and d[self.pos] not in WHITESPACE and d[self.pos] not in DELIMITERS:
            self.pos += 1
        return d[start:self.pos]

    def object(self):
        """The next object, or a Keyword for anything that is not one. None at the end of the data."""
        self.skip_ws()
        d = self.data
        if self.pos >= len(d):
            return None
        c = d[self.pos]
        if c == 0x2F:                                         # /name
            self.pos += 1
            raw = self.regular()
            out = bytearray()
            i = 0
            while i < len(raw):
                if raw[i] == 0x23 and len(raw) - i >= 3 and all(x in b"0123456789abcdefABCDEF" for x in raw[i + 1:i + 3]):
                    out.append(int(raw[i + 1:i + 3], 16))
                    i += 3
                else:
                    out.append(raw[i])
                    i += 1
            return Name(bytes(out))
        if c == 0x28:
            return self.literal_string()
        if c == 0x3C:
            if d[self.pos + 1:self.pos + 2] == b"<":
                return self.dictionary()
            return self.hex_string()
        if c == 0x5B:
            self.pos += 1
            items = []
            while True:
                self.skip_ws()
                if self.pos >= len(d):
                    raise FormatError("an array is not closed")
                if d[self.pos] == 0x5D:
                    self.pos += 1
                    return items
                item = self.object()
                if isinstance(item, Keyword):
                    if item.word == b"R" and len(items) >= 2 and is_ref_pair(items[-2], items[-1]):
                        gen, num = items.pop(), items.pop()
                        items.append(Ref(num.int(), gen.int()))
                        continue
                    raise FormatError("unexpected `%s` in an array" % item.word.decode("latin-1"))
                items.append(item)
        if c in b")>]{}":
            self.pos += 1
            return Keyword(bytes([c]))
        word = self.regular()
        if is_number(word):
            return Number(word.decode("ascii"))
        if word == b"true":
            return True
        if word == b"false":
            return False
        if word == b"null":
            return NULL
        return Keyword(word)

    def literal_string(self):
        d = self.data
        self.pos += 1
        out = bytearray()
        depth = 1
        while True:
            if self.pos >= len(d):
                raise FormatError("a literal string is not closed")
            c = d[self.pos]
            self.pos += 1
            if c == 0x5C:                                     # backslash
                if self.pos >= len(d):
                    break
                e = d[self.pos]
                self.pos += 1
                if e in b"nrtbf":
                    out.append({0x6E: 10, 0x72: 13, 0x74: 9, 0x62: 8, 0x66: 12}[e])
                elif e in b"01234567":
                    v = e - 0x30
                    for _ in range(2):
                        if self.pos < len(d) and d[self.pos] in b"01234567":
                            v = v * 8 + d[self.pos] - 0x30
                            self.pos += 1
                    out.append(v & 255)
                elif e == 0x0D:                               # line continuation: backslash + end of line
                    if self.pos < len(d) and d[self.pos] == 0x0A:
                        self.pos += 1
                elif e == 0x0A:
                    pass
                else:
                    out.append(e)                             # \( \) \\ and any other character: itself
            elif c == 0x28:
                depth += 1
                out.append(c)
            elif c == 0x29:
                depth -= 1
                if depth == 0:
                    break
                out.append(c)
            elif c == 0x0D:                                   # an end of line inside a string reads as one LF
                if self.pos < len(d) and d[self.pos] == 0x0A:
                    self.pos += 1
                out.append(0x0A)
            else:
                out.append(c)
        return String(bytes(out))

    def hex_string(self):
        d = self.data
        self.pos += 1
        digits = bytearray()
        while True:
            if self.pos >= len(d):
                raise FormatError("a hexadecimal string is not closed")
            c = d[self.pos]
            self.pos += 1
            if c == 0x3E:
                break
            if c in WHITESPACE:
                continue
            if c not in b"0123456789abcdefABCDEF":
                raise FormatError("a hexadecimal string contains `%s`" % chr(c))
            digits.append(c)
        if len(digits) % 2:
            digits.append(0x30)
        return String(bytes.fromhex(digits.decode("ascii")))

    def dictionary(self):
        d = self.data
        self.pos += 2
        out = Dict()
        pending = []
        while True:
            self.skip_ws()
            if self.pos >= len(d):
                raise FormatError("a dictionary is not closed")
            if d[self.pos:self.pos + 2] == b">>":
                self.pos += 2
                break
            item = self.object()
            if isinstance(item, Keyword):
                if item.word == b"R" and len(pending) >= 2 and is_ref_pair(pending[-2], pending[-1]):
                    gen, num = pending.pop(), pending.pop()
                    pending.append(Ref(num.int(), gen.int()))
                    continue
                raise FormatError("unexpected `%s` in a dictionary" % item.word.decode("latin-1"))
            pending.append(item)
        if len(pending) % 2:
            raise FormatError("a dictionary has a key without a value")
        for i in range(0, len(pending), 2):
            if not isinstance(pending[i], Name):
                raise FormatError("a dictionary key is not a name")
            out.set(pending[i].value, pending[i + 1])
        return out


class Null:
    pass


NULL = Null()


def is_number(word):
    if not word:
        return False
    body = word[1:] if word[:1] in (b"+", b"-") else word
    if not body or body == b".":
        return False
    return all(c in b"0123456789." for c in body) and body.count(b".") <= 1


def is_ref_pair(a, b):
    return isinstance(a, Number) and isinstance(b, Number) and a.is_int() and b.is_int() and a.int() >= 0 and b.int() >= 0


# ---------------------------------------------------------------------------------------------
# section 14: the canonical form of an object

def esc(data):
    if not data:
        return "%"
    return "".join(chr(b) if 0x21 <= b <= 0x7E and b not in (0x25, 0x2F) else "%%%02X" % b for b in data)


def canon_number(lexeme):
    s = lexeme
    neg = s.startswith("-")
    if s[:1] in "+-":
        s = s[1:]
    if "." in s:
        whole, frac = s.split(".")
        frac = frac.rstrip("0")
    else:
        whole, frac = s, ""
    whole = whole.lstrip("0") or "0"
    text = whole + ("." + frac if frac else "")
    if neg and text.strip("0.") != "":
        text = "-" + text
    return text


def canon(obj):
    if obj is NULL or obj is None:
        return "null"
    if obj is True:
        return "true"
    if obj is False:
        return "false"
    if isinstance(obj, Number):
        return canon_number(obj.lexeme)
    if isinstance(obj, String):
        return "<" + obj.value.hex() + ">"
    if isinstance(obj, Name):
        return "/" + esc(obj.value)
    if isinstance(obj, Ref):
        return "%d %d R" % (obj.num, obj.gen)
    if isinstance(obj, list):
        return "[ " + "".join(canon(x) + " " for x in obj) + "]"
    if isinstance(obj, Dict):
        return "<< " + "".join("/%s %s " % (esc(k), canon(v)) for k, v in obj.items()) + ">>"
    raise FormatError("cannot serialise %r" % (obj,))


# ---------------------------------------------------------------------------------------------
# section 8: filters

def ascii_hex(data):
    digits = bytearray()
    for c in data:
        if c == 0x3E:
            break
        if c in WHITESPACE:
            continue
        if c not in b"0123456789abcdefABCDEF":
            raise FormatError("ASCIIHexDecode: `%s` is not a hexadecimal digit" % chr(c))
        digits.append(c)
    if len(digits) % 2:
        digits.append(0x30)
    return bytes.fromhex(digits.decode("ascii"))


def ascii85(data):
    out = bytearray()
    group = []
    i = 0
    if data[:2] == b"<~":
        i = 2
    while i < len(data):
        c = data[i]
        i += 1
        if c in WHITESPACE:
            continue
        if c == 0x7E:                                         # ~> ends the data
            break
        if c == 0x7A and not group:                           # z: four zero bytes
            out += b"\x00\x00\x00\x00"
            continue
        if not 0x21 <= c <= 0x75:
            raise FormatError("ASCII85Decode: byte %02X is outside ! .. u" % c)
        group.append(c - 0x21)
        if len(group) == 5:
            v = 0
            for g in group:
                v = v * 85 + g
            if v > 0xFFFFFFFF:
                raise FormatError("ASCII85Decode: a group exceeds 2^32 - 1")
            out += v.to_bytes(4, "big")
            group = []
    if group:
        if len(group) == 1:
            raise FormatError("ASCII85Decode: a final group of one character")
        n = len(group)
        group += [84] * (5 - n)
        v = 0
        for g in group:
            v = v * 85 + g
        out += (v & 0xFFFFFFFF).to_bytes(4, "big")[:n - 1]
    return bytes(out)


def run_length(data):
    out = bytearray()
    i = 0
    while i < len(data):
        n = data[i]
        i += 1
        if n == 128:
            break
        if n < 128:
            out += data[i:i + n + 1]
            i += n + 1
        else:
            if i >= len(data):
                break
            out += bytes([data[i]]) * (257 - n)
            i += 1
    return bytes(out)


def lzw(data, early):
    out = bytearray()
    table = None
    width = 9
    buf = cnt = 0
    p = 0
    prev = None
    while True:
        while cnt < width:
            if p >= len(data):
                return bytes(out)
            buf = (buf << 8) | data[p]
            p += 1
            cnt += 8
        code = (buf >> (cnt - width)) & ((1 << width) - 1)
        cnt -= width
        buf &= (1 << cnt) - 1
        if code == 256:
            table = [bytes([i]) for i in range(256)] + [b"", b""]
            width = 9
            prev = None
            continue
        if code == 257:
            return bytes(out)
        if table is None:
            table = [bytes([i]) for i in range(256)] + [b"", b""]     # tolerated: data that does not begin with a clear code
        if prev is None:
            if code >= 256:
                raise FormatError("LZWDecode: the first code after a clear is not a byte")
            entry = table[code]
        elif code < len(table):
            entry = table[code]
            table.append(table[prev] + entry[:1])
        elif code == len(table):
            entry = table[prev] + table[prev][:1]
            table.append(entry)
        else:
            raise FormatError("LZWDecode: code %d is not in the table" % code)
        out += entry
        prev = code
        size = len(table) + (1 if early else 0)             # early change: one code sooner
        if size >= 2048:
            width = 12
        elif size >= 1024:
            width = 11
        elif size >= 512:
            width = 10


def predictor(data, parms, doc):
    """Undo a predictor (section 8.7)."""
    get = lambda key, default: doc.integer(parms.get(key), default) if parms is not None else default
    pred = get("Predictor", 1)
    if pred == 1:
        return data
    colors, bpc, columns = get("Colors", 1), get("BitsPerComponent", 8), get("Columns", 1)
    row_bytes = (colors * bpc * columns + 7) // 8
    bpp = max(1, colors * bpc // 8)
    out = bytearray()
    if pred == 2:
        if bpc != 8:
            raise FormatError("the TIFF predictor with %d bits per component is not defined" % bpc)
        for start in range(0, len(data), row_bytes):         # a final partial row is decoded as far as it goes
            row = bytearray(data[start:start + row_bytes])
            for i in range(colors, len(row)):
                row[i] = (row[i] + row[i - colors]) & 255
            out += row
        return bytes(out)
    if pred < 10 or pred > 15:
        raise FormatError("predictor %d is not defined" % pred)
    prev = bytearray(row_bytes)
    pos = 0
    while pos < len(data):                                    # a final partial row is decoded as far as it goes
        ftype = data[pos]
        row = bytearray(data[pos + 1:pos + 1 + row_bytes])
        pos += 1 + row_bytes
        if ftype == 1:
            for i in range(bpp, len(row)):
                row[i] = (row[i] + row[i - bpp]) & 255
        elif ftype == 2:
            for i in range(len(row)):
                row[i] = (row[i] + prev[i]) & 255
        elif ftype == 3:
            for i in range(len(row)):
                left = row[i - bpp] if i >= bpp else 0
                row[i] = (row[i] + ((left + prev[i]) >> 1)) & 255
        elif ftype == 4:
            for i in range(len(row)):
                a = row[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                row[i] = (row[i] + (a if pa <= pb and pa <= pc else (b if pb <= pc else c))) & 255
        elif ftype != 0:
            raise FormatError("PNG predictor: row filter %d is not defined" % ftype)
        out += row
        prev = row + prev[len(row):]
    return bytes(out)


FILTER_NAMES = {b"A85": b"ASCII85Decode", b"AHx": b"ASCIIHexDecode", b"Fl": b"FlateDecode", b"LZW": b"LZWDecode",
                b"RL": b"RunLengthDecode", b"DCT": b"DCTDecode", b"CCF": b"CCITTFaxDecode"}
UNDECODED = (b"DCTDecode", b"JPXDecode", b"CCITTFaxDecode", b"JBIG2Decode", b"Crypt")


# ---------------------------------------------------------------------------------------------
# sections 5-7: the file

class Document:
    def __init__(self, data):
        head = data[:1024].find(b"%PDF-")
        if head < 0:
            raise FormatError("not a PDF file: no %PDF- in the first 1024 bytes")
        self.data = data[head:]                               # every offset counts from the header
        data = self.data
        end = 5
        while end < len(data) and end < 16 and data[end] not in WHITESPACE:
            end += 1
        self.version = data[5:end].decode("latin-1")
        sx = data.rfind(b"startxref", max(0, len(data) - 2048))
        if sx < 0:
            raise FormatError("no startxref in the last 2048 bytes (repairing a file by scanning is not defined)")
        lx = Lexer(data, sx + 9)
        first = lx.object()
        if not isinstance(first, Number) or not first.is_int():
            raise FormatError("startxref is not followed by an offset")
        self.xref = {}                                        # object number -> ("n", offset, gen) | ("c", stream number, index) | ("f",)
        self.trailer = None
        self.revisions = 0
        self.cache = {}
        self.objstm_cache = {}
        seen = set()
        offset = first.int()
        while offset is not None:
            if offset in seen:
                raise FormatError("the chain of cross-reference sections loops")
            seen.add(offset)
            self.revisions += 1
            trailer = self.read_xref_section(offset)
            if self.trailer is None:
                self.trailer = trailer
            hybrid = trailer.get("XRefStm")
            if isinstance(hybrid, Number):
                self.read_xref_section(hybrid.int(), hybrid=True)
            prev = trailer.get("Prev")
            offset = prev.int() if isinstance(prev, Number) else None
        if self.trailer.get("Encrypt") is not None and self.resolve(self.trailer.get("Encrypt")) is not NULL:
            raise FormatError("the document is encrypted; encryption is not defined by this format definition")

    # -- cross-reference sections (section 6)

    def read_xref_section(self, offset, hybrid=False):
        data = self.data
        if not hybrid:
            self.section_free = set()                         # the numbers THIS section declares free (section 6.3)
        lx = Lexer(data, offset)
        lx.skip_ws()
        if data[lx.pos:lx.pos + 4] == b"xref":
            lx.pos += 4
            while True:
                lx.skip_ws()
                if data[lx.pos:lx.pos + 7] == b"trailer":
                    lx.pos += 7
                    break
                start, count = lx.object(), lx.object()
                if not isinstance(start, Number) or not isinstance(count, Number):
                    raise FormatError("a cross-reference subsection header is malformed")
                for i in range(count.int()):
                    off, gen, kind = lx.object(), lx.object(), lx.object()
                    if not isinstance(off, Number) or not isinstance(gen, Number) or not isinstance(kind, Keyword) or kind.word not in (b"n", b"f"):
                        raise FormatError("a cross-reference entry is malformed")
                    num = start.int() + i
                    if num not in self.xref:
                        self.xref[num] = ("n", off.int(), gen.int()) if kind.word == b"n" else ("f",)
                        if kind.word == b"f":
                            self.section_free.add(num)
            trailer = lx.object()
            if not isinstance(trailer, Dict):
                raise FormatError("`trailer` is not followed by a dictionary")
            return trailer
        # a cross-reference stream
        obj = self.parse_indirect(offset, None)
        if not isinstance(obj, Stream) or obj.dict.get("Type") != Name(b"XRef"):
            raise FormatError("offset %d holds neither a cross-reference table nor a cross-reference stream" % offset)
        d = obj.dict
        w = d.get("W")
        if not isinstance(w, list) or len(w) != 3 or not all(isinstance(x, Number) for x in w):
            raise FormatError("a cross-reference stream has no valid /W")
        w = [x.int() for x in w]
        size = d.get("Size")
        index = d.get("Index")
        ranges = [x.int() for x in index] if isinstance(index, list) else [0, size.int() if isinstance(size, Number) else 0]
        rows, undecoded = self.decode_stream(obj)
        if undecoded:
            raise FormatError("a cross-reference stream uses a filter this definition does not decode")
        width = sum(w)
        if width == 0:
            raise FormatError("a cross-reference stream has rows of width 0")
        pos = 0
        for r in range(0, len(ranges) - 1, 2):
            for i in range(ranges[r + 1]):
                if pos + width > len(rows):
                    break
                f = []
                q = pos
                for n in w:
                    f.append(int.from_bytes(rows[q:q + n], "big"))
                    q += n
                pos += width
                kind = f[0] if w[0] else 1
                num = ranges[r] + i
                if num in self.xref and not (hybrid and num in self.section_free):
                    continue
                if kind == 0:
                    self.xref[num] = ("f",)
                elif kind == 1:
                    self.xref[num] = ("n", f[1], f[2])
                elif kind == 2:
                    self.xref[num] = ("c", f[1], f[2])
        return d

    # -- objects (section 5)

    def parse_indirect(self, offset, expect):
        """The object of `n g obj ... endobj` at `offset`."""
        lx = Lexer(self.data, offset)
        num, gen, kw = lx.object(), lx.object(), lx.object()
        if not isinstance(num, Number) or not isinstance(gen, Number) or not isinstance(kw, Keyword) or kw.word != b"obj":
            raise FormatError("offset %d does not hold `n g obj`" % offset)
        if expect is not None and num.int() != expect:
            raise FormatError("offset %d holds object %d, the cross-reference says %d" % (offset, num.int(), expect))
        obj = lx.object()
        if isinstance(obj, Keyword):
            if obj.word == b"endobj":
                return NULL
            raise FormatError("object %d begins with `%s`" % (num.int(), obj.word.decode("latin-1")))
        if isinstance(obj, Dict):
            lx.skip_ws()
            if self.data[lx.pos:lx.pos + 6] == b"stream":
                p = lx.pos + 6
                if self.data[p:p + 2] == b"\r\n":
                    p += 2
                elif self.data[p:p + 1] in (b"\n", b"\r"):
                    p += 1
                length = self.integer(obj.get("Length"), None)
                raw = None
                if length is not None and length >= 0 and p + length <= len(self.data):
                    q = p + length
                    while q < len(self.data) and self.data[q] in WHITESPACE:
                        q += 1
                    if self.data[q:q + 9] == b"endstream":
                        raw = self.data[p:p + length]
                if raw is None:                               # /Length is missing or wrong: the data ends before `endstream`
                    q = self.data.find(b"endstream", p)
                    if q < 0:
                        raise FormatError("stream %d has no endstream" % num.int())
                    if self.data[q - 2:q] == b"\r\n":
                        q -= 2
                    elif self.data[q - 1:q] in (b"\n", b"\r"):
                        q -= 1
                    raw = self.data[p:q]
                return Stream(obj, raw)
        return obj

    def load(self, num):
        if num in self.cache:
            return self.cache[num]
        entry = self.xref.get(num)
        self.cache[num] = NULL                                # a reference to itself while loading reads as null
        if entry is None or entry[0] == "f":
            obj = NULL
        elif entry[0] == "n":
            obj = self.parse_indirect(entry[1], num)
        else:
            obj = self.from_object_stream(entry[1], entry[2], num)
        self.cache[num] = obj
        return obj

    def from_object_stream(self, stream_num, index, num):
        if stream_num not in self.objstm_cache:
            stm = self.load(stream_num)
            if not isinstance(stm, Stream) or stm.dict.get("Type") != Name(b"ObjStm"):
                raise FormatError("object %d is not an object stream" % stream_num)
            data, undecoded = self.decode_stream(stm)
            if undecoded:
                raise FormatError("object stream %d uses a filter this definition does not decode" % stream_num)
            n, first = self.integer(stm.dict.get("N"), 0), self.integer(stm.dict.get("First"), 0)
            lx = Lexer(data, 0)
            pairs = []
            for _ in range(n):
                a, b = lx.object(), lx.object()
                if not isinstance(a, Number) or not isinstance(b, Number):
                    raise FormatError("object stream %d has a malformed index" % stream_num)
                pairs.append((a.int(), b.int()))
            self.objstm_cache[stream_num] = (data, first, pairs)
        data, first, pairs = self.objstm_cache[stream_num]
        if index >= len(pairs) or pairs[index][0] != num:
            hit = [i for i, (n, _) in enumerate(pairs) if n == num]
            if not hit:
                raise FormatError("object %d is not in object stream %d" % (num, stream_num))
            index = hit[0]
        obj = Lexer(data, first + pairs[index][1]).object()
        if isinstance(obj, Keyword):
            raise FormatError("object %d in object stream %d is not an object" % (num, stream_num))
        return obj

    def resolve(self, obj):
        seen = 0
        while isinstance(obj, Ref):
            obj = self.load(obj.num)
            seen += 1
            if seen > 100:
                raise FormatError("a chain of references does not end")
        return NULL if obj is None else obj

    def integer(self, obj, default):
        obj = self.resolve(obj)
        return obj.int() if isinstance(obj, Number) else default

    # -- streams (section 8)

    def decode_stream(self, stream):
        """(data, names of the filters that were NOT applied)."""
        filters = self.resolve(stream.dict.get("Filter"))
        parms = self.resolve(stream.dict.get("DecodeParms"))
        if isinstance(filters, Name):
            filters = [filters]
        elif not isinstance(filters, list):
            filters = []
        if isinstance(parms, Dict):
            parms = [parms]
        elif not isinstance(parms, list):
            parms = []
        data = stream.raw
        for i, f in enumerate(filters):
            f = self.resolve(f)
            name = FILTER_NAMES.get(f.value, f.value) if isinstance(f, Name) else b"?"
            p = self.resolve(parms[i]) if i < len(parms) else None
            if not isinstance(p, Dict):
                p = None
            if name in UNDECODED:
                rest = [self.resolve(x) for x in filters[i:]]
                return data, [FILTER_NAMES.get(x.value, x.value) if isinstance(x, Name) else b"?" for x in rest]
            if name == b"FlateDecode":
                data = predictor(inflate_zlib(data), p, self)
            elif name == b"LZWDecode":
                early = self.integer(p.get("EarlyChange"), 1) if p is not None else 1
                data = predictor(lzw(data, early != 0), p, self)
            elif name == b"ASCII85Decode":
                data = ascii85(data)
            elif name == b"ASCIIHexDecode":
                data = ascii_hex(data)
            elif name == b"RunLengthDecode":
                data = run_length(data)
            else:
                raise FormatError("filter /%s is not defined" % name.decode("latin-1"))
        return data, []

    def canon_object(self, obj):
        if isinstance(obj, Stream):
            head = canon(obj.dict) + " stream raw %d " % len(obj.raw)
            try:
                data, undecoded = self.decode_stream(obj)
            except (FormatError, IndexError) as e:
                return head + "undecodable"
            if undecoded:
                return head + "partial %s %d sha256 %s" % (",".join(esc(n) for n in undecoded), len(data), hashlib.sha256(data).hexdigest())
            return head + "decoded %d sha256 %s" % (len(data), hashlib.sha256(data).hexdigest())
        return canon(obj)

    # -- pages (section 9)

    def pages(self):
        """List of (object number, generation, page dictionary, inherited attributes)."""
        root = self.resolve(self.trailer.get("Root"))
        if not isinstance(root, Dict):
            raise FormatError("the trailer has no /Root catalog")
        out = []
        seen = set()

        def walk(ref, inherited, depth):
            node = self.resolve(ref)
            if not isinstance(node, Dict):
                return
            if ref.num in seen:
                raise FormatError("the page tree loops at object %d" % ref.num)
            seen.add(ref.num)
            inherited = dict(inherited)
            for key in (b"Resources", b"MediaBox", b"CropBox", b"Rotate"):
                if node.get(key) is not None and node.get(key) is not NULL:
                    inherited[key] = node.get(key)
            kids = self.resolve(node.get("Kids"))
            kind = node.get("Type")
            if kind == Name(b"Pages") or (kind != Name(b"Page") and isinstance(kids, list)):
                if depth > 200:
                    raise FormatError("the page tree is deeper than 200 levels")
                for kid in kids if isinstance(kids, list) else []:
                    if isinstance(kid, Ref):                  # /Kids holds references; anything else is skipped
                        walk(kid, inherited, depth + 1)
            else:
                out.append((ref.num, ref.gen, node, inherited))

        if isinstance(root.get("Pages"), Ref):
            walk(root.get("Pages"), {}, 0)
        return out

    def page_content(self, page):
        contents = self.resolve(page.get("Contents"))
        streams = contents if isinstance(contents, list) else [contents]
        pieces = []
        for s in streams:
            s = self.resolve(s)
            if isinstance(s, Stream):
                data, undecoded = self.decode_stream(s)
                if undecoded:
                    raise FormatError("a content stream uses a filter this definition does not decode")
                pieces.append(data)
        return b"\n".join(pieces), len(pieces)


# ---------------------------------------------------------------------------------------------
# section 10: content streams

def content_tokens(data):
    """The canonical operator listing: one line per operator."""
    lx = Lexer(data, 0)
    lines = []
    operands = []
    while True:
        obj = lx.object()
        if obj is None:
            break
        if not isinstance(obj, Keyword):
            operands.append(obj)
            continue
        word = obj.word
        if word == b"BI":
            params = Dict()
            while True:
                lx.skip_ws()
                if lx.pos >= len(data):
                    raise FormatError("an inline image has no ID")
                if data[lx.pos:lx.pos + 2] == b"ID" and (lx.pos + 2 >= len(data) or data[lx.pos + 2] in WHITESPACE):
                    lx.pos += 2
                    break
                key = lx.object()
                value = lx.object()
                if not isinstance(key, Name) or value is None or isinstance(value, Keyword):
                    raise FormatError("an inline image has malformed parameters")
                params.set(key.value, value)
            begin = min(lx.pos + 1, len(data))                # one white-space byte separates ID from the data
            end = None
            p = begin
            while True:
                p = data.find(b"EI", p)
                if p < 0:
                    break
                if p > begin and data[p - 1] in WHITESPACE and (p + 2 >= len(data) or data[p + 2] in WHITESPACE or data[p + 2] in DELIMITERS):
                    end = p - 1
                    break
                p += 1
            if end is None:
                image, lx.pos = data[begin:], len(data)
            else:
                image, lx.pos = data[begin:end], end + 3
            lines.append("BI %s ID %d %s EI" % (canon(params), len(image), hashlib.sha256(image).hexdigest()))
            operands = []
            continue
        if word in (b")", b">", b"]", b"{", b"}"):
            continue                                          # a stray delimiter is skipped
        lines.append("".join(canon(o) + " " for o in operands) + esc(word))
        operands = []
    return lines


PDFDOC = {0x18: 0x02D8, 0x19: 0x02C7, 0x1A: 0x02C6, 0x1B: 0x02D9, 0x1C: 0x02DD, 0x1D: 0x02DB, 0x1E: 0x02DA, 0x1F: 0x02DC}
for _i, _c in enumerate("•†‡…—–ƒ⁄‹›−‰„“”‘’‚"
                        "™ﬁﬂŁŒŠŸŽıłœšž�€"):
    PDFDOC[0x80 + _i] = ord(_c)


def text_string(value):
    """A PDF text string (section 4.3) as text."""
    if value[:2] == b"\xfe\xff":
        return value[2:].decode("utf-16-be", "replace")
    if value[:3] == b"\xef\xbb\xbf":
        return value[3:].decode("utf-8", "replace")
    return "".join(chr(PDFDOC.get(b, b)) for b in value)


def listing(data):
    doc = Document(data)
    numbers = sorted(n for n, e in doc.xref.items() if e[0] != "f" and n != 0)
    lines = ["pdf %s revisions %d objects %d" % (doc.version, doc.revisions, len(numbers))]
    t = doc.trailer
    root, info = t.get("Root"), t.get("Info")
    ident = doc.resolve(t.get("ID"))
    lines.append("trailer root %s info %s id %s" % (
        "%d %d" % (root.num, root.gen) if isinstance(root, Ref) else "-", "%d %d" % (info.num, info.gen) if isinstance(info, Ref) else "-",
        ident[0].value.hex() if isinstance(ident, list) and ident and isinstance(ident[0], String) and ident[0].value else "-"))
    info_dict = doc.resolve(info)
    if isinstance(info_dict, Dict):
        for k, v in info_dict.items():
            v = doc.resolve(v)
            if isinstance(v, String):
                lines.append("info %s %s" % (esc(k), esc(text_string(v.value).encode("utf-8"))))
    for n in numbers:
        entry = doc.xref[n]
        gen = entry[2] if entry[0] == "n" else 0
        try:
            lines.append("object %d %d %s" % (n, gen, doc.canon_object(doc.load(n))))
        except (FormatError, IndexError, ValueError, RecursionError) as e:
            lines.append("object %d %d !unreadable" % (n, gen))
            doc.cache[n] = NULL
    for i, (num, gen, page, inherited) in enumerate(doc.pages()):
        box = doc.resolve(inherited.get(b"MediaBox"))
        rotate = doc.resolve(inherited.get(b"Rotate"))
        try:
            content, count = doc.page_content(page)
            tokens = content_tokens(content)
            tail = "contents %d bytes %d sha256 %s operators %d tokens %s" % (
                count, len(content), hashlib.sha256(content).hexdigest(), len(tokens),
                hashlib.sha256(("".join(l + "\n" for l in tokens)).encode("utf-8")).hexdigest())
        except (FormatError, IndexError, ValueError) as e:
            tail = "contents !unreadable"
        lines.append("page %d object %d %d mediabox %s rotate %s %s" % (
            i + 1, num, gen, canon(box) if isinstance(box, list) else "-", canon(rotate) if isinstance(rotate, Number) else "0", tail))
        resources = doc.resolve(inherited.get(b"Resources"))
        fonts = doc.resolve(resources.get("Font")) if isinstance(resources, Dict) else None
        if isinstance(fonts, Dict):
            for name, ref in fonts.items():
                font = doc.resolve(ref)
                if not isinstance(font, Dict):
                    continue
                subtype, base = font.get("Subtype"), doc.resolve(font.get("BaseFont"))
                holder = font
                if subtype == Name(b"Type0"):
                    desc = doc.resolve(font.get("DescendantFonts"))
                    if isinstance(desc, list) and desc and isinstance(doc.resolve(desc[0]), Dict):
                        holder = doc.resolve(desc[0])
                fd = doc.resolve(holder.get("FontDescriptor"))
                program = "none -"
                if isinstance(fd, Dict):
                    for key in ("FontFile", "FontFile2", "FontFile3"):
                        ff = fd.get(key)
                        if isinstance(ff, Ref):
                            program = "%s %d %d" % (key, ff.num, ff.gen)
                            break
                lines.append("font %d %s %s %s program %s" % (
                    i + 1, esc(name), esc(subtype.value) if isinstance(subtype, Name) else "-",
                    esc(base.value) if isinstance(base, Name) else "-", program))
    return ("\n".join(lines) + "\n").encode("utf-8")


def main(argv):
    args = argv[1:]
    mode = None
    for flag in ("--content", "--tokens", "--stream"):
        if flag in args:
            i = args.index(flag)
            mode = (flag, int(args[i + 1]))
            args = args[:i] + args[i + 2:]
    if len(args) != 1:
        sys.stderr.write(__doc__)
        return 2
    with open(args[0], "rb") as fh:
        data = fh.read()
    try:
        if mode is None:
            sys.stdout.buffer.write(listing(data))
            return 0
        doc = Document(data)
        if mode[0] == "--stream":
            obj = doc.load(mode[1])
            if not isinstance(obj, Stream):
                raise FormatError("object %d is not a stream" % mode[1])
            sys.stdout.buffer.write(doc.decode_stream(obj)[0])
            return 0
        pages = doc.pages()
        if not 1 <= mode[1] <= len(pages):
            raise FormatError("there is no page %d" % mode[1])
        content, _ = doc.page_content(pages[mode[1] - 1][2])
        if mode[0] == "--content":
            sys.stdout.buffer.write(content)
        else:
            sys.stdout.buffer.write(("".join(l + "\n" for l in content_tokens(content))).encode("utf-8"))
        return 0
    except (FormatError, IndexError, ValueError, RecursionError) as e:
        sys.stderr.write("pdf_dump: %s\n" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
