#!/usr/bin/env python3
"""Decode the nine WERK symbols on page-03.jpg into a file."""

import struct
import zlib
import hashlib
import zipfile
import os
from PIL import Image
import numpy as np
import cv2

IMG_PATH = 'page-03.jpg'
GRID = 99
DATA_R0, DATA_R1 = 2, 96  # inclusive
DATA_C0, DATA_C1 = 2, 96
EXPECTED_LEN = 8168
EXPECTED_SHA256 = 'b0823016712e4770e01870f709b10a0fd3d4aaf08753d714092038d84d7617a6'
EXPECTED_CRCS = {
    0: 0xF616796C,
    1: 0xA64016D6,
    2: 0xAC510CD2,
    3: 0x9C35923F,
    4: 0xAE804266,
    5: 0x3A153C58,
    6: 0x63604E4D,
    7: 0xE20A2CD2,
    8: 0x0E184BA8,
}


def binarize(arr):
    """Tile-based binarization as described in the document."""
    H, W = arr.shape
    tile = 64
    thresholds = []
    tile_info = []
    for y in range(0, H, tile):
        for x in range(0, W, tile):
            block = arr[y:y+tile, x:x+tile]
            mn = int(block.min())
            mx = int(block.max())
            if mx - mn >= 40:
                th = (mn + mx) // 2
                thresholds.append(th)
            else:
                th = None
            tile_info.append((y, x, th))
    global_avg = int(np.mean(thresholds)) if thresholds else 128
    mask = np.zeros((H, W), dtype=np.uint8)
    for y, x, th in tile_info:
        if th is None:
            th = global_avg
        block = arr[y:y+tile, x:x+tile]
        mask[y:y+tile, x:x+tile] = (block < th).astype(np.uint8) * 255
    return mask


def cluster_symbols(stats, centroids):
    """Group frame/interior components into the nine symbol positions."""
    comps = []
    for i in range(1, stats.shape[0]):
        x, y, w, h, area = stats[i]
        if w == 0 or h == 0:
            continue
        aspect = min(w, h) / max(w, h)
        # generous filter to capture frames and large interiors
        if w > 350 and h > 350 and aspect > 0.65 and area > 5000:
            comps.append((i, x, y, w, h, area, centroids[i]))
    # cluster by centroid distance
    clusters = []
    for i, x, y, w, h, area, cent in comps:
        cx, cy = cent
        merged = False
        for c in clusters:
            ccx, ccy = c['centroid']
            if abs(cx - ccx) < 350 and abs(cy - ccy) < 350:
                c['ids'].append(i)
                c['bbox'][0] = min(c['bbox'][0], x)
                c['bbox'][1] = min(c['bbox'][1], y)
                c['bbox'][2] = max(c['bbox'][2], x + w)
                c['bbox'][3] = max(c['bbox'][3], y + h)
                total = len(c['ids'])
                c['centroid'] = ((ccx * (total - 1) + cx) / total,
                                 (ccy * (total - 1) + cy) / total)
                merged = True
                break
        if not merged:
            clusters.append({'ids': [i], 'bbox': [x, y, x + w, y + h],
                             'centroid': (cx, cy)})
    # sort top-to-bottom, left-to-right
    clusters.sort(key=lambda c: (c['centroid'][1], c['centroid'][0]))
    return clusters


def read_symbol(arr, mask, labels, cluster, symbol_idx):
    """Return the oriented 99x99 binary grid for one symbol."""
    H, W = arr.shape
    x0, y0, x1, y1 = cluster['bbox']
    # small pad to ensure frame edges are captured; clip to image
    pad = 8
    x0 = max(0, x0 - pad)
    y0 = max(0, y0 - pad)
    x1 = min(W, x1 + pad)
    y1 = min(H, y1 + pad)

    # Gather ink pixels in the region that belong to sizeable components
    # (drop isolated speckles and stray small text)
    region_labels = labels[y0:y1, x0:x1]
    region_mask = mask[y0:y1, x0:x1]
    unique, counts = np.unique(region_labels[region_mask > 0], return_counts=True)
    # keep components with at least a few hundred pixels
    keep = set(unique[counts >= 200].tolist())
    # Also always keep components whose ids are in this cluster
    keep.update(cluster['ids'])

    yy, xx = np.where((region_mask > 0) & (np.isin(region_labels, list(keep))))
    # coordinates in full image
    xs = xx + x0
    ys = yy + y0
    if len(xs) == 0:
        raise ValueError(f'symbol {symbol_idx}: no ink pixels')

    s = xs + ys
    d = xs - ys
    A = (xs[s.argmin()], ys[s.argmin()])  # top-left
    B = (xs[d.argmax()], ys[d.argmax()])  # top-right
    C = (xs[s.argmax()], ys[s.argmax()])  # bottom-right
    D = (xs[d.argmin()], ys[d.argmin()])  # bottom-left

    # sample grid
    grid = np.zeros((GRID, GRID), dtype=np.uint8)
    A = np.array(A, dtype=np.float64)
    B = np.array(B, dtype=np.float64)
    C = np.array(C, dtype=np.float64)
    D = np.array(D, dtype=np.float64)
    for r in range(GRID):
        v = (r + 0.5) / GRID
        for c in range(GRID):
            u = (c + 0.5) / GRID
            P = (1 - u) * (1 - v) * A + u * (1 - v) * B + u * v * C + (1 - u) * v * D
            px = int(round(P[0]))
            py = int(round(P[1]))
            # 3x3 neighbourhood vote
            y0b = max(0, py - 1)
            y1b = min(H, py + 2)
            x0b = max(0, px - 1)
            x1b = min(W, px + 2)
            block = mask[y0b:y1b, x0b:x1b]
            if block.size == 0:
                continue
            ink = np.count_nonzero(block > 0)
            grid[r, c] = 1 if ink >= 5 else 0
    return grid, (A, B, C, D)


def orient_grid(grid):
    """Rotate grid so the top-left orientation elbow is in place."""
    ring0 = np.zeros_like(grid, dtype=bool)
    ring0[0, :] = True
    ring0[GRID - 1, :] = True
    ring0[:, 0] = True
    ring0[:, GRID - 1] = True
    best = None
    best_score = -1
    for k in range(4):
        g = np.rot90(grid, k=k)
        # ring0 should be nearly all black
        ring0_black = np.sum(g[ring0] == 1)
        ring0_total = np.sum(ring0)
        if ring0_black < ring0_total * 0.85:
            continue
        # elbow at (1,1),(1,2),(2,1)
        elbow = g[1, 1] + g[1, 2] + g[2, 1]
        if elbow < 2:
            continue
        # also make sure ring1 at non-elbow positions is mostly white
        score = ring0_black + elbow * 10
        if score > best_score:
            best_score = score
            best = g
    if best is None:
        raise ValueError('could not orient grid')
    return best


def grid_to_codeword(grid):
    bits = grid[DATA_R0:DATA_R1 + 1, DATA_C0:DATA_C1 + 1].flatten()
    n_bits = len(bits)
    n_bytes = n_bits // 8
    codeword = bytearray()
    for i in range(n_bytes):
        byte = 0
        for j in range(8):
            byte = (byte << 1) | int(bits[i * 8 + j])
        codeword.append(byte)
    return bytes(codeword)


def crc32(bytes_data):
    """CRC-32 as defined in the document (ZIP/PNG)."""
    crc = 0xFFFFFFFF
    for b in bytes_data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xEDB88320
            else:
                crc >>= 1
    return crc ^ 0xFFFFFFFF


def decode():
    img = Image.open(IMG_PATH).convert('L')
    arr = np.array(img)
    H, W = arr.shape
    mask = binarize(arr)
    Image.fromarray(mask).save('debug_mask.png')
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=4)
    clusters = cluster_symbols(stats, centroids)
    print(f'found {len(clusters)} symbol clusters')
    if len(clusters) != 9:
        raise RuntimeError(f'expected 9 symbols, got {len(clusters)}')

    codewords = {}
    for idx, cluster in enumerate(clusters):
        print(f'\nSymbol cluster {idx}: ids={cluster["ids"]} bbox={cluster["bbox"]}')
        grid, corners = read_symbol(arr, mask, labels, cluster, idx)
        print('  corners A/B/C/D:', [tuple(map(int, c)) for c in corners])
        grid = orient_grid(grid)
        cw = grid_to_codeword(grid)
        print('  codeword length', len(cw))
        marker = cw[0:2]
        version = cw[2]
        kind = cw[3]
        seq = struct.unpack('>H', cw[4:6])[0]
        total = struct.unpack('>H', cw[6:8])[0]
        file_len = struct.unpack('>I', cw[8:12])[0]
        stored_crc = struct.unpack('>I', cw[12:16])[0]
        computed_crc = crc32(cw[0:12] + cw[16:])
        print(f'  marker={marker!r} version={version} kind={kind} seq={seq}/{total} len={file_len}')
        print(f'  stored CRC={stored_crc:08X} computed={computed_crc:08X} expected={EXPECTED_CRCS.get(seq):08X}')
        if computed_crc != stored_crc:
            print('  *** CRC MISMATCH ***')
        codewords[seq] = cw

    # Repair any data symbol whose own CRC does not match using the parity symbol
    parity_cw = codewords.get(8)
    if parity_cw:
        parity_payload = parity_cw[16:]
        for seq in range(8):
            cw = codewords[seq]
            stored_crc = struct.unpack('>I', cw[12:16])[0]
            computed_crc = crc32(cw[0:12] + cw[16:])
            if computed_crc != stored_crc:
                print(f'  -> repairing SEQ {seq} from parity')
                other = bytes(0 for _ in range(1112))
                for other_seq in range(8):
                    if other_seq == seq:
                        continue
                    other = bytes(a ^ b for a, b in zip(other, codewords[other_seq][16:]))
                repaired = bytes(a ^ b for a, b in zip(other, parity_payload))
                codewords[seq] = cw[:16] + repaired
                new_crc = crc32(codewords[seq][0:12] + codewords[seq][16:])
                print(f'     repaired stored CRC={stored_crc:08X} computed={new_crc:08X}')

    # Reassemble data symbols (SEQ 0..7)
    data_payloads = []
    for seq in range(8):
        if seq not in codewords:
            raise RuntimeError(f'missing data symbol seq {seq}')
        data_payloads.append(codewords[seq][16:])
    file_bytes = b''.join(data_payloads)[:EXPECTED_LEN]
    print(f'\nReassembled file length: {len(file_bytes)} (expected {EXPECTED_LEN})')
    actual_sha = hashlib.sha256(file_bytes).hexdigest()
    print('SHA-256:', actual_sha)
    print('Expected:', EXPECTED_SHA256)
    print('Match:', actual_sha == EXPECTED_SHA256)
    with open('recovered.werk', 'wb') as f:
        f.write(file_bytes)

    # Inspect as ZIP
    if not zipfile.is_zipfile('recovered.werk'):
        print('recovered.werk is not a zip file')
        return
    with zipfile.ZipFile('recovered.werk', 'r') as z:
        print('\nZIP contents:')
        for info in z.infolist():
            print(f'  {info.filename:30s} {info.file_size:6d} bytes  CRC {info.CRC:08X}')
        z.extractall('recovered_pkg')
        print('extracted to recovered_pkg/')


if __name__ == '__main__':
    decode()
