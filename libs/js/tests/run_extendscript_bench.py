#!/usr/bin/env python3
"""run_extendscript_bench.py -- run extendscript_bench.jsx in Illustrator 2020 through
the Adobe plug-ins' COM helper (plugins/illustrator/tools/adobe_com.py): attaches
to a running Illustrator (never quits it), or starts one and quits/kills it at the
end. Photoshop is never touched.

    py -3.12 js/tests/run_extendscript_bench.py <before werk.jsx> <out log>
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIBS = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(os.path.dirname(LIBS), "plugins", "illustrator", "tools"))
import adobe_com  # noqa: E402

before, log = sys.argv[1], sys.argv[2]
d = os.path.join(LIBS, "_scratch").replace("\\", "/")
args = {"task": "werk-bench", "dir": d, "builds": [
    {"name": "before", "path": before.replace("\\", "/"), "sizes": {"sha": "256k", "crc": "256k", "inflate": "64k"},
     "nolimit": True},
    {"name": "after", "path": os.path.join(LIBS, "js", "dist", "werk.jsx").replace("\\", "/"),
     "sizes": {"sha": "1m", "crc": "1m", "inflate": "1m"}, "sinks": ["ring", "window"], "nolimit": True},
]}
with adobe_com.Host("illustrator") as h:
    try:
        rec = h.run(os.path.join(HERE, "extendscript_bench.jsx"), args,
                    progress_file=os.path.join(LIBS, "_scratch", "es-bench-progress.txt"), idle_limit=900)
    except RuntimeError as e:
        rec = {"ret": None, "err": repr(e)}
    events = h.events
with open(log, "w", encoding="utf-8") as fh:
    fh.write("host Illustrator %s\n%s\n%s\nevents %s\n" % (getattr(h, "version", "?"), rec.get("ret"), rec.get("err"), json.dumps(events, default=str)))
print(open(log, encoding="utf-8").read())
