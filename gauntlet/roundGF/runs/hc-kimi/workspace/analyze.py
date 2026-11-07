from PIL import Image
import numpy as np
import cv2

img = Image.open('page-03.jpg').convert('L')
arr = np.array(img)
H, W = arr.shape
print('size', W, H)

# Tile-based binarization per document
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
print('global avg threshold', global_avg, 'non-uniform tiles', len(thresholds))

mask = np.zeros((H, W), dtype=np.uint8)
for y, x, th in tile_info:
    if th is None:
        th = global_avg
    block = arr[y:y+tile, x:x+tile]
    mask[y:y+tile, x:x+tile] = (block < th).astype(np.uint8) * 255

# Save debug binary image
Image.fromarray(mask).save('debug_bin.png')

num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=4)
print('components', num_labels)
cands = []
for i in range(1, num_labels):
    x, y, w, h, area = stats[i]
    if w == 0 or h == 0:
        continue
    aspect = min(w, h) / max(w, h)
    cands.append((area, aspect, w, h, x, y, i))
cands.sort(reverse=True)
print('top 20 components:')
for area, aspect, w, h, x, y, i in cands[:20]:
    print(i, 'area', area, 'bbox', w, h, 'aspect', f'{aspect:.3f}', 'pos', x, y)
