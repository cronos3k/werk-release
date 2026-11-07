from collections import deque
from pathlib import Path
from PIL import Image
import binascii
import hashlib
import json
import sys
import zipfile


IMAGE = Path("page-03.jpg")
OUT = Path("recovered.werk")

# Loose crops around the nine symbols, in reading order.  These deliberately
# exclude the captions; the exact quadrilateral is recovered from the frame.
CROPS = [
    (240, 1320, 900, 2010), (920, 1310, 1580, 1990), (1590, 1300, 2260, 1975),
    (250, 1990, 910, 2690), (930, 1980, 1590, 2680), (1600, 1970, 2265, 2670),
    (260, 2660, 920, 3370), (940, 2650, 1600, 3350), (1610, 2635, 2275, 3340),
]

PRINTED_CRCS = [
    0xF616796C, 0xA64016D6, 0xAC510CD2,
    0x9C35923F, 0xAE804266, 0x3A153C58,
    0x63604E4D, 0xE20A2CD2, 0x0E184BA8,
]
EXPECTED_SHA256 = "b0823016712e4770e01870f709b10a0fd3d4aaf08753d714092038d84d7617a6"


def connected_components(im, box, threshold):
    """Return dark-pixel components in box as (size, pixels, bbox)."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    p = im.load()
    dark = bytearray(w * h)
    for y in range(h):
        off = y * w
        yy = y + y0
        for x in range(w):
            dark[off + x] = p[x + x0, yy] < threshold
    seen = bytearray(w * h)
    comps = []
    for idx, value in enumerate(dark):
        if not value or seen[idx]:
            continue
        stack = [idx]
        seen[idx] = 1
        pts = []
        minx = maxx = idx % w
        miny = maxy = idx // w
        while stack:
            q = stack.pop()
            y, x = divmod(q, w)
            pts.append((x + x0, y + y0))
            if x < minx: minx = x
            if x > maxx: maxx = x
            if y < miny: miny = y
            if y > maxy: maxy = y
            if x and dark[q-1] and not seen[q-1]:
                seen[q-1] = 1; stack.append(q-1)
            if x+1 < w and dark[q+1] and not seen[q+1]:
                seen[q+1] = 1; stack.append(q+1)
            if y and dark[q-w] and not seen[q-w]:
                seen[q-w] = 1; stack.append(q-w)
            if y+1 < h and dark[q+w] and not seen[q+w]:
                seen[q+w] = 1; stack.append(q+w)
        comps.append((len(pts), pts, (minx+x0, miny+y0, maxx+x0, maxy+y0)))
    return comps


def frame_corners(im, crop, threshold=90):
    comps = connected_components(im, crop, threshold)
    # The frame component has by far the broadest roughly-square bounding box.
    candidates = []
    for n, pts, bbox in comps:
        x0, y0, x1, y1 = bbox
        w, h = x1-x0+1, y1-y0+1
        if w > 450 and h > 450 and 0.75 < w/h < 1.33:
            candidates.append((w*h, n, pts, bbox))
    if not candidates:
        raise RuntimeError(f"frame not found in crop {crop}")
    _, n, pts, bbox = max(candidates)
    # As specified by the sheet: extrema of x+y and x-y.  Average the handful
    # of closest pixels to reduce single-pixel JPEG noise at a corner.
    metrics = [
        (lambda x,y: x+y, min),       # top-left
        (lambda x,y: x-y, max),       # top-right
        (lambda x,y: x+y, max),       # bottom-right
        (lambda x,y: x-y, min),       # bottom-left
    ]
    corners = []
    for fn, which in metrics:
        vals = [fn(x,y) for x,y in pts]
        extreme = which(vals)
        near = [(x,y) for (x,y),v in zip(pts,vals) if abs(v-extreme) <= 1]
        corners.append((sum(x for x,y in near)/len(near), sum(y for x,y in near)/len(near)))
    return corners, bbox, n


def sample_grid(im, corners, threshold=90):
    p = im.load()
    A, B, C, D = corners
    grid = []
    for r in range(99):
        row = []
        v = (r + 0.5) / 99
        for c in range(99):
            u = (c + 0.5) / 99
            x = (1-u)*(1-v)*A[0] + u*(1-v)*B[0] + u*v*C[0] + (1-u)*v*D[0]
            y = (1-u)*(1-v)*A[1] + u*(1-v)*B[1] + u*v*C[1] + (1-u)*v*D[1]
            xi, yi = round(x), round(y)
            votes = 0
            for dy in (-1,0,1):
                for dx in (-1,0,1):
                    votes += p[xi+dx, yi+dy] < threshold
            row.append(1 if votes >= 5 else 0)
        grid.append(row)
    return grid


def orient(grid):
    def elbow(g):
        return g[1][1] and g[1][2] and g[2][1]
    for turns in range(4):
        if elbow(grid):
            return grid, turns
        # clockwise
        grid = [list(row) for row in zip(*grid[::-1])]
    raise ValueError("orientation elbow not found")


def grid_to_codeword(grid):
    bits = [grid[r][c] for r in range(2,97) for c in range(2,97)]
    if bits[-1] != 0:
        raise ValueError("leftover module is not white")
    out = bytearray()
    for i in range(0, 9024, 8):
        b = 0
        for bit in bits[i:i+8]:
            b = (b << 1) | bit
        out.append(b)
    return bytes(out)


def decode_one(im, crop, index):
    corners, bbox, n = frame_corners(im, crop)
    grid, turns = orient(sample_grid(im, corners))
    ring0 = sum(grid[0]) + sum(grid[98]) + sum(row[0]+row[98] for row in grid[1:98])
    cw = grid_to_codeword(grid)
    stored = int.from_bytes(cw[12:16], "big")
    computed = binascii.crc32(cw[:12] + cw[16:]) & 0xffffffff
    print(f"symbol {index}: frame={bbox} corners={corners} component={n} turns={turns} ring0={ring0}/392")
    print(f"  marker={cw[:2]!r} ver={cw[2]} kind={cw[3]} seq={int.from_bytes(cw[4:6],'big')} total={int.from_bytes(cw[6:8],'big')} file_len={int.from_bytes(cw[8:12],'big')}")
    print(f"  CRC stored={stored:08X} computed={computed:08X} printed={PRINTED_CRCS[index]:08X}")
    if cw[:2] != b"WK" or cw[2] != 1 or stored != computed or stored != PRINTED_CRCS[index]:
        raise ValueError(f"symbol {index} failed validation")
    return cw


def main():
    im = Image.open(IMAGE).convert("L")
    codewords = [decode_one(im, crop, i) for i,crop in enumerate(CROPS)]
    data = [cw for cw in codewords if cw[3] == 0]
    data.sort(key=lambda cw: int.from_bytes(cw[4:6], "big"))
    file_len = int.from_bytes(data[0][8:12], "big")
    recovered = b"".join(cw[16:] for cw in data)[:file_len]
    OUT.write_bytes(recovered)
    digest = hashlib.sha256(recovered).hexdigest()
    print(f"recovered {len(recovered)} bytes to {OUT}; SHA-256={digest}")
    if digest != EXPECTED_SHA256:
        raise ValueError("final SHA-256 mismatch")
    with zipfile.ZipFile(OUT) as zf:
        print("entries:")
        for zi in zf.infolist():
            print(f"  {zi.filename} ({zi.file_size} bytes)")


if __name__ == "__main__":
    main()
