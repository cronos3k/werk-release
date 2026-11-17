"""Vendored, byte-identical copies of werk's zero-dependency bootstrap readers.

Nothing in this directory is edited. `werk_read.py` is a byte-for-byte copy of
`loaders/werk_read.py` from the werk repository, and
`plugins/blender/test_gate.py` re-hashes both and FAILS the gate if they
differ. A vendored copy that is allowed to drift is a second authority, and a
second authority is the bug this format exists to prevent (Stage 2 decision 4
made the same call for werk-core's schemas).

Why vendor at all: the add-on must work when Blender installs it from a zip
into a directory that has never heard of the werk repo, with zero external
dependencies (stdlib + bpy only). A path import back into the repo would be a
promise about another file, which law 1 bans.
"""
