#!/usr/bin/env python3
"""zip_dump.py - reference reader for werk format definition `zip`.

Implements spec/formats/zip.md from scratch: the end-of-central-directory record (and its
ZIP64 forms), the central directory, local file headers, data descriptors, the extra-field
blocks that matter (ZIP64, Unicode path), stored (method 0) and deflated (method 8) entries,
and CRC-32 verification. DEFLATE is inflated by the code in this file (the algorithm of format
definition `zlib-deflate`), not by Python's zlib or zipfile modules.

    python zip_dump.py <input.zip>  >  <listing>
    python zip_dump.py <input.zip> --entry <name>  >  <that entry's uncompressed bytes>

Output (the definition's canonical form, section 9): UTF-8 text, each line ended by LF:

    zip entries <n> zip64 <0|1> comment <ESC(comment)>
    entry <ESC(name)> method <m> flags <4 hex> time <YYYY-MM-DDThh:mm:ss> crc <8 hex> packed <bytes> size <bytes> sha256 <hex>

NOT implemented, as the definition states: encrypted entries, compression methods other than
0 and 8, multi-disk archives - each refused by name; writing.

Python >= 3.8, standard library only (hashlib for SHA-256). Source only; never run
automatically by any werk tool.
"""

import hashlib
import sys


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


def dos_time(date, time):
    return "%04d-%02d-%02dT%02d:%02d:%02d" % (1980 + (date >> 9), (date >> 5) & 15, date & 31, time >> 11, (time >> 5) & 63, (time & 31) * 2)


def listing(data):
    entries, zip64, comment = read_directory(data)
    lines = ["zip entries %d zip64 %d comment %s" % (len(entries), zip64, esc(text_of(comment, False)))]
    for e in entries:
        out = entry_bytes(data, e)
        lines.append("entry %s method %d flags %04x time %s crc %08x packed %d size %d sha256 %s" % (
            esc(e["name"]), e["method"], e["flags"], dos_time(e["date"], e["time"]), e["crc"], e["packed"], e["size"],
            hashlib.sha256(out).hexdigest()))
    return ("\n".join(lines) + "\n").encode("utf-8")


def main(argv):
    args = argv[1:]
    want = None
    if "--entry" in args:
        i = args.index("--entry")
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
        entries, _, _ = read_directory(data)
        for e in entries:
            if e["name"] == want:
                sys.stdout.buffer.write(entry_bytes(data, e))
                return 0
        raise FormatError("no entry `%s`" % want)
    except (FormatError, IndexError) as e:
        sys.stderr.write("zip_dump: %s\n" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
