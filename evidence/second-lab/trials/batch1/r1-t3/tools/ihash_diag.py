import hashlib, itertools
g = 'eee8b3cbc87703fc945555efec8fdcb0fb133f6c94cf75c8643b57189c4ef2ce'  # geometry/game.glb
b = '866eb5c8c01ea7121bca325d3bd283ddf47fbba6a43cb39cd49edbbadfde6c82'  # physics/bounds.json
want = '60e08ed15118810abfeeee57aa45a4bbbbc3e21d90c887debaff8bd585d496c8'
for order in itertools.permutations([g, b]):
    for raw in (True, False):
        for tail in (b'{}', b''):
            m = b''.join(bytes.fromhex(x) if raw else x.encode() for x in order) + tail
            h = hashlib.sha256(m).hexdigest()
            print(raw, tail, order[0][:6], h[:16], h == want)
