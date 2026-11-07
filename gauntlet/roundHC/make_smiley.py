#!/usr/bin/env python3
"""make_smiley.py -- the payload's one picture, generated deterministically.

A 64x64 indexed-colour PNG of a smiling face. Written by hand out of `zlib` and
`struct` rather than by an imaging library, for two reasons:

  1. **Determinism.** The bytes must be identical on every machine and in every
     future run, because the whole hardcopy experiment is graded on a sha256.
     An imaging library's encoder is free to change its filter heuristics or
     its zlib settings between versions; this file's is pinned here.
  2. **No dependency.** `gauntlet/roundHC/` is a pipeline-side tool tree, and
     the fewer moving parts between "run the script" and "these exact bytes"
     the better.

Colour type 3 (palette) with a 3-entry palette and bit depth 8: 4096 raw pixel
bytes plus 64 filter bytes, which deflates to a few hundred. That matters here
in a way it usually does not -- every byte of the payload becomes ink.

Usage:  python make_smiley.py [--out smiley.png]
"""

import argparse
import hashlib
import os
import struct
import zlib

W = H = 64

#: index -> RGB. 0 white (paper), 1 yellow (face), 2 black (ink).
PALETTE = [(255, 255, 255), (255, 205, 0), (0, 0, 0)]

WHITE, YELLOW, BLACK = 0, 1, 2


def draw():
    """-> H rows of W palette indices. Pure integer arithmetic, no floats."""
    px = [[WHITE] * W for _ in range(H)]

    # face: filled disc, centre (31.5, 31.5), radius 30, with a 2px black rim.
    # Distances are compared in doubled integer coordinates so the centre is
    # exact: cx = 63, cy = 63 in units of half a pixel.
    cx = cy = 63
    r_out = 60          # 30.0 px, doubled
    r_in = 56           # 28.0 px, doubled
    for y in range(H):
        dy = 2 * y + 1 - cy
        for x in range(W):
            dx = 2 * x + 1 - cx
            d2 = dx * dx + dy * dy
            if d2 <= r_in * r_in:
                px[y][x] = YELLOW
            elif d2 <= r_out * r_out:
                px[y][x] = BLACK

    # eyes: two filled discs, radius 3, at (21, 24) and (42, 24)
    for ex in (21, 42):
        for y in range(H):
            for x in range(W):
                if (x - ex) ** 2 + (y - 24) ** 2 <= 9:
                    px[y][x] = BLACK

    # mouth: an arc of the circle of radius 18 about (31.5, 28.5), kept to the
    # lower half, drawn 3 px thick.
    mcx, mcy = 63, 57   # doubled
    for y in range(H):
        dy = 2 * y + 1 - mcy
        if dy <= 0:
            continue
        for x in range(W):
            dx = 2 * x + 1 - mcx
            d2 = dx * dx + dy * dy
            if 32 * 32 <= d2 <= 38 * 38 and dy * dy * 4 >= d2:
                px[y][x] = BLACK
    return px


def png_bytes(px):
    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 3, 0, 0, 0)
    plte = b"".join(struct.pack("BBB", *c) for c in PALETTE)
    raw = b"".join(b"\x00" + bytes(row) for row in px)
    idat = zlib.compress(raw, 9)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"PLTE", plte)
            + chunk(b"IDAT", idat) + chunk(b"IEND", b""))


def build():
    return png_bytes(draw())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "smiley.png"))
    args = ap.parse_args()
    b = build()
    with open(args.out, "wb") as fh:
        fh.write(b)
    print("wrote %s" % args.out)
    print("  %d bytes, sha256 %s" % (len(b), hashlib.sha256(b).hexdigest()))


if __name__ == "__main__":
    main()
