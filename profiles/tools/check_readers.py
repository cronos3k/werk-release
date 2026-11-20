#!/usr/bin/env python3
"""check_readers.py -- every profiles/*/read_*.py carries profiles/tools/container_block.py
verbatim (the shared container code of the six reference readers), and each is self-contained
(imports only the Python standard library).

    python profiles/tools/check_readers.py        exit 0 when all six pass
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILES = os.path.dirname(HERE)
READERS = {"raster-layers": "read_raster_layers.py", "vector-art": "read_vector_art.py",
           "motion-comp": "read_motion_comp.py", "rich-document": "read_rich_document.py",
           "spreadsheet": "read_spreadsheet.py", "presentation": "read_presentation.py"}
STDLIB = {"argparse", "hashlib", "json", "os", "struct", "sys", "zlib"}


def main():
    block = open(os.path.join(HERE, "container_block.py"), encoding="utf-8").read()
    bad = 0
    for prof, fn in READERS.items():
        src = open(os.path.join(PROFILES, prof, fn), encoding="utf-8").read()
        has = block in src
        mods = set()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Import):
                mods.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                mods.add((node.module or "").split(".")[0])
        extra = sorted(mods - STDLIB)
        ok = has and not extra
        bad += not ok
        print("%-14s %-24s block %-5s imports %s %s" % (prof, fn, has, sorted(mods), "OK" if ok else "FAIL %s" % extra))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
