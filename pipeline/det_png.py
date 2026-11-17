"""det_png.py -- a PNG encoder whose bytes depend on the pixels and nothing else.

Why this exists (finding N3 of the release evidence, measured 2026-11-07): the
image fixtures were encoded by Pillow, and Pillow hands the IDAT stream to
whichever zlib its wheel links. The Windows wheel links zlib-ng, the Linux
wheel stock zlib, and the two write different deflate streams for the same
pixels, so one builder produced one fixture on Windows and another on Linux.
A pinned Pillow version is not enough to fix that; a pinned *encoder* is.

So the deflate stream here is written by this file, in pure Python, by a fixed
algorithm with no tunable that a platform could set differently:

* PNG filter per scanline: the one of the five (None, Sub, Up, Average,
  Paeth) with the smallest sum of absolute values of the filtered bytes taken
  as signed, ties to the lower filter number -- libpng's documented heuristic,
  done in integer arithmetic.
* LZ77: greedy, window 32 768, matches 3..258 bytes, one candidate per
  position (the most recent position with the same three bytes), the match
  length found by comparing slices; positions inside a match are not indexed.
* Huffman: one dynamic block per 65 536 symbols, code lengths limited to 15
  (7 for the code-length code) by the Kraft repair zlib and miniz use, ties
  broken by symbol number; RLE of the code lengths with codes 16, 17 and 18.

`zlib` is used only for `crc32` and `adler32`, which are fixed mathematical
functions (MINI-SPECS.md section 6), never for compression. The output is a
valid PNG (decoded by any PNG reader; the tests decode it with Pillow and with
zlib and compare every pixel) and is the same bytes on every OS and every
Python >= 3.8. It is smaller than stored blocks (spec/WRITING-IMAGE.md's
minimal writer) and larger than zlib level 6; size is not the point.
"""

import struct
import zlib

__all__ = ["encode_png", "deflate_zlib", "ENCODER_ID"]

#: what a package records as the encoder of a PNG this module wrote
ENCODER_ID = "werk pipeline/det_png.py 1 (pure-Python deflate, fixed algorithm)"

# --- deflate tables (RFC 1951 section 3.2.5) ---------------------------------
_LEN_BASE = [3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51,
             59, 67, 83, 99, 115, 131, 163, 195, 227, 258]
_LEN_EXTRA = [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4,
              4, 5, 5, 5, 5, 0]
_DIST_BASE = [1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385,
              513, 769, 1025, 1537, 2049, 3073, 4097, 6145, 8193, 12289, 16385,
              24577]
_DIST_EXTRA = [0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10,
               10, 11, 11, 12, 12, 13, 13]
_CL_ORDER = [16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15]

# length 3..258 -> (code index 0..28)
_LEN_CODE = [0] * 259
for _i, _b in enumerate(_LEN_BASE):
    _top = _LEN_BASE[_i + 1] if _i + 1 < len(_LEN_BASE) else 259
    for _l in range(_b, min(_top, 259)):
        _LEN_CODE[_l] = _i
_LEN_CODE[258] = 28


def _dist_code(d):
    # binary search over _DIST_BASE
    lo, hi = 0, 29
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if _DIST_BASE[mid] <= d:
            lo = mid
        else:
            hi = mid - 1
    return lo


class _Bits(object):
    __slots__ = ("out", "acc", "n")

    def __init__(self):
        self.out = bytearray()
        self.acc = 0
        self.n = 0

    def put(self, value, nbits):
        """LSB-first, as deflate packs everything but Huffman codes."""
        self.acc |= value << self.n
        self.n += nbits
        while self.n >= 8:
            self.out.append(self.acc & 0xFF)
            self.acc >>= 8
            self.n -= 8

    def flush(self):
        if self.n:
            self.out.append(self.acc & 0xFF)
        self.acc = 0
        self.n = 0


def _huffman_lengths(freqs, limit):
    """Code lengths for `freqs` (list of ints), every length <= limit.
    Deterministic: ties broken by symbol number."""
    syms = [s for s, f in enumerate(freqs) if f]
    lengths = [0] * len(freqs)
    if not syms:
        return lengths
    if len(syms) == 1:
        lengths[syms[0]] = 1
        return lengths
    # Huffman tree by repeated merge of the two lightest; ties by (weight,
    # smallest symbol in the subtree), which is a total order.
    import heapq
    heap = [(freqs[s], s, s) for s in syms]       # (weight, order key, node)
    heapq.heapify(heap)
    parent = {}
    nxt = len(freqs)
    while len(heap) > 1:
        w1, k1, n1 = heapq.heappop(heap)
        w2, k2, n2 = heapq.heappop(heap)
        parent[n1] = nxt
        parent[n2] = nxt
        heapq.heappush(heap, (w1 + w2, min(k1, k2), nxt))
        nxt += 1
    depth = {}
    for s in syms:
        d, n = 0, s
        while n in parent:
            n = parent[n]
            d += 1
        depth[s] = d
    # Limit: histogram of lengths, Kraft repair (miniz / zlib), then hand the
    # lengths out again, shortest to the most frequent symbol.
    maxlen = max(depth.values())
    count = [0] * (max(maxlen, limit) + 1)
    for s in syms:
        count[depth[s]] += 1
    if maxlen > limit:
        for i in range(limit + 1, maxlen + 1):
            count[limit] += count[i]
            count[i] = 0
        total = sum(count[i] << (limit - i) for i in range(1, limit + 1))
        while total != (1 << limit):
            count[limit] -= 1
            for i in range(limit - 1, 0, -1):
                if count[i]:
                    count[i] -= 1
                    count[i + 1] += 2
                    break
            total -= 1
    order = sorted(syms, key=lambda s: (-freqs[s], s))
    pos = 0
    for L in range(1, limit + 1):
        for _ in range(count[L] if L < len(count) else 0):
            lengths[order[pos]] = L
            pos += 1
    return lengths


def _canonical(lengths):
    """lengths -> codes, already bit-reversed for LSB-first emission."""
    maxl = max(lengths) if lengths else 0
    bl_count = [0] * (maxl + 1)
    for L in lengths:
        if L:
            bl_count[L] += 1
    code = 0
    next_code = [0] * (maxl + 2)
    for bits in range(1, maxl + 1):
        code = (code + bl_count[bits - 1]) << 1 if bits > 1 else 0
        next_code[bits] = code
    codes = [0] * len(lengths)
    for s, L in enumerate(lengths):
        if L:
            c = next_code[L]
            next_code[L] += 1
            r = 0
            for _ in range(L):
                r = (r << 1) | (c & 1)
                c >>= 1
            codes[s] = r
    return codes


def _lz77(data):
    """-> list of symbols: int literal (0..255) or (length, distance)."""
    n = len(data)
    head = {}
    out = []
    i = 0
    mv = data
    while i < n:
        if i + 3 <= n:
            key = mv[i:i + 3]
            cand = head.get(key)
            head[key] = i
            if cand is not None and i - cand <= 32768:
                maxlen = min(258, n - i)
                # longest L with data[cand:cand+L] == data[i:i+L]; the
                # predicate is monotone in L, so a binary search is exact.
                lo, hi = 3, maxlen
                while lo < hi:
                    mid = (lo + hi + 1) // 2
                    if mv[cand:cand + mid] == mv[i:i + mid]:
                        lo = mid
                    else:
                        hi = mid - 1
                out.append((lo, i - cand))
                i += lo
                continue
        out.append(mv[i])
        i += 1
    return out


def _write_block(bits, syms, final):
    lit_f = [0] * 286
    dist_f = [0] * 30
    for s in syms:
        if s.__class__ is int:
            lit_f[s] += 1
        else:
            lit_f[257 + _LEN_CODE[s[0]]] += 1
            dist_f[_dist_code(s[1])] += 1
    lit_f[256] = 1
    # Some inflaters reject a distance tree with fewer than two codes; give
    # it two, deterministically.
    used = [d for d in range(30) if dist_f[d]]
    for d in (0, 1):
        if len(used) >= 2:
            break
        if not dist_f[d]:
            dist_f[d] = 1
            used.append(d)
    lit_l = _huffman_lengths(lit_f, 15)
    dist_l = _huffman_lengths(dist_f, 15)
    hlit = 286
    while hlit > 257 and lit_l[hlit - 1] == 0:
        hlit -= 1
    hdist = 30
    while hdist > 1 and dist_l[hdist - 1] == 0:
        hdist -= 1
    seq = lit_l[:hlit] + dist_l[:hdist]
    # RLE of the code lengths (RFC 1951 3.2.7)
    rle = []
    i = 0
    while i < len(seq):
        L = seq[i]
        run = 1
        while i + run < len(seq) and seq[i + run] == L:
            run += 1
        if L == 0 and run >= 3:
            r = run
            while r >= 3:
                if r >= 11:
                    k = min(r, 138)
                    rle.append((18, k - 11))
                else:
                    k = r
                    rle.append((17, k - 3))
                r -= k
            for _ in range(r):
                rle.append((0, None))
            i += run
            continue
        if L != 0 and run >= 4:
            rle.append((L, None))
            r = run - 1
            while r >= 3:
                k = min(r, 6)
                rle.append((16, k - 3))
                r -= k
            for _ in range(r):
                rle.append((L, None))
            i += run
            continue
        rle.append((L, None))
        i += 1
    cl_f = [0] * 19
    for c, _x in rle:
        cl_f[c] += 1
    cl_l = _huffman_lengths(cl_f, 7)
    hclen = 19
    while hclen > 4 and cl_l[_CL_ORDER[hclen - 1]] == 0:
        hclen -= 1
    lit_c = _canonical(lit_l)
    dist_c = _canonical(dist_l)
    cl_c = _canonical(cl_l)

    bits.put(1 if final else 0, 1)
    bits.put(2, 2)
    bits.put(hlit - 257, 5)
    bits.put(hdist - 1, 5)
    bits.put(hclen - 4, 4)
    for k in range(hclen):
        bits.put(cl_l[_CL_ORDER[k]], 3)
    for c, x in rle:
        bits.put(cl_c[c], cl_l[c])
        if c == 16:
            bits.put(x, 2)
        elif c == 17:
            bits.put(x, 3)
        elif c == 18:
            bits.put(x, 7)
    put = bits.put
    for s in syms:
        if s.__class__ is int:
            put(lit_c[s], lit_l[s])
        else:
            length, dist = s
            lc = _LEN_CODE[length]
            put(lit_c[257 + lc], lit_l[257 + lc])
            if _LEN_EXTRA[lc]:
                put(length - _LEN_BASE[lc], _LEN_EXTRA[lc])
            dc = _dist_code(dist)
            put(dist_c[dc], dist_l[dc])
            if _DIST_EXTRA[dc]:
                put(dist - _DIST_BASE[dc], _DIST_EXTRA[dc])
    put(lit_c[256], lit_l[256])


def deflate_raw(data, block_symbols=65536):
    data = bytes(data)
    syms = _lz77(data)
    bits = _Bits()
    if not syms:
        _write_block(bits, [], True)
    for k in range(0, len(syms), block_symbols):
        chunk = syms[k:k + block_symbols]
        _write_block(bits, chunk, k + block_symbols >= len(syms))
    bits.flush()
    return bytes(bits.out)


def deflate_zlib(data):
    """A zlib stream (RFC 1950): CMF 0x78, FLG 0x01 (no dictionary, the
    'fastest' level hint: the hint is informative only), raw deflate,
    big-endian Adler-32."""
    return (b"\x78\x01" + deflate_raw(data)
            + struct.pack(">I", zlib.adler32(bytes(data)) & 0xFFFFFFFF))


def _filter_rows(raw_rows, bpp):
    """raw_rows: list of bytes (one per scanline, no filter byte).
    -> bytes of the filtered image, each row prefixed by its filter type."""
    out = bytearray()
    prev = bytes(len(raw_rows[0])) if raw_rows else b""
    for row in raw_rows:
        n = len(row)
        cands = []
        # 0 None
        cands.append(bytes(row))
        # 1 Sub
        cands.append(bytes((row[i] - (row[i - bpp] if i >= bpp else 0)) & 0xFF
                           for i in range(n)))
        # 2 Up
        cands.append(bytes((row[i] - prev[i]) & 0xFF for i in range(n)))
        # 3 Average
        cands.append(bytes((row[i] - (((row[i - bpp] if i >= bpp else 0) + prev[i]) >> 1))
                           & 0xFF for i in range(n)))
        # 4 Paeth
        pa_row = bytearray(n)
        for i in range(n):
            a = row[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            p = a + b - c
            pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
            pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
            pa_row[i] = (row[i] - pr) & 0xFF
        cands.append(bytes(pa_row))
        best, best_cost = 0, None
        for ft, cand in enumerate(cands):
            cost = sum(v if v < 128 else 256 - v for v in cand)
            if best_cost is None or cost < best_cost:
                best, best_cost = ft, cost
        out.append(best)
        out += cands[best]
        prev = row
    return bytes(out)


def _filter_rows_np(raw, height, stride, bpp):
    """The same filter choice as _filter_rows, vectorised with numpy (integer
    arithmetic only, so the bytes are identical to the pure-Python path)."""
    import numpy as np
    a8 = np.frombuffer(raw, dtype=np.uint8).reshape(height, stride)
    x = a8.astype(np.int32)
    up = np.zeros_like(x)
    up[1:] = x[:-1]
    left = np.zeros_like(x)
    left[:, bpp:] = x[:, :-bpp]
    upleft = np.zeros_like(x)
    upleft[1:, bpp:] = x[:-1, :-bpp]
    p = left + up - upleft
    pa, pb, pc = np.abs(p - left), np.abs(p - up), np.abs(p - upleft)
    paeth = np.where((pa <= pb) & (pa <= pc), left, np.where(pb <= pc, up, upleft))
    cands = [x, x - left, x - up, x - ((left + up) >> 1), x - paeth]
    cands = [(c & 0xFF).astype(np.uint8) for c in cands]
    costs = []
    for c in cands:
        s = c.astype(np.int32)
        costs.append(np.where(s < 128, s, 256 - s).sum(axis=1))
    costs = np.stack(costs, axis=1)              # (height, 5)
    best = np.argmin(costs, axis=1)              # first minimum = lowest type
    out = bytearray()
    for r in range(height):
        ft = int(best[r])
        out.append(ft)
        out += cands[ft][r].tobytes()
    return bytes(out)


def encode_png(raw, width, height, color_type, bit_depth=8):
    """raw: the unfiltered scanline bytes, row-major, top row first (for
    16-bit samples, big-endian as PNG stores them). color_type 0 (grey),
    2 (RGB) or 6 (RGBA). -> PNG bytes."""
    ch = {0: 1, 2: 3, 4: 2, 6: 4}[color_type]
    bpp = max(1, ch * bit_depth // 8)
    stride = width * ch * bit_depth // 8
    raw = bytes(raw)
    assert len(raw) == stride * height, (len(raw), stride, height)
    try:
        import numpy  # noqa: F401
        filt = _filter_rows_np(raw, height, stride, bpp)
    except ImportError:
        filt = _filter_rows([raw[r * stride:(r + 1) * stride] for r in range(height)],
                            bpp)

    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, bit_depth, color_type, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", deflate_zlib(filt)) + chunk(b"IEND", b""))


def encode_pil(img):
    """A Pillow image (mode L, RGB, RGBA or I;16) -> PNG bytes by this
    encoder. Pillow supplies the pixels only."""
    mode = img.mode
    w, h = img.size
    if mode == "RGB":
        return encode_png(img.tobytes(), w, h, 2)
    if mode == "RGBA":
        return encode_png(img.tobytes(), w, h, 6)
    if mode == "L":
        return encode_png(img.tobytes(), w, h, 0)
    if mode in ("I;16", "I;16L"):
        le = img.tobytes()
        be = bytearray(len(le))
        be[0::2] = le[1::2]
        be[1::2] = le[0::2]
        return encode_png(bytes(be), w, h, 0, 16)
    raise ValueError("det_png: unsupported Pillow mode %r" % mode)
