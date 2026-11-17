#!/usr/bin/env python3
"""write_minimal_3d_entity.py -- write a minimal valid werk package of profile
`3d-entity/1` from scratch, with the Python standard library and nothing else.

    python write_minimal_3d_entity.py <a werk package> <out.werk>
    python write_minimal_3d_entity.py <a werk package> <out-directory> --dir

This is the executable half of spec/WRITING-3D-ENTITY.md, which is NORMATIVE
and which you should read beside it: every step below is a numbered step
there, and every number that document quotes is printed by this script.

"From the file alone" is meant literally. The first argument is any werk
package you are holding -- very likely the one this script came out of, zipped
or unzipped. The script takes from it the two things a writer does not author:
the specification (`spec/`) and the bootstrap readers (`loaders/`), which every
package carries and which a new package must carry too. Everything else it
makes itself:

    geometry/triangle.glb   one indexed triangle: the smallest thing a
                            `core.geom.game` node may hold
    physics/bounds.json     its bounds, MEASURED from that file, so the package
                            has one derived node and one `input_hash` to check
    LICENSE, README.txt
    MANIFEST.json

It shares no code with any werk tool. It imports nothing but hashlib, json,
os, struct, sys, zipfile and zlib.
"""

import hashlib
import json
import os
import struct
import sys
import zipfile
import zlib

TOOL = "spec/examples/write_minimal_3d_entity.py"
TOOL_VERSION = "1"

# A fixed instant and a fixed identity, so that two runs of this script against
# the same donor package produce the same bytes and the walkthrough can quote
# hashes. YOUR package gets the time you wrote it and a NEW random uuid
# (uuid.uuid4()): two packages with one uuid claim to be the same entity.
CREATED = "2026-10-13T00:00:00Z"
ENTITY_UUID = "3d000000-0000-4000-8000-000000000001"

# Law 8: every convention of the profile, as a machine value. These twenty-one
# are fixed by `3d-entity/1` (spec/SPEC.md section 2); a writer copies them and
# a reader refuses a package that declares anything else.
CONVENTIONS = {
    "endianness": "le", "units_per_meter": 1.0, "length_unit": "metre",
    "angle_unit": "radian", "time_unit": "second", "mass_unit": "kilogram",
    "up_axis": "y", "forward_axis": "-z", "right_axis": "+x",
    "handedness": "right", "winding": "ccw", "quat_order": "wxyz",
    "oct_encoding_pole": "y", "sh_l1_order": ["dc", "y", "z", "x"],
    "color_space_default": "srgb", "uv_origin": "top-left",
    "alignment_bytes": 16, "text_encoding": "utf-8", "id_case": "kebab-case",
    "hash_algorithm": "sha256", "signature_algorithm": "ed25519",
}

ENTRY_ORDER = ["MANIFEST.json", "SIGNATURE.json", "LICENSE", "README.txt",
               "loaders/", "spec/", "physics/", "geometry/"]

LICENSE_TEXT = """\
LICENCE TERMS NOT ESTABLISHED

This package is a worked example written by spec/examples/write_minimal_3d_entity.py.
Its content is one triangle. Whoever ran the script decides the terms under
which that content is offered; none are stated here, and this file says so
instead of inventing some. The werk format records licence facts and enforces
none (spec/SPEC.md section 2, `license`).

The specification under spec/ and the readers under loaders/ are not the
content of this package. They are the format, copied unchanged from the
package this one was written from, and they keep whatever terms they had
there.
"""

README_TEXT = """\
This is a werk package. Everything needed to read it is inside it.

Start with spec/README.md. loaders/ holds single-file, dependency-free readers
in Python, Rust and C; any one of them lists the nodes and verifies every hash:

    python loaders/werk_read.py <this file> --verify

This particular package is the worked example of spec/WRITING-3D-ENTITY.md:
one triangle (geometry/triangle.glb) and its measured bounds
(physics/bounds.json), written from scratch by
spec/examples/write_minimal_3d_entity.py.
"""


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def pretty(value):
    """How every JSON file here is spelled: two-space indent, UTF-8 without
    escaping, one trailing newline. The spelling is free -- a file is hashed as
    the bytes it is -- but it has to be SOME fixed spelling to be reproducible."""
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def canonical(value):
    """Canonical JSON for hashing a VALUE (spec/MINI-SPECS.md section 3): keys
    sorted by UTF-8 bytes, no whitespace, non-ASCII written as itself."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


# ---------------------------------------------------------------------------
# step 1 -- the specification and the readers, copied from a package you hold
# ---------------------------------------------------------------------------

def read_donor(path):
    """Return (read(path) -> bytes, manifest) for a zip or directory package."""
    if os.path.isdir(path):
        def read(rel):
            with open(os.path.join(path, *rel.split("/")), "rb") as fh:
                return fh.read()
    else:
        z = zipfile.ZipFile(path)   # MINI-SPECS section 5: any zip library works

        def read(rel):
            return z.read(rel)
    return read, json.loads(read("MANIFEST.json").decode("utf-8"))


def carried_nodes(read, donor):
    """The donor's `core.spec` and `core.loader` nodes at their ACTIVE version:
    the files (path -> bytes) and a fresh node record for each."""
    files, nodes = {}, []
    for n in donor["nodes"]:
        if n["type"] not in ("core.spec", "core.loader"):
            continue
        active = next(v for v in n["versions"] if v["v"] == n["active"])
        listed = []
        for f in active["files"]:
            data = read(f["path"])
            if sha256(data) != f["sha256"]:
                raise SystemExit("the donor's %s does not match its declared hash; "
                                 "refusing to copy a damaged specification" % f["path"])
            files[f["path"]] = data
            entry = {"path": f["path"], "sha256": f["sha256"], "size": len(data)}
            if "media_type" in f:
                entry["media_type"] = f["media_type"]
            listed.append(entry)
        note = ("The specification this package conforms to, travelling inside it "
                "(law 2); copied unchanged from the package it was written from."
                if n["type"] == "core.spec" else
                "A single-file, dependency-free reader, so the package carries a way "
                "to read itself (law 1); copied unchanged.")
        node = {"node_id": n["node_id"], "type": n["type"],
                "versions": [version(listed, note, "authored")],
                "active": 1, "edges": []}
        if "meta" in n:
            node["meta"] = n["meta"]            # a loader's language, entrypoint, ...
        nodes.append(node)
    if not any(n["type"] == "core.spec" for n in nodes):
        raise SystemExit("the donor package carries no core.spec node; a package "
                         "cannot be written from it")
    return files, nodes


# ---------------------------------------------------------------------------
# step 3 -- the payloads
# ---------------------------------------------------------------------------

def triangle_glb():
    """One indexed triangle, POSITION and NORMAL, per spec/SPEC.md section 3.10
    and spec/MINI-SPECS.md section 10. Metres, +Y up, counter-clockwise seen
    from +Z, so the normal is +Z."""
    positions = [(-0.5, 0.0, 0.0), (0.5, 0.0, 0.0), (0.0, 1.0, 0.0)]
    normals = [(0.0, 0.0, 1.0)] * 3
    indices = (0, 1, 2)
    binary = b"".join(struct.pack("<3f", *p) for p in positions)        # 36 bytes
    binary += b"".join(struct.pack("<3f", *n) for n in normals)         # 36 bytes
    binary += struct.pack("<3H", *indices)                              # 6 bytes
    binary += b"\x00" * (-len(binary) % 4)                              # pad BIN with zeros
    gltf = {
        "asset": {"version": "2.0", "generator": TOOL},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": "triangle"}],
        "meshes": [{"primitives": [{"mode": 4,
                                    "attributes": {"POSITION": 0, "NORMAL": 1},
                                    "indices": 2}]}],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3",
             "min": [-0.5, 0.0, 0.0], "max": [0.5, 1.0, 0.0]},
            {"bufferView": 1, "componentType": 5126, "count": 3, "type": "VEC3"},
            {"bufferView": 2, "componentType": 5123, "count": 3, "type": "SCALAR"},
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": 36},
            {"buffer": 0, "byteOffset": 36, "byteLength": 36},
            {"buffer": 0, "byteOffset": 72, "byteLength": 6},
        ],
        "buffers": [{"byteLength": len(binary)}],
    }
    chunk = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    chunk += b" " * (-len(chunk) % 4)                                   # pad JSON with spaces
    total = 12 + 8 + len(chunk) + 8 + len(binary)
    return (b"glTF" + struct.pack("<II", 2, total)
            + struct.pack("<I", len(chunk)) + b"JSON" + chunk
            + struct.pack("<I", len(binary)) + b"BIN\x00" + binary)


def bounds_json():
    """The triangle's bounds, in model space. Its smallest enclosing sphere is
    its circumscribed circle: centre (0, 0.375, 0), radius 0.625, exactly."""
    return pretty({
        "schema_version": 1,
        "space": "model",
        "entity": {
            "aabb_min": [-0.5, 0.0, 0.0],
            "aabb_max": [0.5, 1.0, 0.0],
            "sphere_center": [0.0, 0.375, 0.0],
            "sphere_radius": 0.625,
            "sphere_method": "welzl-exact",
        },
        "epistemic": "measured",
        "note": "Measured from geometry/triangle.glb: three vertices, so the minimal "
                "sphere is the triangle's circumscribed circle.",
    })


# ---------------------------------------------------------------------------
# step 4 -- node and version records
# ---------------------------------------------------------------------------

def file_record(path, data, media_type=None):
    rec = {"path": path, "sha256": sha256(data), "size": len(data)}
    if media_type:
        rec["media_type"] = media_type
    return rec


def version(files, note, epistemic, input_files=None, input_hash=None):
    v = {"v": 1, "files": files, "note": note,
         "producer": {"tool": TOOL, "version": TOOL_VERSION},
         "epistemic": epistemic, "created": CREATED}
    if input_files is not None:
        # Law 5: a derived version says what it was derived from, IN ORDER, and
        # carries the hash of exactly that. `input_params` is written out even
        # when it is empty: {} and absent hash identically, and spelling it out
        # means no reader has to discover that.
        v["input_files"] = input_files
        v["input_params"] = {}
        v["input_hash"] = input_hash
    return v


def input_hash_of(files, paths, params):
    """spec/MINI-SPECS.md section 11: each input's sha256 as 32 RAW bytes, in
    the order input_files lists them, then the canonical JSON of input_params."""
    h = hashlib.sha256()
    for p in paths:
        h.update(hashlib.sha256(files[p]).digest())
    h.update(canonical(params))
    return h.hexdigest()


def spec_sha256_of(nodes):
    """spec/SPEC.md section 2: over every path under spec/ the manifest
    declares, in ascending byte order of the path -- path, 0x0A, the file's
    sha256 as 32 raw bytes, 0x0A -- and the sha256 of that."""
    declared = {}
    for n in nodes:
        for v in n["versions"]:
            for f in v["files"]:
                if f["path"].startswith("spec/"):
                    declared[f["path"]] = f["sha256"]
    acc = b""
    for path in sorted(declared, key=lambda p: p.encode("utf-8")):
        acc += path.encode("utf-8") + b"\n" + bytes.fromhex(declared[path]) + b"\n"
    return hashlib.sha256(acc).hexdigest()


# ---------------------------------------------------------------------------
# step 6 -- the container
# ---------------------------------------------------------------------------

def physical_order(paths):
    """`container.entry_order`, applied: every exact path first, in list order,
    then the directory prefixes in list order, each group sorted; then anything
    left, sorted. MANIFEST.json is always first."""
    left = sorted(paths)
    placed = {}
    for i, pat in enumerate(ENTRY_ORDER):
        if not pat.endswith("/") and pat in left:
            placed[pat] = i
    for i, pat in enumerate(ENTRY_ORDER):
        if pat.endswith("/"):
            for p in left:
                if p not in placed and p.startswith(pat):
                    placed[p] = i
    listed = sorted((p for p in left if p in placed), key=lambda p: (placed[p], p))
    return listed + [p for p in left if p not in placed]


def write_zip(dest, entries):
    """A store-mode zip, written by hand from spec/MINI-SPECS.md section 5:
    method 0, UTF-8 names (flag bit 11), no data descriptor (flag bit 3 clear),
    a fixed timestamp so the same content gives the same bytes."""
    dos_time, dos_date = (9 << 11), ((2026 - 1980) << 9) | (8 << 5) | 8
    body, central = bytearray(), bytearray()
    for name, data in entries:
        nb = name.encode("utf-8")
        crc = zlib.crc32(data) & 0xFFFFFFFF
        offset = len(body)
        body += struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, 0x0800, 0, dos_time,
                            dos_date, crc, len(data), len(data), len(nb), 0)
        body += nb + data
        central += struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, 20, 20, 0x0800, 0,
                               dos_time, dos_date, crc, len(data), len(data),
                               len(nb), 0, 0, 0, 0, 0, offset)
        central += nb
    end = struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, len(entries), len(entries),
                      len(central), len(body), 0)
    with open(dest, "wb") as fh:
        fh.write(bytes(body) + bytes(central) + end)


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 2:
        print(__doc__)
        return 2
    donor_path, dest = args
    as_dir = "--dir" in argv

    # 1. the specification and the readers
    read, donor = read_donor(donor_path)
    files, nodes = carried_nodes(read, donor)
    bounds_schema = "spec/schemas/core.phys.bounds.schema.json"
    if bounds_schema not in files:
        raise SystemExit("the donor package does not carry %s, which this example's "
                         "bounds node needs; use a package of profile 3d-entity/1"
                         % bounds_schema)

    # 2. licence and readme
    files["LICENSE"] = LICENSE_TEXT.encode("utf-8")
    files["README.txt"] = README_TEXT.encode("utf-8")
    nodes.append({"node_id": "license", "type": "core.license",
                  "versions": [version([file_record("LICENSE", files["LICENSE"], "text/plain")],
                                       "The licence statement, embedded in full, never a link "
                                       "(law 7).", "authored")],
                  "active": 1, "edges": []})
    nodes.append({"node_id": "readme", "type": "core.readme",
                  "versions": [version([file_record("README.txt", files["README.txt"],
                                                    "text/plain")],
                                       "One page for a human who opened the archive by hand.",
                                       "authored")],
                  "active": 1, "edges": []})

    # 3. the payloads
    files["geometry/triangle.glb"] = triangle_glb()
    files["physics/bounds.json"] = bounds_json()

    # 4. their nodes
    nodes.append({"node_id": "geom-game", "type": "core.geom.game", "part_id": "triangle",
                  "versions": [version([file_record("geometry/triangle.glb",
                                                    files["geometry/triangle.glb"],
                                                    "model/gltf-binary")],
                                       "The mesh: one triangle, written by hand to show the "
                                       "smallest valid geometry payload.", "authored")],
                  "active": 1, "edges": []})
    bounds_inputs = ["geometry/triangle.glb"]
    bounds_hash = input_hash_of(files, bounds_inputs, {})
    nodes.append({"node_id": "bounds", "type": "core.phys.bounds",
                  "versions": [version([file_record("physics/bounds.json",
                                                    files["physics/bounds.json"],
                                                    "application/json")],
                                       "Axis-aligned box and minimal sphere, measured from "
                                       "the mesh; recompute input_hash to see that it is "
                                       "current.", "measured",
                                       input_files=bounds_inputs, input_hash=bounds_hash)],
                  "active": 1,
                  # `requires`: bounds of a mesh that is gone describe nothing.
                  "edges": [{"to": "geom-game", "kind": "requires", "role": "measured-from"}]})

    # 5. the manifest
    manifest = {
        "werk": {"major": 1, "minor": 0},
        "profile": "3d-entity/1",
        "manifest_schema": "spec/schemas/manifest.schema.json",
        "spec_sha256": spec_sha256_of(nodes),
        "entity": {"uuid": ENTITY_UUID, "name": "Minimal triangle",
                   "summary": "The worked example of spec/WRITING-3D-ENTITY.md: one "
                              "triangle and its measured bounds.",
                   "created": CREATED},
        "conventions": CONVENTIONS,
        "container": {"form": "directory" if as_dir else "zip",
                      "zip_compression": "store", "entry_order": ENTRY_ORDER},
        "license": {"file": "LICENSE", "sha256": sha256(files["LICENSE"])},
        "schemas": {"core.phys.bounds": bounds_schema},
        "layouts": {},
        "parts": [{"part_id": "triangle", "name": "Triangle", "parent": None,
                   "transform": {"translation": [0.0, 0.0, 0.0],
                                 "rotation": [1.0, 0.0, 0.0, 0.0],
                                 "scale": [1.0, 1.0, 1.0]}}],
        "materials": [],
        "primary": {"mesh": "geom-game"},
        "nodes": nodes,
        "generator": {"tool": TOOL, "version": TOOL_VERSION},
    }
    if "spec/conventions-map.json" in files:
        manifest["conventions_map"] = "spec/conventions-map.json"
    files["MANIFEST.json"] = pretty(manifest)

    # 6. the container
    order = physical_order(files)
    order.remove("MANIFEST.json")
    order.insert(0, "MANIFEST.json")
    if as_dir:
        for p in order:
            full = os.path.join(dest, *p.split("/"))
            os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
            with open(full, "wb") as fh:
                fh.write(files[p])
    else:
        write_zip(dest, [(p, files[p]) for p in order])

    # the checkpoints spec/WRITING-3D-ENTITY.md quotes
    glb, bounds = files["geometry/triangle.glb"], files["physics/bounds.json"]
    print("geometry/triangle.glb   %d bytes  sha256 %s" % (len(glb), sha256(glb)))
    print("physics/bounds.json     %d bytes  sha256 %s" % (len(bounds), sha256(bounds)))
    print("bounds input_hash       %s" % bounds_hash)
    print("spec_sha256             %s   (depends on the package you copied spec/ from)"
          % manifest["spec_sha256"])
    print("nodes                   %d   files %d (+ MANIFEST.json)"
          % (len(nodes), len(files) - 1))
    print("wrote %s" % dest)
    print("check it:  python loaders/werk_read.py %s --verify --strict" % dest)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
