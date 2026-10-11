import sys, re
d = open(sys.argv[1], 'rb').read()
for w in sys.argv[2:]:
    hits = [m.start() for m in re.finditer(re.escape(w.encode()), d, re.I)]
    print(w, hits[:20])
    for h in hits[:3]:
        print('   ', d[max(0, h - 48):h + 80])
