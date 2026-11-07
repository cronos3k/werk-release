#!/usr/bin/env python3
"""edge_targets.py -- the writer half of SPEC.md section 5, "Edge targets".

    python tools/edge_targets.py package.werk|MANIFEST.json   # list dangling edges

Every `edges[].to` names a `node_id` in the same manifest's `nodes[]`. A
writer MUST NOT emit an edge to an absent node: every conformant reader kills
the source of a `requires` edge to an absent node (`requires-missing-node`,
severity error), and degrades an `enhances` edge to one (`edge-dangling`,
warn). This module is the check every Python fixture builder and
`pipeline/package.py` run before they hash a manifest, so the refusal is in
one place. werk-core has the same check (`werk::manifest::dangling_edges`,
`refuse_dangling_edges`), used by `werkc build-fixture` and
`Package::add_node`. Both refuse an edge of EITHER kind: the specification's
MUST NOT is for every edge, and the code says what the text says.

The first package that broke the rule was gauntlet/roundOW/mini-v1.werk: its
builder dropped a node and kept an edge into it.
"""

import json
import sys
import zipfile


def dangling_edges(nodes):
    """[node dicts] -> [(source node_id, target, kind)] for each edge whose
    target is not a node_id in `nodes`, in manifest order."""
    ids = {n.get("node_id") for n in nodes}
    out = []
    for n in nodes:
        for e in n.get("edges") or []:
            if e.get("to") not in ids:
                out.append((n.get("node_id"), e.get("to"), e.get("kind")))
    return out


def refuse_dangling_edges(nodes):
    """Raise SystemExit if any edge, `requires` or `enhances`, points at a
    node that is not in `nodes` (SPEC section 5: a writer MUST NOT emit one)."""
    bad = dangling_edges(nodes)
    if bad:
        raise SystemExit(
            "refusing to write a package with an edge to a node that is not in "
            "nodes[] (SPEC section 5): %s. Drop the edge, or drop the dependent "
            "node too." % ", ".join("`%s` %s `%s`" % (s, k, t) for s, t, k in bad))


def _main(argv):
    if len(argv) != 2:
        print(__doc__.strip())
        return 2
    path = argv[1]
    if path.endswith(".json"):
        with open(path, "rb") as fh:
            man = json.loads(fh.read())
    else:
        with zipfile.ZipFile(path) as z:
            man = json.loads(z.read("MANIFEST.json"))
    bad = dangling_edges(man.get("nodes", []))
    for s, t, k in bad:
        print("%s --%s--> %s: target is not in nodes[]" % (s, k, t))
    print("%d dangling edge(s), %d of them `requires`"
          % (len(bad), sum(1 for _, _, k in bad if k == "requires")))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
