#!/usr/bin/env python3
"""loader_caps.py -- what a bootstrap loader can do, read from the loader itself.

    from loader_caps import loader_capabilities
    meta["capabilities"] = loader_capabilities(loader_bytes)

WHY. A `core.loader` node declares, in `meta.capabilities`, what the reader it
carries actually does (SPEC.md section 7, `$defs/loaderMeta`), and SPEC section
10.0 is explicit that an undeclared capability and an unimplemented declared
one are both failures. That list existed in NINE places: once in each loader's
own header and once in each of eight writers -- five fixture builders, the
pipeline packer, the Blender exporter and werkc -- every one a literal typed by
hand. They disagreed: `werk_read.py` said six capabilities, every writer
declared four for it, and the manifest schema's enum admitted neither of the
two extra names, so a writer that DID copy the loader's own list produced a
manifest its own schema rejected. A third-party writer found it (finding
F-AC-4, 2026-10-13); it is the S-19 failure again, and it is the envelope
magic table's failure with a different table.

The cure is the same as for every other table-in-N-files in this repository:
ONE statement, and everybody else reads it. Each loader carries one line, in a
comment, in its first 200 lines:

    WERK-LOADER-CAPABILITIES: read-manifest verify-hashes read-envelope materialize

and a writer that embeds the loader reads the list out of the bytes it is
embedding. The loader is then the single authority on what the loader does,
which is the only arrangement in which the two cannot drift.

`tests/run_gate_reference.py` checks that every loader has the line, that
every name on it is in the `capabilities` enum of both manifest schemas, and
that every fixture's manifest declares exactly that list for the loader it
carries.
"""

MARK = b"WERK-LOADER-CAPABILITIES:"


def loader_capabilities(data):
    """The capability list a loader's own source declares, in its order."""
    head = b"\n".join(data.split(b"\n")[:200])
    at = head.find(MARK)
    if at < 0:
        raise ValueError("this loader does not state its capabilities: no `%s` line in "
                         "its first 200 lines" % MARK.decode("ascii"))
    line = head[at + len(MARK):].split(b"\n", 1)[0]
    caps = [c.decode("ascii") for c in line.replace(b"*/", b" ").split()]
    if not caps:
        raise ValueError("the `%s` line names no capability" % MARK.decode("ascii"))
    return caps


if __name__ == "__main__":
    import sys
    for path in sys.argv[1:]:
        with open(path, "rb") as fh:
            print("%s: %s" % (path, " ".join(loader_capabilities(fh.read()))))
