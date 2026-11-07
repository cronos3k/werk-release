"""werk retarget -- the Stage 6 skeleton and retargeting implementation.

    from retarget import load_canonical, sources, calibrate, retarget, writers

Python 3, stdlib + numpy. numpy was already a build-time dependency of the
fixtures; the runtime loaders in `loaders/` stay dependency-free and none of
this is on their path.
"""

import json
import os

from .skeleton import Clip, Rig            # noqa: F401

SPEC_SKELETON = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "spec", "skeleton", "canonical-humanoid-v1.json")
MAPS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "maps")


def load_canonical(path=None):
    return Rig.from_canonical(path or SPEC_SKELETON)


def load_map(name, path=None):
    """A bone-correspondence map, by name.

    Looked up first in the maps that TRAVEL WITH THE CANONICAL SKELETON (the
    `retarget` block of spec/skeleton/canonical-humanoid-v1.json -- mixamo,
    ue-mannequin, vrm-humanoid), then in retarget/maps/. The spec's own maps
    win, so a map shipped with the format is never shadowed by a local file
    without that being visible in the returned provenance.
    """
    with open(path or SPEC_SKELETON, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    if name in doc.get("retarget", {}):
        m = doc["retarget"][name]
        return m["map"], {"map_id": name, "from": "spec/skeleton/canonical-humanoid-v1.json",
                          "description": m.get("description")}
    p = os.path.join(MAPS_DIR, name + ".json")
    if not os.path.isfile(p):
        raise KeyError("no bone map %r in the canonical skeleton or in %s"
                       % (name, MAPS_DIR))
    with open(p, "r", encoding="utf-8") as fh:
        m = json.load(fh)
    # Recorded as the path INSIDE THE REPOSITORY, never the absolute path of
    # the checkout: the provenance travels in packages, and an absolute path
    # leaked the builder's directory and made the fixture's bytes depend on
    # where the repository was cloned (release finding N5).
    rel = os.path.relpath(p, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return m["map"], {"map_id": m.get("map_id", name), "from": rel.replace(os.sep, "/"),
                      "description": m.get("description"),
                      "derivation": m.get("derivation")}
