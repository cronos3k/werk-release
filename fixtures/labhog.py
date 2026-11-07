#!/usr/bin/env python3
"""labhog.py — a complete implementation of `werk.descriptor.labhog/1`.

This is the executable statement of `spec/layouts/embedding.layout.txt` §4.
Where a sentence in that file is ambiguous, this code is what it means — and
where this code and that file disagree, the layout file wins and this file is
the bug (the same relationship `spec/examples/make-examples.py` has with the
other layout grammars).

The descriptor exists so that a `core.embedding` node can be **measured**
rather than asserted: everything below is arithmetic over the source image, so
a reader holding that image can recompute the vector and check it, which is
law 5's validate-or-recompute applied to a field that normally cannot be
checked at all. It is not a neural embedding and does not pretend to be one.

Requires numpy (for an exact integral-image box resample over a multi-megapixel
raster) and Pillow (to decode the raster). NEITHER SHIPS INSIDE A WERK
PACKAGE: this is a builder, not a `core.loader`, and law 1's dependency ban
applies to what travels in the file.

    python fixtures/labhog.py <image.png>      # prints the 72 components
"""

import math
import sys

import numpy as np

GRID = 32          # the descriptor's working resolution
COLOUR_BINS = 64   # 4 x 4 x 4 in CIELAB
ORIENT_BINS = 8
DIM = COLOUR_BINS + ORIENT_BINS      # 72
SWATCHES = 8
MODEL_ID = "werk.descriptor.labhog/1"
TOLERANCE = 1e-6

# sRGB (D65) -> CIE XYZ. Values as printed in the layout file, digit for digit.
M_RGB_XYZ = np.array([
    [0.4124564, 0.3575761, 0.1804375],
    [0.2126729, 0.7151522, 0.0721750],
    [0.0193339, 0.1191920, 0.9503041],
], dtype=np.float64)
WHITE = np.array([0.95047, 1.00000, 1.08883], dtype=np.float64)


def box_resample(rgb):
    """Step 1 — exact box average to GRID x GRID, in binary64.

    The integral image is built with cumsum over float64 on integer-valued
    data, so every partial sum is exact (a 8-bit raster of any plausible size
    sums to far less than 2**53) and the only rounding is the final divide.
    """
    h, w, _ = rgb.shape
    ii = np.zeros((h + 1, w + 1, 3), dtype=np.float64)
    ii[1:, 1:, :] = rgb.astype(np.float64).cumsum(axis=0).cumsum(axis=1)

    out = np.zeros((GRID, GRID, 3), dtype=np.float64)
    for cy in range(GRID):
        y0 = (cy * h) // GRID
        y1 = ((cy + 1) * h) // GRID
        if y1 <= y0:
            y1 = min(y0 + 1, h)
        for cx in range(GRID):
            x0 = (cx * w) // GRID
            x1 = ((cx + 1) * w) // GRID
            if x1 <= x0:
                x1 = min(x0 + 1, w)
            total = ii[y1, x1] - ii[y0, x1] - ii[y1, x0] + ii[y0, x0]
            out[cy, cx] = total / float((y1 - y0) * (x1 - x0))
    return out


def srgb_to_linear(c255):
    """Step 2."""
    s = c255 / 255.0
    return np.where(s <= 0.04045, s / 12.92, ((s + 0.055) / 1.055) ** 2.4)


def linear_to_lab(lin):
    """Steps 3 and 4. `lin` is (..., 3) linear sRGB in [0,1]."""
    xyz = lin @ M_RGB_XYZ.T
    t = xyz / WHITE
    eps = 216.0 / 24389.0
    f = np.where(t > eps, np.cbrt(t), (841.0 / 108.0) * t + 4.0 / 29.0)
    lab = np.empty_like(f)
    lab[..., 0] = 116.0 * f[..., 1] - 16.0
    lab[..., 1] = 500.0 * (f[..., 0] - f[..., 1])
    lab[..., 2] = 200.0 * (f[..., 1] - f[..., 2])
    return lab


def _clamp_bin(v, lo, step, hi_index):
    idx = int(math.floor((v - lo) / step))
    return max(0, min(hi_index, idx))


def descriptor(image):
    """Return (vector[72] float64, palette[8][4] float64, diagnostics dict).

    `image` is a PIL.Image. Alpha is ignored (layout file §4), which the
    profile's images do not have anyway.
    """
    rgb = np.asarray(image.convert("RGB"))
    cells = box_resample(rgb)                       # (32,32,3) in [0,255]
    lin = srgb_to_linear(cells)                     # (32,32,3) in [0,1]
    lab = linear_to_lab(lin)                        # (32,32,3)

    # -- step 5: the 4x4x4 CIELAB histogram ------------------------------
    counts = np.zeros(COLOUR_BINS, dtype=np.int64)
    lin_sum = np.zeros((COLOUR_BINS, 3), dtype=np.float64)
    bin_of = np.zeros((GRID, GRID), dtype=np.int64)
    for y in range(GRID):
        for x in range(GRID):
            L, a, b = lab[y, x]
            lb = _clamp_bin(L, 0.0, 25.0, 3)
            ab = _clamp_bin(a + 100.0, 0.0, 50.0, 3)
            bb = _clamp_bin(b + 100.0, 0.0, 50.0, 3)
            idx = 16 * lb + 4 * ab + bb
            bin_of[y, x] = idx
            counts[idx] += 1
            lin_sum[idx] += lin[y, x]
    cells_total = float(GRID * GRID)
    colour = counts.astype(np.float64) / cells_total

    # -- step 6: the 8-bin gradient orientation histogram ----------------
    Lp = np.pad(lab[:, :, 0], 1, mode="edge")
    kx = np.array([[-1.0, 0.0, 1.0], [-2.0, 0.0, 2.0], [-1.0, 0.0, 1.0]])
    ky = np.array([[-1.0, -2.0, -1.0], [0.0, 0.0, 0.0], [1.0, 2.0, 1.0]])
    orient = np.zeros(ORIENT_BINS, dtype=np.float64)
    for y in range(GRID):
        for x in range(GRID):
            win = Lp[y:y + 3, x:x + 3]
            gx = float((win * kx).sum())
            gy = float((win * ky).sum())
            m = math.sqrt(gx * gx + gy * gy)
            t = math.atan2(gy, gx)
            if t < 0.0:
                t += math.pi
            if t >= math.pi:
                t -= math.pi
            k = max(0, min(ORIENT_BINS - 1, int(math.floor(t * ORIENT_BINS / math.pi))))
            orient[k] += m
    mag_total = float(orient.sum())
    if mag_total > 0.0:
        orient = orient / mag_total

    # -- steps 7 and 8: concatenate, L2-normalise ------------------------
    vec = np.concatenate([colour, orient])
    norm = math.sqrt(float((vec * vec).sum()))
    if norm > 0.0:
        vec = vec / norm

    # -- step 9: the palette ---------------------------------------------
    # Largest counts first, ties broken by ASCENDING bin index. Python's sort
    # is stable, so sorting the ascending index list by -count does exactly
    # that, and does it the same way on every machine.
    order = sorted(range(COLOUR_BINS), key=lambda i: -counts[i])[:SWATCHES]
    palette = np.zeros((SWATCHES, 4), dtype=np.float64)
    for slot, idx in enumerate(order):
        if counts[idx] == 0:
            continue
        mean = lin_sum[idx] / float(counts[idx])
        palette[slot, 0:3] = mean
        palette[slot, 3] = counts[idx] / cells_total

    diag = {
        "grid": GRID,
        "nonempty_colour_bins": int((counts > 0).sum()),
        "dominant_bin": int(order[0]),
        "gradient_magnitude_total": mag_total,
        "l2_norm_before_normalise": norm,
    }
    return vec, palette, diag


def as_f32_bytes(a):
    """Little-endian binary32, round-to-nearest-even (numpy's default cast)."""
    return np.ascontiguousarray(a, dtype="<f4").tobytes()


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    from PIL import Image
    vec, pal, diag = descriptor(Image.open(argv[1]))
    print("model      : %s" % MODEL_ID)
    print("dim        : %d   (%d colour + %d orientation)"
          % (DIM, COLOUR_BINS, ORIENT_BINS))
    print("diagnostics: %s" % diag)
    for i in range(0, DIM, 8):
        print("  [%2d] %s" % (i, " ".join("%9.6f" % v for v in vec[i:i + 8])))
    print("palette (linear sRGB r,g,b,weight):")
    for r, g, b, w in pal:
        print("  %8.6f %8.6f %8.6f   %6.4f" % (r, g, b, w))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
