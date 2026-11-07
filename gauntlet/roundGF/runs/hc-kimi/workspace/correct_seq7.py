import sys
sys.path.insert(0, '.')
import decoder
import hashlib, struct

img = __import__('PIL').Image.open('page-03.jpg').convert('L')
arr = __import__('numpy').array(img)
mask = decoder.binarize(arr)
num_labels, labels, stats, centroids = __import__('cv2').connectedComponentsWithStats(mask, connectivity=4)
clusters = decoder.cluster_symbols(stats, centroids)
codewords = {}
for idx, cluster in enumerate(clusters):
    grid, _ = decoder.read_symbol(arr, mask, labels, cluster, idx)
    grid = decoder.orient_grid(grid)
    cw = decoder.grid_to_codeword(grid)
    seq = cw[4] * 256 + cw[5]
    codewords[seq] = cw

# current file from seq0..7
file_now = b''.join(codewords[i][16:] for i in range(8))[:8168]
print('current SHA', hashlib.sha256(file_now).hexdigest())

# parity-corrected seq7
payloads = [codewords[i][16:] for i in range(8)]
parity = codewords[8][16:]
other_xor = bytes(0 for _ in range(1112))
for i in range(7):
    other_xor = bytes(a ^ b for a, b in zip(other_xor, payloads[i]))
corrected7 = bytes(a ^ b for a, b in zip(other_xor, parity))
print('corrected seq7 differs from decoded in', sum(a!=b for a,b in zip(corrected7, payloads[7])), 'bytes')
file_corr = b''.join(payloads[:7] + [corrected7])[:8168]
print('corrected SHA', hashlib.sha256(file_corr).hexdigest())
print('expected SHA', 'b0823016712e4770e01870f709b10a0fd3d4aaf08753d714092038d84d7617a6')

# find positions of differences within payload/file
for j,(a,b) in enumerate(zip(payloads[7], corrected7)):
    if a!=b:
        print('first diff at payload byte', j, 'within file' if j<384 else 'padding')
        break
