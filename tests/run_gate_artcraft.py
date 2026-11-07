#!/usr/bin/env python3
"""run_gate_artcraft.py -- GATE ARTCRAFT: packages written by OTHER PEOPLE'S
writers, read by the four reference readers.

    python tests/run_gate_artcraft.py [--samples DIR] [--record]

WHY. Until 2026-10-13 every package any gate in this repository read had been
written by this repository. The first corpus written elsewhere -- the ArtCraft
applications, through the `craft-werk` library (Rust) and through Spark's
exporter (TypeScript) -- was measured against the reference core as it stood
on master: of 40 packages, 32 were refused with the single error "no manifest
schema for this profile", because their profiles are not the two the core has
built in. Seven verified; one is damaged on purpose. Law 12 says a reader
skips what it does not understand; the core was refusing it instead. Ruling 2
of 2026-10-13 (docs/RULINGS-2026-10-13.md) is the answer, and this gate is its
acceptance test:

  * every sample verifies in the reference core with exit status 0 and exactly
    the node census recorded for it;
  * every sample whose name says it is damaged exits 1 with exactly the
    recorded dead node, and nothing else dead;
  * the three bootstrap loaders agree with the core on the verdict.

THE CORPUS IS NOT IN THIS REPOSITORY, and that is deliberate: it belongs to
its writers and it grows while they work. What IS in this repository is the
record (tests/artcraft-corpus.json): one entry per sample, pinned by SHA-256
(the container for the zip form, MANIFEST.json for the directory form), with
the census measured when it was recorded. Three consequences, each reported
rather than hidden:

  * the corpus is absent        -> one SKIP, and the gate is INCOMPLETE;
  * a recorded sample is absent -> SKIP for that sample;
  * a sample is present that the record does not know, or whose bytes are no
    longer the recorded ones -> it is still verified, and held to the part of
    the claim that needs no record (intact exits 0, damaged exits 1), and the
    line says UNPINNED so nobody mistakes it for an exact-census check.

`--record` rewrites the record from what the core measures now. It refuses to
record an intact sample that does not verify, so a regression cannot be
recorded into a pass.
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate_common as G                                        # noqa: E402

DEFAULT_SAMPLES = os.environ.get(
    "WERK_ARTCRAFT_SAMPLES",
    os.path.join(os.environ.get("WERK_LAB", "<WERK_LAB unset>"),
                 "ArtCraft", "werk-integration", "samples"))
RECORD = os.path.join(G.ROOT, "tests", "artcraft-corpus.json")

CENSUS = re.compile(r"^census\s*:\s*(\d+) nodes: (\d+) alive, (\d+) skipped, (\d+) dead",
                    re.M)


def discover(root):
    """[(relative name, absolute path, form)] of every package under root."""
    found = []
    for base, dirs, files in os.walk(root):
        if "MANIFEST.json" in files:
            found.append((os.path.relpath(base, root).replace(os.sep, "/"), base, "directory"))
            dirs[:] = []
            continue
        dirs.sort()
        for name in sorted(files):
            if name.endswith(".werk"):
                p = os.path.join(base, name)
                found.append((os.path.relpath(p, root).replace(os.sep, "/"), p, "zip"))
    return sorted(found)


def identity(path, form):
    return G.sha256_file(os.path.join(path, "MANIFEST.json") if form == "directory"
                         else path)


def field(out, key):
    m = re.search(r"^%s\s*:\s*(.+)$" % key, out, re.M)
    return m.group(1).strip() if m else None


def measure(core, path):
    rc, out = G.verify(core, path)
    m = CENSUS.search(out)
    return {
        "exit": rc,
        "profile": field(out, "profile"),
        "signature": field(out, "signature"),
        "validated": field(out, "validated"),
        "census": [int(x) for x in m.groups()] if m else None,
        "dead": G.dead_nodes(out),
        "errors": sorted(c for s, c in G.codes(out) if s == "error"),
    }, out


def is_damaged(name):
    return "damaged" in name.lower()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--samples", default=DEFAULT_SAMPLES)
    ap.add_argument("--record", action="store_true")
    args = ap.parse_args(argv)

    gate = G.Gate("ARTCRAFT")
    if not os.path.isdir(args.samples):
        gate.record("corpus present", "SKIP",
                    "%s does not exist; the corpus belongs to its writers and is "
                    "not in this repository" % args.samples)
        return gate.finish()
    readers = G.readers(gate)
    core = next((r for r in readers if r[0] == "core"), None)
    if core is None:
        return gate.finish()
    packages = discover(args.samples)

    if args.record:
        rec, refused = {}, 0
        for name, path, form in packages:
            got, _out = measure(core, path)
            if got["exit"] != (1 if is_damaged(name) else 0) or got["census"] is None:
                print("NOT RECORDED %s: exit %s, errors %s"
                      % (name, got["exit"], got["errors"]))
                refused += 1
                continue
            got.update({"form": form, "sha256": identity(path, form),
                        "sha256_of": "MANIFEST.json" if form == "directory" else "container"})
            rec[name] = got
        with open(RECORD, "w", encoding="utf-8", newline="\n") as fh:
            json.dump({"_comment": "Generated by tests/run_gate_artcraft.py --record. "
                                   "Do not edit by hand.",
                       "samples": rec}, fh, indent=1, sort_keys=True, ensure_ascii=False)
            fh.write("\n")
        print("recorded %d sample(s) in %s; %d refused" % (len(rec), RECORD, refused))
        return 1 if refused else 0

    with open(RECORD, encoding="utf-8") as fh:
        rec = json.load(fh)["samples"]
    seen, pinned, unpinned = set(), 0, 0
    apps = {}
    for name, path, form in packages:
        seen.add(name)
        got, out = measure(core, path)
        want = rec.get(name)
        exact = want is not None and want["sha256"] == identity(path, form)
        want_exit = 1 if is_damaged(name) else 0
        cen = got["census"]
        summary = ("exit %d, %s, %s" % (got["exit"], got["profile"],
                                        "%d nodes: %d alive, %d skipped, %d dead" % tuple(cen)
                                        if cen else "no census"))
        if got["dead"]:
            summary += ", dead: " + " ".join(got["dead"])
        if exact:
            pinned += 1
            same = all(got[k] == want[k] for k in
                       ("exit", "profile", "signature", "census", "dead", "errors"))
            gate.check("core: %s" % name, same, summary,
                       "MEASURED %s BUT RECORDED exit %s census %s dead %s errors %s"
                       % (summary, want["exit"], want["census"], want["dead"],
                          want["errors"]))
        else:
            unpinned += 1
            ok = got["exit"] == want_exit and (len(got["dead"]) == 1) == is_damaged(name)
            gate.check("core: %s" % name, ok,
                       "UNPINNED (%s): %s" % ("not in the record" if want is None
                                              else "bytes changed since recorded", summary),
                       "UNPINNED, and exit %d where %d is required: %s; errors %s"
                       % (got["exit"], want_exit, summary, got["errors"]))
        # the three loaders: the same verdict, and the same dead node by name
        for reader in readers:
            if reader[0] == "core":
                continue
            rc, lout = G.verify(reader, path)
            named = all(re.search(r"^(FAIL|\[error\]).*\b%s\b" % re.escape(d), lout, re.M)
                        for d in got["dead"])
            ok = rc == got["exit"] and named
            if not ok:
                gate.record("%s: %s" % (reader[0], name), "FAIL",
                            "exit %d where the core exits %d; %s"
                            % (rc, got["exit"], lout.strip().splitlines()[-1][:160]
                               if lout.strip() else "no output"))
            apps.setdefault((name.split("/")[0], reader[0]), []).append(ok)
        apps.setdefault((name.split("/")[0], "core"), []).append(True)
    for (app, rd) in sorted(apps):
        if rd == "core":
            continue
        oks = apps[(app, rd)]
        gate.check("%s agrees with the core: %s" % (rd, app), all(oks),
                   "%d of %d package(s): same exit status, same dead node"
                   % (sum(oks), len(oks)))
    for name in sorted(set(rec) - seen):
        gate.record("core: %s" % name, "SKIP", "recorded, but absent from the corpus")
    gate.check("corpus census", bool(packages),
               "%d package(s) from %d application(s): %d pinned and exact, %d unpinned"
               % (len(packages), len({n.split("/")[0] for n, _p, _f in packages}),
                  pinned, unpinned))
    return gate.finish()


if __name__ == "__main__":
    sys.exit(main())
