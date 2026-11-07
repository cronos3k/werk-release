#!/usr/bin/env python3
"""fixture_pin.py -- assert a gate is measuring the fixture build it thinks it is.

Every gate harness in this repository states numbers about a fixture: 36 nodes,
168 declared files, a preview prefix of 972 057 bytes. Those are measurements of
ONE BUILD. A rebuild that changes the package silently changes what the gate
measured, and the gate goes on printing PASS.

That is not hypothetical. Stage 8's re-measurement found `crate-v1.werk`
recorded at one byte count with two different sha256s in two sections of one
document, the retarget fixture two bytes off its record, and a file count stale
by one (findings S8-1 … S8-3). Every one of them was a rebuild nobody noticed.

So: `fixtures/fixtures.json` is the single record of what each fixture is, and
a harness calls `pin()` at the top of its run. A mismatch prints both hashes and
says what to do, and the harness decides whether that is a FAIL or a warning --
this module never exits on its own, because a gate that dies before printing its
measurements has thrown away the thing it exists to produce.

    from tests.fixture_pin import pin, PinResult
    r = pin("crate-v1")
    record("fixture pinned", "PASS" if r.ok else "FAIL", r.detail)
"""

import hashlib
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECORD = os.path.join(ROOT, "fixtures", "fixtures.json")


class PinResult(object):
    __slots__ = ("key", "ok", "detail", "path", "size", "sha256", "record")

    def __init__(self, key, ok, detail, path, size, sha256, record):
        self.key, self.ok, self.detail = key, ok, detail
        self.path, self.size, self.sha256, self.record = path, size, sha256, record

    def __bool__(self):
        return self.ok

    __nonzero__ = __bool__


def load_record():
    with open(RECORD, encoding="utf-8") as fh:
        return json.load(fh)


def pin(key):
    """Check one fixture against fixtures/fixtures.json. Never raises on drift."""
    try:
        rec = load_record()["fixtures"][key]
    except (OSError, KeyError):
        return PinResult(key, False,
                         "no record for %r in fixtures/fixtures.json; run "
                         "python fixtures/record_fixtures.py" % key,
                         None, None, None, None)
    path = os.path.join(ROOT, rec["path"].replace("/", os.sep))
    if not os.path.isfile(path):
        return PinResult(key, False, "%s is not on disk" % rec["path"],
                         path, None, None, rec)
    with open(path, "rb") as fh:
        data = fh.read()
    size, digest = len(data), hashlib.sha256(data).hexdigest()
    if size == rec["size_bytes"] and digest == rec["sha256"]:
        return PinResult(key, True,
                         "%s %d B, sha256 %s (matches the record)"
                         % (rec["path"], size, digest[:16]),
                         path, size, digest, rec)
    return PinResult(
        key, False,
        "%s DRIFTED: on disk %d B / %s, recorded %d B / %s. The fixture was "
        "rebuilt; re-measure this gate's expectations, then run "
        "python fixtures/record_fixtures.py to update the record."
        % (rec["path"], size, digest[:16], rec["size_bytes"], rec["sha256"][:16]),
        path, size, digest, rec)


def pin_all(keys):
    return [pin(k) for k in keys]


if __name__ == "__main__":
    doc = load_record()
    bad = 0
    for key in doc["fixtures"]:
        r = pin(key)
        print("%-6s %s" % ("OK" if r.ok else "DRIFT", r.detail))
        bad += 0 if r.ok else 1
    raise SystemExit(1 if bad else 0)
