import hashlib, sys
d = open(sys.argv[1], 'rb').read()
print(len(d), hashlib.sha256(d).hexdigest())
print(d[:256])
print(d[-256:])
