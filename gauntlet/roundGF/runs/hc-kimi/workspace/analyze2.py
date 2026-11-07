from PIL import Image
import numpy as np
import cv2

img = Image.open('page-03.jpg').convert('L')
arr = np.array(img)
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
        else:
            th = None
        tile_info.append((y, x, th))
        if th is not None:
            thresholds.append(th)
global_avg = int(np.mean(thresholds)) if thresholds else 128

mask = np.zeros((H, W), dtype=np.uint8)
for y, x, th in tile_info:
    if th is None:
        th = global_avg
    block = arr[y:y+tile, x:x+tile]
    mask[y:y+tile, x:x+tile] = (block < th).astype(np.uint8) * 255

num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=4)
print('components', num_labels)
syms = []
for i in range(1, num_labels):
    x, y, w, h, area = stats[i]
    if w == 0 or h == 0:
        continue
    aspect = min(w, h) / max(w, h)
    if w > 400 and h > 400 and aspect > 0.8:
        syms.append((area, aspect, w, h, x, y, i, centroids[i]))
syms.sort(reverse=True)
print('filtered square components:', len(syms))
for area, aspect, w, h, x, y, i, cent in syms:
    print(i, 'area', area, 'bbox', w, h, 'aspect', f'{aspect:.3f}', 'pos', x, y, 'centroid', cent)
