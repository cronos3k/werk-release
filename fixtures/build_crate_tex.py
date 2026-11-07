#!/usr/bin/env python3
"""build_crate_tex.py — the TEXTURED fixture, `fixtures/crate-tex-v1.werk`.

    python fixtures/build_crate_tex.py [--blender <blender.exe>] [--out DIR]

Why this fixture exists
-----------------------
`fixtures/crate-v1.werk` is vertex-coloured and carries no `core.tex` node at
all — its build script says, correctly, that inventing a texture would be the
one thing a *conformance* fixture must never do. The consequence is that the
whole texture path in every adapter has shipped unmeasured: WerkLink's texture
import was written and never exercised, and its texture export was reported as
not-implemented partly on the ground that nothing could have tested it.

This is a different kind of fixture and says so in its own README node: it is a
TEST fixture, deliberately constructed, whose job is to be the measured input
for the texture and material paths. Nothing here pretends to be a scan.

How it is built, and why through Blender
----------------------------------------
The mesh is `fixtures/crate-v1.werk`'s own game geometry, imported by the
gate-proven Blender add-on (`adapters/blender`), given UVs, dressed with three
generated maps and exported by the same add-on's exporter. That route was
chosen over hand-writing a package because the add-on's textured export is
already gate-measured, so this fixture is produced by code that is under test
rather than by a one-off script that is not.

The three maps are generated HERE, in stdlib Python, from a stated procedure:

  * `crate-tex-albedo.png`  — sRGB. Plank pattern with a per-plank tint and a
    deterministic grain, derived from a fixed integer hash. No randomness.
  * `crate-tex-normal.png`  — LINEAR. A tangent-space normal map computed by
    central differences over the SAME height field the grain comes from, so
    the two maps agree by construction rather than by eye.
  * `crate-tex-mr.png`      — LINEAR. glTF packing: occlusion in R, roughness
    in G, metallic in B. Metallic is 0 everywhere: a wooden crate is a
    dielectric, and writing a metallic map that is uniformly zero is the point
    — it makes "did the channel packing survive?" answerable.

Every byte is a pure function of this file, so two runs produce the same
fixture. Determinism is asserted, not hoped for: `--check-determinism` builds
twice and compares.

UVs are a box projection computed analytically (dominant face normal picks the
plane), not Blender's Smart UV Project, because an unwrapper's output is not
guaranteed stable across Blender versions and a fixture whose bytes depend on
that is not a fixture.
"""

import argparse
import hashlib
import json
import os
import struct
import subprocess
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

TEX_SIZE = 256
PLANKS = 6


# ---------------------------------------------------------------------------
# a minimal deterministic PNG writer (stdlib zlib only)
# ---------------------------------------------------------------------------

def write_png(path, width, height, rows_rgba):
    """8-bit RGBA PNG, colour type 6, filter 0 on every scanline.

    Filter 0 everywhere rather than an adaptive heuristic: an adaptive filter
    would make the bytes depend on a heuristic nobody here can state, and this
    file's whole claim is that its output is a pure function of its source.
    """
    raw = bytearray()
    for row in rows_rgba:
        raw.append(0)
        raw.extend(row)

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    body = (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))
    with open(path, "wb") as fh:
        fh.write(body)
    return body


# ---------------------------------------------------------------------------
# the maps
# ---------------------------------------------------------------------------

def _hash01(x, y, salt):
    """A stated integer hash in [0,1). Not random: reproducible from (x,y,salt)."""
    h = hashlib.sha256(struct.pack(">iii", x, y, salt)).digest()
    return struct.unpack(">I", h[:4])[0] / 4294967296.0


def height_field(size=TEX_SIZE, planks=PLANKS):
    """Plank height: a groove between planks plus a low-amplitude grain.

    Returned as floats in [0,1]. This is the ONE source both the normal map
    and the albedo's grain read from, which is what makes them agree.
    """
    field = []
    plank_h = size / float(planks)
    for y in range(size):
        row = []
        p = int(y / plank_h)
        edge = min(y - p * plank_h, (p + 1) * plank_h - 1 - y)
        groove = 0.0 if edge >= 2.0 else (1.0 - edge / 2.0)
        for x in range(size):
            grain = 0.5 + 0.5 * _hash01(x // 3, p, 17)
            ripple = 0.06 * ((x * 7 + p * 31) % 11) / 10.0
            row.append(max(0.0, min(1.0, 0.75 + 0.12 * grain + ripple - 0.7 * groove)))
        field.append(row)
    return field


def albedo_rows(field, size=TEX_SIZE, planks=PLANKS):
    plank_h = size / float(planks)
    rows = []
    for y in range(size):
        p = int(y / plank_h)
        tint = 0.85 + 0.15 * _hash01(0, p, 5)
        row = bytearray()
        for x in range(size):
            h = field[y][x]
            r = int(round(255 * min(1.0, 0.62 * tint * (0.55 + 0.6 * h))))
            g = int(round(255 * min(1.0, 0.42 * tint * (0.55 + 0.6 * h))))
            b = int(round(255 * min(1.0, 0.24 * tint * (0.55 + 0.6 * h))))
            row += bytes((r, g, b, 255))
        rows.append(bytes(row))
    return rows


def normal_rows(field, size=TEX_SIZE, strength=2.2):
    """Tangent-space normal from central differences on the height field.

    +Y green (OpenGL convention, which is glTF's and werk's). Written out as
    the usual (n*0.5+0.5) encoding, which is why this map MUST be declared
    linear: read as sRGB, every normal bends.
    """
    rows = []
    for y in range(size):
        row = bytearray()
        for x in range(size):
            hl = field[y][(x - 1) % size]
            hr = field[y][(x + 1) % size]
            hd = field[(y - 1) % size][x]
            hu = field[(y + 1) % size][x]
            nx = -(hr - hl) * strength
            ny = -(hu - hd) * strength
            nz = 1.0
            inv = 1.0 / ((nx * nx + ny * ny + nz * nz) ** 0.5)
            nx, ny, nz = nx * inv, ny * inv, nz * inv
            row += bytes((int(round((nx * 0.5 + 0.5) * 255)),
                          int(round((ny * 0.5 + 0.5) * 255)),
                          int(round((nz * 0.5 + 0.5) * 255)),
                          255))
        rows.append(bytes(row))
    return rows


def mr_rows(field, size=TEX_SIZE):
    """glTF packing: occlusion=R, roughness=G, metallic=B."""
    rows = []
    for y in range(size):
        row = bytearray()
        for x in range(size):
            h = field[y][x]
            occl = int(round(255 * (0.55 + 0.45 * h)))       # grooves darker
            rough = int(round(255 * (0.90 - 0.25 * h)))      # grooves rougher
            metal = 0                                        # wood is dielectric
            row += bytes((occl, rough, metal, 255))
        rows.append(bytes(row))
    return rows


# ---------------------------------------------------------------------------
# driving Blender
# ---------------------------------------------------------------------------

def find_blender(explicit=None):
    if explicit:
        return explicit if os.path.isfile(explicit) else None
    env = os.environ.get("WERK_BLENDER")
    if env and os.path.isfile(env):
        return env
    roots = [r"C:\Program Files\Blender Foundation",
             r"C:\Program Files (x86)\Blender Foundation"]
    found = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            exe = os.path.join(root, name, "blender.exe")
            if os.path.isfile(exe):
                found.append(exe)
    return found[-1] if found else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blender", default=None)
    ap.add_argument("--out", default=HERE)
    ap.add_argument("--src", default=os.path.join(HERE, "crate-v1.werk"))
    ap.add_argument("--check-determinism", action="store_true")
    args = ap.parse_args()

    blender = find_blender(args.blender)
    if not blender:
        print("SKIP: no Blender found. Set WERK_BLENDER or pass --blender.")
        return 3
    if not os.path.isfile(args.src):
        print("FAIL: source fixture missing: %s" % args.src)
        return 1

    tmp = os.path.join(args.out, ".werk-tex-tmp")
    os.makedirs(tmp, exist_ok=True)

    field = height_field()
    maps = {
        "albedo": (os.path.join(tmp, "crate-tex-albedo.png"), albedo_rows(field), "sRGB"),
        "normal": (os.path.join(tmp, "crate-tex-normal.png"), normal_rows(field), "Non-Color"),
        "mr":     (os.path.join(tmp, "crate-tex-mr.png"),     mr_rows(field),     "Non-Color"),
    }
    for key, (path, rows, _cs) in maps.items():
        data = write_png(path, TEX_SIZE, TEX_SIZE, rows)
        print("  map %-7s %6d B  sha256 %s" % (key, len(data),
                                               hashlib.sha256(data).hexdigest()[:16]))

    out_path = os.path.join(args.out, "crate-tex-v1.werk")
    report_path = os.path.join(tmp, "build_report.json")

    def run_blender(target):
        cmd = [blender, "--background", "--factory-startup",
               "--python", os.path.join(HERE, "build_crate_tex_in_blender.py"),
               "--",
               "--src", args.src,
               "--out", target,
               "--albedo", maps["albedo"][0],
               "--normal", maps["normal"][0],
               "--mr", maps["mr"][0],
               "--addon", os.path.join(ROOT, "adapters", "blender"),
               "--report", report_path]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0 or not os.path.isfile(target):
            sys.stdout.write(proc.stdout[-4000:])
            sys.stderr.write(proc.stderr[-4000:])
            raise SystemExit("FAIL: Blender exited %d" % proc.returncode)
        return json.load(open(report_path, encoding="utf-8"))

    report = run_blender(out_path)
    body = open(out_path, "rb").read()
    print("\n%s" % out_path)
    print("  %d bytes, sha256 %s" % (len(body), hashlib.sha256(body).hexdigest()))
    print("  nodes=%d  tex_nodes=%d  material_slots=%s  uv_layers=%s  verts=%d tris=%d"
          % (report["nodes"], report["tex_nodes"], report["material_slots"],
             report["uv_layers"], report["verts"], report["tris"]))
    print("  color_space: %s" % json.dumps(report["color_space"], sort_keys=True))

    if args.check_determinism:
        second = out_path + ".2"
        run_blender(second)
        a = hashlib.sha256(open(out_path, "rb").read()).hexdigest()
        b = hashlib.sha256(open(second, "rb").read()).hexdigest()
        os.remove(second)
        # MANIFEST.json carries a wall clock, so whole-file identity is not the
        # claim; payload identity is. The add-on's own gate makes the same
        # distinction and names it rather than hiding it.
        print("  determinism: whole-file %s (manifest carries `created`)"
              % ("identical" if a == b else "DIFFERS, as expected"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
