import sys
d = open(sys.argv[1], 'rb').read()
print(len(d))
print(d[:600])
print('---TAIL---')
print(d[-400:])
