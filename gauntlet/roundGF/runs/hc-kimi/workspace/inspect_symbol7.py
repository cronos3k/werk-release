from PIL import Image
import numpy as np
import cv2
from decoder import binarize, cluster_symbols

img = Image.open('page-03.jpg').convert('L')
arr = np.array(img)
mask = binarize(arr)
num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=4)
clusters = cluster_symbols(stats, centroids)
# find bottom-middle cluster
cluster = clusters[7]
x0,y0,x1,y1=cluster['bbox']
print('cluster 7 bbox', x0,y0,x1,y1, 'ids', cluster['ids'])
# list components that overlap this bbox
for i in range(1, stats.shape[0]):
    x,y,w,h,area=stats[i]
    if x+w < x0 or x > x1 or y+h < y0 or y > y1:
        continue
    if area < 50:
        continue
    aspect = min(w,h)/max(w,h) if w and h else 0
    print(i, 'area', area, 'bbox', w, h, 'aspect', f'{aspect:.2f}', 'pos', x, y, 'centroid', centroids[i])
