#!/usr/bin/env python3
"""inflate.py - reference decoder for werk format definition `zlib-deflate`.

Implements spec/formats/zlib-deflate.md from scratch: DEFLATE (RFC 1951) with the zlib
(RFC 1950) and gzip (RFC 1952) framings. It deliberately does NOT use Python's zlib module
for decompression - it is the definition as code. (hashlib is not used either: Adler-32 and
CRC-32 are implemented here, as the definition gives them.)

    python inflate.py <input file>  >  <decompressed bytes>

The framing is recognised from the leading bytes: 1f 8b = gzip; a valid zlib header
(CMF & 15 == 8, CMF >> 4 <= 7, (CMF*256 + FLG) % 31 == 0) = zlib; anything else is refused.
Use --raw to decode a bare DEFLATE stream with no framing.

Python >= 3.8, standard library only. Source only; never run automatically by any werk tool.
"""

import sys

LENGTH_BASE = [3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31,
               35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258]
LENGTH_EXTRA = [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2,
                3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0]
DIST_BASE = [1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769,
             1025, 1537, 2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577]
DIST_EXTRA = [0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8,
              9, 9, 10, 10, 11, 11, 12, 12, 13, 13]
CODE_LENGTH_ORDER = [16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15]


class FormatError(Exception):
    pass


class BitReader:
    """Bits are consumed from each byte starting at the LEAST significant bit."""

    def __init__(self, data, pos):
        self.data = data
        self.pos = pos      # next byte
        self.bitbuf = 0
        self.bitcnt = 0

    def bits(self, n):
        while self.bitcnt < n:
            if self.pos >= len(self.data):
                raise FormatError("unexpected end of data")
            self.bitbuf |= self.data[self.pos] << self.bitcnt
            self.pos += 1
            self.bitcnt += 8
        v = self.bitbuf & ((1 << n) - 1)
        self.bitbuf >>= n
        self.bitcnt -= n
        return v

    def align(self):
        self.bitbuf = 0
        self.bitcnt = 0


def build_table(lengths):
    """Canonical Huffman code (RFC 1951 section 3.2.2) -> {(length, code): symbol}."""
    max_len = max(lengths) if lengths else 0
    bl_count = [0] * (max_len + 1)
    for l in lengths:
        if l:
            bl_count[l] += 1
    code = 0
    next_code = [0] * (max_len + 2)
    for bits in range(1, max_len + 1):
        code = (code + bl_count[bits - 1]) << 1
        next_code[bits] = code
    table = {}
    for symbol, l in enumerate(lengths):
        if l:
            table[(l, next_code[l])] = symbol
            next_code[l] += 1
    return table, max_len


def decode_symbol(br, table):
    """Huffman codes are packed most-significant bit first, one bit at a time."""
    tab, max_len = table
    code = 0
    for length in range(1, max_len + 1):
        code = (code << 1) | br.bits(1)
        symbol = tab.get((length, code))
        if symbol is not None:
            return symbol
    raise FormatError("invalid Huffman code")


FIXED_LITLEN = build_table([8] * 144 + [9] * 112 + [7] * 24 + [8] * 8)
FIXED_DIST = build_table([5] * 30)


def inflate(data, pos=0):
    """Decode one DEFLATE stream starting at data[pos]. Returns (bytes, position after it)."""
    br = BitReader(data, pos)
    out = bytearray()
    while True:
        final = br.bits(1)
        btype = br.bits(2)
        if btype == 0:
            br.align()
            if br.pos + 4 > len(data):
                raise FormatError("truncated stored block")
            length = data[br.pos] | (data[br.pos + 1] << 8)
            nlength = data[br.pos + 2] | (data[br.pos + 3] << 8)
            if length ^ 0xFFFF != nlength:
                raise FormatError("stored block LEN/NLEN mismatch")
            br.pos += 4
            if br.pos + length > len(data):
                raise FormatError("truncated stored block")
            out += data[br.pos:br.pos + length]
            br.pos += length
        elif btype in (1, 2):
            if btype == 1:
                litlen, dist = FIXED_LITLEN, FIXED_DIST
            else:
                hlit = br.bits(5) + 257
                hdist = br.bits(5) + 1
                hclen = br.bits(4) + 4
                cl = [0] * 19
                for i in range(hclen):
                    cl[CODE_LENGTH_ORDER[i]] = br.bits(3)
                cl_table = build_table(cl)
                lengths = []
                while len(lengths) < hlit + hdist:
                    sym = decode_symbol(br, cl_table)
                    if sym < 16:
                        lengths.append(sym)
                    elif sym == 16:
                        if not lengths:
                            raise FormatError("repeat with no previous length")
                        lengths += [lengths[-1]] * (3 + br.bits(2))
                    elif sym == 17:
                        lengths += [0] * (3 + br.bits(3))
                    else:
                        lengths += [0] * (11 + br.bits(7))
                if len(lengths) != hlit + hdist:
                    raise FormatError("code lengths overrun")
                litlen = build_table(lengths[:hlit])
                dist = build_table(lengths[hlit:])
            while True:
                sym = decode_symbol(br, litlen)
                if sym < 256:
                    out.append(sym)
                elif sym == 256:
                    break
                else:
                    if sym > 285:
                        raise FormatError("invalid length symbol")
                    length = LENGTH_BASE[sym - 257] + br.bits(LENGTH_EXTRA[sym - 257])
                    dsym = decode_symbol(br, dist)
                    if dsym > 29:
                        raise FormatError("invalid distance symbol")
                    distance = DIST_BASE[dsym] + br.bits(DIST_EXTRA[dsym])
                    if distance > len(out):
                        raise FormatError("distance reaches before the start of the output")
                    start = len(out) - distance
                    for i in range(length):          # byte by byte: the copy may overlap itself
                        out.append(out[start + i])
        else:
            raise FormatError("reserved block type 3")
        if final:
            break
    return bytes(out), br.pos


def adler32(data):
    a, b = 1, 0
    for byte in data:
        a = (a + byte) % 65521
        b = (b + a) % 65521
    return (b << 16) | a


def crc32(data):
    crc = 0xFFFFFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xEDB88320 if crc & 1 else crc >> 1
    return crc ^ 0xFFFFFFFF


def decode_zlib(data):
    if len(data) < 6:
        raise FormatError("too short for a zlib stream")
    cmf, flg = data[0], data[1]
    if cmf & 0x0F != 8 or cmf >> 4 > 7 or (cmf * 256 + flg) % 31:
        raise FormatError("not a zlib header")
    if flg & 0x20:
        raise FormatError("preset dictionary (FDICT) is not supported: the dictionary is not in the stream")
    out, pos = inflate(data, 2)
    if pos + 4 > len(data):
        raise FormatError("missing Adler-32")
    stored = int.from_bytes(data[pos:pos + 4], "big")
    if stored != adler32(out):
        raise FormatError("Adler-32 mismatch")
    return out


def decode_gzip(data):
    out = bytearray()
    pos = 0
    while pos < len(data):                      # a gzip file is one or more members
        if data[pos:pos + 2] != b"\x1f\x8b":
            raise FormatError("not a gzip member")
        if data[pos + 2] != 8:
            raise FormatError("gzip compression method is not deflate")
        flg = data[pos + 3]
        pos += 10
        if flg & 4:                              # FEXTRA
            pos += 2 + (data[pos] | (data[pos + 1] << 8))
        if flg & 8:                              # FNAME, zero-terminated
            pos = data.index(0, pos) + 1
        if flg & 16:                             # FCOMMENT, zero-terminated
            pos = data.index(0, pos) + 1
        if flg & 2:                              # FHCRC
            pos += 2
        member, pos = inflate(data, pos)
        crc = int.from_bytes(data[pos:pos + 4], "little")
        size = int.from_bytes(data[pos + 4:pos + 8], "little")
        if crc != crc32(member) or size != len(member) & 0xFFFFFFFF:
            raise FormatError("gzip CRC-32 or ISIZE mismatch")
        pos += 8
        out += member
    return bytes(out)


def decode(data, raw=False):
    if raw:
        return inflate(data, 0)[0]
    if data[:2] == b"\x1f\x8b":
        return decode_gzip(data)
    return decode_zlib(data)


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        sys.stderr.write(__doc__)
        return 2
    with open(args[0], "rb") as fh:
        data = fh.read()
    try:
        out = decode(data, raw="--raw" in argv)
    except (FormatError, IndexError, ValueError) as e:
        sys.stderr.write("inflate: %s\n" % e)
        return 1
    sys.stdout.buffer.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
