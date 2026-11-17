#!/usr/bin/env python3
"""make_inputs.py -- the deterministic synthetic inputs of the cross-matrix.

    python tests/make_inputs.py <out-dir>

Pure standard library, no randomness: the same bytes on every machine. Writes

    source.png (8x8 RGBA, the WRITING-IMAGE.md test pattern), thumb.png (4x4),
    tex-albedo.png, tex-normal.png, preview.png (16x16), triangle.glb (the
    WRITING-3D-ENTITY.md triangle), empty.bin (0 bytes), notes-unicode.txt,
    big.bin (BIG_MB MiB of a fixed LCG stream, for the directory-form large
    file case), recipe.json, disclosure.json, key.hex (RFC 8032 test key 1,
    public by construction), and attach-NN.txt for the many-nodes case.
"""

import json
import os
import struct
import sys
import zlib

BIG_MB = int(os.environ.get("WERK_BIG_MB", "24"))


def png(rows):
    height, width = len(rows), len(rows[0])
    raw = b"".join(b"\x00" + bytes(c for px in row for c in px) for row in rows)

    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))
    stored = b""
    for i in range(0, len(raw), 0xFFFF):
        part = raw[i:i + 0xFFFF]
        last = 1 if i + 0xFFFF >= len(raw) else 0
        stored += struct.pack("<BHH", last, len(part), len(part) ^ 0xFFFF) + part
    idat = b"\x78\x01" + stored + struct.pack(">I", zlib.adler32(raw) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", idat) + chunk(b"IEND", b""))


def pattern(n, seed):
    return [[((x * 36 + seed) % 256, (y * 36 + 2 * seed) % 256,
              192 if ((x // 2) + (y // 2)) % 2 == 0 else 64,
              128 if (x >= n // 2 and y >= n // 2) else 255) for x in range(n)] for y in range(n)]


def box_half(rows):
    out = []
    for y in range(0, len(rows), 2):
        row = []
        for x in range(0, len(rows[0]), 2):
            b = [rows[y][x], rows[y][x + 1], rows[y + 1][x], rows[y + 1][x + 1]]
            row.append(tuple((sum(p[c] for p in b) + 2) // 4 for c in range(4)))
        out.append(row)
    return out


def triangle_glb():
    pos = struct.pack("<9f", -0.5, 0, 0, 0.5, 0, 0, 0, 1, 0)
    nrm = struct.pack("<9f", 0, 0, 1, 0, 0, 1, 0, 0, 1)
    idx = struct.pack("<3H", 0, 1, 2) + b"\x00\x00"
    binc = pos + nrm + idx
    gltf = {"asset": {"version": "2.0", "generator": "werk libs make_inputs"},
            "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
            "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1},
                                        "indices": 2, "mode": 4}]}],
            "buffers": [{"byteLength": len(binc)}],
            "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 36},
                            {"buffer": 0, "byteOffset": 36, "byteLength": 36},
                            {"buffer": 0, "byteOffset": 72, "byteLength": 6}],
            "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3",
                           "min": [-0.5, 0, 0], "max": [0.5, 1, 0]},
                          {"bufferView": 1, "componentType": 5126, "count": 3, "type": "VEC3"},
                          {"bufferView": 2, "componentType": 5123, "count": 3, "type": "SCALAR"}]}
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    total = 12 + 8 + len(js) + 8 + len(binc)
    return (b"glTF" + struct.pack("<II", 2, total) + struct.pack("<I", len(js)) + b"JSON" + js
            + struct.pack("<I", len(binc)) + b"BIN\x00" + binc)


def main(out):
    os.makedirs(out, exist_ok=True)

    def put(name, data):
        with open(os.path.join(out, name), "wb") as fh:
            fh.write(data)
    src = pattern(8, 0)
    put("source.png", png(src))
    put("thumb.png", png(box_half(src)))
    put("tex-albedo.png", png(pattern(8, 17)))
    put("tex-normal.png", png([[(128, 128, 255, 255)] * 4] * 4))
    put("preview.png", png(pattern(16, 5)))
    put("triangle.glb", triangle_glb())
    put("empty.bin", b"")
    put("notes-unicode.txt", "Größe → straße · 日本語 · emoji 🎨 · tab\tend\n".encode("utf-8"))
    put("profile-extra.md", "# A profile document this bundle does not carry\n\nWritten by "
        "tests/make_inputs.py for the spec-files case: Größe.\n".encode("utf-8"))
    put("spec-readme.md", b"# spec/README.md, replaced by the writing application\n")
    put("key.hex", b"9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60\n")
    put("key2.hex", b"4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb\n")
    for i in range(40):
        put("attach-%02d.txt" % i, ("attachment %d of the many-nodes case\n" % i).encode())
    import hashlib
    sp = png(src)
    recipe = {
        "recipe_version": 1,
        "target": {"node_id": "image-source", "version": 1,
                   "files": [{"path": "image/source.png",
                              "sha256": hashlib.sha256(sp).hexdigest(), "size": len(sp)}]},
        "reproducibility": "deterministic",
        "reproducibility_note": "The pattern is a closed-form function of the pixel position; "
                                "tests/make_inputs.py recomputes it byte for byte.",
        "steps": [{"step_id": "pattern", "role": "other",
                   "tool": {"name": "tests/make_inputs.py", "version": "1"},
                   "params": {"size": 8, "scale": 0.5, "gamma": 2.2}}],
        "unrecorded": []}
    put("recipe.json", (json.dumps(recipe, indent=2, ensure_ascii=False) + "\n").encode())
    disclosure = {
        "disclosure_version": 1, "ai_generated": False, "ai_modified": False,
        "generation_scope": "none",
        "declared_by": {"name": "werk libs cross-matrix", "kind": "service",
                        "uri": "urn:werk:test:cross-matrix"},
        "declared_at": "2026-11-07T00:00:00Z",
        "human_authorship": {"claimed": True, "description": "A closed-form test pattern "
                             "written by a person, through a script. Größe: 1.0 · 日本"},
        "models": [],
        "synthetic_markers": {"declared_watermarks": [{"kind": "none", "present": False,
                                                       "note": "none"}],
                              "c2pa_manifest_present": False, "embedded_metadata_stripped": True},
        "statements": [{"id": "test-pattern", "text": "A test pattern, not a picture.",
                        "epistemic": "measured", "confidence": 1.0,
                        "basis": "the pixels are a formula"}],
        "jurisdiction_note": "Informational only."}
    put("disclosure.json", (json.dumps(disclosure, indent=2, ensure_ascii=False) + "\n").encode())
    # A Linear-congruential stream: fixed bytes, fast, no randomness.
    big = os.path.join(out, "big.bin")
    if not os.path.exists(big) or os.path.getsize(big) != BIG_MB << 20:
        x = 12345
        with open(big, "wb") as fh:
            for _ in range(BIG_MB):
                buf = bytearray(1 << 20)
                for i in range(0, 1 << 20, 4096):
                    x = (x * 1103515245 + 12345) & 0x7FFFFFFF
                    buf[i:i + 4] = struct.pack("<I", x)
                fh.write(bytes(buf))
    print("inputs in %s" % out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "inputs")
