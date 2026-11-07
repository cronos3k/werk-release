#!/usr/bin/env python3
"""payload_file.py -- the writer half of SPEC.md section 2.1.

    from payload_file import annotate_payload_files
    annotate_payload_files(nodes)      # in place, before the manifest is built

WHY. `primary.{mesh,geometry,sound,image}` names a NODE and a node may hold
several files. An 8B implementer in the open-weights gauntlet followed
`primary.sound` to its node exactly as SPEC section 2 told it to, took
`files[0]`, and wrote out `audio/sfx/crate-impact-hard-surface.json` -- the
DESCRIPTOR -- where a WAV was asked for, while reporting success. Nothing was
malformed; the format simply never said which file IS the sound (S-XV-4 /
S-OW-2, the successor to S-13).

SPEC section 2.1 answers it with an optional per-version `payload_file`, and
this is the one place a werk writer in this repository computes it, so that
five fixture builders cannot disagree about what a node's payload is.

The rules here are the WRITER's, and they are deliberately narrower than the
reader's fallback in SPEC section 2.1: a writer that is not certain emits
nothing, because an absent `payload_file` sends the reader to a documented
fallback and a WRONG one sends it to the wrong bytes.
"""

#: node type -> the reserved `role` its payload file carries. SPEC section 2.1.
ROLE_BY_TYPE = {
    "core.audio.effect": "best",
    "core.audio.ambience": "best",
    "core.imposter": "atlas",
    "core.recipe": "record",
}

#: node type -> the payload file's extension, where the role vocabulary does
#: not cover it and exactly one file can carry it.
EXT_BY_TYPE = {
    "core.anim.clip": ".wkac",
    "core.skeleton": ".json",
}


def payload_file_for(node_type, files):
    """-> the path of THE payload file of this version, or None if unknowable.

    `files` is a list of manifest file dicts. Never guesses: every rule below
    requires the answer to be unique, and a `descriptor` is never selected.
    """
    if len(files) == 1:
        return files[0]["path"]
    explicit = [f for f in files if f.get("role") == "payload"]
    if len(explicit) == 1:
        return explicit[0]["path"]
    role = ROLE_BY_TYPE.get(node_type)
    if role:
        hit = [f for f in files if f.get("role") == role]
        if len(hit) == 1:
            return hit[0]["path"]
    ext = EXT_BY_TYPE.get(node_type)
    if ext:
        hit = [f for f in files
               if f["path"].endswith(ext) and f.get("role") != "descriptor"]
        if len(hit) == 1:
            return hit[0]["path"]
    return None


def annotate_payload_files(nodes, only_multifile=True):
    """Set `payload_file` on every version where it is determinable. -> count.

    `only_multifile` skips single-file versions, where the field is redundant
    (SPEC section 2.1 rule 2 answers them without it) and would add a line of
    manifest per node for nothing -- the manifest is inlined whole by readers
    on a documentation budget, and 150 redundant lines is a real cost.
    """
    n = 0
    for node in nodes:
        for version in node.get("versions", []):
            files = version.get("files") or []
            if only_multifile and len(files) < 2:
                continue
            if version.get("payload_file"):
                continue
            path = payload_file_for(node.get("type", ""), files)
            if path is None:
                continue
            version["payload_file"] = path
            n += 1
    return n


def check_payload_files(manifest):
    """-> list of problems. A `payload_file` must name a file in ITS version."""
    bad = []
    for node in manifest.get("nodes", []):
        for version in node.get("versions", []):
            pf = version.get("payload_file")
            if pf is None:
                continue
            paths = [f["path"] for f in version.get("files") or []]
            if pf not in paths:
                bad.append("%s v%s: payload_file %r is not in this version's "
                           "files[] (%s)" % (node.get("node_id"),
                                             version.get("v"), pf,
                                             ", ".join(paths) or "empty"))
            for f in version.get("files") or []:
                if f["path"] == pf and f.get("role") == "descriptor":
                    bad.append("%s v%s: payload_file %r is marked role "
                               "'descriptor', which is never the payload"
                               % (node.get("node_id"), version.get("v"), pf))
    return bad
