import sys
d = open(sys.argv[1], 'rb').read()
print(len(d))
print(d[:300])
print(d[-300:])
