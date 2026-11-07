#!/usr/bin/env python3
"""make_pages.py -- render the werk-hardcopy/1 printout.

Three A4 sheets at 300 DPI (2480 x 3508 px):

    sheet 1, 2   the PROSE TIER, from `prose/PROSE.txt`, laid out in a monospace
                 face at a size a phone camera reads without effort. Sheets 1
                 and 2 together are the complete description of the code on
                 sheet 3 -- geometry, sampling, codeword layout, CRC-32 with a
                 test vector, parity, reassembly -- plus the recovered file's
                 SHA-256 and a paragraph on what the file is.
    sheet 3      the PAYLOAD TIER: nine werk-hardcopy/1 symbols in a 3 x 3 grid,
                 each with its sequence number, kind, total and CRC printed in
                 plain text beneath it.

Deterministic given the payload file and the font. Dependencies: Pillow, and one
monospace TrueType face (Consolas on Windows, DejaVu Sans Mono elsewhere) --
recorded rather than vendored because this is a pipeline-side tool, not part of
any package.

Usage:  python make_pages.py [--payload smiley-v1.werk] [--out pages/clean]
"""

import argparse
import hashlib
import os

from PIL import Image, ImageDraw, ImageFont

import wcode

HERE = os.path.dirname(os.path.abspath(__file__))

DPI = 300
PW, PH = 2480, 3508          # A4 at 300 DPI
MODULE_PX = 6                # 0.51 mm at 300 DPI
PROSE_MARGIN_X = 100
PROSE_MARGIN_Y = 130
PROSE_PT = 7.8
PROSE_LEADING = 39
BOTTOM_MARGIN = 60

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\consola.ttf",
    r"C:\Windows\Fonts\cour.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
]


def mono(px):
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return ImageFont.truetype(p, int(px)), p
    raise SystemExit("no monospace TrueType font found; tried %s" % FONT_CANDIDATES)


def prose_page(lines, font, leading):
    """-> (image, y cursor just under the last line)."""
    img = Image.new("L", (PW, PH), 255)
    d = ImageDraw.Draw(img)
    y = PROSE_MARGIN_Y
    for ln in lines:
        d.text((PROSE_MARGIN_X, y), ln.rstrip("\n"), font=font, fill=0)
        y += leading
    return img, y


def draw_symbols(img, y0, codewords, sha_hex, font):
    """The payload tier, drawn onto an existing sheet under the prose."""
    d = ImageDraw.Draw(img)
    block = (wcode.W + 2 * wcode.QUIET) * MODULE_PX
    cols = 3
    gap = 28
    cap_h = 44
    pitch = block + cap_h
    grid_w = cols * block + (cols - 1) * gap
    x0 = (PW - grid_w) // 2

    for i, cw in enumerate(codewords):
        rec = wcode.parse_codeword(cw)
        sym = wcode.render_symbol(wcode.codeword_to_matrix(cw), MODULE_PX)
        r, c = divmod(i, cols)
        x = x0 + c * (block + gap)
        y = y0 + r * pitch
        img.paste(sym, (x, y))
        cap = "SEQ %d/%d %s CRC %08X" % (
            rec["seq"], rec["total"], "DATA" if rec["kind"] == 0 else "PARITY",
            rec["crc"])
        d.text((x + wcode.QUIET * MODULE_PX, y + block + 4), cap, font=font, fill=0)

    rows = -(-len(codewords) // cols)
    fy = y0 + rows * pitch + 16
    d.text((PROSE_MARGIN_X, fy), "SHA-256 of the recovered file:  "
           + " ".join(sha_hex[i:i + 8] for i in range(0, 64, 8)), font=font, fill=0)
    return fy + PROSE_LEADING


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--payload", default=os.path.join(HERE, "smiley-v1.werk"))
    ap.add_argument("--out", default=os.path.join(HERE, "pages", "clean"))
    args = ap.parse_args()

    data = open(args.payload, "rb").read()
    sha = hashlib.sha256(data).hexdigest()
    codewords = wcode.encode(data)

    prose = open(os.path.join(HERE, "prose", "PROSE.txt"), encoding="utf-8").read()
    # sheets are separated by a line holding the two characters \f
    sheets = [s for s in prose.split("\n\\f\n") if s.strip()]

    px = PROSE_PT * DPI / 72.0
    font, font_path = mono(px)
    leading = PROSE_LEADING

    os.makedirs(args.out, exist_ok=True)
    widest = 0
    for i, sheet in enumerate(sheets):
        lines = sheet.strip("\n").split("\n")
        widest = max(widest, max(len(l) for l in lines))
        img, y = prose_page(lines, font, leading)
        if i == len(sheets) - 1:
            y = draw_symbols(img, y + 20, codewords, sha, font)
        if y > PH - BOTTOM_MARGIN:
            raise SystemExit("sheet %d overflows: needs %d px, has %d"
                             % (i + 1, y, PH - BOTTOM_MARGIN))
        img.save(os.path.join(args.out, "page-%02d.png" % (i + 1)), dpi=(DPI, DPI))

    block = (wcode.W + 2 * wcode.QUIET) * MODULE_PX
    print("payload      %s" % args.payload)
    print("  %d bytes, sha256 %s" % (len(data), sha))
    print("  %d symbols (%d data + %d parity), %d payload bytes each"
          % (len(codewords), sum(1 for c in codewords if c[3] == 0),
             sum(1 for c in codewords if c[3] == 1), wcode.PAYLOAD_BYTES))
    print("font         %s at %.1f pt (%.0f px), leading %d px, widest line %d chars"
          % (font_path, PROSE_PT, px, leading, widest))
    print("symbol       %d modules + %d quiet, %d px/module -> %d px (%.1f mm)"
          % (wcode.W, wcode.QUIET, MODULE_PX, block, block * 25.4 / DPI))
    print("module       %.3f mm" % (MODULE_PX * 25.4 / DPI))
    print("sheets       %d prose + 1 payload = %d, A4 at %d DPI"
          % (len(sheets) - 1, 1, DPI))
    print("density      %d bytes/symbol, 9 symbols/sheet -> %d file bytes per "
          "payload sheet" % (wcode.PAYLOAD_BYTES, 8 * wcode.PAYLOAD_BYTES))
    print("wrote        %s" % args.out)


if __name__ == "__main__":
    main()
