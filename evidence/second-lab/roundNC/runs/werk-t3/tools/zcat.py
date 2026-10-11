"""Print one entry of the container to stdout (in memory; nothing written to disk).
usage: zcat.py <container> <entry> [start_line] [n_lines]"""
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
data = z.read(sys.argv[2])
text = data.decode('utf-8', 'replace')
lines = text.split('\n')
start = int(sys.argv[3]) if len(sys.argv) > 3 else 1
n = int(sys.argv[4]) if len(sys.argv) > 4 else len(lines)
sys.stdout.reconfigure(encoding='utf-8')
print(f'[{sys.argv[2]}: {len(data)} bytes, {len(lines)} lines]')
for i in range(start - 1, min(start - 1 + n, len(lines))):
    print(f'{i + 1:5d}| {lines[i]}')
