import sys
sys.path.insert(0, '.')
import decoder
def decode_and_capture():
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
    # parity check
    data = b''.join(codewords[i][16:] for i in range(8))
    parity = codewords[8][16:]
    xor = bytes(a ^ b for a, b in zip(data, parity))
    print('parity XOR data == parity?', all(b == 0 for b in xor))
    print('XOR nonzero count:', sum(1 for b in xor if b))
    # Show CRC mismatches
    for seq in range(9):
        cw = codewords[seq]
        stored = int.from_bytes(cw[12:16], 'big')
        computed = decoder.crc32(cw[:12] + cw[16:])
        status = 'OK' if stored == computed else 'MISMATCH'
        print(f'SEQ {seq}: stored {stored:08X} computed {computed:08X} {status}')

decode_and_capture()
