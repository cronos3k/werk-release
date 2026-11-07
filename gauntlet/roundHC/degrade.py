#!/usr/bin/env python3
"""degrade.py -- the "scanned" arm: what a photograph of the printout looks like.

The clean 300-DPI renders are what a printer receives. Nobody archaeologises a
print buffer; they photograph a sheet of paper under whatever light is in the
room. This applies, in this order and deterministically:

  1. a small ROTATION (0.5 to 1.0 degrees, alternating sign per sheet), on a
     paper-white canvas, with bicubic resampling
  2. a MILD BLUR (Gaussian, radius 1.1 px at 300 DPI -- about a quarter of a
     module), which is optical softness plus ink spread
  3. UNEVEN LIGHTING: a linear luminance ramp across the diagonal, 100 % at the
     bright corner falling to 62 % at the dark one, plus a broad vignette
  4. NOISE: zero-mean additive noise, standard deviation 9 of 255, from a seeded
     Mersenne Twister so the arm is reproducible
  5. a JPEG round trip at quality 82, because a photograph arrives as a JPEG

Every value is stated here rather than tuned until the decoder passed: they were
chosen once, from what a phone photograph of a laser print actually looks like,
and the reference decoder was then run against the result. If the degradation
had defeated the decoder that would have been the finding.

Usage:  python degrade.py [--src pages/clean] [--out pages/scanned]
"""

import argparse
import math
import os
import random

from PIL import Image, ImageFilter

ANGLES = [0.7, -0.55, 0.9, -0.8, 0.6, -0.95]
BLUR_RADIUS = 1.1
NOISE_SD = 9.0
DARKEST = 0.62
JPEG_QUALITY = 82
SEED = 20260809


def degrade(img, angle, rng):
    img = img.convert("L")
    img = img.rotate(angle, resample=Image.BICUBIC, fillcolor=255)
    img = img.filter(ImageFilter.GaussianBlur(BLUR_RADIUS))

    w, h = img.size
    px = bytearray(img.tobytes())
    # a diagonal illumination ramp plus a soft vignette, then noise
    cx, cy = w / 2.0, h / 2.0
    rmax = math.hypot(cx, cy)
    for y in range(h):
        fy = y / float(h - 1)
        base = y * w
        for x in range(w):
            fx = x / float(w - 1)
            ramp = 1.0 - (1.0 - DARKEST) * (0.55 * fx + 0.45 * fy)
            r = math.hypot(x - cx, y - cy) / rmax
            vig = 1.0 - 0.14 * r * r
            v = px[base + x] * ramp * vig + rng.gauss(0.0, NOISE_SD)
            px[base + x] = 0 if v < 0 else (255 if v > 255 else int(v))
    return Image.frombytes("L", (w, h), bytes(px))


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(here, "pages", "clean"))
    ap.add_argument("--out", default=os.path.join(here, "pages", "scanned"))
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    rng = random.Random(SEED)
    names = sorted(n for n in os.listdir(args.src) if n.endswith(".png"))
    for i, name in enumerate(names):
        img = Image.open(os.path.join(args.src, name))
        out = degrade(img, ANGLES[i % len(ANGLES)], rng)
        dst = os.path.join(args.out, name.replace(".png", ".jpg"))
        out.save(dst, "JPEG", quality=JPEG_QUALITY, dpi=(300, 300))
        print("%s -> %s  (rotation %+.2f deg, %d bytes)"
              % (name, os.path.basename(dst), ANGLES[i % len(ANGLES)],
                 os.path.getsize(dst)))


if __name__ == "__main__":
    main()
