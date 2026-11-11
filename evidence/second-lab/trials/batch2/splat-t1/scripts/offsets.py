import sys
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from werk_inspect import read_zip
buf = open(sys.argv[1], 'rb').read()
entries, _, _ = read_zip(buf)
for e in entries:
    if e['name'].startswith(('tools/', 'recipe/', 'loaders/')):
        print('%-42s lho=%-9d data=[%d .. %d) size=%d crc=%08x' % (
            e['name'], e['lho'], e['start'], e['start'] + e['csize'], e['csize'], e['crc']))
