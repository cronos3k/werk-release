#!/usr/bin/env python3
"""wcode.py -- werk-hardcopy/1: the 2D matrix code, encoder and reference decoder.

This is BOTH halves of the hardcopy experiment's machinery:

  * the ENCODER, which turns a byte string into square black-and-white module
    matrices for printing, and
  * the REFERENCE DECODER, which is written *only* against what
    `docs/HARDCOPY-DRAFT.md` says in prose. It is the control: if this decoder
    needs a fact the printed prose does not state, the prose is wrong, and the
    experiment would be measuring the printout's luck rather than its
    self-description.

The symbol is deliberately NOT QR. See `docs/HARDCOPY-DRAFT.md` section 2 for
the argument; the short form is that the printed prose has to be sufficient to
implement a decoder from scratch, ISO/IEC 18004 is not implementable from one
page of prose, and a code that a stranger cannot implement from the paper it is
printed on defeats the entire point of the artifact.

Dependencies: stdlib only for encode/decode of matrices; Pillow for the image
paths (`render_symbol`, `decode_image`). No numpy.

SYMBOL GEOMETRY (the normative statement lives in the DRAFT; this is the same
thing in code)

    W = 99 modules on a side.
    ring 0  (r or c in {0, W-1})          SOLID BLACK -- the locator frame
    ring 1  (r or c in {1, W-2})          WHITE, except the three modules
                                          (1,1), (1,2), (2,1), which are BLACK:
                                          the orientation elbow, marking the
                                          top-left corner
    data    rows 2..W-3, cols 2..W-3      D = 95, so 9025 module positions

    9025 positions carry 1128 bytes (9024 bits) most-significant-bit first,
    row-major, left to right then top to bottom; black = 1. The one leftover
    position is written white and ignored.

CODEWORD LAYOUT (1128 bytes)

    0..1    0x57 0x4B          magic, "WK"
    2       0x01               version
    3       0x00 | 0x01        kind: 0 = data, 1 = parity
    4..5    u16 big-endian     seq, this symbol's index in the document
    6..7    u16 big-endian     total, symbols in the document
    8..11   u32 big-endian     file_len, length of the original file in bytes
    12..15  u32 big-endian     crc32 of bytes 0..11 followed by bytes 16..1127
    16..1127                   payload, 1112 bytes

SEQUENCING AND PARITY

    The file is zero-padded up to a multiple of 1112. Data symbols carry
    consecutive 1112-byte slices. After each group of at most K = 8 data
    symbols comes one parity symbol whose payload is the XOR of that group's
    data payloads, so any ONE lost or corrupt symbol per group is recoverable.
    `seq` counts every symbol, both kinds, in printed order.
"""

import struct
import zlib

MAGIC = b"\x57\x4b"
VERSION = 1
KIND_DATA = 0
KIND_PARITY = 1

W = 99                      # modules per side, including both rings
DATA_SIDE = W - 4           # 95
DATA_POSITIONS = DATA_SIDE * DATA_SIDE          # 9025
CODEWORD_BYTES = DATA_POSITIONS // 8            # 1128
HEADER_BYTES = 16
PAYLOAD_BYTES = CODEWORD_BYTES - HEADER_BYTES   # 1112
GROUP = 8                   # data symbols per parity symbol
QUIET = 4                   # white modules around the symbol


# --------------------------------------------------------------------------
# codewords
# --------------------------------------------------------------------------

def make_codeword(kind, seq, total, file_len, payload):
    if len(payload) != PAYLOAD_BYTES:
        raise ValueError("payload must be %d bytes" % PAYLOAD_BYTES)
    head = MAGIC + bytes([VERSION, kind]) + struct.pack(">HHI", seq, total, file_len)
    crc = zlib.crc32(head + payload) & 0xFFFFFFFF
    return head + struct.pack(">I", crc) + payload


def parse_codeword(cw):
    """-> dict, or None if it is not a well-formed, CRC-clean codeword."""
    if len(cw) != CODEWORD_BYTES or cw[0:2] != MAGIC or cw[2] != VERSION:
        return None
    kind = cw[3]
    seq, total, file_len = struct.unpack(">HHI", cw[4:12])
    crc = struct.unpack(">I", cw[12:16])[0]
    if (zlib.crc32(cw[0:12] + cw[16:]) & 0xFFFFFFFF) != crc:
        return None
    return {"kind": kind, "seq": seq, "total": total, "file_len": file_len,
            "crc": crc, "payload": cw[16:]}


def encode(data):
    """bytes -> [codeword bytes], in printed order."""
    file_len = len(data)
    n_data = max(1, -(-file_len // PAYLOAD_BYTES))
    padded = data + b"\x00" * (n_data * PAYLOAD_BYTES - file_len)
    slices = [padded[i * PAYLOAD_BYTES:(i + 1) * PAYLOAD_BYTES] for i in range(n_data)]
    n_groups = -(-n_data // GROUP)
    total = n_data + n_groups

    out, seq = [], 0
    for g in range(n_groups):
        grp = slices[g * GROUP:(g + 1) * GROUP]
        for s in grp:
            out.append(make_codeword(KIND_DATA, seq, total, file_len, s))
            seq += 1
        par = bytearray(PAYLOAD_BYTES)
        for s in grp:
            for i, b in enumerate(s):
                par[i] ^= b
        out.append(make_codeword(KIND_PARITY, seq, total, file_len, bytes(par)))
        seq += 1
    return out


def assemble(records):
    """[parsed codeword dicts] -> (bytes | None, report dict).

    Recovers at most one missing/corrupt symbol per group by XOR.
    """
    report = {"seen": len(records), "recovered_by_parity": [], "missing": []}
    if not records:
        return None, report
    total = records[0]["total"]
    file_len = records[0]["file_len"]
    by_seq = {}
    for r in records:
        if r["total"] != total or r["file_len"] != file_len:
            continue
        by_seq.setdefault(r["seq"], r)
    report["total"] = total
    report["file_len"] = file_len

    # groups are 8 data + 1 parity, in printed order; the last group may be short
    groups, base = [], 0
    while base < total:
        groups.append(list(range(base, min(base + GROUP + 1, total))))
        base += GROUP + 1
    parity_seqs = {g[-1] for g in groups}

    payloads = {}
    for members in groups:
        present = [s for s in members if s in by_seq]
        absent = [s for s in members if s not in by_seq]
        for s in present:
            payloads[s] = by_seq[s]["payload"]
        if len(absent) == 1:
            acc = bytearray(PAYLOAD_BYTES)
            for s in present:
                for i, b in enumerate(payloads[s]):
                    acc[i] ^= b
            payloads[absent[0]] = bytes(acc)
            report["recovered_by_parity"].append(absent[0])
        elif absent:
            report["missing"].extend(absent)

    if report["missing"]:
        return None, report

    data = b"".join(payloads[s] for s in range(total) if s not in parity_seqs)
    return data[:file_len], report


# --------------------------------------------------------------------------
# matrices
# --------------------------------------------------------------------------

def codeword_to_matrix(cw):
    """bytes -> W x W list of lists, 1 = black."""
    m = [[0] * W for _ in range(W)]
    for i in range(W):
        m[0][i] = m[W - 1][i] = m[i][0] = m[i][W - 1] = 1
    m[1][1] = m[1][2] = m[2][1] = 1
    bits = []
    for b in cw:
        for k in range(7, -1, -1):
            bits.append((b >> k) & 1)
    for i, bit in enumerate(bits):
        r, c = divmod(i, DATA_SIDE)
        m[2 + r][2 + c] = bit
    return m


def matrix_to_codeword(m):
    """W x W matrix -> bytes (the leftover position is discarded)."""
    bits = []
    for r in range(2, W - 2):
        for c in range(2, W - 2):
            bits.append(m[r][c])
    out = bytearray()
    for i in range(0, CODEWORD_BYTES * 8, 8):
        v = 0
        for k in range(8):
            v = (v << 1) | bits[i + k]
        out.append(v)
    return bytes(out)


def frame_score(m):
    """-> fraction of ring-0 positions that are black. A sanity gate."""
    ring = ([m[0][i] for i in range(W)] + [m[W - 1][i] for i in range(W)]
            + [m[i][0] for i in range(1, W - 1)] + [m[i][W - 1] for i in range(1, W - 1)])
    return sum(ring) / float(len(ring))


def elbow_corner(m):
    """Which corner carries the three-module orientation elbow: 0=TL,1=TR,2=BR,3=BL."""
    cands = [
        (m[1][1] + m[1][2] + m[2][1], 0),
        (m[1][W - 2] + m[1][W - 3] + m[2][W - 2], 1),
        (m[W - 2][W - 2] + m[W - 2][W - 3] + m[W - 3][W - 2], 2),
        (m[W - 2][1] + m[W - 2][2] + m[W - 3][1], 3),
    ]
    cands.sort(reverse=True)
    return cands[0][1]


def rot90(m):
    """Rotate the matrix 90 degrees clockwise."""
    n = len(m)
    return [[m[n - 1 - c][r] for c in range(n)] for r in range(n)]


# --------------------------------------------------------------------------
# rendering  (Pillow)
# --------------------------------------------------------------------------

def render_symbol(m, module_px):
    from PIL import Image
    side = (W + 2 * QUIET) * module_px
    img = Image.new("L", (side, side), 255)
    px = img.load()
    for r in range(W):
        for c in range(W):
            if not m[r][c]:
                continue
            x0 = (c + QUIET) * module_px
            y0 = (r + QUIET) * module_px
            for y in range(y0, y0 + module_px):
                for x in range(x0, x0 + module_px):
                    px[x, y] = 0
    return img


# --------------------------------------------------------------------------
# reference decoder  (Pillow, no numpy)
# --------------------------------------------------------------------------

def _binarize(img, tile=64):
    """-> (w, h, bytearray of 0/1 where 1 = ink), local midpoint threshold."""
    g = img.convert("L")
    w, h = g.size
    src = g.tobytes()
    tw = (w + tile - 1) // tile
    th = (h + tile - 1) // tile
    thr = [[0] * tw for _ in range(th)]
    for ty in range(th):
        for tx in range(tw):
            lo, hi = 255, 0
            y1 = min(h, (ty + 1) * tile)
            x0, x1 = tx * tile, min(w, (tx + 1) * tile)
            for y in range(ty * tile, y1, 2):
                row = src[y * w + x0:y * w + x1]
                if row:
                    a = min(row)
                    b = max(row)
                    if a < lo:
                        lo = a
                    if b > hi:
                        hi = b
            # a tile with no contrast is all paper or all ink; bias to paper
            thr[ty][tx] = (lo + hi) // 2 if hi - lo > 40 else -1
    # fill contrast-free tiles from the global midpoint
    flat = [v for row in thr for v in row if v >= 0]
    fallback = (sum(flat) // len(flat)) if flat else 128
    for ty in range(th):
        for tx in range(tw):
            if thr[ty][tx] < 0:
                thr[ty][tx] = fallback

    bits = bytearray(w * h)
    for y in range(h):
        ty = y // tile
        base = y * w
        row = thr[ty]
        for x in range(w):
            if src[base + x] < row[x // tile]:
                bits[base + x] = 1
    return w, h, bits


def _components(w, h, bits, step, min_side):
    """Connected components of ink on a `step`-subsampled grid.

    -> [(x0, y0, x1, y1)] full-resolution bounding boxes, big and roughly square.
    """
    sw, sh = w // step, h // step
    small = bytearray(sw * sh)
    for y in range(sh):
        for x in range(sw):
            if bits[(y * step) * w + (x * step)]:
                small[y * sw + x] = 1
    seen = bytearray(sw * sh)
    out = []
    for y0 in range(sh):
        for x0 in range(sw):
            i0 = y0 * sw + x0
            if not small[i0] or seen[i0]:
                continue
            stack = [i0]
            seen[i0] = 1
            xa = xb = x0
            ya = yb = y0
            n = 0
            while stack:
                i = stack.pop()
                n += 1
                y, x = divmod(i, sw)
                if x < xa:
                    xa = x
                if x > xb:
                    xb = x
                if y < ya:
                    ya = y
                if y > yb:
                    yb = y
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < sw and 0 <= ny < sh:
                        j = ny * sw + nx
                        if small[j] and not seen[j]:
                            seen[j] = 1
                            stack.append(j)
            bw = (xb - xa + 1) * step
            bh = (yb - ya + 1) * step
            if bw >= min_side and bh >= min_side and 0.75 <= bw / float(bh) <= 1.33:
                out.append((xa * step, ya * step, xb * step + step - 1,
                            yb * step + step - 1))
    return out


def _corners(w, h, bits, box, pad=12, min_blob=400):
    """The four corners of the frame, clockwise from the top-left-most.

    Three things here were MEASURED to be necessary, and all three are stated in
    the printed prose because a stranger would otherwise get them wrong exactly
    as this decoder first did:

    1. Corners are the extremes of x+y and x-y, NOT the topmost/leftmost/
       rightmost/bottommost pixels. At a rotation of one degree a 495-pixel edge
       five pixels thick has some three hundred pixels sharing the same smallest
       column, so "leftmost, and among ties the bottommost" picks a point most of
       the way down the edge and the sampling grid collapses.
    2. Isolated specks must be dropped. Sensor noise puts single dark pixels in
       the quiet zone and one of them moves a corner by tens of pixels.
    3. But the frame must NOT be assumed to be one connected piece. Under an
       illumination gradient the binarisation breaks it into several, so every
       surviving blob in the box contributes.
    """
    x0 = max(0, box[0] - pad)
    y0 = max(0, box[1] - pad)
    x1 = min(w - 1, box[2] + pad)
    y1 = min(h - 1, box[3] + pad)
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    seen = bytearray(bw * bh)
    a = b = c = d = None
    for sy in range(bh):
        for sx in range(bw):
            i0 = sy * bw + sx
            if seen[i0] or not bits[(y0 + sy) * w + (x0 + sx)]:
                continue
            stack = [i0]
            seen[i0] = 1
            blob = []
            while stack:
                i = stack.pop()
                blob.append(i)
                yy, xx = divmod(i, bw)
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = xx + dx, yy + dy
                    if 0 <= nx < bw and 0 <= ny < bh:
                        j = ny * bw + nx
                        if not seen[j] and bits[(y0 + ny) * w + (x0 + nx)]:
                            seen[j] = 1
                            stack.append(j)
            if len(blob) < min_blob:
                continue
            for i in blob:
                yy, xx = divmod(i, bw)
                p = (x0 + xx, y0 + yy)
                s1, s2 = p[0] + p[1], p[0] - p[1]
                if a is None or s1 < a[0] + a[1]:
                    a = p
                if b is None or s2 > b[0] - b[1]:
                    b = p
                if c is None or s1 > c[0] + c[1]:
                    c = p
                if d is None or s2 < d[0] - d[1]:
                    d = p
    if a is None:
        return None
    return [a, b, c, d]


def _sample(w, h, bits, corners):
    """Bilinear module sampling. corners are grid (0,0), (0,W-1), (W-1,W-1), (W-1,0)."""
    (ax, ay), (bx, by), (cx, cy), (dx, dy) = corners
    m = [[0] * W for _ in range(W)]
    for r in range(W):
        v = (r + 0.5) / W
        for c in range(W):
            u = (c + 0.5) / W
            x = ((1 - u) * (1 - v) * ax + u * (1 - v) * bx
                 + u * v * cx + (1 - u) * v * dx)
            y = ((1 - u) * (1 - v) * ay + u * (1 - v) * by
                 + u * v * cy + (1 - u) * v * dy)
            xi, yi = int(round(x)), int(round(y))
            n = 0
            for oy in (-1, 0, 1):
                for ox in (-1, 0, 1):
                    px, py = xi + ox, yi + oy
                    if 0 <= px < w and 0 <= py < h and bits[py * w + px]:
                        n += 1
            m[r][c] = 1 if n >= 5 else 0
    return m


def decode_image(path, step=4, min_side=300, verbose=False):
    """-> ([parsed codeword dicts], diagnostics dict)."""
    from PIL import Image
    img = Image.open(path)
    w, h, bits = _binarize(img)
    boxes = _components(w, h, bits, step, min_side)
    diag = {"boxes": len(boxes), "sampled": 0, "frame_reject": 0, "crc_fail": 0}
    out = []
    for box in boxes:
        corners = _corners(w, h, bits, box)
        if corners is None:
            continue
        m = _sample(w, h, bits, corners)
        if frame_score(m) < 0.90:
            diag["frame_reject"] += 1
            continue
        for _ in range(4):
            if elbow_corner(m) == 0:
                break
            m = rot90(m)
        diag["sampled"] += 1
        rec = parse_codeword(matrix_to_codeword(m))
        if rec is None:
            diag["crc_fail"] += 1
            if verbose:
                print("   symbol at %s: CRC/magic failed" % (box,))
            continue
        out.append(rec)
    return out, diag
